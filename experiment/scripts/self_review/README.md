# Qwen same-model self-review of 56 candidates

Local offline preparation is complete. No tokenizer connection or real model request has yet been made. The main task may launch this workflow after the four-condition evaluation finishes.

The set fixes 52 selected short traces and the shortest valid, answer-correct original candidate from each of the 4 unselected questions. Selection for those four follows the existing `prepare_blind_audit.py` ordering `(chain_token_count, request_key)` exactly. All 56 are frozen before shuffling with seed20260910 and assignment to SR001–SR056. Final answers for accepted traces come from the original selected requests, including existing g1 recovery, rather than being synthesised from gold labels.

Each candidate receives only 1 generation POST, at most 56 total. Settings are temperature=0, presence/frequency penalty=0, max_tokens at most 4096 and thinking enabled. The final JSON judges query, causal_rules, world_update, arithmetic and conclusion, each with pass/fail/unknown and a short quotation, followed by overall. Model requests contain only the common rubric, public original problem messages, complete candidate reasoning and original final_content. qid, source status, earlier Judge decisions, gold labels, oracle and structured source_meta are excluded from the model body.

## Files

- `candidate_inputs56.jsonl` contains the 56 frozen blinded inputs, with metadata separated from review_input.
- `blind56_sidecar.json` locally maps blind_audit_id to qid, source and request_key.
- `prepare_self_review.py` runs freeze entirely offline. prepare calls only the existing vLLM `/tokenize` endpoint, then creates a run_eval-compatible manifest using exact prompt-token counts.
- `run_eval.py` is an isolated copy of the existing runner with arm SELF_REVIEW. Its only change preserves complete HTTP error-response text; the main evaluation runner is unchanged.
- `parse_self_review.py` separately stores model reports, component judgements, quotation checks, usage, latency and unknown/truncated outcomes.
- `review_schema.json` and `review_system.txt` contain the common review rules for inspection.
- `offline_verification.json` records network-free mock results. After 6 mock dispatches, a repeat run added 0 calls. Truncation, unknown outcomes, HTTP errors, parsing failures and reserved_unknown states were not resent. The four-question selection matched the existing blinded audit.

`requests56.jsonl` has not yet been generated because the real tokenizer has not been called. Mock token counts cannot be used as actual budgets. Preparation adds 1 generation-free `/tokenize` call per item, with at most 56 tokenizer requests counted separately from 56 generation requests.

## Commands for the main task

Extract the package into D41's `/root/autodl-tmp/CAUSE-thesis-20260910/self_review`. The commands below use the existing Python environment. No libraries need to be installed because the runner and parser use the standard library.

```bash
/root/autodl-tmp/cladder_memory_probe_3q_qwen36_20260812/env/vllm/bin/python /root/autodl-tmp/CAUSE-thesis-20260910/self_review/prepare_self_review.py prepare --candidates /root/autodl-tmp/CAUSE-thesis-20260910/self_review/candidate_inputs56.jsonl --output /root/autodl-tmp/CAUSE-thesis-20260910/self_review/requests56.jsonl --tokenize-endpoint http://127.0.0.1:8000/tokenize
```

The budget is `min(4096, 16384 - exact_prompt_tokens - 128)`. Prompts that do not fit receive context_budget_error, without compressing the problem statement or applying an implicit repair.

```bash
/root/autodl-tmp/cladder_memory_probe_3q_qwen36_20260812/env/vllm/bin/python /root/autodl-tmp/CAUSE-thesis-20260910/self_review/run_eval.py run --manifest /root/autodl-tmp/CAUSE-thesis-20260910/self_review/requests56.jsonl --run-dir /root/autodl-tmp/CAUSE-thesis-20260910/self_review/run56 --endpoints http://127.0.0.1:8000/v1/chat/completions http://127.0.0.1:8001/v1/chat/completions --concurrency-per-endpoint 8 --timeout-seconds 1800 --progress-every 4
```

```bash
/root/autodl-tmp/cladder_memory_probe_3q_qwen36_20260812/env/vllm/bin/python /root/autodl-tmp/CAUSE-thesis-20260910/self_review/parse_self_review.py --run-dir /root/autodl-tmp/CAUSE-thesis-20260910/self_review/run56 --candidates /root/autodl-tmp/CAUSE-thesis-20260910/self_review/candidate_inputs56.jsonl --output-dir /root/autodl-tmp/CAUSE-thesis-20260910/self_review/analysis56
```

Outputs are `analysis56/self_review_records56.jsonl` and `self_review_summary.json`. Original requests are in SQLite `attempts.request_json`, and raw responses are under `run56/raw_responses`. Every `finish_reason=length` is labelled `review_truncated`. Unknown outcomes, parsing failures, HTTP errors and inconsistent overall judgements are reported separately, never resent and never counted as passes. Repeating the same manifest does not resend existing reservations.

This is a diagnostic self-review by the generation model over its own output distribution and may repeat its original errors. It is **not independent human review or external ground truth**. Results cannot directly be interpreted as a semantic-error rate and do not alter frozen primary evaluation data, demonstration selection or policy. The 52/4 source grouping supports post hoc diagnostic summaries only.
