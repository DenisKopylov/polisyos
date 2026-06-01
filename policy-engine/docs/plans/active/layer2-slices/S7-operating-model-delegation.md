---
title: PolicyOS Layer 2 S7 Operating Model / Delegation Implementation Plan
status: active
owner: governance-board
created: 2026-06-01
last_verified: null
stability: draft
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
slice: S7
slice_label: operating_model_delegation
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on: S6
---

# Layer 2 S7 Operating Model / Delegation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make human-in-the-loop delegation a typed, mandate-bounded operating model where autonomy means `capable ∩ permitted ∩ within-bounds`, and where human approval is an accountable record rather than responsibility theater.

**Architecture:** S7 adds A-side runtime-quality delegation contracts and P26 responsibility-integrity checks, then injects a compact `Layer2S7DelegationPostureInput` into the S2/S4/S5/S6 shadow loop. The producer owns `DelegationContract`, `DecisionRightsMatrix`, `HumanDecisionRequest`, and `HumanDecisionRecord`; B consumes those records and can pause, request, route, or record a human decision, but cannot self-approve, choose values, infer mandate, or promote to production. S7 closes the S7-owned orchestration/delegation layer of `CROSS_CUTTING.scientist_orchestration` without claiming full S8 value-choice provenance, S13 oversight effectiveness, or production authority.

**Tech Stack:** Python 3.14, Pydantic v2 strict models through S0 `Layer2ReadinessModel`, existing S0 `GovernanceDecisionClass`, `ValueOfInformationEstimate`, `AuthorityBoundary`, S2 `ClusterHandoffRecord` / `RefinementDecision` / `ConstraintStoreSnapshot`, S6 `MandateLegitimacyRecord` posture, Scientist supervisor seeds in `scientist.agent.supervisor` and `scientist.agent.supervisor_eval`, participation/consultation mandate seeds, `run_universal_outcome_corpus.py`, pytest, and existing `tools.quality.validation` validators.

---

## Scope

This task plan implements only roadmap slice S7.

It does **not** implement: S8 authorized value-choice provenance, Pareto ranking, social-weight selection, S10 outcome prediction, S11 calibration/rich predictive models, S12 envelope-growth economics, S13 full oversight-effectiveness reporting, production recommendation authority, public rollout authority, portfolio optimization, or S14 universality battery closure.

Cell/layer moved by S7:

- `CROSS_CUTTING.scientist_orchestration`: `implemented_but_not_orchestrated -> implemented` for the S7 operating/delegation layer only. S2 already contributed generation handoff records and kept the cell open for S7. S7 closes the typed orchestration/decision-rights handoff chain without assigning the whole Scientist package as authority.

Open cell count delta:

- S0 baseline remains `17`.
- Current cluster-map open cell count becomes `4` after S7 (was `5` after S6).
- S7 records the closed orchestration/delegation cell in its manifest and edits `cluster_ownership_map.toml`:
  - set `[cell.CROSS_CUTTING.scientist_orchestration]` to `ratchet_state="implemented"` and `p01_chain="implemented"`;
  - set `owner_module` to `src/polisyos/runtime/quality/layer2_delegation.py`;
  - keep Scientist seed files as seeds only;
  - set `gap="none_for_s7_delegation_scope"`;
  - remove `[open_cell_closure.CROSS_CUTTING.scientist_orchestration]`.
- Do not mark `ACTOR.value_choice_provenance`, `KNOWLEDGE.calibration`, `KNOWLEDGE.ir_proof_carrying_analytics`, or `DESIGNER_ITSELF.envelope_growth` implemented.
- Do not change `layer2_floor_governance.toml`; the governed `s7_delegation_integrity` floor already exists.
- Do not weaken `layer2_slice_cell_matrix.toml`. The S2 manifest already records `CROSS_CUTTING.scientist_orchestration` as an S2 contribution with `closure_owner_slice="S7"`; S7 provides the closure manifest and cluster-map state.

First proving ground:

- The standing 13 W12 real-producer corpus cases remain the proving ground.
- All 13 cases get an S7 delegation block with a decision-class row, rights-matrix row, request/record disposition, and expert/gold comparison.
- High-stakes, value-laden, out-of-envelope, mandate-limited, and low-VOI cases are represented in `tests/fixtures/layer2/s7/s7_delegation_expert_labels.json`.
- Negative controls:
  - `oversight_theater_probe`: human clicks approval without evidence summary, active choice, disconfirming evidence, or accountability statement; must invalidate the record.
  - `wrong_role_approval_probe`: a role outside `DecisionRightsMatrix.required_role` approves; must invalidate the record.
  - `ai_first_high_stakes_probe`: high-stakes/value-laden/out-of-envelope decision defaults to AI-first; must block.
  - `mandate_absent_delegation_probe`: delegated-autonomous mode is requested without S6 mandate legitimacy; must block.
- `delegation_precision`, `delegation_recall`, and `responsibility_integrity_pass_rate` must be `1.0`.
- `oversight_theater_false_clear_count` and `wrong_role_false_clear_count` must be `0`.

S7 authority boundary:

- `authoritative_for`: `delegation_integrity`, `decision_rights_matrix`, `human_decision_routing`, `mandate_bounded_decision_record`, `responsibility_integrity_check`, `governance_attention_allocation`, `governed_pilot_promotion_gate`.
- `may_not_use_for`: `production_claim_authority`, `rollout_authority`, `publication_authority`, `value_choice_authority`, `social_weight_selection`, `outcome_prediction_authority`, `forecast_calibration_authority`, `oversight_effectiveness_claim`, `human_approval_without_decision_record`, `ai_self_authorization`, `delegated_autonomy_without_mandate`, `s13_accountability_closure`.

Promotion boundary:

- S7 may unlock `governed_pilot` posture for grounded cases when S6 mandate is grounded and the S7 decision record passes responsibility integrity.
- S7 must not unlock `production`.
- S7 must not convert S8 value choices, S10 forecasts, S11 calibration, or S13 accountability into implemented states.

## Architecture Decision

S7 delegation contracts live in `polisyos.runtime.quality`, not in `pdc`, `scientist`, `core.security`, or `foundry`.

Reason: Scientist and security modules contain useful execution and delegation-token seeds, but the Policy Design Case authority gate is runtime-quality. S7 wraps those seeds behind strict PDC delegation records, then gives S2 a compact posture and refs. B can consume those refs and route human attention, but it cannot manufacture approval authority from a workflow summary, a UI click, or a security token.

Module placement:

- Create `src/polisyos/runtime/quality/layer2_delegation.py`.
- Modify `src/polisyos/runtime/quality/__init__.py` to export S7 contracts and producer functions.
- Modify `src/polisyos/pdc/_impl/layer2_design_search.py` to add `Layer2S7DelegationPostureInput`, consume it in the S2 run, record it in constraints/handoffs/design refs, and project it by audience.
- Modify `src/polisyos/pdc/__init__.py` to export the S7 posture DTO.
- Modify `tools/quality/validation/run_universal_outcome_corpus.py` to produce S7 blocks for all 13 cases after S6 and inject the pinned case posture into S2.
- Modify `tools/quality/validation/check_policy_design_case_layer2_readiness.py` to validate the S7 manifest, inventory entry, floor reference, traceability, cluster closure, and summary metrics.

Import boundaries:

- `runtime.quality.layer2_delegation` may import public S0 PDC contracts from `polisyos.pdc`, S6 mandate record shapes by public runtime-quality export, and Scientist supervisor evaluation records by public module.
- `pdc._impl.layer2_design_search` must not import `runtime.quality.layer2_delegation`, `scientist.agent.supervisor`, or `core.security.delegation`.
- `run_universal_outcome_corpus.py` is the orchestrator: it calls S6 producers, builds S7 delegation records, then passes `Layer2S7DelegationPostureInput` into S2 for the pinned design case.
- `core.security.delegation.DelegationTokenManager` is not the S7 PDC delegation record. A signed token can be a provenance ref, never an approval record.

S7 public labels:

- `DelegationInteractionMode`: `ai_follow`, `request_driven`, `ai_first`, `delegated_autonomous`.
- `DecisionRight`: `request_evidence`, `approve`, `reject`, `revise_scope`, `escalate`.
- `DecisionRole`: `policy_design_governance_reviewer`, `mandate_owner`, `domain_principal`, `affected_person_representative`, `accountable_officer`, `technical_reviewer`.
- `DelegationDisposition`: `no_interrupt`, `request_human_decision`, `recorded_valid_decision`, `blocked_wrong_role`, `blocked_oversight_theater`, `blocked_mandate_missing`, `blocked_ai_first_forbidden`.
- `ResponsibilityIntegrityStatus`: `pass`, `limit`, `block`.
- `DecisionNeedReason`: `high_stakes`, `value_laden`, `out_of_envelope`, `mandate_limited`, `low_voi_no_interrupt`, `routine_in_envelope`.

Five-rights rule:

- Every `HumanDecisionRequest` exposes exactly these rights to the accountable human role:
  - `request_evidence`
  - `approve`
  - `reject`
  - `revise_scope`
  - `escalate`
- A record is valid only when the chosen right is allowed by the matrix row for the decision class and the actor role.

Fail-closed delegation rule:

- High-stakes, value-laden, out-of-envelope, or mandate-limited decisions cannot default to `ai_first`.
- `delegated_autonomous` requires:
  - S6 mandate disposition is grounded;
  - decision class allows delegated autonomy;
  - bounds are explicit;
  - active disconfirming evidence was shown or the class is low-risk/no-interrupt.
- A human click without evidence summary, active choice, disconfirming evidence, and accountability statement is `oversight_theater`.
- A decision record from the wrong role is invalid even if the decision content is plausible.
- Low-VOI routine in-envelope actions do not interrupt, but the no-interrupt decision is still recorded and bounded.

Consumer rule:

- S7 emits `AxisPositionDeclaration` and `AxisFirewallStatus` for `CROSS_CUTTING.scientist_orchestration` with pattern ids `P26`, `P12`, `P15`, `P20`, and `P22` as relevant.
- S7 writes typed S2 `ConstraintStoreSnapshot.constraint_records` for pending, requested, blocked, or recorded human-decision states.
- S7 persists top-level refs on `DesignRecordV0.ledger_refs`: `DelegationContract`, `DecisionRightsMatrix`, `HumanDecisionRequest`, and `HumanDecisionRecord` when present.
- S7 emits `ClusterHandoffRecord` rows proving that Scientist orchestration consumed cluster artifacts and emitted/blocked/routed typed handoffs instead of workflow summaries.
- Missing downstream slices become typed pending constraints:
  - S8 value-choice provenance pending when a decision attempts to choose social weights;
  - S13 oversight-effectiveness pending when a record tries to claim full oversight effectiveness;
  - S12 envelope growth pending when a delegated action claims certified envelope expansion.

Audience projection rule:

- `PUBLIC`: decision-shaped, pull-first summary: what decision is needed, who is accountable, what rights are available, what limitation applies. Do not expose machine-only disposition labels such as `blocked_oversight_theater`.
- `REVIEWER`: decision class, required role, interaction mode, right exercised, P26/P20/P22/P12/P15 firewall status, and reason.
- `EXPERT`: all record refs, matrix rows, mandate refs, VOI rank, responsibility-integrity check, disconfirming evidence refs, and negative-control flags.
- `MACHINE`: full compact posture, request/record refs, constraint-store entries, handoff rows, metrics inputs, authority boundary, and governed-pilot eligibility.

## Pattern Pass

Relevant failure patterns: `P01`, `P02`, `P03`, `P04`, `P05`, `P09`, `P10`, `P12`, `P13`, `P15`, `P20`, `P22`, `P25`, `P26`.

Existing risks found:

- `CROSS_CUTTING.scientist_orchestration` is `implemented_but_not_orchestrated` / `bridge_missing`. S2 contributed `ClusterHandoffRecord` for generation but intentionally did not close the whole cell.
- Scientist supervisor and worker orchestration seeds can delegate work, but they are not PDC authority records.
- `GovernanceDecisionClass` exists in S0 and S2 uses it for `a_spec_gap`, but no `DecisionRightsMatrix`, `HumanDecisionRequest`, or `HumanDecisionRecord` currently governs the role/right/record lifecycle.
- S6 mandate legitimacy exists as a fail-closed prerequisite, but S7 must decide what the system is allowed to ask a human to do with that mandate.
- A UI or workflow could create P26 responsibility theater by asking a human to approve without active choice, evidence, disconfirming evidence, or role authority.
- A B-side loop could self-route governance decisions as if the request itself were approval.

Correct pattern:

- Runtime-quality owns delegation integrity. B receives an injected S7 posture and cannot self-clear human decision authority.
- Human decisions are records, not vibes: decision class, role, rights, evidence summary, active choice, disconfirming evidence, mandate boundary, responsibility statement, and rule version all travel together.
- Low-VOI actions are not spammy interruptions, but they are still bounded and replayable.
- High-stakes/value-laden/out-of-envelope decisions become pull-first human requests, not AI-first suggestions.
- Wrong-role approval and oversight theater are negative controls, not warnings.
- `GovernanceDecisionClass` remains the shared S0 contract; S7 populates and consumes it through `DecisionRightsMatrix`, not by inventing a parallel governance enum.
- S7 closes only the delegation/orchestration layer. It does not close S8 values, S13 accountability, or production authority.

Missing capability labels before implementation:

- `artifact_missing` for `DelegationContract`, `DecisionRightsMatrix`, `HumanDecisionRequest`, and `HumanDecisionRecord`.
- `bridge_missing` for `CROSS_CUTTING.scientist_orchestration`.
- `consumer_missing` for S2 pause/request/record behavior.
- `surface_missing` for decision-shaped PUBLIC/REVIEWER/EXPERT/MACHINE projections.
- `semantic_test_missing` for high-stakes/value-laden/out-of-envelope routing and low-VOI non-interruption.
- `verification_missing` for P26 oversight-theater and wrong-role negative controls.

Acceptance signal:

- S7 artifacts are strict, replayable, exported from `runtime.quality`, registered in traceability/manifest/inventory, and consumed by S2.
- S2 can pause into `HumanDecisionRequest`, record a valid `HumanDecisionRecord`, or block invalid records without self-approval.
- All 13 W12 cases have S7 blocks and metrics.
- `delegation_precision=1.0`, `delegation_recall=1.0`, `responsibility_integrity_pass_rate=1.0`, `oversight_theater_false_clear_count=0`, and `wrong_role_false_clear_count=0`.
- Cluster-map open cell count is `4`; remaining open cells are exactly `ACTOR.value_choice_provenance`, `KNOWLEDGE.calibration`, `KNOWLEDGE.ir_proof_carrying_analytics`, and `DESIGNER_ITSELF.envelope_growth`.

## Code-Grounded Reality Check

Existing strengths to reuse:

- `GovernanceDecisionClass`, `ValueOfInformationEstimate`, `AuthorityBoundary`, `AxisPositionDeclaration`, `AxisFirewallStatus`, `CertifiedOperationEnvelope`, and `DesignRecordV0` already exist in `polisyos.pdc`.
- `RefinementDecision` already routes `human_decision` and requires `governance_decision_class_ref`.
- `ConstraintStoreSnapshot.constraint_records` and `ClusterHandoffRecord` already exist after S6 and are the correct bridge surface for S7.
- S6 `MandateLegitimacyRecord` and `Layer2S6BlindSpotPostureInput` provide the mandate prerequisite. S7 should consume mandate refs and posture, not re-evaluate P22.
- `scientist.agent.supervisor_eval` already contains delegation success / quorum / citation / budget evidence. S7 can reference these as seeds for no-interrupt or governed-pilot evidence, but not as a human decision record.
- `scientist.agent.supervisor` and `scientist.agent.protocols.DelegationResult` provide worker-delegation runtime seeds. S7 wraps them into PDC handoff records; it does not expose workflow summaries as authority.
- `core.security.delegation` signs service/user propagation tokens. S7 can cite `delegation_jti` as provenance, but the token is not a mandate or approval.
- `participation_requirement`, `runtime.quality.consultation`, and S6 mandate checks already protect P20/P22 boundaries.

Weak spots that make S7 more than a small DTO patch:

- S7 has no single new cell in `layer2_slice_cell_matrix.toml`, but it is the closure owner for the split `CROSS_CUTTING.scientist_orchestration` cell. The plan must validate closure through the S7 manifest and cluster map, not by pretending S2 closed it.
- `run_universal_outcome_corpus.py` is already carrying S4/S5/S6 route logic. S7 should mirror that pattern with small helpers and not refactor the route.
- PUBLIC projection must be decision-shaped and pull-first. It should not dump matrix rows, machine disposition labels, or role internals.
- Governed-pilot posture is not production. Tests must assert production outcomes and closeout honesty are unchanged.
- S7 must keep S8 value-choice authority pending when human decisions touch objectives/social weights.

## Source Of Truth

| Concern | Source |
| --- | --- |
| Roadmap closure contract | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md#s7--operating-model--delegation-layer-mandate-backed` |
| P26 failure pattern | `docs/reference/policy-design-case-failure-patterns.md` |
| Slice-cell assignments | `architecture/policy_design_case/layer2_slice_cell_matrix.toml` |
| Cluster closure contract | `architecture/policy_design_case/cluster_ownership_map.toml` (`CROSS_CUTTING.scientist_orchestration`) |
| Floor governance | `architecture/policy_design_case/layer2_floor_governance.toml#s7_delegation_integrity` |
| Artifact traceability | `architecture/policy_design_case/layer2_artifact_traceability.toml` (`DelegationContract`, `DecisionRightsMatrix`, `HumanDecisionRequest`, `HumanDecisionRecord`) |
| Shared S0 contracts | `src/polisyos/pdc/_impl/layer2_readiness.py`, `src/polisyos/pdc/__init__.py` |
| S2 loop/projection narrow waist | `src/polisyos/pdc/_impl/layer2_design_search.py` |
| S6 mandate prerequisite | `src/polisyos/runtime/quality/layer2_blind_spot_firewalls.py` |
| Scientist delegation seeds | `src/polisyos/scientist/agent/protocols.py`, `src/polisyos/scientist/agent/supervisor.py`, `src/polisyos/scientist/agent/supervisor_eval.py` |
| Security delegation-token seed | `src/polisyos/core/security/delegation.py` |
| Canonical corpus route | `tools/quality/validation/run_universal_outcome_corpus.py` |

## Files

Create:

- `src/polisyos/runtime/quality/layer2_delegation.py`
- `architecture/policy_design_case/layer2_s7_delegation_manifest.json`
- `tests/unit/runtime/quality/test_layer2_s7_delegation.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py`
- `tests/fixtures/layer2/s7/s7_delegation_case_signals.json`
- `tests/fixtures/layer2/s7/s7_delegation_expert_labels.json`
- `tests/fixtures/layer2/s7/oversight_theater_probe.json`
- `tests/fixtures/layer2/s7/wrong_role_approval_probe.json`
- `tests/fixtures/layer2/s7/ai_first_high_stakes_probe.json`
- `tests/fixtures/layer2/s7/mandate_absent_delegation_probe.json`

Modify:

- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/pdc/__init__.py`
- `src/polisyos/pdc/_impl/layer2_design_search.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `architecture/policy_design_case/cluster_ownership_map.toml`
- `architecture/policy_design_case/inventory.json`
- `tests/unit/pdc/test_layer2_s2_design_search.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`

---

## Task 1: Red-First S7 Semantic And Negative Tests

**Files:**

- Create: `tests/unit/runtime/quality/test_layer2_s7_delegation.py`
- Modify: `tests/unit/pdc/test_layer2_s2_design_search.py`
- Modify: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- Create fixtures under `tests/fixtures/layer2/s7/`

- [ ] **Step 1: Add runtime unit red tests**

Create `tests/unit/runtime/quality/test_layer2_s7_delegation.py` with these tests:

- `test_s7_artifacts_are_strict_replayable_and_exported`
- `test_decision_rights_matrix_maps_classes_to_roles_modes_and_five_rights`
- `test_high_stakes_value_laden_or_out_of_envelope_defaults_to_request_driven`
- `test_low_voi_in_envelope_action_records_no_interrupt`
- `test_oversight_theater_probe_invalidates_human_decision_record`
- `test_wrong_role_approval_probe_invalidates_human_decision_record`
- `test_ai_first_high_stakes_probe_blocks`
- `test_mandate_absent_delegation_probe_blocks_delegated_autonomous`
- `test_s7_delegation_integrity_metric_requires_precision_recall_and_responsibility`

Minimum red test content:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.runtime.quality import (
    DelegationContract,
    DecisionRightsMatrix,
    HumanDecisionRecord,
    HumanDecisionRequest,
    P26ResponsibilityIntegrityError,
    build_decision_rights_matrix,
    build_human_decision_request,
    record_human_decision,
    s7_delegation_integrity,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures/layer2/s7"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_s7_artifacts_are_strict_replayable_and_exported() -> None:
    for model in (
        DelegationContract,
        DecisionRightsMatrix,
        HumanDecisionRequest,
        HumanDecisionRecord,
    ):
        assert model.model_config.get("extra") == "forbid"


def test_decision_rights_matrix_maps_classes_to_roles_modes_and_five_rights() -> None:
    matrix = build_decision_rights_matrix(
        case_id="ua-msme-affordable-loans-2022",
        rule_version_ref="policyos.layer2.s7.delegation.v1",
    )

    row = matrix.row_for_decision_class("a_spec_gap")
    assert row.required_role == "policy_design_governance_reviewer"
    assert set(row.available_rights) == {
        "request_evidence",
        "approve",
        "reject",
        "revise_scope",
        "escalate",
    }
    assert row.default_interaction_mode == "request_driven"
    assert row.ai_first_allowed is False


def test_oversight_theater_probe_invalidates_human_decision_record() -> None:
    probe = _fixture("oversight_theater_probe.json")

    with pytest.raises(P26ResponsibilityIntegrityError, match="oversight_theater"):
        record_human_decision(**probe)
```

Expected initial result: import errors or assertion failures because `layer2_delegation.py` and S7 exports do not exist.

- [ ] **Step 2: Add S2 consumer red tests**

Extend `tests/unit/pdc/test_layer2_s2_design_search.py` with:

- `test_s2_consumes_s7_delegation_posture_and_pauses_for_human_request`
- `test_s2_records_valid_s7_human_decision_without_production_authority`
- `test_s2_s7_wrong_role_record_blocks_self_approval`
- `test_s2_s7_public_projection_is_decision_shaped_pull_first`
- `test_s2_s7_reviewer_projection_shows_p26_and_role_status`
- `test_s2_s7_expert_machine_projection_contains_refs_matrix_and_integrity`
- `test_s2_s7_governed_pilot_requires_s6_mandate_and_s7_valid_record`
- `test_s2_does_not_import_s7_runtime_quality_producer`

Minimum red assertion pattern:

```python
def test_s2_consumes_s7_delegation_posture_and_pauses_for_human_request() -> None:
    input_row = _input()
    posture = _delegation_posture(disposition="request_human_decision")

    run = run_s2_shadow_design_loop(input_row, delegation_posture=posture)

    assert run.delegation_posture == posture
    assert run.status == "governance_required"
    assert any(
        record.cell_ref == "CROSS_CUTTING.scientist_orchestration"
        and record.refinement_route == "human_decision"
        for record in run.constraint_store.constraint_records
    )
    assert posture.human_decision_request_ref in run.design_record.ledger_refs
```

Expected initial result: `run_s2_shadow_design_loop()` does not accept `delegation_posture`.

- [ ] **Step 3: Add W12.D red tests**

Extend `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py` with:

- `test_w12d_emits_s7_delegation_for_13_cases`
- `test_w12d_s7_records_precision_recall_and_responsibility_integrity`
- `test_w12d_s7_gold_labels_cover_all_13_cases_and_decision_need_reasons`
- `test_w12d_s7_pinned_case_injects_delegation_posture_into_s2`
- `test_w12d_s7_production_posture_and_closeout_honesty_unchanged`
- `test_w12d_s7_negative_controls_fail_closed`

Expected S7 summary assertions:

```python
summary = report["s7_delegation_summary"]
assert summary["case_count"] == 13
assert summary["delegation_precision"] == 1.0
assert summary["delegation_recall"] == 1.0
assert summary["responsibility_integrity_pass_rate"] == 1.0
assert summary["oversight_theater_false_clear_count"] == 0
assert summary["wrong_role_false_clear_count"] == 0
assert len(summary["per_case_delegation_table"]) == 13
```

- [ ] **Step 4: Run Task 1 red checks**

Run:

```bash
uv run pytest tests/unit/runtime/quality/test_layer2_s7_delegation.py -q
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
```

Expected:

```text
S7-specific tests fail because contracts, exports, corpus fixtures, and S2 delegation_posture wiring are missing.
Existing non-S7 tests should still be interpretable; do not change production code in Task 1.
```

- [ ] **Step 5: Commit Task 1**

```bash
git add tests/unit/runtime/quality/test_layer2_s7_delegation.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/fixtures/layer2/s7
git commit -m "test: add layer2 s7 delegation red tests" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 2: Contracts, Producers, Decision Rights, And P26 Firewalls

**Files:**

- Create: `src/polisyos/runtime/quality/layer2_delegation.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`
- Test: `tests/unit/runtime/quality/test_layer2_s7_delegation.py`

- [ ] **Step 1: Implement strict S7 contracts**

Create `src/polisyos/runtime/quality/layer2_delegation.py` with strict `Layer2ReadinessModel` subclasses:

- `DecisionRightsMatrixRow`
- `DecisionRightsMatrix`
- `DelegationContract`
- `ResponsibilityIntegrityCheck`
- `HumanDecisionRequest`
- `HumanDecisionRecord`
- `DelegationIntegrityReport`
- `DelegationNegativeControlResult`

Required fields:

- all records carry `schema_version="policyos.policy_design_case.layer2_s7_delegation.v1"`;
- all top-level records carry `record_ref` or `*_ref`;
- every top-level artifact carries `authority_boundary`;
- `HumanDecisionRequest.available_rights` must contain exactly the five rights;
- `HumanDecisionRecord` must carry `actor_role`, `decision_right_exercised`, `evidence_summary_ref`, `disconfirming_evidence_refs`, `active_choice`, `accountability_statement`, `mandate_record_ref`, and `responsibility_integrity`.

- [ ] **Step 2: Implement producer functions**

Add:

- `build_decision_rights_matrix(case_id, rule_version_ref) -> DecisionRightsMatrix`
- `build_delegation_contract(case_id, matrix, s6_mandate_record_ref, rule_version_ref) -> DelegationContract`
- `build_human_decision_request(case_id, contract, decision_class_id, need_reasons, voi_rank, rule_version_ref) -> HumanDecisionRequest`
- `record_human_decision(case_id, request, actor_role, decision_right_exercised, evidence_summary_ref, disconfirming_evidence_refs, active_choice, accountability_statement, mandate_record_ref, rule_version_ref) -> HumanDecisionRecord`
- `evaluate_delegation_for_case(case_id, s6_mandate_posture, case_signals, expert_label, rule_version_ref) -> DelegationIntegrityReport`
- `s7_delegation_integrity(probe_results) -> dict[str, object]`

Core rules:

- if `need_reasons` intersects `{"high_stakes", "value_laden", "out_of_envelope", "mandate_limited"}`, default mode is `request_driven`;
- if `need_reasons == {"low_voi_no_interrupt"}`, disposition is `no_interrupt`;
- if actor role does not match matrix row, raise `P26ResponsibilityIntegrityError("wrong_role_approval")`;
- if active choice, evidence summary, disconfirming evidence, or accountability statement is missing for a required decision, raise `P26ResponsibilityIntegrityError("oversight_theater")`;
- if delegated autonomy is requested without grounded S6 mandate, raise `P26ResponsibilityIntegrityError("delegated_autonomy_without_mandate")`.

- [ ] **Step 3: Export S7 public surface**

Modify `src/polisyos/runtime/quality/__init__.py` to export:

- `LAYER2_S7_DELEGATION_SCHEMA_VERSION`
- all S7 labels and record classes
- `P26ResponsibilityIntegrityError`
- all producer/metric functions

- [ ] **Step 4: Run Task 2 green checks**

Run:

```bash
uv run pytest tests/unit/runtime/quality/test_layer2_s7_delegation.py -q
uv run ruff check src/polisyos/runtime/quality/layer2_delegation.py src/polisyos/runtime/quality/__init__.py tests/unit/runtime/quality/test_layer2_s7_delegation.py
```

Expected:

```text
S7 runtime unit tests pass.
All exported S7 artifacts use extra=forbid.
P26 oversight-theater and wrong-role probes raise typed errors.
Ruff passes.
```

- [ ] **Step 5: Commit Task 2**

```bash
git add src/polisyos/runtime/quality/layer2_delegation.py \
  src/polisyos/runtime/quality/__init__.py \
  tests/unit/runtime/quality/test_layer2_s7_delegation.py
git commit -m "feat: add layer2 s7 delegation contracts and P26 checks" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 3: Inject S7 Delegation Posture Into The S2 Shadow Loop

**Files:**

- Modify: `src/polisyos/pdc/_impl/layer2_design_search.py`
- Modify: `src/polisyos/pdc/__init__.py`
- Test: `tests/unit/pdc/test_layer2_s2_design_search.py`

- [ ] **Step 1: Add PDC-local S7 posture DTO**

In `src/polisyos/pdc/_impl/layer2_design_search.py`, add `Layer2S7DelegationPostureInput` near the S5/S6 posture DTOs.

Required fields:

- `delegation_contract_ref`
- `decision_rights_matrix_ref`
- `human_decision_request_ref`
- `human_decision_record_ref | None`
- `decision_class_id`
- `required_role`
- `interaction_mode`
- `disposition`
- `available_rights`
- `decision_right_exercised | None`
- `responsibility_integrity_status`
- `mandate_record_ref`
- `voi_rank`
- `need_reasons`
- `authority_boundary`
- `governed_pilot_eligible`
- `constraint_store_updates`
- `handoff_rows`
- `limitation_summary`

Do not import `runtime.quality.layer2_delegation` in this file.

- [ ] **Step 2: Extend `run_s2_shadow_design_loop`**

Add `delegation_posture: Layer2S7DelegationPostureInput | None = None`.

When present:

- include S7 constraint-store updates;
- add S7 ledger refs to `DesignRecordV0.ledger_refs`;
- add one `ClusterHandoffRecord` from `CROSS_CUTTING.scientist_orchestration` to `INTERVENTION.design_candidate`;
- if disposition is `request_human_decision`, status is `governance_required`;
- if disposition starts with `blocked_`, status is `blocked` or `governance_required` according to the existing S2 status vocabulary;
- if `governed_pilot_eligible` is true, add a non-production `governed_pilot_eligible` field to the S2 summary/projection, not to production authority.

- [ ] **Step 3: Add projection fields**

Extend `project_s2_design_search` with `_s7_projection_fields(audience, delegation_posture, constraint_store)`:

- PUBLIC keys:
  - `human_decision_needed`
  - `accountable_role`
  - `available_decision_rights`
  - `delegation_limitation`
  - no machine-only `DelegationDisposition` label;
- REVIEWER keys:
  - `s7_decision_class_id`
  - `s7_required_role`
  - `s7_interaction_mode`
  - `s7_p26_firewall_status`
  - `s7_decision_right_exercised`;
- EXPERT/MACHINE keys:
  - all S7 refs;
  - `decision_rights_matrix_row`;
  - `responsibility_integrity_check`;
  - `need_reasons`;
  - `constraint_store_updates`;
  - `handoff_rows`;
  - `authority_boundary`;
  - `governed_pilot_eligible`.

Add assertion helper:

- `assert_s2_public_projection_has_delegation_request(projection)`

- [ ] **Step 4: Export posture DTO**

Modify `src/polisyos/pdc/__init__.py` to export `Layer2S7DelegationPostureInput` and `assert_s2_public_projection_has_delegation_request`.

- [ ] **Step 5: Run Task 3 checks**

Run:

```bash
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
rg -n "layer2_delegation|build_decision_rights_matrix|record_human_decision|evaluate_delegation_for_case" src/polisyos/pdc/_impl/layer2_design_search.py
```

Expected:

```text
PDC S2 tests pass.
The rg command returns no matches; B consumes only injected S7 posture.
PUBLIC projection is decision-shaped and does not expose machine-only disposition labels.
```

- [ ] **Step 6: Commit Task 3**

```bash
git add src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/pdc/__init__.py \
  tests/unit/pdc/test_layer2_s2_design_search.py
git commit -m "feat: inject layer2 s7 delegation posture into shadow design loop" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 4: Canonical Corpus Route Wiring - 13-Case S7 Delegation Coverage

**Files:**

- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`
- Modify: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- Create: `tests/fixtures/layer2/s7/s7_delegation_case_signals.json`
- Create: `tests/fixtures/layer2/s7/s7_delegation_expert_labels.json`
- Create negative probe JSON files under `tests/fixtures/layer2/s7/`

- [ ] **Step 1: Add S7 fixtures**

Create `s7_delegation_case_signals.json` with 13 cases. Each case entry includes:

- `case_id`
- `decision_class_id`
- `requested_interaction_mode`
- `stakes_band`
- `value_laden`
- `out_of_envelope`
- `mandate_status`
- `voi_rank`
- `actor_role`
- `evidence_summary_ref`
- `disconfirming_evidence_refs`
- `active_choice`
- `accountability_statement`
- `decision_right_exercised`

Create `s7_delegation_expert_labels.json` with 13 matching cases. Each label entry includes:

- `expected_need_reasons`
- `expected_interaction_mode`
- `expected_disposition`
- `expected_required_role`
- `expected_request_emitted`
- `expected_record_valid`
- `expected_governed_pilot_eligible`

Ensure coverage includes:

- at least 4 request-driven high-stakes/value-laden/out-of-envelope cases;
- at least 3 low-VOI no-interrupt cases;
- at least 2 blocked mandate-limited or absent-mandate cases;
- at least 1 governed-pilot eligible case;
- at least 1 wrong-role record in negative controls, not in positive corpus labels.

- [ ] **Step 2: Add S7 corpus route helpers**

In `run_universal_outcome_corpus.py`, add:

- `S7_CASE_SIGNALS_PATH`
- `S7_EXPERT_LABELS_PATH`
- `S7_NEGATIVE_CONTROL_PROBES`
- `_s7_delegation_summary(case, repo_root, s6_blind_spot_firewalls)`
- `_s7_delegation_corpus_summary(cases, repo_root)`
- `_s7_delegation_posture_input(s7_delegation)`
- `_s7_negative_control_probe_results(repo_root)`

Route order for each case:

```text
S1/S2 base -> S4 -> S5 -> S6 -> S7 -> S2 pinned injection
```

The S7 block must be added to each case as `s7_delegation`.

- [ ] **Step 3: Inject S7 posture into pinned S2 run**

For the pinned `ua-msme-affordable-loans-2022` S2 summary, call:

```python
run_s2_shadow_design_loop(
    input_row,
    regime_claim_ref=s4_epistemic_regime["regime_claim_ref"],
    design_strategy=s4_epistemic_regime["recommended_strategy"],
    commitment_profile_ref=s4_epistemic_regime["commitment_profile_ref"],
    commitment_stakes=s4_epistemic_regime["derived_commitment"]["stakes"],
    composition_posture=composition_posture,
    blind_spot_posture=blind_spot_posture,
    delegation_posture=delegation_posture,
)
```

Expected S2 summary additions:

- `s2_design_search["delegation_posture"]` present or represented through run dump;
- `constraint_store.constraint_records` includes `CROSS_CUTTING.scientist_orchestration`;
- `design_record.ledger_refs` includes S7 refs;
- `canonical_outcome_effect == "none_shadow_or_governed_pilot_only"`.

- [ ] **Step 4: Add corpus summary metrics**

The top-level W12.D report must include `s7_delegation_summary` with:

- `schema_version`
- `case_count`
- `delegation_precision`
- `delegation_recall`
- `responsibility_integrity_pass_rate`
- `oversight_theater_false_clear_count`
- `wrong_role_false_clear_count`
- `ai_first_high_stakes_false_clear_count`
- `mandate_absent_delegation_false_clear_count`
- `request_emitted_count`
- `no_interrupt_count`
- `valid_human_decision_record_count`
- `governed_pilot_eligible_count`
- `per_case_delegation_table`
- `decision_need_reason_counts`
- `interaction_mode_counts`
- `disposition_counts`

- [ ] **Step 5: Run Task 4 checks**

Run:

```bash
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
```

Expected:

```text
W12.D tests pass.
All 13 cases contain s7_delegation.
delegation_precision=1.0.
delegation_recall=1.0.
responsibility_integrity_pass_rate=1.0.
All S7 false-clear counts are 0.
S7 does not change production-posture outcomes or closeout honesty.
```

- [ ] **Step 6: Commit Task 4**

```bash
git add tools/quality/validation/run_universal_outcome_corpus.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/fixtures/layer2/s7
git commit -m "feat: classify layer2 s7 delegation coverage" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 5: S7 Manifest, Readiness Validator, Cluster Closure, And Inventory

**Files:**

- Create: `architecture/policy_design_case/layer2_s7_delegation_manifest.json`
- Modify: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- Modify: `architecture/policy_design_case/cluster_ownership_map.toml`
- Modify: `architecture/policy_design_case/inventory.json`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`

- [ ] **Step 1: Add S7 manifest**

Create `architecture/policy_design_case/layer2_s7_delegation_manifest.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s7_delegation_manifest.v1",
  "slice": "S7",
  "slice_label": "operating_model_delegation",
  "status": "active",
  "owner": "governance-board",
  "depends_on": ["S6"],
  "cells_closed": ["CROSS_CUTTING.scientist_orchestration"],
  "expected_current_open_cell_count": 4,
  "required_artifacts": [
    "DelegationContract",
    "DecisionRightsMatrix",
    "HumanDecisionRequest",
    "HumanDecisionRecord"
  ],
  "required_firewalls": ["P26", "P20", "P22", "P12", "P15"],
  "floor_id": "s7_delegation_integrity",
  "floor_metric": "delegation_precision_recall_and_responsibility_integrity",
  "delegation_precision": 1.0,
  "delegation_recall": 1.0,
  "responsibility_integrity_pass_rate": 1.0,
  "oversight_theater_false_clear_count": 0,
  "wrong_role_false_clear_count": 0,
  "case_count": 13,
  "authority_scope": [
    "delegation_integrity",
    "decision_rights_matrix",
    "human_decision_routing",
    "mandate_bounded_decision_record",
    "responsibility_integrity_check",
    "governance_attention_allocation",
    "governed_pilot_promotion_gate"
  ],
  "may_not_use_for": [
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "value_choice_authority",
    "social_weight_selection",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "oversight_effectiveness_claim",
    "human_approval_without_decision_record",
    "ai_self_authorization",
    "delegated_autonomy_without_mandate",
    "s13_accountability_closure"
  ],
  "producer_module": "src/polisyos/runtime/quality/layer2_delegation.py",
  "consumer_module": "src/polisyos/pdc/_impl/layer2_design_search.py",
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
}
```

- [ ] **Step 2: Extend readiness validator**

Add S7 constants and `_validate_s7_delegation(s7, floor_governance, artifact_traceability, cluster_map_payload, current_open_cells, assigned_cells, inventory, issues)` in `check_policy_design_case_layer2_readiness.py`.

Validator must check:

- manifest exists and schema is valid;
- `cells_closed == {"CROSS_CUTTING.scientist_orchestration"}`;
- `expected_current_open_cell_count == 4`;
- the S7 cell is no longer in `_open_cell_refs(cluster_map)`;
- current open count equals 4;
- required artifacts match traceability;
- floor id exists and floor revision rule is `decision_rights_matrix_change_requires_governance_owner`;
- required firewalls include `P26`, `P20`, `P22`, `P12`, and `P15`;
- `delegation_precision`, `delegation_recall`, and `responsibility_integrity_pass_rate` are at least `1.0`;
- false-clear counts are zero;
- inventory entry exists and matches manifest authority boundary.

Summary keys:

- `s7_case_count`
- `s7_delegation_precision`
- `s7_delegation_recall`
- `s7_responsibility_integrity_pass_rate`
- `s7_oversight_theater_false_clear_count`
- `s7_wrong_role_false_clear_count`
- `s7_expected_current_open_cell_count`

- [ ] **Step 3: Close cluster-map cell**

Update `[cell.CROSS_CUTTING.scientist_orchestration]`:

```toml
owner_module = "src/polisyos/runtime/quality/layer2_delegation.py"
seed_files = [
  "src/polisyos/runtime/quality/layer2_delegation.py",
  "src/polisyos/scientist/agent/supervisor.py",
  "src/polisyos/scientist/agent/supervisor_eval.py",
  "src/polisyos/scientist/agent/protocols.py",
]
ratchet_state = "implemented"
p01_chain = "implemented"
authority_dim = "cluster_orchestration_integrity"
firewall = "P26_responsibility_integrity_laundering"
publishes = ["INTERVENTION.design_candidate", "DESIGNER_ITSELF.cluster_evidence"]
consumes = [
  "SYSTEM.cluster_artifacts",
  "KNOWLEDGE.cluster_artifacts",
  "ACTOR.cluster_artifacts",
  "OTHER_AGENTS.cluster_artifacts",
  "ACTOR.mandate_legitimacy",
]
gap = "none_for_s7_delegation_scope"
action = "S7 emits DelegationContract, DecisionRightsMatrix, HumanDecisionRequest, HumanDecisionRecord, and typed handoff records; S13 oversight effectiveness remains future work."
```

Remove `[open_cell_closure.CROSS_CUTTING.scientist_orchestration]`.

- [ ] **Step 4: Register S7 manifest in inventory**

Add one artifact to `architecture/policy_design_case/inventory.json`:

- `id`: `layer2_s7_delegation_manifest`
- `path`: `architecture/policy_design_case/layer2_s7_delegation_manifest.json`
- `kind`: `layer2_s7_delegation_manifest`
- `schema_version`: `policyos.policy_design_case.layer2_s7_delegation_manifest.v1`
- `owner`: `governance-board`
- `status`: `active`
- `capability_reality_label`: `implemented`
- `authority_scope`: same as manifest
- `may_not_use_for`: same as manifest
- `validator`: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `canonical_route`: `tools/quality/validation/run_universal_outcome_corpus.py`

Expected inventory layer2 artifact count becomes `15`.

- [ ] **Step 5: Run Task 5 checks**

Run:

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
python3 -m json.tool architecture/policy_design_case/inventory.json >/dev/null
python3 -m json.tool architecture/policy_design_case/layer2_s7_delegation_manifest.json >/dev/null
```

Expected:

```text
Readiness validator status=pass.
current_open_cell_count=4.
inventory_artifact_count=15.
s7_delegation_precision=1.0.
s7_delegation_recall=1.0.
s7_responsibility_integrity_pass_rate=1.0.
Cluster validator status=pass.
open_or_incomplete_count=4.
```

- [ ] **Step 6: Commit Task 5**

```bash
git add architecture/policy_design_case/layer2_s7_delegation_manifest.json \
  architecture/policy_design_case/cluster_ownership_map.toml \
  architecture/policy_design_case/inventory.json \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py
git commit -m "chore: close layer2 s7 delegation orchestration cell" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 6: Repo-Quality Tests, Snapshots, And Burn-Down Confirmation

**Files:**

- Create: `tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py`
- Modify prior-slice live-count snapshot tests listed below.

- [ ] **Step 1: Add S7 repo-quality tests**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py` with:

- `test_layer2_s7_manifest_is_valid_and_open_count_is_4`
- `test_layer2_s7_closes_scientist_orchestration_with_delegation_scope`
- `test_layer2_s7_required_artifacts_are_traceable_and_exported`
- `test_layer2_s7_firewalls_are_registered_and_floor_is_governed`
- `test_layer2_s7_inventory_registration_exists`
- `test_layer2_s7_inventory_and_manifest_authority_boundaries_match`
- `test_layer2_s7_b_side_consumes_injected_posture_only`
- `test_layer2_s7_public_projection_is_decision_shaped_pull_first`
- `test_layer2_s7_negative_controls_fail_closed`
- `test_layer2_s7_manifest_metrics_match_generated_corpus_summary`
- `test_layer2_s7_corpus_summary_records_precision_recall_and_integrity`
- `test_layer2_s7_does_not_mark_s8_s10_s11_s12_s13_or_s14_cells_implemented`

- [ ] **Step 2: Update prior-slice live-count snapshots**

Closing `CROSS_CUTTING.scientist_orchestration` moves live open count `5 -> 4`.

Update only live readiness open-count assertions:

- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
  - live readiness open count `4`; keep S2 static manifest `expected_current_open_cell_count == 15`.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
  - live readiness open count `4`; keep S3 static manifest `expected_current_open_cell_count == 15`.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
  - live readiness open count `4`; keep S4 static manifest `expected_current_open_cell_count == 13`.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`
  - live readiness open count `4`; keep S5 static manifest `expected_current_open_cell_count == 10`.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`
  - live readiness open count `4`; keep S6 static manifest `expected_current_open_cell_count == 5`.

Run stale searches:

```bash
rg -n "summary\\[\\\"(open_cell_count|current_open_cell_count)\\\"\\] == 5|live_open_count_is_5|readiness_open_count_is_5" \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py
rg -n "\\[open_cell_closure\\.CROSS_CUTTING\\.scientist_orchestration\\]" \
  architecture/policy_design_case/cluster_ownership_map.toml
```

Expected: both commands return no matches.

- [ ] **Step 3: Run repo-quality burn-down**

Run:

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
python3 -m json.tool architecture/policy_design_case/inventory.json >/dev/null
python3 -m json.tool architecture/policy_design_case/layer2_s7_delegation_manifest.json >/dev/null
git diff --check
```

Expected:

```text
Repo-quality tests pass.
Readiness validator status=pass.
current_open_cell_count=4.
inventory_artifact_count=15.
S7 delegation metrics are all at floor.
Cluster validator status=pass.
open_or_incomplete_count=4.
JSON files parse.
git diff --check reports no whitespace errors.
```

- [ ] **Step 4: Commit Task 6**

```bash
git add tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py
git commit -m "chore: register layer2 s7 delegation progress" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 7: Full S7 Verification

- [ ] **Step 1: Run full S7 + regression gate**

Run:

```bash
uv run pytest tests/unit/runtime/quality/test_layer2_s7_delegation.py -q
uv run pytest tests/unit/pdc/test_layer2_readiness_contracts.py tests/unit/pdc/test_layer2_s2_design_search.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py -q
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q
uv run pytest tests/unit/runtime/quality/test_layer2_s6_blind_spot_firewalls.py tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py tests/unit/runtime/quality/test_layer2_graded_outcomes.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools architecture guardrails check
```

Expected:

```text
S7 unit + repo-quality tests pass.
S1/S2/S3/S4/S5/S6 regression tests pass.
W12.D route emits s4_epistemic_regime, s5_coupling_composition, s6_blind_spot_firewalls, and s7_delegation for all 13 cases.
S7 delegation precision, recall, and responsibility integrity are 1.0.
Theater/wrong-role/AI-first-high-stakes/mandate-absent false-clear counts are 0.
Layer 2 readiness validator: status pass; open_cell_count/current_open_cell_count 4.
Cluster ownership validator: status pass; open_or_incomplete/open-cell count 4.
Capability ratchet unchanged/green.
Runtime API contract pass.
Architecture guardrails pass.
```

Record under this task:

- `case_count`
- `delegation_precision`
- `delegation_recall`
- `responsibility_integrity_pass_rate`
- `oversight_theater_false_clear_count`
- `wrong_role_false_clear_count`
- `ai_first_high_stakes_false_clear_count`
- `mandate_absent_delegation_false_clear_count`
- `request_emitted_count`
- `no_interrupt_count`
- `valid_human_decision_record_count`
- `governed_pilot_eligible_count`
- `decision_need_reason_counts`
- `interaction_mode_counts`
- `disposition_counts`
- any Done-When caveat.

- [ ] **Step 2: Manual Done-When probes**

Run:

```bash
python3 - <<'PY'
import polisyos.runtime.quality as rq
names = [
    "DelegationContract",
    "DecisionRightsMatrix",
    "HumanDecisionRequest",
    "HumanDecisionRecord",
]
for name in names:
    obj = getattr(rq, name)
    print(name, getattr(obj, "model_config", {}).get("extra"))
PY
rg -n "layer2_delegation|build_decision_rights_matrix|record_human_decision|evaluate_delegation_for_case" src/polisyos/pdc/_impl/layer2_design_search.py
python3 - <<'PY'
from polisyos.pdc import Layer2S7DelegationPostureInput
print("delegation_contract_ref" in Layer2S7DelegationPostureInput.model_fields)
PY
python3 - <<'PY'
import tomllib
from pathlib import Path
payload = tomllib.loads(Path("architecture/policy_design_case/cluster_ownership_map.toml").read_text(encoding="utf-8"))
open_cells = sorted(
    f"{cluster}.{axis}"
    for cluster, axes in payload.get("open_cell_closure", {}).items()
    for axis in axes
)
print(open_cells)
PY
```

Expected:

```text
All four S7 artifacts are exported from runtime.quality and use extra=forbid.
The rg command returns no matches, proving B consumes only injected posture.
Layer2S7DelegationPostureInput is exported from polisyos.pdc.
Open cells are exactly:
['ACTOR.value_choice_provenance', 'DESIGNER_ITSELF.envelope_growth', 'KNOWLEDGE.calibration', 'KNOWLEDGE.ir_proof_carrying_analytics']
```

## Done When

1. `DelegationContract`, `DecisionRightsMatrix`, `HumanDecisionRequest`, and `HumanDecisionRecord` are strict, replayable, and exported from `runtime.quality`.
2. S7 consumes S6 mandate refs and cannot authorize delegated autonomy when mandate is absent, limited, or candidate-only.
3. B consumes injected `Layer2S7DelegationPostureInput` and cannot self-approve or import S7 producers.
4. `CROSS_CUTTING.scientist_orchestration` is implemented for S7 delegation/orchestration scope, with P01 chain implemented, and no wholesale Scientist authority claim.
5. High-stakes, value-laden, out-of-envelope, and mandate-limited decisions surface a request; low-VOI in-envelope actions do not interrupt.
6. P26 fails closed: oversight theater and wrong-role approval invalidate the `HumanDecisionRecord`.
7. P20/P22 remain bounded: S7 can route value/mandate decisions to humans but cannot choose social weights or invent mandate.
8. S7 emits `AxisPositionDeclaration`, `AxisFirewallStatus`, typed `ConstraintStoreSnapshot.constraint_records`, S7 `ClusterHandoffRecord` rows, and DesignRecord ledger refs.
9. S7 posture renders in all four audience projections:
   - PUBLIC: decision-shaped, pull-first accountability summary only.
   - REVIEWER: decision class, role, mode, right, P26/P20/P22/P12/P15 status.
   - EXPERT/MACHINE: all refs, matrix rows, request/record details, integrity checks, VOI rank, authority boundary, and governed-pilot eligibility.
10. All 13 corpus cases contain S7 blocks; precision/recall/integrity metrics are recorded; negative-control false-clear counts are zero.
11. Production-posture outcomes and closeout honesty are unchanged by S7; S7 affects governed-pilot routing only.
12. `s7_delegation_integrity` floor is recorded from the governed floor table; no denominator/floor is changed.
13. Cluster-map open cell count is `4`; both validators pass; S7 manifest is registered in inventory.
14. No S8 value-choice provenance, S10 forecast support, S11 calibration/predictive maturity, S12 envelope growth, S13 oversight effectiveness, production authority, calibrated prediction, rich simulation, portfolio optimization, or S14 universality battery cell is marked implemented.

## Commit Guidance

Mirror the S4/S5/S6 red-first sequence, one logical commit per task:

```text
test: add layer2 s7 delegation red tests
feat: add layer2 s7 delegation contracts and P26 checks
feat: inject layer2 s7 delegation posture into shadow design loop
feat: classify layer2 s7 delegation coverage
chore: close layer2 s7 delegation orchestration cell
chore: register layer2 s7 delegation progress
```

End commit messages with the repo's standard co-author trailer. Do not mark any S8+ value-choice, prediction, calibration, envelope-growth, accountability, production, or S14 universality cell as implemented.
