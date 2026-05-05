from __future__ import annotations

import numpy as np
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.ir.analytics.causal import load_data_readiness_report, load_proof_bundle
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    EpistemicTier,
    load_negative_certificate,
)
from polisyos.ir.analytics.partial_identification import load_bounds_bundle


def _edge(src: str, dst: str, *, bidirected: bool = False) -> CausalEdge:
    if bidirected:
        return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def _bow_arc_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[
            _edge("X", "Y"),
            _edge("X", "Y", bidirected=True),
        ],
    )


def _linear_iv_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["Z", "X", "Y"],
        edges=[
            _edge("Z", "X"),
            _edge("X", "Y"),
            _edge("X", "Y", bidirected=True),
        ],
    )


def _wright_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["Z", "W", "X", "Y"],
        edges=[
            _edge("Z", "X"),
            _edge("Z", "W"),
            _edge("W", "Y"),
            _edge("X", "Y"),
            _edge("X", "Y", bidirected=True),
        ],
    )


def _data(seed: int = 0, n: int = 400) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.binomial(1, 0.5, n).astype(float)
    y = 0.6 * x + 0.5 * rng.standard_normal(n)
    return {"X": x, "Y": y}


def _linear_iv_data(seed: int = 0, n: int = 800) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n)
    u = rng.standard_normal(n)
    x = 0.8 * z + 0.9 * u + 0.25 * rng.standard_normal(n)
    y = 1.5 * x + 1.2 * u + 0.25 * rng.standard_normal(n)
    return {"Z": z, "X": x, "Y": y}


def _wright_data(seed: int = 0, n: int = 1000) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n)
    u = rng.standard_normal(n)
    w = 0.6 * z + 0.2 * rng.standard_normal(n)
    x = 0.8 * z + 0.7 * u + 0.2 * rng.standard_normal(n)
    y = 1.4 * x + 0.9 * w + 0.7 * u + 0.2 * rng.standard_normal(n)
    return {"Z": z, "W": w, "X": x, "Y": y}


def _run_bow_arc(tmp_path, seed: int = 0):
    store = FileSystemCAS(tmp_path / f"cas-bow-{seed}")
    engine = CausalEngine(artifact_store=store)
    report, bundle, cert = engine.run(
        "X",
        "Y",
        _bow_arc_graph(),
        data_dict=_data(seed=seed),
        run_id=f"hedge-{seed}",
    )
    assert report is None
    assert cert is not None
    assert cert.blocking_type is BlockingType.HEDGE_STRUCTURE
    return store, bundle, cert


def _run_linear_iv_hedge(tmp_path, seed: int = 0):
    store = FileSystemCAS(tmp_path / f"cas-linear-{seed}")
    engine = CausalEngine(artifact_store=store)
    report, bundle, cert = engine.run(
        "X",
        "Y",
        _linear_iv_graph(),
        data_dict=_linear_iv_data(seed=seed),
        run_id=f"hedge-linear-{seed}",
    )
    assert report is None
    assert cert is not None
    assert cert.blocking_type is BlockingType.HEDGE_STRUCTURE
    return store, bundle, cert


def _run_wright_hedge(tmp_path, seed: int = 0):
    store = FileSystemCAS(tmp_path / f"cas-wright-{seed}")
    engine = CausalEngine(artifact_store=store)
    report, bundle, cert = engine.run(
        "X",
        "Y",
        _wright_graph(),
        data_dict=_wright_data(seed=seed),
        run_id=f"hedge-wright-{seed}",
    )
    assert report is None
    assert cert is not None
    assert cert.blocking_type is BlockingType.HEDGE_STRUCTURE
    return store, bundle, cert


def test_fallback_provides_bounds_on_bow_arc(tmp_path) -> None:
    _, _, cert = _run_bow_arc(tmp_path)
    assert cert.partial_bounds is not None
    assert cert.bounds_bundle is not None
    assert cert.partial_bounds.lower_bound < cert.partial_bounds.upper_bound
    assert (
        cert.partial_bounds.lower_bound,
        cert.partial_bounds.upper_bound,
    ) != (-1.0, 1.0)
    assert cert.fallback_result is not None
    assert cert.fallback_result.bounds is not None
    assert cert.fallback_result.bounds_tier in {
        EpistemicTier.EXACT_NONPARAMETRIC,
        EpistemicTier.PARTIAL_IDENTIFICATION,
    }
    assert cert.recovery_plan is not None
    assert cert.recovery_plan.candidate_actions


def test_fallback_parametric_rescue_monotone(tmp_path) -> None:
    _, _, cert = _run_bow_arc(tmp_path, seed=4)
    assert cert.fallback_result is not None
    assert cert.fallback_result.parametric_rescue is not None
    assert cert.fallback_result.parametric_rescue.assumption == "monotone_treatment_response"
    assert cert.fallback_result.parametric_tier is EpistemicTier.ASSUMPTION_DEPENDENT


def test_fallback_parametric_rescue_linear(tmp_path) -> None:
    _, _, cert = _run_linear_iv_hedge(tmp_path, seed=11)
    assert cert.fallback_result is not None
    assert cert.fallback_result.parametric_rescue is not None
    assert cert.fallback_result.parametric_rescue.assumption == "linearity"
    assert cert.fallback_result.parametric_rescue.method == "wald_iv"
    assert cert.fallback_result.parametric_rescue.point_estimate is not None
    assert abs(cert.fallback_result.parametric_rescue.point_estimate - 1.5) < 0.35
    assert cert.fallback_result.parametric_rescue.estimand_formula == "Cov(Z, Y) / Cov(Z, X)"
    assert cert.fallback_result.parametric_rescue.supporting_variables == ("Z",)
    assert cert.fallback_result.parametric_tier is EpistemicTier.ASSUMPTION_DEPENDENT


def test_fallback_parametric_rescue_wright_path_tracing(tmp_path) -> None:
    _, _, cert = _run_wright_hedge(tmp_path, seed=17)
    assert cert.fallback_result is not None
    assert cert.fallback_result.parametric_rescue is not None
    assert cert.fallback_result.parametric_rescue.assumption == "linearity"
    assert cert.fallback_result.parametric_rescue.method == "wright_path_tracing"
    assert cert.fallback_result.parametric_rescue.point_estimate is not None
    assert abs(cert.fallback_result.parametric_rescue.point_estimate - 1.4) < 0.4
    assert cert.fallback_result.parametric_rescue.estimand_formula == "b_X_Y"
    assert cert.fallback_result.parametric_rescue.supporting_variables == ("Z", "W", "X", "Y")
    assert cert.fallback_result.parametric_tier is EpistemicTier.ASSUMPTION_DEPENDENT


def test_fallback_sensitivity_curve_monotone(tmp_path) -> None:
    _, _, cert = _run_bow_arc(tmp_path, seed=1)
    curve = cert.quantitative_diagnostics["sensitivity_curve"]
    lowers = [point[1] for point in curve]
    uppers = [point[2] for point in curve]
    assert lowers == sorted(lowers, reverse=True)
    assert uppers == sorted(uppers)


def test_fallback_suggested_experiments(tmp_path) -> None:
    _, _, cert = _run_bow_arc(tmp_path, seed=2)
    assert cert.suggested_experiments
    assert cert.suggested_experiments[0].design_type == "RCT"


def test_fallback_audit_trail(tmp_path) -> None:
    store, bundle, cert = _run_bow_arc(tmp_path, seed=3)
    assert bundle.run_id == "hedge-3"
    assert bundle.query_str
    assert bundle.proof_bundle_ref is not None
    assert bundle.data_readiness_report_ref is not None
    assert bundle.bounds_bundle_ref is not None
    assert bundle.negative_certificate_ref is not None
    assert cert.quantitative_diagnostics["fallback_level"] == 4
    assert load_proof_bundle(store, bundle.proof_bundle_ref).proof_status == "non_identified"
    assert load_data_readiness_report(store, bundle.data_readiness_report_ref).decision in {
        "pass",
        "warn",
        "unknown",
    }
    assert (
        load_bounds_bundle(store, bundle.bounds_bundle_ref).lower_bound
        == cert.bounds_bundle.lower_bound
    )
    assert (
        load_negative_certificate(store, bundle.negative_certificate_ref).blocking_type
        is BlockingType.HEDGE_STRUCTURE
    )
