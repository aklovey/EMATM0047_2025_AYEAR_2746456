# Recalculate the saved results

This repository edition translates non-English prompt/reasoning spans. Offline scoring uses the preserved final-response and numeric fields; original byte hashes, offsets and token counts describe the original run. See [ENGLISH_RELEASE.md](ENGLISH_RELEASE.md).


[Repository overview](../README.md) · [Evidence index](EVIDENCE.md)

## Historical system evidence

The [system-exploration supplement](../supplement/system_exploration/README.md) includes the original 974-question clean and 180-question stress paired matrix, resource summaries, selected per-question and per-shard accounting fields, and preserved source functions. After installing the same analysis requirements used below, run:

```sh
python supplement/system_exploration/recalculate_system_results.py --output reanalysis/system_exploration.json
```

This checks identical ordered question IDs, C0 preservation, original paired-bootstrap and McNemar results, the 49-shard accounting, legacy model turns plus schema repairs, and input/output/total-token identities. Its [saved result](../supplement/system_exploration/recalculated_system_results.json) matches both original comparison packs. The source excerpts are an inspection and offline-analysis supplement, not a complete live historical agent environment.

## Offline analysis

These commands use the saved model outputs. Fresh scoring, main scoring, CPT-cluster inference and joint Holm correction were executed on 11 September 2026 with Python 3.11.9, NumPy 2.4.6 and SciPy 1.17.1. This verification consists of saved-output reanalysis. The [environment record](../experiment/analysis_environment.json) identifies the numerical runtime.

Run from the repository root. The commands are single-line commands, which can be used in PowerShell or a POSIX shell with a suitable `python` executable. Installing the analysis requirements and extracting the archive prepares the inputs.

```sh
python -m pip install -r requirements-analysis.txt
python -m tarfile -e experiment/CAUSE_Experiment_English_Release_20260912.tar.gz reanalysis/raw
```

The archive expands into `dev10/`, `main300/`, `fresh246/`, `self_review56/` and `code_and_demonstrations/`. Each evaluation directory contains condition-specific `*.attempts.jsonl` files, full responses, configuration, usage and original request manifests under `inputs/`.

Recalculate the fresh cohort.

```sh
python experiment/scripts/analyze_paired.py --targets experiment/data/fresh246/targets_scoring_only.jsonl --arm ZERO=reanalysis/raw/fresh246/ZERO.attempts.jsonl --arm FULL_COT=reanalysis/raw/fresh246/FULL_COT.attempts.jsonl --arm HEURISTIC_SHORT=reanalysis/raw/fresh246/HEURISTIC_SHORT.attempts.jsonl --arm PNS_COT=reanalysis/raw/fresh246/PNS_COT.attempts.jsonl --output reanalysis/fresh246
```

Recalculate the main cohort's scores.

```sh
python experiment/scripts/analyze_paired.py --targets experiment/data/freeze300/targets_scoring_only.jsonl --arm ZERO=reanalysis/raw/main300/ZERO.attempts.jsonl --arm FULL_COT=reanalysis/raw/main300/FULL_COT.attempts.jsonl --arm HEURISTIC_SHORT=reanalysis/raw/main300/HEURISTIC_SHORT.attempts.jsonl --arm PNS_COT=reanalysis/raw/main300/PNS_COT.attempts.jsonl --output reanalysis/main300
```

Apply the main cohort's CPT-group analysis and combine the six prespecified p-values for Holm correction.

```sh
python experiment/scripts/cpt_statistics/analyze_cpt_sensitivity.py --scored reanalysis/main300/scored_all_frozen_targets.csv --groups experiment/data/main300_CPT_groups.json --primary-report reanalysis/main300/paired_analysis.json --output reanalysis/main_CPT_sensitivity.json --final-input-confirmed
python experiment/scripts/cpt_statistics/joint_holm.py --main reanalysis/main_CPT_sensitivity.json --fresh reanalysis/fresh246/paired_analysis.json --output reanalysis/joint_comparisons.json
```

New outputs go under `reanalysis/`. Strict scoring retains all frozen targets and counts missing, failed or malformed responses as incorrect. The paired script's item-level main-cohort tests are diagnostic; the CPT command applies the 271-group analysis used in the dissertation. `--final-input-confirmed` is the original analysis script's switch for reading a supplied completed dataset.

| Check | Expected result |
|---|---|
| Main correct, PNS / FULL / HEURISTIC / ZERO | 279 / 277 / 272 / 254, each out of 300 |
| Fresh correct, PNS / FULL / HEURISTIC / ZERO | 224 / 208 / 208 / 187, each out of 246 |
| Main units | 300 targets in 271 full-CPT groups |
| Fresh units | 246 numerical instances |
| Bootstrap | 20,000 samples per comparison |
| Main paired test | 200,000 CPT-group sign flips |
| Fresh paired test | Exact two-sided McNemar |
| Multiplicity | Holm correction across six prespecified comparisons |

The fresh bootstrap resamples instances; the main bootstrap resamples full-CPT groups and retains their paired questions. The two cohorts remain separate in the joint correction. Saved reference outputs are [`main_CPT_sensitivity.json`](../experiment/main_CPT_sensitivity.json), [`fresh_analysis/paired_analysis.json`](../experiment/fresh_analysis/paired_analysis.json) and [`joint_comparisons.json`](../experiment/joint_comparisons.json).

## Recorded model setup

Generating new responses requires a Qwen model installation and a compatible vLLM service with `/tokenize` and `/v1/chat/completions`. The preparation and execution entry points are [`prepare_requests.py`](../experiment/scripts/prepare_requests.py) and [`run_eval.py`](../experiment/scripts/run_eval.py). Their `--help` output documents required input and output paths. The original request manifests can also be inspected directly after archive extraction.

| Setting | Downstream evaluation |
|---|---|
| Model | `Qwen/Qwen3.6-35B-A3B`, BF16 |
| Serving | vLLM 0.27.1, two RTX PRO 6000 Blackwell Server Edition GPUs, one service per GPU with TP 1 |
| Sampling | Temperature 1.0, top-p 0.95, top-k 20, min-p 0, repetition penalty 1, presence and frequency penalties 0 |
| Interface | Native chat completions, thinking enabled, `preserve_thinking` disabled |
| Generation seed | `20260910 + question_id`, matched across the four conditions on each target |
| Context | 16,384 tokens |
| Completion cap | `min(12000, 16384 - max_four_condition_prompt_tokens - 128)`, shared within each target |
| Concurrency | 24 requests per GPU for main and fresh evaluation |

The generation seed was checked in all 1,200 main and 984 fresh request records. Cohort sampling and statistical resampling also use date-based fixed seeds but serve different purposes. Fresh numerical generation has its own schedule in [`fresh_source/`](../experiment/fresh_source/). Phase56 construction has a separate raw-completion protocol and seed schedule in [`phase56_method_contract_compact.json`](../experiment/phase56/phase56_method_contract_compact.json).

Public target fields form the prompt, while reference answers and full SCMs are stored separately for scoring and calculation. The runner records a reservation before dispatch and does not automatically resend a request whose delivery status is unknown. Use a separate output directory for a new inference run.

## Rebuilding data and figures

The captured official CLADDER generator revision is `3d2d1169b4b939a09048a6a75956c8972a93cc38`. [`GENERATE_FRESH246_REPRODUCTION.md`](../experiment/fresh_source/GENERATE_FRESH246_REPRODUCTION.md) records the actual generation driver, dependencies, historical input paths and proposal rules. The frozen data, all 257 proposals and the 11 exclusions are included in [`fresh_source/`](../experiment/fresh_source/).

The root [`figures/`](../figures/) directory contains numerical plotting scripts, their input data, editable Draw.io sources and exports. [`requirements-figures.txt`](../requirements-figures.txt) records the plotting dependencies. The [`paper/`](../paper/) directory contains `main.tex`, the school class and the figure copies needed to compile the dissertation.

The numerical analysis entry points use repository-relative defaults. Some archived generation, figure and historical orchestration scripts retain original machine paths, which should be mapped to a separate working copy when rerunning them. The historical method code is a reference snapshot rather than a complete historical service environment, and the immutable model Hub revision was not recorded. The verified offline workflow reproduces analysis from saved responses; it does not establish identical new stochastic model generations.
