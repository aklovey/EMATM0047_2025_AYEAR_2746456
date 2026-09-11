# Blinded model-assisted semantic review

This review read 12 complete candidates individually, using only the designated questions, candidate traces and supporting task specifications. Under a strict complete-trajectory criterion, five passed and seven contained substantive uncorrected problems. Among the seven failures, A06, A10 and A12 still contained valid main proofs. Their failures arose from coexisting erroneous branches or auxiliary claims. The main arguments of A01, A04, A09 and A11 were not certified. All 12 final yes/no answers agreed with the independently recalculated directions, which does not establish correctness of their complete reasoning.

This is a review assisted by a single model, rather than human/expert ground truth or objective calibration of the judge's FPR. The sample was purposively enriched, so its counts do not estimate population rates. The judgement file was completed before unblinding, without reading the sidecar, original judge decisions, individual sources or selection mapping. audit_plan disclosed the overall sample composition, and the supporting source_meta included a groundtruth field. The review was therefore blinded to original judge decisions and source identities, but not completely blinded to answers. Recalculation did not use source groundtruth values.

The review assigned pass/fail/unknown separately for estimand, causal rule, factual/counterfactual updating, arithmetic and support for the candidate's conclusion. An arithmetic pass means that the stated expression was evaluated correctly, not that its estimand was valid. Early draft errors explicitly replaced later by correct rules were not treated as final failures. Retained errors were recorded separately. A conclusion-support pass permits a valid main proof to coexist with other errors, which still count against the complete trajectory.

| Audit ID | Complete trajectory | Valid main proof | Independent recalculation | Main evidence |
|---|---|---|---|---|
| A01 | fail | Not certified | Y_0=0, yes | Incorrectly holds a negatively related child at zero after intervention and treats an AND input as an independently sufficient cause. Both factual and counterfactual Y are actually zero. |
| A02 | pass | Present | ATE=0.173784, yes | Correct complete frontdoor formula, population weights and arithmetic. Later reasoning corrects the early error. |
| A03 | pass | Present | NIE=0.2346, yes | Correct directions for the two relations and comparison within a fixed X stratum. A sign proof is sufficient. |
| A04 | fail | Not certified | ETT=0.1184, yes | Uses the observed untreated-group risk 0.5920 as the counterfactual risk for the factual treated group. The correct value is 0.5188. |
| A05 | pass | Present | Y_1=0, yes | Retains the observed ancestor at zero, with both OR inputs zero after intervention. Local event notation is imprecise but does not invalidate this case's proof. |
| A06 | fail | Present | NDE=0.1068, no | The main NDE calculation is correct, but the auxiliary decomposition retains incorrect IE, TE and magnitude claims. |
| A07 | pass | Present | Y_0=0, no | Correctly updates descendants together before applying OR. Earlier exploratory estimands are not retained. |
| A08 | pass | Present | ETT=0.1431, yes | Correctly retains the factual treated-stratum outcome mechanism and replaces only the mediator distribution. |
| A09 | fail | Not certified | ETT=0.0795, yes | Substitutes an observed risk difference for ETT. The correct counterfactual is 0.0920 rather than 0.1556. |
| A10 | fail | Present | Y_0=0, yes | The valid main AND proof needs only one zero input. Errors in the negatively related child's update and an alternative OR claim remain. |
| A11 | fail | Not certified | NIE bounds are entirely positive, no | Does not adjust for H-induced mediator–outcome confounding. The reviewer's independent bound proof cannot be attributed to the original candidate. |
| A12 | fail | Present | ATE=0.13133, no | Numerical comparisons give a valid frontdoor sign proof, but the trace repeatedly claims that an arrow itself implies a positive effect. |

The correct decomposition for A06 is NDE=0.1068, TNIE=-0.1989 and TE=-0.0921. The candidate's “Indirect ≈ -0.214. Total ≈ -0.106.” is not corrected later. A12 does not fail for omitting a magnitude calculation. Its numerical sign argument is valid. The strict failure concerns the retained general rule that a direct effect implies a positive effect. When reporting these cases, the dissertation should explain the sensitivity to this criterion rather than describe the candidates as wholly unable to calculate NDE or ATE.

Recalculation of A01 and A10 under the supplied deterministic mechanisms gives (V2,V3,Y)=(1,0,0) when X=1 and (0,1,0) under do(X=0). The supporting specification describes V3 as not V2, while the graph lists X→V3. These are equivalent for this query because V2=X and the intervention is only on X, although the edge-by-edge descriptions are not identical. In A05, “P(Qwiu=0 OR Yupt=0)” is not a general formula for negating OR. The surrounding candidate text explicitly says that both inputs are zero and uses “neither”, so this case's proof passes with the notation limitation retained.

A11 particularly requires separating an invalid formula from whether the sign can still be established for the question. Let q00_h=P(Y=1|do(X=0,B=0),H=h), and define q01_h analogously. Under the supplied binary Markovian graph, no additional unmentioned common causes, and the public percentages, the constraints are as follows.

- 0.4845 q00_poor + 0.129 q00_good = 0.3681.
- 0.3655 q01_poor + 0.021 q01_good = 0.33239.
- NIE = 0.238(q01_poor-q00_poor) + 0.0525(q01_good-q00_good), with each q in [0,1].

Local Decimal arithmetic enumerated the endpoints of these constraints and gave NIE∈[0.0356189474, 0.0853129498]. The sign is therefore still positive for these data, although the exact NIE is not point identified. Multiplying unadjusted outcome contrasts gives 0.07553, but this value cannot be called an identified NIE. The supporting source estimand itself omits outcome adjustment for H, so the review does not treat that formula as a theoretical authority. These bounds are additional reviewer calculations. The original candidate did not contain this argument.

All 12 audit IDs are unique and present. Programmatic checks confirmed that all 60 criterion quotations are exact substrings of the candidate text. This review made no additional model API requests and used no sidecar or other private inputs. Local calculations checked only Boolean states, arithmetic from the supplied percentages and the A11 linear-constraint endpoints. Per-criterion machine-readable results are retained in the designated blind12_review.jsonl file. high/medium confidence describes reviewer judgement rather than calibrated probabilities.
