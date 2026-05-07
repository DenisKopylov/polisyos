# Scientist Search Shim Authoring Contract

Owner: `team-scientist`
Applies to: `src/polisyos/scientist/search/**`
Last updated: 2026-05-05

## Purpose

This package is a compatibility shim for
`src/polisyos/scientist/methods/search/**`. New implementation work belongs in
the canonical methods package.

## Allowed File Categories

- Shim modules that redirect public imports to `polisyos.scientist.methods.search`.
- Local README/AUTHORING/index docs that explain the migration target.
- No new implementation modules, generated search traces, or benchmark reports.

## Public/Private Boundary

Public imports remain stable for compatibility. Canonical public implementation
lives under `polisyos.scientist.methods.search`.

## Naming Convention

Mirror the canonical module names only when a legacy import path must be kept.
Do not add new names under this first-level shim.

## Test Location

Canonical import and shim tests live in `tests/unit/scientist/methods/`.
Compatibility-era behavior tests may remain in `tests/unit/scientist/search/`.

## Fixture/Data Policy

Use small fixtures under `tests/_data/scientist/` or in test modules. Do not
commit search traces or generated candidate bundles here.

## Generated File Policy

Search reports are local or archive evidence. Committed generated artifacts
must be registered before landing and should reference the canonical methods
package.

## Extension Points

Search strategies are builtin today under
`polisyos.scientist.methods.search.strategies`. Future external strategies
should route through the Scientist extension contract rather than ad hoc dynamic
imports.

## Deprecation And Shim Policy

This shim is time-boxed to sunset on `2027-03-02`. Strategy renames require a
compatibility alias or migration note when saved workflow specs reference the
old name.
