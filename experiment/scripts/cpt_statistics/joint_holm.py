"""Joint six-comparison Holm with distinct main/fresh populations and test types."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from analyze_cpt_sensitivity import COMPARISONS, ROOT, file_record, holm_adjust, read_json


def build_joint(main, fresh):
    if main.get("n_frozen_targets") != 300 or main.get("unique_full_CPT_groups") != 271:
        raise ValueError("Expected main300 CPT sensitivity with 271 groups")
    if fresh.get("n_frozen_targets") != 246:
        raise ValueError("Expected fresh246 paired analysis")
    if fresh.get("unique_groups") != 246:
        raise ValueError("fresh246 requires 246 independent groups for exact McNemar interpretation")
    if set(main.get("comparisons", {})) != set(COMPARISONS) or set(fresh.get("comparisons", {})) != set(COMPARISONS):
        raise ValueError("Exactly the prespecified three comparisons required in each cohort")
    rows = []
    for key in COMPARISONS:
        source = main["comparisons"][key]
        rows.append({"cohort": "released_followup300", "n": 300, "inference_groups": 271,
                     "comparison": key, "test": "paired CPT cluster sign-flip permutation (Monte Carlo)",
                     "primary_p": source["cluster_permutation_p"],
                     "holm_within_cohort_p": source["cluster_permutation_holm_within_three_p"],
                     "accuracy_delta": source["accuracy_delta"], "gain": source["gain"], "loss": source["loss"],
                     "paired_ci95": source["paired_CPT_cluster_bootstrap_ci95"],
                     "ci_method": "paired CPT cluster percentile bootstrap",
                     "diagnostic_mcnemar_p": source["diagnostic_mcnemar_p"]})
    for key in COMPARISONS:
        source = fresh["comparisons"][key]
        if source.get("n") != 246:
            raise ValueError(f"Fresh comparison denominator mismatch: {key}")
        rows.append({"cohort": "fresh_SCM246", "n": 246, "inference_groups": 246,
                     "comparison": key, "test": "paired item-level exact McNemar (independent fresh mechanisms)",
                     "primary_p": source["mcnemar_exact_p"], "holm_within_cohort_p": source["mcnemar_holm_p"],
                     "accuracy_delta": source["accuracy_delta"], "gain": source["gain"], "loss": source["loss"],
                     "paired_ci95": source["paired_cluster_bootstrap_ci95"],
                     "ci_method": "paired instance percentile bootstrap"})
    for row, adjusted in zip(rows, holm_adjust([row["primary_p"] for row in rows])):
        row["holm_across_six_p"] = adjusted
    return {"schema_version": 1, "analysis_plan": "experiment/scripts/cpt_statistics/CPT_SENSITIVITY_PRESPEC.md",
            "cohorts_pooled": False, "family_size": 6, "adjustment": "Holm step-down",
            "scope": "Three main300 cluster-permutation p-values and three fresh246 exact-McNemar p-values in one six-comparison family; never aggregate the different distributions into 546 items.",
            "comparisons": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", type=Path, default=ROOT / "main_CPT_sensitivity.json")
    parser.add_argument("--fresh", type=Path, default=ROOT / "fresh_analysis/paired_analysis.json")
    parser.add_argument("--output", type=Path, default=ROOT / "joint_comparisons.json")
    args = parser.parse_args(argv)
    records = [file_record(path) for path in (args.main, args.fresh, Path(__file__))]
    report = build_joint(read_json(args.main), read_json(args.fresh))
    report["provenance"] = {"generated_utc": datetime.now(timezone.utc).isoformat(), "inputs_and_code": records, "model_calls": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
