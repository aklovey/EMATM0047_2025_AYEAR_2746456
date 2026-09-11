from __future__ import annotations

import json
from typing import Any, Callable, Protocol

from src.providers.deepseek_client import (
    build_deepseek_request,
    call_deepseek_chat,
)


class StructuredJudgeTransport(Protocol):
    """Provider-neutral boundary for strict semantic-judge calls."""

    def preflight_request(self, messages: list[dict[str, str]]) -> dict[str, Any]: ...

    def call(
        self,
        messages: list[dict[str, str]],
        *,
        validator: Callable[[dict[str, Any]], dict[str, Any]],
        user_id: str | None = None,
    ) -> dict[str, Any]: ...


class DeepSeekChatJudgeTransport:
    """DeepSeek-only semantic Judge transport with no provider fallback."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        call_fn: Callable[..., dict[str, Any]] = call_deepseek_chat,
    ) -> None:
        self.config = dict(config)
        self._call_fn = call_fn

    def _arm_config(self) -> dict[str, Any]:
        runtime = self.config.get("runtime")
        arm = {
            key: value
            for key, value in self.config.items()
            if key not in {"provider", "transport", "runtime"}
        }
        if isinstance(runtime, dict):
            arm.update(runtime)

        if self.config.get("provider") != "deepseek":
            raise ValueError("semantic judge provider must be deepseek")
        if self.config.get("transport") != "chat.completions":
            raise ValueError("semantic judge transport must be chat.completions")
        if arm.get("model") != "deepseek-v4-pro":
            raise ValueError("semantic judge model must be deepseek-v4-pro")
        if dict(arm.get("thinking") or {}).get("type") != "enabled":
            raise ValueError("semantic judge thinking.type must be enabled")
        if arm.get("reasoning_effort") != "max":
            raise ValueError("semantic judge reasoning_effort must be max")
        if arm.get("omit_max_tokens") is not True:
            raise ValueError("semantic judge must omit max_tokens")
        if arm.get("response_format") != {"type": "json_object"}:
            raise ValueError("semantic judge response_format must be json_object")
        if arm.get("api_model") not in {None, "deepseek-v4-pro"}:
            raise ValueError(
                "semantic judge resolved model must remain deepseek-v4-pro"
            )
        return arm

    def preflight_request(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Resolve and validate the exact final request without dispatching it."""

        arm = self._arm_config()
        request = build_deepseek_request(
            messages,
            arm,
            max_tokens=None,
        )
        resolved_model = str(request.get("model") or "")
        thinking_type = str(
            ((request.get("extra_body") or {}).get("thinking") or {}).get("type") or ""
        )
        reasoning_effort = str(request.get("reasoning_effort") or "")
        if resolved_model != "deepseek-v4-pro":
            raise ValueError("resolved semantic judge model is not deepseek-v4-pro")
        if thinking_type != "enabled":
            raise ValueError("resolved semantic judge request disabled thinking")
        if reasoning_effort != "max":
            raise ValueError("resolved semantic judge request changed reasoning effort")
        if request.get("response_format") != {"type": "json_object"}:
            raise ValueError("resolved semantic judge request lacks json_object mode")
        if "max_tokens" in request:
            raise ValueError("resolved semantic judge request is not uncapped")
        return {
            "provider": "deepseek",
            "endpoint_type": "chat.completions",
            "requested_model": str(arm["model"]),
            "resolved_model": resolved_model,
            "thinking_type": thinking_type,
            "reasoning_effort": reasoning_effort,
            "status": "ready",
            "parse_status": "not_dispatched",
            "decision": "not_evaluated",
            "provider_call_count": 0,
            "retry_count": 0,
            "fallback_allowed": False,
            "fallback_used": False,
            "request": request,
        }

    def call(
        self,
        messages: list[dict[str, str]],
        *,
        validator: Callable[[dict[str, Any]], dict[str, Any]],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        preflight = self.preflight_request(messages)
        arm = self._arm_config()
        base = {
            key: preflight[key]
            for key in (
                "provider",
                "endpoint_type",
                "requested_model",
                "resolved_model",
                "thinking_type",
                "reasoning_effort",
                "fallback_allowed",
                "fallback_used",
            )
        }
        try:
            response = self._call_fn(
                messages,
                arm,
                max_tokens=None,
                user_id=user_id,
            )
        except Exception as exc:
            return {
                **base,
                "status": "provider_error",
                "parse_status": "not_parsed",
                "decision": "rejected",
                "accepted": False,
                "parsed": None,
                "error": str(exc),
                "response_model": None,
                "provider_call_count": 1,
                "retry_count": 0,
                "usage": _normalized_usage({}),
                "latency_ms": None,
                "request": preflight["request"],
            }

        raw_provider_call_count = response.get("provider_call_count")
        provider_call_count = int(
            raw_provider_call_count if raw_provider_call_count is not None else 1
        )
        retry_count = int(
            response.get("retry_count")
            if response.get("retry_count") is not None
            else max(0, provider_call_count - 1)
        )
        common = {
            **base,
            "response_model": response.get("model"),
            "provider_call_count": provider_call_count,
            "retry_count": retry_count,
            "usage": _normalized_usage(response.get("usage") or {}),
            "latency_ms": response.get("latency_ms"),
            "request": preflight["request"],
        }
        if response.get("ok") is not True:
            return {
                **common,
                "status": "provider_error",
                "parse_status": "not_parsed",
                "decision": "rejected",
                "accepted": False,
                "parsed": None,
                "error": response.get("error_message") or response.get("error_type"),
            }

        if str(response.get("model") or "") != str(preflight["resolved_model"]):
            return {
                **common,
                "status": "model_mismatch",
                "parse_status": "not_parsed",
                "decision": "rejected",
                "accepted": False,
                "parsed": None,
                "error": (
                    "semantic judge response model differs from the resolved request model"
                ),
            }

        try:
            parsed = json.loads(str(response.get("content") or ""))
            if not isinstance(parsed, dict):
                raise ValueError("structured semantic verdict is not an object")
            validator(parsed)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return {
                **common,
                "status": "invalid_or_nonconforming_response",
                "parse_status": "invalid",
                "decision": "rejected",
                "accepted": False,
                "parsed": None,
                "error": str(exc),
            }
        return {
            **common,
            "status": "parsed",
            "parse_status": "parsed",
            "decision": "not_evaluated",
            "accepted": False,
            "parsed": parsed,
            "error": None,
        }


def _normalized_usage(usage: dict[str, Any]) -> dict[str, int]:
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(
        usage.get("output_tokens") or usage.get("completion_tokens") or 0
    )
    total_tokens = int(usage.get("total_tokens") or 0) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }
