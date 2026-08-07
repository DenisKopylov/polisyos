---
title: PAO-R36 - Recommended Revision Register
status: delivered_independent_audit
audit_id: PAO-R36
verified_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
audit_branch: research/pao-r36-independent-audit
research_only: true
authoritative_for:
  - pao_r36_audit_revision_requirements
  - pao_r36_required_for_standing_separation
  - pao_r36_revision_execution_evidence
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, custodian, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog, or system-design decision
---

# PAO-R36 recommended revision register

## 1. Standing rule

The independent audit disposition is **`NO_GO` as submitted**. This is not a fiat change to the
research's own `accepted_narrow_scope` standing. It means the submitted package cannot enter
consolidation unchanged because its load-bearing contract contradicts itself and contains a circular
effective gate.

`R1` through `R10` are **required for standing**. The research may retain `accepted_narrow_scope`
after those revisions if the revised text and independent conformance evidence close every listed
finding. `R11` through `R14` are improvements: they correct citation/transfer precision but do not by
themselves determine the formal safety of the contract.

No item authorizes implementation. Execution evidence means revised research text, a deterministic
semantic fixture, or an independent audit reproduction—not production deployment.

## 2. Required for standing

### R1 — reconcile the authority/notice/fence order

**Defect.** `PAO-R36-III-001` (blocking). The primary report transitions authority before arming the
fence and publishing the notice, while the detailed contract requires the notice visible and fence
armed before transition.

**Required change.** Publish one controlling ordered sequence across all seven artifacts. At minimum:

1. prepare and verify notice/version relations;
2. make the notice safely visible in staged/non-current form;
3. arm and prove the authority fence over every admitted `S/C` member;
4. append the current-head transition; and
5. run post-transition member probes before effectiveness.

The primary report's step table must not preserve the contradictory order. State which artifact is
controlling if summaries remain.

**Evidence of execution.** A cross-file order ledger quotes every step reference and shows one
identical precedence graph. Execute two semantic fixtures: crash immediately after `t_authority` and
before any later step; every `S/C` member must already return successor-current-linked,
predecessor-historical-linked, or fail-closed, and the notice must already resolve.

### R2 — remove the self-referential `Complete(R)` gate

**Defect.** `PAO-R36-III-002` (blocking). `R` contains the effective declaration while
`Complete(R)` is a precondition for appending that declaration.

**Required change.** Separate the pre-effect record/evidence closure from the effective-declaration
event. The precondition must be computed over objects that already exist. After append, the effective
event may join the historical transaction record.

**Evidence of execution.** A delete-effective-event fixture can satisfy every pre-effect requirement
without treating a draft/placeholder declaration as complete; effect is then appended exactly once.
A remove-one-pre-effect-record fixture remains red.

### R3 — freeze the synchronous notification obligation at admission

**Defect.** `PAO-R36-III-003` (blocking). `P` membership may be frozen while the rule deciding whether
actual receipt is pre-effect remains mutable.

**Required change.** Before `t_authority`, freeze an authorized obligation disposition for the case:
no direct cohort; notification-intent-before-effect; or qualifying-receipt-before-effect. Unknown or
missing classification blocks. A later institutional change is a new append-only decision and cannot
retroactively manufacture an effective pass.

**Evidence of execution.** Run a fixture in which delivery fails and the classifier attempts to
downgrade receipt-before-effect to asynchronous. Expected outcome: no `t_effective`, red obligation
integrity, and an appended attempted-change record rather than a rewritten classification.

### R4 — bind the public-observer invariant to the full correction tuple

**Defect.** `PAO-R36-III-004` (material). The three-label `state(s,t)` predicate does not bind
correction identity, selected notice, phase, authenticated cutoff, projection parity, or language
parity.

**Required change.** Define the observable proposition over a semantic tuple. Preserve the three
high-level authority postures as a projection, but require every positive/historical result to bind
the same correction identity, expected predecessor/successor, notice identity and phase,
authenticated `as_of`, projection relation, and authoritative-language result.

**Evidence of execution.** Add red fixtures for: correct successor with the wrong notice; correct
successor with a staged notice after authority transition; stale authenticated currentness snapshot;
and one authoritative language that widens permission. Each must fail even if the high-level label is
`successor_current_linked`.

### R5 — make event order falsifiable

**Defect.** `PAO-R36-III-005` (material). `t_stage <= t_authority <= t_effective` is prose without an
append-order or anti-backdating verifier.

**Required change.** State the required event precedence independently of display timestamps. Define
what equal timestamps mean, require every effective evidence cutoff not later than the effective
event, and forbid a derived surface from selecting an earlier displayed effective time.

**Evidence of execution.** Add three attacks: effective event appended before the final member
receipt; later append carrying a backdated effective time; and equal display timestamps with reversed
event order. All must be red. Preserve F13 for version/currentness inversion.

### R6 — bind completeness snapshots to a controlled registry/config generation

**Defect.** `PAO-R36-IV-001` (material). A new controlled route/cache/representation can appear after
`S/C` freeze and before effect while the old denominator passes.

**Required change.** Bind each controlled set to the exact source-of-truth generation used for
admission and require that generation to remain the only active controlled generation until effect,
or require the transaction to extend/restart and re-probe. A PolicyOS-controlled new member may not
be reclassified as an external exclusion.

**Evidence of execution.** Insert a new controlled surface/cache variant after snapshot. The effect
gate must fail or restart with the enlarged denominator. Removing the new member from a hand-written
list while it remains in the live registry must not pass.

### R7 — split ambiguous falsifiers into exact variants

**Defect.** `PAO-R36-VI-001` (material). F03, F05, F08, F11, and F13 use conditional/disjunctive or
set-wide outcomes; F06 omits the required member argument.

**Required change.** Split each into one fixture per phase and obligation class. Every row must have:
one initial state, one attack, one detector, and one exact terminal outcome expressed in the suite's
own vocabulary. Name every failed member or define an explicit all-members operator.

**Evidence of execution.** A conformance ledger lists every revised fixture and proves there is no
“if”, “or”, “as applicable”, unnamed `FAIL_CLOSED`, or phase-dependent expected block inside one row.

### R8 — add stale-base simultaneous-correction control

**Defect.** `PAO-R36-VI-004` (material). F08 detects two simultaneous heads but not serialized
last-writer loss of an intervening correction.

**Required change.** State that the predecessor/base head admitted by a correction must still be the
canonical head immediately before transition, unless a new append-only correction explicitly rebases
on the intervening successor. Add a two-correction attack.

**Evidence of execution.** Stage C1 `v1->v2` and C2 `v1->v3`; transition C1; attempt C2. C2 must block
or be re-admitted against `v2`. A single-head last-writer success is a failing result.

### R9 — content-bind every completion receipt to the correction

**Defect.** `PAO-R36-VI-005` (material). F16 catches member deletion but not reuse of all valid member
receipts from another correction or snapshot.

**Required change.** Require each member result and aggregate join to bind the correction identity,
set snapshot identity/generation, required predicate, selected predecessor/successor/notice, and
cutoff.

**Evidence of execution.** Reuse a complete receipt family from C1 for C2 with identical member names
and counts. The gate must fail even though no row or marker is missing.

### R10 — reconcile Pass I counts and zero claims

**Defect.** `PAO-R36-I-001` (material) and `PAO-R36-I-002` (minor). The exact lowercase `supersede`
count is 47 files, not the unresolved inherited 48; `retraction` lacks matching-line/occurrence
figures.

**Required change.** Update the orientation and primary summary with one count vocabulary and these
re-derived figures:

- `supersede`: 47 files / 203 matching lines / 246 occurrences;
- `superseded`: 34 / 152 / 180;
- `retraction`: 7/40/44 for all source files and 6/39/43 for Python files;
- `cache_invalidat`: 3/5/5; and
- `subscriber`: 3/18/21.

Keep `correction_notice`, `notify_subscribers`, and `correction_feed` as `not_established` complete-walk
zeros unless a recursive exact-pin tree/archive walk is supplied.

**Evidence of execution.** Independent script or exact-case reconciliation prints file, line, and
occurrence denominators and the revised prose/table arithmetic agrees exactly.

## 3. Improvements

### R11 — cite INT-R7's terminal controlling section

**Defect.** `PAO-R36-VIII-003` (minor).

**Required change.** Wherever final public verification/current-authority semantics are stated, add
`policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:620-760` as the
controlling citation. Earlier issuance/revocation rows may remain as historical detail.

**Evidence of execution.** Search every PAO-R36 reference to `int-r7/public-verification-profile.md`;
load-bearing outcome claims point to §18 or explicitly state that earlier text is read through §18.

### R12 — narrow accessibility transfers

**Defect.** `PAO-R36-II-002` (minor).

**Required change.** Revise EU-04 and UK-08 so the sources require accessibility of the correction
notice, status, links, feedback, and any otherwise-required recourse route. Do not say the
accessibility regime creates substantive recourse.

**Evidence of execution.** Source-transfer table and synthesis separate accessibility/feedback from
the independently grounded administrative recourse obligation.

### R13 — narrow the Regulation No 1 transfer

**Defect.** `PAO-R36-II-004` (minor).

**Required change.** State that Regulation No 1 supports governed enumeration and language-specific
institutional publication/communication. Attribute language-invariant correction identity to the
PAO-R36 interface requested from INT-R6, not to the Regulation.

**Evidence of execution.** EU-03's “source proposition” and “transfer” columns no longer claim the
Regulation establishes semantic identity.

### R14 — pin the COPE edition

**Defect.** `PAO-R36-II-003` (minor).

**Required change.** Identify the exact COPE Retraction Guidelines edition/date audited. At audit
time the DOI resolves to Version 3, August 2025. Preserve the DOI and state the edition explicitly.

**Evidence of execution.** The ledger row contains DOI, title, version/date, and a revisit note if the
DOI target changes.

## 4. Closure condition

The audit may move from `NO_GO` only after R1-R10 are executed and independently verified against the
revised branch. Closure requires:

- zero blocking findings;
- no remaining material contradiction in the order, observer predicate, completeness gate, or
  falsifier suite;
- count reconciliation whose prose and table agree; and
- readback of every revised file from the branch after writing.

R11-R14 should be completed before consolidation publication, but they do not substitute for the
standing-critical formal repairs.
