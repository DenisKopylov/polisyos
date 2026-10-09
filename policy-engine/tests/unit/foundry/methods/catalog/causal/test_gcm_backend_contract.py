"""The selected GCM profile cannot quietly execute the native OLS profile."""

import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit
from polisyos.foundry.methods.catalog.causal.id_engine import CtfQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType


def _fit_data() -> SCMFitData:
    x = np.linspace(-2.0, 2.0, 20)
    return SCMFitData(
        data=np.column_stack([x, 2 * x]),
        column_names=["X", "Y"],
        graph=CausalGraphModel(
            graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[CausalEdge(src="X", dst="Y")]
        ),
    )


def test_selected_gcm_refuses_missing_source_context() -> None:
    with pytest.raises(RuntimeError, match="source-resolved|bridge unavailable"):
        HybridSCMFit.pure_step(_fit_data(), {"fit_backend": "dowhy_gcm"})


def test_selected_gcm_refuses_admg_with_declared_dag_reason() -> None:
    dag_data = _fit_data()
    admg_data = dag_data.model_copy(
        update={
            "graph": CausalGraphModel(
                graph_type=GraphType.ADMG,
                nodes=["X", "Y"],
                edges=[CausalEdge(src="X", dst="Y")],
            )
        }
    )

    with pytest.raises(
        ValueError,
        match="selected GCM profile requires a fully observed declared static DAG",
    ) as refusal:
        HybridSCMFit.pure_step(admg_data, {"fit_backend": "dowhy_gcm"})

    assert refusal.value.reason_code == "graph_not_declared_static_dag"


def test_causal_engine_run_surfaces_selected_gcm_admg_refusal() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    rng = np.random.default_rng(13)
    x = rng.normal(size=48)
    y = 0.25 + 1.5 * x + rng.normal(scale=0.2, size=48)
    engine = CausalEngine(registry=MethodRegistry.get_instance())

    with pytest.raises(
        ValueError,
        match="selected GCM profile requires a fully observed declared static DAG",
    ) as refusal:
        engine.run(
            "X",
            "Y",
            graph,
            data_dict={"graph": graph, "X": x, "Y": y, "n_samples": 32},
            counterfactual_query=CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                evidence=(("X", 0.0),),
                kind="ett",
            ),
            run_id="unsupported-admg-gcm",
        )

    assert refusal.value.reason_code == "graph_not_declared_static_dag"


def test_explicit_native_profile_never_claims_dowhy_fit() -> None:
    output = HybridSCMFit.pure_step(_fit_data(), {"fit_backend": "native_hybrid"})
    assert output["scm_spec"].fit_method == "native_hybrid"
    assert output["scm_spec"].fit_provenance is None
    assert output["structural_causal_model_spec"] is output["scm_spec"]


import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal import _dowhy_worker as bridge
from polisyos.foundry.methods.catalog.causal.gcm_fit import validate_persisted_gcm_spec
from polisyos.foundry.methods.catalog.causal.gcm_query import (
    GCMQuery,
    validate_persisted_estimator_interval,
)
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
from polisyos.ir.analytics.causal_queries import CausalQuery, load_causal_query_result
from polisyos.ir.analytics.structural_causal_model import persist_structural_causal_model_spec
from polisyos.ir.registry.refs import CausalQueryResultRef
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.nodes.builtins.causal.run_causal_queries import RunCausalQueriesNode
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_QUERY_RESULT_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _dgp(n: int) -> SCMFitData:
    rng = np.random.default_rng(321)
    x = rng.normal(size=n)
    noise = rng.normal(size=n)
    return SCMFitData(
        data=np.column_stack([x, 2 * x + noise]),
        column_names=["X", "Y"],
        graph=CausalGraphModel(
            graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[CausalEdge(src="X", dst="Y")]
        ),
        metadata={"sampling_unit": "iid_observation_row", "input_scope": "known_synthetic_dgp"},
    )


def _fit_real(tmp_path: Path, n: int):
    data = _dgp(n)
    store = FileSystemCAS(tmp_path)
    source = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="tests.scm_fit_data",
            media_type="application/json",
            schema=SchemaInfo(name="tests.SCMFitData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    MethodRegistry.get_instance().register(HybridSCMFit, override=True)
    from polisyos.foundry import causal_worker_execution_context

    with causal_worker_execution_context(store=store, source_ref=source):
        result = run_job(
            JobSpec(
                job_kind="method",
                method_fqn=HybridSCMFit.signature.fqn,
                input_refs={"scm_fit_data": source},
                seed=23,
            ),
            cas_root=tmp_path,
            method_state=data,
        )
    assert not result.issues, result.issues
    assert result.method_result_ref is not None
    payload = from_canonical_bytes(store.get_bytes(result.method_result_ref))
    from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec

    model = StructuralCausalModelSpec.model_validate(payload["structural_causal_model_spec"])
    assert payload["structural_causal_model_spec"] == payload["scm_spec"]
    return store, source, data, model, result


@pytest.fixture
def selected_worker(monkeypatch):
    interpreter = bridge._worker_directory() / ".venv/bin/python"
    assert interpreter.is_file(), (
        "Install selected genuine locked worker before running; backend absence is not PASS"
    )
    monkeypatch.setenv("POLISYOS_DOWHY_WORKER_PYTHON", str(interpreter))


def _contrast() -> CausalQuery:
    return CausalQuery(
        query_type="attribution",
        treatment_variable="X",
        outcome_variable="Y",
        n_samples=3000,
        contrast={
            "target": {"type": "atomic", "value": 1},
            "comparator": {
                "kind": "interventional",
                "intervention": {"type": "atomic", "value": 0},
            },
        },
    )


def test_actual_gcm_job_persisted_fresh_reader_and_scientist_consumer(tmp_path, selected_worker):
    store, source, data, model, result = _fit_real(tmp_path / "cas", 400)
    assert model.fit_method == "gcm" and model.schema_version == "1.1"
    assert model.fit_provenance.versions["dowhy"] == "0.14"
    assert model.training_rows.source_sha256 == hashlib.sha256(store.get_bytes(source)).hexdigest()
    from polisyos import foundry as methods

    methods.validate_source_bound_gcm_spec(model, store)
    methods.validate_source_bound_causal_worker_response(
        response=model.fit_provenance.worker_response,
        state=data,
        store=store,
        source_ref=source,
    )
    root, conditional = model.mechanisms
    assert root.family_params["observed_samples"] == data.data[:, 0].tolist()
    coefficient = conditional.family_params["coefficients"]["X"]
    assert coefficient == pytest.approx(
        np.linalg.lstsq(
            np.column_stack([np.ones(400), data.data[:, 0]]), data.data[:, 1], rcond=None
        )[0][1],
        abs=1e-12,
    )
    assert abs(coefficient - 2) < 4 / np.sqrt(
        np.sum((data.data[:, 0] - data.data[:, 0].mean()) ** 2)
    )
    assert np.asarray(conditional.family_params["residual_samples"]) == pytest.approx(
        data.data[:, 1] - conditional.family_params["intercept"] - coefficient * data.data[:, 0]
    )
    ref = persist_structural_causal_model_spec(_ensure_ir_artifact_store(store), model)
    reader = """
import json,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.registry.refs import StructuralCausalModelSpecRef
from polisyos.ir.analytics.structural_causal_model import load_structural_causal_model_spec
from polisyos.foundry.methods.catalog.causal.gcm_fit import validate_persisted_gcm_spec
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
store=FileSystemCAS(sys.argv[1]);ref=StructuralCausalModelSpecRef.model_validate(json.loads(sys.argv[2]))
model=load_structural_causal_model_spec(store,ref);validate_persisted_gcm_spec(model,store)
query=json.loads(sys.argv[3]);output=GCMQuery.pure_step(SCMQueryData(scm_spec=model,query=query),{'__seed__':23,'enable_dowhy_comparison':False})
assert sys.version_info[:2]==(3,14)
assert not output['envelope'].gate_eligible
print(json.dumps({'mean':output['query_result'].result_mean,'profile':model.fit_provenance.profile}))
"""
    fresh = subprocess.run(
        [
            sys.executable,
            "-c",
            reader,
            str(store.root),
            ref.model_dump_json(),
            _contrast().model_dump_json(),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr
    assert json.loads(fresh.stdout)["mean"] == pytest.approx(coefficient, abs=1e-10)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="native-gcm-scm")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("native-gcm-scm"))
    state = ExperimentState(
        run_id="native-gcm-scm",
        params={
            "random_seed": 23,
            "structural_causal_model_ref": ref.model_dump(mode="json"),
            "causal_query": _contrast().model_dump(mode="json"),
            "causal_estimator_bootstrap_replicates": 40,
        },
    )
    outcome = RunCausalQueriesNode().execute(ctx, state)
    assert outcome.status == "ok", outcome.error
    persisted = load_causal_query_result(
        _ensure_ir_artifact_store(FileSystemCAS(store.root)),
        CausalQueryResultRef.model_validate(
            outcome.state.artifacts_index[ARTIFACT_CAUSAL_QUERY_RESULT_REF].model_dump(mode="json")
        ),
    )
    assert persisted.result_mean == pytest.approx(coefficient, abs=1e-10)
    interval = persisted.estimator_interval
    assert interval is not None and interval.replicate_count == 40
    from polisyos import ir
    from polisyos.ir import analytics

    assert type(interval) is ir.CausalEstimatorInterval is analytics.CausalEstimatorInterval
    assert type(model.training_rows) is ir.SCMTrainingRows
    assert type(model.fit_provenance) is ir.SCMFitProvenance
    assert persisted.result_kind is ir.CausalResultKind.ITE_DISTRIBUTION
    assert interval.refit_scope == ("X", "Y") and interval.n_units == 400
    assert interval.interval[0] < coefficient < interval.interval[1]
    assert interval.to_uncertainty_envelope().confidence_level == 0.95
    assert not interval.to_uncertainty_envelope().gate_eligible
    assert not persisted.to_uncertainty_envelope().gate_eligible
    for key in ("point_estimate", "confidence_level", "n_units", "replicate_count", "seed"):
        raw = interval.model_dump(mode="json")
        raw[key] = str(raw[key])
        with pytest.raises(ValueError):
            ir.CausalEstimatorInterval.model_validate(raw)
    for key in ("interval", "replicate_estimates"):
        for substitute in ("0.0", False):
            raw = interval.model_dump(mode="json")
            raw[key][0] = substitute
            with pytest.raises(ValueError, match="finite JSON number primitives"):
                ir.CausalEstimatorInterval.model_validate(raw)
    validate_persisted_estimator_interval(
        interval, model, persisted.query, FileSystemCAS(store.root)
    )
    methods.validate_source_bound_causal_estimator_interval(
        interval, model, persisted.query, FileSystemCAS(store.root)
    )
    corrupted = interval.model_copy(
        update={"replicate_estimates": tuple(v + 0.2 for v in interval.replicate_estimates)}
    )
    with pytest.raises(ValueError, match="differs from source-bound"):
        validate_persisted_estimator_interval(corrupted, model, persisted.query, store)


def test_row_permutation_source_and_effective_mechanism_tampering_refused(
    tmp_path, selected_worker
):
    store, source, data, model, _ = _fit_real(tmp_path, 100)
    changed = data.model_copy(deep=True)
    changed.data[:, 1] = changed.data[::-1, 1]
    with (
        bridge.worker_execution_context(store=store, source_ref=source),
        pytest.raises(bridge.WorkerBindingError, match="resolved source rows"),
    ):
        HybridSCMFit.pure_step(changed, {})
    altered = model.model_copy(deep=True)
    altered.mechanisms[1].family_params["coefficients"]["X"] += 0.5
    with pytest.raises(ValueError, match="content-bound fitted worker output"):
        validate_persisted_gcm_spec(altered, store)
    # Keep all backend/source/hash markers and make the fake exported residuals
    # internally consistent with a changed coefficient. Custody alone must not
    # certify the effective numerical fit.
    forged = model.model_copy(deep=True)
    exported = forged.fit_provenance.worker_response["result"]["mechanisms"]["Y"]
    exported["coefficients"]["X"] += 0.5
    residuals = (
        data.data[:, 1] - exported["intercept"] - exported["coefficients"]["X"] * data.data[:, 0]
    )
    exported["residual_samples"] = residuals.tolist()
    exported["noise_std"] = float(np.std(residuals))
    forged.mechanisms[1].family_params.update(
        coefficients=dict(exported["coefficients"]),
        residual_samples=residuals.tolist(),
        noise_std=float(np.std(residuals)),
    )
    with pytest.raises(ValueError, match="differs from source-row oracle"):
        validate_persisted_gcm_spec(forged, store)
    from polisyos.foundry.methods.catalog.causal.gcm_fit import _gcm_spec_from_worker

    for node, field in (
        ("X", "observed_samples"),
        ("Y", "residual_samples"),
        ("Y", "intercept"),
        ("Y", "coefficients"),
        ("Y", "noise_std"),
    ):
        for boolean in (False, True):
            response = json.loads(json.dumps(model.fit_provenance.worker_response))
            export = response["result"]["mechanisms"][node]
            value = export[field]
            # Numeric strings preserve the value; bools are separate wrong primitive controls.
            if isinstance(value, list):
                value[0] = boolean if boolean else str(value[0])
            elif isinstance(value, dict):
                value["X"] = boolean if boolean else str(value["X"])
            else:
                export[field] = boolean if boolean else str(value)
            with pytest.raises(ValueError, match="finite JSON numbers"):
                _gcm_spec_from_worker(data, response, response["result"], seed=23)
    noniid = model.model_copy(deep=True)
    noniid.training_rows.fit_input["metadata"]["sampling_unit"] = "panel_row"
    with pytest.raises(ValueError, match="explicit iid observation-row"):
        GCMQuery.pure_step(
            SCMQueryData(scm_spec=noniid, query=_contrast()),
            {"bootstrap_replicates": 20, "enable_dowhy_comparison": False},
        )
    missing = FileSystemCAS(tmp_path / "empty")
    with pytest.raises((OSError, ValueError, KeyError, RuntimeError)):
        validate_persisted_gcm_spec(model, missing)


def test_actual_query_consumer_binds_complete_cas_projection_and_original_request(
    tmp_path, selected_worker, monkeypatch
):
    """A genuine job's editable peer cannot replace its immutable result or request."""
    import polisyos.scientist.nodes.builtins.causal.run_causal_queries as owner

    store, source, data, model, _ = _fit_real(tmp_path / "cas", 100)
    ref = persist_structural_causal_model_spec(_ensure_ir_artifact_store(store), model)
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="query-custody")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("query-custody"))
    state = ExperimentState(
        run_id="query-custody",
        params={
            "random_seed": 23,
            "structural_causal_model_ref": ref.model_dump(mode="json"),
            "causal_query": _contrast().model_dump(mode="json"),
        },
    )
    assert owner.RunCausalQueriesNode().execute(ctx, state).status == "ok"
    genuine_job = owner.run_job
    cases = ("summary", "draws", "kind", "metadata", "original_request", "missing_artifact")
    for case in cases:
        observed = {}

        def actual_job_then_corrupt(spec, *, selected_case=case, measurement=observed, **kwargs):
            # Execute the real dispatcher and preserve its real fitted-source markers.
            if selected_case == "original_request":
                original = kwargs["method_state"]
                request = original.query.model_dump(mode="json")
                request["contrast"]["target"]["value"] = 2.0
                kwargs["method_state"] = original.model_copy(
                    update={"query": CausalQuery.model_validate(request)}
                )
            job = genuine_job(spec, **kwargs)
            assert not job.issues and job.method_result_ref is not None
            original_bytes = store.get_bytes(job.method_result_ref)
            measurement["genuine_sha256"] = hashlib.sha256(original_bytes).hexdigest()
            if selected_case == "missing_artifact":
                job.method_result_ref = None
                return job
            if selected_case == "original_request":
                # A genuine different-arm job keeps both aliases and CAS coherent.
                assert job.final_state["query_result"].query.contrast.target.value == 2.0
                return job
            result = job.final_state["query_result"].model_copy(deep=True)
            if selected_case == "summary":
                result.result_mean += 5
                result.result_ci = (result.result_mean, result.result_mean)
            elif selected_case == "draws":
                result.result_distribution[0] += 5
            elif selected_case == "kind":
                result.result_kind = "outcome_distribution"
            elif selected_case == "metadata":
                result.metadata["unbound_claim"] = "same backend and source markers"
            job.final_state["query_result"] = result
            assert store.get_bytes(job.method_result_ref) == original_bytes
            return job

        monkeypatch.setattr(owner, "run_job", actual_job_then_corrupt)
        outcome = owner.RunCausalQueriesNode().execute(ctx, state)
        assert outcome.status == "fail", f"accepted genuine-job {case} corruption"
        assert outcome.error is not None
        assert ARTIFACT_CAUSAL_QUERY_RESULT_REF not in outcome.state.artifacts_index
        assert observed["genuine_sha256"]


def test_public_source_bound_validation_facade_identity_invocation_and_pickle():
    """Facade names preserve the actual providers and callable ABI."""
    import io
    import pickle
    from importlib import import_module

    from polisyos import foundry
    from polisyos.foundry import methods
    from polisyos.foundry.methods import api

    providers = {
        "causal_worker_execution_context": bridge.worker_execution_context,
        "validate_source_bound_gcm_spec": validate_persisted_gcm_spec,
        "validate_source_bound_causal_estimator_interval": validate_persisted_estimator_interval,
        "validate_source_bound_causal_worker_response": bridge.validate_persisted_worker_response,
    }
    allowed = {(p.__module__, p.__name__) for p in providers.values()}

    class FacadeUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            if (module, name) not in allowed:
                raise pickle.UnpicklingError("unexpected provider in locally created ABI fixture")
            return getattr(import_module(module), name)

    for name, provider in providers.items():
        assert name in foundry.__all__
        assert getattr(foundry, name) is provider
        assert name in methods.__all__ and name in api.__all__
        assert getattr(methods, name) is getattr(api, name) is provider
        assert FacadeUnpickler(io.BytesIO(pickle.dumps(provider))).load() is provider
    with pytest.raises(TypeError):
        methods.causal_worker_execution_context()
    with pytest.raises(TypeError):
        methods.validate_source_bound_gcm_spec()
    with pytest.raises(TypeError):
        methods.validate_source_bound_causal_estimator_interval()
    with pytest.raises(TypeError):
        methods.validate_source_bound_causal_worker_response()


def test_true_refit_sampling_interval_shrinks_predictive_distribution_does_not(
    tmp_path, selected_worker
):
    widths = []
    spans = []
    for n in (400, 800):
        store, source, data, model, _ = _fit_real(tmp_path / str(n), n)
        query = CausalQuery(
            query_type="interventional",
            treatment_variable="X",
            outcome_variable="Y",
            treatment_value=1,
            n_samples=4000,
        )
        with bridge.worker_execution_context(store=store, source_ref=source):
            output = GCMQuery.pure_step(
                SCMQueryData(scm_spec=model, query=query),
                {"__seed__": 45, "bootstrap_replicates": 80, "enable_dowhy_comparison": False},
            )
        interval = output["query_result"].estimator_interval
        validate_persisted_estimator_interval(interval, model, query, store)
        widths.append(interval.interval[1] - interval.interval[0])
        spans.append(output["query_result"].result_ci[1] - output["query_result"].result_ci[0])
        assert output["envelope"].distribution_family.value == "unknown"
    print(
        json.dumps(
            {
                "n_units": [400, 800],
                "estimator_widths": widths,
                "predictive_spans": spans,
                "width_ratio": widths[1] / widths[0],
                "predictive_ratio": spans[1] / spans[0],
            }
        )
    )
    assert 0.45 < widths[1] / widths[0] < 0.95
    assert 0.8 < spans[1] / spans[0] < 1.2
