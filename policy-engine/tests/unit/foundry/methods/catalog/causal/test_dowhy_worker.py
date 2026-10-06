"""Non-skipping selected-worker consumers on an explicitly known synthetic DGP."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import pickle
import pydoc
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods import causal as public_causal
from polisyos.foundry.methods.catalog import causal as catalog_causal
from polisyos.foundry.methods.catalog.causal import _dowhy_worker as bridge
from polisyos.foundry.methods.catalog.causal.dowhy_identify_estimate import DoWhyIdentifyEstimate
from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import CausalEffectReport, EstimationStatus
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job


def dgp(seed: int = 19, n: int = 500) -> GraphCausalData:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    a = rng.binomial(1, 1 / (1 + np.exp(-x)))
    y = 2 * a + 1.5 * x + rng.normal(size=n)
    return GraphCausalData(
        data=np.column_stack([a, y, x]),
        column_names=["A", "Y", "X"],
        treatment="A",
        outcome="Y",
        covariates=["X"],
        graph_dot="digraph { X -> A; X -> Y; A -> Y; }",
    )


def admit(tmp_path, data):
    store = FileSystemCAS(tmp_path)
    ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="tests.graph_causal_data",
            media_type="application/json",
            schema=SchemaInfo(name="tests.GraphCausalData", version="2.0.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return store, ref


@pytest.fixture
def selected_worker(monkeypatch):
    configured = os.environ.get("E02_TEST_DOWHY_WORKER_PYTHON")
    executable = (
        Path(configured) if configured else bridge._worker_directory() / ".venv" / "bin" / "python"
    )
    assert executable.is_file(), (
        "Install the frozen standalone DoWhy profile before this native test"
    )
    monkeypatch.setenv("POLISYOS_DOWHY_WORKER_PYTHON", str(executable))


def test_missing_installed_profile_assets_are_a_typed_unavailability(tmp_path, monkeypatch):
    missing = tmp_path / "isolated_installation" / "causal" / "_dowhy_worker.py"
    missing.parent.mkdir(parents=True)
    missing.touch()
    monkeypatch.setattr(bridge, "__file__", str(missing))
    with pytest.raises(bridge.WorkerUnavailableError, match="profile assets unavailable"):
        bridge._worker_directory()


def test_public_complete_report_builder_abi_and_real_producer_invocation(
    tmp_path, selected_worker, monkeypatch
):
    assert public_causal.DoWhyIdentifyEstimate is catalog_causal.DoWhyIdentifyEstimate
    assert catalog_causal.DoWhyIdentifyEstimate is DoWhyIdentifyEstimate
    builder = public_causal.DoWhyIdentifyEstimate.report_from_worker_result
    assert pickle.loads(pickle.dumps(builder)) is builder  # noqa: S301 -- same-process trusted ABI bytes
    assert builder.__qualname__ == "DoWhyIdentifyEstimate.report_from_worker_result"
    assert "report_from_worker_result" in pydoc.render_doc(
        public_causal.DoWhyIdentifyEstimate, renderer=pydoc.plaintext
    )
    calls = []

    def observe(**kwargs):
        calls.append(kwargs["response"]["request_sha256"])
        return builder(**kwargs)

    monkeypatch.setattr(
        public_causal.DoWhyIdentifyEstimate, "report_from_worker_result", staticmethod(observe)
    )
    data = dgp()
    store, source = admit(tmp_path, data)
    MethodRegistry.get_instance().register(DoWhyIdentifyEstimate, override=True)
    with bridge.worker_execution_context(store=store, source_ref=source):
        result = run_job(
            JobSpec(job_kind="method", method_fqn=DoWhyIdentifyEstimate.signature.fqn),
            cas_root=tmp_path,
            method_state=data,
        )
    assert not result.issues
    saved = from_canonical_bytes(store.get_bytes(result.method_result_ref))
    report = CausalEffectReport.model_validate(saved["report"])
    assert report.point_estimate == pytest.approx(2.016134929864521)
    assert len(calls) == 1, "The actual producer must execute the supported facade override"
    expected = public_causal.DoWhyIdentifyEstimate.report_from_worker_result(
        data=data, params={}, response=report.metadata["worker"]
    )
    assert len(calls) == 2 and calls[0] == calls[1]
    assert expected == report
    assert CausalEffectReport.model_validate_json(expected.model_dump_json()) == report
    resolved = {p.name: p.default for p in DoWhyIdentifyEstimate.signature.parameters}
    assert builder(data=data, params=resolved, response=report.metadata["worker"]) == report
    assert report.method_params == resolved
    assert bridge.artifacts.ArtifactRef is type(source)


def test_real_worker_job_cas_fresh_python314_reader(tmp_path, selected_worker):
    data = dgp()
    store, source = admit(tmp_path, data)
    MethodRegistry.get_instance().register(DoWhyIdentifyEstimate, override=True)
    spec = JobSpec(
        job_kind="method",
        method_fqn=DoWhyIdentifyEstimate.signature.fqn,
        seed=13,
        input_refs={"dowhy_observational_data": source},
    )
    with bridge.worker_execution_context(store=store, source_ref=source):
        result = run_job(spec, cas_root=tmp_path, method_state=data)
    assert not result.issues
    assert result.method_result_ref is not None
    payload = from_canonical_bytes(store.get_bytes(result.method_result_ref))
    report = payload["report"]
    assert report["status"] == "success", report
    worker = report["metadata"]["worker"]
    assert worker["python"].startswith("3.12.") and worker["versions"]["dowhy"] == "0.14"
    assert worker["source"]["content_sha256"] == hashlib.sha256(store.get_bytes(source)).hexdigest()
    assert payload["envelope"]["confidence_level"] == 0.95
    evidence = from_canonical_bytes(store.get_bytes(result.method_evidence_ref))
    assert evidence["may_not_use_for"] == ["governance_admissibility", "method_validity"]
    assert str(source.artifact_id) in {
        str(ref.artifact_id) for ref in store.get_manifest(result.method_result_ref).inputs
    }
    reader = """
import hashlib,json,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData
from polisyos.foundry.methods.catalog.causal._dowhy_worker import validate_persisted_worker_response
from polisyos.foundry.methods.causal import DoWhyIdentifyEstimate
store=FileSystemCAS(sys.argv[1])
result_ref=ArtifactRef.model_validate(json.loads(sys.argv[2]))
source=ArtifactRef.model_validate(json.loads(sys.argv[3]))
payload=from_canonical_bytes(store.get_bytes(result_ref))
report=CausalEffectReport.model_validate(payload['report'])
worker=report.metadata['worker']
state=GraphCausalData.model_validate(from_canonical_bytes(store.get_bytes(source)))
validate_persisted_worker_response(response=worker,state=state,store=store,source_ref=source)
assert report==DoWhyIdentifyEstimate.report_from_worker_result(data=state,params={},response=worker)
assert sys.version_info[:2]==(3,14)
assert worker['source']['artifact_ref']==source.model_dump(mode='json')
assert worker['source']['content_sha256']==hashlib.sha256(store.get_bytes(source)).hexdigest()
assert report.confidence_level==.95 and abs(report.point_estimate-2.016134929864521)<1e-10
assert list(report.confidence_interval)==worker['result']['interval']
envelope=report.to_uncertainty_envelope()
assert not envelope.gate_eligible
assert envelope.metadata['gate_eligibility_reason']=='causal_identification_admission_not_established'
assert envelope.confidence_level==.95
assert envelope.confidence_interval==tuple(envelope.numeric_policy.canonicalize(value) for value in worker['result']['interval'])
print(json.dumps({'python':sys.version,'report':report.model_dump(mode='json')},sort_keys=True))
"""
    fresh = subprocess.run(
        [
            sys.executable,
            "-c",
            reader,
            str(tmp_path),
            result.method_result_ref.model_dump_json(),
            source.model_dump_json(),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr
    assert json.loads(fresh.stdout)["report"]["point_estimate"] == pytest.approx(2.016134929864521)
    assert report["confidence_interval"] == pytest.approx([1.8265023190563892, 2.2057675406726527])
    corrupted = json.loads(json.dumps(worker))
    corrupted["parent_observed"]["request_binding"]["payload"]["target_units"] = "att"
    with pytest.raises(bridge.WorkerBindingError, match="binding mismatch"):
        bridge.validate_persisted_worker_response(
            response=corrupted, state=data, store=store, source_ref=source
        )


def test_source_row_permutation_refused_before_worker(tmp_path, selected_worker):
    data = dgp(n=80)
    store, source = admit(tmp_path, data)
    changed = data.model_copy(deep=True)
    changed.data[:, 1] = changed.data[::-1, 1]
    with bridge.worker_execution_context(store=store, source_ref=source):
        report = DoWhyIdentifyEstimate.pure_step(changed, {})["report"]
    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None and report.confidence_interval is None
    assert "resolved source rows" in report.status_reason


def test_real_persisted_binding_missing_and_malformed_fields_are_typed_refusals(
    tmp_path, selected_worker
):
    data = dgp(n=80)
    store, source = admit(tmp_path, data)
    with bridge.worker_execution_context(store=store, source_ref=source):
        response = DoWhyIdentifyEstimate.pure_step(data, {})["report"].metadata["worker"]
    # Derive the deletion set from the actual non-default producer object.
    required_paths = [(key,) for key in response]
    required_paths += [
        ("parent_observed", key)
        for key in response["parent_observed"]
        if key in {"worker_lock_sha256", "worker_code_sha256", "request_binding"}
    ]
    required_paths += [
        ("parent_observed", "request_binding", key)
        for key in response["parent_observed"]["request_binding"]
    ]
    required_paths += [("result", key) for key in response["result"]]
    for path in required_paths:
        changed = copy.deepcopy(response)
        parent = changed
        for key in path[:-1]:
            parent = parent[key]
        del parent[path[-1]]
        with pytest.raises(bridge.WorkerBindingError):
            bridge.validate_persisted_worker_response(
                response=changed, state=data, store=store, source_ref=source
            )
    for key in ["versions", "result", "parent_observed"]:
        changed = copy.deepcopy(response)
        changed[key] = []
        with pytest.raises(bridge.WorkerBindingError):
            bridge.validate_persisted_worker_response(
                response=changed, state=data, store=store, source_ref=source
            )
    with bridge.worker_execution_context(store=store, source_ref=source):
        request = bridge._bound_request(
            operation="linear_ate",
            state=data,
            payload=response["parent_observed"]["request_binding"]["payload"],
            seed=0,
        )
    import tomllib

    lock = tomllib.loads((bridge._worker_directory() / "uv.lock").read_text())
    malformed = {key: value for key, value in response.items() if key != "parent_observed"}
    malformed["versions"] = []
    with pytest.raises(bridge.WorkerBindingError):
        bridge._validate_reply(malformed, request, lock)
    # Self-consistent hashes/version markers must not turn malformed JSON scalars
    # into numerical evidence at the persisted consumer boundary.
    for key, values in {
        "point": ["2.0", True, 10**1000],
        "standard_error": ["0.1", False],
        "interval": [["1.0", "3.0"], [True, 3.0], [0, 10**1000]],
        "control_value": [False],
        "treatment_value": [True],
    }.items():
        for value in values:
            changed = copy.deepcopy(response)
            changed["result"][key] = value
            with pytest.raises(bridge.WorkerBindingError):
                bridge.validate_persisted_worker_response(
                    response=changed, state=data, store=store, source_ref=source
                )


@pytest.mark.parametrize(
    "params",
    [
        {"estimand_type": "nonparametric-nie"},
        {"method_name": "backdoor.propensity_score_matching"},
        {"target_units": "att"},
        {"treatment_value": 2},
        {"confidence_level": 0.9},
        {"execution_profile": "shim"},
    ],
)
def test_selected_profile_does_not_relabel_unsupported_requests(params):
    report = DoWhyIdentifyEstimate.pure_step(dgp(n=80), params)["report"]
    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None and report.confidence_level is None


def test_default_without_actual_source_context_has_no_backend_witness():
    report = DoWhyIdentifyEstimate.pure_step(dgp(n=80), {})["report"]
    assert report.status is EstimationStatus.NUMERICAL_FAILURE
    assert report.metadata["capability"] == "backend_unavailable"
    assert report.point_estimate is None


def instrument_actual_worker(monkeypatch, mutation):
    """Instrument the actual installed backend in a test child; never a fallback."""
    original = subprocess.Popen
    script = str(bridge._worker_directory() / "worker.py")
    prefix = """
import runpy,sys
from dowhy import CausalModel
original=CausalModel.estimate_effect
def controlled(self,*args,**kwargs):
    actual=original(self,*args,**kwargs)
"""
    program = (
        prefix
        + mutation
        + "\n    return actual\nCausalModel.estimate_effect=controlled\nrunpy.run_path(sys.argv[1],run_name='__main__')"
    )

    def launch(args, **kwargs):
        if args == [os.environ["POLISYOS_DOWHY_WORKER_PYTHON"], "-I", script]:
            args = [args[0], "-I", "-c", program, script]
        return original(args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", launch)


def test_real_estimate_point_only_survives_parent_cas_and_reader(
    tmp_path, selected_worker, monkeypatch
):
    instrument_actual_worker(
        monkeypatch,
        "    actual.get_confidence_intervals=lambda **kwargs:None\n    actual.get_standard_error=lambda:None",
    )
    data = dgp(n=100)
    store, source = admit(tmp_path, data)
    MethodRegistry.get_instance().register(DoWhyIdentifyEstimate, override=True)
    spec = JobSpec(
        job_kind="method",
        method_fqn=DoWhyIdentifyEstimate.signature.fqn,
        input_refs={"dowhy_observational_data": source},
    )
    with bridge.worker_execution_context(store=store, source_ref=source):
        result = run_job(spec, cas_root=tmp_path, method_state=data)
    assert not result.issues
    reopened = FileSystemCAS(tmp_path)
    persisted = from_canonical_bytes(reopened.get_bytes(result.method_result_ref))
    report = CausalEffectReport.model_validate(persisted["report"])
    assert report.point_estimate is not None
    assert report.status is EstimationStatus.NUMERICAL_FAILURE
    assert report.confidence_interval is None and report.confidence_level is None
    assert not report.to_uncertainty_envelope().gate_eligible
    bridge.validate_persisted_worker_response(
        response=report.metadata["worker"], state=data, store=reopened, source_ref=source
    )


@pytest.mark.parametrize(
    "malformed",
    [
        "[[0.,1.],[2.,3.]]",
        "[0.,1.,2.]",
        "[3.,1.]",
        "[float('nan'),1.]",
        "[0.,float('inf')]",
        "['1.0','3.0']",
        "[True,3.0]",
    ],
)
def test_actual_estimator_malformed_ci_refused_in_parent(
    tmp_path, selected_worker, monkeypatch, malformed
):
    instrument_actual_worker(
        monkeypatch, f"    actual.get_confidence_intervals=lambda **kwargs:{malformed}"
    )
    data = dgp(n=100)
    store, source = admit(tmp_path, data)
    with bridge.worker_execution_context(store=store, source_ref=source):
        report = DoWhyIdentifyEstimate.pure_step(data, {})["report"]
    assert report.status is EstimationStatus.NUMERICAL_FAILURE
    assert report.point_estimate is None and report.confidence_interval is None
    assert report.confidence_level is None
