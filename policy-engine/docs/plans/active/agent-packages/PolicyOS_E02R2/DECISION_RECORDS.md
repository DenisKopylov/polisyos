# E02-R2 decision record drafts

**Current status (reconciled 2026-10-01).** Denis's R1 Option A, R11 universal v3
blocked-run/N9-exclusion, and R5 protected-mode EvalSafety fail-closed direction
remain the recorded principal choices. R5 implementation is integrated at
`f7d66883fbcb352eb923c23e3e104608490e8061`; that does not close the finding. Its
positive DataTrust bridge and complete four-base whole-file P41 replay remain open.
R1 V3 has a bounded design GO for static candidate-scenario selection within the
already selected controlled N4→N5 lane. It excludes exactly the four server-injected
execution IDs at `nl_provenance.source_context` from the selector basis; the full
DesignProblem identity and complete job/context custody remain bound. This is an
engineering design status, not a new principal permission, production-grounding
claim, or authority grant. The source-pinned profile-selection review is cited in
the dated R1 V3 draft below. Source-pinned diagnosis and independent review also
give a bounded engineering GO to remove only the caller's
`target_world_scope_profile_id` nonempty-string prerequisite from the existing
`VerifiedNLJobScope` issuer for authenticated, established simulate-only served
`POST /api/v1/control/runs/nl` jobs. Existing event/outbox/manifest, actor, route,
tenant/cell, intent-digest, current job/run/state, nonempty matching live lease-owner,
and attempt checks remain. The ephemeral scope is `cycle_input_candidate_only`: it
binds the act and lease, not profile vocabulary or profile admission, and grants no
N8, S8, promotion, publication, world-growth, or other authority. These reviews are
source/design evidence, not runtime delivery; the configured served positive, truthful
compiler fixture, and current integrated run remain open. The distinct R1 Appendix-A
test-identity proposal and R1/R5 per-active-basis proposal remain pending. Principal choices still pending are R2,
R13, R14, and the separate broader R9 owner-index-publication, V3-binding, and
multi-view proposals. Denis's R9 ruling retains a temporary refusal only for served
V2 production-approval issuance and operational currentness across recognized
owner-index states. Historical packet bytes/signatures and unrelated candidate,
packet, and artifact families remain outside that refusal. Its V3 implementation
and deployment-bound rollout remain open.
A ruling records direction; it does not by itself claim closure or authorize
reissue or restamp of a governed artifact.

**Prepared:** 2026-09-24. **Original code inspected:** candidate base
`73c656744f051d9f40667da7f8bc91c61d8b4ebf`. The sections below preserve their
original proposal snapshots. Later dated addenda supersede only the status and
evidence they explicitly update; no record authorizes a governed reissue or restamp.

Each draft follows the visibility fields in
`docs/system-design-decisions/policyos-identity-and-custody-boundary.md` §9.7:
question, options and costs, premises, proposed choice and decision-maker status,
remainder, falsifier, and binding seam. Predicate labels and implementation/property
divergences follow P37 and P38 in
`docs/reference/policy-design-case-failure-patterns.md`.

## R1 — CYC-01 ordinary N4 entry without an established owner context

**Question.** When an ordinary plain-language request has no tenant-store-bound
`CycleSubstrateContext`, may the HTTP composition return candidate work, and what
evidence must exist before S8 may emit a ranked recommendation?

**Options and costs.**

1. Require an owner context before any N4 candidate work. This keeps the producer
   input simple, but users pay for missing owner data with total refusal; new cases
   depend on pre-enumerated owner state. The HTTP/runtime team pays little change
   cost; ordinary users and source owners pay in refused candidate work and
   pressure to pre-enumerate scope.
2. Remove context, source, and binding checks. This restores reachability quickly,
   but runtime and policy consumers bear the risk that caller-owned or mismatched
   world state is treated as grounded. The runtime-quality team saves implementation
   effort while N5/S8 and published-claim consumers bear the integrity cost.
3. **Preferred lane proposal — bind server-selected intent through the existing
   payload and job-created event/outbox.** The authenticated ordinary NL action
   selects candidate-only; request-body markers cannot select or upgrade authority.
   Put one strict typed intent in the already persisted control-job payload, then
   bind its digest, exact payload ref, job/run identity, and authenticated action
   in the existing job-created event/outbox. Before worker/N4 dispatch, load and
   reconcile the job, event/outbox, and payload bytes. Missing, legacy, conflicting,
   or mismatched evidence is non-runnable and refuses before dispatch. A retry keeps
   the immutable intent and payload; validate the current lease/attempt at dispatch
   rather than minting a per-retry successor artifact. If creation is not atomic,
   any partially written row must remain unleaseable or fail closed before N4.

   Recognized EvalSafety/protected intent still goes through its existing owner and
   current checks; malformed or refused protected intent cannot fall through to
   candidate execution. If this endpoint is meant to accept protected work without
   a declared server-recognizable action or mode, name an explicit server-owned
   selector; neither `execution_profile` nor caller context is that selector.
   For candidate-only work, try the existing canonical producer with absent context
   typed `not_established`. Candidate computation may proceed without claiming N5
   simulation or authority. When the job has both tenant and cell IDs, a successful
   no-context proposal is persisted as `N4CandidateProposalRecord.v1` with the
   `cycle_substrate_context_unavailable` limitation. Without that owner scope,
   proposal persistence remains `not_established` and there is no proposal ref.
   This proposal-only route does not produce a `CompiledRecursiveGenerationCycleRun`.
   If N4 returns `generation_unavailable` or `preflight_rejected`, complete the job
   with result status `not_established`, no proposal ref or artifact, and
   N5/N8/N9/S8 stage statuses `not_run`. S8 authority remains unavailable on all
   these limited paths. Do not enter recursive simulation to manufacture
   blocked observations. A later compiled-run route would need its own versioned
   limitation and byte-exact historical serializer. S8 remains blocked/limited until it
   loads the real persisted N4 handoff and existing owners establish tenant binding
   and context currentness. Cost: payload/event binding and dispatch reconciliation;
   a later compiled-run route would additionally require versioned replay. This
   reuses the job payload, event/outbox, CAS, and
   `GenerationSourceRepository`; it adds no standalone admission artifact, public
   status DTO, or second context owner. The ControlPlane/HTTP and runtime-quality
   owners pay for payload/event binding and dispatch wiring; the N4 source owner
   pays the handoff integration; test and package owners pay for served witnesses
   and any compiled-run historical replay needed by that later route.
4. **Conditional only — add a standalone CAS admission artifact or retry-successor
   chain.** These duplicate intent already bound by the payload and event/outbox and
   add artifact lifecycle, read paths, and retry machinery. Consider a separate CAS
   record only if a focused race/owner test proves option 3 cannot make a partial
   creation unleaseable or fail closed before dispatch. A retry chain is warranted
   only if a concrete retry can change the immutable intent or payload in place.
   The present evidence establishes neither condition; these mechanisms are not in
   the preferred write set. The artifact-store and control-store owners would pay
   for the extra producer, retention, retry, and consumer lifecycle.
5. **Rejected option:** add a new root-context owner inside R1. This could supply
   positive evidence sooner, but would overlap R13's runtime-store repair and risk
   a second WMR/context owner. The existing WMR producer accepts a supplied store;
   wiring that owner is the narrower route. The substrate/runtime team would pay
   to maintain duplicate construction and reconciliation, while tenant consumers
   would bear the resulting custody ambiguity.

**Principal choice on the five existing normative fixtures.**

- **A — upgrade them.** Keep the `authorized` outcomes, but use a served real N4
  producer, the existing persisted source handoff, and owner-resolved
  tenant-context/currentness evidence. This preserves their behavioral intent, but
  depends on R13's store path and the missing context-owner capability. The HTTP,
  N4/source, and context-owner teams pay the integration and four-base witness cost.
- **B — keep them blocked.** Preserve fail-closed behavior until that owner
  capability exists, and change the old expected dispositions only after Denis
  explicitly rules the comparability decision. This accepts bounded loss of those
  authority outcomes; it does not justify refusing ordinary candidate work. The
  affected policy users bear the unavailable normative outcomes; runtime-quality
  owners avoid asserting unverified authority.

**Premises.** B01–B03 describe ordinary request entry and the need to carry
data/model context through the actual HTTP → N4 → N5 path; their criterion is a
real ordinary request, not a manually assembled Python context
(`PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md`, B01–B03; bundle
`CYC-01.md`). S0-K06’s binding application says fail-closed binds protected actions,
published claims, and custody facts, while candidate work may carry a declared
unknown (`docs/system-design-decisions/stage0-custody-kernel-ratification.md` §4.3).
The identity ruling makes typed absence behavior PolicyOS’s contract, while the
external owner remains owner of its function
(`docs/system-design-decisions/policyos-identity-and-custody-boundary.md` §5). The
product’s ordinary front door must remain usable as the causal model grows
(`docs/system-design-decisions/policy-design-causal-operating-system-north-star.md`
§§5–6).

When an ordinary `candidate_only` HTTP request has no context and no explicit N4
port, the composition returns `N4CandidateProposalExecution` before the recursive
route. The worker persists and reopens a successful proposal when tenant/cell
job scope is available; terminal N4 outcomes and absent scope produce no proposal
ref. N5 and S8 are `not_run`
(`src/polisyos/runtime/http/services/control/run_lifecycle.py@sha256:db84338772e43cb55a57c1bb91e78e85468b5c7788ccf8d709aec2e8194526a3`).
An explicit N4 port without context is refused. The HTTP function has no call to
`_build_cycle_substrate_context_from_owner`, and no production caller of
`CycleSubstrateContextArtifactOwner` was found in the served route. These facts
establish candidate reachability, not a B01–B03 served N4→N5 witness
(`src/polisyos/runtime/http/services/control/generation_cycle.py@sha256:4425b37053189b66f2d49124f8033218e9c936719798c29acae8817fcfe90a0e`).
The separate composed-WMR fallback still rebuilds a root-local store, so it
cannot supply tenant context for a future full N4 route
(`src/polisyos/runtime/quality/intervention_substrate.py@sha256:1783a4ecfd67e0010e4e4ccc5c19a022da5786e517c70f356cd5f639cbc726df`).
The underlying `build_production_data_state_world_model_record(store, ...)` accepts
a supplied store; R13 owns wiring that existing producer to the runtime store.

`CycleSubstrateContext` is a candidate-only in-memory envelope: its typed
`authority_purpose` is `cycle_input_candidate_only`, and `may_not_use_for` excludes
authority. `CycleSubstrateContextArtifactOwner` can persist and resolve an
already-built context under the current job and tenant, but no served caller
builds the source-bound context and invokes that owner. The compiled wrapper
records `cycle_substrate_context_ref` as a
content-hash string, not an `ArtifactRef` or tenant-bound manifest, and currently
has no typed field preserving an absent context as `not_established`. If a later
compiled-run route carries absent context, version this hashed wrapper with that
typed limitation and an exact historical projection; S8 must load and consume the
limitation alongside signed evidence. The current no-context proposal-only route
does not write this wrapper. The current
`GenerationSourceRepository` persists an actual `DesignGenerationOrganRun` and its
context through the runtime store, then validates its owner profile, CAS bytes,
problem, candidate, and context on replay. This existing handoff is the durable N4
source record to resolve at S8; do not add a parallel source record. The runtime
CAS's ambient owner index provides
artifact-store custody, but the handoff's `ArtifactWriteOptions` omit explicit
`tenant_context`. Ambient store custody does not establish which tenant-owned root
context the producer consumed, nor the separate signed-value permission S8 consumes.
`CycleSubstrateContext` also has no typed epoch or currentness field/gate:
content-valid replay does not establish that its WMR and context remain current. A
non-null context, matching context hash, hash-verified run, or mere use of
`runtime.store` is not P32 proof
(`src/polisyos/runtime/quality/cycle_substrate.py@f24fcc8ded61aa07c0c4145ea27f929995533f11`;
`src/polisyos/runtime/http/services/control/generation_cycle.py@055cca6c9424deac61fa61543143a2a2d2310b1a`;
`src/polisyos/runtime/quality/generation_source.py@9bd65c03be46082edb9d0af4749776085ef5569a`;
`src/polisyos/core/artifacts/ownership.py@95dc77f264b38dc40d658cfb2c9b153265e7a99b`).

The existing `[authorized]` control-service fixture is not a positive
context-consumption witness: its `_CanonicalFixtureN4Port` delegates to
`_CgfGenerationPort`, returning a test `_GenerationResult` rather than a
`DesignGenerationOrganRun`; it writes no N4 source handoff
(`tests/unit/runtime/http/test_control_service_di.py@4c100bb6d2c17cac8e3e61bee34519c338c075ec::test_process_nl_job_enters_persisted_tenant_scope[authorized]`;
`tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a::_CgfGenerationPort`). The five normative bridge
cases currently expecting `authorized` also use `_CgfGenerationPort`, not real N4:
`test_same_display_ids_do_not_bind_another_current_compiled_source`,
`test_current_permission_expiry_overrides_persisted_green`,
`test_current_signature_corruption_revokes_recommendation`, and
`test_every_current_job_reader_replays_persisted_authority` for `get_job_status` and
`get_latest_job_for_run`. The current-head review reports 17/22 cases passing and
these five returning `blocked`; this is not yet the four-base P41/JUnit receipt
(`tests/unit/runtime/http/test_normative_generation_bridge.py@ef8ec18a438afe790a0b03f35f90b9e90d6288d4`).

**Earlier lane proposal (before Denis's dated option-A ruling below).** Option 3
was proposed here. Its preferred mechanism is one server-selected typed intent
carried in the existing persisted payload and bound by the existing job-created
event/outbox, with readback reconciliation before dispatch. A standalone CAS
admission artifact remains conditional on a focused test showing that this existing
binding cannot fail closed across partial creation; no such evidence is established
here. Preserve context content validation, but do not treat the current repo-root
fallback as proof of tenant-store custody. An ordinary request with no established
context may return candidate work and carry an explicit typed unknown; it must not
invent a WMR, catalog entry, or concrete scope. If that unknown prevents a valid N5
world simulation, retain a typed pending/limited result. S8 may emit a ranked
recommendation only after it loads and verifies the real, persisted N4 handoff with
its embedded `CycleSubstrateContext`, bound to the exact problem and candidate
identities. `GenerationSourceRepository.load(ref, run_id)` returns the full
`GenerationSourceHandoff`; `resolve(...)` returns a `GenerationSourceResolution`
projection, not the full handoff. S8 must use `load` or a strict owner extension
that verifies the full handoff. The handoff's owner profile must bind
`tenant_context`; do not make a second artifact for the embedded context. The
existing `build_production_data_state_world_model_record(store, ...)` is the named
WMR producer to wire through the runtime-supplied store under R13. It owns WMR
production. The existing `CycleSubstrateContextArtifactOwner` persists and
resolves an already-built tenant/job-bound context; its served source-profile
producer/caller remains missing. Context currentness
must likewise be established by an existing owner or remain `not_established`;
ambient CAS custody and content-valid handoff replay alone do not prove it. A
matching hash or caller-injected context is insufficient. An N7 re-entry's prior
handoff does not prove its post-growth context; until a complete post-growth witness
exists, S8 remains blocked for that source. At this earlier snapshot, the fixture
choice was open; Denis later chose option A in the dated addendum. Four-base
fixture replay remains pending/UNRUN, and no fixture counts as positive S8
evidence before the served witness.

**P37 — gate predicates at admission.**

- The raw request is caller supplied and supports candidate generation only; it is
  not a predicate establishing policy authority.
- `CycleSubstrateContext` validation recomputes problem binding, WMR identity,
  registry projection, and content hashes (`recomputed`). Its candidate-only purpose
  and `may_not_use_for` limit are part of the typed content; neither establishes
  tenant custody.
- The existing `GenerationSourceHandoff` is the durable post-N4 record and embeds
  its `CycleSubstrateContext`. `GenerationSourceRepository.load(ref, run_id)` returns
  the full handoff for source-profile and content replay; `resolve(...)` returns only
  a `GenerationSourceResolution` projection, and S8 does not currently call `load`.
  Its current write profile lacks explicit `tenant_context`, so the tenant binding
  remains `not_established`. The
  repo-root WMR fallback is not tenant-context-custodied. No separate pre-N4
  tenant-context persistence/resolver owner is identified; if one is required,
  leave it `not_established` until an existing owner is named rather than adding a
  second context artifact owner.
- Runtime CAS ambient owner-index/profile/content checks can establish custody of
  stored bytes (`independently_reconciled` for the configured store, after the
  expected tenant/cell is resolved; see
  `src/polisyos/core/artifacts/ownership.py@95dc77f264b38dc40d658cfb2c9b153265e7a99b`).
  They do not establish explicit tenant-context binding. The N4 handoff write
  profile omits `tenant_context`, so tenant ownership of the consumed root context is
  `not_established` despite ambient CAS custody and source-preservation success.
- The existing `GenerationSourceRepository` persists the full
  `GenerationSourceHandoff`. `load(ref, run_id)` returns it for replay and
  content/profile/problem/candidate verification; `resolve(...)` returns a
  `GenerationSourceResolution` projection, not the full handoff. S8 does not
  currently load that handoff. Use its embedded context as the durable post-N4
  record; do not duplicate it. Missing refs, mismatched context, duplicate
  identities, or absent post-growth handoff block S8.
- Context currentness is separate from custody and content replay. `CycleSubstrateContext`
  has no typed epoch/currentness gate; after content replay, whether the context
  remains current against its WMR and tenant scope is `not_established`. A stale or
  unknown context blocks S8 authority. Signed-value decisions still require their
  own owner verifier and current epoch evidence (`independently_reconciled`).
- On the no-context proposal-only route with tenant and cell IDs,
  `N4CandidateProposalRecord.v1` carries `cycle_substrate_context_unavailable`
  after successful N4 work. Without that scope, persistence is `not_established`
  with no proposal ref. A terminal N4 unavailability completes the job with
  result `not_established`, no proposal artifact, and N5/N8/N9/S8 `not_run`;
  this stage status does not grant S8 authority. If a later compiled-run route admits absent context,
  version its hashed wrapper and preserve historical serialization. S8 must consume
  any such limitation alongside signed evidence; signed-frontier validity cannot
  establish tenant binding or context currentness, which remain
  `not_established` until their existing owners provide those predicates.

**P38 — property and divergence.** Property: ordinary requests retain candidate
reachability under unknown context, while S8 ranking requires a real N4 handoff,
owner-backed tenant/currentness predicates, and consumption of any typed
`not_established` limitation. The explicit-port refusal is conditioned on missing
context plus an injected `root_n4_generation_port`; the default production route
omits that argument and can reach N6 `grammar_fallback`. Removing the early refusal
therefore restores only candidate reachability; it does not produce a real N4 organ,
persist a `GenerationSourceHandoff`, or satisfy B01–B03's served HTTP→N4→N5
criterion. The compiled wrapper currently retains only `cycle_substrate_context_ref`
as a hash and loses the typed limitation for absent context or unestablished
tenant/currentness. The runtime CAS's ambient owner index supplies store custody, but
neither the local `.tmp` WMR nor ambient storage alone proves tenant-context binding
or currentness. Current N4 has a durable
`GenerationSourceRepository` handoff embedding the consumed `CycleSubstrateContext`,
with content/profile/problem/candidate replay, but its write profile has no explicit
`tenant_context`; current S8 reloads the leaf `GenerationCycleRun` and checks its
compiled/frontier binding without resolving that source handoff, a context epoch,
or an outer wrapper limitation.
Divergent case: shape/content-valid context, `_CgfGenerationPort` output, or valid
signed-frontier evidence can appear sufficient without proving real N4 consumption,
tenant ownership, currentness, or the absence of a typed `not_established` wrapper
limitation. The five normative fixtures fail closed as `blocked` against their
`authorized` expectations, but their fake N4 result does not establish the missing
real owner path. The current-head report is 17/22 pass; four-base P41 evidence remains
pending. A removal probe retains signed-frontier and candidate markers but removes
or mismatches the embedded context in the handoff, its tenant binding, or its WMR
linkage; S8 must block with zero recommendations. A separate hashed-wrapper probe
removes the typed `not_established` limitation while leaving signed evidence and
markers intact; S8 must still refuse ranking when the source context is absent. Once
an existing owner exposes typed context currentness, a stale-context probe retains
the source handoff while that owner reports its embedded context stale/unknown; S8
must block with typed limitation. The served
positive control must carry an actual N4 candidate through HTTP →
`DesignGenerationOrganRun` → `GenerationSourceRepository.persist` →
`GenerationSourceRepository.load(ref, run_id)` → S8, including tenant binding on the
embedded context and currentness from an existing owner. `resolve(...)` currently
returns a `GenerationSourceResolution` projection, so it is not by itself a
full-handoff witness. Separately, a
served ordinary request without context must still return candidate work while N5/S8
remain limited or blocked.

**Remainder.** This decision does not appoint a WMR/catalog owner, create a second
world store, or convert an LLM candidate into evidence. The ordinary HTTP worker
persists a successful proposal when owner context is absent and tenant/cell job
scope is available. The separate
root-local WMR fallback needs R13's runtime-store repair before a full N4 caller
can use it. The existing `GenerationSourceRepository`
persists the full handoff containing the embedded post-N4 context, but S8 still needs
to load it; its write profile needs tenant binding, and context currentness must come
from an existing owner. The typed absent-context limitation must also persist in the
content-hashed compiled wrapper v2; its v1 historical projection must preserve old
bytes, and S8 must consume the limitation. No
served source-profile resolver is identified, so construction of the exact
pre-N4 context remains `not_established` until the existing context owner is
wired to an admitted source. No S8 positive
claim is supported by the current `[authorized]` fixture alone. Its
signed-frontier semantics must remain covered. For the five normative fixtures, the
principal chose option A: upgrade their base-pass authorization expectations to
real served N4/handoff/context-currentness witnesses. Until the implementation
and four-base replay are recorded, they are not positive S8 witnesses and their
baseline disposition is not finalized. The separate control-service `[authorized]`
tenant-scope fixture also
needs a real owner/handoff witness or its own comparability ruling.
N7 currently rebinds a post-growth context without emitting a post-growth source
handoff, so that context remains `not_established` and S8 stays blocked until the
canonical owner path supplies a complete witness.

**Remainder standing and signatory.** An absent or unmatched substrate fact has
standing `not_established`; that does not put the ordinary request or candidate
capability on hold. The registered source owner signs any source fact it supplies.
The existing context artifact owner must be wired to an exact source-profile
resolver and served caller; that resolver remains `not_established`. R13 may wire
the existing WMR producer to the runtime store and use the existing N4 handoff
boundary, but does not appoint another context owner or institution. The
HTTP/runtime composition owns carrying the typed unknown and
gating authority, not signing source facts. Denis, as principal, remains the pending
signatory for this proposed candidate/authority boundary; this draft is not
ratification.

**Falsifier / revisit trigger.** Reopen if a served ordinary request cannot return
candidate work when context is absent, or if a candidate with `not_established`
substrate evidence reaches N5 as a grounded simulation, promotion, publication, or
S8 authority output. The S8 negative probe retains valid signed-frontier bytes and
candidate markers while removing or mismatching the embedded context in the N4
handoff, its tenant binding, or its WMR linkage; it must return blocked with no ranked
recommendations. The positive control uses a served HTTP request with a real N4
organ, complete source-preservation receipt, and a persisted `GenerationSourceHandoff`
that embeds the consumed context and is reopened by `GenerationSourceRepository` from
the runtime-supplied store. The handoff's owner profile explicitly binds
`tenant_context`; an existing owner must provide typed context/WMR currentness before
S8 projection. Do not create a separate context artifact for this control. If no
existing owner can provide that predicate, it remains `not_established` and the
positive control cannot pass. Mere store location or content hash does not satisfy
it. Once an existing owner exposes typed context currentness, a distinct
stale-context probe retains the handoff but changes that owner's currentness result
to stale/unknown; S8 must carry that limitation and withhold recommendation
authority. That probe remains unrunnable until the missing typed context-currentness
capability exists.
The N7 control changes the post-growth context while preserving only prior handoff
refs; it must remain blocked. The ordinary candidate control uses a served request
without context and observes candidate work with N5/S8 appropriately limited. These
are acceptance criteria; none is claimed as run here. A removal probe that omits the
typed wrapper limitation but preserves signed-frontier bytes must not produce an S8
ranked recommendation. The schema-v2 hashed wrapper must retain its new limitation,
while historical schema-v1 replays serialize to their exact prior projection.

**Where it binds.** HTTP entry at
`src/polisyos/runtime/http/services/control/generation_cycle.py@sha256:4425b37053189b66f2d49124f8033218e9c936719798c29acae8817fcfe90a0e`
and the served `ControlPlaneService` caller; the currently unserved composed-WMR
fallback and WMR construction at
`src/polisyos/runtime/quality/intervention_substrate.py@sha256:1783a4ecfd67e0010e4e4ccc5c19a022da5786e517c70f356cd5f639cbc726df::_production_composed_world_model_record`
(store repair assigned to R13); candidate-only context contract at
`src/polisyos/runtime/quality/cycle_substrate.py@f24fcc8ded61aa07c0c4145ea27f929995533f11`;
N4 at
`src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`
and `GenerationSourceRepository` at
`src/polisyos/runtime/quality/generation_source.py@9bd65c03be46082edb9d0af4749776085ef5569a`;
N7 post-growth re-entry at
`src/polisyos/runtime/quality/recursive_generation_cycle.py@ddff9abd228378166bce8437862ebe487ae00149`;
and S8 replay at
`src/polisyos/runtime/quality/design_axes/value_choice_provenance.py@83ec53fefe0cc036480bb3d164ebcb44225a6ed9::_generation_disposition`.
The wrapper seam is `CompiledRecursiveGenerationCycleRun` in
`src/polisyos/runtime/http/services/control/generation_cycle.py@055cca6c9424deac61fa61543143a2a2d2310b1a`;
it needs v2 hashing plus v1 historical projection and an S8 consumer bridge for the
typed limitation. The proposal does not alter external catalog vocabulary or appoint
a WMR owner.

**Pattern pass.** P04/P05/P07/P10/P15/P27/P31/P32/P37/P38. The observed defect is
both an authority prerequisite leaking into candidate reachability and authority
being granted without source-consumption/custody evidence. The target is typed unknown
for ordinary candidate work and complete owner-backed evidence at authority gates.
The HTTP caller and a best-effort repo-root context builder exist. The existing
handoff persists the embedded context; `load` returns the full handoff, while
`resolve` returns a projection and S8 does not yet load it. Its write profile lacks
explicit tenant binding; context currentness is also `not_established`. No separate
pre-N4 context artifact/resolver owner is identified, so do not invent one. Current
fixtures have `verification_missing` for real N4 source consumption, explicit
tenant-context admission, and currentness.
Acceptance requires a served ordinary candidate control and a separate served
real-candidate S8 positive, with S8 rejecting absent, foreign, stale, or
post-growth-mismatched owner proof and consuming the typed wrapper limitation.
The hashed wrapper's v2 field must preserve exact v1 historical bytes. The five
existing normative authorization expectations remain a principal choice between
real-producer upgrade and bounded blocked outcome; the 17/22 current-head result is
not a four-base P41 verdict.

## R1 addendum — owner-bound N4→N5→S8 path (principal ruling, 2026-09-26)

This addendum records Denis's selection of option A. It supersedes the earlier R1
proposal's open A/B fixture choice and “subject to Denis's ruling” wording; that
proposal and its evidence remain as the pre-ruling record. This ruling selects an
implementation direction. It does not claim the served positive path, its controls,
or R1 closure have been delivered.

**Question.** How should an ordinary plain-language request reach real N4
production and N5 simulation, and what evidence is required before S8 may emit a
ranked recommendation? How should the existing normative fixtures that expect
`authorized` prove that behavior?

**Options and costs.**

- **A — selected.** Build the real served, owner-bound N4→N5→S8 path through the
  existing runtime store and evidence owners, then update the old fake N4 fixtures
  to use real tenant, runtime-store, persisted-source, and context evidence. The
  HTTP/control, world-model/context, N4 source, N5/S8, and test owners pay for
  cross-owner wiring and realistic end-to-end tests. The tests cost more than
  fixture-only tests, and exercise the capability PolicyOS claims to provide.
- **B — not selected.** Keep the existing fixtures blocked until an owner-bound
  path exists. This avoids integration cost now, but preserves over-refusal at the
  ordinary front door and leaves no positive served normative witness. Users and
  policy-design flows bear the unavailable ordinary outcomes.
- **C — rejected.** Remove the context/source checks or keep a fake port as the
  authority-positive fixture. This is the cheapest test change, but lets synthetic
  status, matching IDs, or caller-supplied context stand in for tenant custody and a
  real N4 record. S8 and recommendation consumers bear the false-authority risk.

**Premises.** B01–B03 require evidence from an ordinary request through the real
HTTP→N4→N5 path, not a manually assembled Python context. S0-K06 keeps the bands
distinct: an ordinary candidate request may continue with an explicit typed unknown
scope, while protected actions and S8 authority require their own evidence. Sources:
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`,
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CYC-01.md@sha256:0fb74637f987bb1a8be4a91f83c6120f918d4c8a3fe27b2974d5b3d2a417ba78`, and
`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md@sha256:a8410cddf3e2c8b7f4c194d06d0c38523fb64634f247e6baf96dfd6359197ea7`.

The existing `GenerationSourceRepository` persists the N4
`GenerationSourceHandoff`; `load(ref, run_id)` returns the full handoff while
`resolve(...)` returns a projection. The existing world-model producer accepts a
supplied store, so the R13 runtime-store owner is the path to wire. No separate
pre-N4 context owner is established by the inspected evidence. Reuse these owners;
if tenant context or currentness remains unavailable, preserve it as
`not_established` rather than creating a second owner or artifact. Current source
identities at this snapshot:
`policy-engine/src/polisyos/runtime/quality/generation_source.py@sha256:6a13f56d2716c610ae2ed9a1bb64cebf4d77e4294b603bfcad034b9aeb665d58`,
`policy-engine/src/polisyos/runtime/quality/cycle_substrate.py@sha256:1e7f14f5634526f120f2f10fb1d7b06bea1e368a2e954734b679a6050b859f88`,
`policy-engine/src/polisyos/runtime/quality/intervention_substrate.py@sha256:1783a4ecfd67e0010e4e4ccc5c19a022da5786e517c70f356cd5f639cbc726df`, and
`policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py@sha256:f0e1871fdabf636e69517f1819ad93bbd795bf8ca0a5d1e42960ccda677b0155`.

The current `[authorized]` control-service case and the five normative selectors
use fake `_CgfGenerationPort` results rather than a real persisted N4 handoff. A
fake positive therefore tests fixture status, not the owner-bound path. The
relevant test files are
`policy-engine/tests/unit/runtime/http/test_control_service_di.py@sha256:c4f0f0552de85ecd3aaecca6b3ef70a2640fc1e3295a5d9578c80aa99bbf0b36` and
`policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py@sha256:3bf494166dd3d86bfd254cfa992fc382f522b2082316b946c328d9f5e9f7c29a`.
Keep the separate protected explicit-N4/no-owner-context refusal in
`policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py@sha256:8b6d67145038c14d5c3b257c3e92cd791518f47e114ea7cb06aff9b7a92464e3`.

**Principal ruling and implementation direction.** Denis selected option A on
2026-09-26. Implement the path through the existing owners:

1. The served control-plane job supplies the authenticated tenant/job identity and
   uses the runtime-provided tenant-bound store. Request markers, display IDs,
   repo-root CAS state, and test-fixture state do not establish authority.
2. Wire the existing world-model/context producer through that runtime store and
   bind the context to the exact problem, candidate, and tenant scope. Do not build
   a second WMR, context, or source owner.
3. Invoke the real N4 producer and persist its source in the existing
   `GenerationSourceRepository`; replay must reconcile the job/run, full handoff,
   stored bytes, and tenant/store scope.
4. Run N5 over that same source and current context. S8 must load the full persisted
   handoff (or a strict equivalent), establish context currentness and its own
   signed-evidence prerequisites, and only then emit a ranked recommendation.
5. Replace the fake authority-positive fixtures with the real served path and
   preserve distinct foreign-tenant, stale-context, and protected no-context
   negatives.

An ordinary candidate request with unknown scope may still produce N4 candidate
work under a typed limitation; that does not assert that N5 simulation ran, that a
world context is grounded, or that S8 may emit authority. If valid N5 simulation
cannot proceed without the unknown context, return a typed limited/pending result.
S8 remains blocked or `not_established` until tenant binding, context currentness,
and signed-evidence predicates are established by their owners. Do not turn the
candidate unknown into a global front-door refusal, and do not let it authorize a
ranked or published claim.

**P37/P38 — admission predicate and divergence.** Recompute the persisted N4
handoff and problem/candidate/context bindings; independently reconcile tenant
identity and runtime-store custody against the authenticated job. Context
currentness and signed-value permission require current evidence from their owners;
absence remains `not_established`. The divergent case is a green fake N4 fixture
with no persisted source bytes or consumed tenant-bound context: its markers pass
while the served property is absent. Replacing that fixture with the real handoff
and consumer is part of option A.

**Remainder.** The ruling does not establish that an existing owner can provide
every tenant-context or currentness predicate. Candidate work remains available
with an explicit limitation where scope is unknown; authority remains blocked until
the owner evidence exists. The positive served N4→N5→S8 witness, the marker-removal
probes, preserving candidate control, and four-base touched-file replay are still
implementation and verification work. R1 remains open; no finding or register row
is closed by this decision. WMR/store changes remain with R13's canonical owner and
must respect the active shared-file lease. This ruling authorizes no governed
reissue or restamp.

**Falsifier / revisit trigger.** Reopen this choice if the existing owner path
cannot persist and replay the exact N4 handoff through the same tenant-bound
runtime store; if foreign-tenant, stale, mismatched, or substituted source/context
can reach N5/S8; if removing tenant binding or full-handoff consumption while
retaining markers leaves the authority test green; or if missing S8-grade context
alone refuses an ordinary candidate request. Closure evidence must include a
served positive that reaches N4→N5→S8 from persisted owner-bound evidence, a
separate no-context candidate-only request that succeeds with its typed limitation,
and negative controls for foreign/mismatched/stale evidence. These are future
signals, not results claimed here.

**Where it binds.** This ruling binds the served plain-language `ControlPlaneService`
path, its real N4 source producer/`GenerationSourceRepository`, the runtime-store
WMR/context producer, N5, S8, and the existing fake-positive control-service and
normative-generation selectors named above. It preserves the protected no-context
refusal and the ordinary candidate path. It does not change status vocabulary,
authorize publication from candidate evidence, close R13, or assign a second owner.

### R1 scoped production-data feasibility follow-up (2026-09-27; implementation refinement, not a new principal choice)

**Decision status.** Denis's R1 option A is settled: build the served owner-bound N4→N5→S8 path. This note narrows the first candidate-band data seam; it does not reopen that choice. The separate per-active-basis R1/R5 question remains pending. Candidate profile admission is not an N5 prerequisite; it is an S8/authority prerequisite.

**Question and options with costs.** Can the selected path begin from current `production_data` without waiting for a new raw dataset, and what exact input is missing from the served path?

- **A — reuse the existing scoped DataState/WMR owner, selected for the first candidate test.** The source tree and builder already describe a real UA/fiscal-credit world, valid-time scope `2021-12/2023-07`, and exact dotted slots including `global.tax_rate` and `government.balance`. Materialize/read that WMR only after the single DesignProblem compile, through the active runtime-supplied tenant-bound store, and bind the same problem, candidate atom, WMR and N5 request. Cost: widen the existing owner's store contract, wire a post-compile resolver and add a served witness. No new raw-data acquisition or profile-signing appointment is needed for candidate N5.
- **B — wait for a new source covering the current served request's 2024–2026 data interval.** This is required before claiming that the current request is grounded in its requested interval; it delays that exact case. It is not required to start code against a separately declared retrospective case that matches the existing data.
- **C — treat the builder's 2026 Fabric query timestamp as evidence that its 2021–2023 source covers 2024–2026. Rejected.** `as_of_valid_time` is a bitemporal query coordinate; it does not change `WorldModelRecord.valid_time_scope` or the underlying data period.

**Premises.** The scoped production-data/source census is /Users/deniskopylov/.codex/scratch/e02-r1-production-census-docs-20260927/R1_SCOPED_PRODUCTION_DATA_CENSUS_20260927_v3.md@sha256:1f9c1e1e61f8d7ba7fee554170608f71eddc04418d14580494032487230474c5. Its exact manifests are: root `manifest.json` SHA `9e0e0aa0acd3c91f0120a80a2570be358ff16a63218abcd998f4d6f0212b6105`; Ukraine `FINAL_ARTIFACTS_MANIFEST.json` SHA `e65ca699c56b203097c5dc11d99fd171a337e89ee888132ce82e36557d87992d`; dataset catalog `manifest.json` SHA `bbd5e6794717fb00e153be01860021e29c664da6d0d3938f05daefdd527a92ea`; and L4/L5 source import manifest SHA `ae108ec29220d99c60293406375babc13c2a3cfa2ba0637999a603abc52e26c1`. The named manifests do not enumerate all production-data paths or exclude embedded/opaque WMRs; no such absence claim is made. `build_production_data_state_world_model_record` materializes a DataState WMR from the cited source. The exact tracked-source census finds its sole direct production call in `_production_composed_world_model_record`, which uses `.tmp/gy-s-composed-wmr-cas`; it is not the runtime API's tenant-bound store. The source census script /Users/deniskopylov/.codex/scratch/e02-r1-production-census-docs-20260927/r1_scoped_profile_census.py@sha256:424e7167a400ffe6a5ed06c435957466161ae02147bff5400f71e90b0e1f2a88 emitted receipt /Users/deniskopylov/.codex/scratch/e02-r1-production-census-docs-20260927/R1_SCOPED_PROFILE_CENSUS.json@sha256:62ec16b0943a78096a743f404270092df32b8e5868d56645f48188ffd1b78001: all 5,906 tracked Python paths under the explicit product roots `src`, `tools`, `tests`, and `examples` are included (2,696 `policy-engine/src`, 445 `policy-engine/tools`, 2,736 `policy-engine/tests`, 29 `policy-engine/examples`); all 2,743 test-directory Python files (including 7 under `examples/tests`) were AST-parsed with zero errors. It found five explicit `DesignProblem(...)` test call sites and 16 lexical builder-identifier occurrences. The exact source/test denominator and AST/caller inventory are complete for that Git tree; dynamically aliased invocations and serialized/opaque fixtures are not excluded. The builder's `FileSystemCAS` annotation narrows code that uses public `ArtifactStore` operations; reuse that owner through the runtime-supplied store and prove full build/readback there.

Within the five direct/qualified `DesignProblem(...)` calls found in all tracked test Python files, the served plain-language compile fixture and the recorded GY fiscal replay, none explicitly matches the source WMR's combined domain/time/target-slot scope. The served fixture is `social`, UA, valid/policy time `2026-05-15`, data time `2024-2026`, and lever slot `credit_access`; the source WMR is `fiscal_credit`, `2021-12/2023-07`, with no `credit_access` slot. The five explicit test calls default to `generic_policy`; overrides include `fiscal_policy`, `education_policy`, and `water_quality`, retain 2026 time fields and use underscore `government_balance`; none uses `fiscal_credit` or dotted `government.balance`. The recorded GY fiscal replay is `ua_msme_cgf_decisive_capture`, 2026, with underscore slot names. This is bounded to the enumerated source/test forms and does not exclude dynamic or serialized cases. The strict context owner matches domain and region exactly and checks target-slot membership exactly. Its current predicate does not compare problem `data_time`/`valid_time` with `WorldModelRecord.valid_time_scope`, so no permitted temporal relation is established by the green domain/slot check.

**Smallest next step and required witness (proposed; UNRUN).** Extend the existing DataState/WMR owner to accept the runtime's `ArtifactStore` contract, and expose its result through a post-compile resolver in the served control/generation composition. The first explicitly scoped test case may use UA/fiscal_credit, `2021-12/2023-07`, and the existing dotted `global.tax_rate` slot with the candidate `tax_relief_rate` mechanism, if the owner confirms that temporal interpretation. It must start through the served N4 path, bind to the one compiled problem and tenant-scoped store, execute the existing N5 method, and read back the real numerical result. Proposed identity: `tests/integration/core_runtime/test_served_cycle_world_profile.py::test_candidate_unknown_profile_reaches_real_n4_n5_through_tenant_store`. Preserve `tests/unit/runtime/http/test_control_service_di.py::test_served_nl_job_persists_real_candidate_proposal_without_n6_or_s8` as the ordinary no-profile N4 control.

Add a foreign-tenant/modified-WMR/unsupported-slot negative that refuses before N5; test temporal mismatch under the owner-declared candidate rule (typed unknown or limited computation, never current-scope authority); add a control using the explicitly compatible dotted slot; and `...::test_remove_candidate_world_binding_with_markers_retained_turns_positive_red`, which removes content/job/slot binding while retaining refs/status markers. Candidate profile admission stays `not_established`; this result cannot produce S8 authority or publication. If the user asks for the existing 2024–2026 `credit_access` case, preserve that scope as typed unknown/acquisition need until a compatible source is produced.

**P35/P37/P38/P40.** The census receipt above states the complete tracked source/test denominator and limits data-file claims to exact named manifests. Recompute source manifest/data bytes, Data Forge binding, runtime-store tenant/job scope, exact compiled-problem identity, temporal interval, dotted target slot, atom, N5 request and persisted result. Candidate profile admission is not established and is not needed for this computation; only S8/authority admission requires that profile/issuer evidence. P38 divergence: current strict context matching checks domain/region/slot but omits `data_time`/`valid_time_scope`; its green can therefore coexist with the divergent 2026 problem and 2021–2023 WMR. The separate Fabric query-as-of timestamp cannot fill this gap. P40 bucket: the temporal omission is the same R1/P38 scope-binding class one level deeper, not a new time-specific class. Widen the generic owner predicate; do not patch only the 2021–2023 fixture.

**Remainder and falsifier.** Existing data is sufficient to begin this bounded owner/candidate path, but no compatible compiled test problem, tenant-store WMR, served N5 invocation/readback, or N5 temporal-compatibility test is established. No source-data appointment is outstanding for the retrospective scope; S8 still requires its separate appointed issuer/current profile admission and signed value evidence. Revisit if the existing builder cannot operate on the runtime store without bypassing custody; if a changed/foreign/time-incompatible profile reaches N5; if removing binding while keeping markers leaves the positive green; if missing profile admission blocks ordinary candidate work; or if candidate N5 output upgrades to S8.

**Where it binds.** Existing `data_state_substrate.py` and `world_model_record.py` remain WMR producers, `ControlPlaneService._process_control_job` → the single `compile_and_run_recursive_generation_cycle` remains the served caller, the runtime-supplied tenant store remains the custody owner, and the existing N4/N5 consumers remain the computation path. This is an R1 prerequisite only, not R1/B01–B03 closure, a second WMR/context owner, or a new authority path.

### R1 DataState/S1 temporal-coverage refinement (proposal by E02-R2; 2026-09-28)

**Status.** This is an implementation-decision proposal for Denis’s already selected R1 Option A, not a new principal ruling. It does not reopen or claim completion of Option A. The existing DataState/S1 implementation owner remains identified; this proposal makes no new source-data, implementation-owner, issuer, signer, trust-root, or institutional appointment. It addresses how source-time evidence affects this WMR’s candidate disposition; any source semantics not established by authoritative evidence remain `not_established`.

**Question.** What time evidence may the existing DataState/S1 owner use to bind the first production WMR to a compiled candidate and let the existing N5 consumer use it, while preserving ordinary N4 computation when coverage is unknown?

**Decision status and owner.** Proposed; no per-source time semantics are decided here. The existing DataState/S1 implementation owner is identified and owns projection/mapping code; this is not a new implementation-owner appointment. Source facts must come from authoritative source metadata/documentation or independently reconciled data evidence. The implementation owner cannot assign meaning to an external `period_id` by convention. No new source-data appointment, institutional signer, or trust-root appointment is requested; this preserves the existing R1 premise that no source-data appointment is outstanding. If available authoritative evidence does not establish a field's temporal meaning, that input's time coverage remains `not_established`. Until then, option 3 governs this WMR's candidate disposition.

**Options and costs.**

1. **Recommended — have the existing DataState/S1 implementation owner derive and implement a source-specific temporal-selection rule from source-authoritative evidence.** For each of the five actual inputs, establish what `period_id` denotes, its time granularity, and the approved selection/aggregation rule; establish the interval-boundary interpretation and how annual rows relate to month bounds; state the household and budget selection/sampling rules; and derive selected-time coverage from the rows actually consumed. Bind that evidence to the WMR and candidate scope through the existing owners. Classify a source as `covered` only when available source evidence supports the requested scope, `not_covered` only when that evidence establishes a disjoint/unsupported scope, and otherwise `not_established`. Use existing typed limitation/status owners; do not add a declaration-only DTO. If available source evidence is incomplete, the DataState owner records the unresolved input as `not_established`; that is not authority to invent the field semantics or to request a new signer. Cost: the existing DataState/S1 owner reconciles current source manifests, producer metadata and documentation and implements only supported selectors; test owners add a marker-retaining interval mutation, in-range control and preserving N4 control, then replay the touched file. No new raw data is inherently required, but an unresolved or unsupported family may remain limited. This is the only option that can make the existing interval-shaped retrospective source a candidate N5 input without guessing; option 2 would define a different, as-of case.

2. **Narrow the first view to an evidence-supported as-of snapshot.** The existing DataState/S1 owner derives a single valid-time reference and deterministic as-of selection only where source-authoritative evidence supports it; the WMR records the resulting narrower scope/resolution and candidate N5 use is limited to a matching compiled case. Cost: this may be simpler than full interval aggregation, but it changes the first case from an interval to a point/as-of view, still requires source-specific annual/monthly semantics, and may require versioned WMR or consumer updates if typed fields change. Requests outside that snapshot are evidenced `not_covered` only when the data supports that conclusion; otherwise they remain `not_established`. No generic date-string comparison is implied.

3. **Interim unknown-scope candidate behavior.** Keep ordinary served N4 candidate work available with temporal coverage `not_established`. Candidate N5 computation with this WMR may proceed only if the existing result path can carry that limitation end to end; if it cannot, only this WMR-backed N5 disposition is `not_established`/not run. This does not refuse the request at the front door or forbid other candidate computation. Cost: the existing N5 result/projection path must be checked for honest limitation propagation; if it cannot express the limitation, the WMR-backed N5 witness waits for option 1 or 2, while N4 remains available. This is the interim default, not a claim that the existing N5 limitation mechanism is absent.

A generic comparison of `DesignProblem.data_time` with `WorldModelRecord.valid_time_scope`, or a raw `VARCHAR period_id BETWEEN ? AND ?`, is not an accepted option. It confuses distinct time roles, cannot map year-only rows to month intervals, and can both over-refuse candidate work and accept a label unsupported by consumed data.

**Premises.** The current DataState implementation accepts `period_start/end` and uses them for the L5 profile, preimage, and WMR `valid_time_scope`, but does not pass them into `_project_real_l4_payload`. That projection takes latest firm rows and registry resolution over their full files, averages all corrected-panel rows, sums an unordered first 100,000 budget rows, and selects the latest 100 household rows. Its `period_id` values are not used in the produced model fields. The five Parquet sources have `period_id: VARCHAR`; the repository’s synthetic fixture represents annual firm rows as `2022`/`2023` and corrected-panel rows as `2022`, while monthly fixtures use `2022-03`. The source `LOCAL_IMPORT_MANIFEST.json` lists paths/counts/bytes but no per-column time meanings or aggregation rules. Therefore the emitted `2021-12/2023-07` label is not evidence that those rows support that interval or `firm_month` resolution.

Evidence: `data_state_substrate.py@sha256:b29a8cab49c2a01312b27246cebc88829dbf1f0fa3e80f38bb13b76c0de80de4`; `capability_index_compiler.py@sha256:a8b5dc5d3caf6ae909f5faa94279ead3e8819afbf58af43f0ab33f14495d72cd`; `LOCAL_IMPORT_MANIFEST.json@sha256:ae108ec29220d99c60293406375babc13c2a3cfa2ba0637999a603abc52e26c1`; metadata-only addendum `/Users/deniskopylov/.codex/scratch/e02-r1-datastate-time-scope-20260928/R1_DATASTATE_TIME_SCOPE_ADDENDUM.md@sha256:728cc08f3fb07c7cbf723ae3b5014d14140230d10a81f7dc4dc14200365c80f0`. The separate static review rejected a generic `data_time`/`valid_time_scope` comparison as a proxy and over-refusal risk: `/Users/deniskopylov/.codex/scratch/e02-r1-candidate-n5-patches-20260927/time-guard/R1_TIME_SCOPE_CANDIDATE_INDEPENDENT_REVIEW.md@sha256:7195aaee03de64908a9b356ef3e88dfaea898ebae281b1963a099c606e070a42`. Baseline decision-record pin before this proposed addition: `DECISION_RECORDS.md@sha256:de1c2c534b8d59ffba32b7fced553689a05afc6e02fff02ed88da3d40dcbbe49`, §R1 scoped production-data feasibility follow-up, lines 536–558. Source records were inspected only through schemas/Parquet footer metadata for this time-semantics review; no row census or test is claimed.

**Authority and candidate effects.** These are evidence classifications for this decision, not a proposal for a new public enum. The choice affects only whether this existing WMR may serve a specific compiled scope. `covered` permits the existing owners to bind this WMR to the exact problem, N4 source, tenant-scoped runtime store, and N5 request for candidate computation. `not_covered` withholds this WMR from that scope while preserving ordinary N4 candidate work and a typed path to another source/acquisition. `not_established` must travel forward as unknown: ordinary N4 remains available, and an N5 candidate calculation may proceed only if its result remains explicitly scope-limited; if the current N5 artifact cannot express that limitation, report the N5 disposition as `not_established` without turning it into a front-door refusal. Neither unknown nor candidate output becomes S8 authority. This decision does not appoint a profile signer, NCM producer, S8 principal, or deployment trust root; it does not authorize publication or change the separate S8 gate.

**Remainder and acceptance signal.** The DataState/S1 implementation owner is already identified; no new owner appointment is requested. Source-authoritative time semantics for the five inputs remain unestablished by the inspected manifest/fixture evidence, and the code lane must not guess them. Once existing source evidence supports a rule, the smallest implementation owner remains `runtime/quality/data_state_substrate.py`, with a served caller only after the existing runtime-store/context bridge is ready. Add a synthetic-Parquet test that holds L5/WMR status markers fixed, changes only the selected interval, and proves the actual projected values change according to the rule; include an in-range expected-value control, an evidenced-out-of-range case, and an unknown-time case where N4 continues and N5 either carries the typed limitation end to end or only this WMR-backed N5 disposition is `not_established`. Removing the row-selection predicate while leaving all markers intact must make the interval test fail. Then demonstrate one served N4→N5 result on the evidence-supported retrospective scope through the exact runtime store. This is a prerequisite witness, not full R1 closure.

**Falsifier / revisit trigger.** Revisit this choice if the existing DataState/S1 owner finds source-authoritative evidence that establishes a different time granularity/coverage or supports another selection rule for any of the five inputs. If evidence remains absent for a required input, keep that input and this WMR-backed N5 disposition `not_established` under option 3; absence alone does not reopen the decision or create an appointment. Reassess candidate behavior after checking whether an N5 result can carry the unknown limitation end to end. The implementation claim is falsified if shifting only out-of-range source rows changes the admitted result, if shifting the requested interval does not change selected rows where the source-backed rule requires a change, or if removing the predicate with markers retained leaves the test green. The preserving falsifier is independent: unknown profile/time coverage must not stop ordinary N4 or any candidate N5 computation whose result can truthfully carry the limitation.

**Where it binds.** This binds the existing DataState/S1 WMR producer and the selected served `POST /api/v1/control/runs/nl` → `ControlPlaneService` → `compile_and_run_recursive_generation_cycle` candidate N4/N5 route, after R13 wires the producer and context through the active tenant-bound store. It does not bind generic `DesignProblem.data_time` parsing, all WMR producers, NCM source issuance, S8 schedules/frontiers/authorization, signer trust, epochs outside this WMR, publication, debt-register closure, or governed reissue. R1 and R13 remain open until their full served/custody evidence and independent closure signals are met.

**Pattern pass.** P08 (valid versus transaction time), P10 (time-bounded state must change materially), P27/P31 (reuse DataState owner; fix the source-selection class), P35 (enumerate all five inputs; do not generalize from fixtures), P37/P38 (construct coverage from consumed rows, not declared labels), P40 (same R1 scope class one level deeper), and P41 (replay touched test files). The R1 candidate-path review already warns that a generic time comparator is the same class of proxy and over-refusal; this draft chooses the owner-specific evidence seam rather than another parser or gate.



### R1 source-time and byte-provenance evidence update (2026-09-28; no new ruling)

This evidence update preserves Denis’s selected Option A above. It makes no new principal ruling, source-data appointment, implementation-owner appointment, or signer/trust appointment. It corrects the evidence boundary for the first real-data N5 witness: the read-only provenance review found **no source-backed minimal positive real N5 subset yet**. All five inputs named by `DataStateSubstrate._default_data_state_paths` have `period_id: VARCHAR`, but source-time meaning and completeness are not established uniformly. Examples are the EDR `2025-01` fallback label, an annual row labelled `2022-12` under inherited monthly granularity, a budget projection over an unordered first 100,000 rows without a period filter, PFU filename dates not reconciled to report dates, and household coverage ending at 2021-12. The DataState SQL also projects across whole files while declaring 2021-12 through 2023-07. These are source-specific questions for the already identified DataState/S1 owner; string comparison or nearest-period selection cannot answer them.

The byte predicate is separate: the local import manifest gives aggregate inventory/bytes but no per-file normalized-Parquet checksum, the expected source-specific normalized-artifact sidecar is absent, and the imported root points to a different historical path. Thus the current evidence does not bind the actual five normalized files to their raw-source snapshot, normalizer version, and period transforms. A path, footer statistic, `period_id`, WMR interval label, or Fabric query-as-of timestamp is not that binding. Production rows were read-only; large inputs were not bulk-scanned or content-hashed. Exact evidence: `/Users/deniskopylov/.codex/scratch/e02-r1-datastate-provenance-20260928/R1_DATASTATE_SOURCE_TIME_PROVENANCE.md@sha256:9b9c1cd2b9cd1144c09408bf3f03e63ba5ae5763728307f686d2cf37c76f511a`, including its five-input denominator and unresolved-by-construction limits.

**Options and costs for this residual.** (1) Continue the already selected Option A by having the existing S1/DataState owner derive only source-supported time/grain/selection and sparse-coverage rules, bind consumed normalized bytes to producer/source receipts, and then bridge the resulting typed profile through the existing N3/context/runtime-store/N5 owners. Cost: source-specific reconciliation plus persisted byte receipts and served tests; unsupported inputs/scopes remain limited. No new owner or institutional appointment is inferred. (2) Treat path, aggregate manifest, period labels, or current SQL output as sufficient. Rejected: it is cheaper, but repeats the P37/P38 proxy and could admit post-period or unbound rows. (3) Refuse ordinary candidate work until all source semantics are known. Rejected: it over-refuses. Interim behavior is N4 candidate continuation with typed `not_established`; this WMR-backed N5 disposition remains `not_established` unless the existing N5 result can carry that limitation honestly.

**Premises and gate predicates.** Five configured inputs are the complete DataState input denominator (`data_state_substrate.py@sha256:b29a8cab49c2a01312b27246cebc88829dbf1f0fa3e80f38bb13b76c0de80de4`). Source-code transforms and Parquet footer labels are `recomputed`; their connection to these imported bytes and their validity semantics are `not_established`. Actual source/normalized-byte provenance is `not_established`; the imported manifest lacks per-file digests. P38 divergence: the intended property is period-correct, source-bound evidence in the WMR; the current predicate combines whole-file/latest aggregates and an arbitrary budget cap. A `2025-01` EDR fallback or `2024-07` firm-panel row can therefore influence a WMR declaring a 2023-07 end. Relevant design/PDC sources are the bridge map `/Users/deniskopylov/.codex/scratch/e02-r1-positive-bridge-map-20260928/R1_POSITIVE_BRIDGE_DESIGN.md@sha256:bf929c808f1fc92dc9eadaa3d7399a267a744dbcc1cb3d4e15b60abd90a2c7ce` and the failure-pattern register `policy-engine/docs/reference/policy-design-case-failure-patterns.md@sha256:64f9fa40453980d9128443ee34a4bf3298b71c157a5ebcc3bd6cb786abeb090a` (P08/P10/P14/P27/P31/P37/P38).

**S8 remainder.** The served S8 consumer exists, but the runtime app/container default `NormativeAuthorityTrust` is empty. No real configured signer/mandate/current trust root, source-bound signed value schedule/frontier, or positive real N5 source/NCM/calibration slice was established by these reviews. A fixture-generated key proves test mechanics only. This is a separately supplied institutional/authority prerequisite: candidate N4/N5 cannot silently acquire S8 authority, and an absent/stale trust record must leave S8 typed-blocked with zero ranked recommendations. This evidence update neither appoints that signer nor changes the selected Option A; it records why real S8 authorization is still unavailable.

**Remainder and falsifier.** Still needed: owner-supported time roles, granularity, interval boundaries, deterministic selection/aggregation/cap and missing-period semantics for every input actually consumed; byte-exact per-input/source/normalizer binding; then a served, authenticated N4→N5 run that persists and rereads the exact handoff, selected bytes, WMR/context and N5 receipt through the runtime tenant store. Falsify by changing an input’s bytes while retaining manifest/profile markers, or changing only an out-of-period row while markers remain: provenance/selection must refuse or produce a typed limitation and the marker-retaining test must turn red. Revisit if source-authoritative evidence changes a period rule, establishes a supported profile, or contradicts the recorded coverage. A preserving control is the existing ordinary no-profile N4 candidate test: it must continue with typed scope limitation and no S8 authority.

**Where it binds.** This narrows only the first DataState/S1-backed R1 candidate N4/N5 slice and its S8 disposition. It does not close B01–B03/R1, create a second owner, authorize a profile from NL text, change protected-mode refusal, appoint S8 trust, or close GY-PR1, promotion, publication, or any debt row.

### R1 controlled-profile owner-bound N4→N5 slice (Denis’s follow-up direction; 2026-09-28)

**Decision and scope.** Denis retains the already-selected Option A and chooses the next engineering slice: exercise one controlled, explicitly test-only profile through the owner-bound N4→N5 handoff, using the runtime-supplied tenant store. The served witness must persist and reread the context and N5 result against the same request, tenant, job, compiled problem, and candidate. Marking a fixture “controlled” is test scope; it is not production source provenance or authority. This selection does not claim a source-backed real-data N5 run, S8 authority, or B01–B03/R1 closure.

**Options and costs.** (1) **Selected:** prove the N4→N5 owner/context/store bridge with a controlled fixture now. It requires a served positive, foreign-tenant and altered-binding negatives, a marker-retaining owner-context removal probe, an ordinary-candidate preserving control, and touched-file P41 replay; it lets bridge engineering proceed while source semantics remain unresolved. (2) Wait for all five production DataState time meanings and normalized-byte provenance before demonstrating any positive N4→N5 handoff. This avoids a fixture-only witness but holds independent bridge work behind the source owner’s evidence task, so it is not selected. (3) Treat fixture output as real-data validity or S8 evidence. Rejected: this would confuse test mechanics with source grounding and authority.

**Premises and gate predicates.** Existing CycleSubstrateContext and N5 owners are the intended path; the test must use their production composition and runtime-supplied store, not a test-only parallel resolver or root-rebuilt CAS. Job/tenant/problem/candidate binding is recomputed from persisted artifacts and request context. Production time coverage and normalized source-byte binding remain `not_established` as recorded in the five-input DataState review below. P38 divergence is explicit: a synthetic fixture can make N5 numerically execute while saying nothing about whether the production rows support the declared interval; it must not be presented as source-valid evidence.

**Proposed witness (not yet present or run).** Positive: `tests/integration/core_runtime/test_served_cycle_world_profile.py::test_controlled_profile_reaches_real_n4_n5_through_tenant_store`, with actual N4 production, owner-resolved context, actual N5 invocation and persisted-result readback. Negative: foreign tenant and changed problem/candidate/context bindings refuse before N5. Removal probe: `::test_owner_context_removal_with_markers_retained_turns_n5_red` keeps artifact/ref/status markers but removes the owner-produced context link. Preserving control: `tests/unit/runtime/http/test_control_service_di.py::test_served_nl_job_persists_real_candidate_proposal_without_n6_or_s8` continues an ordinary no-profile candidate without requiring S8. The four-base replay must cover every touched test file and measure this Appendix-B selector’s input-closure attribution; keep attribution unresolved unless the fixture/plugin inputs are reconciled.

**Remainder, owner, falsifier, and revisit trigger.** Runtime HTTP/generation owners implement the bridge; the DataState/S1 owner still owns source-specific time semantics and Data Forge still owns normalized-artifact provenance. Real-data N5 stays limited until those premises are evidence-backed. S8 stays limited until current signer/mandate/trust and source-bound signed value evidence are independently admitted. **Falsifier:** keep status and reference markers but remove the owner-produced context link or N5 consumption; the served positive must turn red. If it remains green, reopen the slice and widen the owner mechanism. A foreign job or tenant must refuse, while the no-provider ordinary-candidate control must pass. Revisit when the DataState owner supplies source-supported period rules and byte bindings, or if the controlled path uses another store/context owner or a fixture-only shortcut. No epoch is reissued, no data is restamped, and no register row is closed by this decision.

**Where it binds.** This direction binds only the next R1 N4→N5 engineering witness and its tests. It preserves N4 candidate availability with a typed unknown, refuses to turn fixture status into authority, and leaves real-data validity and S8 authority as separately measured residuals.

### R1 implementation evidence addendum — bounded served N4 fallback (`031e2133c`, 2026-09-28)

This is an implementation evidence update under Denis's binding option-A ruling above; it does not introduce a second principal choice or claim that option A is complete. The served worker passes `n4_proposal_only=True` only for its validated persisted `simulate_only_attempt` route. With no CycleSubstrateContext and no explicit N4 port, real N4 work can be persisted and reopened as the v2 `N4CandidateProposalSimulationRecord`. The v2 artifact records `simulation_unavailable/cycle_substrate_context_not_established`; N5/N8/N9/S8 are `not_run`. Terminal N4 failures retain their actual disposition. A supplied owner-bound context is not downgraded to proposal-only and trips `n4_proposal_only_context_conflict`.

**P37/P38.** The route selection is recomputed from the validated persisted job intent; missing owner context is carried as a typed unknown on this candidate-only outcome and is never accepted as an S8 predicate. The property is ordinary candidate computation despite unknown scope while authority stays gated. This implementation covers the persisted no-context `simulate_only_attempt` seam; an explicit N4 port without context remains refused, and this commit does not make N5 run. That is the bounded divergence, so no broad B01–B03 or R1 closure follows.

The marker-retaining route sentinel is `test_simulate_only_served_worker_persists_computation_without_s8_or_publication`; the owner-bound-context selector refusal is `test_simulate_only_n4_selector_refuses_an_owner_bound_cycle_context`; the independent context-to-N5 preserving control is `test_http_recursive_route_carries_one_context_to_n5_owner_block`. The final P41 receipt compares seven cohorts / 144 common identities against `9e0bb0d342ae704f17773ca2c815ef620a309af3` and reports zero common pass→nonpass. Receipt /Users/deniskopylov/.codex/scratch/e02-r1-post-structural-20260928/R1_POST_STRUCTURAL_P41.json@sha256:01573aee7a89896bcbce52cc977b3501cf3dacafdb2da4234d4ee636b44f2aed; JUnit: /Users/deniskopylov/.codex/scratch/e02-r1-post-structural-20260928/intent-final.junit.xml@sha256:b7b41469a93900b5025f41583fb40ca487202b7b8280a649220d12bb81cc59d2, /Users/deniskopylov/.codex/scratch/e02-r1-post-structural-20260928/http.junit.xml@sha256:597ebccf595c7e72b11b81c29373773952c04c5a1511778320eeff98402f06c8, /Users/deniskopylov/.codex/scratch/e02-r1-post-structural-20260928/nl-acq.junit.xml@sha256:6f18bc2b29bbc8fe7d56f878152081fc800d66f406dd597346f2902f33656eb6, /Users/deniskopylov/.codex/scratch/e02-r1-post-structural-20260928/source.junit.xml@sha256:d68b72024d5bb6e7d8b307bbf5dc69cc134096475f13d9f66c2772cbc4ef3a9f, /Users/deniskopylov/.codex/scratch/e02-r1-post-structural-20260928/context-conflict.junit.xml@sha256:67175c8407d7d424b927ce6acde926aa36adbe706ed17596662c9822a62bac00, /Users/deniskopylov/.codex/scratch/e02-r1-post-structural-20260928/epoch-context.junit.xml@sha256:9f95fc444264dfab5b11713fa00b7ee1ad04b48d689ebe2474be86d9ca4548cd. The four-base Appendix-A/B and touched-file replay remains `UNRUN`.

**Remainder and falsifier.** Option A still requires an ordinary served request to use a compatible candidate-grade WMR and the runtime-supplied tenant store, resolve the same owner-bound context through the existing N4 source handoff, execute N5 and verify its result, then separately prove S8 consumes current context and signed evidence. Foreign, stale, changed-WMR and protected-action negatives plus the full four-base replay remain required. Revisit this bounded route if removal of its server-selected selector still leaves it entering no-context N6, if a terminal N4 error is mislabeled `simulation_unavailable`, or if a valid owner context is silently discarded.

**Where it binds.** This evidence binds only the served `simulate_only_attempt` no-context proposal path and its generation-source v2 serializer/replay. It preserves the R1 option-A binding for the real owner-bound N4→N5→S8 path; it authorizes no authority, publication, governed artifact reissue, epoch restamp, finding closure, or debt-register edit.

## R2 — CYC-05 strangle proof, deployment identity, and historical replay

**Question.** How should a persisted N6 run retain the claim that production does
not route through `run_fixture`, without making historical replay depend on a live
source checkout or treating current-source drift as proof that history is invalid?

**Options and costs.**

1. Re-hash all Python files under `src/polisyos` at every consumer replay. The
   implementation uses `source_root.rglob('*.py')`; non-Python files are outside
   that denominator. This is simple to understand, but every consumer and packaged
   deployment pays for live source access; unrelated Python edits can invalidate
   old runs. Runtime-quality and deployment owners pay the repeated scan and
   checkout dependency; historical consumers pay the false-staleness cost.
2. Remove the strangle receipt and stop checking the production-path property. This
   removes false staleness, but the runtime and public projections lose evidence for
   a safety-relevant orchestration boundary. Runtime maintainers save the gate cost;
   N9 and public-projection consumers pay with an unverified production-path claim.
3. **Proposed lean:** keep the census over its declared source/build inputs as a
   source/deploy-time tooling gate. Extend the existing canonical identity owner to
   expose a typed deployment-identity projection for run-start and pre-N9 admission;
   do not create a second identity calculation. The owner’s full identity comprises
   the baseline of `pyproject.toml`, `uv.lock`, every file in the resolved authority
   import closure, and the Python runtime manifest, combined with the authority import
   closure and loaded-code manifest. Capture that already-admitted census receipt
   and the loaded deployment identity at N6 run start. Before N9 invokes promotion,
   require the run-start identity, the census-bound identity, and the currently
   loaded canonical identity to match exactly, with the census verdict passing.
   Missing evidence yields `not_established`; mismatch yields `stale`; either
   withholds N9 authority while ordinary candidate computation continues. The
   direct AST call census is not complete call-path proof: aliased or reflective
   dispatch, and any blanket caller allowlist, remain `not_established` unless
   independently reconciled. A declaration alone cannot turn an unresolved path
   green. The source/deploy census receipt must declare the complete inspected
   source/build inputs, the derived denominator, and dispatch classes unresolved
   by construction. Its instrument verdict is `pass` only after complete inspection
   with no forbidden production route and no unresolved authority-relevant class;
   `fail` when completed inspection finds a forbidden route; and `UNRUN` when
   inspection errors, the denominator is incomplete, or aliased/reflective dispatch
   remains unresolved. Inspection failure is never substituted with an exception
   or a green marker. This instrument verdict is separate from runtime currentness:
   currentness is `current` only for an identity-bound `pass` whose run-start,
   census-bound, and loaded identities match; `stale` for a proven identity
   mismatch; and `not_established` for census `fail`/`UNRUN`, missing binding, or
   unresolved coverage. This instrument/currentness separation follows the
   independent decision-draft review
   `/Users/deniskopylov/.codex/scratch/e02-r2-decision-drafts-independent-review-20260925.md@sha256:fc7103792e6525d032101dba8208336f223d3f21c5e87118f5407bc66b21af4c`.
   The current identity is computed inside private confidence-ledger
   functions; no
   public packaged API exposes this pre-N9 admission gate. Extend that owner and
   wire the gate before N9. Persist its decision in `GenerationCycleRun` v3 for
   later replay, but a v3 field constructed after N9 cannot authorize the N9 call
   that precedes it. Historical replay must not depend on today’s checkout. Require
   byte-exact v1 replay against the pinned v1 bytes; v2 byte-exactness remains
   `UNRUN` / `not_established` until an owner supplies an original v2 payload and
   byte oracle. The costs are a public owner API, pre-N9 bridge, schema migration,
   and historical payload/serializer evidence for each version. The confidence-
   ledger owner pays for its public identity API/input contract; runtime-quality
   pays for the census and pre-N9 bridge; package/deployment and consumer owners
   pay for source-free resolution and typed status wiring; test owners pay the
   full four-base and historical-byte witnesses.

   Identity coverage is a precondition, not implied by exporting the current ledger
   digest. First enumerate whether the frozen confidence-ledger import/deployment
   closure actually contains the production N6 route and source/deploy gate result.
   Two costed carrier choices remain for the principal:

   a. Extend the canonical Confidence Ledger closure and epoch inputs to include the
      measured N6 route and source/deploy gate inputs. This preserves one identity
      owner and one bound identity, but expands its input/schema contract, requires
      complete closure measurement and packaged producer/consumer wiring, and may
      require an authorized identity transition. The canonical closure's current
      N6 membership is `UNRUN`. The Confidence Ledger owner pays the closure/schema
      expansion and authorized transition evidence; runtime-quality and packaging
      owners pay measured route inclusion and installed-consumer wiring.
   b. Keep the canonical identity inputs fixed and add a typed census carrier whose
      exact bytes/ref are bound to that canonical identity. This avoids widening
      the identity inputs but adds a second persisted record, producer, package or
      guarded-store resolution, admission verifier, retention rule, and consumer
      choreography; its binding must be independently reconciled. Runtime-quality
      and artifact owners pay the carrier lifecycle; deployment/package owners pay
      offline resolution and retention; the Confidence Ledger owner still pays for
      the single canonical identity binding.

   Both choices require a real source-free packaged bridge: an installed runtime
   must resolve the owner-produced identity and census evidence, verify their exact
   binding, and expose one typed currentness assessment to run-start and pre-N9
   admission. The source-free carrier and bridge are `not_established` /
   `bridge_missing`; a checkout path, private `__file__` discovery, or caller-supplied
   digest is not a substitute. Until a carrier is admitted, old runs may replay as
   historically valid with currentness `not_established`; candidate computation
   continues under its typed limitation and N9 authority is withheld. Neither
   choice authorizes restamping trust-posture pins or promotion epochs; any future
   identity/schema change must use its separately authorized transition and
   readback. A bare ledger identity that does not establish N6 route coverage is
   insufficient for `current`.

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
(`src/polisyos/runtime/quality/confidence_ledger.py@c3775ce0a96966fcbc46fa243e5cc03f3a80c84b`,
`runtime/quality/confidence_ledger.py::_deployment_relative_paths_from_closure`,
`_deployment_baseline`, `_deployment_identity_from_baseline`).
`_admit_loaded_runtime` is private and takes a repository root; the run validator
has no public packaged currentness API from that owner. A source checkout’s mere
presence at validation time is not deployment identity. The register’s
`merged-lanes-need-a-reissue-path-neither-lane-declared` row remains open on its
engineering reissue path; this proposal does not authorize a reissue or restamp.

The read-only identity census confirms that the current canonical closure is rooted
in `confidence_ledger` and does not automatically cover the N6 route. Exact frozen
closure membership remains `UNRUN`; the census found no direct
confidence-ledger-to-generation-cycle import. The existing ledger digest alone is
therefore not evidence that the N6 production route or its source/deploy gate is
covered. Bind the gate to the canonical identity only after measuring membership,
or extend the canonical owner to include the N6 route/gate inputs. Evidence:
`/Users/deniskopylov/.codex/scratch/e02-r2-r2-identity-census-20260924.md@sha256:7cd9dfc6378ff929c21016cc507633f75f05ecbcf4f5ad4c2f8aaf685f06903a`.

At the inspected base, `StrangleReceipt` documents that it does not establish build
or deployment identity and admits that alias/dynamic-call completeness is not
established. It computes a source hash over all Python files under `src/polisyos`
using `source_root.rglob('*.py')`; non-Python files are outside that denominator.
`verify_current` and `validate_generation_cycle_run` require a live `repo_root` and
compare those current Python files during validation
(`runtime/quality/generation_cycle.py`).
The classifier recognizes only direct AST calls whose final callee name is
`run_fixture`. It also exempts every direct caller under
`src/polisyos/runtime/quality/workspace/loop.py:` by path prefix; that exception is
not proof that each exempt caller is unreachable from production. An alias such as
`fixture = loop.run_fixture; fixture()` or reflective `getattr(loop, name)()` is
outside the observed direct-call predicate. Those cases can leave the `strangled`
marker green while violating the production-path property.
`GenerationCycleRun` currently accepts v1 and v2; extending it requires v3 plus
historical projections for both older versions. The confidence ledger already
computes the canonical loaded-runtime identity internally, but this code path does
not make that identity a public run-currentness capability or bridge it into the
generation-cycle consumers.

The current `GenerationCycleController.run` calls `_promote_completed_generation`
and applies its N9 result before constructing `GenerationCycleRun` and recomputing
`StrangleReceipt`. Therefore a v3 run field added at construction is too late to
gate the same N9 admission; the identity/census proof must already be available to
the live invocation before promotion
(`src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`).

The tracked historical run fixture is v1: `historical_artifacts.py` pins Git blob
`adab90797d1d1562ae252c076883bc5af6d77ce6`. The associated
`test_tracked_owner_epochs_remain_exactly_readable` validates the v1 model and
compares flattened JSON leaves after model dump; it does not compare serialized run
bytes against the pinned blob
(`tests/unit/runtime/quality/historical_artifacts.py@4a8d4bf763b2295da64e5e418f96fbf7c3ddd3c1`;
`tests/unit/runtime/quality/test_generation_source.py@dfbffbf32f90920a0b67310e4dd1d94b45e9308c`).
The separate generation-cycle contract reissue test preserves raw historical
contract bytes, not the `GenerationCycleRun` v1 serializer bytes
(`tests/repo_quality/tools/test_layer3_gy_generation_cycle_contract.py@6ff8b4691de6250900154aac5e64f3ac7898c605`).
No tracked v2 historical run payload or byte oracle is established. Consequently
v1 byte-exact serializer replay is still a required test, and v2 replay is
`UNRUN` / `not_established` until its owner supplies the original captured payload
and a byte oracle; a payload freshly generated by the current producer cannot
stand in for either historical record.

The wider tracked GY artifact census is not one fixture: it contains 9 N6-v1
occurrences across 6 distinct run IDs, 1 N6-v2 occurrence, 7 recursive-v1 objects
with 7 distinct parent hashes, and 6 compiled-v1 objects with 6 distinct hashes.
The 9 v1 occurrences include duplicate historical/current representations in the
depth-universality record; the pinned v1 blob is an older serialization of the same
run ID represented by the current v2 generation-cycle contract. This does not
establish an original v2 run payload or byte oracle. The serializer denominator
must walk the full tracked fixture/receipt set, retain occurrence paths while
deduplicating identical payloads, compare exact raw/canonical bytes or owner hashes,
and verify every recursive and compiled parent hash. Use the full-census shape in
`tests/unit/runtime/quality/test_cyc_02.py@fe5ff4c56828a37b5c50fe5954dc461fec677f46b420a222d4f4511583154a72`.
The read-only census and source files are
`/Users/deniskopylov/.codex/scratch/e02-r2-r2-history-design-review-20260925.md@sha256:5eb1de2a6654a7757d4f7a0f4cc613c672658c2f143639957e6c55a1d82159a`,
`policy-engine/architecture/policy_design_case/layer3_gy_composition_certificates.json@sha256:275aae6c25d7a5f1b423f794c895d5ba5abc2d073c958177e007eb086b47c43f`,
`policy-engine/architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json@sha256:4126ab96594433343249af6a493b192817b2ae04995852ea8a90b46e99e02173`,
`policy-engine/architecture/policy_design_case/layer3_gy_generation_cycle_contract.json@sha256:d8c332b21dea297d80e2d099de02d05066c2912b230a31535962f549aa531522`, and
`policy-engine/architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json@sha256:c0917aebdef8e1ee44f07ce4bc6b84ccc93ca04becb63a1307ebb171a56013b7`.

**Proposed choice; principal status.** Adopt option 3's source/deploy census and
pre-N9 currentness gate as the lane proposal, subject to principal ruling on the
carrier. Prefer option 3a, extending the existing canonical Confidence Ledger
owner, because it keeps one identity owner; choose option 3b only if the measured
closure cannot correctly cover the N6 route/gate without a separate typed carrier.
Neither is implemented or source-free packaged today. Do not compute a parallel
identity in `generation_cycle.py`, infer currentness from checkout availability, or
use the bare ledger digest before N6 coverage is measured. At N6 run
start, capture the owner-produced canonical loaded-deployment identity and the
passing census receipt bound to that exact identity. Before
`_promote_completed_generation` admits N9, require an exact match among the run-start
identity, the census-bound identity, and the identity of code currently loaded by
the runtime. A passing match yields packaged currentness `current`; a changed
identity yields `stale`; absent owner/census evidence or failed inspection yields
`not_established`. Both `stale` and `not_established` withhold N9 authority, while
ordinary candidate computation may continue under the typed limitation. The census
gate proves only the deployment-code/production-path predicate. It does not prove
tenant context or custody, N4 handoff consumption, candidate-byte identity,
world-model currentness, or EvalSafety; those authority gates remain independently
required.

Persist the run-start admission and its typed result in `GenerationCycleRun` v3 for
later audit and replay, but do not treat that post-N9 field as the live pre-N9 gate.
Historical validity is orthogonal to packaged currentness: a run may be
`historically_valid` and current, stale, or `not_established`. Historical replay uses
persisted bytes, version, and receipt, never today’s source tree. Require a byte-
exact v1 serialization comparison against the pinned v1 blob; the existing leaf-
equality test does not close it. V2 byte-exactness remains `UNRUN` /
`not_established` until the historical owner supplies a captured v2 payload and
byte oracle; the current producer cannot synthesize that evidence. This draft does
not assert the owner API, pre-N9 bridge, exact v1 replay, or v2 payload evidence is
already present.

**P37 — gate predicates at admission.**

- The strangle census’s declared file/deployment denominator must be derived from
  the actual shipped source/build inputs (`recomputed`); a producer’s claimed count
  or a search-index result is insufficient (`consumer_asserted`). Its receipt
  declares inspected source/build inputs, the derived denominator, and
  unresolved-by-construction dispatch classes. The instrument returns `pass` only
  for complete inspection with the guarded property established, `fail` when a
  completed inspection proves a forbidden production path, and `UNRUN` on
  inspection error, incomplete inputs, or unresolved authority-relevant dispatch.
  Runtime `current | stale | not_established` remains a separate identity/currentness
  result; `fail` or `UNRUN` cannot yield `current`.
- The canonical identity is recomputed by the confidence-ledger owner from the
  project and lock files, authority-import-closure files, Python runtime manifest,
  authority import closure, and loaded-code manifest. The field-level predicate is
  `recomputed`; exposing it through a source-free packaged run-start/pre-N9 typed
  admission bridge is currently `bridge_missing`. Option 3a adds the N6 route and
  census inputs to this identity's closure/epoch; option 3b binds a separate typed
  census carrier to that exact identity and must independently reconcile the
  binding. Both require the installed package to resolve and verify the evidence;
  an absent carrier is `not_established`. The gate must compare exact run-start,
  census-bound, and currently loaded identities before N9. A v3 field created after
  promotion is too late; missing evidence is `not_established` and mismatch is
  `stale`, either with no N9 authority while candidate work continues. Whether the
  current closure contains the production N6 route and source/deploy gate is
  `not_established` until the frozen closure is enumerated. A ledger digest without
  that coverage cannot establish N6 currentness.
- Historical validity is a separate predicate from packaged currentness. The v1
  pinned bytes exist, but current `GenerationCycleRun` validation compares parsed
  leaves rather than serialized bytes, so exact v1 replay is `not_established` until
  byte equality is tested. No original v2 payload/byte oracle is established;
  v2 byte replay is `UNRUN` / `not_established` until the historical owner captures
  the actual payload. A historical-valid run can independently be current, stale,
  or `not_established` for the deployed package.
- Direct AST call edges can be recomputed, but reflective/aliased entry paths remain
  `not_established` unless the deployment census independently covers them. That
  limitation must be frozen in the receipt; it cannot be converted to “no callers”
  by a declared allowlist. A path-prefix exemption remains consumer-asserted until
  behavioral production reachability is independently reconciled.

**P38 — property and divergence.** Property: the deployed production N6 path does
not route through `run_fixture`, the exact admitted deployment identity is current
at the N9 authority boundary, and historical runs replay without requiring today’s
source checkout. Current implementation: `GenerationCycleController.run` calls
`_promote_completed_generation` and applies the N9 result before constructing
`GenerationCycleRun` and recomputing `StrangleReceipt`; the latter recomputes only
after promotion. Later `verify_current` hashes Python files under `src/polisyos`
through `source_root.rglob('*.py')`, excludes non-Python inputs, and requires
`repo_root`. No public packaged identity API or pre-N9 bridge is wired.
Divergent case: absent or stale run-start identity/census evidence cannot withhold
the already-executed N9 promotion; adding a currentness field only to the returned
v3 run does not fix that order. Separately, `test_tracked_owner_epochs_remain_exactly_readable`
parses the v1 run and compares JSON leaves, not bytes. V2 has no original payload
or byte oracle, so its historical serializer cannot be verified from the current
producer. A comment-only edit to `lex/simulator/report.py` changes the broad source
receipt, but whether that file is in the canonical authority import closure and
therefore changes deployment identity is unmeasured. That example does not establish
that the edit is unrelated to deployment identity or that identity remains fixed.
A reflective `getattr` route to `run_fixture` also remains a bounded
`not_established` class unless the census covers it; a clean direct AST census is
not complete call-graph proof. More specifically, `_call_name` recognizes only
`Name` and `Attribute` call targets, while `_is_allowed_fixture_caller` exempts all
direct callers beneath one `workspace/loop.py` path prefix. An aliased call can be
missed and an unexpected production call within that prefix can be blanket-exempted;
both can leave the `strangled` status green while the actual production-reachability
property is false. Neither a direct-caller list nor that prefix is an independently
reconciled production call graph. The confidence-ledger import/deployment closure
may also omit N6 route code because it is rooted in the ledger's own dependencies;
the live N6 closure membership is `UNRUN`. If a route change lies outside that
closure while the gate compares only the bare ledger identity, it can remain
`current` for a changed N6 path. This is the P38 divergence the owner extension or
identity-bound gate receipt must falsify; exporting the ledger digest alone cannot.
(`src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`;
`tests/unit/runtime/quality/test_generation_source.py@dfbffbf32f90920a0b67310e4dd1d94b45e9308c`).

**Remainder.** This does not authorize changing the canonical deployment identity,
trust-posture pins, or GY promotion-contract epochs on merge. Any required reissue
needs its own authorized transition and readback. It also does not decide that all
dynamic Python dispatch can be statically proven; unresolved dispatch stays an
explicit limitation and cannot support a stronger authority grade. The full identity
includes the project/lock baseline, Python runtime, authority import closure, and
loaded-code manifest; it is not a manifest-plus-lock-only binding. This proposal
does not claim currentness is already available to packaged run consumers, nor that
the `lex/simulator/report.py` comment probe leaves canonical identity unchanged.
It also does not treat the current `workspace/loop.py` path-prefix exemption or a
clean direct-call AST scan as evidence that aliased or reflective dispatch is absent
from the production path.

**Separate adjacent lead; not the R2 N6 predicate.** The read-only source audit
found that `LegacyPromotionStrangleReceipt.recompute` is used by three N9 promotion
builders and treats an absent `src/polisyos` directory as an empty caller set, then
reports `strangled`. Its property is the N9 predecessor-promotion strangle, not the
N6 `run_fixture` route. The existing promotion test checks the current checkout's
positive state; the missing-root/parse-error behavioral probe is `UNRUN`. Keep this
as a separate P37/P38 candidate, and classify it independently before opening or
closing a finding under P40; it is not automatically the same class as R2's N6
`run_fixture` predicate and does not widen this fix. Evidence:
`src/polisyos/runtime/quality/promotion_sequence.py@dc8beab981b714e80e54bef22ba83bc66ab3ffd4`,
`tests/unit/runtime/quality/test_promotion_sequence.py@fd72907d54b287a2d22031786e6cfd955a40c4d1`,
and the read-only census receipt
`/Users/deniskopylov/.codex/scratch/e02-r2-r2-identity-census-20260924.md@sha256:7cd9dfc6378ff929c21016cc507633f75f05ecbcf4f5ad4c2f8aaf685f06903a`.

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

**Falsifier / revisit trigger.** Keep census and run-start marker fields intact, but
remove the actual owner-captured identity or census evidence from the live pre-N9
admission. The call must return typed `not_established`, ordinary candidate work may
continue, and N9 promotion and its authority effects must not occur; a marker-only
green result falsifies the gate. Keep the bare confidence-ledger digest and all N6
receipt markers fixed, but remove the measured N6-route coverage or its identity-bound
gate result; the verdict must be `not_established`, never `current`. In a separate
stale probe, change a proven canonical identity input between run start and pre-N9
admission: the status must be `stale` and
N9 must remain withheld. A preserving control supplies the unchanged, owner-admitted
identity and passing census at both points; if independent N9 gates pass, promotion
must proceed. Historical replay of the pinned v1 fixture must compare serialized
bytes exactly, while a historically valid run with no current identity remains
replayable with currentness `not_established`. V2 byte replay remains `UNRUN` until
its historical owner supplies the original payload and byte oracle; no current
producer-generated replacement counts. The `lex/simulator/report.py` comment probe
is not an identity-drift probe until import-closure membership and effect are
measured. For the strangle predicate, keep the `strangled` marker and direct-census
receipt but introduce an aliased or reflective production call to `run_fixture`; a
complete census that resolves the path must return `fail`, while a path it cannot
resolve must return `UNRUN` and runtime currentness `not_established`; N9 remains
withheld in both cases. Force an inspection error in a separate probe; the tool must
return `UNRUN`, never crash in place of a verdict. A direct call inside the currently
exempt path must also fail unless a behavioral reachability check independently
establishes that exact caller as non-production. No blanket path-prefix allowlist is
an acceptable positive control. These are acceptance requirements, not results
recorded by this draft.

**Where it binds.** Source/deploy-time census and run-start identity capture; the
strangle classifier at `runtime/quality/generation_cycle.py::_collect_strangle_source_census`,
`::_call_name`, and `::_is_allowed_fixture_caller`; the
canonical identity owner and full input composition in
`runtime/quality/confidence_ledger.py::_admit_loaded_runtime`,
`_deployment_baseline`, and `_deployment_identity_from_baseline`; and a live typed
admission bridge immediately before `_promote_completed_generation` applies N9.
`GenerationCycleRun` v3 records that decision for later audit/replay, but its
construction after promotion cannot serve as the live gate. Historical/current
projections remain at `runtime/quality/generation_cycle.py::StrangleReceipt`,
`GenerationCycleRun`, and `validate_generation_cycle_run`. The behavioral gate and
removal/preserving controls belong in
`tests/unit/runtime/quality/test_epoch_validity_cascade.py@c6b546da2e9e5d77487e563e1954f1e5f6ef5130`.
The v1 fixture and current leaf-comparison test are
`tests/unit/runtime/quality/historical_artifacts.py@4a8d4bf763b2295da64e5e418f96fbf7c3ddd3c1`
and `tests/unit/runtime/quality/test_generation_source.py@dfbffbf32f90920a0b67310e4dd1d94b45e9308c`;
the latter must gain the byte-exact v1 oracle. The separate generation-cycle
contract-byte test is scoped to contract reissue and does not prove run serialization
(`tests/repo_quality/tools/test_layer3_gy_generation_cycle_contract.py@6ff8b4691de6250900154aac5e64f3ac7898c605`).
Currentness is an epoch question at admission, not an incidental source-tree scan.
The consumer handoff includes `runtime/quality/recursive_generation_cycle.py` and
`runtime/quality/design_axes/value_choice_provenance.py::_generation_disposition`;
both currently reject any `validate_generation_cycle_run` issue. Separate historical
replay validity from packaged currentness so a valid historical run can replay with
no checkout while its authority projection carries `currentness=not_established`
and withholds authority. Genuine historical corruption remains a replay failure.
Source-wide search also finds three `validate_generation_cycle_run` call sites in
`tools/quality/validation/check_layer3_gy_second_domain_pack.py` (lines 2999, 4515,
5977), feeding the N10a generated cycle trace, single-terminal closure, and smoke
replay. Classify each as historical replay or current source-gate inspection. If
behavior or output changes, include that checker and
`tests/unit/runtime/quality/test_second_domain_pack.py` in the consumer lease and
four-base test denominator; regenerate its JSON only when the owner produces a real
delta. The review identifies the calls at
`policy-engine/tools/quality/validation/check_layer3_gy_second_domain_pack.py@sha256:43d1a51c8e14b4a3f0872ff7fbdf38a157c63546b1b08752aa7f2d98ea086964` and
`policy-engine/tests/unit/runtime/quality/test_second_domain_pack.py@sha256:7e4aba32fe6e9ed46ba3c07c92e02f81e12720d89fdbca8c6c140f63a0d1d37e`.
Witnesses must cover both behaviors in
`tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py@b675681a801cb9a66ec3ca80faf636fd91bc92d9`
and `tests/unit/runtime/http/test_normative_generation_bridge.py@ef8ec18a438afe790a0b03f35f90b9e90d6288d4`.

**Pattern pass.** P07/P08/P29/P35/P37/P38/P41. Existing anti-patterns are runtime
recomputation over an overbroad source denominator, a marker receipt without
deployment identity, and post-promotion persistence mistaken for a pre-promotion
gate. Target: one complete source/deploy census, the existing canonical identity
owner extended into a typed run-start/pre-N9 contract, and separate historical
validity from packaged `current | stale | not_established`. The canonical identity
must cover the production N6 route and source/deploy gate; if its existing closure
does not, extend that same owner or bind an owner-issued gate receipt to the exact
canonical identity. A bare ledger digest is insufficient. The private identity
calculation and current source check exist; the public packaged identity bridge and
pre-N9 gate are `bridge_missing`, while closure membership and dynamic-call coverage
remain `not_established`. Acceptance requires marker-preserving removal and unchanged-
identity controls, byte-exact v1 replay, and an explicit `UNRUN` v2 result until an
original payload and byte oracle are owner-captured. The `lex/simulator/report.py`
comment probe remains unmeasured for import-closure effect. The P41 four-base JUnit
receipt for this regression class is pending the broker; this draft does not claim
the base-passing test set has been replayed or restored.

### R2 loaded-code closure follow-up — principal choice pending (2026-09-28)

**Proposed by / decision status.** Proposed by E02-R2 for Denis. Date: 2026-09-28. Status: PENDING;
neither option is selected or recommended, and this draft appoints no owner.

**Measured P38 gap.** The confidence-ledger resolver follows forward imports from the ledger root,
structurally omitting importing N6 module `generation_cycle.py`. This is expected from the current
algorithm but a P38 gap if that closure is used for N6 deployment currentness. N6 currentness and
canonical identity binding remain `UNRUN` / `not_established`; the ordinary controller withholds N9.
The sole production caller/path in `src/` is the GenerationCycleController route; direct test
construction exists. No production bypass was observed. The signer itself checks a supplied ledger
identity but no N6-currentness proof. The removal receipt records source snapshot
`44a7441eba7ad92eb6b95a767e14f0dbe61f27b3`, not the documentation input head `6ffa3e63d`; its
mutant stops before changed bytes are read and is not a byte-binding witness. Memo:
`/Users/deniskopylov/.codex/scratch/e02-r2-loaded-closure-investigation-20260928/R2_LOADED_CLOSURE_GAP.md@sha256:413633ca15921dc30b577b69a6bec33a6247286f643954fbbd33d802b231c890`.
Full frozen receipt:
`/Users/deniskopylov/.codex/scratch/e02-r7-r8-exact-head-20260928/R2_REMOVAL_PROBE_RECEIPT.md@sha256:99c72d9fe759bd1f17b331d8c94ec5a53eea51866a8d652ee4d519503a863206`.

**Costed options (unselected).** A: authorize appointment of a package-build identity producer and
implement the chain by reusing the confidence-ledger identity owner; bind the served N6→N9 closure,
lock, loaded-code evidence and passing census, then require exact run-bound currentness at signer
intake. Package/deployment pays for issuance; confidence-ledger for canonical verification/API; N6
for census and pre-N9 bridge; N9 for signer enforcement; test/release for mutation,
positive/control, history and four-base evidence; authorized identity/epoch owners for any approved
reissue. B: retain typed `UNRUN`, allow candidate computation under declared unknown, and withhold
N9. N6/N9 and deployment owners carry the limitation and later measurement cost. Neither option is
adopted or recommended here.

**Premises.** A deployment identity binds loaded deployment code, not checkout presence; historical
replay stays byte-exact without a live checkout; candidate work under declared unknown remains
available while N9 authority is withheld. These premises follow
`/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md@sha256:f9b3776032e88190ac8d29f60d9623450f4d734e163cc16ae53f49b0f2a77bce`
and the memo above.

**Remainder.** If A is later selected, dynamic/aliased source classes still need a declared
denominator, and the N9 signer owner must refuse every caller without exact run-bound N6 proof. No
package-build issuer is appointed. If B is selected, packaged currentness remains `UNRUN` and N9
remains withheld.

**Revisit trigger / falsifier.** Revisit after Denis rules on A/B and the package-build
issuer/production caller can be named. Under A, retain census markers and nominal PASS, mutate N6
pre-N9 guard bytes after manifest issuance, and require identity change or strict refusal before N9;
the unchanged package is the positive control. Candidate computation under `UNRUN` must remain
available and unrelated source edits must not invalidate historical replay. Full four-base R2
evidence remains `UNRUN`.

**Where it binds.** Confidence-ledger identity owner; unappointed package-build/deployment producer;
N6 census and pre-N9 bridge; `CanonicalN9PromotionPort` signer intake; strict run/public/value
consumers; and any separately authorized identity/epoch transition. This decision draft changes none
of those owners or records.

### R2 issuer policy — N9 current authority (principal decision draft)

**Status.** Drafted by the E02-R2 lane on 2026-09-25 for Denis and the authorized
security owner; no issuer is appointed by this draft. This supplement records the
issuer question separately from the engineering capability needed to verify a
release handoff. It does not revise the R2 historical/currentness proposal above.

**Question.** Which institutionally authorized issuer, if any, may establish the
current N6 source/deployment receipt for N9 authority in an installed package?

**Options and costs.**

1. **A — authorize the existing release-attestation workflow.** The principal and
   security owner admit the exact OIDC issuer, repository, workflow path/ref,
   predicate type, and trust-root/rotation source. A receiver verifies the detached
   statement against the exact built wheel and its N6 receipt. This keeps the
   existing release chain as the issuer, but makes N9 current authority depend on
   preserving that workflow identity and delivering its evidence bundle; a workflow
   or trust-root change requires an authorized transition. The release owner and
   security owner carry workflow and trust-root upkeep; deployment operators retain
   the exact wheel and evidence bundle. The identities are not supplied by this
   draft and must not be guessed.
2. **B — appoint a deployment/admission institution.** That institution issues a
   receipt binding the exact wheel digest and N6 receipt digest/verdict, which the
   runtime verifies offline. This separates release construction from deployment
   authorization, but costs an appointment, a receipt and custody lifecycle, and
   an owner-backed verifier/provider. The appointed institution issues and retains
   the receipt; the runtime owner carries its provider and consumer lifecycle. No
   such institution or runtime path is established in the reviewed repository.
3. **C — leave the production issuer unappointed.** Keep the issuer predicate
   `not_established`; N9 current authority is withheld in installed mode while
   ordinary candidate computation and historically valid replay remain usable.
   This preserves the authority boundary, but leaves no production N9 currentness
   path until an issuer is appointed; consumers requiring current N9 authority
   carry that bounded loss. This is the interim behavior proposed while A or B
   remains undecided; it is not a principal ruling to stop building the verifier or
   evidence handoff.

**Buildable capability, independent of issuer appointment.** Proceed with the
receiver-side release-envelope verifier under the existing SLSA/security owner, the
immutable exact-wheel plus detached-evidence handoff, and the typed runtime
consumer. Exercise the verifier with isolated test-only trust policy. This proves
the protocol and tamper behavior only; test trust cannot admit a production issuer.
Keep Confidence Ledger as the sole deployment-identity calculator and consume the
verified handoff through the existing runtime deployment-security composition.
The source-free package bootstrap, candidate path, and historical serializers can
be built and tested without an issuer. The production issuer policy is a separate
institutional admission. An appointment authorizes the act it names; verification
does not itself appoint or sign for that issuer.

**Premises.** The independent v3 review found no source-free runtime verifier,
issuer allowlist, or evidence provider for the release handoff, and found the
nearest SLSA and audit verifiers do not establish this release issuer. It concludes
the receiver capability is engineerable now with test-only trust while production
issuer admission remains a principal/security decision. The exact final wheel and
N6 receipt must be covered by the signed handoff; matching package hashes alone
are not issuer evidence. Unknown issuer scope binds N9 authority, not permission to
build candidate or historical capability. Evidence:
`/Users/deniskopylov/.codex/scratch/e02-r2-r2-package-handoff-design-v3-20260925.md@sha256:7fc188cebe92e2a5e94ab14b367296d4b54c014b73d7ed8d150e14f55c305a8f`;
`/Users/deniskopylov/.codex/scratch/e02-r2-r2-package-handoff-design-review-v3-20260925.md@sha256:b176ec6948ca26f90bdc33a026dc4221e3cbfefaacd33f5e9aee0f4b0ad4a180`;
`docs/system-design-decisions/policyos-identity-and-custody-boundary.md` §§8–9.7;
`docs/system-design-decisions/stage0-custody-kernel-ratification.md` §4.3.

**Proposed choice; principal status.** Build and verify the receiver and exact
evidence handoff under test-only trust now. Until Denis and the authorized security
owner decide A or B and admit the corresponding issuer policy, use C for the
production issuer predicate: `not_established`, with N9 authority withheld.
Candidate computation and historical replay continue as distinct typed outcomes.
No signer, repository/workflow identity, trust root, currentness epoch, trust
posture pin, or promotion receipt is selected or reissued here. **No principal
choice has been made.**

**Remainder and standing.** The exact production issuer identity, trust-root
source/rotation authority, release-evidence delivery location, and authorized epoch
transition remain for the principal/security owner and existing trust/deployment
owners. The verifier protocol and evidence handoff are a buildable missing runtime
capability; the unappointed production issuer is an owner-decision blocker only for
N9 current authority. Neither blocks candidate work or historical replay. A valid
release handoff does not by itself establish unrelated N9 predicates such as
tenant custody, EvalSafety, or world-model currentness.

**Falsifier / revisit trigger.** For A or B, retain the gate and package markers,
then change the installed N6 route and regenerate its local manifest and census
receipt without an issuer-authenticated handoff for that exact resulting wheel;
N9 must remain withheld. An attestation from a different repository/workflow/ref,
or a trust-root/workflow rotation without the authorized transition, must also fail
admission. The preserving control supplies the exact authorized signed handoff for
the exact wheel and receipt, and the offline verifier admits only the issuer named
by the authorized policy. For interim C, test both sides of the band boundary: if
issuer absence blocks ordinary candidate work or historical replay, the refusal is
too broad; if N9 current authority follows from self-hashed/co-packaged receipt
bytes alone, it is too weak. Reopen this record when the authorized owner supplies
an issuer identity, trust-root/rotation source, and evidence custody route that can
be falsified by these probes.

**Where it binds.** This draft binds only the production issuer predicate for N9
current authority and the trust-policy input consumed by the release-handoff
verifier. It informs the receiver-side extension in `src/polisyos/core/security/slsa/`,
the existing runtime handoff composition in
`src/polisyos/runtime/http/deployment_security.py` and
`deployment_security_attestation.py`, the sole identity projection in
`src/polisyos/runtime/quality/confidence_ledger.py`, and the admission immediately
before N9 in `src/polisyos/runtime/quality/generation_cycle.py`. It does not block
or bind the source-free bootstrap, candidate N6 work, or historical replay; it does
not appoint the issuer; and it authorizes no trust-posture, confidence-ledger,
loaded-runtime, or GY promotion-epoch reissue. Later change requires an appended,
dated principal decision naming this record and the evidence that moved it.

### R2 scope addendum — historical replay now; release handoff future (2026-09-25)

**Status and relation to the issuer draft.** The independent review gives a
conditional GO for the historical/currentness split and a NO-GO for making the
full release-attestation pipeline a prerequisite to the measured R2 regression
repairs. This lane scope proposal follows that review. It supersedes the preceding
issuer supplement's “proceed now” wording only as a recommendation for E02-R2's
regression-repair scope. It does not withdraw engineering permission under the
identity boundary, appoint an issuer, or replace the still-pending issuer options
above. The question of who can establish installed N9 current authority remains
for Denis and the authorized security owner.

**Question.** Should E02-R2 require the full release-attestation verifier and
exact-wheel evidence handoff to repair historical-run invalidation, or close the
historical/currentness split first and leave that larger authority capability for
a separately selected scope?

**Options and costs.**

1. **Narrow E02-R2 to historical replay and a typed currentness split.** Remove
   checkout discovery and eager checkout reads from package import; validate old
   run bytes, versioned historical projections, and recursive/compiled parents
   without today's source. Assess currentness separately against the canonical
   deployment identity and admitted epoch; without sufficient evidence return
   `not_established`. Keep the N6 route census in its source/deploy tool owner.
   Candidate computation and historical replay continue under unknown currentness;
   N9 current authority remains withheld. Keep source/development and verification
   test contexts distinct from installed-production authority so absent issuer
   evidence does not blanket-refuse those measured consumers. The runtime-quality
   and Confidence Ledger owners carry the validator/bootstrap changes, while the
   affected consumers and test owners carry their typed-result wiring and four-base
   replay cost. This addresses the measured historical regression but does not
   establish a positive installed N9 currentness path.
2. **Expand E02-R2 to the full release-attestation receiver and exact-wheel
   handoff.** Add or extend the receiver verifier, approved trust policy, immutable
   evidence provider, archive/member reconciliation, release transport and a
   source-free served N9 witness. The security/release and runtime deployment
   owners carry a broad capability and operational-retention cost. It does not
   follow from the historical replay regression, and the issuer, provider, and
   exact subject policy remain unappointed or unselected.
3. **Defer all R2 work until an issuer is appointed.** This avoids a later currentness
   integration step, but leaves the measured unrelated-source invalidation and
   checkout-dependent replay in place and risks refusing valid candidate/history
   work. The runtime-quality owner and users of replay/candidate paths bear that
   delay. The review does not recommend this option.

**Premises.** The independent review finds the measured R2 red is historical-run
replay invalidated by present source drift. Historical validity can be computed
from the persisted versioned bytes and parent hashes without claiming that the run
is current. At the reviewed source, `StrangleReceipt.verify_current()` requires a
repository root and recomputes today's census; `validate_generation_cycle_run()`
without a root reports `strangle_receipt_currentness_not_established`, which its
recursive caller treats as a validity issue. That conflates historical replay with
current authority. Conversely, a positive installed N9 currentness claim still
needs an admitted identity/route evidence handoff and authorized epoch; no issuer
policy or source-free runtime verifier exists. The v3 design's exact-wheel path is
therefore a possible future authority capability, not a prerequisite for the
historical fix. Evidence:
`/Users/deniskopylov/.codex/scratch/e02-r2-r2-v3-independent-review-20260925.md@sha256:b25ad02dfda13e1cb1c0481dabdce560477b5e70b3ef289918b27d86f5f15e1c`;
`/Users/deniskopylov/.codex/scratch/e02-r2-r2-package-handoff-design-v3-20260925.md@sha256:7fc188cebe92e2a5e94ab14b367296d4b54c014b73d7ed8d150e14f55c305a8f`;
`docs/system-design-decisions/policyos-identity-and-custody-boundary.md@sha256:f9b3776032e88190ac8d29f60d9623450f4d734e163cc16ae53f49b0f2a77bce` §§8–9.7;
`docs/system-design-decisions/stage0-custody-kernel-ratification.md@sha256:a8410cddf3e2c8b7f4c194d06d0c38523fb64634f247e6baf96dfd6359197ea7` §4.3.

The source seam and consumers at the reviewed target are
`src/polisyos/runtime/quality/generation_cycle.py@sha256:8ea492a13d35847d048dff8db87c1ed8711611741a2f9b1f96ba821da0f6e33e`,
`src/polisyos/runtime/quality/recursive_generation_cycle.py@sha256:6ec061ec348ef27e807b760bd09af7cb25155389a9d3694cb8b19e69f0b702f9`,
and `src/polisyos/runtime/quality/confidence_ledger.py@sha256:67c9eead466478377a15b27261005992d48e0aff1b783ac4913242c781d9c1c4`.

**Proposed choice; principal status.** The E02-R2 lane proposes option 1 for the
measured regression scope. The historical validator must decide replay from the
run's own frozen versioned content and parent bindings; currentness is a separate
typed result and cannot contaminate historical validity. In installed mode with no
admitted currentness evidence, return `not_established` and withhold N9 authority;
ordinary candidate work and historically valid replay remain available. Keep the
full receiver/wheel handoff as a future capability proposal pending selection by
the principal and named release/security/runtime owners, not as work this R2
regression repair must build now. No principal choice has been made, and this
proposal does not select among issuer options A/B/C above.

**Engineering permission and selected lane scope.** The institution's absence
limits the authority claim, not permission to develop a verifier. The existing
design's test-only protocol work remains technically buildable; that permission is
not a lane assignment. A future capability scope may select and assign the receiver
and handoff owners, subject, evidence provider, and test policy. Production
admission still requires the principal/security owner's issuer and trust-root
decision. This E02-R2 scope proposal defers that receiver/wheel path and does not
make it an acceptance prerequisite for historical replay. The source-free
bootstrap and versioned historical serializer remain in the narrowed R2 scope; a
test-only issuer policy does not create production authority.

**P37 — predicates at admission.** Historical validity is recomputed from the
persisted run schema/projection, exact content, and recursive/compiled parent
hashes; it says only that the record replays under its historical rules. Current
deployment identity/route coverage and its epoch are separate predicates. Without
the owner-admitted identity, N6 census result, and authorized currentness transition,
installed currentness is `not_established`; a checkout path, package self-hash, or
field marker cannot supply it. Missing currentness does not change a successful
historical verdict or itself refuse candidate work; it withholds N9 authority.

**P38 — property and divergence.** Property: historical records replay byte-exactly
without consulting the receiving deployment's current source, while N9 authority
is admitted only on a separately established current deployment/route predicate.
The reviewed implementation checks `repo_root` source census as part of
`validate_generation_cycle_run()` and exposes a missing-root currentness issue that
the recursive consumer treats as historical invalidity
(`src/polisyos/runtime/quality/generation_cycle.py@sha256:8ea492a13d35847d048dff8db87c1ed8711611741a2f9b1f96ba821da0f6e33e`,
`src/polisyos/runtime/quality/recursive_generation_cycle.py@sha256:6ec061ec348ef27e807b760bd09af7cb25155389a9d3694cb8b19e69f0b702f9`). An unrelated
source edit, or a packaged reader with no checkout, can therefore refuse a
historically intact run. Moving currentness into the historical predicate would
continue that divergence; accepting a package self-hash as issuer would create the
opposite divergence by granting current authority without an admitted source.

**Remainder and standing.** The production issuer, evidence provider, trust-root
rotation source, and currentness epoch transition remain undecided and
`not_established`; this scope proposal does not authorize a restamp. The exact
future attestation subject is also open: a whole-wheel archive hash is not itself
the canonical Confidence Ledger identity. A later owner must justify whether its
verifier needs the archive or a signed loaded-code/resource manifest plus the N6
receipt. Authentic N6 v2 historical bytes remain a named data-record gap and stay
`UNRUN`; do not synthesize them. P41 replay of every touched file remains a
prerequisite to code changes and closure, including the previously incomplete
generation-cycle, recursive-gate, normative-bridge, and Confidence Ledger paths.
The review also identifies that
`CanonicalN9PromotionPort._open_confidence_ledger_session()` in
`src/polisyos/runtime/quality/promotion_sequence.py@sha256:0a8aea760583e596d4e9198102b1e11b122d8d82224670d39446c28a58041173`
rebuilds a CAS through `ConfidenceLedgerSession.from_repo()` although
`PromotionRuntime.store` already exists. Carry that existing-store handoff in the
shared R2/R13 custody lease; it predates E02's execution base and is not an
E02-introduced regression. The Confidence Ledger `state_root` is a separate
persistence-owner question, not established merely by reusing the CAS.

**Falsifier / revisit trigger.** Keep historical run and parent bytes fixed while
changing an unrelated current source file: the historical validator must still
replay them byte-exactly. Change an N6 route-relevant input while retaining its
receipt markers: the source/deploy gate must fail or return `UNRUN` /
`not_established`, and N9 must remain withheld. With currentness/issuer evidence
absent, ordinary candidate work and a valid historical replay must succeed; if
either is refused, the gate is too broad. If N9 becomes current from a
self-consistent package manifest/receipt alone, the gate is too weak. Reopen the
future issuer/handoff scope when the principal and authorized owners name the exact
issuer policy, evidence provider, route subject, and epoch transition that can be
tested against those falsifiers.

**Where it binds.** This scope proposal binds the separation between historical
validation and currentness assessment in
`src/polisyos/runtime/quality/generation_cycle.py@sha256:8ea492a13d35847d048dff8db87c1ed8711611741a2f9b1f96ba821da0f6e33e` and its recursive consumer in
`src/polisyos/runtime/quality/recursive_generation_cycle.py@sha256:6ec061ec348ef27e807b760bd09af7cb25155389a9d3694cb8b19e69f0b702f9`; source-free bootstrap
under the sole Confidence Ledger identity owner at
`src/polisyos/runtime/quality/confidence_ledger.py@sha256:67c9eead466478377a15b27261005992d48e0aff1b783ac4913242c781d9c1c4`; the existing N6 route census
tool owner at
`tools/quality/validation/check_layer3_gy_generation_cycle_contract.py@sha256:9d8ee91dd4aa7c35b20d4ed6d302f38e61b491fa8f62205fcd14d772d149a264`; and the pre-N9 authority boundary. The existing store reuse in
`CanonicalN9PromotionPort._open_confidence_ledger_session()` is shared with
R13/P27/P31. This addendum does not bind or authorize the full receiver/wheel
handoff as current R2 work, alter the issuer choices above, change R9, or edit the
register/plans. The review is design evidence only; no repair or behavioral witness
is claimed here.

### R2 persisted-byte boundary refinement — principal decision draft; implementation evidence updated (2026-09-29)

**Status.** This remains a principal-level decision draft, not a ruling or class-closure claim. The NO-GO against candidate fd9375a correctly identified that decoded-map comparison did not prove raw-byte equality. The shared S8 _read guard has since landed at 686ecfcfad93641865591dd44d04197b397f8f24; bounded input-mutation and history tests pass as recorded below. No independent class-wide review, raw-byte code-removal probe, full served ControlPlaneService witness, currentness proof, or principal ruling is inferred.

**Question and options with costs.** Does historical validity require each persisted N6 source byte sequence to equal the versioned serializer, or is decoded semantic equality sufficient?

1. **Recommended proposal — enforce wire-byte equality at the shared persisted-source intake.** Preserve CAS bytes, verify the content-addressed ID and manifest, compare raw bytes to the recorded schema's exact serializer using the N6 writer's CanonSpec(forbid_floats=False), then run the historical semantic projection. Keep currentness as a distinct typed question. Cost: one shared owner check and byte-variant/removal/consumer tests; benefit: equivalent JSON spellings cannot claim byte-exact history.
2. **Accept decoded-map equality.** Cost is lower, but the property diverges from byte-exact replay at whitespace/key-order variants. This cannot support a byte-exact closure claim.
3. **Refuse every historical read without byte verification.** This avoids a false positive, but would over-refuse legitimate history and candidate consumers now that the owner has the bounded raw comparison.

**Premises and evidence.** The prior candidate review /Users/deniskopylov/.codex/scratch/e02-r2-s8-owner-seam-20260929/R2_S8_OWNER_SEAM_INDEPENDENT_REVIEW.md@sha256:21ebcb2b11e1fd9cabd632df8baa0e961a6dbb81fc964ed706ada7553f29a086c was read-only and found a whitespace/key-order variant could retain the decoded mapping while changing raw bytes. At 686, _read now compares those raw bytes with the canonical v1 serialization; implementation source is policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py@git-blob:7b5d610a7bc89e184f8f75a29c3141737bcf3404, the focused consumer test is policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py@git-blob:6b29b6dbaa49680af09645c0f3f467e6d580752f, and the history test is policy-engine/tests/unit/runtime/quality/test_generation_cycle_history.py@git-blob:10e85526f01cb298542688d6a8fee5ac5934cd88. The integrated history file is 27/27 ( /Users/deniskopylov/.codex/scratch/e02-r2-wheel-backend-diagnostic-20260929/integrated-history-686.xml@sha256:3e8394399345ae53feabd1c420ab81ecb29a4d1c6d468278d1683f9cba1b101a); focused test_s8_rejects_post_v1_field_from_raw_persisted_n6_bytes is 1/1 and directly calls NormativeValueScheduleOwner._read (/Users/deniskopylov/.codex/scratch/e02-r2-wheel-backend-diagnostic-20260929/integrated-s8-686.xml@sha256:247842c4e849bdd4fc7f7ce42cd1a70ee76eed932f7a066f6e77096845342b1a). test_source_free_package_replays_n6_v1_v2_v3_with_semantic_mutation passes 1/1 from an extracted wheel on candidate fd9375a (/Users/deniskopylov/.codex/scratch/e02-r2-wheel-backend-diagnostic-20260929/source-free-wheel-offline-backend.xml@sha256:3c914014361fecc5a618aca4a39932d35dfce5cdfc3dc1c7c1bc10988f174b7c); that earlier candidate-pinned run is not an exact-686 wheel receipt. The integrated whole-file run at 686 also includes that named test.

**Remainder, owner, falsifier, and revisit trigger.** Runtime Control owns the shared persisted-source intake; Runtime Quality owns the historical projection/serializer. Authentic historical v2 source bytes remain a data-record gap; do not synthesize them. Preserve a canonical v1 positive, then remove the raw-byte equality guard while retaining its markers: the lexical-variant expectation must turn red. That implementation-removal probe is UNRUN; the passing input-mutant tests are not a substitute. A full served path must carry the exact N4 source/context through ControlPlaneService, load the bytes from an extracted install without checkout support, and keep currentness typed separately. Reopen the decision if the byte-mutant remains green, currentness masks a history error, or the ordinary no-currentness candidate control is refused. The unrelated-source-comment control remains a separate historical-currentness property.

**Where it binds; P37/P38.** This draft binds only historical validity of persisted N6 source bytes at the shared normative intake and the versioned serializer. The property is raw-byte identity to historical canonical encoding; the landed code checks that exact predicate before the decoded-mapping history validator. The current behavioral witness exercises _read, while the production consumer claim includes the served ControlPlaneService reader and currentness boundary; that larger chain is not yet witnessed. It does not decide deployment identity, N9 admission, publication, or S8 authority. Missing issuer evidence continues to withhold authority only and does not block the byte-history repair or unrelated engineering.

### Wave5 historical `repo://` reference sibling (P41)

**Question.** How should the immutable Wave5 manifest's historical `repo://`
references be evaluated after E02 retires a referenced path, when the manifest
records no admitted source snapshot or content digest?

**Options and costs.**

1. An authorized artifact owner issues an append-only as-of/content sidecar that
   binds the exact Wave5 manifest digest to the exact admission commit and tree,
   and lets the historical resolver verify each referenced blob and anchor from
   that tree. This can restore a positive historical verdict without depending on
   today's checkout, but requires owner evidence for the actual admission, a
   retained/retrievable Git object set, a sidecar producer, and a separate
   historical consumer path. The registered artifact owner pays for the source
   receipt and object retention; runtime-quality pays for resolver integration and
   historical verification. Git's first commit containing the manifest or its
   current branch ancestry cannot be chosen as a substitute for the missing owner
   fact.
2. Keep the manifest immutable and return typed historical
   `not_established`/`UNRUN` until that owner evidence exists. This preserves the
   distinction between a missing snapshot and a proved invalid reference, but
   leaves the old historical check unresolved and cannot claim a pass from the
   current tree. Historical consumers and the record owner bear that unresolved
   status; they pay no reissue cost and do not gain a green result.

**Premises.** The same test blob
`tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py@7c4b73fb339f36b21bcc430c1260f35d76a745d6`
has the same-key P41 result `pass` on E02's execution base and main, and `fail` on
E02 and Phase 0. The full four-base receipt is
`PolicyOS_E02R2/R14_RATCHET_MAP.md@c13460e67ebf13ba36faf077fb38a7c38fce5631`
(commit `9d54442a`); it enumerates 36 manifest references across 30 target paths
and identifies the sole absent target as
`repo://packages/runtime-api-client/runtimeApiClient.ts`. The four JUnit bytes
were rehashed and match the recorded values:

| Base | Result | JUnit artifact `path@sha256` |
|---|---|---|
| E02 execution base | pass | `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/cells/e02_execution_base/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml@24ac90ee7118270b65ce28bad68a9dc884c9e9a13e763732d6af5a522f8ad86b` |
| E02 head | fail | `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/cells/e02_head/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml@13d44f90d391fe6cfa7f1d13471767c41e743848d6383085a5662431384e4542` |
| main | pass | `/Users/deniskopylov/.codex/scratch/e02-r2-baselines/p41-pre-repair-20260924T144020Z-80143/cells/main/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml@4aebe1a1e5ed2b8672686870c97fca4b56d7899b95c781b4f2c0d66f58eab140` |
| Phase 0 merge | fail | `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/cells/phase0_merge/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml@ef86ba29e19625866b81baf79d1d82be4c25fa57323788d3b3fefeb55141b2d4` |

The manifest blob is `architecture/policy_design_case/wave5_i5_external_consumer_truth_manifest.json@fa16e56d90fcfb6b90d8de56cb261ae00f69a95d`; the checker is
`tools/quality/validation/check_policy_design_case_capability_ratchet.py@1cd361b73a01e7ed7668d18b92a4491e335d8628`. Both are unchanged across the four
bases. The E02 deletion alone explains the key transition: the current validator
resolves each reference against today's `repo_root` and checks `Path.exists()` and
an optional anchor. It has no manifest-bound source revision, tree, or content
digest with which to establish the old target's historical state. The P41 raw
artifact custody inspection
`PolicyOS_E02R2/P41_ARTIFACT_RELOCATION.md@f60fe1b2c44dbc5c6164a06d2f3c326ac174406a`
confirmed SHA-exact custody for all 109 recorded JUnit references in its 113-row
checkpoint; that is artifact custody, not test semantics or historical source
identity.

**Proposed choice; principal status.** Use option 2 now, pending Denis's ruling:
the historical Wave5 reference verdict is `not_established` until
`team-runtime-quality` provides an
authorized as-of/content sidecar. Option 1 is the only proposed route to a positive
historical verdict, subject to the principal's ruling and the owner proving the
actual admission snapshot. Do not restore the retired raw `runtimeApiClient.ts`,
edit or regenerate the Wave5 manifest, restamp its timestamp/status, or infer its
source tree from current ancestry. The current generated-client outputs remain the
runtime/API owner's live artifacts; their existence does not recover the retired
file's historical bytes. This sibling narrows the Wave5 evidence consequence of
R2's historical/current distinction; the related owner appointment and broader
snapshot question are also recorded in R14, without authorizing a second receipt
or a manifest reissue.

**P37 — gate predicates.** Manifest byte identity is `recomputed` from the
registered immutable digest, but does not identify the source tree. The asserted
Wave5 admission commit/tree and target bytes are `not_established` without an
owner-issued sidecar. If supplied, its binding to the exact manifest digest and
Git blobs/anchors must be `independently_reconciled`; the current checkout's path
presence and the commit that first added the manifest are not authority for the
as-of fact.

**P38 — property and divergence.** Property: every Wave5 `repo://` reference
resolved to the expected file and anchor in the exact source snapshot used for
Wave5 admission. Current implementation: it tests target existence and optional
anchor text in today's checkout. Divergent cases: it fails the E02/Phase 0 test
when the raw client path is absent, even though that alone says nothing about its
historical bytes; and a present path on another current tree can pass without
proving it was present in the admitted snapshot.

**Remainder.** The historical snapshot/content producer is `producer_missing`
until the artifact owner supplies the sidecar; a historical resolver consuming it
is `bridge_missing`. This scope does not alter N6's `GenerationCycleRun` serializer
or its packaged `current | stale | not_established` check, does not change active
references that intentionally mean current-tree files, and does not decide the
separate WS-2D current closeout ledger paths. The raw-client deletion remains an
E02 regression for the current checker, not evidence that the immutable Wave5
record may be rewritten.

**Falsifier / revisit trigger.** Keep the Wave5 manifest bytes, status, and phase
markers fixed. A sidecar pointing to a tree where the referenced path or required
anchor is absent must fail; inability to inspect that tree must return `UNRUN`,
not pass. The preserving control resolves the old reference from the owner-bound
historical tree while the current checkout lacks `runtimeApiClient.ts`; an
unrelated edit to today's checkout must not change that historical verdict. A
separate current-client control keeps the canonical generated TypeScript client
`packages/runtime-api-client/canonicalRuntimeApiClient.ts@96d655649cfd765b326a3ef3aa207153b4c1a8f6`
resolvable with the retired raw twin absent. These are proposed acceptance
witnesses, not run results.

**Where it binds.** This decision binds only the immutable Wave5 manifest's
historical resolver in
`tools/quality/validation/check_policy_design_case_capability_ratchet.py::validate_repo_reference`
and the behavioral identity
`test_policy_design_case_capability_ratchet::test_wave5_exit_records_i5_manifest_and_influence_boundaries`.
It does not authorize changes to the manifest, the runtime API client's generated
artifact owner, N6 historical serializers/currentness, or WS-2D's live closeout
references. The same boundary and its evidence are cross-referenced by R14.

### R2 package-only route attestation issuer — principal decision draft (2026-09-26)

**Status and relation to the R2 drafts.** This addendum supplements the R2 source-free
currentness proposal and issuer-policy draft above. It resolves the narrower evidence
gap: how an installed package can consume an N6 route census when it has no source
checkout. It does not replace the existing issuer choices A/B/C, select a trust root,
appoint an issuer, or authorize an identity/epoch reissue. No principal ruling has been
made.

**Question.** What evidence may establish package-only N6 route currentness, binding the
route census to the canonical loaded deployment identity and lock inputs, when
`src/polisyos`, `pyproject.toml`, and `uv.lock` are not present at runtime?

**Options and costs.**

1. **Appoint a build/deploy issuer for an identity-bound receipt.** Denis and the
   authorized security owner select an existing authorized release issuer or appoint a
   deployment/admission institution under the existing issuer policy. Its immutable
   receipt binds the exact built package subject, the N6 route-census rule, complete
   inspected denominator, and independently derived complete served-root set, as well
   as the census verdict/unresolved classes and canonical Confidence Ledger deployment
   identity (including its loaded-code manifest, lock and other owner-defined inputs).
   Root discovery must use the actual registered served handlers and worker/job
   dispatch source of truth; a curated root list cannot support class-wide PASS. The
   installed reader verifies issuer/trust policy and reconciles the receipt against
   the code actually loaded and the package's lock identity, without a source checkout.
   This enables positive package currentness, but
   costs an issuer appointment or exact workflow admission, trusted key/root and
   rotation policy, build/deploy producer, immutable evidence delivery and retention,
   offline runtime verifier, and an authorized transition if identity inputs change.
   Release/deployment, security, Confidence Ledger, and runtime-quality owners carry
   those duties. The identity remains computed by the existing Confidence Ledger owner;
   the receipt is N6-scoped evidence bound to that identity, not a second identity
   calculation.

2. **Keep source-tree tooling and bound installed currentness as `UNRUN`.** The
   source/deploy tool recomputes the route closure and served-root denominator from
   the actual route registry and worker/job dispatch in an available checkout. It
   returns `UNRUN` if registration or root completeness cannot be reconciled; a
   finite hand-maintained root list cannot return class-wide PASS. A source-tree result
   alone does not attest which bytes are installed; an installed package without a verified owner
   receipt returns currentness `not_established`/`UNRUN`, with N9 authority withheld.
   Candidate computation and source-free historical replay continue. This is the
   smallest honest interim path and avoids inventing an issuer, but leaves positive
   package-only currentness unavailable until option 1 is admitted.

3. **Reject an unsigned package self-attestation.** A JSON file co-packaged beside the
   code, even if it lists source hashes, lock digest, manifest, and a PASS marker, has
   no independent issuer or trust root. Code and receipt can be changed together, so
   package presence, internal hash consistency, and a claimed producer role remain
   self-attested. This is cheap to add but can falsely green the authority predicate; it
   is rejected as evidence for package currentness. It may be diagnostic input only and
   must yield `UNRUN` for authority.

**Premises and predicate provenance.** The property is that the served production N6
path does not route through `WorkspaceLoop.run_fixture`; it is separate from the sibling
`workflow_run` fixture path. Existing `StrangleReceipt` counts direct AST names and
exempts every direct caller under `workspace/loop.py`, so that source census is not
itself a complete route proof. The R2 route-closure design requires unresolved indirect
dispatch or incomplete served-root enumeration to produce `UNRUN` and retains the
candidate-band path under a declared limitation. In P37 terms: route membership, root
completeness, and forbidden-edge checks are `recomputed` by the build/source tool;
matching the installed loaded-code manifest and lock to the
receipt is `independently_reconciled` by the packaged reader; the issuer identity and
trust root are `institutionally_supplied` by the principal/security owner. An exact R2
reviewer also found that a new served sibling omitted from the candidate's finite root
list can call `run_fixture` and leave the owner result PASS. Root completeness is
therefore a separate deciding predicate; it must be derived from the actual served
route registry and worker/job dispatcher, not from the same list under review. If it is
not independently reconciled, route currentness is `UNRUN` and no class-wide authority
PASS is allowed. Review note:
`/Users/deniskopylov/.codex/scratch/e02-r2-served-root-completeness-review-20260926.md@sha256:f8c4ac4bee61d81ef6390a2ce819dc5992153066d650b3919932d1842de925d6`.

The inspected packaged readiness path returns `UNRUN` and names
`packaged_build_identity_issuer_not_appointed`, `n6_strangle_census_not_established`,
and `deployment_authority_issuer_not_appointed`. It checks whether
`_packaged_deployment_identity.json` exists but no production issuer/reader for that
file was found; its only other repository references are readiness tests. The canonical
identity owner is `confidence_ledger`; its current source-checkout path requires
`pyproject.toml`, `uv.lock`, and `src/polisyos`. A package self-file is not proof that
these inputs or the route census describe the installed loaded code. Evidence:
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py@sha256:63b3c9bbde5faf530da1466a563e76833c6d29682612d86ea008e8a08c3d7e4d`;
current R2 record
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/DECISION_RECORDS.md@sha256:00a335053b755e1e49e402983191b67eadd6b9de418f10ec21a52d57aa03227f`.

**P38 — property and divergence.** Property: every served production N6 entry is
covered and does not route through `WorkspaceLoop.run_fixture`; package currentness
binds that route result to the exact loaded deployment. The candidate route analyzer
uses a finite root set. Divergent case: register a new served sibling outside that
list and let it call `run_fixture`; the analyzer can return PASS while the property is
false. This is the same P38/P40 class, not a new root-instance class; do not patch it
by adding another root to a curated list. A second package-boundary divergence is an
unsigned co-packaged JSON whose PASS marker and digest are updated alongside the code:
a form-only reader stays green although the installed route changed. The current
packaged readiness result `UNRUN` is
honest; neither a curated root list nor package presence may replace it.

The read-only class-mechanism review recommends the existing `StrangleReceipt` owner for
route closure, a separate N6-scoped receipt bound to the existing canonical identity,
and a real build/deploy issuer before positive package currentness. The follow-up
review identifies incomplete served-root enumeration as the same P38/P40 class; no
class-wide PASS is available until that denominator is independently derived. The
review rejects unsigned package claims and treats the runtime fixture token as
containment only, not proof that no route exists.
Review evidence:
`/Users/deniskopylov/.codex/scratch/e02-r2-class-mechanism-design-20260926.md@sha256:7264f158170d87b876b47abe881f2929c35a2089dd55ffdd0ede6482ffb59e8d` and
`/Users/deniskopylov/.codex/scratch/e02-r2-owner-attestation-independent-review-v4-20260926.md@sha256:4fb90c37f3b8fc027e8b29fd204248a552d58400b83095bf22e9eb72905fcb82`.

**Proposed choice; decision-maker and binding status.** Recommend option 1 as the
production path for any positive installed N6 currentness. Until Denis and the
authorized security owner name/admit its issuer and trust policy, apply option 2:
installed currentness remains `UNRUN`/`not_established`, N9 authority is withheld, and
candidate computation plus historically valid replay remain available. Option 3 is
rejected for authority. No class-wide route PASS is admissible until root completeness
and issuer-bound package identity both pass. This is a proposal, not a principal ruling;
the exact release workflow or deployment institution must not be guessed from repository
presence. Denis decides; the authorized security owner co-owns issuer and trust-root
admission.

**Historical validity and currentness.** Historical validity is replay of the persisted,
versioned run and parent bytes under that run's historical serializer; it never requires
today's source tree or a currently installed package receipt. Currentness is a separate
typed epoch fact: `current` only when a root-complete N6 census has verdict PASS and
its issuer, route-rule version, canonical deployment identity, loaded-code manifest,
and lock binding reconcile with the installed runtime; a proven changed identity is
`stale`; absent, unsigned, incomplete, or unresolved evidence is
`UNRUN`/`not_established`. Persisting a new receipt requires a v4 run projection with
explicit frozen v1–v3 serializers; do not append fields to the R11 v3 projection.
Missing package evidence withholds
authority, not candidate work or historical replay.

**Remainder.** The exact production issuer, admitted release workflow or deployment
institution, trust-root/rotation owner, evidence transport/retention path, and
authorized currentness transition remain undecided. The route analyzer's unresolved
dispatch classes remain `UNRUN`; complete served-root enumeration is not yet
independently established, so no class-wide authority PASS is available. This addendum
does not make Python reflection statically complete by declaration. It does not close
R2, authorize a restamp, or resolve the independent historical v2 byte-oracle gap.
If no issuer is appointed, the bounded residual is package-only currentness `UNRUN`,
not a source-checkout fallback and not unsigned self-attestation.

**Falsifier / revisit trigger.** Keep receipt fields and PASS markers intact, then add
and register a new served sibling route outside the declared root list that reaches
`run_fixture`. The census must discover that root and return FAIL, or return `UNRUN`
if registration/reachability cannot be reconciled; it must never PASS. Also alter a
route-relevant N6 call/alias, installed loaded code, or lock input without an authorized
receipt for the resulting exact package. The installed reader must return
FAIL or `UNRUN`/`not_established`; it must never report current, and N9 remains
withheld. A receipt from a different package/lock, or a regenerated unsigned JSON beside
altered code, must also fail to establish currentness. For option 2, an unresolved
reachable dispatch must remain `UNRUN`; if source-tree-only evidence is accepted as
package currentness, the boundary is too weak. The preserving control is a real served
N6 run with a verified receipt from the admitted issuer bound to the exact package and
matching loaded-code/lock identity; it may establish currentness only after the route
census PASS and all other N9 predicates pass. If absence of the receipt blocks ordinary
candidate computation or historical replay, the refusal is too broad. Revisit this
record when the principal/security owner supplies an issuer identity, verifier trust
source/rotation rule, and exact evidence delivery path that can pass these falsifiers.

**Where it binds.** This decision binds only the package-only N6 route-attestation
issuer and its currentness predicate: the release/deploy receipt producer and installed
verifier; the owner of the complete served route registry and worker/job dispatch
inventory; the existing Confidence Ledger deployment identity owner and packaged
readiness/identity API; the existing `generation_cycle.py::StrangleReceipt` route-census
owner; the versioned `GenerationCycleRun` receipt binding and pre-N9 currentness
consumer; and the GY-N6 validator's three-valued output. It does not change the global
deployment identity formula, historical replay semantics, `workflow_run` fixture
permission, candidate-band permission, or the existing A/B/C issuer options except by
requiring their selected issuer to bind this exact N6 subject. No trust-posture pins,
promotion epochs, or other governed artifacts are reissued by this draft.


## R3 — N9 promotion-comparison epoch (OP-R3-REISSUE; principal draft)

**Status.** Draft for Denis/principal; no ruling or governed-artifact reissue is authorized. The existing selected blocker catalog remains 56/282; this is a crosscutting premise, not a new finding row.

**Question.** Should the promotion-comparison owner transition the frozen contract from receipt v6 / comparison rule v5 to receipt v8 / rule v7, retain both epochs for a demonstrated live custody consumer, or keep comparison refused?

**Premises and evidence.** The current owner source emits v8/rule-v7; the frozen contract carries v6/rule-v5. The exact-head checker receipt at df5188a7435cbd0394da33979eab7482c754c249 is source-equivalent to 2cd for this narrow check, not an exact 2cd invocation. It returns FAIL/exit 1, complete_verdict=true, selection_status=partial, with proof_input_strangle_drift and promotion_comparison_admission_manifest_drift at unauthorized_manifest_epoch_transition; the measured input is the frozen contract, and full source/import/data-input closure is not established. Receipt: /Users/deniskopylov/.codex/scratch/e02-r3-current-census-20260928/promotion-check-df5188.json@sha256:8ec943ab67d90c3f5050ab787e5608870db242b0a309490e44c1e6a10dd8ae92. The corrected historical audit is /Users/deniskopylov/.codex/scratch/e02-r3-current-census-20260928/R3-historical-audit-2cd.md@sha256:8b8e562428a44484ac3466a92dcd066da30ab87d779dc3b5b6c46ef7fa9b45bb. Historical receipts remain bound to their original serializers and cannot regain current authority. Silent restamping is prohibited.

**Options and costs.**

1. **A — authorize owner transition (preferred if current comparison authority is needed).** Denis authorizes the existing owner to regenerate the current contract as v8/rule-v7, recording the premise and exact old/new hashes. Cost: governed artifact delta, owner review, dependent-consumer replay, and release verification. This does not rewrite or promote historical v6 receipts.
2. **B — retain the artifact and support two explicit epochs.** Consider only if the owner identifies a live policy/custody consumer that must compare both frozen v6/rule-v5 and current v8/rule-v7. Broad old compatibility is not a sufficient premise. Cost: durable dual-epoch owner logic, separate projections/hashes/admission paths, and a real consumer witness; no artifact reissue occurs.
3. **C — keep the typed refusal.** Defer comparison authority until the premise is supplied. Cost: current promotion comparison remains unavailable; candidate work and historical reads continue within their existing scope.

**Decision authority and execution.** Denis/principal selects A, B, or C. The registered promotion-contract owner executes an authorized A or a substantiated B. The architect records any register change. This draft itself authorizes no artifact mutation, reissue, restamp, or ledger-status change.

**Remainder and closure signals by option.** Under A, leave the frozen artifact untouched until authorization; close only after owner-generated transition, exact hash readback, current consumer replay, preserved historical non-admission, and checker PASS/exit 0 with adequate selector scope and both the epoch-transition and proof_input_strangle predicates satisfied. Under B, retain the frozen artifact; close only after a named live consumer exercises both explicit epoch paths, each projection/hash/admission is separately recomputed and bound, mixed/unauthorized epochs fail, the independent proof_input_strangle issue is resolved with adequate scope, and historical non-admission remains green. Under C, keep the measured typed FAIL/exit 1 and a named revisit path; this is a bounded refusal, not R3 closure. For any option, incomplete inspection is UNRUN/exit 2. Do not interpret the separate four-base P41 replay as authorization: the whole-file runs of test_promotion_sequence.py and test_generation_source.py are independent of the decision and may run while it is pending.

**Falsifier and revisit trigger.** Reopen A versus C if the owner demonstrates identical comparison projection, hash, and admission outcomes for frozen v6/rule-v5 and live v8/rule-v7 without a transition. Consider B only if a named live policy/custody consumer needs both epochs; lack of that consumer falsifies B. A marker-only green or an unresolved proof-input strangle cannot support PASS.

**Where it binds; P37/P38.** This draft binds only the N9 promotion-comparison artifact, its owner generator/checker, and current comparison consumers. It does not change the historical serializer, grant current authority to old receipts, or authorize trust-pin or generation-cycle reissue. The checker measured the frozen artifact and owner replay but selected only a partial input scope; the two issues must remain distinct. PASS is about recomputed epoch-specific projections, hashes, and admission over the declared complete input scope, not schema-marker presence or exit code alone.

**Pattern pass.** P07/P32/P35/P37/P38: preserve historical serializer replay, reject trust-by-form, enumerate the receipt set, disclose the checker predicate's partial denominator, and keep implementation/property scope explicit. Historical projection belongs to the promotion-sequence serializer; governed output remains with its registered contract owner. No plan or debt-register edit is proposed.

## R4 — GY-N6 contract validator must return a verdict

**Question.** How should the validator construct its isolated N9 verification state
so it follows the problem actually presented at N9, and how should it distinguish a
known semantic refusal from an inspection failure? Separately, what is established
about a later production invocation that encounters an existing durable ledger
under an earlier basis?

**Options and costs.**

1. **Proposed choice:** keep exact full-risk-scope equality and lazily create one
   checker-local verification session at the first N9 call, using that call's exact
   final `DesignProblem` and binding. Retain that same N9 problem/binding and session
   for both the summary batch and embedded receipt revalidation. This aligns checker
   inputs with N9, but the temporary verification ledger does not establish how a
   repeated production invocation behaves with an older durable root.
2. Keep the eager pre-controller verification session and report its later scope
   mismatch as semantic `fail`. This preserves equality but reports the checker
   fixture's lifecycle mismatch as if it were a production ledger refusal, leaving
   the intended N6→N9 contract unmeasured.
3. Accept matching `scope_id` while ignoring inequality in the complete risk-scope
   projection. This avoids the mismatch but lets a same-ID basis change bypass the
   owner guard and confuse prior spend with newly admitted risk.
4. Rebase or replace a durable ledger under the revised basis. This could make a
   repeated N9 call proceed, but risks discarding non-resettable cumulative spend
   and needs an owner-authorized, replayable transition that is not established.

**Premises.** `_build_live_payload_in_verification_namespace` currently opens
`ConfidenceLedgerSession._for_verification` before the controller, from the initial
problem binding. N6 can revise the problem before N9. In contrast,
`CanonicalN9PromotionPort.__call__` derives the binding from its N9 `problem` and
opens the production session there; `_run_n9_promotion_port_batch` then checks exact
equality with the complete `confidence_risk_scope_for_problem(problem_binding)`.
After the controller returns, the checker currently also passes the original
pre-N6 `problem` to `_embedded_promotion_comparison_admissions`; that value reaches
`admit_canonical_promotion_receipt_for_comparison(design_problem=problem)`. The
receipt is bound to the final N9 problem, so both the checker session and the
revalidation problem argument must be derived from and retain that exact N9 input.
Thus the observed error reflects checker fixture bindings that can straddle the N6
revision and does not by itself establish a production refusal. The execution-base
validator returns a typed fail with three issues; current-head `--check` lets
`confidence_ledger_scope_binding_mismatch` escape as `ValueError`.
The production owner returns typed `not_promoted` for a `ConfidenceLedgerError`
while opening its durable session, but behavior for a repeated invocation whose
existing root is bound to an earlier basis remains `UNRUN` pending a behavioral
witness. The ledger anchors the full scope and persisted receipts/events witness
cumulative spend; a stable identifier does not prove continuity or authorize a
transition. Existing tests refuse unrelated scope binding and prevent deleting
ledger events from resetting spend
(`tools/quality/validation/check_layer3_gy_generation_cycle_contract.py@b8134aeffe3b96760e7fd9663ae9670e85391160`,
`src/polisyos/runtime/quality/promotion_sequence.py@dc8beab981b714e80e54bef22ba83bc66ab3ffd4`,
`src/polisyos/runtime/quality/confidence_ledger.py@c3775ce0a96966fcbc46fa243e5cc03f3a80c84b`,
`tests/unit/runtime/quality/test_promotion_sequence.py@fd72907d54b287a2d22031786e6cfd955a40c4d1`,
`tests/unit/runtime/quality/test_confidence_ledger.py@1537ea3e9984fd9599d4d95b3c9e95c040af6fbf`).
The validator tests are `test_generation_cycle_contract_mutations_turn_red` and
`test_generation_cycle_contract_write_refuses_stale_comparison_admission`
(`tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a`).
The mutation test’s existing denominator is 12; the fix must keep all 12 mutations
red. The P41 four-base receipts and exact command output remain pending broker
citation; this draft makes no test-pass claim.

**Proposed choice; principal status.** Recommend option 1 for the validator and
retain the runtime owner's exact guard. Capture and retain the exact final N9
`DesignProblem` and `N9DesignProblemBinding`. Create the checker’s single temporary
verification session lazily from that binding at the first N9 call, and use that
same final problem/binding and session for the complete summary batch and every
embedded receipt revalidation. Do not pass the original pre-N6 problem to receipt
admission. A known full-scope mismatch between a session and the N9 binding returns
typed `fail` with
`confidence_ledger_scope_binding_mismatch`; successful validation returns `PASS`;
an inspection or recomputation failure that prevents a verdict returns typed
`UNRUN` (exit 2 with measured/not-measured disclosure). No production ledger is
replaced or restamped here. The separate behavior of a repeated production call
against an existing old-basis durable root is `UNRUN` pending a witness; if that
path refuses admission, it must remain a typed non-promotion unless an
owner-authorized append-only transition preserves prior lineage and cumulative
spend. Denis remains principal for any authority decision on such a transition;
no transition or receipt reissue is authorized by this draft.

**P37 — gate predicates at admission.** The checker’s final N9 binding and full
`ConfidenceRiskBudgetScope` are recomputed from the exact final N9 `DesignProblem`.
The checker must retain that same problem/binding and pass it to receipt
revalidation; exact equality between its scope and the one in the single
checker-local session is recomputed. Receipt, event and spend lineage for a
production durable root must be independently resolved from the ledger owner; the
old-root repeated-invocation behavior is `not_established` until that witness
exists. Matching `scope_id` is only an identifier, not proof of basis equality or
continuity. Any transition authority is institutionally supplied by the ledger
owner and principal and remains `not_established` until recorded.

**P38 — property and divergence.** Property: the contract validator exercises one
coherent N6→N9 flow and returns PASS, semantic FAIL, or UNRUN according to its
evidence; production N9 never accepts a changed durable basis without an authorized,
spend-preserving transition. The checker currently opens its verification session
before N6 and passes the original problem to receipt revalidation after N9; either
can differ from the final N9 problem. Divergent case: N6 revises the problem basis,
production N9 binds receipts to that final problem, but checker receipt
revalidation receives the old one. The implementation must retain the exact N9
problem/binding for both the lazy session and revalidation. Separately, a temporary
fresh checker ledger cannot decide how production handles an existing durable root
from an earlier basis; that requires a separate witness. Full-scope equality must
not be weakened to make either path green.

**Remainder and signatory.** This draft authorizes only checker-local session
construction and verdict composition. It does not authorize a production basis
transition, durable ledger replacement, cumulative-spend reset, or receipt reissue.
`runtime/quality` owns the typed N9 binding and validator composition. The
ConfidenceLedger owner must propose any future append-only replayable transition
and cumulative-spend rules; Denis remains the principal signatory for that authority
decision. Until a production old-root witness and any required owner transition
exist, that behavior remains `UNRUN` and revised-basis admission cannot claim
closure.

**Falsifier / revisit trigger.** Reopen if the checker does not derive its sole
verification session from the final N9 binding and pass that same final problem to
both N9 summary and receipt revalidation, if full-scope inequality can pass, or if
any of the 12 existing contract mutations turns green. The removal probe
deliberately opens the checker session under basis A, then exercises N9 and receipt
revalidation with basis B that retains the same scope ID and record markers; the
full-scope mismatch must return semantic FAIL with
`confidence_ledger_scope_binding_mismatch`, not crash or become UNRUN. This
independent A→B probe ensures the session and receipt sides cannot both drift
together and still pass; removing full-scope equality while keeping the IDs and
markers makes the refusal assertion fail. The preserving control uses the exact
same final N9 problem/binding for session creation, summary admission and receipt
revalidation.
Inspection/recomputation failure before a semantic result returns UNRUN/exit 2. A
separate unrun production probe seeds an old durable root and invokes N9 with a
revised same-ID basis, asserting a typed non-promotion and unchanged prior
events/spend; only an owner-authorized transition with exact replay and spend
continuity can change that result. These are acceptance criteria, not claims that
the tests or probes have run.

**Where it binds.** Checker-local lazy session creation, reuse, and verdict
composition in `tools/quality/validation/check_layer3_gy_generation_cycle_contract.py`;
production session opening and exact N9 equality in
`src/polisyos/runtime/quality/promotion_sequence.py`; risk-scope and lineage
custody in `src/polisyos/runtime/quality/confidence_ledger.py`. A revised-basis
durable transition is a future ledger-owner capability and is not supplied by the
validator.

**Pattern pass.** P04/P05/P07/P29/P32/P37/P38/P41. The checker’s pre-N6 session
acts as a proxy for the final N9 basis; the production owner’s full-scope equality
is the property and must remain intact. Target: align the checker’s temporary
session with N9’s final input, report semantic mismatch as FAIL and inspection
failure as UNRUN, and leave production durable-root continuity `not_established`
until witnessed.

## R5 — mode-owned evidence gates and EvalSafety context denominator

**Historical proposal snapshot.** The proposal and `UNRUN` labels in this section
record the pre-implementation design. The dated R5 implementation addendum below
supersedes its pending status and evidence claims; retain this text as design history.

**Question.** Which admitted N6 run bands require their mode-owned evidence gate (DataTrust or EvalSafety), and how does ordinary candidate work remain available without deriving authority from missing or mismatched evidence?

**Options and costs.**

1. Keep the current conditional denominator guard. This leaves empty maps and the custom-controller path outside the check, and it lets a missing worker result erase whether the request was ordinary candidate work or a declared evaluation attempt. The recursive-runtime owner pays little change cost; protected users and DataTrust consumers bear the bypass and wrong-gate risk.
2. Require current EvalSafety context for every mode, including `simulate_only`. This is easy to state but over-refuses pure computation and conflicts with the candidate band and S0-K06; it also assigns the wrong owner to `retrospective` and `measurement_audit`. EvalSafety and ControlPlane owners pay for unnecessary wiring, while candidate and DataTrust users pay the refusal or misclassification cost. These DataTrust modes still cannot become candidate work when their own evidence is missing.
3. **Proposed lane lean:** extend the existing `ControlPlaneService.launch_nl_run` admission owner and reuse R1's proposed binding through the existing persisted job payload and `job_created` event/outbox. Put one strict typed run-intent value in the existing payload; bind its digest, exact payload ref, job/run identity, and authenticated route/action through the existing event/outbox, then reconcile those records before dispatch. This is a proposal, not an implemented contract, and creates no standalone admission artifact. A versioned server admission policy derives intent from the authenticated route/action, not a caller assertion, and positively classifies the ordinary `/runs/nl` action as `candidate_only`. It does not derive that decision from missing context, empty EvalSafety output, caller-supplied band, execution profile, or mode token. A well-formed declared attempt is resolved by `resolve_evaluation_mode`: `simulate_only` is the distinct `simulate_only_attempt` band; `retrospective` and `measurement_audit` require the existing DataTrust owner and select `data_trust_required`; only `sandbox_pilot`, `field_pilot`, and `deployment` select `eval_safety_required`. Missing, malformed, contradictory, legacy, or mismatched DataTrust/EvalSafety binding is typed `not_established` and non-runnable for that declared mode. It never falls through to `candidate_only`; only the affirmative authenticated ordinary-route policy selects candidate work. The EvalSafety band requires a current verified context for the exact graph-leaf denominator on every path, while the DataTrust band uses its separate existing owner and contract. Costs are typed payload and event/outbox binding, atomic creation or explicit fail-closed recovery, readback, launch/worker/recursive propagation, DataTrust and EvalSafety owner integration, and the behavioral witnesses below. ControlPlane/Store owners pay for admission and durability, the existing DataTrust and EvalSafety owners pay for their mode-specific bindings, and runtime/test/package owners pay for consumer wiring and four-base witnesses. A legacy row without a matching payload/event binding remains historically readable but is not eligible for N6.

**Premises.** The public `EvaluationMode` vocabulary includes `simulate_only`, `retrospective`, `measurement_audit`, `sandbox_pilot`, `field_pilot`, and `deployment` (`pdc/_impl/evaluation_safety.py:43-50`). GY §3.5.6 assigns `retrospective` and `measurement_audit` to DataTrust, and assigns only `sandbox_pilot`, `field_pilot`, and `deployment` to EvalSafety (`docs/plans/active/layer3-slices/GY-engine-subordination.md:2521-2526`). The existing generation-cycle value owner already blocks the two DataTrust modes when its DataTrust input is absent (`runtime/quality/generation_cycle.py:2974-2978`); this is not a candidate fallback or an EvalSafety check. `EvaluationAttemptIntake.mode_resolution` is a DTO field, not the resolver owner (`runtime/quality/evaluation_safety.py:438-447`). The canonical owner is `runtime/quality/evaluation_modes.py::resolve_evaluation_mode`; it rejects missing and invalid tokens and does not apply aliases or simulation fallback (`:15-40`). The EvalSafety consumer independently recomputes this resolution and rejects a mismatch (`runtime/quality/evaluation_safety.py:1445-1448`).

The DataTrust/EvalSafety mode split corrects the independent review's blocking finding that the former R5 proposal routed every non-simulation mode through EvalSafety: `/Users/deniskopylov/.codex/scratch/e02-r2-decision-drafts-independent-review-20260925.md@sha256:fc7103792e6525d032101dba8208336f223d3f21c5e87118f5407bc66b21af4c`.

The existing request carries an arbitrary context mapping. The reserved attempt key is `_EVALUATION_SAFETY_ATTEMPT_KEY` (`runtime/http/services/control/run_lifecycle.py:218`), and the worker-only `_admit_evaluation_safety_attempt` returns `None` when that key is absent; strict model parsing can raise for malformed content (`:2859-2867`). This is too late to choose a run band and cannot distinguish an ordinary request from a declared attempt lost before worker admission. The production launch owner is `ControlPlaneService.launch_nl_run` (`runtime/http/services/control/run_lifecycle.py:1319,4013-4029,4106-4134`), composed by `RuntimeContainer.startup` (`runtime/http/container.py:342-354`) and the authenticated `/runs/nl` route/action (`runtime/http/routes/control.py:261-265,368-390`). No trusted run-band field or policy exists at this source head; candidate-only selection is currently `not_established`.

The durable store does not yet preserve this decision. `ControlJobRecord` has no typed run-intent field or band (`runtime/http/services/control_plane_store.py:845-867`). `create_job` writes the row, progress, `job_created` event and outbox in separate operations (`:2398-2466`); `job_created` currently says only `{"state":"pending"}` (`:2855-2861`). SQLite `_execute` commits each operation separately, while PostgreSQL calls without the existing transaction lane open a separate cursor/transaction (`:4415-4498`). Both schema initializers use `CREATE TABLE IF NOT EXISTS` and do not migrate existing rows (`:3950-3980,4134-4162`). The current implementation therefore does not make row, event, and outbox atomic. Do not claim it does.

The recursive controller checks the EvalSafety denominator only when `evaluation_contexts_by_node` is truthy and only when no custom factory is configured (`runtime/quality/recursive_generation_cycle.py:823-839`). `CycleControllerFactory` accepts only `(node_ref, problem)` (`:401`), so the custom factory cannot receive or prove consumption of an EvalSafety context; the factory is called at the leaf (`:871-905`). HTTP passes `{}` when EvalSafety and cycle-substrate context are both absent (`runtime/http/services/control/generation_cycle.py:665-669`). That ordinary request is not thereby a `simulate_only` attempt.

**Proposed choice; principal status.** Adopt option 3 as a lane proposal, pending Denis's ruling. Reuse R1's proposed smaller binding: place the typed server-selected intent in the existing persisted job payload, and bind its digest, exact payload ref, job/run identity, and authenticated route/action in the existing `job_created` event/outbox. The current event contains only `{"state":"pending"}`; extending it to bind the payload and intent is proposed, not implemented. Before dispatch, reconcile the current job, event/outbox, and payload bytes. A partially written or mismatched row must remain unleaseable or fail closed before N6. Do not add a standalone CAS admission artifact, a second N6 selector, a second owner, or a mutable-row-only authority field unless a focused race/owner test proves the existing binding cannot fail closed. Extend the existing server ingress/admission seam so it derives typed intent from authenticated route/action and policy before a job is runnable. The ordinary route explicitly constructs `candidate` intent under a versioned server rule. A caller cannot set a band or promote its own assertion into a server intent; every declared evaluation mode is parsed strictly and sent through `resolve_evaluation_mode`, not through its supplied `mode_resolution` value. Map `simulate_only` to pure computation, `retrospective` and `measurement_audit` to the existing DataTrust gate, and `sandbox_pilot`, `field_pilot`, and `deployment` to EvalSafety. A missing DataTrust binding for either DataTrust mode remains `not_established` and non-runnable in that declared mode; missing EvalSafety evidence for a protected mode remains `not_established` and fail-closed. Neither condition selects or falls through to `candidate_only`; only the affirmative authenticated ordinary-route policy selects candidate work. The current event-binding design and mode-specific owner gates are proposals, not implemented contracts.

The persisted band is one of `candidate_only`, `simulate_only_attempt`, `data_trust_required`, `eval_safety_required`, or `not_established`. The typed, schema-versioned run-intent value in the existing payload carries the server-resolved intent/policy version, declared attempt identity and generation, requested-mode token digest when present, canonical mode-resolution status/mode, and selected band. Its CAS payload bytes supply the content digest; the existing `job_created` event/outbox is proposed to bind that digest and exact payload ref with job/run identity, tenant, actor, and route/action. Reconcile the payload and event/outbox against the current row before dispatch; a row field alone is only a lookup projection. Retries keep the immutable intent and payload and check the current lease/attempt at dispatch; do not mint a per-retry artifact unless a concrete retry can change the intent or payload in place. Dispatch starts only after this evidence is read back.

The current store does not provide the required atomicity. Extend `ControlPlaneStore.create_job` with a transaction boundary so the job row, progress, intent-bearing payload reference, `job_created` event, and outbox intent commit together; that boundary does not exist today. Publish/dispatch only after the proposed transaction commits. If one transaction cannot cover the existing event/outbox path, add explicit idempotent recovery that reconciles row/event/outbox before dispatch; a row without a matching payload/event binding is not eligible. No new admission-artifact reference column or CAS owner is proposed. Existing jobs have no fabricated band or restamped event: keep historical status queries readable, but classify absent, legacy, or mismatched bindings as `not_established` and refuse N6.

Band behavior is explicit:

- `candidate_only` is selected only by the authenticated server route/action's versioned ordinary-route admission policy. It permits pure candidate computation without an EvalSafety `ValuePort` and confers no authority. If the owner resolver cannot establish `CycleSubstrateContext`, carry that unknown through R1's single compiled-wrapper v2 typed limitation; do not infer unknown merely because the request omitted a context, since the HTTP owner builder may resolve one from existing production WMR/catalogs.
- `simulate_only_attempt` requires a well-formed declared attempt whose mode is accepted as `simulate_only` by `resolve_evaluation_mode` and whose payload/event intent binding is read back before replay. It is pure computation and needs no R5 current-head denominator. It grants no protected effects, S8 authority grade, promotion, or publication. Missing or malformed intent cannot select this band.
- `data_trust_required` is selected only for `retrospective` and `measurement_audit`. Route these modes through the existing DataTrust owner and its consumer contract. Missing, malformed, foreign, stale, or mismatched DataTrust binding is typed `not_established` and non-runnable in that mode; it never downgrades to `candidate_only` or substitutes EvalSafety evidence. Preserve the existing `data_trust_gate_missing` refusal in the generation-cycle value owner.
- `eval_safety_required` is selected only for accepted `sandbox_pilot`, `field_pilot`, and `deployment` modes. The worker must preserve this band even when the attempt or result is absent, malformed, stale, or refused. Such conditions produce a typed refusal before N6; they never become `candidate_only`, `simulate_only_attempt`, or `data_trust_required`. Recompute the exact graph-leaf refs and require exactly one current, independently verified `EvaluationExecutionContext` per leaf. Empty, missing, extra, stale, foreign, or problem-mismatched context refuses. Do not weaken the EvalSafety consumer verifier or create another mode resolver.
- `not_established` covers legacy/unclassifiable payload/event binding and malformed or contradictory declared intent. It is a non-runnable state. At the HTTP boundary return a typed refusal before dispatch; if a refused attempt is persisted for audit, its immutable intent remains `not_established` and its job is terminal, never runnable.

Pass the verified band to `RecursiveGenerationCycleController.run` and check it before every leaf factory path. For `eval_safety_required`, the current custom-factory contract cannot express context consumption, so return a typed `recursive_eval_safety_custom_factory_context_not_consumed` refusal before invoking that factory. This is a bounded residual: a context-aware typed factory contract and post-factory reconciliation do not exist at this head. Do not pretend that checking the denominator alone proves that the custom controller's `ValuePort` consumed the expected context. The ordinary normal-controller candidate route and the declared `simulate_only_attempt` route retain pure computation, with promotion/publication disabled for both. R1 owns the context limitation schema and historical serializer; the exact v2 limitation field/type name remains for that owner to specify. If the compiled-run hashed model changes, R1 must preserve the prior byte projection under its historical serializer and bump the current schema. R5 reuses that typed limitation and adds no competing artifact.

This proposal does not decide that any S8-positive fixture lacks owner context. The HTTP owner builder may derive context from production WMR/catalogs; four-base replay determines the fixture's actual red. A no-context fallback through `production_composed_world_model_record` is a plausible N4 owner route, not proved served support. Do not claim the R1 candidate preserving control, served N4 owner bridge, or R13 world-growth custody is complete until an end-to-end witness establishes it.

**P37 — gate predicates at admission.**

- Server-resolved route/action intent and selected band are recomputed under a versioned admission policy; caller-provided mode/band fields are `consumer_asserted` and cannot choose the persisted band.
- The typed intent in the persisted payload, job-created event/outbox, current job/run IDs, payload digest, tenant, actor, route/action, generation, and attempt are independently reconciled before worker execution. A missing or mismatched binding is `not_established`.
- The attempt's canonical mode is recomputed by `resolve_evaluation_mode`; the supplied `mode_resolution` DTO is not accepted as evidence. A `simulate_only_attempt` additionally requires a well-formed declared attempt and replay of that same decision.
- The exact recursive leaf set is recomputed from the validated graph. `data_trust_required` is independently admitted by the existing DataTrust owner for only `retrospective` and `measurement_audit`; missing binding remains `not_established`, never candidate. For `eval_safety_required`, every leaf's current EvalSafety context is independently verified by the existing consumer owner for only `sandbox_pilot`, `field_pilot`, and `deployment`. Empty-map, custom-factory, missing, stale, and foreign-context cases fail closed.
- `candidate_only` and `simulate_only_attempt` make no EvalSafety authority claim. A missing DataTrust or EvalSafety binding cannot select either band. Unknown substrate scope for the positively admitted ordinary candidate route stays `not_established` in R1's typed limitation; it is not converted into a concrete context.

**P38 — property and divergence.** Property: the server-selected intent is durably replayed from the payload/event binding at the served leaf; `retrospective`/`measurement_audit` reach DataTrust, `sandbox_pilot`/`field_pilot`/`deployment` reach EvalSafety with one current verified head per graph leaf on every supported factory path; pure candidate and explicit `simulate_only_attempt` work remain available without authority. The existing generation-cycle value owner correctly blocks missing DataTrust for the two DataTrust modes (`data_trust_gate_missing`, `generation_cycle.py:2974-2978`), but the HTTP run intent/band is not durably bound. Separately, the preceding R5 proposal's generic “all non-simulation” EvalSafety classification would send the two DataTrust modes through the wrong gate. The recursive guard also checks context presence rather than a persisted intent binding: the worker's optional key can return `None`, the HTTP composition supplies `{}`, the denominator skips falsey maps and is inside the no-factory branch, and the custom factory cannot consume a context. Divergent cases include a DataTrust mode mislabeled `eval_safety_required`, a missing DataTrust binding reinterpreted as candidate work, a protected action whose missing binding is mistaken for ordinary candidate work, an empty map for a nonempty leaf graph, and an EvalSafety-required custom factory that bypasses the guard. Current absence also cannot truthfully distinguish candidate-only from `simulate_only_attempt`.

**Remainder.** The typed intent payload contract, payload/event binding, atomic job/event/outbox creation or idempotent fail-closed recovery, worker readback, and route-to-leaf band propagation are `bridge_missing`/`verification_missing` at this head; this proposal adds no standalone admission artifact or artifact owner. Existing rows without a matching binding remain historically readable but are `not_established` for N6. `retrospective` and `measurement_audit` must use the existing DataTrust owner; their missing binding remains non-runnable `not_established` and cannot become candidate work. The current custom-factory interface cannot consume/reconcile EvalSafety contexts and is refused for `eval_safety_required` until that smallest missing capability is implemented and witnessed. R1's candidate-context limitation and compiled-wrapper historical serializer remain its owner responsibility. Every proposed R5 test, removal probe, and preserving control remains `UNRUN`; no proposal result is evidence of a pass.

**Remainder standing and signatory.** `data_trust_required` without its mode-owned DataTrust binding and `eval_safety_required` without its exact-leaf EvalSafety evidence are both `not_established` and non-runnable; neither can become `candidate_only`. A correctly admitted `simulate_only_attempt` or `candidate_only` can compute without either authority gate, while promotion/publication/S8 remain prohibited; candidate/substrate uncertainty stays a typed limitation. `ControlPlaneService.launch_nl_run` is the proposed existing software owner for admission issuance; `ControlPlaneStore` owns durable transaction/event/readback; the recursive runtime owns mode-band enforcement; existing DataTrust and EvalSafety owners supply their distinct evidence. Denis remains the pending principal signatory; this draft is not a principal ruling.

**Falsifier / revisit trigger.** Reopen if a declared DataTrust or EvalSafety mode with absent/malformed payload reaches its mode execution without a typed refusal; if `retrospective` or `measurement_audit` reaches `candidate_only` or `eval_safety_required`, or missing DataTrust evidence does not remain `not_established`; if a persisted band can be changed by a caller assertion, absent context/result, mutable row, or job kind; if an old row is upgraded to candidate eligibility without an owner payload/event binding; if row/event/outbox disagreement still permits dispatch; if a stale worker reuses a prior attempt intent; if an empty or foreign leaf context, or the current custom factory, can pass under `eval_safety_required`; or if an explicit `simulate_only_attempt` gains promotion/publication/S8 authority. Required witnesses (proposed; all tests, removal probes, and preserving controls remain `UNRUN`):

- `test_control_plane_store_run_intent_payload_event_binding_and_readback`: new row, event, and outbox read back the same content-bound intent; interruption cannot leave a runnable partial record. `test_legacy_control_job_without_run_intent_binding_is_readable_but_not_n6_eligible`: existing SQLite/PostgreSQL rows remain historically readable and resolve to `not_established`, with no synthetic event or backfill.
- `test_launch_candidate_and_eval_safety_intents_select_distinct_bands`: the authenticated ordinary server route selects `candidate_only`; `retrospective`/`measurement_audit` select `data_trust_required`; only `sandbox_pilot`/`field_pilot`/`deployment` select `eval_safety_required`; corrupting or omitting the payload/event binding while retaining schema markers refuses and cannot fall back. `test_launch_malformed_eval_safety_intent_refuses_before_dispatch`: malformed and unresolved tokens return a typed refusal, not a crash or candidate downgrade.
- `test_data_trust_modes_require_distinct_owner_binding`: each DataTrust mode reaches the existing DataTrust owner with a valid binding; remove that binding while keeping mode and payload markers, and the mode becomes non-runnable `not_established` rather than candidate or EvalSafety. Its preserving control verifies the ordinary authenticated route still selects candidate only through its positive route policy.
- `test_launch_simulate_only_attempt_is_persisted_as_pure_compute`: a well-formed attempt whose resolver returns `simulate_only` reads back as `simulate_only_attempt`, computes without a current EvalSafety head, and cannot promote, publish, or emit S8 authority.
- `test_eval_safety_required_band_requires_exact_leaf_denominator`: normal controller execution rejects empty, missing, extra, stale, foreign, and problem-mismatched contexts; a current exact denominator preserves the valid control. `test_eval_safety_required_custom_factory_refuses_unconsumed_context`: the existing factory is refused before invocation until it can receive and reconcile typed contexts.
- `test_nl_pipeline_candidate_route_preserves_r1_limitation_without_authority`: the ordinary served route reaches existing candidate owners and persists R1's v2 unknown limitation only when owner-context resolution actually returns unknown. P41 replay, not fixture shape, decides whether S8 bridge fixtures have owner context; the plausible no-context N4 route is not a served witness by source inspection alone.
- Keep Appendix A `test_non_simulation_leaf_requires_current_eval_safety_head` as the base regression witness. Every newly touched test file must first have its complete four-base P41 denominator recorded. These are acceptance criteria, not run receipts.

**Where it binds.** Server intent resolution before dispatch in `runtime/http/routes/control.py` and `runtime/http/services/control/run_lifecycle.py::ControlPlaneService.launch_nl_run`; the proposed typed intent in the existing persisted job payload and its binding in the existing `job_created` event/outbox; transaction or fail-closed recovery and readback in `ControlPlaneStore.create_job`; worker replay in `_process_control_job`; band propagation through `runtime/http/services/control/generation_cycle.py`; graph-leaf equality before controller-factory dispatch in `runtime/quality/recursive_generation_cycle.py`; canonical mode resolution in `runtime/quality/evaluation_modes.py`; the existing DataTrust refusal in `runtime/quality/generation_cycle.py` (`data_trust_gate_missing`, lines 2974–2978); and current EvalSafety evidence verification in `runtime/quality/evaluation_safety.py`. R1 owns the compiled-wrapper v2 limitation and historical serializer. Promotion, publication, and S8 consumers continue to enforce their own authority boundary.

**Pattern pass.** P04/P05/P07/P12/P29/P31/P32/P37/P38/P41. Existing failure: optional worker attempt plus conditional denominator, no durable run-intent bridge, and a non-atomic job/event/outbox sequence; the generic non-simulation label also conflates the DataTrust and EvalSafety owners. Target: one server-selected typed intent in the existing persisted payload, bound by the `job_created` event/outbox and reconciled before replay; atomic persistence or explicit idempotent recovery; exact mode-specific owner gate (`data_trust_required` or `eval_safety_required`) and graph-derived EvalSafety denominator on all supported factory paths; and a separately named pure `simulate_only_attempt`. Missing capability labels: `bridge_missing`, `verification_missing`, and `semantic_test_missing` until payload/event readback, served mode-owner consumers, and removal probes pass.

### R5 implementation addendum — five-band served intent (2026-09-27)

**Status and question.** This addendum supersedes the preceding R5 draft's
pending/UNRUN status claims. Denis ruled that non-simulation authority modes
`sandbox_pilot`, `field_pilot`, and `deployment` require current
EvalSafety evidence for the exact leaf context; any relaxation is limited to pure
computation. This records that direction's implementation, not an additional
principal ruling. It does not decide the separate R1/R5 per-active-basis question
or DataTrust-positive admission. How does every served NL launch preserve
server-selected intent through durable admission and replay while keeping
candidate computation available without protected authority?

**Options and costs.**

1. **Reuse the served authorization and ControlPlane owners with one five-band
   intent contract. Implemented.** Require the sealed route/action proof for every
   NL launch, including candidate requests; persist and reconcile typed intent across
   the existing payload, creation event/outbox, and worker replay. Use the canonical
   resolver and existing storage/permission owners. Cost: route, store, worker,
   recursive-owner, and served-test changes.
2. **Use EvalSafety for every non-simulation token or launch. Rejected.** Lower local
   complexity, but assigns `retrospective` and
   `measurement_audit` to the wrong owner and refuses candidate computation
   under an explicit unknown.
3. **Keep the optional context-presence guard or let missing intent fall through to
   candidate; retain a test-only no-proof launcher. Rejected.** Cheapest initially,
   but permits protected work to escape its owner gate and leaves the test path
   outside production custody.

**Premises.** S0-K06 fails closed in the authority band while allowing candidate
work with a typed unknown. GY assigns `sandbox_pilot`, `field_pilot`, and
`deployment` to EvalSafety; `retrospective` and
`measurement_audit` to DataTrust; and `simulate_only` to pure
computation. Reuse the existing served proof and job/event/outbox owners. Sources:
`docs/system-design-decisions/policy-design-causal-operating-system-north-star.md@46f6502a1a29c160d99a258ea3a6209e08ae55dfcb95836790403ec26c8998e2`,
`docs/system-design-decisions/stage0-custody-kernel-ratification.md@a8410cddf3e2c8b7f4c194d06d0c38523fb64634f247e6baf96dfd6359197ea7`,
`docs/plans/active/layer3-slices/GY-engine-subordination.md@5d06f4cc55541fb28030ec4f6c75f2a10537df53c60f792df84de118d0aeb4c5`,
`docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md@35c1b64c91aa4209cffed4aed42d89258e5f975afab44464f201111ba0b4d725`, and
`docs/reference/policy-design-case-failure-patterns.md@64f9fa40453980d9128443ee34a4bf3298b71c157a5ebcc3bd6cb786abeb090a`.

**Implementation and decision status.** `f7d66883fbcb352eb923c23e3e104608490e8061`
integrates the five bands: `candidate_only`, `simulate_only_attempt`,
`data_trust_required`, `eval_safety_required`, and
`not_established`. Every NL launch requires the sealed served proof; direct
service calls without it refuse. The test-only
`launch_internal_candidate_nl_run` was retired after a direct call-node census
parsed 2,696 Python files and found zero production calls (census:
`/Users/deniskopylov/.codex/scratch/e02-r5-owner-candidate-20260926/R5_internal_candidate_source_census.json@a3793962a433156e7405a04358a62d2c944a04a540262ecab7a4c065227c2d75`; blind spots are reflective dispatch, string loading, and aliases that erase the method name).

The ordinary served route preserves candidate computation with typed unknown scope.
`simulate_only_attempt` remains pure compute and cannot promote, publish, or
emit S8 authority. The three protected modes require current EvalSafety evidence and
the exact leaf denominator; missing, malformed, stale, or mismatched evidence
refuses before protected work and never selects candidate. DataTrust modes retain
their typed band: N4 candidate materialization can carry
`data_trust_owner_not_established`, while the DataTrust-dependent recursive
path refuses rather than substituting EvalSafety. Malformed intent is terminal and
unleaseable as `not_established`.

The admitted job supplies tenant, cell, run, and job identity for N4 writing and
readback; a missing cell remains unknown, and nested caller
`runtime_identity` cannot supply it. Finite request numbers use the existing
resource-binding digest profile; raw body/query authorization remains intact and
non-finite numbers refuse before enqueue.

**Evidence.** The integrated focused JUnit passed 28/28 (0 failures, errors, or
skips; 47.656 seconds):
`/Users/deniskopylov/.codex/scratch/e02-r5-integration-20260927/integrated-r5-v11.junit.xml@sha256:9ba0dd805eef65e6c6cf9a928120a485c59290462330cba79554074099c97843`.
It covers the protected denominator, candidate/simulation controls, five-band
binding, proof-required launch, finite/non-finite inputs, served N4 persistence and
readback, schema and cycle-occurrence controls, and four B88 replay controls.

With markers retained, removing shared N4 owner-scope checks produced three
expected reds and one green ordinary served-candidate control: foreign inner scope
at write, self-hashed foreign inner scope at current readback (historical v1 replay
still exact), and foreign nested identity with a missing owner cell. JUnit:
`/Users/deniskopylov/.codex/scratch/e02-r5-owner-candidate-20260926/r5-scope/v11-owner-scope-removal.junit.xml@sha256:745c3d89e395467fafa268449fe43fe5847fbe2f28834c28110713c7d1ff3776`.
Both changed sources were restored byte-exactly
(`/Users/deniskopylov/.codex/scratch/e02-r5-owner-candidate-20260926/r5-scope/v11-owner-scope-removal.source-hashes.txt@ceb3800c3171d9b915c6ea08ebfff576043c402c2683ecf0da2236328a2dc899`).
A supplemental synthetic field-pilot EvalSafety property-removal probe also turns
its discriminator red:
`/Users/deniskopylov/.codex/scratch/e02-r5-owner-candidate-20260926/R5_v6_core_guard_removal_probe_RECEIPT.md@c88301871e402cce0bca137f7962a4f6573235998199ad4adbf6f946d82755dc`.
It is not a complete protected-mode matrix.

Implementation owners include
`runtime/http/routes/control.py@0018f247b22b9479be1e37e3827c0381740d8b42649bd08490fe8823494e238c`,
`runtime/http/services/control/run_lifecycle.py@db84338772e43cb55a57c1bb91e78e85468b5c7788ccf8d709aec2e8194526a3`,
`runtime/http/services/control_plane_store.py@0901dbd098485f1c37f033bf6832584106c5de1768d9179e2dfaed9980a6107c`,
`runtime/quality/evaluation_modes.py@ad6d4522d057f8301c4b1fedd85991e176f1c621ef88a6f31abd84c5498a7422`, and
`runtime/quality/recursive_generation_cycle.py@2a26ac897d37587e8ab0b5ae38f7790b438c2479044e0f60cbd1e2a27cf5935f`.
Behavioral tests include
`tests/unit/runtime/http/test_control_job_execution_intent.py@77862b95680f6c01619dc320eaec6d0fb90dd0eca040f423643447a262913e58`,
`tests/unit/runtime/http/test_workspace_loop_transition.py@3760a94148dd65344504cd743c9cecf9d3b62d57a4224896c3523e1d028ed7b7`,
and `tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py@dcbcfdfbd14183812f9674cfa88d008838ee124c9bb8ec511789ebbca34c65f3`.

**P37 / P38 and pattern pass.** Mode resolution and graph-leaf enumeration are
`recomputed`; the sealed route/action/job binding is
`independently_reconciled`; the positive DataTrust result remains
`not_established`. The property is an owner-bound intent reaching its matching
evidence gate. The prior proxy was optional attempt presence and a truthy EvalSafety
map guarded only on one factory path; divergent cases were an empty map for a
nonempty graph, missing attempt binding, and a custom factory that could not consume
context. P04/P05/P07/P12/P31/P32/P37/P38/P40/P41 apply; owner-scope reconciliation
is same-class depth, not a new ladder.

**Remainder.** DataTrust-positive recursion is `bridge_missing`: there is no
served producer/readback binding for a current candidate/WMR/scope/epoch result.
The simulation fixture reaches a typed N5 block
`joint_simulation_ncm_spec_missing`; it is not successful numeric N5 evidence.
Complete four-base whole-file P41 replay for every touched test remains
`UNRUN`. The 28 focused cases are not that denominator; R5 is not finding-
level closed, and the separate R1/R5 per-active-basis decision remains pending.

**Revisit trigger / falsifier.** Reopen if a marker-preserving removal or mutation of
served proof/intent/event binding still reaches the worker/compiler; if protected
work runs without its exact current EvalSafety head; if a candidate request is
refused solely for absent EvalSafety; if simulation gains promotion, publication,
or S8 authority; if DataTrust is admitted through EvalSafety; or if whole-file P41
changes regression attribution. A future DataTrust-positive result needs an
owner-produced persisted binding to candidate/WMR/scope/epoch plus served positive,
foreign, and missing-evidence controls.

**Where it binds.** Served authorization binds at
`runtime/http/routes/control.py` and `ControlPlaneService.launch_nl_run`;
persisted intent and event/outbox reconciliation bind in `ControlPlaneStore`
and `_process_control_job`; band resolution binds at
`runtime/quality/evaluation_modes.py`; current EvalSafety leaf admission and
pure-computation boundaries bind in
`runtime/quality/recursive_generation_cycle.py`; N4 owner identity binds in
`runtime/http/services/control/nl_pipeline.py` and
`runtime/quality/generation_source.py`. Surfaces project this typed truth and
do not invent authority. This addendum changes no register or plan and authorizes no
governed reissue.

### R1/R5 addendum — refresh evidence for each active basis (2026-09-25)

**Question.** When N6 revises `current_problem`, may N4/N5 continue using the
root-bound substrate context or EvalSafety head, and how does the ordinary
candidate route remain useful while that basis-specific evidence is unknown?

**Options and costs.**

1. Reuse the root context/head or remove the equality check. This avoids a new
   owner call, but turns a correct stale-context refusal into false grounding for
   `B != S` and can carry a root EvalSafety admission into a different problem.
   The recursive-runtime owner pays little change cost; protected-mode users and
   the authority consumers bear the stale-evidence risk.
2. Refuse all work when per-basis context is unavailable. This prevents stale
   evidence from reaching protected consumers, but also closes ordinary
   candidate computation under an explicitly unknown scope. Candidate users pay
   the over-refusal cost; runtime and safety owners save the per-basis integration
   effort.
3. **Proposed lane choice, pending Denis:** after N6 selects the typed
   `current_problem`, resolve its recomputed full basis hash `B` through the
   existing context/world owners immediately before N4 and N5. Thread one
   immutable, owner-validated `CycleSubstrateContext(B, WMR)` to those consumers.
   For each protected non-simulation leaf (`sandbox_pilot`, `field_pilot`, and
   `deployment`), separately obtain and verify a fresh `EvaluationExecutionContext`
   for that exact `B` before N4 through the existing EvalSafety owner; retain the
   second independent fresh challenge at N8. A cycle-substrate context is not an
   EvalSafety context and cannot issue, retag, or stand in for one. This costs an
   owner-first per-basis resolution seam, exact-basis admission, and served
   removal/preserving witnesses. It reuses existing owners and does not add a
   second registry or mode resolver. The context/world and EvalSafety owners pay
   for per-basis resolution/admission; runtime-quality and test owners pay for
   controller wiring and behavioral witnesses. DataTrust modes retain their
   separate DataTrust owner and are not routed through this EvalSafety context.

**Premises.** N6 advances the problem from the preceding revision, while the
recursive controller currently retains one root context across cycles. N4 and N5
check context/problem equality; that check is sound but its operand becomes stale
after a revision. The existing EvalSafety leaf preflight does not itself prove a
fresh head for every later basis. The owner/dataflow evidence and design are
recorded in
`/Users/deniskopylov/.codex/scratch/e02-r2-r1-r5-per-basis-context-owner-design-20260925.md@sha256:9c7063755f9b6c99a1c50e7dd04d1b2c27c3be6b728337f9dbfc2dde7b30fd79`.

**Proposed choice; principal status.** Prefer option 3 as the R1/R5 engineering
direction; Denis's principal ruling remains pending. If context resolution is
`not_established`, an explicitly admitted `candidate_only` run may still persist
proposal-only N4 with R1's typed unknown-context limitation. It does not claim a
WMR-grounded atom or effect and does not enter N5/N8, N9, S8 authority grading,
publication, or normative replay on that unknown. `simulate_only` may simulate
only with a valid current-basis context and skips N9 otherwise. Every protected
mode remains fail-closed before N4 if its exact-B context or fresh EvalSafety
admission is absent, stale, foreign, ambiguous, or mismatched. A supplied corrupt
or foreign context is invalid evidence, not an unknown to swallow. This candidate
limitation applies only to the positively admitted ordinary candidate route;
missing EvalSafety evidence does not reclassify a protected mode, and missing
DataTrust evidence does not reclassify `retrospective` or `measurement_audit`.

**P37/P38.** The active basis `B = hash(current_problem)` is recomputed at each
cycle; context currentness against `B` and the active world epoch is
`not_established` until the owner resolves it. Protected EvalSafety admission for
each `B` must be independently verified. The implementation/property divergence
is that consumers compare context to the exact problem correctly, but the
producer supplies the root context `S` after N6 advances to `B`; removing the
comparison would admit stale evidence. The gate must test owner refresh, not just
retain the equality marker.

**Remainder.** The context provider for a post-admission overlay W1 is a
separately confirmed R13 capability gap; this addendum does not claim it exists.
Until resolved, carry the candidate limitation and withhold protected work that
requires current W1. The per-basis EvalSafety refresh, context refresh and
consumer boundaries remain `verification_missing`/`bridge_missing`; all proposed
tests and probes are `UNRUN`. Historical hashed contexts and compiled-run
records remain replayable under their old projections; any added hashed fields
require a schema bump and historical serializer.

**Falsifier / revisit trigger.** Reopen if any `B != S` N4/N5 consumes the root
context, if a protected mode enters N4 without a fresh exact-B EvalSafety head, or
if an unknown candidate reaches N9/S8 authority/publication. The removal probe
keeps run/context/cycle markers valid while removing the per-basis refresh; a
two-cycle `S != B` witness must turn red. The preserving control removes owner
context for an ordinary admitted candidate request and requires proposal-only N4
plus the typed limitation, with no authority path. Test every protected mode with
both an exact current-B positive control and missing/stale/foreign/mismatched
negative cases; preserve N8's distinct fresh challenge. These are proposed
acceptance signals, not run receipts. Retain the Appendix A witness
`tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py::test_non_simulation_leaf_requires_current_eval_safety_head`; add the
per-basis removal/preserving tests in the changed whole-file P41 denominator.

**Where it binds.** N6's `current_problem` transition and N4/N5 context threading
bind in `runtime/quality/generation_cycle.py`; per-basis context construction and
validation bind in `runtime/quality/cycle_substrate.py` and the existing HTTP
context owner `runtime/http/services/control/generation_cycle.py`. Exact-leaf
protected admission binds at `runtime/quality/recursive_generation_cycle.py` and
`runtime/quality/evaluation_safety.py`. N9, S8, promotion, and publication readers
must consume the resulting typed status and retain their own authority checks.

## R9 — CAS supports several honest typed views of one blob

**Question.** How can the CAS deduplicate identical bytes while representing two
different, truthful typed profiles for those bytes?

**Options and costs.**

1. Keep one first-writer profile and return a bounded, typed profile-conflict
   refusal when a caller asks for a different view. This preserves honest refs and
   avoids caller-specific exceptions, but callers that use identical payload bytes
   for distinct legitimate views pay with a refusal until the store can represent
   that view. Existing simulation, deployment, and promotion consumers remain
   limited at that boundary. Every backend must still compare the stored winner's
   complete profile before returning a legacy ref; an unsupported backend may
   refuse a conflicting write, but cannot return a ref for an unheld profile.
2. Return a ref for the newly requested kind while leaving the first manifest in
   place. This avoids immediate caller failures, but the returned ref lies about
   the persisted profile and pushes integrity failures onto every later reader.
3. **Conditional multi-view proposal; principal ruling pending:** preserve
   immutable bytes and physical content deduplication while adding independently
   persisted, qualified view records. Each view must bind the exact blob, every
   consumer-visible immutable profile claim, and its runtime-resolved tenant/cell
   owner. `integrity.optional` must either participate in the versioned profile
   projection or be constrained to an exact owner-recomputed schema that rejects
   unsupported values before publication; the derived `integrity.sha256` is always
   recomputed against the bytes. The authority self-link must also be view-aware and
   acyclic: either omit only the derived `authority.manifest_ref` pointer from the
   view-key projection and then verify it equals the selected qualified-view URI, or
   carry it in a separate versioned reference contract. In either design, the
   existing bare `cas-manifest://<ArtifactID>` remains primary-view-only and cannot
   resolve an authority-bearing qualified view. Unsigned candidate bytes remain
   usable as candidate data; only contracts that require signed custody verify a
   signature bound to that exact view and tenant. Until per-view tenant isolation is
   proven, cross-tenant requests keep a typed refusal. Costs include profile and
   authority-reference migration for every affected reader, versioned refs and
   transfer, per-view ownership/signatures, backend and adapter work, and a complete
   path-scoped source inventory plus semantic consumer classification before the
   write set can be called complete.
   The backend boundary has two costed shapes: support typed views across every
   configured backend and adapter before exposing selection, which has the broadest
   implementation and migration cost; or begin with the runtime-supplied filesystem
   owner for the served ProgramGraph and deployed epoch-evidence corridors, while
   unsupported stores/adapters return a typed `artifact_view_unsupported` result.
   The scoped path is smaller but cannot serve a view when the runtime's actual
   owner is outside that boundary. Neither shape permits a primary, sibling, or
   bare-ID fallback. Even outside the selected-view scope, legacy writes must refuse
   a stored-winner profile mismatch.

**Premises.** B150’s distinguishing case is identical bytes under profile A and
profile B: the first manifest is preserved, but the second `ArtifactRef` advertises
profile B. Its source recommendation requires that a ref match actual persisted
semantics and preserve byte deduplication (`source/B_r19_original.md`, B150; bundle
`CAS-01.md`). At the inspected base, `ArtifactRef` carries content `ArtifactID`,
kind, and media type; `ArtifactOwnershipIndex` and signature lookup are keyed by
`ArtifactID`, while `has_signature(aid)` and `sign_artifact(aid)` do not identify a
separate typed view or tenant. With identical bytes, two tenants therefore share
the content ID: a signature or ownership entry for one tenant's view could be
mistaken for the other tenant's. Physical blob equality cannot establish tenant
ownership or authorize signature reuse
(`src/polisyos/core/artifacts/manifest.py@ecac478bce792c8451919e30d82bb25ba99662c7`,
`src/polisyos/core/artifacts/store.py@775d9811ae8fc3fd075845400b7a0b452600e387`,
`src/polisyos/core/artifacts/ownership.py@95dc77f264b38dc40d658cfb2c9b153265e7a99b`,
and `src/polisyos/core/artifacts/_signature_ops.py@793c4faea145ca25522860836ecab93747a732f5`).
The source recommendation preserves honest refs and byte deduplication; it does not
license tenant identity to collapse into the byte hash.

The independent R9 review found a second profile-binding premise: `IntegrityInfo.optional`
is defined as `dict[str, str] | None` and is inspected by five production files in
the complete 2,693-file Python source denominator. Those readers distinguish its
value and require `None`; excluding the whole integrity envelope would therefore let
consumer-distinguishable manifests share one view key. The five readers are
`src/polisyos/core/contracts/c4_persisted_profiles.py@59623501f71f545276f132f42d6d343cdbd41187`,
`src/polisyos/runtime/quality/data_forge_binding.py@3c5635a52efc4660a2dcd27f5c2fad96b70bf810`,
`src/polisyos/runtime/quality/promotion_sequence.py@dc8beab981b714e80e54bef22ba83bc66ab3ffd4`,
`src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`,
and
`src/polisyos/runtime/quality/open_world_risk.py@ba17f9bc0ea55873af99f97db2bdbe9b642e0a3d`;
the field is declared at
`src/polisyos/core/artifacts/manifest.py@ecac478bce792c8451919e30d82bb25ba99662c7`.
The smallest sound choices are to bind the exact optional claim or reject/recompute
values outside an owner-defined schema; `integrity.sha256` remains a derived byte
check, not a caller-supplied view claim.

The authority reference is another unresolved identity premise. The production
writer builds `ArtifactAuthorityInfo.manifest_ref` as
`cas-manifest://<ArtifactID>` at
`src/polisyos/runtime/http/services/control/artifacts.py@63eaad653c6a3627fe9e99873100829facefd1e7`,
and validators in
`src/polisyos/runtime/quality/promotion_sequence.py@dc8beab981b714e80e54bef22ba83bc66ab3ffd4`
and `src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`
require that bare-ID form. A complete `rg` census found this URI in 8 files of the
same 2,693-file Python denominator; named route/report/monitor consumers include
`src/polisyos/runtime/http/routes/artifacts.py@f20a3db2df9cdb3f74c1ad7bf6728d8d1bcb9ca3`,
`src/polisyos/core/artifacts/cas_integrity_report.py@c0ecac7e433443ebdce04272b7e8412c3e560477`,
`src/polisyos/runtime/quality/proving_ground/proof_carrying_analytics_search.py@2fddba3f792e94f9d43e1dd3e1ef77278e0fd1ae`,
and
`src/polisyos/scientist/governance/continuous/monitors.py@8fe83d14dda67a91b5655761ca3be3f5eb11f6d6`.
A qualified `(ArtifactID, view_id)` cannot be selected by that URI. Embedding a
qualified URI in `authority` while hashing the whole object creates a cycle; the
complete eight-file consumer census and a versioned acyclic self-link rule are
pre-code gates, not implementation details to infer from the failing test.

**Complete static boundary census and production-caller delta.** The read-only
P35 census is pinned to Phase 0 merge `73c656744f051d9f40667da7f8bc91c61d8b4ebf`:
all 2,693 tracked Python source files parsed with zero syntax failures, and all 23
tracked package TypeScript files were enumerated. Its overlapping counts are files,
not call totals: 35 store/adapter boundaries, 6 ProgramGraph path files, 17
epoch/authority path files, 8 `cas-manifest://` files, and 10 signed-evidence API
producer/consumer files; 461 files contain typed artifact/reference/manifest names,
328 dereference `artifact_id`, and 250 lower it to a string. The scan found no
`ArtifactViewRef`/`view_id` selector in Python or TypeScript. The receipt, scanner,
and full path/blob/site inventory are
`/Users/deniskopylov/.codex/scratch/e02-r2-r9-boundary-map-20260924.md@sha256:6015ffa95eccc6513a74c122d1663e2f55b1caec8829179b16eaa56be352cf6f`,
`/Users/deniskopylov/.codex/scratch/e02-r2-r9-boundary-census-20260924.py@sha256:709a324d7fe3d0d470b82a8efca67c91fb011158bc06273d6a1cfac6920f06bb`, and
`/Users/deniskopylov/.codex/scratch/e02-r2-r9-boundary-census-20260924.json@sha256:22a59f33ec11451820bcb3bb8512d4155633fcf4b8676db6b7ef3aa831836c20`.
These overlapping syntactic categories are not a 461-file implementation list;
the AST census does not establish runtime reachability, dynamic dispatch, or that
each candidate method is a CAS call.

The current artifact HTTP routes select by `artifact_id` and provide no view
selector; the three TypeScript files with artifact-ID tokens include a generated
type assertion, not a production view caller. Public view selection is outside the
initial filesystem-only boundary. If a selected view must cross HTTP, add it to the
owned versioned API schema and regenerate the client through its owner; do not let
the route discard a selector or resolve it as the primary manifest
(`src/polisyos/runtime/http/routes/artifacts.py@f20a3db2df9cdb3f74c1ad7bf6728d8d1bcb9ca3`,
`schemas/runtime_api_v1.openapi.json@21fd390c0d67340c380c5e8c4ea3b0666d9b5680`,
`packages/runtime-api-client/types.ts@06ec886c1f2eaeda0edfc044ac2e8cedd83f5438`).

The regression reaches a served caller: `JointSimulationController.run_once`
passes the selected plan's refs and atom parameters to `execute_program_graph` for
each horizon step
(`src/polisyos/runtime/quality/joint_simulation_horizon.py@e74fa941d673b98b51e3b90934db666ecfa6467c`).
The executor reduces `ArtifactRef | ArtifactID | str` to a bare ID and rebuilds
output lineage as ID-only `InputRef`s; a selector added only to the ref model would
be lost before persisted state, metrics, and reports
(`src/polisyos/foundry/execute/_internal/models/__init__.py@f4502d42c8ba7b57096bd8d7b8e5c0e681dcc77d`,
`src/polisyos/foundry/execute/_internal/graph/__init__.py@c771be51959fe826f197b77f88afadf3a6833c16`).
Compiler and patching paths also lower refs, as enumerated in the census inventory.
The exact ProgramGraph artifact ID and the two colliding input profiles remain
`UNRUN`; this confirms the production corridor, not the reported collision.

The deployed epoch corridor is a consumer of externally signed evidence, not a
proven local signed-evidence producer. `RuntimeContainer.install()` configures the
deployed intake; `EpochDeployment` captures its `ArtifactStore`, resolves signed
records through `FileSystemSignedArtifactEvidenceRepository.read_exact`, and
verifies their bytes/signatures under the configured trust role before the
transition bridge and cascade consume them
(`src/polisyos/runtime/http/container.py@d960e207accd81fa98187c96ce0fd9e5458bb369`,
`src/polisyos/runtime/quality/epoch_deployment.py@bc9edd50e2bdb52b9a259547a296bcb87c625b08`,
`src/polisyos/runtime/quality/epoch_transition_verification.py@cd2cb26e4e253f402d7cdca851bbd5bfff9698d3`).
The tracked-source census finds no direct production call to
`FileSystemSignedArtifactEvidenceRepository.persist_signed`; a view design must
preserve exact selected-manifest/signature resolution without claiming that this
deployed chain locally issues the admitted signature.

The backend census adds concrete fail-closed obligations. S3 and GCS name objects
by `ArtifactID`; when the manifest already exists, their write paths can skip
comparing the winner profile and return a ref labeled with the new caller's kind
or media type. This is the false-profile case from option 2 and must be fixed even
if those backends report typed view support as unavailable
(`src/polisyos/core/artifacts/backends/s3_store.py@26c85746a028674cc7b3f62617d4efeaf21b1976`,
`src/polisyos/core/artifacts/backends/gcs_store.py@ab91a7412b3249fcc368da1741e403d661dce562`).
The cache's bare-ID backfill omits `tenant_context`, `same_input_closure`, and
`authority`; it must preserve those fields or return typed unsupported, never
resolve a reduced cache entry as the requested primary view
(`src/polisyos/core/artifacts/backends/caching_store.py@346d899a4632e185f1afa77ab7efb576b1efdbd8`).
Signatures use one `<hex>.sig` path and bind exact manifest bytes; ownership is
indexed by `ArtifactID`, so neither signature nor ownership may transfer across
two views of one blob. Legacy v1 transfer enumerates only `.blob`, `.manifest.json`,
and `.sig`; view transfer must be additive, explicitly enumerate exact view
manifest/signature bytes, and import them into the destination runtime owner's
custody. Namespace and async adapters expose ID-only APIs, and the IR package has a
second ID/ref contract that also lowers to strings; they are outside an initial
filesystem-only support boundary until their selectors are carried end to end.

The Appendix A discriminator is
`quality.test_joint_simulation_horizon::test_program_graph_plan_loops_real_shared_state_executor`
(`policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py@8ed265c0b1fd980c1a189866d17166c05f7e188b`).
The Appendix B discriminators are
`unit.runtime.http.test_runtime_deployment_security::test_epoch_privileged_source_ports_are_captured_and_attested`,
`unit.runtime.quality.test_epoch_deployment::test_configured_policy_exchange_reaches_native_verifier_limitation`,
`unit.runtime.quality.test_epoch_deployment::test_privileged_native_verifier_is_operational_and_deployment_local`,
and
`unit.runtime.quality.test_promotion_epoch_deployment::test_configured_positive_carrier_still_hits_unchanged_ep_d03_refusal`
(`policy-engine/tests/unit/runtime/http/test_runtime_deployment_security.py@aa8d8bad3537b1ef16e43f8f0816112e9c8cec73`,
`policy-engine/tests/unit/runtime/quality/test_epoch_deployment.py@e2ffe8167bc3c4a702d31a7c823ed25555fff194`,
`policy-engine/tests/unit/runtime/quality/test_promotion_epoch_deployment.py@270187cb4598dd61d54bc6d7b9a2ec2d6143d008`).
The four-base P41 JUnit row receipts for these test identities are pending the
baseline broker at
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/r9-p41-cas-view-tests.junit.xml@PENDING_SHA256`;
the Appendix A/B comparisons remain hypotheses until those outcomes, flags, and
test blob identities are recorded. The reported ProgramGraph `inputs` conflict
does not yet establish the artifact ID or the two persisted input profiles; capture
both from the frozen P41 run before designing against that collision. These tests
and the profile/self-link probes below remain `UNRUN`.

**Conditional proposal; principal status.** Option 3 remains a lane proposal, not
an adopted design, principal ruling, implementation authorization, or claim that
multi-view support exists. If Denis selects honest typed views, keep `ArtifactID`
as the hash of exact bytes and introduce a separate strict qualified view identity
whose resolution recomputes the selected manifest, blob, full profile, and
runtime-bound tenant/cell ownership. Never resolve a missing view through the bare
ID, primary manifest, sibling view, or their signature. Unsigned candidate views
may resolve as candidate data without authority; a consuming contract that requires
signed custody must verify a signature for that exact view and tenant, otherwise
return a typed refusal. Preserve historical manifest, signature, and v1 transfer
bytes exactly; keep legacy `ArtifactRef` and `InputRef` unchanged and version any
qualified-reference DTO and its hashed enclosing projections.

Before code, freeze P41 outcomes and complete the semantic classification of the
P35 census of profile readers, authority URI producers/validators, ref-lowering
paths, adapters, and transfers. The static denominator and URI/adapter inventory
are now recorded in the census cited above; before calling a scoped write set
complete, classify every selected producer,
lowering, backend, and consumer in that inventory and resolve dynamic/DI call paths
for the chosen corridors. Do not expand this into a blanket conversion of all 461
files with typed-reference names. For `integrity.optional`, choose and test one owner
rule: include its exact persisted
value in the view key, or define the exact permitted schema, recompute permitted
values, and reject all other values before publication. Recompute `integrity.sha256`
from payload bytes. For `authority.manifest_ref`, choose one acyclic contract: derive
the view key from all authority fields except only this computed self-pointer, then
store and verify the pointer against the exact qualified view URI; or add a separate
versioned authority-view reference and migrate every reader. In either case, retain
all other authority fields in the profile key and make the legacy bare-ID URI
primary-only. If affected consumers cannot be migrated without weakening historical
or authority checks, keep that authority profile on the primary-only path and leave
multi-view authority support open. The exact ProgramGraph `ArtifactID` and colliding
`inputs` manifests, principal choice, code, and all behavior witnesses remain
pending.

**Legacy reference and chronology-hash boundary (clarification).** Preserve the
existing `ArtifactRef` and `InputRef` field sets and serialized forms. Do not add an
optional view selector to either legacy type. Introduce a separate strict, versioned
`ArtifactViewRef` carrying the blob `ArtifactID` and immutable full-profile ID, and
provide explicit view-aware store APIs; any persisted DTO that must carry this ref
uses a new v2 schema while its v1 serializer remains byte-exact and primary-only.
Legacy v1 import/export transports only the primary manifest and its exact signature
bytes. A separately versioned view-transfer inventory carries each qualified view's
exact manifest bytes and, when signed custody is required, its signature bytes bound
to that view; it cannot reinterpret or replace the primary manifest. A qualified read
or signature lookup has no fallback to the primary view.
This split is required because chronology's `_raw_model_mapping` enumerates model
fields into canonical bytes with `exclude_none=False`; persisted chronology objects
and the v1 signed-evidence record therefore change their bytes and hashes if a nullable
field is added to a nested legacy ref. `SignedArtifactEvidenceRecord` includes several
`ArtifactRef` fields, and its bytes are framed and content-hashed, so a new field
cannot be made backward-compatible by defaulting it to null
(`src/polisyos/core/contracts/chronology.py@a2853507e54a339fb5cfc70c5c5a699e2859c10f`,
`src/polisyos/core/artifacts/signed_evidence.py@917909c44ed187cf16e0bd8a466b279039dcbd12`,
`src/polisyos/core/artifacts/manifest.py@ecac478bce792c8451919e30d82bb25ba99662c7`).
The legacy `ArtifactRef`/`InputRef` shape and primary manifest/signature byte sequence
remain the historical contract; the qualified type and v2 envelope are additive.

**Qualified input lineage at consumers (clarification).** A v2 view manifest must
use a separate strict `ArtifactViewInputRef {view_ref, role}` for each lineage edge;
the legacy `InputRef {artifact_id, role}` cannot distinguish two qualified views of
one blob. Do not add an optional selector to `InputRef`, and do not lower
`ArtifactViewRef` to its bare `artifact_id` before a view-aware read, write, or
lineage record. The v2 serializer and importer must round-trip the qualified view
selector and role; v1 serializers and primary-only history remain byte-exact. A
complete static source census is attached above; dynamic/reachable caller
classification remains a closure gate. Existing lowering surfaces that need
explicit selector-preservation review include ProgramGraph input construction in
`src/polisyos/foundry/execute/_internal/graph/__init__.py@c771be51959fe826f197b77f88afadf3a6833c16`,
Foundry execute artifact lineage in
`src/polisyos/foundry/execute/api.py@0d8aa78d13b69277f9ae35c8083ecfa07c84b19a`,
and epoch-transition artifact inputs in
`src/polisyos/runtime/quality/epoch_transition_inputs.py@8a5c44bb231027f156edf9d6dd2977424d714cfd`.
These examples do not claim to be the complete set: enumerate every producer,
lowering, transfer, and consumer. A positive v2 round-trip must preserve two refs
with one blob ID but different view IDs and verify each exact manifest; a
marker-preserving selector-removal probe must fail rather than silently resolve the
primary or sibling view. The v1 byte oracle remains a separate required control.

**Canonical profile and view-key input (proposed).** Define a versioned
`cas-view-profile/v1` projection over the complete persisted semantic profile:
`kind`, `media_type`, `byte_size`, `artifact_schema` (serialized as `schema`),
`canon`, ordered `inputs`, `producer`, `env`, `governance`, `tenant_context`,
`same_input_closure`, ordered typed `warnings`, all consumer-visible `authority`
fields, and `integrity.optional` unless the owner instead enforces an exact
recomputed schema and rejects unsupported values before publication. Warnings and
optional integrity claims are persisted distinctions: changing one must either
change the view key or be refused/recomputed by that explicit schema. The current
`ManifestLifecycle.profile_mismatches` omits `warnings`, so the view owner must
extend its projection and write contract. Do not exclude the entire integrity
envelope: recompute `integrity.sha256` against the exact payload and never accept it
as a caller claim.

For authority, exclude only the derived `manifest_ref` self-pointer from key
computation, while retaining every other authority field; after the view key is
derived, store the qualified pointer and verify that it equals the selected view
URI. If this cannot be made compatible with all readers, use a separate versioned
authority-view reference instead. The old bare-ID `cas-manifest://` URI continues
to resolve only the primary manifest. Canonicalize this versioned projection with
the manifest serializer's stable JSON rules: JSON-mode fields with aliases,
`exclude_none=True`, sorted object keys, and list order preserved. Derive the view
key from a versioned envelope containing exact payload SHA-256, runtime-resolved
tenant/cell owner identity, and the canonical projection. `artifact_id` is excluded
from the projection but the payload digest remains an outer key input;
`created_at` is excluded as instance-time metadata. Same-profile retry means the
same payload digest, resolved owner, and byte-exact canonical projection and must
converge on one view record. A required signature binds to that view key but is not
a profile-key input. The serializer, optional-integrity schema, self-pointer
derivation, and consumer URI agreement are proposed contracts, not implemented or
validated here. The current projection sources are
`src/polisyos/core/artifacts/_manifest_lifecycle.py@0681605eed226b2638dce4cb9d7b9e710491323d`
and
`src/polisyos/core/artifacts/manifest.py@ecac478bce792c8451919e30d82bb25ba99662c7`.

Tenant quota admission must reserve the incremental payload and exact serialized
primary/view metadata, plus any signature sidecar required by the consuming
contract, before publishing a view. The current tenant CAS preflight
checks `len(data) + 4_096`; that fixed allowance is not sufficient evidence that a
new view sidecar fits. If the transaction cannot reserve all required metadata
within the tenant allowance, refuse before making the view visible; do not publish
a blob-only or partially manifested view. The measured implementation is
`src/polisyos/fabric/storage/tenant_cas.py@d45d8a5856d38fed50f8fe3a1e24e8cb92858164`.

**P37 — gate predicates at admission.**

- Blob identity is SHA-256 over the exact persisted bytes (`recomputed`).
- A typed view exists only if the store resolves its immutable view record and
  recomputes its binding to the blob and complete profile (`recomputed`). The
  requested kind/schema/inputs are consumer assertions (`consumer_asserted`) until
  persisted under that view identity.
- Tenant ownership must resolve from explicit tenant-bound view metadata and the
  owning tenant store/context (`independently_reconciled`). A missing tenant binding
  is `not_established`; a matching content `ArtifactID` is not tenant evidence.
- Signature verification is a required predicate only when the caller or
  authority contract requires signed custody. Candidate CAS storage with
  `SigningConfig(enabled=False, sign_on_put=False)` does not assert or require a
  signature. When required, a signature must bind to the exact view identity and
  tenant (`independently_reconciled`); the current ID-only signature index is
  insufficient to distinguish cross-tenant views, so the required signature is
  `not_established` unless separately stored view-bound signature evidence exists.
  If that required signature is absent or unverifiable, the authority decision
  fails closed.
- A qualified view resolves only by its qualified identity. Missing qualified
  metadata cannot fall back to the bare `ArtifactID` primary manifest or signature.
- The view key is recomputed from the versioned profile projection, payload digest,
  and runtime-resolved tenant/cell owner. It includes warnings and either includes
  `integrity.optional` or enforces the declared exact schema/recompute/refusal rule;
  `integrity.sha256` is recomputed from the blob. It includes every authority field
  except only the derived self-pointer, which must validate against the selected
  qualified URI; this binding does not prove empirical origin or warning truth.
- Tenant quota admission must recompute/reserve the bytes for the exact primary
  and view metadata, plus any required signature sidecar, before publication. The
  current `len(data) + 4_096` estimate is `not_established` as a bound on variable
  sidecar size; no view may publish until the required incremental bytes are admitted.
- `ArtifactRef` and `InputRef` are nested in persisted manifests and other hashed
  DTOs. Any qualified-ref extension must preserve historical projections byte
  exactly by versioning the qualified ref or the enclosing schema and serializer.
- Equal bytes never imply equal lineage or provenance. Any absent lineage relation
  remains `not_established` rather than inferred from the shared blob hash.

**P38 — property and divergence.** Property: content may have multiple typed views
only when each view's exact profile and tenant owner are independently resolvable,
and when a caller requires a signature, that signature resolves for that view.
Current implementation: `ArtifactOwnershipIndex` and signature operations key only
on content `ArtifactID`; the store can therefore confuse same-byte tenant views,
while CAS signing is optional. `ManifestLifecycle.profile_mismatches` omits persisted
`warnings` (`src/polisyos/core/artifacts/_manifest_lifecycle.py@0681605eed226b2638dce4cb9d7b9e710491323d`)
and the proposed key would also be wrong if it excluded all integrity metadata:
`IntegrityInfo.optional` is read by five consumers in the complete 2,693-file Python
denominator and can alter their classification. The authority producer and two
validators use `cas-manifest://<ArtifactID>`, which resolves only the primary view
and cannot identify `(ArtifactID, view_id)`; putting a qualified URI into the hashed
authority object also creates a self-reference cycle unless the derived pointer
alone is projected out and then checked. The URI occurs in 8/2,693 source files;
the complete static set is recorded in the boundary census above, but its consumers
still require classification for the selected view scope. `TenantScopedCAS.put_bytes` preflights
`len(data) + 4_096` and does not size a proposed view sidecar
(`src/polisyos/fabric/storage/tenant_cas.py@d45d8a5856d38fed50f8fe3a1e24e8cb92858164`).

Divergent cases: ID-only ownership/signature cannot distinguish tenant A from B;
a warning-only or consumer-visible `integrity.optional` change can reuse one key;
a bare-ID authority URI can select the primary rather than the selected view; a
self-referential qualified URI cannot be hashed as part of itself; and a variable
sidecar may exceed the fixed quota allowance. Probe each distinction while keeping
view markers fixed: reject or change the key for warning/optional-integrity changes;
refuse bare-primary or sibling resolution; and reject an altered self-pointer. A
positive derivation must produce the same qualified self-pointer from the same
acyclic key inputs and validate it on read. Same-byte tenant views, signature
isolation, unsigned candidate behavior, exact quota refusal, and idempotent retry
remain required controls. The full-profile mechanism and all these controls are
unimplemented and `UNRUN`.

**Remainder.** This proposal does not claim equal bytes have equal empirical
origin, authorize changing an existing profile, or decide that the CAS can verify
empirical meaning of kind, warnings, or lineage. Consumers retain their own source
and semantic evidence duties. The complete static source census closes the earlier
enumeration gap, but P41 JUnit results, the exact ProgramGraph artifact ID and both
colliding input manifests, semantic/dynamic caller classification for the chosen
scope, principal ruling, owner assignment, and every new witness are still pending;
none is a closure receipt. Per-view concurrency and quota remain implementation
obligations. Cross-tenant views stay refused until view-level
ownership isolation and any contract-required signature binding are proven. The
shared content hash never substitutes for tenant custody. If the optional-integrity
or authority self-link rule cannot preserve all consumer distinctions and historical
checks, the bounded residual is primary-only authority/profile use; do not publish a
view that silently conflates those claims.

The initial backend/API boundary is also unresolved pending principal choice. A
filesystem-only rollout must return `artifact_view_unsupported` from S3, GCS,
caching, async, IR, namespace, and other unwired adapters; it must not infer primary
selection from a missing selector. The legacy S3/GCS profile-mismatch path still
needs a full stored-winner comparison and typed refusal even when view support is
unsupported. A full-backend option must additionally prove view identity, ownership,
signature, transfer, and quota behavior in each backend. No public HTTP selector or
generated TypeScript support is proposed until its owned schema and route are
versioned. The static census also did not establish a production caller of
`FileSystemSignedArtifactEvidenceRepository.persist_signed`; deployed epoch evidence
is consumed and verified, while local view-signature production remains
`not_established`.

**Remainder standing and signatory.** The CAS has no standing to prove empirical
origin or consumer-specific lineage; those predicates remain `not_established` by
the CAS alone, and each consuming owner must sign or independently reconcile its
own evidence. Candidate artifact storage need not create a signature; authority
consumers retain their own signed-custody requirement where their contract says so.
The `polisyos.core.artifacts` package owns artifact IDs, manifests, signatures, and
the CAS boundary (`src/polisyos/core/artifacts/README.md@7b4cc0bb5ae7dd9c4602fcf1b6ff1186881bfc4c`). A named
engineering owner/signatory for the multi-view contract and cross-backend
implementation is not established by that package README or this draft; that
assignment remains `unallocated/not_established` until made. Denis remains the
pending principal signatory for the semantic choice to support honest typed views.
The independent review
`/Users/deniskopylov/.codex/scratch/e02-r2-r9-independent-review-20260924.md@sha256:e32d6dff6dda46fb67ba4b586bdc693a438acb32591531877f8fcd18876530df`
returned NO-GO to implementation of the prior option-3 wording. This correction
addresses its optional-integrity and self-link gaps and adds the complete static
boundary census; it does not classify every consumer semantically, measure the
exact ProgramGraph profiles, establish dynamic reachability, or replace the
principal's ruling.

**Falsifier / revisit trigger.** Reopen if any backend returns a view ref whose
resolved manifest differs from it, if concurrent same-profile retries create
divergent duplicate view records, if a tampered view can point at a different
blob/profile while retaining a green verification result, or if a signature for
tenant A's view verifies tenant B's same-byte view. Under the all-backend option,
the acceptance signal is the A/B same-bytes witness through filesystem, S3, GCS,
and caching-store contracts: both view manifests resolve only under their own
tenant and exact profile; signing only A cannot satisfy a contract-required
signature check for B. Under the filesystem-only option, the filesystem owner gets
that positive witness and each unsupported backend/adapter returns typed
`artifact_view_unsupported` with no fallback; its legacy conflicting-profile write
must still refuse rather than return the new caller's ref. A distinct
positive control stores and resolves unsigned candidate content under
`SigningConfig(enabled=False, sign_on_put=False)` without producing an authority
result. A qualified-reference removal probe keeps the bare primary artifact and
its manifest/signature intact while removing the qualified view; lookup must refuse
instead of falling back. Preserve the historical primary manifest and signature
bytes through export/import and historical-reader round-trip byte-exactly. Remove
tenant metadata while preserving view markers and bytes; the tenant-bound access
must fail. Change only `warnings` and only `integrity.optional` while retaining the
view marker: each must change the recomputed view identity or be rejected/recomputed
by the declared exact schema; recompute `integrity.sha256` from bytes. Change the
authority self-pointer to a bare primary URI and then a sibling-view URI with all
other markers intact; both must refuse. The positive self-link control derives a
stable qualified URI from acyclic inputs and validates it on read. Concurrent
retries with the same payload, owner, and complete profile must converge on one
view; changing only `created_at` must not change it, while different bytes must.
After P41, capture the actual ProgramGraph artifact ID and both colliding input
profiles. The quota probe leaves enough capacity for current `len(data) + 4_096`
but not the exact serialized view and required signature sidecars; refuse before
publication. A `.views/<profile>.manifest.json` sidecar cannot simply reuse today's
recursive `*.manifest.json` namespace because the filesystem enumerator parses its
basename as an `ArtifactID`; change that layout or the shared enumerator as one
owner-level design. View sidecars count toward tenant quota. Caching, async, IR, and
ProgramGraph paths must preserve the selector and complete write profile;
`CachingArtifactStore` currently addresses manifests by bare `ArtifactID` and omits
`tenant_context`, `same_input_closure`, and `authority` when reconstructing cache
`PutOptions`. The current `LoweredIRRef`/`ProgramGraphRef` has no qualified selector,
and ProgramGraph lowering reconstructs refs from the bare ID. All these probes, the
Appendix regressions, and the ProgramGraph collision details are `UNRUN` /
unmeasured; no principal choice or implementation is claimed.


**Where it binds.** Shared contract
`src/polisyos/core/artifacts/protocol.py@cc012c638b833e52d9658b91364398f81b7dd741::ArtifactStore`;
typed references and historical projections in
`src/polisyos/core/artifacts/manifest.py@ecac478bce792c8451919e30d82bb25ba99662c7`;
manifest lifecycle and `FileSystemCAS` in
`src/polisyos/core/artifacts/_manifest_lifecycle.py@0681605eed226b2638dce4cb9d7b9e710491323d` and
`src/polisyos/core/artifacts/store.py@775d9811ae8fc3fd075845400b7a0b452600e387`;
configured S3/GCS implementations at
`src/polisyos/core/artifacts/backends/s3_store.py@26c85746a028674cc7b3f62617d4efeaf21b1976`
and `src/polisyos/core/artifacts/backends/gcs_store.py@ab91a7412b3249fcc368da1741e403d661dce562`;
ownership index at
`src/polisyos/core/artifacts/ownership.py@95dc77f264b38dc40d658cfb2c9b153265e7a99b`;
signature operations at
`src/polisyos/core/artifacts/_signature_ops.py@793c4faea145ca25522860836ecab93747a732f5`;
signing configuration at
`src/polisyos/core/artifacts/signing.py@cc3082cdf613707d6df284266fc8c97e565bba84`;
caching boundary at
`src/polisyos/core/artifacts/backends/caching_store.py@346d899a4632e185f1afa77ab7efb576b1efdbd8`;
async/IR adapters at
`src/polisyos/core/artifacts/async_store.py@cfab46e12fe8c42af84b391e852da9ca91d33f08`
and `src/polisyos/core/artifacts/ir_adapter.py@ea124f8447af2bb7fc68d8887e3d47c080ee29ef`;
Foundry refs at
`src/polisyos/core/contracts/foundry.py@70d0c344fe8418314ffd634bf40b3ead3484f49f`;
ProgramGraph lowering at
`src/polisyos/foundry/compile/trinity_compiler.py@c2ef2b5acb787b17d253750c612d1f2ed3c5900f`;
and transfer at
`src/polisyos/core/artifacts/_transfer_ops.py@ea6697559933d3eb74c70aec978948297c6c8e52`.
The actual served callers are
`src/polisyos/runtime/quality/joint_simulation_horizon.py@e74fa941d673b98b51e3b90934db666ecfa6467c`
and the deployed epoch chain in
`src/polisyos/runtime/quality/epoch_deployment.py@bc9edd50e2bdb52b9a259547a296bcb87c625b08`,
`src/polisyos/runtime/quality/epoch_transition_verification.py@cd2cb26e4e253f402d7cdca851bbd5bfff9698d3`,
and `src/polisyos/runtime/http/container.py@d960e207accd81fa98187c96ce0fd9e5458bb369`.
The scoped store boundary also includes tenant quota and adapter mediation in
`src/polisyos/fabric/storage/tenant_cas.py@d45d8a5856d38fed50f8fe3a1e24e8cb92858164`,
`src/polisyos/core/security/namespace.py@b939e5a1bd44e6870dc18a56dcd2a8b05f615b18`,
and `src/polisyos/runtime/quality/non_data_acquisition.py@f437ce1cf10d1f5bdbfdb7e9566ae45e40303e47`.
No caller may
construct an envelope to compensate for a missing CAS view API or tenant-bound
signature owner.

**Additional consumer bindings and census gate.** The `integrity.optional` reader
set is the five production files named in the premises. The current authority URI
writer is `src/polisyos/runtime/http/services/control/artifacts.py@63eaad653c6a3627fe9e99873100829facefd1e7`;
validators include `src/polisyos/runtime/quality/promotion_sequence.py@dc8beab981b714e80e54bef22ba83bc66ab3ffd4`
and `src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`.
The URI census found 8 source files / 2,693 Python files: the writer, two
validators, and `runtime/http/routes/artifacts.py`, `core/artifacts/cas_integrity_report.py`,
`runtime/quality/data_forge_binding.py`,
`runtime/quality/proving_ground/proof_carrying_analytics_search.py`, and
`scientist/governance/continuous/monitors.py` (exact blobs are listed in the
premises and the full census JSON). The static census enumerates all eight URI
sites; before code, classify each producer/reader and the other profile readers as
selected-view or primary-only, resolve dynamic dispatch on the chosen routes, and
attach the path@sha output to the lease map. The syntactic inventory is complete;
semantic consumer coverage is not established by that count.


**Pattern pass.** P05/P27/P31/P32/P37/P38. The instance symptom is a CAS conflict;
the class is the mismatch between a content key and a single semantic view. Target:
one generic, typed multi-view contract implemented by the shared owner, not
consumer-specific exceptions. A second R9 symptom is a boundary loss of the view
selector; it remains the same P40 class because every escape is a consumer of the
same artifact-view identity. Multi-view refs/artifacts are `artifact_missing` and
consumer resolution is `consumer_missing` until manifests, required-signature
semantics, quota accounting, historical replay, and the selected support boundary
are wired. A filesystem-only rollout requires positive producer/consumer witnesses
on the served corridors and typed unsupported behavior with no fallback on every
unwired backend/adapter; all-backend support requires positive witnesses across each
configured backend. Neither rollout makes the 461-file syntactic reference set a
blanket conversion list.

### R9 addendum — P41 reassessment and lean deviation (2026-09-25)

**Status and relation to the earlier proposal.** This dated lane proposal is based on
the four-base P41 collision capture and the subsequent class reassessment. It
supersedes the earlier conditional multi-view recommendation and the generic
multi-view target in the Pattern pass above as the proposed repair for these
measured regressions. That text remains design exploration, not the current lane
repair recommendation. This addendum does not close B150 or settle whether PolicyOS
needs a general same-bytes/multiple-use capability. No principal choice or repair
behavior is established by this addendum.

**Question.** Should R9 address the observed ProgramGraph and epoch profile
conflicts by weakening CAS profile validation, adding generic typed views, or
correcting the producer-owned profiles while preserving strict CAS semantics?

**Options and costs.**

1. **Lane proposal — preserve strict CAS and correct the two producer profiles.**
   Keep `_ManifestLifecycle.validate_profile` fail-closed. In the ProgramGraph
   owner, emit no constraint report when no `check_constraints` operation ran; when
   checks do run, derive the report's input lineage from the definitions and state
   actually consumed. Leave state-delta and metrics input lineage intact. In the
   test-owned epoch setup, request `policy.admission` for the initial write used by
   `_policy_configuration`, while retaining the fixture helper's existing default
   for unrelated chronology cases. The graph/report owner bears the producer
   contract and test cost; test owners bear the narrow fixture change and replay
   cost. This preserves byte deduplication and truthful refs, but leaves generic
   occurrence provenance unresolved.
2. **Add generic selected multi-view CAS now.** This could represent two genuinely
   required profiles over identical bytes, but costs a versioned view contract,
   tenant-bound ownership and signatures, quota and transfer rules, adapter and
   consumer migration, ProgramGraph selector propagation, and historical
   serializers. The artifact-store owner and every admitted producer/consumer
   would carry that broad implementation and compatibility cost. P41 supplies no
   witness that either measured regression needs two simultaneously consumed
   profiles; the exact ProgramGraph manifest/input list was not captured.
3. **Add a typed use/provenance record if an existing run/evidence owner cannot
   preserve the relation.** This can keep one physical blob and one truthful
   manifest while recording separate event uses. It costs a typed producer,
   persistence, replay and consumer path only if the existing owner is insufficient;
   the artifact owner and affected runtime consumer owner carry that work. No
   complete generic use-record owner or served caller requiring this record is
   established; do not create an envelope without that witness.
4. **Return a ref for a requested profile that the store does not hold — rejected.**
   It avoids the immediate exception but makes the ref claim a false kind or input
   closure. Readers then bear the integrity failure, contrary to B150 and the
   CAS owner's contract.

**Premises.** P41 records the ProgramGraph discriminator as 24 passing cases at
the execution base, 23 passing and one failing at E02, 24 passing on main, and 23
passing and one failing at Phase 0. Its failure names the same blob
`sha256:7b19c822faafb9f9a41dfdba35ee9195060e12cb60fb434f8a53544153b00bcd` and
only an `inputs` mismatch; P41 did not retain the first manifest or exact input
list. Source shows an empty default `ConstraintReport` is persisted even when no
constraint-check operation ran, with the broad run input list including changing
patch refs. Those refs are real dependencies of state deltas/metrics, but are not
dependencies of an unchecked empty report. P41 also records four main-to-Phase-0
epoch setup failures with `kind` mismatch on the same admission blob
`sha256:d9c2c0b074bc0f24007b282fdaaacce72c2be4bc7966ade07a2d6c6994ef4f04`:
the fixture first stores the canonical statement as
`fixture.predicate-policy-admission`, then `_policy_configuration` persists those
same bytes as `policy.admission`. The fixture label has no independent semantic
reader; the signed policy type is consumer-facing. These four epoch comparisons
are main-to-Phase-0 only; the affected cases or test files are absent at the older
E02 revisions. The strict store check correctly refuses both mismatches, and B150
allows a typed use/provenance record as an alternative when distinct uses are
actually required. Evidence:
`/Users/deniskopylov/.codex/scratch/e02-r2-r9-class-reassessment-20260925.md@sha256:1f54814c61acf25410302b99fa336599d874016bb79833f65b656630cb44ea4b`;
`/Users/deniskopylov/.codex/scratch/e02-r2-r9-p41-collision-capture-20260925.md@sha256:3356a5c5d2309274d27276332be69f4819326c2e0ebcc7d2cdc97b49bfd8d396`;
`PolicyOS_E02_Combined_Agent_Package/bundles/CAS-01.md@36bcff0953c8b8e010f66ad7a0b355458b0f640d`.

**Proposed choice; principal status and deviation.** The E02-R2 lane proposes
option 1 for the observed regression repairs: strict CAS, a truthful output-specific
ProgramGraph constraint-report profile, and a fixture-specific `policy.admission`
initial kind. This explicitly deviates from the original R9 lean in §7.1, which
asked to support multiple honest typed views of one blob. The P41 evidence explains
the deviation: these two conflicts have producer-side causes and do not demonstrate
that multiple semantic profiles must be selected concurrently. This remains a lane
proposal for principal consideration, not principal approval and not proof that the
proposed fixes work. Keep the broader view/use decision pending; the current generic
multi-view producer/consumer chain and a complete typed use-record owner are
`not_established`. No production signer, authority view, API selector, or
backend-wide support is proposed here.

**P37 — predicates at admission.** CAS recomputes exact byte identity and whether
the requested profile equals the stored manifest (`recomputed`). It does not
recompute whether a caller's `inputs` were consumed to produce an output or whether
a `kind` names the actual semantic type; those producer predicates are
`not_established` until the owning paths derive and behaviorally verify them. For
the ProgramGraph case, the precise persisted input list is `not_established` even
though source and the failing field point to the broad generic input list. For the
epoch fixture, P41 and source establish the write order, canonical payload identity,
requested kinds, and the absence of a consumer for the fixture label; this supports
the narrow fixture alignment, but does not establish an issuer or signed production
authority. A generic selected view, tenant ownership, and a required signature
would each need independent owner/store reconciliation; a caller-supplied view ID,
kind string, or test key cannot establish them.

**P38 — property and divergence.** Property: every returned ref describes the
exact persisted artifact profile, and each profile's lineage names the inputs that
actually produced that artifact. The CAS currently compares the requested profile
to the first persisted profile and correctly refuses a mismatch. The ProgramGraph
producer diverges by attaching step-varying patch refs to a constant empty report
that ran no checks; the equality gate then refuses a later report write even though
those refs did not affect that report. The epoch test helper diverges by first
persisting the consumer-facing policy statement under a fixture-only kind, after
which the signed-evidence owner correctly refuses to return a `policy.admission`
ref over that stored manifest. Relaxing the gate would make the returned ref
untruthful. A generic view marker would also diverge if it selected a manifest
without recomputing actual inputs and reconciling owner/signature evidence.

**Remainder and standing.** The ProgramGraph repair does not settle whether a real
checked report may recur with identical bytes and different necessary input
closures; its actual checks must remain bound. The epoch fixture alignment does
not appoint an issuer or change the deployed epoch reader's signature policy.
B150's broader distinct-use provenance remains `not_established`: the existing
simulation receipt is partial, and no complete generic use-record producer was
identified. The artifact owner owns strict blob/profile integrity; the graph
producer owns report semantics; the test helper owns fixture labels. The principal
and CAS/artifact owner retain the decision on generic selected views versus a typed
use record. No historical manifest/signature is restamped, and no source or test
behavior is claimed fixed or verified by this draft.

**Falsifier / revisit trigger.** For option 1, retain report and fixture markers,
then remove the `check_constraints`-ran condition: the unchecked report must again
carry irrelevant changing patch inputs and reproduce the collision. Keep a positive
control with an actual check proving its report persists with the checked
definitions/state lineage, and keep state-delta/metrics lineage for their patch
dependencies. Restore the fixture's initial
`fixture.predicate-policy-admission` kind while retaining the later
`policy.admission` signed write: the setup must refuse the mismatch; the preserving
control uses `policy.admission` for this configured fixture and confirms
verification reads the exact persisted manifest, while unrelated chronology
fixtures still use the default. Separately, retain API markers but remove strict
stored-profile comparison; changed-kind and changed-input negative writes must
then show why the returned ref would be false. Reopen the generic-view/use-record
choice only when a served production witness shows identical payload bytes with two
independently required semantic relations, both consumed; first demonstrate that
the existing typed run/evidence owner cannot preserve the relation. Removing just
one selected view/use while leaving the blob and sibling relation must break only
its dependent consumer. A synthetic two-profile unit case alone does not falsify
the present lane proposal. These are acceptance probes, not results already run.

**Where it binds.** Strict stored-winner profile checks at
`src/polisyos/core/artifacts/_manifest_lifecycle.py@0681605eed226b2638dce4cb9d7b9e710491323d`
and `src/polisyos/core/artifacts/store.py@775d9811ae8fc3fd075845400b7a0b452600e387`;
truthful report emission/lineage at
`src/polisyos/foundry/execute/_internal/graph/__init__.py@c771be51959fe826f197b77f88afadf3a6833c16`
and its served horizon caller
`src/polisyos/runtime/quality/joint_simulation_horizon.py@e74fa941d673b98b51e3b90934db666ecfa6467c`;
the fixture write at `tests/_helpers/chronology_qualification.py` and its
`_policy_configuration` consumer in
`tests/unit/runtime/quality/test_epoch_deployment.py`; and the shared conflict
negative at `tests/unit/core/phase0/test_artifact_store.py`. The behavior witnesses
are the ProgramGraph horizon and real constraint-executor tests plus the listed
epoch setup/readers. This addendum does not authorize a general view selector,
production epoch signing, unrelated API/generated artifacts, or changes to the
debt register/plans. P41 measured the prior behavior; proposed repair controls
remain unrun and must be verified before any closure claim.

## R11 — CYC-04 blocked repeated candidate must not reach N9

**Question.** When the loop marks a repeated candidate `blocked`, what must happen
at the final-run and promotion boundaries, and which consumers actually read the
`LoopVOIDecision` type?

**Options and costs.**

1. **Proposed lean:** preserve `blocked` as a distinct non-advancing safety cap for
   repeated candidates. Recompute that a blocked decision is final and consistent
   with the run terminal, then prevent the blocked run from entering N9 promotion or
   any current-authority projection. The scheduler's `advance` remains advisory.
   This preserves the specific integrity meaning, but requires a run-validator
   invariant, an N9 guard, and served consumer witnesses.
2. Map `blocked` to `stop` or `escalate` before finalization. This reuses the older
   vocabulary, but loses the distinction between an invalid/non-progressing repeated
   candidate and an ordinary stop or a request for human judgment. It still needs
   the same N9 and terminal-consistency guards.
3. Treat `scheduler_action=advance` as authoritative and continue. This avoids a new
   action state, but permits a repeated candidate to count as new progress and can
   send it to N9 despite the block.

**Premises.** The phase-0 JUnit receipts are
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-20260924T084614Z-77175/cells/e02_execution_base/test_generation_cycle.junit.xml@5cc9da821ca9b6940f7bc6e1123f6fb663283b5367002cf12c93d5ad6a1a6588`
and
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-20260924T084614Z-77175/cells/e02_head/test_generation_cycle.junit.xml@4fc8f811e7a08e4227c6236bd52e3bd1122f984c75d5a904dacf0d962cafc71e`.
The E02-head failure shows final `next_action=blocked`,
`terminal_kind=search_ceiling_repair_required`, `scheduler_action=advance`, and
`reason=fake_cycle_same_candidate_repeated`. The E02-head test expects `stop` or
`escalate`; the base test file has a different blob and the same `repo_root` wiring
was added on E02, so these receipts do not prove a pass-to-fail change for an
unchanged test
(`tests/unit/runtime/quality/test_generation_cycle.py@beb20c6bb8e1ed8aa46910fea0d3a4cf7cfabe15`;
`tests/unit/runtime/quality/test_generation_cycle.py@28682ef61d0cec22f2420794f7e3aa3e396418b4`).
The E02-head `_fake_cycle_reason` compares adjacent
`selected_candidate_content_hash` fields. `_candidate_content_hash` accepts an
object-supplied `sha256:` from the atom, candidate, or provenance without recomputing
canonical owner bytes, and otherwise hashes only the candidate ID
(`src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`).
The JUnit receipt omits the selected values and exact source payloads, so it does not
establish that the two candidate payloads are equal. A repeated-candidate predicate
is `not_established` until the actual producer handoff is resolved and canonical
owner bytes are compared; an unavailable or mismatched handoff must remain typed
`not_established` and cannot be converted into a repeated-candidate claim from the
reason marker alone. The existing canonical source owner is
`GenerationSourceRepository.load(ref, run_id)`: it verifies CAS integrity, exact
handoff bytes, and run binding, then validates the full `GenerationSourceHandoff`.
That handoff's source-binding validator recomputes each candidate from the persisted
producer inputs with `_shadow_candidate_from_grounding` and compares the full typed
candidate projection; `identities()` enumerates the actual `(problem, candidate,
atom.content_hash)` denominator. The R11 comparison must load both owner handoffs,
select through `identities()`, and compare canonical bytes of the recomputed owner
candidate projections. `GenerationSourceRepository.resolve(...)` may help locate a
matching summary, but its `GenerationSourceResolution` projection or summary hash
alone is not the owner-byte equality oracle
(`src/polisyos/runtime/quality/generation_source.py@9bd65c03be46082edb9d0af4749776085ef5569a`).

A complete AST census walked 2,693 tracked `src/**/*.py` files with zero parse
errors and recorded 8 direct `LoopVOIDecision` name references, 20 typed direct
field reads, and zero `ImportFrom` sites
(`/Users/deniskopylov/.codex/scratch/e02-r2-baselines/r11-loopvoi-ast-census.json@sha256:2452aabf5a991a3caf66dad7f2d5393a101a96992bb53e13b9c58adbe3091db3`).
It found no direct `LoopVOIDecision` consumer outside
`src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`.
Within
that owner, the N6 loop stops further cycles when `next_action != advance`, and the
refinement/search projections map `blocked` to `block_candidate` / `blocked_no_retry`.
But after the loop, `GenerationCycleController.run` unconditionally calls
`_promote_completed_generation`; that call does not receive or check blocked-run
status. `validate_generation_cycle_run` rejects extra cycles after `stop`/`escalate`,
but does not enforce that `blocked` is final or consistent with `terminal_status` and
`blocked_reason`. The recursive route consumes the run-derived terminal projection,
not `LoopVOIDecision` directly; `generation_cycle_terminal_state` maps a blocked run
to `RECURSIVE_BLOCKED`. The S8 `_generation_disposition` path validates the N6 run
and reads its fronts, but has no blocked-run predicate before it may call the
recommendation owner. A direct board consumer is absent from this tracked-source
census. The census disproves a broad direct-consumer claim; it does not prove that
state-level consumers enforce the block.

**Proposed choice; principal status.** Recommend option 1, subject to Denis's
principal ruling. Keep `blocked` distinct; do not map every blocked state to `stop`
or `escalate`. A repeated-candidate reason is admitted only when the producer's exact
canonical candidate bytes independently resolve equal. If those bytes or their owner
handoff are unavailable, preserve `candidate_identity_not_established` as a typed
limitation and withhold N9 authority rather than accepting a caller hash or reason
string. Resolve each complete source set with `GenerationSourceRepository.load`, use
`GenerationSourceHandoff.identities()` to select the exact candidate, and require
the handoff's candidate-recomputation validator plus canonical candidate-byte
comparison across both cycles. A summary-only `resolve(...)` result cannot establish
equality. Require the run validator to recompute that any blocked action is the final
cycle, has `blocked_no_retry` and `block_candidate`, and agrees with the enclosing
`terminal_status=blocked` and `blocked_reason`. Require the production N6→N9 path to
refuse a blocked or identity-not-established run before pre-N9 subjects, admissions,
or receipts are produced. S8 must also retain the blocked disposition with no ranked
recommendation. The current test expectation should change only with this behavioral
witness; this draft does not claim the witness has run.

**P37 — gate predicates at admission.**

- The source census denominator is the complete tracked `src/**/*.py` set: 2,693
  files, zero parse errors. Its no-direct-consumer result is `recomputed` for that
  syntax/tree denominator; external, dynamic, and generated consumers remain
  `not_established`.
- The current repeated-candidate gate compares the two stored hash strings
  (`consumer_asserted`). `_candidate_content_hash` may accept a caller object's
  `sha256:` claim or fall back to hashing only its candidate ID; equality of
  canonical owner bytes is `not_established` until both full source handoffs load
  and candidate projections recompute from producer inputs. The handoff validator
  and `identities()` live in `generation_source.py`; compare canonical bytes of the
  recomputed candidate projections, not just the `GenerationSourceResolution`
  returned by summary-based `resolve(...)`. The repeated-candidate predicate becomes
  `independently_reconciled` only after that byte comparison; otherwise its outcome
  remains typed `not_established`.
- Blocked-final consistency must be recomputed from every cycle, its typed decision,
  `blocked_no_retry` state, and the enclosing status/reason; a run-level
  `terminal_status` string alone is `consumer_asserted`.
- N9 eligibility must be independently reconciled against the validated run and
  refuse any blocked terminal before authority-bearing work. A missing or stale
  guard is `not_established` and cannot produce an N9-positive result.

**P38 — property and divergence.** Property: only producer-resolved equality of
canonical candidate bytes may count as a repeated candidate; an unavailable identity
is `not_established`, and a blocked run cannot reach N9/S8 current authority even
when the advisory scheduler says `advance`. Current implementation: the N6 loop
compares stored hash strings, `_candidate_content_hash` can trust the candidate's
claimed `sha256:` or ID fallback, and the loop then unconditionally calls
`_promote_completed_generation`; the validator lacks blocked-final/terminal
consistency. The existing owner boundary at `GenerationSourceRepository.load` can
verify the source artifact and recompute candidate projections, but the loop does
not use those records for equality; `resolve(...)`'s summary projection alone would
not close this gap. Divergent cases: different owner bytes carry the same claimed
hash, or the last action is `blocked` while N9 runs. The recursive route derives a
terminal state from the run; it is not a direct `LoopVOIDecision` consumer. S8
revalidates the run but does not yet enforce blocked-run refusal. Both state-level
paths need behavioral witnesses before they can be credited with preserving the
block.

**Remainder.** This decision covers the repeated-candidate cap and its boundary to
N9/S8, not a universal mapping for all `blocked` outcomes. The board has no direct
`LoopVOIDecision` consumer in the measured source set; any indirect board path is
`not_established` until named and witnessed. The recursive router consumes the
run-derived terminal state, while S8 consumes the validated run/fronts and signed
authorization path; neither is a direct action consumer. Their safe handling is not
established by the N6 loop break or AST census. No general claim that every consumer
handles `blocked` is made here.

**Remainder standing and signatory.** Denis is the pending principal signatory for
the action vocabulary. `runtime/quality` owns the typed loop decision and final N9
boundary. The direct board consumer is absent from the census, and no owner is
appointed for any external or dynamic consumer; those paths remain
`unallocated/not_established`. This proposal does not appoint an external actor or
create authority through the action label.

**Falsifier / revisit trigger.** Reopen if two owner-resolved handoffs with equal
canonical candidate bytes fail to produce a final `blocked` action, or if a blocked
action permits another cycle, lacks `blocked_no_retry`/`block_candidate`, disagrees
with the enclosing blocked terminal, reaches N9, or emits an S8 ranked/current
recommendation. The decisive negative probe supplies an otherwise N9-eligible
blocked run with valid positive N9 evidence; it must produce no N9 subject, admitted
batch, promotion receipt, or public recommendation. The marker-preserving removal
probe keeps `fake_cycle_same_candidate_repeated` and a caller-supplied identical
`sha256:` claim but changes one handoff's canonical owner bytes; equality must no
longer be established, so the reason marker cannot create the repeated-candidate
block. If either owner handoff is unavailable, the outcome must instead be typed
`candidate_identity_not_established` with N9 withheld. A positive distinct-byte
control resolves both handoffs, keeps the repeated-reason marker, supplies otherwise
valid N9 evidence, and must not classify the candidates as repeated; ordinary
`stop`/`escalate` controls must retain their existing terminal projections. These
are acceptance criteria; none is claimed as run here.

**Where it binds.** Loop and post-loop N9 owner at
`src/polisyos/runtime/quality/generation_cycle.py::GenerationCycleController.run`
and `::_promote_completed_generation`; run checks at
`src/polisyos/runtime/quality/generation_cycle.py::validate_generation_cycle_run`;
refinement/search projections in that module; canonical candidate identity and
producer-byte revalidation at `GenerationSourceRepository.load`,
`GenerationSourceHandoff.identities`, and
`GenerationSourceHandoff._validate_source_bindings` (which recomputes candidates
from producer inputs) in
`src/polisyos/runtime/quality/generation_source.py@9bd65c03be46082edb9d0af4749776085ef5569a`;
recursive terminal projection in
`src/polisyos/runtime/quality/recursive_generation_cycle.py`; and normative public
projection in
`src/polisyos/runtime/quality/design_axes/value_choice_provenance.py::_generation_disposition`.
No direct board consumer is named by this proposal.

**Pattern pass.** P04/P05/P29/P37/P38/P41. The observed divergence is an N6 break
followed by an unconditional N9 call and a validator that does not enforce blocked
terminal consistency. Target: recomputed final-block consistency and one N9 guard
before authority work. The existing fixture records the block but not the N9
non-promotion witness; the closure state is `verification_missing` until equal-byte
owner-handoff, marker-removal, distinct-byte candidate-preserving, blocked-run,
N9/S8 non-promotion, and preserved-terminal controls pass.

## R11 addendum — universal v3 blocked-run N9 exclusion (principal ruling, 2026-09-26)

This addendum records Denis's binding ruling for R11. It supersedes earlier R11
statements that the principal decision was pending or that N9 exclusion covered
only repeated-candidate causes. It does not claim code has been integrated and does
not close the finding.

**Decision.** For every current `policyos.runtime.generation_cycle_controller.v3`
run with `terminal_status="blocked"`, do not enter the N9 promotion owner,
regardless of `blocked_reason`, scheduler action, or source of the block. Preserve
the VOI decision's action and reason; a run-level guard may independently set the
run terminal to blocked. Emit the existing typed
`PromotionPortObservation(status="not_promoted")` with no certified IDs, N9
receipts, or pre-N9 observation payloads. This rule applies to v3; it does not
rewrite v1/v2 historical meanings or bytes. Candidate-band computation and its
typed limitations remain available; the rule withholds N9 authority for a blocked
run.

**Options and costs.**

1. **Selected: status-based N9 exclusion for every blocked v3 run.** Test the
   exact status named in the principal ruling, skip the N9 owner, and record the
   existing `not_promoted` observation. This is a broad authority refusal by
   design. An otherwise N9-eligible candidate is also withheld when its enclosing
   v3 run is blocked; Denis accepted that cost. The mechanism must remain on the
   single N6→N9 path and have a run-validator invariant and behavioral controls.
2. Cause-scoped exclusion. Refuse only named, independently reconciled block
   causes. This preserves more N9 opportunities but creates a second
   cause-to-authority policy whose omissions or proxy reason checks could admit a
   blocked run. Rejected by the ruling.
3. Let N9 decide independently. This retains the most review opportunities but
   violates the binding rule and preserves the unconditional owner call. Rejected
   by the ruling.

**Premises and complete block-cause census.** The principal ruling establishes
policy; source inspection establishes the current divergence. At commit
`5eca56ab0b9dc07ae094cc99f4a55045d1a53988`,
`src/polisyos/runtime/quality/generation_cycle.py` has SHA-256
`2442d86b228a1542b4fdbf6557f11e4a8eb417be8017afb7a5f5584c3467beb1`.
The census parsed 2,695 tracked runtime Python files with zero syntax errors and
found one production `GenerationCycleRun` constructor. It found three current
assignments of `terminal_status="blocked"`:

- max-cycle safety cap: `voi_safety_cap_reached_without_scheduler_stop`;
- fake-cycle/progress guard: `fake_cycle_same_candidate_repeated`,
  `cycle_two_not_counterexample_driven`, or `no_retry_without_new_grammar`;
- no-retry grammar guard: `new_grammar_elements_not_introduced`,
  `new_grammar_owner_missing`, `new_grammar_element_not_owned`, or
  `no_retry_without_new_grammar`.

R11 also maps a final `LoopVOIDecision(next_action="blocked")` to a blocked v3
run while retaining the action and reason. The production `decide_next_action`
constructor currently assigns `unsupported_terminal` for an unsupported prior
terminal. `_revise_node` constructs a `next_action="blocked", reason="pending"`
placeholder that is overwritten before run construction; it is not a run-level
cause. Thus the census plus the required R11 mapping covers the current three
run-guard classes and the direct VOI-block class. Reason text remains diagnostic;
the N9 refusal does not branch on a cause allow-list. Any future blocked run cause
is withheld by the same status predicate.

Instrument:
`/Users/deniskopylov/.codex/scratch/e02-r11b-action-terminal-20260926/r11b_block_cause_census_5eca.py@0d48cb2cd8b490ee23db4b4996be7827863fc7db706736c4c8b16f6aa296af32`.
Output:
`/Users/deniskopylov/.codex/scratch/e02-r11b-action-terminal-20260926/R11B_BLOCK_CAUSE_CENSUS_5ECA.json@be88ba4056cd8fca03a1b97d5d7f7c0e17353b075073728aca7ef91f7cbfdda6`.

The historical census walked 2,883 tracked JSON/JSONL files plus pinned v1 object
`adab90797d1d1562ae252c076883bc5af6d77ce`: 11 persisted N6 runs (10 v1, one v2),
all completed, zero blocked; no v3 run was in this denominator. Non-JSON,
runtime-only, and external persisted records remain unresolved by construction.
The v1/v2 serializer and historical validation must stay unchanged. Receipt:
`/Users/deniskopylov/.codex/scratch/e02-r11b-action-terminal-20260926/R11B_BLOCKED_HISTORY_CENSUS_5ECA.json@47640e422af25a31d4bf1a522fbe9ce07a9c0da2d19fcad5877b909cb7c335c2`.

**Complete consumer census.** The instrument parsed 2,695 runtime Python and 445
tool Python files and scanned 1,231 tracked TS/TSX/JS/JSX files in `apps` and
`packages`: zero Python parse errors; eight direct `LoopVOIDecision` identifier
references, all in `generation_cycle.py`; twelve typed runtime/tool contract
reference sites; zero exact frontend tokens from the declared token set. The
runtime consumers are:

- `runtime/quality/generation_cycle.py`: N6 action/run construction, validation,
  post-loop N9 owner call, and terminal projection;
- `runtime/quality/recursive_generation_cycle.py`: run validation and derived
  recursive terminal;
- `runtime/quality/acquisition_route_loop.py`: recursive/acquisition wrapper;
- `runtime/quality/public_export.py`: run validation/public export;
- `runtime/quality/design_axes/value_choice_provenance.py`: normative projection;
- `runtime/http/services/control/generation_cycle.py`: HTTP composition/reopen;
- `runtime/http/services/control/evaluation_safety.py`: evaluation-safety and
  promotion bridge;
- `runtime/http/services/control/run_lifecycle.py`: HTTP lifecycle/reopen.

The four other typed contract sites are validators:
`check_layer3_gy_composition_artifacts.py`,
`check_layer3_gy_depth_n_universality_contract.py`,
`check_layer3_gy_generation_cycle_contract.py`, and
`check_layer3_gy_second_domain_pack.py`. There is no direct board consumer in this
measured source set. Zero frontend exact-token hits do not establish absence of a
differently named, generated, reflective, or external board consumer; those remain
`not_established`. Downstream listed consumers read the run or its terminal
projection, not `LoopVOIDecision` directly.

Instrument:
`/Users/deniskopylov/.codex/scratch/e02-r11b-action-terminal-20260926/r11b_consumer_census_5eca.py@c5afb39022af2577b99535db692afda60489faa6a7e8625daea09a17c4a0b25b`.
Output:
`/Users/deniskopylov/.codex/scratch/e02-r11b-action-terminal-20260926/R11B_PRODUCTION_CONSUMER_CENSUS_5ECA.json@126275ec1ea00a246e7baa82c4be411573b6dad3c5c0b008feba7a1569a5badc`.

**Chosen mechanism and boundary.** In `GenerationCycleController.run`, map a
final VOI `next_action="blocked"` to `terminal_status="blocked"` and the existing
blocked-cycle projection without rewriting `scheduler_action` or the VOI reason.
At the post-loop boundary, before `_promote_completed_generation`, branch on the
exact current-v3 `terminal_status="blocked"` predicate; do not enter N9 and
return `PromotionPortObservation(status="not_promoted")` with reason
`generation_cycle_blocked_before_n9:<blocked_reason>`. The reason explains the
refusal; it is not the admission predicate. For v3, the run validator must
recompute action/run consistency and final-cycle blocked projection, and reject a
blocked run carrying certified-current status, certified IDs, N9 receipts, an N9
strangle receipt, or pre-N9 admission payload. Gate these new invariants to v3 so
v1/v2 serialization and history replay remain byte-exact. Preserve existing
run-derived recursive terminal mapping, including the safety-cap distinction.
Do not add a schema field, second N9 owner, scheduler threshold, or EIG/USD
conversion.

**P37/P38.** The N9 gate turns on the exact current-v3 run status
`terminal_status="blocked"`, which is the principal-selected property. Readers
must validate that status against the run's typed action/guard projections. The
gate must not turn on reason strings, repeated-candidate markers, action alone, or
presence/absence of a receipt field. The implementation divergence is the
unconditional post-loop N9 call and the direct blocked action that can leave its
run completed. A blocked-run marker paired with N9 certification must fail v3
validation, and removing the pre-N9 branch while keeping markers must make the
negative owner-boundary test fail.

Relevant patterns: P04, P05, P29, P31, P32, P37, P38, P40, P41. This decision
settles N9 scope, not whether the repeated-candidate premise is true.
`_fake_cycle_reason` compares stored candidate hash claims/ID fallback; canonical
equality of producer-owned bytes remains `not_established` until both persisted
source handoffs are resolved and their candidate projections compared. R11a
scheduler utility units remain unresolved; no unsupported threshold is added.

**Remainder and owners.** Runtime-quality owns run construction, terminal
validation, and the N9 boundary. `GenerationSourceRepository` owns candidate
source-byte resolution. HTTP/S8, public export, recursive routing, and any later
identified board projection must be checked against the typed blocked result. A
real served/public/board witness that no current authority leaks from blocked
runs remains missing. Denis's policy choice is settled; the architect owns any
register change. This addendum does not modify the debt register or claim closure.

**Falsifier and revisit trigger.** Remove only the v3 blocked-status branch before
N9 while retaining run status, reason, and markers. For each blocked producer
class, an N9-owner spy or otherwise N9-eligible fixture must show a call and the
negative test must fail. Forge certified-current status, receipt markers, or
pre-N9 admission payload into a blocked v3 run; validation must reject it.
Preserve a positive nonblocked control with a valid current candidate and
otherwise valid N9 evidence: it must reach the N9 owner and retain existing
certification behavior. Preserve exact v1/v2 replay for the pinned 11-record
corpus. Revisit if any blocked v3 run reaches N9, passes validation with N9
authority, the nonblocked control is refused, or historical v1/v2 bytes/meaning
change. Any new blocked cause is automatically subject to N9 withholding.
These are required acceptance witnesses, not results claimed by this draft.

**Where it binds.** `runtime/quality/generation_cycle.py` at
`GenerationCycleController.run`, the post-loop `_promote_completed_generation`
boundary, `_validate_generation_cycle_run`, `_blocked_cycle`, and
`generation_cycle_terminal_state`; all run-derived consumers listed in the census;
and semantic tests. The R2 schema version is v3. Test write set:
`tests/unit/runtime/quality/test_generation_cycle.py`, plus the smallest served
consumer witness required for projection behavior. Source integration waits for
R13's shared-file lease and independent review; this record is not a test receipt.

**Decision-maker and binding status.** Denis's ruling dated 2026-09-26 is binding
for current v3 runs. The option and accepted cost are recorded above. Principal
reconsideration is not a prerequisite for implementation; any policy change needs
a new explicit principal ruling.

### R11 implementation status addendum — 2026-09-26

The ruling's v3 status guard and validator invariants were subsequently committed
in `caad223d2096ed19c957c4ad6a7e838302736130`, superseding the earlier
"code not integrated" and "integration waits" statements as historical
pre-implementation status. The focused post-R13 candidate had **7/7 passing**
cases, including blocked VOI, retry/safety-cap blocks, and a nonblocked N9
control; removing the N9 guard while retaining the markers made two negative
cases fail. Receipts:
`/Users/deniskopylov/.codex/scratch/e02-r11b-action-terminal-20260926/R11B_POST_R13_GREEN_7.junit.xml@sha256:2ebd8a9ec168c1d6a20ade426478d67e3ef4d7c1c92fb1a663f9a3c516162bd3`
and
`/Users/deniskopylov/.codex/scratch/e02-r11b-action-terminal-20260926/R11B_POST_R13_N9_REMOVAL_RED.junit.xml@sha256:53e79f705cb0a5746c21f530028dddde7c18e804368b44f394a9c55bcd92eb19`.
The exact write set, controls, and remaining consumer limits are in
`/Users/deniskopylov/.codex/scratch/e02-r11b-action-terminal-20260926/R11B_POST_R13_HANDOFF.md@sha256:909d1241a0cf0ac047db8412579cf91658e3fff5da994a5df1d800b648cee77d`.
This is an implementation receipt for the bounded N6→N9 property, not evidence
of a served public/S8/board witness or complete four-base whole-file replay.


## R13 — one world-growth path and runtime store custody

**Question.** How must production N7 and acquisition re-entry be bounded so every
world-growth write uses the canonical admitted path and each artifact crosses the
same runtime-owned store at its producer and consumer? Is any production ACQ-01
producer established, or must the local route remain explicitly non-authoritative?

**Options and costs.**

1. Keep the local route as production authority. This is the least immediate
   rewiring, but a route-bearing receipt can be supplied through runtime hints or
   constructor injection even though the tracked `acq01_route` producer is a test
   fixture. The production N7 consumer currently has no scope fence; the route can
   mint a local WMR, select `grown_world_after_ref`, rebind an atom, and reach N5
   without overlay admission, passport, or native epoch. It also rebuilds stores
   from paths, so it bypasses tenant custody. This option preserves an unsafe
   second world-growth arm and is not recommended. The local route/runtime owner
   saves the strangle and store-plumbing effort; PolicyOS, tenant-bound consumers,
   and affected users bear the authority and custody risk.
2. **Bounded-strangle proposal:** put a structural production-scope refusal at the
   N7 gateway boundary for every default, runtime-hinted, and constructor-injected
   local owner, and a second refusal at re-entry for every route-bearing legacy
   receipt. The latter must run before reading `grown_world_after_ref`, rebuilding
   context, rebinding an atom, invoking N5, or emitting positive movement. Keep the
   local fixture only under explicit `contract_testing` scope, with a typed
   synthetic/non-authoritative result and no N9 or public authority. Preserve route
   planning and ordinary candidate computation when no acquisition gap is present.
   Keep served world growth on the existing WDI → Data Forge overlay → passport →
   native epoch → bridge path. If WDI has no exact bridge selection, either use the
   identity-checked runtime store for candidate evidence while returning a typed
   no-growth/deferred result, or refuse before live transport when that store cannot
   be supplied; never call the executor with a missing store and a root fallback.
   Costs are a controller/gateway/re-entry admission seam, explicit store plumbing
   through each producer/reader pair, historical receipt compatibility, and served
   negative/positive witnesses across the actual container composition. Runtime-
   quality and acquisition owners pay for the structural guards/store wiring;
   source and artifact owners pay for typed evidence integration; test owners pay
   for the served and historical-replay witnesses.
3. Build or identify an actual production ACQ-01 producer and route it through the
   canonical bridge. This could restore a served ACQ-01 path, but no tracked producer
   and complete request/authority/journal handshake are established. External or
   dynamic producer existence remains `not_established`; a caller or producer name
   alone is insufficient. It requires an appointed owner, typed request, covered
   authority/journal, overlay/passport/native-epoch admission, runtime-store custody,
   and a served end-to-end witness. Do not create a second writer while that caller
   and chain are absent. The appointed producer institution pays for its authorized
   act and evidence lifecycle; Data Forge/runtime owners pay for bridge and
   admission integration; test owners pay for the end-to-end witness.


**Premises.** B12 requires the real chain from typed requirement through authorized
job, owner acceptance, re-entry, and recomputation; a plan or unaccepted response
is not world growth (`source/B_r19_original.md`, B12; bundle `ACQ-01.md`). LA-046 is
an explicit handoff into ACQ-01, not permission for another compiler or data owner
(`source/LA_r09_original.md`, LA-046; bundle `ACQ-01.md`). The North Star describes
VOI-driven demand paging into the growing causal world model. GY Rev 16 / N13b
requires the single Data Forge overlay, passport, and native-epoch admission path.
Storage custody requires the store supplied by the runtime; root reconstruction
loses the tenant guard.

The source census at candidate base `73c656744` enumerated 2,693 `src/polisyos`
Python files, 2,722 test Python files, and 445 tool Python files; it found 21
tracked source hits and 14 test hits for `acq01_route`, with the only tracked route
producer in a test fixture. This establishes `producer_missing` only for tracked
literal producers in that denominator. It does not establish absence of an external
or dynamically injected producer. More importantly, the production consumer is
reachable regardless of that producer census: `RecursiveGenerationCycleController`
constructs the production controller with the container `PromotionRuntime`,
`GenerationCycleController.run` invokes the N7 route, and `_n7_owner_gateway`
accepts `problem.runtime_hints["n7_owner_gateway"]`, then a constructor-injected
gateway, then the default gateway. A well-formed route receipt can therefore reach
the production consumer through a dynamic seam. The default `authority_scope` is
`production`; the current branch has no structural guard before local gateway use.
The receiver, not producer absence or `synthetic`/route/hash markers, must enforce
the boundary.

The served WDI path already composes the existing canonical owner. With an exact
configured tenant/cell/run/route selection, the container supplies
`control_service._artifact_store` to `AcquisitionWorldGrowthBridge` and the live
executor; the bridge uses the same store for native admission history and
world-growth/re-entry receipts, and `PromotionRuntime.store` is identity-checked
against the control runtime store. The overlay, passport, and native epoch are
resolved before a positive delta or re-entry is accepted. This is the production
world-growth path to preserve.

There is a reachable WDI custody gap in the no-bridge/no-exact-selection branch.
The port still invokes governed live acquisition but omits `artifact_store`; the
executor then calls `build_artifact_store(ArtifactStoreConfig(...root=cas_root))`
using the local path. Empty world-growth routes are an ordinary configuration
state. A no-growth verdict does not repair custody of the response or snapshot.
That branch must receive the exact identity-checked runtime store and remain typed
no-growth/deferred, or refuse before live transport if the store is unavailable;
it must never enter a root-based fallback.

The full source AST census found 26 direct `FileSystemCAS(...)` sites among the
2,693 production Python files, five of which are the E02 root-rebuild additions in
the R13 write set. This is not a count of every relevant store handoff: the WDI
`build_artifact_store(root=...)` fallback is another reachable root-based instance,
and the R13 brief groups several conceptual paths under five constructors. Re-derive
and enumerate each producer/reader pair before code rather than carrying a
site-count proxy. The five E02 additions to resolve are N5 simulation-result
persist/load, composed-WMR/NCM write/read, local N7 route capture, captured Fabric
fetch persistence/read, and the Foundry training adapter. The N7 default gateway's
`.n7-live-cas` retrieval producer must also be traced through its store handoff.
The pre-existing `fabric/retrieval/executor.py` constructor is reached from the NL
mixin's persistence branch in source, but no direct caller of the NL mixin entrypoint
is found; its served operational reachability is `not_established`, not proven local
or retired.

Store identity is a producer/consumer property, not root equality. The production
recursive owner already has the identity-checked `PromotionRuntime.store`, but does
not pass it into `GenerationCycleController`; N5 `persist_joint_simulation_result`
and `load_joint_simulation_result` independently rebuild from `repo_root`. The
composed-WMR producer (`intervention_substrate._production_composed_world_model_record`
and the data-state builder) and NCM reader independently reopen
`.tmp/gy-s-composed-wmr-cas`; replacing only the reader would orphan the writer's
refs. Inject one appropriate owner store into both sides and bind any cache to that
store/tenant identity. Do not inject the WDI bridge store into this separate WMR
chain unless those refs are in that store. The local N7 gateway, retrieval/capture
writer, captured-fetch reader, and route-context builder also need the same exact
supplied store for any allowed contract-testing path. A second store object at the
same root is not equivalent custody. The training adapter is a plugin/CLI local
output path with no served tenant-bound caller established; use its configured
store factory and explicitly local scope, or identify and inject its actual owner.

The canonical WDI re-entry also conflates stable subject and active basis. The root
`compiled.design_problem_ref` remains the stable subject, while a nonzero source
cycle may have a revised `design_problem_basis_ref`. The bridge supplies the root
problem, and current re-entry compares that ref with the source cycle's active
basis and the next cycle basis. For cycle zero the active problem is the root; for a
later cycle it is the immediately preceding cycle's `revision_request.revised_problem`,
not the source cycle's own next revision. Resolve that active problem from the same
run history, verify it equals the source-cycle basis, preserve the root subject, and
carry both identities through re-entry and movement. The movement consumer checks
subject/cycle but not both basis identities, so a moved atom alone is not a witness.

A further same-class ACQ-01 receipt-binding gap is present on the canonical WDI
path. `AcquisitionOverlayReentryReceipt` binds its own bytes, but the issuer omits
the source cycle's `selected_candidate_content_hash`; bridge and movement consumers
compare the candidate ref but not its content hash against their re-resolved route
closure. `_candidate_content_hash` can fall back to a digest of candidate ID, and a
missing candidate binding returns early from record validation. A SHA-shaped string
or self-hash is not independent content evidence. Recompute the candidate digest
from canonical candidate bytes or resolve/hash its artifact; bind the source-cycle
candidate ref and content hash into new v3 receipts; preserve v1/v2 projections and
history exactly; and make both bridge and movement consumers compare ref plus hash
to their own resolved closure. If candidate bytes cannot be resolved, preserve
candidate computation with typed unknown but do not admit authority-grade re-entry.

The Appendix R12 `n7_reentry_candidate_atom_not_canonical` symptom belongs to
the same local legacy N7 arm: its prior-atom type/identity assumption is not a reason
to patch the canonical WDI re-entry. The served active-overlay WDI owner creates a
new cycle and does not consume/rebind that prior atom. The local route's atom issue
is removed by the production strangle; its explicit contract-testing fixture keeps
its own typed limitation and exact fixture store. No atom-rebinding behavior is
claimed fixed by this decision draft.

The current acquisition contract validator also has a proxy-gate divergence. It
counts `SubstrateRegistration`/registry-builder symbol calls across the whole
`generation_cycle.py` and probes a temporary root; the persisted expected-entry
reconstruction in `_validate_n7_acq01_registry_binding` is counted as a bootstrap
producer even though it verifies an owner entry. Narrow that validator to the
bootstrap-registration subproperty with role-aware analysis, and prove the actual
production N7 strangle through a real controller witness. Removing the local N7
route must not delete the deterministic persisted-entry verification.

**Correction from the subsequent read-only Cycle Board audit.** The 1,000-event
boundary is an explicit typed refusal, not silent loss: `AcquisitionMovementService.project_row`
returns `status="invalid_source"` with reason `movement_event_window_incomplete`
when the bounded page is full, before searching for a row receipt
(`policy-engine/src/polisyos/runtime/quality/acquisition_movement.py@d82db7baa318ad8003c2fe03b26e41afd7997eca`);
the Cycle Board carries that typed result as `movement_status`
(`policy-engine/src/polisyos/runtime/http/services/cycle_board_projection.py@440d9a1e0cd5acf1c52757ed13a8908371185e8c`).
This supersedes the earlier characterization of that Cycle Board boundary as a P38
divergence; no Cycle Board DS15 item is proposed on this evidence. The separate,
adjacent question is pending: `AcquisitionRouteLoop._resolve_terminal_event` calls
`list_events(run_id=..., job_id=...)` without a limit
(`policy-engine/src/polisyos/runtime/quality/acquisition_route_loop.py@8d2aecd29b71bfc43af45d4d8ff89f2683916d1a`),
and that reader defaults to 500 (`policy-engine/src/polisyos/runtime/quality/event_log.py@8eb1c070a157b82c7d98e38d0f803ae4096f73d0`).
Whether that default can truncate required route history is not established; audit
that adjacent path and its consumers before naming any finding or DS15 item. The
Cycle Board behavior is source-audited only; the behavioral witness, production
reachability census, and four-base attribution remain `UNRUN`.


**Proposed choice; principal status.** The bounded-strangle option is the
assignment's lean and has independent-review `GO` as the principal proposal, but
implementation readiness remains `NO-GO` until the corrections and closure gates
below are addressed. Denis's principal ruling is pending; this text is not that
ruling and claims no code or witness has landed.

At the production N7 admission boundary, refuse local acquisition through every
default, runtime-hinted, and constructor-injected gateway. Independently, any
production route-bearing legacy receipt must be quarantined before the controller
selects `grown_world_after_ref`, rebuilds local context, rebinds an atom, calls N5,
or emits positive growth/movement. Do not trust producer absence, a `synthetic`
marker, route schema/version, owner artifact hash, or other payload declaration as
the refusal predicate. Keep fixture N7 only under an explicit `contract_testing`
scope; its result must be typed synthetic and non-authoritative, and cannot establish
N9/public authority. Ordinary candidate computation without an acquisition gap stays
available. A production no-gap control must still pass.

Preserve the existing selected WDI bridge as the one production world-growth owner.
When its exact route is selected, prove that the same identity-checked runtime store
object and tenant-bound write options flow through container → live executor →
bridge/WMR evidence → admission and receipt persistence → re-entry read → N5
persist/load. For the no-bridge or no-exact-selection branch, do not execute live
transport with `artifact_store=None` and a raw `cas_root` fallback: pass the exact
runtime-owned store and return a typed no-growth/deferred state, or refuse before
transport if that owner store cannot be supplied. Only the canonical bridge can
turn its admitted passport/native-epoch evidence into world growth.

Route all production N7 capture writes and reads through the exact store supplied
by the recursive owner (`PromotionRuntime.store`, with its existing identity check)
threaded through controller, gateway—including injected seams—and retrieval/capture
helpers. N5 result persistence and loading must share that same production owner
store. For composed-WMR/NCM, pass one appropriate runtime-supplied store to the WMR
writer, data-state builder, and NCM reader, preserving tenant options and binding
root-only caches to exact store/tenant identity; do not switch only the reader or
assume the WDI bridge's store owns those refs. Keep any contract-testing local route
on one injected fixture-store object. Use the configured store factory for the
training adapter's explicit local output lane unless a served owner is identified.
Resolve the legacy NL retrieval executor's caller census before classifying it as
local-only or retired; if served, thread the guarded runtime store, and if closed,
record the owner/caller evidence.

For valid WDI re-entry, use root problem bytes as active basis at cycle zero; for a
later source cycle, resolve the preceding cycle's `revision_request.revised_problem`
from the same persisted run and require its ref to equal that source cycle's basis.
Keep `original_run.design_problem_ref` as the stable subject and issue the next
cycle with that subject plus the verified active basis. Movement must verify both
subject and source/new basis. For acquisition re-entry lineage, independently
recompute the source candidate content digest; issue a new v3 receipt carrying its
candidate ref/hash and make both bridge and movement consumers reconcile those
values to their independently loaded route closure. Preserve v1/v2 validation,
serialization, and content hashes byte-exactly; never synthesize hashes or restamp
historical receipts. Treat the bootstrap contract validator as a separate,
role-aware registration check; the production controller witness proves the
strangle. These are proposed owner-level mechanisms; their complete caller census,
implementation, and witnesses are pending.


**P37 — gate predicates at admission.**

- At this head the production N7 scope guard is `not_established`. A future gate
  must derive production-vs-contract-testing scope from the structural controller
  owner context (`independently_reconciled`); a producer census, runtime hint,
  constructor choice, `synthetic` field, route marker, or owner hash alone is
  `consumer_asserted` and cannot open production re-entry.
- A production route-bearing ACQ-01 receipt is refused before the
  `grown_world_after_ref` fallback, context rebuild, atom binding, and N5. A `None`
  rebuild result is not a refusal signal.
- Canonical WDI admission is `independently_reconciled` only after exact route and
  authority resolution, journal-covered request, Data Forge overlay admission,
  passport, native epoch, activation, positive membership delta, and same-case
  receipt. Current no-bridge/no-selection live-executor behavior is `not_established`
  for custody: the proposal requires typed no-growth/deferred with the exact runtime
  store, or refusal before live transport; a root-rebuilt fallback cannot satisfy it.
- Store custody is `not_established` at the proposed N7/N5/WMR handoffs until a
  served witness verifies object identity and tenant-bound options across each
  producer/reader chain. Equal root paths, `cas_root`, or a manifest tenant string
  alone are `consumer_asserted`.
- `design_problem_ref` is the stable subject; active basis is recomputed from the
  root problem for cycle zero or the preceding cycle's revised problem thereafter,
  then matched against `design_problem_basis_ref`. Movement must verify both.
- Candidate content identity must be `recomputed` from canonical candidate bytes
  or a resolved content-addressed artifact; current ID-derived/self-declared fallback
  is insufficient (`not_established` for authority-grade re-entry). Both bridge and
  movement must independently compare the receipt's v3 ref/hash with their own
  route closure.
- The bootstrap validator's counted producer calls are `recomputed` only when
  classified by enclosing role. Its current global symbol count does not establish
  the served N7 boundary. Training output is local-only unless a served owner is
  identified; legacy NL retrieval reachability is `not_established`.


**P38 — property and divergence.** Property: every production world-growth write
uses the canonical authorized Data Forge bridge and the runtime's tenant-bound
store, while production N7 cannot consume a route-bearing legacy receipt outside
that bridge. Current implementation: the tracked route producer is a fixture, but
the production controller is reachable through runtime-hinted/injected gateways
and has no scope fence. If local context reconstruction returns `None`, re-entry
still selects `grown_world_after_ref`, rebinds the atom, and invokes N5. In served
WDI execution, no bridge or no exact selection omits `artifact_store` while the
executor rebuilds a store from `cas_root`. These are divergent cases even when no
tracked production producer exists.

The store property also diverges at each producer/reader pair: production
`GenerationCycleController` drops the identity-checked PromotionRuntime store,
N5 persist/load rebuild from paths, WMR writer and NCM reader independently reopen a
root, and local capture writer/reader can use distinct store instances. The exact
same object and tenant options—not equality of root strings—are required. The
bootstrap validator measures global builder-symbol presence plus a temporary-root
probe; it falsely counts the persisted registry-entry verifier as a producer and
can miss a production gateway path that bypasses the counted calls. Keep it for the
narrow registration property, with role-aware census, and use a real production
controller witness for the strangle.

For identity, the implementation treats stable subject and active basis as equal
at re-entry although a revised cycle can retain the subject and change its basis;
the movement consumer currently checks the subject/cycle but not both bases. For
receipt lineage, the v1/v2 re-entry receipt omits source-candidate content hash and
both the bridge and movement readers compare only candidate ref; an ID-derived
fallback hash and self-hash do not prove the candidate bytes selected by the route
closure. A valid same-ID/different-bytes receipt can therefore diverge from the
source candidate unless source bytes are recomputed and both consumers bind the
qualified evidence. Those are the same R13 custody/route-binding class one level
deeper under P40, not reasons for per-call patches. All distinguishing cases and
removal probes remain `UNRUN`.


**Remainder.** This does not make PolicyOS the owner of external licenses, data
collection, or institutional authority. Those remain typed inputs owned by their
source institutions/Data Forge; PolicyOS owns its admission, receipt, re-entry, and
the truth of its world-growth claim. An absent external or dynamic producer is
`not_established`, not a warrant to accept the local route. The canonical WDI bridge
is the only proposed production growth path; its no-selection fetch/store behavior,
N7 local gateway and receipt fences, N5 and composed-WMR store identity, candidate
content binding, stable-subject/active-basis semantics, and bootstrap-gate correction
have not been behaviorally verified. All R13 probes remain `UNRUN`; no closure is
claimed. Root-based stores and authority fallback listed above remain residuals
until every affected producer and reader uses its exact owner store or is refused.

The earlier Cycle Board candidate is withdrawn: its full-page condition produces
the typed `invalid_source` / `movement_event_window_incomplete` result, as shown by
`policy-engine/src/polisyos/runtime/quality/acquisition_movement.py@d82db7baa318ad8003c2fe03b26e41afd7997eca`,
which the Cycle Board retains as `movement_status`
(`policy-engine/src/polisyos/runtime/http/services/cycle_board_projection.py@440d9a1e0cd5acf1c52757ed13a8908371185e8c`).
No Cycle Board DS15 residual is proposed. The adjacent `AcquisitionRouteLoop`
terminal-event lookup uses the event-log reader's implicit default of 500
(`policy-engine/src/polisyos/runtime/quality/acquisition_route_loop.py@8d2aecd29b71bfc43af45d4d8ff89f2683916d1a`;
`policy-engine/src/polisyos/runtime/quality/event_log.py@8eb1c070a157b82c7d98e38d0f803ae4096f73d0`).
Its completeness and consumer behavior remain an unaudited, `UNRUN` adjacent
question; establish whether that boundary is reachable and divergent before
classifying a finding or proposing a separate DS15 item. No P41 attribution is
claimed.

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
The semantic change introduced by keeping `design_problem_ref` stable while
advancing `design_problem_basis_ref` has not been measured against main's movement
and world-growth closure checks. Re-establish the four-base behavior for
`test_actual_wdi_admits_delta_and_reenters_same_case` (both parameter values),
`test_actual_acquisition_producers_preserve_tenant_custody_through_reentry`, and
`test_native_supplier_requires_separate_gy_act_then_projects_to_cycle_board`
(`tests/integration/core_runtime/test_acquisition_world_growth_chain.py@c101c5d2a2f25da0bce6cf6a265eff4a99a2bdc2`,
`tests/integration/core_runtime/test_acquisition_tenant_custody.py@3b8d25a171a6f8a6f30de50401027967f53656ed`,
`tests/unit/runtime/quality/test_acquisition_movement_positive.py@e2516e48fd58b3bfab2a271cb9423fc1405c1472`). Until then, the stable-subject/current-basis
split is `not_established` as preserving these closure semantics; no result in this
draft credits the refactor with that closure. The split and context equality are in
`src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`
and `src/polisyos/runtime/quality/cycle_substrate.py@f24fcc8ded61aa07c0c4145ea27f929995533f11`.

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

**Falsifier / revisit trigger.** Reopen if production can call any local N7 gateway
through the default, runtime-hinted, or constructor-injected seam; if a route-bearing
production receipt can affect `grown_world_after_ref`, local context, atom binding,
N5, or positive movement before typed refusal; if no-bridge WDI reaches live
transport without the exact runtime store; or if a raw-root fallback is reachable.

Required negative/removal probes (all `UNRUN`):

- Inject a valid fixture `n7_owner_gateway` through runtime hints and separately
  through the constructor seam, retain valid route/owner/hash markers, and remove
  the production guard. A real production controller must reveal forbidden gateway
  invocation/local write, so the test turns red. Ordinary no-gap candidate generation
  remains the preserving control.
- Present a valid production route-bearing receipt for which context rebuild returns
  `None`, with `grown_world_after_ref` different from the current WMR. Refusal must
  precede reading that ref, context rebuild, atom rebind, N5, and positive movement.
  Remove only that refusal while keeping receipt/hash markers valid; an observed WMR
  or N5 change makes the probe fail.
- Retain a supplied-store marker but substitute a distinct store object at the same
  root. Guarded N7 capture, N5 persistence/load, and composed-WMR writer/NCM reader
  must fail custody. The positive control verifies the exact same runtime-owned
  object and tenant options across each complete producer/reader chain.
- Force exact WDI bridge selection to `None` or omit the bridge. The port must either
  stop before live transport or use the identity-checked runtime store while returning
  typed no-growth/deferred; any `artifact_store=None` root rebuild turns the test red.
  The selected-route WDI positive remains the preserving served control, with foreign
  tenant/cell reads refused.
- Keep run/route/passport/epoch markers valid while changing only the basis under
  the same stable subject at a nonzero cycle. Resolve the active problem from the
  preceding cycle's revised problem; assert the old subject remains stable, the
  source/new cycle bases bind their problem bytes, re-entry/N5 uses the active basis,
  and movement binds both. Cross-bound subject or basis must refuse. Unchanged basis
  remains a one-cycle control.
- Recompute a source-cycle candidate digest from its actual canonical bytes (or
  content-addressed artifact), then alter the receipt hash to another valid digest
  and reissue the receipt self-hash while preserving markers. The bridge's
  `_validate_reentry` and `AcquisitionMovementService.consume_terminal` must each
  refuse against their independently resolved closure; if either consumer's
  ref/hash comparison is removed while markers remain, the corresponding negative
  test must fail. A positive served WDI path verifies
  the exact source ref/hash in a new v3 receipt through both consumers.
- Preserve the contract-testing local route only with explicit `authority_scope`,
  a typed synthetic/non-authoritative result, one exact fixture store, and no N9 or
  public authority. Keep the bootstrap-registration validator role-aware and pair it
  with the production-controller witness; deleting the deterministic persisted
  registry-entry verification must still make its own test fail.

Historical v1/v2 re-entry receipts must deserialize, validate under their own
historical rules, and reproduce exact old bytes/hashes; no synthetic source hash,
restamp, or promotion to v3 is allowed. A new v3 receipt is current admission, not a
historical replay. Preserve ordinary candidate computation and the exact selected
WDI growth path after Data Forge admission, passport, and native epoch. Complete the
specified tests only after P41 freeze and the shared-file lease; none of these
receipts, removal probes, controls, or related regression outcomes is claimed here.

For B27, retain the distinct falsifier: with a P0 `CycleSubstrateContext` still
present, a changed P1 basis must not pass N5/N7 through equality with old P0 owner
evidence. The positive witness is a served owner-issued P0→P1 transition that names
changed premises, revalidates and persists P1 context, admits it through N5/N7, and
keeps P0 history replayable. Until that transition producer exists, a later cycle
may remain limited/blocked; no synthetic rebind is authorized. This B27 obligation
is not discharged by the stable-subject/current-basis behavior above.


**Where it binds.** The structural production owner flow is
`runtime/http/container.py` → `runtime/quality/recursive_generation_cycle.py` →
`runtime/quality/generation_cycle.py::GenerationCycleController`; the source seams
are `recursive_generation_cycle.py@ddff9abd228378166bce8437862ebe487ae00149` and
`generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`. The N7 owner-gateway
injection, route-context builder, `grown_world_after_ref` fallback, atom binding,
and N5 entry all bind in `generation_cycle.py`; default/injected gateway plus local
capture production/read binds in
`runtime/quality/acquisition_planner.py@7e2e5a189da71145dbcbc347c04ee92e6be0aaa1`.
The production WDI owner and exact store/admission handoff bind in
`runtime/http/services/acquisition_surface_execution.py@74bfe81aa16b00561c7650032593bd2be722d67e`,
`runtime/quality/acquisition_executor.py@58b528e659121696e97da333f1b44a0c60e83d7f`,
and
`runtime/quality/acquisition_world_growth.py@e5caf4ccb42af91418472269bb052b8cf4db71fc`.
The no-bridge/no-selection live-executor fallback is part of this custody boundary.

N5 result-store injection binds at the recursive owner, `GenerationCycleController`,
`JointSimulationPort`, and both joint-result persist/load helpers in
`generation_cycle.py`. The composed-WMR writer and data-state builder bind at
`runtime/quality/intervention_substrate.py@e4c7c30f81438908688a169cb3d51fbd3f66be20`
and
`runtime/quality/data_state_substrate.py@c141184edc49e7b9c868dd7d40a91ec0dc32a483`; the
HTTP owner and NCM reader must pass/read one same store object, with the cache bound
to store/tenant identity. Do not switch the NCM reader to a store that does not
contain the writer's refs.

Stable subject/current-basis validation and N5 re-entry bind in
`generation_cycle.py`; movement's consumer must verify both identities in
`runtime/quality/acquisition_movement.py@d82db7baa318ad8003c2fe03b26e41afd7997eca`.
Source-candidate content hash recomputation and receipt v3/history projection bind
in the same `generation_cycle.py` owner; the two independent re-entry consumers are
`runtime/quality/acquisition_world_growth.py` and `acquisition_movement.py`. The
local route fixture binds in `tests/unit/remediation/test_acq_01.py`; B27 binds to
`CycleSubstrateContext.design_problem_ref` and context validation in
`runtime/quality/cycle_substrate.py@f24fcc8ded61aa07c0c4145ea27f929995533f11`, as well
as the two problem refs and recursive consumers in `generation_cycle.py`; the
currently mis-scoped N7 fixture tests and bootstrap validator bind in
`tests/unit/runtime/quality/test_generation_cycle.py`,
`tests/unit/runtime/quality/test_acquisition_planner.py`, and
`tools/quality/validation/check_layer3_gy_acquisition_contract.py`.

The complete root-store AST census and its R13 callers are in
`R13_ROUTE_MAP.md@sha256:2af8f00dcfa701d2715e7b4b33f264b161523b3fcd3fdc28955e5a6aa3c96ab5`.
The served acquisition seam and no-selection fallback are documented in
`/Users/deniskopylov/.codex/scratch/e02-r2-acquisition-flow-seam-audit-20260924.md@sha256:fa24d840cd4c6fb485230f435a3787b195c79ee979b0536e1e9eb03819b3ee9a`;
the independent readiness corrections are at
`/Users/deniskopylov/.codex/scratch/e02-r2-r13-independent-review-20260924.md@sha256:48f3ce612c25c9328b7b06164936470f9af8e268cecb4dabbee8a84ad95593a0`.
The expected P41 test denominator includes
`tests/unit/runtime/quality/test_generation_cycle.py`,
`tests/unit/runtime/quality/test_joint_simulation_horizon.py`,
`tests/unit/runtime/quality/test_intervention_substrate.py`,
`tests/integration/runtime_quality/test_data_state_substrate.py`,
`tests/unit/runtime/quality/test_acquisition_planner.py`,
`tests/integration/core_runtime/test_acquisition_authority_served.py`,
`tests/integration/core_runtime/test_acquisition_world_growth_chain.py`,
`tests/unit/runtime/quality/test_acquisition_movement_positive.py`,
`tests/integration/core_runtime/test_acquisition_tenant_custody.py`, and
`tests/unit/remediation/test_plg_03.py` if training behavior changes. If the NL
retrieval path is retained or proven production-reachable, also reserve
`tests/unit/fabric/test_retrieval_fetch_custody.py` and
`tests/unit/runtime/http/test_nl_pipeline_materialization.py`. Every test remains
pending the frozen P41 denominator; these are planned witnesses, not results.


**Pattern pass.** P01/P02/P05/P07/P08/P12/P27/P28/P31/P32/P35/P37/P38/P40/P41.
Existing defects are the dynamically reachable local N7 second writer, route-bearing
receipt fall-through, owner-store loss at producer/reader boundaries, subject/basis
conflation, candidate-ref-only receipt binding, and a bootstrap gate that counts a
verification helper as a producer. Target: one structurally guarded N7 production
chokepoint, the canonical WDI overlay/passport/native-epoch owner, exact runtime
store identity across each read/write chain, and independently verified subject,
basis, and candidate bytes. The explicit local contract fixture remains synthetic
and non-authoritative; ordinary candidate work remains available. Tracked ACQ-01
producer status is `producer_missing` only for the enumerated literal-source set;
external/dynamic producer existence is `not_established`. The same-class receipt
hash and store handoff escape is widened under P40, not repaired site by site.
Missing capability labels include `bridge_missing`/`verification_missing` for the
production admission, store, and receipt witnesses. Correction: the Cycle Board's
1,000-event boundary returns typed `invalid_source` with
`movement_event_window_incomplete`
(`policy-engine/src/polisyos/runtime/quality/acquisition_movement.py@d82db7baa318ad8003c2fe03b26e41afd7997eca`),
and carries it as row `movement_status`
(`policy-engine/src/polisyos/runtime/http/services/cycle_board_projection.py@440d9a1e0cd5acf1c52757ed13a8908371185e8c`),
so it is not asserted here as a DS15 gap. Separately, the adjacent
`AcquisitionRouteLoop` terminal-event lookup's implicit 500-event default remains
unaudited (`policy-engine/src/polisyos/runtime/quality/acquisition_route_loop.py@8d2aecd29b71bfc43af45d4d8ff89f2683916d1a`;
`policy-engine/src/polisyos/runtime/quality/event_log.py@8eb1c070a157b82c7d98e38d0f803ae4096f73d0`);
its behavior is `not_established` and its tests are `UNRUN`, with no DS15 item
proposed pending that audit. Closure requires all R13 negative probes and
preserving controls above, exact production-store identity through actual container
composition, byte-exact v1/v2 replay plus current v3 admission, and all touched-file
four-base results. This draft claims none of those tests has run.

### R13 addendum — exact source occurrence and active-overlay basis (2026-09-25)

**Question.** What evidence must bind a selected acquisition cycle to the exact
N4 source problem it used, and may re-entry claim a current post-admission world
when the canonical owner chain cannot produce that world?

**Options and costs.**

1. Keep using the compiled root and one-time context, or drop the basis equality.
   This avoids extending owners, but either rejects legitimate revised cycles or
   treats root/source bytes as the revised basis and risks a confidently wrong
   re-entry. Runtime-quality owners save receiver/context wiring; route consumers
   pay with over-refusal or stale-world risk.
2. Refuse every revised-cycle route until a production-qualified W1 provider is
   appointed. This withholds unsupported authority, but also prevents the lane
   from building and testing the already-authorized receiver and evidence
   handoff. Runtime and test owners avoid integration work for now; users of valid
   revised-cycle candidate/route behavior pay for the delay, while the separate
   issuer appointment remains unmade.
3. **Proposed lane choice, pending Denis:** extend the existing
   `GenerationSourceRepository` and canonical Data Forge → data-state/world-model
   owners. Resolve one typed source handoff for exact `(run_id, cycle_index)`;
   reconcile its full `DesignProblem` basis `B`, candidate/atom identity set, and
   predecessor revision; preserve stable route subject `S` separately. After the
   existing passport/overlay/epoch admission `E`, resolve W1 from that exact
   admitted overlay through the runtime-supplied guarded store, then provide the
   existing N4/N5/re-entry consumers a context bound to `(B, W1)`. Costs are the
   owner-chain extension, exact source and tenant custody checks, typed
   subject/basis evidence, historical-schema preservation if receipts change,
   and the four-base witness set. Preserve `GenerationSourceRepository.load`
   integrity/profile validation and cycle-agnostic payload identity; add exact
   occurrence as a separate predicate. This does not add a second world-growth
   path or reconstruct a store from a root. The GenerationSource/route owners pay
   for exact receiver lineage; Data Forge/data-state owners pay for W1 composition
   through the supplied store; runtime-quality and test owners pay for served
   evidence and compatibility witnesses.

**Premises.** For cycle 0, `B = S`; for later cycle `i`, `B` is the exact
`revision_request.revised_problem` from cycle `i-1`. The source witness must be
the unique N4 handoff for that same run and cycle, with its typed `problem` hash
equal to B and its complete candidate identities reconciled to that cycle. The
existing `source_identity_hash()` excludes cycle index, so it cannot prove the
occurrence by itself. Keep the three world references distinct: source W0,
admitted overlay/epoch E, and post-admission W1. The independent v2 review
confirmed the exact occurrence gap and that the canonical composer does not
materialize the selected active overlay into a runtime-store-custodied W1:
`/Users/deniskopylov/.codex/scratch/e02-r2-subject-basis-reentry-v2-independent-review-20260925.md@sha256:ec361a1378a6fcb7d5bf2cd6e2bc0d690ccbf1b63c8016673bd570e53fdb00f0`.

**Proposed choice; principal and engineering status.** Prefer option 3 as the
R13 design, pending Denis's ruling on the decision record. That pending principal
ruling does not require owner approval to perform already-authorized engineering
on the existing repository and canonical owners. The implementation must retain
R1/R5's bands: if a context is unknown, ordinary candidate work may carry a typed
limitation and produce proposal-only N4; N5/N8/N9, S8 authority grading and
publication cannot treat that as grounded. Protected modes refuse before N4
without current exact-B context and fresh exact-B EvalSafety admission. If the
canonical owner cannot resolve W1 after E, positive re-entry/movement is
`not_established` and stops. The fixture may prove consumer mechanics only.
Native positive production qualification remains `absent/unallocated` under
DS15; this proposal neither appoints its issuer nor claims DS15 closure.

**P37/P38.** The run, source occurrence, typed problem bytes, complete candidate
set, predecessor edge, and current W1 must be recomputed or independently
reconciled at admission; a cycle index field or outer self-hash alone is
`consumer_asserted`. Today a route can retain a basis marker without joining the
typed N4 source and predecessor, and the WMR composer lacks the selected overlay
and runtime store. The property is exact `(run, cycle, B, E, W1)` source-to-
re-entry custody; the implementation's root subject and one-time context are the
wrong operands when `S != B`. Removing equality would convert a false negative
into stale-world false admission.

**Remainder.** The smallest missing capability is a canonical provider that
resolves post-admission W1 from the exact admitted Data Forge overlay using the
runtime-supplied guarded store and issues a content-bound `CycleSubstrateContext`
for `(B, W1)` to existing N4/N5/re-entry owners. Source-level inspection
confirmed this provider is absent; this is an engineering capability to add,
not an unspecified owner-appointment blocker. The native production epoch
qualification/issuer remains separately unallocated. Do not mint W1 from the
legacy local FileTabular route, `.tmp/gy-s-composed-wmr-cas`, a root-rebuilt
store, or a stale W0. Any durable basis fields require additive schema versions
and byte-exact historical serializers; do not restamp history. Exact source
selection and active-overlay production evidence remain `bridge_missing`,
`producer_missing`/`not_established` until witnessed. No DS15 closure is claimed.

**Falsifier / revisit trigger.** Reopen if two handoffs with the same
cycle-agnostic source identity can satisfy the selected cycle, if a handoff's
problem differs from B or its predecessor revision while markers remain intact,
if the route loses tenant/guarded-store custody, or if any positive re-entry
labels W0 as W1 without resolving the admitted overlay E. The removal probe
preserves run/cycle/route markers and outer hashes while changing only exact
source occurrence or predecessor basis; route resolution must refuse. The
context probe runs a revised `S != B` route with a valid W1 provider, then removes
only per-basis/overlay refresh; stale S/W0 must fail the witness. The preserving
control resolves exact `(run, cycle, B)`, current E/W1 and same tenant through
the runtime store, then advances one cycle under B while keeping row identity S.
Retain the whole-file P41 witnesses
`tests/integration/core_runtime/test_acquisition_world_growth_chain.py::test_actual_wdi_admits_delta_and_reenters_same_case` (both parameter values),
`tests/integration/core_runtime/test_acquisition_tenant_custody.py::test_actual_acquisition_producers_preserve_tenant_custody_through_reentry`, and
`tests/unit/runtime/quality/test_acquisition_movement_positive.py::test_native_supplier_requires_separate_gy_act_then_projects_to_cycle_board`.
All these probes, controls, and tests remain `UNRUN` pending P41 replay; a fixture
control is not a production authority receipt.

**Where it binds.** Exact occurrence and typed handoff loading bind in
`runtime/quality/generation_source.py` through the same runtime-supplied
`ArtifactStore`; selection and predecessor reconciliation bind in
`runtime/quality/acquisition_route_loop.py`. Passport/overlay/epoch admission
remains in `runtime/quality/acquisition_world_growth.py`, with current W1
resolution extending the canonical data-state/world-model owners
(`runtime/quality/data_state_substrate.py` and
`runtime/quality/intervention_substrate.py`). Re-entry basis and any versioned
receipt bind in `runtime/quality/generation_cycle.py`; movement must keep S as
row identity and validate B/E/W1 separately in
`runtime/quality/acquisition_movement.py`. Candidate, protected, N9, S8 and
publication reader boundaries remain those stated in the R1/R5 per-basis
addendum above.

### R13 addendum — active WDI observation and prior binding census (2026-09-28)

**Question.** Can the existing served WDI route establish a post-admission world basis by matching identifiers alone, or must its active observations, canonical-variable-to-slot relation, and SKG prior be independently bound before the existing WMR/context owners can re-enter N5?

**Options and costs.**

1. **Admit and extend the existing owner chain.** The exact active-observation projection exists only as a candidate on unintegrated branch/commit `fba62c46dba85abfb3e94fb818bb26d6a56d7a0a`; it is absent from canonical base `db42655626da93c37abc896bdf127730bb0b5f96` and has no served caller. First review/admit that owner projection into the canonical Data Forge path and wire its exact receipt-bound result to a production served consumer through the existing `AcquisitionWorldGrowthBridge` and supplied store. Then have the existing snapshot/WMR owners bind admission, data/time/entity scope, canonical variable, resolved Foundry slot, and independently resolved SKG prior to one DataSnapshot basis, and pass WMR/context through the existing re-entry owner. The mapping and SKG provenance must be independently resolved, not derived from caller strings. This costs owner review/integration, a served consumer, the WMR/context bridge, and positive/removal/control witnesses, while preserving one world-growth path and existing storage custody.
2. Keep the served route positive only through admission and receipt recovery; report post-growth WMR/context as `not_established` and carry a typed limitation until those owners exist. This keeps ordinary candidate work available and avoids a false world claim, at the cost of delaying a positive post-growth N5 witness.
3. Add a WDI-specific second snapshot/WMR writer, or call `_production_skg_ref` with the new WDI snapshot ID and treat the copied field as proof. This may shorten the local path, but duplicates the world-growth owner and can make an unrelated latest academic SKG ref pass only because its caller copied the active snapshot ID. It conflicts with N13b's one admission path, P27, P37, and P38; do not select it.

**Premises.** The frozen read-only census at candidate `fba62c46dba85abfb3e94fb818bb26d6a56d7a0a` enumerated 7,743 tracked source/config files under `policy-engine` (suffix set and exclusions in the receipt), without reading `production_data`. It found `project_active_observations` only in that unintegrated candidate, at its read-only definition, with no production caller. A complete tracked-source grep at canonical base `db42655626da93c37abc896bdf127730bb0b5f96` finds no `project_active_observations` occurrence; canonical `overlay.py` is `@sha256:f53ae8091cb32080905245d835b4f97225e9f7de30528076d676615d27734745`. Thus the current production path has neither this exact-observation projection producer nor a served consumer. Data Forge's `MetricFieldBinding` owns `raw_field → canonical_variable`; `build_world_model_record` receives `policy_slot_ids` and resolves those IDs through Foundry's `SlotRegistry`, with no producer joining that canonical variable to a slot. The existing `generation_cycle.py` boundary helper synthesizes limited slot bindings from supplied IDs; it is not an active-WDI mapping.

`_production_skg_ref` selects the latest academic SKG snapshot/version, accepts a caller-supplied `snapshot_id`, and copies that value into `SkgCausalPriorRef.source_data_snapshot_id`. Its only production caller is the L4 data-state builder, not the active WDI overlay. `_assert_same_world_version` compares snapshot ID strings; it cannot establish that the chosen SKG ref was admitted for or reconciled to the active WDI basis. A typed `source_data_snapshot_id` is a claim unless its producer independently binds it.

Frozen receipt: `/Users/deniskopylov/.codex/scratch/e02-r13-blocker-census-20260928/R13_WDI_BINDING_BLOCKER.md@sha256:98e5313066c47455f0ac9e8ad972ca8124a9dd94af51da399d4970f44b2b96be`; census reproducer: `/Users/deniskopylov/.codex/scratch/e02-r13-blocker-census-20260928/census.py@sha256:c6a0e2e83d97ceeeb3d412e628fc5d2ef76ad289eee3f037491e587af28e0d09`.

**Proposed choice; principal status.** Propose option 1 as the engineering direction within R13's existing architectural constraints, with an explicit prerequisite: first admit the candidate projection into the canonical Data Forge owner and demonstrate a served production consumer. Only after that may the chain compose the exact admitted overlay, runtime-supplied guarded store, independently bound snapshot/slot relation/SKG prior, WMR, and context. Until those steps produce evidence, use option 2's typed limitation and do not claim a post-growth WMR/context or dependent N5 effect. This remains a proposal only, not a principal ruling or authorization; Denis's R13 principal decision remains pending. This addendum does not authorize a second writer, declare an independent SKG prior, or close B12.

**P37/P38 and P40.** The property is that the post-growth WMR and context correspond to the exact active WDI observation basis and its qualified causal prior. The current version gate turns on equality of `source_data_snapshot_id` and other snapshot ID strings; that predicate is `consumer_asserted` until an owner binds the prior and the active snapshot. Divergent case: copy the WDI snapshot ID onto a ref to the latest unrelated academic SKG snapshot; string equality can pass while the property is false. The active canonical-variable-to-slot relation is also `not_established`. This is the same R13 world-growth/owner-bypass class one level deeper, not a new class: both symptoms are the missing admitted-observation-to-WMR/context bridge. Under P40, do not patch `_production_skg_ref` or individual routes; widen the existing owner chain or keep this bounded residual.

**Remainder.** The exact-observation projection is not admitted on the canonical base, and there is no served consumer; the current WDI production composition proves at most its selected admission/receipt layer until an owner projection is admitted, served, and consumed into an exact snapshot and post-growth context. `producer_missing` applies to the canonical active-WDI projection and DataSnapshot/prior evidence issuers; `bridge_missing` applies to projection → WMR → context/re-entry. This work advances the existing B12/ACQ-01 and R13 relation to GY-N13b/DS15; it does not establish or close any debt-register row, Atlas slice, or plan task. The same-runtime-store and subject/basis R13 residuals remain independently open.

**Falsifier / revisit trigger.** Reopen this assessment if a production caller is found that consumes the exact active receipt/projection, resolves the canonical variable to an existing slot through an owner-issued mapping, independently resolves an SKG prior for the resulting snapshot, and passes the verified WMR/context through served N5 under the same tenant-bound store. For the closure probe, retain receipt, epoch, snapshot-ID, and ref markers but substitute an unrelated SKG version while copying the WDI snapshot ID; the served witness must turn red. Remove the canonical-variable-to-slot binding while preserving those markers; it must also turn red. Preserving control: selected WDI admission and receipt recovery stay green, and ordinary candidate computation remains available with a typed post-growth unknown when the WMR/context basis is absent.

**Where it binds.** This is R13/B12 at the Data Forge → WMR → CycleSubstrateContext → N5 handoff, and advances the existing GY-N13b/Atlas DS15 corridor. Data Forge retains overlay, passport, and native-epoch admission. The projection implementation on `fba62c46dba85abfb3e94fb818bb26d6a56d7a0a` is a candidate only; its admission to the canonical tree and a served production consumer are prerequisites, not completed capability. The existing WMR and context owners retain construction and validation; the runtime-supplied guarded store retains tenant custody. No new owner is appointed by this draft, and no change to `DEBT-REGISTER.md` or `LEDGER.md` is proposed.

## R14 — historical W5 references and current WS-2D client evidence

**Question.** Should W5's `repo://` references be judged against today's
checkout, and what evidence may establish the exact repository snapshot against
which that historical closeout was admitted?

**Options and costs.**

1. Rewrite the W5 manifest references to current paths and reissue its timestamp
   or status. This would make the current-path checker green cheaply, but would
   change an immutable historical record under a later source epoch and imply a
   new W5 admission that did not happen.
2. Treat the commit that first added the W5 manifest, or another reachable
   ancestor, as its admitted snapshot. This avoids changing the record, but Git
   history does not say that this was the source state used for the recorded
   admission; choosing it would turn chronology or convenience into authority.
3. **Proposed bounded choice:** preserve W5 bytes and report its historical
   reference verdict as `UNRUN` / `not_established` until the registered owner
   supplies an authorized, content-bound receipt identifying the exact admitted
   commit and tree. Separately repair WS-2D's current code-evidence paths to the
   existing generated-client outputs. This leaves one historical predicate
   unresolved and requires an owner receipt, while restoring truthful live
   closeout evidence without restamping W5.

**Premises.** The W5 manifest blob is
`architecture/policy_design_case/wave5_i5_external_consumer_truth_manifest.json@fa16e56d90fcfb6b90d8de56cb261ae00f69a95d`
with content SHA-256
`a1ecd3ccbce72bb4b19d4c07d9f59878025fa0e456dbcf5df4f058c3b86cd095`. It records
`generated_at=2026-05-23T00:00:00Z`, an owner, and `repo://` paths, but no source
commit or tree. The registry
`architecture/generated_artifacts.toml@9c0f1dfdac86dd02f16d3b17c5bd28da4e0f9165`
classifies it as an immutable `source_committed` historical record and pins its
bytes; that SHA does not identify the repository tree against which its links
were admitted. The archived closeout
`docs/archive/reports/2026-05-23-policy-design-case-wave5-closeout.md@a9b5684ad7dca3863881fd2a1de54fc3bb77d3e7`
states the same date and owner and names the manifest, but records no commit or
tree. The W4 sibling uses the same date/owner form without a snapshot identity
(`architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json@fbae5281f065ebbd9ad988a6261a48cf9a660e06`).

Git records the W5 manifest's first addition in commit
`da54f58206f396d8620425a6d45464640e650dd9`, tree
`2c66e430a71b2dcfe5702da0892f328ee2a7404e`, authored on 2026-05-30. That tree
contains `packages/runtime-api-client/runtimeApiClient.ts`; the manifest's
generated date is seven days earlier. This proves the first committed tree held
the referenced path. It does not prove that tree was used for the May 23 W5
admission. No existing source/owner receipt resolves that discrepancy.

The current validator in
`tools/quality/validation/check_policy_design_case_capability_ratchet.py@1cd361b73a01e7ed7668d18b92a4491e335d8628`
passes the present `repo_root` into `validate_repo_reference`, which checks the
current filesystem path and, when present, anchor text. The baseline W5 case
`tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py::test_wave5_exit_records_i5_manifest_and_influence_boundaries` has source blob
`7c4b73fb339f36b21bcc430c1260f35d76a745d6`. The complete P41 same-key four-base
receipt is now recorded in
`PolicyOS_E02R2/R14_RATCHET_MAP.md@c13460e67ebf13ba36faf077fb38a7c38fce5631`
(commit `9d54442a`): E02 execution base and main pass; E02 head and Phase 0 fail.
The map cites each JUnit path and SHA-256 and records the complete denominator of
36 refs / 30 target paths, with only the retired raw client path missing on E02 and
Phase 0. The E02 and Phase 0 failures establish the present-path regression; they
do not establish that the historical Wave5 claim was false. The R2 Wave5 sibling
above records the same four JUnit identities and the separate historical/current
predicate boundary.

For WS-2D, the current closeout ledger
`release/core-runtime-closeout.ledger.toml@fa45439af5135f04f2de06199645ac0a8b6f7073`
still cites `runtimeApiClient.ts` and `.js`. The unchanged loader
`tools/devx/workspace/core_runtime_closeout.py@4c9b00f7ba498763de40ed9211631c33d0bfce70`
checks these as current evidence paths and correctly refuses the now-missing
files. The generated-artifact owner list in
`docs/reference/generated-artifacts.md@18c0d71a208bd22cfd1aef6c3b6dd3446f2d89c3`
names `types.ts`, `canonicalRuntimeApiClient.ts`, and
`canonicalRuntimeApiClient.js` as the current outputs. The three unchanged
closeout tests at blob
`69a05038d3c2bd5123c4fd81e473426c355f85b1` exercise those current ledger paths.

**Proposed choice; principal status.** Adopt option 3, pending Denis's ruling.
Do not edit, regenerate, or restamp the W5 manifest. The smallest evidence that
would close its historic reference check is an append-only owner-issued
provenance receipt from `team-runtime-quality`, binding the manifest's exact
SHA-256 to the exact repository commit and tree used for W5 admission and stating
the basis for that binding. No such receipt is established in the inspected
owner records. Until it exists, historical W5 reference validation is
`UNRUN` / `not_established`; it is neither a historical pass nor a proved
historical failure. Engineering may resolve and verify repository objects only
after that identity is supplied. Independently, update the WS-2D ledger to cite
the current generated-client outputs listed above; preserve its `implemented`
claim only if all replacement paths resolve.

**P37 — gate predicates at admission.**

- W5 manifest bytes must match the generated-artifact registry's exact content
  SHA (`recomputed`). That binds the record bytes, not its source tree.
- The claim that a particular commit/tree was the W5 admitted source is
  `not_established` until the artifact owner supplies a receipt for that
  snapshot. `generated_at`, current branch ancestry, and a path-introducing
  commit cannot substitute for that owner fact.
- Once supplied, the receipt-to-manifest binding and Git tree/blob membership
  must be independently checked (`independently_reconciled`). Failed Git object
  or tree inspection returns `UNRUN`; it is not a green result.
- WS-2D's listed generated artifacts are current evidence. Their existence is
  recomputed from the present repository and does not confer API authority.

**P38 — property and divergence.** Property: every repository reference in the
historical W5 record resolved to the expected file/anchor in the exact snapshot
used for its admission. Current implementation: it checks `Path.exists()` and
anchor text in today's checkout. Divergent case: E02 deletes the raw client
path, so the unchanged historical manifest fails today's path check, while the
checker has no recorded snapshot identity with which to decide historical
validity. For WS-2D the required property is different: current closeout paths
must exist now, and the current-path check is appropriate once the ledger names
the current generated outputs.

**Remainder and signatories.** `team-runtime-quality` owns the historical W5
record and must sign the source-snapshot fact; Denis, as principal, decides
whether that fact is required to make historical links admissible and accepts
the bounded `UNRUN` state meanwhile. The runtime/API client artifact owner
maintains the generated outputs, and the core-runtime closeout owner maintains
the current WS-2D evidence row. This proposal does not appoint a new owner,
assert that W5 was invalid, or authorize a W5 reissue. The historic reference
predicate remains incomplete until the source snapshot is owner-bound.

**Falsifier / revisit trigger.** Reopen when `team-runtime-quality` supplies an
owner-authorized snapshot receipt binding the exact W5 manifest digest to an
exact commit and tree. At that point, a behavioral removal probe must keep the
W5 manifest bytes, status, and phase markers fixed while checking a tree where
the cited target is absent; inspection proving absence must fail, and an
inspection failure must return `UNRUN`. The positive control must resolve the
unchanged W5 refs in the owner-bound historical tree even when the current tree
retires the old client path. A current-tree unrelated edit must not change that
historical verdict. Separately, remove a canonical WS-2D output while leaving
ledger status text untouched; the current closeout check must reject it. These
probes are required and are not claimed as run here.

**Where it binds and register proposal.** The historical resolver belongs at
the W5 call path in
`tools/quality/validation/check_policy_design_case_capability_ratchet.py`; keep
ordinary active capability-reference checks bound to the current tree. The
semantic acceptance identities are
`tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py::test_wave5_exit_records_i5_manifest_and_influence_boundaries`
and all three cases in
`tests/repo_quality/tools/test_core_runtime_closeout.py`; repair the latter by
updating only the WS-2D evidence refs in the release ledger. Add the R14
historical snapshot limitation and these exact closure signals to the proposed
register/crosswalk records; P37 and P38 already describe the gate failure class,
so this draft proposes no duplicate pattern row. Do not claim closure for W5
from the current-path test alone.

## Closeout note

R1 option A and R11's universal v3 blocked-run/N9-exclusion rule have principal
rulings recorded in their dated addenda. Their finding-level status and outstanding
falsifiers remain governed by those addenda. Denis's R5 protected-mode fail-closed
direction is recorded and its five-band served-intent implementation is integrated
at f7d66883f; R5 remains open on its DataTrust-positive bridge and complete
four-base whole-file P41 replay. The separate R1/R5 per-active-basis decision remains
pending. At this earlier closeout snapshot, the remaining principal proposals in
this document were R2, R9, R13, and R14. Later dated addenda below add the separate
R1 Appendix-A test-identity proposal and the R9 V2 production-approval ruling; this
undated snapshot is not the current status. Earlier proposal text is retained as
history; dated addenda supersede status claims only where they explicitly say so.
No governed reissue or restamp is authorized by these records.


## Public IR owner decision — versioned uncertainty representation (B31, B201, B202)

**Status:** draft for the public-IR owner(s); not adopted. The three findings remain held. This draft records one owner decision per finding and a shared schema direction only where their public uncertainty representations intersect. It does not assign B201/B202 to DS16: the current crosswalk removes those exact edges, and DS16 is contextual adjacency rather than a shared producer owner here.

**Question.** What public, versioned representation preserves identification bounds,
statistical/model uncertainty, point-functional semantics, and joint-draw identity
without treating one as evidence for another or granting authority by itself?

**Options and costs.**

1. **A — additive versioned uncertainty contract (recommended).** Keep
   `ValueOuterSet` identification-only; encode statistical uncertainty in a separate
   typed channel tied to estimand and unit; tag the point functional independently
   from the equal-tail interval; reuse `PosteriorSamplesCarrier` for inline joint
   draws and define a content-bound typed reference for persisted large draws. Bind
   one common ordered-draw identity and version the public schema. Cost: schema bump,
   historical serializers/migrations, persistence and producer/consumer wiring, and
   end-to-end verification.
2. **B — retain candidate-only summaries until the served chain exists.** Do not
   present incomplete means/intervals or marginals as a complete distribution; carry
   a typed limitation where a consumer needs the missing semantics. Cost: reduces
   immediate compatibility work but leaves statistical uncertainty and joint-law
   consumers unavailable; it does not close the producer/consumer capability.
3. **C — narrow compatibility projection with a tagged median.** Where the public
   interval must contain its point, set `point_functional=median`, preserve posterior
   mean separately, retain native equal-tail bounds, and still use a carrier/reference
   for joint operations. Cost: requires a versioned semantic tag and is incompatible
   with consumers that interpret the point as mean; it does not close joint-draw
   identity or large-payload persistence.

**Premises.** The four focused diagnostic probes reproduced two B31 failures, one
B201 failure, and one B202 failure (4/4 expected diagnostic failures; 0 errors).
`ValueOuterSet` currently does not preserve a statistical interval separately from
identification bounds; the IR envelope rejects a valid skewed posterior whose mean
lies outside its equal-tail interval; and calibration summaries omit the existing
`PosteriorSamplesCarrier`, so different joint draw pairings collapse to the same
marginals. The complete tracked-source census covers 2,696 product Python files,
2,732 test Python files, and 5 IR migration Python files. It found no production
callsite for the summary adapter or value-outer-set helper and no uncertainty-family
migration references. `PosteriorSamplesCarrier` exists and Foundry Monte Carlo
consumes it, but the source string `joint_sample_id` is not content-bound to the
ordered draw payload. The probe ran at `59c9d7331a39f5a333d316df94ce870febeddfe4`;
direct owner/source-test files were identical through `9d20cabe72a46d98a4d80da5c28b37b456857d44`, while transitive import closure at that later head is
`not_established`. The later `7f162d98` commit changes only ledger documents. No
production positive consumer, public migration/replay, or authority-grade effect was
measured.

**Proposed choice and decision-maker status.** Prefer option A as the target
contract, with option B as the operating limitation until an owner-admitted schema
and served consumer exist. The public-IR owner for each semantic decision must rule; this draft is not a
principal ruling or authority admission and does not assert one shared owner appointment. The three binding decisions are: **B31** —
separate identification bounds from statistical/model uncertainty; **B201** — choose
and version the point functional independently of equal-tail interval semantics while
preserving v1.1 history; **B202** — choose the public inline-carrier / persisted-reference
contract and content-bound ordered joint-draw identity. Reuse `PosteriorSamplesCarrier`;
do not create a duplicate carrier or infer a source law from marginal summaries.

**Remainder.** This schema decision does not establish calibration validity, sampler
adequacy, mixing, effective sample size, a production consumer, large-draw storage,
or byte-exact historical replay. It grants no promotion or publication authority.
Those producer, persistence, consumer, migration, and served-witness tasks remain
implementation work after the owner decision.

**Revisit trigger (falsifier).** Reopen if a supported consumer cannot preserve a
nonzero native statistical interval alongside a point-identified set without widening
the identification set; if a valid asymmetric mean/equal-tail summary changes meaning
or fails byte-exact replay; or if two distinct ordered joint-draw batches can share an
admitted identity or reload as the same joint law. The draft is not closed until
behavioral probes for all three properties pass through persistence and a production
consumer.

**Binding scope.** Public/versioned uncertainty representation and B31/B201/B202
producer-consumer paths only. B31 has separate GY-N8/Atlas DS16 touch relations; the current crosswalk admits no B201/B202→DS16 edge and no shared DS16 producer owner. No domain or jurisdiction profile is selected, no data
or sampler is certified, and no promotion/publication authority is granted.

**Source receipt:** `/Users/deniskopylov/.codex/scratch/e02-r2-held-uncertainty-20260926/held-uncertainty-ledger-addendum.json@sha256:1601a73ebb33f1246978ab399fb7eae0fc8ccd066d068b7e8064cf29e9528b4a`. The four probe assertions are expected to fail
against the current implementation; their output is a diagnostic counterexample, not
a passing acceptance suite.

## DFK-01 held owner decisions — LA-005, LA-026 and LA-027 (2026-09-26)

**Status.** These three rows remain `held`; this addendum changes only their single blocker kind from `data_record` to `owner_decision`. The complete local inventory is recorded in /Users/deniskopylov/.codex/scratch/e02-r2-dfk01-inventory-20260926/DFK01_REASSESSMENT.md@sha256:974d4eca6604e4343f08c567d6e057b0838abacd0520dd192b760d7ca9e6a4d3. It establishes repository-local source, test, tool, loader, package-configuration and locally reachable-history facts. It does not establish external publications, installed consumers, or untracked payloads. The inventory was taken at `bcf14f319`; the tracked product inputs are unchanged through current HEAD `4d79cd5971c8a6b95078aeaa8e49157f125e124a`. No behavior, wheel/sdist artifact or P41 test was run.

The remaining question is the owner’s supported-FQN/canonical-owner decision. An external shipped-version, external-import and persisted-class/import-identity consumer record is conditional: require it only if the responsible owner asserts that the old FQN is supported. If a concrete retained payload is later identified, record its identity and replay or conversion requirement separately; do not infer public support from payload presence. The local census alone is not evidence of external absence.

### LA-005 — `polisyos.foundry.domain.schema` public support boundary

**Question.** Is the exact Foundry schema module a supported public entrypoint despite its absence from the explicit Foundry stable-entrypoint list?

**Options and costs.**

1. **Contract controls; treat the module as internal.** The public-surface owner and Foundry schema owner confirm that the contract allowlist governs, then retire only `foundry/domain/schema.py` after a marker-retaining negative import and built wheel/sdist absence check. Preserve the declared Foundry facade and the distinct plugin/provenance DTO owners. Cost: update the current importability test, package output, and any internal import. No external-consumer census is required absent an owner assertion of support.
2. **Declare a supported ABI.** Add the exact FQN to the public-surface contract, provide a deprecation/sunset window and an owner-issued inventory of shipped versions, external import consumers and persisted class-identity payloads before migration. Cost: maintain the API and migration window, extend package/public-surface validation, and preserve or convert old identities.

**Premises.** The explicit contract lists only `polisyos.foundry`, `.api`, `.compile`, and `.execute`; the source module calls itself a public API and the current DFK test preserves its importability. The complete local census found the FQN only in that test, not in production source/tools. Current Hatch configuration includes `src/polisyos`, but no locally tracked built distribution proves what was published. Sources: DFK01_REASSESSMENT memo above; `policy-engine/architecture/public_surface/contract.toml@sha256:579f930914495042582072e1c6d9ccf8e05bda121e87c462fe5c886e9f00a580`; `policy-engine/src/polisyos/foundry/domain/schema.py@sha256:9795fe24efddc4cd27ceb537c82a3663d8f4052bf063b65cf7b70d4e348ee347`; `policy-engine/tests/unit/remediation/test_dfk_01.py@sha256:6264576cce04bd0f753b763623c715eec4c9ffef69cf1c261c93523212326d56`; `policy-engine/hatch.toml@sha256:761d5e5395c8f2b72e9bb36ee39471dd8dc6ae7ab5046fbdd74a38485b1a84fa`.

**Proposed choice; owner status.** Prefer option 1 if the public-surface owner confirms the written allowlist is controlling. No owner or principal ruling is yet recorded.

**Remainder.** LA-005 stays held until the owner answers. Either choice still needs the finding-specific positive/canonical control, negative/removal probe, built-package witness when retirement is selected, and four-base P41 replay. A support ruling makes the shipped-version/consumer/payload record an additional required input to that decision path; it is not presumed today.

**Revisit trigger / falsifier.** Reopen the internal-by-default choice if an owner-issued public API catalog, release manifest, supported-version matrix, external import integration, or retained payload demonstrates that the exact FQN is part of the supported ABI. The retirement witness must also turn red if the module is restored while its negative/import and wheel/sdist assertions remain.

**Where it binds.** Public-surface owner binds `architecture/public_surface/contract.toml`, the public API boundary, and any deprecation window. Foundry schema and package owners bind internal caller migration, package output, and the behavioral witness. This does not authorize a broad `foundry/domain` deletion.

**P37/P38.** The complete local source/test/tool/import-loader/history census is `recomputed`; Hatch inclusion is `recomputed` from configuration, while built/published artifact contents and external consumers are `not_established`. The relation between the written allowlist, the “public API” docstring and the September importability test is an `owner_decision`, not a locally recomputed authority fact. The current test turns on successful import/class identity; it does not turn on public support or actual consumers. Divergent case: the path is absent from the current allowlist while the test is green and Hatch still packages it.

### LA-026 — `polisyos.data_forge.kernel.schemas.codegen` descriptor role

**Question.** Does the empty `GeneratedSchemaModule` descriptor have an intended supported contract/consumer, or should this exact module be retired?

**Options and costs.**

1. **Retire the placeholder.** Data Forge schema owner confirms it has no producer/consumer role; remove only the descriptor/FQN and replace the positive import assertion with the negative/removal/package witness, preserving the canonical schema registry and migrations. Cost: update one module, its explicit compatibility test and built-package projection.
2. **Retain as supported.** Owner names the producer, consumer, artifact contract and canonical schema owner; designate the FQN and versioning/sunset policy. If externally supported, issue the shipped-version/import/persisted-payload record before changing it. Cost: implement and maintain the actual capability plus producer/consumer/replay tests; the name alone does not justify generating code.

**Premises.** Local census found a three-field descriptor with no generation behavior or production source/tool consumer; it is not present in the ABI model registry. The current test treats importability as preservation. The repo does not supply an external support record. Sources: DFK01_REASSESSMENT memo above; `policy-engine/src/polisyos/data_forge/kernel/schemas/codegen.py@sha256:2e4d9bf7791b0cccce090fd80afde9bb51809506a51666dfd9fde2a8ef4c685e`; `policy-engine/src/polisyos/schemas/abi_models.py@sha256:651884b092b690b868c8501e7a5cc34d19f7d68cad2b65cd1180ae928b50c835`; DFK test and Hatch config cited under LA-005.

**Proposed choice; owner status.** Prefer option 1 if the Data Forge schema owner confirms the descriptor has no intended consumer. No owner ruling is yet recorded.

**Remainder.** The finding stays held pending owner response. Retirement still requires an import-negative and built-wheel/sdist absence witness, a removal probe that restores the path while keeping markers, canonical-registry positive control, and P41 replay. If support is asserted, the owner must name its producer/consumer and issue the conditional shipped-version/external-consumer record. If a concrete retained payload is separately identified, bind a replay or conversion witness to that payload; behavior remains unmeasured.

**Revisit trigger / falsifier.** Reopen retirement if the owner supplies a concrete producer/consumer contract, an owner-issued shipped-version/API record or a retained payload whose type identity resolves to this FQN. The negative test must fail if this module is restored while its markers remain.

**Where it binds.** Data Forge schema owner binds module role, canonical registry ownership, and package compatibility; package/test owners bind actual wheel/sdist contents and the removal/control witness. No second code-generation owner is created by this draft.

**P37/P38.** Local source/import/dynamic-loader/history facts are `recomputed`; external support and payload use are `not_established`. `test_dfk_01.py` currently turns on importability and class shape. Divergent case: a module can import successfully while its descriptor performs no generation and has no producer/consumer.

### LA-027 — canonical schema path and `pipeline.schemas` compatibility

**Question.** Is `kernel/schemas` the canonical registry/evolution/migration owner and `kernel/pipeline/schemas` a temporary compatibility alias, or does the active plan’s pipeline path remain the canonical destination?

**Options and costs.**

1. **Keep `kernel/schemas` canonical; sunset the pipeline alias.** Data Forge and architecture-plan owners confirm the implementation/facade path is authoritative, then the plan owner reconciles the plan and names a migration owner/sunset. Retain the old import only for an explicit bounded compatibility window. Cost: plan/caller/test updates and, if removal is approved, a package/history migration witness.
2. **Make `kernel/pipeline/schemas` canonical.** Move the registry/evolution/migration implementation and all callers behind that path, and leave at most one compatibility re-export at the former `kernel/schemas` address. Cost: relocate one owner and update facade, callers, architecture boundaries, tests and package projections; prevent two registries.

**Premises.** The tracked implementation and top-level facade use `kernel/schemas`; `kernel/pipeline/schemas` re-exports it, while `DATA_FORGE_CONSOLIDATION_PLAN.md` still names the pipeline path for the registry. The local census finds no other production source/tool consumer of the pipeline FQN, but local absence does not establish external ABI absence. Sources: DFK01_REASSESSMENT memo above; `policy-engine/src/polisyos/data_forge/kernel/pipeline/schemas/__init__.py@sha256:0ab76067bbdd73818cda5d79fbac01c24c4b6f8ac03c80835ead6403ea80b9bf`; `policy-engine/docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md@sha256:28927b07f7d068260df4f586a670d2883b4f44180b78411b0efe76764072360f`; `policy-engine/architecture/shims.toml@sha256:3752050d411eecc6dddf52500d009e6d081de12d2584497aa8916ffdc9e312d3`.

**Proposed choice; owner status.** Current implementation evidence favors option 1, contingent on the plan owner’s confirmation; this draft does not amend the plan or assert the alias sunset. No owner ruling is yet recorded.

**Remainder.** LA-027 remains held. After the path ruling, preserve one registry owner and prove canonical imports/identity, the chosen old-address behavior, package output, a marker-retaining removal/alias probe, and four-base P41. Require an external shipped-version/import/persisted-identity record only if the owner affirms the old FQN is supported; handle any concrete retained payload as a separate versioned replay/conversion input.

**Revisit trigger / falsifier.** Reopen option 1 if the plan owner reaffirms the pipeline path as the required owner or an owner-issued release/payload record shows supported external imports of the alias. A claimed sunset is falsified if a shipped supported-version artifact or retained import identity still requires the alias after the declared window.

**Where it binds.** Data Forge owner binds the single registry/evolution/migration implementation; architecture-plan owner binds the documented canonical path; package/public-surface owners bind the supported old FQN and sunset gate. The draft does not edit the plan or register.

**P37/P38.** Current implementation and exact import/export identities are `recomputed`; the plan is `institutionally_supplied`; its authority relative to the source owner is not resolved. External clients and published artifacts are `not_established`. Existing alias/importability tests establish that both paths resolve to the same objects, not which address owns future schema behavior or the completion of a sunset. Divergent case: both imports preserve identity while the plan names the alias and code/facade name the canonical implementation.

**Shared H14 partition check at add75.** The complete 14-row walk is: owner decisions `{B31, B201, B202, LA-005, LA-026, LA-027}` (6); data records `{B61, B219, LA-031}` (3); smallest missing capabilities `{B194, B197, LA-032}` (3). Current status is 12 held and 2 bounded closed (`LA-010`, `LA-049`), with no open H row. The LA-migrations audit memo gives an intermediate 6/2/4 partition by placing B219 under `smallest_missing_capability`; the B219 audit identifies the unavailable pinned NetworkX 3.6.1 runtime artifact as `data_record` while the implementation/test owner exists. This explicit disagreement is resolved from the complete row walk and B219 owner audit. The Appendix-C held labels for LA-010/049 remain historical; their closure is bounded to in-repository owner/caller contracts. No status, behavior, or blanket compatibility claim is inferred beyond those rows. Audits: /Users/deniskopylov/.codex/scratch/e02-r2-held-la-migrations-20260927/HELD_LA_MIGRATIONS_CURRENT_HEAD_AUDIT.md@sha256:cec3e25b3bf4eedc2127160cf323663d67cad6c8a695654658d59a5746b6bf9b; /Users/deniskopylov/.codex/scratch/e02-r2-held-b194-b219-20260927/H_B194_B219_CURRENT_HEAD_AUDIT.md@sha256:3b351908c5f4b597bd942b28a4f9a1120bccf8e21e2354a50b2dff019fa5caa4.


## Current-head bounded implementation addenda (2026-09-27)

### R5 — served fixture contract repair

Commit `ce18d7445` updates the served control-service fixtures to use the injected artifact store/catalog and observe the owner-derived source context. Focused selectors passed 3/3 and the candidate-path controls 3/3 (JUnit receipts are in `FINAL_REPORT.md` and `residual_ledger.json`). This repairs fixture alignment only; the positive DataTrust bridge and full four-base P41 remain open.

### R11 — public blocked-N6 refusal witness

At commit `11feb2108`, the focused public export group passed 2/2, including `test_terminal_blocked_n6_refuses_public_n9_projection_before_receipt_parse` and a public-surface control; the historical N6 suite passed 26/26. Receipts: `/Users/deniskopylov/.codex/scratch/e02-r11-integrated-20260927/R11_PUBLIC_EXPORT_FOCUSED_V4.junit.xml@sha256:3664c2035c16d8eba5a38319928602487941616e7fd56d830016b4659667c7cf`; `/Users/deniskopylov/.codex/scratch/e02-r11-integrated-20260927/R11_HISTORY_FULL.junit.xml@sha256:7c574c748eca6d45de718fa53bd04ec8c26595cb1dafc3183f05278774c5f404`. Later shared-file changes mean these are component receipts, not a current `a5141d432` whole-file or four-base replay. Public/board consumer completeness and the full R11 class remain open. The B10/B11 source-card audit does not assign their distinct discriminators to R11.

The independent V2 review gives a bounded GO to the test-only controller→`PromotionRuntime._prepare_completed_generation` latest-occurrence/final-basis witness design. The V3 test-only integration patch is uncommitted on top of `355225dd`. Its four focused selectors passed 4/4, but the full test file is still running; this is not a full-file or integrated class result. This 4/4 receipt supersedes the earlier setup-red candidate attempt and does not change `verification_missing` until an owner-issued nonblocked run reaches the witness. Public board/projection and four-base consumer completeness remain open. Focused JUnit /Users/deniskopylov/.codex/scratch/e02-r11-v3-integrated-355225-20260927/focused/test.junit.xml@sha256:6ffce55fd929069d048a4b7b26fc372cf8720198d8e0f331712562420ab554f6; V2 design review /Users/deniskopylov/.codex/scratch/e02-r2-r11-current-a514-test-candidate-20260927/R11_TEST_CANDIDATE_V2_INDEPENDENT_REVIEW.md@sha256:3206d20fbd57993c69440b45ebf536a782b3becee9a6764e89578955224c75ec.

### R2 — candidate currentness boundary

Commit `a0d820c22` has a focused candidate/stale witness: a candidate can carry typed `not_established` currentness while strict authority validation rejects it; a foreign deployment identity is stale and refused; substituting the strict validator at the recursive owner boundary makes the otherwise valid candidate path fail while the ordinary candidate control passes. The focused JUnit and stale guard RED/GREEN are cited on B30 in `residual_ledger.json`. This does not choose between the pending principal options, establish source-free packaged currentness, or close the historical-unrelated-edit/current-currentness distinction. A separate WDI `[False]` selector previously failed with a chronology `InputRef` AttributeError; that red is superseded for that selector by the 1/1 green at exact head `a5141d432` after signed-evidence InputRef integration. The distinct latest full WDI file is 8/9 at `a5141d432`, with one failure awaiting P41 attribution (`UNRUN`); neither receipt closes B12’s dependent-calculation discriminator. The R2 full four-base replay remains `UNRUN`. The bounded integration at `a877f8abc` then ran `test_generation_cycle.py` 145/149 and `test_generation_cycle_history.py` 26/26; the exact comparison to 154 had zero pass→fail among 148 common identities. It neither supplies an installed N6 issuer nor proves positive N9 authority. Durable receipt: `/Users/deniskopylov/.codex/scratch/e02-r2-integrated-154407-20260928/R2_INTEGRATION_RECEIPT.md@sha256:064aac803a3091a2296d67606a0820bbd24e925d33be6b01dd1499b25ce85e29`.

### R2 packaged-identity issuer blocker checkpoint

The read-only checkpoint at `a5141d432912efc5611129ce0b22d13a30762dfc` finds no production build/deploy owner issuing and admitting a signed identity that binds exact installed-code bytes, canonical lock, and complete N6 route-census evidence. The confidence-ledger owner remains the sole identity reader. Keep packaged strict currentness typed `UNRUN`; do not add a package-local self-attested manifest or a parallel issuer. No positive packaged path, code patch, or epoch reissue follows from this census; ordinary candidate computation remains available under declared unknown. This is an owner-appointment decision blocker, not a behavioral receipt. The bounded owner-design decision draft is `/Users/deniskopylov/.codex/scratch/e02-r2-loaded-manifest-owner-design-20260927/R2_IMPLEMENTATION_BLOCKER.md@sha256:3a2900be1f4cab2ed92c780d95f48d5719b129dc35919bc0181eff1bd6636453`. Full bounded blocker and item-7 decision draft: `/Users/deniskopylov/.codex/scratch/e02-r2-loaded-manifest-owner-design-20260927/R2_IMPLEMENTATION_BLOCKER.md@sha256:3a2900be1f4cab2ed92c780d95f48d5719b129dc35919bc0181eff1bd6636453`. Checkpoint source `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py@sha256:9a8945227abf9638f97740639ba9856e53ae08cf7b11cc7fd4ad064d280c62fd`; integrated R2 source `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py@sha256:cc09224f8ad20e94fdcd4d7fc26021da3aee0ee4ee44c2798bb97752403be3b2`; the earlier leaf-overlay source pin `sha256:63b3c9bbde5faf530da1466a563e76833c6d29682612d86ea008e8a08c3d7e4d` is historical.

### R9/P07 — P40 bounded residual after second independent BLOCK

Commit `99887f92a` now has a bounded exact-head signed-evidence full-file result 6/6 and WDI `[False]` selector result 1/1; receipts are `/Users/deniskopylov/.codex/scratch/e02-r2-integration-wave-20260927/r9/signed-evidence.junit.xml@sha256:a6548174f1164f4a8083618fda1dcc4b6556ebd379d8baf538ade714b490daee` and `/Users/deniskopylov/.codex/scratch/e02-r2-integration-wave-20260927/wdi/false.junit.xml@sha256:dce268d078c61cd8fa152b2e6fd499e3e224a97160bc27cf18fe10ca84dcdf3c`. These do not clear the separate projection-class residual. The independent static review `/Users/deniskopylov/.codex/scratch/e02-r9-p07-scope-20260927/INDEPENDENT_REVIEW.md@sha256:89c3d1e626a4baa7fe85d7bdf5ff3a5fca6a47c8084ecfae0eba023d17dc371c` BLOCKs candidate patch `b5ee2b67dc2a4dfeb3ba44e7504163a97d0cf0b38dbdb654a3190b27f68f9788` on base `58a6420af`. This second escape is bucketed as the same shared R9/P07 projection class; it is not a direct review of commit `99887f92a`'s signed-evidence `InputRef` correction. P40 therefore stops per-consumer patches in this class. Bounded residual: preserve pre-version raw hashing for unversioned owners or version/replay each owner; type both inline-epoch schema overloads; and add typed v2 consumption or fail-closed evidence at the C3 signed-evidence anchor. The smallest closure capability belongs to the core artifact serializer and runtime chronology owners: complete consumer/schema census with version-aligned serialization and readback. Falsifier/closure signal, proposed and `UNRUN`: exact replay of a persisted unselected-ref `promotion-owner-query-context.v2` preimage; a marker-retaining versionless omission must turn the test red while explicit chronology v1 projection remains green; both inline-epoch producers must pass typed persisted round-trip; selected signed-evidence must be read through the C3 anchor with selector-free control. No closure or third-round implementation claim is made.


The later owner-level projection review is an independent BLOCK and remains the same R9/P07 class under P40, not a new site to patch: three runtime SignedEvidenceRepository constructor sites exist, but no production `persist_signed` caller; seven downstream DTO source files remain strict-v1 and reject v2; and the two C3 v1 golden vectors require replay. Keep R9 partial and stop per-consumer patches until a production producer plus versioned readers are identified. Memo `/Users/deniskopylov/.codex/scratch/e02-r9-p07-wire-registry-20260927/INDEPENDENT_REVIEW.md@sha256:fd5fd30a4d8b0f73d561264723eabd507de6ea3b100f4dbe97574296dde25c63`.

### R14 — bounded two-store test seam

Commit `a5141d432` adds `test_served_qualification_reads_policy_store_and_writes_runtime_store` and `test_shared_policy_and_runtime_store_remains_a_qualified_control` to `tests/unit/runtime/quality/test_chronology_proof.py`. Both touched chronology test files passed 46/46 at exact source head `a5141d432`; JUnit `/Users/deniskopylov/.codex/scratch/e02-r2-integration-wave-20260927/r14/two-files.junit.xml@sha256:5728a93ff4c9d11b76029e143f164cff06ac6b30751b2c45f326b4699bbd83e9`. This is bounded whole-file evidence, not a four-base replay or R14 class closure; no finding status changes are inferred.

### R1 — served-context and generic time-scope candidates: independent BLOCKs

The V2 served-context handoff review is BLOCK at exact source head `a5141d432912efc5611129ce0b22d13a30762dfc`: no named candidate-context provider was found in 0/2,907 tracked `policy-engine/src` files. The reviewed change is an injection seam, not an in-repository profile resolver or initial served bridge. A fixed Ukraine/fiscal-credit DataState→WMR producer does exist; it is not a capability-neutral profile selector or job-scoped served handoff. The separate exported no-context `design_generation` API may select the fixed-UA WMR while scope is `not_established`, but the served unknown-scope path exits through `candidate_proposal_only` before `_content_bound_candidates`; a served fallback is not proven and production-caller reachability of the API path remains under investigation. The owner census also finds the builder records requested time bounds without applying them in inspected queries.

The separate generic time-scope candidate is also BLOCKed: `data_time` is not a generic source-coverage predicate interchangeable with `WorldModelRecord.valid_time_scope`; the proposed comparison can over-refuse legitimate retrospective candidate work and unknown time encodings. Neither candidate has independent test/removal/control/four-base evidence. P40 treats both as the same R1 profile/scope class one level deeper; stop adding instance callbacks or parser formats. Keep ordinary candidate work available with typed unknown. The smallest missing capability is a source/profile owner that distinguishes evidenced coverage, evidenced non-coverage and unknown, plus initial job-scoped served handoff. Closure signal remains actual served N4 → qualified same-store N5 → separate S8 authority consumer. No B01/B02/B03 status changes follow.

Reviews and census: `/Users/deniskopylov/.codex/scratch/e02-r1-served-context-bridge-20260927/R1_SERVED_CONTEXT_HANDOFF_V2_INDEPENDENT_REVIEW.md@sha256:c95848c9fd3f7660d59931bcd7e4020d1512d00ffb51d0de73107b1e28ce06ae`; `/Users/deniskopylov/.codex/scratch/e02-r1-candidate-n5-patches-20260927/time-guard/R1_TIME_SCOPE_CANDIDATE_INDEPENDENT_REVIEW.md@sha256:7195aaee03de64908a9b356ef3e88dfaea898ebae281b1963a099c606e070a42`; `/Users/deniskopylov/.codex/scratch/e02-r1-served-context-bridge-20260927/R1_WORLD_PROFILE_OWNER_CENSUS_A514.md@sha256:200bebc024648c6b5e78254d5241f9f8465802b8c20caf09c189db6b1ca6286e`.


### R1 — default-world candidate independent BLOCK (add75 review)

At source head `a5141d432`, the default-world candidate is BLOCKed: its union return breaks N4 contract-validator/replay capture and a second-domain failure path. The review's complete denominator is 5,877 Python files and 27 public API call/definition occurrences. The candidate is not integrated; positive served N5/S8 remains absent. Memo `/Users/deniskopylov/.codex/scratch/e02-r1-grounder-default-world-20260927/R1_INDEPENDENT_REVIEW.md@sha256:8b00d67cb4b1969da3ae5b3e8e2bc6aa3ac37eaf98e70037c38665b014e55e75`. No decision ruling is implied by this review.

## Current evidence addendum — R11 and R12 (2026-09-28; no status changes)

R11: Commit 1544073dd4b6dd82cbaf77b5b2c22dea19cd3889 lands the independently reviewed V3 test-only latest-occurrence/final-basis witness. Focused selectors pass 4/4; the whole test_generation_cycle.py file is 139/148 (9 failures, 0 errors/skips). Relative to the 355 whole-file baseline, 144 test identities are common and none pass→fail. The positive owner-issued nonblocked N9 path is still UNRUN, so the universal blocked-N9 decision remains adopted while the class remains partial. Receipt /Users/deniskopylov/.codex/scratch/e02-r11-v3-integrated-355225-20260927/R11_INTEGRATION_RECEIPT.md@sha256:8ec84fa8174eee053f88a340a8154980f6344983e5d9584f70996e8fcf75bfdb; independent review /Users/deniskopylov/.codex/scratch/e02-r11-v3-natural-terminal-355225-20260927/R11_V3_V2_INDEPENDENT_REVIEW.md@sha256:a0a3edc52fb495b840056379284046fa4cdd889ae5fa1eb842ffcc7a1a8c7c34.

R12/R13: At clean 154, the acquisition-planner strangle selector passes and the whole planner file passes 71 tests with one intentional cloud skip. R12 diagnosis identifies the remaining two N7 synthetic-receipt expectations as a real-grounding gap: owner-produced N4 must operate on an admitted world through AcquisitionWorldGrowthBridge; classify the residual under R13, not R2. No expected outcome was changed and no class/finding status is promoted. Planner receipts and diagnosis are in FINAL_REPORT.md; exact diagnosis /Users/deniskopylov/.codex/scratch/e02-r12-diagnosis-20260927/R12_DIAGNOSIS.md@sha256:77b55664b7b5ee1800e422f7fd6911035b6481ab63e8dcd00f3908479439e328.

## R12/R13 — candidate N5/N8 re-entry after an N7 owner write (2026-09-28)

**Decision status.** Draft for Denis, not a principal ruling. Commit `44a7441eb` implements the bounded candidate behavior below and changes two Appendix-A test expectations. It does not claim production ACQ-01 world growth, CGF grounding, N9 admission, or S8 authority. The standalone draft is `/Users/deniskopylov/.codex/scratch/e02-r12-n7-candidate-20260928/PRINCIPAL_DECISION_DRAFT.md@sha256:ff423359673ac051c9e15ef2e025f045443ce0c2b964990ab179db6389ee5ac4`; the reviewed candidate and marker-retaining removal probe are recorded in `/Users/deniskopylov/.codex/scratch/e02-r12-n7-candidate-20260928/review/delivery/CANDIDATE_RECEIPT.md@sha256:324e86da7ae9b3b30be77eeca4bc73b5e2738199d57a345959000ecd377618ac`. At exact `44a7441eb` the complete generation-cycle file passes 153/153; against `10315b7b2`, all 153 identities match, with two N7 fail→pass changes and zero pass→nonpass. The third fail→pass is an N9 confidence-ledger case and is not attributed to this patch because ignored local ledger state differs. The complete comparison is `/Users/deniskopylov/.codex/scratch/e02-44a-cycle-p41-20260928/GENERATION_CYCLE_44A_P41_RECEIPT.md@sha256:597827a3203bc6e52855aa83f4a50dd64ba1f607bf85b8423b402ea186c2fb40`; four-base attribution remains `UNRUN`.

**Question.** After a verified local N7 owner write changes the selected candidate's world basis, may N6 run the existing N5/N8 candidate computations in the same cycle when no owner-issued, source-bound N4/CGF result exists?

**Options and costs.**

1. **Candidate-band re-entry with a typed unknown (implemented proposal).** Verify the emission, candidate ID and original hash, affected-source dependency, and exact owner-artifact target-slot binding. Rebind the atom to the new world reference and call N5/N8. Carry `grounding_unavailable` with no CGF disposition, certificates, or positive grounding count; withhold N9/S8 authority. Cost: two base expectations of one synthetic grounding result change to zero and an explicit limitation. A real N5 or N8 owner may still return pending, so this does not buy a positive estimate.
2. **Require source-bound N4/CGF before any re-entry.** This avoids dependent candidate work under unknown grounding. Cost: even a valid data-only owner write cannot trigger candidate N5/N8 computation; the receipt's same-cycle index remains a marker until a new N4/CGF producer is appointed and wired.
3. **Keep the early return and record a bounded residual.** This requires no immediate code change, but leaves the Appendix-A regression and the mismatch between re-entry markers and actual dependent callbacks.

**Premises.** The local fixture's owner artifact records a data/world write and a candidate binding, not a source-grounded causal result. The old fixture expectation counted fabricated CG1/CG2/CG3 shadow identifiers as real grounding. `acquisition_planner._rederive_grounding_for_affected_region` now returns `grounding_unavailable` with `generation_result_problem_scope_unestablished`; before `44a7441eb`, N6 returned before `_joint_value_node`. The acquired evidence source slot and an intervention's action target slot need not be equal: the affected-region dependency index relates the former to the candidate, and the owner binding independently identifies the latter. The reviewed control uses `owner_panel_missing` as source and `policy_outcome_slot` as target. These are in-repository contract-testing facts, not claims about a served N4/CGF owner.

**Remainder and owner.** The local N7 route remains confined to `contract_testing`; production world growth belongs to `AcquisitionWorldGrowthBridge` with overlay admission, passport, and native epoch. The N5/N8 witness uses pending test ports, so actual simulation/value evidence and post-growth dependent calculation are unproved. The runtime-quality generation owner holds the re-entry semantics; Data Forge and N4/CGF owners must issue and validate any future source-grounded post-write result. No second world-growth owner is appointed. B12 and LA-046 stay partial.

**Falsifier and revisit trigger.** Reopen if a mismatched candidate ID/hash, owner target-slot binding, or absent affected-source dependency can reach N5/N8; if retaining receipt markers while removing `_joint_value_node` leaves the test green; if the typed unknown is labeled `grounded_shadow`; or if pending N5/N8 work yields an N9 receipt or S8 authority. Revisit when an owner-issued N4/CGF result is independently bound to the post-write world and candidate. The marker-retaining early-return probe is red at the actual N5 callback count and the restored three-selector control is green, as recorded in the candidate receipt.

**Where it binds; P37/P38.** This draft binds only the N7→N5/N8 candidate handoff and the two named Appendix-A tests; the R6 foreign-context refusal remains. Verified emission, candidate hash, owner target slots, and dependency membership are recomputed from the receipt and atom for this local contract. N4/CGF source grounding is `not_established`, so it cannot carry an authority gate. Requiring source-slot and action-target string overlap would test vocabulary coincidence rather than dependency; the disjoint-slot control is the divergent case. The production served chain and four-base P41 remain to be measured.


## R1 — Appendix-A selector identity for contextless HTTP N4 refusal (proposed principal decision; 2026-09-28)

**Decision status.** Pending Denis. This is a proposed new principal-level decision about the Appendix-A test identity, separate from Denis’s already-selected R1 Option A: the served, owner-bound N4→N5→S8 path. Code/test commit `267636d55ada385a08a4c9c3b6c02f58abb75685` changes the witness from `test_http_and_direct_recursive_paths_share_the_pre_n9_subject_strangle` to `test_http_contextless_explicit_n4_refuses_before_n4`; the replacement's docstring calls the old selector “Retired.” That code label is not a recorded principal ruling. This entry asks Denis whether to accept the identity change; it does not reopen or replace Option A. The existing Option A owner-chain memo is /Users/deniskopylov/.codex/scratch/e02-r1-positive-owner-chain-20260928/R1_OPTION_A_OWNER_CHAIN_MEMO.md@sha256:7fa9f630a3b2d7ecd483d16511f8fb4a771b3ebb4c32ed56ba43899043d3dc9a.

**Question.** Should Appendix-A accept the HTTP-only refusal identity in place of the combined HTTP/direct-controller identity, retain the combined parity requirement by rebuilding its witness, or split HTTP refusal and direct-controller behavior into separate cases?

**Options and costs.**

1. **Accept the HTTP-only refusal identity as the Appendix-A witness (proposed; pending Denis).** It measures only refusal before explicit N4 when served owner context is absent. Cost: test/P41 owners must bind the new identity and keep direct-controller behavior as a separate residual; a later parity claim still needs paired inputs and owner-bound evidence.
2. **Retain the combined identity and parity requirement.** Rebuild a test that exercises both paths and specifies the same observable property on matched inputs. Cost: runtime-quality/test owners must restore or add the direct-controller and HTTP controls, and P41 must track the actual combined inputs; keeping one name without both paths risks a false parity claim.
3. **Split into separate HTTP and direct-controller cases.** Keep the new HTTP refusal witness and add an independently specified direct-controller case. Cost: an additional selector, path-specific controls, and separate P41 identities, but each test then binds one property.

**Premises.** At code/test commit `267636d55ada385a08a4c9c3b6c02f58abb75685`, the replacement HTTP selector asserts `cycle_substrate_context_not_established`, zero N4-port calls, and no `runtime.promotion.pre_n9_epoch_validity_subject` artifact. The selector passes in /Users/deniskopylov/.codex/scratch/e02-r1-r13-http-intent-20260928/renamed-target.junit.xml@sha256:daba72e4868894223797f81e1f64a0b015e082d8d0a980ebf05f159e19827d4e; the marker-retaining guard-removal probe fails the selector because explicit N4 is invoked in /Users/deniskopylov/.codex/scratch/e02-r1-r13-http-intent-20260928/guard-removal-probe.junit.xml@sha256:a65c57f5b0877f3e865629ca1275f8b91d5a13324177f2f42c0e960f6bd447ed. The separate three-scope served candidate-preserving control, `tests/unit/runtime/http/test_control_service_di.py::test_served_nl_job_persists_real_candidate_proposal_without_n6_or_s8`, passes `[None]`, `[tenant_id]`, and `[cell_id]` in /Users/deniskopylov/.codex/scratch/e02-r1-r13-http-intent-20260928/renamed-target.junit.xml@sha256:daba72e4868894223797f81e1f64a0b015e082d8d0a980ebf05f159e19827d4e. The whole recursive-gate file is 27/29 in /Users/deniskopylov/.codex/scratch/e02-r1-r13-http-intent-20260928/integrated-recursive-c090.xml@sha256:6848a66c612ef1edbb3fd0952ded252004bc5f97de9efdf8419a9828ea35ebe6; the two failures are `test_recursive_constructor_denominator_has_no_unwrapped_n9_call` and `test_task_44_public_export_denominator_is_exact`, both static-denominator checks. Their owner attribution is **UNRESOLVED** because strict P41 full-input closure is unmeasured. No Main comparison is asserted here. The source is policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py@sha256:4849284f891af20a2c59ec8986e0773c0d22c95b8231cd26b002b0325ccb3aa8; the reviewed test-only patch is /Users/deniskopylov/.codex/scratch/e02-r1-r13-http-intent-20260928/R1_REVIEWED_TEST_ONLY.patch@sha256:9003c8710dc68c401b3e9c04967ddc3031396e7c9db488930cf7006c0299656c.

**Proposed choice; remainder.** Option 1 is the proposal for Denis to consider, not a selection. Denis’s existing Option A remains selected independently. Until Denis rules on this proposal, the code/test commit is evidence that the implementation uses a narrower selector, not authority to rewrite the principal Appendix-A decision. The old and new identities are not treated as equivalent. Direct-controller parity and the positive served owner-bound N4→N5→S8 path remain `UNRUN`; full strict four-base P41 closure remains `UNRUN`; the two static-denominator failures remain owner-`UNRESOLVED`. No finding status or closure changes.

**Falsifier and revisit trigger.** The HTTP refusal witness is falsified if removing the refusal guard while retaining route/status markers leaves the test green; the recorded removal probe turns red. The preserving-control evidence is weakened if any of its three scope cases stops preserving candidate proposal work. Revisit the identity proposal if a paired HTTP/direct-controller witness establishes the same specified property, or if review shows the HTTP-only selector no longer exercises the served refusal boundary.

**Where it binds; P37/P38.** This proposal binds only the Appendix-A identity and the recursive-gate test record. It does not bind the served N4 producer, N5 computation, S8 authority, publication, or an R1 closure. The measured property is contextless HTTP refusal before N4; HTTP/direct-controller parity is not measured. A direct-controller call without the HTTP path is the divergent case.

**Pattern pass.** P04/P05/P37/P38/P41: preserve typed authority refusal; distinguish the HTTP property from the unmeasured parity claim; keep the changed test identity and incomplete P41 input closure explicit.


### R13/P31 — bounded filesystem CAS ownership advance (decision draft; 2026-09-28)

**Decision status and scope.** Draft for Denis; no principal ruling is recorded. This record describes the code snapshot at commit `d103d234cc114ef9a5b725de1d9a460b61ebeea0`, which integrates the six-path R13/P31 owner repair. The independent review gives a **bounded GO** for this first owner-wire slice, with explicit limits; it does not close R13 or establish system-wide tenant isolation. The six integrated source/test blobs are identical to the reviewed candidate blobs listed below. This engineering result is a partial custody advance, not a principal ruling, a register closure, or proof of the broader world-growth path.

**Question.** What is the bounded acceptance rule for ambient filesystem CAS ownership while keeping unique unclaimed candidate work available, and what residuals remain before a broader R13 closure claim?

**Options and costs.**

1. **Accept the existing-owner JSON repair as a bounded partial advance (recommended).** Keep the existing `ArtifactOwnershipIndex` as the ownership source, serialize its local read/modify/write transactions across instances with a persistent file lock, validate raw versioned payloads and rows before admitting an unclaimed result, cache only the validated claim-ID set per instance, enforce claims at `FileSystemCAS` operations, and normalize supplied/default raw filesystem stores at the existing Scientist `_resolve_store` seam. Preserve the historical v1/v2 bytes on reads; explicit owner mutation uses the existing v2 writer and does not constitute a bulk restamp. Cost: cold/changed lookups and tenant-scoped lookups remain O(N); each instance may hold O(N) claim IDs; full JSON rewrite mutations remain cumulative Θ(N²); no shared access lease covers a claim check through a subsequent read; raw paths, iterator snapshots, external identity issuance, and unnormalized callers remain bounded residuals.
2. **Replace the JSON owner with a transactional SQLite v3 source of truth now.** Indexed row lookup and transactions could reduce full-index scans and rewrite amplification. Cost: new persisted schema/source of truth, a controlled migration, and explicit historical replay and authority rules. No migration, reissue, restamp, or cutover is part of this integrated slice. Design comparison: `/Users/deniskopylov/.codex/scratch/e02-r13-ownership-index-design-20260928/OWNERSHIP_INDEX_TRANSACTIONAL_REPAIR.md@sha256:68e2065652658ae93a56f6153376359c382c297d4f1f3dfd275bdd232a449376`.
3. **Require resolved tenant scope for every CAS operation.** This makes the no-scope rule simple but refuses even unique unclaimed candidate work, contrary to the candidate-band direction and over-refusal rule.
4. **Keep the former bypasses.** This avoids implementation cost but leaves claimed IDs reachable without scope and lets a supplied raw store skip the Scientist owner seam. It does not satisfy custody.

**Premises and evidence.** Commit `d103d234cc114ef9a5b725de1d9a460b61ebeea0` changes exactly six paths. Integrated source/test blobs are: `policy-engine/src/polisyos/core/artifacts/ownership.py@git-blob:eee3353c0b78027712fe882b8382c7492b31aa56`; `policy-engine/src/polisyos/core/artifacts/store.py@git-blob:d0bedb5b585daf13245e22e071c6e41df47ec45c`; `policy-engine/src/polisyos/scientist/orchestration/workflows/builder.py@git-blob:d9ae16738da9e3e5193d76d8913542ad6e3546d8`; and tests `policy-engine/tests/unit/core/artifacts/test_ownership_history.py@git-blob:52f742abd703e2df70faa69756363408b0a71979`, `policy-engine/tests/unit/core/artifacts/test_artifact_id_serialization_contract.py@git-blob:bce9ada28fe409d35f91c303fa6aad67c0d8fc83`, `policy-engine/tests/unit/scientist/orchestration/workflows/test_builder_pinning.py@git-blob:6bd7401e08ae1fa7c1e57ddd07d647c79d661ebd`.

The integrated nine-file focused replay passed **122/122**, 0 failures/errors/skips: `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/integrated-nine-files.xml@sha256:3957fd27ced7a0383e5a25994a6fa4c3b099c7123070a0b93251da8bc96e289e`. The served acquisition tenant-custody file passed **3/3**, including `tests.integration.core_runtime.test_acquisition_tenant_custody::test_actual_acquisition_producers_preserve_tenant_custody_through_reentry`: `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/integrated-tenant-custody.xml@sha256:b928e9238a2227c83c457bcaeb34b5c66ddc44e2474b775d2204b37f103d817f`. Ruff and diff checks passed in the bounded independent review `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/review-50624a401/R13_P31_INDEPENDENT_REVIEW_50624a401.md@sha256:f089b28b0c1dd4dfef89ddc65508f8b8426cd26b9363a48d1e2afe646425e6ac`; that review is for the byte-identical six-path code and explicitly is not a four-base or full-system review. Its direct probe is `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/review-50624a401/view_blob_claim_probe.txt@sha256:83968795b908180c54b6ad85a75726bbd51e3254af11ebd380b9e5b7c3973fc0`.

The owner now serializes local cooperating read/modify/write operations; the claim query validates version-specific fields and rows before returning an unclaimed result; reads preserve valid historical v1/v2 bytes; explicit owner mutation is the tested v1-to-v2 transition. The sidecar uses `sha256-local-integrity`: it is not a key-backed external tenant-identity signature or an issuer for active tenant/cell identity. Active scope continues to come from runtime context. Removal evidence is split by source snapshot; no removal probes were run after integration at d103:

**Original 63b83e661 candidate probes (pre-correction; not byte-identical to the integrated six paths).** These are historical evidence for the earlier candidate only, not acceptance evidence for the corrected d103 source:

- Removing the aggregate claim guard turned the probe red (1/1): `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/candidate/probe-unscoped-owner-removed.xml@sha256:f9adf7e9fb9ea7f1b308a311c4f1189fc18fd9440be4e9047c27daa65c168658`.
- Removing the claimed-target guard turned the probe red (1/1): `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/candidate/probe-unscoped-target-removed.xml@sha256:cb68589c4f647aa31e5fb24049a040f47b59f2fc0a2676f24458419f7e144743`.
- Removing the Scientist raw-store normalizer turned the probe red (1/1): `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/candidate/probe-scientist-normalization-removed.xml@sha256:948d8492846fba406eef32c202cb168c4c2166b06513c0a239e6f247f1c020be`.
- Removing signed v1/v2 row validation turned 9/10 cases red; the remaining malformed-map case was independently rejected by a type check: `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/candidate/probe-malformed-index-validation-removed.xml@sha256:2466697ff7cbe5a3556cbb8426ae3522f19894d4307e9cadd0ab9bf066325395`.

**Corrected 50624a401 candidate probes (pre-integration; source blobs byte-identical to d103).** These receipts exercise the corrected lock, raw-v2 field validation, and cache mechanisms on the same six path blobs now integrated; they still are not post-integration runs:

- Removing the cross-instance write lock turned its deterministic probe red (1/1): `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/candidate/revision-deterministic-race-removal.xml@sha256:90c7f5a9864a7db62feda941b39235959de1076661e137f844c8bf23f6bf383d`.
- Removing raw-v2 required-field validation turned 2/2 cases red: `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/candidate/revision-removal-raw-v2-required-fields.xml@sha256:bdd32ddc606ef5e3f165e8597c4aa4c64d23f34336f81d1e11d6af201994d4b8`.
- Bypassing the validated-cache path turned its probe red (1/1): `/Users/deniskopylov/.codex/scratch/e02-r13-namespace-custody-20260928/candidate/revision-removal-validated-cache.xml@sha256:43e2ec1e2373b206d8dc8f01a6070c38540a601b9c97ee75fdc7fb07709668cb`.

The independent review classifies the integrated change as bounded, not a whole-system custody proof.

**Proposal; principal status.** Recommend option 1 as the bounded R13/P31 implementation advance while retaining SQLite v3 as a measured scaling option. Denis’s ruling remains pending. The code commit and bounded GO do not grant authority to close B12, LA-046, R13, or any register row. No R13 world-growth authorization follows from this storage decision.

**Remainder and owners.** The `ArtifactOwnershipIndex`/`FileSystemCAS` owner owns the signed-index contract and CAS checks; the Scientist workflow owner owns default/supplied store normalization at `_resolve_store`. This is one P31 class under P40: if a sibling route escapes, widen the owner mechanism or record a bounded residual and falsifier, rather than patching callers serially.

- **Raw path issuance and later OS access.** On an ambient-enforced view, `FileSystemCAS.get_paths()` checks the current owner claim and then returns ordinary `Path` objects. That check governs issuance only; later `open(path)` calls bypass CAS authorization and cannot be revoked. A direct default `FileSystemCAS(root)` with ownership enforcement off can issue a path for a claimed view. The independent probe reproduced this raw-store escape. Raw instances outside the Scientist normalization seam and any direct filesystem consumer remain outside the bounded owner route.
- **Iterator snapshot and materialization.** `iter_artifact_ids()` returns a sorted, fully materialized list. Its lazy helper takes an ambient no-scope `claimed_artifact_ids()` snapshot once when traversal reaches its first eligible manifest and filters the remainder against that set. A claim admitted after that snapshot can still be yielded later in the overlapping traversal; a subsequent ambient `get_bytes()`/`get_paths()` call rechecks and refuses. This is not a strict post-commit listing snapshot or revocable lease. Listing uses O(N) result-list memory, separate from the O(N) claim-ID snapshot/cache.
- **No shared access lease and concurrency scope.** The persistent `flock` serializes owner API mutations across instances and local processes that share the same lock-file filesystem semantics. It does not span claim check through later blob/manifest access. The verified race test is separate instances with overlapping threads, not independent OS processes, multi-host, or network-filesystem deployment; raw directory edits bypass the lock.
- **Index and cache cost.** Each claim mutation reads, validates, serializes and rewrites the full JSON index; N successive claim updates remain cumulative Θ(N²). Tenant-scoped `owners_for()` still parses the full index at O(N) per lookup. Cold/changed cache refresh is O(N), and each instance can retain O(N) claim IDs. No few-thousand-row or N/2N performance benchmark was run. An indexed transactional owner is the smallest capability if measured costs warrant SQLite v3.
- **P38 freshness proxy and local authority.** Cache freshness compares `(device, inode, size, mtime_ns, ctime_ns)` for both files rather than comparing their bytes. Owner API writes replace files atomically, but an out-of-owner in-place rewrite preserving the whole tuple is not detected. The local integrity sidecar does not establish who may write the ownership directory or authenticate a tenant identity supplied by runtime context.
- **Remaining exposure.** `ownership_evidence()` can expose global index path/digest/count metadata; owner-mismatch diagnostics may disclose tenant labels. Previously returned paths, raw filesystem access, custom stores, and raw `FileSystemCAS` consumers beyond the Scientist seam are not covered. Cloud backends have no established backend-native ownership owner. Tenant-scoped access to unclaimed historical bytes can remain refused; an absent claim does not establish public provenance.
- **Broader R13 and finding status.** Production ACQ-01/Data Forge overlay admission, passport and native-epoch qualification, post-growth WMR/context/NCM, dependent-calculation behavior, and root-rebuilt stores beyond this six-path slice remain separate work. In the current residual ledger, B12 is `partial` and classified R13; LA-046 is `partial` with a distinct compiler/profile and N7-handoff residual. Sources: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/residual_ledger.json@git-blob:bc21056d72c168b0039f65d995702c43964fb2a0#rows/B12` and `#rows/LA-046`.

**Falsifier and revisit trigger.** Keep the marker-retaining removal witnesses for the owner claim guard, claimed target/lineage checks, Scientist raw-store normalization, strict raw-v2/malformed-row validation, cross-instance lock, and cache refresh; removing each corresponding mechanism must make its property test red. Preserve the unique unclaimed no-scope candidate control and valid historical-v1 byte-replay control. The exact integrated nine-file and served tenant-custody results above are positive bounded witnesses, not substitutes for whole-file four-base P41. Reopen this bounded disposition if a claimed ID is read or mutated without its owner through an ambient-enforced route, if malformed signed state is treated as unclaimed, if valid unique candidate work is refused, if owner APIs lose a concurrent claim, or if a new production caller reaches a raw store outside the seam. If the required property expands to strict post-commit enumeration or revocation of an issued filesystem path, it needs an explicit owner-mediated handle/lease contract and behavioral witness; the current slice excludes those guarantees.

Four-base and whole-system measurements remain incomplete. The older recorded P41 matrices include two unresolved default-workflow changes from E02 base to E02 head: `test_engine_default_workflow_e1_7.py::test_engine_default_workflow_e1_7` and `test_engine_default_workflow_p8.py::test_engine_default_workflow_p8_wires_bindings_and_pre_sim_gate` are `PASS_TO_FAIL`, `owner_attribution=UNRESOLVED`, `case_input_equivalence=BODY_SAME_INPUT_CLOSURE_UNMEASURED`. At the integration snapshot recorded in that same matrix they were `OTHER_OUTCOME_CHANGE` (failed to passed), still unresolved; that older comparison is not a replay at d103. `test_ownership_history.py` is absent at 781878, 00d946 and 5fd3, so those cells are N/A; the recorded four-base `test_workflow_tracing.py` cells are all skipped and therefore UNRUN. The R13 integration did not rerun four-base P41, architecture guardrails, an independent-process/multi-host test, or a performance benchmark. Sources: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T163157Z-83283/results.json@sha256:09c4c28380c4a4878b0f3738204f5579a26b7f5024b6aea95210c479fdb8f8be` and `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T164030Z-86453/results.json@sha256:d62f6a797cd17a71800e4552c938d1ad28252ce5cf3fe250e4e9defa6991b3d5`.

**Where it binds; P37/P38.** This draft binds only the filesystem ownership-index owner, `FileSystemCAS` enforcement surface, and Scientist store-normalization seam for the covered ambient and tenant-scoped operations. P37: index schema/signature/claim rows are recomputed from the local integrity pair; active tenant/cell identity is runtime-supplied and its external issuer/authentication is not established. The file-identity tuple is only a cache-freshness predicate, not byte identity. P38: property is that unscoped ambient operations do not consume current known tenant claims while unique unclaimed candidate work remains usable. The implementation checks against a validated claim snapshot, but returns a raw path after that check and enumerates from one claim-set snapshot; a later OS read or claim admitted mid-traversal can outlive the check. A direct default `FileSystemCAS` with enforcement off is the concrete divergent caller. Those divergences are named residuals, not evidence of full custody.

**Pattern pass.** P05/P27/P31/P32/P35/P37/P38/P40/P41: reuse one owner; validate claim substance before an unclaimed classification; keep candidate-band work usable; enumerate the tested denominator; distinguish a local integrity sidecar from an external identity signature; disclose path and listing proxies; stop at this bounded owner slice; and retain the unresolved P41 cells.

### R1 — purpose-limited job scope for worker context replay (decision draft; 2026-09-28)

**Status and binding seam.** Draft for Denis and the architecture owner; no owner appointment or principal ruling is recorded. This refines the already-selected R1 Option A controlled N4→N5 engineering runway. `VerifiedJobScope` is a proposed purpose-limited contract name, not an existing type, artifact, or standalone owner. This draft does not reopen candidate-band access or decide S8 authority.

**Question.** After the existing NL job-execution owner has revalidated the persisted authorization/intent receipt and the control store has verified the live `(job, worker, attempt)` lease, what scope may the worker use to persist and replay a candidate-only `CycleSubstrateContext` for that job?

**Options and costs.**

1. **Derive a purpose-limited `VerifiedJobScope` from existing owners (proposed engineering direction).** Recompute it from the persisted NL binding and current lease for each worker execution/replay. Limit it to the exact job, run, lease attempt, tenant/cell, and candidate-context persist/resolve purpose. It conveys no general user roles, PII entitlement, protected-action permission, or S8 authority. Cost: a typed owner contract and a single worker-to-context-owner bridge with receipt/lease mutation tests. It avoids propagating request state and does not add a competing scope issuer.
2. **Persist and rehydrate the original request `AccessScope`.** This preserves a direct actor lineage, but turns request-local roles, PII/MFA and token/delegation facts into asynchronous job authority. Cost: a security owner must define durable custody, expiry/revocation, delegation and privilege changes; stale authority could outlive the request. This is not needed to establish the narrower candidate-context operation.
3. **Keep worker context persistence unavailable until a scope owner contract is approved.** Continue the candidate-only N4 proposal path with `cycle_substrate_context_unavailable`/typed limitation. This is the lowest implementation cost and preserves ordinary candidate work, but it leaves the controlled served N4→N5 owner-bound context path unavailable.

**Premises.** The request `AccessScope` is held in request-local `ContextVar` state; `_job_tenant_scope` sets tenant/cell but does not reinstall that request scope. The persisted NL execution-intent owner already reconciles job, actor, authorization receipt, payload, event and outbox; `ControlPlaneStore.current_execution_job_record()` re-reads and checks the active job/worker/attempt lease. `CycleSubstrateContextArtifactOwner` instead gates on current request `AccessScope`, producing the focused failure `cycle_substrate_context_job_authenticated_scope_not_established` in `test_served_simulate_only_replays_admitted_fixture_context_into_n5`. Evidence: `run_lifecycle.py@git-blob:c6056b5834f04725827d09a4cabb65c4af20074e`; `control_plane_store.py@git-blob:d4b2f0ca048160e9d0c97b8f205c167cded306ca`; `tenant_context.py@git-blob:e91c6822386f34d1a91bde49098d7ddf40326819`; `cycle_substrate.py@git-blob:666dd063cea0c8218c9a4430b8b5ad0d2658267d`; focused result `/Users/deniskopylov/.codex/scratch/e02-r1-positive-bridge-map-20260928/r1-positive-64583b314/pytest.log@sha256:6a8372ec23de963f99e43ebb55f7f2f7b2e4a440481c651eae6f5705f1aec4e5` at candidate commit `64583b31447934f475fb3635df86f71c803bb7e1`.

**Proposed choice and decision-maker status.** Advance option 1 for the controlled-profile candidate path through the existing NL job-execution owner and context owner. The architecture/security owner must confirm the exact purpose and receipt/lease binding. Whether the scope must retain original-principal lineage or may be a delegated service execution, and what authorization freshness/revocation rule applies beyond the live job lease, remain undecided. The proposal grants no user-level or protected authority while those questions are open.

**Remainder.** A successful candidate-scope handoff establishes only the job-bound context persistence/replay seam. It does not establish source-time coverage for the five real DataState inputs, profile/current-epoch admission, signed-value trust, S8, publication, or external principal/delegation validity. B01–B03 statuses and the 56/282 selected/total ledger counts do not change; no new ledger row is proposed.

**Falsifier and revisit trigger.** The closure witness is a served request→persisted receipt/event/outbox→live lease verification→derived job scope→same-store context persist→context resolve→actual N5 consumption path. Keep markers but remove/change receipt binding, lease identity/currentness, tenant/cell, job/run, or allowed purpose: the positive must fail. A scope that permits another job or operation falsifies the contract. A separate control must preserve ordinary N4 candidate work with typed limitation when the job scope is absent. Revisit if the existing NL job owner cannot replay the exact receipt, or if lease verification cannot be bound to the context owner operation without introducing a second issuer.

**Where it binds; P37/P38.** The seam is the existing HTTP/NL job owner→worker lease→`CycleSubstrateContextArtifactOwner`→N5 candidate path. P37 predicates are the recomputed persisted receipt binding and control-store verified live lease; principal/delegation lineage and authorization currentness beyond the lease remain `not_established`. The current implementation's `_current_job_scope` tests presence of a request-local `AccessScope`; the desired property is a purpose-limited job operation after receipt+lease verification. A worker with verified persisted job evidence and a live matching lease but no request-local ContextVar is the divergent case. The gate's current refusal is not evidence that the request `AccessScope` should be serialized. This draft does not bind real-data source temporal scope, S8, publication, or any debt-register closure.

### R13/P31 — Core-owned internal artifacts facade for epoch store construction (decision draft; provisional implementation integrated 2026-09-28)

**Decision status.** Draft for Denis; no principal ruling or Core/architecture owner disposition is recorded. This decision draft proposes the unlisted `polisyos.core.artifacts` facade as an internal Core seam. It deliberately departs from `R13_CORE_ARTIFACT_FACADE_DECISION.md@sha256:7a3a2ea09dba401b0113d3d44e2fda504711778a08b9f102a48cb27f6603809c`, whose preferred option was public supported-entrypoint promotion; the V2 review also preferred two exports from the stable `polisyos.core` root. This draft proposes the narrower internal route because no real external consumer has been demonstrated. The implementation has already been integrated provisionally in code span `25916581c270114faa044a38ba69e9e66b111d62..3ec377af6f0be281f0e5ad6ec080a859fead9105`, under the task’s typed limitation. That is engineering progress, not Denis’s ruling, public-surface admission, authority grant, or closure of R13, B12, or LA-046. The independent candidate review is bounded GO only for this epoch-store slice.

**Question.** How should `runtime.quality.epoch_deployment` reach Core’s existing `ArtifactStoreConfig` and `build_artifact_store` without depending on backend internals, rebuilding a CAS from a root path, or making an ABI promise wider than this internal consumer needs?

**Options and costs.**

1. **Use the two exports on `polisyos.core.artifacts` as an internal Core-owner API (provisionally implemented).** The facade exports `ArtifactStoreConfig` and `build_artifact_store`; `epoch_deployment` constructs fallback storage through that owner and routes reads through its runtime-store repository seam. The chronology persistence owner binds both proof-store and policy-store factories to the same runtime-supplied accessor. Keep `polisyos.core.artifacts` unlisted in `architecture/public_surface/contract.toml`; do not classify these two names as public stable or add a public inventory/release promise. Cost: this internal cross-root seam still needs team-Core disposition and an exact-head architecture-guardrail pass after the current red findings are resolved or explicitly owned. Contract/internal-by-default gives no public compatibility promise, so these exports remain owner-controlled.
2. **Inject the runtime-supplied `ArtifactStore`/accessor into every configured epoch construction path.** This adds no import seam and maximizes explicit custody. Cost: census and rewire every config-only caller; any caller without a supplied store must retain a typed limited/unavailable result. It can remove the factory dependency only if the complete served caller set proves injection is available.
3. **Add the two names to the already-supported `polisyos.core` public-stable root.** This remains a future alternative only if a real external consumer establishes a public need. Cost: those exact names acquire the two-minor-release deprecation promise, and the Core-root inventory/reference must be regenerated and reviewed through the owner command with an additive public-API release fragment.
4. **Promote `polisyos.core.artifacts` as a public-stable supported entrypoint.** This is not a narrow alternative: the inventory generator includes the entire facade `__all__`, not a two-name allowlist, and the full set takes on stable removal obligations. Cost: broad ABI review, inventory/reference regeneration, and ongoing compatibility maintenance.
5. **Defer or inject a typed limitation until the owner seam is accepted.** This remains the fallback if Core rejects the internal seam or complete edge attribution establishes that this seam violates the import contract. Cost: configured epoch evidence reads remain limited where no runtime store is injected.

**Premises and evidence.** Core already owns the configuration/factory in `core/artifacts/backends/config.py`; rebuilding `FileSystemCAS(root)` would bypass the runtime-supplied, possibly guarded store and violate P27/P31. Static source inspection shows the factory imports protocol/observability types only under `TYPE_CHECKING` and imports concrete store implementations inside factory branches, so the facade re-export has no evident eager cycle. The runtime facade identity test now passes in the integrated whole-file run. The R13 candidate’s bounded independent review, `REVIEW-95b747f6f.md@sha256:d11100becd56d76b305359b5de6a065013c55c89e196376ffac2c5a2cfeee2fd`, found the same internal seam and gave GO for the epoch-store slice; its six R13 source/test blobs are byte-identical to the six current blobs cited below.

The public-surface contract lists `polisyos.core` and selected sibling entrypoints but omits `polisyos.core.artifacts`; its rule says unlisted module paths are internal by default. Conversely, `core/artifacts/README.md` has a “Public API” section and the `artifacts/__init__.py` module docstring says “Publish the stable CAS artifact ABI.” `core/README.md` lists artifacts as a lazy subpackage while naming only `polisyos.core` as the supported package entrypoint. These statements conflict in scope and wording; none is authority to silently admit the whole facade or to claim a selective public export. Record the inconsistency as OP-ARCH-ABI / a register proposal for owner reconciliation. Exact-head architecture guardrails ran as the sole command at pinned source/test HEAD `3ec377af6f0be281f0e5ad6ec080a859fead9105` and exited 1. The gate reports 3 failure classes / 111 detailed diagnostics: a deep-import aggregate with 108 added-edge diagnostics, plus mismatches in two generated families. Across all 2,696 tracked Python source files, current edge set was 3,410 against a 3,330-edge baseline: 108 additions (107 pre-existing E02/merge drift plus one later edge), 28 removed baseline rows, net +80. The five R13 epoch-store commits `25916581c..3ec377af6` added zero deep-import edges; in particular, `epoch_deployment` added zero warning edges. The flagged `chronology_proof -> core.artifacts._manifest_lifecycle` edge already appeared in the prior exact capture. The one new edge since that capture is `scientist.orchestration.workflows.builder -> core.artifacts.ownership`; exact source blame and prior/current snapshots show it was introduced at `d103d234cc` (`fix(R13): fence cross-instance tenant claims and guarded CAS access`), is absent at prior exact HEAD `e0c6623`, and is present at `d103` and captured `3ec`. `e55012e22` precedes `d103` and changed the builder's backend factory / ambient enforcement, not this ownership import. Prior edge attribution is bounded to the 107 unchanged added edges (82 E02-source + 25 merge-composition) and 28 unchanged baseline removals, plus this source-blamed `d103` edge; no same-command four-base replay was run.

The generated-family denominator was four completed required families: runtime API client (3 outputs) and dashboard API types (1 output) are clean; runtime OpenAPI snapshot and trust-claim posture mismatch. At the pinned 3ec guardrail capture, the registered OpenAPI owner export had not been run, so expected owner-output bytes were UNRUN then. A later registered-owner replay at source/test HEAD `eb17337503d99a09964f8e15cf2beb12a28d6a77` ran twice to separate scratch outputs; both invocations exited 0 and produced byte-identical 2,810,328-byte files (SHA-256 `4dd7115efbc122a89b7b75e51ebe60b1755f42297bd57d37625afd12ef850845`). Against tracked snapshot `policy-engine/schemas/runtime_api_v1.openapi.json@git-blob:fb15057e33e839e3c50b813b4f274733d640d9b9`, the owner output differs at exactly 10 JSON leaves, all in the existing default response example for `GET /api/v1/exports/governed-projections/confidence-ledger-risk-spend`; the complete 111 path and 572 component-schema sets are identical. Diagnosis `/Users/deniskopylov/.codex/scratch/e02-r2-openapi-eb1733750-20260928/OPENAPI_OWNER_DIAGNOSIS.md@sha256:a01f32e0d0000400d5539a929ba1451e5f0a4f5494c56880f5f8e50f69b14bf1` and complete leaf delta `/Users/deniskopylov/.codex/scratch/e02-r2-openapi-eb1733750-20260928/openapi-owner-delta.json@sha256:950790ca6c9d5e8f6f2477c4153ffe8a5ec3f28ba21f247376e3bfc06ad9e228` establish repeatable bytes at eb and a measured snapshot-value mismatch. They do not establish the cause, authorize regeneration/reissue, or update the 3ec gate verdict. The Main comparison is context only. For trust posture, read-only reconciliation found 149/149 listed source members present, 24 content digests changed, 0 missing; expected current projection bytes and complete current-source discovery remain UNRUN. `team-architecture` owns the content-bound trust artifact approval/reissue; never restamp it to clear a gate. The standalone Atlas status-retirement gate is outside this command and has no verdict. Raw output `/Users/deniskopylov/.codex/scratch/e02-r2-guardrails-3ec-20260928/guardrails.out@sha256:7e8e1c5a76626e72e8656cd4697cf3b29e5c9e2ff8fe85d2e4eeb9c3bf1f3db5`; corrected complete triage `/Users/deniskopylov/.codex/scratch/e02-r2-guardrails-3ec-20260928/ARCHITECTURE_GUARDRAILS_3EC_TRIAGE.md@sha256:12098c8e523c3f480f853a9cd1d5eaebfcf9540487c3403c1909249a40519017`.

This V9 patch is based on source/test HEAD `8177440fdc3b86bffa479b7b8bfe1729bf968484`; exact-head architecture guardrails were not run at that snapshot (`UNRUN`). The 3ec census and later eb OpenAPI owner replay are time-pinned measurements; no newer gate result is inferred. No public ABI approval, gate pass, or full R13 closure is inferred.

**Current integrated source/test blobs.** The R13 seam source/test blobs at `3ec377af6f0be281f0e5ad6ec080a859fead9105` are:
- `policy-engine/src/polisyos/core/artifacts/backends/config.py@git-blob:93c144f77b44c9e9300d7479b7f5b8c86e766345`
- `policy-engine/src/polisyos/core/artifacts/__init__.py@git-blob:1140ecc434355ba298f087b90e2bfccd27032d85`
- `policy-engine/src/polisyos/runtime/quality/chronology_proof.py@git-blob:12d6a4e1bb5cccf2d8fbe578b5a3478b3ee457ac`
- `policy-engine/src/polisyos/runtime/quality/epoch_deployment.py@git-blob:83e6031f4ae0d74b48ee64c4deb75f15d0d753c0`
- `policy-engine/tests/unit/core/artifacts/test_artifact_store_protocol.py@git-blob:5fd89eb563912ca6fc9f60600bffd47a2231b606`
- `policy-engine/tests/unit/runtime/quality/test_epoch_deployment.py@git-blob:bcfc619bd454cc1bf6499fb696839de020d7d43f`
- `policy-engine/tests/unit/runtime/quality/test_semantic_epoch_native_qualification.py@git-blob:875e4eeb6d934e8827f3136f52893ac279d91164`
- `policy-engine/src/polisyos/core/artifacts/README.md@git-blob:7b4cc0bb5ae7dd9c4602fcf1b6ff1186881bfc4c`
- `policy-engine/src/polisyos/core/README.md@git-blob:f73553622adc93767c1eea46dfef753b99328254`
- `policy-engine/architecture/public_surface/contract.toml@git-blob:d568a925f1cf055e517f5a5e0d691d4c6390a0a5`
The R13 slice’s own changes do not add this facade to supported entrypoints; unrelated public-surface edits elsewhere on the branch are outside this decision.

**Bounded integrated behavior and strict P41 evidence.** The strict four-ref whole-file replay covered three complete touched test files × four pinned revisions (12 cells): 8 PASS, 4 Git-MISSING, 0 present-cell UNRUN. The four missing cells are `test_epoch_deployment.py` and `test_semantic_epoch_native_qualification.py` at execution base `78187878e` and E02 head `00d946c2b`; those files are absent at those refs, so they provide no historical result. Main/current were 24/24→27/27, 5/5→6/6, and 8/8→9/9. Across common Main/current identities there are zero pass→fail outcomes; the two selected Appendix B epoch identities also pass at both refs. Current exact JUnits: epoch `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T202903Z-70617/cells/integration_head/test_epoch_deployment-c7b5eca4827b.junit.xml@sha256:577d06a4bd191deedae35b57792108e8573661a06213e977c175c3c1e55869c4`; native qualification `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T202903Z-70617/cells/integration_head/test_semantic_epoch_native_qualification-af2c76290290.junit.xml@sha256:9e04c95221ede5305320bb771fde6704ca7b70c14f3c0db374db1f37021400c0`; artifact protocol `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T202903Z-70617/cells/integration_head/test_artifact_store_protocol-1db51de3f63f.junit.xml@sha256:ae165250cb5487ce7158b3640bf3d9808799a2e49169708eea5a6eaca469b5f7`, all under `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T202903Z-70617/`. Manifest `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T202903Z-70617/results.json@sha256:6a1c166411082b4aebf55240f8bbe3ae2f176a795fd1261cc1d6af91b60afc20`; broker memo `/Users/deniskopylov/.codex/scratch/e02-r2-baselines/p41-r13-p31-three-files-20260928T202903Z.md@sha256:3bb85666b136da9d494f378bdb267cd0bad4b358f90bcae64586b59c1e3cd3f5`. An earlier 5/5 focused-selector and 42/42 whole-file receipt is supplementary only and is not counted as strict P41 because it is absent from the broker’s manifest census. No result is inferred for the four missing cells, and this does not establish full R13 closure.

The two marker-retaining candidate removal probes in the independent review are pre-integration receipts, but the reviewed source/test blobs are byte-identical to current `3ec` blobs above: removing `_repository()` runtime routing made the signed-evidence denial selector red (1/1): `/Users/deniskopylov/.codex/scratch/e02-r13-owner-store-candidate-262a85a7/signed-repository-removal.junit.xml@sha256:1c827a12d853c20cd6738445207c1f4fde759612f7b37b18fd1e464ffe2d9e26`; restoring `_policy_store_factory` to `state.store` made the native-policy owner witnesses red (2/2): `/Users/deniskopylov/.codex/scratch/e02-r13-owner-store-candidate-262a85a7/policy-store-removal.junit.xml@sha256:219eb18af7bcbe7cbfb4c3ac85b54680aaece171f140e5373a7ed988b4c87430`. The review also has a signed-read positive control and an allowed profile/native qualification control. These probes establish this owner-store property only; they are not new post-integration mutation runs.

**Actual bounded code/test write set.** The integrated six-file R13 seam comprises `core/artifacts/__init__.py` (facade exports), `runtime/quality/epoch_deployment.py` (fallback factory and signed-read route), `runtime/quality/chronology_proof.py` (same runtime-store accessor for proof and policy stores), and tests `tests/unit/core/artifacts/test_artifact_store_protocol.py`, `tests/unit/runtime/quality/test_epoch_deployment.py`, `tests/unit/runtime/quality/test_semantic_epoch_native_qualification.py`. The internal choice adds no R13 public-surface contract/inventory/release-fragment change; unrelated branch changes are outside this decision. If an internal release note is separately required, classify it as internal and do not set `public_surface_inventory_reviewed=true`. A later public-root option has a separate write set: `architecture/public_surface/contract.toml`, owner-generated `architecture/public_surface/inventory.json` and `docs/reference/public-surface.md`, plus a public-stable release fragment; do not apply those for this internal seam.

**Property, controls, and P38 boundary.** The bounded property is: under composition, all selected epoch signed-evidence and chronology policy/proof reads or writes use the exact runtime `ArtifactStore` object supplied by the caller; a denied read through that store refuses while identical bytes remain reachable by a separate raw-root peer. Positive controls are included in the 5/5 and 42/42 runs. The facade identity test is an owner/import witness, not custody proof. R13 review notes that `composition_scope()` checks matching configured backing roots, but root equality alone does not establish tenant identity: the runtime caller must supply the tenant-bound guarded store. A raw same-root store is the concrete divergent case and remains outside this proof.

**Proposed choice and status.** Recommend retaining option 1 as the provisional internal engineering route while the principal ABI question and Core/architecture owner disposition remain pending. Denis has not ratified this draft. The integrated code may continue serving the bounded epoch-store path under its declared scope limitations, but it does not authorize a public compatibility claim, broaden authority, or close B12/LA-046/R13. Do not widen import exceptions, modify `supported_entrypoints`, regenerate inventory for this seam, or resolve contradictory documentation by assumption. If the exact-head guardrail rejects the internal facade import or Core declines to own the exports, use runtime injection or retain the typed limitation; do not add an architectural exception to force a green gate.

**Remainder and owners.** Core owns the artifacts facade and factory; team-architecture owns public-surface classification and generated inventory. Runtime-quality owns the epoch caller and its read chokepoint. The README/module wording versus public-surface contract discrepancy remains open; propose owner reconciliation for the register, whose changes the architect lands. The caller’s tenant authorization remains externally supplied; matching roots do not prove it. A separate 2,696/2,696 Python AST census found the original five direct `FileSystemCAS` constructor sites absent from the three named R13 modules (`rg 'FileSystemCAS('` returns zero there); the remaining `generation_cycle` root builder is contract-testing-only while the served bridge supplies the runtime store. This proves only the bounded constructor-site direction. It does not prove the full owner-custody/world-growth chain. Residuals remain: raw `get_paths` outside the enforced seam; iterator claim-set snapshot without a read lease through the subsequent blob read; `stat` identity used as a byte-equality proxy; full-index JSON rewrites with O(N²) cumulative cost; and the root/ACQ-01 route not shown entering through the single overlay-admission, passport, and native-epoch chain. Census receipt `/Users/deniskopylov/.codex/scratch/e02-r13-root-store-census-20260928/receipt.md@sha256:9c4d6163ddf99c442d99049cffeb2577bef99261c8a083a24f7fd8c2d144b416`; tracked report `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/FINAL_REPORT.md@git-blob:b7b59cd6888e10c6389907a9a0c3b20d64aca9ac`. This decision does not establish S8 authority or any finding-level closure.

**Falsifier and revisit trigger.** The pinned 3ec exact-head guardrail exited 1; the patch-base source/test HEAD `8177440fdc3b86bffa479b7b8bfe1729bf968484` has no exact-head gate result recorded (`UNRUN`) and must not be represented as acceptance. The OpenAPI owner replay at eb measured the 10-leaf snapshot mismatch; its cause and any authorized reissue remain not_established. Reopen option 1 if complete attribution shows the internal facade route causes a prohibited edge, Core declines to own it, an owner read/write bypasses the bound accessor, the denied-store tests pass after removing the routing, or a same-root raw store is mistaken for tenant authorization. The chronology private edge and trust-posture mismatch remain unresolved; the OpenAPI output mismatch is measured at eb but cause/reissue disposition remains open. Obtain a fresh exact-head gate and owner disposition before calling generated-family status clear. Revisit option 2 when a complete call-site census shows every configured epoch builder receives the runtime-owned store and the factory path can be removed without behavior loss. Upgrade to option 3 only when the complete caller census names a real external consumer whose need cannot be met by internal composition; add only the two root names, then regenerate/review the public inventory and release fragment. Promote the whole artifacts facade only with an explicit owner decision covering every `__all__` name.

**Where it binds; P37/P38.** Binds the Core-internal artifacts facade, the epoch-deployment construction seam, and chronology/epoch runtime-store accessors. P37: selection of the owner-bound store object is recomputed at the accessor; tenant identity and authority are supplied by the runtime caller and remain `not_established` by root equality alone; public-stable admission is `not_established` and is not a gate this proposal opens. P38: the implementation property is exact supplied-store use on the actual reads/writes. An import marker, successful raw-root read, facade identity test, or public inventory entry is a proxy and cannot prove custody. Divergent case: the correct factory is re-exported while an epoch repository bypasses the guarded runtime store, or a raw same-root store is supplied and mistaken for tenant authority. P27/P31 require the existing Core owner and runtime repository chokepoints, not a parallel constructor or caller-by-caller patch.

### R1 — bounded purpose-limited NL worker scope and updated evidence (decision draft; 2026-09-29)

**Status and binding seam.** Denis selected R1 Option A and the controlled-profile N4→N5 engineering slice. The integrated `VerifiedNLJobScope` bridge received independent bounded GO at `77bfcdb36` + `eb1733750`; the result is evidence for one candidate-band worker seam, not an owner appointment, S8 ruling, source-time contract, or full B01–B03 closure. This addendum supersedes the earlier proposed `VerifiedJobScope` name and the focused-failure-only status. No ledger status/count changes are proposed.

**Question.** Once the existing NL execution owner has replayed the persisted job binding and the control store has verified the current `(job, worker, attempt)` lease, what scope may the worker pass to the cycle-context owner for candidate N5 computation, and what principal/delegation and revocation facts must that scope preserve?

**Options and costs.**

1. **Retain the implemented `VerifiedNLJobScope` for this candidate-only operation.** Derive it from reconciled persisted intent/authorization evidence and the live lease; bind exact job/run/tenant/cell/attempt and `cycle_input_candidate_only` purpose. This keeps the existing NL and context owners, enables controlled candidate N5, and costs internal bridge maintenance plus mutation/removal tests. It does not settle actor-versus-service lineage or freshness/revocation beyond the checked lease.
2. **Persist and rehydrate request `AccessScope`.** This retains request authority fields but makes roles, PII/MFA, delegation, expiry and revocation durable across an asynchronous job. It requires a security owner and additional custody/currentness machinery; that broader authority is not needed for candidate context replay.
3. **Keep worker context replay unavailable until all lineage/freshness questions are decided.** This preserves ordinary N4 candidate proposals and typed limitations but discards a bounded N5 bridge already exercised with a controlled fixture.
4. **Synthesize scope from payload or marker fields. Rejected.** A tenant/cell, actor/role, authorization-receipt marker, event/outbox field, permission snapshot, or digest does not issue a scope. This would turn identity-shaped declarations into authority.

**Premises and evidence.** The NL execution owner reconciles persisted job, event/outbox, capability manifest, actor, authorization receipt and intent digest (`run_lifecycle.py@git-blob:be50a2752d210d299a4a9c92ca424f5888da8b28`); the control store re-reads current lease against the handler fence (`control_plane_store.py@git-blob:d4b2f0ca048160e9d0c97b8f205c167cded306ca`); the cycle-context owner rechecks purpose/binding and persists/resolves through the runtime-supplied store (`cycle_substrate.py@git-blob:cac954ad97017b62ec98ac5f1b853e14bb8eda87`). Focused 5/5, shared-owner 3/3, marker-retaining removal-red, and bounded independent review are cited in `OPEN_PREMISES.md` §§OP-R1-CONTEXT/WORKER-SCOPE. Whole-file P41 there is complete for the measured `eb173` test blob only; all case-diff ownership remains unresolved. The subsequent direct R11 JUnit and incomplete 16-cell bed P41 are cited in OP-R1-CONTEXT; the latter uses test blob `5603d312…` but predates the `builder.py` change now in the 5f/838 source tree. The four-file R1 importer migration set still lacks a complete exact-current whole-file four-base replay. The positive uses fixture profile/WMR/context and is not an ASGI or production DataState profile witness.

**Proposed bounded choice and owner status.** Retain option 1 for the exact controlled-profile candidate operation. The actor/delegation lineage and authorization revocation/currentness beyond a live lease remain owner questions. The responsible security/authority owner is not appointed by this record; if the unresolved semantics are required to permit even this candidate operation, the owner must decide that before widening scope. No scope is inferred from user-supplied markers.

**Remainder.** The bridge grants no production profile admission, real-data temporal validity, N9, S8, signed-value, promotion, publication, or acquisition authority. Five-input DataState source time, production profile-owner wiring, S8 signer/current epoch, principal/delegation lineage, and revocation beyond the lease remain unresolved. B01–B03 stay partial; denominator stays 282/282, selected blocker set 56/282. Whole-file P41 for `test_control_service_di.py` measured execution/Main 30/30, E02 28/31, and integration `eb173` 35/41; 48 case-diff attributions are all `UNRESOLVED`. `be857b3c9ceb048b9a0fb491ad3ef475620557f3` adds a focused R11 control; direct JUnit `/Users/deniskopylov/.codex/scratch/e02-r13-r11-stop-control-test-patch-20260929/integrated-R11-target.xml@sha256:38b0a598b7158889a536c570d525016f8fc0baec5d70a4ffbfca98a604a7c23a` is 1/1 with zero failures/errors (it postdates the earlier pre-run `UNRUN` receipt). The partial P41 manifest at `bed508646` (`raw/p41-custom-20260928T213314Z-92507/results.json@sha256:da21734cb758da1dc5d97be2431b3e3411277d899733251efa59c2510511a2b9`) has 16 cells: 5 `PASS`, 1 E02-worker `UNRUN` after process-group `killpg` raised `EPERM`, 8 scheduler-paused `UNRUN`, and 2 Git-`MISSING`; 13 pair comparisons are `UNRUN` and 3 `MISSING`, with no pass→fail attribution from incomplete pairs. It pins the control-service test blob `5603d312b7bb4ecaa3f66c9b3e486fa116becaa5` at source/test head `bed508646`. Code head `5f433df89` retains that test blob but changes `builder.py` from `d9ae1673…` at bed to `52de4ccb…`; docs head `838915079` adds documentation on that later source tree. Thus no complete exact-current whole-file replay exists; the four-file R1 importer migration set still lacks complete four-base replay. The receipt's differing outcomes are not assigned to this R1 bridge or the later R11 test change.

**Closure signal, falsifier and revisit trigger.** Preserve the positive path from replayed job/authorization receipt through current lease, issued purpose-limited scope, same-store context persist/resolve and actual N5. Keep markers while removing the resolver handoff; the positive must turn red. A forged scope with matching job/tenant/cell/worker/attempt/actor/route markers, stale lease, foreign job/context, changed purpose, or missing persisted receipt must refuse. The no-owner ordinary N4 candidate control must continue with a typed limitation. Revisit if the scope reaches another operation, the live lease can change between verification and use, or fixture/unknown-time evidence is used for a production-current or S8 claim.

**Where it binds; P37/P38.** The seam is authenticated NL `simulate_only` execution-owner → control-store lease → cycle-context owner → N5. P37: persisted intent-digest equality is `recomputed`; agreement among job, payload, event/outbox, capability, actor and authorization-receipt fields plus the current `(job, worker, attempt)` lease is `independently_reconciled`. `VerifiedNLJobScope` purpose fields are `recomputed` after those checks. The context owner reconciles private issuance and exact job/run/tenant/cell/problem/slot/purpose against persisted state (`independently_reconciled`); context artifact bytes/integrity/content binding are `recomputed`. Fixture profile/WMR/context are `consumer_asserted`; N5 invocation/result is `recomputed` for those fixture inputs. Production profile, source-time scope, S8 signer/epoch, signed-value validity, lineage and revocation beyond the lease are `not_established`. The private sentinel is process-local, and no authority claim relies on a consumer-asserted or not-established predicate. P38: the former implementation used request-local `AccessScope` presence as a proxy for worker authority; the bounded implementation tests reconciled job evidence plus current lease and exact-purpose scope. A real production profile owner/current source-time contract is still absent, so a fixture can run actual N5 while real-data admissibility remains unestablished. This draft does not bind authority, publication, or a register closure.

### R13 — observation period versus publisher update/as-of time (decision draft; 2026-09-29)

**Status.** Proposed choice for principal review; not adopted and not a finding closure. B12/R13 remains partial, LA-046 remains separate, and the 282-row ledger is unchanged.

**Question.** What may candidate N8 infer about the freshness or vintage of a WDI panel assembled from admitted observations?

**Options and costs.**

1. **Preserve candidate N8 panel shape and carry `source_update_time_not_established` (recommended).** Keep observation-period selection as implemented and expose the missing source-update premise as a limitation. This allows useful candidate computation now; cost: no claim that the selected bytes are the publisher's current/as-of vintage until a source record is admitted.
2. **Refuse candidate N8 panel work until source-update semantics are supplied.** This avoids any chance of a consumer reading panel shape as freshness, but over-refuses computation whose output can remain explicitly candidate and limited.
3. **Infer update/as-of semantics from the row year, local retrieval time, `source_watermark`, or `dataset_version` (rejected).** This appears to avoid a new source contract, but conflates observation period, retrieval/content identity, and publisher vintage; it could make a stale response look current.

**Premises.** In `acquisition_executor.py`, the WDI `date` is checked against the requested observation-year window. The passport binds `source_watermark` to raw response bytes and `dataset_version` to the live normalized-result digest; `overlay.py` rechecks those bytes and stores `year`/`survey_year`/`wave`. `LiveSourceExecutionEvidence` binds request and raw-response content but does not encode publisher update/as-of semantics. These are content and observation-period checks, not a publisher vintage record (`policy-engine/src/polisyos/runtime/quality/acquisition_executor.py@git-blob:399fc8d459ebb71169ded1da375e59c9dc24ecea`; `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/overlay.py@git-blob:f59a731f7937f45ff5c56116e94903c1fe3bf358`; `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py@git-blob:fdbbc9f0ab4aaf9c7ffd388f5512e8307aa76260`). The reviewed 04fe projection candidate is not integrated and is evidence only for a proposed typed source-time limitation (`/Users/deniskopylov/.codex/scratch/e02-r13-exact-projection-candidate-20260928/R13_ACTIVE_OBSERVATION_PROJECTION_CANDIDATE.md@sha256:8222a875ecbe7405ba13df238261d6302c54f93395a8c63a9777061156bdefd6`; review `/Users/deniskopylov/.codex/scratch/e02-r13-design-review-20260929/R13_SLICE_A_REVIEW.md@sha256:bfa9b09d9d1cd0f47bf27989ea68c30f032a0f210dcf164d0e0e38ba8c4cc182`).

**Proposed choice.** Select option 1 for candidate N8. Preserve the source-updated/as-of limitation as typed state; do not turn it into a global N8 refusal or infer it from a neighboring field.

**Remainder, owner, and revisit trigger.** The missing `data_record` is source-issued update/publication/as-of/version semantics bound by Data Forge to the selected response digest, passport, and epoch. The Data Forge acquisition/overlay owner owns typed admission; the publisher or authorized source custodian supplies the semantics. A specific source-side issuer/record is not established. Revisit before any freshness/currentness, S8, publication, or other authority claim depends on this data, or if currentness begins changing panel selection. Falsifier: keep observation year, response digest, passport/epoch, and status markers fixed while removing, staling, or substituting the source-issued vintage assertion; if the consumer still reports currentness, reopen this slice. If no source semantics are supplied, retain the limitation.

**Safe engineering now.** Candidate N8 panel-shape computation may proceed with `source_update_time_not_established`; other independent candidate and typed-verifier work remains available. OP-R1-TIME's five-input DataState semantics and R13's selected-row-to-WMR/N5 bridge remain separate premises. A versioned Foundry receipt/context is required only if this temporal fact is later persisted and influences candidate selection or authority; it is not a prerequisite for the bounded candidate computation.

**Where it binds; P37/P38.** This draft binds only source-vintage/currentness interpretation for the B12/R13 WDI candidate panel, with LA-046 kept separate. It does not grant source-currentness, S8, publication, or authority, and does not close the R13 row-to-WMR/N5 bridge. The gate predicate must resolve a source-issued update/as-of record and bind it to selected bytes and epoch (`not_established` until supplied); a matching digest or observation year alone is not the predicate. Relevant patterns: P08, P27, P31, P37, P38.

### R1 — plain-language Appendix-A compiler selector (decision draft; 2026-09-29)

**Decision status.** This remains a proposal for Denis's ruling on how the inherited Appendix-A selector is classified. Denis selected R1 Option A and the controlled-profile N4→N5 engineering slice; this narrow selector proposal does not reopen that choice or establish full R1 closure. No ledger status or denominator change is proposed.

**Question.** Should `tests/unit/runtime/http/test_nl_pipeline_materialization.py::test_plain_language_front_door_calls_real_design_problem_compiler` remain the plain-language front-door witness after the old unbound recursive/N5 expectation was replaced with a candidate-only compile-and-return boundary?

**Options and costs.**

1. **Keep the identity as a candidate-band compiler and limitation witness (proposed).** Exercise the real NL compiler gateway and span-support path, select `candidate_only`, return typed `N4CandidateProposalExecution` with target scope `not_established`, and prove the recursive controller is not reached. Cost: the selector's terminal N4 fixture is a control, not a real N4 producer; a separate served producer witness remains necessary.
2. **Replace it with the qualified-v3 compiler test.** Cost: fewer tests, but this plain-language candidate boundary and its Appendix-A identity stop being measured.
3. **Retain the former synthetic recursive/N5 expected outcome. Rejected.** Cost: it treats an unbound fixture marker as owner evidence and contradicts the selected authority boundary.

**Premises and evidence.** At earlier candidate `b6330454718f73ac907e07d88f7b8e52ee0c1d24`, the target test was absent and the old explicit-N4 selector failed with `cycle_substrate_context_not_established`; that is a historical refusal, not evidence that the current candidate-only selector fails. At candidate source commit `fba4289467401cd1c70e5f6504aba4e80122b70c`, with the uncommitted test-file WIP (test file SHA-256 `99d6b21eab61bed66d23d58326b07df6b800aacff2d4ea916ab5e056864a85e7`; Git blob hash `48d9d218a77e22328acd487a9116a826d03145b2`), the restored selector passes **1/1**. The test WIP was then committed as `3f0ebda3cf2a78c135062bfd43639125f78f7946`; that commit adds only the 111-line test file change, and its implementation blob remains `generation_cycle.py@git-blob:471a80e2db0d93cec5a4c19d5970c1ddb9182e63`. The restored-selector JUnit is `/Users/deniskopylov/.codex/scratch/e02-r1-frontdoor-integration-20260929/frontdoor-restored-green.xml@sha256:b2517ac99c0445412bd2d7e07da3ecf26e912842fcab0f6b9652e5ef213de2de`.

The served candidate and owner controls pass **5/5** at the same candidate/test-WIP snapshot. They cover plain HTTP compilation, three persisted candidate-proposal scope controls, and controlled-profile N4→N5 owner replay; this is not real-data validity or S8 authority. JUnit: `/Users/deniskopylov/.codex/scratch/e02-r1-frontdoor-integration-20260929/served-candidate-and-owner-controls.xml@sha256:3c7475385e75fc9c2a0cf951c2df80f3140700ce35b286e9446c216b6083236d`.

The marker-retaining removal probe changes only the candidate-only early-return condition (`/Users/deniskopylov/.codex/scratch/e02-r1-frontdoor-integration-20260929/R1_CANDIDATE_BYPASS.patch@sha256:5cf2057112445b6ab64fc79dc7ffd22d4bca421694d0b736cd4b119b09b84420`). The selector is **0/1 passing (one expected failing case)** because its recursive-controller tripwire fires: `/Users/deniskopylov/.codex/scratch/e02-r1-frontdoor-integration-20260929/frontdoor-marker-retaining-removal-red.xml@sha256:a4de691eac8c75eaadc1c443b425be965c32a89b4b1fd8650257af382d9bcd4e`. Restoring the implementation returns the same selector to 1/1 green above. An earlier WIP run failed only on an import before correction; it is not the deciding receipt.

**Proposed choice.** Select option 1 for this selector only: preserve the plain-language identity as a behavioral candidate-band boundary. The terminal N4 result must remain explicitly unavailable/limited and must not enter recursive N5/N6/N9/S8/publication through this test. Do not treat the served synthetic-profile N4→N5 control as actual-data admission.

**Remainder.** The selector test is committed in R1 candidate `3f0ebda3cf2a78c135062bfd43639125f78f7946` and present in the current integrated branch `codex/e02-r2` at `2d85006eab77e94800d5ce644a1f0c050c51f5b1` (tree `52812c7e9f8cb471e922d3662795e10f5ff7a1b5`); that merged tree has the same relevant implementation blob `471a80e2db0d93cec5a4c19d5970c1ddb9182e63` and test blob `48d9d218a77e22328acd487a9116a826d03145b2`. The exact integrated-head whole-file JUnit records the selector **PASS** within 40 pass / 11 fail among 51 cases: `/Users/deniskopylov/.codex/scratch/e02-r13-integrated-20260929/nl/junit.xml@sha256:b9e043696edcd5751e0184da02b24268d027d957a466e9f60ddaeea9cf45a4df`. Its integrated receipt is `/Users/deniskopylov/.codex/scratch/e02-r13-integrated-20260929/INTEGRATED_R1_R13_RECEIPT.md@sha256:ae77faf57bbf32604c35b006e9515a95885ff06ad4424d9b201e1cc64a6fd898`. The candidate whole-file receipt at the fba+WIP snapshot reports 40 pass / 11 fail among 51 cases; its historical four-cell comparisons show 35 pass→pass and 11 fail→fail among 46 common identities, with five candidate-only passes and no pass→fail. This is supplementary comparison only: required same-flags exact four-base whole-file replay at current committed source remains **UNRUN**. Whole-file receipt `/Users/deniskopylov/.codex/scratch/e02-r1-nl-whole-20260929/R1_NL_WHOLE_RECEIPT.md@sha256:d20f5353079a8d99f499ccc9d7df8c7c98482f60947bfbcecbe1b0eb33dded84`; candidate JUnit `/Users/deniskopylov/.codex/scratch/e02-r1-nl-whole-20260929/candidate.xml@sha256:24ee6bf0f5383146e622ff9ac7f4af5c76a904272c45eb5b6e2869748befb4b0`. The terminal fixture returns `generation_unavailable`; it is a limitation/route control, not a successful N4 source claim. Real DataState source-time semantics, production-profile coverage, current S8 signer/epoch, and publication remain `not_established`; R1 remains partial. These gaps do not block ordinary N4 candidate work or the controlled candidate computation.

**Falsifier and revisit trigger.** The marker-retaining removal probe is red as required. The property is falsified if deleting the candidate-only early return while preserving typed result/status markers still passes, or if this selector reaches a recursive controller, N5, N6, N9, S8, or publication. Revisit the proposed classification if the compiler/gateway/span-support route changes, the candidate-only limitation disappears, or the served candidate control is withdrawn. The exact integrated-head whole-file replay is recorded; keep the same-flags four-base replay `UNRUN` until every cell has its own complete receipt. Do not infer that matrix from the focused or historical comparisons.

**Where it binds; P37/P38.** This draft binds only the plain-language Appendix-A compiler selector. Compiler and span-support calls, the typed candidate result, and the recursive-controller exclusion are recomputed by the test. Source scope, tenant/store custody, temporal coverage, and current S8 authority remain `not_established` here. P38 divergence: a compiled `DesignProblem` or N5/S8 marker alone is not an admitted owner context; the test measures typed candidate return plus the absence of recursive entry, with the tripwire and removal probe providing the distinguishing boundary. Relevant patterns: P04, P05, P12, P29, P37, P38, P41.

## R1 evidence addendum — direct context refusal and controlled N5 fixture (2026-09-29)

**Decision status.** This records implementation evidence under Denis's already selected Option A in “R1 addendum — owner-bound N4→N5→S8 path.” It adds no principal ruling, finding row, or ledger status change; B01–B03 remain partial.

**Options and costs.**

1. **Treat the direct injected-N4 test as a protected positive (rejected).** It is smaller and preserves the old expectation, but it supplies no worker-issued `VerifiedNLJobScope` or owner-persisted `CycleSubstrateContext` while asking for a protected pre-N9 epoch subject. That would let a fixture stand in for authority evidence.
2. **Keep that direct path refused and use the served worker-owned fixture for the bounded N5 positive (selected under Option A).** Require the leased worker, purpose-limited scope, and same-store context persist/readback for the controlled `simulate_only` witness. This costs a real orchestration test and deliberately stops before S8; it does not solve production DataState time or current signer/epoch.

**Premises and measured evidence.** At integrated source/test commit `8ca88499f`, the old selector `test_direct_recursive_http_and_replay_share_one_owner_context_ref` now expects `cycle_substrate_context_not_established` when it directly supplies an N4 port but no cycle context/verified worker scope. It asserts N4 and the recursive controller are not invoked and no pre-N9 epoch-validity subject is emitted. The separate `test_served_simulate_only_replays_admitted_fixture_context_into_n5` uses the leased worker's purpose-limited scope and `CycleSubstrateContextArtifactOwner` on the runtime-supplied store; N5 reaches `joint_simulated`, but profile admission remains `not_established`, S8 is blocked/not run, the normative disposition is not run, and no N9 receipt or publication is produced. The ordinary no-owner candidate controls remain available. The exact integrated whole-file run is 41/41, zero failures/errors/skips: `/Users/deniskopylov/.codex/scratch/e02-r1-control-integrated-20260929/junit.xml@sha256:916abb68b0d869daf3b5a76e12b27089f78f64bd1dcacb4d364f8b9e4321ac51`. The bounded test correction review is `/Users/deniskopylov/.codex/scratch/e02-r1-control-owner-refusal-20260929/INDEPENDENT_DELTA_REVIEW.md@sha256:791d1ccebe207a4ee5e3e1e14834b21892b7ab0a0f5d57bb7f8d17f7d9101f2d`. Source/test anchors: `policy-engine/tests/unit/runtime/http/test_control_service_di.py@git-blob:c8943b80da8ad0203a09332dbaaf1b6e5a816757`; `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py@git-blob:471a80e2db0d93cec5a4c19d5970c1ddb9182e63`; `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@git-blob:44408ec780524453e39650070031f0c8a6875bc4`; `policy-engine/src/polisyos/runtime/quality/cycle_substrate.py@git-blob:cac954ad97017b62ec98ac5f1b853e14bb8eda87`.

**Remainder, falsifier, and revisit trigger.** This is an exact integrated one-file witness only: the final-blob four-base P41 replay remains **UNRUN**. The source-guard removal and served persist→resolve removal probes are also **UNRUN**, so the 41/41 result is not R1 closure. Keep the current-source pre-N9 epoch-subject positive and S8 current-authority witness **UNRUN** until the relevant current N6 source and issuer evidence exist. Falsifier: with typed markers retained, removing the context guard must make the direct protected-path test reach N4/controller or emit the subject; removing only persist/resolve must make the served N5 positive fail, while the ordinary no-owner candidate control continues. Revisit if a real production profile/time owner, current S8 issuer, or a served consumer with different context semantics is established. The source-time premise and issuer/currentness appointment remain separately owned in OP-R1-TIME, OP-R1-S8, and OP-R2-N6.

**Where it binds; P37/P38.** This addendum binds the test classification at the direct control-plane composition boundary and the controlled simulate-only worker path. The direct test recomputes that owner context is absent and refuses before N4; the served test reconciles the worker lease/scope, persisted context identity and same-store readback, then recomputes N5 for the fixture inputs. P38 divergence is bounded: the old direct injected helper tested a pre-N9 protected result without owner evidence; it is not a served ordinary-candidate caller. The fixture profile/WMR and production temporal validity remain `consumer_asserted` / `not_established`; this evidence grants no profile, currentness, S8, ranking, promotion, or publication authority.

**Separate R1/R2 replay invariant (no implementation decision).** Historical evidence at candidate `0716402ea` recorded two sidecar-current-front test KeyErrors in a 24-case normative file; the full pinned receipt and source anchors are in OP-R1-S8. The first proposed fix to persist `UNRUN` currentness inside a hashed v1 `NormativeGenerationDisposition` received a NO-GO because future currentness would affect historical replay. No product failure or fix at current HEAD is inferred, and no v1 schema change is authorized by this evidence addendum. A revised owner design v2 exists; its independent review and implementation receipt remain pending. Preserve historical bytes and handle currentness as a separate typed runtime decision.

### DR-R13-N9-CONFIDENCE-LEDGER — store custody and risk-budget scope (decision draft; 2026-09-29)

**Status and question.** Draft for Denis as principal and the appointed Confidence Ledger/runtime-storage owners. No scope choice is adopted, and no authority migration, journal relocation, re-key, or historical artifact adoption is authorized. R13 and its existing ledger rows remain unchanged. Which identity owns the canonical N9 risk budget and its CAS/WAL history: one deployment-wide budget shared across tenants, or separate budgets scoped to authenticated tenant/cell contexts? What runtime storage authority must the N9 writer and replay reader consume to make either rule true?

**Options and costs.**

1. **Deployment-global N9 risk budget.** Appoint a deployment-level owner and explicitly define which tenant requests may read or advance the shared history, its audit audience, and its failure/availability semantics. Keep one shared risk budget per design-problem key and provide a shared store/journal owner with the required serialization. This preserves one non-resettable budget instead of multiplying it across tenants. Cost: tenant contexts share state and availability; the system must establish why one request may affect another tenant's budget and how that cross-tenant action is authorized and audited. Existing local WAL locking proves only same-host/shared-POSIX-filesystem coordination, not distributed coordination.
2. **Tenant/cell-scoped N9 budgets.** Derive the scope only from a verified authenticated `AccessScope`, not from problem payload or receipt fields; define any deployment-level aggregate cap separately. This isolates per-tenant journals. Cost: per-tenant budgets may multiply total available risk spend unless an aggregate rule exists; adding tenant/cell to a persisted scope identity changes journal keys and historical lineage, so requires a versioned migration and proof that no prior budget is silently reset or adopted by the wrong tenant.
3. **Defer authority semantics while preserving history (interim posture; not a final policy choice).** Keep existing IDs, local journal bytes, and WAL recovery behavior unchanged; do not describe the current path as an authorized global or tenant-isolated policy. Return a typed custody/scope limitation for authority use until the owner capability and principal scope ruling exist. Cost: some N9 promotion/replay authority remains unavailable or explicitly limited; candidate work that does not depend on that authority can continue.

**Premises and evidence.** The production `CanonicalN9PromotionPort` already owns a `PromotionRuntime`, but `_open_confidence_ledger_session()` discards its store and calls `ConfidenceLedgerSession.from_repo()`. That factory validates the repo against the loaded deployment root and quick fence, then constructs a local CAS at `<repo>/.polisyos/cas` plus a local state root. The separate projected-receipt reader also calls `from_repo()`; public receipt replay, decision-front, EvalSafety, and export consumers reach that raw-store route. Passing `PromotionRuntime.store` by itself is not enough: the current runtime ambient ownership view sets `ownership_requires_scope=False`, so an unclaimed artifact operation can proceed without an active tenant scope. `GuardedDependencyProxy` forwards its target's non-callable `.root`; `is_authority_session` uses root equality as a store predicate, so an unguarded raw CAS at the expected root passes that check. This is a P38 false proof of owner custody, not evidence that a cross-tenant access occurred.

`ConfidenceRiskBudgetScope.scope_id` includes the scope owner, purpose, owner key, and epoch, but no tenant/cell coordinate. `confidence_risk_scope_for_problem()` uses `design-problem:<design_problem_id>` for that owner key. `from_repo()` places the `.head.json`, `.lock`, `.append.wal`, and `.scope.json` state under the canonical repo root, keyed by that scope ID. The code therefore produces a tenant-neutral journal key for matching problem scope inputs; it does not establish that global sharing is the authorized policy. Historical CAS refs were written without tenant ownership claims. A strict tenant-scoped store may refuse those refs; blindly claiming or restamping them for a tenant would manufacture provenance. Preserve exact payloads, deployment identity checks, immutable session provenance, WAL hash/recovery rules, and existing no-reset protections.

Read-only architecture memo: `/Users/deniskopylov/.codex/scratch/e02-r13-ledger-owner-architecture-20260929/R13_LEDGER_RUNTIME_STORE_ARCHITECTURE.md@sha256:bfc97f47d1b1cf6bafb4b27a8d6d9cfb93e87b77c27202cd5c054dbbbad7c3ce`. Independent owner challenge: `/Users/deniskopylov/.codex/scratch/e02-r13-runtime-store-owner-challenge-20260929.md@sha256:73789fb377dc3eae8ce030a721407f4fd973130289f0a985ad413831b1bbb437`. Both are read-only design analyses, not behavior receipts. The challenge is **NO-GO** for claiming full R13/P31 custody or for simple argument substitution; it is conditional GO only for a narrow owner-capability design that binds the actual serving store, admitted deployment identity, and approved tenant semantics, and is used by both writer and reader. It also finds no mandatory-scope capability in the current ambient store contract.

**Proposed posture and remainder.** Do not select deployment-global or tenant/cell scope by inference from current path names. Before any authority-bearing routing change, the principal must select the risk-budget semantics and the runtime-storage owner must appoint/issue a private capability at the trusted serving composition. That capability must bind the exact admitted backend/store instance, canonical loaded deployment, registry/state root, authenticated scope semantics, and the selected risk scope; it must reach both the production writer and the replay reader. Keep `from_repo()` from accepting caller-selected stores, roots, registries, or tenant claims. Missing capability labels are `bridge_missing` for writer and replay routing, and `not_established` for strict active-scope enforcement, cross-tenant budget semantics, and historic artifact ownership. The principal/owner ruling and capability are pending. This draft does not authorize a code migration.

**Falsifier and revisit trigger.** Preserve repo path, registry, loaded deployment identity, quick fence, and receipt/WAL markers, then replace the serving capability with a raw unguarded `FileSystemCAS` rooted at the same `.polisyos/cas`: an authority-session/store-custody test must refuse before a new head is written. Also omit authenticated active scope while retaining the same guarded store; the first authority CAS read/write must refuse before creating a new ledger root/head. Exercise the real production writer and a separate public replay reader against the designated owner store: both must resolve the exact emitted bytes there, with an authorized same-tenant positive and a foreign-tenant negative. For the scope choice, use two authenticated tenant/cell contexts with the same `design_problem_id`; a global ruling must demonstrate the explicitly authorized shared head, while a tenant/cell ruling must demonstrate distinct versioned scope IDs and journals plus an authorized, byte-preserving historical transition. Enumerate historical refs and replay only where owner provenance is evidenced; otherwise return a typed unresolved-owner result. Reopen this draft if any marker-retaining raw-store/no-scope mutant remains green, the reader still selects its own CAS, the observed scope behavior contradicts the ruling, or migration would reset/adopt a historical budget without authority.

**Where it binds; P37/P38.** This draft binds only authority-grade N9 Confidence Ledger CAS production, replay consumption, and risk-budget journal scope. It does not decide N9 risk calculus, a general ArtifactStore tenancy contract, other promotion evidence, ACQ-01, S8 value custody, or any B/LA closure. P37: loaded deployment identity is recomputed by the existing identity owner; the exact serving store binding needs independent reconciliation at composition; active tenant identity is institutionally supplied by authenticated `AccessScope`; current strict per-operation scope enforcement and historical owner attribution are `not_established`; global-versus-tenant budget semantics require the principal ruling. P38: the current store predicate is root equality, not exact owner-capability plus active-scope proof. The distinguishing case is an unguarded same-root raw CAS, or two tenants with the same design-problem key, where the root predicate passes but the custody/scope property is unanswered. Relevant patterns: P27, P31, P32, P37, P38, P41.

## R2 outer-v1 semantic replay rule — principal and normative-owner draft (2026-09-30)

**Question and status.** When the normative composition rule changes, how does PolicyOS continue to interpret a persisted `NormativeRunDisposition.v1` under its original rule while applying the new rule only to new records? This is a draft for Denis and the normative owner, not an adopted ruling. It complements the earlier R2 deployment-identity decision; it changes no B/LA status, register row, plan, epoch, or issued artifact.

**Options with costs.** (1) Freeze a v1 historical evaluator behind the existing owner and dispatch by persisted schema/rule version; a rule change emits v2 with a separate serializer and evaluator. This keeps history replayable but requires retaining and testing historical rule code. (2) Persist a content-bound, independently admitted rule artifact for each disposition and evaluate that artifact during replay. This can support more flexible rules but adds rule-artifact custody, versioning, verification, and retention costs. (3) Return a typed semantic-history limitation once the implementation rule changes, retaining exact bytes but declining historical semantic claims. This is a safe interim authority posture, but reduces usable historical comparison and publication justification.

**Premises and proposed choice.** Commit `03505d419` freezes outer-v1 wire bytes and manifest profile. The reader still calls the current `_project_normative_composition` and leaf owner to recompute meaning; the v1 record contains no independent historical composition-rule identity. Its focused behavior test, rule-change mutation, and complete historical artifact census are `UNRUN` at this head. Propose option 1 as the owner-first long-term rule because versioned historical projections already exist in this corridor. Until its test and owner ruling exist, use option 3's typed limitation for any demonstrated rule mismatch; do not silently reinterpret or restamp a v1 receipt. Option 2 remains available if the owner shows that code dispatch cannot preserve a particular rule's evidence basis.

**Remainder, falsifier, and revisit trigger.** The owner must enumerate issued v1 outer records and their deployed readers, decide the rule-version transition, and preserve byte-exact v1 replay. Simulate a current aggregation-rule change while keeping an issued v1 record and its markers intact: the historical v1 result must remain identical, a freshly issued v2 result may follow the new rule, and an unsupported version must receive a typed non-authoritative result. A v1 result that silently changes meaning, or a fresh result incorrectly forced through v1, falsifies the proposal. Revisit if a rule needs external evidence that a frozen evaluator cannot reproduce or if issued inventories reveal a version not admitted by the transition.

**Where it binds; pattern pass.** This decision binds historical S8 composition replay and current projection from the same persisted outer artifact. It does not supply N6 deployment identity, signed currentness, source-time semantics, positive S8 authority, or N9 promotion. P07 is the replay rule; P08 separates historical admission time from fresh currentness; P27/P31 keep one normative owner; P37 classifies historical rule identity as `not_established` today; P38's divergent case is unchanged canonical v1 bytes interpreted by changed current aggregation code. The smallest correct pattern is one owner-dispatched rule version plus one frozen historical serializer, with a semantic rule-change test rather than a marker test (P29). Evidence: `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py@git-blob:b42fe85abb091657d7470f35851625ab45e5271a` and `/Users/deniskopylov/.codex/scratch/e02r2-r2-outer-v1-review-20260930/review.md@sha256:cc226ff88bfed0dc58bf8ddf01c4552d3615ecf9aab35a5161585762213fb8a5`.

## R13 N5 simulation-graph owner and served selector — principal draft (2026-09-30)

**Question and status.** Which owner produces the world-model simulation graph
and exact execution plan selected for same-case N5 after acquisition, and how
does that selection reach the served worker under verified
tenant/cell/job/worker/attempt scope? This is an owner-appointment/design
decision for Denis and the WMR, Foundry and runtime-quality owners, not an
adopted ruling. The E02-R2 lane proposes option 1 on 2026-09-30; neither the
principal nor an owner has adopted it. The inspected code path establishes no
producer or served bridge; organizational appointment status is not
established. This draft changes no B/LA status, plan, register, issued epoch,
or authority claim.

**Options with costs.** (1) Appoint a world-model simulation-graph producer
and have it issue a typed, persisted graph-plus-ExecPlan selection bound to
the WMR/model or source cycle, registry and full plan order. Extend the WMR
under a versioned transition, or use an equivalent owner-issued envelope,
then let the served N5 caller re-resolve it on its injected guarded store and
verified tenant/cell/job/worker/attempt scope. This supports a real positive
state-to-engine witness. The world-model/Foundry owners bear the producer,
schema and plan contract work; runtime-quality bears the selector and guarded
store bridge; historical readers bear versioned replay tests and maintenance.
(2) Keep direct controlled ProgramGraph execution as candidate-only
characterization under a separately reviewed lease using test-owned,
owner-built WMR/Foundry artifacts. This allows N5 numerical research without
claiming served world growth; its graph/plan premise remains
`not_established` for authority and the capability remains
`implemented_but_not_orchestrated`. The test lane bears fixture and negative
probe cost, while future integration bears the delayed served bridge; B12/R13
stay partial. (3) Reuse the present policy `CompileResult` as the N5 plan solely
because it carries the same ref kinds. This appears cheap to the integration
lane but transfers an unverified model-phase and lineage risk to N5 consumers
and the justification custodian. It is rejected by current evidence: it
compiles a Trinity **policy** into an ExperimentState, with no owner proof
that its graph is the world-model graph or a served same-case bridge.
Ref-kind equality is a P38 proxy.

**Premises and proposed posture.** The production DataState WMR builder
supplies no `program_graph_refs`; no production caller supplies N5
ProgramGraph plan hints. WMR v1 omits graph artifacts from manifest inputs,
records bare graph IDs and no ExecPlan/order; `EnginePlan.model_dump` drops
runtime refs. Foundry's policy compile refs have no path into the served N5
worker. Option 1 is the lane's preliminary recommendation, while option 2 is
the admissible interim candidate posture. No principal or owner choice has
been adopted. Do not implement option 3. The selected WDI
`percent_gdp` observation still lacks a compatible DataState slot/time and
SKG lineage; appointment of a graph owner does not answer those questions.

**Remainder, standing, falsifier, and revisit trigger.** Which owner or
institution signs the WDI row-to-slot/unit/time rule, SKG lineage, the
world-model graph/plan selection, and live serving scope is `not_established`
here. N9, S8, publication and selected-view CAS replay retain separately
recorded unresolved predicates; this draft does not appoint their signers.
The graph owner, once identified, confirmed or appointed, must define which
world-model graph is admissible for one WMR and how the full ExecPlan and
registry are content-bound, then supply a served positive that actually
changes N5's numerical input when the admitted bound state changes under
verified tenant/cell/job/worker/attempt scope and an owner-approved
row-to-slot/unit/time and SKG lineage rule. Keeping
IDs and markers while removing the selected-state handoff must turn that
positive red. A policy graph with the same ref type but different model phase,
or a same-graph plan with changed order, must not gain authority. Revisit if
an existing world-model graph producer and verified served selector is found
by a complete owner census, or if the appointed producer cannot bind plan
semantics through a versioned WMR/envelope.

**Where it binds.** This draft binds only the R13/B12 ProgramGraph
world-state-to-N5 handoff and its served graph/plan selection. It does not
close canonical Data Forge row-to-DataSnapshot, WDI unit/time, SKG lineage,
N9, S8, publication or multi-view CAS replay. P27/P31 require the WMR and
Foundry owners; P37 leaves graph phase, plan provenance and live scope
`not_established`; P38 distinguishes matching ref kinds from matching model
meaning; P40 keeps the state-to-N5 gap in the existing R13 class. Evidence:
`/Users/deniskopylov/.codex/scratch/e02-r13-n5-implementation-preflight-20260930/PREFLIGHT.md@sha256:0dc0ba211248c42c645c2c7e3c71012ad5dc4e99125c80d30929a696d7869bfd`.

## R9 — crash-safe owner-index publication and mutation boundary (proposed principal decision; 2026-09-30)

**Question.** Which persistence and mutation contract may the R9 implementation rely on when replacing the legacy two-file ownership index and adding cross-instance CAS leases?

**Options and costs.**

1. **Adopt immutable v3 generations behind one atomic pointer, with the reviewed prerequisites (recommended proposal).** Before pointer publication, strictly fsync the newly created `generations/` entry in its parent, the generation file and generation directory; after pointer replacement, strictly fsync the ownership directory. Any required fsync failure aborts publication or returns a typed indeterminate outcome. Freeze `evidence()` as a versioned shape naming the pointer, immutable generation and signature bytes. Preserve the exact current legacy v1/v2 pair as the first imported generation without restamping; historical digest-only references to older overwritten pairs remain `UNRESOLVED` unless an exact archive exists. Make index mutation private or require an unforgeable lease capability issued by the CAS owner. Cost: a sequenced persistence/API migration, precise crash and replay tests, caller updates, and an explicit unresolved historical remainder. The reviewed generation-pointer direction is retained, but this option is **not approved or implemented by this draft**.
2. **Choose a single-file envelope or journal instead.** This may simplify the atomic commit point or recovery, but still requires strict directory durability, a frozen evidence/version contract, explicit handling of overwritten legacy history, and mutation through the lease owner. Cost: a fresh recovery/crash analysis and independent design review before implementation; it cannot be used to bypass the same three blockers.
3. **Keep the current two-file index and defer crash-safe R9 publication.** Cost: the measured owner/read race and crash-torn index remain; R9 stays partial and no crash-safe claim is made.

**Premises.** At the pinned source, `_write_payload()` replaces `index.json` and `index.signature.json` in separate operations. `fsync_parent()` silently treats failure to open the parent directory as success; an `os.fsync` `OSError` propagates without a typed indeterminate result. `ArtifactOwnershipIndex` is publicly exported with mutation methods that do not take a CAS lease. Existing evidence consumers use legacy index/signature path/digest semantics. Review found no archive for legacy generations already overwritten before migration; a hash cannot recreate their bytes. These are source/design findings, not new test results.

**Remainder, falsifier, and revisit trigger.** The v3 evidence contract must distinguish pointer identity, exact immutable generation bytes, and signature bytes; old digest-only evidence is not silently upgraded. Reopen the proposal if an exact archive for overwritten generations is discovered, if an owner identifies a different source-authoritative replay rule, or if crash injection shows any point where restart reports a valid generation whose bytes or directory entry were not durably committed. Required closure falsifiers are: (a) each directory/file/pointer fsync crash point reopens to a complete generation or typed indeterminate result; (b) every retained legacy fixture and migrated current pair replays byte-exactly, while unavailable overwritten history stays `UNRESOLVED`; (c) a direct `record_*` call without the lease capability refuses and the CAS-owned leased positive succeeds. Keep the unclaimed-candidate and exact-view controls; a lock must not become a blanket refusal. The separate retained-raw-path probe must also show guarded consumers cannot open a path after authorization becomes stale.

**Where it binds.** This draft binds the Core ownership-index persistence/evidence API and the FileSystemCAS mutation boundary in R9/CAS-01. It does not decide the separate same-blob multi-view policy, establish arbitrary direct filesystem access as guarded, or close R9. P40 classifies this as the same R9 owner-first custody class, one level deeper: widen and freeze the owner-level mechanism, or retain a bounded residual with these falsifiers; this is a worked example within the already-declared class, not another repair round. The independent review also requires the complete caller/schema/test write set to be frozen before an implementation handoff; the ordered prerequisite → CAS custody → caller migration → acceptance sequence is a proposal, not proof that this census is complete. R9 remains partial until the crash, replay, mutation-bypass, cross-process race, guarded-path, and candidate-control witnesses pass. Evidence: `/Users/deniskopylov/.codex/scratch/r9-atomic-publication-design-20260930/R9_ATOMIC_PUBLICATION_DESIGN_V2_REVIEW.md@sha256:27462cb8f74afc9c667b9709cfb10ca8e6b293e9d58d7b01f8d4694a122b9fe1`; source blobs are enumerated in `OPEN_PREMISES.md` under `OP-R9-ATOMIC-PUBLICATION-V2-REVIEW`.

## R9 — bind served production approvals to owner evidence v3 (proposed principal decision; 2026-09-30)

**Question.** Commit `8765436bb` has landed immutable ownership generations and pointer publication, but the writer activates pointer format on every changed owner mutation while the served approval path remains v2. What owner-controlled activation and consumer contract must be in place before pointer format can safely coexist with production approvals?

**Options and costs.**

1. **Add an owner-owned default-off pointer activation gate, then adopt packet v3 with scoped-claim currentness (recommended proposal).** Keep `ArtifactOwnershipIndex` as the sole publisher; bind activation in its existing config/composition path to canonical deployment identity and cover every mutation path. Add a lease-bound scoped projection of the server-resolved approval inputs; packet v3 stores it in a strict nested binding and the served reader recomputes it. Cost: coordinate owner, store/config, DTO, approval, HumanDecisionService, route/composition, deployment attestation, generated API, tests and docs; preserve exact v1/v2 serializers and complete a one-way authorized rollout before enabling pointer format.
2. **Quarantine pointer format from v2 approvals as an interim fallback.** Keep pointer publication gated off where the owner can enforce that state; if pointer format is observed, refuse v2 issuance before the CAS write and return no operational currentness receipt for v2 reads. Cost: approvals using pointer-format stores remain unavailable until the v3 chain is complete; ordinary candidate/runtime work remains available in the inactive format.
3. **Compare the complete global generation for currentness.** This is mechanically smaller but every unrelated tenant's owner-index write stales every approval, and it still needs exact owner verification and versioned historical serializers. Cost: systemic churn and false stale outcomes; reject unless a measured product contract explicitly requires global invalidation.

**Premises.** At current head `edf4aa31158c1a0457d5b9bf6d649f623bdcb8cd`, `8765436bb` has landed immutable generation and pointer code, but `_write_payload` publishes a pointer on every changed owner mutation without an activation precondition. The landed owner evidence includes `policyos.artifact_ownership_evidence.v3`, `pointer_generation_v1`, separate pointer/generation schema IDs, exact same-snapshot pointer and immutable-generation byte hashes, semantic payload/signature digests, and the portable locator `{container_ref:<generation_sha256>, member:"signature"}`. Owner mutations serialize through the index-local `index.lock` flock, not a runtime `FileSystemCAS` transaction lease; no scoped approval claim projection is produced. Meanwhile the served route/builder/service/resolver remains v2: the builder carries only two digest markers, route evidence errors become `None`, and currentness ignores owner evidence. Thus pointer publication leaves v2 issuance/currentness reachable; the pointer-rollout review calls that unsafe. The v3 consumer/activation gate is `UNRUN`. This is source reachability evidence only, not evidence of an already-migrated live CAS. The proposed contract adds a lease-bound projection of the exact server-resolved scorecard, production basis, human-decision record and request, tenant/cell and selected manifest profiles; unrelated tenant writes must not stale it. Owner `sha256-local-integrity` is unkeyed integrity, not cryptographic signer identity. The committed fixture census at source pin `eb3383e3581b0ac7dc55781934584a1bde91dc7e` was 13,413 tracked paths, 290 fixture files, zero raw v1/v2 packets/receipts. Live CAS population and retention remain `not_established`.

**Remainder, falsifier, and revisit trigger.** No v3 authority or closure claim follows from this proposal. Preserve frozen pre-change v1/v2 bytes/refs: v1's exact original projection (with the legacy helper's `exclude_none=True` serializer distinct from the authority writer), and v2's full authority projection with its original default/`None` values. A re-dump through the expanded model is not a fixture. V1 remains history-only; v2 is never emitted after pointer activation. A match of both semantic digests to the captured first-migration pair is only a snapshot match: recompute the packet's exact scorecard, basis, decision-record and request claims, tenant/cell and selected manifest profiles against those captured bytes. Only a complete verified match may yield owner-binding `historical-valid`, distinct from packet signature status. Otherwise return typed owner-binding `UNRESOLVED` (with `snapshot_match_only` when the pair matches); never promote a snapshot match into historical approval validity. Neither old version is current without authorized reissue. Before pointer publication, enumerate configured/persisted CAS records through the store owner and record missing history as unresolved. Revisit if that inventory finds recoverable exact overwritten generations, if the owner cannot return exact bytes and scoped claims under one lease, or if a principal/appointed owner supplies a different explicit invalidation scope. The decisive falsifier keeps packet markers and signature intact while removing/changing a relevant owner claim: served currentness must be stale/unresolved with no currentness receipt. The control changes only an unrelated tenant's claim and must remain current. A v2 emission attempt after pointer activation must refuse before any CAS write.

**Where it binds.** This proposed choice binds pointer activation for the existing ownership owner and the production approval v3 `ProductionApprovalPacketResolver`/`HumanDecisionService` served write/read path. The current pointer writer is already in code and unconditional; no activation gate or v3 consumer is claimed. The first implementation boundary is an owner/config-owned, deployment-bound default-off gate over all pointer publication paths, with v2 issuance refusal before CAS and no operational currentness when pointer format is observed. Then implement the lease-bound scoped resolver, strict control DTO, versioned serializers/builder, service writer/readers, route/composition/deployment attestation, generated API owners and behavioral tests. Freeze v1/v2 bytes and enumerate live CAS before any authorized one-way pointer activation; drain all v2 writers first. Preserve candidate/runtime work while the authority rollout is inactive. This proposal appoints no external signer and does not resolve live CAS inventory/retention or the meaning of the local integrity digest. R9 remains `partial`; no register or plan status changes are proposed. Evidence: `/Users/deniskopylov/.codex/scratch/e02-r9-pointer-rollout-20260930/R9_POINTER_ROLLOUT_GATE_REVIEW.md@sha256:4a5ddae35f92d134328798d95bc4adb522cf8b3ab225788a3288a2c9be409e2d`.

### R9 current-state addendum — V2 production-approval authority containment across recognized owner-index states (2026-09-30)

**Supersession and decision status.** The preceding default-off interim proposal is retained as a historical design snapshot, but it is superseded as the implemented state and temporary recommendation by this addendum. Commit `6722e2a30ea424c84b1d20dfaa64664ee045fdec` does not add a pointer activation switch: `_write_payload` still publishes pointer generations on every ownership mutation. It instead adds an owner-bound v2 authority gate. At this dated snapshot, Denis's principal decision was still pending on whether the V2 production-approval refusal across all recognized owner-index states should remain the temporary product posture; the later ruling below resolves that question. The gate landing is not that ruling, does not authorize a global pointer rollout, and does not close R9/CAS-01.

**Current proposal and cost.** Keep the pointer writer as implemented and retain the v2 gate until an owner-bound v3 chain is served. The shared `HumanDecisionService` refuses every v2 production-approval issuance before its authority CAS write and refuses every v2 operational-currentness resolution for all recognized owner formats: `ephemeral_empty_v2`, legacy v1, v2 signed-pair, and pointer-generation. Owner lookup/shape failure is a distinct typed unresolved refusal. This suspends served v2 production-approval issue and currentness even for an older signed packet whose digest markers happen to match. That is a real availability cost; historical signed bytes/signatures remain readable and ordinary candidate artifact writes remain available. Candidate storage continuity does not mean served v2 approval capability remains available. Do not reintroduce a default-off fallback or infer that legacy format makes v2 current.

**Costed feasible alternatives (principal choice pending).**

1. **Retain this broad v2 refusal pending v3 (current code; proposed temporary posture).** It avoids treating format or digest markers as scoped authority and keeps candidate writes plus historical byte/signature reads available. Cost: all served v2 approval issuance and operational currentness remain unavailable, including legacy signed-pair records whose claims might in fact be unchanged.
2. **Build an owner-atomic publication gate before considering a narrower interim.** The existing owner/config path would have to serialize every pointer-publishing mutation, including the packet's own `record_owner`, against v2 issue/currentness under the runtime store lease. Only after an end-to-end witness covers every mutation route could the principal consider narrowing issuance refusal to the state the gate actually prevents. The gate alone does not make v2 scoped claims current and must not re-enable currentness from digest markers. Cost: owner/config/store lease work across all mutation callers and a deployment-bound transition; it may reduce issuance refusal but does not restore operational v2 approval without an independent scoped-claim resolver.
3. **Permit v2 operational currentness when pointer format is absent or digest markers match (rejected).** This preserves more apparent availability, but the v2 packet has no independent resolver for exact selected claims; a format check or global digest match does not prove the packet's tenant/cell/manifest claims. Rejecting this shortcut costs continued v2 currentness suspension until v3; accepting it risks authority on `not_established` evidence.

The earlier pointer-observed-only interim in `/Users/deniskopylov/.codex/scratch/E02R2-R9-v3-positive-path-design-20260930.md@sha256:7f3faf231f2b6920f211d8ec59034334c9c9f6451f78d71dbcbbc6d8baecf207` is superseded as an implementable gate by the current source: pointer publication is unconditional, and the packet CAS write itself records an owner claim that can publish the pointer after any preflight. A narrower format-only check therefore has a TOCTOU gap unless publication is first made owner-atomic across that write.

**Owner path and intended positive v3 path.** Issuance runs `routes/runs.py::create_run_production_approval` → `ProductionApprovalPacketResolver.persist_authorized_packet` → `HumanDecisionService._persist_production_decision_packet` → the `HumanDecisionAuthoritySink` using the runtime-supplied store. The store records an owner claim as part of the packet authority write; a preflight cannot rule out the same write publishing a pointer. Currentness callers including `ProductionApprovalPacketResolver.require_currentness`, `AgentActionAuthorityBuilder`, and capability authority converge on `HumanDecisionService.resolve_production_decision_packet`, so the refusal sits at the shared owner. The route's projection helper still maps lookup errors to absent evidence; that projection is not authority. The central service reads owner evidence from the supplied sink and refuses typed on absence or invalid shape. No CAS is reconstructed from a root path.

The v3 positive path remains unimplemented and `UNRUN`: the canonical owner must compute, under the runtime-supplied store lease, a strict projection of the server-resolved scorecard, production basis, human-decision record and decision request, tenant/cell, and selected manifest profiles. A strict nested `artifact_ownership_binding` must carry exact pointer/generation version and byte identities plus the portable generation locator and owner-computed scoped-claims digest. V3 issuance and a fresh reader must recompute the same scoped projection under that lease. A relevant claim mutation with packet markers retained must refuse; changing only another tenant's claim must preserve currentness. This scope-specific projection avoids making every unrelated tenant write stale. A deployment-bound activation/drain receipt is also still required before any claim that pointer publication is a safe rollout.

**P37/P38/P40.** Owner format is recomputed through the supplied store. Exact correspondence between the v2 digest markers and the packet's selected scoped owner claims is `not_established`; every recognized v2 format therefore refuses. P38 divergence is deliberate over-refusal: a signed-pair v2 packet with marker digests equal to the evidence still cannot be reported operationally current. That authority limit is not a finding that its signature or historical bytes are invalid. P40 places this at the shared v2 authority owner. If another production consumer bypasses it, route that consumer through the same owner mechanism rather than adding another local patch; the full importer census remains open.

**Behavioral evidence and bounded P41.** The focused current-source run passed 3/3 in 8.506 s: `test_v2_currentness_gate_refuses_pointer_and_digest_markers_do_not_substitute`, `test_v2_packet_issuer_refuses_empty_legacy_and_pointer_owner_states`, and `test_served_v2_approval_refuses_pointer_owner_without_packet_artifact` (`/Users/deniskopylov/.codex/scratch/e02-r9-pointer-integrated-20260930/committed_focused.junit.xml@sha256:06d15b6cab3815c043b10974405567de5772949db1347f2cb432bb1c7abfa52b`). The selectors cover refusal under empty/legacy/pointer owner evidence, a distinct owner-lookup refusal, no packet artifact on the served 503, a candidate-store write, and historical packet-byte/signature readability. The removal probe removes the central gate while retaining digest markers and causes the otherwise valid packet to resolve.

The whole-file run for the two touched test files passed 144/146; its two reds were `tests.unit.runtime.http.test_control_api::test_explicit_non_simulation_attempt_blocks_before_workspace_loop` (`KeyError: eval_safety_disposition`) and `tests.unit.runtime.http.test_control_api::test_list_connectors_and_profiles_are_producer_backed` (`assert 0 == 1`) (`/Users/deniskopylov/.codex/scratch/e02-r9-pointer-integrated-20260930/two_files.junit.xml@sha256:b1a4d76f6bed0c4047af7acebc70868129ba97ed20e2d42147f04fa44ebb8703`). Both exact selectors also failed on clean pre-patch HEAD `8622de6dda195d1738663d3ad1cc77a2a532a964` in 1.985 s with the same failures (`/Users/deniskopylov/.codex/scratch/e02-r9-pointer-integrated-20260930/base_two.junit.xml@sha256:996a49ec069e0e4d9d014f36dac058ac0082f4ce08304d0319168e7ddeb41479`). Thus this bounded comparison shows no new pass-to-fail among those two identities. It is not the required four-base whole-file replay. Since a changed path includes `test_control_api.py`, complete input-closure/disjointness for those failures has not been established; formal P41 inherited attribution remains `not_established`, and the remaining touched-file/four-base denominator is `UNRUN`.

**Falsifier and revisit trigger for the recognized-owner-state suspension.** Reconsider the breadth only if a served v2 reader (or owner extension) resolves and content-binds every exact packet-scoped tenant/cell/selected-manifest claim under the same runtime-store lease, then remains current after an unrelated tenant mutation while refusing a changed or removed selected claim with all packet markers and signature retained. A legacy label, absent pointer, matching digest, or format preflight alone is not a falsifier. Once the owner-bound v3 writer/reader, exact historical serializers, deployment identity and v2 drain are witnessed, replace the temporary v2 refusal through the authorized rollout; do not silently reactivate v2.

**Remainder and binding.** Preserve exact versioned historical projections and signatures, but do not claim exhaustive replay: the committed-fixture census found zero raw approval packet/receipt fixtures, and the live configured CAS population remains `not_established`. No signed receipt is restamped. This addendum binds only the served v2 production-approval issuer/currentness seam and its temporary refusal proposal. It does not bind candidate artifacts, unrelated packet families, or global ownership-index publication. R9 remains `partial`; no debt-register or plan closure is proposed. At this dated snapshot, the principal had yet to decide whether to retain this V2 production-approval refusal across recognized owner-index states pending the V3 scoped projection and deployment-bound rollout evidence.

## EMP-01 / B31 — meaning and projection of statistical intervals (draft; no ruling, 2026-09-30)

**Question.** May the existing public ValueOuterSet carry a report's statistical interval separately from its identification bounds, and what evidence is sufficient to project it?

**Options and costs.**

1. **Extend the existing owner with a versioned statistical-interval component (proposed direction, subject to owner semantics).** Keep lower/upper as identification bounds and preserve the native interval independently with typed provenance and any established coverage/estimand/unit/time fields. Bump the persisted owner/receipt schema and historical serializer boundary; expose it only through a served consumer that can distinguish the two meanings. Cost: coordinated owner, producer, persisted snapshot/receipt, reader, replay, and eventually API/surface work. The current helper has no production caller, so this alone would not close B31.
2. **Keep the public DTO and its interval semantics on HOLD while allowing candidate-only work.** Carry the raw interval only in an explicitly non-authoritative producer-local candidate record until an appointed owner supplies the missing contract. Cost: B31 remains held and no general public statistical-interval claim is available; avoids silently freezing an under-specified public/hash contract.
3. **Treat the confidence interval as lower/upper or convert it to a symmetric proxy envelope.** Cost: a misleading public uncertainty claim, lost asymmetry, and unit-dependent behavior; reject on current evidence because it conflates sampling with identification/transport uncertainty.

**Premises.** The B31 audit criterion requires uncertainty channels to remain distinct and forbids arbitrary width. Current source drops the CI for a point set and symmetrizes a proxy interval. The two current selectors are RED, but no base-passing result exists: their test file is absent on 78187878e and 5fd3ebcc1, and E02's own test-first receipt recorded the B31 assertions red. This is existing held work, not an R2-introduced regression. Source inspection found no production caller of the helper and no production ValueGateReceipt constructor. The statistical interval's coverage, estimand, unit, provenance and time scope are not established by a pair of floats.

**Remainder, falsifier, and revisit trigger.** No public DTO change is authorized by this draft. Revisit when the principal/appointed value owner defines which interval semantics and metadata are guaranteed by the producer and who consumes them. Once implemented, preserve [1,10] byte/value-exactly as the separate statistical interval through a production producer, persisted artifact and consumer; remove that field with all markers retained and require a typed limitation, while the point-identified candidate control continues. Enumerate historical snapshots/receipts, preserve old serializer bytes exactly, and classify live CAS rows separately before claiming replay. The complete closure signal must include a served producer-to-persisted-artifact-to-consumer witness; helper-only tests do not discharge B31.

**Where it binds.** This draft binds only EMP-01/B31's value uncertainty semantics and the existing ValueOuterSet owner. It does not decide calibration, transport authority, promotion, publication, or Atlas DS12/DS13. Ledger status stays held; no debt-register or plan edit is proposed. Evidence and four-ref attribution: /Users/deniskopylov/.codex/scratch/E02R2-B31-statistical-interval-design-dee6ab3af.md@sha256:dce7d1456cd5a85db252f77448d85597aaaaa3c9fc8af384c3613bcf60d33a86; fresh current JUnit: /Users/deniskopylov/.codex/scratch/e02-b31-current-20260930/B31_current_two.junit.xml@sha256:1a3a2cb4abb50065f7bf30ebb9225210a10f4bb74b1acad985bac46cab750b32.

## R9 principal ruling — retain temporary V2 production-approval refusal across recognized owner-index states pending V3 (2026-09-30)

**Ruling and costed options.** Denis selected option 1 in the preceding R9 current-state addendum: retain the shared-owner refusal for V2 production-approval issuance and operational currentness until the owner-bound V3 path is implemented and reviewed. The accepted cost is that every served V2 production approval remains unavailable, including a legacy signed-pair packet whose owner claims may in fact be unchanged. Historical packet bytes and signatures remain readable, and ordinary candidate artifact writes remain available. The alternative is to build and verify the complete scoped V3 writer/reader and deployment-bound transition before restoring served approval authority; this costs the owner, serializer, service, deployment, API-surface and behavioral-test work already listed above. A format-only or digest-only V2 exception is not selected because it does not resolve exact packet-scoped claims.

**Premises and evidence boundary.** At source pin `b4a1212b6` (2026-09-30), the shared `HumanDecisionService` contains the V2 issuer/currentness refusal described above. Its focused evidence remains the 3/3 run at `/Users/deniskopylov/.codex/scratch/e02-r9-pointer-integrated-20260930/committed_focused.junit.xml@sha256:06d15b6cab3815c043b10974405567de5772949db1347f2cb432bb1c7abfa52b`. The nonempty V2 signed-pair refusal branch was source-inspected but not separately behavior-tested. The two-file result is 144/146 with the same two failing selectors on the clean pre-patch comparison; that bounded comparison is not the required four-base whole-file P41 replay, and formal inherited attribution remains `not_established`. This ruling adds no test evidence.

**Status and scope correction.** This ruling supersedes earlier R9 wording that Denis’s choice was pending. In the preceding dated addendum, “all-format” means all recognized owner-index states for the served V2 production-approval issuer/currentness seam (`ephemeral_empty_v2`, legacy v1, v2 signed-pair, and pointer-generation); it does not mean all receipt, packet, or artifact families, and it does not refuse historical byte/signature reads. The prior alternatives, premises, and test snapshots remain historical records. Owner-index-publication, V3-binding, and multi-view proposals remain separate open decisions.

**Remainder, falsifier, and revisit trigger.** V3 remains unimplemented and `UNRUN`. Revisit the breadth of the refusal only after the canonical owner resolves and content-binds the exact packet-scoped scorecard, production basis, human-decision record and request, tenant/cell, and selected manifest profiles under the runtime-supplied store lease. With packet markers and signature retained, changing or removing a relevant selected claim must make served currentness stale or unresolved and issue no currentness receipt; changing only an unrelated tenant's claim must preserve currentness. Before any production transition, also require an enumerated live-store inventory, canonical deployment identity, owner-atomic pointer publication control, and a deployment-bound v2 drain/rollout receipt. Passing these conditions triggers a fresh principal review; it does not silently reactivate V2.

**Where the ruling binds.** It binds the served V2 production-approval issuer and operational-currentness seam at the shared human-decision owner. Historical byte/signature reading and candidate-band artifact work remain available. It does not authorize a global pointer-writer rollout or establish that the existing unconditional pointer-generation writer is safe to activate in production. R9/CAS-01 remains `partial`; the ledger, debt register, and GY/Atlas plan statuses are unchanged.

## R1 V3 profile-selection reference — bounded engineering decision record (draft; 2026-10-01)

**Decision status.** This is an engineering decision draft within Denis's already selected R1 Option A and controlled candidate N4→N5 lane. The source-pinned V3 design review gives a bounded GO for its existing coding lease; this record does not request or grant new principal permission, claim code integration, or change B01–B03 status. The separate Appendix-A test-identity and R1/R5 per-active-basis proposals remain distinct.

**Question.** How can one server-configured static candidate scenario match an ordinary served N4 semantic/provenance record despite execution IDs supplied by the verified worker, without weakening the full DesignProblem identity or job/context custody required by N5 and replay?

**Options and costs.**

1. **Keep exact full-ref matching.** This is the smallest code change and preserves one identity comparison, but a static profile cannot know future worker-assigned tenant, cell, job, and run IDs; the controlled served N4→N5 candidate path remains unavailable.
2. **Use a purpose-specific profile-selection ref (bounded engineering direction).** Derive it from the existing frozen context-job v1 projection after removing only `tenant_id`, `cell_id`, `job_id`, and `run_id` at `nl_provenance.source_context`. Cost: one helper, a renamed/versioned candidate profile field, and dual checks at existing admission/materialization/N5 joins. This permits static candidate-scenario selection while retaining the full per-execution ref at every persisted custody join.
3. **Strip broader provenance or use the reduced ref as job/context identity.** This appears simpler, but could hide retained semantic changes or allow cross-job/context confusion. Reject; it weakens the property and bypasses existing custody owners.

**Premises.** Denis selected the controlled owner-bound synthetic candidate lane while real DataState time contracts and S8 remain limited. The four omitted values are server-injected execution IDs at that one nested path; raw request, time/as-of, jurisdiction, authority, remaining source provenance, and all other semantic fields stay in the selector basis. The frozen v1 serializer and complete `CycleSubstrateContext.design_problem_ref` remain unchanged. The configured action is hypothetical candidate `set_to`, not proof that L6/LEX admits a real lever. The V3 design and independent delta review are `/Users/deniskopylov/.codex/scratch/e02-r1-candidate-atom-design-20260930/R1_PROFILE_SELECTION_REF_REVISION_V3.md@sha256:c8d4a11581f4c7a98e2f62c479f514f179b2fb9be3f6d873741bca04154ac50c` and `/Users/deniskopylov/.codex/scratch/e02-r1-candidate-atom-design-20260930/R1_PROFILE_SELECTION_REF_V3_INDEPENDENT_DELTA_REVIEW_20261001.md@sha256:26cd196f13023030cbecb4d42d63c7d73d66f04925b343f88342600e89a6cac5`; the independent review ran no tests. The separate source-pinned scope diagnosis and independent issuer review are `/Users/deniskopylov/.codex/scratch/e02-r1-candidate-atom-design-20260930/R1_SCOPE_ISSUER_P40_DIAGNOSIS_20261001.md@sha256:c7976f89aa239cabcec6a6cd310ffd08f855c62597be997166c40779bc371256` and `/Users/deniskopylov/.codex/scratch/e02-r1-candidate-atom-design-20260930/R1_GENERAL_SCOPE_ISSUER_REVIEW_20261001.md@sha256:d1fcfd43494d5bcf2bd80ad476e99347f6ad4c5ee95ba282bf7c6dd99d6dc807`. They give GO only for removing the request `target_world_scope_profile_id` nonempty-string condition from existing `VerifiedNLJobScope` issuance, retaining established admission, exact simulate-only intent band/mode, authenticated actor, tenant/cell, route/event/outbox/manifest and digest binding, current persisted job/run/state, nonempty live lease owner matching dispatch, and same attempt. The scope remains ephemeral `cycle_input_candidate_only`; it binds the act/lease, not profile vocabulary, profile admission, or authority. Neither review ran tests. The admitted freeze-02 whole-file run was 1 pass / 2 fail: one scope-issuer mismatch and one source-unbound compiler fixture; it is not a successful served receipt. The configured served positive still needs the truthful compiler fixture and a fresh admitted runtime run. These source reviews do not claim runtime delivery or R1 closure.

**Remainder.** The reviewed issuer correction is still an engineering direction, not an implemented or runtime-verified behavior: the configured served positive needs a truthful compiler fixture and a fresh admitted runtime wave. This draft does not establish a configured production profile producer, real source-time validity, real-world effect grounding, LEX admissibility, S8, N9, promotion, publication, or an authority-grade result. Those remain limited or `not_established` under their existing owners. The R1 candidate source also predates the integration lane's R9 selected-manifest-view API and reduces runtime refs to bare artifact-ID strings in context handoff/read paths. Forward-porting must preserve selected `ArtifactRef` and manifest-profile identity and use the view-aware store API; otherwise selected-view custody may fail or resolve an unintended default view. This is a bounded engineering integration remainder for the R9 typed-view owner to resolve, not a new principal blocker and not a reason to weaken the issuer or selector property. No test or served positive is claimed by this design record; a reviewed design GO is not a behavior receipt.

**Falsifier and revisit trigger.** Reopen this engineering choice if changing any retained semantic/provenance value leaves selection unchanged; changing only the four verified execution IDs changes selection while full problem/context refs fail to differ; a foreign/stale worker can replay another job's context or reach N5; a profile mutation after startup escapes hash refusal; or the served positive requires a fake compiler, source-context erasure, identity rewrite, or LEX provenance laundering. Keep profile markers fixed in the removal probe, and require the ordinary no-profile N4 candidate control to continue with its typed limitation.

**Where it binds.** Only server-configured, simulate-only candidate scenario selection and N4→N5 candidate computation under the existing verified worker/context-job chain. The selection ref is not a DesignProblem, tenant, job, context, grounding, custody, or authority ref. Full problem/context custody, history replay, S8 authority, and publication are unchanged. This follows P05/P15 (the result remains candidate-only and carries no authority), P27/P32 (reuse existing owners and resolve/bind the selected profile and complete custody refs), P37 (recompute the profile basis; revalidate full worker/job/context custody through the existing owner; real time/grounding remain `not_established`), P38, and P40 (one purpose-specific selector mechanism, not per-consumer identity patches). The P38 divergent case is concrete: comparing one full execution-bound ref for both profile selection and job identity makes the positive selector unreachable, while using the reduced selector for identity would weaken custody. P41 four-base replay and served behavioral evidence remain `UNRUN`; the ledger/status count does not change.

## R9 governed-public read closure trust — engineering draft, 2026-10-01

- **Options with costs:** A uses the existing CAS owner as trust root, with an exact purpose/operation/ref closure and measured deployment root isolation; B appoints an independently authenticated grant issuer with protected key custody, rotation, recovery, and historical migration; C keeps anonymous verification limited until either trust basis exists, retaining the public-read capability gap.
- **Premises:** publisher/mandate verification has existing owners; the ownership-index digest is unkeyed local integrity; exclusive root protection is not established by the reviewed source. HTTP/public provider/watcher are existing consumers. A private fixture proves local behavior, not production isolation.
- **Remainder:** no current-Claim grant, arbitrary tenant-read permission, or V2 approval is implied. Records without closures require an authorized transition. Same-root writer/process compromise remains outside A. Selected ArtifactRef preservation may proceed independently and grants no new permission.
- **Revisit trigger as falsifier:** an untrusted deployment principal can replace the canonical ownership index, or a public/tenant request mints a closure without the owner's completed verification. A valid-index removal of only the closure must refuse anonymous GET/watcher before private bytes while all publisher, mandate, population, locator, and unrelated claims remain intact.
- **Where it binds:** anonymous verification and bounded watcher authority for exact governed-public records; candidate work and independent selected-view repair continue. This does not supersede Denis's V2 refusal ruling.

Status: draft for the principal if existing CAS-owner appointment/deployment evidence does not settle A. No owner is appointed by this report. Reviewed source/design and exact scope: `OPEN_PREMISES.md`, R9 public-read trust entry and its path@sha citations.


## E02-ARCH-01/08 — execution profiles and protected invalidator ordering (pending decision draft; 2026-10-01)

**Decision status.** Pending. The architecture source supplies recommendations, not an adopted ruling. This draft states the choice between deferring a cross-owner strict-local guarantee and selecting it as a qualification target. Because the complete action set and individual owner appointments are not established, it is not yet a principal-ready choice of concrete runtime scope. It does not change R1's selected controlled-candidate path, Denis's R9 V2 production-approval refusal, or any finding status.

**Question.** Should PolicyOS retain bounded owner-local contracts without claiming a shared strict-local order, or select strict-local ordering for a bounded action set after its source callers and invalidators are named? Operated multi-host ordering is outside E02 in either choice and would require a separate future decision on transaction, custody, recovery, and failure model.

**Mutually exclusive options and costs.**

1. **Defer the cross-owner strict-local guarantee.** Keep existing owner-local contracts within their evidenced scope; carry the absence of a shared all-invalidators order as an explicit remainder. Cost: PolicyOS makes no strict-local cross-owner currentness promise for protected actions relying on those separate stores. Existing authority checks/refusals continue according to their own contracts. Candidate/history work proceeds with declared limits and typed unknowns; this choice does not add a blanket candidate refusal.
2. **Select strict-local as a qualification target for a bounded, owner-named action set.** At this step authorize only the decision contract and a complete source caller/invalidator census. The bounded source read found these existing action anchors: `ControlPlaneService.record_production_approval_packet` (control progress recording); `HumanDecisionService.create_record`, `resolve_production_approval_inputs`, and `resolve_production_decision_packet` (decision-record emission and production-input/packet resolution); `ArtifactOwnershipIndex.record_owner`, `record_view_owner`, and `FileSystemCAS.record_artifact_owner` (ownership claim emission). These are inventory seeds, not a selected strict-local scope or a complete producer-to-consumer map. Exact Control cancellation/fence and N11 activation/use action identities, all affected callers, and the individual participating owner appointments still need to be enumerated. No runtime change or admission guarantee is authorized until that named action/invalidator set and owner boundary are returned for principal review. Cost: owner/caller census, cross-owner contract, subsequent code/test work, and qualification of database/filesystem/runtime assumptions; the eventual guarantee is limited to the actions and failure model actually verified. Since that action scope is not yet complete, this remains a scope-discovery draft, not a ready-to-adopt concrete capability decision.

The two options are mutually exclusive on whether to select strict-local as a qualification target. Operated multi-host remains unclaimed under both and is not an independent alternative here.

**Premises.** E02-ARCH-01 separates candidate/history from strict-local protected issuance/current-use and retains normal authorization, tenant, valid-source, job-custody, DataTrust, and EvalSafety duties in candidate/history. E02-ARCH-08 gives the specific stale-view case: Core reads permit/fence 7, Control commits cancellation/fence 8, and Core commits using the old view. The current bounded source read identifies the methods above but does not provide a complete cross-owner census. In particular, a method that records a packet/claim or resolves production inputs is an action anchor, not proof that all cancellation, trust/policy, or N11 invalidators share its transaction. Runtime authority, artifact custody, and epoch lifetime are distinct roles, while the individual appointment and common transaction boundary are `not_established`. Reuse Core, Control, and N11 owners first. Same-host SQLite is a candidate mechanism, not a verified property; separate ATTACHed WAL databases, matching CAS roots, and unit-local locks do not prove one commit domain. Existing `OP-R9-PHYSICAL-CLAIM-LINEARIZATION` and `OP-R4-N11-LIFETIME` remain narrower premises, not substitutes for this decision.

**Remainder.** Neither choice establishes a distributed/multi-host guarantee. Option 2 authorizes only an action/invalidator census and decision contract until the exact names, owner joins, and relevant emissions are reviewed. It does not authorize implementation, a rollout, a new signature, or a protected admission. Existing R1/R9 decisions stay as selected. Ordinary candidate/history work and historical replay remain available subject to their existing contracts; normal authorization, tenant, source, job-custody, DataTrust, and EvalSafety requirements remain in force.

**Revisit trigger as falsifier.** After any action scope is named and an implementation is separately authorized, preserve its permit, cancellation, and publication markers; pause after its authoritative permit/fence read, commit the relevant invalidator, then resume the protected action. If it succeeds against the stale view, the strict-local ordering claim is falsified. Also require the ordinary candidate/history control to proceed with any unknown carried as a typed limitation. A design review or an owner-local guard alone is not closure evidence.

**Where it binds.** At present, this draft binds only the decision-contract and source-census choice. A later adopted strict-local contract may bind only its explicitly named authority admission, publication, custody, and current-use actions and their enumerated invalidators. It does not bind all protected endpoints by adjacency, block candidate computation/history replay, broaden the R9 V2 refusal, or relax ordinary safeguards. Pattern pass: P04/P05/P08 (status, authority, and time), P27/P31 (reuse owners and close the shared class), P37/P38 (name gate predicates and divergences), P40 (one class-wide mechanism, not instance rounds). No register, plan, or ledger status change is proposed.

**Source pins.** Recommendations: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/references/PolicyOS_E02_Architecture_Decisions_2026-10-01.docx@sha256:e7f98ddad1ba77c5d43345033daec8cc44ba12019f5a0eb3afbdae74c771e0a8`, E02-ARCH-01 at extracted line 93 and E02-ARCH-08 at line 273; extracted text `/Users/deniskopylov/.codex/scratch/E02R2_PRINCIPAL_ARCHITECTURE_DECISIONS_20261001/document-text.txt@sha256:4327b10d6b3e5ef9601a57e9f7f8a543d3caba1f61261a244dbbae4aa1c57561`. Traceability audit (not ruling): `/Users/deniskopylov/.codex/scratch/E02R2_ARCH_RECOMMENDATION_TRACEABILITY_20261001/architecture_recommendation_traceability.json@sha256:5cfbbbd97d919e7b1b9e1b75f4e6419b425be2d462255b010edb082b9a3f2b5a`.

**Observed action anchors at `0443e0643aa6aee44bd8dc1ee58b28f4fa8421a5` (bounded read; incomplete census).** `ControlPlaneService.record_production_approval_packet`: `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@git-blob:2290c7f28c463cd6b4a4366f6d8be52edbf3ece1#L3542`; `HumanDecisionService.create_record`, `resolve_production_approval_inputs`, `resolve_production_decision_packet`: `policy-engine/src/polisyos/runtime/http/services/human_decisions.py@git-blob:a5d8bfd7406d9caa5ec5b85532e48dd8660e3bd0#L1600,#L1971,#L2083`; `ArtifactOwnershipIndex.record_owner` and `record_view_owner`: `policy-engine/src/polisyos/core/artifacts/ownership.py@git-blob:021c850bf84518d856defd287373f883e7dbc1ce#L1001,#L1159`; `FileSystemCAS.record_artifact_owner`: `policy-engine/src/polisyos/core/artifacts/store.py@git-blob:730675df4c2964bf9ab1b1c5551cb8dd8162a27d#L589`. These names identify existing methods only; their listing is not an admitted scope or a complete invalidator census.
