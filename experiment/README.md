# Experiment and review materials

All Qwen generation requests in this experiment have finished, comprising 40 development requests, 1,200 follow-up requests on released data, 984 requests on new numerical instances and 56 same-model self-reviews, for a total of **2,280**. A further 2,280 tokenizer requests involved no generation. These counts exclude historical PNS/Judge calls and Codex-assisted analysis that was not separately metered. D41 was powered off but the instance was not released. The complete power-cycle bill was ¥28.89.

## Result entry points

- `main_analysis/` contains the originally specified full-denominator results for 300 questions, with 279 correct for PNS, 277 for FULL, 272 for HEURISTIC and 254 for ZERO. This cohort has historical baseline exposure and CPT reuse; the original question-level p-values are diagnostic only.
- `main_CPT_sensitivity.json` / `.md` retain all 300 questions and apply resampling and whole-group sign flips to 271 complete-CPT groups.
- `fresh_analysis/` covers 246 new SCM instances, with 224 correct for PNS, 208 for FULL, 208 for HEURISTIC and 187 for ZERO. It is restricted to four probability-query types using frontdoor and mediation structures with prespecified filtering.
- `joint_comparisons.json` analyses the two different distributions separately and applies Holm correction across six comparisons. For the fresh instances, adjusted p-values for PNS against FULL/HEURISTIC are 0.00998/0.02100.
- `self_review/` contains 29 parseable self-reported passes and 27 truncated responses with unknown outcomes. Neither self-reports nor quotation matching constitute independent semantic ground truth.
- `dev_analysis/` contains the four-condition development check on 10 questions. Its results were not used to adjust the method.

## Raw records

`CAUSE_Experiment_English_Release_20260912.tar.gz` contains 16,542,678 bytes and 2,357 tar members. It includes 40/1,200/984/56 complete raw responses, actual requests, states, token usage, runtime parameters and consistent SQLite snapshots. Extraction creates the `dev10`, `main300`, `fresh246` and `self_review56` directories. `local_archive_verification.json` records archive readability and response counts. No new model requests were used to reconstruct the original results.

`data/` contains public problem statements, scoring-only labels, the fixed 56 demonstrations and their deployment policy. Target gold labels, complete SCMs and source reasoning were excluded from model prompts. `fresh_source/` preserves all 257 proposals, 11 exclusions, new SCM parameters, the executed generation driver, independent calculators and official source code. Official RandomBuilder Uniform proposals underwent consistency filtering, so the resulting distribution is not the original balanced benchmark distribution. The two cohorts are not combined into 546 samples from one distribution.

`source_data/cladder_v1_source_pair.zip` preserves the original balanced and meta-models files used here. Development exclusions are stored separately in `development_question_ids.json`. The value 7,064 counts metadata records, not distinct CPTs.

## Recalculation and code scope

The statistical environment is recorded in `analysis_environment.json`. Extract the raw records into a new directory such as `raw/`, then run `scripts/analyze_paired.py --help` to inspect its parameters. Complete per-question scores, confidence intervals, CPT mappings and six-comparison results are supplied. Recalculating these files requires no model requests.

```text
python scripts/analyze_paired.py --targets data/fresh246/targets_scoring_only.jsonl --arm ZERO=raw/fresh246/ZERO.attempts.jsonl --arm FULL_COT=raw/fresh246/FULL_COT.attempts.jsonl --arm HEURISTIC_SHORT=raw/fresh246/HEURISTIC_SHORT.attempts.jsonl --arm PNS_COT=raw/fresh246/PNS_COT.attempts.jsonl --output reanalysis_fresh
```

`scripts/cpt_statistics/` provides the 300-question grouped sensitivity analysis and joint six-comparison correction. The original analysis and its numerical results are preserved. Scope notes added to output copies correct the insufficient assumption that different model_id values alone establish independent mechanisms.

`fresh_source/GENERATE_FRESH246_REPRODUCTION.md` records the executed generation command, dependencies and path mappings. For regeneration, point the driver's output root to a new working directory and retain the supplied frozen data. `reference_method_code/` is a captured historical-method reference implementation whose byte identity with earlier execution has not been established. Provider files with credential risks were excluded, so it is not a complete historical serving environment.

`cases/` and `audit/` preserve prespecified case selection, blinded reviews and raw responses. Human ground truth for complete natural-language paths, the population Judge false-acceptance rate and complete cross-model monetary amortisation remain unestablished. Matching answers, short traces and self-reported passes do not establish these quantities.
