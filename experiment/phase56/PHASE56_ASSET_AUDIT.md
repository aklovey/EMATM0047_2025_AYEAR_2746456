# Phase56 asset closure and execution checks (2026-09-10)

Existing Phase56 was closed as **52/56 accepted and 4/56 without an accepted trace**. The original database retains 52 completed / 4 pending items; the new report preserves that history. Additional Phase56 model calls total 0, and the original max-7 recovery plan was not executed.

## Directly usable local assets

- `phase56_accepted52_demo_pool.jsonl` contains 52 complete full_cot / pns_cot pairs, their Qwen token counts, qid, query_type, gold_answer, original problem messages, selected request keys and audit fields.
- `phase56_original_inputs56.jsonl` contains all original 56 complete inputs and segmentations for whole-group leakage exclusions.
- `phase56_closure_all56.jsonl` contains 56 terminal records with complete historical artifacts. Failed rows have pns_cot=null; parent traces are not presented as successful compressions.
- `phase56_selected_lineage52.jsonl` contains frozen_prefix, reasoning_suffix, complete_chain, final_content and prompt_key for the 52 selected lineages. All 52/52 satisfy prefix+suffix=chain=selected artifact character-for-character. The original q30359-s001-delete-r2 entry was posting; its output was reconstructed from the existing g1 succeeded sidecar with its source recorded.
- `phase56_pending_candidate_rows.jsonl` / `phase56_pending_judge_rows.jsonl` preserve full original candidates and Judge reasons for the four failed questions.
- `phase56_source_export.json` is a 39 MB read-only extraction containing all items/results, relevant candidates, Judge records and contracts. It does not replace the complete original HTTP database. The original journal remains on the host.
- `phase56_closure_summary.json` / `phase56_failed4.jsonl` provide dissertation statistics and failure categories.
- `phase56_ledger_accounting.json` gives separate counts and token usage for each original ledger.
- `live_runtime_20260910.json` records the observed argv, GPUs, model lists and health of both D41 services during this task.

## Facts supported for the dissertation

Each of the 52 selected traces was rechecked for optimized=true, fallback=false, a valid deterministic answer, Judge acceptance and strict shortening relative to its parent. Complete-chain tokens total **116,826 → 75,074**, a reduction of **41,752 (35.74%)**. Acceptance is **52/56 (92.86%)**. The compression rate concerns the successful subset and is not a downstream accuracy result.

Final selection contains **30 DELETE and 22 KEEP traces**. The original generation journal contains **7,947 KEEP and 6,561 DELETE entries**, with no REPLACE or replacement_generate entries. REPLACE is therefore an implementation branch without evidence of activation in this run. The run cannot be described as a comparison of three executed interventions.

The final Judges for the 52 selected traces comprise **51 GPT-5.5 and 1 DeepSeek V4 Pro decisions**. The batch did not use one Judge throughout. The 113 GPT recovery reviews also do not represent all Judge calls for this batch.

| qid | Type | Original requests | Reason for the terminal outcome |
|---:|---|---:|---|
| 19407 | ett | 207 | ETT was represented as population ATE or an ordinary interventional effect. Treated conditioning and unobserved confounding were not handled correctly. Historical Judges repeatedly rejected the candidates. |
| 24494 | ett | 175 | ETT was treated as an observational conditional difference or population effect, omitting confounding and conditioning on the treated group. Historical Judges repeatedly rejected the candidates. |
| 29833 | det-counterfactual | 198 | Both candidates reaching final materialisation were shorter and answer-matched, but incorrectly kept muvy fixed at false after intervention and confused AND/OR gates. Judges rejected both. |
| 30257 | det-counterfactual | 145 | Negative causal relations were misread, counterfactual updates relied on unsupported assumptions, and some traces contained internal contradictions. Historical Judges repeatedly rejected the candidates. |

These reasons come from historical Judges and are traceable error diagnoses, not new human ground truth. Shorter candidates marked answer-correct can still fail semantically, and all four questions contained such candidates. Rejection reasons for q29833's two materialisation requests are retained. Their cause was incorrect counterfactual structural updating, not a missing file or an absent Judge call.

## Budgets and call-count definitions

The frozen policy uses 3→5 valid matched rounds, with at most 5 raw attempts per KEEP/DELETE/REPLACE lineage and no votes from invalid trials. One replacement generation is conditionally triggered. For 1,691 safe steps, the conservative generation ceiling is **1,691 × (5+5+1+5) = 27,056**, excluding Judge, tokenize, canary and additional recovery dispatches. This task stopped further expansion, with an additional budget of **0**.

The original Qwen journal contains **14,508 rows**, comprising 14,338 completed, 42 scientific_invalid and 128 posting. All 128 posting rows have succeeded dispatches in the earlier g1 sidecar; their original rows are preserved. Counting physical dispatch records gives **14,508+128=14,636**. g1 dispatches are not new scientific samples. The original 56-question recovery directory is a copied view and must not be added again to the original journal. Recorded raw slots 6/7 total 0.

Known Judge provider_call_count values are 2,747 for DeepSeek, 113 for the isolated GPT default-effort run, 113 for GPT xhigh strict recovery and 11,718 for the latest future ledger. Known calls total **14,691**. A further 46 historical DeepSeek and 24 future reserved records have unresolved outcomes and cannot be assigned zero cost. The original future ledger's 11,703 calls are already included in the recovery ledger's 11,718 and must not be counted twice. Separate canaries are outside this total, so a dissertation cost statement should identify these as recorded counts or a lower bound.

Stored original Qwen usage totals 12,491,141 input, 28,901,182 output and 41,392,323 total tokens. It excludes the 128 originally unresolved calls, g1 recovery usage and separate canaries, and is therefore incomplete. Per-Judge usage is in the JSON; copied future ledgers must not be summed together.

## Services observed during this task

D41 instance `fxqnqh00m3-1d1e6b8d` had a verified SSH hostname. The observed runtime was `vLLM 0.27.1` on 2× RTX PRO 6000 Blackwell Server Edition GPUs, each with 97887 MiB. Both endpoints served BF16 Qwen/Qwen3.6-35B-A3B with TP=1. Ports 8000/8001 and PIDs 1595/1597 corresponded to GPU0/1, and both health endpoints returned 200. Complete argv records are in live_runtime JSON.

Key settings were max_model_len=16384, max_num_seqs=64, max_num_batched_tokens=16384, GPU memory utilisation=.85, enabled prefix caching, chunked prefill, enforce_eager, language_model_only, moe_backend=triton, disabled FlashInfer autotune, generation_config=vllm and reasoning_parser=qwen3. The services ran under `/root/autodl-tmp/CAUSE-thesis-20260910/gpu0` and `gpu1`. No second runner was started.

The reusable SSH host was `connect.westd.seetacloud.com:52108`, user root. The local key was `C:/Users/aklovey/.ssh/main_laptop_ed25519`, with known_hosts at `C:/Users/aklovey/Documents/Codex/2026-08-17/qwen36-fewshot-icl-pilot/work/ssh/known_hosts_autodl`. Old port 14144 timed out, and old port 30656 had a changed host key; checks were not bypassed. The historical host CLIProxy credential path was `C:/Users/Wyatt/AppData/Local/CLIProxyAPI/client-token.txt`. No secrets were read or printed during this task.

## Version boundaries

The authoritative Phase56 host path is `E:/wt/cause-qwen-pns-adaptive-20260826`, with the journal under `artifacts/experiments/qwen_pns_phase56_20260826_v2_recovery_18plus3_v1`. The local 8/17 fixed-M=2 pool with 56 completions and 6,910 requests is a different batch. The 520-request adaptive snapshot under D:/CAUSE is also not final Phase56. The 9/9 discussion of selecting traces by highest quality score concerned a new protocol and did not alter this batch's shortest-after-hard-checks selection rule.

The latest historical host threads 01a0319e-273f-7ac2-9336-fc77ed4a2f12 and 01a06a54-83f8-7681-b369-7f75e9be63df were read, and key numerical values were checked against current raw files. Operations were limited to reading, extraction and report generation in new directories, with no new inference calls or changes to historical databases.
