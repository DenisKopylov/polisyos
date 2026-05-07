# Runtime HTTP Services Authoring Contract

Owner: `team-runtime`
Applies to: `src/polisyos/runtime/http/services/**`
Last updated: 2026-05-05

## Purpose

This package owns route-adjacent application services for Runtime API v1. It
keeps route handlers thin while preserving HTTP contract semantics.

## Allowed File Categories

- Product Python service modules, adapter subpackages, and local docs.
- No route definitions, OpenAPI snapshots, frontend code, or runtime state.

## Public/Private Boundary

Services are internal to `polisyos.runtime.http`. Public API is the HTTP route
contract and generated OpenAPI, not direct imports from service modules.

## Naming Convention

Use snake_case service names matching route or domain concepts, for example
`control.py`, `lineage.py`, or `artifact_inspector.py`.

## Test Location

Tests live in `tests/unit/runtime/http/` and should assert route behavior or
service contracts through dependency injection.

## Fixture/Data Policy

Use `tests/_data/` or runtime HTTP test fixtures. Do not commit local run
state, CAS payloads, or generated API responses here.

## Generated File Policy

Generated OpenAPI and clients live under `schemas/`, `packages/`, and
`apps/runtime-dashboard/src/api/types.ts`.

## Extension Points

Runtime middleware plugins use `polisyos.runtime_middlewares`. Services are not
plugin hosts.

## Deprecation And Shim Policy

Endpoint behavior changes require API versioning docs and generated-client
compatibility notes before old response shapes are removed.
