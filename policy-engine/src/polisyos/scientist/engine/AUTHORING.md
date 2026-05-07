# Scientist Engine Shim Authoring

## Purpose

Keep legacy `polisyos.scientist.engine.*` imports working during the Wave 4
orchestration move.

## Allowed File Categories

Python re-export shims, package-local README/AUTHORING docs, and no new
implementation modules.

## Public/Private Boundary

This package is public compatibility surface. Canonical implementation is
private or public according to `polisyos.scientist.orchestration.engine`.

## Naming Convention

Shim filenames must mirror the legacy module name exactly.

## Test Location

Shim tests live under `tests/unit/scientist/methods/` or the orchestration
engine test subtree when behavior belongs to the canonical package.

## Fixture/Data Policy

Do not add fixtures here.

## Generated File Policy

Generated files are not allowed in this shim package.

## Extension Points

None. Engine extension and node registration remain outside this shim package.

## Deprecation And Shim Policy

Every file must point to `polisyos.scientist.orchestration.engine` and retain
sunset metadata consistent with `architecture/shims.toml`.
