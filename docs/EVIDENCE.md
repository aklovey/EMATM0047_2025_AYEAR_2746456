# Dissertation evidence guide

The dissertation's E identifiers refer to project records. This page maps every identifier to material in this repository. Non-English source passages have been translated as described in [the English release note](ENGLISH_RELEASE.md). The numbered publication references are listed separately in [the bibliography](../paper/references.bib).

## Main study

| Dissertation ID | Material | Repository entry points |
| --- | --- | --- |
| E1 | Historical planning and experiment summary | [4 September record, English translation](../supplement/historical/CAUSE_Thesis_Structure_and_Experiment_Gaps_2026-09-04.md), [completed 10 September record, English translation](../supplement/historical/CAUSE_Thesis_Structure_and_Experiment_Gaps_COMPLETED_20260910.md) |
| E2 | Historical results, banks, overlap and construction usage | [Results summary](../evidence/historical_results_summary.json), [construction usage](../evidence/historical_offline_full_journal_costs.json), [bank versions](../evidence/historical_asset_builds.json), [group audit](../evidence/cladder_group_audit.json), [saved historical scores](../supplement/historical/scored_results/) |
| E3 | Phase56 construction and the 300-target evaluation | [Construction closure, English release](../experiment/phase56/phase56_closure_all56.jsonl), [56 construction inputs](../experiment/phase56/phase56_original_inputs56.jsonl), [source export](../experiment/phase56/phase56_source_export.json), [construction records](../experiment/phase56/), [main paired results](../experiment/main_analysis/paired_analysis.json), [271-group CPT analysis](../experiment/main_CPT_sensitivity.json) |
| E5 | Component calculations and semantic review | [Independent component calculations](../evidence/phase56_independent_component_audit.json), [model-assisted review](../evidence/blinded_model_assisted_review.md), [deblinded case mapping](../evidence/semantic_review_deblinded.json), [review inputs and decisions](../experiment/audit/) |
| E6 | Fresh numerical instances and the 246-target evaluation | [Generation and provenance](../experiment/fresh_source/README.md), [frozen cohort](../experiment/data/fresh246/manifest.json), [fresh paired results](../experiment/fresh_analysis/paired_analysis.json), [six-comparison Holm adjustment](../experiment/joint_comparisons.json) |
| E8 | Qwen self-review diagnostic | [Summary](../experiment/self_review/self_review_summary.json), [56 records](../experiment/self_review/self_review_records56.jsonl), [quotation checks](../experiment/self_review/quote_validation_summary.json) |
| E9 | Current model usage and the GPU-cycle bill | [Request and token accounting](../experiment/run_accounting_final.json), [AutoDL bill supporting CNY 28.89](../evidence/autodl_billing_20260910.json) |

The [current-run English archive](../experiment/CAUSE_Experiment_English_Release_20260912.tar.gz) contains an English release of requests, response records, per-condition attempts and journal snapshots for `dev10/`, `main300/`, `fresh246/` and `self_review56/`. It also contains the recorded code, demonstrations and runtime metadata. The Phase56 construction records are supplied separately under `experiment/phase56/`.

The worked successful compression example is available as a [readable account](../supplement/compression_example/case_and_execution_evidence.md) and [verbatim selected trace](../supplement/compression_example/q1428_final_demo_verbatim.txt). The [recorded follow-up protocol](../experiment/protocol/FINAL_COMPARISON_SPEC.md) describes the four-condition comparison.

## Historical supporting material

| ID | Material | Repository entry points |
| --- | --- | --- |
| E4 | Earlier verifier replay | [Observed runtime results](../supplement/historical/verifier_replay/observed_runtime_results.json), [verifier code and replay data](../supplement/historical/verifier_replay/CAUSE_Verifier_English_Release_20260912.zip) |
| E7 | Descriptive paired-change cases | [Case report](../evidence/main300_paired_change_cases.md), [selection plan](../supplement/case_selection_plan.md), [case responses](../supplement/case_raw/), [executable counterexample](../supplement/q9510_public_iv_counterexample.py) |

E4 and E7 belong to the historical supplement and are not cited directly in the current main chapters. Their IDs are retained so earlier notes remain readable. The historical exhaustive-PNS56 database is outside this repository; its retained scoring records and usage summaries are under E2. Current Phase56 has its separate complete 56-parent closure and export under E3.

The [extended supplement](../supplement/CAUSE_Electronic_Supplement_20260910.md) preserves older section and table numbering. Use this page for current paths and the dissertation bibliography for current publication references. The [original source manifest](../supplement/historical/source_manifest_20260910.json) and [old ledger](../supplement/historical/evidence_ledger_20260910.md) are retained as historical records. Their basenames and old publication-number ranges are not the current navigation scheme.

## File inventory

[source_manifest.json](../source_manifest.json) records the delivered repository-relative paths and roles. It contains no machine-specific source locations. [REPRODUCE.md](REPRODUCE.md) gives the offline analysis commands, and [the figure directory](../figures/) contains editable diagrams, plotting code and the data used for the numerical figures.
