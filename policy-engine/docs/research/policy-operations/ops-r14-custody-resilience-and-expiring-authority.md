---
id: OPS-R14
artifact_kind: research_report
status: research_only
research_standing: accepted_narrow_scope
capability_standing: NO_GO
gate_standing: NO_GO
repository: DenisKopylov/polisyos
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
source_baseline_equivalent_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
audited_head: 3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7
audit_head: 34c65a04ef178b9a59f70b9fb2012edee17a67cd
inspection_date: 2026-08-06
amendment_date: 2026-08-08
wave: 4
parallel_tasks:
  - PAO-R36
  - PAO-R4
  - S0-GAP-02
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

# OPS-R14 — Custody-grade resilience and expiring authority

## 0. Three-axis standing after independent audit

| Axis | Question | Amended value |
| --- | --- | --- |
| `research_standing` | Is this a valid bounded research architecture at the amended commit? | **`accepted_narrow_scope`** |
| `capability_standing` | Can the pinned repository operate or claim custody-grade resilience and governed expiring authority? | **`NO_GO`** |
| `gate_standing` | May the first-public-signature gate open? | **`NO_GO`** |

The original collapse happened because one standing field forced a refusal about present
**capability** to be written as a refusal about the **research result**.

The architecture is now accepted after the required audit revisions. The two operational refusals do
not move: this amendment supplies no institutional role binding, no independent custody commitment,
no runtime chain, no implemented GY-N12/PAO-R36 endpoint, and no retained successful disconnected
drill. Nothing here authorizes implementation, publication, signing, or opening a gate.

The repository still does not establish:

- a runtime watched-dependency chain with accountable renewal role, process-derived lead time,
  sufficient renewal evidence, affirmative grace authority, protected-use consequence, complete
  affected query, public effect, and prospective delivery reconciliation;
- per-class durable acknowledgement, RPO/RTO measurement, and an implemented evidence-based
  `Restored(c,cutoff)` verifier;
- a complete recovery chain across independently governed content, control, public-log,
  trust/status, source-capture, authority-dependency, and hold domains;
- a general legal-hold lifecycle beyond narrow snapshot classification/GC protection;
- an executed measured clean-environment/disconnected drill proving the INT-R7 minimum profile;
- a delivered GY-N12 currentness runtime owner or PAO-R36 public-change runtime endpoint; or
- institutional assignments and commitments that survive organizational change.

## 1. Commission answer

PolicyOS's signed records survive time, failure, and organizational change only if custody preserves
five separable things:

1. original evidence and immutable control chronology;
2. public-proof closure needed to evaluate historical issuance and durable verifiability;
3. current authority and dependency evidence at an explicit query coordinate;
4. legal/institutional controls over preservation, deletion, access, correction, and succession; and
5. executed recovery evidence proving the first four can be reassembled from independently governed
   custody domains.

The selected hybrid architecture remains unchanged:

- per-class RPO/RTO and acknowledgement boundaries;
- content-addressed reconstruction plus append-only control replay;
- independently retained and independently reconciled public-log, trust/status, source-capture, and
  hold evidence;
- continuous closure checks plus periodic clean full restore-and-verify drills;
- first-class governed watched dependencies, with jobs/alerts as delivery mechanisms only;
- prospective due-event obligations and reconciliation in addition to fail-closed use-time checks;
- selective dual custody/escrow for transferable evidence, never for non-transferable authority;
- OAIS-style preservation responsibility, PREMIS-style preservation-event discipline, and long-term
  cryptographic renewal without selecting an archive, vendor, or wire;
- legal hold as an orthogonal disposal override, not a retention-class transition;
- strict consumption of INT-R7 and GY-N12 and a declared interface to PAO-R36; and
- P37 provenance classification for every load-bearing gate predicate.

A record that cannot be fully replayed is not rewritten, deleted, or retroactively declared never to
have existed. Historical issuance, projection fidelity, public history, durable verifiability at
verification time, and current authority at query time remain separately reportable under PV-K01 and
PV-K02 (`int-r7-r8-public-verification-and-disclosure-ratification.md:91-123`).

## 2. Orientation and complete source census

The full amended ledger is [`ops-r14/orientation-ledger.md`](ops-r14/orientation-ledger.md).
Documentation anchors use `109ba3f4`; the architect established that `policy-engine/src` is byte-
identical to the original pin.

The following figures are the architect-supplied complete tree walk. **Path denominator:**
`policy-engine/src`. **Search:** case-sensitive fixed strings over the pinned ref, binary files
excluded. Each row states its **file-type denominator** as required by P35.

| Token | File-type denominator | Files | Matching lines | Occurrences |
| --- | --- | ---: | ---: | ---: |
| `legal_hold` | all source | **2** | **7** | **8** |
| `renewal` | all source | **4** | **4** | **4** |
| `renewal` | Python only | **1** | **1** | **1** |
| `expires_at` | Python only | **49** | **280** | **363** |
| `ttl_seconds` | Python only | **30** | **116** | **148** |
| `expiry` | Python only | **27** | **102** | **121** |
| `grace_period` | all source | **0** | **0** | **0** |
| `not_after` | all source | **0** | **0** | **0** |
| `revocation_time` | all source | **0** | **0** | **0** |

Consequences:

- the commission's `renewal = 1` was correct only for an unstated Python denominator;
- the audit's `renewal` results and high-cardinality file counts reproduce;
- the audit's `legal_hold = 2 / 4 / 5` is wrong; the complete result is **2 / 7 / 8**;
- the three zeroes are established, not `not_established`; and
- the semantic conclusion is strengthened: no source capability combines the complete governed-
  renewal proposition.

The one Python `renewal` occurrence is worker processing-lease renewal
(`runtime/http/services/control_worker.py:84-85,128-174`). It must not be reused as proof that a DSA,
delegation, licence, certification, consent, budget authority, contract, audit right, certificate, or
jurisdiction review is governed.

## 3. Acceptance-evidence finding, narrowed

### OPS-R14-ACCEPTANCE-001 — documentation/tabletop versus exercised recovery

At `109ba3f4`, `platform-acceptance.md` records:

- line 15: `Runbook presence` — automated — `pass`;
- line 23: `Retention and restore posture` — automated — `pass`, because retention policy and recovery
  runbooks cover the posture; and
- line 30: `Incident / runbook tabletop` — manual — `pass`.

`platform-acceptance-manual.md:85-95` records reading the alert-to-runbook path and validating compose
syntax. These rows do not say that a custody-grade restore ran, that RPO/RTO was measured, or that
`DurablyVerifiableAt(t_v)` passed. The original phrase “runbook accepted as DR closeout evidence” was
stronger than the baseline evidence and is withdrawn.

The real defect is a taxonomy gap: the acceptance surface does not separately report

1. document/procedure present;
2. tabletop completed;
3. restore path exercised; and
4. custody-grade drill predicates passed.

**Closure signal:** a distinct exercised-recovery row must remain non-green until a real restore runs,
or the row must link a retained DE-01–DE-10 event package with frozen scope, actual failure injection,
clean independent restore, measured loss/time, clause-by-clause results, disconnected-path evidence,
and append-only remediation/retest. Runbooks remain substantive inputs, not exercise evidence.

## 4. Binding ownership and seam

### 4.1 Stage 0

S0-K08 requires append-only correction, S0-K09 adopts the Custody Time Model, and S0-K10 makes
suspension durable with wake only a candidate
(`stage0-custody-kernel-ratification.md:94-110`). Recovery, expiry, hold, and all amended fixtures
preserve those findings.

### 4.2 INT-K05 and GY-N12

INT-K05 forbids a second chronology/currentness owner
(`int-wave-claim-semantics-ratification.md:158-170`). GY-N12 remains the sole project semantic/plan
contract owner for epoch/currentness/stale/reissue/release chronology. Its layer is explicitly
**project semantic/plan `contract_only`; runtime capability `absent/unallocated`**. OPS-R14 records and
restores inputs/outputs but creates no competing runtime type, schema, or owner.

### 4.3 INT-R7

INT-R7 remains the delivered research input for public-proof lifecycle, key rotation/revocation,
anti-equivocation, archival verification, evidence obtainability, and disconnected closure. OPS-R14
consumes its five dimensions and supplies custody/recovery/expiry/hold/drill mechanics without
claiming the INT-R7 runtime minimum is implemented.

### 4.4 PAO-R36

OPS-R14 does not define correction meaning, notice, supersession operation, cache/subscriber behavior,
feeds, or translation parity. It requires an immutable relation, canonical applicable public head,
frozen controlled denominator, and member-bound completion evidence, then verifies those survive and
reconcile after recovery.

PAO-R36 F11 is closed at semantic-specification level only by the conjunction:

**`RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`.**

RP-10 alone is not enough. This conjunction preserves event order, latest head, incomplete-fan-out
failure, rollback detection, and clause-by-clause drill visibility without defining PAO-R36's half.

### 4.5 OPS-R12

Institutional replacement, national continuity, workforce/site continuity, mission-essential
functions, and simultaneous loss of every independently governed domain remain OPS-R12. OPS-R14
assumes at least one competent continuing institution or lawful successor.

## 5. Breadth, comparison, and selection

| Model | Selection | Selecting or eliminating property |
| --- | --- | --- |
| Per-class RPO/RTO with independently governed recovery paths | **Selected.** | Unequal public/procedural/harm consequences require different objectives and evidence predicates. |
| One consistent snapshot across all stores | **Rejected as universal basis; optional accelerator.** | It couples systems, omits external custody domains, and can restore an authentic but stale world. |
| Content-addressed reconstruction plus control-event replay | **Selected with conditions.** | It separates bytes from authority chronology; requires high-water marks, reducer custody, orphan/conflict handling, and closure checks. |
| Continuous verification versus point-in-time backup validation | **Select both continuous checks and periodic full restore; reject either alone.** | Continuous checks can share production failures; backup readability does not prove replay, authority, independence, or disconnected use. |
| Watched governed record versus jobs/alerts | **Select record; jobs/alerts are delivery only.** | A job cannot establish source, role, renewal evidence, grace, affected set, public effect, or delivery completeness. |
| Escrow/dual custody | **Select for transferable evidence only; reject universal escrow.** | Copies can preserve bytes/software/exit material, not consent, delegation, competence, budget, or counterparty signature. |
| OAIS-style preservation | **Select responsibility/lifecycle discipline.** | Ingest, fixity, representation information, migration, access, and planning transfer; certification/vendor/legal period do not. |
| Legal hold as override versus retention-class transition | **Select orthogonal override.** | Hold blocks disposition while schedule, deadline, authority expiry, access, and correction history remain visible. |
| Declaration-driven gates | **Reject.** | A gate that trusts its own premise can remain green when the property is false; P37 requires recomputation/reconciliation and red falsification probes. |
| Current scattered TTL/expiry fields and runbooks without event reconciliation/drill | **Rejected.** | Expiry can first surface as a runtime error; documentary posture is not measured recovery. |

## 6. Custody-class objectives and `Restored(c,cutoff)`

The detailed model is
[`ops-r14/custody-class-objectives-and-recovery-closure.md`](ops-r14/custody-class-objectives-and-recovery-closure.md).
Values remain research targets, not legal minima or current capability.

| Custody class | RPO | Minimum safe RTO | Driver |
| --- | ---: | ---: | --- |
| `shadow` | 24 hours | 5 business days | It cannot carry governed/public authority; declared recomputation/loss is tolerable while promotion is blocked. |
| `governed` | 15 minutes | 24 hours | Internal review/promotion chronology cannot disappear silently. |
| `published` | zero acknowledged loss | 4 hours safe read/verification; 24 hours full mutation | Public reliance and anti-equivocation make a missing acknowledged append unacceptable. |
| `active-incident` | zero acknowledged loss | 1 hour | Delay can amplify harm and destroy response chronology. |
| `appeal-relevant` | zero acknowledged loss | 4 hours | Exact evidence/version/service chronology can affect procedural rights. |
| `legal-release` | zero acknowledged loss | 4 hours | Unavailability and wrongful release can both cause irreversible harm. |
| `public-verification-log` | zero acknowledged loss | 2 hours online common view; offline closure remains independently usable | The log is anti-equivocation evidence, not a cache. |

The loss model covers failure of content, control, journal, public log, trust/status, source capture,
worker/scheduler/queue/cache, or one organization/service endpoint, provided every independently
governed copy is not lost. “Independent” is reconciled over administration, substrate, credential/
root-key, failure, and observation provenance; two declared observers sharing one root count as one.

`Restored(c,cutoff)` remains clause-by-clause:

- `RC-01`: event prefix recomputed and independently reconciled with high-water marks;
- `RC-02`: control references recomputed against content digests; orphans confer no authority;
- `RC-03`: deterministic head recomputed from retained reducer/history;
- `RC-04`: authority time independently reconciled and currentness routed to GY-N12;
- `RC-05`: hold coverage and destructive-operation logs reconciled; release is not delete;
- `RC-06`: five INT-R7 dimensions separately recomputed/reconciled;
- `RC-07`: public history, correction relation, head, and member completion reconciled;
- `RC-08`: dependency coverage, affected set, due obligations, and event delivery reconciled; and
- `RC-09`: actual loss/time recomputed with authenticated time evidence.

A database, bucket, signature, declaration, or endpoint returning healthy is not restoration evidence.

## 7. P37 — package-wide predicate provenance register

This is the one package-wide classification table. Each row is one load-bearing predicate, frozen at
admission as exactly one allowed category. The “positive rule” states the consequence at an
OPS-R14-controlled gate. Subordinate implementation checks inherit the classification of the
predicate they decide; none creates a sixth class.

| ID | Load-bearing predicate | Classification | Positive rule / required treatment |
| --- | --- | --- | --- |
| PP-01 | Complete literal source census and denominators | `recomputed` | Positive set-level facts require complete path/file-type enumeration; indexes never count. |
| PP-02 | Original object identity and fixity | `recomputed` | Positive only from retained bytes and digest recomputation. |
| PP-03 | Control-to-content reference closure | `recomputed` | Positive only when every reference resolves and hashes match. |
| PP-04 | Deterministic control head from retained prefix/reducer | `recomputed` | Recovered index or declared head never outranks replay. |
| PP-05 | Event-prefix completeness through cutoff | `independently_reconciled` | Compare recomputed prefix with non-producing high-water observations; gap is non-positive. |
| PP-06 | Custody-domain independence | `independently_reconciled` | Reconcile administration/substrate/key/failure provenance; declarations cannot count copies. |
| PP-07 | Authenticated/monotonic query and event time | `independently_reconciled` | Clock conflict/rollback blocks authority and objective measurement. |
| PP-08 | Record custody-class assignment | `institutionally_supplied` | OPS-R14 cannot create a positive authority claim from the assignment; it applies the most conservative objective until admitted by the canonical process. |
| PP-09 | Authority instrument applicability and legal scope | `institutionally_supplied` | No positive use/renewal/hold/publication finding from an unverified applicability declaration. |
| PP-10 | Competence of renewal/delegation/review/fiscal role | `institutionally_supplied` | Missing or unresolved competence fails closed; account control is insufficient. |
| PP-11 | Bilateral instrument/contract renewal sufficiency | `institutionally_supplied` | Local intent, service, payment, or expectation cannot establish renewal. |
| PP-12 | Technical credential validity for named endpoint/scope | `recomputed` | Cryptographic/issuer verification can be positive; it never establishes underlying legal authority. |
| PP-13 | Consent/withdrawal/current subject authorization | `institutionally_supplied` | OPS-R14 cannot infer consent from silence/use; unresolved authorization blocks affected use. |
| PP-14 | Budget/fiscal authority for new obligation | `institutionally_supplied` | Expected continuation or system balance cannot make it positive. |
| PP-15 | Jurisdiction-pack review competence/currentness basis | `institutionally_supplied` | OPS-R14 records evidence; GY-N12 owns currentness, so unresolved input is non-positive. |
| PP-16 | Affirmative grace authority and exact scope | `institutionally_supplied` | No grace by default; technical overlap/retry cannot make the gate positive. |
| PP-17 | Due set from rights, lead policies, and named window | `recomputed` | Every due obligation is generated from admitted records, not a hand list. |
| PP-18 | Prospective due/overdue/expiry event delivery | `independently_reconciled` | Expected events are reconciled with independent history; any missing/late/conflicting item yields `delivery_gap`. |
| PP-19 | Protected-use currentness at query time | `not_established` | At the pin GY-N12 runtime is absent; protected use must be non-positive. |
| PP-20 | Affected-case set from registered dependency edges | `recomputed` | Re-run the cutoff/version-bound query; a maintained alert list is insufficient. |
| PP-21 | Completeness of affected-case set | `independently_reconciled` | Compare with independent fixture oracle/edge census; mismatch is non-positive. |
| PP-22 | Hold applicability, scope, and issuing competence | `institutionally_supplied` | Ambiguity preserves the disposal barrier and cannot authorize deletion/use. |
| PP-23 | Cross-store hold coverage and absence of destructive action | `independently_reconciled` | Reconcile every store/key/log/destructive path; one uncovered member fails. |
| PP-24 | Final hold-release competence | `institutionally_supplied` | A tag/admin assertion cannot release; unresolved release keeps barrier active. |
| PP-25 | Post-release disposal authorization | `institutionally_supplied` | Release is never delete; no positive disposal without separate admitted authority. |
| PP-26 | Cryptographic signature/content verification | `recomputed` | Positive only for the cryptographic dimension; it does not prove currentness. |
| PP-27 | Signing-time issuer authorization/trust policy | `institutionally_supplied` | If unresolved, historical issuer authority is non-positive without rewriting occurrence. |
| PP-28 | Compromise/revocation interval | `independently_reconciled` | Reconcile multiple retained observations; global invalidation/pass by declaration is forbidden. |
| PP-29 | Historical verifier/component/profile identity | `recomputed` | Content digests and frozen vectors must match; test-stub substitution fails. |
| PP-30 | Historical semantic equivalence across parser/canonicalizer | `recomputed` | Protected-query differential yields interpretation not established; newer success does not win. |
| PP-31 | Latest public-log/checkpoint head | `independently_reconciled` | An authentic old checkpoint cannot establish latest applicable. |
| PP-32 | PAO-R36 correction meaning/current-head assignment | `consumer_asserted` | OPS-R14 cannot make it positive; it consumes the canonical owner's content-bound result and otherwise blocks mutation. |
| PP-33 | PAO-R36 frozen controlled-member denominator | `consumer_asserted` | A denominator declaration alone cannot establish completion or restoration. |
| PP-34 | PAO-R36 fan-out/member completion | `independently_reconciled` | Positive only after member-bound reconciliation over the frozen denominator. |
| PP-35 | External source current official status/successor identity | `independently_reconciled` | Retained historical capture does not prove current official status. |
| PP-36 | Organizational succession scope | `institutionally_supplied` | Query-specific unresolved overlap remains non-positive; original issuer never changes. |
| PP-37 | RPO data-loss measurement | `recomputed` | Compute from acknowledged/restored event coordinates; backup frequency is not measurement. |
| PP-38 | RTO elapsed-time measurement | `recomputed` | Compute from declared start through all passing predicates using reconciled time. |
| PP-39 | Drill corpus/member denominator | `recomputed` | Freeze exact corpus and membership; sampling states complete denominator/method. |
| PP-40 | Failure injection affected the intended domain | `recomputed` | Environment/telemetry evidence must show the failure; discussion or Boolean is insufficient. |
| PP-41 | Disconnected network condition | `independently_reconciled` | Network policy/observation evidence required; an operator assertion cannot pass. |
| PP-42 | Drill uses real intended canonicalizer/verifier/reducer/profile | `recomputed` | Component/profile digests must match; permissive substitute yields `real_path_identity_mismatch`. |
| PP-43 | Independent review role, exception acceptance, and retest authority | `institutionally_supplied` | OPS-R14 records the role/evidence but cannot convert it to operational authority. |
| PP-44 | Acceptance row represents exercised recovery | `independently_reconciled` | Positive only from a linked DE package or distinct executed exercise evidence. |
| PP-45 | Public notice/disclosure duty for an expiry/hold/change | `institutionally_supplied` | OPS-R14 cannot decide or publish; route to canonical process/PAO-R36. |
| PP-46 | Contract option, audit right, exit duty, or survival clause exists | `institutionally_supplied` | Must be proved from admitted instrument/rule; procurement recordkeeping statutes alone do not establish it. |
| PP-47 | Escrow release condition and authority | `institutionally_supplied` | Readable bytes do not prove lawful release or continuing authority. |
| PP-48 | Aggregate custody-grade runtime capability exists | `not_established` | At the pin the chain is absent/unallocated; capability and gate remain `NO_GO`. |

**Gate rule:** if a decisive predicate is `consumer_asserted`, `institutionally_supplied`, or
`not_established`, an OPS-R14 gate fails closed or degrades the claim; it cannot return a positive.
Institutional facts may later be admitted by their canonical owner, but this research never promotes
the declaration itself.

### 7.1 Falsify-the-declaration proof

Two amended fixtures perform the P37 probe:

- F-13 leaves “alert sent” intact but removes the event from independent history. The result is
  `delivery_gap` and blocked use.
- F-15 leaves two `independent=true` declarations intact but makes both observers share one compromised
  substrate/root. The result is `custody_independence_not_established` and restoration false.

Both fixtures go red because the property is recomputed/reconciled. A green result would prove the
fixture tested the declaration.

## 8. Watched dependency and six renewal families

The prose-only contract is
[`ops-r14/watched-dependency-and-legal-hold-semantics.md`](ops-r14/watched-dependency-and-legal-hold-semantics.md).
Every record carries identity, source/provenance, interval/query time, role/succession, process-derived
lead time, sufficient renewal evidence, affirmative grace authority, protected-use consequence,
reproducible affected query, public effect, append-only history, fail-closed use behavior, and the new
WD-05A prospective delivery/reconciliation proposition.

The eleven commissioned rights remain exhaustively mapped to six structural families:

1. **external/bilateral instruments:** DSA, model licence, audit right, contract;
2. **technical credentials:** API credential, encryption certificate;
3. **personal/role competence:** delegation, reviewer certification;
4. **subject authorization:** consent;
5. **fiscal/statutory authority:** budget authority; and
6. **internal governance currentness:** jurisdiction-pack review consuming GY-N12.

The differentiator is who/what can establish the next interval, not a parameter. **Local intent alone
cannot establish renewal.** A competent unilateral option exercise can establish it only where the
admitted instrument authorizes the role and every scope, notice, timing, and condition precedent is
proved. A fresh credential does not renew its underlying authority; escrow does not renew consent,
delegation, competence, budget, or contract; later renewal does not validate an unauthorized gap.

WD-12 still closes safety: absence/delay never extends authority. WD-05A separately closes the
scheduled-event predicate: every right has a durable due obligation over a named window, the due set
is recomputed, observed events are independently reconciled, and any gap yields a durable incident
and non-positive prospective-delivery claim. A late runtime refusal cannot hide that miss.

## 9. Long-term replay and legal hold

Replay preserves original bytes, signing profile, signing-time trust/status, trusted time, public-log
evidence, compromise intervals, renewal evidence, format/parser/canonicalizer behavior, historical
rules/sources/dependencies, organizational mandate/succession, preservation events, and a content-
bound disconnected verifier closure.

Controlling rules survive without weakening:

- original bytes are never replaced by migration/re-signing;
- renewal appends and never backdates issuance;
- a recovered private key is not reactivated from backup;
- compromise is interval-specific;
- missing historical verifier makes durable verifiability non-positive without erasing history;
- parser/canonicalization differential makes historical interpretation not established;
- historical and current replay are distinct;
- scoped succession preserves established non-overlap and blocks disputed overlap;
- vanished source separates historical use from current official status; and
- every replay failure appends.

Legal hold remains an orthogonal scoped cross-store disposal override. It suspends deletion, GC,
destructive compaction/migration, overwrite, crypto-erasure, and destruction of sole decryption/
verification material. It does not extend authority, permit use/publication, block correction, erase
access restrictions, or make a superseded record current. Holds aggregate; final release requires
competent evidence and a later separate disposal decision.

## 10. Seventeen fixtures and drill evidence

The amended suite is in
[`ops-r14/disaster-fixtures-and-drill-evidence.md`](ops-r14/disaster-fixtures-and-drill-evidence.md):

1. CAS restored without control DB;
2. duplicate and conflicting control event;
3. duplicate wake;
4. advanced head with incomplete fan-out;
5. signing-key compromise;
6. vanished official source;
7. 10,000 simultaneous stale cases;
8. final hold release racing deletion;
9. authentic old snapshot rollback;
10. total unresolved successor conflict;
11. unavailable historical verifier;
12. ciphertext without authorized key;
13. scheduler outage across expiry plus declared-alert falsification;
14. lawful partial succession with disputed overlap;
15. false independence over one shared substrate/root;
16. authenticated-time rollback; and
17. parser/canonicalization differential.

F-14–F-17 each specify one input, detector, exact expected verdict, and forbidden outcome. F-13/F-15
prove P37 by keeping declarations intact while making their premises false and returning red.

DE-01–DE-10 require frozen scope, actual injection, clean independently sourced recovery,
disconnected execution, content-bound real-path identities, anti-substitution, measured loss/time,
clause-by-clause predicates, adversarial outcomes, stable evidence, independent review, and append-
only remediation/retest. No runbook, calendar entry, marker, or self-attested green packet passes.

## 11. Public-administration grounding

The external ledger remains grounded in official U.S./UK primary sources plus archival and
cryptographic standards. Transfer limits remain explicit:

- government decisions/material transactions need adequate explanatory records;
- disposition, archives, holds, disclosure, litigation, and procurement records remain governed and
  distinct from a generic TTL;
- a hold preserves but does not validate or authorize;
- FOI access and obstructive-destruction rules do not create universal indefinite retention or open
  publication;
- procurement law supports durable files and decision chronology, while contract options, audit
  rights, exit duties, records rights, and survival clauses are **instrument-specific predicates**
  proved only from the admitted contract/statute/agreement;
- continuity confidence comes from exercises, after-action evidence, remediation, and retest; and
- long-term verification is an institutional service, not one algorithm/provider.

No external period, legal conclusion, archive, vendor, custodian, owner, or instrument-specific right
is transferred into PolicyOS.

## 12. Capability honesty

At the pin:

- snapshot-level hold classification/encryption check/GC protection is `implemented`, narrowly;
- general hold, watched dependency, class RPO/RTO chain, `Restored` verifier, long-term replay chain,
  prospective delivery reconciliation, and qualifying drill are `absent/unallocated`;
- the five runbooks are **factually present and substantive**, while the recovery capability remains
  `absent/unallocated`; no custom maturity label is used;
- GY-N12 is project semantic/plan `contract_only`, with runtime capability `absent/unallocated`;
- INT-R7 is a delivered research dependency, while the complete runtime minimum remains
  `absent/unallocated`;
- the PAO-R36 runtime interface chain is `absent/unallocated` despite a complete research seam; and
- OPS-R12 is deferred scope, not absorbed or maturity-labelled here.

No `producer_missing`, `bridge_missing`, `verification_missing`, or `semantic_test_missing` label is
used without its prerequisite. The worker-lease anti-laundering guard remains explicit.

## 13. Amendment and delivery map

- primary amended decision report: this file;
- count and acceptance ledger: [`ops-r14/orientation-ledger.md`](ops-r14/orientation-ledger.md);
- classes/loss/consistency/restored predicate:
  [`ops-r14/custody-class-objectives-and-recovery-closure.md`](ops-r14/custody-class-objectives-and-recovery-closure.md);
- watched dependency, rights, delivery reconciliation, and hold:
  [`ops-r14/watched-dependency-and-legal-hold-semantics.md`](ops-r14/watched-dependency-and-legal-hold-semantics.md);
- replay/preservation:
  [`ops-r14/long-term-replay-and-preservation.md`](ops-r14/long-term-replay-and-preservation.md);
- seventeen fixtures and drill contract:
  [`ops-r14/disaster-fixtures-and-drill-evidence.md`](ops-r14/disaster-fixtures-and-drill-evidence.md);
- capability labels/interfaces:
  [`ops-r14/repository-integration-handoff.md`](ops-r14/repository-integration-handoff.md);
- primary sources/transfer limits:
  [`ops-r14/external-primary-source-and-transfer-ledger.md`](ops-r14/external-primary-source-and-transfer-ledger.md); and
- per-audit-finding disposition: [`ops-r14/amendment-ledger.md`](ops-r14/amendment-ledger.md).

## 14. Final decision

The architecture is a valid bounded research result and should survive consolidation. PolicyOS is not
ready to claim or operate it. Before the first live public signature, the project still needs
institutional adoption of roles/failure domains, independently governed custody commitments,
separately authorized implementation, delivered GY-N12/PAO-R36 runtime endpoints, and a retained
successful disconnected drill over content-bound real intended paths.

**Research standing:** `accepted_narrow_scope`.  
**Capability standing:** `NO_GO`.  
**First-public-signature gate standing:** `NO_GO`.
