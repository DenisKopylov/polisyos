# E02-R2 decision record drafts

**Status:** proposals for the principal; none is ratified by this file. Repeating a
lane lean does not make it a principal decision. The principal’s ruling, signer, and
date remain pending for R1, R2, R5, R9, R11, and R13.

**Prepared:** 2026-09-24. **Code inspected:** candidate base
`73c656744f051d9f40667da7f8bc91c61d8b4ebf`. These records describe the proposed
disposition and its evidence. They do not assert that a repair or probe has run.

Each draft follows the visibility fields in
`docs/system-design-decisions/policyos-identity-and-custody-boundary.md` §9.7:
question, options and costs, premises, proposed choice and decision-maker status,
remainder, falsifier, and binding seam. Predicate labels and implementation/property
divergences follow P37 and P38 in
`docs/reference/policy-design-case-failure-patterns.md`.

## R1 — CYC-01 ordinary N4 entry without owner-bound context

**Question.** When an ordinary plain-language request has no established
`CycleSubstrateContext`, may the HTTP composition run N4 candidate computation, and
where must it stop?

**Options and costs.**

1. Require an owner-bound context before any N4 computation. This keeps the N4 input
   contract simple, but the user and candidate-generation path pay for missing owner
   data with a total refusal. New jurisdictions and cases begin with unknowns, so this
   also makes ordinary entry depend on pre-enumerated owner state.
2. Remove the context and binding checks. This restores reachability quickly, but
   runtime and policy consumers would bear the risk of caller-owned or mismatched
   world state being treated as grounded.
3. **Proposed lean:** keep content binding and revalidation when the canonical owner
   context exists; when it does not, permit candidate computation and carry a typed
   `not_established` substrate limitation. Only an existing owner bridge may fill
   that context. The candidate remains ineligible for actions whose authority needs
   that grounding. The runtime owner pays for carrying the limitation through the
   run and its projections; the user keeps access to candidate work.

**Premises.** B01–B03 describe ordinary request entry and the need to carry data/model
context through the actual HTTP → N4 → N5 path; their criterion is a real ordinary
request, not a manually assembled Python context (`PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md`, B01–B03; bundle `CYC-01.md`). S0-K06’s binding application says fail-closed binds protected actions, published claims, and custody facts, while candidate work may carry a declared unknown (`stage0-custody-kernel-ratification.md` §4.3). The identity ruling makes typed absence behavior PolicyOS’s contract, while the external owner remains owner of its function (`policyos-identity-and-custody-boundary.md` §5). The product’s ordinary front door must remain usable as the causal model grows (`policy-design-causal-operating-system-north-star.md` §§5–6).

At the inspected base, `compile_plain_language_recursive_generation_cycle` already
tries `_build_cycle_substrate_context_from_owner` and revalidates a supplied context,
but then raises `cycle_substrate_context_not_established` whenever an explicit N4
port is present without that context. The owner builder only composes registered
substrate entries and an existing WMR; it does not establish arbitrary missing
substrate facts (`runtime/http/services/control/generation_cycle.py`).

**Proposed choice; principal status.** Adopt option 3 as the lane proposal, subject to
principal ruling. Keep the existing content-hash and revalidation checks. Do not
manufacture a WMR, catalog entry, or concrete scope to satisfy N4. An ordinary
request can proceed through candidate computation with an explicit unknown. If that
unknown prevents a valid N5 world simulation, preserve a typed pending/limited N5
result rather than claim a simulation. Promotion, publication, protected modes, and
the S8 authority grade remain gated on the owner evidence they require. The lane has
not made this decision for the principal.

**P37 — gate predicates at admission.**

- The raw request is caller supplied and supports candidate generation only; it is
  not a predicate establishing policy authority.
- A present `CycleSubstrateContext` is admitted only after its problem binding,
  registered-entry projection, WMR identity, and content hashes are recomputed by
  the typed context validator (`recomputed`).
- If the owner context is absent, its scope is `not_established`; the declaration of
  absence stays a limitation and cannot satisfy an authority gate.
- Any later authority decision must use the relevant existing owner verifier and
  current epoch evidence (`independently_reconciled`). A missing or stale verifier
  result is `not_established` and blocks that authority action.

**P38 — property and divergence.** Property: an ordinary request can yield candidate
work without owner context, while unknown substrate facts cannot support an
authority-grade output. Current implementation: the HTTP compiler raises whenever
an explicit `root_n4_generation_port` meets a missing context
(`runtime/http/services/control/generation_cycle.py::compile_plain_language_recursive_generation_cycle`).
Divergent case: a plain request has no catalog-owned context but has the configured
N4 producer; the candidate computation is refused even though its output could be
marked limited. The converse probe must also hold: a candidate carrying this
limitation cannot pass promotion or publication with the limitation removed only
from a display projection.

**Remainder.** No decision here grants authority to guess a jurisdiction, create a
second world store, or convert an LLM candidate into evidence. Where valid owner
data is absent, the next step is an owner/data record or the smallest missing owner
capability, not a synthetic context. The system continues to own the absence
contract and the authority gate.

**Remainder standing and signatory.** An absent or unmatched substrate fact has
standing `not_established`; that does not put the ordinary request or candidate
capability on hold. The registered source owner signs any source fact it supplies.
If a particular source owner is not registered, that fact remains
`unallocated/not_established` until the source boundary names its signer; this draft
does not make that appointment. The HTTP/runtime composition owns carrying the
typed unknown and gating authority, not signing source facts. Denis, as principal,
remains the pending signatory for this proposed candidate/authority boundary; this
draft is not ratification.

**Falsifier / revisit trigger.** Reopen if a served ordinary request cannot produce
candidate work when the context is absent, or if a candidate with `not_established`
substrate evidence can reach N5 as a grounded simulation, promotion, publication, or
S8 authority output. The acceptance witness is the plain-language front door and
NL-job tenant-scope path; the authority control is a negative promotion/publication
case with the same absent context. Neither witness is claimed as run here.

**Where it binds.** The HTTP composition at
`runtime/http/services/control/generation_cycle.py::compile_plain_language_recursive_generation_cycle`
and `_build_cycle_substrate_context_from_owner`; `CycleSubstrateContext` validation
at `runtime/quality/cycle_substrate.py`; the recursive N4/N5 orchestration and
downstream promotion/S8 authority gates. This proposal does not alter the external
catalog or WMR owners.

**Pattern pass.** P04/P05/P10/P15. The observed defect is an authority prerequisite
leaking into candidate reachability; the target is one explicit typed limitation
that survives all projections. The owner builder exists, but the ordinary missing
context route remains `implemented_but_not_orchestrated`; acceptance requires the
candidate producer to run and an authority consumer to reject the unresolved case.

## R2 — CYC-05 strangle proof, deployment identity, and historical replay

**Question.** How should a persisted N6 run retain the claim that production does
not route through `run_fixture`, without making historical replay depend on a live
source checkout or treating current-source drift as proof that history is invalid?

**Options and costs.**

1. Re-hash all Python files under `src/polisyos` at every consumer replay. The
   implementation uses `source_root.rglob('*.py')`; non-Python files are outside
   that denominator. This is simple to understand, but every consumer and packaged
   deployment pays for live source access; unrelated Python edits can invalidate
   old runs.
2. Remove the strangle receipt and stop checking the production-path property. This
   removes false staleness, but the runtime and public projections lose evidence for
   a safety-relevant orchestration boundary.
3. **Proposed lean:** keep the complete source/deployment census as a source/deploy-
   time tooling gate and extend the existing canonical identity owner; do not create
   a second identity calculation. The owner’s full identity comprises the baseline
   of `pyproject.toml`, `uv.lock`, every file in the resolved authority import
   closure, and the Python runtime manifest, combined with the authority import
   closure and loaded-code manifest. Today this is computed inside private
   confidence-ledger functions; no public packaged API exposes canonical deployment
   currentness to `GenerationCycleRun` consumers. Extend that owner and wire a
   production validation bridge to emit a typed currentness result. Add it in
   `GenerationCycleRun` v3, with explicit byte-preserving v1 and v2 historical
   projections that exclude v3 fields. Historical replay then validates the saved
   projection and receipt without today’s checkout; current admission separately
   compares the recorded identity to the current admitted identity as a typed epoch
   fact. The added costs are a public owner API, production bridge, schema migration,
   and proof that both old projections still replay exactly.

**Premises.** B30’s audit card calls for a controlled source/build slice, distinct
missing-source, parse-error, and forbidden-caller states, and reuse for an unchanged
deployment (`source/B_r19_original.md`, B30; bundle `CYC-05.md`). B29 separately
requires a normal stop to retain its epistemic meaning; a structural receipt must not
turn a bounded successful run into abstention (`B29`). The ratified identity rule
requires historical provability and makes epochs/staleness the way current claims
remain honest (`policyos-identity-and-custody-boundary.md` §§1, 4). The canonical
deployment identity is broader than the loaded-code manifest and lock file alone:
the confidence-ledger owner includes `pyproject.toml`, `uv.lock`, source files in
the resolved authority import closure, Python runtime identity, the authority
import closure, and the loaded-code manifest
(`runtime/quality/confidence_ledger.py::_deployment_relative_paths_from_closure`,
`_deployment_baseline`, `_deployment_identity_from_baseline`).
`_admit_loaded_runtime` is private and takes a repository root; the run validator
has no public packaged currentness API from that owner. A source checkout’s mere
presence at validation time is not deployment identity. The register’s
`merged-lanes-need-a-reissue-path-neither-lane-declared` row remains open on its
engineering reissue path; this proposal does not authorize a reissue or restamp.

At the inspected base, `StrangleReceipt` documents that it does not establish build
or deployment identity and admits that alias/dynamic-call completeness is not
established. It computes a source hash over all Python files under `src/polisyos`
using `source_root.rglob('*.py')`; non-Python files are outside that denominator.
`verify_current` and `validate_generation_cycle_run` require a live `repo_root` and
compare those current Python files during validation
(`runtime/quality/generation_cycle.py`).
`GenerationCycleRun` currently accepts v1 and v2; extending it requires v3 plus
historical projections for both older versions. The confidence ledger already
computes the canonical loaded-runtime identity internally, but this code path does
not make that identity a public run-currentness capability or bridge it into the
generation-cycle consumers.

**Proposed choice; principal status.** Adopt option 3 as the lane proposal, subject to
principal ruling. The source/deploy-time gate owns the census. Extend the canonical
identity owner to publish a typed identity/currentness contract from its existing
full inputs, and connect that contract through a production bridge to generation-
cycle validation. Do not compute a parallel identity in `generation_cycle.py`.
Persist new identity/currentness evidence in `GenerationCycleRun` v3. Preserve both
v1 and v2 as byte-exact historical projections excluding all v3-only fields; legacy
runs without a recorded canonical identity may replay historically but have
currentness `not_established`. Historical validation uses persisted bytes, version,
and receipt, not today’s source tree. The separate typed epoch/currentness result
compares a v3 run’s recorded identity with the identity admitted by the current
runtime. A historically valid run can therefore be stale for current authority
while remaining valid evidence of what happened. This extends an existing private
identity owner; it does not assert that the public API or consumer bridge already
exists.

**P37 — gate predicates at admission.**

- The strangle census’s declared file/deployment denominator must be derived from
  the actual shipped source/build inputs (`recomputed`); a producer’s claimed count
  or a search-index result is insufficient (`consumer_asserted`).
- The canonical identity is recomputed by the confidence-ledger owner from the
  project and lock files, authority-import-closure files, Python runtime manifest,
  authority import closure, and loaded-code manifest. The field-level predicate is
  `recomputed`; exposing it to packaged run consumers through a typed public API and
  production bridge is currently `bridge_missing`. Until that bridge is wired,
  generation-cycle currentness is `not_established` and yields no current positive.
- Historical content, schema version, and receipt binding are recomputed from the
  persisted artifact (`recomputed`). The v3 serializer must preserve explicit v1
  and v2 projections byte-exactly. Historical validity does not imply currentness.
- Direct AST call edges can be recomputed, but reflective/aliased entry paths remain
  `not_established` unless the deployment census independently covers them. That
  limitation must be frozen in the receipt; it cannot be converted to “no callers”
  by a declared allowlist.

**P38 — property and divergence.** Property: the deployed production N6 path does
not route through `run_fixture`, and a persisted run remains replayable as historical
evidence independent of a live source checkout. Current implementation: the
consumer calls `StrangleReceipt.verify_current`, which hashes all Python files
under `src/polisyos` via `source_root.rglob('*.py')`; non-Python files are outside
that denominator, and the method requires `repo_root`. No public packaged
currentness bridge from the canonical identity owner is wired to `GenerationCycleRun`.
Divergent case:
a packaged historical run with its persisted receipt but no live checkout cannot be
replayed by the current validator; it raises
`generation_cycle_strangle_receipt_currentness_not_established` even though the
question is historical validity. A comment-only edit to
`lex/simulator/report.py` changes the broad source receipt, but
whether that file is in the canonical authority import closure and therefore
changes deployment identity is unmeasured. That example does not establish that the
edit is unrelated to deployment identity or that the identity remains fixed. A
second boundary case is a reflective `getattr` route to `run_fixture`: a direct
AST-name census can miss the forbidden path while still reporting its enumerated
source set clean. The future gate must either distinguish that path or preserve it
as a bounded `not_established` limitation; it may not claim complete call-graph
proof from the direct census alone.

**Remainder.** This does not authorize changing the canonical deployment identity,
trust-posture pins, or GY promotion-contract epochs on merge. Any required reissue
needs its own authorized transition and readback. It also does not decide that all
dynamic Python dispatch can be statically proven; unresolved dispatch stays an
explicit limitation and cannot support a stronger authority grade. The full identity
includes the project/lock baseline, Python runtime, authority import closure, and
loaded-code manifest; it is not a manifest-plus-lock-only binding. This proposal
does not claim currentness is already available to packaged run consumers, nor that
the `lex/simulator/report.py` comment probe leaves canonical identity unchanged.

**Remainder standing and signatory.** Dynamic/reflective caller completeness is
`not_established`; no complete-census verifier or signer is identified by this
record, so the census may not support an authority claim for those paths. The
source/deployment census is the proposed mechanism. The existing identity
calculation belongs to the confidence-ledger owner, but its deployment identity
helper is private and no public packaged run-currentness API or production bridge
is identified. Extending that owner is proposed; currentness stays
`not_established` until the typed owner API and bridge exist. An engineering owner
for the census and any stronger dynamic-dispatch proof remains unallocated until
assigned.
For the merged-epoch register row, the standing rule is already ruled: a transition
must be declared from the merge base. `runtime/quality` owns the fifth transition
implementation and its stated premise; the row closes only after the authorized
reissue succeeds and readback matches. This draft neither reopens that ruling nor
authorizes a restamp (`docs/plans/active/DEBT-REGISTER.md`,
`merged-lanes-need-a-reissue-path-neither-lane-declared`, standing decision ruled
2026-09-10). Denis remains the pending principal signatory for the proposed
historical/currentness boundary.

**Falsifier / revisit trigger.** Reopen if a packaged historical run with no
checkout cannot replay from its stored v1/v2 projection or v3 bytes/receipt, or if
the v3 public currentness bridge accepts a changed canonical identity as current
without an epoch status change. The identity-drift probe must alter a proved input
to the canonical identity; the comment-only `lex/simulator/report.py` example is
not such a probe until its import-closure membership and effect are measured. The
census removal probe keeps receipt markers but removes the actual source/deploy
check; it must fail. These probes are acceptance requirements, not results recorded
by this draft.

**Where it binds.** Source/deploy-time tooling gate; canonical identity owner and
full input composition in `runtime/quality/confidence_ledger.py::_admit_loaded_runtime`,
`_deployment_baseline`, and `_deployment_identity_from_baseline`; the proposed
public owner API and production bridge into generation-cycle consumers; and
historical/current projections at `runtime/quality/generation_cycle.py::StrangleReceipt`,
`GenerationCycleRun`, and `validate_generation_cycle_run`. The run schema moves to
v3 with byte-exact v1/v2 projections. Recursive-leaf validation and public OWR
projection consume the typed status; currentness is an epoch question at admission,
not an incidental source-tree scan.

**Pattern pass.** P07/P08/P29/P35/P37/P38/P41. Existing anti-patterns are runtime
recomputation over an overbroad source denominator and a marker receipt whose
deployment identity is explicitly absent. Target: one complete source/deploy census,
the existing canonical identity owner extended into a typed public run-currentness
contract, and separate historical/current statuses. The private identity calculation
and current source check exist; the public packaged generation-cycle bridge is
`bridge_missing`, and source-check coverage for dynamic calls is `not_established`.
Acceptance is byte-exact v1/v2/v3 historical replay plus a currentness falsifier
against a changed canonical identity. The `lex/simulator/report.py` comment probe
remains unmeasured for import-closure effect.

## R5 — EvalSafety context denominator for non-simulation leaves

**Question.** Which recursive leaf modes require a current EvalSafety context for
every leaf, and may another context type or a custom controller factory substitute
for that requirement?

**Options and costs.**

1. Keep the existing conditional denominator check. The recursive controller stays
   permissive, but callers and users bear a path-dependent safety boundary; a custom
   factory or an empty map can bypass the check.
2. Require an EvalSafety context for every mode, including `simulate_only`. This is
   straightforward, but ordinary pure computation pays an authority-band cost and
   loses the inexpensive candidate path required by S0-K06.
3. **Proposed lean:** every leaf in `retrospective`, `measurement_audit`,
   `sandbox_pilot`, `field_pilot`, or `deployment` must have a canonical, current
   EvalSafety context verified for that exact leaf. The complete context-key set
   must equal the recomputed leaf set even when it is empty. Only `simulate_only`
   may omit EvalSafety, and that choice is declared as candidate computation; it
   cannot authorize promotion, publication, or deployment. Runtime and EvalSafety
   owners pay for a single structural guard and current-head verification.

**Premises.** The public mode vocabulary distinguishes `simulate_only` from
`retrospective`, `measurement_audit`, `sandbox_pilot`, `field_pilot`, and `deployment`
(`pdc/_impl/evaluation_safety.py::EvaluationMode`). The evaluation-safety consumer
verifier already recomputes bindings, validity windows, evidence heads, and the
unique revision head (`runtime/quality/evaluation_safety.py::verify_evaluation_safety_consumer_admission`).
The recursive controller currently checks contexts only under
`if self._cycle_controller_factory is None`, and only checks the denominator when
`evaluation_contexts_by_node` is truthy; it also permits a nonempty substrate-context
map to satisfy the “context established” branch (`runtime/quality/recursive_generation_cycle.py`).
S0-K06 keeps cheap candidate computation open while binding authority actions to
verified scope; ADR-0179 principle 4 calls over-refusal a defect
(`docs/adr/0179-correspondence-vocabularies-meaning-principles-first-profiles-open.md`).

**Proposed choice; principal status.** Adopt option 3 as the lane proposal, subject
to principal ruling. Use the already-owned EvalSafety verifier, not a new parallel
gate. Compute the recursive leaf set from the validated graph, require exact
denominator equality for every non-simulation mode on every controller path, and
refuse authority-grade work if any leaf’s current safety head is absent, stale,
mismatched, or unresolved. A `CycleSubstrateContext` is not an EvalSafety context.
Pure `simulate_only` retains candidate computation with its mode declared; that does
not create an exception for any other mode.

**P37 — gate predicates at admission.**

- Leaf membership is recomputed from the validated recursive graph (`recomputed`).
- Canonical mode is taken from the verified mode-resolution owner (`recomputed`);
  the request’s mode token alone is `consumer_asserted` and cannot downgrade a
  non-simulation request.
- Context-map completeness is the equality of the exact context keys and graph leaf
  refs, including the empty-map case (`recomputed`).
- A supplied `EvaluationExecutionContext` is only caller input until the EvalSafety
  owner verifies its exact binding, valid time, current evidence, and revision head
  (`independently_reconciled`). Missing verification is `not_established` and blocks
  non-simulation execution.
- Substrate context may support candidate/world binding but never stands in for
  EvalSafety (`not_established` for the safety predicate).

**P38 — property and divergence.** Property: no non-simulation recursive leaf runs
without its own current EvalSafety head, regardless of factory or context map shape.
Current implementation: the denominator guard is inside the no-factory branch and
skips equality for an empty context mapping. Divergent case: a graph with one leaf
and `evaluation_contexts_by_node={}` does not raise the denominator mismatch; a
controller factory also bypasses the guard. The property fails while the present
predicate can be green.

**Remainder.** This does not make a `simulate_only` result safe for promotion or
publication. Its authority remains separately gated. Any future relaxation for
ordinary candidate computation applies only to the typed `simulate_only` mode and
must remain visible in the run record.

**Remainder standing and signatory.** Missing, stale, or mismatched EvalSafety
evidence has standing `not_established` and blocks every non-simulation mode. The
existing consumer-admission verifier in
`runtime/quality/evaluation_safety.py` owns the software check; its module explicitly
does not make an institutional appointment, and this record names no external
evidence signer. The recursive runtime owns enforcing the denominator, but cannot
sign EvalSafety evidence. Denis remains the pending principal signatory for this
proposed mode boundary; any later expansion of the `simulate_only` exception needs
a separate principal decision.

**Falsifier / revisit trigger.** Reopen if any non-simulation leaf proceeds with a
missing, empty, incomplete, stale, or foreign EvalSafety context; repeat with a
custom controller factory. The positive control is an ordinary `simulate_only`
candidate that proceeds without an EvalSafety certificate but cannot cross an
authority gate. These are required tests; none is claimed as run here.

**Where it binds.** Structural check in
`runtime/quality/recursive_generation_cycle.py::RecursiveGenerationCycleController.run`;
mode, context currentness, and revision-head admission in
`runtime/quality/evaluation_safety.py::verify_evaluation_safety_consumer_admission`;
promotion/publication consumers retain their own authority checks.

**Pattern pass.** P04/P05/P37/P38. The existing failure is a conditional guard whose
implementation checks a proxy for “context provided” instead of exact current
coverage. Target: graph-derived denominator plus the canonical current-head owner.
The verifier exists; structural coverage over all controller paths is
`verification_missing` until the empty-map/factory falsifiers and the
`simulate_only` control pass.

## R9 — CAS supports several honest typed views of one blob

**Question.** How can the CAS deduplicate identical bytes while representing two
different, truthful typed profiles for those bytes?

**Options and costs.**

1. Keep one first-writer profile and return a bounded, typed profile-conflict
   refusal when a caller asks for a different view. This preserves honest refs and
   avoids caller-specific exceptions, but callers that use identical payload bytes
   for distinct legitimate views pay with a refusal until the store can represent
   that view. Existing simulation, deployment, and promotion consumers remain
   limited at that boundary.
2. Return a ref for the newly requested kind while leaving the first manifest in
   place. This avoids immediate caller failures, but the returned ref lies about
   the persisted profile and pushes integrity failures onto every later reader.
3. **Proposed lean:** preserve immutable bytes and physical content deduplication,
   while adding independently persisted, typed view records/manifests that bind a
   view identity to the content hash and full profile. A returned view ref resolves
   only when its own persisted profile exists and verifies. Implement the contract
   through the common `ArtifactStore` owner for filesystem, S3, GCS, and caching
   backends. CAS and API owners pay for additional metadata, versioned references,
   import/export and signature handling; callers do not need envelope hacks or
   duplicate payloads.

**Premises.** B150’s distinguishing case is identical bytes under profile A and
profile B: the first manifest is preserved, but the second `ArtifactRef` advertises
profile B. Its source recommendation requires that a ref match actual persisted
semantics and preserve byte deduplication (`source/B_r19_original.md`, B150; bundle
`CAS-01.md`). The class lean preserves the honesty E02 bought: never return a ref
whose profile the store does not hold. At the inspected base, `ArtifactRef` holds
content ID, kind, and media type, while `ArtifactManifest` is a single sidecar per
content-addressed blob; `FileSystemCAS._put_blob_and_manifest_once` validates the
one existing profile and refuses a mismatch (`core/artifacts/manifest.py`,
`core/artifacts/store.py`). The store factory exposes filesystem, S3, GCS, and cached
variants (`core/artifacts/backends/config.py`).

**Proposed choice; principal status.** Adopt option 3 as the lane proposal, subject
to principal ruling. Keep blob identity as the hash of exact bytes. Give each typed
view its own stable identity and immutable profile binding; do not make kind or
inputs mutable on the blob’s first manifest. Resolve and verify the view through
the runtime-supplied store. A profile that is absent, malformed, or mismatched
returns a typed refusal. Preserve historical single-profile refs by versioned
readers; any added hash-bound view fields require a schema/version bump and
historical projection rules.

**P37 — gate predicates at admission.**

- Blob identity is SHA-256 over the exact persisted bytes (`recomputed`).
- A typed view exists only if the store resolves its immutable view record and
  recomputes its binding to that blob (`recomputed`). The requested kind/schema/
  inputs are consumer assertions (`consumer_asserted`); persisted producer and
  authority semantics are `not_established` by the CAS alone and require the
  relevant owner contract before carrying authority.
- Where a view carries authority, signature, tenant, event, and input closure must
  be resolved and checked through the existing owner/verifier (`independently_reconciled`).
  A missing view or verifier is `not_established` and cannot receive a positive
  authority result.
- Equal bytes never imply equal lineage or provenance. Any absent lineage relation
  remains `not_established` rather than inferred from the shared blob hash.

**P38 — property and divergence.** Property: content can be reused across multiple
typed meanings only when each meaning is explicitly stored and verifiable. Current
implementation: a single content-addressed manifest is the semantic profile, and a
conflicting profile raises. That refusal preserves honesty but rejects a valid
second view; a workaround that returns the new ref without a second persisted view
would diverge in the opposite direction by claiming a profile the store lacks. The
distinguishing case is one byte-identical payload requested once as profile A and
once as profile B: both views must resolve to their own manifests while both still
resolve to the same blob bytes.

**Remainder.** This does not claim equal bytes have equal empirical origin, authorize
changing an existing profile, weaken signature/tenant verification, or decide that
all kind and lineage fields can be verified by the CAS itself. Consumers that need
source independence still require their own evidence. Per-view concurrency and
cross-backend compatibility remain implementation obligations.

**Remainder standing and signatory.** The CAS has no standing to prove empirical
origin or consumer-specific lineage; those predicates remain `not_established` by
the CAS alone, and each consuming owner must sign or independently reconcile its
own evidence. The `polisyos.core.artifacts` package owns artifact IDs, manifests,
signatures, and the CAS boundary (`src/polisyos/core/artifacts/README.md`). A named
engineering owner/signatory for the multi-view contract and cross-backend
implementation is not established by that package README or this draft; that
assignment remains `unallocated/not_established` until made. Denis remains the
pending principal signatory for the semantic choice to support honest typed views.

**Falsifier / revisit trigger.** Reopen if any backend returns a view ref whose
resolved manifest differs from it, if same-profile retries create a second view,
or if a tampered view can point at a different blob/profile while retaining a green
verification result. The acceptance signal is the A/B same-bytes witness through
filesystem, S3, GCS, and caching-store contracts, plus the existing first-writer
and corrupted-blob negatives. No such run is claimed here.

**Where it binds.** Shared contract `core/artifacts/protocol.py::ArtifactStore`;
typed references and historical projections in `core/artifacts/manifest.py`;
manifest lifecycle and `FileSystemCAS` in `core/artifacts/_manifest_lifecycle.py`
and `core/artifacts/store.py`; configured remote/cache implementations under
`core/artifacts/backends/`; artifact import/export and signature paths. No caller may
construct an envelope to compensate for a missing CAS view API.

**Pattern pass.** P05/P27/P31/P32/P37/P38. The instance symptom is a CAS conflict;
the class is the mismatch between a content key and a single semantic view. Target:
one generic, typed multi-view contract implemented by the shared owner, not
consumer-specific exceptions. Multi-view refs/artifacts are `artifact_missing` and
consumer resolution is `consumer_missing` until the shared contract, every backend,
and a mismatch-negative witness are wired.

## R11 — CYC-04 VOI semantics after a repeated candidate cycle

**Question.** When the loop’s final candidate repeats the immediately preceding
candidate, should `blocked` remain a distinct safety cap, or should the VOI outcome
be expressed as `stop` or `escalate`?

**Options and costs.**

1. **Proposed lean:** preserve `blocked` as a typed safety cap for a repeated
   candidate cycle. Keep `terminal_kind=search_ceiling_repair_required` and the
   `fake_cycle_same_candidate_repeated` reason. The scheduler’s `advance` result is
   advisory and must not override the blocked outcome or authorize another cycle.
   This accurately separates non-progress from an ordinary stop or a request for
   human judgment. Its cost is that the board, promotion, public projection, and
   recursive-routing consumers must all preserve this cap; their complete behavior
   has not been demonstrated here.
2. Map the outcome to `stop` or `escalate`, retaining the repeated-candidate reason
   only as diagnostic metadata. This matches the current test expectation and keeps
   the older action vocabulary, but risks describing a non-progressing repeated
   candidate as an ordinary stop or as a human decision rather than a repair-required
   cap.
3. Allow the scheduler’s `advance` to continue the loop. This avoids a new action
   state, but permits a repeated candidate to count as another search cycle and
   violates the loop’s non-repeat discipline.

**Premises.** The phase-0 JUnit receipts are
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-20260924T084614Z-77175/cells/e02_execution_base/test_generation_cycle.junit.xml@5cc9da821ca9b6940f7bc6e1123f6fb663283b5367002cf12c93d5ad6a1a6588`
and
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-20260924T084614Z-77175/cells/e02_head/test_generation_cycle.junit.xml@4fc8f811e7a08e4227c6236bd52e3bd1122f984c75d5a904dacf0d962cafc71e`.
The E02-head failure payload reports final `next_action=blocked`,
`terminal_kind=search_ceiling_repair_required`, `scheduler_action=advance`, and
`reason=fake_cycle_same_candidate_repeated`. The E02-head test source asserts that
cycle 0 advances and that the final action is `stop` or `escalate`
(`policy-engine/tests/unit/runtime/quality/test_generation_cycle.py@beb20c6bb8e1ed8aa46910fea0d3a4cf7cfabe15`,
`test_controller_runs_counterexample_driven_revision_over_two_real_cycles`). At E02's
execution base, the test file is a different blob
(`policy-engine/tests/unit/runtime/quality/test_generation_cycle.py@28682ef61d0cec22f2420794f7e3aa3e396418b4`);
E02 also added `repo_root` wiring in this test. The two receipts therefore do not
establish a pass-to-fail change for an unchanged test, and this draft makes no such
P41 claim. The E02-head implementation compares adjacent
`selected_candidate_content_hash` fields in `_fake_cycle_reason`
(`policy-engine/src/polisyos/runtime/quality/generation_cycle.py@a17e52cff360f554478dd44844ea3ef27c62c043`).
The JUnit receipts do not contain the candidate hash values, so no numeric hash
sequence or independent runtime observation of that equality is claimed. The receipt
shows the outcome for this fixture; it does not establish which action vocabulary is
correct or prove how every production consumer handles `blocked`.

**Proposed choice; principal status.** Recommend option 1, subject to Denis’s
principal ruling. Define `blocked` as a non-advancing cap for this repeated-candidate
condition, with `search_ceiling_repair_required` preserved as the terminal kind.
The `scheduler_action=advance` field must not override that cap. Do not change the
base test expectation on this draft alone: a changed expectation needs a behavioral
witness for the chosen semantics and consumer composition. The cited JUnit trace is
not evidence that the board, promotion, projection, or recursive routing paths
consume `blocked` safely; none of that consumer proof is claimed here.

**P37 — gate predicates at admission.**

- E02's `_fake_cycle_reason` compares adjacent
  `selected_candidate_content_hash` fields (`policy-engine/src/polisyos/runtime/quality/generation_cycle.py@a17e52cff360f554478dd44844ea3ef27c62c043`).
  Equality of stored fields is `recomputed`; whether each field is bound to the
  candidate bytes is `not_established` without resolving those bytes. The reason
  marker alone is `not_established` as evidence of candidate equality.
- A `blocked` decision must dominate an `advance` scheduler recommendation before
  any additional cycle or authority-bearing action. The JUnit output shows both
  fields but does not prove consumer precedence; downstream composition remains
  `not_established` and cannot carry an authority-grade positive.

**P38 — property and divergence.** Property: once adjacent cycle candidates repeat,
that repeated occurrence cannot be treated as new progress or reach current authority
through an `advance` recommendation. The observed decision contains
`next_action=blocked` and `scheduler_action=advance` at once. A consumer that gates on
`scheduler_action` while ignoring `next_action` would diverge from the property by
advancing after the typed block. Whether a production consumer takes that path is
not established here; the coexisting values make precedence a required behavioral
witness, not an assumed implementation fact.

**Remainder.** This proposal defines only the CYC-04 repeated-candidate case; it does
not define every use of `blocked` or establish general VOI-consumer behavior. The
run validator must reject a non-final blocked cycle. Board, promotion, public
projection, and recursive-routing composition remain unproven and must not treat this
draft as proof that a blocked candidate cannot affect current authority. The test
assertion records an expected result, not proof of the correct contract.

**Remainder standing and signatory.** Denis is the pending principal signatory for
the action vocabulary. `runtime/quality` is the code boundary for the loop decision,
but an assigned engineering signatory for the broader consumer composition is not
established by this record. Owners for the board, promotion, public projection, and
recursive-routing consumers are also not identified here; their standing is
`unallocated/not_established` until appointed. Until those owners provide behavioral
witnesses, this draft grants no consumer authority to interpret `blocked` as a safe
terminal.

**Falsifier / revisit trigger.** The proposed cap fails if a run with equal adjacent
candidate content hashes receives a different reason while retaining the repeated
candidate condition, if a candidate-hash difference still produces
`fake_cycle_same_candidate_repeated`, if another cycle executes after `blocked`, or
if any consumer admits the blocked candidate to current authority. For the
removal probe, preserve the reason marker but change the actual adjacent hashes; the
behavioral assertion must turn red if the marker alone still produces the block.
These are acceptance probes, not results claimed by this draft.

**Where it binds.** Typed result and scheduler precedence at
`runtime/quality/generation_cycle.py::LoopVOIDecision` and
`GenerationCycleController.decide_next_action`; repeated-candidate classification
and run validation in `generation_cycle.py`; and the board, promotion, public
projection, and recursive-routing consumers named by CYC-04. The loop result is not
complete until those consumers consume the typed block and prevent later-cycle or
current-authority use.

**Pattern pass.** P04/P05/P29/P37/P38/P41. The observed gap is the coexistence of a
blocking `next_action` and an `advance` recommendation, with consumer precedence not
established. Target: one typed blocked cap that is derived from candidate identity
and enforced across every consumer. The test trace exists; consumer-composition
verification remains `verification_missing`. No test expectation change or
implementation is claimed by this decision draft.

## R13 — one world-growth path and runtime store custody

**Question.** Does the tracked ACQ-01 local route have a production producer that
can be connected to world-growth admission, or must that route remain explicitly
non-authoritative until a producer and its admission handshake exist?

**Options and costs.**

1. Keep the local route as production authority. This is the least wiring, but
   policy users and Data Forge owners bear two definitions of world growth, while
   the local path lacks overlay admission, passport, native epoch, and the runtime’s
   tenant-bound store.
2. **Proposed choice:** confine the local route to an explicitly marked,
   non-authoritative contract-test or demonstration lane. The existing fixture
   remains useful; production ACQ-01 stays `producer_missing` and cannot mint a WMR
   or re-enter N7 until a real production producer and its admission handshake are
   established. The served WDI route continues through the existing canonical
   bridge. Users keep that admitted acquisition path, while ACQ-01’s future
   production capability remains incomplete.
3. Build or identify an actual production ACQ-01 producer now, then route it through
   the canonical bridge. This could restore a served ACQ-01 path, but the measured
   source tree does not establish such a producer or caller handshake. It requires
   an owner, typed production inputs, authority/journal binding, and a served
   end-to-end witness before it can be promoted; building those without an identified
   production caller would create an unsupported capability with no established
   purpose or authority boundary.

**Premises.** B12 requires the real chain from typed requirement through authorized
job, owner acceptance, re-entry, and recomputation; a plan or unaccepted response is
not world growth (`source/B_r19_original.md`, B12; bundle `ACQ-01.md`). LA-046 remains
an explicit handoff into ACQ-01, not permission for another compiler or data owner
(`source/LA_r09_original.md`, LA-046; bundle `ACQ-01.md`). The North Star says
acquisition is VOI-driven demand paging into the growing causal world model
(`policy-design-causal-operating-system-north-star.md` §5). GY Rev 16 / N13b and
the acquisition frontier require Data Forge overlay admission, passport, and native
epoch qualification. Storage custody requires the store supplied by the runtime;
rebuilding `FileSystemCAS` from a path loses the guarded tenant context.

The independent source census at candidate base `73c656744` walked the complete
denominators of 2,693 `src/polisyos` Python files, 2,722 test Python files, and 445
tool Python files. It found 21 tracked source hits and 14 test hits for
`acq01_route`; source inspection shows one production call to
`_rebuild_n7_acq01_route_context` and a producer only in the test fixture. This
establishes `producer_missing` for the tracked production route in that denominator;
it does not prove that no external or dynamic producer exists. Such a producer is
`not_established` until identified and its handshake is independently reconciled.

The served WDI path already composes `AcquisitionWorldGrowthBridge` with
`control_service._artifact_store`, the event log, and epoch deployment
(`runtime/http/services/acquisition_surface_execution.py`). The bridge selects an
exact tenant/cell/run/route, uses the existing native admission owner, persists
authority receipts through the supplied store with tenant/cell/run/job binding, and
reconciles reads against the expected tenant
(`runtime/quality/acquisition_world_growth.py`). In contrast,
`GenerationCycleController._rebuild_n7_acq01_route_context` reads a route-provided
`capture_store_root`, reconstructs `FileSystemCAS`, and can build a fresh WMR/context
from a local route snapshot without the canonical bridge’s overlay/passport/epoch
chain (`runtime/quality/generation_cycle.py`).

Root-rebuilt store repairs are a separate mandatory custody obligation and are not
discharged by choosing option 2: route acquisition-planner persistence through its
runtime-supplied store (including `.n7-live-cas` and `FileSystemCAS(cas_root)`);
replace generation-cycle `_joint_simulation_result_store`, the
`.tmp/gy-s-composed-wmr-cas` read, and route-store reconstruction with the supplied
store; and repair `foundry/plugins/training_adapter.py` to use the runtime-owned
store where its artifacts cross that boundary. Contract fixtures may use isolated
test stores only while explicitly non-authoritative.

**Proposed choice; principal status.** Deviate from the assignment lean to route
ACQ-01 into the bridge: its premise that a production ACQ-01 producer exists is not
established by the complete tracked-source census. Adopt option 2 as the lane
proposal, pending Denis’s principal ruling. Confine the local route to explicitly
non-authoritative contract-testing/demonstration and prevent it from minting a
production WMR or re-entering production N7. Keep the served WDI path on the
existing `AcquisitionWorldGrowthBridge`; do not add a second production producer
or change that working bridge. ACQ-01 may be reconsidered for production only after
an actual producer and its typed request, authority/journal, overlay, passport,
native-epoch, tenant-store persistence/readback, and served consumer handshake are
demonstrated end to end. This is a proposed deviation, not a principal decision or
an implementation claim.

**P37 — gate predicates at admission.**

- Route selection is an exact comparison of a verified closure’s
  `(tenant, cell, run, route, design_problem)` with configured typed selection
  (`recomputed` against `institutionally_supplied` deployment configuration).
  Configuration selects a route; it does not establish acquisition authority.
- Production ACQ-01 producer presence is `producer_missing` in the enumerated
  tracked-source denominator above. The census result is `recomputed` for that
  denominator only; absence of an external or dynamic producer is
  `not_established` and may not be claimed from this census.
- Live evidence is admitted only after the existing catalog/authority, budget,
  owner receipt, native epoch, and passport chain is resolved and reconciled
  (`independently_reconciled`). A URL, plan, caller-owned CAS snapshot, or route
  declaration alone is `consumer_asserted` and cannot admit data.
- Before/after overlay membership and the positive admitted delta are read from the
  owner’s catalog projection (`recomputed`). If the canonical owner or expected
  tenant cannot be verified, growth is `not_established` and the route stays
  pending/deferred.
- Receipt tenant custody must be verified through the runtime store and durable
  event reconciliation (`independently_reconciled`); a manifest tenant field by
  itself is not proof.

**P38 — property and divergence.** Property: every production world-growth write
enters through Data Forge overlay admission, passport, and native epoch qualification
using the runtime’s tenant-bound store. Current implementation: the tracked
production source has one call to `_rebuild_n7_acq01_route_context`, while the only
tracked `acq01_route` producer is a test fixture; the helper accepts
`capture_store_root`, constructs a new `FileSystemCAS`, and rebuilds local route
context. Divergent case: a fixture-produced route payload supplied to a production
N7 run can create a WMR and re-enter the cycle without overlay admission, passport,
epoch receipt, or the runtime store’s tenant guard. The route’s production producer
being absent from tracked source does not remove this reachable bypass. A production
tenant-transfer probe must also fail through the guarded store, not only through a
raw filesystem store.

**Remainder.** This does not make PolicyOS the owner of external licenses, data
collection, or institutional authority. Those remain integrated typed inputs owned
by their source institutions/Data Forge; PolicyOS owns admission, receipt, re-entry,
and the truth of its resulting world-growth claim. An unavailable external owner
means a typed limitation or blocker, never a local authority substitute. This draft
does not close the merge-related authorized-epoch reissue register row. Production
ACQ-01 remains `producer_missing` for tracked source, and no absence of external or
dynamic producers is claimed. Root-rebuilt store repairs listed above remain
mandatory independently of this route-confinement choice.

**B27 remainder / smallest missing capability.** Separating
`GenerationCycleRecord.design_problem_ref` from
`design_problem_basis_ref` does not close B27. `CycleSubstrateContext` still binds
the full `design_problem_ref`, its context-binding hash, and owner evidence; the
resolver requires equality with the active problem hash. No owner-issued P0→P1
context-transition API or producer is identified in the inspected owner path.
The smallest missing capability is an owner-issued transition receipt that states
the changed premises, revalidates the source/owner evidence against P1, emits and
persists a new P1 context, and preserves P0 history (`source/B_r19_original.md`,
B27; bundle `CYC-03.md`). Until that transition producer is identified
(`producer_missing`) and its source issuer is resolved (`not_established`), keep
equality strict, do not synthetically rebind P0 evidence, and allow a later-cycle
served request to remain limited or blocked until a valid P1 context exists. This
draft does not claim a stable-subject/current-basis receipt alone closes B27.

**Remainder standing and signatory.** A source institution signs its own license,
collection, and institutional-authority acts; where no source owner or signer is
identified, that input remains `unallocated/not_established` and cannot be replaced
by a PolicyOS signature. The already-served WDI world-growth claim is owned by the
`runtime/quality/acquisition_world_growth.py` admission and re-entry path, together
with `runtime/quality/acquisition_movement.py`,
`runtime/quality/acquisition_epoch_admission.py`, and
`runtime/quality/semantic_epoch_qualification.py`; these owners verify typed source
evidence and tenant custody. This WDI owner chain does not establish an ACQ-01
production producer: its status is `producer_missing` in the enumerated tracked
source denominator, while external or dynamic producers remain
`not_established`. For the merged-epoch register row, the merge-base transition rule
is already ruled; `runtime/quality` owns the fifth transition and must state its
premise, perform the authorized reissue, and verify matching readback
(`docs/plans/active/DEBT-REGISTER.md`,
`merged-lanes-need-a-reissue-path-neither-lane-declared`). No reissue is authorized
by this draft. Denis remains the pending principal signatory for this proposed
single-world-growth boundary.

**Falsifier / revisit trigger.** Reopen if a production caller can mutate the
authoritative world through a path other than the canonical bridge, if the bridge
reconstructs a store from a root instead of receiving the runtime store, or if a
guarded-store re-entry lets a stale/foreign tenant read or attach another tenant’s
receipt. The served witness is authorized WDI evidence → overlay delta → passport
and epoch receipt → same-case re-entry under the same tenant; the negative is a
foreign or unresolved tenant/case. A candidate computation with no admitted data is
the property-preserving control. A removal probe that deletes the production-route
confinement while retaining its non-authoritative markers must turn red if a fixture
route can still mint a production WMR. Reconsider ACQ-01 production routing only
when a real production producer is identified and its complete admission handshake
has a served semantic witness; a name hit or route declaration alone does not
falsify `producer_missing`. For B27, the falsifier is a revised P1 basis with the
P0 `CycleSubstrateContext` retained: if N5/N7 treat that old owner evidence as
matching P1, the equality gate is unsound. The next positive witness is a served
P0→P1 revision whose owner-issued transition names changed premises, produces a
revalidated P1 context, and admits it through N5/N7 while retaining replayable P0
history; a changed population/model must not reuse P0 evidence. Until that witness
exists, the later cycle may remain limited/blocked. These runs are required for
implementation; none is claimed here.

**Where it binds.** Production composition in
`runtime/http/services/acquisition_surface_execution.py`; the bridge and durable
admission/readback in `runtime/quality/acquisition_world_growth.py`; ACQ-01
orchestration, its single production call, and local route confinement in
`runtime/quality/generation_cycle.py::_rebuild_n7_acq01_route_context`; the test-only
producer in `tests/unit/remediation/test_acq_01.py`; and the separate runtime-store
custody repairs in `runtime/quality/acquisition_planner.py`,
`runtime/quality/generation_cycle.py`, and `foundry/plugins/training_adapter.py`.
N5 result persistence and composed-WMR reads must consume the supplied store where
their artifacts cross the runtime custody boundary. B27 binds to
`CycleSubstrateContext.design_problem_ref` and context-binding validation in
`runtime/quality/cycle_substrate.py`, plus
`GenerationCycleRecord.design_problem_ref` / `design_problem_basis_ref` and the
recursive N5/N7 consumers in `runtime/quality/generation_cycle.py`.

**Pattern pass.** P01/P02/P05/P07/P08/P12/P27/P31/P32/P35/P37/P38. The observed
classes are a local route without a tracked production producer, a missing
owner-issued P0→P1 context transition, and root-rebuilt stores that bypass tenant
custody. Target: confine the local route to a non-authoritative test/demo lane,
preserve the existing served WDI bridge as the proven production world-growth chain,
and keep context equality strict until an owner-issued transition exists. Production
ACQ-01 is `producer_missing`; possible external or dynamic producers are
`not_established`. B27's smallest missing capability is the P0→P1 transition
producer/receipt; its falsifier and next served witness are above. Closure for
production ACQ-01 requires an actual producer, persisted typed evidence,
bridge/admission handshake, tenant-bound re-entry, and served semantic test. The
separate store-custody obligation closes only when every runtime call site uses the
supplied tenant-bound store and the guarded tenant negative passes.

## Closeout note

These five drafts are proposals only. The lane has not recorded a principal’s
acceptance, implemented the proposed repairs, run their falsifiers, or authorized
any governed reissue. A principal ruling should be appended with its date, named
decision, evidence that moved it, and any changed remainder; it should not be
backfilled as though already granted.
