from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import dowhy_refute as refute_module
from polisyos.foundry.methods.causal import GraphCausalData, ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus, RefutationTestType


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _confounded_fixture(n: int = 4000, seed: int = 123) -> GraphCausalData:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    x = 0.9 * z + rng.normal(0.0, 0.3, size=n)
    y = 1.2 * x + 1.0 * z + rng.normal(0.0, 0.3, size=n)
    return GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; X -> Y; }",
        graph_ref="cas:graph:refute",
        covariates=["Z"],
    )


def _dispatch_report(data: GraphCausalData, *, params: dict[str, object] | None = None):
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.refutation.dowhy_refute@1.0.0")
    result = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params=params or {},
        seed=17,
    )
    return result.output["report"]


def test_dowhy_refute_graceful_fail_when_dependency_missing(monkeypatch):
    def _raise_import_error():
        raise ModuleNotFoundError("No module named 'dowhy'")

    monkeypatch.setattr(refute_module, "_load_dowhy_dependencies", _raise_import_error)
    report = _dispatch_report(_confounded_fixture(n=256))

    assert report.status == EstimationStatus.NUMERICAL_FAILURE
    assert report.status_reason is not None
    assert "backend unavailable" in report.status_reason.lower()


def test_dowhy_refute_marks_random_common_cause_passed_on_confounded_fixture():
    pytest.importorskip("dowhy")
    report = _dispatch_report(
        _confounded_fixture(),
        params={
            "method_name": "backdoor.linear_regression",
            "effect_ratio_tolerance": 0.5,
            "p_value_threshold": 0.0,
        },
    )

    tests = {item.test_type: item for item in report.refutation_results}
    assert RefutationTestType.RANDOM_COMMON_CAUSE in tests
    assert tests[RefutationTestType.RANDOM_COMMON_CAUSE].passed is True


def test_dowhy_refute_always_emits_four_required_tests(monkeypatch):
    class _FakeEstimate:
        value = 1.0

        @staticmethod
        def get_standard_error():
            return 0.1

        @staticmethod
        def get_confidence_intervals():
            return np.array([0.8, 1.2], dtype=float)

    class _FakeModel:
        def __init__(self, *, data, treatment, outcome, graph):
            del data, treatment, outcome, graph

        @staticmethod
        def identify_effect(*, proceed_when_unidentifiable: bool):
            del proceed_when_unidentifiable
            return "identified"

        @staticmethod
        def estimate_effect(*args, **kwargs):
            del args, kwargs
            return _FakeEstimate()

        @staticmethod
        def refute_estimate(*args, **kwargs):
            del args, kwargs
            raise RuntimeError("synthetic refuter failure")

    class _FakeDoWhy:
        CausalModel = _FakeModel

    class _FakePandas:
        @staticmethod
        def DataFrame(data, columns):
            return {"data": data, "columns": columns}

    monkeypatch.setattr(
        refute_module,
        "_load_dowhy_dependencies",
        lambda: (_FakeDoWhy(), _FakePandas()),
    )

    report = _dispatch_report(_confounded_fixture(n=256))

    assert len(report.refutation_results) == 4
    assert {item.test_type for item in report.refutation_results} == {
        RefutationTestType.PLACEBO_TREATMENT,
        RefutationTestType.RANDOM_COMMON_CAUSE,
        RefutationTestType.DATA_SUBSET,
        RefutationTestType.BOOTSTRAP,
    }
    assert all(item.passed is False for item in report.refutation_results)
