# ADR-0018: Causal Estimator Protocol (Phase 12)

## Status
Proposed

## Context

Phase 12 adds quasi-experimental causal inference methods into Foundry methods (NUMPY backend).
The current architecture already contains:

- `MethodRegistry` + `MethodDispatcher` + `NumpyRunner`
- `UncertaintyEnvelope` IR contract and propagation pipeline
- Scientist method-job execution path and DecisionPacket assembly node

We need a causal contract that is auditable, reproducible, and interoperable with existing
Scientist/Foundry flows.

## Decision

1. Causal methods are implemented as standard Foundry methods under:
   `polisyos.foundry.methods.catalog.causal`.
2. Causal output contract is `polisyos.ir.causal.CausalEffectReport`.
3. `CausalEffectReport` carries:
   - static method metadata trace (`method`, `estimand`, assumptions)
   - dynamic diagnostics (`diagnostics`, placebo outputs, status)
   - optional conversion to `UncertaintyEnvelope` (`to_uncertainty_envelope()`).
4. Determinism tier for causal methods is `DeterminismTier.STATISTICAL` declared at method class
   level and applied by `NumpyRunner`.
5. Structural time-series method is named `StructuralTimeSeries` and uses
   `inference_method="state_space_simulation"` to avoid misleading Bayesian claims when backend is
   MLE/Kalman-based.
6. Scientist default workflow includes `run_causal_evaluation` node as skip-safe step:
   if `state.observational_data_ref` is missing, node returns `status="skip"`.

## Static vs Dynamic Assumptions

- Static assumptions are declared in `MethodMetadata.assumptions` and represent identification
  requirements of the method.
- Dynamic assumption checks are emitted in `CausalEffectReport.diagnostics`.

This split supports both discovery-time method selection and runtime governance decisions.

## Consequences

- Causal evidence is first-class in DecisionPacket (`causal` section + uncertainty bounds).
- Confidence governance pass can inspect causal envelopes via `causal_envelope_ref`.
- Failure modes are explicit (`EstimationStatus`) and avoid fake fallback estimates.
- ABI surface expands with `ir.causal.CausalEffectReport`.

