---
title: Custody Time Model (CTM) — Target Temporal Semantics for Policy Custody
status: draft design decision — target temporal spec for custody-bearing work
owner: team-architecture
created: 2026-08-02
last_reviewed: 2026-08-02
decision_status: accepted as the target spec every custody-bearing temporal contract is subordinated to; ratified in pair with S0-K09
source_research: docs/research/policy-operations/ops-r4-temporal-semantics-for-policy-custody.md
informs:
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
  - docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - docs/research/policy-operations-and-real-world-runtime-backlog.md
related:
  - docs/system-design-decisions/stage0-custody-kernel-ratification.md
  - docs/system-design-decisions/policy-design-causal-grounding-firewall.md
  - docs/system-design-decisions/policy-design-search-target-spec.md
  - docs/system-design-decisions/policyos-identity-and-custody-boundary.md
authoritative_for: [temporal_role_vocabulary, temporal_query_semantics, late_event_reaction_categories]
may_not_use_for: [production_wire_contract, universal_event_envelope, legal_effective_date_adjudication, administrative_deadline_operation, authority_grant, capability_claim, executable_benchmark_claim]
---

# Custody Time Model (CTM) — Target Temporal Semantics

This decision record **registers** the delivered OPS-R4 research
(`ops-r4-temporal-semantics-for-policy-custody.md`, result `accepted_narrow_scope`)
as the **target spec** every custody-bearing temporal contract is built toward, and
records what we adopt, what is refuted, and what is deferred. The research document
is the evidence; this is the **PolicyOS reading** of it.

> **One law first.** CTM is a **semantic profile, not a platform.** Under the
> no-parallel-worlds law (P27/P28) it is subordinated to existing family owners:
> Fabric keeps data valid/transaction time, Lex keeps legal publication and effect,
> Decision Validity and the Claim Ledger keep dependency and lifecycle, audit keeps
> integrity, and **Atlas projects but never owns temporal truth**. No shared
> persisted temporal envelope is created. The mapping in §4 is binding.

CTM is the **fourth layer of the causal OS**, completing the set:
**data (memory) = GY-S / L1–L6** · **grounding (the type system) = CGF** ·
**search (the scheduler) = RACE-HOG-PODS** · **time (the custody clock) = CTM**.

## 1. What it is, in our terms

Established temporal systems each answer one bounded question well: bitemporal
stores answer which version was valid and transaction-visible at a cutoff; stream
processors answer how far a computation believes its input has progressed; CDC logs
answer how source changes were ordered and delivered; event-sourced workflows answer
how an execution can be deterministically reconstructed; legal-informatics models
answer how force, efficacy, and applicability are represented.

**None of them proves that a PolicyOS claim was justified at a historical cutoff.**
They cannot say which evidence PolicyOS had *received*, which it had *admitted for
the relevant purpose*, whether the producer remained *competent*, whether a late
fact was *materially dependency-bearing*, whether a public claim had already been
*issued*, or which claim owner was *authorized to react*. Those are custody and
authority questions — ours by the signature rule.

That gap is the whole temporal authority-delta, and it is small. The result is
`accepted_narrow_scope`: PolicyOS needs a thin shared profile, **not** a universal
persisted event envelope and **not** a fixed bundle of clocks.

## 2. The nine primitive temporal roles

A sparse semantic profile. A role says what a temporal value *means*, who may assert
it, and how it participates in custody — it is **not** a requirement that every
object carry a field for every role. A role may be an instant, a civil date, an
interval, a version relation, a transaction sequence, a provenance assertion, a
lifecycle event, or a query cutoff.

| Role | Meaning | May affect authority |
| --- | --- | --- |
| **R1 Source occurrence / act** | When an external event or act happened in its source domain | Yes when material; never by itself |
| **R2 Source effect / validity** | When the source proposition, norm, authority, or entitlement is applicable | Often directly |
| **R3 Observation / measurement** | The period a measurement, survey, or estimate speaks about | Through relevance and freshness |
| **R4 Source publication / version** | When and in which source version an assertion was issued or revised | Sometimes; publication is not effect by default |
| **R5 PolicyOS receipt** | When we first obtained an immutable representation under a named custody channel | Enables `known_by`; grants **no** admission |
| **R6 Transaction visibility** | When a record became visible in a named store under its ordering model | Indirectly; bounds what may be claimed historically |
| **R7 Verification** | When an identified verifier checked a declared predicate, with outcome and method | Yes as a required predicate; **never** equal to admission |
| **R8 Purpose-scoped admission** | The authorized action admitting an object/version for a named purpose and scope | Directly |
| **R9 PolicyOS claim / publication / lifecycle action** | When we evaluated, signed, published, staled, suspended, corrected, superseded, reissued, or withdrew our own record | Directly |

The roles are irreducible because collapsing any adjacent pair produces a concrete
authority error:

- effect into occurrence misstates future-effective and retroactive rules;
- observation into publication misstates the period measured;
- publication into receipt pretends we had timely custody;
- receipt into transaction visibility ignores persistence and store order;
- **visibility into verification or admission launders stored bytes into authority**;
- admission into decision erases the canonical consumer's responsibility;
- processing time into any source or custody role fabricates a semantic fact.

The fifth is S0-K05 stated in temporal terms; the sixth is S0-K12; the last is the
rule that keeps wall-clock telemetry out of semantic identity.

## 3. Relations, not clocks; query coordinates, not an overloaded `as_of`

Derived concepts are **derived from primitive records, relations, and query
coordinates** — not persisted as universal timestamps: `known_by`, `verified_by`,
`admitted_by`, `current_at`, `late`, `retroactive`, `stale`, `expired`,
`review_due`, `replay_cutoff`, `processing_time`.

Correction, revocation, supersession, derivation, authority withdrawal, version
validity, and the unresolved correction-before-original case are expressed as
**typed immutable mutation relations**, never as a mutated timestamp.

Queries carry **explicit coordinates** instead of one overloaded `as_of`: the
valid/effect coordinate, the transaction/knowledge cutoff, the purpose-scoped
admission cutoff, the publication-history coordinate, and — where required — the
exact replay context. Historical replay at a declared cutoff excludes later
knowledge and uses the versions then visible; **current rebuild is a different
question and must be asked differently.**

Temporal values that bear authority preserve enough to avoid false precision:
lexical form where material, calendar and jurisdiction, offset honesty (known UTC ≠
known offset ≠ named zone ≠ unknown), precision monotonicity (a day is never
promoted to a second), explicit interval closure, uncertain bounds, retained
conflicting assertions, and clock-quality provenance. **Authority monotonicity:
reducing temporal precision or timezone certainty can never increase authority.**

## 4. The reuse map (binding subordination)

| Semantic responsibility | Existing owner | Posture |
| --- | --- | --- |
| Source data validity, observation period, release vintage | Fabric / Data Forge domain owner | wire existing; extend precision |
| Transaction visibility, store cutoffs | Fabric, Data Forge, event and claim stores | wire existing; consolidate query semantics |
| Source progress and receipt | Fabric connectors, cursors, source truth | wire existing; make progress ≠ receipt ≠ completeness explicit |
| Legal publication, effect, version | Lex and legal Data Forge | wire existing (OPS-R10/R11 adapters) |
| Verification and integrity | core audit/security and family verifiers | wire existing; separate *verified* from *admitted* and *current* |
| Purpose-scoped admission | evidence / claim / decision owners | **extend canonical owners; do not centralize** |
| Claim dependency and currentness | Decision Validity, Claim Ledger | wire existing; shared predicates only |
| Correction / revocation / supersession | Fabric, Lex, Claim Ledger, public owner | consolidate the relation vocabulary |
| Late and out-of-order assessment | Fabric processing + canonical consumers | extend as **advisory** evidence |
| Exact replay | Scientist checkpoints, snapshots, NormPack, artifact store | consolidate refs; build only the receipt projection |
| Public publication, currentness, archive | Claim Ledger / Decision Validity, audit; **Atlas projects** | extend the later public owner (PAO-R36 / INT-R7 / INT-R8) |
| Custody deadlines and review-due | decision jobs, obligation graph, retention | qualify and reuse owner-native duties — never external legal deadlines |

An adapter maps evidence. **An adapter never reinterprets a family-native date and
never grants authority.**

## 5. Late events: assess, recommend, never mint

Lateness is not an intrinsic global enum — an object is late **relative to** a
declared expectation (a source progress contract, transaction cutoff, evaluation
window, scheduled wake, publication, legal-effect start, or dependency epoch).

A `LateEventAssessment` is **advisory evidence** produced at the adapter/consumer
boundary. It recommends a minimum reaction from a seven-step ladder — L0 retain only
· L1 annotate · L2 update current context · L3 recompute the materially dependent
current claim · L4 suspend and require revalidation · L5 open a new epoch and
reissue/supersede/withdraw · L6 competent-human adjudication — escalating with
materiality, public standing, irreversibility, and dispute.

**The canonical claim or publication consumer records the actual reaction.** Fabric,
temporal adapters, Atlas, and source payloads supply evidence only. In particular, a
source payload's own `required_action` is never an automated default, and a watermark
never becomes proof of semantic completeness. This is S0-K05 and S0-K12 at the
temporal boundary, and it is why the ladder recommends rather than decides.

## 6. What is refuted

**A universal persisted `OperationalEventEnvelope` does not survive.** Weighed
against three alternatives it scores high semantic loss (forcing occurrence, effect,
publication, observation, receipt, admission, and processing into one shape turns
intervals, versions, and relations into fake timestamps), very high P13 owner
gravity (a new central temporal platform), and very high P27 owner-preemption of
canonical family owners without evidence. Its legitimate intent — event identity,
source/custody separation, duplicate and correction lineage, late-event evidence —
is satisfied more safely by family-native records plus shared predicates.

A **thin transport header** remains a research candidate *only* at boundaries where
the repository shows repeated transport-level duplication, and at most carries
owner-qualified record identity, producer namespace, immutable target relations, and
a transaction/audit reference. It may never require every role, carry a universal
`required_action`, decide admission, or become the source of legal effect.

## 7. The concrete repository consequence

The research classifies the existing `TimeSourceEnvelopeAudit` as **a local audit
projection that has become an accidental universal envelope** — it demands a fixed
fifteen-role bundle and normalizes values across unrelated domains, while runtime
quality cannot own legal effect, source observation, admission, retention, replay, or
claim reaction. Its prescribed narrowing (planning-level, no code authorized here) is
also the prescribed fix for the registered defect **GY-DEF4**:

1. treat it as **projection only**;
2. narrow and preferably rename it — e.g. `TimeSourceConsistencyAuditProjection`;
3. **remove `admitted` from `mismatch_disposition`**; use diagnostic outcomes —
   `consistent`, `inconsistent`, `insufficient_evidence`, `blocked_for_owner_review`;
4. accept sparse family-native roles instead of demanding every field;
5. delegate legal effect and competence to Lex, source progress to Fabric contracts;
6. never derive a missing source time from processing time or a generic default;
7. never equate watermark freshness with semantic completeness;
8. map `replay_time` to an explicit replay query or receipt, not one timestamp;
9. carry tests that falsify valid/transaction collapse, false precision, and
   authority laundering.

Point 3 removes the literal that `runtime/quality/authority.py` currently reads as
the implicit pass. Until this narrowing is accepted by the affected owners, the
current audit is **local evidence about one proving-ground composition** and must not
be cited as the PolicyOS temporal contract.

## 8. Honest caveats (do not paper over)

1. **This is a semantic profile at research standing.** It authorizes no production
   wire contract, no H2 architecture, and no legal-effective-date adjudication.
2. **The delta is small on purpose.** Most of the work is *wire-existing* and
   *extend-existing* across family owners; the only genuinely new projections are the
   advisory `LateEventAssessment`, the `TemporalMutationRelation` vocabulary, and the
   `TemporalReplayReceipt`.
3. **Ratified in pair with S0-K09**, which required exactly this: preserve source,
   custody, and repository temporal roles wherever their collapse could change
   authority or replay, without freezing a universal clock vocabulary.
4. **Adoption is per-boundary, not global.** A family adopts the profile when a
   consumer needs cross-family comparison; there is no migration wave, and no
   contract is rewritten to satisfy the vocabulary alone.

## 9. Status

Accepted as the target spec for custody-bearing temporal work. Handoffs stay with
their owners: OPS-R1/R2/R3/R8 (suspension, affected sets, resume, world release),
OPS-R10/R11 (legal family adapters), PAO-R36 / INT-R7 / INT-R8 / Atlas (public
correction and currentness), and OPS-R15 with S0-GAP-02 (benchmark predicates). No
code is written from this document directly — it governs the shape of the tasks, the
same way CGF governs grounding and RACE-HOG-PODS governs search.
