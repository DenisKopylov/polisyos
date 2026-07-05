from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar

import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlan,
    LoweredIR,
    LoweredIRRef,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    ProgramOp,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.ir.analytics.interventions import (
    InterventionContext,
    NodeIntervention,
    QueryTarget,
    VariableAssignment,
    identification_plan_for_intervention,
)
from polisyos.ir.analytics.ncm import ExogenousSpec, NCMSpec, StructuralEquation
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    ConstraintRegistry,
)
from polisyos.ir.linker import LinkedIntervention, link_trinity
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.registry.registry_fragments import RegistryBundle
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.quality.design_axes.coupling_composition import (
    CouplingEdge,
    build_coupling_graph,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
    build_intervention_atom_binding,
    intervention_atom_target_selector_ref,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationControllerPolicy,
    JointSimulationHorizonController,
    JointSimulationRequest,
    ProofReceiptError,
    build_content_bound_simulation_receipt,
    verify_simulation_receipt,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    DataForgeBindingRef,
    FabricWorldRef,
    FoundryBindingRef,
    PolicySlotBinding,
    ResolvedSubstrateEntryRef,
    SimulationModelRef,
    SkgCausalPriorRef,
    SubstrateRegistryRef,
    WorldModelRecord,
    world_model_record_content_hash,
)


def _ref(char: str) -> str:
    return "sha256:" + char * 64


def _coupling_graph(kind: str):
    if kind == "independent":
        edges = (
            CouplingEdge(
                boundary_ref="boundary://eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="independent",
                interaction_strength="none",
                feedback_intensity="none",
                evidence_ref="evidence://independent",
            ),
        )
    elif kind == "shared_resource":
        edges = (
            CouplingEdge(
                boundary_ref="boundary://eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="shared_resource:budget_capacity",
                interaction_strength="medium",
                feedback_intensity="none",
                evidence_ref="evidence://shared-resource",
            ),
        )
    elif kind == "feedback":
        edges = (
            CouplingEdge(
                boundary_ref="boundary://eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="claim_volume",
                interaction_strength="medium",
                feedback_intensity="medium",
                evidence_ref="evidence://feedback-forward",
            ),
            CouplingEdge(
                boundary_ref="boundary://delivery-eligibility",
                source_module_ref="module://delivery",
                target_module_ref="module://eligibility",
                relation="queue_delay_response",
                interaction_strength="medium",
                feedback_intensity="medium",
                evidence_ref="evidence://feedback-return",
            ),
        )
    elif kind == "general_equilibrium":
        edges = (
            CouplingEdge(
                boundary_ref="boundary://eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="system_wide_labor_market",
                interaction_strength="strong",
                feedback_intensity="none",
                evidence_ref="evidence://general-equilibrium",
            ),
        )
    else:
        raise AssertionError(f"unknown coupling graph fixture {kind}")
    return build_coupling_graph(
        design_ref=f"design://joint-simulation/{kind}",
        module_refs=("module://eligibility", "module://delivery"),
        module_discovery_ref="discovery://fixture",
        interaction_edges=edges,
        rule_version_ref="policyos.layer2.s5.coupling_composition.test",
    )


def _intervention(*, intervention_id: str, rate: str = "0.20") -> InterventionSpec:
    return InterventionSpec.model_validate(
        {
            "intervention_id": intervention_id,
            "kind": "tax_subsidy",
            "target": SelectorPredicate(
                field="id",
                operator=SelectorOperator.EQUALS,
                value="all",
            ),
            "schedule": ScheduleSpec(start_step=0, duration_steps=4),
            "params": {"rate": Decimal(rate)},
            "priority": 1,
            "target_population_type": "wartime_msme",
            "target_sector_ids": ["manufacturing"],
            "target_region_ids": ["UA-30"],
        }
    )


def _bundle(intervention: InterventionSpec) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_ua_msme_credit", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_ua_msme_credit",
            problem_frame_ref=_ref("a"),
            interventions=[intervention],
        ),
        model_spec=ModelSpec(model_id="model_ua_msme", data_snapshot_ref=_ref("b")),
    )


def _registries() -> RegistryBundle:
    return RegistryBundle(
        mechanisms=DEFAULT_MECHANISM_REGISTRY,
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )


def _linked(intervention: InterventionSpec) -> LinkedIntervention:
    linked_bundle, report = link_trinity(_bundle(intervention), _registries())
    assert report.ok, [issue.model_dump(mode="json") for issue in report.issues]
    return linked_bundle.bindings.interventions[0]


def _atom(
    *,
    intervention_id: str,
    causal_variable: str,
    engine_variable: str,
    value: float,
    world_model_record_ref: str,
) -> InterventionAtomBinding:
    intervention = _intervention(intervention_id=intervention_id)
    causal = NodeIntervention(
        assignments=(VariableAssignment(variable=causal_variable, value=value),)
    )
    return build_intervention_atom_binding(
        problem_frame_ref=_ref("a"),
        policy_spec_ref=_ref("c"),
        intervention=intervention,
        linked_intervention=_linked(intervention),
        causal_intervention=causal,
        query_target=QueryTarget(
            outcome_variables=("firm_survival",),
            conditioning=("baseline_credit_access",),
            functional="average_treatment_effect",
        ),
        identification_plan=identification_plan_for_intervention(causal),
        causal_context=InterventionContext(
            source_domain="observed_ua_msme_panel",
            target_domain="wartime_msme",
            selection_diagram_ref=intervention_atom_target_selector_ref(intervention),
            available_data_refs=("data_snapshot:ua_msme_credit_panel",),
            assumptions=("target_selector_content_bound",),
        ),
        world_model_record_ref=world_model_record_ref,
        producer_ref=f"test.joint_simulation:{intervention_id}",
        operator_proof_type_map={"tax_subsidy": "node"},
        mechanism_variable_map={"tax_subsidy": ("agents.income", "government.balance")},
        mechanism_config_overrides={
            "joint_simulation_engine_variable": engine_variable,
        },
    )


def _world_record(*, policy_domain: str = "fiscal_credit") -> WorldModelRecord:
    fields: dict[str, Any] = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "bound",
        "producer_ref": "test.world_model_record",
        "region_or_jurisdiction": "UA-30",
        "population_scope": "wartime_msme",
        "policy_domain": policy_domain,
        "valid_time_scope": "2026-05-24/2026-12-31",
        "tx_time_scope": "2026-05-24T12:00:00+00:00",
        "resolution": "firm_month",
        "branch_mode": BranchMode.OBSERVED,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root="/tmp/policyos-test-world",
            snapshot_id="snapshot-2026-05-24",
            branch="main",
            world_query_policy="as_of_valid_and_tx_time",
            provenance_manifest_ref="manifest://fabric/test",
            content_query_digest=_ref("1"),
            content_query_row_count=2,
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id="snapshot-2026-05-24",
            release_id="release-1",
            role="academic",
            read_api_identity="data_forge.read_api.test",
            snapshot_ref="snapshot://data-forge/test",
            merkle_root="merkle:test",
            data_hash=_ref("2"),
            provenance_manifest_ref="manifest://data-forge/test",
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=_ref("3"),
            model_spec_hash=_ref("4"),
            model_id="model_ua_msme_world",
            data_snapshot_ref=_ref("5"),
            registry_bundle_ref=_ref("6"),
            ncm_refs=("ncm://fixture/msme-interaction",),
            fidelity_level="high",
            calibrated=True,
            calibration_ref=_ref("7"),
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=_ref("8"),
            bound_state_snapshot_ref=_ref("9"),
            mapping_rules_ref=_ref("a"),
            state_slot_digest=_ref("b"),
        ),
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref="skg://test",
            skg_version_id="skg-v1",
            source_data_snapshot_id="snapshot-2026-05-24",
        ),
        "substrate_registry_ref": SubstrateRegistryRef(
            substrate_version_id="substrate_version_1111111111111111",
            content_hash=_ref("c"),
            resolved_entries=(
                ResolvedSubstrateEntryRef(
                    source_id="l5_measurement_registry",
                    family_id="firm_fundamentals",
                    layer="L5",
                    coverage_score=0.8,
                    trust_tier="authoritative_partial_coverage",
                    trust_cap=0.85,
                    identification_mode="point_identified",
                    schema_regime_id="ukraine_schema_v2",
                    data_version="l5-calibration-d2",
                    snapshot_id="snapshot-2026-05-24",
                    source_snapshot_id="snapshot-2026-05-24",
                    entry_content_hash=_ref("d"),
                ),
            ),
        ),
        "policy_slot_map": (
            PolicySlotBinding(
                slot_id="agents.income",
                state_path="agents.income",
                entity_scope="agent",
                temporal_granularity="month",
            ),
            PolicySlotBinding(
                slot_id="government.balance",
                state_path="government_balance",
                entity_scope="government",
                temporal_granularity="month",
            ),
        ),
    }
    candidate = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        content_hash=_ref("0"),
        **fields,
    )
    content_hash = world_model_record_content_hash(candidate)
    return WorldModelRecord(
        world_model_record_id=f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _ncm_with_cross_term() -> NCMSpec:
    return NCMSpec(
        endogenous_vars=["income_delta", "balance_delta", "firm_survival"],
        exogenous_specs=[
            ExogenousSpec(variable="u_income", associated_endogenous="income_delta"),
            ExogenousSpec(variable="u_balance", associated_endogenous="balance_delta"),
            ExogenousSpec(variable="u_survival", associated_endogenous="firm_survival"),
        ],
        structural_equations=[
            StructuralEquation(
                variable="income_delta",
                parents=[],
                exogenous="u_income",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable="balance_delta",
                parents=[],
                exogenous="u_balance",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable="firm_survival",
                parents=["income_delta", "balance_delta"],
                exogenous="u_survival",
                equation_type="nonlinear",
                equation_params={
                    "noise_expression": (
                        "1.0 + (2.0 * income_delta) + (3.0 * balance_delta) "
                        "+ (5.0 * income_delta * balance_delta) + u"
                    ),
                },
            ),
        ],
        is_acyclic=True,
        markov_condition_verified=True,
        independence_model="dag_markov",
        fit_method="symbolic",
    )


def _request(
    *,
    record: WorldModelRecord | None = None,
    ncm: NCMSpec | None = None,
    world_model_record_ref: str | None = None,
    policy_domain: str = "fiscal_credit",
) -> JointSimulationRequest:
    record = record or _world_record(policy_domain=policy_domain)
    ref = world_model_record_ref or record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=1.0,
            world_model_record_ref=ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable="balance_delta",
            value=1.0,
            world_model_record_ref=ref,
        ),
    )
    return JointSimulationRequest(
        world_model_record_ref=ref,
        world_model_record=record,
        intervention_atoms=atoms,
        selected_outcomes=("firm_survival",),
        baseline_state={"income_delta": 0.0, "balance_delta": 0.0, "firm_survival": 1.0},
        horizon=HorizonSpec(start=0, end=3, step=1),
        engine_plan=(
            EnginePlan(
                engine_kind="ncm_parallel_worlds",
                objective_ref="objective://firm-survival",
                ncm_spec=ncm or _ncm_with_cross_term(),
                variable_map={
                    "agents.income": "income_delta",
                    "government.balance": "balance_delta",
                    "firm_survival": "firm_survival",
                },
                eligibility_conditions=("acyclic", "counterfactual_do_worlds"),
            ),
        ),
        world_credal_state_before={"firm_survival": {"low": 0.2, "high": 0.8}},
    )


def _program_graph_plan(tmp_path: Path) -> EnginePlan:
    store = FileSystemCAS(tmp_path / "cas")
    ir_ref = store.put_json(
        {"fixture": "joint_simulation_program_graph"},
        PutOptions(
            kind="ir.lowered_fixture",
            media_type="application/json",
            schema=SchemaInfo(name="test.lowered_fixture", version="1.0"),
        ),
    )
    lowered_ref = store.put_json(
        LoweredIR(ir_ref=ir_ref),
        PutOptions(
            kind="foundry.lowered_ir",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.LoweredIR", version="0.2"),
        ),
    )
    params_ref = store.put_json(
        {
            "binding_id": "binding.program_graph_subsidy",
            "mechanism_id": "tax_subsidy",
            "intervention_ids": ["program_graph_income_subsidy"],
            "priority": 1,
            "params": {"rate": Decimal("0.0")},
            "schedule": ScheduleSpec(start_step=0, duration_steps=4).model_dump(mode="json"),
            "selector": SelectorPredicate(
                field="id",
                operator=SelectorOperator.EQUALS,
                value="all",
            ).model_dump(mode="json"),
            "selected_fidelity": "fluid",
            "notes": ["joint_simulation_program_graph_contract"],
        },
        PutOptions(
            kind="foundry.lowered_mechanism_payload",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.LoweredMechanismPayload", version="0.2.0"),
        ),
    )
    program_ref = store.put_json(
        ProgramGraph(
            ir_ref=ir_ref,
            lowered_ir_ref=LoweredIRRef(artifact_id=lowered_ref.artifact_id),
            nodes=[
                ProgramNode(
                    node_id="apply_subsidy",
                    node_kind="op",
                    mechanism_type="tax_subsidy",
                    params_ref=params_ref,
                    op=ProgramOp(op_kind="apply_mechanism"),
                    inputs=["agents.income"],
                    outputs=["agents.income", "government.balance"],
                )
            ],
            edges=[],
        ),
        PutOptions(
            kind="foundry.program_graph",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.2"),
        ),
    )
    exec_plan_ref = store.put_json(
        ExecPlan(
            program_ref=ProgramGraphRef(artifact_id=program_ref.artifact_id),
            order=["apply_subsidy"],
        ),
        PutOptions(
            kind="foundry.exec_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecPlan", version="0.2"),
        ),
    )
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    base_state = base_state.replace(
        agents=base_state.agents.replace(
            income=jnp.asarray([1000.0, 2000.0], dtype=jnp.float32)
        )
    )
    return EnginePlan(
        engine_kind="program_graph",
        objective_ref="objective://program-graph-smoke",
        eligibility_conditions=("acyclic", "state_transition"),
        variable_map={"mean_income": "agents.income"},
        program_store=store,
        program_graph_ref=program_ref,
        exec_plan_ref=exec_plan_ref,
        program_base_state=base_state,
        program_parameter_overrides_by_atom={
            "income_subsidy": {"apply_subsidy": {"rate": 0.10}},
            "balance_grant": {"apply_subsidy": {"rate": 0.20}},
        },
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        constraint_registry=ConstraintRegistry(constraints={}),
    )


def test_runs_individual_pairwise_joint_on_real_ncm_with_content_bound_receipt() -> None:
    result = JointSimulationHorizonController().run(_request())

    assert result.uncertainty_kind == "K_sim"
    assert result.world_credal_state_after == result.world_credal_state_before
    assert result.promotion_ready_value_packet["authority_blockers"] == [
        "simulation_only_k_sim_not_world_evidence"
    ]
    assert result.engine_decisions[0].engine_kind == "ncm_parallel_worlds"
    assert result.engine_decisions[0].decision == "selected"
    assert result.engine_decisions[0].method_fqn.endswith("ncm_engine@1.0.0")
    assert result.equilibrium_semantics["objective://firm-survival"] == "static_SCM"

    levels = {trajectory.run_level for trajectory in result.trajectories}
    assert levels == {"individual", "pairwise", "joint"}
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.step for point in joint.points] == [0]
    assert joint.diagnostics["temporal_capability"] == "static"
    assert joint.diagnostics["horizon_loop"] is False
    assert joint.points[-1].outcomes["firm_survival"] == pytest.approx(11.0)

    term = result.interaction_terms[0]
    assert term.atom_ids == ("income_subsidy", "balance_grant")
    assert term.outcome == "firm_survival"
    assert term.by_step == {0: pytest.approx(5.0)}
    assert term.formula == "joint_effect_minus_sum_individual_effects"
    assert result.feedback_classification.numeric_interaction == "non_additive"

    verify_simulation_receipt(result.receipt, result.content_bound_payload())


@pytest.mark.parametrize(
    ("graph_kind", "expected_blocker"),
    [
        ("shared_resource", "unsupported_coupling_class:shared_resource"),
        ("feedback", "unsupported_coupling_class:feedback"),
        (
            "general_equilibrium",
            "general_equilibrium_coupling_not_grounded_by_available_engine",
        ),
    ],
)
def test_unsupported_coupling_is_gated_not_summed(
    graph_kind: str,
    expected_blocker: str,
) -> None:
    request = _request().model_copy(update={"coupling_graph": _coupling_graph(graph_kind)})

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "coupling_composition_gate_unsupported"
    assert expected_blocker in result.engine_decisions[0].blockers
    assert not result.trajectories
    assert not result.interaction_terms
    assert result.receipt.calibration_status == "unsupported_coupling_gated"
    assert result.receipt.authoritative_for == ()
    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert result.feedback_classification.support_status == "unsupported"
    assert expected_blocker in result.feedback_classification.support_blockers


def test_supported_shared_resource_runs_on_coupled_engine_with_gate_receipt() -> None:
    request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "coupling_graph": _coupling_graph("shared_resource"),
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "engine_plan": (
                EnginePlan(
                    engine_kind="coupled_des_abm",
                    objective_ref="objective://claims-queue",
                    eligibility_conditions=(
                        "unemployment_claims",
                        "benefit_queue",
                        "service_queue",
                    ),
                    variable_map={
                        "agents.income": "benefit_amount",
                        "government.balance": "service_rate",
                    },
                    coupled_state={
                        "initial_income": [1000.0, 600.0, 400.0],
                        "initial_savings": [0.0, 0.0, 0.0],
                        "is_employed": [0.0, 0.0, 0.0],
                    },
                    coupled_params={
                        "benefit_amount": 0.0,
                        "service_rate": 0.5,
                        "initial_queue_length": 0.0,
                        "seed": 7,
                    },
                ),
            ),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].decision == "selected"
    assert result.feedback_classification.support_status == "supported"
    assert result.feedback_classification.engine_supported is True
    assert result.feedback_classification.shared_resource is True
    assert result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    verify_simulation_receipt(result.receipt, result.content_bound_payload())


def test_contract_testing_can_only_demonstrate_removed_coupling_gate_mutation() -> None:
    request = _request().model_copy(update={"coupling_graph": _coupling_graph("feedback")})

    result = JointSimulationHorizonController.for_contract_testing(
        disable_coupling_gate=True
    ).run(request)

    assert result.engine_decisions[0].decision == "selected"
    assert result.trajectories
    assert result.feedback_classification.support_status == "supported"
    assert "unsupported_coupling_class:feedback" in result.feedback_classification.support_blockers
    assert result.diagnostics["controller_authority_scope"] == "contract_testing"
    assert result.diagnostics["coupling_gate_disabled"] is True


def test_safe_public_policy_exposes_no_gate_bypass_knobs() -> None:
    with pytest.raises(ValueError):
        JointSimulationControllerPolicy.model_validate({"disable_coupling_gate": True})


def test_declared_unbacked_equilibrium_semantics_is_gated() -> None:
    plan = _request().engine_plan[0].model_copy(
        update={"declared_equilibrium_semantics": "game_model"}
    )
    result = JointSimulationHorizonController().run(
        _request().model_copy(update={"engine_plan": (plan,)})
    )

    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "equilibrium_semantics_not_backed_by_engine"
    assert "declared_semantics_unbacked:game_model" in result.engine_decisions[0].blockers
    assert result.equilibrium_semantics["objective://firm-survival"] == "unsupported"
    assert not result.trajectories


def test_receipt_verification_fails_when_run_is_claimed_without_trajectories() -> None:
    payload = {
        "trajectories": [],
        "metrics": {"engine": "ncm_parallel_worlds"},
        "diagnostics": {"engine_run_claimed": True},
    }

    with pytest.raises(ProofReceiptError, match="receipt_engine_run_missing"):
        build_content_bound_simulation_receipt(
            engine_kind="ncm_parallel_worlds",
            payload=payload,
            diagnostics=payload["diagnostics"],
        )


def test_program_graph_plan_loops_real_shared_state_executor(tmp_path: Path) -> None:
    request = _request().model_copy(
        update={
            "engine_plan": (_program_graph_plan(tmp_path),),
            "selected_outcomes": ("mean_income",),
            "baseline_state": {"mean_income": 0.0},
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].engine_kind == "program_graph"
    assert result.engine_decisions[0].decision == "selected"
    assert result.engine_decisions[0].method_fqn == "foundry.execute.program_graph"
    assert result.equilibrium_semantics["objective://program-graph-smoke"] == "dynamic_SCM"
    assert {trajectory.run_level for trajectory in result.trajectories} == {
        "individual",
        "pairwise",
        "joint",
    }
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.step for point in joint.points] == [0, 1, 2, 3]
    assert all("state_delta_ref" in point.engine_state for point in joint.points)
    assert [point.outcomes["mean_income"] for point in joint.points] == pytest.approx(
        [1800.0, 2160.0, 2592.0, 3110.4]
    )
    assert abs(result.interaction_terms[0].by_step[3]) > 1.0
    verify_simulation_receipt(result.receipt, result.content_bound_payload())


def test_system_dynamics_plan_runs_registered_stock_flow_engine() -> None:
    world_record = _world_record()
    atoms = (
        _atom(
            intervention_id="capacity_inflow",
            causal_variable="agents.income",
            engine_variable="exogenous_inflows.0",
            value=2.0,
            world_model_record_ref=world_record.world_model_record_id,
        ),
        _atom(
            intervention_id="demand_inflow",
            causal_variable="government.balance",
            engine_variable="exogenous_inflows.1",
            value=3.0,
            world_model_record_ref=world_record.world_model_record_id,
        ),
    )
    request = JointSimulationRequest(
        world_model_record_ref=world_record.world_model_record_id,
        world_model_record=world_record,
        intervention_atoms=atoms,
        selected_outcomes=("stock0", "stock1"),
        horizon=HorizonSpec(start=0, end=2, step=1),
        engine_plan=(
            EnginePlan(
                engine_kind="system_dynamics",
                objective_ref="objective://stock-flow",
                variable_map={
                    "agents.income": "exogenous_inflows.0",
                    "government.balance": "exogenous_inflows.1",
                    "stock0": "stock:0",
                    "stock1": "stock:1",
                },
                system_dynamics_state={
                    "initial_stocks": [10.0, 0.0],
                    "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
                    "exogenous_inflows": [0.0, 0.0],
                },
                system_dynamics_params={"dt": 1.0},
            ),
        ),
        baseline_state={"stock0": 10.0, "stock1": 0.0},
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].method_fqn == "simulation.system_dynamics.stock_flow@1.0.0"
    assert result.engine_decisions[0].equilibrium_semantics == "dynamic_SCM"
    assert result.engine_decisions[0].temporal_capability == "multi_period"
    assert {trajectory.run_level for trajectory in result.trajectories} == {
        "individual",
        "pairwise",
        "joint",
    }
    joint = result.trajectory_for("joint", ("capacity_inflow", "demand_inflow"))
    distinct_states = {
        tuple(point.engine_state["stock_values"])
        for point in joint.points
    }
    assert len(distinct_states) >= 2
    assert joint.points[-1].outcomes == pytest.approx({"stock0": 11.9, "stock1": 8.1})
    assert result.interaction_terms[0].by_step[2] == pytest.approx(1.9)


def test_method_registry_estimator_selects_registered_dynamic_method_without_engine_branch() -> None:
    world_record = _world_record()
    atoms = (
        _atom(
            intervention_id="capacity_inflow",
            causal_variable="agents.income",
            engine_variable="exogenous_inflows.0",
            value=2.0,
            world_model_record_ref=world_record.world_model_record_id,
        ),
        _atom(
            intervention_id="demand_inflow",
            causal_variable="government.balance",
            engine_variable="exogenous_inflows.1",
            value=3.0,
            world_model_record_ref=world_record.world_model_record_id,
        ),
    )
    request = JointSimulationRequest(
        world_model_record_ref=world_record.world_model_record_id,
        world_model_record=world_record,
        intervention_atoms=atoms,
        selected_outcomes=("stock0", "stock1"),
        horizon=HorizonSpec(start=0, end=2, step=1),
        engine_plan=(
            EnginePlan(
                engine_kind="method_registry_estimator",
                objective_ref="objective://generic-stock-flow",
                method_fqn="simulation.system_dynamics.stock_flow@1.0.0",
                variable_map={
                    "agents.income": "exogenous_inflows.0",
                    "government.balance": "exogenous_inflows.1",
                    "stock0": "stock:0",
                    "stock1": "stock:1",
                },
                system_dynamics_state={
                    "initial_stocks": [10.0, 0.0],
                    "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
                    "exogenous_inflows": [0.0, 0.0],
                },
                system_dynamics_params={"dt": 1.0},
            ),
        ),
        baseline_state={"stock0": 10.0, "stock1": 0.0},
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].engine_kind == "method_registry_estimator"
    assert result.engine_decisions[0].method_fqn == "simulation.system_dynamics.stock_flow@1.0.0"
    assert result.engine_decisions[0].temporal_capability == "multi_period"
    joint = result.trajectory_for("joint", ("capacity_inflow", "demand_inflow"))
    assert [point.outcomes["stock1"] for point in joint.points] == pytest.approx(
        [0.0, 4.0, 8.1]
    )


def test_registry_des_queue_tag_does_not_back_time_series_semantics() -> None:
    request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "engine_plan": (
                EnginePlan(
                    engine_kind="method_registry_estimator",
                    objective_ref="objective://queue-tag-counterexample",
                    method_fqn="simulation.discrete_event.queue@1.0.0",
                    declared_equilibrium_semantics="agent_based_model",
                    eligibility_conditions=("multi_period", "agent_based_model"),
                    variable_map={
                        "agents.income": "arrival_rate",
                        "government.balance": "service_rate",
                    },
                    coupled_state={"queue_length": 0.0},
                    system_dynamics_params={
                        "service_rate": 1.0,
                        "arrival_rate": 2.0,
                        "n_steps": 3,
                    },
                ),
            ),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "method_output_shape_does_not_back_semantics"
    assert "output_shape:scalar_final_value" in result.engine_decisions[0].blockers
    assert "declared_semantics_unbacked:agent_based_model" in result.engine_decisions[0].blockers
    assert not result.trajectories
    assert result.receipt.calibration_status == "no_run"


def test_fresh_scalar_method_contract_does_not_back_agent_based_semantics() -> None:
    class FreshScalarFinalValueMethod:
        signature: ClassVar[MethodSignature] = MethodSignature(
            name="fresh_scalar",
            namespace="simulation.test_scalar",
            version="1.0.0",
            input_slots=frozenset(
                {SlotSpec("scalar_input", SlotType.SCALAR, Unit("count", "value"))}
            ),
            output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))}),
            parameters=(),
            fidelity=FidelityLevel.HIGH,
            complexity=ComplexityClass.O_N,
            backend=ComputeBackend.NUMPY,
            supports_jit=False,
            supports_vmap=False,
            supports_grad=False,
        )
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description="Test-only scalar final-value method.",
            tags=frozenset({"simulation", "fresh-scalar"}),
            assumptions={
                "joint_simulation_output_shape": "scalar_final_value",
                "joint_simulation_equilibrium_semantics": "agent_based_model",
            },
        )

        @staticmethod
        def pure_step(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
            del params
            return {"result": {"final_value": float(state.get("scalar_input", 0.0))}}

    registry = MethodRegistry._create_fresh()
    fqn = registry.register(FreshScalarFinalValueMethod)
    request = _request().model_copy(
        update={
            "engine_plan": (
                EnginePlan(
                    engine_kind="method_registry_estimator",
                    objective_ref="objective://fresh-scalar-counterexample",
                    method_fqn=fqn,
                    declared_equilibrium_semantics="agent_based_model",
                    eligibility_conditions=("multi_period", "agent_based_model"),
                ),
            ),
        }
    )

    result = JointSimulationHorizonController(method_registry=registry).run(request)

    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "method_output_shape_does_not_back_semantics"
    assert result.engine_decisions[0].blockers == (
        "output_shape:scalar_final_value",
        "declared_semantics_unbacked:agent_based_model",
    )
    assert result.receipt.calibration_status == "no_run"
    assert not result.trajectories


def test_newly_registered_dynamic_method_is_selectable_without_controller_code() -> None:
    class FreshRegisteredDynamicMethod:
        signature: ClassVar[MethodSignature] = MethodSignature(
            name="fresh_dynamic_stock",
            namespace="simulation.test_dynamic",
            version="1.0.0",
            input_slots=frozenset(
                {
                    SlotSpec(
                        "initial_stocks",
                        SlotType.VECTOR,
                        Unit("stock", "level"),
                        shape=("n_stocks",),
                    ),
                    SlotSpec(
                        "flow_matrix",
                        SlotType.MATRIX,
                        Unit("flow", "rate"),
                        shape=("n_stocks", "n_stocks"),
                    ),
                }
            ),
            output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))}),
            parameters=(ParameterSpec(name="n_steps", default=3),),
            fidelity=FidelityLevel.HIGH,
            complexity=ComplexityClass.O_N,
            backend=ComputeBackend.NUMPY,
            supports_jit=False,
            supports_vmap=False,
            supports_grad=False,
        )
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description="Test-only dynamic method registered after controller construction.",
            tags=frozenset({"simulation", "system-dynamics", "fresh-test-method"}),
            assumptions={
                "joint_simulation_output_shape": "time_series_trajectory",
                "joint_simulation_equilibrium_semantics": "dynamic_SCM",
            },
        )

        @staticmethod
        def pure_step(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
            n_steps = int(params.get("n_steps", 3))
            initial = [float(item) for item in state["initial_stocks"]]
            inflows = [float(item) for item in state.get("exogenous_inflows", [0.0, 0.0])]
            trajectory = [
                [initial[0] + (step * inflows[0]), initial[1] + (step * inflows[1])]
                for step in range(n_steps + 1)
            ]
            return {
                "result": {
                    "trajectory": trajectory,
                    "final_stocks": trajectory[-1],
                    "mass_balance": sum(trajectory[-1]) - sum(trajectory[0]),
                }
            }

    registry = MethodRegistry._create_fresh()
    fqn = registry.register(FreshRegisteredDynamicMethod)
    world_record = _world_record()
    atoms = (
        _atom(
            intervention_id="capacity_inflow",
            causal_variable="agents.income",
            engine_variable="exogenous_inflows.0",
            value=2.0,
            world_model_record_ref=world_record.world_model_record_id,
        ),
        _atom(
            intervention_id="demand_inflow",
            causal_variable="government.balance",
            engine_variable="exogenous_inflows.1",
            value=3.0,
            world_model_record_ref=world_record.world_model_record_id,
        ),
    )
    request = JointSimulationRequest(
        world_model_record_ref=world_record.world_model_record_id,
        world_model_record=world_record,
        intervention_atoms=atoms,
        selected_outcomes=("stock0", "stock1"),
        horizon=HorizonSpec(start=0, end=2, step=1),
        engine_plan=(
            EnginePlan(
                engine_kind="method_registry_estimator",
                objective_ref="objective://fresh-registered-dynamic",
                method_fqn=fqn,
                variable_map={
                    "agents.income": "exogenous_inflows.0",
                    "government.balance": "exogenous_inflows.1",
                    "stock0": "stock:0",
                    "stock1": "stock:1",
                },
                eligibility_conditions=("multi_period",),
                system_dynamics_state={
                    "initial_stocks": [10.0, 0.0],
                    "flow_matrix": [[0.0, 0.0], [0.0, 0.0]],
                    "exogenous_inflows": [0.0, 0.0],
                },
            ),
        ),
        baseline_state={"stock0": 10.0, "stock1": 0.0},
    )

    result = JointSimulationHorizonController(method_registry=registry).run(request)

    assert result.engine_decisions[0].method_fqn == fqn
    assert result.engine_decisions[0].temporal_capability == "multi_period"
    joint = result.trajectory_for("joint", ("capacity_inflow", "demand_inflow"))
    assert [point.engine_state["stock_values"] for point in joint.points] == [
        [10.0, 0.0],
        [12.0, 3.0],
        [14.0, 6.0],
    ]


def test_matching_coupled_engine_runs_individual_pairwise_joint_with_real_interaction() -> None:
    request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "engine_plan": (
                EnginePlan(
                    engine_kind="coupled_des_abm",
                    objective_ref="objective://claims-queue",
                    eligibility_conditions=(
                        "unemployment_claims",
                        "benefit_queue",
                        "service_queue",
                    ),
                    variable_map={
                        "agents.income": "benefit_amount",
                        "government.balance": "service_rate",
                    },
                    coupled_state={
                        "initial_income": [1000.0, 600.0, 400.0],
                        "initial_savings": [0.0, 0.0, 0.0],
                        "is_employed": [0.0, 0.0, 0.0],
                    },
                    coupled_params={
                        "benefit_amount": 0.0,
                        "service_rate": 0.5,
                        "initial_queue_length": 0.0,
                        "seed": 7,
                    },
                ),
            ),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].engine_kind == "coupled_des_abm"
    assert result.engine_decisions[0].decision == "selected"
    assert result.engine_decisions[0].temporal_capability == "multi_period"
    assert {trajectory.run_level for trajectory in result.trajectories} == {
        "individual",
        "pairwise",
        "joint",
    }
    assert result.interaction_terms
    pairwise = result.trajectory_for("pairwise", ("income_subsidy", "balance_grant"))
    left = result.trajectory_for("individual", ("income_subsidy",))
    right = result.trajectory_for("individual", ("balance_grant",))
    derived_terminal = (
        pairwise.points[-1].effect["final_queue_length"]
        - left.points[-1].effect["final_queue_length"]
        - right.points[-1].effect["final_queue_length"]
    )
    assert result.interaction_terms[0].by_step[pairwise.points[-1].step] == pytest.approx(
        derived_terminal
    )


def test_receipt_verification_fails_for_fabricated_stub_refs() -> None:
    result = JointSimulationHorizonController().run(_request())
    fabricated = result.receipt.model_copy(
        update={
            "trajectory_hash": _ref("e"),
            "diagnostics_hash": _ref("f"),
            "diagnostics_attached": False,
        }
    )

    with pytest.raises(ProofReceiptError, match="receipt_content_mismatch"):
        verify_simulation_receipt(fabricated, result.content_bound_payload())


def test_non_matching_domain_is_not_routed_to_unemployment_coupled_kernel() -> None:
    request = _request(policy_domain="housing_zoning")
    request = request.model_copy(
        update={
            "engine_plan": (
                EnginePlan(
                    engine_kind="coupled_des_abm",
                    objective_ref="objective://housing",
                    eligibility_conditions=("feedback", "service_queue"),
                    coupled_state={"initial_income": [1000.0], "is_employed": [1.0]},
                    coupled_params={"n_steps": 3, "benefit_amount": 100.0},
                ),
            )
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "engine_eligibility_failed"
    assert result.equilibrium_semantics["objective://housing"] == "unsupported"
    assert not result.trajectories


def test_cyclic_ncm_is_rejected_not_silently_grounded() -> None:
    cyclic = _ncm_with_cross_term().model_copy(
        update={
            "is_acyclic": False,
            "structural_equations": [
                StructuralEquation(
                    variable="income_delta",
                    parents=["firm_survival"],
                    exogenous="u_income",
                    equation_type="linear",
                ),
                StructuralEquation(
                    variable="firm_survival",
                    parents=["income_delta"],
                    exogenous="u_survival",
                    equation_type="linear",
                ),
            ],
        }
    )

    result = JointSimulationHorizonController().run(_request(ncm=cyclic))

    assert result.engine_decisions[0].decision == "unsupported"
    assert "cyclic_ncm_rejected" in result.engine_decisions[0].blockers
    assert result.equilibrium_semantics["objective://firm-survival"] == "unsupported"
    assert not result.trajectories


def test_pending_world_model_record_ref_fails_closed() -> None:
    with pytest.raises(JointSimulationControllerError, match="world_model_record_ref_pending"):
        JointSimulationHorizonController().run(
            _request(world_model_record_ref="pending_world_model_record_ref")
        )


def test_receipt_builder_is_deterministic_and_strangles_abm_stub_fields() -> None:
    payload = {
        "trajectory": [{"step": 0, "outcomes": {"firm_survival": 1.0}}],
        "metrics": {"engine": "ncm_parallel_worlds"},
        "diagnostics": {"warnings": []},
    }

    first = build_content_bound_simulation_receipt(
        engine_kind="ncm_parallel_worlds",
        payload=payload,
        diagnostics={"warnings": []},
    )
    second = build_content_bound_simulation_receipt(
        engine_kind="ncm_parallel_worlds",
        payload=payload,
        diagnostics={"warnings": []},
    )

    assert first == second
    assert first.diagnostics_attached is True
    assert "phase4_abm_result_stub" not in first.model_dump_json()
    verify_simulation_receipt(first, payload)
