# Towards Efficient Causal Reasoning with Large Language Models

*From Few-Shot Demonstrations to Tool-Agent Workflows*

This repository accompanies an MSc dissertation for EMATM0047 at the University of Bristol. The study examines how reusable demonstrations and the organisation of model calls affect accuracy and resource use in causal reasoning on CLADDER. It provides code, evaluation data, response records and supporting analyses.

[Evidence index](docs/EVIDENCE.md) · [Recalculate results](docs/REPRODUCE.md) · [System exploration](supplement/system_exploration/)

## Study and results

### Demonstration construction and reuse

PNS starts from a recorded parent trace with a correct final answer, segments its reasoning, and generates continuations from KEEP and DELETE prefix interventions. It selects a shorter complete trace after checking its answer, causal reasoning, reconstruction and length. The procedure adapts the intervention and continuation ideas discussed in CausalMath to construct reusable CLADDER demonstrations.

Phase56 accepted shorter traces for **52 of 56 parents**, reducing reasoning tokens across those accepted pairs by **35.74%**. The [deployed 56-identity bank](experiment/data/demonstrations56.jsonl) uses these shorter traces and retains the original parents for the remaining four. Across all 56 identities, reasoning length falls from 128,764 to 87,012 tokens, a **32.43%** reduction. The [Phase56 construction ledger](experiment/phase56/phase56_ledger_accounting.json) records upfront token use and judge calls. Incomplete cost records leave the full monetary break-even unresolved.

The three few-shot conditions use the same two same-type demonstration identities and order for each target. FULL_COT supplies full reasoning, HEURISTIC_SHORT extracts parent spans at a closely matched length, and PNS_COT uses the construction and fallback policy. ZERO supplies no demonstrations.

| Cohort | PNS_COT | FULL_COT | HEURISTIC_SHORT | ZERO | PNS input saving against FULL |
|---|---:|---:|---:|---:|---:|
| Main, 300 previously evaluated targets | 279/300 | 277/300 | 272/300 | 254/300 | 20.19% |
| Fresh, 246 numerical instances | 224/246 | 208/246 | 208/246 | 187/246 | 18.62% |

Fresh accuracy improves by 6.50 percentage points against both FULL and HEURISTIC, with six-comparison Holm-adjusted p-values of 0.00998 and 0.02100. The main cohort's corresponding CPT-cluster confidence intervals include zero. Detailed results are in [fresh paired analysis](experiment/fresh_analysis/paired_analysis.md), [main CPT sensitivity](experiment/main_CPT_sensitivity.md) and [joint comparisons](experiment/joint_comparisons.json).

The cohorts are analysed separately. Main contains previously evaluated questions and shared numerical configurations, with paired analysis using 271 CPT groups. Fresh contains 246 of 257 uniform CPT proposals retained by fixed validity and novelty checks within existing graph families, stories and four probability-query types. The [semantic review](evidence/blinded_model_assisted_review.md) includes cases where correct final answers coexist with errors in reasoning.

### Workflow comparison

The system supplement compares two complete workflows on the same 974 questions. The selected shared-first-pass C0 workflow scores 934 correct against legacy's 935, with 100 versus 3,571 model calls and 1,424,946 versus 11,140,677 total tokens. The [supplement guide](supplement/system_exploration/README.md) reports input and output token use separately and explains the 49-shard accounting. The comparison measures workflows that differ in tool interfaces and call organisation. A separate [180-question stress diagnostic](supplement/system_exploration/shared_first_pass/structural_stress_holdout/) examines performance on selected query types.

## Find the materials

The [evidence index](docs/EVIDENCE.md) maps the dissertation's experiments to their files, including the historical verifier replay and platform bill. The [system-exploration source register](supplement/system_exploration/source_register.json) links the historical agent and shared-first-pass tables to preserved reports, accounting records and implementation excerpts.

| Location | Contents |
|---|---|
| [`figures/`](figures/) | Full plotting code and input data, native Draw.io diagrams, and SVG/PDF/PNG exports. |
| [`experiment/data/`](experiment/data/) | Evaluation demonstration bank, target inputs, scoring labels and CPT groups. |
| [`experiment/scripts/`](experiment/scripts/) | Request preparation, scoring, paired statistics and heuristic extraction. |
| [`experiment/phase56/`](experiment/phase56/) | All 56 parent inputs and closure records, source export, selected lineage, failures and construction summaries. |
| [Experiment records archive](experiment/CAUSE_Experiment_English_Release_20260912.tar.gz) | Requests, response records, usage and SQLite snapshots. |
| [`experiment/fresh_source/`](experiment/fresh_source/) | Executed generator driver, official source, proposal and exclusion records, frozen generation records and independent calculations. |
| [`experiment/reference_method_code/`](experiment/reference_method_code/) | Historical construction-method reference snapshot. |
| [`evidence/`](evidence/) | Overlap checks, semantic calculations, historical comparisons, compression measurements and billing. |
| [`supplement/`](supplement/) | Further case material, historical records and theoretical notes, including [verifier replay](supplement/historical/verifier_replay/). |
| [`supplement/system_exploration/`](supplement/system_exploration/) | Historical DeepSeek agent reports, the original GPT-5.5 paired matrix, per-question/per-shard resource fields, released execution manifests and offline reanalysis. |

The current-run archive contains 1,200 main and 984 fresh generation requests, plus 40 development and 56 self-review requests. Phase56 construction and judge calls have their own records in `experiment/phase56/`. Cases and review outputs are also available under [`experiment/cases/`](experiment/cases/), [`experiment/audit/`](experiment/audit/) and [`experiment/self_review/`](experiment/self_review/).

## Recalculate and reuse

[The reproduction guide](docs/REPRODUCE.md) provides offline commands for scoring saved responses, CPT-cluster inference and the six-comparison correction. Saved-output reanalysis was executed on 11 September 2026 using Python 3.11.9, NumPy 2.4.6 and SciPy 1.17.1. These commands run directly on the saved records.

The historical system paired statistics and accounting were also [recalculated from the released records](supplement/system_exploration/recalculated_system_results.json) on 14 September. The offline script matches the original clean and stress comparison counts, intervals and resource totals.

For new model runs, the guide gives the Qwen/vLLM settings, execution entry points and archived path mappings. All 2,184 main and fresh request records use `20260910 + question_id` as their generation seed, matched across conditions within each target. Cohort sampling and statistical resampling use separate seed schedules, which are also documented.

## Sources

CLADDER supplies the benchmark, graph families, stories and generator. The captured generator revision and setup are in the [generation record](experiment/fresh_source/GENERATE_FRESH246_REPRODUCTION.md). CausalMath provides methodological context for the PNS procedure. The included upstream code and data retain their original attribution and licence information.
