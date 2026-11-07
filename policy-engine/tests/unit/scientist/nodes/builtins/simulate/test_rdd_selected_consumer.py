"""Source-bound RDD jobs and their complete persisted report consumers."""

import copy
import os
import subprocess
import sys

import numpy as np
import pytest

from polisyos.core.artifacts import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.catalog.causal.protocols import RDDObservationalData
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.foundry.methods.components.io import materialize_method_input
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as evaluation


def _source(ctx, state, *, n=201):
    x = np.linspace(-1.0, 1.0, n)
    cutoff = 0.2
    data = RDDObservationalData(
        running_variable=x,
        outcome=0.4 * x + 2.5 * (x >= cutoff) + 0.025 * np.sin(np.arange(x.size)),
        cutoff=cutoff,
    )
    # Exercise the real bound-vector materializer; the cutoff comes from its typed fallback.
    data = materialize_method_input(
        method_class=RegressionDiscontinuity,
        signature=RegressionDiscontinuity.signature,
        bound_inputs={"running_variable": data.running_variable, "outcome": data.outcome},
        fallback_state=data.model_copy(
            update={"running_variable": np.zeros_like(x), "outcome": np.zeros_like(x)}
        ),
    )
    ref = ctx.store.put_json(
        data.model_dump(mode="json"),
        PutOptions(kind="tests.rdd_source", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    MethodRegistry.get_instance().register(RegressionDiscontinuity, override=True)
    return data, state.model_copy(update={"observational_data_ref": ref}), ref


def _spec():
    return JobSpec(
        job_kind="method",
        method_fqn=RegressionDiscontinuity.signature.fqn,
        method_params={"bandwidth": 0.5, "kernel": "uniform", "manipulation_test": False},
        seed=13,
    )


def test_actual_rdd_job_refuses_materialized_cutoff_not_in_selected_source(
    execution_context, minimal_state
):
    data, state, _ = _source(execution_context, minimal_state)
    stale = data.model_copy(update={"cutoff": -0.2})
    with pytest.raises(ValueError, match="RDD materialization/source mismatch"):
        evaluation._run_primary_causal_job(
            ctx=execution_context, state=state, observational_data=stale, spec=_spec()
        )


def test_actual_rdd_job_refuses_coherently_rewritten_report_and_envelope(
    execution_context, minimal_state, monkeypatch
):
    data, state, _ = _source(execution_context, minimal_state)
    original = evaluation.run_job

    def substituted_job(*args, **kwargs):
        result = original(*args, **kwargs)
        assert not result.issues
        output = copy.deepcopy(result.final_state)
        report = CausalEffectReport.model_validate(output["report"])
        changed = report.model_copy(
            update={
                "point_estimate": report.point_estimate + 10.0,
                "confidence_interval": tuple(x + 10.0 for x in report.confidence_interval),
            }
        )
        output["report"] = changed
        output["envelope"] = changed.to_uncertainty_envelope()
        ref = execution_context.store.put_json(
            output,
            PutOptions(kind="tests.rdd_substituted_output", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        saved = from_canonical_bytes(execution_context.store.get_bytes(ref))
        return result.model_copy(update={"final_state": saved, "method_result_ref": ref})

    monkeypatch.setattr(evaluation, "run_job", substituted_job)
    with pytest.raises(ValueError, match="numerical report projection mismatch"):
        evaluation._run_primary_causal_job(
            ctx=execution_context, state=state, observational_data=data, spec=_spec()
        )


@pytest.mark.parametrize(
    ("profile", "n"),
    [
        ("legacy", 201),
        ("legacy-by-version", 201),
        ("kernel_hc0", 201),
        ("rbc", 201),
        ("kernel_hc0", 8000),
    ],
    ids=["legacy", "legacy-by-version", "kernel-hc0", "rbc", "kernel-hc0-native-8000"],
)
def test_registered_rdd_materializer_cas_and_fresh_consumer_preserve_current_profile(
    execution_context, minimal_state, profile, n
):
    from polisyos.foundry.methods.catalog.causal.rdd import KernelHC0RegressionDiscontinuity

    data, state, source = _source(execution_context, minimal_state, n=n)
    assert data.sample_size == n
    method = (
        KernelHC0RegressionDiscontinuity if profile == "kernel_hc0" else RegressionDiscontinuity
    )
    MethodRegistry.get_instance().register(method, override=True)
    spec = _spec().model_copy(update={"method_fqn": method.signature.fqn})
    if profile == "legacy-by-version":
        spec = spec.model_copy(
            update={
                "method_fqn": method.signature.fqn.split("@", 1)[0],
                "method_version": method.signature.version,
            }
        )
    if profile == "rbc":
        spec = spec.model_copy(
            update={
                "method_params": {
                    **spec.method_params,
                    "bias_correction": True,
                    "bias_bandwidth": 0.7,
                }
            }
        )
    result = evaluation._run_primary_causal_job(
        ctx=execution_context, state=state, observational_data=data, spec=spec
    )
    assert not result.issues
    report = CausalEffectReport.model_validate(result.final_state["report"])
    assert report.point_estimate == pytest.approx(2.5, abs=0.02)
    assert report.method_params["cutoff"] == data.cutoff
    assert report.to_uncertainty_envelope().gate_eligible is False
    reader = """
import json,sys
from types import SimpleNamespace
from polisyos.core.artifacts import ArtifactRef,FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.methods.catalog.causal.protocols import RDDObservationalData
from polisyos.scientist.compute.job_spec import JobResult,JobSpec
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import _reconcile_selected_causal_output
store=FileSystemCAS(sys.argv[1])
data=RDDObservationalData.model_validate(from_canonical_bytes(store.get_bytes(ArtifactRef.model_validate_json(sys.argv[2]))))
result=JobResult.model_validate_json(sys.argv[3])
spec=JobSpec.model_validate_json(sys.argv[4])
_reconcile_selected_causal_output(ctx=SimpleNamespace(store=store),result=result,observational_data=data,spec=spec)
assert result.final_state['envelope']['gate_eligible'] is False
assert data.sample_size == int(sys.argv[5])
print('PASS actual registered RDD/source/materializer/report/fresh consumer; empirical assumptions not established')
"""
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            reader,
            str(execution_context.store.root),
            source.model_dump_json(),
            result.model_dump_json(),
            spec.model_dump_json(),
            str(n),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert child.returncode == 0, child.stdout + child.stderr
