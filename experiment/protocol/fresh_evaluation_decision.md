# Fresh SCM evaluation decision

Decision date: 2026-09-10, before reading any accuracy result from the running 300-target follow-up. That run's interim monitoring covers technical completion only. User has authorized additional Qwen calls and delegated remaining decisions while asleep.

## Purpose and scope

Close the historical-exposure limitation with genuinely new parameterized causal instances, using the official CLADDER generator code at commit `3d2d1169b4b939a09048a6a75956c8972a93cc38`. An eight-instance offline pilot has already passed independent label and numerical checks and is excluded from the fresh evaluation.

Freeze **246 new independent probability SCM instances**: ATE94, ETT82, NDE20, NIE50. Each contributes one target. ATE/ETT use the author's frontdoor family and its existing smoking_frontdoor story. NDE/NIE use mediation and existing compatible stories. The sampler draws full CPT parameters uniformly on (0,1). This is an official-generator fresh-instance extension under a specified restricted distribution, **not** the released balanced CLADDER distribution or a new official benchmark split.

No deterministic-counterfactual extension is claimed: changing irrelevant root probabilities or merely renaming an old Boolean mechanism would not establish a new query-relevant mechanism. The original 300-target follow-up continues to cover all five families including54 deterministic questions.

Before inference, exclude any duplicate full or query-relevant parameter configuration from historical metadata and the eight pilot SCMs. Reject and log generated items whose author label disagrees with independent calculations from the public rounded values or full CPT. Do not select on any Qwen outcome. Record every sampling attempt and the exclusion denominator.

## Fixed comparison

Use the unchanged56-demo bank (52 accepted compressed trajectories +4 exact-parent fallbacks), ordinary length-matched compression, same two distinct same-class demos and order across FULL/HEURISTIC/PNS, and ZERO reference. Keep generation model, temperature1,top_p.95,top_k20,seed mapping,output budget shared across conditions,and strict lowercaseJSON scoring identical to the existing protocol.

Exactly246x4=984 additional generation slots, one POST per target/condition, no automatic resend. Run in a separate output directory after the first300 complete, with24workers/GPU. The two cohorts are never pooled as though they had the same target distribution. The fresh cohort's results do not change the old cohort's selection or analysis.

## Analysis

Within each cohort report the same three paired contrasts, confidence intervals and raw McNemar p-values. Retain the already specified within-cohort Holm correction and additionally report Holm across all six contrasts, so the added cohort cannot be used to select an uncorrected favourable result. No noninferiority margin, no accuracy-driven expansion or repeated seed search.

The paper must distinguish prior-exposed follow-up evidence from newly sampled mechanism evidence, and report the fresh cohort's restricted graph/story/parameter distribution. If dataset generation fails its offline checks, report that failure without substituting an uncertified set.
