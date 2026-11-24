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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "variable",
        "raw_field",
        "slot_id",
        "metric_id",
        "quantity_kind",
        "time_support",
        "aggregation",
    ),
    [
        ("economic.gdp", "gdp", "global.gdp", "annual_gdp_level", "flow", "period_total", "sum"),
        (
            "fiscal.balance",
            "balance",
            "government.balance",
            "annual_fiscal_balance",
            "stock",
            "state_end",
            "last",
        ),
    ],
    ids=("annual-gdp-flow", "year-end-fiscal-stock"),
)
async def test_served_observed_outcome_level_reopens_without_new_work(
    tmp_path,
    monkeypatch,
    variable,
    raw_field,
    slot_id,
    metric_id,
    quantity_kind,
    time_support,
    aggregation,
):
    """Exercise the complete V7 attachment on two genuinely selected annual series."""
    import json
    import os
    import subprocess
    import sys
    from datetime import date
    from decimal import Decimal
    from math import isfinite
    from pathlib import Path

    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import (
        ArtifactRef,
        FileSystemCAS,
        PutOptions,
        SchemaInfo,
        ensure_ir_artifact_store,
        input_ref_from_artifact_ref,
        load_core_json_artifact,
    )
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
    from polisyos.core.contracts.model_input_requirements import ModelInputPort
    from polisyos.core.contracts.variable_binding import (
        MeasurementAxis,
        MeasurementBindingProfile,
        MeasurementBindingProfileRef,
        ModelInputScope,
    )
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir import ForecastingUncertaintyBundleRef, load_forecasting_uncertainty_bundle
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY
    from polisyos.runtime.quality.forecast_profile_binding import ForecastOutcomeLevelRelationV1
    from polisyos.runtime.quality.generation_cycle import _load_value_data_profile_from_l1_dcat
    from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope
    from polisyos.scientist.methods.backtesting import ForecastOwner
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )
    from tests._helpers.catalog_source_admission import admit_fixture_catalog_source
    from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
    from tests.unit.remediation.test_frc_02_owner import _rule, _temporal_roles
    from tests.unit.runtime.http.test_control_service_di import (
        _run_controlled_simulate_only_job_fixture,
    )
    from tests.unit.runtime.quality.test_forecast_profile_binding import (
        _persist_selected_definition,
        _persist_selected_representation,
    )

    tenant_id = "7cf3b2a8-0d6b-4d25-a01c-f248e933e1f0"
    cell_id = "5f7ca7a3-2d66-4bbc-a7a2-f35c60ba3a7f"
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root).for_tenant(tenant_id, cell_id)
    years = tuple(range(2010, 2025))
    population = "national_economy"
    scope = ModelInputScope(
        population_ref=population,
        geography_ref="UA",
        jurisdiction_ref="UA",
        period_start=date(years[0], 1, 1),
        period_end=date(years[-1], 12, 31),
        period_basis="calendar_year",
        time_role="observation_time",
    )
    # Explicit software fixture data. At least one held-out discontinuity is
    # large compared with training variability, so an all-hit oracle cannot pass.
    level = 1_000 if quantity_kind == "flow" else 225
    values = tuple(
        float(level + 4 * index + ((index % 3) - 1) + (600 if index == 13 else 0))
        for index in range(len(years))
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        definition_ref = _persist_selected_definition(
            store, variable=variable, revision=f"annual-{quantity_kind}-v1"
        )
        representation_ref = _persist_selected_representation(
            store,
            definition=definition_ref,
            scale=Decimal(1),
            quantity_kind=quantity_kind,
            time_support=time_support,
            aggregation=aggregation,
            population_ref=scope.population_ref,
        )
        profile_contract = MeasurementBindingProfile(
            profile_id="forecast.annual-held-out-level",
            revision="fixture",
            required_axes=(
                MeasurementAxis.QUANTITY_KIND,
                MeasurementAxis.MEASURE_FORM,
                MeasurementAxis.UNIT_ID,
                MeasurementAxis.TIME_SUPPORT,
            ),
        )
        profile_contract_ref = MeasurementBindingProfileRef.model_validate(
            store.put_json(
                profile_contract,
                PutOptions(
                    kind=profile_contract.ARTIFACT_KIND,
                    media_type=profile_contract.ARTIFACT_MEDIA_TYPE,
                    schema=SchemaInfo(
                        name=profile_contract.ARTIFACT_SCHEMA_NAME,
                        version=profile_contract.ARTIFACT_SCHEMA_VERSION,
                    ),
                ),
                return_selected_profile=True,
            ).model_dump()
        )
        slot = DEFAULT_SLOT_REGISTRY.slots[slot_id]
        assert slot.unit is not None and slot.unit.unit_id == "usd"
        assert slot.kind.value == quantity_kind
        port = ModelInputPort(
            purpose="outcome_validation",
            port_id=metric_id,
            slot_id=slot_id,
            state_path=slot.state_path,
            unit_id=slot.unit.unit_id,
            semantic_definition_ref=definition_ref,
            representation_ref=representation_ref,
            binding_profile_ref=profile_contract_ref,
            scope=scope,
        )
        active = make_native_multivariable_active_projections(
            tmp_path / "observed-catalog",
            source_rows=[
                {
                    "country_code": "UA",
                    "year": year,
                    raw_field: value,
                    "condition_json": json.dumps(
                        {
                            "population_ref": scope.population_ref,
                            "geography_ref": scope.geography_ref,
                            "jurisdiction_ref": scope.jurisdiction_ref,
                            "time_period_basis": "calendar_year",
                        },
                        sort_keys=True,
                    ),
                }
                for year, value in zip(years, values, strict=True)
            ],
            variable_specs=(
                {
                    "target_variable": variable,
                    "raw_field": raw_field,
                    "raw_unit": "usd",
                    "canonical_unit": "usd",
                    "valid_min": 0,
                    "valid_max": 10_000,
                    "temporal_start": str(years[0]),
                    "temporal_end": str(years[-1]),
                    "source_measure_scope": {
                        "population": scope.population_ref,
                        "temporal_granularity": "annual",
                        "jurisdiction_ref": scope.jurisdiction_ref,
                        "time_period_basis": "calendar_year",
                        "source_geography_id": "UA",
                        "geography_ref": scope.geography_ref,
                    },
                    "source_semantic_definition_ref": definition_ref,
                    "source_representation_ref": representation_ref,
                },
            ),
            condition_units_by_raw_field={raw_field: "usd"},
            artifact_store=store,
            return_selected_raw_profile=True,
        )
        active.overlay.close()

        # Use the source's original physical Catalog and overlay, never a copied
        # baseline path. The N4 worker retains its separately selected K_ref root.
        catalog = admit_fixture_catalog_source(
            repo_root=active.repo_root, database_path=active.baseline_path
        )
        selected_projection = active.projections[variable]
        with catalog_serving_source_scope(catalog):
            observed_profile = _load_value_data_profile_from_l1_dcat(
                repo_root=active.repo_root,
                outcome=variable,
                owner_access_ref=f"fixture:served-observed-level:{variable}",
                overlay_path=active.overlay_path,
                artifact_store=store,
                activated_observation_projection=selected_projection,
            )
        assert observed_profile is not None
        assert tuple(row.period_id for row in observed_profile.rows) == years
        assert tuple(row.outcome_value for row in observed_profile.rows) == values
        assert {row.unit_id for row in observed_profile.rows} == {"UA"}
        profile_ref = _persist_profile_pair(
            store, projection=selected_projection, profile=observed_profile
        )
        values_ref = store.put_json(
            {variable: values},
            PutOptions(kind="test.forecast.selected_series", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        snapshot = DataSnapshot(data_ref=values_ref)
        snapshot_ref = store.put_json(
            snapshot.model_dump(mode="json"),
            PutOptions(
                kind=DataSnapshot.ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                    version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[input_ref_from_artifact_ref(values_ref, role="data_ref")],
            ),
            return_selected_profile=True,
        )
        policy_ref = store.put_json(
            PolicySpec(policy_id=f"{metric_id}_candidate_forecast_basis").model_dump(mode="json"),
            PutOptions(kind="ir.policy_spec", media_type="application/json"),
            return_selected_profile=True,
        )
        rule_ref = _rule(store)

    def attach_inputs(context):
        for reference in (profile_ref, snapshot_ref, policy_ref, rule_ref):
            context.add_input(reference)

    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "bounded-n4-substrate",
        outcome_variable=slot_id,
        include_owner_slot_manifest=True,
        owner_knob_dictionary={
            "tax_relief_rate": {
                "default": 0.1,
                "type": "float",
                "min": 0.0,
                "max": 0.5,
                "mechanism_id": "tax_relief_rate",
                "param_path": "params.rate",
            }
        },
    )
    with monkeypatch.context() as producer_fixture:
        finished = await _run_controlled_simulate_only_job_fixture(
            producer_fixture,
            tmp_path,
            root_input_factory=attach_inputs,
            source_repo_root=source.root,
            source_root=source.root,
            basis_repo_root=source.root,
            l6_source_owner_root=source.root,
            tenant_id=tenant_id,
            cell_id=cell_id,
            stage_diagnostic_path=tmp_path / "observed-level-stages.jsonl",
            forecast_outcome_port=port,
        )
    try:
        assert finished.job.state == "completed"
        assert len(finished.n5_port_observations) == 1
        assert finished.model_declaration.outcome_variable == slot_id
        core_run_id = finished.job.progress["core_run_id"]
        job_id = finished.job.job_id
        control_db = finished.service._control_store._sqlite_path
        assert control_db is not None
    finally:
        finished.service.close()

    case = {
        "cas_root": str(cas_root.resolve()),
        "catalog_root": str(active.repo_root.resolve()),
        "catalog_database": str(active.baseline_path.resolve()),
        "control_db": str(control_db.resolve()),
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "core_run_id": core_run_id,
        "job_id": job_id,
    }
    owner_requests = []
    original_run = ForecastOwner.run

    def observe_forecast(owner, forecast_request):
        owner_requests.append(forecast_request)
        return original_run(owner, forecast_request)

    with monkeypatch.context() as warm_fixture:
        warm_fixture.setattr(ForecastOwner, "run", observe_forecast)
        with TestClient(_observed_level_reader_app(case, warm_fixture)) as client:
            run_response = client.get(f"/api/v1/runs/{core_run_id}")
            assert run_response.status_code == 200, run_response.text
            run = run_response.json()["run"]
            selected_sources = [
                row["n4_source_ref"]
                for row in run["candidate_simulation"]["n5_observations"]
                if row["status"] == "joint_simulated" and row["lineage_status"] == "resolved"
            ]
            (candidate_ref,) = selected_sources
            (model_ref,) = (
                ref for ref in run["root_input_artifacts"] if ref["kind"] == "ir.model_spec"
            )
            body = {
                "intent_id": f"served-observed-level-{metric_id}",
                "candidate_source_ref": candidate_ref,
                "observed_source_ref": DataSnapshotRef.model_validate(
                    snapshot_ref.model_dump(mode="json")
                ).model_dump(mode="json"),
                "value_data_profile_ref": profile_ref.model_dump(mode="json"),
                "value_data_unit_id": "UA",
                "model_spec_ref": model_ref,
                "policy_spec_ref": policy_ref.model_dump(mode="json"),
                "calibration_rule_ref": rule_ref.model_dump(mode="json"),
                "calibration_threshold": 0.9,
                "split": {
                    "train_start": 0,
                    "train_end": 11,
                    "holdout_start": 11,
                    "holdout_end": 15,
                    "horizon": 4,
                },
                "target_metric": variable,
                "method_params": {"horizon": 4, "alpha": 0.3, "beta": 0.1},
                "temporal_roles": _temporal_roles().model_dump(mode="json"),
                "seed": 11,
            }
            case_owner = client.app.state.runtime_container.control_service
            assert case_owner is not None and case_owner._worker is None
            assert case_owner.catalog_serving_source == catalog
            prepost_case = tmp_path / "observed-level-prepost-case.json"
            prepost_case.write_text(
                json.dumps({**case, "request": body}, sort_keys=True), encoding="utf-8"
            )
            response = client.post(f"/api/v1/runs/{core_run_id}/predictive-calibration", json=body)
            assert response.status_code == 201, response.text
            warm = response.json()
            association = warm["association"]
            assert association["schema_version"].endswith(".v7")
            assert association["authority_scope"] == "predictive_only"
            assert association["s10"]["forecast_tier"] == "blocked"
            for key in (
                "issuer_status",
                "source_time_status",
                "population_scope_status",
                "counterfactual_credibility_status",
            ):
                assert association[key] == "not_established"
            matched = warm["observed_outcome_level"]
            assert matched["status"] == "matched_candidate"
            assert matched["support"]["observed_target_metric"] == variable
            assert matched["support"]["target_variable"] == slot_id
            assert matched["support"]["n4_metric_id"] == metric_id
            assert matched["support"]["measurement_unit"] == "usd"
            assert matched["support"]["holdout_years"] == list(years[11:])
            assert matched["support"]["observed_series_scope"]["period_start"] == "2010-01-01"
            assert matched["support"]["observed_series_scope"]["period_end"] == "2024-12-31"
            assert matched["support"]["authority_scope"] == "predictive_only"
            relation_raw = association["observed_outcome_relation_ref"]
            assert matched["support"]["relation_ref"] == relation_raw
            relation_ref = ArtifactRef.model_validate(relation_raw)
            published = [
                row.event
                for row in case_owner._diagnostic_event_log.list_events(
                    run_id=core_run_id, job_id=job_id
                )
                if row.event.phase == "predictive_calibration_publication"
            ]
            (publication,) = published
            assert publication.event_id == association["event_id"]
            assert str(relation_ref.artifact_id) in publication.input_refs
            assert warm["association_ref"]["artifact_id"] in publication.artifact_refs
    assert len(owner_requests) == 1

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        # Exact selected stored bytes exercise canonical date-tag decoding; the
        # HTTP calendar strings alone do not prove the persisted object reopens.
        persisted_relation = ForecastOutcomeLevelRelationV1.model_validate(
            load_core_json_artifact(store, relation_ref)
        )
        assert type(persisted_relation.observed_scope.period_start) is date
        assert persisted_relation.observed_scope == scope
        assert persisted_relation.model_spec_ref.model_dump(mode="json") == model_ref
        assert persisted_relation.model_port_id == metric_id
        assert persisted_relation.source_representation_ref == representation_ref
        assert persisted_relation.target_representation_ref == representation_ref
        assert persisted_relation.transformation == "identity"
        bundle = load_forecasting_uncertainty_bundle(
            ensure_ir_artifact_store(store),
            ForecastingUncertaintyBundleRef.model_validate(association["uncertainty_bundle_ref"]),
        )
    intervals = tuple(sorted(bundle.prediction_interval, key=lambda interval: interval.horizon))
    assert tuple(row.horizon for row in intervals) == (1, 2, 3, 4)
    assert all(isfinite(float(row.point)) for row in intervals)
    assert len({float(row.point) for row in intervals}) > 1
    assert bundle.target_id == variable
    hit_count = sum(
        float(row.lower) <= value <= float(row.upper)
        for row, value in zip(intervals, values[11:], strict=True)
    )
    assert hit_count < len(intervals)
    assert association["s10"]["observed_series_coverage"] == {
        "holdout_numerator": hit_count,
        "holdout_denominator": len(intervals),
        "holdout_coverage": hit_count / len(intervals),
        "estimand": "predictive_interval_coverage",
        "evidence_status": "recomputed",
        "authority_scope": "predictive_only",
    }
    case["warm"] = warm
    case_file = tmp_path / "observed-level-warm-case.json"
    case_file.write_text(json.dumps(case, sort_keys=True), encoding="utf-8")
    # Python process, app instances, service, store and run index all reopen.
    product_root = Path(__file__).resolve().parents[3]
    pythonpath = os.pathsep.join(str(product_root / folder) for folder in ("tests", "src", "."))
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "tests.integration.core_runtime.test_predictive_calibration_profile_owner_binding",
            str(case_file),
        ],
        cwd=product_root,
        env={**os.environ, "PYTHONPATH": pythonpath},
        check=False,
        capture_output=True,
        text=True,
        timeout=75,
    )
    (tmp_path / "observed-level-cold.log").write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "v7_cold_match_remove_restore_no_effect" in result.stdout


def _observed_level_reader_app(case, monkeypatch):
    from pathlib import Path

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http import dev_identity_middleware
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourceSelection
    from tests.unit.runtime.http.test_control_service_di import (
        _fixture_claims,
        _install_fixture_tenant_lifespan,
    )

    root = Path(case["catalog_root"]).resolve(strict=True)
    db = Path(case["catalog_database"]).resolve(strict=True)
    cas = Path(case["cas_root"]).resolve(strict=True)
    tenant_id = case["tenant_id"]
    cell_id = case["cell_id"]
    selection = CatalogServingSourceSelection(
        snapshot_root=root,
        database_relative_path=db.relative_to(root),
        catalog_run_profile="preflight_core",
    )
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", case["control_db"])
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setattr(
        dev_identity_middleware,
        "build_fixture_identity_claims",
        lambda: _fixture_claims(tenant_id=tenant_id, cell_id=cell_id),
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        app = create_runtime_api_app(
            cas_root=cas,
            core_runs_root=cas / "runs",
            repo_root=root,
            allow_fixture_identity=True,
            catalog_run_profile="preflight_core",
            catalog_source_selection=selection,
        )
    _install_fixture_tenant_lifespan(app, tenant_id=tenant_id, cell_id=cell_id)
    return app


def _cold_observed_level_replay(case_file):
    import json
    import os
    from hashlib import sha256
    from pathlib import Path

    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
    from polisyos.core.artifacts._layout import CASPathLayout
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.control import ControlPlaneService
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from polisyos.scientist.methods.backtesting import ForecastOwner

    case = json.loads(case_file.read_text(encoding="utf-8"))
    warm = case["warm"]
    selected = ArtifactRef.model_validate(warm["association"]["observed_outcome_relation_ref"])
    assert selected.manifest_profile_sha256 is not None
    cas_root = Path(case["cas_root"]).resolve(strict=True)
    store = FileSystemCAS.open_existing_read_only(cas_root)
    sidecar = CASPathLayout(cas_root).view_manifest_path(
        selected.artifact_id, selected.manifest_profile_sha256
    )
    assert sidecar.is_file() and sidecar.stat().st_nlink == 1 and not sidecar.is_symlink()
    assert sidecar.resolve(strict=True).is_relative_to(cas_root)
    saved = sidecar.with_name(sidecar.name + ".fault-hold")
    assert not saved.exists()
    with tenant_scope(None, tenant_id=case["tenant_id"], cell_id=case["cell_id"]):
        assert store.verify(selected).ok
        original = store.get_raw_manifest_bytes(selected)
    assert sidecar.read_bytes() == original

    def refuse_work(*_args, **_kwargs):
        raise AssertionError("fresh V7 read attempted producer, worker or simulation")

    endpoint = f"/api/v1/runs/{case['core_run_id']}/predictive-calibration"

    with pytest.MonkeyPatch.context() as cold_patch:
        cold_patch.setattr(ForecastOwner, "run", refuse_work)
        cold_patch.setattr(ControlPlaneService, "_process_control_job", refuse_work)
        cold_patch.setattr(JointSimulationHorizonController, "run", refuse_work)

        def read():
            with TestClient(_observed_level_reader_app(case, cold_patch)) as client:
                owner = client.app.state.runtime_container.control_service
                assert owner is not None and owner._worker is None
                assert owner._control_store._sqlite_path.resolve() == Path(case["control_db"])
                assert owner.catalog_serving_source.database_path == Path(case["catalog_database"])
                response = client.get(endpoint)
                assert response.status_code == 200, response.text
                publications = [
                    row.event.event_id
                    for row in owner._diagnostic_event_log.list_events(
                        run_id=case["core_run_id"], job_id=case["job_id"]
                    )
                    if row.event.phase == "predictive_calibration_publication"
                ]
                assert publications == [warm["association"]["event_id"]]
                return response.json()

        def compare_base(payload):
            assert payload["association_ref"] == warm["association_ref"]
            assert payload["association"] == warm["association"]

        current = read()
        compare_base(current)
        assert current["observed_outcome_level"] == warm["observed_outcome_level"]
        os.replace(sidecar, saved)
        try:
            assert not sidecar.exists() and saved.read_bytes() == original
            limited = read()
            compare_base(limited)
            assert limited["observed_outcome_level"] == {"status": "not_established"}
            assert limited["association"]["s10"]["interval_support"]
            assert limited["association"]["s10"]["observed_series_coverage"]
        finally:
            os.replace(saved, sidecar)
        assert sidecar.read_bytes() == original
        with tenant_scope(None, tenant_id=case["tenant_id"], cell_id=case["cell_id"]):
            assert store.verify(selected).ok
            assert store.get_raw_manifest_bytes(selected) == original
        restored = read()
        compare_base(restored)
        assert restored["observed_outcome_level"] == warm["observed_outcome_level"]
    fresh_cases = case_file.with_name("observed-level-fresh-cases.json")
    fresh_cases.write_text(
        json.dumps({"current": current, "removed": limited, "restored": restored}, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "association_ref": warm["association_ref"],
                "publication_event_id": warm["association"]["event_id"],
                "selected_relation_ref": selected.model_dump(mode="json"),
                "selected_view_raw_sha256": sha256(original).hexdigest(),
                "observed_series_coverage": warm["association"]["s10"]["observed_series_coverage"],
                "observed_relation_states": [
                    payload["observed_outcome_level"]["status"]
                    for payload in (current, limited, restored)
                ],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    print("v7_cold_match_remove_restore_no_effect", flush=True)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    _cold_observed_level_replay(Path(sys.argv[1]))
