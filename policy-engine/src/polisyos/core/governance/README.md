# Governance (`polisyos.core.governance`)

`core.governance` is the shared validation-policy layer for `scientist` and `lex`. It defines
validation profiles, pass execution context, and the small legal/safety backend stack used during
preflight and runtime governance checks.

## Role in System

- **Depends on:** `core.contracts` for shared issue types and `core.backends` for backend dispatch.
- **Used by:** `scientist` orchestration, `lex` policy checks, and any runtime path that needs shared validation gating.
- **Boundary function:** keeps pass selection and strictness consistent across domains.

## Key Concepts

- **Validation profiles** - `FAST`, `MVP`, and `STRICT` encode which passes run and how blockers short-circuit.
- **Pass context** - `PassContext` carries the IR, registry bundle, run id, and execution state for each validator.
- **Safety/legal checks** - shared passes cover intervention safety, legal policy evaluation, and related gating logic.
- **Backend dispatch** - legal evaluation can be routed through a stub or AST-based backend without `eval`/`exec`.
- **Strategic response** - the profile sets now include `strategic_response` alongside the other governance gates.

## Public API

- `ProfileLevel`
- `ValidationProfile`
- pass modules under `passes/`
- legal backends under `legal/backends/`

## Current State

- Last updated: 2026-04-03
- `ValidationProfile.mvp()` and `ValidationProfile.strict()` both include the `strategic_response` pass.
- The governance package still exposes only the profile types at package level; pass implementations remain module-local.
