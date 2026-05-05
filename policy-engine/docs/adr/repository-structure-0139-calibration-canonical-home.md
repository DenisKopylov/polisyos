# ADR-RSR-0139: Canonical Home for Calibration

## Status

Accepted

## Date

2026-05-03

## Context

Calibration code appears in top-level `calibration/`, `scientist/calibration/`,
and `foundry/calibration/`. Some calibration concepts are shared, while others
may be package-specific.

The inspected Phase 3B tree has no `src/polisyos/scientist/calibration/`
package. Scientist calibration behavior lives in bounded modules under
`scientist/autotune`, `scientist/backtesting`, `scientist/governance`, and
`scientist/search`. Top-level `polisyos.calibration` provides generic
diagnostics and recalibration helpers, while `polisyos.foundry.calibration`
provides Foundry model-parameter calibration and measurement-aware loss.

## Decision

1. `polisyos.calibration` is the canonical shared home for generic calibration
   diagnostics, scoring, validation-report adapters, and recalibration.
2. `polisyos.foundry.calibration` remains a Foundry-specific bounded context
   for model-parameter calibration, measurement-aware loss, Hessian/UQ,
   robust-set selection, and Foundry calibration artifacts.
3. Scientist calibration modules remain Scientist-specific orchestration and
   governance modules; Phase 3B does not create a
   `polisyos.scientist.calibration` package.
4. `polisyos.ddm_15_7.calibration` is handled by ADR-RSR-0135 and becomes
   `polisyos.ddm.calibration`; it is not shared calibration API.
5. Phase 4A records the shared-name decision in
   `architecture/name_registry.toml` and clarifies public-surface ownership.

## Consequences

Future calibration imports become predictable. Shared code stops drifting across
package-specific copies. The package tree may still contain bounded-context
directories named `calibration`, but the shared diagnostics API has a single
canonical home.

## Concrete Impact

- Blueprint:
  `docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md#calibration-canonical-home`.
- Source: `src/polisyos/calibration/**`, `src/polisyos/foundry/calibration/**`,
  and Scientist calibration modules under `src/polisyos/scientist/**`.
- Shared API owner: `team-scientist`.
- Foundry bounded-context owner: `team-foundry`.
- Migration owner: `team-architecture`.
- Target phases: `3B`, `4A`.
- Rollback: revert Phase 4A manifest/name-registry edits and reopen this ADR.

## Related Decisions

- Related: ADR-RSR-0134 Cross-Package Shared Name Registry.
