# Authoring Search Methods

## Purpose

Keep policy-search, promotion, VOI, readiness, benchmark, and strategy code in
the canonical `polisyos.scientist.methods.search` package.

## Allowed File Categories

Runtime modules, typed DTOs, small package-local helpers, README/index docs, and
subpackages for funnels and strategies.

## Public/Private Boundary

Use `polisyos.scientist.methods.search` for first-party imports. Do not
reintroduce `polisyos.scientist.search` compatibility imports.

## Naming Convention

Name modules by the search contract they implement, such as `voi_scheduler.py`,
`promotion_evidence.py`, `benchmark_registry.py`, or `strategies/<kind>.py`.

## Test Location

Existing behavior tests may remain under `tests/unit/scientist/search` until the
test taxonomy moves. New canonical-surface tests should prefer
`tests/unit/scientist/methods/search`.

## Fixture/Data Policy

Use tiny synthetic objectives, lightweight candidates, and local fixtures. Do
not require external services or production data for unit tests.

## Generated File Policy

Generated benchmark reports, promotion bundles, and VOI manifests belong under
build or report artifact directories, not inside this package.

## Extension Points

Strategy extensions live under `strategies/`; funnel extensions live under
`funnel/`. Public extension contracts should be documented in the package README
before they are consumed outside Scientist.

## Deprecation And Shim Policy

The legacy `polisyos.scientist.search` import root is retired. Keep negative
tests for retired imports and migrate any remaining first-party callers to
`polisyos.scientist.methods.search`.
