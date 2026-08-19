---
title: PAO-R36 - Repository Integration and Dependency Handoff
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

# Repository integration and dependency handoff

## 1. Purpose and vocabulary

This document maps the amended correction contract onto existing PolicyOS owners without appointing
a new package, service, endpoint, database, media type, vendor, archive, signer, publication venue, or
implementation team. It applies P27/P28 owner-first placement and P37 gate-predicate discipline.

The repository capability chain remains:

`typed contract/artifact + producer + persisted artifact/event + orchestration bridge + consumer + verification + surface/out-of-scope decision + negative semantic test`.

The missing-state labels have prerequisites:

- `producer_missing` presupposes a named consumer expecting the artifact/event;
- `bridge_missing` presupposes both producer and consumer;
- `verification_missing` presupposes an already wired chain;
- `surface_missing` presupposes an internal capability; and
- a research contract is not source capability.

Where those prerequisites are absent, the correct statement is `absent/unallocated` or
`not_established`, not a more mature missing-state label.

Every future gate also inherits the amended P37 requirement: the decisive predicate, provenance
class, evidence source, owner, and cutoff are frozen at admission. `consumer_asserted`,
`institutionally_supplied`, and `not_established` predicates cannot produce a positive gate.

## 2. Owner-first integration map

| Needed correction capability | Existing owner/interface to extend or consume | Evidence at `main@109ba3f4` | Correct present-state label | Handoff constraint |
| --- | --- | --- | --- | --- |
| Canonical append-only predecessor/successor relation | `policy-engine/src/polisyos/core/contracts/rule_evolution.py` | The source is byte-identical to the original pin. It owns registry/replay/public annotation, persistence, producer/reader roles, semantic-change blocking, old-logic replay, and `silent_upgrade_allowed: false`. | General evolution chain is implemented in its bounded purpose; public-correction transaction/fan-out specialization is `absent/unallocated`. | Extend the existing owner/domain bridge. Do not create `correction_evolution.py`, a PAO owner, or a second supersession ledger. |
| Current head, `as_of`, epoch, stale/revalidation/reissue/withdrawal chronology | GY-N12 in `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md` at docs pin `109ba3f4` | GY-N12 names one append-only currentness owner and requires reuse of rule evolution. It remains undelivered. | `contract_only` / undelivered as declared by its plan. | Consume its event/currentness answer. PAO-R36 cannot implement another head or treat GY-N12 as delivered. |
| Four-audience correction-notice projection | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py` | Existing PUBLIC, REVIEWER, EXPERT, MACHINE projection machinery owns omission/redaction/gap/contest/recourse/audit semantics. | Base projection capability exists; correction-notice tuple/phase semantics are `absent/unallocated`. | Reuse the four audiences and protected-query semantics. Do not invent a fifth audience or parallel projector. |
| Public bundle producer and HTTP-facing consumer boundary | Producer: `policy-engine/src/polisyos/runtime/quality/public_export.py`; consumer boundary: `policy-engine/src/polisyos/runtime/http/services/control/response_shapes.py`, invoked by `control_plane_store.py` | `build_public_export_bundle` exists. The HTTP response shaper reads `public_export`/`public_export_ref`. The complete invocation census still finds no production path calling the builder. No signing path is established. | Existing producer-to-HTTP relation is `bridge_missing`; correction specialization is `absent/unallocated`. | Both endpoint prerequisites justify `bridge_missing`. Do not infer a signed correction capability or a correction consumer from the label. |
| Terminal issuance/key/currentness/public-verification semantics | Delivered INT-R7 `PublicVerificationProfile`, terminal controlling amendment §18 | Section 18 at `policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:620-760` controls final dimensions, snapshot selection, obtainability, succession, and pre-issuance evidence gate. | Delivered research profile; production correction-signing capability remains unclaimed. | Consume the five dimensions and latest-snapshot rule. Do not select algorithms, key services, certificate authorities, logs, witnesses, or custodians. |
| Durable correction notice producer/reader | No correction-specific source owner established | Complete pinned walk: `correction_notice` = 0 files / 0 matching lines / 0 occurrences under `policy-engine/src`, all source types. | `absent/unallocated`, not `producer_missing`. | First place the semantic contract under existing owners, then name producer, persisted artifact, consumer, verification, and surface. |
| Versioned correction retrieval and full observer tuple | Existing temporal/public retrieval components plus GY-N12 currentness | Generic version/temporal components exist, but no complete correction surface roster or tuple-bound chain is established. | `absent/unallocated` as a correction bridge; generic components are reusable. | Future owner census must enumerate every authority-bearing route/variant and bind it to the same correction/snapshot/generation/currentness answer. |
| Correction-scoped surface/cache generation and read probes | Generic cache owners including `foundry/methods/compiler/hot_reload.py`, `fabric/_adapters/observability.py`, and `fabric/connectors/cache/_store_core.py` | Complete pinned walk: `cache_invalidat` = 3 files / 5 matching lines / 6 occurrences. These are generic mechanisms, not correction inventory or evidence. | Correction capability `absent/unallocated`, not `bridge_missing`. | Enumerate `S/C`, freeze exact registry/config generation, prove the global fence before authority, then independently read-probe each member. |
| Subscriber registry, cohort/obligation freeze, accepted intent, and receipt evidence | Generic subscriber-adjacent source only | Complete pinned walk: `subscriber` = 3 files / 18 matching lines / 21 occurrences; `notify_subscribers` = 0/0/0. No correction cohort/consumer exists. | `absent/unallocated`, not `producer_missing`. | A competent institutional process supplies candidate cohort/obligation inputs; the gate independently reconciles and freezes each member's class at admission. No later downgrade. |
| Public/machine correction feed | No correction feed source owner established | Complete pinned walk: `correction_feed` = 0/0/0. | `absent/unallocated`. | Keep the handoff proposition-only. Do not infer schema, topic, endpoint, media type, package, or service. |
| Archive correction relation | Existing custody/evolution semantics; OPS-R14 preservation interface; no correction-specific archive roster | Required predecessor/successor/notice relation exists only in research semantics. No enumerated correction archive set/source generation is established. | `absent/unallocated` as correction fan-out. | Future census distinguishes controlled archive members from unknown external copies. PAO does not appoint an archive or retention rule. |
| Authoritative-language correction parity | INT-R6 interface plus Atlas D4 language posture | INT-R6 is unresearched. Council Regulation No 1 supports governed language enumeration, not semantic identity. Atlas D4 selects project language posture. | Decisive parity predicate `not_established`; correction mechanism `absent/unallocated`. | Request one invariant identity, parity result, denominator, cutoff, and fail-closed outcome. Do not design translation workflow/equivalence mechanics. |
| Effective gate with phase-correct record set | Existing append chronology plus future correction transaction | Amended research defines `R_gate`, `R_post`, strict event order, full receipt binding, and P37 classification; no source chain exists. | `absent/unallocated`, not `verification_missing`. | Implementer must construct the decisive predicates; a declaration/draft/placeholder cannot satisfy the gate. |
| End-to-end correction verification | Future full chain under existing owners | Producer, artifacts, bridges, inventories, consumers, surfaces, and live tests do not exist as one chain. | `absent/unallocated`, not `verification_missing`. | Apply `verification_missing` only after real wiring. Tests derive members from frozen owners, falsify declarations, remove live properties, replay foreign receipts, and inject generation drift. |

## 3. P37 handoff requirements

The amended detailed contract contains one complete `PredicateProvenanceSnapshot` table. A future
implementation plan must preserve, for every load-bearing predicate:

1. stable predicate identity;
2. one of `recomputed`, `independently_reconciled`, `consumer_asserted`,
   `institutionally_supplied`, or `not_established`;
3. producing and non-producing evidence sources;
4. accountable role, cutoff, and source generation;
5. fail-closed/degraded effect for the last three classes; and
6. a falsify-the-declaration test that keeps markers intact while breaking the live property.

This is a semantic handoff, not a proposed schema. Different representations are permitted only when
the same gate behavior is preserved.

## 4. Dependency declarations

### 4.1 INT-R6 — multilingual authority equivalence, unresearched

PAO-R36 requires an interface supplying:

- one correction semantic identity invariant across the admitted authoritative-language set;
- a parity result for claim type, corrected scope, reasons, material conditions, limitations, denied
  uses, currentness, risk direction, predecessor significance, contest, and independently grounded
  recourse;
- proof that translation cannot broaden authority, permission, certainty, or currency;
- exact language-set snapshot/generation, denominator, and evidence cutoff; and
- a fail-closed `not_established`/divergent result.

Council Regulation No 1 contributes only the bounded lesson that institutional language membership
and language-specific communication/publication are governed and enumerated. It does not establish
semantic identity. Atlas D4 remains the project language posture. PAO-R36 does not define translator
workflow, human review, terminology control, model use, release order, translation memory, or an
equivalence algorithm.

F01-A/B exercises the supplied parity result; it does not smuggle in a local mechanism.

### 4.2 GY-N12 — currentness and epochs, undelivered

PAO-R36 requires:

- one append-only successor current-head event;
- predecessor current-authority false without deleting historical authenticity;
- exact `as_of` answers over event prefixes;
- stale/revalidation/reissue/withdrawal references;
- admitted-base-head recomputation immediately before transition; and
- one chronology corrections consume rather than duplicate.

Until delivered, PAO-R36 can specify but not execute `t_authority` or `t_effective`.

### 4.3 INT-R7 — delivered research profile, terminal section controls

PAO-R36 consumes terminal Section 18's:

- `IssuerIssuanceAuthentic`;
- `ProjectionFaithful`;
- `PublicHistoryEstablished`;
- `DurablyVerifiableAt(t_v)`;
- `CurrentAuthorityAsOf(t_q)`;
- latest-snapshot selection;
- evidence obtainability;
- lawful succession; and
- pre-issuance evidence gate.

Earlier text is read through Section 18. PAO adds only correction identity, notice/fan-out linkage,
controlled-generation/receipt binding, and safe observer requirements.

### 4.4 OPS-R14 — custody resilience and expiring authority

The seam remains as previously confirmed:

- OPS-R14 preserves every version, relation, public head, and completion receipt and supplies
  recovery/preservation mechanics;
- PAO-R36 defines correction meaning, notice, cache/surface/subscriber/feed/language semantics; and
- recovery must never render predecessor-current merely because an old signature verifies.

PAO-R36 does not adjudicate OPS-R14, select storage/disaster mechanics, define retention/expiry, or
set recovery objectives.

## 5. Required owner sequence for a future plan

Without authorizing work, the prerequisite-correct sequence is:

1. complete concept/owner census at the implementation pin;
2. extend canonical rule evolution rather than create a second chronology;
3. consume delivered GY-N12 currentness;
4. bind correction notice semantics into the existing projection owner and packaging owner;
5. persist the correction transaction, predicate-provenance snapshot, set snapshots/generations, and
   member-bound evidence before describing downstream bridges;
6. enumerate actual controlled surfaces, caches, subscribers, feeds, archives, and languages;
7. freeze member obligations and prove the notice/fence before authority transition;
8. wire each producer-to-consumer bridge and preserve failures;
9. expose bounded public/audit states without authority amplification; and
10. execute the deterministic falsifier suite over the real chain.

Only after consumers exist can `producer_missing` apply; only after both endpoints exist can
`bridge_missing` apply; only after wiring can `verification_missing` apply.

## 6. Present capability conclusion

The settled complete census at `main@109ba3f4` gives zero correction-notice, subscriber-notification,
and correction-feed source occurrences under the stated denominator. Generic supersession,
projection, public export, cache, temporal, and subscriber-adjacent code does not compose into a
correction capability.

The amended package therefore remains `accepted_narrow_scope` and
`pending_independent_conformance`. It maps a coherent semantic handoff; it neither authorizes nor
claims the live chain.
