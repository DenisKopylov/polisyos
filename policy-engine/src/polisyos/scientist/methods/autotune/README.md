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


When an evaluation merges explicit lineage with producer-returned refs, a same-ID edge whose selected manifest profile conflicts with the producer ref is rejected. A generic profileless edge may still be upgraded from a selected producer ref; protected claim evaluations require selected source refs. Successor claim replay also accepts a predecessor only when its policy metadata and selected claim-suite ref match the registry writer shape. Historical profileless pointers remain readable as history but cannot supply a verified protected predecessor.

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

The shared fresh-read verifier for source-profile receipts and fitted-basis
recomputation is owned by [`source_profile_verification.py`](source_profile_verification.py).
`runtime.py` retains compatibility re-exports; `bayesian_generator.py` consumes the
same verifier owner directly, avoiding a runtime-to-producer import cycle.

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
dispatch binding and remain inadmissible to this stricter reader. Finite method request
parameters use a dedicated canonical fingerprint profile across dispatch, packet
persistence, and fresh admission; integer-only requests retain the default canonical
bytes, while NaN and infinities remain refused. The profile records configuration identity
and does not upgrade the request or its outputs beyond candidate-grade evidence. A
real `run_job` CAS fixture verifies the produced dispatch binding and adapter payload;
a strict-default mutation leaves the finite request without dispatch provenance, and
NaN/Inf requests remain unbound or fail with a typed runtime issue. These checks cover
request serialization only and do not establish method validity or authority.

The default policy-runtime L3/L4 backend still does not execute that causal
MethodJob or a scientific draw loop. Its invocation packet remains separate
from bootstrap counts and its fixed CI proxy remains non-authoritative. The
controlled direct-L4 versus L3→L4 witness runs the actual bootstrap loop over
the same bound source, but patches the nuisance and tau fit layers. An
env-gated native witness is prepared: it runs direct L4 (80 draws) and L3→L4
(40 then 80 draws) through the real estimator, MethodJob, and CAS path, then
compares the same-source full-L4 result/config/profile and fresh-read counts.
That direct-L3/L4 native fit remains unrun pending its own confirmation. B157
therefore remains held for the default policy-runtime consumer and native-L3/L4
confirmation. No count is inferred from requested configuration or from the
fixed CI proxy.

A separate configured-native-GP Search × DR MethodJob witness ran through the
real SearchLoopRunner, MethodJob, CAS, and fresh-reader path. Its fixed synthetic
40-row fixture emitted four distinct selected clipping values, evaluations,
MethodResult refs, and work-packet refs; each evaluation used 40 actual bootstrap
draws and remained non-promotable. The persisted DR diagnostics show why its
ATEs form a plateau: three thresholds (.0280024, .159418, and .260552) leave
observed propensity support [.375, .4375] untouched and all return ATE
.9659262, while threshold .450824 clips all propensities and returns .9580069.
The companion test checks the actual clipping fraction against the persisted
propensity support, requires the unclipped plateau, and requires active
clipping to change the measured output; it does not require every distinct
request to produce a unique metric. The fourth row is a real Bayesian
acquisition whose persisted fit basis records the exact previous three
evaluation refs. This is a candidate-grade synthetic execution witness, not a
causal-validity, calibration, authority, or promotion claim.

This runtime path does not establish B108 fiscal source law. It requires an
exact metric name and, when configured, an exact unit; owner-declared aliases,
sign, measurement time, and conflict policy still need the real fiscal source.
See the local
[V5 search receipt](../../../../../docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/v5-search/receipt.md)
for the selected criteria, tests, and remaining producer boundary.

## Search-profile receipt and receiver boundary

For a fitted configured-native acquisition with an exact persisted fit basis,
the SearchLoop evaluation receipt stores a strict SearchGPProposalUncertainty
bound to the emitted candidate, exact MethodJob request/result/evidence,
profile, fit basis, metric, direction, split, and unit. The values are
candidate-grade posterior mean, posterior standard deviation, and acquisition
value at the effective typed candidate parameters. Fit-basis schema v2 keeps
both the actual GP fit rows and the full ordered effective corpus used to
select an adaptive acquisition. A fresh receiver rehydrates both from selected
CAS profiles, refits the GP, and recomputes the three values. Missing,
malformed, non-finite, or mismatched uncertainty is refused for warm-start
admission; historical schema-v1 bases remain readable but cannot be promoted
to the new proposal-evidence path. Injected optimizers and fallbacks do not
receive this typed evidence. These candidate predictions do not establish
policy effects, calibration, law, or external authority.

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

## Champion reference identity and claim-adjudication publication

Promotion binds the complete selected candidate reference, including its selected
manifest profile. Candidate and evaluation manifests carry exactly one selected
`benchmark_suite` input; the evaluation manifest also carries exactly one matching
candidate input. Candidate and evaluation persistence use `input_ref_from_artifact_ref`
to preserve the selected view. The `ChampionPointer` keeps the full suite `ArtifactRef`,
so later comparisons do not infer identity from an artifact ID or suite label. Historical
pointers with an ID-only suite reference remain readable; later promotion is refused
with `champion_suite_basis_unknown` until the suite basis is explicitly reissued.

Claim-adjudication transitions are stored as one `claim-champion-envelope.v1` value
in `champion.json`. Its `pointer` is the existing `ChampionPointer` payload; its
`promotion_basis` hashes that exact pointer payload and records the predecessor. The
hash excludes the envelope, so the binding is non-circular, and one atomic file
replacement leaves a fresh reader with either the old pair or the new pair.
`ChampionRegistry.get` continues to return `ChampionPointer` for diagnostic history.
Historical bare pointers remain readable only with their matching `promotion_basis.json`;
missing or mismatched sidecars retain their refusal behavior. The getter does not establish
the historical CAS sources as protected evidence. A protected successor/replay resolves
the immediate predecessor's suite, candidate, and evaluation refs by their exact selected
profiles, verifies their Core payloads and producer/schema identities, and binds both
manifest lineage edges and the evaluation's candidate ref. Profileless, unavailable, or
content/edge-inconsistent predecessor sources remain history-only and receive a typed
refusal. This is a one-hop check; it does not recursively replay an unbounded history.
Older software that validates `champion.json` as a bare pointer must be upgraded before a
new envelope is written.

This persistence behavior binds candidate-grade registry state and one immediate
predecessor. It does not establish external evaluator authority or resolve whether a
changed suite should re-evaluate an incumbent or begin a separately identified comparison.


### Protected claim-adjudication selected-reference boundary

The claim-specific admission path requires signed `claim-independent-evaluation.v2`
receipts that bind the candidate, evaluation, independent benchmark corpus, observations,
raw execution input, and the exact selected `BenchmarkSuite` ArtifactRef. The suite and
claim candidate writers return their CAS-selected manifest profiles; the candidate and
evaluation manifest edges retain that same suite profile, and the evaluation edge retains
the full candidate profile. Registry promotion and protected replay compare the complete
typed references and validate their producer, schema, kind, and suite identity.

The admitted-result writer records six selected input edges: raw input, candidate,
evaluation, benchmark suite, evaluation receipt, and execution receipt. A fresh Data
Forge reader resolves the complete role set by profile, replays the signed records, and
checks the selected raw input against its extraction and optional retraction source edges
before projecting any row. Those two source edges resolve to the exact extraction and
retraction manifests, including their media type, schema version, and producer version.
The public result DTO remains ID-oriented; its persisted manifest is the selected-view
bridge. Same-ID alternate candidate, suite, or raw-source profiles are refused.

The method execution producer returns selected profiles for result and evidence records;
the evidence manifest and payload bind the complete method-result reference. A measured
work packet returns its selected profile and preserves the candidate, suite, snapshot,
data, result, and evidence views. Evaluation manifests bind each declared selected
method result, evidence, work packet, and Search-GP fit basis. Protected claim producer
calls return a selected evaluation profile automatically. These method artifacts retain
their declared execution or diagnostic purpose and do not acquire governance authority
from profile selection.

Generic loops keep profileless candidate/history records readable; when a producer has a
selected reference, its evaluation edge carries that exact view. For claim-adjudication,
the candidate and suite plus every declared optional producer role require exact selected
profiles. Older ID-only replay calls and v2 receipts lacking `benchmark_suite_ref` remain
history only and receive a typed selected-profile refusal; no profile is inferred from the
current champion. The repository still has no production evaluator receipt-v2 emitter or
appointment issuer, so external issuer authority and full production capability remain
`producer_missing`/`surface_out_of_scope`. Test signer and evaluator fixtures are local
only. Native pytest, external issuer integration, and process-level B117 validation remain
UNRUN; no closure is claimed for those paths.


`SearchLoopRunner` uses the search package's private `lifecycle._SearchLifecycleOwner`
directly for generation, evaluation, run state, and stopping. The public
`SearchController` compatibility facade and the `SearchService` ask/tell
contract remain available through their existing search-package paths; the
private owner is not re-exported by the autotune facade.


## Ordered calibration report metric admission

`CalibrationMetaEvaluator` keeps genuine scalar report2.0 runner/scoring behavior.
A runner may additionally return `(report, selected_report_ref)`, matching the
existing `Calibrator.run_and_persist` result. New typed batch report2.1 metrics
require that selected ref, a store, exact returned/selected content equality, and
`foundry.calibration.replay_ordered_batch_report_projection`. The shared owner
reopens the selected full input/config/graph/plan/registry/parameter sources and
recomputes one final forward, configured loss and weighted metrics. It does not
rerun optimization/Hessian or attest an issuer or external calibration law.

Missing/denied selected bytes or an unavailable numeric/PRNG profile gives
`not_established`; malformed present or contradictory selected metrics
give `mismatch`. The split objective is withheld rather than replacing an absent
measurement with zero or dropping an inconvenient row. Existing evaluation
`status`, notes and metadata retain those limitations, selected refs and the
candidate evidence grade, and the metric-source guardrail blocks promotion. An
unavailable incumbent score is likewise unavailable, not a measured zero.
Successful batch scoring retains `inference_status=unavailable_generic_loss`;
the existing condition-number score is a candidate curvature diagnostic and does
not become inferential calibration. Real selected-producer consumer tests are in
the welfare fixture module; legacy/unselected profile tests remain in the mirrored
autotune test module. Runtime execution and external scientific authority are
separate from these source contracts.


Calibration selected reads share Foundry's `read_calibration_source()` and typed
availability result with welfare and the scalar response reader. A profileless
readable basis is `not_established` and cannot supply aggregate fit scoring;
a duplicate selection or malformed present selected payload is `mismatch`.
Both preserve the candidate-only limitation and prevent promotion. No default
manifest or missing authority is inferred. The same exact report/ref is exercised
through the real welfare and `CalibrationMetaEvaluator` paths in the batch tests.


Selected new batch JSON models are admitted through Core's strict schema-directed
wire reader, not a coercing model constructor. NPZ sources follow their generic CAS
and snapshot owners. The same-report status discriminator collects both actual
welfare and autotune outcomes before assertions, so a mutation cannot hide one
consumer behind the other's early failure. Runtime receipts remain necessary.


Modelled calibration JSON uses the required-model intake. Configuration is admitted
by its canonical producer/reader owner across scalar and batch paths. Raw/reference
reads are explicitly content-only; they cannot silently stand in for typed model
admission. Current caller classification is a source review aid, not a keyword gate.
