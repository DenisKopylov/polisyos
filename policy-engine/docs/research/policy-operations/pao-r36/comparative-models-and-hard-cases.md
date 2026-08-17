---
title: PAO-R36 - Comparative Models, Selection, and Hard Cases
research_id: PAO-R36
status: amended_research
result_standing: accepted_narrow_scope
audit_disposition_of_submitted_version: NO_GO
amendment_status: pending_independent_conformance
audited_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
audit_commit: 9bbfd37a218222ae06c1f669b95dba37c4732765
pinned_repository_commit: 109ba3f4
amendment_branch: research/pao-r36-amendment
research_only: true
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, archive, signer, publication-of-record venue, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - translation-parity mechanism design
  - recovery objective, retention period, expiry rule, or disaster-mode design
  - automatic amendment of any plan, backlog, or system-design decision
---

# Comparative models, selection, and hard cases

## 1. Selection result

No single comparator supplies the complete correction fan-out. The selected design remains a
composite:

- append-only predecessor/successor identity as the semantic backbone;
- explicit version and authenticated `as_of` retrieval for historically bounded use;
- a separate durable reasons-bearing correction notice carried by every admitted authority-bearing
  public path, without appointing a publication-of-record venue;
- statistical revision-policy disciplines for correction/revision classification, published policy,
  vintages, schedules, and revision analysis;
- official-gazette conventions for durable citation and linked correction/replacement notices;
- admitted push notification plus public/machine pull replay;
- independently verified convergence over frozen, generation-bound controlled surfaces/caches;
- archive relationships preserving original, successor, notice, and correction context; and
- a language-invariant semantic identity and parity result requested from INT-R6.

The independent audit confirmed the architecture. The amendment changes the order and decisive gate
construction, not the selected model: the staged notice and behaviorally proved authority fence now
precede the current-head event; `R_gate` precedes and `R_post` follows the effective event; and each
member's receipt obligation is frozen at admission.

## 2. Model comparison

| Candidate model | What it contributes | Why it is insufficient alone | Selected disposition |
| --- | --- | --- | --- |
| Internal append-only evolution | Immutable predecessor/successor relation and replayable history. | No outward notice, controlled denominator, machine feed, direct notification, or convergence proof. | Semantic backbone under the existing evolution owner. |
| Versioned resource plus `as_of` | Exact historical/current retrieval and temporal non-retroactivity. | Pull-only; does not notify known cohorts or prove all controlled paths safe. | Required retrieval layer under GY-N12 currentness. |
| Separate erratum/correction notice | Reasons, changed proposition, citation, public observability. | Can coexist with predecessor-current or an unreachable/wrong successor. | Required, tuple-bound notice; staged and public before authority. |
| Statistical revision policy | Classification, published policy, vintages, schedules, revision quality analysis. | Does not establish signer authority, administrative effect, affected-party receipt, archive custody, or currentness. | Bounded procedural analogue. |
| Official-gazette correction/replacement | Durable citation, linked notice, preserved earlier publication, dates/reasons/objection information. | Does not update APIs, caches, machine consumers, subscriber cohorts, or language parity. | Notice/linkage convention only; no venue appointment. |
| Push notification | Direct dissemination to known subscribers/affected parties. | Excludes unregistered observers and does not create public replay/currentness. | Required for admitted cohorts; obligation class frozen at admission. |
| Pull correction feed | Discoverable replay for public and machine observers. | Leaves known affected parties with discovery burden and does not prove cache/surface convergence. | Required controlled machine/public observation set. |
| Best-effort cache invalidation | Operational propagation mechanism. | Acknowledgement can be green while a variant still serves predecessor-current. | Accepted only with frozen generation and read-after-invalidate evidence. |
| Archive/tombstone/retraction | Preserved status notice and conspicuous linkage. | Retraction collapses correction, withdrawal, historical use, and current authority; tombstone can erase context. | Retained-notice analogy only; rejected as governing model. |
| Global physical atomicity | Simple conceptual switch. | Unrealistic across independent systems and unnecessary for safety. | Rejected; use a pre-armed semantic fence and safe mixed states. |
| Unbounded eventual consistency | Operationally easy. | Permits predecessor-current or successor-current-without-notice after authority changes. | Rejected; physical lag is allowed only behind the three-state full-tuple invariant. |

## 3. Why the amended composition is necessary

The two boundaries solve different questions:

- `t_authority` answers which canonical record is current; and
- `t_effective` answers whether the bounded synchronous fan-out has been independently verified.

The amendment closes the two forbidden windows without demanding physical atomicity:

1. the staged notice is already public, exact, and non-current before the head changes; and
2. the authority fence is already proved over every admitted controlled path before the head changes.

A crash immediately after `t_authority` therefore yields only:

- the successor as current with the admitted notice and predecessor relation;
- the predecessor as historical with the admitted successor/notice relation; or
- fail-closed unavailability.

A wrong notice, staged notice, stale currentness snapshot, unfaithful projection, or divergent
language result satisfies neither positive state and fails closed. The model does not add a fourth
state to paper over bad ordering.

## 4. Hard case A — correction increases risk or exposure

### 4.1 Fixture

PolicyOS published and signed a fictional eligibility record stating that relief applied up to
50,000 units. The admitted source should have stated 25,000. The correction excludes a class that
appeared eligible and may increase repayment, enforcement, planning, or appeal exposure.

The numbers are fictional; the fixture tests direction of harm.

### 4.2 Decidable protocol disposition

Before the transaction can append a successor:

1. Step 0 freezes the affected-set decision, every admitted member, each member's receipt obligation,
   predicate-provenance class, owner, source, independent reconciliation source, and cutoff.
2. Step 1 independently reconciles risk direction. A producer declaration of “typographical,”
   “administrative,” or “neutral” is not decisive.
3. Missing, conflicting, consumer-asserted, merely institutionally supplied, or not-established
   receipt-obligation evidence defaults to `qualifying_receipt_before_effect`.
4. The predecessor remains historically authentic and retrievable with its publication interval.
5. The successor is distinct and carries the changed threshold, basis, scope, limitations, and denied
   uses.
6. The staged notice names the affected class and likely adverse direction without exposing protected
   personal information. It preserves uncertainty, limitations, deadlines, and any independently
   grounded recourse.
7. The authority fence and notice are in place before the head changes.
8. `e_effective` is rejected while any synchronous member lacks a qualifying bound receipt.

An attempted in-transaction movement from synchronous to asynchronous is rejected and recorded. A
later competent institutional decision can govern a new admission; it cannot retroactively create the
prior pass.

### 4.3 What remains institutional/legal

PAO-R36 does not decide:

- whether a real hearing, direct notice, actual receipt, interim protection, or remedy is legally
  required;
- whether the correction has prospective or retroactive legal effect;
- whether reliance creates liability, estoppel, reopening, or grandfathering; or
- whether the final notice is legally sufficient.

It only prevents an admitted institutional predicate from remaining mutable or self-supplied inside
the gate.

### 4.4 Halfway failure

Given `sub_3` frozen as `qualifying_receipt_before_effect`, no qualifying receipt, and an attempted
class downgrade after `t_authority`, the exact result is:

`REJECT_OBLIGATION_CHANGE + APPEND_ATTEMPTED_CHANGE + REJECT_EFFECTIVE_APPEND + NO_EFFECTIVE + RED(notification_obligation_integrity)`.

The canonical successor remains current behind the safe observer invariant. The obligation does not
change.

## 5. Hard case B — superseded version remains legally or administratively significant

### 5.1 Fixture

PolicyOS published and signed a procurement-evaluation record `v1`. Contracting decisions were taken
while `v1` was current. PolicyOS later discovers an error and admits corrected version `v2`.

### 5.2 Decidable protocol disposition

1. Preserve `v1`, signature/proof closure, publication interval, reasons, limitations, and authority
   evidence.
2. Bind each prior decision to the exact version and authenticated `as_of` it used.
3. Append a distinct `v2` on the still-current admitted base; a stale-base second correction must
   re-admit rather than silently replace an intervening correction.
4. Publish the staged notice and prove the fence before `v2` becomes current.
5. Current default retrieval selects `v2` only from `e_authority` onward.
6. Historical retrieval before `e_authority` reproduces `v1` and its relation to `n2`/`v2`.
7. Every claimed archive preserves identities and bidirectional links; disconnected bytes do not
   satisfy archive completeness.
8. Any later institutional decision on reconsideration, grandfathering, appeal, remedy, or no change
   is another append-only record linked to the exact affected decisions.

### 5.3 Forbidden implications

The notice and feed must not imply that:

- `v1` was never authentic;
- every decision under `v1` is invalid;
- `v2` applied to an event before `e_authority` merely because it is current now; or
- the correction itself supplies a remedy or legal conclusion.

### 5.4 Halfway failure

If `public_page` shows `v2` but `api_versioned` cannot reproduce `v1`, historical retrieval is red.
If an archive preserves all bytes but loses `v1 -> n2 -> v2` or the reverse link, archive linkage is
red. Neither failure is repaired by deleting `v1` or restoring it as current.

## 6. Hard case C — correction after revocation of the original signing key

### 6.1 Fixture

The predecessor was signed with `K_old`. The credential was later retired, revoked, or compromised.
The correction is issued using currently authorized `K_new`.

### 6.2 Controlling INT-R7 consumption

The final semantics are read through terminal controlling Section 18 at
`policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:620-760`.
PAO-R36 consumes five separately reportable dimensions:

1. `IssuerIssuanceAuthentic`;
2. `ProjectionFaithful`;
3. `PublicHistoryEstablished`;
4. `DurablyVerifiableAt(t_v)`; and
5. `CurrentAuthorityAsOf(t_q)`.

Snapshot selection and evidence obtainability also remain distinct. Earlier examples at
`:250-405` are historical detail under the terminal amendment.

### 6.3 Required correction disposition

1. Preserve original bytes, original signature, trusted-time evidence, key-status events, compromise
   interval evidence, and applicable snapshot-selection evidence.
2. Evaluate `K_old` at the supported issuance interval, not solely at current query time.
3. Never infer historical issuance contradiction from later revocation alone.
4. Never infer current authority from historical signature validity.
5. Keep compromise uncertainty non-positive for the affected dimension.
6. Bind `K_new`'s successor/notice to the predecessor identity without replacing the original
   signature.
7. Make current authority depend on `K_new`'s own issuance/status evidence and the canonical GY-N12
   head.
8. Bind every `K` result and public observer receipt to this correction, snapshot, cutoff, selected
   versions/notice, and non-producer verifier provenance.

### 6.4 Worked outcomes

| Original relation to revocation/compromise | Historical predecessor dimension | Current predecessor dimension after correction | Public wording boundary |
| --- | --- | --- | --- |
| Trusted issuance before authenticated revocation; no contrary compromise evidence | `IssuerIssuanceAuthentic=established`; durable result evaluated separately | `CurrentAuthorityAsOf=false` because superseded; current signing authorization may also be false | Distinguish historical issuance, current key authorization, and supersession. |
| Issuance inside unresolved compromise interval | Issuance dimension `not_established` for the affected uncertainty | Not current | State the uncertainty/evidence cutoff; do not call the record forged solely from uncertainty. |
| Signature after authenticated revocation/authorization cutoff | Issuance temporally unauthorized; bytes/history retained as evidence | Not current | State unauthorized issuance; preserve rather than delete. |
| Only an older authentic status snapshot is supplied | Snapshot selection is `supplied_snapshot_only`; current positive unavailable | Current result non-positive/not established | State snapshot limitation; do not present old authentic status as latest. |

### 6.5 F09 remains a real attack

- F09-A catches later-revocation laundering into “never authentic.”
- F09-B catches historical-signature laundering into “still current.”

These attacks exercise distinct dimensions and are not mere restatements of PV-K02.

## 7. Additional concurrency hard case — two corrections admitted on one stale base

C1 admits `v1 -> v2`; C2 separately admits stale `v1 -> v3`. C1 transitions first. Exactly one head
exists at every instant, so a fork-only detector would miss the loss.

The amended rule recomputes the admitted base immediately before every authority append. C2 is
rejected and re-admitted against `v2`; it cannot obtain a last-writer success that silently discards
C1's correction semantics. F18 is the exact attack.

## 8. Current-state negative comparator

At `main@109ba3f4`, complete tree walk over path denominator `policy-engine/src`, all source file
types, case-sensitive fixed strings, binary excluded, establishes:

- `correction_notice`: 0 files / 0 matching lines / 0 occurrences;
- `notify_subscribers`: 0 / 0 / 0; and
- `correction_feed`: 0 / 0 / 0.

The repository has reusable internal evolution, generic cache, projection, temporal, archive, and
subscriber-adjacent components, but no correction-specific outward chain. GY-N12 remains undelivered;
INT-R6 remains unresearched; INT-R7 remains a delivered research profile rather than a production
correction-signing capability.

The selected composite is therefore a research semantic contract with `accepted_narrow_scope`, not
a claim that the current repository can execute it.
