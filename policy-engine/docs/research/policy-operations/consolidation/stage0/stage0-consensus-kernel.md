---
title: Stage-0 Consensus Kernel
status: draft_consolidation
kind: research-synthesis
research_scope:
  - PAO-R0
  - PAO-R1
  - OPS-R15
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
pao_r1_audit_commit: 566840c330e867a15313923c87c20b6863cb053f
ops_r15_audit_commit: 42a79a655974b37e28a89d31b5f72ffea83927f4
consolidation_date: 2026-07-28
consolidation_branch: research/stage0-anchor-consolidation
authoritative_for:
  - cross-audit synthesis at recorded commits
  - proposed Stage-0 research amendments
  - candidate additional-research sequencing
may_not_use_for:
  - production capability claim
  - final code contract
  - canonical owner assignment
  - authority grant
  - legal compliance conclusion
  - implementation authorization
  - production benchmark passage
  - production RPO or RTO commitment
  - automatic amendment of authoritative backlogs or decisions
research_only: true
---

# Stage-0 Consensus Kernel

## Standing

This is a short ratification candidate for `team-architecture`. It consolidates
only propositions supported by the ratified identity/custody decision and the
independent audits of PAO-R0, PAO-R1, and OPS-R15. It is not a production
schema, owner assignment, legal conclusion, benchmark pass, or implementation
authorization.

The historical research baseline and pinned current `main` are identical at
`4813b49f6ce14e8debf3aaea096f0967d38d9768`. No later repository change resolves
or invalidates these statements.

## Candidate ratification statements

### Identity invariants

#### S0-K01 — Identity above a case

**Precise wording.** PolicyOS needs a stable technical reference above a single
Policy Design Case to keep custody of its own justification across multiple
cases and changes. That functional need is OWN. `PolicyMatter` remains the
candidate research name; its schema, namespace, package owner, issuer, and
public representation are unresolved.

- **Support:** identity/custody decision §6; PAO-R0 audit `ID-001`.
- **Known limitation:** no typed matter contract, producer, store, bridge,
  consumer, verifier, or surface exists.
- **Constrains:** later work must remain attachable to a future higher-order
  reference.
- **Does not decide:** identifier syntax, cardinality, split/merge rules, or
  canonical owner.
- **Supersession trigger:** ratified subject-reference and owner decision.

#### S0-K02 — Existing identifiers are not silently repurposed

**Precise wording.** `case_id`, `run_id`, `job_id`,
`decision_lineage_key`, `policy_id`, `portfolio_id`, an artifact digest, a legal
instrument identifier, or a URL must not be silently declared the lifetime
policy identity. Identity continuity does not by itself grant evidence
applicability, legal continuity, or authority.

- **Support:** identity decision §§5–6; PAO-R0 identifier census and
  compatibility audit.
- **Known limitation:** a future migration may explicitly map an existing
  identifier after governed review.
- **Constrains:** research artifacts and new contracts.
- **Does not decide:** migration mechanics.
- **Supersession trigger:** an accepted compatibility and migration contract.

### Boundary invariants

#### S0-K03 — Classify one plane at a time

**Precise wording.** Boundary analysis separates:

```text
external institutional act
→ evidence emission
→ PolicyOS receipt/verification/admission
→ scoped PolicyOS claim reaction
→ public projection
```

OWN, INTEGRATE, OBSERVE, and OUT_OF_SCOPE classify PolicyOS's responsibility
for one declared plane or relationship. A mixed row must be decomposed before
it can constrain work.

- **Support:** identity decision §5; PAO-R1 audit `H-01`; OPS-R15
  administrative-trap audit.
- **Known limitation:** this is a semantic method, not a required storage
  layout.
- **Constrains:** boundary findings, fixtures, public wording.
- **Does not decide:** a global register schema.
- **Supersession trigger:** none without revisiting the ratified identity.

#### S0-K04 — External acts remain external

**Precise wording.** Adjudication, individual administration, legally effective
notification, payment execution, service delivery, procurement operation,
institution-wide records administration, and comparable anti-roles are not
PolicyOS execution functions. PolicyOS may integrate competent evidence of an
external result and must own the effect on claims it signs; receipt or display
must never be represented as PolicyOS performance.

- **Support:** identity decision §§5–6; PAO-R1 and OPS-R15 audits.
- **Known limitation:** the competent external operator and legal effect are
  jurisdiction- and pilot-dependent.
- **Constrains:** H2, adapters, benchmarks, and public projections.
- **Does not decide:** external institutional responsibility.
- **Supersession trigger:** a new ratified PolicyOS identity decision.

### Authority invariants

#### S0-K05 — No authority by observation, transport, or projection

**Precise wording.** Observation, receipt, authentication, integrity
verification, storage, workflow success, authorization admission, benchmark
pass, and UI display do not by themselves create claim authority. Authority
changes only through the existing purpose-scoped authority path and its
canonical verifier/claim owner.

- **Support:** one-lattice decision; PDC `AuthorityBoundary`; runtime-quality
  and projection doctrine; all three audits.
- **Known limitation:** family-specific admission contracts remain distributed.
- **Constrains:** proposed states, envelopes, benchmark labels, and surfaces.
- **Does not decide:** one universal evidence lifecycle.
- **Supersession trigger:** accepted mappings to canonical family owners.

#### S0-K06 — Scope must close before authority use

**Precise wording.** Authority-bearing use must close over the subject,
purpose, tenant, jurisdiction, competent producer, applicable time, and
permitted/prohibited use needed for that action. Unknown or mismatched tenant,
jurisdiction, subject, or competence fails closed for the affected protected
action.

- **Support:** `AuthorityBoundary` meet semantics; identity decision; security
  and jurisdiction findings in PAO-R0 and OPS-R15 audits.
- **Known limitation:** current checkpoint/control-job and jurisdiction
  implementations do not yet provide this closure.
- **Constrains:** research requirements and future negative tests.
- **Does not decide:** a common persisted header or one gate sequence.
- **Supersession trigger:** none; implementation shape remains open.

#### S0-K07 — Projection cannot mint authority

**Precise wording.** Publication owners produce governed projections; Atlas
renders them and must not create, upgrade, or resolve authority. Controlled
surfaces must preserve operator attribution and current, stale, corrected,
superseded, or withdrawn meaning as supplied by canonical owners.

- **Support:** Atlas constitution and identity decision; PDC projection-only
  contracts; audits' current-surface qualifications.
- **Known limitation:** exact public vocabulary and correction fan-out belong
  to PAO-R36, INT-R7/INT-R8, and Atlas work.
- **Constrains:** public and generated surfaces.
- **Does not decide:** Atlas as the owner of the underlying record.
- **Supersession trigger:** accepted public-correction contract.

### Temporal invariants

#### S0-K08 — Correction appends; history is not rewritten

**Precise wording.** A correction, revocation, supersession, withdrawal, or
identity-association change appends a new custody fact and preserves the prior
signed bytes and transaction-time history. A cryptographically valid old
record may be semantically stale and must not be shown as current.

- **Support:** existing lifecycle and reissue patterns; core artifact/signature
  behavior; retention decision; all three audits.
- **Known limitation:** a sidecar is one candidate technique, not proven
  sufficient for public correction.
- **Constrains:** PAO-R0 relations, PAO-R1 reactions, and benchmark predicates.
- **Does not decide:** correction record schema or cache protocol.
- **Supersession trigger:** PAO-R36/INT-R7 accepted design.

#### S0-K09 — Preserve temporal roles without freezing clocks

**Precise wording.** Source occurrence/effect, PolicyOS custody/admission, and
repository transaction/history must remain distinguishable wherever their
collapse could change authority or replay. Historical replay at a declared
cutoff excludes later knowledge and uses the versions then visible; current
rebuild is a different question. OPS-R4 owns canonical names, ordering,
correction relations, and family placement.

- **Support:** current distributed temporal primitives; OPS-R4 backlog remit;
  three audits' clock findings.
- **Known limitation:** no universal clock vocabulary is ratified.
- **Constrains:** reports from freezing nine, ten, or thirteen common fields.
- **Does not decide:** production event envelope.
- **Supersession trigger:** accepted OPS-R4 temporal model.

### Custody invariants

#### S0-K10 — Suspension is durable; wake is only a candidate

**Precise wording.** A suspended custody object must be reconstructable without
a live worker. A wake must bind to the intended subject and scope; a look-alike
or duplicate event must not silently resume it, and wake receipt must not
upgrade authority.

- **Support:** OPS-R15 audited kernel K01–K03; existing checkpoint, outbox, and
  lifecycle fragments.
- **Known limitation:** no end-to-end H2 custody runtime exists.
- **Constrains:** OPS-R1/OPS-R3 and future H2 outcomes.
- **Does not decide:** scheduler, workflow engine, persistence topology, or
  internal state names.
- **Supersession trigger:** governed H2 architecture preserving equivalent
  protection.

#### S0-K11 — Protected actions require equivalent, action-specific protection

**Precise wording.** Before a protected action, current integrity, identity,
authorization, evidence admission, authority, freshness, compatibility, and
applicable human conditions must be re-proven to the extent material to that
action. Equivalent protection is required; one universal twenty-gate resume
chokepoint is not.

- **Support:** identity decision, authorization semantics, OPS-R15 gate audit.
- **Known limitation:** exact phasing belongs to OPS-R1/OPS-R3/INT-R5 and H2.
- **Constrains:** generic `resume()` from bypassing authority reproof.
- **Does not decide:** gate count or atomic transaction boundary.
- **Supersession trigger:** accepted suspension/resume architecture.

#### S0-K12 — Content equality is not authority validity

**Precise wording.** An unchanged payload may lose admissibility because its
source, competence, delegation, license, freshness, jurisdiction, or permitted
use changed. Missing, stale, contradictory, revoked, or unavailable decisive
external evidence must not become a pass. The canonical consumer owns the
claim-specific reaction; a generic evidence envelope does not.

- **Support:** `AuthorityBoundary`; decision-validity patterns; PAO-R1
  absence-behavior audit; OPS-R15 authority-only invalidation predicate.
- **Known limitation:** dependency indexing belongs to OPS-R2 and competence
  semantics to INT-R5/partner facts.
- **Constrains:** reuse, fail-closed behavior, and affected-set research.
- **Does not decide:** physical dependency graph count or universal reaction.
- **Supersession trigger:** accepted OPS-R2 and family-owner contracts.

### Benchmark invariants

#### S0-K13 — Benchmark observable semantics, not internal architecture

**Precise wording.** A future custody capstone must test observable predicates
and permit semantically equivalent implementations. Runtime enum names, a
universal event wrapper, one graph topology, one state machine, one scheduler,
and one service topology are not benchmark ground truth.

- **Support:** OPS-R15 benchmark-validity audit.
- **Known limitation:** observable projections and equivalence functions remain
  to be authored.
- **Constrains:** OPS-R15 revision and Group-B use of its kernel.
- **Does not decide:** benchmark runner implementation.
- **Supersession trigger:** executable benchmark specification with stronger
  implementation-neutral evidence.

#### S0-K14 — Oracle and rebuild must be independent

**Precise wording.** Implementation-visible inputs must exclude expected wakes,
impacts, actions, public postures, and oracle labels. Expected predicates must
be versioned and sealed. Current-state semantic reconstruction must use an
independently owned declarative evaluator that does not share admission,
reducers, dependency traversal, or status projection with the implementation.
A same-code rebuild proves consistency only.

- **Support:** OPS-R15 audit's circularity probe and oracle analysis.
- **Known limitation:** no oracle corpus or reference evaluator exists.
- **Constrains:** any claim that OPS-R15 is executable or passed.
- **Does not decide:** evaluator language or storage.
- **Supersession trigger:** independently reviewed oracle/evaluator package.

#### S0-K15 — The benchmark must resist memorization and preserve dissent

**Precise wording.** The benchmark must use committed public/input/sealed/
evaluator packages, ID and delivery-order mutations, wrong-scope look-alikes,
and at least one adjacent unseen case. Failed runs, oracle versions, raw human
labels, abstentions, disputes, and corrections remain auditable; no post-result
threshold or fixture exclusion may change a scored run.

- **Support:** OPS-R15 anti-overfitting audit and INT-R9 pre-registration
  principles.
- **Known limitation:** sealing, access control, rotation, and reviewer
  governance are not implemented.
- **Constrains:** future benchmark governance.
- **Does not decide:** one universal number of hidden variants or reviewers.
- **Supersession trigger:** exercised benchmark-governance protocol.

#### S0-K16 — Passage is bounded and carries no authority

**Precise wording.** Passage may support only that the named implementation,
repository revision, environment, fixture population, declared scenario
assumptions, and evaluator version satisfied the tested predicates. It is not
legal compliance, institutional competence, production resilience, production
readiness, or authority to perform external acts. No arbitrary efficiency,
RPO, or RTO threshold is part of Stage 0.

- **Support:** repository capability doctrine and OPS-R15 audit.
- **Known limitation:** deployment-specific SLOs remain necessary later.
- **Constrains:** benchmark claims and public wording.
- **Does not decide:** pilot or production acceptance.
- **Supersession trigger:** a separately governed production-like evaluation.

## Deliberately unresolved

The kernel does not ratify:

- a canonical `PolicyMatter` owner, identifier, schema, or relation vocabulary;
- matter-to-case cardinality or evidence inheritance across split/merge;
- a production `OperationalBoundaryDecision` register;
- a universal institutional evidence or event envelope;
- a shared evidence, boundary, owner, custody, or public status lattice;
- clock names or a common field bundle;
- a twenty-gate resume transaction;
- a `WorldRelease` schema or release-state enum;
- H2's state machine, persistence, scheduler, or service topology;
- public correction states, cache fan-out, or long-term key/archive policy;
- institutional operator, competence, proof-of-service, remedy, or payment facts;
- benchmark passage, numerical efficiency targets, or production RPO/RTO.

## Falsifiers of this kernel

The kernel is refuted or must be reopened if any of the following is
demonstrated:

1. a stable above-case custody reference is unnecessary while complete
   historical and cross-case custody remains reproducible;
2. an existing identifier can safely be reinterpreted as lifetime identity
   without ambiguity, migration, or historical rewrite;
3. external execution and evidence handling cannot be separated without making
   PolicyOS disclaim a claim-reaction duty;
4. observation, transport, a benchmark result, or a projection can legitimately
   create authority without a canonical admission/claim owner;
5. historical correction requires rewriting previously signed bytes rather
   than appending a semantic successor;
6. a same-code rebuild can independently detect faults shared by its own
   reducer and dependency logic;
7. an implementation-visible expected trace does not enable scenario-specific
   passing under ID/order/adjacent-case mutations;
8. a production-grade custody capability can be established without
   tenant/jurisdiction closure, action-specific authority reproof, or durable
   reconstructability.

## Smallest coherent next action

`team-architecture` should ratify or amend only S0-K01–S0-K16, then require
source-report amendments before treating the three anchors as completed. It
should commission the bounded subject-reference/owner inquiry and independent
benchmark-oracle inquiry, while allowing remaining Wave-2 research to proceed
under the local assumptions in the sequencing report.
