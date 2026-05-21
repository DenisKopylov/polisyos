---
title: PolicyOS Policy Design Case Implementation Plan
status: archived
owner: team-architecture
created: 2026-05-16
---

# PolicyOS Policy Design Case Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implement the best-in-class policy-design operating model from `docs/system-design-decisions/policy-design-best-in-class-operating-model.md` and accepted ADRs 0156-0165, so a serious PolicyOS run produces a runtime-owned Policy Design Case with intent, concept, legal, data, literature, method, portfolio, argument, claim, governance, lifecycle, proportionality, formal invariant, and closeout evidence.

**Architecture:** reuse the honest diagnostics substrate as the authority layer and extend `src/polisyos/runtime/quality/assurance_case.py` rather than building a parallel case object. Wire existing Lex, Fabric, Scholar, Data Forge, Foundry, Scientist, IR analytics, BERL, DDM, core governance, and core audit capabilities into typed Policy Design Case records; scorecard/readiness may pass only when runtime evidence proves the case contracts.

**Tech Stack:** Python 3, Pydantic runtime quality contracts, FastAPI/runtime control surfaces, FileSystemCAS, Data Forge read APIs, Lex/Fabric/Scholar/Foundry/Scientist producers, IR analytics, BERL, DDM, core audit PROV/SLSA verifier, pytest, repo-quality gates, canary matrix tooling, Playwright dashboard journeys.

---

## Status

- Status: archived after Wave 41 closeout on 2026-05-19.
- Owner: `team-architecture`.
- Created: 2026-05-16.
- Scope: Policy Design Case runtime authority, producer evidence contracts, portfolio/multiverse/synthesis, claim argument closeout, and final policy-domain readiness.
- Closeout report:
  - `docs/archive/reports/2026-05-19-policy-design-case-wave41-closeout.md`
- Primary system design decision:
  - `docs/system-design-decisions/policy-design-best-in-class-operating-model.md`
- Accepted ADRs in direct scope:
  - `docs/adr/0156-policy-design-case-runtime-quality-assurance-profile.md`
  - `docs/adr/0157-policy-intent-capability-ledger-authority-profile.md`
  - `docs/adr/0158-concept-spine-multi-jurisdiction-reconciliation.md`
  - `docs/adr/0159-production-evidence-producer-contracts.md`
  - `docs/adr/0160-evidence-portfolio-independence-multiverse-synthesis.md`
  - `docs/adr/0161-claim-argument-warrant-compiler-closeout-gate.md`
  - `docs/adr/0162-human-oversight-publication-external-audit-authority.md`
  - `docs/adr/0163-lifecycle-ddm-ex-post-calibration.md`
  - `docs/adr/0164-run-cost-proportionality-evidence-budget-governance.md`
  - `docs/adr/0165-formal-policy-case-substrate-invariant-specs.md`
- Substrate ADRs that must not be weakened:
  - `docs/adr/0147-production-evidence-authority-ordering.md`
  - `docs/adr/0148-serious-run-state-machine-and-phase-barriers.md`
  - `docs/adr/0149-effective-mode-and-fallback-degradation-ledger.md`
  - `docs/adr/0150-scorecard-readiness-approval-projection-boundaries.md`
  - `docs/adr/0151-evidence-schema-compatibility-and-legacy-quarantine.md`
  - `docs/adr/0152-semantic-binding-lineage-and-claim-evidence.md`
  - `docs/adr/0153-diagnostic-slos-assurance-case-and-attestation.md`
  - `docs/adr/0154-diagnostic-event-envelope-and-runtime-log-contract.md`
  - `docs/adr/0155-production-invariant-registry-and-ownership-contract.md`
- Diagnostic source backlog:
  - `docs/backlog/production-data-e2e-diagnostic-backlog.md`
  - Pass 1A domain diagnostics feed Wave 3 and Waves 8-25.
  - Pass 1B hardening diagnostics feed Waves 1, 3, 24, 27-32, and 40.
  - Pass 2 behavioral diagnostics are unlocked after Wave 33 emits real domain evidence.

## Definition Of Done

- [x] A serious run emits a runtime-owned Policy Design Case profile over `src/polisyos/runtime/quality/assurance_case.py`.
- [x] The case contains or blocks every minimum record family named by the SDD.
- [x] Intent envelope, capability ledger, requested/effective authority profile, and requester-capture challenge are materialized before producer execution.
- [x] Concept spine and jurisdiction spine close over legal, data, literature, method, objective, option, and claim evidence.
- [x] Lex emits retrieval-backed norm evidence, not legal-shaped payloads.
- [x] Data Forge snapshot/read-API identity is bound into legal, catalog, academic, and domain corpus evidence.
- [x] Fabric emits field-level source/data evidence with rights, quality, lineage, dictionary, unit, geography, time, and rejected-candidate records.
- [x] Scholar emits academic and grey-literature evidence with query graph, scoring, freshness, citation lineage, and support/conflict links.
- [x] Foundry emits method selection, rejection, assumption, identification, uncertainty, sensitivity, transportability, and method-result refs before claims consume method outputs.
- [x] Major empirical claims use predeclared evidence portfolios, independence maps, effective independent evidence counts, multiverse/specification-curve reports, disconfirming lines, synthesis reports, certainty ratings, stopping-rule results, and cost/proportionality evidence unless an accepted single-line deficit is visible.
- [x] Claim compiler emits assurance-case claims with argument strategy, warrant, evidence refs, rebuttals, counter-evidence, requester-capture challenge, BERL reliability refs selected by authority profile, and assurance deficits or blockers.
- [x] Structured expert judgement and consultation are first-class evidence families and cannot masquerade as observed data.
- [x] Implementation contract, monitoring plan, evaluation design, DDM post-market monitoring, and ex-post outcome reassessment are linked to the case lifecycle.
- [x] Human oversight, producer independence, public contestability, publication trust, external audit, and local/client evidence boundaries are case records, not side notes.
- [x] Every case record family exposes maturity and non-adversarial self-FMEA status.
- [x] Run cost/proportionality, best-in-class benchmarking, and formal/model-checked invariant coverage are represented or explicitly blocked by authority profile.
- [x] Scorecard/readiness fail on missing case records, static-only producer maps, local file/path substitution, unsupported claim refs, post-hoc portfolio cherry-picking, missing warrant, missing counter-evidence assessment, missing BERL reliability required by authority profile, and silent promotion of research deficits.
- [x] Dashboard/API/public/export surfaces read and label case authority without minting it.
- [x] Final deterministic closeout proves the Policy Design Case can be generated, inspected, replayed, and audited without private operator context.
- [x] Early walking skeleton closeout proves the ref path before full domain, portfolio, governance, and closeout layers are built.

## ADR Conformance Rule

This plan implements ADRs 0156-0165 on top of ADRs 0147-0155. A phase is not
complete when it creates a file or passes a happy path. A phase is complete
only when the relevant ADR decision bullets are enforced by producer code,
reader code, scorecard/readiness checks, negative controls, and operator-visible
failure records.

| ADR | Required implementation proof |
|-----|-------------------------------|
| ADR-0156 | Policy Design Case extends `runtime/quality/assurance_case.py`; no parallel serious-run case authority; SACM/CAE/GSN mapping or exporter exists; records are CAS/event/schema/mode compatible. |
| ADR-0157 | intent envelope, capability ledger, skipped-duty blockers, requester-capture fields, and profile/effective-mode mapping are runtime-owned and scorecard/readiness-enforced. |
| ADR-0158 | concept spine and jurisdiction spine are per-run authority artifacts consumed by producers and claims; concept/jurisdiction mismatch fails closeout. |
| ADR-0159 | Lex, Fabric, Scholar, and Data Forge emit distinct producer-owned evidence; static inventory and narrative citations cannot satisfy runtime evidence. |
| ADR-0160 | major claims use predeclared portfolios, independence maps, multiverse/specification curves, disconfirming evidence, synthesis, and stopping rules or accepted deficits. |
| ADR-0161 | major claims require argument, warrant, rebuttal/counter-evidence, deficits/blockers, and BERL reliability where explanation trust affects claim acceptance. |
| ADR-0162 | human oversight, producer independence, publication trust, public export, local/client boundaries, and external audit evidence are runtime case authority records. |
| ADR-0163 | lifecycle, DDM monitoring, ex-post reassessment, calibration, and learning records are append-only case evidence and cannot rewrite historical authority. |
| ADR-0164 | run cost, evidence budgets, proportionality, stopping-rule budget proof, and benchmarking are authority-profile-scoped evidence rather than optional operations notes. |
| ADR-0165 | formal Policy Design Case and substrate invariants have registry-backed owners, ADR authority, and non-unit-test evidence where substrate-critical. |

Implementation work must update this plan if a required ADR proof cannot be
implemented as written. Do not silently narrow an ADR requirement in code.

## Non-Goals

- Do not rebuild a second Policy Design Case object outside `runtime/quality` without a superseding ADR.
- Do not rebuild DOE, discovery, Foundry method consensus/equivalence, Scholar retrieval, Data Forge corpus provenance, BERL, DDM, core governance profiles, or core audit verifier before proving rejected reuse.
- Do not weaken the honest diagnostics substrate to make domain evidence pass.
- Do not allow static inventory, broad manifest roles, local file paths, public exports, dashboard state, or bundle-local files to satisfy runtime producer evidence.
- Do not make one dataset and one method production-grade for a major claim unless the case carries an accepted single-line-evidence deficit.
- Do not treat evidence disagreement as noise to average away.
- Do not let exploratory/research deficits silently upgrade to governed or production authority.
- Do not rewrite historical ADRs; add new ADRs or accepted supersession when cross-component contract semantics change.

## Severity Labels

- `PDC-CRITICAL`: a serious policy claim can appear production-ready without runtime-owned Policy Design Case evidence.
- `PDC-HIGH`: a case record exists, but concept, jurisdiction, producer, portfolio, argument, or profile semantics are ambiguous or unenforced.
- `PDC-MEDIUM`: projection, operator diagnostics, documentation, or compatibility behavior is incomplete but cannot upgrade serious authority.
- `PDC-LOW`: naming, migration ergonomics, docs, or test organization work.

## Execution Rule

Waves are sequential. Phases inside one wave are parallel by construction.
When that stops being true, split the dependent work into the next wave before
implementation.

- [x] A later wave may start exploratory work, but it may not merge until the previous wave exit fence is green.
- [x] Every phase must land with at least one negative test that fails before the change and passes after the change.
- [x] Every phase that introduces a new contract must add producer tests and reader/enforcer tests.
- [x] Every phase touching serious closeout must update readiness or scorecard enforcement.
- [x] Every phase touching dashboard/API/public output must prove projection cannot become authority.
- [x] Every phase that wires an existing capability must include a reuse proof and must not duplicate the owner module.
- [x] Every conditional scope phrase is resolved by an authority profile or registry row, not by implementer judgment.
- [x] Every phase handoff must name the generated runtime record, schema/fixture, scorecard or readiness gate, negative test, and rebaseline artifact.
- [x] Every shared runtime-quality, readiness, ADR index, or rebaseline file has exactly one integration owner per wave.

Each phase implementation packet must include:

- phase id and owner;
- entry prerequisites from previous wave exit fences;
- exact files or modules changed;
- read-only inputs consumed from earlier phases;
- runtime records, schemas, fixtures, and generated evidence paths produced;
- negative tests and expected failure messages;
- positive tests and expected pass commands;
- scorecard/readiness/drift/coverage hooks added or confirmed;
- rollback or blocker behavior when required inputs are missing.

## Wave Format And Cross-Wave Dependencies

The wave sections below are the only execution-order source of truth. A worker
should be able to open a wave and assume every phase listed inside that wave can
be developed and merged in any order after the previous wave exit fence is
green.

If a phase needs another phase from the same wave to finish first, the plan is
wrong. Split that dependent phase into the next wave before implementation.

Single-phase waves are intentional serial handoff gates. They keep the original
format while making dependencies visible.

### Wave Format Contract

- [x] Waves are sequential.
- [x] All phases inside one wave are parallel by construction.
- [x] A phase may read outputs from previous waves only.
- [x] A phase may not require a handoff from another phase in the same wave.
- [x] A phase may do read-only reconnaissance for a later wave, but may not merge authority-shaping code early.
- [x] Shared files are allowed only when the wave names one owner and the phases still do not depend on each other's outputs.
- [x] Closeout commands that share ports, CAS, generated bundles, matrix output, or readiness output are modeled as single-phase serial waves.

### Shared Write Locks

| Shared surface | Lock owner | Why it is serialized |
|----------------|------------|----------------------|
| `src/polisyos/runtime/quality/assurance_case.py` and Policy Design Case schemas | wave runtime-quality integrator | case node and authority schema drift affects every phase |
| `src/polisyos/runtime/quality/scorecard.py` and `tools/ci/check_policyos_production_quality_best_in_class.py` | wave closeout integrator | readiness semantics must not be softened by competing changes |
| `tools/quality/validation/build_policy_design_case_coverage.py` and drift checks | coverage integrator | denominator changes must be intentional and recorded |
| `docs/adr/index.toml`, generated ADR indexes, and decision log | docs/ADR integrator | generated docs and supersession state conflict easily |
| `_build/policy-design-case/rebaseline/wave-*` | closeout runner | rebaseline outputs must be fresh, sequential, and attributable |
| local integration stack, dashboard smoke, canary matrix, readiness output | closeout runner | commands share ports, CAS, generated bundles, and matrix/readiness state |

### Test And Tool Placement Conventions

Use these paths unless an existing local test file already owns the same
contract. If a phase chooses a different path, it must record the reason in the
decision log.

| Contract type | Preferred tests or tools |
|---------------|--------------------------|
| Runtime quality record schemas | `tests/unit/runtime/quality/test_policy_design_case_<record>.py` |
| Scorecard/readiness enforcement | `tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py` plus a focused `tests/repo_quality/tools/test_policy_design_case_<gate>.py` |
| Coverage and drift tooling | `tests/repo_quality/tools/test_policy_design_case_coverage.py`, `tests/repo_quality/tools/test_policy_design_case_drift.py`, `tools/quality/validation/build_policy_design_case_coverage.py`, `tools/quality/validation/check_policy_design_case_drift.py` |
| Rebaseline comparison | `tests/repo_quality/tools/test_policy_design_case_rebaseline.py`, `tools/quality/validation/compare_policy_design_case_rebaseline.py` |
| Walking skeleton closeout | `tests/repo_quality/tools/test_policy_design_case_walking_skeleton.py` |
| Lex producer contracts | `tests/unit/lex/test_policy_design_case_legal_authority.py` |
| Data Forge and Fabric contracts | `tests/unit/fabric/test_policy_design_case_source_evidence.py` and focused Data Forge tests under the existing Data Forge test tree |
| Scholar contracts | `tests/unit/scholar/test_policy_design_case_scholar_evidence.py` |
| Foundry, Scientist, and IR portfolio contracts | focused tests under existing `tests/unit/foundry`, `tests/unit/scientist`, and repo-quality portfolio tests |
| Public export, audit, and client projection | `tests/repo_quality/tools/test_policy_design_case_public_export.py`, `tests/repo_quality/tools/test_policy_design_case_external_audit.py`, dashboard journey smoke tests |
| Pass 2 disposition | `tests/repo_quality/tools/test_policy_design_case_pass2_disposition.py`, `tools/quality/validation/check_policy_design_case_pass2_disposition.py` |
| Pass 1B hardening coverage | `tests/repo_quality/tools/test_policy_design_case_pass1b_hardening.py`, `tools/quality/validation/check_policy_design_case_pass1b_hardening.py` |
| Formal invariant coverage | `tests/repo_quality/tools/test_policy_design_case_formal_invariants.py`, `tools/quality/validation/check_policy_design_case_formal_invariants.py`, `architecture/policy_design_case/formal_invariant_specs.toml` |

### Per-Phase Acceptance Packet

Before any phase is marked complete, its PR or branch notes must include this
packet. Missing fields are blockers, not reviewer discretion.

| Packet field | Required content |
|--------------|------------------|
| Scope | exact phase id, SDD record families, ADR bullets, PDD diagnostics, and authority profiles touched |
| Reuse proof | existing modules wired, rejected reuse if anything is `build-new`, and no duplicate owner module |
| Runtime evidence | CAS/event/schema/mode/same-input refs or typed blocker for every record introduced |
| Tests | failing negative test name, passing positive test name, and exact commands run |
| Enforcement | scorecard/readiness/drift/coverage hook or a typed reason the hook belongs to a later phase |
| Operator surface | failure code, owner, missing input, upstream cause, downstream impact, and next command |
| Rebaseline | generated `_build/policy-design-case/rebaseline/wave-N/` artifacts and diff from previous wave |
| Handoff | downstream phases unblocked, schemas frozen, and any remaining blockers with revisit wave |

## Persistent Workstream Ownership

| Workstream | ADR | Persistent owner role | Eve-of-wave review question |
|------------|-----|-----------------------|-----------------------------|
| Policy Design Case runtime profile | ADR-0156 | `team-runtime-quality` | Does this wave extend `runtime/quality`, or did it create a parallel case authority? |
| Intent, capability, profile mapping | ADR-0157 | `team-runtime-control` | Does routing preserve intent, duties, skipped blockers, and effective mode? |
| Concept and jurisdiction spine | ADR-0158 | `team-policy-semantics` | Do all producers and claims close over one per-run spine? |
| Producer evidence contracts | ADR-0159 | `team-domain-producers` | Does each producer own its evidence and rejected candidates? |
| Portfolio, independence, synthesis | ADR-0160 | `team-science-quality` | Does the case reason over independent evidence, not raw count? |
| Claim argument and compiler gate | ADR-0161 | `team-claim-compiler` | Does every major claim have argument, warrant, rebuttal, deficits, and required refs? |
| Governance, publication, audit | ADR-0162 | `team-quality-closeout`, `team-core-audit` | Does publication derive from case authority and remain externally replayable? |
| Lifecycle, DDM, calibration | ADR-0163 | `team-ddm`, `team-science-quality` | Does post-publication learning append evidence without rewriting historical authority? |
| Proportionality and benchmarking | ADR-0164 | `team-science-quality` | Does evidence depth match risk without waiving non-overridable duties? |
| Formal invariant specs | ADR-0165 | `team-quality-closeout` | Are substrate-critical invariants specified outside ordinary unit tests? |
| Substrate authority | ADR-0147-0155 | `team-quality-closeout` | Does the domain plan preserve all serious closeout invariants? |

## Workstream Ownership Rules

Use short-lived branches under `codex/policy-design-case-*`.

| Workstream | Primary owner files | Merge guard |
|------------|---------------------|-------------|
| Runtime case contracts | `src/polisyos/runtime/quality/*`, `schemas/runtime_quality/*` | one runtime-quality owner per wave |
| Intent/capability/runtime profile | `src/polisyos/runtime/quality/*`, `src/polisyos/core/contracts/control.py`, `src/polisyos/core/governance/*` | no producer merge before intent/capability exit fences |
| Concept/jurisdiction spine | `src/polisyos/fabric/entity_resolution/*`, `src/polisyos/scientist/cross_graph/*`, `src/polisyos/ir/*`, `src/polisyos/runtime/quality/*` | no producer merge before spine exit fences |
| Lex producer | `src/polisyos/lex/*`, Lex production-data readers, runtime producer adapters | consumes only previous-wave spine refs |
| Data Forge/Fabric producer | `src/polisyos/data_forge/*`, `src/polisyos/fabric/*` | Fabric evidence starts after Data Forge snapshot wave |
| Scholar producer | `src/polisyos/scholar/*` | consumes only previous-wave intent and spine refs |
| Foundry/IR/Scientist portfolio | `src/polisyos/foundry/*`, `src/polisyos/scientist/*`, `src/polisyos/ir/analytics/*` | portfolio work starts after producer evidence exit fences |
| Claim compiler and BERL | `src/polisyos/runtime/quality/assurance_case.py`, claim compiler modules, `src/polisyos/berl/*` | BERL integration starts after argument/warrant exit fence |
| Scorecard/readiness | `src/polisyos/runtime/quality/scorecard.py`, `tools/ci/check_policyos_production_quality_best_in_class.py` | one closeout owner per gate wave |
| Dashboard/API/public projections | `apps/runtime-dashboard/*`, runtime API routes | projection work starts after projection-label exit fence |
| Docs and ADRs | `docs/adr/*`, `docs/system-design-decisions/*`, `docs/plans/*` | one docs owner; no historical ADR rewrites |

## Phase Fence Checklist

| Fence | Required before merge |
|-------|-----------------------|
| Contract fence | Pydantic or JSON schema, example fixture, producer test, reader test |
| Reuse fence | named existing owner, rejected-reuse evidence for any build-new component |
| Authority fence | runtime event, CAS ref, envelope, schema, same-input closure, profile/effective-mode refs |
| Spine fence | concept/jurisdiction/unit/time/geography closure or typed blocker |
| Producer fence | selected and rejected candidates, rights/freshness/quality/lineage, blockers |
| Portfolio fence | predeclared design, evidence lines, independence collapse, disconfirming lines, synthesis |
| Claim fence | argument, warrant, evidence refs, rebuttals, counter-evidence, deficits, and BERL refs selected by authority profile |
| Projection fence | dashboard/API/public output labels source and cannot be consumed as authority |
| Operator fence | failure has owner, missing input, upstream cause, downstream impact, refs, next command |

## Wave Rebaseline Cadence

Every wave ends with a rebaseline, not only a test pass. The rebaseline answers:

- [x] Did the wave remove a known false pass or replace it with an honest blocker?
- [x] Did any static inventory, public export, local path, or projection become authority?
- [x] Did reuse-first wiring prevent duplicate implementation?
- [x] Did operator time-to-root-cause improve or stay within budget?
- [x] Did evidence quality improve without lowering substrate requirements?

Required artifacts for every wave:

- `_build/policy-design-case/rebaseline/wave-N/coverage.json`
- `_build/policy-design-case/rebaseline/wave-N/coverage.md`
- `_build/policy-design-case/rebaseline/wave-N/readiness.json`
- `_build/policy-design-case/rebaseline/wave-N/deterministic_matrix.json`
- `_build/policy-design-case/rebaseline/wave-N/policy_design_case_sample.json`
- `_build/policy-design-case/rebaseline/wave-N/diff_from_wave_N_minus_1.json`
- `_build/policy-design-case/rebaseline/wave-N/operator_root_cause_sample.md`

Required commands:

```bash
uv run python tools/quality/validation/build_policy_design_case_coverage.py --repo-root . --output-dir _build/policy-design-case/rebaseline/wave-N
uv run python tools/ops_runners/runtime/run_canary_matrix.py --deterministic --json-output _build/policy-design-case/rebaseline/wave-N/deterministic_matrix.json --timeout-s 1200
uv run python tools/ci/check_policyos_production_quality_best_in_class.py --repo-root . --output-format json > _build/policy-design-case/rebaseline/wave-N/readiness.json
uv run python tools/quality/validation/compare_policy_design_case_rebaseline.py --current _build/policy-design-case/rebaseline/wave-N --previous _build/policy-design-case/rebaseline/wave-N-minus-1
```

If a command does not exist in an early wave, the wave must create it or record
typed setup evidence. Do not silently skip rebaseline evidence.

## Policy Design Case Coverage Dashboard

The coverage dashboard is generated, not hand-edited.

Target tool:

```bash
uv run python tools/quality/validation/build_policy_design_case_coverage.py --repo-root . --output-dir _build/policy-design-case/coverage
```

Required metrics:

`Spine target` means after Wave 11. `Claim target` means after Wave 25.

| Metric | Baseline target | Spine target | Claim target | Final target |
|--------|----------------|--------------|--------------|--------------|
| `case_record_family_schema_pct` | baseline | `>= 50` | `>= 90` | `100` |
| `runtime_quality_profile_coverage_pct` | baseline | `>= 70` | `100` | `100` |
| `walking_skeleton_ref_path_pct` | baseline | `100` | `100` | `100` |
| `intent_capability_gate_pct` | baseline | `100` | `100` | `100` |
| `concept_spine_closure_pct` | baseline | `>= 80` | `100` | `100` |
| `producer_contract_runtime_evidence_pct` | baseline | baseline | `>= 90` | `100` |
| `data_forge_snapshot_binding_pct` | baseline | baseline | `>= 90` | `100` |
| `scholar_literature_strand_pct` | baseline | baseline | `>= 80` | `100` |
| `portfolio_predeclaration_pct` | baseline | baseline | `>= 90` | `100` |
| `effective_independent_count_pct` | baseline | baseline | `>= 80` | `100` |
| `claim_argument_warrant_pct` | baseline | baseline | `100` | `100` |
| `berl_required_reliability_pct` | baseline | baseline | `>= 80` | `100` |
| `structured_judgement_consultation_pct` | baseline | baseline | baseline | `100` for registry-required judgement or consultation families |
| `implementation_monitoring_evaluation_pct` | baseline | baseline | baseline | `100` for registry-required monitoring or evaluation families |
| `human_oversight_independence_pct` | baseline | baseline | baseline | `100` for registry-required oversight or independence families |
| `integrity_self_fmea_maturity_pct` | baseline | baseline | `>= 70` | `100` |
| `publication_external_audit_pct` | baseline | baseline | baseline | `100` when public/exported |
| `benchmarking_proportionality_pct` | baseline | baseline | `>= 70` | `100` |
| `formal_invariant_spec_pct` | baseline | baseline | baseline | `>= 80` for closeout-critical invariants |
| `pass2_disposition_pct` | baseline | baseline | baseline | `100` before closeout |
| `false_pass_rate_negative_controls` | `0` | `0` | `0` | `0` |
| `reuse_violation_count` | `0` | `0` | `0` | `0` |

Coverage may drop only when the denominator becomes more honest. Any drop must
be explained in the decision log and must not increase false-pass rate.

## Anti-Drift Audit And Softening Detector

Every wave exit and every PR that touches policy-case-owned files must run:

```bash
uv run python tools/quality/validation/check_policy_design_case_drift.py --repo-root .
uv run python tools/quality/validation/check_substrate_drift.py --repo-root .
```

The policy-case drift detector must fail on:

- new parallel case authority outside `runtime/quality`;
- new second profile taxonomy not mapped to core governance/effective mode;
- new producer evidence accepted from static inventory, local files, dashboard state, public export, or bundle-local refs;
- new major claim accepted with one dataset and one method without an accepted deficit;
- post-hoc portfolio selection that omits disagreeing lines;
- raw evidence count reported without effective independent evidence count;
- claim refs accepted without argument, warrant, rebuttal/counter-evidence, or deficits;
- explanation or warrant accepted without BERL reliability evidence when required;
- exploratory/research deficits promoted to governed or production authority;
- expert judgement accepted as observed data or consultation objections hidden from the case;
- implementation monitoring/evaluation, DDM, lifecycle, audit, or public contestability records omitted when the case scope requires them;
- case record maturity reported as complete without self-FMEA, partial-state contradiction checks, or formal invariant coverage where required;
- best-in-class claims made without benchmarking and proportionality evidence;
- any code or test change that narrows ADR-0156 through ADR-0165 without a superseding ADR.

## Decision Log And ADR Supersession Cadence

Decision log path:

- `docs/system-design-decisions/policy-design-case-decision-log.md`

Each entry must include:

- date;
- context;
- decision;
- affected ADR or SDD section;
- affected wave and phase;
- owner;
- reversibility: `reversible`, `costly_to_reverse`, or `irreversible`;
- revisit trigger;
- revisit wave;
- whether it needs promotion to ADR.

Promotion rule:

- promote to ADR when a decision changes cross-component contract semantics,
  case authority, producer duty, profile mapping, portfolio semantics, claim
  acceptance, public evidence semantics, or compatibility guarantees;
- keep in the decision log when a decision is local, reversible, and does not
  narrow an ADR;
- use new ADRs or accepted supersession, never historical ADR rewrites.

Accepted second ADR pack for Wave 26:

- [ADR-0162: Human Oversight, Publication, And External Audit Authority](../../adr/0162-human-oversight-publication-external-audit-authority.md).
- [ADR-0163: Lifecycle, DDM, Ex-Post Outcomes, And Calibration](../../adr/0163-lifecycle-ddm-ex-post-calibration.md).
- [ADR-0164: Run Cost, Proportionality, And Evidence Budget Governance](../../adr/0164-run-cost-proportionality-evidence-budget-governance.md).
- [ADR-0165: Formal Policy Case And Substrate Invariant Specs](../../adr/0165-formal-policy-case-substrate-invariant-specs.md).

## Target Contract Names

Implementers may adjust module names only if they preserve these concepts and
update all references in this plan.

| Contract | Proposed path |
|----------|---------------|
| Policy Design Case runtime profile | `src/polisyos/runtime/quality/assurance_case.py` |
| Policy Design Case record families | `src/polisyos/runtime/quality/policy_design_case.py` |
| Intent envelope | `src/polisyos/runtime/quality/policy_intent.py` |
| Capability selection ledger | `src/polisyos/runtime/quality/capability_ledger.py` |
| Authority profile mapping | `src/polisyos/runtime/quality/policy_authority_profile.py` |
| Concept spine ledger | `src/polisyos/runtime/quality/concept_spine.py` |
| Jurisdiction spine ledger | `src/polisyos/runtime/quality/jurisdiction_spine.py` |
| Data Forge snapshot binding | `src/polisyos/runtime/quality/data_forge_binding.py` |
| Lex norm authority report | `src/polisyos/runtime/quality/legal_authority.py` |
| Fabric source evidence report | `src/polisyos/runtime/quality/source_evidence.py` |
| Scholar evidence report | `src/polisyos/scholar/evidence.py` |
| Method validity report | `src/polisyos/runtime/quality/method_validity.py` |
| Evidence portfolio design | `src/polisyos/runtime/quality/evidence_portfolio.py` |
| Evidence independence map | `src/polisyos/runtime/quality/evidence_independence.py` |
| Specification curve report | `src/polisyos/runtime/quality/specification_curve.py` |
| Disconfirming evidence ledger | `src/polisyos/runtime/quality/disconfirming_evidence.py` |
| Evidence synthesis report | `src/polisyos/runtime/quality/evidence_synthesis.py` |
| Claim argument/warrant records | `src/polisyos/runtime/quality/claim_argument.py` |
| BERL warrant reliability bridge | `src/polisyos/runtime/quality/explanation_reliability.py` |
| Structured judgement record | `src/polisyos/runtime/quality/structured_judgement.py` |
| Consultation evidence record | `src/polisyos/runtime/quality/consultation.py` |
| Implementation monitoring/evaluation record | `src/polisyos/runtime/quality/implementation_monitoring.py` |
| Human oversight effectiveness record | `src/polisyos/runtime/quality/human_review.py` |
| Producer independence record | `src/polisyos/runtime/quality/independence.py` |
| Integrity threat model and self-FMEA | `src/polisyos/runtime/quality/case_integrity.py` |
| Case maturity profile | `src/polisyos/runtime/quality/case_maturity.py` |
| DDM monitoring bridge | `src/polisyos/runtime/quality/ddm_monitoring.py` |
| Lifecycle/ex-post/calibration record | `src/polisyos/runtime/quality/case_lifecycle.py` |
| Publication trust and external audit record | `src/polisyos/runtime/quality/publication_trust.py` |
| Benchmarking and proportionality record | `src/polisyos/runtime/quality/policy_benchmarking.py` |
| Formal invariant spec registry | `architecture/policy_design_case/formal_invariant_specs.toml` |
| Walking skeleton readiness smoke | `tools/quality/validation/check_policy_design_case_walking_skeleton.py` |
| Pass 2 disposition checker | `tools/quality/validation/check_policy_design_case_pass2_disposition.py` |
| Policy Design Case coverage | `tools/quality/validation/build_policy_design_case_coverage.py` |
| Policy Design Case drift detector | `tools/quality/validation/check_policy_design_case_drift.py` |
| Rebaseline comparator | `tools/quality/validation/compare_policy_design_case_rebaseline.py` |
| Decision log | `docs/system-design-decisions/policy-design-case-decision-log.md` |

These runtime quality paths are projection and authority-record homes. They do
not move behavioral ownership out of Lex, Fabric, Scholar, Data Forge, Foundry,
Scientist, IR analytics, BERL, DDM, core governance, or core audit. Producer
modules own the behavior and source evidence; `runtime/quality` owns the
runtime-readable case records, authority envelopes, and closeout-facing
projections.

## Full SDD Record-Family Coverage Contract

This table is the completeness contract against the design document. A wave
may split the implementation across several files, but the acceptance signal
must be true before final closeout.

| SDD record family | Primary waves/phases | Acceptance signal |
|-------------------|----------------------|-------------------|
| `intent_authoring_and_capture_risk.v1` | 3.1, 23.2 | intent envelope, authoring provenance, requester preference, requester-capture risk, and challenge depth are runtime-owned |
| `capability_mode_and_fallback_selection.v1` | 3.2, 4.1, 5.1 | capability duties, skipped blockers, fallback/degradation, and effective-mode closure are enforced |
| `concept_and_jurisdiction_spine.v1` | 8.1, 8.2, 9.1, 11.1 | concept and jurisdiction spine mismatches fail scorecard/readiness |
| `legal_authority_and_competence.v1` | 12.1, 14.1 | Lex retrieval, norm applicability, competence, selected/rejected norms, and legal blockers are runtime evidence |
| `data_source_semantic_lineage.v1` | 12.2, 13.1, 14.1 | Data Forge snapshot/read-API identity and Fabric field-level lineage are claim-bindable |
| `scholar_academic_evidence.v1` | 12.3, 14.1 | Scholar query/scoring/freshness/citation/support-conflict evidence is a producer-owned strand |
| `numeric_time_and_geography_semantics.v1` | 10.1, 13.1, 21.1 | claims fail on unit, currency, geography, calendar, freshness, or retention mismatch |
| `method_selection_and_validity.v1` | 12.4, 18.1, 18.2 | Foundry/IR emit selected/rejected methods, assumptions, identification, transportability, falsification, and validity limits |
| `evidence_portfolio_and_synthesis.v1` | 15.1-20.1 | portfolios are predeclared, independent, severe-test-aware, synthesized, and scorecard-enforced |
| `structured_judgement_and_consultation.v1` | 27.1, 32.1 | expert judgement is labelled as judgement and stakeholder objections/response-to-comment are first-class records |
| `options_objectives_and_tradeoffs.v1` | 12.5, 15.1, 30.1 | baseline, alternatives, rejected options, objective function, distributional effects, and proportionality are present or blocked |
| `claim_argument_evidence_case.v1` | 21.1-25.1 | major claims have assurance nodes, arguments, warrants, evidence refs, rebuttals, counter-evidence, deficits, and BERL reliability where required |
| `implementation_monitoring_and_evaluation.v1` | 23.2, 27.2, 32.1 | implementation contract, monitoring plan, evaluation design, pre-publication challenge, and DDM post-market evidence are registry-controlled case records |
| `human_oversight_independence_and_review.v1` | 27.1, 32.1 | producer independence, reviewer independence, review effectiveness, dissent, override, and rubber-stamp risk are enforced |
| `integrity_self_fmea_and_maturity.v1` | 1.5, 29.1-29.4, 40.1 | evidence-graph threat model, self-FMEA, maturity profile, and partial-state contradiction checks are generated and gated |
| `lifecycle_ex_post_and_calibration.v1` | 27.2, 34.5, 34.6, 35.1 | lifecycle, supersession, recall/retraction, ex-post outcomes, reassessment, calibration, and memory contamination checks are wired |
| `publication_trust_and_external_governance.v1` | 24.1, 27.3, 28.4, 28.5, 40.1 | approval, override, signing, release, dependency rights, public export, PROV/SLSA archive, verifier, replay, and client compliance are evidence |
| `best_in_class_benchmarking.v1` | 31.1, 41.1 | external audit, human-team benchmark, reversal/retraction, calibration, claim substantiation, triangulation, operator time-to-root-cause, cost, and proportionality metrics exist for at least one implemented domain |
| `formal_substrate_invariant_spec.v1` | 29.4, 40.1 | closeout-critical authority, phase, same-input, CAS/event, and terminal readiness invariants have formal/model-checked specs or accepted blockers |

## Pass 1B Hardening Coverage Contract

Pass 1B cannot remain a single generic hardening row. These PDDs are static or
governance diagnostics that must map to concrete plan phases before Wave 40.

| Pass 1B group | PDDs | Primary phases | Required acceptance |
|---------------|------|----------------|---------------------|
| Tenant/CAS/approval/governance | PDD-022, PDD-023, PDD-024, PDD-025, PDD-028, PDD-029, PDD-030, PDD-033, PDD-058, PDD-095, PDD-096 | 3.3, 24.1, 27.1, 27.3, 28.1 | ownership, approval, override, privacy/security, human review, privileged action, signing, recall/retraction, and public trust records are case-bound |
| Substrate-residual verification | PDD-019, PDD-031, PDD-032, PDD-039, PDD-040, PDD-041, PDD-067, PDD-071, PDD-084, PDD-086 | 1.2, 4.1, 24.1, 27.2, 28.2, 29.2, 29.4, 40.1 | mode/fallback, replay, resilience, trusted fields, partial state, shared CAS, public export, environment provenance, tool transcript, and simulation boundaries remain enforced |
| Observability/orchestration static audit | PDD-017, PDD-018, PDD-045 | 3.2, 10.1, 14.1, 28.3, 40.1 | dormant capabilities, skip causality, and freshness/policy-time semantics are recorded with next diagnostic commands |
| Config/release/deployment/migration | PDD-072, PDD-075, PDD-076, PDD-079, PDD-080, PDD-081, PDD-082 | 27.3, 28.4, 40.1 | deployment parity, release/supply chain, persisted-state migration, quarantine/shim lifecycle, generated-surface drift, runbooks, retention/deletion/replay are case evidence |
| External/plugins/dependencies | PDD-073, PDD-085, PDD-102 | 12.3, 27.3, 28.5, 40.1 | connector acquisition, plugin capability isolation, dependency rights, provider/source risk, and external evidence provenance are enforced |
| Client surfaces static audit | PDD-089, PDD-091, PDD-092, PDD-093, PDD-094 | 3.1, 24.1, 28.5, 40.1 | offline mutations, collaboration attribution, assistant/composer provenance, bureaucratic rendering/export, and client persistence/privacy cannot mint authority |

## Wave 0 - Baseline Current Policy Run Evidence

Purpose: freeze the current policy-design false-pass surface before changing
runtime behavior.

Parallel phases in this wave:

### Phase 0.1 - Baseline Snapshot

- [x] Run the latest deterministic matrix and readiness without changing code.
- [x] Capture whether current serious runs produce a Policy Design Case, intent envelope, capability ledger, concept spine, producer refs, portfolio refs, and claim arguments.
- [x] Record baseline artifacts under `_build/policy-design-case/rebaseline/wave-0/`.
- [x] Record all missing evidence as typed baseline gaps, not as failures to hide.

### Wave 0 Exit Fence

- [x] Baseline artifacts exist under `_build/policy-design-case/rebaseline/wave-0/`.
- [x] The baseline records current false-pass and missing-evidence behavior without code changes.

### Wave 0 Baseline Artifact Index

Recorded on 2026-05-17. These are generated baseline artifacts and are not
runtime authority. They freeze the current false-pass surface for later waves.

Repo-root artifact directory:
`_build/policy-design-case/rebaseline/wave-0/`

Primary baseline artifacts:

- Coverage summary: [`coverage.md`](../../../_build/policy-design-case/rebaseline/wave-0/coverage.md)
- Machine-readable coverage and typed gaps: [`coverage.json`](../../../_build/policy-design-case/rebaseline/wave-0/coverage.json)
- Deterministic matrix run: [`deterministic_matrix.json`](../../../_build/policy-design-case/rebaseline/wave-0/deterministic_matrix.json)
- Readiness output: [`readiness.json`](../../../_build/policy-design-case/rebaseline/wave-0/readiness.json)
- Strict readiness output: [`readiness_require_passing.json`](../../../_build/policy-design-case/rebaseline/wave-0/readiness_require_passing.json)
- Policy Design Case sample placeholder proving absence: [`policy_design_case_sample.json`](../../../_build/policy-design-case/rebaseline/wave-0/policy_design_case_sample.json)
- Typed baseline gaps only: [`baseline_gaps.json`](../../../_build/policy-design-case/rebaseline/wave-0/baseline_gaps.json)
- No-prior-baseline diff: [`diff_from_wave_N_minus_1.json`](../../../_build/policy-design-case/rebaseline/wave-0/diff_from_wave_N_minus_1.json)
- Operator root-cause sample: [`operator_root_cause_sample.md`](../../../_build/policy-design-case/rebaseline/wave-0/operator_root_cause_sample.md)
- Commands and setup gaps: [`commands.json`](../../../_build/policy-design-case/rebaseline/wave-0/commands.json)

Fresh serious bundle captured by Wave 0:

- `_build/policy-design-case/rebaseline/wave-0/canary_evidence/profile-research__provider-simulated__data-canonical_production__scenario-public_golden__ui-api_only/20260517T071340Z_4256579c38a049a2b6661c48aece096b/`

Wave 0 baseline conclusion for downstream phases:

- Current deterministic serious lane, scorecard, readiness, and
  `--require-passing` readiness pass.
- Required Policy Design Case families are absent or only generic/non-PDC
  partial evidence: Policy Design Case, intent envelope, capability ledger,
  concept spine, producer refs, portfolio refs, and claim arguments.
- Missing coverage/rebaseline tools are recorded as typed setup gaps, not
  hidden failures.

## Wave 1 - Contract Fixtures, Red Controls, Reuse Map, Ownership, And Tool Skeletons

Purpose: prepare independent contract surfaces after the baseline is frozen.

Parallel phases in this wave:

### Phase 1.1 - Freeze Contract Fixtures

- [x] Create minimal JSON fixtures for each accepted ADR 0156-0161 contract.
- [x] Include one passing fixture and one failing fixture for every contract.
- [x] Add fixture docs explaining which SDD record family each fixture covers.
- [x] Ensure fixtures contain runtime authority envelopes and cannot pass through static inventory alone.

### Phase 1.2 - Add Red Tests For Known Policy-Design False Passes

- [x] Add failing tests for a serious run with no Policy Design Case.
- [x] Add failing tests for missing intent envelope and missing capability ledger.
- [x] Add failing tests for producer evidence accepted from static inventory, local path, or narrative citation.
- [x] Add failing tests for a final major claim with no portfolio and no accepted deficit.
- [x] Add failing tests for a final major claim with refs but no argument/warrant/rebuttal/deficit.
- [x] Add failing tests for a warrant that requires explanation reliability but lacks BERL refs.

### Phase 1.3 - Capability Realization Reuse Map

- [x] Generate a machine-readable reuse map from the SDD Capability Realization Map.
- [x] Mark every target capability as `wire-existing`, `extend-existing`, `consolidate-existing`, or `build-new`.
- [x] Fail the map if a planned `build-new` item overlaps runtime quality, Data Forge, Scholar, Foundry consensus/equivalence, Scientist DOE/discovery, IR analytics, BERL, DDM, core governance, or core audit without rejected-reuse evidence.
- [x] Add one repo-quality test that rejects missing reuse classification.

### Phase 1.4 - Ownership Skeleton And Decision Log

- [x] Create `docs/system-design-decisions/policy-design-case-decision-log.md`.
- [x] Add owners for every target contract and every ADR 0156-0161 proof obligation.
- [x] Import unresolved SDD open questions and assign revisit waves.
- [x] Add a decision-log row for any known temporary exception.

### Phase 1.5 - Coverage Dashboard Skeleton

- [x] Add `build_policy_design_case_coverage.py` with baseline-only output.
- [x] Add `check_policy_design_case_drift.py` with initial reuse and no-parallel-case checks.
- [x] Add `compare_policy_design_case_rebaseline.py` with typed `no_prior_baseline` output.
- [x] Wire generated output paths under `_build/policy-design-case/`.

### Wave 1 Exit Fence

- [x] Red tests fail for the intended reason before implementation.
- [x] Reuse map covers every target capability.
- [x] Decision log exists and has revisit waves.
- [x] Coverage dashboard can run in baseline mode.
- [x] No phase in this wave consumes another phase's generated output.
- [x] No new ADR or SDD wording weakens ADR-0147 through ADR-0161.

Wave 1 closeout evidence:

- Phase 1.2 red controls are retained as strict expected failures in
  `tests/unit/runtime/quality/test_policy_design_case_false_passes.py` with
  decision-log owner and revisit waves in `DL-PDC-0005`.
- `architecture/policy_design_case/capability_reuse_map.json` covers all 27
  SDD Capability Realization Map targets and rejects missing reuse
  classification or unsafe `build-new` overlap.
- `docs/system-design-decisions/policy-design-case-decision-log.md` owns every
  target contract, every ADR 0156-0161 proof obligation, all 29 imported SDD
  open questions, and known temporary exceptions.
- `tools/quality/validation/build_policy_design_case_coverage.py` runs in
  `baseline_only` mode with outputs under `_build/policy-design-case/`.
- Wave 1 tools read only source documents, committed maps, Wave 0 baselines, or
  runtime source trees; no Wave 1 phase depends on another Wave 1 phase's
  generated `_build` output.
- ADR-0147 through ADR-0161 remain accepted and the Wave 1 SDD/decision-log
  wording preserves their authority instead of relaxing it.

## Wave 2 - Policy Design Case Runtime Profile

Purpose: make the Policy Design Case a runtime quality profile before any
pre-routing, producer, or claim contracts extend it.

Parallel phases in this wave:

### Phase 2.1 - Policy Design Case Runtime Profile

- [x] Extend `src/polisyos/runtime/quality/assurance_case.py` with Policy Design Case profile metadata.
- [x] Add case node types for policy intent, capability duty, concept spine, producer evidence, portfolio, claim, argument, warrant, rebuttal, counter-evidence, and deficit.
- [x] Reserve additive node families for later oversight effectiveness, lifecycle event, audit attestation, publication trust, run-cost proportionality, ex-post outcome, calibration, and formal invariant records.
- [x] Preserve existing substrate assurance-case behavior; do not fork another case model.
- [x] Add tests that fail when a case is created outside the runtime quality authority chain.

### Wave 2 Exit Fence

- [x] ADR-0156 profile red tests pass.
- [x] Runtime-quality owns the Policy Design Case profile.
- [x] Governance, lifecycle, audit, publication, cost, ex-post, calibration, and invariant node families can be added later without breaking existing case fixtures.
- [x] Drift detector rejects a parallel case authority.

Wave 2 closeout evidence:

- Runtime record: `policyos.runtime.policy_design_case.v1` profile emitted by
  `src/polisyos/runtime/quality/assurance_case.py` with runtime-quality owner,
  runtime event ref, CAS ref, same-input closure ref, effective-mode ref, schema
  compatibility ref, and tenant scope.
- Node registry: core node types cover policy intent, capability duty, concept
  spine, producer evidence, portfolio, claim, argument, warrant, rebuttal,
  counter-evidence, and deficit; reserved additive families cover oversight
  effectiveness, lifecycle event, audit attestation, publication trust,
  run-cost proportionality, ex-post outcome, calibration, and formal invariant.
- Negative tests: `test_policy_design_case_profile_rejects_cases_outside_runtime_quality_authority_chain`
  and `test_serious_scorecard_blocks_when_policy_design_case_is_missing`.
- Positive tests: `test_policy_design_case_profile_metadata_is_runtime_quality_owned`,
  `test_policy_design_case_profile_requires_runtime_quality_authority_chain`,
  and existing assurance-case/scorecard unit suites.
- Commands run:
  - `uv run pytest tests/unit/runtime/quality -q`
  - `uv run pytest tests/repo_quality/tools/test_policy_design_case_drift.py -q`
  - `uv run python tools/quality/validation/check_policy_design_case_drift.py --repo-root .`
  - `uv run ruff check --select I,RUF022 src/polisyos/runtime/quality/assurance_case.py src/polisyos/runtime/quality/__init__.py src/polisyos/runtime/quality/scorecard.py tests/_helpers/hds_quality.py tests/unit/runtime/quality/test_assurance_case.py tests/unit/runtime/quality/test_policy_design_case_false_passes.py tests/unit/runtime/quality/test_scorecard.py`

## Wave 3 - Intent, Capability, And Minimum Record Registry

Purpose: establish independent pre-routing contracts over the runtime case
profile.

Parallel phases in this wave:

### Phase 3.1 - Policy Intent Envelope

- [x] Implement intent envelope schema with requester preference and independent-analysis separation.
- [x] Materialize intent before Lex/Fabric/Scholar/Foundry/Scientist routing.
- [x] Add requester-capture risk fields and challenge-depth policy.
- [x] Add tests for missing jurisdiction, target population, policy time, data time, desired outcome, and requester-preferred conclusion.

### Phase 3.2 - Capability Selection Ledger

- [x] Implement capability duty records for Lex, Fabric, Scholar, Foundry, Scientist, compiler, review, publication, and audit.
- [x] Emit selected, skipped, blocked, and fallback duty states.
- [x] Convert silent skips into blockers or allowed-profile degradation records.
- [x] Add tests proving Scholar cannot be omitted silently when the capability ledger requires literature evidence.

### Phase 3.3 - Minimum Case Record Registry

- [x] Add a registry for the SDD minimum Policy Design Case record families.
- [x] Mark each family as required, profile-scoped, or not applicable with typed evidence.
- [x] Link every family to producer owner, reader owner, schema name, scorecard gate, readiness check, and next diagnostic command.
- [x] Add tests that readiness fails on missing owner or missing enforcement function.

Phase 3.3 closeout evidence:

- Runtime registry: `policyos.policy_design_case.record_registry.v1` emitted by
  `src/polisyos/runtime/quality/policy_design_case.py` with all 19 SDD
  minimum families and typed applicability evidence.
- Enforcement: scorecard gate `policy_design_case.minimum_record_registry`,
  readiness component `policy_design_case_record_registry`, and enforcement
  function
  `polisyos.runtime.quality.policy_design_case.validate_policy_design_case_record_registry_payload`.
- Negative tests:
  `test_minimum_record_registry_rejects_missing_owner`,
  `test_minimum_record_registry_rejects_missing_enforcement_function`,
  `test_policy_design_case_record_registry_missing_owner_fails_readiness`,
  and
  `test_policy_design_case_record_registry_missing_enforcement_function_fails_readiness`.
- Positive tests:
  `test_minimum_record_registry_covers_every_sdd_family_with_typed_evidence`
  and `test_minimum_record_registry_report_passes_for_default_rows`.
- Commands run:
  - `uv run pytest tests/unit/runtime/quality/test_policy_design_case_record_registry.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py::test_policy_design_case_record_registry_missing_owner_fails_readiness tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py::test_policy_design_case_record_registry_missing_enforcement_function_fails_readiness -q`
  - `uv run pytest tests/unit/runtime/quality/test_scorecard.py tests/unit/runtime/quality/test_assurance_case.py tests/unit/runtime/quality/test_policy_design_case_record_registry.py -q`
  - `uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q`
  - `uv run ruff check src/polisyos/runtime/quality/policy_design_case.py tests/unit/runtime/quality/test_policy_design_case_record_registry.py`
  - `uv run ruff check --select I,RUF022 src/polisyos/runtime/quality/policy_design_case.py src/polisyos/runtime/quality/scorecard.py src/polisyos/runtime/quality/__init__.py tools/ci/check_policyos_production_quality_best_in_class.py tests/unit/runtime/quality/test_policy_design_case_record_registry.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py`

### Wave 3 Exit Fence

- [x] ADR-0157 intent/capability red tests pass.
- [x] Serious runs can emit intent, capability, and record-registry blockers.
- [x] No phase in this wave depends on another phase in this wave.

Wave 3 closeout evidence:

- Runtime pre-routing materialization now emits `policy_intent_envelope`,
  `policy_design_capability_ledger`, and `policy_design_case` refs before
  Lex/Fabric/Scholar/Foundry/Scientist work.
- Intent envelope fail-closed tests cover missing jurisdiction, target
  population, policy time, data time, desired outcome, and requester-preferred
  conclusion; the NL pipeline blocks missing serious-run jurisdiction before
  Scientist workflow dispatch.
- Capability ledger tests cover schema-version fail-close, skipped duty blocker
  semantics, all required capability duty records, and the Scholar
  literature-evidence omission blocker.
- Minimum record registry tests cover schema-version fail-close, owner and
  enforcement-function readiness failures, typed applicability evidence, and
  scorecard/readiness links.
- Commands run:
  - `uv run pytest tests/unit/runtime/http/test_nl_pipeline_materialization.py -q`
  - `uv run pytest tests/unit/runtime/quality/test_policy_intent_envelope.py tests/unit/runtime/quality/test_assurance_case.py tests/unit/runtime/quality/test_policy_design_case_record_registry.py tests/unit/runtime/http/test_nl_pipeline_materialization.py tests/unit/runtime/quality/test_scorecard.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py::test_policy_design_case_record_registry_missing_owner_fails_readiness tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py::test_policy_design_case_record_registry_missing_enforcement_function_fails_readiness -q`

## Wave 4 - Authority Profile Mapping

Purpose: close requested policy authority, effective mode, validation profile,
and fallback semantics over the Wave 3 pre-routing records.

Parallel phases in this wave:

### Phase 4.1 - Authority Profile Mapping

- [x] Map research/governed/production policy authority to `core/contracts/control.py`, `core/governance/profiles.py`, and `runtime/quality/effective_mode.py`.
- [x] Add checks for requested profile, effective profile, validation profile, and fallback policy closure.
- [x] Add negative tests for dev/smoke/fixture mode leaking into serious closeout.

### Wave 4 Exit Fence

- [x] Requested, effective, validation, and fallback profiles are reconciled.
- [x] Drift detector rejects a second profile taxonomy.

Wave 4 reference artifacts for later waves:

- [Phase 4.1 acceptance packet](../../../_build/policy-design-case/rebaseline/wave-4/phase_4_1_acceptance_packet.md) - scope, tests, enforcement hooks, and exit evidence.
- [Policy Design Case sample](../../../_build/policy-design-case/rebaseline/wave-4/policy_design_case_sample.json) - real runtime PDC sample with closed authority profile.
- [Deterministic matrix](../../../_build/policy-design-case/rebaseline/wave-4/deterministic_matrix.json) - passing Wave 4 canary lane and bundle path.
- [Readiness snapshot](../../../_build/policy-design-case/rebaseline/wave-4/readiness.json) and [rebaseline diff](../../../_build/policy-design-case/rebaseline/wave-4/diff_from_wave_N_minus_1.json) - formal closeout status.
- [DL-PDC-0006](../../system-design-decisions/policy-design-case-decision-log.md#dl-pdc-0006---wave-4-canonical-authority-profile-closure) - canonical authority profile closure decision.

## Wave 5 - Initial Scorecard And Readiness Enforcement

Purpose: make the runtime case, intent, capability, registry, and authority
profile mandatory for serious policy closeout.

Parallel phases in this wave:

### Phase 5.1 - Initial Scorecard And Readiness Enforcement

- [x] Update scorecard/readiness to require Policy Design Case identity for serious policy runs.
- [x] Fail on missing intent envelope, missing capability ledger, missing profile closure, missing case registry entry, or parallel case authority.
- [x] Preserve deterministic canary closeout semantics from the honest diagnostics substrate.

### Wave 5 Exit Fence

- [x] Serious runs cannot close without case profile, intent envelope, capability ledger, registry, and profile/effective-mode closure.
- [x] Coverage dashboard shows runtime case and intent/capability gate coverage.

## Wave 6 - Walking Skeleton Case Contract

Purpose: prove the vertical Policy Design Case ref path before the full domain
record families are built.

Parallel phases in this wave:

### Phase 6.1 - Walking Skeleton Case Contract

- [x] Build a minimal research-profile case fixture that flows through intent, stub concept ref, stub jurisdiction ref, one stub producer evidence record, one major claim, and one accepted `single_line_evidence_deficit`.
- [x] Ensure every skeleton record carries runtime authority envelope, CAS ref, diagnostic event ref, schema compatibility, effective-mode ref, and same-input closure ref.
- [x] Keep the skeleton explicitly non-production: governed and production profiles must reject the accepted deficit.
- [x] Add tests proving the skeleton cannot pass through static inventory, local paths, public export, dashboard state, or bundle-local refs.

### Wave 6 Exit Fence

- [x] A minimal case can carry refs from intent to stub evidence to claim without using real domain producers.
- [x] Governed and production profiles reject the skeleton's accepted single-line deficit.
- [x] The skeleton proves `assurance_case.py` extension compatibility before domain layers are built.

## Wave 7 - Walking Skeleton Readiness Smoke

Purpose: exercise scorecard/readiness against the walking skeleton before the
plan invests in full producer, portfolio, and claim families.

Scope note: Wave 7 uses the focused walking-skeleton readiness smoke at
`tools/quality/validation/check_policy_design_case_walking_skeleton.py`. It
does not require the stub-only walking skeleton to become a selected serious
bundle for `tools/ci/check_policyos_production_quality_best_in_class.py`; the
main readiness aggregator is hardened by later domain gates and proven against
real-domain evidence in Waves 36-40.

Parallel phases in this wave:

### Phase 7.1 - Walking Skeleton Readiness Smoke

- [x] Add a deterministic walking-skeleton closeout command or fixture-driven test that runs scorecard/readiness over the Wave 6 case.
- [x] Assert research profile returns an honest pass-or-deficit outcome with all refs present.
- [x] Assert governed and production profiles fail with typed deficit and missing-domain-evidence blockers.
- [x] Record `_build/policy-design-case/rebaseline/wave-7/walking_skeleton_readiness.json`.

### Wave 7 Exit Fence

- [x] The end-to-end ref path `intent -> stub spine -> stub producer -> claim -> scorecard/readiness` is proven.
- [x] The walking skeleton exposes integration failures before full domain implementation continues.
- [x] No real producer, portfolio, or governance record family is treated as implemented by the skeleton.

## Wave 8 - Concept And Jurisdiction Spine Roots

Purpose: create the independent concept and jurisdiction roots that later
reconciliation and producers will consume.

Parallel phases in this wave:

### Phase 8.1 - Per-Run Concept Spine

- [x] Project a per-run concept spine over Fabric entity resolution, Scientist cross-graph, IR linker, IR registry, and IR world.
- [x] Record canonical concept ids, aliases, source terms, metric bindings, dataset/column bindings, legal concept bindings, method requirement bindings, objective/tradeoff bindings, geography, population, time, units, currency, and calendars.
- [x] Add blockers for unresolved or conflicting concepts.

### Phase 8.2 - Jurisdiction Spine

- [x] Project a jurisdiction spine over Lex, IR normative arbitration, and cross-graph conflict surfaces.
- [x] Record supranational, national, regional, and local authority levels; temporal validity; competence; hierarchy; delegation; pre-emption; and unresolved conflicts.
- [x] Add multi-jurisdiction fixtures and blockers for unresolved competence.

### Wave 8 Exit Fence

- [x] Concept spine and jurisdiction spine exist independently or emit typed blockers.
- [x] No phase in this wave consumes another phase in this wave.

## Wave 9 - Ontology Reconciliation And Normalization Trace

Purpose: reconcile concept and jurisdiction roots into one per-run semantic
closure.

Parallel phases in this wave:

### Phase 9.1 - Ontology Reconciliation And Normalization Trace

- [x] Implement reconciliation trace for metric, dataset, legal, method, objective, and claim concepts.
- [x] Add a normalization trace from raw user terms to canonical concept refs.
- [x] Add tests for synonym collision, unit mismatch, geography mismatch, time mismatch, and legal concept mismatch.

### Wave 9 Exit Fence

- [x] ADR-0158 reconciliation red tests pass.
- [x] Raw user terms map to canonical concept refs or typed blockers.

## Wave 10 - Spine Consumer Semantics And Producer Interfaces

Purpose: expose the reconciled spine to numerical semantics and producers.

Parallel phases in this wave:

### Phase 10.1 - Numeric, Time, Geography, And Calendar Semantics

- [x] Bind unit, currency, price base, exchange rate, inflation adjustment, geography, calendar, and freshness semantics into the concept spine.
- [x] Add claim-level numerical semantics refs.
- [x] Add tests for claims that mix incompatible units, currencies, geography levels, or time bases.

### Phase 10.2 - Producer Spine Interfaces

- [x] Add read interfaces so Lex, Fabric, Scholar, Foundry, Scientist, and compiler code can consume spine refs.
- [x] Require producers to return candidate bindings or blockers rather than local-only labels.
- [x] Add tests proving final claims cannot consume evidence with a mismatched spine ref.

### Wave 10 Exit Fence

- [x] Producers can consume previous-wave spine refs.
- [x] Numerical semantics can be attached to claim refs.
- [x] No phase in this wave consumes another phase in this wave.

## Wave 11 - Spine Scorecard And Readiness Gates

Purpose: enforce spine closure before producer evidence can satisfy serious
policy authority.

Parallel phases in this wave:

### Phase 11.1 - Spine Scorecard And Readiness Gates

- [x] Fail scorecard/readiness on concept mismatch, jurisdiction mismatch, unit mismatch, period mismatch, geography mismatch, and local-concept leakage.
- [x] Add operator diagnostics with missing input, conflicting producer, affected claim, and next command.

### Wave 11 Exit Fence

- [x] Scorecard/readiness fail on spine mismatch.
- [x] Producers may begin binding evidence to stable spine refs.

Wave 11 implementation packet:

- Runtime record: `semantic_binding_ledger` now carries producer spine
  concept, jurisdiction, unit, period, and geography refs.
- Scorecard gate: `semantic_binding_ledger_valid` emits blocking failures for
  mismatched spine dimensions and local-concept leakage.
- Readiness gate: persisted serious bundles are re-read from
  `quality_evidence/semantic_binding_ledger.json`, so a stale pass scorecard
  cannot hide a spine mismatch.
- Negative tests:
  `tests/unit/runtime/quality/test_semantic_binding.py::test_scorecard_blocks_spine_dimension_mismatches_with_operator_diagnostics`
  and
  `tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py::test_readiness_serious_bundle_fails_stale_scorecard_on_spine_mismatch`.
- Positive commands:
  `uv run pytest tests/unit/runtime/quality/test_semantic_binding.py tests/unit/runtime/quality/test_scorecard.py -q`
  and
  `uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q`.

## Wave 12 - Producer Root Evidence Contracts

Purpose: make independent producer evidence real, scenario-relevant, and
runtime-owned.

Parallel phases in this wave:

### Phase 12.1 - Lex Legal Authority Retrieval

- [x] Wire Lex retrieval to emit legal corpus snapshot, query terms, concept refs, jurisdiction/time filters, candidate norms, selected norms, rejected norms, conflicts, competence, and blockers.
- [x] Distinguish `no_relevant_norm_found` from retrieval failure and missing store.
- [x] Add tests for legal-shaped payload without retrieval and wrong-jurisdiction norm false pass.

### Phase 12.2 - Data Forge Snapshot And Read-API Binding

- [x] Bind runtime evidence to Data Forge snapshot manifests, quality gates, artifact ids, and read-API surfaces.
- [x] Cover legal, catalog, academic, and domain data snapshots.
- [x] Add tests for local path substitution, missing snapshot id, stale snapshot, and missing quality gate.

### Phase 12.3 - Scholar Academic And Grey-Literature Evidence

- [x] Emit research intent, query graph, provider traces, source scoring, snippets, citations, freshness, corpus lineage, selected and rejected sources, support/conflict links, and literature-deficit blockers.
- [x] Mark academic source-family independence tags.
- [x] Add tests for narrative citation without Scholar provenance and stale literature freshness.

### Phase 12.4 - Foundry Method Selection And Analytical Validity

- [x] Emit candidate method families, selected methods, rejected methods, assumptions, identification requirements, uncertainty, sensitivity, missingness handling, transportability limits, specification space, and method-result refs.
- [x] Wire IR identification, transportability, partial identification, recoverability, causal ensemble, falsification, and certificate/proof surfaces selected by the method-validity registry.
- [x] Add tests for method chosen after execution and generic simulation false pass.

### Phase 12.5 - Options, Objectives, Welfare, And Tradeoffs

- [x] Emit baseline/no-action option, candidate options, rejected options, objective function, tradeoff weights, social weights, welfare bounds, distributional effects, qualitative effects, risk, and uncertainty.
- [x] Reuse Foundry welfare/uncertainty and IR distributional/fairness/mobility/welfare analytics.
- [x] Add tests for final recommendation without baseline, rejected options, or objective/tradeoff refs.

### Wave 12 Exit Fence

- [x] Lex, Data Forge, Scholar, Foundry, and option/objective producers emit runtime-owned evidence or blockers.
- [x] No producer in this wave consumes another producer's output from this wave.

## Wave 13 - Fabric Source Evidence And Field Lineage

Purpose: bind Fabric field-level source evidence to the Data Forge snapshot
identity produced in Wave 12.

Parallel phases in this wave:

### Phase 13.1 - Fabric Source Evidence And Field Lineage

- [x] Emit source family, source rights, dataset, dictionary, schema, fields, units, geography, time coverage, quality, missingness, freshness, lineage, transformations, selected candidates, rejected candidates, and data-gap blockers.
- [x] Bind derived features to source facets and claim-support features.
- [x] Add tests for manifest-role false pass and data-present-but-irrelevant pass.

### Wave 13 Exit Fence

- [x] Fabric evidence consumes previous-wave Data Forge refs.
- [x] Field-level lineage and derived-feature refs are claim-bindable.

## Wave 14 - Producer Scorecard And Readiness Gates

Purpose: enforce producer evidence before portfolio and claim work can use it.

Parallel phases in this wave:

### Phase 14.1 - Producer Scorecard And Readiness Gates

- [x] Fail scorecard/readiness when final claims use legal, data, literature, method, or objective evidence without producer-owned runtime refs.
- [x] Fail on static inventory substitution, local file refs, missing selected/rejected candidates, missing source rights, missing freshness, missing quality, missing snapshot identity, and missing blockers.

### Wave 14 Exit Fence

- [x] ADR-0159 red tests pass.
- [x] Scorecard/readiness reject static-only producer maps.
- [x] Coverage dashboard shows producer contract runtime evidence moving toward final targets.

Wave 14 closeout evidence:

- [Wave 14 coverage](../../../_build/policy-design-case/rebaseline/wave-14/coverage.json) and [coverage summary](../../../_build/policy-design-case/rebaseline/wave-14/coverage.md) record the producer contract runtime evidence gates.
- [Wave 14 readiness](../../../_build/policy-design-case/rebaseline/wave-14/readiness.json) is tied to the fresh serious bundle and fails closed on the blocking scorecard gates, rather than projecting static readiness.
- [Wave 14 deterministic matrix](../../../_build/policy-design-case/rebaseline/wave-14/deterministic_matrix.json) executed the serious lane and failed on the scorecard. This is the intended honest blocker while producer-owned runtime evidence is incomplete.
- [Wave 14 sample](../../../_build/policy-design-case/rebaseline/wave-14/policy_design_case_sample.json), [diff](../../../_build/policy-design-case/rebaseline/wave-14/diff_from_wave_N_minus_1.json), [operator root cause sample](../../../_build/policy-design-case/rebaseline/wave-14/operator_root_cause_sample.md), and [commands](../../../_build/policy-design-case/rebaseline/wave-14/commands.json) complete the wave rebaseline packet.

Wave 14 rebaseline shortlinks for later phases:

| Shortlink | Artifact |
| --- | --- |
| `W14-COVERAGE` | [coverage.json](../../../_build/policy-design-case/rebaseline/wave-14/coverage.json) |
| `W14-COVERAGE-MD` | [coverage.md](../../../_build/policy-design-case/rebaseline/wave-14/coverage.md) |
| `W14-READINESS` | [readiness.json](../../../_build/policy-design-case/rebaseline/wave-14/readiness.json) |
| `W14-MATRIX` | [deterministic_matrix.json](../../../_build/policy-design-case/rebaseline/wave-14/deterministic_matrix.json) |
| `W14-SAMPLE` | [policy_design_case_sample.json](../../../_build/policy-design-case/rebaseline/wave-14/policy_design_case_sample.json) |
| `W14-DIFF` | [diff_from_wave_N_minus_1.json](../../../_build/policy-design-case/rebaseline/wave-14/diff_from_wave_N_minus_1.json) |
| `W14-RCA` | [operator_root_cause_sample.md](../../../_build/policy-design-case/rebaseline/wave-14/operator_root_cause_sample.md) |
| `W14-COMMANDS` | [commands.json](../../../_build/policy-design-case/rebaseline/wave-14/commands.json) |

## Wave 15 - Evidence Portfolio Design Contract

Purpose: predeclare the claim portfolio before evidence lines and execution
results can be accepted.

Parallel phases in this wave:

### Phase 15.1 - Evidence Portfolio Design Contract

- [x] Implement portfolio design records per major claim and strand.
- [x] Record strands, authority level, candidate data/source families, candidate method families, defensible specification space, inclusion/exclusion rules, disconfirming lines, synthesis rules, stopping rules, and cost/proportionality.
- [x] Fail if portfolio design is created after producer execution without an accepted exception.

### Wave 15 Exit Fence

- [x] Portfolio design is predeclared for major claims or blocked by authority profile.

### Wave 15 Acceptance Packet

| Packet field | Evidence |
|--------------|----------|
| Scope | Phase 15.1, `evidence_portfolio_and_synthesis.v1`, runtime quality Policy Design Case scorecard/readiness/coverage for research, governed, and production authority profiles. |
| Reuse proof | Reuses `runtime/quality/scorecard.py`, Policy Design Case registry facets, coverage builder, and readiness aggregator; no parallel owner module was added. |
| Runtime evidence | `policyos.runtime.policy_design_case.evidence_portfolio_design.v1` schema plus `policy_design_case.evidence_portfolio_design.v1` contract id; serious bundle absence is typed in the Wave 15 sample. |
| Tests | Negative: `test_producer_acceptance_guard_requires_predeclared_portfolio_design`, `test_producer_acceptance_guard_rejects_post_hoc_design_without_exception`; positive: `test_producer_acceptance_guard_accepts_design_declared_before_execution`, `test_readiness_payload_exposes_wave15_portfolio_design_contract_component`. |
| Enforcement | Scorecard gate blocks missing/invalid/post-hoc major-claim portfolio designs; producer guard blocks evidence/result acceptance; coverage emits `portfolio_predeclaration_pct=100`; readiness emits `policy_design_evidence_portfolio_design_contract`. |
| Operator surface | Failure codes include `policy_design_major_claim_portfolio_missing` and `policy_design_portfolio_design_post_hoc`; operator next command is the Wave 15 evidence portfolio and false-pass test set. |
| Rebaseline | Wave 15 rebaseline generated coverage, readiness, deterministic matrix, sample, diff, commands, and root-cause artifacts under `_build/policy-design-case/rebaseline/wave-15/`. |
| Handoff | Wave 16 evidence lines must call the portfolio predeclaration guard before accepting evidence lines or producer execution results. |

| Artifact id | Artifact |
|-------------|----------|
| `W15-COVERAGE` | [coverage.json](../../../_build/policy-design-case/rebaseline/wave-15/coverage.json) |
| `W15-COVERAGE-MD` | [coverage.md](../../../_build/policy-design-case/rebaseline/wave-15/coverage.md) |
| `W15-READINESS` | [readiness.json](../../../_build/policy-design-case/rebaseline/wave-15/readiness.json) |
| `W15-MATRIX` | [deterministic_matrix.json](../../../_build/policy-design-case/rebaseline/wave-15/deterministic_matrix.json) |
| `W15-SAMPLE` | [policy_design_case_sample.json](../../../_build/policy-design-case/rebaseline/wave-15/policy_design_case_sample.json) |
| `W15-DIFF` | [diff_from_wave_N_minus_1.json](../../../_build/policy-design-case/rebaseline/wave-15/diff_from_wave_N_minus_1.json) |
| `W15-RCA` | [operator_root_cause_sample.md](../../../_build/policy-design-case/rebaseline/wave-15/operator_root_cause_sample.md) |
| `W15-COMMANDS` | [commands.json](../../../_build/policy-design-case/rebaseline/wave-15/commands.json) |

## Wave 16 - Evidence Line Model

Purpose: define the unit of portfolio evidence after portfolio design is fixed.

Parallel phases in this wave:

### Phase 16.1 - Evidence Line Model

- [x] Implement evidence line records as method/source/assumption/specification/producer/execution-context combinations.
- [x] Support legal, data, literature, method, simulation, distributional, feasibility, and monitoring strands.
- [x] Add tests for line records missing source lineage, method assumptions, specification id, or producer identity.

### Wave 16 Exit Fence

- [x] Evidence line records can bind to previous-wave portfolio designs.

## Wave 17 - Independence Map And Effective Independent Count

Purpose: collapse correlated evidence lines before multiverse, falsification,
and synthesis can interpret evidence strength.

Parallel phases in this wave:

### Phase 17.1 - Independence Map And Effective Independent Count

- [x] Reuse Foundry method consensus and equivalence to collapse equivalent methods.
- [x] Add source lineage, corpus ancestry, author/institution pool, preprocessing, assumptions, identification strategy, and shared failure-mode collapse.
- [x] Report raw evidence-line count and effective independent evidence count.
- [x] Add tests where 400 raw lines collapse to a small effective count.

### Wave 17 Exit Fence

- [x] Raw evidence count cannot be reported without effective independent evidence count.

## Wave 18 - Multiverse And Disconfirming Evidence

Purpose: run independent portfolio analyses that consume the predeclared
portfolio, evidence-line model, and independence map.

Parallel phases in this wave:

### Phase 18.1 - Multiverse And Specification Curve Projection

- [x] Project Scientist DOE, discovery, Foundry sensitivity, and backtesting outputs into specification-curve records.
- [x] Record defensible specifications, rejected specifications, result distribution, drivers of divergence, and fragile/robust claim markers.
- [x] Add tests for cherry-picked agreeing specifications.

### Phase 18.2 - Disconfirming Evidence And Falsification

- [x] Wire IR falsification report, adversarial plans, and severe-test records into disconfirming evidence ledgers.
- [x] Require disconfirming lines or an accepted deficit by profile.
- [x] Add tests for friendly-only portfolios and missing severe-test rationale.

### Wave 18 Exit Fence

- [x] Specification curves and disconfirming ledgers are generated independently from previous-wave refs.
- [x] No phase in this wave consumes another phase in this wave.

## Wave 19 - Evidence Synthesis, Certainty, And Stopping Rules

Purpose: synthesize multiverse and disconfirming evidence without hiding
divergence.

Parallel phases in this wave:

### Phase 19.1 - Evidence Synthesis, Certainty, And Stopping Rules

- [x] Implement synthesis report records with weighting, heterogeneity model, certainty framework, publication-bias treatment, inclusion/exclusion policy, and sensitivity to synthesis rules.
- [x] Add information-saturation stopping-rule result.
- [x] Connect synthesis to run-cost proportionality evidence.
- [x] Add tests for claim direction changing under reasonable synthesis rules.

### Wave 19 Exit Fence

- [x] Evidence disagreement is represented as divergence evidence or blocker.

## Wave 20 - Portfolio Scorecard And Readiness Gates

Purpose: enforce ADR-0160 after portfolio, evidence lines, independence,
multiverse, falsification, and synthesis exist.

Parallel phases in this wave:

### Phase 20.1 - Portfolio Scorecard And Readiness Gates

- [x] Fail scorecard/readiness on missing predeclared portfolio, missing independence map, missing effective count, missing specification curve, missing disconfirming ledger, missing synthesis report, missing stopping rule, and unaccepted single-line evidence.
- [x] Fail if post-hoc portfolio selection hides disagreeing lines.

### Wave 20 Exit Fence

- [x] ADR-0160 red tests pass.
- [x] Major claims can consume portfolio refs but cannot pass on one dataset and one method by default.
- [x] Coverage dashboard reports portfolio, independence, and synthesis coverage.

## Wave 21 - Claim Compiler Runtime Contract

Purpose: make final claims auditable assurance nodes after portfolio closeout.

Parallel phases in this wave:

### Phase 21.1 - Claim Compiler Runtime Contract

- [x] Update the claim compiler to mint major claims only as Policy Design Case assurance nodes.
- [x] Require claim id, assurance node id, concept refs, legal norm refs, source/data refs, Scholar refs or deficits, method refs, portfolio refs, independence refs, specification-curve refs, disconfirming refs, synthesis refs, objective/tradeoff refs, uncertainty refs, numerical semantics refs, and monitoring refs selected by the claim registry.
- [x] Add tests for prose backfill and missing producer refs.

### Wave 21 Exit Fence

- [x] Claims are minted only as runtime-owned Policy Design Case assurance nodes.

## Wave 22 - Argument, Warrant, Rebuttal, Counter-Evidence, And Deficit Nodes

Purpose: add explicit reasoning around claim refs after the claim node contract
is fixed.

Parallel phases in this wave:

### Phase 22.1 - Argument, Warrant, Rebuttal, Counter-Evidence, And Deficit Nodes

- [x] Add argument strategy and warrant records per major claim.
- [x] Add assumptions, applicability limits, rebuttal nodes, counter-evidence nodes, assurance deficits, requester-capture challenge result, and blockers.
- [x] Add SACM/CAE/GSN mapping or exporter surface.
- [x] Add tests for refs-without-warrant and hidden counter-evidence.

### Wave 22 Exit Fence

- [x] Major claims have explicit argument, warrant, rebuttal, counter-evidence, and deficit surfaces.

## Wave 23 - BERL Reliability And Pre-Publication Challenge

Purpose: attach independent challenge and explanation reliability to the
argument/warrant layer.

Parallel phases in this wave:

### Phase 23.1 - BERL Warrant Reliability Bridge

- [x] Wire BERL explanation bundles, validation thresholds, empirical bounds, and local infidelity diagnostics into warrant reliability records.
- [x] Require BERL refs when explanation reliability affects reviewer trust, automated claim acceptance, or user-facing confidence.
- [x] Add tests for missing BERL refs and failed BERL thresholds.

### Phase 23.2 - Pre-Publication Challenge And Requester-Capture Control

- [x] Wire Scientist policy-design adversary, critic, objectives, search, and backtesting adversarial outputs into challenge nodes.
- [x] Add requester-capture challenge that separates requester preferred conclusion from independent analysis.
- [x] Add tests where a case merely confirms requester prior without independent alternative analysis.

### Wave 23 Exit Fence

- [x] BERL reliability and requester-capture challenge can be produced independently from previous-wave argument refs.
- [x] No phase in this wave consumes another phase in this wave.

## Wave 24 - Final Artifact And Projection Semantics

Purpose: ensure user-facing outputs read authority without minting it.

Parallel phases in this wave:

### Phase 24.1 - Final Artifact And Projection Semantics

- [x] Ensure final artifacts, public exports, dashboard state, and API projections read the Policy Design Case and label draft, projection-only, redacted, stale, contested, blocked, or publishable states.
- [x] Preserve public export semantic meaning without exposing secrets, hidden answers, provider credentials, unsafe paths, or tenant-private sources.
- [x] Add tests proving projections cannot mint claim authority.

### Wave 24 Exit Fence

- [x] Dashboard/API/public projections cannot create authority.

## Wave 25 - Claim Scorecard And Research-Profile Case Gate

Purpose: enforce ADR-0161 and unlock real research-profile evidence for later
governance and behavioral diagnostics.

Parallel phases in this wave:

### Phase 25.1 - Claim Scorecard And Readiness Gates

- [x] Fail scorecard/readiness when a major claim lacks argument, warrant, rebuttal/counter-evidence assessment, accepted assurance deficit, BERL refs selected by authority profile, or required producer/portfolio refs.
- [x] Fail silent promotion of research deficits to governed or production authority.

### Wave 25 Exit Fence

- [x] ADR-0161 red tests pass.
- [x] A research-profile case can emit real domain evidence and honest deficits.
- [x] Final major claims are assurance-case nodes with arguments, warrants, rebuttals, counter-evidence, and blockers.

## Wave 26 - Second Governance ADR Pack

Purpose: accept governance, lifecycle, audit, proportionality, and formal
invariant decisions before implementation narrows them.

Parallel phases in this wave:

### Phase 26.1 - Second ADR Pack

- [x] Accept ADRs for human oversight/publication/external audit, lifecycle/DDM/ex-post/calibration, run cost/proportionality, and formal case invariants before implementation narrows those contracts.
- [x] Link the new ADRs from the SDD and this plan.
- [x] Update ADR index and docs lifecycle checks.

### Wave 26 Exit Fence

- [x] Second ADR pack is accepted and indexed.
- [x] Later governance work has explicit ADR authority.

## Wave 27 - Governance, Lifecycle, And External Audit Roots

Purpose: extend the research-profile case into independent governed-policy
record families.

Parallel phases in this wave:

### Phase 27.1 - Human Oversight, Independence, Consultation, And Legitimacy

- [x] Extend existing human review and value-of-information escalation with reviewer independence, exposure order, time spent, dissent, change requests, override, approve-without-change rate, and rubber-stamp risk.
- [x] Add producer independence and separation-of-duty attestations.
- [x] Add structured expert judgement records with elicitation method, expert provenance, conflicts, uncertainty, and explicit `judgement_not_data` classification.
- [x] Add consultation records with stakeholder map, consultation plan, public comment, objection records, response-to-comment reasoning, unresolved objection severity, and legitimacy blockers.
- [x] Add tests for nominal approval without effective oversight.
- [x] Add tests for expert judgement masquerading as observed data and stakeholder objections hidden from final claims.

### Phase 27.2 - DDM, Ex-Post Outcomes, Calibration, And Case Lifecycle

- [x] Add implementation contract, monitoring plan, and evaluation design records before publication authority.
- [x] Wire DDM shift/degradation/readiness/incident/root-cause events into monitoring records.
- [x] Wire continuous governance reissue, supersession, withdrawal, and validity reports into case lifecycle.
- [x] Wire calibration, backtesting, calibration leaderboard, and memory contamination checks into ex-post learning.
- [x] Link claim predictions to observed outcomes, reassessment status, and future method/uncertainty priors.
- [x] Add tests for stale published cases, missing DDM evidence, and contaminated learning.

### Phase 27.3 - Core Audit, PROV/SLSA, Standalone Verification, And Archive

- [x] Wire `core/audit` PROV JSON, SLSA assembler, verifier, standalone verifier template, and safe archive tooling into external audit records.
- [x] Add a public audit archive that can be verified without private operator context.
- [x] Add tests for missing PROV, missing SLSA, unsafe archive path, and unverifiable exported refs.

### Wave 27 Exit Fence

- [x] Governance, DDM, ex-post, calibration, audit, and public archive records are wired or blocked.
- [x] Structured judgement, consultation, implementation monitoring/evaluation, and human oversight records are wired or blocked.
- [x] No phase in this wave consumes another phase in this wave.

## Wave 28 - Pass 1B Hardening Evidence Records

Purpose: convert Pass 1B static hardening findings into independent case-bound
evidence records.

Parallel phases in this wave:

### Phase 28.1 - Tenant, CAS, Approval, And Governance Hardening

- [x] Bind tenant/CAS ownership, approval, override, privacy/security, human review, privileged action, signing, recall/retraction, and public trust records into the Policy Design Case for the Pass 1B rows that require them.
- [x] Add tests from PDD-022, PDD-023, PDD-024, PDD-025, PDD-028, PDD-029, PDD-030, PDD-033, PDD-058, PDD-095, and PDD-096.

### Phase 28.2 - Substrate-Residual Verification

- [x] Bind mode/fallback, replay, resilience, trusted fields, partial state, shared CAS, public export, environment provenance, tool transcript, and simulation-boundary records into the Policy Design Case.
- [x] Add tests from PDD-019, PDD-031, PDD-032, PDD-039, PDD-040, PDD-041, PDD-067, PDD-071, PDD-084, and PDD-086.

### Phase 28.3 - Observability And Orchestration Static Audit

- [x] Bind dormant capability, skip causality, and freshness/policy-time semantics records into the Policy Design Case.
- [x] Add tests from PDD-017, PDD-018, and PDD-045.

### Phase 28.4 - Config, Release, Deployment, And Migration Hardening

- [x] Bind deployment parity, release/supply chain, persisted-state migration, quarantine/shim lifecycle, generated-surface drift, runbook, retention/deletion, and replay records into the Policy Design Case.
- [x] Add tests from PDD-072, PDD-075, PDD-076, PDD-079, PDD-080, PDD-081, and PDD-082.

### Phase 28.5 - External, Plugin, Dependency, And Client Surface Hardening

- [x] Bind connector acquisition, plugin capability isolation, dependency rights, provider/source risk, external evidence provenance, offline mutation, collaboration attribution, assistant/composer provenance, bureaucratic rendering/export, and client persistence/privacy records.
- [x] Add tests from PDD-073, PDD-085, PDD-102, PDD-089, PDD-091, PDD-092, PDD-093, and PDD-094.

### Wave 28 Exit Fence

- [x] Every Pass 1B hardening group has an implemented or blocked record family.
- [x] No phase in this wave consumes another phase in this wave.

## Wave 29 - Integrity Threat Model, Self-FMEA, Maturity, And Formal Invariants

Purpose: make integrity, failure-mode, maturity, and invariant evidence
first-class without depending on other Wave 29 phases.

Parallel phases in this wave:

### Phase 29.1 - Evidence-Graph Threat Model

- [x] Add evidence-graph threat model records for prompt injection, poisoned datasets, stale indexes, malicious tenants, forged provenance, compromised plugins, local-client leakage, and insider mutation.
- [x] Add tests for missing threat model records on serious cases.

### Phase 29.2 - Non-Adversarial Self-FMEA And Partial-State Contradictions

- [x] Add non-adversarial self-FMEA records for schema migration errors, partial case graphs, contradictory records, stale generated surfaces, operator workarounds, and box-ticking failure.
- [x] Add partial-state contradiction checks that block cases with mutually inconsistent authoritative records.
- [x] Add tests for self-FMEA missing for serious case records and partial-state contradiction false pass.

### Phase 29.3 - Case Maturity Profile

- [x] Add record-family maturity profile using `missing`, `stub`, `partial`, `argument_complete`, `evidence_complete`, `independently_challenged`, `externally_auditable`, and `validated_ex_post`.
- [x] Add tests for maturity inflated without evidence.

### Phase 29.4 - Formal Invariant Specs

- [x] Add formal or lightweight model-checked invariant specs for authority ordering, phase barriers, same-input closure, CAS/event reconciliation, and terminal readiness.
- [x] Add tests for formal-spec coverage regression.

### Wave 29 Exit Fence

- [x] Integrity threat model, self-FMEA, maturity, and formal invariant records are wired or blocked.
- [x] No phase in this wave consumes another phase in this wave.

## Wave 30 - Run-Cost Proportionality Ledger

Purpose: consolidate the cost of evidence production before benchmarking can
claim best-in-class behavior.

Parallel phases in this wave:

### Phase 30.1 - Run-Cost Proportionality Ledger

- [x] Consolidate runtime performance budgets, Foundry cost model, Scientist budgets, DOE/search budgets, provider cost, elapsed time, and human-review burden into a run-cost proportionality ledger.
- [x] Add evidence-depth budget rules tied to authority level, public impact, observed heterogeneity, effective independence, and stopping rule.
- [x] Add tests for high-cost low-impact runs without proportionality evidence.

### Wave 30 Exit Fence

- [x] Run cost and evidence-depth budgets are case records or typed blockers.

### Wave 30 Acceptance Packet

| Packet field | Evidence |
|--------------|----------|
| Scope | Phase 30.1, `best_in_class_benchmarking.v1` cost/proportionality facets, runtime quality Policy Design Case scorecard/readiness/coverage for serious authority profiles. |
| Reuse proof | Reuses `runtime/quality/performance_budget.py`, Foundry method cost, provider quality ledger, human-review calibration, policy synthesis stopping rules, `runtime/quality/scorecard.py`, and the Policy Design Case registry; no parallel cost authority module was added. |
| Runtime evidence | `policyos.runtime.policy_design_case.run_cost_proportionality_ledger.v1` schema plus `policy_design_case.run_cost_proportionality_ledger.v1` contract id; `build_run_cost_proportionality_ledger_from_quality_context` projects missing ledgers from runtime quality context. |
| Tests | Negative: `test_high_cost_low_impact_run_requires_proportionality_evidence`, `test_evidence_depth_budget_blocks_shallow_stop_under_required_depth`, `test_policy_design_case_blocks_high_cost_low_impact_without_proportionality`; positive: `test_run_cost_ledger_consolidates_cost_and_evidence_depth_budgets`, `test_run_cost_ledger_is_projected_from_runtime_quality_context`, `test_assemble_canary_evidence_projects_wave30_run_cost_ledger`, `test_readiness_payload_exposes_wave30_run_cost_proportionality_component`. |
| Enforcement | Scorecard gate `policy_design_wave30_run_cost_proportionality` blocks missing/invalid ledgers, high-cost low-impact runs without proportionality evidence, budget overruns without accepted changes, and evidence-depth under-budget stops; typed blockers can satisfy the exit fence only as blocking records. |
| Operator surface | Failure codes include `policy_design_run_cost_proportionality_ledger_missing`, `policy_design_run_cost_high_cost_low_impact_without_proportionality`, `policy_design_run_cost_evidence_depth_under_budget`, and `policy_design_run_cost_budget_overrun_change_record_missing`; operator next command is the Wave 30 run-cost and false-pass test set. |
| Rebaseline | Wave 30 rebaseline generated coverage, readiness, deterministic matrix, sample, diff, commands, and root-cause artifacts under `_build/policy-design-case/rebaseline/wave-30/`. The fresh deterministic matrix still fails on downstream serious-scorecard blockers, while the Wave 30 readiness component is `pass`. |
| Handoff | Wave 31 benchmarking records may consume Wave 30 `run_cost_ledger_refs` and `proportionality_evidence_refs`; Wave 31 remains responsible for benchmark evidence itself. |

| Artifact id | Artifact |
|-------------|----------|
| `W30-COVERAGE` | [coverage.json](../../../_build/policy-design-case/rebaseline/wave-30/coverage.json) |
| `W30-COVERAGE-MD` | [coverage.md](../../../_build/policy-design-case/rebaseline/wave-30/coverage.md) |
| `W30-READINESS` | [readiness.json](../../../_build/policy-design-case/rebaseline/wave-30/readiness.json) |
| `W30-MATRIX` | [deterministic_matrix.json](../../../_build/policy-design-case/rebaseline/wave-30/deterministic_matrix.json) |
| `W30-SAMPLE` | [policy_design_case_sample.json](../../../_build/policy-design-case/rebaseline/wave-30/policy_design_case_sample.json) |
| `W30-DIFF` | [diff_from_wave_N_minus_1.json](../../../_build/policy-design-case/rebaseline/wave-30/diff_from_wave_N_minus_1.json) |
| `W30-RCA` | [operator_root_cause_sample.md](../../../_build/policy-design-case/rebaseline/wave-30/operator_root_cause_sample.md) |
| `W30-COMMANDS` | [commands.json](../../../_build/policy-design-case/rebaseline/wave-30/commands.json) |

## Wave 31 - Best-In-Class Benchmarking Records

Purpose: make "best in class" falsifiable after cost and evidence-depth budgets
exist.

Parallel phases in this wave:

### Phase 31.1 - Best-In-Class Benchmarking Records

- [x] Add best-in-class benchmarking records for external audit pass rate, human-team benchmark, reversal/retraction metrics, calibration metrics, claim substantiation, triangulation, and operator time-to-root-cause.
- [x] Add tests for best-in-class claims without benchmark evidence.

### Wave 31 Exit Fence

- [x] Benchmarking records can consume previous-wave cost and proportionality refs.

### Wave 31 Acceptance Packet

| Packet field | Evidence |
|--------------|----------|
| Scope | Phase 31.1, `best_in_class_benchmarking.v1`, runtime quality Policy Design Case scorecard/readiness/coverage for falsifiable best-in-class claims after Wave 30 cost/proportionality evidence. |
| Reuse proof | Reuses `runtime/quality/scorecard.py`, Wave 30 `run_cost_proportionality_ledger` refs, Policy Design Case registry facets, coverage builder, and readiness aggregator; no parallel benchmark authority module was added. |
| Runtime evidence | `policyos.runtime.policy_design_case.best_in_class_benchmarking.v1` schema plus `policy_design_case.best_in_class_benchmarking.v1` contract id; `validate_policy_benchmarking_record` validates external audit, human-team, reversal, retraction, calibration, claim substantiation, triangulation, operator root-cause, run-cost, and proportionality evidence. |
| Tests | Negative: `test_best_in_class_claim_without_benchmark_evidence_is_blocked`, `test_best_in_class_benchmarking_scorecard_blocks_unfalsifiable_claim`, `test_best_in_class_benchmarking_rejects_combined_reversal_retraction_substitute`; positive: `test_best_in_class_benchmarking_record_covers_required_metrics_and_cost_refs`, `test_best_in_class_benchmarking_record_is_public_runtime_quality_api`, `test_readiness_payload_exposes_wave31_best_in_class_benchmarking_component`. |
| Enforcement | Scorecard gate `policy_design_wave31_best_in_class_benchmarking` blocks best-in-class claims without validated benchmark records, missing required metric families, benchmark target failures, local/path-like refs, missing cost/proportionality refs, and records that do not cover all best-in-class claim ids. |
| Operator surface | Failure codes include `policy_design_best_in_class_benchmarking_record_missing`, `policy_design_best_in_class_benchmark_metric_missing`, `policy_design_best_in_class_claim_not_benchmarked`, `policy_design_best_in_class_run_cost_ref_missing`, and `policy_design_best_in_class_proportionality_ref_missing`; operator next command is the Wave 31 benchmarking and readiness test set. |
| Rebaseline | Wave 31 rebaseline generated coverage, readiness, deterministic matrix, sample, diff, commands, and root-cause artifacts under `_build/policy-design-case/rebaseline/wave-31/`. The fresh deterministic matrix still fails on downstream serious-scorecard blockers, while the Wave 31 readiness component is `pass`. |
| Handoff | Wave 32 Pass 1B hardening coverage closeout may consume the Wave 31 readiness/coverage component as implemented benchmarking/proportionality evidence, but remains responsible for mapping every Pass 1B PDD to concrete owner/gate/blocker rows. |

| Artifact id | Artifact |
|-------------|----------|
| `W31-COVERAGE` | [coverage.json](../../../_build/policy-design-case/rebaseline/wave-31/coverage.json) |
| `W31-COVERAGE-MD` | [coverage.md](../../../_build/policy-design-case/rebaseline/wave-31/coverage.md) |
| `W31-READINESS` | [readiness.json](../../../_build/policy-design-case/rebaseline/wave-31/readiness.json) |
| `W31-MATRIX` | [deterministic_matrix.json](../../../_build/policy-design-case/rebaseline/wave-31/deterministic_matrix.json) |
| `W31-SAMPLE` | [policy_design_case_sample.json](../../../_build/policy-design-case/rebaseline/wave-31/policy_design_case_sample.json) |
| `W31-DIFF` | [diff_from_wave_N_minus_1.json](../../../_build/policy-design-case/rebaseline/wave-31/diff_from_wave_N_minus_1.json) |
| `W31-RCA` | [operator_root_cause_sample.md](../../../_build/policy-design-case/rebaseline/wave-31/operator_root_cause_sample.md) |
| `W31-COMMANDS` | [commands.json](../../../_build/policy-design-case/rebaseline/wave-31/commands.json) |

## Wave 32 - Pass 1B Hardening Coverage Closeout

Purpose: prove every Pass 1B diagnostic is covered by concrete evidence,
owner, gate, or blocker.

Parallel phases in this wave:

### Phase 32.1 - Pass 1B Hardening Coverage Closeout

- [x] For every Pass 1B group in the hardening coverage contract, record owner, implemented evidence contract, scorecard/readiness gate, and remaining blocker.
- [x] Fail closeout if any Pass 1B PDD is only covered by a generic hardening note.
- [x] Add a generated Pass 1B coverage report under `_build/policy-design-case/rebaseline/wave-32/pass1b_hardening_coverage.json`.
- [x] Add tests that detect missing coverage for tenant/CAS/governance, substrate residual, observability, config/release/migration, external dependency, and client-surface groups.

### Wave 32 Exit Fence

- [x] Every Pass 1B PDD maps to a concrete phase, evidence contract, and closeout gate.
- [x] Pass 1B hardening no longer blocks the real-domain baseline.
- [x] No governance, audit, client, release, or projection record can mint authority.

## Wave 33 - Research-Profile Real Domain Baseline

Purpose: generate real domain evidence before behavioral diagnostics begin.

Parallel phases in this wave:

### Phase 33.1 - Research-Profile Real Domain Baseline

- [x] Run a research-profile policy case through intent, concept spine, producer evidence, portfolio, claim argument, and readiness.
- [x] Record whether live providers or production services are unavailable as typed setup evidence.
- [x] Store baseline evidence under `_build/policy-design-case/rebaseline/wave-33/`.

### Wave 33 Exit Fence

- [x] Research-profile real domain evidence exists or missing infrastructure is typed setup evidence.

### Wave 33 Acceptance Packet

| Packet field | Evidence |
|--------------|----------|
| Scope | Phase 33.1, research-profile real-domain baseline using canonical production data, simulated local provider evidence, live-provider setup probe, production-service setup probe, and readiness aggregation. |
| Real-domain evidence | [real_domain_baseline.json](../../../_build/policy-design-case/rebaseline/wave-33/real_domain_baseline.json) records the Wave 33 exit-fence result, fresh research bundle path, policy intent, blocked concept spine, producer evidence statuses, portfolio gate, claim argument, claim grounding, and readiness status. |
| Runtime bundle | [research_real_domain_matrix.json](../../../_build/policy-design-case/rebaseline/wave-33/research_real_domain_matrix.json) and [deterministic_matrix.json](../../../_build/policy-design-case/rebaseline/wave-33/deterministic_matrix.json) record the fresh research/canonical-production lane. The lane emitted a real bundle and failed closed on scorecard blockers rather than missing evidence. |
| Setup evidence | [live_provider_setup.json](../../../_build/policy-design-case/rebaseline/wave-33/live_provider_setup.json) records `live_provider_unavailable` for the Gonka-compatible LLM gateway; [production_service_setup.json](../../../_build/policy-design-case/rebaseline/wave-33/production_service_setup.json) records `local_backing_service_unavailable` for PostgreSQL-backed production state. Both carry `readiness_state: not_ready`. |
| Extracted case evidence | [policy_design_case_sample.json](../../../_build/policy-design-case/rebaseline/wave-33/policy_design_case_sample.json), [claim_argument.json](../../../_build/policy-design-case/rebaseline/wave-33/claim_argument.json), [policy_grounding_matrix.json](../../../_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json), [quality_scorecard.json](../../../_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json), and [production_data_evidence.json](../../../_build/policy-design-case/rebaseline/wave-33/production_data_evidence.json). |
| Rebaseline | [coverage.json](../../../_build/policy-design-case/rebaseline/wave-33/coverage.json), [coverage.md](../../../_build/policy-design-case/rebaseline/wave-33/coverage.md), [readiness.json](../../../_build/policy-design-case/rebaseline/wave-33/readiness.json), [diff_from_wave_N_minus_1.json](../../../_build/policy-design-case/rebaseline/wave-33/diff_from_wave_N_minus_1.json), and [commands.json](../../../_build/policy-design-case/rebaseline/wave-33/commands.json). |
| Handoff | Wave 34 diagnostics should consume Wave 33 bundle evidence and typed blockers instead of hypothetical case state. |

## Wave 34 - Pass 2 Behavioral Diagnostics

Purpose: run all deferred behavioral diagnostics against real case evidence, not
hypotheses.

Parallel phases in this wave:

### Phase 34.1 - Cross-Domain And Metamorphic Diagnostics

- [x] Run PDD-037, PDD-055, and PDD-056 against Wave 33 evidence.
- [x] Record detailed findings under `_build/diagnostics/` and backlog-summary fragments under `_build/diagnostics/pass2/backlog_fragments/`.

### Phase 34.1 Acceptance Packet

| Packet field | Evidence |
|--------------|----------|
| Scope | Phase 34.1, Pass 2 diagnostics for PDD-037 cross-domain generality, PDD-055 metamorphic policy behavior, and PDD-056 multilingual/transliteration equivalence against Wave 33 evidence. |
| Runtime evidence consumed | Wave 33 artifacts under [`_build/policy-design-case/rebaseline/wave-33/`](../../../_build/policy-design-case/rebaseline/wave-33/), including `real_domain_baseline.json`, `research_real_domain_matrix.json`, `policy_design_case_sample.json`, `quality_scorecard.json`, `readiness.json`, `production_data_evidence.json`, `claim_argument.json`, and `policy_grounding_matrix.json`. |
| Detailed diagnostics | [`phase34_1_cross_domain_metamorphic_diagnostics.json`](../../../_build/diagnostics/pass2/phase34_1_cross_domain_metamorphic_diagnostics.json), [`PDD-037`](../../../_build/diagnostics/pdd-037/cross_domain_generality_diagnostic_matrix.json), [`PDD-055`](../../../_build/diagnostics/pdd-055/metamorphic_policy_diagnostic_suite.json), and [`PDD-056`](../../../_build/diagnostics/pdd-056/multilingual_transliteration_equivalence_audit.json). |
| Findings | PDD-037 diagnosed five missing cross-domain runtime bundles; PDD-055 diagnosed 35 missing metamorphic runtime variants and five missing data-removal/irrelevant-data probes; PDD-056 diagnosed missing English/Ukrainian runtime pairs, transliteration variants, mixed-language variants, and hardcoded-language-path audit evidence. |
| Backlog fragments | [`pdd-037.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-037.md), [`pdd-055.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-055.md), and [`pdd-056.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-056.md). |
| Tests and commands | `uv run pytest tests/repo_quality/tools/test_policy_design_case_pass2_diagnostics.py -q` passed; `uv run python tools/quality/validation/build_policy_design_case_pass2_diagnostics.py` wrote the Phase 34.1 artifacts with `status=diagnosed` and runtime acceptance `failed`. |
| Handoff | Wave 35 should triage these as real Wave 33 behavioral gaps, not as missing diagnostic infrastructure: the scenario-contract controls pass, but the required paired runtime bundles do not exist yet. |

### Phase 34.2 - Adversarial And Fail-Closed Diagnostics

- [x] Run PDD-038, PDD-064, PDD-065, and PDD-098 against Wave 33 evidence.
- [x] Record detailed findings under `_build/diagnostics/` and backlog-summary fragments under `_build/diagnostics/pass2/backlog_fragments/`.

### Phase 34.2 Acceptance Packet

| Packet field | Evidence |
|--------------|----------|
| Scope | Phase 34.2, Pass 2 diagnostics for PDD-038 adversarial fail-closed behavior, PDD-064 cache/index/snapshot poisoning controls, PDD-065 cross-component error semantics, and PDD-098 strategic behavior/gaming/fraud/arbitrage binding against Wave 33 evidence. |
| Runtime evidence consumed | Wave 33 artifacts under [`_build/policy-design-case/rebaseline/wave-33/`](../../../_build/policy-design-case/rebaseline/wave-33/) plus runtime bundle evidence under `.polisyos/canary_evidence/profile-research__provider-simulated__data-canonical_production__scenario-public_golden__ui-api_only/20260518T185434Z_66696d6a137a4e6ba95afc9dd810c045/`. |
| Detailed diagnostics | [`phase34_2_adversarial_fail_closed_diagnostics.json`](../../../_build/diagnostics/pass2/phase34_2_adversarial_fail_closed_diagnostics.json), [`PDD-038`](../../../_build/diagnostics/pdd-038/adversarial_fail_closed_diagnostics.json), [`PDD-064`](../../../_build/diagnostics/pdd-064/cache_index_snapshot_poisoning_audit.json), [`PDD-065`](../../../_build/diagnostics/pdd-065/cross_component_error_semantics_audit.json), and [`PDD-098`](../../../_build/diagnostics/pdd-098/strategic_behavior_binding_audit.json). |
| Findings | Wave 33 fails closed for the baseline, but PDD-038 adversarial scenarios are not scenario-bearing evidence; PDD-064 confirms source/snapshot blockers while missing cache/index fingerprint and poisoning controls; PDD-065 preserves detailed root-cause codes while readiness summary collapses failure semantics; PDD-098 finds no strategic behavior ledger or mechanism-bound gaming/fraud/arbitrage evidence. |
| Backlog fragments | [`pdd-038.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-038.md), [`pdd-064.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-064.md), [`pdd-065.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-065.md), and [`pdd-098.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-098.md). |
| Tests and commands | `uv run pytest tests/repo_quality/tools/test_policy_design_case_pass2_diagnostics.py -q` passed; `uv run python tools/quality/validation/build_policy_design_case_pass2_diagnostics.py` wrote the Phase 34.2 artifacts with `status=diagnosed` and runtime acceptance `failed`. |
| Handoff | Wave 35 should treat these as fail-closed coverage gaps: current blockers prevent publication, but dedicated adversarial, poisoning, error-semantics, and strategic-behavior gates are still required before closeout can rely on them. |

### Phase 34.3 - Claim Grounding And Validity Diagnostics

- [x] Run PDD-044, PDD-048, PDD-050, PDD-051, PDD-057, PDD-087, and PDD-088 against Wave 33 evidence.
- [x] Record detailed findings under `_build/diagnostics/` and backlog-summary fragments under `_build/diagnostics/pass2/backlog_fragments/`.

### Phase 34.3 Acceptance Packet

| Packet field | Evidence |
|--------------|----------|
| Scope | Phase 34.3, Pass 2 diagnostics for claim grounding, competence authority, transferability, uncertainty propagation, monitoring binding, model-registry readiness, and BERL/explanation reliability against Wave 33 evidence. |
| Runtime evidence consumed | Wave 33 artifacts under [`_build/policy-design-case/rebaseline/wave-33/`](../../../_build/policy-design-case/rebaseline/wave-33/) plus the Wave 33 runtime bundle named in `real_domain_baseline.json`. |
| Phase packet | [`phase_34_3_claim_grounding_validity_index.json`](../../../_build/diagnostics/pass2/phase_34_3_claim_grounding_validity_index.json) and [`phase_34_3_claim_grounding_validity_index.md`](../../../_build/diagnostics/pass2/phase_34_3_claim_grounding_validity_index.md) record `status=diagnosed`, runtime acceptance `failed`, six failed/blocked gates, and one not-triggered BERL/explanation diagnostic. |
| Detailed diagnostics | [`PDD-044`](../../../_build/diagnostics/pdd-044/final_artifact_section_grounding_audit.json), [`PDD-048`](../../../_build/diagnostics/pdd-048/institutional_competence_authority_audit.json), [`PDD-050`](../../../_build/diagnostics/pdd-050/external_validity_transferability_audit.json), [`PDD-051`](../../../_build/diagnostics/pdd-051/uncertainty_propagation_chain_audit.json), [`PDD-057`](../../../_build/diagnostics/pdd-057/final_decision_monitoring_claim_binding_audit.json), [`PDD-087`](../../../_build/diagnostics/pdd-087/model_registry_readiness_binding_audit.json), and [`PDD-088`](../../../_build/diagnostics/pdd-088/berl_explanation_reliability_binding_audit.json). |
| Findings | Wave 33 has section refs and claim grounding, but publishable compiler/runtime registry, competence, transferability, uncertainty propagation, monitoring binding, and model-readiness bindings are not sufficient for closeout; PDD-088 is explicitly not triggered because no BERL/explanation support was detected. |
| Backlog fragments | [`pdd-044.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-044.md), [`pdd-048.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-048.md), [`pdd-050.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-050.md), [`pdd-051.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-051.md), [`pdd-057.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-057.md), [`pdd-087.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-087.md), and [`pdd-088.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-088.md). |
| Tests and commands | `uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_3.py` regenerated the packet; `uv run pytest tests/repo_quality/tools/test_policy_design_case_pass2_diagnostics.py -q` and `uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py --repo-root .` passed. |
| Handoff | Wave 35 may classify these findings, but Wave 34 makes no remediation/disposition decision beyond recording the diagnosed gates and the PDD-088 not-triggered boundary. |

### Phase 34.4 - Extraction And Measurement Diagnostics

- [x] Run PDD-100 and PDD-101 against Wave 33 evidence.
- [x] Record detailed findings under `_build/diagnostics/` and backlog-summary fragments under `_build/diagnostics/pass2/backlog_fragments/`.

### Phase 34.4 Acceptance Packet

| Packet field | Evidence |
|--------------|----------|
| Scope | Phase 34.4, Pass 2 diagnostics for PDD-100 document/OCR/table extraction authority and PDD-101 survey measurement/construct-validity semantics against Wave 33 evidence. |
| Runtime evidence consumed | Wave 33 rebaseline artifacts plus runtime bundle quality evidence under `.polisyos/canary_evidence/profile-research__provider-simulated__data-canonical_production__scenario-public_golden__ui-api_only/20260518T185434Z_66696d6a137a4e6ba95afc9dd810c045/`. |
| Phase packet | [`phase_34_4_extraction_measurement_diagnostics.json`](../../../_build/diagnostics/pass2/phase_34_4_extraction_measurement_diagnostics.json) and [`phase_34_4_extraction_measurement_diagnostics.md`](../../../_build/diagnostics/pass2/phase_34_4_extraction_measurement_diagnostics.md) record `status=diagnosed`, runtime acceptance `failed`, and two failed gates. |
| Detailed diagnostics | [`PDD-100`](../../../_build/diagnostics/pdd-100/document_extraction_authority_audit.json) and [`PDD-101`](../../../_build/diagnostics/pdd-101/survey_measurement_construct_validity_audit.json). |
| Findings | PDD-100 confirms there is no claim-bound extraction-quality ledger and adjacent Lex/Scholar QC does not become extraction authority; PDD-101 confirms there is no survey-to-claim measurement ledger, no typed non-survey abstention for the current claim, and no survey-design guard for future survey-shaped sources. |
| Backlog fragments | [`pdd-100.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-100.md) and [`pdd-101.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-101.md). |
| Tests and commands | `uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_4.py` regenerated the packet; focused pytest coverage asserts canonical Wave 34 metadata, Wave 33 provenance, failed gates, detail files, and backlog fragments. |
| Handoff | Wave 35 should treat these as real extraction/measurement authority gaps; Wave 34 only records `recommended_remediation_id` values and does not update disposition artifacts. |

### Phase 34.5 - Operational And Recovery Diagnostics

- [x] Run PDD-046, PDD-077, PDD-078, PDD-090, and PDD-104 against Wave 33 evidence.
- [x] Record detailed findings under `_build/diagnostics/` and backlog-summary fragments under `_build/diagnostics/pass2/backlog_fragments/`.

### Phase 34.5 Acceptance Packet

| Packet field | Evidence |
|--------------|----------|
| Scope | Phase 34.5, Pass 2 diagnostics for root-cause observability, restore drills, resource exhaustion, live/polling parity, and archive-grade reproducibility against Wave 33 evidence. |
| Runtime evidence consumed | Wave 33 rebaseline artifacts, runtime bundle timeline, replay manifest, provenance manifest, performance budget, public export, drift, attestation, scorecard, readiness, and policy-design-case quality evidence. |
| Phase packet | [`phase_34_5_operational_recovery_diagnostics.json`](../../../_build/diagnostics/pass2/phase_34_5_operational_recovery_diagnostics.json) and [`phase_34_5_operational_recovery_diagnostics.md`](../../../_build/diagnostics/pass2/phase_34_5_operational_recovery_diagnostics.md) record `status=diagnosed`, runtime acceptance `failed`, and five failed gates. |
| Detailed diagnostics | [`PDD-046`](../../../_build/diagnostics/pdd-046/operational_root_cause_completeness_audit.json), [`PDD-077`](../../../_build/diagnostics/pdd-077/backup_restore_drill_evidence_audit.json), [`PDD-078`](../../../_build/diagnostics/pdd-078/resource_exhaustion_semantics_audit.json), [`PDD-090`](../../../_build/diagnostics/pdd-090/realtime_cursor_replay_polling_parity_audit.json), and [`PDD-104`](../../../_build/diagnostics/pdd-104/archive_grade_reproducibility_audit.json). |
| Findings | Wave 33 has partial root-cause breadcrumbs, replay/provenance hashes, performance budget evidence, live-stream primitives, and drift/public-export/attestation evidence, but lacks a complete root-cause index, restore drill, resource-exhaustion claim-impact ledger, live/polling parity proof, and archive-grade long-term verification bundle. |
| Backlog fragments | [`pdd-046.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-046.md), [`pdd-077.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-077.md), [`pdd-078.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-078.md), [`pdd-090.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-090.md), and [`pdd-104.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-104.md). |
| Tests and commands | `uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_5.py` regenerated the packet; focused pytest coverage asserts canonical Wave 34 metadata, Wave 33 provenance, failed gates, detail files, and backlog fragments. |
| Handoff | Wave 35 should triage the operational and recovery gaps without treating Wave 34 `recommended_remediation_id` fields as dispositions. |

### Phase 34.6 - Human-Facing, Legitimacy, And Memory Diagnostics

- [x] Run PDD-034, PDD-069, PDD-097, PDD-099, PDD-103, and PDD-083 against Wave 33 evidence.
- [x] Record detailed findings under `_build/diagnostics/` and backlog-summary fragments under `_build/diagnostics/pass2/backlog_fragments/`.

### Phase 34.6 Acceptance Packet

| Packet field | Evidence |
|--------------|----------|
| Scope | Phase 34.6, Pass 2 diagnostics for projection consistency, operator truthfulness, reusable memory/reflexion, implementation feasibility, public contestability/appeals, and human overtrust/UI persuasion risk against Wave 33 evidence. |
| Runtime evidence consumed | Wave 33 rebaseline artifacts and runtime bundle evidence only; the phase index records no dependency on another Wave 34 phase packet. |
| Phase packet | [`phase_34_6_human_facing_legitimacy_memory_diagnostics.json`](../../../_build/diagnostics/pass2/phase_34_6_human_facing_legitimacy_memory_diagnostics.json) and [`phase_34_6_human_facing_legitimacy_memory_diagnostics.md`](../../../_build/diagnostics/pass2/phase_34_6_human_facing_legitimacy_memory_diagnostics.md) record `status=diagnosed`, runtime acceptance `failed`, and six failed gates. |
| Detailed diagnostics | [`PDD-034`](../../../_build/diagnostics/pdd-034/dashboard_api_projection_consistency_audit.json), [`PDD-069`](../../../_build/diagnostics/pdd-069/dashboard_operator_truthfulness_audit.json), [`PDD-083`](../../../_build/diagnostics/pdd-083/reusable_agent_memory_reflexion_applicability_audit.json), [`PDD-097`](../../../_build/diagnostics/pdd-097/implementation_feasibility_beyond_final_text_audit.json), [`PDD-099`](../../../_build/diagnostics/pdd-099/public_contestability_appeals_legitimacy_audit.json), and [`PDD-103`](../../../_build/diagnostics/pdd-103/human_overtrust_ui_persuasion_risk_audit.json). |
| Findings | Wave 33 has projection boundaries, some operator diagnostic shape, source memory-safety primitives, implementation text, lifecycle reports, and projection-only trust semantics; it lacks the phase-required projection matrix, operator journey matrix, runtime memory/no-memory ledger, implementation feasibility ledger, contestability/appeal outcome ledger, and trust-framing UI negative-test ledger. |
| Backlog fragments | [`pdd-034.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-034.md), [`pdd-069.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-069.md), [`pdd-083.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-083.md), [`pdd-097.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-097.md), [`pdd-099.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-099.md), and [`pdd-103.md`](../../../_build/diagnostics/pass2/backlog_fragments/pdd-103.md). |
| Tests and commands | `uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_6.py` regenerated the packet; focused pytest coverage asserts canonical status, Wave 33 provenance, fragments, and absence of `promoted_remediation` disposition semantics. |
| Handoff | Wave 35 may classify the human-facing, legitimacy, and memory findings; Wave 34 leaves them as diagnosed evidence with `recommended_remediation_id` only. |

### Wave 34 Exit Fence

- [x] Pass 2 diagnostics have detailed artifacts and backlog-summary fragments.
- [x] No phase in this wave consumes another phase in this wave.

Exit-fence evidence: `uv run pytest tests/repo_quality/tools/test_policy_design_case_pass2_diagnostics.py -q` passed for all Phase 34 runner and validator coverage; `uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py --repo-root .` passed across all 27 expected PDDs, all six phase indexes, Wave 33 provenance, backlog fragments, and same-wave dependency checks.

## Wave 35 - Pass 2 Triage, Remediation, And Disposition

Purpose: prevent behavioral diagnostics from becoming a report-only exercise
before final closeout.

Parallel phases in this wave:

Wave 35 intentionally has a single phase. The work is serial rather than
parallel: findings must be inventoried before they can be classified, classified
before remediation scope can be chosen, and dispositioned before closeout waves
can safely proceed. Do not split this wave into artificial parallel phases unless
a future revision identifies independent work packets with no shared input or
output dependency.

### Phase 35.1 - Pass 2 Triage, Remediation, And Disposition

- [x] Build a canonical Wave 34 findings ledger from the 27 PDD detail artifacts and six phase indexes, preserving finding code, severity, PDD id, phase, source evidence, recommended gate, and recommended remediation id.
- [x] Cluster findings by root capability gap before choosing remediation scope, so shared causes are handled once instead of creating 27 unrelated local fixes.
- [x] Classify every Wave 34 finding as `must_fix_before_closeout`, `accepted_blocker`, `next_plan_remediation`, or `false_alarm_with_evidence`; every classification must include rationale, owner, affected subsystem, closeout impact, and verification command.
- [x] Identify which current plan waves remain valid, which need strengthened entry criteria, and which new remediation waves must be inserted before Wave 36 can start.
- [x] Implement focused remediation only for findings classified as `must_fix_before_closeout` within Wave 35 scope, and rerun the affected diagnostic after each remediation.
- [x] Record accepted blockers and next-plan remediation items in the decision log with owner, revisit trigger, target plan wave, and the exact evidence that makes deferral honest.
- [x] Generate `_build/policy-design-case/rebaseline/wave-35/pass2_findings_ledger.json`, `_build/policy-design-case/rebaseline/wave-35/pass2_root_cause_clusters.json`, and `_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json`.
- [x] Add or update a disposition validator that fails if any Wave 34 finding lacks classification, rationale, owner, source evidence, verification command, or valid deferral/remediation evidence.
- [x] Fail closeout if any Wave 34 finding lacks disposition, if any `must_fix_before_closeout` item remains unresolved, or if Wave 36 entry criteria do not reflect the resulting disposition.

Execution boundaries:

- Wave 35 may read Wave 34 diagnostic artifacts and Wave 33 evidence, but it must not mutate Wave 34 diagnostic findings to make disposition easier.
- Wave 35 may record `recommended_remediation_id` mappings, but it must not treat a recommendation as a completed remediation without fresh verification evidence.
- Wave 35 must not merge backlog fragments into the main backlog; backlog merge and handoff remain Wave 41 work unless the plan is explicitly revised.
- Wave 35 must not start deterministic canary closeout, runtime API closeout, local integration smoke, dashboard journey smoke, or final readiness closeout as a substitute for disposition.

### Wave 35 Exit Fence

- [x] Every Wave 34 PDD detail artifact is represented in the Wave 35 findings ledger.
- [x] Every Wave 34 finding has exactly one disposition: `must_fix_before_closeout`, `accepted_blocker`, `next_plan_remediation`, or `false_alarm_with_evidence`.
- [x] Every disposition has rationale, owner, affected subsystem, source evidence, closeout impact, verification command, and either completed remediation evidence, accepted-blocker evidence, next-plan target wave, or false-alarm evidence.
- [x] Root-cause clusters cover all findings and identify shared remediation surfaces so the plan does not fragment common capability gaps into duplicated fixes.
- [x] Every `must_fix_before_closeout` item is resolved and its affected Phase 34 diagnostic has been rerun, or Wave 35 fails.
- [x] Any `accepted_blocker` or `next_plan_remediation` item has a revisit trigger and target wave that occurs before the item can affect final closeout.
- [x] Wave 36 and later closeout waves have updated entry criteria that respect the Wave 35 dispositions; closeout waves may start only after the disposition validator passes.

Exit-fence evidence: Wave 35 added
`tools/quality/validation/build_policy_design_case_pass2_disposition.py`,
`tools/quality/validation/check_policy_design_case_pass2_disposition.py`, and
`tests/repo_quality/tools/test_policy_design_case_pass2_disposition.py`. The
builder emits 27 represented Wave 34 detail artifacts, six phase indexes, 113
finding dispositions, one not-triggered artifact disposition for PDD-088, and
six root-cause clusters. Wave 35 classified zero findings as
`must_fix_before_closeout`; no product remediation was completed in Wave 35
because the remaining gaps require inserted pre-Wave-36 remediation waves with
fresh rerun evidence rather than local ledger edits.

## Common Remediation Completion Contract For Waves 35A-35E

The inserted Wave 35 remediation waves close the Wave 34 findings that Wave 35
classified as `next_plan_remediation` or `accepted_blocker`. These waves are
not report-writing exercises. A finding is closed only when fresh runtime or
tooling evidence exists, the affected Phase 34 diagnostic has been rerun, and
Wave 35 disposition records completed remediation evidence for the exact
`finding_id`.

Required start state for every Wave 35A-35E wave:

- [x] Run `uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py --repo-root . --require-passing`.
- [x] Read `_build/policy-design-case/rebaseline/wave-35/pass2_root_cause_clusters.json` and filter the cluster ids named by the wave.
- [x] Read `_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json` and enumerate every affected `finding_id`, `finding_code`, PDD id, source artifact, source evidence, recommended gate, owner, and verification command.
- [x] Create the wave output directory before work begins: `_build/policy-design-case/rebaseline/wave-35A/`, `_build/policy-design-case/rebaseline/wave-35B/`, `_build/policy-design-case/rebaseline/wave-35C/`, `_build/policy-design-case/rebaseline/wave-35D/`, or `_build/policy-design-case/rebaseline/wave-35E/`.

Required completion evidence for every remediated finding:

- `finding_id`, `finding_code`, `pdd_id`, `phase`, and `root_cause_cluster_id`.
- `source_artifact` and the original Wave 35 `source_evidence`.
- The exact implementation artifact or runtime bundle that fixes the gap.
- The diagnostic rerun command, exit code, timestamp, and output artifact path.
- The before status from Wave 35 disposition and the after status from the rerun.
- The owner who accepts the remediation and the command that a reviewer can run.

Disposition update rule:

- A remediated item must no longer remain `next_plan_remediation` or
  `accepted_blocker` for the affected cluster.
- The normal completed state is `must_fix_before_closeout` with
  `remediation_evidence.status=resolved`.
- Use `false_alarm_with_evidence` only when fresh rerun evidence proves the
  original row was a diagnostic false alarm rather than a real capability gap.
- Do not treat a recommended remediation id as completed evidence without a
  fresh diagnostic rerun and a concrete output artifact.

Historical evidence rule:

- Do not edit the original Wave 34 detail artifacts to make Wave 35A-35E look
  cleaner. If a Phase 34 tool must be rerun, capture the rerun summary and
  hashes under the current Wave 35A-35E output directory and update the Wave 35
  disposition artifacts from that evidence.

Closeout-ready validator rule:

- Before Wave 36 can start, run
  `uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py --repo-root . --require-passing --require-closeout-ready`.
- `--require-closeout-ready` must fail while any Wave 35 disposition remains
  `next_plan_remediation` or `accepted_blocker`.

## Wave 35A - Runtime Scenario And Variant Evidence Remediation

Purpose: fully satisfy the Wave 35 `runtime_scenario_variant_coverage` cluster
before deterministic closeout begins.

Parallel phases in this wave:

Wave 35A intentionally has a single phase. Scenario inventory, runtime bundle
generation, equivalence assertions, diagnostic rerun, and disposition update are
serial because later steps depend on the exact bundle ids produced by earlier
steps.

### Phase 35A.1 - Scenario Matrix And Variant Evidence

Affected findings:

- Cluster: `runtime_scenario_variant_coverage`.
- PDDs: PDD-037, PDD-055, PDD-056.
- Wave 35 finding count: 31.
- Source artifacts:
  `_build/diagnostics/pdd-037/cross_domain_generality_diagnostic_matrix.json`,
  `_build/diagnostics/pdd-055/metamorphic_policy_diagnostic_suite.json`,
  and
  `_build/diagnostics/pdd-056/multilingual_transliteration_equivalence_audit.json`.

Required output artifacts:

- `_build/policy-design-case/rebaseline/wave-35A/scenario_variant_inventory.json`
- `_build/policy-design-case/rebaseline/wave-35A/cross_domain_runtime_bundles.json`
- `_build/policy-design-case/rebaseline/wave-35A/metamorphic_runtime_variants.json`
- `_build/policy-design-case/rebaseline/wave-35A/language_equivalence_runtime_pairs.json`
- `_build/policy-design-case/rebaseline/wave-35A/hardcoded_language_path_audit.json`
- `_build/policy-design-case/rebaseline/wave-35A/phase34_1_rerun.json`
- `_build/policy-design-case/rebaseline/wave-35A/wave35_disposition_update.json`

Work packets:

- [x] Build `scenario_variant_inventory.json` by reading Wave 35 disposition rows for PDD-037, PDD-055, and PDD-056. The inventory must contain one row per affected `finding_id`, the scenario or variant id, the required runtime evidence family, owner, source artifact, and verification command.
- [x] For PDD-037, generate runtime-owned research-profile bundles for all missing cross-domain scenarios named by the PDD-037 findings. The current known required scenarios are `social_benefit_tax_relief_household_support`, `healthcare_medicine_access_shortage`, `infrastructure_energy_reliability_support`, `education_labor_reskilling_access`, and `explicit_legal_conflict_benefit_exclusion`.
- [x] Record each PDD-037 bundle in `cross_domain_runtime_bundles.json` with `scenario_id`, `run_id`, `job_id`, `bundle_path`, `quality_scorecard_ref`, `policy_design_case_ref`, `claim_argument_ref`, `source_artifacts`, `scorecard_status`, and `diagnostic_event_refs`.
- [x] For PDD-055, generate paired metamorphic runtime variants for every missing scenario/variant pair named by the PDD-055 findings. Each row in `metamorphic_runtime_variants.json` must include baseline bundle, variant bundle, transformed input, invariant or expected-difference assertion, observed result, and failure code when the assertion fails.
- [x] For PDD-055 irrelevant-data/data-removal probes, record removed or injected fields, why those fields are irrelevant to the final claim, before/after claim and scorecard state, and whether the runtime correctly rejected or ignored the change.
- [x] For PDD-056, generate English/Ukrainian runtime pairs, transliteration variants, and mixed-language variants for every missing language finding. Each row in `language_equivalence_runtime_pairs.json` must include source locale, target locale, transliteration mode, mixed-language mode, paired bundle refs, normalized claim refs, and equivalence result.
- [x] Produce `hardcoded_language_path_audit.json` by scanning runtime routing, prompt/tool, locale, lex/normpack, dashboard/API projection, and scenario loading paths for hardcoded English-only or Ukrainian-only behavior. The audit must list inspected paths, detected literals, approved literals, rejected literals, and owner.
- [x] Rerun Phase 34.1 with `uv run python tools/quality/validation/build_policy_design_case_pass2_diagnostics.py --phase 34.1` and then `uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py --repo-root .`.
- [x] Write `phase34_1_rerun.json` with the command, exit code, stdout/stderr summary, rerun artifact hashes, and per-PDD before/after gate status.
- [x] Update Wave 35 disposition evidence for all 31 affected findings. The update must replace unresolved `next_plan_remediation` rows with resolved remediation evidence or explicit false-alarm evidence backed by the rerun.

### Wave 35A Exit Fence

- [x] `scenario_variant_inventory.json` contains exactly the 31 affected Wave 35 finding ids and no unrelated findings.
- [x] PDD-037 has a runtime bundle row for each required cross-domain scenario and every row has scorecard, claim, and Policy Design Case refs.
- [x] PDD-055 has paired baseline/variant evidence and assertion results for every metamorphic and irrelevant-data/data-removal finding.
- [x] PDD-056 has paired multilingual, transliteration, mixed-language, and hardcoded-language audit evidence.
- [x] Phase 34.1 rerun evidence is captured under `_build/policy-design-case/rebaseline/wave-35A/`.
- [x] No `runtime_scenario_variant_coverage` disposition remains `next_plan_remediation` or `accepted_blocker`.
- [x] `uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py --repo-root . --require-passing --require-closeout-ready` has no failure caused by this cluster.

## Wave 35B - Adversarial Fail-Closed And Strategic Gate Remediation

Purpose: fully satisfy the Wave 35
`adversarial_fail_closed_and_strategic_gates` cluster before deterministic
closeout begins.

Parallel phases in this wave:

Wave 35B intentionally has a single phase. The adversarial, poisoning,
error-taxonomy, and strategic-risk work shares the same fail-closed and negative
control evidence, so it must be remediated and rerun as one serial packet.

### Phase 35B.1 - Adversarial, Poisoning, Error, And Strategic Gates

Affected findings:

- Cluster: `adversarial_fail_closed_and_strategic_gates`.
- PDDs: PDD-038, PDD-064, PDD-065, PDD-098.
- Wave 35 finding count: 12.
- Source artifacts:
  `_build/diagnostics/pass2/phase34_2_adversarial_fail_closed_diagnostics.json`,
  `_build/diagnostics/pdd-038/adversarial_fail_closed_diagnostics.json`,
  `_build/diagnostics/pdd-064/cache_index_snapshot_poisoning_audit.json`,
  `_build/diagnostics/pdd-065/cross_component_error_semantics_audit.json`,
  and `_build/diagnostics/pdd-098/strategic_behavior_binding_audit.json`.

Required output artifacts:

- `_build/policy-design-case/rebaseline/wave-35B/adversarial_scenario_matrix.json`
- `_build/policy-design-case/rebaseline/wave-35B/cache_index_poisoning_controls.json`
- `_build/policy-design-case/rebaseline/wave-35B/cross_component_error_taxonomy.json`
- `_build/policy-design-case/rebaseline/wave-35B/strategic_behavior_gate_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35B/phase34_2_rerun.json`
- `_build/policy-design-case/rebaseline/wave-35B/wave35_disposition_update.json`

Work packets:

- [x] Build `adversarial_scenario_matrix.json` from the PDD-038 disposition rows. It must list each adversarial scenario, prompt/tool injection probe, expected fail-closed code, actual runtime status, owner, bundle ref, and operator-visible failure message.
- [x] For PDD-038, run or add runtime evidence for adversarial policy prompts, malformed tool results, prompt injection, unsafe instruction conflicts, source spoofing, and partial-evidence promotion attempts. Each probe must fail closed without promoting final claim authority.
- [x] Build `cache_index_poisoning_controls.json` for PDD-064 with cache key, index fingerprint, snapshot identity, source-facet hash, poisoned input, stale input, expected rejection code, observed rejection code, and CAS or bundle refs.
- [x] For accepted PDD-064 source/snapshot blockers, record why the current blocker is honest and then add the missing dedicated poisoning controls so the blocker is no longer the only safety evidence.
- [x] Build `cross_component_error_taxonomy.json` for PDD-065. It must map Lex, Fabric, Scholar, Foundry, Scientist, runtime, dashboard/API, scorecard, and readiness error codes to root-cause class, missing producer, downstream impact, and display policy.
- [x] Preserve PDD-065 positive evidence that detailed surfaces keep root-cause codes. Do not convert that positive finding into a remediation task; disposition it as false-alarm/positive evidence only when the taxonomy also exists.
- [x] Build `strategic_behavior_gate_ledger.json` for PDD-098 with mechanism-bound gaming, fraud, arbitrage, monitoring, mitigation, and scorecard gate refs. Generic monitoring prose is not acceptable.
- [x] Rerun Phase 34.2 with `uv run python tools/quality/validation/build_policy_design_case_pass2_diagnostics.py --phase 34.2` and then `uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py --repo-root .`.
- [x] Write `phase34_2_rerun.json` with command, exit code, output hashes, and before/after status for PDD-038, PDD-064, PDD-065, and PDD-098.
- [x] Update Wave 35 disposition evidence for all 12 affected findings. No accepted blocker may remain unless a later decision-log entry explicitly supersedes Wave 35B before Wave 36.

### Wave 35B Exit Fence

- [x] `adversarial_scenario_matrix.json` proves every PDD-038 adversarial and injection probe fails closed with an explicit runtime code.
- [x] `cache_index_poisoning_controls.json` proves stale, poisoned, and fingerprint-mismatched cache/index/snapshot inputs are rejected or quarantined.
- [x] `cross_component_error_taxonomy.json` exists and readiness/dashboard surfaces preserve the taxonomy rather than collapsing it to generic failure.
- [x] `strategic_behavior_gate_ledger.json` contains mechanism-bound gaming, fraud, and arbitrage evidence; generic monitoring text is insufficient.
- [x] Phase 34.2 rerun evidence is captured under `_build/policy-design-case/rebaseline/wave-35B/`.
- [x] No `adversarial_fail_closed_and_strategic_gates` disposition remains `next_plan_remediation` or `accepted_blocker`.

## Wave 35C - Claim Authority, Producer Binding, And Semantic Validity Remediation

Purpose: fully satisfy the Wave 35
`claim_authority_and_extraction_measurement_binding` and
`semantic_validity_monitoring_and_model_readiness` clusters before
deterministic closeout begins.

Parallel phases in this wave:

Wave 35C intentionally has a single phase. Claim authority, producer locator
evidence, extraction/measurement authority, validity semantics, monitoring, and
model readiness all meet at final claim acceptance, so completing one without
the others would create another partial false pass.

### Phase 35C.1 - Claim Authority, Producer Binding, And Semantic Validity

Affected findings:

- Clusters: `claim_authority_and_extraction_measurement_binding` and
  `semantic_validity_monitoring_and_model_readiness`.
- PDDs: PDD-044, PDD-048, PDD-050, PDD-051, PDD-057, PDD-087, PDD-100,
  and PDD-101.
- Wave 35 finding count: 22.
- Boundary PDD: PDD-088 remains not-triggered unless explanation evidence is
  introduced.
- Source artifacts:
  `_build/diagnostics/pass2/phase_34_3_claim_grounding_validity_index.json`,
  `_build/diagnostics/pass2/phase_34_4_extraction_measurement_diagnostics.json`,
  and the eight affected PDD detail JSON artifacts.

Required output artifacts:

- `_build/policy-design-case/rebaseline/wave-35C/claim_authority_binding_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35C/extraction_authority_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35C/measurement_construct_validity_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35C/semantic_validity_model_readiness_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35C/phase34_3_rerun.json`
- `_build/policy-design-case/rebaseline/wave-35C/phase34_4_rerun.json`
- `_build/policy-design-case/rebaseline/wave-35C/wave35_disposition_update.json`

Work packets:

- [x] Build `claim_authority_binding_ledger.json` from affected PDD-044 disposition rows. It must bind every final major claim section to runtime claim registry id, claim argument id, warrant id, producer evidence refs, section refs, scorecard gate, readiness check, and publication status.
- [x] Ensure the PDD-044 scorecard blocker is not treated as remediation. It closes only when publishable claim authority exists and the rerun proves the artifact no longer relies on upstream generic blockers.
- [x] Build `extraction_authority_ledger.json` for PDD-100 with claim id, document id, retrieval locator, jurisdiction, time filter, page/span/table/annex/footnote refs, OCR confidence, skipped-content record, extraction QC result, and source producer owner.
- [x] Promote adjacent Lex/Scholar extraction QC only when it is claim-selected and referenced by the final claim authority ledger. Static batch QC next to the run is not enough.
- [x] Build `measurement_construct_validity_ledger.json` for PDD-101 with survey source id, construct id, target population, sample frame, weights, nonresponse, imputation, strata, clusters, measurement error, construct validity result, and claim binding.
- [x] If the current claim remains non-survey-selected, emit a typed non-survey abstention with future-survey guard evidence. Absence of survey evidence is not enough.
- [x] Build `semantic_validity_model_readiness_ledger.json` for PDD-048, PDD-050, PDD-051, PDD-057, and PDD-087. It must include competence refs, delegation refs, source-target context comparison, transportability limits, end-to-end uncertainty refs, method-result refs, claim-to-monitor map, lifecycle invalidation semantics, model dependency refs, calibration refs, stationarity refs, and DDM readiness refs.
- [x] If BERL or explanation support is introduced while implementing the claim authority ledger, add BERL reliability evidence and rerun PDD-088. If no explanation support is introduced, preserve the explicit PDD-088 not-triggered boundary.
- [x] Rerun Phase 34.3 with `uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_3.py` and Phase 34.4 with `uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_4.py`.
- [x] Run `uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py --repo-root .`.
- [x] Write `phase34_3_rerun.json` and `phase34_4_rerun.json` with command, exit code, output hashes, and before/after status for all affected PDDs.
- [x] Update Wave 35 disposition evidence for all 22 affected findings and the PDD-088 artifact disposition when applicable.

### Wave 35C Exit Fence

- [x] Every final claim section is bound through runtime claim authority and producer evidence refs.
- [x] Extraction authority is claim-selected and covers locator, OCR, table, annex, footnote, skipped-content, and QC semantics.
- [x] Survey/measurement evidence is either claim-bound with design semantics or explicitly abstained with a future-survey guard.
- [x] Competence, transferability, uncertainty, monitoring, model readiness, method-result, and DDM refs are bound end to end.
- [x] Phase 34.3 and Phase 34.4 rerun evidence is captured under `_build/policy-design-case/rebaseline/wave-35C/`.
- [x] No Wave 35C cluster disposition remains `next_plan_remediation` or `accepted_blocker`.
- [x] PDD-088 is either still explicit not-triggered or has fresh BERL reliability evidence.

## Wave 35D - Operational Recovery, Resource, And Archive Remediation

Purpose: fully satisfy the Wave 35
`operational_recovery_resource_and_archive_readiness` cluster before
deterministic closeout begins.

Parallel phases in this wave:

Wave 35D intentionally has a single phase. Root-cause diagnosis, restore,
resource exhaustion, live/polling parity, and archive-grade reproducibility all
share runtime bundle identity and replay/archive refs.

### Phase 35D.1 - Recovery, Resource, Live Parity, And Archive Evidence

Affected findings:

- Cluster: `operational_recovery_resource_and_archive_readiness`.
- PDDs: PDD-046, PDD-077, PDD-078, PDD-090, PDD-104.
- Wave 35 finding count: 29.
- Source artifact:
  `_build/diagnostics/pass2/phase_34_5_operational_recovery_diagnostics.json`
  and the five affected PDD detail JSON artifacts.

Required output artifacts:

- `_build/policy-design-case/rebaseline/wave-35D/operator_root_cause_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35D/restore_drill_bundle.json`
- `_build/policy-design-case/rebaseline/wave-35D/resource_exhaustion_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35D/live_polling_parity_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35D/archive_grade_reproducibility_bundle.json`
- `_build/policy-design-case/rebaseline/wave-35D/phase34_5_rerun.json`
- `_build/policy-design-case/rebaseline/wave-35D/wave35_disposition_update.json`

Work packets:

- [x] Build `operator_root_cause_ledger.json` for PDD-046 with top-level diagnostic command list, scorecard failure breadcrumb rows, first missing producer, upstream cause, downstream impact, owner, missing input, next command, event refs, and timeline refs.
- [x] Normalize Lex, Fabric, Foundry, decision-artifact, Scholar, and record-family failures into first-missing-producer chains. A generic failed gate without this chain does not close PDD-046.
- [x] Build `restore_drill_bundle.json` for PDD-077 with retained-copy hashes, archive hash verification, corruption injection, recovery result, restored dashboard verification, restored lineage verification, restored scorecard verification, restored final-artifact verification, operator, timestamp, and command log.
- [x] Build `resource_exhaustion_ledger.json` for PDD-078 with rate limit, circuit breaker, timeout, byte limit, token limit, cost limit, memory limit, queue limit, degradation behavior, partial-evidence negative scenario, downstream claim impact, and scorecard impact.
- [x] Build `live_polling_parity_ledger.json` for PDD-090 with SSE/WebSocket cursor state, replay cursor, polling snapshot, snapshot hash trail, dropped/reordered/reconnect scenarios, governance wait parity, terminal-state parity, and operator-visible fallback explanation.
- [x] Build `archive_grade_reproducibility_bundle.json` for PDD-104 with decision bundle, legal/data/model/provider/source/version/trust-store snapshots, verifier, timestamp, signature, lockfile, schema refs, redaction refs, long-horizon restore/replay drill, retention jurisdiction, deterministic replay inputs, and bounded-drift explanation if exact replay is impossible.
- [x] Rerun Phase 34.5 with `uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_5.py` and then `uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py --repo-root .`.
- [x] Write `phase34_5_rerun.json` with command, exit code, output hashes, and before/after status for PDD-046, PDD-077, PDD-078, PDD-090, and PDD-104.
- [x] Update Wave 35 disposition evidence for all 29 affected findings.

### Wave 35D Exit Fence

- [x] Operator root-cause evidence identifies the first missing producer and exact next command for every failed class.
- [x] Restore drill evidence proves retained-copy verification, corruption recovery, and restored dashboard/lineage/scorecard/final artifact.
- [x] Resource exhaustion evidence proves typed limits, degradation semantics, partial-evidence negative scenarios, and claim/scorecard impact mapping.
- [x] Live/polling parity evidence proves cursor replay, snapshot hash, reconnect behavior, governance wait, terminal state, and fallback explanation.
- [x] Archive-grade evidence proves long-term verification, retention jurisdiction, durable replay inputs, and either deterministic replay or typed bounded drift.
- [x] Phase 34.5 rerun evidence is captured under `_build/policy-design-case/rebaseline/wave-35D/`.
- [x] No `operational_recovery_resource_and_archive_readiness` disposition remains `next_plan_remediation` or `accepted_blocker`.

## Wave 35E - Human-Facing Legitimacy, Memory, And Trust Remediation

Purpose: fully satisfy the Wave 35
`human_facing_legitimacy_memory_and_trust_controls` cluster before deterministic
closeout begins.

Parallel phases in this wave:

Wave 35E intentionally has a single phase. Projection consistency, operator
truthfulness, memory authority, implementation feasibility, contestability, and
trust framing all determine whether human-facing surfaces can honestly display
the case.

### Phase 35E.1 - Projection, Memory, Legitimacy, And Trust Controls

Affected findings:

- Cluster: `human_facing_legitimacy_memory_and_trust_controls`.
- PDDs: PDD-034, PDD-069, PDD-083, PDD-097, PDD-099, PDD-103.
- Wave 35 finding count: 19.
- Source artifact:
  `_build/diagnostics/pass2/phase_34_6_human_facing_legitimacy_memory_diagnostics.json`
  and the six affected PDD detail JSON artifacts.

Required output artifacts:

- `_build/policy-design-case/rebaseline/wave-35E/projection_operator_truthfulness_matrix.json`
- `_build/policy-design-case/rebaseline/wave-35E/memory_authority_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35E/implementation_feasibility_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35E/contestability_appeals_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35E/trust_framing_ui_negative_tests.json`
- `_build/policy-design-case/rebaseline/wave-35E/phase34_6_rerun.json`
- `_build/policy-design-case/rebaseline/wave-35E/wave35_disposition_update.json`

Work packets:

- [x] Build `projection_operator_truthfulness_matrix.json` for PDD-034 and PDD-069 with API state, dashboard state, readiness state, scorecard blocker state, failed/warn/pass/override/stale/reissued/withdrawn rows, dashboard-to-readiness diff, failure class journey, projection masking negative controls, and denominator caveats.
- [x] Dashboard/API projection must fail closed when labels mask missing, stale, conflicting, reissued, withdrawn, non-authoritative, or projection-only evidence.
- [x] Build `memory_authority_ledger.json` for PDD-083 with memory-used or no-memory decision, memory source, tenant scope, freshness, confidence, contamination checks, prompt/tool refs, replay refs, and authority decision. Empty replay surfaces do not close this finding.
- [x] Build `implementation_feasibility_ledger.json` for PDD-097 with recommendation id, implementation actor, feasibility evidence, risk evidence, monitoring evidence, source refs, method refs, norm refs, and claim binding. Generic final text is not enough.
- [x] Build `contestability_appeals_ledger.json` for PDD-099 with standing, grounds, deadline, submitted evidence, owner, SLA, disposition, outcome refs, lifecycle transition, reissue/stale/withdrawal impact, and monitoring changes.
- [x] Build `trust_framing_ui_negative_tests.json` for PDD-103 with label, icon, color, badge, copy, confidence label, signature cue, authority caveat, zero-review caveat, low-confidence scenario, disputed scenario, untraced scenario, simulated scenario, stale scenario, draft scenario, override-approved scenario, frontend-signed scenario, expected UI state, observed UI state, and screenshot or trace ref.
- [x] Rerun Phase 34.6 with `uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_6.py` and then `uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py --repo-root .`.
- [x] Write `phase34_6_rerun.json` with command, exit code, output hashes, and before/after status for PDD-034, PDD-069, PDD-083, PDD-097, PDD-099, and PDD-103.
- [x] Update Wave 35 disposition evidence for all 19 affected findings.

### Wave 35E Exit Fence

- [x] Projection evidence covers failed, warn, pass, override, stale, reissued, and withdrawn states across API, dashboard, readiness, and scorecard surfaces.
- [x] Operator truthfulness evidence includes dashboard-to-readiness diff, failure-class journey coverage, and zero-denominator human-review caveats.
- [x] Memory evidence explicitly proves memory use authority or no-memory abstention with contamination checks.
- [x] Implementation feasibility and contestability evidence are runtime ledgers, not generic final narrative text.
- [x] Trust-framing evidence includes UI negative tests for low-confidence, disputed, untraced, simulated, stale, draft, override-approved, and frontend-signed states.
- [x] Phase 34.6 rerun evidence is captured under `_build/policy-design-case/rebaseline/wave-35E/`.
- [x] No `human_facing_legitimacy_memory_and_trust_controls` disposition remains `next_plan_remediation` or `accepted_blocker`.

## Wave 35F - Remediation Integrity And Runtime Enforcement Gate

Purpose: prevent deterministic closeout from treating Wave 35A-35E remediation
ledgers as stronger evidence than they are. Wave 35F classifies every Wave
35A-35E remediation artifact by authority class, identifies synthetic or
manual evidence that still needs runtime enforcement, and blocks Wave 36 until
closeout-critical overlay evidence is either backed by runtime/test-observed
proof or explicitly excluded from closeout authority.

Parallel phases in this wave:

Wave 35F intentionally has a single phase. The output is a cross-wave
integrity gate: it reads all Wave 35A-35E outputs, the Wave 35 disposition,
and the affected Phase 34 rerun artifacts before deterministic closeout can
start.

### Phase 35F.1 - Evidence Authority Classification And Enforcement Backfill

Affected inputs:

- Waves: Wave 35A, Wave 35B, Wave 35C, Wave 35D, and Wave 35E.
- Source artifacts:
  `_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json`,
  every `_build/policy-design-case/rebaseline/wave-35A/` through
  `_build/policy-design-case/rebaseline/wave-35E/` output artifact, and the
  Phase 34.1-34.6 rerun summaries captured under those directories.
- Decision-log basis: DL-PDC-0014.

Required output artifacts:

- `_build/policy-design-case/rebaseline/wave-35F/remediation_integrity_classification.json`
- `_build/policy-design-case/rebaseline/wave-35F/runtime_enforcement_gap_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35F/wave35e_human_surface_enforcement_audit.json`
- `_build/policy-design-case/rebaseline/wave-35F/wave35_runtime_evidence_authority_map.json`
- `_build/policy-design-case/rebaseline/wave-35F/wave35f_disposition_integrity_report.json`
- `_build/policy-design-case/rebaseline/wave-35F/wave35f_exit_fence.json`

Work packets:

- [x] Build `remediation_integrity_classification.json` with one row per Wave 35A-35E remediated `finding_id` and implementation artifact. Each row must include wave, cluster id, PDD id, finding id, artifact path, evidence authority class, source refs, rerun ref, reviewer command, and whether the evidence may count toward deterministic closeout.
- [x] Use only these evidence authority classes: `runtime_emitted`, `runtime_derived`, `test_observed`, `synthetic_remediation_overlay`, and `manual_assertion`. Any unknown class fails the gate.
- [x] Build `wave35_runtime_evidence_authority_map.json` mapping every Wave 35A-35E artifact to its upstream runtime, test, diagnostic, or manual source. The map must distinguish runtime-produced facts from remediation overlays that merely describe expected behavior.
- [x] Build `runtime_enforcement_gap_ledger.json` for every closeout-critical row classified as `synthetic_remediation_overlay` or `manual_assertion`. Each gap row must include missing runtime/API/UI enforcement, affected code or artifact path, owner, required test or trace, accepted boundary if any, and Wave 36 blocking decision.
- [x] Build `wave35e_human_surface_enforcement_audit.json` for Dashboard/API projection, memory/no-memory authority, implementation feasibility, contestability, and trust-framing evidence. It must prove each closeout-critical human-facing claim is either `runtime_emitted` or `test_observed`, or mark it `not_closeout_authority` with an explicit caveat.
- [x] For Dashboard/API projection controls, require schema or runtime enforcement evidence that projections fail closed when labels mask missing, stale, conflicting, reissued, withdrawn, non-authoritative, or projection-only evidence. Matrix rows alone are insufficient for closeout authority.
- [x] For trust-framing controls, require actual UI negative test traces or screenshots for low-confidence, disputed, untraced, simulated, stale, draft, override-approved, and frontend-signed states, or mark the Wave 35E ledger as an overlay that cannot satisfy Wave 36.
- [x] For memory controls, require a runtime-emitted no-memory abstention record or memory-use authority record before serious output influence; an empty replay surface remains insufficient unless paired with explicit runtime abstention.
- [x] For implementation feasibility and contestability controls, require runtime-owned ledger provenance or an accepted boundary that prevents final publication/closeout from relying on the ledger as institutional proof.
- [x] Add or update `tools/quality/validation/check_policy_design_case_wave35f_integrity.py` so it fails when any closeout-critical row remains `synthetic_remediation_overlay` or `manual_assertion` without an accepted boundary that blocks Wave 36.
- [x] Run `uv run python tools/quality/validation/check_policy_design_case_wave35f_integrity.py --repo-root .`.
- [x] Run `uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py --repo-root . --require-passing --require-closeout-ready`.
- [x] Write `wave35f_disposition_integrity_report.json` with command, exit code, output hashes, artifact classification counts, unresolved closeout-critical overlay rows, and reviewer command.
- [x] Write `wave35f_exit_fence.json` with the final Wave 35F status and the exact Wave 36 blocking or release decision.

### Wave 35F Exit Fence

- [x] `remediation_integrity_classification.json` covers every Wave 35A-35E remediated finding and every implementation artifact referenced by Wave 35 disposition evidence.
- [x] No closeout-critical artifact remains `synthetic_remediation_overlay` or `manual_assertion` unless `runtime_enforcement_gap_ledger.json` records an accepted boundary that blocks Wave 36 from using it as closeout evidence.
- [x] Wave 35E human-facing controls that affect public, operator, API, memory, or trust surfaces are backed by runtime enforcement, actual test traces/screenshots, or explicit `not_closeout_authority` caveats.
- [x] `check_policy_design_case_wave35f_integrity.py --repo-root .` passes.
- [x] `wave35f_exit_fence.json` reports `status=pass` and `wave36_release_decision=allowed`, or Wave 36 remains blocked with named gap rows.
- [x] Wave 36 entry criteria include Wave 35F and cannot be satisfied by Wave 35A-35E remediation overlays alone.

## Wave 35G - Human Surface Runtime Evidence Backfill And Release Gate

Purpose: clear the named Wave 35F Wave 36 release blockers without weakening the
integrity gate. Wave 35G backfills runtime/test-observed proof for the 19
human-facing blockers from Wave 35F, or records enforceable exclusion boundaries
where institutional ledgers must not be used as closeout authority. Wave 36 may
start only after Wave 35G passes and a refreshed Wave 35F exit fence reports
`wave36_release_decision=allowed`.

Parallel phases in this wave:

Wave 35G has four independent backfill phases that can run in parallel because
they touch distinct authority surfaces and evidence artifacts:

- Phase 35G.1: Dashboard/API projection fail-closed runtime backfill.
- Phase 35G.2: Memory authority runtime abstention backfill.
- Phase 35G.3: Trust-framing UI negative trace backfill.
- Phase 35G.4: Implementation feasibility and contestability provenance boundary
  backfill.

Phase 35G.5 is intentionally sequential. It must run only after Phases 35G.1
through 35G.4 finish, because it regenerates Wave 35E evidence, refreshes Wave
35F classification, and decides whether Wave 36 is released or remains blocked.

### Phase 35G.1 - Projection Fail-Closed Runtime/API/UI Backfill

Affected inputs:

- Wave 35F blockers: `PDD-034-F001`, `PDD-034-F002`, `PDD-034-F003`,
  `PDD-069-F001`, `PDD-069-F002`, and `PDD-069-F003`.
- Source artifacts:
  `_build/policy-design-case/rebaseline/wave-35F/runtime_enforcement_gap_ledger.json`,
  `_build/policy-design-case/rebaseline/wave-35E/projection_operator_truthfulness_matrix.json`,
  `apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts`,
  `apps/runtime-dashboard/src/features/runs/domain/publicationPacket.test.ts`,
  `apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.test.tsx`,
  and the runtime API projection schema/validator artifacts that feed the
  public/operator dashboard.

Required output artifact:

- `_build/policy-design-case/rebaseline/wave-35G/projection_fail_closed_runtime_backfill.json`

Work packets:

- [x] Add or update runtime/API projection validation so projection labels fail
  closed when labels mask missing, stale, conflicting, reissued, withdrawn,
  non-authoritative, or projection-only evidence.
- [x] Add tests that observe the failure at the runtime/API boundary and at the
  dashboard/public projection boundary; matrix rows alone remain insufficient.
- [x] Record one evidence row per masking case with evidence authority
  `runtime_emitted` or `test_observed`, source refs, command, exit code, and
  trace or assertion refs.
- [x] Preserve the Wave 35F rule that projection overlays may not count toward
  deterministic closeout unless this runtime/test-observed backfill is present.

### Phase 35G.2 - Memory Authority Runtime Abstention Backfill

Affected inputs:

- Wave 35F blockers: `PDD-083-F001`, `PDD-083-F002`, and `PDD-083-F003`.
- Source artifacts:
  `_build/policy-design-case/rebaseline/wave-35F/runtime_enforcement_gap_ledger.json`,
  `_build/policy-design-case/rebaseline/wave-35E/memory_authority_ledger.json`,
  scientist orchestration memory applicability, contamination, retrieval, and
  serious-run prompt/tool authority surfaces.

Required output artifact:

- `_build/policy-design-case/rebaseline/wave-35G/memory_authority_runtime_abstention_trace.json`

Work packets:

- [x] Emit a runtime-owned memory authority record before serious output
  influence. The record must distinguish `no_memory_abstention` from
  `memory_use_authority`.
- [x] Prove an empty replay surface is not accepted as memory abstention unless
  paired with the explicit runtime-owned abstention record.
- [x] Add tests for serious-output memory abstention and memory-use authority
  handoff ordering.
- [x] Record contamination, tenant scope, prompt/tool authority refs, and
  reviewer commands in the Wave 35G artifact.

### Phase 35G.3 - Trust-Framing UI Negative Trace Backfill

Affected inputs:

- Wave 35F blockers: `PDD-103-F001`, `PDD-103-F002`, `PDD-103-F003`, and
  `PDD-103-F004`.
- Source artifacts:
  `_build/policy-design-case/rebaseline/wave-35F/runtime_enforcement_gap_ledger.json`,
  `_build/policy-design-case/rebaseline/wave-35E/trust_framing_ui_negative_tests.json`,
  runtime-dashboard component tests, and Playwright journeys for public/operator
  trust surfaces.

Required output artifact:

- `_build/policy-design-case/rebaseline/wave-35G/trust_framing_ui_negative_trace_bundle.json`

Work packets:

- [x] Capture actual UI negative test traces or screenshots for low-confidence,
  disputed, untraced, simulated, stale, draft, override-approved, and
  frontend-signed states.
- [x] Assert that each UI state renders a visible caveat and does not promote
  frontend signatures, badges, labels, or projections to closeout authority.
- [x] Store trace or screenshot refs, test command, exit code, and per-scenario
  authority classification as `test_observed`.
- [x] Keep Wave 36 blocked if any required trust-framing scenario remains only a
  synthetic remediation overlay.

### Phase 35G.4 - Institutional Provenance Boundary Backfill

Affected inputs:

- Wave 35F blockers: `PDD-097-F001`, `PDD-097-F002`, `PDD-097-F003`,
  `PDD-099-F001`, `PDD-099-F002`, and `PDD-099-F003`.
- Source artifacts:
  `_build/policy-design-case/rebaseline/wave-35F/runtime_enforcement_gap_ledger.json`,
  `_build/policy-design-case/rebaseline/wave-35E/implementation_feasibility_ledger.json`,
  `_build/policy-design-case/rebaseline/wave-35E/contestability_appeals_ledger.json`,
  publication readiness, continuous governance lifecycle, public export, and
  runtime provenance surfaces.

Required output artifact:

- `_build/policy-design-case/rebaseline/wave-35G/institutional_provenance_boundary_ledger.json`

Work packets:

- [x] Back implementation feasibility rows with runtime-owned provenance, or
  record an enforceable boundary that prevents publication/closeout from relying
  on the ledger as institutional proof.
- [x] Back contestability and appeals rows with runtime-owned lifecycle outcome
  provenance, or record an enforceable boundary that excludes the ledger from
  closeout authority.
- [x] Add tests proving final publication and deterministic closeout cannot use
  manual feasibility or contestability ledgers unless runtime-owned provenance
  is present.
- [x] Record which rows are `runtime_emitted`, `runtime_derived`,
  `test_observed`, or `not_closeout_authority` with explicit caveats.

### Phase 35G.5 - Integration Rerun And Wave 36 Release Fence

Affected inputs:

- Outputs from Phases 35G.1 through 35G.4.
- `_build/policy-design-case/rebaseline/wave-35E/` human-facing artifacts.
- `_build/policy-design-case/rebaseline/wave-35F/` integrity artifacts.
- Phase 34.6 diagnostics and Wave 35 disposition.

Required output artifacts:

- `_build/policy-design-case/rebaseline/wave-35G/phase34_6_rerun_after_backfill.json`
- `_build/policy-design-case/rebaseline/wave-35G/wave35g_backfill_integrity_report.json`
- `_build/policy-design-case/rebaseline/wave-35G/wave35g_exit_fence.json`

Work packets:

- [x] Add `tools/quality/validation/build_policy_design_case_wave35g_backfill.py`
  to build all Wave 35G artifacts from runtime/test outputs and accepted
  exclusion boundaries.
- [x] Add `tools/quality/validation/check_policy_design_case_wave35g_backfill.py`
  to fail when any of the 19 Wave 35F release blockers lacks runtime/test
  evidence or an enforceable non-closeout-authority boundary.
- [x] Regenerate or update Wave 35E human-facing artifacts so runtime/test
  backfill is visible to Wave 35F classification.
- [x] Rerun Phase 34.6 and capture the rerun under
  `_build/policy-design-case/rebaseline/wave-35G/phase34_6_rerun_after_backfill.json`.
- [x] Rerun Wave 35F classification after Wave 35G backfill and require
  `_build/policy-design-case/rebaseline/wave-35F/wave35f_exit_fence.json` to
  report `status=pass` and `wave36_release_decision=allowed`.
- [x] Run `uv run python tools/quality/validation/check_policy_design_case_wave35g_backfill.py --repo-root .`.
- [x] Run `uv run python tools/quality/validation/check_policy_design_case_wave35f_integrity.py --repo-root .`.
- [x] Run `uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py --repo-root . --require-passing --require-closeout-ready`.
- [x] Write `wave35g_backfill_integrity_report.json` with command, exit code,
  output hashes, blocker closure counts, remaining blocker rows, and reviewer
  command.
- [x] Write `wave35g_exit_fence.json` with final Wave 35G status and exact Wave
  36 release or blocking decision.

### Wave 35G Exit Fence

- [x] All 19 Wave 35F Wave 36 release blockers are covered by Wave 35G artifacts.
- [x] Dashboard/API projection controls have runtime/API/UI fail-closed evidence
  for missing, stale, conflicting, reissued, withdrawn, non-authoritative, and
  projection-only evidence.
- [x] Memory controls include a runtime-emitted no-memory abstention or
  memory-use authority record before serious output influence.
- [x] Trust-framing controls include actual UI negative traces or screenshots for
  low-confidence, disputed, untraced, simulated, stale, draft, override-approved,
  and frontend-signed states.
- [x] Implementation feasibility and contestability rows are backed by
  runtime-owned provenance or enforceable non-closeout-authority boundaries.
- [x] `check_policy_design_case_wave35g_backfill.py --repo-root .` passes.
- [x] Refreshed `check_policy_design_case_wave35f_integrity.py --repo-root .`
  passes.
- [x] Refreshed
  `_build/policy-design-case/rebaseline/wave-35F/wave35f_exit_fence.json`
  reports `status=pass` and `wave36_release_decision=allowed`.
- [x] `_build/policy-design-case/rebaseline/wave-35G/wave35g_exit_fence.json`
  reports `status=pass` and `wave36_release_decision=allowed`, or Wave 36
  remains blocked with named gap rows.

## Wave 35H - Institutional Provenance Runtime Ownership

Purpose: genuinely close the six Wave 35G institutional-provenance boundary
candidates instead of leaving them as `not_closeout_authority` ledgers. Wave 35H
makes implementation-feasibility and contestability/appeals provenance
runtime-owned, so the Wave 35E manual ledgers are replaced by runtime-emitted
evidence and the Wave 35G boundary clears on real proof rather than on an
accepted exclusion. Wave 40 final readiness and publication may not treat the
institutional ledgers as proof until Wave 35H passes.

Scheduling:

Wave 35H may start once Wave 35G passes. It may run in parallel with Waves 36,
37, 38, and 39 because it touches publication-readiness and
governance-lifecycle runtime surfaces that the deterministic canary matrix,
runtime API contract, local integration stack, and dashboard journey smoke do
not exercise. Wave 35H is not a Wave 36 release blocker; the Wave 35G boundary
already keeps Wave 36 from relying on the manual ledgers. Wave 35H must complete
before Wave 40.

Parallel phases in this wave:

- Phase 35H.1: Implementation-feasibility runtime provenance producer.
- Phase 35H.2: Contestability and appeals lifecycle runtime provenance producer.

Phase 35H.3 is sequential. It must run only after Phases 35H.1 and 35H.2 finish,
because it regenerates the Wave 35E ledgers from runtime emission, reruns Wave
35F and Wave 35G classification, and decides the Wave 40 authority fence.

### Phase 35H.1 - Implementation Feasibility Runtime Provenance Producer

Affected inputs:

- Wave 35G boundary findings: `PDD-097-F001`, `PDD-097-F002`, `PDD-097-F003`.
- Source artifacts:
  `_build/policy-design-case/rebaseline/wave-35G/institutional_provenance_boundary_ledger.json`,
  `_build/policy-design-case/rebaseline/wave-35E/implementation_feasibility_ledger.json`,
  the publication-readiness and continuous-governance-lifecycle runtime
  surfaces, and the claim-authority binding artifacts the feasibility rows
  reference.
- Decision-log basis: DL-PDC-0015.

Required output artifact:

- `_build/policy-design-case/rebaseline/wave-35H/implementation_feasibility_runtime_provenance.json`

Work packets:

- [x] Add a runtime producer that emits one implementation-feasibility
  provenance record per serious recommendation. Each record must carry
  producer, event refs, artifact refs, claim binding, actor, risk, and
  monitoring-outcome refs - the exact field set the Wave 35G boundary requires.
- [x] Emit the feasibility record during a serious run, not as a build-time
  overlay; an empty or build-only record must fail closed.
- [x] Add runtime/API tests that observe feasibility provenance emission and
  fail when producer, claim binding, or monitoring-outcome refs are missing.
- [x] Record one evidence row per finding with evidence authority
  `runtime_emitted` or `runtime_derived`, source refs, command, exit code, and
  trace refs.

### Phase 35H.2 - Contestability And Appeals Lifecycle Runtime Provenance Producer

Affected inputs:

- Wave 35G boundary findings: `PDD-099-F001`, `PDD-099-F002`, `PDD-099-F003`.
- Source artifacts:
  `_build/policy-design-case/rebaseline/wave-35G/institutional_provenance_boundary_ledger.json`,
  `_build/policy-design-case/rebaseline/wave-35E/contestability_appeals_ledger.json`,
  the contestability/appeals lifecycle runtime surface, and the
  publication-state surfaces an appeal outcome can affect.
- Decision-log basis: DL-PDC-0015.

Required output artifact:

- `_build/policy-design-case/rebaseline/wave-35H/contestability_appeals_runtime_provenance.json`

Work packets:

- [x] Add a runtime producer that emits one contestability lifecycle outcome
  provenance record per appeal. Each record must carry producer, event refs,
  artifact refs, appeal disposition, lifecycle transition, and publication-state
  effect.
- [x] Cover the three Wave 35E appeal rows - `appeal-msme-standing-001`,
  `appeal-auditor-trace-002`, and `appeal-withdrawal-003` - with runtime-owned
  lifecycle outcome provenance for standing, auditor-trace, and withdrawal
  dispositions.
- [x] Add tests that observe appeal lifecycle emission and prove a manual or
  empty appeal ledger cannot stand in for runtime-owned outcome provenance.
- [x] Record one evidence row per finding with evidence authority
  `runtime_emitted` or `runtime_derived`, source refs, command, exit code, and
  trace refs.

### Phase 35H.3 - Ledger Regeneration And Wave 40 Authority Fence

Affected inputs:

- Outputs from Phases 35H.1 and 35H.2.
- `_build/policy-design-case/rebaseline/wave-35E/implementation_feasibility_ledger.json`
  and `_build/policy-design-case/rebaseline/wave-35E/contestability_appeals_ledger.json`.
- `_build/policy-design-case/rebaseline/wave-35F/` integrity artifacts and
  `_build/policy-design-case/rebaseline/wave-35G/` backfill artifacts.

Required output artifacts:

- `_build/policy-design-case/rebaseline/wave-35H/institutional_provenance_runtime_ownership_ledger.json`
- `_build/policy-design-case/rebaseline/wave-35H/wave35h_provenance_integrity_report.json`
- `_build/policy-design-case/rebaseline/wave-35H/wave35h_exit_fence.json`

Work packets:

- [x] Add `tools/quality/validation/build_policy_design_case_wave35h_provenance.py`
  to build all Wave 35H artifacts from the runtime feasibility and
  contestability producers.
- [x] Regenerate the Wave 35E `implementation_feasibility_ledger.json` and
  `contestability_appeals_ledger.json` so every row carries runtime-emitted
  provenance instead of `manual_assertion`. Do not edit the original Wave 35E
  rows by hand; regenerate them from runtime output and record before/after
  hashes.
- [x] Rerun the Wave 35G Phase 35G.4 institutional-provenance builder and
  require `institutional_provenance_boundary_ledger.json` to report
  `runtime_owned_provenance_count=6` and `not_closeout_authority_count=0`.
- [x] Rerun Wave 35F classification and require every PDD-097 and PDD-099 row to
  classify as `runtime_emitted` or `runtime_derived`, not
  `synthetic_remediation_overlay` or `manual_assertion`.
- [x] Add `tools/quality/validation/check_policy_design_case_wave35h_provenance.py`
  to fail when any of the six Wave 35G boundary findings lacks runtime-owned
  provenance with the full required field set.
- [x] Run `uv run python tools/quality/validation/check_policy_design_case_wave35h_provenance.py --repo-root .`.
- [x] Run `uv run python tools/quality/validation/check_policy_design_case_wave35f_integrity.py --repo-root .`.
- [x] Run `uv run python tools/quality/validation/check_policy_design_case_wave35g_backfill.py --repo-root .`.
- [x] Run `uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py --repo-root . --require-passing --require-closeout-ready`.
- [x] Write `wave35h_provenance_integrity_report.json` with command, exit code,
  output hashes, before/after evidence-authority counts, and reviewer command.
- [x] Write `wave35h_exit_fence.json` with final Wave 35H status and the exact
  Wave 40 authority decision.

### Wave 35H Exit Fence

- [x] All six Wave 35G institutional-provenance boundary findings - PDD-097-F001,
  PDD-097-F002, PDD-097-F003, PDD-099-F001, PDD-099-F002, and PDD-099-F003 - are
  backed by runtime-owned provenance.
- [x] The regenerated Wave 35E feasibility and contestability ledgers carry
  runtime-emitted provenance, and no row remains `manual_assertion`.
- [x] `institutional_provenance_runtime_ownership_ledger.json` reports
  `runtime_owned_provenance_count=6` and `not_closeout_authority_count=0`.
- [x] `check_policy_design_case_wave35h_provenance.py --repo-root .` passes.
- [x] Refreshed `check_policy_design_case_wave35f_integrity.py --repo-root .` and
  `check_policy_design_case_wave35g_backfill.py --repo-root .` still pass.
- [x] `wave35h_exit_fence.json` reports `status=pass` and
  `wave40_authority_decision=allowed`, or Wave 40 keeps the institutional
  ledgers out of final-publication authority with named gap rows.

## Wave 36 - Deterministic Canary Matrix Closeout

Purpose: prove deterministic serious lanes after Pass 2 diagnostics.

Parallel phases in this wave:

### Wave 36 Entry Criteria

- [x] `uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py --repo-root . --require-passing` passes.
- [x] `uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py --repo-root . --require-passing --require-closeout-ready` passes.
- [x] `uv run python tools/quality/validation/check_policy_design_case_wave35f_integrity.py --repo-root .` passes.
- [x] `uv run python tools/quality/validation/check_policy_design_case_wave35g_backfill.py --repo-root .` passes.
- [x] `_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json` reports zero unresolved `must_fix_before_closeout` findings.
- [x] `_build/policy-design-case/rebaseline/wave-35F/wave35f_exit_fence.json` reports `status=pass` and `wave36_release_decision=allowed`.
- [x] `_build/policy-design-case/rebaseline/wave-35G/wave35g_exit_fence.json` reports `status=pass` and `wave36_release_decision=allowed`.
- [x] Wave 35A, Wave 35B, Wave 35C, Wave 35D, Wave 35E, Wave 35F, and Wave 35G exit fences are complete, or a later decision-log entry supersedes the affected Wave 35 cluster with equivalent blocking force before Wave 36 starts.
- [x] Accepted blockers and `next_plan_remediation` items from Wave 35 cannot be counted as deterministic closeout evidence unless their target remediation wave has rerun the affected Phase 34 diagnostic.
- [x] Wave 35A-35E remediation artifacts classified as `synthetic_remediation_overlay` or `manual_assertion` cannot be counted as deterministic closeout evidence unless Wave 35F records runtime/test-observed backfill or an explicit boundary that keeps the affected evidence out of Wave 36.
- [x] Wave 35F human-surface release blockers cannot be cleared by Wave 35A-35E
  overlays alone; Wave 35G runtime/test backfill or enforceable
  non-closeout-authority boundaries must be present.

### Phase 36.1 - Deterministic Canary Matrix

- [x] Run deterministic canary matrix.
- [x] Confirm dev smoke remains explicit and cannot satisfy serious closeout.

### Wave 36 Exit Fence

- [x] Deterministic matrix passes with serious scorecards `pass`.

## Wave 37 - Runtime API Contract Closeout

Purpose: prove runtime API contract behavior without sharing local resources
with other closeout commands.

Parallel phases in this wave:

### Phase 37.1 - Runtime API Contract Check

- [x] Run runtime API contract check.

### Wave 37 Exit Fence

- [x] Runtime API contract passes.

## Wave 38 - Local Integration Stack Smoke

Purpose: prove the local stack smoke in isolation.

Parallel phases in this wave:

### Phase 38.1 - Local Integration Stack Smoke

- [x] Run local integration stack smoke.

### Wave 38 Exit Fence

- [x] Local integration stack smoke passes.

## Wave 39 - Dashboard Journey Smoke

Purpose: prove dashboard projection behavior after runtime and local stack
closeout.

Parallel phases in this wave:

### Phase 39.1 - Dashboard Journey Smoke

- [x] Run dashboard journey smoke.

### Wave 39 Exit Fence

- [x] Dashboard smoke passes.

## Wave 40 - Readiness Aggregator And Bundle Inspection

Purpose: prove final readiness and public bundle integrity after all closeout
commands have fresh evidence.

Parallel phases in this wave:

### Wave 40 Entry Criteria

- [x] `_build/policy-design-case/rebaseline/wave-35H/wave35h_exit_fence.json` reports `status=pass` and `wave40_authority_decision=allowed`.
- [x] `uv run python tools/quality/validation/check_policy_design_case_wave35h_provenance.py --repo-root .` passes.
- [x] No implementation-feasibility or contestability/appeals ledger row remains `manual_assertion` or `not_closeout_authority`; the institutional ledgers are runtime-owned before final publication can rely on them.

### Phase 40.1 - Readiness Aggregator And Bundle Inspection

- [x] Run final readiness with `--require-passing` and matrix evidence.
- [x] Inspect selected serious bundles for Policy Design Case records and public leakage.
- [x] Confirm static inventory remains a producer map, not runtime evidence.
- [x] Confirm every SDD record-family row maps to runtime evidence, typed blocker, or typed out-of-scope authority policy.
- [x] Confirm every Pass 1B row maps to evidence contract, owner, scorecard/readiness gate, and final status.

### Wave 40 Exit Fence

- [x] Readiness aggregator passes with zero serious failures.
- [x] Policy Design Case coverage meets final targets.
- [x] Anti-drift audit passes with zero Non-Goal violations.
- [x] Implementation-feasibility and contestability/appeals records are backed by runtime-owned provenance, not manual ledgers.

## Wave 41 - Documentation, Runbooks, Archive, And Handoff

Purpose: close documentation only after final evidence is recorded and reviewed.

Parallel phases in this wave:

### Phase 41.1 - Documentation, Runbooks, Archive, And Handoff

- [x] Update the SDD only for real decision changes.
- [x] Merge generated backlog-summary fragments into `docs/backlog/production-data-e2e-diagnostic-backlog.md` with artifact links.
- [x] Add or supersede ADRs only when cross-component semantics changed.
- [x] Add operator runbooks for missing case, missing intent, missing spine, missing producer refs, portfolio divergence, synthesis fragility, unsupported claim, BERL failure, DDM failure, and external audit failure.
- [x] Add operator runbooks for self-FMEA failure, maturity regression, missing formal invariant, missing consultation response, hidden expert judgement, proportionality failure, and benchmarking failure.
- [x] Archive this plan only after final closeout evidence is recorded and reviewed.

### Wave 41 Exit Fence

- [x] Decision log has no unresolved exception whose revisit wave is at or before Wave 41.
- [x] Final documentation reflects implementation without hiding remaining limitations.
- [x] This plan is archived only after final evidence paths are recorded.

## Validation Ladder

Use this ladder after each wave.

### Fast Contract Loop

```bash
uv run pytest tests/unit/runtime/quality -q
uv run pytest tests/unit/tools/test_canary_evidence.py -q
uv run python tools/quality/validation/check_honest_diagnostics_proof_harness.py --repo-root .
uv run python tools/quality/validation/check_substrate_drift.py --repo-root .
uv run python tools/quality/validation/check_policy_design_case_drift.py --repo-root .
uv run python tools/quality/validation/build_policy_design_case_coverage.py --repo-root . --output-dir _build/policy-design-case/coverage
```

### Runtime And Case Loop

```bash
uv run pytest tests/unit/runtime/http/test_nl_pipeline_materialization.py tests/unit/runtime/quality tests/unit/tools/test_canary_evidence.py -q
uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py tests/repo_quality/tools/test_canary_matrix.py -q
uv run pytest tests/repo_quality/tools/test_honest_diagnostics_proof_harness.py -q
uv run pytest tests/repo_quality/tools/test_honest_diagnostics_substrate_drift.py tests/repo_quality/tools/test_honest_diagnostics_coverage.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_coverage.py tests/repo_quality/tools/test_policy_design_case_drift.py tests/repo_quality/tools/test_policy_design_case_walking_skeleton.py -q
```

### Producer And Portfolio Loop

```bash
uv run pytest tests/unit/lex tests/unit/fabric tests/unit/scholar tests/unit/foundry tests/unit/scientist -q
uv run pytest tests/unit/runtime/quality/test_policy_intent.py tests/unit/runtime/quality/test_concept_spine.py tests/unit/runtime/quality/test_evidence_portfolio.py tests/unit/runtime/quality/test_claim_argument.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_producer_contracts.py tests/repo_quality/tools/test_policy_design_case_portfolio.py -q
```

### Security, Performance, Resilience, And Audit Loop

```bash
uv run pytest tests/security/test_policyos_runtime_abuse_gates.py tests/performance/test_runtime_hot_paths.py tests/repo_quality/tools/test_runtime_resilience_matrix.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py tests/repo_quality/tools/test_policy_design_case_external_audit.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_self_fmea.py tests/repo_quality/tools/test_policy_design_case_formal_invariants.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_pass1b_hardening.py tests/repo_quality/tools/test_policy_design_case_benchmarking.py tests/repo_quality/tools/test_policy_design_case_pass2_disposition.py -q
```

### Full Closeout Loop

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py --deterministic --json-output _build/.tmp/production-quality/final_deterministic_matrix.json --timeout-s 1200
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run python tools/quality/testing/local_integration_stack.py smoke
corepack pnpm --dir apps/runtime-dashboard run test:journeys:smoke
uv run python tools/quality/validation/check_honest_diagnostics_proof_harness.py --repo-root .
uv run python tools/quality/validation/check_substrate_drift.py --repo-root .
uv run python tools/quality/validation/check_policy_design_case_drift.py --repo-root .
uv run python tools/quality/validation/build_policy_design_case_coverage.py --repo-root . --output-dir _build/policy-design-case/coverage --require-targets
uv run python tools/quality/validation/check_policy_design_case_pass1b_hardening.py --repo-root . --require-passing
uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py --repo-root . --require-passing --require-closeout-ready
uv run python tools/quality/validation/check_policy_design_case_wave35h_provenance.py --repo-root .
uv run python tools/quality/validation/check_policy_design_case_formal_invariants.py --repo-root . --require-passing
uv run python tools/quality/validation/inspect_evidence_bundles.py --repo-root . --matrix-run-json _build/.tmp/production-quality/final_deterministic_matrix.json --json-output _build/.tmp/production-quality/final_evidence_bundle_inspection.json --require-passing
uv run python tools/ci/check_policyos_production_quality_best_in_class.py --repo-root . --matrix-run-json _build/.tmp/production-quality/final_deterministic_matrix.json --output _build/.tmp/production-quality/final_readiness.json --output-format json --require-passing
uv run pytest tests/repo_quality/tools/test_docs_gate.py tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_generate_adr_index.py -q
```

## Acceptance Checklist By Diagnostic Group

| Diagnostic group | Covered by waves | Acceptance signal |
|------------------|------------------|-------------------|
| Pass 1A critical path: PDD-010, PDD-062, PDD-007, PDD-011, PDD-047 | Waves 3-11 | intent, capability, concept spine, ontology reconciliation, and normalization trace are runtime-owned |
| Walking skeleton integration risk | Waves 6-7 | a minimal case proves intent-to-claim refs and scorecard/readiness behavior before full domain layers |
| Legal authority: PDD-001, PDD-043 | Wave 12.1 | Lex retrieves and binds candidate/selected/rejected norms with jurisdiction/time/competence evidence |
| Data and catalog authority: PDD-002, PDD-008, PDD-014, PDD-042, PDD-052, PDD-074 | Waves 10, 12-14 | Data Forge/Fabric source evidence is field-level, semantic, fresh, lineaged, and claim-bindable |
| Method and objective authority: PDD-004, PDD-049 | Waves 12, 15-20, 30 | Foundry selects methods before execution and objective/tradeoff evidence exists |
| Final claim authority: PDD-005, PDD-006 | Waves 15-25 | major claims have portfolio refs, argument/warrant, counter-evidence, and deficits/blockers |
| Substrate-completed diagnostics | All waves | no ADR-0147-0155 semantics are narrowed |
| Pass 1B static hardening | Waves 1, 3, 24, 27-32, 40 | every Pass 1B PDD maps to a concrete evidence contract, scorecard/readiness gate, and owner |
| SDD governance/legitimacy records | Waves 27, 32, 40 | structured judgement, consultation, human oversight, independence, publication trust, and contestability are first-class evidence |
| SDD integrity/benchmark/formal records | Waves 29-31, 40 | self-FMEA, maturity, benchmarking, proportionality, and formal invariants are generated, gated, and covered |
| Pass 2 behavioral diagnostics | Waves 34-35, 35H | diagnostics run on real domain evidence and findings are remediated, dispositioned, or blocked before closeout; institutional feasibility and contestability provenance is runtime-owned |

## Final Closeout Gate

The plan is complete only when:

- [x] all ADR-0156 through ADR-0165 decision bullets are enforced by runtime code and tests;
- [x] ADR-0162 through ADR-0165 are enforced or explicitly scoped to later plans;
- [x] every minimum Policy Design Case record family has schema owner, producer owner, reader owner, and readiness gate;
- [x] the Full SDD Record-Family Coverage Contract is green;
- [x] the Pass 1B Hardening Coverage Contract is green;
- [x] walking skeleton evidence from Waves 6-7 proves the case ref axis before full closeout;
- [x] every Pass 2 finding has Wave 35 remediation, accepted blocker, next-plan disposition, or false-alarm evidence;
- [x] serious readiness fails when a required case record is missing or static-only;
- [x] major claims fail when they lack portfolio, independence, synthesis, argument, warrant, rebuttal/counter-evidence, accepted deficits, or required BERL reliability;
- [x] structured judgement, consultation, implementation monitoring, DDM, human oversight, self-FMEA, maturity, audit, benchmarking, proportionality, and formal invariant records are present, blocked, or out-of-scope by typed authority policy;
- [x] implementation-feasibility and contestability/appeals records are backed by runtime-owned provenance from Wave 35H, not manual ledgers, before final publication can rely on them;
- [x] public/dashboard/API exports cannot mint authority;
- [x] final closeout loop passes;
- [x] final evidence paths are recorded in this plan or an archive report;
- [x] this plan is moved to `docs/plans/archive/` only after final evidence is reviewed.
