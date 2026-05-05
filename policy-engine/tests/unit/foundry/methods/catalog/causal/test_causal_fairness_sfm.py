from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.causal.causal_fairness import (
    CausalFairnessEngine,
    StandardFairnessModel,
    fairness_bounds,
    identify_fairness_effects,
    tv_decomposition,
)
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType


def _edge(src: str, dst: str, *, bidirected: bool = False) -> CausalEdge:
    if bidirected:
        return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def _graph(*, latent_ay: bool = False) -> CausalGraphModel:
    edges = [
        _edge("C", "A"),
        _edge("C", "Y"),
        _edge("A", "M"),
        _edge("M", "Y"),
        _edge("A", "Y"),
    ]
    if latent_ay:
        edges.append(_edge("A", "Y", bidirected=True))
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["A", "C", "M", "Y"],
        edges=edges,
    )


def _state(seed: int = 0, n: int = 600) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    c = rng.standard_normal((n, 1))
    p_a = 1.0 / (1.0 + np.exp(-0.8 * c[:, 0]))
    a = rng.binomial(1, p_a).astype(float)
    m = 0.7 * a + 0.3 * c[:, 0] + 0.1 * rng.standard_normal(n)
    y = 0.25 * a + 0.45 * m + 0.4 * c[:, 0] + 0.2 * rng.standard_normal(n)
    return {
        "outcome": y,
        "protected": a,
        "covariates": c,
        "mediators": m.reshape(-1, 1),
        "__seed__": seed,
    }


def _sfm(*, latent_ay: bool = False) -> StandardFairnessModel:
    return StandardFairnessModel(
        protected_attribute="A",
        mediators=["M"],
        outcome="Y",
        confounders=["C"],
        graph=_graph(latent_ay=latent_ay),
    )


def test_tv_decomposition_sums_to_tv() -> None:
    decomp = tv_decomposition(_sfm(), _state())
    total = decomp.direct_effect + decomp.indirect_effect + decomp.spurious_effect
    assert abs(decomp.tv - total) < 0.05
    assert decomp.metadata["decomposition_valid"] is True


def test_sfm_identification() -> None:
    identified = identify_fairness_effects(_sfm())
    assert identified["ctf_de"].status is IdentificationStatus.IDENTIFIED
    assert identified["ctf_ie"].status is IdentificationStatus.IDENTIFIED
    assert identified["ctf_se"].status is IdentificationStatus.IDENTIFIED


def test_sfm_partial_identification() -> None:
    sfm = _sfm(latent_ay=True)
    identified = identify_fairness_effects(sfm)
    assert identified["ctf_de"].status is not IdentificationStatus.IDENTIFIED
    bounds = fairness_bounds(sfm, _state(seed=1))
    lo, hi = bounds["ctf_de"]
    assert lo < hi


def test_fairness_audit_pipeline() -> None:
    state = _state(seed=2)
    result = CausalFairnessEngine.pure_step(
        state,
        {
            "method": "bounds",
            "graph": _graph(latent_ay=True),
            "protected_attribute": "A",
            "outcome_variable": "Y",
            "mediators": ["M"],
            "confounders": ["C"],
        },
    )
    assert "fairness_report" in result
    assert "decomposition" in result
    assert "bounds" in result
    assert "identification_status" in result["decomposition"]["metadata"]
