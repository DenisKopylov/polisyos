# E02-R2 decision record drafts

**Status:** Denis's R1 option-A, R11 universal v3 blocked-run/N9-exclusion, and
R5 protected-mode EvalSafety fail-closed direction are recorded in dated sections.
R5 implementation is integrated at `f7d66883fbcb352eb923c23e3e104608490e8061`;
that does not close the finding. Its positive DataTrust bridge and complete
four-base whole-file P41 replay remain open, and the separate R1/R5 per-active-basis
proposal remains pending. Principal choices still pending are R2, R9, R13, and R14.
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
pending. The remaining principal proposals in this document are R2, R9, R13, and
R14. Earlier proposal text is retained as history; dated addenda supersede status
claims only where they explicitly say so. No governed reissue or restamp is
authorized by these records.


## DS16 / IR — versioned public uncertainty representation (B31, B201, B202)

**Status:** draft for the DS16 / IR contract owner; not adopted. The three findings
remain held. This draft records one owner decision per finding and gives a shared
schema direction where their public uncertainty representations intersect.

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
and served consumer exist. The DS16 / IR contract owner must rule; this draft is not a
principal ruling or authority admission. The three binding decisions are: **B31** —
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
producer-consumer paths only. No domain or jurisdiction profile is selected, no data
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

**Shared H14 partition check.** The exact row walk is: owner decisions `{B31, B201, B202, LA-005, LA-026, LA-027}` (6); data records `{B61, LA-010, LA-031, LA-049}` (4); smallest missing capabilities `{B194, B197, B219, LA-032}` (4). Across the same 14 Appendix-C rows, status remains 11 held, 2 partial (`LA-010`, `LA-049`), and 1 open (`B219`). This is a blocker-kind refinement only, not a status or behavior upgrade.
