from __future__ import annotations

import concurrent.futures
import json
import os
import re
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Literal, Sequence


POLICY_VERSION = "qwen_pns_adaptive_rollout_v2_3to5"
MAX7_RECOVERY_AMENDMENT_ID = "qwen_pns_phase56_max7_recovery_18plus3_v1"
BRANCH_CODES = {"keep": 1, "delete": 2, "replace": 3, "replacement_generate": 4}

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
_LEGACY_CLI_PROXY_RECOVERY_ACCEPTED_PROFILE = {
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
    "protocol_revision": "responses_xhigh_strict_json_schema_v1",
    "switch_reason": "user_specified_backup_judge",
    "scientific_raw_attempt_delta": 0,
    "recovery_generation": 1,
    "provider_call_count": 1,
    "retry_count": 0,
    "status": "parsed",
    "parse_status": "parsed",
    "decision": "accepted",
    "accepted": True,
    "fallback_allowed": False,
    "fallback_used": False,
}

DecisionAction = Literal[
    "continue", "trigger_replace", "do_not_trigger", "inconclusive_operational"
]
Lineage = Literal["keep", "delete"]


class RolloutInfrastructureError(RuntimeError):
    """Fatal endpoint failure that must stop a run instead of consuming votes."""


@dataclass(frozen=True)
class AdaptiveRolloutConfig:
    """Precommitted limits for Qwen KEEP/DELETE PNS rollouts.

    The default horizon is five *matched valid* rounds. Operationally invalid
    generations do not vote and are bounded separately by the raw-attempt cap.
    """

    initial_valid_rounds: int = 3
    max_valid_rounds: int = 5
    max_raw_attempts_per_lineage: int = 5
    raw_attempt_recovery_amendment: str | None = None

    def validate(self) -> None:
        if self.initial_valid_rounds != 3 or self.max_valid_rounds != 5:
            raise ValueError("rollout protocol is frozen to the 3-then-5 horizon")
        if self.max_raw_attempts_per_lineage not in {5, 7}:
            raise ValueError(
                "raw attempt cap must be five or seven; seven is reserved for an "
                "explicit recovery amendment"
            )
        if self.max_raw_attempts_per_lineage == 7 and (
            self.raw_attempt_recovery_amendment != MAX7_RECOVERY_AMENDMENT_ID
        ):
            raise ValueError(
                "seven raw attempts require the explicit recovery amendment"
            )
        if self.max_raw_attempts_per_lineage == 5 and (
            self.raw_attempt_recovery_amendment is not None
        ):
            raise ValueError("the base max-five config cannot name a recovery amendment")


@dataclass(frozen=True)
class AdaptiveSeedSchedule:
    """Extend raw slots without changing any pre-amendment r0-r5 seed."""

    base_seed: int = 20_260_817
    step_radix: int = 256
    branch_radix: int = 8
    legacy_rollout_radix: int = 4
    extension_base_seed: int = 1_000_000_000
    extension_rollout_slots: int = 2
    recovery_extension_base_seed: int = 1_500_000_000
    recovery_extension_rollout_slots: int = 2

    def derive(self, qid: int, step: int, branch: str, rollout: int) -> int:
        if not 0 <= qid < 65_536:
            raise ValueError(f"qid out of range: {qid}")
        if not 0 <= step < self.step_radix:
            raise ValueError(f"step out of range: {step}")
        if branch not in BRANCH_CODES:
            raise ValueError(f"unknown branch: {branch}")
        if not 0 <= rollout <= 7:
            raise ValueError(f"rollout out of range: {rollout}")
        cell = (qid * self.step_radix + step) * self.branch_radix + BRANCH_CODES[branch]
        if rollout < self.legacy_rollout_radix:
            seed = self.base_seed + cell * self.legacy_rollout_radix + rollout
        elif rollout < (
            self.legacy_rollout_radix + self.extension_rollout_slots
        ):
            seed = (
                self.extension_base_seed
                + cell * self.extension_rollout_slots
                + rollout
                - self.legacy_rollout_radix
            )
        else:
            seed = (
                self.recovery_extension_base_seed
                + cell * self.recovery_extension_rollout_slots
                + rollout
                - self.legacy_rollout_radix
                - self.extension_rollout_slots
            )
        if seed >= 2_147_483_647:
            raise ValueError("seed exceeds signed 32-bit range")
        return seed


@dataclass(frozen=True)
class KeepDeleteDecision:
    action: DecisionAction
    stop: bool
    stop_reason: str | None
    valid_rounds: int
    keep_correct: int
    delete_correct: int
    difference: int
    remaining_rounds: int


@dataclass(frozen=True)
class RolloutTrial:
    """One raw generation result before it is admitted as a scientific vote."""

    valid_for_vote: bool
    correct: bool | None = None
    candidate_id: str | None = None
    request_key: str | None = None
    reasoning: str = ""
    final_content: str = ""
    predicted_answer: str | None = None
    reasoning_tokens: int | None = None
    reasoning_chars: int | None = None
    candidate_eligible: bool = False
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrialRecord:
    lineage: str
    matched_round: int
    raw_attempt: int
    valid_trial_index: int | None
    admitted_to_decision: bool
    trial: RolloutTrial


@dataclass(frozen=True)
class AdaptiveKeepDeleteResult:
    policy_version: str
    decision: KeepDeleteDecision
    observations: tuple[TrialRecord, ...]
    decision_trace: tuple[KeepDeleteDecision, ...]
    raw_attempt_counts: dict[str, int]
    invalid_counts: dict[str, int]


TrialGenerator = Callable[[Lineage, int, int], RolloutTrial]


CandidateDecisionAction = Literal[
    "continue", "accept", "reject", "positive_no_candidate", "inconclusive_operational"
]


@dataclass(frozen=True)
class CandidateDecision:
    action: CandidateDecisionAction
    stop: bool
    stop_reason: str | None
    valid_trials: int
    correct_votes: int
    incorrect_votes: int
    majority_threshold: int
    eligible_candidate_count: int


@dataclass(frozen=True)
class AdaptiveCandidateResult:
    policy_version: str
    lineage: str
    decision: CandidateDecision
    observations: tuple[TrialRecord, ...]
    decision_trace: tuple[CandidateDecision, ...]
    selected_trial: TrialRecord | None
    raw_attempt_count: int
    invalid_count: int


CandidateTrialGenerator = Callable[[str, int, int], RolloutTrial]


@dataclass(frozen=True)
class QwenPnsCotParent:
    """Frozen Qwen parent chain needed by the compatible PNSCoT artifact."""

    question_id: Any
    query_type: str
    original_cot: str
    parent_answer: str
    original_qwen_tokens: int
    parent_audit: dict[str, Any]

    def validate(self) -> None:
        if not self.original_cot:
            raise ValueError("original_cot is required")
        if _normalize_answer(self.parent_answer) is None:
            raise ValueError("parent_answer must be yes or no")
        if self.original_qwen_tokens < 0:
            raise ValueError("original_qwen_tokens must be non-negative")
        if not _audit_passed(self.parent_audit):
            raise ValueError("parent_audit must pass so fallback remains safe")


@dataclass(frozen=True)
class ReplacementGeneration:
    valid: bool
    replacement_text: str = ""
    request_key: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdaptivePnsStepResult:
    step_index: int
    keep_delete: AdaptiveKeepDeleteResult
    replacement_generation: ReplacementGeneration | None
    replacement: AdaptiveCandidateResult | None


@dataclass(frozen=True)
class AdaptivePnsCotRunResult:
    policy_version: str
    step_results: tuple[AdaptivePnsStepResult, ...]
    ranked_candidates: tuple[TrialRecord, ...]
    selected_trial: TrialRecord | None
    artifact: dict[str, Any]


PnsTrialGenerator = Callable[[int, str, int, int, str | None], RolloutTrial]
ReplacementGenerator = Callable[[int], ReplacementGeneration]


def decide_keep_delete(
    keep_votes: Sequence[bool],
    delete_votes: Sequence[bool],
    *,
    config: AdaptiveRolloutConfig | None = None,
) -> KeepDeleteDecision:
    """Decide whether KEEP can finish strictly ahead of DELETE.

    Inputs contain only valid scientific votes and must be paired. The decision
    stops early only when the sign of ``KEEP - DELETE`` can no longer change
    under the precommitted valid-round horizon.
    """

    policy = config or AdaptiveRolloutConfig()
    policy.validate()
    if len(keep_votes) != len(delete_votes):
        raise ValueError("KEEP and DELETE votes must be matched by valid round")
    valid_rounds = len(keep_votes)
    if valid_rounds > policy.max_valid_rounds:
        raise ValueError("valid vote count exceeds max_valid_rounds")

    keep_correct = sum(bool(value) for value in keep_votes)
    delete_correct = sum(bool(value) for value in delete_votes)
    difference = keep_correct - delete_correct
    remaining = policy.max_valid_rounds - valid_rounds

    action: DecisionAction = "continue"
    stop = False
    stop_reason: str | None = None
    if valid_rounds >= policy.initial_valid_rounds:
        if valid_rounds == policy.max_valid_rounds:
            stop = True
            if difference > 0:
                action = "trigger_replace"
                stop_reason = "max_valid_positive"
            else:
                action = "do_not_trigger"
                stop_reason = "max_valid_tie_or_negative"
        elif (
            valid_rounds == policy.initial_valid_rounds
            and difference > remaining
        ):
            action = "trigger_replace"
            stop = True
            stop_reason = "positive_locked"
        elif (
            valid_rounds == policy.initial_valid_rounds
            and difference + remaining <= 0
        ):
            action = "do_not_trigger"
            stop = True
            stop_reason = "nonpositive_locked"

    return KeepDeleteDecision(
        action=action,
        stop=stop,
        stop_reason=stop_reason,
        valid_rounds=valid_rounds,
        keep_correct=keep_correct,
        delete_correct=delete_correct,
        difference=difference,
        remaining_rounds=remaining,
    )


def run_adaptive_keep_delete(
    generate: TrialGenerator,
    *,
    config: AdaptiveRolloutConfig | None = None,
) -> AdaptiveKeepDeleteResult:
    """Collect matched valid KEEP/DELETE rounds until their sign is locked.

    Invalid generations are retained in ``observations`` for audit but do not
    enter either vote list. Each lineage has an independent raw-attempt cap.
    """

    policy = config or AdaptiveRolloutConfig()
    policy.validate()
    votes: dict[Lineage, list[bool]] = {"keep": [], "delete": []}
    raw_attempts: dict[Lineage, int] = {"keep": 0, "delete": 0}
    invalid_counts: dict[Lineage, int] = {"keep": 0, "delete": 0}
    observations: list[TrialRecord] = []
    trace: list[KeepDeleteDecision] = []

    for matched_round in range(1, policy.max_valid_rounds + 1):
        paired_trials: dict[Lineage, RolloutTrial] = {}
        paired_record_indexes: dict[Lineage, int] = {}
        for lineage in ("keep", "delete"):
            while raw_attempts[lineage] < policy.max_raw_attempts_per_lineage:
                raw_attempts[lineage] += 1
                raw_attempt = raw_attempts[lineage]
                try:
                    trial = generate(lineage, matched_round, raw_attempt)
                except RolloutInfrastructureError:
                    raise
                except Exception as exc:
                    trial = RolloutTrial(
                        valid_for_vote=False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                if not isinstance(trial, RolloutTrial):
                    raise TypeError("generate must return RolloutTrial")
                if trial.valid_for_vote and trial.correct is None:
                    raise ValueError(
                        "a valid rollout trial must have a correctness vote"
                    )
                observations.append(
                    TrialRecord(
                        lineage=lineage,
                        matched_round=matched_round,
                        raw_attempt=raw_attempt,
                        valid_trial_index=None,
                        admitted_to_decision=False,
                        trial=trial,
                    )
                )
                if trial.valid_for_vote:
                    paired_trials[lineage] = trial
                    paired_record_indexes[lineage] = len(observations) - 1
                    break
                invalid_counts[lineage] += 1

            if lineage not in paired_trials:
                decision = _operationally_inconclusive(votes, policy)
                return AdaptiveKeepDeleteResult(
                    policy_version=POLICY_VERSION,
                    decision=decision,
                    observations=tuple(observations),
                    decision_trace=tuple(trace),
                    raw_attempt_counts=dict(raw_attempts),
                    invalid_counts=dict(invalid_counts),
                )

        for lineage in ("keep", "delete"):
            record_index = paired_record_indexes[lineage]
            observations[record_index] = replace(
                observations[record_index],
                valid_trial_index=len(votes[lineage]) + 1,
                admitted_to_decision=True,
            )
        votes["keep"].append(bool(paired_trials["keep"].correct))
        votes["delete"].append(bool(paired_trials["delete"].correct))
        decision = decide_keep_delete(votes["keep"], votes["delete"], config=policy)
        trace.append(decision)
        if decision.stop:
            return AdaptiveKeepDeleteResult(
                policy_version=POLICY_VERSION,
                decision=decision,
                observations=tuple(observations),
                decision_trace=tuple(trace),
                raw_attempt_counts=dict(raw_attempts),
                invalid_counts=dict(invalid_counts),
            )

    raise AssertionError(
        "adaptive KEEP/DELETE loop exhausted without a terminal decision"
    )


def run_adaptive_candidate_lineage(
    lineage: str,
    generate: CandidateTrialGenerator,
    *,
    parent: QwenPnsCotParent,
    config: AdaptiveRolloutConfig | None = None,
) -> AdaptiveCandidateResult:
    """Qualify one generated lineage by an adaptive bounded majority vote.

    A positive majority is exportable only when at least one individually
    correct, shorter, audited candidate has been marked ``candidate_eligible``.
    """

    if not lineage.strip():
        raise ValueError("lineage is required")
    parent.validate()
    policy = config or AdaptiveRolloutConfig()
    policy.validate()
    majority = policy.max_valid_rounds // 2 + 1
    observations: list[TrialRecord] = []
    trace: list[CandidateDecision] = []
    valid_records: list[TrialRecord] = []
    raw_attempt = 0
    invalid_count = 0

    for valid_target in range(1, policy.max_valid_rounds + 1):
        record: TrialRecord | None = None
        while raw_attempt < policy.max_raw_attempts_per_lineage:
            raw_attempt += 1
            try:
                trial = generate(lineage, valid_target, raw_attempt)
            except RolloutInfrastructureError:
                raise
            except Exception as exc:
                trial = RolloutTrial(
                    valid_for_vote=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            if not isinstance(trial, RolloutTrial):
                raise TypeError("generate must return RolloutTrial")
            if trial.valid_for_vote and trial.correct is None:
                raise ValueError("a valid rollout trial must have a correctness vote")
            record = TrialRecord(
                lineage=lineage,
                matched_round=valid_target,
                raw_attempt=raw_attempt,
                valid_trial_index=valid_target if trial.valid_for_vote else None,
                admitted_to_decision=trial.valid_for_vote,
                trial=trial,
            )
            observations.append(record)
            if trial.valid_for_vote:
                valid_records.append(record)
                break
            invalid_count += 1

        if record is None or not record.trial.valid_for_vote:
            decision = _candidate_decision(
                valid_records,
                parent=parent,
                majority=majority,
                minimum_valid=policy.initial_valid_rounds,
                max_valid=policy.max_valid_rounds,
                operationally_inconclusive=True,
            )
            return AdaptiveCandidateResult(
                policy_version=POLICY_VERSION,
                lineage=lineage,
                decision=decision,
                observations=tuple(observations),
                decision_trace=tuple(trace),
                selected_trial=None,
                raw_attempt_count=raw_attempt,
                invalid_count=invalid_count,
            )

        decision = _candidate_decision(
            valid_records,
            parent=parent,
            majority=majority,
            minimum_valid=policy.initial_valid_rounds,
            max_valid=policy.max_valid_rounds,
        )
        trace.append(decision)
        if decision.stop:
            eligible = _eligible_candidate_records(valid_records, parent)
            return AdaptiveCandidateResult(
                policy_version=POLICY_VERSION,
                lineage=lineage,
                decision=decision,
                observations=tuple(observations),
                decision_trace=tuple(trace),
                selected_trial=eligible[0] if decision.action == "accept" else None,
                raw_attempt_count=raw_attempt,
                invalid_count=invalid_count,
            )

    raise AssertionError(
        "adaptive candidate loop exhausted without a terminal decision"
    )


def build_optimized_pnscot_artifact(
    parent: QwenPnsCotParent,
    candidate_result: AdaptiveCandidateResult | None,
    *,
    full_pns_asset: dict[str, Any],
) -> dict[str, Any]:
    """Build the existing Qwen demo PNSCoT schema with a safe parent fallback."""

    parent.validate()
    _validate_full_pns_asset(full_pns_asset, question_id=parent.question_id)
    selected_record = (
        candidate_result.selected_trial
        if candidate_result is not None and candidate_result.decision.action == "accept"
        else None
    )
    selected_trial = selected_record.trial if selected_record is not None else None
    selected_audit = (
        selected_trial.metadata.get("audit")
        if selected_trial is not None
        and isinstance(selected_trial.metadata.get("audit"), dict)
        else None
    )
    optimized = bool(
        selected_record is not None and _record_exportable(parent, selected_record)
    )

    if optimized:
        assert selected_trial is not None
        final_cot = selected_trial.reasoning
        final_tokens = int(selected_trial.reasoning_tokens or 0)
        selected_candidate = selected_trial.candidate_id
        selected_request_key = selected_trial.request_key
        audit = dict(selected_audit or {})
    else:
        final_cot = parent.original_cot
        final_tokens = parent.original_qwen_tokens
        selected_candidate = "parent_original"
        selected_request_key = None
        audit = dict(parent.parent_audit)

    rollout_metadata: dict[str, Any] = {
        "policy_version": POLICY_VERSION,
        "action": candidate_result.decision.action
        if candidate_result
        else "parent_fallback",
        "stop_reason": candidate_result.decision.stop_reason
        if candidate_result
        else "no_candidate_lineage",
    }
    if candidate_result is not None:
        rollout_metadata.update(
            {
                "lineage": candidate_result.lineage,
                "valid_trials": candidate_result.decision.valid_trials,
                "correct_votes": candidate_result.decision.correct_votes,
                "incorrect_votes": candidate_result.decision.incorrect_votes,
                "raw_attempt_count": candidate_result.raw_attempt_count,
                "invalid_count": candidate_result.invalid_count,
                "selected_valid_trial_index": (
                    selected_record.valid_trial_index
                    if optimized and selected_record
                    else None
                ),
            }
        )

    artifact = {
        "schema_version": 1,
        "question_id": parent.question_id,
        "query_type": parent.query_type,
        "original_cot": parent.original_cot,
        "final_cot": final_cot,
        "original_qwen_tokens": parent.original_qwen_tokens,
        "final_qwen_tokens": final_tokens,
        "optimized": optimized,
        "fallback": not optimized,
        "selected_candidate": selected_candidate,
        "selected_request_key": selected_request_key,
        "audit": audit,
        "adaptive_rollout": rollout_metadata,
    }
    artifact["full_pns_asset"] = dict(full_pns_asset)
    return artifact


def generate_optimized_pnscot(
    parent: QwenPnsCotParent,
    *,
    eligible_step_indexes: Sequence[int],
    generate: PnsTrialGenerator,
    generate_replacement: ReplacementGenerator,
    full_pns_asset: dict[str, Any],
    config: AdaptiveRolloutConfig | None = None,
    step_workers: int = 1,
) -> AdaptivePnsCotRunResult:
    """Run adaptive KEEP/DELETE/REPLACE steps and materialize one PNSCoT.

    ``generate`` is the provider adapter boundary. It receives the one-based
    step index, ``keep``/``delete``/``replace``, the requested valid round, and
    the raw attempt index. The core never exposes gold data to that callback.
    """

    parent.validate()
    policy = config or AdaptiveRolloutConfig()
    policy.validate()
    steps = [int(step) for step in eligible_step_indexes]
    if any(step < 1 for step in steps) or len(set(steps)) != len(steps):
        raise ValueError("eligible_step_indexes must be unique positive integers")
    if step_workers < 1:
        raise ValueError("step_workers must be positive")

    def run_step(
        step_index: int,
    ) -> tuple[
        AdaptivePnsStepResult,
        list[tuple[TrialRecord, AdaptiveCandidateResult | None]],
    ]:
        pair = run_adaptive_keep_delete(
            lambda lineage, valid_round, raw_attempt, step=step_index: generate(
                step, lineage, valid_round, raw_attempt, None
            ),
            config=policy,
        )
        replacement_generation: ReplacementGeneration | None = None
        replacement: AdaptiveCandidateResult | None = None
        if pair.decision.action == "trigger_replace":
            try:
                replacement_generation = generate_replacement(step_index)
            except RolloutInfrastructureError:
                raise
            except Exception as exc:
                replacement_generation = ReplacementGeneration(
                    valid=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            if not isinstance(replacement_generation, ReplacementGeneration):
                raise TypeError(
                    "generate_replacement must return ReplacementGeneration"
                )
            if (
                replacement_generation.valid
                and not replacement_generation.replacement_text.strip()
            ):
                replacement_generation = replace(
                    replacement_generation,
                    valid=False,
                    error=replacement_generation.error or "empty_replacement_text",
                )
            if (
                replacement_generation.valid
                and replacement_generation.replacement_text.strip()
            ):
                frozen_replacement = replacement_generation.replacement_text
                replacement = run_adaptive_candidate_lineage(
                    f"replace_s{step_index}",
                    lambda _lineage, valid_round, raw_attempt, step=step_index: (
                        generate(
                            step,
                            "replace",
                            valid_round,
                            raw_attempt,
                            frozen_replacement,
                        )
                    ),
                    parent=parent,
                    config=policy,
                )

        step_exportable: list[
            tuple[TrialRecord, AdaptiveCandidateResult | None]
        ] = []
        for record in pair.observations:
            if _record_exportable(parent, record):
                step_exportable.append((record, None))
        if replacement is not None and replacement.selected_trial is not None:
            if _record_exportable(parent, replacement.selected_trial):
                step_exportable.append((replacement.selected_trial, replacement))
        return (
            AdaptivePnsStepResult(
                step_index=step_index,
                keep_delete=pair,
                replacement_generation=replacement_generation,
                replacement=replacement,
            ),
            step_exportable,
        )

    if step_workers == 1 or len(steps) < 2:
        completed_steps = [run_step(step) for step in steps]
    else:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(step_workers, len(steps))
        ) as pool:
            completed_steps = list(pool.map(run_step, steps))

    step_results = [result for result, _candidates in completed_steps]
    exportable = [
        candidate
        for _result, candidates in completed_steps
        for candidate in candidates
    ]

    exportable.sort(key=lambda item: _candidate_sort_key(item[0]))
    selected_record = exportable[0][0] if exportable else None
    selected_result = exportable[0][1] if exportable else None
    if selected_record is not None and selected_result is None:
        selected_result = _synthetic_selected_result(
            selected_record, step_results, policy, parent
        )

    artifact = build_optimized_pnscot_artifact(
        parent,
        selected_result,
        full_pns_asset=full_pns_asset,
    )
    artifact["adaptive_rollout"] = {
        "policy_version": POLICY_VERSION,
        "initial_valid_rounds": policy.initial_valid_rounds,
        "max_valid_rounds": policy.max_valid_rounds,
        "max_raw_attempts_per_lineage": policy.max_raw_attempts_per_lineage,
        "total_requested_rollout_slots": sum(
            sum(result.keep_delete.raw_attempt_counts.values())
            + (result.replacement.raw_attempt_count if result.replacement else 0)
            + (1 if result.replacement_generation is not None else 0)
            for result in step_results
        ),
        "action": "selected" if artifact["optimized"] else "parent_fallback",
        "stop_reason": (
            "optimized_candidate_selected"
            if artifact["optimized"]
            else "no_exportable_candidate"
        ),
        "selected_lineage": selected_record.lineage
        if artifact["optimized"] and selected_record
        else None,
        "steps": [_step_summary(result) for result in step_results],
    }
    return AdaptivePnsCotRunResult(
        policy_version=POLICY_VERSION,
        step_results=tuple(step_results),
        ranked_candidates=tuple(record for record, _source in exportable),
        selected_trial=selected_record if artifact["optimized"] else None,
        artifact=artifact,
    )


def trial_from_qwen_journal_row(
    row: dict[str, Any],
    *,
    parent_qwen_tokens: int,
    parent_answer: str,
    audit: dict[str, Any] | None = None,
) -> RolloutTrial:
    """Convert a ``batch56_runner`` continuation row to the adaptive core."""

    branch = (
        str(
            row.get("branch")
            or row.get("branch_id")
            or row.get("intervention")
            or "candidate"
        )
        .strip()
        .lower()
    )
    step_index = int(row.get("step_index") or 0)
    rollout = int(row.get("rollout") or row.get("trial") or 0)
    valid_value = row.get("valid", row.get("observation_valid", False))
    valid = bool(valid_value is True or valid_value == 1)
    correct_value = row.get("correct", row.get("answer_correct", False))
    correct = bool(correct_value is True or correct_value == 1) if valid else None
    reasoning = str(row.get("complete_chain") or row.get("full_reasoning") or "")
    raw_tokens = row.get("chain_token_count", row.get("reasoning_tokens"))
    tokens = int(raw_tokens) if isinstance(raw_tokens, (int, float)) else None
    raw_chars = row.get("chain_char_count", row.get("reasoning_chars"))
    chars = int(raw_chars) if isinstance(raw_chars, (int, float)) else len(reasoning)
    embedded_audit = row.get("audit") if isinstance(row.get("audit"), dict) else None
    audit_payload = dict(audit or embedded_audit or {})
    candidate_id = str(row.get("candidate_key") or f"{branch}_s{step_index}:t{rollout}")
    answer_value = row.get("predicted_answer", row.get("parsed_answer"))
    predicted_answer = str(answer_value) if answer_value is not None else None
    candidate_eligible = bool(
        valid
        and correct
        and reasoning
        and tokens is not None
        and 0 <= tokens < parent_qwen_tokens
        and _audit_passed(audit_payload)
        and _normalize_answer(predicted_answer) == _normalize_answer(parent_answer)
    )
    return RolloutTrial(
        valid_for_vote=valid,
        correct=correct,
        candidate_id=candidate_id,
        request_key=str(row.get("request_key"))
        if row.get("request_key") is not None
        else None,
        reasoning=reasoning,
        final_content=str(row.get("final_content") or ""),
        predicted_answer=predicted_answer,
        reasoning_tokens=tokens,
        reasoning_chars=chars,
        candidate_eligible=candidate_eligible,
        error=str(row.get("error") or row.get("invalid_reason") or "") or None,
        metadata={
            "audit": audit_payload,
            "journal_state": row.get("state"),
        },
    )


def replacement_generation_from_qwen_journal_row(
    row: dict[str, Any],
) -> ReplacementGeneration:
    """Convert the frozen replacement-generation request from batch56."""

    state = str(row.get("state") or "")
    replacement_text = str(row.get("replacement_text") or "")
    valid = bool(state == "completed" and replacement_text.strip())
    return ReplacementGeneration(
        valid=valid,
        replacement_text=replacement_text if valid else "",
        request_key=str(row.get("request_key"))
        if row.get("request_key") is not None
        else None,
        error=str(row.get("error") or row.get("invalid_reason") or "") or None,
        metadata={"journal_state": state},
    )


def write_pnscot_artifact_jsonl(
    path: str | Path,
    artifacts: Sequence[dict[str, Any]],
) -> Path:
    """Write validated PNSCoT records once; existing artifacts are immutable."""

    rows = [dict(artifact) for artifact in artifacts]
    if not rows:
        raise ValueError("at least one PNSCoT artifact is required")
    for row in rows:
        _validate_pnscot_artifact(row)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            for row in rows:
                handle.write(
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary_path, target)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return target


def _operationally_inconclusive(
    votes: dict[Lineage, list[bool]], policy: AdaptiveRolloutConfig
) -> KeepDeleteDecision:
    valid_rounds = len(votes["keep"])
    keep_correct = sum(votes["keep"])
    delete_correct = sum(votes["delete"])
    return KeepDeleteDecision(
        action="inconclusive_operational",
        stop=True,
        stop_reason="operationally_inconclusive",
        valid_rounds=valid_rounds,
        keep_correct=keep_correct,
        delete_correct=delete_correct,
        difference=keep_correct - delete_correct,
        remaining_rounds=policy.max_valid_rounds - valid_rounds,
    )


def _candidate_decision(
    valid_records: Sequence[TrialRecord],
    *,
    parent: QwenPnsCotParent,
    majority: int,
    minimum_valid: int,
    max_valid: int,
    operationally_inconclusive: bool = False,
) -> CandidateDecision:
    correct = sum(bool(record.trial.correct) for record in valid_records)
    incorrect = len(valid_records) - correct
    eligible_count = len(_eligible_candidate_records(valid_records, parent))
    if operationally_inconclusive:
        return CandidateDecision(
            action="inconclusive_operational",
            stop=True,
            stop_reason="operationally_inconclusive",
            valid_trials=len(valid_records),
            correct_votes=correct,
            incorrect_votes=incorrect,
            majority_threshold=majority,
            eligible_candidate_count=eligible_count,
        )
    if (
        len(valid_records) < minimum_valid
        or minimum_valid < len(valid_records) < max_valid
    ):
        action: CandidateDecisionAction = "continue"
        stop = False
        reason = None
    elif correct >= majority and eligible_count:
        action = "accept"
        stop = True
        reason = "majority_positive"
    elif incorrect >= majority:
        action = "reject"
        stop = True
        reason = "majority_negative"
    elif len(valid_records) == max_valid and correct >= majority:
        action = "positive_no_candidate"
        stop = True
        reason = "positive_majority_no_exportable_candidate"
    elif len(valid_records) == max_valid:
        action = "reject"
        stop = True
        reason = "majority_negative"
    else:
        action = "continue"
        stop = False
        reason = None
    return CandidateDecision(
        action=action,
        stop=stop,
        stop_reason=reason,
        valid_trials=len(valid_records),
        correct_votes=correct,
        incorrect_votes=incorrect,
        majority_threshold=majority,
        eligible_candidate_count=eligible_count,
    )


def _eligible_candidate_records(
    records: Sequence[TrialRecord], parent: QwenPnsCotParent
) -> list[TrialRecord]:
    eligible = [record for record in records if _record_exportable(parent, record)]
    eligible.sort(key=_candidate_sort_key)
    return eligible


def _record_exportable(parent: QwenPnsCotParent, record: TrialRecord) -> bool:
    trial = record.trial
    audit = trial.metadata.get("audit")
    return bool(
        trial.valid_for_vote
        and record.admitted_to_decision
        and trial.correct is True
        and trial.candidate_eligible
        and trial.candidate_id
        and isinstance(trial.request_key, str)
        and bool(trial.request_key.strip())
        and trial.reasoning.strip()
        and trial.reasoning_tokens is not None
        and 0 <= trial.reasoning_tokens < parent.original_qwen_tokens
        and _audit_passed(audit)
        and _normalize_answer(trial.predicted_answer)
        == _normalize_answer(parent.parent_answer)
    )


def _candidate_sort_key(record: TrialRecord) -> tuple[int, int, str]:
    trial = record.trial
    return (
        int(trial.reasoning_tokens or 0),
        int(trial.reasoning_chars or len(trial.reasoning)),
        str(trial.candidate_id),
    )


def _synthetic_selected_result(
    selected: TrialRecord,
    step_results: Sequence[AdaptivePnsStepResult],
    policy: AdaptiveRolloutConfig,
    parent: QwenPnsCotParent,
) -> AdaptiveCandidateResult:
    source_pair = next(
        result.keep_delete
        for result in step_results
        if selected in result.keep_delete.observations
    )
    lineage_records = [
        record
        for record in source_pair.observations
        if record.lineage == selected.lineage and record.trial.valid_for_vote
    ]
    correct = sum(bool(record.trial.correct) for record in lineage_records)
    decision = CandidateDecision(
        action="accept",
        stop=True,
        stop_reason=f"{selected.lineage}_selected_after_paired_decision",
        valid_trials=len(lineage_records),
        correct_votes=correct,
        incorrect_votes=len(lineage_records) - correct,
        majority_threshold=policy.max_valid_rounds // 2 + 1,
        eligible_candidate_count=len(
            _eligible_candidate_records(lineage_records, parent)
        ),
    )
    return AdaptiveCandidateResult(
        policy_version=POLICY_VERSION,
        lineage=selected.lineage,
        decision=decision,
        observations=tuple(lineage_records),
        decision_trace=(decision,),
        selected_trial=selected,
        raw_attempt_count=source_pair.raw_attempt_counts[selected.lineage],
        invalid_count=source_pair.invalid_counts[selected.lineage],
    )


def _step_summary(result: AdaptivePnsStepResult) -> dict[str, Any]:
    pair = result.keep_delete
    attempts = [
        _attempt_summary(record)
        for record in pair.observations
    ]
    if result.replacement is not None:
        attempts.extend(
            _attempt_summary(record)
            for record in result.replacement.observations
        )
    payload: dict[str, Any] = {
        "step_index": result.step_index,
        "attempts": attempts,
        "keep_delete": {
            "action": pair.decision.action,
            "stop_reason": pair.decision.stop_reason,
            "valid_rounds": pair.decision.valid_rounds,
            "keep_correct": pair.decision.keep_correct,
            "delete_correct": pair.decision.delete_correct,
            "raw_attempt_counts": dict(pair.raw_attempt_counts),
            "invalid_counts": dict(pair.invalid_counts),
        },
        "replacement": None,
        "replacement_generation": None,
    }
    if result.replacement_generation is not None:
        generation = result.replacement_generation
        payload["replacement_generation"] = {
            "valid": generation.valid,
            "request_key": generation.request_key,
            "error": generation.error,
            "judge": generation.metadata.get("judge"),
        }
    if result.replacement is not None:
        replacement = result.replacement
        payload["replacement"] = {
            "action": replacement.decision.action,
            "stop_reason": replacement.decision.stop_reason,
            "valid_trials": replacement.decision.valid_trials,
            "correct_votes": replacement.decision.correct_votes,
            "incorrect_votes": replacement.decision.incorrect_votes,
            "raw_attempt_count": replacement.raw_attempt_count,
            "invalid_count": replacement.invalid_count,
        }
    return payload


def _attempt_summary(record: TrialRecord) -> dict[str, Any]:
    trial = record.trial
    return {
        "lineage": record.lineage,
        "matched_round": record.matched_round,
        "raw_attempt": record.raw_attempt,
        "valid_trial_index": record.valid_trial_index,
        "admitted_to_decision": record.admitted_to_decision,
        "request_key": trial.request_key,
        "candidate_id": trial.candidate_id,
        "valid_for_vote": trial.valid_for_vote,
        "correct": trial.correct,
        "candidate_eligible": trial.candidate_eligible,
        "error": trial.error,
        "judge": trial.metadata.get("judge"),
        "deterministic_answer_validation": trial.metadata.get(
            "deterministic_answer_validation"
        ),
    }


def _normalize_answer(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if text in {"yes", "no"} else None


def _audit_passed(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and value.get("passed") is True
        and value.get("coherent", True) is not False
    )


def _validate_pnscot_artifact(row: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "question_id",
        "query_type",
        "original_cot",
        "final_cot",
        "original_qwen_tokens",
        "final_qwen_tokens",
        "optimized",
        "fallback",
        "selected_candidate",
        "selected_request_key",
        "audit",
        "adaptive_rollout",
        "full_pns_asset",
    }
    missing = required - set(row)
    if missing:
        raise ValueError(f"PNSCoT artifact is missing fields: {sorted(missing)}")
    if row["schema_version"] != 1:
        raise ValueError("PNSCoT schema_version must remain 1")
    optimized = row["optimized"] is True
    fallback = row["fallback"] is True
    if optimized == fallback:
        raise ValueError("exactly one of optimized/fallback must be true")
    original_tokens = int(row["original_qwen_tokens"])
    final_tokens = int(row["final_qwen_tokens"])
    if optimized and not 0 <= final_tokens < original_tokens:
        raise ValueError("an optimized PNSCoT must be strictly shorter than its parent")
    if optimized and (
        not isinstance(row["selected_request_key"], str)
        or not row["selected_request_key"].strip()
    ):
        raise ValueError("an optimized PNSCoT must retain its selected request key")
    if fallback and (
        final_tokens != original_tokens or row["final_cot"] != row["original_cot"]
    ):
        raise ValueError("a fallback PNSCoT must reproduce the exact parent chain")
    if not _audit_passed(row["audit"]):
        raise ValueError("the selected PNSCoT path audit must pass")
    if not isinstance(row["adaptive_rollout"], dict) or not row["adaptive_rollout"]:
        raise ValueError("adaptive_rollout metadata is required")
    _validate_full_pns_asset(row["full_pns_asset"], question_id=row["question_id"])
    if row["full_pns_asset"].get("dataset_pns_config_id") is not None:
        _validate_formal_judge_evidence(row)


def _validate_full_pns_asset(value: Any, *, question_id: Any) -> None:
    if not isinstance(value, dict) or not value:
        raise ValueError("full_pns_asset reference is required")
    journal = value.get("journal")
    if not isinstance(journal, str) or not journal.strip():
        raise ValueError("full_pns_asset.journal must be a nonempty string")
    if value.get("qid") != question_id:
        raise ValueError("full_pns_asset.qid must match question_id")


def _validate_formal_judge_evidence(row: dict[str, Any]) -> None:
    acceptance = row.get("judge_acceptance")
    if not isinstance(acceptance, dict):
        raise ValueError("dataset PNS artifact requires Judge acceptance evidence")
    _require_accepted_judge_profile(
        acceptance,
        label="dataset PNS Judge acceptance",
    )
    steps = row["adaptive_rollout"].get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("dataset PNS artifact requires per-step attempts")
    for step in steps:
        attempts = step.get("attempts") if isinstance(step, dict) else None
        if not isinstance(attempts, list) or not attempts:
            raise ValueError("dataset PNS step lacks attempt Judge evidence")
        for attempt in attempts:
            judge = attempt.get("judge") if isinstance(attempt, dict) else None
            if not isinstance(judge, dict):
                raise ValueError("dataset PNS attempt lacks Judge metadata")
            for key in (
                "provider",
                "requested_model",
                "resolved_model",
                "thinking_type",
                "reasoning_effort",
                "status",
                "parse_status",
                "decision",
                "retry_count",
            ):
                if key not in judge:
                    raise ValueError(
                        f"dataset PNS attempt Judge metadata lacks {key}"
                    )
            claims_acceptance = bool(
                attempt.get("valid_for_vote") is True
                or judge.get("accepted") is True
                or judge.get("decision") == "accepted"
            )
            if claims_acceptance:
                _require_accepted_judge_profile(
                    judge,
                    label="dataset PNS accepted attempt Judge evidence",
                )
                if _is_legacy_cli_proxy_recovery(judge):
                    _validate_legacy_recovery_attempt_binding(
                        question_id=row["question_id"],
                        step=step,
                        attempt=attempt,
                        evidence=judge,
                    )


def _is_legacy_cli_proxy_recovery(evidence: dict[str, Any]) -> bool:
    return bool(
        evidence.get("recovery_generation") == 1
        or evidence.get("switch_reason") == "user_specified_backup_judge"
    )


def _require_accepted_judge_profile(
    evidence: dict[str, Any],
    *,
    label: str,
) -> None:
    provider = evidence.get("provider")
    recovery_profile = _is_legacy_cli_proxy_recovery(evidence)
    if recovery_profile:
        fixed = _LEGACY_CLI_PROXY_RECOVERY_ACCEPTED_PROFILE
    elif provider == "cli_proxy" or "scope" in evidence:
        fixed = _FUTURE_CLI_PROXY_ACCEPTED_PROFILE
    elif provider == "deepseek":
        fixed = _LEGACY_DEEPSEEK_ACCEPTED_PROFILE
    else:
        raise ValueError(
            f"{label} must match the legacy DeepSeek or future CLIProxy "
            "strict profile"
        )
    for key, expected in fixed.items():
        if evidence.get(key) != expected:
            raise ValueError(f"{label} {key} must be {expected!r}")
    provider_calls = evidence.get("provider_call_count")
    if type(provider_calls) is not int or provider_calls < 1:
        raise ValueError(f"{label} provider_call_count must be at least 1")
    retry_count = evidence.get("retry_count")
    if type(retry_count) is not int or retry_count < 0:
        raise ValueError(f"{label} retry_count must be a non-negative integer")
    if recovery_profile and provider_calls != 1:
        raise ValueError(f"{label} recovery provider_call_count must be exactly 1")
    if recovery_profile and retry_count != 0:
        raise ValueError(f"{label} recovery retry_count must be exactly 0")
    if not isinstance(evidence.get("verdict"), dict):
        raise ValueError(f"{label} verdict must be an object")
    if recovery_profile:
        provenance = evidence.get("recovery_provenance")
        required_provenance = {
            "generation": 1,
            "target_provider": "cli_proxy",
            "target_model": "gpt-5.5",
            "protocol_revision": "responses_xhigh_strict_json_schema_v1",
            "switch_reason": "user_specified_backup_judge",
        }
        if not isinstance(provenance, dict):
            raise ValueError(f"{label} recovery_provenance must be an object")
        for key, expected in required_provenance.items():
            if provenance.get(key) != expected:
                raise ValueError(
                    f"{label} recovery_provenance.{key} must be {expected!r}"
                )
        source_evidence_id = evidence.get("source_evidence_id")
        if not isinstance(source_evidence_id, str) or not source_evidence_id:
            raise ValueError(f"{label} source_evidence_id must be nonempty")
        expected_effective = (
            "recovery:g1:responses-xhigh-strict-v1:" + source_evidence_id
        )
        if evidence.get("effective_evidence_id") != expected_effective:
            raise ValueError(
                f"{label} effective_evidence_id must be {expected_effective!r}"
            )
        source_state = evidence.get("source_state")
        if source_state not in {
            "completed_provider_error_http_402",
            "reserved_indeterminate",
        }:
            raise ValueError(f"{label} source_state is not an authorized recovery state")
        if evidence.get("evidence_id") != source_evidence_id:
            raise ValueError(f"{label} evidence_id must match source_evidence_id")
        if provenance.get("source_evidence_id") != source_evidence_id:
            raise ValueError(
                f"{label} recovery_provenance.source_evidence_id must match"
            )
        if provenance.get("source_state") != source_state:
            raise ValueError(f"{label} recovery_provenance.source_state must match")
        if not isinstance(provenance.get("source_ledger"), str) or not provenance[
            "source_ledger"
        ].strip():
            raise ValueError(
                f"{label} recovery_provenance.source_ledger must be nonempty"
            )
        normalization = evidence.get("normalization_provenance")
        expected_normalization = {
            "schema_version": "judge_overlay_normalization_v1",
            "profile": "legacy_cli_proxy_recovery_g1",
            "source": "frozen_recovery_transport_contract",
            "derived_fields": {"stream": False, "store": False},
            "raw_absent_fields": ["stream", "store"],
        }
        if normalization != expected_normalization:
            raise ValueError(
                f"{label} normalization_provenance must be "
                f"{expected_normalization!r}"
            )


def _validate_legacy_recovery_attempt_binding(
    *,
    question_id: Any,
    step: dict[str, Any],
    attempt: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    source_id = str(evidence["source_evidence_id"])
    matched = re.fullmatch(
        r"chain:q(?P<qid>\d+):s(?P<step>\d+):"
        r"(?P<lineage>keep|delete|replace):r(?P<raw_attempt>\d+):"
        r"(?P<request_key>.+)",
        source_id,
    )
    if matched is None:
        raise ValueError(
            "dataset PNS accepted attempt recovery evidence_id is malformed"
        )
    lineage = str(attempt.get("lineage") or "").split("_s", 1)[0]
    expected = {
        "qid": str(question_id),
        "step": str(step.get("step_index")),
        "lineage": lineage,
        "raw_attempt": str(attempt.get("raw_attempt")),
        "request_key": str(attempt.get("request_key") or ""),
    }
    if matched.groupdict() != expected:
        raise ValueError(
            "dataset PNS accepted attempt recovery provenance differs from "
            "the attempt identity"
        )
