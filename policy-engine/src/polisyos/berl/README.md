# polisyos.berl

- Last updated: 2026-10-10

Bounded Explanation Reliability Layer package for explanation bundles,
validation thresholds, empirical reliability bounds, and local infidelity
diagnostics.

The package root is an experimental public facade. Treat subpackages as
implementation detail unless they are exported from `polisyos.berl`.

BERL is active Scientist support infrastructure, not a legacy package. Its
current consumers include Scientist validation/preflight and Runtime
warrant-reliability validation, which revalidate explanation-reliability evidence. Do not mark this package
`legacy` or `frozen` unless a future ADR provides a concrete migration target.

## Entry Points

- `ExplanationBundle`
- `ExplanationOrchestrator`
- `ExplanationRequest`
- `persist_explanation_bundle`
- `load_explanation_bundle`
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

## CAS Persistence and Reader Contract

`persist_explanation_bundle` writes an `ExplanationBundle` through the IR CAS boundary and returns an `ExplanationBundleRef` with the exact selected manifest view. It uses the existing generated schema identifier and `EXPLANATION_BUNDLE_SCHEMA_VERSION`, and fixes the artifact kind to `scientist.explanation_bundle` with `application/json` media. `load_explanation_bundle` requires that typed ref, resolves its selected manifest, checks kind, media, schema name, schema version, and required wire fields, then validates the bundle. It does not infer a feature law from refs or bundle declarations.

`ExplanationOrchestrator.explain` remains an in-memory producer; it does not automatically persist. The repository currently has no production call site connecting that method to CAS. The integration test demonstrates the available producer → CAS → fresh CAS reader → existing Phase-5 and Runtime validators route; until a product caller wires that route, its status is `implemented_but_not_orchestrated`. Conditional-law evidence remains `producer_missing`; a self-declared artifact ref does not admit a conditional profile.
