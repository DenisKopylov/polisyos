from __future__ import annotations

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
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
    BayesianCalibrationEnvelopeLimitation,
    _load_bayesian_calibration_summary_candidate,
    _persist_bayesian_calibration_summary_candidate,
    consume_persisted_bayesian_calibration_candidate,
    envelope_from_calibration_param,
    envelopes_from_calibration,
    summarize_bayesian_calibration_posterior,
)
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    NumericPolicySpec,
    NumericToleranceMode,
    PosteriorSamplesCarrier,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)


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
    assert (
        first["A.rate"].metadata["covariance_row"] == renamed["A.rate"].metadata["covariance_row"]
    )
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


def test_legacy_posterior_summary_preserves_unrepresentable_mean_and_draw_context() -> None:
    draws = (0.0,) * 99 + (100.0,)

    summary = summarize_bayesian_calibration_posterior({"theta": draws}, credible_mass=0.9)

    assert summary.posterior_means["theta"] == 1.0
    assert summary.credible_intervals["theta"] == (0.0, 0.0)
    assert "theta" not in summary.parameter_envelopes
    assert summary.parameter_envelope_limitations == {"theta": "point_outside_credible_interval"}
    assert summary.diagnostics["parameter_envelope_limitations"] == {
        "theta": "point_outside_credible_interval"
    }
    assert summary.posterior_draw_context is not None
    assert summary.posterior_draw_context.samples_by_parameter["theta"].samples == draws
    assert summary.posterior_draw_context.input_shapes == {"theta": (100,)}
    assert summary.posterior_draw_context.row_matrix == tuple((draw,) for draw in draws)
    assert summary.posterior_draw_context.row_relation_status == "not_established"
    assert summary.posterior_draw_context.source_binding_status == "caller_input_only"


def test_off_interval_summary_candidate_roundtrips_fresh_cas_and_recomputes_limitation(
    tmp_path,
) -> None:
    draws = (0.0,) * 99 + (100.0,)
    store = FileSystemCAS(tmp_path)
    summary = summarize_bayesian_calibration_posterior(
        {"theta": draws}, credible_mass=0.9, candidate_store=store
    )

    ref = summary.persisted_candidate_ref
    assert ref is not None
    fresh = _load_bayesian_calibration_summary_candidate(FileSystemCAS(tmp_path), ref)

    assert fresh.posterior_means == {"theta": 1.0}
    assert fresh.credible_intervals == {"theta": (0.0, 0.0)}
    assert fresh.parameter_envelopes == {}
    assert fresh.parameter_envelope_limitations == {"theta": "point_outside_credible_interval"}
    assert (
        fresh.parameter_envelope_limitations["theta"]
        is BayesianCalibrationEnvelopeLimitation.POINT_OUTSIDE_CREDIBLE_INTERVAL
    )
    assert fresh.point_role == "posterior_mean"
    assert fresh.interval_method == "numpy_quantile_linear"
    assert fresh.posterior_draw_context is not None
    assert fresh.posterior_draw_context.samples_by_parameter["theta"].samples == draws
    assert fresh.posterior_draw_context.input_shapes == {"theta": (100,)}
    assert fresh.posterior_draw_context.row_relation_status == "not_established"
    assert fresh.posterior_draw_context.source_binding_status == "caller_input_only"
    assert fresh.unit_binding_status == "not_established"
    assert fresh.gate_eligible is False
    calls: list[float] = []

    result = consume_persisted_bayesian_calibration_candidate(
        FileSystemCAS(tmp_path),
        ref,
        simulation_fn=lambda **params: calls.append(float(params["theta"])) or {"theta": 1.0},
        nominal_params={},
        output_metric_ids=["theta"],
    )

    assert result.status == "limited"
    assert result.refusal_reason == "parameter_envelope_unavailable"
    assert result.results == ()
    assert result.candidate.posterior_means == {"theta": 1.0}
    assert result.candidate.credible_intervals == {"theta": (0.0, 0.0)}
    assert calls == []


def test_candidate_store_fresh_reader_reaches_actual_univariate_mc_consumer(tmp_path) -> None:
    draws = (0.1, 0.2, 0.3)
    calls: list[float] = []
    store = FileSystemCAS(tmp_path)
    summary = summarize_bayesian_calibration_posterior({"theta": draws}, candidate_store=store)

    assert summary.persisted_candidate_ref is not None
    assert summary.parameter_envelopes["theta"].point_estimate == summary.posterior_means["theta"]
    result = consume_persisted_bayesian_calibration_candidate(
        FileSystemCAS(tmp_path),
        summary.persisted_candidate_ref,
        simulation_fn=lambda **params: calls.append(float(params["theta"]))
        or {"theta": params["theta"]},
        nominal_params={},
        output_metric_ids=["theta"],
    )

    assert result.status == "evaluated"
    assert result.refusal_reason is None
    assert len(result.results) == 1
    assert result.results[0].envelope.gate_eligible is False
    assert calls
    assert set(calls).issubset(set(draws))


def test_off_interval_candidate_reader_rejects_a_stale_point_functional(tmp_path) -> None:
    summary = summarize_bayesian_calibration_posterior(
        {"theta": (0.0,) * 99 + (100.0,)}, credible_mass=0.9
    )
    summary.posterior_means["theta"] = 2.0
    ref = _persist_bayesian_calibration_summary_candidate(FileSystemCAS(tmp_path), summary)

    with pytest.raises(ValueError, match="does not match its retained draw context"):
        _load_bayesian_calibration_summary_candidate(FileSystemCAS(tmp_path), ref)


def test_candidate_keeps_reversed_caller_rows_distinct_without_joint_admission(
    tmp_path,
) -> None:
    x = (-1.0, 1.0, -1.0, 1.0)
    y = (-1.0, 1.0, -1.0, 1.0)
    store = FileSystemCAS(tmp_path)
    same = summarize_bayesian_calibration_posterior(
        {"x": x, "y": y}, credible_mass=0.9, candidate_store=store
    )
    reversed_pairing = summarize_bayesian_calibration_posterior(
        {"x": x, "y": tuple(reversed(y))}, credible_mass=0.9, candidate_store=store
    )

    same_ref = same.persisted_candidate_ref
    reversed_ref = reversed_pairing.persisted_candidate_ref
    assert same_ref is not None
    assert reversed_ref is not None
    same_fresh = _load_bayesian_calibration_summary_candidate(FileSystemCAS(tmp_path), same_ref)
    reversed_fresh = _load_bayesian_calibration_summary_candidate(
        FileSystemCAS(tmp_path), reversed_ref
    )

    assert same.posterior_means == reversed_pairing.posterior_means
    assert same.credible_intervals == reversed_pairing.credible_intervals
    assert str(same_ref.artifact_id) != str(reversed_ref.artifact_id)
    assert same_fresh.posterior_draw_context.row_matrix != (
        reversed_fresh.posterior_draw_context.row_matrix
    )
    assert same_fresh.posterior_draw_context.row_relation_status == "not_established"
    assert reversed_fresh.posterior_draw_context.row_relation_status == "not_established"
    assert same_fresh.gate_eligible is False
    assert reversed_fresh.gate_eligible is False
    calls: list[dict[str, float]] = []

    def evaluate(**params: float) -> dict[str, float]:
        calls.append(params)
        return {"product": params["x"] * params["y"]}

    for ref in (same_ref, reversed_ref):
        result = consume_persisted_bayesian_calibration_candidate(
            FileSystemCAS(tmp_path),
            ref,
            simulation_fn=evaluate,
            nominal_params={},
            output_metric_ids=["product"],
        )
        assert result.status == "consumer_refused"
        assert result.refusal_reason == "unestablished_joint_law"
        assert result.results[0].envelope.gate_eligible is False
    assert calls == []


def test_legacy_posterior_carrier_survives_cas_and_actual_single_parameter_consumer(
    tmp_path,
) -> None:
    draws = (0.123456789012345, 0.3, 0.5)
    summary = summarize_bayesian_calibration_posterior({"theta": draws}, credible_mass=0.9)

    envelope = summary.parameter_envelopes["theta"]
    assert isinstance(envelope.distribution_payload, PosteriorSamplesCarrier)
    assert envelope.distribution_payload.samples == draws
    store = FileSystemCAS(tmp_path)
    ref = persist_uncertainty_envelope(ensure_ir_artifact_store(store), envelope)
    fresh = load_uncertainty_envelope(ensure_ir_artifact_store(FileSystemCAS(tmp_path)), ref)

    assert isinstance(fresh.distribution_payload, PosteriorSamplesCarrier)
    assert fresh.distribution_payload.samples == draws
    assert fresh.numeric_policy.mode is NumericToleranceMode.DECIMAL_EXACT

    calls: list[float] = []

    def evaluate(**params: float) -> dict[str, float]:
        calls.append(float(params["theta"]))
        return {"metric": params["theta"]}

    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=100,
            mc_batch_size=100,
            mc_min_valid_samples=10,
            compute_sensitivity=False,
        )
    ).propagate(evaluate, {}, {"theta": fresh}, ["metric"])[0]

    assert result.envelope.metadata["mc_n_valid"] == 100
    assert result.envelope.gate_eligible is False
    assert calls
    assert set(calls).issubset(set(draws))


def test_legacy_posterior_pairing_context_is_preserved_but_not_admitted_as_joint_law(
    tmp_path,
) -> None:
    x = (-1.0, 1.0, -1.0, 1.0)
    y = (-1.0, 1.0, -1.0, 1.0)
    reversed_y = (1.0, -1.0, 1.0, -1.0)
    same = summarize_bayesian_calibration_posterior({"x": x, "y": y})
    reversed_pairing = summarize_bayesian_calibration_posterior({"x": x, "y": reversed_y})

    assert sorted(same.posterior_draw_context.samples_by_parameter["y"].samples) == sorted(
        reversed_pairing.posterior_draw_context.samples_by_parameter["y"].samples
    )
    assert (
        same.posterior_draw_context.row_matrix != reversed_pairing.posterior_draw_context.row_matrix
    )
    assert same.posterior_draw_context.row_relation_status == "not_established"
    assert reversed_pairing.posterior_draw_context.row_relation_status == "not_established"

    store = FileSystemCAS(tmp_path)
    ir_store = ensure_ir_artifact_store(store)
    propagator = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=100,
            mc_batch_size=100,
            mc_min_valid_samples=10,
            compute_sensitivity=False,
        )
    )

    def make_evaluator():
        calls: list[dict[str, float]] = []

        def evaluate(**params: float) -> dict[str, float]:
            calls.append(params)
            return {"product": params["x"] * params["y"]}

        return evaluate, calls

    for candidate in (same, reversed_pairing):
        persisted_envelopes = {}
        for name, envelope in candidate.parameter_envelopes.items():
            ref = persist_uncertainty_envelope(ir_store, envelope)
            persisted_envelopes[name] = load_uncertainty_envelope(
                ensure_ir_artifact_store(FileSystemCAS(tmp_path)),
                ref,
            )
        evaluate, calls = make_evaluator()

        result = propagator.propagate(
            evaluate,
            {},
            persisted_envelopes,
            ["product"],
        )[0]
        assert result.envelope.metadata["failure"] == "unestablished_joint_law"
        assert result.envelope.gate_eligible is False
        assert calls == []
