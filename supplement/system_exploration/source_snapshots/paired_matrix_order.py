"""Preserved function excerpts. Source dependencies outside these excerpts are not bundled."""

from __future__ import annotations
from typing import Any
# normalize_binary_answer is an original external source dependency.

# Original formal_experiment_reporting.py lines 119-154

def build_paired_matrix(
    *,
    pack: str,
    candidate_rows: list[dict[str, Any]],
    legacy_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if [row["question_id"] for row in candidate_rows] != [
        row["question_id"] for row in legacy_rows
    ]:
        raise ValueError(f"paired matrix order mismatch for {pack}")
    matrix = []
    for candidate, legacy in zip(candidate_rows, legacy_rows):
        candidate_answer = normalize_binary_answer(candidate.get("final_answer"))
        legacy_answer = normalize_binary_answer(legacy.get("predicted_answer"))
        matrix.append(
            {
                "pack": pack,
                "order": candidate["order"],
                "question_id": candidate["question_id"],
                "query_family": candidate["query_family"],
                "gold_answer_post_run_join": candidate["gold_answer_post_run_join"],
                "c0_answer": candidate_answer,
                "candidate_answer": candidate_answer,
                "legacy_answer": legacy_answer,
                "c0_correct": bool(candidate["correct"]),
                "candidate_correct": bool(candidate["correct"]),
                "legacy_correct": bool(legacy["correct"]),
                "candidate_first_pass_record_sha256": candidate[
                    "first_pass_record_sha256"
                ],
                "candidate_changed_from_c0": False,
                "legacy_execution_valid": bool(legacy.get("execution_valid")),
                "legacy_failure_type": legacy.get("failure_type"),
            }
        )
    return matrix
