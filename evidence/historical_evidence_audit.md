# Audit of original historical experiment evidence, 2026-09-10

This report recalculates results from per-question outputs, frozen request ledgers and original CLADDER data read during the audit. Historical originals were unchanged, and the audit made no model calls. SSH access to the source host, Wyatter-Laptop, was confirmed at the time. Actual file evidence superseded the earlier note that no ICL results were available.

## 1. Historical results available for the dissertation

The historical qwentest100 set was a challenge set balanced by existing single-question baseline outcomes. It contained 50 previously correct questions and 50 with previously valid but incorrect answers, with 20 each for ATE, deterministic counterfactuals, ETT, NDE and NIE. It does not represent CLADDER's original distribution and is not a newly sampled confirmatory test set. Every condition used two same-type demonstrations per question. All denominators retain the 100 frozen targets, and invalid formats count as incorrect.

| Condition | Correct / 100 | Format valid / 100 | Input tokens | Output tokens | Gains / losses against FULL | Difference in percentage points | Paired bootstrap 95% CI | Exact McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | 71 | 100 | 671,354 | 147,121 | 0 / 0 | +0.0 | [+0, +0] | 1.000000 |
| PNS56 | 71 | 97 | 458,093 | 116,649 | 7 / 7 | +0.0 | [-7, +7] | 1.000000 |
| Strong14 | 77 | 100 | 601,524 | 146,234 | 7 / 1 | +6.0 | [+1, +12] | 0.070312 |

PNS56 reduced complete input use by 31.77%, output use by 20.71% and combined input/output tokens by 29.78%. Its strict-accuracy point estimate matched FULL, with seven gains and seven losses, while its format-valid rate fell by three percentage points. These observations support the feasibility of demonstration compression but do not establish an accuracy improvement, equivalence or non-inferiority. Strong14's six-percentage-point gain is an exploratory point estimate. Its exact McNemar p=0.0703125 does not support a claim of statistical significance.

Confidence intervals were calculated from the empirical distribution of each question's paired difference D∈{-1,0,+1}. The distribution of n independent resamples was obtained by n-fold discrete convolution, and its 2.5% and 97.5% quantiles were taken. The resulting values therefore have no Monte Carlo error. The 100 test100 questions have 100 model_id values, so question-level resampling is equivalent to instance-group resampling within this challenge set. The intervals do not account for development, selection or multiple comparisons. Percentile bootstrap intervals and the exact McNemar test are not inverses of the same procedure. Strong14's positive lower interval bound should not override the exact test or the selection limitations.

| Query type, 20 questions each | FULL correct | PNS56 correct | Strong14 correct |
|---|---:|---:|---:|
| ate | 17 | 15 | 17 |
| det-counterfactual | 15 | 15 | 16 |
| ett | 12 | 12 | 12 |
| nde | 14 | 16 | 18 |
| nie | 13 | 13 | 14 |

## 2. Four distinct bank versions

| Version | Unique demonstrations | Compressed / fallback | Complete reasoning tokens | Reduction from parents | Downstream evidence |
|---|---:|---:|---:|---:|---|
| Qwen parent traces | 56 | 0 / 56 | 128,764 | Baseline | FULL 71/100 |
| Initial final package dated 2026-08-17 | 56 | 54 / 2 | 80,258 | 37.67% | An initial candidate-selection version, which cannot substitute for the versions actually evaluated below |
| Exhaustive original audit, called PNS56 in this report | 56 | 56 / 0 | 79,021 | 38.63% | PNS56 71/100 |
| Conservative Strong14 reselection | 56 | 14 / 42 | 115,824 | 10.05% | Strong14 77/100 |

The later adaptive Phase56 protocol is a separate experiment. It does not inherit this table's 56/56 completion status, compression rates or ICL effects. The original CausalMath protocol adaptation scored 63/100 with 79/100 valid formats. Only 21 questions were subsequently rerun selectively, yielding six correct answers and nine valid formats. The historical “repaired 69/100” combined 79 retained questions with 21 replacements. It is not a new independent 100-question run.

## 3. Data selection and instance separation

The historical selection summary records 10,112 CLADDER single-question baseline cases, with 9,239 strictly correct answers (91.37%), 713 valid but incorrect answers and 160 outputs invalid because of format or other issues. A_CORE_READY contained 256 questions, or 2.53% of the full set. Its composition was eight ATE, 231 deterministic counterfactual, four ETT, two NDE and 11 NIE questions. The 256-question core is a candidate pool and does not mean that 256 dynamic compressions were completed.

| Set | Questions | Distinct model_id values |
|---|---:|---:|
| CLADDER balanced data | 10,112 | 5,268 |
| core256 | 256 | 212 |
| Actual demo56 | 56 | 55 |
| Historical test100 | 100 | 100 |

core256 and test100 share no question_id values but share eight model_id values, namely 2063, 2269, 3228, 3349, 3430, 3456, 3506 and 3510. The actual demo56 and test100 share two model_id values, 2063 and 3228. Deduplication by qid alone does not establish separation of causal instances.

Excluding all 304 instance groups from core256 and test100 leaves 9,221 questions across 4,964 instances. Within the five matched query types, 4,409 questions across 3,006 instances remain, comprising 1,374 ATE, 796 deterministic counterfactual, 1,212 ETT, 287 NDE and 740 NIE questions. This pool can support a new evaluation with instance-group exclusions. The new Phase56 demonstrations, semantic-audit cases and development samples must also contribute their model_id values to the exclusion set. Because all 10,112 questions participated in baseline screening, no remaining subset should be described as historically untouched. A suitable description is a newly sampled evaluation set separated from development and demonstration instances and unused for method selection in the current round, with the earlier full-dataset baseline exposure disclosed.

## 4. Offline calls and failure ledger

| Branch | Requests | Input tokens | Output tokens |
|---|---:|---:|---:|
| keep | 3,382 | 3,074,304 | 7,030,738 |
| delete | 3,382 | 2,943,234 | 7,170,074 |
| replacement_generate | 52 | 43,783 | 11,713 |
| replace | 94 | 80,222 | 256,248 |
| Total | 6,910 | 6,141,543 | 14,468,773 |

The ledger contains 6,910 unique request IDs, all with HTTP 200 responses. Terminal states are 6,876 completed and 34 scientific_invalid. The latter comprise five strict-answer parsing failures, 23 continuation-length truncations, four replacement-length truncations, one replacement containing the final answer and one empty content field. There were 52 replacement-generation attempts, of which 47 were successfully frozen, followed by 94 REPLACE continuations. Failed generations are included in the cost totals. Path auditing used local_deterministic_v1, with zero external path-judge model calls.

Each demonstration required a mean of 123.39 requests, 109,670.41 input tokens and 258,370.95 output tokens. Per-demonstration request counts had a median of 113, a 95th percentile of 192 and a range of 40–283. Input-token counts had a median of 89,763 and a 95th percentile of 252,791.75. Output-token counts had a median of 195,099 and a 95th percentile of 753,321.75.

The first POST was at 2026-08-17 06:20:33.926 UTC and the last response at 12:01:14.013 UTC, an interval of 5.678 hours. This interval is not GPU billing time. Setup, idle periods and restarts may incur additional costs, and summed request latency is not GPU wall-clock time. The ledger covers this 6,910-request construction run. It excludes parent-trace generation, earlier smoke tests, later CausalMath repairs and Phase56, so it does not establish total project spending.

## 5. Token-count amortisation

The following comparison uses the construction-token totals above and the mean online savings observed over the historical 100 questions.

| Historical online policy | Input tokens saved per target | Output tokens saved per target | Total tokens saved per target | Total construction tokens / total savings per target | Equivalent repeated 100-question batches |
|---|---:|---:|---:|---:|---:|
| PNS56 | 2,132.61 | 304.72 | 2,437.33 | 8,456.10 target uses | 84.56 |
| Strong14 | 698.30 | 8.87 | 707.17 | 29,144.78 target uses | 291.45 |

Input and output tokens can have different computational and monetary costs. The table simply gives equal weight to tokens from the same model. If output tokens have weight w relative to input tokens, the PNS56 token-count amortisation threshold is `(6,141,543 + w×14,468,773) / (2,132.61 + w×304.72)` target uses. The value of w must come from an applicable cost model or actual billing. Equal-weight counts cannot be presented arbitrarily as realised financial savings. Output savings were observed on this challenge set and are not guaranteed at deployment. New task distributions and output lengths may change or eliminate the savings. Several bank versions share the same candidate-construction pool, so this cost must not be counted as multiple independent construction runs.

## 6. Recorded model parameters

| Setting | Historical online ICL | Historical offline candidate construction |
|---|---|---|
| Model | Qwen/Qwen3.6-35B-A3B | Same |
| Online / continuation endpoint | /v1/chat/completions | /v1/completions for KEEP/DELETE/REPLACE |
| Context length | 16,384 | 16,384 |
| Output cap | min(12000,16384−prompt_tokens−128) | Suffix 8,000 and replacement 1,024, with the same dynamic 128-token reserve |
| temperature / top_p / top_k | 1.0 / 0.95 / 20 | 1.0 / 0.95 / 20 |
| min_p / repetition_penalty | 0.0 / 1.0 | 0.0 / 1.0 |
| presence / frequency penalty | 0 / 0 | 0 / 0 |
| Returned samples per request, n | 1 | 1 |
| KEEP / DELETE / REPLACE repetitions | Not applicable | Two per branch under the old fixed protocol |
| Path audit | Not applicable | local_deterministic_v1, with zero external judge calls |
| Inference service | BF16, TP=1, prefix caching disabled | The locally frozen contract records final concurrency of 48 |

The online conditions used the same fixed targets, demonstration questions and demonstration order. Compression reduced the input and changed the dynamically available output cap, so numerical output-token caps were not identical across conditions. None of the three historical online result sets contained length truncations. This table describes the 17 August historical protocol and is not a parameter record for the latest Phase56 run.

## 7. Evidence files and recalculation entry points

- `historical_test100_paired.csv` contains gold labels, predictions, strict correctness, format validity, tokens, latency and demonstration-instance overlap flags for the 100 questions.
- `historical_results_summary.json` contains per-condition totals, paired gains/losses, exact McNemar tests and discrete-convolution bootstrap intervals.
- `historical_offline_full_journal_costs.json` contains branch-level costs, failures and per-demonstration distributions for all 6,910 construction requests.
- `cladder_group_audit.json` contains qid and model_id intersections among the core, demonstration and test sets.
- `historical_asset_builds.json` records the bank versions actually used downstream.

The original files are listed below.

- FULL is recorded in `C:\Users\aklovey\Documents\Codex\2026-08-17\qwen36-fewshot-icl-pilot\outputs\results\qwentest100_2shot_20260817\results\scored_results.jsonl`.
- PNS56 is recorded in `C:\Users\aklovey\Documents\Codex\2026-08-17\qwen36-fewshot-icl-pilot\outputs\results\qwentest100_pns_cot_2shot_exhaustive_original_audit_20260817\results\scored_results.jsonl`.
- Strong14 is recorded in `C:\Users\aklovey\Documents\Codex\2026-08-17\qwen36-fewshot-icl-pilot\outputs\results\qwentest100_pns_cot_2shot_strong_20260817\results\scored_results.jsonl`.
- The offline ledger is `C:\Users\aklovey\Documents\Codex\2026-08-17\qwen36-fewshot-icl-pilot\outputs\pns56_checkpoints\final_extracted_20260817\final\journal_snapshot.sqlite3`.
- The full selection summary is `C:\Users\aklovey\Documents\Codex\2026-08-17\qwen36-pns-256\work\input_validation_copy\selection_summary.json`.
- The CLADDER data are in `D:\CAUSE_DATASETS\dataset21_20260908\source_root\data\cladder-v1-balanced.json`.
- The CLADDER causal models are in `D:\CAUSE_DATASETS\dataset21_20260908\source_root\data\cladder-v1-meta-models.json`.

The calculation scripts are retained under this task's `work/evidence/history/`, including inspect_history.py, check_groups.py, journal_summary.py and finalize_report.py. This was a read-only statistical recalculation and did not apply a new semantic judge to historical model outputs.
