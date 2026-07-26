---
title: PAO-R0 — Recommended Research Revision
status: draft_audit
kind: research-audit
research_task: PAO-R0
source_report_status: delivered
source_report_result_type: accepted_narrow_scope
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
audit_date: 2026-07-26
audit_branch: research/pao-r0-independent-audit
authoritative_for:
  - repository audit findings at the recorded commits
  - recommended research corrections
may_not_use_for:
  - production capability claim
  - final code contract
  - authority grant
  - production migration authorization
  - automatic identity adjudication
  - direct modification of authoritative plans
research_only: true
---

# PAO-R0 — Recommended Research Revision

## Executive finding

**Recommended result type: `confirmed_with_material_revisions`.**

The repository confirms the need for a stable technical custody identity above a single
Policy Design Case. The ratified identity/custody decision classifies that function as OWN.
No such typed contract or capability exists at either audited baseline.

`PolicyMatter` should remain a **research hypothesis** for an opaque accountability and
justification-custody anchor. It must not become a package owner, schema, status lattice,
namespace rule, split/merge adjudicator, migration instruction, or public resolver through
this report alone.

The safely supportable compatibility packet is narrower:

1. do not reinterpret `case_id`, `run_id`, `decision_lineage_key`, `policy_id`,
   `portfolio_id`, an artifact hash, a legal instrument, or a URL as lifetime policy
   identity;
2. do not let similarity, an LLM, a projection, or generic metadata mint identity authority;
3. preserve old CAS and signed bytes;
4. make future associations separately correctable and historically replayable in principle;
5. do not infer evidence applicability from identity continuity;
6. do not ratify owner, status, clock, namespace, cardinality, or split/merge rules until the
   assigned consolidation work is complete.

This revision distinguishes Baseline-A facts from current-main facts. They are identical:
historical commit and pinned current `main` both resolve to
`4813b49f6ce14e8debf3aaea096f0967d38d9768`.

# 1. Task and project fit

## 1.1 Standing

PAO-R0 is a Stage-0 **research anchor** in the Wave-2 backlog. The backlog says its
compatibility freeze is a research guard, not a final code contract, capability claim, or
authority grant.

The ratified fact is functional:

> PolicyOS owns the technical identity needed to keep custody of its own policy
> justification above a single case.

The following are not ratified by that decision:

- package placement;
- a wire identifier;
- namespace federation;
- origin/current custodian fields;
- case-to-matter cardinality;
- split/merge ID allocation;
- legal competence;
- a status enum;
- a nine-clock envelope;
- a public resolver;
- migration authorization.

## 1.2 Exact research question

What minimum technical identity and history constraints let PolicyOS keep its own
justification custody across multiple cases and real-world changes without:

- merging unrelated interventions;
- losing continuity;
- laundering external legal authority;
- transporting evidence beyond its justified scope;
- rewriting historical artifacts;
- creating a duplicate status or canonical owner?

## 1.3 Boundary

| Function | Corrected boundary |
| --- | --- |
| Stable PolicyOS technical custody reference | OWN function, ratified. |
| PolicyOS case/artifact association with that reference | Candidate OWN function; contract and owner unresolved. |
| Candidate identity matching | OWN diagnostic, candidate-only. |
| Legal continuity, succession, split, merger, institutional mandate | INTEGRATE competent external evidence. |
| Administrative registry identifier | INTEGRATE/OBSERVE within registry scope. |
| Evidence applicability after a continuity assertion | Existing transportability/applicability/authority owners; no grant from identity. |
| Applications, eligibility, payments, notices, service delivery, citizen case files | OUT_OF_SCOPE or typed evidence integration, as already ruled. |

## 1.4 Relationship to adjacent tasks

- PAO-R1 applies the boundary function-by-function.
- OPS-R4 owns the canonical time-role algebra.
- OPS-R15 owns the long-cycle benchmark vocabulary and capstone.
- INT-R5 owns competence/delegation research.
- INT-R7 owns key rotation and durable verification.
- INT-R8 owns public uncertainty/compression semantics.
- PAO-R36 owns matter-aware public correction fan-out.
- OPS-R2 owns payload-recompute vs authority-revalidation dependency semantics.

PAO-R0 may identify constraints for those tasks; it may not settle their contracts.

# 2. Current repository baseline

## 2.1 Two-baseline result

| Item | Baseline A | Baseline B |
| --- | --- | --- |
| Ref | Historical report SHA | Pinned current `main` |
| SHA | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `4813b49f6ce14e8debf3aaea096f0967d38d9768` |
| Comparison | — | Identical; no changed files or commits |
| Stale claims | None can be stale due to later evolution | Same tree |

## 2.2 Matter capability state

| Chain element | Corrected state |
| --- | --- |
| Typed matter contract | `planned_only` / `documented_only` |
| Producer | `producer_missing` |
| Persisted matter/association artifact | `artifact_missing` |
| Admission/orchestration bridge | `bridge_missing` |
| Matter-aware consumer | `consumer_missing` |
| Semantic verification | `verification_missing` / `semantic_test_missing` |
| API/dashboard/public surface | `surface_missing` |

It is inaccurate to call the matter contract `contract_only`: no typed contract exists.

## 2.3 Reusable but narrower primitives

| Primitive | Actual owner/state | Safe reuse claim |
| --- | --- | --- |
| Runtime PDC graph | PDC; implemented; graph structure only | Candidate structural integration neighborhood. |
| Record-family completeness and projection anti-laundering | runtime quality/PDC tests; implemented | Reuse negative-gate patterns. |
| CAS, manifests, signatures | core artifacts; implemented | Preserve bytes, content identity, provenance, tenant ownership. |
| Portable audit package | core audit; implemented | Package/verify future canonical artifacts; not semantic event owner. |
| Artifact/task lineage | IR artifacts; implemented | Technical dependencies only. |
| Legal corpus/version producer | Data Forge legal; implemented | Produce legal-document evidence. |
| Legal runtime selection/evaluation | Lex; implemented | Consume/select legal versions; not policy identity. |
| Decision validity | core contracts + Scientist validation; implemented, decision-scoped | Reuse event/dedupe/review patterns; tenant qualification gap remains. |
| Claim lifecycle and reissue | Scientist continuous governance; implemented, claim-scoped | Reuse append-only and affected-scope patterns. |
| Transportability/applicability/capability scope | IR/runtime quality/Scientist; implemented in parts | Canonical owners of evidence-use scope. |
| DDM incidents/readiness/shifts | DDM/Scientist; implemented | Event/evidence producer, not identity owner. |
| Atlas/runtime lineage | projection doctrine and artifact/run surfaces | Future consumer; current UI debt must not be hidden. |

## 2.4 Identifier inventory

Confirmed:

- `PolicyMatter` appears only in the identity decision and Wave-2 backlog.
- `policy_matter`, `matter_id`, and `matter_ref` have no tracked implementation occurrence.
- PDC `RuntimePolicyDesignCase` is strict, run-oriented, and carries no case or subject field.
- `ArtifactID` is a content hash.
- `decision_lineage_key` is decision-scoped and its local persistence path is not
  tenant-qualified.
- generated API clients and dashboard routes are predominantly `run_id`-oriented.
- `PolicyPortfolio` is candidate-composition IR.
- generic `subject_id`/`subject_reference` fields exist but do not implement lifetime policy
  custody.

## 2.5 Owner posture

The repository does not establish a package-level canonical owner for `PolicyMatter`.

Corrected conclusion:

> PDC lineage is the backlog's later integration target and a plausible semantic
> neighborhood. `core.contracts` owns shared ABI, runtime quality is a candidate validating
> bridge, core artifacts owns bytes/signatures, and core audit owns portable verification.
> A P27 consolidation decision must assign the semantic owner before any contract is frozen.

# 3. External research baseline

## 3.1 Bounded negative finding

Replace the universal negative with:

> Within the enumerated review corpus—W3C PROV, Akoma Ntoso/ELI, PREMIS/RiC-O,
> DataCite/ARK/DOI, bitemporal systems, event sourcing, record linkage, GLEIF legal-entity
> events, selected government program inventories, and Memento—no single pattern was found
> that decides lifetime public-policy identity across all report scenarios.

This is a bounded research finding, not proof that no such model exists anywhere.

## 3.2 Supported external lessons

- persistent identifiers separate reference from mutable metadata;
- provenance models attribution/derivation, not domain identity adjudication;
- legal-document identity is not policy identity;
- valid and transaction time preserve different historical views;
- record linkage supports uncertain candidate matches;
- identifier persistence depends on governance, not syntax;
- legal-entity event models are analogies, not direct policy rules.

## 3.3 Citation corrections

- keep official W3C, OASIS, ELI, PREMIS, RiC-O, DataCite, ARK, GLEIF, FPI, and RFC sources
  under bounded wording;
- replace the “DOI Foundation” row's ARK URL with an official DOI Handbook/Foundation URL,
  or relabel it as ARK;
- replace ResearchGate bitemporal citation with the underlying primary publication/author
  report;
- use the official GLEIF Legal Entity Events policy/model for event claims;
- treat publisher links for Fellegi–Sunter and Sadinle as method evidence only.

# 4. Result

## 4.1 Candidate definition

- `research_only: true`
- `candidate_for_consolidation: true`

> `PolicyMatter` is a candidate stable technical reference under which PolicyOS could keep
> custody of its own cases, claims, decisions, corrections, withdrawals, and public
> signatures across more than one case. It is not, by itself, proof of legal continuity,
> evidence applicability, administrative program existence, or jurisdictional effect.

This is a research definition, not a final code contract.

## 4.2 Safely established distinctions

`PolicyMatter` must remain distinct from:

- a run, job, graph, case, or decision lineage;
- an artifact/content hash;
- a legal document or version;
- a PolicyPortfolio;
- a release or epoch;
- a name, URL, agency, budget line, registry entry, or jurisdiction;
- an evidence-transport/applicability certificate;
- an Atlas/public projection.

## 4.3 Candidate identity kernel

- `research_only: true`
- `candidate_for_consolidation: true`

Safe candidate constraints:

- a stable non-reassigned reference is desirable;
- creation/issuance provenance must be retained;
- descriptions/aliases are versioned rather than identity keys;
- admitted assertions and corrections are append-only;
- authority and permitted uses are explicit.

Unresolved design choices:

- identifier syntax and opacity;
- issuer namespace;
- global vs tenant-internal reference;
- whether origin tenant is immutable;
- current custodian representation;
- jurisdiction context;
- alias resolution period;
- public exposure and privacy.

## 4.4 Identity resolution, relations, and statuses

Do not create one `support_status`.

Use separate candidate dimensions:

| Dimension | Candidate representation | Existing owner/mapping requirement |
| --- | --- | --- |
| Relation | `continues`, `succeeds`, `splits_from`, `merges_from`, `corrects`, etc. | Matter-domain vocabulary, still research. |
| Resolution outcome | same/new/successor/split/merge/related/unresolved/contested | Diagnostic result or review receipt; cannot mint authority. |
| Authority | purpose-scoped `AuthorityBoundary` and competence evidence | Extend/map existing authority owner. |
| Evidentiary support | Existing claim/capability support contracts | Do not duplicate. |
| Lifecycle validity | Existing decision/claim validity and reissue owners | Do not duplicate. |
| Publication/readiness | Existing one-lattice/Atlas grammar | Projection input only. |

`identity_unresolved` and `identity_contested` are safe as resolution outcomes or diagnostic
conditions. `revoked` is a lifecycle/authority event, not a support score.

## 4.5 New episode, successor, split, merge, or new matter

Repository-consistent process advice:

1. resolve typed source/target references and provenance;
2. establish the asserting actor's competence and scope;
3. compare objective, mechanism, population, mandate, accountability, jurisdiction, and
   declared continuity without reducing them to one similarity score;
4. preserve contradictions;
5. emit a candidate outcome or route to competent review;
6. do not grant evidence applicability.

The following must remain open:

- whether every split creates new child IDs;
- whether every merge creates a new result ID;
- whether parents remain publicly/permanently resolvable;
- reenactment default;
- false-split reconciliation and canonical aliases;
- custody transfer across tenants;
- one-case-to-many-matter cardinality.

These are jurisdiction-dependent research and product-policy questions, not Stage-0 rules.

## 4.6 Episode graph

- `research_only: true`
- `candidate_for_consolidation: true`

Safe research properties:

- preserve distinct external objects and PolicyOS authority objects;
- reify authority-relevant assertions;
- allow competing assertions;
- append corrections rather than overwrite;
- retain valid-world and as-recorded views;
- separate identity relations from evidence-use relations;
- keep projections non-authoritative.

Do not freeze:

- one universal episode schema across five lifecycles;
- lifecycle class/type enums;
- required cardinalities;
- authority consequence enums;
- owner/package placement.

## 4.7 Temporal semantics

Established concepts:

- valid time and transaction time;
- source observation and legal/effective time in domain-specific contracts;
- publication time where a public record exists;
- append-only replay.

Candidate compatibility rule:

> Do not collapse legally effective, source-observed, system-recorded, and publicly
> published time when they differ.

OPS-R4 must decide canonical fields. `correction_time` and `supersession_time` should default
to event/relation semantics unless OPS-R4 demonstrates that distinct clocks are required.

## 4.8 Identity versus evidence

Same-matter continuity grants **no evidence authority**.

A future identity layer should only reference or trigger existing:

- `TransportabilityResult` and transportability gates;
- applicability/jurisdiction/validity contracts;
- `CapabilityScope`;
- legal authority and rights/freshness envelopes;
- evidence-independence accounting;
- decision-validity and authority-revalidation events.

It must not reproduce those fields in a common matter envelope.

## 4.9 Tenant and namespace

Current facts:

- CAS uses shared content IDs with separate tenant ownership claims;
- identical bytes can have the same artifact ID in two tenants;
- tenant read isolation is tested;
- public-ref redaction has a reproducible failing test;
- decision-validity lineage paths are keyed only by raw lineage value.

Research constraints:

- no cross-tenant authority inference from matching external IDs;
- future matter stores/routes/caches must be explicitly tenant-safe;
- issuer federation and custody transfer need a trust protocol.

Unresolved:

- immutable origin tenant;
- public namespace;
- equality semantics across issuers;
- institutional transfer;
- imported-artifact association.

## 4.10 Migration principles

Safe research constraints:

1. inventory existing identifier meanings without reinterpretation;
2. add associations, do not mutate historical bytes;
3. preserve unresolved/unassigned cases;
4. distinguish current corrected and historical recorded views;
5. revalidate authority/evidence use after association change;
6. keep old identifiers in their original semantic domains.

Not authorized:

- a migration phase schedule;
- dual-write production behavior;
- public resolver changes;
- cache invalidation rules;
- automated clustering;
- a final sidecar schema.

# 5. Counterexamples and failure modes

## 5.1 Core falsifiers retained

A future proposal is falsified if it:

1. silently merges unrelated interventions;
2. loses a genuine continuity history solely because name, agency, instrument, or scale
   changed;
3. rewrites a signed/CAS historical artifact;
4. lets similarity or a projection grant identity authority;
5. treats identity continuity as evidence transport;
6. loses parent provenance in a split/merge;
7. forces an unresolved candidate into same/new;
8. bypasses tenant access or namespace boundaries;
9. makes a wrong association publicly current without a visible correction;
10. creates a second canonical owner or status lattice.

## 5.2 Corrected failure-pattern mapping

| Research risk | Correct register pattern |
| --- | --- |
| Schema/report mistaken for capability | P01 — Contract-only capability |
| Fragments coexist without orchestration | P02 — Component sophistication with thin orchestration |
| Correction not externally visible | P03 — Internal richness with poor external surface |
| New identity/support/publication statuses | P04 — Status enum proliferation |
| Projection/diagnostic mistaken for authority | P05 — Authority dilution |
| Historical replay lacks rule version | P07 — Schema versioning without rule evolution |
| Time roles collapsed | P08 — Time semantics fragmentation |
| Structurally valid false merge | P10 — Structural-only validation |
| Producers disagree on subject/scope before emission | P12 — Producer fragmentation |
| Matter envelope becomes mandatory gravity well | P13 — Contract gravity well |
| Same matter/split inflates independent support | P14 — Raw evidence count inflation |
| LLM/similarity candidate becomes identity authority | P15 — LLM speculation laundering |
| Human adjudicator lacks mandate/information | P26 — Responsibility-integrity laundering |
| New matter owner bypasses canonical owner | P27 — Parallel re-implementation / canonical-owner bypass |
| Hand-authored benchmark proves itself | P29 — Authorial proof / self-attested artifact |
| A reference/shape is accepted without resolve-bind-verify | P32 — Trust-by-form |
| Named fixture becomes the specification | P33 — Witness-as-spec / teaching-to-the-test |

Do not reuse the source report's shifted titles.

# 6. Benchmark or fixture proposal

## 6.1 Standing

- `research_only: true`
- `candidate_for_consolidation: true`

The proposed synthetic corpus is not an existing fixture. Exact counts are non-binding.

## 6.2 Required benchmark properties

- independently adjudicated, sealed ground truth;
- explicit competence/evidence scope;
- unresolved/contested candidate cases;
- false-merge, false-split, historical rewrite, tenant collision, public correction, and
  evidence-transport sentinels;
- adversarial variants generated beyond the authored examples;
- a validator that fails after semantic corruption;
- no jurisdiction-dependent split/merge expected result unless the fixture supplies the
  relevant legal rule.

## 6.3 Reusable test patterns

- PDC compiler/projection/anti-laundering tests;
- record-family status-only rejection;
- shared-CAS tenant isolation;
- recall/retraction public-contestability blocker;
- decision-validity law-change and legacy-packet tests;
- partial reissue and lifecycle bridge;
- Data Forge/Lex version selection;
- audit archive verification;
- PolicyPortfolio composition tests as conceptual negative evidence.

`run-24` and `lineage_fixture_001` must be described as literals in test scenarios, not
fixture symbols.

# 7. Artifact contract sketches

Every sketch in this section has:

```yaml
research_only: true
candidate_for_consolidation: true
canonical_owner: unresolved
may_not_use_for:
  - production schema
  - authority grant
  - migration authorization
```

## 7.1 Candidate matter reference

```yaml
MatterRefCandidate:
  stable_ref: opaque-or-governed-reference  # syntax unresolved
  issuer_ref: governed-reference            # federation unresolved
  creation_provenance_ref: artifact-reference
```

Do not freeze tenant, jurisdiction, alias, current owner, or public resolver into this
reference.

## 7.2 Candidate lineage assertion

```yaml
MatterLineageAssertionCandidate:
  assertion_ref: immutable-reference
  source_ref: typed-reference
  target_ref: typed-reference
  relation_type: candidate-vocabulary
  asserting_authority_ref: reference
  competence_evidence_refs: [reference]
  provenance_refs: [reference]
  temporal_scope_ref: canonical-temporal-reference
  authority_boundary_ref: canonical-authority-boundary
  correction_of_ref: reference-or-null
  contradiction_refs: [reference]
  prohibited_uses:
    - automatic_evidence_transport
    - automatic_legal_identity
```

No local `support_status` is proposed. Evidentiary support, authority, validity, and
publication map to their canonical owners.

## 7.3 Candidate resolution receipt

```yaml
MatterIdentityResolutionReceiptCandidate:
  receipt_ref: immutable-reference
  subject_refs: [typed-reference]
  candidate_hypotheses: [diagnostic-hypothesis]
  decisive_evidence_refs: [reference]
  rejected_alternatives: [diagnostic-record]
  unresolved_contradictions: [diagnostic-record]
  proposed_resolution_outcome: candidate-outcome
  reviewer_or_producer_ref: reference-or-null
  authority_ceiling_ref: canonical-authority-boundary
  may_not_use_for:
    - identity_authority_without_admitted_assertion
    - evidence_pooling
```

The receipt is diagnostic/audit material, not an admitted lineage assertion.

## 7.4 No common envelope yet

Do not define the source report's common envelope. Consolidation must instead map:

- artifact/CAS refs → core artifacts/contracts;
- provenance → core contracts;
- authority → existing `AuthorityBoundary`;
- tenant/cell → security/CAS ownership;
- jurisdiction/applicability → legal/capability owners;
- time roles → OPS-R4 and existing temporal contracts;
- claim support → existing support owner;
- decision/lifecycle validity → existing validity owners;
- public status → one-lattice/Atlas grammar.

# 8. Later integration handoff

| Candidate responsibility | Producer/owner question | Required chain before capability claim |
| --- | --- | --- |
| Matter reference | P27 decision: PDC semantic area vs another ratified owner | contract → governed producer → persisted artifact → validation bridge → consumer → semantic verification → surface |
| Case association | Scope/cardinality unresolved | typed assertion → CAS/audit → closeout/validity consumers → replay tests |
| External succession evidence | External competent authority + adapter | source evidence → producer-owned artifact → resolve/bind/verify → candidate/admitted assertion |
| Legal link | Data Forge producer + Lex runtime consumer | versioned source → selection/evaluation → scoped matter assertion |
| Incident link | DDM/Scientist producer | incident evidence → typed association → affected-scope closure |
| Identity correction | owner unresolved; PAO-R36 public consumer | append-only correction → impact graph → API/cache/archive/public fan-out |
| Portable verification | core audit after canonical artifact exists | signed package → independent semantic/integrity verifier |
| Atlas view | projection consumer only | canonical producer output or honest unknown |

No row is an implementation instruction.

# 9. Promotion and kill rules

## 9.1 Research-only

Remain research-only while any of these is unresolved:

- canonical owner;
- status/authority mapping;
- OPS-R4 temporal consolidation;
- competence/delegation;
- namespace/federation/transfer;
- case cardinality and granularity;
- independently adjudicated benchmark;
- tenant-qualified storage/routes/caches;
- public correction and archival verification.

## 9.2 Synthetic prototype

A prototype may be proposed only after explicit plan approval and only with:

- synthetic/non-authoritative data;
- candidate-only matching;
- separate resolution receipt and admitted assertion;
- canonical authority/temporal/scope references;
- no production public record changes;
- explicit unresolved/contested outcomes;
- split/merge/replay and cross-tenant negative tests.

## 9.3 Governed/production

This report does not authorize governed or production work. Later plans must prove the full
capability chain, tenant/public-surface closure, migration replay, clean rebuild parity,
key-rotation verification, correction fan-out, and independent legal/records review.

## 9.4 Kill rules already supported

Block any proposal that:

- treats an existing narrow identifier as lifetime identity;
- lets similarity, generic metadata, or projection grant authority;
- rewrites historical bytes;
- bypasses canonical evidence-scope owners;
- bypasses tenant access controls;
- creates a duplicate owner/status lattice;
- uses PolicyPortfolio as a registry;
- claims implementation from a schema, fixture, ADR, plan, or dashboard alone.

# 10. Open questions for consolidation

1. Which package owns the semantic matter reference and lineage assertion?
2. Which fields belong in shared ABI vs owner-local artifacts?
3. Can one PDC bind multiple matters, and at what claim/option/decision scope?
4. Which relation/outcome vocabulary is jurisdiction-neutral?
5. What evidence and delegation establish competent continuity?
6. How do existing claim support, capability authority, decision validity, and Atlas status
   compose with identity diagnostics?
7. Which time roles are fields, event properties, or derived projections?
8. Is origin tenant an identity attribute, provenance attribute, or neither?
9. How are issuer federation, custody transfer, import, and cross-tenant equality handled?
10. What split/merge rules are jurisdictional vs PolicyOS technical custody policy?
11. What retention/resolver guarantee is legally and operationally supportable?
12. Can a wrong association be corrected across API, cache, archive, translation, and
    key-rotation surfaces without changing old bytes?
13. How is dependency completeness proved for matter-aware fan-out?
14. What independent benchmark owner seals the ground truth?

# Appendix A. Replacement compatibility packet

This packet is non-binding unless an item already restates a separately ratified invariant.

| ID | Compatibility statement | Standing |
| --- | --- | --- |
| RCP-01 | `case_id` is not the identity above a case. | Already binding from the ratified boundary. |
| RCP-02 | Do not reinterpret `run_id`, `decision_lineage_key`, artifact IDs, legal-document IDs, portfolio IDs, names, or URLs as lifetime identity. | Defensible temporary compatibility advice. |
| RCP-03 | Similarity, LLM output, generic metadata, and projections cannot mint identity authority. | Already binding authority doctrine. |
| RCP-04 | Historical CAS and signed bytes are not rewritten; corrections are additive. | Already binding integrity/replay doctrine. |
| RCP-05 | Identity continuity grants no evidence applicability or transport. | Already binding evidence-scope doctrine. |
| RCP-06 | Future identity evidence must be typed, provenance-bearing, purpose-scoped, and fail closed when unresolved. | Existing generic invariant; matter schema remains proposed. |
| RCP-07 | Distinct time roles must not be silently collapsed. | Existing temporal principle; OPS-R4 owns final vocabulary. |
| RCP-08 | Matter work must pass P27 owner review and reuse existing ABI, authority, temporal, security, applicability, validity, audit, and projection owners. | Existing reuse-first/P27 rule. |
| RCP-09 | No cross-tenant authority inference follows from equal external IDs or equal content hashes. | Existing isolation principle; federation semantics unresolved. |
| RCP-10 | Owner, identifier form, namespace, tenant transfer, cardinality, split/merge allocation, public resolver, status mapping, and clock fields remain open. | Explicit non-freeze. |

# Appendix B. Corrected final posture

The repository genuinely supports:

- the need for a technical custody identity above a case;
- absence of its implementation;
- non-equivalence of current identifier families;
- candidate-only automated matching;
- preservation of historical bytes;
- separation of identity and evidence applicability;
- reuse of narrower existing primitives.

It supports only as research recommendations:

- an opaque/non-reassigned ID;
- reified lineage assertions;
- an episode graph;
- non-destructive split/merge;
- a diagnostic resolution receipt;
- a case-association sidecar.

It does not support freezing:

- PDC as canonical owner;
- runtime quality as the admission owner;
- core audit as semantic event owner;
- immutable origin tenant;
- mandatory split/merge IDs;
- a common status/temporal envelope;
- nine clocks;
- permanent resolver behavior;
- sidecar correction sufficiency;
- a production migration.
