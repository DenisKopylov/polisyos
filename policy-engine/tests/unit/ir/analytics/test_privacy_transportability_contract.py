from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.privacy_transportability import (
    DistortionToleranceMap,
    DPGraphSourceKind,
    DPMechanismScope,
    DPUtilityManifest,
    PrivacyAwareTransportCertificate,
    PrivacyObservedMode,
    PrivateFactorBound,
    PrivateFactorMetric,
    ValidityPredicate,
    ValidityPredicateKind,
    apply_privacy_transportability_gate,
    attach_privacy_transportability_to_result,
    build_privacy_aware_transport_certificate,
    coerce_dp_utility_manifest,
    coerce_privacy_aware_transport_certificate,
    combine_private_factor_envelopes,
    load_privacy_aware_transport_certificate,
    persist_privacy_aware_transport_certificate,
)
from polisyos.ir.analytics.transportability import (
    SNode,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
)
from polisyos.ir.registry.refs import PrivacyAwareTransportCertificateRef


def _certificate(
    *,
    mode: PrivacyObservedMode = PrivacyObservedMode.INTERVAL,
) -> PrivacyAwareTransportCertificate:
    return PrivacyAwareTransportCertificate(
        certificate_id="privacy_transport_cert_demo",
        query="P*(Y|do(X))",
        selection_diagram_ref="sha256:selection-diagram",
        latent_transport_status=TransportabilityStatus.IDENTIFIED,
        privacy_observed_mode=mode,
        transport_formula_ref="sha256:transport-formula",
        source_domains=("source_a",),
        target_domain="target_t",
        dp_scope=(
            DPMechanismScope(
                domain_id="source_a",
                mechanism_id="laplace_source",
                mechanism_family="laplace",
                privacy_model="central",
                epsilon=2.0,
                delta=0.0,
                protected_variables=("Z",),
                released_statistics=("P_s(Y|do(X),Z)",),
                clipping={"Y": 1.0},
                public_channel_spec={"query_class": "laplace_histogram_v1"},
            ),
            DPMechanismScope(
                domain_id="target_t",
                mechanism_id="gaussian_target",
                mechanism_family="gaussian",
                privacy_model="central",
                epsilon=3.0,
                delta=1e-6,
                protected_variables=("Z",),
                released_statistics=("P_t(Z)",),
                public_channel_spec={"query_class": "gaussian_histogram_v1"},
            ),
        ),
        private_factor_bounds=(
            PrivateFactorBound(
                factor_id="source_kernel",
                factor_expression="P_s(Y|do(X),Z)",
                domain_id="source_a",
                metric=PrivateFactorMetric.LINF,
                error_bound=0.02,
                confidence_level=0.95,
                estimator_kind="debias_laplace_histogram",
                debiasing_required=True,
            ),
            PrivateFactorBound(
                factor_id="target_marginal",
                factor_expression="P_t(Z)",
                domain_id="target_t",
                metric=PrivateFactorMetric.TV,
                error_bound=0.01,
                confidence_level=0.95,
                support_floor=0.10,
                estimator_kind="gaussian_interval",
            ),
        ),
        validity_predicates=(
            ValidityPredicate(
                predicate_id="formula_error",
                predicate_kind=ValidityPredicateKind.FORMULA_ERROR,
                expression="eta_source + eta_target <= 0.05",
                margin=0.05,
                sensitivity_by_factor={
                    "source_kernel": 1.0,
                    "target_marginal": 1.0,
                },
            ),
        ),
        distortion_tolerance_map=DistortionToleranceMap(
            query_id="transport_demo",
            latent_formula_ref="sha256:transport-formula",
            factor_ids=("source_kernel", "target_marginal"),
            factor_metrics={
                "source_kernel": PrivateFactorMetric.LINF,
                "target_marginal": PrivateFactorMetric.TV,
            },
            factor_error_bounds={
                "source_kernel": 0.03,
                "target_marginal": 0.02,
            },
            support_floors={"P_t(Z=z)": 0.10},
            predicate_margins={"formula_error": 0.05},
            sensitivity_matrix={
                "formula_error": {
                    "source_kernel": 1.0,
                    "target_marginal": 1.0,
                }
            },
            utility_maps={
                "source_a": {"mechanism_to_error_contract": "laplace_histogram_v1"},
                "target_t": {"mechanism_to_error_contract": "gaussian_histogram_v1"},
            },
            feasible_region={"description": "L eta <= gamma and support constraints hold"},
            epsilon_projection={
                "source_a": {"epsilon_min": 1.0},
                "target_t": {"epsilon_min": 1.5},
            },
        ),
        blocking_reasons=("privacy_distortion_exceeds_margin",)
        if mode is PrivacyObservedMode.BLOCKED
        else (),
        assumptions=("public_channel_spec_available",),
        provenance={"stage": "15.3"},
    )


def _manifest() -> DPUtilityManifest:
    certificate = _certificate()
    return DPUtilityManifest(
        manifest_id="utility_manifest_demo",
        query_id="transport_demo",
        source_domains=certificate.source_domains,
        target_domain=certificate.target_domain,
        dp_scope=certificate.dp_scope,
        private_factor_bounds=certificate.private_factor_bounds,
        validity_predicates=certificate.validity_predicates,
        distortion_tolerance_map=certificate.distortion_tolerance_map,
        privacy_mismatch_variables=("Z",),
        graph_source_kind=DPGraphSourceKind.FIXED_EX_ANTE,
        graph_uncertainty_accounted=True,
        fallback_queries=(
            {
                "query": "P_t(Z)",
                "mode": "descriptive_interval",
            },
        ),
    )


def test_privacy_transport_certificate_round_trip_and_attachment(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    certificate = _certificate(mode=PrivacyObservedMode.INTERVAL)

    ref = persist_privacy_aware_transport_certificate(store, certificate)
    loaded = load_privacy_aware_transport_certificate(store, ref)
    attached = attach_privacy_transportability_to_result(
        TransportabilityResult(
            status=TransportabilityStatus.IDENTIFIED,
        ),
        ref,
        loaded,
    )

    assert isinstance(ref, PrivacyAwareTransportCertificateRef)
    assert ref.kind == "ir.privacy_aware_transport_certificate"
    assert loaded == certificate
    assert attached.metadata["privacy_observed_mode"] == "interval"
    assert attached.metadata["privacy_latent_transport_status"] == "identified"
    assert attached.metadata["privacy_certificate_ref"]["kind"] == (
        "ir.privacy_aware_transport_certificate"
    )
    assert attached.metadata["privacy_factor_bounds"][0]["factor_id"] == "source_kernel"
    assert attached.metadata["privacy_dp_scope"][1]["domain_id"] == "target_t"


def test_blocked_privacy_transport_certificate_requires_reasons() -> None:
    with pytest.raises(ValueError, match="blocking_reasons"):
        PrivacyAwareTransportCertificate.model_validate(
            {
                **_certificate(mode=PrivacyObservedMode.BLOCKED).model_dump(mode="json"),
                "blocking_reasons": [],
            }
        )


def test_coerce_privacy_transport_certificate_from_nested_dict() -> None:
    certificate = _certificate(mode=PrivacyObservedMode.EXACT)
    payload = {"privacy_transport_certificate": certificate.model_dump(mode="json")}

    coerced = coerce_privacy_aware_transport_certificate(payload)

    assert coerced == certificate


def test_build_privacy_transport_certificate_and_apply_gate() -> None:
    manifest = _manifest()
    certificate = build_privacy_aware_transport_certificate(
        utility_manifest=manifest,
        latent_transport_status=TransportabilityStatus.IDENTIFIED,
        query="P*(Y|do(X))",
        selection_diagram_ref="selection_diagram:demo",
    )
    gated = apply_privacy_transportability_gate(
        TransportabilityResult(status=TransportabilityStatus.IDENTIFIED),
        certificate,
    )

    assert certificate.privacy_observed_mode is PrivacyObservedMode.EXACT
    assert gated.status is TransportabilityStatus.IDENTIFIED


def test_apply_privacy_transportability_gate_marks_interval_results_as_partial() -> None:
    gated = apply_privacy_transportability_gate(
        TransportabilityResult(status=TransportabilityStatus.IDENTIFIED),
        _certificate(mode=PrivacyObservedMode.INTERVAL),
    )

    assert gated.status is TransportabilityStatus.PARTIALLY_IDENTIFIED
    assert gated.identified_region == {
        "privacy_observed_mode": "interval",
        "privacy_interval_only": True,
    }


def test_build_privacy_transport_certificate_blocks_private_graph_without_accounting() -> None:
    manifest = _manifest().model_copy(
        update={
            "graph_source_kind": DPGraphSourceKind.INFERRED_PRIVATE,
            "graph_uncertainty_accounted": False,
        }
    )

    certificate = build_privacy_aware_transport_certificate(
        utility_manifest=manifest,
        latent_transport_status=TransportabilityStatus.IDENTIFIED,
        query="P*(Y|do(X))",
        selection_diagram_ref="selection_diagram:demo",
    )

    assert certificate.privacy_observed_mode is PrivacyObservedMode.BLOCKED
    assert "graph_private_unaccounted" in certificate.blocking_reasons


def test_build_privacy_transport_certificate_blocks_without_public_channel_spec() -> None:
    original_manifest = _manifest()
    manifest = original_manifest.model_copy(
        update={
            "dp_scope": tuple(
                scope.model_copy(update={"public_channel_spec": {}})
                for scope in original_manifest.dp_scope
            )
        }
    )

    certificate = build_privacy_aware_transport_certificate(
        utility_manifest=manifest,
        latent_transport_status=TransportabilityStatus.IDENTIFIED,
        query="P*(Y|do(X))",
        selection_diagram_ref="selection_diagram:demo",
    )

    assert certificate.privacy_observed_mode is PrivacyObservedMode.BLOCKED
    assert "missing_public_channel_spec:source_a" in certificate.blocking_reasons
    assert "missing_public_channel_spec:target_t" in certificate.blocking_reasons


def test_coerce_dp_utility_manifest_and_combine_envelopes() -> None:
    manifest = _manifest()
    payload = {"dp_utility_manifest": manifest.model_dump(mode="json")}

    coerced = coerce_dp_utility_manifest(payload)
    envelope = combine_private_factor_envelopes(manifest.private_factor_bounds)

    assert coerced == manifest
    assert envelope is not None
    assert envelope.confidence_interval == (-0.03, 0.03)


def test_snode_origin_privacy_is_supported() -> None:
    s_node = SNode(
        target_variable="Z",
        context_dimension="dp_release_scope",
        source_value="released",
        target_value="suppressed",
        delta=1.0,
        severity="high",
        origin=SNodeOrigin.PRIVACY,
    )

    assert s_node.origin is SNodeOrigin.PRIVACY
