# Preserved implementation excerpts

These files expose the actual accounting, pairing and history operations relevant to the system results. They are excerpts from preserved project checkouts, not a full environment for restarting the historical agents.

| File | Source and purpose |
|---|---|
| `resource_aggregation.py` | Verbatim `legacy_resource_metrics` and `_aggregate_generic_audits` from July `src/formal_holdout_experiment.py`. The first counts model turns plus schema repair; the second sums each unique shard audit once. |
| `paired_statistics.py` | Verbatim paired comparison and bootstrap functions from July `src/formal_experiment_reporting.py`, with imports added so offline reanalysis can call them. |
| `paired_matrix_order.py` | Verbatim pairing function from the same July module. Its question-ID order check precedes the post-run answer/correctness matrix. The external answer-normalisation helper is not bundled here. |
| `shard_index.py` | Verbatim July `index_generic_shards` function. It attaches one graph-audit resource record to the questions in that shard. The original JSON reader helpers are outside the excerpt. |
| `july_legacy_history.md` | Original line ranges showing one question's evolving message list and appended assistant/tool observations in the July runner. |
| `august_agent_history.md` | Original line ranges from the later 24 August checkout supporting the June reports' multi-turn interpretation. Exact identity with the June runtime has not been established. |

The [source register](../source_register.json) gives original relative file paths and line ranges. Each function body is preserved verbatim. Only clearly identified supporting imports and explanatory wrapper text are added. The history extracts are text for inspection and are not executable scripts. Runtime secrets, endpoint settings, other local services and the full dependency tree are outside this excerpt release.
