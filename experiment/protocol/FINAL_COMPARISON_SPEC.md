# CLADDER final four-condition comparison protocol (2026-09-10, v2 parent fallback)

## Material Passport

- Phase: instance-separated follow-up evaluation after fixing the method. This is the preparation stage, with no new model results.
- Main question: Can auditable reasoning-trajectory compression improve the efficiency of few-shot causal reasoning?
- Claim: Estimate changes in accuracy and input/output costs. No non-inferiority claim is specified, and non-significance will not be described as equivalence.

## 1. Samples and comparisons

The formal cohort has N=300, with four conditions per target and a primary budget of 1,200 calls. A separate development check selects 10 known development targets, with four conditions and 40 calls. Neither sample size nor conditions may be selected according to the significance of formal results. The formal cohort excludes smoke-test targets and their model_id groups. The planned 1,240 calls exclude historical PNS construction and separately recorded recovery calls.

| Condition | Reasoning demonstrations | Demonstrations per question |
|---|---|---:|
| ZERO | No demonstrations | 0 |
| FULL_COT | Original correct CoT from two fixed demonstrations | 2 |
| HEURISTIC_SHORT | The same demonstrations' original CoT compressed by model-free heuristic extraction | 2 |
| PNS_COT | The same demonstrations' currently frozen PNS-compressed traces | 2 |

The three demonstration conditions share problem statements, known answers, demonstration identities, query-type routing and order. Each type-specific pool must provide at least 2 usable traces. All generators may use only the corresponding demonstration's public original problem and known answer. PNS content supplies only a token-length budget to the ordinary compressor and cannot be used for content extraction. Target gold labels and oracle metadata appear only in local scoring files.

**Necessary pre-execution revision**. The latest 52 accepted traces contain only 1 ett item, so they cannot provide two distinct same-type demonstrations. The new downstream ICL conditions therefore use the original pool of 56 demonstration identities. The 52 accepted items use compressed traces; the 4 questions q19407, q24494, q29833 and q30257 use their original parents as fallback. FULL, PNS and HEURISTIC reasoning is identical for these 4 items. Historical Phase56 remains 52 accepted / 4 failed. Fallback belongs only to the new downstream policy and does not redefine the historical experiment as 56 successes. Each target receives two fixed, distinct, same-type demonstration identities. This round estimates the complete deployable policy of replacing successfully compressed traces and retaining parents after failure, rather than an idealised effect restricted to successful traces. The manifest automatically counts fallback/optimised use among the formal cohort's 600 demonstration slots.

The 56-item pool contains ate6, det-counterfactual36, ett3, nde2 and nie9. Complete parents total 128,764 tokens; the 52-short-trace plus 4-parent policy totals 87,012 tokens; ordinary compression totals 86,970 tokens. Each ordinary compressed trace differs from its PNS-policy counterpart by at most 3 tokens. These are demonstration-bank reasoning lengths, not complete online prompt costs.

## 2. Sampling scope and historical exposure

The source is the 10,112 questions in `D:\CAUSE_DATASETS\dataset21_20260908\source_root\data\cladder-v1-balanced.json`, together with `cladder-v1-meta-models.json` in that directory. Background is joined through `meta.model_id`, which also serves as the causal-instance grouping key. The core scope contains only the five query types supported by existing demonstrations, namely ate, det-counterfactual, ett, nde and nie.

Exclude complete model_id groups for all known core256, challenge100, latest Phase56 and semantic-audit development items. Allocate the 300-question quota proportionally to the remaining counts across the five types. Use fixed seed 20260910, sample at most 1 question per model_id, and sample randomly within each type. This defines a restricted, instance-deduplicated population across five types. It is neither full-CLADDER coverage nor a challenge set balanced by historical baseline correctness.

Every source question has historical full-baseline exposure, so the cohort is termed a **baseline-exposed, group-disjoint follow-up evaluation**. The design excludes known development and demonstration instances and does not use new targets' historical correctness for this round's sampling or tuning. It cannot guarantee that historical outputs were never viewed or that no undocumented development use occurred. Graph topologies and story templates may recur across sets; no complete graph-family or template holdout is claimed.

## 3. Calling parameters and execution

| Parameter | Rule |
|---|---|
| Model | Qwen/Qwen3.6-35B-A3B; the observed service model ID/loading path is authoritative |
| Service | Native vLLM `/v1/chat/completions`; fixed qid routing when each GPU runs an independent TP1 service |
| thinking | enable_thinking=True, preserve_thinking=False |
| temperature / top_p / top_k | 1.0 / 0.95 / 20 |
| n / stream | 1 / False |
| min_p / repetition_penalty | 0.0 / 1.0 |
| presence_penalty / frequency_penalty | 0.0 / 0.0 |
| Context limit | 16,384 tokens |
| Shared four-condition output cap | For each target, min(12000,16384−max(exact serialised prompt tokens across four conditions)−128) |
| seed | Fixed target-level seed shared by all four conditions; this does not imply complete cancellation of stochastic sampling noise |
| Answer format | A strict single JSON object, `{"answer":"yes"}` or `{"answer":"no"}` |
| Scheduling | Fixed pseudorandom target order; balanced rotation of condition order within targets to reduce time/cache effects |
| Concurrency, revised before main execution | dev remains at 8 per GPU/16 total; main launch arguments set 24 per GPU/48 total |
| Failure handling | At most one primary POST per target×condition; unknown in-flight requests are not automatically resent. Any technical recovery of explicit failures is stored as a separate attempt with its recovery policy, preserving original results |

Sharing the output budget across conditions reduces differences in available output space during the main content comparison. This round does not directly test whether using saved context for more demonstrations further improves accuracy. Additional demonstrations and fixed-total-budget experiments remain future work.

On 2026-09-10, before the main experiment started or produced results, its infrastructure concurrency was set to 24 per GPU. Current vLLM logs reported 499,712 KV-cache tokens per GPU, equivalent to a theoretical concurrency of 30.50 at a 16,384-token window. The requirement 24×16,384=393,216 is below each GPU's cache capacity. Development remained at 8 per GPU. Only the runner's concurrency command-line argument changed. Prompts, random seeds, output caps, sampling settings and targets were unchanged, and all four main conditions shared this environment. Actual memory scheduling and throughput remain documented by execution logs. Latency is an environmental diagnostic within a run; dev–main latency differences cannot be interpreted as method effects.

The tokenizer must match the actual Qwen service. An older local tokenizer may support preparation, but final prompt budgets use the service's serialisation/tokenize output. If a target cannot fit the fixed 2-shot prompt, record a context failure and retain it in the primary denominator. Do not replace targets according to expected performance.

## 4. Ordinary compression rules

The model-free `heuristic_short.py` splits original CoT by sentence and newline. It assigns fixed simple weights to formulae, numbers, conclusion terms and causal terminology, while downweighting repeated checking language. It selects spans by score and restores source order. Sentences exceeding 128 tokens are processed as 64-token chunks. At most one source prefix fills the remaining budget. The procedure adds no reasoning, calls no teacher and does not select candidates by correctness.

Each demonstration's target length is its PNS reasoning-token count, with tolerance max(16 tokens,5%). Outputs record the exact length gap, retained spans and any truncated span. If some demonstrations cannot meet the tolerance, retain and report those failures without adjusting rules after viewing target outcomes. FULL/HEURISTIC/PNS append the same demonstration final answer. The answer is excluded from reasoning compression rates but included in complete prompt cost.

This control compares the complete PNS construction process with a transparent, inexpensive extractive baseline. It does not establish superiority over every prompt compressor or isolate the contribution of DELETE or REPLACE. Controls such as KEEP-only with matched construction budgets remain future work.

## 5. Prespecified analysis and ledgers

The primary endpoint is strict accuracy over all 300 frozen targets, with missing/API/format failures counted as incorrect. The primary effect is PNS_COT−FULL_COT accuracy, accompanied by complete prompt-input token savings on the same targets. PNS−HEURISTIC is the key secondary comparison; PNS−ZERO is supplementary evidence about the overall contribution of demonstrations. All three McNemar tests report raw and Holm-adjusted p-values. Query-type analyses are exploratory only.

Report gain, loss, both-correct and both-wrong counts, together with paired percentile 95% intervals from 20,000 model_id-group bootstrap samples. Each group contains one question here, so this equals question-level paired resampling. McNemar uses an exact two-sided binomial test. If full reasoning produces format failures, valid-only and both-valid results remain diagnostics and cannot replace the primary denominator.

Each request records arm, qid, group_id, demonstration qids and order, service/model, seed, request body, state, HTTP status, finish_reason, prompt/completion/total tokens and elapsed time. Ledgers separate historical offline generation and Judge calls, current offline compression, online evaluation and failure recovery. Unknown usage or billing is missing, not zero. GPU wall-clock time comes from service/task start and finish times, not summed request latencies. Monetary break-even reuse counts require consistent currency units and reliable records; otherwise report tokens and call counts.

The 300-question budget is an estimation choice under time constraints, not an automatically adequate sample size for significance or non-inferiority. With approximately 14% paired disagreement, the rough accuracy-difference interval half-width is 4.2 percentage points; at approximately 25%, it is 5.7 points. Actual intervals use the frozen results, and wide intervals must retain their uncertainty.

## 6. Delivery interfaces

- `prepare_holdout.py` accepts source data, metamodels and any number of historical-qid JSON/JSONL sources. It outputs `targets_public.jsonl`, `targets_scoring_only.jsonl` and selection_report.
- `heuristic_short.py` accepts canonical demonstration records `{question_id,query_type,gold_answer,full_cot,pns_cot}` and appends `heuristic_cot` and a length audit.
- `analyze_paired.py` accepts scoring targets and four `ARM=attempts.jsonl` inputs, supporting the earlier runner's `extracted` schema. It outputs per-question CSV scores and paired-statistics JSON and MD.
- `prepare_requests.py` obtains exact serialised lengths through local vLLM `/tokenize`, fixes the shared four-condition output cap and writes the request manifest. It calls tokenize only and generates no answers.
- `run_eval.py` is a Linux/Windows standard-library runner with persistent SQLite reservations before POST and unique qid×arm pairs. The two endpoints each default to concurrency 8; main execution overrides this with `--concurrency-per-endpoint 24`. Stable routing uses qid modulo 2. It supports resumed exports without resending reserved items and outputs `ARM.attempts.jsonl` per condition for analysis.
- `canonical56_with_heuristic.jsonl`, `freeze300/` and `dev10/` are this round's formal inputs with group separation. The 300 formal questions comprise ate94, ett82, det-counterfactual54, nie50 and nde20. Development uses 2 per type from historical challenge100, excluding every demonstration instance.

At delivery, no scripts had sent model requests or rewritten historical results. The main task centrally executes formal calls after writing the final demonstration bank, exclusions, target manifest and service parameters, following this protocol version.
