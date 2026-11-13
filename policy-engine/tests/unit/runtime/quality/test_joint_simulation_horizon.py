from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
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
    JointSimulationResult,
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
        evidence_state="observed",
        rule_version_ref="policyos.layer2.s5.coupling_composition.test",
    )


def _intervention(
    *,
    intervention_id: str,
    rate: str = "0.20",
    kind: str = "tax_subsidy",
) -> InterventionSpec:
    params = {"rate": Decimal(rate)} if kind in {"tax_subsidy", "income_tax"} else {}
    return InterventionSpec.model_validate(
        {
            "intervention_id": intervention_id,
            "kind": kind,
            "target": SelectorPredicate(
                field="id",
                operator=SelectorOperator.EQUALS,
                value="all",
            ),
            "schedule": ScheduleSpec(start_step=0, duration_steps=4),
            "params": params,
            "priority": 1,
            "target_population_type": "wartime_msme",
            "target_sector_ids": ["manufacturing"],
            "target_region_ids": ["UA-30"],
        }
    )


def _bundle(intervention: InterventionSpec) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_ua_msme_credit", domain=ProblemDomain.FISCAL
        ),
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
    mechanism_kind: str = "tax_subsidy",
    mechanism_variables: tuple[str, ...] | None = None,
) -> InterventionAtomBinding:
    intervention = _intervention(
        intervention_id=intervention_id,
        kind=mechanism_kind,
    )
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
        operator_proof_type_map={mechanism_kind: "node"},
        mechanism_variable_map={
            mechanism_kind: mechanism_variables or ("agents.income", "government.balance")
        },
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
            PolicySlotBinding(
                slot_id="firms.labor_count",
                state_path="firms.labor_count",
                entity_scope="firm",
                temporal_granularity="month",
            ),
            PolicySlotBinding(
                slot_id="agents.employer_id",
                state_path="agents.employer_id",
                entity_scope="agent",
                temporal_granularity="month",
            ),
            PolicySlotBinding(
                slot_id="agents.is_employed",
                state_path="agents.is_employed",
                entity_scope="agent",
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
        endogenous_vars=[
            "income_delta",
            "balance_delta",
            "labor_count_delta",
            "firm_survival",
        ],
        exogenous_specs=[
            ExogenousSpec(variable="u_income", associated_endogenous="income_delta"),
            ExogenousSpec(variable="u_balance", associated_endogenous="balance_delta"),
            ExogenousSpec(
                variable="u_labor_count",
                associated_endogenous="labor_count_delta",
            ),
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
                variable="labor_count_delta",
                parents=[],
                exogenous="u_labor_count",
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
        baseline_state={
            "income_delta": 0.0,
            "balance_delta": 0.0,
            "firm_survival": 1.0,
        },
        horizon=HorizonSpec(start=0, end=3, step=1),
        engine_plan=(
            EnginePlan(
                engine_kind="ncm_parallel_worlds",
                objective_ref="objective://firm-survival",
                ncm_spec=ncm or _ncm_with_cross_term(),
                variable_map={
                    "agents.income": "income_delta",
                    "government.balance": "balance_delta",
                    "firms.labor_count": "labor_count_delta",
                    "firm_survival": "firm_survival",
                },
                eligibility_conditions=("acyclic", "counterfactual_do_worlds"),
            ),
        ),
        world_credal_state_before={"firm_survival": {"low": 0.2, "high": 0.8}},
    )


def _program_graph_plan(
    tmp_path: Path,
    *,
    store: FileSystemCAS | None = None,
    rates_by_atom: tuple[float, float] = (0.10, 0.10),
) -> EnginePlan:
    import jax.numpy as jnp

    store = store or FileSystemCAS(tmp_path / "cas")
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
            schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.2.0"),
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
            schema=SchemaInfo(name="polisyos.core.ExecPlan", version="0.2.0"),
        ),
    )
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    base_state = base_state.replace(
        agents=base_state.agents.replace(income=jnp.asarray([1000.0, 2000.0], dtype=jnp.float32))
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
            "income_subsidy": {"apply_subsidy": {"rate": rates_by_atom[0]}},
            "balance_grant": {"apply_subsidy": {"rate": rates_by_atom[1]}},
        },
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        constraint_registry=ConstraintRegistry(constraints={}),
        outcome_aggregations={"mean_income": {"method": "mean", "unit": "usd"}},
    )


def test_runs_individual_pairwise_joint_on_real_ncm_with_content_bound_receipt() -> None:
    request = _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})
    result = JointSimulationHorizonController().run(request)

    assert request.horizon.steps() == (0,)
    assert result.uncertainty_kind == "K_sim"
    assert result.world_credal_state_after == result.world_credal_state_before
    authority_blockers = result.promotion_ready_value_packet["authority_blockers"]
    assert "simulation_only_k_sim_not_world_evidence" in authority_blockers
    assert "simulation_effect_basis_not_established" in authority_blockers
    assert result.diagnostics["effect_basis_status"] == "not_established"
    assert result.diagnostics["interaction_evidence_issues"] == []
    assert result.diagnostics["interaction_sampling_issues"] == []
    assert result.diagnostics["requested_replications"] == 1
    assert len(result.diagnostics["replication_seeds"]) == 1
    # Checked orders describe complete model-scope coverage; one draw remains noninferential.
    assert result.feedback_classification.checked_interaction_orders == tuple(
        range(1, len(request.intervention_atoms) + 1)
    )
    assert result.feedback_classification.interaction_sampling_status == (
        "standard_error_not_estimated"
    )
    assert "standard_error_not_estimated" in authority_blockers
    assert "interaction_sampling_not_established" in authority_blockers
    assert "interaction_sampling_not_established" in result.feedback_classification.limitations
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
    sampling = term.replication_sampling_by_step[0]
    assert sampling.replicate_count == 1
    assert sampling.status == "standard_error_not_estimated"
    assert sampling.effects_standard_error == {"derived_effect": None}
    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert result.feedback_classification.numeric_interaction_basis == "not_established"
    assert "interaction_numeric_classification_unsupported" in authority_blockers

    verify_simulation_receipt(result.receipt, result.content_bound_payload())


def test_operation_receipt_memo_requires_fresh_cas_and_exact_signed_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Memoize only a freshly selected CAS receipt, never its mutable result."""
    import sys

    from polisyos.core.artifacts.manifest import WarningRecord
    from polisyos.core.canon.canon_json import CanonSpec
    from polisyos.pdc._impl import gy_waist
    from polisyos.runtime.quality import joint_simulation_horizon as owner
    from polisyos.runtime.quality.generation_cycle import (
        JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
        JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA,
        GenerationCycleError,
        load_joint_simulation_result,
    )

    fixture_path = (
        Path(__file__).resolve().parents[4]
        / "architecture/policy_design_case/layer3_gy_composition_certificates.json"
    )
    payload = json.loads(fixture_path.read_text())["recursive_runs"][0]["nodes"][2][
        "joint_simulation"
    ]
    store = FileSystemCAS(tmp_path / "receipt-cas")
    options = PutOptions(
        kind=JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
        media_type="application/json",
        schema=SchemaInfo(name=JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA, version="1.0.0"),
    )
    ref = store.put_json(
        payload,
        options,
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True),
        return_selected_profile=True,
    )
    original = owner.build_content_bound_simulation_receipt
    calls: list[int] = []

    def counted(_code: object, _offset: int) -> None:
        calls.append(1)

    monitoring = sys.monitoring
    tool_id = next(index for index in range(6) if monitoring.get_tool(index) is None)
    monitoring.use_tool_id(tool_id, "receipt-test")
    monitoring.register_callback(tool_id, monitoring.events.PY_START, counted)
    monitoring.set_local_events(tool_id, original.__code__, monitoring.events.PY_START)

    def reset_monitoring() -> None:
        monitoring.set_local_events(tool_id, original.__code__, 0)
        monitoring.register_callback(tool_id, monitoring.events.PY_START, None)
        monitoring.free_tool_id(tool_id)

    request.addfinalizer(reset_monitoring)
    with owner._receipt_verification_operation():
        first = load_joint_simulation_result(ref, store=store)
        second = load_joint_simulation_result(ref, store=store)
        assert first is not second and len(calls) == 1
        with owner._receipt_verification_operation():
            load_joint_simulation_result(ref, store=store)
            assert len(calls) == 1
        outer_memo = owner._RECEIPT_MEMO.get()

        @owner._receipt_verification_worker_scoped
        def worker() -> None:
            assert owner._RECEIPT_MEMO.get() is not outer_memo
            assert owner._RECEIPT_CAS_BINDING.get() is None
            load_joint_simulation_result(ref, store=store)
            assert len(calls) == 2

        worker()
        assert owner._RECEIPT_MEMO.get() is outer_memo
        load_joint_simulation_result(ref, store=store)
        assert len(calls) == 2

        @owner._receipt_verification_worker_scoped
        def failed_worker() -> None:
            assert owner._RECEIPT_MEMO.get() is not outer_memo
            assert owner._RECEIPT_CAS_BINDING.get() is None
            raise RuntimeError("worker failed")

        with owner._cas_receipt_verification_binding(
            store.get_bytes(ref), ("fixture",), canon=store.get_manifest(ref).canon
        ):
            outer_binding = owner._RECEIPT_CAS_BINDING.get()
            assert outer_binding is not None
            with pytest.raises(RuntimeError, match="worker failed"):
                failed_worker()
            assert owner._RECEIPT_CAS_BINDING.get() is outer_binding
            assert owner._RECEIPT_MEMO.get() is outer_memo
        # A returned mutable object is not the next read's cached object.
        first._content_payload["world_model_record_ref"] = "mutated"
        with pytest.raises(ProofReceiptError):
            owner.verify_simulation_receipt(first.receipt, first.content_bound_payload())
        before = len(calls)
        third = load_joint_simulation_result(ref, store=store)
        assert (
            len(calls) == before and third.content_bound_payload() == second.content_bound_payload()
        )
        # Current rules are part of the key; no previous result certifies them.
        with monkeypatch.context() as changed:
            changed.setattr(
                gy_waist,
                "GY_CONTENT_HASH_EXCLUDED_FIELDS",
                (*gy_waist.GY_CONTENT_HASH_EXCLUDED_FIELDS, "not_present_in_payload"),
            )
            load_joint_simulation_result(ref, store=store)
            assert len(calls) == before + 1
        baseline_calls = len(calls)
        original_exclusion = gy_waist.is_gy_content_hash_excluded_field

        def same_rule_but_closure(key: str) -> bool:
            return original_exclusion(key)

        with monkeypatch.context() as changed:
            changed.setattr(gy_waist, "is_gy_content_hash_excluded_field", same_rule_but_closure)
            load_joint_simulation_result(ref, store=store)
            load_joint_simulation_result(ref, store=store)
        assert len(calls) == baseline_calls + 2
        alternate = store.put_json(
            payload,
            PutOptions(
                kind=JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA, version="1.0.0"),
                warnings=[WarningRecord(code="test.alternate_profile", msg="different view")],
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True),
            return_selected_profile=True,
        )
        assert alternate.artifact_id == ref.artifact_id
        assert alternate.manifest_profile_sha256 != ref.manifest_profile_sha256
        before_alternate = len(calls)
        load_joint_simulation_result(alternate, store=store)
        assert len(calls) == before_alternate + 1

        # Every hit still reads the selected manifest and source bytes.
        def missing(*_args: Any, **_kwargs: Any) -> bytes:
            raise FileNotFoundError("selected payload removed")

        with monkeypatch.context() as removed:
            removed.setattr(store, "get_bytes", missing)
            with pytest.raises(GenerationCycleError, match="joint_simulation_result_unavailable"):
                load_joint_simulation_result(ref, store=store)
        with monkeypatch.context() as removed:
            removed.setattr(store, "get_raw_manifest_bytes", missing)
            with pytest.raises(GenerationCycleError, match="joint_simulation_result_unavailable"):
                load_joint_simulation_result(ref, store=store)

        def revoked(*_args: Any, **_kwargs: Any) -> bytes:
            raise ArtifactOwnershipError("fixture owner revoked")

        with monkeypatch.context() as denied:
            denied.setattr(store, "get_bytes", revoked)
            with pytest.raises(GenerationCycleError, match="joint_simulation_result_unavailable"):
                load_joint_simulation_result(ref, store=store)
        forged = copy.deepcopy(payload)
        forged["receipt"]["payload_hash"] = "sha256:" + "a" * 64
        forged_ref = store.put_json(
            forged,
            options,
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True),
            return_selected_profile=True,
        )
        with pytest.raises(GenerationCycleError, match="receipt_or_payload_invalid"):
            load_joint_simulation_result(forged_ref, store=store)
    after = len(calls)
    with owner._receipt_verification_operation():
        load_joint_simulation_result(ref, store=store)
    assert len(calls) == after + 1


def test_operation_receipt_memo_with_explicit_retained_selected_cas(
    request: pytest.FixtureRequest,
) -> None:
    """Measure the exact retained selected result without running another engine."""
    import os
    import sys
    from time import perf_counter

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality import joint_simulation_horizon as owner
    from polisyos.runtime.quality.acquisition_evaluation import (
        rebuild_selected_candidate_n5_request,
    )
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationN5InputV5
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result

    fixture_root = os.environ.get("POLISYOS_TEST_RECEIPT_RETAINED_CAS")
    selected_json = os.environ.get("POLISYOS_TEST_RECEIPT_COMPILED_REF")
    selected_inputs = os.environ.get("POLISYOS_TEST_RECEIPT_SELECTED_INPUTS")
    tenant = os.environ.get("POLISYOS_TEST_RECEIPT_TENANT")
    cell = os.environ.get("POLISYOS_TEST_RECEIPT_CELL")
    if not fixture_root or not (selected_json or selected_inputs) or not tenant or not cell:
        pytest.skip("explicit retained CAS, selected refs, tenant and cell are required")
    store = FileSystemCAS.open_existing_read_only(Path(fixture_root))
    calls: list[int] = []
    verification_entries: list[int] = []
    gy_calls: list[int] = []
    selected_gy_calls: list[int] = []
    binding_decodes: list[int] = []
    monitoring = sys.monitoring
    tool_id = next(index for index in range(6) if monitoring.get_tool(index) is None)
    monitoring.use_tool_id(tool_id, "receipt-retained-test")

    code = owner.build_content_bound_simulation_receipt.__code__
    verify_code = owner.verify_simulation_receipt.__code__
    gy_code = owner.gy_content_hash.__code__
    decode_code = owner.from_canonical_bytes.__code__
    selected_code = owner.JointSimulationHorizonController.validate_selected_result.__code__
    binding_code = owner._cas_receipt_verification_binding.__wrapped__.__code__

    def counted(observed_code: object, _offset: int) -> None:
        if observed_code is code:
            calls.append(1)
        elif observed_code is verify_code:
            verification_entries.append(1)
        elif observed_code is gy_code:
            gy_calls.append(1)
            if sys._getframe(1).f_back.f_code is selected_code:
                selected_gy_calls.append(1)
        elif observed_code is decode_code and sys._getframe(1).f_back.f_code is binding_code:
            binding_decodes.append(1)

    monitoring.register_callback(tool_id, monitoring.events.PY_START, counted)
    monitoring.set_local_events(tool_id, code, monitoring.events.PY_START)
    monitoring.set_local_events(tool_id, verify_code, monitoring.events.PY_START)
    monitoring.set_local_events(tool_id, gy_code, monitoring.events.PY_START)
    monitoring.set_local_events(tool_id, decode_code, monitoring.events.PY_START)

    def reset_monitoring() -> None:
        monitoring.set_local_events(tool_id, code, 0)
        monitoring.set_local_events(tool_id, verify_code, 0)
        monitoring.set_local_events(tool_id, gy_code, 0)
        monitoring.set_local_events(tool_id, decode_code, 0)
        monitoring.register_callback(tool_id, monitoring.events.PY_START, None)
        monitoring.free_tool_id(tool_id)

    request.addfinalizer(reset_monitoring)
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        if selected_inputs is not None:
            selected = json.loads(Path(selected_inputs).read_text())
            assert selected["tenant_id"] == tenant and selected["cell_id"] == cell
            input_ref = ArtifactRef.model_validate(selected["input"]["ref"])
            result_ref = ArtifactRef.model_validate(selected["result"]["ref"])
        else:
            assert selected_json is not None
            compiled_ref = ArtifactRef.model_validate_json(selected_json)
            compiled = CompiledRecursiveGenerationCycleRun.model_validate(
                load_core_json_artifact(store, compiled_ref)
            )
            cycles = tuple(
                cycle
                for leaf in compiled.recursive_run.leaf_nodes
                if leaf.cycle_run is not None
                for cycle in leaf.cycle_run.cycles
            )
            assert len(cycles) == 1
            simulation = cycles[0].simulation
            input_ref = simulation.candidate_simulation_n5_input_ref
            result_ref = simulation.simulation_result_ref
            assert input_ref is not None and result_ref is not None
        input_record = CandidateSimulationN5InputV5.model_validate(
            load_core_json_artifact(store, input_ref)
        )
        expected = rebuild_selected_candidate_n5_request(
            store=store,
            input_ref=input_ref,
            run_id=input_record.run_id,
            job_id=input_record.job_id,
            tenant_id=input_record.tenant_id,
            cell_id=input_record.cell_id,
        )
        calls.clear()
        verification_entries.clear()
        gy_calls.clear()
        selected_gy_calls.clear()
        binding_decodes.clear()
        start = perf_counter()
        with owner._receipt_verification_operation():
            first = load_joint_simulation_result(result_ref, store=store, expected_request=expected)
            first_elapsed = perf_counter() - start
            first_count = len(calls)
            second = load_joint_simulation_result(
                result_ref, store=store, expected_request=expected
            )
            total_elapsed = perf_counter() - start
            two_load_entries = len(verification_entries)
            two_load_gy_calls = len(gy_calls)
            assert len(selected_gy_calls) == 0
            assert len(binding_decodes) == 2
            assert first_count == 1 and len(calls) == 1
            assert two_load_entries >= 4
            assert first is not second and first.receipt == second.receipt
            changed = expected.model_copy(update={"replications": expected.replications + 1})
            with pytest.raises(
                ValueError, match="joint_simulation_result_execution_binding_invalid"
            ):
                load_joint_simulation_result(result_ref, store=store, expected_request=changed)
            assert len(calls) == 1
            changed_comparator = expected.model_copy(
                update={
                    "comparator_profile": owner.NCMConditionalComparatorProfile(
                        outcome_units=dict.fromkeys(expected.selected_outcomes, "fixture-unit")
                    ),
                    "evidence_state": expected.evidence_state or {},
                }
            )
            with pytest.raises(
                ValueError, match="joint_simulation_result_execution_binding_invalid"
            ):
                load_joint_simulation_result(
                    result_ref, store=store, expected_request=changed_comparator
                )
            controller = JointSimulationHorizonController()
            altered_model = first.model_copy(update={"world_model_record_ref": "mutated"})
            with pytest.raises(JointSimulationControllerError) as model_refusal:
                controller.validate_selected_result(request=expected, result=altered_model)
            assert str(model_refusal.value.__cause__) == "result_model_receipt_payload_mismatch"
            altered_payload = second.model_copy(deep=True)
            altered_payload._content_payload["world_model_record_ref"] = "mutated"
            with pytest.raises(JointSimulationControllerError) as payload_refusal:
                controller.validate_selected_result(request=expected, result=altered_payload)
            assert isinstance(payload_refusal.value.__cause__, ProofReceiptError)
        print(
            f"RETAINED_RECEIPT_BUILDS first={first_count} two_load_builds=1 "
            f"two_load_verifications={two_load_entries} two_load_hits={two_load_entries - 1} "
            f"gy_calls={two_load_gy_calls} selected_gy_calls=0 binding_decodes=2 "
            f"first_seconds={first_elapsed:.6f} two_loads_seconds={total_elapsed:.6f}",
            flush=True,
        )


def test_joint_simulation_v1_result_replays_byte_exactly_without_state_handoff(
    tmp_path: Path,
) -> None:
    """The tracked historical v1 projection survives an exact CAS read/re-persist."""

    from polisyos.core.canon.canon_json import CanonSpec, to_canonical_bytes
    from polisyos.runtime.quality.generation_cycle import (
        JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
        JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    fixture_path = (
        Path(__file__).resolve().parents[4]
        / "architecture/policy_design_case/layer3_gy_composition_certificates.json"
    )
    embedded = json.loads(fixture_path.read_text(encoding="utf-8"))["recursive_runs"][0]["nodes"][
        2
    ]["joint_simulation"]
    assert embedded["schema_version"] == "policyos.runtime.joint_simulation_horizon.v1"
    assert "state_consumption" not in embedded
    legacy_spec = CanonSpec(forbid_floats=False, forbid_nan_inf=True)

    store = FileSystemCAS(tmp_path / "n5-v1-replay-cas")
    try:
        first_ref = store.put_json(
            embedded,
            PutOptions(
                kind=JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA, version="1.0.0"),
            ),
            canon_spec=legacy_spec,
        )
        first_bytes = store.get_bytes(first_ref)
        assert first_bytes == to_canonical_bytes(embedded, legacy_spec)
        first_manifest = store.get_manifest(first_ref)
        assert first_manifest.artifact_schema is not None
        assert first_manifest.artifact_schema.version == "1.0.0"

        replayed = load_joint_simulation_result(first_ref, store=store)
        assert replayed.schema_version == "policyos.runtime.joint_simulation_horizon.v1"
        assert replayed.state_consumption is None
        replayed_ref = persist_joint_simulation_result(replayed, store=store)
        assert replayed_ref.artifact_id == first_ref.artifact_id
        assert store.get_bytes(replayed_ref) == first_bytes
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def test_joint_simulation_v4_result_replays_byte_exactly_with_interaction_summary(
    tmp_path: Path,
) -> None:
    """A historical v4 wire replays exactly beside a separate current v5 result."""

    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.generation_cycle import (
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JOINT_SIMULATION_HORIZON_SCHEMA_VERSION,
    )
    from tests.unit.remediation.test_cyc_02 import (
        _historical_v4_numeric_interaction,
        _persist_legacy_n5_result,
    )

    request = _request().model_copy(
        update={"horizon": HorizonSpec(start=0, end=0, step=1), "replications": 2}
    )
    result = JointSimulationHorizonController().run(request)
    assert result.schema_version == JOINT_SIMULATION_HORIZON_SCHEMA_VERSION
    assert result.schema_version == "policyos.runtime.joint_simulation_horizon.v5"
    assert "interaction_numerical_tolerance" in result.diagnostics
    assert result.state_consumption is None
    assert result.interaction_terms
    for term in result.interaction_terms:
        assert term.replication_sampling_by_step
        for summary in term.replication_sampling_by_step.values():
            assert summary.status == "estimated"
            assert summary.replicate_count == 2
            assert len(summary.samples) == 2

    store = FileSystemCAS(tmp_path / "n5-historical-v4-replay-cas")
    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            current_ref = persist_joint_simulation_result(result, store=store)
            current_bytes = store.get_bytes(current_ref)
            current_manifest = store.get_manifest(current_ref)
            current_replayed = load_joint_simulation_result(
                current_ref,
                store=store,
                expected_world_model_record_content_hash=result.world_model_record_content_hash,
            )
        current_payload = from_canonical_bytes(current_bytes)
        assert current_payload["schema_version"] == result.schema_version
        assert current_manifest.artifact_schema is not None
        assert current_manifest.artifact_schema.version == "5.0.0"
        assert current_replayed.schema_version == JOINT_SIMULATION_HORIZON_SCHEMA_VERSION
        assert current_replayed.content_bound_payload() == result.content_bound_payload()

        # Build a real historical wire from current paired samples and the
        # verified v4 history helper; changing only the schema label would
        # leave v5-only fields and the wrong historical verdict in the bytes.
        historical_ref, historical_v4 = _persist_legacy_n5_result(
            result,
            store=store,
            source_ref=current_ref,
            schema_version=4,
        )
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            historical_bytes = store.get_bytes(historical_ref)
            historical_manifest = store.get_manifest(historical_ref)
        historical_payload = from_canonical_bytes(historical_bytes)

        assert (
            historical_payload["schema_version"] == "policyos.runtime.joint_simulation_horizon.v4"
        )
        assert "state_consumption" not in historical_payload
        assert "interaction_numerical_tolerance" not in historical_payload["diagnostics"]
        assert historical_manifest.artifact_schema is not None
        assert historical_manifest.artifact_schema.version == "4.0.0"
        assert historical_v4.feedback_classification.numeric_interaction == (
            _historical_v4_numeric_interaction(historical_payload)
        )
        assert historical_v4.feedback_classification.interaction_sampling_status == (
            result.feedback_classification.interaction_sampling_status
        )
        current_terms = {(term.atom_ids, term.outcome): term for term in result.interaction_terms}
        for historical_term in historical_v4.interaction_terms:
            current_term = current_terms[(historical_term.atom_ids, historical_term.outcome)]
            assert historical_term.by_step == current_term.by_step
            assert (
                historical_term.replication_sampling_by_step
                == current_term.replication_sampling_by_step
            )

        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            replayed = load_joint_simulation_result(
                historical_ref,
                store=store,
                expected_world_model_record_content_hash=result.world_model_record_content_hash,
            )
            replayed_ref = persist_joint_simulation_result(replayed, store=store)
            assert replayed_ref.artifact_id == historical_ref.artifact_id
            assert store.get_bytes(replayed_ref) == historical_bytes
            assert store.get_bytes(current_ref) == current_bytes
        assert replayed.schema_version == "policyos.runtime.joint_simulation_horizon.v4"
        assert replayed.state_consumption is None
        assert replayed.content_bound_payload() == historical_v4.content_bound_payload()
        assert replayed.feedback_classification == historical_v4.feedback_classification
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def _paired_sampling_result_for_wire(tmp_path: Path, wire: str) -> JointSimulationResult:
    """Build a current result or a schema-qualified v4 fixture freshly read from CAS."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.generation_cycle import persist_joint_simulation_result
    from tests.unit.remediation.test_cyc_02 import _persist_legacy_n5_result

    result = JointSimulationHorizonController().run(
        _request().model_copy(
            update={"horizon": HorizonSpec(start=0, end=0, step=1), "replications": 2}
        )
    )
    assert result.schema_version == "policyos.runtime.joint_simulation_horizon.v5"
    if wire == "v5":
        return result
    assert wire == "v4"
    store = FileSystemCAS(tmp_path / "historical-paired-sampling")
    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            current_ref = persist_joint_simulation_result(result, store=store)
        _, historical = _persist_legacy_n5_result(
            result, store=store, source_ref=current_ref, schema_version=4
        )
        assert historical.schema_version == "policyos.runtime.joint_simulation_horizon.v4"
        return historical
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


@pytest.mark.parametrize("wire", ["v4", "v5"])
def test_sampling_and_interaction_summaries_are_recomputed_and_required(
    tmp_path: Path, wire: str
) -> None:
    """B21: signed summary markers cannot replace the selected draw substance."""

    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationResult,
        build_content_bound_simulation_receipt,
    )

    result = _paired_sampling_result_for_wire(tmp_path, wire)
    payload = result.content_bound_payload()
    assert payload["schema_version"] == f"policyos.runtime.joint_simulation_horizon.{wire}"
    point = payload["trajectories"][0]["points"][0]
    summary = point["replication_sampling"]
    assert summary["status"] == "estimated"
    assert summary["replicate_count"] == 2
    assert len(set(summary["seeds"])) == 2
    for trajectory in payload["trajectories"]:
        for persisted_point in trajectory["points"]:
            persisted_summary = persisted_point["replication_sampling"]
            assert [sample["seed"] for sample in persisted_summary["samples"]] == persisted_summary[
                "seeds"
            ]
            assert [sample["engine_state"] for sample in persisted_summary["samples"]] == (
                persisted_point["engine_state"]["replication_engine_states"]
            )

    unbound_state = copy.deepcopy(payload)
    state_point = unbound_state["trajectories"][0]["points"][0]
    state_point["engine_state"]["replication_engine_states"][0]["candidate_probe"] = True
    state_receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=unbound_state,
        diagnostics=unbound_state["diagnostics"],
    )
    with pytest.raises(ValueError, match="replication_engine_state_binding_mismatch"):
        JointSimulationResult.model_validate(
            {**unbound_state, "receipt": state_receipt.model_dump(mode="json")}
        )

    unbound_seed = copy.deepcopy(payload)
    unbound_seed["trajectories"][0]["points"][0]["replication_sampling"]["samples"][0]["seed"] += 20
    seed_receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=unbound_seed,
        diagnostics=unbound_seed["diagnostics"],
    )
    with pytest.raises(ValueError, match="replication_sample_seed_binding_mismatch"):
        JointSimulationResult.model_validate(
            {**unbound_seed, "receipt": seed_receipt.model_dump(mode="json")}
        )

    forged = copy.deepcopy(payload)
    forged_summary = forged["trajectories"][0]["points"][0]["replication_sampling"]
    forged_summary["outcomes_standard_error"] = {
        key: float(value or 0.0) + 1.0
        for key, value in forged_summary["outcomes_standard_error"].items()
    }
    forged_receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=forged,
        diagnostics=forged["diagnostics"],
    )
    with pytest.raises(ValueError, match="replication_standard_error_recomputation_mismatch"):
        JointSimulationResult.model_validate(
            {**forged, "receipt": forged_receipt.model_dump(mode="json")}
        )

    missing = copy.deepcopy(payload)
    missing["trajectories"][0]["points"][0].pop("replication_sampling")
    missing_receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=missing,
        diagnostics=missing["diagnostics"],
    )
    with pytest.raises(ValueError, match="replication_sampling_summary_missing"):
        JointSimulationResult.model_validate(
            {**missing, "receipt": missing_receipt.model_dump(mode="json")}
        )

    # Remove the derived interaction summary but retain its additive/status markers.
    missing_interaction_summary = copy.deepcopy(payload)
    assert missing_interaction_summary["interaction_terms"]
    missing_interaction_summary["interaction_terms"][0].pop("replication_sampling_by_step")
    interaction_receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=missing_interaction_summary,
        diagnostics=missing_interaction_summary["diagnostics"],
    )
    with pytest.raises(ValueError, match="interaction_sampling_source_recomputation_mismatch"):
        JointSimulationResult.model_validate(
            {
                **missing_interaction_summary,
                "receipt": interaction_receipt.model_dump(mode="json"),
            }
        )


@pytest.mark.parametrize("wire", ["v4", "v5"])
def test_n5_fresh_cas_reader_rejects_forged_replicate_mean(tmp_path: Path, wire: str) -> None:
    """A content-bound CAS payload cannot replace the selected draw mean."""

    from polisyos.core.canon import CanonSpec
    from polisyos.runtime.quality.generation_cycle import (
        JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
        JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA,
        GenerationCycleError,
        load_joint_simulation_result,
    )

    result = _paired_sampling_result_for_wire(tmp_path, wire)
    forged = copy.deepcopy(result.content_bound_payload())
    point = forged["trajectories"][0]["points"][0]
    key = next(iter(point["outcomes"]))
    point["outcomes"][key] += 1.0
    forged["receipt"] = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=forged,
        diagnostics=forged["diagnostics"],
    ).model_dump(mode="json")

    store = FileSystemCAS(tmp_path / "n5-forged-mean-cas")
    try:
        ref = store.put_json(
            forged,
            PutOptions(
                kind=JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name=JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA,
                    version={"v4": "4.0.0", "v5": "5.0.0"}[wire],
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True),
        )
        with pytest.raises(GenerationCycleError) as exc_info:
            load_joint_simulation_result(ref, store=store)
        assert exc_info.value.code == "joint_simulation_result_integrity_invalid"
        assert "replication_mean_recomputation_mismatch" in str(exc_info.value.__cause__)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


@pytest.mark.parametrize("wire", ["v4", "v5"])
def test_layer3_raw_replication_validator_fails_closed_on_malformed_metric_map(
    tmp_path: Path, wire: str
) -> None:
    """A supplied malformed draw map returns a typed issue, not an uncaught error."""

    from tools.quality.validation.check_layer3_gy_joint_simulation_horizon_contract import (
        _replication_sampling_issues,
        _replication_sampling_projection,
    )

    result = _paired_sampling_result_for_wire(tmp_path, wire)
    projection = _replication_sampling_projection(result)
    assert projection["schema_version"] == f"policyos.runtime.joint_simulation_horizon.{wire}"
    projection["trajectories"][0]["points"][0]["replication_sampling"]["samples"][0]["outcomes"] = (
        None
    )
    issues = _replication_sampling_issues(projection, expected_count=2)
    if wire == "v4":
        assert {issue["code"] for issue in issues} == {"replication_sample_metric_mapping_invalid"}
    else:
        assert {issue["code"] for issue in issues} == {"replication_typed_result_invalid"}
        assert "outcomes" in issues[0]["detail"]


def test_layer3_v5_quality_consumer_reconciles_persisted_result_and_rejects_rehashed_corruption(
    tmp_path: Path,
) -> None:
    """The N5 gate consumes v5's typed wire, not only its projected status fields."""

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.generation_cycle import (
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )
    from tests.unit.remediation.test_sim_03 import (
        _native_expression_request,
        _with_native_conditional_comparator,
    )
    from tools.quality.validation.check_layer3_gy_joint_simulation_horizon_contract import (
        _interaction_sampling_issues,
        _replication_sampling_issues,
        _replication_sampling_projection,
        _validate_gate,
    )

    request = _with_native_conditional_comparator(
        _native_expression_request(
            "u + 2 * income_delta + 3 * balance_delta + 4 * income_delta * balance_delta",
            replications=2,
        )
    )
    produced = JointSimulationHorizonController().run(request)
    assert produced.schema_version == "policyos.runtime.joint_simulation_horizon.v5"
    assert produced.diagnostics["interaction_numerical_tolerance"]["status"] == "qualified"

    store = FileSystemCAS(tmp_path / "n5-v5-quality-consumer-cas")
    try:
        with tenant_scope(None, tenant_id="tenant-n5-quality-consumer", cell_id="cell-n5"):
            result_ref = persist_joint_simulation_result(produced, store=store)
            result = load_joint_simulation_result(
                result_ref,
                store=store,
                expected_request=request,
            )
        projection = _replication_sampling_projection(result)
        assert projection["schema_version"] == "policyos.runtime.joint_simulation_horizon.v5"
        assert projection["receipt"] == result.receipt.model_dump(mode="json")
        assert (
            _validate_gate(
                projection,
                expected_engine="ncm_parallel_worlds",
                expected_temporal="static",
                expected_output_shape="static_point",
                expected_semantics="static_SCM",
                require_evolving_state=False,
            )
            == []
        )
        assert _replication_sampling_issues(projection, expected_count=2) == []
        assert _interaction_sampling_issues(projection) == []

        unknown_numeric_claim = copy.deepcopy(result.content_bound_payload())
        unknown_numeric_claim["unexpected_numeric_claim"] = {
            "status": "qualified",
            "value": 1,
        }
        unknown_numeric_claim_receipt = build_content_bound_simulation_receipt(
            engine_kind=result.receipt.engine_kind,
            payload=unknown_numeric_claim,
            diagnostics=unknown_numeric_claim["diagnostics"],
        )
        verify_simulation_receipt(unknown_numeric_claim_receipt, unknown_numeric_claim)
        unknown_numeric_claim["receipt"] = unknown_numeric_claim_receipt.model_dump(mode="json")
        unknown_numeric_claim_gate = {**projection, **unknown_numeric_claim}
        unknown_numeric_claim_gate["receipt_payload_hash"] = (
            unknown_numeric_claim_receipt.payload_hash
        )
        unknown_numeric_claim_issues = _replication_sampling_issues(
            unknown_numeric_claim_gate,
            expected_count=2,
        )
        assert unknown_numeric_claim_issues == [
            {
                "code": "replication_projection_keyset_mismatch",
                "missing_fields": [],
                "unexpected_fields": ["unexpected_numeric_claim"],
            }
        ]

        unsupported_result = JointSimulationHorizonController().run(
            _request().model_copy(update={"coupling_graph": _coupling_graph("shared_resource")})
        )
        assert unsupported_result.schema_version == ("policyos.runtime.joint_simulation_horizon.v5")
        assert unsupported_result.engine_decisions[0].decision == "unsupported"
        assert unsupported_result.trajectories == ()
        unsupported_wire = unsupported_result.model_dump(mode="json")
        unsupported_wire["joint_atom_ids"] = list(unsupported_result.atom_ids)
        assert _replication_sampling_issues(unsupported_wire, expected_count=None) == [
            {"code": "replication_joint_trajectory_unavailable"}
        ]
        assert _interaction_sampling_issues(unsupported_wire) == [
            {"code": "interaction_joint_trajectory_unavailable"}
        ]

        empty_joint_points = copy.deepcopy(result.content_bound_payload())
        joint_wire = next(
            trajectory
            for trajectory in empty_joint_points["trajectories"]
            if trajectory["run_level"] == "joint"
        )
        joint_wire["points"] = []
        empty_joint_receipt = build_content_bound_simulation_receipt(
            engine_kind=result.receipt.engine_kind,
            payload=empty_joint_points,
            diagnostics=empty_joint_points["diagnostics"],
        )
        verify_simulation_receipt(empty_joint_receipt, empty_joint_points)
        empty_joint_points["receipt"] = empty_joint_receipt.model_dump(mode="json")
        try:
            JointSimulationResult.model_validate(empty_joint_points)
        except (ProofReceiptError, TypeError, ValueError) as exc:
            empty_joint_schema_valid = False
            empty_joint_schema_error = str(exc)
        else:
            empty_joint_schema_valid = True
            empty_joint_schema_error = ""
        empty_joint_gate = {**projection, **empty_joint_points}
        empty_joint_gate["receipt_payload_hash"] = empty_joint_receipt.payload_hash
        empty_joint_issues = _replication_sampling_issues(
            empty_joint_gate,
            expected_count=2,
        )
        if empty_joint_schema_valid:
            assert empty_joint_issues == [{"code": "replication_joint_trajectory_unavailable"}]
        else:
            assert len(empty_joint_issues) == 1
            assert empty_joint_issues[0]["code"] == "replication_typed_result_invalid"
            assert "interaction_sampling_issue_recomputation_mismatch" in (empty_joint_schema_error)
            assert "interaction_sampling_issue_recomputation_mismatch" in empty_joint_issues[0].get(
                "detail", ""
            )
            assert "payload_hash" not in empty_joint_issues[0].get("detail", "")

        projection_only_mutation = copy.deepcopy(projection)
        projection_only_mutation["joint_terminal_outcomes"]["firm_survival"] += 1.0
        projection_issues = _validate_gate(
            projection_only_mutation,
            expected_engine="ncm_parallel_worlds",
            expected_temporal="static",
            expected_output_shape="static_point",
            expected_semantics="static_SCM",
            require_evolving_state=False,
        )
        assert any(
            issue["code"] == "sampling_projection_mismatch"
            and issue.get("field") == "joint_terminal_outcomes"
            for issue in projection_issues
        )

        corrupt_draw = copy.deepcopy(result.content_bound_payload())
        draw = corrupt_draw["trajectories"][0]["points"][0]["replication_sampling"]["samples"][0]
        draw["engine_state"]["corrupt_draw_binding"] = True
        draw_receipt = build_content_bound_simulation_receipt(
            engine_kind=result.receipt.engine_kind,
            payload=corrupt_draw,
            diagnostics=corrupt_draw["diagnostics"],
        )
        corrupt_draw["receipt"] = draw_receipt.model_dump(mode="json")
        corrupt_draw_gate = {**projection, **corrupt_draw}
        corrupt_draw_gate["receipt_payload_hash"] = draw_receipt.payload_hash
        draw_issues = _replication_sampling_issues(corrupt_draw_gate, expected_count=2)
        assert any(
            issue["code"] == "replication_typed_result_invalid"
            and "replication_engine_state_binding_mismatch" in issue.get("detail", "")
            and "payload_hash" not in issue.get("detail", "")
            for issue in draw_issues
        ), draw_issues

        corrupt_interaction = copy.deepcopy(result.content_bound_payload())
        term = corrupt_interaction["interaction_terms"][0]
        step = next(iter(term["by_step"]))
        term["by_step"][step] += 1.0
        interaction_receipt = build_content_bound_simulation_receipt(
            engine_kind=result.receipt.engine_kind,
            payload=corrupt_interaction,
            diagnostics=corrupt_interaction["diagnostics"],
        )
        corrupt_interaction["receipt"] = interaction_receipt.model_dump(mode="json")
        corrupt_interaction_gate = {**projection, **corrupt_interaction}
        corrupt_interaction_gate["receipt_payload_hash"] = interaction_receipt.payload_hash
        interaction_issues = _interaction_sampling_issues(corrupt_interaction_gate)
        assert any(
            issue["code"] == "interaction_typed_result_invalid"
            and "JointSimulationResult" in issue.get("detail", "")
            and "payload_hash" not in issue.get("detail", "")
            for issue in interaction_issues
        ), interaction_issues

        assert result.feedback_classification.numeric_interaction == "non_additive"
        corrupt_tolerance = copy.deepcopy(result.content_bound_payload())
        corrupt_tolerance["feedback_classification"]["numeric_interaction"] = "additive"
        tolerance_receipt = build_content_bound_simulation_receipt(
            engine_kind=result.receipt.engine_kind,
            payload=corrupt_tolerance,
            diagnostics=corrupt_tolerance["diagnostics"],
        )
        corrupt_tolerance["receipt"] = tolerance_receipt.model_dump(mode="json")
        corrupt_tolerance_gate = {**projection, **corrupt_tolerance}
        corrupt_tolerance_gate["receipt_payload_hash"] = tolerance_receipt.payload_hash
        tolerance_issues = _interaction_sampling_issues(corrupt_tolerance_gate)
        assert any(
            issue["code"] == "interaction_typed_result_invalid"
            and "numeric_interaction_classification_recomputation_mismatch"
            in issue.get("detail", "")
            for issue in tolerance_issues
        )
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def test_committed_v1_joint_result_keeps_original_receipt_projection() -> None:
    """Replay the one tracked v1 result projection without adding v2 fields."""

    fixture_path = (
        Path(__file__).resolve().parents[4]
        / "architecture/policy_design_case/layer3_gy_composition_certificates.json"
    )
    embedded = json.loads(fixture_path.read_text(encoding="utf-8"))["recursive_runs"][0]["nodes"][
        2
    ]["joint_simulation"]
    payload = {key: value for key, value in embedded.items() if key != "receipt"}
    assert "state_consumption" not in payload
    parsed = JointSimulationResult.model_validate(embedded)
    assert parsed.schema_version == "policyos.runtime.joint_simulation_horizon.v1"
    verify_simulation_receipt(parsed.receipt, payload)
    from polisyos.runtime.quality.generation_cycle import (
        _n8_sampling_uncertainty_limitations,
    )

    assert _n8_sampling_uncertainty_limitations(parsed) == frozenset(
        {
            "legacy_sampling_not_established",
            "legacy_interaction_not_established",
            "interaction_numeric_classification_unsupported",
        }
    )


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
    assert result.feedback_classification.interaction_sampling_status == "not_established"
    assert "interaction_evidence_incomplete" in result.diagnostics["interaction_sampling_issues"]


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


def _shared_resource_stock_flow_fallback_request(
    *,
    candidate_order: tuple[str, ...],
) -> JointSimulationRequest:
    """Build one fixed-input request with two real registered dynamic candidates."""

    base = _request()
    state = {
        "initial_stocks": [10.0, 0.0],
        "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
        "exogenous_inflows": [0.0, 0.0],
    }
    variable_map = {
        "agents.income": "exogenous_inflows.0",
        "government.balance": "exogenous_inflows.1",
        "stock0": "stock:0",
        "stock1": "stock:1",
    }
    stock_flow_fqn = "simulation.system_dynamics.stock_flow@1.0.0"
    generic_registry_plan = EnginePlan(
        engine_kind="method_registry_estimator",
        objective_ref="objective://stock-flow-generic",
        method_fqn=stock_flow_fqn,
        eligibility_conditions=("multi_period",),
        variable_map=variable_map,
        system_dynamics_state=state,
        system_dynamics_params={"dt": 1.0},
    )
    system_dynamics_plan = EnginePlan(
        engine_kind="system_dynamics",
        objective_ref="objective://stock-flow-native",
        variable_map=variable_map,
        system_dynamics_state=state,
        system_dynamics_params={"dt": 1.0},
    )
    candidates = {
        "method_registry_estimator": generic_registry_plan,
        "system_dynamics": system_dynamics_plan,
    }
    if len(candidate_order) != len(candidates) or set(candidate_order) != set(candidates):
        raise ValueError("fallback_candidate_order_must_cover_the_declared_candidates")
    return base.model_copy(
        update={
            "selected_outcomes": ("stock0", "stock1"),
            "baseline_state": {"stock0": 10.0, "stock1": 0.0},
            "horizon": HorizonSpec(start=0, end=2, step=1),
            "coupling_graph": _coupling_graph("shared_resource"),
            "engine_plan": tuple(candidates[item] for item in candidate_order),
        }
    )


@pytest.mark.parametrize(
    ("candidate_order", "expected_trace"),
    [
        (
            ("method_registry_estimator", "system_dynamics"),
            (
                (
                    "method_registry_estimator",
                    "unsupported",
                    "coupling_composition_gate_unsupported",
                ),
                ("system_dynamics", "selected", "engine_eligibility_satisfied"),
            ),
        ),
        (
            ("system_dynamics", "method_registry_estimator"),
            (("system_dynamics", "selected", "engine_eligibility_satisfied"),),
        ),
    ],
    ids=("incompatible-first-falls-through", "compatible-first-short-circuits"),
)
def test_joint_simulation_engine_fallback_is_ordered_and_fresh_cas_bound(
    tmp_path: Path,
    candidate_order: tuple[str, ...],
    expected_trace: tuple[tuple[str, str, str], ...],
) -> None:
    """Only a coupling-capable registered runner produces the persisted result."""

    from polisyos.core.canon import from_canonical_bytes
    from polisyos.runtime.quality.generation_cycle import (
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    registry = MethodRegistry._create_fresh()
    request = _shared_resource_stock_flow_fallback_request(candidate_order=candidate_order)
    result = JointSimulationHorizonController(method_registry=registry).run(request)
    actual_trace = tuple(
        (item.engine_kind, item.decision, item.reason) for item in result.engine_decisions
    )
    assert actual_trace == expected_trace
    assert registry.get_entry("simulation.system_dynamics.stock_flow@1.0.0") is not None
    selected = tuple(item for item in result.engine_decisions if item.decision == "selected")
    assert len(selected) == 1
    assert selected[0].engine_kind == "system_dynamics"
    assert selected[0].method_fqn == "simulation.system_dynamics.stock_flow@1.0.0"
    assert result.receipt.engine_kind == "system_dynamics"
    assert result.receipt.calibration_status == "content_bound_run_receipt"
    assert result.diagnostics["engine_run_claimed"] is True
    assert result.diagnostics["coupling_support_status"] == "supported"
    assert all(item.engine_kind == "system_dynamics" for item in result.trajectories)
    assert all(item.method_fqn == selected[0].method_fqn for item in result.trajectories)
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.step for point in joint.points] == [0, 1, 2]
    assert set(joint.points[-1].outcomes) == {"stock0", "stock1"}

    store = FileSystemCAS(tmp_path / "n5-engine-fallback-cas")
    try:
        result_ref = persist_joint_simulation_result(result, store=store)
        persisted = from_canonical_bytes(store.get_bytes(result_ref))
        assert persisted["engine_decisions"] == [
            item.model_dump(mode="json") for item in result.engine_decisions
        ]
        fresh = load_joint_simulation_result(
            result_ref,
            store=store,
            expected_world_model_record_content_hash=request.world_model_record.content_hash,
            expected_atom_ids=tuple(item.intervention_id for item in request.intervention_atoms),
            expected_selected_outcomes=request.selected_outcomes,
        )
        assert fresh.content_bound_payload() == result.content_bound_payload()
        assert fresh.engine_decisions == result.engine_decisions
        assert fresh.receipt == result.receipt
        assert fresh.trajectories == result.trajectories
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


@pytest.mark.parametrize(
    "candidate_order",
    [
        ("method_registry_estimator", "system_dynamics"),
        ("system_dynamics", "method_registry_estimator"),
    ],
    ids=("incompatible-first", "system-dynamics-first"),
)
def test_joint_simulation_all_incompatible_candidates_persist_explicit_refusal(
    tmp_path: Path,
    candidate_order: tuple[str, ...],
) -> None:
    """Persist each ordered rejection; fresh numerical readers refuse no-run output."""

    from polisyos.core.canon import from_canonical_bytes
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    registry = MethodRegistry._create_fresh()
    assert len(registry) == 0
    request = _shared_resource_stock_flow_fallback_request(candidate_order=candidate_order)
    plans_by_kind = {plan.engine_kind: plan for plan in request.engine_plan}
    system_dynamics_plan = plans_by_kind["system_dynamics"]
    plans_by_kind["system_dynamics"] = system_dynamics_plan.model_copy(
        update={"system_dynamics_state": {"initial_stocks": [10.0, 0.0]}}
    )
    request = request.model_copy(
        update={"engine_plan": tuple(plans_by_kind[kind] for kind in candidate_order)}
    )
    result = JointSimulationHorizonController(method_registry=registry).run(request)

    expected_reasons = {
        "method_registry_estimator": "coupling_composition_gate_unsupported",
        "system_dynamics": "system_dynamics_state_missing",
    }
    actual_trace = tuple(
        (item.engine_kind, item.decision, item.reason) for item in result.engine_decisions
    )
    assert actual_trace == tuple(
        (kind, "unsupported", expected_reasons[kind]) for kind in candidate_order
    )
    decisions_by_kind = {item.engine_kind: item for item in result.engine_decisions}
    assert (
        "unsupported_coupling_class:shared_resource"
        in decisions_by_kind["method_registry_estimator"].blockers
    )
    assert "flow_matrix_missing" in decisions_by_kind["system_dynamics"].blockers
    assert registry.get_entry("simulation.system_dynamics.stock_flow@1.0.0") is not None
    assert result.diagnostics["engine_run_claimed"] is False
    assert result.trajectories == ()
    assert result.receipt.trajectory_count == 0
    assert result.receipt.authoritative_for == ()
    assert result.receipt.calibration_status == "unsupported_coupling_gated"

    store = FileSystemCAS(tmp_path / "n5-all-engines-rejected-cas")
    try:
        result_ref = persist_joint_simulation_result(result, store=store)
        persisted = from_canonical_bytes(store.get_bytes(result_ref))
        assert [item["reason"] for item in persisted["diagnostics"]["unsupported_reasons"]] == [
            expected_reasons[kind] for kind in candidate_order
        ]
        with pytest.raises(
            GenerationCycleError, match="joint_simulation_result_trajectory_missing"
        ):
            load_joint_simulation_result(
                result_ref,
                store=store,
                expected_world_model_record_content_hash=request.world_model_record.content_hash,
                expected_atom_ids=tuple(
                    item.intervention_id for item in request.intervention_atoms
                ),
                expected_selected_outcomes=request.selected_outcomes,
            )
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def test_contract_testing_can_only_demonstrate_removed_coupling_gate_mutation() -> None:
    request = _request().model_copy(
        update={
            "coupling_graph": _coupling_graph("feedback"),
            "horizon": HorizonSpec(start=0, end=0, step=1),
        }
    )

    result = JointSimulationHorizonController.for_contract_testing(disable_coupling_gate=True).run(
        request
    )

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
    plan = (
        _request()
        .engine_plan[0]
        .model_copy(update={"declared_equilibrium_semantics": "game_model"})
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


def test_program_graph_plan_refuses_conflicting_shared_slot_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import joint_simulation_horizon as controller_module

    real_execute = controller_module.execute_program_graph
    calls = 0

    def observe_execute(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return real_execute(*args, **kwargs)

    monkeypatch.setattr(controller_module, "execute_program_graph", observe_execute)
    request = _request().model_copy(
        update={
            "engine_plan": (_program_graph_plan(tmp_path, rates_by_atom=(0.10, 0.20)),),
            "selected_outcomes": ("mean_income",),
            "baseline_state": {"mean_income": 0.0},
        }
    )

    results = tuple(
        JointSimulationHorizonController().run(
            request.model_copy(update={"intervention_atoms": atoms})
        )
        for atoms in (
            request.intervention_atoms,
            tuple(reversed(request.intervention_atoms)),
        )
    )

    for result in results:
        decision = result.engine_decisions[0]
        assert decision.decision == "unsupported"
        assert decision.reason == "intervention_assignment_conflict"
        assert decision.blockers == ("intervention_assignment_conflict",)
        assert result.diagnostics["engine_run_claimed"] is False
        assert result.diagnostics["unsupported_reasons"] == [
            {
                "objective_ref": "objective://program-graph-smoke",
                "reason": "intervention_assignment_conflict",
                "blockers": ["intervention_assignment_conflict"],
            }
        ]
        assert result.trajectories == ()
        assert result.marginal_effects == {}
        assert result.interaction_terms == ()
        assert result.receipt.trajectory_count == 0
        assert result.receipt.authoritative_for == ()
        assert result.receipt.calibration_status == "no_run"
    assert calls == 0

    from polisyos.core.canon import from_canonical_bytes
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    store = FileSystemCAS(tmp_path / "n5-program-conflict-refusal-cas")
    try:
        result_ref = persist_joint_simulation_result(results[0], store=store)
        persisted = from_canonical_bytes(store.get_bytes(result_ref))
        assert persisted["engine_decisions"][0]["reason"] == ("intervention_assignment_conflict")
        assert persisted["diagnostics"]["engine_run_claimed"] is False
        with pytest.raises(
            GenerationCycleError, match="joint_simulation_result_trajectory_missing"
        ):
            load_joint_simulation_result(
                result_ref,
                store=store,
                expected_world_model_record_content_hash=(request.world_model_record.content_hash),
                expected_atom_ids=tuple(
                    item.intervention_id for item in request.intervention_atoms
                ),
                expected_selected_outcomes=request.selected_outcomes,
            )
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def test_program_graph_plan_roundtrips_exact_selected_compilation() -> None:
    compile_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="compiler.compile_report",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    legacy = EnginePlan(engine_kind="program_graph", objective_ref="objective://selected")
    assert "program_compilation_ref" not in legacy.model_dump(mode="json")

    plan = EnginePlan(
        engine_kind="program_graph",
        objective_ref=legacy.objective_ref,
        program_compilation_ref=compile_ref,
    )
    reopened = EnginePlan.model_validate_json(plan.model_dump_json())
    assert reopened.program_compilation_ref == compile_ref

    with pytest.raises(ValueError, match="program_compilation_ref_engine_mismatch"):
        EnginePlan(
            engine_kind="ncm_parallel_worlds",
            objective_ref=legacy.objective_ref,
            program_compilation_ref=compile_ref,
        )
    with pytest.raises(ValueError, match="program_compilation_ref_unselected"):
        EnginePlan(
            engine_kind="program_graph",
            objective_ref=legacy.objective_ref,
            program_compilation_ref=compile_ref.model_copy(
                update={"manifest_profile_sha256": None},
            ),
        )


def test_selected_program_graph_input_preflight_stops_before_runner_and_charge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The actual selected-model obligation set reaches the pre-runner stop."""
    from polisyos.core.artifacts import ArtifactRef, CoreJSONArtifactStore
    from polisyos.core.contracts.foundry import ExecPlanRef, ProgramGraphRef
    from polisyos.core.contracts.model_input_requirements import (
        load_model_input_obligation_set,
    )
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.foundry.execute import load_state_snapshot
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationControllerError,
        ProgramGraphInputsRequiredError,
    )
    from polisyos.runtime.quality.model_input_requirements import (
        derive_program_graph_input_interface,
        preflight_program_graph_inputs,
    )
    from tests._helpers.program_graph_tax_subsidy_input import (
        prepare_program_graph_tax_subsidy_input_case,
    )
    from tests.unit.runtime.quality.test_model_input_requirements import (
        _context,
        _stock_declaration,
    )

    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path,
        opening_balance_usd=None,
        mechanism_start_step=2,
        model_input_port_declaration_builder=_stock_declaration,
    )
    try:
        assert isinstance(case.store, CoreJSONArtifactStore)
        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        base_state = load_state_snapshot(
            case.store,
            snapshot_ref=case.bound_state_snapshot_ref,
        )
        selected_plan = EnginePlan(
            engine_kind="program_graph",
            objective_ref="objective://program-graph-model-input",
            eligibility_conditions=("acyclic", "state_transition"),
            variable_map={"mean_income": "agents.income"},
            program_store=case.store,
            program_graph_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            program_base_state=base_state,
            program_base_ref=case.bound_state_snapshot_ref,
            mechanism_registry=registry.mechanism_registry,
            slot_registry=registry.slot_registry,
            merge_registry=registry.merge_registry,
            selector_field_registry=registry.selector_field_registry,
            constraint_registry=registry.constraint_registry,
        )
        request = _request().model_copy(
            update={
                "engine_plan": (selected_plan,),
                "horizon": HorizonSpec(start=0, end=3, step=1),
                "selected_outcomes": ("mean_income",),
                "baseline_state": {"mean_income": 0.0},
            }
        )
        interface_ref = derive_program_graph_input_interface(
            case.store,
            program_graph_ref=ProgramGraphRef.model_validate(
                case.program_graph_ref.model_dump(mode="python")
            ),
            exec_plan_ref=ExecPlanRef.model_validate(case.exec_plan_ref.model_dump(mode="python")),
            registry_bundle_ref=case.registry_bundle_ref,
        )
        assert interface_ref is not None
        callback_calls: list[tuple[str, str]] = []

        def selected_input_preflight(
            actual_request: JointSimulationRequest,
            actual_plan: EnginePlan,
            decision: Any,
        ) -> Any:
            callback_calls.append((decision.engine_kind, decision.decision))
            assert actual_request.world_model_record is request.world_model_record
            assert actual_plan is selected_plan
            return preflight_program_graph_inputs(
                case.store,
                interface_ref=interface_ref,
                program_graph_ref=ProgramGraphRef.model_validate(
                    case.program_graph_ref.model_dump(mode="python")
                ),
                exec_plan_ref=ExecPlanRef.model_validate(
                    case.exec_plan_ref.model_dump(mode="python")
                ),
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=case.input_bindings_ref,
                context=_context(case),
                steps=actual_request.horizon.steps(),
            )

        controller = JointSimulationHorizonController()
        runner_registry_calls: list[str] = []
        monkeypatch.setattr(
            controller,
            "_engine_runners",
            lambda: runner_registry_calls.append("dispatch") or {},
        )
        physical_dispatch_calls: list[str] = []
        from polisyos.runtime.quality import joint_simulation_horizon as controller_module

        monkeypatch.setattr(
            controller_module,
            "_run_cached_replicates",
            lambda *args, **kwargs: physical_dispatch_calls.append("charge"),
        )
        with pytest.raises(
            JointSimulationControllerError, match="program_graph_input_preflight_required"
        ):
            controller.run(request)
        with pytest.raises(
            JointSimulationControllerError, match="program_graph_input_preflight_required"
        ):
            controller.run(request, _program_graph_input_preflight=lambda *_args: None)
        before_dependency = request.model_copy(
            update={"horizon": HorizonSpec(start=0, end=1, step=1)}
        )
        with pytest.raises(
            JointSimulationControllerError,
            match="program_graph_semantic_horizon_intake_not_established",
        ):
            controller.run(
                before_dependency, _program_graph_input_preflight=selected_input_preflight
            )
        with pytest.raises(ProgramGraphInputsRequiredError) as raised:
            controller.run(
                request,
                _program_graph_input_preflight=selected_input_preflight,
            )

        assert callback_calls == [("program_graph", "selected")] * 2
        assert runner_registry_calls == []
        assert physical_dispatch_calls == []
        assert isinstance(raised.value.obligation_set_ref, ArtifactRef)
        selected_set, obligations = load_model_input_obligation_set(
            case.store, raised.value.obligation_set_ref
        )
        assert selected_set.invocation.program_graph_ref == case.program_graph_ref
        assert selected_set.invocation.exec_plan_ref == case.exec_plan_ref
        assert selected_set.invocation.steps == request.horizon.steps()
        assert len(obligations) == 1
        assert obligations[0].port.slot_id == "government.balance"
        assert obligations[0].dependencies[0].first_required_step == 2
    finally:
        case.close()


def test_semantic_program_graph_horizon_executes_and_reopens_every_selected_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A native activated opening state reaches the late compiled mechanism."""
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import WarningRecord
    from polisyos.core.contracts.foundry import ExecPlanRef
    from polisyos.core.contracts.model_input_requirements import (
        ProgramGraphInputInvocation,
        load_model_input_obligation_set,
    )
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.foundry.data_plane import load_input_bindings
    from polisyos.foundry.execute import load_state_snapshot
    from polisyos.ir.trinity import load_trinity_bundle_artifact
    from polisyos.runtime.quality import joint_simulation_horizon as horizon_owner
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )
    from polisyos.runtime.quality.model_input_requirements import preflight_program_graph_inputs
    from tests._helpers.program_graph_tax_subsidy_input import (
        activated_program_graph_opening_stock,
        prepare_program_graph_tax_subsidy_input_case,
    )
    from tests.unit.foundry.runtime.test_execute_input_bindings import (
        _stock_declaration_in_source_scope,
    )
    from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import _n4_atom
    from tests.unit.runtime.quality.test_model_input_requirements import _context, _interface

    horizon = HorizonSpec(start=0, end=4, step=1)
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "graph",
        opening_balance_usd=None,
        mechanism_start_step=3,
        mechanism_duration_steps=2,
        model_input_port_declaration_builder=_stock_declaration_in_source_scope,
        snapshot_id="base-acquisition-horizon",
    )
    try:
        store = case.store
        invocation = ProgramGraphInputInvocation(
            context=_context(case),
            interface_ref=_interface(case),
            program_graph_ref=ProgramGraphRef.model_validate(case.program_graph_ref.model_dump()),
            exec_plan_ref=ExecPlanRef.model_validate(case.exec_plan_ref.model_dump()),
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=case.input_bindings_ref,
            steps=horizon.steps(),
        )
        obligation_ref = preflight_program_graph_inputs(
            store, **vars(invocation)
        ).obligation_set_ref
        _, (stock,) = load_model_input_obligation_set(store, obligation_ref)
        assert stock.port.purpose == "initial_state"
        assert {dep.first_required_step for dep in stock.dependencies} == {3}
        with activated_program_graph_opening_stock(
            tmp_path / "activated-source",
            case,
            obligation_set_ref=obligation_ref,
            expected_invocation=invocation,
        ) as materialize:
            opening = materialize(
                workspace_dir=tmp_path / "data-forge-workspace",
                transaction_time=datetime(2026, 10, 2, 12, tzinfo=UTC),
            )
        bindings_ref = opening.semantic_foundry_input_bindings_ref
        selection = opening.semantic_input_selection
        assert bindings_ref is not None and selection is not None
        assert (
            load_input_bindings(store, bindings_ref).data_snapshot_ref == opening.data_snapshot_ref
        )
        correspondence_ref = selection.correspondence_basis_ref
        registry = load_registry_bundle_content(store, case.registry_bundle_ref)
        trinity = load_trinity_bundle_artifact(ensure_ir_artifact_store(store), case.trinity_ref)
        (intervention,) = trinity.policy_spec.interventions
        initial = _request()
        atom = _n4_atom(trinity, initial.world_model_record, intervention)
        plan = EnginePlan(
            engine_kind="program_graph",
            objective_ref="objective://selected-opening-stock",
            program_compilation_ref=case.compile_report_ref,
            program_semantic_input_bindings_ref=bindings_ref,
            program_store=store,
            program_graph_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            program_base_state=load_state_snapshot(
                store, snapshot_ref=case.bound_state_snapshot_ref
            ),
            program_base_ref=case.bound_state_snapshot_ref,
            mechanism_registry=registry.mechanism_registry,
            slot_registry=registry.slot_registry,
            merge_registry=registry.merge_registry,
            selector_field_registry=registry.selector_field_registry,
            constraint_registry=registry.constraint_registry,
            variable_map={"opening_stock": "government_balance"},
        )
        request = initial.model_copy(
            update={
                "engine_plan": (plan,),
                "horizon": horizon,
                "intervention_atoms": (atom,),
                "selected_outcomes": ("opening_stock",),
                "baseline_state": {"opening_stock": 1000.0},
                "replications": 2,
            }
        )

        def preflight(selected_request, selected_plan, decision):
            assert selected_request is request and selected_plan is plan
            assert decision.engine_kind == "program_graph"
            selected = preflight_program_graph_inputs(store, **vars(invocation))
            assert selected.obligation_set_ref == obligation_ref
            return selected

        from polisyos.runtime.quality import n5_candidate_content as content_owner

        component_input = store.put_json(
            {"component": "generic-input", "authority": "not-established"},
            PutOptions(
                kind="runtime.quality.generic_cycle_simulation_n5_input",
                media_type="application/json",
            ),
            return_selected_profile=True,
        )
        component_successor = store.put_json(
            {"component": "semantic-successor", "authority": "not-established"},
            PutOptions(
                kind="runtime.quality.model_input_successor_selection",
                media_type="application/json",
            ),
            return_selected_profile=True,
        )
        controller = JointSimulationHorizonController()
        from polisyos.runtime.quality.acquisition_evaluation import (
            _prepare_generic_model_input_numerical_quantity,
        )

        native_preflight = preflight(request, plan, controller._select_engine(request).decision)
        quantity = _prepare_generic_model_input_numerical_quantity(
            store=store, request=request, preflight=native_preflight, controller=controller
        )
        changed_request = request.model_copy(update={"seed": request.seed + 1})
        changed_quantity = _prepare_generic_model_input_numerical_quantity(
            store=store,
            request=changed_request,
            preflight=native_preflight,
            controller=controller,
        )
        assert quantity.numerical_intent != changed_quantity.numerical_intent
        # Component control for an intermediate state after another graph node:
        # retain its real full bytes without pretending to replay prior patches.
        import jax

        from polisyos.foundry.execute import (
            prepare_program_graph_mechanism_calls,
            state_snapshot_value_projection,
        )

        base = load_state_snapshot(store, snapshot_ref=quantity.bound_state_snapshot_ref)
        intermediate = base.replace(
            agents=base.agents.replace(income=base.agents.income.at[0].add(1))
        )
        assert float(intermediate.government_balance) == float(base.government_balance)
        assert state_snapshot_value_projection(intermediate) != state_snapshot_value_projection(
            base
        )
        prepared_call = next(
            row
            for row in prepare_program_graph_mechanism_calls(
                store,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                base_state=base,
                mechanism_registry=registry.mechanism_registry,
                steps=horizon.steps(),
            )
            if row[2] == 3
        )
        for invalid_graph in (
            case.program_graph_ref.model_copy(update={"manifest_profile_sha256": None}),
            case.program_graph_ref.model_copy(
                update={"manifest_profile_sha256": "sha256:" + "0" * 64}
            ),
        ):
            with pytest.raises((FileNotFoundError, OSError, ValueError)):
                prepare_program_graph_mechanism_calls(
                    store,
                    program_ref=invalid_graph,
                    exec_plan_ref=case.exec_plan_ref,
                    base_state=base,
                    mechanism_registry=registry.mechanism_registry,
                    steps=horizon.steps(),
                )
        probe = content_owner.GenericProgramGraphN5ContentRun(
            controller=controller,
            request=request,
            input_ref=component_input,
            semantic_successor_ref=component_successor,
            store=store,
        ).observer_for_unit("f" * 64, 0)
        index, node_id, step, bound_call = prepared_call
        probe.graph_started(
            step=step, seed=step, base_state_ref=quantity.bound_state_snapshot_ref, nodes=()
        )
        probe.mechanism_started(
            step=step,
            plan_index=index,
            node_id=node_id,
            selected_call=bound_call,
            state=intermediate,
            key=jax.random.PRNGKey(3),
            target_mask=None,
        )
        assert probe.current is not None
        recorded_call = probe.current.calls[0]
        state_ref = recorded_call["state_ref"]
        assert recorded_call["state_matches_base"] is False
        assert isinstance(state_ref, ArtifactRef) and state_ref.manifest_profile_sha256 is not None
        assert state_snapshot_value_projection(
            load_state_snapshot(store, snapshot_ref=state_ref)
        ) == state_snapshot_value_projection(intermediate)
        blob_path = store._member_path(state_ref.artifact_id, "blob", None)
        held_path = blob_path.with_name(blob_path.name + ".temporarily-unavailable")
        blob_path.rename(held_path)
        try:
            with pytest.raises((FileNotFoundError, OSError, ValueError)):
                load_state_snapshot(store, snapshot_ref=state_ref)
        finally:
            held_path.rename(blob_path)
        assert state_snapshot_value_projection(
            load_state_snapshot(store, snapshot_ref=state_ref)
        ) == state_snapshot_value_projection(intermediate)
        content_scope = content_owner.GenericProgramGraphN5ContentRun(
            controller=controller,
            request=request,
            input_ref=component_input,
            semantic_successor_ref=component_successor,
            store=store,
        )
        token = content_owner._ACTIVE.set(content_scope)
        try:
            result = controller.run(request, _program_graph_input_preflight=preflight)
        finally:
            content_owner._ACTIVE.reset(token)
        result = content_owner.bind_generic_program_graph_n5_content_observation(
            result, scope=content_scope
        )
        diagnostic = content_owner.GenericProgramGraphContentObservationV1.model_validate_json(
            json.dumps(result.diagnostics[content_owner.CONTENT_OBSERVATION_KEY], allow_nan=False)
        )
        assert diagnostic.predicate_provenance == "recomputed", (
            diagnostic.reason_codes,
            tuple(
                (step.reason_codes, tuple(call.reason_codes for call in step.calls))
                for step in diagnostic.steps
            ),
            diagnostic.profile_stability,
            diagnostic.source_image_stability,
        )
        observed = content_owner.read_generic_program_graph_n5_content_observation(
            result,
            input_ref=component_input,
            semantic_successor_ref=component_successor,
            expected_request=request,
            store=store,
        )
        assert observed.predicate_provenance == "recomputed"
        assert observed.completion.status == "recomputed"
        assert len(observed.steps) == 10
        assert sum(len(step.calls) for step in observed.steps) == 4
        assert not observed.protected_use_allowed
        from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash

        for historical_profile in ("foundry-bound-call-content/1", "foundry-bound-call-content/2"):
            historical_payload = copy.deepcopy(result.content_bound_payload())
            historical_observation = historical_payload["diagnostics"][
                content_owner.CONTENT_OBSERVATION_KEY
            ]
            historical_observation["call_normalization_profile"] = historical_profile
            historical_observation["content_hash"] = exact_n5_content_hash(
                {
                    key: value
                    for key, value in historical_observation.items()
                    if key != "content_hash"
                }
            )
            historical_receipt = horizon_owner.build_content_bound_simulation_receipt(
                engine_kind=result.receipt.engine_kind,
                payload=historical_payload,
                diagnostics=historical_payload["diagnostics"],
            )
            historical_result = JointSimulationResult.model_validate(
                {**historical_payload, "receipt": historical_receipt.model_dump(mode="json")}
            )
            historical_result._content_payload = historical_payload
            assert horizon_owner.semantic_program_graph_result_inputs(
                historical_result
            ) == horizon_owner.semantic_program_graph_result_inputs(result)
            with pytest.raises(ValueError, match="generic_program_graph_content_not_established"):
                content_owner.read_generic_program_graph_n5_content_observation(
                    historical_result,
                    input_ref=component_input,
                    semantic_successor_ref=component_successor,
                    expected_request=request,
                    store=store,
                )

        # A rehashed receipt cannot default a missing wire profile to the
        # current normalizer. The original observation hash is deliberately
        # retained: default insertion previously made it appear valid.
        missing_profile_payload = copy.deepcopy(result.content_bound_payload())
        del missing_profile_payload["diagnostics"][content_owner.CONTENT_OBSERVATION_KEY][
            "call_normalization_profile"
        ]
        missing_profile_receipt = horizon_owner.build_content_bound_simulation_receipt(
            engine_kind=result.receipt.engine_kind,
            payload=missing_profile_payload,
            diagnostics=missing_profile_payload["diagnostics"],
        )
        missing_profile_result = JointSimulationResult.model_validate(
            {**missing_profile_payload, "receipt": missing_profile_receipt.model_dump(mode="json")}
        )
        missing_profile_result._content_payload = missing_profile_payload
        with pytest.raises(ValueError, match="call_normalization_profile"):
            content_owner.read_generic_program_graph_n5_content_observation(
                missing_profile_result,
                input_ref=component_input,
                semantic_successor_ref=component_successor,
                expected_request=request,
                store=store,
            )

        # Rehashing the outer result cannot turn an incomplete physical trace
        # into the original producer's complete call census.
        incomplete_payload = copy.deepcopy(result.content_bound_payload())
        incomplete_observation = incomplete_payload["diagnostics"][
            content_owner.CONTENT_OBSERVATION_KEY
        ]
        incomplete_observation["steps"] = incomplete_observation["steps"][:-1]
        incomplete_observation["content_hash"] = exact_n5_content_hash(
            {key: value for key, value in incomplete_observation.items() if key != "content_hash"}
        )
        incomplete_receipt = horizon_owner.build_content_bound_simulation_receipt(
            engine_kind=result.receipt.engine_kind,
            payload=incomplete_payload,
            diagnostics=incomplete_payload["diagnostics"],
        )
        incomplete_result = JointSimulationResult.model_validate(
            {**incomplete_payload, "receipt": incomplete_receipt.model_dump(mode="json")}
        )
        incomplete_result._content_payload = incomplete_payload
        with pytest.raises(ValueError, match="generic_program_graph_content_step_census_mismatch"):
            content_owner.read_generic_program_graph_n5_content_observation(
                incomplete_result,
                input_ref=component_input,
                semantic_successor_ref=component_successor,
                expected_request=request,
                store=store,
            )
        prepared_calls = {
            (index, node_id, step): content.hex()
            for index, node_id, step, content in quantity.prepared_calls
        }
        for observed_step in observed.steps:
            actual_calls = {
                (call.plan_index, call.node_id, observed_step.step): call.callable_receiver_hex
                for call in observed_step.calls
            }
            assert actual_calls == {
                key: value for key, value in prepared_calls.items() if key[2] == observed_step.step
            }
        foreign_input = component_input.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "0" * 64}
        )
        with pytest.raises((FileNotFoundError, ValueError)):
            content_owner.read_generic_program_graph_n5_content_observation(
                result,
                input_ref=foreign_input,
                semantic_successor_ref=component_successor,
                expected_request=request,
                store=store,
            )
        assert len(result.physical_work_observations) == 2
        assert {work.status for work in result.physical_work_observations} == {"completed"}
        assert {trajectory.run_level for trajectory in result.trajectories} == {
            "individual",
            "joint",
        }
        for trajectory in result.trajectories:
            assert [point.outcomes["opening_stock"] for point in trajectory.points] == [
                1000.0,
                1000.0,
                1000.0,
                962.5,
                920.3125,
            ]
        edges = horizon_owner.semantic_program_graph_result_inputs(result)
        assert len(edges) == 14  # Ten step chains and four observed call-state snapshots.
        assert all(edge.manifest_profile_sha256 is not None for edge in edges)
        persisted = persist_joint_simulation_result(result, store=store)
        fresh = FileSystemCAS(case.store_root)
        reopened = load_joint_simulation_result(persisted, store=fresh, expected_request=request)
        assert horizon_owner.semantic_program_graph_result_inputs(reopened) == edges
        with pytest.raises(
            GenerationCycleError, match="joint_simulation_semantic_expected_request_required"
        ):
            load_joint_simulation_result(persisted, store=fresh)

        # N8 must not turn the same useful numerical artifact into a
        # conditional value until its generic V3 owner join supplies the
        # exact selected request. This fixture intentionally has no generic
        # owner references, so the semantic reader must fail closed.
        from types import SimpleNamespace

        from polisyos.runtime.quality import generation_cycle
        from polisyos.runtime.quality.generation_cycle import (
            SimulationPortObservation,
            _conditional_simulation_value_observation,
        )
        from polisyos.runtime.quality.generic_simulation_admission import GenericN5ResolvedResult

        candidate = SimpleNamespace(
            candidate_id="candidate_semantic_program_graph",
            atom=atom,
            intervention_atoms=(atom,),
        )
        simulation = SimulationPortObservation(
            candidate_id=candidate.candidate_id,
            status="joint_simulated",
            simulation_ref=result.receipt.payload_hash,
            simulation_result_ref=persisted,
            authority_blockers=tuple(
                result.promotion_ready_value_packet.get("authority_blockers", ())
            ),
            k_world_ref_before=request.world_model_record.content_hash,
            k_world_ref_after=request.world_model_record.content_hash,
            world_model_record=request.world_model_record,
        )
        problem = SimpleNamespace(
            outcome_of_interest=SimpleNamespace(target_variable="opening_stock")
        )
        n8 = _conditional_simulation_value_observation(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            artifact_store=fresh,
            cycle_index=0,
        )
        assert n8 is not None
        assert n8.status == "value_blocked"
        assert n8.authority_blockers == ("joint_simulation_semantic_expected_request_required",)
        assert n8.value_receipt is None
        assert n8.method_selection_receipt is None

        # Exercise the downstream receipt comparison in isolation. The
        # numerical result is real; the owner handoff is supplied here so the
        # earlier missing-owner guard does not mask the stale receipt.
        with monkeypatch.context() as consumer:
            consumer.setattr(
                generation_cycle,
                "_replay_generic_n5_observation",
                lambda **_: (None, GenericN5ResolvedResult(result=reopened, request=request)),
            )
            stale_observation = simulation.model_copy(
                update={"simulation_ref": "sha256:" + "f" * 64}
            )
            n8 = _conditional_simulation_value_observation(
                candidate=candidate,
                simulation=stale_observation,
                problem=problem,
                artifact_store=fresh,
                cycle_index=0,
            )
        assert n8 is not None
        assert n8.status == "value_blocked"
        assert n8.authority_blockers == ("joint_simulation_result_integrity_invalid",)
        assert "receipt_payload_hash_binding_mismatch" in n8.reason

        manifest = store.get_manifest(persisted)
        broken = store.put_bytes(
            store.get_bytes(persisted),
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                canon=manifest.canon,
                inputs=[edge for edge in manifest.inputs if edge != edges[-1]],
            ),
            return_selected_profile=True,
        )
        assert broken.artifact_id == persisted.artifact_id
        assert broken.manifest_profile_sha256 != persisted.manifest_profile_sha256
        with pytest.raises(
            GenerationCycleError, match="semantic_program_graph_result_sources_invalid"
        ):
            load_joint_simulation_result(broken, store=fresh, expected_request=request)

        forged = copy.deepcopy(result.content_bound_payload())
        for trajectory in forged["trajectories"]:
            point = trajectory["points"][-1]
            point["outcomes"]["opening_stock"] += 1
            point["effect"]["opening_stock"] += 1
            for sample in point["replication_sampling"]["samples"]:
                sample["outcomes"]["opening_stock"] += 1
                sample["effects"]["opening_stock"] += 1

        def persist_rehashed(payload):
            payload["receipt"] = build_content_bound_simulation_receipt(
                engine_kind=result.receipt.engine_kind,
                payload=payload,
                diagnostics=payload["diagnostics"],
            ).model_dump(mode="json")
            return store.put_json(
                payload,
                PutOptions(
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    schema=manifest.artifact_schema,
                    inputs=manifest.inputs,
                ),
                canon_spec=horizon_owner.CanonSpec(forbid_floats=False, forbid_nan_inf=True),
                return_selected_profile=True,
            )

        forged_ref = persist_rehashed(forged)
        with pytest.raises(
            GenerationCycleError, match="joint_simulation_semantic_expected_request_required"
        ):
            load_joint_simulation_result(forged_ref, store=fresh)
        with pytest.raises(
            GenerationCycleError, match="semantic_program_graph_result_sources_invalid"
        ) as projected:
            load_joint_simulation_result(forged_ref, store=fresh, expected_request=request)
        assert str(projected.value.__cause__) == (
            "semantic_program_graph_result_projection_mismatch"
        )

        actual_step = (
            result.trajectories[0].semantic_program_graph_replications[1].step_result_refs[-1]
        )
        step_manifest = store.get_manifest(actual_step)
        alternate_step = store.put_bytes(
            store.get_bytes(actual_step),
            PutOptions(
                kind=step_manifest.kind,
                media_type=step_manifest.media_type,
                schema=step_manifest.artifact_schema,
                canon=step_manifest.canon,
                inputs=step_manifest.inputs,
                warnings=[WarningRecord(code="test.alternate_step", msg="Same step bytes")],
            ),
            return_selected_profile=True,
        )
        assert alternate_step.artifact_id == actual_step.artifact_id
        assert alternate_step.manifest_profile_sha256 != actual_step.manifest_profile_sha256
        grafted = copy.deepcopy(result.content_bound_payload())
        point = grafted["trajectories"][0]["points"][-1]
        alternate_ref = alternate_step.model_dump(mode="json")
        point["replication_sampling"]["samples"][1]["engine_state"]["simulation_result_ref"] = (
            alternate_ref
        )
        point["engine_state"]["replication_engine_states"][1]["simulation_result_ref"] = (
            alternate_ref
        )
        with pytest.raises(
            GenerationCycleError, match="semantic_program_graph_result_sources_invalid"
        ) as graft:
            load_joint_simulation_result(
                persist_rehashed(grafted), store=fresh, expected_request=request
            )
        assert str(graft.value.__cause__) == (
            "semantic_program_graph_result_projection_locator_mismatch"
        )

        reader = store.get_raw_manifest_bytes

        def missing_correspondence(ref, *args, **kwargs):
            if getattr(ref, "artifact_id", None) == correspondence_ref.artifact_id:
                raise FileNotFoundError("selected source correspondence removed")
            return reader(ref, *args, **kwargs)

        def unexpected_reservation(*args, **kwargs):
            pytest.fail("missing semantic proof reached the physical reservation boundary")

        with monkeypatch.context() as scope:
            scope.setattr(store, "get_raw_manifest_bytes", missing_correspondence)
            scope.setattr(horizon_owner, "_run_cached_replicates", unexpected_reservation)
            with pytest.raises(
                horizon_owner.JointSimulationControllerError,
                match="program_graph_semantic_horizon_intake_not_established",
            ) as refusal:
                controller.run(request, _program_graph_input_preflight=preflight)
            assert "semantic_correspondence_missing" in refusal.value.context["reason"]
    finally:
        case.close()


def test_rejected_program_graph_does_not_create_input_obligations_before_fallback() -> None:
    """An ineligible graph cannot emit obligations when a later engine is selected."""
    request = _request().model_copy(
        update={
            "engine_plan": (
                EnginePlan(
                    engine_kind="program_graph",
                    objective_ref="objective://rejected-program-graph",
                    eligibility_conditions=("cyclic",),
                ),
                _request().engine_plan[0],
            ),
            "horizon": HorizonSpec(start=0, end=0, step=1),
        }
    )
    callback_calls: list[str] = []

    def selected_input_preflight(*_args: Any) -> Any:
        callback_calls.append("called")
        raise AssertionError("preflight must follow actual engine selection")

    result = JointSimulationHorizonController().run(
        request,
        _program_graph_input_preflight=selected_input_preflight,
    )

    assert [item.engine_kind for item in result.engine_decisions] == [
        "program_graph",
        "ncm_parallel_worlds",
    ]
    assert [item.decision for item in result.engine_decisions] == ["unsupported", "selected"]
    assert callback_calls == []


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
        [1650.0, 1815.0, 1996.5, 2196.15]
    )
    assert abs(result.interaction_terms[0].by_step[3]) > 1.0
    verify_simulation_receipt(result.receipt, result.content_bound_payload())


def test_program_graph_horizon_preserves_one_complete_method_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import ValidationError

    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.artifacts.environment import (
        CPUInfo,
        EnvironmentManifest,
        GPUInfo,
        JAXInfo,
        OSInfo,
        PythonInfo,
    )
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
    from polisyos.core.contracts.foundry import (
        MethodExecutionBundle,
        MethodExecutionBundleRef,
        MethodMetricBinding,
        MethodMetricBindingSet,
        MethodMetricBindingSetRef,
        StateDelta,
        StateSnapshot,
        StateSnapshotRef,
    )
    from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
    from polisyos.foundry.methods.base import (
        ComplexityClass,
        ComputeBackend,
        FidelityLevel,
        MethodMetadata,
        MethodSignature,
        SlotSpec,
        SlotType,
        Unit,
    )
    from polisyos.foundry.methods.registry import MethodRegistry as GraphMethodRegistry
    from polisyos.ir.kernel.method_metrics import (
        MethodMetricSourceUnit,
        registered_method_metric_law_metadata,
        registered_method_metric_unit_adapter_metadata,
    )
    from polisyos.ir.kernel.units import RateUnit
    from polisyos.runtime.quality.joint_simulation_horizon import (
        MethodMetricHorizonFailureCapture,
        MethodMetricHorizonFailureOccurrence,
    )

    class _HorizonCaptureMethod:
        signature: ClassVar[MethodSignature] = MethodSignature(
            name="capture_scalar",
            namespace="tests.horizon_method_capture",
            version="1.0.0",
            input_slots=frozenset(),
            output_slots=frozenset(
                {
                    SlotSpec(
                        name="result",
                        slot_type=SlotType.SCALAR,
                        unit=Unit(dimension="ratio", symbol="ratio"),
                    )
                }
            ),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_1,
            backend=ComputeBackend.NUMPY,
            supports_jit=False,
            supports_vmap=False,
            supports_grad=False,
        )
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description="Horizon capture test method"
        )

        @staticmethod
        def pure_step(state: object, params: object) -> dict[str, float]:
            return {"result": 0.25}

    store = FileSystemCAS(tmp_path / "cas")

    def put_json(payload: object, *, kind: str, schema_name: str, version: str) -> ArtifactRef:
        return store.put_json(
            payload,
            PutOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version=version),
            ),
            return_selected_profile=True,
        )

    policy_ref = put_json(
        {"candidate": "horizon-method-capture"},
        kind="ir.trinity_bundle",
        schema_name="test.horizon_policy",
        version="1.0",
    )
    registry_ref = put_json(
        {"registry": "horizon-test"},
        kind="core.registry_bundle",
        schema_name="test.horizon_registry",
        version="1.0",
    )
    metric_registry_ref = put_json(
        {"metrics": "horizon-test"},
        kind="ir.metric_registry",
        schema_name="test.horizon_metrics",
        version="1.0",
    )
    units_registry_ref = put_json(
        {"units": "horizon-test"},
        kind="ir.units_registry",
        schema_name="test.horizon_units",
        version="1.0",
    )
    lowered_ref = store.put_json(
        LoweredIR(ir_ref=policy_ref, mechanisms=[], constraints=[]),
        PutOptions(
            kind="foundry.lowered_ir",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.LoweredIR", version="0.2"),
        ),
        return_selected_profile=True,
    )
    signature = _HorizonCaptureMethod.signature
    method_build_digest = (
        "sha256:"
        + hashlib.sha256(inspect.getsource(_HorizonCaptureMethod).encode("utf-8")).hexdigest()
    )
    graph_ref = store.put_json(
        ProgramGraph(
            ir_ref=policy_ref,
            lowered_ir_ref=LoweredIRRef.model_validate(lowered_ref.model_dump(mode="python")),
            nodes=[
                ProgramNode(
                    node_id="capture_method",
                    node_kind="method",
                    method_fqn=signature.fqn,
                    method_version=signature.version,
                )
            ],
            edges=[],
            entrypoints=["capture_method"],
        ),
        PutOptions(
            kind="foundry.program_graph",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.2.0"),
            inputs=[input_ref_from_artifact_ref(lowered_ref, role="lowered_ir")],
        ),
        return_selected_profile=True,
    )
    typed_graph_ref = ProgramGraphRef.model_validate(graph_ref.model_dump(mode="python"))
    law_id, law_version, law_digest = registered_method_metric_law_metadata()
    adapter_id, adapter_version, adapter_digest = registered_method_metric_unit_adapter_metadata()
    binding = MethodMetricBinding(
        binding_id="binding.horizon_capture_scalar",
        objective_id="objective.horizon_capture_scalar",
        metric_id="metric.horizon_capture_scalar",
        node_id="capture_method",
        method_fqn=signature.fqn,
        method_version=signature.version,
        method_abi_digest=signature.abi_digest(),
        method_abi_digest_algorithm="blake2b",
        method_build_digest=method_build_digest,
        method_build_digest_scope="class_source_only",
        output_slot_id="result",
        output_shape="scalar",
        source_unit=MethodMetricSourceUnit(dimension="ratio", symbol="ratio", scale=1),
        target_unit=RateUnit(base="ratio"),
        law_id=law_id,
        law_version=law_version,
        law_code_digest=law_digest,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        adapter_code_digest=adapter_digest,
        conversion_operation="unsupported",
        availability="unavailable",
        limitation="capture_test_does_not_assert_method_metric_law",
    )
    binding_set_ref = store.put_json(
        MethodMetricBindingSet(
            program_graph_ref=typed_graph_ref,
            policy_ref=policy_ref,
            registry_bundle_ref=registry_ref,
            metric_registry_ref=metric_registry_ref,
            units_registry_ref=units_registry_ref,
            bindings=[binding],
        ),
        PutOptions(
            kind=MethodMetricBindingSet.ARTIFACT_KIND,
            media_type=MethodMetricBindingSet.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MethodMetricBindingSet.ARTIFACT_SCHEMA_NAME,
                version=MethodMetricBindingSet.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                input_ref_from_artifact_ref(typed_graph_ref, role="program_graph"),
                input_ref_from_artifact_ref(policy_ref, role="policy"),
                input_ref_from_artifact_ref(registry_ref, role="registry_bundle"),
                input_ref_from_artifact_ref(metric_registry_ref, role="metric_registry"),
                input_ref_from_artifact_ref(units_registry_ref, role="units_registry"),
            ],
        ),
        return_selected_profile=True,
    )
    typed_binding_set_ref = MethodMetricBindingSetRef.model_validate(
        binding_set_ref.model_dump(mode="python")
    )
    exec_plan_ref = store.put_json(
        ExecPlan(program_ref=typed_graph_ref, order=["capture_method"]),
        PutOptions(
            kind="foundry.exec_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecPlan", version="0.2.0"),
            inputs=[
                input_ref_from_artifact_ref(typed_graph_ref, role="program_graph"),
                input_ref_from_artifact_ref(
                    typed_binding_set_ref,
                    role="method_metric_bindings",
                ),
            ],
        ),
        return_selected_profile=True,
    )
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    base_state = base_state.replace(
        agents=base_state.agents.replace(
            income=np.asarray([10.0, 20.0], dtype=np.float64),
        )
    )
    base_ref = put_state_snapshot(
        store,
        state=base_state,
        step=0,
        return_selected_profile=True,
    )
    GraphMethodRegistry.get_instance().register(_HorizonCaptureMethod, override=True)
    monkeypatch.setattr(
        "polisyos.foundry.execute._internal.graph.capture_environment",
        lambda **_kwargs: EnvironmentManifest(
            cpu=CPUInfo(architecture="test", model_name="test-cpu", core_count=1, thread_count=1),
            gpu=GPUInfo(),
            os=OSInfo(system="test", release="1", version="test-os"),
            python=PythonInfo(version="3.12.0", implementation="CPython", compiler="test"),
            jax=JAXInfo(),
        ),
    )
    plan = EnginePlan(
        engine_kind="program_graph",
        objective_ref="objective://horizon-method-capture",
        eligibility_conditions=("acyclic", "state_transition"),
        variable_map={"mean_income": "agents.income"},
        program_store=store,
        program_graph_ref=typed_graph_ref,
        exec_plan_ref=exec_plan_ref,
        program_base_state=base_state,
        program_base_ref=base_ref,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        constraint_registry=ConstraintRegistry(constraints={}),
        outcome_aggregations={"mean_income": {"method": "mean", "unit": "usd"}},
    )
    request = _request().model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=1, step=1),
            "engine_plan": (plan,),
            "selected_outcomes": ("mean_income",),
            "baseline_state": {"mean_income": 0.0},
        }
    )

    try:
        result = JointSimulationHorizonController().run(request)
        joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
        rows = [point.engine_state["method_execution"] for point in joint.points]
        assert [row["status"] for row in rows] == ["captured", "captured"]
        assert all("simulation_result_ref" not in row for row in rows)
        assert all(
            row["method_metric_binding_set_ref"] == rows[0]["method_metric_binding_set_ref"]
            for row in rows
        )
        assert all(
            row["method_execution_bundle_ref"] == rows[0]["method_execution_bundle_ref"]
            for row in rows
        )
        assert all(row["method_execution_bundle_ref"]["manifest_profile_sha256"] for row in rows)
        state_delta = validate_core_model_json_artifact(
            StateDelta,
            store,
            joint.points[0].engine_state["state_delta_ref"],
        )
        assert isinstance(state_delta.base_ref, StateSnapshotRef)
        assert state_delta.base_ref.manifest_profile_sha256 is not None
        occurrence_ids = [item["occurrence_id"] for row in rows for item in row["occurrences"]]
        assert len(occurrence_ids) == len(set(occurrence_ids)) == 2
        bundle = validate_core_model_json_artifact(
            MethodExecutionBundle,
            store,
            ArtifactRef.model_validate(rows[0]["method_execution_bundle_ref"]),
        )
        assert len(bundle.occurrences) == 2
        assert all(
            item.dispatch is not None
            and item.dispatch.input_state_status == "not_established"
            and item.dispatch.input_state_ref is None
            and item.dispatch.input_state_limitation
            for item in bundle.occurrences
        )
        assert {item.invocation_id for item in bundle.occurrences} == {
            "graph-invocation.000001",
            "graph-invocation.000002",
        }
        assert [
            source["occurrence_ids"] for source in joint.diagnostics["method_execution_sources"]
        ] == [[item] for item in occurrence_ids]
        verify_simulation_receipt(result.receipt, result.content_bound_payload())

        def fail_dispatch(_state: object, _params: object) -> dict[str, float]:
            raise ValueError("horizon method failure witness")

        monkeypatch.setattr(_HorizonCaptureMethod, "pure_step", staticmethod(fail_dispatch))
        failed_result = JointSimulationHorizonController().run(request)
        assert failed_result.trajectories == ()
        assert failed_result.diagnostics["engine_run_claimed"] is False
        assert failed_result.diagnostics["physical_work_interruption"] == "n5_physical_work_failed"
        failed_work = failed_result.physical_work_observations
        assert len(failed_work) == failed_result.diagnostics["physical_work_units"] == 1
        assert failed_work[0].status == "failed"
        assert failed_work[0].error_type == "MethodExecutionAbortError"
        failure_capture = MethodMetricHorizonFailureCapture.model_validate(
            failed_result.diagnostics["method_metric_horizon_failure_capture"]
        )
        assert failure_capture.status == "failed"
        assert failure_capture.step == 0
        assert failure_capture.physical_work_event_id == failed_work[0].event_id
        assert failure_capture.step_source.step == failure_capture.step
        assert failure_capture.step_source.source_status == "failed"
        failed_bundle = validate_core_model_json_artifact(
            MethodExecutionBundle,
            store,
            MethodExecutionBundleRef.model_validate(
                failure_capture.method_execution_bundle_ref.model_dump(mode="python")
            ),
        )
        assert failed_bundle.method_metric_binding_set_ref.model_dump(
            mode="json"
        ) == failure_capture.method_metric_binding_set_ref.model_dump(mode="json")
        assert failed_bundle.program_graph_ref.model_dump(
            mode="json"
        ) == typed_graph_ref.model_dump(mode="json")
        assert failed_bundle.exec_plan_ref.model_dump(mode="json") == exec_plan_ref.model_dump(
            mode="json"
        )
        bundle_manifest = store.get_manifest(failure_capture.method_execution_bundle_ref)
        bundle_edges = {edge.role: edge for edge in bundle_manifest.inputs}
        assert bundle_edges["program_graph"] == input_ref_from_artifact_ref(
            failed_bundle.program_graph_ref,
            role="program_graph",
        )
        assert bundle_edges["exec_plan"] == input_ref_from_artifact_ref(
            failed_bundle.exec_plan_ref,
            role="exec_plan",
        )
        assert bundle_edges["method_metric_binding_set"] == input_ref_from_artifact_ref(
            failed_bundle.method_metric_binding_set_ref,
            role="method_metric_binding_set",
        )
        prestate_ref = failure_capture.step_source.prestate_ref
        prestate_snapshot = validate_core_model_json_artifact(StateSnapshot, store, prestate_ref)
        assert prestate_snapshot.step == failure_capture.step
        loaded_prestate = load_state_snapshot(store, snapshot_ref=prestate_ref)
        assert np.array_equal(loaded_prestate.agents.income, base_state.agents.income)
        assert len(failed_bundle.occurrences) == 1
        failed_occurrence = failed_bundle.occurrences[0]
        assert failed_occurrence.status == "failed"
        assert failed_occurrence.dispatch is not None
        assert failed_occurrence.dispatch.input_state_status == "not_established"
        assert failed_occurrence.dispatch.input_state_ref is None
        assert failure_capture.step_source.occurrence_ids == (failed_occurrence.occurrence_id,)
        assert failure_capture.occurrences == (
            MethodMetricHorizonFailureOccurrence(
                occurrence_id=failed_occurrence.occurrence_id,
                invocation_id=failed_occurrence.invocation_id,
                node_id=failed_occurrence.node_id,
                status=failed_occurrence.status,
            ),
        )
        relabeled_step = failure_capture.model_dump(mode="json")
        relabeled_step["step"] = failure_capture.step + 1
        with pytest.raises(ValidationError):
            MethodMetricHorizonFailureCapture.model_validate(relabeled_step)
        mismatched_occurrence = failure_capture.model_dump(mode="json")
        mismatched_occurrence["step_source"]["occurrence_ids"] = [
            failed_occurrence.occurrence_id + ":relabelled"
        ]
        with pytest.raises(ValidationError):
            MethodMetricHorizonFailureCapture.model_validate(mismatched_occurrence)
        assert failed_occurrence.dispatch is not None
        assert failed_occurrence.dispatch.outcome == "failed"
        assert failed_occurrence.dispatch.backend_trace_status == "not_established"
        assert failed_occurrence.dispatch.backend_attempts == ()
        assert failed_occurrence.dispatch.actual_backend is None
        assert failed_occurrence.dispatch.backend_identity_status == "not_established"
        assert failed_occurrence.dispatch.fallback_status == "not_established"
        assert failed_occurrence.dispatch.seed_status == "not_established"
        assert failed_occurrence.dispatch.rng_state_status == "runner_rng_state_not_retained"
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def _alternate_manifest_profile(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    version: str,
    source_store: FileSystemCAS | None = None,
) -> ArtifactRef:
    source_store = source_store or store
    manifest = source_store.get_manifest(ref)
    return store.put_bytes(
        source_store.get_bytes(ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=ProducerInfo(component="test.foundry.program_graph", version=version),
            env=manifest.env,
            inputs=manifest.inputs,
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        ),
    )


def test_served_program_graph_refuses_foreign_selected_manifest_profile(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cas"
    owner_store = FileSystemCAS(root).for_tenant("tenant-owner")
    foreign_store = FileSystemCAS(root).for_tenant("tenant-foreign")
    plan = _program_graph_plan(tmp_path, store=owner_store)

    foreign_program_ref = _alternate_manifest_profile(
        foreign_store,
        plan.program_graph_ref,
        version="2.0.0",
        source_store=owner_store,
    )
    foreign_exec_plan_ref = _alternate_manifest_profile(
        foreign_store,
        plan.exec_plan_ref,
        version="2.0.0",
        source_store=owner_store,
    )
    assert foreign_program_ref.artifact_id == plan.program_graph_ref.artifact_id
    assert foreign_exec_plan_ref.artifact_id == plan.exec_plan_ref.artifact_id
    assert foreign_program_ref.manifest_profile_sha256 is not None
    assert foreign_exec_plan_ref.manifest_profile_sha256 is not None
    assert owner_store.get_bytes(plan.program_graph_ref) == foreign_store.get_bytes(
        foreign_program_ref
    )
    assert owner_store.get_bytes(plan.exec_plan_ref) == foreign_store.get_bytes(
        foreign_exec_plan_ref
    )
    assert (
        owner_store.get_manifest(plan.program_graph_ref).producer
        != foreign_store.get_manifest(foreign_program_ref).producer
    )

    foreign_plan = plan.model_copy(
        update={
            "program_graph_ref": foreign_program_ref,
            "exec_plan_ref": foreign_exec_plan_ref,
        }
    )
    request = _request().model_copy(
        update={
            "engine_plan": (foreign_plan,),
            "selected_outcomes": ("mean_income",),
            "baseline_state": {"mean_income": 0.0},
        }
    )

    with pytest.raises(ArtifactOwnershipError):
        JointSimulationHorizonController().run(request)


def test_served_program_graph_output_lineage_keeps_selected_manifest_profiles(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-owner")
    plan = _program_graph_plan(tmp_path, store=store)
    selected_program_ref = _alternate_manifest_profile(
        store, plan.program_graph_ref, version="2.0.0"
    )
    selected_exec_plan_ref = _alternate_manifest_profile(store, plan.exec_plan_ref, version="2.0.0")
    selected_plan = plan.model_copy(
        update={
            "program_graph_ref": selected_program_ref,
            "exec_plan_ref": selected_exec_plan_ref,
        }
    )
    request = _request().model_copy(
        update={
            "engine_plan": (selected_plan,),
            "selected_outcomes": ("mean_income",),
            "baseline_state": {"mean_income": 0.0},
        }
    )

    result = JointSimulationHorizonController().run(request)

    trajectory = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    state_delta_id = trajectory.points[0].engine_state["state_delta_ref"]
    state_delta_manifest = store.get_manifest(state_delta_id)
    selected_inputs = {
        item.role: item.manifest_profile_sha256 for item in state_delta_manifest.inputs
    }
    assert selected_inputs["program_graph"] == selected_program_ref.manifest_profile_sha256
    assert selected_inputs["exec_plan"] == selected_exec_plan_ref.manifest_profile_sha256


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
    distinct_states = {tuple(point.engine_state["stock_values"]) for point in joint.points}
    assert len(distinct_states) >= 2
    assert joint.points[-1].outcomes == pytest.approx({"stock0": 11.9, "stock1": 8.1})
    assert result.interaction_terms[0].by_step[2] == pytest.approx(1.9)


def test_method_registry_estimator_selects_registered_dynamic_method_without_engine_branch() -> (
    None
):
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
    assert [point.outcomes["stock1"] for point in joint.points] == pytest.approx([0.0, 4.0, 8.1])


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
    request = _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})
    result = JointSimulationHorizonController().run(request)
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


def test_n5_abm_strangle_probe_censuses_every_production_stub_caller() -> None:
    from tools.quality.validation.check_layer3_gy_joint_simulation_horizon_contract import (
        _abm_stub_strangle_probe,
        _validate_abm_stub_strangle,
    )

    probe = _abm_stub_strangle_probe()

    assert probe["production_stub_callers"] == []
    assert probe["content_bound_without_diagnostic_limited"] is True
    assert probe["persisted_diagnostic_content_bound"] is True
    assert probe["diagnostic_authority_not_established"] is True
    assert _validate_abm_stub_strangle(probe) == []
    mutated = {**probe, "production_stub_callers": ["simulation/coupled.py:140"]}
    assert "abm_production_stub_caller_present" in {
        issue["code"] for issue in _validate_abm_stub_strangle(mutated)
    }
    unattached = {**probe, "persisted_diagnostic_content_bound": False}
    assert "abm_persisted_diagnostic_binding_missing" in {
        issue["code"] for issue in _validate_abm_stub_strangle(unattached)
    }
    promoted = {**probe, "diagnostic_authority_not_established": False}
    assert "abm_diagnostic_authority_limit_missing" in {
        issue["code"] for issue in _validate_abm_stub_strangle(promoted)
    }


def test_n5_rederive_audit_validates_live_payload_without_frozen_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.quality.validation import (
        check_layer3_gy_joint_simulation_horizon_contract as contract,
    )

    runner = getattr(contract, "rederive_audit", None)
    assert callable(runner), "N5 live rederive lane is missing"
    live = {"schema_version": contract.SCHEMA_VERSION, "behavioral_mutations": []}
    monkeypatch.setattr(contract, "build_live_payload", lambda _root: live)
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda payload: {"status": "pass", "issues": []}
        if payload is live
        else {"status": "fail", "issues": [{"code": "wrong_payload"}]},
    )

    assert runner(Path.cwd()) == {"status": "pass", "issues": []}


def test_n5_expected_qa_reference_reconciles_fresh_v5_results_and_refuses_tampering(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from tools.quality.validation import (
        check_layer3_gy_joint_simulation_horizon_contract as contract,
    )

    repo_root = Path(__file__).resolve().parents[4]
    reference_path = tmp_path / "expected-qa-reference.json"
    monkeypatch.setattr(contract, "OUTPUT_PATH", reference_path)

    live_builder = contract.build_live_payload
    first_live = live_builder(repo_root)
    assert contract.validate_payload(first_live) == {"status": "pass", "issues": []}
    monkeypatch.setattr(contract, "build_live_payload", lambda _root: first_live)
    assert contract.write(repo_root) == {"status": "pass", "issues": []}
    reference = json.loads(reference_path.read_text(encoding="utf-8"))

    assert reference["schema_version"] == contract.EXPECTED_QA_REFERENCE_SCHEMA_VERSION
    assert reference["authority_purpose"] == "expected_qa_contract_only"
    assert "source_identity_not_asserted" in reference["limitations"]
    assert reference["contract"]["behavioral_mutations"] == first_live["behavioral_mutations"]
    expected_gate = reference["contract"]["positive_gate"]["dynamic_horizon"]
    assert "n5_diagnostic_freshness_json" in expected_gate
    assert "trajectories" not in expected_gate
    assert "receipt_payload_hash" not in expected_gate
    assert "interaction_terms" not in expected_gate
    assert '"str":"interaction_terms"' in expected_gate["n5_diagnostic_freshness_json"]
    assert (
        '"str":"policyos.runtime.n5_diagnostic_freshness.v1"'
        in expected_gate["n5_diagnostic_freshness_json"]
    )
    assert '"str":"expected_qa_contract_only"' in expected_gate["n5_diagnostic_freshness_json"]
    assert '"str":"protected_use_not_permitted"' in expected_gate["n5_diagnostic_freshness_json"]
    typed_result, _, typed_issue = contract._typed_v5_result_wire(
        first_live["positive_gate"]["dynamic_horizon"]
    )
    assert typed_issue is None
    assert typed_result is not None and typed_result.interaction_terms
    from polisyos.runtime.quality.n5_replay_numerical_projection import (
        project_n5_diagnostic_freshness_bytes,
    )

    assert expected_gate["n5_diagnostic_freshness_json"] == (
        project_n5_diagnostic_freshness_bytes(typed_result).decode("utf-8")
    )
    coupled_summary = reference["contract"]["positive_gate"]["coupling_gate"][
        "supported_coupled_des_abm"
    ]
    assert "receipt" not in coupled_summary
    coupled_result_gate = coupled_summary["result"]
    assert "n5_diagnostic_freshness_json" in coupled_result_gate
    coupled_typed_result, _, coupled_typed_issue = contract._typed_v5_result_wire(
        first_live["positive_gate"]["coupling_gate"]["supported_coupled_des_abm"]["result"]
    )
    assert coupled_typed_issue is None
    assert coupled_typed_result is not None
    assert coupled_result_gate["n5_diagnostic_freshness_json"] == (
        project_n5_diagnostic_freshness_bytes(coupled_typed_result).decode("utf-8")
    )

    # The second producer run creates fresh physical IDs and CAS receipts. The reference should
    # still match because the canonical owner validates those joins and marks only its declared
    # identity/time fields as not compared.
    monkeypatch.setattr(contract, "build_live_payload", live_builder)
    expected_builder = contract._expected_qa_reference
    fresh_references: list[dict[str, Any]] = []

    def _capture_expected_reference(payload: dict[str, Any]) -> dict[str, Any]:
        expected = expected_builder(payload)
        fresh_references.append(expected)
        return expected

    monkeypatch.setattr(contract, "_expected_qa_reference", _capture_expected_reference)

    def _first_changed_path(left: Any, right: Any, path: str = "", depth: int = 0) -> str | None:
        if type(left) is not type(right):
            return path or "$"
        if depth >= 12:
            return None if left == right else path or "$"
        if isinstance(left, dict):
            for key in sorted(set(left) | set(right)):
                child_path = f"{path}.{key}" if path else str(key)
                if key not in left or key not in right:
                    return child_path
                changed_path = _first_changed_path(left[key], right[key], child_path, depth + 1)
                if changed_path is not None:
                    return changed_path
            return None
        if isinstance(left, list):
            if len(left) != len(right):
                return f"{path}.length" if path else "$.length"
            for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
                changed_path = _first_changed_path(
                    left_item,
                    right_item,
                    f"{path}[{index}]",
                    depth + 1,
                )
                if changed_path is not None:
                    return changed_path
            return None
        if left != right:
            return path or "$"
        return None

    check_report = contract.check(repo_root)
    if check_report["status"] != "pass":
        mismatch_path = (
            None if not fresh_references else _first_changed_path(reference, fresh_references[-1])
        )
        pytest.fail(f"fresh expected-QA reference drift at {mismatch_path}: {check_report}")

    # Keep artifact-corruption controls cheap while exercising the real check comparator.
    monkeypatch.setattr(contract, "build_live_payload", lambda _root: first_live)
    monkeypatch.setattr(contract, "_expected_qa_reference", lambda _payload: reference)

    def _assert_reference_drift(mutated: dict[str, Any]) -> None:
        reference_path.write_text(json.dumps(mutated, indent=2, sort_keys=True) + "\n")
        report = contract.check(repo_root)
        assert report["status"] == "fail"
        assert "joint_simulation_contract_drift" in {issue["code"] for issue in report["issues"]}

    status_changed = copy.deepcopy(reference)
    status_changed["contract"]["positive_gate"]["status"] = "limited"
    _assert_reference_drift(status_changed)

    numeric_changed = copy.deepcopy(reference)
    numeric_gate = numeric_changed["contract"]["positive_gate"]["dynamic_horizon"]
    numeric_projection = json.loads(numeric_gate["n5_diagnostic_freshness_json"])

    def _change_first_float(node: Any) -> bool:
        if isinstance(node, dict):
            if set(node) == {"float"} and isinstance(node["float"], str):
                node["float"] = (float.fromhex(node["float"]) + 0.125).hex()
                return True
            return any(_change_first_float(value) for value in node.values())
        if isinstance(node, list):
            return any(_change_first_float(value) for value in node)
        return False

    assert _change_first_float(numeric_projection)
    numeric_gate["n5_diagnostic_freshness_json"] = json.dumps(
        numeric_projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    _assert_reference_drift(numeric_changed)

    result_removed = copy.deepcopy(reference)
    result_removed["contract"]["positive_gate"]["dynamic_horizon"].pop(
        "n5_diagnostic_freshness_json"
    )
    _assert_reference_drift(result_removed)

    # A stale receipt on the fresh raw wire must fail before reference projection/comparison.
    invalid_raw = copy.deepcopy(first_live)
    invalid_raw["positive_gate"]["dynamic_horizon"]["receipt"]["payload_hash"] = (
        "sha256:" + "0" * 64
    )
    monkeypatch.setattr(contract, "build_live_payload", lambda _root: invalid_raw)
    monkeypatch.setattr(
        contract,
        "_expected_qa_reference",
        lambda _payload: pytest.fail("invalid raw payload reached expected-QA comparison"),
    )
    invalid_report = contract.check(repo_root)
    assert invalid_report["status"] == "fail"
    assert "joint_simulation_live_payload_invalid" in {
        issue["code"] for issue in invalid_report["issues"]
    }

    coupled_result_removed = copy.deepcopy(first_live)
    coupled_result_removed["positive_gate"]["coupling_gate"]["supported_coupled_des_abm"].pop(
        "result"
    )
    monkeypatch.setattr(contract, "build_live_payload", lambda _root: coupled_result_removed)
    removed_result_report = contract.check(repo_root)
    assert "supported_coupled_result_missing" in {
        issue["code"] for issue in removed_result_report["issues"]
    }

    coupled_receipt_corrupted = copy.deepcopy(first_live)
    coupled_receipt_corrupted["positive_gate"]["coupling_gate"]["supported_coupled_des_abm"][
        "result"
    ]["receipt"]["payload_hash"] = "sha256:" + "0" * 64
    monkeypatch.setattr(contract, "build_live_payload", lambda _root: coupled_receipt_corrupted)
    coupled_receipt_report = contract.check(repo_root)
    assert any(
        issue["code"] == "sampling_typed_result_invalid"
        and "receipt_content_mismatch" in issue.get("detail", "")
        for issue in coupled_receipt_report["issues"]
    )

    # The writer applies the same raw gate and leaves its target absent on refusal.
    invalid_output = tmp_path / "must-not-be-written.json"
    monkeypatch.setattr(contract, "OUTPUT_PATH", invalid_output)
    monkeypatch.setattr(contract, "build_live_payload", lambda _root: coupled_result_removed)
    write_report = contract.write(repo_root)
    assert write_report["status"] == "fail"
    assert not invalid_output.exists()

    historical_v4 = {
        "schema_version": "policyos.runtime.joint_simulation_horizon.v4",
        "trajectory": [{"step": 0, "outcomes": {"candidate": 1.0}}],
    }
    unchanged_v4, projected_count = contract._project_n5_result_gates(historical_v4)
    assert unchanged_v4 == historical_v4
    assert projected_count == 0


def test_n5_abm_source_flip_runs_behavior_and_restores_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from tools.quality.validation import (
        check_layer3_gy_joint_simulation_horizon_contract as contract,
    )

    runner = getattr(contract, "_run_abm_stub_source_flip", None)
    assert callable(runner), "N5 ABM source-flip runner is missing"
    source_path = tmp_path / "src/polisyos/foundry/methods/catalog/simulation/coupled.py"
    source_path.parent.mkdir(parents=True)
    original = (
        b"from polisyos.foundry.methods.catalog.simulation.dynamics import (\n"
        b"    build_content_bound_abm_result,\n"
        b")\n"
        b"    abm_result = build_content_bound_abm_result(\n"
        b'        method_id="simulation.coupled_policy.des_abm",\n'
        b"        horizon=horizon,\n"
        b"        payload=result,\n"
        b"        diagnostics=diagnostics,\n"
        b"    )\n"
    )
    source_path.write_bytes(original)

    def _completed(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="RuntimeError: abm_result_stub_strangled",
            stderr="",
        )

    monkeypatch.setattr(contract.subprocess, "run", _completed)

    result = runner(tmp_path)

    assert result["mutation_id"] == "source_flip_abm_production_stub_restored"
    assert result["result"] == "RED"
    assert result["proof"]["stub_fence_observed"] is True
    assert source_path.read_bytes() == original


def test_compatible_atom_permutation_preserves_real_outputs_after_fresh_cas_read(
    tmp_path: Path,
) -> None:
    """B20: compatible atom orders preserve real outputs for a supported NCM step."""

    from polisyos.runtime.quality.generation_cycle import (
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    request = _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})
    atom_orders = (
        request.intervention_atoms,
        tuple(reversed(request.intervention_atoms)),
    )
    store = FileSystemCAS(tmp_path / "n5-compatible-order-cas")
    fresh_results: list[JointSimulationResult] = []
    try:
        for atom_order in atom_orders:
            ordered_request = request.model_copy(update={"intervention_atoms": atom_order})
            result = JointSimulationHorizonController(
                method_registry=MethodRegistry._create_fresh()
            ).run(ordered_request)

            assert result.engine_decisions[0].decision == "selected"
            assert result.engine_decisions[0].engine_kind == "ncm_parallel_worlds"
            assert result.diagnostics["engine_run_claimed"] is True
            assert result.trajectories

            result_ref = persist_joint_simulation_result(result, store=store)
            fresh = load_joint_simulation_result(
                result_ref,
                store=store,
                expected_world_model_record_content_hash=(
                    ordered_request.world_model_record.content_hash
                ),
                expected_atom_ids=tuple(
                    atom.intervention_id for atom in ordered_request.intervention_atoms
                ),
                expected_selected_outcomes=ordered_request.selected_outcomes,
            )
            assert fresh.atom_ids == tuple(
                atom.intervention_id for atom in ordered_request.intervention_atoms
            )
            assert fresh.trajectories == result.trajectories
            fresh_results.append(fresh)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()

    def semantic_projection(
        result: JointSimulationResult,
    ) -> tuple[object, ...]:
        trajectories = {
            (item.run_level, tuple(sorted(item.atom_ids))): tuple(
                (
                    point.step,
                    tuple(sorted(point.outcomes.items())),
                    tuple(sorted(point.effect.items())),
                    point.engine_state,
                    (
                        None
                        if point.replication_sampling is None
                        else point.replication_sampling.model_dump(mode="json")
                    ),
                )
                for point in item.points
            )
            for item in result.trajectories
        }
        assert all(len(atom.causal_do_expr.assignments) == 1 for atom in request.intervention_atoms)
        engine_variable_by_atom_id = {
            atom.intervention_id: request.engine_plan[0].variable_map[
                atom.causal_do_expr.assignments[0].variable
            ]
            for atom in request.intervention_atoms
        }
        assert len(set(engine_variable_by_atom_id.values())) == len(engine_variable_by_atom_id)

        def canonical_sampling_summary(
            summary: Any,
            pair_atom_ids: tuple[str, str],
        ) -> dict[str, Any]:
            assert len(pair_atom_ids) == 2
            assert len(set(pair_atom_ids)) == 2
            ordered_pair_ids = tuple(
                atom_id for atom_id in result.atom_ids if atom_id in set(pair_atom_ids)
            )
            assert ordered_pair_ids == pair_atom_ids

            projection = summary.model_dump(mode="json")
            samples = projection["samples"]
            assert isinstance(samples, list)
            assert samples
            for sample in samples:
                assert isinstance(sample, dict)
                engine_state = sample["engine_state"]
                assert isinstance(engine_state, dict)
                source_scope_states = engine_state["source_scope_engine_states"]
                assert isinstance(source_scope_states, dict)
                assert {"pairwise", "individual_left", "individual_right"}.issubset(
                    source_scope_states
                )
                assert "individual_by_atom_id" not in source_scope_states

                for scope_name, atom_id in zip(
                    ("individual_left", "individual_right"), pair_atom_ids, strict=True
                ):
                    individual_state = source_scope_states[scope_name]
                    assert isinstance(individual_state, dict)
                    intervention = individual_state["intervention"]
                    assert isinstance(intervention, dict)
                    assert set(intervention) == {engine_variable_by_atom_id[atom_id]}

                individual_by_atom_id = {
                    pair_atom_ids[0]: source_scope_states.pop("individual_left"),
                    pair_atom_ids[1]: source_scope_states.pop("individual_right"),
                }
                source_scope_states["individual_by_atom_id"] = individual_by_atom_id
            return projection

        interactions = {
            (tuple(sorted(item.atom_ids)), item.outcome): (
                item.by_step,
                item.formula,
                {
                    step: canonical_sampling_summary(summary, item.atom_ids)
                    for step, summary in item.replication_sampling_by_step.items()
                },
            )
            for item in result.interaction_terms
        }
        return (
            tuple(sorted(result.atom_ids)),
            result.engine_decisions,
            trajectories,
            interactions,
            result.marginal_effects,
            result.higher_order_residuals,
            result.feedback_classification.model_dump(mode="json"),
            tuple(result.diagnostics["interaction_evidence_issues"]),
            tuple(result.diagnostics["interaction_sampling_issues"]),
            tuple(result.promotion_ready_value_packet["authority_blockers"]),
        )

    assert fresh_results[0].atom_ids == tuple(
        atom.intervention_id for atom in request.intervention_atoms
    )
    assert fresh_results[1].atom_ids == tuple(
        atom.intervention_id for atom in reversed(request.intervention_atoms)
    )
    assert fresh_results[0].atom_ids != fresh_results[1].atom_ids
    assert semantic_projection(fresh_results[0]) == semantic_projection(fresh_results[1])


@pytest.mark.parametrize(
    "producer_rows",
    ["empty", "short", "full", "producer-uses-wrong-dt"],
    ids=(
        "empty-refuses",
        "short-is-partial",
        "full-is-complete",
        "wrong-dt-is-limited",
    ),
)
def test_system_dynamics_grid_coverage_uses_real_rows_and_retains_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    producer_rows: str,
) -> None:
    """B22: real stock-flow rows determine coverage; final-state markers cannot fill gaps."""

    from polisyos.foundry.methods.catalog.simulation.dynamics import (
        StockFlowSystemDynamicsEstimator,
    )
    from polisyos.runtime.quality.generation_cycle import (
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    real_pure_step = StockFlowSystemDynamicsEstimator.pure_step
    emitted_by_inflows: dict[tuple[float, ...], dict[str, object]] = {}

    def controlled_pure_step(
        state: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        requested_dt = float(params["dt"])
        used_dt = 1.0 if producer_rows == "producer-uses-wrong-dt" else requested_dt
        output = real_pure_step(state, {**params, "dt": used_dt})
        payload = output["result"]
        inflows = tuple(float(value) for value in state["exogenous_inflows"])
        raw_rows = tuple(tuple(float(value) for value in row) for row in payload["trajectory"])
        if len(raw_rows) != 3:
            raise AssertionError("controlled test expects three real producer rows")
        if producer_rows == "empty":
            payload["trajectory"] = []
        elif producer_rows == "short":
            payload["trajectory"] = payload["trajectory"][:-1]
        emitted_by_inflows[inflows] = {
            "requested_dt": requested_dt,
            "used_dt": used_dt,
            "raw_rows": raw_rows,
            "final_stocks": tuple(float(value) for value in payload["final_stocks"]),
            "returned_row_count": len(payload["trajectory"]),
        }
        return output

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(controlled_pure_step),
    )
    base = _shared_resource_stock_flow_fallback_request(
        candidate_order=("system_dynamics", "method_registry_estimator")
    )
    system_dynamics_plan = base.engine_plan[0].model_copy(
        update={"system_dynamics_params": {"dt": 2.0}}
    )
    request = base.model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=4, step=2),
            "engine_plan": (system_dynamics_plan, *base.engine_plan[1:]),
        }
    )
    controller = JointSimulationHorizonController(method_registry=MethodRegistry._create_fresh())

    if producer_rows == "empty":
        for engine_plan in (request.engine_plan, request.engine_plan[:1]):
            emitted_by_inflows.clear()
            result = controller.run(request.model_copy(update={"engine_plan": engine_plan}))
            assert result.engine_decisions[0].decision == "selected"
            assert result.engine_decisions[0].engine_kind == "system_dynamics"
            assert result.trajectories == ()
            assert result.diagnostics["engine_run_claimed"] is False
            assert result.diagnostics["physical_work_interruption"] == "n5_physical_work_failed"
            assert (
                "n5_physical_work_failed"
                in result.promotion_ready_value_packet["authority_blockers"]
            )
            assert len(result.physical_work_observations) == 1
            work = result.physical_work_observations[0]
            assert work.status == "failed"
            assert work.error_code == "trajectory_coverage_incomplete"
            assert len(emitted_by_inflows) == 1
        only_emission = next(iter(emitted_by_inflows.values()))
        assert only_emission["requested_dt"] == 2.0
        assert only_emission["used_dt"] == 2.0
        assert only_emission["raw_rows"]
        assert only_emission["returned_row_count"] == 0
        assert only_emission["final_stocks"]
        return

    result = controller.run(request)
    assert result.engine_decisions[0].decision == "selected"
    assert result.engine_decisions[0].engine_kind == "system_dynamics"
    assert result.diagnostics["engine_run_claimed"] is True
    assert result.diagnostics["physical_time_basis_status"] == "not_established"
    assert (
        "horizon_time_alignment_not_established"
        in result.promotion_ready_value_packet["authority_blockers"]
    )
    assert set(emitted_by_inflows) == {
        (1.0, 0.0),
        (0.0, 1.0),
        (1.0, 1.0),
    }

    requested_steps = request.horizon.steps()
    expected_row_count = 2 if producer_rows == "short" else 3
    expected_coverage = "partial" if producer_rows == "short" else "complete"

    def semantic_steps(diagnostics: dict[str, Any], key: str) -> tuple[int, ...]:
        raw_steps = diagnostics[key]
        assert isinstance(raw_steps, (list, tuple))
        assert all(isinstance(step, int) and not isinstance(step, bool) for step in raw_steps)
        return tuple(raw_steps)

    assert all(emission["requested_dt"] == 2.0 for emission in emitted_by_inflows.values())
    assert all(
        emission["returned_row_count"] == expected_row_count
        for emission in emitted_by_inflows.values()
    )
    joint = result.trajectory_for(
        "joint",
        tuple(atom.intervention_id for atom in request.intervention_atoms),
    )
    assert tuple(point.step for point in joint.points) == requested_steps[:expected_row_count]
    assert semantic_steps(joint.diagnostics, "requested_steps") == requested_steps
    assert (
        semantic_steps(joint.diagnostics, "covered_steps") == requested_steps[:expected_row_count]
    )
    assert joint.diagnostics["coverage_status"] == expected_coverage
    assert joint.diagnostics["hold_last"] is False
    joint_emission = emitted_by_inflows[(1.0, 1.0)]
    actual_rows = tuple(
        tuple(float(value) for value in point.engine_state["stock_values"])
        for point in joint.points
    )
    assert actual_rows == joint_emission["raw_rows"][:expected_row_count]

    if producer_rows == "short":
        assert tuple(point.step for point in joint.points) == (0, 2)
        assert actual_rows[-1] != joint_emission["final_stocks"]
        assert any(
            issue.startswith("horizon_incomplete:")
            for issue in result.diagnostics["interaction_evidence_issues"]
        )
        assert (
            "interaction_evidence_incomplete"
            in result.promotion_ready_value_packet["authority_blockers"]
        )
        assert (
            "interaction_evidence_incomplete" in result.diagnostics["interaction_sampling_issues"]
        )
    else:
        assert tuple(point.step for point in joint.points) == requested_steps
        assert result.diagnostics["interaction_evidence_issues"] == []

    if producer_rows == "producer-uses-wrong-dt":
        assert all(emission["used_dt"] == 1.0 for emission in emitted_by_inflows.values())
        assert all(emission["requested_dt"] == 2.0 for emission in emitted_by_inflows.values())
        # This diagnostic compares the requested method parameter, not emitted timestamps.
        assert joint.diagnostics["time_alignment_status"] == "not_established"
        assert joint.diagnostics["declared_step_parameter_matches_request"] is True
        # The protected time-basis status remains unknown even for this full-row countermodel.
        assert result.diagnostics["physical_time_basis_status"] == "not_established"
        assert (
            "horizon_time_alignment_not_established"
            in result.promotion_ready_value_packet["authority_blockers"]
        )

    store = FileSystemCAS(tmp_path / f"n5-grid-coverage-{producer_rows}-cas")
    try:
        result_ref = persist_joint_simulation_result(result, store=store)
        fresh = load_joint_simulation_result(
            result_ref,
            store=store,
            expected_world_model_record_content_hash=request.world_model_record.content_hash,
            expected_atom_ids=tuple(atom.intervention_id for atom in request.intervention_atoms),
            expected_selected_outcomes=request.selected_outcomes,
        )
        fresh_joint = fresh.trajectory_for(
            "joint",
            tuple(atom.intervention_id for atom in request.intervention_atoms),
        )
        assert fresh_joint.points == joint.points
        assert semantic_steps(fresh_joint.diagnostics, "requested_steps") == requested_steps
        assert (
            semantic_steps(fresh_joint.diagnostics, "covered_steps")
            == requested_steps[:expected_row_count]
        )
        assert fresh_joint.diagnostics["coverage_status"] == expected_coverage
        assert (
            fresh.diagnostics["interaction_evidence_issues"]
            == result.diagnostics["interaction_evidence_issues"]
        )
        assert (
            "horizon_time_alignment_not_established"
            in fresh.promotion_ready_value_packet["authority_blockers"]
        )
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def test_system_dynamics_step_changes_real_rows_on_the_requested_grid() -> None:
    """A unit-step change reaches the registered producer and its actual trajectory."""

    request = _shared_resource_stock_flow_fallback_request(
        candidate_order=("system_dynamics", "method_registry_estimator")
    )

    def run_for_step(step: int) -> tuple[JointSimulationRequest, JointSimulationResult]:
        plan = request.engine_plan[0].model_copy(
            update={"system_dynamics_params": {"dt": float(step)}}
        )
        selected_request = request.model_copy(
            update={
                "horizon": HorizonSpec(start=0, end=2 * step, step=step),
                "engine_plan": (plan, *request.engine_plan[1:]),
            }
        )
        result = JointSimulationHorizonController(
            method_registry=MethodRegistry._create_fresh()
        ).run(selected_request)
        return selected_request, result

    unit_request, unit_result = run_for_step(1)
    coarse_request, coarse_result = run_for_step(2)
    unit_joint = unit_result.trajectory_for(
        "joint",
        tuple(atom.intervention_id for atom in unit_request.intervention_atoms),
    )
    coarse_joint = coarse_result.trajectory_for(
        "joint",
        tuple(atom.intervention_id for atom in coarse_request.intervention_atoms),
    )

    assert tuple(point.step for point in unit_joint.points) == unit_request.horizon.steps()
    assert tuple(point.step for point in coarse_joint.points) == coarse_request.horizon.steps()
    assert unit_joint.diagnostics["requested_time_step"] == 1
    assert coarse_joint.diagnostics["requested_time_step"] == 2
    assert unit_joint.diagnostics["effective_method_time_step"] == 1
    assert coarse_joint.diagnostics["effective_method_time_step"] == 2
    assert unit_joint.diagnostics["time_alignment_status"] == "not_established"
    assert coarse_joint.diagnostics["time_alignment_status"] == "not_established"
    assert unit_joint.diagnostics["declared_step_parameter_matches_request"] is True
    assert coarse_joint.diagnostics["declared_step_parameter_matches_request"] is True
    assert unit_joint.points[-1].outcomes["stock1"] == pytest.approx(4.0)
    assert coarse_joint.points[-1].outcomes["stock1"] == pytest.approx(8.0)
    assert unit_result.diagnostics["physical_time_basis_status"] == "not_established"
    assert coarse_result.diagnostics["physical_time_basis_status"] == "not_established"


def test_finite_source_coordinate_requires_real_scalar_categories() -> None:
    """Accept producer scalar categories and reject malformed scalar-like containers."""
    import numpy as np

    from polisyos.runtime.quality.joint_simulation_horizon import (
        _finite_source_coordinate,
    )

    real_scalars = (1, 1.25, np.int64(2), np.float32(2.5), np.float64(3.5))
    for value in real_scalars:
        assert _finite_source_coordinate(value) == pytest.approx(float(value))

    malformed_values = (
        True,
        np.bool_(True),
        "1",
        1 + 0j,
        np.complex64(1 + 0j),
        [1.0],
        (1.0,),
        np.asarray([1.0]),
        np.asarray(1.0),
    )
    for value in malformed_values:
        assert _finite_source_coordinate(value) is None

    for value in (float("nan"), float("inf"), -float("inf"), np.float64("nan")):
        assert _finite_source_coordinate(value) is None


@pytest.mark.parametrize(
    "time_control",
    [
        "actual",
        "irregular",
        "repeated",
        "reordered",
        "missing",
        "malformed",
        "singleton",
    ],
)
def test_coupled_source_times_remain_candidate_through_fresh_cas_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    time_control: str,
) -> None:
    """Real coupled metrics survive projection while physical-time mapping stays unknown."""
    from dataclasses import replace

    from polisyos.foundry.coupling.executor import CoupledContractsExecutor
    from polisyos.foundry.methods.catalog.simulation.coupled import (
        CoupledPolicySimulationEstimator,
    )
    from polisyos.runtime.quality.generation_cycle import (
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        _finite_source_coordinate,
    )

    request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "coupling_graph": _coupling_graph("shared_resource"),
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "horizon": HorizonSpec(start=0, end=3, step=1),
            "engine_plan": (
                EnginePlan(
                    engine_kind="coupled_des_abm",
                    objective_ref="objective://b22-coupled-time-source",
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
                        "initial_income": [1000.0, 600.0],
                        "initial_savings": [0.0, 0.0],
                        "is_employed": [0.0, 0.0],
                    },
                    coupled_params={
                        "benefit_amount": 0.0,
                        "service_rate": 0.5,
                        "initial_queue_length": 4.0,
                    },
                ),
            ),
        }
    )

    real_step = CoupledContractsExecutor.step
    real_pure_step = CoupledPolicySimulationEstimator.pure_step
    step_indices: dict[int, int] = {}
    executor_initial_times: dict[int, float] = {}
    executor_references: list[CoupledContractsExecutor] = []
    step_observations: list[dict[str, Any]] = []
    captured_runs: list[dict[str, Any]] = []

    def controlled_step(self: Any, runtime_state: Any) -> Any:
        if id(self) not in step_indices:
            executor_references.append(self)
            step_indices[id(self)] = 0
            executor_initial_times[id(self)] = float(runtime_state.time)
        index = step_indices[id(self)]
        step_indices[id(self)] += 1
        step_result = real_step(self, runtime_state)
        original_metrics = dict(step_result.metrics)
        reported_metrics = dict(original_metrics)
        initial_time = executor_initial_times[id(self)]
        offsets = {
            "irregular": (0.25, 1.75, 2.5),
            "repeated": (1.0, 1.0, 2.0),
            "reordered": (1.0, 3.0, 2.0),
        }
        if time_control in offsets:
            reported_time = initial_time + offsets[time_control][index]
            reported_metrics["coupled/time"] = reported_time
            reported_metrics["queue/time"] = reported_time
        elif time_control == "missing" and index == 1:
            reported_metrics.pop("coupled/time", None)
        elif time_control == "malformed" and index == 1:
            reported_metrics["coupled/time"] = "not-a-time"
        elif time_control == "singleton" and index == 1:
            reported_metrics["coupled/time"] = [float(original_metrics["coupled/time"])]
        step_observations.append({"original": original_metrics, "reported": dict(reported_metrics)})
        return replace(step_result, metrics=reported_metrics)

    def captured_pure_step(state: Any, params: Any) -> dict[str, Any]:
        first_step = len(step_observations)
        output = real_pure_step(state, params)
        payload = output["result"]
        captured_runs.append(
            {
                "initial_time": float(payload["coupled_initial_time"]),
                "metrics": copy.deepcopy(payload["metrics"]),
                "queue_rows": copy.deepcopy(payload["queue_length_trajectory"]),
                "steps": copy.deepcopy(step_observations[first_step:]),
            }
        )
        return output

    monkeypatch.setattr(CoupledContractsExecutor, "step", controlled_step)
    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(captured_pure_step),
    )
    result = JointSimulationHorizonController(method_registry=MethodRegistry._create_fresh()).run(
        request
    )

    assert result.engine_decisions[0].decision == "selected"
    assert result.engine_decisions[0].engine_kind == "coupled_des_abm"
    assert result.diagnostics["physical_time_basis_status"] == "not_established"
    assert (
        "horizon_time_alignment_not_established"
        in result.promotion_ready_value_packet["authority_blockers"]
    )
    assert len(captured_runs) == len(
        {trajectory.diagnostics["physical_run_ref"] for trajectory in result.trajectories}
    )
    assert len(step_observations) == sum(len(run["metrics"]) for run in captured_runs)

    for run in captured_runs:
        assert len(run["metrics"]) == len(run["queue_rows"]) == 3
        assert len(run["steps"]) == len(run["metrics"])
        for metric, observation, queue_value in zip(
            run["metrics"], run["steps"], run["queue_rows"], strict=True
        ):
            original = observation["original"]
            reported = observation["reported"]
            assert float(metric["queue/queue_length"]) == float(queue_value)
            assert float(original["queue/queue_length"]) == float(queue_value)
            assert _finite_source_coordinate(original["coupled/time"]) == pytest.approx(
                float(original["coupled/time"])
            )
            assert _finite_source_coordinate(original["queue/time"]) == pytest.approx(
                float(original["queue/time"])
            )
            assert original["coupled/dt"] == reported["coupled/dt"]
            assert {
                key: value
                for key, value in original.items()
                if key not in {"coupled/time", "queue/time"}
            } == {
                key: value
                for key, value in reported.items()
                if key not in {"coupled/time", "queue/time"}
            }
        if time_control != "actual":
            assert any(
                observation["original"].get("coupled/time")
                != observation["reported"].get("coupled/time")
                for observation in run["steps"]
            )

    for trajectory in result.trajectories:
        assert trajectory.diagnostics["time_alignment_status"] == "not_established"
        assert trajectory.diagnostics["declared_step_parameter_matches_request"] is True
        assert tuple(point.step for point in trajectory.points) == request.horizon.steps()
        output_queue_rows = tuple(
            float(point.outcomes["final_queue_length"]) for point in trajectory.points[1:]
        )
        matched_queue_runs = [
            run
            for run in captured_runs
            if output_queue_rows
            == pytest.approx(tuple(float(value) for value in run["queue_rows"]))
        ]
        assert matched_queue_runs
        trace = trajectory.diagnostics["source_time_trace"]
        trace_status = trajectory.diagnostics["source_time_trace_status"]
        if time_control in {"missing", "malformed", "singleton"}:
            expected_reason = (
                "transition_source_time_missing:1"
                if time_control == "missing"
                else "transition_source_time_malformed:1"
            )
            assert trace is None
            assert trace_status == "not_established"
            assert trajectory.diagnostics["source_time_trace_reason"] == expected_reason
            for run in matched_queue_runs:
                row = run["metrics"][1]
                assert _finite_source_coordinate(row["queue/time"]) is not None
                if time_control == "missing":
                    assert "coupled/time" not in row
                elif time_control == "malformed":
                    assert row["coupled/time"] == "not-a-time"
                else:
                    singleton_time = row["coupled/time"]
                    actual_time = run["steps"][1]["original"]["coupled/time"]
                    assert isinstance(singleton_time, list)
                    assert len(singleton_time) == 1
                    assert singleton_time[0] == pytest.approx(float(actual_time))
            continue

        assert trace_status == "observed_candidate"
        assert trace["unit_status"] == "not_established"
        assert trace["origin_status"] == "not_established"
        assert trace["horizon_relation_status"] == "not_established"
        matched_source_runs = [
            run
            for run in matched_queue_runs
            if float(trace["initial_coordinate"]) == run["initial_time"]
            and tuple(trace["transition_coordinates"])
            == pytest.approx(tuple(float(row["coupled/time"]) for row in run["metrics"]))
        ]
        assert matched_source_runs
        assert len(trace["transition_coordinates"]) == len(output_queue_rows)
        if time_control == "irregular":
            assert any(
                tuple(trace["transition_coordinates"])
                == pytest.approx(
                    tuple(run["initial_time"] + offset for offset in (0.25, 1.75, 2.5))
                )
                for run in matched_source_runs
            )
        elif time_control == "repeated":
            assert trace["transition_coordinates"][0] == trace["transition_coordinates"][1]
        elif time_control == "reordered":
            assert trace["transition_coordinates"][1] > trace["transition_coordinates"][2]

    store = FileSystemCAS(tmp_path / f"n5-coupled-source-time-{time_control}-cas")
    try:
        result_ref = persist_joint_simulation_result(result, store=store)
        fresh = load_joint_simulation_result(
            result_ref,
            store=store,
            expected_world_model_record_content_hash=request.world_model_record.content_hash,
            expected_atom_ids=tuple(atom.intervention_id for atom in request.intervention_atoms),
            expected_selected_outcomes=request.selected_outcomes,
        )
        assert fresh.trajectories == result.trajectories
        assert fresh.diagnostics["physical_time_basis_status"] == "not_established"
        assert (
            "horizon_time_alignment_not_established"
            in fresh.promotion_ready_value_packet["authority_blockers"]
        )
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def test_fresh_state_consumption_receipt_matches_complete_typed_projection(tmp_path: Path) -> None:
    """A fresh ordinary plan retains an unknown profile without self-refusal."""
    from polisyos.core.security.tenant_context import tenant_scope
    from tests.unit.runtime.quality.test_generation_cycle import _owner_program_graph_n5_witness

    witness = _owner_program_graph_n5_witness(tmp_path, income_values=(1000.0, 2000.0))
    try:
        result = witness.result
        assert result.state_consumption is not None
        assert result.state_consumption.exec_plan_manifest_profile_sha256 is None
        payload = result.content_bound_payload()
        assert "exec_plan_manifest_profile_sha256" in payload["state_consumption"]
        assert payload["state_consumption"]["exec_plan_manifest_profile_sha256"] is None
        assert payload == result.model_dump(mode="json", exclude={"receipt"})
        verify_simulation_receipt(result.receipt, payload)
        assert result.state_consumption.exec_plan_provenance == "not_established"
        assert set(result.state_consumption.authority_limitations).issubset(
            result.promotion_ready_value_packet["authority_blockers"]
        )
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            ref = witness.simulation.simulation_result_ref
            assert ref is not None
            persisted = json.loads(witness.store.get_bytes(ref))
        assert persisted["state_consumption"] == payload["state_consumption"]
    finally:
        witness.store.close()


def test_numerical_failure_stays_recorded_without_becoming_access_denial(monkeypatch) -> None:
    """The shared access-error choke point leaves ordinary failed work intact."""
    request = _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})
    controller = JointSimulationHorizonController()
    selected = controller._select_engine(request)
    assert selected.decision.decision == "selected"
    assert selected.decision.method_fqn is not None
    method = controller._registry.get(selected.decision.method_fqn)
    calls: list[str] = []

    def fail_numeric(_state: object, _params: object) -> None:
        calls.append("actual-selected-method")
        raise ValueError("controlled numerical failure")

    monkeypatch.setattr(method, "pure_step", staticmethod(fail_numeric))
    result = controller.run(request)
    assert calls == ["actual-selected-method"]
    assert result.trajectories == ()
    assert result.diagnostics["physical_work_interruption"] == "n5_physical_work_failed"
    assert len(result.physical_work_observations) == 1
    work = result.physical_work_observations[0]
    assert work.status == "failed"
    assert work.error_type == "ValueError"
    assert result.receipt.trajectory_count == 0
    assert result.receipt.calibration_status == "no_run"
    verify_simulation_receipt(result.receipt, result.content_bound_payload())


def test_semantic_input_limitations_remain_unknown_before_source_replay() -> None:
    from polisyos.runtime.quality import joint_simulation_horizon as owner

    result = owner.JointSimulationResult.model_construct(diagnostics={}, trajectories=())
    assert result.verified_semantic_input_limitation_codes is None
    assert owner.verify_semantic_program_graph_result_sources(object(), result) is None
    assert result.verified_semantic_input_limitation_codes is None


@pytest.mark.parametrize(
    "admission_codes",
    [
        (("optional_axis_unknown:methodology_ref",), ("source_currentness_not_established",)),
        ((), ()),
        (("code",), None),
    ],
)
def test_semantic_source_replay_uses_all_owner_codes_instead_of_copied_notes(
    monkeypatch: pytest.MonkeyPatch,
    admission_codes: tuple[tuple[str, ...], tuple[str, ...] | None],
) -> None:
    """Exercise code aggregation at the existing admission seam without physical N5."""
    from types import SimpleNamespace

    from polisyos.core.contracts.foundry import FoundryInputBindingsRef
    from polisyos.foundry import execute as execute_owner
    from polisyos.runtime.quality import joint_simulation_horizon as owner

    selected_ref = FoundryInputBindingsRef(artifact_id=_ref("1"), manifest_profile_sha256=_ref("2"))
    graph_ref = ArtifactRef(
        artifact_id=_ref("3"), kind="foundry.program_graph", media_type="application/json"
    )
    plan_ref = ArtifactRef(
        artifact_id=_ref("4"), kind="foundry.exec_plan", media_type="application/json"
    )
    plan = SimpleNamespace(
        program_semantic_input_bindings_ref=selected_ref,
        program_graph_ref=graph_ref,
        exec_plan_ref=plan_ref,
    )
    groups, admissions, trajectories = {}, {}, []
    for index, codes in enumerate(admission_codes):
        seed = 11 + index
        physical_ref = str(7 + index) * 64
        refs, chain, points = [], [], []
        for step_index in range(2):
            step_ref = ArtifactRef(
                artifact_id=_ref(str(5 + 2 * index + step_index)),
                kind="foundry.simulation_result",
                media_type="application/json",
                manifest_profile_sha256=_ref("a"),
            )
            refs.append(step_ref)
            step = SimpleNamespace(
                steps=(0, 1),
                step_index=step_index,
                replication_seed=seed,
                effective_step=step_index,
            )
            basis = SimpleNamespace(
                input_bindings_ref=selected_ref,
                semantic_horizon_step=step,
                program_graph_ref=graph_ref,
                exec_plan_ref=plan_ref,
            )
            step_codes = (
                codes if step_index == 0 else (("later_step_only",) if index == 0 and codes else ())
            )
            chain.append(
                SimpleNamespace(
                    basis=basis,
                    semantic_input_limitation_codes=step_codes,
                    simulation_result=SimpleNamespace(state_snapshot_ref=step_ref),
                )
            )
            locator = step_ref.model_dump(mode="json")
            points.append(
                SimpleNamespace(
                    step=step_index,
                    replication_sampling=SimpleNamespace(
                        samples=(
                            SimpleNamespace(
                                seed=seed,
                                engine_state={"simulation_result_ref": locator},
                                outcomes={},
                                effects={},
                            ),
                        )
                    ),
                    engine_state={
                        "simulation_result_ref": locator,
                        "replication_engine_states": [{"simulation_result_ref": locator}],
                        "semantic_input_notes": ["semantic_input_limitation:forged_copied_code"],
                    },
                )
            )
        replication = SimpleNamespace(step_result_refs=tuple(refs), replication_seed=seed)
        groups[physical_ref] = (replication,)
        admissions[str(refs[0].artifact_id)] = tuple(chain)
        trajectories.append(
            SimpleNamespace(
                diagnostics={"physical_run_ref": "sha256:" + physical_ref},
                points=tuple(points),
            )
        )
    result = SimpleNamespace(
        diagnostics={"semantic_program_graph_bindings_ref": selected_ref.model_dump(mode="json")},
        horizon=SimpleNamespace(steps=lambda: (0, 1)),
        trajectories=trajectories,
    )
    monkeypatch.setattr(owner, "_semantic_program_graph_replications", lambda _: groups)
    monkeypatch.setattr(
        owner.JointSimulationHorizonController,
        "_select_engine",
        lambda *_: SimpleNamespace(
            plan=plan,
            decision=SimpleNamespace(decision="selected", engine_kind="program_graph"),
        ),
    )
    monkeypatch.setattr(execute_owner, "resolve_core_json_profile_store", lambda store: store)
    monkeypatch.setattr(
        execute_owner,
        "admit_semantic_horizon_step_chain",
        lambda store, refs: admissions[str(refs[0].artifact_id)],
    )
    monkeypatch.setattr(owner, "load_state_snapshot", lambda *args, **kwargs: object())
    monkeypatch.setattr(owner, "_program_graph_outcomes", lambda *args: {})
    request = SimpleNamespace(selected_outcomes=())
    if None in admission_codes:
        with pytest.raises(
            ValueError, match="semantic_program_graph_input_limitations_not_established"
        ):
            owner.verify_semantic_program_graph_result_sources(
                object(), result, expected_request=request
            )
        return
    expected_codes = {code for codes in admission_codes for code in codes}
    if admission_codes[0]:
        expected_codes.add("later_step_only")
    expected = tuple(sorted(expected_codes))
    assert (
        owner.verify_semantic_program_graph_result_sources(
            object(), result, expected_request=request
        )
        == expected
    )
    for trajectory in trajectories:
        for point in trajectory.points:
            point.engine_state.pop("semantic_input_notes")
    assert (
        owner.verify_semantic_program_graph_result_sources(
            object(), result, expected_request=request
        )
        == expected
    )


def test_receipt_binding_snapshot_and_selected_comparison_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Exact fast paths cannot certify changed decoders, rules, or mutable payloads."""
    import sys

    from polisyos.runtime.quality import joint_simulation_horizon as owner
    from polisyos.runtime.quality.generation_cycle import (
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    selected_request = _request().model_copy(
        update={"horizon": HorizonSpec(start=0, end=0, step=1), "replications": 2}
    )
    produced = JointSimulationHorizonController().run(selected_request)
    store = FileSystemCAS(tmp_path / "binding-snapshot")
    ref = persist_joint_simulation_result(produced, store=store)
    raw, canon = store.get_bytes(ref), store.get_manifest(ref).canon
    calls: list[int] = []
    native_comparison_hashes: list[int] = []
    code = owner.build_content_bound_simulation_receipt.__code__
    gy_code = owner.gy_content_hash.__code__
    selected_code = owner.JointSimulationHorizonController.validate_selected_result.__code__
    monitoring = sys.monitoring
    tool_id = next(index for index in range(6) if monitoring.get_tool(index) is None)
    monitoring.use_tool_id(tool_id, "receipt-snapshot-test")

    def count_native(observed: object, _offset: int) -> None:
        if observed is code:
            calls.append(1)
        elif observed is gy_code and sys._getframe(1).f_back.f_code is selected_code:
            native_comparison_hashes.append(1)

    monitoring.register_callback(tool_id, monitoring.events.PY_START, count_native)
    monitoring.set_local_events(tool_id, code, monitoring.events.PY_START)
    monitoring.set_local_events(tool_id, gy_code, monitoring.events.PY_START)

    def reset_monitoring() -> None:
        monitoring.set_local_events(tool_id, code, 0)
        monitoring.set_local_events(tool_id, gy_code, 0)
        monitoring.register_callback(tool_id, monitoring.events.PY_START, None)
        monitoring.free_tool_id(tool_id)

    request.addfinalizer(reset_monitoring)
    with owner._receipt_verification_operation():
        loaded = load_joint_simulation_result(ref, store=store, expected_request=selected_request)
        with owner._cas_receipt_verification_binding(raw, ("test",), canon=canon):
            binding = owner._RECEIPT_CAS_BINDING.get()
            assert binding is not None
            with owner._cas_receipt_verification_binding(raw, ("unsupported",), canon=object()):
                assert owner._RECEIPT_CAS_BINDING.get() is None
                assert (
                    owner._receipt_cas_memo_key(loaded.receipt, loaded.content_bound_payload())
                    is None
                )
            assert owner._RECEIPT_CAS_BINDING.get() is binding
            with pytest.raises(TypeError):
                binding[5]["diagnostics"] = {}  # type: ignore[index]
            owner.verify_simulation_receipt(loaded.receipt, loaded.content_bound_payload())
            assert owner._receipt_cas_memo_key(loaded.receipt, loaded.content_bound_payload())
            before = len(calls)
            original_decoder = owner.from_canonical_bytes
            with monkeypatch.context() as changed:
                changed.setattr(
                    owner, "from_canonical_bytes", lambda *a, **kw: original_decoder(*a, **kw)
                )
                assert (
                    owner._receipt_cas_memo_key(loaded.receipt, loaded.content_bound_payload())
                    is None
                )
                owner.verify_simulation_receipt(loaded.receipt, loaded.content_bound_payload())
            assert len(calls) == before + 1

    controller = JointSimulationHorizonController()
    volatile = loaded.model_copy(deep=True)
    volatile._content_payload["diagnostics"]["timestamp"] = "fixture-only volatile occurrence"
    native_comparison_hashes.clear()
    controller.validate_selected_result(request=selected_request, result=loaded)
    assert native_comparison_hashes == []
    controller.validate_selected_result(request=selected_request, result=volatile)
    assert len(native_comparison_hashes) == 2
    original_gy = owner.gy_content_hash
    comparison_hashes: list[int] = []

    def custom_gy(value: object) -> str:
        if sys._getframe(1).f_code is selected_code:
            comparison_hashes.append(1)
        return original_gy(value)

    with monkeypatch.context() as changed:
        changed.setattr(owner, "gy_content_hash", custom_gy)
        controller.validate_selected_result(request=selected_request, result=loaded)
        assert len(comparison_hashes) == 2
        controller.validate_selected_result(request=selected_request, result=volatile)
        assert len(comparison_hashes) == 4
    altered = loaded.model_copy(deep=True)
    altered._content_payload["world_model_record_ref"] = "changed"
    with pytest.raises(JointSimulationControllerError):
        controller.validate_selected_result(request=selected_request, result=altered)
    numeric = loaded.model_copy(deep=True)
    numeric._content_payload["horizon"]["end"] += 1
    with pytest.raises(JointSimulationControllerError):
        controller.validate_selected_result(request=selected_request, result=numeric)
    assert not owner._same_exact_json({"v": -0.0}, {"v": 0.0})
    assert not owner._same_exact_json({"v": True}, {"v": 1})
