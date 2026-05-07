# Shared Test Data Authoring Contract

Owner: `team-quality`
Applies to: `tests/_data/**`
Last updated: 2026-05-05

## Purpose

This subtree owns small, reviewed input fixtures for tests.

## Allowed File Categories

- Small JSON, YAML, TOML, text, pickle compatibility samples, and local docs.
- No production data, raw logs, benchmark reports, or generated test output.

## Public/Private Boundary

Fixtures are test-only. Product source must not import or read this subtree.

## Naming Convention

Use package or domain subdirectories and descriptive lowercase filenames.
Compatibility fixtures should name the format or migration target.

## Test Location

Each fixture must have at least one consumer under `tests/`.

## Fixture/Data Policy

Keep fixtures minimal, deterministic, reviewed, and safe to commit. Redact
anything that resembles production data.

## Generated File Policy

Generated fixtures require a regeneration command in the consuming test or
README. Bulk generated outputs belong under ignored local roots.

## Extension Points

Add new fixture families only with an owner and consuming test path.

## Deprecation And Shim Policy

Remove fixture families when their compatibility shim or migration reader is
deleted.
