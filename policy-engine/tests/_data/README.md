# Shared Test Data

Owner: `team-quality`
Last updated: 2026-05-05

## Purpose

`tests/_data` stores small reviewed input fixtures used by pytest suites across
packages.

## Public API

Only tests and test helpers import or read this subtree. Product code must not
depend on `tests/_data`.

## Internal Layout

| Path | Role |
| --- | --- |
| `checkpoint_compat/` | Pickle/JSON checkpoint compatibility inputs. |
| `data_forge/` | Data Forge test payloads. |
| `fabric/` | Fabric connector and discovery payloads. |
| `lex/` | Lex intervention and corpus fixtures. |
| `performance/` | Small performance baselines. |
| `phase0/` | Phase 0 known input/output examples. |
| `scientist/` | Scientist workflow and research DAG payloads. |
| `transportability/` | Transportability gate fixtures. |

## Extension Points

New fixture families require an owner, a test consumer, and a short note in the
nearest README or fixture catalog.

## Tests

Consumed by the full pytest suite. Fixture policy is checked by repository
quality tests.

## Operability Links

- `tests/README.md`
- `tests/FIXTURE_CATALOG.md`
- `architecture/policies/directory_contracts.toml`

## Known Shims/Deprecations

Compatibility fixtures stay until the corresponding shim or migration reader
sunsets.
