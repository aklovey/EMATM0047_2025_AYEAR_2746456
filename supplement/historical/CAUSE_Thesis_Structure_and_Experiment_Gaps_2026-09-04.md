# Recommendations for CAUSE thesis structure and experimental gaps

Prepared on 2026-09-04 from the complete Gmail series [CAUSE 1/8]–[CAUSE 8/8] and its key attachments available that day. This document recommends a thesis structure and experimental plan. It does not report new experimental results.

## 1. Recommended central argument

The proposed title is **Auditable Reasoning-Trajectory Compression for Few-Shot Causal Reasoning**.

The English working title is **Auditable Reasoning-Trajectory Compression for Few-Shot Causal Reasoning**.

The central question is whether auditable interventions on traces from causal questions already answered correctly by a model can produce shorter reasoning demonstrations with competitive accuracy and context costs on independent questions. PNS is the specific method. It should be defined through KEEP/DELETE/REPLACE prefix interventions and continuation search, without claiming that Pearl's PNS has been identified.

The existing engineering system supports data access, trace retention, answer validation, call records and evaluation. Early tool protocols, graph extensions, SkillOpt and truncation experiments explain how the research converged on this question. They do not need equal space as separate research themes. Results from different models, samples and metrics should not be connected into a single performance-growth curve.

Three contributions are recommended.

1. A causal-reasoning experimental framework that distinguishes answer correctness, path auditability and cost.
2. A demonstration-compression procedure based on original Qwen CoT, frozen parent traces and controlled continuation.
3. Empirical analysis of compression, ICL transfer and their failure conditions, including results that do not show an accuracy gain.

The third contribution still needs a final independent evaluation. Existing evidence is sufficient to draft the introduction, method, experimental setup and much of the pilot results. Writing should begin before every extension is complete.

## 2. Three research questions

| ID | Research question | Main observations | Current evidence status |
|---|---|---|---|
| RQ1 | Can trace interventions produce shorter causal-reasoning demonstrations that retain correct answers and pass path audits? | Frozen parents, candidate traces and the complete generation funnel | Historical batches have results; the latest Phase56 is at 52/56 and has not been closed |
| RQ2 | How does PNS-CoT affect accuracy and context cost on independent questions compared with full CoT and ordinary compression? | Paired question-level ICL outputs | The historical challenge set supports token savings; accuracy improvement and non-inferiority remain unconfirmed, and an ordinary-compression control is missing |
| RQ3 | Which factors limit compression and transfer, including continuation recovery, semantic drift, format failure, segmentation, judges and budgets? | Branches and error cases aggregated by question | Failure cases and historical diagnostics exist; independent auditing and limited mechanism analysis are still needed |

If time is limited, RQ3 can remain explanatory analysis. It need not promise strict causal identification, general skill learning or model internalisation.

## 3. How the eight reports fit into the dissertation

| Email | Content and role | Dissertation use | Conclusions it does not establish |
|---|---|---|---|
| [1/8](https://mail.google.com/mail/#all/1a06b8b7f4878058) | Latest Qwen PNS design; the 2 September PDF reports an experimental snapshot from 30 August, while the 4 September file proposes the next design | Method, experimental setup, current generation results and pending evaluation | The new proposal was not an executed experiment, and 52 results are not complete results for 56 questions |
| [2/8](https://mail.google.com/mail/#all/1a06b8c0a335d424) | Two-host experiment history and high-value findings, mainly through 18 August | Motivation, pilot studies and appendix | Different historical systems do not form one controlled experiment |
| [3/8](https://mail.google.com/mail/#all/1a06b8c631fc08a1) | Synchronisation-scope audit, conversation index and archive inventory | Reproducibility statement and electronic-supplement index | File and conversation counts are not scientific-contribution counts |
| [4/8](https://mail.google.com/mail/#all/1a06b8c78058cef0) | Experiment-evidence inventory and baseline/optimisation comparison inventory | Source checks for main results and setup-comparison table | An inventory does not replace original per-question outputs |
| [5/8](https://mail.google.com/mail/#all/1a06b8cf6e70bb1d) | Single-GPU execution, continuation probes and recovery status | Brief deployment description in Implementation, with small probes in the appendix | A three-question probe is not a stable model ranking; successful execution is not evidence of successful training or reasoning performance |
| [6/8](https://mail.google.com/mail/#all/1a06b8d1752a4442) | Unified historical Qwen test100 × 56-demo comparison and two workbooks | The most useful current ICL pilot evidence, which can move to the appendix once new formal results are complete | Different 56-demo versions cannot be mixed, and patched results cannot be treated as an independent 100-question run |
| [7/8](https://mail.google.com/mail/#all/1a06b8d58f29f7e0) | Method, static screening, dynamic preflight, correct-CoT bank and handoff | Method, data funnel and protocol-version descriptions | Static sensitivity is not model-level necessity, and a method-package description is not an execution result |
| [8/8](https://mail.google.com/mail/#all/1a06b8d826aaee1f) | Historical DeepSeek compression, label ablation and method disclosure | Exploratory representation experiments and semantic-fidelity failure analysis | These are not Qwen results, and gold-conditioned rewriting is not lossless extraction |

## 4. Proposed contents and page allocation

Under the previously supplied 30-page limit, initially target 25 pages of main text, leaving about five pages for the abstract, figure/table adjustments and references. The formal submission rules must determine which sections count towards the limit. Appendices and references should not be assumed to be exempt.

### Chapter 1 — Introduction, about two pages

Explain why causal-reasoning tasks require both correct answers and reliable reasoning, and why long CoT also adds context and inference costs. Motivate the study with two specific observations. Early tool agents showed a gap between answer performance and programmatic path acceptance, while the advantage of the 900-question scaffold largely coincided with fewer truncations.

Then introduce the three RQs, scope and contributions above. The main experiment concerns demonstration generation and ICL. LoRA, reinforcement learning and world models are not prerequisites for completing this dissertation.

### Chapter 2 — Background and Related Work, about three pages

Four sections are suggested, covering causal-reasoning tasks and benchmarks, CoT and few-shot ICL, reasoning/prompt compression, and trace interventions with LLM judges. Explain that formal operations on a causal problem and local interventions on model-generated text pose different identification problems.

Clarify the comparison by explaining what changes under full CoT, ordinary compression and controlled-continuation search. References must be completed from the original papers. This email review does not replace a literature review or support a claim of being the first such method.

### Chapter 3 — Method and System, about five pages

The suggested subsections are as follows.

1. **Task and data interfaces.** Describe unified inputs, public question text, offline oracles, answer validators and their access boundaries.
2. **Parent-candidate selection.** Present metadata-stratified sampling → baseline execution → baseline-correct cases → auditable/segmentable traces → frozen PNS pool. Retain denominators and exclusion reasons at every stage.
3. **Source-faithful segmentation.** Use contiguous character spans without omissions or overlaps. Steps after the first explicit or semantic answer exposure do not enter the necessity analysis.
4. **KEEP/DELETE/REPLACE search.** Anchor each step independently to the same parent C0 and generate the complete suffix. Freeze replacement text before repeated sampling.
5. **Candidate acceptance and selection.** Require a deterministic answer check, complete-chain semantic review and a strictly shorter complete chain. Select by token count, character count and candidate ID.
6. **ICL use.** Fix demonstration identities, routing, count, order, question text and answer format, changing only the reasoning representation under comparison.

Source fidelity is a requirement on segmentation and prefix provenance. It does not imply that the complete newly generated suffix is extracted from the original text. A correct answer after DELETE may arise through recalculation, reconstruction of deleted information or a valid alternative path.

A protocol-version table is necessary. The general method description in email 7/8 uses two repetitions per condition and parent fallback. The latest Phase56 instead freezes a 3→5-round protocol with strict shortening and no fallback. Erroneous REPLACE text in another dynamic-preflight file is a stress intervention, whereas Phase56 uses REPLACE as a candidate-improvement operation. These cannot be merged into one executed algorithm.

### Chapter 4 — Experimental Design, about three pages

Describe actual model versions, tokenizer, runtime budgets, data groups, demonstration/test separation, evaluation conditions, statistical methods and cost definitions.

At least three data roles should be distinguished. Development material supports method and candidate construction, challenge100 is balanced by earlier baseline correctness, and the final evaluation is unused for selection or tuning. If CLADDER contains parallel textual variants of the same causal instance, identifiable instance/graph and query families should inform leakage checks and statistical dependence.

The main metric is strict accuracy over every frozen target, with format failures counted as incorrect. Also report format validity, truncation, API failure, input/output tokens, complete-chain length and total construction cost. Path auditing and valid-only accuracy are supplementary measures and do not replace the primary endpoint.

### Chapter 5 — Results, about eight pages

Organise the chapter by research question.

1. **Reliability and budget diagnostics, about one page.** Select the most relevant old agent, truncation and protocol findings, explaining their influence on the current design.
2. **Demonstration generation and compression, about two pages.** Show the frozen sample funnel, accepted/failed/incomplete counts, compression distribution, branch provenance and costs.
3. **Independent ICL results, about three pages.** Report paired accuracy, format validity and context cost for full, PNS and ordinary-compression conditions. Query-type breakdowns are secondary analyses.
4. **Ablation and failure analysis, about two pages.** Cover ordinary compression, conservative/aggressive selection, recovery, judge or segmentation errors, retaining only completed and comparable experiments.

The third part can initially present the historical pilot, clearly marked exploratory. It must not imply that formal ICL evaluation under the latest protocol is complete.

### Chapter 6 — Discussion and Limitations, about three pages

Explain the observable benefits of compression, why accuracy may not improve, the conditioning introduced by selecting correct CoT, how model recovery affects step interpretation, limitations from judges and format failures, and how many reuses would amortise construction cost.

Use a DeepSeek rewrite that preserves the answer while changing the estimand as a central failure case. A correct binary answer is insufficient to establish preservation of the causal quantity and rules being calculated.

### Chapter 7 — Conclusion, about one page

Answer each RQ without adding unmeasured claims. Cross-dataset transfer or LoRA using compressed traces can appear as future work, not completed contributions.

The electronic appendix should retain historical experiment tables, complete prompts and schemas, protocol versions, manifests/hashes, paired per-question outputs, failure categories, cost ledgers and single-GPU deployment notes. Do not paste the entire conversation inventory into the main text.

## 5. Existing evidence and its scope

| Evidence | Numbers | Supported statement | Required boundary |
|---|---|---|---|
| Qwen correct-CoT bank | 10,112 baseline records; 9,239 correct usable CoT traces; static core of 256 | Large-scale baseline organisation and candidate stratification were completed | 256 is a static-candidate count, not 256 dynamically validated PNS-CoT successes or 256 training results [7] |
| Historical exhaustive PNS56 | Reasoning 128,764→79,021 tokens, −38.63% | This frozen historical bank is substantially shorter | It belongs to the 17 August system and cannot use the latest 52-trace denominator [6] |
| Historical FULL versus PNS ICL | Strict 71/100 versus 71/100; seven gains/seven losses; prompt 671,354→458,093, −31.77% | The challenge set shows the same accuracy point estimate with less input use | p=1 does not prove equivalence/non-inferiority; format validity falls from 100 to 97; ZERO's 50 is induced by sampling [2,4,6] |
| Historical Strong14 | 77/100; p=.0703 against FULL; 62/200 demonstration slots replaced | Conservative selection merits further evaluation | It is not significantly better than FULL, and the best condition cannot be selected after the fact as a confirmed finding [6] |
| Latest Phase56 | 52/56 completed; parents of the 52 traces 116,826→75,074 tokens, −35.74% | Compression and acceptance progress for the current successful subset | The PDF snapshot ends on 30 August; no formal 56-row artifact exists yet, and test100 has not been authorised under this protocol [1] |
| CausalMath adaptation control | Original independent 100-question run 63/100 with 79 valid formats; patched results 69/100 with 88 valid formats | The adaptation has format and transfer problems | The 69 combines 79 old and 21 selectively rerun questions; it is neither a conclusion about the full official implementation nor an independent full100 run [6] |
| 900-question scaffold | A749/900, B810/900; 59 of the net 61 gains come from A-truncated/B-completed cases | Completion-rate control matters under a fixed budget | Among 836 pairs completed by both, the difference is +0.24 pp with p=.8746; this conditional subset is diagnostic and does not decompose the complete causal effect [2,4] |
| Shared first pass | legacy935/974→934/974; calls3571→100; tokens11.140677M→1.424946M | Reports support a system-level contribution in call and token efficiency | This is a historical GPT-5.5 system, not a Qwen or PNS gain; the original report states that a non-inferiority gate passed, but this review did not recalculate it from per-question outputs [2,4] |
| DeepSeek compression/label experiments | 12 demonstrations and a 20-question challenge set; structured rewrites are substantially shorter | Exploratory representation and label-format comparisons can illustrate fidelity failures | Rewriting was gold-conditioned using GPT-5.5 and contained NIE/NDE semantic problems; it was neither lossless compression nor a strictly minimal sufficient chain [8] |

For costs, zero additional calls during historical offline reselection does not mean that candidate generation was free. The preceding candidate pool required 6,910 formal requests. The 31.77% figure is the complete-input token saving over that 100-question set, not a 31.77% reduction in end-to-end total cost.

## 6. Required work in order of completion priority

### P0-1. Close the latest Phase56 and freeze traceable material

The pending questions are q19407, q24494, q29833 and q30257. The old max-7 configuration covers only three of them. q29833 is the specific gap behind the expectation of 53 versus the observed 52. First record how this question will be handled and the maximum budget for each question, then resume through the existing checks. Do not replace a question with an easier one or treat a different historical batch of 56 as completion of this run.

Deliverables are a formal manifest, 56 terminal-state records with candidate lineage, length and answer audits, per-trace judge provenance, and failure/recovery ledgers. If 56/56 cannot be achieved within budget, report the protocol as incomplete. Any later failure-fallback policy should be a separate version rather than a retrospective change to the completion definition.

Among the current 52 traces, one used DeepSeek V4 Pro and 51 used GPT-5.5 as the judge. Retain these actual sources. An independent re-audit is supplementary and does not overwrite original results. The current request is for thesis planning only, not GPU startup or model calls.

### P0-2. Arrange an independent final comparison and distinguish workflow acceptance

Under the current frozen checks, run ZERO/FULL_COT/PNS_COT after achieving 56/56 and checking demonstration/test duplication. Do not insert new ablations directly into the old protocol.

The existing test100 is workflow acceptance if that protocol continues, rather than another independent evidence set the dissertation must necessarily add. If the next version can directly freeze the final method and a new holdout, formally revise the checks and use a necessary smoke test to connect to the new evaluation. Prioritise the independent results within the available budget. The existing checks should not simply be skipped without revising the protocol.

Whether this evaluation can be called held out depends on prior use for demonstration selection, selection-rule choice or tuning. If it reuses the 100 questions repeatedly analysed in earlier work, it should remain a development/challenge evaluation. A separate unused final set should then be sampled under a frozen new version.

Sample the final set through stratified random sampling from the target task distribution. Do not force another 50/50 balance by baseline correctness or select for PNS gains. A preliminary budget can assume 300–500 questions, while the formal N should follow from expected paired disagreement, the effect to detect or a predefined non-inferiority margin. Neither 100 nor 500 guarantees adequate statistical power. Multiple rollouts, steps or demonstration slots are not independent questions.

If all historical data have already been used in development, explain which new instances or group exclusions can still provide an unexposed evaluation. Renaming a set test does not restore independence.

### P0-3. Add a length-matched ordinary-compression control

The minimal main comparison for the next version is as follows.

| Condition | Content | Question addressed |
|---|---|---|
| ZERO | No demonstrations | Overall effect of adding demonstrations |
| FULL_COT | The same original questions and CoT traces | Full-demonstration baseline |
| HEURISTIC_SHORT | Ordinary compression without step interventions, at a length close to PNS | Whether shortening alone is sufficient |
| PNS_COT | CoT compressed through the current frozen procedure | Performance of the PNS procedure against these alternatives |

For a target, keep demonstration questions, count, order, routing, question text, final-answer format and decoding settings identical. Use the same tokenizer for length matching. Freeze length tolerance, failure handling and selection rules during development. Align the ordinary compressor's information access with the PNS generator's access. A stronger teacher or supplied gold labels must be recorded as a separate method factor if used.

First compare content replacement with the same two-shot setting. Then, under a predefined total context budget, compare how many demonstrations fit and how well they perform. The first comparison concerns content quality and the second concerns budget use. They are different effects.

RANDOM_SHORT, using random or position-matched deletion, is a low-cost mechanism ablation. A stronger claim that step interventions outperform repeated generation and selection also requires KEEP-only or ordinary resampling search, matched for candidate/call budget and answer, length and judge filters. Otherwise, only the complete procedure can be evaluated, and gains cannot be attributed separately to DELETE/REPLACE.

### P0-4. Independently calibrate the path judge and assess semantic fidelity

Stratify a sample of approximately 50–100 candidates across accepted, rejected and boundary cases, KEEP/DELETE/REPLACE, and long/short chains. Review them manually or deterministically without condition names, model names or selection outcomes. If only the 52 final accepted traces are available, review all 52 and add some rejected and boundary candidates. Report both candidate and unique-question counts.

The rubric should cover at least the target estimand, formula/intervention rules, factual and counterfactual worlds, key values/equations, conclusion support and answer leakage. Report false acceptance, false rejection, parsing failures and agreement. Population error estimates from stratified sampling need weights. Proportions from an artificially balanced sample are not population occurrence rates.

Segmentation review can use the same sample, checking whether boundaries preserve the complete text, whether critical steps were split incorrectly and whether another reasonable segmentation changes local conclusions. It need not become another large project.

### P0-5. Prespecify statistical endpoints and complete cost/failure accounting

Before viewing final results, decide whether the claim is an accuracy improvement or non-inferiority within a predefined margin with lower cost. For non-inferiority, specify an acceptable loss δ and sample size in advance, then test whether the paired-difference lower confidence bound exceeds −δ. A p-value above .05 is not a pass, and δ should not be enlarged after viewing results.

Report paired accuracy differences, confidence intervals, gains/losses and McNemar results. Use paired bootstrap resampling by question or genuinely independent causal-instance group. Distinguish primary and secondary analyses across query types and conditions and address multiple comparisons. valid-only and both-completed subsets help diagnosis, while the main denominator retains every frozen target.

Costs can usually be completed from existing logs without rerunning experiments. Include offline generation, judges, failures and retries, mean and quantile costs per accepted trace, and online complete-prompt tokens, completions, latency and format validity. Summed request latencies are not GPU wall-clock costs. Unknown bills are missing values rather than zero.

Where comparable same-currency costs exist, calculate `break-even reuses = additional offline construction cost / per-inference cost saving`. There is no break-even point if the denominator is nonpositive. Without reliable monetary costs, report tokens and call budgets rather than combining incompatible service prices.

## 7. Experiments required only by particular claims

| Item | When required | Smallest reasonable approach |
|---|---|---|
| Cross-dataset evaluation | The title or conclusions claim applicability to multiple causal tasks or cross-dataset generalisation | Choose one or two structurally different, verifiable datasets; use a 20–50-question pilot per dataset to estimate the selection funnel, then freeze independent evaluations. CounterBench or graph-structure queries are candidates, subject to checking actual inputs and validator coverage |
| Step necessity / recovery mechanism | The work claims repeatable operational necessity for a step type | Use a small preselected set of questions and steps with confirmation rollouts independent of selection. Eight to ten repetitions per condition are only a starting point. Distinguish bypass, semantic reconstruction, valid alternatives and failure; none automatically establishes Pearl's PNS |
| Matched resampling budget | The work claims that PNS interventions outperform ordinary search or selection from multiple candidates | Match KEEP-only or ordinary resampling to PNS for budget, verifier and selection, then evaluate on the same new test set |
| Formal comparison with CausalMath | Outperforming CausalMath is a main contribution | Freeze the complete repaired bank and run all targets independently. Identify the implementation as a protocol adaptation and audit model, budget and format comparability |
| Multiple seeds / demonstration pools | The work claims stability to random selection | Prespecify a few repeats during development, first checking the key FULL, ordinary-compression and PNS conditions. Retain within-question dependence in analysis |

Multiple query types within one dataset do not establish cross-dataset validation. Two successful demonstrations per type show that preparation can run, not that ICL is effective for that type. Cross-dataset results should include each dataset and a macro summary, with micro aggregation reported separately.

## 8. Work that can follow graduation

LoRA/SFT, RL/OPD, multi-epoch compression, world-model extensions, graph augmentation, full SkillOpt, simultaneous expansion to all 13 types, broader judge-provider comparisons, full-scale PNS and low-level KV-cache reconstruction can be deferred. Existing LoRA smoke material has not produced a reportable training checkpoint or test effect. If internalisation is not promised, there is no need to begin a new training programme.

Under a tight deadline, a frozen method, complete independent controls, semantic auditing and cost interpretation will usually support the dissertation better than ten unfinished systems.

## 9. Recommended main figures and tables

1. **Method diagram.** Separate offline parent selection/intervention generation, offline validation and online ICL, with clear boundaries showing that gold/oracle information supports offline scoring only.
2. **Data-funnel table.** Show the original pool, baseline sample, correct, eligible and accepted counts, with exclusion reasons. Separate historical and current material.
3. **Main-results table.** Give strict accuracy, paired differences and CIs, format validity, prompt/completion tokens and costs for each condition.
4. **Compression-distribution figure.** Show question-level compression rates and failure coverage instead of only an aggregate percentage for successful traces.
5. **Error-analysis table.** Include seven gains/seven losses, format failure, semantic drift and reconstruction after continuation, with two or three complete examples.
6. **Cost figure or table.** Relate construction cost to amortisation over reuse. Where evidence is incomplete, retain the original token and call tables.

A single curve showing accuracy rising continuously from May to September is not recommended, because models, samples, budgets, input access and scoring rules changed repeatedly.

## 10. Suggested wording for the current results

> On a 100-question challenge set balanced by historical baseline outcomes, two-shot ICL with PNS-compressed demonstrations and with full-CoT demonstrations both achieved 71% strict accuracy. The PNS condition reduced total complete-input tokens by 31.77%, while format compliance fell from 100% to 97%. Paired outcomes included seven gains and seven losses. This experiment supports the feasibility of resource compression but does not establish improved accuracy, equivalence or non-inferiority. A separate, stricter Phase56 protocol has currently accepted 52 traces, with a 35.74% reduction in complete reasoning tokens over its successful subset. Its complete demonstration set and downstream ICL evaluation remain unfinished.

This paragraph should be labelled as pilot evidence and current progress. The final abstract must be updated after independent evaluation rather than prematurely claiming a significant improvement in reasoning performance.

## 11. Minimal execution order

1. Draft Chapters 1–4 immediately and organise Chapter 5's historical pilot and existing generation results.
2. Check q29833's recovery rule and budgets for all four pending questions, then complete or explicitly terminate Phase56 while retaining every terminal state.
3. If the current frozen process continues, check duplication and complete three-condition test100 while retaining its development/challenge status. If a formal revision goes directly to final evaluation, connect the new holdout through necessary smoke checks and avoid redundant spending.
4. After independent auditing and development analysis, freeze the next ordinary-compression control, primary endpoint and new evaluation manifest.
5. Run one complete paired final evaluation and analyse accuracy, format, cost and failure, without repeatedly adding samples based on significance.
6. Add the corresponding small studies only if the dissertation still promises cross-dataset or step-mechanism claims, then complete the discussion and conclusion.

## 12. Sources and review scope

[1] Email 1/8 includes `2026-09-04_qwen_pns_experiment_design_progress.md` and extractable text from `2026-09-02_qwen_pns_experiment_report_mobile_v2.pdf`, including its 14 pages of status and protocol descriptions.

[2] Email 2/8 includes `HIGH_VALUE_EXPERIMENT_BRIEF.md`, `CAUSE_SYNC_README.md` and the returned portion of `DETAILED_EXPERIMENT_REPORT.md`. Extraction of the long historical attachment was marked truncated, and its full extraction link was unavailable in this review. Key historical numbers here are cross-supported by the complete brief and email 4/8 inventories. No conclusion relies on the missing portion.

[3] Email 3/8 includes `SYNC_AND_SCOPE_AUDIT.md`, package inventories, and conversation summaries/date counts. The large per-conversation inventory is an existence index rather than evidence of effectiveness.

[4] Email 4/8 includes `baseline_optimization_comparison_catalog.csv` and `experiment_evidence_catalog.csv`.

[5] Email 5/8 includes `QWEN35_SINGLE_GPU_SMOKE_TEST_REPORT.md`, `QWEN36_REASONING_ASSETS_FINAL_REPORT.md` and `QWEN36_REASONING_ASSETS_STATE_AND_RESUME.md`. Model names follow the actual reports and are not all renamed Qwen3.6 based on the email subject.

[6] Email 6/8 includes `qwentest100_demo56_unified_comparison_20260818.md`, the unified-comparison workbook and the repaired-only workbook.

[7] Email 7/8 includes the PNS method, general-logic README, full-baseline screening README, and descriptions of static screening and dynamic preflight.

[8] Email 8/8 includes `COMPRESSION_METHOD_DISCLOSURE_POSTHOC_CN.md`, `raw_full_report.md`, `label_ablation_report.md`, `cot_only_report.md` and the historical-reference README.

This review organises evidence from emails and attachments. It reran no model, training or statistical code and did not verify every original journal, per-question output or commit hash cited by the attachments. Final dissertation tables should be generated from frozen original results with protocol versions and sources recorded.
