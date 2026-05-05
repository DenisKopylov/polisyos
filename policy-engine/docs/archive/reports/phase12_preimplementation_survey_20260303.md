# Phase 12 Pre-Implementation Survey (Simplified TR Scope)

- Generated (UTC): 2026-03-03T00:00:00Z
- Purpose: validate whether Simplified TR scope is sufficient for target policy domains before enabling full strict rollout.
- Linked ADR: `ADR-0089`.

## Survey Structure

- Total questions: 30
- Domains covered: fiscal policy, labor, health, education, energy, migration
- Response scale:
  - `YES/NO` for hard capability checks
  - `LOW/MEDIUM/HIGH` for risk assessments
  - free-text notes for edge cases

## Key Aggregated Findings

- Questions with clear in-scope answer (`YES`): 22/30
- Questions requiring symbolic/full do-calculus escalation: 6/30
- Questions blocked by data availability only: 2/30

## Scope Decision

- Simplified TR remains default for MVP rollout.
- Escalation to symbolic/full path is required when:
  - mediator/front-door structure is detected
  - hard legal constraints introduce non-trivial selection bias
  - proxy exclusion validity fails and no direct target data exists

## Blocking Risks Captured

1. Cross-jurisdiction policy transfer with legal DAG constraints can exceed Simplified TR assumptions.
2. Multi-step proxy chains in low-data contexts need explicit partial identification fallback.
3. Lagged effects require explicit time-stationarity warnings and operator acknowledgment.

## Actioned Follow-ups

1. Keep `transport_solver_mode=simplified` as default.
2. Add explicit symbolic mode selector (`symbolic_y0|symbolic_r|full_auto`).
3. Require `DataGap` + `PartialIdentificationResult` emission for NON_TRANSPORTABLE outcomes.
