"""B222: the existing fit helper reaches native CAS query/twin consumers.

This is an explicit synthetic/manual compatibility profile, not the selected
DoWhy backend, a new nonlinear Hybrid default, or real-data causal authority.
"""

import json
import os
import subprocess
import sys

import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.catalog.causal.gcm_fit import _fit_additive_noise_poly
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData, TwinNetworkQueryData
from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import (
    CausalQuery,
    CausalQueryResult,
    load_causal_query_result,
    persist_causal_query_result,
)
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
    load_structural_causal_model_spec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.analytics.twin_network import (
    TwinNetworkResult,
    load_twin_network_result,
    persist_twin_network_result,
)
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job


def _fit_and_persist(store, *, family=MechanismFamily.ADDITIVE_NOISE):
    graph = CausalGraphModel(
        graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[CausalEdge(src="X", dst="Y")]
    )
    x = np.linspace(-2.0, 2.0, 101)
    # The source is real CAS input to the existing helper. The known DGP law
    # supplies the independent query oracle, not hand-written polynomial params.
    source = store.put_json(
        {"data": np.column_stack([x, x * x]).tolist(), "columns": ["X", "Y"]},
        PutOptions(kind="tests.polynomial_fit_rows", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    rows = np.asarray(from_canonical_bytes(store.get_bytes(source))["data"])
    parameters = _fit_additive_noise_poly(rows[:, 1], rows[:, :1], ["X"], degree=2)
    assert parameters["fit_mode"] == "additive_noise_poly"
    assert parameters["poly_coefficients"]["X^2"] == pytest.approx(1.0, abs=1e-12)
    if family is MechanismFamily.LINEAR:
        # Keep all helper-produced polynomial fields but declare an independent
        # LINEAR law. The LINEAR consumer must use 1+3X rather than those fields.
        parameters = {**parameters, "intercept": 1.0, "coefficients": {"X": 3.0}, "noise_std": 0.0}
    model = StructuralCausalModelSpec(
        schema_version="1.0",
        graph=graph,
        fitted=True,
        fit_method="manual",
        mechanisms=[
            NodeMechanism(
                variable="X",
                family=MechanismFamily.EMPIRICAL,
                family_params={
                    "mean": float(x.mean()),
                    "std": float(x.std()),
                    "observed_samples": rows[:, 0].tolist(),
                    "observed_samples_source": str(source.artifact_id),
                    "observed_sample_alignment": str(source.artifact_id),
                    "joint_sample_group": str(source.artifact_id),
                },
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=family,
                family_params=parameters,
                source=MechanismSource.DATA_FITTED,
            ),
        ],
    )
    assert model.fit_provenance is None
    ref = persist_structural_causal_model_spec(_ensure_ir_artifact_store(store), model)
    return (
        source,
        ref,
        load_structural_causal_model_spec(
            _ensure_ir_artifact_store(FileSystemCAS(store.root)), ref
        ),
    )


def _actual_job(store, method, state, slot):
    MethodRegistry.get_instance().register(method, override=True)
    source = store.put_json(
        state.model_dump(mode="json"),
        PutOptions(
            kind="tests.native_causal_input",
            media_type="application/json",
            schema=SchemaInfo(name=type(state).__name__, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    job = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=method.signature.fqn,
            input_refs={slot: source},
            method_params={"enable_dowhy_comparison": False} if method is GCMQuery else {},
            seed=19,
        ),
        cas_root=store.root,
        method_state=state,
    )
    assert not job.issues, json.dumps(job.issues, indent=2)
    assert job.method_result_ref is not None
    payload = from_canonical_bytes(store.get_bytes(job.method_result_ref))
    return job, payload


@pytest.mark.parametrize(
    "family,expected", [(MechanismFamily.ADDITIVE_NOISE, 4.0), (MechanismFamily.LINEAR, 7.0)]
)
def test_existing_polynomial_helper_to_typed_cas_real_query_and_fresh_reader(
    tmp_path, family, expected
):
    store = FileSystemCAS(tmp_path / "cas")
    source, model_ref, model = _fit_and_persist(store, family=family)
    query = CausalQuery(
        query_type="interventional",
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
        n_samples=64,
    )
    job, payload = _actual_job(
        store, GCMQuery, SCMQueryData(scm_spec=model, query=query), "scm_query_data"
    )
    assert payload["causal_query_result"] == payload["query_result"]
    result = CausalQueryResult.model_validate(payload["causal_query_result"])
    assert result.result_mean == pytest.approx(expected, abs=1e-10)
    assert result.result_distribution == pytest.approx([expected] * 64, abs=1e-10)
    assert result.estimator_interval is None and not result.to_uncertainty_envelope().gate_eligible
    result_ref = persist_causal_query_result(_ensure_ir_artifact_store(store), result)
    loaded = load_causal_query_result(
        _ensure_ir_artifact_store(FileSystemCAS(store.root)), result_ref
    )
    assert loaded.model_dump(mode="json") == result.model_dump(mode="json")
    reader = r"""
import json,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.registry.refs import StructuralCausalModelSpecRef,CausalQueryResultRef
from polisyos.ir.analytics.structural_causal_model import load_structural_causal_model_spec
from polisyos.ir.analytics.causal_queries import load_causal_query_result
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
store=FileSystemCAS(sys.argv[1]);model=load_structural_causal_model_spec(store,StructuralCausalModelSpecRef.model_validate_json(sys.argv[2]));result=load_causal_query_result(store,CausalQueryResultRef.model_validate_json(sys.argv[3]));expected=float(sys.argv[4])
assert model.schema_version=='1.0' and model.fit_method=='manual' and model.fit_provenance is None
output=GCMQuery.pure_step(SCMQueryData(scm_spec=model,query=result.query),{'__seed__':19,'enable_dowhy_comparison':False})['query_result']
assert abs(result.result_mean-expected)<1e-10 and abs(output.result_mean-expected)<1e-10
assert not result.to_uncertainty_envelope().gate_eligible
print(json.dumps({'fresh_mean':output.result_mean,'persisted_mean':result.result_mean,'family':model.mechanisms[1].family.value,'selected_backend_claim':False}))
"""
    fresh = subprocess.run(
        [
            sys.executable,
            "-c",
            reader,
            str(store.root),
            model_ref.model_dump_json(),
            result_ref.model_dump_json(),
            str(expected),
        ],
        capture_output=True,
        env=os.environ,
    )
    print(fresh.stdout.decode(), end="")
    assert fresh.returncode == 0, fresh.stderr.decode()


def test_existing_polynomial_fit_helper_shared_residual_twin_cas_and_fresh_reader(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    _source, model_ref, model = _fit_and_persist(store)
    state = TwinNetworkQueryData(
        scm_spec=model,
        factual_condition={"X": 1.0, "Y": 1.25},
        treatment_variable="X",
        factual_treatment_value=1.0,
        counterfactual_treatment_value=2.0,
        outcome_variable="Y",
        n_samples=32,
    )
    job, payload = _actual_job(store, TwinNetworkQuery, state, "twin_network_query_data")
    result = TwinNetworkResult.model_validate(payload["twin_network_result"])
    # Independent law f(x)=x² and retained factual residual .25: both worlds
    # share that same residual, so do2-do1=4-1=3 on every unit.
    assert result.po_factual_mean == pytest.approx(1.25, abs=1e-10)
    assert result.po_counter_mean == pytest.approx(4.25, abs=1e-10)
    assert result.ite_distribution == pytest.approx([3.0] * 32, abs=1e-10)
    assert result.estimator_interval is None and not result.to_uncertainty_envelope().gate_eligible
    ref = persist_twin_network_result(_ensure_ir_artifact_store(store), result)
    assert load_twin_network_result(
        _ensure_ir_artifact_store(FileSystemCAS(store.root)), ref
    ).model_dump(mode="json") == result.model_dump(mode="json")
    reader = r"""
import json,sys
from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.registry.refs import StructuralCausalModelSpecRef,TwinNetworkResultRef
from polisyos.ir.analytics.structural_causal_model import load_structural_causal_model_spec
from polisyos.ir.analytics.twin_network import load_twin_network_result
from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery
from polisyos.foundry.methods.catalog.causal.protocols import TwinNetworkQueryData
store=ensure_ir_artifact_store(FileSystemCAS(sys.argv[1]));model=load_structural_causal_model_spec(store,StructuralCausalModelSpecRef.model_validate_json(sys.argv[2]));old=load_twin_network_result(store,TwinNetworkResultRef.model_validate_json(sys.argv[3]));state=TwinNetworkQueryData(scm_spec=model,factual_condition={'X':1.0,'Y':1.25},treatment_variable='X',factual_treatment_value=1.0,counterfactual_treatment_value=2.0,outcome_variable='Y',n_samples=32)
new=TwinNetworkQuery.pure_step(state,{'__seed__':19})['twin_network_result']
for result in [old,new]:
 assert abs(result.ite_mean-3.0)<1e-10 and abs(result.po_counter_mean-4.25)<1e-10
 assert result.estimator_interval is None and not result.to_uncertainty_envelope().gate_eligible
print(json.dumps({'fresh_ite':new.ite_mean,'persisted_ite':old.ite_mean,'fresh_counter':new.po_counter_mean,'selected_backend_claim':False}))
"""
    fresh = subprocess.run(
        [
            sys.executable,
            "-c",
            reader,
            str(store.root),
            model_ref.model_dump_json(),
            ref.model_dump_json(),
        ],
        capture_output=True,
        env=os.environ,
    )
    print(fresh.stdout.decode(), end="")
    assert fresh.returncode == 0, fresh.stderr.decode()


def test_declared_polynomial_payload_missing_coefficients_refuses_native_query(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    _source, _ref, model = _fit_and_persist(store)
    parameters = dict(model.mechanisms[1].family_params)
    del parameters["poly_coefficients"]
    incomplete = model.model_copy(
        update={
            "mechanisms": [
                model.mechanisms[0],
                model.mechanisms[1].model_copy(update={"family_params": parameters}),
            ]
        }
    )
    query = CausalQuery(
        query_type="interventional",
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
        n_samples=1,
    )
    with pytest.raises(ValueError, match="invalid additive_noise polynomial payload"):
        GCMQuery.pure_step(
            SCMQueryData(scm_spec=incomplete, query=query), {"enable_dowhy_comparison": False}
        )
