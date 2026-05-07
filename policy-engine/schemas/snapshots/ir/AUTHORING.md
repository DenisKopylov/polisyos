# IR Schema Snapshot Authoring Contract

Owner: `team-ir`
Applies to: `schemas/snapshots/ir/**`
Last updated: 2026-05-05

## Purpose

This subtree stores committed IR ABI schema snapshots used by semantic diff
checks and compatibility gates.

## Allowed File Categories

- Generated `*.schema.json` files.
- `_manifest.json` describing snapshot metadata.
- Local README, AUTHORING, and generated index documentation.

## Public/Private Boundary

Snapshots are public compatibility baselines. Source model definitions live in
`src/polisyos/**`; do not add private helper code here.

## Naming Convention

Schema files use `<model-id>.schema.json`. The manifest remains named
`_manifest.json`.

## Test Location

Schema and ABI checks live under `tests/contract/`,
`tests/repo_quality/architecture/test_schema_diff.py`, and IR unit tests under
`tests/unit/ir/`.

## Fixture/Data Policy

These JSON files are committed generated baselines, not test fixtures. Example
payloads belong under `tests/_data/` or `tests/_golden/`.

## Generated File Policy

Never edit snapshots by hand. Regenerate from `policy-engine/` with
`python3 tools/quality/diagnostics/gen_schema.py --models ir`.

## Extension Points

No extension points live here. New schema families are registered through the
schema generator and ABI model registry.

## Deprecation And Shim Policy

Schema removals require an ADR, migration note, and compatibility review before
the baseline is deleted.
