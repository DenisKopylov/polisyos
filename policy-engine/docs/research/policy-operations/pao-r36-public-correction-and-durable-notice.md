---
title: PAO-R36 - Public Correction and Durable Notice for Our Own Published Records
research_id: PAO-R36
status: delivered_research
result_standing: accepted_narrow_scope
result_reason: >-
  The complete operational semantics, ordering, observer invariant, enumerated completeness model,
  hard-case dispositions, falsifiers, and owner/dependency handoff are specifiable. The repository
  cannot presently support a public-correction capability or an effective/completeness claim because
  the correction-specific notice, controlled-surface registry, subscriber cohort, machine feed,
  archive-link fan-out, and translation-parity chain are absent or undelivered.
repository: https://github.com/DenisKopylov/polisyos
repository_branch_inspected: main
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
delivery_branch: research/pao-r36-public-correction-and-durable-notice
inspection_date: 2026-08-06
wave: 4
research_only: true
dependencies:
  - INT-R6
  - GY-N12
  - INT-R7
  - OPS-R14
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

# PAO-R36 - Public correction and durable notice for our own published records

## 1. Result standing

**Result: `accepted_narrow_scope`.**

The correction fan-out is fully specifiable as an ordered semantic contract with a bounded public
observer, enumerated completion sets, exact failure behavior, and falsifiable outcomes. It is not
currently executable as a PolicyOS capability. At the pinned repository state:

- internal supersession/evolution is a developed primitive with a canonical owner;
- the public-export producer is not a signed correction and lacks a production HTTP bridge;
- no correction-specific notice, subscriber-notification operation, or machine correction feed was
  established in source;
- GY-N12 currentness is contract-only and undelivered;
- INT-R6 translation parity is unresearched; and
- no complete controlled-surface, cache, subscriber, archive, or authoritative-language registry
  exists from which an effective/completeness claim could be recomputed.

That limitation is the reason for the narrow standing, not a reason to weaken the contract. This
research does not claim that the repository can currently issue a public correction.

## 2. Answer to the commission's question

> What is the complete correction fan-out for a record **we** published and signed?

The complete fan-out is a **two-boundary, append-only authority transaction** over an enumerated set
of controlled observers:

1. prepare and authorize a corrected successor without changing the original signed bytes;
2. append an immutable predecessor/successor relation under the existing evolution owner;
3. prepare one durable public correction notice that preserves the protected semantics required by
   PV-K04;
4. freeze every completion denominator before current authority changes;
5. establish proof/key/currentness preconditions through INT-R7 and GY-N12 interfaces;
6. admit the correction, notice, version/as-of relation, notification intent, feed item, archive
   relations, and language-parity obligations as one staged transaction;
7. append the successor as current under GY-N12, making the predecessor non-current without erasing
   its historical authenticity;
8. enforce an authority fence so every controlled surface can return only corrected-current,
   predecessor-historical-with-link, or unavailable;
9. publish the notice on every enumerated controlled authority-bearing surface;
10. make the corrected and superseded versions retrievable with explicit version and `as_of`
    semantics;
11. invalidate and verify every enumerated controlled cache/variant;
12. expose the correction in the machine-readable correction feed;
13. establish bidirectional archive linkage and preservation evidence;
14. establish authoritative-language parity through the future INT-R6 interface;
15. durably admit every registered subscriber/affected-party cohort member to notification and keep
    delivery failures visible; and
16. append an **effective** declaration only after every synchronous member has produced verifiable
    safe-state evidence.

Actual subscriber receipt may continue after effectiveness only when the entire frozen cohort has
already been durably admitted to delivery, no failure can remain silent, and the institutional
risk/notice rule has not required actual receipt before effect. An adverse correction can therefore
have a stricter gate than an ordinary correction.

The detailed stepwise contract and completeness proof obligations are in
[`pao-r36/ordered-fanout-and-completeness-contract.md`](pao-r36/ordered-fanout-and-completeness-contract.md).

## 3. Fixed law and scope boundary

PAO-R36 consumes rather than reopens these ratified findings:

- **PV-K01:** current authority is separately reportable and bound to an authenticated `as_of`
  cutoff;
- **PV-K02:** historical authenticity and current authority are distinct, non-erasing propositions;
- **PV-K04:** a projection may reduce detail but may not amplify truth, certainty, authority,
  currency, or permission; and
- **S0-K08:** correction appends; history is not rewritten.

Pinned anchors are
`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:92-151`
and `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:101`.

The operational question is therefore not whether the old record is deleted or edited. It is how
PolicyOS changes current authority, makes that change publicly observable, completes controlled
fan-out under independent failures, and proves the bounded result.

This research is limited to custody of PolicyOS's own signatures and published records. It excludes
third-party misinformation monitoring, discovery of external false copies, takedown requests to
uncontrolled publishers, social-media monitoring, and claims that the public internet has converged.

## 4. Pass I - orientation audit before design

The detailed ledger is
[`pao-r36/orientation-ledger.md`](pao-r36/orientation-ledger.md). Every repository proposition in the
package is pinned to `1a7a2d05ebba22fae80e9934329e4b880806588e`.

Ordinary GitHub egress was unavailable in the execution environment and `gh` was not installed. The
commission-permitted connected exact-ref interface was used. This allowed exact file reads and
exact-ref path-bounded searches but not a local whole-tree counting script. P35 therefore requires a
split verdict rather than invented certainty.

### 4.1 Census dispositions

| Exact token | Brief file count | Independent observation at the pin | Disposition |
| --- | ---: | --- | --- |
| `supersede` | 48 | 49 distinct exact-ref connector candidate files | **Not verified; disagreement.** Connector search is not promoted into a P35-complete literal census. |
| `superseded` | 34 | 37 distinct exact-ref connector candidate files | **Not verified; disagreement** under the same limitation. |
| `retraction` | 6 | 7 files in the stated all-file `policy-engine/src` denominator: six Python files plus one README | **Inherited denominator wrong as stated.** Six is the Python-file count; seven is the connector all-file set. |
| `cache_invalidat` | 3 | 3 distinct source files | Connector agreement on file count; matched lines and literal occurrences remain not established. |
| `subscriber` | 3 | 3 distinct source files | Connector agreement on file count; no correction subscriber capability follows. |
| `correction_notice` | 0 | zero indexed path-bounded results | Connector agreement, not an overstated script-proved universal absence. |
| `notify_subscribers` | 0 | zero indexed path-bounded results | Connector agreement with the same boundary. |
| `correction_feed` | 0 | zero indexed path-bounded results | Connector agreement with the same boundary. |

The inherited statement that `rule_evolution.py` has 30 top-level classes and functions does
reproduce. A complete four-range read of all 839/839 lines found 28 column-zero `def` declarations,
two column-zero `class` declarations, and no column-zero `async def`: **30 total**. The arithmetic is
28 + 2 = 30; the nested protocol method is excluded because it is not top-level.

### 4.2 Structural orientation that does reproduce

- `policy-engine/src/polisyos/core/contracts/rule_evolution.py` is the canonical evolution owner. It
  records producer/reader ownership, persistence, replay, a bridge/consumer/verification chain,
  blocks semantic changes, preserves old-logic replay, and states `silent_upgrade_allowed: False`
  (`:1-35`, `:130-231`, `:270-338`).
- `policy-engine/src/polisyos/runtime/quality/projection_semantics.py` is 3,763 lines and owns the four
  canonical audiences PUBLIC, REVIEWER, EXPERT, and MACHINE (`:648-655`, `:3758-3763`).
- `policy-engine/src/polisyos/runtime/quality/public_export.py` is 2,103 lines, builds the public
  bundle, contains no exact `signature` token, and has no production HTTP caller. The existing public
  export producer-to-HTTP relation is correctly `bridge_missing`; that does not make it a correction
  capability.
- GY-N12 is the sole planned epoch/currentness owner and explicitly reuses rule evolution rather
  than creating a parallel correction chronology
  (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2052-2138`).
- Atlas D4 is ratified: `uk` primary, `en` baseline/fallback, `ru` UI
  `legacy_continuity_frozen` - not used and not deleted
  (`policy-engine/docs/brand/ATLAS_SOURCE_OF_TRUTH.md:262-338`).

The repository asymmetry remains material even after correcting the inherited counts: internal
supersession is broad; a public correction chain is not established.

## 5. Selected operating model

The selected model is composite because no single comparator covers history, authority, public
notice, machine access, direct notification, caches, archives, and language parity:

- append-only predecessor/successor chain is the semantic backbone;
- versioned resource and explicit `as_of` retrieval preserve historically bounded use;
- a separate linked notice is the public reasons-bearing object;
- statistical revision practice supplies classifications, published policy, vintages, and change
  analysis;
- official-gazette practice supplies durable citation and replacement/corrigendum conventions;
- push plus pull supplies subscriber notice and public/machine replay;
- verified invalidation supplies safe convergence for the controlled cache set;
- archive relationships preserve original/successor context; and
- INT-R6 must supply language-invariant semantic identity and parity.

The breadth-first comparison and worked hard-case fixtures are in
[`pao-r36/comparative-models-and-hard-cases.md`](pao-r36/comparative-models-and-hard-cases.md).

### 5.1 Rejected standalone models

- **Internal append chain only:** rejects public observability and has no fan-out denominator.
- **Version/as-of only:** pull retrieval does not notify known affected parties or prove convergence.
- **Statistical revision policy only:** does not establish signer authority, individual exposure, or
  legal effect.
- **Gazette notice only:** does not update APIs, caches, machine consumers, subscriber cohorts, or
  languages.
- **Separate erratum only:** can coexist with a predecessor still rendered as current.
- **Push only:** excludes unregistered observers and lacks public replay.
- **Pull only:** leaves known subscribers and affected parties with the discovery burden.
- **Best-effort cache invalidation:** permits predecessor-current after an effective claim.
- **Retraction/tombstone:** collapses correction, withdrawal, historical authenticity, and old legal
  significance; it fails the non-erasure law as a governing model.
- **Current PolicyOS state:** internal supersession with no outward correction chain leaves the
  observer unable to know that current authority changed.

## 6. Ordered semantic contract

The operation has two public boundaries:

- `t_authority`: GY-N12 appends the successor as current and the predecessor becomes non-current; and
- `t_effective`: every synchronous enumerated gate has passed and a bounded completion assertion is
  appended.

`t_stage <= t_authority <= t_effective`. Effectiveness is not backdated to staging or authority
transition.

### 6.1 Steps, failure behavior, and verification

| Step | Preconditions | Effect | Failure behavior | Verifiable evidence | Effect gate |
| --- | --- | --- | --- | --- | --- |
| 0. Classify | Exact original, issuer, claim class, reason, scope, risk direction, and known affected decisions | Creates a proposed correction disposition | Missing/indeterminate class blocks staging; no generic “minor” fallback | Authorized classification, reasons, original identity | Before authority |
| 1. Preserve original | Original bytes, signature, proof/status evidence, publication context available | Freezes predecessor as historical evidence | Missing original or evidence blocks correction; never reconstruct silently | Content identity, signature/proof refs, custody receipt | Before authority |
| 2. Construct successor | Corrected proposition, reasons, limitations, scope, denied uses, recourse resolved | Produces a new non-current successor candidate | In-place edit or unresolved protected input is rejected | Source-resolvable semantic diff and independent authorization | Before authority |
| 3. Link evolution | Canonical owner accepts predecessor/successor relation | Appends proposed relation; no second head yet | Fork, cycle, missing predecessor, or duplicate head rejects transaction | One predecessor, one successor, immutable relation evidence | Before authority |
| 4. Build public notice | PV-K04 protected semantics and links available | Creates reasons-bearing correction notice | Missing material condition/limitation/risk/recourse blocks | Protected-query comparison against source | Before authority |
| 5. Freeze denominators | Registries for controlled surfaces, caches, subscribers, feed partitions, archives, languages, and key evidence close at a cutoff | Creates immutable snapshots `S,C,N,P,F,A,L,K` | Mutable, ownerless, or unenumerated set blocks any “all” claim | Member lists, counts, cutoff, owners, exclusions | Before authority |
| 6. Establish signature/currentness prerequisites | INT-R7 outcome and GY-N12 interface state available | Proves original historical outcome and successor authorization without conflating them | Revoked/unknown signing interval or unavailable currentness yields bounded negative/indeterminate outcome | Authenticated status snapshots and `as_of` cutoff | Before authority |
| 7. Stage fan-out intent | Successor, notice, version/as-of relation, feed item, archive links, language obligations, and cohort intents all reference one correction identity | Makes the transaction recoverable without making it current | Partial staging stays non-current and visibly incomplete | Cross-reference closure and per-member admission receipts | Before authority |
| 8. Transition current authority | All pre-authority gates pass; one current-head owner available | Appends successor-current and predecessor-non-current at `t_authority` | Append failure leaves predecessor current; ambiguous outcome makes controlled surfaces fail closed pending reconciliation | GY-N12 event and exact cutoff | Before effective |
| 9. Enforce authority fence | `t_authority` visible to controlled read paths | Prevents predecessor-current; permits corrected-current, historical-with-link, or unavailable | Any bypass is a red incident and blocks effectiveness | Probe every member of `S` and relevant `C` variants | Before effective |
| 10. Publish notice and version/as-of state | Surface inventory frozen | Every controlled surface links notice, successor, predecessor, and currentness | Failed member remains unavailable/non-current and blocks effectiveness | Per-member retrieval/protected-query receipt | Before effective |
| 11. Invalidate controlled caches | Cache inventory and variant keys frozen | Evicts/marks predecessor-current and warms or resolves safe successor/history state | Best-effort acknowledgement is insufficient; failed member blocks effectiveness | Read-after-invalidate probe on all `C` | Before effective |
| 12. Feed, archive, and language parity | `F`, `A`, `L` frozen; INT-R6 parity interface available | Makes correction replayable to machines, bidirectionally linked in archives, and semantically equivalent in authoritative languages | Missing partition, lost link, or language divergence blocks effectiveness | Partition offsets/snapshot evidence, archive round-trip, protected-query parity | Before effective |
| 13. Subscriber/affected-party admission | `N` and any adverse cohort `P` frozen | Durably admits each member to delivery and exposes receipt/failure state | Silent drop blocks; adverse institutional rule may require actual receipt before effect | Per-member admission and delivery state; red dead-letter state | Admission before effect; receipt may lag only under stated rule |
| 14. Effective declaration | Every synchronous member passed against the frozen snapshots | Appends bounded `t_effective` assertion naming exactly what is complete | Any missing/failed/stale receipt means `NO_EFFECTIVE` | Independently recomputable manifest of sets, counts, cutoffs, and receipts | Final synchronous gate |
| 15. Post-effect operation | Effective declaration exists | Continues delivery, audits, later incidents, and further corrections append-only | Later failure appends incident and may downgrade bounded surface state; never rewrites completion history | Delivery/incident receipts and renewed `as_of` reports | May lag |

No step is “retry until green” without evidence of each failed intermediate state. A partway failure
leaves either the predecessor current (before `t_authority`) or all affected controlled surfaces in a
safe non-predecessor-current state (after `t_authority`).

## 7. Completeness semantics

### 7.1 Required enumerated sets

| Set | Complete denominator |
| --- | --- |
| `R` | Original, successor, correction notice, authority transition, effective declaration, and required status/reason records for this correction transaction |
| `S` | Every controlled authority-bearing public surface and route variant that can answer currentness or render the record |
| `C` | Every controlled cache/CDN/store layer and key/locale/device/representation variant that can serve a member of `S` |
| `N` | Every registered subscriber admitted by the correction's subscription policy at the frozen cutoff |
| `P` | Every affected-party member admitted by the institutional adverse-impact rule, when that rule applies |
| `F` | Every declared feed partition, cursor domain, or replay segment required to expose the correction to the declared machine consumer class |
| `A` | Every archive or preserved copy under organizational or contractual control that is included in the bounded archive claim |
| `L` | Every authoritative language version for the correction under Atlas D4 and the future INT-R6 decision |
| `K` | Every signature, key-status, timestamp/currentness, preservation, and verification evidence item required by INT-R7 for the reported outcome |

Unknown browser copies, screenshots, search indexes, downstream republications, and third-party
caches are not silently included. They are explicit exclusions. The system may say “complete over
`S@cutoff` and `C@cutoff`”; it may not say “all public copies are corrected.”

### 7.2 Structural completeness rule

For each set `X`, a completion assertion is valid only if it carries:

- one immutable snapshot identity `snapshot(X)`;
- the complete member list or a content-bound derivation from the owning source of truth;
- `|X|`, the finite member count at the cutoff;
- set owner and membership rule;
- cutoff and any governed exclusions;
- one member outcome for every member; and
- a verifier that recomputes the outcomes from live artifacts/surfaces rather than trusting the
  producer's receipt.

Formally, for a governed predicate `safe_X(x, c, t_effective)`:

`complete_X(c) := enumerated(snapshot(X,c)) AND count(receipts_X) = |X| AND forall x in X: verified(safe_X(x,c,t_effective))`.

A missing member, duplicate member, mutable denominator, unresolved receipt, or self-attested-only
receipt makes `complete_X` false. “All caches,” “all subscribers,” and “all archives” without a
snapshot are not claims.

## 8. Public observer model and distributed-consistency invariant

Between `t_authority` and `t_effective`, systems may fail and converge at different times. For each
controlled authority-bearing surface `s in S`, a public observer may see exactly one of:

1. **successor-current-linked:** the corrected record is current and links to the notice and
   predecessor;
2. **predecessor-historical-linked:** the old record is retrievable only as historical/non-current
   and links to its successor and notice; or
3. **unavailable-fail-closed:** the surface declines a current-authority answer and exposes a bounded
   failure/maintenance state.

The invariant is:

`forall s in S, forall t >= t_authority: state(s,t) in {successor_current_linked, predecessor_historical_linked, unavailable_fail_closed}`.

The dangerous states are forbidden:

- predecessor rendered as current after `t_authority`;
- successor rendered as current without notice/predecessor/currentness links;
- two current heads;
- a notice that exists but the corrected record or recourse path is unreachable;
- an effective claim while an enumerated member is missing or red;
- historical authenticity made false merely because a key was later revoked; and
- a restore that resurrects predecessor-current.

This is the consistency law that makes asynchronous physical convergence safe. The operation is not
required to make every system switch in one instant; it is required to prevent any controlled system
from asserting the dangerous intermediate meaning.

## 9. The three hard cases

### 9.1 Correction increases risk or exposure

**Worked disposition.** The original record states that a person, group, place, or activity is below
a threshold. The corrected source shows a higher-risk classification that can trigger scrutiny,
restriction, cost, or loss of benefit.

The transaction must:

- classify `risk_direction = increases_exposure` before authority transition;
- preserve the old statement, reasons, evidence, and the exact interval during which it was current;
- state what changed, why, who may be affected, and which uses are denied pending institutional
  review;
- freeze an affected-party cohort `P` under an authorized rule rather than infer it from a convenient
  subscriber list;
- obtain an institutional decision on hearing, direct notice, timing, protective redaction, and
  whether actual receipt is required before effect;
- avoid implying that the correction applies retroactively to decisions already taken; and
- preserve contest, review, and recourse routes.

A neutral/default classification is forbidden when risk direction is unresolved. PAO-R36 does not
declare any notice legally sufficient.

### 9.2 Legally significant superseded version

**Worked disposition.** A benefit, restriction, contract adjustment, inspection, or administrative
decision was made while the old signed version was current. A later correction changes the basis.

The transaction must:

- retain the superseded version and its signature/proof closure;
- bind each prior decision to the exact version and decision-time/currentness cutoff it used;
- expose the successor and correction notice without relabeling the prior decision as if it used the
  successor;
- state that the old version is non-current for new use while its significance for past decisions is
  an unresolved or institutionally decided proposition;
- record any reconsideration, appeal, grandfathering, remedy, or no-change disposition as a separate
  append-only decision; and
- prevent archives or APIs from returning only “latest,” which would make the prior decision
  unintelligible.

The correction does not by itself void, validate, reopen, or ratify an earlier decision.

### 9.3 Original signed with a since-revoked key

**Worked disposition.** The original record was signed under key `K_old`; the key was later retired,
revoked, or compromised; the correction is issued under a currently authorized key `K_new`.

Consume INT-R7 as follows:

- verify the original against issuance-time signer authority, trusted time, status evidence, and
  compromise/revocation interval;
- report the original as historically authentic only if the INT-R7 predicate supports that outcome;
- report uncertain overlap as indeterminate and never current-positive;
- do not infer that later revocation makes an earlier valid issuance a forgery or erases it;
- do not allow `K_old` to sign the correction after its authority cutoff;
- sign the correction under a current authorized issuer role/key and link its proof to the original
  proof/status history;
- preserve any preservation-custodian signature as preservation evidence, not a replacement issuer
  signature; and
- continue to report current authority separately through GY-N12/currentness evidence.

PAO-R36 chooses no algorithm, certificate authority, key store, revocation mechanism, or renewal
period.

## 10. Public correction notice semantics under PV-K04

### 10.1 Must retain

A public correction notice must retain or source-resolvably bind:

- original record identity, exact predecessor version, successor identity, and immutable relation;
- issuer/authorizing role and bounded authority evidence reference;
- what was wrong, what changed, why it changed, and the correction classification;
- claim type, basis, scope, assumptions, material conditions, and limitations;
- current-authority state and authenticated `as_of`, publication, authority-transition, and effective
  times as distinct roles;
- denied uses and any new or preserved use limitations;
- risk direction, affected-class statement, and whether a direct-notice/receipt decision remains
  pending;
- whether the old version has known or unresolved significance for decisions already taken;
- contest, dissent, recourse, review, and contact routes;
- signature/key-status distinction, including historical versus current outcome;
- archive relationship and bounded preservation state;
- authoritative-language set/parity status and any fail-closed language member; and
- bounded completion scope: exactly which frozen sets are complete and which external copies are
  excluded.

Omitting any item that changes a protected answer converts the public operation into a rewrite or an
authority-amplifying projection, even when the database keeps the history.

### 10.2 May compress

The notice may compress unchanged narrative, repetitive evidence detail, proof internals, and
operational receipt detail when:

- every surfaced claim remains resolvable to the source;
- the compression does not change claim type, scope, basis, conditions, limitations, denied use,
  risk direction, currentness, recourse, or old-version qualification;
- dropped material has a governed omission reason/effect relation; and
- the shorter notice is equal or more conservative for every protected query.

It may not summarize “revoked key” as “invalid document,” “superseded” as “never authentic,” or
“notice admitted to delivery” as “all affected persons notified.”

## 11. Machine-readable correction feed - semantic requirements only

A machine consumer must be able to determine:

- the invariant correction identity;
- exact original and successor identities and direction of supersession;
- correction/revision/withdrawal classification and risk direction;
- what claim, scope, conditions, limitations, and denied uses changed or were retained;
- historical-authenticity and current-authority outcomes as distinct dimensions;
- relevant publication, authority, effective, and `as_of` cutoffs;
- whether an old version may have significance for earlier decisions and where its disposition is
  recorded;
- notice, recourse, archive, language, signature/key-status, and verification references;
- bounded completion snapshots and per-domain status for surfaces, caches, subscribers, feed,
  archives, and languages; and
- later incidents or corrections in the same append-only chain.

A machine consumer must never be able to conclude from the feed alone that:

- the original was deleted, forged, or historically unauthentic merely because it was superseded or
  a key was later revoked;
- the correction automatically invalidated or reopened past decisions;
- the notice is legally sufficient in a jurisdiction;
- every subscriber or affected person actually received or understood notice;
- uncontrolled internet copies or search indexes have converged;
- historical authenticity establishes current authority;
- missing/indeterminate currentness is a positive;
- translation parity exists without INT-R6 evidence; or
- a preservation signature is the original issuer's signature.

This research defines no feed schema, serialization, media type, endpoint, package, topic, database,
or transport.

## 12. Effectiveness and permitted lag

### 12.1 Must be complete before `effective`

- `R`: original/successor/notice/status/effective records and their append-only links;
- `S`: every controlled authority-bearing surface in a safe state;
- `C`: every controlled cache/variant verified not to serve predecessor-current;
- `F`: every declared machine-feed partition or replay domain exposes the correction;
- `A`: every archive in the bounded controlled claim has bidirectional original/successor/notice
  linkage;
- `L`: every authoritative language has an INT-R6 parity pass or is fail-closed; a divergent active
  language blocks effectiveness;
- `K`: every evidence item needed for the reported signature/currentness outcome resolves and
  content-binds;
- `N`: every registered subscriber in the frozen cohort has a durable delivery-admission state and
  failures are visible; and
- `P`: every member of an adverse affected-party cohort satisfies the institutionally chosen
  pre-effect condition.

### 12.2 May lag after `effective`

- actual subscriber receipt, acknowledgment, or later retry when the complete cohort was admitted
  durably and the institutional policy does not require receipt first;
- analytics about notice reach, comprehension, or downstream use;
- uncontrolled third-party caches and republications, reported only as exclusions;
- later archive replication or preservation actions outside the bounded `A` set; and
- post-effect investigation, appeal, reconsideration, or remedy, each appended as its own governed
  event.

A lagging process may not change the meaning of the effective claim. Its separate state remains
publicly/auditably reportable.

## 13. Falsifier suite

The executable semantic specification is
[`pao-r36/falsifier-suite.md`](pao-r36/falsifier-suite.md). It defines exact outcomes such as
`BLOCK_AUTHORITY`, `NO_EFFECTIVE`, `FAIL_CLOSED(member)`, `RED(gate)`, `APPEND_INCIDENT`, and
`REJECT_TRANSACTION`.

Required falsifiers include:

1. authoritative language versions diverge;
2. a superseded record renders as current on a controlled surface;
3. a correction rewrites the predecessor instead of superseding it;
4. a controlled cache serves predecessor-current after effectiveness;
5. a subscriber is never notified and no gate turns red;
6. a notice drops a retained limitation; and
7. an archived copy loses its supersession link.

Commission-independent attacks add:

8. forked current heads;
9. later key revocation laundered into “original never authentic”;
10. an adverse correction mislabeled neutral;
11. recovery un-corrects the record;
12. subscriber denominator mutates after admission;
13. `as_of` inversion or backdated effectiveness;
14. an unenumerated external copy is used to claim universal convergence;
15. notice published while successor or recourse is unreachable; and
16. a self-attested completion manifest remains green after a member receipt is removed.

For every fixture the current-state negative comparator shows the same failure pattern: internal
supersession can exist while the public observer still sees predecessor-current or no durable notice,
feed, receipt, archive relation, or parity evidence.

## 14. Repository integration handoff

The complete owner/label/dependency map is
[`pao-r36/repository-integration-and-dependencies.md`](pao-r36/repository-integration-and-dependencies.md).

### 14.1 Canonical placement

- extend `core/contracts/rule_evolution.py` for the append-only correction relation;
- consume GY-N12 for current head, epoch, stale/reissue, and `as_of` currentness;
- extend `projection_semantics.py` for correction-notice protected semantics;
- extend `public_export.py` only through a competent architecture decision and without treating its
  unsigned existing bundle as a correction;
- consume INT-R7 for signing-time and key-lifecycle verification; and
- do not create a PAO-R36 module, a second evolution ledger, a second currentness service, or a fifth
  audience.

### 14.2 Correct missing-state use

| Capability | Pinned-state handoff label |
| --- | --- |
| General rule evolution/replay owner | Existing bounded implemented chain; correction specialization absent/unallocated |
| GY-N12 currentness | `contract_only` / undelivered |
| Public export producer to production HTTP | `bridge_missing` because both endpoints are named |
| Correction notice | Absent/unallocated, not `producer_missing` because no named correction consumer is evidenced |
| Correction subscriber registry/notification | Absent/unallocated, not `producer_missing` |
| Correction feed | Absent/unallocated |
| Correction cache inventory/bridge | Absent/unallocated; generic cache invalidation tokens do not establish endpoints |
| Correction archive fan-out | Absent/unallocated |
| Translation parity | Blocked on declared INT-R6 research dependency |
| Full-chain verification | Absent/unallocated, not `verification_missing` until the chain is wired |

This avoids the prior-wave error of applying a mature missing-state label before its logical
prerequisite exists.

## 15. Declared dependencies and the OPS-R14 seam

### 15.1 INT-R6 - dependency, not solution

PAO-R36 needs INT-R6 to provide one language-invariant correction identity; semantic parity for claim
type, reasons, scope, material conditions, limitations, denied use, currentness, risk direction,
old-version qualification, contest and recourse; a frozen language denominator; and a fail-closed
outcome on divergence. PAO-R36 does not define translation mechanics.

### 15.2 GY-N12 - dependency, undelivered

PAO-R36 needs one append-only current-head transition, predecessor non-current status, `as_of`
retrieval, and stale/reissue references. It does not create a second owner and cannot claim a current
production correction until GY-N12 is delivered.

### 15.3 INT-R7 - delivered research profile, consumed

PAO-R36 consumes issuance-time signer authority, key status, trusted time, preservation roles,
revocation/compromise uncertainty, and separate historical/current outcomes. It does not redesign
cryptography or custody.

### 15.4 OPS-R14 - declared parallel seam

PAO-R36 owns semantics of change: supersession, notice, fan-out, cache/subscriber/feed/archive/language
behavior, observer invariant, and completion evidence.

OPS-R14 owns mechanics of survival: recovery objectives, replay procedure, legal hold, retention,
expiring rights, renewal, disaster behavior, queue/storage durability, and drill evidence.

Required interface obligations are:

- a recovery operation must never be able to un-correct a record;
- replay must preserve correction order, links, notices, receipts, and currentness cutoffs;
- legal hold/retention action must not sever a required historical correction chain;
- failover must preserve the post-`t_authority` safe-state invariant; and
- signing-right expiry/renewal must expose an authenticated status for INT-R7/PAO-R36 without PAO-R36
  defining expiry.

No recovery objective, expiry period, renewal rule, retention period, retry horizon, disaster mode,
or legal-hold mechanism is specified here.

## 16. External primary-source synthesis

The source and transfer ledger is
[`pao-r36/external-primary-source-and-transfer-ledger.md`](pao-r36/external-primary-source-and-transfer-ledger.md).
It uses stable identifiers across EU, US, and UK regimes plus archival and records standards.

The most important transferable findings are:

- **reasons:** TFEU Article 296, Charter Article 41, APA practice, OFR corrections, ONS policy, and
  Gazette notices all support a reasons-bearing corrective act rather than a silent edit;
- **preservation:** 44 U.S.C. 3101, UK public-record guidance, Gazette permanence, EU historical
  archives, ISO 15489, OAIS, and PREMIS support preservation of record and context without equating
  preservation with current authority;
- **old-version significance:** ONS's treatment of RPI and Gazette date corrections show why a
  published old version can continue to matter for indexation, contracts, reliance, or past
  decisions;
- **revision maturity:** Eurostat/ONS practice supports correction-versus-revision classification,
  published policies, vintages, reason/date notices, and revision analysis;
- **affected parties:** adverse-measure and direct-stakeholder-notice practice supports an explicit
  risk-increase branch, not a universal legal-sufficiency rule;
- **publication of record:** Federal Register and Gazette practice supports durable citation,
  authorized placement, retained originals, and linked corrective publication;
- **accessibility/language:** EU and UK regimes show that a correction unavailable to part of its
  audience is an incomplete public operation; and
- **retraction limit:** scholarly tombstone practice is useful for conspicuous retained status but is
  rejected as the correction model because it does not preserve PolicyOS's full authority/as-of
  semantics.

Nothing in the comparison determines applicable law, legal sufficiency, jurisdictional competence,
or the legal effect of a particular correction.

## 17. Open questions for consolidation

### 17.1 Engineering

- Which existing owner can generate the complete controlled-surface set `S` from live routing so a
  sibling surface cannot bypass the correction fence?
- Can `C` be derived from actual cache/routing configuration, including language and representation
  variants, rather than a parallel hand list?
- Where is the one authority chokepoint that can prevent predecessor-current across all public read
  paths?
- How is subscriber membership frozen across concurrent subscribe/unsubscribe/contact changes?
- Which verifier independently recomputes each completion predicate and fails after a member is
  removed or corrupted?
- What gate prevents notice publication when successor, proof closure, or recourse is unreachable?

### 17.2 Institutional

- Which role may prepare, authorize, and publish a correction, and when must those duties be
  separated?
- Who classifies a correction as exposure-increasing and defines `P`?
- When must actual affected-party receipt precede effectiveness?
- Who decides legal effect, reconsideration, appeal, remedy, or grandfathering for decisions made
  under the old version?
- Which surface is the publication of record and which are convenience projections?
- Which archives are under organizational, contractual, legal-deposit, or no control?
- Which language versions are authoritative after INT-R6, subject to Atlas D4?

### 17.3 Additional research

- INT-R6 multilingual authority equivalence;
- OPS-R14 recovery, legal hold, expiry, renewal, and disaster mechanics under the no-un-correct
  interface;
- a jurisdiction- and record-class-specific duty matrix for direct notice, reconsideration,
  publication, archives, language, and accessibility;
- subscriber reachability and accessible fallback channels without vendor appointment;
- limits of transferring official-gazette correction practice to signed digital records; and
- statistical vintage/revision evidence suitable for correction-quality monitoring without
  authority laundering.

## 18. Delivery package

This research package consists only of Markdown:

1. `pao-r36-public-correction-and-durable-notice.md` - primary answer and standing;
2. `pao-r36/orientation-ledger.md` - Pass I repository audit and corrected orientation;
3. `pao-r36/ordered-fanout-and-completeness-contract.md` - stepwise contract and completeness law;
4. `pao-r36/comparative-models-and-hard-cases.md` - breadth-first selection and hard cases;
5. `pao-r36/falsifier-suite.md` - executable semantic falsifiers and current-state comparator;
6. `pao-r36/repository-integration-and-dependencies.md` - owner-first handoff and seam declarations; and
7. `pao-r36/external-primary-source-and-transfer-ledger.md` - stable external sources and bounded transfers.

Every artifact repeats the `may_not_use_for` boundary. No implementation file, workflow, upload
fragment, staging directory, generated binary, or self-executing automation is part of the delivery.

## 19. Final disposition

`accepted_narrow_scope` is the correct standing because the public correction operation is now
specified strongly enough to falsify unsafe designs and guide consolidation, while the repository
cannot honestly claim the capability or its completion denominators. Advancement requires owner
ratification and later implementation work under the existing evolution, projection, export,
currentness, and verification owners, plus delivered INT-R6/GY-N12/OPS-R14 interfaces. Nothing in
this report opens a production or publication gate.
