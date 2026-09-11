# Prespecified main300 complete-CPT cluster sensitivity analysis

Saved on 2026-09-10 (Asia/Shanghai), before reading final or intermediate main300 predictions, computing accuracy or comparing outcomes. The main task reported that model requests were still running. This subtask read only the frozen statistical script and the structure of the CPT-group mapping.

## Material Passport

- Mode: statistical validate / prespecified sensitivity implementation.
- Verification Status: PRESPECIFIED; results unknown.
- Scope: supplementary main300 sensitivity and six-comparison Holm helper; zero model calls.
- Frozen primary analysis: `work/evaluation/analyze_paired.py` remains unchanged.

## Data, estimand and comparisons

1. Inputs are limited to final four-condition scored CSV files explicitly supplied by the main task, or complete terminal attempts with the frozen target manifest. Intermediate predictions still being appended are neither discovered nor read automatically.
2. Grouping uses `work/evaluation/main300_CPT_groups.json`, defining groups by identical complete-CPT mechanisms and expecting 300 question_id values in 271 groups. The original primary denominator always retains all 300 questions. CPT repeats, historical overlap, format failures, API failures and missing responses never cause exclusions; failures remain incorrect under the frozen primary analysis.
3. Three directions are fixed, PNS_COT − FULL_COT, PNS_COT − HEURISTIC_SHORT and PNS_COT − ZERO. Each reports the original question-weighted mean difference, gain, loss, both-correct and both-wrong counts. Each question's difference is candidate correctness minus reference correctness.
4. This sensitivity analysis was added after CPT repeats were identified and while outcomes remained unknown. It preserves the original primary analysis and is not described as the initially preregistered primary test.

## Paired CPT-cluster bootstrap

- Sample 271 complete-CPT groups with replacement and equal probability from the 271 groups, retaining all paired questions within each selected group.
- Each statistic is the sum of paired correctness differences in sampled groups divided by the total number of sampled questions. This preserves the question-weighted estimand. Unequal group sizes make the resampled denominator variable, while the observed denominator remains fixed at 300.
- Use 20,000 samples and the 2.5% and 97.5% percentile limits with NumPy linear quantiles. These CIs have no simultaneous-coverage adjustment.
- CPT groups are assumed to be independent sampling units, with arbitrary dependence among questions within each group. Clustering does not remove historical demo/core/challenge overlap and therefore does not establish generalisation to new mechanisms.

## Whole-group sign-flip permutation

- Sum question-level differences within each CPT group to obtain group total D_g. The observed statistic is S = sum_g D_g; dividing by the fixed 300 gives a mean difference with the same ordering.
- Independently generate equiprobable +1/−1 signs for each group and compute S_b = sum_g sign_g × D_g. Candidate and reference labels are exchanged jointly within each group.
- The two-sided Monte Carlo p = (1 + count(|S_b| >= |S|)) / (200,000 + 1). Integer totals avoid floating-point boundary errors. Groups with zero totals remain in the group count and sampling.
- The test assumes that condition labels can be jointly exchanged within each CPT group under the null, equivalently sign symmetry of group differences, with independence across groups. A zero mean difference alone is insufficient. Fixed prompt conditions were not randomly assigned, so this is a model-comparison sensitivity test under that exchangeability assumption.
- The program always uses 200,000 random sign flips and an add-one Monte Carlo p-value. Even with small toy samples, its output is not called an exact permutation p-value. Tests separately enumerate toy sign distributions to check the implementation.
- The main300 question-level iid McNemar p-value is not treated as a strict test under dependence induced by complete CPTs.

## Randomness and multiple comparisons

- The root seed is fixed at 20260910, using NumPy default_rng / PCG64. In the fixed comparison order above, SeedSequence(20260910).spawn(6) supplies separate bootstrap and permutation streams for each comparison, with spawn_key recorded.
- Apply Holm step-down correction to the three original main300 cluster-permutation p-values. Report all raw and adjusted values without selecting comparisons by their results.
- A separate helper accepts the three main300 cluster-permutation p-values and three fresh246 exact McNemar p-values, applying Holm within the same prespecified six-comparison family. Each effect retains its denominator, CI, test type and distribution identity. The two cohorts are never pooled into 546 questions for a single accuracy or pooled test.
- fresh246 exact McNemar values are supplied by its analysis task. This script only checks and reads completed results, with zero additional model calls.

## Validation and interpretation

- Inputs must contain all four conditions and exactly the same 300 unique question_id values. The scored CSV correct field must be 0/1, and the CPT mapping must cover all and only those questions. Integrity failures produce errors rather than silent exclusions.
- The attempts-path mode reuses the frozen primary script's strict JSON-answer scoring function. Missing terminal responses count as incorrect under the primary rule, but the operator must explicitly confirm that inputs are final.
- While outcomes remain unknown, hand-checkable synthetic paired examples validate gain/loss counts, group aggregation, add-one Monte Carlo p-values, two-sided tails and Holm correction. Tests do not read main predictions.
- Final outputs are `outputs/experiment/main_CPT_sensitivity.json` and `.md`. They record input and code SHA-256 values, group counts, random streams, replicate counts, software versions and assumptions. Report observed evidence only. Non-significance is not equivalence, non-inferiority or proof that the method is ineffective.

Method reference is the official SciPy permutation_test documentation on paired-sample permutations and the add-one convention for randomised p-values. The final implementation will check the current official documentation and include its link.
