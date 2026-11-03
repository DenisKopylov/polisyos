"""CAL-06 scoped uncertainty report contract and persistence tests."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.foundry.calibration.execution_basis import read_calibration_report_source
from polisyos.foundry.calibration.report import (
    CalibrationCoordinateProjection,
    CalibrationOrderedBatchReport,
    CalibrationReport,
    CalibrationUncertainty,
    put_calibration_config,
    put_calibration_report,
    serialize_calibration_report_v1,
)
from polisyos.foundry.calibration.uncertainty_adapter import (
    envelope_from_calibration_param,
    envelopes_from_calibration,
)
from polisyos.foundry.uncertainty.covariance import extract_std
from polisyos.ir.analytics.calibration import CalibrationConfig
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
    UncertaintyEnvelope,
)

_FIELDS = ("A.rate", "B.rate")
_POINTS = {"A.rate": 0.25, "B.rate": 0.25, "C.rate": 0.7}


def _scoped_report(
    *,
    schema_version: str = "2.2",
    scope: tuple[str, ...] | None = _FIELDS,
    field_order: tuple[str, ...] = _FIELDS,
    coordinate_name: str = "shared_rate",
    calibrated_params: dict[str, float] | None = None,
    projection_status: str = "complete",
    include_projection: bool = True,
    include_uncertainties: bool = True,
    ordered_batch_execution: CalibrationOrderedBatchReport | None = None,
) -> CalibrationReport:
    """Build a deterministic report fixture with one tied optimizer coordinate."""
    projection = (
        CalibrationCoordinateProjection(
            field_order=field_order,
            coordinate_order=(coordinate_name,),
            matrix=tuple((1.0,) for _ in field_order),
        )
        if include_projection
        else None
    )
    uncertainties = (
        CalibrationUncertainty(
            params=[coordinate_name],
            covariance=[[0.0025]],
            correlation=[[1.0]],
            std=[0.05],
        )
        if include_uncertainties
        else None
    )
    return CalibrationReport(
        schema_version=schema_version,
        ordered_batch_execution=ordered_batch_execution,
        uncertainty_field_scope=scope,
        calibrated_params=_POINTS if calibrated_params is None else calibrated_params,
        total_loss=0.01,
        uncertainties=uncertainties,
        coordinate_projection=projection,
        coordinate_projection_status=projection_status,
    )


def _ordered_batch_report_scope() -> CalibrationOrderedBatchReport:
    return CalibrationOrderedBatchReport(
        consumed_profile_sha256="a" * 64,
        input_status="in_memory_input_only",
    )


def _legacy_full_report(schema_version: str) -> CalibrationReport:
    """Build an unscoped legacy report whose projection covers every point field."""
    ordered_scope = _ordered_batch_report_scope() if schema_version == "2.1" else None
    return CalibrationReport(
        schema_version=schema_version,
        ordered_batch_execution=ordered_scope,
        calibrated_params=_POINTS,
        total_loss=0.01,
        uncertainties=CalibrationUncertainty(
            params=["shared_rate", "C.rate"],
            covariance=[[0.0025, 0.0], [0.0, 0.01]],
            correlation=[[1.0, 0.0], [0.0, 1.0]],
            std=[0.05, 0.1],
        ),
        coordinate_projection=CalibrationCoordinateProjection(
            field_order=("A.rate", "B.rate", "C.rate"),
            coordinate_order=("shared_rate", "C.rate"),
            matrix=((1.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        ),
        coordinate_projection_status="complete",
    )


def test_scoped_report_preserves_tied_fields_and_leaves_c_point_only() -> None:
    report = _scoped_report()

    envelopes = envelopes_from_calibration(report)

    assert report.uncertainty_field_scope == _FIELDS
    assert report.calibrated_params == _POINTS
    assert report.coordinate_projection is not None
    assert report.coordinate_projection.field_order == _FIELDS
    assert set(envelopes) == set(_FIELDS)
    assert "C.rate" not in envelopes
    for name in _FIELDS:
        assert envelopes[name].metadata["covariance_params"] == list(_FIELDS)
        assert envelopes[name].metadata["covariance_row"] == pytest.approx(
            [0.0025, 0.0025], rel=0, abs=1e-9
        )
        assert envelopes[name].gate_eligible is False

    without_c = _scoped_report(calibrated_params={name: _POINTS[name] for name in _FIELDS})
    without_c_envelopes = envelopes_from_calibration(without_c)
    for name in _FIELDS:
        assert (
            without_c_envelopes[name].distribution_payload == envelopes[name].distribution_payload
        )
        assert (
            without_c_envelopes[name].metadata["covariance_row"]
            == envelopes[name].metadata["covariance_row"]
        )


def test_scoped_report_uses_projection_basis_not_coordinate_name() -> None:
    original = envelopes_from_calibration(_scoped_report(coordinate_name="shared_rate"))
    renamed = envelopes_from_calibration(_scoped_report(coordinate_name="renamed_tie"))

    for name in _FIELDS:
        assert original[name].metadata["covariance_row"] == renamed[name].metadata["covariance_row"]
        assert original[name].distribution_payload == renamed[name].distribution_payload


@pytest.mark.parametrize(
    "scope",
    [
        None,
        (),
        ("A.rate", "A.rate"),
        ("C.rate",),
        ("D.rate",),
        ("B.rate", "A.rate"),
    ],
)
def test_scoped_report_rejects_missing_duplicate_uncovered_or_reordered_scope(
    scope: tuple[str, ...] | None,
) -> None:
    with pytest.raises(ValueError):
        _scoped_report(scope=scope)


@pytest.mark.parametrize(
    ("include_projection", "include_uncertainties", "projection_status"),
    [
        (False, True, "not_established"),
        (True, False, "complete"),
        (True, True, "incomplete"),
        (True, True, "unsupported"),
    ],
)
def test_scoped_report_requires_uncertainty_and_complete_projection(
    include_projection: bool,
    include_uncertainties: bool,
    projection_status: str,
) -> None:
    with pytest.raises(ValueError):
        _scoped_report(
            include_projection=include_projection,
            include_uncertainties=include_uncertainties,
            projection_status=projection_status,
        )


def test_scoped_report_requires_exact_ordered_coordinate_basis() -> None:
    projection = CalibrationCoordinateProjection(
        field_order=_FIELDS,
        coordinate_order=("shared_rate",),
        matrix=((1.0,), (1.0,)),
    )

    with pytest.raises(ValueError):
        CalibrationReport(
            schema_version="2.2",
            uncertainty_field_scope=_FIELDS,
            calibrated_params=_POINTS,
            total_loss=0.01,
            uncertainties=CalibrationUncertainty(
                params=["renamed_tie"],
                covariance=[[0.0025]],
                correlation=[[1.0]],
                std=[0.05],
            ),
            coordinate_projection=projection,
            coordinate_projection_status="complete",
        )


def test_projection_rejects_duplicate_fields_bad_shape_and_nonfinite_matrix() -> None:
    with pytest.raises(ValueError):
        CalibrationCoordinateProjection(
            field_order=("A.rate", "A.rate"),
            coordinate_order=("shared_rate",),
            matrix=((1.0,), (1.0,)),
        )
    with pytest.raises(ValueError):
        CalibrationCoordinateProjection(
            field_order=_FIELDS,
            coordinate_order=("shared_rate",),
            matrix=((1.0,),),
        )
    with pytest.raises(ValueError):
        CalibrationCoordinateProjection(
            field_order=_FIELDS,
            coordinate_order=("shared_rate",),
            matrix=((float("nan"),), (1.0,)),
        )


def test_scoped_report_versions_require_scope_and_ordered_2_3_contract() -> None:
    scoped_ordered = _scoped_report(
        schema_version="2.3",
        ordered_batch_execution=_ordered_batch_report_scope(),
    )
    assert scoped_ordered.schema_version == "2.3"
    assert scoped_ordered.uncertainty_field_scope == _FIELDS

    with pytest.raises(ValueError):
        _scoped_report(scope=None)
    with pytest.raises(ValueError):
        _scoped_report(schema_version="2.3", ordered_batch_execution=None)
    with pytest.raises(ValueError):
        _scoped_report(
            schema_version="2.3",
            scope=None,
            ordered_batch_execution=_ordered_batch_report_scope(),
        )
    with pytest.raises(ValueError):
        _scoped_report(
            schema_version="2.1",
            scope=_FIELDS,
            ordered_batch_execution=_ordered_batch_report_scope(),
        )
    with pytest.raises(ValueError):
        _scoped_report(schema_version="2.0", scope=_FIELDS)
    with pytest.raises(ValueError):
        CalibrationReport(schema_version="9.9", total_loss=0.01)


def test_legacy_2_0_and_2_1_keep_all_point_coverage_without_scope() -> None:
    ordinary = _legacy_full_report("2.0")
    ordered = _legacy_full_report("2.1")

    assert ordinary.uncertainty_field_scope is None
    assert ordered.uncertainty_field_scope is None
    assert "uncertainty_field_scope" not in ordinary.model_dump(mode="json")
    assert "uncertainty_field_scope" not in ordered.model_dump(mode="json")
    assert ordinary.coordinate_projection is not None
    assert set(ordinary.coordinate_projection.field_order) == set(_POINTS)
    assert ordered.coordinate_projection is not None
    assert set(ordered.coordinate_projection.field_order) == set(_POINTS)

    with pytest.raises(ValueError):
        _scoped_report(schema_version="2.0", scope=None)


def test_scoped_report_persists_and_fresh_reader_retains_scope_and_config_edge(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    config_ref = put_calibration_config(
        store,
        CalibrationConfig(),
        return_selected_profile=True,
    )
    assert config_ref.manifest_profile_sha256 is not None
    report = _scoped_report()
    report = report.model_copy(update={"uncertainty_envelopes": envelopes_from_calibration(report)})
    report_ref = put_calibration_report(
        store,
        report,
        inputs=[input_ref_from_artifact_ref(config_ref, role="calibration_config")],
    )

    fresh_store = FileSystemCAS(tmp_path)
    source = read_calibration_report_source(fresh_store, ref=report_ref)

    assert source.status == "matched"
    fresh_report = source.require_value()
    assert fresh_report.schema_version == "2.2"
    assert fresh_report.uncertainty_field_scope == _FIELDS
    assert fresh_report.calibrated_params == _POINTS
    assert fresh_report.coordinate_projection is not None
    assert fresh_report.coordinate_projection.field_order == _FIELDS
    assert fresh_report.uncertainties is not None
    assert fresh_report.uncertainties.params == ["shared_rate"]
    assert set(fresh_report.uncertainty_envelopes or {}) == set(_FIELDS)
    for envelope in (fresh_report.uncertainty_envelopes or {}).values():
        assert isinstance(envelope.distribution_payload, ParametricFitCarrier)
        assert extract_std(envelope) == pytest.approx(0.05, rel=0, abs=1e-12)
        assert envelope.gate_eligible is False

    manifest = fresh_store.get_manifest(report_ref)
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.version == "2.2"
    config_edges = [edge for edge in manifest.inputs if edge.role == "calibration_config"]
    assert len(config_edges) == 1
    assert config_edges[0].artifact_id == config_ref.artifact_id
    assert config_edges[0].manifest_profile_sha256 == config_ref.manifest_profile_sha256
    assert not any(edge.role == "calibration_execution_input_basis" for edge in manifest.inputs)


@pytest.mark.parametrize("display_level", [0.8, 0.95])
def test_scoped_typed_normal_json_keeps_sigma_separate_from_display_level(
    display_level: float,
) -> None:
    envelope = envelope_from_calibration_param(
        _scoped_report(),
        "A.rate",
        confidence_level=display_level,
    )

    assert envelope is not None
    assert isinstance(envelope.distribution_payload, ParametricFitCarrier)
    assert envelope.distribution_payload.family is DistributionFamily.NORMAL
    assert envelope.distribution_payload.parameters == {"mean": 0.25, "std": 0.05}
    assert envelope.confidence_level is None
    assert envelope.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
    assert envelope.is_heuristic_ci is True
    assert envelope.gate_eligible is False

    restored = UncertaintyEnvelope.model_validate_json(envelope.model_dump_json())
    assert extract_std(restored) == pytest.approx(0.05, rel=0, abs=1e-12)
    assert restored.metadata["requested_confidence_level"] == display_level
    tampered = restored.model_copy(update={"metadata": {**restored.metadata, "std": 9.0}})
    assert extract_std(tampered) == pytest.approx(0.05, rel=0, abs=1e-12)


def test_scoped_display_levels_change_width_without_changing_typed_sigma() -> None:
    report = _scoped_report()
    narrow = envelope_from_calibration_param(report, "A.rate", confidence_level=0.8)
    wide = envelope_from_calibration_param(report, "A.rate", confidence_level=0.95)

    assert narrow is not None
    assert wide is not None
    assert wide.ci_width > narrow.ci_width
    assert extract_std(narrow) == pytest.approx(0.05, rel=0, abs=1e-12)
    assert extract_std(wide) == pytest.approx(0.05, rel=0, abs=1e-12)


def test_v1_wire_projection_omits_new_scope_field_and_keeps_historical_bytes() -> None:
    report = CalibrationReport(
        schema_version="2.0",
        calibrated_params={"A.rate": 0.25},
        total_loss=0.01,
        coordinate_projection=CalibrationCoordinateProjection(
            field_order=("A.rate",),
            coordinate_order=("A.rate",),
            matrix=((1.0,),),
        ),
    )
    legacy_projection = report.model_copy(
        update={
            "schema_version": "1.0",
            "uncertainty_field_scope": ("A.rate",),
        }
    )
    historical_payload = {
        "schema_version": "1.0",
        "calibrated_params": {"A.rate": 0.25},
        "total_loss": 0.01,
        "per_target_loss": {},
        "target_weights": {},
        "loss_history": [],
        "grad_norm_history": [],
        "series_comparison": {},
        "fit_quality": None,
        "uncertainties": None,
        "identifiability": None,
        "uncertainty_envelopes": None,
        "uncertainty_envelope_refs": None,
        "diagnostics": [],
        "execution_context": {},
    }

    serialized = serialize_calibration_report_v1(legacy_projection)

    assert serialized == to_canonical_bytes(
        historical_payload,
        CanonSpec(forbid_floats=False),
    )
    assert b"uncertainty_field_scope" not in serialized
