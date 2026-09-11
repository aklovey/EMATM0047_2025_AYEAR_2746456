# main300 complete-CPT cluster sensitivity analysis

## Material Passport

- Verification Status: ANALYZED. The implementation passed tests on synthetic examples; this table reports supplementary analysis of the final inputs.
- Scope: The original primary analysis and all frozen targets are retained; zero additional model calls.

The observed denominator includes all 300 questions. The inferential resampling units are 271 complete-CPT groups. The mean difference remains question-weighted, and questions with repeated mechanisms are retained.

| Comparison | Mean difference | CPT cluster bootstrap 95% CI | gain/loss | cluster permutation p (MC) | Three-comparison Holm p |
|---|---:|---:|---:|---:|---:|
| PNS_COT:FULL_COT | +0.67% | [-2.02%, +3.49%] | 10/8 | 0.814571 | 0.814571 |
| PNS_COT:HEURISTIC_SHORT | +2.33% | [-0.33%, +5.05%] | 12/5 | 0.142719 | 0.285439 |
| PNS_COT:ZERO | +8.33% | [+5.02%, +11.84%] | 28/3 | 4.99998e-06 | 1.49999e-05 |

There are 20,000 bootstrap samples and 200,000 whole-group sign flips, with root seed = 20260910. The two-sided p = (1 + count(|null| ≥ |observed|)) / (B + 1) is a Monte Carlo result, not an exhaustive exact test.

The test assumes that the two condition labels can be jointly exchanged within each CPT group under the null, with different groups treated as independent units. Prompt conditions were not randomly assigned, and a zero mean difference alone does not establish exchangeability. Percentile CIs are not simultaneous intervals and need not yield the same conclusions as the permutation test.

Original question-level McNemar p-values are retained only in the JSON field diagnostic_mcnemar_p. With repeated CPTs, they are not treated as tests on strictly independent questions. Clustering does not remove historical demo/core/challenge overlap or establish generalisation to new mechanisms.

This supplementary specification was saved after the grouping audit identified repeats and before outcomes were read. The original main300 analysis is unchanged. fresh246 is reported separately, with six-comparison Holm correction in joint_comparisons.json; the cohorts are never merged into 546 questions.

The method follows the [official SciPy permutation_test documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html), checking paired label exchanges, sign flips and the randomised add-one p-value. This analysis explicitly uses a two-sided tail based on the absolute statistic.

All 11/11 categories of statistical misinterpretation were considered within this analysis's scope, as recorded in the JSON fallacy_scope_review. Non-significance does not establish equivalence or non-inferiority.
