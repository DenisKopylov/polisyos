from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.ir.analytics.welfare import (
    GEUncertaintyBundle,
    GEUncertaintyRepresentation,
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareStatus,
    load_welfare_bundle,
    persist_ge_uncertainty_bundle,
    persist_welfare_bundle,
)
from polisyos.ir.registry.refs import ArtifactRefModel
from pydantic import ValidationError


def test_welfare_bundle_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    matrix_ref = store.put_json(
        {"matrix": [[1.05]]},
        PutOptions(kind="ir.welfare_multiplier_matrix", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ge_ref = persist_ge_uncertainty_bundle(
        store,
        GEUncertaintyBundle(
            model_class="linearized_ge_io",
            representation=GEUncertaintyRepresentation.MULTIPLIER_INTERVALS,
            multiplier_shape=(1, 1),
            point_multiplier_ref=ArtifactRefModel.model_validate(matrix_ref.model_dump()),
            lower_multiplier_ref=ArtifactRefModel.model_validate(matrix_ref.model_dump()),
            upper_multiplier_ref=ArtifactRefModel.model_validate(matrix_ref.model_dump()),
        ),
    )
    pe_ref = persist_uncertainty_envelope(
        store,
        UncertaintyEnvelope(
            point_estimate=1.0,
            confidence_interval=(0.8, 1.2),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        ),
    )
    bundle_ref = persist_welfare_bundle(
        store,
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            ge_model_ref=ArtifactRefModel.model_validate(matrix_ref.model_dump()),
            pe_uncertainty_refs={"policy_value": pe_ref},
            ge_uncertainty_ref=ge_ref,
            point_estimate=0.84,
            credible_interval=(0.51, 1.12),
            robust_interval=(0.12, 1.43),
            interval_semantics=WelfareIntervalSemantics.MIXED_NESTED,
            channel_decomposition={"pe": 0.57, "ge": 0.27},
            method_used=WelfareMethod.MIXED_NESTED,
            status=WelfareStatus.OK,
        ),
    )

    bundle = load_welfare_bundle(store, bundle_ref)
    assert bundle.point_estimate == 0.84
    assert bundle.robust_interval == (0.12, 1.43)
    assert bundle.ge_uncertainty_ref == ge_ref
    assert bundle.pe_uncertainty_refs["policy_value"] == pe_ref


def test_welfare_bundle_rejects_malformed_interval() -> None:
    with pytest.raises(ValidationError):
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            point_estimate=1.0,
            credible_interval=(2.0, 1.0),
            interval_semantics=WelfareIntervalSemantics.CREDIBLE,
            method_used=WelfareMethod.MONTE_CARLO,
            status=WelfareStatus.OK,
        )


def test_welfare_bundle_requires_warning_for_partial_status() -> None:
    with pytest.raises(ValidationError):
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            point_estimate=1.0,
            interval_semantics=WelfareIntervalSemantics.NONE,
            method_used=WelfareMethod.DETERMINISTIC,
            status=WelfareStatus.PARTIAL,
        )
