from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.proximal_mediation import (
    proximal_mediation_identify_v1,
)
from polisyos.ir.analytics.causal import proof_bundle_from_proximal_mediation_certificate
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
from polisyos.ir.analytics.proximal import ProximalMediationCertificate, ProxyAnnotation


def _directed(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def _bidirected(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)


def _graph(*, add_z_to_m: bool = False) -> CausalGraphModel:
    edges = [
        _directed("X", "A"),
        _directed("X", "M"),
        _directed("X", "Y"),
        _directed("Z", "A"),
        _directed("A", "M"),
        _directed("M", "Y"),
        _directed("A", "Y"),
        _bidirected("A", "Y"),
        _bidirected("A", "Z"),
        _bidirected("Y", "W"),
    ]
    if add_z_to_m:
        edges.append(_directed("Z", "M"))
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["A", "M", "Y", "X", "Z", "W"],
        edges=edges,
    )


def test_proximal_mediation_identify_v1_emits_certificate() -> None:
    result = proximal_mediation_identify_v1(
        _graph(),
        treatment="A",
        mediator="M",
        outcome="Y",
        proxies=ProxyAnnotation(
            treatment_inducing=("Z",),
            outcome_inducing=("W",),
            covariates=("X",),
        ),
        target_effect="nie",
    )

    assert isinstance(result, ProximalMediationCertificate)
    assert result.query.target_effect == "nie"
    assert all(check.status == "pass" for check in result.graph_checks)
    assert [item.name for item in result.bridge_equations] == [
        "outcome_bridge_h1",
        "nested_bridge_h0",
    ]
    bundle = proof_bundle_from_proximal_mediation_certificate(result)
    assert bundle.proof_status == "oracle_needed"
    assert bundle.theorem_family == "proximal_mediation_thm1_dukes_2023"
    assert bundle.metadata["proximal_mediation_certificate"]["query"]["mediator"] == "M"


def test_proximal_mediation_proof_bundle_promotes_when_oracle_is_accepted() -> None:
    result = proximal_mediation_identify_v1(
        _graph(),
        treatment="A",
        mediator="M",
        outcome="Y",
        proxies=ProxyAnnotation(
            treatment_inducing=("Z",),
            outcome_inducing=("W",),
            covariates=("X",),
        ),
        target_effect="psi",
    )

    assert isinstance(result, ProximalMediationCertificate)
    bundle = proof_bundle_from_proximal_mediation_certificate(
        result,
        oracle_assumptions_accepted=True,
    )
    assert bundle.proof_status == "identified"
    assert bundle.proof_stratum == "A1_extended"
    assert bundle.metadata["oracle_assumptions_accepted"] is True


def test_proximal_mediation_identify_v1_rejects_forbidden_direct_proxy_edge() -> None:
    result = proximal_mediation_identify_v1(
        _graph(add_z_to_m=True),
        treatment="A",
        mediator="M",
        outcome="Y",
        proxies=ProxyAnnotation(
            treatment_inducing=("Z",),
            outcome_inducing=("W",),
            covariates=("X",),
        ),
    )

    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type is BlockingType.PROXIMAL_CONDITION_FAILED
    assert result.quantitative_diagnostics["failed_check"] == "no_direct_edge_Z_to_M"
