"""DiD report diagnostics are recomputed by actual job and CAS consumers."""

import copy
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from polisyos.core.artifacts import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.catalog.causal.did import (
    StaggeredDifferenceInDifferences,
    StandardDifferenceInDifferences,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import CausalEffectReport, EstimationStatus
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
    _run_primary_causal_job,
    _verify_selected_did_diagnostics,
    _verify_selected_did_target,
)


def _panel(pre=3):
    timing = np.array([3, 3, 4, 4, -1, -1, -1, -1])
    y = np.tile(np.arange(6, dtype=float), (8, 1))
    y[:4, :3] += [0.0, 0.5, -0.3]
    y[:2, 3:] += np.array([1.0, 3.0])[:, None]
    y[2:4, 4:] += np.array([2.0, 5.0])[:, None]
    y[4:, 3:] += np.arange(4)[:, None] * 0.2
    return PanelObservationalData(
        outcome=y,
        treatment=(timing >= 0).astype(int),
        time_treatment=pre,
        treatment_timing=timing,
        unit_ids=np.arange(8),
    )


def _source(ctx, state, data, method):
    ref = ctx.store.put_json(
        data.model_dump(mode="json"),
        PutOptions(kind="tests.diagnostic_source", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    MethodRegistry.get_instance().register(method, override=True)
    return state.model_copy(
        update={"observational_data_ref": ref, "causal_method_fqn": method.signature.fqn}
    ), ref


@pytest.mark.parametrize(
    "method", [StandardDifferenceInDifferences, StaggeredDifferenceInDifferences]
)
def test_real_method_job_and_fresh_reader_validate_complete_diagnostic(
    execution_context, minimal_state, method
):
    data = _panel()
    params = {"n_bootstrap": 99} if method is StaggeredDifferenceInDifferences else {}
    if method is StandardDifferenceInDifferences:
        data = data.model_copy(update={"treatment_timing": np.where(data.treatment, 3, -1)})
    state, source = _source(execution_context, minimal_state, data, method)
    result = _run_primary_causal_job(
        ctx=execution_context,
        state=state,
        observational_data=data,
        spec=JobSpec(
            job_kind="method",
            method_fqn=method.signature.fqn,
            method_params=params,
            seed=13,
        ),
    )
    assert not result.issues
    report = CausalEffectReport.model_validate(result.final_state["report"])
    assert report.status is EstimationStatus.SUCCESS
    reader = """
import json,sys
from polisyos.core.artifacts import FileSystemCAS,ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import _verify_selected_did_diagnostics
store=FileSystemCAS(sys.argv[1])
data=PanelObservationalData.model_validate(from_canonical_bytes(store.get_bytes(ArtifactRef.model_validate_json(sys.argv[2]))))
output=from_canonical_bytes(store.get_bytes(ArtifactRef.model_validate_json(sys.argv[3])))
_verify_selected_did_diagnostics(output,observational_data=data,staggered=sys.argv[4]=='1')
assert output['report']['method_params']['parallel_trends_identified'] is False
print('PASS actual persisted numerical diagnostic; identification authority not established')
"""
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            reader,
            str(execution_context.store.root),
            source.model_dump_json(),
            result.method_result_ref.model_dump_json(),
            "1" if method is StaggeredDifferenceInDifferences else "0",
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert child.returncode == 0, child.stdout + child.stderr


def test_changed_only_diagnostic_window_refuses_in_actual_primary_job(
    execution_context, minimal_state
):
    old_data = _panel(pre=2)
    current = old_data.model_copy(update={"time_treatment": 3})
    method = StaggeredDifferenceInDifferences
    state, _ = _source(execution_context, minimal_state, current, method)
    old = method.pure_step(old_data, {"n_bootstrap": 99, "__rng__": np.random.default_rng(13)})
    _verify_selected_did_target(old, observational_data=current, params={"n_bootstrap": 99})
    # The genuine job receives an old materialization while its actual source
    # now has a different diagnostic window. The target alone still binds.
    with pytest.raises(ValueError, match="diagnostic basis/result"):
        _run_primary_causal_job(
            ctx=execution_context,
            state=state,
            observational_data=old_data,
            spec=JobSpec(
                job_kind="method",
                method_fqn=method.signature.fqn,
                method_params={"n_bootstrap": 99},
                seed=13,
            ),
        )


@pytest.mark.parametrize(
    "mutation", ["window", "result", "missing", "coherent_forgery", "basis", "marker_only"]
)
def test_fresh_cas_reader_refuses_diagnostic_substitution_with_target_markers_retained(
    execution_context, mutation
):
    data = _panel()
    output = StaggeredDifferenceInDifferences.pure_step(
        data, {"n_bootstrap": 99, "__rng__": np.random.default_rng(13)}
    )
    output = copy.deepcopy(output)
    report = output["report"].model_dump(mode="json")
    target = copy.deepcopy(
        {k: report["method_params"][k] for k in ["target_contract", "target_binding"]}
    )
    if mutation == "window":
        data = data.model_copy(update={"time_treatment": 2})
    elif mutation == "result":
        report["diagnostics"][0]["passed"] = not report["diagnostics"][0]["passed"]
    elif mutation == "missing":
        report["method_params"].pop("diagnostic_binding")
    elif mutation == "basis":
        report["method_params"]["diagnostic_contract"]["input_sha256"] = "0" * 64
    elif mutation == "marker_only":
        report["method_params"]["diagnostic_contract"] = {
            "profile": "pretrend_group_mean_linear_hc1_normal_v1",
            "identification_authority": False,
        }
    else:
        report["diagnostics"][0]["p_value"] = 0.999
        report["diagnostics"][0]["passed"] = True
        contract = report["method_params"]["diagnostic_contract"]
        contract["diagnostics"] = copy.deepcopy(report["diagnostics"])

        def digest(value):
            return hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            ).hexdigest()

        contract["result_sha256"] = digest(contract["diagnostics"])
        report["method_params"]["diagnostic_binding"] = digest(contract)
    assert report["status"] == EstimationStatus.SUCCESS.value
    assert {k: report["method_params"][k] for k in target} == target
    output["report"] = report
    ref = execution_context.store.put_json(
        output,
        PutOptions(kind="tests.diagnostic_output", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    saved = from_canonical_bytes(execution_context.store.get_bytes(ref))
    with pytest.raises(ValueError, match="diagnostic"):
        _verify_selected_did_diagnostics(saved, observational_data=data, staggered=True)
