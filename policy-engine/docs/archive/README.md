# Archive Lifecycle

`docs/archive/**` is an evidence library, not a holding pen for unfinished
documentation.

## Classes

| Path | Class | Commit rule |
| --- | --- | --- |
| `docs/archive/reports/` | Curated audit, verification, ADR-link, release, and operational evidence reports | Commit only reviewed evidence with an owner, date, source command, or source inventory. |
| `docs/archive/reports/benchmarks/` | Promoted benchmark evidence | Commit only reviewed summaries or baselines; raw benchmark output stays ignored under `benchmarks/_reports/`. |
| `docs/archive/specs/` | Frozen historical specs | Retain only when still cited by ADRs, migration docs, or reference docs. |

Historical plans live in `docs/plans/archive/`. Code retained for historical
compatibility lives in `tools/archive/`.

## Promotion Rules

Move material into `docs/archive/**` only after it has a stable evidence role.
New reports must name an owner, creation date, source command or source
inventory, retention expectation, and any redaction notes. Large raw logs,
one-off scratch files, local reports, and generated benchmark bundles remain in
ignored local roots until a reviewer promotes a small summary.
