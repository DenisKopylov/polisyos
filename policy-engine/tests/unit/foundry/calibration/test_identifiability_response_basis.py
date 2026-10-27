"""Execute-backed local sensitivity binds real state, units, axes and CAS lineage."""

from __future__ import annotations

import logging
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlan,
    ExecuteRequest,
    FoundryExecConfig,
    FoundryExecutionInputBasis,
    Metrics,
    ParameterOverrideBundle,
    ParameterOverrideBundleRef,
    ProgramGraph,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
)
from polisyos.core.registry import (
    build_default_registry_bundle,
    load_registry_bundle_content,
)
from polisyos.core.run.context import RunContext
from polisyos.foundry.calibration import (
    ExecuteResponseBasisCandidate,
    load_execute_response_basis_candidate,
)
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.calibration.execution_basis import (
    load_calibration_execution_input_basis,
    put_calibration_execution_input_basis,
)
from polisyos.foundry.calibration.identifiability import (
    IdentifiabilityDiagnosticConfig,
    _load_execute_response_matrix,
    attach_identifiability_diagnostic_ref,
    identifiability_diagnostic,
)
from polisyos.foundry.calibration.report import (
    CalibrationReport,
    put_calibration_report,
)
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane.bindings import build_input_bindings
from polisyos.foundry.execute import (
    ExecutionSourceAdmissionRefusal,
    admit_execution_source,
)
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
from polisyos.ir import get_json_artifact
from polisyos.ir.analytics.calibration import (
    CalibrationConfig,
    CalibrationTarget,
    TrainableParamRef,
)
from polisyos.ir.analytics.uncertainty import (
    load_simulation_result_subject_uncertainty_projection,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROPAGATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_CALIBRATION_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


def _native_fixture(
    tmp_path,
    *,
    reported_income=(2.0, 2.0),
    store=None,
    return_selected_profile=True,
    feedback=False,
    unrelated_override=False,
    source_override_profile_selected=True,
):
    store = FileSystemCAS(tmp_path / "cas") if store is None else store
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    state = GlobalState.empty(n_agents=2, n_firms=1)
    state = state.replace(
        agents=state.agents.replace(
            active=jnp.asarray([True, True]),
            income=jnp.asarray([10.0, 10.0]),
            reported_income=jnp.asarray(reported_income),
        ),
        government_balance=jnp.asarray(-2.0),
        tax_rate=jnp.asarray(0.125),
    )
    snapshot = put_state_snapshot(store, state=state, step=0, return_selected_profile=True)
    state_ref = StateSnapshotRef.model_validate(snapshot.model_dump(mode="python"))
    data_snapshot_payload_ref = store.put_json(
        DataSnapshot(data_ref=state_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(state_ref, role="data_ref")],
        ),
        return_selected_profile=True,
    )
    data_snapshot_ref = DataSnapshotRef.model_validate(
        data_snapshot_payload_ref.model_dump(mode="python")
    )
    bindings_result = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry.bundle_ref,
        return_selected_profile=True,
    )
    interventions = [
        {
            "intervention_id": "tax",
            "kind": "income_tax",
            "target": {
                "kind": "predicate",
                "field": "id",
                "operator": "==",
                "value": "all",
            },
            "schedule": {"start_step": 0, "duration_steps": 1},
            "params": {"rate": Decimal("0.5")},
        }
    ]
    if unrelated_override:
        interventions.append(
            {
                "intervention_id": "unrelated_tax",
                "kind": "income_tax",
                "target": {
                    "kind": "predicate",
                    "field": "id",
                    "operator": "==",
                    "value": "all",
                },
                "schedule": {"start_step": 0, "duration_steps": 1},
                "params": {"rate": Decimal("0")},
            }
        )
    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="response", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="response",
            interventions=interventions,
        ),
        model_spec=ModelSpec(
            model_id="response",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        policy,
        candidate_id="response_fixture_candidate",
        metadata={"evidence_grade": "candidate", "purpose": "controlled fixture"},
    )
    candidate_ref = persist_policy_candidate_schema(
        store,
        candidate,
        inputs=[
            input_ref_from_artifact_ref(data_snapshot_ref, role="world_model_data_snapshot"),
            input_ref_from_artifact_ref(registry.bundle_ref, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    policy_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store),
            policy,
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")],
        ).model_dump(mode="python")
    )
    compiled = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry.bundle_ref,
            return_selected_profile=True,
        ),
    )
    assert compiled.ok
    feedback_config_ref = None
    if feedback:
        from polisyos.foundry._internal.quickstart import (
            prepare_trivial_feedback_config,
        )

        feedback_config_ref = prepare_trivial_feedback_config(
            store,
            exec_plan_ref=compiled.exec_plan_ref,
            return_selected_profile=True,
        )
    plan = ExecPlan.model_validate(from_canonical_bytes(store.get_bytes(compiled.exec_plan_ref)))
    program = ProgramGraph.model_validate(from_canonical_bytes(store.get_bytes(plan.program_ref)))
    tax_node = next(node for node in program.nodes if node.node_id == "tax")
    source_override_ref = None
    if unrelated_override:
        unrelated_tax = next(node for node in program.nodes if node.node_id == "unrelated_tax")
        source_override_payload_ref = store.put_json(
            ParameterOverrideBundle(
                overrides={unrelated_tax.node_id: {"rate": 0.125}},
                sources={unrelated_tax.node_id: ["controlled_source_override"]},
                notes=["controlled_selected_source_override"],
            ),
            PutOptions(
                kind=ParameterOverrideBundle.ARTIFACT_KIND,
                media_type=ParameterOverrideBundle.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=ParameterOverrideBundle.ARTIFACT_SCHEMA_NAME,
                    version=ParameterOverrideBundle.ARTIFACT_SCHEMA_VERSION,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=source_override_profile_selected,
        )
        source_override_ref = ParameterOverrideBundleRef.model_validate(
            source_override_payload_ref.model_dump(mode="python")
        )
    result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compiled.exec_plan_ref,
            input_bindings_ref=bindings_result.input_bindings_ref,
            registry_bundle_ref=registry.bundle_ref,
            feedback_config_ref=feedback_config_ref,
            parameter_override_bundle_ref=source_override_ref,
            exec_config=FoundryExecConfig(seed=29),
            return_selected_profile=return_selected_profile,
        ),
    )
    assert result.ok
    simulation = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(result.simulation_result_ref))
    )
    poststate = load_state_snapshot(store, snapshot_ref=simulation.state_snapshot_ref)
    if feedback:
        assert np.isfinite(float(poststate.government_balance))
    elif unrelated_override:
        assert np.isfinite(float(poststate.government_balance))
        assert float(poststate.government_balance) != pytest.approx(sum(reported_income) / 2 - 2)
    else:
        assert float(poststate.government_balance) == pytest.approx(sum(reported_income) / 2 - 2)
    return store, result.simulation_result_ref, f"{tax_node.node_id}.rate"


def _diagnostic(store, simulation_ref, parameter):
    return identifiability_diagnostic(
        store,
        simulation_result_ref=simulation_ref,
        observed_moment_bundle={"balance": 0.0},
        parameter_center={parameter: 0.5},
        response_slots={"balance": "government.balance"},
        config=IdentifiabilityDiagnosticConfig(
            simulation_reps=2,
            bootstrap_reps=0,
            profile_grid_size=0,
            seed=29,
            finite_diff_rel_step=0.01,
        ),
    )


def _assert_unrelated_source_override_survives_replays(
    store, source_ref, parameter, matrix_ref, *, profile_selected
):
    source = SimulationResult.model_validate(from_canonical_bytes(store.get_bytes(source_ref)))
    source_admission = admit_execution_source(store, source_ref)
    if profile_selected:
        assert source_admission.mode == "single_step_basis"
        assert source_admission.basis is not None
        source_request = source_admission.basis.request
        source_override_ref = source_request.parameter_override_bundle_ref
    else:
        assert source_admission.mode == "legacy_profileless"
        source_request = None
        edges = [
            item
            for item in store.get_manifest(source_ref).inputs
            if item.role == "parameter_override_bundle"
        ]
        assert len(edges) == 1
        assert edges[0].manifest_profile_sha256 is not None
        source_override_ref = ParameterOverrideBundleRef(
            artifact_id=edges[0].artifact_id,
            manifest_profile_sha256=edges[0].manifest_profile_sha256,
        )
    assert source_override_ref is not None
    assert source_override_ref.manifest_profile_sha256 is not None
    original_bundle = ParameterOverrideBundle.model_validate(
        from_canonical_bytes(store.get_bytes(source_override_ref))
    )
    assert original_bundle.overrides == {"unrelated_tax": {"rate": 0.125}}
    assert original_bundle.sources == {"unrelated_tax": ["controlled_source_override"]}
    assert original_bundle.notes == ["controlled_selected_source_override"]

    target_node, separator, target_param = parameter.rpartition(".")
    assert separator and target_node == "tax" and target_param == "rate"
    matrix = from_canonical_bytes(store.get_bytes(matrix_ref))
    response_basis = matrix["response_basis"]
    assert response_basis["gate_eligible"] is False
    source_input = response_basis["source_inputs"]["source.parameter_override_bundle"]["ref"]
    assert source_input == source_override_ref.model_dump(mode="json")
    for replay in response_basis["replays"]:
        override_ref = ParameterOverrideBundleRef.model_validate(replay["override"]["ref"])
        override = ParameterOverrideBundle.model_validate(
            from_canonical_bytes(store.get_bytes(override_ref))
        )
        expected_overrides = {
            "unrelated_tax": {"rate": 0.125},
            target_node: {"rate": float(replay["theta"][parameter])},
        }
        assert override.overrides == expected_overrides
        assert override.sources == {
            "unrelated_tax": ["controlled_source_override"],
            target_node: ["identifiability_diagnostic"],
        }
        assert override.notes == [
            "controlled_selected_source_override",
            "aggregate_moment_identifiability_replay",
        ]
        override_inputs = store.get_manifest(override_ref).inputs
        assert override_inputs == [
            input_ref_from_artifact_ref(
                source_override_ref,
                role="input.original_parameter_override_bundle_ref",
            )
        ]

        request_ref = replay["request"]["ref"]
        request = ExecuteRequest.model_validate(from_canonical_bytes(store.get_bytes(request_ref)))
        assert request.parameter_override_bundle_ref == override_ref
        assert request.return_selected_profile is profile_selected
        if source_request is not None:
            expected_request = source_request.model_dump(mode="json")
            expected_request["parameter_override_bundle_ref"] = override_ref.model_dump(mode="json")
            expected_request["exec_config"]["seed"] = replay["seed"]
            assert request.model_dump(mode="json") == expected_request

        child_ref = SimulationResultRef.model_validate(replay["result"]["ref"])
        child = admit_execution_source(store, child_ref)
        expected_mode = "single_step_basis" if profile_selected else "legacy_profileless"
        assert child.mode == expected_mode
        if child.basis is not None:
            assert child.basis.request == request
            assert child.basis.parameter_overrides == expected_overrides
        else:
            child_edges = [
                item
                for item in child.simulation_manifest.inputs
                if item.role == "parameter_override_bundle"
            ]
            assert child_edges == [
                input_ref_from_artifact_ref(override_ref, role="parameter_override_bundle")
            ]

        if (
            profile_selected
            and replay["theta"] == {parameter: 0.5}
            and replay["seed"] == source_request.exec_config.seed
        ):
            child_state = load_state_snapshot(
                store, snapshot_ref=child.simulation_result.state_snapshot_ref
            )
            source_state = load_state_snapshot(store, snapshot_ref=source.state_snapshot_ref)
            assert float(child_state.government_balance) == pytest.approx(
                float(source_state.government_balance)
            )


def test_native_zero_baseline_has_dimensioned_nonzero_response(tmp_path):
    store, simulation_ref, parameter = _native_fixture(tmp_path)
    diagnostic = _diagnostic(store, simulation_ref, parameter)
    assert diagnostic.sensitivity_matrix_ref is not None
    payload = from_canonical_bytes(store.get_bytes(diagnostic.sensitivity_matrix_ref))
    np.testing.assert_allclose(payload["jacobian"], [[4.0]], rtol=2e-5)
    assert diagnostic.fitted_moments["balance"] == pytest.approx(0.0)
    assert payload["response_basis"]["parameter_units"][parameter]["kind"] == "rate"
    assert payload["response_basis"]["moment_units"]["balance"]["currency"] == "USD"
    # Independent exact law, not the finite-difference implementation.
    variance = Fraction(4) ** 2 * Fraction(1, 16)
    assert variance == 1
    assert payload["response_basis"]["gate_eligible"] is False


def test_explicit_profileless_execute_optout_remains_legacy(tmp_path):
    store, source, parameter = _native_fixture(
        tmp_path, return_selected_profile=False, unrelated_override=True
    )
    source_payload = SimulationResult.model_validate(from_canonical_bytes(store.get_bytes(source)))
    assert source.manifest_profile_sha256 is None
    assert source_payload.schema_version == SimulationResult.LEGACY_ARTIFACT_SCHEMA_VERSION
    assert source_payload.execution_input_basis_ref is None

    from polisyos.foundry.execute import admit_execution_source

    legacy = admit_execution_source(store, source)
    assert legacy.mode == "legacy_profileless"
    assert legacy.basis_inventory is None

    diagnostic = _diagnostic(store, source, parameter)
    assert diagnostic.sensitivity_matrix_ref is not None
    payload = from_canonical_bytes(store.get_bytes(diagnostic.sensitivity_matrix_ref))
    assert payload["response_basis"]["gate_eligible"] is False
    _assert_unrelated_source_override_survives_replays(
        store, source, parameter, diagnostic.sensitivity_matrix_ref, profile_selected=False
    )
    for replay in payload["response_basis"]["replays"]:
        request = ExecuteRequest.model_validate(
            from_canonical_bytes(store.get_bytes(replay["request"]["ref"]))
        )
        assert request.return_selected_profile is False
    with pytest.raises(ValueError, match="basis differs"):
        _load_execute_response_matrix(
            store,
            diagnostic.sensitivity_matrix_ref,
            source_ref=source,
            response_slots={"balance": "government.balance"},
            parameter_center={parameter: 0.5},
            config=IdentifiabilityDiagnosticConfig(
                simulation_reps=2,
                bootstrap_reps=0,
                profile_grid_size=0,
                seed=29,
                finite_diff_rel_step=0.01,
            ),
        )


def test_legacy_source_with_unselected_override_refuses_replay(tmp_path, monkeypatch):
    store, source, parameter = _native_fixture(
        tmp_path,
        return_selected_profile=False,
        unrelated_override=True,
        source_override_profile_selected=False,
    )
    admitted = admit_execution_source(store, source)
    assert admitted.mode == "legacy_profileless"
    source_override_edges = [
        item
        for item in admitted.simulation_manifest.inputs
        if item.role == "parameter_override_bundle"
    ]
    assert len(source_override_edges) == 1
    assert source_override_edges[0].manifest_profile_sha256 is None

    def no_replay(*args, **kwargs):
        pytest.fail("an unselected present source override was silently omitted")

    monkeypatch.setattr("polisyos.foundry.execute.api.execute", no_replay)
    with pytest.raises(
        ValueError,
        match="legacy response source parameter override has no selected manifest profile",
    ):
        _diagnostic(store, source, parameter)


def test_selected_summary_and_state_routes_replay_the_admitted_request(tmp_path, monkeypatch):
    from polisyos.foundry.calibration.identifiability import (
        _build_execute_summary_evaluator,
        _ExecuteResponseEvaluator,
    )
    from polisyos.foundry.execute import admit_execution_source, execute

    store, source, parameter = _native_fixture(tmp_path, unrelated_override=True)
    source_payload = SimulationResult.model_validate(from_canonical_bytes(store.get_bytes(source)))
    assert admit_execution_source(store, source).mode == "single_step_basis"
    requests = []

    def capture_execute(store_arg, request):
        requests.append(request)
        return execute(store_arg, request)

    monkeypatch.setattr("polisyos.foundry.execute.api.execute", capture_execute)
    summary = _build_execute_summary_evaluator(
        store,
        simulation_result_ref=source,
        simulation_result=source_payload,
    )
    summary({parameter: 0.5}, 41)
    response = _ExecuteResponseEvaluator(
        store,
        source,
        {"balance": "government.balance"},
        {parameter: 0.5},
        ("balance",),
        IdentifiabilityDiagnosticConfig(
            simulation_reps=1,
            bootstrap_reps=0,
            profile_grid_size=0,
            seed=41,
            finite_diff_rel_step=0.01,
        ),
    )
    response({parameter: 0.5}, 41)

    assert len(requests) == 2
    assert all(request.return_selected_profile is True for request in requests), [
        request.model_dump(mode="json") for request in requests
    ]
    assert all("return_selected_profile" in request.model_fields_set for request in requests)
    assert all(request.exec_plan_ref == source_payload.exec_plan_ref for request in requests)
    assert all(request.input_bindings_ref == requests[0].input_bindings_ref for request in requests)
    source_request = admit_execution_source(store, source).basis.request
    source_override_ref = source_request.parameter_override_bundle_ref
    assert source_override_ref is not None
    for request in requests:
        assert request.parameter_override_bundle_ref is not None
        replay_bundle = ParameterOverrideBundle.model_validate(
            from_canonical_bytes(store.get_bytes(request.parameter_override_bundle_ref))
        )
        assert replay_bundle.overrides == {
            "unrelated_tax": {"rate": 0.125},
            "tax": {"rate": 0.5},
        }
        assert store.get_manifest(request.parameter_override_bundle_ref).inputs == [
            input_ref_from_artifact_ref(
                source_override_ref,
                role="input.original_parameter_override_bundle_ref",
            )
        ]


def test_foundry_admission_returns_exact_basis_inventory(tmp_path):
    store, source, _ = _native_fixture(tmp_path)
    admitted = admit_execution_source(store, source)
    assert admitted.mode == "single_step_basis"
    assert admitted.basis is not None
    assert admitted.basis_manifest is not None
    assert admitted.basis_inventory is not None
    assert isinstance(admitted.basis_inventory, tuple)

    def inventory_key(items):
        return sorted(
            (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in items
        )

    assert inventory_key(admitted.basis_inventory) == inventory_key(admitted.basis_manifest.inputs)


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ("profileless_ref", "execution_source_basis_selected_profile_missing"),
        ("missing_edge", "execution_source_requires_one_execution_input_basis_edge"),
        (
            "mismatched_edge",
            "execution_source_basis_ref_differs_from_exact_result_edge",
        ),
        (
            "explicit_optout",
            "execution_source_basis_request_did_not_explicitly_select_profiles",
        ),
    ],
)
def test_selected_source_admission_rejects_present_malformed_basis_before_state_load(
    response_case, monkeypatch, mutation, expected_error
):
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.foundry.calibration.identifiability import _response_context

    _, store, source, parameter, _ = response_case
    assert admit_execution_source(store, source).mode == "single_step_basis"
    source_payload = from_canonical_bytes(store.get_bytes(source))
    source_manifest = store.get_manifest(source)
    inputs = list(source_manifest.inputs)
    if mutation == "profileless_ref":
        source_payload["execution_input_basis_ref"]["manifest_profile_sha256"] = None
        inputs = [
            item.model_copy(update={"manifest_profile_sha256": None})
            if item.role == "execution_input_basis"
            else item
            for item in inputs
        ]
    elif mutation == "missing_edge":
        inputs = [item for item in inputs if item.role != "execution_input_basis"]
    elif mutation == "mismatched_edge":
        inputs = [
            item.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
            if item.role == "execution_input_basis"
            else item
            for item in inputs
        ]
    elif mutation == "explicit_optout":
        basis_ref = ArtifactRef.model_validate(source_payload["execution_input_basis_ref"])
        basis_manifest = store.get_manifest(basis_ref)
        basis = FoundryExecutionInputBasis.model_validate(
            from_canonical_bytes(store.get_bytes(basis_ref))
        )
        request = basis.request.model_copy(update={"return_selected_profile": False})
        changed_basis = basis.model_copy(update={"request": request})
        new_basis_ref = store.put_json(
            changed_basis,
            PutOptions(
                kind=basis_ref.kind,
                media_type=basis_ref.media_type,
                schema=basis_manifest.artifact_schema,
                inputs=basis_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        source_payload["execution_input_basis_ref"] = new_basis_ref.model_dump(mode="json")
        inputs = [
            input_ref_from_artifact_ref(new_basis_ref, role="execution_input_basis")
            if item.role == "execution_input_basis"
            else item
            for item in inputs
        ]
    malformed_ref = store.put_json(
        source_payload,
        PutOptions(
            kind=source_manifest.kind,
            media_type=source_manifest.media_type,
            schema=source_manifest.artifact_schema,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )

    def no_state(*args, **kwargs):
        pytest.fail("malformed selected source reached state loading")

    monkeypatch.setattr("polisyos.foundry.execute.executor.load_state_snapshot", no_state)
    with pytest.raises(ExecutionSourceAdmissionRefusal) as refusal:
        admit_execution_source(store, malformed_ref)
    assert type(refusal.value) is ExecutionSourceAdmissionRefusal
    assert refusal.value.reason == expected_error
    assert type(refusal.value.__cause__) is ValueError
    assert str(refusal.value.__cause__) == expected_error

    with pytest.raises(ValueError, match=expected_error):
        _response_context(
            store,
            malformed_ref,
            {"balance": "government.balance"},
            {parameter: 0.5},
            ("balance",),
            IdentifiabilityDiagnosticConfig(
                simulation_reps=1,
                bootstrap_reps=0,
                profile_grid_size=0,
                seed=41,
                finite_diff_rel_step=0.01,
            ),
        )


def test_feedback_selected_source_is_typed_uncomposed_refusal(tmp_path, monkeypatch):
    from polisyos.foundry.calibration.identifiability import (
        _build_execute_summary_evaluator,
        _response_context,
    )
    from polisyos.foundry.execute import admit_execution_source

    store, source, parameter = _native_fixture(tmp_path, feedback=True)
    admitted = admit_execution_source(store, source)
    assert admitted.mode == "feedback_uncomposed"
    assert admitted.basis is None
    assert admitted.basis_inventory is None
    assert admitted.simulation_result.execution_source_status == "feedback_uncomposed"

    def no_replay(*args, **kwargs):
        pytest.fail("feedback_uncomposed source was downgraded to a replay")

    monkeypatch.setattr("polisyos.foundry.execute.api.execute", no_replay)
    with pytest.raises(ValueError, match=f"feedback_uncomposed source {source.artifact_id}"):
        _build_execute_summary_evaluator(
            store,
            simulation_result_ref=source,
            simulation_result=admitted.simulation_result,
        )
    with pytest.raises(ValueError, match=f"feedback_uncomposed source {source.artifact_id}"):
        _response_context(
            store,
            source,
            {"balance": "government.balance"},
            {parameter: 0.5},
            ("balance",),
            IdentifiabilityDiagnosticConfig(
                simulation_reps=1,
                bootstrap_reps=0,
                profile_grid_size=0,
                seed=41,
                finite_diff_rel_step=0.01,
            ),
        )


def test_metric_name_collision_does_not_bind_counter_to_response_unit(tmp_path):
    """A key collision is insufficient to join an execution counter to a state response."""
    store, simulation_ref, parameter = _native_fixture(tmp_path)
    simulation = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(simulation_ref))
    )
    metrics = Metrics.model_validate(from_canonical_bytes(store.get_bytes(simulation.metrics_ref)))
    assert "step_latency_ms" in metrics.values
    assert "unit" not in Metrics.model_fields
    assert "source_ref" not in Metrics.model_fields

    diagnostic = identifiability_diagnostic(
        store,
        simulation_result_ref=simulation_ref,
        observed_moment_bundle={"step_latency_ms": float(metrics.values["step_latency_ms"])},
        parameter_center={parameter: 0.5},
        response_slots={"step_latency_ms": "government.balance"},
        config=IdentifiabilityDiagnosticConfig(
            simulation_reps=2,
            bootstrap_reps=0,
            profile_grid_size=0,
            seed=29,
            finite_diff_rel_step=0.01,
        ),
    )

    assert diagnostic.sensitivity_matrix_ref is not None
    payload = from_canonical_bytes(store.get_bytes(diagnostic.sensitivity_matrix_ref))
    basis = payload["response_basis"]
    assert basis["gate_eligible"] is False
    assert basis["state_paths"]["step_latency_ms"] == "government_balance"
    assert basis["moment_units"]["step_latency_ms"]["currency"] == "USD"
    # The native graph producer's same-name metric is a wall-clock counter in milliseconds.
    # The typed Metrics carrier has no per-key unit/source binding, so this candidate basis
    # cannot authorize propagation merely because the strings happen to match.


def test_fresh_reader_recomputes_actual_native_response(tmp_path):
    store, simulation_ref, parameter = _native_fixture(tmp_path, unrelated_override=True)
    diagnostic = _diagnostic(store, simulation_ref, parameter)
    payload = _load_execute_response_matrix(
        FileSystemCAS(tmp_path / "cas"),
        diagnostic.sensitivity_matrix_ref,
        source_ref=simulation_ref,
        response_slots={"balance": "government.balance"},
        parameter_center={parameter: 0.5},
        config=IdentifiabilityDiagnosticConfig(
            simulation_reps=2,
            bootstrap_reps=0,
            profile_grid_size=0,
            seed=29,
            finite_diff_rel_step=0.01,
        ),
    )
    _assert_unrelated_source_override_survives_replays(
        store, simulation_ref, parameter, diagnostic.sensitivity_matrix_ref, profile_selected=True
    )
    assert payload["response_basis"]["gate_eligible"] is False
    # The unrelated source tax shifts the level; the differentiated tax still has the
    # exact registered state response from the fixture's reported-income series.
    np.testing.assert_allclose(payload["jacobian"], [[4.0]], rtol=2e-5)

    # Retain every response-basis marker and replace one real replay with a content-bound
    # bundle that drops the unrelated source override. The fresh reader must reject the
    # semantic map divergence, rather than accept the unchanged roster shape.
    matrix_manifest = store.get_manifest(diagnostic.sensitivity_matrix_ref)
    changed_matrix = from_canonical_bytes(store.get_bytes(diagnostic.sensitivity_matrix_ref))
    changed_record = changed_matrix["response_basis"]["replays"][0]
    theta = changed_record["theta"]
    fake_override_ref = store.put_json(
        ParameterOverrideBundle(
            overrides={"tax": {"rate": float(theta[parameter])}},
            sources={"tax": ["identifiability_diagnostic"]},
            notes=["aggregate_moment_identifiability_replay"],
        ),
        PutOptions(
            kind=ParameterOverrideBundle.ARTIFACT_KIND,
            media_type=ParameterOverrideBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ParameterOverrideBundle.ARTIFACT_SCHEMA_NAME,
                version=ParameterOverrideBundle.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    request_ref = ExecuteRequest.model_validate(
        from_canonical_bytes(store.get_bytes(changed_record["request"]["ref"]))
    )
    fake_request_ref = store.put_json(
        request_ref.model_copy(update={"parameter_override_bundle_ref": fake_override_ref}),
        PutOptions(
            kind="foundry.identifiability_replay_request",
            media_type="application/json",
            inputs=[
                input_ref_from_artifact_ref(simulation_ref, role="response.source"),
                input_ref_from_artifact_ref(fake_override_ref, role="response.override"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )

    def identity(ref):
        return {
            "ref": ref.model_dump(mode="json"),
            "content_sha256": "sha256:" + sha256(store.get_bytes(ref)).hexdigest(),
            "manifest_sha256": "sha256:" + sha256(store.get_manifest_bytes(ref)).hexdigest(),
        }

    changed_record["override"] = identity(fake_override_ref)
    changed_record["request"] = identity(fake_request_ref)
    replacements = {
        "response.override.0": input_ref_from_artifact_ref(
            fake_override_ref, role="response.override.0"
        ),
        "response.request.0": input_ref_from_artifact_ref(
            fake_request_ref, role="response.request.0"
        ),
    }
    changed_inputs = [replacements.get(item.role, item) for item in matrix_manifest.inputs]
    changed_matrix_ref = store.put_json(
        changed_matrix,
        PutOptions(
            kind=matrix_manifest.kind,
            media_type=matrix_manifest.media_type,
            schema=matrix_manifest.artifact_schema,
            inputs=changed_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="merged source/finite-difference map"):
        _load_execute_response_matrix(
            store,
            changed_matrix_ref,
            source_ref=simulation_ref,
            response_slots={"balance": "government.balance"},
            parameter_center={parameter: 0.5},
            config=IdentifiabilityDiagnosticConfig(
                simulation_reps=2,
                bootstrap_reps=0,
                profile_grid_size=0,
                seed=29,
                finite_diff_rel_step=0.01,
            ),
        )


def test_actual_response_matrix_reader_refuses_non_object_payload(response_case):
    _, store, source, parameter, original = response_case
    manifest = store.get_manifest(original)
    malformed = store.put_json(
        ["not", "an", "object"],
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
    )

    with pytest.raises(ValueError, match="response matrix payload must be an object"):
        _load_execute_response_matrix(
            store,
            malformed,
            source_ref=source,
            response_slots={"balance": "government.balance"},
            parameter_center={parameter: 0.5},
            config=IdentifiabilityDiagnosticConfig(
                simulation_reps=2,
                bootstrap_reps=0,
                profile_grid_size=0,
                seed=29,
                finite_diff_rel_step=0.01,
            ),
        )


@pytest.fixture(scope="module")
def response_case(tmp_path_factory):
    path = tmp_path_factory.mktemp("response_case")
    store, source, parameter = _native_fixture(path)
    diagnostic = _diagnostic(store, source, parameter)
    assert diagnostic.sensitivity_matrix_ref is not None
    return path, store, source, parameter, diagnostic.sensitivity_matrix_ref


def _read(case, *, matrix=None, **updates):
    path, _, source, parameter, original = case
    kwargs = dict(
        source_ref=source,
        response_slots={"balance": "government.balance"},
        parameter_center={parameter: 0.5},
        config=IdentifiabilityDiagnosticConfig(
            simulation_reps=2,
            bootstrap_reps=0,
            profile_grid_size=0,
            seed=29,
            finite_diff_rel_step=0.01,
        ),
    )
    kwargs.update(updates)
    return _load_execute_response_matrix(FileSystemCAS(path / "cas"), matrix or original, **kwargs)


def _changed_matrix(case, change, *, inputs=None):
    _, store, _, _, original = case
    payload = from_canonical_bytes(store.get_bytes(original))
    change(payload)
    from polisyos.core.canon import CanonSpec

    return store.put_json(
        payload,
        PutOptions(
            kind=original.kind,
            media_type=original.media_type,
            schema=store.get_manifest(original).artifact_schema,
            inputs=store.get_manifest(original).inputs if inputs is None else inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "unit",
        "parameter_unit",
        "missing_input",
        "extra_input",
        "wrong_hash",
        "wrong_manifest",
        "fake_ref",
        "changed_source",
        "slot",
        "model",
        "axis",
        "jacobian",
        "fisher",
        "seed",
        "missing_replay",
    ],
)
def test_actual_cas_basis_mutations_refuse_before_state_load(response_case, monkeypatch, mutation):
    def change(payload):
        basis = payload["response_basis"]
        source = basis["source_inputs"]
        if mutation == "unit":
            basis["moment_units"]["balance"]["currency"] = "UAH"
        elif mutation == "parameter_unit":
            basis["parameter_units"][basis["parameter_names"][0]]["base"] = "percent"
        elif mutation == "missing_input":
            del source["bound_state"]
        elif mutation == "extra_input":
            source["unexpected"] = source["source"]
        elif mutation == "wrong_hash":
            source["source"]["content_sha256"] = "sha256:" + "f" * 64
        elif mutation == "wrong_manifest":
            source["source"]["manifest_sha256"] = "sha256:" + "f" * 64
        elif mutation == "fake_ref":
            source["source"]["ref"]["artifact_id"] = "sha256:" + "f" * 64
        elif mutation == "changed_source":
            source["source"]["ref"] = source["model"]["ref"]
        elif mutation == "slot":
            basis["response_slots"]["balance"] = "global.tax_rate"
        elif mutation == "model":
            source["model"] = source["data"]
        elif mutation == "axis":
            payload["moment_names"] = ["unrelated"]
        elif mutation == "jacobian":
            payload["jacobian"] = [[999.0]]
        elif mutation == "fisher":
            payload["fisher_information"] = [[999.0]]
        elif mutation == "seed":
            basis["replays"][0]["seed"] += 1
        elif mutation == "missing_replay":
            basis["replays"].pop()

    matrix = _changed_matrix(response_case, change)
    # Basis/roster failures happen before protected state consumption. Numerical
    # matrix changes require reading the genuine states to recompute the oracle.
    if mutation not in {"jacobian", "fisher"}:

        def no_state(*args, **kwargs):
            pytest.fail("unvalidated response basis reached state loading")

        monkeypatch.setattr("polisyos.foundry.execute.executor.load_state_snapshot", no_state)
    with pytest.raises(ValueError):
        _read(response_case, matrix=matrix)


def test_forged_unit_with_retained_markers_is_rejected(response_case):
    def forged(payload):
        payload["response_basis"]["moment_units"]["balance"]["currency"] = "UAH"

    matrix = _changed_matrix(response_case, forged)
    payload = from_canonical_bytes(response_case[1].get_bytes(matrix))
    assert payload["response_basis"]["profile"] == "execute_scalar_state_response_v1"
    assert payload["response_basis"]["gate_eligible"] is False
    assert payload["jacobian"][0][0] == pytest.approx(4.0, rel=2e-5)
    with pytest.raises(ValueError, match="basis differs"):
        _read(response_case, matrix=matrix)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate"])
def test_manifest_exact_input_roster_is_consumed(response_case, mutation):
    _, store, _, _, original = response_case
    inputs = list(store.get_manifest(original).inputs)
    from polisyos.core.artifacts.manifest import InputRef

    if mutation == "missing":
        inputs.pop()
    elif mutation == "extra":
        inputs.append(inputs[0].model_copy(update={"role": "response.extra"}))
    else:
        inputs.append(InputRef(artifact_id=inputs[1].artifact_id, role=inputs[0].role))
    matrix = _changed_matrix(response_case, lambda payload: None, inputs=inputs)
    with pytest.raises(ValueError, match="manifest input roster"):
        _read(response_case, matrix=matrix)


@pytest.mark.parametrize("update", ["center", "config", "slot"])
def test_caller_expected_contract_is_recomputed(response_case, update):
    parameter = response_case[3]
    kwargs = {}
    if update == "center":
        kwargs["parameter_center"] = {parameter: 0.4}
    elif update == "config":
        kwargs["config"] = IdentifiabilityDiagnosticConfig(
            simulation_reps=2,
            bootstrap_reps=0,
            profile_grid_size=0,
            seed=30,
            finite_diff_rel_step=0.01,
        )
    else:
        kwargs["response_slots"] = {"balance": "global.tax_rate"}
    with pytest.raises(ValueError, match="basis differs"):
        _read(response_case, **kwargs)


def test_real_changed_source_ref_is_not_old_response_basis(response_case, tmp_path):
    _, other, _ = _native_fixture(tmp_path, reported_income=(1.0, 1.0), store=response_case[1])
    with pytest.raises((ValueError, FileNotFoundError)):
        _read(response_case, source_ref=other)


def test_unknown_partial_response_refuses_without_dropping_known_slots(response_case, monkeypatch):
    _, store, source, parameter, _ = response_case

    def no_execute(*args, **kwargs):
        pytest.fail("unknown response slot reached execute")

    monkeypatch.setattr("polisyos.foundry.execute.api.execute", no_execute)
    with pytest.raises(ValueError, match="unsupported scalar"):
        identifiability_diagnostic(
            store,
            simulation_result_ref=source,
            observed_moment_bundle={"balance": 0.0, "unknown": 0.0},
            parameter_center={parameter: 0.5},
            response_slots={
                "balance": "government.balance",
                "unknown": "not.registered",
            },
            config=IdentifiabilityDiagnosticConfig(bootstrap_reps=0, profile_grid_size=0),
        )


def test_native_constant_response_is_not_invented(tmp_path):
    store, source, parameter = _native_fixture(tmp_path, reported_income=(0.0, 0.0))
    diagnostic = _diagnostic(store, source, parameter)
    payload = from_canonical_bytes(store.get_bytes(diagnostic.sensitivity_matrix_ref))
    assert payload["jacobian"] == [[0.0]]
    assert "zero_summary_sensitivity" in diagnostic.blocking_reasons
    assert payload["response_basis"]["gate_eligible"] is False


def test_original_affine_callback_zero_baseline_is_separate_math_control(response_case):
    _, store, source, _, _ = response_case
    diagnostic = identifiability_diagnostic(
        store,
        simulation_result_ref=source,
        observed_moment_bundle={"y": 0.0},
        parameter_center={"x": 2.0},
        summary_evaluator=lambda theta, seed: {"y": theta["x"] - 2},
        config=IdentifiabilityDiagnosticConfig(
            simulation_reps=2, bootstrap_reps=0, profile_grid_size=0
        ),
    )
    payload = from_canonical_bytes(store.get_bytes(diagnostic.sensitivity_matrix_ref))
    np.testing.assert_allclose(payload["jacobian"], [[1.0]])
    assert "response_basis" not in payload


def test_native_state_response_resource_scaling_keeps_declared_units(tmp_path):
    store, source, parameter = _native_fixture(tmp_path, reported_income=(2000.0, 2000.0))
    diagnostic = _diagnostic(store, source, parameter)
    payload = from_canonical_bytes(store.get_bytes(diagnostic.sensitivity_matrix_ref))
    assert payload["jacobian"][0][0] == pytest.approx(4000.0, rel=2e-5)
    assert payload["response_basis"]["moment_units"]["balance"]["currency"] == "USD"
    # Changing numerical currency amounts rescales derivative, not its unit tag.
    assert Fraction(4000, 4) == 1000


def test_actual_fresh_child_reads_persisted_native_basis(response_case):
    import hashlib
    import importlib
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    path, _, source, parameter, matrix = response_case
    module_names = (
        "polisyos",
        "polisyos.foundry",
        "polisyos.foundry.calibration",
        "polisyos.foundry.execute",
        "polisyos.foundry.execute.api",
        "polisyos.foundry.calibration.identifiability",
    )
    package = importlib.import_module("polisyos")
    package_root = Path(package.__file__).resolve().parent
    expected_sources = {}
    for module_name in module_names:
        module = importlib.import_module(module_name)
        module_spec = module.__spec__
        assert module_spec is not None
        assert module_spec.origin is not None
        module_path = Path(module.__file__).resolve()
        spec_path = Path(module_spec.origin).resolve()
        assert module_path == spec_path
        assert module_path.is_file()
        assert module_path.is_relative_to(package_root)
        expected_sources[module_name] = {
            "origin": str(module_path),
            "sha256": hashlib.sha256(module_path.read_bytes()).hexdigest(),
        }

    request = json.dumps(
        {
            "cas": str(path / "cas"),
            "source": source.model_dump(mode="json"),
            "matrix": matrix.model_dump(mode="json"),
            "parameter": parameter,
            "expected_sources": expected_sources,
        }
    )
    child = r"""
import hashlib, importlib, json, pathlib, sys
request=json.loads(sys.argv[1])
expected=request['expected_sources']
origins={}
spec_origins={}
hashes={}
for name, binding in expected.items():
    module=importlib.import_module(name)
    module_spec=module.__spec__
    if module_spec is None or module_spec.origin is None:
        raise AssertionError(f'{name} has no concrete import origin')
    origin=pathlib.Path(module.__file__).resolve()
    spec_origin=pathlib.Path(module_spec.origin).resolve()
    if origin != spec_origin:
        raise AssertionError(f'{name} __file__ and spec origin differ: {origin} != {spec_origin}')
    digest=hashlib.sha256(origin.read_bytes()).hexdigest()
    if str(origin) != binding['origin']:
        raise AssertionError(f'{name} origin differs: {origin} != {binding["origin"]}')
    if digest != binding['sha256']:
        raise AssertionError(f'{name} bytes differ: {digest} != {binding["sha256"]}')
    origins[name]=str(origin)
    spec_origins[name]=str(spec_origin)
    hashes[name]=digest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import SimulationResultRef
from polisyos.foundry.calibration.identifiability import _load_execute_response_matrix, IdentifiabilityDiagnosticConfig
payload=_load_execute_response_matrix(FileSystemCAS(request['cas']), ArtifactRef.model_validate(request['matrix']),
    source_ref=SimulationResultRef.model_validate(request['source']), response_slots={'balance':'government.balance'},
    parameter_center={request['parameter']:0.5}, config=IdentifiabilityDiagnosticConfig(
    simulation_reps=2,bootstrap_reps=0,profile_grid_size=0,seed=29,finite_diff_rel_step=0.01))
print(json.dumps({'jacobian':payload['jacobian'],'profile':payload['response_basis']['profile'],
    'gate_eligible':payload['response_basis']['gate_eligible'],'origins':origins,
    'spec_origins':spec_origins,'sha256':hashes,'executable':str(pathlib.Path(sys.executable).absolute())}))
"""
    result = subprocess.run(
        [sys.executable, "-c", child, request],
        capture_output=True,
        text=True,
        timeout=60,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    answer = json.loads(result.stdout.strip().splitlines()[-1])
    assert answer["jacobian"][0][0] == pytest.approx(4.0, rel=2e-5)
    assert answer["gate_eligible"] is False
    assert answer["executable"] == str(Path(sys.executable).absolute())
    expected_origins = {name: binding["origin"] for name, binding in expected_sources.items()}
    expected_hashes = {name: binding["sha256"] for name, binding in expected_sources.items()}
    assert answer["origins"] == expected_origins
    assert answer["spec_origins"] == expected_origins
    assert answer["sha256"] == expected_hashes
    print("FRESH_CHILD_REQUEST=" + request)
    print(
        "FRESH_CHILD_RESULT="
        + json.dumps(
            {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "executable": sys.executable,
            }
        )
    )
    print("FRESH_CHILD_RESPONSE=" + json.dumps(answer))


def test_axis_order_is_bound_on_actual_two_slot_response(response_case):
    _, store, source, parameter, _ = response_case
    config = IdentifiabilityDiagnosticConfig(
        simulation_reps=2,
        bootstrap_reps=0,
        profile_grid_size=0,
        seed=29,
        finite_diff_rel_step=0.01,
    )
    slots = {"balance": "government.balance", "rate": "global.tax_rate"}
    diagnostic = identifiability_diagnostic(
        store,
        simulation_result_ref=source,
        observed_moment_bundle={"balance": 0.0, "rate": 0.125},
        parameter_center={parameter: 0.5},
        response_slots=slots,
        config=config,
    )
    payload = _load_execute_response_matrix(
        store,
        diagnostic.sensitivity_matrix_ref,
        source_ref=source,
        response_slots=slots,
        parameter_center={parameter: 0.5},
        config=config,
    )
    np.testing.assert_allclose(payload["jacobian"], [[4.0], [0.0]], rtol=2e-5)
    with pytest.raises(ValueError, match="basis differs"):
        _load_execute_response_matrix(
            store,
            diagnostic.sensitivity_matrix_ref,
            source_ref=source,
            response_slots=dict(reversed(list(slots.items()))),
            parameter_center={parameter: 0.5},
            config=config,
        )


def test_actual_altered_source_bytes_refuse_before_state_load(response_case, tmp_path, monkeypatch):
    import shutil

    from polisyos.core.artifacts.store import ArtifactIntegrityError

    path, original_store, source, parameter, matrix = response_case
    assert admit_execution_source(original_store, source).mode == "single_step_basis"
    copied = tmp_path / "cas"
    shutil.copytree(path / "cas", copied)
    store = FileSystemCAS(copied)
    blob, _ = store._paths(source.artifact_id)
    blob.write_bytes(blob.read_bytes() + b" ")

    def no_state(*args, **kwargs):
        pytest.fail("altered CAS source reached state load")

    monkeypatch.setattr("polisyos.foundry.execute.executor.load_state_snapshot", no_state)
    with pytest.raises(ArtifactIntegrityError) as refusal:
        _load_execute_response_matrix(
            store,
            matrix,
            source_ref=source,
            response_slots={"balance": "government.balance"},
            parameter_center={parameter: 0.5},
            config=IdentifiabilityDiagnosticConfig(
                simulation_reps=2,
                bootstrap_reps=0,
                profile_grid_size=0,
                seed=29,
                finite_diff_rel_step=0.01,
            ),
        )
    assert type(refusal.value) is ArtifactIntegrityError


def test_selected_replay_basis_view_cannot_be_downgraded(response_case, monkeypatch):
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.canon import CanonSpec
    from polisyos.foundry.calibration.identifiability import (
        _response_basis_inputs,
        _response_identity,
        _ResponseBasis,
    )

    _, store, source, parameter, matrix = response_case
    payload = from_canonical_bytes(store.get_bytes(matrix))
    basis = _ResponseBasis.model_validate(payload["response_basis"])
    record = basis.replays[-1]
    result_ref = ArtifactRef.model_validate(record.result.ref.model_dump(mode="python"))
    result_payload = from_canonical_bytes(store.get_bytes(result_ref))
    result_payload["execution_input_basis_ref"]["manifest_profile_sha256"] = None
    result_manifest = store.get_manifest(result_ref)
    inputs = [
        item.model_copy(update={"manifest_profile_sha256": None})
        if item.role == "execution_input_basis"
        else item
        for item in result_manifest.inputs
    ]
    downgraded_result_ref = store.put_json(
        result_payload,
        PutOptions(
            kind=result_ref.kind,
            media_type=result_ref.media_type,
            schema=result_manifest.artifact_schema,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    replacement = record.model_copy(
        update={"result": _response_identity(store, downgraded_result_ref)}
    )
    changed_basis = basis.model_copy(
        update={
            "replays": tuple(
                replacement if replay == record else replay for replay in basis.replays
            )
        }
    )
    changed_payload = dict(payload)
    changed_payload["response_basis"] = changed_basis.model_dump(mode="json")
    changed_matrix_ref = store.put_json(
        changed_payload,
        PutOptions(
            kind=matrix.kind,
            media_type=matrix.media_type,
            schema=store.get_manifest(matrix).artifact_schema,
            inputs=_response_basis_inputs(changed_basis),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
    )

    def no_state(*args, **kwargs):
        pytest.fail("downgraded execution-basis selected view reached state loading")

    monkeypatch.setattr("polisyos.foundry.execute.executor.load_state_snapshot", no_state)
    with pytest.raises(ValueError, match="execution_source_basis_selected_profile_missing"):
        _load_execute_response_matrix(
            store,
            changed_matrix_ref,
            source_ref=source,
            response_slots={"balance": "government.balance"},
            parameter_center={parameter: 0.5},
            config=IdentifiabilityDiagnosticConfig(
                simulation_reps=2,
                bootstrap_reps=0,
                profile_grid_size=0,
                seed=29,
                finite_diff_rel_step=0.01,
            ),
        )


@pytest.mark.parametrize("mutation", ["missing", "wrong", "duplicate", "extra"])
def test_actual_replay_manifest_lineage_is_verified(response_case, monkeypatch, mutation):
    from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
    from polisyos.core.canon import CanonSpec
    from polisyos.foundry.calibration.identifiability import (
        _response_basis_inputs,
        _response_identity,
        _ResponseBasis,
    )

    _, store, source, _, matrix = response_case
    payload = from_canonical_bytes(store.get_bytes(matrix))
    record = payload["response_basis"]["replays"][-1]
    result_ref = ArtifactRef.model_validate(record["result"]["ref"])
    result_payload = from_canonical_bytes(store.get_bytes(result_ref))
    result_manifest = store.get_manifest(result_ref)
    inputs = [item for item in result_manifest.inputs if item.role != "input.input_bindings_ref"]
    if mutation == "wrong":
        inputs.append(InputRef(artifact_id=source.artifact_id, role="input.input_bindings_ref"))
    elif mutation in {"duplicate", "extra"}:
        inputs.extend(
            item for item in result_manifest.inputs if item.role == "input.input_bindings_ref"
        )
        inputs.append(
            InputRef(
                artifact_id=source.artifact_id,
                role="input.input_bindings_ref" if mutation == "duplicate" else "unexpected.extra",
            )
        )
    corrupt_result = store.put_json(
        result_payload,
        PutOptions(
            kind=result_ref.kind,
            media_type=result_ref.media_type,
            schema=result_manifest.artifact_schema,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    record["result"] = _response_identity(store, corrupt_result).model_dump(mode="json")
    basis = _ResponseBasis.model_validate(payload["response_basis"])
    corrupt_matrix = store.put_json(
        payload,
        PutOptions(
            kind=matrix.kind,
            media_type=matrix.media_type,
            schema=store.get_manifest(matrix).artifact_schema,
            inputs=_response_basis_inputs(basis),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    def no_state(*args, **kwargs):
        pytest.fail("forged native replay lineage reached state load")

    monkeypatch.setattr("polisyos.foundry.execute.executor.load_state_snapshot", no_state)
    expected_errors = {
        "missing": "execution_source_requires_one_edge:input.input_bindings_ref",
        "wrong": "execution_source_edge_profile_missing:input.input_bindings_ref",
        "duplicate": "execution_source_simulation_result_duplicate_input_role",
        "extra": "lineage mismatch",
    }
    with pytest.raises(ValueError, match=expected_errors[mutation]):
        _read(response_case, matrix=corrupt_matrix)


@pytest.mark.parametrize("target", ["initial", "replay"])
def test_nested_state_npz_bytes_are_verified_before_state_interpretation(
    response_case, tmp_path, monkeypatch, target
):
    import shutil

    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.store import ArtifactIntegrityError
    from polisyos.core.contracts.foundry import StateSnapshot

    path, _, source, parameter, matrix = response_case
    copied = tmp_path / "cas"
    shutil.copytree(path / "cas", copied)
    store = FileSystemCAS(copied)
    assert admit_execution_source(store, source).mode == "single_step_basis"
    payload = from_canonical_bytes(store.get_bytes(matrix))
    if target == "initial":
        wrapper_ref = ArtifactRef.model_validate(
            payload["response_basis"]["source_inputs"]["bound_state"]["ref"]
        )
    else:
        result_ref = ArtifactRef.model_validate(
            payload["response_basis"]["replays"][-1]["result"]["ref"]
        )
        result = SimulationResult.model_validate(from_canonical_bytes(store.get_bytes(result_ref)))
        wrapper_ref = result.state_snapshot_ref
    wrapper = StateSnapshot.model_validate(from_canonical_bytes(store.get_bytes(wrapper_ref)))
    blob, _ = store._paths(wrapper.state_ref.artifact_id)
    blob.write_bytes(blob.read_bytes() + b" ")

    def no_state(*args, **kwargs):
        pytest.fail("unverified nested state blob reached state interpretation")

    monkeypatch.setattr("polisyos.foundry.execute.executor.load_state_snapshot", no_state)
    with pytest.raises(ArtifactIntegrityError) as refusal:
        _load_execute_response_matrix(
            store,
            matrix,
            source_ref=source,
            response_slots={"balance": "government.balance"},
            parameter_center={parameter: 0.5},
            config=IdentifiabilityDiagnosticConfig(
                simulation_reps=2,
                bootstrap_reps=0,
                profile_grid_size=0,
                seed=29,
                finite_diff_rel_step=0.01,
            ),
        )
    assert type(refusal.value) is ArtifactIntegrityError


def test_native_response_calibration_report_reaches_fresh_state_slot_consumer(tmp_path):
    store, source_simulation_ref, parameter = _native_fixture(tmp_path)
    diagnostic = _diagnostic(store, source_simulation_ref, parameter)
    assert diagnostic.diagnostic_ref is not None
    selected_simulation_ref = attach_identifiability_diagnostic_ref(
        store,
        simulation_result_ref=source_simulation_ref,
        diagnostic_ref=diagnostic.diagnostic_ref,
    )
    response = load_execute_response_basis_candidate(store, selected_simulation_ref)
    assert isinstance(response, ExecuteResponseBasisCandidate)
    registry_ref = response.source_inputs["registry"].ref
    execution_plan_ref = response.source_inputs["exec_plan"].ref
    program_graph_ref = response.source_inputs["program"].ref
    base_state_ref = StateSnapshotRef.model_validate(
        response.source_inputs["bound_state"].ref.model_dump(mode="python")
    )
    registry = load_registry_bundle_content(store, registry_ref)
    execution_plan = ExecPlan.model_validate(
        get_json_artifact(ensure_ir_artifact_store(store), execution_plan_ref)
    )
    program_graph = ProgramGraph.model_validate(
        get_json_artifact(ensure_ir_artifact_store(store), program_graph_ref)
    )
    base_state = load_state_snapshot(store, snapshot_ref=base_state_ref)

    node_id, _, parameter_id = parameter.rpartition(".")

    def load_parameter_payload(ref):
        assert isinstance(ref, ArtifactRef)
        return get_json_artifact(ensure_ir_artifact_store(store), ref)

    calibration_config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="balance",
                model_metric_path="government.balance",
                fabric_query=None,
            )
        ],
        trainables=[TrainableParamRef(node_id=node_id, param_id=parameter_id)],
        steps=1,
        max_steps=1,
        learning_rate=1e-10,
        seed=29,
        hessian={"enabled": True, "max_params": 1},
    )
    calibrator = Calibrator(
        CalibratorInputs(
            config=calibration_config,
            program_graph=program_graph,
            exec_plan=execution_plan,
            base_state=base_state,
            mechanism_registry=registry.mechanism_registry,
            slot_registry=registry.slot_registry,
            merge_registry=registry.merge_registry,
            selector_field_registry=registry.selector_field_registry,
            parameter_loader=load_parameter_payload,
            constraint_registry=registry.constraint_registry,
            raw_targets={"balance": [response.fitted_moments["balance"]]},
            controls_seq=jnp.asarray([0]),
            exec_plan_ref=execution_plan_ref,
            registry_bundle_ref=registry_ref,
            mechanism_registry_ref=response.source_inputs["registry.mechanism_registry"].ref,
            units_registry=registry.units_registry,
            units_registry_ref=response.source_inputs["registry.units_registry"].ref,
            base_state_snapshot_ref=base_state_ref,
        )
    )
    report, report_ref = calibrator.run_and_persist(store)
    assert report_ref.manifest_profile_sha256 is not None
    assert report.uncertainty_envelopes is not None
    assert parameter in report.uncertainty_envelopes
    assert report.calibrated_params[parameter] == response.parameter_center[parameter]
    report_manifest = store.get_manifest(report_ref)
    basis_edge = next(
        edge for edge in report_manifest.inputs if edge.role == "calibration_execution_input_basis"
    )
    basis_ref = ArtifactRef(
        artifact_id=basis_edge.artifact_id,
        kind="foundry.calibration_execution_input_basis",
        media_type="application/json",
        manifest_profile_sha256=basis_edge.manifest_profile_sha256,
    )
    calibration_basis = load_calibration_execution_input_basis(store, basis_ref)
    assert calibration_basis.target_inputs[0].source_kind == "caller_raw_targets"
    assert calibration_basis.source_attestation_status == "not_established"

    def execute_node(*, selected_report_ref, run_id):
        run = RunContext.start(
            store=store,
            registry_bundle=registry_ref,
            run_dir=tmp_path / run_id,
            run_id=run_id,
        )
        context = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger(f"test.execute-response-bridge.{run_id}"),
        )
        state = ExperimentState(
            run_id=run_id,
            inputs={INPUT_CALIBRATION_REPORT_REF: selected_report_ref},
            artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: selected_simulation_ref},
            params={
                "propagation_response_basis": {
                    "schema_version": "1.0",
                    "state_slot_ids": ["government.balance"],
                },
                "propagation_config": {
                    "preferred_method": "monte_carlo",
                    "mc_n_samples": 100,
                    "mc_batch_size": 100,
                    "mc_min_valid_samples": 50,
                },
            },
        )
        return PropagateUncertaintyNode().execute(context, state), state

    outcome, input_state = execute_node(selected_report_ref=report_ref, run_id="b190-positive")
    assert outcome.status == "ok"
    output_simulation_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    output_simulation = SimulationResult.model_validate(
        get_json_artifact(ensure_ir_artifact_store(store), output_simulation_ref)
    )
    output_envelope_ref = output_simulation.uncertainty_envelopes["government.balance"]
    assert output_envelope_ref.manifest_profile_sha256 is not None
    propagated_report_ref = outcome.state.artifacts_index[ARTIFACT_PROPAGATION_REPORT_REF]
    propagated_report = get_json_artifact(ensure_ir_artifact_store(store), propagated_report_ref)
    assert propagated_report["methods"] == ["monte_carlo"]
    response_claim = propagated_report["response_basis_candidate"]
    assert response_claim["evidence_grade"] == "candidate"
    assert response_claim["gate_eligible"] is False
    assert response_claim["mapping_status"] == "candidate_only"
    assert response_claim["source_inputs"] == {
        role: identity.model_dump(mode="json")
        for role, identity in sorted(response.source_inputs.items())
    }
    assert "calibration_source_attestation_not_established" in response_claim["limitation_codes"]
    assert "calibration_uncertainty_law_not_authoritative" in response_claim["limitation_codes"]
    assert "external_parameter_unit_authority_not_established" in response_claim["limitation_codes"]
    assert propagated_report["state_slot_outputs"]["government.balance"]["envelope_ref"] == (
        output_envelope_ref.model_dump(mode="json")
    )
    projection = load_simulation_result_subject_uncertainty_projection(
        ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas")),
        output_simulation_ref,
        subject_kind="state_slot",
        subject_id="government.balance",
    )
    assert projection.envelope is not None
    assert projection.envelope_ref == output_envelope_ref
    assert projection.candidate_only is True
    assert projection.gate_eligible is False
    assert "execute_response_basis_revalidation_not_performed_by_ir" in (
        projection.limitation_codes
    )
    assert "draw_success_ledger_missing" in projection.limitation_codes
    assert projection.envelope.ci_width > 0.0

    report_manifest = store.get_manifest(report_ref)
    config_edge = next(edge for edge in report_manifest.inputs if edge.role == "calibration_config")
    config_ref = ArtifactRef(
        artifact_id=config_edge.artifact_id,
        kind="foundry.calibration_config",
        media_type="application/json",
        manifest_profile_sha256=config_edge.manifest_profile_sha256,
    )
    stripped_basis_report_ref = put_calibration_report(
        store,
        report,
        inputs=[input_ref_from_artifact_ref(config_ref, role="calibration_config")],
    )
    stripped_outcome, stripped_state = execute_node(
        selected_report_ref=stripped_basis_report_ref,
        run_id="b190-missing-basis-edge",
    )
    assert stripped_outcome.status == "fail"
    assert stripped_outcome.error is not None
    assert stripped_outcome.error.code == "propagation_response_basis_invalid"
    assert "calibration_execution_input_basis" in stripped_outcome.error.message
    assert stripped_outcome.artifacts == []
    assert stripped_outcome.state.artifacts_index == stripped_state.artifacts_index

    wrong_base_state_checksum = (
        "0" * 64 if calibration_basis.base_state_checksum_sha256 != "0" * 64 else "1" * 64
    )
    corrupted_basis = type(calibration_basis).model_validate(
        {
            **calibration_basis.model_dump(mode="python"),
            "base_state_checksum_sha256": wrong_base_state_checksum,
        }
    )
    basis_input_edges = list(store.get_manifest(basis_ref).inputs)
    corrupted_basis_ref = put_calibration_execution_input_basis(
        store,
        corrupted_basis,
        inputs=basis_input_edges,
    )
    corrupted_basis_report_ref = put_calibration_report(
        store,
        report,
        inputs=[
            input_ref_from_artifact_ref(config_ref, role="calibration_config"),
            input_ref_from_artifact_ref(
                corrupted_basis_ref,
                role="calibration_execution_input_basis",
            ),
        ],
    )
    corrupted_basis_outcome, corrupted_basis_state = execute_node(
        selected_report_ref=corrupted_basis_report_ref,
        run_id="b190-corrupted-base-state-checksum",
    )
    assert corrupted_basis_outcome.status == "fail"
    assert corrupted_basis_outcome.error is not None
    assert corrupted_basis_outcome.error.code == "propagation_response_basis_invalid"
    assert "base_state_checksum_sha256 digest mismatch" in (corrupted_basis_outcome.error.message)
    assert corrupted_basis_outcome.artifacts == []
    assert corrupted_basis_outcome.state.artifacts_index == corrupted_basis_state.artifacts_index

    parameter_input_index = next(
        index
        for index, item in enumerate(calibration_basis.parameter_inputs)
        if item.node_id == node_id and parameter_id in item.parameter_ids
    )
    parameter_input = calibration_basis.parameter_inputs[parameter_input_index]
    assert parameter_input.source_ref is not None
    assert diagnostic.diagnostic_ref.manifest_profile_sha256 is not None
    corrupted_parameter_inputs = list(calibration_basis.parameter_inputs)
    corrupted_parameter_inputs[parameter_input_index] = type(parameter_input).model_validate(
        {
            **parameter_input.model_dump(mode="python"),
            "source_ref": diagnostic.diagnostic_ref.model_dump(mode="python"),
        }
    )
    corrupted_parameter_basis = type(calibration_basis).model_validate(
        {
            **calibration_basis.model_dump(mode="python"),
            "parameter_inputs": corrupted_parameter_inputs,
        }
    )
    parameter_edge_role = f"parameter_input.{parameter_input.ordinal}"
    corrupted_parameter_edges = [
        input_ref_from_artifact_ref(diagnostic.diagnostic_ref, role=parameter_edge_role)
        if edge.role == parameter_edge_role
        else edge
        for edge in basis_input_edges
    ]
    corrupted_parameter_basis_ref = put_calibration_execution_input_basis(
        store,
        corrupted_parameter_basis,
        inputs=corrupted_parameter_edges,
    )
    corrupted_parameter_report_ref = put_calibration_report(
        store,
        report,
        inputs=[
            input_ref_from_artifact_ref(config_ref, role="calibration_config"),
            input_ref_from_artifact_ref(
                corrupted_parameter_basis_ref,
                role="calibration_execution_input_basis",
            ),
        ],
    )
    corrupted_parameter_outcome, corrupted_parameter_state = execute_node(
        selected_report_ref=corrupted_parameter_report_ref,
        run_id="b190-foreign-parameter-input-source",
    )
    assert corrupted_parameter_outcome.status == "fail"
    assert corrupted_parameter_outcome.error is not None
    assert corrupted_parameter_outcome.error.code == "propagation_response_basis_invalid"
    assert "parameter input source differs from program node" in (
        corrupted_parameter_outcome.error.message
    )
    assert corrupted_parameter_outcome.artifacts == []
    assert (
        corrupted_parameter_outcome.state.artifacts_index
        == corrupted_parameter_state.artifacts_index
    )

    envelope = report.uncertainty_envelopes[parameter]
    change = (
        min(
            envelope.ci_upper - envelope.point_estimate,
            envelope.point_estimate - envelope.ci_lower,
        )
        / 4
    )
    assert change > 0.0
    altered_payload = envelope.model_dump(mode="python")
    altered_payload["point_estimate"] = envelope.point_estimate + change
    if isinstance(altered_payload["distribution_payload"], dict):
        altered_payload["distribution_payload"]["parameters"]["mean"] += change
    altered_envelope = type(envelope).model_validate(altered_payload)
    report_payload = report.model_dump(mode="python")
    report_payload["uncertainty_envelopes"] = {
        **report.uncertainty_envelopes,
        parameter: altered_envelope,
    }
    altered_report = CalibrationReport.model_validate(report_payload)
    altered_report_ref = put_calibration_report(
        store,
        altered_report,
        inputs=[
            input_ref_from_artifact_ref(config_ref, role="calibration_config"),
            input_ref_from_artifact_ref(
                basis_ref,
                role="calibration_execution_input_basis",
            ),
        ],
    )
    altered_outcome, altered_state = execute_node(
        selected_report_ref=altered_report_ref,
        run_id="b190-mutated-envelope-bytes",
    )
    assert altered_outcome.status == "fail"
    assert altered_outcome.error is not None
    assert altered_outcome.error.code == "propagation_response_basis_invalid"
    assert "calibration envelope changed" in altered_outcome.error.message
    assert altered_outcome.artifacts == []
    assert altered_outcome.state.artifacts_index == altered_state.artifacts_index

    profileless_report_ref = ArtifactRef(
        artifact_id=report_ref.artifact_id,
        kind=report_ref.kind,
        media_type=report_ref.media_type,
    )
    profileless_outcome, profileless_state = execute_node(
        selected_report_ref=profileless_report_ref,
        run_id="b190-profileless-report-ref",
    )
    assert profileless_outcome.status == "fail"
    assert profileless_outcome.error is not None
    assert profileless_outcome.error.code == "propagation_response_basis_invalid"
    assert "does not select a manifest profile" in profileless_outcome.error.message
    assert profileless_outcome.artifacts == []
    assert profileless_outcome.state.artifacts_index == profileless_state.artifacts_index
