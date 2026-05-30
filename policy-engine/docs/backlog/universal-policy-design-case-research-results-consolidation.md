---
title: Universal Policy Design Case Research Results Consolidation
status: normalized-final-synthesis-draft
owner: team-policyos
created: 2026-05-21
updated: 2026-05-22
source_scope: deep-research-report-105..146
raw_source: docs/research/universal-policy-design/deep-research-reports-105-146-combined.md
research_plan: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md
implementation_plan: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md
failure_patterns: docs/reference/policy-design-case-failure-patterns.md
source_ownership: docs/reference/policy-design-case-source-ownership.md
---

# Universal Policy Design Case Research Results Consolidation

This document is the normalized synthesis of the universal Policy Design Case
research stream. The raw source of individual research outputs is
`docs/research/universal-policy-design/deep-research-reports-105-146-combined.md`.
This file is no longer a report-by-report ledger. It is the cross-report
analysis: shared terminology, decisions, dependency structure, unresolved
theory, and engineering-readiness implications.

The synthesis covers C0-C41:

- C0-C27: baseline, formal semantics, producer and claim binding, external
  surfaces, lifecycle, evaluation, and implementation readiness.
- C28-C41: post-synthesis closeout questions on concept spine physical form,
  effective independence, semantic benchmarks, acceptable deficits, complexity,
  rule evolution public policy, participation legitimacy, calibration blocking,
  capability debt, bridge authority, obligation explosion, external legitimacy,
  producer liveness, and historical-priors firewall.

Source ownership is governed by
`docs/reference/policy-design-case-source-ownership.md`. This synthesis is the
normalized control point between the raw ledger, the research plan, the
implementation plan, and the ADR/doc gates; it should be cited before the raw
ledger when a later engineering task needs the stable C/E/P interpretation.

## Synthesis Method

This pass used evidence-synthesis rather than append-only summarization:

- keep source traceability but do not preserve every paragraph;
- group findings by mechanisms, not by download order;
- separate stable kernel, bridge-new integration, and research-only decisions;
- preserve formulas and decision tables where they are load-bearing;
- treat disagreement as information about scope, authority level, or
  implementation state;
- avoid vote counting: repeated findings matter only when they reveal the same
  failure mechanism.

External synthesis practices used in earlier passes remain the method
reference: PRISMA-ScR-style source inventory, JBI-style data charting,
Thomas/Harden-style thematic synthesis, RAMESES-style context-mechanism-outcome
reasoning, SWiM-style transparent narrative synthesis, and evidence-gap-map
matrix thinking.

## Executive Finding

PolicyOS does not need a new universal policy engine from scratch. It already
has strong internal kernels:

- runtime assurance and authority envelopes;
- formal closeout invariants;
- policy design record-family registry;
- claim lifecycle and claim support predicates;
- SourceContract/Data Forge/Fabric/Lex/Scholar/Foundry surfaces;
- IR proof-carrying analytics;
- temporal logic for obligations;
- public/export projection guardrails;
- challenge factory, VOI, calibration, DDM, and audit primitives.

The main system gap is not lack of components. It is **claim-bound, authority
preserving orchestration**:

```text
strong producer artifacts
  -> thin bridge / missing spine / incomplete claim registry binding
  -> local pass fields diverge from reader truth
  -> public or dashboard surfaces cannot reconstruct the case
```

The universal Policy Design Case should therefore be a compiled runtime object:

```text
request and authority profile
  -> universal policy grammar
  -> governed candidate obligations
  -> concept/time/legal spine
  -> producer handshake
  -> claim-bound evidence registry
  -> argument, warrant, conflict, independence, and portfolio graph
  -> unified closeout substrate
  -> typed multi-audience projection
  -> lifecycle revalidation, calibration, and memory
```

The core research answer is also clear: PolicyOS can avoid hundreds of hard
domain adapters, but not by replacing knowledge with LLM text. The right form is
universal fields plus a small governed rule kernel. LLMs may generate
candidates; runtime producers, admissibility, authority envelopes, and closeout
decide whether anything becomes evidence, limitation, blocker, or rejected
speculation.

## Normalized Task Map

| Task range | Normalized role | Engineering posture |
| --- | --- | --- |
| C0 | Capability baseline and canonical paths | Ready for capability ratchet |
| C1-C3 | Status, admissibility, authority, closeout | ADR-first, then shared substrate |
| C4-C5, C10, C38 | Universal grammar, obligations, baselines, obligation explosion | Mostly ready after priority/funnel policy |
| C6-C8, C11, C28, C40 | Concept spine, legal competence, time/geography, producer liveness | Bridge-new; concept-spine hybrid decision now exists |
| C9, C13-C15, C29 | Claim-method binding, independence, conflict, warrants | Bridge-new with strong IR/assurance seeds |
| C12, C25, C35, C41 | LLM and historical-prior firewalls | Ready as governance/firewall policy |
| C16, C39a | PDC projection structure and external legitimacy surface | Ready for typed projection engineering |
| C17-C19, C30, C34, C39b | Contestability, recourse boundary, tradeoffs, participation, semantic benchmark | Mostly ready; recourse mechanics are a decision backlog, not a research backlog |
| C20-C21, C33 | Lifecycle, rule evolution, public revalidation | Ready for semantic-lineage design |
| C22-C24, C31-C32, C36-C37 | Acquisition, cost, deficits, complexity, capability debt, bridge authority | Ready for policy matrices and closeout integration |
| C26-C27 | Evaluation and readiness | Ready to drive implementation planning |

## Canonical Vocabulary

| Term | Normalized meaning |
| --- | --- |
| Capability reality | A capability exists only when contract, producer, persisted artifact/event, bridge, consumer, verification, external or out-of-scope surface, and semantic/e2e test exist. |
| Capability debt | Typed incompleteness in that chain, such as `contract_only`, `bridge_missing`, `surface_missing`, or `semantic_test_missing`. |
| Authority-bearing artifact | Runtime artifact whose authority envelope permits a named authority purpose. |
| Projection-only artifact | Dashboard, API, public export, package, or diagnostic view that may display authority but cannot satisfy authority. |
| Candidate | LLM, critic, history, public contestation, or retrieval output that has not been admitted by a governed producer/reader path. |
| Claim-bound evidence | Evidence attached to a specific claim, not a global evidence pool. |
| Concept spine | Run-owned reconciled semantic authority across policy terms, metrics, columns, norms, methods, populations, geographies, time roles, units, and legal authority types. |
| Status envelope | Cross-system wrapper preserving local statuses while adding severity, blockingness, authority effect, publication scope, review action, owner, TTL, and closeout effect. |
| Soft gate | Warning/review state with owner, TTL, escalation, publication effect, and closeout effect. |
| Deficit | Missing or weakened obligation that is explicitly classified as accepted, limited, review-required, reissue-required, or blocking. |
| Effective independence | Evidence strength after collapsing shared source, lineage, method, author, institution, sponsor, assumption, DGP, legal authority, or LLM generation path. |
| Producer handshake | Protocol by which producers consume requirements/concepts, emit selected/rejected/blocked bindings, and expose blockers before downstream closeout. |
| Bridge record | Orchestration artifact proving boundary continuity, handoff, requirement propagation, or reader verification; not substantive domain evidence by default. |
| Current-run evidence | Evidence produced/admitted for the present run. Historical memory and calibration may affect routing but cannot close claims. |
| Semantic false pass | Structurally complete case whose content is wrong, unsupported, stale, scope-shifted, authority-laundered, or not publicly reconstructable. |
| Structural commitment | ADR decision about object shape, ownership, allowed transitions, authority boundary, or decision rule. It should be implemented and tested. |
| Tuned parameter | Threshold, weight, budget, minimum count, or timing value that may begin as a governed default and be calibrated later. |
| Decision backlog | Small set of explicit choices needed before engineering. It is not a new research cycle. |
| Recourse pointer | Typed, verified-reachable reference to the external or deployment-owned process where affected parties can contest a high-stakes PDC. |

## Unified Layer Model

| Layer | Owns | Main synthesis result |
| --- | --- | --- |
| L0 Capability | Canonical paths, shims, reality labels, debt | Capability is a chain, not a schema. |
| L1 Status and authority | Status lattice, admissibility, deficits, closeout effects | Preserve local enums but compose through shared envelope. |
| L2 Universal grammar | Facets, risks, obligation rules, baselines | No domain packs; use universal fields plus governed rules. |
| L3 Semantic spine | Concept, legal, time, geography, units | Hybrid: governed namespaces plus per-run spine artifact. |
| L4 Producer coordination | Handshake, liveness, bridge authority, acquisition | Producers must emit bindings/blockers, not broad context as authority. |
| L5 Claim registry | Data, norm, method, uncertainty, argument, warrant refs | Global evidence pools do not support claims. |
| L6 Evidence synthesis | Independence, conflict, portfolio, counterevidence | Raw count is not strength; conflict is a first-class fact. |
| L7 PDC compiler | Records, assurance graph, typed projection | Final output is a projection of runtime graph. |
| L8 Closeout substrate | Invariants, source truth, attestation, compatibility | One `can_i_closeout`, not many local pass flags. |
| L9 External legitimacy | Public, reviewer, expert, machine, audit surfaces | Legitimacy requires reconstructability and contestability. |
| L10 Lifecycle learning | Rule evolution, revalidation, calibration, memory | Historical learning changes future posture, not current evidence. |
| L11 Evaluation and self-FMEA | Semantic benchmarks, complexity, review effectiveness | Structural validation is necessary but insufficient. |

## System-Wide Firewalls

These firewalls are the most important safety conclusions.

| Firewall | Forbidden shortcut | Correct path |
| --- | --- | --- |
| LLM candidate | LLM risk/rule/legal/participation output satisfies evidence. | Store as candidate; admit only through deterministic/governed validation. |
| Projection | API/dashboard/public/export/package summary becomes authority. | Projection points to authority-bearing artifacts and carries forbidden-use metadata. |
| Historical priors | Calibration or memory closes/refutes current claim. | Priors adjust VOI, budget, uncertainty, review, provider choice, and authority cap only. |
| Raw count | Many lines imply strong evidence. | Collapse dependence and report effective support. |
| Legal retrieval | Topic/jurisdiction hit becomes legal authority. | Require competence, hierarchy, instrument, time, funding/implementation authority, and claim anchor. |
| Participation | Consultation summary or LLM speculation becomes affected-person preference. | Require provenance, representativeness, permitted claim use, dissent, and privacy-safe projection. |
| Schema compatibility | Readable payload equals same policy meaning. | Track rule lineage, taxonomy move, logic hash, and current-guidance status. |
| Bridge authority | Handoff/carrier record becomes producer evidence. | Bridge is authoritative only about its boundary and only with envelope, CAS, same-input, and reader compatibility. |
| Cost/degradation | Cost/latency signal silently changes evidence quality. | Route through budget state, degradation-SLA state, approval separation, and public limitation if material. |

## Decision Backlog Closeout

The third bucket is now reclassified. It is not "research still needed" in the
deep-report sense. It is a short decision backlog: each item should close by a
decision memo or ADR in one to three days, then move to engineering with
fixture-backed constraints.

ADR writers must separate:

- **Structural commitment:** committed schema, ownership, transitions,
  authority boundary, invariant, and negative tests.
- **Tuned parameter:** provisional thresholds, counts, weights, budgets, or
  deadlines that are config-governed, owned, and recalibrated later.

This split lets ADRs move on stable structure without pretending that early
numeric thresholds are final.

| Item | Closeout decision | Engineering effect |
| --- | --- | --- |
| C22 acquisition | Eligibility precedes ranking; mandatory gates dominate VOI; `accepted_deficit`, `publish_with_limitation`, and `closeout_block` are distinct; governed/production commit needs human/governed authority. | E17 can start after a decision-boundary ADR. |
| C19/C34 participation | Commit matrix structure `claim_use x authority_level x population_scope`; imperfect representativeness downgrades claim use instead of silently blocking or inflating; exact thresholds are governed config. | Participation schemas can implement claim-use downgrade and provenance checks now. |
| C17/C39b recourse | PolicyOS owns contestability records, public visibility, reopening triggers, recourse pointers, and recourse-outcome ingestion. It does not own universal appeal intake/adjudication/SLA. | PDC projection can expose contestability without pretending to be a tribunal. |
| C7 legal competence | Jurisdiction fallback is governed per-jurisdiction config; one norm may carry multiple authority types; competence changes split the claim by legal window. | Lex engineering ADR can proceed. |
| C24 liveness | Liveness is bounded: `eventually X` becomes `X within deadline D, else escalate`, verified as finite-state deadline consistency. | Closeout substrate can extend current safety invariants without full temporal model checking. |
| C24 review telemetry | Start advisory-only; measure override rate, review time, dissent, separation-of-duty failure, and no-delta reviews from existing metadata. Blocking consequences wait for longitudinal data. | E19 can collect telemetry now without adding premature gates. |

## Decisions Now Stable Enough

### Capability Reality And Capability Debt

The capability chain is:

```text
typed contract/artifact
  -> producer
  -> persisted artifact/event
  -> orchestration bridge
  -> consumer
  -> verification
  -> external/audit/API/dashboard surface or explicit out_of_scope
  -> semantic/e2e test
```

Reality states should be first-class:

- `contract_only`
- `producer_missing`
- `artifact_missing`
- `bridge_missing`
- `consumer_missing`
- `verification_missing`
- `implemented_but_not_orchestrated`
- `surface_missing`
- `surface_out_of_scope`
- `semantic_test_missing`
- `compatibility_shim`
- `projection_only`

C36 turns these into a debt algebra. Base points are:

| State | Points | Default interpretation |
| --- | ---: | --- |
| `surface_out_of_scope` | 0 | Valid only with rationale, owner, review date, and inspection path. |
| `compatibility_shim` | 1 | Low only off authority path and with sunset/dual-read evidence. |
| `projection_only` | 1 | Low only if consumer-side authority denial is enforced. |
| `contract_only` | 2 | A form exists but no capability chain. |
| `consumer_missing` | 2 | Artifact exists but nothing acts on it. |
| `surface_missing` | 2 | Internal truth is not externally observable. |
| `producer_missing` | 3 | Expected artifact has no producer. |
| `artifact_missing` | 3 | Logic exists but no persisted/replayable artifact. |
| `bridge_missing` | 4 | Producer and consumer exist but are not linked. |
| `implemented_but_not_orchestrated` | 4 | Component works locally but not in runtime chain. |
| `verification_missing` | 5 | Chain exists but no end-to-end proof. |
| `semantic_test_missing` | 5 | Structural proof exists but content adequacy does not. |

Purpose multipliers make the same debt more severe when it lies on evidence,
authority, closeout, or lifecycle paths:

| Purpose | Factor |
| --- | ---: |
| `internal_helper` | 0.5 |
| `diagnostic_only` | 0.75 |
| `public_surface` | 1.0 |
| `lifecycle_trigger` | 1.25 |
| `evidence_producer` | 1.5 |
| `closeout_input` | 1.75 |
| `authority_gate` | 2.0 |

Local debt:

```text
local_points =
  base_state_points * purpose_factor
  + serious_profile_premium
  + sole_path_premium
  + ownerless_or_expired_premium
  + chain_cluster_premium
  - mitigation_credit
```

Release/readiness bands:

| Zone | Condition | Decision |
| --- | --- | --- |
| Green | max severity <= medium, no blocker, authority-weighted debt < 12 | Ready |
| Yellow | one high outside authority/closeout or debt 12-20 with owner/expiry | Conditional |
| Orange | cluster rule or debt 20-30 without hard blocker | Not ready |
| Red | any blocker, laundering path, or debt > 30 | Freeze except remediation |

### Status, Admissibility, And Deficits

PolicyOS should not create a "god enum". It should preserve local statuses and
compose them through axes:

- severity: `ok < advise < warn < fail < invalidating`;
- blockingness: `none < soft_gate < hard_gate`;
- overridability: `not_needed < overridable < human_override_only < non_overridable`;
- authority tier;
- evidence tier;
- publication scope;
- readiness cap;
- degradation/proxy state;
- review action;
- closeout effect;
- owner, TTL, and escalation.

Admissibility states:

- `admissible`
- `context_only`
- `proxy_with_limitation`
- `contested`
- `blocked`
- `out_of_scope`

Deficit policy from C31 should be the cross-reader authority matrix. Deficits
include missing evidence, stale evidence, proxy evidence, weak independence,
unresolved concept, contested evidence, legal uncertainty, method limitation,
participation gap, cost/degradation limit, and lifecycle staleness.

| Deficit disposition | Meaning |
| --- | --- |
| `allowed_with_limitation` | Claim may proceed only with explicit limitation. |
| `internal_only` | Internal/reviewer use only, no public authority. |
| `human_review_required` | Soft gate with named owner and TTL. |
| `expert_review_required` | Higher review because authority or public impact is material. |
| `accepted_deficit` | Evidence cannot or should not be acquired now, and the deficit is explicit. |
| `reissue_required` | Existing/public case must be updated or reviewed. |
| `hard_blocking` | Closeout/publication cannot proceed in requested scope. |

Important invariant: accepted deficit, publish-with-limitation, and closeout
block are different states. "Publish with limitation" must never bypass a
mandatory gate.

### Concept Spine Physical Form

C28 resolves the biggest open semantic question: choose **hybrid concept
spine**.

```text
governed namespaces for stable reference frames
  + per-run reconciled concept spine artifact
  = authoritative closeout surface
```

Global governance should be small:

- unit IDs;
- currency IDs;
- calendar IDs;
- time-role taxonomy;
- geography scheme/version IDs;
- legal authority type taxonomy;
- relation taxonomy;
- stable norm citation schemes;
- stable method-family IDs.

Run-local reconciliation should decide:

- what a policy term means in this claim;
- which metric, legal concept, data column, method obligation, population,
  geography, time role, unit, and authority type apply;
- which bridge authority exists between schemes;
- which mismatches are limitation, transform, split-claim, or blocker.

Relation taxonomy:

| Relation | Closeout effect |
| --- | --- |
| `identity` | Direct closure if same governed concept/version and scope. |
| `equivalence` | Closure only with bridge evidence and scope tuple. |
| `broader` / `narrower` | Useful for discovery, not auto-closure. |
| `scope_shifted` | Limitation, split claim, transform, or blocker. |
| `authority_shifted` | Needs authority bridge, otherwise blocker. |
| `conflicting` | Blocker or claim split. |
| `deprecated` | Historical replay only unless replacement/migration is declared. |
| `unresolved` | Blocker. |
| `operationalizes` | Source column/feature supports metric or term; not identity. |
| `governs` | Norm governs requirement; not identity. |
| `satisfies_method_obligation` | Method closes obligation; not identity. |

Authority envelope for concept relations must carry namespace, scheme owner,
concept version, definition ref, relation type, provenance, jurisdiction,
temporal scope, population/geography scope, unit semantics, instrument type,
data source scope, method scope, authority profile, and supersession/replacement
refs.

Governed namespaces should start as repo-governed dictionaries, not a registry
service. Promotion to a service is justified only when multiple deployments or
tenants need runtime-shared namespace state, external parties need runtime
read/propose access, lifecycle events must propagate to live consumers, or audit
requires queryable history independent of git. This is a structural commitment;
service promotion is a later operational trigger, not a prerequisite.

### Legal Authority And Time Semantics

Generic jurisdiction membership is not serious legal authority. Legal authority
requires:

```text
source norm
  -> authority basis
  -> competent actor
  -> permitted instrument
  -> active legal window
  -> non-preempted position
  -> funding authority when spending is claimed
  -> review/appeal/contestability path where needed
```

Three C7 mini-decisions are now stable:

- hierarchy fallback is not a universal rule; it is a governed
  per-jurisdiction property in the legal-authority namespace;
- authority-type multiplicity is allowed, so one norm may be enabling,
  funding, delegating, or oversight authority at the same time;
- temporal competence changes split claims by competence window; a genuine
  competence gap blocks or limits only the affected segment.

Numeric/time/geography transformations are never authority-neutral. Any unit,
currency, calendar, geography, time-role, freshness, or aggregation transform
creates a derived artifact with lineage, lossiness, reversibility, validation,
and authority-before/after. Production authority requires registered transform
or ADR support, CAS-derived refs, same-input closure, and no silent substitution
between legal effective time, data observation time, policy time, model time,
detection time, publication time, replay time, freshness time, and retention
time.

### Obligation Control

C38 resolves the obligation-explosion problem. The model is:

| Layer | Cardinality | Closeout effect |
| --- | ---: | --- |
| Candidate ledger | Unlimited | Never blocks. |
| Bundle ledger | Bounded by family, scope, authority, remedy | Can be promoted. |
| Blocking frontier | Bounded by complexity budget | Blocks or caps. |

Source ceilings:

| Source | Default ceiling |
| --- | --- |
| Governed rule | `mandatory` or `authority_level_mandatory` |
| Legal requirement | `authority_level_mandatory` after competence/time/scope proof |
| Deterministic critic | `conditional` |
| Producer blocker | `mandatory` in affected scope |
| Historical failure | `review_required` |
| LLM candidate | `candidate` |
| Human reviewer | `review_required` unless authority-envelope-backed |
| Public contestation | `review_required` unless material and claim-linked |

Promotion is lexicographic:

1. authority allowance;
2. legal/privacy admissibility;
3. current-run evidence relevance;
4. material public risk;
5. VOI and marginal assurance value;
6. cost, degradation, and reviewer burden;
7. complexity budget.

Raw candidates must be canonicalized, deduplicated, lineage-collapsed, and
bundled before promotion. One active bundle per
`(family, scope, authority_profile, temporal_window, remedy_path)` is the
default. Deferred/rejected obligations remain visible with reason, owner, time,
and reopen trigger.

### Evidence Acquisition Decision Boundaries

C22 is closeable as a decision-boundary ADR, not another research pass.
Strategy taxonomy and VOI are already sufficient; the missing rule is that
ranking is not the same as authorization.

Acquisition policy:

- eligibility precedes ranking: `gap_type` maps to eligible strategies, and VOI
  ranks only inside that eligible set;
- mandatory gates dominate VOI: a non-overridable blocker forces block or
  required remediation regardless of attractive `net_voi`;
- `accepted_deficit`, `publish_with_limitation`, and `closeout_block` are
  terminally different and ordered;
- `publish_with_limitation` never bypasses a mandatory gate;
- governed/production strategy selection may be recommended automatically, but
  commit, especially proxy-with-degraded-authority, requires human or governed
  decision authority.

The closeout artifact should be a compact table:

```text
gap_type
  x authority_level
  x mandatory_gate_state
  -> eligible_strategies
  -> decision_owner
```

This unblocks E17 while keeping thresholds and cost values as tuned parameters.

### Producer Coordination And Bridge Authority

C40 defines producer liveness as a bounded state machine, not free-form waiting.
Producer states:

- `requested`
- `preflighted`
- `waiting_on_spine`
- `waiting_on_peer`
- `emitted_context_only`
- `emitted_binding`
- `blocked`
- `timed_out`
- `degraded`
- `rerun_required`
- `abandoned`

Three liveness invariants matter most:

1. No producer may wait for an unnamed peer condition. `waiting_on_peer` must
   name producer, artifact family, required fields, and deadline.
2. `waiting_on_spine` is only for shared run-level inputs: scenario contract,
   concept/jurisdiction spine, authority profile, semantic signature.
3. A producer that can emit useful bootstrap context must do so before waiting,
   but `emitted_context_only` is never closeout authority.

Recommended staged execution:

1. run contract and carrier;
2. bootstrap concept/jurisdiction/time spine;
3. parallel preflight of data, legal, method, scholar, and source families;
4. first-pass context/blocker emission;
5. provisional claim registry;
6. second-pass authoritative binding;
7. semantic closure;
8. closeout and projection.

C37 resolves bridge authority. Bridge records are authoritative only about the
boundary they own.

| Bridge class | Can prove | Cannot prove | Default closeout status |
| --- | --- | --- | --- |
| Transport carrier | Context/ids were passed. | Producer understood or used them correctly. | Diagnostic only. |
| Handoff ledger | Boundary continuity and missing handoffs. | Domain adequacy. | Conditional closeout evidence for boundary. |
| Binding assertion | Producer declared selected/rejected/blocked. | Reader accepted it. | Conditional. |
| Producer attestation | Producer consumed/emitted/preserved identity. | Reader acceptance. | Yes with envelope/CAS/same-input. |
| Reader attestation | Reader verified/blocked under contract. | Producer truth by itself. | Yes for reader/closeout. |
| Diagnostic projection | Displayed state. | Any authority. | Never. |
| Closeout evidence | Closeout verdict under versions. | Domain truth without producer evidence. | Yes for closure only. |

Bridge record can become closeout input only if runtime-owned, CAS-addressed,
authority-enveloped, same-input-closed, reader-compatible, redaction/integrity
clean, and scoped to a boundary purpose.

No new bridge-specific top-level authority role is needed. The preferred
commitment is a generic `closeout_input` role plus boundary scope:
`authoritative_boundary`, `may_not_use_for`, CAS refs, same-input closure, and
reader compatibility. Bridge records can prove boundary facts, not producer
domain truth.

### Claim-Bound Evidence And Method Authority

C9 confirmed that claim taxonomy does not need to be invented from scratch.
PolicyOS already has claim support predicates and proof-carrying IR analytics.
The missing bridge is:

```text
IR / Foundry / Scholar / Fabric / Lex artifact
  -> claim-bound registry entry
  -> method / uncertainty / limitation / blocker refs
```

Method outputs must be explicit. Generic `foundry.execute` or generic
simulation narrative is not serious method authority. Claim families must bind
to method outputs, assumptions, uncertainty, sensitivity, limitations, and
negative/partial identification where applicable.

For superiority claims, selected option evidence is not enough. The claim must
bind to baseline and alternative comparison:

- status quo;
- business-as-usual;
- no-action baseline;
- named alternatives;
- fragility/scenario baselines where operationally meaningful.

Rejected alternatives need records, not disappearance.

### Effective Independence

C29 keeps existing strict cluster collapse and adds graded calculus.

Evidence-line identity should include claim ids, strand, polarity, source refs,
primary source, retrieval path, legal authority, author/institution/sponsor,
dataset/corpus/snapshot/subject pool, preprocessing, transformation lineage,
method family, identification strategy, assumptions, proof-reuse status, LLM
generation path, simulation DGP, participation sample frame, concept spine,
jurisdiction, and time roles.

Pairwise model:

```text
if hard_collapse(a, b):
    I(a, b) = 0.0
else:
    D(a, b) = min(0.95, sum(weight_c * overlap_c(a, b)))
    I(a, b) = 1.0 - D(a, b)
```

Hard collapse:

- same primary source / subject pool / consultation event;
- same Data Forge snapshot, preprocessing cluster, and identification strategy;
- same controlling legal instrument for same proposition/scope/time;
- same DGP, calibration source, and assumption family;
- same LLM model snapshot, prompt chain, and retrieval bundle;
- same study reported as preprint, article, brief, and press release.

Partial collapse bands:

| Condition | Suggested `I(a,b)` |
| --- | ---: |
| Same dataset, different method family | 0.20-0.45 |
| Different data, same method family/identification | 0.35-0.60 |
| Same author/institution, different data | 0.55-0.80 |
| Same sponsor only | 0.70-0.90 |
| Shared legal hierarchy, different instruments/propositions | 0.60-0.85 |
| Same DGP family, different calibration/sensitivity | 0.25-0.50 |
| Different participation channels, same sample frame | 0.30-0.55 |
| Shared high-level concept spine only | 0.90-1.00 |

Aggregation:

```text
quality(a) in {1.00 admissible, 0.75 proxy_with_limitation, 0.50 context_only}
novelty(a | S) = 1 if S empty else max(0, min(I(a,b) for b in S))
effective_mass(S) = sum(quality(a) * novelty(a | accepted_before))
```

Counterevidence is not collapsed away into support; it has separate polarity
and must remain visible.

Rare domains need an explicit scarcity path, not evidence inflation. PolicyOS
should distinguish `scarcity_structural` from `scarcity_remediable`.
Structural scarcity can lead to lower-authority closeout, production closeout
only with a reviewed and public single-line deficit, or a more reversible and
monitorable policy design. It never turns one line into many independent lines,
and it strengthens rather than weakens the LLM candidate-to-authority firewall.

### Conflict, Contestability, And Argument

Conflict is a first-class record, not an exception. Conflict types include:

- empirical;
- methodological;
- legal;
- scope;
- normative;
- participation;
- implementation;
- authority/provenance.

Resolution routes differ:

- empirical conflict may need more evidence;
- methodological conflict needs method validity, not majority vote;
- legal conflict uses hierarchy, speciality, competence, and time;
- scope conflict often splits claims;
- normative/participation conflict may remain contested with residual dissent.

Argument/warrant semantics build on existing SACM/CAE/GSN mapping. Warrant is
an inference license with assumptions, applicability limits, BERL/reliability
refs, and conditions under which evidence supports the claim. Major claims need
argument, warrant, rebuttal/counterevidence, limitations, and accepted deficits
where applicable.

For public recourse, the committed boundary is: PolicyOS owns the
contestability record, not the external recourse process. A high-stakes
production contested PDC must expose what is contested, positions, evidence per
side, decision authority, limitations, reopening triggers, named owner, and a
typed `recourse_pointer`. Appeal intake, adjudication, SLA, and outcome
authority remain deployment/institution owned. PolicyOS ingests recourse
outcomes as lifecycle or revalidation events.

### Participation Legitimacy

C34 separates participation evidence by permitted claim use:

- preference;
- lived experience;
- acceptability;
- legitimacy;
- procedural fairness;
- implementation feasibility;
- objection/dissent;
- context only.

Participation source kinds include survey, consultation, deliberative panel,
hearing, administrative complaint, civil-society submission, expert interview,
affected-person testimony, and LLM/analyst speculation.

Minimum provenance:

- who was asked;
- how and when;
- sampling frame and representativeness;
- consent/redaction;
- facilitation/sponsor;
- dissent and unresolved objections;
- geography/population scope;
- limitations;
- permitted claim use.

LLM or analyst speculation cannot support affected-person preference or
legitimacy. Real participation evidence may still be only context evidence if
its provenance does not support stronger claims.

The missing participation decision is no longer open-ended research. Commit the
matrix structure:

```text
claim_use
  x authority_level
  x population_scope
  -> min_representativeness_class
  -> min_provenance_fields
```

Imperfect or uncertain representativeness should usually downgrade the claim
use, not delete the policy or launder prevalence. For example, a thin but
credible testimony may support existence or lived-experience claims, while
preference prevalence, subgroup acceptability, and legitimacy-at-population
scale require representative or quota/stratified process. "High stakes" should
reuse authority level and public population-preference scope instead of adding a
new status axis. Exact numeric thresholds are tuned parameters under named
methodological and governance owners.

### Tradeoffs And Welfare

Scalar welfare may be displayed but cannot hide value choice. The public and
reviewer surfaces must separate:

1. frontier facts;
2. evaluative transforms, including social-weight provenance;
3. governance decision selecting a point;
4. rejected nondominated options;
5. residual dissent.

No forced aggregation should turn political or normative disagreement into a
fake technical optimum.

### External Legitimacy Surface

C39 must be split for execution:

- **C39a projection structure:** typed public, reviewer, expert, machine,
  dashboard, and audit surfaces. This is ready for engineering with C16.
- **C39b recourse mechanics:** contestability/appeal boundary. This is a
  decision backlog item, now closed by the "record, not tribunal" boundary
  unless a deployment chooses to add its own recourse process.

External surface is not cosmetic. It is a legitimacy layer.

Audience entitlement:

| Audience | Minimum visibility |
| --- | --- |
| Public | claim-level summary, why-not for blocked/limited claims, legal/data/method basis summary, uncertainty, tradeoffs, participation quality, dissent, redactions, public audit ref |
| Dashboard | operational truth, first blocker, owner, phase, authority refs, projection labels, no `None` that hides failure |
| Reviewer | reconstructable claim graph, evidence/counterevidence, warrants, deficits, omissions, replay, redactions |
| Expert | assumptions, method alternatives, uncertainty internals, frontier, social weights, participation admissibility, residual dissent |
| Audit consumer | verifier-first package, refs, digests, provenance, boundary, public/private split |
| Machine consumer | stable enums, schema versions, immutable refs, omission manifests, redaction reasons, field-to-source mapping |

Redaction test: the case must remain contestable after redaction. Privacy and
security can hide raw transcripts, identifiers, prompts, private eval internals,
or sensitive quotes, but must not hide blockers, dissent, limitations, or
authority gaps.

For high-stakes contested production cases, `recourse_pointer` is mandatory and
must be verified reachable. A free-text URL or generic office name is not enough
for publication closeout.

### Rule Evolution And Public Revalidation

C33 extends C21: schema/ABI compatibility is not semantic equivalence.

Two axes must be tracked:

- schema readability and lossless migration;
- rule/taxonomy semantics for admissibility, scope, authority, readiness, and
  publication.

Closed PDC meaning is historically immutable, but it may stop being current
guidance.

Change classes and public effects:

| Change | Default semantic meaning | Public effect |
| --- | --- | --- |
| Editorial | Non-semantic | No notice |
| Lossless schema migration | ABI-only | Internal migration; annotation only if public artifact changes |
| Threshold change | Semantic until frozen-corpus replay proves no delta | Annotation or stricter/weaker path by delta |
| Stricter admissibility | Semantic tightening | Public annotation and mandatory revalidation for active governed/production reliance |
| Weaker admissibility | Semantic loosening | No silent upgrade; reissue required for uplift |
| New blocker | Semantic tightening | Reissue or withdrawal review |
| Retired blocker | Semantic loosening | Optional reissue; no silent upgrade |
| Taxonomy split/merge | Depends on mapping class | Boundary/authority change triggers reissue or mandatory revalidation |
| Authority-profile change | Semantic if blocking/downgrade power changes | Profile drift annotation and revalidation where relied upon |

Every closed PDC needs immutable semantic tuple plus execution tuple: rule refs,
taxonomy refs, concept spine refs, authority profile, code/git refs, schema
versions, reader gates, source refs, replay mode, and public revision state.

Requirement-id remapping is compatible only when it is alias-only or proven
semantic preservation: the requirement logic hash does not change, scope and
authority effects do not change, and any closed PDC that satisfied the old id
satisfies the new semantics. If the logic hash changes, the change is a new
requirement, not a remap. Splits, merges, authority changes, or stricter
admissibility create revalidation or blockers. A safe public remap may still
require annotation rather than silent rewriting.

### Calibration And Historical Priors

C35 and C41 align. Historical priors are process signals, not claim evidence.

Allowed effects:

- VOI/search ranking;
- evidence budget;
- uncertainty widening;
- review escalation;
- provider/model selection;
- default enablement;
- benchmark priority;
- authority cap for future runs in the affected bucket.

Forbidden effects:

- satisfy data/norm/method/participation evidence;
- refute current admissible evidence by themselves;
- mint authority;
- hide current deficits.

Calibration blocking policy is bucketed by:

```text
claim family
  x domain
  x jurisdiction
  x method family
  x provider
  x authority level
```

Metrics that may cap/block high-authority future runs after mature history:

- severe interval under-coverage;
- false-pass rate;
- reversal rate;
- retraction rate;
- material group/domain calibration gap;
- persistent decision-direction bias tied to harm.

Metrics that mainly adjust review/budget/provider routing:

- Brier/reliability/log score;
- uncertainty diagnostics;
- generic forecast bias without observed harmful consequence.

Control-quality metrics such as low blocker precision or high false-block rate
should reduce automation and force human adjudication, not strengthen blocking.

Sparse-history policy:

| History state | Minimum data | Allowed effect |
| --- | --- | --- |
| Insufficient | <30 resolved cases or <10 error opportunities | Warning, uncertainty widening, extra evidence; no history-only block. |
| Thin | 30-99 resolved and 10-19 error opportunities | Reviewer note, extra independent check, narrower publication. |
| Forming | 100-199 resolved and >=20 opportunities in multiple windows | Mandatory review, readiness cap, provider/method downgrade. |
| Mature adverse | >=200 resolved and >=50 opportunities or equivalent long history, breach persists | Scoped high-authority block and remediation. |

### Complexity Budget

C32 defines complexity as a self-FMEA concern. The key formula:

```text
Net-MAV(item) =
  decision_gain
  + falsification_value
  + authority_gain
  + auditability_gain
  - human_time_cost
  - latency_penalty
  - rerun_penalty
  - false_block_penalty
```

Minimum floor cannot be simplified away:

- authority binding for decisive artifacts;
- decisive claim support;
- source truth and semantic binding;
- conflict/counterevidence handling;
- accepted deficits and public limitations;
- unified closeout object.

PDC complexity classifications:

| Class | Meaning | Default action |
| --- | --- | --- |
| Proportionate | Floor satisfied, no red ceremony, budget in range, items have positive value or legal/safety necessity. | Requested authority closeout allowed. |
| Too heavy | Floor satisfied, controls decision-coupled, but cost/burden high. | Modularize, defer to lifecycle, reduce reviewer fan-out. |
| Ceremonial | Red ceremony, zero-delta reviews, orphan warnings, perpetual waivers, bloat without decision value. | Retire/merge/redesign, cap or block closeout. |
| Under-assured | Budget light but missing decisive evidence/authority/semantic floor. | Add assurance even if complexity rises. |

Ceremony signals include repeated empty records, warnings without owner, controls
that never affect decisions, reviews with no deltas, gates always waived,
high false-block rate, and waiting dominating cycle time.

Ceremony measurement must not become another ceremony. It should be derived from
telemetry already emitted by runtime events, status envelopes, claim diffs,
deficit ledgers, lifecycle records, and producer-liveness state durations.
Complexity budget is advisory by default for individual runs. It gates growth
of new controls by requiring expected Net-MAV and telemetry, then informs
periodic governance pruning. If the complexity budget itself never causes a
retire/merge/keep decision, it should be eligible for retirement.

### Closeout Substrate

Closeout is one decision surface:

```text
can_i_closeout(run_id) =
  formal_invariants
  + event reconciliation
  + attestation
  + source truth
  + metamorphic controls
  + performance/cost/degradation budgets
  + schema/git/reader compatibility
  + semantic binding
  + claim registry closure
  + PDC record-family status
  + projection/publication state
  + complexity/self-FMEA status
```

Audit verifier augments publication trust; it does not create runtime authority
by itself. Dashboard/public/API projections may display closeout; they do not
mint closeout.

The closeout record should be materialized by a separate closeout substrate
reader, not by readiness. Readiness is one conjunct of closeout; it should not
become owner of invariants, source truth, attestation, compatibility, semantic
closure, publication state, and record-family status. The closeout reader emits
one immutable runtime record whose authority is only
`authoritative_for=[closeout_verdict]`.

Liveness should extend current finite-state safety checks through bounded
deadlines: `eventually X` becomes `X within deadline D, else escalate`. The
verification target is deadline consistency, retry/lease state, and escalation,
not full unbounded temporal model checking.

### Semantic Benchmark Rubric

C30 defines semantic benchmark as human-led claim-level adjudication above
structural validation.

Labels:

- `semantic_pass`
- `limitation_required`
- `contested`
- `unsupported`
- `false_pass`
- `fabricated_unverifiable`
- `reviewer_disagreement`

Every rejected structural pass needs a gold card:

```text
claim_id
dimension_id
evidence_ref
context_ref
failure_mode
why_structural_checks_missed_it
status_should_have_been
required_surface_change
```

Required probes:

- faithful snippet but unsupported claim;
- authentic but legally incompetent source;
- stale but structurally valid evidence;
- audit-valid but untrustworthy case reconstruction;
- projection/public export laundering;
- participation attribution laundering;
- independence inflation;
- method mismatch;
- ceremony without semantic substance.

Structural pass is necessary but not sufficient. Any materially load-bearing
claim labeled `unsupported`, `false_pass`, or `fabricated_unverifiable` blocks
case-level semantic pass.

## What Is Ready For Engineering

Engineering can now be planned for these stable or ADR-ready areas:

- capability ratchet and debt reporting;
- status envelope and soft-gate crosswalk;
- accepted-deficit matrix;
- governed obligation candidate/bundle/frontier ledger;
- hybrid concept-spine implementation plan;
- producer handshake and liveness envelope;
- bridge authority validator;
- IR/Foundry/Scholar/Fabric/Lex to ClaimRecord bridge;
- strict and graded effective independence map;
- typed PDC projection and external legitimacy surfaces;
- closeout substrate integration;
- rule lineage and public revalidation records;
- calibration and historical-prior influence records;
- semantic false-pass benchmark pack;
- complexity and ceremony self-FMEA;
- evidence acquisition decision-boundary ADR and E17 planner;
- legal competence Lex ADR with jurisdiction-config fallback, multiple
  authority types, and competence-window splitting;
- C39a typed projection surface, separated from C39b recourse boundary;
- bounded-liveness invariants and advisory review-effectiveness telemetry.

## What Must Remain Research-Guarded

Do not harden these without separate ADR or fixture-backed decision:

- exact thresholds for effective-independence weights beyond initial defaults;
- final authority-level portfolio minima by all claim families;
- final participation legitimacy numeric thresholds for high-stakes public
  claims; the matrix structure and downgrade posture are decided;
- final calibration blocking thresholds after enough longitudinal data exists;
- institution-owned appeal intake, adjudication, SLA, and outcome authority;
  PolicyOS-owned contestability record and `recourse_pointer` are decided;
- exact complexity budgets after observed reviewer/cost telemetry;
- promotion from repo-governed concept dictionaries to a standalone registry
  service; default and promotion triggers are decided;
- numeric thresholds for rare-domain weak-evidence paths; the scarcity
  structure is decided;
- which social-weight provenance classes are sufficient for public legitimacy;
- how much automation is allowed in semantic benchmark adjudication.

## Implementation-Planning Implications

The next plan should not be another theoretical research pass. It should be a
bridge-first engineering plan with explicit capability-debt and authority
firewall gates.

Recommended first implementation slices:

1. Capability reality ratchet and C36 debt reporting.
2. Status envelope, deficit matrix, and soft-gate lifecycle.
3. Hybrid concept spine carrier plus producer handshake/liveness records.
4. Producer to ClaimRecord bridges for Lex, Fabric, Scholar, Foundry, Data
   Forge, and IR analytics.
5. Effective independence strict cluster collapse plus graded pairwise scoring
   behind a feature flag.
6. Typed `PolicyDesignCaseProjection` with public/reviewer/expert/machine
   entitlement matrix.
7. Unified `can_i_closeout` surface over existing substrate fragments.
8. Rule-lineage and public revalidation records.
9. Historical-prior influence record and calibration sparse-history policy.
10. Semantic false-pass benchmark and gold-card schema.

Acceptance for the engineering plan should require each task to state:

- which C decision it implements;
- which capability reality state it closes;
- whether it is authority-bearing, projection-only, diagnostic, or bridge
  authority;
- which firewall could be violated;
- which semantic/e2e negative test proves it is not laundering authority;
- which public/reviewer/machine surface exposes the result or why it is
  explicitly out of scope.

Every ADR used by the engineering plan should include:

- **Structural commitment:** the schema, transition, owner, invariant, or
  authority boundary being committed now;
- **Tuned parameter:** thresholds, weights, minimum counts, budgets, deadlines,
  or reviewer/calibration cutoffs that start as governed defaults and remain
  revisable;
- **Negative laundering test:** the case where the new surface must not mint
  authority;
- **Owner and revision path:** who may update tuned parameters and when
  fixture/corpus evidence is required.

## Remaining Research Backlog

This backlog is now narrow:

- collect fixture cases for concept-spine population, aggregation, legal
  instrument, and boundary-version shifts;
- calibrate effective-independence weights using real portfolios;
- tune complexity budgets after measuring reviewer minutes, false-block rate,
  and artifact size across similar runs;
- tune calibration thresholds after enough resolved outcome opportunities;
- build semantic benchmark public/hidden/rotating governance with reviewer
  calibration;
- decide whether concept namespace promotion triggers have fired after testing
  repo-governed dictionaries;
- tune participation representativeness thresholds under named methodological
  and governance owners;
- specify deployment-owned appeal intake/adjudication/SLA only where a real
  institution asks PolicyOS to host or integrate that process.

## Final Synthesis

The research stream converges on one design sentence:

> PolicyOS should generate universal Policy Design Cases by compiling a
> claim-bound runtime evidence graph under explicit authority, concept,
> status, independence, lifecycle, and projection semantics, while allowing
> LLMs, historical memory, dashboards, and bridges to assist but never to mint
> substantive authority.

The system's best next move is not more broad research. It is careful
bridge-first engineering, protected by the conceptual constraints above.
