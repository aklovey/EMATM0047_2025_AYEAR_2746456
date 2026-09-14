# Phase56 closure and runtime checks, 2026-09-10

The existing Phase56 run was closed with **52/56 accepted traces and 4/56 parents without an accepted trace**. The original databases retain 52 completed and four pending records, and the new report does not change that history. There were zero new Phase56 model calls, and the original max-7 recovery plan was not executed.

## Available local material

- `phase56_accepted52_demo_pool.jsonl` contains 52 complete full_cot / pns_cot pairs, their Qwen token counts, qid, query_type, gold_answer, original question messages, selected request keys and audit fields.
- `phase56_original_inputs56.jsonl` contains the 56 complete original inputs and segmentations for exclusions at the instance-group level.
- `phase56_closure_all56.jsonl` contains 56 closure rows, including complete historical artifacts. Failed rows have pns_cot=null, so a parent trace is not presented as a successful compression.
- `phase56_selected_lineage52.jsonl` contains frozen_prefix, reasoning_suffix, complete_chain, final_content and prompt_key for the 52 selected lineages. All 52 satisfy prefix+suffix=chain=selected artifact character for character. The original q30359-s001-delete-r2 entry had posting status. Its lineage was reconstructed from the existing succeeded g1 sidecar, with that source recorded.
- `phase56_pending_candidate_rows.jsonl` and `phase56_pending_judge_rows.jsonl` preserve the complete original candidates and judge rationales for the four unsuccessful questions.
- `phase56_source_export.json` is a 39 MB read-only export containing all items/result records, relevant candidates, judge records and contracts. It does not replace the complete original HTTP database. The original journal remains on the source host.
- `phase56_closure_summary.json` and `phase56_failed4.jsonl` provide the reported numerical summary and failure categories.
- `phase56_ledger_accounting.json` separates counts and token usage by original ledger.
- `live_runtime_20260910.json` records the live argv, GPUs, model lists and health responses for the two D41 services during this run.

## Findings supported by the records

The 52 selected traces were individually rechecked for optimized=true, fallback=false, a valid deterministic answer, judge acceptance and strict shortening relative to the parent. Total complete-chain tokens fell from **116,826 to 75,074**, a reduction of **41,752 tokens (35.74%)**. The success rate was **52/56 (92.86%)**, and the compression rate applies only to the successful subset. These are construction results rather than downstream accuracy results.

The final selections comprised **30 DELETE traces and 22 KEEP traces**. The original generation journal contains **7,947 KEEP and 6,561 DELETE records**, with no REPLACE or replacement_generate entries. REPLACE is therefore a conditional implementation branch for which this run provides no execution evidence. The run cannot be described as an empirical comparison of three interventions.

The final judges for the 52 selected traces were **GPT-5.5 for 51 traces and DeepSeek V4 Pro for one trace**. This batch did not use a single judge source throughout. The 113 GPT recovery reviews also do not represent all judge calls for the batch.

| qid | Type | Original requests | Reason for closure without acceptance |
|---:|---|---:|---|
| 19407 | ett | 207 | ETT was treated as population ATE or an ordinary intervention effect. The reasoning did not correctly handle conditioning on the treated population and unobserved confounding. Historical judges repeatedly rejected it. |
| 24494 | ett | 175 | ETT was treated as an observational conditional difference or a population effect. Confounding and the treated-population condition were omitted. Historical judges repeatedly rejected it. |
| 29833 | det-counterfactual | 198 | Both candidates reaching final materialisation matched the answer and were shorter, but incorrectly held muvy at false after intervention and confused AND and OR gates. Both were rejected. |
| 30257 | det-counterfactual | 145 | A negative causal relationship was misread. Counterfactual updates relied on unsupported assumptions, and some traces contained internal contradictions. Historical judges repeatedly rejected them. |

These explanations come from historical judges and provide traceable error diagnoses, rather than a new human gold standard. A candidate can have a correct answer flag and be shorter while still failing semantically. All four questions had such candidates. The rejection rationales for both q29833 materialisation requests have been retained. Their substantive problem was incorrect updating of the counterfactual structure, not a missing file or an absent judge call.

## Budgets and call accounting

The frozen policy used 3→5 valid matched rounds, with at most five raw attempts for each KEEP/DELETE/REPLACE lineage. Invalid attempts did not vote. A replacement-generation call was conditional on a trigger. For 1,691 safe steps, the conservative generation ceiling was **1,691 × (5+5+1+5) = 27,056**, excluding judges, tokenisation, canaries and additional recovery dispatches. No further generation was undertaken at closure, so the new budget was **0**.

The original Qwen journal has **14,508 rows**, comprising 14,338 completed, 42 scientific_invalid and 128 posting records. All 128 posting records have succeeded dispatches in existing g1 sidecars. Their original rows remain unchanged. Physical dispatch records therefore total **14,508+128=14,636**, but g1 dispatches are not additional scientific samples. The original 56-question recovery directory is a copied view and must not be added again to the original journal. The observed number of sixth or seventh raw slots is zero.

Known provider_call_count values in the judge ledgers are 2,747 for DeepSeek, 113 for the isolated GPT default-effort version, 113 for GPT xhigh strict recovery, and 11,718 for the latest future ledger. These sum to **14,691** known calls. A further 46 historical DeepSeek records and 24 future reserved records have unresolved outcomes and cannot be counted as zero cost. The original future count of 11,703 is already included in the recovery ledger count of 11,718 and must not be added twice. Separate canaries are outside these totals. Any reported overall cost should identify these as recorded call counts or a lower bound.

Stored usage in the original Qwen journal is 12,491,141 input tokens, 28,901,182 output tokens and 41,392,323 total tokens. This excludes 128 original calls with unknown usage, g1 recovery usage and separate canaries, so it is not a complete cost total. Per-route judge usage is recorded in the JSON. The two copied future ledgers must not be summed together.

## Runtime parameter snapshot

The D41 instance was `fxqnqh00m3-1d1e6b8d`, with its SSH hostname verified. At the time of inspection, it ran `vLLM 0.27.1` on two RTX PRO 6000 Blackwell Server Edition GPUs, each with 97887 MiB total memory. Each endpoint served BF16 Qwen/Qwen3.6-35B-A3B with TP=1. Ports 8000/8001 and PIDs 1595/1597 corresponded to GPUs 0/1. Both health requests returned 200. Complete argv records are retained in the live_runtime JSON.

The main settings were max_model_len=16384, max_num_seqs=64, max_num_batched_tokens=16384, GPU memory utilization=.85, enabled prefix caching, chunked prefill, enforce_eager, language_model_only, moe_backend=triton, disabled FlashInfer autotune, generation_config=vllm and reasoning_parser=qwen3. The two services used `/root/autodl-tmp/CAUSE-thesis-20260910/gpu0` and `gpu1`. No second runner was started.

## Version boundaries

The authoritative Phase56 source root is `E:/wt/cause-qwen-pns-adaptive-20260826`, with its journal under `artifacts/experiments/qwen_pns_phase56_20260826_v2_recovery_18plus3_v1`. The local 17 August bank with 56 completed questions, 6,910 requests and fixed M=2 is a different batch. The 520-request adaptive snapshot under D:/CAUSE is also not the final Phase56 run. The 9 September discussion of selecting the highest-quality chain proposed a new protocol. It did not change this batch's rule of choosing the shortest candidate after mandatory acceptance checks.

The latest historical source-host threads, 01a0319e-273f-7ac2-9336-fc77ed4a2f12 and 01a06a54-83f8-7681-b369-7f75e9be63df, were read, and the key numbers were rechecked against the available original files. The work involved reading, extraction and report generation in a new directory. It made no new inference calls and changed no historical database.

This section records parameters during execution. The final delivery note records the instance's eventual power state.
