> Canonical allocation: [integration boundaries](../architecture/01-integration-boundaries.md) and `tasks.json` govern shared writers and cross-stream prerequisites. Local task dependencies in this narrative are supplemented there.

# Post-E02 R9 lifecycle and resource workpackages

Status: planning artifact only. Runtime and acceptance execution are UNRUN. Work begins only after E02 is accepted, the applicable source set is frozen, and each owner path is rebound to that accepted source. This memo is not an SDD, implementation, production runbook, or proof of capability.

## Basis and boundary

Pinned G checkout at planning time: d40bca270ef5c456e8233196e4d8d65e099777a7. The immutable CodeC reference is dccea950845cda5b38f026e7770c07819d31f4d9 and is not an ancestor of G. CodeC is used only for small static owner-seam reads; no runtime behavior is claimed. Rebind all paths and symbols at W0 after E02. Do not carry any CodeC witness forward if accepted E02 changed its owner or behavior.

Primary R9 proposal tables: external-foundations/lifecycle/05-implementation-protocols.md, 06-delivery-and-review.md, 08-incidents-and-edge-cases.md, 09-resource-execution-design.md, 10-adversarial-review-and-delivery.md; acquisition/03-storage-and-reuse.md, 05-implementation-and-review.md, 06-operational-continuity.md. The tables are the obligation denominator for this plan: R01–R12, T01–T20, W0–W6, AP01–AP19, E01–E15, X01–X08. This is a crosswalk over those named source tables, not a census of the repository.

Policy boundary: extend existing owner seams. Do not create a universal lifecycle/status service, global permission token, global distributed lock, resource scheduler, generic temporal envelope, or new sovereign subsystem. Keep network-source protocol/capture with CAP; this work consumes CAP’s verified receipt. Keep deployment bootstrap, host provisioning, and backup topology with OPS; this work consumes the accepted profile and tests owner contracts. PolicyOS owns only its signed claims and the evidence contract for external acts; external provider, institutional authority, and physical-media guarantees remain typed evidence or bounded limitations.

## Pattern pass and evidence

Relevant failure patterns: P01/P02 (contract-only/thin orchestration), P04/P05/P09 (status/authority/soft-gate lifecycle), P07/P08 (replay and time-role), P10/P14/P15 (semantic adequacy, independence inflation, candidate laundering), P25/P27 (search frontier and owner bypass), P29/P31/P32 (form proof, instance patch, trust-by-form), P35/P36 (complete denominator and source-ID citation), P37/P38 (predicate classification and property/proxy divergence), P39/P40/P41 (mechanism budget, repair ladder, inherited-red provenance).

Concrete static witnesses, bounded to CodeC dccea950:
- R03/P02: scientist/validation/decision_validity.py::record_dependency_event writes the dedupe marker before applying the event to existing dependency rows; a new subscriber/event ordering needs enrollment plus replay, not just dedupe.
- R05/P10/P32/P38: scientist/validation/claim_support.py::_satisfied_predicates treats nonempty references/strings as satisfying selected predicate kinds. Required property is resolved, content-bound semantic support with verifier provenance. A fake reference is a divergent case.
- R01/AP04/P38: fabric/data_plane/cursor_store.py::CursorStore.save_partition_state serializes writes but does not compare the expected prior head or attempt fence before replacing it. Delayed A can overwrite committed B. A file lock is not a stale-commit fence.
- Resource limitation: core/artifacts/store.py::open_member and open_member_bounded verify a full selected member while reading; bounded buffer does not establish sublinear I/O. runtime operation intent records distinguish pending/completed/refused/unknown/recovery_required and explicitly do not promise external exactly-once. Existing retention planning and lineage are contracts/graphs, not proof of all-copy purge or semantic dependency.

Target pattern: one owner-local admission or commit chokepoint; resolve and bind the actual artifact, authority, rule, time, purpose, and use; persist a typed event/receipt; bridge it into the current consumer; expose scoped limitations; demonstrate both a live positive path and a property-removal probe. Capability states remain precise: generic source event-to-publication currentness is bridge_missing; inspected semantic support is verification_missing at its consumer boundary; full all-copy deletion/restore is absent/unallocated beyond inventoried owner scopes; cross-process multidimensional capacity is absent/unallocated; durable external-effect duty needs a bridge from the existing runtime intent to an outcome consumer; semantic derived/cache/learning invalidation needs a bridge. No R9 table by itself upgrades these states to implemented.

For every gate, classify each deciding predicate at admission: recomputed (content digest, exact local rule evaluation), independently_reconciled (complete owner inventory/frontier comparison), institutionally_supplied (source cut, license act, provider receipt), consumer_asserted (caller says complete), or not_established (unknown influence or missing evidence). Only the first two can independently carry authority-grade green. Name proxy divergences: ref presence vs content support; lock serialization vs expected-head CAS; policy impact plan vs physical copy deletion; estimate/lease vs enforced resource bound; saved projection vs live source/right currentness.

## Executable workpackages

The canonical machine-readable row set is [tasks.json](../tasks.json). It contains LIF-01 through LIF-09 with owner paths marked verified (static CodeC evidence only) or proposed (to rebind after E02), local dependencies, external seams, deliverables, acceptance probes, surfaces, resource locks, rollback and migration notes.

- LIF-01 admits a specific relation and use. Preserve assertion, assessment, and use as distinct typed owner records. Bind exact ArtifactRef/profile and content, proposition/polarity/population/unit/scope, verifier/provenance, rule version, time roles, authority purpose and audience. Carry selection trace and model/evidence denominator separately; no generic independence credit.
- LIF-02 enrolls dependencies against source generations. Record input cut C, enrollment high-water W, replay floor and source journal identity. Replay (C,W] before relying on the dependency. Make source generation and invalidation event atomic where the source owner can; otherwise use prepare/reconcile or a declared cutoff. Public commit participates in a currentness fence over enrolled source and right cuts. Coarse invalidation may precede bounded precise reassessment.
- LIF-03 commits capture progress conditionally. CAP owns source reads, pagination, representation validation and source-cut evidence. This task accepts only CAP’s verified receipt and adds the owner-local cursor expected-head/attempt fence, durable receipt-before-frontier ordering, crash recovery and stale-writer rejection. Sparse source offsets remain legal; never infer continuity from max offset.
- LIF-04 extends the existing long-running runtime duty. Keep intent, attempt, provider effect, receipt and final local commit distinct. Use stable effect identity/request digest, bounded retry/cooldown and recovery reconciliation. Cancel has an explicit race with external accept and local publish. Unknown effect is not success and not permission for blind repeat; do not claim exactly-once.
- LIF-05 fences rights-sensitive writes and manages copy outcomes within the actual owner inventory. Enroll write intent before materialization; check the relevant authority/use generation at commit; pin/drain active readers; quarantine restored state until post-backup rights decisions reconcile. Report membership removal, managed-copy deletion and physical/provider/backup scope separately. No zeroization or universal erasure claim.
- LIF-06 enforces bounded execution in the existing resource owner(s), if one is accepted. Account separately for resident/native/IPC memory, disk output/spill/checkpoint/old-new generations, CPU/IO/network/provider spend, queue and metadata. Reserve worst-case terminal fan-in; propagate or release parent reservations before child waits; leases do not prove worker termination. Stream bounded windows, spill only to governed storage, retain a custody/control lane over bulk work, and make saturation explicit. Do not build a global scheduler.
- LIF-07 binds derived artifacts, caches and learned influence to actual parents and use. Reuse ArtifactManifest/InputRef and the lineage graph; add owner-local semantic/right/model/rule/source-generation and exact selection dependencies. Cache identity includes audience, purpose and resolved inputs. Confirmatory use requires method-valid evidence and correction/reassessment when affected; exploratory candidates stay visibly lower authority.
- LIF-08 composes the second source after source freeze and review. CAP owns the second-source capture path; OPS owns bootstrap/deployment/backup topology. This task checks that the admitted receipt/profile, compatibility, source-specific cuts, consumer, migration roots and old-reader retirement compose without inventing a global snapshot. Unknown required semantics refuse that use; optional unknown facets remain inert.
- LIF-09 is the integrated acceptance/review receipt, not another mechanism. Run only after the source set and all owner changes are frozen. Record the exact commands, inputs, complete outputs, removals, resource denominator and limitations. If review changes a source or consumer after the resource wave, reprice the wave. Runtime remains UNRUN until an executor runs the acceptance plan on the accepted implementation.

## Source crosswalk: complete relevant tables

R obligations (lifecycle/06-delivery-and-review.md §1):
- R01 → LIF-03: stale snapshot/delete, max-offset gaps, adapter cut/overlap/incarnation/schema/continuity witness; sparse offsets are valid.
- R02 → LIF-02: a newly matching record invalidates a negative/set result; scope generation first, exact index second.
- R03 → LIF-02: dedupe-before-enrollment gap; enrollment plus replay after high-water and replay-floor check; dedupe follows committed effect.
- R04 → LIF-02/LIF-09: unchanged head with source/permission drift while scheduler is down; writer-participating cut/expiry or qualified cutoff, not optimistic snapshot.
- R05 → LIF-01/LIF-07: references are not semantic support; bind assertion, assessment, use and content predicate.
- R06 → LIF-01/LIF-07: repeated studies are not independent; retain denominator and selection trace outside evidence-slot counting.
- R07 → LIF-05: applicability/precedence/effect-time decision before rights fence; distinguish revision from actual revocation and preserve alternatives/irrevocable grants.
- R08 → LIF-05: enroll writes, commit fence, restore quarantine and post-backup decisions; incomplete inventory is not full deletion.
- R09 → LIF-05: unlink/membership differs from physical erasure; identify placements, deletion scope and replay limitation.
- R10 → LIF-04: external effect with lost reply/expired idempotency; preserve duty/intent/attempt/effect and reconcile provider window.
- R11 → LIF-08: second source/plugin must preserve semantics and budget; real second-source witness, directional compatibility, separate root publish and delete fences.
- R12 → LIF-01/LIF-06: avoid indiscriminate mandatory verifiers; owner handoffs, candidate exploration and audience-scoped projection.

W protocol rows (lifecycle/06 §3):
- W0 → LIF-01/LIF-09: freeze sources/callers/sibling consumers, owner contracts, commit domains and selected protocol; name one owner per generation/source/use/store; decide transaction vs prepare/reconcile/cutoff.
- W1 → LIF-03: capture/resume to exact receipt → verified frontier → sealed root → fresh selected reader; retain partial API semantics.
- W2 → LIF-01: assertion/assessment/use, relation, rule, original/translation occurrence, negative dependencies and selection trace.
- W3 → LIF-02: Claim Ledger/Decision Validity plus source owner/publisher; event-before-enrollment, duplicate-before-effect, publication race, scheduler down and generation-before-fanout.
- W4 → LIF-05: rights, copy enrollment/restore, all actual writers before sensitive materialization.
- W5 → LIF-04/LIF-06: use existing ControlPlaneStore transaction/outbox, outcome inbox, due/cooldown, retries, cooperative cancellation, recovery, actor recheck and reserve.
- W6 → LIF-08/LIF-09: second source after freeze/reviews, distinct layout/page pattern and consumer, qualified source cuts, compatibility, old reader, migration/GC roots and one bounded resource wave.

T acceptance rows (lifecycle/06 §4):
- T01–T04 → LIF-03: concurrent update/delete; sparse offsets vs dense gap/filter; reset/schema/selector/log expiry; crash page/cursor, unreadable child and 304 without exact retained body. No resurrection, double effect, or empty-as-complete.
- T05–T08 → LIF-02: change around enrollment, replay floor and crash marker/effect; material source/rights race; scheduler off/expiry/refusal; matching-record addition. No missed invalidation, cached green, overbroad invalidation or universal-absence claim.
- T09–T10 → LIF-01/LIF-07: same refs with wrong polarity/unit/population/legal scope; common cohorts, selection frontier, no-hit vs equivalence. No false support, independence, all-data or “best” claim.
- T11–T14 → LIF-05: license revision vs applicable revoke; revoke during check/write/stream; stale restore; shared CAS/WORM/provider/backup copies. No blanket deny, late write, resurrection or false all-copy deletion.
- T15–T17 → LIF-04: provider effect/reply loss/idempotency expiry; cancel before/after remote acceptance and local lease loss; duty over releases/checkpoint migration/history compaction. No blind repeat, false-stopped status or lost duty/history.
- T18 → LIF-02/LIF-08: independent cuts, backdated event, storm, lagging reverse index. No global-snapshot claim; append action history and bound pending work.
- T19 → LIF-08: unknown optional vs required facet, stable schema/new meaning, mutation during index build. Preserve optional inert, block required unsupported use, prevent mixed generation/fallback.
- T20 → LIF-04/LIF-06/LIF-08: provider 429/global method state, root added during GC and expired writer. Quotas/pools and overload explicit; root/delete fence; no stale publish. These subcases remain separately asserted.

AP rows (acquisition/05-implementation-and-review.md §4; conditional activation is part of the row):
- AP01 → LIF-01: preseed/runtime same capture/use; removing terminal receipt while keeping label must fail.
- AP02 → LIF-01: saved-source reuse rechecks purpose/rights/profile.
- AP03 → LIF-03: 304 without exact prior body refetches or stays unavailable.
- AP04 → LIF-03: paginated mutation/crash/missing/repeated pages, stale resume A after B, and range validator/content encoding/Content-Range. CAP owns protocol; cursor task owns commit fence.
- AP05 → LIF-08 seam only: prompt injection, redirects, DNS/socket/proxy/credential checks and query privacy are CAP-owned when activated; no duplicate capture/security implementation here.
- AP06 → LIF-01: legal act/version/current/historical/future/repeal/translation/notification receipt; no-hit is not absence.
- AP07 → LIF-05: cumulative disclosure across aliases/audiences/runs and timeouts; no prohibited raw copies; new draw/audience remains distinct.
- AP08 → LIF-04: wrong remote snapshot/executable/recipient receipt rejected; unknown effect not blindly repeated.
- AP09 → LIF-05/LIF-08: each actual surface enforces target owner/applicable grant; authorized sharing positive; foreign/nonexistent same not-found projection.
- AP10 → LIF-06: memory/disk/provider contention defers boundedly; lease does not release held memory; real billable account is not reset by retry; no hard cap without measured denominator.
- AP11 → LIF-05: migration/restore cannot resurrect revoked generation; reconcile heads and post-backup histories using actual store backup protocol.
- AP12 → LIF-08: supported source/profile extension through existing owner registry; unknown semantics remain candidate.
- AP13 → LIF-04 conditional seam: real institutional response is bound to issuer/original; draft/signature is not authority. Implement only if selected capability uses it.
- AP14 → LIF-07/LIF-05: shared or mixed derivative binds exact parents/output permission; no false independence or cross-tenant cache existence leak.
- AP15 → LIF-07: cold/expired/unavailable derivative is not empty; rebuild under actual rights/model/source generation and do not substitute source without rebinding.
- AP16 → LIF-08 seam: trust bootstrap/succession, old-root rollback and historical vs current use are OPS/institutional prerequisites if activated; no self-consistent provision proof.
- AP17 → LIF-04/LIF-08: service duty transfer/cutoff and offline reader expiry; no false current badge. Consume OPS continuity mechanism, do not build deployment bootstrap.
- AP18 → LIF-07: learning outcome exposure invokes confirmatory method correction and relation recommendation→act→exposure→outcome; candidate/exploratory work remains lower authority.
- AP19 → LIF-01/LIF-07: anonymous human occurrence gains no invented identity/independence; bound translation challenge reassesses affected uses only.

Adversarial tables:
- E01–E02 (lifecycle/10 §1) → LIF-06: simultaneous terminal fan-in exhausts reserve; nested parent/child holds deadlock. Reserve full fan-in or joint peak/checkpoint-release.
- E03, E10, E15 → LIF-04: cancel/commit ordering; visible provider effect with lost receipt and compaction; control-store unavailability. No false stop, blind repeat, or cached green/second sovereign plane.
- E04 → LIF-02/LIF-03: lost CDC interval/skewed reads; require remote-cut to local mapping or a qualified common cut.
- E05–E08 → LIF-05/LIF-06: revoke before first disclosure/cache waiter; restore rollback closure; compaction hiding public revoke; mmap/native reader after unlink. Fence admission, quarantine restore, preserve causal public interval, drain pins; no delivered-byte recall or zeroization assertion.
- E09 → LIF-08 seam: parser external-reference fetch is CAP-owned; per-operation fetch/redirect/address checks required if selected.
- E11–E13 → LIF-07/LIF-08: resolved model/learned selection changes; unknown event/ANN recall; producer downgrades required facet and migration drops bytes. Exact model/selection dependency, no absence inference, consumer requiredness wins.
- E14 → LIF-05/LIF-07: withdrawn promoted semantic generation dirties affected claims; operational rollback is not an authority event.
- X01 → LIF-03: restore/incarnation ABA.
- X02–X03 → LIF-02/LIF-05: lagging reverse index loses negative; revoke/restore coalescing hides a public interval.
- X04 → LIF-06: decode/spill ENOSPC before outcome.
- X05/X08 → LIF-04/LIF-06: canceled writer survives lease; control recovery causes retries/log overload.
- X06 → LIF-07: same bytes cannot share cache entry across changed audience/purpose/model.
- X07 → LIF-05: tombstone missed after retention expiry/restore.
- I01–I07 (lifecycle/08 §2) are external incident motivations, not PolicyOS findings and not implementation claims.

## Conflict, ordering, acceptance and limits

W0 source freeze and code rebind precede edits. Serialize writes by shared boundary: cursor frontier (LIF-03); source journal/generation plus Claim/DV head and publication cut (LIF-02); rights generation/copy enrollment/root-vs-GC (LIF-05); runtime intent/outbox/effect inbox (LIF-04); capacity owner/reservation ledger (LIF-06); manifest/derived cache lineage (LIF-07). LIF-01 changes relation/use fields through their canonical owner only. LIF-08 consumes CAP and OPS deliverables; it does not write their owners. Distinct owners may develop in parallel only after W0 confirms no shared commit domain. A task that spans CAS placement, source generation, and public head must declare a transaction or prepare/reconcile/cutoff path; no best-effort sequence presented as atomic.

Acceptance is future work and must be behavioral:
1. Positive path: an input with exact CAP receipt produces persisted artifact/event, enrolls and replays its dependency, commits under current source/right fences, and a fresh selected consumer/audit surface reports the right scoped status. Exercise a reuse under a changed purpose/audience and an authorized sharing case.
2. Adversarial path: include every row in the JSON row probes. Particularly run stale cursor A after B; event before enrollment and replay-floor expiry; fake-but-present reference; source/right change with scheduler stopped; 304 without prior bytes; rights revoke during commit/stream and restore; provider effect then lost receipt; cancel after accept; nested resource wait and fan-in; spill ENOSPC; retained mmap pin; same-byte cache under changed audience/model; changed learned selection; unknown required facet; root publication racing GC.
3. Removal probes: remove the expected-head comparison but keep locks/field names; remove content resolution while keeping refs/verifier markers; remove C→W replay but keep dedupe marker; remove live admission fence but keep saved projection; remove copy enrollment/restore quarantine but keep retention policy; remove effect reconciliation but keep idempotency key; remove transitive reservation/terminal reserve but keep estimate constants; remove selection/model parent edge but keep lineage labels. Each must fail its corresponding semantic acceptance.
4. Crash/chaos points: before/after receipt, frontier, enrollment marker, event effect, provider call, outcome receipt, final public commit, revoke/write commit, restore switch, spill allocation and GC fence; hold old worker beyond lease; provider timeout after effect; control store unavailable. Record external unknown effects as unknown and keep bounded recovery.
5. Every deciding predicate has a P37 class and evidence source. Distinguish source-supplied cut from independently reconciled local journal; exact byte hash from semantic proposition; rights applicability from issuer-supplied legal act; planned copy inventory from independently reconciled actual placements; estimated demand from enforced bound. Refusal, partial, stale, contested, unavailable and review-required projections must remain distinct and visible to the intended consumer/audience.

Pattern closure is not asserted until a real producer, typed persisted artifact/event, lifecycle bridge, fresh consumer, verification, API/audit surface or explicit surface_out_of_scope, and negative semantic test run. Open capability states stay named as above. For scope not selected, say out_of_scope with owner and trigger, not “passed”. Resource measurement is a single bounded wave after the review/source freeze. If owner changes arrive after it, reprice before claiming the bound.

No implementation, product execution, tests, imports, installs, production reads or runtime probes were performed for this plan. Do not treat this artifact or any static CodeC read as acceptance evidence.
