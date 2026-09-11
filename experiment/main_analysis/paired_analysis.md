# Four-condition paired comparison

The primary denominator contains all 300 frozen targets. API failures, missing responses and format failures count as incorrect.

| Condition | Correct/total | Strict accuracy | Format valid | API failure/missing | Input tokens (observed) | Output tokens (observed) |
|---|---:|---:|---:|---:|---:|---:|
| ZERO | 254/300 | 84.67% | 293 | 0 | 66982.0 | 543770.0 |
| FULL_COT | 277/300 | 92.33% | 300 | 0 | 2093177.0 | 370815.0 |
| HEURISTIC_SHORT | 272/300 | 90.67% | 297 | 0 | 1670645.0 | 400950.0 |
| PNS_COT | 279/300 | 93.00% | 300 | 0 | 1670526.0 | 370548.0 |

| Comparison | Difference | Paired 95% CI | gain/loss | McNemar p | Holm p | Input saving |
|---|---:|---|---:|---:|---:|---:|
| PNS_COT:FULL_COT | +0.67% | [-2.00%, +3.33%] | 10/8 | 0.814529 | 0.814529 | 20.19% |
| PNS_COT:HEURISTIC_SHORT | +2.33% | [-0.33%, +5.00%] | 12/5 | 0.143463 | 0.286926 | 0.01% |
| PNS_COT:ZERO | +8.33% | [+5.00%, +12.00%] | 28/3 | 4.64916e-06 | 1.39475e-05 | -2393.99% |

CIs are percentile intervals obtained by resampling instance groups with replacement. Missing usage is not counted as zero. Where cost records are incomplete, token totals cover observed calls only. Summed request latency is not GPU wall-clock time.

Non-significance cannot be interpreted as equivalence or non-inferiority. This analysis specified no non-inferiority margin.

Scope correction. Grouping here uses model_id, but the 300 identifiers correspond to only 271 complete-CPT groups. The question-level McNemar tests and intervals above are retained as originally specified diagnostics. Inference accounting for repeated parameters is in main_CPT_sensitivity.md. All 300 questions and their numerical values are retained.
