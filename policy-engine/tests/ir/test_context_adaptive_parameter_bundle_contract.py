from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.literature import EvidenceParameter
from polisyos.ir.analytics.parameters import (
    ContextAdaptiveParameterBundle,
    ParameterApplicability,
    load_context_adaptive_parameter_bundle,
    persist_context_adaptive_parameter_bundle,
)
from polisyos.ir.analytics.transportability import TransportMode, TransportabilityStatus
from polisyos.ir.refs import ContextAdaptiveParameterBundleRef


def test_context_adaptive_parameter_bundle_artifact_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    target_context = ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        publication_year=2022,
    )
    parameter = EvidenceParameter(name="fiscal_multiplier", value=1.2)
    applicability = ParameterApplicability(
        parameter_id="fiscal_multiplier",
        target_context_id="UA",
        transport_status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.TRANSPORT_FORMULA,
        transport_confidence=0.6,
        context_distance=0.4,
        is_applicable=True,
        adjustment_required=True,
        uncertainty_multiplier=1.8,
        recommended_value=1.2,
    )
    bundle = ContextAdaptiveParameterBundle(
        target_context=target_context,
        simulation_domain="fiscal",
        parameters={"fiscal_multiplier": parameter},
        applicability={"fiscal_multiplier": applicability},
        unsupported_parameters=["tax_elasticity"],
        skg_snapshot_ref="duckdb://mock#v1",
        skg_version_id=1,
        selection_timestamp="2026-03-02T12:00:00+00:00",
    )

    ref = persist_context_adaptive_parameter_bundle(store, bundle)
    loaded = load_context_adaptive_parameter_bundle(store, ref)

    assert isinstance(ref, ContextAdaptiveParameterBundleRef)
    assert ref.kind == "ir.context_adaptive_parameter_bundle"
    assert loaded == bundle
