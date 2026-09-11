from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .storage import (
    append_jsonl_unique,
    load_secret,
    read_json,
    redact_text,
    sha256_json,
    sha256_text,
    write_frozen_json,
    write_json,
)


JUDGE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer_correct": {"type": "boolean"},
        "path_correct": {"type": "boolean"},
        "rung_respected": {"type": "boolean"},
        "query_type_respected": {"type": "boolean"},
        "all_required_operations_present": {"type": "boolean"},
        "contains_material_error": {"type": "boolean"},
        "contains_unjustified_leap": {"type": "boolean"},
        "uses_invalid_causal_rule": {"type": "boolean"},
        "uses_world_knowledge_over_scm": {"type": "boolean"},
        "semantic_operation_reintroduced": {"type": "boolean"},
        "corrected_injected_error": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "error_codes": {"type": "array", "items": {"type": "string"}},
        "brief_rationale": {"type": "string", "maxLength": 800},
    },
    "required": [
        "answer_correct",
        "path_correct",
        "rung_respected",
        "query_type_respected",
        "all_required_operations_present",
        "contains_material_error",
        "contains_unjustified_leap",
        "uses_invalid_causal_rule",
        "uses_world_knowledge_over_scm",
        "semantic_operation_reintroduced",
        "corrected_injected_error",
        "confidence",
        "error_codes",
        "brief_rationale",
    ],
    "additionalProperties": False,
}


REPLACEMENT_SEMANTIC_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "semantically_equivalent": {"type": "boolean"},
        "valid_alternative_path": {"type": "boolean"},
        "no_contradiction": {"type": "boolean"},
        "valid_intervention": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "error_codes": {"type": "array", "items": {"type": "string"}},
        "brief_rationale": {"type": "string", "maxLength": 800},
    },
    "required": [
        "semantically_equivalent",
        "valid_alternative_path",
        "no_contradiction",
        "valid_intervention",
        "confidence",
        "error_codes",
        "brief_rationale",
    ],
    "additionalProperties": False,
}


CHAIN_COHERENCE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "chain_coherent": {"type": "boolean"},
        "logic_valid": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "error_codes": {"type": "array", "items": {"type": "string"}},
        "brief_rationale": {"type": "string", "maxLength": 800},
    },
    "required": [
        "chain_coherent",
        "logic_valid",
        "confidence",
        "error_codes",
        "brief_rationale",
    ],
    "additionalProperties": False,
}


_SEMANTIC_FORBIDDEN_FIELDS = {
    "gold",
    "gold_answer",
    "gold_reasoning",
    "groundtruth",
    "answer_correct",
}

CORRECTNESS_SYSTEM = """You are the evaluator-only correctness judge for explicit public CLADDER traces.
Evaluate the complete causal path, not merely the final yes/no answer. Even when the final answer is correct,
set path_correct=false if any intermediate operation contains a material error, invalid formula, wrong rung,
wrong conditioning/intervention/counterfactual world, or an unjustified leap. Do not output hidden reasoning.
Return only the strict structured verdict and a short rationale."""

AUDITOR_SYSTEM = """You are an independent adversarial path auditor for explicit public CLADDER traces.
Actively search for answer-right/path-wrong cases, rung collapse, association/intervention confusion,
intervention/counterfactual confusion, invalid conditioning or adjustment, invalid do-operator use,
factual/counterfactual world mixing, NDE/NIE/ATE/ATT/ETT definition errors, arithmetic errors,
unstated computation, world knowledge substituted for the SCM, and answer-first rationalization.
Do not output hidden reasoning. Return only the strict structured verdict and a short rationale."""

REPLACEMENT_SEMANTIC_SYSTEM = """You are the CLADDER replacement-intervention judge.
Decide whether the replacement is either a semantics-preserving compression of the original step OR a
different but valid alternative causal path. Also decide whether it contradicts the supplied problem or
reasoning context, and whether it forms a targeted valid intervention. Equivalence and valid alternative
path are not required one-to-one, but at least one must hold; no_contradiction and valid_intervention are
both hard requirements. Any programmatic semantic reference is advisory only: it is an alignment anchor,
not a required one-to-one step map or required reasoning path. Do not judge final-answer correctness or
the complete rollout chain. Return only the requested JSON object and a short rationale."""

CHAIN_COHERENCE_SYSTEM = """You are the CLADDER full-chain semantic judge.
Decide only whether the complete public reasoning chain is coherent and logically valid for the supplied
problem. Any programmatic semantic reference is advisory only and need not match the candidate step for
step or use the same valid path. Do not decide whether its final answer matches a hidden dataset label.
Return only the requested JSON object and a short rationale."""


def _value(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(name, default)
    direct = getattr(row, name, None)
    if direct is not None:
        return direct
    visible = getattr(row, "solver_visible", None)
    if visible is not None and name in {"given_info", "question"}:
        return getattr(visible, name, default)
    return default


def _meta(row: Any) -> dict[str, Any]:
    value = _value(row, "meta", {})
    if isinstance(value, dict):
        return value
    metadata = _value(row, "metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _assert_no_semantic_gold_fields(value: Any) -> None:
    if isinstance(value, dict):
        forbidden = {
            str(key).strip().casefold()
            for key in value
            if str(key).strip().casefold() in _SEMANTIC_FORBIDDEN_FIELDS
        }
        if forbidden:
            raise ValueError(
                f"semantic judge payload contains forbidden fields: {sorted(forbidden)}"
            )
        for child in value.values():
            _assert_no_semantic_gold_fields(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_no_semantic_gold_fields(child)


def _sanitized_semantic_reference(row: Any) -> dict[str, Any] | None:
    value = _value(row, "semantic_reference")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("semantic reference must be a mapping")
    expected = {
        "source",
        "role",
        "one_to_one_required",
        "same_path_required",
        "steps",
    }
    if set(value) != expected:
        raise ValueError("semantic reference fields differ from the Judge contract")
    if value.get("role") != "advisory_alignment_anchor_only":
        raise ValueError("semantic reference must remain advisory")
    if (
        value.get("one_to_one_required") is not False
        or value.get("same_path_required") is not False
    ):
        raise ValueError("semantic reference cannot require one-to-one or same-path alignment")
    source = value.get("source")
    steps = value.get("steps")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("semantic reference source is missing")
    if not isinstance(steps, list) or not steps:
        raise ValueError("semantic reference non-answer steps are missing")
    sanitized_steps: list[dict[str, str]] = []
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"source_field", "text"}:
            raise ValueError("semantic reference step fields differ")
        source_field = step.get("source_field")
        text = step.get("text")
        if (
            not isinstance(source_field, str)
            or not source_field.strip()
            or source_field == "end"
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise ValueError("semantic reference contains an invalid or answer step")
        sanitized_steps.append({"source_field": source_field, "text": text})
    return {
        "source": source,
        "role": "advisory_alignment_anchor_only",
        "one_to_one_required": False,
        "same_path_required": False,
        "steps": sanitized_steps,
    }


def replacement_semantic_payload(
    sample: Any,
    *,
    original_step: dict[str, Any],
    replacement_step: dict[str, Any],
) -> dict[str, Any]:
    """Build the CLADDER-only semantic-intervention payload without gold data."""

    meta = _meta(sample)
    payload = {
        "dataset": "CLADDER",
        "question_id": str(
            _value(sample, "question_id", _value(sample, "source_id", "unknown"))
        ),
        "given_info": str(_value(sample, "given_info", "") or ""),
        "question": str(_value(sample, "question", "") or ""),
        "rung": int(meta.get("rung", _value(sample, "rung", 0)) or 0),
        "query_type": str(
            meta.get("query_type", _value(sample, "query_type", "")) or ""
        ),
        "original_step": copy.deepcopy(dict(original_step)),
        "replacement_step": copy.deepcopy(dict(replacement_step)),
    }
    semantic_reference = _sanitized_semantic_reference(sample)
    if semantic_reference is not None:
        payload["semantic_reference"] = semantic_reference
    _assert_no_semantic_gold_fields(payload)
    return payload


def chain_coherence_payload(
    sample: Any,
    *,
    candidate_chain: dict[str, Any],
) -> dict[str, Any]:
    """Build the CLADDER-only full-chain payload without answer labels."""

    meta = _meta(sample)
    payload = {
        "dataset": "CLADDER",
        "question_id": str(
            _value(sample, "question_id", _value(sample, "source_id", "unknown"))
        ),
        "given_info": str(_value(sample, "given_info", "") or ""),
        "question": str(_value(sample, "question", "") or ""),
        "rung": int(meta.get("rung", _value(sample, "rung", 0)) or 0),
        "query_type": str(
            meta.get("query_type", _value(sample, "query_type", "")) or ""
        ),
        "candidate_public_chain": copy.deepcopy(dict(candidate_chain)),
    }
    semantic_reference = _sanitized_semantic_reference(sample)
    if semantic_reference is not None:
        payload["semantic_reference"] = semantic_reference
    _assert_no_semantic_gold_fields(payload)
    return payload


def _validate_semantic_verdict(
    value: dict[str, Any],
    *,
    schema: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} verdict must be an object")
    expected = set(schema["properties"])
    if set(value) != expected:
        raise ValueError(
            f"{label} verdict keys differ: "
            f"missing={sorted(expected-set(value))}, extra={sorted(set(value)-expected)}"
        )
    for field, field_schema in schema["properties"].items():
        if field_schema.get("type") == "boolean" and not isinstance(value[field], bool):
            raise ValueError(f"{label} field {field} must be boolean")
    confidence = value["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError(f"{label} confidence must be numeric")
    if not 0.0 <= float(confidence) <= 1.0:
        raise ValueError(f"{label} confidence outside [0,1]")
    error_codes = value["error_codes"]
    if not isinstance(error_codes, list) or not all(
        isinstance(item, str) for item in error_codes
    ):
        raise ValueError(f"{label} error_codes must be a string list")
    rationale = value["brief_rationale"]
    if not isinstance(rationale, str):
        raise ValueError(f"{label} brief_rationale must be a string")
    if len(rationale) > 800:
        raise ValueError(f"{label} brief_rationale is too long")
    return value


def validate_replacement_semantic_verdict(
    value: dict[str, Any],
) -> dict[str, Any]:
    return _validate_semantic_verdict(
        value,
        schema=REPLACEMENT_SEMANTIC_JSON_SCHEMA,
        label="replacement semantic",
    )


def replacement_semantic_pass(
    verdict: dict[str, Any], *, min_confidence: float = 0.90
) -> bool:
    return bool(
        (
            verdict.get("semantically_equivalent") is True
            or verdict.get("valid_alternative_path") is True
        )
        and verdict.get("no_contradiction") is True
        and verdict.get("valid_intervention") is True
        and float(verdict.get("confidence") or 0.0) >= float(min_confidence)
    )


def validate_chain_coherence_verdict(value: dict[str, Any]) -> dict[str, Any]:
    return _validate_semantic_verdict(
        value,
        schema=CHAIN_COHERENCE_JSON_SCHEMA,
        label="chain coherence",
    )


def chain_coherence_pass(
    verdict: dict[str, Any], *, min_confidence: float = 0.90
) -> bool:
    return bool(
        verdict.get("chain_coherent") is True
        and verdict.get("logic_valid") is True
        and float(verdict.get("confidence") or 0.0) >= float(min_confidence)
    )


def normalize_yes_no(value: Any) -> str:
    text = str(value or "").strip().lower().rstrip(".")
    if text in {"yes", "y", "true", "1"}:
        return "yes"
    if text in {"no", "n", "false", "0"}:
        return "no"
    return text


def exact_answer_matches(trace: dict[str, Any], gold_answer: Any) -> bool:
    return normalize_yes_no(trace.get("final_answer")) == normalize_yes_no(gold_answer)


def path_judge_pass(verdict: dict[str, Any], *, min_confidence: float = 0.90) -> bool:
    """Path-only gate, intentionally independent of final-answer correctness."""

    return bool(
        verdict.get("path_correct") is True
        and verdict.get("rung_respected") is True
        and verdict.get("query_type_respected") is True
        and verdict.get("all_required_operations_present") is True
        and verdict.get("contains_material_error") is False
        and verdict.get("contains_unjustified_leap") is False
        and verdict.get("uses_invalid_causal_rule") is False
        and verdict.get("uses_world_knowledge_over_scm") is False
        and float(verdict.get("confidence") or 0.0) >= float(min_confidence)
    )


def judge_pass(verdict: dict[str, Any], *, min_confidence: float = 0.90) -> bool:
    return bool(
        verdict.get("answer_correct") is True
        and path_judge_pass(verdict, min_confidence=min_confidence)
    )


def validate_judge_verdict(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("judge verdict must be an object")
    expected = set(JUDGE_JSON_SCHEMA["properties"])
    if set(value) != expected:
        raise ValueError(f"judge verdict keys differ: missing={sorted(expected-set(value))}, extra={sorted(set(value)-expected)}")
    for field in expected:
        schema = JUDGE_JSON_SCHEMA["properties"][field]
        if schema.get("type") == "boolean" and not isinstance(value[field], bool):
            raise ValueError(f"judge field {field} must be boolean")
    confidence = float(value["confidence"])
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("judge confidence outside [0,1]")
    if not isinstance(value["error_codes"], list) or not all(isinstance(item, str) for item in value["error_codes"]):
        raise ValueError("judge error_codes must be a string list")
    rationale = str(value["brief_rationale"])
    if len(rationale) > 800:
        raise ValueError("judge brief_rationale is too long")
    return value


def evaluator_payload(
    sample: Any,
    candidate: dict[str, Any],
    *,
    intervention_type: str = "KEEP",
    original_operation: dict[str, Any] | None = None,
    modified_operation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = _meta(sample)
    gold = _value(sample, "gold", None)
    if gold is not None:
        gold_answer = _value(gold, "answer", None)
        gold_reasoning = _value(gold, "reasoning", None)
        groundtruth = _value(gold, "groundtruth", None)
    else:
        gold_answer = _value(sample, "answer", _value(sample, "gold_answer", None))
        gold_reasoning = _value(sample, "reasoning", _value(sample, "gold_reasoning", None))
        groundtruth = meta.get("groundtruth", _value(sample, "groundtruth", None))
    return {
        "given_info": str(_value(sample, "given_info", "") or ""),
        "question": str(_value(sample, "question", "") or ""),
        "gold_answer": gold_answer,
        "gold_reasoning": gold_reasoning,
        "groundtruth": groundtruth,
        "rung": int(meta.get("rung", _value(sample, "rung", 0)) or 0),
        "query_type": str(meta.get("query_type", _value(sample, "query_type", "")) or ""),
        "candidate_public_trace": candidate,
        "intervention_type": intervention_type,
        "original_operation": original_operation,
        "modified_operation": modified_operation,
    }


def _messages(system: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
    ]


def _semantic_messages(
    system: str,
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> list[dict[str, str]]:
    return _messages(
        system,
        {
            "task_payload": payload,
            "output_contract": schema,
        },
    )


class CladderSemanticJudge:
    """CLADDER-only two-decision semantic Judge over an injected transport."""

    def __init__(self, transport: Any, *, min_confidence: float = 0.90) -> None:
        self.transport = transport
        self.min_confidence = float(min_confidence)

    def judge_replacement(
        self,
        sample: Any,
        original_step: dict[str, Any],
        replacement_step: dict[str, Any],
        *,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        payload = replacement_semantic_payload(
            sample,
            original_step=original_step,
            replacement_step=replacement_step,
        )
        result = self.transport.call(
            _semantic_messages(
                REPLACEMENT_SEMANTIC_SYSTEM,
                payload,
                REPLACEMENT_SEMANTIC_JSON_SCHEMA,
            ),
            validator=validate_replacement_semantic_verdict,
            user_id=user_id,
        )
        return self._decision(result, replacement_semantic_pass)

    def preflight_replacement(
        self,
        sample: Any,
        original_step: dict[str, Any],
        replacement_step: dict[str, Any],
    ) -> dict[str, Any]:
        payload = replacement_semantic_payload(
            sample,
            original_step=original_step,
            replacement_step=replacement_step,
        )
        return self.transport.preflight_request(
            _semantic_messages(
                REPLACEMENT_SEMANTIC_SYSTEM,
                payload,
                REPLACEMENT_SEMANTIC_JSON_SCHEMA,
            )
        )

    def judge_chain(
        self,
        sample: Any,
        candidate_chain: dict[str, Any],
        *,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        payload = chain_coherence_payload(
            sample,
            candidate_chain=candidate_chain,
        )
        result = self.transport.call(
            _semantic_messages(
                CHAIN_COHERENCE_SYSTEM,
                payload,
                CHAIN_COHERENCE_JSON_SCHEMA,
            ),
            validator=validate_chain_coherence_verdict,
            user_id=user_id,
        )
        return self._decision(result, chain_coherence_pass)

    def preflight_chain(
        self,
        sample: Any,
        candidate_chain: dict[str, Any],
    ) -> dict[str, Any]:
        payload = chain_coherence_payload(
            sample,
            candidate_chain=candidate_chain,
        )
        return self.transport.preflight_request(
            _semantic_messages(
                CHAIN_COHERENCE_SYSTEM,
                payload,
                CHAIN_COHERENCE_JSON_SCHEMA,
            )
        )

    def _decision(self, result: dict[str, Any], pass_fn: Any) -> dict[str, Any]:
        verdict = result.get("parsed")
        accepted = bool(
            result.get("status") == "parsed"
            and result.get("parse_status") == "parsed"
            and isinstance(verdict, dict)
            and pass_fn(verdict, min_confidence=self.min_confidence)
        )
        return {
            **result,
            "verdict": verdict,
            "decision": "accepted" if accepted else "rejected",
            "accepted": accepted,
        }


def _responses_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0) or input_tokens + output_tokens
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _judge_audit_fields(
    request: dict[str, Any],
    *,
    called_at_utc: str | None,
) -> dict[str, Any]:
    model_config = {
        key: request[key]
        for key in ("provider", "endpoint", "model", "reasoning", "text", "max_output_tokens")
    }
    return {
        "provider": "openai",
        "model": str(request["model"]),
        "endpoint_type": "responses",
        "generation_parameters": {
            "reasoning": request["reasoning"],
            "structured_output": {
                "type": request["text"]["format"]["type"],
                "name": request["text"]["format"]["name"],
                "strict": request["text"]["format"]["strict"],
                "schema_sha256": sha256_json(request["text"]["format"]["schema"]),
            },
            "max_output_tokens": request["max_output_tokens"],
        },
        "prompt_sha256": sha256_json(request["input"]),
        "model_config_sha256": sha256_json(model_config),
        "called_at_utc": called_at_utc,
    }


def _response_text(response: Any) -> str:
    if str(getattr(response, "status", "")) == "incomplete":
        detail = getattr(response, "incomplete_details", None)
        raise ValueError(f"incomplete Responses API result: {getattr(detail, 'reason', 'unknown')}")
    for item in list(getattr(response, "output", []) or []):
        if str(getattr(item, "type", "")) != "message":
            continue
        for content in list(getattr(item, "content", []) or []):
            content_type = str(getattr(content, "type", ""))
            if content_type == "refusal":
                raise ValueError("Responses API refusal")
            if content_type == "output_text":
                return str(getattr(content, "text", "") or "")
    value = str(getattr(response, "output_text", "") or "")
    if not value:
        raise ValueError("Responses API returned no output text")
    return value


def build_responses_request(
    call_id: str,
    config: dict[str, Any],
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    schema_name: str,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    """Return the complete configured-model Responses API request/cache key."""

    return {
        "call_id": call_id,
        "provider": "openai",
        "endpoint": "responses",
        "model": str(config["model"]),
        "input": messages,
        "reasoning": {"effort": str(config.get("reasoning_effort", "xhigh"))},
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
        "max_output_tokens": int(max_output_tokens or config.get("max_output_tokens", 1400)),
    }


@dataclass(frozen=True)
class StructuredResponseResult:
    call_id: str
    status: str
    parsed: dict[str, Any] | None
    record: dict[str, Any]


class StructuredResponsesStore:
    """Content-addressed Responses API calls with explicit retries and strict schemas."""

    def __init__(self, output: str | Path, config: dict[str, Any]) -> None:
        self.output = Path(output)
        self.config = dict(config)
        self._client: Any | None = None
        self._secret: str | None = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._secret = load_secret(
                str(self.config.get("api_key_env") or "OPENAI_API_KEY"),
                self.config.get("api_key_file"),
            )
            self._client = OpenAI(
                api_key=self._secret,
                base_url=str(self.config["base_url"]),
                max_retries=0,
                timeout=float(self.config.get("timeout_seconds", 600.0)),
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if callable(close):
                close()

    def preflight_exact_model(self) -> dict[str, Any]:
        client = self._ensure_client()
        models = client.models.list()
        model_ids = sorted({str(getattr(item, "id", "")) for item in getattr(models, "data", [])})
        required = str(self.config["model"])
        result = {
            "base_url": str(self.config["base_url"]),
            "required_model": required,
            "available_model_ids": model_ids,
            "passed": required in model_ids,
        }
        write_json(self.output / "score_plane" / "route_preflight.json", result)
        if not result["passed"]:
            raise RuntimeError(f"configured judge model unavailable: {required}")
        return result

    def call(
        self,
        call_id: str,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any],
        schema_name: str,
        validator: Any | None = None,
        max_output_tokens: int | None = None,
    ) -> StructuredResponseResult:
        request = build_responses_request(
            call_id,
            self.config,
            messages,
            schema=schema,
            schema_name=schema_name,
            max_output_tokens=max_output_tokens,
        )
        request_hash = sha256_json(request)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", call_id)
        root = self.output / "score_plane" / "responses"
        request_path = root / "requests" / f"{safe}.json"
        receipt_path = root / "receipts" / f"{safe}.json"
        result_path = root / "results" / f"{safe}.json"
        if result_path.exists():
            prior = read_json(result_path)
            if prior.get("request_sha256") != request_hash:
                raise ValueError(f"Responses cache key collision for {call_id}")
            if receipt_path.exists() and read_json(receipt_path).get("request_sha256") != request_hash:
                raise ValueError(f"Responses receipt mismatch for {call_id}")
            write_json(
                receipt_path,
                {
                    "call_id": call_id,
                    "request_sha256": request_hash,
                    "state": "completed" if prior.get("status") == "parsed" else "completed_error",
                    "retry_count": int(prior.get("retry_count", 0) or 0),
                    "called_at_utc": prior.get("called_at_utc"),
                },
            )
            append_jsonl_unique(self.output / "logs" / "calls.jsonl", prior)
            if prior.get("status") != "parsed":
                append_jsonl_unique(self.output / "logs" / "errors.jsonl", prior)
            return StructuredResponseResult(call_id, str(prior.get("status")), prior.get("parsed"), prior)
        if receipt_path.exists():
            receipt = read_json(receipt_path)
            if receipt.get("request_sha256") != request_hash:
                raise ValueError(f"Responses receipt mismatch for {call_id}")
            record = {
                "call_id": call_id,
                **_judge_audit_fields(
                    request,
                    called_at_utc=receipt.get("called_at_utc"),
                ),
                "request_sha256": request_hash,
                "status": "indeterminate_after_prior_dispatch",
                "provider_call_count": 0,
                "retry_count": 0,
                "parsed": None,
                "response_id": None,
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }
            write_json(result_path, record)
            append_jsonl_unique(self.output / "logs" / "calls.jsonl", record)
            return StructuredResponseResult(call_id, record["status"], None, record)

        write_frozen_json(request_path, {**request, "request_sha256": request_hash})
        # Client/credential setup is not an external dispatch and therefore
        # precedes the crash-recovery receipt.
        client = self._ensure_client()
        called_at_utc = _utc_now()
        audit_fields = _judge_audit_fields(request, called_at_utc=called_at_utc)
        write_frozen_json(
            receipt_path,
            {
                "call_id": call_id,
                "request_sha256": request_hash,
                "state": "dispatched",
                "retry_count": 0,
                "called_at_utc": called_at_utc,
            },
        )
        errors: list[str] = []
        response: Any | None = None
        response_ok = False
        raw_text = ""
        started = time.perf_counter()
        maximum = int(self.config.get("max_retries", 2))
        for attempt in range(maximum + 1):
            try:
                response = client.responses.create(
                    model=request["model"],
                    input=request["input"],
                    reasoning=request["reasoning"],
                    text=request["text"],
                    max_output_tokens=request["max_output_tokens"],
                )
                raw_text = _response_text(response)
                response_ok = True
                break
            except Exception as exc:
                errors.append(redact_text(str(exc), [self._secret or ""]))
                if attempt >= maximum:
                    break
                time.sleep(min(16.0, 2.0**attempt))
        if not response_ok:
            record = {
                "call_id": call_id,
                **audit_fields,
                "request_sha256": request_hash,
                "status": "provider_error",
                "error": errors[-1] if errors else "provider_error",
                "provider_call_count": len(errors),
                "retry_count": max(0, len(errors) - 1),
                "parsed": None,
                "response_id": None,
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        else:
            raw_path = root / "raw" / f"{safe}.txt"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(raw_text, encoding="utf-8")
            try:
                parsed = json.loads(raw_text)
                if not isinstance(parsed, dict):
                    raise ValueError("structured response is not an object")
                if validator is not None:
                    validator(parsed)
                status = "parsed"
                error = None
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                parsed = None
                status = "invalid_or_nonconforming_response"
                error = str(exc)
            record = {
                "call_id": call_id,
                **audit_fields,
                "request_sha256": request_hash,
                "status": status,
                "error": error,
                "provider_call_count": len(errors) + 1,
                "retry_count": len(errors),
                "model": str(getattr(response, "model", request["model"]) or request["model"]),
                "response_id": str(getattr(response, "id", "") or ""),
                "parsed": parsed,
                "raw_response_sha256": sha256_text(raw_text),
                "usage": _responses_usage(response),
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        write_json(result_path, record)
        write_json(
            receipt_path,
            {
                "call_id": call_id,
                "request_sha256": request_hash,
                "state": "completed" if record["status"] == "parsed" else "completed_error",
                "retry_count": record["retry_count"],
                "called_at_utc": called_at_utc,
            },
        )
        append_jsonl_unique(self.output / "logs" / "calls.jsonl", record)
        if record["status"] != "parsed":
            append_jsonl_unique(self.output / "logs" / "errors.jsonl", record)
        return StructuredResponseResult(call_id, record["status"], record.get("parsed"), record)


class ResponsesJudge:
    def __init__(self, store: StructuredResponsesStore, config: dict[str, Any]) -> None:
        self.store = store
        self.config = dict(config)

    def judge(
        self,
        sample: Any,
        candidate: dict[str, Any],
        *,
        role: str = "correctness",
        intervention_type: str = "KEEP",
        original_operation: dict[str, Any] | None = None,
        modified_operation: dict[str, Any] | None = None,
        call_suffix: str = "",
    ) -> dict[str, Any]:
        qid = str(_value(sample, "question_id", _value(sample, "source_id", "unknown")))
        candidate_hash = sha256_json(candidate)[:20]
        system = CORRECTNESS_SYSTEM if role == "correctness" else AUDITOR_SYSTEM
        payload = evaluator_payload(
            sample,
            candidate,
            intervention_type=intervention_type,
            original_operation=original_operation,
            modified_operation=modified_operation,
        )
        call_id = f"judge_{role}_{qid}_{candidate_hash}{('_' + call_suffix) if call_suffix else ''}"
        result = self.store.call(
            call_id,
            _messages(system, payload),
            schema=JUDGE_JSON_SCHEMA,
            schema_name="cladder_path_verdict",
            validator=validate_judge_verdict,
        )
        return {
            "call_id": call_id,
            "status": result.status,
            "verdict": result.parsed,
            "passed": bool(
                result.parsed is not None
                and judge_pass(result.parsed, min_confidence=float(self.config.get("min_confidence", 0.90)))
            ),
            "path_pass": bool(
                result.parsed is not None
                and path_judge_pass(
                    result.parsed,
                    min_confidence=float(self.config.get("min_confidence", 0.90)),
                )
            ),
            "usage": result.record.get("usage"),
            "latency_ms": float(result.record.get("latency_ms", 0.0) or 0.0),
            "retry_count": result.record.get("retry_count", 0),
        }

    def double_audit(self, sample: Any, candidate: dict[str, Any], *, call_suffix: str = "final") -> dict[str, Any]:
        correctness = self.judge(sample, candidate, role="correctness", call_suffix=call_suffix)
        adversarial = self.judge(sample, candidate, role="adversarial", call_suffix=call_suffix)
        return {
            "correctness": correctness,
            "adversarial": adversarial,
            "passed": correctness["passed"] is True and adversarial["passed"] is True,
        }


def deterministic_verifier_result(
    candidate: dict[str, Any],
    *,
    supported: bool = False,
    checks: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    check_rows = list(checks)
    return {
        "supported": bool(supported),
        "passed": bool(supported and all(row.get("passed") is True for row in check_rows)),
        "checks": check_rows,
        "claim_boundary": (
            "deterministic_query_type_check"
            if supported
            else "schema_and_exact_answer_only; no deterministic semantic path certification"
        ),
        "candidate_sha256": sha256_json(candidate),
    }


def final_acceptance_decision(
    *,
    schema_valid: bool,
    exact_answer: bool,
    initial_judge: dict[str, Any],
    fixed_point: dict[str, Any],
    paraphrase_stability: dict[str, Any],
    wrong_replacement: dict[str, Any],
    final_double_audit: dict[str, Any],
) -> dict[str, Any]:
    """Apply every frozen acceptance gate, including two independent final calls."""

    correctness = final_double_audit.get("correctness", {})
    adversarial = final_double_audit.get("adversarial", {})
    gates = {
        "schema_valid": schema_valid is True,
        "exact_answer": exact_answer is True,
        "initial_path_judge": initial_judge.get("passed") is True,
        "delete_fixed_point": fixed_point.get("passed") is True,
        "paraphrase_stability": paraphrase_stability.get("passed") is True,
        "wrong_replacement_detection_and_correction": wrong_replacement.get("passed") is True,
        "final_correctness_judge": correctness.get("passed") is True,
        "final_adversarial_auditor": adversarial.get("passed") is True,
        "final_double_audit": final_double_audit.get("passed") is True,
    }
    failed = [name for name, passed in gates.items() if not passed]
    return {"accepted": not failed, "gates": gates, "failed_gates": failed}
