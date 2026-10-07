"Independent bounded FRC oracle: source-admitted native ETS and fresh CAS."

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from polisyos.calibration.forecast_bridge import (
    EmpiricalCalibrationEvidence,
    ForecastCalibrationProfile,
    ForecastCandidateReceipt,
    load_empirical_calibration_evidence,
    load_forecast_candidate_receipt,
)
from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.fabric import DataSchema
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.analytics.forecasting_uncertainty import load_forecasting_uncertainty_bundle
from polisyos.ir.artifacts import get_json_artifact, normalize_artifact_ref, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.methods.backtesting.forecast_owner import (
    ForecastOwner,
    ForecastOwnerRequest,
    persist_forecast_owner_request,
)

ARTIFACTS = []


def put(
    store: object,
    payload: object,
    kind: str,
    schema_name: str | None = None,
    schema_version: str = "1.0",
    inputs: object = (),
) -> object:
    if schema_name:
        return ArtifactRefModel.model_validate(
            put_json_artifact(
                store,
                payload,
                kind=kind,
                schema_name=schema_name,
                schema_version=schema_version,
                inputs=list(inputs),
                canon_spec=CanonSpec(forbid_floats=False),
            )
        )
    return ArtifactRefModel.model_validate(
        normalize_artifact_ref(
            store.put_json(
                payload,
                PutOptions(kind=kind, media_type="application/json"),
                canon_spec=CanonSpec(forbid_floats=False),
            )
        )
    )


def configured(
    root: object, *, misses: object = False, nominal: object = 0.95
) -> tuple[object, ...]:
    store = FileSystemCAS(root)
    # By induction, exact Holt level at t is 11+2t and trend is 2,
    # hence forecasts for t=32..36 are 75,77,79,81,83. Every rolling
    # origin residual is zero, so its conformal absolute-error quantile is 0.
    train = [float(11 + 2 * t) for t in range(32)]
    expected = [float(11 + 2 * t) for t in range(32, 37)]
    observed = [x + 100 for x in expected] if misses else expected
    data = put(store, {"revenue": train + observed}, "test.independent.observed")
    schema = put(
        store,
        DataSchema(
            schema_id="independent.frc.revenue",
            version="2.1",
            fields=[{"name": "revenue", "data_type": "float64", "unit": "count"}],
        ).model_dump(mode="json"),
        "fabric.data_schema",
        "polisyos.fabric.DataSchema",
    )
    source = put(
        store,
        DataSnapshot(data_ref=data, data_schema_ref=schema).model_dump(mode="json"),
        "fabric.data_snapshot",
    )
    rule = put(
        store,
        {
            "schema_version": "1.0",
            "rule_id": "rolling-origin-residual-conformal.v1",
            "rule_version": "1.0",
            "estimand": "predictive_interval_coverage",
            "algorithm": "rolling_origin_residual_conformal",
            "nominal_coverage": nominal,
        },
        "ir.forecast_calibration_rule",
    )
    model = put(store, {"spec_id": "independent-model-ets"}, "ir.model_spec")
    policy = put(store, {"spec_id": "independent-policy-ets"}, "ir.policy_spec")
    origin = datetime(2026, 8, 17, tzinfo=UTC)
    roles = (
        "data_valid_time",
        "calibration_window_start",
        "calibration_window_end",
        "policy_effective_time",
        "prediction_time",
        "observation_time",
    )
    request = ForecastOwnerRequest(
        observed_source_ref=DataSnapshotRef(artifact_id=source.artifact_id),
        split={
            "train_start": 0,
            "train_end": 32,
            "holdout_start": 32,
            "holdout_end": 37,
            "horizon": 5,
        },
        target_metric="revenue",
        target_unit="count",
        target_scale="source_native",
        method_params={"horizon": 5, "alpha": 0.4, "beta": 0.2},
        report_id="independent-revenue-ets",
        calibration_rule={"rule_id": "rolling-origin-residual-conformal.v1", "artifact_ref": rule},
        temporal_roles={name: origin + timedelta(days=i) for i, name in enumerate(roles)},
        model_spec_ref=model.artifact_id,
        policy_spec_ref=policy.artifact_id,
        seed=20261009,
    )
    request_ref = persist_forecast_owner_request(store, request)
    profile = ForecastCalibrationProfile(
        profile_id="independent-frc",
        profile_version="2.1",
        request_ref=request_ref,
        calibration_threshold=0.9,
    )
    profile_ref = put(
        store,
        profile.model_dump(mode="json"),
        "ir.forecast_calibration_profile",
        "polisyos.calibration.forecast_calibration_profile",
        inputs=[{"artifact_id": str(request_ref.artifact_id), "role": "forecast_request"}],
    )
    return store, request, profile_ref, expected


def run_case(root: object, **kwargs: object) -> tuple[object, ...]:
    store, request, profile, expected = configured(root, **kwargs)
    result = ForecastOwner(store, empirical_profile_ref=profile).run(request)
    fresh = FileSystemCAS(root)
    receipt = load_forecast_candidate_receipt(fresh, result.candidate_receipt_ref)
    evidence = load_empirical_calibration_evidence(fresh, receipt.empirical_evidence_ref)
    ARTIFACTS.append(
        {
            "cas": str(root),
            "request": request.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
            "evidence": evidence.model_dump(mode="json"),
        }
    )
    return fresh, request, result, receipt, evidence, expected


@pytest.mark.parametrize("misses", [False, True])
def test_native_ets_from_source_to_fresh_intervals_independent_oracle(
    tmp_path: Path, misses: object
) -> None:
    fresh, request, result, receipt, evidence, expected = run_case(tmp_path / "cas", misses=misses)
    source = get_json_artifact(fresh, request.observed_source_ref.artifact_id)
    rows = get_json_artifact(fresh, source["data_ref"]["artifact_id"])["revenue"][32:37]
    bundle = load_forecasting_uncertainty_bundle(fresh, result.uncertainty_bundle_ref)
    intervals = sorted(bundle.prediction_interval, key=lambda item: item.horizon)
    # Expected values are induction above; neither result nor report supplies oracle.
    if not ([float(i.point) for i in intervals] == pytest.approx(expected, abs=1e-10)):
        raise AssertionError
    if not ([float(i.lower) for i in intervals] == pytest.approx(expected, abs=1e-10)):
        raise AssertionError
    if not ([float(i.upper) for i in intervals] == pytest.approx(expected, abs=1e-10)):
        raise AssertionError
    hits = sum(float(i.lower) <= y <= float(i.upper) for i, y in zip(intervals, rows, strict=True))
    if not (hits == (0 if misses else 5)):
        raise AssertionError
    if not ((evidence.recomputed_numerator, evidence.recomputed_denominator) == (hits, 5)):
        raise AssertionError
    if not (evidence.recomputed_pass_rate == hits / 5):
        raise AssertionError
    if not (evidence.floor_passed == (not misses)):
        raise AssertionError
    if not (
        str(result.candidate_receipt_ref.artifact_id)
        != str(result.empirical_evidence_ref.artifact_id)
    ):
        raise AssertionError
    if not (
        fresh.get_manifest(result.candidate_receipt_ref.artifact_id).kind
        == "ir.forecast_candidate_receipt"
    ):
        raise AssertionError
    if not (
        fresh.get_manifest(result.empirical_evidence_ref.artifact_id).kind
        == "ir.empirical_calibration_evidence"
    ):
        raise AssertionError
    report = load_backtest_report(fresh, evidence.report_ref)
    if not (report.trust_eligible is False and report.trust_score is None):
        raise AssertionError
    if not (
        receipt.verifier_provenance == "not_established"
        and receipt.authority_scope == "predictive_only"
    ):
        raise AssertionError
    if not (result.bridge_status == "bridge_pending"):
        raise AssertionError
    if not (result.measurement_binding.unit_id == "count"):
        raise AssertionError
    if not (result.measurement_binding.schema_version == "2.1.0"):
        raise AssertionError
    if not (
        bundle.metadata["measurement_binding"] == result.measurement_binding.model_dump(mode="json")
    ):
        raise AssertionError
    if not (len(set(request.temporal_roles.model_dump().values())) == 6):
        raise AssertionError


@pytest.mark.parametrize("nominal", [0.8, 0.95])
def test_nominal_without_changed_observations_cannot_be_empirical_coverage(
    tmp_path: Path, nominal: object
) -> None:
    _, _, _, _, evidence, _ = run_case(tmp_path / "cas", misses=True, nominal=nominal)
    if not (evidence.nominal_confidence_level == nominal):
        raise AssertionError
    if not (evidence.recomputed_pass_rate == 0 and evidence.recomputed_denominator == 5):
        raise AssertionError


@pytest.mark.parametrize(
    "defect",
    [
        "missing_schema",
        "unresolved_schema",
        "malformed_schema",
        "wrong_kind",
        "wrong_profile",
        "wrong_unit",
        "missing_unit",
        "nonnumeric_type",
        "wrong_target",
        "unsupported_scale",
        "missing_scale",
        "missing_target_unit",
        "legacy_request",
    ],
)
def test_schema_unit_scale_admission_before_numerical_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    store, request, _, _ = configured(tmp_path / "cas")
    source = get_json_artifact(store, request.observed_source_ref.artifact_id)
    schema = get_json_artifact(store, source["data_schema_ref"]["artifact_id"])
    kind = "fabric.data_schema"
    name = "polisyos.fabric.DataSchema"
    if defect == "missing_schema":
        source.pop("data_schema_ref")
    elif defect == "unresolved_schema":
        source["data_schema_ref"]["artifact_id"] = "sha256:" + "f" * 64
    elif defect == "wrong_unit":
        request = request.model_copy(update={"target_unit": "percent"})
    elif defect == "wrong_target":
        request = request.model_copy(update={"target_metric": "absent"})
    elif defect == "unsupported_scale":
        request = request.model_copy(update={"target_scale": "percent_to_ratio"})
    elif defect == "missing_scale":
        request = request.model_copy(update={"target_scale": None})
    elif defect == "missing_target_unit":
        request = request.model_copy(update={"target_unit": None})
    elif defect == "legacy_request":
        request = request.model_copy(update={"schema_version": "1.0"})
    else:
        schema["description"] = "independent-invalid-" + defect
        if defect == "malformed_schema":
            schema["fields"] = "not-a-list"
        elif defect == "wrong_kind":
            kind = "fake.schema"
        elif defect == "wrong_profile":
            name = "fake.DataSchema"
        elif defect == "missing_unit":
            schema["fields"][0].pop("unit")
        elif defect == "nonnumeric_type":
            schema["fields"][0]["data_type"] = "string"
        source["data_schema_ref"] = put(store, schema, kind, name).model_dump(mode="json")
    source_ref = put(store, source, "fabric.data_snapshot")
    request = request.model_copy(
        update={"observed_source_ref": DataSnapshotRef(artifact_id=source_ref.artifact_id)}
    )
    calls = []

    def forbidden(*args: object, **kwargs: object) -> None:
        calls.append(1)
        raise AssertionError("numeric callback escaped preflight")

    monkeypatch.setattr(MethodDispatcher, "dispatch", forbidden)
    with pytest.raises((ValueError, TypeError, KeyError, FileNotFoundError)):
        ForecastOwner(store).run(request)
    if not (calls == []):
        raise AssertionError


def test_populated_measurement_dto_does_not_replace_unit_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.scientist.methods.backtesting import forecast_owner as owner

    store, request, _, _ = configured(tmp_path / "cas")
    request = request.model_copy(update={"target_unit": "percent"})
    original = owner.resolve_forecast_measurement_binding

    def removed(store: object, **kwargs: object) -> object:
        kwargs["target_unit"] = "count"
        dto = original(store, **kwargs)
        return dto.model_copy(update={"unit_id": "percent"})

    calls = []

    def forbidden(*args: object, **kwargs: object) -> None:
        calls.append(1)
        raise AssertionError("removed equality admits populated fake DTO")

    monkeypatch.setattr(owner, "resolve_forecast_measurement_binding", removed)
    monkeypatch.setattr(MethodDispatcher, "dispatch", forbidden)
    with pytest.raises(AssertionError, match="populated fake DTO"):
        ForecastOwner(store).run(request)
    if not (calls == [1]):
        raise AssertionError  # Same preflight oracle becomes red on property removal.


def test_fresh_cas_rejects_valid_hash_false_coverage_receipt(tmp_path: Path) -> None:
    fresh, _request, result, receipt, evidence, _ = run_case(tmp_path / "cas", misses=True)
    payload = evidence.model_dump(mode="json")
    payload.update(
        recomputed_numerator=5,
        recomputed_pass_rate=1.0,
        within_ci_numerator=5,
        persisted_numerator=5,
        floor_passed=True,
        usable_for_calibration=True,
        failure_codes=[],
    )
    EmpiricalCalibrationEvidence.model_validate(payload)
    false = put(
        fresh,
        payload,
        "ir.empirical_calibration_evidence",
        "polisyos.calibration.empirical_calibration_evidence",
        "1.1",
        fresh.get_manifest(result.empirical_evidence_ref.artifact_id).inputs,
    )
    forged = ForecastCandidateReceipt.model_validate(
        {**receipt.model_dump(mode="json"), "empirical_evidence_ref": false.model_dump(mode="json")}
    )
    forged_ref = put(
        fresh,
        forged.model_dump(mode="json"),
        "ir.forecast_candidate_receipt",
        "polisyos.calibration.forecast_candidate_receipt",
        inputs=[
            {"artifact_id": str(forged.profile_ref.artifact_id), "role": "forecast_profile"},
            {"artifact_id": str(forged.request_ref.artifact_id), "role": "forecast_request"},
            {"artifact_id": str(false.artifact_id), "role": "empirical_evidence"},
        ],
    )
    with pytest.raises(ValueError, match=r"reproduced|reconciled|payload"):
        load_forecast_candidate_receipt(FileSystemCAS(tmp_path / "cas"), forged_ref)


def test_adapter_fresh_refs_time_roles_and_terminal_authority_refusal(tmp_path: Path) -> None:
    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

    fresh, request, result, _, evidence, _ = run_case(tmp_path / "cas")
    fields = result.to_s10_input_fields(FileSystemCAS(tmp_path / "cas"))
    if not (fields["empirical_calibration_evidence_ref"] == result.empirical_evidence_ref):
        raise AssertionError
    if not (fields["forecast_candidate_receipt_ref"] == result.candidate_receipt_ref):
        raise AssertionError
    if not (fields["expected_rule_version_ref"] == request.calibration_rule.rule_id):
        raise AssertionError
    if not (fields["temporal_roles"] == request.temporal_roles):
        raise AssertionError
    if not (fields["verifier_provenance"] == "not_established"):
        raise AssertionError
    inputs = RealValueOwnerGateway(
        repo_root=fresh.root,
        empirical_evidence_resolver=lambda ref: load_empirical_calibration_evidence(
            FileSystemCAS(tmp_path / "cas"), ref
        ),
    ).produce_forecast_inputs(
        candidate=SimpleNamespace(candidate_id="independent-candidate"),
        problem=SimpleNamespace(
            design_problem_id="independent-problem",
            outcome_of_interest=SimpleNamespace(target_variable="revenue"),
        ),
        world_record=SimpleNamespace(
            world_model_record_id="independent-world",
            content_hash="sha256:" + "b" * 64,
            valid_time_scope="2026-Q3",
            region_or_jurisdiction="UA",
        ),
        method_result=SimpleNamespace(output=fields, temporal_roles=request.temporal_roles),
        selected_method_fqn=request.method_fqn,
    )
    record = inputs["forecast_calibration_record"]
    if not (record.numerator == 5 and record.denominator == 5):
        raise AssertionError
    for name, value in request.temporal_roles.model_dump().items():
        if not (getattr(record, name) == value):
            raise AssertionError
    if not (
        {"causal_effect_authority", "treatment_assignment_authority", "s10_authority"}
        <= set(record.may_not_use_for)
    ):
        raise AssertionError
    # A live compatible predictive record reaches its explicit purpose boundary.
    # Changing its artifact purpose cannot admit causal/treatment authority.
    for denied in ("causal_effect", "treatment_assignment", "s10_authority"):
        with pytest.raises(ValueError, match="authority_scope"):
            EmpiricalCalibrationEvidence.model_validate(
                {**evidence.model_dump(mode="json"), "authority_scope": denied}
            )
    bad = result.model_copy(
        update={
            "temporal_roles": request.temporal_roles.model_copy(
                update={"observation_time": datetime(2020, 1, 1, tzinfo=UTC)}
            )
        }
    )
    with pytest.raises(ValueError, match="temporal roles"):
        bad.to_s10_input_fields(fresh)


def teardown_module() -> None:
    import importlib.metadata as meta
    import os
    import platform
    import sys

    origins = {
        name: str(Path(m.__file__).resolve())
        for name, m in sorted(sys.modules.items())
        if name.startswith("polisyos") and getattr(m, "__file__", None)
    }
    lane = Path(os.environ["PYTHONPATH"]).resolve()
    if not (all(Path(p).is_relative_to(lane) for p in origins.values())):
        raise AssertionError(origins)
    target = Path(os.environ["FRC_REVIEW_OUTPUT"])
    target.write_text(
        json.dumps(
            {
                "environment": {
                    "python": sys.version,
                    "executable": sys.executable,
                    "platform": platform.platform(),
                    "numpy": np.__version__,
                    "scipy": meta.version("scipy"),
                    "PYTHONPATH": os.environ["PYTHONPATH"],
                    "native_backend": "numpy",
                    "no_thread_caps": True,
                },
                "polisyos_origins": origins,
                "cases": ARTIFACTS,
            },
            indent=2,
            default=str,
        )
    )
