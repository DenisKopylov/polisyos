from __future__ import annotations

import copy
import json
import logging
import os
import subprocess
import sys
from fractions import Fraction

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
    _load_propagated_envelopes,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROPAGATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


@pytest.mark.parametrize("partial", [False, True])
def test_propagate_uncertainty_node_updates_simulation_result(tmp_path, partial) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_prop")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.propagate"))

    env_ref = persist_uncertainty_envelope(
        store,
        UncertaintyEnvelope(
            point_estimate=1.0,
            confidence_interval=(0.8, 1.2),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.TRUST,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        ),
    )

    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=state_snapshot_ref,
            uncertainty_envelope_ref=env_ref,
        ),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )

    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"applied_nodes": 1, "step_latency_ms": 12}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_prop",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id),
        },
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref,
        },
        params={
            "propagation_mc_n_samples": 100,
            "propagation_mc_batch_size": 100,
            "propagation_sensitivity": {
                "applied_nodes": {"data_snapshot": 1.0},
                **({"step_latency_ms": {"data_snapshot": 1.0}} if not partial else {}),
            },
        },
    )

    outcome = PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"

    updated_sim_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    payload = from_canonical_bytes(store.get_bytes(updated_sim_ref.artifact_id))
    updated_sim = SimulationResult.model_validate(payload)

    assert updated_sim.uncertainty_envelopes is not None
    assert set(updated_sim.uncertainty_envelopes.keys()) == {"applied_nodes", "step_latency_ms"}
    assert ARTIFACT_PROPAGATION_REPORT_REF in outcome.state.artifacts_index

    report_ref = outcome.state.artifacts_index[ARTIFACT_PROPAGATION_REPORT_REF]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report["methods"] == [PropagationMethod.DELTA_METHOD.value] * 2
    envelopes = _load_propagated_envelopes(store, updated_sim_ref)
    assert all(env.gate_eligible is False for env in envelopes.values())
    assert envelopes["applied_nodes"].distribution_family is DistributionFamily.NORMAL
    assert envelopes["applied_nodes"].metadata["output_std"] > 0
    if partial:
        gap = envelopes["step_latency_ms"]
        assert gap.distribution_family is DistributionFamily.UNKNOWN
        assert gap.confidence_level is None
        assert gap.metadata["failure"] == "missing_output"
        assert report["missing_output_metric_ids"] == ["step_latency_ms"]
        assert report["incomplete_output_metric_ids"] == ["step_latency_ms"]
        assert report["full_mapping_established"] is False


def _native_fixture(tmp_path, *, reported_income=(2.0, 2.0), initial_balance=-2.0):
    from decimal import Decimal

    import jax.numpy as jnp

    from polisyos.core.contracts.foundry import (
        CompileRequest,
        ExecPlan,
        ExecuteRequest,
        FoundryExecConfig,
        FoundryInputBindings,
        FoundryInputBindingsRef,
        ProgramGraph,
        StateSnapshotRef,
    )
    from polisyos.foundry.compile.api import compile as compile_foundry
    from polisyos.foundry.contracts.state import GlobalState
    from polisyos.foundry.execute.api import execute as execute_foundry
    from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle

    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store)
    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="response", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="response",
            interventions=[
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
            ],
        ),
        model_spec=ModelSpec(
            model_id="response",
            data_snapshot_ref="sha256:" + "0" * 64,
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        policy,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=policy.schema_version),
        ),
    )
    compiled = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry.bundle_ref,
        ),
    )
    assert compiled.ok
    plan = ExecPlan.model_validate(from_canonical_bytes(store.get_bytes(compiled.exec_plan_ref)))
    program = ProgramGraph.model_validate(from_canonical_bytes(store.get_bytes(plan.program_ref)))
    tax_node = next(node for node in program.nodes if node.mechanism_type == "income_tax")
    state = GlobalState.empty(n_agents=2, n_firms=1)
    state = state.replace(
        agents=state.agents.replace(
            active=jnp.asarray([True, True]),
            income=jnp.asarray([10.0, 10.0]),
            reported_income=jnp.asarray(reported_income),
        ),
        government_balance=jnp.asarray(initial_balance),
        tax_rate=jnp.asarray(0.125),
    )
    snapshot = put_state_snapshot(store, state=state, step=0)
    state_ref = StateSnapshotRef(artifact_id=snapshot.artifact_id)
    data_ref = store.put_json(
        DataSnapshot(data_ref=state_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
        ),
    )
    bindings = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_ref,
            registry_bundle_ref=registry.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_ref,
        ),
        PutOptions(kind="foundry.input_bindings", media_type="application/json"),
    )
    result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compiled.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=bindings.artifact_id),
            registry_bundle_ref=registry.bundle_ref,
            exec_config=FoundryExecConfig(seed=29),
        ),
    )
    assert result.ok
    simulation = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(result.simulation_result_ref))
    )
    poststate = load_state_snapshot(store, snapshot_ref=simulation.state_snapshot_ref)
    assert float(poststate.government_balance) == pytest.approx(
        sum(reported_income) / 2 + initial_balance
    )
    return store, result.simulation_result_ref, f"{tax_node.node_id}.rate"


def _persist_test_law(store, envelope, *, inputs=None):
    from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
    from polisyos.core.canon import CanonSpec

    ref = store.put_json(
        envelope.model_dump(mode="python", round_trip=True),
        PutOptions(
            kind="ir.uncertainty_envelope",
            media_type="application/json",
            schema=SchemaInfo(name="ir.uncertainty_envelope", version="1.1"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected = ref.model_copy(
        update={
            "manifest_profile_sha256": ManifestLifecycle.profile_sha256(store.get_manifest(ref))
        }
    )
    store.get_manifest(selected)
    return selected


@pytest.fixture(scope="module")
def native_cases(tmp_path_factory):
    from polisyos.foundry.calibration.identifiability import (
        IdentifiabilityDiagnosticConfig,
        identifiability_diagnostic,
    )

    cases = {}
    for name, incomes, initial in (
        ("zero", (2.0, 2.0), -2.0),
        ("nonzero", (2.0, 2.0), -1.0),
        ("scaled", (2000.0, 2000.0), -2.0),
    ):
        path = tmp_path_factory.mktemp(f"native_node_{name}")
        store, source, parameter = _native_fixture(
            path, reported_income=incomes, initial_balance=initial
        )
        diagnostic_config = IdentifiabilityDiagnosticConfig(
            simulation_reps=2,
            bootstrap_reps=0,
            profile_grid_size=0,
            seed=29,
            finite_diff_rel_step=0.01,
        )
        slots = {"balance": "government.balance", "tax_rate": "global.tax_rate"}
        diagnostic = identifiability_diagnostic(
            store,
            simulation_result_ref=source,
            observed_moment_bundle={"balance": sum(incomes) / 2 + initial, "tax_rate": 0.125},
            parameter_center={parameter: 0.5},
            response_slots=slots,
            config=diagnostic_config,
        )
        matrix = diagnostic.sensitivity_matrix_ref
        payload = from_canonical_bytes(store.get_bytes(matrix))
        env = UncertaintyEnvelope(
            point_estimate=0.5,
            confidence_interval=(0.0, 1.0),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.TRUST,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            gate_eligible=False,
            metadata={
                "param_name": parameter,
                "unit": payload["response_basis"]["parameter_units"][parameter],
                "std": 0.25,
                "law_scope": "declared_synthetic_normal",
            },
        )
        law = _persist_test_law(store, env)
        params = {
            "propagation_response_basis": {
                "matrix_ref": matrix.model_dump(mode="json"),
                "response_slots": slots,
                "response_units": payload["response_basis"]["moment_units"],
                "parameter_center": {parameter: 0.5},
                "diagnostic_config": diagnostic_config.model_dump(mode="json"),
            },
            "propagation_response_slots": slots,
            "propagation_input_envelope_refs": {parameter: law.model_dump(mode="json")},
            "propagation_config": {"preferred_method": "delta", "delta_covariance_jitter": 0.0},
        }
        cases[name] = (path, store, source, parameter, params)
    return cases


def _node(case, *, params=None, source=None):
    _, store, original, _, expected = case
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="R_native_response")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.native_response"))
    state = ExperimentState(
        run_id="R_native_response",
        params=copy.deepcopy(expected if params is None else params),
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: original if source is None else source},
    )
    return PropagateUncertaintyNode().execute(ctx, state)


def _persisted(case, outcome):
    store = FileSystemCAS(case[0] / "cas")
    assert outcome.status == "ok"
    ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    simulation = SimulationResult.model_validate(from_canonical_bytes(store.get_bytes(ref)))
    report = from_canonical_bytes(store.get_bytes(simulation.propagation_report_ref))
    envelopes = _load_propagated_envelopes(store, ref)
    return store, simulation, report, envelopes


@pytest.mark.parametrize(
    "case_name,baseline,variance",
    [
        ("zero", 0.0, Fraction(1)),
        ("nonzero", 1.0, Fraction(1)),
        ("scaled", 1998.0, Fraction(1000000)),
    ],
)
def test_native_node_dimensioned_response_and_constant(native_cases, case_name, baseline, variance):
    case = native_cases[case_name]
    _, simulation, report, envelopes = _persisted(case, _node(case))
    assert set(envelopes) == {"balance", "tax_rate"}
    assert envelopes["balance"].point_estimate == pytest.approx(baseline)
    row = next(
        item["diagnostics"] for item in report["diagnostics"] if item["metric_id"] == "balance"
    )
    assert row["output_variance"] == pytest.approx(float(variance), rel=2e-5)
    assert envelopes["tax_rate"].point_estimate == pytest.approx(0.125)
    assert envelopes["tax_rate"].confidence_interval == (0.125, 0.125)
    assert envelopes["tax_rate"].metadata["verified_zero_jacobian"] is True
    assert envelopes["tax_rate"].metadata["constant_scope"] == "local_linearized_response"
    assert envelopes["tax_rate"].metadata["global_constancy"] == "not_established"
    assert all(env.gate_eligible is False for env in envelopes.values())
    assert envelopes["balance"].interval_semantics is IntervalSemantics.HEURISTIC_RANGE
    assert report["response_basis"]["source_ref"]["artifact_id"] == str(case[2].artifact_id)
    assert report["full_mapping_established"] is True
    assert report["gate_eligible"] is False
    assert "applied_nodes" not in simulation.uncertainty_envelopes


def test_native_node_partial_requested_outputs_keep_known(native_cases):
    case = native_cases["zero"]
    params = copy.deepcopy(case[4])
    params["propagation_response_slots"]["unknown"] = "not.registered"
    store, sim, report, envelopes = _persisted(case, _node(case, params=params))
    assert envelopes["balance"].metadata["output_std"] == pytest.approx(1.0, rel=2e-5)
    assert envelopes["tax_rate"].point_estimate == pytest.approx(0.125)
    assert envelopes["unknown"].distribution_family is DistributionFamily.UNKNOWN
    assert envelopes["unknown"].metadata["failure"] == "missing_output"
    assert envelopes["unknown"].confidence_level is None
    assert report["output_metric_count"] == 3
    assert report["missing_output_metric_ids"] == ["unknown"]
    assert report["unmapped_metric_ids"] == ["unknown"]
    assert report["full_mapping_established"] is False
    assert report["response_basis"]["requested_slots"]["unknown"] == "not.registered"
    roles = {item.role: item for item in store.get_manifest(sim.propagation_report_ref).inputs}
    assert roles["response_matrix"].manifest_profile_sha256 == case[4][
        "propagation_response_basis"
    ]["matrix_ref"].get("manifest_profile_sha256")
    assert set(roles) == {
        "base_simulation_result",
        "response_matrix",
        "propagation_config",
        f"input_envelope.{case[3]}",
    }


def test_native_node_missing_law_keeps_verified_constant(native_cases):
    case = native_cases["zero"]
    params = copy.deepcopy(case[4])
    params["propagation_input_envelope_refs"] = {}
    _, _, report, envelopes = _persisted(case, _node(case, params=params))
    assert envelopes["balance"].distribution_family is DistributionFamily.UNKNOWN
    assert report["full_mapping_established"] is False
    assert envelopes["tax_rate"].confidence_interval == (0.125, 0.125)
    assert envelopes["tax_rate"].metadata["verified_zero_jacobian"] is True
    assert envelopes["tax_rate"].metadata["constant_scope"] == "local_linearized_response"
    assert envelopes["tax_rate"].metadata["global_constancy"] == "not_established"


@pytest.mark.parametrize(
    "fault", ["target", "order", "units", "center", "config", "matrix_ref", "extra_input", "source"]
)
def test_native_node_exact_basis_refuses_counterfeits(native_cases, fault):
    case = native_cases["zero"]
    params = copy.deepcopy(case[4])
    source = None
    if fault == "target":
        params["propagation_response_slots"]["balance"] = "global.tax_rate"
    elif fault == "order":
        params["propagation_response_basis"]["response_slots"] = dict(
            reversed(list(params["propagation_response_basis"]["response_slots"].items()))
        )
    elif fault == "units":
        params["propagation_response_basis"]["response_units"]["balance"]["currency"] = "EUR"
    elif fault == "center":
        params["propagation_response_basis"]["parameter_center"][case[3]] = 0.25
    elif fault == "config":
        params["propagation_response_basis"]["diagnostic_config"]["seed"] = 30
    elif fault == "matrix_ref":
        params["propagation_response_basis"]["matrix_ref"]["artifact_id"] = "sha256:" + "f" * 64
    elif fault == "extra_input":
        params["propagation_input_envelope_refs"]["invented.axis"] = next(
            iter(params["propagation_input_envelope_refs"].values())
        )
    elif fault == "source":
        store = case[1]
        payload = from_canonical_bytes(store.get_bytes(case[2]))
        payload["notes"] = [*payload["notes"], "different-current-source"]
        manifest = store.get_manifest(case[2])
        source = store.put_json(
            payload,
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                inputs=manifest.inputs,
            ),
        )
    with pytest.raises((ValueError, RuntimeError, OSError, KeyError)):
        _node(case, params=params, source=source)


@pytest.mark.parametrize("fault", ["unit", "axis", "center"])
def test_native_node_refuses_new_valid_cas_wrong_law(native_cases, fault):
    case = native_cases["zero"]
    params = copy.deepcopy(case[4])
    store = case[1]
    from polisyos.core.artifacts.manifest import ArtifactRef

    ref = ArtifactRef.model_validate(params["propagation_input_envelope_refs"][case[3]])
    payload = from_canonical_bytes(store.get_bytes(ref))
    if fault == "unit":
        payload["metadata"]["unit"] = {"kind": "money", "currency": "USD"}
    elif fault == "axis":
        payload["metadata"]["param_name"] = "invented.axis"
    else:
        payload["point_estimate"] = 0.25
    forged = _persist_test_law(store, UncertaintyEnvelope.model_validate(payload))
    params["propagation_input_envelope_refs"][case[3]] = forged.model_dump(mode="json")
    with pytest.raises(ValueError, match="parameter/unit/center"):
        _node(case, params=params)


def test_native_node_fresh_child_reads_actual_partial_report(native_cases):
    case = native_cases["zero"]
    params = copy.deepcopy(case[4])
    params["propagation_response_slots"]["unknown"] = "not.registered"
    outcome = _node(case, params=params)
    ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    script = "import json,sys\nfrom polisyos.core.artifacts.store import FileSystemCAS\nfrom polisyos.core.canon import from_canonical_bytes\nfrom polisyos.core.contracts.foundry import SimulationResultRef,SimulationResult\nfrom polisyos.ir.analytics.uncertainty import UncertaintyEnvelope,DistributionFamily\nfrom polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import _load_propagated_envelopes\nstore=FileSystemCAS(sys.argv[1]);ref=SimulationResultRef.model_validate(json.loads(sys.argv[2]))\nsim=SimulationResult.model_validate(from_canonical_bytes(store.get_bytes(ref)))\nreport=from_canonical_bytes(store.get_bytes(sim.propagation_report_ref))\nenvs=_load_propagated_envelopes(store,ref)\nassert report['full_mapping_established'] is False\nassert envs['unknown'].distribution_family is DistributionFamily.UNKNOWN\nassert abs(envs['balance'].metadata['output_std']-1)<1e-4\nassert envs['tax_rate'].confidence_interval==(0.125,0.125)\nassert all(not x.gate_eligible for x in envs.values())\nprint(json.dumps({'known':['balance','tax_rate'],'unavailable':['unknown'],'gate_eligible':False}))\n"
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(case[0] / "cas"),
            json.dumps(ref.model_dump(mode="json")),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    assert json.loads(child.stdout.strip().splitlines()[-1])["gate_eligible"] is False


def test_native_node_wrong_selected_manifest_refuses(native_cases):
    case = native_cases["zero"]
    params = copy.deepcopy(case[4])
    params["propagation_response_basis"]["matrix_ref"]["manifest_profile_sha256"] = (
        "sha256:" + "f" * 64
    )
    with pytest.raises((ValueError, RuntimeError, OSError, KeyError)):
        _node(case, params=params)


def test_native_node_refuses_new_cas_forged_jacobian(native_cases):
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.canon import CanonSpec

    case = native_cases["zero"]
    store = case[1]
    params = copy.deepcopy(case[4])
    matrix = ArtifactRef.model_validate(params["propagation_response_basis"]["matrix_ref"])
    payload = from_canonical_bytes(store.get_bytes(matrix))
    payload["jacobian"][0][0] = 0.0
    manifest = store.get_manifest(matrix)
    forged = store.put_json(
        payload,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    params["propagation_response_basis"]["matrix_ref"] = forged.model_dump(mode="json")
    with pytest.raises(ValueError, match="persisted-state finite differences"):
        _node(case, params=params)


def test_native_node_preserves_selected_law_view(native_cases):
    from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref

    case = native_cases["zero"]
    params = copy.deepcopy(case[4])
    store = case[1]
    original = ArtifactRef.model_validate(params["propagation_input_envelope_refs"][case[3]])
    law = UncertaintyEnvelope.model_validate(from_canonical_bytes(store.get_bytes(original)))
    selected = _persist_test_law(
        store,
        law,
        inputs=[input_ref_from_artifact_ref(case[2], role="declared_synthetic_fixture_source")],
    )
    assert selected.artifact_id == original.artifact_id
    assert selected.manifest_profile_sha256 != original.manifest_profile_sha256
    params["propagation_input_envelope_refs"][case[3]] = selected.model_dump(mode="json")
    outcome = _node(case, params=params)
    reopened, sim, report, envelopes = _persisted(case, outcome)
    assert envelopes["balance"].metadata["output_std"] == pytest.approx(1.0, rel=2e-5)
    envelope_edges = [
        item
        for item in reopened.get_manifest(
            outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
        ).inputs
        if item.role.startswith("metric_envelope.")
    ]
    output_refs = [
        ArtifactRef(
            artifact_id=edge.artifact_id,
            kind="ir.uncertainty_envelope",
            media_type="application/json",
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )
        for edge in envelope_edges
    ]
    for ref in [sim.propagation_report_ref, *output_refs]:
        inputs = reopened.get_manifest(ref).inputs
        matches = [item for item in inputs if item.role == f"input_envelope.{case[3]}"]
        assert matches == [input_ref_from_artifact_ref(selected, role=f"input_envelope.{case[3]}")]


@pytest.mark.parametrize(
    "owned_role", ["metric_envelope.balance", "propagation_config", "propagation_report"]
)
@pytest.mark.parametrize("fault", ["missing", "duplicate", "extra", "foreign", "strip_selector"])
def test_native_output_reader_refuses_incomplete_manifest_roster(
    native_cases, fault, owned_role, monkeypatch
):
    from polisyos.core.artifacts.manifest import InputRef

    case = native_cases["zero"]
    outcome = _node(case)
    store = case[1]
    ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    payload = from_canonical_bytes(store.get_bytes(ref))
    manifest = store.get_manifest(ref)
    inputs = list(manifest.inputs)
    edge = next(item for item in inputs if item.role == owned_role)
    if fault == "missing":
        inputs.remove(edge)
    elif fault == "duplicate":
        inputs.append(edge)
    elif fault == "extra":
        inputs.append(edge.model_copy(update={"role": "metric_envelope.invented"}))
    elif fault == "strip_selector":
        assert edge.manifest_profile_sha256 is not None
        inputs[inputs.index(edge)] = edge.model_copy(update={"manifest_profile_sha256": None})
    else:
        inputs[inputs.index(edge)] = InputRef(artifact_id=case[2].artifact_id, role=edge.role)
    selected = store.put_json(
        payload,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=inputs,
        ),
    )
    from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle

    selected = selected.model_copy(
        update={
            "manifest_profile_sha256": ManifestLifecycle.profile_sha256(
                store.get_manifest(selected)
            )
        }
    )
    original_get = store.get_bytes

    def before_load(arg):
        if getattr(arg, "kind", None) == "ir.uncertainty_envelope":
            raise AssertionError("roster refusal must precede envelope interpretation")
        return original_get(arg)

    monkeypatch.setattr(store, "get_bytes", before_load)
    with pytest.raises(ValueError, match="roster|owned view"):
        _load_propagated_envelopes(store, selected)


def test_native_standalone_outputs_bind_exact_propagation_config(native_cases):
    from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref

    case = native_cases["zero"]
    outcome = _node(case)
    store, simulation, report, _ = _persisted(case, outcome)
    config_ref = simulation.propagation_config_ref
    assert report["response_basis"]["propagation_config_ref"] == config_ref.model_dump(mode="json")
    assert report["response_basis"]["propagation_config"]["delta_covariance_jitter"] == 0.0
    sim_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    output_refs = [
        ArtifactRef(
            artifact_id=edge.artifact_id,
            kind="ir.uncertainty_envelope",
            media_type="application/json",
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )
        for edge in store.get_manifest(sim_ref).inputs
        if edge.role.startswith("metric_envelope.")
    ]
    for ref in [simulation.propagation_report_ref, *output_refs]:
        assert [
            edge for edge in store.get_manifest(ref).inputs if edge.role == "propagation_config"
        ] == [input_ref_from_artifact_ref(config_ref, role="propagation_config")]


def test_finite_output_reader_allows_equal_ids_on_distinct_owned_aliases(native_cases):
    case = native_cases["zero"]
    outcome = _node(case)
    store = case[1]
    ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    payload = from_canonical_bytes(store.get_bytes(ref))
    manifest = store.get_manifest(ref)
    # Two roles can genuinely name the same distribution content. Exactness
    # concerns alias-owned roles/views, not a false uniqueness rule on hashes.
    constant = payload["uncertainty_envelopes"]["tax_rate"]
    payload["uncertainty_envelopes"] = {"constant_a": constant, "constant_b": constant}
    edge = next(item for item in manifest.inputs if item.role == "metric_envelope.tax_rate")
    inputs = [item for item in manifest.inputs if not item.role.startswith("metric_envelope.")]
    inputs.extend(
        edge.model_copy(update={"role": f"metric_envelope.{name}"})
        for name in ("constant_a", "constant_b")
    )
    selected = store.put_json(
        payload,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=inputs,
        ),
    )
    from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle

    selected = selected.model_copy(
        update={
            "manifest_profile_sha256": ManifestLifecycle.profile_sha256(
                store.get_manifest(selected)
            )
        }
    )
    envelopes = _load_propagated_envelopes(store, selected)
    assert set(envelopes) == {"constant_a", "constant_b"}
    assert all(env.confidence_interval == (0.125, 0.125) for env in envelopes.values())


def test_native_node_refuses_supplied_law_without_selected_view(native_cases, monkeypatch):
    case = native_cases["zero"]
    params = copy.deepcopy(case[4])
    params["propagation_input_envelope_refs"][case[3]].pop("manifest_profile_sha256")

    def no_matrix_interpretation(*args, **kwargs):
        raise AssertionError("incomplete input-law view must refuse before matrix interpretation")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty._load_execute_response_matrix",
        no_matrix_interpretation,
    )
    with pytest.raises(ValueError, match="exact selected manifest"):
        _node(case, params=params)


def test_finite_output_reader_refuses_unselected_top_before_bytes(native_cases, monkeypatch):
    case = native_cases["zero"]
    outcome = _node(case)
    ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    assert ref.manifest_profile_sha256 is not None
    incomplete = ref.model_copy(update={"manifest_profile_sha256": None})

    def before_load(arg):
        raise AssertionError("unselected container refusal must precede any bytes")

    monkeypatch.setattr(case[1], "get_bytes", before_load)
    with pytest.raises(ValueError, match="SimulationResult requires an exact selected"):
        _load_propagated_envelopes(case[1], incomplete)


@pytest.mark.parametrize(
    "fault", ["config_selector", "law_selector", "law_duplicate", "law_missing"]
)
def test_finite_output_reader_refuses_changed_output_input_views(native_cases, fault, monkeypatch):
    from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
    from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref

    case = native_cases["zero"]
    outcome = _node(case)
    store = case[1]
    sim_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    sim_manifest = store.get_manifest(sim_ref)
    sim_payload = from_canonical_bytes(store.get_bytes(sim_ref))
    edge = next(item for item in sim_manifest.inputs if item.role == "metric_envelope.balance")
    envelope_ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind="ir.uncertainty_envelope",
        media_type="application/json",
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    envelope_manifest = store.get_manifest(envelope_ref)
    inputs = list(envelope_manifest.inputs)
    role = "propagation_config" if fault == "config_selector" else f"input_envelope.{case[3]}"
    changed = next(item for item in inputs if item.role == role)
    if fault == "law_duplicate":
        inputs.append(changed)
    elif fault == "law_missing":
        inputs.remove(changed)
    else:
        inputs[inputs.index(changed)] = changed.model_copy(update={"manifest_profile_sha256": None})
    envelope_ref = store.put_json(
        from_canonical_bytes(store.get_bytes(envelope_ref)),
        PutOptions(
            kind=envelope_manifest.kind,
            media_type=envelope_manifest.media_type,
            schema=envelope_manifest.artifact_schema,
            inputs=inputs,
        ),
    )
    envelope_ref = envelope_ref.model_copy(
        update={
            "manifest_profile_sha256": ManifestLifecycle.profile_sha256(
                store.get_manifest(envelope_ref)
            )
        }
    )
    sim_inputs = [
        item
        if item.role != edge.role
        else input_ref_from_artifact_ref(envelope_ref, role=edge.role)
        for item in sim_manifest.inputs
    ]
    selected = store.put_json(
        sim_payload,
        PutOptions(
            kind=sim_manifest.kind,
            media_type=sim_manifest.media_type,
            schema=sim_manifest.artifact_schema,
            inputs=sim_inputs,
        ),
    )
    selected = selected.model_copy(
        update={
            "manifest_profile_sha256": ManifestLifecycle.profile_sha256(
                store.get_manifest(selected)
            )
        }
    )
    original_get = store.get_bytes

    def before_load(arg):
        if getattr(arg, "kind", None) == "ir.uncertainty_envelope":
            raise AssertionError("view refusal must precede envelope interpretation")
        return original_get(arg)

    monkeypatch.setattr(store, "get_bytes", before_load)
    with pytest.raises(ValueError, match="config owned view|input law"):
        _load_propagated_envelopes(store, selected)
