"""CAS-backed owner test for the selected EMP-01 profile/member bridge."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import FileSystemCAS, ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
from polisyos.core.contracts import DataSnapshot, DataSnapshotRef, ForecastProfileMemberV1
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ActivatedAcquisitionObservationProjection,
    CanonicalAcquisitionObservation,
    ObservationProvenanceClass,
)
from polisyos.ir import (
    ArtifactRefModel,
    InputRef,
    get_json_artifact,
    load_backtest_report,
    normalize_artifact_ref,
    put_json_artifact,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.pdc._impl.gy_waist import gy_content_hash
from polisyos.runtime.quality.forecast_profile_binding import (
    join_profile_member_to_observed_series,
    validate_profile_projection_binding,
)
from polisyos.runtime.quality.generation_cycle import ValueDataProfile, ValueOwnerRow
from polisyos.scientist.methods.backtesting.forecast_owner import (
    ForecastOwner,
    ForecastOwnerRequest,
)
from tests.unit.data_forge.domains.catalog.knowledge.test_overlay import (
    _scenario_with_raw_rows,
)
from tests.unit.remediation.test_frc_02_owner import (
    _put_json,
    _request,
    _rule,
    _source,
)
from tests.unit.runtime.quality.test_acquisition_executor import (
    _activate_real_epoch_scenario,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.manifest import ArtifactRef


def _to_ir_artifact_ref(ref: CoreArtifactRef) -> ArtifactRefModel:
    """Preserve a Core ref's exact selected view across the typed IR boundary."""
    return ArtifactRefModel.model_validate(normalize_artifact_ref(ref))


def _cas_profile(
    store: FileSystemCAS, *, forged_source_row: bool = False
) -> tuple[
    ArtifactRefModel,
    list[float],
    ArtifactRefModel,
    ActivatedAcquisitionObservationProjection,
]:
    values = [float(index + 1) for index in range(34)]
    observations: list[CanonicalAcquisitionObservation] = []
    profile_rows: list[ValueOwnerRow] = []
    for unit_index, unit_id in enumerate(("UA", "PL", "RO")):
        for period_id in range(34):
            value = float(period_id + 1 + unit_index)
            observation = CanonicalAcquisitionObservation(
                observation_id=f"fixture-{unit_id}-{period_id}",
                dataset_id="controlled.forecast-profile",
                raw_variable="metric",
                canonical_var="metric",
                country_code=unit_id,
                year=period_id,
                value=value,
                condition_json='{"unit":"synthetic index"}',
                acquisition_method="controlled_fixture",
                source_watermark="controlled_fixture",
                dataset_version="fixture-v1",
                observation_class=ObservationProvenanceClass.OBSERVED,
            )
            observations.append(observation)
            source_hash = gy_content_hash(
                {
                    "outcome": "metric",
                    "unit_id": unit_id,
                    "period_id": period_id,
                    "value": value,
                    "dataset_id": observation.dataset_id,
                    "observation_id": observation.observation_id,
                    "measurement_unit": "synthetic index",
                }
            )
            if forged_source_row and unit_id == "UA" and period_id == 0:
                source_hash = gy_content_hash({"forged": "not-in-projection"})
            row_fields = {
                "unit_id": unit_id,
                "period_id": period_id,
                "outcome_value": value,
                "measurement_unit": "synthetic index",
                "source_row_content_hashes": (source_hash,),
            }
            profile_rows.append(
                ValueOwnerRow(
                    **row_fields,
                    row_content_hash=gy_content_hash(row_fields),
                )
            )
    projection = ActivatedAcquisitionObservationProjection.issue(
        receipt_ref=CoreArtifactRef(
            artifact_id="sha256:" + "1" * 64,
            kind="epoch.activated_overlay_admission_receipt",
            media_type="application/json",
        ),
        receipt_content_sha256="sha256:" + "2" * 64,
        passport_ref=CoreArtifactRef(
            artifact_id="sha256:" + "3" * 64,
            kind="epoch.acquisition_passport_snapshot",
            media_type="application/json",
        ),
        passport_content_sha256="sha256:" + "4" * 64,
        variable_id="metric",
        epoch_id=1,
        passport_id="fixture-passport",
        admission_content_sha256="sha256:" + "5" * 64,
        observations=observations,
    )
    ir_store = ensure_ir_artifact_store(store)
    projection_ref = ArtifactRefModel.model_validate(
        put_json_artifact(
            ir_store,
            projection.model_dump(mode="json"),
            kind="runtime.value_owner_source_projection",
            schema_name="runtime.value_owner_source_projection.v1",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    )
    rows_payload = tuple(row.model_dump(mode="json") for row in profile_rows)
    profile_payload = {
        "schema_version": "policyos.runtime.value_data_profile.v2",
        "outcome": "metric",
        "measurement_unit": "synthetic index",
        "rows": rows_payload,
        "owner_row_count": len(rows_payload),
        "unit_count": 3,
        "period_count": 34,
        "available_data_modalities": ("panel", "tabular"),
        "treatment_assignment_status": "owner_assignment_unresolved",
        "owner_access_ref": "controlled://test-forecast-profile",
        "owner_rows_content_hash": gy_content_hash(rows_payload),
    }
    profile = ValueDataProfile.model_validate(
        {**profile_payload, "content_hash": gy_content_hash(profile_payload)}
    )
    profile_ref = ArtifactRefModel.model_validate(
        put_json_artifact(
            ir_store,
            profile.model_dump(mode="json"),
            kind="runtime.value_data_profile",
            schema_name="runtime.value_data_profile.v2",
            schema_version="2.0",
            inputs=[
                InputRef(
                    artifact_id=projection_ref.artifact_id,
                    role="activated_source_projection",
                    manifest_profile_sha256=projection_ref.manifest_profile_sha256,
                )
            ],
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    )
    return profile_ref, values, projection_ref, projection


def _request_with_profile(
    store: FileSystemCAS,
    source_ref: DataSnapshotRef,
    rule_ref: ArtifactRef,
    profile_ref: ArtifactRefModel,
    projection_ref: ArtifactRefModel,
    projection: ActivatedAcquisitionObservationProjection,
    *,
    unit_id: str,
) -> ForecastOwnerRequest:
    manifest = store.get_manifest(profile_ref)
    projection_inputs = [
        item for item in manifest.inputs if item.role == "activated_source_projection"
    ]
    if len(projection_inputs) != 1:
        raise ValueError("selected profile lacks one source-owner projection edge")
    input_ref = ArtifactRefModel(
        artifact_id=projection_inputs[0].artifact_id,
        kind="runtime.value_owner_source_projection",
        media_type="application/json",
        manifest_profile_sha256=projection_inputs[0].manifest_profile_sha256,
    )
    if input_ref != projection_ref:
        raise ValueError("selected profile projection edge does not match fixture")
    profile_payload = get_json_artifact(ensure_ir_artifact_store(store), profile_ref)
    profile = ValueDataProfile.model_validate(profile_payload)
    projection = validate_profile_projection_binding(
        profile=profile,
        projection_payload=projection.model_dump(mode="json"),
    )
    observed_source_ref = _to_ir_artifact_ref(source_ref)
    snapshot_payload = get_json_artifact(ensure_ir_artifact_store(store), observed_source_ref)
    snapshot = DataSnapshot.model_validate(snapshot_payload)
    observed_data_ref = _to_ir_artifact_ref(snapshot.data_ref)
    observed_payload = get_json_artifact(ensure_ir_artifact_store(store), observed_data_ref)
    member, _values = join_profile_member_to_observed_series(
        profile=profile,
        profile_ref=profile_ref,
        source_projection_ref=projection_ref,
        projection=projection,
        observed_source_ref=observed_source_ref,
        observed_data_ref=observed_data_ref,
        target_metric="metric",
        unit_id=unit_id,
        observed_values=observed_payload["metric"],
    )
    base = _request(source_ref, rule_ref, report_id=f"profile-owner-{unit_id}")
    payload = base.model_dump(mode="python")
    payload["value_data_profile_ref"] = profile_ref
    payload["value_data_unit_id"] = unit_id
    payload["forecast_profile_member"] = member
    return ForecastOwnerRequest.model_validate(payload)


def _profile_artifacts_from_real_owner(
    store: FileSystemCAS,
    profile: ValueDataProfile,
    projection: object,
) -> tuple[ArtifactRefModel, ArtifactRefModel]:
    ir_store = ensure_ir_artifact_store(store)
    projection_ref = ArtifactRefModel.model_validate(
        put_json_artifact(
            ir_store,
            projection.model_dump(mode="json"),
            kind="runtime.value_owner_source_projection",
            schema_name="runtime.value_owner_source_projection.v1",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    )
    profile_ref = ArtifactRefModel.model_validate(
        put_json_artifact(
            ir_store,
            profile.model_dump(mode="json"),
            kind="runtime.value_data_profile",
            schema_name="runtime.value_data_profile.v2",
            schema_version="2.0",
            inputs=[
                InputRef(
                    artifact_id=projection_ref.artifact_id,
                    role="activated_source_projection",
                    manifest_profile_sha256=projection_ref.manifest_profile_sha256,
                )
            ],
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    )
    return profile_ref, projection_ref


def test_owner_preserves_profileless_legacy_result_when_profile_pair_is_absent(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    request = _request(
        source_ref,
        rule_ref,
        report_id="profile-owner-legacy-no-profile",
    )

    assert request.value_data_profile_ref is None
    assert request.value_data_unit_id is None
    assert request.forecast_profile_member is None

    result = ForecastOwner(store).run(request)
    assert result.value_data_profile_ref is None
    assert result.forecast_profile_member_ref is None
    assert result.authority_scope == "predictive_only"
    assert result.bridge_status == "bridge_pending"

    ir_store = ensure_ir_artifact_store(store)
    diagnostics = get_json_artifact(ir_store, result.calibration_diagnostics_ref)
    assert diagnostics["metadata"]["profile_join_status"] == "profileless_legacy"
    assert "value_data_profile_ref" not in diagnostics["metadata"]
    assert "forecast_profile_member_ref" not in diagnostics["metadata"]
    diagnostic_manifest = store.get_manifest(result.calibration_diagnostics_ref)
    assert not any(
        edge.role in {"value_data_profile", "forecast_profile_member"}
        for edge in diagnostic_manifest.inputs
    )

    report = load_backtest_report(ir_store, result.backtest_report_ref)
    assert report.metadata["profile_join_status"] == "profileless_legacy"
    assert "value_data_profile_ref" not in report.metadata
    assert "forecast_profile_member_ref" not in report.metadata
    report_manifest = store.get_manifest(result.backtest_report_ref)
    assert not any(
        edge.role in {"value_data_profile", "forecast_profile_member"}
        for edge in report_manifest.inputs
    )


def test_owner_request_rejects_incomplete_present_profile_member_pairs(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    profile_ref, _values, projection_ref, projection = _cas_profile(store)
    valid_request = _request_with_profile(
        store,
        source_ref,
        rule_ref,
        profile_ref,
        projection_ref,
        projection,
        unit_id="UA",
    )
    before_artifacts = {str(item) for item in store.iter_artifact_ids()}
    valid_payload = valid_request.model_dump(mode="python")

    missing_member = {
        **valid_payload,
        "forecast_profile_member": None,
    }
    with pytest.raises(ValueError, match="selected value profile member receipt is incomplete"):
        ForecastOwnerRequest.model_validate(missing_member)

    member_without_profile = {
        **valid_payload,
        "value_data_profile_ref": None,
        "value_data_unit_id": None,
    }
    with pytest.raises(
        ValueError, match="profile member receipt requires an exact selected profile"
    ):
        ForecastOwnerRequest.model_validate(member_without_profile)

    assert {str(item) for item in store.iter_artifact_ids()} == before_artifacts


def test_owner_consumes_exact_prebound_profile_member_receipt_and_report_edges(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(
        store, holdout=[31.0, 32.0, 33.0, 34.0], training=[float(i) for i in range(1, 31)]
    )
    rule_ref = _rule(store)
    profile_ref, selected_values, projection_ref, projection = _cas_profile(store)

    result = ForecastOwner(store).run(
        _request_with_profile(
            store,
            source_ref,
            rule_ref,
            profile_ref,
            projection_ref,
            projection,
            unit_id="UA",
        )
    )

    assert result.authority_scope == "predictive_only"
    assert result.value_data_profile_ref == profile_ref
    assert result.forecast_profile_member_ref is not None
    assert result.forecast_profile_member_ref.kind == "runtime.forecast_profile_member"
    member_payload = get_json_artifact(
        ensure_ir_artifact_store(store), result.forecast_profile_member_ref
    )
    member = ForecastProfileMemberV1.model_validate(member_payload)
    assert member.profile_ref == profile_ref
    assert member.source_projection_ref == projection_ref
    assert member.observed_source_ref == ArtifactRefModel(
        artifact_id=source_ref.artifact_id,
        kind=source_ref.kind,
        media_type=source_ref.media_type,
        manifest_profile_sha256=source_ref.manifest_profile_sha256,
    )
    assert member.unit_id == "UA"
    assert member.period_ids == tuple(range(34))
    assert member.row_count == len(selected_values)
    assert member.population_scope_status == "not_established"
    assert member.completeness_status == "not_established"
    assert member.source_time_status == "not_established"
    assert member.source_relation_status == "not_established"
    assert member.treatment_assignment_status == "owner_assignment_unresolved"

    report_manifest = store.get_manifest(result.backtest_report_ref)
    for ref, role in (
        (profile_ref, "value_data_profile"),
        (result.forecast_profile_member_ref, "forecast_profile_member"),
    ):
        assert any(
            str(edge.artifact_id) == str(ref.artifact_id)
            and edge.role == role
            and edge.manifest_profile_sha256 == ref.manifest_profile_sha256
            for edge in report_manifest.inputs
        )


def test_owner_consumes_real_value_profile_producer_output_and_persists_candidate_join(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from polisyos.runtime.quality import data_state_substrate, substrate_registry
    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

    rows = [
        {
            "country_code": "UA",
            "year": period_id,
            "distress_score": 0.10 + 0.01 * period_id,
            "condition_json": {"unit": "synthetic index"},
        }
        for period_id in range(34)
    ]
    scenario = _scenario_with_raw_rows(tmp_path / "source", monkeypatch, rows)
    try:
        _production, activated = _activate_real_epoch_scenario(scenario)
        projection = scenario.overlay.read_activated_semantic_epoch_observations(
            receipt_ref=activated.receipt_ref,
            artifact_store=scenario.store,
            passport=scenario.passport,
            authority=scenario.authority,
        )
        paths = SimpleNamespace(l1_dcat_path=scenario.authority.baseline_path)
        monkeypatch.setattr(
            data_state_substrate,
            "default_substrate_catalog_paths",
            lambda _repo_root, **_kwargs: paths,
        )
        monkeypatch.setattr(
            substrate_registry,
            "default_substrate_catalog_paths",
            lambda _repo_root, **_kwargs: paths,
        )
        outcome = scenario.passport.variable_id
        candidate = SimpleNamespace(
            atom=SimpleNamespace(target_world_slots=(outcome,)),
        )
        problem = SimpleNamespace(
            outcome_of_interest=SimpleNamespace(target_variable=outcome),
            jurisdiction_time=SimpleNamespace(region="UA"),
        )
        profile = RealValueOwnerGateway(
            repo_root=scenario.authority.repo_root,
            catalog_overlay_path=scenario.overlay.overlay_path,
            artifact_store=scenario.store,
            activated_observation_projection=projection,
        ).load_value_data_profile(
            candidate=candidate,
            problem=problem,
            world_record=object(),
        )
        selected_unit = profile.rows[0].unit_id
        selected_rows = sorted(
            (row for row in profile.rows if row.unit_id == selected_unit),
            key=lambda row: row.period_id,
        )
        observed_values = [row.outcome_value for row in selected_rows]
        assert len(observed_values) == 34

        data_ref = _put_json(
            scenario.store,
            {outcome: observed_values},
            kind="test.forecast.observed_data",
        )
        snapshot = DataSnapshot(
            data_ref=data_ref,
            stats={"rows": len(observed_values), "source": "controlled_profile_test"},
        )
        snapshot_ref = _put_json(
            scenario.store,
            snapshot.model_dump(mode="json"),
            kind="fabric.data_snapshot",
        )
        source_ref = DataSnapshotRef(
            artifact_id=snapshot_ref.artifact_id,
            kind=snapshot_ref.kind,
            media_type=snapshot_ref.media_type,
            manifest_profile_sha256=snapshot_ref.manifest_profile_sha256,
        )
        rule_ref = _rule(scenario.store)
        request = _request(
            source_ref,
            rule_ref,
            report_id="profile-owner-real-emp01",
            train_end=30,
            horizon=4,
        )
        request_payload = request.model_dump(mode="python")
        profile_ref, projection_ref = _profile_artifacts_from_real_owner(
            scenario.store, profile, projection
        )
        selected_projection = validate_profile_projection_binding(
            profile=profile,
            projection_payload=projection.model_dump(mode="json"),
        )
        member, _joined_values = join_profile_member_to_observed_series(
            profile=profile,
            profile_ref=profile_ref,
            source_projection_ref=projection_ref,
            projection=selected_projection,
            observed_source_ref=_to_ir_artifact_ref(source_ref),
            observed_data_ref=_to_ir_artifact_ref(data_ref),
            target_metric=outcome,
            unit_id=selected_unit,
            observed_values=observed_values,
        )
        request_payload.update(
            target_metric=outcome,
            value_data_profile_ref=profile_ref,
            value_data_unit_id=selected_unit,
            forecast_profile_member=member,
        )

        result = ForecastOwner(scenario.store).run(
            ForecastOwnerRequest.model_validate(request_payload)
        )

        assert result.value_data_profile_ref is not None
        assert result.value_data_profile_ref.kind == "runtime.value_data_profile"
        assert result.forecast_profile_member_ref is not None
        report = load_backtest_report(
            ensure_ir_artifact_store(scenario.store), result.backtest_report_ref
        )
        assert report.metadata["profile_join_status"] == "joined_candidate"
        assert report.metadata["value_data_profile_ref"] == (
            result.value_data_profile_ref.model_dump(mode="json")
        )
        member_payload = get_json_artifact(
            ensure_ir_artifact_store(scenario.store),
            result.forecast_profile_member_ref,
        )
        member = ForecastProfileMemberV1.model_validate(member_payload)
        assert member.unit_id == selected_unit
        assert member.outcome == outcome
        assert member.measurement_unit == "synthetic index"
        assert member.observed_source_ref == ArtifactRefModel(
            artifact_id=source_ref.artifact_id,
            kind=source_ref.kind,
            media_type=source_ref.media_type,
            manifest_profile_sha256=source_ref.manifest_profile_sha256,
        )
        assert member.observed_data_ref == ArtifactRefModel(
            artifact_id=data_ref.artifact_id,
            kind=data_ref.kind,
            media_type=data_ref.media_type,
            manifest_profile_sha256=data_ref.manifest_profile_sha256,
        )
        assert member.authority_scope == "predictive_only"
        assert member.completeness_status == "not_established"
    finally:
        scenario.overlay.close()


def test_owner_refuses_member_drift_foreign_unit_and_profile_without_producer_edge(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(
        store, holdout=[31.0, 32.0, 33.0, 34.0], training=[float(i) for i in range(1, 31)]
    )
    rule_ref = _rule(store)
    profile_ref, _values, projection_ref, projection = _cas_profile(store)
    forged_ref, _values, forged_projection_ref, forged_projection = _cas_profile(
        store, forged_source_row=True
    )

    before = sorted(
        path.relative_to(store.root).as_posix() for path in store.root.rglob("*") if path.is_file()
    )
    with pytest.raises(ValueError, match="source_row_binding_mismatch"):
        _request_with_profile(
            store,
            source_ref,
            rule_ref,
            forged_ref,
            forged_projection_ref,
            forged_projection,
            unit_id="UA",
        )
    with pytest.raises(ValueError, match="unit_not_found"):
        _request_with_profile(
            store,
            source_ref,
            rule_ref,
            profile_ref,
            projection_ref,
            projection,
            unit_id="foreign-unit",
        )
    after = sorted(
        path.relative_to(store.root).as_posix() for path in store.root.rglob("*") if path.is_file()
    )
    assert after == before

    orphan_ref = ArtifactRefModel.model_validate(
        put_json_artifact(
            ensure_ir_artifact_store(store),
            json.loads(store.get_bytes(profile_ref)),
            kind="runtime.value_data_profile",
            schema_name="runtime.value_data_profile.v2",
            schema_version="2.0",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    )
    with pytest.raises(ValueError, match="source-owner projection edge"):
        _request_with_profile(
            store,
            source_ref,
            rule_ref,
            orphan_ref,
            projection_ref,
            projection,
            unit_id="UA",
        )
