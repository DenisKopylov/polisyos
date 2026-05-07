# Shared Golden Records

Owner: `team-quality`
Last updated: 2026-05-05

## Purpose

`tests/_golden` stores reviewed golden records and snapshots used to detect
behavioral drift.

## Public API

Only tests read this subtree. Product code must not import golden records.

## Internal Layout

| Path | Role |
| --- | --- |
| `contract/` | Contract golden records. |
| `foundry/` | Foundry method/signature golden snapshots. |

## Extension Points

New golden families require an owning package, regeneration instructions, and a
test consumer.

## Tests

Consumed by package tests and repository-quality drift checks.

## Operability Links

- `tests/FIXTURE_CATALOG.md`
- `architecture/directory_contracts.toml`
- `architecture/test_ratchets.toml`

## Known Shims/Deprecations

Golden records tied to compatibility shims stay until the shim sunset.
