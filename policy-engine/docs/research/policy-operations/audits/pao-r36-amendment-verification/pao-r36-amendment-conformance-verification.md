---
title: PAO-R36 Amendment - Independent Conformance Verification
verification_id: PAO-R36-AMV
status: delivered_independent_verification
verdict: CONFORMS_WITH_GAPS
blocking_findings: 0
material_gaps: 1
minor_findings: 0
commendations: 11
total_findings: 12
verified_amendment_commit: 926326174135ef6e407037ebcbe2094228430729
audited_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
independent_audit_commit: 9bbfd37a218222ae06c1f669b95dba37c4732765
documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
verification_branch: research/pao-r36-amendment-verification
research_only: true
authoritative_for:
  - pao_r36_amendment_independent_conformance_verdict
  - pao_r36_audit_finding_closure_assessment
  - pao_r36_ratified_kernel_conformance_assessment
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, archive, signer, publication-of-record venue, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - repair or mutation of the amendment branch
  - automatic amendment of any plan, backlog, audit, or system-design decision
---

# PAO-R36 amendment independent conformance verification

## 1. Verdict

**`CONFORMS_WITH_GAPS` — 0 blocking findings, 1 material verification gap.**

The amended semantic contract conforms to all three blocking repairs required by the hostile
independent audit and conforms to the ratified kernels inspected at the documentation pin. The
amendment preserves the audit-confirmed strengths: two separate public boundaries, safe mixed-state
convergence, frozen enumerated completeness, explicit external-copy exclusions, worked adverse and
historical cases, detectable non-erasure, existing-owner placement, and prerequisite-correct
capability labels.

The one gap is Pass I execution. This verifier could establish the branch topology, exact file set,
line counts, blob identities, and both independent `+267` arithmetic paths. It could also establish
that the audit's 47-file correction was not produced from a P35-valid denominator. It could not
independently execute a complete exact-ref source-blob census in this environment, so the amendment's
replacement literal counts—including 48/215/260 for `supersede`—remain corroborated by the registered
P35 record but not freshly re-measured here. That gap is material because the commission made the
declined finding the sharpest orientation test; it is not blocking to the corrected semantic
contract.

No amendment text was repaired or changed by this verification.

## 2. Standing shape

The amendment reports these exact frontmatter field names and values:

| Field | Value |
| --- | --- |
| `result_standing` | `accepted_narrow_scope` |
| `audit_disposition_of_submitted_version` | `NO_GO` |
| `amendment_status` | `pending_independent_conformance` |

This verification does not rewrite those fields. Its separate result is
`verdict: CONFORMS_WITH_GAPS`. The submitted version remains historically `NO_GO`; the author's
research standing remains `accepted_narrow_scope`; and the amendment's own status remains the value
present at the verified commit. Consolidation can now compare those three amendment fields with this
independent verdict without collapsing them.

## 3. Finding count reconciliation

| Severity | Count |
| --- | ---: |
| blocking | **0** |
| material gap | **1** |
| minor | **0** |
| commendation | **11** |
| **Total** | **12** |

The prose and table agree: **12 findings = 0 blocking + 1 material + 0 minor + 11 commendations**.

## 4. Complete finding register

| ID | Severity | Finding | Evidence and verdict |
| --- | --- | --- | --- |
| `PAO-R36-AMV-I-001` | material | The complete source literal census was not independently executable through the available connector/egress path. | The audit's index denominator is invalid under P35, so 47/203/246 cannot stand as a complete census. The documentation pin records the architect's complete-walk figures and omission mechanism, but this verifier could not walk every source blob. Exact replacement counts remain independently unestablished. |
| `PAO-R36-AMV-I-002` | commendation | Repository shape and both delta calculations reproduce exactly. | Eight Markdown files, eight commits ahead/zero behind, audited head as merge base; amendment 2,564 lines minus audited 2,297 equals +267; remote 2,164 additions minus 1,897 deletions also equals +267. |
| `PAO-R36-AMV-III-001` | commendation | The single controlling order closes both forbidden crash windows. | The staged notice is publicly resolvable at Step 3; the fence is proved at Step 9; authority appends at Step 10. Each row names the forbidden observation it prevents. The table blocks in the primary and detailed files are identical UTF-8 content. |
| `PAO-R36-AMV-III-002` | commendation | The record completeness gate is non-circular and does not silently exclude the declaration. | `R_gate` contains only pre-declaration records. Step 12 appends the declaration and creates `R_post = R_gate union {declaration}`; the verifier requires exactly one new member and `|R_post| = |R_gate| + 1`. |
| `PAO-R36-AMV-III-003` | commendation | Notification obligation is frozen at admission and the asynchronous escape is closed. | Per-member class, owner, evidence source, reconciliation source, cutoff, and P37 class freeze at Step 0; unknown/declared-only defaults synchronous; sync-to-async mutation is rejected. F05-B/C test both escape forms. |
| `PAO-R36-AMV-IV-001` | commendation | P37 is applied with exactly the registered five labels and a genuine falsify-the-declaration probe. | The one normative table uses only `recomputed`, `independently_reconciled`, `consumer_asserted`, `institutionally_supplied`, and `not_established`. F17 removes the live property while retaining green declarations and still goes red. |
| `PAO-R36-AMV-V-001` | commendation | Observer state, controlled generations, and receipts are bound to full semantic identity rather than labels alone. | Positive observer labels require the exact correction tuple; `S/C` bind source generations; every receipt binds correction, snapshot, generation, predicate, versions, notice, cutoff, and verifier provenance. |
| `PAO-R36-AMV-VI-001` | commendation | Formerly conditional falsifiers are split into deterministic single-world variants. | F03, F05, F06, F08, F11, F13 and related phase splits each state one world, one detector, one detector class, one exact verdict, and one forbidden green outcome. |
| `PAO-R36-AMV-VI-002` | commendation | F18 detects serialized stale-base loss even with one head at every instant. | C1 moves `v1` to `v2`; stale C2 still names `v1` and is rejected/readmitted. Retaining one-head and admission markers while removing the current-base property still makes the recomputed detector red. |
| `PAO-R36-AMV-VI-003` | commendation | F22 detects wrong, staged, and stale-currentness tuples despite a retained high-level label. | F22-A/B/C keep `successor_current_linked` markers while falsifying notice identity, notice phase, or latest snapshot selection; the independent full-tuple probe fails closed. |
| `PAO-R36-AMV-VII-001` | commendation | The amendment conforms to PV-K01, PV-K02, PV-K04, S0-K06, S0-K08, INT-K05, GY-N12, and terminal INT-R7 Section 18. | Currentness remains cutoff-bounded; history is append-only; projection cannot amplify; candidate/declared gate predicates fail closed; no second owner is created; key/currentness dimensions remain separate and read through the controlling terminal layer. |
| `PAO-R36-AMV-X-001` | commendation | Prohibitions and capability honesty survive amendment. | No source or workflow changes, implementation authorization, erasure, parallel owner, translation mechanism, recovery objective, expiry rule, legal sufficiency, vendor appointment, or claim that the repository can issue a correction. |

## 5. Orientation and arithmetic

The complete orientation evidence is in
[`pao-r36-amendment-verification-orientation-ledger.md`](pao-r36-amendment-verification-orientation-ledger.md).
The key reproduced facts are:

- amendment head is 8 commits ahead and 0 behind the audited head;
- the exact merge base is the audited head;
- all eight changed paths are Markdown files in the PAO-R36 research package;
- line counts are `509 / 480 / 698 / 258 / 180 / 190 / 82 / 167`;
- amendment total is `2,564` lines;
- audited total is `2,297` lines;
- `2,564 - 2,297 = +267`;
- remote additions/deletions are `2,164 / 1,897`; and
- `2,164 - 1,897 = +267`.

The equality of those independently derived deltas is a substantive commendation, not merely a
cosmetic number check.

## 6. The declined audit finding

### 6.1 What can be verified

The independent audit obtained 49 connector candidates for a case-insensitive `supersede` search,
identified two uppercase-only members, and subtracted them to obtain 47 lowercase files. The audit's
arithmetic on that returned set was coherent. It was not a valid P35 census because the returned set
was an index result rather than the complete source tree.

At documentation pin `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, P35 expressly states that an
index establishes neither absence nor a positive count and records the wave-4 omission: the connector
returned 49 candidates while the tree held 50 case-insensitive members. The two uppercase-only
subtractions remained correct; the starting set was one member short. Therefore the audit's
47/203/246 result is not supportable as a complete-tree correction and the amendment is justified in
declining that audit finding rather than adopting it.

### 6.2 What cannot be freshly certified here

The commission additionally requires this verifier to establish the complete set from the tree. The
available interface returned exact tree identities but not a complete content-bearing recursive tree
that could be walked without truncation; code search is index-backed; archive download was unavailable
through ordinary egress. Those are precisely the methods P35 says must not be used as denominators.

I therefore state the outcome without softening it:

- **the audit's 47-file census is not a valid complete census and should remain declined**;
- **the amendment's exact replacement 48/215/260 was not independently re-measured by this verifier**;
- the same execution limitation applies to the remaining supplied literal counts and settled zeroes;
- this is the sole material gap behind `CONFORMS_WITH_GAPS`.

A fresh retained `git grep` or complete tree/blob walker at the documentation pin would close the gap.

## 7. Audit blocker 1 — one controlling order

### 7.1 Byte-level table identity

The normative order table in the primary report and detailed contract was fetched directly from the
same amendment commit. From the opening `| Step | Preconditions | ... |` row through Step 13 and the
two-sentence ordering conclusion, the returned UTF-8 content is identical. There is no paraphrased
second order.

### 7.2 Required precedence

The controlling precedence is:

`Step 3 staged notice public and linked`

`< Step 9 authority fence proved over unchanged S/C generations`

`< Step 10 current-head append`

`< Step 11 controlled convergence probes`

`< Step 12 effective declaration`.

Step 3 expressly says it closes successor-current with no notice. Step 9 expressly says it closes
predecessor-current after the head change. Step 10 states that, because both already hold, a crash
immediately after authority append cannot produce either forbidden observation.

### 7.3 Crash probes

**Crash A: after Step 10 with no Step 11 execution.** The fence was already proven and remains the
precondition of the authority event. A controlled surface/cache may expose only the successor with
the exact linked notice, the predecessor as historical with the link, or fail closed. It cannot serve
predecessor-current.

**Crash B: after Step 10 before any notice phase follow-up.** The staged notice was already publicly
resolvable at Step 3 and its identity remains part of the full tuple. The successor cannot be current
without a notice. The phase changes by append chronology rather than by replacing the notice in
place.

The amendment fixes the order; it does not widen the observer model to admit a fourth state.

## 8. Audit blocker 2 — no circular record gate

`R_gate` is explicitly defined as the frozen pre-declaration record set. It contains the predecessor,
staged successor, notice, authority-transition event, notification-intent records, required
pre-effective status/evidence records, and any pre-effective incident records. It does not contain a
placeholder effective declaration.

The Step 12 precondition is `Complete(R_gate)` together with the other named sets and synchronous
receipts. The Step 12 effect appends exactly one effective-declaration event and defines:

`R_post = R_gate union {effective_declaration_event}`.

Independent verification requires:

- `R_gate` complete while no declaration exists;
- one successful append;
- exactly one new record in `R_post`;
- `|R_post| = |R_gate| + 1`; and
- the new member is the declaration bound to the same correction/snapshots.

Thus the declaration is not required before it exists. It is also not silently excluded after it
exists. The original circularity is closed.

## 9. Audit blocker 3 — notification obligation frozen at admission

For each `N/P` member, Step 0 freezes:

- receipt obligation class;
- accountable owner;
- evidence source;
- independent reconciliation source;
- cutoff;
- exact P37 provenance class; and
- snapshot identity/generation.

The permitted obligation classes are `intent_before_authority`,
`qualifying_receipt_before_effect`, and `asynchronous_receipt_permitted`. A missing, disputed,
consumer-asserted, merely institutionally supplied, or not independently reconciled decision does
not default asynchronous. It defaults to `qualifying_receipt_before_effect` and keeps the gate red.

F05-B supplies a frozen synchronous member with no qualifying receipt and attempts effect. Its exact
verdict is `NO_EFFECTIVE + RED(notification_receipt) + REJECT_EVENT(e_effective)`.

F05-C attempts to change the same member from synchronous to asynchronous after admission while
leaving the original classification marker in place. Its exact verdict is
`REJECT_CLASS_CHANGE(sub_3) + NO_EFFECTIVE + RED(notification_obligation_integrity)`.

The async escape is closed by procedure, not merely prohibited in prose.

## 10. P37 conformance

### 10.1 Registered vocabulary

P37 at the documentation pin defines exactly five provenance labels:

1. `recomputed`;
2. `independently_reconciled`;
3. `consumer_asserted`;
4. `institutionally_supplied`; and
5. `not_established`.

The amendment's normative provenance table uses exactly those five values. No sixth local synonym is
introduced. The classification is frozen at Step 0.

The table covers:

- every `Complete(X)` predicate;
- each observer-model label;
- every Step 0-13 precondition/effect gate; and
- the falsifier detectors as one class.

A decisive predicate classified as `consumer_asserted`, `institutionally_supplied`, or
`not_established` cannot produce a positive gate; it blocks or degrades the claim.

### 10.2 Falsify-the-declaration probe

F17 leaves declarations, marker fields, snapshots, and producer receipts saying green but changes the
live `public_export` behavior to predecessor-current. The detector re-probes the live controlled
surface and is frozen as `independently_reconciled`. The exact verdict is:

`FAIL_CLOSED(public_export) + NO_EFFECTIVE + RED(declared_gate_predicate) + REJECT_AGGREGATE`.

The fixture removes the property while keeping the declaration. It therefore tests the predicate,
not the presence of its claim.

## 11. Observer tuple, event order, generations, and receipts

### 11.1 Full observer tuple

A surface state is evaluated over a tuple containing at least correction identity, predecessor and
successor identity, authority posture, exact notice identity and phase, authenticated `as_of`,
projection relation, authoritative-language result, and effective relation. The three high-level
labels are projections of a conforming tuple, not independent marker values.

Consequences:

- the right successor with the wrong notice fails;
- the right successor with a staged notice after authority fails;
- an authentic but non-latest currentness snapshot fails a current positive; and
- one language widening permission fails the tuple.

### 11.2 Append order and anti-backdating

The append sequence is strict:

`seq(e_stage) < seq(e_authority) < seq(e_effective)`.

Display timestamps do not override append order. Evidence cutoffs must not follow the effective event.
Equal displayed timestamps are accepted only where append sequence remains distinct and correctly
ordered. F20-A/B/C respectively reject early effect, backdated display, and equal-time/reversed event
order.

### 11.3 Controlled generations

`S` and `C` snapshots bind the exact live registry/config generation active at admission. If the
controlled generation changes before effect, the old denominator cannot remain green: the transaction
must restart or extend and re-probe. A new controlled member cannot be relabeled an external
exclusion. F21 removes the property while preserving the old member list and markers; the live
generation mismatch still makes the gate red.

### 11.4 Receipt binding

Every member receipt binds:

`(correction_id, set_id, snapshot_id, source_generation, member_id, required_predicate_id,
predecessor_id, successor_id, notice_id, as_of_cutoff, evidence_cutoff, verifier_identity,
verifier_provenance, outcome)`.

F19 offers a complete valid receipt family from C1 to C2 with identical member names and counts. The
exact mismatch on correction/snapshot/version/notice binding rejects the receipts and effective event.

## 12. Deterministic falsifier conformance

The suite defines one exact terminal conjunction per world. The formerly ambiguous cases are split:

- F03-A through F03-D separate byte mutation, semantic mutation, missing successor, and post-authority
  discovery;
- F05-A through F05-C separate permitted asynchronous delivery failure, missing synchronous receipt,
  and attempted class downgrade;
- F06-A/B name the precise phase/member outcome;
- F08-A/B separate pre-append fork and post-authority equivocation;
- F11-A/B/C separate restored old head, missing notice, and missing completion evidence;
- F13-A/B separate historical and current `as_of` inversion; and
- F01, F07, and F15 are likewise split by phase where required.

Each inspected variant contains:

- one `World`;
- one `Attack`;
- one named `Detector`;
- one frozen `Detector class`;
- one `Exact expected verdict`; and
- one `Forbidden green outcome`.

### 12.1 F18 — serialized stale-base correction

World: C1 admits `v1 -> v2`; C2 admits stale `v1 -> v3`; C1 transitions first; there is exactly one
head at every instant. The attack preserves C2's earlier admission markers and attempts a last-writer
append.

Detector: recompute the canonical head immediately before C2's append and compare it with C2's bound
base. Exact verdict:

`BLOCK_AUTHORITY + READMIT_REQUIRED(C2,v2) + RED(correction_base_head)`.

Forbidden outcome: C2 appends `v3` directly from `v1` merely because no simultaneous fork exists.

**Remove-property/keep-markers probe:** retain C2's valid-looking admission, one-head marker, and
predecessor field, but change the live current head to `v2`. The recomputed base-head property is
false; the detector still goes red. F18 is behavioral rather than marker-based.

### 12.2 F19 — cross-correction receipt replay

World: C1 and C2 have the same member labels/counts but different correction, snapshot, versions,
notice, and cutoff. Attack: offer C1's complete receipts to C2. Exact binding comparison rejects the
family and effect. No missing-row detector is needed.

### 12.3 F20 — event ordering and backdating

- F20-A appends effect before the final member receipt and rejects the event.
- F20-B appends later but presents an earlier effective time and rejects the event.
- F20-C uses equal display timestamps with reversed append sequence and rejects the event.

Each preserves F13 as a separate version-selection attack.

### 12.4 F21 — controlled-generation drift

World: a new controlled route/cache variant becomes active after snapshot. Attack: preserve the old
snapshot and aggregate. Exact generation comparison requires restart/re-probe and rejects effect.

### 12.5 F22 — full-tuple attacks

- F22-A: right successor, wrong notice identity;
- F22-B: right successor, notice still staged after authority; and
- F22-C: authentic supplied snapshot is not latest-established-under-policy.

Each has one named surface member and one exact fail-closed verdict.

**Remove-property/keep-markers probe:** retain `successor_current_linked`, current, and green
projection markers, but replace the notice identity/phase or latest-snapshot property. The independent
full-tuple detector rejects the state. F22 does not trust the high-level label it is testing.

## 13. Ratified-kernel conformance

### 13.1 `PV-K01`

Current authority remains a separately reportable proposition evaluated at an authenticated `as_of`.
The full observer tuple and F13/F20 prevent a supplied historical snapshot or display timestamp from
becoming a current positive.

### 13.2 `PV-K02` and `S0-K08`

The predecessor remains byte/identity-preserved and historically reportable. Correction, notice,
authority, effective declaration, attempted obligation mutation, and later incidents are append-only
events. No repair rewrites historical authenticity or restores predecessor-current.

The prohibition is detectable through F02, F03, F07, F09, F11, F13, F18, and the `R_post` count rule.

### 13.3 `PV-K04`

A positive observer state requires the exact notice and projection relation. A notice that drops a
limitation, denied use, risk direction, old-version significance, dissent, or recourse is rejected or
fails closed. Accessibility changes do not create substantive recourse, and translation parity
remains an INT-R6 interface rather than a local mechanism.

### 13.4 `S0-K06` and P37

An authority-grade effective gate cannot be carried by a consumer assertion, merely supplied
institutional premise, or unknown. Those values fail closed or degrade. This is the gate-predicate
application of the ratified authority-band rule and is exercised by F05, F10, F17, and F23.

### 13.5 `INT-K05`, P27/P28, and GY-N12

The amendment extends/consumes the existing `rule_evolution.py`, `projection_semantics.py`, public
export, and planned GY-N12 owners. It creates no second correction chronology, currentness service,
or parent ledger. GY-N12 remains contract-only/undelivered and no amendment text claims otherwise.

### 13.6 Terminal INT-R7 Section 18

Final key/currentness outcomes read through the terminal controlling layer at
`int-r7/public-verification-profile.md:620-760`. Issuer issuance, projection faithfulness, public
history, durable verification, and current authority remain separate. Latest-snapshot selection is
required for a current positive; historical authenticity is not erased by later revocation or present
evidence failure.

## 14. Audit closure matrix

| Audit requirement | Verification disposition |
| --- | --- |
| R1 one order and two named forbidden observations | **closed** |
| R2 non-circular `R_gate` / explicit `R_post +1` | **closed** |
| R3 frozen synchronous notification predicate | **closed** |
| R4 full observer tuple | **closed** |
| R5 event order and anti-backdating | **closed** |
| R6 controlled registry/config generation | **closed** |
| R7 deterministic single-world falsifiers | **closed** |
| R8 serialized stale-base attack | **closed** |
| R9 exact correction-bound receipts | **closed** |
| R10 census and zero claims | **gap: amendment records the supplied result; fresh independent complete walk not executable here** |
| R11 terminal INT-R7 citation | **closed** |
| R12 accessibility transfer narrowing | **closed** |
| R13 Regulation No 1 transfer narrowing | **closed** |
| R14 COPE edition/date pin | **closed** |

The three original blocking findings are closed. No new blocking conflict with a ratified kernel was
found.

## 15. Prohibitions and capability honesty

The amendment modifies documentation only. It does not:

- authorize implementation;
- define a final schema, media type, endpoint, package, service, database, or serialization;
- erase or edit a published predecessor;
- appoint a signer, vendor, archive, service, or publication-of-record venue;
- create a parallel evolution or currentness owner;
- define INT-R6 translation-parity mechanics;
- set OPS-R14 recovery objectives, retention, expiry, or disaster behavior;
- declare any notification legally sufficient;
- open a publication or first-public-record gate; or
- claim the repository presently issues public corrections.

The settled-source-zero capability conclusion in the amendment is not independently re-censused by
this verifier, but the capability labels themselves remain prerequisite-correct: the absent
correction chains are not mislabeled `producer_missing`, `bridge_missing`, or
`verification_missing`.

## 16. Final disposition and stop condition

The amended contract is internally coherent, closes the hostile audit's three blockers, preserves the
confirmed architecture, and conforms to the ratified kernels inspected. The result is not
`CONFORMS` only because the commission required a fresh independent complete source census and the
available execution path could not produce one without violating P35.

**Final verdict: `CONFORMS_WITH_GAPS`; blocking findings: 0; material gaps: 1.**

No requested semantic, falsifier, P37, arithmetic, standing, or kernel pass was left unexamined. The
only unreached execution is the complete source-blob literal walk described in
`PAO-R36-AMV-I-001`; the report states the exact command/evidence that would settle it.
