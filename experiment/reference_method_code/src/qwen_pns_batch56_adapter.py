from __future__ import annotations

import concurrent.futures
import importlib.util
import json
import math
import os
import sys
import threading
import time
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Sequence

from .qwen_pns_adaptive import (
    MAX7_RECOVERY_AMENDMENT_ID,
    POLICY_VERSION,
    AdaptivePnsCotRunResult,
    AdaptiveRolloutConfig,
    AdaptiveSeedSchedule,
    QwenPnsCotParent,
    ReplacementGeneration,
    RolloutInfrastructureError,
    RolloutTrial,
    _validate_pnscot_artifact,
    generate_optimized_pnscot,
    replacement_generation_from_qwen_journal_row,
    trial_from_qwen_journal_row,
    write_pnscot_artifact_jsonl,
)
from .pns_dataset_preparation import (
    PreparedDatasetPnsItem,
    prepare_dataset_pns_item,
)
from .pns_judge_ledger import SemanticJudgeLedger
from .qwen_pns_request_recovery import (
    QwenRequestRecovery,
    RecoveredScientificAttempt,
    RecoveryContractError,
    RecoveryInfrastructureError,
)
from .datasets.adapters.cladder import CladderAdapter


ADAPTER_VERSION = "qwen_pns_batch56_adapter_v2_qwen_source_segments"
DATASET_PNS_PROTOCOL_VERSION = "cladder_qwen_parent_segments_v2"
DATASET_PNS_CONTRACT_KEY = "dataset_pns_contract_v2"
RECOVERY_AMENDMENT_CONTRACT_KEY = "adaptive_rollout_recovery_amendment_v1"
RECOVERY_EXECUTION_GATE_KEY = "adaptive_rollout_recovery_execution_gate_v1"


@dataclass(frozen=True)
class DatasetPnsExecutionConfig:
    """Dataset-routed PNS execution contract for the fresh CLADDER run."""

    dataset_name: str = "CLADDER"
    canonical_context_authorization: str = "pns_intervention_only"
    fallback_policy: str = "qwen_parent_source_preserving_v1"
    allow_explicit_fallback: bool = True
    protocol_version: str = DATASET_PNS_PROTOCOL_VERSION

    def validate(self) -> None:
        if self.dataset_name != "CLADDER":
            raise ValueError(
                "the current batch56 execution adapter is CLADDER-specific"
            )
        if self.canonical_context_authorization != "pns_intervention_only":
            raise ValueError(
                "canonical context must be scoped to pns_intervention_only"
            )
        if self.allow_explicit_fallback and not self.fallback_policy.strip():
            raise ValueError("dataset PNS fallback policy must be named")
        if self.protocol_version != DATASET_PNS_PROTOCOL_VERSION:
            raise ValueError(
                "dataset PNS protocol must use frozen Qwen source segments v2"
            )


@dataclass(frozen=True)
class AdaptiveRolloutRecoveryAmendment:
    """Narrow, journal-isolated raw-attempt amendment for failed phase56 items."""

    target_qids: tuple[int, ...]
    source_journal: str
    target_journal: str
    workspace_manifest: str
    contract_id: str = MAX7_RECOVERY_AMENDMENT_ID
    base_max_raw_attempts_per_lineage: int = 5
    amended_max_raw_attempts_per_lineage: int = 7
    new_raw_slots_only: tuple[int, ...] = (6, 7)
    required_completed_before_execute: int = 53
    expected_total_items: int = 56

    def validate(self) -> None:
        if self.contract_id != MAX7_RECOVERY_AMENDMENT_ID:
            raise ValueError("max7 recovery contract_id differs")
        if not self.target_qids or len(set(self.target_qids)) != len(
            self.target_qids
        ):
            raise ValueError("recovery target_qids must be nonempty and unique")
        if any(type(qid) is not int or qid < 1 for qid in self.target_qids):
            raise ValueError("recovery target_qids must be positive integers")
        if self.base_max_raw_attempts_per_lineage != 5:
            raise ValueError("recovery base raw-attempt cap must remain five")
        if self.amended_max_raw_attempts_per_lineage != 7:
            raise ValueError("recovery amended raw-attempt cap must be seven")
        if self.new_raw_slots_only != (6, 7):
            raise ValueError("recovery may add only raw slots six and seven")
        if self.required_completed_before_execute + len(self.target_qids) != (
            self.expected_total_items
        ):
            raise ValueError("recovery completion gate does not partition the batch")
        source = Path(self.source_journal).resolve()
        target = Path(self.target_journal).resolve()
        if source == target:
            raise ValueError("source and target recovery journals must differ")
        if target.name != "journal.sqlite3":
            raise ValueError("recovery target must be the shared journal.sqlite3")
        if not str(self.workspace_manifest).strip():
            raise ValueError("recovery workspace manifest is required")

    def config_for_qid(
        self, base: AdaptiveRolloutConfig, qid: int
    ) -> AdaptiveRolloutConfig:
        self.validate()
        base.validate()
        if base.max_raw_attempts_per_lineage != (
            self.base_max_raw_attempts_per_lineage
        ):
            raise ValueError("recovery must be layered over the frozen max-five config")
        if int(qid) not in self.target_qids:
            return base
        amended = replace(
            base,
            max_raw_attempts_per_lineage=self.amended_max_raw_attempts_per_lineage,
            raw_attempt_recovery_amendment=self.contract_id,
        )
        amended.validate()
        return amended

    def contract(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": RECOVERY_AMENDMENT_CONTRACT_KEY,
            "contract_id": self.contract_id,
            "target_qids": list(self.target_qids),
            "source_journal": str(Path(self.source_journal).resolve()),
            "target_journal": str(Path(self.target_journal).resolve()),
            "workspace_manifest": str(Path(self.workspace_manifest).resolve()),
            "source_journal_mutated": False,
            "base_max_raw_attempts_per_lineage": (
                self.base_max_raw_attempts_per_lineage
            ),
            "amended_max_raw_attempts_per_lineage": (
                self.amended_max_raw_attempts_per_lineage
            ),
            "new_raw_slots_only": list(self.new_raw_slots_only),
            "required_completed_before_execute": (
                self.required_completed_before_execute
            ),
            "expected_total_items": self.expected_total_items,
            "unchanged": [
                "sample_manifest",
                "generation_model",
                "segmentation",
                "rubric",
                "deterministic_answer_validation",
                "strict_shorter_than_parent",
                "initial_valid_rounds",
                "max_valid_rounds",
            ],
        }

    def verify_execution_gate(self, journal: Any) -> dict[str, Any]:
        """Attest 53+3 once, then permit only monotonic resume of the same 3."""

        self.validate()
        actual = Path(journal.path).resolve()
        expected = Path(self.target_journal).resolve()
        if actual != expected:
            raise RuntimeError(
                "recovery adapter is not attached to the isolated target journal"
            )
        rows = list(journal.item_rows())
        if len(rows) != self.expected_total_items:
            raise RuntimeError(
                f"recovery journal must contain exactly {self.expected_total_items} items"
            )
        state_by_qid = {int(row["qid"]): str(row.get("state") or "pending") for row in rows}
        if len(state_by_qid) != self.expected_total_items:
            raise RuntimeError("recovery journal item qids must be unique")
        target_set = set(self.target_qids)
        pending = sorted(
            qid for qid, state in state_by_qid.items() if state != "completed"
        )
        completed = sum(state == "completed" for state in state_by_qid.values())
        prior = journal.get_meta(RECOVERY_EXECUTION_GATE_KEY, None)
        if prior is None:
            if completed != self.required_completed_before_execute or set(pending) != target_set:
                raise RuntimeError(
                    "max7 recovery requires exactly "
                    f"{self.required_completed_before_execute} completed items and "
                    f"pending qids {sorted(target_set)} before first execution"
                )
            evidence = {
                "schema_version": RECOVERY_EXECUTION_GATE_KEY,
                "passed": True,
                "initial_completed_count": completed,
                "initial_pending_qids": pending,
                "target_qids": list(self.target_qids),
                "source_journal": str(Path(self.source_journal).resolve()),
                "target_journal": str(expected),
                "workspace_manifest": str(Path(self.workspace_manifest).resolve()),
                "source_journal_mutated": False,
            }
            journal.set_meta(RECOVERY_EXECUTION_GATE_KEY, evidence, require_same=True)
            return evidence
        if not isinstance(prior, dict) or prior != {
            "schema_version": RECOVERY_EXECUTION_GATE_KEY,
            "passed": True,
            "initial_completed_count": self.required_completed_before_execute,
            "initial_pending_qids": sorted(target_set),
            "target_qids": list(self.target_qids),
            "source_journal": str(Path(self.source_journal).resolve()),
            "target_journal": str(expected),
            "workspace_manifest": str(Path(self.workspace_manifest).resolve()),
            "source_journal_mutated": False,
        }:
            raise RuntimeError("max7 recovery execution-gate attestation differs")
        if not set(pending).issubset(target_set):
            raise RuntimeError("non-target item became pending during max7 recovery")
        if completed < self.required_completed_before_execute:
            raise RuntimeError("completed item count regressed during max7 recovery")
        return prior


@dataclass(frozen=True)
class VllmEndpointMetrics:
    running: int
    waiting: int
    kv_cache_usage: float
    preemptions_total: int
    generation_tokens_total: int


def parse_vllm_metrics(payload: str) -> VllmEndpointMetrics:
    """Extract the endpoint-local capacity signals from vLLM Prometheus text."""

    values: dict[str, float] = {}
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            head, raw_value = line.rsplit(None, 1)
            name = head.split("{", 1)[0]
            values[name] = float(raw_value)
        except (ValueError, TypeError):
            continue

    def required(*names: str) -> float:
        for name in names:
            if name in values:
                return values[name]
        raise ValueError(f"vLLM metrics missing {names[0]}")

    return VllmEndpointMetrics(
        running=int(required("vllm:num_requests_running")),
        waiting=int(required("vllm:num_requests_waiting")),
        kv_cache_usage=required(
            "vllm:kv_cache_usage_perc", "vllm:gpu_cache_usage_perc"
        ),
        preemptions_total=int(required("vllm:num_preemptions_total")),
        generation_tokens_total=int(required("vllm:generation_tokens_total")),
    )


@dataclass(frozen=True)
class AdaptiveEndpointConcurrencyConfig:
    initial_inflight: int = 48
    min_inflight: int = 16
    max_inflight: int = 64
    increase_step: int = 4
    samples_per_window: int = 6
    low_kv_threshold: float = 0.70
    soft_kv_threshold: float = 0.82
    hard_kv_threshold: float = 0.90

    def validate(self) -> None:
        if self.min_inflight < 1:
            raise ValueError("min_inflight must be positive")
        if not self.min_inflight <= self.initial_inflight <= self.max_inflight:
            raise ValueError("initial_inflight must be within endpoint bounds")
        if self.increase_step < 1 or self.samples_per_window < 1:
            raise ValueError("endpoint step and window must be positive")
        if not (
            0.0
            < self.low_kv_threshold
            < self.soft_kv_threshold
            < self.hard_kv_threshold
            <= 1.0
        ):
            raise ValueError("KV thresholds must be strictly increasing")


@dataclass(frozen=True)
class EndpointConcurrencyDecision:
    target: int
    changed: bool
    reason: str


class AdaptiveEndpointConcurrencyPolicy:
    """Endpoint-local admission target driven by its own vLLM capacity."""

    def __init__(self, config: AdaptiveEndpointConcurrencyConfig) -> None:
        config.validate()
        self.config = config
        self.target = config.initial_inflight
        self._samples: list[VllmEndpointMetrics] = []
        self._last_preemptions: int | None = None

    def _set_target(self, target: int, reason: str) -> EndpointConcurrencyDecision:
        bounded = min(self.config.max_inflight, max(self.config.min_inflight, target))
        changed = bounded != self.target
        self.target = bounded
        self._samples.clear()
        return EndpointConcurrencyDecision(
            target=self.target,
            changed=changed,
            reason=reason,
        )

    def observe(self, metrics: VllmEndpointMetrics) -> EndpointConcurrencyDecision:
        preempted = bool(
            self._last_preemptions is not None
            and metrics.preemptions_total > self._last_preemptions
        )
        self._last_preemptions = metrics.preemptions_total
        hard_waiting = metrics.waiting >= max(8, math.ceil(self.target * 0.15))
        if (
            metrics.kv_cache_usage >= self.config.hard_kv_threshold
            or hard_waiting
            or preempted
        ):
            decrement = max(
                self.config.increase_step,
                math.ceil((self.target * 0.25) / self.config.increase_step)
                * self.config.increase_step,
            )
            return self._set_target(
                self.target - decrement, "hard_capacity_backoff"
            )

        self._samples.append(metrics)
        if len(self._samples) < self.config.samples_per_window:
            return EndpointConcurrencyDecision(
                target=self.target,
                changed=False,
                reason="collecting_capacity_window",
            )

        window = self._samples
        if (
            max(sample.kv_cache_usage for sample in window)
            > self.config.soft_kv_threshold
            or sum(sample.waiting > 0 for sample in window) >= 3
        ):
            return self._set_target(
                self.target - self.config.increase_step, "soft_capacity_backoff"
            )
        if (
            max(sample.kv_cache_usage for sample in window)
            <= self.config.low_kv_threshold
            and all(sample.waiting == 0 for sample in window)
            and max(sample.running for sample in window) >= self.target
        ):
            return self._set_target(
                self.target + self.config.increase_step, "healthy_capacity_probe"
            )
        self._samples.clear()
        return EndpointConcurrencyDecision(
            target=self.target,
            changed=False,
            reason="capacity_hold",
        )


class EndpointAdmissionGate:
    """Non-preemptive endpoint-local admission control."""

    def __init__(self, *, initial_target: int) -> None:
        if initial_target < 1:
            raise ValueError("initial endpoint target must be positive")
        self._condition = threading.Condition()
        self._target = initial_target
        self._inflight = 0
        self._circuit_reason: str | None = None

    @property
    def target(self) -> int:
        with self._condition:
            return self._target

    @property
    def inflight(self) -> int:
        with self._condition:
            return self._inflight

    def acquire(self, timeout: float | None = None) -> None:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while self._inflight >= self._target:
                if self._circuit_reason is not None:
                    raise RuntimeError(
                        f"endpoint admission circuit open: {self._circuit_reason}"
                    )
                remaining = (
                    None if deadline is None else max(0.0, deadline - time.monotonic())
                )
                if remaining == 0.0 or not self._condition.wait(remaining):
                    if deadline is not None and time.monotonic() >= deadline:
                        raise TimeoutError("endpoint admission timed out")
            if self._circuit_reason is not None:
                raise RuntimeError(
                    f"endpoint admission circuit open: {self._circuit_reason}"
                )
            self._inflight += 1
            self._condition.notify_all()

    def release(self) -> None:
        with self._condition:
            if self._inflight < 1:
                raise RuntimeError("endpoint admission release without acquire")
            self._inflight -= 1
            self._condition.notify_all()

    def set_target(self, target: int) -> None:
        if target < 1:
            raise ValueError("endpoint target must be positive")
        with self._condition:
            self._target = target
            self._condition.notify_all()

    def open_circuit(self, reason: str) -> None:
        with self._condition:
            self._circuit_reason = reason or "unspecified endpoint failure"
            self._condition.notify_all()

    def wait_for_inflight(self, expected: int, *, timeout: float) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: self._inflight == expected,
                timeout=timeout,
            )


def fetch_vllm_endpoint_metrics(
    base_url: str, *, timeout_seconds: float = 3.0
) -> VllmEndpointMetrics:
    request = urllib.request.Request(
        f"{str(base_url).rstrip('/')}/metrics",
        headers={"Accept": "text/plain"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return parse_vllm_metrics(payload)


class AdaptiveEndpointConcurrencyController:
    """Lazily tune each endpoint from only that endpoint's vLLM metrics."""

    def __init__(
        self,
        *,
        endpoint_labels: Sequence[str],
        admission_gates: Sequence[EndpointAdmissionGate],
        config: AdaptiveEndpointConcurrencyConfig,
        metrics_reader: Callable[[str], VllmEndpointMetrics] | None = None,
        event_observer: Callable[[str, dict[str, Any]], None] | None = None,
        metrics_interval_seconds: float = 10.0,
    ) -> None:
        config.validate()
        labels = tuple(str(label).rstrip("/") for label in endpoint_labels)
        gates = tuple(admission_gates)
        if not labels or len(labels) != len(gates):
            raise ValueError("endpoint labels and admission gates must match")
        if metrics_interval_seconds <= 0:
            raise ValueError("metrics interval must be positive")
        self._endpoint_labels = labels
        self._gates = gates
        self._policies = tuple(
            AdaptiveEndpointConcurrencyPolicy(config) for _ in labels
        )
        self._metrics_reader = metrics_reader or fetch_vllm_endpoint_metrics
        self._event_observer = event_observer
        self._metrics_interval_seconds = float(metrics_interval_seconds)
        self._lifecycle_lock = threading.Lock()
        self._poll_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._closed = False

    @property
    def started(self) -> bool:
        with self._lifecycle_lock:
            return self._thread is not None

    def _event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_observer is not None:
            self._event_observer(event_type, payload)

    def ensure_started(self) -> None:
        with self._lifecycle_lock:
            if self._closed:
                raise RuntimeError("adaptive endpoint controller is closed")
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._run,
                name="adaptive-vllm-endpoint-controller",
                daemon=True,
            )
            self._thread.start()

    def poll_once(self) -> None:
        with self._poll_lock:
            for index, (label, gate, policy) in enumerate(
                zip(self._endpoint_labels, self._gates, self._policies)
            ):
                try:
                    metrics = self._metrics_reader(label)
                except Exception as exc:
                    self._event(
                        "adaptive_endpoint_metrics_error",
                        {
                            "backend_index": index,
                            "endpoint": label,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
                    continue
                decision = policy.observe(metrics)
                if not decision.changed:
                    continue
                previous_target = gate.target
                gate.set_target(decision.target)
                self._event(
                    "adaptive_endpoint_target_changed",
                    {
                        "backend_index": index,
                        "endpoint": label,
                        "previous_target": previous_target,
                        "target": decision.target,
                        "reason": decision.reason,
                        "running": metrics.running,
                        "waiting": metrics.waiting,
                        "kv_cache_usage": metrics.kv_cache_usage,
                        "preemptions_total": metrics.preemptions_total,
                        "generation_tokens_total": metrics.generation_tokens_total,
                    },
                )

    def open_endpoint_circuit(self, backend_index: int, reason: str) -> None:
        gate = self._gates[backend_index]
        gate.open_circuit(reason)
        self._event(
            "adaptive_endpoint_circuit_open",
            {
                "backend_index": backend_index,
                "endpoint": self._endpoint_labels[backend_index],
                "reason": reason,
                "inflight": gate.inflight,
            },
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            self.poll_once()
            if self._stop.wait(self._metrics_interval_seconds):
                break

    def close(self) -> None:
        with self._lifecycle_lock:
            self._closed = True
            thread = self._thread
            self._stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, self._metrics_interval_seconds + 1.0))


class QidAffinityRequestExecutorPool:
    """Spread independent steps while keeping matched branches co-located."""

    def __init__(
        self,
        executors: Sequence[Any],
        *,
        backend_labels: Sequence[str] | None = None,
        route_observer: Callable[[dict[str, Any]], None] | None = None,
        admission_gates: Sequence[EndpointAdmissionGate] | None = None,
        concurrency_controller: Any | None = None,
    ) -> None:
        if not executors:
            raise ValueError("at least one request executor is required")
        self._executors = tuple(executors)
        labels = tuple(backend_labels or ())
        if labels and len(labels) != len(self._executors):
            raise ValueError("backend labels must match request executors")
        self._backend_labels = labels or tuple(
            f"replica-{index}" for index in range(len(self._executors))
        )
        self._route_observer = route_observer
        gates = tuple(admission_gates or ())
        if gates and len(gates) != len(self._executors):
            raise ValueError("admission gates must match request executors")
        self._admission_gates = gates or None
        self._concurrency_controller = concurrency_controller

    @property
    def backend_count(self) -> int:
        return len(self._executors)

    def backend_index_for_qid_step(self, qid: int, step: int) -> int:
        return (int(qid) + int(step)) % self.backend_count

    def execute(self, task: Any) -> dict[str, Any]:
        backend_index = self.backend_index_for_qid_step(task.qid, task.step)
        if self._concurrency_controller is not None:
            self._concurrency_controller.ensure_started()
        gate = (
            self._admission_gates[backend_index]
            if self._admission_gates is not None
            else None
        )
        if gate is not None:
            gate.acquire()
        try:
            try:
                result = self._executors[backend_index].execute(task)
            except Exception as exc:
                if self._concurrency_controller is not None:
                    self._concurrency_controller.open_endpoint_circuit(
                        backend_index,
                        f"executor_exception:{type(exc).__name__}",
                    )
                raise
        finally:
            if gate is not None:
                gate.release()
        if result.get("new_post") is True and self._route_observer is not None:
            self._route_observer(
                {
                    "request_key": str(task.request_key),
                    "qid": int(task.qid),
                    "step_index": int(task.step),
                    "backend_index": backend_index,
                    "backend": self._backend_labels[backend_index],
                }
            )
        if result.get("infra_error") is True:
            if self._concurrency_controller is not None:
                self._concurrency_controller.open_endpoint_circuit(
                    backend_index, "request_result_infrastructure_error"
                )
            raise RolloutInfrastructureError(
                f"endpoint infrastructure failure on backend {backend_index}"
            )
        return result

    def post_json_for_qid_step(
        self,
        *,
        qid: int,
        step: int,
        path: str,
        body: dict[str, Any],
        request_id: str,
        timeout: float,
    ) -> tuple[int, str, dict[str, Any]]:
        """POST one frozen recovery request through the existing endpoint gate."""

        backend_index = self.backend_index_for_qid_step(qid, step)
        if self._concurrency_controller is not None:
            self._concurrency_controller.ensure_started()
        gate = (
            self._admission_gates[backend_index]
            if self._admission_gates is not None
            else None
        )
        if gate is not None:
            gate.acquire()
        try:
            executor = self._executors[backend_index]
            api = getattr(executor, "api", None)
            post_json = getattr(api, "post_json", None)
            if not callable(post_json):
                raise TypeError("request executor lacks a JSON transport")
            result = post_json(
                path,
                body,
                request_id=request_id,
                timeout=timeout,
            )
        except Exception as exc:
            if self._concurrency_controller is not None:
                self._concurrency_controller.open_endpoint_circuit(
                    backend_index,
                    f"recovery_exception:{type(exc).__name__}",
                )
            raise
        finally:
            if gate is not None:
                gate.release()
        if self._route_observer is not None:
            self._route_observer(
                {
                    "request_id": str(request_id),
                    "qid": int(qid),
                    "step_index": int(step),
                    "backend_index": backend_index,
                    "backend": self._backend_labels[backend_index],
                    "route_kind": "qwen_request_recovery_g1",
                }
            )
        return result

    def close(self) -> None:
        if self._concurrency_controller is not None:
            self._concurrency_controller.close()


def install_qid_affinity_request_pool(
    runtime: Any,
    runner: Any,
    *,
    base_urls: Sequence[str],
    item_workers: int,
    adaptive_config: AdaptiveEndpointConcurrencyConfig | None = None,
    metrics_reader: Callable[[str], VllmEndpointMetrics] | None = None,
    metrics_interval_seconds: float = 10.0,
) -> QidAffinityRequestExecutorPool:
    """Install a frozen dual-replica generation topology on one journal."""

    normalized_urls = tuple(str(url).rstrip("/") for url in base_urls)
    if len(normalized_urls) < 2:
        raise ValueError("qid-affinity routing requires at least two base URLs")
    if any(not url for url in normalized_urls):
        raise ValueError("base URLs must be non-empty")
    if adaptive_config is None:
        contract = {
            "version": "qid_step_mod_v2",
            "generation_base_urls": list(normalized_urls),
            "generation_route": "qid_plus_step_mod_backend_count",
            "affinity_fields": ["qid", "step"],
            "matched_branches_same_endpoint": True,
            "tokenize_base_url": normalized_urls[0],
            "global_item_workers": int(item_workers),
            "automatic_failover": False,
        }
    else:
        contract = {
            "version": "qid_step_mod_v3_endpoint_local",
            "generation_base_urls": list(normalized_urls),
            "generation_route": "qid_plus_step_mod_backend_count",
            "affinity_fields": ["qid", "step"],
            "matched_branches_same_endpoint": True,
            "tokenize_base_url": normalized_urls[0],
            "aggregate_generation_limit": None,
            "outer_item_scheduler_workers": int(item_workers),
            "automatic_failover": False,
        }
    meta_key = "adaptive_api_pool_contract_v1"
    previous = runner.journal.get_meta(meta_key)
    runner.journal.set_meta(meta_key, contract, require_same=True)
    if previous is None:
        runner.journal.event("api_pool_cutover", contract)

    executors = [
        runtime.RequestExecutor(runner.journal, runtime.HttpJsonApi(url))
        for url in normalized_urls
    ]
    gates: list[EndpointAdmissionGate] | None = None
    controller: AdaptiveEndpointConcurrencyController | None = None
    if adaptive_config is not None:
        adaptive_config.validate()
        adaptive_contract = {
            "version": "endpoint_local_v1",
            "generation_base_urls": list(normalized_urls),
            "work_unit": "provider_request_from_independent_qid_step",
            "aggregate_generation_limit": None,
            "item_workers_role": "outer_item_scheduler_only",
            "initial_inflight_per_endpoint": adaptive_config.initial_inflight,
            "min_inflight_per_endpoint": adaptive_config.min_inflight,
            "max_inflight_per_endpoint": adaptive_config.max_inflight,
            "increase_step": adaptive_config.increase_step,
            "samples_per_window": adaptive_config.samples_per_window,
            "low_kv_threshold": adaptive_config.low_kv_threshold,
            "soft_kv_threshold": adaptive_config.soft_kv_threshold,
            "hard_kv_threshold": adaptive_config.hard_kv_threshold,
            "metrics_interval_seconds": float(metrics_interval_seconds),
            "signals": [
                "vllm:kv_cache_usage_perc",
                "vllm:num_requests_running",
                "vllm:num_requests_waiting",
                "vllm:num_preemptions_total",
                "vllm:generation_tokens_total",
            ],
            "lazy_metrics_start": True,
            "metrics_fetch_during_prepare": False,
            "reserve_after_admission": True,
            "nonpreemptive_downscale": True,
            "automatic_failover": False,
        }
        adaptive_meta_key = "adaptive_endpoint_concurrency_contract_v1"
        previous_adaptive = runner.journal.get_meta(adaptive_meta_key)
        runner.journal.set_meta(
            adaptive_meta_key,
            adaptive_contract,
            require_same=True,
        )
        if previous_adaptive is None:
            runner.journal.event(
                "adaptive_endpoint_concurrency_installed", adaptive_contract
            )
        gates = [
            EndpointAdmissionGate(
                initial_target=adaptive_config.initial_inflight
            )
            for _ in normalized_urls
        ]
        controller = AdaptiveEndpointConcurrencyController(
            endpoint_labels=normalized_urls,
            admission_gates=gates,
            config=adaptive_config,
            metrics_reader=metrics_reader,
            event_observer=lambda event_type, payload: runner.journal.event(
                event_type, payload
            ),
            metrics_interval_seconds=metrics_interval_seconds,
        )
    pool = QidAffinityRequestExecutorPool(
        executors,
        backend_labels=normalized_urls,
        route_observer=lambda payload: runner.journal.event(
            "generation_route", payload
        ),
        admission_gates=gates,
        concurrency_controller=controller,
    )
    runner.executor = pool
    return pool


class _AdaptiveRunLock:
    def __init__(self, handle: Any, *, windows: bool) -> None:
        self._handle = handle
        self._windows = windows
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._handle.seek(0)
            if self._windows:
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._closed = True
            self._handle.close()

    def __enter__(self) -> _AdaptiveRunLock:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


def acquire_adaptive_run_lock(path: str | Path) -> _AdaptiveRunLock:
    """Acquire a real non-blocking single-runner lock on Windows and POSIX."""

    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    windows = os.name == "nt"
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        if windows:
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError) as exc:
        handle.close()
        raise RuntimeError(
            "another adaptive Qwen PNS runner already holds the run lock"
        ) from exc
    return _AdaptiveRunLock(handle, windows=windows)


@dataclass
class ExecutionAccounting:
    """Separate logical requests, journal reuse, reservations, and real POSTs."""

    requested_slots: int = 0
    reused_slots: int = 0
    registered_slots: int = 0
    actual_generation_posts: int = 0
    infrastructure_errors: int = 0

    def begin(self) -> None:
        self.requested_slots += 1

    def fail_before_registration(self) -> None:
        self.infrastructure_errors += 1

    def finish(
        self,
        *,
        existed: bool,
        row: dict[str, Any] | None,
        result: dict[str, Any] | None,
        raised: bool = False,
    ) -> None:
        if existed:
            self.reused_slots += 1
        elif row is not None:
            self.registered_slots += 1
        if result is not None:
            self.actual_generation_posts += int(bool(result.get("new_post")))
            self.infrastructure_errors += int(bool(result.get("infra_error")))
            return
        posted = bool(row and row.get("posting_at") is not None)
        self.actual_generation_posts += int(not existed and posted)
        self.infrastructure_errors += int(raised)


class Batch56AdaptiveAdapter:
    """Run the adaptive policy through the frozen batch56 Qwen runtime.

    The adapter intentionally reuses batch56's request bodies, response parser,
    reserve-before-POST journal, prompt cache, tokenizer, replacement prompt,
    and local path auditor.  Only orchestration changes: valid trials can grow
    from two to five, invalid trials consume separate bounded raw slots, and a
    deterministic 3:2 result is terminal at the five-valid horizon.
    """

    def __init__(
        self,
        *,
        runtime: Any,
        runner: Any,
        config: AdaptiveRolloutConfig | None = None,
        item_workers: int = 16,
        step_workers_per_item: int = 1,
        journal_reference: str | None = None,
        dataset_pns: DatasetPnsExecutionConfig | None = None,
        semantic_judge: Any | None = None,
        judge_ledger: SemanticJudgeLedger | None = None,
        request_recovery: QwenRequestRecovery | None = None,
        recovery_amendment: AdaptiveRolloutRecoveryAmendment | None = None,
    ) -> None:
        self.runtime = runtime
        self.runner = runner
        self.config = config or AdaptiveRolloutConfig()
        self.config.validate()
        if item_workers < 0:
            raise ValueError("item_workers must be nonnegative")
        if step_workers_per_item < 0:
            raise ValueError("step_workers_per_item must be nonnegative")
        self.item_workers = item_workers
        self.step_workers_per_item = step_workers_per_item
        if dataset_pns is not None:
            dataset_pns.validate()
        self.dataset_pns = dataset_pns
        self._prepared_dataset_items: dict[int, PreparedDatasetPnsItem] = {}
        self.semantic_judge = semantic_judge
        self.judge_ledger = judge_ledger
        self.request_recovery = request_recovery
        if recovery_amendment is not None:
            recovery_amendment.validate()
            if self.config.max_raw_attempts_per_lineage != (
                recovery_amendment.base_max_raw_attempts_per_lineage
            ):
                raise ValueError(
                    "recovery amendment requires the frozen max-five base config"
                )
            if Path(runner.journal.path).resolve() != Path(
                recovery_amendment.target_journal
            ).resolve():
                raise ValueError(
                    "recovery amendment target journal differs from runner journal"
                )
        self.recovery_amendment = recovery_amendment
        reference = journal_reference or Path(runner.journal.path).name
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("journal_reference must be a nonempty string")
        self.journal_reference = reference
        self._journal_reference_explicit = journal_reference is not None
        self.seeds = AdaptiveSeedSchedule()
        self._initialized = False
        _validate_runtime(runtime)

    def initialize(self) -> None:
        """Create an adaptive journal contract without invoking model/token APIs."""

        if self._initialized:
            return
        if self.request_recovery is not None:
            self.request_recovery.verify_source()
        snapshot = Path(self.runner.run_dir) / "batch_input_56_adaptive.jsonl"
        source = Path(self.runner.input_path).read_bytes()
        if snapshot.exists():
            if snapshot.read_bytes() != source:
                raise RuntimeError(
                    "adaptive run input differs from its frozen snapshot"
                )
        else:
            with snapshot.open("xb") as handle:
                handle.write(source)

        if self.dataset_pns is not None:
            prepared_items: dict[int, PreparedDatasetPnsItem] = {}
            for item in self.runner.items:
                qid = int(item["question_id"])
                prepared_items[qid] = prepare_dataset_pns_item(
                    item,
                    dataset_name=self.dataset_pns.dataset_name,
                    canonical_context_authorization=(
                        self.dataset_pns.canonical_context_authorization
                    ),
                    explicit_fallback=(
                        self._source_preserving_fallback
                        if self.dataset_pns.allow_explicit_fallback
                        else None
                    ),
                    fallback_name=self.dataset_pns.fallback_policy,
                )
            self._prepared_dataset_items = prepared_items

        contract = {
            "adapter_version": ADAPTER_VERSION,
            "policy_version": POLICY_VERSION,
            "model": getattr(self.runtime, "MODEL", None),
            "max_model_len": getattr(self.runtime, "MAX_MODEL_LEN", None),
            "suffix_requested_max_tokens": getattr(
                self.runtime, "SUFFIX_REQUESTED_MAX_TOKENS", None
            ),
            "replacement_requested_max_tokens": getattr(
                self.runtime, "REPLACEMENT_REQUESTED_MAX_TOKENS", None
            ),
            "sampling": (
                self.runtime.sampling_fields()
                if callable(getattr(self.runtime, "sampling_fields", None))
                else None
            ),
            "initial_valid_rounds": self.config.initial_valid_rounds,
            "max_valid_rounds": self.config.max_valid_rounds,
            "max_raw_attempts_per_lineage": self.config.max_raw_attempts_per_lineage,
            # Keep the copied phase56 base contract byte-for-byte compatible.
            # The isolated r6/r7 seed band is recorded only in the amendment.
            "seed_schedule": {
                "base_seed": self.seeds.base_seed,
                "step_radix": self.seeds.step_radix,
                "branch_radix": self.seeds.branch_radix,
                "legacy_rollout_radix": self.seeds.legacy_rollout_radix,
                "extension_base_seed": self.seeds.extension_base_seed,
                "extension_rollout_slots": self.seeds.extension_rollout_slots,
            },
            "decision_rule": (
                "KEEP correct > DELETE correct at horizon "
                f"{self.config.max_valid_rounds}; "
                f"{self.config.max_valid_rounds // 2 + 1}:"
                f"{self.config.max_valid_rounds // 2} accepted"
            ),
            "invalid_trials_vote": False,
            "selection": "complete Qwen tokens, chars, candidate id; audited fail-closed",
            "item_workers": self.item_workers or "all_frozen_items",
            "journal_reference": self.journal_reference,
            "dataset_pns_protocol_version": (
                self.dataset_pns.protocol_version
                if self.dataset_pns is not None
                else None
            ),
        }
        journal = self.runner.journal
        journal.set_meta("adaptive_rollout_contract", contract, require_same=True)
        if self.recovery_amendment is not None:
            amendment_contract = self.recovery_amendment.contract()
            amendment_contract["seed_schedule_extension"] = {
                "recovery_extension_base_seed": (
                    self.seeds.recovery_extension_base_seed
                ),
                "recovery_extension_rollout_slots": (
                    self.seeds.recovery_extension_rollout_slots
                ),
                "preserves_raw_slots": list(range(6)),
                "adds_raw_slots": list(
                    self.recovery_amendment.new_raw_slots_only
                ),
            }
            journal.set_meta(
                RECOVERY_AMENDMENT_CONTRACT_KEY,
                amendment_contract,
                require_same=True,
            )
        journal.set_meta(
            "adaptive_step_parallelism_contract_v1",
            {
                "version": "independent_steps_v1",
                "step_workers_per_item": (
                    self.step_workers_per_item or "all_eligible_steps"
                ),
                "global_generation_limit": None,
            },
            require_same=True,
        )
        if self.dataset_pns is not None:
            prepared = [
                self._prepared_dataset_items[int(item["question_id"])]
                for item in self.runner.items
            ]
            source_counts = Counter(
                item.segmentation_source for item in prepared
            )
            semantic_reference_counts = Counter(
                item.semantic_reference_source for item in prepared
            )
            journal.set_meta(
                DATASET_PNS_CONTRACT_KEY,
                {
                    "version": DATASET_PNS_PROTOCOL_VERSION,
                    "dataset_name": self.dataset_pns.dataset_name,
                    "dataset_scope": "CLADDER-only",
                    "canonical_context_authorization": (
                        self.dataset_pns.canonical_context_authorization
                    ),
                    "planner_visible": False,
                    "test_prompt_visible": False,
                    "parent_source": "parent_reasoning",
                    "segment_source": "segments",
                    "boundary_authority": "frozen_qwen_parent_segments",
                    "source_preserving": True,
                    "programmatic_role": (
                        "semantic_reference_alignment_anchor_only"
                    ),
                    "one_to_one_required": False,
                    "same_path_required": False,
                    "canonical_author_text_generation_visible": False,
                    "canonical_author_text_judge_visible": True,
                    "canonical_author_text_judge_scope": (
                        "advisory_non_answer_steps_only"
                    ),
                    "fallback_policy": self.dataset_pns.fallback_policy,
                    "fallback_count": sum(item.used_fallback for item in prepared),
                    "segmentation_sources": dict(sorted(source_counts.items())),
                    "semantic_reference_sources": dict(
                        sorted(semantic_reference_counts.items())
                    ),
                    "sample_ids": [int(item.question_id) for item in prepared],
                    "items": [
                        {
                            "question_id": int(item.question_id),
                            "config_id": item.config_id,
                            "segmentation_source": item.segmentation_source,
                            "parent_source": item.parent_source,
                            "segment_source": item.segment_source,
                            "semantic_reference_source": (
                                item.semantic_reference_source
                            ),
                            "fallback_used": item.used_fallback,
                            "fallback_policy": item.fallback_policy,
                            "semantic_reference_fields": list(
                                item.semantic_reference_fields
                            ),
                            "qwen_segment_indexes": [
                                segment.step_index for segment in item.segments
                            ],
                            "eligible_step_indexes": list(
                                item.eligible_step_indexes
                            ),
                        }
                        for item in prepared
                    ],
                },
                require_same=True,
            )
        journal.register_items(self.runner.items)
        if self.allows_unknown_request_reclassification():
            recovery = journal.recover_unknown()
            if any(recovery.values()):
                journal.event("adaptive_resume_recovery", recovery)
        recover_responses = getattr(self.runner, "_recover_response_received", None)
        if callable(recover_responses):
            recover_responses()
        self._initialized = True

    def allows_unknown_request_reclassification(self) -> bool:
        """Keep copied posting rows intact for read-only G1 materialization."""

        return self.request_recovery is None and self.recovery_amendment is None

    def run(self, *, output_path: str | Path) -> list[dict[str, Any]]:
        """Run/resume all items and create or verify one immutable JSONL artifact."""

        if self.dataset_pns is not None and (
            self.semantic_judge is None or self.judge_ledger is None
        ):
            raise RuntimeError(
                "dataset PNS execution requires the DeepSeek semantic Judge and ledger"
            )
        output = Path(output_path)
        reference = Path(self.journal_reference)
        referenced_journal = (
            reference if reference.is_absolute() else output.parent / reference
        ).resolve()
        actual_journal = Path(self.runner.journal.path).resolve()
        if referenced_journal != actual_journal:
            qualifier = "explicit" if self._journal_reference_explicit else "default"
            raise ValueError(
                f"{qualifier} journal reference does not resolve from the artifact directory; "
                "keep the artifact in run-dir or pass a resolvable journal_reference"
        )
        self.prepare_execution()
        items = self._execution_items()
        effective_item_workers = self.item_workers or len(items)
        if effective_item_workers == 1:
            artifacts = [self.run_item(item) for item in items]
        else:
            by_qid: dict[int, dict[str, Any]] = {}
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=effective_item_workers
            ) as pool:
                futures = {
                    pool.submit(self.run_item, item): int(item["question_id"])
                    for item in items
                }
                for future in concurrent.futures.as_completed(futures):
                    qid = futures[future]
                    by_qid[qid] = future.result()
            artifacts = [by_qid[int(item["question_id"])] for item in items]
        if self.recovery_amendment is not None:
            completed_by_qid = {
                int(item["question_id"]): self._completed_artifact(
                    int(item["question_id"])
                )
                for item in self.runner.items
            }
            missing = sorted(
                qid for qid, artifact in completed_by_qid.items() if artifact is None
            )
            if missing:
                raise RuntimeError(
                    f"max7 recovery did not materialize exact56; pending qids {missing}"
                )
            artifacts = [
                completed_by_qid[int(item["question_id"])]
                for item in self.runner.items
            ]
        self._write_or_verify_artifacts(output, artifacts)
        return artifacts

    def prepare_execution(self) -> None:
        """Prepare all frozen prompts before a staged first-item execution."""

        self.initialize()
        if self.recovery_amendment is not None:
            self.recovery_amendment.verify_execution_gate(self.runner.journal)
        items = self._execution_items()
        if self.dataset_pns is None:
            self.runner.ensure_wave_prompts(items)
        else:
            self._ensure_dataset_wave_prompts(items)

    def _execution_items(self) -> list[dict[str, Any]]:
        if self.recovery_amendment is None:
            return list(self.runner.items)
        target = set(self.recovery_amendment.target_qids)
        selected = [
            item
            for item in self.runner.items
            if int(item["question_id"]) in target
        ]
        selected_qids = {int(item["question_id"]) for item in selected}
        if selected_qids != target or len(selected) != len(target):
            raise RuntimeError("max7 recovery target qids differ from the frozen batch")
        return selected

    def _source_preserving_fallback(
        self, item: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return [
            {
                "step_index": int(segment.step_index),
                "source_field": f"qwen_parent_segment_{int(segment.step_index)}",
                "text": str(segment.text),
                "answer_exposed": bool(segment.answer_exposed_prefix),
            }
            for segment in self.runtime.item_segments(item)
        ]

    def _runtime_segments(
        self, prepared: PreparedDatasetPnsItem
    ) -> list[Any]:
        segment_type = getattr(self.runtime, "Segment", None)
        if segment_type is None:
            raise TypeError("dataset PNS runtime is missing Segment")
        return [
            segment_type(
                segment.step_index,
                segment.char_start,
                segment.char_end,
                segment.text,
                segment.answer_exposed_prefix,
            )
            for segment in prepared.segments
        ]

    def _ensure_dataset_wave_prompts(
        self, wave: Sequence[dict[str, Any]]
    ) -> None:
        make_branches = getattr(self.runtime, "make_keep_delete_branches", None)
        if not callable(make_branches):
            raise TypeError(
                "dataset PNS runtime is missing make_keep_delete_branches"
            )
        encoding_jobs: list[tuple[int, str]] = []
        specs: list[Any] = []
        for item in wave:
            qid = int(item["question_id"])
            prepared = self._prepared_dataset_items[qid]
            segments = self._runtime_segments(prepared)
            encoding_jobs.append((qid, prepared.parent_reasoning))
            for branch in make_branches(prepared.parent_reasoning, segments):
                specs.append(
                    self.runtime.PromptSpec(
                        prompt_key=(
                            f"q{qid}-s{int(branch.step_index):03d}-"
                            f"{branch.intervention}"
                        ),
                        qid=qid,
                        step=int(branch.step_index),
                        branch=str(branch.intervention),
                        endpoint="/v1/completions",
                        frozen_prefix=str(branch.prefix),
                        serialized_prompt=(
                            str(item["base_serialized_prompt"])
                            + str(branch.prefix)
                        ),
                    )
                )

        def encode_parent(job: tuple[int, str]) -> None:
            qid, text = job
            encoding = self.runtime.ensure_encoding(
                self.runner.journal,
                self.runner.api,
                key=f"q{qid}-parent-frozen-qwen-v2",
                qid=qid,
                purpose="dataset_frozen_qwen_parent_reasoning_v2",
                source_key=None,
                text=text,
            )
            self.runner.journal.set_parent_encoding(qid, encoding)

        parallel_map = getattr(self.runtime, "parallel_map", None)
        if callable(parallel_map):
            parallel_map(
                encode_parent,
                encoding_jobs,
                min(16, max(1, len(encoding_jobs))),
                label="frozen_qwen_parent_tokenization",
            )
            parallel_map(
                lambda spec: self.runtime.ensure_prompt(
                    self.runner.journal, self.runner.api, spec
                ),
                specs,
                min(16, max(1, len(specs))),
                label="frozen_qwen_keep_delete_prompt_tokenization",
            )
            return
        for job in encoding_jobs:
            encode_parent(job)
        for spec in specs:
            self.runtime.ensure_prompt(self.runner.journal, self.runner.api, spec)

    @staticmethod
    def _semantic_sample(item: dict[str, Any]) -> dict[str, Any]:
        audit_reference = item.get("audit_reference")
        offline = (
            audit_reference.get("offline_oracle")
            if isinstance(audit_reference, dict)
            else None
        )
        offline = offline if isinstance(offline, dict) else {}
        source_meta = offline.get("source_meta")
        source_meta = source_meta if isinstance(source_meta, dict) else {}
        sample = {
            "question_id": int(item["question_id"]),
            "given_info": str(
                offline.get("source_given_info") or item.get("given_info") or ""
            ),
            "question": str(
                offline.get("source_question") or item.get("question") or ""
            ),
            "meta": {
                **source_meta,
                "query_type": str(item.get("query_type") or ""),
            },
        }
        canonical = CladderAdapter().get_pns_canonical_steps(item)
        if canonical is not None:
            non_answer_steps = [
                {
                    "source_field": step.source_field,
                    "text": step.text,
                }
                for step in canonical.steps
                if not step.answer_exposed and step.source_field != "end"
            ]
            if non_answer_steps:
                sample["semantic_reference"] = {
                    "source": canonical.source,
                    "role": "advisory_alignment_anchor_only",
                    "one_to_one_required": False,
                    "same_path_required": False,
                    "steps": non_answer_steps,
                }
        return sample

    @staticmethod
    def _qwen_generation_prompt_item(item: dict[str, Any]) -> dict[str, Any]:
        """Expose only frozen Qwen inputs to runtime prompt builders.

        In particular, the CLADDER author/programmatic reasoning lives under
        ``reasoning`` or ``audit_reference`` and must never be available to a
        Qwen generation-prompt builder.
        """

        return {
            key: item[key]
            for key in (
                "question_id",
                "query_type",
                "messages",
                "base_serialized_prompt",
                "parent_reasoning",
                "segments",
            )
            if key in item
        }

    @staticmethod
    def _safe_judge_metadata(result: dict[str, Any]) -> dict[str, Any]:
        allowed = (
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
            "usage",
            "latency_ms",
            "verdict",
            "error",
        )
        return {key: result.get(key) for key in allowed if key in result}

    def _semantic_judge_call(
        self,
        *,
        evidence_id: str,
        identity: dict[str, Any],
        invoke: Callable[[], dict[str, Any]] | None,
        noncall_status: str | None = None,
    ) -> dict[str, Any]:
        if self.semantic_judge is None or self.judge_ledger is None:
            raise RuntimeError("semantic Judge is not configured")
        previous = self.judge_ledger.reserve(evidence_id, identity)
        if previous is not None:
            return {
                **previous,
                "evidence_id": evidence_id,
                "ledger_reused": True,
            }
        if invoke is None:
            status = str(noncall_status or "not_called")
            transport = getattr(self.semantic_judge, "transport", None)
            build_noncall = getattr(transport, "noncall_result", None)
            if callable(build_noncall):
                result = self._safe_judge_metadata(
                    build_noncall(status, error=status)
                )
            else:
                result = {
                    "provider": "deepseek",
                    "endpoint_type": "chat.completions",
                    "requested_model": "deepseek-v4-pro",
                    "resolved_model": "deepseek-v4-pro",
                    "response_model": None,
                    "thinking_type": "enabled",
                    "reasoning_effort": "max",
                    "status": status,
                    "parse_status": "not_parsed",
                    "decision": "rejected",
                    "accepted": False,
                    "provider_call_count": 0,
                    "retry_count": 0,
                    "fallback_allowed": False,
                    "fallback_used": False,
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    },
                    "latency_ms": None,
                    "verdict": None,
                    "error": status,
                }
        else:
            result = self._safe_judge_metadata(invoke())
        self.judge_ledger.complete(evidence_id, result)
        return {
            **result,
            "evidence_id": evidence_id,
            "ledger_reused": False,
        }

    def _judge_chain(
        self,
        *,
        item: dict[str, Any],
        evidence_id: str,
        identity: dict[str, Any],
        reasoning: str,
        parsed_answer: str | None,
        syntactically_valid: bool,
    ) -> dict[str, Any]:
        if not syntactically_valid:
            return self._semantic_judge_call(
                evidence_id=evidence_id,
                identity=identity,
                invoke=None,
                noncall_status="not_called_invalid_generation",
            )
        sample = self._semantic_sample(item)
        return self._semantic_judge_call(
            evidence_id=evidence_id,
            identity=identity,
            invoke=lambda: self.semantic_judge.judge_chain(
                sample,
                {
                    "steps": [{"step_id": "complete_chain", "text": reasoning}],
                    "final_answer": parsed_answer,
                },
                user_id=evidence_id,
            ),
        )

    def journal_lifecycle_accounting(self) -> dict[str, Any]:
        """Return stable journal-lifetime counts, including all resumed invocations."""

        rows = self.runner.journal.request_rows()
        states = Counter(str(row.get("state") or "missing") for row in rows)
        return {
            "registered_slots": len(rows),
            "actual_generation_posts": sum(
                row.get("posting_at") is not None for row in rows
            ),
            "responses_received": sum(
                row.get("response_received_at") is not None for row in rows
            ),
            "state_counts": dict(sorted(states.items())),
        }

    def run_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Run one registered item, or return its exact completed adaptive result."""

        qid = int(item["question_id"])
        completed = self._completed_artifact(qid)
        if completed is not None:
            return completed
        effective_rollout_config = (
            self.recovery_amendment.config_for_qid(self.config, qid)
            if self.recovery_amendment is not None
            else self.config
        )

        parent_tokens = self._parent_token_count(qid)
        prepared = self._prepared_dataset_items.get(qid)
        if prepared is None:
            effective_item = item
            parent_reasoning = str(item["parent_reasoning"])
            parent_audit = self.runtime.local_path_audit(
                item,
                candidate_key="parent_original",
                reasoning=parent_reasoning,
                final_content=item["parent_final_content"],
                provenance_ok=True,
            )
            segments = {
                int(segment.step_index): segment
                for segment in self.runtime.item_segments(item)
            }
            eligible_steps = [
                step
                for step, segment in segments.items()
                if not bool(segment.answer_exposed_prefix)
            ]
            if len(eligible_steps) != int(item["safe_step_count"]):
                raise RuntimeError(f"safe step count changed for q{qid}")
            full_pns_asset = {"journal": self.journal_reference, "qid": qid}
        else:
            parent_reasoning = prepared.parent_reasoning
            effective_item = {**item, "parent_reasoning": parent_reasoning}
            parent_audit = {
                "candidate_key": "parent_dataset_frozen_qwen",
                "passed": True,
                "coherent": True,
                "error": None,
                "evidence": {
                    "auditor": "dataset_frozen_qwen_source_validation",
                    "external_model_calls": 0,
                    "dataset_config_id": prepared.config_id,
                    "segmentation_source": prepared.segmentation_source,
                    "parent_source": prepared.parent_source,
                    "segment_source": prepared.segment_source,
                    "semantic_reference_source": (
                        prepared.semantic_reference_source
                    ),
                    "fallback_used": prepared.used_fallback,
                },
            }
            segments = {
                int(segment.step_index): segment
                for segment in self._runtime_segments(prepared)
            }
            eligible_steps = list(prepared.eligible_step_indexes)
            full_pns_asset = {
                "journal": self.journal_reference,
                "qid": qid,
                "dataset_pns_config_id": prepared.config_id,
                "segmentation_source": prepared.segmentation_source,
                "parent_source": prepared.parent_source,
                "segment_source": prepared.segment_source,
                "semantic_reference_source": prepared.semantic_reference_source,
                "fallback_used": prepared.used_fallback,
            }
        if (
            parent_audit.get("passed") is not True
            or parent_audit.get("coherent", True) is False
        ):
            raise RuntimeError(f"parent path audit failed q{qid}")
        self.runner.journal.store_audit(qid, "parent_original", 0, parent_audit)

        parent = QwenPnsCotParent(
            question_id=qid,
            query_type=str(item["query_type"]),
            original_cot=parent_reasoning,
            parent_answer=str(item["parent_answer"]),
            original_qwen_tokens=parent_tokens,
            parent_audit=parent_audit,
        )

        accounting_by_step = {
            step: ExecutionAccounting() for step in eligible_steps
        }
        vote_history: dict[int, dict[str, list[RolloutTrial]]] = {
            step: {"keep": [], "delete": []} for step in eligible_steps
        }

        def generate(
            step_index: int,
            lineage: str,
            _valid_round: int,
            raw_attempt: int,
            replacement_text: str | None,
        ) -> RolloutTrial:
            trial = self._generate_trial(
                item=effective_item,
                parent=parent,
                step_index=step_index,
                lineage=lineage,
                raw_attempt=raw_attempt,
                replacement_text=replacement_text,
                accounting=accounting_by_step[step_index],
            )
            if lineage in {"keep", "delete"}:
                vote_history[step_index][lineage].append(trial)
            return trial

        def generate_replacement(step_index: int) -> ReplacementGeneration:
            history = vote_history[step_index]
            return self._generate_replacement(
                item=effective_item,
                segment=segments[step_index],
                keep_correct=sum(trial.correct is True for trial in history["keep"]),
                delete_correct=sum(
                    trial.correct is True for trial in history["delete"]
                ),
                accounting=accounting_by_step[step_index],
            )

        result = generate_optimized_pnscot(
            parent,
            eligible_step_indexes=eligible_steps,
            generate=generate,
            generate_replacement=generate_replacement,
            full_pns_asset=full_pns_asset,
            config=effective_rollout_config,
            step_workers=self.step_workers_per_item or len(eligible_steps),
        )
        accounting = ExecutionAccounting(
            requested_slots=sum(
                value.requested_slots for value in accounting_by_step.values()
            ),
            reused_slots=sum(
                value.reused_slots for value in accounting_by_step.values()
            ),
            registered_slots=sum(
                value.registered_slots for value in accounting_by_step.values()
            ),
            actual_generation_posts=sum(
                value.actual_generation_posts for value in accounting_by_step.values()
            ),
            infrastructure_errors=sum(
                value.infrastructure_errors for value in accounting_by_step.values()
            ),
        )
        self._persist_replacement_decisions(effective_item, segments, result)
        artifact = result.artifact
        if self.recovery_amendment is not None:
            artifact["rollout_recovery_amendment"] = {
                "schema_version": RECOVERY_AMENDMENT_CONTRACT_KEY,
                "contract_id": self.recovery_amendment.contract_id,
                "targeted": qid in self.recovery_amendment.target_qids,
                "base_max_raw_attempts_per_lineage": (
                    self.recovery_amendment.base_max_raw_attempts_per_lineage
                ),
                "effective_max_raw_attempts_per_lineage": (
                    effective_rollout_config.max_raw_attempts_per_lineage
                ),
                "new_raw_slots_only": list(
                    self.recovery_amendment.new_raw_slots_only
                ),
                "source_journal_mutated": False,
                "workspace_manifest": str(
                    Path(self.recovery_amendment.workspace_manifest).resolve()
                ),
            }
        if self.dataset_pns is not None:
            original_tokens = artifact.get("original_qwen_tokens")
            final_tokens = artifact.get("final_qwen_tokens")
            if not (
                artifact.get("optimized") is True
                and artifact.get("fallback") is False
                and isinstance(original_tokens, int)
                and isinstance(final_tokens, int)
                and final_tokens < original_tokens
            ):
                raise RuntimeError(
                    f"formal q{qid} must materialize an optimized shorter PNS-CoT"
                )
        artifact["adaptive_rollout"]["completion_invocation_accounting"] = asdict(
            accounting
        )
        if self.semantic_judge is not None and self.judge_ledger is not None:
            selected_trial = (
                result.selected_trial.trial
                if result.selected_trial is not None
                else None
            )
            final_answer = (
                selected_trial.predicted_answer
                if selected_trial is not None
                else parent.parent_answer
            )
            final_source_key = (
                artifact.get("selected_request_key") or "dataset_parent_fallback"
            )
            final_evidence_id = f"materialization:q{qid}:{final_source_key}"
            final_judge = self._judge_chain(
                item=effective_item,
                evidence_id=final_evidence_id,
                identity={
                    "kind": "accepted_materialization",
                    "qid": qid,
                    "request_key": str(final_source_key),
                    "optimized": artifact.get("optimized") is True,
                },
                reasoning=str(artifact["final_cot"]),
                parsed_answer=final_answer,
                syntactically_valid=True,
            )
            final_answer_validation = CladderAdapter().validate_pns_answer(
                {**effective_item, "answer": effective_item.get("gold_answer")},
                final_answer,
            )
            if final_judge.get("accepted") is not True:
                raise RuntimeError(
                    f"accepted materialization Judge failed closed for q{qid}: "
                    f"{final_judge.get('status')}"
                )
            if final_answer_validation.valid is not True:
                raise RuntimeError(
                    f"accepted materialization deterministic answer failed q{qid}"
                )
            artifact["judge_acceptance"] = final_judge
            artifact["deterministic_answer_validation"] = asdict(
                final_answer_validation
            )
            artifact["full_pns_asset"]["judge_ledger"] = str(
                self.judge_ledger.path.name
            )
        record = {
            "schema_version": 1,
            "result_type": ADAPTER_VERSION,
            "policy_version": POLICY_VERSION,
            "question_id": qid,
            "artifact": artifact,
        }
        _validate_pnscot_artifact(artifact)
        self.runner.journal.complete_item(qid, record)
        return artifact

    def _generate_trial(
        self,
        *,
        item: dict[str, Any],
        parent: QwenPnsCotParent,
        step_index: int,
        lineage: str,
        raw_attempt: int,
        replacement_text: str | None,
        accounting: ExecutionAccounting,
    ) -> RolloutTrial:
        qid = int(item["question_id"])
        accounting.begin()
        execution_started = False
        try:
            if lineage not in {"keep", "delete", "replace"}:
                raise ValueError(f"unsupported lineage: {lineage}")
            if lineage == "replace" and not (
                replacement_text and replacement_text.strip()
            ):
                raise ValueError(
                    "REPLACE continuation requires frozen replacement text"
                )
            if lineage != "replace" and replacement_text is not None:
                raise ValueError("replacement text must not enter KEEP/DELETE requests")
            prompt_key = f"q{qid}-s{step_index:03d}-{lineage}"
            prompt = self.runner.journal.get_prompt(prompt_key)
            if prompt is None:
                raise RuntimeError(f"missing frozen prompt {prompt_key}")
            task = self.runtime.task_from_prompt(
                prompt,
                qid=qid,
                step=step_index,
                branch=lineage,
                rollout=raw_attempt,
                gold=item["gold_answer"],
                seeds=self.seeds,
            )
            execution_started = True
            row = self._execute_task(task, accounting)
        except Exception:
            if not execution_started:
                accounting.fail_before_registration()
            raise
        if row is None:
            return RolloutTrial(
                valid_for_vote=False,
                candidate_id=f"{lineage}_s{step_index}:t{raw_attempt}",
                request_key=task.request_key,
                error="request row missing after execution",
            )
        try:
            self.runtime.assert_response_assets(row)
        except RuntimeError as exc:
            return RolloutTrial(
                valid_for_vote=False,
                candidate_id=f"{lineage}_s{step_index}:t{raw_attempt}",
                request_key=task.request_key,
                error=f"response_asset_invalid: {exc}",
                metadata={"journal_state": row.get("state")},
            )

        encoding_error: str | None = None
        if (
            row.get("complete_chain") is not None
            and row.get("chain_token_count") is None
        ):
            try:
                encoding_journal = (
                    self.request_recovery
                    if row.get("_request_recovery") is not None
                    else self.runner.journal
                )
                if encoding_journal is None:
                    raise RuntimeError("recovered chain lacks its g1 sidecar")
                encoding = self.runtime.ensure_encoding(
                    encoding_journal,
                    self.runner.api,
                    key=f"chain-{row['request_key']}",
                    qid=qid,
                    purpose="complete_candidate_chain",
                    source_key=row["request_key"],
                    text=row["complete_chain"],
                )
                if row.get("_request_recovery") is not None:
                    row = {
                        **row,
                        "chain_token_count": int(encoding["token_count"]),
                        "chain_token_ids_json": encoding.get("token_ids_json"),
                    }
                else:
                    self.runner.journal.update_chain_encoding(
                        row["request_key"], encoding
                    )
                    row = self.runner.journal.request_row(row["request_key"])
                    assert row is not None
            except (
                Exception
            ) as exc:  # tokenization failure blocks export, not the answer vote
                encoding_error = f"{type(exc).__name__}: {exc}"

        syntactically_valid = bool(row.get("valid") is True or row.get("valid") == 1)
        parsed_answer = (
            str(row.get("parsed_answer"))
            if row.get("parsed_answer") is not None
            else None
        )
        evidence_id = (
            f"chain:q{qid}:s{step_index}:{lineage}:r{raw_attempt}:"
            f"{row.get('request_key')}"
        )
        judge_evidence = None
        if self.semantic_judge is not None and self.judge_ledger is not None:
            judge_evidence = self._judge_chain(
                item=item,
                evidence_id=evidence_id,
                identity={
                    "kind": "chain",
                    "qid": qid,
                    "step_index": step_index,
                    "lineage": lineage,
                    "raw_attempt": raw_attempt,
                    "request_key": str(row.get("request_key") or ""),
                },
                reasoning=str(row.get("complete_chain") or ""),
                parsed_answer=parsed_answer,
                syntactically_valid=syntactically_valid,
            )
        answer_validation: dict[str, Any]
        if syntactically_valid:
            deterministic = CladderAdapter().validate_pns_answer(
                {**item, "answer": item.get("gold_answer")},
                parsed_answer,
            )
            answer_validation = asdict(deterministic)
            recorded_correct = bool(
                row.get("correct") is True or row.get("correct") == 1
            )
            if recorded_correct != deterministic.valid:
                raise RuntimeError(
                    f"deterministic answer validation differs from journal q{qid} "
                    f"s{step_index} {lineage} r{raw_attempt}"
                )
        else:
            answer_validation = {
                "valid": False,
                "expected_answer": str(item.get("gold_answer") or ""),
                "parsed_answer": parsed_answer,
                "reason": "generation_not_syntactically_valid",
            }

        audit: dict[str, Any] | None = None
        if (
            syntactically_valid
            and answer_validation["valid"] is True
            and (
                judge_evidence is None
                or judge_evidence.get("accepted") is True
            )
            and isinstance(row.get("chain_token_count"), int)
            and int(row["chain_token_count"]) < parent.original_qwen_tokens
        ):
            candidate_key = f"{lineage}_s{step_index}:t{raw_attempt}"
            prompt = self.runner.journal.get_prompt(row["prompt_key"])
            prefix = prompt.get("frozen_prefix") if prompt else None
            provenance_ok = bool(
                isinstance(prefix, str)
                and isinstance(row.get("reasoning_suffix"), str)
                and row.get("complete_chain") == prefix + row["reasoning_suffix"]
            )
            audit = self.runtime.local_path_audit(
                item,
                candidate_key=candidate_key,
                reasoning=str(row.get("complete_chain") or ""),
                final_content=str(row.get("final_content") or ""),
                provenance_ok=provenance_ok,
            )
            evidence = audit.get("evidence")
            if isinstance(evidence, dict):
                audit["evidence"] = {
                    **evidence,
                    "semantic_judge_evidence_id": (
                        evidence_id if judge_evidence is not None else None
                    ),
                    "semantic_judge_passed": (
                        judge_evidence.get("accepted") is True
                        if judge_evidence is not None
                        else None
                    ),
                }
            self.runner.journal.store_audit(
                qid, candidate_key, int(row.get("request_seq") or raw_attempt), audit
            )
        trial = trial_from_qwen_journal_row(
            row,
            parent_qwen_tokens=parent.original_qwen_tokens,
            parent_answer=parent.parent_answer,
            audit=audit,
        )
        trial = replace(
            trial,
            valid_for_vote=(
                trial.valid_for_vote
                and (
                    judge_evidence is None
                    or judge_evidence.get("accepted") is True
                )
            ),
            correct=(
                bool(answer_validation["valid"])
                if trial.valid_for_vote
                and (
                    judge_evidence is None
                    or judge_evidence.get("accepted") is True
                )
                else trial.correct
            ),
            candidate_eligible=(
                trial.candidate_eligible
                and (
                    judge_evidence is None
                    or judge_evidence.get("accepted") is True
                )
            ),
            error=(
                trial.error
                or (
                    None
                    if judge_evidence is None
                    or judge_evidence.get("accepted") is True
                    else f"semantic_judge_{judge_evidence.get('status')}"
                )
            ),
            metadata={
                **trial.metadata,
                **(
                    {"request_recovery": dict(row["_request_recovery"])}
                    if isinstance(row.get("_request_recovery"), dict)
                    else {}
                ),
                "deterministic_answer_validation": answer_validation,
                **(
                    {"judge": judge_evidence}
                    if judge_evidence is not None
                    else {}
                ),
            },
        )
        if encoding_error:
            trial = replace(
                trial,
                error=encoding_error,
                metadata={**trial.metadata, "encoding_error": encoding_error},
            )
        return trial

    def _generate_replacement(
        self,
        *,
        item: dict[str, Any],
        segment: Any,
        keep_correct: int,
        delete_correct: int,
        accounting: ExecutionAccounting,
    ) -> ReplacementGeneration:
        qid = int(item["question_id"])
        step = int(segment.step_index)
        request_key = f"q{qid}-s{step:03d}-replacement-generate-r0"
        trigger = {
            "qid": qid,
            "step_index": step,
            "keep_correct": keep_correct,
            "delete_correct": delete_correct,
            "triggered": True,
            "generation_request_key": request_key,
            "state": "triggered_pending",
        }
        accounting.begin()
        if (
            self.recovery_amendment is not None
            and qid in self.recovery_amendment.target_qids
            and self.runner.journal.request_row(request_key) is None
        ):
            return ReplacementGeneration(
                valid=False,
                request_key=request_key,
                error=(
                    "max7_recovery_new_replacement_generation_forbidden; "
                    "only existing replacement evidence or new r6/r7 rollouts "
                    "may be used"
                ),
            )
        execution_started = False
        try:
            self.runner.journal.upsert_replacement(trigger)
            spec = self.runtime.PromptSpec(
                prompt_key=f"q{qid}-s{step:03d}-replacement-generate",
                qid=qid,
                step=step,
                branch="replacement_generate",
                endpoint="/v1/chat/completions",
                messages=self.runtime.replacement_messages(
                    self._qwen_generation_prompt_item(item), segment
                ),
                requested_max_tokens=self.runtime.REPLACEMENT_REQUESTED_MAX_TOKENS,
            )
            prompt = self.runtime.ensure_prompt(
                self.runner.journal, self.runner.api, spec
            )
            task = self.runtime.task_from_prompt(
                prompt,
                qid=qid,
                step=step,
                branch="replacement_generate",
                rollout=0,
                gold=None,
                seeds=self.seeds,
            )
            execution_started = True
            row = self._execute_task(task, accounting)
            if row is None:
                raise RuntimeError("replacement request row missing after execution")
            self.runtime.assert_response_assets(row, replacement_generation=True)
            generation = replacement_generation_from_qwen_journal_row(row)
            if not generation.valid:
                raise RuntimeError(generation.error or "replacement generation invalid")
            if self.semantic_judge is not None and self.judge_ledger is not None:
                judge_evidence_id = (
                    f"replacement:q{qid}:s{step}:{row.get('request_key')}"
                )
                replacement_judge = self._semantic_judge_call(
                    evidence_id=judge_evidence_id,
                    identity={
                        "kind": "replacement",
                        "qid": qid,
                        "step_index": step,
                        "request_key": str(row.get("request_key") or ""),
                    },
                    invoke=lambda: self.semantic_judge.judge_replacement(
                        self._semantic_sample(item),
                        {
                            "step_id": str(getattr(segment, "step_index", step)),
                            "text": str(getattr(segment, "text", "")).rstrip(),
                        },
                        {
                            "step_id": str(getattr(segment, "step_index", step)),
                            "text": generation.replacement_text,
                        },
                        user_id=judge_evidence_id,
                    ),
                )
                generation = replace(
                    generation,
                    valid=(
                        generation.valid
                        and replacement_judge.get("accepted") is True
                    ),
                    error=(
                        generation.error
                        or (
                            None
                            if replacement_judge.get("accepted") is True
                            else "replacement_semantic_judge_rejected"
                        )
                    ),
                    metadata={
                        **generation.metadata,
                        "judge": replacement_judge,
                    },
                )
                if not generation.valid:
                    self.runner.journal.upsert_replacement(
                        {
                            **trigger,
                            "state": "semantic_rejected",
                            "replacement_text": generation.replacement_text,
                            "error": generation.error,
                        }
                    )
                    return generation
            branch = self.runtime.make_replace_branch(
                item["parent_reasoning"], segment, generation.replacement_text
            )
            replace_spec = self.runtime.PromptSpec(
                prompt_key=f"q{qid}-s{step:03d}-replace",
                qid=qid,
                step=step,
                branch="replace",
                endpoint="/v1/completions",
                frozen_prefix=branch.prefix,
                serialized_prompt=item["base_serialized_prompt"] + branch.prefix,
            )
            self.runtime.ensure_prompt(
                self.runner.journal, self.runner.api, replace_spec
            )
            self.runner.journal.upsert_replacement(
                {
                    **trigger,
                    "state": "frozen",
                    "replacement_text": generation.replacement_text,
                    "replacement_with_delimiter": branch.replacement_text,
                    "replace_prefix": branch.prefix,
                }
            )
            return generation
        except RolloutInfrastructureError as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.runner.journal.upsert_replacement(
                {**trigger, "state": "generation_failed", "error": error}
            )
            raise
        except Exception as exc:
            if not execution_started:
                accounting.fail_before_registration()
            error = f"{type(exc).__name__}: {exc}"
            self.runner.journal.upsert_replacement(
                {**trigger, "state": "generation_failed", "error": error}
            )
            return ReplacementGeneration(
                valid=False, request_key=request_key, error=error
            )

    def _execute_task(
        self, task: Any, accounting: ExecutionAccounting
    ) -> dict[str, Any] | None:
        existing = self.runner.journal.request_row(task.request_key)
        existed = existing is not None
        if existing is None and self.recovery_amendment is not None:
            qid = int(getattr(task, "qid", -1))
            rollout = int(getattr(task, "rollout", -1))
            branch = str(getattr(task, "branch", ""))
            if not (
                qid in self.recovery_amendment.target_qids
                and rollout in self.recovery_amendment.new_raw_slots_only
                and branch in {"keep", "delete", "replace"}
            ):
                raise RolloutInfrastructureError(
                    "max7 recovery permits only new r6/r7 Qwen rollout slots "
                    "for the exact three target qids"
                )
        if (
            existing is not None
            and existing.get("state") == "posting"
            and self.request_recovery is not None
        ):
            try:
                self._validate_active_posting_identity(task, existing)
                recovered = self.request_recovery.recover_for_task(task)
                row = self._materialize_recovered_task(task, existing, recovered)
            except (RecoveryContractError, RecoveryInfrastructureError) as exc:
                accounting.finish(
                    existed=True,
                    row=existing,
                    result={"new_post": False, "infra_error": True},
                )
                raise RolloutInfrastructureError(
                    f"g1 request recovery failed closed for {task.request_key}: {exc}"
                ) from exc
            except Exception as exc:
                accounting.finish(
                    existed=True,
                    row=existing,
                    result={"new_post": False, "infra_error": True},
                )
                raise RolloutInfrastructureError(
                    f"g1 response materialization failed closed for "
                    f"{task.request_key}: {type(exc).__name__}: {exc}"
                ) from exc
            accounting.finish(
                existed=True,
                row=existing,
                result={
                    "new_post": not recovered.cached,
                    "infra_error": False,
                },
            )
            return row
        try:
            result = self.runner.executor.execute(task)
        except Exception:
            row = self.runner.journal.request_row(task.request_key)
            accounting.finish(existed=existed, row=row, result=None, raised=True)
            raise
        row = self.runner.journal.request_row(task.request_key)
        accounting.finish(existed=existed, row=row, result=result)
        return row

    @staticmethod
    def _validate_active_posting_identity(
        task: Any, source_row: dict[str, Any]
    ) -> None:
        raw_request = source_row.get("request_json")
        try:
            request_body = json.loads(raw_request)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RecoveryContractError(
                f"active posting identity drift for {task.request_key}: request_json"
            ) from exc
        expected = {
            "request_key": task.request_key,
            "qid": task.qid,
            "step_index": task.step,
            "branch": task.branch,
            "rollout": task.rollout,
            "seed": task.seed,
            "endpoint": task.endpoint,
            "prompt_key": task.prompt_key,
        }
        if request_body != task.body or any(
            source_row.get(key) != value for key, value in expected.items()
        ):
            raise RecoveryContractError(
                f"active posting identity drift for {task.request_key}"
            )

    def _materialize_recovered_task(
        self,
        task: Any,
        source_row: dict[str, Any],
        recovered: RecoveredScientificAttempt,
    ) -> dict[str, Any]:
        prompt = self.runner.journal.get_prompt(task.prompt_key)
        if prompt is None:
            raise RuntimeError(f"recovered request prompt disappeared: {task.prompt_key}")
        raw_prompt_ids = prompt.get("prompt_token_ids_json")
        if not isinstance(raw_prompt_ids, str):
            raise RuntimeError(
                f"recovered request prompt lacks token IDs: {task.prompt_key}"
            )
        expected_prompt_ids = json.loads(raw_prompt_ids)
        if not isinstance(expected_prompt_ids, list) or not all(
            type(value) is int for value in expected_prompt_ids
        ):
            raise RuntimeError(
                f"recovered request prompt token IDs are invalid: {task.prompt_key}"
            )
        raw = dict(recovered.response)
        if task.branch == "replacement_generate":
            parser = getattr(self.runtime, "parse_replacement_response", None)
            if not callable(parser):
                raise TypeError("batch56 runtime lacks recovery replacement parser")
            state, fields = parser(raw, expected_prompt_ids=expected_prompt_ids)
        else:
            parser = getattr(self.runtime, "parse_completion_response", None)
            if not callable(parser):
                raise TypeError("batch56 runtime lacks recovery completion parser")
            frozen_prefix = prompt.get("frozen_prefix")
            if not isinstance(frozen_prefix, str) or task.gold_answer is None:
                raise RuntimeError(
                    f"recovered continuation lacks frozen scoring inputs: {task.request_key}"
                )
            state, fields = parser(
                raw,
                frozen_prefix=frozen_prefix,
                gold_answer=task.gold_answer,
                expected_prompt_ids=expected_prompt_ids,
            )
        if not isinstance(state, str) or not isinstance(fields, dict):
            raise TypeError("batch56 recovery parser returned an invalid result")
        serialized = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
        return {
            **source_row,
            **fields,
            "state": state,
            "http_status": 200,
            "raw_response_text": serialized,
            "response_json": serialized,
            "response_received_at": recovered.recovery_dispatch_id,
            "completed_at": recovered.recovery_dispatch_id,
            "_request_recovery": {
                "generation": "g1",
                "dispatch_id": recovered.recovery_dispatch_id,
                "source_request_key": recovered.source_request_key,
                "cached": recovered.cached,
            },
        }

    def _persist_replacement_decisions(
        self,
        item: dict[str, Any],
        segments: dict[int, Any],
        result: AdaptivePnsCotRunResult,
    ) -> None:
        qid = int(item["question_id"])
        for step_result in result.step_results:
            decision = step_result.keep_delete.decision
            triggered = decision.action == "trigger_replace"
            generation = step_result.replacement_generation
            row: dict[str, Any] = {
                "qid": qid,
                "step_index": step_result.step_index,
                "keep_correct": decision.keep_correct,
                "delete_correct": decision.delete_correct,
                "triggered": triggered,
                "generation_request_key": generation.request_key
                if generation
                else None,
                "state": (
                    "frozen"
                    if generation and generation.valid
                    else "generation_failed"
                    if triggered
                    else "operationally_inconclusive"
                    if decision.action == "inconclusive_operational"
                    else "not_triggered"
                ),
                "error": generation.error if generation else None,
            }
            if generation and generation.valid:
                branch = self.runtime.make_replace_branch(
                    item["parent_reasoning"],
                    segments[step_result.step_index],
                    generation.replacement_text,
                )
                row.update(
                    {
                        "replacement_text": generation.replacement_text,
                        "replacement_with_delimiter": branch.replacement_text,
                        "replace_prefix": branch.prefix,
                    }
                )
            self.runner.journal.upsert_replacement(row)

    def _parent_token_count(self, qid: int) -> int:
        row = next(
            (row for row in self.runner.journal.item_rows() if row["qid"] == qid), None
        )
        if row is None or not isinstance(row.get("parent_token_count"), int):
            raise RuntimeError(f"parent encoding missing for q{qid}")
        return int(row["parent_token_count"])

    def _completed_artifact(self, qid: int) -> dict[str, Any] | None:
        row = next(
            (row for row in self.runner.journal.item_rows() if row["qid"] == qid), None
        )
        if row is None or row.get("state") != "completed":
            return None
        payload = json.loads(row.get("result_json") or "null")
        if (
            not isinstance(payload, dict)
            or payload.get("result_type") != ADAPTER_VERSION
        ):
            raise RuntimeError(
                f"q{qid} was completed by a different runner; use a fresh adaptive run directory"
            )
        artifact = payload.get("artifact")
        if not isinstance(artifact, dict):
            raise RuntimeError(f"completed adaptive item q{qid} lacks its artifact")
        return artifact

    @staticmethod
    def _write_or_verify_artifacts(
        path: Path, artifacts: Sequence[dict[str, Any]]
    ) -> None:
        if not path.exists():
            write_pnscot_artifact_jsonl(path, artifacts)
            return
        existing = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if existing != list(artifacts):
            raise RuntimeError(
                "existing adaptive PNSCoT artifact differs; refusing overwrite"
            )


def load_batch56_runtime(path: str | Path) -> ModuleType:
    """Load the copied frozen batch56 runner without modifying its source."""

    runner_path = Path(path).resolve()
    if not runner_path.is_file():
        raise FileNotFoundError(runner_path)
    module_name = "cause_qwen_batch56_runtime"
    previous = sys.modules.pop(module_name, None)
    sys.path.insert(0, str(runner_path.parent))
    try:
        spec = importlib.util.spec_from_file_location(module_name, runner_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load batch56 runtime from {runner_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        _validate_runtime(module)
        return module
    except Exception:
        sys.modules.pop(module_name, None)
        if previous is not None:
            sys.modules[module_name] = previous
        raise
    finally:
        sys.path.remove(str(runner_path.parent))


def _validate_runtime(runtime: Any) -> None:
    required = (
        "PromptSpec",
        "REPLACEMENT_REQUESTED_MAX_TOKENS",
        "assert_response_assets",
        "ensure_encoding",
        "ensure_prompt",
        "item_segments",
        "local_path_audit",
        "make_replace_branch",
        "replacement_messages",
        "task_from_prompt",
    )
    missing = [name for name in required if not hasattr(runtime, name)]
    if missing:
        raise TypeError(f"batch56 runtime is missing: {', '.join(missing)}")
