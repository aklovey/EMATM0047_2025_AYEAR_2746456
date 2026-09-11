# Paired-change cases from main300

The selection rule was written before completion. It takes the two smallest question_id values among FULL-wrong/PNS-correct targets, the two smallest among FULL-correct/PNS-wrong targets, and the smallest question_id with a format failure, giving five cases. selection.json records ten and eight targets in the two paired-change categories and ten targets affected by format failures. This review explains only the five fixed cases. It did not resample, change the parser, supplement recorded answers or make new model calls.

Here, correct and incorrect refer to the predefined strict score against the source gold label. They do not establish that every reasoning step is correct. Each target has one stochastic rollout per condition, and main300 contains CPT reuse. These are descriptive cases. A single observed difference cannot be attributed to compression itself, a particular deleted passage or generalisation across CPTs.

| qid | Query | Source gold | FULL→PNS | Case focus |
|---|---|---|---|---|
| 662 | Joint NIE | yes | no→yes | FULL replaced the joint mediated effect with a requirement that each path be positive. PNS ultimately retained the joint interpretation. |
| 8884 | ATE | yes | no→yes | FULL added an H→smoking edge absent from the question. PNS eventually calculated the effect using the absence of a backdoor into treatment. |
| 4910 | ATE | no | no→yes | PNS read the negative risk difference but overrode it with commonsense expectations and the claim that an edge implies a positive effect. |
| 9510 | ATE/IV | yes | yes→no | This is a decline under source-gold scoring. PNS appealed to common sense, while FULL also lacked conditions needed for general ATE identification. |
| 5820 | NDE | no | no→no | FULL and PNS did not differ. ZERO failed the output enum because it returned capitalised “No”. |

## q662 and joint mediation

The public graph is season→weather/sprinkler→ground, with no direct season→ground edge and no backdoor into season. Together, the two mediators cover all causal paths, so the joint NIE=TE=0.60−0.55=0.05, supporting yes. This result does not require both individual paths to contribute positive effects.

FULL wrote “So Indirect Effect = 0.05 (positive).” midway through its reasoning, but later wrote “But we definitely lack the data to confirm the mediation paths are positive.” and ultimately returned no. PNS also initially questioned whether the information was sufficient, but later stated “The combined indirect effect is positive.” and returned yes. Quoting only FULL's correct intermediate expression would incorrectly suggest that its self-correction was complete, because its final conclusion changed the estimand again. PNS's language about simply adding individual path effects should not be generalised to path-specific effects with interactions. The valid argument in this question is that the joint mediators cover all causal paths.

## q8884 and confounding of a downstream mediator

The public graph contains S→B, S→Y, H→B, H→Y and B→Y, but no H→S edge. H does confound B's effect on Y, yet S has no incoming backdoor. The population ATE is therefore P(Y=1|S=1)−P(Y=1|S=0)=0.54−0.70=−0.16. The question asks whether the effect is a reduction, so the answer is yes.

FULL introduced “H -> S”, then repeatedly speculated that unobserved confounding might reverse the observed difference and answered no. PNS eventually stated “No H -> S. So S is exogenous with respect to M's confounders. Observational = Causal.” Its final calculation is valid. PNS still included one sentence treating the direct S→Y edge as a reason for absence of confounding, so not every sentence is rigorous. The valid justification is its final argument about the absence of a backdoor.

## q4910 and negative probabilities overridden by common sense

In the public graph H→W, H→A and W→A, husband H has no parents and wife W is a downstream mediator. ATE=0.31−0.79=−0.48, so a question asking whether it increases alarm ringing should be answered no.

FULL correctly wrote “Setting the alarm by the husband decreases the probability of the alarm ringing (0.31 < 0.79).” PNS also read the two probabilities and negative association correctly, but subsequently insisted “Direct causal effect implies increase.” and returned yes. An arrow allows causal influence without specifying its sign. This is a retained rule or commonsense error, rather than a failure to see the probabilities or subtract them correctly. One response difference cannot identify which compressed passage caused the error.

## q9510 and the distinction between scoring decline and population ATE identification

Let Z denote global versus local company, W clean water and Y cholera. The public marginal differences are ΔY=0.41−0.54=−0.13 and ΔW=0.26−0.56=−0.30, giving a Wald ratio of 13/30≈0.433333.

FULL made a sign error in its first half but explicitly corrected it later with “So Effect W->C must be Positive!” The earlier error should not be described as an uncorrected final sign error. PNS ultimately rejected a positive effect with “In any reasonable model, clean water reduces disease.” It attributed company-stratified differences to poverty confounding, contrary to the closed graph and hypothetical-world constraints in the question.

FULL also claimed “So the mediation equation holds exactly.” This goes beyond what a general IV graph guarantees. The public graph and four marginal probabilities alone do not establish that the Wald ratio equals the population ATE. Additional conditions, such as effect homogeneity, may support that interpretation. Instrument monotonicity alone is also insufficient to equate a local effect with the population ATE. The complete public question supplied here does not explicitly assume linearity, homogeneity or monotonicity.

A binary-H counterexample can be checked directly and is compatible even with instrument monotonicity. Let H be independent of company Z, with each H stratum having probability 1/2. Set Z=0 for global and Z=1 for local. In the order H=0, H=1, use the following probabilities.

- P(W=1|global,H)=(9/70,137/350), and P(W=1|local,H)=(7/10,21/50).
- P(Y=1|W=0,H)=(26/125,9/10), and P(Y=1|W=1,H)=(177/250,0).

Marginalising over H exactly recovers P(W|global/local)=0.26/0.56 and P(Y|global/local)=0.41/0.54. However, ATE=½(0.708−0.208)+½(0−0.9)=−0.20. The local company increases the probability of W in both H strata. A shared Uniform threshold can therefore realise a monotonic response for every individual. This counterexample shows that a positive Wald ratio does not determine the population ATE. It does not assert that the actual hidden source CPT has a negative ATE.

The independent script [q9510_public_iv_counterexample.py](q9510_public_iv_counterexample.py) was executed, and all probability, ATE and monotonicity-compatibility assertions passed. The main scores remain FULL correct and PNS incorrect. FULL should not be presented as a complete identification proof, and PNS's no should not be reinterpreted as recognising non-identifiability. This limitation concerns the public case examined here, rather than a judgement on the entire benchmark.

## q5820 and case-sensitive enum failure

ZERO's saved content is exactly `\n\n{"answer": "No"}`. It is valid JSON with permitted leading whitespace, but “No” is outside the strict lowercase yes/no enum. There is no code fence, explanatory prefix or empty content. finish_reason is stop, and the original response was not truncated. The original strict prediction is empty, correct=0 and format_valid=0. These values are retained. Lowercasing the answer after the fact or substituting an answer from reasoning would change the scoring rule.

FULL and PNS both returned valid lowercase no. Both compared stairs with the elevator and converted mortality to survival. The survival effects in the two mood strata are −0.47 and −0.45. With the elevator as baseline, NDE_survival=0.18×(−0.47)+0.82×(−0.45)=−0.4536. FULL explicitly wrote “Stairs vs Elevator: Let's treat Elevator as baseline/reference.” PNS used the same direction.

The public question refers only to “my decision” and does not clearly name treatment 1/0. The source no label cannot establish that the candidates' variable coding is necessarily correct. Reversing the comparison to elevator versus stairs gives NDE_survival=+0.4568. The definite finding here is the original content's enum error. Numerical interpretation is reported only for the named comparison explicitly used by each candidate.

## Evidence and limitations

The complete machine-readable record is work/main_cases/case_review.json. It contains the public formulas, 17 exact short quotations, SHA-256 values for 20 saved responses, unchanged content, original strict scores and case-specific limitations. Programmatic checks confirmed that the five qids matched the preselected list, all 17 quotations were substrings of their source responses, and strict enum checks on all 20 content fields agreed with the existing format_valid values. The original responses and main scores were unchanged.

This is an unblinded electronic-appendix case review assisted by a single model. It is not a set of human expert labels or a new causal experiment on the mechanism. If used in the dissertation, one or two sentences can identify the cases, with complete evidence retained in the electronic supplement rather than occupying the 30-page main-text allowance.
