---
title: PAO-R36 - Repository Integration and Dependency Handoff
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

# Repository integration and dependency handoff

## 1. Purpose

This document maps the correction fan-out onto existing PolicyOS owners without appointing a new
package, service, endpoint, database, wire format, or implementation team. It is an owner-first
handoff under P27/P28: extend the repository's existing evolution, projection, publication, and
currentness owners; do not create a second correction chronology beside them.

The handoff also applies the repository's missing-state vocabulary literally. At the pinned commit,
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:14-35` defines a capability as a
chain containing a typed contract/artifact, producer, persisted artifact/event, orchestration bridge,
consumer, verification, inspectable surface or explicit out-of-scope decision, and a negative
semantic test. The labels have prerequisites:

- `producer_missing` presupposes a named consumer that expects the artifact or event;
- `bridge_missing` presupposes both a producer and a consumer;
- `verification_missing` presupposes an already wired chain; and
- `surface_missing` presupposes an internal capability that exists before the surface is considered.

A named idea with none of those endpoints is **absent/unallocated**, not automatically
`producer_missing`. A research contract is not source capability.

## 2. Owner-first integration map

| Needed correction capability | Existing owner to extend or consume | Evidence at the pin | Correct present-state label | Handoff constraint |
| --- | --- | --- | --- | --- |
| Canonical append-only correction and predecessor/successor relation | `policy-engine/src/polisyos/core/contracts/rule_evolution.py` | The owner identifies the shared rule-evolution contract and runtime-quality producer/reader, creates replay-safe registries, blocks semantic changes, preserves original-logic replay, and sets `silent_upgrade_allowed: False` (`:1-35`, `:130-231`, `:270-338`). | The **general evolution owner is implemented as a bounded chain**; a public-correction transaction and its fan-out specialization are **absent/unallocated**. | Extend this owner or its domain-owned runtime bridge. Do not create `correction_evolution.py`, a PAO-R36 owner, or a second supersession ledger. |
| Current head, current authority, epoch, stale/reissue chronology, and `as_of` status | GY-N12 in `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md` | GY-N12 owns model-revision epochs, current fronts, stale/revalidation state, append-only reissue/supersession, and explicitly says to reuse `core.contracts.rule_evolution` rather than build a parallel owner (`:2052-2138`). | `contract_only` / undelivered, as declared by the brief and planning record. | Consume its named interface. PAO-R36 may require a current-head transition and `as_of` answer but may not implement a second currentness owner or claim GY-N12 is delivered. |
| Public correction notice projection across canonical audiences | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py` | The 3,763-line owner builds PUBLIC, REVIEWER, EXPERT, and MACHINE projections from one projection truth (`:648-655`, `:3758-3763`) and already owns omission, redaction, gaps, contest, recourse, and audit references. | Base projection capability exists; correction-notice semantics are **absent/unallocated**. | Reuse its protected-query and limitation machinery. A correction notice must not become a fifth audience or a second projection engine. |
| Public bundle construction | `policy-engine/src/polisyos/runtime/quality/public_export.py` | A 2,103-line bundle producer exists. The exact whole-tree invocation set is the definition, two tools, and two tests; no production HTTP caller exists. The file contains no exact `signature` token (`public_export.py:1-120`; INT-R8 orientation `:145-174`). | `bridge_missing` for the existing public-export producer-to-production-HTTP relationship, because both producer and intended public consumer boundary are named. | A correction handoff may extend this producer only after a competent architecture decision. It must not call the current unsigned bundle a signed correction or infer that its existing `bridge_missing` label proves a correction consumer exists. |
| Issuance-time signature, key retirement/revocation, preservation signature, and verification outcomes | Delivered INT-R7 `PublicVerificationProfile` | INT-R7 distinguishes issuer from preservation custodian, forbids replacing original signatures during migration, preserves predecessor key evidence, and separates historical issuance from current/new-signing authority (`int-r7/public-verification-profile.md:250-405`). | Delivered **research profile**; no production correction-signing capability is thereby established. | Consume INT-R7 outcomes and evidence references. Do not select algorithms, key services, certificate authorities, or a new custody owner. |
| Durable correction notice producer and reader | No correction-specific source owner was established; exact `correction_notice` source search returned zero indexed results | There is no named source contract, producer, persisted event, or correction-specific consumer at the pin. | **Absent/unallocated.** Not `producer_missing`, because a named correction-notice consumer is not yet evidenced. | An implementation plan must first place the semantic contract under the owners above, name its consumer, and then apply the vocabulary. |
| Versioned public resource and explicit `as_of` retrieval of original/successor | Existing public retrieval and currentness owners must be enumerated by a later architecture pass; GY-N12 owns currentness semantics | The research established the required behavior but did not establish one complete current public-resource consumer roster from source. | **Not established / absent as a correction bridge.** | Do not appoint a route or endpoint here. The future plan must enumerate every controlled resource and route through the one currentness answer. |
| Correction-scoped cache and CDN invalidation | Existing generic cache components include `foundry/methods/compiler/hot_reload.py`, `fabric/_adapters/observability.py`, and `fabric/connectors/cache/_store_core.py` | The exact-ref search found three `cache_invalidat` source files, none established as a public-correction cache inventory or consumer. | **Absent/unallocated** for correction. Not `bridge_missing`, because correction producer and cache consumer endpoints are not both established. | Reuse generic cache mechanisms only after the controlled set `C` is enumerated. Generic invalidation tokens do not prove public-currentness convergence. |
| Subscriber registry, cohort freeze, and delivery receipts | Existing generic `subscriber` hits are in scholar search security, review collaboration, and an academic runtime registry | The three token hits do not constitute a correction subscriber registry or notification consumer. Exact `notify_subscribers` search returned zero indexed results. | **Absent/unallocated.** Not `producer_missing`, because a correction-notification consumer/cohort contract is not established. | A future institutional decision must define admission and affected-party rules; engineering must then freeze `N`/`P` snapshots and make failures red. |
| Public/machine correction feed | No source owner established; exact `correction_feed` search returned zero indexed results | No correction feed producer, persisted stream, reader, or verification chain is evidenced. | **Absent/unallocated.** | Keep PAO-R36 at semantic requirements. Do not infer a format, media type, endpoint, topic, or package. |
| Archive linkage and preservation relation | Historical authenticity/current-authority law in PV-K02/S0-K08; preservation roles in INT-R7; repository archival mechanisms not appointed here | The semantics require original and successor retention and bidirectional links, but no correction-specific archive consumer set `A` was established. | **Absent/unallocated** as correction fan-out. | A future owner census must distinguish controlled repositories, legal-deposit copies, contracted archives, and unknown external copies before claiming completion. |
| Authoritative-language correction parity | INT-R6, with Atlas D4 as fixed posture | INT-R6 is unresearched. D4 fixes `uk` as primary, `en` as baseline/fallback, and `ru` as `legacy_continuity_frozen`, not used and not deleted (`ATLAS_SOURCE_OF_TRUTH.md:262-338`). | **Blocked on declared research dependency**, not a locally missing mechanism to invent. | Consume a language-invariant semantic identity and parity outcome from INT-R6; leave mechanics to that task. |
| End-to-end correction verification | Future full chain | The correction producer, persisted event, bridges, consumers, inventories, and surfaces do not yet exist as one wired chain. | **Absent/unallocated**, not `verification_missing`. | Apply `verification_missing` only after the real chain is wired. Then tests must recompute from live members and fail when a member is removed or corrupted. |

## 3. Required handoff sequence

A future implementation plan should use this order, not because PAO-R36 authorizes the work, but
because the capability labels are otherwise logically invalid:

1. prove by complete concept search that each proposed addition belongs under an existing owner or
   record the absence and an architecture decision;
2. extend `rule_evolution.py`'s canonical append-only relation rather than creating a parallel owner;
3. consume GY-N12 current-head/currentness semantics when delivered;
4. bind correction notice semantics into `projection_semantics.py` and public packaging into the
   existing export owner;
5. name and persist the correction event/notice evidence before describing any downstream bridge;
6. enumerate the actual consumers: controlled public surfaces, caches, subscribers, feed readers,
   archives, and authoritative languages;
7. wire each named producer-to-consumer bridge and preserve failure receipts;
8. expose bounded public and audit states without authority amplification; and
9. add semantic tests that exercise the real chain and derive their member set from the frozen
   registries rather than a hand-maintained fixture list.

Only after step 6 can `producer_missing` be applied to a named expected artifact; only after both
endpoints exist can `bridge_missing` be applied; only after step 7 can `verification_missing` be
accurate.

## 4. Dependency declarations

### 4.1 INT-R6 - multilingual authority equivalence, unresearched

PAO-R36 requires INT-R6 to supply this interface, without choosing its mechanism:

- one correction semantic identity that is invariant across authoritative languages;
- a parity answer for claim type, corrected scope, reasons, material conditions, limitations,
  denied uses, currentness, risk direction, legally significant-old-version qualification, and
  contest/recourse;
- an assertion that translation cannot broaden authority, permission, certainty, or currency;
- a language-set denominator and per-language evidence cutoff; and
- a fail-closed outcome when an authoritative language diverges or is unavailable.

Atlas D4 fixes the exposure posture: `uk` primary; `en` baseline/fallback; `ru` frozen legacy and
excluded from active public support. PAO-R36 does not define translation workflow, human review,
terminology control, translation memory, model use, release order, or an equivalence algorithm.

### 4.2 GY-N12 - currentness and epochs, undelivered

PAO-R36 requires GY-N12 to supply:

- append-only current-head transition for the successor;
- current-authority false for the predecessor without deleting historical authenticity;
- exact `as_of` answers over old and new versions;
- stale/revalidation/reissue status references; and
- one chronology that corrections consume rather than duplicate.

Until that owner is delivered, the correction operation can be specified but cannot make a
production currentness or effective claim.

### 4.3 INT-R7 - public verification and key lifecycle, delivered research

PAO-R36 consumes INT-R7 for:

- issuance-time signature and signer-authority evidence;
- key retirement, revocation, compromise interval, and uncertainty outcomes;
- separation of issuer and preservation custodian;
- append-only preservation/renewal lineage; and
- distinct reports for historical authenticity and current authority.

A correction signed after a key-lifecycle event must not rewrite the original signature, relabel a
preservation signer as the issuer, or infer current authority from signature validity.

### 4.4 OPS-R14 - custody-grade resilience and expiring authority, parallel wave-4 seam

PAO-R36 owns the semantics of change. OPS-R14 owns survival mechanics. The interface required from
OPS-R14 is:

- a restore or replay must never make a superseded predecessor current again;
- restored state must preserve correction-event order, predecessor/successor links, notices,
  completion receipts, and currentness cutoffs;
- a legal hold or retention decision must not sever the historical correction chain;
- signing-right expiry or renewal mechanics must expose enough state for INT-R7/PAO-R36 to decide
  whether a correction could be issued, without PAO-R36 defining that expiry; and
- drills must be able to show the bounded semantic result, while OPS-R14 owns recovery targets,
  replay procedures, disaster behavior, hold mechanics, expiry, and renewal.

PAO-R36 sets no recovery objective, service level, expiry period, retry horizon, retention period,
disaster mode, or legal-hold procedure.

## 5. OPS-R14 seam matrix

| Concern | PAO-R36 owns | OPS-R14 owns | Required interface |
| --- | --- | --- | --- |
| Correction meaning | Predecessor/successor, notice, current-authority change, public observer invariant | None | OPS-R14 must preserve the meaning during recovery. |
| Recovery/replay | Requirement that recovery cannot un-correct | Recovery objectives, replay mechanics, ordering restoration, drill evidence | Rebuilt state yields the same current head and complete append-only chain. |
| Legal hold/retention | Correction chain may not lose a required historical link | Hold triggers, retention/deletion mechanics, evidence of enforcement | A held predecessor and its links remain available under the bounded archive claim. |
| Signing right near expiry | Correction operation consumes a current authorization outcome | Expiry/renewal policy and continuity mechanics | Expose an authenticated status outcome; no hidden grace period invented by PAO-R36. |
| Disaster during fan-out | Safe public states remain corrected-current, historical-with-link, or unavailable | Disaster mode, failover, restoration, replay, operational drills | No failover surface may serve predecessor-current after `t_authority`. |
| Subscriber delivery survival | Delivery state remains separately reportable and failures remain red | Queue durability, recovery, replay, operational objectives | Restore cohort snapshot and receipts without converting admitted intent into false receipt. |

The sharp obligation is deliberately one sentence: **a recovery operation must never be able to
un-correct a record.** The mechanism belongs to OPS-R14.

## 6. Typed open questions for consolidation

### 6.1 Engineering

- **ENG-01 - controlled-surface registry:** Which current repository owner can enumerate every
  authority-bearing public surface for set `S`, and what evidence proves there is no sibling bypass?
- **ENG-02 - cache denominator:** Can `C` be derived from actual routing and cache configuration,
  including locale/device/representation variants, rather than maintained as a parallel list?
- **ENG-03 - authority fence:** Where is the one structural chokepoint that can prevent
  predecessor-current responses between `t_authority` and `t_effective` without a per-route patch?
- **ENG-04 - cohort snapshot race:** How is subscriber membership frozen so concurrent subscribe,
  unsubscribe, transfer, and contact changes do not make the denominator mutable after admission?
- **ENG-05 - evidence recomputation:** Which verifier can read the branch/runtime registries and
  independently recompute every completion assertion, including corrupt-member probes?
- **ENG-06 - successor reachability:** What gate prevents publication of a notice when the corrected
  record, proof closure, or recourse target is unavailable?
- **ENG-07 - emergency correction:** Can the same semantic fence be used for urgent adverse-risk
  correction without inventing an unverified bypass, while operational timing remains with OPS-R14?

### 6.2 Institutional

- **INST-01 - correction authority:** Which institutional role may classify and issue a correction,
  and when is separation of preparation, authorization, and publication required?
- **INST-02 - risk increase:** Who decides that a correction increases exposure, which affected
  cohort is in `P`, and whether actual receipt is a pre-effect condition?
- **INST-03 - old legal significance:** Who determines whether a past decision continues, requires
  reconsideration, is appealable, or is void? PAO-R36 explicitly does not decide this.
- **INST-04 - direct notification duty:** What jurisdiction-, record-, and harm-specific rule decides
  whether public notice alone is insufficient? No generic notification step is declared legally
  sufficient.
- **INST-05 - publication of record:** Which controlled publication is the publication of record for
  a PolicyOS-issued statement, and which other surfaces are informative projections?
- **INST-06 - archive boundary:** Which archives are under organizational control, contractual
  control, legal-deposit obligation, or wholly external, and what may be claimed about each class?
- **INST-07 - languages:** Which language versions are authoritative for each audience and
  jurisdiction after INT-R6, subject to the fixed Atlas D4 exposure posture?

### 6.3 Additional research

- **RES-01 - INT-R6:** Establish multilingual semantic identity and authoritative-language parity.
- **RES-02 - OPS-R14:** Establish recovery, replay, legal-hold, expiry, renewal, and disaster
  mechanics compatible with the no-un-correct interface.
- **RES-03 - jurisdictional duty matrix:** Research record-specific notification, reconsideration,
  publication, archival, and adverse-effect rules before any legal-sufficiency claim.
- **RES-04 - subscriber reachability:** Compare public-sector direct-notice regimes and accessible
  fallback channels without appointing a vendor or channel.
- **RES-05 - gazette transfer limits:** Test where official-gazette correction practice transfers to
  signed digital records and where statutory publication rules make it non-transferable.
- **RES-06 - statistical vintage evidence:** Research revision-triangle and real-time-dataset
  evidence suitable for correction quality monitoring without turning statistical practice into an
  authority rule.

## 7. Handoff standing

The integration result is `accepted_narrow_scope`. The canonical placement and dependency interfaces
are sufficiently specified for consolidation. The full correction capability is not present, and its
completeness cannot be verified until controlled surface, cache, subscriber, archive, and language
sets are real, frozen, and wired through the existing owners. This document appoints none of them and
authorizes no implementation.
