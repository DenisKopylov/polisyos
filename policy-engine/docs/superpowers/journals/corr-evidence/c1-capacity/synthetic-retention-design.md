# Finite synthetic campaign retention diagnostic

This measurement follows positive warm RSS trends in both twelve-input live
throughput traces. It introduces no provider calls and makes no correctness,
calibration, throughput, or week-long resource claim. The scope is the existing
campaign, rich typed extraction, ordinary SDK with `httpx.MockTransport`, and
the repository token estimator. Graph finalization is a separate owner and
measurement.

Before any measured run, emit one dated, content-bound declaration containing
the complete generated ordinal frames of 100 and 1000 inputs. Python streams
every input and hash; independent SQL recursive ordinal generation reconciles
the complete identity set. The temporary in-memory SQLite frame is explicitly
bounded to at most 1000 rows and runs before the first work completion; it is
not evidence of full-campaign memory bounds. The 100 frame is the prefix of
the 1000 frame, with identical input-only construction and response shape.

Use one fresh long-lived actual campaign process per size, concurrency one,
queue capacity two, one attempt per phase. Every source and persisted artifact
is marked synthetic. Screening returns true; extraction returns one typed
constructed causal claim with its actual source span; self-verification
returns an empty verification list. Empty self-verification is not independent
entailment. Mock usage is constructed and is not a provider cost.

The model ID is used only to exercise the existing SDK contract. The only HTTP
client is constructed with a MockTransport; no provider credential is loaded
and no network transport is used. The harness holds a reset ContextVar, three
fixed counters, scalar concurrency counters and a rolling digest. It never
retains request/response lists or corpus work maps. The checkpoint callback
uses durable SQL counts. Full observation membership is reconciled in both
directions, one bounded file at a time, against the database's primary keys;
each filename must agree with its context ID. End reconciliation runs after
the recorded campaign-return timestamp and is named separately.

The existing campaign source projection is extended by the diagnostic,
telemetry, analysis and token-estimator owners. Admission and worker finish
both recompute it. An observed source change invalidates attribution. Both
sizes must use exactly the same declaration/source projection. Source changes
require a new append-only declaration, not a restamp of measured artifacts.

Each profile has sampled operational caps of 1800 wall seconds, 3 GiB summed
worker/descendant RSS and 2 GiB observed native disk writes at 0.25-second
cadence. The two-work SDK smoke took about two seconds including imports and
verification; the conservative cap is an operational limit, not a forecast.
A partial run under a cap is `not_established`, and unsampled short-lived
children remain covered only by the telemetry's stated observation limits.
The native observer is excluded from worker CPU/RSS. Run only in a quiet
window coordinated with the graph resource profiles.

Post-run analysis uses the existing completion-bin and OLS implementation.
It retains every native sample, independently reconciles typed sample values
through SQL, and keeps unreadable samples ambiguous. Three windows are shown:
after first completion while the complete frame is still in progress; after
first completion through actual campaign return, including mandatory replay;
and the entire warm trace through exit. Startup and cleanup cannot supply a
claim of steady memory. The finite positive/negative slopes may still reflect
allocator warm-up; this diagnostic cannot causally identify all retention or
prove provider behavior over a week.

The red-first source-finish and duplicate-observation-body cases reproduced
the existing attribution/identity class before repair. Their corresponding
removals delete actual source/identity comparisons while leaving declarations
and output markers intact. The warm-window removal includes replay/cleanup
and fails the per-completion assertion. No closed A, B, C2 or scientific gate
is changed.

Root owns declaration readback and measured-run release. Commands from the
product root, with the venv first in PATH:

```text
.venv/bin/python -m docs.superpowers.journals.corr-evidence.c1-capacity.synthetic_retention declare docs/superpowers/journals/corr-evidence/c1-capacity/2026-09-09-synthetic-retention-declaration.json
.venv/bin/python -m docs.superpowers.journals.corr-evidence.c1-capacity.synthetic_retention profile docs/superpowers/journals/corr-evidence/c1-capacity/2026-09-09-synthetic-retention-declaration.json 100 .tmp/corr-c1-capacity/synthetic-retention/100
.venv/bin/python -m docs.superpowers.journals.corr-evidence.c1-capacity.synthetic_retention profile docs/superpowers/journals/corr-evidence/c1-capacity/2026-09-09-synthetic-retention-declaration.json 1000 .tmp/corr-c1-capacity/synthetic-retention/1000
```

These displayed commands are a run plan, not execution receipts. All deciding
execution outputs are retained separately by the run harness.
# Pre-run declaration correction, 2026-09-09

The staged whitespace gate returned RC2 for two whitespace-only lines in
`throughput_trace_analysis.py`. Removing those spaces changed a bound source
file before any retention profile. The first dated declaration remains intact
and unexecuted. `2026-09-09-synthetic-retention-declaration-v2.json` supersedes
it with the corrected source projection; both complete ordinal frames and all
operating limits are unchanged. Its declaration hash is
`sha256:c794e4957d37cb73de88696a8c42ae6cca90246086827055c7b1cc1c8b484dfe`.
