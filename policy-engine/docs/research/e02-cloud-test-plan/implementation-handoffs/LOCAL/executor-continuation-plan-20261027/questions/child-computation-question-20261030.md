# G decision request: new child computation rights under an intact producer grant

**Architecture question only. No implementation or acceptance is requested.**
The current engine enforces a producer's declared `NodeSpec.state_writes` on its
active state view; nested branches may only narrow it. That contract remains intact.
It cannot be silently reinterpreted as publication-only. Three actual R102 planners
hit this guard while invoking existing child computation and consequently lack the
comparison search result. This occurs before the intended target-authorization and
cold-reader controls, and is not a successful comparison proof.

Please select the authority/composition rule:

1. **Introduce a new, separately issued and admitted child-computation capability**
   beyond the intact parent grant. May an appointed engine owner admit a private
   child workspace after independently verifying issuer appointment/currentness,
   exact immutable registered composition and actual child implementations,
   invocation/tenant/attempt, enforced input/read basis, controlled effect envelope,
   resource/cancellation lifecycle and settlement custody? A child NodeSpec is
   evidence of its contract, not the source of these additional rights.
2. **Require an explicit parent composition grant**, derived from authorized
   registered child contents/implementations, with a separately enforced projection
   limited to the parent's original four paths. This is also a new grant/migration;
   neither the current narrow producer view nor its publication scope changes merely
   because a union is written down.
3. **An existing binding rule already decides this.** Identify its finding/invariant,
   appointed owner and applicable scope before implementation follows it.

Conditional recommendation: option1, extending the existing engine invocation,
registry, journal and merge owners rather than creating a second engine. Keep the
four parent paths unchanged: candidate schema, search result, selected Trinity input
and frontier report. Reconcile issuer admission/revocation generation and actual
content-bound child registration before each invocation and final publication.
Rejected or unadmitted input cannot mint a successful settled-workspace receipt.

Private state by itself does not isolate CAS writes/references, RunContext/manifests,
ports, tenant effects or public/export bytes, and conveys no authority. Which owner
must stage, constrain or refuse each effect? The current `state_reads` declaration
and pre-check are advisory; they are not an enforced privacy or read-capability
firewall. If an independently enforced input/read or effect boundary is missing,
should the operation refuse, or may only a precisely limited candidate operation
continue without protected settlement/publication claims? Please specify that plane.

The proposed issuer, complete content-bound composition admission, enforced read/
effect envelope and cross-entry workspace lifecycle are currently absent/unallocated,
with verification_missing and semantic_test_missing. All grant predicates must be
recomputed or independently reconciled, not caller/LLM declarations or shape checks.
A copied model, cleared journal or private completion detacher cannot supply them.
Sync/async/remote, replay, deadline, cancellation, late-effect and byte-publication
controls must demonstrate the same selected rule; a prototype cannot promise parity.

[the detailed source analysis](child-computation-analysis-20261030.md) contains the exact three persisted findings, current source criterion,
reuse/extend alternatives, proposed issuer/freshness/read/effect/settlement contract,
migration footprint and deciding adversarial/removal controls. The pyi is an
unratified design sketch only. Existing causal, calibration, evaluation-safety,
source and authority guards remain unchanged; no scientific or authority result may
be fabricated to make the comparison test pass. No production apply is authorized
before the selected ruling and independent implementation review.


Source analysis is bound to `f44a6455be0313dc1b6258e7fca2518f232c4e43`, tree `ebef4bc1959a4bcf49dd5cc6d3e64a7b6e256a9e`. All 24 named planner/engine inputs remain byte-identical at the documentation delivery. The source-consumer author protocol uses the local label R4; this question does not claim closure of canonical queue row R4 or any finding. The exact executable witness is `_exercise_two_real_completed_ex_ante_sources_and_fresh_planner` in `tests/unit/runtime/http/test_observational_method_runtime.py`.

Local preserved packet: `LOCAL/raw/e02-execution-20261027/repairs/R4-real-comparison-planner-r2/manifest.json@378724db8e5c3da7a5423823384ad8fcb330fbbd627fe19d621b73098b114fd7`. Its `actual-r102-findings.json` and source-input manifest bind the three failures. Independent question review: `LOCAL/raw/e02-execution-20261027/reviews/R4-composite-child-workspace-question-r2-independent/review.md`. G owns the ruling; the author has not implemented the proposed capability.
