# ADR-0115: Layered Architecture Enforcement

## Status

Proposed

## Date

2026-04-18

## Context

The desired package layering is documented, but prose is not enough. Current
imports include reverse edges such as `ir -> foundry`, `ir -> scientist`,
`lex -> foundry`, and `foundry -> scientist`.

## Decision

Use import-linter as the primary architecture boundary arbiter:

1. `architecture/imports/contracts.toml` declares layers, forbidden imports, and
   Data Forge domain independence.
2. `polisyos-tools architecture guardrails` delegates import checks to import-linter
   instead of reimplementing graph logic.
3. Temporary exceptions live in `architecture/imports/exceptions.toml` or
   `architecture/shims.toml` with owner and sunset.

## Consequences

- New reverse edges fail in CI.
- Compatibility shims remain possible but must be registered.
- Package boundaries become auditable and reproducible.

## Phase 0 Implementation Note

Repository SOTA Phase 0 validated `architecture/imports/contracts.toml` against
the topology schema on 2026-05-02 and registered the current experimental
scientist-support roots (`polisyos.berl`, `polisyos.calibration`,
`polisyos.ddm_15_7`, and `polisyos.synthetic_world`) in the layer contract. The
dedicated import-linter runner for this TOML remains a report-only normalization
target until its baseline and exceptions are accepted; existing CI import checks
continue to use the legacy `architecture/imports/policy.toml` path.

## Related Decisions

- Extends: ADR-0004 (architecture boundaries import gate), ADR-0061 (import
  gate CI contract), ADR-0096 (canonical product root).

- Related: ADR-0111 (workspace root SOTA contract), ADR-0121 (Python monorepo),
  ADR-0127 (repository hygiene gates).
