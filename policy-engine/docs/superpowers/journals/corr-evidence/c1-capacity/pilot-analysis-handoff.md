# C1 pilot archive and bounded post-run interpretation

The analysis semantics were written before this helper author inspected any live
parsed response. This author has still not inspected those responses or loaded a
credential. Root runs the CLI with the existing actual-key `SafeJsonWriter`.

`pilot_analysis.py` reads the existing checkpoint schema through read-only SQLite
and ordinary JSON. It does not instantiate a campaign or rerun an extractor. The
complete six identities/order, input bytes, frame digest, SQL and file families,
reserved phase identity, hashes, requested/reported model, observation epoch and
own synthetic markers are reconciled. The comparison consumes only identical
input/prompt boolean screening judgments; structural extraction differences carry
no error interpretation. Every report stays candidate-only with authority false.

Costs charge every observed provider reply, including failed replies that the
checkpoint called usage-unknown. Missing provider usage remains unknown and cost
becomes a lower bound. The checkpoint/transport discrepancy is preserved as an
existing C1 phase-accounting limitation; no historical receipt is restamped.
Per-tercile forecasts consume the unchanged `historical-source-cost-target.json`
owner and reconcile its target totals against its complete stratum rows. The
forecast's service seconds are summed provider request latency; startup, queuing,
owner CPU and graph finalization are excluded. Full-pass wall time needs those
separate measurements. No full pass is authorized by this helper.

Primary attempt responses, provider observations, run summaries and strangles are
archived once, with exact byte readback. Held input packets and derived work
records are verified but not copied. Complete terminal storage uses independent
pathlib and os.walk/lstat identity/value sets, including WAL/SHM/locks; missing or
unreadable roots cannot become zero. Allocated blocks and logical lengths are
separate from native write I/O. Warm OLS consumes the complete trace after at least
one completion and makes no memory-complexity or concurrency-knee claim.

## Verification

`pilot-analysis-sourcefreeze-green.json`: five marked stdlib tests pass, 0.066s.
`pilot-analysis-test-identity-census.json`: all test identities independently agree
between AST and unittest enumeration (five pilot tests and one interpretation
test). `pilot-analysis-sourcefreeze-ruff.json`: five exact helper/test paths pass.

Actual remove-property probes all fail with the intended assertion while fixture
markers remain: `pilot-identity-removal.json` (unbound input and independent storage
set admitted), `pilot-unknown-usage-removal.json` (unknown became zero),
`pilot-boolean-removal.json` (string counted as boolean),
`pilot-archive-scan-removal.json` (partial archive appeared before refusal), and
`pilot-memory-removal.json` (positive synthetic trend became zero). Their captured
source hashes preserve the exact earlier helper epoch; the final green includes
subsequent same-input/model/epoch admission and missing-storage-root guards.
The storage-root red is `pilot-storage-absent-red.json`.

## Append-only throughput interpretation correction

`throughput_reanalysis.py` leaves the pinned runner, actual stop rule, selection,
source declaration and original v1 reports unchanged. Its new v2 interpretation
calls the existing stop owner, then requires an actual comparison between two
complete increasing-concurrency levels before crediting a knee. A first-level
error stop remains a stop and establishes no knee. HTTP 429 and the adapter's
`upstream_rate_limit` classification do not establish where the limit originated.
This is the existing P38 measurement-proxy class, corrected in the interpretation
surface rather than by changing an experiment after its calls.

`throughput-knee-reanalysis-red.json` reproduces the old first-level false knee;
`throughput-knee-sourcefreeze-green.json` passes the corrected first-level, actual
plateau and incomplete-level controls. Removing only comparison admission goes
red in `throughput-knee-reanalysis-removal.json`. New v2 outputs retain source
report hashes, original decisions, corrected decisions, unrun levels and a full
terminal storage census. They are post-run corrections, never pre-outcome claims.

## Root invocation

From `policy-engine`, with the venv first in PATH, invoke the module with two
`--binding` execution declarations, paired `--profile` directories, the existing
historical `--target`, and a new evidence `--output` directory. The helper loads no
provider API and performs no model request. It loads the existing key only to scan
and write the archive. The same root-owned scanner wraps deciding command output.

The binding files are `2026-09-09-deepseek-pilot-execution-binding.json` and
`2026-09-09-minimax-pilot-execution-binding.json`; paired profiles are
`deepseek-pilot-profile` and `minimax-pilot-profile` under this directory.
The target is `../c/historical-source-cost-target.json`. The proposed new archive
path is `pilot-primary-archive`. All paths passed to the CLI are relative to the
product root. Separate throughput correction invocation takes each original
`.tmp/corr-c1-capacity/throughput/<model>/throughput-report.json` and a new v2 JSON
path under this evidence directory. Root must review/freeze these helpers before
publishing those outputs.
