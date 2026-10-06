"""Non-skipping selected-worker consumers on an explicitly known synthetic DGP."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.catalog.causal import _dowhy_worker as bridge
from polisyos.foundry.methods.catalog.causal.dowhy_identify_estimate import DoWhyIdentifyEstimate
from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus
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
    executable = bridge._worker_directory() / ".venv" / "bin" / "python"
    assert executable.is_file(), (
        "Install the frozen standalone DoWhy profile before this native test"
    )
    monkeypatch.setenv("POLISYOS_DOWHY_WORKER_PYTHON", str(executable))


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
store=FileSystemCAS(sys.argv[1])
result_ref=ArtifactRef.model_validate(json.loads(sys.argv[2]))
source=ArtifactRef.model_validate(json.loads(sys.argv[3]))
payload=from_canonical_bytes(store.get_bytes(result_ref))
report=CausalEffectReport.model_validate(payload['report'])
worker=report.metadata['worker']
state=GraphCausalData.model_validate(from_canonical_bytes(store.get_bytes(source)))
validate_persisted_worker_response(response=worker,state=state,store=store,source_ref=source)
assert sys.version_info[:2]==(3,14)
assert worker['source']['artifact_ref']==source.model_dump(mode='json')
assert worker['source']['content_sha256']==hashlib.sha256(store.get_bytes(source)).hexdigest()
assert report.confidence_level==.95 and abs(report.point_estimate-2.016134929864521)<1e-10
assert list(report.confidence_interval)==worker['result']['interval']
assert report.to_uncertainty_envelope().gate_eligible
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
