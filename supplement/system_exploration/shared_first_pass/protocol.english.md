# Shared-first-pass protocol

Summary of the preserved `experiment_protocol.md`, covering the design, selection rules and endpoints. The [protocol manifest](protocol_manifest.release.json) and [dataset-freeze manifest](dataset_freeze_manifest.release.json) retain the recorded configuration and freeze metadata, with local runtime locations removed.

## Registration and execution conditions

The source records registration at 23:48:49 UTC on 17 July 2026, before formal holdout execution, under `gpt55_c_shared_first_pass_rowwise_verifier_v1`. It records GPT-5.5, high reasoning effort and fixed concurrency eight. The candidate exposes exactly `causal_graph_query` and `causal_query_solver`. Gold answers are unavailable during execution. Only public declarations, final answers, tool observations, verifier/runtime records, usage and latency are retained; hidden chain of thought is neither requested nor persisted.

The accepted C baseline is the generic external-tools workflow. This study does not enable a new global compact skill or perform skill evolution. The older independently sampled E arm is historical behavioural evidence and does not identify the effect of a second revision. The existing 556 development rows are exploratory and cannot provide the final generalisation estimate.

## Shared record and conditions

All derived conditions use the same immutable first-pass record for each question, including its initial answer and tool observations.

| Condition | Operation |
|---|---|
| C0 | Preserve the initial C answer. |
| N | Produce normalised verifier events without changing the answer. |
| G | Apply a deterministic guard without a model call, only where the exact-capability, unique-alias, estimand and answer-space contracts agree and the tool evidence is not conflicting. |
| R | Apply at most one same-model revision to an actionable row, without rerunning tools. |
| GR | Apply G, then consider one revision only for the remaining actionable rows. |
| Legacy | Use the earlier multi-turn tool-agent workflow at equal execution settings for the formal holdout comparison. |

Permitted actionable events concern invalid/missing answer schema, structural query mismatch with a unique alias mapping, exact-solver answer disagreement under an exactness contract, a publicly resolvable tool-request contract mismatch, or answer-space mapping failure for formatting repair. A raw alias-string mismatch alone, ambiguous normalisation, unsupported/insufficient solver results, solver error without a reliable alternative, question-family labels, historical correctness and gold-dependent signals cannot trigger an answer override.

## Development selection

G, R and GR are eligible only if total correctness is at least C0's, corrections exceed regressions, unsupported/insufficient tool results do not change answers, and untriggered rows stay unchanged. Among eligible arms, the rule selects the largest net correction, then the smallest incremental token cost, then G before GR before R. If all are ineligible, it freezes C with no answer intervention instead of introducing another arm.

## Holdout construction and size

After candidate selection, the protocol constructs mutually exclusive clean-natural and structural-stress packs from the deterministic source split. It excludes development IDs, historical prompt/skill/resource-development IDs, stage-A/B IDs and defined content or near-duplicate combinations. The stress pack covers selected difficult structural families and is diagnostic only. The ordered IDs, family/split counts, source and pack hashes, selection command and code revision are recorded in the freeze manifest. Execution and post-run gold scoring are separated.

The plan targets at least the larger of 1,200 rows and the estimated 80%-power requirement, preferring 90% power where eligible untouched data allow it. If insufficient data remain, all eligible rows are used and achieved power is reported instead of inserting previously used rows. The resulting clean pack contains 974 questions, as recorded in the supplied freeze and run manifests.

## Endpoints and decision rule

The source specifies paired N, arm accuracies, both-correct/wrong and discordant counts, accuracy difference, exact two-sided McNemar p, a paired-bootstrap percentile interval, corrections/regressions, trigger/revision rates and resource use.

Superiority to C0 requires a positive difference, p below .05, a positive lower 95% interval bound, a correction/regression ratio of at least three, a revision rate at most 10% and a token increase at most 20%. A positive direction without the statistical requirements remains unconfirmed.

Legacy comparison uses identical ordered holdout IDs and inputs, model, reasoning effort, endpoint, retry and timeout settings, scorer and fixed concurrency. The candidate-minus-legacy paired 95% interval must have a lower bound above -1.5 percentage points. The candidate/legacy token ratio must be at most .30 and the model-call ratio at most .20, with exactly two candidate public tools. These requirements concern this historical system comparison.

The registered audit conditions include strict schemas, post-run gold joining, execution-payload checks, at most one revision per question, no tool reruns during revision, unchanged untriggered answers, failed answers remaining in the denominator, protected resume inputs and explicit terminal status. These are descriptions of the preserved protocol, not instructions for running this repository now.

If C0 improvement is unconfirmed but the legacy non-inferiority and resource requirements pass, the final decision retains C and adds normalised observability without answer intervention. The source prohibits changing the protocol after inspecting holdout results. The recorded final selection followed this C0 path.
