# CausalMath theory and the Phase56 adaptation

Definitions of necessity and sufficiency, with the implemented Phase56 continuation score and candidate-selection procedure.

## Theoretical background

CausalMath [14] connects reasoning-step interventions to the probability of necessity and sufficiency. For a question q and known correct answer y, let S be the original chain and let S′t replace step st with an altered step while regenerating its continuation. Its PS and PN definitions condition on different factual outcomes, which separates the chance that a chain corrects a failure from the chance that altering a step breaks a successful answer. The joint PNS event requires success under the original chain and failure under the altered chain for the same underlying case.

The identification conditions determine when this joint event can be recovered from intervention probabilities. CausalMath defines exogeneity through P(st | do(s<t), q) = P(st | s<t, q). Its monotonicity assumption excludes an altered chain correcting an answer that would fail under the original chain. Under these conditions, PNS equals the difference between original and altered intervention success probabilities. A second result replaces monotonicity with the stronger requirement that the original intervention succeeds with probability one. PNS then becomes one minus the success probability of the altered intervention. A single correct parent response provides an operational starting point, but does not establish that probability-one condition.

Algorithm 1 of CausalMath evaluates altered continuations with a validator and estimates the score through a Monte Carlo average. It retains steps whose scores exceed a threshold and uses the resulting traces as demonstrations or training data. The present method adopts step interventions and continuation-based evaluation for demonstration compression, with a different search procedure. All candidates originate from a fixed parent, KEEP and DELETE are compared through admitted valid rounds, and the final trajectory is selected globally by length subject to answer, provenance and semantic checks. The resulting local contrast measures response sensitivity under this procedure. The experiments do not establish the identification assumptions needed to interpret it as Pearl PNS.

## Core formulas with exact source anchors

### T1  Conditional sufficiency and necessity

$$
\begin{aligned}\mathrm{PS}(S,q)&=P(A_{\operatorname{do}(S)}=y\mid A\ne y,\bar S,q),\\\mathrm{PN}(S,\bar s_t,q)&=P(A_{\operatorname{do}(S_t^{\prime})}\ne y\mid A=y,S,q).\end{aligned}
$$

Definitions 2 and 3, equations (2) and (3), printed page 4.

Sbar is the null or incorrect reference chain. S_t_prime=(s_<t,sbar_t,s_prime_>t), where the alternative step changes the downstream rollout. Conditional definitions are not the binary parent-correctness check.

### T2  Joint counterfactual PNS

$$
\mathrm{PNS}(S,\bar s_t,q)=P\!\left(A_S=y,\ A_{S_t^{\prime}}\ne y\mid q\right),\qquad S_t^{\prime}=(s_{<t},\bar s_t,s_{>t}^{\prime}).
$$

Definition 4 begins on printed page 4 and equation (4) appears on printed page 5.

Notation makes conditioning on q explicit, which is implicit in original equation (4). This is a joint counterfactual event, not a difference of two arbitrarily sampled text-completion rates.

### T3  Identification under stated conditions

$$
\mathrm{PNS}(S,\bar s_t,q)=\begin{cases}p_S(q)-p_{S_t^{\prime}}(q),&\text{under exogeneity and monotonicity},\\1-p_{S_t^{\prime}}(q),&\text{under exogeneity and a perfect intervention with }p_S(q)=1.\end{cases}
$$

Lemma 1, printed pages 5–6; Appendix A.1 and Lemma 2, printed pages 23–24; Appendix A.3 and Lemma 3, printed page 24.

The second route removes monotonicity but retains the specified perfect-intervention interpretation and its connection to interventional probabilities. Appendix A.3 also invokes exogeneity in its proof. One observed correct trace does not establish p_S=1.

Here $p_S(q)=P(A=y\mid\operatorname{do}(S),q)$. Exogeneity is written in original equation (A.1) as $P(s_t\mid\operatorname{do}(s_{<t}),q)=P(s_t\mid s_{<t},q)$. Monotonicity is $P(A_S\ne y,\ A_{S_t^{\prime}}=y\mid q)=0$. The second line retains the perfect-intervention and exogeneity interpretation used in Appendix A.3, while dispensing with monotonicity.

### T4  CausalMath Monte Carlo score

$$
\widehat{\mathrm{PNS}}_{\mathrm{CM}}(S,\bar s_t,q)=1-\frac{1}{k}\sum_{j=1}^{k}V\!\left(S_t^{\prime(j)}\right).
$$

Equation (5), printed page 6; Algorithm 1, printed page 5.

Under the preceding perfect-original-intervention condition, ideal V is the binary success indicator for the altered rollout. The paper applies a validation model to logical integrity and coherence as well as answer success. With an imperfect validator this is a validator-based approximation, not an exact identified quantity.

### T5  Actual Phase56 local continuation contrast

$$
\widehat{\Delta}_t(n)=\frac{C_{K,t}(n)-C_{D,t}(n)}{n},\qquad C_{b,t}(n)=\sum_{r=1}^{n}\mathbf{1}\{\widehat y_{b,t,r}=y\},\quad b\in\{K,D\}.
$$

qwen_pns_adaptive.py decide_keep_delete and run_adaptive_keep_delete, lines 312–468; archived adaptive_rollout.steps records.

n counts admitted valid matched rounds, rather than raw attempts. The implemented decision uses the integer numerator d. Matching is bookkeeping across sampled continuations, not a pairing of observed individual counterfactual outcomes. Validity filtering and adaptive stopping remain part of the score definition.

## Algorithm adapted to the executed method

```text
Algorithm 1  Frozen-parent candidate search executed in Phase56
Input  Public problem q, known demonstration answer y, frozen parent S,
       eligible source-preserving segments T, raw cap 5 per branch
Output An accepted shorter trajectory or a recorded construction failure

C ← empty candidate pool
for each segment t in T
    prefix K ← S through the end of t
    prefix D ← S before the start of t
    n ← 0; raw K ← 0; raw D ← 0; d ← 0
    observations ← empty; local decision ← inconclusive
    while n < 5
        trial K ← NextValid(K, raw cap 5)
        if trial K is missing
            break
        trial D ← NextValid(D, raw cap 5)
        if trial D is missing
            break
        admit both trials as the next completed matched round
        n ← n + 1
        d ← d + correct(K) − correct(D)
        if n = 3 and d > 2
            local decision ← trigger replacement; break
        if n = 3 and d + 2 ≤ 0
            local decision ← do not trigger; break
        if n = 5
            local decision ← trigger replacement if d > 0 else do not trigger
    add every individually exportable admitted K or D observation to C
    save local decision and all attempts

rank C by complete reasoning tokens, characters, then candidate identifier
materialise the first candidate when C is nonempty
retain it only if final materialisation acceptance succeeds
otherwise preserve the construction failure in the closure

NextValid samples from public q plus the fixed branch prefix until a valid
trial appears or that branch has used five raw attempts across this step.
Every raw attempt is recorded, including failures. An unmatched valid trial
remains in the record but is not admitted to the vote vectors or candidate pool.
```

This pseudocode describes the executed KEEP/DELETE search and its final selection, rather than reproducing CausalMath Algorithm 1. Each trial is a newly sampled suffix. Invalid attempts consume the branch cap, while only a complete valid pair can enter the vote vectors or candidate pool. Four rounds are not an early stopping checkpoint. The local decision controls the configured replacement extension, but it is not a universal majority or export criterion. Individually exportable KEEP/DELETE continuations require correctness, admission to a completed pair, the required checks, a shorter complete chain and valid provenance. They may be selected even when the local comparison remains inconclusive.

The configured extension would freeze one replacement step and sample its REPLACE lineage, accepting that lineage at the three- or five-valid-trial checkpoint only with at least three correct votes and an exportable continuation. Phase56 contains no replacement-generation or REPLACE request rows, so that extension contributes no empirical result here and is omitted from the executed pseudocode. The planned increase to seven raw attempts was also not executed. Construction ended with 52 accepted trajectories and 4 failures. The later use of the exact parent for those four demonstration identities is a separate downstream policy, which does not convert the construction failures into successes.

## Concentrated comparison for §2.5 or the supplement

| Aspect | CausalMath | Executed Phase56 |

|---|---|---|

| Purpose | PNS-based reconstruction for mathematical and commonsense reasoning, followed by ICL or SFT | Auditable demonstration compression evaluated on few-shot causal inference |

| Intervention | An altered or corrupted step and a regenerated continuation, with semantic-disjointness required in Algorithm 1 | KEEP ends after a frozen parent segment and DELETE ends before it; continuations may recover omitted content |

| Search state | Paper describes iterative necessity-based pruning; current official code updates the chain from the edited step onward | Every eligible position is evaluated against the same frozen parent; candidate trajectories are pooled globally |

| Local quantity | One minus average validation success for altered rollouts, interpreted under stated assumptions | Difference of correct-answer counts across admitted valid KEEP and DELETE rounds |

| Sampling and stopping | k altered rollouts and a necessity threshold alpha in paper Algorithm 1 | Checks at 3 and 5 valid matched rounds with independent raw cap 5 per branch; invalid attempts do not vote |

| Selection | Retain or prune using the necessity threshold; repository also contains iterative suffix replacement | Individual export eligibility followed by complete-token, character and identifier ordering; final acceptance is separate |

| Replacement | Central to the stated counterfactual construction | A configured extension with no observed replacement-generation or REPLACE rows in Phase56 |

| Semantic guarantees | Identification relies on specified interventions and assumptions | Structural traceability, answer checks and fallible semantic judging are recorded; no identification or semantic-fidelity theorem is established |

## Source interpretation notes

The original paper uses an observed binary correctness check as its practical PS estimate in Algorithm 1 on page 5. Equations (2) and (3) define conditional counterfactual probabilities, and Lemma 1 imposes probability-one success of the original intervention. The exposition should preserve this distinction rather than equating all three objects.

The theory formula uses a validator V. To interpret the Monte Carlo average as altered-intervention success, V must measure the relevant success event accurately and rollouts must follow the specified intervention distribution. A semantic judge introduces measurement error, while deletion followed by unconstrained recovery differs from a forced semantically disjoint corrupted step. The matched rounds in Phase56 do not identify the joint potential outcomes for a shared latent unit.

The original Algorithm 1 retains a step when its score is strictly greater than alpha and drops it otherwise. Current repository code also contains a sequential update function that replaces the current suffix when pn is strictly less than its threshold. The packet cites these at their own source level and does not silently treat the repository as a verbatim transcription of the published pseudocode.

The current official repository was read without executing its code. Relevant functions in `algo/pnps_cot.py` are `parse_nodes`, `generate_replacement_step`, `ensure_different_step`, `evaluate_replacement_step` and `update_chain_if_needed`. The snapshot is saved as `official_pnps_cot.py` for inspection. It splits nodes at double newlines and tests an alternative step across fresh continuations. Phase56 instead uses its frozen source-preserving segments and exact raw-prefix continuation records.

The Phase56 closure explicitly records zero max7 generation rows and no replacement-generation or REPLACE rows. The pseudocode therefore omits that unexecuted extension while the accompanying explanation retains its configured role. All 52 accepted trajectories arose from KEEP or DELETE, and the 4 construction failures remain failures.

## Reference 14

[14] X. Yu, Z. Wang, L. Yang, H. Li, A. Liu, X. Xue, J. Wang and M. Yang. Causal Sufficiency and Necessity Improves Chain-of-Thought Reasoning. Advances in Neural Information Processing Systems, vol. 38, pp. 126109–126141, 2025. doi 10.52202/085713-4204.

The following BibTeX was fetched directly from the current official proceedings endpoint. The older local BibTeX has the same author list, title, year and pages but omits the DOI.

```bibtex
@inproceedings{NEURIPS2025_b7870bd4,
 author = {Yu, Xiangning and Wang, Zhuohan and Yang, Linyi and Li, Haoxuan and Liu, Anjie and Xue, Xiao and Wang, Jun and Yang, Mengyue},
 booktitle = {Advances in Neural Information Processing Systems},
 doi = {10.52202/085713-4204},
 editor = {D. Belgrave and C. Zhang and H. Lin and R. Pascanu and P. Koniusz and M. Ghassemi and N. Chen},
 pages = {126109--126141},
 publisher = {Curran Associates, Inc.},
 title = {Causal Sufficiency and Necessity Improves Chain-of-Thought Reasoning},
 url = {https://proceedings.neurips.cc/paper_files/paper/2025/file/b7870bd43b2d133a1ed95582ae5d82a4-Paper-Conference.pdf},
 volume = {38, Main Conference},
 year = {2025}
}
```

[Official proceedings metadata](https://papers.nips.cc/paper_files/paper/2025/hash/b7870bd43b2d133a1ed95582ae5d82a4-Abstract-Conference.html), [official paper](https://papers.nips.cc/paper_files/paper/2025/file/b7870bd43b2d133a1ed95582ae5d82a4-Paper-Conference.pdf), [official source repository](https://github.com/yxn9191/causalmath).

## Verification scope

The local 33-page paper was extracted, and pages 4, 5, 23 and 24 were rendered to verify overbars, primes, conditions and equation placement. Equation (5) and Lemma 1 were checked on page 6. The existing implementation and closure records were used for the adaptation. No model calls or experiments were run. No manuscript or existing bibliography entry was changed.
