# ADR-0013: Uncertainty Propagation Pipeline

- Status: Accepted
- Date: 2026-02-07
- Deciders: PolicyOS Core (Foundry + Scientist)
- Supersedes: none
- Related: ADR-0012 (UncertaintyEnvelope IR Contract)

## Context

ADR-0012 introduced a typed `UncertaintyEnvelope`, but the runtime pipeline did not
propagate uncertainty from inputs to simulation outputs.

Observed gaps:

1. `SimulationResult` had no per-metric uncertainty references.
2. Decision packet uncertainty section had only input envelope refs.
3. Governance could not gate on confidence interval width.
4. No reusable propagation module for delta/MC strategies.

This blocked trustworthy decision support: output metrics were emitted as point values
without uncertainty bounds and without policy gates on uncertainty quality.

## Decision

Implement an end-to-end uncertainty propagation pipeline with the following components:

1. New Foundry package `polisyos.foundry.uncertainty` with:

   - `DeltaMethodPropagator` (JAX Jacobian-based linearized propagation)
   - `MonteCarloPropagator` (sampling-based propagation with chunked batching)
   - `AnalyticalPropagator` (linear Normal closed-form helper)
   - `PropagationDispatcher` with robust delta dry-run and automatic fallback to MC
   - covariance utilities and envelope aggregation helpers
2. Extend `SimulationResult` with optional fields:

   - `uncertainty_envelopes: Mapping[str, UncertaintyEnvelopeRef] | None`
   - `propagation_config_ref: ArtifactRef | None`
   - `propagation_report_ref: ArtifactRef | None`
3. Add Scientist built-in node `PropagateUncertaintyNode` between simulation and governance.
4. Update `BuildDecisionPacketNode` to ingest propagated output envelopes and auto-fill
   `uncertainty_bounds` from them.
5. Add governance `ConfidencePass` and enable it in `ValidationProfile.strict()`.

## Key Design Constraints

1. Delta covariance handling:

   - If full covariance rows are available in input envelope metadata, use full covariance.
   - Otherwise fallback to diagonal covariance.
2. JAX differentiability robustness:

   - Auto strategy selection performs dry-run shape/Jacobian validation.
   - On dry-run or delta execution failure, dispatcher falls back to MC.
3. MC memory safety:

   - Sampling/execution is chunked by `mc_batch_size` to avoid OOM on large models.
4. Backward compatibility:

   - `SimulationResult` additions are optional and additive.
   - Existing runs/artifacts without propagated uncertainty remain valid.

## Consequences

### Positive

- Uncertainty becomes part of first-class runtime outputs, not only input metadata.
- Governance can block decisions with overly wide confidence intervals in strict mode.
- Decision packet now carries per-metric propagated bounds for downstream consumers.

### Negative

- Additional runtime cost for propagation, especially under Monte Carlo.
- Additional complexity in workflow and governance configuration.

### Mitigations

- Optional propagation node behavior (safe skip when inputs are absent).
- Auto strategy selection prefers Delta where applicable.
- Tunable MC batch size and sample count.

## Implementation Notes

- `run_governance` now evaluates confidence issues using the active validation profile.
- `preflight.DEFAULT_PIPELINE` includes `ConfidencePass`; pass execution remains controlled
  by profile `pass_ids`.

- Metrics provider initialization was hardened to always pass iterable metric readers to
  OpenTelemetry SDK.

## Rollout

1. Enable by default in workflow (`run_simulation -> propagate_uncertainty -> run_governance`).
2. Start with strict profile confidence thresholds:

   - `uncertainty_max_ci_width_ratio = 0.5`
   - `uncertainty_max_ci_width_abs = 1e6`
   - `uncertainty_min_gate_eligible_ratio = 0.5`
3. Iterate threshold calibration per domain.

## Compliance

- Architecture boundary maintained: propagation logic isolated in Foundry uncertainty module.
- Additive schema evolution only for `SimulationResult`.
- Governance gating integrated via existing validator pass framework.
