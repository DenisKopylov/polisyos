---
title: PolicyOS Layer 2 S5 Coupling Classifier + Design-Composition Algebra Implementation Plan
status: active
owner: team-foundry-design-composition
created: 2026-05-31
last_verified: null
stability: draft
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
slice: S5
slice_label: coupling_composition
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on: S4
---

# Layer 2 S5 Coupling Classifier + Design-Composition Algebra Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make design composition admissible only after A-side coupling classification proves a modular, near-decomposable, or hierarchically coupled boundary with the right limitations; entangled designs, especially those with `feedback_intensity="high"`, require system-level evidence, dynamics requirements, or downgrade before whole-design authority can be assembled.

**Architecture:** S5 implements D2.6 as an A-side composition gate, not as a new generator. It wraps the existing Foundry coupling and dynamics seeds behind strict runtime-quality contracts, emits replayable `CouplingGraph`, `CouplingRegimeClassification`, `DecompositionResult`, `RecursiveDesignGraph`, `DesignInterfaceContract`, `SystemDynamicsRequirement`, `CompositionReceipt`, and `ComputationalTractabilityBudget` artifacts, with strict nested boundary/discovery/forecast-scope/composition-law records where needed, then injects the composition posture into the S2/S4 shadow design loop as data. The B loop may consume the injected composition receipt and strategy, but it may not self-decompose, average away coupling, accept user-supplied module boundaries as proof, or assemble whole-design authority when P17 has not passed.

**Tech Stack:** Python 3.14, Pydantic v2 strict models (`extra="forbid"`), S0 public PDC contracts from `polisyos.pdc` (`Layer2ReadinessModel`, `AuthorityBoundary`, `AxisPositionDeclaration`, `AxisFirewallStatus`, `EpistemicRegime`, `Audience`), S4 `EpistemicRegimeClaim` and commitment profile records, Foundry seeds (`foundry/coupling/des_kernel.py`, `foundry/methods/catalog/causal/dynamic_graph_dscm.py`, `foundry/methods/catalog/simulation/dynamics.py`), `run_universal_outcome_corpus.py`, pytest, and existing `tools.quality.validation` validators.

---

## Scope

This task plan implements only roadmap slice S5.

It does **not** implement: S6 blind-spot producers, S7 delegation, S8 value-choice provenance, S10 outcome prediction, S11 rich predictive dynamics/calibration models, production rollout authority, portfolio optimization, or a simulation engine for equilibrium prediction. S5 emits dynamics **requirements** and D3.5-compatible `ForecastSupport` system-effect **scope**; it does not claim calibrated forecasts.

Cells moved by S5 (cluster cells, **closed**):

- `SYSTEM.connectivity_modularity`: `implemented_but_not_orchestrated -> implemented` by wrapping Foundry coupling seeds behind a deterministic, replayable coupling producer.
- `SYSTEM.dynamics_feedback`: `implemented_but_not_orchestrated -> implemented` by emitting `SystemDynamicsRequirement` when feedback or entanglement blocks partial-equilibrium authority.
- `INTERVENTION.scale_composition`: `implemented_but_not_orchestrated -> implemented` by producing a `CompositionReceipt` that consumes the coupling/decomposition records before whole-design authority is assembled.

Open cell count delta:

- S0 baseline remains `17`.
- Current cluster-map open cell count becomes `10` after S5 (was `13` after S4; S5 closes three cells).
- S5 records the closed cells in its own manifest and edits `cluster_ownership_map.toml` (flip all three `[cell.*]` entries to `implemented`, remove the matching `[open_cell_closure.*]` entries).

First proving ground:

- The standing 13 W12 real-producer corpus cases remain the proving ground.
- All 13 cases get an S5 coupling/composition block and a per-case gold comparison.
- Coupling gold is boundary-specific: each case has at least one boundary row with module/interface refs, expected regime, residual interaction status, and dynamics trigger.
- `coupling_accuracy_with_false_modular_penalty` is computed against expert gold labels and must meet or exceed the S5 floor.
- The negative controls `false_modular_probe`, `syntactic_decomposition_probe`, and `boundary_spoof_probe` fail closed under P17.

S5 authority boundary:

- `authoritative_for`: `coupling_regime_classification`, `decomposition_validity`, `composition_gate`, `system_dynamics_requirement`, `critical_path_authority_composition`, `coupling_accuracy_metric`.
- `may_not_use_for`: `production_claim_authority`, `rollout_authority`, `publication_authority`, `equilibrium_prediction_authority`, `simulation_calibration_authority`, `whole_design_authority_without_coupling_graph`, `whole_design_authority_from_syntactic_decomposition`, `whole_design_authority_from_user_supplied_module_split`, `averaged_cross_level_authority`, `false_modular_decomposition`, `weakened_authority_from_tractability_cutoff`.

## Architecture Decision

S5 contracts live in `polisyos.runtime.quality`, not in `pdc`, `scientist`, or `foundry`.

Reason: Foundry owns reusable method seeds; the Policy Design Case runtime owns the authority gate. S5 should wire existing Foundry coupling/dynamics capability into a PDC producer and then expose replayable artifacts through the existing DesignRecord narrow waist. That keeps the direction A -> B as data flow and prevents B-side composition laundering.

Module placement:

- Create `src/polisyos/runtime/quality/layer2_coupling_composition.py`.
- Modify `src/polisyos/runtime/quality/__init__.py` to export S5 contracts.
- Modify `src/polisyos/pdc/_impl/layer2_design_search.py` only to consume injected S5 data and project it. It must not import `runtime.quality.layer2_coupling_composition`.
- Modify `tools/quality/validation/run_universal_outcome_corpus.py` to produce S5 blocks for all 13 cases and inject the pinned case's S5 posture into the existing S2/S4 shadow loop.

Import boundaries:

- `runtime.quality.layer2_coupling_composition` may import public S0 PDC contracts from `polisyos.pdc`, S4 runtime types from `runtime.quality.layer2_epistemic_regime`, and Foundry seed modules by ref/name. It must not import `pdc._impl.layer2_design_search`.
- `pdc._impl.layer2_design_search` receives one PDC-local `Layer2S5CompositionPostureInput` DTO containing the S5 receipt projection: coupling regime, composition disposition, boundary rows, ledger refs, critical path refs, residual risk, forecast-support label, dynamics requirement ref, and tractability ref. It must not import `runtime.quality.layer2_coupling_composition`.
- The corpus route is the orchestrator: it calls S4 first, S5 second, and passes both into the S2 loop for the pinned case.

S5 public labels:

- `CouplingRegime`: `modular`, `near_decomposable`, `hierarchically_coupled`, `entangled`.
- `CompositionDisposition`: `compose`, `compose_with_limitations`, `system_evidence_required`, `blocked`.
- `DynamicsRequirementLevel`: `none`, `local_sensitivity`, `system_dynamics_required`, `simulation_only_contested`.
- `CompositionAuthorityMode`: `critical_path_only`, `module_local_only`, `not_composable`.
- `FeedbackIntensity`: `none`, `weak`, `medium`, `high` (a dynamics trigger, not a coupling-regime replacement).
- `InteractionStrength`: `none`, `weak`, `medium`, `strong` (edge evidence strength; `none` is only for explicit modular interface rows).
- `ForecastSupportBaseOrigin`: `simulation_only`, `transported_scholar_estimate`, `validated_local_model`, `historical_prior`, `equilibrium_contested`.
- `ForecastClaimScope`: `leaf_only`, `system_effect`, `context_only`, `routing_only`.
- `SystemEffectSupportLabel`: `leaf_only_no_system_claim`, `simulation_only_system_effect`, `transported_with_heavy_limitation`, `validated_local_dynamic_model`, `historical_prior_system_context`, `equilibrium_contested`.

Critical-path authority rule:

- Whole-design authority is composed from modules only along the declared critical path.
- The regime on the critical path is selected by the most restrictive critical-path module regime, not by averaging all modules and not by taking the minimum over irrelevant peripheral modules.
- `hierarchically_coupled` boundaries propagate upstream limitations downstream in topological order.
- If the critical path contains `ignorance`, `entangled`, `feedback_intensity=high`, or a missing dynamics requirement, the receipt is limited or blocked.

Composition laws this slice must test and enforce:

- **identity/no-op:** adding an explicit no-op sub-design cannot change portfolio authority.
- **associativity/regrouping invariance:** regrouping children into a program or portfolio preserves interfaces, dependencies, evidence refs, and closeout-relevant limitations.
- **typed interface compatibility:** a producer sub-design's outputs, legal acts, budget allocations, data products, and delivery commitments match the consumer sub-design's inputs before composition.
- **critical-path monotonicity:** critical dependencies may block or limit the portfolio, but non-critical limitations become scoped limitations instead of global hard blocks when posture permits.
- **explicit boundary refs:** every cross-level handoff carries authority, provenance, rule version, time role, geography, population, and audience purpose.

## Pattern Pass

Relevant failure patterns: `P01`, `P02`, `P03`, `P04`, `P05`, `P10`, `P13`, `P15`, `P16`, `P17`, `P23`, `P24`.

Existing risks found:

- `SYSTEM.connectivity_modularity`, `SYSTEM.dynamics_feedback`, and `INTERVENTION.scale_composition` have seed files and architecture notes, but no owned PDC producer, persisted artifact, orchestration bridge, consumer, surface, or semantic tests. Current state is `implemented_but_not_orchestrated` / `bridge_missing`.
- S2 can emit a single candidate and S4 can inject regime/strategy, but the loop still has no composition gate. A country-scale or multi-module policy could look valid by validating parts separately and ignoring cross-effects.
- Foundry has dynamics and coupling methods, but their richness is hidden from PDC surfaces. Without S5, the system risks P03 hidden internal richness and P17 decomposition laundering.
- A B-side generator could create a syntactic tree of sub-designs and ask for whole-design authority without proving decomposition validity.

Correct pattern:

- A-side classifies coupling first, then decomposition validity, then composition authority. The gate defaults toward more coupling: absent graph or absent edge evidence is not `modular`.
- Modules are discovered producer results from the `RecursiveDesignGraph` / case structure, not user assertions. A user-supplied convenient module split can be a candidate hypothesis, never decomposition proof.
- Modularization design moves such as pilots, ring-fencing, phase sequencing, severability clauses, buffers, transition periods, or sunset rules remain candidate interventions until A produces a new coupling graph proving the reduced coupling.
- Coupling is classified per boundary/interface, then summarized for the design. There is no single global label that can hide a bad boundary.
- `false_modular_probe` with strong cyclic cross-effects fails P17 even if every submodule is individually valid.
- Entangled designs, especially with `feedback_intensity="high"`, emit `SystemDynamicsRequirement` and route to system-level evidence or downgrade; no partial-equilibrium system-effect claim is projected as publishable.
- System-effect support reuses the D3.5 `ForecastSupport` dictionary (`base_origin + claim_scope`) instead of inventing a second prediction ladder.
- `ComputationalTractabilityBudget` is produced and consumed by the receipt; approximation or anytime cutoffs may limit search/composition claims but may not weaken authority requirements.
- `CompositionReceipt` is persisted and referenced from `DesignRecordV0.ledger_refs`, with axis positions and firewall statuses for all three S5 cells.
- PUBLIC, REVIEWER, EXPERT, and MACHINE projections expose the composition posture at audience-specific detail.

Missing capability labels before implementation:

- `bridge_missing` for the three S5 cells.
- `artifact_missing` for runtime-visible `CouplingGraph`, `CouplingRegimeClassification`, `DecompositionResult`, `RecursiveDesignGraph`, `DesignInterfaceContract`, `SystemDynamicsRequirement`, `CompositionReceipt`, and `ComputationalTractabilityBudget`, plus nested boundary/discovery/forecast-scope/law-check records.
- `consumer_missing` for the compose-or-downgrade gate in the shadow loop.
- `surface_missing` for all audience projections.
- `semantic_test_missing` for P17 negative controls and 13-case scale-composition corpus adequacy.
- `verification_missing` for composition laws, system-dynamics obligation recall, and tractability-budget consumption.

Acceptance signal:

- Three S5 cells move to `implemented`; cluster-map open cell count drops from `13` to `10`.
- All S5 artifacts are strict, replayable, and exported from `runtime.quality`.
- B consumes an injected composition posture and cannot self-classify coupling or compose authority without an S5 receipt.
- All 13 corpus cases have per-case coupling rows and gold comparisons; false-modular count is zero; the S5 floor is met.
- Boundary-level coupling rows cover all four D2.6 regimes, including at least one `hierarchically_coupled` boundary.
- Production posture and S4 closeout behavior are unchanged; S5 affects shadow/governed composition routing only.

## Code-Grounded Reality Check

Existing strengths to reuse:

- `Layer2ReadinessModel` in `src/polisyos/pdc/_impl/layer2_readiness.py` is already strict and frozen. Task 2 should export `Layer2ReadinessModel` and `Audience` from `polisyos.pdc` before S5 imports them, then S5 public DTOs should subclass that public base instead of inventing another Pydantic base unless there is a concrete field-level reason.
- S4 already established the A-gate-owned pattern: `runtime.quality.layer2_epistemic_regime` classifies, the W12.D corpus route injects simple values into S2, and S2 records refs without importing the runtime-quality classifier.
- `run_universal_outcome_corpus.py` already loads all 13 cases, emits S4 per-case blocks, and computes an aggregate summary. S5 should mirror this pattern rather than creating a second corpus runner.
- `check_policy_design_case_layer2_readiness.py` and the S4 repo-quality tests already provide the manifest/inventory/open-count pattern. S5 should extend those validators in-place.
- `PolicyPortfolio`, `InteractionMatrix`, `LexPolicyBundleInput`, Foundry dynamics, and DES coupling code are useful seeds and references. They are not yet a design-composition producer, so S5 should wrap their concepts lightly rather than trying to run heavy simulations in unit tests.

Weak spots that make S5 larger than it first looks:

- `run_universal_outcome_corpus.py` is a single integration point with hand-wired S2/S4 helpers. Adding S5 touches imports, per-case construction, top-level report schema, pinned-case S2 injection, and W12.D tests.
- `src/polisyos/pdc/_impl/layer2_design_search.py` must update more than the function signature: candidate DTO, design record axis/firewall/ledger refs, projections, deterministic replay key, cluster interface contracts, handoff records, and refinement routing all need S5-aware behavior.
- Cluster-map closure cannot only flip `ratchet_state`; implemented cells with empty `owner_module` fail the cluster validator. S5 must set owners for `SYSTEM.connectivity_modularity`, `SYSTEM.dynamics_feedback`, and `INTERVENTION.scale_composition`.
- `AuthorityBoundary` and `DesignRecordV0` have bounded list lengths. Keep S5 deny-lists and ledger refs compact; do not turn every boundary row into a ledger ref.
- `runtime.quality.__init__.py` and `polisyos.pdc.__init__.py` are explicit public surfaces. Export updates are mechanical but easy to miss.
- `layer2_artifact_traceability.toml` already names the S5 top-level artifacts. Do not add new top-level S5 artifact names unless the roadmap/traceability table is intentionally changed.

Scope correction from this code pass:

- Top-level S5 artifacts remain the roadmap/traceability set: `CouplingGraph`, `CouplingRegimeClassification`, `DecompositionResult`, `RecursiveDesignGraph`, `DesignInterfaceContract`, `SystemDynamicsRequirement`, `CompositionReceipt`, and `ComputationalTractabilityBudget`.
- `BoundaryCouplingClassification`, `ModuleDiscoveryResult`, `ForecastSupportScope`, and `CompositionLawCheck` are strict nested DTOs/check records inside those artifacts and reports. They are exported for tests and projection clarity, but they are not new traceability rows or independent manifest `required_artifacts`.
- The S2 injection should use one PDC-local `Layer2S5CompositionPostureInput` DTO instead of a dozen optional parameters. This keeps the B loop import-safe and makes replay-key/projection wiring less brittle.

## Source Of Truth

| Concern | Source |
| --- | --- |
| Roadmap closure contract | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md#s5--coupling-classifier--design-composition-algebra` |
| P17 failure pattern | `docs/reference/policy-design-case-failure-patterns.md` |
| Slice-cell assignments | `architecture/policy_design_case/layer2_slice_cell_matrix.toml` |
| Cluster closure contracts | `architecture/policy_design_case/cluster_ownership_map.toml` (`SYSTEM.connectivity_modularity`, `SYSTEM.dynamics_feedback`, `INTERVENTION.scale_composition`) |
| Floor governance | `architecture/policy_design_case/layer2_floor_governance.toml#s5_coupling_accuracy` |
| Artifact traceability | `architecture/policy_design_case/layer2_artifact_traceability.toml` (all S5 named artifacts already listed) |
| S0 public contracts | `src/polisyos/pdc/__init__.py`, `src/polisyos/pdc/_impl/layer2_readiness.py` |
| S2 loop and projection narrow waist | `src/polisyos/pdc/_impl/layer2_design_search.py` |
| Public S2 facade | `src/polisyos/pdc/__init__.py` |
| S4 regime/commitment input | `src/polisyos/runtime/quality/layer2_epistemic_regime.py`, `src/polisyos/runtime/quality/case_lifecycle.py` |
| Foundry coupling seed | `src/polisyos/foundry/coupling/des_kernel.py` |
| Foundry dynamics seeds | `src/polisyos/foundry/methods/catalog/causal/dynamic_graph_dscm.py`, `src/polisyos/foundry/methods/catalog/simulation/dynamics.py` |
| Design-composition seeds | `src/polisyos/ir/loading/portfolio.py`, `src/polisyos/lex/intervention_artifacts.py` |
| Canonical corpus route | `tools/quality/validation/run_universal_outcome_corpus.py` |

## Files

Create:

- `src/polisyos/runtime/quality/layer2_coupling_composition.py`
- `architecture/policy_design_case/layer2_s5_coupling_composition_manifest.json`
- `tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`
- `tests/fixtures/layer2/s5/false_modular_probe.json`
- `tests/fixtures/layer2/s5/syntactic_decomposition_probe.json`
- `tests/fixtures/layer2/s5/boundary_spoof_probe.json`
- `tests/fixtures/layer2/s5/s5_coupling_case_signals.json`
- `tests/fixtures/layer2/s5/s5_coupling_expert_labels.json`

Modify:

- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/pdc/__init__.py`
- `src/polisyos/pdc/_impl/layer2_design_search.py`
- `tests/unit/pdc/test_layer2_s2_design_search.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
- `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`
- `architecture/policy_design_case/cluster_ownership_map.toml`
- `architecture/policy_design_case/inventory.json`

Do not modify:

- `architecture/policy_design_case/layer2_floor_governance.toml` (`s5_coupling_accuracy` already exists).
- `architecture/policy_design_case/layer2_slice_cell_matrix.toml`.
- `architecture/policy_design_case/layer2_dependency_dag.json`.
- S6+ cells, production authority, rich prediction/calibration models, or sealed S14 battery fixtures.

---

## Task 1: Red-First S5 Semantic And Negative Tests

**Files:**

- Create: `tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py`
- Create: `tests/fixtures/layer2/s5/false_modular_probe.json`
- Create: `tests/fixtures/layer2/s5/syntactic_decomposition_probe.json`
- Create: `tests/fixtures/layer2/s5/boundary_spoof_probe.json`
- Create: `src/polisyos/runtime/quality/layer2_coupling_composition.py` (skeleton import target only)

- [x] **Step 1: Add P17 negative-control fixtures**

Create `tests/fixtures/layer2/s5/false_modular_probe.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s5.false_modular_probe.v1",
  "case_id": "s5_false_modular_probe",
  "declared_coupling_regime": "modular",
  "expected_error": "P17FalseModularityError",
  "design_ref": "pdc://layer2/s5/false-modular/design",
  "module_refs": [
    "module://benefit-generosity",
    "module://eligibility-enforcement",
    "module://provider-incentives"
  ],
  "interaction_edges": [
    {
      "source_module_ref": "module://benefit-generosity",
      "target_module_ref": "module://provider-incentives",
      "relation": "incentive_feedback",
      "interaction_strength": "strong",
      "feedback": true,
      "evidence_ref": "fixture://s5/false_modular/edge-1"
    },
    {
      "source_module_ref": "module://provider-incentives",
      "target_module_ref": "module://eligibility-enforcement",
      "relation": "gaming_pressure",
      "interaction_strength": "strong",
      "feedback": true,
      "evidence_ref": "fixture://s5/false_modular/edge-2"
    },
    {
      "source_module_ref": "module://eligibility-enforcement",
      "target_module_ref": "module://benefit-generosity",
      "relation": "political_feedback",
      "interaction_strength": "strong",
      "feedback": true,
      "evidence_ref": "fixture://s5/false_modular/edge-3"
    }
  ]
}
```

Create `tests/fixtures/layer2/s5/syntactic_decomposition_probe.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s5.syntactic_decomposition_probe.v1",
  "case_id": "s5_syntactic_decomposition_probe",
  "expected_error": "P17SyntacticCompositionError",
  "design_ref": "pdc://layer2/s5/syntactic-only/design",
  "module_refs": [
    "module://tax",
    "module://transfer",
    "module://administration"
  ],
  "coupling_graph_ref": null,
  "decomposition_claim": "three named modules are enough to compose authority"
}
```

Create `tests/fixtures/layer2/s5/boundary_spoof_probe.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s5.boundary_spoof_probe.v1",
  "case_id": "s5_boundary_spoof_probe",
  "expected_error": "P17BoundarySpoofError",
  "design_ref": "pdc://layer2/s5/boundary-spoof/design",
  "user_supplied_module_refs": [
    "module://politically-convenient-front-office",
    "module://politically-convenient-back-office"
  ],
  "discovered_module_refs": [
    "module://eligibility",
    "module://delivery",
    "module://appeals",
    "module://provider-incentives"
  ],
  "spoofed_boundary_ref": "boundary://front-office/back-office",
  "expected_boundary_regime": "entangled",
  "reason": "user-supplied modules hide strong provider-incentive and appeals feedback across the proposed boundary"
}
```

- [x] **Step 2: Write failing unit tests**

Create `tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.pdc import AxisFirewallStatus, AxisPositionDeclaration
from polisyos.runtime.quality.layer2_coupling_composition import (
    BoundaryCouplingClassification,
    ComputationalTractabilityBudget,
    CompositionReceipt,
    CouplingEdge,
    CouplingGraph,
    CouplingRegimeClassification,
    DecompositionResult,
    DesignInterfaceContract,
    ForecastSupportScope,
    P17BoundarySpoofError,
    P17FalseModularityError,
    P17SyntacticCompositionError,
    P17SystemDynamicsRequiredError,
    RecursiveDesignGraph,
    SystemDynamicsRequirement,
    assert_composition_laws_hold,
    build_composition_receipt,
    build_computational_tractability_budget,
    build_coupling_graph,
    build_system_effect_support,
    build_system_dynamics_requirement,
    classify_coupling,
    composition_to_axis_positions,
    coupling_accuracy,
    critical_path_regime,
    decompose_design,
    derive_recursive_design_graph,
    discover_design_modules,
)

RULE_REF = "repo://docs/adr/0174-policy-evidence-capability-graph.md"


def _modules() -> tuple[str, str, str]:
    return (
        "module://eligibility",
        "module://delivery",
        "module://finance",
    )


def _modular_graph() -> CouplingGraph:
    return build_coupling_graph(
        design_ref="pdc://layer2/s5/modular/design",
        module_refs=_modules(),
        module_discovery_ref="pdc://layer2/s5/module-discovery/modular",
        interaction_edges=(),
        rule_version_ref=RULE_REF,
    )


def _near_decomposable_graph() -> CouplingGraph:
    return build_coupling_graph(
        design_ref="pdc://layer2/s5/near/design",
        module_refs=_modules(),
        module_discovery_ref="pdc://layer2/s5/module-discovery/near",
        interaction_edges=(
            CouplingEdge(
                boundary_ref="boundary://near/eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="implementation_dependency",
                interaction_strength="weak",
                feedback_intensity="weak",
                feedback=False,
                evidence_ref="fixture://s5/near/edge-1",
            ),
        ),
        rule_version_ref=RULE_REF,
    )


def _entangled_graph() -> CouplingGraph:
    return build_coupling_graph(
        design_ref="pdc://layer2/s5/entangled/design",
        module_refs=_modules(),
        module_discovery_ref="pdc://layer2/s5/module-discovery/entangled",
        interaction_edges=(
            CouplingEdge(
                boundary_ref="boundary://entangled/eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="gaming_feedback",
                interaction_strength="strong",
                feedback_intensity="high",
                feedback=True,
                evidence_ref="fixture://s5/entangled/edge-1",
            ),
            CouplingEdge(
                boundary_ref="boundary://entangled/delivery-finance",
                source_module_ref="module://delivery",
                target_module_ref="module://finance",
                relation="budget_feedback",
                interaction_strength="strong",
                feedback_intensity="high",
                feedback=True,
                evidence_ref="fixture://s5/entangled/edge-2",
            ),
            CouplingEdge(
                boundary_ref="boundary://entangled/finance-eligibility",
                source_module_ref="module://finance",
                target_module_ref="module://eligibility",
                relation="political_feedback",
                interaction_strength="strong",
                feedback_intensity="high",
                feedback=True,
                evidence_ref="fixture://s5/entangled/edge-3",
            ),
        ),
        rule_version_ref=RULE_REF,
    )


def _hierarchical_graph() -> CouplingGraph:
    return build_coupling_graph(
        design_ref="pdc://layer2/s5/hierarchical/design",
        module_refs=_modules(),
        module_discovery_ref="pdc://layer2/s5/module-discovery/hierarchical",
        interaction_edges=(
            CouplingEdge(
                boundary_ref="boundary://hierarchical/eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="eligibility_drives_delivery_load",
                interaction_strength="strong",
                feedback_intensity="weak",
                feedback=False,
                evidence_ref="fixture://s5/hierarchical/edge-1",
            ),
            CouplingEdge(
                boundary_ref="boundary://hierarchical/delivery-finance",
                source_module_ref="module://delivery",
                target_module_ref="module://finance",
                relation="delivery_drives_budget_drawdown",
                interaction_strength="strong",
                feedback_intensity="weak",
                feedback=False,
                evidence_ref="fixture://s5/hierarchical/edge-2",
            ),
        ),
        rule_version_ref=RULE_REF,
    )


def test_s5_artifacts_are_strict() -> None:
    with pytest.raises(ValidationError):
        CouplingGraph(
            graph_id="layer2.s5.graph.strict",
            graph_ref="pdc://layer2/s5/strict/graph",
            design_ref="pdc://layer2/s5/strict/design",
            module_refs=list(_modules()),
            interaction_edges=[],
            evidence_state="observed",
            rule_version_ref=RULE_REF,
            unexpected="blocked",
        )


def test_modular_graph_can_compose_only_with_coupling_proof() -> None:
    graph = _modular_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )
    receipt = build_composition_receipt(decomposition)

    assert isinstance(classification, CouplingRegimeClassification)
    assert isinstance(receipt, CompositionReceipt)
    assert classification.coupling_regime == "modular"
    assert decomposition.composition_disposition == "compose"
    assert receipt.authority_mode == "critical_path_only"
    assert receipt.whole_design_authority == "shadow_governed_only"


def test_near_decomposable_composes_with_residual_risk_limitation() -> None:
    graph = _near_decomposable_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )
    receipt = build_composition_receipt(decomposition)

    assert classification.coupling_regime == "near_decomposable"
    assert decomposition.composition_disposition == "compose_with_limitations"
    assert receipt.residual_interaction_risk == "medium"
    assert "residual_interaction_risk" in receipt.authority_boundary.may_not_use_for


def test_false_modular_probe_fails_p17() -> None:
    with pytest.raises(P17FalseModularityError, match="strong cyclic cross-effects"):
        classify_coupling(_entangled_graph(), declared_coupling_regime="modular")


def test_absent_coupling_graph_defaults_to_more_coupling() -> None:
    classification = classify_coupling(
        None,
        design_ref="pdc://layer2/s5/absent/design",
        module_refs=list(_modules()),
        rule_version_ref=RULE_REF,
    )

    assert classification.coupling_regime == "entangled"
    assert classification.firewall_disposition == "block"
    assert classification.defaulted_to_more_coupling is True


def test_syntactic_decomposition_without_coupling_proof_cannot_compose() -> None:
    graph = _modular_graph()
    classification = classify_coupling(graph)
    decomposition = DecompositionResult(
        decomposition_id="layer2.s5.decomposition.syntax",
        decomposition_ref="pdc://layer2/s5/syntax/decomposition",
        design_ref=graph.design_ref,
        coupling_graph_ref=None,
        coupling_classification_ref=classification.classification_ref,
        module_refs=list(_modules()),
        critical_path_module_refs=list(_modules()),
        interface_refs=[],
        composition_disposition="compose",
        residual_interaction_risk="low",
        dynamics_requirement_ref=None,
        rule_version_ref=RULE_REF,
    )

    with pytest.raises(P17SyntacticCompositionError, match="coupling graph"):
        build_composition_receipt(decomposition)


def test_entangled_design_requires_system_dynamics_before_system_effect_claim() -> None:
    graph = _entangled_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )

    assert classification.coupling_regime == "entangled"
    assert classification.feedback_intensity == "high"
    assert decomposition.composition_disposition == "system_evidence_required"
    with pytest.raises(P17SystemDynamicsRequiredError, match="system dynamics"):
        build_composition_receipt(decomposition, system_effect_claim_requested=True)

    dynamics = build_system_dynamics_requirement(decomposition)
    assert dynamics.requirement_level in {"system_dynamics_required", "simulation_only_contested"}


def test_hierarchically_coupled_designs_propagate_upstream_constraints() -> None:
    graph = _hierarchical_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )
    receipt = build_composition_receipt(decomposition)

    assert classification.coupling_regime == "hierarchically_coupled"
    assert decomposition.composition_disposition == "compose_with_limitations"
    assert receipt.propagated_limitation_refs
    assert receipt.authority_mode == "critical_path_only"


def test_user_supplied_module_split_is_candidate_not_boundary_proof() -> None:
    discovered = discover_design_modules(
        design_ref="pdc://layer2/s5/boundary-spoof/design",
        candidate_module_refs=[
            "module://politically-convenient-front-office",
            "module://politically-convenient-back-office",
        ],
        case_signal_refs=["fixture://s5/boundary_spoof/case-signals"],
        rule_version_ref=RULE_REF,
    )

    graph = build_coupling_graph(
        design_ref="pdc://layer2/s5/boundary-spoof/design",
        module_refs=discovered.discovered_module_refs,
        module_discovery_ref=discovered.module_discovery_ref,
        interaction_edges=_entangled_graph().interaction_edges,
        rule_version_ref=RULE_REF,
    )

    assert discovered.user_supplied_module_refs != discovered.discovered_module_refs
    assert classify_coupling(graph).coupling_regime == "entangled"

    with pytest.raises(P17BoundarySpoofError, match="candidate module split"):
        discover_design_modules(
            design_ref="pdc://layer2/s5/boundary-spoof/design",
            candidate_module_refs=[
                "module://politically-convenient-front-office",
                "module://politically-convenient-back-office",
            ],
            case_signal_refs=[],
            treat_candidate_as_proof=True,
            rule_version_ref=RULE_REF,
        )


def test_boundary_specific_classification_records_each_interface() -> None:
    graph = _hierarchical_graph()
    classification = classify_coupling(graph)

    assert classification.boundary_classifications
    assert all(isinstance(row, BoundaryCouplingClassification) for row in classification.boundary_classifications)
    assert {
        (row.source_module_ref, row.target_module_ref)
        for row in classification.boundary_classifications
    } == {
        ("module://eligibility", "module://delivery"),
        ("module://delivery", "module://finance"),
    }
    assert {row.coupling_regime for row in classification.boundary_classifications} == {
        "hierarchically_coupled"
    }


def test_composition_laws_identity_regrouping_interface_and_monotonicity() -> None:
    graph = _near_decomposable_graph()
    recursive = derive_recursive_design_graph(
        design_ref=graph.design_ref,
        module_refs=graph.module_refs,
        parent_child_edges=[(graph.design_ref, module_ref) for module_ref in graph.module_refs],
        rule_version_ref=RULE_REF,
    )
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=["module://eligibility", "module://delivery"],
    )
    receipt = build_composition_receipt(decomposition)

    result = assert_composition_laws_hold(
        recursive_graph=recursive,
        coupling_graph=graph,
        decomposition=decomposition,
        receipt=receipt,
    )

    assert result.identity_noop is True
    assert result.associativity_regrouping_invariant is True
    assert result.typed_interface_compatible is True
    assert result.critical_path_monotonic is True


def test_system_effect_support_reuses_forecast_support_dictionary() -> None:
    scope = build_system_effect_support(
        base_origin="simulation_only",
        claim_scope="system_effect",
        support_ref="pdc://layer2/s5/support/simulation-only-system-effect",
        rule_version_ref=RULE_REF,
    )

    assert isinstance(scope, ForecastSupportScope)
    assert scope.base_origin == "simulation_only"
    assert scope.claim_scope == "system_effect"
    assert scope.support_label == "simulation_only_system_effect"
    assert "calibrated_forecast_authority" in scope.authority_boundary.may_not_use_for


def test_computational_tractability_budget_is_consumed_by_receipt() -> None:
    graph = _entangled_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )
    budget = build_computational_tractability_budget(
        design_ref=graph.design_ref,
        search_space_size="large",
        approximation_mode="anytime_cutoff",
        cutoff_reason="feedback graph too large for exhaustive composition search",
        rule_version_ref=RULE_REF,
    )
    dynamics = build_system_dynamics_requirement(decomposition)
    receipt = build_composition_receipt(
        decomposition,
        dynamics_requirement=dynamics,
        tractability_budget=budget,
    )

    assert isinstance(budget, ComputationalTractabilityBudget)
    assert receipt.tractability_budget_ref == budget.budget_ref
    assert receipt.whole_design_authority != "production"


def test_critical_path_regime_is_not_average_or_min_over_all_modules() -> None:
    module_regimes = {
        "module://eligibility": "risk",
        "module://delivery": "uncertainty",
        "module://finance": "ignorance",
        "module://peripheral": "risk",
    }

    assert critical_path_regime(
        module_regimes=module_regimes,
        critical_path_module_refs=["module://eligibility", "module://delivery"],
    ) == "uncertainty"
    assert critical_path_regime(
        module_regimes=module_regimes,
        critical_path_module_refs=["module://eligibility", "module://finance"],
    ) == "ignorance"


def test_coupling_accuracy_penalizes_false_modular_more_than_false_entangled() -> None:
    false_modular = coupling_accuracy(predicted=["modular"], gold=["entangled"])
    false_entangled = coupling_accuracy(predicted=["entangled"], gold=["modular"])

    assert false_modular["penalized_score"] < false_entangled["penalized_score"]
    assert false_modular["false_modular_count"] == 1
    assert false_modular["false_entangled_count"] == 0
    assert false_entangled["false_modular_count"] == 0
    assert false_entangled["false_entangled_count"] == 1


def test_composition_projects_to_axis_positions_and_firewalls() -> None:
    graph = _near_decomposable_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )
    receipt = build_composition_receipt(decomposition)

    positions, firewalls = composition_to_axis_positions(
        graph=graph,
        classification=classification,
        decomposition=decomposition,
        receipt=receipt,
    )

    assert all(isinstance(position, AxisPositionDeclaration) for position in positions)
    assert all(isinstance(firewall, AxisFirewallStatus) for firewall in firewalls)
    assert {position.cell_ref for position in positions} == {
        "SYSTEM.connectivity_modularity",
        "SYSTEM.dynamics_feedback",
        "INTERVENTION.scale_composition",
    }
    assert {"P17"} <= set().union(*(set(firewall.pattern_ids) for firewall in firewalls))


def test_recursive_design_graph_and_interface_contract_are_replay_visible() -> None:
    graph = _near_decomposable_graph()
    recursive = RecursiveDesignGraph(
        graph_id="layer2.s5.recursive.ua-msme",
        graph_ref="pdc://layer2/s5/ua-msme/recursive-design-graph",
        root_design_ref=graph.design_ref,
        node_refs=[graph.design_ref, *graph.module_refs],
        node_kinds={
            graph.design_ref: "policy_program",
            "module://eligibility": "design_candidate",
            "module://delivery": "design_candidate",
            "module://finance": "design_candidate",
        },
        parent_child_edges=[
            ("pdc://layer2/s5/near/design", "module://eligibility"),
            ("pdc://layer2/s5/near/design", "module://delivery"),
            ("pdc://layer2/s5/near/design", "module://finance"),
        ],
        typed_dependency_edges=[
            {
                "source_ref": "module://eligibility",
                "target_ref": "module://delivery",
                "dependency_type": "implementation_dependency",
                "interface_ref": "pdc://layer2/s5/ua-msme/interface/eligibility-delivery",
            }
        ],
        critical_path_module_refs=["module://eligibility", "module://delivery"],
        interface_refs=["pdc://layer2/s5/ua-msme/interface/eligibility-delivery"],
        rule_version_ref=RULE_REF,
    )
    interface = DesignInterfaceContract(
        interface_id="layer2.s5.interface.delivery-finance",
        interface_ref="pdc://layer2/s5/ua-msme/interface/delivery-finance",
        source_module_ref="module://delivery",
        target_module_ref="module://finance",
        exchanged_claim_refs=["claim://delivery/takeup", "claim://finance/fiscal-burden"],
        authority_boundary=classify_coupling(graph).authority_boundary,
        rule_version_ref=RULE_REF,
    )

    assert recursive.root_design_ref == graph.design_ref
    assert recursive.node_kinds[graph.design_ref] == "policy_program"
    assert recursive.critical_path_module_refs == ["module://eligibility", "module://delivery"]
    assert interface.source_module_ref in graph.module_refs
    assert interface.target_module_ref in graph.module_refs
```

- [x] **Step 3: Add import skeleton and run red**

Create a temporary skeleton `src/polisyos/runtime/quality/layer2_coupling_composition.py` with only the module docstring and `__all__ = []`.

Run:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py -q
```

Expected: fail because the S5 classes/functions do not exist yet. Keep the failure output in the task notes before Task 2.

Task 1 notes, 2026-05-31:

```text
uv run pytest tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py -q

ERROR tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py
ImportError: cannot import name 'BoundaryCouplingClassification' from
'polisyos.runtime.quality.layer2_coupling_composition'
```

## Task 2: Coupling Contracts, Classifier, Decomposition, And P17 Firewalls

**Files:**

- Modify: `src/polisyos/runtime/quality/layer2_coupling_composition.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`
- Modify: `src/polisyos/pdc/__init__.py`

- [x] **Step 1: Export S0 base contracts and implement strict S5 contracts**

First modify `src/polisyos/pdc/__init__.py` to export `Audience` and `Layer2ReadinessModel` from `._impl.layer2_readiness`; add both names to `__all__`. This is a public-surface widening of the existing S0 narrow waist, not a new S5-local base model.

In `layer2_coupling_composition.py`, define strict frozen models by subclassing the existing public `Layer2ReadinessModel` from `polisyos.pdc`. This is the repo-local narrow-waist pattern and avoids a parallel Pydantic base:

```python
CouplingRegime = Literal["modular", "near_decomposable", "hierarchically_coupled", "entangled"]
FeedbackIntensity = Literal["none", "weak", "medium", "high"]
InteractionStrength = Literal["none", "weak", "medium", "strong"]
CompositionDisposition = Literal[
    "compose",
    "compose_with_limitations",
    "system_evidence_required",
    "blocked",
]
DynamicsRequirementLevel = Literal[
    "none",
    "local_sensitivity",
    "system_dynamics_required",
    "simulation_only_contested",
]
CompositionAuthorityMode = Literal[
    "critical_path_only",
    "module_local_only",
    "not_composable",
]
ForecastSupportBaseOrigin = Literal[
    "simulation_only",
    "transported_scholar_estimate",
    "validated_local_model",
    "historical_prior",
    "equilibrium_contested",
]
ForecastClaimScope = Literal["leaf_only", "system_effect", "context_only", "routing_only"]
SystemEffectSupportLabel = Literal[
    "leaf_only_no_system_claim",
    "simulation_only_system_effect",
    "transported_with_heavy_limitation",
    "validated_local_dynamic_model",
    "historical_prior_system_context",
    "equilibrium_contested",
]
```

Top-level S5 artifacts, matching `layer2_artifact_traceability.toml`:

- `CouplingGraph`
- `CouplingRegimeClassification`
- `RecursiveDesignGraph`
- `DesignInterfaceContract`
- `SystemDynamicsRequirement`
- `DecompositionResult`
- `CompositionReceipt`
- `ComputationalTractabilityBudget`

Strict nested DTOs/check records, exported from `runtime.quality` but not added as new top-level artifact-traceability rows:

- `BoundaryCouplingClassification`
- `CouplingEdge`
- `ModuleDiscoveryResult`
- `ForecastSupportScope`
- `CompositionLawCheck`

Each top-level artifact carries `schema_version`, stable `*_id`, stable `*_ref`, `design_ref` where applicable, `rule_version_ref`, and an `AuthorityBoundary` when it can be consumed outside the producer.

`RecursiveDesignGraph` must model the roadmap's recursive `DesignCandidate` / `PolicyProgram` / `PolicyPortfolio` shape inside the graph rather than adding new top-level artifacts. Include `node_kinds`, `parent_child_edges`, `typed_dependency_edges`, `critical_path_module_refs`, and `interface_refs` so regrouping and critical-path law checks are replayable.

Implementation constraint: do not instantiate Foundry JAX/DES/simulation kernels in these unit tests. Use S5 lightweight graph records with `seed_method_refs`/`evidence_refs`; Foundry execution remains a later evidence producer, while S5 is the authority gate over the design graph.

- [x] **Step 2: Implement P17 errors and classifier**

Add:

```python
class P17FalseModularityError(ValueError):
    """Raised when modular authority is claimed across strong cyclic cross-effects."""


class P17SyntacticCompositionError(ValueError):
    """Raised when a design tree is used as decomposition proof without CouplingGraph."""


class P17SystemDynamicsRequiredError(ValueError):
    """Raised when a system-effect claim is requested before dynamics evidence exists."""


class P17BoundarySpoofError(ValueError):
    """Raised when a convenient module split is treated as decomposition proof."""
```

Implement:

- `discover_design_modules(design_ref, candidate_module_refs, case_signal_refs, treat_candidate_as_proof=False, rule_version_ref) -> ModuleDiscoveryResult`
- `derive_recursive_design_graph -> RecursiveDesignGraph`
- `build_coupling_graph -> CouplingGraph`
- `classify_coupling(graph: CouplingGraph | None, *, design_ref: str | None = None, module_refs: list[str] | None = None, module_discovery_ref: str | None = None, rule_version_ref: str | None = None, declared_coupling_regime: CouplingRegime | None = None) -> CouplingRegimeClassification`
- `decompose_design(graph, classification, *, critical_path_module_refs) -> DecompositionResult`
- `build_system_dynamics_requirement(decomposition) -> SystemDynamicsRequirement`
- `build_system_effect_support -> ForecastSupportScope`
- `build_computational_tractability_budget -> ComputationalTractabilityBudget`
- `build_composition_receipt(decomposition, *, dynamics_requirement=None, system_effect_support=None, tractability_budget=None, system_effect_claim_requested=False, module_regimes=None) -> CompositionReceipt`
- `assert_composition_laws_hold -> CompositionLawCheck`
- `critical_path_regime(module_regimes, critical_path_module_refs) -> EpistemicRegime`
- `composition_to_axis_positions -> tuple[list[AxisPositionDeclaration], list[AxisFirewallStatus]]`
- `coupling_accuracy(predicted, gold) -> dict[str, float | int]` with keys `accuracy`, `penalized_score`, `false_modular_count`, and `false_entangled_count`.

`CouplingEdge` includes `boundary_ref`, `source_module_ref`, `target_module_ref`, `relation`, `interaction_strength: InteractionStrength`, `feedback_intensity: FeedbackIntensity`, `feedback`, and `evidence_ref`. Use `interaction_strength="none"` and `feedback_intensity="none"` for explicit modular interface rows that need replay-visible boundary classification but have no observed cross-effect. `feedback` remains the cycle trigger for high intensity feedback; `feedback_intensity` preserves `weak`/`medium` residual signals for truthfully recording predicted intensity.

Classification rules:

- `graph is None`, `evidence_state == "absent"`, or `module_discovery_ref` missing -> `entangled`, `firewall_disposition="block"`, `defaulted_to_more_coupling=True`.
- No interaction edges, or only explicit `interaction_strength="none"` interface rows -> `modular`, `firewall_disposition="pass"`.
- Weak non-feedback edges only -> `near_decomposable`, `firewall_disposition="limit"`.
- Strong directed acyclic cross-module edges -> `hierarchically_coupled`, `firewall_disposition="limit"`, `feedback_intensity` equal to the strongest non-high residual signal (`"weak"` or `"medium"`; `"none"` only when no residual signal is present).
- Any strong feedback cycle -> `entangled`, `feedback_intensity="high"`, `composition_disposition="system_evidence_required"`.
- Strong cross-module edges without a valid hierarchy -> `entangled`, `composition_disposition="system_evidence_required"`.
- Declared `modular` against `near_decomposable`, `hierarchically_coupled`, or `entangled` raises `P17FalseModularityError`.
- Classification is boundary-first: edges are grouped by `boundary_ref`, each interface gets one `BoundaryCouplingClassification`, and the design-level `CouplingRegimeClassification` is the most authority-restrictive critical-boundary summary, with all rows preserved for replay.
- User-supplied `module_refs` are accepted only when tied to a producer-owned `module_discovery_ref`; convenient candidate splits without discovery proof raise `P17BoundarySpoofError` or default to `entangled`.

Composition rules:

- `modular` -> `compose`.
- `near_decomposable` -> `compose_with_limitations`.
- `hierarchically_coupled` -> `compose_with_limitations`, with upstream limitations propagated downstream in topological order.
- `entangled` -> `system_evidence_required`.
- A `DecompositionResult` with `composition_disposition in {"compose", "compose_with_limitations"}` and missing `coupling_graph_ref` raises `P17SyntacticCompositionError`.
- `system_effect_claim_requested=True` with `system_evidence_required` and no dynamics requirement raises `P17SystemDynamicsRequiredError`.
- Dynamics requirements are requirements, not predictions: `simulation_only_contested` may permit a shadow/governed exploration receipt but never production authority.
- `ForecastSupportScope` reuses the D3.5 `ForecastSupport` dictionary as `base_origin + claim_scope`; it may support scoped shadow routing but cannot mint calibrated forecast authority.
- `ComputationalTractabilityBudget` is always referenced by receipts for large, entangled, or hierarchical designs; approximation modes and cutoffs can limit composition claims but cannot lower P17 or P24 obligations.
- `assert_composition_laws_hold` fails closed unless identity/no-op, associativity/regrouping invariance, typed interface compatibility, critical-path monotonicity, and explicit boundary refs all hold.

- [x] **Step 3: Export S5 runtime contracts**

Modify `src/polisyos/runtime/quality/__init__.py` to import and list every public S5 contract and helper in `__all__`.

Run:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py -q
uv run ruff check src/polisyos/runtime/quality/layer2_coupling_composition.py src/polisyos/runtime/quality/__init__.py
```

Expected: all S5 unit tests pass and ruff reports no issues.

Task 2 notes, 2026-05-31:

```text
uv run pytest tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py -q
17 passed

uv run ruff check \
  src/polisyos/runtime/quality/layer2_coupling_composition.py \
  src/polisyos/runtime/quality/__init__.py \
  src/polisyos/pdc/__init__.py
All checks passed!
```

## Task 3: Inject Composition Into The B-Side Shadow Loop

**Files:**

- Modify: `src/polisyos/pdc/_impl/layer2_design_search.py`
- Modify: `src/polisyos/pdc/__init__.py`
- Modify: `tests/unit/pdc/test_layer2_s2_design_search.py`

- [x] **Step 1: Add red S2 loop and surface tests**

Append these tests to `tests/unit/pdc/test_layer2_s2_design_search.py`. Use the existing `_input()` helper and direct `run_s2_shadow_design_loop` calls; do not introduce a private helper that does not exist in the current test file. Extend the current imports from `polisyos.pdc` with `Layer2S5CompositionPostureInput`, `assert_s2_public_projection_has_composition_limitation`, and `project_s2_design_search`.

```python
def test_injected_composition_recorded_on_record_without_self_decomposition() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
        composition_posture=Layer2S5CompositionPostureInput(
            coupling_regime="near_decomposable",
            boundary_coupling_rows=[
                {
                    "boundary_ref": "boundary://credit/fiscal",
                    "source_module_ref": "module://credit-program-enrollment",
                    "target_module_ref": "module://fiscal-burden-per-beneficiary",
                    "coupling_regime": "near_decomposable",
                    "feedback_intensity": "weak",
                }
            ],
            composition_disposition="compose_with_limitations",
            coupling_graph_ref="pdc://layer2/s5/ua-msme/coupling-graph",
            module_discovery_ref="pdc://layer2/s5/ua-msme/module-discovery",
            decomposition_result_ref="pdc://layer2/s5/ua-msme/decomposition-result",
            composition_receipt_ref="pdc://layer2/s5/ua-msme/composition-receipt",
            dynamics_requirement_ref="pdc://layer2/s5/ua-msme/system-dynamics-requirement",
            tractability_budget_ref="pdc://layer2/s5/ua-msme/tractability-budget",
            forecast_support_label="transported_with_heavy_limitation",
            critical_path_module_refs=[
                "module://credit-program-enrollment",
                "module://fiscal-burden-per-beneficiary",
            ],
            residual_interaction_risk="medium",
        ),
    )

    candidate = run.candidates[0]
    assert candidate.coupling_regime == "near_decomposable"
    assert candidate.composition_disposition == "compose_with_limitations"
    assert "pdc://layer2/s5/ua-msme/coupling-graph" in run.design_record.ledger_refs
    assert "pdc://layer2/s5/ua-msme/module-discovery" in run.design_record.ledger_refs
    assert "pdc://layer2/s5/ua-msme/decomposition-result" in run.design_record.ledger_refs
    assert "pdc://layer2/s5/ua-msme/composition-receipt" in run.design_record.ledger_refs
    assert "pdc://layer2/s5/ua-msme/tractability-budget" in run.design_record.ledger_refs

    axis_by_cell = {axis.cell_ref: axis for axis in run.design_record.axis_positions}
    firewall_by_cell = {fw.cell_ref: fw for fw in run.design_record.firewall_status}
    assert axis_by_cell["SYSTEM.connectivity_modularity"].position == "near_decomposable"
    assert axis_by_cell["INTERVENTION.scale_composition"].position.startswith(
        "composition_disposition=compose_with_limitations"
    )
    assert "P17" in firewall_by_cell["SYSTEM.connectivity_modularity"].pattern_ids
    assert "P17" in firewall_by_cell["INTERVENTION.scale_composition"].pattern_ids
```

```python
def test_s2_shadow_loop_does_not_import_or_call_s5_classifier() -> None:
    import inspect
    import polisyos.pdc._impl.layer2_design_search as s2_design_search

    source = inspect.getsource(s2_design_search)

    assert "layer2_coupling_composition" not in source
    assert "classify_coupling" not in source
    assert "decompose_design" not in source
```

```python
def test_four_audience_surface_renders_composition_posture() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
        composition_posture=Layer2S5CompositionPostureInput(
            coupling_regime="near_decomposable",
            boundary_coupling_rows=[
                {
                    "boundary_ref": "boundary://credit/fiscal",
                    "source_module_ref": "module://credit",
                    "target_module_ref": "module://fiscal",
                    "coupling_regime": "near_decomposable",
                    "feedback_intensity": "weak",
                }
            ],
            composition_disposition="compose_with_limitations",
            coupling_graph_ref="pdc://layer2/s5/ua-msme/coupling-graph",
            module_discovery_ref="pdc://layer2/s5/ua-msme/module-discovery",
            decomposition_result_ref="pdc://layer2/s5/ua-msme/decomposition-result",
            composition_receipt_ref="pdc://layer2/s5/ua-msme/composition-receipt",
            dynamics_requirement_ref="pdc://layer2/s5/ua-msme/system-dynamics-requirement",
            tractability_budget_ref="pdc://layer2/s5/ua-msme/tractability-budget",
            forecast_support_label="transported_with_heavy_limitation",
            critical_path_module_refs=["module://credit", "module://fiscal"],
            residual_interaction_risk="medium",
        ),
    )

    projections = project_s2_design_search(
        run,
        audiences=("PUBLIC", "REVIEWER", "EXPERT", "MACHINE"),
    )

    for projection in projections.values():
        assert projection["coupling_regime"] == "near_decomposable"
        assert projection["composition_disposition"] == "compose_with_limitations"
        assert "whole-design authority" in projection["composition_limitation"]

    assert projections["PUBLIC"]["composition_limitation"]
    assert projections["REVIEWER"]["p17_firewall_status"] == "limit"
    assert projections["EXPERT"]["coupling_graph_ref"] == "pdc://layer2/s5/ua-msme/coupling-graph"
    assert projections["EXPERT"]["boundary_coupling_rows"][0]["boundary_ref"] == "boundary://credit/fiscal"
    assert projections["EXPERT"]["forecast_support_label"] == "transported_with_heavy_limitation"
    assert projections["MACHINE"]["critical_path_module_refs"] == ["module://credit", "module://fiscal"]
```

```python
def test_public_composition_projection_requires_limitation() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
        composition_posture=Layer2S5CompositionPostureInput(
            coupling_regime="entangled",
            composition_disposition="system_evidence_required",
            coupling_graph_ref="pdc://layer2/s5/ua-msme/coupling-graph",
            module_discovery_ref="pdc://layer2/s5/ua-msme/module-discovery",
            decomposition_result_ref="pdc://layer2/s5/ua-msme/decomposition-result",
            composition_receipt_ref="pdc://layer2/s5/ua-msme/composition-receipt",
            dynamics_requirement_ref="pdc://layer2/s5/ua-msme/system-dynamics-requirement",
            tractability_budget_ref="pdc://layer2/s5/ua-msme/tractability-budget",
            forecast_support_label="simulation_only_system_effect",
            critical_path_module_refs=["module://credit", "module://fiscal"],
            residual_interaction_risk="high",
        ),
    )
    public_projection = project_s2_design_search(run, audiences=("PUBLIC",))["PUBLIC"]
    assert_s2_public_projection_has_composition_limitation(public_projection)
    broken_projection = dict(public_projection)
    broken_projection["composition_limitation"] = ""

    with pytest.raises(ValueError, match="PUBLIC composition projection requires limitation"):
        assert_s2_public_projection_has_composition_limitation(broken_projection)
```

```python
def test_entangled_composition_routes_refinement_to_decompose_not_point_optimize() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
        composition_posture=Layer2S5CompositionPostureInput(
            coupling_regime="entangled",
            composition_disposition="system_evidence_required",
            coupling_graph_ref="pdc://layer2/s5/ua-msme/coupling-graph",
            module_discovery_ref="pdc://layer2/s5/ua-msme/module-discovery",
            decomposition_result_ref="pdc://layer2/s5/ua-msme/decomposition-result",
            composition_receipt_ref="pdc://layer2/s5/ua-msme/composition-receipt",
            dynamics_requirement_ref="pdc://layer2/s5/ua-msme/system-dynamics-requirement",
            tractability_budget_ref="pdc://layer2/s5/ua-msme/tractability-budget",
            forecast_support_label="simulation_only_system_effect",
            critical_path_module_refs=["module://credit", "module://fiscal"],
            residual_interaction_risk="high",
        ),
    )

    assert run.refinement_decisions[0].decision in {"decompose", "reframe", "human_decision"}
    assert run.refinement_decisions[0].decision != "refine"
```

- [x] **Step 2: Extend S2 input, candidate, design record, and projections**

Modify `run_s2_shadow_design_loop` to accept one injected S5 posture DTO:

```python
composition_posture: Layer2S5CompositionPostureInput | None = None
```

Define `Layer2S5CompositionPostureInput` in `src/polisyos/pdc/_impl/layer2_design_search.py` as a PDC-local strict DTO. It must not import `runtime.quality.layer2_coupling_composition`; it is only the B-loop's consumed projection of the A-owned S5 receipt.

```python
class Layer2S5CompositionPostureInput(Layer2ReadinessModel):
    """Injected S5 A-gate posture consumed by the S2 shadow loop."""

    coupling_regime: Literal[
        "modular",
        "near_decomposable",
        "hierarchically_coupled",
        "entangled",
    ]
    composition_disposition: Literal[
        "compose",
        "compose_with_limitations",
        "system_evidence_required",
        "blocked",
    ]
    coupling_graph_ref: str
    module_discovery_ref: str
    decomposition_result_ref: str
    composition_receipt_ref: str
    dynamics_requirement_ref: str | None = None
    tractability_budget_ref: str | None = None
    boundary_coupling_rows: list[dict[str, object]] = Field(default_factory=list)
    forecast_support_label: str | None = None
    critical_path_module_refs: list[str] = Field(default_factory=list)
    residual_interaction_risk: str | None = None
    authority_mode: Literal["critical_path_only", "module_local_only", "not_composable"] = (
        "critical_path_only"
    )
    false_modular_penalty: float = Field(default=0.0, ge=0.0)
```

Export `Layer2S5CompositionPostureInput` from `src/polisyos/pdc/__init__.py` with the other S2 public DTOs.

Extend `Layer2S2DesignSearchRun` with `composition_posture: Layer2S5CompositionPostureInput | None = None`, and extend `DesignCandidateV0` with the compact candidate-facing subset:

- `coupling_regime`
- `composition_disposition`
- `decomposition_result_ref`
- `composition_receipt_ref`
- `forecast_support_label`
- `residual_interaction_risk`

Extend `_design_record` to append three axis positions and three P17 firewall statuses when `coupling_regime` is injected:

- `SYSTEM.connectivity_modularity`
- `SYSTEM.dynamics_feedback`
- `INTERVENTION.scale_composition`

Extend `_cluster_interfaces` and `_handoff_records` so the DesignRecord surface proves S5 is a consumed bridge:

- `SYSTEM.connectivity_modularity` publishes `CouplingGraph` / `CouplingRegimeClassification`;
- `SYSTEM.dynamics_feedback` publishes `SystemDynamicsRequirement` when present;
- `INTERVENTION.scale_composition` consumes the S5 refs and publishes `CompositionReceipt`;
- handoff records must mark the S5 posture as `consumed`, not `emitted` by B.

Extend `ledger_refs` with all non-empty S5 refs:

- `coupling_graph_ref`
- `module_discovery_ref`
- `decomposition_result_ref`
- `composition_receipt_ref`
- `dynamics_requirement_ref`
- `tractability_budget_ref`

Extend `_deterministic_replay_key` to include the S5 posture fields. Same S2 input with a different S5 receipt must produce a different replay key.

Extend `_refinement_decision` so `composition_disposition="system_evidence_required"` routes to `decompose`, `reframe`, or `human_decision`; it must not return `refine` point-optimization for entangled composition.

When S5 posture is present, set `DesignRecordV0.projection_audiences` to all four audiences even if S4 regime fields are absent, because S5 has its own PUBLIC/REVIEWER/EXPERT/MACHINE surface.

Extend `project_s2_design_search`:

- PUBLIC: `coupling_regime`, `composition_disposition`, `composition_limitation`.
- REVIEWER: add `p17_firewall_status`, `composition_strategy`, `residual_interaction_risk`.
- EXPERT/MACHINE: add `coupling_graph_ref`, `module_discovery_ref`, `decomposition_result_ref`, `composition_receipt_ref`, `dynamics_requirement_ref`, `tractability_budget_ref`, `boundary_coupling_rows`, `forecast_support_label`, `critical_path_module_refs`, `false_modular_penalty`, and `authority_mode`.

Add `assert_s2_public_projection_has_composition_limitation`, export it from `src/polisyos/pdc/__init__.py`, and call it for PUBLIC when S5 fields are present. Projection must work when S5 is present even if S4 is absent; do not hang S5 projection behind the existing `regime_axis is not None` branch.

- [x] **Step 3: Run S2 tests**

Run:

```bash
cd policy-engine
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
```

Expected: all S2/S4/S5 projection tests pass. The B loop records injected S5 posture and never imports or calls `classify_coupling`.

Task 3 notes, 2026-05-31:

```text
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
21 passed

uv run pytest \
  tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py \
  tests/unit/pdc/test_layer2_s2_design_search.py -q
38 passed

uv run ruff check \
  src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/pdc/__init__.py \
  tests/unit/pdc/test_layer2_s2_design_search.py
All checks passed!
```

## Task 4: Canonical Corpus Route Wiring - 13-Case Coupling Classification

**Files:**

- Create: `tests/fixtures/layer2/s5/s5_coupling_case_signals.json`
- Create: `tests/fixtures/layer2/s5/s5_coupling_expert_labels.json`
- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`
- Modify: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`

- [x] **Step 1: Add 13-case S5 producer signals and expert gold labels**

Create `tests/fixtures/layer2/s5/s5_coupling_case_signals.json` before the gold file. This is the producer input fixture; it must not contain `expert_coupling_regime`, `expected_composition_disposition`, or match booleans.

Use this exact table to populate `cases[case_id].observed_boundaries`:

| case_id | boundary_ref | source_module_ref | target_module_ref | relation | observed_interaction_strength | observed_feedback_intensity |
| --- | --- | --- | --- | --- | --- | --- |
| `ua-msme-affordable-loans-2022` | `boundary://ua-msme/credit/fiscal` | `module://credit-program-enrollment` | `module://fiscal-burden-per-beneficiary` | `credit_fiscal_dependency` | `weak` | `weak` |
| `w11a_berlin_rent_cap_2020` | `boundary://berlin/rent-cap/supply-response` | `module://rent-control-rule` | `module://housing-supply-response` | `strategic_supply_feedback` | `strong` | `high` |
| `w11a_boston_operation_ceasefire_1996` | `boundary://boston/deterrence/community-legitimacy` | `module://focused-deterrence` | `module://community-legitimacy` | `legitimacy_deterrence_feedback` | `strong` | `high` |
| `w11a_eu_temporary_protection_ukraine_2022` | `boundary://eu-tpd/eu-framework/member-state-implementation` | `module://eu-temporary-protection-framework` | `module://member-state-implementation` | `framework_implementation_hierarchy` | `strong` | `weak` |
| `w11a_ghana_free_shs_2017` | `boundary://ghana/free-shs/enrollment/capacity` | `module://fee-removal` | `module://school-capacity` | `enrollment_capacity_hierarchy` | `strong` | `medium` |
| `w11a_india_aadhaar_dbt_2016` | `boundary://aadhaar/identity/payment-exclusion` | `module://digital-identity-authentication` | `module://benefit-payment-delivery` | `authentication_payment_feedback` | `strong` | `high` |
| `w11a_mexico_ssb_tax_2014` | `boundary://mexico-ssb/tax/consumption-response` | `module://excise-tax` | `module://consumer-substitution` | `tax_consumption_dependency` | `weak` | `weak` |
| `w11a_netherlands_room_for_river_2007` | `boundary://room-for-river/hydrology/land-use` | `module://floodplain-redesign` | `module://land-use-compensation` | `hydrology_land_use_feedback` | `strong` | `high` |
| `w11a_pakistan_ehsaas_cash_2020` | `boundary://ehsaas/eligibility/payment` | `module://eligibility-verification` | `module://cash-payment-rail` | `eligibility_payment_interface` | `none` | `none` |
| `w11a_uk_levelling_up_fund_2021` | `boundary://levelling-up/central-scoring/local-delivery` | `module://central-project-selection` | `module://local-delivery-capacity` | `central_local_delivery_hierarchy` | `strong` | `medium` |
| `w11a_uk_mtd_vat_2019` | `boundary://mtd-vat/software-filing/compliance` | `module://digital-recordkeeping` | `module://vat-filing-compliance` | `software_filing_interface` | `none` | `none` |
| `w11a_uk_work_programme_2011` | `boundary://work-programme/provider-incentives/participant-sorting` | `module://payment-by-results` | `module://participant-targeting` | `incentive_sorting_feedback` | `strong` | `high` |
| `w11a_us_ppp_2020` | `boundary://ppp/lender-incentives/firm-access` | `module://bank-origination-channel` | `module://small-business-access` | `lender_access_feedback` | `strong` | `high` |

The signal fixture should also include `_meta.schema_version = "policyos.policy_design_case.layer2_s5.coupling_case_signals.v1"`, `_meta.status = "seeded_producer_inputs"`, and `_meta.may_not_use_for = ["expert_gold_comparison", "production_claim_authority", "calibrated_equilibrium_prediction"]`.

Create `tests/fixtures/layer2/s5/s5_coupling_expert_labels.json`:

```json
{
  "_meta": {
    "schema_version": "policyos.policy_design_case.layer2_s5.coupling_expert_labels.v1",
    "reviewer": "team-foundry-design-composition",
    "adjudication_date": "2026-05-31",
    "status": "seeded_for_confirmation",
    "rule_version_ref": "repo://docs/adr/0174-policy-evidence-capability-graph.md",
    "authority_boundary": {
      "authoritative_for": [
        "s5_corpus_coupling_gold_comparison",
        "s5_scale_composition_gold_comparison"
      ],
      "may_not_use_for": [
        "production_claim_authority",
        "calibrated_equilibrium_prediction"
      ]
    }
  },
  "cases": {
    "ua-msme-affordable-loans-2022": {
      "expert_coupling_regime": "near_decomposable",
      "expected_feedback_intensity": "weak",
      "expected_composition_disposition": "compose_with_limitations",
      "requires_system_dynamics": false,
      "scale_class": "national_program",
      "forecast_support_scope": {
        "base_origin": "transported_scholar_estimate",
        "claim_scope": "system_effect",
        "support_label": "transported_with_heavy_limitation"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://ua-msme/credit/fiscal",
          "source_module_ref": "module://credit-program-enrollment",
          "target_module_ref": "module://fiscal-burden-per-beneficiary",
          "expert_coupling_regime": "near_decomposable",
          "expected_feedback_intensity": "weak",
          "requires_system_dynamics": false
        }
      ]
    },
    "w11a_berlin_rent_cap_2020": {
      "expert_coupling_regime": "entangled",
      "expected_feedback_intensity": "high",
      "expected_composition_disposition": "system_evidence_required",
      "requires_system_dynamics": true,
      "scale_class": "city_housing_market",
      "forecast_support_scope": {
        "base_origin": "equilibrium_contested",
        "claim_scope": "system_effect",
        "support_label": "equilibrium_contested"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://berlin/rent-cap/supply-response",
          "source_module_ref": "module://rent-control-rule",
          "target_module_ref": "module://housing-supply-response",
          "expert_coupling_regime": "entangled",
          "expected_feedback_intensity": "high",
          "requires_system_dynamics": true
        }
      ]
    },
    "w11a_boston_operation_ceasefire_1996": {
      "expert_coupling_regime": "entangled",
      "expected_feedback_intensity": "high",
      "expected_composition_disposition": "system_evidence_required",
      "requires_system_dynamics": true,
      "scale_class": "city_public_safety_network",
      "forecast_support_scope": {
        "base_origin": "historical_prior",
        "claim_scope": "system_effect",
        "support_label": "historical_prior_system_context"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://boston/deterrence/community-legitimacy",
          "source_module_ref": "module://focused-deterrence",
          "target_module_ref": "module://community-legitimacy",
          "expert_coupling_regime": "entangled",
          "expected_feedback_intensity": "high",
          "requires_system_dynamics": true
        }
      ]
    },
    "w11a_eu_temporary_protection_ukraine_2022": {
      "expert_coupling_regime": "hierarchically_coupled",
      "expected_feedback_intensity": "weak",
      "expected_composition_disposition": "compose_with_limitations",
      "requires_system_dynamics": false,
      "scale_class": "transnational_integration",
      "forecast_support_scope": {
        "base_origin": "historical_prior",
        "claim_scope": "context_only",
        "support_label": "historical_prior_system_context"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://eu-tpd/eu-framework/member-state-implementation",
          "source_module_ref": "module://eu-temporary-protection-framework",
          "target_module_ref": "module://member-state-implementation",
          "expert_coupling_regime": "hierarchically_coupled",
          "expected_feedback_intensity": "weak",
          "requires_system_dynamics": false
        }
      ]
    },
    "w11a_ghana_free_shs_2017": {
      "expert_coupling_regime": "hierarchically_coupled",
      "expected_feedback_intensity": "medium",
      "expected_composition_disposition": "compose_with_limitations",
      "requires_system_dynamics": false,
      "scale_class": "national_education_system",
      "forecast_support_scope": {
        "base_origin": "transported_scholar_estimate",
        "claim_scope": "system_effect",
        "support_label": "transported_with_heavy_limitation"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://ghana/free-shs/enrollment/capacity",
          "source_module_ref": "module://fee-removal",
          "target_module_ref": "module://school-capacity",
          "expert_coupling_regime": "hierarchically_coupled",
          "expected_feedback_intensity": "medium",
          "requires_system_dynamics": false
        }
      ]
    },
    "w11a_india_aadhaar_dbt_2016": {
      "expert_coupling_regime": "entangled",
      "expected_feedback_intensity": "high",
      "expected_composition_disposition": "system_evidence_required",
      "requires_system_dynamics": true,
      "scale_class": "national_digital_welfare_infrastructure",
      "forecast_support_scope": {
        "base_origin": "equilibrium_contested",
        "claim_scope": "system_effect",
        "support_label": "equilibrium_contested"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://aadhaar/identity/payment-exclusion",
          "source_module_ref": "module://digital-identity-authentication",
          "target_module_ref": "module://benefit-payment-delivery",
          "expert_coupling_regime": "entangled",
          "expected_feedback_intensity": "high",
          "requires_system_dynamics": true
        }
      ]
    },
    "w11a_mexico_ssb_tax_2014": {
      "expert_coupling_regime": "near_decomposable",
      "expected_feedback_intensity": "weak",
      "expected_composition_disposition": "compose_with_limitations",
      "requires_system_dynamics": false,
      "scale_class": "national_tax_public_health",
      "forecast_support_scope": {
        "base_origin": "historical_prior",
        "claim_scope": "system_effect",
        "support_label": "historical_prior_system_context"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://mexico-ssb/tax/consumption-response",
          "source_module_ref": "module://excise-tax",
          "target_module_ref": "module://consumer-substitution",
          "expert_coupling_regime": "near_decomposable",
          "expected_feedback_intensity": "weak",
          "requires_system_dynamics": false
        }
      ]
    },
    "w11a_netherlands_room_for_river_2007": {
      "expert_coupling_regime": "entangled",
      "expected_feedback_intensity": "high",
      "expected_composition_disposition": "system_evidence_required",
      "requires_system_dynamics": true,
      "scale_class": "river_basin_adaptation_system",
      "forecast_support_scope": {
        "base_origin": "validated_local_model",
        "claim_scope": "system_effect",
        "support_label": "validated_local_dynamic_model"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://room-for-river/hydrology/land-use",
          "source_module_ref": "module://floodplain-redesign",
          "target_module_ref": "module://land-use-compensation",
          "expert_coupling_regime": "entangled",
          "expected_feedback_intensity": "high",
          "requires_system_dynamics": true
        }
      ]
    },
    "w11a_pakistan_ehsaas_cash_2020": {
      "expert_coupling_regime": "modular",
      "expected_feedback_intensity": "none",
      "expected_composition_disposition": "compose",
      "requires_system_dynamics": false,
      "scale_class": "national_cash_transfer",
      "forecast_support_scope": {
        "base_origin": "historical_prior",
        "claim_scope": "leaf_only",
        "support_label": "leaf_only_no_system_claim"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://ehsaas/eligibility/payment",
          "source_module_ref": "module://eligibility-verification",
          "target_module_ref": "module://cash-payment-rail",
          "expert_coupling_regime": "modular",
          "expected_feedback_intensity": "none",
          "requires_system_dynamics": false
        }
      ]
    },
    "w11a_uk_levelling_up_fund_2021": {
      "expert_coupling_regime": "hierarchically_coupled",
      "expected_feedback_intensity": "medium",
      "expected_composition_disposition": "compose_with_limitations",
      "requires_system_dynamics": false,
      "scale_class": "national_portfolio_grant_program",
      "forecast_support_scope": {
        "base_origin": "transported_scholar_estimate",
        "claim_scope": "routing_only",
        "support_label": "transported_with_heavy_limitation"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://levelling-up/central-scoring/local-delivery",
          "source_module_ref": "module://central-project-selection",
          "target_module_ref": "module://local-delivery-capacity",
          "expert_coupling_regime": "hierarchically_coupled",
          "expected_feedback_intensity": "medium",
          "requires_system_dynamics": false
        }
      ]
    },
    "w11a_uk_mtd_vat_2019": {
      "expert_coupling_regime": "modular",
      "expected_feedback_intensity": "none",
      "expected_composition_disposition": "compose",
      "requires_system_dynamics": false,
      "scale_class": "national_tax_administration",
      "forecast_support_scope": {
        "base_origin": "historical_prior",
        "claim_scope": "leaf_only",
        "support_label": "leaf_only_no_system_claim"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://mtd-vat/software-filing/compliance",
          "source_module_ref": "module://digital-recordkeeping",
          "target_module_ref": "module://vat-filing-compliance",
          "expert_coupling_regime": "modular",
          "expected_feedback_intensity": "none",
          "requires_system_dynamics": false
        }
      ]
    },
    "w11a_uk_work_programme_2011": {
      "expert_coupling_regime": "entangled",
      "expected_feedback_intensity": "high",
      "expected_composition_disposition": "system_evidence_required",
      "requires_system_dynamics": true,
      "scale_class": "national_labor_market_program",
      "forecast_support_scope": {
        "base_origin": "equilibrium_contested",
        "claim_scope": "system_effect",
        "support_label": "equilibrium_contested"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://work-programme/provider-incentives/participant-sorting",
          "source_module_ref": "module://payment-by-results",
          "target_module_ref": "module://participant-targeting",
          "expert_coupling_regime": "entangled",
          "expected_feedback_intensity": "high",
          "requires_system_dynamics": true
        }
      ]
    },
    "w11a_us_ppp_2020": {
      "expert_coupling_regime": "entangled",
      "expected_feedback_intensity": "high",
      "expected_composition_disposition": "system_evidence_required",
      "requires_system_dynamics": true,
      "scale_class": "national_crisis_credit_program",
      "forecast_support_scope": {
        "base_origin": "simulation_only",
        "claim_scope": "system_effect",
        "support_label": "simulation_only_system_effect"
      },
      "boundary_gold": [
        {
          "boundary_ref": "boundary://ppp/lender-incentives/firm-access",
          "source_module_ref": "module://bank-origination-channel",
          "target_module_ref": "module://small-business-access",
          "expert_coupling_regime": "entangled",
          "expected_feedback_intensity": "high",
          "requires_system_dynamics": true
        }
      ]
    }
  }
}
```

- [x] **Step 2: Add S5 corpus route**

In `run_universal_outcome_corpus.py`:

- Import S5 contracts.
- Add `S5_CASE_SIGNALS_PATH = Path("tests/fixtures/layer2/s5/s5_coupling_case_signals.json")`.
- Add `S5_EXPERT_LABELS_PATH = Path("tests/fixtures/layer2/s5/s5_coupling_expert_labels.json")`.
- Add `_s5_coupling_composition_summary(case, repo_root, s4_epistemic_regime)`.
- Add `_s5_coupling_summary(cases)`.
- Add `s5_coupling_composition` to each case result.
- Add top-level `s5_coupling_summary` to the report.
- Pass the pinned case's S5 refs, boundary rows, ForecastSupport scope, and tractability budget into `_s2_design_search_summary`.

Deterministic per-case graph construction:

- Load the case's S5 producer-input row from `s5_coupling_case_signals.json` and the gold comparison row from `s5_coupling_expert_labels.json`. Prediction graph construction must not read `expert_coupling_regime`, `expected_composition_disposition`, or any gold match boolean.
- `module_refs` is the stable sorted union of every `source_module_ref` and `target_module_ref` in `observed_boundaries`.
- Call `discover_design_modules` with those module refs as candidates and `case_signal_refs=[f"fixture://layer2/s5/{case_id}/case-signals"]`; pass `discovered.discovered_module_refs` and `discovered.module_discovery_ref` into `build_coupling_graph`.
- Convert every `observed_boundaries` row into a `CouplingEdge` with the same `boundary_ref`, source, target, relation, `interaction_strength=observed_interaction_strength`, `feedback_intensity=observed_feedback_intensity`, and `evidence_ref=f"fixture://layer2/s5/{case_id}/{boundary_ref}"`.
- Set `feedback=True` only when `observed_feedback_intensity == "high"`; keep `feedback_intensity` on the edge for `none`/`weak`/`medium`/`high` replay and gold comparison.
- For a one-row case with `observed_feedback_intensity == "high"`, add a deterministic reverse `CouplingEdge` with the same `boundary_ref`, `interaction_strength="strong"`, `feedback_intensity="high"`, `feedback=True`, `relation="feedback_return_path"`, and the same boundary evidence suffix so P17 sees a strong feedback cycle rather than a label-only assertion. Boundary classification aggregates all edges with the same `boundary_ref` into one replay row, so the synthetic return path does not create an extra gold-comparison row.
- Build `RecursiveDesignGraph` from the discovered modules, set the root node kind to `policy_program`, leaf modules to `design_candidate`, and use boundary refs as `interface_refs`.
- Use `critical_path_module_refs` from the observed boundary rows in declaration order, de-duplicated; do not include peripheral modules merely because they exist in the case file.
- Compute `boundary_rows_match_gold` by comparing boundary ref, source ref, target ref, predicted coupling regime, predicted feedback intensity, and dynamics trigger for every boundary row.

Per-case S5 block schema:

```python
{
    "schema_version": "policyos.policy_design_case.layer2_s5.case_coupling_summary.v1",
    "status": "pass",
    "case_id": case_id,
    "classifier_owner": "A_gate",
    "predicted_coupling_regime": classification.coupling_regime,
    "expert_coupling_regime": expert_coupling_regime,
    "predicted_feedback_intensity": classification.feedback_intensity,
    "expected_feedback_intensity": expected_feedback_intensity,
    "coupling_matches_gold": classification.coupling_regime == expert_coupling_regime,
    "boundary_coupling_table": [
        row.model_dump(mode="json") for row in classification.boundary_classifications
    ],
    "boundary_gold": boundary_gold,
    "boundary_rows_match_gold": boundary_rows_match_gold,
    "scale_class": scale_class,
    "composition_disposition": decomposition.composition_disposition,
    "expected_composition_disposition": expected_composition_disposition,
    "composition_matches_gold": decomposition.composition_disposition == expected_composition_disposition,
    "forecast_support_scope": system_effect_support.model_dump(mode="json"),
    "tractability_budget": tractability_budget.model_dump(mode="json"),
    "coupling_graph": graph.model_dump(mode="json"),
    "coupling_classification": classification.model_dump(mode="json"),
    "decomposition_result": decomposition.model_dump(mode="json"),
    "system_dynamics_requirement": dynamics.model_dump(mode="json") if dynamics else None,
    "composition_receipt": receipt.model_dump(mode="json"),
    "coupling_graph_ref": f"pdc://layer2/s5/{case_id}/coupling-graph",
    "module_discovery_ref": f"pdc://layer2/s5/{case_id}/module-discovery",
    "decomposition_result_ref": f"pdc://layer2/s5/{case_id}/decomposition-result",
    "composition_receipt_ref": f"pdc://layer2/s5/{case_id}/composition-receipt",
    "dynamics_requirement_ref": f"pdc://layer2/s5/{case_id}/system-dynamics-requirement" if dynamics else None,
    "tractability_budget_ref": f"pdc://layer2/s5/{case_id}/tractability-budget",
    "canonical_outcome_effect": "none_shadow_only"
}
```

Top-level summary schema:

```python
{
    "schema_version": "policyos.policy_design_case.layer2_s5.coupling_corpus_summary.v1",
    "case_count": 13,
    "coupling_accuracy": accuracy["accuracy"],
    "false_modular_count": accuracy["false_modular_count"],
    "false_entangled_count": accuracy["false_entangled_count"],
    "penalized_score": accuracy["penalized_score"],
    "system_evidence_required_count": sum(
        1 for case in cases if case["s5_coupling_composition"]["composition_disposition"] == "system_evidence_required"
    ),
    "coupling_regime_counts": dict(Counter(
        case["s5_coupling_composition"]["predicted_coupling_regime"] for case in cases
    )),
    "boundary_regime_counts": dict(Counter(
        row["coupling_regime"]
        for case in cases
        for row in case["s5_coupling_composition"]["boundary_coupling_table"]
    )),
    "system_effect_support_labels": sorted({
        case["s5_coupling_composition"]["forecast_support_scope"]["support_label"] for case in cases
    }),
    "per_case_coupling_table": [
        {
            "case_id": case["case_id"],
            "predicted_coupling_regime": case["s5_coupling_composition"]["predicted_coupling_regime"],
            "expert_coupling_regime": case["s5_coupling_composition"]["expert_coupling_regime"],
            "composition_disposition": case["s5_coupling_composition"]["composition_disposition"],
            "boundary_count": len(case["s5_coupling_composition"]["boundary_coupling_table"]),
        }
        for case in cases
    ]
}
```

- [x] **Step 3: Add W12.D route assertions**

Append tests to `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`:

```python
def test_w12d_emits_s5_coupling_for_13_cases(tmp_path: Path) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )

    assert report["summary"]["case_count"] == 13
    s5_blocks = [case["s5_coupling_composition"] for case in report["cases"]]
    assert len(s5_blocks) == 13
    assert {block["classifier_owner"] for block in s5_blocks} == {"A_gate"}
    assert all(block["coupling_graph_ref"].startswith("pdc://layer2/s5/") for block in s5_blocks)
    assert all(block["module_discovery_ref"].startswith("pdc://layer2/s5/") for block in s5_blocks)
    assert all(block["decomposition_result_ref"].startswith("pdc://layer2/s5/") for block in s5_blocks)
    assert all(block["composition_receipt_ref"].startswith("pdc://layer2/s5/") for block in s5_blocks)
    assert all(block["tractability_budget_ref"].startswith("pdc://layer2/s5/") for block in s5_blocks)
    assert all(block["boundary_coupling_table"] for block in s5_blocks)
    assert all(
        block["predicted_feedback_intensity"] == block["expected_feedback_intensity"]
        for block in s5_blocks
    )
    assert all(block["predicted_coupling_regime"] != "modular" or block["composition_disposition"] == "compose" for block in s5_blocks)
```

```python
def test_w12d_s5_prediction_inputs_do_not_contain_gold_labels() -> None:
    signals = json.loads((REPO_ROOT / "tests/fixtures/layer2/s5/s5_coupling_case_signals.json").read_text(encoding="utf-8"))
    forbidden = {
        "expert_coupling_regime",
        "expected_composition_disposition",
        "coupling_matches_gold",
        "composition_matches_gold",
    }

    for entry in signals["cases"].values():
        assert forbidden.isdisjoint(entry)
        for boundary in entry["observed_boundaries"]:
            assert forbidden.isdisjoint(boundary)
```

```python
def test_w12d_s5_records_coupling_accuracy_and_false_modular_penalty(tmp_path: Path) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )

    summary = report["s5_coupling_summary"]
    assert summary["case_count"] == 13
    assert summary["coupling_accuracy"] >= 0.9
    assert summary["penalized_score"] >= 0.9
    assert summary["false_modular_count"] == 0
    assert summary["false_entangled_count"] >= 0
    assert summary["system_evidence_required_count"] >= 1
    assert set(summary["coupling_regime_counts"]) >= {
        "modular",
        "near_decomposable",
        "hierarchically_coupled",
        "entangled",
    }
    assert set(summary["boundary_regime_counts"]) >= {
        "modular",
        "near_decomposable",
        "hierarchically_coupled",
        "entangled",
    }
    assert "simulation_only_system_effect" in summary["system_effect_support_labels"]
    assert len(summary["per_case_coupling_table"]) == 13
```

```python
def test_w12d_s5_does_not_change_canonical_closeout_outcome(tmp_path: Path) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
    )

    case = report["cases"][0]
    assert case["s5_coupling_composition"]["canonical_outcome_effect"] == "none_shadow_only"
    assert case["outcome"] == "publish-with-limitation"
    assert report["summary"]["closeout_honesty_rate"] == 1.0
```

- [x] **Step 4: Run route tests**

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
```

Expected: W12.D tests pass, S5 summary is present, and canonical closeout metrics are unchanged.

Task 4 notes, 2026-05-31:

```text
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
21 passed

uv run ruff check \
  tools/quality/validation/run_universal_outcome_corpus.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py
All checks passed!

S5 emitted summary:
case_count=13
coupling_accuracy=1.0
penalized_score=1.0
false_modular_count=0
coupling_regime_counts={
  "near_decomposable": 2,
  "entangled": 6,
  "hierarchically_coupled": 3,
  "modular": 2
}
```

## Task 5: S5 Manifest, Readiness Validator, And Cluster-Map Cell Closure

**Files:**

- Create: `architecture/policy_design_case/layer2_s5_coupling_composition_manifest.json`
- Modify: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- Modify: `architecture/policy_design_case/cluster_ownership_map.toml`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`

- [x] **Step 1: Create S5 manifest**

Create or refresh this manifest only after Task 4 has emitted `s5_coupling_summary`. Copy `coupling_accuracy`, `penalized_score`, `false_modular_count`, `false_entangled_count`, regime counts, and support labels from that report. The fast readiness validator checks the manifest's static facts and thresholds; the repo-quality route test in Step 4 compares manifest metrics to a freshly generated `s5_coupling_summary`. The payload below shows the expected deterministic seeded outcome shape.

Create `architecture/policy_design_case/layer2_s5_coupling_composition_manifest.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s5_coupling_composition_manifest.v1",
  "manifest_id": "layer2_s5_coupling_composition",
  "slice": "S5",
  "slice_label": "coupling_composition",
  "status": "active",
  "cells_closed": [
    "SYSTEM.connectivity_modularity",
    "SYSTEM.dynamics_feedback",
    "INTERVENTION.scale_composition"
  ],
  "open_cell_count_baseline": 17,
  "expected_current_open_cell_count": 10,
  "floors": ["s5_coupling_accuracy"],
  "coupling_summary_source_ref": "report://w12d/s5_coupling_summary",
  "coupling_accuracy": 1.0,
  "penalized_score": 1.0,
  "false_modular_count": 0,
  "false_entangled_count": 0,
  "coupling_regime_counts": {
    "modular": 2,
    "near_decomposable": 2,
    "hierarchically_coupled": 3,
    "entangled": 6
  },
  "boundary_regime_counts": {
    "modular": 2,
    "near_decomposable": 2,
    "hierarchically_coupled": 3,
    "entangled": 6
  },
  "system_effect_support_labels": [
    "equilibrium_contested",
    "historical_prior_system_context",
    "leaf_only_no_system_claim",
    "simulation_only_system_effect",
    "transported_with_heavy_limitation",
    "validated_local_dynamic_model"
  ],
  "proving_ground_case_count": 13,
  "required_artifacts": [
    "CompositionReceipt",
    "ComputationalTractabilityBudget",
    "CouplingGraph",
    "CouplingRegimeClassification",
    "DecompositionResult",
    "DesignInterfaceContract",
    "RecursiveDesignGraph",
    "SystemDynamicsRequirement"
  ],
  "nested_records": [
    "BoundaryCouplingClassification",
    "CompositionLawCheck",
    "ForecastSupportScope",
    "ModuleDiscoveryResult"
  ],
  "may_not_use_for": [
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "equilibrium_prediction_authority",
    "simulation_calibration_authority",
    "whole_design_authority_without_coupling_graph",
    "whole_design_authority_from_syntactic_decomposition",
    "whole_design_authority_from_user_supplied_module_split",
    "averaged_cross_level_authority",
    "false_modular_decomposition",
    "weakened_authority_from_tractability_cutoff"
  ],
  "semantic_tests": [
    "tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py",
    "tests/unit/pdc/test_layer2_s2_design_search.py",
    "tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py"
  ],
  "negative_controls": [
    "tests/fixtures/layer2/s5/false_modular_probe.json",
    "tests/fixtures/layer2/s5/syntactic_decomposition_probe.json",
    "tests/fixtures/layer2/s5/boundary_spoof_probe.json"
  ],
  "rule_version_ref": "repo://docs/adr/0174-policy-evidence-capability-graph.md",
  "relevant_patterns": ["P01", "P03", "P05", "P10", "P13", "P15", "P17", "P24"],
  "authority_boundary": "shadow_governed_composition_gate_only_no_production_or_prediction_authority"
}
```

- [x] **Step 2: Add readiness validator support**

Modify `check_policy_design_case_layer2_readiness.py`:

- Add `DEFAULT_S5_COUPLING_COMPOSITION_MANIFEST_PATH`.
- Load payload as `"s5_coupling_composition"`.
- Call `_validate_s5_coupling_composition` after S4 validation.
- Add summary keys:
  - `s5_coupling_accuracy`
  - `s5_penalized_score`
  - `s5_expected_current_open_cell_count`
  - `s5_false_modular_count`
  - `s5_false_entangled_count`
  - `s5_coupling_regime_counts`
  - `s5_boundary_regime_counts`
  - `s5_system_effect_support_labels`

Validator requirements:

- `cells_closed` exactly equals the three S5 cells.
- `expected_current_open_cell_count == 10`.
- S5 cells are not present in `open_cell_closure`.
- `s5_coupling_accuracy` floor exists.
- `false_modular_count == 0`.
- `false_entangled_count` is present and non-negative.
- `penalized_score >= 0.9`.
- Do not run W12.D from the readiness validator. The validator is a fast file/static check: it validates metric presence, thresholds, regime-count coverage, cells, floor, deny-list, inventory, and artifact/nested-record shape. Manifest-to-generated-summary equality belongs in the repo-quality route test below.
- `coupling_regime_counts` and `boundary_regime_counts` contain all four D2.6 regimes: `modular`, `near_decomposable`, `hierarchically_coupled`, `entangled`.
- `nested_records` includes `ModuleDiscoveryResult`, `BoundaryCouplingClassification`, `ForecastSupportScope`, and `CompositionLawCheck`; `required_artifacts` stays aligned with `layer2_artifact_traceability.toml`.
- `negative_controls` includes `boundary_spoof_probe.json`.
- Manifest has required deny-list entries.
- Manifest is registered in inventory. This check is expected to fail until Task 6.

- [x] **Step 3: Close cluster-map cells**

In `architecture/policy_design_case/cluster_ownership_map.toml`:

- Remove `[open_cell_closure.SYSTEM.connectivity_modularity]`.
- Remove `[open_cell_closure.SYSTEM.dynamics_feedback]`.
- Remove `[open_cell_closure.INTERVENTION.scale_composition]`.
- Set each matching `[cell.*]` to:
  - `owner_module = "src/polisyos/runtime/quality"` for `SYSTEM.connectivity_modularity` and `SYSTEM.dynamics_feedback`;
  - `owner_module = "src/polisyos/pdc"` for `INTERVENTION.scale_composition` because the consumer/projection bridge lives in the S2 narrow waist;
  - `ratchet_state = "implemented"`
  - `p01_chain = "implemented"`
  - `gap = "none_for_s5_scope"`
  - action text naming the next slice only where relevant, without re-opening the cell.

- [x] **Step 4: Add S5 repo-quality tests**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py` with tests:

- manifest is valid and readiness open count is `10`;
- manifest records cells, metrics, artifacts, and authority boundary;
- cluster map marks three S5 cells `implemented`;
- S5 labels cover all 13 corpus cases and all four D2.6 regimes at boundary level;
- S5 case-signal fixture covers the same 13 corpus cases and contains no expert/gold fields;
- a repo-quality test runs `run_w12d_universal_outcome_corpus` and compares manifest summary metrics to the generated Task 4 S5 corpus summary, including `coupling_accuracy`, `penalized_score`, `false_modular_count`, `false_entangled_count`, regime counts, boundary counts, and support labels;
- readiness rejects stale manifest metrics, missing nested `BoundaryCouplingClassification`, missing `ForecastSupportScope`, missing `ComputationalTractabilityBudget`, or missing `boundary_spoof_probe.json`;
- readiness rejects missing P17 authority boundary;
- readiness rejects S5 cells still open;
- inventory registration test remains red until Task 6.

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py -q
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
```

Expected after Step 3: cluster ownership passes with `open_or_incomplete_count` / open-cell count `10`. Full readiness may fail only on S5 manifest inventory registration until Task 6.

Task 5 notes, 2026-05-31:

```text
Red-first:
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py -q
12 failed, 2 passed

Green:
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py -q
14 passed

uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
status=pass
open_or_incomplete_count=10
open_cell_closure.open_cell_count=10

uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
status=fail
issues=["layer2_s5_manifest_missing_from_inventory"]
current_open_cell_count=10
s5_coupling_accuracy=1.0
s5_penalized_score=1.0
s5_false_modular_count=0
s5_false_entangled_count=0

uv run ruff check \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py
All checks passed!

python3 -m json.tool architecture/policy_design_case/layer2_s5_coupling_composition_manifest.json
ok

git diff --check
ok
```

## Task 6: Repo-Quality Tests, Inventory, Snapshot Updates, And Burn-Down Confirmation

**Files:**

- Modify: `architecture/policy_design_case/inventory.json`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`

- [x] **Step 1: Register S5 manifest in inventory**

Add an inventory artifact:

```json
{
  "id": "layer2_s5_coupling_composition_manifest",
  "path": "architecture/policy_design_case/layer2_s5_coupling_composition_manifest.json",
  "kind": "layer2_s5_coupling_composition_manifest",
  "schema_version": "policyos.policy_design_case.layer2_s5_coupling_composition_manifest.v1",
  "owner": "team-foundry-design-composition",
  "status": "active",
  "capability_reality_label": "implemented",
  "authority_scope": [
    "coupling_regime_classification",
    "composition_gate",
    "system_dynamics_requirement",
    "boundary_coupling_classification",
    "system_effect_support_scope",
    "computational_tractability_budget"
  ],
  "may_not_use_for": [
    "production_claim_authority",
    "equilibrium_prediction_authority",
    "whole_design_authority_without_coupling_graph",
    "whole_design_authority_from_user_supplied_module_split",
    "false_modular_decomposition",
    "weakened_authority_from_tractability_cutoff"
  ],
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py"
}
```

- [x] **Step 2: Update live open-count snapshots from 13 to 10**

Update only live snapshot assertions. Do not rewrite S2/S3/S4 static manifest expectations.

Required updates:

- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
  - `summary["current_open_cell_count"] == 10`
  - `cells_closed_since_s0` includes:
    - `INTERVENTION.scale_composition`
    - `SYSTEM.connectivity_modularity`
    - `SYSTEM.dynamics_feedback`
  - `assigned - current_open_cells` includes the four S2/S4 cells plus the three S5 cells.
- `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`
  - `open_cell_closure["open_cell_count"] == 10`
  - known blind-spot test no longer expects S5 `p01_chain` to be `bridge_missing`; assert `SYSTEM.connectivity_modularity` and `INTERVENTION.scale_composition` have `p01_chain == "implemented"` and `ratchet_state == "implemented"`. Also assert `SYSTEM.dynamics_feedback` has `ratchet_state == "implemented"`; add a `p01_chain == "implemented"` assertion for it if the local test already exposes that field.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
  - live `summary["current_open_cell_count"] == 10`
  - keep S2 manifest static `expected_current_open_cell_count == 15`.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
  - live readiness open count `10`
  - keep S3 manifest static `expected_current_open_cell_count == 15`.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
  - live readiness open count `10`
  - keep S4 manifest static `expected_current_open_cell_count == 13`.

- [x] **Step 3: Run repo-quality burn-down tests**

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
```

Expected:

- all listed tests pass;
- readiness validator returns `status: pass`;
- readiness summary has `current_open_cell_count: 10`;
- cluster validator returns `status: pass`;
- cluster open cell count is `10`;
- S5 manifest is registered in inventory.

Task 6 notes, 2026-05-31:

```text
Red-first after updating expected live snapshots and S5 inventory test:
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py -q
6 failed, 55 passed
remaining issue: layer2_s5_manifest_missing_from_inventory

Green:
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py -q
61 passed

uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
status=pass
current_open_cell_count=10
inventory_artifact_count=13
s5_coupling_accuracy=1.0
s5_penalized_score=1.0
s5_false_modular_count=0
s5_false_entangled_count=0

uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
status=pass
open_or_incomplete_count=10
open_cell_closure.open_cell_count=10

uv run ruff check \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py
All checks passed!

python3 -m json.tool architecture/policy_design_case/inventory.json >/dev/null
python3 -m json.tool architecture/policy_design_case/layer2_s5_coupling_composition_manifest.json >/dev/null
ok

git diff --check
ok
```

## Task 7: Full S5 Verification

- [x] **Step 1: Run the full S5 + regression gate**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py -q
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py -q
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q
uv run pytest tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py tests/unit/runtime/quality/test_layer2_graded_outcomes.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools architecture guardrails check
```

Expected:

```text
S5 unit + repo-quality tests pass.
S2/S3/S4 regression tests pass.
W12.D route emits s4_epistemic_regime and s5_coupling_composition for all 13 cases.
Layer 2 readiness validator: status pass; open_cell_count/current_open_cell_count 10; S5 cells closed.
Cluster ownership validator: status pass; open_or_incomplete/open-cell count 10.
Capability ratchet unchanged/green.
Runtime API contract pass.
Architecture guardrails pass.
```

Record the verified coupling accuracy, penalized score, false-modular count, system-evidence-required count, and any Done-When caveat directly under this task.

Task 7 notes, 2026-05-31:

```text
uv run pytest tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py -q
17 passed

uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
21 passed

uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py -q
14 passed

uv run pytest \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
29 passed

uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q
43 passed

uv run pytest \
  tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py \
  tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py \
  tests/unit/runtime/quality/test_layer2_graded_outcomes.py -q
36 passed

uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
status=pass
open_cell_count=10
current_open_cell_count=10
cells_closed_since_s0 includes:
  INTERVENTION.scale_composition
  SYSTEM.connectivity_modularity
  SYSTEM.dynamics_feedback
s5_coupling_accuracy=1.0
s5_penalized_score=1.0
s5_false_modular_count=0
s5_false_entangled_count=0

uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
status=pass
open_or_incomplete_count=10
open_cell_closure.open_cell_count=10

PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
Runtime API contract check passed.

uv run polisyos-tools architecture guardrails check
Architecture guardrail check passed.

Done-When probes:
runtime.quality exports all 13 S5 top-level/nested contracts as strict frozen Layer2ReadinessModel DTOs.
PDC B-side rg for layer2_coupling_composition/classify_coupling/decompose_design/build_coupling_graph returned no matches.
W12.D S5 metrics:
  case_count=13
  coupling_accuracy=1.0
  penalized_score=1.0
  false_modular_count=0
  false_entangled_count=0
  system_evidence_required_count=6
  coupling_regime_counts={"near_decomposable": 2, "entangled": 6, "hierarchically_coupled": 3, "modular": 2}
  boundary_regime_counts={"near_decomposable": 2, "entangled": 6, "hierarchically_coupled": 3, "modular": 2}
  system_effect_support_labels=[
    "equilibrium_contested",
    "historical_prior_system_context",
    "leaf_only_no_system_claim",
    "simulation_only_system_effect",
    "transported_with_heavy_limitation",
    "validated_local_dynamic_model"
  ]
  canonical_outcome_effects=["none_shadow_only"]
S2 DesignRecordV0.ledger_refs contain module_discovery/coupling_graph/decomposition/receipt/dynamics/tractability refs.
project_s2_design_search renders S5 posture for PUBLIC, REVIEWER, EXPERT, and MACHINE.
No Done-When caveat recorded for S5 scope; no S6+ cell, production authority, calibrated equilibrium prediction, rich simulation, portfolio optimization, or S14 universality claim was marked implemented.
```

## Done When

1. The named S5 artifacts (`CouplingGraph`, `CouplingRegimeClassification`, `DecompositionResult`, `RecursiveDesignGraph`, `DesignInterfaceContract`, `SystemDynamicsRequirement`, `CompositionReceipt`, and `ComputationalTractabilityBudget`) plus nested `BoundaryCouplingClassification`, `ModuleDiscoveryResult`, `ForecastSupportScope`, and `CompositionLawCheck` records are strict, replayable, and exported from `runtime.quality`.
2. Coupling classification is A-gate-owned. B consumes injected coupling/composition posture and cannot self-classify, self-decompose, or compose authority without an S5 receipt.
3. Modules are discovered producer results with replayable `module_discovery_ref`; user-supplied module splits and modularization proposals are candidate hypotheses only and cannot prove decomposition validity until A emits a new coupling graph.
4. Coupling is boundary-specific first. Each case records boundary/interface rows, all four D2.6 regimes are covered (`modular`, `near_decomposable`, `hierarchically_coupled`, `entangled`), and the design-level summary cannot hide a blocking boundary.
5. Default is toward more coupling: absent graph, absent edge evidence, missing module discovery, or syntactic decomposition without proof cannot return `modular`.
6. `false_modular_probe` with strong cyclic cross-effects fails P17; `syntactic_decomposition_probe` fails P17; `boundary_spoof_probe` fails P17; entangled designs with `feedback_intensity="high"` and no dynamics evidence cannot publish a system-level effect claim.
7. Modular, near-decomposable, or hierarchically coupled boundaries may compose only through a `CompositionReceipt`; near-decomposable and hierarchically coupled cases carry residual or propagated limitations.
8. Entangled cases route to `SystemDynamicsRequirement` and downgrade/system-evidence-required posture, not partial-equilibrium optimization or production authority.
9. Critical-path authority composition and composition laws are implemented: module regimes compose by critical path, not by average and not by min-over-all modules; identity/no-op, associativity/regrouping invariance, typed interface compatibility, critical-path monotonicity, and explicit boundary refs are enforced.
10. System-effect scope reuses the D3.5 `ForecastSupport` dictionary (`base_origin + claim_scope`), and `ComputationalTractabilityBudget` is produced and consumed by the receipt without weakening authority requirements.
11. All 13 corpus cases are classified against expert gold labels; `coupling_accuracy_with_false_modular_penalty >= floor`; false-modular count is `0`; per-case boundary table is recorded.
12. Production-posture outcomes and closeout honesty are unchanged by S5; S5 affects shadow/governed composition routing only.
13. `SYSTEM.connectivity_modularity`, `SYSTEM.dynamics_feedback`, and `INTERVENTION.scale_composition` are `implemented`; cluster-map open cell count is `10`; both validators pass; the S5 manifest is registered in inventory.
14. Full S5 artifacts are persisted as replayable ledger refs on `DesignRecordV0.ledger_refs`, and S5 posture renders in all four audience projections via `project_s2_design_search`:
    - PUBLIC: coupling regime + composition limitation.
    - REVIEWER: coupling regime + P17 status + composition disposition.
    - EXPERT/MACHINE: module-discovery/graph/decomposition/receipt/dynamics/tractability refs, boundary rows, ForecastSupport scope, critical path, residual risk, false-modular penalty, authority mode.

## Verification Commands

See Task 7. Plan-level done = all Task 7 commands pass with the expected output, the open cell count is `10`, S5 corpus coupling metrics are recorded, and no production floor is weakened.

## Commit Guidance

Mirror the S4 red-first sequence, one logical commit per task:

```text
test: add layer2 s5 coupling-composition red tests
feat: add layer2 s5 coupling classifier, decomposition, and P17 firewalls
feat: inject layer2 s5 composition into shadow design loop
feat: classify layer2 s5 corpus coupling and scale composition
chore: close layer2 s5 coupling and composition cells
chore: register layer2 s5 coupling-composition progress
```

End commit messages with the repo's standard co-author trailer. Do not mark any S6+ cell, production authority, calibrated equilibrium prediction, rich simulation, portfolio optimization, or S14 universality battery cell as implemented.
