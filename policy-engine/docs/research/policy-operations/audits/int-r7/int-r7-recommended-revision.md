---
title: INT-R7 — Independent Recommended Revision Register
verified_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - executable revision register R1 through R22 for the audited INT-R7 research
  - distinction between revisions required to retain standing and optional improvements
  - evidence conditions for verifying that each revision was completed
may_not_use_for:
  - rewriting the audited research automatically
  - adoption or ratification of any proposed revision
  - production implementation authorization
  - final schema, wire, package, serialization, database, or API contract
  - owner, vendor, authority, trust-service, log, witness, archive, or custodian appointment
  - legal sufficiency or jurisdictional compliance conclusion
research_only: true
---

# INT-R7 recommended revision register

## 1. Revision classes

- **Required for standing** — without the revision, the current `GO_WITH_REVISIONS` research
  cannot be consolidated as internally coherent, capability-honest, source-honest, or
  executable as a specification.
- **Improvement** — raises precision or coverage but does not independently change the current
  standing.

This register does not rewrite INT-R7. It states the defect, required change, and observable
evidence of execution.

## 2. Required for standing

### R1 — split issuer authenticity from projection, public history, and durable verifiability

**Defect.** `ProjectionRelationValid` is inside `StatementComplete`; public history and
preservation are inside `HistoricalAuthenticity`. An INT-R8 failure, withheld projection, lost
witness snapshot, or archive break can therefore negate the issuer-side issuance event.

**Required change.** Revise the formal argument so that issuer issuance authenticity,
projection faithfulness, public-history establishment, durable verifiability at `t_v`, and
current authority at `t_q` are separately reportable. Top-level public-current outcomes may
require their conjunction. Do not prescribe a wire format or enum.

**Execution evidence.** Updated formulas in the threat-model artifact; corresponding language
in the primary report, profile, lifecycle, UX, and suite; F-08 and INT-R8-failure fixtures that
preserve issuer issuance while blocking the public/current positive.

### R2 — make snapshot selection/anti-rollback explicit

**Defect.** An authentic pre-withdrawal status/trust snapshot can be replayed after a newer
authentic withdrawal or compromise snapshot exists.

**Required change.** Add a separately named latest/monotonic-selection result under a declared
distribution policy, or state that the verifier proves only the supplied snapshot and cannot
claim latest currentness. Bind the citizen wording to that result.

**Execution evidence.** Formal predicate/result, UX mapping, offline-profile text, and a frozen
attack where a complete authentic old snapshot is presented after a newer withdrawal.

### R3 — mark INT-R8-dependent positives as hypothetical and unsatisfied

**Defect.** INT-R8 has no delivered research result in the inspected repository state, while
baseline B0/B1 and positive formulas assume a passing relation.

**Required change.** Add an explicit unresolved-dependency statement at every positive baseline,
profile gate, and suite execution boundary. State that issuer-side issuance can still be
evaluated separately after R1, but no public projection/current result can pass.

**Execution evidence.** B0/B1 labelled hypothetical; main/profile/suite/dependency documents all
state “not executable until a delivered INT-R8 contract is pinned”; no wording claims a present
projection proof.

### R4 — mark GY-N12 current outcomes as contract-only/planned

**Defect.** GY-N12 is a canonical plan, not an implemented producer/verifier. Some prose reads
like a complete currentness mechanism rather than an interface.

**Required change.** State at every currentness-positive boundary that the result is conditional
on a delivered authenticated GY-N12 output/history interface.

**Execution evidence.** Dependency table, baseline fixture, result formulas, UX and first-signature
gate use the same planned/undelivered qualification.

### R5 — repair all new-capability missing-state labels

**Defect.** The repository vocabulary defines `producer_missing` as “a consumer expects an
artifact/event but no deployed producer emits it.” N-01 through N-07 and the public proof/temporal-verifier handoff use downstream labels without evidenced prerequisite consumers, endpoints, or wired chains.

**Required change.** Reclassify N-01 through N-07 and the public proof/temporal-verifier summary rows from pinned evidence. Use `contract_only` only where a
real admitted type/contract exists with no producer/consumer/workflow; otherwise state
`absent/unallocated at pinned commit` without upgrading it into a repository capability label.
Retain `bridge_missing` for the real public-export producer and its absent route.

**Execution evidence.** Revised N-01..N-07 and summary tables with one evidence citation per label; no `producer_missing` row lacks a named consumer, no `bridge_missing` row lacks both endpoints, and no `verification_missing` row lacks a wired chain. This closes blocking finding INT-R7-X-001.

### R6 — make every frozen predicate expectation exact

**Defect.** At least 7/18 cases contain conditional/disjunctive values that cannot satisfy the
suite's exact-equality rule; F-12, F-13 and F-18 also conflate subcases or policy/math results.

**Required change.** Split alternative mutations into separate fixtures/subfixtures and replace
prose values with exact typed predicate values plus an independent evaluation-status field for
not-evaluated/short-circuited predicates. Preserve existing case IDs as immutable families or
version the suite rather than weakening them in place.

**Execution evidence.** A machine-readable expectation for every case; a static validator that
rejects `or`, `if`, `under_*`, or free-prose pseudo-values in predicate slots; equality harness
can load all cases without interpretation.

### R7 — correct F-04's terminal taxonomy

**Defect.** F-04 expects `TAMPERED_OR_SIGNATURE_INVALID` while `SignatureValid=true`; the actual
failure is unauthorized/invalid temporal issuance after effective revocation.

**Required change.** Introduce or use a precise temporal/authorization terminal and preserve the
true signature-math result visibly.

**Execution evidence.** Updated F-04 expected vector and matching UX/reason-code taxonomy; a test
asserts the tamper/signature-invalid terminal is forbidden for this fixture.

### R8 — correct F-08 after the aggregate split

**Defect.** Split-view witness failure makes `HistoricalAuthenticity=false`, erasing otherwise
established issuer issuance.

**Required change.** Report issuer issuance separately as established (when all issuance inputs
pass), report common view as not established, and block every public-current positive.

**Execution evidence.** Updated F-08 vector, formal aggregate, machine/human expected output, and
reason codes.

### R9 — add the four minimum missing attacks

**Defect.** The frozen gate does not catch signer+TSA collusion, authentic-snapshot rollback,
conflicting valid succession claims, or parser/canonicalization differentials. Selective
negative-terminal withholding is also missing and is required for the `INT-K06` case.

**Required change.** Add all five attacks under a new suite version or as mandatory exact
subfixtures, without weakening F-01..F-18.

**Execution evidence.** Fixtures and exact outcomes for A-X1 through A-X5; suite denominator and
result block updated; S0-K16 scope retained.

### R10 — make the pre-first-signature recovery drill non-circular

**Defect.** “Real disconnected recovery drill before first signature” can be read as requiring a
live public record before the first live public record.

**Required change.** Specify a representative non-authoritative/ceremonial corpus that traverses
the real verifier, trust/status, log/witness, projection/currentness fixture, preservation and
disconnected restore paths before live issuance, followed by a bounded first-live-record drill.
Do not accept a paper runbook.

**Execution evidence.** Revised gate text, named pre-live fixture class, exact expected report,
and explicit first-live follow-up trigger.

### R11 — add anti-rollback and compromised-primary/cross-custody recovery outcomes

**Defect.** A year-12 archive can restore an authentic but stale snapshot or an internally
consistent closure from one compromised custody domain.

**Required change.** Require observable detection of stale authentic snapshots under the declared
policy and successful verification/recovery when primary custody/control infrastructure is
unavailable or compromised. Leave topology/vendor/RPO/RTO to OPS-R14.

**Execution evidence.** Gate checklist and recovery fixtures include stale-snapshot and
compromised-primary cases; result report identifies independent/cross-custody evidence without
appointing a provider.

### R12 — reclassify NARA US-01 as historical-only

**Defect.** Official NARA page says the 2005 PKI guidance is superseded and no longer accurate.
The research uses its Trust Documentation Set language in present-tense preservation support.

**Required change.** Label it historical precedent, remove any present normative implication,
and add a current records/retention authority where a current requirement is asserted.

**Execution evidence.** Source ledger, lifecycle/profile discussion and primary report all show
`historical_only`; current requirements cite a current source or are stated as INT-R7 design
requirements.

### R13 — narrow Federal PKI US-02

**Defect.** The Delegated Digital Signature Playbook is nonbinding and specific to Federal
Register submissions.

**Required change.** State the official disclaimer and exact subject-matter scope wherever the
source supports purpose-limited delegation controls.

**Execution evidence.** Source ledger and comparative/authority discussion contain the same
nonbinding, use-case-specific transfer limit.

### R14 — record the missed orientation date correction

**Defect.** The orientation ledger confirms O-14 but does not catch the false claim that
ratification occurred four days earlier. Ratification, pinned commit, principal decision and
inspection all date to 2026-08-04.

**Required change.** Add a corrected orientation entry and remove/qualify the briefing timeline.

**Execution evidence.** Revised ledger row cites ratification frontmatter and states the same-day
fact explicitly.

### R15 — add an explicit public evidence-obtainability result

**Defect.** A proof can be technically complete but selectively unavailable to citizens,
journalists, courts, or other agencies. A-10 discusses suppression, but the result vector does
not expose obtainability or lawful restriction.

**Required change.** Add a separate service/public-administration result distinguishing public
availability, records-process availability, competent lawful restriction, and not established.
Do not make it part of signature authenticity.

**Execution evidence.** Threat model, predicate/report semantics, citizen UX and at least one
withholding fixture use the result.

## 3. Improvements

### R16 — replace “independent predicates” with “separately reportable dimensions”

**Defect.** Several dimensions are derived or depend on others.

**Required change.** Retain failure visibility but remove the mathematical independence claim.

**Execution evidence.** Headline, formal section and executive summary use consistent wording.

### R17 — correct minor source metadata and attribution

**Defect.** PAdES edition date is wrong; RFC 9162 is made to sound like it standardizes the
chosen witness policy; Sigstore's general verification page is used for fields documented more
precisely in Bundle Format.

**Required change.** Set ETSI-05 to 2024-01; label witness quorum as design inference; add exact
Sigstore Bundle Format locator.

**Execution evidence.** Updated 30-row source ledger and all affected citations.

### R18 — add a global anti-wire-format warning

**Defect.** Backticked state/result lists and `verify_public_record(...)` can be copied as a
canonical enum/API despite frontmatter prohibitions.

**Required change.** State once in each relevant artifact that names and function notation are
semantic distinctions/examples, not a closed enum, schema, wire format, package or API.

**Execution evidence.** Warning appears in lifecycle, UX, profile and suite; no text says an
implementation must use those exact encodings.

### R19 — add a positive lawful succession case

**Defect.** F-18 protects against substitution but does not show the valid path where a successor
appends custody/status while predecessor attribution remains.

**Required change.** Add a positive fixture and human/machine output.

**Execution evidence.** Successor credential authentic; predecessor remains original issuer;
preservation/currentness result is bounded to the successor's actual role.

### R20 — preserve exact set-level reproduction artifacts

**Defect.** O-05 and O-09 rely on connected searches/scripts whose complete output is not retained
with the research.

**Required change.** Retain plain-text script output or a bounded generated ledger naming commit,
root, inclusion rule and denominator. Do not add self-executing automation to the repository.

**Execution evidence.** Reviewable static outputs for the pinned commit; re-run instructions
reproduce the same set.

### R21 — distinguish local cryptographic validity from policy satisfaction in threshold cases

**Defect.** F-13 uses `SignatureValid: false_under_required_signature_policy`, conflating one
mathematically valid signature/partial contribution with failure of the required authorization
quorum.

**Required change.** Report local cryptographic verification and signature-policy/quorum
satisfaction separately.

**Execution evidence.** Exact F-13 vector and predicate definitions show both values.

### R22 — add source-currentness review metadata

**Defect.** Long-lived research can silently continue relying on sources later superseded, as
US-01 demonstrates.

**Required change.** Add checked-on date and current/superseded status for institutional guidance
where source currentness is load-bearing, without claiming automatic future monitoring.

**Execution evidence.** External ledger has a review date/status column and an explicit manual
recheck trigger before consolidation or implementation design.

## 4. Standing gate after revision

The audited work may retain `GO_WITH_REVISIONS` after R1–R15 are executed and independently
verified. R5 is the blocking capability-honesty repair. R1, R2, R6–R9 are necessary for a
coherent/executable formal specification. R3–R4 preserve dependency honesty. R10–R11 protect
the first-signature gate. R12–R14 restore source/orientation honesty. R15 closes a material
public-administration gap.

R16–R22 are improvements and do not independently block the current standing, though they are
strongly recommended before implementation design.
