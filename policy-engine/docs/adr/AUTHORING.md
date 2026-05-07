# ADR Authoring Contract

Owner: `team-docs`
Applies to: `docs/adr/**`
Last updated: 2026-05-05

## Purpose

This directory stores architecture decision records that are durable enough to
be cited by contracts, plans, gates, release notes, and onboarding material.

## Allowed File Categories

- Decision records in Markdown.
- `README.md`, `index.md`, `index.toml`, and topic indexes generated or
  refreshed by ADR tooling.
- Local templates named `_template.md` or `template.md`.

## Public/Private Boundary

Everything in this directory is public repository documentation. Drafts may be
committed only when they carry explicit status metadata and an owner.

## Naming Convention

Use `NNNN-short-title.md` for numbered ADRs. Repository-structure ADRs may use
`repository-structure-NNNN-short-title.md` when preserving an existing sequence.

## Test Location

ADR metadata and index checks live in
`tests/repo_quality/architecture/docs/` and
`tests/repo_quality/tools/test_repository_best_in_class_phase0_7_inventory.py`.

## Fixture/Data Policy

Do not place raw evidence or bulky audit output here. Put evidence under
`docs/archive/reports/` and link the reviewed summary from the ADR.

## Generated File Policy

`index.md`, `index.toml`, and topic indexes are generated or refreshed by ADR
index tooling. Manual edits must preserve machine-readable fields: status,
topic, package, supersedes, superseded_by, and related.

## Extension Points

ADR topics may define future extension hosts, but executable extension examples
belong under `examples/extensions/` with their own README.

## Deprecation And Shim Policy

Superseded ADRs stay in place. Add `superseded_by` metadata and link the
replacement instead of deleting or renaming historical decisions.
