# Shared-first-pass report

Summary of the preserved `GPT-5.5 Shared First-Pass Rowwise Verifier Report.md`. The underlying [paired comparisons](primary_paired_comparisons.csv) and [resource metrics](resource_metrics.json) are unchanged.

## Recorded decision

The selected decision retained C as the default, merged alias-normalised observability and disabled answer intervention. No new skill was generated. The development stage rejected G, R and GR; the selected formal candidate is byte-identical C0.

Development contained 556 rows, with C0 accuracy 90.4676%. R/GR had three regressions. These exploratory results selected the candidate and do not establish generalisation.

## Clean holdout

The clean comparison contains 974 paired questions. Candidate-minus-C0 accuracy is exactly zero, McNemar p is 1 and its paired interval is [0, 0], because the candidate preserves C0. Relative to legacy, the recorded difference is approximately -0.103 percentage points with a 95% interval [-1.335, 1.129]. The source reports no superiority to C0 and reports that the legacy non-inferiority and efficiency requirements passed.

The selected candidate has zero corrections and zero regressions relative to C0. The result therefore does not show that an answer-revision intervention improved answers.

## Stress, resources and interpretation

The 180-item structural-stress pack is diagnostic and remains separate from the primary estimate. Its candidate and legacy totals are 158 and 163 correct. Family-specific results are supplied in the unchanged [family metrics](family_metrics.csv).

The source reports candidate/legacy ratios of 0.1279047943 for total tokens and 0.0280033604 for model calls, with two public candidate tools. Wall-clock results are descriptive because the call graphs differ. The detailed input/output and call identities are recoverable from the execution manifests and selected accounting fields in the two pack folders.

The raw declared-query string mismatch remains recorded, while alias-normalised and structural comparisons determine whether a mismatch is actionable. Unsupported and insufficient-evidence solver results did not override answers. All post-processing conditions share one C record, allowing their effects to be compared without resampling the first answer. This does not expose hidden GPT-5.5 reasoning or establish a chain-of-thought compression result. The legacy tool interface and call graph also differ from the shared candidate.

The source's final audit flags report success for its framework check, payload leakage scan, unchanged source hashes and equal-execution contract. These are historical recorded flags. The new offline script in this supplement separately verifies the distributed numerical evidence without executing a model.
