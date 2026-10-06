# Causal estimates and identification admission

A successful `CausalEffectReport` preserves its point estimate, interval,
confidence level, and numerical status. These statistics describe an estimator
result. They do not establish that the requested effect is identified for the
current source data, causal graph, estimand, or target population.

`CausalEffectReport.to_uncertainty_envelope()` therefore emits a non-gating
candidate, including when a producer supplies an identified-estimand string,
graph reference, proof reference, or verifier-role label. The interval retains
its statistical semantics; it is not replaced by a manufactured heuristic range.
Existing persisted reports can be reopened without changing their report schema.

When `ConfidencePass` is executed, an offered `causal_envelope_ref` in
`artifacts_index` or the top-level state remains a causal-purpose candidate.
The pass reports the existing `CONFIDENCE_GATE_ELIGIBILITY_LOW` blocker before
attempting to load its bytes. Missing storage, an unresolved or malformed ref,
a false `source="ensemble"` declaration, producer proof labels, a zero minimum
gate ratio, and healthy simulation metrics cannot confer identification
admission. Supported noncausal simulation confidence checks retain their normal
threshold behavior. This contract applies when the workflow executes the
confidence pass; it does not claim that every workflow profile selects that pass.

The current contracts do not supply a positive identification-admission bridge.
`ProofBundle` persistence preserves a producer's structural proof description;
`IdentificationPlanRef` projects an identification plan. Neither constitutes
independent admission merely because it resolves or declares `identified`.
Runtime's existing evaluation-safety verifier supports current execution context,
certificate revisions, and fresh consumer challenges, for attempted-evaluation
safety. That purpose does not prove causal identification. Runtime's Foundry
consumption replay is explicitly descriptive and forbids use for causal
identification. The current code-owned confidence-ledger promotion routes cover
calibration and data trust. Foundry value-evidence projections are intrinsically
`contract_only_nonproduction`, and `CausalEffectReport` owns no such projection
capability. None of these boundaries is promoted into a causal issuer here.

To establish a positive causal authority path, the existing responsible owners
must supply one accepted packet containing:

- The canonical scientific identification owner and independently appointed
  verifier contract, with a current trusted verifier route and revision head.
- Resolved observation/input and graph artifacts, exact source identities, and
  the complete query: outcome, intervention contrast, conditioning, target
  population, environment, and time window. Assumptions must retain their
  observed or declared provenance rather than becoming proof by assertion.
- A verifier result derived from those exact inputs, including any
  non-identification result, validity window, and currentness/revision checks.
- A lower-layer consumer contract that validates the existing Runtime result
  against a fresh consumer challenge and that complete current binding. IR
  cannot import Runtime, and a caller-constructed DTO or boolean is insufficient.

The falsifier is concrete: retain `SUCCESS`, point estimate, CI, and every
positive declaration while removing the issuer or replacing the resolved data,
graph, estimand, target, source, revision, verifier, or challenge. The actual
consumer must remain non-gating. Positive identification authority is **UNRUN**
until that accepted owner packet and bridge exist; no new issuer or seal is
introduced by this slice. An arbitrarily mislabeled artifact presented solely
as a noncausal simulation metric, with no causal consumer role, lies outside
this causal-purpose intake window and establishes no causal authority.

## FIT-01 resource dependency

B54's content-bound nuisance reuse, detached readers, bounded logistic targeting,
and conditional regular-IID EIF tests are unchanged. B56's existing synthetic
pool witness runs all four jobs, repeats, seeds, and folds under the actual
`LocalWorkerPool`, but its registered `StudyNode` is a test fixture. It is not a
current admitted production study.

The common `RunCausalEvaluationNode` requires actual Runtime evaluation-safety
context, current verifier/revision, exact observed source and target identities,
and fresh admission. Its input loader accepts typed panel, RDD, HTE, or graph
contracts and its output consumer expects a canonical report. TMLE currently
declares raw `X`/treatment/outcome slots and returns a treatment-effect mapping.
Closing B56 requires the existing common owner to supply that admitted typed
TMLE input/report bridge and an actual study packet declaring models, all repeats
and seeds, folds, competing jobs, and the existing outer pool budget. A fixture
registry substitution or safety self-attestation cannot replace it. B56 remains
limited; no global CPU/thread scheduler or universal serial-workload claim is
introduced.
