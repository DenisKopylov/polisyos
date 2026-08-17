---
id: OPS-R14-INTEGRATION-HANDOFF
artifact_kind: research_handoff
status: research_only
standing: NO_GO
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner, vendor, custodian, archive, or service appointment
  - escrow agent appointment
  - authority grant
  - delegation grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - permission to sign
  - automatic amendment of any plan, backlog, or system-design decision
  - automatic amendment of the status lattice
  - proof that any retention period is legally sufficient
  - absorption of OPS-R12 institutional-scale continuity scope
  - design of PAO-R36 correction, notice, subscriber fan-out, or correction-feed semantics
---

# Repository integration handoff

## 1. Vocabulary discipline

This handoff uses the repository's capability-reality vocabulary exactly as defined at
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:17-34`:

- `implemented`: the precisely scoped chain has a contract/artifact, producer, persisted effect,
  bridge, consumer, verification, surface/limits, and a meaningful negative or semantic test;
- `contract_only`: a contract/status shape exists, but no producing/consuming workflow establishes
  the capability;
- `producer_missing`: a **named consumer** expects an event/artifact and no producer exists;
- `bridge_missing`: both concrete endpoints exist but orchestration between them is absent;
- `verification_missing`: the chain is wired but no end-to-end verification establishes it;
- `semantic_test_missing`: structural tests exist, but the authority/content property is not tested;
- `absent/unallocated`: no admitted capability contract/owner chain exists at the pinned state.

A label is not shorthand for urgency. It is used only when its prerequisites are evidenced.

## 2. Handoff matrix

| Scope | Label at the pinned repository | Prerequisite evidence | Why no stronger or different label |
| --- | --- | --- | --- |
| Snapshot-level legal-hold retention classification and GC protection | **implemented**, narrowly | Contract/artifact: `SnapshotRetentionClass.LEGAL_HOLD` and tagged `WorldSnapshotRecord`; producer/admission path: snapshot registration/classification; persisted effect: snapshot metadata/tags; bridge/consumer: `gc_world_snapshots()` calls `classify_snapshot_retention()` and protects the result; negative/semantic tests: missing encryption metadata is rejected and a legal-hold snapshot survives GC even with ordinary retain tags empty. | This label applies only to snapshot metadata and GC. It does not imply a legal-hold lifecycle, legal sufficiency, or cross-store barrier. Evidence: `policy-engine/src/polisyos/fabric/security/retention.py:32-38,100-112`; `policy-engine/src/polisyos/fabric/world/store/snapshots.py:661-689`; `policy-engine/tests/unit/fabric/test_world_time_travel.py:340-400`. |
| General legal-hold issuance, scope, third-party notice/freeze, multiple-hold aggregation, release authority, cross-store deletion barrier, correction interaction, and public effect | **absent/unallocated** | No admitted end-to-end contract or owner chain was found. The two source files above do not contain these semantics. | Not `contract_only`: the complete lifecycle contract is not present in runtime source. Not `bridge_missing`: both lifecycle endpoints are not established. Not `verification_missing`: no wired chain exists to verify. |
| First-class `WatchedDependencyRecord` for expiring rights | **absent/unallocated** | No exact-ref source candidate for `WatchedDependencyRecord`, `renewal_owner`, `renewal_evidence`, or `affected_case_query`; the only Python `renewal` literal is worker-lease documentation. | Not `producer_missing`: no concrete runtime consumer contract for this record is admitted at the pin. Not `contract_only`: no runtime contract exists. This research supplies prose semantics only. Evidence: `policy-engine/src/polisyos/runtime/http/services/control_worker.py:84-85,128-174`. |
| Worker lease renewal | **implemented**, out of OPS-R14 authority scope | `ControlWorker` leases jobs, heartbeats, and renews the processing lease. | This is not a watched legal/institutional right and must not be reused as proof that authority renewal exists. Evidence: `policy-engine/src/polisyos/runtime/http/services/control_worker.py:84-174`. |
| Per-custody-class RPO/RTO and durable acknowledgement policy | **absent/unallocated** | The inspected runbooks do not define the seven classes, their acknowledgement boundary, measured objectives, or restored predicate. | Not `contract_only`: no admitted repository contract for the class model exists at the pin. This research recommends one but authorizes no implementation. |
| Cross-store `Restored(c, cutoff)` verifier and independent high-water marks | **absent/unallocated** | Useful procedures exist, but no admitted end-to-end contract/owner chain joins CAS, control journal/database, public log, trust/status closure, holds, dependencies, and measured objective. | Not `verification_missing`: that label presupposes a wired chain. Here the chain itself is not established. |
| Replay/restore, retained artifact recovery, corruption recovery, key rotation, and fabric data-plane recovery procedure documents | **implemented as documentation artifacts only** | The five named Markdown files exist and contain concrete steps, commands, checks, and evidence locations. | This does not promote the procedures to a custody-grade recovery capability. Their existence is an input to drills, not evidence of execution. Evidence: `policy-engine/docs/runbooks/replay-or-restore.md:1-128`; `policy-engine/docs/runbooks/retained-artifact-recovery.md:1-180`; `policy-engine/docs/runbooks/artifact-corruption-recovery.md:1-119`; `policy-engine/docs/runbooks/key-rotation.md:1-113`; `policy-engine/docs/runbooks/fabric-quarantine-dlq-and-data-plane-recovery.md:1-178`. |
| Ten-to-thirty-year signed-record replay across key, algorithm, format, and organization change | **absent/unallocated**, with reusable implemented procedures | INT-R7 supplies controlling research semantics; the operational runbooks supply fragments. No admitted implementation chain or qualifying drill is established. | Not `bridge_missing`: archive/verifier/succession endpoints are not all implemented. Not `verification_missing`: no wired complete chain. INT-R7 explicitly keeps capability claims bounded. |
| Custody-grade drill evidence package and disconnected restore gate | **absent/unallocated** | Acceptance evidence closes posture from document presence/tabletop; no inspected event package contains frozen corpus, failure injection, clean restore, measured RPO/RTO, restored predicate, and disconnected proof. | Not `verification_missing`: the full recovery chain is not already wired. Evidence: `policy-engine/docs/archive/reports/platform-acceptance.md:15,23,30`; `policy-engine/docs/archive/reports/platform-acceptance-manual.md:85-95`. |
| GY-N12 epoch, currentness, stale certificates, append-only reissue, and release-family chronology | **contract_only** | The normative plan defines the owner and semantics but is explicitly a build-new task and no live capability is established. | This is the canonical currentness dependency; OPS-R14 must not create a parallel owner. Evidence: `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2053-2120`. |
| INT-R7 public-proof lifecycle research | **delivered dependency; runtime capability deliberately unclaimed** | The controlling amendment specifies five dimensions, pre-live ceremonial/disconnected drill, anti-rollback, independent custody, succession, and evidence obtainability. | Do not force this research-delivery fact into a runtime label. For the runtime minimum profile, the repository's own terminal text does not permit a capability claim. Evidence: `policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md:990-1025`; `policy-engine/docs/research/policy-operations/int-r7/lifecycle-migration-preservation.md:550-650`. |
| OPS-R14 to PAO-R36 public-change interface | **absent/unallocated at this pin; declared dependency seam** | PAO-R36 is parallel. Neither side's concrete implementation endpoint is established in the inspected pin. | Not `bridge_missing`: both concrete endpoints do not yet exist. OPS-R14 requires immutable relation/current-head and fan-out-completion evidence but does not define correction/notice/feed semantics. Evidence: `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:512-532`. |
| Institutional-scale continuity and replacement of whole organizations | **deferred to OPS-R12; intentionally not classified as OPS-R14 work** | The backlog keeps the continuity directorate deferred while OPS-R14 is narrowed to PolicyOS's own records and expiring authority. | Absorbing it would violate the commission boundary. Evidence: `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:130-151,500-505`. |

## 3. Labels intentionally not used

### 3.1 `producer_missing`

No OPS-R14 runtime row is labelled `producer_missing`. The relevant proposed consumers are themselves
research contracts or parallel/undelivered work, not concrete implemented consumers at the pin. The
public-verification kernel names OPS-R14 as a dependency, but the complete runtime consumer chain is
not established; calling the gap `producer_missing` would skip that prerequisite.

A future use of this label must name the exact implemented consumer, the exact event/artifact it
expects, and the source evidence showing that expectation.

### 3.2 `bridge_missing`

No selected row has both implemented endpoints without orchestration. The PAO-R36 seam and the
cross-store recovery chain are earlier-stage: one or more endpoints remain absent. A future
`bridge_missing` claim must cite both endpoint implementations and show only the connecting workflow
is absent.

### 3.3 `verification_missing`

The custody-grade recovery chain is not merely untested; it is not fully wired. Therefore
`verification_missing` would overstate implementation. The narrow snapshot legal-hold GC path does
have semantic tests and is labelled `implemented` only within that scope.

### 3.4 `semantic_test_missing`

No row is assigned this label without first proving structural tests and a wired property whose
content/authority semantics are the only remaining gap. Several proposed fixtures may later expose
such a state, but the pinned evidence does not justify the label today.

## 4. Integration interfaces required for future consolidation

These are dependency declarations, not final APIs.

### 4.1 GY-N12 interface required by OPS-R14

OPS-R14 requires GY-N12 to accept an explicit query coordinate and evidence of expiry, revocation,
renewal, stale review, and succession, and to return the canonical currentness/epoch finding plus the
selected latest-applicable snapshot evidence. OPS-R14 retains and restores those inputs/outputs. It
does not own the currentness projection.

### 4.2 INT-R7 interface consumed by OPS-R14

OPS-R14 consumes the original signed record and complete public-proof closure, five separately
reportable dimensions, anti-rollback evidence, independently retained checkpoints, disconnected
verifier corpus, and lawful-succession semantics. OPS-R14 provides custody, recovery, and drill
evidence; it does not choose a competing public-proof profile.

### 4.3 PAO-R36 interface required by OPS-R14

OPS-R14 requires an immutable correction/supersession relation, the canonical applicable public
head, the exact owned-surface/recipient denominator, and durable fan-out-completion evidence. It
verifies those survive recovery. PAO-R36 owns correction meaning, notice, caches, subscribers,
correction feeds, and translation parity.

### 4.4 OPS-R12 boundary

OPS-R14 assumes at least one competent independent custody domain and a continuing institution or
lawful successor. Institutional replacement, national continuity, workforce/site continuity,
mission-essential-function governance, and recovery after total institutional loss remain OPS-R12.

## 5. Proposed consolidation sequence

This sequence is research advice only and does not amend a backlog.

1. Ratify the semantic boundary: watched rights and recovery mechanics in OPS-R14; currentness in
   GY-N12; public change in PAO-R36; institutional continuity in OPS-R12.
2. Resolve institutional owner-role and authority questions before selecting any wire or vendor.
3. Establish the seven custody classes, acknowledgement boundaries, and restored predicate as one
   reviewed contract.
4. Establish the watched-dependency semantic contract and complete affected-case query requirement.
5. Establish legal-hold issuance/release and cross-store disposal-barrier semantics.
6. Define only then the implementation endpoints and decide whether any gap qualifies as
   `producer_missing` or `bridge_missing`.
7. Build and wire the complete chain under a separate implementation authorization.
8. Add generic behavioral verification and the disaster fixture suite.
9. Execute the pre-live disconnected ceremonial drill required by INT-R7.
10. Re-read and audit the resulting repository state before any capability or gate claim.

## 6. Open questions for consolidation

### Engineering

1. Which independently failing domains must acknowledge each custody class before the API can return
   durable success, and how is the independent high-water mark authenticated?
2. What event-journal/reducer preservation strategy can replay historical control state when the
   runtime, dependencies, and database engine have changed?
3. How is the authority-dependency graph made complete-by-construction so a new protected action
   cannot omit a watched right?
4. How does the affected-case query remain reproducible across index, rule, and schema migration
   without becoming a second chronology owner?
5. What is the exact PAO-R36 completion evidence denominator for owned surfaces, caches, subscribers,
   feeds, and translations, and how does OPS-R14 restore it without designing the protocol?
6. How are hold barriers enforced across CAS, databases, logs, indexes, backups, third-party custody,
   encryption-key destruction, and destructive migrations?
7. Which disconnected verifier dependencies must be source-retained, binary-retained, emulated, or
   reproducibly built over the required horizon?

### Institutional

1. Which competent roles may create, narrow, review, and release a legal hold, and how is vacancy or
   succession evidenced without appointing holders in this research?
2. Which roles own renewal work for each right family, and which renewals require a counterparty,
   subject, certifier, fiscal authority, or delegator rather than an internal role?
3. Which custody copies are independently governed enough to survive primary compromise, and which
   institution is willing and authorized to accept that long-term responsibility?
4. What access route must remain for citizens, journalists, courts, archives, auditors, and restricted
   requesters after the primary publisher or organization disappears?
5. Which retention schedules, archives, disclosure regimes, procurement clauses, and litigation
   processes apply in each deployment, and how will applicability be revalidated over time?
6. Who may declare the start and end of a recovery measurement, accept a failed objective, and require
   remediation/retest?
7. What lawful succession evidence resolves organizational merger, abolition, or split, especially
   where two successors claim the same record family?

### Additional research

1. Complete a true byte-level tree census of all expiry/TTL constructs at the pin and classify each by
   right family, protected action, and current consumer before migration planning.
2. Determine whether a generic dependency-registration rule can make omission fail at build/test time
   rather than relying on a manually maintained list.
3. Model mass-expiry storms under realistic queue, storage, and verification loads, including class
   priority, backpressure, and public fan-out dependencies.
4. Compare long-horizon evidence-renewal profiles and verifier-preservation strategies without
   selecting a final wire format or archive service.
5. Research public-sector organizational succession and archival transfer patterns for the actual
   intended jurisdictions.
6. Research how legal hold, privacy erasure/minimization duties, classified material, privilege, and
   public verification interact in the intended deployments without treating any one regime as
   universal.
7. Resolve the seam question of whether PAO-R36's completion evidence can be made durable without
   moving correction meaning into OPS-R14; if not, return the seam for ratification rather than
   crossing it informally.

## 7. Standing

**NO_GO.** The pinned repository does not establish a first-class expiring-right record and owner
chain, per-class durable acknowledgement and restored predicates, cross-store recovery closure,
general legal-hold lifecycle, or qualifying disconnected drill evidence. GY-N12 is `contract_only`,
PAO-R36 is parallel, and institutional roles and independent custody commitments are unresolved.
These are prerequisites to a custody-grade claim, not revisions that can be deferred until after the
first public signature.
