"""Served predictive profile intake must reopen the actual Data Forge owner."""

from __future__ import annotations

import pytest


def _persist_profile_pair(store, *, projection, profile):
    from polisyos.core.artifacts import ArtifactRef, ensure_ir_artifact_store
    from polisyos.ir import CanonSpec, InputRef, put_json_artifact

    ir_store = ensure_ir_artifact_store(store)
    projection_ref = put_json_artifact(
        ir_store,
        projection.model_dump(mode="json"),
        kind="runtime.value_owner_source_projection",
        schema_name="runtime.value_owner_source_projection.v1",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    profile_ref = put_json_artifact(
        ir_store,
        profile.model_dump(mode="json"),
        kind="runtime.value_data_profile",
        schema_name="runtime.value_data_profile.v2",
        schema_version="2.0",
        inputs=(
            InputRef(
                artifact_id=projection_ref["artifact_id"],
                role="activated_source_projection",
                manifest_profile_sha256=projection_ref["manifest_profile_sha256"],
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ArtifactRef.model_validate(profile_ref)


@pytest.mark.asyncio
async def test_runtime_intake_reopens_owner_projection_and_rejects_self_consistent_forgery(
    tmp_path, monkeypatch, request
) -> None:
    """A valid local producer receipt passes; fake receipt and changed rows refuse."""
    from polisyos.core import artifacts
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        ActivatedAcquisitionObservationProjection,
    )
    from polisyos.runtime.http.services.predictive_calibration import (
        PredictiveCalibrationError,
        _validate_selected_value_data_profile,
    )
    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        resolve_catalog_serving_source,
    )
    from tests.integration.core_runtime.test_acquisition_world_growth_chain import (
        _admit_served_wdi_projection,
    )

    admitted = await _admit_served_wdi_projection(
        tmp_path,
        monkeypatch,
        request,
        baseline_country_code="UA",
    )
    served = admitted.served
    projection = admitted.projection
    store = served.case.bridge.artifact_store
    overlay_path = served.case.call_args["overlay_path"]
    repo_root = served.case.authority.repo_root
    gateway = RealValueOwnerGateway(
        repo_root=repo_root,
        catalog_overlay_path=overlay_path,
        artifact_store=store,
        activated_observation_projection=projection,
    )
    source = resolve_catalog_serving_source(
        repo_root,
        selection=None,
        requested_profile=None,
    )
    assert source.overlay_path.resolve() == overlay_path.resolve()

    with tenant_scope(
        None,
        tenant_id=served.closure.tenant_id,
        cell_id=served.closure.cell_id,
    ):
        profile = gateway.load_value_data_profile(
            candidate=object(),
            problem=served.closure.design_problem_basis,
            world_record=object(),
        )
        profile_ref = _persist_profile_pair(store, projection=projection, profile=profile)

        with catalog_serving_source_scope(source):
            selected = _validate_selected_value_data_profile(store, profile_ref)
        assert selected.profile.model_dump(mode="json") == profile.model_dump(mode="json")
        assert selected.projection.model_dump(mode="json") == projection.model_dump(mode="json")
        assert selected.source_passport.passport_id == projection.passport_id
        assert selected.projection.source_time_status == "not_established"

        # A valid, rehashed profile can still violate the serving producer's
        # one-row-per-unit-period rule. Keep all shape/hash markers and prove
        # Runtime intake rejects the duplicated actual owner observation.
        from polisyos.pdc import gy_content_hash
        from polisyos.runtime.quality.generation_cycle import (
            ValueDataProfile,
            _derived_value_data_modalities,
        )

        duplicate_rows = (profile.rows[0], *profile.rows)
        duplicate_payload = profile.model_dump(mode="json")
        duplicate_payload.pop("content_hash")
        duplicate_payload["rows"] = tuple(row.model_dump(mode="json") for row in duplicate_rows)
        duplicate_payload["owner_row_count"] = len(duplicate_rows)
        duplicate_payload["owner_rows_content_hash"] = gy_content_hash(duplicate_payload["rows"])
        duplicate_payload["available_data_modalities"] = _derived_value_data_modalities(
            duplicate_rows
        )
        duplicate_profile = ValueDataProfile.model_validate(
            {**duplicate_payload, "content_hash": gy_content_hash(duplicate_payload)}
        )
        duplicate_profile_ref = _persist_profile_pair(
            store,
            projection=projection,
            profile=duplicate_profile,
        )
        with (
            catalog_serving_source_scope(source),
            pytest.raises(PredictiveCalibrationError) as duplicate_refusal,
        ):
            _validate_selected_value_data_profile(store, duplicate_profile_ref)
        assert duplicate_refusal.value.code == "predictive_calibration_value_profile_invalid"

        # The projection below is internally self-consistent and carries the
        # actual verified passport, but its receipt is not the active owner receipt.
        fake_receipt_ref = artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID("sha256:" + "f" * 64),
            kind="epoch.activated_overlay_admission_receipt",
            media_type="application/json",
        )
        fake_receipt_projection = ActivatedAcquisitionObservationProjection.issue(
            receipt_ref=fake_receipt_ref,
            receipt_content_sha256="sha256:" + "e" * 64,
            passport_ref=projection.passport_ref,
            passport_content_sha256=projection.passport_content_sha256,
            variable_id=projection.variable_id,
            epoch_id=projection.epoch_id,
            passport_id=projection.passport_id,
            admission_content_sha256=projection.admission_content_sha256,
            observations=tuple(row.observation for row in projection.observations),
        )
        fake_profile_ref = _persist_profile_pair(
            store,
            projection=fake_receipt_projection,
            profile=profile,
        )
        with (
            catalog_serving_source_scope(source),
            pytest.raises(PredictiveCalibrationError) as fake_receipt_refusal,
        ):
            _validate_selected_value_data_profile(store, fake_profile_ref)
        assert fake_receipt_refusal.value.code == "predictive_calibration_value_profile_invalid"

        changed_observations = tuple(
            row.observation.model_copy(update={"value": row.observation.value + 0.25})
            if index == 0
            else row.observation
            for index, row in enumerate(projection.observations)
        )
        changed_projection = ActivatedAcquisitionObservationProjection.issue(
            receipt_ref=projection.receipt_ref,
            receipt_content_sha256=projection.receipt_content_sha256,
            passport_ref=projection.passport_ref,
            passport_content_sha256=projection.passport_content_sha256,
            variable_id=projection.variable_id,
            epoch_id=projection.epoch_id,
            passport_id=projection.passport_id,
            admission_content_sha256=projection.admission_content_sha256,
            observations=changed_observations,
        )
        changed_profile_ref = _persist_profile_pair(
            store,
            projection=changed_projection,
            profile=profile,
        )
        with (
            catalog_serving_source_scope(source),
            pytest.raises(PredictiveCalibrationError) as changed_refusal,
        ):
            _validate_selected_value_data_profile(store, changed_profile_ref)
        assert changed_refusal.value.code == "predictive_calibration_value_profile_invalid"
