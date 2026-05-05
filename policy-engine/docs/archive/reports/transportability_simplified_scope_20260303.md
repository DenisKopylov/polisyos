# Transportability Simplified Scope (`simplified_tr_v2`)

- Generated (UTC): 2026-03-03T00:00:00Z
- Purpose: explicit coverage statement for Phase 12 DoD.

## Covered by `simplified_tr_v2`

1. Selection diagram construction from context deltas + legal/data mismatch S-nodes.
2. Backdoor-style transportability checks with confidence penalties.
3. Direct / Transportable / Non-transportable status classification.
4. Data gap reporting with proxy suggestions.
5. Legal hard/soft constraint integration into feasibility.
6. Partial identification fallback emission path for non-transportable outcomes.
7. Time-stationarity flagging for lagged transport paths.

## Not fully covered by `simplified_tr_v2`

1. Complete symbolic derivations for arbitrary front-door/c-component structures.
2. General do-calculus proof synthesis across all graph classes.
3. Exhaustive algebraic transport formula minimization.
4. Full R-based formula evaluation pipelines when external runtime is unavailable.

## Escalation Policy

- Default: `transport_solver_mode=simplified`
- Escalate when:
  - symbolic/front-door identification is required,
  - legal/data constraints invalidate simplified assumptions,
  - high-stakes decision requires explicit symbolic traceability.
- Escalated mode: `transport_solver_mode=full_auto` with backend order `y0 -> r`.
