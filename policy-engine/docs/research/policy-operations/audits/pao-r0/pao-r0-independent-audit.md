---
title: PAO-R0 — Independent Repository Audit
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

# PAO-R0 — Independent Repository Audit

## 1. Audit scope and standing

This document audits the supplied research report, **PAO-R0 — Policy Matter Identity and
Episode Graph**, as an adversarial repository claim set. It does not endorse or implement the
report. It adds no runtime type, schema, migration, enum, owner, status, or authority rule.

The audit inspected tracked repository content, code, tests, plans, ADRs, ownership metadata,
public-surface policy, import policy, generated API clients, and Git history. It also ran
targeted existing tests and bounded static/dynamic probes. The complete atomic ledger is in
[`pao-r0-claim-evidence-ledger.md`](pao-r0-claim-evidence-ledger.md); commands and fixture
details are in
[`pao-r0-test-and-fixture-verification.md`](pao-r0-test-and-fixture-verification.md).

The audit applies the repository's own standing rules:

- the [identity and custody decision](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md#L1-L20)
  is ratified for system identity and scope, but may not be used as a capability claim;
- the [Wave-2 backlog](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md#L38-L53)
  says every deliverable is research-only, not an authority grant or code contract;
- a research ledger is not runtime authority until normalized, reviewed, and ratified;
- capability claims require the complete producer → artifact → bridge → consumer →
  verification → surface chain.

## 2. Historical and current baselines

| Baseline | Requested ref | Resolved SHA | Result |
| --- | --- | --- | --- |
| A — historical | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Reproduced from a full clone. |
| B — current | `main` resolved at audit start | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Pinned before analysis and branch creation. |

`git ls-remote`, the connected GitHub repository API, and local Git all returned the same
current `main` SHA. GitHub commit comparison returned `identical`, zero commits ahead or
behind, and no changed files. The audit branch was created from that exact tree.

Consequently, Baseline A and Baseline B are byte-identical. Every historical verdict is also
the current verdict. There are no findings in the category “historically correct, now stale,”
and no current-only implementation. This is an evidence result, not an assumption.

The audited commit introduced the ratified identity decision and the reshaped Wave-2 backlog
in the same change:
`4813b49f docs: ratify PolicyOS identity and custody boundary; reshape Wave-2 research; audit both plans`.

## 3. Executive verdict

**Verdict: `confirmed_with_material_revisions`.**

The repository confirms the central need: the ratified boundary decision explicitly places
[`PolicyMatter` identity above a single case in OWN](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md#L123-L139).
It also confirms that existing case, run, decision, artifact, legal-document, portfolio, and
release identities are semantically narrower and that no typed `PolicyMatter` implementation
exists at either baseline.

Material revisions are required because the report then crosses its own research boundary:

1. Appendix D declares a 30-rule freeze “immediately binding,” although both the report and
   repository forbid a research deliverable from granting authority.
2. PDC is a plausible placement candidate, not a ratified `PolicyMatter` canonical owner.
3. The common envelope duplicates several existing owners and introduces a parallel
   `support_status` grammar.
4. Nine proposed clocks pre-empt the explicitly assigned OPS-R4 temporal research.
5. Nine failure-pattern uses are materially misnumbered or misdescribed.
6. `run-24` and `lineage_fixture_001` are literal values in tests, not named reusable fixtures.
7. Lex is not the sole legal-version producer; Data Forge owns offline legal preprocessing.
8. Atlas is projection-only as a doctrine, but the active plan records two current UI surfaces
   that still mint local authority-like values.
9. Tenant safety is substantial but incomplete: raw `decision_lineage_key` storage is not
   tenant-qualified, and a public-export redaction test fails at the pinned baseline.
10. A sidecar correction can preserve signed bytes, but there is no implemented matter-aware
    public correction/fan-out chain proving that the sidecar is sufficient.

The safe Stage-0 result is therefore a smaller compatibility packet: do not reinterpret
existing identifiers; do not let similarity or projection mint identity authority; do not
rewrite signed/CAS history; do not infer evidence applicability from identity continuity; and
do not create a canonical contract before owner, temporal, namespace, status, and correction
consolidation.

## 4. Highest-severity findings

| ID | Severity | Finding | Baseline A | Baseline B | Required action |
| --- | --- | --- | --- | --- | --- |
| F-01 | Critical | **Authority overclaim:** “Immediately binding” turns a research artifact into an unratified authority source. | Contradicted by the report's own `may_not_use_for: authority grant` and the Wave-2 research-only clause. | Same. | Replace “binding” with classified advice/proposals; require human-principal/architecture-owner acceptance for any new constraint. |
| F-02 | Critical | **Parallel-lattice and duplicate-envelope risk:** the proposed `support_status` combines authority, evidentiary support, contestation, resolution, and revocation. | Conflicts with the ratified “no new statuses” rule and overlaps three current status owners. | Same. | Remove the common `support_status`; map relations, resolution outcomes, authority boundary, claim support, and lifecycle validity separately. |
| F-03 | High | **PDC owner not established:** the report converts a later integration target into a canonical-owner conclusion. | PDC is authoritative only for graph structure; the identity decision does not assign package ownership. | Same. | Mark PDC, `core.contracts`, and a possible dedicated sub-area as consolidation candidates; require a P27 owner decision. |
| F-04 | High | **Temporal pre-emption:** mandatory event/valid/effective/transaction/publication/observation/admission/correction/supersession fields settle OPS-R4 prematurely. | OPS-R4 explicitly owns the multi-clock envelope; only a subset is canonical today. | Same. | Freeze the need to preserve distinct time roles, not field names or nine independent clocks. |
| F-05 | High | **Failure-pattern routing defects:** P07, P08, P12, P13, P15, P26, P29, P32, and P33 are used under wrong or shifted meanings. | Contradicted by the register. | Same. | Correct IDs/titles and add the more relevant P04, P06/P09 where applicable. |
| F-06 | High | **Fixture overclaim:** `run-24` and `lineage_fixture_001` are not fixture symbols; several “fixture families” are only ordinary unit tests. | Literal values found; no named fixture/corpus. | Same. | Cite exact test functions and say “test pattern,” not “frozen reusable fixture.” |
| F-07 | High | **Tenant/namespace assumptions are not proven:** immutable `origin_tenant_id` and custody transfer are unratified; decision-validity storage is tenant-blind by key. | Static and dynamic probe confirmed same storage path for identical raw lineage keys. | Same. | Keep federation and transfer open; require tenant-qualified storage before reusing the lineage store. |
| F-08 | High | **Public surface is not fully safe:** the existing public-export redaction test fails and leaks a private CAS reference into the serialized bundle. | One targeted test fails reproducibly. | Same. | Treat public correction/export readiness as incomplete; route to PAO-R36/INT-R7. |
| F-09 | High | **Atlas actual-state overclaim:** projection-only is the governing doctrine, not a complete description of current code. | Active plan records two authority-minting surfaces; code locally computes readiness. | Same. | Distinguish normative boundary from implementation reality. |
| F-10 | High | **Lex ownership is incomplete:** runtime selection is in Lex, but offline source/version-index production is Data Forge-owned. | Public-surface policy and implementation contradict sole-Lex producer wording. | Same. | Use “Data Forge producer → Lex runtime consumer/evaluator” and preserve the legal-document/matter distinction. |
| F-11 | High | **Sidecar sufficiency unproven:** signatures bind historical bytes and manifest, but no matter-aware correction chain exists. | Integrity behavior implemented; semantic correction and public fan-out are planned only. | Same. | Limit PAO-R0 to non-rewrite and typed-link requirements; defer public semantics to PAO-R36/INT-R7. |

## 5. What the research got right

The following findings are supported with high confidence at both baselines:

- The system boundary expressly requires an identity above a single Policy Design Case.
- No implemented `PolicyMatter`, `policy_matter`, `matter_id`, or `matter_ref` type, schema,
  route, generated client field, migration, or persistence family exists.
- `run_id`, `job_id`, and the PDC `graph_id` identify execution/graph context, not a
  lifetime public intervention.
- `ArtifactID` is a SHA-256 content identity. It is stable for bytes, not for a mutable
  real-world policy.
- `decision_lineage_key` identifies a decision-validity lineage and is not proved globally,
  jurisdictionally, or tenant unique.
- legal-document source/version identity is distinct from policy-matter identity.
- `PolicyPortfolio` models candidate `PolicySpec` combinations and interactions, not a
  deployed policy stock.
- technical CAS lineage (`produced_by`, `consumed_by`, `derived_from`,
  `invalidated_by`) is not a policy succession/split/merge graph.
- same-matter continuity must not grant evidence transport. Existing transportability,
  applicability, capability-scope, legal-authority, and evidence-independence contracts
  already support that separation.
- similarity, names, URLs, agencies, shared text, or content hashes must not mint authority.
- corrections must preserve historical bytes and transaction history.
- unresolved identity is a legitimate candidate-resolution result; it need not become a
  second publication state.
- split, merge, succession, and reenactment cannot be decided reliably by a universal
  jurisdiction-neutral similarity rule.

## 6. What is overstated or unsupported

| Report statement | Audit result | Corrected statement |
| --- | --- | --- |
| “PDC is the closest/presumptive canonical owner.” | Plausible architecture inference, not owner proof. | PDC is one candidate placement because the backlog points later integration to PDC lineage; owner remains unratified. |
| “runtime quality should admit matter evidence.” | Candidate integration, not an existing capability or producer authority. | Runtime quality may validate/adapt admitted producer evidence, but its README says it cannot create producer authority itself. |
| “core audit is an appropriate owner for matter-custody audit events.” | Overclaim. | Core audit owns portable packaging and verification; semantic custody-event ownership is unresolved. |
| “No new top-level canonical owner is justified.” | Unsupported. | Reuse-first favors extension, but P27 review must compare PDC, shared ABI, and a narrowly scoped new owner. |
| “The repository already has … matter-ready primitives.” | Partly supported. | It has useful fragments; they are not orchestrated or semantically matter-aware. |
| “Typed matter contract: contract_only.” | Wrong capability vocabulary. | No typed contract exists. State is `planned_only`/`documented_only`, followed by producer/artifact/bridge/consumer/verification/surface missing. |
| “Portable matter verification can extend core audit.” | Design recommendation. | Core audit can package a future canonical artifact after its producer and semantics exist. |
| “Origin tenant is immutable identity.” | Unratified. | Tenant is a security/ownership context today; immutable origin and cross-tenant custody transfer remain research questions. |
| “All nine clocks are mandatory.” | Premature contract. | Time roles must not be collapsed; OPS-R4 must decide canonical names, derivations, and event-vs-field treatment. |
| “Parents remain permanently resolvable.” | Strong archival recommendation, not current retention policy. | Preserve references subject to a ratified retention/resolver policy; permanent resolution is not implemented or authorized. |

## 7. What is contradicted by the repository

1. **The report says its compatibility freeze is immediately binding.** The Wave-2 backlog
   says the freeze is a research guard, not a final code contract, and the report itself
   forbids use as an authority grant.
2. **The report's common envelope implies one new support status owner.** The repository
   already has:
   - capability authority: `admissible | limited | contested | blocked`;
   - claim support: `unsupported | weakly_supported | supported | contested`;
   - decision validity/lifecycle: `active`, `warning`, `stale`, `human_review_required`,
     `superseded`, `reissued`, `withdrawn`, `revoked`;
   - purpose-scoped `AuthorityBoundary`.
3. **The report treats PDC placement as established.** The PDC README limits authority to
   `pdc_graph_structure`, and PDC is absent from the stable public-package registry.
4. **The report describes Atlas as projection-only without qualification.** The active plan
   states that `PublicSectorReadinessPanel` and `ScientificDepthPanel` mint values the
   runtime never produced; current code computes `approvalReady` locally.
5. **The report attributes legal source/version production to Lex.** The public-surface
   contract assigns offline legal preprocessing to Data Forge; Lex is the stable runtime
   facade and consumer.
6. **The report calls `run-24` and `lineage_fixture_001` reusable fixtures.** They are string
   literals inside named unit tests.
7. **The report's failure-pattern labels do not match the exact register.**
8. **The report implies public export plumbing is ready for extension.** The existing
   tenant-private-reference redaction test is red at both baselines.
9. **The report says `honest-diagnostics-substrate.md` was represented by a renamed
   decision-log path.** Both files exist: the former is the source draft design decision;
   the latter is a distinct append-only implementation-decision log that points back to it.

## 8. What became stale after the research SHA

Nothing. Baseline A equals Baseline B exactly. No file, contract, test, plan, ADR, or owner
record changed between the report's historical commit and the pinned current `main`.

Any incorrect current-state statement was already incorrect or overstated at the historical
SHA; none became wrong because of later repository evolution.

## 9. Internal contradictions in the research

The report's frontmatter and contract sections say:

- `research_only: true`;
- `may_not_use_for: authority grant`;
- `may_not_use_for: final code contract`;
- `may_not_use_for: production migration authorization`;
- sketches are `candidate_for_consolidation`.

Appendix D nevertheless says `Standing: Immediately binding as a Stage-0 research guard` and
marks every PMF row “Yes” under “Binding now.” The distinction between “research guard” and
“authority grant” is not operationally meaningful if the artifact purports to stop current
work, compel fields, assign an owner, or prohibit a package decision.

The report also says the proposed outcomes are “not a second publication or authority
lattice,” then places `authoritative`, `corroborated`, `contested`, `unresolved`, and
`revoked` in a common `support_status`. That field crosses the exact boundaries the prose
claims to preserve.

Finally, the report correctly leaves case-to-many-matter support, federation, transfer,
granularity, and competence open, but its PMF rules simultaneously freeze multi-matter
attachment, namespace design, transfer-compatible origin fields, split/merge IDs, and
subject closure.

## 10. Boundary and authority audit

The **function-level OWN verdict is confirmed** because the ratified identity decision says
`PolicyMatter identity above a single case` is “OWN, now.” The report is also right that
legal succession, formal continuity, public-registry assertions, institutional transfer,
and jurisdiction-specific legal effect generally arrive as typed external evidence.

That ruling does not prove:

- a Python package owner;
- a wire identifier format;
- an origin-tenant invariant;
- competence rules for a jurisdiction;
- a split/merge allocation rule;
- a public resolver;
- a status enum;
- an operational producer;
- an implemented capability.

The appropriate authority split is:

| Function | Standing |
| --- | --- |
| Stable technical reference for PolicyOS's own custody | Ratified OWN function. |
| Binding a PolicyOS artifact/case to that reference | Candidate OWN function; contract and owner unresolved. |
| Legal/sovereign continuity or succession | INTEGRATE typed external evidence; jurisdiction-specific competence unresolved. |
| Candidate matching and contradiction detection | Internal diagnostic/candidate-only. |
| Evidence applicability after continuity | Existing evidence-scope owners decide; identity grants nothing. |
| Administrative program, payments, eligibility, citizen case files | Out of scope or integrate/observe as already ruled. |

## 11. Canonical-owner and P27 audit

| Candidate responsibility | Documented/actual owner today | Audit conclusion |
| --- | --- | --- |
| PDC graph structure | `polisyos.pdc`, `team-policyos-runtime`; authority only for graph structure | Strong semantic neighborhood; not proof of matter identity ownership. |
| Shared DTO/ABI and provenance refs | `polisyos.core.contracts` | Must participate if a cross-package wire contract is proposed. |
| Runtime validation/adaptation | `polisyos.runtime.quality` | Plausible bridge/validator, but cannot create producer authority by itself. |
| Content persistence and signatures | `polisyos.core.artifacts` | Existing CAS/signing owner; not real-world identity owner. |
| Portable audit packaging | `polisyos.core.audit` | Verifier/export owner; not semantic event owner. |
| Technical artifact lineage | `polisyos.ir.artifacts` | Reusable technical dependency substrate, not matter semantics. |
| Legal source/version build | `polisyos.data_forge.domains.legal` | Offline producer. |
| Legal runtime selection/evaluation | `polisyos.lex` | Runtime consumer/evaluator and legal evidence source. |
| Incidents/readiness/shift evidence | DDM/Scientist | Event/evidence producers, not identity adjudicators. |
| Current/public projection | runtime HTTP/Atlas | Consumers only by doctrine; known implementation debt remains. |
| H2 custody runtime | Horizon/plan concept, not a current package owner | Consumer designation is a proposal. |

The report's owner conclusion should be replaced with:

> The repository establishes an OWN function and identifies PDC lineage as a later
> integration target. It does not ratify a package-level canonical owner. Consolidation must
> compare extension of PDC, placement of shared ABI in `core.contracts`, and any narrowly
> justified new semantic owner under P27 before contract freeze.

## 12. Identifier and lineage census

The census searched the entire tracked `policy-engine/` tree at both baselines, excluding
only `.venv`, `node_modules`, and `_build`. Because both Git trees are identical, counts are
the same.

| Term | Files | Actual semantic finding |
| --- | ---: | --- |
| `PolicyMatter` | 2 | Ratified identity decision and Wave-2 research backlog only. |
| `policy_matter` | 0 | No source/schema/API/test implementation. |
| `matter_id` | 0 | No implementation. |
| `matter_ref` | 0 | No implementation. |
| `subject_ref` | 8 | Mostly Lex/knowledge or `subject_reference` substrings; no matter identity. |
| `policy_id` | 201 | Highly overloaded owner-local identifier. |
| `case_id` | 593 | Case/governance/lifecycle/projection identity; not globally self-scoping. |
| `decision_lineage_key` | 22 | Decision validity lineage; raw store key is not tenant-qualified. |
| `run_id` | 1,217 | Runtime execution identity and dominant route/cache key. |
| `job_id` | 283 | Operational job identity. |
| `graph_id` | 73 | Several graph identities; PDC graph ID is derived from `run_id`. |
| `artifact_id` | 1,090 | Content-addressed artifact identity. |
| `portfolio_id` | 38 | Candidate portfolio/evidence-local meanings. |
| `release_id` | 23 | Release/version identity. |
| `epoch_id` | 12 | Epistemic/acquisition/calibration epoch. |
| `tenant_id` | 321 | Security/ownership scope, not yet a federated semantic identity model. |
| `jurisdiction` | 635 | Applicability/legal/context scope; multiple owners. |
| `valid_at` / `tx_at` | 102 / 81 | Canonical runtime bitemporal cursor vocabulary. |
| `admitted_at` | 1 | Not a current cross-repository canonical clock. |

Negative finding protocol:

- exact terms included all report-requested case/snake/camel variants;
- paths searched: tracked repository source, tests, docs, fixtures, schemas, generated clients,
  dashboard, migrations, architecture manifests, and Git history at the pinned tree;
- exclusions: environment/build dependency trees only;
- confidence: high for the tracked Git trees;
- blind spots: external databases/services, ignored generated runtime outputs, encrypted or
  binary artifacts, and behavior requiring unavailable optional dependencies.

The report missed generic `subject_id` and `subject_reference` primitives. Those are
underclaims in its inventory, not a hidden lifetime policy identity: they lack the asserted
custody, non-reassignment, episode, and legal-succession semantics.

## 13. Capability-reality audit

| Capability chain element | Actual state | Evidence-backed qualification |
| --- | --- | --- |
| Typed `PolicyMatter` contract | `planned_only` / `documented_only` | Name appears only in decision/backlog. |
| Matter identifier producer | `producer_missing` | No generator or governed registry. |
| Case-to-matter artifact | `artifact_missing` | No schema or persisted kind. |
| Matter admission bridge | `bridge_missing` | Runtime quality has no matter adapter. |
| Matter-aware consumer | `consumer_missing` | PDC, H2, validity, and DDM do not consume it. |
| Matter semantic verification | `verification_missing` / `semantic_test_missing` | Proposed fixture catalogue is not implemented. |
| Matter API/public surface | `surface_missing` | No route, OpenAPI field, client field, or dashboard query. |
| PDC runtime graph | `implemented` | Graph structure only; run/job/tenant context. |
| PDC record-family completeness | `implemented` | Typed records defeat a status-only pass; no matter semantics. |
| CAS/manifests/signatures | `implemented` | Content integrity and tenant ownership; not real-world identity. |
| Technical artifact lineage | `implemented` | Artifact/task dependency relations only. |
| Legal version index | `implemented` | Data Forge producer, Lex runtime selection; document identity only. |
| Decision validity | `implemented_but_not_orchestrated` for broad custody | Decision-scoped; no generic payload-vs-authority impact sets or tenant-qualified lineage key. |
| Claim lifecycle/reissue | `implemented` at claim/case scope | Strong append-only precedent; no matter correction chain. |
| Portable audit | `implemented` for artifacts/runs | No matter semantic verifier. |
| Atlas matter projection | `surface_missing` | Projection doctrine exists; matter graph does not. |
| Public correction fan-out | `planned_only` | Assigned to PAO-R36. |

The report's aggregate label should therefore be:

> `planned_only + producer_missing + artifact_missing + bridge_missing +
> consumer_missing + verification_missing + surface_missing`, with reusable implemented
> fragments that remain semantically narrower.

## 14. Temporal and replay audit

| Proposed clock | Existing repository meaning/owner | Audit disposition |
| --- | --- | --- |
| Event time | `occurred_at`/source events in several domains; OPS-R4 owns consolidation | Preserve concept; do not freeze field name here. |
| Valid time | `TemporalRef.valid_at`, Fabric bitemporal facts | Existing canonical concept. |
| Effective time | Lex/legal and runtime temporal envelope | Existing but domain-specific; consolidate in OPS-R4. |
| Transaction time | `TemporalRef.tx_at`, Fabric transaction history | Existing canonical concept. |
| Publication time | Legal source and public records use variants | Required only where publication occurs; not a universal field. |
| Observation time | Runtime `TimeSourceEnvelopeAudit.source_observed_at` and producer events | Existing concept; OPS-R4 must align it. |
| Admission time | Named by OPS-R4; nearly absent in implementation | Planned, not canonical. |
| Correction time | Usually derivable from a correction event's recorded/transaction time | Do not invent a separate universal clock without proof. |
| Supersession time | Usually lifecycle relation + effective/recorded time | Treat as event/relation unless OPS-R4 proves a separate clock. |

The repository already has `TemporalScope(valid_at, tx_at, branch, snapshot_id,
scenario_id)` and a broader runtime `TimeSourceEnvelopeAudit`. The report's new common
envelope duplicates these shapes and names `recorded_at` where canonical runtime DTOs use
`tx_at`/`transaction_time`.

Safe Stage-0 wording:

> Do not collapse legally effective, source-observation, system-recording, and public
> publication time where they differ. Preserve enough event history to reconstruct both
> valid-world and as-recorded views. OPS-R4 owns the canonical vocabulary and determines
> which roles are fields, event attributes, or derivable projections.

Historical replay of matter identity cannot be claimed. Existing Fabric and runtime temporal
tests prove narrower valid/transaction behavior; current PDC graphs and public routes are
run-oriented and contain no matter association.

## 15. Tenant, namespace, and security audit

Established:

- shared CAS blobs are global content hashes;
- ownership claims are stored separately per tenant/cell;
- a tenant cannot read another tenant's artifact without its own ownership claim;
- identical bytes intentionally have the same `ArtifactID` across tenants;
- route and policy layers contain tenant checks.

Not established:

- an immutable `origin_tenant_id` as part of real-world policy identity;
- a federated issuer namespace;
- cross-tenant matter equality;
- transfer of matter custody without identity change;
- institution-to-tenant mapping;
- tenant-safe `decision_lineage_key` persistence;
- public/private matter-ID disclosure policy.

Two concrete probes matter:

1. `DecisionValidityStateStore._lineage_path()` hashes only the raw
   `decision_lineage_key`. Two tenants using the same local store and same raw key resolve to
   the same file unless callers manually qualify the key.
2. The existing test
   `test_public_export_redacts_tenant_private_runtime_refs_from_payload_and_projection`
   fails because a raw private CAS reference remains in serialized output.

This does not prove that current CAS read authorization permits cross-tenant data access; the
separate cross-tenant CAS test passes. It does prove that the report cannot treat namespace,
cache, public projection, and transfer safety as ready primitives.

## 16. Contract-sketch critique

### Common envelope

The envelope is too broad to freeze. It combines:

- CAS/artifact references owned by core artifacts/contracts;
- tenant and cell scope owned by security/CAS;
- jurisdiction and applicability owned by legal/capability owners;
- bitemporal fields owned by runtime/Fabric and future OPS-R4 consolidation;
- provenance already modeled in core contracts;
- `AuthorityBoundary` already modeled in PDC;
- a new support/lifecycle/identity status grammar.

The correction is not to create a larger cross-owner struct. A future matter family should
reference canonical envelopes or compose owner-specific contracts, with one explicit mapping
for each reused field.

### `PolicyMatter`

Safe as a research noun and opaque accountability-anchor hypothesis. Premature fields:
`origin_tenant_id`, `origin_jurisdiction_context_ref`, fixed namespace rules, permanent
indexes, and assumed PDC placement.

### `PolicyMatterEpisode`

Useful research distinction, but `lifecycle_class`, `episode_type`, and
`authority_consequence` are unfrozen vocabularies. The report mixes administrative,
institutional, implementation, epistemic, and public-record events under one contract while
saying those lifecycles remain distinct.

### `PolicyMatterLineageAssertion`

Reification, provenance, correction linkage, source/target typing, and explicit permitted
uses are strong candidate requirements. The single `identity_effect` and `support_status`
fields are premature: relation type, authority boundary, resolution result, evidentiary
support, and lifecycle validity must remain separate.

### Identity-resolution receipt

Legitimate candidate audit artifact if it is strictly diagnostic and cannot grant identity.
Its `proposed_outcome` belongs to resolution diagnostics, while an admitted lineage assertion
must come from a separate competent producer.

## 17. Compatibility-freeze audit

No PMF rule becomes binding because PAO-R0 says so. The table below classifies its substance:

| PMF | Standing classification | Audit note |
| --- | --- | --- |
| 01 | Already binding because it restates a ratified repository invariant | Identity is explicitly above a case. |
| 02 | Defensible temporary compatibility advice | Decision lineage is narrower, but no formal redesign/freeze exists. |
| 03 | Mixed: PolicyPortfolio separation is established; generic `policy_id` wording is advice | Do not imply one global rule for all `policy_id` owners. |
| 04 | Proposed Stage-0 constraint requiring explicit acceptance | Extensible matter refs would change new schemas. |
| 05 | Speculative design choice | Opaque/non-reassignable is strong PID advice, not ratified wire contract. |
| 06 | Proposed Stage-0 constraint requiring explicit acceptance | Issuer namespace/federation unresolved. |
| 07 | Already binding for existing tenant/legal authority boundaries; too broad as a future matter schema | Preserve current boundaries; defer field shape. |
| 08 | Speculative design choice | Immutable origin/current custodian split is unratified. |
| 09 | Proposed Stage-0 constraint requiring explicit acceptance | One-to-many is plausible but not implemented. |
| 10 | Unresolved research question / premature schema constraint | Report itself leaves multi-matter cases open. |
| 11 | Repository-consistent recommendation, not canonical rule | Split/merge identity allocation is jurisdiction/product dependent. |
| 12 | Repository-consistent recommendation | Legal instruments already permit broad structures, but matter cardinality is unimplemented. |
| 13 | Existing typed/provenance invariant plus proposed matter schema | The generic principle binds; artifact family does not. |
| 14 | Already binding authority invariant | Similarity/LLM output cannot mint authority. |
| 15 | Proposed resolution capability; mapping unresolved | Represent diagnostics without adding a second status lattice. |
| 16 | Already binding append-only/CAS/replay invariant | Scope-specific correction contract remains open. |
| 17 | Premature schema constraint | Pre-empts OPS-R4; preserve semantic distinctions only. |
| 18 | Already binding integrity invariant | Historical signed bytes cannot be mutated without invalidating identity/signature. |
| 19 | Proposed retention/resolver constraint | “Remain resolvable” is not guaranteed permanently by current retention policy. |
| 20 | Defensible compatibility advice | Existing bitemporal doctrine supports it; matter projection is absent. |
| 21 | Already binding evidence-scope invariant | Existing transportability/applicability owners already enforce separation. |
| 22 | Repository-consistent recommendation | Parent-history retention is strong but exact identity rules remain open. |
| 23 | Existing tenant isolation plus unresolved federation rule | Do not generalize artifact-ID equality; identical content IDs intentionally cross tenants. |
| 24 | Already binding projection doctrine; current implementation debt exists | It cannot be cited as proof of full compliance. |
| 25 | Already established by ADR-0022 semantics | PolicyPortfolio is candidate composition. |
| 26 | Owner not established | Requires explicit P27 owner review. |
| 27 | Speculative owner/product decision | H2 is a horizon, not a current canonical subsystem. |
| 28 | Planned only / proposed Stage-0 constraint | PAO-R36 owns fan-out research. |
| 29 | Premature schema/closeout constraint | No canonical matter subject closure or status mapping exists. |
| 30 | Defensible identifier-design advice | Should remain a candidate until identifier governance is accepted. |

The replacement compatibility packet appears in
[`pao-r0-recommended-revision.md`](pao-r0-recommended-revision.md).

## 18. Benchmark and fixture audit

The proposed synthetic corpus and metamorphic properties are valuable research design, but
none is a current repository fixture. The exact findings are:

- `run-24` is a string literal in
  `test_runtime_policy_design_case_compiler.py`, not a fixture ID or reusable corpus.
- `lineage_fixture_001` is a string literal in
  `test_decision_validity_service.py`, not a named fixture object.
- PDC compiler, projection, anti-laundering, and record-family tests exist and are reusable
  as test **patterns**.
- tenant/CAS, recall/retraction, decision-validity law-change/legacy, partial reissue,
  lifecycle bridge, legal version selection, runtime lineage, audit export, and
  PolicyPortfolio test families exist.
- most are function-local builders; none proves PolicyMatter semantics.
- PolicyPortfolio tests are useful negative conceptual evidence but do not assert
  “portfolio is not deployed identity.”
- runtime lineage tests could not be collected in the audit environment because `jaxlib`
  was unavailable through an eager import chain.

The benchmark should be promoted only after its ground truth is produced independently,
sealed, and tested against a generic property-based validator. Otherwise it risks P29
(authorial proof) and P33 (witness-as-spec).

## 19. External citation-quality audit

| Report source/use | Result | Required correction |
| --- | --- | --- |
| W3C PROV | Official primary source supports domain-neutral provenance, not policy sameness. | Keep, narrow to provenance semantics. |
| OASIS Akoma Ntoso | Official primary source supports legal-document structure/identity/versioning. | Keep; do not infer policy identity. |
| ELI, PREMIS, RiC-O, RFC 7089 | Official/primary sources match their bounded uses. | Keep with precise, non-universal wording. |
| DataCite relations | Official page supports version/continuation/part relations and steward-defined semantics. | Keep. |
| ARK | Official ARK material supports persistence/opaque-reference recommendations. | Keep as an analogy, not a proof of PolicyOS rules. |
| “DOI Foundation guidance” | The supplied URL points to ARK Alliance, not DOI Foundation. | Replace with the official DOI Handbook/DOI Foundation source or relabel as ARK. |
| Bitemporal research | Report cites ResearchGate. | Replace with the underlying primary IEEE/ACM publication or author technical report. |
| Fellegi–Sunter/Sadinle | Publisher/primary research supports uncertain linkage. | Keep; do not equate statistical labels with legal authority. |
| GLEIF events | GLEIF supports legal-entity event histories. | Cite the official Legal Entity Events policy/model rather than an L1 landing page. |
| Federal Program Inventory | Official source supports program listing and acknowledges alignment/data-quality limits. | Keep as bounded external-registry evidence. |
| “No single pattern exists” | Absolute universal negative is not supportable. | Say “No single pattern was identified in the enumerated review corpus.” |

Targeted external verification was available. It was limited to citation support and source
quality, not a comprehensive global survey of policy registries or jurisdictional law.

## 20. Promotion/kill-rule critique

The report's conservative promotion direction is sound, but several rules assume the very
contract they are meant to gate. Correct promotion sequencing should be:

1. Ratify scope and owner before package/schema placement.
2. Consolidate temporal vocabulary with OPS-R4.
3. Map relation, resolution, support, authority, and lifecycle semantics without adding a
   parallel lattice.
4. Ratify namespace/tenant/federation and competence models.
5. Build an independently adjudicated semantic benchmark.
6. Prototype on synthetic data only.
7. Prove the complete capability chain and public correction path.
8. Rehearse additive migration without changing old bytes.

Kill rules that already follow from current repository authority can remain:

- no similarity or projection authority;
- no silent history rewrite;
- no evidence transport from identity continuity;
- no bypass of tenant isolation;
- no PolicyPortfolio reinterpretation;
- no new owner without P27 review.

Kill rules that must remain proposals include mandatory ID form, split/merge allocation,
multi-matter case cardinality, permanent resolver obligations, PDC placement, and required
clock fields.

## 21. Recommended final PAO-R0 posture

PAO-R0 should be frozen only as a **research compatibility packet**, not a contract or
authority-bearing freeze:

> The repository confirms the need for a stable PolicyOS custody identity above a case and
> confirms that current identifiers do not collectively implement it. A `PolicyMatter`
> remains a candidate opaque accountability anchor. Existing identifiers must not be
> retroactively reinterpreted; similarity and projections must not create identity
> authority; historical CAS/signed bytes must remain unchanged; and identity continuity
> must not grant evidence applicability. Package owner, common contract, temporal fields,
> namespace/federation, split/merge allocation, case cardinality, competence, public
> correction, and status mapping remain open for PAO-R1/OPS-R4/OPS-R15/INT-R5/INT-R7/
> INT-R8/PAO-R36 consolidation.

The source result `accepted_narrow_scope` should be changed to
`confirmed_with_material_revisions` for the audited revision.

## 22. Required changes before Stage-0 freeze

1. Remove all “immediately binding” and “Binding now: Yes” language.
2. State that only separately ratified repository invariants are already binding.
3. Replace the PDC owner conclusion with an explicit P27 consolidation question.
4. Change matter capability state from `contract_only` to `planned_only/documented_only`.
5. Remove the common `support_status` and map each concept to existing status/authority
   owners.
6. Replace nine mandatory clocks with a semantic non-collapse constraint owned by OPS-R4.
7. Correct every failure-pattern ID/title and add P04 for lattice risk.
8. Replace fixture claims with exact paths and test symbols; label literals accurately.
9. Split legal version ownership into Data Forge producer and Lex runtime consumer.
10. Distinguish Atlas projection doctrine from acknowledged current implementation debt.
11. Make tenant origin, custody transfer, issuer federation, and public namespace explicitly
    unratified.
12. Qualify split/merge/new-ID and reenactment defaults as jurisdiction/product questions.
13. Integrate transportability, applicability, capability scope, legal authority, evidence
    independence, and decision-validity contracts by reference instead of duplicating them.
14. Limit sidecar correction to a non-rewrite technique; do not call it sufficient before
    PAO-R36/INT-R7 prove fan-out, cache, API, archive, and key-rotation behavior.
15. Replace absolute external negative claims and fix the DOI/ARK and ResearchGate citations.
16. Record the current public-export redaction failure and tenant-blind lineage-key risk as
    blockers for any governed prototype.

## 23. Open questions for PAO-R1, OPS-R4, OPS-R15, INT-R5, INT-R7, INT-R8, and PAO-R36

| Task | Questions that must remain open |
| --- | --- |
| PAO-R1 | Which identity functions are OWN vs INTEGRATE; who is competent to assert what; which package owns the canonical technical reference? |
| OPS-R4 | Canonical time-role algebra; event vs field; correction/supersession representation; late/retroactive semantics; clock naming. |
| OPS-R15 | Whether one case can bind multiple matters and at what scope; capstone fixtures; clean rebuild; long-cycle custody behavior. |
| INT-R5 | Competence, delegation, conflicts, review mandate, and limits of a PolicyOS human adjudicator. |
| INT-R7 | Signature/key rotation, archival verification, correction sidecars, resolver retention, and verification after key revocation. |
| INT-R8 | Public representation of uncertainty/contestation and compression without changing authority. |
| PAO-R36 | Matter-aware correction fan-out, API supersession, cache invalidation, notification, translation parity, and archive linkage. |
| OPS-R2 | Payload-recompute vs authority-revalidation sets and completeness of dependency registration. |
| OPS-R14 | Namespace, alias, resolver, correction-history, and disaster-recovery custody. |

## 24. Commands and verification results

Key results:

| Command/probe | Baseline | Result |
| --- | --- | --- |
| `git ls-remote origin refs/heads/main` plus GitHub compare | A/B | Same SHA; compare `identical`. |
| `python3 -m tools.cli workspace bootstrap` | B | Failed: system Python lacks `click`. |
| `python3 -m tools.cli workspace doctor` | B | Failed: system Python lacks `click`. |
| Doctor under temporary Python 3.14 environment | B | Python/uv/lock pass; Node version, Playwright browser, corepack cache, Pillow sync, OpenAPI/frontend checks fail or block. |
| PDC README command | B | Frozen dependency sync blocked by Pillow 10.4.0/JPEG build availability. |
| `pytest ... test_runtime_policy_design_case_compiler.py` | B | 4 passed. |
| `pytest ... test_policy_design_case_projection_semantics.py` | B | 37 passed. |
| Targeted nine-file fixture/capability batch | B | 54 passed, 1 failed (public-export redaction). |
| `pytest ... tests/unit/pdc` under audit-only import shim | B | 122 passed, 1 shim-induced failure. |
| DDM facade/readiness subset | B | 4 passed. |
| Signing/store-signing/audit round-trip subset | B | 3 passed. |
| Runtime HTTP lineage subset | B | Collection blocked: `jax` requires unavailable `jaxlib`. |
| Architecture import/public-surface/facade subset | B | 2 passed, 2 failed; import exceptions expired and public-surface snapshot drift exists. |
| Documentation gate/lifecycle subset | B | 31 passed, 2 failed on pre-existing stale path references and an expired docs-freshness exception baseline. |
| Raw decision-lineage key path probe | B | Identical key resolves to identical file path; store API has no tenant parameter. |
| PDC subject-cardinality probe | B | No subject/matter fields; `extra="forbid"`; graph cannot currently carry a matter ref. |

All dynamic execution occurred on Baseline B. Because A and B are the same tree, code and
test definitions are identical, but environment-dependent runtime outcomes were not
duplicated in a second checkout.

See
[`pao-r0-test-and-fixture-verification.md`](pao-r0-test-and-fixture-verification.md)
for exact commands, symbols, outputs, audit relevance, and blockers.

## 25. Limitations of this audit

- The supplied report was audited from task context; it was not present as a committed
  repository file.
- Full dependency bootstrap was blocked by the environment's system Python and Pillow/JPEG
  build availability.
- Runtime HTTP tests were blocked by unavailable `jaxlib`; no claim is made that those tests
  pass or fail.
- Some targeted tests used an explicitly documented import shim outside the repository to
  avoid unrelated eager imports. A shim-induced PDC failure was excluded from repository
  findings.
- No production service, database, deployed cache, external registry, or tenant federation
  was available. Static namespace findings therefore identify risk, not an observed
  cross-tenant incident.
- External citation review was targeted, not a systematic review of every jurisdiction or
  identifier system.
- Exact semantics of sovereign policy continuity require jurisdiction-specific legal and
  institutional evidence outside this repository.
- Absence findings cover tracked Git content at the two identical pinned baselines; they do
  not prove absence in external systems, ignored runtime data, or future branches.
