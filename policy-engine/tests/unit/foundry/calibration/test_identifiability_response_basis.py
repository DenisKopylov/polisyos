"""Execute-backed local sensitivity binds real state, units, axes and CAS lineage."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlan,
    ExecuteRequest,
    FoundryExecConfig,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    ProgramGraph,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.calibration.identifiability import (
    IdentifiabilityDiagnosticConfig,
    _load_execute_response_matrix,
    identifiability_diagnostic,
)
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle


def _native_fixture(tmp_path, *, reported_income=(2.0, 2.0), store=None):
    store = FileSystemCAS(tmp_path / "cas") if store is None else store
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
        government_balance=jnp.asarray(-2.0),
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


def test_fresh_reader_recomputes_actual_native_response(tmp_path):
    store, simulation_ref, parameter = _native_fixture(tmp_path)
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
    np.testing.assert_allclose(payload["jacobian"], [[4.0]], rtol=2e-5)


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
            response_slots={"balance": "government.balance", "unknown": "not.registered"},
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
    import json
    import os
    import subprocess
    import sys

    path, _, source, parameter, matrix = response_case
    request = json.dumps(
        {
            "cas": str(path / "cas"),
            "source": source.model_dump(mode="json"),
            "matrix": matrix.model_dump(mode="json"),
            "parameter": parameter,
        }
    )
    child = r"""
import json, sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import SimulationResultRef
from polisyos.foundry.calibration.identifiability import _load_execute_response_matrix, IdentifiabilityDiagnosticConfig
request=json.loads(sys.argv[1])
payload=_load_execute_response_matrix(FileSystemCAS(request['cas']), ArtifactRef.model_validate(request['matrix']),
    source_ref=SimulationResultRef.model_validate(request['source']), response_slots={'balance':'government.balance'},
    parameter_center={request['parameter']:0.5}, config=IdentifiabilityDiagnosticConfig(
    simulation_reps=2,bootstrap_reps=0,profile_grid_size=0,seed=29,finite_diff_rel_step=0.01))
print(json.dumps({'jacobian':payload['jacobian'],'profile':payload['response_basis']['profile'],'gate_eligible':payload['response_basis']['gate_eligible']}))
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
        simulation_reps=2, bootstrap_reps=0, profile_grid_size=0, seed=29, finite_diff_rel_step=0.01
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

    path, _, source, parameter, matrix = response_case
    copied = tmp_path / "cas"
    shutil.copytree(path / "cas", copied)
    store = FileSystemCAS(copied)
    blob, _ = store._paths(source.artifact_id)
    blob.write_bytes(blob.read_bytes() + b" ")

    def no_state(*args, **kwargs):
        pytest.fail("altered CAS source reached state load")

    monkeypatch.setattr("polisyos.foundry.execute.executor.load_state_snapshot", no_state)
    with pytest.raises(ArtifactIntegrityError):
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
    with pytest.raises(ValueError, match="lineage mismatch"):
        _read(response_case, matrix=corrupt_matrix)
