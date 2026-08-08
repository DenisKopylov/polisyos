---
title: PAO-R36 - Amendment Ledger After Independent Audit
research_id: PAO-R36
status: amendment_delivered_pending_conformance
result_standing: accepted_narrow_scope
audit_disposition_of_submitted_version: NO_GO
amendment_status: pending_independent_conformance
audited_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
audit_commit: 9bbfd37a218222ae06c1f669b95dba37c4732765
pinned_repository_commit: 109ba3f4
amendment_branch: research/pao-r36-amendment
research_only: true
authoritative_for:
  - pao_r36_amendment_disposition_by_audit_finding
  - pao_r36_r1_r14_execution_map
  - pao_r36_amended_file_register
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, archive, signer, publication-of-record venue, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - proof that independent conformance has passed
  - automatic amendment of any plan, backlog, or system-design decision
---

# PAO-R36 amendment ledger after independent audit

## 1. Amendment posture

The independent audit found the submitted package `NO_GO` because of three internal contract
blockers. It also recorded 24 commendations confirming the architecture. This amendment repairs the
blockers and executes R1-R14 without weakening the confirmed two-boundary construction, safe
mixed-state observer, frozen enumerated completeness, external-copy honesty, worked hard cases,
ratified-kernel detectability, owner-first placement, or prerequisite-correct capability labels.

The amendment does not claim that the audit is closed. The branch is submitted for independent
conformance verification. `accepted_narrow_scope` remains the research author's standing and is not a
capability, implementation, publication, or legal-sufficiency claim.

Disposition vocabulary:

- `accepted`: the finding is adopted and its required preservation/change is present;
- `accepted_with_variation`: the finding's concern is adopted, but later authoritative evidence
  changes the exact repair; and
- `declined_with_reason`: the finding is not adopted because identified evidence refutes it.

## 2. Finding-by-finding disposition

| Audit finding ID | Disposition | Exact amendment | Landing site |
| --- | --- | --- | --- |
| `PAO-R36-I-001` | **declined_with_reason** | The audit's 47/203/246 `supersede` correction is itself wrong. Architect-supplied complete `git grep` at pin `109ba3f4`, path denominator `policy-engine/src`, all source file types, case-sensitive fixed string, binary excluded, establishes **48 files / 215 matching lines / 260 occurrences**. The connector set was one file short; subtracting the two uppercase-only members from that incomplete set produced 47. | Primary report §4; `orientation-ledger.md` §§1-3; this ledger §4. |
| `PAO-R36-I-002` | **accepted_with_variation** | Matching-line/occurrence units and both file-type denominators are now explicit, using the complete-walk figures: `retraction` all source 7/40/45; Python only 6/39/44. | Primary §4; orientation §§1,3. |
| `PAO-R36-I-003` | accepted | Structural owner/declaration/line-count conclusions are preserved and bound to source byte-identity at the new docs pin. | Orientation §4; primary §4.2. |
| `PAO-R36-I-004` | accepted | Generic cache/subscriber occurrences remain explicitly non-capability-bearing. | Orientation §§3.2,5; integration §2. |
| `PAO-R36-I-005` | **accepted_with_variation** | The original refusal to infer zero from an index was correct. The amendment now records settled 0/0/0 values because the architect supplied a complete pinned tree walk with both denominators. | Primary §4; orientation §§1,3.3. |
| `PAO-R36-II-001` | accepted | Statistical revision policy remains a bounded analogue for policy/classification/vintages/revision analysis, not signer authority or individual legal effect. | External ledger EU-06, UK-01 through UK-04; primary §5. |
| `PAO-R36-II-002` | accepted | Accessibility transfer is narrowed to accessibility of otherwise-required notice, status, links, feedback, and independently grounded recourse. | External ledger EU-04, US-06, UK-08; primary §§5,13. |
| `PAO-R36-II-003` | accepted | COPE source is pinned to **Retraction Guidelines Version 3, August 2025**, DOI retained, with revisit note. | External ledger SCH-01. |
| `PAO-R36-II-004` | accepted | Council Regulation No 1 now supports governed language enumeration/communication only; language-invariant identity is attributed to the PAO interface requested from INT-R6. | External ledger EU-03 and synthesis; integration §4.1; primary §5. |
| `PAO-R36-II-005` | accepted | Legal/publication sources remain explicit analogues and create no direct PolicyOS duty, venue, deadline, remedy, or sufficiency claim. | External ledger §§1,3. |
| `PAO-R36-III-001` | accepted | One controlling order now publishes the staged notice and proves the authority fence before the current-head event. Each choice names the forbidden observation it prevents. The same table appears verbatim in primary §8 and detailed contract §7. | Primary §§8-9; detailed §§7-8. |
| `PAO-R36-III-002` | accepted | `R_gate` is explicitly the complete pre-declaration record set. Step 12 appends the declaration and creates `R_post = R_gate union {declaration}`, count delta +1. The declaration is not an undeclared exclusion. | Primary §6.2; detailed §4 and Step 12. |
| `PAO-R36-III-003` | accepted | Every `N/P` member's receipt obligation, owner, cutoff, provenance class, and reconciliation source are frozen at Step 0. Unknown defaults synchronous; later sync-to-async change is rejected/appended. | Primary §11; detailed §§6,7 Step 0/8,10; F05-B/F05-C. |
| `PAO-R36-III-004` | accepted | Observer labels now project a full tuple binding correction identity, selected versions, exact notice/phase, authenticated `as_of`, projection relation, and authoritative-language result. Wrong/staged notice cannot satisfy a positive label. | Primary §10; detailed §9; F22-A/B/C and F01-B. |
| `PAO-R36-III-005` | accepted | Append sequence is strict independently of display timestamps; evidence cutoffs precede effect; backdating and reversed equal-time order are rejected. | Primary §6.1; detailed §3; F20-A/B/C. |
| `PAO-R36-III-006` | accepted | The two-boundary construction remains the governing result. | Primary §§1-3,6; detailed §§1,3. |
| `PAO-R36-III-007` | accepted | The three safe mixed-state labels remain exclusive; ordering is fixed rather than widening the observer state space. | Primary §§9-10; detailed §§8-9. |
| `PAO-R36-IV-001` | accepted | `S/C` snapshots now bind exact registry/config generations. Generation change blocks/restarts admission; a new controlled member cannot become an external exclusion. | Primary §6.3; detailed §5; F21. |
| `PAO-R36-IV-002` | accepted | Unknown external copies remain explicit exclusions; universal internet-cleared language remains forbidden. | Primary §§12,18; detailed §§4,14; F14. |
| `PAO-R36-IV-003` | accepted | Snapshot/member/count/cutoff/exclusion/recomputation discipline is preserved and strengthened with generation and exact receipt tuple binding. | Primary §§6,12; detailed §§4-6. |
| `PAO-R36-V-001` | accepted | Risk-increasing case remains decidable without legal-sufficiency claims; obligation freeze closes the audit escape hatch. | Primary §15.1; comparative §4; F10/F05-B/F05-C. |
| `PAO-R36-V-002` | accepted | Predecessor remains version-bound, retrievable, archive-linked, and intelligible for past decisions; no automatic retroactivity/remedy is asserted. | Primary §15.2; comparative §5; F13-A/B. |
| `PAO-R36-V-003` | accepted | Revoked-key case retains separate terminal INT-R7 dimensions and no local crypto redesign. | Primary §15.3; comparative §6; F09-A/B. |
| `PAO-R36-VI-001` | accepted | Conditional/disjunctive/phase-dependent/set-wide cases are split into deterministic variants. Named members or explicit `FAIL_CLOSED_ALL(X)` are used. | `falsifier-suite.md` F01-A/B, F03-A-D, F05-A-C, F06-A/B, F07-A/B, F08-A/B, F11-A-C, F13-A/B, F15-A/B. |
| `PAO-R36-VI-002` | accepted | F13 survives as two exact `as_of` inversion variants. | F13-A and F13-B. |
| `PAO-R36-VI-003` | accepted | F16 remains the remove-one-member/keep-green-markers probe. | F16. |
| `PAO-R36-VI-004` | accepted | Serialized stale-base attack C1 `v1->v2`, then stale C2 `v1->v3`, is added; one head at every instant no longer evades the suite. | F18; detailed P37 detector row. |
| `PAO-R36-VI-005` | accepted | Every receipt binds the exact correction/snapshot/generation/predicate/version/notice/cutoff/verifier tuple; complete C1 receipt-family replay into C2 fails. | Detailed §5; primary §6.3; F19. |
| `PAO-R36-VI-006` | accepted | F09 remains a genuine two-direction laundering attack, now split into exact variants. | F09-A/B. |
| `PAO-R36-VII-001` | accepted | Non-erasure/currentness law remains behaviorally detectable through identity, relation, surface, archive, key, and recovery probes. | Detailed §§7-9; F02/F03/F07/F09/F11. |
| `PAO-R36-VII-002` | accepted | PV-K04 continues to bind notice compression and full tuple projection. | Primary §13; detailed §11; F06/F22. |
| `PAO-R36-VII-003` | accepted | Existing evolution/projection/currentness owners remain controlling; no parallel owner is introduced. | Integration §§1-4; primary §§3,17. |
| `PAO-R36-VIII-001` | accepted | OPS-R14 seam remains closed and is not re-adjudicated; PAO retains only correction semantics. | Integration §4.4; detailed §15; primary §17. |
| `PAO-R36-VIII-002` | accepted | INT-R6 remains an interface dependency; no parity mechanism is smuggled into F01 or the contract. | Integration §4.1; detailed §§7 Step 7,15; F01-A/B. |
| `PAO-R36-VIII-003` | accepted | Every final INT-R7 outcome statement now cites/read-throughs terminal controlling Section 18 at `:620-760`. | Primary §§3,13,15.3; detailed §§2,4,11,13,15; comparative §6; integration §§2,4.3; orientation §4. |
| `PAO-R36-IX-001` | accepted | Existing public-export producer and HTTP consumer boundary remain explicitly evidenced; absent production connection remains `bridge_missing`. | Orientation §§4-5; integration §2. |
| `PAO-R36-IX-002` | accepted | Correction notice/feed/subscriber/cache/archive/end-to-end states remain `absent/unallocated`, not prerequisite-invalid labels. Settled zeroes strengthen the conclusion. | Orientation §§3.3,5; integration §§1-2,6; primary §18. |
| `PAO-R36-X-001` | accepted | All amended artifacts retain research-only prohibitions; no erasure, parallel owner, translation mechanism, recovery objective, expiry rule, legal sufficiency, vendor appointment, implementation, or gate opening is introduced. | Frontmatter and conclusion/prohibition sections across all eight amended artifacts. |
| `PAO-R36-X-002` | **accepted_with_variation** | `accepted_narrow_scope` remains substantively honest, but the amendment explicitly states `pending_independent_conformance` and does not claim the audit's `NO_GO as submitted` is closed. | Frontmatter and result-standing sections in all amended artifacts; primary §§1,19. |

## 3. R1-R14 execution register

| Revision | Required change | Executed amendment | Evidence location |
| --- | --- | --- | --- |
| R1 | One order; notice and fence before authority; justify each choice; close two crash windows. | Canonical 14-step table is verbatim in primary/detailed; Step 3 closes successor-current-without-notice; Step 9 closes predecessor-current; crash cuts are explicit. | Primary §§8-9; detailed §§7-8. |
| R2 | Remove circular `Complete(R)`. | `Complete(R_gate)` is precondition; event creates `R_post`; declaration membership/count delta is explicit. | Primary §6.2; detailed §4 and Step 12. |
| R3 | Freeze synchronous receipt predicate. | Per-member obligation/provenance/owner/cutoff frozen Step 0; unknown synchronous; mutation rejected. | Primary §11; detailed §10; F05-B/C. |
| R4 | Bind observer label to full correction tuple. | Full tuple and exact positive-label predicates defined; wrong/staged/stale variants fail closed. | Primary §10; detailed §9; F22-A/B/C. |
| R5 | Falsifiable event order and anti-backdating. | Strict append sequence plus nondecreasing authenticated time/evidence cutoff; three exact attacks. | Primary §6.1; detailed §3; F20-A/B/C. |
| R6 | Bind `S/C` to controlled generation. | Generation equality is a completeness predicate; drift forces restart/re-probe. | Primary §6.3; detailed §5; F21. |
| R7 | Split ambiguous falsifiers. | Every affected base ID has deterministic variants with one detector/verdict/forbidden outcome. | Falsifier suite §4. |
| R8 | Serialized stale-base correction. | Added F18. | F18; detailed P37 table. |
| R9 | Exact correction-bound receipts. | Full receipt tuple and cross-correction replay attack. | Primary §6.3; detailed §5; F19. |
| R10 | Reconcile census with denominators. | Architect-supplied complete-walk figures adopted; audit I-001 declined; zeroes settled. | Primary §4; orientation §§1-3; this ledger §4. |
| R11 | Cite INT-R7 terminal controlling layer. | All load-bearing INT-R7 claims read through Section 18 `:620-760`. | Primary, detailed, comparative, integration, orientation. |
| R12 | Narrow accessibility transfer. | Accessibility attaches to otherwise-required notice/feedback/recourse only. | External EU-04/US-06/UK-08; primary §5. |
| R13 | Narrow Regulation No 1 transfer. | Source supports governed language enumeration; identity/parity assigned to INT-R6 interface. | External EU-03/synthesis; integration §4.1; primary §5. |
| R14 | Pin COPE edition/date. | Version 3, August 2025, DOI and revisit note recorded. | External SCH-01. |

## 4. Settled census recorded under P35

Common method: complete tree walk at `main@109ba3f4`; path denominator `policy-engine/src`;
case-sensitive fixed strings; binary files excluded.

| Token | File-type denominator | Files | Matching lines | Occurrences |
| --- | --- | ---: | ---: | ---: |
| `supersede` | all source; all 48 are Python | **48** | **215** | **260** |
| `superseded` | all source | **34** | **154** | **183** |
| `retraction` | all source | **7** | **40** | **45** |
| `retraction` | Python only | **6** | **39** | **44** |
| `cache_invalidat` | all source | **3** | **5** | **6** |
| `subscriber` | all source | **3** | **18** | **21** |
| `correction_notice` | all source | **0** | **0** | **0** |
| `notify_subscribers` | all source | **0** | **0** | **0** |
| `correction_feed` | all source | **0** | **0** | **0** |

The audit's `supersede` correction is declined rather than averaged. Its two uppercase-only
subtractions were correct; its indexed starting set was incomplete by one file. This is the exact
failure mode the P35 index rider warns against.

## 5. Amended file register

The amendment updates the seven working research documents in place and adds this ledger:

1. `policy-engine/docs/research/policy-operations/pao-r36-public-correction-and-durable-notice.md`;
2. `policy-engine/docs/research/policy-operations/pao-r36/ordered-fanout-and-completeness-contract.md`;
3. `policy-engine/docs/research/policy-operations/pao-r36/falsifier-suite.md`;
4. `policy-engine/docs/research/policy-operations/pao-r36/comparative-models-and-hard-cases.md`;
5. `policy-engine/docs/research/policy-operations/pao-r36/repository-integration-and-dependencies.md`;
6. `policy-engine/docs/research/policy-operations/pao-r36/orientation-ledger.md`;
7. `policy-engine/docs/research/policy-operations/pao-r36/external-primary-source-and-transfer-ledger.md`; and
8. `policy-engine/docs/research/policy-operations/pao-r36/amendment-ledger.md`.

No audit artifact, sibling research artifact, source file, workflow, binary, upload fragment, staging
directory, or self-executing transport artifact is modified.

## 6. Conformance handoff

Independent conformance should execute, not keyword-check:

- the Step 10 crash cut with notice and fence already active;
- `R_gate` completion followed by exact one-member `R_post` delta;
- rejection of a sync-to-async obligation mutation and of effect with an unverified synchronous
  member;
- wrong notice, staged notice, stale snapshot, and language-widening tuple failures;
- early/backdated/reversed effective-event failures;
- controlled-generation drift;
- exact receipt-family replay rejection;
- stale-base C2 rejection/re-admission;
- falsify-the-declaration with markers intact; and
- the settled census with both denominators.

This ledger is evidence of the amendment text and declared fixtures only. It is not independent proof
that the amended branch conforms.
