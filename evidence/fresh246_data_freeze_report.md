# Frozen set of 246 new CLADDER causal instances

Status is READY. Data generation and independent local recalculation are complete. This does not mean that model evaluation is complete. This subtask made no model calls and did not inspect intermediate predictions or results from the original main300 run.

| Item | Result |
|---|---:|
| Fixed targets / distinct SCMs | 246 / 246 |
| ATE / ETT / NDE / NIE | 94 / 82 / 20 / 50 |
| Sampling attempts / retained / excluded | 257 / 246 / 11 |
| yes / no | 116 / 130 |
| Complete-CPT duplicates against 7,064 historical metadata records and eight probes | 0 |
| Target-relevant CPT duplicates against historical records and probes | 0 |
| Complete or relevant CPT duplicates within the 246 new instances | 0 |
| Agreement among original labels, independent full-precision labels, public-percentage labels and complete-SCM labels | 246 / 246 |
| Agreement between independent full-precision effects and original numerical values, tolerance 1e-8 | 246 / 246 |
| Maximum numerical discrepancy in local recalculation | 8.88×10⁻¹⁶ |
| Generation and filtering time alone | 20.671 seconds |

The unmodified official [causalNLP/cladder](https://github.com/causalNLP/cladder/tree/3d2d1169b4b939a09048a6a75956c8972a93cc38) source was used at commit `3d2d1169b4b939a09048a6a75956c8972a93cc38`, through `generate_questions`, `RandomBuilder` and `create_query`. The authors' code generated the natural-language questions, SCMs and original gold labels. The independent script performed only recalculation and predefined validity screening. It did not use the old reasoning.step5 as an oracle.

Candidate generation sampled each complete-CPT parameter independently from Uniform(0,1). **The final 246-question distribution is that proposal distribution conditional on the predefined validity filters.** It is neither an unfiltered uniform sample nor an independent sample from the original balanced/difficulty distribution. ATE/ETT were restricted to frontdoor graphs and NDE/NIE to mediation graphs. The original story templates were retained, so the evaluation concerns new target-relevant numerical instances rather than generalisation to new stories or graph families.

The filters were recorded before generation. They required successful generation, a yes/no answer, no complete or target-relevant CPT duplication, agreement with independent full-precision values and labels, a consistent nonzero effect under public-percentage precision, and no duplicate public question. Data were not selected using Qwen outputs, observed effects of the method or significance.

Of the 11 exclusions, ten involved disagreement between the authors' label and the strict effect-direction rule, and ten involved a conflicting label or zero effect under public-percentage precision. These categories overlap and must not be added to obtain 20 exclusions. **For ATE/ETT, the authors assign no whenever `abs(effect)<0.005`, so the first category is not a numerical calculation error in their code.** This task did not change the authors' labels. It excluded conflicting candidates under the fixed consistency rule. All attempts, seeds, complete CPTs and exclusion reasons were retained.

The generation base seed was 2,026,092,000. The four query types used offsets of 0, 100,000, 200,000 and 300,000, with the seed increasing by attempt within each type. The ordering seed was 2,026,092,099. Each target corresponds to one new SCM. qid values range from 1,100,000 to 1,100,245, and group_id uses the form `fresh:seed:...`. The authors' function does not produce a global question_id, so `official_question_id` remains null. The original desc_id, model index and within-model question index are stored separately, without inventing official IDs.

Execution used the source host's existing Python 3.9.16. Additional dependencies were installed in an isolated target directory, leaving the original interpreter environment unchanged. The added installed files total approximately 41.14 MB. pomegranate 0.14.8 used an existing Windows CPython 3.9 wheel, so no old Python interpreter was installed and no large extension was compiled.

Inputs and complete records are under this task's `work/fresh_cladder_feasibility/freeze246/`.

- `targets_public.jsonl` contains 246 rows with only the public fields required by the existing evaluation runner. Question text matches the authors' output exactly.
- `targets_scoring_only.jsonl` contains 246 scoring-side rows, which must remain outside prompts.
- `selected_source_and_validation246.jsonl` contains complete original questions, models, seeds, mappings and independent recalculation values.
- `sampling_attempts.jsonl` and `all_attempt_models.jsonl` retain all 257 attempts and their models, including exclusions.
- `generation_protocol.json` records the rules fixed before generation.
- `manifest.json` and `local_independent_verification.json` record counts, versions and the second local recalculation.

The historical total of 7,064 counts metadata records. Canonical graph+complete-CPT signatures identify only 4,256 distinct numerical SCMs, not 7,064 independent SCMs. The complete executed generation driver is retained as `work/fresh_cladder_feasibility/generate_fresh246_executed.py`. The original command and dependencies are documented in `GENERATE_FRESH246_REPRODUCTION.md` in the same directory.

The planned next stage comprises 246×4=984 target-model calls. This fresh evaluation must be analysed separately from the original baseline-exposed main300 cohort. This report confirms only the frozen new data and offline validity checks. It makes no advance claim about the downstream effect of compression.
