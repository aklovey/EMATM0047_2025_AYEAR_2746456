"""Prespecified main300 CPT sensitivity; never auto-discovers prediction files.

Run only after final input handoff, with --final-input-confirmed. Input is a final
long-form four-arm scored CSV, OR frozen targets plus four terminal attempt files.
No source, target, model request, or primary-analysis file is modified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[2]
ARMS = ("PNS_COT", "FULL_COT", "HEURISTIC_SHORT", "ZERO")
COMPARISONS = tuple(f"PNS_COT:{arm}" for arm in ARMS[1:])
BOOTSTRAP_REPS = 20_000
PERMUTATION_REPS = 200_000
SEED = 20260910
PRIMARY_SCRIPT = Path(__file__).resolve().parents[1] / "analyze_paired.py"
PRESPEC = Path(__file__).with_name("CPT_SENSITIVITY_PRESPEC.md")
SCIPY_SOURCE = "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_record(path):
    p = Path(path).resolve()
    return {"path": str(p), "sha256": sha256(p), "bytes": p.stat().st_size}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def holm_adjust(p_values):
    """Holm step-down adjusted p, retaining the original input order."""
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1 or not len(p) or np.any(~np.isfinite(p)) or np.any((p < 0) | (p > 1)):
        raise ValueError("p-values must be a nonempty finite vector in [0, 1]")
    order = np.argsort(p, kind="stable")
    out = np.empty(len(p), dtype=float)
    running = 0.0
    for rank, index in enumerate(order):
        running = min(1.0, max(running, (len(p) - rank) * p[index]))
        out[index] = running
    return out.tolist()


def validate_and_align(rows, mapping, expected_n=300, expected_clusters=271):
    """Use all manifest IDs, independent of CSV row order, and reject deletion."""
    if not isinstance(mapping, dict) or len(mapping) != expected_n:
        raise ValueError(f"CPT mapping must have exactly {expected_n} question IDs")
    normalized = {}
    for key, value in mapping.items():
        qid = int(key)
        if qid in normalized or not isinstance(value, str) or not value:
            raise ValueError("CPT mapping has duplicate normalized IDs or empty groups")
        normalized[qid] = value
    if len(set(normalized.values())) != expected_clusters:
        raise ValueError(f"Expected {expected_clusters} CPT groups")
    by_arm = {arm: {} for arm in ARMS}
    for row in rows:
        arm = row.get("arm")
        if arm not in by_arm:
            raise ValueError(f"Unexpected arm: {arm}")
        qid = int(row["question_id"])
        if qid not in normalized or qid in by_arm[arm]:
            raise ValueError(f"{arm}: duplicate or outside-manifest question ID {qid}")
        raw = row.get("correct")
        if str(raw) not in {"0", "1"}:
            raise ValueError(f"{arm}/{qid}: correct must be 0 or 1, got {raw!r}")
        by_arm[arm][qid] = {**row, "question_id": qid, "correct": int(raw)}
    ids = sorted(normalized)
    for arm, values in by_arm.items():
        if set(values) != set(normalized):
            raise ValueError(f"{arm}: requires every one of {expected_n} scored rows; "
                             f"missing={len(set(normalized) - set(values))}")
    return ({arm: [values[qid] for qid in ids] for arm, values in by_arm.items()},
            [normalized[qid] for qid in ids])


def aggregate_clusters(differences, groups):
    differences = np.asarray(differences, dtype=np.int64)
    if differences.ndim != 1 or len(differences) != len(groups) or not len(groups):
        raise ValueError("Differences and groups must be nonempty and aligned")
    ids = sorted(set(groups))
    index = {group: i for i, group in enumerate(ids)}
    totals = np.zeros(len(ids), dtype=np.int64)
    sizes = np.zeros(len(ids), dtype=np.int64)
    for diff, group in zip(differences, groups):
        totals[index[group]] += diff
        sizes[index[group]] += 1
    return ids, totals, sizes


def bootstrap_cluster_ratio(totals, sizes, rng, reps=BOOTSTRAP_REPS):
    totals = np.asarray(totals, dtype=np.int64)
    sizes = np.asarray(sizes, dtype=np.int64)
    if totals.shape != sizes.shape or totals.ndim != 1 or not len(totals) or np.any(sizes <= 0) or reps <= 0:
        raise ValueError("Invalid cluster vectors or replicate count")
    boot = np.empty(reps, dtype=float)
    for start in range(0, reps, 1000):
        take = min(1000, reps - start)
        draw = rng.integers(0, len(totals), size=(take, len(totals)))
        boot[start:start + take] = totals[draw].sum(axis=1) / sizes[draw].sum(axis=1)
    return {"ci95": np.quantile(boot, [.025, .975], method="linear").tolist(),
            "replicates": reps, "method": "paired CPT cluster percentile bootstrap",
            "statistic": "sum(sampled cluster difference totals) / sum(sampled cluster item counts)",
            "simultaneous_ci": False}


def cluster_signflip(totals, rng, reps=PERMUTATION_REPS):
    """Always Monte Carlo, including small toy inputs. Integer absolute tail."""
    totals = np.asarray(totals, dtype=np.int64)
    if totals.ndim != 1 or not len(totals) or reps <= 0:
        raise ValueError("Invalid cluster totals or replicate count")
    observed = int(totals.sum())
    extreme = 0
    null_sum = 0
    null_sum_sq = 0
    for start in range(0, reps, 2000):
        take = min(2000, reps - start)
        signs = rng.integers(0, 2, size=(take, len(totals)), dtype=np.int64) * 2 - 1
        null = signs @ totals
        extreme += int(np.count_nonzero(np.abs(null) >= abs(observed)))
        null_sum += int(null.sum())
        null_sum_sq += int(np.square(null).sum())
    p = (extreme + 1) / (reps + 1)
    return {"test": "paired CPT cluster sign-flip permutation (Monte Carlo)",
            "observed_total_difference": observed, "nonzero_cluster_totals": int(np.count_nonzero(totals)),
            "replicates": reps, "extreme_count": extreme, "p": p,
            "two_sided_rule": "(1 + count(abs(null_total) >= abs(observed_total))) / (B + 1)",
            "exact": False, "add_one": True,
            "monte_carlo_standard_error_approx": float(np.sqrt(p * (1 - p) / (reps + 1))),
            "null_mean_total": null_sum / reps,
            "null_sd_total": float(np.sqrt(max(0., null_sum_sq / reps - (null_sum / reps) ** 2)))}


def analyze_rows(rows, mapping, expected_n=300, expected_clusters=271,
                 bootstrap_reps=BOOTSTRAP_REPS, permutation_reps=PERMUTATION_REPS, seed=SEED):
    arms, groups = validate_and_align(rows, mapping, expected_n, expected_clusters)
    streams = np.random.SeedSequence(seed).spawn(2 * len(COMPARISONS))
    group_counts = Counter(groups)
    report = {
        "schema_version": 1, "cohort": "released_followup300", "analysis_role": "supplementary CPT sensitivity",
        "n_frozen_targets": expected_n, "unique_full_CPT_groups": len(group_counts),
        "primary_denominator": f"all {expected_n} frozen items; no exclusions; missing/API/format failures wrong",
        "estimand": "item-weighted paired correctness difference on the original frozen target set",
        "grouping": "identical complete CPT mechanism mapping, not model_id",
        "duplicate_CPT_groups": sum(n > 1 for n in group_counts.values()),
        "items_in_duplicate_CPT_groups": sum(n for n in group_counts.values() if n > 1),
        "max_CPT_group_size": max(group_counts.values()),
        "seed": seed, "rng": "NumPy default_rng / PCG64; SeedSequence.spawn(6)",
        "bootstrap_replicates": bootstrap_reps, "permutation_replicates": permutation_reps,
        "arms": {arm: {"correct": sum(r["correct"] for r in values), "n": expected_n,
                       "strict_accuracy": sum(r["correct"] for r in values) / expected_n}
                 for arm, values in arms.items()},
        "comparisons": {},
        "assumptions_and_limits": [
            "CPT clusters are independent sampling units; within-CPT dependence is unrestricted.",
            "Sign-flip inference assumes joint exchangeability of the two condition labels inside every CPT cluster under the null, equivalently symmetric cluster differences. A zero population mean alone is insufficient.",
            "Prompt conditions were not randomly assigned; permutation inference is model-based under the exchangeability assumption, not a design-based randomized experiment.",
            "Monte Carlo sign flips with add-one adjustment, not exact permutation enumeration.",
            "Point estimate denominator is all 300 original items; bootstrap resamples 271 clusters and uses their sampled item count as its ratio denominator.",
            "CPT clustering does not remove history/demo overlap or demonstrate generalization to unseen mechanisms.",
            "Item-level exact McNemar is retained only as an iid diagnostic for main300.",
            "Per-comparison percentile CIs are not simultaneous intervals and need not give identical decisions to permutation p-values.",
            "No equivalence or non-inferiority claim; failure to reject is not evidence of equality.",
        ],
        "sources": [{"url": SCIPY_SOURCE, "checked_date": "2026-09-10",
                     "scope": "paired label swaps/sign flips, randomized add-one p, and caution about two-sided conventions; our tail is absolute statistic, not SciPy's default twice-min-tail"}],
    }
    for i, comparison in enumerate(COMPARISONS):
        candidate, reference = comparison.split(":")
        ca = np.array([r["correct"] for r in arms[candidate]], dtype=np.int64)
        re = np.array([r["correct"] for r in arms[reference]], dtype=np.int64)
        delta = ca - re
        group_ids, totals, sizes = aggregate_clusters(delta, groups)
        gain = int(np.count_nonzero(delta == 1))
        loss = int(np.count_nonzero(delta == -1))
        bootstrap = bootstrap_cluster_ratio(totals, sizes, np.random.default_rng(streams[2 * i]), bootstrap_reps)
        permutation = cluster_signflip(totals, np.random.default_rng(streams[2 * i + 1]), permutation_reps)
        report["comparisons"][comparison] = {
            "n": expected_n, "clusters": len(group_ids), "candidate": candidate, "reference": reference,
            "gain": gain, "loss": loss, "both_correct": int(np.count_nonzero((ca == 1) & (re == 1))),
            "both_wrong": int(np.count_nonzero((ca == 0) & (re == 0))),
            "accuracy_delta": float(delta.mean()),
            "paired_CPT_cluster_bootstrap_ci95": bootstrap["ci95"], "bootstrap": bootstrap,
            "cluster_permutation_p": permutation["p"], "cluster_permutation": permutation,
            "diagnostic_mcnemar_p": float(binomtest(gain, gain + loss, .5).pvalue) if gain + loss else 1.0,
            "diagnostic_mcnemar_scope": "item-level iid diagnostic only; repeated CPT mechanisms violate iid item premise",
            "bootstrap_rng_spawn_key": list(streams[2 * i].spawn_key),
            "permutation_rng_spawn_key": list(streams[2 * i + 1].spawn_key),
            "cluster_totals": [{"CPT_group": group, "n": int(size), "paired_difference_total": int(total)}
                               for group, size, total in zip(group_ids, sizes, totals)],
        }
    adjusted = holm_adjust([report["comparisons"][key]["cluster_permutation_p"] for key in COMPARISONS])
    for key, p in zip(COMPARISONS, adjusted):
        report["comparisons"][key]["cluster_permutation_holm_within_three_p"] = p
    report["within_cohort_multiplicity"] = {"method": "Holm step-down", "family_size": 3,
                                            "p_type": "CPT cluster permutation Monte Carlo"}
    report["fallacy_scope_review"] = {
        "coverage": "11/11 assessed for the scope of this sensitivity analysis; not a global validity certification",
        "Simpson_paradox": "No subgroup generalization; query-type heterogeneity is outside this pooled sensitivity and remains in original descriptive output.",
        "ecological_fallacy": "Item-weighted estimand is explicit; no inference about persons or group averages.",
        "Berkson_selection": "Frozen selected benchmark; no unrestricted population claim; history overlap remains a limitation.",
        "collider_bias": "No post-outcome filtering or covariate adjustment.",
        "base_rate_neglect": "Reports all-item accuracy and paired differences; does not infer PPV or clinical performance.",
        "regression_to_mean": "Not a pre/post intervention design; selection and reuse remain limits.",
        "survivorship_bias": "All frozen items retained including failed or invalid responses.",
        "look_elsewhere": "All three fixed contrasts reported; within-three and optional joint-six Holm.",
        "forking_paths": "Supplement added after data audit but before outcomes; preserves original analysis and records prespec.",
        "correlation_causation": "Algorithmic paired comparison; no real-world causal effect claim.",
        "reverse_causality": "Not a temporal observational causal claim.",
    }
    return report


def render_markdown(report):
    lines = ['# main300 complete-CPT cluster sensitivity analysis', "", "## Material Passport", "",
             '- Verification Status: ANALYZED. The implementation passed tests on synthetic examples; this table reports supplementary analysis of the final inputs.',
             '- Scope: The original primary analysis and all frozen targets are retained; zero additional model calls.', "",
             f"The observed denominator includes all {report['n_frozen_targets']} questions. The inferential resampling units are {report['unique_full_CPT_groups']} complete-CPT groups. "
             'The mean difference remains question-weighted, and questions with repeated mechanisms are retained.', "",
             '| Comparison | Mean difference | CPT cluster bootstrap 95% CI | gain/loss | cluster permutation p (MC) | Three-comparison Holm p |',
             "|---|---:|---:|---:|---:|---:|"]
    for key, row in report["comparisons"].items():
        lo, hi = row["paired_CPT_cluster_bootstrap_ci95"]
        lines.append(f"| {key} | {row['accuracy_delta']:+.2%} | [{lo:+.2%}, {hi:+.2%}] | {row['gain']}/{row['loss']} | "
                     f"{row['cluster_permutation_p']:.6g} | {row['cluster_permutation_holm_within_three_p']:.6g} |")
    lines += ["", f"Bootstrap {report['bootstrap_replicates']:,} samples; whole-group sign flips {report['permutation_replicates']:,} samples; root seed = {report['seed']}. "
              'The two-sided p = (1 + count(|null| ≥ |observed|)) / (B + 1) is a Monte Carlo result, not an exhaustive exact test.', "",
              'The test assumes that the two condition labels can be jointly exchanged within each CPT group under the null, with different groups treated as independent units. '
              'Prompt conditions were not randomly assigned, and a zero mean difference alone does not establish exchangeability. Percentile CIs are not simultaneous intervals and need not yield the same conclusions as the permutation test.', "",
              'Original question-level McNemar p-values are retained only in the JSON field diagnostic_mcnemar_p. With repeated CPTs, they are not treated as tests on strictly independent questions. '
              'Clustering does not remove historical demo/core/challenge overlap or establish generalisation to new mechanisms.', "",
              'This supplementary specification was saved after the grouping audit identified repeats and before outcomes were read. The original main300 analysis is unchanged. fresh246 is reported separately, with six-comparison Holm correction in joint_comparisons.json; the cohorts are never merged into 546 questions.', "",
              f'The method follows the [official SciPy permutation_test documentation]({SCIPY_SOURCE}), checking paired label exchanges, sign flips and the randomised add-one p-value. '
              'This analysis explicitly uses a two-sided tail based on the absolute statistic.', "",
              "All 11/11 categories of statistical misinterpretation were considered within this analysis's scope, as recorded in the JSON fallacy_scope_review. Non-significance does not establish equivalence or non-inferiority.", ""]
    return "\n".join(lines)


def load_attempts_scored(targets_path, specs):
    spec = importlib.util.spec_from_file_location("frozen_primary_analysis_for_scoring", PRIMARY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    targets = module.read(targets_path)
    if len(targets) != 300 or len({int(r["question_id"]) for r in targets}) != 300:
        raise ValueError("Frozen targets must contain 300 unique question IDs")
    rows, names, paths = [], set(), []
    for item in specs:
        arm, path = item.split("=", 1)
        if arm in names or arm not in ARMS:
            raise ValueError(f"Unexpected or duplicate arm {arm}")
        names.add(arm)
        paths.append(path)
        rows.extend(module.score_rows(targets, module.read(path), arm))
    if names != set(ARMS):
        raise ValueError("Exactly all four frozen arms are required")
    return rows, [targets_path, *paths]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scored", type=Path, help="Final long-form four-arm scored CSV")
    parser.add_argument("--targets", type=Path, help="Frozen targets with gold, required for attempts mode")
    parser.add_argument("--arm", action="append", help="ARM=final_attempts.jsonl")
    parser.add_argument("--groups", type=Path, default=ROOT / "data/main300_CPT_groups.json")
    parser.add_argument("--primary-report", type=Path, help="Optional final original paired_analysis.json for exact point-estimate cross-check")
    parser.add_argument("--output", type=Path, default=ROOT / "main_CPT_sensitivity.json")
    parser.add_argument("--final-input-confirmed", action="store_true")
    args = parser.parse_args(argv)
    if not args.final_input_confirmed:
        parser.error("Use only after final input handoff; --final-input-confirmed is required before any prediction read")
    if bool(args.scored) == bool(args.arm) or bool(args.targets) != bool(args.arm):
        parser.error("Choose --scored OR both --targets and four --arm arguments")
    inputs = [args.groups, PRIMARY_SCRIPT, PRESPEC, Path(__file__)]
    if args.scored:
        inputs.append(args.scored)
    else:
        inputs.extend([args.targets, *(item.split("=", 1)[1] for item in args.arm)])
    if args.primary_report:
        inputs.append(args.primary_report)
    before = [file_record(path) for path in inputs]
    if args.scored:
        with args.scored.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    else:
        rows, _ = load_attempts_scored(args.targets, args.arm)
    report = analyze_rows(rows, read_json(args.groups))
    if args.primary_report:
        primary = read_json(args.primary_report)
        if primary.get("n_frozen_targets") != 300:
            raise ValueError("Primary report denominator differs")
        for key in COMPARISONS:
            original = primary["comparisons"][key]
            supplementary = report["comparisons"][key]
            for field in ("n", "gain", "loss", "both_correct", "both_wrong", "accuracy_delta"):
                if original[field] != supplementary[field]:
                    raise ValueError(f"Frozen primary point estimate mismatch: {key}/{field}")
        report["original_point_estimates_cross_check"] = "PASS: n/gain/loss/both-correct/both-wrong/delta identical for every comparison"
    else:
        report["original_point_estimates_cross_check"] = "Not supplied; values use all scored targets and same paired definitions"
    for record in before:
        if sha256(record["path"]) != record["sha256"]:
            raise RuntimeError(f"Input changed during analysis: {record['path']}; refuse output")
    report["provenance"] = {"generated_utc": datetime.now(timezone.utc).isoformat(),
                            "final_input_confirmed": True, "model_calls": 0,
                            "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                            "inputs_and_code": before}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "n": 300, "CPT_groups": 271, "comparisons": len(COMPARISONS)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
