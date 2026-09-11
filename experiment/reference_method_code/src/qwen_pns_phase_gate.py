from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class PnsPhaseGateDecision:
    """Fail-closed offline decision for the staged Qwen PNS experiment."""

    state: str
    reason_codes: tuple[str, ...]
    allowed_outputs: tuple[str, ...]
    phase56_complete: bool
    phase256_complete: bool = False


def evaluate_pns_phase_gate(manifest: Mapping[str, Any]) -> PnsPhaseGateDecision:
    """Evaluate an in-memory manifest without creating or changing artifacts."""

    preflight_reasons = _judge_preflight_reasons(manifest.get("judge_preflight"))
    if preflight_reasons:
        return _blocked("judge_preflight_blocked", preflight_reasons)

    inventory_reasons = _judge_inventory_reasons(manifest.get("judge_artifacts"))
    if inventory_reasons:
        return _blocked("judge_artifact_isolation_blocked", inventory_reasons)

    reasons = _phase_reasons(manifest.get("phase56"), expected=56, prefix="phase56")
    if reasons:
        return _blocked("phase56_blocked", reasons)
    judge_reasons = _phase56_judge_reasons(
        manifest["phase56"],
        manifest.get("judge_artifacts"),
        manifest["judge_preflight"]["judge_config_id"],
    )
    if judge_reasons:
        return _blocked("phase56_judge_blocked", judge_reasons)

    demo_pool = manifest.get("demo_pool")
    if demo_pool is None:
        return PnsPhaseGateDecision(
            state="demo_pool_required",
            reason_codes=(),
            allowed_outputs=("phase56_status", "freeze_demo_pool"),
            phase56_complete=True,
        )
    demo_reasons = _pool_reasons(demo_pool, expected=56, prefix="demo_pool")
    demo_reasons.extend(_demo_matches_phase56_reasons(manifest["phase56"], demo_pool))
    demo_reasons.extend(
        _artifact_reuse_reasons(manifest, ("judge_preflight", "demo_pool"))
    )
    if demo_reasons:
        return _blocked(
            "demo_pool_blocked", demo_reasons, phase56_complete=True
        )

    test100 = manifest.get("test100")
    if test100 is None:
        return PnsPhaseGateDecision(
            state="test100_pool_required",
            reason_codes=(),
            allowed_outputs=("phase56_status", "freeze_test100_pool"),
            phase56_complete=True,
        )
    test_reasons = _pool_reasons(test100, expected=100, prefix="test100")
    test_reasons.extend(
        _artifact_reuse_reasons(
            manifest, ("judge_preflight", "demo_pool", "test100")
        )
    )
    if test_reasons:
        return _blocked(
            "test100_pool_blocked", test_reasons, phase56_complete=True
        )
    overlap_reasons = _demo_test100_overlap_reasons(demo_pool, test100)
    if overlap_reasons:
        return _blocked(
            "demo_test100_overlap_blocked",
            overlap_reasons,
            phase56_complete=True,
        )

    matched_arms = manifest.get("test100_matched_arms")
    comparison_table = manifest.get("historical_comparison_table")
    if matched_arms is None and comparison_table is None:
        return PnsPhaseGateDecision(
            state="test100_evidence_required",
            reason_codes=(),
            allowed_outputs=(
                "phase56_status",
                "demo_test100_isolation_report",
                "freeze_test100_matched_arms",
                "freeze_historical_comparison_table",
            ),
            phase56_complete=True,
        )
    evidence_reasons = _matched_arms_reasons(matched_arms, test100)
    evidence_reasons.extend(
        _historical_comparison_reasons(
            comparison_table,
            test100=test100,
            matched_arms=matched_arms,
        )
    )
    evidence_reasons.extend(
        _artifact_reuse_reasons(
            manifest,
            (
                "judge_preflight",
                "demo_pool",
                "test100",
                "test100_matched_arms",
                "historical_comparison_table",
            ),
        )
    )
    if evidence_reasons:
        return _blocked(
            "test100_evidence_blocked",
            evidence_reasons,
            phase56_complete=True,
        )

    coarse_tuning = manifest.get("coarse_tuning")
    if coarse_tuning is None:
        return PnsPhaseGateDecision(
            state="coarse_tuning_directions_required",
            reason_codes=(),
            allowed_outputs=("unvalidated_coarse_tuning_directions",),
            phase56_complete=True,
        )
    coarse_reasons = _coarse_tuning_reasons(coarse_tuning)
    if coarse_reasons:
        return PnsPhaseGateDecision(
            state="coarse_tuning_blocked",
            reason_codes=tuple(dict.fromkeys(coarse_reasons)),
            allowed_outputs=("unvalidated_coarse_tuning_directions",),
            phase56_complete=True,
        )
    authorization = manifest.get("phase256_authorization")
    if authorization is None:
        if manifest.get("phase256") is not None:
            return PnsPhaseGateDecision(
                state="phase256_authorization_blocked",
                reason_codes=("phase256_user_confirmation_required",),
                allowed_outputs=("unvalidated_coarse_tuning_directions",),
                phase56_complete=True,
            )
        return PnsPhaseGateDecision(
            state="phase256_authorization_required",
            reason_codes=(),
            allowed_outputs=("unvalidated_coarse_tuning_directions",),
            phase56_complete=True,
        )
    authorization_reasons = _phase256_authorization_reasons(
        manifest, authorization
    )
    if authorization_reasons:
        return PnsPhaseGateDecision(
            state="phase256_authorization_blocked",
            reason_codes=tuple(dict.fromkeys(authorization_reasons)),
            allowed_outputs=("unvalidated_coarse_tuning_directions",),
            phase56_complete=True,
        )

    phase256 = manifest.get("phase256")
    if phase256 is None:
        return PnsPhaseGateDecision(
            state="phase256_ready",
            reason_codes=(),
            allowed_outputs=("phase256_execution",),
            phase56_complete=True,
        )
    frozen_config = authorization["frozen_config"]
    phase256_reasons: list[str] = []
    if (
        not isinstance(phase256, Mapping)
        or phase256.get("config_id") != frozen_config["config_id"]
    ):
        phase256_reasons.append("phase256_config_reference_mismatch")
    phase256_reasons.extend(
        _phase_reasons(phase256, expected=256, prefix="phase256")
    )
    if phase256_reasons:
        return PnsPhaseGateDecision(
            state="phase256_blocked",
            reason_codes=tuple(dict.fromkeys(phase256_reasons)),
            allowed_outputs=("phase256_status",),
            phase56_complete=True,
        )
    return PnsPhaseGateDecision(
        state="phase256_complete",
        reason_codes=(),
        allowed_outputs=("phase256_final_status",),
        phase56_complete=True,
        phase256_complete=True,
    )


def _blocked(
    state: str,
    reasons: Sequence[str],
    *,
    phase56_complete: bool = False,
) -> PnsPhaseGateDecision:
    return PnsPhaseGateDecision(
        state=state,
        reason_codes=tuple(dict.fromkeys(reasons)),
        allowed_outputs=("phase56_status",),
        phase56_complete=phase56_complete,
    )


def _pool_reasons(value: Any, *, expected: int, prefix: str) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"{prefix}_manifest_required"]
    reasons: list[str] = []
    if not isinstance(value.get("artifact"), str) or not value["artifact"].strip():
        reasons.append(f"{prefix}_artifact_required")
    if value.get("frozen") is not True:
        reasons.append(f"{prefix}_not_frozen")
    if value.get("expected") != expected:
        reasons.append(f"{prefix}_expected_must_be_{expected}")

    records = value.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        reasons.append(f"{prefix}_records_required")
        return reasons
    if len(records) != expected:
        reasons.append(f"{prefix}_record_count_must_be_{expected}")

    sample_ids: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            reasons.append(f"{prefix}_record_invalid")
            continue
        sample_id = record.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            reasons.append(f"{prefix}_record_sample_id_missing")
        else:
            sample_ids.append(sample_id)
        if "content" not in record:
            reasons.append(f"{prefix}_record_content_missing")
        elif not _has_meaningful_content(record.get("content")):
            reasons.append(f"{prefix}_record_content_empty")
    if len(sample_ids) != len(set(sample_ids)):
        reasons.append(f"{prefix}_duplicate_sample_id")
    return list(dict.fromkeys(reasons))


def _has_meaningful_content(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value) and any(_has_meaningful_content(item) for item in value.values())
    if _is_record_sequence(value):
        return bool(value) and any(_has_meaningful_content(item) for item in value)
    return value is not None


def _artifact_reuse_reasons(
    manifest: Mapping[str, Any], keys: Sequence[str]
) -> list[str]:
    artifacts = [
        value["artifact"]
        for key in keys
        if isinstance((value := manifest.get(key)), Mapping)
        and isinstance(value.get("artifact"), str)
        and value["artifact"].strip()
    ]
    if len(artifacts) != len(set(artifacts)):
        return ["pipeline_artifact_reused"]
    return []


def _demo_matches_phase56_reasons(
    phase56: Mapping[str, Any], demo_pool: Any
) -> list[str]:
    if not isinstance(demo_pool, Mapping):
        return []
    phase_records = phase56.get("records")
    demo_records = demo_pool.get("records")
    if not _is_record_sequence(phase_records) or not _is_record_sequence(demo_records):
        return []
    phase_by_id = {
        record.get("sample_id"): _normalized_content(record.get("content"))
        for record in phase_records
        if isinstance(record, Mapping) and isinstance(record.get("sample_id"), str)
    }
    demo_by_id = {
        record.get("sample_id"): _normalized_content(record.get("content"))
        for record in demo_records
        if isinstance(record, Mapping) and isinstance(record.get("sample_id"), str)
    }
    if phase_by_id != demo_by_id:
        return ["demo_pool_does_not_match_phase56"]
    return []


def _demo_test100_overlap_reasons(demo_pool: Any, test100: Any) -> list[str]:
    if not isinstance(demo_pool, Mapping) or not isinstance(test100, Mapping):
        return []
    demo_records = demo_pool.get("records")
    test_records = test100.get("records")
    if not _is_record_sequence(demo_records) or not _is_record_sequence(test_records):
        return []

    demo_ids = {
        record.get("sample_id")
        for record in demo_records
        if isinstance(record, Mapping) and isinstance(record.get("sample_id"), str)
    }
    test_ids = {
        record.get("sample_id")
        for record in test_records
        if isinstance(record, Mapping) and isinstance(record.get("sample_id"), str)
    }
    reasons: list[str] = []
    if demo_ids & test_ids:
        reasons.append("demo_test100_sample_id_overlap")

    demo_content = {
        _normalized_content(record.get("content"))
        for record in demo_records
        if isinstance(record, Mapping) and "content" in record
    }
    test_content = {
        _normalized_content(record.get("content"))
        for record in test_records
        if isinstance(record, Mapping) and "content" in record
    }
    if demo_content & test_content:
        reasons.append("demo_test100_content_overlap")
    return reasons


def _matched_arms_reasons(value: Any, test100: Mapping[str, Any]) -> list[str]:
    if not isinstance(value, Mapping):
        return ["test100_matched_arms_artifact_required"]
    reasons: list[str] = []
    if not isinstance(value.get("artifact"), str) or not value["artifact"].strip():
        reasons.append("test100_matched_arms_artifact_required")
    if value.get("frozen") is not True:
        reasons.append("test100_matched_arms_not_frozen")
    if value.get("expected") != 100:
        reasons.append("test100_matched_arms_expected_must_be_100")

    test_records = test100.get("records")
    test_ids = {
        record.get("sample_id")
        for record in test_records
        if isinstance(record, Mapping) and isinstance(record.get("sample_id"), str)
    }
    sample_ids = value.get("sample_ids")
    if not _is_record_sequence(sample_ids):
        reasons.append("test100_matched_arms_sample_ids_required")
    else:
        listed_ids = [item for item in sample_ids if isinstance(item, str)]
        if len(listed_ids) != 100 or set(listed_ids) != test_ids:
            reasons.append("test100_matched_arms_sample_ids_do_not_match_test100")

    arms = value.get("arms")
    arm_names: list[str] = []
    if not _is_record_sequence(arms):
        reasons.append("test100_matched_arms_requires_multiple_arms")
    else:
        arm_names = [item for item in arms if isinstance(item, str) and item.strip()]
        if len(set(arm_names)) < 2 or len(arm_names) != len(arms):
            reasons.append("test100_matched_arms_requires_multiple_arms")

    matched_records = value.get("matched_records")
    if not _is_record_sequence(matched_records):
        reasons.append("test100_matched_arms_records_required")
        return reasons
    matched_ids = [
        record.get("sample_id")
        for record in matched_records
        if isinstance(record, Mapping) and isinstance(record.get("sample_id"), str)
    ]
    if len(matched_ids) != 100 or set(matched_ids) != test_ids:
        reasons.append("test100_matched_arms_records_do_not_match_test100")

    result_artifact_ids: list[str] = []
    expected_arm_names = set(arm_names)
    for record in matched_records:
        if not isinstance(record, Mapping):
            reasons.append("test100_matched_arms_record_invalid")
            continue
        arm_results = record.get("arm_results")
        if not isinstance(arm_results, Mapping) or set(arm_results) != expected_arm_names:
            reasons.append("test100_matched_arms_record_arm_set_mismatch")
            continue
        for result in arm_results.values():
            if not isinstance(result, Mapping) or result.get("status") != "complete":
                reasons.append("test100_matched_arms_result_incomplete")
                continue
            artifact_id = result.get("artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id.strip():
                reasons.append("test100_matched_arms_result_artifact_missing")
            else:
                result_artifact_ids.append(artifact_id)
    if len(result_artifact_ids) != len(set(result_artifact_ids)):
        reasons.append("test100_matched_arms_duplicate_result_artifact")
    return reasons


def _historical_comparison_reasons(
    value: Any,
    *,
    test100: Mapping[str, Any],
    matched_arms: Any,
) -> list[str]:
    if not isinstance(value, Mapping):
        return ["historical_comparison_table_artifact_required"]
    reasons: list[str] = []
    if not isinstance(value.get("artifact"), str) or not value["artifact"].strip():
        reasons.append("historical_comparison_table_artifact_required")
    if value.get("frozen") is not True:
        reasons.append("historical_comparison_table_not_frozen")

    expected_test_artifact = test100.get("artifact")
    expected_arms_artifact = (
        matched_arms.get("artifact") if isinstance(matched_arms, Mapping) else None
    )
    if (
        value.get("test100_artifact") != expected_test_artifact
        or value.get("matched_arms_artifact") != expected_arms_artifact
    ):
        reasons.append("historical_comparison_table_artifact_reference_mismatch")

    arms = matched_arms.get("arms") if isinstance(matched_arms, Mapping) else []
    expected_arms = {
        item for item in arms if isinstance(item, str) and item.strip()
    }
    rows = value.get("rows")
    if not _is_record_sequence(rows):
        reasons.append("historical_comparison_table_rows_required")
    else:
        current_row_arms = {
            row.get("arm")
            for row in rows
            if isinstance(row, Mapping)
            and row.get("row_type") == "current"
            and row.get("sample_count") == 100
            and isinstance(row.get("metrics"), Mapping)
            and bool(row["metrics"])
        }
        if not expected_arms or not expected_arms.issubset(current_row_arms):
            reasons.append("historical_comparison_table_missing_matched_arms")
        has_historical_row = any(
            isinstance(row, Mapping)
            and row.get("row_type") == "historical"
            and isinstance(row.get("source_label"), str)
            and bool(row["source_label"].strip())
            and isinstance(row.get("metrics"), Mapping)
            and bool(row["metrics"])
            for row in rows
        )
        if not has_historical_row:
            reasons.append("historical_comparison_table_historical_row_required")
    return reasons


def _coarse_tuning_reasons(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["coarse_tuning_manifest_required"]
    reasons: list[str] = []
    allowed_keys = {"output_kind", "validation_status", "directions"}
    if not set(value).issubset(allowed_keys):
        reasons.append("coarse_tuning_contains_non_coarse_claims")
    if value.get("output_kind") != "unvalidated_coarse_tuning_directions":
        reasons.append("coarse_tuning_output_kind_invalid")
    if value.get("validation_status") != "unvalidated":
        reasons.append("coarse_tuning_must_remain_unvalidated")
    directions = value.get("directions")
    if not _is_record_sequence(directions) or not directions:
        reasons.append("coarse_tuning_directions_required")
    elif any(not isinstance(item, str) or not item.strip() for item in directions):
        reasons.append("coarse_tuning_directions_required")
    return reasons


def _phase256_authorization_reasons(
    manifest: Mapping[str, Any], value: Any
) -> list[str]:
    if not isinstance(value, Mapping):
        return ["phase256_authorization_manifest_required"]
    reasons: list[str] = []
    if value.get("user_confirmed") is not True:
        reasons.append("phase256_user_confirmation_required")
    if value.get("completed_before_phase256") is not True:
        reasons.append("phase256_authorization_not_before_execution")

    config = value.get("frozen_config")
    if not isinstance(config, Mapping):
        reasons.append("phase256_config_artifact_required")
        return reasons
    artifact = config.get("artifact")
    if not isinstance(artifact, str) or not artifact.strip():
        reasons.append("phase256_config_artifact_required")
    if config.get("frozen") is not True:
        reasons.append("phase256_config_not_frozen")
    if config.get("phase") != "phase256":
        reasons.append("phase256_config_scope_invalid")
    config_id = config.get("config_id")
    if not isinstance(config_id, str) or not config_id.strip():
        reasons.append("phase256_config_id_required")
    parameters = config.get("parameters")
    if not isinstance(parameters, Mapping) or not parameters:
        reasons.append("phase256_config_parameters_required")

    prior_artifacts = {
        prior.get("artifact")
        for key in (
            "judge_preflight",
            "demo_pool",
            "test100",
            "test100_matched_arms",
            "historical_comparison_table",
        )
        if isinstance((prior := manifest.get(key)), Mapping)
    }
    if artifact in prior_artifacts:
        reasons.append("phase256_config_not_separate")
    return reasons


def _normalized_content(value: Any) -> str:
    """Return a readable, deterministic key without creating hash artifacts."""

    def normalize(item: Any) -> Any:
        if isinstance(item, str):
            return " ".join(item.split())
        if isinstance(item, Mapping):
            return {str(key): normalize(item[key]) for key in sorted(item, key=str)}
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            return [normalize(child) for child in item]
        return item

    return json.dumps(
        normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _is_record_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _valid_deepseek_judge_runtime_metadata(value: Mapping[str, Any]) -> bool:
    exact = {
        "provider": "deepseek",
        "endpoint_type": "chat.completions",
        "requested_model": "deepseek-v4-pro",
        "resolved_model": "deepseek-v4-pro",
        "response_model": "deepseek-v4-pro",
        "thinking_type": "enabled",
        "reasoning_effort": "max",
        "parse_status": "parsed",
        "decision": "accepted",
        "accepted": True,
        "fallback_allowed": False,
        "fallback_used": False,
    }
    if any(value.get(key) != expected for key, expected in exact.items()):
        return False
    provider_calls = value.get("provider_call_count")
    retry_count = value.get("retry_count")
    return bool(
        type(provider_calls) is int
        and provider_calls >= 1
        and type(retry_count) is int
        and retry_count >= 0
        and provider_calls == retry_count + 1
    )


def _judge_preflight_reasons(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["judge_preflight_artifact_required"]
    reasons: list[str] = []
    if not isinstance(value.get("artifact"), str) or not value["artifact"].strip():
        reasons.append("judge_preflight_artifact_required")
    if (
        not isinstance(value.get("judge_config_id"), str)
        or not value["judge_config_id"].strip()
    ):
        reasons.append("judge_preflight_config_id_required")
    if value.get("preflight_canary_passed") is not True:
        reasons.append("judge_preflight_canary_not_passed")
    if value.get("completed_before_live56") is not True:
        reasons.append("judge_preflight_not_before_live56")
    if not _valid_deepseek_judge_runtime_metadata(value):
        reasons.append("judge_preflight_runtime_metadata_invalid")
    return reasons


def _judge_inventory_reasons(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ["judge_artifact_inventory_required"]
    forbidden = {"legacy_gpt", "disabled", "skipped", "unresolved"}
    reasons: list[str] = []
    for artifact in value:
        if not isinstance(artifact, Mapping):
            reasons.append("judge_artifact_inventory_entry_invalid")
            continue
        if artifact.get("status") in forbidden and (
            artifact.get("isolated") is not True or artifact.get("counted") is not False
        ):
            reasons.append("judge_legacy_or_unresolved_artifact_not_isolated")
    return reasons


def _phase56_judge_reasons(
    value: Mapping[str, Any], inventory: Any, judge_config_id: str
) -> list[str]:
    reasons: list[str] = []
    records = value.get("records")
    assert isinstance(records, Sequence) and not isinstance(records, (str, bytes))
    excluded_statuses = {"legacy_gpt", "disabled", "skipped", "unresolved"}
    excluded_artifact_ids = {
        artifact.get("artifact_id")
        for artifact in inventory
        if isinstance(artifact, Mapping)
        and artifact.get("status") in excluded_statuses
        and isinstance(artifact.get("artifact_id"), str)
    }
    current_inventory = {
        artifact.get("artifact_id"): artifact
        for artifact in inventory
        if isinstance(artifact, Mapping)
        and artifact.get("current") is True
        and artifact.get("counted") is True
        and isinstance(artifact.get("artifact_id"), str)
    }
    first_sample_id = records[0].get("sample_id") if records and isinstance(records[0], Mapping) else None
    first_judge = records[0].get("judge") if records and isinstance(records[0], Mapping) else None
    first_judge_artifact_id = (
        first_judge.get("artifact_id") if isinstance(first_judge, Mapping) else None
    )
    gate = value.get("judge_start_gate")
    if not isinstance(gate, Mapping):
        reasons.append("phase56_first_accepted_judge_gate_required")
    else:
        if not isinstance(gate.get("artifact"), str) or not gate["artifact"].strip():
            reasons.append("phase56_first_accepted_judge_gate_required")
        if gate.get("first_accepted_sample_id") != first_sample_id:
            reasons.append("phase56_first_accepted_judge_sample_mismatch")
        if gate.get("judge_config_id") != judge_config_id:
            reasons.append("phase56_first_accepted_judge_config_mismatch")
        if gate.get("first_accepted_judge_artifact_id") != first_judge_artifact_id:
            reasons.append("phase56_first_accepted_judge_artifact_mismatch")
        if gate.get("judge_metadata_validated") is not True:
            reasons.append("phase56_first_accepted_judge_metadata_not_validated")

    record_judge_artifact_ids: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        judge = record.get("judge")
        if not isinstance(judge, Mapping):
            reasons.append("phase56_record_judge_required")
            continue
        if judge.get("status") != "validated_pass":
            reasons.append("phase56_record_judge_status_invalid")
        if judge.get("passed") is not True:
            reasons.append("phase56_record_judge_not_passed")
        if judge.get("metadata_validated") is not True:
            reasons.append("phase56_record_judge_metadata_invalid")
        if not _valid_deepseek_judge_runtime_metadata(judge):
            reasons.append("phase56_record_judge_runtime_metadata_invalid")
        if judge.get("config_id") != judge_config_id:
            reasons.append("phase56_record_judge_config_mismatch")
        if judge.get("sample_id") != record.get("sample_id"):
            reasons.append("phase56_record_judge_sample_mismatch")
        artifact_id = judge.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            reasons.append("phase56_record_judge_artifact_missing")
            continue
        record_judge_artifact_ids.append(artifact_id)
        if artifact_id in excluded_artifact_ids:
            reasons.append("phase56_record_judge_artifact_excluded")
        inventory_entry = current_inventory.get(artifact_id)
        if not isinstance(inventory_entry, Mapping):
            reasons.append("phase56_record_judge_not_in_current_inventory")
            continue
        if (
            inventory_entry.get("status") != "validated_pass"
            or inventory_entry.get("passed") is not True
            or inventory_entry.get("metadata_validated") is not True
        ):
            reasons.append("phase56_current_judge_inventory_status_invalid")
        if not _valid_deepseek_judge_runtime_metadata(inventory_entry):
            reasons.append(
                "phase56_current_judge_inventory_runtime_metadata_invalid"
            )
        if inventory_entry.get("config_id") != judge_config_id:
            reasons.append("phase56_current_judge_inventory_config_mismatch")
        if inventory_entry.get("sample_id") != record.get("sample_id"):
            reasons.append("phase56_current_judge_inventory_sample_mismatch")

    if len(record_judge_artifact_ids) != len(set(record_judge_artifact_ids)):
        reasons.append("phase56_duplicate_judge_artifact")
    if set(record_judge_artifact_ids) != set(current_inventory):
        reasons.append("phase56_current_judge_inventory_mismatch")
    return reasons


def _phase_reasons(value: Any, *, expected: int, prefix: str) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"{prefix}_manifest_required"]
    reasons: list[str] = []
    if value.get("expected") != expected:
        reasons.append(f"{prefix}_expected_must_be_{expected}")
    if value.get("accepted") != expected:
        reasons.append(f"{prefix}_accepted_must_be_{expected}")
    if value.get("complete_trajectories") != expected:
        reasons.append(f"{prefix}_complete_trajectories_must_be_{expected}")

    records = value.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        reasons.append(f"{prefix}_records_required")
        return reasons
    if len(records) != expected:
        reasons.append(f"{prefix}_record_count_must_be_{expected}")

    sample_ids: list[str] = []
    trajectory_artifact_ids: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            reasons.append(f"{prefix}_record_invalid")
            continue
        sample_id = record.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            reasons.append(f"{prefix}_record_sample_id_missing")
        else:
            sample_ids.append(sample_id)
        if record.get("accepted") is not True:
            reasons.append(f"{prefix}_record_not_accepted")
        if record.get("optimized") is not True or record.get("fallback") is not False:
            reasons.append(f"{prefix}_record_not_strictly_optimized")
        parent_tokens = record.get("parent_qwen_tokens")
        final_tokens = record.get("final_qwen_tokens")
        if (
            type(parent_tokens) is not int
            or type(final_tokens) is not int
            or parent_tokens < 1
            or final_tokens < 1
            or final_tokens >= parent_tokens
        ):
            reasons.append(f"{prefix}_record_not_strictly_shorter")
        if record.get("trajectory_complete") is not True:
            reasons.append(f"{prefix}_record_trajectory_incomplete")
        trajectory_artifact_id = record.get("trajectory_artifact_id")
        if (
            not isinstance(trajectory_artifact_id, str)
            or not trajectory_artifact_id.strip()
        ):
            reasons.append(f"{prefix}_record_trajectory_artifact_missing")
        else:
            trajectory_artifact_ids.append(trajectory_artifact_id)
        if record.get("trajectory_status") != "complete":
            reasons.append(f"{prefix}_record_trajectory_status_invalid")
        if record.get("trajectory_sample_id") != sample_id:
            reasons.append(f"{prefix}_record_trajectory_sample_mismatch")
    if len(sample_ids) != len(set(sample_ids)):
        reasons.append(f"{prefix}_duplicate_sample_id")
    if len(trajectory_artifact_ids) != len(set(trajectory_artifact_ids)):
        reasons.append(f"{prefix}_duplicate_trajectory_artifact")
    return list(dict.fromkeys(reasons))
