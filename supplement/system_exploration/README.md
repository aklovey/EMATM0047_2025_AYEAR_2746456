# System-level exploration evidence

This supplement supports the dissertation's system-exploration chapter. It provides the actual paired records and resource fields needed to check the historical GPT-5.5 comparison, together with the preserved DeepSeek reports and relevant implementation excerpts. These studies are separate from the Qwen PNS demonstration-compression experiments.

| Study | Reused object | Main evidence |
|---|---|---|
| DeepSeek tool agents, 21-22 June 2026 | Visible conversation history and tool observations within one question | [100-question report](deepseek_agent/agent_tools_100_report.english.md), [500-question report](deepseek_agent/agent_tools_500_report.md), [later history-control excerpt](source_snapshots/august_agent_history.md) |
| GPT-5.5 shared first pass, 18 July 2026 | One saved initial output/observation record across post-processing conditions | [Original paired matrix](shared_first_pass/paired_sample_matrix.csv), [original resource summary](shared_first_pass/resource_metrics.json), [protocol account](shared_first_pass/protocol.english.md), [result account](shared_first_pass/report.english.md) |

The June reports are retained in a later August checkout. That checkout confirms accumulated-history control flow but does not establish byte identity with the June runtime. The July snapshots are also preserved source evidence, not a new claim of exact historical runtime identity. The [source register](source_register.json) identifies each file's source and whether it is unchanged, redacted, translated or an excerpt.

## What the system tables report

The DeepSeek accepted-record reports contain 90/100 and 444/500 correct answers. Their original strict trace metrics are 13/100 and 61/500, and their operation-alignment metrics are 3/100 and 7/500. Mean model turns are 4.31 and 4.368. The 500-question run records an eight-turn cap; the displayed 100-question configuration does not state a cap. The graph tool used CLADDER graph-ID metadata to retrieve a template. The operational trace checks are not expert semantic labels, and the two accepted-record runs are not assumed to be disjoint samples.

The shared-first-pass clean comparison uses the same **974 unique questions**, with one empty legacy answer retained in the denominator.

| Recorded measure | Legacy multi-turn | Selected shared C0 |
|---|---:|---:|
| Correct answers | 935 | 934 |
| Input tokens | 9,461,308 | 1,012,666 |
| Output tokens | 1,679,369 | 412,280 |
| Total tokens | 11,140,677 | 1,424,946 |
| Model calls | 3,571 | 100 |
| Shared first-pass shards | Not applicable | 49 |
| Public tool interfaces | 9 | 2 |

C0 has 19 gains and 20 losses relative to legacy. The original paired-bootstrap 95% interval for candidate-minus-legacy accuracy is [-1.33470, 1.12936] percentage points around -0.10267 percentage points. Under that historical protocol, the reported -1.5 percentage-point non-inferiority and resource requirements passed. This conclusion is separate from the current PNS hypothesis tests.

The selected candidate makes no incremental answer-revision calls. The system call counts reflect shard-level versus per-question execution and different tool interfaces. The 97.20% model-call and 87.21% total-token reductions concern the complete configurations, rather than an isolated compression effect. A separate 180-question stress diagnostic scores 158 versus 163 and is not pooled with the clean comparison.

## Recalculate from the released evidence

From the repository root, using the existing analysis requirements:

```sh
python -m pip install -r requirements-analysis.txt
python supplement/system_exploration/recalculate_system_results.py --output reanalysis/system_exploration.json
```

This runs without a model service. It checks the paired matrix, unchanged C0 answers, denominator and ordered IDs, and recalculates the contingency counts and original paired statistics. It sums the [974 legacy accounting rows](shared_first_pass/clean_holdout_natural/legacy_accounting.csv) and [49 shard accounting rows](shared_first_pass/clean_holdout_natural/shard_accounting.csv), then compares their totals with the released execution manifests. The original source functions used for aggregation and inference are preserved under [source_snapshots](source_snapshots/README.md). The [saved verification result](recalculated_system_results.json) records the executed offline check.

Legacy's 3,570 model turns plus one schema repair yield 3,571 model calls. Its 2,582 tool calls are recorded separately. Prompt plus completion tokens equal total tokens; the 870,418 separately reported reasoning tokens are not added a second time. The shard manifest records 49 unique shards and two retries; the 100 calls already come from its recorded model-call aggregation. The script does not reinterpret the retry count as an extra charge outside that total.

## Record types

- `paired_sample_matrix.csv`, `primary_paired_comparisons.csv`, `resource_metrics.json` and supporting comparison CSVs are unmodified files from the preserved run.
- `*.release.json` preserves experimental fields and lists each removed local path or service endpoint. Its original hash fields describe original artifacts, not the redacted release file.
- `legacy_accounting.csv` is a selected-field export from accepted per-question raw records. `shard_accounting.csv` selects accounting fields from each original graph audit. Values are not translated or recomputed except the explicitly named legacy `model_calls` column.
- Protocol and report summaries identify their source; the [source register](source_register.json) records translation, redaction and excerpting.
- The source excerpts support inspection of accounting and conversation-history logic. They do not include the complete historical runtime environment.

Current Qwen cohorts, historical DeepSeek runs and the GPT-5.5 comparison retain separate models, input access, sample sets and scoring contracts. This directory adds their evidence without merging their results or changing their original experimental roles.
