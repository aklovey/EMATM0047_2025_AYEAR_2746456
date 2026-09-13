# Auditable reasoning trajectory compression for few-shot causal reasoning

This repository accompanies Wyatt Wang's MSc dissertation for EMATM0047 at the University of Bristol. The study asks whether auditable compression of reasoning demonstrations can improve the accuracy and input/output token trade-off in few-shot causal reasoning on CLADDER. It provides editable LaTeX sources, code, frozen evaluation data, response records and supporting analyses.

[LaTeX sources](paper/) · [Evidence index](docs/EVIDENCE.md) · [Recalculate results](docs/REPRODUCE.md) · [System exploration](supplement/system_exploration/)

## Study and results

PNS starts from a recorded parent trace with a correct final answer, segments its reasoning, and generates continuations from KEEP and DELETE prefix interventions. It selects a shorter complete trace using answer, semantic-review, reconstruction and length checks. This procedure adapts the intervention and continuation ideas discussed in CausalMath for reusable CLADDER demonstrations.

Phase56 accepted shorter traces for **52 of 56 parents**, reducing reasoning tokens across those accepted pairs by **35.74%**. The four unsuccessful compressions retain their parent traces in the deployed bank. Across all 56 identities, reasoning length falls from 128,764 to 87,012 tokens, a **32.43%** reduction.

The three few-shot conditions use the same two same-type demonstration identities and order for each target. FULL_COT supplies full reasoning, HEURISTIC_SHORT extracts parent spans at a closely matched length, and PNS_COT uses the construction and fallback policy. ZERO supplies no demonstrations.

| Cohort | PNS_COT | FULL_COT | HEURISTIC_SHORT | ZERO | PNS input saving against FULL |
|---|---:|---:|---:|---:|---:|
| Main, 300 released targets | 279/300 | 277/300 | 272/300 | 254/300 | 20.19% |
| Fresh, 246 numerical instances | 224/246 | 208/246 | 208/246 | 187/246 | 18.62% |

Fresh accuracy improves by 6.50 percentage points against both FULL and HEURISTIC, with six-comparison Holm-adjusted p-values of 0.00998 and 0.02100. The main cohort's corresponding CPT-cluster confidence intervals include zero. The two cohorts are analysed separately. Detailed results are in [fresh paired analysis](experiment/fresh_analysis/paired_analysis.md), [main CPT sensitivity](experiment/main_CPT_sensitivity.md) and [joint comparisons](experiment/joint_comparisons.json).

The main cohort has prior experimental exposure and numerical reuse, which the 271-group CPT analysis does not remove. Fresh contains 246 of 257 uniform CPT proposals retained by fixed validity and novelty checks within existing graph families, stories and four probability-query types. The findings therefore concern this construction and fallback policy on these cohorts. Semantic cases distinguish inspectable provenance from correct reasoning, and incomplete construction costs leave monetary break-even unresolved.

## Find the materials

The [evidence index](docs/EVIDENCE.md) maps the dissertation's experiments to actual files, including the historical verifier replay and platform bill. The new [system-exploration source register](supplement/system_exploration/source_register.json) links the historical agent and shared-first-pass tables to preserved reports, accounting records and implementation excerpts.

| Location | Contents |
|---|---|
| [`paper/`](paper/) | Current eight-chapter LaTeX sources, bibliography and compilation assets, updated 14 September 2026. Long author/editor lists display the first three names followed by et al. The thesis PDF is not included. |
| [`figures/`](figures/) | Full plotting code and input data, native Draw.io diagrams, and SVG/PDF/PNG exports. |
| [`experiment/data/`](experiment/data/) | Evaluation demonstration bank, public target inputs, scoring labels and CPT groups, with non-English spans translated for this release. |
| [`experiment/scripts/`](experiment/scripts/) | Request preparation, scoring, paired statistics and heuristic extraction. |
| [`experiment/phase56/`](experiment/phase56/) | All 56 parent inputs and closure records, source export, selected lineage, failures and construction summaries. |
| [`experiment/CAUSE_Experiment_English_Release_20260912.tar.gz`](experiment/CAUSE_Experiment_English_Release_20260912.tar.gz) | English release of current-run requests, response records, usage and SQLite snapshots. |
| [`experiment/fresh_source/`](experiment/fresh_source/) | Executed generator driver, official source, proposal and exclusion records, frozen outputs and independent calculations. |
| [`experiment/reference_method_code/`](experiment/reference_method_code/) | Historical construction-method reference snapshot. |
| [`evidence/`](evidence/) | Overlap checks, semantic calculations, historical comparisons, compression measurements and billing. |
| [`supplement/`](supplement/) | Further case material, historical records and theoretical notes, including [verifier replay](supplement/historical/verifier_replay/). |
| [`supplement/system_exploration/`](supplement/system_exploration/) | Historical DeepSeek agent reports, the original GPT-5.5 paired matrix, per-question/per-shard resource fields, released execution manifests and offline reanalysis. |

The current-run archive contains 1,200 main and 984 fresh generation requests, plus 40 development and 56 self-review requests. Historical Phase56 construction and judge calls are recorded separately. Cases and review outputs are also available under [`experiment/cases/`](experiment/cases/), [`experiment/audit/`](experiment/audit/) and [`experiment/self_review/`](experiment/self_review/).

The system supplement adds a broader historical comparison on the same 974 questions. The selected shared-first-pass C0 workflow scores 934 correct against legacy's 935, with 100 versus 3,571 model calls and 1,424,946 versus 11,140,677 total tokens. The [supplement guide](supplement/system_exploration/README.md) separates input/output usage and explains the 49-shard accounting. These are complete-system results with different tool interfaces, not an additional PNS-compression experiment. The separate 180-question stress diagnostic is retained.

## Recalculate and reuse

[The reproduction guide](docs/REPRODUCE.md) provides offline commands for scoring saved responses, CPT-cluster inference and the six-comparison correction. **Saved-output reanalysis was executed on 11 September 2026** using Python 3.11.9, NumPy 2.4.6 and SciPy 1.17.1. It requires no model service.

The historical system paired statistics and accounting were also [recalculated from the released records](supplement/system_exploration/recalculated_system_results.json) on 14 September. The offline script matches the original clean and stress comparison counts, intervals and resource totals without model calls.

The guide also records the Qwen/vLLM settings and separate seed roles. All 2,184 main and fresh request records use `20260910 + question_id` as their generation seed, matched across conditions within each target. Recreating generation requires the model-serving environment; its entry points and archived path mappings are documented separately from offline analysis.

## English release

All repository documentation and filenames are in English. Non-English passages in some recorded prompt and reasoning fields have been translated for this edition. Recorded answers, scoring labels, seeds, token usage and numerical results remain those of the original experiments. Translated text is not a byte-exact raw record, and original text hashes and character offsets still describe the originals, which are retained in the private local archive. See [the release note](docs/ENGLISH_RELEASE.md). The compiled thesis PDF is not distributed here.

## Sources

CLADDER supplies the benchmark, graph families, stories and generator. The captured generator revision and setup are in the [generation record](experiment/fresh_source/GENERATE_FRESH246_REPRODUCTION.md). CausalMath supplies methodological context; this project does not reproduce its experiments. Publication references are in [`paper/references.bib`](paper/references.bib). Upstream code and data retain their included attribution and licence information; this repository assigns no new blanket licence to third-party material.
