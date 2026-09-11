from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import yaml

from .experiments.cladder_pns_mvp.judge import CladderSemanticJudge
from .experiments.cladder_pns_mvp.judge_transport import (
    DeepSeekChatJudgeTransport,
)
from .providers.deepseek_client import call_deepseek_chat
from .pns_judge_ledger import SemanticJudgeLedger


_CANARY_SAMPLE = {
    "question_id": "deepseek-judge-preflight-canary",
    "given_info": (
        "In a binary structural causal model, A directly causes B. "
        "Under do(A=1), B=1; under do(A=0), B=0."
    ),
    "question": "Does intervening on A change B?",
    "meta": {"rung": 2, "query_type": "ate"},
}
_CANARY_ORIGINAL_STEP = {
    "step_id": "step1",
    "text": "Compare B under do(A=1) and do(A=0).",
}
_CANARY_REPLACEMENT_STEP = {
    "step_id": "step1",
    "text": "Condition on observed A instead of intervening on A.",
}
_CANARY_CHAIN = {
    "steps": [
        {
            "step_id": "step1",
            "text": "Compare B under do(A=1) and do(A=0).",
        },
        {
            "step_id": "step2",
            "text": "The two interventional outcomes differ, so A changes B.",
        },
    ],
    "final_answer": "yes",
}

_LEGACY_DEEPSEEK_ACCEPTED_PROFILE = {
    "provider": "deepseek",
    "endpoint_type": "chat.completions",
    "requested_model": "deepseek-v4-pro",
    "resolved_model": "deepseek-v4-pro",
    "response_model": "deepseek-v4-pro",
    "thinking_type": "enabled",
    "reasoning_effort": "max",
    "status": "parsed",
    "parse_status": "parsed",
    "decision": "accepted",
    "accepted": True,
    "fallback_allowed": False,
    "fallback_used": False,
}
_FUTURE_CLI_PROXY_ACCEPTED_PROFILE = {
    "provider": "cli_proxy",
    "endpoint_type": "responses",
    "base_url": "http://127.0.0.1:8317/v1",
    "requested_model": "gpt-5.5",
    "resolved_model": "gpt-5.5",
    "response_model": "gpt-5.5",
    "actual_judge_model": "gpt-5.5",
    "thinking_type": "enabled",
    "reasoning_effort": "xhigh",
    "json_schema_strict": True,
    "stream": False,
    "store": False,
    "protocol_revision": "future_responses_xhigh_strict_json_schema_v1",
    "scope": "future_new_evidence",
    "switch_reason": "user_authorized_future_judge",
    "scientific_raw_attempt_delta": 0,
    "app_max_retries": 0,
    "default_pass_allowed": False,
    "status": "parsed",
    "parse_status": "parsed",
    "decision": "accepted",
    "accepted": True,
    "fallback_allowed": False,
    "fallback_used": False,
}


def build_deepseek_semantic_judge(
    resolved_config: dict[str, Any],
    *,
    min_confidence: float,
    call_fn: Callable[..., dict[str, Any]] = call_deepseek_chat,
) -> CladderSemanticJudge:
    """Build the only Judge implementation admitted to the formal Qwen PNS CLI."""

    transport = DeepSeekChatJudgeTransport(resolved_config, call_fn=call_fn)
    return CladderSemanticJudge(transport, min_confidence=min_confidence)


def build_judge_contract(resolved_config: dict[str, Any]) -> dict[str, Any]:
    runtime = resolved_config.get("runtime")
    arm = {
        key: value
        for key, value in resolved_config.items()
        if key not in {"provider", "transport", "runtime"}
    }
    if isinstance(runtime, dict):
        arm.update(runtime)
    return {
        "provider": resolved_config.get("provider"),
        "endpoint_type": resolved_config.get("transport"),
        "requested_model": arm.get("model"),
        "resolved_model": arm.get("api_model") or arm.get("model"),
        "thinking_type": dict(arm.get("thinking") or {}).get("type"),
        "reasoning_effort": arm.get("reasoning_effort"),
        "response_format": arm.get("response_format"),
        "omit_max_tokens": arm.get("omit_max_tokens") is True,
        "max_retries": int(arm.get("max_retries") or 0),
        "max_provider_calls_per_logical_call": int(arm.get("max_retries") or 0)
        + 1,
        "fallback_allowed": False,
    }


def load_frozen_phase56_contract(
    path: str | Path,
    *,
    input_manifest: str | Path,
    judge_contract: dict[str, Any],
    execution_options: dict[str, Any],
) -> dict[str, Any]:
    """Validate the single phase56 source against the exact CLI input/options."""

    config_path = Path(path)
    if not config_path.is_file():
        raise RuntimeError(f"phase56 config is missing: {config_path}")
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("phase56 config must be a mapping")

    protocol_id = payload.get("protocol_id")
    if protocol_id != "qwen_pns_phase56_20260826_v2_qwen_source_segments":
        raise RuntimeError("phase56 must use the frozen Qwen-source-segments v2 protocol")
    dataset = _required_mapping(payload, "dataset")
    if dataset.get("name") != "CLADDER":
        raise RuntimeError("phase56 dataset must be CLADDER")
    segmentation = _required_mapping(dataset, "segmentation")
    expected_segmentation = {
        "actual_source": "frozen_input_qwen_parent_segments",
        "parent_source": "parent_reasoning",
        "segment_source": "segments",
        "source_preserving": True,
        "programmatic_source": "cladder_programmatic_reasoning",
        "programmatic_role": "semantic_reference_alignment_anchor_only",
        "one_to_one_required": False,
        "same_path_required": False,
        "canonical_author_text_qwen_prompt": "forbidden",
        "canonical_author_text_judge_payload": (
            "advisory_non_answer_steps_only"
        ),
        "programmatic_steps_present_but_malformed": "fail_closed",
        "programmatic_steps_missing": "named_explicit_fallback_only",
        "fallback_id": "qwen_parent_source_preserving_v1",
    }
    if segmentation != expected_segmentation:
        raise RuntimeError("phase56 frozen Qwen segmentation contract changed")

    sample = _required_mapping(payload, "sample_manifest")
    frozen_ids = sample.get("sample_ids")
    if (
        sample.get("required") is not True
        or sample.get("runtime_replacement_forbidden") is not True
        or sample.get("frozen_sample_count") != 56
        or not isinstance(frozen_ids, list)
        or len(frozen_ids) != 56
        or len(set(frozen_ids)) != 56
        or any(type(qid) is not int for qid in frozen_ids)
    ):
        raise RuntimeError("phase56 frozen 56-sample manifest is invalid")
    declared_input = Path(str(sample.get("path") or ""))
    actual_input = Path(input_manifest)
    if declared_input.name != actual_input.name:
        raise RuntimeError("phase56 input filename differs from the frozen config")
    actual_ids = _read_input_question_ids(actual_input)
    if actual_ids != frozen_ids:
        raise RuntimeError("phase56 input IDs/order differ from the frozen config")

    phase = _required_mapping(payload, "phase56")
    shorter = _required_mapping(phase, "final_qwen_tokens")
    if not (
        phase.get("accepted_target") == 56
        and phase.get("preserve_all_attempt_and_judge_trajectories") is True
        and phase.get("silent_sample_drop_forbidden") is True
        and phase.get("fallback_counts_as_accepted") is False
        and shorter
        == {
            "operator": "<",
            "reference": "parent_qwen_tokens",
            "scope": "complete_reasoning_chain",
        }
    ):
        raise RuntimeError("phase56 strict shorter/no-fallback contract changed")

    rollout = _required_mapping(payload, "rollout")
    expected_rollout = {
        "initial_valid_rounds": 3,
        "max_valid_rounds": 5,
        "max_raw_attempts_per_lineage": 5,
        "accept_correct_votes": 3,
        "accept_at_five": "3:2",
        "extra_recovery": False,
    }
    if rollout != expected_rollout:
        raise RuntimeError("phase56 rollout contract must remain 3-to-5, 3:2, no recovery")
    if (
        execution_options.get("initial_valid_rounds") != 3
        or execution_options.get("max_valid_rounds") != 5
        or execution_options.get("max_raw_attempts_per_lineage") != 5
    ):
        raise RuntimeError("CLI rollout options differ from the frozen phase56 config")

    judge = _required_mapping(payload, "judge")
    if not (
        judge.get("provider") == "deepseek"
        and judge.get("transport") == "chat.completions"
        and judge.get("model") == "deepseek-v4-pro"
        and _required_mapping(judge, "thinking").get("type") == "enabled"
        and judge.get("reasoning_effort") == "max"
        and judge.get("response_format") == {"type": "json_object"}
        and judge.get("omit_max_tokens") is True
        and judge.get("openai_or_gpt_fallback") == "forbidden"
        and judge.get("error_parse_or_skip_policy") == "reject"
        and judge.get("replacement_semantic_acceptance")
        == {
            "any_of": ["semantically_equivalent", "valid_alternative_path"],
            "all_of": ["no_contradiction", "valid_intervention"],
        }
        and judge.get("complete_chain_acceptance")
        == {"all_of": ["chain_coherent", "logic_valid"]}
        and judge.get("deterministic_answer_validation")
        == "required_separate_hard_gate"
    ):
        raise RuntimeError("phase56 Judge policy differs from the frozen DeepSeek gate")
    for phase_key, contract_key in (
        ("provider", "provider"),
        ("transport", "endpoint_type"),
        ("model", "requested_model"),
        ("reasoning_effort", "reasoning_effort"),
        ("response_format", "response_format"),
    ):
        if judge.get(phase_key) != judge_contract.get(contract_key):
            raise RuntimeError("phase56 Judge config differs from resolved runtime")
    if (
        _required_mapping(judge, "thinking").get("type")
        != judge_contract.get("thinking_type")
        or bool(judge.get("omit_max_tokens"))
        != bool(judge_contract.get("omit_max_tokens"))
    ):
        raise RuntimeError("phase56 Judge thinking/token policy differs from runtime")

    concurrency = _required_mapping(payload, "concurrency")
    endpoints = concurrency.get("endpoints")
    base_urls = execution_options.get("base_urls")
    if not (
        concurrency.get("scope") == "endpoint_local"
        and isinstance(endpoints, list)
        and len(endpoints) == 2
        and len(set(endpoints)) == 2
        and concurrency.get("initial_inflight_per_endpoint") == 48
        and concurrency.get("aggregate_generation_limit") is None
        and concurrency.get("outer_item_scheduler") == "fully_expanded"
        and concurrency.get("outer_step_scheduler") == "fully_expanded"
        and concurrency.get("generation_route")
        == "qid_plus_step_mod_backend_count"
        and concurrency.get("affinity_fields") == ["qid", "step"]
        and concurrency.get("matched_branches_same_endpoint") is True
        and concurrency.get("automatic_failover") is False
    ):
        raise RuntimeError("phase56 endpoint-local concurrency contract changed")
    if not (
        execution_options.get("adaptive_endpoint_concurrency") is True
        and isinstance(base_urls, list)
        and len(base_urls) == len(endpoints)
        and len(set(base_urls)) == len(base_urls)
        and execution_options.get("endpoint_initial_inflight") == 48
        and execution_options.get("item_workers") == 0
        and execution_options.get("step_workers_per_item") == 0
    ):
        raise RuntimeError("CLI concurrency options differ from the frozen phase56 config")

    return {
        "protocol_id": protocol_id,
        "phase_config": str(config_path.resolve()),
        "dataset": "CLADDER",
        "input_manifest": str(actual_input.resolve()),
        "input_filename": actual_input.name,
        "sample_count": 56,
        "sample_ids": list(frozen_ids),
        "segmentation": {
            key: expected_segmentation[key]
            for key in (
                "actual_source",
                "parent_source",
                "segment_source",
                "source_preserving",
                "programmatic_role",
                "one_to_one_required",
                "same_path_required",
                "canonical_author_text_qwen_prompt",
                "canonical_author_text_judge_payload",
            )
        },
        "rollout": expected_rollout,
        "strict_shorter_no_fallback": True,
        "endpoint_count": len(endpoints),
        "initial_inflight_per_endpoint": 48,
        "aggregate_generation_limit": None,
        "generation_route": "qid_plus_step_mod_backend_count",
        "affinity_fields": ["qid", "step"],
        "matched_branches_same_endpoint": True,
        "judge_config": {
            "provider": "deepseek",
            "endpoint_type": "chat.completions",
            "model": "deepseek-v4-pro",
            "thinking_type": "enabled",
            "reasoning_effort": "max",
        },
    }


def _required_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"phase56 config field {key} must be a mapping")
    return value


def _read_input_question_ids(path: Path) -> list[int]:
    if not path.is_file():
        raise RuntimeError(f"phase56 input manifest is missing: {path}")
    ids: list[int] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(),
        1,
    ):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"phase56 input manifest line {line_number} is invalid JSON"
            ) from exc
        if not isinstance(row, dict) or type(row.get("question_id")) is not int:
            raise RuntimeError(
                f"phase56 input line {line_number} lacks integer question_id"
            )
        ids.append(row["question_id"])
    if len(ids) != 56:
        raise RuntimeError("phase56 input manifest must contain exactly 56 rows")
    return ids


def run_offline_judge_preflight(
    judge: CladderSemanticJudge,
    *,
    judge_contract: dict[str, Any],
) -> dict[str, Any]:
    """Resolve both formal semantic payload shapes without any provider call."""

    replacement = judge.preflight_replacement(
        _CANARY_SAMPLE,
        _CANARY_ORIGINAL_STEP,
        _CANARY_REPLACEMENT_STEP,
    )
    full_chain = judge.preflight_chain(_CANARY_SAMPLE, _CANARY_CHAIN)
    payloads = {
        "replacement": _safe_preflight_payload(replacement),
        "full_chain": _safe_preflight_payload(full_chain),
    }
    if any(payload["provider_call_count"] != 0 for payload in payloads.values()):
        raise RuntimeError("offline Judge preflight unexpectedly dispatched a request")
    if any(not _preflight_payload_passes(payload) for payload in payloads.values()):
        raise RuntimeError("offline Judge payload failed its DeepSeek contract")
    expected = {
        "provider": "deepseek",
        "endpoint_type": "chat.completions",
        "requested_model": "deepseek-v4-pro",
        "resolved_model": "deepseek-v4-pro",
        "thinking_type": "enabled",
        "reasoning_effort": "max",
        "response_format": {"type": "json_object"},
        "omit_max_tokens": True,
        "max_retries": 3,
        "max_provider_calls_per_logical_call": 4,
        "fallback_allowed": False,
    }
    if judge_contract != expected:
        raise RuntimeError("resolved Judge contract differs from the frozen DeepSeek gate")
    return {
        "schema_version": "qwen_pns_judge_offline_preflight_v1",
        "passed": True,
        "provider_calls": 0,
        "judge_contract": judge_contract,
        "payloads": payloads,
    }


def write_offline_judge_preflight(
    path: str | Path,
    evidence: dict[str, Any],
) -> None:
    if evidence.get("schema_version") != "qwen_pns_judge_offline_preflight_v1":
        raise RuntimeError("offline Judge preflight schema is not recognized")
    if evidence.get("passed") is not True or evidence.get("provider_calls") != 0:
        raise RuntimeError("offline Judge preflight did not pass without provider calls")
    _write_or_verify_json(path, evidence)


def build_execution_binding(
    *,
    runtime_runner: str | Path,
    input_manifest: str | Path,
    run_dir: str | Path,
    output_artifact: str | Path,
    rollout_contract: dict[str, Any],
    phase_contract: dict[str, Any],
) -> dict[str, Any]:
    """Bind a live Judge canary to one exact formal-run command target."""

    return {
        "runtime_runner": str(Path(runtime_runner).resolve()),
        "input_manifest": str(Path(input_manifest).resolve()),
        "run_dir": str(Path(run_dir).resolve()),
        "output_artifact": str(Path(output_artifact).resolve()),
        "rollout_contract": dict(rollout_contract),
        "phase_contract": dict(phase_contract),
    }


def run_live_judge_canary(
    judge: CladderSemanticJudge,
    *,
    ledger: SemanticJudgeLedger,
    judge_contract: dict[str, Any],
    execution_binding: dict[str, Any],
    output_path: str | Path,
) -> dict[str, Any]:
    """Dispatch one bounded synthetic chain judgment behind a no-resend ledger."""

    evidence_id = "canary:deepseek-v4-pro:full-chain-v1"
    identity = {
        "kind": "live_judge_canary",
        "judge_contract": judge_contract,
        "execution_binding": execution_binding,
    }
    previous = ledger.reserve(evidence_id, identity)
    if previous is None:
        result = judge.judge_chain(
            _CANARY_SAMPLE,
            _CANARY_CHAIN,
            user_id=evidence_id,
        )
        evidence = _safe_judge_evidence(result)
        ledger.complete(evidence_id, evidence)
    else:
        evidence = dict(previous)
    passed = _accepted_deepseek_evidence(evidence)
    artifact = {
        "schema_version": "qwen_pns_deepseek_judge_canary_v1",
        "passed": passed,
        "judge_contract": judge_contract,
        "execution_binding": execution_binding,
        "evidence_id": evidence_id,
        "ledger": str(ledger.path.resolve()),
        "ledger_state": "completed",
        "dispatch_bound": {
            "logical_calls": 1,
            "max_provider_calls": judge_contract[
                "max_provider_calls_per_logical_call"
            ],
        },
        "judge_evidence": evidence,
    }
    _write_or_verify_json(output_path, artifact)
    return artifact


def rebind_live_judge_canary(
    source_path: str | Path,
    *,
    output_path: str | Path,
    expected_judge_contract: dict[str, Any],
    new_execution_binding: dict[str, Any],
) -> dict[str, Any]:
    """Reuse accepted v1 canary evidence for v2 without a provider call."""

    source = Path(source_path).resolve()
    target = Path(output_path).resolve()
    if source == target:
        raise RuntimeError("canary rebind requires a new v2 attestation path")
    source_artifact = _read_json_object(source, label="source live Judge canary")
    if source_artifact.get("schema_version") != "qwen_pns_deepseek_judge_canary_v1":
        raise RuntimeError("source live Judge canary schema is not recognized")
    if source_artifact.get("judge_contract") != expected_judge_contract:
        raise RuntimeError("source live Judge canary Judge contract differs")
    evidence = source_artifact.get("judge_evidence")
    if (
        source_artifact.get("passed") is not True
        or not isinstance(evidence, dict)
        or not _accepted_deepseek_evidence(evidence)
    ):
        raise RuntimeError("source live Judge canary lacks accepted DeepSeek evidence")
    source_binding = source_artifact.get("execution_binding")
    if not isinstance(source_binding, dict):
        raise RuntimeError("source live Judge canary execution binding is missing")
    _validate_canary_rebind_transition(source_binding, new_execution_binding)

    artifact = {
        "schema_version": "qwen_pns_deepseek_judge_canary_rebind_v2",
        "passed": True,
        "provider_calls": 0,
        "source_canary": str(source),
        "judge_contract": expected_judge_contract,
        "source_execution_binding": source_binding,
        "execution_binding": new_execution_binding,
        "rebind_policy": {
            "allowed_changes": [
                "run_dir",
                "output_artifact",
                "phase_contract.protocol_id",
                "phase_contract.phase_config",
                "phase_contract.segmentation",
                "phase_contract.generation_route",
                "phase_contract.affinity_fields",
                "phase_contract.matched_branches_same_endpoint",
            ],
            "qwen_route_change": (
                "qid_only_to_qid_plus_step_matched_affinity"
            ),
            "judge_contract_unchanged": True,
            "provider_dispatch": False,
            "ledger_copied": False,
            "formal_attempts_copied": False,
        },
    }
    _write_or_verify_json(target, artifact)
    return artifact


def verify_live_judge_canary(
    path: str | Path,
    *,
    expected_judge_contract: dict[str, Any],
    expected_execution_binding: dict[str, Any],
) -> dict[str, Any]:
    source = Path(path)
    artifact = _read_json_object(source, label="live Judge canary artifact")
    if artifact.get("schema_version") == "qwen_pns_deepseek_judge_canary_rebind_v2":
        return _verify_rebound_live_judge_canary(
            artifact,
            expected_judge_contract=expected_judge_contract,
            expected_execution_binding=expected_execution_binding,
        )
    if artifact.get("schema_version") != "qwen_pns_deepseek_judge_canary_v1":
        raise RuntimeError("live Judge canary schema is not recognized")
    if artifact.get("judge_contract") != expected_judge_contract:
        raise RuntimeError("live Judge canary Judge contract differs")
    if artifact.get("execution_binding") != expected_execution_binding:
        raise RuntimeError("live Judge canary execution binding differs")
    evidence = artifact.get("judge_evidence")
    if artifact.get("passed") is not True or not isinstance(evidence, dict):
        raise RuntimeError("live Judge canary did not pass")
    if not _accepted_deepseek_evidence(evidence):
        raise RuntimeError("live Judge canary lacks accepted DeepSeek evidence")
    return artifact


def _verify_rebound_live_judge_canary(
    artifact: dict[str, Any],
    *,
    expected_judge_contract: dict[str, Any],
    expected_execution_binding: dict[str, Any],
) -> dict[str, Any]:
    if artifact.get("passed") is not True or artifact.get("provider_calls") != 0:
        raise RuntimeError("rebound live Judge canary is not an offline pass")
    if artifact.get("judge_contract") != expected_judge_contract:
        raise RuntimeError("rebound live Judge canary Judge contract differs")
    if artifact.get("execution_binding") != expected_execution_binding:
        raise RuntimeError("rebound live Judge canary execution binding differs")
    source_path = artifact.get("source_canary")
    if not isinstance(source_path, str) or not Path(source_path).is_absolute():
        raise RuntimeError("rebound live Judge canary source path is not absolute")
    source = _read_json_object(source_path, label="source live Judge canary")
    if source.get("schema_version") != "qwen_pns_deepseek_judge_canary_v1":
        raise RuntimeError("source live Judge canary schema is not recognized")
    if source.get("judge_contract") != expected_judge_contract:
        raise RuntimeError("source live Judge canary Judge contract differs")
    evidence = source.get("judge_evidence")
    if (
        source.get("passed") is not True
        or not isinstance(evidence, dict)
        or not _accepted_deepseek_evidence(evidence)
    ):
        raise RuntimeError("source live Judge canary lacks accepted DeepSeek evidence")
    source_binding = source.get("execution_binding")
    if source_binding != artifact.get("source_execution_binding"):
        raise RuntimeError("rebound live Judge canary source binding differs")
    _validate_canary_rebind_transition(source_binding, expected_execution_binding)
    return artifact


def _validate_canary_rebind_transition(
    source_binding: Any,
    new_binding: Any,
) -> None:
    if not isinstance(source_binding, dict) or not isinstance(new_binding, dict):
        raise RuntimeError("canary rebind execution bindings must be mappings")
    for key in ("runtime_runner", "input_manifest", "rollout_contract"):
        if source_binding.get(key) != new_binding.get(key):
            raise RuntimeError(f"canary rebind stable execution field changed: {key}")
    if source_binding.get("run_dir") == new_binding.get("run_dir"):
        raise RuntimeError("canary rebind must use a new run_dir")
    if source_binding.get("output_artifact") == new_binding.get("output_artifact"):
        raise RuntimeError("canary rebind must use a new output_artifact")

    source_phase = source_binding.get("phase_contract")
    new_phase = new_binding.get("phase_contract")
    if not isinstance(source_phase, dict) or not isinstance(new_phase, dict):
        raise RuntimeError("canary rebind phase contracts must be mappings")
    if source_phase.get("protocol_id") != "qwen_pns_phase56_20260826":
        raise RuntimeError("canary rebind source is not the frozen v1 protocol")
    if (
        new_phase.get("protocol_id")
        != "qwen_pns_phase56_20260826_v2_qwen_source_segments"
    ):
        raise RuntimeError("canary rebind target is not the frozen v2 protocol")
    segmentation = new_phase.get("segmentation")
    if not isinstance(segmentation, dict) or not (
        segmentation.get("actual_source")
        == "frozen_input_qwen_parent_segments"
        and segmentation.get("programmatic_role")
        == "semantic_reference_alignment_anchor_only"
    ):
        raise RuntimeError("canary rebind target segmentation is not frozen v2")
    if not (
        new_phase.get("generation_route")
        == "qid_plus_step_mod_backend_count"
        and new_phase.get("affinity_fields") == ["qid", "step"]
        and new_phase.get("matched_branches_same_endpoint") is True
    ):
        raise RuntimeError("canary rebind target Qwen step-affinity route is invalid")
    allowed_phase_changes = {
        "protocol_id",
        "phase_config",
        "segmentation",
        "generation_route",
        "affinity_fields",
        "matched_branches_same_endpoint",
    }
    stable_source_phase = {
        key: value
        for key, value in source_phase.items()
        if key not in allowed_phase_changes
    }
    stable_new_phase = {
        key: value
        for key, value in new_phase.items()
        if key not in allowed_phase_changes
    }
    if stable_source_phase != stable_new_phase:
        raise RuntimeError("canary rebind stable execution phase fields changed")


def _read_json_object(path: str | Path, *, label: str) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise RuntimeError(f"{label} is missing: {source}")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be an object")
    return value


def run_with_first_accepted_gate(
    adapter: Any,
    *,
    output_path: str | Path,
    gate_path: str | Path,
    expected_items: int = 56,
) -> list[dict[str, Any]]:
    """Release the full batch only after its first frozen item is accepted."""

    items = list(adapter.runner.items)
    if len(items) != int(expected_items):
        raise RuntimeError(
            f"formal PNS manifest must contain exactly {expected_items} items"
        )
    adapter.prepare_execution()
    first = adapter.run_item(items[0])
    _validate_formal_accepted_artifact(first)
    first_evidence = dict(first["judge_acceptance"])
    evidence_id = first_evidence.pop("evidence_id", None)
    safe_evidence = _safe_judge_evidence(first_evidence)
    if evidence_id is not None:
        safe_evidence["evidence_id"] = evidence_id
    gate = {
        "schema_version": "qwen_pns_first_accepted_judge_gate_v1",
        "passed": True,
        "question_id": first["question_id"],
        "optimized": first["optimized"],
        "fallback": first["fallback"],
        "original_qwen_tokens": first["original_qwen_tokens"],
        "final_qwen_tokens": first["final_qwen_tokens"],
        "judge_evidence": safe_evidence,
        "deterministic_answer_validation": dict(
            first["deterministic_answer_validation"]
        ),
    }
    _write_or_verify_json(gate_path, gate)

    rows = adapter.run(output_path=output_path)
    if len(rows) != int(expected_items):
        raise RuntimeError(
            f"formal PNS output must contain exactly {expected_items} accepted items"
        )
    ids: set[str] = set()
    for row in rows:
        _validate_formal_accepted_artifact(row)
        qid = str(row.get("question_id"))
        if qid in ids:
            raise RuntimeError(f"duplicate formal PNS question_id: {qid}")
        ids.add(qid)
    return rows


def run_until_first_future_accepted_gate(
    adapter: Any,
    *,
    gate_path: str | Path,
    expected_items: int = 56,
) -> dict[str, Any]:
    """Resume pending items only until one strict future-Judge artifact is proven."""

    items = list(adapter.runner.items)
    if len(items) != int(expected_items):
        raise RuntimeError(
            f"formal PNS manifest must contain exactly {expected_items} items"
        )
    adapter.prepare_execution()
    existing_gate = Path(gate_path)
    if existing_gate.is_file():
        gate = _read_json_object(existing_gate, label="first future Judge gate")
        if not (
            gate.get("schema_version")
            == "qwen_pns_first_future_accepted_judge_gate_v1"
            and gate.get("passed") is True
            and isinstance(gate.get("judge_evidence"), dict)
            and gate["judge_evidence"].get("scope") == "future_new_evidence"
        ):
            raise RuntimeError("first future Judge gate is invalid")
        qid = str(gate.get("question_id"))
        matching = [item for item in items if str(item.get("question_id")) == qid]
        if len(matching) != 1:
            raise RuntimeError("first future Judge gate item is not in the manifest")
        artifact = adapter.run_item(matching[0])
        _validate_formal_accepted_artifact(artifact)
        if artifact.get("judge_acceptance", {}).get("scope") != (
            "future_new_evidence"
        ):
            raise RuntimeError("first future Judge gate artifact scope differs")
        return artifact

    rows = adapter.runner.journal.item_rows()
    state_by_qid: dict[str, str] = {}
    for row in rows:
        if isinstance(row, dict):
            qid = row.get("qid")
            state = row.get("state")
        else:
            qid = row["qid"]
            state = row["state"]
        state_by_qid[str(qid)] = str(state or "pending")
    pending = [
        item
        for item in items
        if state_by_qid.get(str(item.get("question_id")), "pending")
        != "completed"
    ]
    if not pending:
        raise RuntimeError(
            "no pending item can establish the first future Judge accepted gate"
        )

    for item in pending:
        artifact = adapter.run_item(item)
        _validate_formal_accepted_artifact(artifact)
        judge_acceptance = artifact.get("judge_acceptance")
        if not isinstance(judge_acceptance, dict) or judge_acceptance.get(
            "scope"
        ) != "future_new_evidence":
            continue
        first_evidence = dict(judge_acceptance)
        evidence_id = first_evidence.pop("evidence_id", None)
        safe_evidence = _safe_judge_evidence(first_evidence)
        if evidence_id is not None:
            safe_evidence["evidence_id"] = evidence_id
        gate = {
            "schema_version": "qwen_pns_first_future_accepted_judge_gate_v1",
            "passed": True,
            "question_id": artifact["question_id"],
            "optimized": artifact["optimized"],
            "fallback": artifact["fallback"],
            "original_qwen_tokens": artifact["original_qwen_tokens"],
            "final_qwen_tokens": artifact["final_qwen_tokens"],
            "judge_evidence": safe_evidence,
            "deterministic_answer_validation": dict(
                artifact["deterministic_answer_validation"]
            ),
        }
        _write_or_verify_json(gate_path, gate)
        return artifact
    raise RuntimeError(
        "pending items completed without a strict future Judge accepted artifact"
    )


def _validate_formal_accepted_artifact(artifact: dict[str, Any]) -> None:
    if not isinstance(artifact, dict):
        raise RuntimeError("formal PNS artifact must be an object")
    optimized = artifact.get("optimized")
    fallback = artifact.get("fallback")
    if not isinstance(optimized, bool) or not isinstance(fallback, bool):
        raise RuntimeError("formal PNS artifact must label optimized and fallback")
    if optimized == fallback:
        raise RuntimeError("formal PNS optimized/fallback labels must be mutually exclusive")
    original_tokens = artifact.get("original_qwen_tokens")
    final_tokens = artifact.get("final_qwen_tokens")
    if not (
        optimized is True
        and fallback is False
        and isinstance(original_tokens, int)
        and isinstance(final_tokens, int)
        and final_tokens < original_tokens
    ):
        raise RuntimeError(
            "formal accepted artifact must be an optimized shorter PNS-CoT"
        )
    deterministic = artifact.get("deterministic_answer_validation")
    if not isinstance(deterministic, dict) or deterministic.get("valid") is not True:
        raise RuntimeError("formal PNS deterministic answer validation did not pass")
    evidence = artifact.get("judge_acceptance")
    if not isinstance(evidence, dict) or not _accepted_formal_judge_evidence(evidence):
        raise RuntimeError(
            "formal PNS artifact lacks accepted Judge evidence matching the "
            "legacy DeepSeek or future CLIProxy strict profile"
        )
    evidence_id = str(evidence.get("evidence_id") or "")
    if not evidence_id.startswith("materialization:"):
        raise RuntimeError("formal PNS artifact lacks materialization Judge evidence_id")


def _safe_judge_evidence(result: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "provider",
        "endpoint_type",
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


def _accepted_deepseek_evidence(evidence: dict[str, Any]) -> bool:
    return bool(
        evidence.get("provider") == "deepseek"
        and evidence.get("endpoint_type") == "chat.completions"
        and evidence.get("requested_model") == "deepseek-v4-pro"
        and evidence.get("resolved_model") == "deepseek-v4-pro"
        and evidence.get("response_model") == "deepseek-v4-pro"
        and evidence.get("thinking_type") == "enabled"
        and evidence.get("reasoning_effort") == "max"
        and evidence.get("status") == "parsed"
        and evidence.get("parse_status") == "parsed"
        and evidence.get("decision") == "accepted"
        and evidence.get("accepted") is True
        and int(evidence.get("provider_call_count") or 0) >= 1
        and int(evidence.get("retry_count") or 0) >= 0
        and evidence.get("fallback_allowed") is False
        and evidence.get("fallback_used") is False
        and isinstance(evidence.get("verdict"), dict)
    )


def _accepted_formal_judge_evidence(evidence: dict[str, Any]) -> bool:
    """Admit only the frozen legacy or user-authorized future Judge profile."""

    if not isinstance(evidence, dict):
        return False
    is_future = (
        evidence.get("provider") == "cli_proxy"
        or "scope" in evidence
    )
    expected = (
        _FUTURE_CLI_PROXY_ACCEPTED_PROFILE
        if is_future
        else _LEGACY_DEEPSEEK_ACCEPTED_PROFILE
    )
    return bool(
        all(evidence.get(key) == value for key, value in expected.items())
        and type(evidence.get("provider_call_count")) is int
        and evidence["provider_call_count"] >= 1
        and type(evidence.get("retry_count")) is int
        and evidence["retry_count"] >= 0
        and isinstance(evidence.get("verdict"), dict)
    )


def _write_or_verify_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") != serialized:
            raise RuntimeError(f"refusing to overwrite different gate artifact: {target}")
        return
    with target.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(serialized)


def _safe_preflight_payload(result: dict[str, Any]) -> dict[str, Any]:
    request = dict(result.get("request") or {})
    extra_body = request.get("extra_body")
    extra_body = extra_body if isinstance(extra_body, dict) else {}
    thinking = extra_body.get("thinking")
    thinking = thinking if isinstance(thinking, dict) else {}
    messages = request.get("messages")
    roles = (
        [str(message.get("role") or "") for message in messages]
        if isinstance(messages, list)
        else []
    )
    return {
        "provider": result.get("provider"),
        "endpoint_type": result.get("endpoint_type"),
        "requested_model": result.get("requested_model"),
        "resolved_model": result.get("resolved_model"),
        "thinking_type": result.get("thinking_type"),
        "extra_body_thinking_type": thinking.get("type"),
        "reasoning_effort": result.get("reasoning_effort"),
        "status": result.get("status"),
        "parse_status": result.get("parse_status"),
        "decision": result.get("decision"),
        "provider_call_count": int(result.get("provider_call_count") or 0),
        "retry_count": int(result.get("retry_count") or 0),
        "fallback_allowed": result.get("fallback_allowed"),
        "fallback_used": result.get("fallback_used"),
        "response_format": request.get("response_format"),
        "max_tokens_present": "max_tokens" in request,
        "request_keys": sorted(key for key in request if key != "messages"),
        "message_roles": roles,
        "message_count": len(roles),
    }


def _preflight_payload_passes(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("provider") == "deepseek"
        and payload.get("endpoint_type") == "chat.completions"
        and payload.get("requested_model") == "deepseek-v4-pro"
        and payload.get("resolved_model") == "deepseek-v4-pro"
        and payload.get("thinking_type") == "enabled"
        and payload.get("extra_body_thinking_type") == "enabled"
        and payload.get("reasoning_effort") == "max"
        and payload.get("status") == "ready"
        and payload.get("parse_status") == "not_dispatched"
        and payload.get("provider_call_count") == 0
        and payload.get("fallback_allowed") is False
        and payload.get("fallback_used") is False
        and payload.get("response_format") == {"type": "json_object"}
        and payload.get("max_tokens_present") is False
        and payload.get("message_roles") == ["system", "user"]
    )
