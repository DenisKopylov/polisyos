# ADR-0120: Test Topology Mirror

## Status

Proposed

## Date

2026-04-18

## Context

Tests currently mirror old packages and mix architecture tests, unit tests,
integration tests, performance tests, and fixtures. As package topology changes,
tests must move with the source and become easier to audit.

## Decision

Adopt explicit test topology:

```text
tests/
|-- architecture/
|-- contract/
|-- property/
|-- unit/
|-- integration/
|-- e2e/
|-- golden/
|-- performance/
|-- tools/
|-- lint/
`-- fixtures/
```

`tests/unit/<package>` mirrors `src/polisyos/<package>`. Architecture gates live
under `tests/architecture`; full pipeline behavior lives under `tests/e2e` and
`tests/golden`.

## Consequences

- Source moves have predictable test moves.
- Cross-cutting architecture checks stop living as loose root test files.
- Fixture ownership and refresh policy become explicit.
