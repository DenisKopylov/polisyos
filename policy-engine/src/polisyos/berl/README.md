# polisyos.berl

- Last updated: 2026-10-11

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
- `ExplanationBundleStoreReadError`
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

Persisted bundle consumers use one fixed kind/media/schema contract and preserve the full selected
manifest profile. `persist_explanation_bundle` opts into the store's producer-side
`return_selected_profile` result and refuses a profileless write result; it never reconstructs the
selector from a later default-manifest read. Phase-5 and Runtime warrant-reliability both reload the
exact typed `ExplanationBundleRef`, validate the selected manifest and whole persisted bundle, and
retain the selector in their outputs. When a supported backend throws an unexpected read error, the
loader raises `ExplanationBundleStoreReadError`; Runtime emits a stable failed gate saying object
absence is not established. It does not treat provider errors as absence or use an embedded inline
bundle to rescue the selected ref. This bounded error boundary does not establish production store
availability or live currentness.

A `conditional_observational` bundle is diagnostic-only until a verified law resolver exists;
profile strings, method assumptions, and artifact references are declarations, not law verification.
Unknown or malformed primary and `alternatives_tested` profiles, malformed method-level profiles,
and method-level profiles that disagree with the bundle are refused. The supported `marginal` and
`marginal_interventional` profiles remain available under the current empirical-replacement
contract.

## CAS Persistence and Reader Contract

`persist_explanation_bundle` writes an `ExplanationBundle` through the IR CAS boundary and returns an `ExplanationBundleRef` with the exact selected manifest view. It uses the existing generated schema identifier and `EXPLANATION_BUNDLE_SCHEMA_VERSION`, and fixes the artifact kind to `scientist.explanation_bundle` with `application/json` media. `load_explanation_bundle` requires that typed ref, resolves its selected manifest, checks kind, media, schema name, schema version, and required wire fields, then validates the bundle. It does not infer a feature law from refs or bundle declarations.

`ExplanationOrchestrator.explain` remains an in-memory producer; it does not automatically persist.
The controlled integration witness demonstrates producer → same-write selected-profile CAS ref →
fresh Phase-5 and Runtime readers. Historical valid profileless default refs remain readable when
the default manifest satisfies the fixed BERL contract; newly persisted refs always preserve the
profile selected by their own write. The public `build_quality_scorecard` function belongs to
Runtime quality, not BERL. Known source-snapshot uses include `tools/ops_runners/runtime/canary_evidence.py`
and `tests/_helpers/hds_quality.py` at source snapshot
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; those uses do not establish an orchestrated BERL
scorecard capability. This BERL witness is not a production caller or currentness assertion.
Conditional-law evidence remains `producer_missing`; a self-declared artifact ref does not admit a
conditional profile.
