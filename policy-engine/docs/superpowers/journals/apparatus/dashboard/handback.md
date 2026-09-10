# Dashboard apparatus contribution

Implementation follows `docs/superpowers/specs/2026-09-10-apparatus-dashboard.md`
at Stage 1 commit `e4b9ce4dfe7ebcafa111582e3da3a8f3bbdba8dd`. Root integrates commits
and owns final cold-station/full-suite receipts. This is a contribution, not a
completion claim. Raw paths below are relative to this directory.

## B1 — unavailable child execution

`persistenceProcessResult.ts` now emits named `PersistenceExecutionUnrunError`
with `UNRUN:` for launch failure, signal/timeout, absent output and malformed JSON.
It preserves the actual cause/stderr and leaves deliberate nonzero JSON refusal
status/body unchanged. No deadlines changed.

| Gate | Exit | Measured duration | Complete output |
| --- | ---: | ---: | --- |
| Exact decoder file before implementation | 1 | Vitest 3.19s | `raw/decoder-unrun-red.log` — four failed, two passed |
| Same decoder file after implementation | 0 | Vitest 5.12s | `raw/decoder-unrun-green.log` — six passed |
| ESLint two changed decoder files | 0 | Tool session elapsed not emitted after redirected async completion | `raw/decoder-lint.log` |

The tests execute real failed, missing and timed-out children. The deliberately
refused JSON envelope remains a separate passing case. Prettier formatted only
the two changed files (`raw/decoder-format.log`, exit 0).

## Live follow-ups

- Python wrong-PATH replay: actual automated-capture and workflow files reproduce
  two missing-jsonschema failures / nineteen assertions, exit 1, Vitest 7.96s,
  `raw/python-consumer-path-red.log`. Capture now visibly says UNRUN; workflow
  still needs the planned completed-result envelope and project interpreter.
- Accessibility exact-file coverage replay reproduces the same 30,000ms timeout,
  exit 1, Vitest 47.31s (`raw/a11y-targeted-baseline.log`). A scratch timing probe
  initially could not import React because the scratch had no dashboard package
  binding (`raw/a11y-timing-probe.log`, exit 1, 7.23s); this is a probe setup
  non-receipt, not an accessibility finding. Bound-dependency probe is ongoing.
