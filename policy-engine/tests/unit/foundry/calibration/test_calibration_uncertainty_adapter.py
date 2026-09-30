from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.foundry.calibration.report import (
    CalibrationCoordinateProjection,
    CalibrationReport,
    CalibrationUncertainty,
    put_calibration_report,
    serialize_calibration_report_v1,
)
from polisyos.foundry.calibration.uncertainty_adapter import (
    envelope_from_calibration_param,
    envelopes_from_calibration,
    summarize_bayesian_calibration_posterior,
)
from polisyos.ir.analytics.uncertainty import IntervalSemantics, UncertaintySource


def test_envelope_from_calibration_param() -> None:
    report = CalibrationReport(
        schema_version="1.0",
        calibrated_params={"node.tax_rate": 0.25},
        total_loss=0.01,
        uncertainties=CalibrationUncertainty(
            method="laplace",
            params=["node.tax_rate"],
            std=[0.05],
            covariance=[[0.0025]],
            correlation=[[1.0]],
        ),
    )
    env = envelope_from_calibration_param(report, "node.tax_rate")
    assert env is not None
    assert env.point_estimate == 0.25
    assert env.ci_lower < env.point_estimate < env.ci_upper
    assert env.source == UncertaintySource.CALIBRATION
    assert env.interval_semantics == IntervalSemantics.HEURISTIC_RANGE
    assert env.is_heuristic_ci is True
    assert env.gate_eligible is False
    assert env.confidence_level is None
    assert env.metadata["requested_confidence_level"] == 0.95


def test_envelope_from_calibration_param_none_when_uncertainty_missing() -> None:
    report = CalibrationReport(
        calibrated_params={"node.tax_rate": 0.25},
        total_loss=0.01,
        uncertainties=None,
    )
    assert envelope_from_calibration_param(report, "node.tax_rate") is None


def test_envelopes_from_calibration_filters_missing_std() -> None:
    report = CalibrationReport(
        schema_version="1.0",
        calibrated_params={"node.tax_rate": 0.25, "node.vat_rate": 0.2},
        total_loss=0.01,
        uncertainties=CalibrationUncertainty(
            method="laplace",
            params=["node.tax_rate"],
            std=[0.05],
            covariance=[[0.0025]],
            correlation=[[1.0]],
        ),
    )
    envelopes = envelopes_from_calibration(report)
    assert set(envelopes.keys()) == {"node.tax_rate"}


def test_envelopes_from_calibration_projects_tied_group_covariance() -> None:
    report = CalibrationReport(
        schema_version="2.0",
        calibrated_params={"A.rate": 0.25, "B.rate": 0.25},
        total_loss=0.01,
        uncertainties=CalibrationUncertainty(
            params=["shared_rate"],
            covariance=[[0.0025]],
            correlation=[[1.0]],
            std=[0.05],
        ),
        coordinate_projection=CalibrationCoordinateProjection(
            field_order=("A.rate", "B.rate"),
            coordinate_order=("shared_rate",),
            matrix=((1.0,), (1.0,)),
        ),
    )

    envelopes = envelopes_from_calibration(report)

    assert set(envelopes) == {"A.rate", "B.rate"}
    for name in ("A.rate", "B.rate"):
        assert envelopes[name].metadata["std"] == 0.05
        assert envelopes[name].metadata["covariance_params"] == ["A.rate", "B.rate"]
        assert envelopes[name].metadata["covariance_row"] == pytest.approx(
            [0.0025, 0.0025], rel=0, abs=1e-9
        )
        assert envelopes[name].gate_eligible is False


def test_v2_report_without_projection_does_not_use_v1_name_identity() -> None:
    report = CalibrationReport(
        schema_version="2.0",
        calibrated_params={"node.rate": 0.25},
        total_loss=0.01,
        uncertainties=CalibrationUncertainty(
            params=["node.rate"],
            std=[0.05],
            covariance=[[0.0025]],
            correlation=[[1.0]],
        ),
    )

    assert envelope_from_calibration_param(report, "node.rate") is None


def test_v2_projection_must_cover_every_reported_calibrated_field() -> None:
    with pytest.raises(ValueError, match="cover every calibrated parameter field"):
        CalibrationReport(
            schema_version="2.0",
            calibrated_params={"A.rate": 0.25, "B.rate": 0.25},
            total_loss=0.01,
            uncertainties=CalibrationUncertainty(
                params=["shared_rate"],
                covariance=[[0.0025]],
                correlation=[[1.0]],
                std=[0.05],
            ),
            coordinate_projection=CalibrationCoordinateProjection(
                field_order=("A.rate",),
                coordinate_order=("shared_rate",),
                matrix=((1.0,),),
            ),
        )


def test_v2_incomplete_projection_status_withholds_name_keyed_envelope() -> None:
    report = CalibrationReport(
        schema_version="2.0",
        calibrated_params={"node.rate": 0.25},
        total_loss=0.01,
        uncertainties=CalibrationUncertainty(
            params=["node.rate"],
            std=[0.05],
            covariance=[[0.0025]],
            correlation=[[1.0]],
        ),
        coordinate_projection_status="incomplete",
    )

    assert envelope_from_calibration_param(report, "node.rate") is None


def test_tied_projection_is_invariant_to_coordinate_name() -> None:
    def projected(coordinate_name: str) -> dict[str, object]:
        report = CalibrationReport(
            schema_version="2.0",
            calibrated_params={"A.rate": 0.25, "B.rate": 0.25},
            total_loss=0.01,
            uncertainties=CalibrationUncertainty(
                params=[coordinate_name],
                covariance=[[0.0025]],
                correlation=[[1.0]],
                std=[0.05],
            ),
            coordinate_projection=CalibrationCoordinateProjection(
                field_order=("A.rate", "B.rate"),
                coordinate_order=(coordinate_name,),
                matrix=((1.0,), (1.0,)),
            ),
        )
        return envelopes_from_calibration(report)

    first = projected("shared_rate")
    renamed = projected("renamed_tie")
    assert first["A.rate"].metadata["covariance_row"] == renamed["A.rate"].metadata[
        "covariance_row"
    ]
    assert first["B.rate"].metadata["std"] == renamed["B.rate"].metadata["std"]


def test_historical_v1_serializer_preserves_pre_projection_wire_shape(tmp_path) -> None:
    report = CalibrationReport(
        schema_version="2.0",
        calibrated_params={"node.rate": 0.25},
        total_loss=0.01,
        coordinate_projection=CalibrationCoordinateProjection(
            field_order=("node.rate",),
            coordinate_order=("node.rate",),
            matrix=((1.0,),),
        ),
    )
    legacy_payload = {
        "schema_version": "1.0",
        "calibrated_params": {"node.rate": 0.25},
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

    assert serialize_calibration_report_v1(report) == to_canonical_bytes(
        legacy_payload,
        CanonSpec(forbid_floats=False),
    )
    store = FileSystemCAS(tmp_path)
    historical_report = report.model_copy(update={"schema_version": "1.0"})
    ref = put_calibration_report(store, historical_report)
    historical_bytes = store.get_bytes(ref.artifact_id)
    assert historical_bytes == serialize_calibration_report_v1(historical_report)
    replayed = CalibrationReport.model_validate(from_canonical_bytes(historical_bytes))
    assert replayed.schema_version == "1.0"
    assert replayed.coordinate_projection is None


def test_summarize_bayesian_calibration_posterior_supports_emulator_diagnostics() -> None:
    summary = summarize_bayesian_calibration_posterior(
        {
            "node.tax_rate": [0.21, 0.24, 0.25, 0.23, 0.22],
            "node.transfer": [1.1, 1.0, 1.2, 1.05, 0.98],
        },
        credible_mass=0.9,
        emulator_diagnostics={
            "emulator_name": "gp_surrogate",
            "emulator_noise_std": {"node.tax_rate": 0.01},
        },
        posterior_diagnostics={"r_hat_max": 1.01},
    )

    assert summary.posterior_means["node.tax_rate"] > 0.0
    assert (
        summary.parameter_envelopes["node.tax_rate"].interval_semantics
        == IntervalSemantics.CREDIBLE_INTERVAL
    )
    assert summary.parameter_envelopes["node.tax_rate"].source == UncertaintySource.CALIBRATION
    assert summary.diagnostics["calibration_mode"] == "bayesian_emulator"
    assert summary.uncertainty_decomposition["node.tax_rate"]["aleatoric"] is not None
