"""Real installed consumers of the canonical selected worker and public bridges."""
# ruff: noqa: T201, S301 -- complete deciding stdout and canonical pickle ABI probes

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import pickle
import pydoc
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from polisyos import foundry
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry import methods
from polisyos.foundry.methods.catalog.causal import _dowhy_worker as bridge
from polisyos.foundry.methods.catalog.causal.dowhy_identify_estimate import (
    DoWhyIdentifyEstimate,
)
from polisyos.foundry.methods.components.io import dematerialize_method_output
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job

PUBLIC = {
    "causal_worker_execution_context": ("_dowhy_worker", "worker_execution_context"),
    "validate_source_bound_causal_worker_response": (
        "_dowhy_worker",
        "validate_persisted_worker_response",
    ),
    "validate_source_bound_gcm_spec": ("gcm_fit", "validate_persisted_gcm_spec"),
    "validate_source_bound_causal_estimator_interval": (
        "gcm_query",
        "validate_persisted_estimator_interval",
    ),
}


def _fixture(kind):
    path = Path(os.environ["E02_" + kind.upper() + "_FIXTURE_PATH"])
    spec = importlib.util.spec_from_file_location("installed_" + kind + "_fixture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _site():
    site = Path(sys.prefix) / "lib/python3.14/site-packages"
    assert Path(bridge.__file__).is_relative_to(site)
    return site


def _configured(monkeypatch):
    executable = Path(os.environ["E02_TEST_DOWHY_WORKER_PYTHON"])
    assert executable.is_absolute() and executable.is_file()
    monkeypatch.setenv("POLISYOS_DOWHY_WORKER_PYTHON", str(executable))
    return executable


def test_public_canonical_helpers_and_pure_report_factory_identity():
    _site()
    api = importlib.import_module("polisyos.foundry.methods.api")
    for name, (leaf, symbol) in PUBLIC.items():
        canonical = getattr(
            importlib.import_module("polisyos.foundry.methods.catalog.causal." + leaf),
            symbol,
        )
        assert getattr(foundry, name) is getattr(methods, name) is getattr(api, name) is canonical
        assert pickle.loads(pickle.dumps(canonical)) is canonical
    factory = DoWhyIdentifyEstimate.report_from_worker_result
    assert pickle.loads(pickle.dumps(factory)) is factory
    assert "report_from_worker_result" in pydoc.plain(pydoc.render_doc(DoWhyIdentifyEstimate))


READER = """
import hashlib,json,sys
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry import methods
from polisyos.foundry.methods.catalog.causal import _dowhy_worker as bridge
from polisyos.foundry.methods.catalog.causal.dowhy_identify_estimate import DoWhyIdentifyEstimate
from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData
from polisyos.ir.analytics.causal import CausalEffectReport
site=Path(sys.prefix)/'lib/python3.14/site-packages'
assert sys.flags.isolated and Path(bridge.__file__).is_relative_to(site)
assert not any('/src' in p for p in sys.path)
store=FileSystemCAS(sys.argv[1]);ref=ArtifactRef.model_validate(json.loads(sys.argv[2]));source=ArtifactRef.model_validate(json.loads(sys.argv[3]))
report=CausalEffectReport.model_validate(from_canonical_bytes(store.get_bytes(ref))['report'])
state=GraphCausalData.model_validate(from_canonical_bytes(store.get_bytes(source)))
worker=report.metadata['worker']
try:
    methods.validate_source_bound_causal_worker_response(response=worker,state=state,store=store,source_ref=source)
except bridge.WorkerUnavailableError as exc:
    assert sys.argv[4]=='missing_asset'
    print(json.dumps({'typed_refusal':type(exc).__name__,'reason':str(exc),'reply_sha256':hashlib.sha256(store.get_bytes(ref)).hexdigest()}))
else:
    assert sys.argv[4]=='positive'
    expected=DoWhyIdentifyEstimate.report_from_worker_result(data=state,params={},response=worker)
    assert expected.model_dump(mode='json')==report.model_dump(mode='json')
    origins={n:m.__file__ for n,m in sys.modules.copy().items() if n.startswith('polisyos') and getattr(m,'__file__',None)}
    assert all(Path(p).is_relative_to(site) for p in origins.values())
    print(json.dumps({'point':report.point_estimate,'p_value':report.p_value,'complete_report_equal':True,'profile':str(bridge._worker_directory()),'product_origins':origins,'reply_sha256':hashlib.sha256(store.get_bytes(ref)).hexdigest()}))
"""


def test_real_installed_method_job_factory_and_fresh_reader_with_asset_removal(
    tmp_path, monkeypatch
):
    _site()
    executable = _configured(monkeypatch)
    fixture = _fixture("dowhy")
    data = fixture.dgp()
    store, source = fixture.admit(tmp_path, data)
    MethodRegistry.get_instance().register(DoWhyIdentifyEstimate, override=True)
    calls = []
    factory = DoWhyIdentifyEstimate.report_from_worker_result

    def observed_factory(**kwargs):
        calls.append(kwargs)
        return factory(**kwargs)

    launches = []
    popen = subprocess.Popen

    def observed_launch(argv, **kwargs):
        if argv[0] == str(executable):
            launches.append({"argv": argv, "cwd": str(kwargs["cwd"])})
        return popen(argv, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(
            DoWhyIdentifyEstimate,
            "report_from_worker_result",
            staticmethod(observed_factory),
        )
        patch.setattr(subprocess, "Popen", observed_launch)
        with foundry.causal_worker_execution_context(store=store, source_ref=source):
            result = run_job(
                JobSpec(
                    job_kind="method",
                    method_fqn=DoWhyIdentifyEstimate.signature.fqn,
                    seed=13,
                    input_refs={"dowhy_observational_data": source},
                ),
                cas_root=tmp_path,
                method_state=data,
            )
    assert not result.issues
    report = CausalEffectReport.model_validate(
        from_canonical_bytes(store.get_bytes(result.method_result_ref))["report"]
    )
    assert report.status.value == "success", report
    assert len(calls) == len(launches) == 1
    declared = dematerialize_method_output(
        method_class=DoWhyIdentifyEstimate,
        signature=DoWhyIdentifyEstimate.signature,
        output={"report": report},
    )
    assert set(declared) == set(DoWhyIdentifyEstimate.signature.output_slot_names)
    assert declared["causal_effect_report"] is report
    profile = bridge._worker_directory()
    assert profile == Path(bridge.__file__).parent / "_dowhy_profile"
    assert launches[0]["argv"] == [str(executable), "-I", str(profile / "worker.py")]
    expected = json.loads(Path(os.environ["E02_PROFILE_EXPECTED_JSON"]).read_text())
    for name, record in expected["assets"].items():
        assert hashlib.sha256((profile / name).read_bytes()).hexdigest() == record["sha256"]
    worker = report.metadata["worker"]
    assert worker["python"].startswith("3.12.") and worker["versions"]["dowhy"] == "0.14"
    assert worker["authority"] == "candidate_computation_only"
    assert (
        worker["parent_observed"]["worker_code_sha256"]
        == hashlib.sha256(
            (profile / "worker.py").read_bytes() + (profile / "protocol.py").read_bytes()
        ).hexdigest()
    )
    matrix = np.column_stack([np.ones(data.sample_size), data.data[:, 0], data.data[:, 2]])
    assert report.point_estimate == pytest.approx(
        np.linalg.lstsq(matrix, data.data[:, 1], rcond=None)[0][1], abs=1e-10
    )
    evidence = from_canonical_bytes(store.get_bytes(result.method_evidence_ref))
    assert evidence["may_not_use_for"] == [
        "governance_admissibility",
        "method_validity",
    ]

    def fresh(mode):
        child = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                READER,
                str(tmp_path),
                result.method_result_ref.model_dump_json(),
                source.model_dump_json(),
                mode,
            ],
            capture_output=True,
            text=True,
        )
        print(child.stdout, end="")
        print(child.stderr, end="", file=sys.stderr)
        assert child.returncode == 0, child.stdout + child.stderr
        return json.loads(child.stdout)

    positive = fresh("positive")
    original = (profile / "worker.py").read_bytes()
    retired = profile / "worker.py.e02-temporarily-retired"
    assert not retired.exists()
    (profile / "worker.py").rename(retired)
    try:
        negative = fresh("missing_asset")
        assert negative["reply_sha256"] == positive["reply_sha256"]
    finally:
        retired.rename(profile / "worker.py")
    assert (profile / "worker.py").read_bytes() == original
    restored = fresh("positive")
    assert restored["reply_sha256"] == positive["reply_sha256"]
    print(
        json.dumps(
            {
                "actual_worker_launch": launches,
                "canonical_assets": expected,
                "removed_asset_reader": "WorkerUnavailableError",
                "complete_factory_projection": "equal",
                "authority": "known synthetic computation only",
            },
            sort_keys=True,
        )
    )


def test_installed_true_gcm_job_and_scientist_source_bound_interval_consumer(tmp_path, monkeypatch):
    site = _site()
    _configured(monkeypatch)
    fixture = _fixture("gcm")
    run = subprocess.run
    child_reads = []

    def isolated_reader(argv, **kwargs):
        if argv[0] == sys.executable and "-c" in argv:
            argv = list(argv)
            position = argv.index("-c")
            argv[position + 1] += (
                "\nfrom pathlib import Path\nfrom polisyos.foundry.methods.catalog.causal import _dowhy_worker as installed_bridge\nassert sys.flags.isolated and Path(installed_bridge.__file__).is_relative_to(Path(sys.prefix)/'lib/python3.14/site-packages')\nassert installed_bridge._worker_directory()==Path(installed_bridge.__file__).parent/'_dowhy_profile'\n"
            )
            argv.insert(1, "-I")
            child_reads.append(argv)
        actual = run(argv, **kwargs)
        if child_reads and argv == child_reads[-1]:
            print(actual.stdout, end="")
            print(actual.stderr, end="", file=sys.stderr)
        return actual

    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "run", isolated_reader)
        fixture.test_actual_gcm_job_persisted_fresh_reader_and_scientist_consumer(tmp_path, None)
    assert len(child_reads) == 1
    origins = {
        name: module.__file__
        for name, module in sys.modules.copy().items()
        if name.startswith("polisyos") and getattr(module, "__file__", None)
    }
    assert all(Path(origin).is_relative_to(site) for origin in origins.values())
    print(
        json.dumps(
            {
                "gcm_job_native_and_fresh_reader": "PASS",
                "real_scientist_bootstrap_replicates": 40,
                "interval_gate_eligible": False,
                "product_origins": origins,
            },
            sort_keys=True,
        )
    )
