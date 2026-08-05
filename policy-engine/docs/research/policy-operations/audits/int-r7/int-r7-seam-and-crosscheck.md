---
title: INT-R7 — Ratified-Kernel, GY/Atlas, and INT-R8 Seam Crosscheck
verified_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - independent Pass VII conformance check against ratified kernel findings
  - independent Pass VIII proof/content seam audit
  - conflicts and compatibility findings against GY-N12 and Atlas DS12/DS13 plans
  - findings INT-R7-VII-001 through INT-R7-VIII-003
may_not_use_for:
  - amendment or ratification of INT-R7, INT-R8, GY-N12, Atlas, or the custody kernel
  - production implementation authorization
  - final schema, wire, package, serialization, database, or API contract
  - assignment of semantic owner, operator, service, witness, archive, vendor, or custodian
  - legal sufficiency or jurisdictional compliance conclusion
  - claim that INT-R8, GY-N12, or an end-to-end public proof capability has been delivered
research_only: true
---

# INT-R7 seam and crosscheck

## 1. Method

Binding architecture is cited by finding ID, not neighboring prose. The audit crosschecks:

- `INT-K06`, `INT-K02`, `INT-K01`, `INT-K05` from
  `int-wave-claim-semantics-ratification.md`;
- `S0-K07`, `S0-K08`, `S0-K16` from the Stage-0 custody kernel and its accepted
  consolidation record;
- GY-N12 epoch/currentness ownership in `GY-engine-subordination.md`; and
- Atlas DS12/DS13 ownership in `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`.

For INT-R8, repository searches found planning/backlog references but no committed delivered
INT-R8 research result. A repository commit search for `INT-R8` returned no commits, and a
repository content search returned plans/backlog/context rather than a delivered INT-R8
artifact. The brief's more specific account—CI bootstrap workflow plus truncated fragment—is
not promoted as independently established because those exact objects were not readable from a
resolved exact ref. The decision-relevant fact is established: **no delivered INT-R8 content
contract is available to satisfy INT-R7's dependency.**

## 2. Pass VII — ratified-kernel conformance

### 2.1 `INT-K06` — first procedural custody claim, no probability

**Ratified requirement.** The first likely signed object is a falsifiable procedural custody
claim carrying no probability. Its proposition is about history and order.

**INT-R7 treatment.** Primary, not incidental:

- `procedural_custody_claim` is the first claim class in the profile;
- the canonical statement binds prospective seal, firstness population/order, chronology,
  prohibited-substitution policy, deviations, adjudication/evaluator identity, dissent, and
  negative/refusal terminals;
- trusted chronology and anti-backdating are part of the threat model;
- F-12 attacks false prospectivity/firstness rather than merely signature bytes;
- the citizen result has `PROCEDURAL_HISTORY_NOT_ESTABLISHED`.

**Verdict:** conforms strongly. The suite must split F-12's alternative mutations, but the
semantic target is correct.

### 2.2 `INT-K02` — `delta` is inseparable from obligation set and assumptions

**INT-R7 treatment.** `BasisBound` atomically covers value, declared-obligation-set
commitment, maintained-assumptions commitment, rider, proof/evaluation revision, and context.
The work calls omission semantic substitution and makes F-11 a blocking case.

**Verdict:** conforms. The current F-11 vector needs two fixtures, but no presentation-only
escape remains.

### 2.3 `INT-K01` / `S0-K08` — append-only correction and withdrawn history

**INT-R7 treatment.** The lifecycle appends challenge, invalidation, withdrawal,
supersession, reissue, and successor links. Old bytes/signature/time/log evidence remain.
`withdrawn_but_verifiable` and `superseded_but_verifiable` are first-class; F-17 makes a valid
old issuance and false current authority coexist.

**Verdict:** conforms in lifecycle semantics. The formal `HistoricalAuthenticity` aggregate
is too broad because later public-history/preservation failures can erase issuer-side issuance;
that is a formula defect, not a rejection of the withdrawn/current split.

### 2.4 `S0-K16` — bounded meaning of passage

**INT-R7 treatment.** Freeze rule 9 and the scope section state that passage supports only the
named implementation, revision, environment, evaluator, fixture set, trust/status inputs, and
policies. The report does not claim that the suite has run.

**Verdict:** conforms.

### 2.5 `S0-K07` / `INT-K05` — projection cannot mint authority; one owner/no second lattice

**INT-R7 treatment.** The profile:

- calls public export/projection `projection_only`;
- requires institutional authority evidence independently of content projection;
- consumes GY-N12 currentness rather than defining revision triggers or a status owner;
- consumes INT-R8's relation rather than defining retained content, material omission,
  compression loss, or disclosure budget;
- describes citizen outcomes as projections of one predicate report, not a new authority
  ledger.

**Verdict:** conforms. The code-like state lists need a warning against being copied as a
closed implementation enum, but they do not create a second owner in the research.

## 3. Ratified-kernel findings

### INT-R7-VII-001 — commendation — `INT-K06` is the primary security case

Chronology, prospectivity, firstness, negative terminals, and anti-backdating are core proof
semantics, not metadata added to a probabilistic signature profile.

### INT-R7-VII-002 — commendation — `INT-K02` basis completeness is treated as signature security

A bare or basis-substituted `delta` cannot receive a positive result even when a key signs the
incomplete statement.

### INT-R7-VII-003 — commendation — withdrawn-but-verifiable conforms to append-only correction

The verifier can say “validly issued then” and “not current now” without mutating the original.

### INT-R7-VII-004 — commendation — falsifier passage is correctly bounded by `S0-K16`

No broad capability, theorem, legal-compliance, or untested-profile claim follows from 18/18.

### INT-R7-VII-005 — commendation — no second authority ledger or projection owner is created

GY-N12 and INT-R8 remain named semantic owners; INT-R7 owns proof requirements only.

## 4. Pass VIII — proof/content seam

### 4.1 What INT-R7 legitimately owns

INT-R7 may require the public proof to bind:

- a stable retained-claim-set commitment supplied by INT-R8;
- the projection/redaction policy identity and version;
- the proof/reference and typed result of the INT-R8 relation;
- a successor relation when a public projection changes; and
- enough retained evidence to verify that relation offline.

Those are proof-input and proof-lifecycle requirements. They do not decide which claims are
retained or what omissions are materially safe.

### 4.2 Boundary-crossing hunt

Across 10/10 audited artifacts, no passage was found that:

- chooses the retained public claim set;
- defines compression-loss magnitude or acceptability;
- defines `lossy_but_safe` or `blocked_material_omission` semantics;
- allocates or composes a disclosure budget;
- chooses which restricted evidence must become public;
- adjudicates privacy versus disclosure; or
- creates an INT-R7-owned content status lattice.

The work does require high-entropy/hiding locators, binds human/accessibility transformations,
and says a projection failure blocks public proof. These are proof/privacy-integrity
requirements. They do not select public content. References to possible INT-R8 typed outcomes
are explicitly non-definitional.

### 4.3 Required interface quality

The declared interface is sufficiently explicit to survive pending delivery:

1. stable retained-claim-set commitment;
2. deterministic or otherwise verifiable projection/redaction relation;
3. policy/version identity;
4. typed pass/failure result;
5. successor relation; and
6. offline-verifiable evidence.

INT-R7 does not assume that every candidate record can pass. If INT-R8 concludes that a safe
projection cannot be produced, INT-R7 blocks the **public projection/proof result**. That is a
valid gate rather than an attempt to dictate the content answer.

### 4.4 What fails because INT-R8 is absent

Every positive baseline/profile result that sets `ProjectionRelationValid=true` is currently
unsatisfied. In particular:

- baseline B0/B1 are hypothetical semantic fixtures;
- no `VerifiedCurrent` public projection can be executed;
- F-16 cannot perform complete offline verification;
- the first-public-signature gate remains closed; and
- no repository capability may be inferred from the interface specification.

### 4.5 Load-bearing formal error

The seam ceases to be clean inside the formal aggregate:

```text
ProjectionRelationValid
  -> StatementComplete
  -> IssuanceAuthentic
  -> HistoricalAuthenticity
```

This makes an absent or failed INT-R8 projection relation negate issuer-side issuance
authenticity. The correct effect is narrower:

- issuer-side issuance may remain authentic;
- public projection faithfulness is not established;
- no public-current positive result is permitted.

This is the highest-value required revision because INT-R8 is not delivered and because future
projection loss/withholding must not rewrite historical issuer facts.

## 5. GY-N12 compatibility

INT-R7 correctly consumes:

- epoch identity and semantic revision;
- authenticated current-head/status projection with `as_of`;
- current, stale, revalidation-required, unresolved/OpenWorldRisk, challenged, withdrawn,
  invalidated, superseded and reissued relations; and
- historical replay.

It does not own revision triggers or currentness adjudication. No circularity was found where
GY assumes INT-R7 creates currentness. The unresolved issue is delivery: GY-N12 is planned,
not implemented, so all current-authority outcomes are conditional contracts.

The snapshot anti-rollback issue is not a GY ownership transfer. GY may own the status history;
INT-R7 must still state what a verifier proves when presented with an authentic older snapshot.

## 6. Atlas DS12/DS13 compatibility

Atlas DS12 requires a real public proof chain and the INT-R7/INT-R8 gate before the first
public record. DS13 later owns richer accountability/transparency surfaces. INT-R7's minimum
log inclusion, witnessed common view, challenge/withdrawal visibility, and offline proof closure
before first publication do not improperly pull the entire DS13 product surface into DS12.
They are safety properties of the first proof.

No conflict was found with Atlas ownership. The legacy FNV strangle is aligned with DS12. The
research does not claim that the planned route, producer, or viewer has been implemented.

## 7. Pass VIII findings

### INT-R7-VIII-001 — commendation — the proof/content seam is explicit and disciplined

**Evidence:** content-seam sections in the primary report, profile, threat model, integration
handoff, citizen UX, and falsifier suite.

The declared interface survives pending INT-R8 delivery and does not pre-decide compression or
disclosure semantics.

### INT-R7-VIII-002 — material — no delivered INT-R8 result satisfies the interface

**Evidence:** repository searches resolve only planning/backlog/context references and no
committed delivered INT-R8 research artifact or commit. The exact failed-upload mechanics are
`not_established` by this audit; the missing result is established.

All INT-R8-dependent positive outcomes remain hypothetical and the first-signature gate stays
closed.

### INT-R7-VIII-003 — material — projection failure is incorrectly allowed to erase issuer-side authenticity

**Evidence:** `ProjectionRelationValid` is nested through `StatementComplete` into
`IssuanceAuthentic` and `HistoricalAuthenticity`.

Move projection faithfulness to a separately reportable component and require it only for
public-projection/current aggregate outcomes.

## 8. Crosscheck conclusion

INT-R7 is coherent under the non-delivery of INT-R8 **as an interface-and-gate research
artifact**, not as an executable public-verification profile. Its ownership boundaries and
ratified-kernel alignment are strong. The formal aggregate must be revised so that the missing
content proof blocks public verification without falsifying the historical issuer event.
