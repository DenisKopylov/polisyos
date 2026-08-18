---
id: OPS-R14-INTEGRATION-HANDOFF
artifact_kind: research_handoff
status: research_only
research_standing: accepted_narrow_scope
capability_standing: NO_GO
gate_standing: NO_GO
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
audited_head: 3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7
audit_head: 34c65a04ef178b9a59f70b9fb2012edee17a67cd
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

This handoff uses the capability-reality vocabulary at
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:14-35` literally:

- `implemented`: the precisely scoped chain has a typed contract/artifact, producer, persisted effect,
  bridge, consumer, verification, visible/audit surface or explicit surface disposition, and a
  meaningful negative semantic test;
- `contract_only`: a type/schema/status or admitted semantic contract exists, but no producing/
  consuming workflow establishes the capability;
- `producer_missing`: a named consumer expects an event/artifact and no producer exists;
- `artifact_missing`: producer logic exists but its event/artifact is not persisted/queryable/replayable;
- `bridge_missing`: both concrete endpoints exist but orchestration does not connect them;
- `consumer_missing`: an event/artifact is produced and persisted but no reader acts on it;
- `verification_missing`: an already wired chain lacks end-to-end verification;
- `implemented_but_not_orchestrated`: a component works in isolation but is not in the runtime flow;
- `semantic_test_missing`: structural tests exist but the authority/content property is untested;
- `surface_missing` / `surface_out_of_scope`: surface state after internal capability is established;
- `absent/unallocated`: no admitted prerequisite chain exists.

A factual statement such as “five runbooks are present and substantive” is not a maturity label. A
label is used only where its prerequisites are evidenced. Research delivery and runtime capability are
reported separately.

## 2. Handoff matrix

| Scope | Canonical capability label at the pin | Factual evidence and layer | Why no stronger/different label |
| --- | --- | --- | --- |
| Snapshot-level legal-hold classification and GC protection | **`implemented`**, narrowly | `SnapshotRetentionClass.LEGAL_HOLD`; persisted snapshot metadata/tags; GC consumer; tests reject missing encryption metadata and preserve held snapshots. | Applies only to snapshot metadata and GC. It does not imply issuance, scope aggregation, release, third-party freeze, cross-store barrier, or legal sufficiency. Evidence: `fabric/security/retention.py:32-38,100-112`; `fabric/world/store/snapshots.py:661-689`; `tests/unit/fabric/test_world_time_travel.py:340-400`. |
| General legal-hold lifecycle | **`absent/unallocated`** | No admitted end-to-end owner/contract/producer/consumer chain establishes issuance, aggregation, release, third-party propagation, correction interaction, or public effect. | Not `contract_only`, `bridge_missing`, or `verification_missing`: the prerequisite runtime endpoints are not established. |
| First-class watched dependency, including WD-05A delivery reconciliation | **`absent/unallocated`** | This amended package supplies a prose semantic contract. The pinned runtime does not establish the right record, producer, independent event reconciliation, affected-case consumer, or authority gate chain. | Not `producer_missing`: no implemented consumer contract expecting this artifact is established. The only Python `renewal` literal remains worker-lease documentation. |
| Worker processing-lease renewal | **`implemented`**, outside OPS-R14 authority scope | `ControlWorker` leases jobs, heartbeats, and renews processing leases. | A worker lease is not a delegation, agreement, licence, certification, consent, fiscal authority, contract, or jurisdiction review. It must never be reused as authority-renewal evidence. Evidence: `control_worker.py:84-174`. |
| Per-custody-class RPO/RTO and durable acknowledgement | **`absent/unallocated`** | Seven classes and objectives are accepted research architecture only. | No admitted runtime contract/producer/measurement/consumer chain at the pin; not `contract_only` merely because this prose exists. |
| Cross-store `Restored(c,cutoff)` verifier, common-mode independence, and authenticated high-water marks | **`absent/unallocated`** | Useful storage/replay procedures exist; the complete control/content/log/trust/hold/dependency/measurement chain does not. | Not `verification_missing`: the chain itself is not wired. |
| Custody-grade recovery capability for which five runbooks are inputs | **`absent/unallocated`** | **Factual non-label statement:** the five named Markdown procedures are present and substantive, with commands, checks, and evidence destinations. | Document presence is an input, not a capability chain or drill. The prior phrase `implemented as documentation artifacts only` is removed because it is not a repository maturity label. |
| Ten-to-thirty-year signed-record replay across key, algorithm, format, parser, time, and organization change | **`absent/unallocated`** | INT-R7 supplies controlling research semantics and runbooks supply fragments. | Archive/verifier/succession endpoints are not all runtime capabilities; not `bridge_missing` or `verification_missing`. |
| Custody-grade drill package and disconnected restore gate | **`absent/unallocated`** | Acceptance evidence records runbook presence, restore posture, and a tabletop; no DE-01–DE-10 package is established. | The full chain is not wired, so `verification_missing` would overstate reality. `OPS-R14-ACCEPTANCE-001` is the documentation/tabletop-versus-exercised-recovery taxonomy finding. |
| GY-N12 epoch/currentness/stale/reissue/release chronology | **Project semantic/plan contract layer: `contract_only`; runtime capability: `absent/unallocated`.** | The normative plan defines ownership and semantics as a build-new task. It is not a delivered runtime type, schema, producer, or consumer chain. | This qualification prevents the contract-layer label from being read as runtime implementation. GY-N12 remains the sole currentness owner. Evidence: `GY-engine-subordination.md:2053-2120`. |
| INT-R7 public-proof lifecycle | **Runtime capability: `absent/unallocated` for the complete minimum profile.** | **Factual non-label statement:** the research dependency is delivered and defines five dimensions, pre-live ceremonial/disconnected drill, anti-rollback, independent custody, succession, and obtainability. | Research delivery does not satisfy runtime prerequisites or open a gate. Evidence: `int-r7-public-verification-lifecycle.md:990-1025`; `int-r7/lifecycle-migration-preservation.md:550-650`. |
| OPS-R14 to PAO-R36 public-change interface | **Runtime interface chain: `absent/unallocated`.** | The seam is declared and semantically complete from OPS-R14's side. Concrete runtime endpoints are not both established at the pin. | Not `bridge_missing`: both implemented endpoints are prerequisites. F11 closure is the conjunction `RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`. |
| Institutional-scale continuity/replacement of whole organizations | **Not an OPS-R14 capability row; deferred scope boundary.** | Backlog keeps OPS-R12 deferred while OPS-R14 covers PolicyOS's own records and expiring authority. | Absorbing or maturity-labeling OPS-R12 here would violate the commissioned boundary. Evidence: backlog `:130-151,500-505`. |

## 3. Labels intentionally not used

### 3.1 `producer_missing`

No OPS-R14 row is labelled `producer_missing`. Proposed consumers are research requirements or
parallel/undelivered work, not a proven implemented consumer expecting one exact runtime artifact. A
future use must cite the concrete consumer and expected persisted event/artifact.

### 3.2 `bridge_missing`

No selected row has two implemented endpoints with only orchestration missing. PAO-R36 and the
cross-store recovery chain are earlier-stage. A future use must cite both endpoint implementations.

### 3.3 `verification_missing`

The aggregate custody chain is not merely untested; it is not fully wired. The narrow snapshot hold/
GC path has semantic tests and is `implemented` only within that exact scope.

### 3.4 `semantic_test_missing`

No row receives this label without a wired structural chain whose remaining defect is specifically
a missing authority/content semantic test. The amended fixtures specify future tests but do not
establish those prerequisites at the pin.

## 4. Integration interfaces required for consolidation

These are dependency declarations, not final APIs.

### 4.1 GY-N12

OPS-R14 supplies an explicit query coordinate and retained evidence of expiry, revocation, renewal,
stale review, time rollback, and succession. GY-N12 returns the canonical currentness/epoch finding
and latest-applicable evidence when its runtime owner is delivered. OPS-R14 retains/restores the
inputs and outputs; it never owns the currentness projection.

### 4.2 INT-R7

OPS-R14 consumes original bytes and complete public-proof closure, five separate dimensions,
anti-rollback evidence, independently reconciled checkpoints, disconnected verifier corpus, and
lawful/scoped succession semantics. It supplies custody, recovery, and drill evidence without
selecting a competing public-proof profile.

### 4.3 PAO-R36

OPS-R14 requires an immutable predecessor/successor relation, canonical applicable public head,
frozen owned-surface/recipient denominator, and member-bound completion evidence. It independently
reconciles those after recovery. PAO-R36 owns correction meaning, notice, caches, subscribers, feeds,
and translation parity.

The “recovery must never un-correct” seam is not carried by RP-10 alone. It requires
`RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`.

### 4.4 OPS-R12

OPS-R14 assumes at least one competent independently governed custody domain and a continuing
institution or lawful successor. Replacement of the whole institution, national continuity,
workforce/site continuity, and simultaneous loss of every independent domain remain OPS-R12.

## 5. Consolidation sequence

This sequence is research advice only and does not amend a backlog:

1. Ratify the boundary among OPS-R14, GY-N12, PAO-R36, and OPS-R12.
2. Resolve institutional role/authority questions before any wire or vendor selection.
3. Establish the seven classes, acknowledgement boundaries, and restored predicate.
4. Establish the watched-dependency contract, WD-05A due-event reconciliation, and affected query.
5. Establish legal-hold issuance/release and cross-store disposal-barrier semantics.
6. Classify every decisive predicate under P37 and make consumer-asserted, institutionally supplied,
   or not-established predicates non-positive.
7. Define implementation endpoints and only then apply producer/bridge labels.
8. Build and wire the complete chain under separate authorization.
9. Add generic behavioral verification and the seventeen-fixture suite.
10. Execute the pre-live disconnected ceremonial drill required by INT-R7.
11. Re-read the resulting branch/runtime state before any capability or gate claim.

## 6. Open questions

### Engineering

1. Which independently governed domains must acknowledge each class, and how are shared substrate,
   control-account, key-root, and high-water-mark dependencies detected?
2. What event-journal/reducer preservation strategy replays historical state after engine change?
3. How is dependency registration complete-by-construction for every protected action?
4. How does the affected query survive index/rule/schema migration without a second chronology owner?
5. How is the PAO-R36 frozen denominator independently reconciled without defining its protocol?
6. How are hold barriers enforced across content, DBs, logs, indexes, backups, third parties, keys,
   and destructive migrations?
7. Which verifier dependencies are source-retained, binary-retained, emulated, or reproducibly built,
   and how is test-stub substitution rejected?
8. Which authenticated/monotonic time evidence resolves rollback at expiry and replay coordinates?

### Institutional

1. Which competent roles create, narrow, review, and release holds, and how is succession evidenced?
2. Which roles seek each renewal, and which require a counterparty, subject, certifier, fiscal
   authority, or delegator rather than local action?
3. Which copies are independently governed, and which institution is authorized to hold them?
4. What controlled access route survives for public, court, archive, audit, and restricted requesters?
5. Which retention, archive, disclosure, procurement, and litigation regimes apply per deployment?
6. Who declares recovery measurement boundaries and accepts a miss/retest?
7. What evidence resolves merger, abolition, or scoped split with disputed overlap?

### Additional research

1. Classify the architect-supplied complete expiry/TTL census by right family, protected action, and
   current consumer before migration planning.
2. Determine whether dependency registration can make omission fail at build/test time.
3. Model mass-expiry storms with class priority, backpressure, and public fan-out dependencies.
4. Compare long-horizon renewal/verifier-preservation strategies without selecting a wire or archive.
5. Research actual-jurisdiction succession and archival-transfer patterns.
6. Research hold interaction with privacy erasure/minimization, classified material, privilege, and
   public verification without treating one regime as universal.

## 7. Standing

The handoff architecture and label discipline are accepted in narrow research scope. The pinned
repository lacks the watched-right chain, class acknowledgement/restoration chain, general hold
lifecycle, and qualifying drill.

**Research standing:** `accepted_narrow_scope`.  
**Capability standing:** `NO_GO`.  
**First-public-signature gate standing:** `NO_GO`.
