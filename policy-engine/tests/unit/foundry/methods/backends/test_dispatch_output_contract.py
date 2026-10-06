"""Exercise canonical slot monitoring through real backend dispatch."""

from __future__ import annotations

import warnings
from dataclasses import replace
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.foundry.methods.catalog.ml import ensure_ml_methods_registered
from polisyos.foundry.methods.catalog.ml.protocols import TabularData
from polisyos.foundry.methods.exceptions import MethodContractError
from polisyos.foundry.methods.lifecycle.output_monitor import MethodOutputMonitor
from polisyos.foundry.methods.registry import MethodRegistry


class _AliasedVector:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="aliased_vector",
        namespace="tests.monitor",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {SlotSpec("result", SlotType.VECTOR, Unit("signal", "1"), shape=(2,))}
        ),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="Native alias test producer")

    @staticmethod
    def pure_step(state: Any, params: Any) -> Any:
        return state


class _VariableVector(_AliasedVector):
    signature = replace(
        _AliasedVector.signature,
        name="variable_vector",
        output_slots=frozenset({SlotSpec("result", SlotType.VECTOR, Unit("signal", "1"))}),
    )


@pytest.fixture(autouse=True)
def _reset_registry() -> Any:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _dispatch_registered(method: type, state: Any, params: dict[str, Any] | None = None) -> Any:
    registry = MethodRegistry.get_instance()
    registry.register(method, override=True)
    resolved = registry.get(method.signature.fqn)
    return MethodDispatcher.get_instance().dispatch(
        method_class=resolved,
        signature=resolved.signature,
        state=state,
        params=params or {},
        seed=13,
    )


def test_native_alias_and_sidecars_do_not_create_slot_anomalies() -> None:
    values = np.array([2.0, 5.0])
    raw = {"report": values, "envelope": {"candidate": True}, "warnings": ["candidate"]}
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        result = _dispatch_registered(_AliasedVector, raw)
    assert result.output is raw
    assert result.slot_outputs["result"] is values
    assert list(result.slot_outputs) == ["result"]
    assert observed == []


@pytest.mark.parametrize(
    "payload, error",
    [
        ({"envelope": {"candidate": True}}, "missing output for declared slot"),
        ({"report": np.array([[1.0, 2.0]])}, "expects VECTOR"),
        ({"report": np.array([1.0])}, "expected shape"),
    ],
)
def test_actual_runner_rejects_missing_and_malformed_declared_slots(
    payload: Any, error: str
) -> None:
    with pytest.raises(MethodContractError, match=error):
        _dispatch_registered(_AliasedVector, payload)


def test_raw_numeric_sidecar_remains_an_error_diagnostic(monkeypatch: Any) -> None:
    emissions: list[Any] = []
    monkeypatch.setattr(
        "polisyos.foundry.methods.backends.dispatch._emit_anomaly_metric",
        lambda fqn, flags: emissions.append((fqn, flags)),
    )
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        result = _dispatch_registered(
            _AliasedVector,
            {"report": np.array([2.0, 5.0]), "diagnostic_draw": np.array([np.nan, np.inf])},
        )
    np.testing.assert_array_equal(result.slot_outputs["result"], [2.0, 5.0])
    messages = [str(w.message) for w in observed]
    assert len(messages) == 2
    assert any("nan_detected" in m and "diagnostic_draw" in m for m in messages)
    assert any("inf_detected" in m and "diagnostic_draw" in m for m in messages)
    assert all("unexpected_key" not in m and "missing_key" not in m for m in messages)
    assert len(emissions) == 1
    assert emissions[0][0] == _AliasedVector.signature.fqn
    assert {flag.reason for flag in emissions[0][1]} == {"nan_detected", "inf_detected"}
    assert all(flag.severity == "error" for flag in emissions[0][1])


def test_empty_diagnostics_and_explicit_numeric_empties_are_distinct() -> None:
    monitor = MethodOutputMonitor()
    flags = monitor.check_output_contract(
        slot_outputs={"result": np.array([], dtype=float), "diagnostics": []},
        raw_output={"result": np.array([], dtype=float), "warnings": (), "audit": []},
        expected_keys={"result", "diagnostics"},
    )
    assert [(f.key, f.reason, f.severity) for f in flags] == [("result", "empty_array", "warning")]


def test_nonempty_numeric_sequences_keep_nan_inf_diagnostics() -> None:
    flags = MethodOutputMonitor().check_output_contract(
        slot_outputs={"result": np.array([2.0, 5.0])},
        raw_output={"diagnostics": [np.nan, np.inf]},
        expected_keys={"result"},
    )
    assert {(f.key, f.reason, f.severity) for f in flags} == {
        ("diagnostics", "nan_detected", "error"),
        ("diagnostics", "inf_detected", "error"),
    }


def test_declared_vector_empty_list_keeps_native_warning() -> None:
    with pytest.warns(UserWarning, match="result: empty_array") as observed:
        result = _dispatch_registered(_VariableVector, {"report": []})
    assert result.slot_outputs["result"] == []
    assert len(observed) == 1


def test_canonical_missing_and_extra_keys_remain_typed_errors() -> None:
    flags = MethodOutputMonitor().check_output_contract(
        slot_outputs={"wrong": np.array([2.0, 5.0])},
        raw_output={"report": np.array([2.0, 5.0])},
        expected_keys={"result"},
    )
    assert {(f.key, f.reason, f.severity) for f in flags} == {
        ("result", "missing_key", "error"),
        ("wrong", "unexpected_key", "warning"),
    }


def test_registered_standard_did_report_alias_uses_canonical_slot() -> None:
    ensure_causal_methods_registered()
    method = MethodRegistry.get_instance().get("causal.inference.did.standard@1.0.0")
    control = np.tile(np.arange(10, dtype=float), (5, 1))
    treated = control[:3].copy()
    treated[:, 5:] += 3.0
    data = PanelObservationalData(
        outcome=np.vstack([treated, control]),
        treatment=np.array([1, 1, 1, 0, 0, 0, 0, 0]),
        time_treatment=5,
    )
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        result = _dispatch_registered(method, data)
    assert result.slot_outputs["result"] is result.output["report"]
    assert result.slot_outputs["result"].point_estimate == pytest.approx(3.0)
    assert observed == []


def test_registered_noncausal_prediction_preserves_its_slot_contract() -> None:
    ensure_ml_methods_registered()
    method = MethodRegistry.get_instance().get("ml.regression.random_forest@1.0.0")
    x = np.linspace(-1.0, 1.0, 32)
    data = TabularData(features=x[:, None], target=1.0 + 2.0 * x)
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        result = _dispatch_registered(method, data, {"n_estimators": 50})
    assert result.slot_outputs["result"] is result.output["result"]
    assert result.slot_outputs["uncertainty_envelope"] is result.output["uncertainty_envelope"]
    assert result.slot_outputs["result"].predictions.shape == (32,)
    assert observed == []
