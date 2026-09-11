# Editable dissertation figures

| Figure | Editable source | Data or supporting inputs |
| --- | --- | --- |
| 3.1 Auditable construction and evaluation | [Draw.io source](figure1_auditable_compression.drawio) | Native diagram with SVG, PDF and PNG exports |
| 4.1 Evaluation cohorts | [Draw.io source](figure4_1_evaluation_design.drawio), [builder](build_design.py) | [Provenance](figure4_1_provenance.json) |
| 5.1 Compression distribution | [Python source](figure5_1_phase56_compression_source.py) | [Source data](figure5_1_phase56_compression_source_data.csv), [summary](figure5_1_phase56_compression_summary.json) |
| 5.2 Input use and accuracy contrasts | [Python source](figure5_2_evaluation_efficiency_source.py) | [Source data](figure5_2_evaluation_efficiency_source_data.csv), [analysis inputs](figure5_2_inputs/) |

The figure 3.1 files match the final wording in the voice-revised dissertation. The plotted values and intervals come from the saved evaluations. All exports are included, so reading the paper does not require the plotting environment. Use `requirements-figures.txt` from the repository root for the Python figure dependencies. The archived source scripts document their original output locations; set those paths to a new working directory when regenerating exports.
