# E02-R2 decision record drafts

**Status:** proposals for the principal; none is ratified by this file. Repeating a
lane lean does not make it a principal decision. The principal’s ruling, signer, and
date remain pending for R1, R2, R5, R9, R11, R13, and R14.

**Prepared:** 2026-09-24. **Code inspected:** candidate base
`73c656744f051d9f40667da7f8bc91c61d8b4ebf`. These records describe the proposed
disposition and its evidence. They do not assert that a repair or probe has run.

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
   depend on pre-enumerated owner state.
2. Remove context, source, and binding checks. This restores reachability quickly,
   but runtime and policy consumers bear the risk that caller-owned or mismatched
   world state is treated as grounded.
3. **Proposed lean:** let ordinary requests produce candidate work while carrying
   typed `not_established` context as a limitation. Keep N5, promotion, publication,
   protected modes, and S8 authority gated on their own owner evidence. S8 requires
   a real N4 source handoff that embeds the consumed `CycleSubstrateContext`, binds
   the exact problem/candidate bytes, and carries explicit tenant binding in its
   owner profile. Persist a typed context-limitation result as `not_established`
   when context is absent or tenant/currentness predicates lack owner evidence, in
   the existing content-hashed `CompiledRecursiveGenerationCycleRun` wrapper.
   Version it as schema v2 with a byte-exact historical v1 projection; S8 must
   consume the limitation so signed evidence alone cannot rank when context is
   `not_established`. The cost is wrapper versioning, exact v1 replay, and an S8
   consumer bridge; this adds no owner evidence. Context currentness must come from
   an existing owner; if none can establish it, S8 remains `not_established`. This
   preserves candidate access
   without creating a separate context artifact.
4. **Rejected option:** add a new root-context owner inside R1. This could
   supply positive evidence sooner,
   but would overlap R13's runtime-store repair and risk a second WMR/context owner.
   The existing WMR producer already accepts a supplied store; wiring that owner is
   the narrower route.

**Principal choice on the five existing normative fixtures.**

- **A — upgrade them.** Keep the `authorized` outcomes, but use a served real N4
  producer, the existing persisted source handoff, and owner-resolved
  tenant-context/currentness evidence. This preserves their behavioral intent, but
  depends on R13's store path and the missing context-owner capability.
- **B — keep them blocked.** Preserve fail-closed behavior until that owner
  capability exists, and change the old expected dispositions only after Denis
  explicitly rules the comparability decision. This accepts bounded loss of those
  authority outcomes; it does not justify refusing ordinary candidate work.

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

The HTTP function calls `_build_cycle_substrate_context_from_owner` whenever its
ordinary caller supplies no context; this is a production path, including the
`RunLifecycleService` worker, not only a test fallback. The
`root_n4_generation_port` argument defaults to `None`; the early refusal occurs
only when context is absent and a caller explicitly injects that port. The default
production route omits the explicit port, so removing that refusal can reach the
default N6 `grammar_fallback` candidate path. That path does not itself create a
real N4 `DesignGenerationOrganRun` or persisted `GenerationSourceHandoff`, and
therefore is not a B01–B03 served HTTP→N4→N5 witness. The ordinary candidate
control proves only candidate reachability. The helper calls
`production_composed_world_model_record(repo_root)`, whose implementation creates
`build_artifact_store(ArtifactStoreConfig(... root=.tmp/gy-s-composed-wmr-cas))`,
and separately builds a registry from repo-root catalogs. That path does not use
the runtime-supplied tenant-bound store and therefore does not establish root
context custody, even when the resulting context hashes validate
(`src/polisyos/runtime/http/services/control/generation_cycle.py@055cca6c9424deac61fa61543143a2a2d2310b1a`;
`src/polisyos/runtime/quality/intervention_substrate.py@e4c7c30f81438908688a169cb3d51fbd3f66be20`).
The underlying `build_production_data_state_world_model_record(store, ...)` accepts
a supplied store; correcting the wrapper to use it belongs to R13's root-rebuilt-
store write set and requires its shared lease. R1 must not build a competing owner.

`CycleSubstrateContext` is a candidate-only in-memory envelope: its typed
`authority_purpose` is `cycle_input_candidate_only`, and `may_not_use_for` excludes
authority. No independent pre-N4 owner persists and resolves a tenant-bound root
context. The compiled wrapper records `cycle_substrate_context_ref` as a
content-hash string, not an `ArtifactRef` or tenant-bound manifest, and currently
has no typed field preserving an absent context as `not_established`. Extend this
same hashed wrapper to schema v2 with that typed limitation and an exact v1
historical projection; S8 must load/consume the v2 limitation alongside signed
evidence. The current
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

**Proposed choice; principal status.** Adopt option 3 as the lane proposal, subject
to principal ruling. Preserve context content validation, but do not treat the
current repo-root fallback as proof of tenant-store custody. An ordinary request
with no established context may return candidate work and carry an explicit typed
unknown; it must not invent a WMR, catalog entry, or concrete scope. If that unknown
prevents a valid N5 world simulation, retain a typed pending/limited result. S8 may
emit a ranked recommendation only after it loads and verifies the real, persisted N4
handoff with its embedded `CycleSubstrateContext`, bound to the exact problem and
candidate identities. `GenerationSourceRepository.load(ref, run_id)` returns the
full `GenerationSourceHandoff`; `resolve(...)` returns a `GenerationSourceResolution`
projection, not the full handoff. S8 must use `load` or a strict owner extension
that verifies the full handoff. The handoff's owner profile must bind
`tenant_context`; do not make a second artifact for the embedded context. The
existing `build_production_data_state_world_model_record(store, ...)` is the named
WMR producer to wire through the runtime-supplied store under R13. It owns WMR
production; no separate pre-N4 tenant-context persistence/resolution owner is
identified. If that capability proves necessary, it remains `not_established` until
an existing owner is demonstrated, and R1 does not create one. Context currentness
must likewise be established by an existing owner or remain `not_established`; ambient
CAS custody and content-valid handoff replay alone do not prove it. A matching hash or
caller-injected context is insufficient. An N7 re-entry's prior handoff does not
prove its post-growth context; until a complete post-growth witness exists, S8
remains blocked for that source. The principal choice between fixture options A and
B remains open. No fixture may be counted as positive S8 evidence before that ruling
and witness.

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
- When context is absent, or tenant binding/currentness lacks owner evidence,
  persist a typed `not_established` substrate-context limitation in the existing
  content-hashed compiled wrapper v2, with a byte-exact v1 historical projection
  that excludes the new field. S8 must consume this limitation alongside signed
  evidence; signed-frontier validity cannot establish tenant binding or context
  currentness, which remain `not_established` until their existing owners provide
  those predicates.

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
world store, or convert an LLM candidate into evidence. The HTTP root builder is a
production caller but is not a compliant tenant-store owner path; its storage fix
belongs to R13's shared owner work. The existing `GenerationSourceRepository`
persists the full handoff containing the embedded post-N4 context, but S8 still needs
to load it; its write profile needs tenant binding, and context currentness must come
from an existing owner. The typed absent-context limitation must also persist in the
content-hashed compiled wrapper v2; its v1 historical projection must preserve old
bytes, and S8 must consume the limitation. No
separate pre-N4 context artifact/resolver owner is identified, so that requirement
remains `not_established` unless an existing owner is demonstrated. No S8 positive
claim is supported by the current `[authorized]` fixture alone. Its
signed-frontier semantics must remain covered. For the five normative fixtures, the
principal must choose whether to upgrade their base-pass authorization expectations
to real served N4/handoff/context-currentness witnesses or allow them to remain
blocked until the owner capability exists. Until the choice and four-base replay are
recorded, they are not positive S8 witnesses and their baseline disposition is not
finalized. The separate control-service `[authorized]` tenant-scope fixture also
needs a real owner/handoff witness or its own comparability ruling.
N7 currently rebinds a post-growth context without emitting a post-growth source
handoff, so that context remains `not_established` and S8 stays blocked until the
canonical owner path supplies a complete witness.

**Remainder standing and signatory.** An absent or unmatched substrate fact has
standing `not_established`; that does not put the ordinary request or candidate
capability on hold. The registered source owner signs any source fact it supplies.
If a separate pre-N4 tenant-context owner proves necessary, it remains
`unallocated/not_established` until an existing owner is named; R13 may wire the
existing WMR producer to the runtime store and use the existing N4 handoff boundary,
but does not appoint a separate context owner or institution. The HTTP/runtime composition owns carrying the typed unknown and
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
`src/polisyos/runtime/http/services/control/generation_cycle.py@055cca6c9424deac61fa61543143a2a2d2310b1a`
and the served `RunLifecycleService` caller; current fallback
`_build_cycle_substrate_context_from_owner`; WMR construction at
`src/polisyos/runtime/quality/intervention_substrate.py@e4c7c30f81438908688a169cb3d51fbd3f66be20::_production_composed_world_model_record`
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
   green. The current identity is computed inside private confidence-ledger
   functions; no
   public packaged API exposes this pre-N9 admission gate. Extend that owner and
   wire the gate before N9. Persist its decision in `GenerationCycleRun` v3 for
   later replay, but a v3 field constructed after N9 cannot authorize the N9 call
   that precedes it. Historical replay must not depend on today’s checkout. Require
   byte-exact v1 replay against the pinned v1 bytes; v2 byte-exactness remains
   `UNRUN` / `not_established` until an owner supplies an original v2 payload and
   byte oracle. The costs are a public owner API, pre-N9 bridge, schema migration,
   and historical payload/serializer evidence for each version.

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

**Proposed choice; principal status.** Adopt option 3 as the lane proposal, subject
to principal ruling. The source/deploy-time gate owns the census. Extend the canonical
identity owner to publish a typed identity/currentness contract from its existing
full inputs; do not compute a parallel identity in `generation_cycle.py`. At N6 run
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
  or a search-index result is insufficient (`consumer_asserted`).
- The canonical identity is recomputed by the confidence-ledger owner from the
  project and lock files, authority-import-closure files, Python runtime manifest,
  authority import closure, and loaded-code manifest. The field-level predicate is
  `recomputed`; exposing it through the existing owner to a run-start/pre-N9 typed
  admission bridge is currently `bridge_missing`. The gate must compare exact
  run-start, census-bound, and currently loaded identities before N9. A v3 field
  created after promotion is too late; missing evidence is `not_established` and
  mismatch is `stale`, either with no N9 authority while candidate work continues.
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
reconciled production call graph
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
green result falsifies the gate. In a separate stale probe, change a proven canonical
identity input between run start and pre-N9 admission: the status must be `stale` and
N9 must remain withheld. A preserving control supplies the unchanged, owner-admitted
identity and passing census at both points; if independent N9 gates pass, promotion
must proceed. Historical replay of the pinned v1 fixture must compare serialized
bytes exactly, while a historically valid run with no current identity remains
replayable with currentness `not_established`. V2 byte replay remains `UNRUN` until
its historical owner supplies the original payload and byte oracle; no current
producer-generated replacement counts. The `lex/simulator/report.py` comment probe
is not an identity-drift probe until import-closure membership and effect are
measured. For the strangle predicate, keep the `strangled` marker and direct-census
receipt but introduce an aliased or reflective production call to `run_fixture`; the
census must fail or return `not_established`, and N9 must remain withheld. A direct
call inside the currently exempt path must also fail unless a behavioral reachability
check independently establishes that exact caller as non-production. No blanket
path-prefix allowlist is an acceptable positive control. These are acceptance
requirements, not results recorded by this draft.

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
Witnesses must cover both behaviors in
`tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py@b675681a801cb9a66ec3ca80faf636fd91bc92d9`
and `tests/unit/runtime/http/test_normative_generation_bridge.py@ef8ec18a438afe790a0b03f35f90b9e90d6288d4`.

**Pattern pass.** P07/P08/P29/P35/P37/P38/P41. Existing anti-patterns are runtime
recomputation over an overbroad source denominator, a marker receipt without
deployment identity, and post-promotion persistence mistaken for a pre-promotion
gate. Target: one complete source/deploy census, the existing canonical identity
owner extended into a typed run-start/pre-N9 contract, and separate historical
validity from packaged `current | stale | not_established`. The private identity
calculation and current source check exist; the public packaged identity bridge and
pre-N9 gate are `bridge_missing`, while dynamic-call coverage remains
`not_established`. Acceptance requires marker-preserving removal and unchanged-
identity controls, byte-exact v1 replay, and an explicit `UNRUN` v2 result until an
original payload and byte oracle are owner-captured. The `lex/simulator/report.py`
comment probe remains unmeasured for import-closure effect. The P41 four-base JUnit
receipt for this regression class is pending the broker; this draft does not claim
the base-passing test set has been replayed or restored.

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
3. **Proposed lean:** distinguish an explicit candidate-only N6 computation band
   from an EvalSafety-evaluated run. Candidate-only computation carries no
   EvalSafety `ValuePort`, confers no authority, and records scope as typed
   `not_established`; it remains available when ordinary request context is
   unknown. Do not infer this band or `simulate_only` from a missing context.
   Whenever EvalSafety evaluates a leaf in `retrospective`, `measurement_audit`,
   `sandbox_pilot`, `field_pilot`, or `deployment`, that leaf must have a canonical,
   current EvalSafety context verified for it. The complete context-key set must
   equal the recomputed leaf set, including rejecting `{}` for a nonempty set.
   Runtime and EvalSafety owners pay for explicit band selection, a structural
   denominator guard, and current-head verification.

**Premises.** The public mode vocabulary distinguishes `simulate_only` from
`retrospective`, `measurement_audit`, `sandbox_pilot`, `field_pilot`, and `deployment`
(`pdc/_impl/evaluation_safety.py::EvaluationMode`). The evaluation-safety consumer
verifier already recomputes bindings, validity windows, evidence heads, and the
unique revision head (`runtime/quality/evaluation_safety.py::verify_evaluation_safety_consumer_admission`).
The recursive controller currently checks contexts only under
`if self._cycle_controller_factory is None`, and only checks the denominator when
`evaluation_contexts_by_node` is truthy; it also permits a nonempty substrate-context
map to satisfy the “context established” branch (`runtime/quality/recursive_generation_cycle.py`).
The HTTP composition deliberately passes `{}` when both EvalSafety and
`CycleSubstrateContext` are absent (`runtime/http/services/control/generation_cycle.py:665-669`).
That served ordinary candidate-only N6 path is not established as `simulate_only`.
S0-K06 keeps cheap candidate computation open while binding authority actions to
verified scope; ADR-0179 principle 4 calls over-refusal a defect
(`docs/adr/0179-correspondence-vocabularies-meaning-principles-first-profiles-open.md`).

**Proposed choice; principal status.** Adopt option 3 as the lane proposal, subject
to principal ruling. Use the already-owned EvalSafety verifier, not a new parallel
gate. Select candidate-only computation through an explicit typed band, with no
EvalSafety `ValuePort`, no authority, and a `not_established` scope limitation;
absence of EvalSafety or substrate context does not establish `simulate_only`.
Whenever EvalSafety evaluates a non-simulation leaf, compute the recursive leaf set
from the validated graph and require exact denominator equality on every controller
path, including rejecting an empty map for a nonempty leaf set. Refuse evaluated
authority-grade work if any leaf’s current safety head is absent, stale, mismatched,
or unresolved. A `CycleSubstrateContext` is not an EvalSafety context. The ordinary
contextless candidate route remains available only under the explicit candidate-only
band and cannot authorize promotion, publication, or deployment.

**P37 — gate predicates at admission.**

- Leaf membership is recomputed from the validated recursive graph (`recomputed`).
- Canonical execution band and mode are taken from their verified owners
  (`recomputed`); a missing context or request mode token alone is
  `consumer_asserted` and cannot select candidate-only or downgrade an evaluated
  non-simulation request.
- Context-map completeness is the equality of the exact context keys and graph leaf
  refs for an EvalSafety-evaluated run, including the empty-map case (`recomputed`).
- A supplied `EvaluationExecutionContext` is only caller input until the EvalSafety
  owner verifies its exact binding, valid time, current evidence, and revision head
  (`independently_reconciled`). Missing verification is `not_established` and blocks
  an EvalSafety-evaluated non-simulation leaf; the explicit candidate-only band
  carries `not_established` as a limitation and has no EvalSafety result or authority.
- Substrate context may support candidate/world binding but never stands in for
  EvalSafety (`not_established` for the safety predicate).

**P38 — property and divergence.** Property: every EvalSafety-evaluated
non-simulation recursive leaf has its own current EvalSafety head, regardless of
factory or context map shape, while ordinary candidate-only N6 remains possible
under unknown scope without creating an EvalSafety result. Current implementation:
the denominator guard is inside the no-factory branch and skips equality for an
empty context mapping; HTTP also passes `{}` when both contexts are absent without
an explicit candidate-only band. Divergent cases: an evaluated graph with one leaf
and `evaluation_contexts_by_node={}` does not raise the denominator mismatch; a
controller factory also bypasses the guard; and a contextless ordinary request
does not carry a typed candidate-only limitation. The evaluated-mode property fails
while the present predicate can be green, and simply making absence fail closed
would violate the candidate-band property.

**Remainder.** Neither candidate-only N6 nor `simulate_only` is safe for promotion
or publication; authority remains separately gated. Candidate-only computation
records the unknown scope as `not_established` and emits no EvalSafety result. Any
EvalSafety-evaluated non-simulation leaf remains blocked until its exact current
context is verified. The candidate-only band must be explicit in the run record.

**Remainder standing and signatory.** Missing, stale, or mismatched EvalSafety
evidence has standing `not_established` and blocks every EvalSafety-evaluated
non-simulation leaf. Explicit candidate-only computation records that same unknown
as a typed limitation and proceeds without an EvalSafety `ValuePort` or authority. The
existing consumer-admission verifier in
`runtime/quality/evaluation_safety.py` owns the software check; its module explicitly
does not make an institutional appointment, and this record names no external
evidence signer. The recursive runtime owns enforcing the denominator and selecting
an explicit candidate-only band, but cannot sign EvalSafety evidence. Denis remains
the pending principal signatory for this proposed mode boundary; candidate-only
cannot be inferred from `simulate_only`, absent context, or a caller token.

**Falsifier / revisit trigger.** Reopen if any EvalSafety-evaluated non-simulation
leaf proceeds with a missing, empty, incomplete, stale, or foreign EvalSafety
context; repeat with a custom controller factory. An empty map for a graph with a
nonempty evaluated leaf set must refuse. The positive control is the served
contextless ordinary candidate route: with an explicit candidate-only band it
proceeds, records scope `not_established`, emits no EvalSafety result, and cannot
cross an authority gate. These are required tests; none is claimed as run here.

**Where it binds.** Structural check in
`runtime/quality/recursive_generation_cycle.py::RecursiveGenerationCycleController.run`;
mode, context currentness, and revision-head admission in
`runtime/quality/evaluation_safety.py::verify_evaluation_safety_consumer_admission`;
promotion/publication consumers retain their own authority checks.

**Pattern pass.** P04/P05/P37/P38. The existing failure is a conditional guard whose
implementation checks a proxy for “context provided” instead of exact current
coverage. Target: graph-derived denominator plus the canonical current-head owner.
The verifier exists; structural coverage over all evaluated controller paths is
`verification_missing` until the empty-map/factory falsifiers and the explicit
candidate-only served control pass.

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
   while adding independently persisted typed view records/manifests bound to the
   content hash, full profile, and tenant ownership. A returned view must resolve
   its own exact manifest/profile and tenant binding. Signature verification is
   required only where the caller or authority contract requires signed custody;
   unsigned candidate bytes remain valid CAS content. When required, signatures and
   ownership resolve by the typed view identity, never by content `ArtifactID` alone.
   Permit cross-tenant views only if view records and any required signatures remain
   isolated per tenant; until the shared owner can prove that isolation, keep the
   existing typed refusal for cross-tenant view requests. CAS/API owners pay for
   tenant-scoped metadata, versioned refs, import/export and signature handling;
   callers do not need envelope hacks or duplicate payloads.

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
test blob identities are recorded.

**Proposed choice; principal status.** Adopt option 3 as the lane proposal, subject
to principal ruling. Keep blob identity as the hash of exact bytes, but define typed
view identity to include its full immutable profile and tenant ownership. A view is
usable only after resolving its exact persisted manifest and recomputing the byte,
profile, and tenant binding through the runtime-supplied store. Keep bare
`ArtifactID` as the primary legacy reference to the historical manifest; a
qualified view reference must resolve its own view record and must never fall back
to the bare ID, primary manifest, or their signature when that view is missing.
Unsigned candidate artifacts may be stored and resolved without a signature, but
they carry no authority. Verify a signature only where the consuming contract
requires one, and then bind it to that exact qualified view and tenant; never reuse
an ID-only or other-view signature. If that required signature is absent or
unverifiable, the authority consumer returns a typed refusal. Preserve historical manifest and signature
bytes byte-exactly. If a qualified reference changes `ArtifactRef` or `InputRef`
nested in hashed DTOs, use a separately versioned qualified reference with
historical serializers that exclude it, or bump the enclosing schema and add a
historical serializer that preserves the old projection byte-for-byte. If the common
owner cannot provide per-view tenant isolation, cross-tenant views remain refused
rather than sharing ownership by content hash.

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
complete caller census is a closure gate. Existing lowering surfaces that need
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
`same_input_closure`, `authority`, and the ordered typed `warnings` list. Warnings
are included because they are persisted producer/runtime claims; a changed warning
must not silently reuse a view whose manifest says otherwise. The current
`ManifestLifecycle.profile_mismatches` omits `warnings`, so the view owner must
extend that projection and its write contract to carry them. Canonicalize this
projection with the manifest serializer's stable JSON rules: JSON-mode fields with
aliases, `exclude_none=True`, sorted object keys, and list order preserved.
Derive the qualified view key from a versioned envelope containing the exact
payload SHA-256, the runtime-resolved tenant/cell owner identity, and the canonical
profile projection. `artifact_id` is excluded from the profile projection but the
payload digest remains an outer view-key input so different bytes never alias;
`created_at` and the `integrity` envelope are excluded because they are
instance-derived/time-derived and the payload digest is validated separately.
Include `byte_size` in the profile and recompute it from the exact payload, even
though equal payload bytes necessarily have equal size. Same-profile retry means
the same payload digest, resolved owner identity, and byte-exact canonical profile
projection; it converges on one view record. A required signature binds to that
view key but is not itself an input to the profile projection. The current manifest
serializer/projection source is
`src/polisyos/core/artifacts/_manifest_lifecycle.py@0681605eed226b2638dce4cb9d7b9e710491323d`;
warnings are a persisted `ArtifactManifest` field at
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
  and runtime-resolved tenant/cell owner. The projection includes warnings so the
  persisted claim set cannot be silently changed on reuse; this binding does not
  independently prove the warning claims themselves.
- Tenant quota admission must recompute/reserve the bytes for the exact primary
  and view metadata, plus any required signature sidecar, before publication. The
  current `len(data) + 4_096` estimate is `not_established` as a bound on variable
  sidecar size; no view may publish until the required incremental bytes are admitted.
- `ArtifactRef` and `InputRef` are nested in persisted manifests and other hashed
  DTOs. Any qualified-ref extension must preserve historical projections byte
  exactly by versioning the qualified ref or the enclosing schema and serializer.
- Equal bytes never imply equal lineage or provenance. Any absent lineage relation
  remains `not_established` rather than inferred from the shared blob hash.

**P38 — property and divergence.** Property: content may have multiple typed
views only when each view's exact profile and tenant owner are independently
resolvable, and when a caller requires a signature, that signature resolves for
that view. Current implementation: `ArtifactOwnershipIndex` and signature
operations key only on content `ArtifactID`; the store can therefore confuse
same-byte tenant views, while CAS signing is optional. `ManifestLifecycle.profile_mismatches`
checks the write profile fields but omits persisted `warnings`; two manifests that
differ only in warning claims can therefore pass the current profile comparison
(`src/polisyos/core/artifacts/_manifest_lifecycle.py@0681605eed226b2638dce4cb9d7b9e710491323d`).
`TenantScopedCAS.put_bytes` preflights `len(data) + 4_096` before
publication and does not size a proposed view sidecar
(`src/polisyos/fabric/storage/tenant_cas.py@d45d8a5856d38fed50f8fe3a1e24e8cb92858164`).
Divergent cases: an ID-only
ownership/signature check cannot distinguish tenant A from B; a warning-only
profile change is ignored; and a variable sidecar may exceed the fixed allowance
used by the current quota predicate. The distinguishing probes must create
same-byte views under two tenants, sign only view A, and prove that an
authority-contract read of view B remains unverified and refused; a candidate read
may resolve only if B has its own exact tenant-bound view. An unsigned candidate
control with `SigningConfig(enabled=False, sign_on_put=False)` must resolve its
exact manifest as candidate content without producing authority. A warning-only
change must produce a distinct view key; an identical same-profile concurrent retry
must converge. A quota case with available capacity below the exact sidecar size
must refuse before publishing the view. Both valid candidate views may still
resolve to one physical blob.

**Remainder.** This does not claim equal bytes have equal empirical origin,
authorize changing an existing profile, or decide that all kind and lineage fields
can be verified by the CAS itself. Consumers that need source independence still
require their own evidence. Per-view concurrency and cross-backend compatibility
remain implementation obligations. Cross-tenant view creation stays refused until
per-view ownership isolation and any contract-required signature binding are proven;
the shared content hash never substitutes for tenant custody.

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

**Falsifier / revisit trigger.** Reopen if any backend returns a view ref whose
resolved manifest differs from it, if concurrent same-profile retries create
divergent duplicate view records, if a tampered view can point at a different
blob/profile while retaining a green verification result, or if a signature for
tenant A's view verifies tenant B's same-byte view. The acceptance signal is the
A/B same-bytes witness through filesystem, S3, GCS, and caching-store contracts:
both view manifests resolve only under their own tenant and exact profile; signing
only A cannot satisfy a contract-required signature check for B. A distinct
positive control stores and resolves unsigned candidate content under
`SigningConfig(enabled=False, sign_on_put=False)` without producing an authority
result. A qualified-reference removal probe keeps the bare primary artifact and
its manifest/signature intact while removing the qualified view; lookup must refuse
instead of falling back. Preserve the historical primary manifest and signature
bytes through export/import and historical-reader round-trip byte-exactly. Remove
tenant metadata while preserving view markers and bytes; the tenant-bound access
must fail. The profile projection probe changes only `warnings` and requires a
different view key; the positive retry control holds payload, owner, and every
projected field fixed across concurrent writes and requires one stable view key.
Changing only `created_at` must not change that key, while a different payload
digest must. A quota probe leaves enough capacity for the current `len(data) +
4_096` estimate but not the exact serialized view and any required signature
sidecars; the store must refuse before publishing the view. A
`.views/<profile>.manifest.json` sidecar cannot simply reuse today's
recursive `*.manifest.json` namespace: the filesystem enumerator parses the basename
as an `ArtifactID`; the sidecar layout or that shared enumerator must change as one
owner-level design. View sidecars also count toward the tenant's quota. Caching,
async, IR, and ProgramGraph paths must preserve the qualified selector and complete
write profile end-to-end. `CachingArtifactStore` currently addresses manifests by
bare `ArtifactID` and reconstructs cache-population `PutOptions` without
`tenant_context`, `same_input_closure`, or `authority`; async/IR adapters and the
current `LoweredIRRef`/`ProgramGraphRef` likewise have no qualified selector, and
ProgramGraph lowering reconstructs refs from the bare ID. No such run is claimed
here.

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
No caller may
construct an envelope to compensate for a missing CAS view API or tenant-bound
signature owner.

**Pattern pass.** P05/P27/P31/P32/P37/P38. The instance symptom is a CAS conflict;
the class is the mismatch between a content key and a single semantic view. Target:
one generic, typed multi-view contract implemented by the shared owner, not
consumer-specific exceptions. A second R9 symptom is a boundary loss of the view
selector; it remains the same P40 class because every escape is a consumer of the
same artifact-view identity. Multi-view refs/artifacts are `artifact_missing` and
consumer resolution is `consumer_missing` until manifests, required-signature
semantics, quota accounting, every backend/adapter, historical replay, and the
positive/negative witnesses are wired.

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
chain (`runtime/quality/generation_cycle.py`). The canonical served bridge’s
existence does not fence this second arm: the production N7 caller invokes the local
helper without an execution-scope or contract-testing guard, and the helper itself
does not require one. A route payload can therefore reach the local reconstruction
from the production N7 path. The missing tracked production producer is not the
safety boundary; the reachable helper must be structurally refused in production or
its input must be admitted through the canonical bridge
(`src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`;
`src/polisyos/runtime/http/services/acquisition_surface_execution.py@74bfe81aa16b00561c7650032593bd2be722d67e`;
`src/polisyos/runtime/quality/acquisition_world_growth.py@e5caf4ccb42af91418472269bb052b8cf4db71fc`).

Root-rebuilt store repairs are a separate mandatory custody obligation and are not
discharged by choosing option 2. The five constructor sites to route through the
runtime-supplied store are: (1) `generation_cycle.py::_joint_simulation_result_store`
(`.polisyos/cas`); (2) the composed-WMR NCM read (`.tmp/gy-s-composed-wmr-cas`);
(3) `generation_cycle.py::_rebuild_n7_acq01_route_context` (route-provided
`capture_store_root`); (4) `acquisition_planner.py`'s `FileSystemCAS(cas_root)`
used with `.n7-live-cas`; and (5) `foundry/plugins/training_adapter.py`'s
`FileSystemCAS(output_dir / "artifacts")`. Contract fixtures may use isolated test
stores only while explicitly non-authoritative. The count is the five tracked
`FileSystemCAS` constructor sites in these R13 write-set modules; it is not a claim
that every use of file-backed storage repository-wide is a root-rebuild defect
(`src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`;
`src/polisyos/runtime/quality/acquisition_planner.py@7e2e5a189da71145dbcbc347c04ee92e6be0aaa1`;
`src/polisyos/foundry/plugins/training_adapter.py@c97231729436ec2a44ae1c3b6d7b79dafb9a1de9`).

**Proposed choice; principal status.** Choose the confinement arm of the assignment
lean, pending Denis’s principal ruling. The served WDI bridge exists, but tracked
source does not establish a separate production ACQ-01 producer and its caller
handshake that can be wired to that bridge. Confine the local route to explicitly
non-authoritative contract-testing/demonstration and prevent it from minting a
production WMR or re-entering production N7. Keep the served WDI path on the
existing `AcquisitionWorldGrowthBridge`; do not add a second production producer
or change that working bridge. ACQ-01 may be reconsidered for production only after
an actual producer and its typed request, authority/journal, overlay, passport,
native-epoch, tenant-store persistence/readback, and served consumer handshake are
demonstrated end to end. This is the proposed choice within the assignment lean,
pending the principal decision; it is not an implementation claim.

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
context, with no execution-scope/contract-testing guard at the production call or in
the helper. Divergent case: a fixture-produced route payload supplied to a production
N7 run can create a WMR and re-enter the cycle without overlay admission, passport,
epoch receipt, or the runtime store’s tenant guard. The route’s production producer
being absent from tracked source does not remove this reachable bypass. A production
tenant-transfer probe must also fail through the guarded store, not only through a
raw filesystem store. Separately, E02’s split between stable
`design_problem_ref` and revised `design_problem_basis_ref` is not closure evidence:
its effect on main’s same-case world-growth and movement semantics has not been
measured. A stable subject label can coexist with a changed basis, and this draft
does not establish that every movement/re-entry consumer preserves the intended
subject while validating the revised basis.

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
`7c4b73fb339f36b21bcc430c1260f35d76a745d6`. The R14 reviewer's provisional relative-run comparison reports pass at E02's base
and main and fail at E02's head and the Phase 0 merge, with that source blob
unchanged; this report is not yet admitted as P41 evidence. The full four-base
P41/JUnit row receipt is pending the baseline broker:
`docs/plans/active/agent-packages/PolicyOS_E02R2/raw/r14-p41-wave5-test.xml@PENDING_SHA256`
(no receipt exists at draft time). The broker must record outcomes, flags, and test
blob identity before that pending citation is replaced with a computed SHA. Until
then, the reported relative outcomes are a hypothesis to re-verify, not admitted
P41 evidence; when confirmed they establish present path retirement, not that the
historical W5 claim was false.

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

These seven drafts are proposals only. The lane has not recorded a principal’s
acceptance, implemented the proposed repairs, run their falsifiers, or authorized
any governed reissue. A principal ruling should be appended with its date, named
decision, evidence that moved it, and any changed remainder; it should not be
backfilled as though already granted.
