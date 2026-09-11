# Fresh CLADDER SCM extension: 246 fixed new instances

This is a separately analyzed four-type extension generated with unmodified official CLADDER code, not a split of the original balanced dataset. No model predictions were consulted during construction.

- ATE 94 and ETT 82 use frontdoor graphs; NDE 20 and NIE 50 use mediation graphs.
- Each target has a different full CPT and a different query-relevant CPT signature. Exact signatures are excluded against all 7,064 historical meta-models, all eight feasibility-probe models and earlier selected new models.
- Proposal generation samples every CPT cell independently from Uniform(0,1) through the official RandomBuilder. The final evaluation distribution is that proposal distribution conditioned on the prewritten validity/exclusion criteria, not an unfiltered uniform sample. Both differ from the historical difficulty-builder distribution.
- Source commit: `3d2d1169b4b939a09048a6a75956c8972a93cc38`; official functions: `causalbenchmark.generator.generate_questions`, `RandomBuilder`, `create_query`.
- Fixed seed base 2,026,092,000; independent per-type streams offset by 100,000; attempt seed increments by one. Target-order seed is 2,026,092,099. All seeds/specs/parameters are saved.
- Evaluation qids are 1,100,000–1,100,245. The official generator function supplies `desc_id` and within-model question index, but no global question_id; `official_question_id` is explicitly null and both author indices are preserved.
- Polarity alternates within type before generation. There is no answer-balancing or Qwen-outcome selection.
- ATE/ETT reuse the `smoking_frontdoor` story. NDE/NIE cycle six official mediation stories. This tests new numerical SCM instances, not held-out graph families or new story templates.

257 candidate draws produced 246 selected instances and 11 exclusions. No duplicate CPT exclusions occurred. Ten exclusions involve disagreement between the source label and strict sign-based independent calculation, and ten involve public-percentage precision/label conflict or zero (overlapping categories).

The author's ATE/ETT implementation returns “no” for `abs(effect)<0.005`, regardless of the requested polarity. Thus these label disagreements are not necessarily arithmetic bugs in the author implementation: they reflect its near-zero decision rule. The prewritten label agreement rule excluded conflicting targets rather than silently relabeling them. All 246 retained instances have identical author, full-precision independent, rounded-public and full-SCM answer directions, and agree numerically with the full-precision author groundtruth to 1e-8.

Files:

- `targets_public.jsonl`: exactly the public fields expected by the existing evaluation runner; no gold/SCM/oracle.
- `targets_scoring_only.jsonl`: qid/group/type/gold sidecar, never include in model prompts.
- `selected_source_and_validation246.jsonl`: source row, full model, IDs, seed and independent validation for each selected target.
- `sampling_attempts.jsonl`: all 257 sampling attempts and reasons, including exclusions.
- `all_attempt_models.jsonl`: all generated CPTs, including excluded candidates.
- `generation_protocol.json`: rules written before generation.
- `manifest.json`: construction counts and versions.
- `local_independent_verification.json`: second independent recomputation after transfer to the local machine.

Historical source reasoning.step5 may contain display-formula mistakes; it is preserved only in the offline source file and is neither the label calculator nor part of target prompts. This extension must be reported separately from the historical baseline-exposed main300 evaluation.
