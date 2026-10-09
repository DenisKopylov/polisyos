# polisyos.berl

- Last updated: 2026-05-03

Bounded Explanation Reliability Layer package for explanation bundles,
validation thresholds, empirical reliability bounds, and local infidelity
diagnostics.

The package root is an experimental public facade. Treat subpackages as
implementation detail unless they are exported from `polisyos.berl`.

BERL is active Scientist support infrastructure, not a legacy package. Its
current consumer is Scientist validation/preflight code, which uses BERL to
produce and validate explanation-reliability evidence. Do not mark this package
`legacy` or `frozen` unless a future ADR provides a concrete migration target.

## Entry Points

- `ExplanationBundle`
- `ExplanationOrchestrator`
- `ExplanationRequest`
- `validate_explanation_bundle`
- `summarize_explanation_response`
- `empirical_bernstein_upper_bound`
- `hoeffding_upper_bound`
- `estimate_local_infidelity`

## Feature-Dependence Limits

`kernel_shap` and `kernel_shap_marginal` currently implement exact Shapley values over an
empirical replacement background. They run only when the request declares `marginal` or
`marginal_interventional`. The `kernel_shap_conditional` identifier and any KernelSHAP request
with the default `conditional_observational` profile return a diagnostic with no attribution:
BERL does not currently admit a verified observed-feature conditional law or sampler. A future
conditional producer must bind its law, source population, feature order, and version before this
adapter can make a conditional claim.

Persisted bundle consumers run the same profile gate before Phase-5 or warrant-reliability
admission. A `conditional_observational` bundle is diagnostic-only until a verified law resolver
exists; profile strings, method assumptions, and artifact references are declarations, not law
verification. Unknown or malformed primary and `alternatives_tested` profiles, malformed
method-level profiles, and method-level profiles that disagree with the bundle are refused. The
supported `marginal` and `marginal_interventional` profiles remain available under the current
empirical-replacement contract.
