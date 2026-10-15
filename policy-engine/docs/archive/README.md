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

## Read retained evidence

- [Report retention and promotion rules](reports/README.md).
- [Report entrypoints](reports/index.md), a curated route rather than a complete inventory.
- [Historical specifications](specs/README.md).
- [Completed and superseded execution plans](../plans/archive/README.md).

A retained record describes its own source and period. Its presence here does
not revalidate the result or establish current runtime readiness.

## Promotion Rules

Move material into `docs/archive/**` only after it has a stable evidence role.
New reports must name an owner, creation date, source command or source
inventory, retention expectation, and any redaction notes. Large raw logs,
one-off scratch files, local reports, and generated benchmark bundles remain in
ignored local roots until a reviewer promotes a small summary.
