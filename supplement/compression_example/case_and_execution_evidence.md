# q1428 and the executed candidate-selection rules

This evidence note supports the rubric additions without changing any reported experiment result. All quoted text comes from the archived q1428 records. The accompanying `case_example.json` contains the complete public problem, parent reasoning, segment offsets, exact continuation prompt, generated suffix, selected reasoning and judge records. `q1428_final_demo_verbatim.txt` renders the unchanged downstream example template at illustrative position 1. It does not assert that a particular target used that position.

## Worked example suitable for the manuscript

Question 1428 asks whether medication improves heart condition through blood pressure in a specified mediation graph. Medication changes the probability of high blood pressure from 0.82 to 0.01. Without medication, the probability of a healthy heart is 0.83 under low blood pressure and 0.43 under high blood pressure. The corresponding probabilities with medication are 0.73 and 0.50.

The selected KEEP continuation preserves the first segment of the parent, which spans characters 0–202, and generates all subsequent reasoning again. The frozen prefix contains exactly 203 characters, including its final newline.

```text
The user wants to determine if medication positively affects heart condition *through* blood pressure based on a hypothetical scenario.
This is a causal inference question asking about indirect effects.
```

The following passage is quoted from the newly generated suffix. In this passage, M denotes medication, B denotes high blood pressure and H denotes a healthy heart. This local M is the treatment, whereas the generic M in the thesis mediation notation denotes the mediator.

```text
Effect of M on B: M=1 decreases P(B=1) from 0.82 to 0.01. So M -> B is negative (M=1 lowers B=1).
Effect of B on H: B=1 decreases P(H=1) from 0.83 to 0.43 (at M=0) and from 0.73 to 0.50 (at M=1). So B -> H is negative (B=1 lowers H=1).
Since M -> B is negative and B -> H is negative, the indirect effect is negative * negative = positive.
Thus, medication positively affects heart condition through blood pressure.
```

The displayed passage is an editorial excerpt. The final demonstration retains the entire saved 954-token reasoning, including additional checking and repeated answer statements. Text omitted around the passage remains in that demonstration, which means the excerpt length is not the algorithm's compressed length. The parent contains 2,052 reasoning tokens under the same tokenizer, so the complete accepted trajectory is 53.51% shorter. Both lengths exclude the final visible answer object. The archived final content parses exactly as `{"answer":"yes"}`. The older input metadata also contains a stored count of 2,061, which is preserved in the evidence JSON but is not used for this comparison.

An independent calculation checks the candidate's qualitative conclusion. Let X denote medication, B high blood pressure and Y a healthy heart. Using the saved estimand at the untreated outcome reference level gives

\[
\mathrm{NIE}=\sum_b P(Y=1\mid X=0,B=b)\{P(B=b\mid X=1)-P(B=b\mid X=0)\}
=0.83(0.99-0.18)+0.43(0.01-0.82)=0.324>0.
\]

This is an independent substitution using the rounded public probabilities. It is not a quotation or numerical calculation produced by the selected candidate. The unrounded archived conditional probabilities give 0.3280824602967321, which agrees with the stored ground truth of 0.32808246029673194. Both calculations support yes. The check establishes the central inference for this example without claiming that every parent sentence or every accepted trajectory is semantically correct.

The selected record is `q1428-s001-keep-r1`, which belongs to the first completed matched round at step 1. Its final materialisation judgment was accepted by DeepSeek V4 Pro, which reported coherent and logically valid with confidence 0.97. This number is the judge's self-reported confidence rather than an independently estimated reliability probability. The earlier trial judgment reported 0.96. Exact concatenation of the saved prefix and suffix reproduces the selected artifact and the downstream canonical demonstration without alteration.

## Replacement text for the local comparison in §3.4

Each eligible parent segment defines two continuation prefixes. KEEP retains the parent through that segment, whereas DELETE ends immediately before it. The rest of the reasoning is generated anew from the public problem and the chosen prefix. A lineage identifies a fixed question, segment and intervention. Its raw attempts are separate sampled continuations. A matched round contains one valid KEEP continuation and one valid DELETE continuation, each with a deterministic correctness vote. These votes concern the newly generated answers, rather than repeated judgments of a single fixed output.

The configured comparison first checks three valid matched rounds and has a horizon of five. Let d be the number of correct KEEP answers minus the number of correct DELETE answers. At three rounds, the comparison triggers replacement when d exceeds 2 and stops without replacement when d + 2 is nonpositive. Otherwise it continues to five rounds. The implemented rule does not stop at four rounds. At five rounds, a positive difference triggers replacement and a tie or negative difference does not. Invalid attempts consume the raw-attempt allowance but do not enter the paired vote vectors. An observation is admitted only after both branches have supplied a valid continuation for that round. Exhaustion before a terminal comparison produces an operationally inconclusive result. The executed baseline contract allowed five raw attempts per branch. The planned seven-attempt amendment was not executed, and the closure record reports zero max7 generation rows.

The local comparison controls whether a replacement text is proposed. It does not decide whether every observed KEEP or DELETE continuation can enter the final pool. In q1428, one attempt in each branch failed the semantic-judge threshold. Five raw attempts per branch therefore yielded four valid matched rounds with four correct answers in each branch. The local result remained operationally inconclusive. The first KEEP continuation nevertheless met the individual export requirements and remained available for final selection.

## Replacement text for qualification and selection in §3.5

When the local comparison triggers replacement, one replacement text is generated and frozen for that segment. New continuations from this fixed replacement prefix form the REPLACE lineage. At the three- or five-valid-trial checkpoint, this lineage qualifies when at least three answers are correct and at least one continuation is individually exportable. Three incorrect answers reject the lineage. A positive majority without an exportable continuation cannot supply a final candidate, and exhaustion of the raw-attempt allowance leaves the lineage operationally inconclusive. The three-correct-vote requirement applies to this REPLACE qualification step.

For KEEP and DELETE, each observed continuation enters the global candidate pool when it is valid, belongs to a completed matched round, has the correct answer, passes the structural and semantic checks, preserves the required provenance and is shorter than its parent. It must also have a nonempty request identifier, reasoning and candidate identifier, with an answer matching the known demonstration answer. Eligibility does not require the local KEEP–DELETE comparison to reach a decision or the branch to accumulate three correct answers. A qualifying REPLACE lineage contributes its selected exportable continuation. The final pool is ordered by complete reasoning token count, then character count, then candidate identifier. The shortest eligible candidate becomes the optimized asset subject to final materialisation acceptance. These separate local and global rules explain how an accepted short trajectory can originate from an operationally inconclusive local comparison.

## Execution details and information access

The Phase56 runtime consumed frozen source-preserving parent segments rather than generating a new segmentation during the rollout. Its validation checks consecutive one-based step indexes, contiguous character ranges, exact substring equality and full reconstruction of the parent. Exposure flags form a cumulative suffix, and only segments before that suffix are eligible. The input preparation code converts zero-based atomic units to one-based segments and attaches intervening whitespace to the preceding unit. It uses the earlier of the frozen exposure annotation and a strong-answer regex match, which checks explicit answer and final-output commitments. For q1428, the zero-based exposure unit is 33, the first exposed segment is one-based step 34 at character 2976, and 33 steps are eligible. This is a recorded textual exposure boundary, not a proof that all earlier reasoning is semantically answer-free.

For q1428, the saved base prompt ends with the open assistant thinking prefix `<|im_start|>assistant\n<think>\n`. Appending the exact 203-character KEEP prefix produces the raw `/v1/completions` prompt with 286 tokens. The construction contract specifies Qwen/Qwen3.6-35B-A3B, temperature 1, top-p 0.95, top-k 20 and an 8,000-token requested suffix allowance. The effective allowance for this request is also 8,000. This construction setting is separate from the downstream evaluation's output budget.

Semantic judging receives the public problem, candidate chain, query metadata and the permitted advisory non-answer reference steps. The reference is not sent to Qwen generation, and the judge payload excludes explicit hidden gold-label and correctness fields. The references can still aid the causal calculation, so this is not a reference-free semantic review. Deterministic answer validation uses the known demonstration label separately. The judge requires both coherence and logical validity together with self-reported confidence of at least 0.90.

The original semantic-judge contract uses DeepSeek V4 Pro with thinking enabled and maximum reasoning effort. The later judging and recovery records use GPT-5.5 through the Responses interface with xhigh effort and a strict JSON schema. Among the 52 accepted final materialisation judgments, 1 record resolves to DeepSeek V4 Pro and 51 resolve to GPT-5.5. These are counts of accepted final judgments, not counts of every intermediate judge call. q1428's final judgment used one provider call without retry or fallback. Failed requests and historical recovery behavior remain represented in the existing experiment totals.

## Evidence anchors and provenance limits

The authoritative case fields are in `work/evidence/phase56/phase56_source_export.json`, under `items[qid=1428].input` and `items[qid=1428].result.artifact`. The separate selected-lineage export is `outputs/experiment/phase56/phase56_selected_lineage52.jsonl`, which provides the saved prefix, generated suffix and complete chain. The canonical accepted pool supplies the 2,052 and 954 token counts. The extraction script checks these counts with the saved Qwen tokenizer and makes no model calls.

The current method reference snapshot supplies the following implementation anchors.

| Rule | Source anchor |
|---|---|
| Three- and five-round paired decisions | `outputs/experiment/reference_method_code/src/qwen_pns_adaptive.py`, `decide_keep_delete`, line 312 |
| Invalid attempts, matching and admission | Same file, `run_adaptive_keep_delete`, line 377 |
| Frozen replacement lineage | Same file, `run_adaptive_candidate_lineage`, line 471 and `generate_optimized_pnscot`, line 658 |
| Global collection and sorting | Same file, `generate_optimized_pnscot`, lines 746–780 |
| Replacement majority checkpoints | Same file, `_candidate_decision`, line 959 |
| Individual export conditions | Same file, `_record_exportable`, line 1029 |
| Token, character and identifier ordering | Same file, `_candidate_sort_key`, line 1049 |
| KEEP/DELETE metadata wrapper after selection | Same file, `_synthetic_selected_result`, line 1058 |
| Frozen segments and exposure validation | `outputs/experiment/reference_method_code/src/pns_dataset_preparation.py`, lines 72–129 |
| Raw prompt formed from base prompt plus prefix | `outputs/experiment/reference_method_code/src/qwen_pns_batch56_adapter.py`, `_ensure_dataset_wave_prompts`, around lines 1340–1370 |
| Judge payload and pass conditions | `outputs/experiment/reference_method_code/src/experiments/cladder_pns_mvp/judge.py`, `chain_coherence_payload` and `chain_coherence_pass` |

The snapshot was captured from the current source worktree on 10 September 2026. Its byte identity with the historical Phase56 runtime is not established, as stated in its README. The q1428 matching, exhaustion, eligibility and selection claims are additionally supported by saved execution records. Eight accepted KEEP/DELETE examples have fewer than three valid correct branch votes, which independently rules out a universal three-vote export condition. Their identifiers and counts are retained in the evidence JSON.

The two `*_legacy_reference.py` files in this evidence folder were read from the earlier hardened runtime bundle. They illustrate the inherited prefix construction and segment schema only. They are not proof of Phase56 runtime identity and are not used alone to assert a historical execution rule. The available input preparation sources are `C:/Users/aklovey/Documents/Codex/2026-08-17/qwen36-pns-256/work/verify_demo56_budget.py`, especially `STRONG_ANSWER_EXPOSURE_RE`, `first_strong_exposure` and `make_segments`, and the preceding package builder. The original selector's atomic-unit construction was not recovered in this bounded check. The manuscript should describe the frozen units and the verified exposure overlay without inventing a sentence-splitting or semantic-segmentation procedure.

The source's displayed author-programmatic step 5 for q1428 contains arithmetic that does not evaluate to its stated number. The independent check above uses the saved estimand and the conditional probabilities instead. This source issue is recorded in the JSON so that the incorrect displayed line is not copied into the thesis as a verified calculation.
