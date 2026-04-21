from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.interference import (
    InteractionComplex,
    InterferenceCertificate,
    load_interaction_complex,
    load_interference_certificate,
    persist_interaction_complex,
    persist_interference_certificate,
)
from polisyos.ir.refs import ArtifactRefModel, InteractionComplexRef, InterferenceCertificateRef


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _artifact_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(ch),
        kind=kind,
        media_type="application/json",
    )


def _interaction_complex(
    *,
    reduction_policy: str = "cluster_projection",
) -> InteractionComplex:
    return InteractionComplex(
        nodes=("A__0", "Y__0", "A__1", "Y__1"),
        hyperedges=(("A__0", "Y__0"), ("A__1", "Y__1")),
        simplices=(),
        exposure_operator_ref=_artifact_ref("a", kind="ir.interference_exposure_operator"),
        reduction_policy=reduction_policy,
    )


def test_interaction_complex_rejects_duplicate_or_undeclared_nodes() -> None:
    with pytest.raises(ValidationError, match="nodes must be unique"):
        InteractionComplex(
            nodes=("A__0", "A__0"),
            hyperedges=(),
            simplices=(),
            exposure_operator_ref=_artifact_ref("a", kind="ir.interference_exposure_operator"),
            reduction_policy="pairwise_projection",
        )

    with pytest.raises(ValidationError, match="references undeclared nodes"):
        InteractionComplex(
            nodes=("A__0", "Y__0"),
            hyperedges=(("A__0", "Y__1"),),
            simplices=(),
            exposure_operator_ref=_artifact_ref("a", kind="ir.interference_exposure_operator"),
            reduction_policy="cluster_projection",
        )


def test_interference_certificate_rejects_blank_assumptions_and_nonfinite_bound() -> None:
    with pytest.raises(ValidationError, match="exposure_assumptions must be a list/tuple"):
        InterferenceCertificate(
            supported_query_family="pairwise_projection_queries",
            exposure_assumptions="not-a-sequence",
            reduction_error_bound=None,
            fallback_mode="pairwise",
        )

    with pytest.raises(ValidationError, match="reduction_error_bound must be finite"):
        InterferenceCertificate(
            supported_query_family="cluster_projection_queries",
            exposure_assumptions=("cluster_partition_used_as_topology_proxy",),
            reduction_error_bound=float("inf"),
            fallback_mode="clustered",
        )

    with pytest.raises(ValidationError, match="fallback_reason_codes must be non-empty"):
        InterferenceCertificate(
            supported_query_family="pairwise_projection_queries",
            reduction_error_bound=None,
            fallback_mode="pairwise",
            mode_requested="complex",
            mode_used="pairwise",
            fallback_triggered=True,
            fallback_reason_codes=(),
        )

    with pytest.raises(ValidationError, match="mode_requested must equal mode_used"):
        InterferenceCertificate(
            supported_query_family="simplicial_star_local_queries",
            reduction_error_bound=None,
            fallback_mode="unsupported",
            mode_requested="complex",
            mode_used="pairwise",
            fallback_triggered=False,
            fallback_reason_codes=(),
        )

    with pytest.raises(ValidationError, match="fallback_mode must be unsupported when mode_used is complex"):
        InterferenceCertificate(
            supported_query_family="simplicial_star_local_queries",
            reduction_error_bound=None,
            fallback_mode="pairwise",
            mode_requested="complex",
            mode_used="complex",
            fallback_triggered=False,
            fallback_reason_codes=(),
            estimability_checks={
                "topology_evidence": "pass",
                "simplicial_closure": "pass",
                "exposure_positivity": "pass",
                "higher_order_separability": "pass",
                "inference_regime": "pass",
                "pre_outcome_selection": "pass",
            },
        )


def test_phase_f_contracts_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    interaction_complex = _interaction_complex()
    certificate = InterferenceCertificate(
        supported_query_family="cluster_projection_queries",
        exposure_assumptions=(
            "exposure_mapping:fractional",
            "support_limited_to_pairwise_or_cluster_reduction",
        ),
        reduction_error_bound=None,
        fallback_mode="clustered",
        mode_requested="complex",
        mode_used="clustered",
        fallback_triggered=True,
        fallback_reason_codes=("higher_order_separability_failed",),
        estimability_checks={
            "topology_evidence": "pass",
            "simplicial_closure": "pass",
            "exposure_positivity": "pass",
            "higher_order_separability": "fail",
            "inference_regime": "pass",
            "pre_outcome_selection": "pass",
        },
    )

    interaction_complex_ref = persist_interaction_complex(store, interaction_complex)
    certificate_ref = persist_interference_certificate(store, certificate)

    assert isinstance(interaction_complex_ref, InteractionComplexRef)
    assert isinstance(certificate_ref, InterferenceCertificateRef)
    assert load_interaction_complex(store, interaction_complex_ref) == interaction_complex
    assert load_interference_certificate(store, certificate_ref) == certificate


def test_reduction_error_bound_none_is_honest_default() -> None:
    certificate = InterferenceCertificate(
        supported_query_family="pairwise_projection_queries",
        exposure_assumptions=("hypergraph_identification_not_claimed",),
        reduction_error_bound=None,
        fallback_mode="pairwise",
        mode_requested="complex",
        mode_used="pairwise",
        fallback_triggered=True,
        fallback_reason_codes=("higher_order_separability_failed",),
    )

    assert certificate.reduction_error_bound is None
    assert certificate.fallback_mode == "pairwise"
    assert certificate.mode_used == "pairwise"
