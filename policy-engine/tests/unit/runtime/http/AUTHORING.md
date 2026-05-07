# Runtime HTTP Test Authoring

## Purpose

Keep runtime HTTP behavior covered without requiring a live server.

## Allowed File Categories

Pytest modules, local helpers, tiny fixtures, and local docs.

## Public/Private Boundary

Prefer service-level public APIs. Private route helpers may be tested for
contract-level edge cases.

## Naming Convention

Use `test_<service_or_route>.py`.

## Test Location

Tests stay in `tests/unit/runtime/http/`.

## Fixture/Data Policy

Use inline payloads or reviewed fixtures under `tests/_data/`.

## Generated File Policy

Generated API clients and OpenAPI outputs are not committed here.

## Extension Points

Middleware extension coverage should name `polisyos.runtime_middlewares`.

## Deprecation And Shim Policy

Deprecated route tests must identify the replacement route or service.
