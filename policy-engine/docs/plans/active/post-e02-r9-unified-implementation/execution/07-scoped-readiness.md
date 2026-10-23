# Scoped readiness without weakening composed acceptance

This is a scheduling correction, not a new product status system or a reduction of the original programme. `tasks.json` and [stage-requirements.json](stage-requirements.json) are binding together. The planning manifest is version 2 because dispatch semantics changed. A version-1-only consumer must refuse dispatch until it supports these stage/scoped-rebind rules; it must not ignore unknown fields or silently restore whole-task scheduling. This is a planning compatibility rule, not a product API version. This document supplies the deciding properties for the changed edges. Implementation still starts only after actual E02 G acceptance.

## A complete affected scope, not a global waiting room

P0-ACCEPT is the global entry gate. P0-REBIND retains responsibility for the **complete** original inventory, unresolved obligations and source reconciliation. It may release a task before unrelated reconciliation finishes, only after root records all of the following in the existing journal:

1. Actual accepted E02 commit/tree and acceptance boundary; exact current original predicates and historical dispositions for the task. A prior implementation may satisfy a dependency only through its actual accepted output and preserved scope, never by a similar task title.
2. Complete affected closure: native producer/semantic owner, actual readers/importers, code/test/API/generated companions, migration and shared rule owners. Include downstream readers that will not be edited but must remain compatible. Inventory rows and shared references in the conflict registry are starting points, not proof of completeness.
3. Resolve every discovered cross-boundary dependency to a pinned interface, real output, explicit decision, or a named wait. An unknown writer, consumer, source conflict or shared semantic rule blocks that affected closure. An unrelated unresolved Trust/Docs or institutional question does not block a disjoint cursor or UI task.
4. Exact normalized read/write/generated-family leases; current upstream stage predicates; selected conditional suppliers; phase-specific resources and required execution permission. Unresolved write sets do not receive a speculative lease.
5. Scope owner and root reconcile the record before release. Record its evidence, source pins and invalidation triggers. A newly discovered shared owner or changed interface fences affected writes and acceptance until rebind; unrelated work continues.

There is one global inventory and lease journal, not independent inventories per lead. P0-REBIND is complete only after **all** original obligations and initial ownership routes are reconciled; FINAL-FREEZE requires that completion. A scoped release cannot erase a missing original row, decide a normative question by default, or claim an incomplete capability is accepted.

## Edge stages

Resolve an incoming edge in this order: `supplier_stage_invariants` in stage-requirements.json; the consumer's `dependency_stage_overrides[supplier]`; then its `dependency_stage`. In particular, P0-ACCEPT always means actual E02 acceptance, and P0-REBIND means completed global reconciliation. Ordinary retained mechanism edges mean owner readiness. Final checkpoints consume the specific frozen identity or deciding output they name.

`interface_agreement` is a **planning predicate**, not a new product enum. Producer and consumer owners pin the smallest existing or approved extended native contract: exact source/path/version, producing condition, schema/rule, authority/status/time meanings, permitted payload/receipt boundary, migration, and a distinguishing oracle. Root records the agreement and affected leases. Both sides can then build isolated parts without waiting for the supplier's full implementation. If the meaning itself is unresolved, interface agreement is unavailable; a mock does not resolve it.

An agreement can precede the supplier task's own implementation prerequisites only when those prerequisites do not determine the agreement's meaning. For example, a schema can be agreed before a transport implementation; an unresolved lawful-use rule cannot be replaced by a guessed permission field. Consuming code remains candidate and is not enabled for protected actions merely because it compiles against an agreed interface.

The actual producer, persistence, bridge, fresh consumer and semantic proof remain required at composed acceptance. `acceptance_dependencies` names those real suppliers; conditional requirements add the suppliers activated by the selected profile. A bidirectional witness relationship is not automatically a scheduler cycle: name the producer's emission node and the consumer's observation node. A genuinely circular authority justification is still invalid. Complete stage analysis includes task-local progression; never flatten every witness into a start-before-start edge.

## Edge decisions

| Consumer / supplier | Earliest permitted work | What still blocks composition or activated execution | Source basis |
|---|---|---|---|
| CAP-02 / LIF-03 | Bounded single-response capture with complete durable root and explicit more-pages refusal | Enabling paginated/resumable/range/partition progress or competing frontier writers requires the actual LIF-03 fence and its recovery/stale-writer proof. No second cursor owner. | R9 acquisition/05 A1, AP04; lifecycle/06 W1/T01–T04 |
| CAP-05 / CAP-02, CAP-03 | Legal relation/parser and temporal logic after selected capture/use **interface agreement** | Actual captured representation and admitted relation/use; CAP-04 change event must reach a fresh legal consumer before the full currentness claim. CAP-04 completion is not a prerequisite to start legal work. | R9 acquisition/05 A2/A3 parallelism; AP06; lifecycle/06 W2/W3 |
| CAP-06 / CAP-02, CAP-03, LIF-04, LIF-05 | Controlled-query/provider adapter preparation against agreed receipt, duty, use and copy contracts | Real grants, actual durable attempt/outcome and rights/sink enforcement before any protected effect. A new remote executor requires real durable dispatch/receipt/cancel support; existing-worker work does not wait for an unrelated source-change producer. CAP-04 is required when ongoing source-event handling is claimed. | R9 acquisition/05 A4/A5; AP07–AP11; lifecycle/06 W4/W5 |
| UI-03 / UI-02 | Existing-index allocation and consumer over agreed public-record contract | Actual admissible public-record/index output, fresh permitted consumer and original DS13 predicate. No second index producer and no publication authority from a fixture. | Atlas DS12/DS13; accepted index is rebound at E02 |
| UI-04 / UI-03, LIF-02 | Consultation/history components against agreed index and immutable-history/currentness contracts | Actual append-only response/supersession events, preserved closed bytes and all claimed API/browser/CLI/MACHINE/audit surfaces. | Atlas DS13; W5-K03/K04; P26 |
| UI-08 / GYD-09, GYD-12 | Rendering and refusal/cause-class logic against agreed O1/O3 records | Actual O1/O3 emitted evidence and original DS21 gate. O2 cannot substitute. Deployment/acquisition origin and all four cause classes remain distinct. | Atlas DS21; GY-O1/O3; WP-04/05 |
| UI-17 / CAP-03, CAP-04 | Acquisition status/refusal surface against agreed use/change projection | Real producer output, actual selected positive route and, when numeric VOI is claimed, DEB-13 metric/ranking witness. Acquisition cost does not supply that metric. | Atlas DS15; ds15-numeric-voi-metric-residual-granularity |
| CNT-04/05/06/07 / CNT-02 | Substantive law, measurement, causal and testimony research after selected-source metadata **contract** agreement | Exact selected-source metadata/content, source-qualified native verifier and actual consumer at admission. Completion of the entire heterogeneous library is not required to research one selected source. CNT-01's commissioned scope remains a prerequisite. | R9 substantive W0–W6; acquisition A2/A3; source-library onboarding scope |
| GYD-18/20 / GYD-17; GYD-22 / GYD-17, GYD-18 | Oracle, corpus, replay recipe and health-readout preparation after agreed run/output contracts | Actual V2/V3 outputs consumed in original V3/V5/V7 order during the final wave. Preparing a verifier does not establish a numerical or runtime result. | GY-V2/V3/V5/V7; verification_preparation stage |

These are 21 explicit interface-stage edges, plus the scoped/conditional relocations. Other mechanism edges retain their declared owner-readiness requirement. This is not a blanket permission to begin any consumer against imaginary upstream output. Accepted-E02 rebind may reveal another valid stage split; root must identify its original predicate and exact preserved acceptance obligation before changing it.

## Wave start and completion are different dependencies

After FINAL-REVIEW establishes the final replay identity, FINAL-REPLAY may dispatch independent GY, Atlas, acquisition, lifecycle and operational shards. LIF-09 supplies the lifecycle shard; it is **joined at completion**, not a reason to delay all other shards. GYD-16–22 similarly contribute their actual original wave evidence. Within a shard, real output dependencies and shared browser/store/native-memory resources still determine order.

FINAL-REPLAY cannot finish its evidence accounting until every selected frozen matrix obligation has an actual result or explicit unresolved outcome. It cannot be accepted while required predicates fail or remain unverified. FINAL-USE waits for accepted composed evidence **and** every required original disposition and external authorization. A truthful diagnostic wave may finish with ERROR/FAIL/UNRUN without admitting practical use.

`dependency-levels.json` is only the collapsed task-ID prerequisite projection. An interface node may become available before its task completes; completion joins and scoped resource predicates are outside that projection. Its depth/width are neither a critical-path duration nor available writer capacity. The future root schedules actual stages and leases, not whole rows by their topological level.

## Lease economy

Hold a write lease while the author can mutate its exact files or shared semantic owner. After committing, reading back the immutable candidate and confirming the writer is quiescent, root can release the lease while independent review continues on that candidate. Task acceptance still waits for review. A successor writer must use the explicit compatible base; changed review scope requires delta review. Review delay alone does not reserve a source file.

CPU/RAM/browser/store/provider tickets are acquired for the phase that uses them, not for the entire task's lifetime. An agent waiting for review or an issuer does not retain a compute ticket without an active process. A process with uncertain termination retains its resource claim until reconciled. No lease expiry, cancellation request or commit is proof that a process stopped.

Pattern pass: P01/P02/P05/P07/P13/P27/P29/P35/P37/P38/P41. Falsifiers: unrelated scope dispute must not freeze an already reconciled disjoint lane; unknown shared owner must freeze its affected lane; mock producer cannot pass composed acceptance; another shard may start while LIF-09 runs, but release cannot omit its required result. These are documentary procedure checks; product execution remains UNRUN.

## R15 conditional composition

For DES-12, `conditional_composition_dependencies` is a claim-selected composition requirement, not a preparation edge. Select it when a numeric scientific EVSI claim is made; bind the actual qualified DEB-13 result then. Otherwise record not-applicable with the chosen nonnumeric/bounded design basis. Do not silently fill scientific EVSI from a compute-ranking score. Every `r15_extension` must be included in its task readiness/acceptance and recomputed final obligation coverage. Technical-profile references list possible methods; only the selected guarantee activates its corresponding checks.
