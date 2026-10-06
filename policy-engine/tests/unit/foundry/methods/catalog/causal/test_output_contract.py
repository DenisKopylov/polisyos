"""Causal output bindings preserve report authority and specialized results."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import _common as causal_common
from polisyos.foundry.methods.catalog.causal._common import (
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.did import StandardDifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.kernel_lowering import build_kernel_estimator_spec
from polisyos.foundry.methods.catalog.causal.kernel_methods import KernelCMEPluginEstimator
from polisyos.foundry.methods.catalog.causal.operator_valued import (
    OperatorCMEKRREstimator,
    OperatorUnsupportedTargetMethod,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    PanelObservationalData,
    RDDObservationalData,
)
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.foundry.methods.components.io import dematerialize_method_output
from polisyos.ir.analytics.causal import (
    CausalMethod,
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.estimand import make_backdoor_estimand
from tests.unit.foundry.methods.catalog.causal.test_kernel_runtime import _synthetic_state
from tests.unit.foundry.methods.catalog.causal.test_operator_valued_methods import _operator_state


def _reaches_wrapper(
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    name: str,
    visited: frozenset[str],
) -> bool:
    if name in visited:
        return False
    for call in ast.walk(functions[name]):
        if not isinstance(call, ast.Call):
            continue
        target = ast.unparse(call.func)
        if target == "wrap_causal_output":
            return True
        if target in functions and _reaches_wrapper(functions, target, visited | {name}):
            return True
    return False


def _wrapped_method_classes() -> list[type]:
    """Derive local pure-step paths to the wrapper from every causal Python file.

    This census selects common-wrapper consumers through direct local calls.
    It does not classify reflected calls, plugin code outside this directory,
    or the scientific semantics of method-specific extra output fields.
    """
    catalog = Path(causal_common.__file__).parent
    methods = []
    for path in sorted(catalog.rglob("*.py")):
        functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        classes: dict[str, str] = {}
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[node.name] = node
            elif isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions[f"{node.name}.{member.name}"] = member
                if f"{node.name}.pure_step" in functions:
                    classes[node.name] = f"{node.name}.pure_step"

        selected = [
            name
            for name, path_name in classes.items()
            if _reaches_wrapper(functions, path_name, frozenset())
        ]
        if selected:
            suffix = path.relative_to(catalog).with_suffix("")
            module = importlib.import_module(
                "polisyos.foundry.methods.catalog.causal." + ".".join(suffix.parts)
            )
            methods.extend(getattr(module, name) for name in selected)
    assert methods, "the source census must select actual causal wrapper consumers"
    return methods


def _report(status: EstimationStatus):
    common = {
        "method": CausalMethod.REGRESSION_DISCONTINUITY,
        "estimand": "ATE",
        "sample_size": 80,
        "n_treated": 40,
        "n_control": 40,
        "pre_periods": 0,
        "post_periods": 0,
        "assumptions": {},
    }
    if status is EstimationStatus.SUCCESS:
        return build_success_report(
            **common,
            point_estimate=3.0,
            confidence_interval=(2.0, 4.0),
            inference_method="asymptotic",
        )
    return build_failure_report(**common, status=status, reason="bounded unsupported inference")


@pytest.mark.parametrize("status", [EstimationStatus.SUCCESS, EstimationStatus.INPUT_INVALID])
def test_every_local_wrapper_consumer_gets_its_common_declared_ports(status):
    """Live signatures bind the same report/envelope, including failure authority."""
    report = _report(status)
    output = wrap_causal_output(report)
    expected = {
        "report": report,
        "causal_effect_report": report,
        "result": report,
        "envelope": output["envelope"],
        "uncertainty_envelope": output["envelope"],
        "warnings": output["warnings"],
    }
    for method in _wrapped_method_classes():
        for slot in method.signature.output_slots:
            if slot.name in expected:
                assert output[slot.name] is expected[slot.name], method.signature.fqn
    assert output["envelope"].gate_eligible is (status is EstimationStatus.SUCCESS)


@pytest.mark.parametrize(
    "reserved", ["report", "causal_effect_report", "envelope", "uncertainty_envelope"]
)
def test_extras_cannot_replace_shared_authority_outputs(reserved):
    """A successful-looking extra cannot replace a refusal's bound projection."""
    refused = _report(EstimationStatus.INPUT_INVALID)
    successful = _report(EstimationStatus.SUCCESS)
    replacement = successful if "report" in reserved else successful.to_uncertainty_envelope()

    with pytest.raises(ValueError, match="reserved causal output"):
        wrap_causal_output(refused, extras={reserved: replacement})


@pytest.mark.parametrize("method", [RegressionDiscontinuity, StandardDifferenceInDifferences])
def test_native_estimator_declared_report_survives_dispatch_and_cas(method, tmp_path):
    """A known jump/ATT reaches the declared consumer field and persists unchanged."""
    if method is RegressionDiscontinuity:
        x = np.linspace(-1.0, 1.0, 101)
        data = RDDObservationalData(
            running_variable=x, outcome=3.0 * (x >= 0.0) + 0.2 * x, cutoff=0.0
        )
        params = {"bandwidth": 1.0, "manipulation_test": False}
    else:
        data = PanelObservationalData(
            outcome=np.array([[1.0, 2.0, 6.0, 7.0], [2.0, 3.0, 4.0, 5.0]]),
            treatment=np.array([1, 0]),
            time_treatment=2,
        )
        params = {}
    output = (
        MethodDispatcher.get_instance()
        .dispatch(
            method_class=method, signature=method.signature, state=data, params=params, seed=11
        )
        .output
    )
    assert set(method.signature.output_slot_names) <= set(output)
    report = output["causal_effect_report"]
    assert report is output["report"] is output["result"]
    assert report.point_estimate == pytest.approx(3.0)
    normalized = dematerialize_method_output(
        method_class=method, signature=method.signature, output=output
    )
    declared_report = normalized[
        "causal_effect_report" if method is RegressionDiscontinuity else "result"
    ]
    assert declared_report is report
    store = FileSystemCAS(tmp_path)
    ref = persist_causal_effect_report(store, declared_report)
    loaded = load_causal_effect_report(FileSystemCAS(store.root), ref)
    assert loaded.point_estimate == pytest.approx(3.0)
    assert loaded.status is EstimationStatus.SUCCESS


def test_native_kernel_specialized_result_is_preserved_at_consumer():
    """The shared report alias does not overwrite a distinct kernel result DTO."""
    estimand = make_backdoor_estimand(
        treatment="T", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
    )
    spec = build_kernel_estimator_spec(
        estimand,
        shape="backdoor",
        identification_metadata={
            "kernel_lowering_requested": True,
            "distributional_query_kind": "interventional_law",
            "variable_roles": {"treatment": ("treatment",), "outcome": ("outcome",)},
        },
    )
    output = KernelCMEPluginEstimator.pure_step(
        _synthetic_state(n_obs=40), {"kernel_spec": spec.model_dump(mode="json"), "__seed__": 11}
    )
    assert output["causal_effect_report"] is output["report"]
    assert output["uncertainty_envelope"] is output["envelope"]
    assert output["result"] is not output["report"]
    normalized = dematerialize_method_output(
        method_class=KernelCMEPluginEstimator,
        signature=KernelCMEPluginEstimator.signature,
        output=output,
    )
    assert normalized["result"] is output["result"]
    assert normalized["result"]["effect_norm"] == output["kernel_report"]["effect_norm"]


def test_alias_fallback_does_not_prove_actual_declared_output():
    """Keep legacy keys: normalization succeeds while the direct ABI is absent."""
    output = wrap_causal_output(_report(EstimationStatus.SUCCESS))
    output.pop("causal_effect_report")
    normalized = dematerialize_method_output(
        method_class=RegressionDiscontinuity,
        signature=RegressionDiscontinuity.signature,
        output=output,
    )
    assert normalized["causal_effect_report"] is output["report"]
    with pytest.raises(AssertionError):
        assert set(RegressionDiscontinuity.signature.output_slot_names) <= set(output)


@pytest.mark.parametrize("method", [OperatorCMEKRREstimator, OperatorUnsupportedTargetMethod])
def test_native_operator_specialized_result_is_preserved_at_consumer(method):
    """Both an estimated operator and a typed refusal retain their own result."""
    state = _operator_state() if method is OperatorCMEKRREstimator else {}
    output = method.pure_step(state, {"reference_treatment": 0.0, "max_evaluation_points": 4})
    assert set(method.signature.output_slot_names) <= set(output)
    assert output["causal_effect_report"] is output["report"]
    assert output["uncertainty_envelope"] is output["envelope"]
    assert output["result"] is not output["report"]
    normalized = dematerialize_method_output(
        method_class=method, signature=method.signature, output=output
    )
    assert normalized["result"] is output["result"]
    if method is OperatorCMEKRREstimator:
        assert (
            normalized["result"]["operator_matrix"]
            == output["operator_effect_bundle"]["operator_matrix"]
        )
        assert output["envelope"].gate_eligible is True
    else:
        assert normalized["result"]["status"] == "failed"
        assert output["envelope"].gate_eligible is False
