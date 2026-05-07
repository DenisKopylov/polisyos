# Shared Golden Records Authoring Contract

Owner: `team-quality`
Applies to: `tests/_golden/**`
Last updated: 2026-05-05

## Purpose

This subtree owns reviewed golden records and snapshots for drift detection.

## Allowed File Categories

- Small JSON/YAML/TOML golden records, `.gitkeep`, and local docs.
- No raw run output, large snapshots, or production data.

## Public/Private Boundary

Golden records are test-only and must not be read by product source.

## Naming Convention

Use package/domain subdirectories and descriptive filenames. Generated golden
files should include their producer in the consuming test.

## Test Location

Every golden record must be consumed by a test under `tests/`.

## Fixture/Data Policy

Keep records deterministic and reviewable. Store inputs in `tests/_data/` when
they are not expected outputs.

## Generated File Policy

Regeneration commands belong in tests or README docs. Generated bulk output
must stay ignored unless promoted intentionally.

## Extension Points

New golden families require owner review and a documented consumer.

## Deprecation And Shim Policy

Delete golden records with the shim or compatibility reader they protect.
