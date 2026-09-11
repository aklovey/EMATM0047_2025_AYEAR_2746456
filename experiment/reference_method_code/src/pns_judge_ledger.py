from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class IndeterminateJudgeDispatchError(RuntimeError):
    """A reserved Judge call may have been dispatched and must not be resent."""


class SemanticJudgeLedger:
    """Reserve-before-call SQLite ledger for fail-closed semantic judgments."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._closed = False
        self._connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS judge_evidence(
                evidence_id TEXT PRIMARY KEY,
                state TEXT NOT NULL CHECK(state IN ('reserved','completed')),
                identity_json TEXT NOT NULL,
                result_json TEXT
            )
            """
        )
        self._connection.commit()

    def reserve(
        self, evidence_id: str, identity: dict[str, Any]
    ) -> dict[str, Any] | None:
        key = str(evidence_id).strip()
        if not key:
            raise ValueError("Judge evidence_id must be nonempty")
        identity_payload = _canonical_json(identity)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM judge_evidence WHERE evidence_id=?",
                (key,),
            ).fetchone()
            if row is None:
                self._connection.execute(
                    """
                    INSERT INTO judge_evidence(
                        evidence_id,state,identity_json,result_json
                    ) VALUES(?,'reserved',?,NULL)
                    """,
                    (key, identity_payload),
                )
                self._connection.commit()
                return None
            if row["identity_json"] != identity_payload:
                raise RuntimeError(
                    f"Judge evidence identity differs for {key}"
                )
            if row["state"] != "completed":
                raise IndeterminateJudgeDispatchError(
                    f"Judge evidence {key} is reserved/indeterminate; no-resend"
                )
            result = json.loads(row["result_json"] or "null")
            if not isinstance(result, dict):
                raise RuntimeError(f"completed Judge evidence {key} is invalid")
            return result

    def complete(self, evidence_id: str, result: dict[str, Any]) -> None:
        key = str(evidence_id).strip()
        _validate_result_metadata(result)
        result_payload = _canonical_json(result)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM judge_evidence WHERE evidence_id=?",
                (key,),
            ).fetchone()
            if row is None:
                raise RuntimeError(
                    f"Judge evidence {key} must be reserved before completion"
                )
            if row["state"] == "completed":
                if row["result_json"] != result_payload:
                    raise RuntimeError(
                        f"Judge completed result differs for {key}"
                    )
                return
            self._connection.execute(
                """
                UPDATE judge_evidence
                SET state='completed', result_json=?
                WHERE evidence_id=? AND state='reserved'
                """,
                (result_payload, key),
            )
            self._connection.commit()

    def completed_records(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT evidence_id,identity_json,result_json
                FROM judge_evidence
                WHERE state='completed'
                ORDER BY evidence_id
                """
            ).fetchall()
        records: list[dict[str, Any]] = []
        for row in rows:
            identity = json.loads(row["identity_json"])
            result = json.loads(row["result_json"])
            records.append(
                {"evidence_id": row["evidence_id"], **identity, **result}
            )
        return records

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._connection.close()

    def __enter__(self) -> SemanticJudgeLedger:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_result_metadata(result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        raise TypeError("Judge result metadata must be an object")
    fixed = {
        "provider": "deepseek",
        "endpoint_type": "chat.completions",
        "requested_model": "deepseek-v4-pro",
        "resolved_model": "deepseek-v4-pro",
        "thinking_type": "enabled",
        "reasoning_effort": "max",
        "fallback_allowed": False,
        "fallback_used": False,
    }
    for key, expected in fixed.items():
        if result.get(key) != expected:
            raise ValueError(
                f"Judge result {key} must be {expected!r}, got {result.get(key)!r}"
            )
    accepted = result.get("accepted") is True
    if accepted and not (
        result.get("response_model") == "deepseek-v4-pro"
        and result.get("status") == "parsed"
        and result.get("parse_status") == "parsed"
        and result.get("decision") == "accepted"
    ):
        raise ValueError("accepted Judge result lacks valid DeepSeek parsed evidence")
