# DeepSeek V4 CLADDER 500 Agent Tools Uncapped Results

Output directory:

`outputs/experiments/deepseek_v4_cladder500_agent_tools_uncapped_20260622`

Configuration:

- model: `deepseek-v4-pro`
- thinking: enabled
- reasoning_effort: max
- max_tokens: omitted from API request (`None` in planned requests)
- max_turns: 8
- accepted records: 500
- unique samples: 500
- balanced query types: 50 samples per type

Completion audit:

- API OK: 500/500
- final schema valid: 500/500
- tool execution rate: 100%
- total estimated cost: 36.1300846 CNY

Summary metrics:

- answer accuracy strict: 444/500 = 88.8%
- trace valid strict: 61/500 = 12.2%
- operation aligned strict: 7/500 = 1.4%
- avg tool calls: 3.176
- avg model turns: 4.368
- avg total tokens: 16956.952
- avg reasoning tokens: 6575.942

Runtime tool counts:

- causal_graph: 501
- cladder_probability_facts: 480
- cladder_calculator: 439
- graph_motifs: 93
- directed_paths: 53
- d_separation: 22

Agent-tool PNS analysis:

`outputs/experiments/deepseek_v4_cladder500_agent_tools_uncapped_20260622/agent_tool_pns`

- graph evidence rate: 100%
- probability evidence rate: 100%
- extra graph tool rate: 25.8%
- calculator used rate: 81.8%
- avg declared PNS trace score: 0.1580
- avg tool PNS trace score: 0.0690
- avg combined PNS trace score: 0.1580

Accuracy by canonical query type:

| query type | samples | accuracy | extra graph tool rate |
|---|---:|---:|---:|
| ate | 50 | 96% | 16% |
| backadj | 50 | 90% | 82% |
| collider_bias | 50 | 94% | 48% |
| correlation | 50 | 98% | 0% |
| det-counterfactual | 50 | 84% | 42% |
| ett | 50 | 54% | 6% |
| exp_away | 50 | 92% | 14% |
| marginal | 50 | 100% | 4% |
| nde | 50 | 92% | 18% |
| nie | 50 | 88% | 28% |

Interpretation:

The 500-sample run confirms the 100-sample pattern at larger scale: answer accuracy is high enough to be useful, runtime evidence collection is stable, and schema/tool-call reliability is strong after accepted-record filtering. The main weakness remains trace quality rather than answer generation. `ett` is the clear accuracy bottleneck, and final operation-plan alignment remains very low despite valid tool evidence.

Next optimization target:

Post-tool trace synthesis should be prioritized over more prompt-level PNS pressure. The model already gathers graph and probability evidence reliably; the system needs a deterministic or verifier-guided step that turns actual tool observations into canonical `operation_plan`, query-specific checks, and answer-support operations.
