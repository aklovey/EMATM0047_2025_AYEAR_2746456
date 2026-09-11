# Completed work on five key gaps in the CAUSE dissertation

Updated on 2026-09-10. The research question is **whether auditable reasoning-trace compression can improve the efficiency of few-shot causal reasoning**. CLADDER is the main dataset. This work covers five query types, namely ATE, deterministic counterfactuals, ETT, NDE and NIE.

**The answer is yes for this prespecified extension using new numerical instances.** On 246 questions, the PNS policy scored 224/246 (91.06%), while FULL and length-matched ordinary compression each scored 208/246 (84.55%). The gain over each was 6.50 percentage points, with six-comparison Holm-adjusted p-values of 0.00998 and 0.02100. Relative to FULL, input tokens fell by 18.62% and output tokens by 11.05%. This result applies to the generated, validity-filtered frontdoor/mediation tasks across four probabilistic query types and the current single demonstration policy. The 300-question follow-up on existing data did not establish an accuracy advantage for PNS over FULL or ordinary compression. High offline construction cost, limited semantic validation and untested multiple seeds/demonstration pools continue to limit the conclusion.

This report replaces the progress snapshot in the original recommendations. The original MD and DOCX remain unchanged, as do the raw experiment databases. Approval requirements in older material belong to historical protocols. The current completion plan was executed within the deadline under the user's authorisation. Failures are retained as outcomes, without continuing search merely to raise the success rate.

## Final status of the five work items

| Work item | Delivered material | Scope of the conclusion |
|---|---|---|
| P0-1 Phase56 closure | 56 closure rows, 52 short traces, four unaccepted parents with provenance, segmentation/prefix/suffix checks and cost evidence | Closure with failures is complete; this is not 56/56 success under the old protocol |
| P0-2 Independent comparison | Four-condition outputs for 300 existing-data instances and 246 new probabilistic SCMs, plus ten development instances | The 300 questions have historical baseline exposure; the 246 are new instances from the official generator with independent checks, and the cohorts are analysed separately |
| P0-3 Length-matched ordinary compression | Identical demonstration identities/order, with ordinary extractive compression within three tokens of PNS for each trace | Compares the whole procedure with this inexpensive control; does not identify the separate contributions of DELETE/REPLACE |
| P0-4 Semantic review | Deterministic component checks for all 56 questions and a separate blinded model-assisted review of 12 candidates | Independent human truth for complete natural-language paths is still absent, so full judge FPR/FNR calibration is not established |
| P0-5 Statistics, cost and failure | Frozen main denominators, CPT-group paired analysis, McNemar tests on new instances, six-comparison Holm correction and separate offline/online accounting | No unplanned non-inferiority claim; unknown bills and call costs remain missing rather than zero |

## P0-1. Complete Phase56 closure with failures

The authoritative source is `qwen_pns_phase56_20260826_v2_recovery_18plus3_v1` under the source host's `E:/wt/cause-qwen-pns-adaptive-20260826`. Existing logs were read without resending Phase56 generation or judge requests, and the max-7 extension was not executed. The old database retains 52 completed and four pending records. The new closure records the four questions as lacking an accepted trace at the deadline.

| Metric | Value |
|---|---:|
| Originally planned / accepted / unaccepted at closure | 56 / 52 / 4 |
| Acceptance rate | 92.86% |
| Parent / compressed tokens in successful subset | 116,826 / 75,074 |
| Compression rate in successful subset | 35.74% |
| Selected KEEP / DELETE | 22 / 30 |
| REPLACE / replacement generation in this Phase56 run | 0 / 0 |
| Final judge provenance | 51 GPT-5.5 traces; one DeepSeek V4 Pro trace |
| New Phase56 calls during this work | 0 |

| Unsuccessful question | Type | Historical diagnosis and why a correct yes/no answer was insufficient |
|---|---|---|
| q19407 | ETT | The counterfactual quantity for the treated population was confused with population ATE or a general intervention quantity; handling of confounding was incomplete |
| q24494 | ETT | An observed conditional difference or population effect replaced the counterfactual quantity conditional on treatment |
| q29833 | Deterministic counterfactual | A downstream variable was held fixed after intervention and AND/OR relations were confused; both shorter final candidates with matching answers were rejected |
| q30257 | Deterministic counterfactual | Negative relations and post-intervention structural updates were mishandled, with some inconsistent deductions |

These failure explanations initially come from historical judges. The separate independent-review coverage is reported below. PNS here denotes prompt-prefix interventions and continuation search anchored to frozen parents. It is not identification or estimation of Pearl's PNS. REPLACE is a conditional implementation branch that was not triggered in this run, so no empirical effect is reported for it.

## P0-2. Comparison with new instance exclusions

The original challenge100 set was constructed with 50 previously correct and 50 previously incorrect baseline answers. Recalculation gave FULL 71/100, historical PNS 71/100 and Strong14 77/100, with seven gains and seven losses between FULL and PNS. More importantly, the old challenge set shared eight model_id values with core256 and two with the actual demo56 despite having different question IDs. Historical results therefore remain exploratory pilot evidence.

This work excluded model_id groups belonging to core256, challenge100, Phase56 and development cases from the 10,112 CLADDER questions. The five query types left 4,409 questions with 3,006 model_id values available for sampling. Proportional sampling by query type with fixed seed 20260910 selected 300 distinct model_id values, comprising 94 ATE, 54 deterministic counterfactual, 82 ETT, 20 NDE and 50 NIE questions. The development check used ten additional model_id values, with no ID intersection with the main evaluation or demonstrations. Sampling did not read old baseline correctness, and the sample was not expanded based on results.

A subsequent check of actual parameters found that the 300 IDs correspond to only 271 complete graph+CPT groups, with 45 questions in 16 repeated groups. The union of historical demo/core/challenge material overlaps 59 targets across 32 complete-CPT groups. Of these, 23 targets across 14 groups overlap demo56. Thus, **model_id separation does not establish mechanism independence**, and the earlier ID-based independence statement was corrected. All 300 questions are retained as a follow-up evaluation with mechanism reuse, supplemented by CPT-group statistics. The actual CPT separation of the 246 newly generated questions was checked independently.

All source questions have historical baseline exposure, so this is a **baseline-exposed, group-disjoint follow-up evaluation**. Graph topology and story templates may recur, and unknown historical development use cannot be fully excluded.

The 52-success pool contains only one ETT trace and cannot provide two distinct same-type examples. The new downstream policy therefore retains 56 demonstration identities, using accepted short traces for 52 and exact parent fallback for the four unaccepted questions. This revision does not change the original Phase56 success rate. Each formal few-shot condition has 600 slots, comprising 483 compressed slots and 117 fallback slots.

| Condition | Strictly correct / 300 | Accuracy | Format valid | Truncations | API failures / missing | Input tokens | Output tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| ZERO | 254/300 | 84.67% | 293 | 0 | 0 | 66,982 | 543,770 |
| FULL_COT | 277/300 | 92.33% | 300 | 0 | 0 | 2,093,177 | 370,815 |
| HEURISTIC_SHORT | 272/300 | 90.67% | 297 | 0 | 0 | 1,670,645 | 400,950 |
| PNS_COT | 279/300 | 93.00% | 300 | 0 | 0 | 1,670,526 | 370,548 |

| Paired comparison | Accuracy difference in percentage points | 95% CPT-group interval in percentage points | Gains/losses | CPT permutation p, MC | Within-cohort Holm p |
|---|---:|---|---:|---:|---:|
| PNS_COT versus FULL_COT | +0.67 | [-2.02, +3.49] | 10/8 | 0.814571 | 0.814571 |
| PNS_COT versus HEURISTIC_SHORT | +2.33 | [-0.33, +5.05] | 12/5 | 0.142719 | 0.285439 |
| PNS_COT versus ZERO | +8.33 | [+5.02, +11.84] | 28/3 | 4.99998e-06 | 1.49999e-05 |

The measured complete-input token saving relative to FULL is **20.19%**. The main denominator remains 300 questions. Intervals use 20,000 resamples of the 271 complete-CPT groups, while p-values use 200,000 whole-group sign flips with a plus-one correction. This supplementary analysis assumes exchangeability of condition labels at group level. It is not an RCT with randomly allocated conditions. The originally planned question-level McNemar tests and intervals remain in the original analysis files as diagnostics, rather than strict tests under independent mechanisms. Equal point estimates or nonsignificance are not interpreted as non-inferiority.

### New-instance extension using the official generator

Before viewing any accuracy result for the 300 questions above, an extension was fixed with 246 new probabilistic SCMs, comprising 94 ATE, 82 ETT, 20 NDE and 50 NIE questions. Each SCM provides only one evaluation target. The work used RandomBuilder and generate_questions from official CLADDER commit `3d2d1169b4b939a09048a6a75956c8972a93cc38`, without changing the authors' source. ATE/ETT use frontdoor graphs and the smoking_frontdoor story. NDE/NIE use mediation graphs and six existing stories.

All CPTs are proposed from Uniform(0,1), then screened using predefined mechanism-novelty checks and agreement among original, independent and public-precision labels. The evaluation therefore follows a **conditional distribution after validity screening**, rather than the original balanced distribution or unfiltered Uniform sampling. Of 257 attempts, 246 were retained and 11 excluded. Nine exclusions involved both a label-direction convention conflict and a public-precision conflict, with one additional case in each category alone. The authors' assignment of no to very small ATE/ETT values is a labelling convention, not a numerical calculation error.

None of the 246 complete or target-relevant CPTs duplicates the 7,064 historical model metadata records, the eight small-probe models or another new instance. Independent numerical and label checks passed for 246/246. The number of metadata records is not the number of distinct CPTs. This separation comes from new causal parameters rather than renamed question IDs or reworded text. Story templates and graph families are still reused, so the results do not establish cross-story, cross-graph or new deterministic-Boolean-mechanism generalisation.

| Condition | Strictly correct / 246 | Accuracy | Format valid | Truncations | API failures / missing | Input tokens | Output tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| ZERO | 187/246 | 76.02% | 240 | 3 | 0 | 65,759 | 823,411 |
| FULL_COT | 208/246 | 84.55% | 246 | 0 | 0 | 1,898,530 | 446,995 |
| HEURISTIC_SHORT | 208/246 | 84.55% | 243 | 0 | 0 | 1,545,106 | 466,829 |
| PNS_COT | 224/246 | 91.06% | 245 | 0 | 0 | 1,545,034 | 397,597 |

| Fresh-instance paired comparison | Difference in percentage points | 95% paired interval in percentage points | Gains/losses | McNemar p | Within-cohort Holm p |
|---|---:|---|---:|---:|---:|
| PNS_COT versus FULL_COT | +6.50 | [+2.44, +10.57] | 21/5 | 0.00249392 | 0.00498784 |
| PNS_COT versus HEURISTIC_SHORT | +6.50 | [+2.03, +10.98] | 24/8 | 0.00700037 | 0.00700037 |
| PNS_COT versus ZERO | +15.04 | [+10.16, +20.33] | 41/4 | 9.33488e-09 | 2.80046e-08 |

| Cohort | Comparison | Joint six-comparison Holm p |
|---|---|---:|
| released_followup300 | PNS_COT versus FULL_COT | 0.814571 |
| released_followup300 | PNS_COT versus HEURISTIC_SHORT | 0.285439 |
| released_followup300 | PNS_COT versus ZERO | 2.49999e-05 |
| fresh_SCM246 | PNS_COT versus FULL_COT | 0.00997567 |
| fresh_SCM246 | PNS_COT versus HEURISTIC_SHORT | 0.0210011 |
| fresh_SCM246 | PNS_COT versus ZERO | 5.60093e-08 |

The cohorts are not pooled into a 546-question accuracy estimate for one distribution. Each retains its three planned comparisons, with an additional Holm correction over all six comparisons. This decision also preceded reading effects from the first cohort.

## P0-3. Length-matched ordinary compression

The ordinary compressor accesses only the demonstration's original CoT and known answer. PNS supplies a length budget without influencing content selection. Fixed rules split text by sentences/newlines, assign weights to formulas, numbers and causal terms, downweight repeated checking language, and restore the original order after selection. Long passages are divided into blocks, with an original-passage prefix used to fill the budget if needed. The procedure generates no new reasoning and does not select content using target answers.

| Demonstration-bank representation | Total reasoning tokens | Description |
|---|---:|---|
| FULL | 128,764 | 56 original traces |
| PNS policy | 87,012 | 52 short traces plus four parent fallbacks, a reduction of 32.43% |
| HEURISTIC | 86,970 | Within three tokens of the PNS policy for every trace |

The three few-shot conditions share demonstration questions, count, order, question text, final-answer format and decoding parameters for each target. All four conditions use a common output-token cap, so the main comparison does not conflate content quality with extra output space made available by compression. Increasing demonstration count within a fixed total context budget has not been tested and remains future work.

## P0-4. Independent checks and fidelity limitations

Deterministic checks cover all 56 questions. Independently recalculated source-label directions agree for 56/56, and all 52 short traces pass segmentation-continuity, original-prefix-plus-continuation reconstruction and same-tokenizer length checks. The authors' displayed source expressions contain 19 numerical inequalities and one missing-operator ambiguity. Exact values for four NIE/arrowhead questions still differ from stored groundtruth, while label signs agree. These are source-reference issues and cannot be attributed to compression.

Candidate arithmetic extraction covers 135 computable equations in 13/52 traces, with no local inequality found. The remaining 39 traces are uncovered. Old candidate final_content values are correct for 52/52 after case normalisation, but only 50/52 use strict lowercase JSON. The two capitalised No values are recorded separately, and a no appearing in a format template is not misread as the conclusion.

After unblinding the 12-candidate model-assisted review, five of the eight originally accepted traces passed the complete-trajectory criterion and three had substantive flags. All four candidates from unaccepted questions were flagged. Three failed candidates nevertheless contained valid main proofs alongside incorrect auxiliary claims. All 12 final yes/no answers agreed with independent calculations, showing that answer direction and complete-trajectory validity are different properties. The q29833 error already existed in its parent and was retained in the rejected continuation, so it cannot be attributed to DELETE.

Under the user's additional authorisation, a further 56-item Qwen same-model self-review was run. Its actual state is `{"review_truncated": 27, "review_parsed": 29}`, with overall valid judgements `{"unknown": 27, "pass": 29}`. It received only public question text and candidates, without gold, oracle output or old judge decisions. It used temperature 0, enabled thinking and an output cap of 4096 tokens. Failures and truncations were not retried. Its information conditions differ from those of the model-assisted blinded review, so disagreements cannot all be attributed to model capability. This diagnostic did not change the demonstrations fixed for the main comparison.

The 29 parsed records are model self-reported passes, not independent audit passes. Among their 145 quotation slots, 65 nonempty quotations match exactly, 28 are empty and 52 are nonverbatim, affecting 26 reviews. No quotation exceeds 180 characters. A nonverbatim quotation is a quotation-accuracy flag rather than automatic evidence of a semantic hallucination. Two reviews of candidates from unaccepted questions also self-reported a pass, further showing why same-model review does not directly replace independent truth.

An independent tool establishes only the properties it actually checks. Agreement with source labels, presence of a number or a correct equation does not establish correctness of an entire natural-language derivation. The 12 blinded reviews concealed the old judge, selection status, condition and model names, but remain model-assisted analyses rather than human expert labels. Their enriched sample does not estimate the candidate population's false-acceptance rate. The practical conclusion is that inspectable evidence of semantic risk has been added, while **calibration of the complete-path judge remains unestablished**.

## P0-5. Statistics and end-to-end cost

The primary endpoint is strict accuracy on all frozen targets in each cohort. API failures, missing responses and format failures count as incorrect. The main comparison is PNS−FULL, with PNS−HEURISTIC as the key secondary comparison and PNS−ZERO as supplementary. The 300-question analysis retains the planned question-level analysis as a diagnostic. After discovering repeated CPTs but before reading results, sensitivity analyses were specified using bootstrap resampling and whole-group sign flips over 271 complete-CPT groups. The 246 new instances use 20,000 instance-level paired bootstrap resamples and exact McNemar tests. Both within-cohort three-comparison Holm and joint six-comparison Holm results are reported. The joint family uses group-permutation p-values for main300 and exact McNemar p-values for fresh246. No non-inferiority margin was set, so nonsignificance cannot prove equivalence or non-inferiority.

| Stage | Recorded calls | Observed token cost | Incomplete coverage |
|---|---:|---|---|
| Historical fixed PNS, 17 August | 6,910 | Qwen input 6,141,543, output 14,468,773 | This version is separate from the new Phase56 |
| New Phase56 Qwen | 14,636 physical dispatch records | Original-ledger input 12,491,141, output 28,901,182 | Includes 128 old recovery dispatches; usage still excludes some recovery, old unknown calls and canaries; this is not an independent-sample count |
| Phase56 DeepSeek judge | 2,747 known provider calls | Input 9,238,246, output 12,881,167 | A further 46 reserved outcomes are unresolved |
| Phase56 isolated GPT default-effort review | 113 | Input 468,097, output 64,161 | Costs from the discarded configuration remain recorded |
| Phase56 GPT xhigh recovery | 113 | Input 476,007, output 275,727 | Separate from default effort |
| Phase56 final GPT future ledger | 11,718 | Input 43,222,853, output 21,187,196 | A further 24 reserved records; old copied views are not added again |
| Current ordinary compression and deterministic audit | Zero model calls | Local computation | Local time is not zero, but there are no model-token charges |

The 300-question follow-up contains 1,200 frozen requests, with measured totals of 5,501,330 input and 1,686,083 output tokens. The 246 new instances add 984 requests, with 5,054,429 input and 2,134,832 output tokens. The development check completed 40 additional requests, using 187,032 input and 62,438 output tokens. Two few-shot conditions had format failures, which counted as incorrect without prompting method changes. Reported usage for the 56 same-model reviews is `{"prompt_tokens": 126818, "total_tokens": 323482, "completion_tokens": 196664}`. Planned generation calls total 2,280, comprising 1,200 main, 984 fresh, 40 development and 56 self-review calls. Actual dispatches and failures are recorded in the accompanying SQLite and terminal-state files. A further 2,280 tokenisation-only preparation requests are separate from generation calls.

Development concurrency was eight per GPU. The main comparison used 24 per GPU, or 48 in total. Before the main comparison started, each service reported 499,712 available KV-cache tokens per GPU. Because 24×16,384=393,216, concurrency was raised on that basis to improve throughput. Model parameters, prompts, targets, seeds and output caps remained frozen across the main conditions. Latency differences between development and main evaluation are not method effects.

Calls and tokens are separated by actual model and stage. Tokens from different services are not simply added and converted into money. Summed request latency is not GPU wall-clock time. The platform bill was checked directly. D41's two GPUs ran from 2026-09-10 05:25:41 to 07:29:46, lasting two hours, four minutes and five seconds. Three balance deductions of CNY 7.99, 13.97 and 6.93 totalled **CNY 28.89**. This covers the full power-on cycle, including all current experiments and preparation, rather than one condition. It excludes the existing data-disk daily charge, historical PNS construction, historical external judging and unmetered Codex assistance. D41 was shut down without releasing the instance.

Complete monetary costs comparable across stages are still missing, so no monetary amortisation point is calculated. That metric requires reliable same-currency costs and a positive per-use saving. Historical equal-weight token amortisation is only a count ratio, not actual financial break-even.

## Parameter table for the dissertation

| Parameter | Current main comparison |
|---|---|
| Generation model | Qwen/Qwen3.6-35B-A3B, local BF16 weights |
| Hardware / inference service | Two RTX PRO 6000 Blackwell GPUs, each with TP=1; vLLM 0.27.1 |
| Context / output | 16,384; shared per-target cap min(12,000,16,384−maximum prompt tokens across four conditions−128), observed range 6,974–12,000 |
| temperature / top_p / top_k | 1.0 / 0.95 / 20 |
| min_p / repetition penalty | 0 / 1 |
| presence / frequency penalty | 0 / 0 |
| thinking / preserve_thinking | Enabled / False; demonstration reasoning is placed explicitly inside one user message |
| seed | 20260910 + target qid, identical across four conditions |
| API | Loopback `/v1/chat/completions`, one POST per target×condition |
| Concurrency | Development eight per GPU; main comparison 24 per GPU, 48 total |
| Caching and scheduling | Prefix caching enabled; fixed pseudorandom target order and rotating condition order; latency used only as an environment-dependent diagnostic |
| Routing | Same-type two-shot selection by dataset query type, with the same metadata-assisted routing for all few-shot conditions |
| Main format | A single JSON object with lowercase yes/no in answer |
| Samples | Main 300×4; development 10×4; model_id separation between sets |

## Dissertation structure and future work

The dissertation has seven chapters, covering introduction, background and related work, method, experimental design, results, discussion and limitations, and conclusion. The main text centres on traceable compression, few-shot use and cost interpretation, retaining failures. The old DOCX supplied the formatting and verified references, while the remaining text was rewritten.

Editable method diagrams use native Draw.io nodes and connectors, accompanied by SVG, PDF and preview exports. Parameters, protocol versions and failure types are presented in tables. A monthly accuracy-improvement curve spanning different models and samples should not be drawn.

LoRA/SFT, RL, world models, full SkillOpt, cross-dataset transfer, full-scale PNS, more judges, additional demonstrations under a fixed total budget, and budget-matched KEEP-only search remain future work. These experiments were not completed and are not presented as contributions.

## Evidence entry points

- `evidence/historical_evidence_audit.md` and `historical_test100_paired.csv` contain recalculation of the old 100-question results, instance overlap and historical costs.
- `evidence/phase56_closure_and_parameters.md` records the new 56-row closure, ledgers and lineage.
- `evidence/independent_semantic_and_arithmetic_audit.md` contains deterministic component checks for the 56 questions.
- `evidence/blinded_model_assisted_review.md` contains the 12-candidate blinded review and its limitations.
- `experiment/` retains frozen inputs, decoding parameters, per-question outputs, statistical scripts and failures.
- The historical `thesis/` delivery contained the rewritten dissertation DOCX/PDF, figure sources and editable flowcharts.

The original public CLADDER sources are the [project and code](https://github.com/causalNLP/cladder) and the [NeurIPS 2023 paper](https://papers.nips.cc/paper_files/paper/2023/file/631bb9434d718ea309af82566347d607-Paper-Conference.pdf). Every experiment number in this report comes from logs read or generated during this task, rather than inference from paper abstracts or memory.
