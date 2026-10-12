# Autotune MethodJob evaluation

`MethodJobBenchmarkEvaluator` connects `SearchLoopRunner` to the canonical
Foundry MethodJob runner. Configure a method FQN, a mapping from method input
slots to candidate fields, and a `PromotionPolicy`. Each evaluation runs the
method against the persisted candidate and suite refs, then stores the method
result and execution evidence refs in the `BenchmarkEvaluation` lineage.

The evaluator admits only the configured primary metric. If the policy declares
a unit, the method output must return the same unit in `metric_units`. Missing,
non-finite, boolean, or unit-mismatched values remain unavailable; the search
objective does not replace them with zero. Sample counts and guardrails affect
promotion only when the method itself returns those fields. MethodJob execution
evidence proves execution reproducibility, not governance admissibility or
method validity.
The optional `search_parameter_bindings` argument maps a SearchSpace dimension to
one dynamic parameter in the registered MethodSignature. The runner requires the
exact current method FQN, version, and ABI; a finite numeric SearchSpace bound
compatible with the parameter type and any declared method bounds; and a candidate
value of that exact type inside the bound. A bound parameter cannot also appear in
the evaluator's fixed `method_params`. The resolved value is written into the actual
MethodJob JobSpec, request basis, and source-work packet. A fresh reader resolves it
again from the persisted candidate and checks the method signature and effective
parameters. These values remain candidate-grade search inputs, not measurements of
causal truth or authority.


`BayesianSourceProfile` records the actual optimizer class and configuration,
proposal source, search-space fingerprint, the caller context frozen at
`SearchLoopRunner` entry, objective identity, effective fitted training corpus,
and effective model profile. Transform-family fields describe the configured
normalization/standardization/likelihood semantics; separate state fingerprints
bind the actual learned normalization bounds, outcome statistics, and likelihood
noise. The native optimizer and injected optimizers have distinct profile kinds.
A profile is warm-start eligible only after a successful native GP acquisition
with an observed fitted basis, supported transform families, captured transform
and noise states, and a nonempty corpus bound to the actual fitted input and
target matrices. Same-run history only needs to match its immutable space,
context, objective, and configured native optimizer header so cold Sobol rows
can reach the first fit. External warm history must pass the full fitted-profile
gate against the receiving context, objective, and search space. An initial
Sobol proposal does not qualify as fitted GP history. The producer keeps an
acquired profile candidate-only when it cannot persist the selected
`SearchGPFitBasis`; descriptive profile fields never substitute for that
artifact. Missing optimizer introspection leaves the corpus unknown rather than
substituting the input history.

The fitted-state fingerprint covers every state-dict parameter and buffer. It accepts
infinite sentinels only for direct registered `lower_bound`/`upper_bound` buffers on
the installed GPyTorch `Interval` API, with the API-valid negative-lower/positive-upper
direction and valid bounds. Those values are encoded explicitly and their constraint
owner type remains bound into the fingerprint; arbitrary infinite values and all NaN
state still refuse.

The transfer bridge persists search histories through CAS and reads canonical
numeric values back into typed records. Warm-start history remains candidate
evidence; it does not establish an external source's authority or eligibility.

An opt-in diagnostic MethodJob can bind method slots directly from a persisted
`fabric.data_snapshot` and its source data artifact. The causal DR/R bootstrap
loop can emit `BootstrapExecutionWork` only when capture is enabled; the
MethodJob observer checks those loop counts against its fresh-read result,
effective draw configuration, source sample, result/evidence refs, and MethodJob
key before persisting a diagnostic-only packet. The search runner reads that
packet again, binds it to the candidate/evaluation/attempt, and carries its ref
in the benchmark evaluation. This is candidate-grade engineering observation;
it does not admit a policy-effect mapping or alter promotion authority.

The packet reader also verifies what the method actually received. Execution
evidence records every dispatched input's full ArtifactRef selector and
selected manifest schema, plus a canonical dtype, shape, and content fingerprint
for each method-state slot. A fresh reader rebuilds those slot values from the
persisted candidate and DataSnapshot sources and rejects changed values even
when their row counts match. It also checks that packet, result, evidence, and
source-manifest lineage retains selected manifest profiles. Unbound diagnostic
packets remain schema 1.2; parameter-bound packets use schema 1.3 and carry the
selected Search MethodJob profile and candidate values. The reader admits 1.2 only
with no Search parameter binding fields. Prior 1.1 diagnostic packets lack the
dispatch binding and remain inadmissible to this stricter reader.

The default policy-runtime L3/L4 backend still does not execute that causal
MethodJob or a scientific draw loop. Its invocation packet remains separate
from bootstrap counts and its fixed CI proxy remains non-authoritative. The
controlled direct-L4 versus L3→L4 witness runs the actual bootstrap loop over
the same bound source, but patches the nuisance and tau fit layers. An
env-gated native witness is prepared: it runs direct L4 (80 draws) and L3→L4
(40 then 80 draws) through the real estimator, MethodJob, and CAS path, then
compares the same-source full-L4 result/config/profile and fresh-read counts.
That native fit remains unrun pending the serialized numerical slot. B157
therefore remains held for the default policy-runtime consumer and native-fit
confirmation. No count is inferred from requested configuration or from the
fixed CI proxy.

This runtime path does not establish B108 fiscal source law. It requires an
exact metric name and, when configured, an exact unit; owner-declared aliases,
sign, measurement time, and conflict policy still need the real fiscal source.
See the local
[V5 search receipt](../../../../../docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/v5-search/receipt.md)
for the selected criteria, tests, and remaining producer boundary.

## Search-profile receipt and receiver boundary

The visible `warm_start_compatibility` profile is descriptive metadata. It does
not admit a history row by itself. The configured generator keeps a one-use
proposal record, and `SearchLoopRunner` consumes it only for the exact built-in
`BayesianCandidateGenerator` + `MethodJobBenchmarkEvaluator` path. The resulting
`BenchmarkEvaluation` stores a candidate-only receipt bound to the proposal
parameters, immutable `JobSpec`, reconstructed method-state fingerprint, method
result/evidence refs, output metric, and evaluation lineage.

Before using a row as source-profile history, the receiver opens a fresh CAS
reader, resolves the typed evaluation and its candidate, suite, MethodResult, and
MethodExecutionEvidence, rebuilds the bound method state from the persisted
inputs, recomputes the `JobKey`, and reconciles the reported metric with the
MethodResult. Full child refs are checked from the persisted evaluation payload
and their selected CAS manifest views; the evaluation manifest itself currently
indexes those child inputs by artifact ID. Missing, malformed, changed, or marker-only receipts remain
ordinary measured history but cannot carry a source profile into transfer or
native-GP warm-start admission. Injected/fallback optimizers remain separately
profiled and are never made native by caller metadata.

This receipt binds search-history mechanics. The MethodExecutionEvidence itself
remains authoritative only for execution reproducibility and explicitly cannot
establish governance admissibility or method validity. A fresh CAS receipt does
not establish fiscal owner sign/unit/alias rules, causal identification, source
authority, or scientific method validity; B108 remains limited and B157 remains
held at those external/source-work boundaries.


A native-GP warm start now also requires an internal `SearchGPFitBasis` CAS
artifact. It records the exact selected benchmark-evaluation refs used by the fit,
the strict search bounds and optimizer configuration, and the resolved
MethodJob/data run profile (including the selected DataSnapshot/data refs and
recomputed source sample count when data slots are used). The receiver verifies
every bound evaluation and MethodJob chain, then reruns the canonical native GP
fit from those CAS-backed observations and compares the complete finite model-state
fingerprint and recomputed profile before admitting rows. The reader never loads or
executes stored model weights. A caller-created profile or a copied fitted-model marker cannot
open that path; direct raw `BayesianOptimizer.warm_start` rejects native-GP
profile claims without the shared verifier handoff. If a selected ref, method or
data identity, quantity, context, configuration, or recomputed fit differs, the
rows remain ordinary measured history and are not used as native-GP warm-start
history.

This fresh recomputation demonstrates a current candidate-grade native-GP view
under the installed code and dependencies. It does not prove the source process's
historical invocation, issuer, scientific calibration, external source authority,
or causal validity. The public `BayesianSourceProfile` payload and exports stay
unchanged; older profile-only records remain readable as measurements but are
not admitted as fitted native-GP history without the new exact basis.
