---
title: PAO-R36 - Public Correction Falsifier Suite
research_id: PAO-R36
status: delivered_research
result_standing: accepted_narrow_scope
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
research_only: true
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog, or system-design decision
---

# Public correction falsifier suite

## 1. Purpose and execution rule

This is an executable semantic specification: each fixture defines initial governed facts, one
adversarial change, the observation oracle, and an exact required outcome. A future implementation
passes only by exercising the real correction path and producing the stated behavior. Marker strings,
field presence, a hand-authored green receipt, or a test-only shortcut do not pass. This applies P29,
P31, P33, P35, and P36 from
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-80`.

The suite uses these exact outcomes:

- `BLOCK_AUTHORITY`: no `t_authority` event may be appended;
- `NO_EFFECTIVE`: no `t_effective` declaration may be issued;
- `FAIL_CLOSED(member)`: the named controlled member may not return a current-authority positive;
- `RED(gate)`: the named gate must be visibly non-green with an owned reason;
- `APPEND_INCIDENT`: preserve the correction and append evidence of the later failure; never rewrite;
- `REJECT_TRANSACTION`: the proposed correction object is inadmissible; and
- `PASS`: the specified safe behavior is observed over the complete frozen denominator.

A failure discovered before `t_authority` normally requires `BLOCK_AUTHORITY`. A failure discovered
after `t_authority` cannot be repaired by restoring the predecessor as current; it requires
`NO_EFFECTIVE`, `FAIL_CLOSED`, `RED`, and `APPEND_INCIDENT` as applicable.

## 2. Common fixture

Unless a test overrides a value, use:

- predecessor `v1`, successor `v2`, notice `n2`;
- `S = {public_page, public_export, api_current, api_versioned, machine_projection}` with denominator 5;
- `C = {page_edge, export_edge, api_edge, origin_object_cache}` with denominator 4;
- `F = {public_correction_stream, machine_history_stream}` with denominator 2;
- `A = {primary_archive, public_evidence_archive}` with denominator 2;
- `L = {uk, en}` with denominator 2;
- `N = {sub_1, sub_2, sub_3}` with denominator 3;
- no uncontrolled copy is included in a controlled denominator; and
- every completion assertion must name the exact snapshot identity and count.

These names are fixtures, not endpoint, package, service, or schema decisions.

## 3. Commission-required falsifiers

### F01 - authoritative language versions diverge

**Given.** `uk` and `en` are linked to one correction semantic identity. The canonical successor says
that a benefit is unavailable after the cutoff and retains an appeal route.

**Attack.** The English notice omits the appeal route or says the benefit remains available.

**Oracle.** Compare protected queries for claim type, scope, currentness, denied use, limitation,
adverse effect, and recourse across every member of `L`.

**Expected before `t_authority`.** `BLOCK_AUTHORITY`; `RED(translation_parity)`; no language may say
effective.

**Expected after `t_authority`.** `FAIL_CLOSED(en)`; `NO_EFFECTIVE`; `RED(translation_parity)`;
`APPEND_INCIDENT`. Ukrainian may remain available only if it does not imply parity completeness.

**Exact pass condition.** All 2/2 language members answer every protected query equivalently or more
conservatively under the INT-R6 interface.

### F02 - a superseded record renders as current on a controlled surface

**Given.** `v2` became the GY-N12 current head at `t_authority`; `v1` remains historical.

**Attack.** `api_current` or `public_page` returns `v1` with an unqualified current/authoritative
presentation.

**Oracle.** Query every 5/5 member of `S` at a cutoff after `t_authority` and inspect resolved version,
currentness, notice relation, and `as_of`.

**Expected.** `FAIL_CLOSED(attacked_member)`; `NO_EFFECTIVE`; `RED(surface_convergence)`;
`APPEND_INCIDENT`. The system must not rewrite the GY-N12 head back to `v1`.

**Exact pass condition.** Every 5/5 surface returns `v2` current with links, `v1` historical with
links, or unavailable; zero members return `v1` current.

### F03 - correction silently rewrites instead of superseding

**Given.** `v1` is a signed published record with stable content identity.

**Attack.** The correction changes bytes or semantic content at the `v1` identity, or replaces `v1`
without a distinct `v2` and predecessor relation.

**Oracle.** Compare the archived and canonical `v1` identity/content before and after correction;
traverse predecessor/successor relations.

**Expected.** `REJECT_TRANSACTION`; `BLOCK_AUTHORITY`; `RED(history_integrity)`. If detected after a
claim, `APPEND_INCIDENT` and fail affected surfaces closed. Never normalize the mutation as a valid
correction.

**Exact pass condition.** `v1` is byte/semantic-identity stable, `v2` is distinct, and both directions
of the correction relation resolve.

### F04 - a controlled cache serves the old version after effective is declared

**Given.** An effective declaration names `C` denominator 4 and `S` denominator 5.

**Attack.** `page_edge` serves `v1` as current after `t_effective`.

**Oracle.** Probe all 4/4 cache members and the corresponding surface, bypassing no registered variant.

**Expected.** The continuing safe-state claim for `C`/`S` becomes false; the historical receipt at
`t_effective` remains append-only. `FAIL_CLOSED(page_edge)`; `RED(cache_convergence)`;
`APPEND_INCIDENT`. The canonical correction remains appended/current. A best-effort warning is not
enough.

**Exact pass condition.** Zero controlled cache members can serve `v1` as current after
`t_authority`; all 4/4 have member-bound evidence.

### F05 - a subscriber is never notified and no gate goes red

**Given.** `N` contains `sub_1`, `sub_2`, and `sub_3`; delivery may lag after effect.

**Attack.** `sub_3` has no delivery receipt, no visible retry/escalation state, and aggregate status
remains green or says all notified.

**Oracle.** Recompute notification status directly from every 3/3 cohort member.

**Expected.** Test fails. `RED(notification_delivery)` is mandatory. The aggregate must say 2/3
qualifying deliveries, not complete. If an affected-party pre-effect rule applied to `sub_3`, also
`NO_EFFECTIVE`.

**Exact pass condition.** Every cohort member has a delivered receipt or a visible owned non-green
state; "all notified" is permitted only for 3/3 qualifying delivery receipts.

### F06 - the notice drops a retained limitation

**Given.** The successor remains subject to a geographic limit and a denied use for individual
eligibility decisions.

**Attack.** The notice summarizes the numerical correction but omits one of those constraints.

**Oracle.** Run PV-K04 protected-query comparison from canonical successor to notice.

**Expected before `t_authority`.** `REJECT_TRANSACTION`; `BLOCK_AUTHORITY`;
`RED(notice_semantic_parity)`.

**Expected after `t_authority`.** `FAIL_CLOSED` for surfaces using the defective notice;
`NO_EFFECTIVE`; `APPEND_INCIDENT` and append a corrected notice. Do not edit the defective notice in
place.

**Exact pass condition.** Every retained limitation and denied use is visible or source-resolvable
with a governed omission effect, and no protected answer is widened.

### F07 - an archived copy loses its supersession link

**Given.** Both members of `A` preserve `v1`, `n2`, and `v2`.

**Attack.** `public_evidence_archive` preserves all three byte objects but cannot traverse `v1 -> n2
-> v2`, or the reverse relation.

**Oracle.** Execute round-trip relation traversal and content identity checks at both 2/2 archive
members.

**Expected before `t_authority`.** `BLOCK_AUTHORITY`; `RED(archive_linkage)`.

**Expected after `t_authority`.** `NO_EFFECTIVE`; `RED(archive_linkage)`; `APPEND_INCIDENT`; fail an
authority-bearing archive view closed. Preservation of disconnected bytes does not pass.

**Exact pass condition.** Both 2/2 archives preserve identities and bidirectional correction
relations.

## 4. Additional adversarial falsifiers

### F08 - forked successors create two current heads

**Given.** Two correction attempts `v2a` and `v2b` both cite `v1`.

**Attack.** Different controlled surfaces treat different successors as current at the same `as_of`
cutoff.

**Oracle.** Recompute the GY-N12 head and query all `S` members at one authenticated cutoff.

**Expected.** `BLOCK_AUTHORITY` if pre-append; otherwise `FAIL_CLOSED(S)`;
`NO_EFFECTIVE`; `RED(single_current_head)`; `APPEND_INCIDENT`. No last-writer rule may silently choose.

**Exact pass condition.** Exactly one current successor exists at the cutoff; any competing candidate
is non-current with an explicit disposition.

### F09 - revoked-key laundering

**Given.** `v1` was signed by `K_old`, later revoked; `v2` is signed by `K_new`.

**Attack A.** A verifier says revocation proves `v1` was never authentic.

**Attack B.** A verifier says a valid historical `K_old` signature proves `v1` remains current.

**Oracle.** Evaluate issuance-time authorization, current key status, GY-N12 currentness, and
compromise interval separately under INT-R7.

**Expected.** Both attacks fail. `RED(verification_semantics)` and no current positive from the
collapsed proposition. Historical outcome is valid, invalid, or indeterminate only from issuance-time
evidence; current authority is separately false after supersession.

**Exact pass condition.** The four propositions - content match, issuance authorization,
compromise certainty, current authority - are separately reported and no one substitutes for another.

### F10 - adverse correction is disguised as neutral maintenance

**Given.** `v2` reduces eligibility or increases an enforcement burden for a known class.

**Attack.** The transaction labels the change typographical/administrative, does not create a risk
classification, and uses the ordinary lagging-notification path.

**Oracle.** Compare predecessor and successor effects on protected groups/obligations and inspect the
institutional risk/affected-party decision.

**Expected.** `BLOCK_AUTHORITY`; `RED(risk_direction)` and `RED(affected_party_decision)`. Unknown is
not neutral.

**Exact pass condition.** Risk direction is explicit, adverse classes are named at a safe level, and
the authorized direct-notice/pre-effect rule is present before transition.

### F11 - recovery un-corrects the record

**Given.** `v2` is current and effective; `v1` is historical.

**Attack.** A restore, replay, failover, or disaster process reconstructs a state in which `v1` is
current, `n2` is missing, or the later GY-N12 event is absent.

**Oracle.** Compare restored append order, current head, notice linkage, and surface-safe states with
the pre-recovery history.

**Expected.** No authority-positive service may resume. `FAIL_CLOSED(S)`;
`RED(ops_r14_recovery_invariant)`; `APPEND_INCIDENT`. Recovery must never be accepted by deleting or
rewriting `v2`.

**Exact pass condition.** Restored state preserves all later events and cannot return an earlier head
as current. Mechanics belong to OPS-R14.

### F12 - mutable subscriber denominator hides a missed recipient

**Given.** `N` is frozen at cutoff with denominator 3.

**Attack.** After `sub_3` fails delivery, the live registry changes and completion is recomputed over
`{sub_1, sub_2}`, yielding 2/2 green.

**Oracle.** Resolve the frozen cohort snapshot named by the correction, not the live registry.

**Expected.** `RED(notification_cohort_integrity)`; aggregate remains incomplete against denominator
3; deletion from the live registry cannot rewrite history.

**Exact pass condition.** Completion uses the exact frozen cohort and reports later eligibility
changes separately.

### F13 - `as_of` inversion makes the correction retroactive by presentation

**Given.** `v1` was current through `t_authority - 1`; `v2` becomes current at `t_authority`.

**Attack.** A historical query before `t_authority` returns `v2` as if it had been current then, or a
current query after `t_authority` returns `v1`.

**Oracle.** Query exact versions and current-at-cutoff for times immediately before and after the
transition.

**Expected.** `RED(temporal_semantics)`; affected surface fails closed; no effective completeness.

**Exact pass condition.** Historical queries reproduce `v1` for its interval and current queries
select `v2` only from the actual transition cutoff onward.

### F14 - unenumerated external copy is counted as cleared

**Given.** Controlled sets are complete, but a third-party mirror outside PolicyOS control still
shows `v1` without notice.

**Attack.** The effective notice says all copies, all caches, or the internet have been corrected.

**Oracle.** Compare the completion assertion with named `S`, `C`, and exclusion records.

**Expected.** `REJECT_TRANSACTION` for the amplified notice; `RED(completeness_scope)`. The controlled
correction may still be effective if its bounded claims are true, but the universal statement is
false.

**Exact pass condition.** The notice names controlled denominators and explicitly excludes unknown
external copies.

### F15 - notice is reachable but successor is not

**Given.** `n2` is published and says `v2` is current.

**Attack.** A controlled surface can resolve the notice but cannot retrieve or verify `v2`.

**Oracle.** Traverse notice -> successor on all `S`, `F`, and `A` members that expose the notice.

**Expected before `t_authority`.** `BLOCK_AUTHORITY`.

**Expected after `t_authority`.** `FAIL_CLOSED(attacked_members)`; `NO_EFFECTIVE`;
`RED(referential_integrity)`; `APPEND_INCIDENT`.

**Exact pass condition.** Every current notice has a resolvable, identity-bound successor and
predecessor relation wherever that notice is authority-bearing.

### F16 - a self-attested completion receipt survives member deletion

**Given.** An effective declaration says `C` is complete at denominator 4.

**Attack.** Remove one member result while preserving the aggregate count/green markers.

**Oracle.** Independently join the frozen `C` membership to member-bound evidence.

**Expected.** Completion recomputation fails; `RED(completeness_evidence)`; no effective declaration.

**Exact pass condition.** Removing any one of 4/4 member results makes the gate fail even when all
aggregate marker strings remain.

## 5. Current-state negative comparator for every fixture

The pinned repository has internal supersession primitives, an unsigned public-export producer with
no production HTTP bridge, four-audience projection machinery, and delivered research semantics for
INT-R7. It has no admitted public correction notice, notification chain, correction feed, controlled
correction cache set, archive correction relation, or translation-parity mechanism. The table below
states what a public observer can see today if each attack occurs.

| ID | Pinned current-state observer outcome | Existing red gate? |
| --- | --- | --- |
| F01 | The observer may receive divergent language text or no correction at all; no language-invariant correction identity is exposed. | No correction-parity gate established. |
| F02 | An internal supersession can exist while an outward surface continues presenting the old export/current view. | No end-to-end correction surface gate established. |
| F03 | The ratified prohibition exists, but a public observer has no correction chain proving that an outward change was append-only rather than an edit. | No public-chain rewrite detector established. |
| F04 | A controlled cache can serve stale content; the repository has generic cache invalidation occurrences but no correction-scoped enumerated invalidation receipt. | No correction effective/cache gate established. |
| F05 | There is no correction subscriber cohort or notification producer/consumer chain; a subscriber receives nothing. | No correction notification gate exists to turn red. |
| F06 | There is no public correction notice contract against which retained limitations can be compared. | No notice-parity correction gate established. |
| F07 | The observer cannot traverse a correction relation in a named public archive because no correction-specific archive fan-out exists. | No archive-linkage correction gate established. |
| F08 | GY-N12 specifies one chronology but is contract-only/undelivered; outward surfaces have no complete head-convergence proof. | No delivered correction single-head gate. |
| F09 | INT-R7 research can describe the correct outcome, but the public export is not a production signed correction proof. | No production public correction verification chain. |
| F10 | No correction risk-direction or affected-party classification is exposed. | No adverse-correction gate. |
| F11 | OPS-R14 is parallel research; the current repository cannot prove that restore preserves a correction chain that does not yet exist. | No wired cross-seam recovery invariant. |
| F12 | No frozen correction subscriber cohort exists, so a mutable live denominator can neither be detected nor honestly reported. | No cohort-integrity gate. |
| F13 | Currentness semantics are owned in GY-N12 but no production correction `as_of` fan-out is established. | No correction temporal-convergence gate. |
| F14 | No enumerated correction completion assertion exists; a broad claim would be unsupported rather than falsifiably bounded. | No completion-scope gate. |
| F15 | `public_export.py` has a producer but no production HTTP bridge, and there is no correction notice/successor traversal chain. | No correction referential-integrity gate. |
| F16 | There is no wired correction completion receipt to recompute; marker-presence validation would prove nothing. | No correction completion-evidence gate. |

The exact expected current-state result for all sixteen fixtures is therefore **no capability claim**.
The repository cannot currently issue or prove a public correction fan-out.

## 6. Graduation rule

A future chain may be called verified only when:

1. every fixture runs against the real producer, persisted event/artifact, bridge, consumer, visible
   surface, and enumerated set;
2. each mandatory negative changes the named gate exactly as specified;
3. the remove-property/keep-markers variants fail;
4. the test denominator is derived from the same live registry snapshot used by the correction; and
5. current-state absences are no longer mislabeled as `verification_missing` before the chain is
   actually wired.

## 7. `may_not_use_for`

This suite may not be used for production implementation authorization; a final wire, schema,
package, database, serialization, media-type, or API contract; canonical owner, vendor, or service
appointment; an authority grant; a capability claim; legal sufficiency or a jurisdictional
conclusion; permission to publish or open a gate; or automatic amendment of any plan, backlog, or
system-design decision.
