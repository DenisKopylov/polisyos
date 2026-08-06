---
title: PAO-R36 - Comparative Models, Selection, and Hard Cases
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

# Comparative models, selection, and hard cases

## 1. Selection result

No single comparator supplies the complete correction fan-out. The selected design is a composite:

- append-only predecessor/successor chain as the semantic backbone;
- versioned and explicit `as_of` retrieval for historically bounded use;
- a separate, durable correction notice as a publication-of-record object;
- statistical revision-policy disciplines for change classification, published policy, vintages,
  and revision analysis;
- both push notification and a pull correction feed;
- verified invalidation for the enumerated controlled cache set before an effective claim;
- bidirectional archive linkage; and
- language-invariant correction identity with translation parity supplied later by INT-R6.

The eliminating property for every rejected standalone model is named below.

## 2. Breadth-first comparison

| Model | Strong property | Dangerous omission if used alone | Selection disposition and eliminating property |
| --- | --- | --- | --- |
| 1. Append-only supersession chain with immutable predecessor | Matches `PV-K02`/`S0-K08`; preserves historical authenticity and exposes direction of change | A chain can be internally correct yet invisible to public observers, caches, subscribers, archives, or languages | **Selected as backbone, rejected as complete model.** Eliminating property: no required outward discoverability or fan-out denominator. |
| 2. Versioned resource with explicit `as_of` retrieval | Preserves exact vintages and lets a prior decision bind the version actually used | Pull-only retrieval does not create a notice, alert a subscriber, or prove cache convergence | **Selected as retrieval dimension, rejected as complete model.** Eliminating property: no proactive notice or completion gate. |
| 3. Statistical-agency revision practice | Mature distinctions between scheduled revision and error correction; published policies; revision triangles; old vintages; reason and date of supersession | Statistical vintages often concern estimates and aggregates, not signed authority, individual exposure, mandate, or legal effect of an earlier public act | **Selected as operational analogue, rejected as authority model.** Eliminating property: it cannot by itself answer signature/current-authority or individual administrative-effect questions. |
| 4. Official-gazette/publication-of-record correction | Durable public notice, signer/issuer discipline, citation to prior publication, replacement or correction convention, and preservation of the public record | Gazette publication alone cannot update PolicyOS APIs, machine consumers, controlled caches, subscriber cohorts, or language projections | **Selected as publication convention, rejected as complete fan-out.** Eliminating property: no system-wide controlled-surface convergence. |
| 5. Errata-and-notice as a separate linked document class | Makes the correction discoverable without mutating the original and can carry reasons, scope, and challenge routes | A free-standing erratum can coexist with an old resource still presented as current | **Selected as notice class, rejected as currentness owner.** Eliminating property: no binding current-head transition. |
| 6a. Push notification only | Reaches known recipients without requiring polling | Excludes unregistered observers and machine consumers; delivery lists change; nonreceipt may be silent | **Rejected.** Eliminating property: no universal public discoverability and no pull/replay path. |
| 6b. Pull-only correction feed | Replayable and available to machines and unregistered observers | Imposes discovery burden on affected parties and can leave known subscribers unaware | **Rejected.** Eliminating property: no proactive notification where a duty or risk classification requires it. |
| 6c. Push plus pull | Covers registered cohorts and public/machine observers; supports replay and direct notice | Still needs enumerated cohorts and failure-visible delivery states | **Selected.** Completeness is split: feed completeness, cohort admission, and actual delivery are separately reported. |
| 7a. Cache/CDN invalidation as best effort | Operationally simple; tolerates partial infrastructure failure | Permits a controlled surface to serve the predecessor as current after the system says corrected | **Rejected for controlled caches.** Eliminating property: dangerous stale-current state remains permitted. |
| 7b. Verified invalidation as precondition of `effective` | Makes stale-current on a controlled member a falsifier, not a tolerated delay | Requires an enumerated cache/surface inventory and fail-closed interval | **Selected for controlled `C`/`S`.** Unknown external copies remain disclosed exclusions, not false negatives. |
| 8. Retraction with tombstone | Strong signal that a work should not be relied upon as current; scholarly practice often preserves a marked record | A tombstone collapses correction, withdrawal, unreliability, and legal effect; it can hide the exact successor, deny legitimate historical use, or be implemented as erasure | **Rejected as the correction model.** Eliminating property: it fails the non-erasure law and the need to preserve legally significant old versions. A withdrawal status may be a separate append-only proposition, never a substitute for the correction chain. |
| 9. Current PolicyOS state: internal supersession, zero outward correction chain | Reuses a developed internal primitive and avoids duplicating owners | The public observer can continue to see the predecessor as current; no notice, feed, cohort, archive relation, cache gate, or language-parity evidence exists | **Rejected mandatory negative comparator.** Eliminating property: it violates public observability and cannot support any bounded fan-out completeness claim. |

## 3. Why the composite is preferred

The append chain supplies truth about history; versioned retrieval supplies time-bounded access; the
separate notice supplies reasons and discoverability; statistical practice supplies revision
classification and transparent vintages; publication-of-record practice supplies durable public
linkage; push plus pull supplies direct and replayable notice; verified invalidation supplies safe
controlled convergence; archive linkage preserves evidence; and INT-R6 must supply equivalence
across authoritative languages.

This combination rejects two false choices:

1. **atomic everywhere or unsafe eventual consistency.** PolicyOS does not need every system to
   switch in one physical instant. It needs a semantic fence under which lagging controlled systems
   can be corrected-current, historical-with-link, or unavailable, but never old-current.
2. **delete the error or preserve confusion.** PolicyOS preserves the predecessor as history while
   separately making current authority false and forcing the correction notice onto every controlled
   authority-bearing path.

## 4. Administrative-law and public-record implications

A government correction is not equivalent to a blog edit because it can alter the reasons on which
people relied, change exposure, and affect decisions made during the original publication interval.
The operational contract therefore separates:

- duty-to-give-reasons analogues from the technical act of replacing bytes;
- preservation of an official record from current authority;
- notice to the public from direct notice to an affected cohort;
- correction from revision, withdrawal, retraction, or new policy;
- prospectively corrected guidance from the status of decisions already made; and
- accessibility/language parity from editorial convenience.

These are design transfers, not jurisdictional legal conclusions. The external-source ledger records
what transfers and what does not.

## 5. Hard case A - a correction that increases risk

### Fixture

PolicyOS published and signed a public eligibility record stating that an administrative relief
program applied to entities with a measured burden of up to 50,000 units. The signed source should
have said 25,000. Correcting the value excludes a group that appeared eligible under the predecessor
and may increase repayment, enforcement, planning, or appeal exposure.

The numbers are fictional. The fixture tests direction of harm, not a real program.

### Required disposition

1. The correction is classified `risk_increase` or `mixed_adverse`, never silently `administrative`
   or `beneficial`.
2. The predecessor remains historically authentic and retrievable with its publication interval.
3. The successor is appended with an immutable predecessor relation and a reasoned explanation of
   the corrected threshold.
4. The notice names the affected class and likely direction of increased exposure without exposing
   protected personal information.
5. The notice preserves contest, recourse, deadlines, limitations, and any uncertainty about who is
   affected.
6. An authorized institutional owner determines whether a direct affected-party cohort `P` exists,
   whether actual receipt must precede effect, and whether interim protection is required. PAO-R36
   does not declare the resulting notice legally sufficient.
7. No machine or human reader may infer that the correction automatically has retroactive effect,
   automatically creates liability, or automatically resolves reliance interests.
8. If the affected-party decision is absent or risk direction is unknown, the standard effective
   gate remains red.

### Safe public observations

Before `t_authority`, the predecessor may remain current while the correction is staged and clearly
non-current. After `t_authority`, controlled surfaces may show the successor as current, the
predecessor as historical with the adverse correction notice, or fail closed. A controlled surface
may not continue to present the more favorable predecessor as current.

### Failure halfway

If ordinary public surfaces have converged but the required affected-party cohort is incomplete, the
correction cannot be called effective under a pre-effect receipt rule. If actual receipt was allowed
to lag, every undelivered member stays visible and red; an aggregate cannot hide the failure.

## 6. Hard case B - the superseded version remains legally significant

### Fixture

PolicyOS published and signed a procurement-evaluation record. Contracting decisions were taken while
version `v1` was current. PolicyOS later discovers an error and publishes corrected version `v2`.
Whether any past decision is void, reviewable, grandfathered, or unaffected depends on law and the
competent institution, not on the correction fan-out itself.

### Required disposition

1. Preserve `v1`, its signature, publication interval, reasons, limitations, and authority evidence.
2. Append `v2` and a correction notice; never rewrite `v1` into the corrected text.
3. Bind each past decision record to the exact version and `as_of` context it used.
4. Let the current default select `v2` only after the GY-N12 transition.
5. Let historical retrieval reproduce `v1` and show that it is superseded, not nonexistent.
6. State explicitly that supersession does not automatically decide the validity or remedy for past
   decisions.
7. Preserve any later institutional determination about grandfathering, reconsideration, or remedy as
   another append-only record linked to the affected decisions.
8. Keep both versions in every claimed archive member and expose the bidirectional correction chain.

### What the feed and notice must not imply

They must not say that every decision under `v1` is invalid, that `v1` was never authentic, or that
`v2` applies to a past event merely because it is current now. The machine consumer must be able to
ask which version was authoritative at the relevant cutoff and receive a bounded answer.

### Failure halfway

If the current public page shows `v2` but a decision audit can no longer retrieve `v1`, archive and
historical-retrieval completeness fail. If an archive preserves `v1` bytes but loses its link to
`v2`, the archive also fails: preservation without relation is insufficient for a correction chain.

## 7. Hard case C - correction across a revoked signing key

### Fixture

The predecessor was signed with key `K_old`. The key was later revoked or its authorization ended.
The correction is issued after that event using currently authorized key `K_new`.

### Required disposition under INT-R7

1. Preserve the original signature, original signed statement, trusted-time evidence, applicable
   status snapshots, and key lifecycle events.
2. Evaluate `K_old` at the predecessor issuance interval, not only at the current query time.
3. Keep four propositions distinct:
   - whether the predecessor bytes match the signed statement;
   - whether `K_old` was authorized at the supported issuance time;
   - whether compromise uncertainty makes historical authenticity indeterminate; and
   - whether the predecessor has current authority after supersession.
4. Sign the correction with a currently authorized role/key under the delivered INT-R7 profile.
5. Link `K_new`'s correction to the predecessor identity and to relevant `K_old` status events without
   pretending that key rotation or revocation rewrites the old signature.
6. Make the successor's current authority depend on its own currentness/status evidence and GY-N12
   head, not on a claim that the predecessor remains currently authorized.

### Worked status outcomes

| Original signing relation to revocation/compromise | Historical predecessor outcome | Current predecessor outcome after correction | Required notice wording |
| --- | --- | --- | --- |
| Trusted issuance before an authenticated revocation cutoff, no contrary compromise evidence | May remain historically authentic under INT-R7 | Not current because superseded; key may also be unauthorized for new signing | Distinguish valid historical issuance from revoked current signing authority and supersession |
| Issuance falls in an unresolved compromise interval | Indeterminate; never promoted to a current positive | Not current | State indeterminacy and the evidence cutoff; do not label the old record forged solely from uncertainty |
| Signature was created after an authenticated revocation/authorization cutoff | Unauthorized issuance under the evaluated policy; bytes/history remain preserved | Not current | State unauthorized issuance and preserve the record as evidence; do not delete it |
| Revocation evidence is missing or stale at query time | Current verification cannot be positive | Not current or indeterminate, depending on GY-N12/status evidence | State unavailable/indeterminate status, not `Verified` |

INT-R7 is the delivered owner for these distinctions at
`policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:250-405`.
PAO-R36 adds only the correction-chain obligations. It does not choose algorithms, key providers,
certificate authorities, logs, witnesses, or status services.

### Failure halfway

If the correction page verifies `K_new` but drops `K_old` status history, the chain is incomplete. If
a verifier treats revocation as proof that the original record was never authentic, it violates
`PV-K02`. If it treats a historically authentic `K_old` signature as current authority, it also
violates `PV-K02` and `PV-K01`.

## 8. Mandatory negative comparator - current state

At the pinned commit, the developed internal supersession primitive does not provide the outward
correction chain. Against the three hard cases, an observer can see:

| Fixture | What the current state can represent internally | What the public observer cannot reliably determine |
| --- | --- | --- |
| Risk-increasing correction | An internal record may be superseded or withdrawn | That exposure increased; who is affected; whether a notice exists; whether a direct cohort was admitted; whether nonreceipt turns a gate red |
| Legally significant predecessor | Internal replay/evolution concepts can preserve old logic in some contexts | Which public version governed a past decision; whether the old public record remains retrievable; whether archive links are intact; whether supersession has retroactive effect |
| Revoked-key chain | INT-R7 research supplies semantics and other code owns some signing/currentness concepts | A production public correction proof crossing the revocation event; separate historical/current outcomes on every public surface; completeness of status evidence |

The current state is therefore not a degraded implementation of this contract. It is a missing
public correction capability and must not be represented as able to issue one.

## 9. Selection boundaries

The selected composite does not decide:

- whether a particular jurisdiction recognizes a correction or requires additional service;
- the retroactive legal effect of a corrected record;
- who has legal standing or a remedy;
- how INT-R6 proves semantic language equivalence;
- how OPS-R14 recovers, replays, holds, or expires authority;
- a final wire, schema, serialization, media type, package, database, or endpoint; or
- any implementation owner beyond extending already admitted canonical owners.

## 10. `may_not_use_for`

This comparison may not be used for production implementation authorization; a final wire, schema,
package, database, serialization, media-type, or API contract; canonical owner, vendor, or service
appointment; an authority grant; a capability claim; legal sufficiency or a jurisdictional
conclusion; permission to publish or open a gate; or automatic amendment of any plan, backlog, or
system-design decision.
