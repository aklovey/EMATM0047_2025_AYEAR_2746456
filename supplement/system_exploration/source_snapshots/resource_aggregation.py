"""Preserved function excerpts. Source dependencies outside these excerpts are not bundled."""

from __future__ import annotations
from typing import Any

# Original formal_holdout_experiment.py lines 678-699

def legacy_resource_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    usage_keys = set()
    for row in records:
        usage_keys.update((row.get("usage") or {}).keys())
    usage = {
        key: sum(int((row.get("usage") or {}).get(key) or 0) for row in records)
        for key in sorted(usage_keys)
    }
    return {
        "model_calls": sum(
            int(row.get("turn_count") or 0)
            + int(bool(row.get("repair_attempted")))
            for row in records
        ),
        "transport_retries": 0,
        "schema_repairs": sum(
            int(bool(row.get("repair_attempted"))) for row in records
        ),
        "tool_calls": sum(int(row.get("tool_call_count") or 0) for row in records),
        "latency_ms_total": sum(int(row.get("latency_ms") or 0) for row in records),
        "usage": usage,
    }



# Original formal_holdout_experiment.py lines 702-724

def _aggregate_generic_audits(
    audits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    usage_keys = {
        key
        for payload in audits.values()
        for key in (payload.get("usage") or {})
    }
    return {
        "unique_shards": len(audits),
        "model_calls": sum(int(row.get("model_calls") or 0) for row in audits.values()),
        "model_retries": sum(int(row.get("model_retries") or 0) for row in audits.values()),
        "latency_ms_total": sum(
            int(row.get("latency_ms_total") or 0) for row in audits.values()
        ),
        "usage": {
            key: sum(
                int((row.get("usage") or {}).get(key) or 0)
                for row in audits.values()
            )
            for key in sorted(usage_keys)
        },
    }
