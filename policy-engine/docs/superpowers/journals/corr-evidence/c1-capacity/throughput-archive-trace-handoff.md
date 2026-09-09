# Throughput primary archive and completion traces

The archive uses the existing throughput runner's `load_plan` and
`read_level_rows` owners to resolve the admitted complete frame and reconcile
terminal work identities. It preserves nonrecomputable primary response,
provider observation, timing checkpoint, and exact raw telemetry bytes with
the existing credential-aware writer's complete preflight scan. SHM is a
rebuildable index, named separately rather than treated as primary evidence.

The actual declaration/frame integration originally failed with
`KeyError: selected_members`: reading a sealed declaration alone omitted the
frame resolution performed by `load_plan`. This was the same declared
owner-attribution class, not a new scientific rule. The fix extends that
existing owner; no input parser or scientific denominator changes. The red is
`throughput-archive-real-frame-red.json`; the final green is
`throughput-archive-owner-final-baseline.json` (four tests, RC0). Its actual
frozen declaration/12-outcome control reaches the credential preflight and
deliberately refuses before copying any real response bytes. Root owns the
actual credential-scanned archive execution.

The four removal captures `throughput-archive-owner-final-*.json` demonstrate:
`plan_owner` reproduces the actual missing frame; `archive_scan` admits a
marked synthetic secret; `archive_identity` admits an extra provider identity;
`active_window` includes cleanup in the active memory window. Each returns
RC1 for its decisive property. Scan/identity removals run only synthetic
controls so a removed preflight can never copy actual provider bytes.
`throughput-archive-owner-final-census.json` independently reconciles all four
test identities by AST and unittest discovery; `...-ruff.json` records RC0.

The trace analysis reconciles every raw sample through Python and SQLite
JSON1 typed values, retaining ambiguous samples explicitly. Its active warm
window begins after the first observed completion and ends at the existing
checkpoint's last `finished_at`, which is recorded before outcome-file and
SQLite persistence. Completion bins missing from observations are unsampled,
not zeros. Cleanup and the zero-RSS exit sample are separately retained.

Both actual traces have positive warm RSS slopes. Neither the short pilots
nor these twelve-input traces establish stable week-long memory or a
concurrency knee. The first-level error stop remains valid, while the
separate v2 interpretation correctly leaves the knee `not_established`.
Transport status labels do not locate the origin of the error. The two
one-call diagnostics remain outside every original experiment denominator.

The paired pilot's five equal screening booleans provide no correctness
evidence; its one joint extracted response has a structural difference, not
a gold error. Forecasts use charged provider observations including failed
responses and the frozen declaration rate; they are conditional source-work
projections, not a measured full-pass wall time or provider billing proof.
The frozen pilots allow one attempt per phase. These projections hold that
retry policy and the observed phase frequencies fixed; they do not forecast
the prepared two-attempt template, changed retries, or unknown interrupted
usage.

A separately predeclared synthetic campaign retention diagnostic is the next
bounded measurement. It must keep the harness bounded, use the actual SDK and
campaign with a mock HTTP transport, and carry no provider throughput,
calibration, correctness, or week-long safety claim.
