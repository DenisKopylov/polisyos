# E77 Morris row-count probe attempts

Attempt 1 at the original 100 MiB allowance is preserved in [attempt1](./attempt1/report.md) and ended `UNRUN_RESOURCE_CEILING` after the imported source/backend reached about 166 MiB RSS. Its original report and receipts remain unchanged.

Attempt 2 reused the same candidate archive and 328-byte inputs, with an explicit 384 MiB allowance after measuring the import baseline. It completed two actual native `analyze_sensitivity` calls and confirmed that four valid rows/two trajectories are accepted by a plan capped at two estimated runs; see [`attempt2/report.md`](./attempt2/report.md) and its raw receipts. This result applies to the analysis-input count boundary only.
