---
title: Policy Design Case Decision Log
status: active append-only log
owner: team-architecture
created: 2026-05-17
source_decision: policy-design-best-in-class-operating-model.md
source_plan: ../plans/archive/2026-05-19-policyos-policy-design-case-implementation-plan.md
---

# Policy Design Case Decision Log

This log captures implementation-time ownership assignments, reversible local
decisions, deferred open questions, and temporary exceptions for the Policy
Design Case workstream. ADR 0156-0165 remain the stable architecture layer.
Entries here must not narrow those ADRs unless a later ADR explicitly accepts
the supersession.

## Append-Only Rule

Entries are append-only. Do not rewrite prior entries to change history. When a
decision changes, append a new entry that references the older entry and marks
the older decision as superseded in the new context.

Use this log for bounded, reversible implementation choices. Promote a decision
to ADR when it changes cross-component contract semantics, case authority,
producer duties, profile mapping, portfolio semantics, claim acceptance, public
evidence semantics, or compatibility guarantees.

Quarterly, review accumulated entries and either promote, retire, or mark them
as superseded through a later entry.

## Append-Only Entry Template

Copy this template for new entries under `## Entries`.

```markdown
### DL-PDC-0000 - short decision title

- **Date**: YYYY-MM-DD
- **Context**: Why this decision is needed and what source question, phase, or incident raised it.
- **Decision**: The decision made, or the open question retained with the current constraint.
- **Affected ADR or SDD section**: ADR-0156, ADR-0157, ADR-0158, ADR-0159, ADR-0160, ADR-0161, ADR-0162, ADR-0163, ADR-0164, ADR-0165, SDD section, or a subset.
- **Affected wave and phase**: Wave N, Phase N.N, exit fence, or plan section.
- **Owner**: team or role accountable for revisiting the entry.
- **Reversibility**: reversible, costly_to_reverse, or irreversible.
- **Revisit trigger**: Concrete event that forces review.
- **Revisit wave**: after Wave N, quarterly review, or immediate if violated.
- **Promotion status**: log_only_pending_revisit, needs_adr, promoted_to_ADR-XXXX, retired, or superseded_by_DL-PDC-XXXX.
```

## Owner Role Legend

| Owner role | Primary accountability |
|------------|------------------------|
| `team-runtime-quality` | Runtime quality assurance case, authority records, schemas, scorecard-readable case records, and substrate compatibility. |
| `team-runtime-control` | Intent, routing, capability duties, skipped-duty blockers, profile mapping, and effective-mode closure. |
| `team-policy-semantics` | Concept spine, jurisdiction spine, semantic closure, legal/data/method/objective/claim reconciliation, and conflict representation. |
| `team-domain-producers` | Lex, Fabric, Scholar, and Data Forge producer-owned evidence records and runtime bindings. |
| `team-science-quality` | Foundry, Scientist, IR analytics, evidence portfolio, independence, multiverse, synthesis, calibration, and benchmarking semantics. |
| `team-claim-compiler` | Final claim compiler, argument, warrant, rebuttal, counter-evidence, assurance deficits, and BERL warrant reliability bridge. |
| `team-quality-closeout` | Readiness, scorecard, final closeout, approval/projection boundaries, governance hardening, and anti-drift gates. |
| `team-core-audit` | PROV/SLSA archive, external audit, standalone verification, safe archive, and publication-trust evidence packaging. |
| `team-ddm` | Drift, degradation, readiness, incident, and root-cause monitoring evidence used after publication. |
| `team-architecture-governance` | ADR promotion, decision-log review, accepted exceptions, ownership conflicts, and cross-workstream supersession. |
| `coverage-integrator` | Policy Design Case coverage, drift, rebaseline comparison, and generated dashboard tooling. |
| `docs-adr-integrator` | ADR index, SDD decision log, plan references, docs lifecycle checks, and final documentation handoff. |

## Target Contract Ownership Skeleton

These owners are the Phase 1.4 skeleton owners for the target contracts named in
the implementation plan. They do not move behavioral ownership into
`runtime/quality`; producer modules still own producer behavior and source
evidence, while `runtime/quality` owns runtime-readable authority records and
closeout-facing projections.

| Target contract | Proposed path | Primary owner | Reuse or behavioral owner | First revisit wave |
|-----------------|---------------|---------------|----------------------------|--------------------|
| Policy Design Case runtime profile | `src/polisyos/runtime/quality/assurance_case.py` | `team-runtime-quality` | `src/polisyos/runtime/quality` assurance-case substrate | after Wave 2 |
| Policy Design Case record families | `src/polisyos/runtime/quality/policy_design_case.py` | `team-runtime-quality` | runtime quality schema and authority records | after Wave 2 |
| Intent envelope | `src/polisyos/runtime/quality/policy_intent.py` | `team-runtime-control` | Scientist policy-design schemas and IR problem framing | after Wave 3 |
| Capability selection ledger | `src/polisyos/runtime/quality/capability_ledger.py` | `team-runtime-control` | Scientist orchestration, Foundry method selection, runtime quality ledgers | after Wave 3 |
| Authority profile mapping | `src/polisyos/runtime/quality/policy_authority_profile.py` | `team-runtime-control` | core governance profiles, control contracts, effective mode | after Wave 5 |
| Concept spine ledger | `src/polisyos/runtime/quality/concept_spine.py` | `team-policy-semantics` | Fabric entity resolution, Scientist cross-graph, IR linker/registry/world | after Wave 11 |
| Jurisdiction spine ledger | `src/polisyos/runtime/quality/jurisdiction_spine.py` | `team-policy-semantics` | Lex knowledge, IR normative arbitration, jurisdiction/legal analytics | after Wave 11 |
| Data Forge snapshot binding | `src/polisyos/runtime/quality/data_forge_binding.py` | `team-domain-producers` | Data Forge snapshots, manifests, quality gates, read API | after Wave 14 |
| Lex norm authority report | `src/polisyos/runtime/quality/legal_authority.py` | `team-domain-producers` | Lex knowledge, legal evaluation, normpack, provenance | after Wave 14 |
| Fabric source evidence report | `src/polisyos/runtime/quality/source_evidence.py` | `team-domain-producers` | Fabric connectors, contracts, quality, provenance, federation | after Wave 14 |
| Scholar evidence report | `src/polisyos/runtime/quality/scholar_evidence.py` | `team-domain-producers` | Scholar discover/search/freshness/orchestrator/provenance APIs | after Wave 14 |
| Method validity report | `src/polisyos/runtime/quality/method_validity.py` | `team-science-quality` | Foundry method catalog, selection, cost, uncertainty, IR analytics | after Wave 18 |
| Evidence portfolio design | `src/polisyos/runtime/quality/evidence_portfolio.py` | `team-science-quality` | Scientist DOE/discovery, Foundry sensitivity, IR ensemble/falsification | after Wave 20 |
| Evidence independence map | `src/polisyos/runtime/quality/evidence_independence.py` | `team-science-quality` | Foundry consensus/equivalence and source-lineage collapse projections | after Wave 20 |
| Specification curve report | `src/polisyos/runtime/quality/specification_curve.py` | `team-science-quality` | Scientist DOE/discovery, Foundry sensitivity, IR causal ensemble | after Wave 20 |
| Disconfirming evidence ledger | `src/polisyos/runtime/quality/disconfirming_evidence.py` | `team-science-quality` | IR falsification, Scientist discovery, backtesting severe tests | after Wave 20 |
| Evidence synthesis report | `src/polisyos/runtime/quality/evidence_synthesis.py` | `team-science-quality` | Scientist discovery aggregation, stability, utility judging, priors | after Wave 20 |
| Claim argument/warrant records | `src/polisyos/runtime/quality/claim_argument.py` | `team-claim-compiler` | claim compiler, Scientist claim ledgers, assurance-case nodes | after Wave 25 |
| BERL warrant reliability bridge | `src/polisyos/runtime/quality/explanation_reliability.py` | `team-claim-compiler` | `src/polisyos/berl` explanation bundles and reliability bounds | after Wave 23 |
| Structured judgement record | `src/polisyos/runtime/quality/structured_judgement.py` | `team-quality-closeout` | human review, value-of-information escalation, expert judgement protocol records | after Wave 27 |
| Consultation evidence record | `src/polisyos/runtime/quality/consultation.py` | `team-quality-closeout` | human review, stakeholder maps, response-to-comment governance | after Wave 27 |
| Implementation monitoring/evaluation record | `src/polisyos/runtime/quality/implementation_monitoring.py` | `team-ddm` | DDM, continuous governance, evaluation and monitoring plan records | after Wave 27 |
| Human oversight effectiveness record | `src/polisyos/runtime/quality/human_review.py` | `team-quality-closeout` | Scientist governance human-review packets, queues, decisions, VOI escalation | after Wave 27 |
| Producer independence record | `src/polisyos/runtime/quality/independence.py` | `team-quality-closeout` | producer duty ledger, review independence, separation-of-duty attestations | after Wave 27 |
| Integrity threat model and self-FMEA | `src/polisyos/runtime/quality/case_integrity.py` | `team-quality-closeout` | honest diagnostics controls, partial-state contradiction checks, threat model records | after Wave 29 |
| Case maturity profile | `src/polisyos/runtime/quality/case_maturity.py` | `team-quality-closeout` | coverage dashboard, self-FMEA, closeout readiness | after Wave 29 |
| DDM monitoring bridge | `src/polisyos/runtime/quality/ddm_monitoring.py` | `team-ddm` | `src/polisyos/ddm` shift, degradation, readiness, incident, root-cause events | after Wave 27 |
| Lifecycle/ex-post/calibration record | `src/polisyos/runtime/quality/case_lifecycle.py` | `team-science-quality` | continuous governance, calibration, backtesting, memory contamination checks | after Wave 35 |
| Publication trust and external audit record | `src/polisyos/runtime/quality/publication_trust.py` | `team-core-audit` | core audit PROV JSON, SLSA assembler, verifier, safe archive | after Wave 28 |
| Benchmarking and proportionality record | `src/polisyos/runtime/quality/policy_benchmarking.py` | `team-science-quality` | runtime budgets, Foundry cost model, Scientist budgets, human-team benchmark records | after Wave 31 |
| Formal invariant spec registry | `architecture/policy_design_case/formal_invariant_specs.toml` | `team-quality-closeout` | honest diagnostics proof harness and validation tools | after Wave 29 |
| Walking skeleton readiness smoke | `tools/quality/validation/check_policy_design_case_walking_skeleton.py` | `coverage-integrator` | readiness, runtime quality fixtures, policy design case sample output | after Wave 7 |
| Pass 2 disposition checker | `tools/quality/validation/check_policy_design_case_pass2_disposition.py` | `coverage-integrator` | Pass 2 diagnostic outputs and Wave 35 disposition artifacts | after Wave 35 |
| Policy Design Case coverage | `tools/quality/validation/build_policy_design_case_coverage.py` | `coverage-integrator` | coverage dashboard, record-family schema inventory, generated rebaseline output | after Wave 1 |
| Policy Design Case drift detector | `tools/quality/validation/check_policy_design_case_drift.py` | `coverage-integrator` | anti-drift rules, no-parallel-case checks, reuse map | after Wave 1 |
| Rebaseline comparator | `tools/quality/validation/compare_policy_design_case_rebaseline.py` | `coverage-integrator` | `_build/policy-design-case/rebaseline/wave-*` output contracts | after Wave 1 |
| Decision log | `docs/system-design-decisions/policy-design-case-decision-log.md` | `docs-adr-integrator` | SDD, ADR index, implementation plan, decision-log append-only review | quarterly review |

## ADR 0156-0161 Proof Obligation Ownership

These rows assign the current owner of each accepted ADR proof obligation. If a
later wave changes an owner or path, append a new entry instead of editing
these rows in place.

| Proof id | Obligation | Owner | Revisit wave |
|----------|------------|-------|--------------|
| ADR-0156-O1 | Introduce Policy Design Case schema facets in or over `src/polisyos/runtime/quality`. | `team-runtime-quality` | after Wave 2 |
| ADR-0156-O2 | Map assurance-case nodes for claim, argument, warrant, evidence, rebuttal, counter-evidence, and deficits. | `team-runtime-quality`, `team-claim-compiler` | after Wave 22 |
| ADR-0156-O3 | Document SACM/CAE/GSN mapping or exporter contract. | `team-runtime-quality`, `team-core-audit` | after Wave 22 |
| ADR-0156-O4 | Add scorecard/readiness checks that reject missing assurance-case structure. | `team-quality-closeout` | after Wave 25 |
| ADR-0156-O5 | Add tests that fail when a parallel serious-run case object bypasses `runtime/quality`. | `team-runtime-quality`, `coverage-integrator` | after Wave 2 |
| ADR-0157-O1 | Materialize policy intent envelope schema and runtime records before routing. | `team-runtime-control` | after Wave 3 |
| ADR-0157-O2 | Add requester-capture fields and challenge-depth policy. | `team-runtime-control`, `team-claim-compiler` | after Wave 23 |
| ADR-0157-O3 | Materialize capability selection ledger schema. | `team-runtime-control` | after Wave 3 |
| ADR-0157-O4 | Add Scholar duty entries in routing and scorecard surfaces. | `team-runtime-control`, `team-domain-producers` | after Wave 14 |
| ADR-0157-O5 | Map policy authority levels to execution profiles, core governance profiles, and runtime effective mode. | `team-runtime-control` | after Wave 5 |
| ADR-0157-O6 | Add scorecard/readiness checks for missing intent, missing duty, disallowed skip, fallback leakage, and profile mismatch. | `team-quality-closeout` | after Wave 5 |
| ADR-0157-O7 | Add tests for cross-run, stale, and contradictory intent/capability evidence. | `team-runtime-control` | after Wave 5 |
| ADR-0158-O1 | Add per-run concept spine schema. | `team-policy-semantics` | after Wave 8 |
| ADR-0158-O2 | Add jurisdiction spine and conflict-record schema. | `team-policy-semantics` | after Wave 9 |
| ADR-0158-O3 | Add projection adapters over Fabric entity resolution, Scientist cross-graph, IR linker/registry/world, and normative arbitration. | `team-policy-semantics` | after Wave 10 |
| ADR-0158-O4 | Add full producer evidence APIs beyond the Wave 10 spine-ref reader/emitter contract. | `team-policy-semantics`, `team-domain-producers`, `team-science-quality` | after Wave 14 |
| ADR-0158-O5 | Add scorecard/readiness checks for concept mismatch, jurisdiction mismatch, unit/time/geography mismatch, and local-concept leakage. | `team-quality-closeout` | after Wave 11 |
| ADR-0158-O6 | Add tests for multi-jurisdiction conflict, stale spine refs, and claim evidence bound to incompatible concepts. | `team-policy-semantics` | after Wave 11 |
| ADR-0159-O1 | Add Lex legal retrieval and norm-binding evidence schemas. | `team-domain-producers` | after Wave 14 |
| ADR-0159-O2 | Add Fabric source-family, field-binding, quality, rights, and lineage schemas. | `team-domain-producers` | after Wave 14 |
| ADR-0159-O3 | Add Scholar retrieval, scoring, freshness, citation, and support/conflict evidence schemas. | `team-domain-producers` | after Wave 14 |
| ADR-0159-O4 | Add Data Forge snapshot/read-API binding records. | `team-domain-producers` | after Wave 14 |
| ADR-0159-O5 | Add scorecard/readiness checks for producer duty, snapshot identity, source rights, freshness, quality, semantic binding, and selected/rejected candidate evidence. | `team-quality-closeout` | after Wave 14 |
| ADR-0159-O6 | Add negative tests for static inventory substitution, manifest-role false pass, legal-shaped payload without retrieval, narrative citation without Scholar provenance, and local corpus path leakage. | `team-domain-producers`, `team-quality-closeout` | after Wave 14 |
| ADR-0160-O1 | Add evidence portfolio design schema. | `team-science-quality` | after Wave 15 |
| ADR-0160-O2 | Add evidence strand and evidence line schemas. | `team-science-quality` | after Wave 16 |
| ADR-0160-O3 | Add independence map and effective independent count records. | `team-science-quality` | after Wave 17 |
| ADR-0160-O4 | Add method-equivalence and source-lineage collapse projections. | `team-science-quality` | after Wave 17 |
| ADR-0160-O5 | Add multiverse/specification-curve records. | `team-science-quality` | after Wave 18 |
| ADR-0160-O6 | Add disconfirming evidence ledger. | `team-science-quality` | after Wave 18 |
| ADR-0160-O7 | Add convergence/divergence cluster report. | `team-science-quality` | after Wave 19 |
| ADR-0160-O8 | Add evidence synthesis report and certainty rating. | `team-science-quality` | after Wave 19 |
| ADR-0160-O9 | Add stopping-rule and information-saturation report. | `team-science-quality` | after Wave 19 |
| ADR-0160-O10 | Add run-cost proportionality linkage. | `team-science-quality`, `team-quality-closeout` | after Wave 30 |
| ADR-0160-O11 | Add scorecard/readiness checks for missing portfolio, post-hoc cherry-picking, missing independence map, missing severe test, missing synthesis sensitivity, and unsupported single-line major claims. | `team-quality-closeout` | after Wave 20 |
| ADR-0161-O1 | Add claim argument and warrant schema. | `team-claim-compiler` | after Wave 22 |
| ADR-0161-O2 | Add claim-to-portfolio, claim-to-synthesis, claim-to-norm, claim-to-source, claim-to-method, claim-to-objective, and claim-to-uncertainty refs. | `team-claim-compiler` | after Wave 21 |
| ADR-0161-O3 | Add rebuttal, counter-evidence, assurance-deficit, and blocker records. | `team-claim-compiler` | after Wave 22 |
| ADR-0161-O4 | Add BERL explanation reliability refs for applicable warrants. | `team-claim-compiler` | after Wave 23 |
| ADR-0161-O5 | Add claim compiler checks that reject missing producer evidence and prose backfill. | `team-claim-compiler` | after Wave 21 |
| ADR-0161-O6 | Add scorecard/readiness checks for unsupported claim, evidence-without-argument, missing BERL reliability evidence, hidden counter-evidence, and silent promotion of research deficits. | `team-quality-closeout` | after Wave 25 |

## ADR 0162-0165 Proof Obligation Ownership

These rows assign the current owner of each second-pack governance ADR proof
obligation accepted in Wave 26. If a later wave changes an owner or path,
append a new entry instead of editing these rows in place.

| Proof id | Obligation | Owner | Revisit wave |
|----------|------------|-------|--------------|
| ADR-0162-O1 | Add effective human oversight records with reviewer independence, dissent, challenge outcome, override, rubber-stamp risk, automation-bias controls, and accepted deficits. | `team-quality-closeout` | after Wave 27 |
| ADR-0162-O2 | Add producer/reviewer independence and requester-capture closeout records. | `team-quality-closeout` | after Wave 27 |
| ADR-0162-O3 | Add publication trust, public export, local/client evidence boundary, recall/contestability, and external audit archive refs using core audit verifier surfaces. | `team-core-audit`, `team-quality-closeout` | after Wave 28 |
| ADR-0162-O4 | Add readiness/projection checks that reject projection-only publication, missing redaction proof, missing standalone verification, and missing publication authority. | `team-quality-closeout`, `team-core-audit` | after Wave 28 |
| ADR-0163-O1 | Add append-only case lifecycle event schema and transition checks. | `team-ddm`, `team-runtime-quality` | after Wave 27 |
| ADR-0163-O2 | Add implementation, monitoring, evaluation, DDM shift/degradation/readiness/incident/root-cause, and ex-post reassessment records. | `team-ddm`, `team-science-quality` | after Wave 27 |
| ADR-0163-O3 | Add calibration ledger, calibration governance, and learning-record contamination controls. | `team-science-quality`, `team-ddm` | after Wave 35 |
| ADR-0163-O4 | Add readiness checks for stale lifecycle state, missing monitoring plans, historical rewrite attempts, missing reassessment, weak calibration blockers, and contaminated learning records. | `team-quality-closeout`, `team-ddm` | after Wave 35 |
| ADR-0164-O1 | Add run cost, evidence budget, proportionality, provider/compute/storage/audit/reviewer/consultation burden, and budget-change records. | `team-science-quality` | after Wave 30 |
| ADR-0164-O2 | Add best-in-class benchmarking records and baseline selection rules for expert human-team or historical comparison. | `team-science-quality` | after Wave 31 |
| ADR-0164-O3 | Add readiness checks for missing budget, over-budget without change authority, under-budget without stopping-rule proof, disproportional evidence depth, and prohibited cost-based waivers. | `team-quality-closeout`, `team-science-quality` | after Wave 31 |
| ADR-0165-O1 | Add `architecture/policy_design_case/formal_invariant_specs.toml` with owner, ADR source, protected authority property, check type, evidence artifact, and supersession metadata. | `team-quality-closeout` | after Wave 29 |
| ADR-0165-O2 | Add formal invariant validation tooling and repo-quality tests for authority ordering, phase barriers, CAS/event reconciliation, terminal readiness, projection boundaries, lifecycle monotonicity, publication authority, and proportionality waiver boundaries. | `team-quality-closeout`, `coverage-integrator` | after Wave 29 |
| ADR-0165-O3 | Add scorecard/readiness or docs lifecycle checks that report missing required formal invariant evidence before governed or production closeout. | `team-quality-closeout`, `docs-adr-integrator` | after Wave 29 |

## Imported Source Open Questions

Imported from
`docs/system-design-decisions/policy-design-best-in-class-operating-model.md`
on 2026-05-17. The revisit wave is the first wave that should have enough
implementation evidence to resolve, supersede, or re-scope the question.

| Source question | Owner | Revisit wave |
|-----------------|-------|--------------|
| 1. Should the policy concept spine be one physical registry or a reconciled view over multiple registries with one per-run authority artifact? | `team-policy-semantics` | after Wave 11 |
| 2. How much option comparison should be generated by default for research runs versus required only for governed/production runs? | `team-science-quality` | after Wave 30 |
| 3. Which distributional-effect categories should be mandatory by policy domain, and which should be scenario-configured? | `team-science-quality` | after Wave 30 |
| 4. What is the minimum acceptable institutional competence model before recommendations can be public-facing? | `team-domain-producers`, `team-quality-closeout` | after Wave 14 |
| 5. Should authoring provenance include raw prompts in encrypted/private CAS, or only salted hashes plus sanitized summaries? | `team-runtime-control`, `team-quality-closeout` | after Wave 28 |
| 6. Which external dependency rights should be non-overridable blockers versus reviewable warnings in research profiles? | `team-core-audit`, `team-quality-closeout` | after Wave 28 |
| 7. What public contestability contract belongs in the core case before Pass 2 legitimacy diagnostics run? | `team-quality-closeout` | after Wave 28 |
| 8. What minimum ex-post observation window is required before a policy claim can be marked confirmed, refuted, superseded, or inconclusive? | `team-science-quality`, `team-ddm` | after Wave 35 |
| 9. Which calibration metrics should block future high-authority runs when a domain or method family has a weak historical track record? | `team-science-quality` | after Wave 35 |
| 10. Which structured expert judgement protocols are acceptable for governed runs, and who can qualify as an expert? | `team-quality-closeout` | after Wave 27 |
| 11. How should multi-jurisdiction norm conflicts be represented when legal authority is genuinely unresolved rather than merely missing? | `team-policy-semantics`, `team-domain-producers` | after Wave 11 |
| 12. Which best-in-class benchmark tasks should compare PolicyOS with expert human policy teams? | `team-science-quality` | after Wave 31 |
| 13. Should PolicyOS use SACM as its canonical interchange format and CAE/GSN as profiles, or keep an internal schema with required exporters? | `team-runtime-quality`, `team-core-audit` | after Wave 22 |
| 14. Which assurance-deficit classes may be accepted in research, governed, and production modes? | `team-claim-compiler`, `team-quality-closeout` | after Wave 25 |
| 15. What minimum human-review telemetry proves effective oversight without turning review into surveillance theater? | `team-quality-closeout` | after Wave 27 |
| 16. Which requester-capture challenge failures are non-overridable blockers? | `team-runtime-control`, `team-claim-compiler` | after Wave 23 |
| 17. Which substrate invariants deserve TLA+/PlusCal or equivalent model checks before implementation proceeds? | `team-quality-closeout` | after Wave 29 |
| 18. What minimum portfolio maturity is required for research, governed, and production major claims? | `team-science-quality`, `team-quality-closeout` | after Wave 20 |
| 19. Which method/data/source-lineage features should collapse raw evidence lines into one effective independent line? | `team-science-quality` | after Wave 17 |
| 20. What stopping rules should govern information saturation for low, medium, and high-impact policy claims? | `team-science-quality` | after Wave 19 |
| 21. Which evidence-synthesis certainty framework should PolicyOS use as the default outside health-policy domains: GRADE-like, domain-specific, or a PolicyOS profile? | `team-science-quality` | after Wave 19 |
| 22. Which Scholar source classes, freshness policies, citation-quality scores, and conflict thresholds are mandatory for academic evidence strands in research, governed, and production modes? | `team-domain-producers` | after Wave 14 |
| 23. Which existing module owners are sufficient as authoritative case-record producers, and which require explicit facade or projection packages? | `team-architecture-governance` | after Wave 14 |
| 24. Which agent-simulation and synthetic-world evidence lines are independent enough from observational and econometric evidence to raise effective evidence strength rather than only raw evidence count? | `team-science-quality` | after Wave 20 |
| 25. Which `runtime/quality/assurance_case.py` fields become canonical Policy Design Case fields, and which policy-specific records remain extensions? | `team-runtime-quality` | after Wave 2 |
| 26. How exactly do research/governed/production authority levels map to core governance profiles, execution profiles, and runtime effective-mode checks? | `team-runtime-control` | after Wave 5 |
| 27. Which DDM shift, degradation, readiness, incident, and root-cause events are mandatory for post-publication monitoring by authority level? | `team-ddm` | after Wave 27 |
| 28. Which BERL reliability bounds and local-infidelity thresholds should be shown to reviewers or block claim acceptance? | `team-claim-compiler` | after Wave 23 |
| 29. What Data Forge snapshot and read-API contracts are sufficient to prove corpus identity for legal, dataset, academic, and domain evidence? | `team-domain-producers` | after Wave 14 |

## Entries

### DL-PDC-0001 - target contract owner skeleton

- **Date**: 2026-05-17
- **Context**: Phase 1.4 requires an owner for every target contract named by the Policy Design Case implementation plan.
- **Decision**: Use the `Target Contract Ownership Skeleton` table as the initial owner map. Runtime quality owns closeout-readable case records, but behavioral producer ownership remains with Lex, Fabric, Scholar, Data Forge, Foundry, Scientist, IR analytics, BERL, DDM, core governance, and core audit as listed in the reuse column.
- **Affected ADR or SDD section**: SDD Capability Realization Map; plan Target Contract Names; ADR-0156, ADR-0157, ADR-0158, ADR-0159, ADR-0160, ADR-0161.
- **Affected wave and phase**: Wave 1, Phase 1.4.
- **Owner**: `docs-adr-integrator`
- **Reversibility**: reversible
- **Revisit trigger**: Any wave introduces a target contract at a different path, discovers that the primary owner cannot emit the required runtime record, or needs a `build-new` gap that overlaps a `wire-existing` owner.
- **Revisit wave**: after Wave 14 and quarterly review
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0002 - ADR proof obligation owner skeleton

- **Date**: 2026-05-17
- **Context**: Phase 1.4 requires an owner for every ADR 0156-0161 proof obligation before waves begin implementing runtime authority.
- **Decision**: Use the `ADR 0156-0161 Proof Obligation Ownership` table as the initial proof-owner map. Proof owners must update this log rather than silently moving an obligation, weakening a gate, or treating another phase's future work as current evidence.
- **Affected ADR or SDD section**: ADR-0156, ADR-0157, ADR-0158, ADR-0159, ADR-0160, ADR-0161.
- **Affected wave and phase**: Wave 1, Phase 1.4; all later ADR enforcement waves.
- **Owner**: `team-architecture-governance`
- **Reversibility**: reversible
- **Revisit trigger**: A proof obligation is implemented, blocked, assigned to a later wave, or found to require ADR supersession because implementation cannot satisfy the accepted ADR text.
- **Revisit wave**: after each listed obligation's revisit wave and quarterly review
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0003 - imported SDD open question revisit waves

- **Date**: 2026-05-17
- **Context**: Phase 1.4 requires unresolved SDD open questions to be imported and assigned revisit waves.
- **Decision**: Import all 29 open questions from `policy-design-best-in-class-operating-model.md` into the `Imported Source Open Questions` table with first-responsible owners and revisit waves. A revisit wave is not permission to ignore the question; it is the first expected point with enough implementation evidence to resolve, split, or promote the question.
- **Affected ADR or SDD section**: SDD Open Questions; SDD ADR Extraction Candidates; ADR-0156, ADR-0157, ADR-0158, ADR-0159, ADR-0160, ADR-0161.
- **Affected wave and phase**: Wave 1, Phase 1.4; Wave 41 documentation handoff.
- **Owner**: `docs-adr-integrator`
- **Reversibility**: reversible
- **Revisit trigger**: A revisit wave closes, the question blocks implementation earlier than expected, or the answer changes cross-component semantics and needs ADR promotion.
- **Revisit wave**: after each listed source question's revisit wave and quarterly review
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0004 - temporary Wave 0 false-pass carry-forward

- **Date**: 2026-05-17
- **Context**: Wave 0 froze the current false-pass baseline: deterministic serious lanes and readiness can pass while Policy Design Case, intent envelope, capability ledger, concept spine, producer refs, portfolio refs, and claim arguments are absent or only generic/non-PDC partial evidence.
- **Decision**: Temporarily allow this known false-pass state only as a named baseline gap while Wave 1 red controls, coverage tooling, and later runtime gates are being built. This exception cannot be used as evidence of serious policy readiness, cannot justify new passing gates, and must shrink as ADR-specific gates land.
- **Affected ADR or SDD section**: ADR-0156, ADR-0157, ADR-0158, ADR-0159, ADR-0160, ADR-0161; SDD Problem and Core Decision.
- **Affected wave and phase**: Wave 0 baseline; Wave 1, Phase 1.4; Wave 2; Wave 20; Wave 25; Wave 40.
- **Owner**: `team-quality-closeout`
- **Reversibility**: reversible
- **Revisit trigger**: Any readiness, scorecard, dashboard, export, or public artifact treats the Wave 0 false-pass state as production evidence; or the corresponding ADR gate wave closes without retiring or superseding this exception.
- **Revisit wave**: after Wave 2 for missing case authority, after Wave 20 for portfolio false passes, after Wave 25 for claim false passes, and final check at Wave 40
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0005 - strict xfail carry-forward for Wave 1 red controls

- **Date**: 2026-05-17
- **Context**: Phase 1.2 and the Wave 1 exit fence require red controls for known Policy Design Case false passes to fail for the intended reason before runtime implementation. The controls must remain visible and mergeable while later waves add the runtime scorecard/readiness gates.
- **Decision**: Carry the Phase 1.2 red controls in `tests/unit/runtime/quality/test_policy_design_case_false_passes.py` as strict expected failures with reason `Policy Design Case red control pending implementation`. A strict XPASS is a failure and must trigger removal of the corresponding xfail or replacement with a green enforcement test.
- **Affected ADR or SDD section**: ADR-0156, ADR-0157, ADR-0159, ADR-0160, ADR-0161; SDD Diagnostic Synthesis.
- **Affected wave and phase**: Wave 1, Phase 1.2; Wave 1 exit fence; Wave 2; Wave 20; Wave 25.
- **Owner**: `team-quality-closeout`
- **Reversibility**: reversible
- **Revisit trigger**: Any Phase 1.2 red control XPASSes, moves, broadens, increases, or remains xfailed after its corresponding runtime gate wave closes.
- **Revisit wave**: after Wave 2 for missing case/intent/capability/producer authority, after Wave 20 for portfolio false passes, and after Wave 25 for claim/warrant/BERL false passes
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0006 - Wave 4 canonical authority profile closure

- **Date**: 2026-05-17
- **Context**: Wave 4 requires requested policy authority, effective execution profile, validation profile, and fallback policy to close over Wave 3 pre-routing records without allowing dev/smoke/fixture semantics into serious closeout.
- **Decision**: Treat `src/polisyos/core/contracts/control.py` as the canonical authority taxonomy owner and require governance profiles, effective-mode ledgers, Policy Design Case authority profiles, canary request materialization, and canary evidence ledgers to derive from that mapping. Drift detection must reject synonymous second taxonomies.
- **Affected ADR or SDD section**: ADR-0157-O5, ADR-0157-O6; SDD Open Question 26.
- **Affected wave and phase**: Wave 4, Phase 4.1; Wave 4 exit fence.
- **Owner**: `team-runtime-control`
- **Reversibility**: costly_to_reverse
- **Revisit trigger**: Any new policy authority level, validation profile, fallback policy, or serious closeout mode is added outside the canonical mapping or requires different semantics for research/governed/production.
- **Revisit wave**: after Wave 5 and quarterly review
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0007 - Wave 26 second governance ADR pack

- **Date**: 2026-05-18
- **Context**: Wave 26 requires accepted ADR authority for human oversight/publication/external audit, lifecycle/DDM/ex-post/calibration, run cost/proportionality, and formal case invariants before Waves 27-35 implement those contracts.
- **Decision**: Promote the second governance pack to ADR-0162, ADR-0163, ADR-0164, and ADR-0165. Later governance, lifecycle, proportionality, and formal-invariant implementation must cite those ADRs or append a superseding decision before narrowing their contracts.
- **Affected ADR or SDD section**: ADR-0162, ADR-0163, ADR-0164, ADR-0165; SDD ADR Extraction Candidates; SDD Governance And Publication Layer; SDD Best-In-Class Success Criteria.
- **Affected wave and phase**: Wave 26, Phase 26.1; Wave 26 exit fence; Waves 27-35.
- **Owner**: `docs-adr-integrator`
- **Reversibility**: costly_to_reverse
- **Revisit trigger**: Any later governance implementation omits, weakens, or remaps a second-pack ADR proof obligation without a superseding ADR or accepted decision-log entry.
- **Revisit wave**: after Wave 29, after Wave 35, and quarterly review
- **Promotion status**: promoted_to_ADR-0162_ADR-0163_ADR-0164_ADR-0165

### DL-PDC-0008 - Wave 35 runtime scenario disposition

- **Date**: 2026-05-19
- **Context**: Wave 35 clustered Wave 34 findings for `runtime_scenario_variant_coverage` from PDD-037, PDD-055, and PDD-056; source evidence is `_build/diagnostics/pdd-037/cross_domain_generality_diagnostic_matrix.json`, `_build/diagnostics/pdd-055/metamorphic_policy_diagnostic_suite.json`, `_build/diagnostics/pdd-056/multilingual_transliteration_equivalence_audit.json`, and `_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json`.
- **Decision**: Defer these findings only to inserted Wave 35A, not to final closeout. Wave 36 may not start until Wave 35A either emits fresh cross-domain, metamorphic, multilingual, and hardcoded-language-path runtime evidence or appends a superseding decision with equivalent blocking force.
- **Affected ADR or SDD section**: ADR-0157, ADR-0158, ADR-0159, ADR-0160; SDD Diagnostic Synthesis; Wave 35 disposition.
- **Affected wave and phase**: Wave 35, Phase 35.1; Wave 35A; Wave 36 entry criteria.
- **Owner**: `team-runtime-quality`
- **Reversibility**: reversible
- **Revisit trigger**: Any attempt to run Wave 36 before Wave 35A exits, or any new runtime scenario matrix evidence changes the affected findings.
- **Revisit wave**: Wave 35A before Wave 36
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0009 - Wave 35 adversarial and strategic gate disposition

- **Date**: 2026-05-19
- **Context**: Wave 35 clustered Wave 34 findings for `adversarial_fail_closed_and_strategic_gates` from PDD-038, PDD-064, PDD-065, and PDD-098; source evidence is `_build/diagnostics/pass2/phase34_2_adversarial_fail_closed_diagnostics.json` and `_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json`.
- **Decision**: Treat existing fail-closed rows as accepted blockers only, and route missing adversarial, poisoning, error-taxonomy, and strategic-behavior gates to inserted Wave 35B. These blockers are not completed remediation and cannot satisfy deterministic closeout by themselves.
- **Affected ADR or SDD section**: ADR-0156, ADR-0157, ADR-0162, ADR-0165; SDD Diagnostic Synthesis; Wave 35 disposition.
- **Affected wave and phase**: Wave 35, Phase 35.1; Wave 35B; Wave 36 entry criteria.
- **Owner**: `team-security`
- **Reversibility**: reversible
- **Revisit trigger**: Any poisoning, prompt-injection, error-semantics, or strategic-behavior evidence changes, or Wave 36 is invoked before Wave 35B exits.
- **Revisit wave**: Wave 35B before Wave 36
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0010 - Wave 35 claim authority and extraction disposition

- **Date**: 2026-05-19
- **Context**: Wave 35 clustered Wave 34 findings for `claim_authority_and_extraction_measurement_binding` from PDD-044, PDD-100, and PDD-101; source evidence is `_build/diagnostics/pass2/phase_34_3_claim_grounding_validity_index.json`, `_build/diagnostics/pass2/phase_34_4_extraction_measurement_diagnostics.json`, and `_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json`.
- **Decision**: Route claim registry, producer locator, extraction-quality, and survey/measurement remediation to inserted Wave 35C. The PDD-044 scorecard blocker remains accepted only as evidence that publication is blocked, not as claim-authority remediation.
- **Affected ADR or SDD section**: ADR-0159, ADR-0161, ADR-0162; SDD Claim, Argument, And Public Evidence Layer; Wave 35 disposition.
- **Affected wave and phase**: Wave 35, Phase 35.1; Wave 35C; Wave 36 entry criteria.
- **Owner**: `team-claim-compiler`
- **Reversibility**: reversible
- **Revisit trigger**: Any claim compiler, Lex/Scholar locator, extraction-quality, or survey measurement evidence changes, or Wave 36 is invoked before Wave 35C exits.
- **Revisit wave**: Wave 35C before Wave 36
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0011 - Wave 35 semantic validity disposition

- **Date**: 2026-05-19
- **Context**: Wave 35 clustered Wave 34 findings for `semantic_validity_monitoring_and_model_readiness` from PDD-048, PDD-050, PDD-051, PDD-057, and PDD-087; source evidence is `_build/diagnostics/pass2/phase_34_3_claim_grounding_validity_index.json` and `_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json`.
- **Decision**: Route competence, transportability, uncertainty, monitoring, and model-readiness binding remediation to inserted Wave 35C alongside claim authority work, because these findings share claim-to-method and claim-to-runtime binding surfaces.
- **Affected ADR or SDD section**: ADR-0158, ADR-0160, ADR-0161, ADR-0163; SDD Evidence Portfolio And Validity Layer; Wave 35 disposition.
- **Affected wave and phase**: Wave 35, Phase 35.1; Wave 35C; Wave 36 entry criteria.
- **Owner**: `team-science-quality`
- **Reversibility**: reversible
- **Revisit trigger**: Any jurisdiction-spine, Foundry method-result, uncertainty, monitoring, DDM, or model-readiness evidence changes, or Wave 36 is invoked before Wave 35C exits.
- **Revisit wave**: Wave 35C before Wave 36
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0012 - Wave 35 operational recovery and archive disposition

- **Date**: 2026-05-19
- **Context**: Wave 35 clustered Wave 34 findings for `operational_recovery_resource_and_archive_readiness` from PDD-046, PDD-077, PDD-078, PDD-090, and PDD-104; source evidence is `_build/diagnostics/pass2/phase_34_5_operational_recovery_diagnostics.json` and `_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json`.
- **Decision**: Route root-cause, restore, resource-exhaustion, live/polling parity, and archive-grade verification remediation to inserted Wave 35D. Wave 36 and later closeout waves must keep these as blockers until the affected Phase 34.5 diagnostic is rerun.
- **Affected ADR or SDD section**: ADR-0156, ADR-0162, ADR-0163, ADR-0165; SDD Governance And Publication Layer; Wave 35 disposition.
- **Affected wave and phase**: Wave 35, Phase 35.1; Wave 35D; Wave 36 entry criteria.
- **Owner**: `team-core-audit`
- **Reversibility**: reversible
- **Revisit trigger**: Any restore, resource-exhaustion, live cursor, replay, archive, or operator-diagnostic evidence changes, or Wave 36 is invoked before Wave 35D exits.
- **Revisit wave**: Wave 35D before Wave 36
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0013 - Wave 35 human-facing legitimacy and trust disposition

- **Date**: 2026-05-19
- **Context**: Wave 35 clustered Wave 34 findings for `human_facing_legitimacy_memory_and_trust_controls` from PDD-034, PDD-069, PDD-083, PDD-097, PDD-099, and PDD-103; source evidence is `_build/diagnostics/pass2/phase_34_6_human_facing_legitimacy_memory_diagnostics.json` and `_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json`.
- **Decision**: Route projection consistency, operator truthfulness, memory/no-memory authority, implementation feasibility, contestability, and trust-framing controls to inserted Wave 35E. Dashboard, API, and public-facing closeout may not start from projection-only or optimistic UI semantics.
- **Affected ADR or SDD section**: ADR-0162, ADR-0163, ADR-0165; SDD Governance And Publication Layer; Wave 35 disposition.
- **Affected wave and phase**: Wave 35, Phase 35.1; Wave 35E; Wave 36 entry criteria.
- **Owner**: `team-quality-closeout`
- **Reversibility**: reversible
- **Revisit trigger**: Any dashboard/API projection, memory ledger, implementation, appeals, human-review, or trust-framing evidence changes, or Wave 36 is invoked before Wave 35E exits.
- **Revisit wave**: Wave 35E before Wave 36
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0014 - Wave 35 remediation integrity gate before deterministic closeout

- **Date**: 2026-05-19
- **Context**: Waves 35A-35E can produce resolved Wave 35 disposition evidence while some artifacts are remediation overlays or matrix ledgers rather than direct runtime/API/UI enforcement proof. Deterministic Wave 36 must not accidentally count synthetic remediation overlays as stronger closeout authority than their provenance permits.
- **Decision**: Insert Wave 35F before Wave 36. Wave 35F must classify every Wave 35A-35E remediation artifact as `runtime_emitted`, `runtime_derived`, `test_observed`, `synthetic_remediation_overlay`, or `manual_assertion`; closeout-critical overlay/manual rows must be backed by runtime/test-observed evidence or explicitly excluded from Wave 36 closeout authority by an accepted boundary.
- **Affected ADR or SDD section**: ADR-0162, ADR-0163, ADR-0165; SDD Governance And Publication Layer; Wave 35 disposition; Wave 36 entry criteria.
- **Affected wave and phase**: Wave 35F, Phase 35F.1; Wave 36 entry criteria.
- **Owner**: `team-quality-closeout`
- **Reversibility**: reversible
- **Revisit trigger**: Any attempt to start Wave 36 without Wave 35F passing, or any Wave 35A-35E artifact being used as closeout authority despite classification as `synthetic_remediation_overlay` or `manual_assertion`.
- **Revisit wave**: Wave 35F before Wave 36
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0015 - Wave 35H institutional provenance runtime ownership

- **Date**: 2026-05-19
- **Context**: Wave 35G closed 19 human-surface release blockers, but six of them - PDD-097-F001/F002/F003 (implementation feasibility) and PDD-099-F001/F002/F003 (contestability/appeals) - were cleared with `not_closeout_authority` boundaries rather than runtime evidence. The Wave 35E feasibility and appeals ledgers remain `manual_assertion`, so final publication cannot treat them as institutional proof. This is honest but leaves the institutional provenance surface short of runtime ownership.
- **Decision**: Insert Wave 35H before Wave 40. Wave 35H adds runtime producers that emit implementation-feasibility provenance (producer, event refs, artifact refs, claim binding, actor, risk, monitoring-outcome refs) and contestability lifecycle outcome provenance (producer, event refs, artifact refs, appeal disposition, lifecycle transition, publication-state effect), regenerates the Wave 35E ledgers from runtime emission, and reruns Wave 35F/35G classification so all six findings become `runtime_emitted`/`runtime_derived`. Wave 35H is not a Wave 36 release blocker; it may run in parallel with Waves 36-39 and gates Wave 40 final publication authority.
- **Affected ADR or SDD section**: ADR-0162, ADR-0163; SDD Governance And Publication Layer; Wave 35G institutional provenance boundary; Wave 40 entry criteria; Final Closeout Gate.
- **Affected wave and phase**: Wave 35H, Phases 35H.1-35H.3; Wave 40 entry criteria.
- **Owner**: `team-quality-closeout`
- **Reversibility**: reversible
- **Revisit trigger**: Any attempt to let final publication or Wave 40 rely on the implementation-feasibility or contestability/appeals ledgers while they remain `manual_assertion` or `not_closeout_authority`.
- **Revisit wave**: Wave 35H before Wave 40
- **Promotion status**: log_only_pending_revisit

### DL-PDC-0016 - Wave 41 documentation closeout review

- **Date**: 2026-05-19
- **Context**: Wave 41 requires a final decision-log review after Wave 35H and Wave 40 evidence is recorded. The reviewed evidence is `_build/policy-design-case/rebaseline/wave-35H/wave35h_exit_fence.json`, `_build/policy-design-case/rebaseline/wave-35H/wave35h_provenance_integrity_report.json`, `_build/policy-design-case/rebaseline/wave-40/wave40_readiness_bundle_inspection.json`, and `_build/policy-design-case/rebaseline/wave-40/wave40_exit_fence.json`.
- **Decision**: Retire all due temporary Policy Design Case exceptions and revisit items through Wave 41. Wave 40 reports `status=pass`, zero serious readiness failures, zero coverage target failures, zero anti-drift Non-Goal violations, SDD record-family mapping with 19 required families and zero issues, Pass 1B closeout with 39 implemented rows and zero issues, and `final_publication_decision=allowed`. Wave 35H reports six runtime-owned institutional provenance rows and zero `not_closeout_authority` rows, so the implementation-feasibility and contestability/appeals exception from DL-PDC-0015 is closed. No SDD or ADR change is required because this review confirms existing ADR-0156 through ADR-0165 semantics rather than changing them.
- **Affected ADR or SDD section**: ADR-0156, ADR-0157, ADR-0158, ADR-0159, ADR-0160, ADR-0161, ADR-0162, ADR-0163, ADR-0164, ADR-0165; SDD Final Closeout Gate; Decision Log.
- **Affected wave and phase**: Wave 35H, Wave 40, Wave 41 Phase 41.1, Wave 41 exit fence.
- **Owner**: `docs-adr-integrator`
- **Reversibility**: reversible
- **Revisit trigger**: A later closeout artifact reports new serious readiness failures, coverage target failures, anti-drift Non-Goal violations, `manual_assertion` or `not_closeout_authority` institutional rows, or a cross-component semantic change that requires ADR supersession.
- **Revisit wave**: quarterly review
- **Promotion status**: retired
- **Closes**: DL-PDC-0001, DL-PDC-0002, DL-PDC-0003, DL-PDC-0004, DL-PDC-0005, DL-PDC-0006, DL-PDC-0007, DL-PDC-0008, DL-PDC-0009, DL-PDC-0010, DL-PDC-0011, DL-PDC-0012, DL-PDC-0013, DL-PDC-0014, DL-PDC-0015
