# DeepSeek V4 Agent Tools + PNS Results

## Graph adapter scope

The text-to-graph adapter produces the structured causal DAG corresponding to the CLADDER sample graph_id. It does not independently discover a new causal graph from natural language. Runtime provenance is labelled `cladder_graph_id_template`, and the adapter declares that it does not use the gold answer, gold reasoning, groundtruth or estimand.

The graph serves as input to runtime tools for graph rendering, path listing, motif detection and d-separation, with graph/path evidence included in the final evidence chain.

## 100-question maximum-thinking results with omitted max_tokens

Output directory

`outputs/experiments/deepseek_v4_cladder100_agent_tools_uncapped_v3_parser_20260622`

Configuration

- model: `deepseek-v4-pro`
- thinking: enabled
- reasoning_effort: max
- max_tokens: omitted from API request
- accepted records: 100
- unique samples: 100
- API OK: 100/100
- final schema valid: 100/100
- answer accuracy strict: 90/100
- trace valid strict: 13/100
- operation aligned strict: 3/100
- avg tool calls: 3.17
- avg model turns: 4.31
- estimated total cost: 5.2021834 CNY

Runtime tool counts:

- causal_graph: 100
- cladder_probability_facts: 99
- cladder_calculator: 92
- graph_motifs: 15
- directed_paths: 7
- d_separation: 4

All accepted records had both graph evidence and probability/numeric evidence.

## Agent-tool PNS analysis

PNS analysis artifacts:

`outputs/experiments/deepseek_v4_cladder100_agent_tools_uncapped_v3_parser_20260622/agent_tool_pns`

Key findings:

- graph evidence rate: 100%
- probability evidence rate: 100%
- extra graph tool rate: 22%
- calculator used rate: 88%
- avg declared PNS trace score: 0.1792
- avg tool PNS trace score: 0.0710
- avg combined PNS trace score: 0.1792

Main missing operations by declared trace:

- answer_supported_by_mediation_verdict
- answer_supported_by_collider_verdict
- check_natural_direct_effect
- counterfactual_answer_supported_by_world_comparison
- check_natural_indirect_effect
- answer_supported_by_adjustment_verdict

Interpretation:

The mandatory graph+probability evidence gate is useful as an admissibility filter. The weaker point is not basic tool access; it is final trace/tool alignment. The model often uses tools correctly enough to answer, but final `operation_plan` remains generic and does not fully mirror the actual tool evidence path, so trace/operation metrics stay low.

## PNS v1 optimization smoke

Added config:

`configs/model_providers/deepseek_agent_pns_optimized_uncapped.yaml`

Added policy:

- keep graph+probability evidence as necessary
- canonicalize `query_type` before calculator
- conditionally call graph_motifs/directed_paths/d_separation for mediation, adjustment, collider, and path queries
- make final operation_plan mirror the actual tool-derived evidence path

Paid smoke output:

`outputs/experiments/deepseek_v4_cladder20_agent_pns_optimized_20260622`

PNS v1 smoke results:

- records: 20
- API OK: 20/20
- final schema valid: 20/20
- answer accuracy: 17/20
- avg tool calls: 3.30
- avg turns: 4.45
- estimated total cost: 1.262268 CNY

Same-sample comparison against the baseline 100-run subset:

| run | samples | correct | accuracy | extra graph tool rate | avg tools | cost CNY |
|---|---:|---:|---:|---:|---:|---:|
| baseline same-20 | 20 | 19 | 95% | 40% | 3.45 | 1.0292 |
| PNS v1 | 20 | 17 | 85% | 35% | 3.30 | 1.2623 |

Conclusion:

PNS v1 should not be scaled. It preserved schema validity but did not improve accuracy, did not increase useful graph-tool use on the same sample set, and cost more. The next optimization should target final trace canonicalization and operation-plan synthesis after tool observations, rather than adding more pre-answer prompt pressure.
