# Full-CPT and conditional-mechanism overlap in main300

This audit read the frozen questions and CLADDER model parameters. It did not inspect predictions, call a model, or delete or replace targets. The original main analysis remains unchanged. The report provides the data-quality record and grouping information for a bootstrap sensitivity analysis.

## Main findings

The 7,064 records in the original meta-models file correspond to 4,256 canonical full-CPT signatures. Different model_id values therefore do not guarantee different numerical SCMs.

| Check | Targets covered | Distinct signature groups | Repeated groups | Questions in repeated groups | Questions beyond one per group |
|---|---:|---:|---:|---:|---:|
| Complete graph+CPT | 300 | 271 | 16 | 45 | 29 |
| Relevant CPTs under the fresh-cohort rule, covering only frontdoor and mediation | 76 | 71 | 3 | 8 | 5 |
| Extended conditional-mechanism core, exploratory | 300 | 268 | 15 | 47 | 32 |

## Intersections between main300 and existing sources

In the table below, the target count is the number of matching main300 questions. The group count is the number of signatures shared by the two sources. These counts describe different quantities.

| Source | Complete CPTs, targets / groups | Fresh-cohort relevant CPTs, targets / groups | Extended conditional-mechanism core, targets / groups |
|---|---:|---:|---:|
| demo56 | 23 / 14 | 4 / 2 | 31 / 14 |
| core256 | 54 / 27 | 9 / 4 | 54 / 24 |
| challenge100 | 30 / 16 | 6 / 3 | 32 / 15 |
| Union of all three | 59 / 32 | 10 / 5 | 59 / 29 |

main300 has no qid or model_id intersection with these three sources. This does not imply an absence of overlap in complete numerical CPTs. A shared graph alone was not counted as an overlap. The probability tables had to match exactly.

By query type, all 23 targets with complete-CPT overlap against demo56 are deterministic counterfactuals. All 54 targets overlapping core256 are also deterministic counterfactuals. The 30 targets overlapping challenge100 comprise 25 deterministic counterfactuals, four ATE questions and one NDE question. The union of 59 targets contains all 54 deterministic counterfactual questions, four ATE questions and one NDE question.

## Signature definitions and interpretation

A complete signature contains graph_id and every CPT. Single-element lists for root variables are reduced to numerical values, all probabilities are represented as floats, and JSON keys are sorted. Conditional-parent order and array axes are retained. The procedure applies no rounding or tolerance matching and does not distinguish numerically identical models by story ID. This rule is numerically equivalent to the full key used in the fresh-cohort check and gives the same total of 4,256 groups.

The predefined relevant-signature rule for the fresh cohort covers only two graphs. For frontdoor, it uses P(V3|X) and P(Y|V1,V3). For mediation, it uses P(V2|X) and P(Y|X,V2). The remaining main300 graph types are therefore outside that existing rule. For an additional descriptive check, this report defines an extended conditional-mechanism core, which retains every non-root conditional CPT except the mechanism for treatment X. It is identical to the fresh-cohort rule on frontdoor and mediation graphs. On other graphs, it is an explicitly exploratory extension.

**Overlap in some relevant CPTs does not establish that the complete SCMs are identical or that target answers repeat.** The omitted root distributions and treatment-assignment mechanisms may affect the estimand. Only a complete-CPT signature match supports identity of the complete numerical SCM in the canonical variables. Even then, story semantics, query_type, evidence or intervention direction may differ.

Rechecking fresh246 with the same full canonicalisation and predefined relevant signatures still gives 246 complete groups and 246 relevant groups. Both have zero overlap with all 7,064 historical metadata records, which represent 4,256 canonical full-CPT signatures. This provides more direct evidence of numerical separation for the fresh-instance extension.

## Use in the statistical sensitivity analysis

`work/evaluation/main300_CPT_groups.json` maps each qid to a complete-CPT group ID and includes all 300 questions. Group IDs are determined from sorted complete signatures, without using accuracy or predictions. These numerical SCM groups can support a paired bootstrap sensitivity analysis alongside the original main analysis. They do not justify removing overlapping questions based on results, selecting replacement targets or rewriting the original main analysis.

`main300_CPT_overlap_audit.json` contains the complete repeated groups, intersecting qids, source qids, group mappings and signature definitions, which allow individual overlaps to be checked.
