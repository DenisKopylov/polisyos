from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from fixtures.runtime_http import build_runtime_api_env
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.runtime import (
    CounterfactualMetric,
    LineageRef,
    QuantityValue,
    ScenarioRef,
    TemporalRef,
    UnitRef,
)
from polisyos.ir.analytics.forecasting_uncertainty import (
    FanChartSpec,
    ForecastCalibrationMethod,
    ForecastCoverageDiagnostic,
    ForecastIntervalSemantics,
    HorizonDiagnosticState,
    HorizonInterval,
    HorizonPolicyRule,
    HorizonPolicySpec,
    HorizonQuantileSet,
)
from polisyos.ir.analytics.regime_shift_forecast import (
    ForecastShiftTypeAssessment,
    RegimeBenchmarkStatus,
    RegimeForecastCalibrationStatus,
    RegimeIdentifiabilityStatus,
    RegimeModelFamily,
    RegimeShiftForecastBundle,
    persist_regime_shift_forecast_bundle,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.services.scenarios import _enforce_phase4_scenario_gate


def test_run_scenarios_return_manifest_with_assumptions_and_lineage(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    run_details = client.get(f"/api/v1/runs/{run_id}").json()["run"]

    response = client.get(
        f"/api/v1/runs/{run_id}/scenarios",
        params={"valid_at": run_details["started_at"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert response.headers["X-Temporal-Scope"] != "current"
    assert payload["run_id"] == run_id
    assert payload["temporal_scope"]["valid_at"] is not None
    assert payload["scenarios"]

    scenario = payload["scenarios"][0]
    assert scenario["baseline_run_id"] == run_id
    assert scenario["interventions"]
    assert scenario["assumptions"]
    assert scenario["phase4_gate_verdict"]["gate_id"] == "phase4_temporal_policy_gate"
    assert scenario["phase4_gate_verdict"]["status"] == "allowed"
    assert scenario["model_lineage"]["id"].startswith(f"scenario:{scenario['id']}:model")
    assert scenario["assumptions"][0]["lineage"]["id"].startswith(
        f"scenario:{scenario['id']}:assumption"
    )

    manifest_response = client.get(f"/api/v1/scenarios/{scenario['id']}")
    assert manifest_response.status_code == 200
    assert manifest_response.json()["scenario"]["id"] == scenario["id"]


def test_runtime_scenario_gate_rejects_long_uncalibrated_temporal_window() -> None:
    run = SimpleNamespace(
        run_id="R_phase4_long_window",
        details=SimpleNamespace(
            started_at=datetime(2024, 1, 1, tzinfo=UTC),
            finished_at=datetime(2025, 2, 15, tzinfo=UTC),
        ),
    )

    with pytest.raises(RuntimeHTTPError) as exc:
        _enforce_phase4_scenario_gate(run, scenario_id="scn_phase4_long_window")

    assert exc.value.code == "phase4_regime_gate_failed"
    assert exc.value.extensions is not None
    assert exc.value.extensions["phase4_gate_verdict"]["refusal_code"] == (
        "phase4_regime_gate_failed"
    )


def test_runtime_scenario_gate_passes_long_calibrated_bundle_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ref = persist_regime_shift_forecast_bundle(
        store,
        _sample_regime_bundle(horizon=13),
    )
    run = SimpleNamespace(
        run_id="R_phase4_calibrated_window",
        details=SimpleNamespace(
            started_at=datetime(2024, 1, 1, tzinfo=UTC),
            finished_at=datetime(2025, 2, 15, tzinfo=UTC),
        ),
    )

    verdict = _enforce_phase4_scenario_gate(
        run,
        scenario_id="scn_phase4_calibrated_window",
        store=store,
        regime_shift_forecast_bundle_ref=str(ref.artifact_id),
    )

    assert verdict.allowed
    assert verdict.checked_regime_bundle is True
    assert verdict.regime_status == "calibrated"


def test_runtime_scenario_gate_rejects_bad_long_horizon_bundle_ref(tmp_path) -> None:
    run = SimpleNamespace(
        run_id="R_phase4_bad_ref_window",
        details=SimpleNamespace(
            started_at=datetime(2024, 1, 1, tzinfo=UTC),
            finished_at=datetime(2025, 2, 15, tzinfo=UTC),
        ),
    )

    with pytest.raises(RuntimeHTTPError) as exc:
        _enforce_phase4_scenario_gate(
            run,
            scenario_id="scn_phase4_bad_ref_window",
            store=FileSystemCAS(tmp_path),
            regime_shift_forecast_bundle_ref="sha256:" + "f" * 64,
        )

    verdict = exc.value.extensions["phase4_gate_verdict"]
    assert "regime_shift_forecast_bundle_ref_load_failed" in verdict["reasons"]


def test_scenario_capabilities_list_supported_and_unsupported_surfaces(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    scenario = client.get(f"/api/v1/runs/{run_id}/scenarios").json()["scenarios"][0]

    response = client.get(f"/api/v1/scenarios/{scenario['id']}/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["scenario_id"] == scenario["id"]
    surfaces = {item["surface"]: item for item in payload["capabilities"] if not item["metric_id"]}
    assert surfaces["run_metrics"]["supported"] is True
    assert surfaces["whatif"]["supported"] is True
    assert any(
        item["metric_id"] == "policy_cost" and item["supported"] for item in payload["capabilities"]
    )


def test_counterfactual_metrics_are_single_payload_with_scenario_ref(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    scenario = client.get(f"/api/v1/runs/{run_id}/scenarios").json()["scenarios"][0]

    response = client.get(
        f"/api/v1/runs/{run_id}/metrics",
        params={"scenario_id": scenario["id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"]["id"] == scenario["id"]
    metric = payload["metrics"]["policy_cost"]
    assert metric["actual"]["quantity_class"] == "decision"
    assert metric["counterfactual"]["quantity_class"] == "decision"
    assert metric["delta"]["quantity_class"] == "decision"
    assert metric["counterfactual"]["time"]["scenario_id"] == scenario["id"]
    assert metric["delta"]["time"]["scenario_id"] == scenario["id"]
    assert metric["scenario_ref"]["id"] == scenario["id"]
    assert metric["scenario_ref"]["assumption_ids"]
    assert metric["counterfactual"]["lineage"]["summary"]["assumptions"]


def test_scenario_lineage_deep_dive_contains_assumptions_and_exports(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    scenario = client.get(f"/api/v1/runs/{run_id}/scenarios").json()["scenarios"][0]
    metrics = client.get(
        f"/api/v1/runs/{run_id}/metrics",
        params={"scenario_id": scenario["id"]},
    ).json()["metrics"]
    lineage_id = metrics["policy_cost"]["counterfactual"]["lineage"]["id"]

    response = client.get(
        f"/api/v1/lineage/{lineage_id}",
        params={"scenario_id": scenario["id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    lineage = payload["lineage"]
    assert payload["temporal_scope"]["scenario_id"] == scenario["id"]
    assert lineage["id"] == lineage_id
    assert lineage["status"] == "pending"
    node_kinds = {node["kind"] for node in lineage["nodes"]}
    assert {"assumption", "model", "baseline_run", "intervention"}.issubset(node_kinds)
    assert any(edge["relation"] == "assumes" for edge in lineage["edges"])
    assert lineage["exports"]["openlineage"].endswith("/export/openlineage")

    prov_response = client.get(f"/api/v1/lineage/{lineage_id}/export/prov")
    assert prov_response.status_code == 200
    prov_payload = prov_response.json()["payload"]
    assert any(
        entity.get("polisyos:kind") == "assumption" for entity in prov_payload["entity"].values()
    )


def test_create_scenario_draft_is_fetchable(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    quantity = next(
        item
        for item in client.get(f"/api/v1/runs/{run_id}/quantities").json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )
    body = {
        "id": "scn_operator_fixture",
        "policy_question": "What if policy cost is capped?",
        "author": "test-operator",
        "model_family": "operator-specified",
        "interventions": [
            {
                "field": "policy_cost",
                "operator": "set",
                "value": quantity,
                "baseline_value": quantity,
                "constraint_ids": [],
            }
        ],
        "assumptions": [
            {
                "id": "asm_fixture",
                "label": "No behavior change",
                "status": "operator_assumption",
                "lineage": {
                    "id": "scenario:fixture:assumption",
                    "status": "pending",
                    "freshness": "current",
                    "summary": {"source": "test"},
                },
            }
        ],
    }

    response = client.post(f"/api/v1/runs/{run_id}/scenarios", json=body)

    assert response.status_code == 200
    assert response.headers["Location"] == "/api/v1/scenarios/scn_operator_fixture"
    scenario = response.json()["scenario"]
    assert scenario["status"] == "draft"
    assert scenario["assumptions"][0]["lineage"]["id"] == "scenario:fixture:assumption"
    fetched = client.get("/api/v1/scenarios/scn_operator_fixture")
    assert fetched.status_code == 200
    assert fetched.json()["scenario"]["policy_question"] == "What if policy cost is capped?"


def test_created_scenario_survives_fresh_runtime_context(tmp_path) -> None:
    first_env = build_runtime_api_env(tmp_path)
    first_client = first_env["client"]
    run_id = first_env["core_run_id"]
    quantity = next(
        item
        for item in first_client.get(f"/api/v1/runs/{run_id}/quantities").json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )
    body = {
        "id": "scn_durable_fixture",
        "policy_question": "What if policy cost is capped durably?",
        "author": "test-operator",
        "model_family": "operator-specified",
        "interventions": [
            {
                "field": "policy_cost",
                "operator": "set",
                "value": quantity,
                "baseline_value": quantity,
                "constraint_ids": [],
            }
        ],
        "assumptions": [
            {
                "id": "asm_durable_fixture",
                "label": "No behavior change",
                "status": "operator_assumption",
                "lineage": {
                    "id": "scenario:durable:assumption",
                    "status": "pending",
                    "freshness": "current",
                    "summary": {"source": "test"},
                },
            }
        ],
    }

    created = first_client.post(f"/api/v1/runs/{run_id}/scenarios", json=body)
    assert created.status_code == 200
    scenario = created.json()["scenario"]
    assert scenario["lifecycle_status"] == "saved"
    assert scenario["manifest_hash"].startswith("sha256:")
    assert scenario["revision"] == 1

    second_env = build_runtime_api_env(tmp_path)
    second_client = second_env["client"]
    fetched = second_client.get("/api/v1/scenarios/scn_durable_fixture")

    assert fetched.status_code == 200
    payload = fetched.json()
    assert payload["scenario"]["policy_question"] == body["policy_question"]
    assert payload["scenario"]["manifest_hash"] == scenario["manifest_hash"]


def test_scenario_manifest_rejects_conflicting_temporal_scope(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    run_details = client.get(f"/api/v1/runs/{run_id}").json()["run"]
    scenario = client.get(
        f"/api/v1/runs/{run_id}/scenarios",
        params={"valid_at": run_details["started_at"]},
    ).json()["scenarios"][0]

    response = client.get(
        f"/api/v1/scenarios/{scenario['id']}",
        params={"valid_at": run_details["finished_at"]},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "scenario_temporal_scope_mismatch"


def test_counterfactual_metric_rejects_anonymous_scenario_values() -> None:
    actual = _quantity(metric_id="effect_size", scenario_id=None)
    scenario_ref = ScenarioRef(
        id="scn_named",
        status="computed",
        baseline_run_id="run_actual",
        lineage=LineageRef(
            id="scenario:scn_named:model",
            status="pending",
            freshness="current",
            summary={"source": "test"},
        ),
        assumption_ids=["asm_1"],
    )

    with pytest.raises(ValueError, match=r"time\.scenario_id"):
        CounterfactualMetric(
            metric_id="effect_size",
            label="Effect size",
            actual=actual,
            counterfactual=_quantity(metric_id="effect_size.cf", scenario_id=None),
            delta=_quantity(metric_id="effect_size.delta", scenario_id="scn_named"),
            scenario_ref=scenario_ref,
            assumption_ids=["asm_1"],
        )


def _quantity(*, metric_id: str, scenario_id: str | None) -> QuantityValue:
    return QuantityValue(
        point=1.0,
        unit=UnitRef(code="1", system="ucum", display="ratio"),
        metric_id=metric_id,
        lineage=LineageRef(
            id=f"lineage:{metric_id}",
            status="verified",
            freshness="current",
            summary={"source": "test"},
        ),
        time=TemporalRef(scenario_id=scenario_id),
        quantity_class="decision",
    )


def _ref(hex_digit: str, *, kind: str = "ir.test_artifact") -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=f"sha256:{hex_digit * 64}",
        kind=kind,
        media_type="application/json",
    )


def _sample_regime_bundle(*, horizon: int) -> RegimeShiftForecastBundle:
    generated_at = datetime.now(UTC)
    return RegimeShiftForecastBundle(
        method_fqn="forecasting.regime.hybrid@1.0.0",
        target_id="tax_receipts",
        generated_at=generated_at,
        prediction_interval=(
            HorizonInterval(
                horizon=horizon,
                point=10.0,
                lower=8.0,
                upper=12.0,
                coverage_target=0.9,
                constructor=ForecastCalibrationMethod.BAYESIAN_PLUS_CONFORMAL,
                sample_count=40,
            ),
        ),
        fan_chart=FanChartSpec(
            quantile_levels=(0.05, 0.50, 0.95),
            horizons=(
                HorizonQuantileSet(
                    horizon=horizon,
                    quantiles={"0.05": 8.0, "0.5": 10.0, "0.95": 12.0},
                ),
            ),
        ),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=0.9,
            empirical_coverage_by_horizon={horizon: 0.91},
            coverage_gap_by_horizon={horizon: 0.01},
            mean_interval_width_by_horizon={horizon: 4.0},
            sample_count_by_horizon={horizon: 40},
            last_recalibrated_at=generated_at,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.BAYESIAN_PLUS_CONFORMAL,
            rules=(
                HorizonPolicyRule(
                    horizon_start=horizon,
                    horizon_end=horizon,
                    diagnostic_state=HorizonDiagnosticState.GREEN,
                    allowed_methods=(ForecastCalibrationMethod.BAYESIAN_PLUS_CONFORMAL,),
                    gate_eligible=True,
                    regime="hybrid_regime_shift",
                ),
            ),
            gate_eligible=True,
        ),
        interval_semantics=ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL,
        calibration_method=ForecastCalibrationMethod.BAYESIAN_PLUS_CONFORMAL,
        nominal_coverage=0.9,
        sample_size_assumption="unit_test_fixture",
        regime_assumption="hybrid recurring regimes and one-off structural breaks",
        regime_model_family=RegimeModelFamily.HYBRID,
        identifiability_status=RegimeIdentifiabilityStatus.IDENTIFIED,
        regime_status=RegimeForecastCalibrationStatus.CALIBRATED,
        regime_count_posterior_ref=_ref("1"),
        break_count_posterior_ref=_ref("2"),
        assignment_posterior_ref=_ref("3"),
        break_posterior_ref=_ref("4"),
        permutation_invariant_regime_map_ref=_ref("5"),
        regime_parameter_summary_ref=_ref("6"),
        transition_summary_ref=_ref("7"),
        predictive_mixture_ref=_ref("8"),
        regime_conditional_forecasts_ref=_ref("9"),
        calibration_slice_ref=_ref("a"),
        break_recovery_curve_ref=_ref("b"),
        shift_type_assessment=ForecastShiftTypeAssessment.STRUCTURAL,
        shift_type_assessment_ref=_ref("c"),
        identifiability_diagnostics_ref=_ref("d"),
        benchmark_status=RegimeBenchmarkStatus.GREEN,
    )
