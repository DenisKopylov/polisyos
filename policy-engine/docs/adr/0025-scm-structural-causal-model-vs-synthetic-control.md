# ADR-0025: SCM Terminology Split (Structural Causal Model vs Synthetic Control)

## Status

Accepted

## Date

2026-02-28

## Context

The codebase historically used `scm` in paths and filenames for the Abadie Synthetic Control method.
In the SCM rollout, `SCM` must refer exclusively to **Structural Causal Model** artifacts and workflows.
Keeping Abadie method under `scm` naming creates ambiguity across IR contracts, docs, and implementation phases.

## Decision

1. Reserve term `SCM` for **Structural Causal Model** semantics only.
2. Canonical implementation module for Abadie method is:
   `polisyos.foundry.methods.catalog.causal.synthetic_control`.
3. Keep legacy module `polisyos.foundry.methods.catalog.causal.scm` as a deprecation shim for direct-import compatibility.
4. Keep method registry identity unchanged:
   `causal.inference.synthetic_control@1.0.0`.

## Consequences

### Positive

- Removes semantic collision between Structural Causal Model features and Synthetic Control estimator.
- Reduces confusion in implementation phases where SCM IR artifacts are introduced.
- Preserves runtime behavior and registry compatibility.

### Negative

- Temporary dual-module naming (`synthetic_control` + legacy `scm` shim) increases short-term maintenance surface.
- Legacy star-import behavior from `catalog.causal.scm` is no longer supported by design.

## Compatibility Notes

- Direct imports from legacy path remain supported.
- New code must import from `catalog.causal.synthetic_control`.
