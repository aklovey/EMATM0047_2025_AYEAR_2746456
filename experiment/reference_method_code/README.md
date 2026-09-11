# PNS v2 method-code reference snapshot

**reference snapshot captured now, historical execution identity not established**

This lightweight method reference was read on 2026-09-10 (Asia/Shanghai) from the current host worktree `E:\wt\cause-qwen-pns-adaptive-20260826`, using an explicit file list. No source code was executed or modified, and no model calls were made. It is neither a runtime package proven byte-identical to historical Phase56 execution nor a complete repository guaranteed to run independently.

`SOURCE_INDEX.json` records each file's original path, size, modification time, capture time and screening status. `current_HEAD_reference_only` identifies Git HEAD at capture time and **does not establish the historical execution version**. No `.py` files were directly present in the historical v2 journal directory `artifacts/experiments/qwen_pns_phase56_20260826_v2_recovery_18plus3_v1`. This capture did not comprehensively trace archived file identity across D41 or the complete historical tree. Older local `runtime_v1` files also exist but were not mixed into this v2 reference snapshot.

## Included implementation scope

| File | Main purpose |
|---|---|
| `src/qwen_pns_adaptive.py` | Adaptive KEEP/DELETE decisions, candidate paths, eligibility and selection, and PNS-CoT asset export |
| `src/qwen_pns_batch56_adapter.py` | 56-question execution adapter, original Qwen segmentation and prefix logic, requests and recovery, and dataset contract v2 |
| `src/qwen_pns_judge_gate.py` | Judge binding, evidence checks and frozen-contract checks |
| `src/experiments/cladder_pns_mvp/judge.py` | Semantic Judge call wrapper and judgement structure |
| `src/experiments/cladder_pns_mvp/judge_transport.py` | Judge transport structure |
| `src/pns_judge_ledger.py` | Judge ledger implementation, excluding databases |
| `src/pns_dataset_preparation.py` | Dataset preparation and segmentation reference structure |
| `src/qwen_pns_phase_gate.py` | Phase-contract logic |
| `src/qwen_pns_request_recovery.py` | Request-recovery logic |
| `src/qwen_pns_candidate_materialization_recovery.py` | Recovery of existing candidate material |
| `src/qwen_pns_max7_recovery.py` | Reference max7 recovery variant |
| `scripts/run_qwen_pns_adaptive.py` | Reference adaptive-execution entry point |
| `scripts/recover_qwen_pns_existing_candidates.py` | Reference existing-candidate recovery entry point |
| `configs/experiments/qwen_pns_phase56_20260826_v2.yaml` | v2 parameters and source-preserving segmentation contract |
| `configs/experiments/qwen_pns_phase56_20260826_v2_cli_proxy_resume.yaml` | Reference historical recovery-transport configuration structure |

The 15 included code/configuration files total 504,542 bytes. Models, caches, datasets, SQLite databases, raw requests and responses, `.env` files and authentication files are excluded. Core-algorithm imports may refer to omitted modules or external runtime bundles. This is a deliberately limited documentation attachment, not a complete executable dependency closure.

## Credential screening

After reading files on the source host, screening checked common key, private-key and static Bearer patterns, Python AST literal credential assignments and dictionaries, and YAML credential key–value pairs. Only files passing these checks were transferred locally. Key-pattern screening was repeated before local writing. Matched literal values were neither printed nor transferred.

`src/providers/deepseek_client.py` matched the literal-credential-dictionary check, so the entire file was excluded. Only its path and exclusion reason are retained. Conservative matches are possible, so the finding does not establish that a detected value was a valid credential. Its original location remains a source pointer for authorised private inspection. Included files retain environment-variable names, dynamic authentication construction and parameter structures, but no plaintext credential values detected by this scan.

This practical scan has an explicit scope; it is not a formal proof against arbitrarily encoded secrets. The attachment supports method review. The presence of a code branch does not establish that the branch executed in the historical runs reported by the dissertation.

## Relationship to dissertation evidence

Historical completion counts, request costs, selected prefixes and suffixes, and semantic-component findings rely on frozen artifacts, per-question results and ledger exports actually read for this task. This snapshot helps locate algorithm and configuration structure. Its limits concerning historical execution identity should remain explicit in the electronic supplement.
