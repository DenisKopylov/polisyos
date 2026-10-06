# polisyos.berl

- Last updated: 2026-10-06

Bounded Explanation Reliability Layer package for explanation bundles,
validation thresholds, empirical reliability bounds, and local infidelity
diagnostics.

Persisted `ExplanationBundle` records are checked against the generated wire
profile before DTO validation in both Runtime reliability and Scientist Phase 5.
The current profile is `1.1.0`; the version-pinned `1.0.0` reader remains
available. Construction DTO defaults remain an input convenience and do not
make an incomplete record valid persisted output.

`KernelSHAPAdapter` is an empirical marginal/background-replacement method. A
conditional request uses `ConditionalSHAPAdapter`, which requires an injected
source-law resolver and model-profile verifier. Its available math profiles are
exact affine Gaussian conditioning, exact weighted finite-support strata, and
fixed-N bounded nonlinear Gaussian expectations. These interfaces do not
provide a law producer or verification authority: when one is absent, BERL
returns a diagnostic without marginal fallback, and both persisted consumers
require an injected content verifier before conditional output can pass. BERL
explanations remain prediction attributions, not causal effects.

The package root is an experimental public facade. Treat subpackages as
implementation detail unless they are exported from `polisyos.berl`.

BERL is active Scientist support infrastructure, not a legacy package. Its
current consumer is Scientist validation/preflight code, which uses BERL to
produce and validate explanation-reliability evidence. Do not mark this package
`legacy` or `frozen` unless a future ADR provides a concrete migration target.

## Entry Points

- `ExplanationBundle`
- `ConditionalExplanationEvidence`
- `ConditionalSHAPAdapter`
- `ConditionalLawResolver`
- `ConditionalModelVerifier`
- `AffineModelProfileResolver`
- `BoundedOutputProfileVerifier`
- `ResolvedConditionalLaw`
- `GaussianJointLaw`
- `WeightedFiniteSupportLaw`
- `ExplanationOrchestrator`
- `ExplanationRequest`
- `ConditionalSHAPAdapter`
- `validate_persisted_explanation_bundle`
- `validate_explanation_bundle`
- `summarize_explanation_response`
- `empirical_bernstein_upper_bound`
- `hoeffding_upper_bound`
- `estimate_local_infidelity`
