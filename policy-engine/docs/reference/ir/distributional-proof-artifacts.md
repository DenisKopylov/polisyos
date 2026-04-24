# Distributional Proof Artifacts

Freshness: 2026-04-19
Owner: `@ir-owners`, `@causal-owners`
Source of truth: `src/polisyos/ir/analytics/distributional.py`, `src/polisyos/scientist/nodes/builtins/simulate/run_distributional_analysis.py`
Research rationale: Stage 5.1 in `docs/archive/plans/CAUSAL_ENGINE_RESEARCH_RESULT_PLAN.md`

## Purpose

`DistributionalProofArtifact` and `CausalAssumptionCard` are the typed proof-carrying
surface for distributional causal claims.

They exist to enforce one conservative rule:

- identified or bounded marginal counterfactual laws do **not** automatically identify an OT coupling;
- coupling-level claims need their own proof channel and may remain `SCENARIO` even when marginals are `IDENTIFIED`;
- `DistributionalEffectBundle.justification` stays weakest-link for backward compatibility, while
  `marginal_justification` and `coupling_justification` preserve the finer split.

## Safety Theorem

PolicyOS treats distributional causal claims as safe only under the following contract:

1. If the proof kernel identifies the marginal post-intervention law `P(Y in A | do(X))`,
   then marginal functionals derived only from that law may be marked `IDENTIFIED`.
2. If the system only has valid outer or sharp bounds for the target functional,
   then the claim may be marked `BOUNDED`, but only when a matching bounds artifact is attached.
3. A concrete OT coupling may be marked `IDENTIFIED` only when the corresponding joint law is
   separately identified. Otherwise it remains `SCENARIO` or, in future theorem families,
   `BOUNDED` via set identification.

## Contracts

`CausalAssumptionCard`

- typed assumption card with `scope`, `status`, `theorem_family`, `assumption_type`, and `testable`
- persisted independently and referenced from bundles and proof artifacts
- replaces flat strings as the machine-readable source of truth; plain-language assumptions remain a legacy projection

`DistributionalProofArtifact`

- wraps a base `ProofBundle`
- optionally links the normalized `EstimandAST`
- records whether the target is a marginal law object such as `cdf` or a `coupling`
- records bound uniformity and coupling status explicitly
- requires `quantile`, `tail_prob`, and `expected_shortfall` targets to cite a
  CDF/survival source through `derived_from_target`; they are not primary proof-kernel targets

- carries typed assumption-card refs

`EventPredicate`

- extends `DistributionRef` so CDF/event queries such as `P(Y <= t | do(X))`
  can be represented directly in the existing `EstimandAST`

- validates that the event variable belongs to the distribution factor variables
- supports half-line, interval, and set events for proof-kernel reductions

## Runtime Integration

`RunDistributionalAnalysisNode` now persists:

- a marginal `DistributionalProofArtifact` when a proof-kernel result exists;
- theorem-backed bounded marginal artifacts for configured Lee monotone-selection
  and Makarov pointwise ITE tail/quantile requests when their required data and
  assumptions are present;

- a coupling `DistributionalProofArtifact` for OT claims, with `scenario_only` status unless a stronger theorem family is supplied;
- typed `CausalAssumptionCard` artifacts referenced from `DistributionalEffectBundle.causal_assumption_refs`.

The runtime enforces one additional invariant:

- `DistributionalJustification.BOUNDED` is invalid unless `DistributionalEffectBundle.distributional_bounds_refs`
  contains at least one bounds artifact for the reported functional and `distributional_proof_ref`
  points to a `DistributionalProofArtifact`.

- theorem-backed bounded marginals do not upgrade the OT coupling by default;
  `coupling_justification` stays `SCENARIO` until a separate coupling proof is attached.
