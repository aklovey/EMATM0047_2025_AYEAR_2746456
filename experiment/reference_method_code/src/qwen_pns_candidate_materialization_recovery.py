from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Sequence

import yaml

from .datasets.adapters.cladder import CladderAdapter
from .pns_judge_ledger import IndeterminateJudgeDispatchError
from .qwen_pns_adaptive import (
    AdaptiveRolloutConfig,
    POLICY_VERSION,
    QwenPnsCotParent,
    ReplacementGeneration,
    RolloutTrial,
    _require_accepted_judge_profile,
    _step_summary,
    _validate_pnscot_artifact,
    generate_optimized_pnscot,
    replacement_generation_from_qwen_journal_row,
    trial_from_qwen_journal_row,
)
from .qwen_pns_request_recovery import load_g1_manifest


RECOVERY_SCHEMA = "qwen_pns_existing_candidate_materialization_recovery_v1"
MANIFEST_SCHEMA = "qwen_pns_existing_candidate_order_manifest_v1"
REPORT_SCHEMA = "qwen_pns_existing_candidate_materialization_report_v1"
BATCH_RECOVERY_SCHEMA = (
    "qwen_pns_existing_candidate_materialization_batch_recovery_v1"
)
BATCH_MANIFEST_SCHEMA = "qwen_pns_existing_candidate_batch_manifest_v1"
BATCH_REPORT_SCHEMA = "qwen_pns_existing_candidate_batch_report_v1"
WORKSPACE_CONTRACT_SCHEMA = "recovery_workspace_contract_v1"
RESULT_TYPE = "qwen_pns_batch56_adapter_v2_qwen_source_segments"

_SAFE_JUDGE_FIELDS = (
    "provider",
    "endpoint_type",
    "transport",
    "base_url",
    "requested_model",
    "resolved_model",
    "response_model",
    "actual_judge_model",
    "thinking_type",
    "reasoning_effort",
    "json_schema_strict",
    "stream",
    "store",
    "protocol_revision",
    "scope",
    "switch_reason",
    "scientific_raw_attempt_delta",
    "app_max_retries",
    "default_pass_allowed",
    "status",
    "parse_status",
    "decision",
    "accepted",
    "provider_call_count",
    "retry_count",
    "fallback_allowed",
    "fallback_used",
    "recovery_generation",
    "recovery_provenance",
    "source_evidence_id",
    "effective_evidence_id",
    "source_state",
    "normalization_provenance",
    "usage",
    "latency_ms",
    "verdict",
    "error",
)


@dataclass(frozen=True)
class ExistingCandidateRecoveryConfig:
    contract_id: str
    target_qid: int
    input_manifest: Path
    journal: Path
    future_judge_resume_config: Path
    candidate_manifest: Path
    terminal_report: Path
    output_artifact: Path
    first_accepted_gate: Path
    first_future_accepted_gate: Path
    expected_completed_items: int = 56
    qwen_recovery_manifest: Path | None = None
    qwen_recovery_sidecar: Path | None = None
    replay_source_journal: Path | None = None
    recovery_workspace_contract: Path | None = None

    def validate(self) -> None:
        if not self.contract_id.strip():
            raise ValueError("candidate recovery contract_id is required")
        if self.target_qid < 1:
            raise ValueError("candidate recovery target_qid must be positive")
        if self.expected_completed_items != 56:
            raise ValueError("candidate recovery must retain the exact 56-item target")
        if self.candidate_manifest == self.terminal_report:
            raise ValueError("candidate manifest and terminal report must differ")
        if (self.qwen_recovery_manifest is None) != (
            self.qwen_recovery_sidecar is None
        ):
            raise ValueError(
                "Qwen g1 recovery manifest and sidecar must be configured together"
            )
        if (self.replay_source_journal is None) != (
            self.recovery_workspace_contract is None
        ):
            raise ValueError(
                "copied-journal replay source and workspace contract must be configured together"
            )
        if self.replay_source_journal is not None and (
            self.replay_source_journal == self.journal
        ):
            raise ValueError("copied-journal replay source must differ from target")


@dataclass(frozen=True)
class ExistingCandidateRecoveryBatchConfig:
    contract_id: str
    target_qids: tuple[int, ...]
    max7_qids: tuple[int, ...]
    input_manifest: Path
    source_journal: Path
    source_future_judge_ledger: Path
    future_judge_resume_config: Path
    qwen_recovery_manifest: Path
    qwen_recovery_sidecar: Path
    recovery_root: Path
    journal: Path
    future_judge_ledger: Path
    candidate_root: Path
    workspace_contract_artifact: Path
    batch_manifest: Path
    terminal_report: Path
    output_artifact: Path
    first_accepted_gate: Path
    first_future_accepted_gate: Path
    expected_completed_items: int = 56
    expected_initial_completed: int = 35
    expected_initial_pending: int = 21
    expected_completed_after_review: int = 53

    def validate(self) -> None:
        if not self.contract_id.strip():
            raise ValueError("batch candidate recovery contract_id is required")
        if len(self.target_qids) != 18 or len(set(self.target_qids)) != 18:
            raise ValueError("batch candidate recovery requires 18 unique review qids")
        if len(self.max7_qids) != 3 or len(set(self.max7_qids)) != 3:
            raise ValueError("batch candidate recovery requires 3 unique max7 qids")
        if set(self.target_qids) & set(self.max7_qids):
            raise ValueError("review18 and max7 qids must be disjoint")
        if any(type(qid) is not int or qid < 1 for qid in (*self.target_qids, *self.max7_qids)):
            raise ValueError("batch candidate recovery qids must be positive integers")
        if self.expected_completed_items != 56:
            raise ValueError("batch candidate recovery must retain the exact 56-item target")
        if (self.expected_initial_completed, self.expected_initial_pending) != (35, 21):
            raise ValueError("batch candidate recovery requires the frozen 35/21 source state")
        if self.expected_completed_after_review != 53:
            raise ValueError("batch candidate recovery must gate max7 at 53 completed")
        if self.source_journal == self.journal:
            raise ValueError("recovery journal must differ from the source journal")
        if self.source_future_judge_ledger == self.future_judge_ledger:
            raise ValueError("recovery future Judge ledger must differ from its source")
        for label, path in {
            "journal": self.journal,
            "future_judge_ledger": self.future_judge_ledger,
            "candidate_root": self.candidate_root,
            "workspace_contract_artifact": self.workspace_contract_artifact,
            "batch_manifest": self.batch_manifest,
            "terminal_report": self.terminal_report,
            "output_artifact": self.output_artifact,
            "first_accepted_gate": self.first_accepted_gate,
            "first_future_accepted_gate": self.first_future_accepted_gate,
        }.items():
            if not path.is_relative_to(self.recovery_root):
                raise ValueError(f"batch recovery {label} must stay under recovery_root")
        if len(
            {
                self.workspace_contract_artifact,
                self.batch_manifest,
                self.terminal_report,
                self.output_artifact,
            }
        ) != 4:
            raise ValueError("batch recovery artifacts must use distinct paths")

    @property
    def exact_initial_pending_qids(self) -> tuple[int, ...]:
        return tuple(sorted((*self.target_qids, *self.max7_qids)))

    def item_config(self, qid: int) -> ExistingCandidateRecoveryConfig:
        if qid not in self.target_qids:
            raise ValueError(f"q{qid} is outside the frozen review18 scope")
        item_root = self.candidate_root / f"q{qid}"
        config = ExistingCandidateRecoveryConfig(
            contract_id=f"{self.contract_id}:q{qid}",
            target_qid=qid,
            input_manifest=self.input_manifest,
            journal=self.journal,
            future_judge_resume_config=self.future_judge_resume_config,
            candidate_manifest=item_root / "candidate_manifest.json",
            terminal_report=item_root / "terminal_report.json",
            output_artifact=self.output_artifact,
            first_accepted_gate=self.first_accepted_gate,
            first_future_accepted_gate=self.first_future_accepted_gate,
            expected_completed_items=self.expected_completed_items,
            qwen_recovery_manifest=self.qwen_recovery_manifest,
            qwen_recovery_sidecar=self.qwen_recovery_sidecar,
            replay_source_journal=self.source_journal,
            recovery_workspace_contract=self.workspace_contract_artifact,
        )
        config.validate()
        return config


@dataclass(frozen=True)
class ExistingCandidate:
    qid: int
    rank: int
    request_seq: int
    request_key: str
    candidate_id: str
    step_index: int
    branch: str
    rollout: int
    chain_token_count: int
    chain_char_count: int
    complete_chain: str
    parsed_answer: str
    audit: dict[str, Any]
    chain_judge: dict[str, Any]
    chain_evidence_id: str

    @property
    def materialization_evidence_id(self) -> str:
        return f"materialization:q{self.qid}:{self.request_key}"


@dataclass(frozen=True)
class _OfflineReplay:
    item: dict[str, Any]
    parent_tokens: int
    candidates: tuple[ExistingCandidate, ...]
    rollout_trace: dict[str, Any]


def load_existing_candidate_recovery_config(
    path: str | Path,
    *,
    project_root: str | Path,
) -> ExistingCandidateRecoveryConfig | ExistingCandidateRecoveryBatchConfig:
    source = Path(path).resolve()
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("schema_version") == (
        BATCH_RECOVERY_SCHEMA
    ):
        return _load_existing_candidate_batch_recovery_payload(
            payload,
            project_root=project_root,
        )
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != RECOVERY_SCHEMA
    ):
        raise ValueError("existing-candidate recovery config schema differs")
    if payload.get("status") != "frozen_user_authorized":
        raise ValueError("existing-candidate recovery config is not executable")
    authorization = payload.get("authorization")
    source_paths = payload.get("source")
    invariants = payload.get("invariants")
    artifacts = payload.get("artifacts")
    if not all(
        isinstance(value, dict)
        for value in (authorization, source_paths, invariants, artifacts)
    ):
        raise ValueError("existing-candidate recovery config sections are invalid")
    expected_invariants = {
        "candidate_source": "existing_durable_journal_and_g1_recovery_only",
        "candidate_chain_judge_source": "completed_evidence_only",
        "reserved_chain_evidence_policy": "exclude_no_resend",
        "candidate_order": ["chain_token_count", "chain_char_count", "candidate_id"],
        "new_qwen_rollouts_allowed": False,
        "qwen_tokenizer_required": False,
        "qwen_base_url_required": False,
        "strictly_shorter_than_parent": True,
        "deterministic_answer_validation": "required",
        "materialization_judge": "required_fail_closed",
        "reorder_after_judge_result_allowed": False,
        "replace_sample_allowed": False,
    }
    for key, expected in expected_invariants.items():
        if invariants.get(key) != expected:
            raise ValueError(f"existing-candidate recovery invariant differs: {key}")
    if (
        authorization.get("instruction")
        != "review_q4171_existing_candidates_sequentially"
    ):
        raise ValueError("existing-candidate recovery authorization differs")
    root = Path(project_root).resolve()

    def resolve(value: Any) -> Path:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError("existing-candidate recovery path is missing")
        candidate = Path(raw)
        return (candidate if candidate.is_absolute() else root / candidate).resolve()

    config = ExistingCandidateRecoveryConfig(
        contract_id=str(payload.get("contract_id") or ""),
        target_qid=int(authorization.get("target_qid")),
        input_manifest=resolve(source_paths.get("input_manifest")),
        journal=resolve(source_paths.get("journal")),
        future_judge_resume_config=resolve(
            source_paths.get("future_judge_resume_config")
        ),
        candidate_manifest=resolve(artifacts.get("candidate_manifest")),
        terminal_report=resolve(artifacts.get("terminal_report")),
        output_artifact=resolve(artifacts.get("output_artifact")),
        first_accepted_gate=resolve(artifacts.get("first_accepted_gate")),
        first_future_accepted_gate=resolve(artifacts.get("first_future_accepted_gate")),
        expected_completed_items=int(payload.get("expected_completed_items", 56)),
        qwen_recovery_manifest=resolve(source_paths.get("qwen_recovery_manifest")),
        qwen_recovery_sidecar=resolve(source_paths.get("qwen_recovery_sidecar")),
    )
    config.validate()
    return config


def load_existing_candidate_batch_recovery_config(
    path: str | Path,
    *,
    project_root: str | Path,
) -> ExistingCandidateRecoveryBatchConfig:
    config = load_existing_candidate_recovery_config(
        path,
        project_root=project_root,
    )
    if not isinstance(config, ExistingCandidateRecoveryBatchConfig):
        raise ValueError("existing-candidate recovery config is not a batch contract")
    return config


def _load_existing_candidate_batch_recovery_payload(
    payload: dict[str, Any],
    *,
    project_root: str | Path,
) -> ExistingCandidateRecoveryBatchConfig:
    if payload.get("status") != "frozen_user_authorized":
        raise ValueError("batch candidate recovery config is not executable")
    authorization = payload.get("authorization")
    source_paths = payload.get("source")
    invariants = payload.get("invariants")
    artifacts = payload.get("artifacts")
    if not all(
        isinstance(value, dict)
        for value in (authorization, source_paths, invariants, artifacts)
    ):
        raise ValueError("batch candidate recovery config sections are invalid")
    expected_invariants = {
        "candidate_source": "existing_durable_journal_and_g1_recovery_only",
        "candidate_chain_judge_source": "completed_evidence_only",
        "reserved_chain_evidence_policy": "exclude_no_resend",
        "candidate_order": ["chain_token_count", "chain_char_count", "candidate_id"],
        "new_qwen_rollouts_allowed": False,
        "qwen_tokenizer_required": False,
        "qwen_base_url_required": False,
        "strictly_shorter_than_parent": True,
        "deterministic_answer_validation": "required",
        "materialization_judge": "required_fail_closed",
        "materialization_judge_provider": "cli_proxy",
        "materialization_judge_model": "gpt-5.5",
        "materialization_judge_reasoning_effort": "xhigh",
        "reorder_after_judge_result_allowed": False,
        "replace_sample_allowed": False,
        "review_order": "authorization_target_qids",
        "journal_copy_method": "sqlite_backup",
        "source_journal_mutation_allowed": False,
        "source_future_judge_ledger_mutation_allowed": False,
        "max7_logic_in_review18_allowed": False,
    }
    for key, expected in expected_invariants.items():
        if invariants.get(key) != expected:
            raise ValueError(f"batch candidate recovery invariant differs: {key}")
    if authorization.get("instruction") != (
        "review_exact_18_existing_candidates_sequentially"
    ):
        raise ValueError("batch candidate recovery authorization differs")
    if authorization.get("scope") != "existing_generated_candidates_only":
        raise ValueError("batch candidate recovery scope differs")

    def qid_tuple(value: Any, *, label: str) -> tuple[int, ...]:
        if not isinstance(value, list) or any(type(qid) is not int for qid in value):
            raise ValueError(f"batch candidate recovery {label} must be an integer list")
        return tuple(value)

    root = Path(project_root).resolve()

    def resolve(value: Any) -> Path:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError("batch candidate recovery path is missing")
        candidate = Path(raw)
        return (candidate if candidate.is_absolute() else root / candidate).resolve()

    config = ExistingCandidateRecoveryBatchConfig(
        contract_id=str(payload.get("contract_id") or ""),
        target_qids=qid_tuple(
            authorization.get("target_qids"),
            label="target_qids",
        ),
        max7_qids=qid_tuple(
            authorization.get("max7_qids"),
            label="max7_qids",
        ),
        input_manifest=resolve(source_paths.get("input_manifest")),
        source_journal=resolve(source_paths.get("journal")),
        source_future_judge_ledger=resolve(
            source_paths.get("future_judge_ledger")
        ),
        future_judge_resume_config=resolve(
            source_paths.get("future_judge_resume_config")
        ),
        qwen_recovery_manifest=resolve(source_paths.get("qwen_recovery_manifest")),
        qwen_recovery_sidecar=resolve(source_paths.get("qwen_recovery_sidecar")),
        recovery_root=resolve(artifacts.get("recovery_root")),
        journal=resolve(artifacts.get("journal")),
        future_judge_ledger=resolve(artifacts.get("future_judge_ledger")),
        candidate_root=resolve(artifacts.get("candidate_root")),
        workspace_contract_artifact=resolve(
            artifacts.get("workspace_contract")
        ),
        batch_manifest=resolve(artifacts.get("batch_manifest")),
        terminal_report=resolve(artifacts.get("terminal_report")),
        output_artifact=resolve(artifacts.get("output_artifact")),
        first_accepted_gate=resolve(artifacts.get("first_accepted_gate")),
        first_future_accepted_gate=resolve(
            artifacts.get("first_future_accepted_gate")
        ),
        expected_completed_items=int(payload.get("expected_completed_items", 56)),
        expected_initial_completed=int(
            invariants.get("source_initial_completed_count", -1)
        ),
        expected_initial_pending=int(
            invariants.get("source_initial_pending_count", -1)
        ),
        expected_completed_after_review=int(
            invariants.get("target_completed_after_review18", -1)
        ),
    )
    config.validate()
    return config


def _sqlite_safe_stats(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro",
        uri=True,
    )
    try:
        return _sqlite_safe_stats_from_connection(connection, resolved)
    finally:
        connection.close()


def _sqlite_safe_stats_from_connection(
    connection: sqlite3.Connection,
    path: Path,
) -> dict[str, Any]:
    integrity = str(connection.execute("PRAGMA integrity_check(1)").fetchone()[0])
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity check failed for {path}: {integrity}")
    tables = [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]
    row_counts: dict[str, int] = {}
    for table in tables:
        quoted = table.replace('"', '""')
        row_counts[table] = int(
            connection.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
        )
    item_state_counts: dict[str, int] = {}
    pending_qids: list[int] = []
    if "items" in tables:
        item_state_counts = {
            str(state): int(count)
            for state, count in connection.execute(
                "SELECT state,COUNT(*) FROM items GROUP BY state ORDER BY state"
            ).fetchall()
        }
        pending_qids = [
            int(row[0])
            for row in connection.execute(
                "SELECT qid FROM items WHERE state!='completed' ORDER BY qid"
            ).fetchall()
        ]
    judge_state_counts: dict[str, int] = {}
    if "judge_evidence" in tables:
        judge_state_counts = {
            str(state): int(count)
            for state, count in connection.execute(
                "SELECT state,COUNT(*) FROM judge_evidence GROUP BY state ORDER BY state"
            ).fetchall()
        }
    stat = path.stat()
    wal = Path(f"{path}-wal")
    return {
        "path": str(path),
        "file_bytes": int(stat.st_size),
        "file_mtime_ns": int(stat.st_mtime_ns),
        "wal_bytes": int(wal.stat().st_size) if wal.is_file() else 0,
        "integrity_check": integrity,
        "page_size": int(connection.execute("PRAGMA page_size").fetchone()[0]),
        "page_count": int(connection.execute("PRAGMA page_count").fetchone()[0]),
        "freelist_count": int(
            connection.execute("PRAGMA freelist_count").fetchone()[0]
        ),
        "tables": tables,
        "table_row_counts": row_counts,
        "item_state_counts": item_state_counts,
        "pending_qids": pending_qids,
        "judge_state_counts": judge_state_counts,
    }


def _sqlite_logical_stats(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        key: stats[key]
        for key in (
            "integrity_check",
            "tables",
            "table_row_counts",
            "item_state_counts",
            "pending_qids",
            "judge_state_counts",
        )
    }


def _stats_with_path(stats: dict[str, Any], path: Path) -> dict[str, Any]:
    return {**stats, "path": str(path.resolve())}


def _backup_sqlite_database(
    source_path: Path,
    target_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = source_path.resolve()
    target = target_path.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if target.exists():
        raise RuntimeError(f"refusing to overwrite recovery SQLite copy: {target}")
    source_wal = Path(f"{source}-wal")
    if source_wal.is_file() and source_wal.stat().st_size != 0:
        raise RuntimeError(f"source SQLite WAL is nonempty; writer may be active: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(
        f"file:{source.as_posix()}?mode=ro",
        uri=True,
    )
    target_connection: sqlite3.Connection | None = None
    try:
        data_version_before = int(
            source_connection.execute("PRAGMA data_version").fetchone()[0]
        )
        source_before = _sqlite_safe_stats_from_connection(
            source_connection,
            source,
        )
        target_connection = sqlite3.connect(target)
        source_connection.backup(target_connection)
        target_connection.commit()
        target_connection.close()
        target_connection = None
        data_version_after = int(
            source_connection.execute("PRAGMA data_version").fetchone()[0]
        )
        source_after = _sqlite_safe_stats_from_connection(
            source_connection,
            source,
        )
    finally:
        if target_connection is not None:
            target_connection.close()
        source_connection.close()
    if data_version_before != data_version_after or source_before != source_after:
        raise RuntimeError(f"source SQLite changed during backup: {source}")
    if source_after["wal_bytes"] != 0:
        raise RuntimeError(f"source SQLite WAL changed during backup: {source}")
    target_stats = _sqlite_safe_stats(target)
    if _sqlite_logical_stats(source_before) != _sqlite_logical_stats(target_stats):
        raise RuntimeError(f"SQLite backup logical metadata differs: {source}")
    return source_before, target_stats


def _require_initial_partition(
    config: ExistingCandidateRecoveryBatchConfig,
    journal_stats: dict[str, Any],
) -> None:
    expected_states = {
        "completed": config.expected_initial_completed,
        "pending": config.expected_initial_pending,
    }
    if journal_stats.get("item_state_counts") != expected_states:
        raise RuntimeError(
            "source journal must be the frozen 35 completed / 21 pending snapshot"
        )
    if journal_stats.get("pending_qids") != list(config.exact_initial_pending_qids):
        raise RuntimeError("source journal pending qids differ from review18 + max7")
    if journal_stats.get("table_row_counts", {}).get("items") != (
        config.expected_completed_items
    ):
        raise RuntimeError("source journal must contain exactly 56 items")


def initialize_existing_candidate_recovery_workspace(
    config: ExistingCandidateRecoveryBatchConfig,
) -> dict[str, Any]:
    """Atomically clone the two writable SQLite assets without touching sources."""

    config.validate()
    if config.recovery_root.exists():
        return validate_existing_candidate_recovery_workspace(config)
    staging_root = config.recovery_root.with_name(
        f"{config.recovery_root.name}.preparing"
    )
    if staging_root.exists():
        raise RuntimeError(
            f"stale recovery staging root requires manual inspection: {staging_root}"
        )
    config.recovery_root.parent.mkdir(parents=True, exist_ok=True)
    staging_journal = staging_root / config.journal.relative_to(config.recovery_root)
    staging_future = staging_root / config.future_judge_ledger.relative_to(
        config.recovery_root
    )
    source_journal_stats, target_journal_stats = _backup_sqlite_database(
        config.source_journal,
        staging_journal,
    )
    _require_initial_partition(config, source_journal_stats)
    source_future_stats, target_future_stats = _backup_sqlite_database(
        config.source_future_judge_ledger,
        staging_future,
    )
    if "judge_evidence" not in source_future_stats.get("tables", []):
        raise RuntimeError("source future Judge ledger lacks judge_evidence")
    workspace_contract = {
        "schema_version": WORKSPACE_CONTRACT_SCHEMA,
        "contract_id": config.contract_id,
        "source_journal": str(config.source_journal),
        "target_journal": str(config.journal),
        "source_future_judge_ledger": str(config.source_future_judge_ledger),
        "target_future_judge_ledger": str(config.future_judge_ledger),
        "source_journal_mutated": False,
        "source_future_judge_ledger_mutated": False,
        "copied_via_sqlite_backup": True,
        "pending_partition": {
            "review18_qids": list(config.target_qids),
            "max7_qids": list(config.max7_qids),
            "exact_initial_pending_qids": list(config.exact_initial_pending_qids),
            "exact_initial_pending_count": config.expected_initial_pending,
        },
        "source_safe_stats": {
            "journal": source_journal_stats,
            "future_judge_ledger": source_future_stats,
        },
        "target_initial_safe_stats": {
            "journal": _stats_with_path(target_journal_stats, config.journal),
            "future_judge_ledger": _stats_with_path(
                target_future_stats,
                config.future_judge_ledger,
            ),
        },
    }
    staging_contract = staging_root / config.workspace_contract_artifact.relative_to(
        config.recovery_root
    )
    _write_or_verify_json(staging_contract, workspace_contract)
    os.replace(staging_root, config.recovery_root)
    return validate_existing_candidate_recovery_workspace(
        config,
        require_initial_state=True,
    )


def validate_existing_candidate_recovery_workspace(
    config: ExistingCandidateRecoveryBatchConfig,
    *,
    require_initial_state: bool = False,
) -> dict[str, Any]:
    config.validate()
    contract = _read_json_if_exists(config.workspace_contract_artifact)
    if not isinstance(contract, dict):
        raise RuntimeError("recovery workspace exists without its contract")
    expected_identity = {
        "schema_version": WORKSPACE_CONTRACT_SCHEMA,
        "contract_id": config.contract_id,
        "source_journal": str(config.source_journal),
        "target_journal": str(config.journal),
        "source_future_judge_ledger": str(config.source_future_judge_ledger),
        "target_future_judge_ledger": str(config.future_judge_ledger),
        "source_journal_mutated": False,
        "source_future_judge_ledger_mutated": False,
        "copied_via_sqlite_backup": True,
        "pending_partition": {
            "review18_qids": list(config.target_qids),
            "max7_qids": list(config.max7_qids),
            "exact_initial_pending_qids": list(config.exact_initial_pending_qids),
            "exact_initial_pending_count": config.expected_initial_pending,
        },
    }
    for key, expected in expected_identity.items():
        if contract.get(key) != expected:
            raise RuntimeError(f"recovery workspace contract differs: {key}")
    source_stats = contract.get("source_safe_stats")
    target_initial_stats = contract.get("target_initial_safe_stats")
    if not isinstance(source_stats, dict) or not isinstance(target_initial_stats, dict):
        raise RuntimeError("recovery workspace safe stats are missing")
    current_source_journal = _sqlite_safe_stats(config.source_journal)
    current_source_future = _sqlite_safe_stats(config.source_future_judge_ledger)
    if current_source_journal != source_stats.get("journal"):
        raise RuntimeError("source journal changed after recovery workspace creation")
    if current_source_future != source_stats.get("future_judge_ledger"):
        raise RuntimeError(
            "source future Judge ledger changed after recovery workspace creation"
        )
    current_target_journal = _sqlite_safe_stats(config.journal)
    current_target_future = _sqlite_safe_stats(config.future_judge_ledger)
    states = current_target_journal.get("item_state_counts", {})
    pending = set(current_target_journal.get("pending_qids", []))
    initial_pending = set(config.exact_initial_pending_qids)
    if (
        current_target_journal.get("table_row_counts", {}).get("items")
        != config.expected_completed_items
        or set(states) - {"completed", "pending"}
        or not pending.issubset(initial_pending)
        or int(states.get("completed", 0)) < config.expected_initial_completed
        or int(states.get("completed", 0)) > config.expected_completed_items
    ):
        raise RuntimeError("recovery journal state escaped the frozen 56-item partition")
    if "judge_evidence" not in current_target_future.get("tables", []):
        raise RuntimeError("recovery future Judge ledger lacks judge_evidence")
    if require_initial_state:
        _require_initial_partition(config, current_target_journal)
        if current_target_journal != target_initial_stats.get("journal"):
            raise RuntimeError("initial recovery journal differs from SQLite backup")
        if current_target_future != target_initial_stats.get("future_judge_ledger"):
            raise RuntimeError(
                "initial recovery future Judge ledger differs from SQLite backup"
            )
    return contract


def freeze_existing_candidate_batch_manifest(
    config: ExistingCandidateRecoveryBatchConfig,
    *,
    judge_records: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    existing = _read_json_if_exists(config.batch_manifest)
    if existing is not None:
        _validate_existing_candidate_batch_manifest(config, existing)
        return existing
    workspace_contract = validate_existing_candidate_recovery_workspace(
        config,
        require_initial_state=True,
    )
    items: list[dict[str, Any]] = []
    for qid in config.target_qids:
        item_config = config.item_config(qid)
        _item, parent_tokens, candidates = discover_existing_candidates(
            item_config,
            judge_records=judge_records,
        )
        if not candidates:
            raise RuntimeError(f"q{qid} has no admissible frozen existing candidates")
        item_manifest = freeze_existing_candidate_manifest(
            item_config,
            parent_tokens=parent_tokens,
            candidates=candidates,
        )
        items.append(
            {
                "qid": qid,
                "candidate_manifest": str(item_config.candidate_manifest),
                "candidate_count": int(item_manifest["candidate_count"]),
                "first_rank": int(item_manifest["first_rank"]),
            }
        )
    manifest = {
        "schema_version": BATCH_MANIFEST_SCHEMA,
        "contract_id": config.contract_id,
        "status": "frozen_no_provider_calls",
        "workspace_contract": workspace_contract,
        "target_qids_in_review_order": list(config.target_qids),
        "max7_qids_excluded": list(config.max7_qids),
        "target_count": len(config.target_qids),
        "candidate_order": ["chain_token_count", "chain_char_count", "candidate_id"],
        "sequential_materialization": True,
        "new_qwen_rollouts": 0,
        "qwen_tokenizer_calls": 0,
        "qwen_base_url": None,
        "materialization_judge": {
            "provider": "cli_proxy",
            "model": "gpt-5.5",
            "reasoning_effort": "xhigh",
            "fail_closed": True,
        },
        "items": items,
    }
    _write_or_verify_json(config.batch_manifest, manifest)
    return manifest


def load_existing_candidate_batch_manifest(
    config: ExistingCandidateRecoveryBatchConfig,
) -> dict[str, Any]:
    manifest = _read_json_if_exists(config.batch_manifest)
    if not isinstance(manifest, dict):
        raise RuntimeError("batch execute requires a frozen prepare manifest")
    _validate_existing_candidate_batch_manifest(config, manifest)
    return manifest


def _validate_existing_candidate_batch_manifest(
    config: ExistingCandidateRecoveryBatchConfig,
    manifest: dict[str, Any],
) -> None:
    workspace_contract = validate_existing_candidate_recovery_workspace(config)
    expected = {
        "schema_version": BATCH_MANIFEST_SCHEMA,
        "contract_id": config.contract_id,
        "status": "frozen_no_provider_calls",
        "workspace_contract": workspace_contract,
        "target_qids_in_review_order": list(config.target_qids),
        "max7_qids_excluded": list(config.max7_qids),
        "target_count": len(config.target_qids),
        "candidate_order": ["chain_token_count", "chain_char_count", "candidate_id"],
        "sequential_materialization": True,
        "new_qwen_rollouts": 0,
        "qwen_tokenizer_calls": 0,
        "qwen_base_url": None,
        "materialization_judge": {
            "provider": "cli_proxy",
            "model": "gpt-5.5",
            "reasoning_effort": "xhigh",
            "fail_closed": True,
        },
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise RuntimeError(f"frozen batch candidate manifest differs: {key}")
    items = manifest.get("items")
    if not isinstance(items, list) or [row.get("qid") for row in items] != list(
        config.target_qids
    ):
        raise RuntimeError("frozen batch candidate manifest item order differs")
    for row in items:
        if not isinstance(row, dict):
            raise RuntimeError("frozen batch candidate manifest item is invalid")
        qid = int(row["qid"])
        item_config = config.item_config(qid)
        item_manifest = _read_json_if_exists(item_config.candidate_manifest)
        if not isinstance(item_manifest, dict):
            raise RuntimeError(f"q{qid} frozen candidate manifest is missing")
        if (
            row.get("candidate_manifest") != str(item_config.candidate_manifest)
            or row.get("candidate_count") != item_manifest.get("candidate_count")
            or row.get("first_rank") != item_manifest.get("first_rank")
        ):
            raise RuntimeError(f"q{qid} batch candidate manifest binding differs")


def discover_existing_candidates(
    config: ExistingCandidateRecoveryConfig,
    *,
    judge_records: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], int, list[ExistingCandidate]]:
    """Replay the frozen adaptive protocol without any provider/runtime access."""

    replay = _replay_existing_qid(config, judge_records=judge_records)
    return replay.item, replay.parent_tokens, list(replay.candidates)


def _replay_existing_qid(
    config: ExistingCandidateRecoveryConfig,
    *,
    judge_records: Sequence[dict[str, Any]],
) -> _OfflineReplay:
    """Re-run only the pure adaptive state machine over durable evidence."""

    config.validate()
    item = _load_target_item(config.input_manifest, config.target_qid)
    connection = sqlite3.connect(
        f"file:{config.journal.as_posix()}?mode=ro", uri=True
    )
    connection.row_factory = sqlite3.Row
    try:
        item_row = connection.execute(
            "SELECT state,parent_token_count,input_json FROM items WHERE qid=?",
            (config.target_qid,),
        ).fetchone()
        if item_row is None:
            raise RuntimeError(f"candidate recovery item q{config.target_qid} is absent")
        if item_row["state"] == "completed":
            raise RuntimeError(
                f"candidate recovery item q{config.target_qid} is already completed"
            )
        parent_tokens = item_row["parent_token_count"]
        if type(parent_tokens) is not int or parent_tokens < 1:
            raise RuntimeError("candidate recovery parent token count is missing")
        if json.loads(item_row["input_json"] or "null") != item:
            raise RuntimeError(
                "candidate recovery input differs from registered journal item"
            )
        request_rows = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM requests WHERE qid=? ORDER BY request_seq",
                (config.target_qid,),
            ).fetchall()
        ]
        has_prompts = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='prompts'"
        ).fetchone()
        prompt_rows = (
            {
                str(row["prompt_key"]): dict(row)
                for row in connection.execute(
                    "SELECT * FROM prompts WHERE qid=?", (config.target_qid,)
                ).fetchall()
            }
            if has_prompts
            else {}
        )
        audits = {
            str(row["candidate_key"]): {
                "candidate_key": str(row["candidate_key"]),
                "passed": row["passed"] == 1,
                "coherent": row["coherent"] == 1,
                "error": row["error"],
                "evidence": json.loads(row["evidence_json"] or "null"),
            }
            for row in connection.execute(
                "SELECT * FROM audits WHERE qid=?", (config.target_qid,)
            ).fetchall()
        }
        replacements = {
            int(row["step_index"]): dict(row)
            for row in connection.execute(
                "SELECT * FROM replacements WHERE qid=? ORDER BY step_index",
                (config.target_qid,),
            ).fetchall()
        }
    finally:
        connection.close()

    chain_judges: dict[str, dict[str, Any]] = {}
    for record in judge_records:
        if not (
            record.get("kind") == "chain"
            and int(record.get("qid", -1)) == config.target_qid
            and isinstance(record.get("request_key"), str)
        ):
            continue
        request_key = str(record["request_key"])
        if request_key in chain_judges:
            raise RuntimeError(f"duplicate completed chain Judge evidence: {request_key}")
        chain_judges[request_key] = record

    recovered_count = _overlay_g1_recovered_rows(
        config,
        request_rows=request_rows,
        prompts=prompt_rows,
        item=item,
    )
    parent_audit = audits.get("parent_original")
    if not isinstance(parent_audit, dict):
        raise RuntimeError("candidate recovery lacks the durable parent audit")
    parent = QwenPnsCotParent(
        question_id=config.target_qid,
        query_type=str(item["query_type"]),
        original_cot=str(item["parent_reasoning"]),
        parent_answer=str(item.get("parent_answer") or item.get("gold_answer") or ""),
        original_qwen_tokens=parent_tokens,
        parent_audit=parent_audit,
    )
    parent.validate()
    validator = CladderAdapter()
    trials: dict[tuple[int, str, int], RolloutTrial] = {}
    request_seq_by_key: dict[str, int] = {}
    row_by_key: dict[str, dict[str, Any]] = {}
    for row in request_rows:
        request_key = str(row.get("request_key") or "")
        request_seq_by_key[request_key] = int(row.get("request_seq") or 0)
        row_by_key[request_key] = row
        branch = str(row.get("branch") or "")
        if branch not in {"keep", "delete", "replace"}:
            continue
        key = (int(row["step_index"]), branch, int(row["rollout"]))
        if key in trials:
            raise RuntimeError(f"duplicate durable rollout slot: {key}")
        candidate_id = f"{branch}_s{key[0]}:t{key[2]}"
        audit = audits.get(candidate_id)
        raw_judge = chain_judges.get(request_key)
        judge, strict_profile = _trace_judge_metadata(raw_judge)
        deterministic = validator.validate_pns_answer(
            {**item, "answer": item.get("gold_answer")},
            row.get("parsed_answer"),
        )
        base = trial_from_qwen_journal_row(
            {**row, "candidate_key": candidate_id},
            parent_qwen_tokens=parent_tokens,
            parent_answer=parent.parent_answer,
            audit=audit,
        )
        judge_accepted = bool(
            isinstance(raw_judge, dict)
            and raw_judge.get("accepted") is True
            and strict_profile
        )
        valid_for_vote = bool(base.valid_for_vote and judge_accepted)
        if valid_for_vote and bool(base.correct) != deterministic.valid:
            raise RuntimeError(
                f"deterministic answer differs from durable row: {request_key}"
            )
        trials[key] = replace(
            base,
            valid_for_vote=valid_for_vote,
            correct=deterministic.valid if valid_for_vote else base.correct,
            candidate_eligible=bool(base.candidate_eligible and judge_accepted),
            error=(
                base.error
                or (
                    None
                    if judge_accepted
                    else "judge_evidence_unavailable_or_rejected_fail_closed"
                )
            ),
            metadata={
                **base.metadata,
                "judge": judge,
                "deterministic_answer_validation": asdict(deterministic),
                **(
                    {"request_recovery": row["_request_recovery"]}
                    if isinstance(row.get("_request_recovery"), dict)
                    else {}
                ),
            },
        )

    eligible_steps = [
        int(segment["step_index"])
        for segment in item.get("segments", [])
        if isinstance(segment, dict)
        and segment.get("answer_exposed_prefix") is not True
    ]
    if not eligible_steps or len(eligible_steps) != int(item.get("safe_step_count", -1)):
        raise RuntimeError("candidate recovery eligible step set differs")

    def generate(
        step: int,
        lineage: str,
        _valid_round: int,
        raw_attempt: int,
        _replacement_text: str | None,
    ) -> RolloutTrial:
        trial = trials.get((step, lineage, raw_attempt))
        if trial is not None:
            return trial
        return RolloutTrial(
            valid_for_vote=False,
            candidate_id=f"{lineage}_s{step}:t{raw_attempt}",
            error="durable_rollout_slot_missing_fail_closed",
            metadata={"judge": _trace_judge_metadata(None)[0]},
        )

    replacement_judges = {
        int(record["step_index"]): record
        for record in judge_records
        if record.get("kind") == "replacement"
        and int(record.get("qid", -1)) == config.target_qid
        and isinstance(record.get("step_index"), int)
    }

    def generate_replacement(step: int) -> ReplacementGeneration:
        durable = replacements.get(step)
        if not durable or not durable.get("generation_request_key"):
            return ReplacementGeneration(
                valid=False,
                error="durable_replacement_generation_missing_fail_closed",
            )
        row = row_by_key.get(str(durable["generation_request_key"]))
        if row is None:
            return ReplacementGeneration(
                valid=False,
                request_key=str(durable["generation_request_key"]),
                error="durable_replacement_request_missing_fail_closed",
            )
        generation = replacement_generation_from_qwen_journal_row(row)
        raw_judge = replacement_judges.get(step)
        accepted = isinstance(raw_judge, dict) and raw_judge.get("accepted") is True
        return replace(
            generation,
            valid=bool(generation.valid and accepted),
            error=(
                generation.error
                or (None if accepted else "replacement_judge_unavailable_or_rejected")
            ),
            metadata={
                **generation.metadata,
                "judge": _safe_judge_metadata(raw_judge or {}),
            },
        )

    full_asset = _load_full_pns_asset_template(config.journal)
    full_asset.update({"journal": config.journal.name, "qid": config.target_qid})
    result = generate_optimized_pnscot(
        parent,
        eligible_step_indexes=eligible_steps,
        generate=generate,
        generate_replacement=generate_replacement,
        full_pns_asset=full_asset,
        config=AdaptiveRolloutConfig(),
        step_workers=1,
    )
    _verify_replay_against_durable_replacements(result.step_results, replacements)

    candidates: list[ExistingCandidate] = []
    for rank, record in enumerate(result.ranked_candidates, 1):
        trial = record.trial
        request_key = str(trial.request_key or "")
        raw_judge = chain_judges.get(request_key)
        audit = trial.metadata.get("audit")
        if not isinstance(raw_judge, dict) or not isinstance(audit, dict):
            raise RuntimeError(f"exportable candidate lacks durable evidence: {request_key}")
        safe_chain = _safe_judge_metadata(raw_judge)
        safe_chain["evidence_id"] = str(raw_judge.get("evidence_id") or "")
        candidates.append(
            ExistingCandidate(
                qid=config.target_qid,
                rank=rank,
                request_seq=request_seq_by_key[request_key],
                request_key=request_key,
                candidate_id=str(trial.candidate_id),
                step_index=int(record.trial.candidate_id.split("_s", 1)[1].split(":", 1)[0]),
                branch=record.lineage.split("_s", 1)[0],
                rollout=record.raw_attempt,
                chain_token_count=int(trial.reasoning_tokens),
                chain_char_count=int(trial.reasoning_chars or len(trial.reasoning)),
                complete_chain=trial.reasoning,
                parsed_answer=str(trial.predicted_answer),
                audit=audit,
                chain_judge=safe_chain,
                chain_evidence_id=safe_chain["evidence_id"],
            )
        )
    if not candidates:
        raise RuntimeError("candidate recovery found no exportable admitted candidates")

    original_state_counts: dict[str, int] = {}
    for row in request_rows:
        state = str(row.get("_source_journal_state") or row.get("state") or "missing")
        original_state_counts[state] = original_state_counts.get(state, 0) + 1
    replay_trace = dict(result.artifact["adaptive_rollout"])
    replay_trace.update(
        {
            "steps": [_step_summary(step) for step in result.step_results],
            "trace_source": (
                "pure_offline_replay_of_existing_journal_g1_sidecar_and_completed_judge_evidence"
            ),
            "journal_lifecycle_accounting": {
                "registered_slots": len(request_rows),
                "actual_generation_posts": sum(
                    row.get("posting_at") is not None for row in request_rows
                ),
                "responses_received": sum(
                    row.get("response_received_at") is not None
                    or isinstance(row.get("_request_recovery"), dict)
                    for row in request_rows
                ),
                "source_state_counts": dict(sorted(original_state_counts.items())),
                "g1_recovered_response_count": recovered_count,
            },
        }
    )
    return _OfflineReplay(
        item=item,
        parent_tokens=parent_tokens,
        candidates=tuple(candidates),
        rollout_trace=replay_trace,
    )


def _overlay_g1_recovered_rows(
    config: ExistingCandidateRecoveryConfig,
    *,
    request_rows: list[dict[str, Any]],
    prompts: dict[str, dict[str, Any]],
    item: dict[str, Any],
) -> int:
    posting = [row for row in request_rows if row.get("state") == "posting"]
    if not posting:
        return 0
    if config.qwen_recovery_manifest is None or config.qwen_recovery_sidecar is None:
        return 0
    manifest = load_g1_manifest(config.qwen_recovery_manifest)
    expected_source = (
        config.replay_source_journal or config.journal
    ).resolve()
    if Path(manifest.source_journal).resolve() != expected_source:
        raise RuntimeError("g1 recovery manifest source journal differs")
    if config.replay_source_journal is not None:
        _validate_copied_journal_replay_binding(config)
    authorized = {request.source_request_key: request for request in manifest.requests}
    connection = sqlite3.connect(
        f"file:{config.qwen_recovery_sidecar.as_posix()}?mode=ro", uri=True
    )
    connection.row_factory = sqlite3.Row
    recovered = 0
    try:
        for row in posting:
            request_key = str(row.get("request_key") or "")
            request = authorized.get(request_key)
            if request is None:
                continue
            dispatch = connection.execute(
                "SELECT * FROM recovery_dispatches WHERE source_request_key=?",
                (request_key,),
            ).fetchone()
            encoding = connection.execute(
                """
                SELECT * FROM recovery_encodings
                WHERE source_key=? AND purpose='complete_candidate_chain'
                """,
                (request_key,),
            ).fetchone()
            if dispatch is None or dispatch["state"] != "succeeded" or encoding is None:
                continue
            if json.loads(dispatch["source_identity_json"] or "null") != request.to_dict():
                raise RuntimeError(f"g1 recovery identity differs: {request_key}")
            prompt = prompts.get(str(row.get("prompt_key") or ""))
            if prompt is None:
                raise RuntimeError(f"g1 recovered prompt is missing: {request_key}")
            parsed = _parse_g1_completion(
                json.loads(dispatch["response_json"] or "null"),
                frozen_prefix=str(prompt.get("frozen_prefix") or ""),
                expected_prompt_ids=json.loads(prompt["prompt_token_ids_json"]),
                gold_answer=str(item.get("gold_answer") or ""),
            )
            if parsed.get("complete_chain") != encoding["text"]:
                raise RuntimeError(f"g1 recovered chain encoding differs: {request_key}")
            row.update(parsed)
            row.update(
                {
                    "_source_journal_state": "posting",
                    "state": parsed["state"],
                    "chain_token_count": int(encoding["token_count"]),
                    "chain_token_ids_json": encoding["token_ids_json"],
                    "response_received_at": str(dispatch["dispatch_id"]),
                    "completed_at": str(dispatch["dispatch_id"]),
                    "_request_recovery": {
                        "generation": "g1",
                        "dispatch_id": str(dispatch["dispatch_id"]),
                        "source_request_key": request_key,
                        "cached": True,
                    },
                }
            )
            recovered += 1
    finally:
        connection.close()
    return recovered


def _validate_copied_journal_replay_binding(
    config: ExistingCandidateRecoveryConfig,
) -> None:
    if (
        config.replay_source_journal is None
        or config.recovery_workspace_contract is None
    ):
        raise RuntimeError("copied-journal replay provenance is incomplete")
    contract = _read_json_if_exists(config.recovery_workspace_contract)
    if not isinstance(contract, dict):
        raise RuntimeError("copied-journal replay workspace contract is missing")
    expected = {
        "schema_version": WORKSPACE_CONTRACT_SCHEMA,
        "source_journal": str(config.replay_source_journal),
        "target_journal": str(config.journal),
        "source_journal_mutated": False,
        "copied_via_sqlite_backup": True,
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise RuntimeError(f"copied-journal replay binding differs: {key}")


def _parse_g1_completion(
    raw: dict[str, Any],
    *,
    frozen_prefix: str,
    expected_prompt_ids: list[int],
    gold_answer: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "state": "scientific_invalid",
        "valid": 0,
        "correct": 0,
        "parsed_answer": None,
        "reasoning_suffix": None,
        "final_content": None,
        "complete_chain": None,
        "invalid_reason": None,
        "failure_class": "scientific_invalid",
    }
    choices = raw.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        result["invalid_reason"] = "response_choices_schema"
        return result
    choice = choices[0]
    text = choice.get("text")
    if choice.get("prompt_token_ids") != expected_prompt_ids:
        result["invalid_reason"] = "provider_prompt_token_ids_mismatch"
        return result
    output_ids = choice.get("token_ids")
    if not isinstance(output_ids, list) or not all(type(value) is int for value in output_ids):
        result["invalid_reason"] = "missing_output_token_ids"
        return result
    if not isinstance(text, str) or not text:
        result["invalid_reason"] = "empty_content"
        return result
    if choice.get("finish_reason") != "stop":
        result.update(
            {
                "reasoning_suffix": text,
                "complete_chain": frozen_prefix + text,
                "invalid_reason": f"finish_reason_{choice.get('finish_reason') or 'missing'}",
            }
        )
        return result
    if "</think>" not in text:
        result.update(
            {
                "reasoning_suffix": text,
                "complete_chain": frozen_prefix + text,
                "invalid_reason": "missing_think_close",
            }
        )
        return result
    reasoning_suffix, final_content = text.split("</think>", 1)
    complete_chain = frozen_prefix + reasoning_suffix
    answer = _strict_json_answer(final_content)
    result.update(
        {
            "reasoning_suffix": reasoning_suffix,
            "final_content": final_content,
            "complete_chain": complete_chain,
        }
    )
    if answer is None:
        result["invalid_reason"] = "strict_answer_parse"
        return result
    result.update(
        {
            "state": "completed",
            "valid": 1,
            "correct": int(answer == str(gold_answer).strip().lower()),
            "parsed_answer": answer,
            "invalid_reason": None,
            "failure_class": None,
        }
    )
    return result


def _strict_json_answer(content: str) -> str | None:
    try:
        parsed = json.loads(content.strip())
    except (json.JSONDecodeError, AttributeError):
        return None
    if not isinstance(parsed, dict) or set(parsed) != {"answer"}:
        return None
    answer = str(parsed.get("answer") or "").strip().lower()
    return answer if answer in {"yes", "no"} else None


def _verify_replay_against_durable_replacements(
    step_results: Sequence[Any],
    replacements: dict[int, dict[str, Any]],
) -> None:
    if {result.step_index for result in step_results} != set(replacements):
        raise RuntimeError("offline replay step set differs from durable replacements")
    for result in step_results:
        durable = replacements[result.step_index]
        decision = result.keep_delete.decision
        expected = {
            "keep_correct": decision.keep_correct,
            "delete_correct": decision.delete_correct,
            "triggered": decision.action == "trigger_replace",
        }
        actual = {
            "keep_correct": int(durable["keep_correct"]),
            "delete_correct": int(durable["delete_correct"]),
            "triggered": durable["triggered"] == 1,
        }
        if actual != expected:
            raise RuntimeError(
                f"offline replay differs from durable decision at step {result.step_index}: "
                f"{actual} != {expected}"
            )


def freeze_existing_candidate_manifest(
    config: ExistingCandidateRecoveryConfig,
    *,
    parent_tokens: int,
    candidates: Sequence[ExistingCandidate],
) -> dict[str, Any]:
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "contract_id": config.contract_id,
        "target_qid": config.target_qid,
        "source_journal": str(config.journal),
        "parent_qwen_tokens": parent_tokens,
        "candidate_order": [
            "chain_token_count",
            "chain_char_count",
            "candidate_id",
        ],
        "candidate_count": len(candidates),
        "first_rank": candidates[0].rank,
        "materialization_outcomes_consulted_for_order": False,
        "completed_rejections_retained_for_ledger_reuse": True,
        "new_qwen_rollouts": 0,
        "qwen_tokenizer_calls": 0,
        "qwen_base_url": None,
        "reserved_chain_evidence_policy": "excluded_no_resend",
        "reorder_after_materialization_judge": False,
        "candidates": [
            {
                "rank": candidate.rank,
                "request_seq": candidate.request_seq,
                "request_key": candidate.request_key,
                "candidate_id": candidate.candidate_id,
                "step_index": candidate.step_index,
                "branch": candidate.branch,
                "rollout": candidate.rollout,
                "chain_token_count": candidate.chain_token_count,
                "chain_char_count": candidate.chain_char_count,
                "chain_judge_evidence_id": candidate.chain_evidence_id,
                "materialization_evidence_id": candidate.materialization_evidence_id,
            }
            for candidate in candidates
        ],
    }
    if config.replay_source_journal is not None:
        manifest.update(
            {
                "replay_source_journal": str(config.replay_source_journal),
                "recovery_workspace_contract": str(
                    config.recovery_workspace_contract
                ),
            }
        )
    _write_or_verify_json(config.candidate_manifest, manifest)
    return manifest


def _load_or_freeze_candidate_order(
    config: ExistingCandidateRecoveryConfig,
    *,
    parent_tokens: int,
    discovered: Sequence[ExistingCandidate],
) -> tuple[dict[str, Any], list[ExistingCandidate]]:
    existing = _read_json_if_exists(config.candidate_manifest)
    if existing is None:
        manifest = freeze_existing_candidate_manifest(
            config, parent_tokens=parent_tokens, candidates=discovered
        )
        return manifest, list(discovered)
    if not (
        existing.get("schema_version") == MANIFEST_SCHEMA
        and existing.get("contract_id") == config.contract_id
        and int(existing.get("target_qid", -1)) == config.target_qid
        and int(existing.get("parent_qwen_tokens", -1)) == parent_tokens
        and existing.get("candidate_order")
        == ["chain_token_count", "chain_char_count", "candidate_id"]
        and existing.get("materialization_outcomes_consulted_for_order") is False
        and (
            config.replay_source_journal is None
            or (
                existing.get("replay_source_journal")
                == str(config.replay_source_journal)
                and existing.get("recovery_workspace_contract")
                == str(config.recovery_workspace_contract)
            )
        )
    ):
        raise RuntimeError("frozen candidate manifest identity differs")
    rows = existing.get("candidates")
    if not isinstance(rows, list) or len(rows) != existing.get("candidate_count"):
        raise RuntimeError("frozen candidate manifest candidates are invalid")
    by_key = {candidate.request_key: candidate for candidate in discovered}
    ordered: list[ExistingCandidate] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise RuntimeError("frozen candidate manifest row is invalid")
        request_key = str(raw.get("request_key") or "")
        candidate = by_key.get(request_key)
        frozen_candidate = (
            replace(candidate, rank=int(raw.get("rank", -1)))
            if candidate is not None
            else None
        )
        expected = {
            "rank": frozen_candidate.rank if frozen_candidate else None,
            "request_seq": frozen_candidate.request_seq if frozen_candidate else None,
            "request_key": frozen_candidate.request_key if frozen_candidate else None,
            "candidate_id": frozen_candidate.candidate_id if frozen_candidate else None,
            "step_index": frozen_candidate.step_index if frozen_candidate else None,
            "branch": frozen_candidate.branch if frozen_candidate else None,
            "rollout": frozen_candidate.rollout if frozen_candidate else None,
            "chain_token_count": frozen_candidate.chain_token_count if frozen_candidate else None,
            "chain_char_count": frozen_candidate.chain_char_count if frozen_candidate else None,
            "chain_judge_evidence_id": (
                frozen_candidate.chain_evidence_id if frozen_candidate else None
            ),
            "materialization_evidence_id": (
                frozen_candidate.materialization_evidence_id if frozen_candidate else None
            ),
        }
        if frozen_candidate is None or raw != expected:
            raise RuntimeError(
                f"frozen candidate manifest provenance differs: {request_key}"
            )
        ordered.append(frozen_candidate)
    return existing, ordered


def _snapshot_materialization_lifecycle(
    config: ExistingCandidateRecoveryConfig,
    *,
    manifest: dict[str, Any],
    judge_records: Sequence[dict[str, Any]],
    judge_ledger: Any,
) -> list[dict[str, Any]]:
    """Read safe materialization states without reserving or dispatching."""

    manifest_rows = manifest.get("candidates")
    if not isinstance(manifest_rows, list):
        raise RuntimeError("candidate manifest lacks lifecycle rows")
    by_evidence = {
        str(row["materialization_evidence_id"]): row
        for row in manifest_rows
        if isinstance(row, dict)
    }
    completed = {
        str(record["evidence_id"]): record
        for record in judge_records
        if record.get("kind") == "accepted_materialization"
        and int(record.get("qid", -1)) == config.target_qid
        and str(record.get("evidence_id") or "") in by_evidence
    }
    sidecar_states: dict[str, str] = {}
    sidecar_path = getattr(judge_ledger, "future_sidecar_path", None)
    if sidecar_path is not None and Path(sidecar_path).is_file():
        connection = sqlite3.connect(
            f"file:{Path(sidecar_path).resolve().as_posix()}?mode=ro", uri=True
        )
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT evidence_id,state,identity_json,result_json
                FROM judge_evidence
                WHERE evidence_id LIKE ?
                ORDER BY evidence_id
                """,
                (f"materialization:q{config.target_qid}:%",),
            ).fetchall()
        finally:
            connection.close()
        for row in rows:
            evidence_id = str(row["evidence_id"])
            manifest_row = by_evidence.get(evidence_id)
            if manifest_row is None:
                continue
            expected_identity = {
                "kind": "accepted_materialization",
                "qid": config.target_qid,
                "request_key": manifest_row["request_key"],
                "optimized": True,
            }
            if json.loads(row["identity_json"] or "null") != expected_identity:
                raise RuntimeError(
                    f"materialization lifecycle identity differs: {evidence_id}"
                )
            state = str(row["state"])
            if state == "reserved" and row["result_json"] is not None:
                raise RuntimeError(
                    f"reserved materialization unexpectedly has a result: {evidence_id}"
                )
            if state == "completed" and evidence_id not in completed:
                raise RuntimeError(
                    f"completed materialization is absent from ledger view: {evidence_id}"
                )
            sidecar_states[evidence_id] = state

    lifecycle: list[dict[str, Any]] = []
    for manifest_row in manifest_rows:
        evidence_id = str(manifest_row["materialization_evidence_id"])
        result = completed.get(evidence_id)
        state = sidecar_states.get(evidence_id)
        if result is None and state != "reserved":
            continue
        if result is not None:
            safe = _safe_judge_metadata(result)
            lifecycle.append(
                {
                    "rank": int(manifest_row["rank"]),
                    "request_key": str(manifest_row["request_key"]),
                    "evidence_id": evidence_id,
                    "ledger_state": "completed",
                    "status": safe.get("status"),
                    "parse_status": safe.get("parse_status"),
                    "decision": safe.get("decision"),
                    "accepted": safe.get("accepted") is True,
                    "provider": safe.get("provider"),
                    "actual_judge_model": safe.get("actual_judge_model")
                    or safe.get("resolved_model"),
                    "provider_call_count": safe.get("provider_call_count"),
                    "retry_count": safe.get("retry_count"),
                }
            )
        else:
            lifecycle.append(
                {
                    "rank": int(manifest_row["rank"]),
                    "request_key": str(manifest_row["request_key"]),
                    "evidence_id": evidence_id,
                    "ledger_state": "reserved",
                    "status": "reserved_indeterminate_no_resend",
                    "parse_status": "not_parsed",
                    "decision": "not_available",
                    "accepted": False,
                    "provider": None,
                    "actual_judge_model": None,
                    "provider_call_count": None,
                    "retry_count": None,
                }
            )
    return lifecycle


def _classify_materialization_lifecycle(
    snapshot: Sequence[dict[str, Any]],
    *,
    selected_rank: int | None,
    current_resume_invocations: int,
    current_attempts: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    lifecycle: list[dict[str, Any]] = []
    current_by_rank = {
        int(row["rank"]): row
        for row in current_attempts
        if isinstance(row, dict) and isinstance(row.get("rank"), int)
    }
    for source in snapshot:
        row = dict(source)
        rank = int(row["rank"])
        if row["ledger_state"] == "reserved":
            status = "reserved_indeterminate_no_resend"
        elif selected_rank is None:
            status = "completed_not_selected"
        elif rank < selected_rank:
            status = "preselected_completed_rejected_or_nonselected"
        elif rank == selected_rank:
            current = current_by_rank.get(rank, {})
            status = (
                "selected_completed_ledger_reuse"
                if current.get("ledger_reused") is True
                else "selected_completed_current_recovery"
            )
        else:
            status = (
                "post_selected_completed_due_local_artifact_validation_failure_"
                "not_selected"
            )
        row["lifecycle_status"] = status
        lifecycle.append(row)

    completed_rows = [
        row for row in lifecycle if row["ledger_state"] == "completed"
    ]
    all_completed_calls = sum(
        int(row["provider_call_count"])
        for row in completed_rows
        if type(row.get("provider_call_count")) is int
    )
    v3_new_completed_calls = sum(
        int(row["provider_call_count"])
        for row in completed_rows
        if selected_rank is not None
        and int(row["rank"]) >= selected_rank
        and type(row.get("provider_call_count")) is int
    )
    current_confirmed = sum(
        int(row.get("provider_call_count_this_recovery") or 0)
        for row in current_attempts
    )
    summary = {
        "all_completed_provider_calls": all_completed_calls,
        "v3_new_completed_provider_calls": v3_new_completed_calls,
        "indeterminate_evidence_count": sum(
            row["ledger_state"] == "reserved" for row in lifecycle
        ),
        "current_resume_invocations_started": current_resume_invocations,
        "current_resume_confirmed_provider_calls": current_confirmed,
    }
    return lifecycle, summary


def recover_existing_candidate_materialization(
    config: ExistingCandidateRecoveryConfig,
    *,
    semantic_judge: Any,
    judge_ledger: Any,
) -> dict[str, Any]:
    """Judge frozen existing candidates in order and commit the first strict pass."""

    existing_terminal = _read_json_if_exists(config.terminal_report)
    if existing_terminal is not None:
        if existing_terminal.get("contract_id") != config.contract_id:
            raise RuntimeError("candidate recovery terminal report contract differs")
        return _load_completed_artifact(config.journal, config.target_qid)

    completed = _load_completed_artifact_if_present(
        config.journal,
        config.target_qid,
    )
    if completed is not None:
        recovery = completed.get("adaptive_rollout", {}).get(
            "candidate_materialization_recovery"
        )
        if not isinstance(recovery, dict) or recovery.get("contract_id") != (
            config.contract_id
        ):
            raise RuntimeError("completed qid is not from this recovery contract")
        _finalize_recovered_artifact(config, completed)
        return completed

    judge_records = judge_ledger.completed_records()
    replay = _replay_existing_qid(config, judge_records=judge_records)
    item = replay.item
    parent_tokens = replay.parent_tokens
    manifest, candidates = _load_or_freeze_candidate_order(
        config,
        parent_tokens=parent_tokens,
        discovered=replay.candidates,
    )
    lifecycle_snapshot = _snapshot_materialization_lifecycle(
        config,
        manifest=manifest,
        judge_records=judge_records,
        judge_ledger=judge_ledger,
    )
    attempts: list[dict[str, Any]] = []
    accepted_artifact: dict[str, Any] | None = None
    accepted_candidate: ExistingCandidate | None = None
    new_calls = 0
    for candidate in candidates:
        evidence_id = candidate.materialization_evidence_id
        identity = {
            "kind": "accepted_materialization",
            "qid": config.target_qid,
            "request_key": candidate.request_key,
            "optimized": True,
        }
        try:
            previous = judge_ledger.reserve(evidence_id, identity)
        except IndeterminateJudgeDispatchError:
            attempts.append(
                {
                    "rank": candidate.rank,
                    "request_key": candidate.request_key,
                    "evidence_id": evidence_id,
                    "status": "reserved_indeterminate_skipped_no_resend",
                    "accepted": False,
                    "ledger_reused": True,
                    "provider_call_count_this_recovery": None,
                }
            )
            continue
        ledger_reused = previous is not None
        if previous is None:
            try:
                new_calls += 1
                result = _safe_judge_metadata(
                    semantic_judge.judge_chain(
                        _semantic_sample(item),
                        {
                            "steps": [
                                {
                                    "step_id": "complete_chain",
                                    "text": candidate.complete_chain,
                                }
                            ],
                            "final_answer": candidate.parsed_answer,
                        },
                        user_id=evidence_id,
                    )
                )
                judge_ledger.complete(evidence_id, result)
            except Exception as exc:
                attempts.append(
                    {
                        "rank": candidate.rank,
                        "request_key": candidate.request_key,
                        "evidence_id": evidence_id,
                        "status": f"provider_or_parse_error:{type(exc).__name__}",
                        "accepted": False,
                        "ledger_reused": False,
                        "provider_call_count_this_recovery": None,
                    }
                )
                continue
        else:
            result = _safe_judge_metadata(previous)
        attempts.append(
            {
                "rank": candidate.rank,
                "request_key": candidate.request_key,
                "evidence_id": evidence_id,
                "status": result.get("status"),
                "decision": result.get("decision"),
                "accepted": result.get("accepted") is True,
                "actual_judge_model": result.get("actual_judge_model")
                or result.get("resolved_model"),
                "ledger_reused": ledger_reused,
                "provider_call_count_this_recovery": (
                    0 if ledger_reused else int(result.get("provider_call_count") or 0)
                ),
            }
        )
        if result.get("accepted") is not True:
            continue
        try:
            _require_accepted_judge_profile(
                result,
                label="recovery materialization Judge",
            )
            accepted_artifact = _build_recovered_artifact(
                config,
                item=item,
                parent_tokens=parent_tokens,
                candidate=candidate,
                materialization_judge={
                    **result,
                    "evidence_id": evidence_id,
                    "ledger_reused": ledger_reused,
                },
                attempts=attempts,
                judge_ledger_name=Path(judge_ledger.path).name,
                rollout_trace=replay.rollout_trace,
            )
        except (RuntimeError, ValueError) as exc:
            attempts[-1].update(
                {
                    "deliverable": False,
                    "artifact_validation_status": (
                        f"failed:{type(exc).__name__}:{exc}"
                    ),
                }
            )
            continue
        attempts[-1]["deliverable"] = True
        accepted_candidate = candidate
        break

    refreshed_judge_records = judge_ledger.completed_records()
    lifecycle_snapshot = _snapshot_materialization_lifecycle(
        config,
        manifest=manifest,
        judge_records=refreshed_judge_records,
        judge_ledger=judge_ledger,
    )
    lifecycle, lifecycle_summary = _classify_materialization_lifecycle(
        lifecycle_snapshot,
        selected_rank=accepted_candidate.rank if accepted_candidate else None,
        current_resume_invocations=new_calls,
        current_attempts=attempts,
    )
    if accepted_artifact is not None:
        recovery_metadata = accepted_artifact["adaptive_rollout"][
            "candidate_materialization_recovery"
        ]
        recovery_metadata["materialization_lifecycle"] = lifecycle
        recovery_metadata["materialization_lifecycle_summary"] = lifecycle_summary
        recovery_metadata["materialization_lifecycle_classification_basis"] = {
            "frozen_candidate_order": config.candidate_manifest.name,
            "selected_rank": accepted_candidate.rank,
            "v3_new_completed_definition": (
                "completed materialization provider calls at or after selected rank"
            ),
            "post_selected_status_inference": (
                "higher-rank completed evidence exists only because the earlier "
                "accepted candidate failed local artifact validation"
            ),
            "ordering_affected_by_lifecycle": False,
        }
        _validate_pnscot_artifact(accepted_artifact)

    report = {
        "schema_version": REPORT_SCHEMA,
        "contract_id": config.contract_id,
        "target_qid": config.target_qid,
        "candidate_manifest": str(config.candidate_manifest),
        "candidate_count": manifest["candidate_count"],
        "attempted_count": len(attempts),
        "accepted": accepted_artifact is not None,
        "accepted_rank": accepted_candidate.rank if accepted_candidate else None,
        "accepted_request_key": (
            accepted_candidate.request_key if accepted_candidate else None
        ),
        "materialization_judge_invocations_started_this_recovery": new_calls,
        "materialization_provider_calls_confirmed": sum(
            int(row.get("provider_call_count_this_recovery") or 0) for row in attempts
        ),
        "materialization_provider_call_count": (
            None
            if any(
                row.get("provider_call_count_this_recovery") is None for row in attempts
            )
            else sum(
                int(row.get("provider_call_count_this_recovery") or 0)
                for row in attempts
            )
        ),
        "indeterminate_materialization_call_attempts": sum(
            row.get("provider_call_count_this_recovery") is None for row in attempts
        ),
        "new_qwen_rollouts": 0,
        "qwen_tokenizer_calls": 0,
        "qwen_base_url": None,
        "attempts": attempts,
        "materialization_lifecycle": lifecycle,
        "materialization_lifecycle_summary": lifecycle_summary,
        "materialization_lifecycle_classification_basis": (
            accepted_artifact["adaptive_rollout"][
                "candidate_materialization_recovery"
            ].get("materialization_lifecycle_classification_basis")
            if accepted_artifact is not None
            else None
        ),
    }
    if accepted_artifact is None:
        _write_or_verify_json(config.terminal_report, report)
        raise RuntimeError(
            "all frozen existing candidates failed materialization Judge"
        )
    _complete_item(config.journal, config.target_qid, accepted_artifact)
    _write_recovery_gates(config, accepted_artifact)
    report["exact_output_materialized"] = _materialize_exact_output_if_complete(config)
    _write_or_verify_json(config.terminal_report, report)
    return accepted_artifact


def _validate_review18_progress(
    config: ExistingCandidateRecoveryBatchConfig,
) -> dict[str, Any]:
    stats = _sqlite_safe_stats(config.journal)
    pending = set(stats.get("pending_qids", []))
    target = set(config.target_qids)
    max7 = set(config.max7_qids)
    if not max7.issubset(pending):
        raise RuntimeError("max7 qids were changed before review18 completed")
    completed_review = target - pending
    expected_pending = (target - completed_review) | max7
    if pending != expected_pending:
        raise RuntimeError("recovery journal pending partition differs during review18")
    expected_completed = config.expected_initial_completed + len(completed_review)
    if stats.get("item_state_counts") != {
        "completed": expected_completed,
        "pending": config.expected_completed_items - expected_completed,
    }:
        raise RuntimeError("recovery journal counts differ during review18")
    for qid in sorted(completed_review):
        artifact = _load_completed_artifact(config.journal, qid)
        recovery = artifact.get("adaptive_rollout", {}).get(
            "candidate_materialization_recovery"
        )
        if not isinstance(recovery, dict) or recovery.get("contract_id") != (
            config.item_config(qid).contract_id
        ):
            raise RuntimeError(f"completed review q{qid} has foreign provenance")
    return stats


def recover_existing_candidate_materialization_batch(
    config: ExistingCandidateRecoveryBatchConfig,
    *,
    semantic_judge: Any,
    judge_ledger: Any,
) -> dict[str, Any]:
    """Sequentially review exactly the frozen 18 qids; never dispatch Qwen."""

    config.validate()
    load_existing_candidate_batch_manifest(config)
    validate_existing_candidate_recovery_workspace(config)
    _validate_review18_progress(config)
    existing_terminal = _read_json_if_exists(config.terminal_report)
    if existing_terminal is not None:
        if not (
            existing_terminal.get("schema_version") == BATCH_REPORT_SCHEMA
            and existing_terminal.get("contract_id") == config.contract_id
            and existing_terminal.get("target_qids_in_review_order")
            == list(config.target_qids)
        ):
            raise RuntimeError("batch terminal report identity differs")
        return existing_terminal

    accepted_qids: list[int] = []
    failed_qids: list[int] = []
    item_reports: list[dict[str, Any]] = []
    for qid in config.target_qids:
        item_config = config.item_config(qid)
        prior_report = _read_json_if_exists(item_config.terminal_report)
        if isinstance(prior_report, dict) and prior_report.get("accepted") is False:
            failed_qids.append(qid)
            item_reports.append(_batch_item_report(item_config, prior_report))
            continue
        try:
            recover_existing_candidate_materialization(
                item_config,
                semantic_judge=semantic_judge,
                judge_ledger=judge_ledger,
            )
        except RuntimeError as exc:
            terminal = _read_json_if_exists(item_config.terminal_report)
            if not (
                str(exc) == "all frozen existing candidates failed materialization Judge"
                and isinstance(terminal, dict)
                and terminal.get("contract_id") == item_config.contract_id
                and terminal.get("accepted") is False
            ):
                raise
            failed_qids.append(qid)
            item_reports.append(_batch_item_report(item_config, terminal))
            _validate_review18_progress(config)
            continue
        terminal = _read_json_if_exists(item_config.terminal_report)
        if not (
            isinstance(terminal, dict)
            and terminal.get("contract_id") == item_config.contract_id
            and terminal.get("accepted") is True
        ):
            raise RuntimeError(f"q{qid} accepted without a valid terminal report")
        accepted_qids.append(qid)
        item_reports.append(_batch_item_report(item_config, terminal))
        _validate_review18_progress(config)

    final_stats = _validate_review18_progress(config)
    successful = len(accepted_qids) == len(config.target_qids) and not failed_qids
    if successful:
        if (
            final_stats.get("item_state_counts")
            != {
                "completed": config.expected_completed_after_review,
                "pending": len(config.max7_qids),
            }
            or final_stats.get("pending_qids") != sorted(config.max7_qids)
        ):
            raise RuntimeError("review18 success did not reach the frozen 53/3 gate")
    models = sorted(
        {
            str(attempt.get("actual_judge_model"))
            for report in item_reports
            for attempt in report.get("attempts", [])
            if isinstance(attempt, dict) and attempt.get("actual_judge_model")
        }
    )
    report = {
        "schema_version": BATCH_REPORT_SCHEMA,
        "contract_id": config.contract_id,
        "status": (
            "accepted_18_of_18_max7_gate_ready"
            if successful
            else "incomplete_frozen_existing_candidates_exhausted"
        ),
        "batch_manifest": str(config.batch_manifest),
        "target_qids_in_review_order": list(config.target_qids),
        "max7_qids_reserved_no_rollout_change": list(config.max7_qids),
        "target_count": len(config.target_qids),
        "accepted_count": len(accepted_qids),
        "accepted_qids": accepted_qids,
        "failed_count": len(failed_qids),
        "failed_qids": failed_qids,
        "actual_judge_models": models,
        "materialization_provider_calls_confirmed": sum(
            int(item.get("materialization_provider_calls_confirmed") or 0)
            for item in item_reports
        ),
        "indeterminate_materialization_call_attempts": sum(
            int(item.get("indeterminate_materialization_call_attempts") or 0)
            for item in item_reports
        ),
        "new_qwen_rollouts": 0,
        "qwen_tokenizer_calls": 0,
        "qwen_base_url": None,
        "journal_state": {
            "item_state_counts": final_stats.get("item_state_counts"),
            "pending_qids": final_stats.get("pending_qids"),
        },
        "exact_output_materialized": config.output_artifact.is_file(),
        "output_artifact": (
            str(config.output_artifact) if config.output_artifact.is_file() else None
        ),
        "items": item_reports,
    }
    _write_or_verify_json(config.terminal_report, report)
    return report


def _batch_item_report(
    config: ExistingCandidateRecoveryConfig,
    report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "qid": config.target_qid,
        "contract_id": config.contract_id,
        "candidate_manifest": str(config.candidate_manifest),
        "terminal_report": str(config.terminal_report),
        "candidate_count": report.get("candidate_count"),
        "attempted_count": report.get("attempted_count"),
        "accepted": report.get("accepted") is True,
        "accepted_rank": report.get("accepted_rank"),
        "accepted_request_key": report.get("accepted_request_key"),
        "materialization_provider_calls_confirmed": report.get(
            "materialization_provider_calls_confirmed"
        ),
        "indeterminate_materialization_call_attempts": report.get(
            "indeterminate_materialization_call_attempts"
        ),
        "attempts": report.get("attempts", []),
    }


def _build_recovered_artifact(
    config: ExistingCandidateRecoveryConfig,
    *,
    item: dict[str, Any],
    parent_tokens: int,
    candidate: ExistingCandidate,
    materialization_judge: dict[str, Any],
    attempts: Sequence[dict[str, Any]],
    judge_ledger_name: str,
    rollout_trace: dict[str, Any],
) -> dict[str, Any]:
    deterministic = CladderAdapter().validate_pns_answer(
        {**item, "answer": item.get("gold_answer")},
        candidate.parsed_answer,
    )
    if deterministic.valid is not True:
        raise RuntimeError("recovery candidate deterministic answer failed")
    full_pns_asset = _load_full_pns_asset_template(config.journal)
    full_pns_asset.update(
        {
            "journal": config.journal.name,
            "qid": config.target_qid,
            "judge_ledger": judge_ledger_name,
            "candidate_materialization_recovery_manifest": config.candidate_manifest.name,
            "qwen_request_recovery_sidecar": (
                config.qwen_recovery_sidecar.name
                if config.qwen_recovery_sidecar is not None
                else None
            ),
            "qwen_request_recovery_manifest": (
                config.qwen_recovery_manifest.name
                if config.qwen_recovery_manifest is not None
                else None
            ),
        }
    )
    historical_slots = int(rollout_trace["total_requested_rollout_slots"])
    lifecycle = rollout_trace["journal_lifecycle_accounting"]
    artifact = {
        "schema_version": 1,
        "question_id": config.target_qid,
        "query_type": str(item["query_type"]),
        "original_cot": str(item["parent_reasoning"]),
        "final_cot": candidate.complete_chain,
        "original_qwen_tokens": parent_tokens,
        "final_qwen_tokens": candidate.chain_token_count,
        "optimized": True,
        "fallback": False,
        "selected_candidate": candidate.candidate_id,
        "selected_request_key": candidate.request_key,
        "audit": candidate.audit,
        "adaptive_rollout": {
            **rollout_trace,
            "action": "selected_existing_candidate_materialization_recovery",
            "stop_reason": "first_materialization_judge_pass_in_frozen_order",
            "selected_lineage": candidate.branch,
            "completion_invocation_accounting": {
                "requested_slots": historical_slots,
                "reused_slots": historical_slots,
                "registered_slots": int(lifecycle["registered_slots"]),
                "actual_generation_posts": int(lifecycle["actual_generation_posts"]),
                "infrastructure_errors": 0,
                "source": "reconstructed_existing_durable_generation_history",
                "new_qwen_rollouts": 0,
                "new_actual_generation_posts": 0,
            },
            "candidate_materialization_recovery": {
                "schema_version": RECOVERY_SCHEMA,
                "contract_id": config.contract_id,
                "candidate_rank": candidate.rank,
                "candidate_manifest": config.candidate_manifest.name,
                "reviewed_materializations": len(attempts),
                "new_qwen_rollouts": 0,
                "reordered_after_judge_result": False,
                "prior_rejections_preserved": True,
                "materialization_attempts": list(attempts),
            },
        },
        "full_pns_asset": full_pns_asset,
        "judge_acceptance": materialization_judge,
        "deterministic_answer_validation": asdict(deterministic),
    }
    _validate_pnscot_artifact(artifact)
    return artifact


def _trace_judge_metadata(
    raw: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    if isinstance(raw, dict):
        safe = _safe_judge_metadata(raw)
        safe["evidence_id"] = str(raw.get("evidence_id") or "")
        # Chain admission follows the original adapter contract: a completed
        # ledger verdict is consumed through ``accepted``.  The stricter
        # materialization profile is applied only to the newly judged final
        # artifact, not retroactively to historical per-chain evidence.
        return safe, raw.get("accepted") is True
    return (
        {
            "provider": None,
            "requested_model": None,
            "resolved_model": None,
            "thinking_type": None,
            "reasoning_effort": None,
            "status": "completed_evidence_unavailable_no_resend",
            "parse_status": "not_parsed",
            "decision": "rejected",
            "accepted": False,
            "retry_count": None,
            "provider_call_count": None,
            "evidence_id": None,
        },
        False,
    )


def _load_target_item(path: Path, qid: int) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matches = [row for row in rows if int(row.get("question_id", -1)) == qid]
    if len(matches) != 1:
        raise RuntimeError(f"candidate recovery input must contain q{qid} exactly once")
    return matches[0]


def _semantic_sample(item: dict[str, Any]) -> dict[str, Any]:
    audit_reference = item.get("audit_reference")
    offline = (
        audit_reference.get("offline_oracle")
        if isinstance(audit_reference, dict)
        else {}
    )
    offline = offline if isinstance(offline, dict) else {}
    source_meta = offline.get("source_meta")
    source_meta = source_meta if isinstance(source_meta, dict) else {}
    sample = {
        "question_id": int(item["question_id"]),
        "given_info": str(
            offline.get("source_given_info") or item.get("given_info") or ""
        ),
        "question": str(offline.get("source_question") or item.get("question") or ""),
        "meta": {**source_meta, "query_type": str(item.get("query_type") or "")},
    }
    canonical = CladderAdapter().get_pns_canonical_steps(item)
    if canonical is not None:
        steps = [
            {"source_field": step.source_field, "text": step.text}
            for step in canonical.steps
            if not step.answer_exposed and step.source_field != "end"
        ]
        if steps:
            sample["semantic_reference"] = {
                "source": canonical.source,
                "role": "advisory_alignment_anchor_only",
                "one_to_one_required": False,
                "same_path_required": False,
                "steps": steps,
            }
    return sample


def _safe_judge_metadata(result: dict[str, Any]) -> dict[str, Any]:
    return {key: result.get(key) for key in _SAFE_JUDGE_FIELDS if key in result}


def _load_full_pns_asset_template(journal: Path) -> dict[str, Any]:
    connection = sqlite3.connect(journal)
    try:
        rows = connection.execute(
            "SELECT result_json FROM items WHERE state='completed' ORDER BY ordinal"
        ).fetchall()
    finally:
        connection.close()
    for (raw,) in rows:
        payload = json.loads(raw or "null")
        asset = (
            payload.get("artifact", {}).get("full_pns_asset")
            if isinstance(payload, dict)
            else None
        )
        if isinstance(asset, dict) and asset.get("dataset_pns_config_id") is not None:
            return dict(asset)
    raise RuntimeError("candidate recovery lacks a same-phase full_pns_asset template")


def _complete_item(journal: Path, qid: int, artifact: dict[str, Any]) -> None:
    record = {
        "schema_version": 1,
        "result_type": RESULT_TYPE,
        "policy_version": POLICY_VERSION,
        "question_id": qid,
        "artifact": artifact,
    }
    payload = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    connection = sqlite3.connect(journal)
    try:
        with connection:
            row = connection.execute(
                "SELECT state,result_json FROM items WHERE qid=?", (qid,)
            ).fetchone()
            if row is None:
                raise RuntimeError(f"candidate recovery item q{qid} disappeared")
            if row[0] == "completed":
                if json.loads(row[1] or "null") != record:
                    raise RuntimeError(f"completed recovery item q{qid} differs")
                return
            connection.execute(
                "UPDATE items SET state='completed',result_json=?,completed_at=datetime('now') WHERE qid=?",
                (payload, qid),
            )
    finally:
        connection.close()


def _load_completed_artifact(journal: Path, qid: int) -> dict[str, Any]:
    connection = sqlite3.connect(journal)
    try:
        row = connection.execute(
            "SELECT state,result_json FROM items WHERE qid=?", (qid,)
        ).fetchone()
    finally:
        connection.close()
    if row is None or row[0] != "completed":
        raise RuntimeError(f"candidate recovery terminal item q{qid} is not completed")
    payload = json.loads(row[1] or "null")
    artifact = payload.get("artifact") if isinstance(payload, dict) else None
    if not isinstance(artifact, dict):
        raise RuntimeError("candidate recovery completed artifact is invalid")
    _validate_pnscot_artifact(artifact)
    return artifact


def _load_completed_artifact_if_present(
    journal: Path,
    qid: int,
) -> dict[str, Any] | None:
    connection = sqlite3.connect(journal)
    try:
        row = connection.execute(
            "SELECT state,result_json FROM items WHERE qid=?", (qid,)
        ).fetchone()
    finally:
        connection.close()
    if row is None or row[0] != "completed":
        return None
    payload = json.loads(row[1] or "null")
    artifact = payload.get("artifact") if isinstance(payload, dict) else None
    if not isinstance(artifact, dict):
        raise RuntimeError("completed recovery item lacks its artifact")
    _validate_pnscot_artifact(artifact)
    return artifact


def _materialize_exact_output_if_complete(
    config: ExistingCandidateRecoveryConfig,
) -> bool:
    connection = sqlite3.connect(config.journal)
    try:
        rows = connection.execute(
            "SELECT qid,state,result_json FROM items ORDER BY ordinal"
        ).fetchall()
    finally:
        connection.close()
    if len(rows) != config.expected_completed_items:
        raise RuntimeError("candidate recovery journal item count differs from 56")
    if any(row[1] != "completed" for row in rows):
        return False
    artifacts = []
    for _qid, _state, raw in rows:
        payload = json.loads(raw or "null")
        artifact = payload.get("artifact") if isinstance(payload, dict) else None
        if not isinstance(artifact, dict):
            raise RuntimeError("completed item lacks PNSCoT artifact")
        _validate_pnscot_artifact(artifact)
        artifacts.append(artifact)
    serialized = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in artifacts
    )
    _write_or_verify_text(config.output_artifact, serialized)
    return True


def _finalize_recovered_artifact(
    config: ExistingCandidateRecoveryConfig,
    artifact: dict[str, Any],
) -> None:
    recovery = artifact["adaptive_rollout"]["candidate_materialization_recovery"]
    attempts = recovery.get("materialization_attempts")
    if not isinstance(attempts, list):
        raise RuntimeError("completed recovery artifact lacks attempt summaries")
    _write_recovery_gates(config, artifact)
    manifest = _read_json_if_exists(config.candidate_manifest)
    if not isinstance(manifest, dict):
        raise RuntimeError("completed recovery artifact lacks frozen manifest")
    report = {
        "schema_version": REPORT_SCHEMA,
        "contract_id": config.contract_id,
        "target_qid": config.target_qid,
        "candidate_manifest": str(config.candidate_manifest),
        "candidate_count": manifest.get("candidate_count"),
        "attempted_count": len(attempts),
        "accepted": True,
        "accepted_rank": recovery.get("candidate_rank"),
        "accepted_request_key": artifact.get("selected_request_key"),
        "materialization_provider_calls_confirmed": sum(
            int(row.get("provider_call_count_this_recovery") or 0)
            for row in attempts
            if isinstance(row, dict)
        ),
        "materialization_provider_call_count": (
            None
            if any(
                row.get("provider_call_count_this_recovery") is None
                for row in attempts
                if isinstance(row, dict)
            )
            else sum(
                int(row.get("provider_call_count_this_recovery") or 0)
                for row in attempts
                if isinstance(row, dict)
            )
        ),
        "indeterminate_materialization_call_attempts": sum(
            row.get("provider_call_count_this_recovery") is None
            for row in attempts
            if isinstance(row, dict)
        ),
        "new_qwen_rollouts": 0,
        "qwen_tokenizer_calls": 0,
        "qwen_base_url": None,
        "attempts": attempts,
        "materialization_lifecycle": recovery.get(
            "materialization_lifecycle", []
        ),
        "materialization_lifecycle_summary": recovery.get(
            "materialization_lifecycle_summary", {}
        ),
        "materialization_lifecycle_classification_basis": recovery.get(
            "materialization_lifecycle_classification_basis", {}
        ),
        "exact_output_materialized": _materialize_exact_output_if_complete(config),
    }
    _write_or_verify_json(config.terminal_report, report)


def _write_recovery_gates(
    config: ExistingCandidateRecoveryConfig, artifact: dict[str, Any]
) -> None:
    evidence = _safe_judge_metadata(artifact["judge_acceptance"])
    evidence["evidence_id"] = artifact["judge_acceptance"]["evidence_id"]
    common = {
        "passed": True,
        "question_id": artifact["question_id"],
        "optimized": True,
        "fallback": False,
        "original_qwen_tokens": artifact["original_qwen_tokens"],
        "final_qwen_tokens": artifact["final_qwen_tokens"],
        "judge_evidence": evidence,
        "deterministic_answer_validation": dict(
            artifact["deterministic_answer_validation"]
        ),
    }
    _write_gate_if_absent(
        config.first_accepted_gate,
        {"schema_version": "qwen_pns_first_accepted_judge_gate_v1", **common},
        expected_schema="qwen_pns_first_accepted_judge_gate_v1",
    )
    _write_gate_if_absent(
        config.first_future_accepted_gate,
        {"schema_version": "qwen_pns_first_future_accepted_judge_gate_v1", **common},
        expected_schema="qwen_pns_first_future_accepted_judge_gate_v1",
    )


def _write_gate_if_absent(
    path: Path,
    payload: dict[str, Any],
    *,
    expected_schema: str,
) -> None:
    existing = _read_json_if_exists(path)
    if existing is not None:
        if not (
            existing.get("schema_version") == expected_schema
            and existing.get("passed") is True
        ):
            raise RuntimeError(f"existing recovery gate is invalid: {path}")
        return
    _write_or_verify_json(path, payload)


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"recovery artifact is not an object: {path}")
    return value


def _write_or_verify_json(path: Path, payload: dict[str, Any]) -> None:
    serialized = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    _write_or_verify_text(path, serialized)


def _write_or_verify_text(path: Path, serialized: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise RuntimeError(
                f"refusing to overwrite different recovery artifact: {path}"
            )
        return
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(serialized)
