---
title: "PAO-R0 — Policy Matter Identity and Episode Graph"
status: delivered
kind: deep-research
research_task: PAO-R0
result_type: accepted_narrow_scope
repository: "https://github.com/DenisKopylov/polisyos"
repository_branch: main
repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
inspection_date: 2026-07-26
authoritative_for:
  - research findings on stable PolicyMatter identity
  - candidate episode and lineage semantics
  - PolicyMatterCompatibilityFreeze research guard
may_not_use_for:
  - capability claim
  - authority grant
  - final code contract
  - production migration authorization
  - automatic identity adjudication
  - administrative case-management ownership
research_only: true
---

# PAO-R0 — Policy Matter Identity and Episode Graph

## Executive Finding

**Boundary verdict: OWN, with explicit INTEGRATE edges.** PolicyOS must own the stable technical identity and custody graph that lets it determine which of its own signatures, claims, cases, corrections, supersessions, and withdrawals concern the same continuing policy. It must not, however, silently make sovereign or legally effective policy-identity determinations: formal continuity, legal succession, institutional transfer, split, merger, and reenactment evidence generally originates with competent external authorities and enters through typed, fail-closed evidence contracts. This extends, rather than reopens, the ratified ruling that PolicyMatter identity above a single case is an OWN function because otherwise PolicyOS cannot know which of its public signatures remains current.

**Recommended narrow-scope result.** A `PolicyMatter` should be a stable, opaque, non-reassignable **accountability and justification-custody identity for one lineage-bearing public-authority intervention commitment**. It is the referential anchor under which PolicyOS preserves continuity and separation across multiple design cases, decisions, legal instruments, implementation episodes, evaluations, incidents, institutional owners, and public records. It is not an assertion that all those objects are versions of one another, nor does sameness of matter make evidence automatically transferable across changed populations, mechanisms, objectives, or jurisdictions.

**Main identity principle.** The stable thing is **not an immutable tuple of policy name, agency, instrument, objective, population, mechanism, budget, or territory**. All of those can change, and several unrelated policies can share them. What remains stable is:

1. the opaque identity anchor and its issuer namespace;
2. the non-reassignable creation and custody history;
3. the append-only set of provenance-bearing assertions that establish, contest, correct, split, merge, succeed, or terminate continuity;
4. the preserved distinction between matter identity and the scope in which evidence remains applicable.

This follows the same separation found in mature identifier, provenance, legal-document, archival, and temporal standards: identifiers preserve reference, provenance preserves derivation, and temporal models preserve historical views, but none of them independently proves that two public interventions are “the same policy.” ([DataCite Support][1])

**Main unresolved risk.** No universal, jurisdiction-neutral automatic rule can decide policy sameness through all material objective, mechanism, population, authority, and institutional changes. That boundary is partly legal, institutional, and normative. Automated matching can produce candidate hypotheses and contradiction packets; it cannot confer authoritative identity. Material cases therefore require competent external evidence or delegated human adjudication.

**Stage-0 freeze verdict: supportable now.** The repository already has reusable PDC, CAS, lineage, audit, Lex versioning, decision-validity, append-only reissue, temporal-query, tenant-boundary, and Atlas projection primitives. What is absent is the semantic matter identity, its typed association and lineage assertions, the migration bridge, and adversarial tests. The freeze can therefore be adopted immediately as a research guard without claiming implementation.

The task specification used for this report is the supplied PAO-R0 research brief.

---

# 1. Task And Project Fit

## 1.1 Source task

| Field | Value |
|---|---|
| Backlog | Custody & Operations — Parallel Deep Research Backlog |
| Wave | Wave 2, Rev 2 |
| Task | PAO-R0 |
| Group | Group C — Boundary & Identity |
| Priority | Stage-0 bootstrap anchor |
| Owner | `team-architecture` |
| Suggested later path | `policy-engine/docs/research/policy-operations/pao-r0-policy-matter-identity-and-episode-graph.md` |
| Deliverable standing | Research only; no repository modification |

Wave 2 explicitly separates lifetime custody from Wave-1’s single-case machinery and identifies PAO-R0, PAO-R1, and OPS-R15 as bootstrap anchors before the remaining tasks are parallelized.

## 1.2 Exact research question

> What stable identity should exist above a single Policy Design Case so that a PolicyMatter survives pilots, enactment, scaling, renaming, successor instruments, institutional transitions, splits, mergers, corrections, evaluations, incidents, and public-record changes without silently merging unrelated initiatives or breaking historical continuity?

## 1.3 Why this is research-first

The repository already supports strong fragments around one case and its artifacts, but introducing a lifetime identity is not a local schema addition. It determines:

- what counts as continuing the same public signature;
- which evidence and incidents may be attached to which policy;
- how invalidation and correction fan out;
- whether a split inherits evidence;
- whether a successor instrument preserves or breaks continuity;
- how signed historical artifacts remain interpretable;
- whether public records can be corrected without rewriting history.

Encoding the wrong granularity early would be difficult to reverse because `case_id`, `decision_lineage_key`, public URLs, cache keys, audit records, and signed artifacts could become implicit lifetime identifiers.

## 1.4 False production claim prevented

The task prevents this false claim:

> PolicyOS maintains lifetime custody of policy justification, while it actually tracks only isolated runs, cases, decision packets, or legal-document versions and cannot prove which continuing real-world policy a signature concerns.

The governing decision states that PolicyOS owns everything it signs for while the signature publicly stands and must preserve revalidation, reissue, supersession, correction, withdrawal, and historical provability.

## 1.5 Four-way boundary adjudication

| Function | Verdict | Reason |
|---|---|---|
| Stable PolicyOS matter identifier | **OWN** | Without it, PolicyOS can silently continue, correct, or withdraw the wrong signature. |
| Case-to-matter custody association | **OWN** | It determines which PolicyOS artifacts and claims are affected by later events. |
| PolicyOS lineage assertion and correction history | **OWN** | It is part of PolicyOS’s own public justification custody. |
| Legal succession, governmental merger, formal continuity declaration | **INTEGRATE** | External competent institutions determine legal or sovereign effect; PolicyOS owns the typed evidence interface. |
| External administrative program registry | **INTEGRATE** | Registry identifiers and records are evidence, not PolicyOS’s own master data. |
| Institutional responsibility where claim validity is unaffected | **OBSERVE** | It identifies accountability but may not change epistemic validity. |
| Applications, payments, notices, service delivery and citizen case files | **OUT_OF_SCOPE** | These are administrative anti-roles under the ratified boundary. |

The identity decision expressly rejects expanding PolicyOS into a public administrator, case-management system, court, payment system, notification channel, CRM, or general ERP.

## 1.6 Relationship to PAO-R1 and OPS-R15

- **PAO-R1** should consume this report’s distinction between PolicyOS-owned technical identity and externally supplied sovereign identity evidence. PAO-R1 remains responsible for applying the four-way test function by function.
- **OPS-R15** must use `PolicyMatter` as the top-level identity vocabulary for its 18–24 month custody-cycle benchmark. A case may suspend, resume, migrate, or close, while the matter continues.
- **PAO-R0 does not settle** the durable workflow, invalidation scheduler, world-release, public-correction, or resilience contracts. It states the identity assumptions those contracts must preserve.

---

# 2. Current Repo Baseline

## 2.1 Inspection record

| Item | Finding |
|---|---|
| Repository | `https://github.com/DenisKopylov/polisyos` |
| Branch inspected | `main` |
| Commit | `4813b49f6ce14e8debf3aaea096f0967d38d9768` |
| Inspection date | 2026-07-26 |
| Repository layout | Most requested paths are under the `policy-engine/` project root. |
| Renamed path | The requested `honest-diagnostics-substrate.md` was represented by `docs/system-design-decisions/honest-diagnostics-substrate-decision-log.md`. |
| Search method | Commit-pinned GitHub repository search and direct file retrieval across requested identifiers and concepts. |
| Search limitation | A local clone and `rg` pass were attempted but could not complete because the execution environment could not resolve GitHub. Negative search findings are therefore high-confidence connector-search findings, not claims of mathematically exhaustive absence. |
| Modification status | No repository files were changed. |

The inspected commit is the repository revision that ratified the identity/custody boundary and reshaped Wave 2.

## 2.2 Inspected paths

The baseline covered:

- `AGENTS.md`;
- `policy-engine/CONTRIBUTING.md`;
- `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md`;
- the universal vision, target architecture, operating model, diagnostics decision log, and north-star decisions;
- `docs/reference/policy-design-case-failure-patterns.md`;
- Wave-1 backlog and distillation;
- Wave-2 backlog;
- retention and recovery;
- GY and Atlas active plans;
- `src/polisyos/pdc`;
- `src/polisyos/runtime/quality`;
- `src/polisyos/core/audit`;
- `src/polisyos/core/artifacts`;
- `src/polisyos/ir/artifacts`;
- `src/polisyos/lex`;
- legal-corpus versioning;
- `src/polisyos/ddm`;
- Scientist continuous-governance lifecycle/reissue code;
- PolicyPortfolio IR and ADR-0022;
- representative unit, semantic, replay, governance, and projection tests.

The repository’s own architecture discipline requires reuse-first ordering and a complete producer → artifact → bridge → consumer → verification → surface chain before a capability is considered real.

## 2.3 Existing primitives

### 2.3.1 PDC graph and typed authority waist

`src/polisyos/pdc` is the closest canonical owner. It exposes a runtime PDC graph, authority boundaries, promotion references, artifacts, claims, warrants, deficits, and projection sources. The current graph is tied to `run_id`, optional `job_id`, and `tenant_id`; its documented authority is structural PDC graph authority, not lifetime policy identity. The projection remains explicitly projection-only, and an LLM candidate cannot be laundered directly into the graph.

### 2.3.2 PDC runtime record families

The PDC registry already requires typed record families for legal authority, semantic lineage, implementation, monitoring, evaluation, lifecycle, human oversight, and publication. A simple `"status": "pass"` is insufficient; missing record families block closeout.

This is a suitable authority waist to extend. It is not evidence that a lifetime matter identity already exists.

### 2.3.3 Content-addressed artifacts

`ArtifactID` is a stable `sha256:` content address used in manifests, runtime URLs, CLI arguments, and signature statements. It identifies bytes, not a continuing real-world policy.

Artifact manifests are immutable and already preserve schema, direct inputs, producer, environment, governance, tenant context, same-input closure, authority references, and integrity metadata.

### 2.3.4 Technical artifact lineage

The IR artifact lineage graph represents artifact and task nodes with `produced_by`, `consumed_by`, `derived_from`, and `invalidated_by` relations. It is valuable for technical dependencies, but it does not contain policy-matter, legal-succession, split, merger, institutional-transition, or public-accountability semantics.

### 2.3.5 Runtime lineage surface

The runtime lineage API already supports tenant enforcement, `valid_at`, `tx_at`, branch/snapshot/scenario context, audit recording, PROV/OpenLineage exports, and fail-closed surface admission. This is reusable projection and export plumbing, not the canonical source of PolicyMatter semantics.

### 2.3.6 Decision validity

The decision-validity subsystem tracks a decision lineage under changes to law, data, sources, models, metrics, context, historical semantics, and post-deployment evidence. It uses `decision_lineage_key`, fingerprints, dependency keys, events, and review/reissue states. Its test fixtures show that a law change can move a decision into human review and that legacy packets can receive sticky lifecycle triggers.

Nothing in the inspected contract proves that `decision_lineage_key` is tenant-qualified, jurisdiction-qualified, globally non-reassignable, or semantically equivalent to a lifetime public policy.

### 2.3.7 Append-only claim lifecycle and reissue

Scientist continuous governance already maps detector events into append-only claim lifecycle transitions and blocks unscoped events. It preserves old records while generating projection-only public revision state.

The reissue contract links original and new decision packets, claim ledgers, changed scope, unchanged records, superseded references, public diffs, and human review without mutating the old artifacts.

Tests confirm:

- partial claim reissue preserves unaffected claims;
- projections remain projection-only;
- an event without affected claim scope produces a blocker and no lifecycle mutation.

This is the strongest repository precedent for matter-lineage corrections.

### 2.3.8 Lex source identity and versioning

Lex separates:

- a legal-document source identity;
- document versions;
- official or canonical external locators;
- jurisdiction;
- publication and effective dates;
- active-version resolution at an `as_of` date;
- provenance and quality warnings.

Its legal version index records missing or overlapping temporal ranges and emits a deterministic world event.

This is evidence for legal-instrument episodes. It cannot be promoted into policy identity because:

- one instrument may authorize several policy matters;
- one matter may be implemented through several instruments;
- instrument succession may or may not preserve matter identity.

### 2.3.9 Core audit

`core.audit` assembles deterministic portable archives from CAS artifacts and run metadata and verifies integrity, signatures, and provenance offline.

It is an appropriate owner for matter-custody audit events and portable verification packages, but not for the semantic definition of a matter.

### 2.3.10 DDM

DDM is the canonical package for drift, degradation, readiness, incidents, and shift evidence. It can produce events that affect a matter, but it does not establish which matter an incident belongs to.

### 2.3.11 PolicyPortfolio

ADR-0022 and the loader define `PolicyPortfolio` as a set of candidate `PolicySpec` references and interactions used for analysis/search. It is not a deployed policy stock and not a lifetime policy identity. Reusing it for PolicyMatter would merge design-option composition with real-world custody.

## 2.4 Identifier inventory

| Identifier | Current meaning and owner | Scope/mutability | Public, signed, replay use | Migration risk |
|---|---|---|---|---|
| `case_id` | PDC/runtime-quality case identity | Case-bound; usually accompanied by run/job/tenant, but not intrinsically globally scoped | Appears in governance, revision, and lifecycle records | **Critical:** current schemas could tempt later code to treat case as lifetime policy. |
| `decision_lineage_key` | Decision-validity lineage | Stable for one decision lineage; inspected contracts do not establish tenant/jurisdiction/global uniqueness | Used by monitoring, dependency events, and historical validity state | **High:** may be mistaken for matter identity even though one matter can have many decisions. |
| `run_id` | Execution/run identity | Ephemeral process/run scope | Widely stored for replay and audit | **Critical if elevated:** a matter survives many runs. |
| `job_id` | Runtime job identity | Execution scope | Operational diagnostics | Not suitable for identity. |
| `graph_id` | Runtime PDC graph identity | Derived from current graph/run context | CAS persistence and projection | Graph version, not matter. |
| `artifact_id` | Content address | Immutable for bytes; global digest syntax | Signatures, URLs, lineage, replay | Cannot identify a mutable real-world policy. |
| `portfolio_id` | Candidate portfolio identity in IR and evidence modules | Analysis-specific and overloaded | May appear in artifacts | Must remain separate from deployed matter stock. |
| `policy_id` | Overloaded across PolicySpec, evaluation policy, caches, legal/evidence code | Meaning depends on owner | May leak into exports | Must not be treated as globally canonical. |
| `release_id` | Data/world/model release identity | Release/version scope | Replay and world-state selection | Matter may span many releases. |
| `epoch_id` | Knowledge, acquisition, calibration, or grounding epoch | Epistemic version scope | Staleness/revalidation | Matter spans many epochs. |
| `tenant_id` | Security and ownership boundary | Explicit, essential, temporally stable only within tenancy | CAS/security/audit | Must qualify authority, but current tenant cannot be embedded as an unchangeable semantic policy attribute. |
| `jurisdiction` | Applicability/context attribute | Versioned and potentially multi-valued | Lex/PDC/legal outputs | Jurisdiction may expand, contract, or change; it cannot be the ID. |
| `supersedes` | Distributed artifact, claim, rule, and document relation | Typed by local owner | Replay and lifecycle | Generic reuse without source/target types would be ambiguous. |
| `lineage` | Artifact, run, legal, evidence, UI, and scenario lineage | Multiple incompatible meanings | Widely projected/exported | A dedicated typed matter-lineage relation is needed; generic lineage is insufficient. |
| `matter_id` | No implementation occurrence returned by commit-pinned repository search | — | — | Exact semantic owner and contract remain absent. |

The PDC and tenant/CAS tests currently bind records to `case_id`, `run_id`, `job_id`, and `tenant_id`, including public-trust, recall, retraction, decision lifecycle, and human-review records.

## 2.5 Current capability chain

| Chain element | Current state | Likely owner |
|---|---|---|
| Typed matter contract | **contract_only** as a research/backlog concept | PDC lineage area, to extend |
| Matter identifier producer | **producer_missing** | Future governed PDC/runtime-quality producer |
| Case-to-matter association artifact | **producer_missing** | PDC identity owner |
| Technical artifact lineage | Implemented | `ir.artifacts` / CAS |
| Legal-document identity/version evidence | Implemented | Lex |
| Claim/decision lifecycle | Implemented but case/decision scoped | Scientist continuous governance / decision validity |
| Matter-lineage bridge | **bridge_missing** | Runtime quality adapter ring |
| Matter-aware invalidation consumer | **bridge_missing** | Future H2 custody runtime |
| Semantic identity tests | **semantic_test_missing** | PDC semantic fixtures |
| Matter projection | **surface_missing** | Atlas/runtime lineage projection |
| Public correction fan-out | Separate PAO-R36 research dependency | Atlas/publication owners |
| Portable audit verification | Implemented for artifacts/runs | Core audit |

**Overall capability label:**

`contract_only + producer_missing + bridge_missing + semantic_test_missing + surface_missing`, surrounded by substantial `implemented_but_not_orchestrated` fragments.

## 2.6 Reusable tests and fixtures

The following can be extended rather than replaced:

- PDC compiler projection and anti-LLM-laundering tests;
- PDC record-family completeness blockers;
- tenant/CAS/public-trust and recall/retraction tests;
- decision-validity law-change and legacy-packet tests;
- append-only lifecycle and partial-reissue tests;
- artifact-lineage closure tests;
- Lex version-index and temporal-selection fixtures;
- runtime lineage tenant, `valid_at`, `tx_at`, replay, and export tests;
- audit export/offline verification fixtures;
- PolicyPortfolio tests as negative non-identity fixtures.

## 2.7 Research blockers versus engineering blockers

### Research blockers

1. No jurisdiction-neutral automatic identity theorem exists.
2. Competence to declare continuity, split, merger, or succession varies by legal system.
3. The exact granularity of a “policy” is often contestable: umbrella strategy, intervention family, program, and statutory scheme can overlap.
4. One PDC may analyse a package affecting several matters; the permitted granularity of case-to-matter links remains unratified.
5. Cross-institution and cross-jurisdiction identity federation requires an issuer and trust model.
6. “Same matter” does not answer whether old evidence transports to new scope.

### Engineering blockers

1. No canonical matter schema or identifier registry.
2. No case-to-matter typed association.
3. No matter-lineage assertion producer or validator.
4. No migration/dual-read mechanism for legacy cases.
5. No matter-aware authority-dependency fan-out.
6. No frozen semantic benchmark.
7. No matter projection or public resolver.
8. No correction path for a cryptographically valid record associated with the wrong matter.
9. No explicit support for split/merge cardinalities.
10. No matter-aware cross-tenant isolation tests.

## 2.8 Smallest reuse-first integration path

The smallest path visible today is:

1. **Extend the PDC identity/lineage owner**, rather than create a new top-level authority family.
2. Add a typed `MatterSubjectRef` and separate matter-association/lineage assertions.
3. Let `runtime/quality` admit, validate, downgrade, or block external identity evidence.
4. Persist immutable matter and assertion artifacts in CAS.
5. Record custody events through core audit and existing append-only lifecycle patterns.
6. Use Lex only as legal-instrument evidence.
7. Let the H2 custody runtime consume matter identity for suspension, wake, invalidation, and replay.
8. Let Atlas and runtime lineage project matter history without minting it.
9. Keep PolicyPortfolio as candidate-composition IR.

The repository ownership map already places PDC in the design-grammar authority area and states that runtime quality is the current PDC backbone owner; it also requires reuse-first classifications and complete capability chains.

---

# 3. External Research Baseline

## 3.1 Negative finding

Among the inspected primary standards and canonical research, **no single pattern establishes lifetime public-policy identity across design cases, legal instruments, institutional changes, implementation variants, public records, splits, mergers, and disputed continuity**.

Each pattern family solves a narrower problem:

- persistent identifiers preserve reference;
- provenance represents derivation and responsibility;
- archival models preserve records and context;
- legal-document identifiers distinguish works, expressions, manifestations, and versions;
- temporal systems preserve valid and recorded history;
- entity resolution ranks candidate matches;
- public registries identify objects within a defined administrative scope.

PolicyOS therefore needs a composed identity method with an explicit authority delta.

## 3.2 Pattern-family comparison

| Pattern family | What it solves | What it does not solve | Split/merge/dispute support | PolicyOS authority delta |
|---|---|---|---|---|
| Persistent identifiers: DOI, ARK, DataCite | Opaque/stable naming, non-reassignment, aliases, related identifiers and version relations | Does not determine whether two interventions are the same policy | Can encode relations, but steward decides their meaning | Competent lineage assertion, tenant/jurisdiction scope, authority consequence, correction and replay |
| W3C PROV | Entities, activities, agents, derivation, attribution, bundles | Domain semantics and identity equivalence are intentionally external | Can represent competing provenance bundles; no policy-sameness adjudication | Typed policy relations, competence evidence, fail-closed identity state |
| PREMIS and RiC-O | Preservation objects, events, agents, rights, archival context and relationships | Does not decide intervention continuity | Good preservation of parent/child and correction context | Authority-bearing matter lineage and claim-validity consequences |
| Akoma Ntoso / ELI | Legal-document work/version/manifestation identity, URIs, temporal/legal metadata | A legal instrument is not a policy matter | Excellent document versioning; limited policy-program split/merge semantics | Many-to-many instrument-to-matter links and continuity evidence |
| Bitemporal databases | Valid-time and transaction-time history | Does not determine identity or competent authority | Supports corrected histories without overwrite | Observation, admission, publication, correction and authority semantics |
| Event sourcing | Append-only event history and reconstructable state | Event stream boundaries assume an aggregate identity already exists | Can encode corrections and branches if designed | Stable matter aggregate boundary, immutable assertion IDs, historical authority views |
| Probabilistic record linkage | Candidate match/non-match/possible classification under uncertainty | Similarity is not sovereign authority | Can preserve unresolved matches; no legal effect | Candidate-only use, independent evidence, human adjudication, no authority upgrade |
| GLEIF legal-entity events | Structured name change, merger, demerger, acquisition, spinoff and event status | Legal-entity identity differs from policy identity | Strong typed event model | Policy-specific objective/mechanism/population and evidence-scope review |
| Government program inventories | Official program/listing identifiers and selected statutory/administrative metadata | Inventory granularity and completeness vary; one listing may aggregate or fragment policies | Usually weak on historical split/merge and contested identity | Treat as external evidence, not canonical matter identity |
| Memento | Historical web-resource representations and datetime negotiation | URL history is not policy identity | Preserves prior public-resource states | Explicit matter association, correction, supersession and signature validity |

W3C PROV deliberately supplies a domain-neutral model of entities, activities, agents, derivation, and responsibility; the conditions that establish domain-specific identity or derivation remain outside the standard. ([W3C][2])

Akoma Ntoso and ELI distinguish legal works, expressions, manifestations, versions, and identifiers, making them strong legal-instrument evidence sources but not policy-matter definitions. ([OASIS][3])

DataCite provides useful typed relations such as versions, continuations, and parts, while ARK and DOI guidance emphasize persistence and non-reassignment. Their persistence depends on governance and stewardship, not identifier syntax alone. ([DataCite Support][1])

Fellegi–Sunter record linkage and later Bayesian linkage methods explicitly allow uncertain or possible matches. That is useful for candidate generation but cannot justify an authoritative identity upgrade. ([Tandfonline][4])

Bitemporal research and event-sourcing patterns support reconstruction of what was valid and what was recorded at different times, but they presuppose a chosen aggregate or entity boundary. ([ResearchGate][5])

## 3.3 Established findings versus design recommendations

### Established by standards or repository evidence

- Persistent identifiers should not be reassigned.
- Content identity and real-world entity identity are different.
- Provenance and identity assertions need explicit source, agent, activity, and evidence.
- Legal-document identity and policy identity are different.
- Corrections must preserve prior states for historical replay.
- Probabilistic matching has legitimate unresolved outcomes.
- Split/merge and succession require typed relations, not generic similarity.

### Design recommendations specific to PolicyOS

- Define PolicyMatter as an accountability/custody anchor.
- Make identity assertions first-class, versioned artifacts.
- Separate identity from evidence applicability.
- Use a namespace-qualified opaque ID.
- Treat automated matching as candidate-only.
- Keep split and merge non-destructive.
- Map identity findings into the existing Atlas grammar as blockers or limitations.
- Preserve unresolved and contested states.

### Unresolved open questions

- Jurisdiction-specific competence rules.
- Cross-institution federation and transfer of custody.
- Appropriate granularity for umbrella strategies and composite programs.
- Whether a single PDC may authoritatively attach to multiple matters.
- Public identifier exposure and privacy model.
- Threshold for treating mechanism or objective change as successor rather than continuation.

---

# 4. Result

## 4.1 Candidate definition of PolicyMatter

> **PolicyMatter is a stable, opaque, non-reassignable, namespace-qualified accountability and justification-custody identity representing one continuing or lineage-connected public-authority intervention commitment, under which PolicyOS binds its cases, decisions, claims, evidence-scope conclusions, custody events, corrections, supersessions, withdrawals, and public records.**

The identity is stable, but the policy’s descriptions and embodiments are not. A matter may span:

- several Policy Design Cases;
- several runs and decision packets;
- several laws, regulations, contracts, guidance documents, and budget lines;
- several institutional owners;
- pilot, rollout, scale, suspension, and reactivation episodes;
- several implementation variants;
- multiple evaluations and incidents;
- corrected and superseded public records.

A PolicyMatter is therefore primarily a **durable accountability object and intervention-lineage anchor**, not an enduring problem, title, agency, legal document, or software object.

## 4.2 What PolicyMatter is not

| Object | Why it is not PolicyMatter |
|---|---|
| Public problem or policy domain | Many unrelated interventions address the same problem. |
| Authorized objective | Distinct interventions may share the objective; objectives may also change. |
| Policy Design Case | A matter can have many design, redesign, revalidation, and appeal-related cases. |
| Workflow run | Runs are computational episodes. |
| Recommendation or option | These are candidates or decisions within a matter. |
| Policy instrument | One instrument can implement several matters; one matter can use many instruments. |
| Law or regulation | Legal documents have their own work/version identity. |
| Program name | Names collide and change. |
| Agency | Institutions reorganize and transfer mandates. |
| Budget line | Budgets are mutable and may fund several matters. |
| Implementation project | A matter may have several regional or supplier implementations. |
| Service | One service may operationalize several policies. |
| Evaluation | Evaluation is evidence about a matter. |
| Incident | An incident affects a matter but does not define it. |
| Public record or URL | Records and locations can be corrected, replaced, or disappear. |
| Decision | One matter has many decisions over time. |
| PolicyPortfolio | PolicyPortfolio models candidate combinations, not deployed lifetime custody. |
| Topic | Topic similarity has no identity authority. |

## 4.3 The identity kernel

No descriptive field is universally immutable. The candidate identity kernel therefore has two layers.

### Immutable technical anchors

1. `policy_matter_id`;
2. issuer or identity namespace;
3. non-reassignment rule;
4. creation/admission event reference;
5. origin tenant/security namespace;
6. original jurisdictional authority context;
7. append-only assertion and correction history.

### Versioned substantive identity basis

1. authorized objective;
2. intervention family and mechanism;
3. target or affected population;
4. benefit/burden distribution;
5. jurisdictional and territorial scope;
6. accountable public authority;
7. legal mandate;
8. policy theory or theory of change;
9. public continuity, succession, split, or merger declarations.

The substantive layer informs adjudication; it does not become a deterministic hash key.

## 4.4 Field classification

| Field class | Examples | Treatment |
|---|---|---|
| Immutable anchor | `policy_matter_id`, issuer namespace, creation event | Never changed or reassigned |
| Mutable description | canonical label, summary, current agency, budget | Versioned descriptive records |
| Versioned scope | objective, mechanism, population, territory, jurisdiction | Effective intervals plus transaction history |
| External assertion | statute, official succession declaration, registry entry | Typed evidence with competent authority |
| Derived projection | current label, current owner, current episode set | Recomputed from admitted graph |
| Alias | old name, external program number, deprecated URL | Versioned and non-canonical |
| Disputed attribute | contested objective continuity, disputed owner | Preserved with competing assertions |
| Human-adjudicated | material objective/mechanism/population continuity | Signed adjudication receipt and authority ceiling |

## 4.5 New episode, new version, successor or new matter

### 4.5.1 Four-stage decision protocol

**Stage A — reference closure**

The candidate must have:

- explicit source and target objects;
- tenant/namespace and jurisdiction context;
- event, effective, observation, and transaction times;
- evidence provenance;
- relation type;
- scope of the assertion.

Failure produces `identity_unresolved`, not a guessed answer.

**Stage B — competence closure**

Determine whether the asserting body or reviewer is competent to state:

- continuity;
- legal succession;
- split;
- merger;
- transfer;
- repeal and replacement;
- correction.

A title, web page, or similar wording is not proof of competence.

**Stage C — material continuity analysis**

Compare, without collapsing into one similarity score:

- authorized objective;
- intervention mechanism/family;
- target and burdened populations;
- legal mandate;
- accountability/public commitment;
- jurisdiction and scope;
- theory of action;
- declared continuity or replacement.

A material contradiction must be resolved or preserved as contested.

**Stage D — typed outcome**

Candidate outcomes are:

- `same_matter_new_episode`;
- `same_matter_new_version`;
- `same_matter_successor_instrument`;
- `matter_split`;
- `matter_merge`;
- `derived_matter`;
- `related_but_distinct`;
- `identity_contested`;
- `identity_unresolved`;
- `new_matter`.

These are identity-resolution outcomes, **not a second publication or authority lattice**. They become evidence inputs or blockers to the existing Atlas grammar.

### 4.5.2 Checkable rulebook

| Change | Default safe classification | Conditions that preserve identity | Conditions creating successor/new matter |
|---|---|---|---|
| Rename | Same matter, new alias/version | No material substantive change | Rename conceals objective or mechanism replacement |
| Agency transfer | Same matter, institutional-transition episode | Competent mandate and accountability transfer | New authority adopts materially different purpose or intervention |
| Pilot to scale | Same matter, new implementation/scale episode, or derived matter | Explicit continuation; same intervention lineage; scope change documented | Scaled program independently authorized with materially different mechanism/objective |
| Failed pilot replaced | Successor, derived, or new matter | Only if competent authority explicitly continues the intervention commitment despite redesign | Same name reused for materially different intervention |
| Amendment | Same matter version/episode | Amendment modifies the same intervention commitment | Amendment replaces core objective or theory of action |
| New legal instrument | Same matter successor instrument | Instrument explicitly continues or reauthorizes the matter | Instrument replaces it with a distinct commitment |
| Repeal and immediate replacement | Unresolved until legal continuity analysed | No substantive gap; explicit succession; same accountability | Replacement changes mandate/objective/mechanism materially |
| Reenactment after dormancy | Successor or new matter by default | Strong explicit continuity and preserved accountability history | New authority, purpose, or intervention despite similar text |
| Geographic expansion | Same matter episode or derived matter | Explicit extension of the same matter | Independent national program merely resembles local pilot |
| Geographic contraction | Same matter scope version | Formal narrowing | Residual branches become independently accountable programs |
| Target-population change | Scope review; same, split, or new | Extension remains within authorized intervention commitment | Original and new populations need separate mechanisms/accountability |
| Mechanism change | Strong review trigger | Change remains within declared intervention family | New mechanism changes theory of action or burden distribution materially |
| Objective change | Presumption of successor/new matter | Clarification or subordinate objective only | Authorized end or public commitment changes materially |
| Emergency variant | Same episode or derived matter | Temporary emergency authority modifies the existing intervention | Separate emergency program with independent mandate |
| Suspension | Same matter, suspension episode | No replacement or termination | Suspension is actually repeal/termination |
| Reactivation | Same matter if formal continuity | Same identity and accountability restored | New enactment constitutes a successor |
| Split | Parent preserved; new child matter IDs | Never represented as mere versions | — |
| Merge | Parent matters preserved; new merged matter ID | Never collapse parent histories | — |
| Institutional reorganization | Same matter institutional episode | Mandate transferred | Reorganization creates materially different policy |
| Public-record correction | Same matter; new record version/correction event | Corrects representation only | Correction reveals original record concerned another matter |

### 4.5.3 Version versus episode

- **Version** describes a revised representation or specification of the same object: amended design specification, corrected label, revised public record, updated scope statement.
- **Episode** describes a bounded occurrence or interval: design, pilot, rollout, suspension, monitoring period, incident response, institutional transition.
- A version may be produced during an episode.
- A new episode need not create a new matter.
- A successor instrument is a new legal object; whether it is attached to the same matter is separately asserted.

## 4.6 Candidate episode graph

### 4.6.1 Node families

1. **PolicyMatter**
   - lifetime identity anchor.
2. **PolicyMatterEpisode**
   - a matter-specific occurrence or interval in one lifecycle.
3. **External object**
   - legal instrument;
   - institution;
   - program registry entry;
   - budget authorization;
   - implementation;
   - service;
   - evaluation;
   - incident;
   - public record.
4. **PolicyOS authority object**
   - PDC;
   - decision;
   - claim;
   - evidence binding;
   - public signature;
   - reissue packet;
   - withdrawal or correction record.
5. **Event**
   - enactment;
   - publication;
   - effective date;
   - transfer;
   - incident;
   - correction;
   - split;
   - merger;
   - suspension;
   - reactivation.
6. **PolicyMatterLineageAssertion**
   - a reified, independently addressable assertion connecting source and target objects.

### 4.6.2 Five distinct lifecycles

| Lifecycle | Typical episodes | PolicyOS boundary |
|---|---|---|
| Epistemic | design, validation, evidence acquisition, stale, revalidation | OWN |
| Administrative | applications, notices, appeals, remedies | INTEGRATE typed evidence; do not own administration |
| Implementation | pilot, procurement, rollout, scale, capacity failure | INTEGRATE evidence |
| Institutional | mandate, delegation, transfer, reorganization | INTEGRATE/OBSERVE according to claim-validity effect |
| Public records | publication, correction, supersession, archive, disclosure | OWN PolicyOS records; INTEGRATE external records |
| PolicyOS custody overlay | attach case, revalidate, reissue, correct, supersede, withdraw | OWN |

A matter must not have one linear `matter_status`. It can simultaneously be:

- active in implementation;
- epistemically stale;
- institutionally transferred;
- under incident review;
- represented by a superseded public record.

### 4.6.3 Events, intervals and projections

The graph should combine:

- **events** for occurrences such as enactment, publication, split, correction;
- **state intervals** for implementation, suspension, ownership, legal effect;
- **entities** for matters, episodes, instruments, institutions, records;
- **typed edges** for scoped relationships;
- **projections** for current and historical views.

A projection must never become the source of identity authority.

### 4.6.4 Required graph properties

1. Multiple simultaneous episodes are allowed.
2. Matter-specific episodes belong to one matter.
3. Shared implementations, instruments, evaluations, and records are external entities linked many-to-many to matters.
4. Competing lineage assertions coexist.
5. Every assertion carries valid/effective and transaction history.
6. Split and merge never delete parent identities.
7. Corrections supersede assertions rather than overwrite them.
8. Historical replay reconstructs both:
   - the world considered valid at a time;
   - the assertions PolicyOS had admitted by that time.
9. Identity relations and evidence-applicability relations remain separate.
10. A same-matter assertion does not automatically transport evidence.

## 4.7 Lineage relation semantics

| Relation | Source → target and cardinality | Identity and temporal meaning | Competent assertion and evidence | Missing/correction/replay behavior |
|---|---|---|---|---|
| `has_episode` | Matter → matter episode, 1:N | Membership; identity-preserving | PolicyOS custody producer using admitted episode evidence | Missing link blocks episode aggregation; corrected by new association assertion |
| `continues` | Episode → prior episode; exceptional matter-ID reconciliation | Explicit identity continuity | Competent authority or delegated custody adjudicator | No similarity-only inference; revoked assertion restores unresolved state |
| `implements` | Implementation entity → matter, N:M | Does not itself assert identity | Delivery authority, contract, official implementation record | Missing link prevents implementation evidence from affecting matter |
| `enacts` | Legal instrument → matter, N:M | Instrument gives legal form; no one-to-one identity assumption | Competent legislative/executive source | Correction preserves prior association |
| `authorizes` | Instrument/decision/mandate → matter or episode, N:M | Defines authority scope and effective interval | Competent legal authority | Absence caps legal authority; retroactive evidence can trigger revalidation |
| `evaluates` | Evaluation → matter/episode, N:M | Evidence relation only | Evaluation owner plus methodology/provenance | Does not establish identity; wrong link invalidates evidence use |
| `monitors` | Monitoring contract/report → matter/episode, N:M | Observation relation | Typed monitoring producer | Missing scope blocks lifecycle transition |
| `corrects` | New assertion/record → prior assertion/record, N:1 | Prior object retained; new transaction-time truth | Owner or competent correction authority | Current view follows correction; historical view retains old state |
| `supersedes` | New artifact/episode/assertion → prior peer, N:1 or N:M | Replaces current effect, not historical existence | Competent owner | Must name scope and effective time; not equivalent to withdrawal |
| `withdraws` | Custody event → PolicyOS signature/record/assertion | Ends current PolicyOS reliance/public standing | Authorized PolicyOS human or rule-bound process | Historical retention mandatory |
| `replaces` | New matter/instrument/implementation → old | Does **not** imply same identity | Competent source and explicit scope | Default `related_but_distinct` or unresolved |
| `succeeds` | New matter → predecessor matter, N:M | Identity-distinct successor with inherited accountability history | Competent authority/human adjudication | Parent remains; evidence inherited only after scope review |
| `splits_from` | Child matter → parent, N:1 or N:M | New child identity | Competent split decision | Parent retained; child receives no blanket evidence authority |
| `splits_into` | Parent → children, 1:N | Inverse navigational assertion | Same evidence as `splits_from` | Every child needs scoped inheritance review |
| `merges_from` | New matter → parent matters, N:M | New merged identity | Competent merger decision | Separate parent histories preserved |
| `merges_into` | Parents → merged matter, N:1 | Inverse navigation | Same evidence as `merges_from` | No alias collapse |
| `derived_from` | New matter → source matter(s), N:M | Related lineage without identity continuity | Competent design/authorization evidence | No automatic supersession or evidence inheritance |
| `renamed_from` | New alias/label version → old alias/label version | Same matter; descriptive only | Official naming/publication evidence | Rename cannot create or merge matter IDs |
| `scales_from` | Scale episode → pilot episode | Candidate continuity; identity effect must be explicit | Formal continuation, budget/mandate, implementation documentation | Without decisive evidence, remain unresolved or derived |
| `narrows` | New scope version/episode → prior scope | Identity-preserving only if authorized as same matter | Competent scope decision | Evidence applicability must be narrowed |
| `expands` | New scope version/episode → prior scope | Identity-preserving only if authorized | Competent expansion decision | Old evidence requires transport/scope review |
| `temporarily_suspends` | Suspension event/episode → active episode | Identity-preserving interruption | Competent operational/legal authority | Suspension is not withdrawal or termination |
| `reinstates` | Reactivation episode → suspended episode | Restores operation; same identity only with continuity evidence | Competent authority | New enactment may instead be successor |
| `publicly_represents` | Public record → matter(s), N:M | Representation, not identity creation | Record publisher | Wrong association requires public correction |
| `institutionally_owned_by` | Matter/episode → institution, N:M over time | Accountability/mandate interval; agency change alone does not change identity | Competence/mandate records | Historical owners retained; transfer may trigger authority review |

Generic `related_to` and untyped `same_as` should be prohibited wherever authority depends on the distinction.

## 4.8 Identity authority and adjudication

### 4.8.1 Evidence hierarchy

| Evidence | Permitted role |
|---|---|
| Statute, regulation, formal decision, or official declaration by a competent body | May establish legal continuation, succession, split, merger, or replacement within its legal scope |
| Official budget/program/registry records | May establish administrative identifiers, implementation continuity, or corroboration |
| Formal institutional succession record | May establish mandate/accountability transfer |
| Official public-record correction | May correct a published matter association |
| Archival classification | May support records continuity, not alone prove policy sameness |
| Policy documentation and public statements | Corroborating evidence |
| Shared text, name, URL, documents, staff, or agency | Candidate-generation evidence only |
| PolicyOS model similarity | Internal hypothesis only |
| Delegated human adjudication | May establish PolicyOS technical custody routing; does not create sovereign legal effect |

### 4.8.2 What PolicyOS may publish

PolicyOS may publish:

- that it has attached a case to a matter based on specified evidence;
- that a continuity assertion is externally authorized;
- that identity is contested or unresolved;
- that a previous association was corrected;
- the authority scope of its conclusion.

PolicyOS may not publish as fact:

- legal identity inferred solely from similarity;
- a merger inferred from shared documents;
- a split inferred solely from changed populations;
- cross-tenant equivalence from matching external IDs;
- evidence continuity merely because matter identity was preserved.

### 4.8.3 Fail-closed outcome

When competent identity evidence is absent:

1. preserve existing cases and artifacts separately;
2. record candidate matches in an identity-resolution receipt;
3. mark the association `identity_unresolved` or `identity_contested`;
4. do not pool evidence, incidents, evaluations, or performance history;
5. do not issue a matter-level current publication;
6. cap downstream authority through the existing Atlas status grammar;
7. require acquisition of authority evidence or human adjudication.

## 4.9 Persistent identifier requirements

### 4.9.1 Canonical reference

The canonical reference should be logically equivalent to:

```text
<issuer-or-identity-namespace, policy_matter_id>
```

The wire identifier may be globally collision-resistant, but authority still requires explicit namespace, tenant, and jurisdiction context.

### 4.9.2 Requirements

1. Opaque and free of names, agencies, objectives, territories, dates, or legal citations.
2. Immutable and non-reassignable.
3. Collision-resistant.
4. Qualified by issuer/identity namespace.
5. Original namespace preserved through institutional or tenant transfer.
6. Current custodian represented as a versioned relation.
7. Aliases and external IDs stored separately.
8. Deprecated IDs remain resolvable.
9. Split children and merged results receive new IDs.
10. Parent IDs remain permanently resolvable.
11. Public IDs must not reveal sensitive population or security information.
12. Resolver state must be exportable and independently verifiable.
13. Disaster recovery must preserve:
    - namespace registry;
    - alias bindings;
    - lineage assertions;
    - correction history;
    - signing and verification material.
14. ID equality must never cross tenant or issuer boundaries without an admitted equivalence/continuity assertion.

Persistent-identifier systems similarly separate opaque identity from mutable metadata and prohibit identifier reassignment, but they depend on institutional persistence commitments rather than syntax alone. ([ARK Alliance](https://arks.org/about/ark-features/))

## 4.10 Temporal semantics

Every event or assertion must distinguish at least:

| Clock | Meaning |
|---|---|
| Event time | When the underlying event occurred |
| Valid time | When the assertion is considered true in the modeled world |
| Effective time | When a legal or policy effect begins or ends |
| Transaction time | When PolicyOS recorded the representation |
| Publication time | When a record was made public |
| Observation time | When PolicyOS or its source observed the event |
| Admission time | When the evidence passed the PolicyOS authority boundary |
| Correction time | When a correcting assertion was admitted |
| Supersession time | When a prior artifact or assertion ceased to be current |

### 4.10.1 Required historical views

The graph must answer:

1. **As valid/effective:** What policy relation was considered legally or operationally effective at time T?
2. **As known:** What had PolicyOS observed by time T?
3. **As admitted:** What had passed PolicyOS authority gates by time T?
4. **As published:** What did PolicyOS publicly represent at time T?
5. **Current corrected view:** What does PolicyOS now consider the correct lineage?
6. **Historical replay:** What result would the historical rule/schema set have produced from the information available then?

### 4.10.2 Retroactive events

A retroactive law, corrected record, or reconstructed lineage can change the current valid-time view while leaving the old transaction-time view intact. It may trigger:

- annotation only;
- identity revalidation;
- authority revalidation;
- recomputation;
- public correction;
- reissue;
- supersession;
- withdrawal.

It may never silently rewrite the historical record.

## 4.11 Authority dependencies

| Change | Minimum consequence |
|---|---|
| Matter identity later found wrong | Identity revalidation plus impact analysis of every dependent claim, decision, incident, evaluation, and publication |
| Source unchanged, association revoked | Authority revalidation; payload may remain unchanged |
| Pilot and national program wrongly separated | Human continuity adjudication; corrected association; missing-history review |
| Unrelated policies merged | Immediate block; evidence separation; public correction; possible withdrawal |
| Split with evidence copied to all children | Scope review for every inherited evidence item |
| Institution changes but matter continues | Update institutional episode; competence revalidation where necessary |
| Successor instrument changes objective | Matter-successor/new-matter adjudication and evidence-scope review |
| Cryptographically valid record has wrong matter | Integrity remains valid; semantic authority becomes invalid or review-required |
| Alias corrected | Annotation/version update unless claims depended on alias semantics |
| Public URL changes | No identity change; update alias/record location |
| Matter association unresolved | No matter-level authority aggregation |

The repository already recognizes that payload validity and authority validity are different: append-only lifecycle events can supersede or block claims without rewriting their underlying artifacts.

## 4.12 Migration principles

### Phase 0 — Compatibility freeze

Stop new code and contracts from treating `case_id`, `decision_lineage_key`, `policy_id`, `portfolio_id`, or public URLs as permanent policy identity.

### Phase 1 — Inventory without reinterpretation

Inventory all legacy identifiers with:

- identifier kind;
- original value;
- tenant and jurisdiction context;
- source artifact;
- historical meaning;
- current resolution state.

### Phase 2 — Additive matter associations

Create separate, immutable case-to-matter association assertions. Do not edit old CAS objects or signed public packets.

### Phase 3 — Conservative resolution

Classify legacy records as:

- resolved;
- contested;
- unresolved;
- intentionally unassigned.

Ambiguous cases must not be automatically grouped. A non-authoritative candidate cluster may be used internally, but it must be prohibited from evidence pooling or public identity claims.

### Phase 4 — Dual-read projections

Current projections may show the corrected matter association while historical replay reads the original artifact and association view known at the historical transaction time.

### Phase 5 — Authority impact processing

A changed association triggers the authority-dependency graph:

- cases and claims;
- evidence use;
- incidents;
- monitoring;
- public records;
- revalidation;
- correction;
- supersession or withdrawal.

### Phase 6 — Deprecate case-as-matter assumptions

Only after benchmark and migration replay success should APIs, caches, exports, and public resolvers require or prefer matter references.

### Legacy identifier treatment

- `case_id` remains a case identifier.
- `decision_lineage_key` remains a decision-lineage identifier.
- Old values may become aliases or historical references through typed binding records.
- They must not be redefined retroactively as PolicyMatter IDs.
- Existing signed artifacts retain their original bytes and meaning.
- A new sidecar assertion may state that the artifact was later found to concern another matter.
- Public URLs continue to resolve to historical records plus correction/supersession information.

## 4.13 PolicyMatterCompatibilityFreeze — concise form

Until a canonical contract is ratified:

1. no current identifier is lifetime policy identity;
2. every new custody artifact must accept an extensible matter subject reference;
3. associations must be separately correctable;
4. one matter must support many cases;
5. scoped multi-matter cases must remain possible;
6. split and merge must be first-class;
7. tenant and jurisdiction context must be explicit;
8. unresolved and contested identity must be representable;
9. similarity cannot authorize identity;
10. corrections must append and supersede;
11. current and historical projections must be distinguishable;
12. old signed artifacts must never be rewritten;
13. matter identity must not imply evidence transport;
14. PolicyPortfolio must not become a matter registry;
15. PDC remains the presumptive canonical owner;
16. Atlas remains projection-only.

The complete standalone freeze appears in Appendix D.

## 4.14 Established findings, narrow conclusions, unresolved questions and rejected approaches

### Established findings

- A stable identity above cases is necessary for lifetime custody.
- Existing identifiers are insufficient individually.
- Existing repository owners can be extended.
- Matter identity, artifact lineage, legal-document identity, and evidence applicability must remain distinct.
- Historical corrections must be append-only.
- Split and merge require preserved parent histories.

### Accepted narrow conclusions

- PolicyMatter should be an opaque accountability/custody anchor.
- The ID is immutable; identity claims are versioned and correctable.
- Competent authority is required for authoritative continuity.
- Automated matching is candidate-only.
- Unresolved identity is a legitimate fail-closed outcome.
- The compatibility freeze is immediately supportable.

### Unresolved questions

- Exact jurisdictional competence rules.
- Global/federated namespace governance.
- Granularity of umbrella policies.
- Case-to-multiple-matter scoping.
- Public resolver and privacy model.
- Exact boundary between same matter redesign and successor matter.

### Rejected approaches

1. `case_id` as lifetime identity.
2. `decision_lineage_key` as lifetime identity.
3. Name- or text-similarity identity.
4. One legal instrument = one matter.
5. One program registry ID = one matter.
6. One agency = one matter.
7. Content hash = policy identity.
8. PolicyPortfolio = deployed policy stock.
9. Automatic union-find over candidate matches.
10. Silent retroactive correction.
11. Generic `related_to` for authority-relevant lineage.
12. Evidence inheritance solely from matter continuity.

## 4.15 Direct answers to the 22 final questions

1. **What remains the same?** The namespace-qualified, non-reassignable accountability and justification-custody identity, plus its preserved lineage history.
2. **Why not case, run, instrument, name, or agency?** Each is an episode, representation, implementation, or custodian that can change while the intervention commitment continues.
3. **Which changes preserve identity?** Rename, ordinary amendment, scope version, institutional transfer, suspension/reactivation, successor instrument, and pilot scaling when competent continuity evidence exists and material contradictions are resolved.
4. **Which changes create a new matter?** Split, merge result, materially new objective, materially new intervention theory, independent authorization, or replacement without continuity.
5. **How are ambiguous cases represented?** `identity_unresolved` or `identity_contested`, with candidate hypotheses and no evidence pooling.
6. **Who may assert continuity?** A competent public authority, legally authorized registry or records steward within scope, or a delegated human adjudicator for PolicyOS technical custody.
7. **What may PolicyOS infer?** Candidate matches and contradictions. It may not infer sovereign identity from similarity.
8. **Fail-closed outcome?** Separate custody, no aggregation, authority ceiling, acquisition or human review required.
9. **How are split and merge preserved?** New IDs for children/result; parents retained; separately scoped evidence and provenance.
10. **How are correction and revocation represented?** New append-only assertions linked to the old assertion; no overwrite.
11. **How do times interact?** Valid/effective time models the world; observation/admission/transaction/publication times model PolicyOS knowledge, authority, and public representation.
12. **How do legacy IDs migrate?** Through additive alias and association records; their historical meanings do not change.
13. **What must current work stop assuming?** That any case, decision, portfolio, instrument, artifact, release, agency, name, or URL is the lifetime identity.
14. **What is in the freeze?** Extensible matter refs, non-reassignment, split/merge, temporal history, tenant/jurisdiction scope, unresolved states, append-only corrections, no automatic merge, and PDC ownership.
15. **Which owner should be extended?** The PDC identity/lineage area, with runtime quality as the admitting adapter.
16. **Which artifacts are candidates only?** PolicyMatter, Episode, LineageAssertion, CompatibilityFreeze, and IdentityResolutionReceipt contract sketches.
17. **False-merge falsifier?** Two initiatives with identical names and documents but different mandates, populations, and authorities must remain separate.
18. **Continuity-loss falsifier?** A formally continued pilot that changes name, agency, instrument, and scale must retain matter history.
19. **OPS-R15 constraint?** Its capstone must attach every case, wake, event, correction, split, merge, and publication to matter-scoped identity without historical rewrite.
20. **What remains research-only?** The exact contract, granularity, competence rules, automatic resolution method, namespace federation, and production migration.
21. **What may later be prototyped?** Synthetic matter graphs, candidate matching, human review packets, additive legacy associations, and replay projections.
22. **What must be blocked?** Silent merge, case-as-matter, similarity authority, unproven cross-tenant equality, history rewrite, evidence inheritance without scope review, and a duplicate canonical owner.

---

# 5. Counterexamples And Failure Modes

## 5.1 Naming, renaming and pilot continuity

| Case | Unsafe conclusion | Correct safe outcome and required evidence | Authority, public-record and replay consequence | Human review |
|---|---|---|---|---|
| 1. Name collision | Same public name means same matter | Separate matters. Require competent continuity evidence, not title equality. | Block pooling; public records show distinct namespaces; replay remains separate. | Not mandatory if distinct authority evidence is decisive |
| 2. Rename | New name means new matter | Same matter, new alias/version, if substantive continuity holds. | Annotation only unless prior claims depend on the name; historical aliases retained. | Only if contradictory changes accompany rename |
| 3. Pilot to scale | National program is automatically unrelated | Same matter scale episode or explicitly derived matter, based on mandate, objective, mechanism and continuity declaration. | Preserve pilot evidence history but recheck transport to national scope. | Mandatory for material scope change |
| 4. Pilot replacement | Same name means failed pilot continues | Successor/derived/new matter if mechanism or objective materially changed. | Old pilot incidents and results remain attached to predecessor; new public record must not borrow them silently. | Mandatory |
| 5. Institutional succession | Ministry dissolution terminates policy identity | Same matter institutional-transition episode if mandate transfers. | Update responsible body and competence evidence; retain prior owner history. | Only if mandate transfer is ambiguous |

## 5.2 Legal, reenactment and structural change

| Case | Unsafe conclusion | Correct safe outcome and required evidence | Authority, public-record and replay consequence | Human review |
|---|---|---|---|---|
| 6. Legal successor | Repeal/replacement always creates new matter or always preserves it | `same_matter_successor_instrument`, successor matter, or new matter depending on formal continuity and material substance. | Legal impact review; current projection names successor instrument; historical instrument remains. | Mandatory where substantive effect changes |
| 7. Reenactment | Similar text means same matter | Default successor/new/unresolved; require strong continuity evidence. | No automatic evidence inheritance; historical repeal gap retained. | Mandatory |
| 8. Split | Rename parent programs as two versions | Parent retained; new child IDs and split assertions. | Child evidence scope reviewed separately; public history shows parent and children. | Mandatory |
| 9. Merge | Collapse two IDs and histories into one | Preserve both parents and create a new merged matter. | Current merged record links both histories; old records remain independently verifiable. | Mandatory |
| 10. Shared instrument | One law means one matter | Instrument links to several matters with scoped provisions. | Legal changes fan out only to affected matters/provisions. | Needed if provision scope is unclear |

## 5.3 Instruments, geography, objectives and mechanisms

| Case | Unsafe conclusion | Correct safe outcome and required evidence | Authority, public-record and replay consequence | Human review |
|---|---|---|---|---|
| 11. Multiple instruments | Different laws mean different matters | One matter may have several authorizing and implementing instruments. | Preserve instrument-specific validity intervals and provenance. | Usually not if links are explicit |
| 12. Municipal to national expansion | Same program name proves continuity | Same, derived, or new matter based on formal continuation and accountability. | Preserve municipal history; national evidence requires transport review. | Mandatory |
| 13. Boundary change | Territory code change creates new identity | Versioned jurisdiction geometry; matter unchanged unless intervention commitment changes. | Historical records use historical boundaries; current projection uses current geometry. | Only for ambiguous scope |
| 14. Objective change | Same mechanism means same policy | Strong presumption of successor/new matter where authorized objective changes materially. | Revalidate claims and public justification; do not present old objective evidence as current. | Mandatory |
| 15. Mechanism change | Same objective guarantees same matter | Same only if mechanism remains within authorized intervention family; otherwise successor/derived/new. | Scope review of all evidence and incidents. | Mandatory |

## 5.4 Population, tenants and historical misclassification

| Case | Unsafe conclusion | Correct safe outcome and required evidence | Authority, public-record and replay consequence | Human review |
|---|---|---|---|---|
| 16. Target-population change | Eligibility change is always a version | Same, split, or new matter depending on scale and intervention effect. | Population-specific evidence cannot be copied without review. | Mandatory for substantial change |
| 17. Agency-name similarity | Similar agencies/program labels imply continuity | Separate matters unless competent evidence links them. | Block evidence pooling and cross-record aggregation. | Usually not if origins are clearly separate |
| 18. Tenant collision | Identical external IDs across tenants identify one matter | Separate namespace-qualified references. Cross-tenant link requires admitted assertion. | Security blocker; no cross-tenant projection or cache reuse. | Required for cross-tenant federation |
| 19. Imported legacy record | Similar legacy case automatically joins nearest matter | Keep unresolved or unassigned; preserve case-level custody. | No matter-level publication or pooling until resolved. | Mandatory |
| 20. Incorrect historical merge | Delete one ID and rewrite history | Issue correction; separate current matters; retain historical wrong merge and its consequences. | Public correction and impact analysis; replay reproduces old erroneous view as historically known. | Mandatory |

## 5.5 Incorrect split, public error and malicious manipulation

| Case | Unsafe conclusion | Correct safe outcome and required evidence | Authority, public-record and replay consequence | Human review |
|---|---|---|---|---|
| 21. Incorrect historical split | Delete duplicate matter IDs | Preserve old IDs as historical aliases/references; add continuity/reconciliation assertion. | Current view may use one canonical matter; old citations remain resolvable. | Mandatory |
| 22. Wrong matter in public record | Edit the old record in place | Publish correction/supersession and corrected association. | Old signed record remains verifiable but marked semantically wrong or superseded. | Mandatory for authority-bearing records |
| 23. Cryptographically valid but semantically wrong | Valid signature means valid matter association | Integrity valid; semantic authority invalid/review-required. | Trigger identity and authority revalidation, public notice where material. | Mandatory |
| 24. Malicious merge | Merge matters to borrow favorable evidence | Block, record attempted privileged action/incident, require independent adjudication. | No current projection change; audit trail and security review. | Mandatory |
| 25. Malicious split | Split identity to escape incident or poor performance history | Block; preserve predecessor and incident links; require competent split evidence. | Public history continues to show relevant predecessor lineage. | Mandatory |

## 5.6 Core falsifiers

An implementation is falsified if any of the following occurs:

1. Two unrelated initiatives silently merge.
2. A genuine pilot-to-national continuation loses its history solely because name, institution, instrument, or scale changed.
3. A legacy case cannot later attach to a matter without changing its signed bytes.
4. A split copies unrestricted evidence authority to all children.
5. A merge erases parent provenance.
6. A corrected lineage view changes historical replay.
7. An unresolved candidate match becomes current through a numerical similarity threshold.
8. Identical cross-tenant external IDs are treated as identical matters.
9. A cryptographically valid but semantically wrong association remains publishable.
10. Matter continuity is treated as proof that evidence remains transportable.

## 5.7 Failure-pattern pass

| Pattern | Why it applies | Unsafe trigger | Constraint introduced | Status |
|---|---|---|---|---|
| P01 — contract-only capability | PolicyMatter appears in decisions/backlog but not runtime contract | Claiming lifetime custody because a schema sketch exists | Full capability chain and benchmark required | Open |
| P02 — fragments without bridge | CAS, Lex, PDC, validity, audit and lineage exist separately | Calling fragments an episode graph | PDC-owned matter bridge required | Reduced, not resolved |
| P03 — internal state without surface | Matter corrections may exist without inspectable public state | Hidden correction while stale record appears current | Atlas/runtime projection and public correction required | Open |
| P05/P15 — prose or projection becomes authority | Similarity explanation or UI could mint identity | LLM says “same policy,” Atlas displays it as fact | Typed assertion and AuthorityBoundary | Reduced |
| P07/P08 — wrong run or closure | Run/case IDs can leak into lifetime scope | A run change creates new matter | Explicit matter reference and closure | Open |
| P10 — structural completeness ≠ semantic adequacy | A graph can be complete but relations wrong | All nodes/edges present, false merge remains | Semantic benchmark and adversarial fixtures | Open |
| P12 — meaning resolved after emission | A case may be published before matter association is known | Later silent reassignment | Pre-publication subject closure or explicit unresolved blocker | Open |
| P13 — governance scope inflation | Identity work could become an administrative master-data platform | PolicyOS owns applications, payments, delivery records | Identity-decision anti-role firewall | Reduced |
| P14 — evidence inflation | Shared matter, split, or merge could duplicate support | Same evidence counted across all children | Separate evidence-applicability review | Open |
| P26 — wrong fallback | Ambiguous identity may be forced to nearest match | Missing evidence defaults to same matter | `identity_unresolved` fail-closed state | Reduced |
| P27 — duplicate canonical owner | New matter subsystem could duplicate PDC, Lex or IR lineage | Parallel status/lineage lattice | Extend PDC; owner map required | Reduced |
| P29 — projection/canonical drift | Matter lists embedded independently in UI/export | Atlas state diverges from canonical graph | Projection derives from PDC matter graph | Open |
| P32 — temporal context missing | Corrections may lack valid/transaction distinction | Current correction leaks into historical replay | Multi-clock mandatory fields | Open |
| P33 — untyped artifact admission | Generic metadata could be treated as identity evidence | `metadata["same_policy"]=true` upgrades authority | Typed allowlisted assertion artifacts | Open |

The project failure-pattern register identifies these categories as capability, authority, projection, temporal, and owner failures rather than mere implementation defects.

---

# 6. Benchmark Or Fixture Proposal

## 6.1 Synthetic corpus

Create a frozen corpus with approximately:

- 18 policy matters;
- 60 Policy Design Cases;
- 40 legal instruments and amendments;
- 12 institutional owners and successor bodies;
- 30 implementation episodes;
- 24 evaluations;
- 20 monitoring contracts;
- 16 incidents;
- 20 corrections or supersessions;
- 50 public records;
- 40 aliases and external IDs;
- 8 tenant namespaces;
- 6 jurisdictions, including changing territorial boundaries;
- 6 disputed identity clusters;
- 4 splits;
- 4 mergers;
- 6 retroactive corrections;
- 10 legacy cases with missing identity evidence.

The exact count is not load-bearing. Coverage of relation types and authority failures is.

## 6.2 Hidden ground-truth graph

The ground truth should be independently adjudicated and sealed before evaluating any resolver. It must classify pairs or clusters as:

- same matter;
- successor;
- split;
- merge;
- derived;
- related but distinct;
- definitely unrelated;
- unresolved;
- contested.

`Unresolved` and `contested` are ground-truth labels, not annotation failures.

## 6.3 Metrics

| Metric | Meaning |
|---|---|
| `false_merge_rate` | Definitely unrelated matters merged |
| `false_split_rate` | Adjudicated continuing matter fragmented |
| `continuity_loss_rate` | Historical cases or episodes lost from a continuing matter |
| `unjustified_identity_upgrade_rate` | Candidate/unresolved relation promoted without competent evidence |
| `unresolved_identity_forced_rate` | Benchmark-unresolved case forced into binary same/new |
| `historical_rewrite_rate` | Current correction changes historical replay |
| `wrong_matter_publication_rate` | Public artifact displayed under incorrect matter |
| `lineage_evidence_coverage` | Assertions with required provenance/competence/time evidence |
| `human_adjudication_accuracy` | Reviewer result against independent ground truth |
| `cross_tenant_collision_rate` | Namespace collision causing cross-tenant merge |
| `evidence_scope_leakage_rate` | Evidence inherited outside justified population/mechanism scope |
| `parent_provenance_loss_rate` | Split/merge loses parent history |

Critical sentinel fixtures require zero:

- false merges;
- forced unresolved answers;
- historical rewrites;
- wrong-matter public publications;
- cross-tenant collisions;
- unauthorized authority upgrades;
- parent provenance loss.

## 6.4 Metamorphic properties

1. Renaming alone must not create a new matter.
2. Identical names alone must not merge matters.
3. Agency transfer alone must not create a new matter.
4. A changed URL must not change identity.
5. Removing decisive continuity evidence must downgrade to unresolved or contested.
6. Adding irrelevant similar documents must not upgrade identity.
7. A split must not copy unrestricted authority to every child.
8. A merge must preserve separate parent provenance.
9. Correcting an assertion must supersede, not overwrite, it.
10. Historical replay must reproduce the identity view known then.
11. A legal instrument linked to several matters must not collapse them.
12. Several instruments linked to one matter must not split it.
13. A valid signature must not override a revoked matter association.
14. Cross-tenant equality of an external ID must not establish identity.
15. Same-matter continuity must not automatically transport evidence to a changed population.
16. A candidate similarity score may change candidate ordering but not authority.
17. A corrected current projection must not alter old CAS hashes.
18. A public alias removal must not make old citations unresolvable.

## 6.5 Migration replay using repository fixtures

A later test can reuse:

- the PDC graph fixture built from `run-24`;
- the decision-validity fixture using `lineage_fixture_001`;
- the W9 lifecycle bridge fixtures using case-bound claim histories.

Replay sequence:

1. Start with legacy artifacts containing only `case_id`, `run_id`, and `decision_lineage_key`.
2. Preserve their hashes and original schemas.
3. Add matter-association assertions.
4. Process:
   - rename;
   - successor instrument;
   - institutional transfer;
   - split;
   - merge;
   - wrong historical association correction.
5. Query the pre-migration transaction-time view.
6. Verify old signed artifacts retain their original subject representation.
7. Query the current corrected view.
8. Verify current impact fan-out reaches the correct claims/public records.
9. Verify no cross-tenant relation is inferred.
10. Compare incremental current view with a clean rebuild.

## 6.6 Human-review packet

A disputed continuity packet should contain:

1. source and target candidate IDs;
2. all competing lineage hypotheses;
3. competent authority and delegation evidence;
4. chronological event sequence;
5. valid/effective/publication/observation/admission times;
6. objective comparison;
7. mechanism and theory-of-action comparison;
8. population and benefit/burden comparison;
9. jurisdiction and territorial comparison;
10. legal instruments and amendments;
11. institutional transition records;
12. official public declarations;
13. similarities and material differences;
14. rejected alternatives;
15. existing PolicyOS signatures affected;
16. false-merge and false-split consequences;
17. recommended identity outcome;
18. resulting authority ceiling;
19. unresolved contradictions;
20. reviewer identity, competence, conflicts, and signature.

## 6.7 Clean historical replay criteria

A replay passes only if:

- every historical artifact hash is unchanged;
- original schema/rule versions are used;
- the original identity view is reconstructed as known/admitted then;
- later corrections are not visible in the earlier transaction-time view;
- current view shows the correction;
- old public references remain resolvable;
- split/merge parent histories remain distinct;
- no evidence is imported merely because identity was later reconciled;
- tenant boundaries remain intact.

---

# 7. Artifact Contract Sketch

All sketches below are **candidate_for_consolidation** and **research_only**.

## 7.1 Common envelope

Every candidate artifact should carry:

```yaml
schema_version: string
rule_version: string
artifact_ref: CAS reference

tenant_scope:
  origin_tenant_id: string
  current_custodian_tenant_id: string | null
  cell_id: string | null

jurisdiction_scope:
  asserted_jurisdictions: [...]
  scope_ref: reference

audience: internal | reviewer | public | machine

time:
  event_time: datetime | null
  valid_from: datetime | null
  valid_until: datetime | null
  effective_from: datetime | null
  effective_until: datetime | null
  observed_at: datetime | null
  admitted_at: datetime
  recorded_at: datetime
  published_at: datetime | null

provenance:
  producer_ref: reference
  runtime_event_ref: reference
  evidence_refs: [...]
  rule_refs: [...]

authority_boundary:
  authoritative_for: [...]
  may_not_use_for: [...]

uncertainty:
  support_status: authoritative | corroborated | contested | unresolved | revoked
  unresolved_reasons: [...]
```

Absence of required tenant, jurisdiction, provenance, competent-authority, or time evidence must block authority-bearing use.

## 7.2 PolicyMatter

```yaml
PolicyMatter:
  policy_matter_id: opaque immutable identifier
  identity_namespace: immutable issuer namespace
  creation_event_ref: reference
  origin_tenant_id: string
  origin_jurisdiction_context_ref: reference

  # Descriptive projections, not identity keys
  canonical_label_ref: reference | null
  alias_set_ref: reference | null
  summary_ref: reference | null

  identity_basis_refs: [...]
  external_identifier_refs: [...]
  authority_boundary: AuthorityBoundary

  # Derived indexes, never the canonical source
  current_episode_index_ref: reference | null
  case_association_index_ref: reference | null
  lineage_assertion_index_ref: reference | null
  public_record_index_ref: reference | null
  current_identity_resolution_ref: reference | null
```

### Justification

- `policy_matter_id` and namespace provide durable reference.
- Creation provenance prevents reassignment.
- Labels and aliases remain mutable.
- Lists are index references rather than embedded mutable arrays.
- There is no single `matter_status`.
- `identity_resolution` is diagnostic and does not replace Atlas authority state.

### Authority boundary

```yaml
authoritative_for:
  - PolicyOS matter reference
  - attachment target for PolicyOS custody artifacts
may_not_use_for:
  - legal existence of a program
  - administrative eligibility
  - individual decision making
  - automatic evidence transport
  - proof that two instruments are legally identical
```

## 7.3 PolicyMatterEpisode

```yaml
PolicyMatterEpisode:
  episode_id: opaque identifier
  policy_matter_ref: reference
  association_assertion_ref: reference
  lifecycle_class:
    - epistemic
    - administrative_evidence
    - implementation_evidence
    - institutional_evidence
    - public_record
    - policyos_custody
  episode_type: typed vocabulary
  valid_interval: interval
  effective_interval: interval | null
  owner_or_source_ref: reference
  external_object_refs: [...]
  predecessor_episode_refs: [...]
  successor_episode_refs: [...]
  status_evidence_refs: [...]
  authority_consequence:
    effect: none | annotate | revalidate_identity | revalidate_authority |
            recompute | correct_public_record | supersede | withdraw |
            human_adjudication
  correction_ref: reference | null
  supersession_ref: reference | null
```

Fail closed if the episode cannot be attached to a matter with a typed association.

## 7.4 PolicyMatterLineageAssertion

```yaml
PolicyMatterLineageAssertion:
  assertion_id: opaque immutable identifier

  source:
    object_type: matter | episode | instrument | institution | record | implementation
    object_ref: reference
  target:
    object_type: matter | episode | instrument | institution | record | implementation
    object_ref: reference

  relation_type: typed relation
  identity_effect:
    - identity_preserving
    - identity_distinct_successor
    - split
    - merge
    - derivative
    - representation_only
    - no_identity_implication

  asserting_authority:
    authority_ref: reference
    competence_ref: reference
    delegation_ref: reference | null
    assertion_scope: string

  evidence_refs: [...]
  contradiction_refs: [...]
  valid_interval: interval | null
  effective_interval: interval | null
  observed_at: datetime
  admitted_at: datetime
  recorded_at: datetime

  support_status: authoritative | corroborated | contested | unresolved | revoked
  contestation_ref: reference | null
  corrects_assertion_ref: reference | null
  revoked_by_assertion_ref: reference | null

  permitted_uses: [...]
  prohibited_uses: [...]
  authority_boundary: AuthorityBoundary
```

A confidence score may appear in an associated resolution receipt, but it may not substitute for `support_status`, authority, or evidence.

## 7.5 PolicyMatterCompatibilityFreeze

```yaml
PolicyMatterCompatibilityFreeze:
  freeze_id: string
  issued_at: datetime
  repository_commit: SHA
  consolidation_owner: team-architecture

  protected_assumptions:
    - identifier_kind
    - protected_rule
    - affected_surfaces
    - prohibited_irreversible_choice
    - safe_extension_point
    - risk_prevented
    - review_trigger
    - immediately_binding

  authority_boundary:
    authoritative_for:
      - Stage-0 research guard
    may_not_use_for:
      - final schema
      - production migration authorization
```

## 7.6 Identity-resolution receipt

A separate receipt is justified because the final identity assertion should not carry every rejected alternative and model diagnostic.

```yaml
PolicyMatterIdentityResolutionReceipt:
  receipt_id: string
  subject_refs: [...]
  candidate_matches_considered:
    - candidate_ref
    - candidate_source
    - non_authoritative_similarity_features
  decisive_evidence_refs: [...]
  rejected_alternatives:
    - hypothesis
    - reason
    - evidence_refs
  unresolved_contradictions: [...]
  proposed_outcome: identity outcome
  competent_authority_ref: reference | null
  human_adjudication_ref: reference | null
  resulting_authority_ceiling: string
  affected_case_refs: [...]
  affected_public_record_refs: [...]
  follow_up_actions: [...]
  authority_boundary:
    authoritative_for:
      - identity resolution audit
      - candidate comparison history
    may_not_use_for:
      - automatic legal identity
      - evidence pooling without admitted lineage assertion
```

## 7.7 Canonical-owner map

| Candidate concept | Existing owner | Owner status | Proposed disposition | Reason |
|---|---|---|---|---|
| PolicyMatter identity | PDC identity/lineage area | Partial semantic neighborhood; exact contract absent | **extend_existing**, candidate_for_consolidation | PDC is the typed authority waist above claims/cases |
| Case-to-matter link | PDC | Absent | Extend PDC with typed association | Determines PDC subject and custody scope |
| Episode graph | PDC plus external evidence references | Partial fragments | Extend/consolidate | Matter-specific identity graph belongs with PDC; external operations remain external |
| Lineage assertion | PDC | Absent as matter semantics | Candidate new contract within existing owner | Avoid duplicate IR/Scientist lineage owner |
| Identity-resolution receipt | Runtime quality producer; PDC-owned artifact family | Absent | Candidate for consolidation | Runtime quality is the adapter/admission ring |
| Public projection | Atlas/runtime lineage | Existing projection owner | Extend projection only | Surfaces may not mint identity |
| Audit event/package | Core audit | Existing | Extend existing | Portable verification and custody event evidence |
| Legal-instrument link | Lex | Existing evidence owner | Extend Lex output/reference use | Legal document identity remains Lex-owned |
| Incident evidence | DDM/Scientist continuous governance | Existing | Link through typed episode/association | Incident producer must not choose matter by similarity |
| Decision validity | Core contracts/Scientist validity | Existing, decision scoped | Add matter reference as extension | Do not redefine `decision_lineage_key` |
| Portfolio relation | PolicyPortfolio IR | Existing candidate-analysis owner | Keep separate; reference only | Portfolio is not deployed matter stock |
| World/release relation | Fabric/GY world and epoch owners | Existing | Consumer reference | Release/version is not matter identity |
| Institutional identity | External authority/registry | External | INTEGRATE | PolicyOS must not become institutional master data |
| H2 custody runtime | Future consumer | Not yet implemented | Consumer, not identity owner | It operates long-lived custody using the stable matter ID |

No new top-level canonical owner is justified by the repository baseline.

---

# 8. Later Integration Handoff

## 8.1 Artifact routing

| Artifact | Producer | Persisted artifact/event | Bridge | Consumer | Verification | Surface | Canonical home |
|---|---|---|---|---|---|---|---|
| PolicyMatter | Governed PDC identity producer | CAS matter artifact + creation audit event | Runtime-quality admission | PDC, H2 custody runtime | Schema, namespace, non-reassignment, tenant checks | Atlas matter header/resolver | `src/polisyos/pdc` candidate |
| Case-to-matter association | PDC/compiler or migration adjudicator | Immutable assertion | Runtime quality | PDC closeout, validity, H2 | Scope, competence, temporal and tenant validation | Case and matter views | PDC |
| Episode | External evidence adapter or PolicyOS custody producer | CAS episode + event | Runtime quality | H2, PDC, validity | Type-specific evidence and time checks | Atlas timeline | PDC relation; external evidence owner remains external |
| Lineage assertion | Competent evidence adapter/human adjudicator | CAS assertion + append-only audit | Runtime quality | Matter graph, authority dependencies | Competence, relation cardinality, contradictions, replay | Atlas lineage view | PDC |
| Identity-resolution receipt | Candidate matcher/human workflow | CAS receipt | Runtime quality | Reviewer, later assertion producer | Reproducibility, rejected alternatives, no authority laundering | Reviewer only by default | Runtime quality/PDC |
| Legal link | Lex | Legal source/version and world event | Existing Lex bridge | Matter assertion producer | Legal source, jurisdiction, effective time | Legal evidence panel | Lex |
| Incident link | DDM/continuous governance | Incident/monitor event | Matter association bridge | Validity and H2 | Affected-matter closure | Incident/public correction views | Existing DDM/Scientist owner |
| Matter correction | Authorized custody process | Correcting assertion, public diff, reissue/withdrawal refs | Continuous-governance bridge | PDC, H2, Atlas | Append-only and fan-out checks | Public correction state | PDC + core audit + Atlas projection |
| Portable matter audit | Core audit assembler | Signed audit bundle | Existing audit exporter | External reviewer | Offline integrity/signature/provenance | Download/export | Core audit |

## 8.2 Constraints imposed on OPS-R15

The custody-cycle capstone must:

1. distinguish `policy_matter_id`, `case_id`, `run_id`, `decision_lineage_key`, `artifact_id`, `release_id`, and `epoch_id`;
2. allow one matter to contain multiple cases;
3. preserve suspended or closed case state while the matter continues;
4. attach every external event through a typed matter/episode association;
5. include an institutional transfer without identity loss;
6. include a split and a merger;
7. include a wrong historical matter association and correction;
8. replay the pre-correction view;
9. preserve parent histories;
10. prevent evidence leakage after split or scope expansion;
11. test a cross-tenant collision;
12. test a malicious merge and split;
13. report:
    - `lost_case_state = 0`;
    - `silent_historical_rewrites = 0`;
    - `wrong_matter_publication = 0`;
    - `unauthorized_identity_upgrades = 0`;
    - `cross_tenant_collision = 0`.

The existing OPS-R15 definition already requires zero lost state, stale public state, unauthorized authority upgrades, silent historical rewrites, and missed affected cases; PAO-R0 adds explicit matter-separation and lineage metrics.

---

# 9. Promotion And Kill Rules

## 9.1 Research-only

Remain `research_only` while any of these is unresolved:

- canonical owner not ratified;
- competence model incomplete;
- namespace model unsettled;
- no semantic benchmark;
- no historical migration replay;
- no cross-tenant tests;
- no public-correction integration.

This report is currently at this level.

## 9.2 Prototype allowed

A prototype is allowed only when:

1. it runs on synthetic or explicitly non-authoritative data;
2. similarity outputs remain candidate-only;
3. all artifacts carry `AuthorityBoundary`;
4. unresolved and contested outcomes are supported;
5. no production public record or claim is changed;
6. split/merge and historical replay are included;
7. the PDC owner is used rather than a parallel owner.

Permitted prototypes:

- synthetic matter graph;
- candidate matcher;
- reviewer packet;
- additive legacy association sidecar;
- historical/current projection comparison.

## 9.3 Governed allowed

A governed pilot requires:

1. ratified PDC owner and schema;
2. typed producer and runtime-quality bridge;
3. tenant/jurisdiction isolation;
4. competence/delegation validation;
5. append-only correction;
6. all required clocks;
7. semantic benchmark passing;
8. matter-aware authority-dependency impact;
9. human review for material transitions;
10. Atlas projection derived from canonical graph.

## 9.4 Production candidate

Production candidacy additionally requires:

- independent legal/records review in the target jurisdiction;
- migration rehearsal over representative signed artifacts;
- zero critical sentinel failures;
- clean-rebuild parity;
- public correction and supersession integration;
- offline audit verification;
- disaster-recovery test for resolver, namespace and lineage state;
- cross-institution import/export test;
- key-rotation and archival-verification compatibility;
- OPS-R15 capstone success.

## 9.5 Blocked

Promotion is blocked if any proposal:

1. treats `case_id` as lifetime identity;
2. treats `decision_lineage_key` as lifetime identity;
3. treats names, text similarity, shared documents, URLs, agencies, or budget codes as sufficient proof;
4. automatically merges matters;
5. cannot represent split and merge;
6. rewrites historical lineage;
7. changes signed legacy artifact bytes during migration;
8. loses tenant or jurisdiction context;
9. cannot represent unresolved or contested identity;
10. allows similarity confidence to upgrade authority;
11. creates a second status lattice;
12. creates a duplicate canonical owner;
13. turns PolicyOS into an administrative master-data or case-management system;
14. treats same matter as automatic evidence applicability;
15. allows a child matter to inherit all parent evidence without scope review;
16. collapses parent histories after merger;
17. permits public matter correction without a visible correction/supersession link;
18. permits cross-tenant equality from matching external IDs.

## 9.6 Out of scope

The following remain out of scope for PAO-R0 and PolicyOS ownership:

- citizen applications;
- individual eligibility and sanctions;
- payments;
- caseworker workflow;
- legally effective notices;
- service-delivery master data;
- enterprise institutional master data;
- court determinations;
- operational execution of policy programs.

---

# 10. Open Questions For Consolidation

## 10.1 Repository contract questions

1. Should the canonical contract live directly in `polisyos.pdc` or a `pdc.identity`/`pdc.lineage` sub-area?
2. Should `RuntimePolicyDesignCase` carry a `MatterSubjectRef`, or should all associations remain sidecar artifacts?
3. Can one PDC attach to several matters? If so, must attachment be claim-, option-, or decision-scoped?
4. How should an unresolved legacy case appear in mandatory PDC record-family coverage?
5. Which decision-validity events should be matter-wide versus claim/case-specific?
6. Should runtime lineage export PROV/OpenLineage directly from the PDC matter graph or through an adapter?
7. What identifier namespace is public and what remains tenant-internal?

## 10.2 Parallel-task overlaps

| Task | Required consolidation |
|---|---|
| PAO-R1 | External identity/assertion functions must be classified INTEGRATE or OBSERVE, not silently OWN |
| OPS-R1 | Suspension records must carry matter subject and re-prove it at resume |
| OPS-R2 | Authority dependency graph must distinguish wrong matter association from payload change |
| OPS-R3 | Migration dossier must preserve matter history and old identifier meanings |
| OPS-R4 | Operational event envelope should supply the multi-clock fields used here |
| OPS-R8 | WorldRelease changes cannot redefine matter identity; matter assertions reference releases |
| OPS-R10 | Legal succession and instrument versions remain Lex evidence |
| OPS-R14 | Namespace, aliases, assertions and correction history need custody-grade recovery |
| INT-R7 | Public matter IDs and assertions must remain verifiable after key rotation |
| INT-R8 | Public summaries must retain identity uncertainty, corrections and denied uses |
| PAO-R36 | Wrong public matter association must trigger correction fan-out |
| OPS-R15 | Capstone vocabulary and critical metrics must be matter-aware |

## 10.3 Unratified assumptions

The following remain `external_dependency_assumption` or `candidate_for_consolidation`:

- competence evidence for continuity declarations;
- delegated human identity adjudicator;
- cross-jurisdiction identity federation;
- public resolver retention period;
- legal effect of historical corrections;
- case-to-multiple-matter support;
- whether a matter identity may transfer between tenants;
- whether a merged matter always receives a new ID;
- exact evidence-scope review contract;
- exact Atlas blocker mapping.

## 10.4 Recommended consolidation owner

`team-architecture`, jointly with the PDC canonical owner, should consolidate PAO-R0 with:

- PAO-R1 boundary results;
- OPS-R4 temporal vocabulary;
- OPS-R15 capstone vocabulary;
- INT-R5 competence/delegation semantics;
- PAO-R36 public correction semantics.

---

# Appendix A. Repository Evidence Register

| Repository evidence | Finding |
|---|---|
| `docs/system-design-decisions/policyos-identity-and-custody-boundary.md` | PolicyOS is lifetime justification custodian; PolicyMatter identity is OWN; anti-ERP boundary. |
| `AGENTS.md` | Reuse-first, capability-reality labels, complete evidence chain. |
| `CONTRIBUTING.md` | Typed boundaries, test and compatibility discipline. |
| Wave-2 backlog | PAO-R0 is Stage-0 identity anchor; Group C extends PDC identity/export boundary. |
| Wave-1 distillation | Shared admission, weakest-boundary, append-only deltas and perturbation cascades. |
| PDC compiler | Runtime graph is run/job/tenant scoped and structural, not matter identity. |
| PDC projection test | Projection derives from graph and remains projection-only. |
| PDC anti-laundering test | LLM candidates cannot become claim authority directly. |
| PDC record registry | Typed record families required; status-only pass rejected. |
| Tenant/CAS governance | Current authority records bind case, run, job and tenant. |
| Artifact ID | Stable content-address ABI, not real-world identity. |
| Artifact manifest | Immutable lineage, producer, tenant, closure, authority and integrity metadata. |
| IR artifact lineage | Technical artifact/task lineage only. |
| Runtime lineage API | Tenant, valid/transaction time, export and fail-closed projection primitives. |
| Decision validity | Decision lineage reacts to law/data/context change; not lifetime matter. |
| Scientist lifecycle bridge | Append-only lifecycle transitions and unscoped-event blockers. |
| Reissue packet | Original/new linkage without mutation. |
| Lifecycle tests | Partial reissue and projection-only public state; missing scope blocks. |
| Lex source/version contracts | Legal source identity, versions, effective time and provenance. |
| Lex version index | Deterministic version selection and quality warnings. |
| Core audit | Portable deterministic audit and offline verification. |
| DDM | Incident and shift evidence producer, not matter identity owner. |
| PolicyPortfolio ADR/code/test | Candidate portfolio analysis; not deployed stock or lifetime identity. |
| Ownership map | PDC and runtime-quality ownership neighborhood; reuse and capability-chain requirements. |
| Retention/recovery | Immutable audit/signature retention and historical verification obligations. |
| Honest diagnostics decision | Append-only supersession and projection-not-authority rule. |

# Appendix B. External Source Register

Access date for all sources: **2026-07-26**.

| Source | Type | Standing | Claim supported | Limitation |
|---|---|---|---|---|
| W3C PROV Data Model / Ontology | Web standard | Primary | Entities, activities, agents, provenance and derivation | Domain identity rules remain external. ([W3C](https://www.w3.org/TR/2012/CR-prov-dm-20121211/)) |
| W3C PROV Constraints | Formal standard | Primary | Consistency and validation constraints | Does not adjudicate policy sameness. ([W3C](https://www.w3.org/TR/2013/REC-prov-constraints-20130430/)) |
| OASIS LegalDocML / Akoma Ntoso | Legal-document standard | Primary | Legal document lifecycle and work/expression/manifestation distinctions | Instrument identity, not policy-matter identity. ([OASIS](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0-part1-vocabulary.html)) |
| European Legislation Identifier | Government/legal interoperability standard | Primary | URI and metadata framework for legislation | Does not establish cross-instrument policy continuity. ([Publications Office of the EU](https://op.europa.eu/en/web/eu-vocabularies/eli)) |
| ICA Records in Contexts Ontology 1.1 | Archival standard | Primary | Archival records and contextual entities/relations | Archival context does not confer policy authority. ([ICA-EGAD](https://ica-egad.github.io/RiC-O/about.html)) |
| PREMIS Data Dictionary | Digital-preservation standard | Primary | Preservation objects, events, agents, rights and relationships | Preservation identity differs from policy identity. ([The Library of Congress](https://www.loc.gov/standards/premis/v3/)) |
| DataCite Metadata Schema | PID metadata standard | Primary | Typed version, part, continuation and relation vocabulary | Relation semantics depend on the steward. ([DataCite Support](https://support.datacite.org/docs/connecting-to-works)) |
| ARK identifier guidance | Persistent-identifier convention | Primary | Opaque naming and persistence commitments | Identifier syntax cannot guarantee institutional persistence. ([ARK Alliance](https://arks.org/about/ark-overview/)) |
| DOI Foundation guidance | Persistent-identifier governance | Primary | Non-reassignment, one referent, metadata and transfer continuity | Does not determine matter granularity. ([ARK Alliance](https://arks.org/about/ark-features/)) |
| Fellegi–Sunter record linkage | Statistical method | Primary research | Link/non-link/possible outcomes under error assumptions | Statistical match is not sovereign identity. ([Tandfonline](https://www.tandfonline.com/doi/abs/10.1080/01621459.1969.10501049)) |
| Sadinle Bayesian record linkage | Statistical method | Primary research | Explicit uncertainty and unresolved linkage | Requires external authority for public identity. ([Tandfonline](https://www.tandfonline.com/doi/abs/10.1080/01621459.2016.1148612)) |
| Bitemporal data research | Formal temporal model | Primary research | Valid-time and transaction-time history | Does not determine identity. ([ResearchGate](https://www.researchgate.net/publication/220967503_Unification_of_Temporal_Data_Models)) |
| Event sourcing | Engineering design pattern | Canonical secondary | Append-only events and state reconstruction | Aggregate boundary must already be chosen. ([martinfowler.com](https://www.martinfowler.com/eaaDev/EventSourcing.html)) |
| GLEIF legal-entity events | Official registry model | Primary | Name change, mergers, demergers, spinoffs and event status | Legal entities differ from policies. ([Home – GLEIF](https://www.gleif.org/ontology/pylodev2/GLEIF_L1.html)) |
| OMB federal assistance listings / inventory evidence | Government registry | Primary | Official program/listing identifiers and attributes | Administrative inventories can be incomplete or use inconsistent granularity. ([fpi.omb.gov](https://fpi.omb.gov/about/fpi)) |
| RFC 7089 Memento | IETF standard | Primary | Historical web representations and time-based access | Resource representation history is not policy identity. ([RFC Editor](https://www.rfc-editor.org/rfc/rfc7089.html)) |

# Appendix C. Identity Decision Tables

## C.1 Same matter versus new matter matrix

| Objective | Mechanism | Population/scope | Competent continuity evidence | Safe outcome |
|---|---|---|---|---|
| Same | Same | Same | Present | Same matter/version or episode |
| Same | Same | Expanded | Present | Same matter scale episode, with evidence-scope review |
| Same | Changed within intervention family | Similar | Present | Same or derived; human review |
| Same | Materially different | Same | Present | Successor/derived; identity contested until adjudicated |
| Materially changed | Same | Same | Present | Successor/new presumption |
| Same | Same | Same | Absent | Unresolved; similarity cannot upgrade |
| Different | Different | Different | Shared name only | Definitely unrelated |
| Same | Same | Same | Explicit split | Parent plus new children |
| Combined from two | Combined | Combined | Explicit merger | New merged matter plus parents |
| Similar after repeal gap | Similar | Similar | Weak/ambiguous | Successor/new/unresolved, not automatic same |

## C.2 Authority-of-assertion matrix

| Actor/source | May assert | May not establish alone |
|---|---|---|
| Legislature or legally competent executive | Legal authorization, replacement, succession, split/merge within competence | Scientific evidence applicability |
| Official program registry | Registry identity and metadata within its scope | Cross-registry or lifetime policy identity |
| Successor institution | Mandate transfer if legally authorized | Retroactive scientific continuity |
| Records/archive authority | Record provenance and archival context | Policy objective/mechanism continuity |
| PolicyOS human adjudicator | PolicyOS custody mapping and authority ceiling | Sovereign legal effect outside delegation |
| PolicyOS automated matcher | Candidate matches and contradictions | Authoritative identity |
| Public statement | Corroboration | Competence or legal continuity |
| Shared text/name/URL | Candidate retrieval | Any authority upgrade |

## C.3 Temporal correction rules

| Situation | Current view | Historical view | Authority action |
|---|---|---|---|
| Late continuity evidence | May attach prior cases now | Prior view remains unresolved | Revalidation |
| Wrong historical merge | Current matters separated | Old merged view reproduced as historically known | Public correction and impact review |
| Wrong historical split | Current continuity asserted | Old separate IDs remain resolvable | Reconciliation, no deletion |
| Retroactive legislation | Valid-time graph changes from legal effective date | Transaction history shows later admission | Materiality review/recompute |
| Public-record correction | Corrected record current | Original record retained and marked corrected | Public notice |
| Revoked continuity assertion | Current view unresolved or distinct | Old assertion visible with revocation | Authority downgrade |
| Successor instrument | Current legal link points to successor | Prior instrument remains historically effective | Legal revalidation |
| Matter split | Children current for later scope | Parent remains for earlier history | Evidence-scope review |

## C.4 Fail-closed behavior

| Missing or conflicting element | Required result |
|---|---|
| Tenant/namespace | Block |
| Jurisdiction scope | Block authority-bearing use |
| Competent authority | Unresolved/candidate-only |
| Provenance | Block |
| Effective or transaction time | Block historical/current publication |
| Split/merge evidence | Keep matters separate |
| Correction relation | Do not replace current lineage silently |
| Human adjudication for material conflict | Review required |
| Evidence-scope review | No inherited evidence authority |
| Cross-tenant federation evidence | No cross-tenant association |

# Appendix D. PolicyMatterCompatibilityFreeze

**Standing:** Immediately binding as a Stage-0 research guard.

**Expiry:** Only after ratification of a canonical contract, P27 owner review, frozen benchmark success, migration replay, and PAO-R1/OPS-R15 consolidation.

| ID | Protected rule | Risk prevented | Current repository surface affected | Binding now | Evidence permitting change |
|---|---|---|---|---|---|
| PMF-01 | `case_id` is not lifetime policy identity | Case/run fragmentation and false continuity | PDC, runtime quality, public revision state | Yes | Ratified contract proving an equivalent higher identity already exists |
| PMF-02 | `decision_lineage_key` is not matter identity | One decision lineage mistaken for policy lifetime | Decision validity, monitoring | Yes | Formal semantic redesign and migration proof |
| PMF-03 | `policy_id` and `portfolio_id` are owner-local | Identifier collision and PolicyPortfolio misuse | IR, PolicySpec, evidence portfolio | Yes | Explicit owner-specific identity ADR |
| PMF-04 | Matter references must be extensible | Irreversible case-only schemas | PDC records, exports, H2 artifacts | Yes | Final `MatterSubjectRef` contract |
| PMF-05 | Matter ID must be opaque and non-reassignable | Rename/agency/instrument changes breaking IDs | Future PDC identity owner | Yes | Independent identifier-governance review |
| PMF-06 | Issuer/namespace must be explicit | Cross-tenant collision | Security, CAS, imports | Yes | Federated namespace protocol |
| PMF-07 | Tenant and jurisdiction context must remain explicit | Authority leakage | PDC, Lex, runtime HTTP | Yes | No removal expected; only refinement |
| PMF-08 | Current tenant/agency cannot be embedded as immutable semantics | Institutional transition breaks identity | Identifier format | Yes | Proven invariant across supported jurisdictions |
| PMF-09 | One matter must support many cases | Redesign/revalidation treated as new policy | PDC and H2 | Yes | No expected reversal |
| PMF-10 | Scoped one-case-to-many-matter attachment must not be structurally impossible | Composite policy cases forced into false identity | PDC graph | Yes | Ratified rule forbidding multi-matter cases |
| PMF-11 | Split and merge are first-class | History loss and alias collapse | PDC lineage, H2 | Yes | No expected reversal |
| PMF-12 | Legal instruments are many-to-many with matters | One-law-one-policy false model | Lex/PDC bridge | Yes | No expected reversal |
| PMF-13 | Identity assertions are typed, versioned and provenance-bearing | Generic metadata becomes authority | Runtime quality, CAS | Yes | Final assertion contract |
| PMF-14 | Similarity is candidate-only | Silent false merge | Matchers, search, LLM workflows | Yes | No automatic exception permitted |
| PMF-15 | Unresolved and contested states must be representable | Forced false binary | PDC, Atlas grammar inputs | Yes | No expected reversal |
| PMF-16 | Corrections append and supersede | Historical rewrite | CAS, audit, lifecycle | Yes | No expected reversal |
| PMF-17 | Valid/effective, observation/admission and transaction times must be preserved | Retroactive leakage into history | Temporal APIs, lineage, exports | Yes | OPS-R4 may refine fields, not remove semantics |
| PMF-18 | Signed legacy artifacts must not be mutated | Signature and replay invalidation | CAS, audit, public packets | Yes | No expected reversal |
| PMF-19 | Legacy identifiers remain resolvable | Broken citations and audits | URLs, exports, caches | Yes | Approved retention/archival policy |
| PMF-20 | Corrected current projection must coexist with historical view | Silent rewrite | Atlas, runtime lineage | Yes | No expected reversal |
| PMF-21 | Matter continuity does not imply evidence applicability | Evidence inflation after scale/split | Evidence synthesis, claims, validity | Yes | Separate transportability/scope certificate |
| PMF-22 | Parent provenance survives split/merge | Incident and performance-history evasion | Lineage, public history | Yes | No expected reversal |
| PMF-23 | Cross-tenant equality requires explicit admitted assertion | Security and authority leakage | Tenant CAS, imports | Yes | Federated trust protocol |
| PMF-24 | Atlas is projection-only | UI mints identity | Atlas DS3/DS4/DS12/DS18 | Yes | No expected reversal |
| PMF-25 | PolicyPortfolio remains candidate-analysis IR | Duplicate lifetime owner | IR loading/portfolio | Yes | New ratified ADR with P27 proof |
| PMF-26 | PDC is the presumptive canonical owner | Duplicate contract family | `src/polisyos/pdc`, runtime quality | Yes | Repository-wide P27 decision showing extension is semantically wrong |
| PMF-27 | H2 custody runtime is a consumer, not automatic identity owner | Workflow subsystem becomes contract gravity well | Future OPS implementation | Yes | Ratified architecture decision |
| PMF-28 | Public corrections require matter-aware links | Wrong matter remains publicly current | Atlas/publication/PAO-R36 | Yes | Final correction contract |
| PMF-29 | Every authority-bearing artifact must support resolved, unresolved or contested subject closure | Publication before identity closure | PDC closeout and signing | Yes | Ratified alternative with equivalent fail-closed behavior |
| PMF-30 | Identifier values must not be derived from mutable labels or external URLs | Reassignment and privacy risk | Future ID generator | Yes | No expected reversal |

# Appendix E. Proposed Fixture Catalogue

| Fixture ID | Scenario | Expected outcome | Failure patterns tested |
|---|---|---|---|
| PM-ID-001 | Same name, unrelated authorities | Two matters | P05, P10, P14 |
| PM-ID-002 | Rename only | Same matter, alias version | P10 |
| PM-ID-003 | Pilot formally scaled nationally | Same matter scale episode | P08, P10 |
| PM-ID-004 | Failed pilot replaced under same name | Successor/derived/new | P05, P14 |
| PM-ID-005 | Ministry dissolved, mandate transferred | Same matter institutional episode | P13 |
| PM-ID-006 | Repeal and replacement, same objective | Successor instrument pending substantive review | P10, P12 |
| PM-ID-007 | Reenactment after multi-year gap | Successor/new/unresolved | P10 |
| PM-ID-008 | One matter splits into two populations | Parent plus two children | P14, P27 |
| PM-ID-009 | Two matters merge | New merged ID plus parents | P14 |
| PM-ID-010 | One instrument authorizes three matters | Three scoped links | P10 |
| PM-ID-011 | One matter has four instruments | One matter, four links | P10 |
| PM-ID-012 | Municipal pilot becomes national program | Same/derived based on evidence | P08, P12 |
| PM-ID-013 | Territorial boundary changes | Same matter, versioned scope | P32 |
| PM-ID-014 | Objective materially changes | Successor/new | P10 |
| PM-ID-015 | Mechanism materially changes | Human adjudication | P10, P14 |
| PM-ID-016 | Population expands substantially | Scope review; same/split/new | P14 |
| PM-ID-017 | Similar agencies independently launch programs | Separate matters | P05 |
| PM-ID-018 | Same external ID in two tenants | Separate namespace refs | P26, P33 |
| PM-ID-019 | Legacy case with weak evidence | Unresolved/unassigned | P26 |
| PM-ID-020 | Historical false merge discovered | Append-only correction and separation | P12, P32 |
| PM-ID-021 | Historical false split discovered | Reconciliation assertion, old IDs preserved | P12, P32 |
| PM-ID-022 | Public record linked to wrong matter | Public correction/supersession | P03, P15 |
| PM-ID-023 | Signature valid, association invalid | Integrity valid; authority blocked | P10, P15 |
| PM-ID-024 | Malicious merge for favorable evidence | Block, incident, human review | P13, P14, P33 |
| PM-ID-025 | Malicious split to evade incident history | Block; predecessor history retained | P13, P14 |
| PM-META-001 | Rename metamorphism | Identity unchanged | P10 |
| PM-META-002 | Add irrelevant similar documents | No authority upgrade | P05 |
| PM-META-003 | Remove decisive continuity declaration | Downgrade to unresolved | P10, P26 |
| PM-META-004 | Change URL | Identity unchanged | P10 |
| PM-META-005 | Split with unrestricted evidence copy | Test must fail | P14 |
| PM-META-006 | Merge with parent deletion | Test must fail | P14, P32 |
| PM-META-007 | Correct assertion in place | Test must fail | P12, P32 |
| PM-META-008 | Replay before correction | Original view reproduced | P32 |
| PM-META-009 | Current view after correction | Corrected lineage shown | P03 |
| PM-META-010 | Candidate score crosses threshold | No authority change | P05, P15 |
| PM-MIG-001 | Legacy `case_id` gains matter sidecar | Original hash unchanged | P12 |
| PM-MIG-002 | Legacy `decision_lineage_key` retained | Remains decision lineage | P27 |
| PM-MIG-003 | Public URL remains resolvable | Historical and correction views available | P03 |
| PM-MIG-004 | Cache keyed only by `case_id` | Governance test fails | P08 |
| PM-MIG-005 | Cross-tenant import | Explicit federation required | P26, P33 |
| PM-MIG-006 | Clean rebuild vs incremental graph | Equivalent current view | P01, P02 |
| PM-MIG-007 | Dormant case resumes after matter correction | Identity and authority rechecked | P12, P32 |
| PM-MIG-008 | Matter split after published claim | Scoped revalidation, no blanket inheritance | P14 |
| PM-MIG-009 | Wrong matter correction after key rotation | Old signature still verifiable; semantic correction visible | P03, P15 |
| PM-MIG-010 | Disaster restore loses alias registry | Recovery test fails | P01, P03 |

---

# Final Research Posture

The strongest defensible result is **accepted_narrow_scope**:

> PolicyOS should own a stable, opaque, non-reassignable and namespace-qualified PolicyMatter identity because lifetime custody of PolicyOS signatures cannot be maintained solely through case, run, instrument, agency, program, publication, artifact, release, or decision identifiers. PolicyMatter should be a durable accountability and justification-lineage anchor. Design, enactment, implementation, evaluation, monitoring, incident, institutional, and public-record histories should remain distinct typed episodes and external objects. Continuity, succession, split, merger, correction, and revocation should be represented by versioned, provenance-bearing lineage assertions whose authority and temporal scope are explicit. Similarity may generate candidates but may not establish authoritative identity. Legacy cases and published artifacts must be attachable to the matter graph without changing their historical bytes or meaning. Same-matter continuity must never be treated as automatic evidence transport.

The need, bounded definition, repository owner, fail-closed posture, migration principle, and compatibility freeze are supportable. A fully automatic identity-resolution method is not.

[1]: https://support.datacite.org/docs/connecting-to-works
[2]: https://www.w3.org/TR/2012/CR-prov-dm-20121211/
[3]: https://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0-part1-vocabulary.html
[4]: https://www.tandfonline.com/doi/abs/10.1080/01621459.1969.10501049
[5]: https://www.researchgate.net/publication/220967503_Unification_of_Temporal_Data_Models
