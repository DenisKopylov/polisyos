---
title: Lifecycle And Cross-Scope Clarifications — R19 Ratification
status: ratified scoped design decision
owner: team-architecture
created: 2026-10-24
decision_status: accepted by the human principal on 2026-10-24
authoritative_for: [R19-SDD-01, R19-SDD-02, R19-SDD-03, R19-SDD-04, R19-SDD-05]
may_not_use_for: [whole_document_ratification, implementation_acceptance, E02_acceptance, finding_closure, external_authority_grant]
---

# R19: five accepted lifecycle clarifications

The human principal explicitly approved all five proposals on 2026-10-24 and
requested their application. The approved source is
`policy-engine/docs/plans/active/post-e02-r9-unified-implementation/architecture/proposals/r19-system-design-clarifications.md`
at `9f32d2706d60a5970d6fdd9ec9896242271a02ab`, with its adjacent JSON.
This record accepts precisely those five scopes. It does not ratify the whole
vision, target architecture or execution-topology drafts, their deferred choices,
or the implementation plan as executed. Source-bound historical receipts keep
their original standing. Effective rule reference: this record, date and clause ID.

## R19-SDD-01 — References do not transfer admissibility

A qualified custody-subject reference or a parent/child split/merge link is
provenance/reference. By itself it transfers no claim authority, status,
currentness, evidence applicability, permission, audience or retention entitlement.
Existing adapter-local namespaces and opaque refs remain usable without an external
institutional ID. External aliases are optional and source/time-qualified.

A child protected claim may reuse an artifact after current owners resolve and
content-bind it and check the child use's scope, time, method and rights. Reuse
does not require reacquiring identical bytes when their custody permits it; it
does require a valid basis for this use. This rule does not choose a global
subject owner, issuer, schema, relation vocabulary, cardinality or identity ontology.

**Alternative rejected:** inferring admissibility from ancestry/equality. It would
silently transfer authority and rights. **Preserved alternative:** local candidate
work and independently qualified reuse under existing owners.
**Falsifier:** unchanged parent bytes and ancestry, but different child purpose,
audience, jurisdiction or expired right; protected child use must not inherit green.

## R19-SDD-02 — Scoped SDD conflict procedure

For an apparent conflict record both source-bound versions, scope/time, the common
protected act and the incompatible obligations. Any consumer may report the finding;
it may not choose precedence. A dated accepted record from the competent human
principal changes standing. Until resolution, the affected PolicyOS protected use
is not admitted; independent authorized work continues.

This procedure governs only the standing/meaning of PolicyOS SDDs. It changes
neither the actual hierarchy of active system/developer/user instructions nor tool
permissions, overrides no legal/safety prohibition and authorizes no forbidden act.
A repository rule applies only to the compatible extent.

**Alternatives rejected:** latest file wins, agent/consumer chooses precedence,
or global stoppage of unrelated work. **Falsifier:** two applicable incompatible
rules for one protected act remain unresolved while that act is emitted, or the
same finding blocks independent candidate research.

## R19-SDD-03 — Amendment authority needs actual delegation

Amendment authority does not follow from issuer/root succession, key custody,
technical custody, architecture governance, repository access, task assignment or
the principal's unavailability. Only the current human principal may delegate it
through a previously accepted record binding identity, the specific amendment act,
scope and duration/revocation. Without that record, or with contested standing,
no successor is assumed; the amendment remains a proposal. Authorized engineering
work continues. This record appoints no successor and settles no external identity dispute.

**Alternative rejected:** technical control as normative succession.
**Falsifier:** a new key holder or repository administrator changes ratified meaning
without the applicable delegation; an unrelated authorized engineering action must
remain possible under the same principal absence.

## R19-SDD-04 — Open questions keep evidence and choice distinct

Every current open §8.4 ID of the vision document has one stable-ID crosswalk row
and an append-only Decision Log reference. An empirical proposition may link a G8
evidence-only answer. Evidence about a normative/design choice informs options;
the choice and remainder stay open until a dated authorized decision. Mixed items
separate those parts. Evidence never makes the normative choice.

The expected set is every ID in the canonical §8.4 source/version at freeze, not a
fixed five. The generic join detects missing, duplicate and orphan rows. The
existing log holds owner, trigger and disposition. A WP reference is included only
for a genuinely withheld proposition; an ordinary unanswered question is not
automatically withheld. Evidence changes or activation open review and do not
automatically close or ratify the question.

**Alternatives rejected:** treating every question as empirical, hard-coding five
answers, or a new decision registry beside the log/WP owners.
**Falsifier:** a sixth canonical ID is omitted while the count remains five; or
a measured improvement is converted into acceptance of a vocabulary amendment.
The document crosswalk records open standing, not a fresh runtime measurement.

## R19-SDD-05 — Composed claims have their own bounded support

A cross-root claim binds purpose, exact editions, supported edges where needed,
exclusions, audience and temporal support. It creates no PolicyMatter ontology,
common mandate, separate certificate or default weight. Membership never proves
adoption: adoption is an external act whose applicability is resolved and content-bound.

Distinguish a display of member outcomes, a verified descriptive/arithmetic
derivation, and a joint causal/feasibility/program claim. An arithmetic derivation
is scoped to verified inputs and operator and grants no joint-policy authority.
For a protected joint causal, feasibility or program claim, the accepted semantic
obligation is support for the claim’s own relevant interactions/dependencies and
system-level conclusion: justify decomposition where used and ground emergent
claims rather than inheriting them from members. A sum of stand-alone effects
cannot satisfy that obligation. D2.6 and execution-topology §5 are target references
for realizing it; this clause does not import their particular proposed mechanisms,
thresholds, schemas or a not-yet-pinned lattice algebra as binding gates. The existing owner tracks the composed
claim's own relevant dependency/freshness closure. A change limits affected uses;
unrelated claims and historical issuance retain their own scoped standing.

**Alternatives rejected:** membership as adoption, averaging authority, a new
portfolio certificate or default social weighting, and globally invalidating
unaffected claims. **Falsifier:** mutate one load-bearing edition or coupling
premise while keeping member IDs; affected joint use must change before publication,
while an independent member claim remains available under its own basis.

## Impact, migration and revisit

- **Status/authority:** no new runtime enum or authority owner. The existing bands
  and claim-specific rules apply; acceptance of these clauses is not admission of
  any external evidence, appointment or policy.
- **Time/replay:** effective from this dated record. Earlier signed artifacts and
  earlier decisions retain their rule-qualified historical meaning. Applying a
  rule to a new/current protected use requires its existing owner's check; no
  silent retroactive authority or permission backfill.
- **Migration:** add the reference/boundary checks and the stable question join
  through existing owners after E02 acceptance. The plan's task extensions carry
  implementation and behavioral verification; this document implements no code.
- **Affected plan:** CNT-01/03/04/07/08, DES-01/07, GYD-30/33, LIF-02 and related
  quality/public-surface consumers, as routed by R19. No task is completed by this act.
- **Remaining inputs:** actual delegation/standing where contested, child use
  rights/applicability, adoption evidence, supported composition edges and source-
  qualified scientific evidence. No blanket external input is imposed on candidate
  work or direct recomputable verification.
- **Revisit:** any named falsifier, an actual scope collision, or evidence that a
  clause blocks a legitimate already-authorized use opens a dated scoped review.
  Research may propose a better rule; it may not silently replace this record.

Pattern pass: P04/P05/P07/P08/P13/P15/P27/P31/P32/P35/P37/P38.
Acceptance here is human approval of five semantic boundaries, not a capability
claim. Runtime producer/bridge/consumer/surface verification remains future work.
