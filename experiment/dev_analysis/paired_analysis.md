# Four-condition paired comparison

The primary denominator contains all 10 frozen targets. API failures, missing responses and format failures count as incorrect.

| Condition | Correct/total | Strict accuracy | Format valid | API failure/missing | Input tokens (observed) | Output tokens (observed) |
|---|---:|---:|---:|---:|---:|---:|
| ZERO | 8/10 | 80.00% | 10 | 0 | 2425.0 | 22197.0 |
| FULL_COT | 8/10 | 80.00% | 10 | 0 | 72169.0 | 14636.0 |
| HEURISTIC_SHORT | 7/10 | 70.00% | 9 | 0 | 56220.0 | 13583.0 |
| PNS_COT | 8/10 | 80.00% | 9 | 0 | 56218.0 | 12022.0 |

| Comparison | Difference | Paired 95% CI | gain/loss | McNemar p | Holm p | Input saving |
|---|---:|---|---:|---:|---:|---:|
| PNS_COT:FULL_COT | +0.00% | [-30.00%, +30.00%] | 1/1 | 1 | 1 | 22.10% |
| PNS_COT:HEURISTIC_SHORT | +10.00% | [+0.00%, +30.00%] | 1/0 | 1 | 1 | 0.00% |
| PNS_COT:ZERO | +0.00% | [-30.00%, +30.00%] | 1/1 | 1 | 1 | -2218.27% |

CIs are percentile intervals obtained by resampling instance groups with replacement. Missing usage is not counted as zero. Where cost records are incomplete, token totals cover observed calls only. Summed request latency is not GPU wall-clock time.

Non-significance cannot be interpreted as equivalence or non-inferiority. This analysis specified no non-inferiority margin.
