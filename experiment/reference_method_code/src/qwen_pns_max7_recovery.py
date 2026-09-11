from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .qwen_pns_batch56_adapter import (
    RECOVERY_EXECUTION_GATE_KEY,
    AdaptiveRolloutRecoveryAmendment,
)


MAX7_RECOVERY_CONTRACT_ID = "qwen_pns_phase56_max7_recovery_18plus3_v1"
MAX7_TARGET_QIDS = (19407, 24494, 30257)
WORKSPACE_MANIFEST_SCHEMA = "qwen_pns_existing_candidate_batch_manifest_v1"
WORKSPACE_CONTRACT_SCHEMA = "recovery_workspace_contract_v1"


@dataclass(frozen=True)
class Max7RecoveryConfig:
    source_path: Path
    workspace_manifest: Path
    source_journal: Path
    target_journal: Path
    source_future_judge_ledger: Path
    target_future_judge_ledger: Path
    target_qids: tuple[int, ...]
    base_max_raw_attempts_per_lineage: int
    amended_max_raw_attempts_per_lineage: int
    new_raw_slots_only: tuple[int, ...]
    required_completed_before_execute: int
    expected_total_items: int

    def amendment(self) -> AdaptiveRolloutRecoveryAmendment:
        return AdaptiveRolloutRecoveryAmendment(
            target_qids=self.target_qids,
            source_journal=str(self.source_journal),
            target_journal=str(self.target_journal),
            workspace_manifest=str(self.workspace_manifest),
            base_max_raw_attempts_per_lineage=(
                self.base_max_raw_attempts_per_lineage
            ),
            amended_max_raw_attempts_per_lineage=(
                self.amended_max_raw_attempts_per_lineage
            ),
            new_raw_slots_only=self.new_raw_slots_only,
            required_completed_before_execute=(
                self.required_completed_before_execute
            ),
            expected_total_items=self.expected_total_items,
        )


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _resolve_path(value: Any, *, project_root: Path, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} path is required")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def load_max7_recovery_config(
    path: str | Path, *, project_root: str | Path
) -> Max7RecoveryConfig:
    source = Path(path).resolve()
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    root = Path(project_root).resolve()
    top = _mapping(payload, label="max7 recovery config")
    if top.get("contract_id") != MAX7_RECOVERY_CONTRACT_ID:
        raise ValueError("max7 recovery contract_id differs")
    workspace = _mapping(top.get("workspace"), label="workspace")
    rollout = _mapping(top.get("rollout_amendment"), label="rollout_amendment")
    judge = _mapping(top.get("judge"), label="judge")

    required_judge = {
        "provider": "cli_proxy",
        "transport": "responses",
        "base_url": "http://127.0.0.1:8317/v1",
        "model": "gpt-5.5",
        "thinking_type": "enabled",
        "reasoning_effort": "xhigh",
        "fallback_allowed": False,
        "default_pass_allowed": False,
    }
    for key, expected in required_judge.items():
        if judge.get(key) != expected:
            raise ValueError(f"max7 recovery Judge {key} must be {expected!r}")

    target_qids = tuple(rollout.get("target_qids") or ())
    new_slots = tuple(rollout.get("new_raw_slots_only") or ())
    if target_qids != MAX7_TARGET_QIDS:
        raise ValueError(
            f"max7 recovery target_qids must be exactly {list(MAX7_TARGET_QIDS)}"
        )
    config = Max7RecoveryConfig(
        source_path=source,
        workspace_manifest=_resolve_path(
            workspace.get("manifest"), project_root=root, label="workspace manifest"
        ),
        source_journal=_resolve_path(
            workspace.get("source_journal"),
            project_root=root,
            label="source journal",
        ),
        target_journal=_resolve_path(
            workspace.get("target_journal"),
            project_root=root,
            label="target journal",
        ),
        source_future_judge_ledger=_resolve_path(
            workspace.get("source_future_judge_ledger"),
            project_root=root,
            label="source future Judge ledger",
        ),
        target_future_judge_ledger=_resolve_path(
            workspace.get("target_future_judge_ledger"),
            project_root=root,
            label="target future Judge ledger",
        ),
        target_qids=target_qids,
        base_max_raw_attempts_per_lineage=int(
            rollout.get("base_max_raw_attempts_per_lineage", -1)
        ),
        amended_max_raw_attempts_per_lineage=int(
            rollout.get("amended_max_raw_attempts_per_lineage", -1)
        ),
        new_raw_slots_only=new_slots,
        required_completed_before_execute=int(
            rollout.get("required_completed_before_execute", -1)
        ),
        expected_total_items=int(rollout.get("expected_total_items", -1)),
    )
    if config.source_journal == config.target_journal:
        raise ValueError("source and target recovery journals must differ")
    if config.source_future_judge_ledger == config.target_future_judge_ledger:
        raise ValueError("source and target future Judge ledgers must differ")
    config.amendment().validate()
    return config


def _read_item_states(path: Path) -> dict[int, str]:
    try:
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5
        )
    except sqlite3.Error as exc:
        raise RuntimeError(f"recovery journal is unavailable: {path}") from exc
    try:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute("SELECT qid,state FROM items ORDER BY qid").fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(f"recovery journal items are unreadable: {path}") from exc
    finally:
        connection.close()
    result = {int(qid): str(state) for qid, state in rows}
    if len(result) != len(rows):
        raise RuntimeError(f"recovery journal contains duplicate qids: {path}")
    return result


def read_request_rows_read_only(path: str | Path) -> list[dict[str, Any]]:
    """Read Qwen request identity/state evidence without opening a writable DB."""

    source = Path(path).resolve()
    connection = sqlite3.connect(
        f"file:{source.as_posix()}?mode=ro", uri=True, timeout=5
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute("SELECT * FROM requests ORDER BY request_seq").fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(f"recovery request evidence is unreadable: {source}") from exc
    finally:
        connection.close()
    return [dict(row) for row in rows]


def _read_meta(path: Path, key: str) -> Any:
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        try:
            row = connection.execute(
                "SELECT value_json FROM meta WHERE key=?", (key,)
            ).fetchone()
        except sqlite3.OperationalError:
            return None
    finally:
        connection.close()
    return None if row is None else json.loads(row[0])


def verify_recovery_workspace(
    config: Max7RecoveryConfig, *, require_execution_ready: bool
) -> dict[str, Any]:
    """Read-only proof that the new root is the prepared journal/ledger copy."""

    if not config.workspace_manifest.is_file():
        raise RuntimeError(
            f"recovery workspace manifest is missing: {config.workspace_manifest}"
        )
    payload = json.loads(config.workspace_manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != (
        WORKSPACE_MANIFEST_SCHEMA
    ):
        raise RuntimeError("recovery workspace manifest schema differs")
    workspace = _mapping(
        payload.get("workspace_contract"), label="workspace_contract"
    )
    if workspace.get("schema_version") != WORKSPACE_CONTRACT_SCHEMA:
        raise RuntimeError("recovery workspace contract schema differs")
    expected_paths = {
        "source_journal": config.source_journal,
        "target_journal": config.target_journal,
        "source_future_judge_ledger": config.source_future_judge_ledger,
        "target_future_judge_ledger": config.target_future_judge_ledger,
    }
    for key, expected in expected_paths.items():
        actual = Path(str(workspace.get(key) or "")).resolve()
        if actual != expected:
            raise RuntimeError(f"recovery workspace {key} differs")
    if workspace.get("source_journal_mutated") is not False:
        raise RuntimeError("recovery workspace must attest source_journal_mutated=false")
    if workspace.get("copied_via_sqlite_backup") is not True:
        raise RuntimeError("recovery workspace lacks SQLite backup attestation")

    partition = _mapping(
        workspace.get("pending_partition"), label="pending_partition"
    )
    max7_qids = tuple(partition.get("max7_qids") or ())
    review18_qids = tuple(partition.get("review18_qids") or ())
    initial_pending = tuple(partition.get("exact_initial_pending_qids") or ())
    if max7_qids != config.target_qids:
        raise RuntimeError("workspace max7 qids differ")
    if len(review18_qids) != 18 or len(set(review18_qids)) != 18:
        raise RuntimeError("workspace review18 partition is not exact")
    if set(review18_qids).intersection(max7_qids):
        raise RuntimeError("workspace review18 and max7 partitions overlap")
    if set(initial_pending) != set((*review18_qids, *max7_qids)) or (
        partition.get("exact_initial_pending_count") != 21
    ):
        raise RuntimeError("workspace initial pending partition differs")

    for path in expected_paths.values():
        if not path.is_file():
            raise RuntimeError(f"recovery workspace artifact is missing: {path}")
    source_states = _read_item_states(config.source_journal)
    target_states = _read_item_states(config.target_journal)
    if len(source_states) != config.expected_total_items or len(target_states) != (
        config.expected_total_items
    ):
        raise RuntimeError("source/target journal must each contain exact56")
    source_pending = {
        qid for qid, state in source_states.items() if state != "completed"
    }
    if source_pending != set(initial_pending):
        raise RuntimeError("source journal no longer has the frozen 35+21 partition")
    target_pending = {
        qid for qid, state in target_states.items() if state != "completed"
    }
    if not target_pending.issubset(set(initial_pending)):
        raise RuntimeError("target journal changed outside the frozen pending partition")

    completed_count = sum(state == "completed" for state in target_states.values())
    if require_execution_ready:
        prior_gate = _read_meta(config.target_journal, RECOVERY_EXECUTION_GATE_KEY)
        first_ready = (
            completed_count == config.required_completed_before_execute
            and target_pending == set(config.target_qids)
        )
        resumed_ready = (
            isinstance(prior_gate, dict)
            and prior_gate.get("passed") is True
            and completed_count >= config.required_completed_before_execute
            and target_pending.issubset(set(config.target_qids))
        )
        if not (first_ready or resumed_ready):
            raise RuntimeError(
                "max7 recovery execution requires review18 terminal and 53 completed"
            )

    return {
        "schema_version": "qwen_pns_max7_recovery_workspace_evidence_v1",
        "status": (
            "RECOVERY_WORKSPACE_EXECUTION_READY"
            if require_execution_ready
            else "RECOVERY_WORKSPACE_PREPARED"
        ),
        "workspace_manifest": str(config.workspace_manifest),
        "source_journal": str(config.source_journal),
        "target_journal": str(config.target_journal),
        "source_journal_opened_read_only": True,
        "source_journal_mutated": False,
        "completed_count": completed_count,
        "pending_qids": sorted(target_pending),
        "target_qids": list(config.target_qids),
        "new_raw_slots_only": list(config.new_raw_slots_only),
        "actual_judge_model": "gpt-5.5",
        "reasoning_effort": "xhigh",
        "fallback_allowed": False,
    }


def _strict_cli_proxy_judge(record: Mapping[str, Any]) -> bool:
    return bool(
        record.get("provider") == "cli_proxy"
        and record.get("actual_judge_model") == "gpt-5.5"
        and record.get("thinking_type") == "enabled"
        and record.get("reasoning_effort") == "xhigh"
        and record.get("status") == "parsed"
        and record.get("parse_status") == "parsed"
        and record.get("fallback_allowed") is False
        and record.get("fallback_used") is False
    )


def build_max7_recovery_report_payload(
    amendment: AdaptiveRolloutRecoveryAmendment,
    *,
    artifacts: Sequence[Mapping[str, Any]],
    item_rows: Sequence[Mapping[str, Any]],
    source_request_rows: Sequence[Mapping[str, Any]],
    request_rows: Sequence[Mapping[str, Any]],
    judge_records: Sequence[Mapping[str, Any]],
    workspace_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute the 3-qid amendment result from accepted/runtime evidence."""

    amendment.validate()
    if not (
        workspace_evidence.get("source_journal_opened_read_only") is True
        and workspace_evidence.get("source_journal_mutated") is False
    ):
        raise RuntimeError("max7 report requires read-only source-journal evidence")
    by_qid = {int(row["question_id"]): row for row in artifacts}
    if len(by_qid) != amendment.expected_total_items or len(artifacts) != (
        amendment.expected_total_items
    ):
        raise RuntimeError("max7 report requires exact56 unique accepted artifacts")
    item_states = {int(row["qid"]): str(row.get("state") or "pending") for row in item_rows}
    if set(item_states) != set(by_qid) or any(
        state != "completed" for state in item_states.values()
    ):
        raise RuntimeError("max7 report requires exact56 completed journal items")

    materialization_ids: set[str] = set()
    target_records: list[dict[str, Any]] = []
    for qid in amendment.target_qids:
        artifact = by_qid.get(qid)
        if artifact is None:
            raise RuntimeError(f"max7 accepted artifact is missing q{qid}")
        rollout = artifact.get("adaptive_rollout")
        recovery = artifact.get("rollout_recovery_amendment")
        judge = artifact.get("judge_acceptance")
        if not isinstance(rollout, Mapping) or rollout.get(
            "max_raw_attempts_per_lineage"
        ) != 7:
            raise RuntimeError(f"q{qid} did not use the amended max7 rollout cap")
        expected_recovery = {
            "contract_id": MAX7_RECOVERY_CONTRACT_ID,
            "schema_version": "adaptive_rollout_recovery_amendment_v1",
            "targeted": True,
            "base_max_raw_attempts_per_lineage": 5,
            "effective_max_raw_attempts_per_lineage": 7,
            "new_raw_slots_only": [6, 7],
            "source_journal_mutated": False,
        }
        if not isinstance(recovery, Mapping) or any(
            recovery.get(key) != value for key, value in expected_recovery.items()
        ):
            raise RuntimeError(f"q{qid} max7 amendment metadata differs")
        if not isinstance(judge, Mapping) or not (
            _strict_cli_proxy_judge(judge)
            and judge.get("accepted") is True
            and judge.get("decision") == "accepted"
        ):
            raise RuntimeError(f"q{qid} materialization Judge did not pass fail-closed")
        evidence_id = str(judge.get("evidence_id") or "")
        if not evidence_id.startswith(f"materialization:q{qid}:"):
            raise RuntimeError(f"q{qid} materialization Judge evidence id differs")
        materialization_ids.add(evidence_id)
        if not (
            artifact.get("optimized") is True
            and artifact.get("fallback") is False
            and int(artifact["final_qwen_tokens"])
            < int(artifact["original_qwen_tokens"])
        ):
            raise RuntimeError(f"q{qid} is not an optimized strictly shorter artifact")
        target_records.append(
            {
                "question_id": qid,
                "selected_request_key": str(artifact["selected_request_key"]),
                "materialization_judge_evidence_id": evidence_id,
                "original_qwen_tokens": int(artifact["original_qwen_tokens"]),
                "final_qwen_tokens": int(artifact["final_qwen_tokens"]),
            }
        )

    source_keys = {str(row.get("request_key") or "") for row in source_request_rows}
    target_keys = {str(row.get("request_key") or "") for row in request_rows}
    if "" in source_keys or "" in target_keys:
        raise RuntimeError("max7 request evidence contains an empty request key")
    new_rows = [
        row for row in request_rows if str(row["request_key"]) not in source_keys
    ]
    new_keys = {str(row["request_key"]) for row in new_rows}
    if len(new_keys) != len(new_rows) or not new_rows:
        raise RuntimeError("max7 request delta must be nonempty and unique")
    if not source_keys.issubset(target_keys):
        raise RuntimeError("copied recovery journal lost historical Qwen requests")
    target_set = set(amendment.target_qids)
    if any(
        int(row.get("qid", -1)) not in target_set
        or int(row.get("rollout", -1)) not in amendment.new_raw_slots_only
        or str(row.get("state") or "") not in {"completed", "scientific_invalid"}
        or row.get("posting_at") is None
        for row in new_rows
    ):
        raise RuntimeError("max7 request delta contains an unauthorized Qwen slot")
    counts_by_qid = {
        qid: sum(int(row["qid"]) == qid for row in new_rows)
        for qid in amendment.target_qids
    }
    if any(count < 1 for count in counts_by_qid.values()):
        raise RuntimeError("each max7 target must contribute at least one new Qwen slot")

    relevant_judges = [
        record
        for record in judge_records
        if str(record.get("evidence_id") or "") in materialization_ids
        or (
            int(record.get("qid", -1)) in target_set
            and int(record.get("raw_attempt", -1)) in amendment.new_raw_slots_only
            and str(record.get("request_key") or "") in new_keys
        )
    ]
    if not materialization_ids.issubset(
        {str(record.get("evidence_id") or "") for record in relevant_judges}
    ):
        raise RuntimeError("max7 materialization Judge evidence is absent from ledger")
    if not relevant_judges or any(
        not _strict_cli_proxy_judge(record) for record in relevant_judges
    ):
        raise RuntimeError("max7 new Judge ledger contains invalid routing metadata")

    return {
        "schema_version": "qwen_pns_max7_recovery_report_v1",
        "contract_id": MAX7_RECOVERY_CONTRACT_ID,
        "status": "COMPLETE",
        "workspace": {
            "manifest": str(Path(amendment.workspace_manifest).resolve()),
            "source_journal": str(Path(amendment.source_journal).resolve()),
            "target_journal": str(Path(amendment.target_journal).resolve()),
            "source_journal_mutated": False,
        },
        "rollout_amendment": {
            "target_qids": list(amendment.target_qids),
            "base_max_raw_attempts_per_lineage": 5,
            "effective_max_raw_attempts_per_lineage": 7,
            "new_raw_slots_only": list(amendment.new_raw_slots_only),
            "all_other_frozen_parameters_unchanged": True,
        },
        "completion": {
            "accepted_count": len(artifacts),
            "target_completed_count": len(target_records),
            "target_records": target_records,
        },
        "new_qwen_rollouts": {
            "request_count": len(new_rows),
            "actual_generation_posts": sum(
                row.get("posting_at") is not None for row in new_rows
            ),
            "counts_by_qid": {str(qid): count for qid, count in counts_by_qid.items()},
            "request_keys": sorted(new_keys),
            "allowed_raw_slots": list(amendment.new_raw_slots_only),
            "historical_requests_reused": len(source_keys),
        },
        "new_judge_evidence": {
            "provider": "cli_proxy",
            "actual_judge_model": "gpt-5.5",
            "thinking_type": "enabled",
            "reasoning_effort": "xhigh",
            "fallback_allowed": False,
            "completed_record_count": len(relevant_judges),
            "actual_provider_calls": sum(
                int(record.get("provider_call_count") or 0)
                for record in relevant_judges
            ),
            "evidence_ids": sorted(
                str(record["evidence_id"]) for record in relevant_judges
            ),
        },
    }
