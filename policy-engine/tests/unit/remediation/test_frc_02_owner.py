"""Focused witnesses for the real FRC-02 predictive owner slice.

These tests deliberately exercise the owner through its CAS boundary.  The
owner is predictive evidence only: it must never be mistaken for a causal
effect-confidence interval or an S10 promotion.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from _helpers.runtime_http import (
    _put_fixture_authority_envelope,
    _record_fixture_owner,
    _runtime_api_request,
    _runtime_api_tenant_scope,
    _runtime_fixture_authority_boundary,
    build_runtime_api_env,
    close_runtime_api_env,
)
from pydantic import ValidationError

from polisyos.calibration.forecast_bridge import (
    persist_empirical_calibration_evidence,
    produce_empirical_calibration_evidence,
)
from polisyos.core.artifacts import (
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
)
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts._profiled_ref import profile_bound_ref
from polisyos.core.artifacts.manifest import ArtifactAuthorityInfo, ArtifactRef
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.ir.analytics.backtest import BacktestReport, load_backtest_report
from polisyos.ir.analytics.forecasting_uncertainty import load_forecasting_uncertainty_bundle
from polisyos.ir.artifacts import InputRef, get_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel, BacktestReportRef
from polisyos.runtime.http.dependencies import get_runtime_api_context
from polisyos.scientist.methods.backtesting.forecast_owner import (
    CalibrationRuleBinding,
    ForecastOwner,
    ForecastOwnerRequest,
    ForecastTemporalRoles,
    TrainHoldoutSplit,
)

METHOD_FQN = "forecasting.univariate.exponential_smoothing@1.0.0"
ESTIMAND = "predictive_interval_coverage"
RULE_ID = "rolling-origin-residual-conformal.v1"
RULE_KIND = "ir.forecast_calibration_rule"


def _put_json(
    store: FileSystemCAS,
    payload: object,
    *,
    kind: str,
    schema: SchemaInfo | None = None,
    authority: ArtifactAuthorityInfo | None = None,
) -> ArtifactRef:
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=schema,
            authority=authority,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _spec(store: FileSystemCAS, *, kind: str, spec_id: str) -> ArtifactRef:
    return _put_json(
        store,
        {"schema_version": "1.0", "spec_id": spec_id},
        kind=kind,
    )


def _source(
    store: FileSystemCAS,
    *,
    holdout: list[float],
    training: list[float] | None = None,
) -> DataSnapshotRef:
    training_values = training if training is not None else [float(index) for index in range(1, 31)]
    values = training_values + holdout
    data_ref = _put_json(
        store,
        {"metric": values},
        kind="test.forecast.observed_data",
    )
    snapshot = DataSnapshot(
        data_ref=ArtifactRef.model_validate(data_ref),
        stats={"rows": len(values), "source": "test_frc_02_owner"},
    )
    snapshot_ref = _put_json(
        store,
        snapshot.model_dump(mode="json"),
        kind="fabric.data_snapshot",
    )
    return DataSnapshotRef(
        artifact_id=snapshot_ref.artifact_id,
        kind=snapshot_ref.kind,
        media_type=snapshot_ref.media_type,
        manifest_profile_sha256=snapshot_ref.manifest_profile_sha256,
    )


def _rule(
    store: FileSystemCAS,
    *,
    payload_updates: dict[str, object] | None = None,
    kind: str = RULE_KIND,
) -> ArtifactRef:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "rule_id": RULE_ID,
        "rule_version": "1.0",
        "estimand": ESTIMAND,
        "algorithm": "rolling_origin_residual_conformal",
        "nominal_coverage": 0.90,
    }
    payload.update(payload_updates or {})
    return _put_json(
        store,
        payload,
        kind=kind,
    )


def _temporal_roles() -> ForecastTemporalRoles:
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    return ForecastTemporalRoles(
        data_valid_time=origin,
        calibration_window_start=origin + timedelta(days=1),
        calibration_window_end=origin + timedelta(days=2),
        policy_effective_time=origin + timedelta(days=3),
        prediction_time=origin + timedelta(days=4),
        observation_time=origin + timedelta(days=5),
    )


def _request(
    source_ref: DataSnapshotRef,
    rule_ref: ArtifactRef,
    *,
    report_id: str,
    manifest_inputs: tuple[InputRef, ...] = (),
    model_spec_ref: ArtifactRef | ArtifactRefModel | str | None = None,
    policy_spec_ref: ArtifactRef | ArtifactRefModel | str | None = None,
    train_end: int = 30,
    horizon: int = 4,
) -> ForecastOwnerRequest:
    return ForecastOwnerRequest(
        observed_source_ref=source_ref,
        split=TrainHoldoutSplit(
            train_start=0,
            train_end=train_end,
            holdout_start=train_end,
            holdout_end=train_end + horizon,
            horizon=horizon,
        ),
        target_metric="metric",
        method_fqn=METHOD_FQN,
        method_params={"horizon": horizon, "alpha": 0.3, "beta": 0.1},
        report_id=report_id,
        estimand=ESTIMAND,
        calibration_rule=CalibrationRuleBinding(
            rule_id=RULE_ID,
            artifact_ref={
                "artifact_id": str(rule_ref.artifact_id),
                "kind": rule_ref.kind,
                "media_type": rule_ref.media_type,
                "manifest_profile_sha256": rule_ref.manifest_profile_sha256,
            },
        ),
        temporal_roles=_temporal_roles(),
        model_spec_ref=model_spec_ref,
        policy_spec_ref=policy_spec_ref,
        manifest_inputs=manifest_inputs,
    )


def test_real_ets_owner_persists_content_bound_predictive_evidence(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)

    result = ForecastOwner(store).run(
        _request(source_ref, rule_ref, report_id="frc-owner-ets-green")
    )

    assert result.method_fqn == METHOD_FQN
    assert result.estimand == ESTIMAND
    assert result.authority_scope == "predictive_only"
    assert result.bridge_status == "bridge_pending"
    assert result.denominator == 4
    assert 0.0 <= result.empirical_coverage <= 1.0
    assert result.nominal_coverage == pytest.approx(0.90)
    assert str(result.observed_source_ref.artifact_id) == str(source_ref.artifact_id)
    assert result.observed_source_ref.kind == source_ref.kind
    assert result.observed_source_ref.media_type == source_ref.media_type
    assert result.training_slice_ref.kind == "ir.forecast_training_slice"
    assert result.method_artifact_ref.kind == "foundry.method_artifact"
    assert result.uncertainty_bundle_ref.kind == "ir.forecasting_uncertainty_bundle"
    assert result.calibration_diagnostics_ref.kind == "ir.calibration_diagnostics_report"
    assert result.backtest_report_ref.kind == "ir.backtest_report"

    generated_refs = (
        (result.training_slice_ref, "polisyos.ir.ForecastTrainingSlice", "1.0"),
        (result.method_artifact_ref, "polisyos.foundry.method_artifact", "1.0.0"),
        (result.uncertainty_bundle_ref, "ir.forecasting_uncertainty_bundle", "1.0"),
        (
            result.calibration_diagnostics_ref,
            "ir.calibration_diagnostics_report.v1",
            "1.0",
        ),
    )
    for ref, schema_name, schema_version in generated_refs:
        selected_profile = ref.manifest_profile_sha256
        assert selected_profile is not None
        manifest = store.get_manifest_by_profile(ref.artifact_id, selected_profile)
        assert str(manifest.artifact_id) == str(ref.artifact_id)
        assert artifact_manifest_profile_sha256(manifest) == selected_profile
        assert (manifest.kind, manifest.media_type) == (ref.kind, "application/json")
        assert manifest.artifact_schema is not None
        assert (manifest.artifact_schema.name, manifest.artifact_schema.version) == (
            schema_name,
            schema_version,
        )

    report_profile = result.backtest_report_ref.manifest_profile_sha256
    assert report_profile is not None
    report_manifest = store.get_manifest_by_profile(
        result.backtest_report_ref.artifact_id, report_profile
    )
    for role, (ref, _schema_name, _schema_version) in zip(
        ("training_slice", "method_artifact", "uncertainty_bundle", "calibration_diagnostics"),
        generated_refs,
        strict=True,
    ):
        matching_edges = [item for item in report_manifest.inputs if item.role == role]
        assert len(matching_edges) == 1
        edge = matching_edges[0]
        assert str(edge.artifact_id) == str(ref.artifact_id)
        assert edge.manifest_profile_sha256 == ref.manifest_profile_sha256

    bundle = load_forecasting_uncertainty_bundle(
        _ensure_ir_artifact_store(store), result.uncertainty_bundle_ref
    )
    assert bundle.target_id == result.target_metric
    assert bundle.coverage_diagnostic.pit_summary_ref is not None
    pit_payload = get_json_artifact(
        _ensure_ir_artifact_store(store),
        bundle.coverage_diagnostic.pit_summary_ref.artifact_id,
    )
    assert pit_payload["target_id"] == result.target_metric
    diagnostics = get_json_artifact(
        _ensure_ir_artifact_store(store), result.calibration_diagnostics_ref.artifact_id
    )
    assert diagnostics["metadata"]["coverage_numerator"] == result.numerator
    assert diagnostics["metadata"]["coverage_denominator"] == result.denominator
    assert diagnostics["metrics"]["n_obs"] == result.denominator
    interval_metadata = diagnostics["metadata"]["interval_coverage"]
    assert interval_metadata["status"] == "evaluated"
    assert interval_metadata["n_comparisons"] == 1
    interval_bins = diagnostics["curves"]["interval_coverage"]
    assert len(interval_bins) == 1
    assert interval_bins[0]["count"] == result.denominator
    assert interval_bins[0]["mean_observed"] == pytest.approx(result.empirical_coverage)
    assert interval_bins[0]["mean_predicted"] == pytest.approx(result.nominal_coverage)

    report = load_backtest_report(_ensure_ir_artifact_store(store), result.backtest_report_ref)
    assert report.overall_coverage_probability == pytest.approx(result.empirical_coverage)
    assert report.metadata["authority_scope"] == "predictive_only"
    assert report.metadata["calibration_diagnostics_ref"]["artifact_id"] == str(
        result.calibration_diagnostics_ref.artifact_id
    )
    assert report.trust_eligible is False
    assert report.trust_score is None
    assert "trust_screening:predictive_only_bridge_pending" in report.degraded_reasons


def test_real_ets_owner_persists_cas_bound_pair_in_report_metadata_and_manifest(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    model_ref = _spec(store, kind="ir.model_spec", spec_id="frc-owner-model")
    policy_ref = _spec(store, kind="ir.policy_spec", spec_id="frc-owner-policy")
    model_id = str(model_ref.artifact_id)
    policy_id = str(policy_ref.artifact_id)

    result = ForecastOwner(store).run(
        _request(
            source_ref,
            rule_ref,
            report_id="frc-owner-complete-pair",
            model_spec_ref=model_id,
            policy_spec_ref=policy_id,
        )
    )

    assert result.model_spec_ref is not None
    assert str(result.model_spec_ref.artifact_id) == model_id
    assert result.model_spec_ref.kind == "ir.model_spec"
    assert result.model_spec_ref.media_type == "application/json"
    assert result.policy_spec_ref is not None
    assert str(result.policy_spec_ref.artifact_id) == policy_id
    assert result.policy_spec_ref.kind == "ir.policy_spec"
    assert result.policy_spec_ref.media_type == "application/json"
    assert result.authority_scope == "predictive_only"
    assert result.bridge_status == "bridge_pending"

    report = load_backtest_report(_ensure_ir_artifact_store(store), result.backtest_report_ref)
    assert report.model_spec_ref == model_id
    assert report.policy_spec_ref == policy_id
    assert report.metadata["model_spec_ref"] == model_id
    assert report.metadata["policy_spec_ref"] == policy_id
    assert report.metadata["authority_scope"] == "predictive_only"
    assert report.metadata["bridge_status"] == "bridge_pending"
    assert report.trust_eligible is False
    assert report.trust_score is None

    report_profile = result.backtest_report_ref.manifest_profile_sha256
    assert report_profile is not None
    manifest = store.get_manifest_by_profile(result.backtest_report_ref.artifact_id, report_profile)
    expected_roles = [
        "observed_source",
        "observed_data",
        "calibration_rule",
        "training_slice",
        "method_artifact",
        "uncertainty_bundle",
        "calibration_diagnostics",
        "model_spec",
        "policy_spec",
    ]
    assert [item.role for item in manifest.inputs] == expected_roles
    assert all(item.manifest_profile_sha256 is not None for item in manifest.inputs)
    model_manifest = store.get_manifest(model_ref.artifact_id)
    policy_manifest = store.get_manifest(policy_ref.artifact_id)
    model_edges = [
        (str(item.artifact_id), item.role, item.manifest_profile_sha256)
        for item in manifest.inputs
        if item.role == "model_spec"
    ]
    policy_edges = [
        (str(item.artifact_id), item.role, item.manifest_profile_sha256)
        for item in manifest.inputs
        if item.role == "policy_spec"
    ]
    assert model_edges == [
        (model_id, "model_spec", artifact_manifest_profile_sha256(model_manifest))
    ]
    assert policy_edges == [
        (policy_id, "policy_spec", artifact_manifest_profile_sha256(policy_manifest))
    ]


def test_real_ets_owner_preserves_same_id_selected_model_policy_profiles(
    tmp_path: Path,
) -> None:
    """The owner resolves and persists the exact selected profiles, not current defaults."""

    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    model_default = _spec(store, kind="ir.model_spec", spec_id="selected-model-profile")
    policy_default = _spec(store, kind="ir.policy_spec", spec_id="selected-policy-profile")

    model_selected = store.put_bytes(
        store.get_bytes(model_default),
        PutOptions(
            kind=model_default.kind,
            media_type=model_default.media_type,
            schema=SchemaInfo(name="test.selected.model_spec", version="nondefault-view"),
        ),
        return_selected_profile=True,
    )
    policy_selected = store.put_bytes(
        store.get_bytes(policy_default),
        PutOptions(
            kind=policy_default.kind,
            media_type=policy_default.media_type,
            schema=SchemaInfo(name="test.selected.policy_spec", version="nondefault-view"),
        ),
        return_selected_profile=True,
    )
    assert model_selected.artifact_id == model_default.artifact_id
    assert policy_selected.artifact_id == policy_default.artifact_id
    assert model_selected.manifest_profile_sha256 != model_default.manifest_profile_sha256
    assert policy_selected.manifest_profile_sha256 != policy_default.manifest_profile_sha256
    assert artifact_manifest_profile_sha256(store.get_manifest(model_default)) == (
        model_default.manifest_profile_sha256
    )
    assert artifact_manifest_profile_sha256(store.get_manifest(policy_default)) == (
        policy_default.manifest_profile_sha256
    )

    selected_model_ref = ArtifactRefModel.model_validate(model_selected.model_dump(mode="json"))
    selected_policy_ref = ArtifactRefModel.model_validate(policy_selected.model_dump(mode="json"))
    result = ForecastOwner(store).run(
        _request(
            source_ref,
            rule_ref,
            report_id="frc-owner-selected-profiles",
            model_spec_ref=selected_model_ref,
            policy_spec_ref=selected_policy_ref,
        )
    )

    assert result.model_spec_ref == selected_model_ref
    assert result.policy_spec_ref == selected_policy_ref
    report_profile = result.backtest_report_ref.manifest_profile_sha256
    assert report_profile is not None
    report_manifest = store.get_manifest_by_profile(
        result.backtest_report_ref.artifact_id,
        report_profile,
    )
    exact_spec_edges = {
        (str(item.artifact_id), item.role, item.manifest_profile_sha256)
        for item in report_manifest.inputs
        if item.role in {"model_spec", "policy_spec"}
    }
    assert exact_spec_edges == {
        (
            str(selected_model_ref.artifact_id),
            "model_spec",
            selected_model_ref.manifest_profile_sha256,
        ),
        (
            str(selected_policy_ref.artifact_id),
            "policy_spec",
            selected_policy_ref.manifest_profile_sha256,
        ),
    }


def test_real_ets_owner_merges_run_binding_edges_with_required_owner_edges(
    tmp_path: Path,
) -> None:
    """Run/source edges supplement the full owner lineage instead of replacing it."""

    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    model_ref = _spec(store, kind="ir.model_spec", spec_id="run-bound-model")
    policy_ref = _spec(store, kind="ir.policy_spec", spec_id="run-bound-policy")
    run_manifest_ref = _put_json(
        store,
        {"schema_version": "1.0", "run_id": "run-frc-owner-edges"},
        kind="runtime.core_run_manifest",
    )
    candidate_source_ref = _put_json(
        store,
        {"schema_version": "1.0", "run_id": "run-frc-owner-edges"},
        kind="runtime.quality.candidate_scenario_source",
    )
    run_inputs = (
        InputRef(
            artifact_id=run_manifest_ref.artifact_id,
            role="run_manifest",
            manifest_profile_sha256=run_manifest_ref.manifest_profile_sha256,
        ),
        InputRef(
            artifact_id=candidate_source_ref.artifact_id,
            role="candidate_source",
            manifest_profile_sha256=candidate_source_ref.manifest_profile_sha256,
        ),
    )

    result = ForecastOwner(store).run(
        _request(
            source_ref,
            rule_ref,
            report_id="frc-owner-run-bound-edges",
            model_spec_ref=str(model_ref.artifact_id),
            policy_spec_ref=str(policy_ref.artifact_id),
            manifest_inputs=run_inputs,
        )
    )

    report_profile = result.backtest_report_ref.manifest_profile_sha256
    assert report_profile is not None
    manifest = store.get_manifest_by_profile(
        result.backtest_report_ref.artifact_id,
        report_profile,
    )
    edges = {
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in manifest.inputs
    }
    assert {
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in run_inputs
    }.issubset(edges)
    expected_owner_roles = {
        "observed_source",
        "observed_data",
        "calibration_rule",
        "training_slice",
        "method_artifact",
        "uncertainty_bundle",
        "calibration_diagnostics",
        "model_spec",
        "policy_spec",
    }
    assert expected_owner_roles.issubset({item.role for item in manifest.inputs})
    assert len(manifest.inputs) == len(expected_owner_roles) + len(run_inputs)
    assert all(item.manifest_profile_sha256 is not None for item in manifest.inputs)


def test_real_ets_owner_rejects_missing_model_policy_cas_binding_before_derived_writes(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    policy_ref = _spec(store, kind="ir.policy_spec", spec_id="frc-owner-policy")
    missing_model_id = "sha256:" + ("f" * 64)
    before_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}

    with pytest.raises(ValueError, match=r"missing|manifest|CAS|artifact"):
        ForecastOwner(store).run(
            _request(
                source_ref,
                rule_ref,
                report_id="frc-owner-missing-model",
                model_spec_ref=missing_model_id,
                policy_spec_ref=str(policy_ref.artifact_id),
            )
        )

    assert {str(artifact_id) for artifact_id in store.iter_artifact_ids()} == before_ids


def test_real_ets_owner_rejects_wrong_model_manifest_profile_before_derived_writes(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    wrong_model_ref = _spec(
        store,
        kind="test.frc02.model_spec",
        spec_id="frc-owner-wrong-model-kind",
    )
    policy_ref = _spec(store, kind="ir.policy_spec", spec_id="frc-owner-policy")
    before_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}

    with pytest.raises(ValueError, match=r"kind|media|manifest|content-bound|profile"):
        ForecastOwner(store).run(
            _request(
                source_ref,
                rule_ref,
                report_id="frc-owner-wrong-model-profile",
                model_spec_ref=str(wrong_model_ref.artifact_id),
                policy_spec_ref=str(policy_ref.artifact_id),
            )
        )

    assert {str(artifact_id) for artifact_id in store.iter_artifact_ids()} == before_ids


def test_same_ets_shape_uses_held_out_observations_for_suitability(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    rule_ref = _rule(store)
    training = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
    in_profile = ForecastOwner(store).run(
        _request(
            _source(store, training=training, holdout=[20.0, 21.0, 22.0]),
            rule_ref,
            report_id="frc-owner-ets-in-profile",
            train_end=len(training),
            horizon=3,
        )
    )
    out_of_profile = ForecastOwner(store).run(
        _request(
            _source(store, training=training, holdout=[1000.0, 1001.0, 1002.0]),
            rule_ref,
            report_id="frc-owner-ets-out-of-profile",
            train_end=len(training),
            horizon=3,
        )
    )

    in_bundle = load_forecasting_uncertainty_bundle(
        _ensure_ir_artifact_store(store), in_profile.uncertainty_bundle_ref
    )
    out_bundle = load_forecasting_uncertainty_bundle(
        _ensure_ir_artifact_store(store), out_of_profile.uncertainty_bundle_ref
    )
    assert in_bundle.horizon_policy.gate_eligible is True
    assert out_bundle.horizon_policy.gate_eligible is True
    assert in_profile.method_fqn == out_of_profile.method_fqn
    assert in_profile.point_forecast == out_of_profile.point_forecast
    assert in_profile.predictive_intervals == out_of_profile.predictive_intervals
    assert in_profile.empirical_coverage != out_of_profile.empirical_coverage
    assert in_profile.coverage_numerator != out_of_profile.coverage_numerator
    assert in_profile.coverage_denominator == out_of_profile.coverage_denominator
    assert in_profile.empirical_suitability == "supported"
    assert out_of_profile.empirical_suitability == "limited"


def test_real_forecast_report_is_limited_in_fresh_diagnostic_http_view(
    tmp_path: Path,
) -> None:
    """Serve only the reader-recomputed projection; raw content stays protected."""
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    app = env["app"]
    original_context_override = app.dependency_overrides.get(get_runtime_api_context)
    try:
        runtime_context = env["app"].state.runtime_api_ctx
        store = runtime_context.store
        rule_ref = _rule(store)
        training = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
        owner_results = []
        report_refs = []
        for holdout, report_id in (
            ([20.0, 21.0, 22.0], "frc-owner-inspector-in-profile"),
            ([1000.0, 1001.0, 1002.0], "frc-owner-inspector-out-of-profile"),
        ):
            result = ForecastOwner(store).run(
                _request(
                    _source(store, training=training, holdout=holdout),
                    rule_ref,
                    report_id=report_id,
                    train_end=len(training),
                    horizon=3,
                )
            )
            selected_ref = ArtifactRef.model_validate(
                result.backtest_report_ref.model_dump(mode="json")
            )
            assert selected_ref.manifest_profile_sha256 is not None
            manifest = store.get_manifest(selected_ref)
            assert (
                artifact_manifest_profile_sha256(manifest) == selected_ref.manifest_profile_sha256
            )
            assert manifest.inputs
            assert all(item.manifest_profile_sha256 is not None for item in manifest.inputs)
            owner_results.append(result)
            report_refs.append(selected_ref)

        assert owner_results[0].point_forecast == owner_results[1].point_forecast
        assert owner_results[0].predictive_intervals == owner_results[1].predictive_intervals
        assert owner_results[0].empirical_coverage != owner_results[1].empirical_coverage
        _record_fixture_owner(
            store,
            *report_refs,
            tenant_id=env["tenant_a"],
            cell_id=env["cell_a"],
            runtime_api_env=env,
        )
        with _runtime_api_tenant_scope(env):
            client = env["client"]
            assert client is not None

            def fetch_content(ref: ArtifactRef, *, selected_profile: bool = True):
                url = f"/api/v1/artifacts/{ref.artifact_id}/content"
                if selected_profile:
                    url += f"?manifest_profile_sha256={ref.manifest_profile_sha256}"
                return _runtime_api_request(env, client.get, url)

            def fetch_diagnostic(ref: ArtifactRef, *, selected_profile: bool = True):
                url = f"/api/v1/artifacts/{ref.artifact_id}/predictive-coverage-diagnostic"
                if selected_profile:
                    url += f"?manifest_profile_sha256={ref.manifest_profile_sha256}"
                return _runtime_api_request(env, client.get, url)

            runtime_context = app.state.runtime_api_ctx
            default_disabled = fetch_diagnostic(report_refs[0], selected_profile=False)
            assert default_disabled.status_code == 409
            assert default_disabled.json()["code"] == "predictive_coverage_diagnostic_not_admitted"

            app.dependency_overrides[get_runtime_api_context] = lambda: replace(
                runtime_context,
                allow_candidate_predictive_diagnostic_surface=True,
            )
            default_response = fetch_diagnostic(report_refs[0], selected_profile=False)
            assert default_response.status_code == 200

            app.dependency_overrides[get_runtime_api_context] = lambda: replace(
                runtime_context,
                allow_candidate_predictive_diagnostic_surface=False,
            )
            disabled = fetch_diagnostic(report_refs[0], selected_profile=False)
            assert disabled.status_code == 409
            assert disabled.json()["code"] == "predictive_coverage_diagnostic_not_admitted"

            app.dependency_overrides[get_runtime_api_context] = lambda: replace(
                runtime_context,
                allow_candidate_predictive_diagnostic_surface=True,
            )
            explicit_response = fetch_diagnostic(report_refs[1])
            assert default_response.status_code == 200
            assert explicit_response.status_code == 200
            default_projection = default_response.json()
            explicit_projection = explicit_response.json()
            assert default_projection["source_artifact_id"] == str(report_refs[0].artifact_id)
            assert explicit_projection["source_artifact_id"] == str(report_refs[1].artifact_id)
            assert (
                default_projection["source_manifest_profile_sha256"]
                == report_refs[0].manifest_profile_sha256
            )
            assert (
                explicit_projection["source_manifest_profile_sha256"]
                == report_refs[1].manifest_profile_sha256
            )
            assert default_response.headers["X-Manifest-Profile-SHA256"] == (
                report_refs[0].manifest_profile_sha256
            )
            assert explicit_response.headers["X-Manifest-Profile-SHA256"] == (
                report_refs[1].manifest_profile_sha256
            )
            unavailable_profile_response = _runtime_api_request(
                env,
                client.get,
                f"/api/v1/artifacts/{report_refs[0].artifact_id}/predictive-coverage-diagnostic",
                params={"manifest_profile_sha256": "sha256:" + "f" * 64},
            )
            assert unavailable_profile_response.status_code == 404
            assert (
                unavailable_profile_response.json()["code"] == "artifact_manifest_profile_not_found"
            )
            assert "preview" not in default_projection
            assert "raw_content" not in default_projection
            assert (
                default_projection["assessment"] == explicit_projection["assessment"] == "limited"
            )

            raw_default = fetch_content(report_refs[0], selected_profile=False)
            raw_explicit = fetch_content(report_refs[1])
            for response in (raw_default, raw_explicit):
                assert response.status_code == 409
                assert response.json()["code"] == "authority_surface_admission_blocked"
            assert default_projection["source_materialization"] == "reader_materialized"
            for field in (
                "producer_attestation_status",
                "s10_metric_mapping_status",
                "s10_threshold_status",
                "issuer_status",
                "effective_time_status",
                "counterfactual_credibility_status",
                "causal_effect_status",
            ):
                assert default_projection[field] == "not_established"
            assert {
                "promotion",
                "publication",
                "policy_selection",
                "causal_effect_claim",
            }.issubset(default_projection["may_not_use_for"])

            # The distinct real owner computations above are retained as
            # diagnostics, but this bounded reader does not reconcile each row
            # with selected forecast/holdout values. Do not label them observations.
            for projection in (default_projection, explicit_projection):
                assert projection["measurement_status"] == "not_measured"
                assert projection["reason_code"] == "unsupported_report_scope"
                assert projection["scenarios"] == []
            assert owner_results[0].empirical_suitability == "supported"
            assert owner_results[1].empirical_suitability == "limited"

            report_bytes = store.get_bytes(report_refs[0])
            profileless_canon_ref = store.put_bytes(
                report_bytes + b" ",
                PutOptions(
                    kind="ir.backtest_report",
                    media_type="application/json",
                    schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
                ),
            )
            _record_fixture_owner(
                store,
                profileless_canon_ref,
                tenant_id=env["tenant_a"],
                cell_id=env["cell_a"],
                runtime_api_env=env,
            )
            profileless_canon_response = fetch_diagnostic(
                profileless_canon_ref,
                selected_profile=False,
            )
            assert profileless_canon_response.status_code == 409
            assert profileless_canon_response.json()["code"] == "canon_profile_absent"

            wrong_kind_ref = _put_json(
                store,
                json.loads(report_bytes),
                kind="test.not_backtest_report",
                schema=SchemaInfo(name="test.not_backtest_report", version="1.0"),
            )
            assert wrong_kind_ref.artifact_id == report_refs[0].artifact_id
            assert wrong_kind_ref.manifest_profile_sha256 != report_refs[0].manifest_profile_sha256
            report_manifest = store.get_manifest(report_refs[0])
            assert report_manifest.canon is not None
            wrong_media_ref = profile_bound_ref(
                store,
                store.put_bytes(
                    report_bytes,
                    PutOptions(
                        kind="ir.backtest_report",
                        media_type="application/octet-stream",
                        schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
                        canon=report_manifest.canon,
                    ),
                ),
            )
            assert wrong_media_ref.artifact_id == report_refs[0].artifact_id
            assert wrong_media_ref.manifest_profile_sha256 != report_refs[0].manifest_profile_sha256
            assert store.get_manifest(wrong_media_ref).media_type == "application/octet-stream"
            wrong_schema_ref = _put_json(
                store,
                json.loads(report_bytes),
                kind="ir.backtest_report",
                schema=SchemaInfo(name="ir.backtest_report", version="2.0"),
            )
            assert wrong_schema_ref.artifact_id == report_refs[0].artifact_id
            assert (
                wrong_schema_ref.manifest_profile_sha256 != report_refs[0].manifest_profile_sha256
            )
            oversized_base_report = load_backtest_report(
                _ensure_ir_artifact_store(store),
                BacktestReportRef.model_validate(report_refs[0].model_dump(mode="json")),
            )
            oversized_payload = oversized_base_report.model_dump(mode="json")
            oversized_payload["metadata"] = {
                **oversized_payload["metadata"],
                "fixture_note": "x" * 2_000_001,
            }
            oversized_report = BacktestReport.model_validate(oversized_payload)
            oversized_payload = oversized_report.model_dump(mode="json")
            assert BacktestReport.model_validate(oversized_payload) == oversized_report
            oversized_ref = _put_json(
                store,
                oversized_payload,
                kind="ir.backtest_report",
                schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
            )
            oversized_manifest = store.get_manifest(oversized_ref)
            assert oversized_manifest.kind == "ir.backtest_report"
            assert oversized_manifest.media_type == "application/json"
            assert oversized_manifest.artifact_schema == SchemaInfo(
                name="ir.backtest_report", version="1.0"
            )
            assert oversized_manifest.canon is not None
            assert oversized_manifest.canon.forbid_floats is False
            assert artifact_manifest_profile_sha256(oversized_manifest) == (
                oversized_ref.manifest_profile_sha256
            )
            assert store.verify(oversized_ref).ok
            oversized_bytes = store.get_bytes(oversized_ref)
            assert len(oversized_bytes) > 2_000_000
            loaded_oversized_report = load_backtest_report(
                _ensure_ir_artifact_store(store),
                BacktestReportRef.model_validate(oversized_ref.model_dump(mode="json")),
            )
            assert loaded_oversized_report.metadata["fixture_note"] == "x" * 2_000_001
            _record_fixture_owner(
                store,
                wrong_kind_ref,
                wrong_media_ref,
                wrong_schema_ref,
                oversized_ref,
                tenant_id=env["tenant_a"],
                cell_id=env["cell_a"],
                runtime_api_env=env,
            )

            denial_boundary = _runtime_fixture_authority_boundary(
                boundary_id="boundary-frc-diagnostic-dashboard-denial"
            )
            denial_boundary["may_not_use_for"] = ["claim_authority", "dashboard_display"]
            denial_envelope_ref = _put_fixture_authority_envelope(
                store,
                denial_boundary,
                producer_version="frc-diagnostic-dashboard-denial-v1",
            )
            denied_ref = _put_json(
                store,
                json.loads(report_bytes),
                kind="ir.backtest_report",
                schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
                authority=ArtifactAuthorityInfo(
                    authority_envelope_ref=str(denial_envelope_ref.artifact_id),
                    authority_envelope_manifest_profile_sha256=(
                        denial_envelope_ref.manifest_profile_sha256
                    ),
                    diagnostic_event_ref="event://tests/frc-02/dashboard-denial",
                    manifest_ref=f"cas-manifest://{report_refs[0].artifact_id}",
                    payload_sha256=hashlib.sha256(report_bytes).hexdigest(),
                ),
            )
            assert denied_ref.artifact_id == report_refs[0].artifact_id
            assert denied_ref.manifest_profile_sha256 != report_refs[0].manifest_profile_sha256
            _record_fixture_owner(
                store,
                denied_ref,
                denial_envelope_ref,
                tenant_id=env["tenant_a"],
                cell_id=env["cell_a"],
                runtime_api_env=env,
            )

            malformed_payload = json.loads(report_bytes.decode("utf-8"))
            malformed_scenario = malformed_payload["scenarios"][0]
            malformed_scenario["interval_hit_count"] = (
                malformed_scenario["interval_evaluated_count"] + 1
            )
            malformed_ref = store.put_json(
                malformed_payload,
                PutOptions(
                    kind="ir.backtest_report",
                    media_type="application/json",
                    schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            malformed_ref = profile_bound_ref(store, malformed_ref)
            missing_count_payload = json.loads(report_bytes.decode("utf-8"))
            del missing_count_payload["scenarios"][0]["interval_evaluated_count"]
            missing_count_ref = store.put_json(
                missing_count_payload,
                PutOptions(
                    kind="ir.backtest_report",
                    media_type="application/json",
                    schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            missing_count_ref = profile_bound_ref(store, missing_count_ref)

            missing_row_payload = json.loads(report_bytes.decode("utf-8"))
            missing_row_payload["scenarios"][0]["outcome_comparisons"].pop()
            missing_row_ref = store.put_json(
                missing_row_payload,
                PutOptions(
                    kind="ir.backtest_report",
                    media_type="application/json",
                    schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            missing_row_ref = profile_bound_ref(store, missing_row_ref)
            duplicate_row_payload = json.loads(report_bytes.decode("utf-8"))
            duplicate_rows = duplicate_row_payload["scenarios"][0]["outcome_comparisons"]
            duplicate_rows.append(dict(duplicate_rows[0]))
            duplicate_row_ref = store.put_json(
                duplicate_row_payload,
                PutOptions(
                    kind="ir.backtest_report",
                    media_type="application/json",
                    schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            duplicate_row_ref = profile_bound_ref(store, duplicate_row_ref)

            invalid_numeric_refs: list[ArtifactRef] = []
            invalid_numeric_cases: tuple[tuple[str, object], ...] = (
                ("huge_positive_integer", 10**1000),
                ("huge_negative_integer", -(10**1000)),
                ("boolean", True),
                ("null", None),
                ("positive_infinity", float("inf")),
                ("negative_infinity", float("-inf")),
                ("not_a_number", float("nan")),
            )
            for _case_name, numeric_value in invalid_numeric_cases:
                invalid_payload = json.loads(report_bytes.decode("utf-8"))
                invalid_payload["scenarios"][0]["outcome_comparisons"][0]["y_true"] = numeric_value
                invalid_ref = store.put_json(
                    invalid_payload,
                    PutOptions(
                        kind="ir.backtest_report",
                        media_type="application/json",
                        schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
                    ),
                    canon_spec=CanonSpec(
                        forbid_floats=False,
                        forbid_nan_inf=False,
                        exclude_none=False,
                    ),
                )
                invalid_numeric_refs.append(profile_bound_ref(store, invalid_ref))

            _record_fixture_owner(
                store,
                wrong_kind_ref,
                malformed_ref,
                missing_count_ref,
                missing_row_ref,
                duplicate_row_ref,
                *invalid_numeric_refs,
                tenant_id=env["tenant_a"],
                cell_id=env["cell_a"],
                runtime_api_env=env,
            )

            wrong_response = fetch_diagnostic(wrong_kind_ref)
            assert wrong_response.status_code == 409
            assert wrong_response.json()["code"] == "predictive_coverage_source_unsupported"
            wrong_media_response = fetch_diagnostic(wrong_media_ref)
            assert wrong_media_response.status_code == 409
            assert wrong_media_response.json()["code"] == "predictive_coverage_source_unsupported"
            wrong_schema_response = fetch_diagnostic(wrong_schema_ref)
            assert wrong_schema_response.status_code == 409
            assert wrong_schema_response.json()["code"] == "predictive_coverage_source_unsupported"
            oversized_response = fetch_diagnostic(oversized_ref)
            assert oversized_response.status_code == 409
            assert oversized_response.json()["code"] == "predictive_coverage_source_unsupported"
            denied_response = fetch_diagnostic(denied_ref)
            assert denied_response.status_code == 409
            assert denied_response.json()["code"] == "authority_surface_admission_blocked"
            denied_decision = denied_response.json()["extensions"]["authority_surface_decision"]
            assert "dashboard_display" in denied_decision["may_not_use_for"]
            assert any(
                row["basis"] == "selected_manifest" and row["status"] != "allowed"
                for row in denied_decision["authority_contributors"]
            )
            for invalid_ref in (
                malformed_ref,
                missing_count_ref,
                missing_row_ref,
                duplicate_row_ref,
            ):
                invalid_response = fetch_diagnostic(invalid_ref)
                assert invalid_response.status_code == 200
                invalid_projection = invalid_response.json()
                assert invalid_projection["assessment"] == "limited"
                assert invalid_projection["measurement_status"] == "invalid_source"
                assert invalid_projection["reason_code"] == "malformed_interval_counts"
                assert invalid_projection["scenarios"] == []

            for (case_name, _), invalid_numeric_ref in zip(
                invalid_numeric_cases, invalid_numeric_refs, strict=True
            ):
                invalid_response = fetch_diagnostic(invalid_numeric_ref)
                assert invalid_response.status_code == 200, case_name
                invalid_projection = invalid_response.json()
                assert invalid_projection["assessment"] == "limited"
                assert invalid_projection["measurement_status"] == "invalid_source"
                assert invalid_projection["reason_code"] == "malformed_report_shape"
                assert invalid_projection["scenarios"] == []

            blob_path, default_manifest_path = store._paths(report_refs[0].artifact_id)
            selected_manifest_path = store._manifest_path_for_ref(
                report_refs[0].artifact_id,
                report_refs[0].manifest_profile_sha256,
            )
            original_blob = blob_path.read_bytes()
            for selected_profile in (False, True):
                try:
                    blob_path.write_bytes(original_blob + b" ")
                    integrity_response = fetch_diagnostic(
                        report_refs[0],
                        selected_profile=selected_profile,
                    )
                    assert integrity_response.status_code == 409
                    assert integrity_response.json()["code"] == "artifact_integrity_failed"
                finally:
                    blob_path.write_bytes(original_blob)

            unavailable_profile_bytes = selected_manifest_path.read_bytes()
            try:
                selected_manifest_path.unlink()
                for selected_profile in (False, True):
                    unavailable_profile_response = fetch_diagnostic(
                        report_refs[0],
                        selected_profile=selected_profile,
                    )
                    assert unavailable_profile_response.status_code == 404
                    assert (
                        unavailable_profile_response.json()["code"]
                        == "artifact_manifest_profile_not_found"
                    )
            finally:
                selected_manifest_path.write_bytes(unavailable_profile_bytes)

            missing_members = {blob_path, default_manifest_path, selected_manifest_path}
            saved_members = {path: path.read_bytes() for path in missing_members}
            try:
                for path in missing_members:
                    path.unlink()
                for selected_profile in (False, True):
                    absent_response = fetch_diagnostic(
                        report_refs[0],
                        selected_profile=selected_profile,
                    )
                    assert absent_response.status_code == 404
                    assert absent_response.json()["code"] == "artifact_not_found"
            finally:
                for path, payload in saved_members.items():
                    path.write_bytes(payload)
    finally:
        if original_context_override is None:
            app.dependency_overrides.pop(get_runtime_api_context, None)
        else:
            app.dependency_overrides[get_runtime_api_context] = original_context_override
        close_runtime_api_env(env)


def test_real_ets_report_carries_method_rule_binding_without_inventing_bridge_evidence(
    tmp_path: Path,
) -> None:
    """The real producer preserves its binding while absent context stays blocked."""

    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    model_ref = _spec(store, kind="ir.model_spec", spec_id="frc-owner-bound-model")
    policy_ref = _spec(store, kind="ir.policy_spec", spec_id="frc-owner-bound-policy")
    result = ForecastOwner(store).run(
        _request(
            source_ref,
            rule_ref,
            report_id="frc-owner-method-rule-binding",
            model_spec_ref=str(model_ref.artifact_id),
            policy_spec_ref=str(policy_ref.artifact_id),
        )
    )

    report = load_backtest_report(_ensure_ir_artifact_store(store), result.backtest_report_ref)
    for metadata in (report.metadata, *(scenario.metadata for scenario in report.scenarios)):
        assert metadata["method_ref"] == "forecasting.univariate.exponential_smoothing"
        assert metadata["method_version"] == "1.0.0"
        assert metadata["rule_version_ref"] == RULE_ID
        assert metadata["calibration_rule_version"] == "1.0"
        assert metadata["calibration_rule_ref"]["artifact_id"] == str(rule_ref.artifact_id)
    manifest = store.get_manifest(result.backtest_report_ref.artifact_id)
    assert (str(rule_ref.artifact_id), "calibration_rule") in {
        (str(item.artifact_id), item.role) for item in manifest.inputs
    }

    # A matching shape and version cannot establish an evaluation owner, its
    # credible-evaluation evidence, or a calibrated S10 purpose.  The canonical
    # consumer still recomputes useful row arithmetic from the actual report.
    evidence = produce_empirical_calibration_evidence(store, result.backtest_report_ref)
    assert evidence.recomputed_numerator == result.numerator
    assert evidence.recomputed_denominator == result.denominator
    assert evidence.recomputed_pass_rate == pytest.approx(result.empirical_coverage)
    assert evidence.empirical_observations_available is False
    assert evidence.failure_codes == (
        "backtest_source_not_established",
        "explicit_context_missing",
    )
    assert evidence.context_bound is False
    assert evidence.usable_for_calibration is False
    assert evidence.floor_passed is False
    assert result.bridge_status == "bridge_pending"
    assert evidence.authority_scope == "predictive_only"
    assert "s10_authority" in evidence.may_not_use_for
    before_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}
    with pytest.raises(ValueError, match="blocked empirical calibration evidence"):
        persist_empirical_calibration_evidence(store, evidence)
    assert {str(artifact_id) for artifact_id in store.iter_artifact_ids()} == before_ids


def test_owner_rejects_incomplete_or_same_model_policy_pair_and_duplicate_inputs(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    duplicate = InputRef(
        artifact_id=str(source_ref.artifact_id),
        role="observed_source",
    )

    payload = _request(source_ref, rule_ref, report_id="frc-owner-partial").model_dump(
        mode="python"
    )
    payload["model_spec_ref"] = str(source_ref.artifact_id)
    with pytest.raises(ValueError, match="model/policy"):
        ForecastOwnerRequest.model_validate(payload)

    payload = _request(source_ref, rule_ref, report_id="frc-owner-complete").model_dump(
        mode="python"
    )
    payload["model_spec_ref"] = str(source_ref.artifact_id)
    payload["policy_spec_ref"] = str(source_ref.artifact_id)
    with pytest.raises(ValueError, match="distinct"):
        ForecastOwnerRequest.model_validate(payload)

    with pytest.raises(ValueError, match="duplicate"):
        _request(
            source_ref,
            rule_ref,
            report_id="frc-owner-duplicate-input",
            manifest_inputs=(duplicate, duplicate),
        )


def test_owner_rejects_subfloor_effective_ets_parameter(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    payload = _request(source_ref, rule_ref, report_id="frc-owner-subfloor").model_dump(
        mode="python"
    )
    payload["method_params"]["alpha"] = 1e-7

    with pytest.raises(ValidationError) as exc_info:
        ForecastOwnerRequest.model_validate(payload)
    matching_errors = [
        error
        for error in exc_info.value.errors()
        if error["loc"] == ("method_params", "alpha") and error["type"] == "greater_than_equal"
    ]
    assert matching_errors
    assert matching_errors[0]["ctx"]["ge"] == 1e-6


@pytest.mark.parametrize(
    ("payload_updates", "kind"),
    [
        ({"rule_version": "9.0"}, RULE_KIND),
        ({"algorithm": "other_algorithm"}, RULE_KIND),
        ({"unexpected": True}, RULE_KIND),
        ({}, "test.forecast.calibration_rule"),
    ],
)
def test_owner_rejects_unadmitted_calibration_rule(
    tmp_path: Path,
    payload_updates: dict[str, object],
    kind: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store, payload_updates=payload_updates, kind=kind)

    with pytest.raises(ValueError, match=r"calibration rule|artifact kind"):
        ForecastOwner(store).run(_request(source_ref, rule_ref, report_id="frc-owner-invalid-rule"))


def test_owner_rejects_naive_or_collapsed_temporal_roles(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    roles = _temporal_roles().model_dump(mode="python")
    roles["observation_time"] = datetime(2026, 1, 1)

    payload = _request(source_ref, rule_ref, report_id="frc-owner-naive").model_dump(mode="python")
    payload["temporal_roles"] = roles
    with pytest.raises(ValueError, match=r"timezone|distinct"):
        ForecastOwnerRequest.model_validate(payload)
