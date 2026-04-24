# ADR-0074: NumPyro for Bayesian SCMs (Phase 15)

## Status

Proposed

## Date

2026-02-28

## Context

Phase 15 introduces Bayesian Structural Causal Models (SCMs) where each mechanism is a
full posterior distribution rather than a point estimate. This enables uncertainty
quantification over counterfactual queries and principled fusion of literature priors
with observational data. PyMC is the dominant Bayesian framework in Python, but its
Aesara/PyTensor compilation overhead adds 30-60 seconds per model and complicates
deployment in containerised batch pipelines. NumPyro, built on JAX, offers
significantly faster compilation and sampling (NUTS on GPU/TPU), a functional API
that composes well with our existing JAX-based ABM bridge, and deterministic seeding
for reproducibility.

## Decision

1. Adopt NumPyro as the Bayesian inference backend for Phase 15 SCMs.
2. Each `Mechanism` in the SCM spec gains an optional `prior_model: NumPyroModel`
   field that defines the probabilistic program for that mechanism.
3. The `gcm_fit` catalog entry will delegate to NumPyro's `MCMC(NUTS(...))` when
   `MechanismSource` is `LITERATURE_PRIOR` or `HYBRID`, and to MLE/MAP for
   `DATA_FITTED` mechanisms (preserving current DoWhy-GCM behaviour).
4. Posterior samples are stored in the `StructuralCausalModelSpec` IR artifact as
   an ArviZ `InferenceData` reference (Zarr-backed in CAS).
5. NumPyro is added as an optional dependency under the `[bayesian]` extra.

## Consequences

### Positive

- 5-20x faster sampling than PyMC on equivalent models (JAX JIT + vectorised chains).
- Functional API avoids global state, making parallel mechanism fitting straightforward.
- ArviZ integration provides convergence diagnostics (R-hat, ESS) out of the box.

### Negative

- JAX installation can be non-trivial on non-CUDA machines (CPU fallback works but
  loses the GPU speedup).

- NumPyro's ecosystem of pre-built distributions is smaller than PyMC's.
- Team must learn JAX-style functional transforms (vmap, jit) for custom mechanisms.
