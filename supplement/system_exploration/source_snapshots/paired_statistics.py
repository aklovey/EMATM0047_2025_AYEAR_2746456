"""Preserved function excerpts. Source dependencies outside these excerpts are not bundled."""

from __future__ import annotations
from typing import Any
import numpy as np
from scipy.stats import binomtest

# Original formal_experiment_reporting.py lines 35-90

def paired_binary_comparison(
    *,
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    left_name: str,
    right_name: str,
    bootstrap_resamples: int = 10_000,
    seed: int = 20260718,
) -> dict[str, Any]:
    left = {str(row["question_id"]): bool(row.get("correct")) for row in left_rows}
    right = {str(row["question_id"]): bool(row.get("correct")) for row in right_rows}
    ordered_ids = [str(row["question_id"]) for row in left_rows]
    if ordered_ids != [str(row["question_id"]) for row in right_rows]:
        raise ValueError("paired rows differ in question-ID order")
    left_correct = np.asarray([left[question_id] for question_id in ordered_ids], dtype=np.int8)
    right_correct = np.asarray([right[question_id] for question_id in ordered_ids], dtype=np.int8)
    differences = right_correct - left_correct
    both_correct = int(np.sum((left_correct == 1) & (right_correct == 1)))
    both_wrong = int(np.sum((left_correct == 0) & (right_correct == 0)))
    left_only = int(np.sum((left_correct == 1) & (right_correct == 0)))
    right_only = int(np.sum((left_correct == 0) & (right_correct == 1)))
    ci_low, ci_high = paired_bootstrap_interval(
        differences,
        resamples=bootstrap_resamples,
        seed=seed,
    )
    discordant = left_only + right_only
    p_value = (
        float(binomtest(right_only, discordant, p=0.5, alternative="two-sided").pvalue)
        if discordant
        else 1.0
    )
    return {
        "left_arm": left_name,
        "right_arm": right_name,
        "paired_n": len(ordered_ids),
        "left_correct": int(left_correct.sum()),
        "right_correct": int(right_correct.sum()),
        "left_accuracy": float(left_correct.mean()) if len(ordered_ids) else 0.0,
        "right_accuracy": float(right_correct.mean()) if len(ordered_ids) else 0.0,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "baseline_only": left_only,
        "candidate_only": right_only,
        "corrections": right_only,
        "regressions": left_only,
        "delta": float(differences.mean()) if len(ordered_ids) else 0.0,
        "delta_pp": float(differences.mean() * 100.0) if len(ordered_ids) else 0.0,
        "mcnemar_exact_two_sided_p": p_value,
        "paired_bootstrap_ci_low": ci_low,
        "paired_bootstrap_ci_high": ci_high,
        "paired_bootstrap_ci_low_pp": ci_low * 100.0,
        "paired_bootstrap_ci_high_pp": ci_high * 100.0,
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_seed": seed,
    }



# Original formal_experiment_reporting.py lines 93-116

def paired_bootstrap_interval(
    differences: np.ndarray,
    *,
    resamples: int,
    seed: int,
) -> tuple[float, float]:
    if differences.size == 0:
        return 0.0, 0.0
    if np.all(differences == differences[0]):
        value = float(differences[0])
        return value, value
    rng = np.random.default_rng(seed)
    values = np.empty(resamples, dtype=float)
    chunk = 500
    for start in range(0, resamples, chunk):
        count = min(chunk, resamples - start)
        indices = rng.integers(
            0,
            differences.size,
            size=(count, differences.size),
        )
        values[start:start + count] = differences[indices].mean(axis=1)
    low, high = np.percentile(values, [2.5, 97.5])
    return float(low), float(high)
