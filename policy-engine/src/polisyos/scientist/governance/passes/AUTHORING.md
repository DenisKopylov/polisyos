# Governance Passes Authoring Contract

Owner: `team-scientist`
Applies to: `src/polisyos/scientist/governance/passes/**`
Last updated: 2026-05-05

## Purpose

This subtree owns builtin governance pass implementations and shared pass
contracts for Scientist workflows.

## Allowed File Categories

- Product Python pass modules, private helper modules, and local docs.
- No workflow outputs, human-review queues, or generated audit reports.

## Public/Private Boundary

Builtin pass modules are private until registered. External ABI is the
`polisyos.scientist_governance_passes` extension point.

## Naming Convention

Use `<concern>_pass.py` for pass implementations. Shared helpers must either
live in `base.py` or use a private underscore prefix.

## Test Location

Tests live under `tests/unit/scientist/` and should cover both pass-level
behavior and workflow integration when applicable.

## Fixture/Data Policy

Use deterministic in-memory fixtures or `tests/_data/scientist/`. Do not commit
review packets or generated governance reports here.

## Generated File Policy

Governance audit output is local or archive evidence; generated committed
artifacts require generated-artifact registration.

## Extension Points

External passes use `polisyos.scientist_governance_passes` and must include an
offline smoke test plus compatibility metadata.

## Deprecation And Shim Policy

Pass removals require a deprecation window, registry compatibility entry, and
tests proving old saved specs fail with a clear migration error.
