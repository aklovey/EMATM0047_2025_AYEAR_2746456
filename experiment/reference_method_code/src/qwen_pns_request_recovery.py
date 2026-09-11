from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


G1_GENERATION = "g1"
G1_EXPECTED_REQUEST_COUNT = 128
G1_MANIFEST_SCHEMA = "qwen_pns_request_recovery_manifest_v1"


class RecoveryContractError(RuntimeError):
    """The frozen recovery source or manifest violates its contract."""


class RecoveryAuthorizationError(RecoveryContractError):
    """A request or source journal is outside the frozen g1 authorization."""


class RecoveryIdentityDriftError(RecoveryContractError):
    """The live source identity differs from the frozen g1 manifest."""


class RecoveryInfrastructureError(RuntimeError):
    """A g1 recovery dispatch is terminally unavailable or indeterminate."""


@dataclass(frozen=True)
class G1RecoveryRequest:
    source_request_seq: int
    source_request_id: str
    source_request_key: str
    request_json: str
    seed: int
    prompt_key: str
    qid: int
    step_index: int
    branch: str
    rollout: int
    endpoint: str
    source_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_request_seq": self.source_request_seq,
            "source_request_id": self.source_request_id,
            "source_request_key": self.source_request_key,
            "request_json": self.request_json,
            "seed": self.seed,
            "prompt_key": self.prompt_key,
            "qid": self.qid,
            "step_index": self.step_index,
            "branch": self.branch,
            "rollout": self.rollout,
            "endpoint": self.endpoint,
            "source_state": self.source_state,
        }


@dataclass(frozen=True)
class G1RecoveryManifest:
    source_journal: str
    requests: tuple[G1RecoveryRequest, ...]
    generation: str = G1_GENERATION
    expected_request_count: int = G1_EXPECTED_REQUEST_COUNT
    schema_version: str = G1_MANIFEST_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generation": self.generation,
            "source_journal": self.source_journal,
            "expected_request_count": self.expected_request_count,
            "requests": [request.to_dict() for request in self.requests],
        }


@dataclass(frozen=True)
class RecoveryDispatchResult:
    http_status: int
    response: Mapping[str, Any]


@dataclass(frozen=True)
class RecoveredScientificAttempt:
    recovery_dispatch_id: str
    source_request_key: str
    qid: int
    step_index: int
    branch: str
    rollout: int
    response: dict[str, Any]
    cached: bool


RecoveryDispatch = Callable[[G1RecoveryRequest, str], RecoveryDispatchResult]


class QwenRequestRecovery:
    """One-generation sidecar recovery for an exact frozen request set."""

    def __init__(
        self,
        *,
        manifest: G1RecoveryManifest,
        sidecar_ledger: str | Path,
        dispatch: RecoveryDispatch,
        read_only_cache: bool = False,
    ) -> None:
        if manifest.generation != G1_GENERATION:
            raise RecoveryContractError("only the frozen g1 generation is supported")
        if len(manifest.requests) != manifest.expected_request_count:
            raise RecoveryContractError("g1 manifest request count is inconsistent")
        self.manifest = manifest
        self.dispatch = dispatch
        source_path = Path(manifest.source_journal)
        if not source_path.is_absolute():
            raise RecoveryAuthorizationError(
                "g1 source journal authorization must be an absolute path"
            )
        self._source_path = source_path.resolve()
        if str(self._source_path) != manifest.source_journal:
            raise RecoveryAuthorizationError(
                "g1 source journal differs from its authorized resolved path"
            )
        self._requests = {
            request.source_request_key: request for request in manifest.requests
        }
        if len(self._requests) != len(manifest.requests):
            raise RecoveryContractError("g1 manifest request keys must be unique")
        self.sidecar_path = Path(sidecar_ledger)
        self.read_only_cache = bool(read_only_cache)
        if self.read_only_cache:
            if not self.sidecar_path.is_file():
                raise RecoveryAuthorizationError(
                    f"read-only g1 sidecar is missing: {self.sidecar_path}"
                )
        else:
            self.sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._closed = False
        self._connection = (
            sqlite3.connect(
                f"file:{self.sidecar_path.resolve().as_posix()}?mode=ro",
                uri=True,
                check_same_thread=False,
            )
            if self.read_only_cache
            else sqlite3.connect(
                self.sidecar_path,
                check_same_thread=False,
            )
        )
        self._connection.row_factory = sqlite3.Row
        if self.read_only_cache:
            self._connection.execute("PRAGMA query_only=ON")
            try:
                self._connection.execute(
                    "SELECT 1 FROM recovery_dispatches LIMIT 1"
                ).fetchone()
                self._connection.execute(
                    "SELECT 1 FROM recovery_encodings LIMIT 1"
                ).fetchone()
            except sqlite3.Error as exc:
                self._connection.close()
                raise RecoveryContractError(
                    "read-only g1 sidecar schema is unavailable"
                ) from exc
            return
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_dispatches(
                dispatch_id TEXT PRIMARY KEY,
                generation TEXT NOT NULL CHECK(generation='g1'),
                source_request_key TEXT NOT NULL UNIQUE,
                source_identity_json TEXT NOT NULL,
                state TEXT NOT NULL CHECK(
                    state IN ('reserved','succeeded','failed_terminal','indeterminate')
                ),
                response_json TEXT,
                error_text TEXT
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_encodings(
                encoding_key TEXT PRIMARY KEY,
                qid INTEGER NOT NULL,
                purpose TEXT NOT NULL,
                source_key TEXT,
                text TEXT NOT NULL,
                tokenize_request_json TEXT NOT NULL,
                tokenize_response_json TEXT NOT NULL,
                token_count INTEGER NOT NULL,
                token_ids_json TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def verify_source(self) -> None:
        """Fail closed unless the live posting set is the frozen g1 set."""

        try:
            connection = sqlite3.connect(
                f"file:{self._source_path.as_posix()}?mode=ro",
                uri=True,
                timeout=5,
            )
        except sqlite3.Error as exc:
            raise RecoveryAuthorizationError(
                f"authorized g1 source journal is unavailable: {self._source_path}"
            ) from exc
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only=ON")
            rows = connection.execute(
                """
                SELECT request_seq,request_id,request_key,request_json,seed,
                       prompt_key,qid,step_index,branch,rollout,endpoint,state
                FROM requests
                WHERE state='posting'
                ORDER BY request_seq
                """
            ).fetchall()
        except sqlite3.Error as exc:
            raise RecoveryIdentityDriftError(
                "g1 source posting set cannot be verified"
            ) from exc
        finally:
            connection.close()
        try:
            current = tuple(_request_from_row(row) for row in rows)
        except RecoveryContractError as exc:
            raise RecoveryIdentityDriftError(
                "g1 source posting set differs from the frozen manifest"
            ) from exc
        if current != self.manifest.requests:
            raise RecoveryIdentityDriftError(
                "g1 source posting set differs from the frozen manifest"
            )

    def verify_cached_dispatches(self, *, qids: Sequence[int]) -> dict[str, Any]:
        """Prove selected frozen G1 rows are reusable without any dispatch."""

        if not self.read_only_cache:
            raise RecoveryAuthorizationError(
                "cached-dispatch preflight requires read-only g1 mode"
            )
        target_qids = sorted({int(qid) for qid in qids})
        expected = [
            request for request in self.manifest.requests if request.qid in target_qids
        ]
        missing: list[str] = []
        with self._lock:
            for request in expected:
                dispatch_id = f"recovery:{G1_GENERATION}:{request.source_request_key}"
                row = self._connection.execute(
                    "SELECT * FROM recovery_dispatches WHERE dispatch_id=?",
                    (dispatch_id,),
                ).fetchone()
                if row is None:
                    missing.append(request.source_request_key)
                    continue
                identity_ok = row["source_identity_json"] == _canonical_json(
                    request.to_dict()
                )
                try:
                    response = json.loads(row["response_json"] or "null")
                except json.JSONDecodeError:
                    response = None
                if not (
                    row["generation"] == G1_GENERATION
                    and row["source_request_key"] == request.source_request_key
                    and row["state"] == "succeeded"
                    and identity_ok
                    and isinstance(response, dict)
                    and response
                ):
                    missing.append(request.source_request_key)
        if missing:
            raise RecoveryAuthorizationError(
                "read-only g1 cache is incomplete for selected qids: "
                + ",".join(missing)
            )
        return {
            "read_only_cache": True,
            "target_qids": target_qids,
            "manifest_request_count": len(expected),
            "cached_succeeded_count": len(expected),
            "provider_dispatch_allowed": False,
        }

    def recover_for_task(self, task: Any) -> RecoveredScientificAttempt:
        """Recover only when the live task is exactly the frozen scientific slot."""

        request_key = str(getattr(task, "request_key", ""))
        request = self._requests.get(request_key)
        if request is None:
            raise RecoveryAuthorizationError(
                f"source request is not authorized by g1: {request_key}"
            )
        try:
            expected_body = json.loads(request.request_json)
        except json.JSONDecodeError as exc:  # already checked at manifest load/freeze
            raise RecoveryContractError(
                f"g1 manifest request_json is invalid for {request_key}"
            ) from exc
        runtime_body = getattr(task, "body", None)
        identity_matches = (
            isinstance(runtime_body, Mapping)
            and dict(runtime_body) == expected_body
            and getattr(task, "seed", None) == request.seed
            and getattr(task, "prompt_key", None) == request.prompt_key
            and getattr(task, "qid", None) == request.qid
            and getattr(task, "step", None) == request.step_index
            and getattr(task, "branch", None) == request.branch
            and getattr(task, "rollout", None) == request.rollout
            and getattr(task, "endpoint", None) == request.endpoint
        )
        if not identity_matches:
            raise RecoveryIdentityDriftError(
                f"g1 runtime task identity differs for {request_key}"
            )
        return self.recover(request_key)

    def get_encoding(self, encoding_key: str) -> dict[str, Any] | None:
        """Read a recovered-chain encoding from the sidecar cache."""

        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM recovery_encodings WHERE encoding_key=?",
                (str(encoding_key),),
            ).fetchone()
        return None if row is None else dict(row)

    def store_encoding(
        self,
        *,
        encoding_key: str,
        qid: int,
        purpose: str,
        source_key: str | None,
        text: str,
        request_body: Mapping[str, Any],
        response: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Cache tokenization for a recovered chain without touching source rows."""

        tokens = response.get("tokens")
        if (
            not isinstance(tokens, list)
            or not all(type(token) is int for token in tokens)
            or response.get("count") != len(tokens)
        ):
            raise RecoveryContractError(
                "invalid recovered-chain tokenization response"
            )
        values = (
            str(encoding_key),
            int(qid),
            str(purpose),
            None if source_key is None else str(source_key),
            str(text),
            _canonical_json(request_body),
            _canonical_json(response),
            len(tokens),
            json.dumps(tokens, separators=(",", ":")),
        )
        with self._lock:
            if self.read_only_cache:
                row = self._connection.execute(
                    "SELECT * FROM recovery_encodings WHERE encoding_key=?",
                    (str(encoding_key),),
                ).fetchone()
                if row is None:
                    raise RecoveryAuthorizationError(
                        f"read-only g1 encoding cache miss: {encoding_key}"
                    )
            else:
                try:
                    with self._connection:
                        self._connection.execute(
                            """
                            INSERT INTO recovery_encodings(
                                encoding_key,qid,purpose,source_key,text,
                                tokenize_request_json,tokenize_response_json,
                                token_count,token_ids_json
                            ) VALUES(?,?,?,?,?,?,?,?,?)
                            """,
                            values,
                        )
                except sqlite3.IntegrityError:
                    pass
                row = self._connection.execute(
                    "SELECT * FROM recovery_encodings WHERE encoding_key=?",
                    (str(encoding_key),),
                ).fetchone()
        if row is None:
            raise RecoveryContractError(
                f"recovery encoding cache row disappeared: {encoding_key}"
            )
        result = dict(row)
        expected = {
            "encoding_key": values[0],
            "qid": values[1],
            "purpose": values[2],
            "source_key": values[3],
            "text": values[4],
            "tokenize_request_json": values[5],
            "tokenize_response_json": values[6],
            "token_count": values[7],
            "token_ids_json": values[8],
        }
        if result != expected:
            raise RecoveryIdentityDriftError(
                f"recovery encoding identity differs for {encoding_key}"
            )
        return result

    def recover(self, source_request_key: str) -> RecoveredScientificAttempt:
        request = self._requests.get(str(source_request_key))
        if request is None:
            raise RecoveryAuthorizationError(
                f"source request is not authorized by g1: {source_request_key}"
            )
        self._verify_source_identity(request)
        dispatch_id = f"recovery:{G1_GENERATION}:{request.source_request_key}"
        identity_json = _canonical_json(request.to_dict())
        prior = self._reserve_or_reuse(
            dispatch_id=dispatch_id,
            request=request,
            identity_json=identity_json,
        )
        if prior is not None:
            return _map_recovered_attempt(
                request,
                dispatch_id=dispatch_id,
                response=prior,
                cached=True,
            )

        try:
            result = self.dispatch(request, dispatch_id)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self._store_terminal(dispatch_id, state="indeterminate", error=error)
            raise RecoveryInfrastructureError(
                f"g1 dispatch {dispatch_id} is indeterminate; no-resend"
            ) from exc
        if not isinstance(result, RecoveryDispatchResult):
            self._store_terminal(
                dispatch_id,
                state="indeterminate",
                error="dispatch_return_type_indeterminate",
            )
            raise RecoveryInfrastructureError(
                f"g1 dispatch {dispatch_id} is indeterminate; no-resend"
            )
        if not 200 <= result.http_status < 300:
            self._store_terminal(
                dispatch_id,
                state="failed_terminal",
                error=f"http_status_{result.http_status}",
            )
            raise RecoveryInfrastructureError(
                f"g1 dispatch {dispatch_id} failed_terminal at HTTP "
                f"{result.http_status}; no g2"
            )
        response = dict(result.response)
        if not response:
            self._store_terminal(
                dispatch_id,
                state="failed_terminal",
                error="empty_response",
            )
            raise RecoveryInfrastructureError(
                f"g1 dispatch {dispatch_id} failed_terminal with empty response; "
                "no g2"
            )
        self._store_success(dispatch_id, response)
        return _map_recovered_attempt(
            request,
            dispatch_id=dispatch_id,
            response=response,
            cached=False,
        )

    def _reserve_or_reuse(
        self,
        *,
        dispatch_id: str,
        request: G1RecoveryRequest,
        identity_json: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM recovery_dispatches WHERE dispatch_id=?",
                (dispatch_id,),
            ).fetchone()
            if row is None:
                if self.read_only_cache:
                    raise RecoveryAuthorizationError(
                        f"read-only g1 dispatch cache miss: {dispatch_id}"
                    )
                self._connection.execute(
                    """
                    INSERT INTO recovery_dispatches(
                        dispatch_id,generation,source_request_key,
                        source_identity_json,state
                    ) VALUES(?,'g1',?,?,'reserved')
                    """,
                    (dispatch_id, request.source_request_key, identity_json),
                )
                self._connection.commit()
                return None
            if (
                row["source_request_key"] != request.source_request_key
                or row["source_identity_json"] != identity_json
            ):
                raise RecoveryIdentityDriftError(
                    f"g1 sidecar identity differs for {dispatch_id}"
                )
            if row["state"] != "succeeded":
                raise RecoveryInfrastructureError(
                    f"g1 dispatch {dispatch_id} is {row['state']}; no-resend/no g2"
                )
            response = json.loads(row["response_json"] or "null")
            if not isinstance(response, dict) or not response:
                raise RecoveryContractError(
                    f"g1 cached response is invalid for {dispatch_id}"
                )
            return response

    def _verify_source_identity(self, expected: G1RecoveryRequest) -> None:
        try:
            connection = sqlite3.connect(
                f"file:{self._source_path.as_posix()}?mode=ro",
                uri=True,
                timeout=5,
            )
        except sqlite3.Error as exc:
            raise RecoveryAuthorizationError(
                f"authorized g1 source journal is unavailable: {self._source_path}"
            ) from exc
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only=ON")
            row = connection.execute(
                """
                SELECT request_seq,request_id,request_key,request_json,seed,
                       prompt_key,qid,step_index,branch,rollout,endpoint,state
                FROM requests
                WHERE request_key=?
                """,
                (expected.source_request_key,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise RecoveryIdentityDriftError(
                f"g1 source identity drift for {expected.source_request_key}"
            ) from exc
        finally:
            connection.close()
        if row is None:
            raise RecoveryIdentityDriftError(
                f"g1 source identity drift for {expected.source_request_key}: missing"
            )
        try:
            current = _request_from_row(row)
        except RecoveryContractError as exc:
            raise RecoveryIdentityDriftError(
                f"g1 source identity drift for {expected.source_request_key}"
            ) from exc
        if current != expected:
            raise RecoveryIdentityDriftError(
                f"g1 source identity drift for {expected.source_request_key}"
            )

    def _store_success(self, dispatch_id: str, response: dict[str, Any]) -> None:
        if self.read_only_cache:
            raise RecoveryAuthorizationError("read-only g1 sidecar cannot store success")
        with self._lock, self._connection:
            changed = self._connection.execute(
                """
                UPDATE recovery_dispatches
                SET state='succeeded',response_json=?
                WHERE dispatch_id=? AND state='reserved'
                """,
                (_canonical_json(response), dispatch_id),
            ).rowcount
        if changed != 1:
            raise RecoveryContractError(
                f"g1 dispatch cannot store success for {dispatch_id}"
            )

    def _store_terminal(self, dispatch_id: str, *, state: str, error: str) -> None:
        if self.read_only_cache:
            raise RecoveryAuthorizationError(
                "read-only g1 sidecar cannot store terminal state"
            )
        if state not in {"failed_terminal", "indeterminate"}:
            raise ValueError(f"unsupported g1 terminal state: {state}")
        with self._lock, self._connection:
            changed = self._connection.execute(
                """
                UPDATE recovery_dispatches
                SET state=?,error_text=?
                WHERE dispatch_id=? AND state='reserved'
                """,
                (state, error, dispatch_id),
            ).rowcount
        if changed != 1:
            raise RecoveryContractError(
                f"g1 dispatch cannot store {state} for {dispatch_id}"
            )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._connection.close()


def freeze_g1_manifest(
    source_journal: str | Path,
    target: str | Path,
    *,
    expected_request_count: int = G1_EXPECTED_REQUEST_COUNT,
) -> G1RecoveryManifest:
    """Freeze the exact g1 posting set without writing to the source journal."""

    if expected_request_count != G1_EXPECTED_REQUEST_COUNT:
        raise RecoveryContractError("g1 recovery is frozen to exactly 128 requests")
    source = Path(source_journal).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    connection = sqlite3.connect(
        f"file:{source.as_posix()}?mode=ro",
        uri=True,
        timeout=5,
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            """
            SELECT request_seq,request_id,request_key,request_json,seed,
                   prompt_key,qid,step_index,branch,rollout,endpoint,state
            FROM requests
            WHERE state='posting'
            ORDER BY request_seq
            """
        ).fetchall()
    finally:
        connection.close()
    if len(rows) != expected_request_count:
        raise RecoveryContractError(
            "g1 source must contain exactly "
            f"{expected_request_count} posting requests, found {len(rows)}"
        )
    requests = tuple(_request_from_row(row) for row in rows)
    keys = [request.source_request_key for request in requests]
    if len(keys) != len(set(keys)):
        raise RecoveryContractError("g1 source request keys must be unique")
    manifest = G1RecoveryManifest(
        source_journal=str(source),
        requests=requests,
    )
    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(
            manifest.to_dict(),
            handle,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        handle.write("\n")
    return manifest


def load_g1_manifest(path: str | Path) -> G1RecoveryManifest:
    """Load and strictly validate a previously frozen g1 manifest."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryContractError(f"g1 manifest is unreadable: {source}") from exc
    if not isinstance(payload, dict):
        raise RecoveryContractError("g1 manifest must be a JSON object")
    if payload.get("schema_version") != G1_MANIFEST_SCHEMA:
        raise RecoveryContractError("g1 manifest schema_version is invalid")
    if payload.get("generation") != G1_GENERATION:
        raise RecoveryContractError("g1 manifest generation is invalid")
    if payload.get("expected_request_count") != G1_EXPECTED_REQUEST_COUNT:
        raise RecoveryContractError("g1 manifest must authorize exactly 128 requests")
    raw_source_journal = payload.get("source_journal")
    raw_requests = payload.get("requests")
    if not isinstance(raw_source_journal, str) or not raw_source_journal.strip():
        raise RecoveryContractError("g1 manifest source_journal is invalid")
    if not isinstance(raw_requests, list) or len(raw_requests) != 128:
        raise RecoveryContractError("g1 manifest requests must contain exactly 128 rows")
    requests = tuple(_request_from_payload(value) for value in raw_requests)
    keys = [request.source_request_key for request in requests]
    sequences = [request.source_request_seq for request in requests]
    if len(keys) != len(set(keys)):
        raise RecoveryContractError("g1 manifest request keys must be unique")
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        raise RecoveryContractError(
            "g1 manifest request sequences must be unique and ordered"
        )
    manifest = G1RecoveryManifest(
        source_journal=raw_source_journal,
        requests=requests,
    )
    if manifest.to_dict() != payload:
        raise RecoveryContractError("g1 manifest contains unexpected identity fields")
    return manifest


def _request_from_row(row: sqlite3.Row) -> G1RecoveryRequest:
    request_json = str(row["request_json"])
    try:
        request_body = json.loads(request_json)
    except json.JSONDecodeError as exc:
        raise RecoveryContractError(
            f"source request {row['request_key']} has invalid request_json"
        ) from exc
    if not isinstance(request_body, dict):
        raise RecoveryContractError(
            f"source request {row['request_key']} request_json must be an object"
        )
    state = str(row["state"])
    if state != "posting":
        raise RecoveryContractError(
            f"source request {row['request_key']} is not posting"
        )
    return G1RecoveryRequest(
        source_request_seq=int(row["request_seq"]),
        source_request_id=str(row["request_id"]),
        source_request_key=str(row["request_key"]),
        request_json=request_json,
        seed=int(row["seed"]),
        prompt_key=str(row["prompt_key"]),
        qid=int(row["qid"]),
        step_index=int(row["step_index"]),
        branch=str(row["branch"]),
        rollout=int(row["rollout"]),
        endpoint=str(row["endpoint"]),
        source_state=state,
    )


def _request_from_payload(value: Any) -> G1RecoveryRequest:
    if not isinstance(value, dict):
        raise RecoveryContractError("g1 manifest request must be an object")
    fields = {
        "source_request_seq",
        "source_request_id",
        "source_request_key",
        "request_json",
        "seed",
        "prompt_key",
        "qid",
        "step_index",
        "branch",
        "rollout",
        "endpoint",
        "source_state",
    }
    if set(value) != fields:
        raise RecoveryContractError("g1 manifest request identity fields differ")
    integer_fields = (
        "source_request_seq",
        "seed",
        "qid",
        "step_index",
        "rollout",
    )
    string_fields = tuple(fields - set(integer_fields))
    if any(type(value[field]) is not int for field in integer_fields):
        raise RecoveryContractError("g1 manifest request integer identity is invalid")
    if any(not isinstance(value[field], str) for field in string_fields):
        raise RecoveryContractError("g1 manifest request string identity is invalid")
    try:
        request_body = json.loads(value["request_json"])
    except json.JSONDecodeError as exc:
        raise RecoveryContractError("g1 manifest request_json is invalid") from exc
    if not isinstance(request_body, dict) or value["source_state"] != "posting":
        raise RecoveryContractError("g1 manifest request is not a frozen posting")
    return G1RecoveryRequest(**value)


def _map_recovered_attempt(
    request: G1RecoveryRequest,
    *,
    dispatch_id: str,
    response: dict[str, Any],
    cached: bool,
) -> RecoveredScientificAttempt:
    return RecoveredScientificAttempt(
        recovery_dispatch_id=dispatch_id,
        source_request_key=request.source_request_key,
        qid=request.qid,
        step_index=request.step_index,
        branch=request.branch,
        rollout=request.rollout,
        response=dict(response),
        cached=cached,
    )


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
