---
id: OPS-R14
artifact_kind: research_report
status: research_only
standing: NO_GO
repository: DenisKopylov/polisyos
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
inspection_date: 2026-08-06
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

# OPS-R14 - Custody-grade resilience and expiring authority

## 0. Result standing

**NO_GO.** PolicyOS cannot presently claim custody-grade resilience for its own signed records or
governed handling of the rights that make those records valid over time. The pinned repository does
not establish:

- a first-class watched dependency with an accountable renewal role, lead time, renewal evidence,
  grace authority, failure consequence, reproducible affected-case query, and public effect;
- per-custody-class durable acknowledgement, RPO/RTO, and an evidence-based restored predicate;
- a complete recovery chain across independently failing content, control, public-log,
  trust/status, source-capture, authority-dependency, and hold domains;
- a general legal-hold lifecycle beyond narrow snapshot retention/GC protection;
- an executed, measured, clean-environment and disconnected drill proving the INT-R7 preservation
  profile before the first live public signature;
- implemented GY-N12 currentness or the parallel PAO-R36 public-change endpoint needed for complete
  recovery reconciliation;
- the institutional role assignments and independent custody commitments needed to sustain these
  duties over organizational change.

This is a completed negative result under INT-K08, which recognizes refusal, void, dispute, no-attempt,
and exhaustion as valid completed outcomes when history is preserved
(`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:213-224`).
It does not authorize implementation or publication.

## 1. Commission answer

PolicyOS's signed records survive time, failure, and organizational change only if custody preserves
five separable things:

1. the original evidence and immutable control chronology;
2. the public-proof closure needed to evaluate historical issuance and durable verifiability;
3. the current authority and dependency evidence applicable at an explicit query time;
4. the legal/institutional controls over preservation, deletion, access, correction, and succession;
5. executed recovery evidence proving the first four can be reassembled from independently failing
   custody domains.

The selected architecture is a hybrid:

- per-class RPO/RTO and acknowledgement boundaries;
- content-addressed reconstruction plus append-only control replay;
- independently retained public-log, trust/status, source-capture, and hold evidence;
- continuous closure checks plus periodic full restore-and-verify drills;
- first-class governed watched-dependency records, with jobs/alerts only as delivery mechanisms;
- selective dual custody or escrow for transferable evidence, never as a substitute for
  non-transferable legal authority;
- OAIS-style preservation duties, PREMIS-style preservation-event discipline, and long-term
  cryptographic evidence renewal without selecting a final archive, vendor, or wire format;
- legal hold as an orthogonal deletion override, not a retention-class transition;
- strict consumption of INT-R7 and GY-N12 and a declared interface to PAO-R36.

A record that cannot be fully replayed is not rewritten, deleted, or retroactively declared never to
have existed. Historical issuance, projection fidelity, public history, durable verifiability at the
verification time, and current authority at the query time remain separately reportable, applying
PV-K01 and PV-K02
(`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:91-123`).

## 2. Orientation audit

Pass I was completed before recommendation work. The full ledger is
[`ops-r14/orientation-ledger.md`](ops-r14/orientation-ledger.md).

### 2.1 Positive agreements

- The three ratification acts contain exactly 264, 379, and 439 lines.
- The five named runbooks exist and contain substantive operational procedures.
- Exact lowercase `legal_hold` occurs in two source files and implements narrow snapshot
  classification/GC protection.
- GY-N12 owns epochs, currentness, stale certificates, append-only reissue, and release-family
  chronology, and is a build-new contract-only task
  (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2053-2120`).
- INT-R7's controlling amendment requires a real ceremonial corpus and disconnected restore before
  the first live public signature; a paper runbook or mocked Boolean does not pass
  (`policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md:1003-1011`;
  `policy-engine/docs/research/policy-operations/int-r7/lifecycle-migration-preservation.md:558-606`).
- The PAO-R36 seam is explicit in the backlog: OPS-R14 owns durability/recovery/expiry mechanics;
  PAO-R36 owns correction meaning, notice, supersession, cache/subscriber fan-out, correction feeds,
  and translation parity
  (`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:512-532`).

### 2.2 Corrected orientation fact

The supplied whole-source-tree count `renewal = 1 file` is false under its stated denominator. Exact
lowercase literal `renewal` occurs in **4 files, 4 matching lines, and 4 occurrences**. Only the Python
occurrence is operational, and it describes worker lease renewal, not renewal of authority
(`policy-engine/src/polisyos/runtime/http/services/control_worker.py:84-85,128-174`). The other three
are fixture text about urban or strategic renewal.

### 2.3 Counts not established

Ordinary cloning failed because outbound GitHub network access was unavailable. The connected
exact-ref interface can read named files but cannot recursively enumerate a raw Git tree and its
search stems some terms. The inherited high-cardinality counts for `expires_at`, `ttl_seconds`, and
`expiry`, and the asserted complete-tree zeroes for `grace_period`, `not_after`, and
`revocation_time`, are therefore marked **not established**, with indexed candidate diagnostics
recorded. This follows P35 rather than promoting code-search output into a complete denominator
(`policy-engine/docs/reference/policy-design-case-failure-patterns.md:78`).

### 2.4 Runbooks are not drills

The runbooks contain useful mechanisms, but inspected acceptance evidence marks recovery posture
green from document presence and closes a tabletop item by reading a runbook
(`policy-engine/docs/archive/reports/platform-acceptance.md:15,23,30`;
`policy-engine/docs/archive/reports/platform-acceptance-manual.md:85-95`). No inspected package
contains a frozen restore corpus, actual failure injection, independent source, measured loss,
measured elapsed recovery, restored predicate, or disconnected execution. The commission's second
falsifier fires.

## 3. Binding ownership and seam

### 3.1 Stage 0 custody kernel

S0-K08 requires correction to append without rewriting history; S0-K09 adopts the Custody Time Model;
S0-K10 makes suspension durable and wake only a candidate
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:94-110`). Recovery,
expiry, and hold semantics in this report preserve those rules.

### 3.2 INT-K05 and GY-N12

INT-K05 forbids a second chronology/currentness owner; future family relation is a reproducible
projection inside the same problem owner
(`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:158-170`).
OPS-R14 therefore records and restores dependency/currentness evidence but does not create an epoch,
currentness, or stale-certificate owner beside GY-N12.

### 3.3 INT-R7

INT-R7 is the delivered input for public-proof lifecycle, key rotation/revocation, transparency,
anti-equivocation, archival verification, and offline closure. OPS-R14 consumes its five-dimensional
verification profile and supplies custody objectives, recovery mechanics, expiring-right semantics,
legal-hold behavior, disaster fixtures, and drill evidence. It does not compete with or weaken
INT-R7.

### 3.4 PAO-R36

OPS-R14 does not define a correction protocol, public notice format, subscriber fan-out, cache
behavior, correction feed, or translation parity. It requires PAO-R36 to expose an immutable
correction/supersession relation, canonical applicable public head, exact denominator of owned
surfaces/recipients, and durable completion evidence. OPS-R14 verifies those artifacts survive and
reconcile after recovery.

### 3.5 OPS-R12

Institutional-scale continuity, replacement of whole organizations, mission-essential-function
continuity, workforce/site continuity, and simultaneous loss of every independent custody domain
remain deferred with OPS-R12. OPS-R14 assumes at least one competent independent custody domain and a
continuing institution or lawful successor.

## 4. Breadth, comparison, and selection

| Model | Selection | Eliminating or selecting property |
| --- | --- | --- |
| Per-class RPO/RTO with independent recovery paths per store | **Selected.** | Different classes create different public, procedural, and harm consequences. The model exposes which evidence failed and measures recovery against a predicate. |
| Single consistent snapshot across all stores | **Rejected as the universal basis; optional accelerator only.** | It couples independent systems, cannot include every external log/custody domain, and can restore a correctly signed but stale world without detecting rollback or missing post-snapshot appends. |
| Content-addressed reconstruction with control replay from an event log | **Selected with conditions.** | It distinguishes immutable bytes from authority-bearing chronology. It requires independently retained high-water marks, reducer/version custody, orphan handling, conflict detection, and control-to-content closure. |
| Continuous verification versus point-in-time backup validation | **Select both continuous closure checks and periodic full restores; reject either alone.** | Continuous checks detect quickly but can share production failures. Backup validation proves readability at one time but not replay, authority, public history, or disconnected operation. |
| Watched-dependency governed records versus scheduled jobs versus alerting | **Select governed records; retain jobs/alerts as delivery only.** | A job or alert cannot establish the right, owner role, renewal evidence, grace authority, affected set, or public effect. Missed delivery cannot extend authority. |
| Escrow or dual custody for disappearing holders | **Select only for transferable evidence and recovery material. Reject universal escrow.** | A copy can preserve bytes, software, an exit package, or authorized recovery material. It cannot preserve consent, certification, delegation, budget authority, statutory competence, or a counterparty signature. |
| OAIS-style archival preservation | **Select the responsibility and lifecycle discipline.** | Ingest, fixity, representation information, preservation planning, migration, access, and designated-community responsibility transfer. Certification, vendor selection, legal retention, and unrestricted access do not. |
| Legal hold as override versus retention-class transition | **Select orthogonal override.** | A hold suspends disposition while leaving the original schedule, passed deadline, authority expiry, access rules, and correction history visible. A class transition obscures why deletion is blocked and complicates multiple holds/release. |
| Current state: scattered TTL/expiry fields and runbooks without drill records | **Rejected.** | Expiry can surface as a runtime error rather than a governed event; no renewal owner or complete affected query is established; documentary preparedness is accepted without measured recovery evidence. |

The complete recovery model and its checkable predicates are in
[`ops-r14/custody-class-objectives-and-recovery-closure.md`](ops-r14/custody-class-objectives-and-recovery-closure.md).

## 5. Custody-class objectives

These values are proposed architecture objectives, not a claim of current capability or legal
minimum.

| Custody class | RPO | Minimum safe RTO | Difference that drives the objective |
| --- | ---: | ---: | --- |
| `shadow` | 24 hours | 5 business days | No governed/public authority may rely on it; recomputation and declared loss are acceptable if promotion is blocked. |
| `governed` | 15 minutes | 24 hours | Internal review and promotion history must not disappear silently, but limited recent work can be repeated. |
| `published` | zero acknowledged loss | 4 hours safe read/verification; 24 hours full mutation | Public reliance and anti-equivocation make an acknowledged missing append unacceptable. |
| `active-incident` | zero acknowledged loss | 1 hour | Delay can amplify harm and destroy the response chronology. |
| `appeal-relevant` | zero acknowledged loss | 4 hours | Exact reasons, evidence, version, and service chronology can affect procedural rights. |
| `legal-release` | zero acknowledged loss | 4 hours | Both unavailability and wrongful release can cause irreversible harm; restrictions and authority must restore with the bytes. |
| `public-verification-log` | zero acknowledged loss | 2 hours online common view; distributed offline closure remains independently usable | The log is anti-equivocation evidence, not a cache; a missing leaf/checkpoint or accepted rollback can hide history. |

The loss model allows failure of content, control, public-log, trust/status, source-capture, worker,
cache, or one organizational/service domain, provided every independently governed copy is not lost.
The objective excludes total institutional loss reserved to OPS-R12.

`Restored(c, cutoff)` is true only after these checks pass:

- every acknowledged event through the cutoff is present once in the logical history;
- every control reference resolves to matching content bytes;
- orphan bytes confer no authority;
- replay produces one deterministic control head and exposes conflicts;
- authority/currentness is evaluated at the explicit query coordinate through GY-N12;
- effective holds blocked every destructive path and releases were separately authorized;
- INT-R7's five dimensions can be reported independently;
- the PAO-R36 public head and completion evidence reconcile;
- every expiring right has complete dependency coverage and an exact affected set;
- measured data loss and elapsed recovery meet the class objective.

A database, bucket, or endpoint returning healthy is not restoration evidence.

## 6. Watched dependency as the center of the task

The owner-neutral, prose-only `WatchedDependencyRecord` contract is in
[`ops-r14/watched-dependency-and-legal-hold-semantics.md`](ops-r14/watched-dependency-and-legal-hold-semantics.md).
It deliberately defines no wire, schema, enum, table, package, serialization, or API.

Every record must establish:

- the protected subject and the exact right being relied on;
- the source/instrument and retained provenance;
- effective interval, expiry, revocation/withdrawal/termination distinctions, and explicit query
  time;
- renewal owner **role**, successor/escalation route, and evidence of competent role binding;
- lead time and intermediate renewal checks based on the real renewal process;
- renewal evidence and the authority competent to produce it;
- grace scope only where affirmatively supported by the authority source;
- failure consequence projected into the existing status/authority machinery;
- a reproducible affected-case query bound to cutoff and dependency/rule version;
- public effect and the PAO-R36 interface requirement;
- append-only history for warnings, attempts, renewal, narrowing, revocation, expiry, and correction;
- fail-closed behavior when the scheduler, queue, or alerting channel is absent.

The eleven right classes form six structural families rather than parameter variants:

1. **external/bilateral instruments:** DSA, model licence, audit right, contract;
2. **technical credentials:** API credential, encryption certificate;
3. **personal/role competence:** delegation, reviewer certification;
4. **subject authorization:** consent;
5. **fiscal/statutory authority:** budget authority;
6. **internal governance currentness:** jurisdiction-pack review, consuming GY-N12.

A renewed credential does not renew its underlying DSA or legal authority. Escrow does not renew
consent, delegation, certification, budget, or contract. A late timer does not create grace. A later
renewal does not validate an unauthorized gap.

## 7. Long-term replay

The full protocol is in
[`ops-r14/long-term-replay-and-preservation.md`](ops-r14/long-term-replay-and-preservation.md).

Replay preserves original bytes, signature, signing profile, credential/trust/status at signing time,
trusted time, public-log evidence, revocation/compromise intervals, algorithm-renewal evidence,
format/representation information, rule/source/dependency versions, organizational mandate and
succession, preservation events, and a disconnected verifier closure.

The controlling rules are:

- original bytes are never replaced by a migrated or re-signed version;
- cryptographic renewal appends evidence over the prior closure before weakness and never backdates a
  new issuance;
- a recovered private signing key is not reactivated merely because a backup contains it;
- compromise is evaluated over evidenced intervals, not a timeless Boolean;
- unsupported historical algorithms require a retained/reproducible isolated verifier and adversarial
  test vectors; failure makes durable verifiability non-positive but does not erase history;
- format migration preserves the original and transformation/fixity evidence;
- historical replay binds historical rules/sources/dependencies; current evaluation is a separate
  query;
- lawful succession preserves predecessor issuer identity and appends a separate custody/currentness
  proposition; conflicting successors do not silently resolve themselves;
- a vanished official source can leave historical evidence intact while current authority is not
  established;
- every replay failure is retained as an append-only event with missing dependencies and
  dimension-by-dimension result.

ISO 14721:2025, PREMIS 3.0, RFC 4998, and RFC 6283 contribute preservation responsibility,
preservation-event vocabulary, and long-term cryptographic renewal patterns. They do not select a
PolicyOS wire format, archive, custodian, retention term, or legal effect.

## 8. Legal-hold semantics

The repository's narrow snapshot fragment is real: a legal-hold retention class/tag flows into GC,
and tests reject missing encryption metadata and preserve a legal-hold snapshot even when ordinary
retain tags are empty
(`policy-engine/src/polisyos/fabric/security/retention.py:32-38,100-112`;
`policy-engine/src/polisyos/fabric/world/store/snapshots.py:661-689`;
`policy-engine/tests/unit/fabric/test_world_time_travel.py:340-400`). That exact path is implemented.

The general legal-hold lifecycle is absent. The selected semantics are:

- hold is an orthogonal, scoped, cross-store disposal override;
- it suspends deletion, GC, destructive compaction, overwrite, destructive migration, crypto-erasure,
  and destruction of the only decryption/verification material;
- it reaches third-party or separate custody where in-scope evidence is held;
- it cannot suspend expiry, revocation, withdrawal, termination, compromise, the duty to stop an
  unauthorized use, append-only correction/supersession, quarantine, access restrictions, or the
  distinction between historical authenticity and current authority;
- retention under hold is not permission to process, rely on, disclose, or publish;
- multiple holds aggregate; releasing one cannot release another;
- after the final competent release, a new disposal decision re-evaluates current policy; release is
  not an immediate delete command;
- correction remains append-only and PAO-R36 owns public correction/notice/fan-out semantics;
- a hold does not make a superseded record current or a signature publicly valid.

## 9. Disaster fixtures and drill evidence

The executable specification is in
[`ops-r14/disaster-fixtures-and-drill-evidence.md`](ops-r14/disaster-fixtures-and-drill-evidence.md).
It contains the seven required fixtures and six additional fixtures:

1. CAS restored but control database absent;
2. duplicate control event, including same identity/different payload conflict;
3. duplicate wake while the underlying dependency remains non-positive;
4. world head advanced but fan-out incomplete;
5. signing-key compromise with interval-boundary records and an old key in backup;
6. a vanished official source;
7. ten thousand cases going stale at once;
8. final legal-hold release racing deletion;
9. authentic but old snapshot rollback;
10. organizational split with conflicting successors;
11. unavailable historical algorithm verifier in a disconnected restore;
12. encrypted bytes restored without authorized decryption material;
13. scheduler outage across authority expiry.

Each fixture specifies the corpus, failure injection, exact expected outcomes, violated invariant,
detection input/verdict, and current-state negative comparator. Critical expected outcomes include:

- orphan CAS content never creates authority;
- byte-identical retries create one effect, while conflicting identity reuse is exposed;
- duplicate wakes never resume a suspended case;
- incomplete fan-out leaves published recovery incomplete without crossing the PAO-R36 seam;
- key compromise never causes historical rewrite or old-key reactivation;
- source disappearance separates historical evidence from current official status;
- mass expiry never extends authority through queue backlog;
- hold release never acts as a delete command;
- an authentic old snapshot is rejected as current when later independent evidence exists;
- storage possession never substitutes for lawful organizational succession;
- verifier failure makes durable verifiability non-positive without erasing the record;
- ciphertext fixity alone does not restore readable evidence;
- timer failure never extends an evidenced right.

A drill must produce a frozen corpus and denominator, real failure injection, clean independent
restore, disconnected network evidence, commands/configuration/versions, measured actual loss and
elapsed recovery, clause-by-clause restored predicates, adversarial outcomes, stable evidence
digests, independent review, remediation, and retest. A paper runbook cannot establish any of those
measurements.

## 10. Public-administration grounding

The external source and transfer ledger is
[`ops-r14/external-primary-source-and-transfer-ledger.md`](ops-r14/external-primary-source-and-transfer-ledger.md).
It uses official primary sources from the United States and United Kingdom, plus archival and
cryptographic standards.

The transferable public-administration principles are:

- government decisions and material transactions need adequate records of what happened, by whom,
  under what authority, and from what evidence;
- disposition is governed by records schedules, archives, special extensions, holds, litigation,
  disclosure, and procurement duties rather than a generic TTL;
- a litigation or records hold suspends covered disposition and can require action across third-party
  custody, but it does not validate an expired right or authorize use;
- freedom-of-information duties require trustworthy records and can prohibit obstructive destruction,
  but they do not create one universal indefinite retention rule or automatic public release;
- procurement records, contract terms, audit rights, exit duties, and survival clauses can outlive
  service, while continued technical service does not prove contract renewal;
- public-sector continuity requires prioritized functions, training, exercising, after-action
  evidence, and improvement closure rather than a document alone;
- archival preservation must survive media, format, software, cryptographic, knowledge-base, and
  organizational change while preserving provenance and access restrictions.

No external retention number, legal conclusion, archive, vendor, or owner is transferred into this
report.

## 11. Repository integration handoff

The detailed handoff is
[`ops-r14/repository-integration-handoff.md`](ops-r14/repository-integration-handoff.md).

Key labels at the pin are:

- **implemented, narrow:** snapshot legal-hold classification/encryption check/GC protection, with a
  producer-consumer-test chain;
- **implemented as documentation artifacts only:** the five in-scope runbooks;
- **contract_only:** GY-N12 currentness/epoch/reissue/release-family chronology;
- **absent/unallocated:** general legal-hold lifecycle, first-class watched dependency, per-class
  RPO/RTO acknowledgement policy, cross-store restored verifier, qualifying drill evidence, and
  complete long-term replay implementation;
- **delivered dependency, runtime capability unclaimed:** INT-R7 research;
- **declared parallel seam, endpoints not yet both implemented:** PAO-R36;
- **deferred and not absorbed:** OPS-R12 institutional-scale continuity.

No row is labelled `producer_missing`, `bridge_missing`, `verification_missing`, or
`semantic_test_missing` without its prerequisite. In particular, the custody recovery chain is not
merely unverified; it is not fully wired, so `verification_missing` would overstate repository
reality.

## 12. Open questions for consolidation

### Engineering

- What independent domains must acknowledge each class before durable success is returned?
- How are event high-water marks authenticated and reducer/verifier environments preserved?
- How is every protected action forced to register all authority-dependency edges?
- How are complete affected sets reproduced across rule/index/schema migration?
- What exact durable completion evidence will PAO-R36 expose without moving correction semantics into
  OPS-R14?
- How are hold barriers enforced across content, control, logs, backups, third parties, keys, and
  migrations?

### Institutional

- Which competent roles may issue/release holds and seek/admit each family of renewal evidence?
- Which independent institution will accept long-term custody responsibility and under what mandate?
- Which access paths must survive for public, competent-records-process, court/audit, and restricted
  requesters?
- Which retention, archive, disclosure, litigation, procurement, consent, fiscal, and delegation
  regimes apply to each deployment?
- Who may accept a missed objective and require remediation/retest?
- What evidence resolves merger, abolition, split, or disputed succession?

### Additional research

- Run a true byte-level full-tree census of every expiry/TTL construct and classify each protected
  right and consumer.
- Test mass-expiry/backpressure and generic dependency completeness under realistic load.
- Compare long-horizon verifier and cryptographic-renewal strategies without choosing a final wire.
- Research actual-jurisdiction succession, archival transfer, privacy/hold, privilege, and restricted
  public-verification interactions.
- Return the PAO-R36 seam for ratification if durable completion evidence cannot be defined without
  crossing into correction meaning.

## 13. Delivery map

- primary decision report: this file;
- Pass I audit: [`ops-r14/orientation-ledger.md`](ops-r14/orientation-ledger.md);
- custody classes, loss model, consistency, and restored predicate:
  [`ops-r14/custody-class-objectives-and-recovery-closure.md`](ops-r14/custody-class-objectives-and-recovery-closure.md);
- watched dependency, eleven right classes, escrow, and legal hold:
  [`ops-r14/watched-dependency-and-legal-hold-semantics.md`](ops-r14/watched-dependency-and-legal-hold-semantics.md);
- key/algorithm/format/organization replay:
  [`ops-r14/long-term-replay-and-preservation.md`](ops-r14/long-term-replay-and-preservation.md);
- thirteen disaster fixtures and drill evidence:
  [`ops-r14/disaster-fixtures-and-drill-evidence.md`](ops-r14/disaster-fixtures-and-drill-evidence.md);
- missing-state labels, interfaces, dependencies, and typed open questions:
  [`ops-r14/repository-integration-handoff.md`](ops-r14/repository-integration-handoff.md);
- external primary sources and transfer limits:
  [`ops-r14/external-primary-source-and-transfer-ledger.md`](ops-r14/external-primary-source-and-transfer-ledger.md).

## 14. Final decision

The recommendation is technically coherent and checkable, but PolicyOS is not ready to claim it.
Before the first live public signature, the project needs institutional adoption of custody roles and
failure domains, an authorized implementation effort, GY-N12 currentness, the PAO-R36 seam endpoint,
and a retained successful disconnected drill over the real intended path. Until then, a positive
`DurablyVerifiableAt(t_v)` cannot rest on runbook presence, and an expiry date cannot be treated as a
governed renewal event merely because a timer exists.

**Standing remains `NO_GO`.**
