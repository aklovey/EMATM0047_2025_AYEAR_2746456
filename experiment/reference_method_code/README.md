# PNS v2 method-code reference snapshot

This snapshot was captured on 10 September 2026 for inspection of the Phase56 implementation. `SOURCE_INDEX.json` records each file's origin, size and capture metadata. The capture-time Git revision does not identify the version executed in the historical experiments.

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

The 15 code and configuration files total 504,542 bytes. Some provider and runtime dependencies are absent; the snapshot supports code inspection rather than standalone execution. Excluded modules are listed in `SOURCE_INDEX.json`.

Historical completion counts, usage, selected continuations and semantic findings are supported by the saved experiment artifacts and ledger exports. The presence of a branch in this source snapshot does not establish that it ran in those experiments.
