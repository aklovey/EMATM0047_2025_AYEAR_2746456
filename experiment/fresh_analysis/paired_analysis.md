# Four-condition paired comparison

The primary denominator contains all 246 frozen targets. API failures, missing responses and format failures count as incorrect.

| Condition | Correct/total | Strict accuracy | Format valid | API failure/missing | Input tokens (observed) | Output tokens (observed) |
|---|---:|---:|---:|---:|---:|---:|
| ZERO | 187/246 | 76.02% | 240 | 0 | 65759.0 | 823411.0 |
| FULL_COT | 208/246 | 84.55% | 246 | 0 | 1898530.0 | 446995.0 |
| HEURISTIC_SHORT | 208/246 | 84.55% | 243 | 0 | 1545106.0 | 466829.0 |
| PNS_COT | 224/246 | 91.06% | 245 | 0 | 1545034.0 | 397597.0 |

| Comparison | Difference | Paired 95% CI | gain/loss | McNemar p | Holm p | Input saving |
|---|---:|---|---:|---:|---:|---:|
| PNS_COT:FULL_COT | +6.50% | [+2.44%, +10.57%] | 21/5 | 0.00249392 | 0.00498784 | 18.62% |
| PNS_COT:HEURISTIC_SHORT | +6.50% | [+2.03%, +10.98%] | 24/8 | 0.00700037 | 0.00700037 | 0.00% |
| PNS_COT:ZERO | +15.04% | [+10.16%, +20.33%] | 41/4 | 9.33488e-09 | 2.80046e-08 | -2249.54% |

CIs are percentile intervals obtained by resampling instance groups with replacement. Missing usage is not counted as zero. Where cost records are incomplete, token totals cover observed calls only. Summed request latency is not GPU wall-clock time.

Non-significance cannot be interpreted as equivalence or non-inferiority. This analysis specified no non-inferiority margin.
