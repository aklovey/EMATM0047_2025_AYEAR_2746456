# Data records

The experiment archive contains saved requests, final answers, reasoning, execution states, token usage and journal snapshots. Offline scoring uses saved final answers and reference labels. Resource analysis uses the usage fields recorded during execution.

Readable text is a presentation copy of the records. Original text hashes and character offsets identify the execution text, so use the corresponding original records for byte-level reconstruction or token recounting. Final answers, labels, identifiers, seeds, usage and numerical results retain their recorded values.

The historical protocol and report summaries retain their experimental settings and results. Their [source register](../supplement/system_exploration/source_register.json) identifies the version and processing of each file.
