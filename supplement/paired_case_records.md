# Supplementary Case Records

These five records describe paired changes and a formatting failure in the completed main300 evaluation. Selection followed a rule written before the complete results were available: choose the two smallest numerical question IDs among PNS-correct/FULL-wrong targets, the two smallest among FULL-correct/PNS-wrong targets, and the smallest ID with a format failure if not already selected. The recorded categories contained 10 gains, eight losses, and 10 targets with a format failure. The [selection plan](case_selection_plan.md) and [selected public problems and scores](selection.json) retain the rule and its application.

Each target has one stochastic rollout per condition. This is a nonblinded, Codex/model-assisted descriptive review, not an expert gold standard or a new causal experiment. Repeated CPTs in main300 further limit generalisation. No target was resampled, parser changed, answer rescued from reasoning, or model call added. “Correct” below means strict agreement with the unchanged source gold; it does not certify the entire derivation.

| Question | Query | Source gold | FULL → PNS | Recorded contrast |
|---|---|---|---|---|
| 662 | Joint NIE | yes | no → yes | Joint mediation versus separate path signs |
| 8884 | ATE | yes | no → yes | An unsupported additional edge |
| 4910 | ATE | no | no → yes | A positive-effect default overrides negative data |
| 9510 | ATE / IV | yes | yes → no | Source scoring differs from identification validity |
| 5820 | NDE | no | no → no | ZERO fails the lowercase answer enumeration |

## q662: joint mediation does not require every path to be positive

Season affects weather and sprinkler; both affect ground wetness. There is no direct season-to-ground edge or backdoor into season. The two mediators jointly cover every causal path, giving joint NIE = TE = 0.60 − 0.55 = 0.05, hence **yes**. Neither individual path must have a positive effect.

FULL initially states, “So Indirect Effect = 0.05 (positive).” It subsequently concludes, “But we definitely lack the data to confirm the mediation paths are positive.” Its final **no** therefore overrides the correct intermediate calculation by changing the scope of the estimand. PNS also initially considers insufficient information, but eventually states, “The combined indirect effect is positive.” and answers **yes**.

The relevant justification is joint coverage of the causal paths. PNS's language about simply adding individual natural-path effects should not be generalised to settings with interactions. This response pair illustrates different interpretations of the target, without establishing that compression caused the correct interpretation.

## q8884: mediator–outcome confounding is not treatment–outcome confounding

Let S denote smoking, B birth weight, H health condition, and Y high infant mortality. The stated edges are S→B, S→Y, H→B, H→Y, and B→Y. H confounds the B–Y relationship, but there is no H→S edge or backdoor into S. Within this hypothetical graph, ATE = 0.54 − 0.70 = −0.16; the question asks whether smoking decreases the outcome, so the answer is **yes**.

FULL introduces “H -> S” and settles on “The safest causal inference answer is "No"”. PNS eventually gives the relevant justification: “No H -> S. So S is exogenous with respect to M's confounders. Observational = Causal.” It answers **yes**. The quoted M is the response's own notation.

PNS nevertheless contains an earlier faulty general rule that a direct edge itself rules out confounding. Its final no-backdoor argument supports the answer; not every sentence is rigorous. The example concerns adherence to the supplied graph, not real-world medical advice or evidence of systematic suppression of invented edges.

## q4910: a causal arrow does not encode a positive sign

The husband affects the wife and alarm, and the wife affects the alarm. The husband has no parents in the stated graph. Thus ATE = 0.31 − 0.79 = −0.48, and the question asking whether setting the alarm increases ringing should receive **no**.

FULL states, “Setting the alarm by the husband decreases the probability of the alarm ringing (0.31 < 0.79).” PNS reads the probabilities and recognises their negative association, but subsequently asserts, “Direct causal effect implies increase.” It also writes, “The direct effect of Husband setting the alarm on the alarm ringing is presumably positive”, before answering **yes**.

This is not simply a missed number or subtraction error. An unsupported sign assumption survives after the negative values have been acknowledged. The single rollout does not reveal which demonstration passage, if any, caused that assumption.

## q9510: unchanged source scoring and an identification limitation

Let Z denote company type, W clean water, Y cholera, and H unobserved poverty. The public graph has Z→W, H→W, H→Y, and W→Y, with no H→Z relationship. Comparing global with local companies gives ΔY = 0.41 − 0.54 = −0.13 and ΔW = 0.26 − 0.56 = −0.30. Their Wald ratio is 13/30 ≈ 0.433333.

FULL initially makes a sign error but later explicitly corrects it: “So Effect W->C must be Positive!” Its final **yes** must not be described as an uncorrected sign mistake. However, its assertion “So the mediation equation holds exactly.” does not establish population ATE identification. The public graph and four margins do not guarantee that the Wald ratio equals the population ATE. Additional restrictions, such as suitable effect homogeneity, would be needed for that interpretation; instrument monotonicity alone does not equate a local effect with the population effect.

PNS instead writes, “In any reasonable model, clean water reduces disease.” and “But this association is confounded by Poverty.” These appeals do not identify the information gap: the response substitutes everyday expectations and an unsupported explanation of company-stratified differences. Its **no** must not be credited as recognising non-identifiability.

The [exact counterexample script](q9510_public_iv_counterexample.py) uses equally probable binary H strata independent of Z, with Z=0 global and Z=1 local. In H=0, H=1 order, its probabilities are:

| Mechanism | H=0 | H=1 |
|---|---:|---:|
| P(W=1 ∣ global,H) | 9/70 | 137/350 |
| P(W=1 ∣ local,H) | 7/10 | 21/50 |
| P(Y=1 ∣ W=0,H) | 26/125 | 9/10 |
| P(Y=1 ∣ W=1,H) | 177/250 | 0 |

Marginalisation reproduces clean-water probabilities 0.26/0.56 and cholera probabilities 0.41/0.54 for global/local companies, yet ATE = ½(0.708−0.208) + ½(0−0.9) = −0.20. Local company status raises water-treatment probability in both strata; shared Uniform thresholds can therefore implement individual monotonicity. All script assertions pass.

This counterexample challenges identification from the public information; it does not claim that the actual hidden source CPT has negative ATE. The source gold **yes**, FULL's correct score, and PNS's incorrect score remain unchanged. Neither response supplies a complete population-ATE identification argument, and this case is not a verdict on the whole benchmark.

## q5820: valid JSON with an invalid answer value

ZERO's exact saved content is represented as `\n\n{"answer": "No"}`: two leading newlines followed by legal JSON. It contains no code fence, explanatory prefix, or empty content. `finish_reason` is `stop`, and the response is not recorded as truncated. The sole format failure is that uppercase `No` lies outside the strict lowercase `yes`/`no` enumeration. Its empty strict prediction, correct=0, and format_valid=0 are retained.

FULL and PNS both return valid lowercase **no**. FULL explicitly chooses “Stairs vs Elevator: Let's treat Elevator as baseline/reference.” Converting death risks to survival effects gives −0.47 and −0.45 across mood strata. With elevator as baseline, NDE_survival = 0.18(−0.47) + 0.82(−0.45) = −0.4536. PNS similarly states, “Direct effect on Survival = - (Direct effect on Death) = ~ -0.46.”

The public question says “my decision” without clearly naming the treatment direction; HEURISTIC_SHORT notes, “It's ambiguous which arm is the "treatment"”. Reversing the named contrast gives +0.4568. These calculations therefore follow the candidates' declared comparison, rather than inferring the encoding from source gold. The definite finding is the output-enumeration error; it is not a FULL-to-PNS improvement, and reasoning must not rescue ZERO's score.

## Supporting records

The portable [case record](case_review.json) preserves all 17 exact short quotations, all 20 original response hashes and contents, unchanged scores, and case-specific limitations. Its relative paths resolve to bundled raw responses. These records support inspection of what the saved responses say; they do not convert five selected examples into population error rates or a causal explanation of compression effects.
