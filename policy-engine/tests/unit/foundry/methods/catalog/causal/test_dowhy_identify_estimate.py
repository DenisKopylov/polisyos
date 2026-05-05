from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import dowhy_identify_estimate as dowhy_module
from polisyos.foundry.methods.causal import (
    GraphCausalData,
    GraphCausalDataV1,
    ensure_causal_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _fork_fixture_v2(n: int = 6000, seed: int = 41) -> tuple[GraphCausalData, float]:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    x = 0.8 * z + rng.normal(0.0, 0.2, size=n)
    y = 1.2 * z + rng.normal(0.0, 0.2, size=n)
    payload = GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; }",
        graph_ref="cas:graph:fork",
        covariates=["Z"],
    )
    return payload, 0.0


def _chain_fixture_v2(n: int = 6000, seed: int = 42) -> tuple[GraphCausalData, float]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    m = 0.7 * x + rng.normal(0.0, 0.2, size=n)
    y = 1.3 * m + rng.normal(0.0, 0.2, size=n)
    payload = GraphCausalData(
        data=np.column_stack([x, y, m]),
        column_names=["X", "Y", "M"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { X -> M; M -> Y; }",
        graph_ref="cas:graph:chain",
    )
    return payload, 0.91


def _linear_confounding_fixture_v2(n: int = 6000, seed: int = 44) -> tuple[GraphCausalData, float]:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    x = 0.9 * z + rng.normal(0.0, 0.3, size=n)
    beta_xy = 1.2
    y = beta_xy * x + 1.1 * z + rng.normal(0.0, 0.3, size=n)
    payload = GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; X -> Y; }",
        graph_ref="cas:graph:linear_confounding",
        covariates=["Z"],
    )
    return payload, beta_xy


def _diamond_fixture_v2(n: int = 6000, seed: int = 43) -> tuple[GraphCausalData, float]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    a = 0.7 * x + rng.normal(0.0, 0.2, size=n)
    b = 0.5 * x + rng.normal(0.0, 0.2, size=n)
    y = 0.8 * a + 0.6 * b + rng.normal(0.0, 0.2, size=n)
    payload = GraphCausalData(
        data=np.column_stack([x, y, a, b]),
        column_names=["X", "Y", "A", "B"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { X -> A; X -> B; A -> Y; B -> Y; }",
        graph_ref="cas:graph:diamond",
    )
    return payload, 0.86


def _fork_fixture_v1(n: int = 6000, seed: int = 41) -> tuple[GraphCausalDataV1, float]:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    x = 0.8 * z + rng.normal(0.0, 0.2, size=n)
    y = 1.2 * z + rng.normal(0.0, 0.2, size=n)
    payload = GraphCausalDataV1(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_gml="digraph { Z -> X; Z -> Y; }",
        graph_ref="cas:graph:fork-v1",
        covariates=["Z"],
    )
    return payload, 0.0


def _dispatch_report(
    data: GraphCausalData | GraphCausalDataV1,
    *,
    method_fqn: str,
    params: dict[str, object] | None = None,
    seed: int = 11,
):
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get(method_fqn)
    result = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params=params or {},
        seed=seed,
    )
    return result.output["report"]


def test_dowhy_v2_linear_confounding_matches_ground_truth():
    pytest.importorskip("dowhy")
    data, ground_truth = _linear_confounding_fixture_v2()
    report = _dispatch_report(
        data,
        method_fqn="causal.inference.dowhy_identify_estimate@2.0.0",
        params={
            "method_name": "backdoor.linear_regression",
            "estimand_type": "nonparametric-ate",
        },
    )
    assert report.status == EstimationStatus.SUCCESS
    assert abs(report.point_estimate - ground_truth) <= 0.1
    assert report.method == CausalMethod.DOWHY_BACKDOOR
    assert report.identified_estimand is not None
    assert report.estimand_type == "nonparametric-ate"
    assert report.graph_ref == "cas:graph:linear_confounding"


@pytest.mark.parametrize(
    ("fixture_builder", "tolerance"),
    [
        (_fork_fixture_v2, 0.1),
        (_chain_fixture_v2, 0.2),
        (_diamond_fixture_v2, 0.2),
    ],
)
def test_dowhy_v2_smoke_on_phase2_fixtures(fixture_builder, tolerance: float):
    pytest.importorskip("dowhy")
    data, ground_truth = fixture_builder()
    report = _dispatch_report(
        data,
        method_fqn="causal.inference.dowhy_identify_estimate@2.0.0",
        params={"method_name": "backdoor.linear_regression"},
    )
    assert report.status == EstimationStatus.SUCCESS
    assert abs(report.point_estimate - ground_truth) <= tolerance


def test_dowhy_v1_legacy_contract_still_works():
    pytest.importorskip("dowhy")
    data, _ = _fork_fixture_v1(n=1000)
    report = _dispatch_report(
        data,
        method_fqn="causal.inference.dowhy_identify_estimate@1.0.0",
        params={"method_name": "backdoor.linear_regression"},
    )
    assert report.status == EstimationStatus.SUCCESS
    assert report.graph_ref == "cas:graph:fork-v1"


def test_dowhy_v2_graceful_fail_when_dependency_missing(monkeypatch):
    def _raise_import_error():
        raise ModuleNotFoundError("No module named 'dowhy'")

    monkeypatch.setattr(dowhy_module, "_load_dowhy_dependencies", _raise_import_error)
    data, _ = _fork_fixture_v2(n=128)
    report = _dispatch_report(
        data,
        method_fqn="causal.inference.dowhy_identify_estimate@2.0.0",
        params={"method_name": "backdoor.linear_regression"},
    )
    assert report.status == EstimationStatus.NUMERICAL_FAILURE
    assert report.method == CausalMethod.DOWHY_BACKDOOR
    assert report.status_reason is not None
    assert "backend unavailable" in report.status_reason.lower()


def test_dowhy_v1_method_name_mapping_is_deterministic_on_failure(monkeypatch):
    def _raise_import_error():
        raise ModuleNotFoundError("No module named 'dowhy'")

    monkeypatch.setattr(dowhy_module, "_load_dowhy_dependencies", _raise_import_error)
    data, _ = _fork_fixture_v1(n=128)
    report = _dispatch_report(
        data,
        method_fqn="causal.inference.dowhy_identify_estimate@1.0.0",
        params={"method_name": "iv.instrumental_variable"},
    )
    assert report.status == EstimationStatus.NUMERICAL_FAILURE
    assert report.method == CausalMethod.DOWHY_IV
