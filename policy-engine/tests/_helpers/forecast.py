"""Shared admitted synthetic ETS source and configured calibration profile."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.calibration import ForecastCalibrationProfile
from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.fabric import DataSchema
from polisyos.ir.artifacts import normalize_artifact_ref, put_json_artifact
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.methods.backtesting.forecast_owner import (
    ForecastOwnerRequest,
    persist_forecast_owner_request,
)


def configured_forecast_request(
    store: FileSystemCAS, holdout: list[float]
) -> tuple[ForecastOwnerRequest, ArtifactRefModel]:
    """Persist one synthetic typed ETS source, request, rule, and candidate profile.

    This declared predictive fixture supplies known rows and separate time roles;
    it supplies no production history, profile issuer, or verifier authority.
    """

    def put(payload: object, kind: str):
        return store.put_json(
            payload,
            PutOptions(kind=kind, media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )

    data = put({"metric": [float(i) for i in range(1, 31)] + holdout}, "test.observed")
    schema = put_json_artifact(
        store,
        DataSchema(
            schema_id="test.forecast",
            version="1.0",
            fields=[{"name": "metric", "data_type": "float64", "unit": "count"}],
        ).model_dump(mode="json"),
        kind="fabric.data_schema",
        schema_name="polisyos.fabric.DataSchema",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    source = put(
        DataSnapshot(data_ref=data, data_schema_ref=schema).model_dump(mode="json"),
        "fabric.data_snapshot",
    )
    rule = put(
        {
            "schema_version": "1.0",
            "rule_id": "rolling-origin-residual-conformal.v1",
            "rule_version": "1.0",
            "estimand": "predictive_interval_coverage",
            "algorithm": "rolling_origin_residual_conformal",
            "nominal_coverage": 0.9,
        },
        "ir.forecast_calibration_rule",
    )
    model = put({"spec_id": "model-ets"}, "ir.model_spec")
    policy = put({"spec_id": "policy-ets"}, "ir.policy_spec")
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    request = ForecastOwnerRequest(
        observed_source_ref=DataSnapshotRef(artifact_id=source.artifact_id),
        split={
            "train_start": 0,
            "train_end": 30,
            "holdout_start": 30,
            "holdout_end": 30 + len(holdout),
            "horizon": len(holdout),
        },
        target_metric="metric",
        target_unit="count",
        target_scale="source_native",
        method_params={"horizon": len(holdout)},
        report_id="configured-ets-report",
        calibration_rule={
            "rule_id": "rolling-origin-residual-conformal.v1",
            "artifact_ref": normalize_artifact_ref(rule),
        },
        temporal_roles=dict(
            zip(
                (
                    "data_valid_time",
                    "calibration_window_start",
                    "calibration_window_end",
                    "policy_effective_time",
                    "prediction_time",
                    "observation_time",
                ),
                (origin + timedelta(days=i) for i in range(6)),
                strict=True,
            )
        ),
        model_spec_ref=model.artifact_id,
        policy_spec_ref=policy.artifact_id,
        seed=17,
    )
    request_ref = persist_forecast_owner_request(store, request)
    profile = ForecastCalibrationProfile(
        profile_id="linear-ets",
        profile_version="1.0",
        request_ref=request_ref,
        calibration_threshold=0.8,
    )
    profile_ref = ArtifactRefModel.model_validate(
        put_json_artifact(
            store,
            profile.model_dump(mode="json"),
            kind="ir.forecast_calibration_profile",
            schema_name="polisyos.calibration.forecast_calibration_profile",
            schema_version="1.0",
            inputs=[{"artifact_id": str(request_ref.artifact_id), "role": "forecast_request"}],
            canon_spec=CanonSpec(forbid_floats=False),
        )
    )
    return request, profile_ref
