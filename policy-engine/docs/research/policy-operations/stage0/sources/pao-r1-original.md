---
title: "PAO-R1 — Operational Boundary Census and Evidence-Contract Register"
status: delivered
kind: deep-research
research_task: PAO-R1
result_type: accepted_narrow_scope
repository: "https://github.com/DenisKopylov/polisyos"
repository_branch: main
repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
inspection_date: 2026-07-26
authoritative_for:
  - research-level application of the ratified four-way custody test
  - provisional OperationalBoundaryDecision register
  - candidate evidence interfaces for INTEGRATE functions
  - activation-review baseline for deferred Wave-2 functions
may_not_use_for:
  - capability claim
  - authority grant
  - legal delegation
  - final code contract
  - production implementation authorization
  - proof that an external institution performed its function
  - expansion of PolicyOS into administration
research_only: true
---

# PAO-R1 — Operational Boundary Census and Evidence-Contract Register

## Executive Finding

**Result: accepted_narrow_scope.**

The ratified four-way custody test can be operationalized consistently, but only when the unit of classification is not a broad noun such as “appeals,” “monitoring,” “records,” or “payments.” The correct unit is:

> one narrowly defined function × one PolicyOS claim at risk × one real operator × one evidence relationship × one downstream PolicyOS reaction.

This decomposition is load-bearing. An external appeal body may own appeal intake and adjudication; PolicyOS owns admission of the outcome as evidence, revalidation of its affected claims, and correction or supersession of its own records. A payment authority may own authorization, settlement, and reconciliation; PolicyOS may integrate signed evidence of those events but must not claim that it paid anyone.

The register therefore needs at least four distinct ownership fields, not one ambiguous owner:

1. the institution that performs the real-world function;
2. the producer of the evidence about that function;
3. the PolicyOS owner of admission and claim reaction;
4. the owner of the public projection.

This follows the repository’s ratified rule: PolicyOS owns everything it signs for while the signature stands, consumes what others sign as typed evidence, and must not claim functions it cannot custody. The same decision expressly excludes administration, case management, courts, legally effective notification, payments, and general enterprise operations.

### The four zones

| Zone | Defensible scope |
|---|---|
| **OWN core** | Policy design and grounding; evidence admission; authority-boundary derivation; PolicyOS signing and publication; staleness, revalidation, correction, reissue, supersession, withdrawal and historical replay of PolicyOS records; matter/case identity; provenance and audit; public verification; internal authorization; safe post-deployment learning. |
| **INTEGRATE perimeter** | Legal enactment and adjudication; administrative events; proof of service; implementation and service-delivery evidence; budgets and appropriations; procurement and suppliers; KPI observations; independent evaluations; appeal outcomes; remedies; payments; institutional succession; records and disclosure decisions; external identity, delegation and oversight evidence. |
| **OBSERVE zone** | Political context, institutional risk, local discretion, workarounds, capture signals, general oversight activity and unadmitted external status signals that inform awareness but do not yet alter claim validity. |
| **OUT_OF_SCOPE anti-roles** | Citizen case management; individual eligibility, risk scoring and sanctions; court or appeal adjudication; legally effective notification; payment execution; physical service delivery; staff scheduling; general procurement, HR, CRM, records-management or ERP operation; sovereign identity provision. |

The principal unresolved tension is competence and legal effect across jurisdictions. The same physical event—an email, registry entry, ministerial announcement, audit report, or administrative decision—may be legally binding, advisory, alleged, or irrelevant depending on the competent body, applicable law, timing and scope. A Stage-0 register can freeze the common evidence envelope and fail-closed rules now, but many operator mappings and legal-effect rules remain pilot- and jurisdiction-dependent.

A Stage-0 register is supportable because the repository already contains most of the necessary local owners: `AuthorityBoundary`, source contracts, Lex competence and temporal primitives, decision-validity events, append-only lifecycle and reissue records, audit archives, DDM incident and monitoring contracts, server-side authorization, and projection-only Atlas surfaces. What is absent is the shared function-level adjudication register and the bridges that bind external institutional evidence to those owners.

The source task for this report is the uploaded PAO-R1 research specification.

---

# 1. Task And Project Fit

## 1.1 Source task

| Field | Value |
|---|---|
| Backlog | Custody & Operations — Parallel Deep Research Backlog |
| Wave | Wave 2, Revision 2 |
| Task | PAO-R1 |
| Group | Group C — Boundary & Identity |
| Priority | Stage 0 bootstrap anchor |
| Owner | `team-architecture` |
| Governing decision | `policyos-identity-and-custody-boundary.md` |
| Suggested later path | `docs/research/policy-operations/pao-r1-operational-boundary-decision-register.md` |
| Standing | Research anchor; no code or repository changes |

The Wave-2 backlog defines PAO-R1 as the per-function application of the already-ratified four-way test and requires every INTEGRATE or OBSERVE row to name the external owner, typed evidence interface, provenance, versioning and fail-closed behavior. It also identifies an INTEGRATE row without absence behavior as a direct falsifier.

## 1.2 Exact question

How should PolicyOS apply the ratified four-way custody test function by function and maintain a provisional `OperationalBoundaryDecision` register that distinguishes what PolicyOS owns, what it integrates through typed evidence contracts, what it merely observes, and what remains outside scope?

This report does not reopen the system’s high-level identity. It operationalizes it.

## 1.3 Why research must precede implementation

Without a common register, two individually plausible implementations could assign the same function differently:

- one team could interpret an appeal outcome adapter as an “appeals subsystem”;
- another could disclaim responsibility for revalidating PolicyOS claims after an appeal;
- a dashboard could display “payment complete” from an unverified payload;
- a generic task queue could grow into an administrative case-management system;
- a legal source could be correctly ingested but never connected to the claims it invalidates;
- a surface could imply that an observed external state is admitted authority;
- several local “evidence contracts” could duplicate one another beside Fabric, Lex, DDM or PDC owners.

The repository’s capability doctrine rejects such partial chains: a capability requires a typed contract, real producer, persisted artifact or event, bridge, consumer, verification, surface or explicit exclusion, and a semantic negative test.

## 1.4 False claims prevented

The register is designed to make the following claims structurally impossible:

- “PolicyOS manages the complete policy lifecycle.”
- “PolicyOS resolved the appeal.”
- “PolicyOS verified legal service” when it received only a send-status payload.
- “PolicyOS compensated affected persons” when compensation was merely recommended or authorized.
- “PolicyOS owns statutory deadlines” when an external procedure calculates and enforces them.
- “PolicyOS delivered the service” when an Atlas row displays an external delivery status.
- “This external event is outside scope” when its absence would silently invalidate a PolicyOS signature.
- “The audit passed” when PolicyOS merely produced an audit package rather than an independent auditor’s conclusion.

## 1.5 Four-way boundary verdict for PAO-R1 itself

The operational-boundary register is **OWN**, narrowly. Without a consistent register, PolicyOS cannot truthfully state what it does and does not sign for, which external events affect its claims, or why its system stopped, limited, corrected or withdrew a result. The register is therefore part of the custody promise.

PolicyOS does not thereby own the institutional functions listed in the register. It owns:

- the boundary decision concerning its own claims;
- the typed intake and admission rules;
- fail-closed behavior;
- downstream claim reaction;
- accurate public representation of the boundary.

## 1.6 Relationship to PAO-R0 and OPS-R15

PAO-R0 supplies the candidate lifetime `policy_matter_ref` to which future boundary events may attach. PAO-R1 treats that reference as an `external_dependency_assumption`; it does not redefine PolicyMatter identity. The separate PAO-R0 task requires matter identity, non-linear episode history, disputed lineage and a compatibility freeze against treating `case_id` as lifetime identity.

OPS-R15 consumes the boundary vocabulary in its 18–24 month custody-cycle benchmark. The backlog already requires administrative events to enter only as integrated evidence and sets `out_of_boundary_actions_attempted = 0`.

---

# 2. Current Repo Baseline

## 2.1 Inspection record

| Item | Finding |
|---|---|
| Repository | `DenisKopylov/polisyos` |
| Branch | `main` |
| Commit | `4813b49f6ce14e8debf3aaea096f0967d38d9768` |
| Inspection date | 2026-07-26 |
| Branch completeness | The commit-pinned main tree and the requested core paths were accessible. A local uncommitted working tree was not available for inspection. |
| Local `rg` | A local clone was attempted for repository-wide `rg`, but the execution environment could not resolve GitHub DNS. Repository-wide search therefore used the commit-pinned GitHub connector, followed by direct file retrieval. |
| Missing/renamed path | The requested `honest-diagnostics-substrate.md` was not present under that name. The current live artifact is `honest-diagnostics-substrate-decision-log.md`; the former implementation plan is archived. |
| Search-only reliance | Negative conclusions—especially absence of payment, notification or service-delivery operators—are based on repository connector search plus direct inspection of returned matches, not a claim of formal exhaustive absence. |
| Modification | No repository files were changed. |

The inspected commit is the revision that ratified the custody boundary and reshaped Wave 2.

## 2.2 Paths inspected

The baseline included:

- `AGENTS.md`;
- `policy-engine/CONTRIBUTING.md`;
- all requested identity, architecture and operating-model decisions;
- the failure-pattern register;
- Wave-1 backlog and distillation;
- Wave-2 backlog;
- retention and recovery;
- GY and Atlas active plans;
- `src/polisyos/pdc`;
- `src/polisyos/runtime/quality`;
- `src/polisyos/core/audit`;
- `src/polisyos/core/artifacts`;
- `src/polisyos/runtime/http` authorization and audit paths;
- `src/polisyos/fabric/connectors/contracts`;
- `src/polisyos/lex`;
- `src/polisyos/ddm`;
- `src/polisyos/scientist/governance/continuous`;
- PolicyPortfolio IR and ADR-0022;
- representative unit, semantic, lifecycle, authorization and public-projection tests.

The project’s import rules place PDC at the narrow waist, allow runtime quality to import engines and external adapters, and prohibit lower layers from depending on upper product layers.

## 2.3 Existing authority-boundary representation

The canonical `AuthorityBoundary` already separates:

- `authoritative_for`;
- `may_not_use_for`;
- evidence kind;
- decision grade;
- authority posture;
- source-authority references;
- rule and limitation references.

Composition intersects permitted uses, unions prohibited uses and takes the weakest decision/evidence boundary. This is exactly the mechanism the operational register should feed rather than replace.

The GY acceptance bar further requires verifier-derived authority, forbids agent writes to Ring-2 fields, and rejects surface or workflow outputs that look authoritative without the underlying authority path.

**Capability label:** implemented.

**Boundary implication:** PAO-R1 must not create a second OWN/INTEGRATE/OBSERVE status lattice. Its verdict is a governance assertion that determines which producer and boundary rules apply; final admissibility remains in the one PolicyOS authority grammar.

## 2.4 Existing evidence-interface patterns

### Fabric source contracts

Fabric’s `SourceContract` already carries:

- source and organization identity;
- schema and semantic IDs;
- security classification, tenant scope and field-level access;
- quality requirements;
- freshness and availability targets;
- permitted and prohibited uses;
- replay evidence;
- lineage;
- trust and calibration status;
- retention;
- deprecation and replacement information.

An active contract fails validation without schema evidence, quality references, replay posture, lineage and idempotency policy.

**Capability label:** implemented, but primarily data-source oriented.

**PAO-R1 implication:** reuse its envelope disciplines but do not force legal determinations, proof of service, payments or appeal outcomes into tabular dataset semantics. The shared pattern is one admission port with family-native payloads.

### Legal authority and competence

Lex distinguishes a retrieved legal source from:

- authority type;
- competent actor;
- permitted instrument;
- legal hierarchy;
- jurisdiction;
- effective time;
- fiscal or implementation authority;
- supersession and appeal relations.

A legal hit is candidate material until authority, competence and time are resolved. Lex can establish legal-source and applicability evidence; it cannot prove actual budget availability, implementation performance, participation or the merits of an appeal.

**Capability label:** legal sensing largely implemented; continuous amendments, generic jurisdiction packs and some bridges remain `implemented_but_not_orchestrated` or `bridge_missing`.

### Appeal and contestability evidence

ADR-0170 explicitly separates PolicyOS-owned contestability records and outcome ingestion from externally owned appeal intake, adjudication, standing, timelines, remedy powers and execution. PolicyOS may state the pointer, evidence status and effect on its claims; it may not state that it adjudicated the appeal or that an external remedy was adequate.

The repository also contains runtime-owned provenance wrappers for external appeal and implementation evidence. “Runtime-owned” here means PolicyOS owns the wrapper, not the event. This terminology is potentially misleading unless the boundary register separately identifies event owner, evidence producer, adapter owner and claim-reaction owner.

**Capability label:** `partial_internal_owner` plus `missing_internal_bridge` for real institutional partners.

### Decision validity

The decision-validity contract already represents append-only dependency events and transitions for:

- law, source, dataset, schema, model and metric invalidation;
- contradictory evidence;
- context drift;
- post-deployment refutation;
- expert and human gates;
- supersession and revocation.

It records occurrence and recording times, affected dependency keys, current status and recommended action.

**Capability label:** `implemented_but_not_orchestrated` for the full lifetime custody loop.

### KPI and monitoring records

`DecisionMonitoringContract`, `MonitoredMetric`, monitoring reports and human-gated reissue plans already exist. They distinguish baselines, ranges, observation counts, verdicts and recalibration targets. They do not yet constitute the full OPS-R5 KPI control and diagnosis protocol.

**Capability label:** `partial_internal_owner`.

### Audit and authorization

`core.audit` assembles deterministic portable archives from CAS artifacts and verifies signatures, integrity and provenance offline. It owns PolicyOS audit packages, not the independent auditor’s professional conclusion.

Runtime authorization writes append-only allow/deny events with subject, tenant, permission, resource binding, step-up outcome and OPA reasons. An allow-path audit failure blocks execution, but the event explicitly records authorization admission—not success of the handler or the external institutional action.

**Capability label:** internal authorization implemented; external administrative authority remains evidence to integrate.

### Public audit and projection

The public audit record requires a verified core package, public references with digests and verification without private operator context. Its PDC surface must remain `projection_only`; otherwise validation emits `external_audit_policy_design_case_surface_mints_authority`.

Atlas’s constitution likewise states that Atlas renders the authority system and never produces authority.

**Capability label:** core projection doctrine implemented; many outward surfaces remain `surface_missing`.

## 2.5 Existing tests and fixtures expressing boundary behavior

The reusable test patterns include:

- non-verifier writers cannot set authoritative fields;
- candidate or failed workflows cannot reach authority surfaces;
- an appeal pointer without a competent, reachable process fails;
- an unscoped lifecycle event produces a blocker rather than mutating claims;
- partial reissue preserves unaffected claims;
- public projections cannot mint authority;
- missing step-up or action permission denies execution;
- inactive or unverifiable source contracts fail admission;
- old records are superseded, not rewritten;
- external audit archives must verify independently;
- stale or revoked dependencies move decisions into review or revalidation.

These are strong seeds for a future boundary benchmark, but there is no single test corpus that asks whether the function’s institutional owner and PolicyOS’s epistemic reaction have been classified correctly.

## 2.6 Negative repository findings and misleading language

### No current `OperationalBoundaryDecision`

Commit-pinned repository search returned no implemented `OperationalBoundaryDecision` symbol or canonical function-level register.

**Capability label:** `contract_only` as a research concept; `producer_missing`, `bridge_missing`, `surface_missing` and `semantic_test_missing`.

### “Compensation” name collision

The repository’s `scientist/orchestration/engine/compensation.py` implements saga-style rollback compensation for failed workflow tiers. It is not public compensation, damages, reimbursement or payment to affected people. A boundary register must prevent this software-engineering term from being surfaced as institutional remediation capability.

### Notification search

Repository search for “notification” returned identity documents, plans and UI toast infrastructure, not a production legally effective notification or proof-of-service subsystem.

### Payment search

Repository search for “payment” returned mechanism models, research corpora, obligation rules and planning material, not an operational payment execution or settlement system.

### Service-delivery search

“Service delivery” appears in architecture and research descriptions, but no inspected module owns end-to-end citizen service operation. These negative findings reinforce the anti-role boundary. They do not prove that no future integration is needed.

## 2.7 Current owner and capability summary

| Boundary capability | Canonical owner | State |
|---|---|---|
| Purpose-scoped authority | PDC | implemented |
| External-source admission | Fabric + runtime quality | implemented, data-focused |
| Legal sensing and competence | Lex | implemented_but_not_orchestrated for continuous living law |
| Monitoring and incident evidence | DDM + feedback contracts | partial_internal_owner |
| Claim lifecycle and reissue | Scientist continuous governance + decision validity | implemented_but_not_orchestrated |
| PolicyOS audit package | Core audit | implemented |
| Internal user/action authorization | Runtime HTTP / DS20 | implemented |
| Human decision and delegation | PDC/runtime quality/DS9 | contract_only to partial_internal_owner |
| Public projection | Atlas projection doctrine | implemented; surfaces staged |
| Institution-specific external evidence | No generic cross-family register | bridge_missing |
| Operational boundary register | Team architecture research owner | contract_only |
| Lifetime custody orchestration | Future H2 runtime | producer_missing / future consumer |

## 2.8 Research blockers

1. Competent operator and legal effect vary by jurisdiction.
2. Institutional systems, identifiers and signatures are unknown until a pilot partner exists.
3. Some external evidence is binding; some is advisory, alleged or merely reported.
4. Administrative, public-record and privacy duties may conflict.
5. One physical event can affect several lifecycles differently.
6. A function’s legal operator may change through reorganization.
7. Some institutional facts are not externally verifiable in real time.
8. It remains unsettled which party has final authority to ratify a production boundary decision across institutions.

## 2.9 Engineering blockers

1. No canonical register producer.
2. No shared discriminated-union port for non-data institutional evidence.
3. No boundary-decision impact graph.
4. No function-level semantic benchmark.
5. No uniform external competence verification.
6. No generic correction/revocation adapter across external evidence families.
7. No Atlas projection for “external operator / evidence status / PolicyOS reaction.”
8. No fleet-level wake and revalidation orchestration.
9. No partner-specific identity and trust federation.
10. No production `policy_matter_ref` yet; PAO-R0 remains an external dependency.

## 2.10 Smallest reuse-first path

1. Keep the register as a versioned research artifact owned by `team-architecture`.
2. Reuse PDC `AuthorityBoundary` as the only authority grammar.
3. Reuse Fabric’s source-contract envelope for common identity, security, quality, replay, lineage and retention fields.
4. Keep family-native evidence payloads in Lex, DDM, audit, authorization, records and institutional adapters.
5. Use runtime quality as the admission and downgrade ring.
6. Use decision validity and continuous governance for downstream reactions.
7. Use core audit for custody events and external verification bundles.
8. Use Atlas only for projection.
9. Let future H2 orchestrate waits, wakes and impacts without becoming the owner of external administration.
10. Build no administrative case-management, payment, notification, procurement or service-delivery subsystem.

This is the repository’s own M30 pattern: a thin shared admission port with family-native payloads, not one merged theorem or score.

---

# 3. External Research Baseline

## 3.1 Accountability models

Bovens defines accountability as a relationship between an actor and a forum in which the actor must explain and justify conduct, the forum can question and judge, and consequences may follow. This supports separate register fields for the real operator, responsible authority, reviewing forum and downstream consequence; an evidence adapter is not the actor that performed the underlying function. (DOI)

Koppell distinguishes transparency, liability, controllability, responsibility and responsiveness and warns that conflicting expectations can produce “multiple accountabilities disorder.” This supports the repository’s rule that legal authority, operational capacity, contestability, public transparency and technical evidence are non-fungible lanes. (Wiley Online Library)

**PolicyOS authority delta:** provenance must state who acted, but the boundary register must additionally state who was legally competent, which claim the act may affect, and which responsibility remains external.

## 3.2 Provenance

W3C PROV distinguishes entities, activities, agents, roles, attribution and acting on behalf of another agent. It can show that an institution generated an appeal outcome and that PolicyOS consumed it, without implying that PolicyOS performed the adjudication. PROV does not by itself determine legal competence or evidentiary sufficiency. (W3 DVCS)

**PolicyOS authority delta:** add competence, scope, binding status, authority boundary, evidence admission and fail-closed semantics.

## 3.3 AI governance roles

The EU AI Act distinguishes provider, deployer, competent authority and natural persons assigned human oversight. Deployers must assign oversight to persons with competence, training and authority, monitor use, suspend risky operation and inform providers and authorities; providers retain distinct serious-incident investigation and reporting duties. The same regulation locates complaints and individual explanations with competent authorities and deployers rather than with an abstract AI system. (EUR-Lex)

NIST’s AI RMF is voluntary and organizes risk management around organizational governance, lifecycle processes, assigned competencies and third-party dependencies. It does not transfer the deploying institution’s duties to a technical evidence system. (NIST AI Resource Center)

**PolicyOS authority delta:** identify whether PolicyOS is the provider of an evidence artifact, an internal deployer of an analytical operation, or merely a consumer of an external institutional event. Do not collapse those roles.

## 3.4 Service ownership

The UK Government Functional Standard assigns the service owner accountability for the whole end-to-end service, including digital and non-digital delivery, costs, customer relations, risk, transition and retirement. A policy-analysis system that displays a service metric is therefore not the service operator. (GOV.UK)

**PolicyOS authority delta:** integrate service-performance evidence and own its epistemic effect, while keeping delivery and service-management execution external.

## 3.5 Transparency records

The UK Algorithmic Transparency Recording Standard requires an operationally accountable senior responsible owner, internal clearance by the deploying or operating team, and updates when a pilot moves to production, datasets change or the operational process changes. A transparency record reports ownership and use; it does not perform the operation or certify its success. (GOV.UK)

**PolicyOS authority delta:** Atlas may project operator and evidence status but must not turn a transparency entry into proof of delivery, legality or effectiveness.

## 3.6 Legal notification and proof of service

Under eIDAS, qualified electronic time stamps and qualified electronic registered delivery services receive specified evidentiary presumptions concerning integrity, sender/recipient identification and time. A generic “sent” event lacks those properties and cannot automatically establish legally effective service. (EUR-Lex)

**PolicyOS authority delta:** separate notice generation, dispatch, delivery, qualified proof of service and legal effect; reject or limit claims when the required evidence class is absent.

## 3.7 Records, disclosure and legal hold

NARA-approved schedules determine federal records disposition, and mission records require agency-specific schedules. ICO guidance similarly places records creation, retention, destruction, disclosure and preservation within the public authority’s governance and legal duties; deleting or altering requested information may be unlawful, and records subject to complaints or appeals may need continued preservation. (National Archives)

GDPR separately imposes purpose limitation, minimization, accuracy and storage limitation for personal data. These duties belong to the competent controller, not automatically to a policy evidence runtime. (EUR-Lex)

**PolicyOS authority delta:** own retention, correction, verification and legal-hold reaction for PolicyOS artifacts; integrate institution-wide disposition, disclosure, subject-access, erasure and archival decisions.

## 3.8 Audit and oversight

ISSAI 100 distinguishes the auditor, responsible party and intended users and requires independence, professional judgment, evidence, reporting and follow-up. Producing a verifiable audit package is not equivalent to performing an independent public-sector audit. (ISSAI)

The European Ombudsman is an independent external body that investigates maladministration within a defined mandate and cannot question a court’s ruling. Its recommendations and inquiries remain institutionally distinct from the administration it reviews. (European Ombudsman)

**PolicyOS authority delta:** own the audit package and the reaction to external findings; integrate the auditor’s or ombudsman’s signed determination; never claim independent oversight merely because the evidence is stored.

## 3.9 Internal control and operational management

GAO’s 2025 Green Book assigns management responsibility for designing, implementing and operating internal control, including preventive controls and change assessment. A monitoring platform may supply evidence but does not replace management’s operational responsibility. (Government Accountability Office)

**PolicyOS authority delta:** own diagnostic and policy-claim reactions; integrate management-control evidence; do not claim control execution.

## 3.10 Procurement and public-sector AI

OECD public-procurement guidance treats procurement as a full institutional cycle with workforce, fiduciary, integrity and conflict-of-interest responsibilities. OECD’s public-sector AI work similarly identifies governance, data, infrastructure, skills, investment, procurement and partnerships as distinct enabling functions with their own operators and safeguards. (OECD)

**PolicyOS authority delta:** procurement, supplier selection and contract execution remain external; PolicyOS owns admission of supplier evidence, license/expiry dependencies and the effect on its claims.

## 3.11 Comparative boundary models

| Model | Assumed institutional setting | What it separates | Mapping to PAO-R1 | Limitation |
|---|---|---|---|---|
| Actor–forum accountability | Public administration and oversight | Actor, forum, judgment, consequence | Requires real operator and review forum fields | Does not define technical evidence contracts |
| Multiple-accountability typology | Hybrid/public organizations | Transparency, liability, control, responsibility, responsiveness | Prevents one “accountability score” | Does not resolve legal competence |
| W3C PROV | Cross-domain data/process provenance | Entity, activity, agent, role, delegation | Supports event/evidence/operator chains | Provenance does not establish authority |
| NIST AI RMF | Voluntary organizational AI risk management | Governance, lifecycle, third parties | Supports assigned owners and monitoring | Not a legal allocation of public powers |
| EU AI Act | Regulated AI provider/deployer ecosystem | Provider, deployer, oversight person, competent authority | Demonstrates non-transferable roles | Applies only within its legal scope |
| GovS 005 | Government service delivery | End-to-end service owner and delivery team | Keeps delivery external | UK organizational convention |
| ATRS | Public algorithmic transparency | SRO, operator, supplier, publication | Projection reports ownership but is not execution | Transparency does not prove performance |
| eIDAS | Trust services and electronic delivery | Sending, receiving, identification, time, qualified status | Separates message from proof of service | Legal effect depends on applicable law |
| ISSAI | Public-sector audit | Auditor, responsible party, user | Audit package ≠ independent audit | National mandates vary |
| NARA/ICO records | Public records administration | Records owner, schedules, disposition, disclosure | Institution-wide records remain external | Jurisdiction-specific |
| GAO Green Book | Government management controls | Management vs audit/monitoring | Monitoring evidence ≠ operation of controls | US federal setting |
| Ombudsman model | Independent complaint review | Administration vs independent reviewer | Appeal/review remains external | Mandates vary |

---

# 4. Result

## 4.1 Operationalization rule

The four-way test is usable when applied in this order:

```text
institutional function
  ↓ decompose into actual acts
real operator and legal authority
  ↓
PolicyOS claim potentially affected
  ↓
external act / evidence emission / evidence admission / claim reaction / public projection
  ↓
OWN / INTEGRATE / OBSERVE / OUT_OF_SCOPE
```

### Verdict rule

For a narrowly defined function `f` and PolicyOS claim `c`:

- **OWN** when absence of PolicyOS performing the narrow epistemic or custody function would make `c` silently false.
- **INTEGRATE** when an external operator performs `f`, but authenticated evidence about `f` can change the validity, scope or permitted use of `c`.
- **OBSERVE** when information about `f` affects context, accountability or risk awareness but does not alter `c` until a separate admission event occurs.
- **OUT_OF_SCOPE** when PolicyOS has neither a claim-validity role nor a legitimate evidence-interface role, or performance of `f` would violate an anti-role.

A broad function that appears to satisfy more than one verdict must be decomposed. Verdict mixing is evidence that the function is too broad.

## 4.2 Five function planes

| Plane | Typical verdict | Example |
|---|---|---|
| External institutional act | INTEGRATE or OUT_OF_SCOPE | Appeal adjudication |
| External evidence emission | INTEGRATE | Signed appeal outcome |
| PolicyOS evidence admission | OWN | Verify competence, scope, signature and time |
| PolicyOS claim reaction | OWN | Revalidate and correct affected claims |
| Atlas/public projection | OWN as projection discipline; never substantive authority | Display “outcome supplied by external body; claims under revalidation” |

## 4.3 Reusable adjudication protocol

### Step 1 — Define narrowly

Replace “appeals” with:

- intake;
- standing determination;
- adjudication;
- outcome publication;
- evidence ingestion;
- PolicyOS claim revalidation;
- remedy authorization;
- remedy execution.

### Step 2 — Identify the exact claim at risk

Examples:

- “This recommendation remains legally admissible.”
- “This public record is current as of date T.”
- “This service was delivered.”
- “Compensation was paid.”
- “This reviewer had authority.”
- “No qualifying incident has been reported.”
- “The evidence set is complete enough for the declared scope.”

### Step 3 — Determine who signed the claim

A claim about PolicyOS’s own publication state is generally OWN. A claim about another institution’s execution is external and can be made only within the admitted evidence boundary.

### Step 4 — Identify the real operator

Record:

- institution;
- system;
- legal or organizational authority;
- normal and degraded workflow;
- after-hours owner;
- dispute forum;
- successor operator.

### Step 5 — Apply the four-way test

Use the predicates above. Do not infer ownership from the existence of code, a task queue, a dashboard or a data connector.

### Step 6 — Map ownership separately

Record:

- `real_operator`;
- `owner_state`;
- `external_producer`;
- `policyos_adapter_owner`;
- `policyos_claim_reaction_owner`;
- `surface_projection_owner`.

### Step 7 — Define the evidence crossing

Every INTEGRATE row must name:

- family-native artifact or event;
- producer and institution;
- competence;
- subject and scope;
- provenance and signature;
- event, effective, observation, admission and transaction times;
- schema and rule version;
- correction, revocation and supersession links;
- permitted and prohibited uses.

### Step 8 — Define absence behavior

Missing evidence is never evidence that no event occurred. Determine whether absence means:

- unknown;
- limitation;
- quarantine;
- publication freeze;
- revalidation;
- human review;
- blocking;
- costed acquisition of the missing institutional evidence.

### Step 9 — Define downstream reaction

Choose the least expansive safety-preserving response:

1. annotate;
2. limit;
3. block or freeze;
4. open a new epoch;
5. revalidate;
6. recompute;
7. request human review;
8. correct, reissue, supersede or withdraw;
9. preserve historical-only state.

### Step 10 — Test anti-role inflation

Ask whether the proposal:

- turns an evidence adapter into the institutional operator;
- requires sovereign authority;
- duplicates an existing owner;
- is merely a projection of existing custody machinery;
- needs partner-specific facts not yet available.

### Step 11 — State confidence and trigger

Each row records:

- confidence;
- unresolved assumptions;
- pilot dependency;
- jurisdiction dependency;
- expiry or review trigger;
- superseded decision reference.

## 4.4 Owner-state model

| Owner state | Meaning |
|---|---|
| `existing_internal_owner` | A canonical PolicyOS owner already performs the narrowly defined OWN function. |
| `partial_internal_owner` | The canonical owner exists, but contracts, bridges, verification or scope are incomplete. |
| `missing_internal_bridge` | External producer and internal consumer exist, but no admitted runtime connection exists. |
| `external_institution_owner` | A named external authority or operator performs the function. PolicyOS may own only the interface and reaction. |
| `owner_unresolved` | No competent operator can be named without jurisdictional or pilot facts. |

This field is separate from implementation state. An external institution can be the clear owner while the PolicyOS adapter remains `producer_missing`.

## 4.5 Current implementation-state vocabulary

| Label | Use in this report |
|---|---|
| `implemented` | Complete enough for its present narrow scope |
| `implemented_but_not_orchestrated` | Local capability exists but is not in the custody workflow |
| `contract_only` | Type or research shape exists without complete runtime chain |
| `producer_missing` | No real producer emits the required record |
| `bridge_missing` | Producer and consumer exist but are not connected |
| `verification_missing` | Chain exists without adequate behavioral proof |
| `surface_missing` | Internal state cannot be inspected through the required surface |
| `semantic_test_missing` | Structural checks exist but function-level adequacy is untested |

## 4.6 Executive boundary map

| Function family | Default verdict | Important exceptions | Main external owner | PolicyOS-owned interface |
|---|---|---|---|---|
| Policy design and epistemic custody | OWN | Source facts and mandates remain external evidence | Source institutions, principals | PDC/RQ authority and design records |
| Legal sensing | OWN | Enactment, adjudication and official publication are external | Legislature, gazette, courts, agencies | Lex intake, applicability, competence and validity reaction |
| Administrative procedure | INTEGRATE or OUT | Internal PolicyOS review is OWN | Case-management authority | Procedure-event and proof-of-service evidence |
| Individual decisions | OUT_OF_SCOPE | Policy-level firewall and returned aggregate evidence are OWN/INTEGRATE | Competent administrative body | PAO-R4 export/use restrictions |
| Implementation and delivery | INTEGRATE | Feasibility analysis is OWN | Service owner, delivery body | Capacity and delivery-evidence admission |
| Monitoring and learning | Split OWN/INTEGRATE | Data collection is external; diagnosis and model update are OWN | Data and evaluation owners | KPI contract, diagnosis, safe update |
| Public records | OWN for PolicyOS records | Institution-wide records, FOI and legal hold are external | Records authority/controller | Own correction, archive linkage and verification |
| Appeals and incidents | INTEGRATE | Admission and PolicyOS correction are OWN | Appeal body, regulator, investigator | Outcome/incident intake and lifecycle cascade |
| Remedies and compensation | INTEGRATE | Recommendation may be OWN/advisory | Remedy authority, treasury, payment operator | Remedy evidence and claim correction |
| Institutional authority | INTEGRATE or OBSERVE | Internal PolicyOS decision rights are OWN | Appointing/mandating body | Competence/delegation verification |
| Procurement and suppliers | INTEGRATE | Supplier-evidence admission is OWN | Procurement authority, contract owner | Supplier dossier, escrow and expiry dependencies |
| Security and identity | OWN for PolicyOS boundary | Citizen/sovereign identity and external authority are INTEGRATE | IdP, competent public authority | Internal authentication, authorization, signing, audit |
| Infrastructure and resilience | OWN custody; INTEGRATE operation | Physical hosting may be outsourced | Hosting/provider operator | RPO/RTO, backup, restore, dependency evidence |
| Atlas surfaces | Projection only | No substantive exception | — | Source-bound, as-of, weakest-boundary rendering |

## 4.7 Evidence lifecycle

The following values describe the state of an evidence object, not a second authority lattice:

- `received`
- `verified`
- `admitted`
- `disputed`
- `corrected`
- `revoked`
- `stale`
- `superseded`
- `rejected`
- `historical_only`

The one Atlas/PDC authority grammar still determines whether a resulting claim is admissible, limited, contested, blocked or publishable.

## 4.8 Generic absence and failure grammar

| Condition | Evidence disposition | Default claim reaction |
|---|---|---|
| No evidence | missing/unknown | Never infer no event; limit or block load-bearing claim |
| Late evidence | late with original event time | Preserve historical view; assess retroactive materiality |
| Stale/expired | stale | Remove from current authority; revalidate |
| Malformed | rejected | Quarantine; no claim effect |
| Unsigned where signature required | unverified | Quarantine or reject |
| Contradictory producers | disputed | Weakest boundary; human or competent adjudication |
| Incompetent producer | rejected_authority | No authority effect; may remain historical provenance |
| Outside subject/jurisdiction/scope | scope_mismatch | Reject for the claim; do not broaden scope |
| Corrected | New evidence supersedes prior | Impact analysis, recomputation or public correction |
| Revoked | Prior authority removed | Freeze affected claim; revalidate/reissue/withdraw |
| External institution unavailable | unknown/stale | No assumption of non-occurrence; costed escalation or block |
| Outside certified envelope | out_of_envelope | Limitation, abstention or human decision |

## 4.9 Boundary-decision state and change semantics

Candidate register states:

- `proposed`
- `research_supported`
- `accepted_narrow_scope`
- `contested`
- `superseded`
- `blocked`
- `deferred_pending_pilot`
- `retired`

These are governance states for the register, not claim-authority states.

### Who may propose

- canonical subsystem owner;
- `team-architecture`;
- designated research owner;
- security, legal, records, privacy or institutional integration owner;
- a pilot partner through a documented challenge.

### Required review

A decision affecting public or authority-bearing behavior requires:

- `team-architecture`;
- the internal canonical owner;
- the real operator or institutional integration owner where available;
- domain review appropriate to legal, records, privacy, security, audit or finance consequences.

### Contradiction with the identity decision

A decision contradicts the ratified identity if it:

- assigns PolicyOS an anti-role;
- disclaims a claim-reaction function needed to keep its signature honest;
- treats receipt of evidence as performance of the act;
- permits an external act to alter claims without a fail-closed interface;
- uses projection or observation as authority.

### Challenge and supersession

A `BoundaryDecisionChallengeReceipt` should identify:

- challenged decision;
- counterexample;
- repository and institutional evidence;
- affected claims and surfaces;
- proposed narrower decomposition;
- requested interim safeguard.

A corrected decision creates a new immutable row with `supersedes_boundary_decision`. The old row remains historically visible.

### Review and expiry triggers

- new jurisdiction or institution;
- pilot activation;
- change of real operator;
- law, mandate or delegation change;
- new public claim or surface;
- incident or appeal exposing an incorrect boundary;
- evidence schema or admission change;
- repository canonical-owner change;
- scheduled quarterly review.

### Mass-impact boundary change

A boundary change is a mass-impact event when it changes:

- OWN ↔ INTEGRATE/OBSERVE/OUT;
- the required competent producer;
- absence behavior;
- permitted or prohibited use;
- the set of active/public claims depending on the row.

Such a change must freeze affected current claims and invoke the future OPS-R2 authority-dependency impact process.

## 4.10 Constraints on active Wave-2 tasks

| Task | Constraint supplied by PAO-R1 |
|---|---|
| INT-R1 | Obligation completeness must declare which external institutional functions and source classes were searched; unknown operators remain open-world remainder. |
| INT-R2 | Every non-data acquisition case must name whether PolicyOS acquires evidence, a human decision, a mandate or an external service—not the external function itself. |
| INT-R3 | UI benchmark must test whether operators distinguish external execution, evidence status and PolicyOS reaction. |
| INT-R4 | Deployed observations are INTEGRATE; causal diagnosis and model write-back are OWN and separately gated. |
| INT-R5 | External mandate/delegation evidence is INTEGRATE; the pre-action authority gate is OWN. |
| INT-R6 | PolicyOS owns semantic equivalence of its projections; authoritative external-language texts and certified translations are integrated evidence. |
| INT-R7 | PolicyOS owns public verification of its signatures; trust-service and archival-provider outputs remain integrated. |
| INT-R8 | Compression and audience projections are OWN; omitted external execution details may not be reconstructed or silently upgraded. |
| INT-R9 | The first-promotion protocol must preregister which external functions are evidence dependencies and which are outside the claim. |
| OPS-R1 | Suspension is OWN; wake events from external institutions are INTEGRATE and require fresh authority checks. |
| OPS-R2 | Maintain separate technical artifact dependencies and authority dependencies, including boundary-decision changes. |
| OPS-R3 | Dormant-case migration must pin the boundary-decision version used at suspension and compare old/new semantics. |
| OPS-R4 | Provides common clocks for all external evidence contracts. |
| OPS-R5 | KPI contract and diagnosis are OWN; data collection and institutional adaptation execution are external. |
| OPS-R8 | WorldRelease compatibility is OWN; source-release production may be external. |
| OPS-R9 | Refresh orchestration is OWN for derived PolicyOS artifacts; source revision remains integrated. |
| OPS-R10 | Living-law sensing is OWN; legislation and official publication remain external. |
| OPS-R11 | Jurisdiction-pack verification is OWN; jurisdictional authority itself is external. |
| OPS-R14 | PolicyOS owns recovery of its custody records; institution-wide continuity, archives and renewals remain integrated. |
| OPS-R15 | Must prove `out_of_boundary_actions_attempted = 0` while consuming and binding external events correctly. |
| PAO-R0 | `policy_matter_ref` stays an extensible external dependency until the identity contract is ratified. |
| PAO-R4 | Individual decisions remain OUT; export firewall and return-evidence interface are OWN. |
| PAO-R36 | PolicyOS owns correction of its records; third-party correction, notice and subscriber delivery are integrated evidence. |

## 4.11 Rejected scope expansions

The following are rejected:

1. a generic “public-policy lifecycle manager”;
2. a citizen case-management module;
3. a court or appeal engine;
4. a legally effective notification channel;
5. a payment or compensation subsystem;
6. a procurement workflow platform;
7. a general service-delivery system;
8. a government-wide records-management system;
9. a sovereign identity provider;
10. a general HR, scheduling or ERP layer;
11. a dashboard that treats external status as evidence;
12. a universal `ExternalEvent` payload with no family-native semantics;
13. a single ownership field that obscures operator, evidence producer, adapter and projection;
14. a single “accountability score” that averages legal authority, delivery, transparency and evidence.

---

# 5. Counterexamples And Failure Modes

| Case | Unsafe result | Safe boundary result | Required evidence and reaction |
|---|---|---|---|
| Appeal overreach | “PolicyOS resolved the appeal.” | Adjudication is INTEGRATE; outcome admission and claim correction are OWN. | Competent appeal-body identity, decision, scope, effective time, signature; absent outcome leaves claim contested/review-required. |
| Notification overclaim | Send-status becomes “legally served.” | Notice dispatch and legal service are external; proof of service is separate INTEGRATE evidence. | Qualified or legally sufficient delivery proof; missing proof blocks claims dependent on service. |
| Payment overclaim | Authorization becomes “compensation paid.” | Authorization, settlement and reconciliation are distinct external events. | Payment-system settlement evidence; authorization alone may support only `authorized_not_paid`. |
| Projection becomes authority | Atlas progress row proves delivery. | Atlas is projection-only. | Resolve to admitted delivery evidence; otherwise display reported/unverified/stale. |
| External outage | No response is treated as “no incident.” | Missing evidence is unknown, not negative evidence. | Mark stale/unknown; freeze or limit affected claim; escalate or acquire evidence. |
| Ministry reorganization | Old authority continues to be trusted. | Institutional succession is integrated competence evidence. | New mandate/delegation and effective interval; stale old authority cannot sign current evidence. |
| Function-family collapse | “Appeals” receives one verdict. | Intake, adjudication, outcome ingestion, revalidation and remedy execution are separate rows. | Different owners and evidence contracts per subfunction. |
| Task-queue scope inflation | A custody queue becomes administrative case management. | Queue is limited to PolicyOS obligations and revalidation jobs. | Anti-role check; citizen case fields or legal deadlines trigger P13 review. |
| OWN understatement | Legal validity is dismissed as external. | Enactment is external, but PolicyOS owns sensing and the invalidation cascade of its own claims. | Legal-world event plus mandatory revalidation. |
| INTEGRATE without absence behavior | External function is listed but outage has no effect. | Row is invalid and blocked. | Every INTEGRATE row must name missing, stale, contradictory and revoked behavior. |
| OBSERVE silently upgraded | Institutional-risk dashboard becomes claim evidence. | Observation remains non-authoritative until explicit admission. | New provenance-bound evidence object and admission event required. |
| Hidden dependency under OUT | Function marked OUT despite determining a signed claim. | Decompose: execution stays OUT; evidence receipt is INTEGRATE. | Boundary challenge required. |
| Duplicate canonical owner | Research creates a new appeals or audit model beside existing owners. | Extend contestability, Lex, DDM, audit or PDC. | P27 owner search and disposition record. |
| Surface implies execution | “Appeal resolved,” “payment complete,” “notice delivered.” | Surface names external operator, evidence class, status, as-of and PolicyOS reaction. | Semantic projection test fails on missing producer or authority ref. |
| Technical “compensation” confusion | Saga rollback is read as financial compensation. | Preserve domain-qualified terminology. | Public/UI lint forbids unqualified “compensation” from workflow rollback events. |
| Valid signature, wrong scope | Signed external event closes unrelated claim. | Signature verifies integrity, not competence or claim binding. | Subject, jurisdiction, authority and scope checks; mismatch rejects admission. |
| Advisory legal opinion becomes law | Counsel memo closes legality. | Advisory evidence stays limited. | Official source or competent adjudication needed for binding claim. |
| Independent audit laundering | PolicyOS audit package is called independent assurance. | Package verification is OWN; auditor opinion is external. | Independent auditor identity, mandate and signed report. |

---

# 6. Benchmark Or Fixture Proposal

## 6.1 Boundary-decision corpus

Create a frozen, independently reviewed corpus of at least 160 rows:

| Stratum | Minimum |
|---|---:|
| Clear OWN | 30 |
| Clear INTEGRATE | 45 |
| Clear OBSERVE | 20 |
| Clear OUT_OF_SCOPE | 25 |
| Broad functions requiring decomposition | 15 |
| Jurisdiction-dependent | 10 |
| Pilot-dependent | 10 |
| Deliberately malicious or misleading | 5 |

Each row should include:

- exact function;
- PolicyOS claim at risk;
- real operator;
- evidence producer;
- competent authority;
- expected verdict;
- expected owner state;
- required interface;
- absence behavior;
- prohibited claim;
- expected public wording;
- adjudicator notes.

## 6.2 Metrics

| Metric | Meaning |
|---|---|
| `false_own_rate` | External institutional function incorrectly claimed as PolicyOS-owned |
| `false_integrate_rate` | Function incorrectly treated as an evidence dependency |
| `false_observe_rate` | Validity-changing external event treated as context only |
| `false_out_of_scope_rate` | Claim-critical dependency incorrectly excluded |
| `scope_inflation_rate` | Anti-role functions assigned to PolicyOS |
| `missing_fail_closed_rate` | INTEGRATE rows without deterministic absence behavior |
| `external_execution_overclaim_rate` | Surface or record implies PolicyOS performed external act |
| `observation_to_authority_upgrade_rate` | Observed signal admitted without transition |
| `duplicate_owner_rate` | New contract family created beside canonical owner |
| `undetected_claim_dependency_rate` | Signed claim omits a load-bearing external function |
| `surface_boundary_misrepresentation_rate` | Projection omits operator/evidence/as-of/boundary |
| `lifecycle_collapse_rate` | Distinct lifecycles merged into one status or owner |
| `competence_mismatch_acceptance_rate` | Evidence from unauthorized producer admitted |
| `late_event_historical_rewrite_rate` | Late evidence changes old replay rather than creating a delta |

Critical sentinel targets should be zero for:

- out-of-boundary execution;
- missing fail-closed behavior;
- observation-to-authority upgrade;
- duplicate canonical owner;
- silent historical rewrite;
- external-execution overclaim.

## 6.3 Metamorphic tests

1. Changing a UI label cannot change the verdict.
2. Adding a task queue cannot turn PolicyOS into the institutional operator.
3. Receiving an event cannot imply PolicyOS performed it.
4. A verified external outcome can change PolicyOS claims without transferring ownership.
5. Missing decisive external evidence cannot become a pass.
6. A dashboard cannot mint authority.
7. Similar function names need not receive the same verdict.
8. Decomposition may—and often must—produce different verdicts.
9. Institutional reorganization triggers competence revalidation without automatically changing the function class.
10. OBSERVE cannot become admitted authority without an explicit transition.
11. OUT execution can have a separately classified INTEGRATE evidence receipt.
12. Changing the external provider must not preserve authority without new competence and trust evidence.
13. A signature alone must not close subject, jurisdiction or scope.
14. Adding more rows cannot close a mandate, proof-of-service or payment-settlement gap.
15. A corrected boundary decision must supersede rather than overwrite.
16. Historical replay uses the boundary version effective at the original decision.

## 6.4 Human-review benchmark

Reviewers receive a packet containing:

- candidate function decomposition;
- signed PolicyOS claim at risk;
- real operator candidates;
- statutory or organizational authority;
- system-of-record evidence;
- external artifact examples;
- proposed absence behavior;
- anti-role analysis;
- existing repository owners;
- competing verdicts;
- public wording examples.

Measure:

- verdict accuracy;
- decomposition accuracy;
- claim-at-risk identification;
- operator/evidence distinction;
- fail-closed completeness;
- P13 and P27 detection;
- public-projection correctness;
- confidence calibration;
- inter-reviewer consistency;
- time to identify the unsafe claim.

## 6.5 Fault-injection cases

- evidence producer outage;
- expired delegation;
- unsigned proof of service;
- corrected payment record;
- duplicate appeal outcome;
- conflicting court and agency records;
- retroactive law;
- late incident report;
- compromised supplier key;
- stale license;
- records hold arriving after scheduled deletion;
- ministry succession mid-case;
- public cache still showing superseded status;
- Atlas projection with producer ref removed;
- observed dashboard metric directly wired to claim status;
- H2 worker attempting to issue a notice or payment.

## 6.6 OPS-R15 linkage

The capstone must demonstrate:

```text
out_of_boundary_actions_attempted = 0
external_execution_overclaims = 0
missing_fail_closed_routes = 0
observation_authority_upgrades = 0
stale_public_shown_as_current = 0
silent_historical_rewrites = 0
missed_affected_claims = 0
```

Administrative events must enter as evidence. PolicyOS may wake, revalidate, limit, correct, supersede or withdraw; it must never:

- issue legally effective notices;
- adjudicate appeals;
- authorize or execute payments;
- operate citizen cases;
- perform procurement;
- deliver physical services;
- replace a court, ombudsman or records authority.

---

# 7. Artifact Contract Sketch

All contracts below are `research_only` and `candidate_for_consolidation`.

## 7.1 OperationalBoundaryDecision

```yaml
schema_version: policyos.research.operational_boundary_decision.v0
rule_version: four-way-custody-test.ratified-2026-07-20

boundary_decision_id: stable opaque id
function_id: canonical semantic id
function_name: human label
function_definition: narrow activity definition
lifecycle:
  - epistemic
  - administrative
  - implementation
  - institutional
  - public_records

boundary_verdict: own | integrate | observe | out_of_scope
verdict_rationale: text
policyos_claim_at_risk:
  claim_family: semantic id
  claim_ref: optional ref
  silent_falsehood: text
identity_decision_ruling_extended: reference

real_operator:
  institution_ref: reference
  role: text
  system_ref: reference
  normal_mode: text
  degraded_mode: text
  dispute_forum_ref: optional reference
legal_or_institutional_authority:
  authority_ref: reference
  competence_scope: structured scope
  effective_interval: interval

owner_state:
  - existing_internal_owner
  - partial_internal_owner
  - missing_internal_bridge
  - external_institution_owner
  - owner_unresolved

existing_canonical_owner: package/team/external role
candidate_owner_extension: optional package/team
current_implementation_state:
  - implemented
  - implemented_but_not_orchestrated
  - contract_only
  - producer_missing
  - bridge_missing
  - verification_missing
  - surface_missing
  - semantic_test_missing

external_producer: optional producer ref
policyos_adapter_owner: optional owner
policyos_consumer: optional owner
claim_reaction_owner: optional owner
surface_projection_owner: optional owner

evidence_contract_ref: optional family-native contract
absence_behavior: typed behavior
downstream_reaction: typed reaction

authority_boundary:
  authoritative_for: [...]
  may_not_use_for: [...]
authoritative_for: [...]
may_not_use_for: [...]

tenant_scope: structured scope
jurisdiction_scope: structured scope
policy_matter_ref: optional external_dependency_assumption
case_or_episode_refs: [...]

valid_time: interval or unresolved
transaction_time: timestamp
observed_time: timestamp or null
admitted_time: timestamp or null

provenance_requirements: [...]
verification_requirements: [...]
surface_projection: policy

confidence: high | medium | low
pilot_dependency: boolean
open_questions: [...]
activation_or_review_trigger: [...]
supersedes_boundary_decision: optional id
status:
  - proposed
  - research_supported
  - accepted_narrow_scope
  - contested
  - superseded
  - blocked
  - deferred_pending_pilot
  - retired
```

## 7.2 Why these fields are necessary

| Field group | Research justification |
|---|---|
| Function identity and definition | Prevents broad-family collapse |
| Claim at risk | Makes OWN/INTEGRATE checkable rather than intuitive |
| Real operator and authority | Separates event owner from evidence adapter |
| Multiple ownership fields | Prevents “runtime-owned wrapper” from implying institutional ownership |
| Owner state vs implementation state | External ownership can be known while the bridge is missing |
| Evidence contract | Ensures INTEGRATE is actionable and fail-closed |
| Authority boundary | Prevents evidence from being reused for broader claims |
| Multiple clocks | Handles late, retroactive, corrected and stale events |
| Provenance and verification | Separates received from admitted evidence |
| Surface policy | Prevents dashboards from minting authority |
| Confidence and trigger | Preserves provisional and pilot-dependent judgments |
| Supersession | Prevents silent rewriting of research decisions |

## 7.3 Shared institutional evidence envelope

```yaml
InstitutionalEvidenceEnvelope:
  evidence_id: stable id
  evidence_family: discriminator

  producer:
    actor_ref: reference
    institution_ref: reference
    system_ref: reference
    role: text

  subject:
    policy_matter_ref: optional external_dependency_assumption
    case_ref: optional
    episode_ref: optional
    claim_refs: [...]

  authority:
    competence_ref: reference
    mandate_or_delegation_ref: optional
    jurisdiction_scope: structured
    subject_matter_scope: structured
    binding_character:
      binding | advisory | reported | alleged | unverified
    authoritative_for: [...]
    may_not_use_for: [...]

  time:
    event_time: timestamp
    legal_effective_time: optional timestamp/interval
    valid_time: optional interval
    publication_time: optional timestamp
    observation_time: timestamp
    receipt_time: timestamp
    admission_time: optional timestamp
    correction_time: optional timestamp
    revocation_time: optional timestamp
    transaction_time: timestamp

  provenance:
    source_ref: reference
    receipt_method: text
    signature_or_authentication_ref: optional reference
    content_hash: digest
    schema_version: text
    rule_version: text
    transformation_chain: [...]
    adapter_ref: reference
    fallback_mode: text
    human_action_refs: [...]
    audit_event_ref: reference

  evidence_status:
    received | verified | admitted | disputed | corrected |
    revoked | stale | superseded | rejected | historical_only

  verification:
    identity_check: result
    competence_check: result
    integrity_check: result
    scope_check: result
    freshness_check: result
    replay_check: result

  downstream:
    affected_claim_refs: [...]
    affected_case_refs: [...]
    affected_public_record_refs: [...]
    required_reaction: [...]
```

## 7.4 Absence-behavior grammar

```yaml
AbsenceBehavior:
  condition:
    missing | late | stale | malformed | unsigned | unverifiable |
    contradictory | unauthorized_producer | scope_mismatch |
    corrected | revoked | institution_unavailable | out_of_envelope

  evidence_disposition:
    unknown | quarantine | reject | contest | stale |
    invalidate_previous | historical_only

  claim_effect:
    none | annotate | limit | block | freeze_publication |
    open_epoch | revalidate | recompute | human_review |
    correct | reissue | supersede | withdraw

  historical_effect:
    preserve_original | append_delta | add_correction_link

  next_action:
    acquire_evidence | contact_operator | escalate |
    wait_for_event | human_adjudication | no_action
```

## 7.5 Boundary challenge receipt

```yaml
BoundaryDecisionChallengeReceipt:
  challenge_id: stable id
  challenged_decision_ref: reference
  challenger:
    actor_ref: reference
    mandate_ref: optional
  counterexample: structured description
  repository_evidence_refs: [...]
  institutional_evidence_refs: [...]
  affected_claim_refs: [...]
  affected_surfaces: [...]
  alleged_failure_patterns: [...]
  requested_interim_action:
    none | annotate | limit | block | freeze
  proposed_decomposition: [...]
  review_owner: role/team
  review_due_at: timestamp
  outcome_ref: optional
```

## 7.6 Canonical-owner map

| Concept/function | Existing owner | Owner state | Boundary verdict | Proposed disposition |
|---|---|---|---|---|
| Policy-level authority contracts | PDC | Existing | OWN | Extend only |
| Function-level boundary register | Team architecture research; no runtime owner yet | Partial/absent | OWN | Research artifact now; candidate PDC reference later |
| External evidence admission | Runtime quality + Fabric source-contract patterns | Partial | OWN | Extend shared envelope, retain family-native payloads |
| Legal sensing | Lex | Existing/partial | OWN | Extend continuous release and jurisdiction packs |
| Enactment and court acts | Legislature/court/gazette | External | INTEGRATE | Evidence interface only |
| KPI control contracts | Feedback/DDM + future OPS-R5 | Partial | OWN | Extend |
| Data collection | External operational/data institution | External | INTEGRATE | Fabric/RQ adapter |
| Appeal adjudication | External appeal body | External | INTEGRATE | Contestability outcome interface only |
| Claim correction after appeal | Decision validity/continuous governance | Existing/partial | OWN | Extend |
| Audit package | Core audit | Existing | OWN | Keep |
| Independent audit opinion | External auditor/SAI | External | INTEGRATE | External-audit evidence contract |
| Internal authorization | Runtime HTTP/DS20 | Existing | OWN | Keep |
| External administrative authority | Competent institution | External | INTEGRATE | Mandate/delegation evidence |
| Monitoring and incidents | DDM + external operators | Partial split | OWN/INTEGRATE | Decompose producer vs reaction |
| Public projection | Atlas | Existing | Projection only | Never mint authority |
| Public signature verification | Core audit + future INT-R7/DS12 | Partial | OWN | Consolidate |
| Service delivery | Service owner/delivery body | External | INTEGRATE evidence; no execution ownership | No service platform |
| Institutional records management | Records authority/controller | External | INTEGRATE | Own only PolicyOS records |
| Compensation payment | Treasury/payment operator | External | INTEGRATE | No payment subsystem |
| Administrative case management | External case system | External | OUT execution; selected events INTEGRATE | No case-management owner |
| Supplier admission | Runtime quality/Fabric/external audit | Partial | OWN | Extend M35 dossier path |
| Supplier operation/procurement | Procurement and contract authority | External | INTEGRATE | No procurement platform |
| H2 custody runtime | Future | Missing | OWN orchestrator of PolicyOS custody | Consumer of register, not owner of external functions |

---

# 8. Later Integration Handoff

| Result/artifact | Producer | Persisted artifact/event | Bridge | Consumer | Verification | Surface | Canonical home |
|---|---|---|---|---|---|---|---|
| Operational boundary register | Team architecture + canonical owners | Versioned research artifact | Later PDC reference/admission | All Wave-2 tasks, H2 | Schema, owner and contradiction checks | Reviewer/MACHINE | Research docs; candidate PDC reference |
| Institutional evidence envelope | Family adapter | CAS artifact + receipt event | Runtime quality | Decision validity, PDC, H2 | Identity, competence, scope, time, signature, replay | Atlas evidence detail | Shared RQ envelope |
| Legal-world evidence | Lex | Legal release/delta and event | Existing/future Lex bridge | N12, H2, PDC | Official source, temporal and competence checks | DS18/legal view | Lex |
| KPI observation evidence | External collector/DDM adapter | Observation artifact/event | DDM/RQ | OPS-R5, learning loop | Definition version, lineage, vintage, scope | DS16/18 | DDM/feedback |
| Appeal or court outcome | External body adapter | Signed outcome evidence | Contestability/RQ | Claim lifecycle | Authority, standing, finality, scope | DS9/13/18 | Contestability + RQ |
| Proof of service | Administrative adapter | Delivery receipt | RQ | Claim or process-validity consumer | Qualified status or jurisdiction rule | Reviewer only unless public-safe | Family-native adapter |
| Delivery/capacity evidence | Service operator adapter | Delivery/capacity report | RQ | Feasibility/value/revalidation | Operator, denominator, period, method | DS7/16 | External adapter + RQ |
| Payment evidence | Treasury/payment adapter | Authorization, settlement and reconciliation events | RQ | Remedy and claim records | Distinct event matching and finality | Public-safe status | Family-native adapter |
| Records/hold decision | Records authority adapter | Schedule, disclosure or hold decision | RQ/core audit | Retention and public-record lifecycle | Authority, scope, effective time | DS13/18 | Core audit + external adapter |
| Boundary change impact | Register reviewer | `BoundaryImpactEvent` | H2/OPS-R2 | Active claims and publications | Dependency traversal and clean-rebuild parity | DS18 | Future H2 |
| Public projection | Runtime producer | Typed API projection | Generated client | Atlas | Projection parity and no-mint semantic tests | PUBLIC/REVIEWER/EXPERT/MACHINE | Atlas |
| Boundary challenge | Authorized challenger | Challenge receipt | Review workflow | Team architecture/canonical owner | Evidence and mandate checks | Reviewer/MACHINE | Governance owner |

---

# 9. Promotion And Kill Rules

## 9.1 `research_only`

Current standing. Required while:

- real institutional operators are not named;
- jurisdictional legal effects are unresolved;
- no semantic benchmark exists;
- no partner evidence has been exercised;
- PAO-R0 matter identity remains provisional;
- register rows have not been independently reviewed.

## 9.2 `prototype_allowed`

Allowed for:

- synthetic boundary corpus;
- static register validator;
- reviewer packet;
- family-native evidence envelopes;
- Atlas mock projections clearly marked `fixture_only`;
- external-event replay against non-production claims.

Conditions:

- no external institutional function is executed;
- no public authority claim is upgraded;
- observations remain non-authoritative;
- every INTEGRATE prototype implements missing/stale/contradictory/revoked behavior;
- P27 owner review passes.

## 9.3 `governed_allowed`

Requires:

1. reviewed function decomposition;
2. named real operator;
3. competent evidence producer;
4. PDC/RQ authority boundary;
5. provenance and multiple clocks;
6. correction and revocation semantics;
7. semantic negative tests;
8. tenant and jurisdiction scoping;
9. Atlas projection parity;
10. pilot partner confirmation where required.

## 9.4 `production_candidate`

Additionally requires:

- partner-system authentication and operational agreements;
- source and schema versioning;
- outage and degraded-mode tests;
- independent competence review;
- historical replay;
- mass-impact boundary-change handling;
- OPS-R15 capstone pass;
- public wording tested for operator/evidence clarity;
- no critical benchmark failures.

## 9.5 `blocked`

A boundary row is blocked when:

- an OWN verdict contradicts the ratified identity without escalation;
- INTEGRATE lacks fail-closed absence behavior;
- OBSERVE is consumed as authority;
- OUT execution is performed by PolicyOS;
- external evidence receipt is described as PolicyOS execution;
- a dashboard mints authority;
- operator, competence, provenance or time is omitted;
- unsupported external evidence upgrades a claim;
- lifecycles are collapsed;
- a pilot assumption is treated as project truth;
- a second canonical owner is created;
- a PolicyOS anti-role is introduced;
- a claim-critical function is excluded merely because its operator is external.

## 9.6 `out_of_scope`

The execution of a function may remain OUT while a separately decomposed evidence receipt is INTEGRATE. Examples:

- individual eligibility is OUT;
- aggregate implementation evidence returned by the case system is INTEGRATE;
- payment execution is OUT;
- settlement evidence is INTEGRATE;
- appeal adjudication is external;
- outcome admission and PolicyOS correction are OWN.

---

# 10. Open Questions For Consolidation

1. Which PDC type should reference the boundary-decision version used for a serious case?
2. Should the register be one global artifact or jurisdiction-pack overlays over a common core?
3. Who is the human principal empowered to ratify a cross-institution production row?
4. How should a boundary row attach to the future PolicyMatter without assuming its final schema?
5. Which external evidence families require cryptographic signatures versus authenticated APIs or independently verified records?
6. How are evidentiary conflicts between competent bodies adjudicated?
7. What is the minimum proof that an external operator remains competent after reorganization?
8. How should legal finality, appealability and provisional decisions be represented across jurisdictions?
9. Which external events require immediate publication freeze versus annotation?
10. What retention and disclosure policy applies to external evidence containing personal, privileged or classified material?
11. How does H2 wake a suspended case when the evidence producer is unavailable but a legal deadline expires?
12. Which boundary changes require revalidation of all historical cases versus only current publications?
13. How should external service-level reports be calibrated before supporting delivery claims?
14. Who verifies proof-of-service evidence outside eIDAS-like qualified regimes?
15. Can an institution delegate evidence production to a supplier without transferring legal responsibility?
16. How should public wording distinguish reported, verified, admitted, binding and executed?
17. What records authority governs the register itself and its superseded decisions?
18. Which partner facts are safe to expose across PUBLIC, REVIEWER, EXPERT and MACHINE views?
19. How should emergency powers and degraded operations alter competence checks?
20. How should the PAO-R31 institutional-transition row be reclassified where succession directly changes claim validity?

**Recommended consolidation owner:** `team-architecture`, with PDC and runtime-quality co-ownership and mandatory domain review from Lex, DDM, audit, security, records/privacy and the relevant institutional partner.

**Review cadence:** quarterly and event-triggered.

---

# Direct Answers To The 29 Required Questions

1. **What does PolicyOS own?** The epistemic and custody functions needed to keep its own signed claims truthful: grounding, admission, authority assignment, publication state, staleness, revalidation, correction, replay, provenance, audit and verification.
2. **What remains external but must feed PolicyOS?** Enactment, adjudication, administration, implementation, delivery, payments, records decisions, institutional authority, oversight and other external acts whose outcomes affect PolicyOS claims.
3. **What may it observe without treating as evidence?** Political context, institutional risk, local discretion, workaround signals, capture indicators and unverified status dashboards.
4. **What stays outside scope?** Individual decisions, citizen case management, courts, legally effective notification, payment execution, service delivery, procurement operation, general records management, HR and ERP functions.
5. **How are broad families classified?** By decomposing them into actual acts, evidence emission, admission, claim reaction and projection.
6. **What claim is at risk?** Each row names the exact PolicyOS claim that would become false, overbroad, stale or misleading.
7. **Who performs external functions?** The competent legislature, court, administrative body, appeal forum, records authority, service owner, treasury, payment operator, procurement authority, auditor, IdP or provider.
8. **In which system?** The institutional system of record, not PolicyOS, unless the row is an internal custody function.
9. **Under what authority?** Statute, regulation, mandate, delegation, appointment, contract, audit mandate, records schedule or other competent authority.
10. **What evidence crosses?** A family-native, typed, provenance-bearing institutional artifact or event.
11. **How is it authenticated?** Through signatures, trusted service status, authenticated APIs, source verification, content hashes and independent cross-checks appropriate to the family.
12. **What provenance is required?** Actor, institution, activity, system, source, receipt method, transformation, adapter, human actions and audit event.
13. **What temporal fields are required?** Event, effective, valid, publication, observation, receipt, admission, transaction, correction and revocation times where applicable.
14. **What happens when evidence is missing?** It becomes unknown—not evidence that nothing happened—and load-bearing claims are limited or blocked.
15. **When late?** Preserve the historical view, record the late transaction and evaluate retroactive impact.
16. **When contradictory?** Mark contested, compose to the weakest boundary and require competent or human adjudication.
17. **When corrected or revoked?** Append a new event, invalidate prior authority, perform impact analysis and revalidate or reissue.
18. **Which claims react?** Only claims transitively dependent on the admitted evidence, with least-expansive safety-preserving scope.
19. **Which repository owners should be extended?** PDC, runtime quality, Fabric, Lex, DDM, decision validity, continuous governance, core audit, runtime authorization and Atlas.
20. **Which owners are partial or absent?** The function-level boundary register, generic institutional evidence union, partner adapters, H2 orchestration and several public surfaces.
21. **Which functions are pilot-dependent?** Most administrative, service, records, payment, procurement, interagency, accessibility, proof-of-service and institutional-transition mappings.
22. **Which deferred triggers are sufficient?** They are generally sufficient to reopen research, not to authorize implementation; each also requires a named operator, authority, system, evidence path and review owner.
23. **How does the register prevent administration creep?** By separating external act, evidence, admission, reaction and projection, and by treating anti-role execution as a kill condition.
24. **How does it prevent responsibility understatement?** External execution does not excuse PolicyOS from owning the effect on its own signatures.
25. **How does it constrain OPS-R15?** Administrative acts enter only as evidence, while PolicyOS performs only custody reactions and records zero out-of-boundary actions.
26. **How are decisions challenged and superseded?** Through evidence-bearing challenge receipts and immutable successor rows.
27. **What remains research-only?** Final schemas, cross-jurisdiction competence rules, partner mappings and production authority.
28. **What may later be prototyped?** The register validator, evidence envelopes, reviewer benchmark, Atlas projection and H2 replay.
29. **What must be blocked?** Anti-role execution, missing absence behavior, observation laundering, dashboard authority, lifecycle collapse, duplicate owners and unsupported institutional assumptions.

---

# Appendix A. Repository Evidence Register

| File or symbol | Current behavior | Ownership implication | Confidence | Related task |
|---|---|---|---|---|
| Identity/custody decision | Ratifies signature rule, four-way test and anti-roles | Governing boundary source | High | All |
| `AGENTS.md` | Requires capability chain, reuse-first and anti-P13/P27/P29 discipline | No contract-only boundary claims | High | PAO-R1 |
| `AuthorityBoundary` | Purpose-scoped permitted/prohibited use and weakest-boundary composition | One authority grammar already exists | High | INT-R1–R9 |
| PDC waist | Verifier-only authority fields | Admission/reaction belongs at waist | High | GY |
| Fabric `SourceContract` | Schema, security, trust, replay, lineage, SLA and retention | Reusable common evidence envelope | High | INTEGRATE contracts |
| Lex legal authority | Separates legal source from competence, time and implementation authority | Legal sensing OWN; sovereign act external | High | OPS-R10/R11 |
| ADR-0170 contestability | Separates outcome ingestion from appeal administration | Appeal adjudication INTEGRATE | High | PAO-R9 |
| `institutional_provenance.py` | Runtime-owned wrappers over external events | Wrapper ownership must not imply event ownership | High | PAO-R1 |
| Decision validity | Append-only dependency events and lifecycle transitions | Claim reaction owner exists | High | OPS-R2/N12 |
| Feedback contracts | Monitoring and reissue primitives | KPI owner partial | High | OPS-R5 |
| DDM | Incident, shift, readiness and calibration evidence | Detection and evidence owner exists | High | INT-R4 |
| Core audit | Portable, independently verifiable package | Audit package OWN; auditor opinion external | High | INT-R7 |
| External-audit record | Enforces projection-only PDC surface | Dashboard/audit projection cannot mint authority | High | Atlas DS12/13 |
| Runtime authorization audit | Records admission, not handler success | Internal auth OWN, execution claim separate | High | INT-R5/DS20 |
| Atlas plan | Atlas renders, never produces authority | Public projection owner only | High | DS4–DS18 |
| Scientist lifecycle bridge | Append-only staleness, blocking, reissue and withdrawal | Post-event reaction owner exists | High | OPS-R2 |
| Retention/recovery | Retains PolicyOS audit/signature/replay artifacts | Not institution-wide records management | High | OPS-R14 |
| PolicyPortfolio IR | Candidate portfolio analysis | Must not become deployed administrative stock | High | OPS-R13 |
| `compensation.py` | Workflow rollback hook | Not financial/public compensation | High | PAO-R20 |
| No `OperationalBoundaryDecision` result | No canonical implementation found | Register remains contract-only research | Medium-high | PAO-R1 |
| Notification/payment/service searches | No inspected production operators | Supports anti-role, subject to search limitation | Medium | Deferred PAO |

# Appendix B. External Source Register

Access date for all sources: **2026-07-26**.

| Source | Type | Standing | Claim supported | Institutional assumptions | Limitation |
|---|---|---|---|---|---|
| Bovens, accountability framework | Peer-reviewed public-administration research | Primary research | Accountability links actor and forum, explanation, judgment and consequences | Identifiable actors and forums | Does not define evidence schema. (DOI) |
| Koppell, multiple accountabilities disorder | Peer-reviewed research | Primary research | Accountability dimensions are distinct and can conflict | Hybrid organization | Does not allocate legal authority. (Wiley Online Library) |
| W3C PROV | Formal provenance standard | Primary | Agents, activities, roles, attribution and delegation | Domain supplies semantics | Provenance is not proof of competence. (W3 DVCS) |
| NIST AI RMF | Government risk framework | Primary official | Organizational governance, lifecycle and third-party risks | Voluntary adoption | Not a legal public-power allocation. (NIST AI Resource Center) |
| EU AI Act | Legislation | Primary legal | Distinct provider, deployer, human oversight and authority duties | EU-regulated use | Context- and use-case-specific. (EUR-Lex) |
| GovS 005 | Digital Government functional standard | Primary official | End-to-end service owner retains delivery accountability | UK government setting | Organizational, not universal law. (GOV.UK) |
| UK ATRS | Government transparency standard | Primary official | Named SRO/operator, signoff and update obligations | UK public bodies | Transparency record does not prove delivery. (GOV.UK) |
| eIDAS | Regulation | Primary legal | Qualified evidence for time and registered delivery | EU trust-service regime | Non-qualified events may have different effect. (EUR-Lex) |
| ISSAI 100 | Public-sector audit standard | Primary professional | Auditor, responsible party and users remain distinct | SAI/public audit mandate | National audit mandates vary. (ISSAI) |
| NARA records schedules | Government records authority | Primary official | Disposition needs approved schedules; mission records need specific rules | US federal agencies | Jurisdiction-specific. (National Archives) |
| ICO records guidance | Regulatory guidance | Primary official | Authorities own retention, destruction and disclosure governance | UK FOI/EIR | Jurisdiction-specific. (ICO) |
| GDPR Article 5 | Legislation | Primary legal | Purpose, minimization, accuracy and storage limitation | Personal-data controller | Does not allocate every records function. (EUR-Lex) |
| GAO Green Book | Government internal-control standard | Primary official | Management owns design and operation of controls | US federal entities | Organizational transfer required. (Government Accountability Office) |
| European Ombudsman statute/guidance | Official institutional mandate | Primary official/legal | Independent complaint forum has bounded authority | EU institutions | Does not cover national bodies. (European Ombudsman) |
| OECD public procurement | Intergovernmental recommendation | Primary official | Procurement is a governed institutional cycle with fiduciary and integrity duties | Adhering public systems | Not a direct implementation contract. (OECD) |
| OECD Governing with AI | Intergovernmental research/report | Primary official | Government AI depends on distinct governance, data, infrastructure, procurement and skills functions | Public administrations | Comparative, not jurisdiction-specific law. (OECD) |

# Appendix C. Full OperationalBoundaryDecision Register

## C.1 Legend

### Verdict

- **O** — OWN
- **I** — INTEGRATE
- **V** — OBSERVE
- **X** — OUT_OF_SCOPE

### Owner state

- **EI** — existing_internal_owner
- **PI** — partial_internal_owner
- **MB** — missing_internal_bridge
- **EX** — external_institution_owner
- **UR** — owner_unresolved

### Claim-at-risk codes

| Code | PolicyOS claim |
|---|---|
| C1 | Design or recommendation is grounded for its declared scope |
| C2 | Authority status and permitted use are correct |
| C3 | Published record is current and honestly qualified |
| C4 | Historical record is replay-valid |
| C5 | Legal basis, competence or mandate is current |
| C6 | Evidence is authentic, current and properly admitted |
| C7 | Feasibility or delivery claim is supported |
| C8 | Monitoring, outcome, incident or harm status is supported |
| C9 | A person/body had authority for the PolicyOS action |
| C10 | Public signature or audit proof is verifiable |
| C11 | Matter, case and lineage binding are correct |
| C12 | PolicyOS record/privacy handling is honest |
| C13 | Learning and world-model update are causally safe |
| C14 | Policy-level output has not become an individual decision |
| C15 | External execution status is not overclaimed |
| C16 | Supplier, license or external dependency remains admissible |
| C17 | Custody, replay and recovery remain available |

### Absence reactions

| Code | Meaning |
|---|---|
| A1 | unknown; never infer non-occurrence |
| A2 | quarantine/reject unverifiable evidence |
| A3 | stale/late; limit and revalidate |
| A4 | contested; human/competent adjudication |
| A5 | corrected/revoked; impact fan-out |
| A6 | external status only; no execution claim |
| A7 | competence/scope mismatch; reject |
| A8 | tenant/privacy/security block |
| A9 | out-of-scope refusal or dependency pointer only |

### Surface

- **PUB** — governed public projection
- **REV** — reviewer/expert projection
- **MCH** — machine projection
- **NONE** — no PolicyOS operational surface
- **EXT** — link or externally reported status only

The table is a normalized projection of the full register schema in §7. Every INTEGRATE row inherits the identity, authority, time, provenance, status and correction fields of its referenced contract family in Appendix D.

## C.2 Policy design and epistemic custody

| ID | Narrow function | L | V | Real operator | State; internal owner | Claim | Contract / absence → reaction | Surface | Conf./trigger |
|---|---|---|---|---|---|---|---|---|---|
| PD-01 | Frame policy problem, decision purpose and scope | E | O | PolicyOS principal/PDC | EI; PDC/RQ | C1,C2 | Missing mandate → block/human decision | REV/MCH | High; scope change |
| PD-02 | Search evidence and persist search boundary | E | O | PolicyOS search controller | EI/IBO; Scientist/Fabric/RQ | C6 | Poor recall → search repair, not false abstention | REV/MCH | High |
| PD-03 | Admit evidence into authority path | E | O | RQ verifier | EI; RQ/PDC | C2,C6 | A2/A7 → block | REV/MCH | High |
| PD-04 | Perform and verify causal inference | E | O | Foundry adapter/RQ | PI/IBO; Foundry/RQ | C1,C6 | Missing ID/calibration → bounds/abstain | REV | High |
| PD-05 | Analyse value and trade-offs | E | O | Value gate/PDC | PI; PDC/RQ | C1,C2 | No normative authority → frontier only | REV | High |
| PD-06 | Represent uncertainty and incomparability | E | O | PDC/value owner | EI/PI | C1,C2 | Unknown remains unknown | PUB/REV/MCH | High |
| PD-07 | Discover and compile obligations | E | O | PDC/GY-N9 | PI | C2,C6 | Unknown remainder visible; no unconditional completeness | REV/MCH | High |
| PD-08 | Produce a policy recommendation | E | O | PDC promotion path | PI/IBO | C1,C2 | Ungrounded candidate remains shadow | REV; PUB only gated | High |
| PD-09 | Produce refusal with acquisition path | E | O | RQ acquisition owner | EI/IBO | C1,C6 | Missing support → costed route | REV/MCH | High |
| PD-10 | Assign authority boundary/status | E | O | PDC verifier | EI | C2 | Missing input takes weakest boundary | All | High |
| PD-11 | Sign PolicyOS claim or packet | PR | O | PolicyOS signing service | PI; core/DS12 | C3,C10 | Key/epoch invalid → no signing | PUB/MCH | High; INT-R7 |
| PD-12 | Publish PolicyOS claim | PR | O | Runtime publication owner | PI/SM; DS12/Atlas | C3,C10 | Missing promotion/proof → freeze | PUB/MCH | High |
| PD-13 | Detect claim staleness | E/PR | O | Decision validity/N12 | PI/IBO | C3,C6 | A3 → `revalidation_required` | All | High |
| PD-14 | Revalidate affected claims | E | O | Decision validity/H2 | PI/IBO | C2,C3,C6 | No current evidence → blocked/limited | REV/MCH | High |
| PD-15 | Partially reissue a decision | E/PR | O | Scientist lifecycle/PDC | EI/IBO | C3,C4 | Preserve unaffected scope | PUB/REV/MCH | High |
| PD-16 | Supersede a PolicyOS record | PR | O | PDC/publication owner | EI/PI | C3,C4 | Visible lineage required | PUB/MCH | High |
| PD-17 | Withdraw a PolicyOS record | PR | O | Authorized PolicyOS principal | PI | C3,C10 | Human authority required | PUB/MCH | High |
| PD-18 | Correct a PolicyOS-owned record | PR | O | PAO-R36 owner | PI/SM | C3,C4,C12 | Append correction; no overwrite | PUB/MCH | High; PAO-R36 |
| PD-19 | Replay historical case and rules | E/PR | O | Core artifacts/PDC | EI | C4,C17 | Missing versions → replay blocked | REV/MCH | High |
| PD-20 | Maintain PolicyMatter identity | E/I/PR | O | Future PDC identity owner | CO/PM; PDC candidate | C11 | Unresolved lineage → no aggregation | REV/MCH | Med.; PAO-R0 |
| PD-21 | Maintain Policy Design Case identity | E | O | PDC | EI | C11 | Tenant/case mismatch → block | REV/MCH | High |
| PD-22 | Maintain claim/artifact lineage | E/PR | O | PDC/IR/core | PI/BM | C4,C6,C11 | Missing edge → authority cap | REV/MCH | High |
| PD-23 | Verify WorldRelease compatibility | E/I | O | Fabric/GY/H2 | PI/BM | C1,C3,C6 | Unverified latest mix → block | REV/MCH | High; OPS-R8 |
| PD-24 | Maintain provenance | All | O | Core/Fabric/PDC | EI | C4,C6,C10 | Unknown provenance → reject/limit | All | High |
| PD-25 | Produce PolicyOS audit package | PR | O | Core audit | EI | C10,C17 | Incomplete package → fail | REV/PUB/MCH | High |
| PD-26 | Verify PolicyOS public proof | PR | O | INT-R7/DS12 | PI | C10 | Revoked/stale key → invalid/current warning | PUB/MCH | High |
| PD-27 | Account for compression loss | PR | O | GY-PA3/INT-R8 | CO/PM | C2,C3 | Material omission → block projection | All | Med.; INT-R8 |
| PD-28 | Preserve multilingual authority semantics | PR | O | Atlas/Lex projection owner | PI/CO | C2,C3,C5 | Semantic upgrade → block | All | Med.; INT-R6 |

## C.3 Legal and mandate functions

| ID | Narrow function | L | V | Real operator | State; internal owner | Claim | Contract / absence → reaction | Surface | Conf./trigger |
|---|---|---|---|---|---|---|---|---|---|
| LG-01 | Ingest legal corpus | E | O | Lex | EI | C5,C6 | EC-01; A2/A3 → limit/block | REV/MCH | High |
| LG-02 | Authenticate legal source | E | O | Lex/jurisdiction pack | PI | C5,C6 | EC-01; A2/A7 | REV | High |
| LG-03 | Detect amendment/repeal/corrigendum | E | O | Lex legal release | PI/BM | C3,C5 | EC-01; missed delta falsifies | REV/MCH | High; OPS-R10 |
| LG-04 | Analyse legal applicability | E | O | Lex/RQ | EI/PI | C1,C5 | Unresolved scope → limitation/block | REV | High |
| LG-05 | Analyse legal competence | E | O | Lex/RQ | PI | C5,C9 | Missing competence → reject authority | REV | High |
| LG-06 | Verify external mandate for PolicyOS use | E/I | O | PDC/RQ gate | PI | C2,C5,C9 | EC-03; missing → block | REV | High |
| LG-07 | Verify external delegation | E/I | O | PDC/RQ gate | PI/CO | C9 | EC-03; expired/wrong scope → block | REV | High; INT-R5 |
| LG-08 | Supply external legal interpretation | A/I | I | Government counsel/competent legal body | EX; Lex/RQ bridge | C5 | EC-02; advisory only unless binding | REV/EXT | Medium; jurisdiction |
| LG-09 | Adjudicate court case | A | I | Court | EX; MB | C3,C5 | EC-02; no outcome → contested | EXT/REV | High |
| LG-10 | Conduct constitutional review | A | I | Constitutional court/body | EX; MB | C5 | EC-02; finality/scope required | EXT/REV | High |
| LG-11 | Enact legislation | A | I | Legislature | EX; Lex bridge | C5 | EC-01; official publication required | EXT/REV | High |
| LG-12 | Repeal legislation | A | I | Legislature/competent body | EX; Lex bridge | C3,C5 | EC-01; freeze affected claims | EXT/REV | High |
| LG-13 | Conduct administrative rulemaking | A | I | Rulemaking authority | EX; Lex bridge | C5 | EC-01; proposal ≠ final rule | EXT/REV | High |
| LG-14 | Formally publish law/rule | PR/A | I | Official gazette/publisher | EX; Lex adapter | C5 | EC-01; unofficial copy limited | EXT/REV | High |
| LG-15 | Provide legal advice | A | I | Authorized counsel | EX; MB | C5 | EC-02; advisory `may_not_use_for` final adjudication | REV | Medium |
| LG-16 | Determine administrative/legal appeal | A | I | Appeal body | EX; contestability bridge | C3,C5 | EC-02; competence/finality required | EXT/REV | High |
| LG-17 | Authorize legal remedy | A | I | Court/appeal/remedy authority | EX; MB | C3,C15 | EC-14; authorization ≠ execution | EXT/REV | High |
| LG-18 | Decide legal hold | PR/A | I | Competent records/legal authority | EX; core-audit bridge | C4,C12 | EC-15; absent hold status → no deletion | REV | High; pilot |

## C.4 Administrative procedure and individual decisions

| ID | Narrow function | L | V | Real operator | State; internal owner | Claim | Contract / absence → reaction | Surface | Conf./trigger |
|---|---|---|---|---|---|---|---|---|---|
| AP-01 | Accept citizen application | A | X | Administrative case system | EX; none | — | A9; external link only | NONE/EXT | High |
| AP-02 | Determine individual eligibility | A | X | Competent administrator | EX; PAO-R4 firewall | C14 | A9; PolicyOS output prohibited | NONE | High |
| AP-03 | Score individual risk | A | X | Authorized case authority, if lawful | EX; PAO-R4 firewall | C14 | A9; prohibited use | NONE | High |
| AP-04 | Impose individual sanction | A | X | Competent public authority/court | EX | C14 | A9 | NONE | High |
| AP-05 | Operate citizen case management | A | X | External case-management owner | EX | — | A9; no case workflow | NONE/EXT | High |
| AP-06 | Calculate statutory deadline | A | I | Case system/competent body | EX; MB | C3,C5,C15 | EC-04; unknown deadline → block dependent claim | REV | Medium; PAO-R5 |
| AP-07 | Apply tolling/extension | A | I | Competent case authority | EX; MB | C3,C5 | EC-04; late correction → replay delta | REV | Medium |
| AP-08 | Generate formal notice | A | I | Administrative authority | EX; MB | C15 | EC-04; generated ≠ served | EXT/REV | Medium |
| AP-09 | Effect legally valid service | A | I | Qualified delivery/service authority | EX; MB | C5,C15 | EC-05; no proof → not served claim | EXT/REV | High |
| AP-10 | Produce proof of service | A | I | Delivery/trust service | EX; MB | C5,C15 | EC-05; A2/A3/A7 | REV/MCH | High |
| AP-11 | Verify citizen identity | A | I | Sovereign/qualified IdP | EX; MB | C15 | EC-17; scope and assurance level required | REV | High |
| AP-12 | Verify representation/legal capacity | A | I | Registry/court/authority | EX; MB | C5,C15 | EC-17; expired authority → reject | REV | High |
| AP-13 | Accept administrative appeal | A | I | Appeal body/intake system | EX; MB | C3,C15 | EC-02/04; receipt only | EXT/REV | High |
| AP-14 | Adjudicate administrative appeal | A | I | Appeal body | EX; MB | C3,C5 | EC-02; no PolicyOS merits decision | EXT/REV | High |
| AP-15 | Accept correction request | A/PR | I | Record/case authority | EX; MB | C3,C12 | EC-04/15; intake ≠ correction | EXT/REV | High |
| AP-16 | Escalate external reviewer/case | A | I | Competent administrative body | EX; MB | C15 | EC-04; status external | EXT/REV | Medium |
| AP-17 | Authorize remedy | A | I | Remedy authority | EX; MB | C15 | EC-14; authorization only | EXT/REV | High |
| AP-18 | Execute remedy | A/I | I | Service/payment/administrative operator | EX; MB | C15 | EC-14; execution evidence required | EXT/REV | High |
| AP-19 | Conduct general citizen communications | A | X | Service/communications authority | EX | — | A9; separate formal notices | NONE/EXT | High |
| AP-20 | Maintain omnichannel service continuity | A/I | I | Service owner | EX; MB | C7,C15 | EC-19; external status, no delivery ownership | REV/EXT | Medium; PAO-R2 |
| AP-21 | Enforce policy-to-individual-decision firewall | E/A | O | PDC/export gate | PI/CO | C14 | EC-06; prohibited individual use blocks export | REV/MCH | High; PAO-R4 |
| AP-22 | Publish appeal outcome | A/PR | I | Appeal body | EX; MB | C3,C15 | EC-02; publication and finality distinct | EXT/REV | High |
| AP-23 | Revalidate PolicyOS claims after appeal | E | O | Decision validity | EI/IBO | C3,C5 | Admitted outcome → scoped cascade | REV/MCH | High |
| AP-24 | Track external remedy progress | A/I | I | Remedy operator | EX; MB | C15 | EC-14; reported ≠ completed | REV/EXT | Medium |

## C.5 Implementation and service delivery

| ID | Narrow function | L | V | Real operator | State; internal owner | Claim | Contract / absence → reaction | Surface | Conf./trigger |
|---|---|---|---|---|---|---|---|---|---|
| IM-01 | Produce implementation plan | E | O | PolicyOS design owner | PI | C1,C7 | Plan is advisory; no execution claim | REV | High |
| IM-02 | Assess operational feasibility | E | O | RQ/Foundry/PDC | PI | C1,C7 | Missing capacity evidence → limit/block | REV | High |
| IM-03 | Assess institutional capacity | E | O | RQ with external evidence | PI | C7 | EC-07; absent observable evidence → blocked | REV | High |
| IM-04 | Establish budget availability | I | I | Finance authority | EX; MB | C7,C15 | EC-08; budget claim unknown if absent | REV/EXT | High |
| IM-05 | Appropriate funds | I | I | Legislature/treasury | EX; MB | C5,C7,C15 | EC-08; proposal ≠ appropriation | EXT/REV | High |
| IM-06 | Run procurement | I | I | Procurement authority | EX; MB | C7,C15,C16 | EC-09; no execution ownership | EXT/REV | High |
| IM-07 | Execute/manage contract | I | I | Contracting authority | EX; MB | C7,C16 | EC-09; contract evidence/time required | REV | High |
| IM-08 | Manage supplier operationally | I | I | Contract/service owner | EX; MB | C7,C16 | EC-09; reported status only | REV | High |
| IM-09 | Schedule staff | I | X | HR/service operator | EX | — | A9; integrate capacity totals separately | NONE | High |
| IM-10 | Deliver staff training | I | I | Service/HR owner | EX; MB | C7 | EC-07; attendance ≠ competence | REV | Medium |
| IM-11 | Configure operational service | I | I | Service owner | EX; MB | C7,C15 | EC-07; configuration evidence | REV | Medium; PAO-R15 |
| IM-12 | Deliver service | I | I | Service owner/delivery provider | EX; MB | C7,C15 | EC-07; evidence required, no execution claim | EXT/REV | High |
| IM-13 | Deliver physical goods/service | I | I | Logistics/delivery body | EX; MB | C7,C15 | EC-07; receipt/coverage required | EXT/REV | High |
| IM-14 | Establish geographic capacity | I | I | Delivery authority | EX; MB | C7 | EC-07; local capacity cannot be assumed | REV | Medium |
| IM-15 | Exercise street-level discretion | A/I | V | Frontline authority | EX; none until admitted | —/C7 | Observe; later EC-07 admission | REV | Medium; PAO-R16 |
| IM-16 | Report operational variance | I | V | Delivery body | EX; MB | —/C7 | Observation only until verified/admitted | REV | Medium |
| IM-17 | Detect workarounds/shadow systems | I | V | Audit/operations observers | EX; MB | —/C7 | Candidate risk signal | REV | Medium; PAO-R17 |
| IM-18 | Execute rollout | I | I | Service/program owner | EX; MB | C7,C15 | EC-07; stage and population scope | REV/EXT | High |
| IM-19 | Scale deployment | I | I | Program authority | EX; MB | C7,C15 | EC-07; pilot evidence does not auto-transport | REV | High |
| IM-20 | Operate emergency mode | I | I | Emergency/service authority | EX; MB | C7,C15 | EC-19; emergency mandate/time required | REV | Medium |
| IM-21 | Operate manual fallback | I | I | Service operator | EX; MB | C7,C15 | EC-19; degraded evidence and reconciliation | REV | Medium |
| IM-22 | Operate hosting/infrastructure | I | I | Cloud/platform operator | EX; PI internal custody | C16,C17 | EC-19/20; outage → degraded custody | REV | High |

## C.6 Monitoring, evaluation and learning

| ID | Narrow function | L | V | Real operator | State; internal owner | Claim | Contract / absence → reaction | Surface | Conf./trigger |
|---|---|---|---|---|---|---|---|---|---|
| ML-01 | Define KPI contract and response semantics | E/I | O | DDM/OPS-R5 owner | PI | C7,C8,C13 | Definition/version required | REV/MCH | High |
| ML-02 | Observe KPI value | I | I | Data/operations owner | EX; MB | C8 | EC-11; missing ≠ target met | REV | High |
| ML-03 | Collect operational data | I | I | External collector | EX; Fabric bridge | C6,C8 | EC-11; source/admission gates | REV | High |
| ML-04 | Monitor PolicyOS claim validity | E/PR | O | DDM/decision validity | EI/IBO | C3,C8 | Stale/trigger → revalidation | REV/MCH | High |
| ML-05 | Operate programme monitoring | I | I | Program/service owner | EX; MB | C7,C8 | EC-11; operator owns process | REV | High |
| ML-06 | Perform causal diagnosis | E | O | Foundry/RQ | PI | C8,C13 | Unidentified cause → freeze adaptation | REV | High |
| ML-07 | Perform PolicyOS analytical evaluation | E | O | Foundry/Scientist/RQ | PI | C1,C8 | Candidate until verified | REV | High |
| ML-08 | Produce independent external evaluation | I | I | Evaluator/auditor | EX; MB | C8 | EC-12; independence and method required | REV/EXT | High |
| ML-09 | Attribute outcomes | E | O | RQ/Foundry | PI | C8,C13 | No ID → bounds/unknown | REV | High |
| ML-10 | Detect incident in PolicyOS/system evidence | E/I | O | DDM | EI | C3,C8,C17 | Trigger candidate/verified event | REV/MCH | High |
| ML-11 | Intake external incident report | I | I | Operator/regulator | EX; MB | C8,C15 | EC-13; alleged ≠ confirmed | REV | High |
| ML-12 | Officially classify incident | I | I | Competent investigator/regulator | EX; MB | C8 | EC-13; competence/finality required | REV/EXT | Medium |
| ML-13 | Report near miss | I | I | Operator/safety body | EX; MB | C8 | EC-13; missing report ≠ no near miss | REV | Medium |
| ML-14 | Assess public harm | I | I | Competent investigator/health authority | EX; MB | C8 | EC-13/14; scope and severity evidence | REV | Medium |
| ML-15 | Conduct post-deployment learning | E | O | GY O-block/RQ | PM/CO | C13 | Safety case required | REV/MCH | High; INT-R4 |
| ML-16 | Update world model | E | O | Fabric/RQ | PM/CO | C13 | Exploratory evidence cannot self-promote | REV/MCH | High |
| ML-17 | Update effect posterior | E | O | Foundry/RQ | PM/CO | C13 | Confirmatory evidence required | REV | High |
| ML-18 | Recommend adaptation | E | O | PDC/RQ | PI | C1,C13 | Human/mandate gate | REV | High |
| ML-19 | Automatically alter real policy | I | X | Competent public authority | EX | C9,C13 | A9; prohibited autonomous execution | NONE | High |
| ML-20 | Recommend rollback | E | O | PDC/RQ | PI | C1,C8 | Recommendation only | REV | High |
| ML-21 | Execute rollback | I | I | Program/service authority | EX; MB | C7,C15 | EC-07/19; execution evidence | EXT/REV | High |
| ML-22 | Recommend termination | E | O | PDC/RQ | PI | C1,C8 | Human/mandate decision required | REV | High |
| ML-23 | Terminate policy/program | I | I | Competent authority | EX; MB | C5,C15 | EC-07/16; official decision/effective time | EXT/REV | High |

## C.7 Public records and transparency

| ID | Narrow function | L | V | Real operator | State; internal owner | Claim | Contract / absence → reaction | Surface | Conf./trigger |
|---|---|---|---|---|---|---|---|---|---|
| PR-01 | Create PolicyOS public record | PR | O | PolicyOS publication owner | PI | C3,C10,C12 | Publication gates | PUB/MCH | High |
| PR-02 | Publish PolicyOS record | PR | O | DS12/runtime | PI/SM | C3,C10 | Missing proof → freeze | PUB/MCH | High |
| PR-03 | Correct PolicyOS record | PR | O | PAO-R36 owner | PI/SM | C3,C4,C12 | Append correction | PUB/MCH | High |
| PR-04 | Supersede PolicyOS record | PR | O | PDC/publication | EI/PI | C3,C4 | Visible lineage | PUB/MCH | High |
| PR-05 | Withdraw PolicyOS record | PR | O | Authorized principal | PI | C3,C10 | Human authority | PUB/MCH | High |
| PR-06 | Link archive and prior versions | PR | O | Core audit/publication | PI | C4,C10,C17 | Missing link → verification limitation | PUB/MCH | High |
| PR-07 | Publish machine-readable correction feed | PR | O | PAO-R36/DS13 | PM/SM | C3,C12 | Parity and cache invalidation | PUB/MCH | High |
| PR-08 | Issue transparency notice about PolicyOS | PR | O | PolicyOS claims register | PI | C3,C15 | Scope-bound language | PUB | High |
| PR-09 | Produce public explanation | PR | O | Atlas/PDC projection | PI | C2,C3 | Same-input; no persuasion laundering | PUB | High |
| PR-10 | Maintain public verification log | PR | O | INT-R7/DS12 | PI | C10,C17 | Revocation/anti-equivocation | PUB/MCH | High |
| PR-11 | Manage institution-wide record retention | PR | I | Records authority/controller | EX; MB | C12,C15 | EC-15; PolicyOS owns only own artifacts | REV/EXT | High |
| PR-12 | Decide records disposition | PR | I | Records authority/archivist | EX; MB | C12 | EC-15; unauthorized deletion blocked | REV | High |
| PR-13 | Process FOI request | PR/A | I | Public authority/FOI office | EX; MB | C12,C15 | EC-15; PolicyOS supplies records/evidence only | EXT | High |
| PR-14 | Process subject-access request | PR/A | I | Controller/privacy office | EX; MB | C12 | EC-15; identity/scope required | EXT | High |
| PR-15 | Redact PolicyOS projection | PR | O | Publication/privacy owner | PI | C3,C12 | Omission receipt and parity | PUB | High |
| PR-16 | Decide institutional disclosure/redaction | PR/A | I | Records/privacy authority | EX; MB | C12,C15 | EC-15; external legal decision | EXT/REV | High |
| PR-17 | Decide erasure/rectification of personal data | PR/A | I | Data controller/authority | EX; MB | C12 | EC-15; own downstream propagation | REV | High |
| PR-18 | Decide disclosure | PR/A | I | Competent records authority | EX; MB | C12,C15 | EC-15; no client-side inference | EXT | High |
| PR-19 | Impose legal hold | PR/A | I | Legal/records authority | EX; MB | C4,C12 | EC-15; hold overrides deletion | REV | High |
| PR-20 | Transfer institutional archive | PR | I | Records authority/archive | EX; MB | C4,C17 | EC-15; custody receipt | EXT/REV | High |
| PR-21 | Monitor third-party misinformation | PR/I | V | Communications/external observers | EX; UR | — | Observation only; corroborate before reaction | REV | Low; pilot |

## C.8 Incidents, appeals, remedies and harm response

| ID | Narrow function | L | V | Real operator | State; internal owner | Claim | Contract / absence → reaction | Surface | Conf./trigger |
|---|---|---|---|---|---|---|---|---|---|
| IR-01 | Intake PolicyOS-system incident | E/I | O | DDM/security | EI | C8,C17 | Internal incident event | REV/MCH | High |
| IR-02 | Intake external implementation incident | I | I | Operator/regulator | EX; MB | C8,C15 | EC-13; alleged status retained | REV | High |
| IR-03 | Validate external incident | I | I | Competent investigator | EX; MB | C8 | EC-13; no self-confirmation | REV | Medium |
| IR-04 | Investigate incident | I | I | Operator/regulator/independent investigator | EX; MB | C8,C15 | EC-13; investigation remains external | EXT/REV | High |
| IR-05 | Classify public harm | I | I | Competent authority | EX; MB | C8 | EC-13/14 | EXT/REV | Medium |
| IR-06 | Analyse near miss for PolicyOS claims | E | O | DDM/RQ | PI | C8,C13 | External evidence remains scoped | REV | High |
| IR-07 | Issue public warning about external harm | I/PR | I | Competent public authority | EX; MB | C3,C15 | EC-14; PolicyOS may relay with attribution | EXT/PUB | Medium |
| IR-08 | Admit appeal evidence | E | O | Contestability/RQ | PI | C3,C5,C6 | EC-02 admission gate | REV/MCH | High |
| IR-09 | Adjudicate appeal | A | I | Appeal body | EX | C3,C5 | EC-02; no merits claim by PolicyOS | EXT | High |
| IR-10 | Correct PolicyOS claims after appeal | E/PR | O | Decision validity/PAO-R36 | PI | C3,C4 | Scoped cascade | PUB/REV | High |
| IR-11 | Recommend compensation | E | O | PDC/human principal | PI | C1 | Advisory only | REV | Medium |
| IR-12 | Authorize compensation | A/FIN | I | Remedy/finance authority | EX; MB | C15 | EC-14; authorization status | EXT/REV | High |
| IR-13 | Pay compensation | FIN | I | Payment operator | EX; MB | C15 | EC-10/14; settlement required | EXT/REV | High |
| IR-14 | Recommend public apology | E | O | PDC/human principal | PI | C1 | Advisory; no issuance claim | REV | Medium |
| IR-15 | Issue public apology | PR/I | I | Accountable institution | EX; MB | C15 | EC-14; issued text/effective publication | EXT/PUB | High |
| IR-16 | Plan remediation | E | O | PDC/human principal | PI | C1,C7 | Plan ≠ execution | REV | High |
| IR-17 | Execute remediation | I | I | Service/program owner | EX; MB | C7,C15 | EC-14/07; execution evidence | EXT/REV | High |
| IR-18 | Notify affected person | A/PR | I | Competent notifying authority | EX; MB | C15 | EC-05/14; delivery proof separate | EXT | High |
| IR-19 | Track remedy | A/I | I | Remedy operator | EX; MB | C15 | EC-14; status explicitly reported | REV/EXT | Medium |

## C.9 Institutional and organizational functions

| ID | Narrow function | L | V | Real operator | State; internal owner | Claim | Contract / absence → reaction | Surface | Conf./trigger |
|---|---|---|---|---|---|---|---|---|---|
| ORG-01 | Assign legal/institutional mandate | I | I | Legislature/executive authority | EX; MB | C5,C9 | EC-03/16 | REV | High |
| ORG-02 | Designate responsible body | I | I | Competent authority | EX; MB | C5,C15 | EC-16 | REV/EXT | High |
| ORG-03 | Establish institutional succession | I | I | Competent legal authority | EX; MB | C5,C9,C15 | EC-16; old competence stale | REV | High |
| ORG-04 | Observe organizational reconfiguration | I | V | Institution/public records | EX; MB | — | Observation until competence impact admitted | REV | Medium |
| ORG-05 | Issue external delegation | I | I | Delegating authority | EX; MB | C9 | EC-03; scope/TTL/subdelegation | REV | High |
| ORG-06 | Enforce internal PolicyOS delegation | E | O | PDC/RQ/DS20 | PI | C9 | Wrong role/TTL → block | REV/MCH | High |
| ORG-07 | Validate acting appointment | I | I | HR/appointing authority | EX; MB | C9 | EC-03; effective interval | REV | High |
| ORG-08 | Validate quorum | I | I | Collegial body/secretariat | EX; MB | C9 | EC-03; quorum loss blocks act | REV | High |
| ORG-09 | Manage external conflict of interest | I | I | Institution/ethics authority | EX; MB | C9,C15 | EC-03/18 | REV | Medium |
| ORG-10 | Enforce internal reviewer COI gate | E | O | PDC/human review | PI | C9 | Missing independence → block | REV | High |
| ORG-11 | Record external recusal | I | I | Competent body | EX; MB | C9 | EC-03; recusal scope | REV | High |
| ORG-12 | Verify reviewer certification | I | I | Certifying authority | EX; MB | C9 | EC-03; expiry watched | REV | High |
| ORG-13 | Establish cross-agency reliance | I | I | Relying and supplying agencies | EX; MB | C5,C15 | EC-16; reliance terms/version | REV | Medium; pilot |
| ORG-14 | Perform interagency handoff | I | I | Partner agencies | EX; MB | C15 | EC-16; receipt and responsibility chain | REV | Medium |
| ORG-15 | Conduct external audit | I/PR | I | Independent auditor/SAI | EX; external-audit adapter | C3,C10,C15 | EC-18; package ≠ opinion | EXT/REV | High |
| ORG-16 | Exercise independent oversight | I | I | Regulator/oversight body | EX; MB | C3,C15 | EC-18; scope/finality | EXT/REV | High |
| ORG-17 | Conduct legislative oversight | I | V | Legislature/committee | EX | — | Observe unless formal finding admitted | EXT | High |
| ORG-18 | Conduct ombudsman review | A/I | I | Ombudsman | EX; MB | C3,C15 | EC-02/18 | EXT/REV | High |
| ORG-19 | Conduct judicial review | A/I | I | Court | EX; MB | C3,C5 | EC-02 | EXT/REV | High |
| ORG-20 | Exercise political accountability | I | V | Ministers, legislature, electorate | EX | — | Context only unless formal act | EXT | High |

## C.10 Finance, payments and suppliers

| ID | Narrow function | L | V | Real operator | State; internal owner | Claim | Contract / absence → reaction | Surface | Conf./trigger |
|---|---|---|---|---|---|---|---|---|---|
| FIN-01 | Prepare institutional budget | I | I | Finance/program authority | EX; MB | C7,C15 | EC-08; proposal status explicit | REV | High |
| FIN-02 | Appropriate budget | I | I | Legislature/treasury | EX; MB | C5,C7 | EC-08; final authority required | EXT/REV | High |
| FIN-03 | Model costs and proportionality | E | O | Foundry/PDC | PI | C1,C7 | External prices/data admitted separately | REV | High |
| FIN-04 | Authorize payment | FIN | I | Finance authority | EX; MB | C15 | EC-10; authorization ≠ execution | REV/EXT | High |
| FIN-05 | Execute payment | FIN | I | Payment operator/bank | EX; MB | C15 | EC-10; settlement evidence | EXT | High |
| FIN-06 | Reconcile payments | FIN | I | Finance system/auditor | EX; MB | C15 | EC-10; period/account scope | REV | High |
| FIN-07 | Execute clawback | FIN/A | I | Competent recovery authority | EX; MB | C15 | EC-10; finality and amount | EXT/REV | High |
| FIN-08 | Operate fraud controls | FIN/I | I | Finance/control authority | EX; MB | C7,C15 | EC-10/13; alert ≠ fraud finding | REV | Medium |
| FIN-09 | Execute compensation payment | FIN | I | Treasury/payment operator | EX; MB | C15 | Cross-reference IR-13 | EXT | High |
| FIN-10 | Conduct procurement | I/FIN | I | Procurement authority | EX; MB | C7,C16 | EC-09 | EXT/REV | High |
| FIN-11 | Select vendor | I/FIN | I | Procurement/contract authority | EX; MB | C7,C16 | EC-09; PolicyOS may analyse, not select | EXT | High |
| FIN-12 | Admit vendor evidence | E | O | RQ/Fabric/audit | PI | C6,C16 | EC-09/18; vendor self-eval not independent | REV | High |
| FIN-13 | Monitor supplier performance | I | I | Contract owner | EX; MB | C7,C16 | EC-09; observed report admitted separately | REV | High |
| FIN-14 | Maintain evidence escrow | I/E | I | Escrow/audit provider | EX; MB | C6,C16 | EC-09/18; access rights/TTL | REV | Medium |
| FIN-15 | Grant independent audit access | I | I | Supplier/contract owner | EX; MB | C6,C16 | EC-18; access receipt | REV | Medium |
| FIN-16 | Manage license | I | I | Rights owner/contract authority | EX; MB | C16 | EC-20; scope/expiry | REV | High |
| FIN-17 | Manage contract expiry | I | I | Contract authority | EX; MB | C16 | EC-20; watched dependency | REV | High |
| FIN-18 | Execute supplier exit | I | I | Contract/service owner | EX; MB | C7,C16 | EC-20; transition evidence | REV | Medium |
| FIN-19 | Conduct substitution drill | I | I | Service/contract owner | EX; MB | C16,C17 | EC-20; drill, not runbook claim | REV | Medium |

## C.11 Security, identity and infrastructure

| ID | Narrow function | L | V | Real operator | State; internal owner | Claim | Contract / absence → reaction | Surface | Conf./trigger |
|---|---|---|---|---|---|---|---|---|---|
| SEC-01 | Authenticate PolicyOS user/service | E/I | O | Runtime security | EI | C9,C12 | Missing/invalid auth → deny | NONE/REV | High |
| SEC-02 | Establish institutional identity | I | I | Government/directory authority | EX; MB | C9,C15 | EC-17; issuer/trust required | REV | High |
| SEC-03 | Establish citizen identity | A | I | Sovereign/qualified IdP | EX; MB | C15 | EC-17; `may_not_use_for` unrelated claims | NONE/REV | High |
| SEC-04 | Authorize internal PolicyOS action | E | O | DS20/runtime HTTP | EI | C9 | Missing permission/step-up → deny | REV/MCH | High |
| SEC-05 | Validate internal decision authority | E | O | PDC/RQ/human review | PI | C9 | Delegation/mandate required | REV | High |
| SEC-06 | Establish external administrative authority | A/I | I | Competent public body | EX; MB | C5,C9 | EC-03/16 | REV | High |
| SEC-07 | Manage PolicyOS signing keys | PR/I | O | Security/INT-R7 owner | PI | C10,C17 | Compromise → revoke/freeze/reissue | MCH | High |
| SEC-08 | Sign PolicyOS artifact | PR | O | Signing service | PI | C10 | Authority/epoch bound | PUB/MCH | High |
| SEC-09 | Verify public PolicyOS signature | PR | O | Public verifier | PI | C10 | Archived key/revocation checks | PUB/MCH | High |
| SEC-10 | Operate PolicyOS cybersecurity controls | I | O | Security/platform team | EI/PI | C12,C17 | Incident → internal response | REV | High |
| SEC-11 | Consume external cyber incident response | I | I | Provider/CERT/operator | EX; MB | C16,C17 | EC-13/19 | REV | High |
| SEC-12 | Operate physical/cloud hosting | I | I | Hosting provider/platform operator | EX; PI custody owner | C16,C17 | EC-19/20; outage/degraded mode | REV | High |
| SEC-13 | Execute PolicyOS disaster recovery | I/PR | O | Platform/custody owner | PI | C4,C10,C17 | Restore drill required | REV/MCH | High |
| SEC-14 | Back up PolicyOS custody state | I/PR | O | Platform owner | EI/PI | C4,C17 | Missing backup → readiness block | REV | High |
| SEC-15 | Preserve PolicyOS verification material | PR | O | INT-R7/OPS-R14 | PI | C10,C17 | Minimum before first public record | PUB/MCH | High |
| SEC-16 | Perform institutional archival preservation | PR | I | Archive/records authority | EX; MB | C10,C17 | EC-15; custody transfer evidence | EXT/REV | Medium |
| SEC-17 | Monitor external source availability | E/I | O | Fabric/Lex/H2 | PI | C6,C17 | Outage → unknown/stale, not no-event | REV/MCH | High |
| SEC-18 | Renew external credential | I | I | Credential issuer/operator | EX; MB | C16,C17 | EC-20; expiry event | REV | High |
| SEC-19 | Monitor license expiry | E/I | O | H2/RQ dependency watcher | PM/CO | C16 | EC-20; pre-expiry escalation | REV/MCH | High |

# Appendix D. Evidence-Contract Catalogue

All contracts inherit the shared envelope in §7.3.

| ID | Family-native payload | External producer | Authority and verification | Required clocks | Missing/corrected behavior | Permitted / prohibited use |
|---|---|---|---|---|---|---|
| EC-01 | Legal publication, amendment, repeal, corrigendum, entry into force | Official publisher/competent authority | Source authenticity, hierarchy, competence, jurisdiction, provision scope | adoption, publication, effective, observed, admitted, tx | Missing official source blocks binding legal claim; correction opens impact review | Legal applicability only; not implementation or outcome proof |
| EC-02 | Court, appeal, ombudsman or other adjudicative outcome | Competent forum | Identity, mandate, case/claim scope, finality, appealability, signature | decision, effective, publication, receipt, admission | No outcome → contested; corrected/reversed outcome supersedes | May change affected claims; may not imply PolicyOS adjudicated |
| EC-03 | Mandate, delegation, appointment, quorum, recusal, certification | Competent appointing/delegating body | Subject matter, role, jurisdiction, amount, TTL, subdelegation, COI | valid/effective, revocation, observed, admitted | Missing/expired/wrong scope blocks action | Authorizes only declared action; no monotone permission |
| EC-04 | Administrative deadline, tolling, notice generation, intake/status | Case-management authority | Case identity, rule version, authority, dedupe, correction | event, legal deadline, effective, observed, admitted | Missing status unknown; late event preserves old replay and triggers impact | Procedure status only; not merits or service proof |
| EC-05 | Delivery and proof of service | Qualified trust/delivery or competent service | Sender/recipient identity, integrity, delivery class, jurisdictional sufficiency | sent, received, legal-effective, observed, admitted | Send receipt alone insufficient; revoked proof invalidates dependent claim | Proof of narrow delivery fact; not content correctness |
| EC-06 | Individual-decision handoff and return evidence | External case system | Aggregate/anonymized or rule-level scope, prohibited individual uses | decision period, return time, admission | Any individual-use leakage blocks export | Aggregate implementation evidence only |
| EC-07 | Capacity, configuration, rollout, delivery and implementation evidence | Service/program owner | Population, denominator, geography, process, completeness, operator competence | service period, measurement, publication, admission | Missing data blocks delivery claim; revisions trigger recompute | Feasibility/delivery evidence; not legal authority |
| EC-08 | Budget proposal, appropriation, availability and authority | Legislature/treasury/finance owner | Fiscal authority, amount, purpose, period, encumbrance | budget period, enactment, effective, admission | Proposal cannot pass as appropriation; expiry/reduction revalidates | Fiscal feasibility only |
| EC-09 | Procurement, contract, vendor selection, supplier performance, escrow | Procurement/contract owner/supplier/auditor | Procedure authority, contract, supplier chain, independence, audit rights | tender, award, contract effective/expiry, report, admission | Missing audit access or expiry caps supplier evidence | Supplier/contract claims only; vendor self-eval not independent |
| EC-10 | Payment authorization, settlement, reconciliation, clawback | Treasury/payment operator | Account/transaction identity, authorization chain, settlement finality, amount/currency | authorized, initiated, settled, reconciled, reversed, admitted | Authorization ≠ settlement; reversal supersedes paid state | Narrow transaction state only |
| EC-11 | KPI observation and operational measurement | Data/operations owner | Metric definition version, basis, population, lineage, revision policy | observation, vintage, publication, admission | Missing observation unknown; definition change opens epoch | Monitoring evidence; threshold does not auto-adapt policy |
| EC-12 | Independent evaluation and attribution | Evaluator/auditor/research body | Independence, protocol, estimand, data, method, uncertainty, conflicts | preregistration, observation, report, admission | Unidentified effect remains bounded/unknown | Supports declared evaluation claim only |
| EC-13 | Incident, near miss, safety and harm report | Operator, regulator, investigator | Reporter role, affected scope, corroboration, severity, causal posture | occurrence, detection, report, correction, admission | Absence ≠ no incident; alleged report downgrade-only | Trigger/review evidence until adjudicated |
| EC-14 | Remedy, remediation, compensation or apology | Remedy/finance/accountable authority | Authorization, execution owner, affected class, amount/action, finality | ordered, effective, executed, paid/issued, admitted | Each stage separate; correction/reversal propagates | Supports only evidenced stage |
| EC-15 | Retention, disclosure, FOI/SAR, redaction, erasure, hold, archive | Records/privacy/legal authority | Authority, record scope, legal basis, retention schedule, security class | request, hold, disposition, transfer, correction, admission | Hold blocks deletion; corrected decision supersedes | Records handling only; not claim merits |
| EC-16 | Responsible body, institutional succession, reliance and handoff | Competent institutional authority | Mandate, successor/predecessor, transferred scope, acceptance | transition effective, publication, admission | Old authority becomes stale; unresolved succession freezes reliance | Competence/responsibility only |
| EC-17 | Institutional/citizen identity, representation and capacity | Sovereign IdP, registry, court, authorized provider | Issuer, assurance level, subject, purpose, representation scope | issuance, valid interval, revocation, admission | Missing/revoked identity blocks dependent act | Identity for declared purpose only |
| EC-18 | External audit and oversight finding | Auditor, SAI, regulator, ombudsman | Independence, mandate, criteria, evidence scope, opinion type | engagement, report, finality, admission | Audit package alone cannot substitute; correction supersedes finding | Supports audit/oversight conclusion only |
| EC-19 | Service continuity, degraded mode, manual fallback, hosting/DR status | Service/platform operator | Mode, scope, capacity, continuity plan, tested recovery, reconciliation | outage, mode change, recovery, admission | Outage unknown/stale; no silent fallback authority | Operational status only |
| EC-20 | Credentials, licenses, contracts, rights, expiry and supplier exit | Issuer/rights/contract owner | Right type, scope, expiry, renewal, grace, successor | issuance, expiry, renewal, revocation, admission | Expiry is watched event; no sudden silent runtime failure | Dependency authority only |
| EC-21 | Authoritative language and translation evidence | Official publisher/certified translator | Source-language anchor, semantic IDs, scope/negation/numeric parity | source version, translation version, admission | Semantic strengthening blocks projection | Language equivalence only; not substantive authority |

# Appendix E. Deferred Activation Review

“Trigger assessment” evaluates whether the backlog trigger is enough to open research, not enough to authorize production.

| ID | Provisional verdict after PAO-R1 | Trigger assessment | Interface that can be frozen now | Additional pilot facts | Disposition |
|---|---|---|---|---|---|
| OPS-R12 | OWN custody scheduler | 50 cases is necessary but not sufficient; require real contention/fan-out | Case priority and authority-dependency descriptors | owners, SLAs, public-freeze rules, queue economics | Remain deferred |
| OPS-R13 | OWN interaction model; deployment facts INTEGRATE | Two deployed policies sharing resources is sufficient to activate | Cross-policy dependency evidence | common population/budget/capacity and real interaction | Remain deferred |
| PAO-R2 | INTEGRATE | First service partner sufficient to activate | EC-19 service-episode evidence | channels, operator, continuity semantics, legal effect | Remain deferred |
| PAO-R3 | Split: OWN PolicyOS accessibility; INTEGRATE external journey | Direct citizen pilot sufficient to activate | Accessibility/language evidence envelope | supported channels, disability/language duties, operator | Remain deferred |
| PAO-R5 | INTEGRATE | Administrative-procedure pilot sufficient to activate | EC-04 clocks/tolling | applicable law, system of record, correction rules | Remain deferred |
| PAO-R6 | INTEGRATE | Legally effective notice pilot sufficient | EC-05 | delivery provider, evidentiary class, legal sufficiency | Remain deferred |
| PAO-R7 | INTEGRATE | Requires a real breach/remedy regime, not only R5/R6 | EC-04/14 | consequence authority, remedy owner, deadlines | Remain deferred |
| PAO-R8 | INTEGRATE | External participants sufficient to activate | EC-17 | accepted identity/representation providers | Remain deferred |
| PAO-R9 | INTEGRATE outcome; OWN reaction | Appeal-body partner sufficient | EC-02/14 | standing, finality, remedies, operator system | Remain deferred |
| PAO-R10 | INTEGRATE institution-wide; OWN own records | Records-regulated partner sufficient | EC-15 | schedules, records officer, archive, legal holds | Remain deferred |
| PAO-R11 | INTEGRATE | First demand sufficient to activate, but too late for baseline privacy design | EC-15 | request authority, exemptions, redaction owner | Remain deferred; prefreeze export hooks |
| PAO-R12 | INTEGRATE decision; OWN propagation | Personal-data pilot sufficient | EC-15 | controller, lawful basis, erasure exceptions | Remain deferred |
| PAO-R13 | INTEGRATE hold; OWN preservation reaction | Litigation sufficient | EC-15 | issuing authority, scope, release process | Remain deferred |
| PAO-R14 | OWN fidelity comparison; enactment INTEGRATE | First enacted design sufficient | EC-01 plus design-diff receipt | official enacted text and implementation owner | Remain deferred |
| PAO-R15 | INTEGRATE service configuration | Enacted design entering service sufficient | EC-07 | configuration system, mapping, local overrides | Remain deferred |
| PAO-R16 | OBSERVE by default; admitted variance becomes INTEGRATE | Multi-office deployment sufficient | Observation envelope + EC-07 promotion | offices, discretion authority, sampling | Remain deferred |
| PAO-R17 | OBSERVE | Multi-office deployment sufficient | Candidate workaround signal | detection channel, non-retaliation, corroboration | Remain deferred |
| PAO-R18 | INTEGRATE | Funded pilot sufficient | EC-08 | appropriation and treasury systems | Remain deferred |
| PAO-R19 | INTEGRATE | Procured dependency sufficient | EC-09/20 | procurement rules, contract owner, supplier chain | Remain deferred |
| PAO-R20 | INTEGRATE | Payment-bearing pilot sufficient | EC-10 | payment rails, settlement, reconciliation, fraud authority | Remain deferred |
| PAO-R21 | INTEGRATE | Physical-delivery pilot sufficient | EC-07 | logistics operator, geography, receipt evidence | Remain deferred |
| PAO-R22 | INTEGRATE | Participant deployment sufficient | EC-07/11 | eligibility denominator, take-up, burden measures | Remain deferred |
| PAO-R23 | Decompose: enforcement execution OUT; effects OBSERVE/INTEGRATE | Enforcement pilot sufficient | Observation plus EC-07/13 | discretion, complaints, sanctions, competent authority | Remain deferred; broad class should be split |
| PAO-R27 | INTEGRATE | First production provider sufficient | EC-20 | exit rights, alternative provider, data portability, drill owner | Remain deferred |
| PAO-R29 | INTEGRATE | Second institution relying on record sufficient | EC-16 | reliance agreement, acceptance, liability, versions | Remain deferred |
| PAO-R30 | Merge with OPS-R13 | Same trigger sufficient | Same cross-policy interface | same interaction facts | Merge at activation |
| PAO-R31 | Reclassify: INTEGRATE when succession changes competence; OBSERVE otherwise | Institutional change sufficient | EC-16 | legal succession, mandate transfer, effective time | Remain deferred with corrected split |
| PAO-R32 | Split: OWN display/custody semantics; INTEGRATE external degraded status | First operational deployment sufficient | EC-19 | fallback operator, reconciliation, public meaning | Remain deferred |
| PAO-R33 | OBSERVE; admitted incident/KPI evidence can become INTEGRATE | Adversarial-stakeholder pilot sufficient | Candidate risk signal | capture pathways, corroboration, independent forum | Remain deferred |
| PAO-R34 | OWN sealed admission receipt; external compartment owner INTEGRATE | First decisive sealed-evidence case sufficient | Sealed evidence receipt | clearance, verifier, disclosure limits, replay | Remain deferred |
| PAO-R35 | Protected intake/investigation OUT; findings INTEGRATE | Institutional demand alone is insufficient; require statutory operator | EC-13/18 | protected channel, anti-retaliation, investigator, disclosure authority | Remain deferred |
| PAO-R37 | OWN evaluation safety; rollout execution INTEGRATE | Adaptive/randomized pilot sufficient | EC-12/13 plus safety gate | treatment authority, stopping rules, harms, rollback owner | Remain deferred |
| PAO-R38 | OWN minimum custody; institutional archive INTEGRATE | INT-R7 residuals or archive program sufficient | EC-15/20 | archive succession, format migration, 10–30 year owner | Remain deferred after minimum |
| PAO-R39 | OWN cost model; external costs INTEGRATE | Fleet formation sufficient | EC-08/09/10 cost evidence | staffing, review, archive and partner costs | Remain deferred |
| PAO-R40 | OBSERVE horizon signals; admission/reaction OWN | Post-pilot alone too vague; require named signal source and decision use | Candidate signal envelope | sources, false-positive cost, owner, trigger | Remain deferred; refine trigger |
| PAO-R41 | OWN control coherence | W10 closure or large control inventory sufficient | Rule/conflict/debt record | actual rule graph, owners, precedence, incidents | Remain deferred |
| OPS-R14 overlap | OWN custody; external renewal/DR evidence INTEGRATE | Active already, not deferred | EC-15/20 | key/archive provider and drills | Consolidate with INT-R7 |
| PAO-R36 rider | OWN correction; third-party misinformation OBSERVE/INTEGRATE | Third-party monitoring should remain deferred | Correction interface | public record channels and competent notice operators | Keep narrow active core |

# Appendix F. Benchmark Fixture Catalogue

| Fixture | Scenario | Expected verdict/decomposition | Expected absence behavior | Unsafe conclusion | Patterns |
|---|---|---|---|---|---|
| BND-001 | Appeal outcome from competent body | Adjudication I; admission/revalidation O | Missing → contested | PolicyOS resolved appeal | P05/P13 |
| BND-002 | Appeal link with no real case/forum | Block | No recourse evidence | “Appealable” | P10/P26 |
| BND-003 | Notice “sent” only | Notice I; service unproven | Block service-dependent claim | Legally served | P10 |
| BND-004 | Qualified proof of service | I | Admit narrow delivery fact | PolicyOS delivered notice | P05 |
| BND-005 | Compensation authorized, unpaid | I stages separate | Payment unknown | Compensation complete | P10/P14 |
| BND-006 | Payment settled then reversed | I | Supersede paid state | Still paid | P08 |
| BND-007 | Delivery dashboard without source | V/projection only | Unknown | Service delivered | P03/P05 |
| BND-008 | Service owner report with provenance | I | Admit scoped report | PolicyOS delivered service | P13 |
| BND-009 | External source outage | I dependency | Unknown/stale | No event occurred | P10 |
| BND-010 | Ministry succession | I competence event | Freeze old authority | Old signer remains valid | P08 |
| BND-011 | Broad “appeals” row | Must decompose | Register validation fails | One verdict | P04/P31 |
| BND-012 | Generic task queue gains citizen fields | X scope inflation | Architecture block | PolicyOS case manager | P13 |
| BND-013 | Legal source externally published | Publication I; sensing O | Missing official version blocks | PolicyOS enacted law | P05 |
| BND-014 | OBSERVE capture signal wired to claim | Invalid upgrade | Admission required | Capture proven | P15 |
| BND-015 | OUT individual decision with returned aggregate data | Decision X; aggregate evidence I | Enforce firewall | PolicyOS decides eligibility | P13/P19 |
| BND-016 | New local appeals schema beside ADR-0170 | Reject P27 | Extend owner | New canonical owner | P27 |
| BND-017 | Atlas label changed to “resolved” | Projection test fails | No authority change | UI label creates fact | P03/P05 |
| BND-018 | Signed outcome wrong jurisdiction | Reject scope | A7 | Signature closes claim | P32 |
| BND-019 | Auditor package produced internally | Package O; independent opinion absent | Limited | Independent audit passed | P05 |
| BND-020 | External independent audit received | I finding; O reaction | Revalidate affected claims | PolicyOS performed audit | P13 |
| BND-021 | KPI threshold crossed | Observation I; diagnosis O | Freeze auto-adaptation | Policy changed automatically | P24 |
| BND-022 | Metric definition revised | I event; O epoch/revalidation | New epoch | Trend is continuous | P08 |
| BND-023 | Incident in media only | V/candidate trigger | Corroborate | Confirmed incident | P10 |
| BND-024 | Regulator confirms incident | I | Scoped revalidation | PolicyOS investigated | P13 |
| BND-025 | Workflow rollback compensation event | O internal technical event | Never public compensation | Affected people compensated | P05 |
| BND-026 | Procurement score from vendor | I candidate; not independent | Limit | Supplier independently verified | P14 |
| BND-027 | Contract expires overnight | I watched dependency | Freeze affected use | Continue silently | P09 |
| BND-028 | FOI request arrives before scheduled deletion | I records event | Hold preservation | Delete as scheduled | P08 |
| BND-029 | Political criticism | V | No claim effect absent formal evidence | Claim invalidated | P10 |
| BND-030 | Court judgment reverses legal basis | I | Freeze/revalidate/supersede | Historical case rewritten | P07/P08 |
| BND-031 | Partner system sends duplicate event | I | Dedupe, one reaction | Duplicate irreversible action | P29 |
| BND-032 | Conflicting agency and court outcomes | I contested | Competent precedence/human review | Average outcomes | P04/M31 |
| BND-033 | Citizen identity token reused for another purpose | I scope mismatch | Reject | Identity proves eligibility | P32 |
| BND-034 | Public record cached after supersession | O correction | Invalidate cache | Old record current | P03 |
| BND-035 | H2 worker attempts payment API | X execution attempt | Hard block/count | Custody runtime pays | P13 |
| BND-036 | H2 receives settlement evidence | I | Bind and update claim | Evidence receipt = payment execution | P05 |
| BND-037 | Institutional transition merely changes name | V unless competence changes | Observe | Mandatory revalidation always | P13 |
| BND-038 | Transition changes mandate | I | Revalidate competence | No authority effect | P05 |
| BND-039 | Missing INTEGRATE absence rule | Block register row | Validation failure | Implicit pass | P01/P10 |
| BND-040 | Superseded boundary row deleted | Fail history test | Append-only successor required | Current decision rewrites history | P07/P08 |

# Appendix G. Stage-0 Boundary Anchor Packet

## G.1 Identity

PolicyOS is the epistemic custodian of policy justification. It owns what it signs and the machinery needed to keep those signatures honest. It does not become the operator of every institution whose actions affect those signatures.

## G.2 Four-way test

```text
absence makes our signed claim silently false
  → OWN the narrow epistemic/custody function

external output changes our claim’s validity or scope
  → INTEGRATE through a typed, fail-closed evidence contract

information changes context or who answers, but not claim validity
  → OBSERVE; no authority until separately admitted

none of the above, or performance violates an anti-role
  → OUT_OF_SCOPE
```

## G.3 Mandatory decomposition

Every broad function is decomposed into:

1. institutional act;
2. evidence emission;
3. PolicyOS admission;
4. PolicyOS claim reaction;
5. public projection.

These layers may have different verdicts.

## G.4 Ownership fields

Never use one ambiguous owner. Record:

- `real_operator`
- `external_evidence_producer`
- `policyos_adapter_owner`
- `policyos_claim_reaction_owner`
- `surface_projection_owner`

## G.5 INTEGRATE minimum

Every INTEGRATE row requires:

- producer identity and competence;
- tenant, jurisdiction and subject scope;
- event/effective/observation/admission/transaction times;
- schema and rule version;
- provenance and integrity;
- binding/advisory/alleged status;
- `authoritative_for` / `may_not_use_for`;
- correction and revocation links;
- missing, stale, conflicting and unavailable behavior;
- affected claims and required reaction.

An INTEGRATE row without fail-closed absence behavior is invalid.

## G.6 OBSERVE minimum

An observation:

- may inform risk awareness;
- does not prove institutional performance;
- does not alter a claim;
- may become evidence only through a new admitted artifact and explicit transition.

## G.7 OUT minimum

PolicyOS may:

- state that the function is external;
- link to the competent authority;
- display a clearly bounded external status;
- block its own claim when required external evidence is absent.

It may not perform the function.

## G.8 Non-negotiable anti-roles

PolicyOS is not:

- a public administrator;
- a citizen case-management system;
- a court or appeal body;
- a payment system;
- a legally effective notification channel;
- a service-delivery operator;
- a procurement, HR, records-management or ERP platform;
- a sovereign identity provider.

## G.9 Core ownership

PolicyOS owns:

- design and grounding;
- evidence admission;
- authority-boundary derivation;
- its own signing and publication;
- staleness and revalidation;
- correction, reissue, supersession and withdrawal;
- historical replay;
- its own provenance, audit and verification;
- internal action authorization;
- safe learning and world-model update.

## G.10 Capstone rule

OPS-R15 must show:

```text
out_of_boundary_actions_attempted = 0
```

while proving that external evidence is correctly admitted, bound, replayed and translated into scoped PolicyOS reactions.

---

# Final Research Posture

The strongest defensible conclusion is:

> PolicyOS should own the epistemic and custody functions required to keep its own signed claims valid across time. It should integrate external administrative, legal, implementation, institutional, financial and public-record events only through typed, provenance-bearing, versioned and fail-closed evidence contracts where those events can change claim validity. It may observe broader institutional context for accountability or risk awareness, but observation must not be upgraded into authority. It must exclude sovereign and administrative functions such as individual adjudication, legally effective notification, payment execution, service delivery, court functions and general case management.
>
> The operational-boundary register must classify narrow functions rather than broad lifecycle families; separately identify the real operator, evidence producer, PolicyOS adapter, claim-reaction owner and projection owner; define missing-evidence behavior; and preserve every boundary decision as a versioned, challengeable research assertion rather than an unchangeable code contract.
>
> The framework is sufficiently coherent and repository-grounded to serve as the Stage-0 adjudication baseline. Production verdicts for institution-specific functions remain conditional on jurisdiction, competent authority, partner systems, real evidence flows and the OPS-R15 capstone.
