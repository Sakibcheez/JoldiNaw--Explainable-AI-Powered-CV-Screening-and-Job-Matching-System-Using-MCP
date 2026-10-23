# Evaluation

See `ml/README.md` for reproducible acquisition/audit/split/training commands. Seed=42. Model selection uses validation macro-F1 with C in {0.1,1,10}. Reports include accuracy, per-class precision/recall/F1, macro averages, confusion matrix, split counts, checksums and label ordering. The strict split excludes crossing identity pairs; benchmark and unseen-job splits provide comparison protocols.

Public dataset benchmark results: **not available**. No public dataset or pretrained embedding weights were downloaded for this implementation. Retrieval relevance, citation correctness against independent annotation, human agreement, demographic sensitivity and operational P50/P95 benchmarks require dedicated experiments. They are not inferred from passing software tests.

Automated synthetic tests exercise end-to-end upload → parse → screen → grounded passage → review → export → deletion, negative tenant authorization, MCP protocol/security, conservative matching, skill distinctions and offline training mechanics. The synthetic offline training test calculates actual metrics only to verify the pipeline; those numbers are not benchmark evidence.

Current command outcomes and pending checks are recorded in `IMPLEMENTATION_STATUS.md`.
