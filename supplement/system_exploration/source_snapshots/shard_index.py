"""Preserved function excerpts. Source dependencies outside these excerpts are not bundled."""

from __future__ import annotations
from pathlib import Path
from typing import Any
# read_json and read_jsonl are original external source dependencies.

# Original shared_first_pass_experiment.py lines 175-199

def index_generic_shards(run_dir: Path | str) -> dict[str, dict[str, Any]]:
    root = Path(run_dir)
    result: dict[str, dict[str, Any]] = {}
    for prediction_path in sorted((root / "shards").rglob("predictions.jsonl")):
        audit_path = prediction_path.with_name("graph_audit.json")
        if not audit_path.exists():
            continue
        audit = read_json(audit_path)
        for prediction in read_jsonl(prediction_path):
            question_id = str(prediction.get("question_id") or "")
            if question_id in result:
                continue
            result[question_id] = {
                "prediction": prediction,
                "shard_id": audit.get("shard_id") or prediction_path.parent.name,
                "usage": {
                    key: int(value or 0)
                    for key, value in (audit.get("usage") or {}).items()
                },
                "latency_ms_total": int(audit.get("latency_ms_total") or 0),
                "model_calls": int(audit.get("model_calls") or 0),
                "model_retries": int(audit.get("model_retries") or 0),
                "audit_path": str(audit_path.resolve()),
            }
    return result
