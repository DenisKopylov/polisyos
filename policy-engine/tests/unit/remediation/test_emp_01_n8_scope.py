"""Scoped candidate rows through the real selected Catalog and N8 owners."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactID, ArtifactRef, FileSystemCAS, ensure_ir_artifact_store
from polisyos.core.contracts import ModelInputScope
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.foundry.extensions.registry import controlled_builtin_foundry_method_registry_scope
from polisyos.foundry.methods.catalog.causal.treatment_effects import AIPWEstimator
from polisyos.ir import CanonSpec, put_json_artifact
from polisyos.runtime.quality import generation_cycle as gc
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from polisyos.runtime.quality.candidate_value_method import (
    _load_selected_value_source_request,
    _reconcile_selected_outer_set,
    persist_candidate_value_source_request,
)
from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope
from tests._helpers.catalog_source_admission import admit_fixture_catalog_source
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.runtime.quality.test_b31_owner_run_basis_v2 import _persist_json, _profile
from tests.unit.runtime.quality.test_value_gate import (
    _avg_income_problem,
    _avg_income_typed_atom_candidate,
    _simulation,
    _simulation_execution_context,
    _world_record,
)


def test_historical_v2_source_profile_keeps_its_canonical_hash() -> None:
    """The new optional scope cannot alter a retained historical v2 profile."""
    profile = _profile()
    assert profile.content_hash == (
        "sha256:475b0e0385cfd8377186cf4fefd59aee2b6fcd58684ac461be6c73770caba270"
    )
    assert "scope_selection_content_sha256" not in profile.model_dump(mode="json")


def test_scoped_signed_source_filters_before_cap_and_replays_through_n8(tmp_path: Path) -> None:
    """A verified source scope remains part of the selected candidate's identity."""
    store = FileSystemCAS(tmp_path / "cas")
    rows = []
    for population in ("population:first", "population:second"):
        for index in range(120):
            treatment = index % 2
            covariate = (index // 2) % 2
            rows.append(
                {
                    "country_code": "UA",
                    "year": 1880 + index,
                    "avg_income": float(index % 13) + 0.25 * treatment + 0.5 * covariate,
                    "agents.income": float(treatment),
                    "income_covariate": float(covariate),
                    "condition_json": json.dumps(
                        {
                            "population_ref": population,
                            "geography_ref": "UA",
                            "jurisdiction_ref": "UA",
                            "time_period_basis": "calendar_year",
                        },
                        sort_keys=True,
                    ),
                }
            )
    source = make_native_multivariable_active_projections(
        tmp_path / "owner",
        source_rows=rows,
        variable_specs=(
            {
                "target_variable": "avg_income",
                "raw_field": "avg_income",
                "raw_unit": "m",
                "canonical_unit": "m",
                "valid_min": 0.0,
                "valid_max": 13.0,
            },
            {
                "target_variable": "agents.income",
                "raw_field": "agents.income",
                "raw_unit": "binary",
                "canonical_unit": "binary",
                "valid_min": 0.0,
                "valid_max": 1.0,
            },
            {
                "target_variable": "income_covariate",
                "raw_field": "income_covariate",
                "raw_unit": "binary",
                "canonical_unit": "binary",
                "valid_min": 0.0,
                "valid_max": 1.0,
            },
        ),
        condition_units_by_raw_field={
            "avg_income": "m",
            "agents.income": "binary",
            "income_covariate": "binary",
        },
        artifact_store=store,
        return_selected_raw_profile=True,
    )
    try:
        projections = source.projections
        outcome_projection = projections["avg_income"]
        outcome_passport = AdmissionPassport.model_validate(
            load_verified_epoch_statement(
                store=store,
                ref=outcome_projection.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        )
        source_context = admit_fixture_catalog_source(
            repo_root=source.repo_root, database_path=source.baseline_path
        )
        scope = ModelInputScope(
            population_ref="population:first",
            geography_ref="UA",
            jurisdiction_ref="UA",
            period_start=date(1880, 1, 1),
            period_end=date(1999, 12, 31),
            time_role="observation_time",
            period_basis="calendar_year",
        )
        loader_inputs = {
            "repo_root": source.repo_root,
            "outcome": "avg_income",
            "owner_access_ref": "fixture://emp05/active-owner",
            "overlay_path": source.overlay_path,
            "scope_region": "UA",
            "artifact_store": store,
            "activated_observation_projection": outcome_projection,
        }
        with catalog_serving_source_scope(source_context):
            # The same actual Catalog SQL must refuse the unselected 240 rows,
            # accept exactly 120 scoped rows, and refuse a lower cap of 119.
            with pytest.raises(gc.ValueOwnerAccessError) as refused:
                gc._load_value_data_profile_from_l1_dcat(**loader_inputs, owner_row_limit=120)
            assert refused.value.code == "acquire_data:value_owner_rows_truncated"
            first = gc._load_value_data_profile_from_l1_dcat(
                **loader_inputs,
                measurement_scope=scope,
                expected_dataset_version=outcome_passport.dataset_version,
                owner_row_limit=120,
            )
            second = gc._load_value_data_profile_from_l1_dcat(
                **loader_inputs,
                measurement_scope=scope.model_copy(update={"population_ref": "population:second"}),
                expected_dataset_version=outcome_passport.dataset_version,
                owner_row_limit=120,
            )
            widened = gc._load_value_data_profile_from_l1_dcat(
                **loader_inputs,
                measurement_scope=scope.model_copy(update={"period_start": date(1879, 1, 1)}),
                expected_dataset_version=outcome_passport.dataset_version,
                owner_row_limit=120,
            )
            assert first is not None and second is not None and widened is not None
            assert first.owner_row_count == second.owner_row_count == 120
            assert [row.outcome_value for row in first.rows] == [
                row.outcome_value for row in second.rows
            ]
            assert first.owner_rows_content_hash != second.owner_rows_content_hash
            assert first.rows == widened.rows
            assert first.content_hash != widened.content_hash
            assert first.scope_selection_content_sha256 != widened.scope_selection_content_sha256
            with pytest.raises(gc.ValueOwnerAccessError) as refused:
                gc._load_value_data_profile_from_l1_dcat(
                    **loader_inputs,
                    measurement_scope=scope,
                    expected_dataset_version=outcome_passport.dataset_version,
                    owner_row_limit=119,
                )
            assert refused.value.code == "acquire_data:value_owner_rows_truncated"
            with pytest.raises(gc.ValueOwnerAccessError) as refused:
                gc._load_value_data_profile_from_l1_dcat(
                    **loader_inputs,
                    measurement_scope=scope,
                    expected_dataset_version="wrong-version",
                    owner_row_limit=120,
                )
            assert refused.value.code == "acquire_data:measurement_scope_dataset_version_mismatch"
            with pytest.raises(gc.ValueOwnerAccessError) as refused:
                gc._load_value_data_profile_from_l1_dcat(
                    **loader_inputs,
                    measurement_scope=scope.model_copy(
                        update={"population_ref": "population:not-present"}
                    ),
                    expected_dataset_version=outcome_passport.dataset_version,
                    owner_row_limit=120,
                )
            assert refused.value.code == "acquire_data:measurement_scope_no_matching_observations"

            problem = _avg_income_problem()
            candidate = replace(
                _avg_income_typed_atom_candidate(problem, unit_id="m"),
                diversity_key=("grant", "country", "avg_income", "emp05_scope"),
            )
            world = _world_record()
            simulation = _simulation(world, candidate_id=candidate.candidate_id)
            estimand = {
                "query_id": "emp05-scoped-candidate",
                "estimand_id": "ATE",
                "outcome": "avg_income",
                "treatment_or_exposure": "agents.income",
                "covariates_or_conditioning": ["income_covariate"],
                "adjustment_set": ["income_covariate"],
                "population": scope.population_ref,
                "sample_filter": None,
                "time_horizon": None,
                "prediction_origin": None,
                "unit": "m",
                "scale": "identity",
                "transform": None,
                "target_role": "estimate",
                "loss_or_utility_id": None,
            }
            bindings = (
                ("outcome", "avg_income"),
                ("treatment", "agents.income"),
                ("covariate", "income_covariate"),
            )
            request = gc.ValueOwnerSourceProjectionRequestV2(
                selected_method_fqn=AIPWEstimator.signature.fqn,
                estimand_spec_json=json.dumps(estimand, sort_keys=True, separators=(",", ":")),
                variable_projections=tuple(
                    gc.ValueOwnerSourceVariableProjectionV2(
                        role=role,
                        variable_id=variable,
                        projection_payload=projections[variable].model_dump(mode="json"),
                        dataset_version=projections[variable]
                        .observations[0]
                        .observation.dataset_version,
                    )
                    for role, variable in bindings
                ),
                measurement_scope=scope,
                outcome_lower=0.0,
                outcome_upper=13.0,
                outcome_bounds_unit="m",
                method_parameters_json="{}",
                seed=7,
            )
            request_ref = persist_candidate_value_source_request(store, request)
            request_manifest = store.get_manifest(request_ref)
            assert request_manifest.artifact_schema.name == (
                "policyos.runtime.value_owner_source_projection_request.v2"
            )
            assert request_manifest.artifact_schema.version == "2.0"
            assert _load_selected_value_source_request(FileSystemCAS(store.root), request_ref) == (
                request
            )
            request_edges = list(request_manifest.inputs)
            assert len(request_edges) == 6
            assert request_edges[-1].manifest_profile_sha256 != "sha256:" + "f" * 64
            foreign_profile_edge = request_edges[-1].model_copy(
                update={"manifest_profile_sha256": "sha256:" + "f" * 64}
            )
            unrelated_edge = request_edges[0].model_copy(update={"role": "unrelated"})
            for foreign_edges in (
                request_edges[:-1],
                [*request_edges, unrelated_edge],
                [*request_edges[:-1], foreign_profile_edge],
            ):
                foreign_wire = put_json_artifact(
                    ensure_ir_artifact_store(store),
                    request.model_dump(mode="json"),
                    kind="runtime.value_owner_source_projection_request",
                    schema_name="policyos.runtime.value_owner_source_projection_request.v2",
                    schema_version="2.0",
                    inputs=foreign_edges,
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
                foreign_ref = ArtifactRef.model_validate(foreign_wire)
                assert foreign_ref.artifact_id == request_ref.artifact_id
                assert foreign_ref.manifest_profile_sha256 != request_ref.manifest_profile_sha256
                with pytest.raises(
                    ValueError, match="candidate_value_method_source_request_lineage_mismatch"
                ):
                    _load_selected_value_source_request(FileSystemCAS(store.root), foreign_ref)
            legacy_estimand = {**estimand, "population": "unspecified"}
            legacy_request = gc.ValueOwnerSourceProjectionRequestV1(
                selected_method_fqn=request.selected_method_fqn,
                estimand_spec_json=json.dumps(
                    legacy_estimand, sort_keys=True, separators=(",", ":")
                ),
                variable_projections=tuple(
                    gc.ValueOwnerSourceVariableProjectionV1(
                        role=binding.role,
                        variable_id=binding.variable_id,
                        projection_payload=binding.projection_payload,
                    )
                    for binding in request.variable_projections
                ),
                outcome_lower=request.outcome_lower,
                outcome_upper=request.outcome_upper,
                outcome_bounds_unit=request.outcome_bounds_unit,
                method_parameters_json=request.method_parameters_json,
                seed=request.seed,
            )
            legacy_ref = persist_candidate_value_source_request(store, legacy_request)
            assert "measurement_scope" not in legacy_request.model_dump(mode="json")
            assert store.get_manifest(legacy_ref).artifact_schema.version == "1.0"
            assert _load_selected_value_source_request(FileSystemCAS(store.root), legacy_ref) == (
                legacy_request
            )
            forged_ref = put_json_artifact(
                ensure_ir_artifact_store(store),
                request.model_dump(mode="json"),
                kind="runtime.value_owner_source_projection_request",
                schema_name="policyos.runtime.value_owner_source_projection_request.v1",
                schema_version="1.0",
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            with pytest.raises(ValueError):
                _load_selected_value_source_request(
                    FileSystemCAS(store.root), ArtifactRef.model_validate(forged_ref)
                )
            forged_legacy_ref = put_json_artifact(
                ensure_ir_artifact_store(store),
                legacy_request.model_dump(mode="json"),
                kind="runtime.value_owner_source_projection_request",
                schema_name="policyos.runtime.value_owner_source_projection_request.v2",
                schema_version="2.0",
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            with pytest.raises(ValueError):
                _load_selected_value_source_request(
                    FileSystemCAS(store.root), ArtifactRef.model_validate(forged_legacy_ref)
                )
            class EquivalentScopedRequest(gc.ValueOwnerSourceProjectionRequestV2):
                pass

            equivalent_request = EquivalentScopedRequest.model_validate(
                request.model_dump(mode="python")
            )
            gateway = gc.RealValueOwnerGateway(
                repo_root=source.repo_root,
                catalog_overlay_path=source.overlay_path,
                catalog_serving_source=source_context,
                artifact_store=store,
                activated_observation_projection=outcome_projection,
                source_projection_request=equivalent_request,
            )
            subclass_profile = gateway.load_value_data_profile(
                candidate=candidate, problem=problem, world_record=world
            )
            assert subclass_profile.schema_version == "policyos.runtime.value_data_profile.v3"
            assert subclass_profile.rows == first.rows
            assert (
                subclass_profile.scope_selection_content_sha256
                == first.scope_selection_content_sha256
            )
            with controlled_builtin_foundry_method_registry_scope() as (registry, report):
                port = gc.FoundryValuePort(
                    evaluation_context=_simulation_execution_context(
                        candidate=candidate, simulation=simulation, problem=problem
                    ),
                    owner_gateway=gateway,
                    requested_method_fqn=AIPWEstimator.signature.fqn,
                    artifact_store=store,
                    method_registry=registry,
                    method_registry_report=report,
                )
                observation = port(
                    candidate=candidate, simulation=simulation, problem=problem, cycle_index=0
                )
                assert observation.status == "value_blocked", observation.reason
                assert observation.authority_blockers == (
                    "candidate_fixture_value_run_not_authority",
                )
                basis_ref = observation._candidate_method_run_basis_ref
                value_ref = observation._candidate_method_value_ref
                assert basis_ref is not None and value_ref is not None
                fresh_store = ensure_ir_artifact_store(FileSystemCAS(store.root))
                basis = gc.ValueOwnerMethodRunBasisV2.model_validate(
                    gc._value_load_ref_payload(fresh_store, basis_ref)
                )
                intent = gc.ValueOwnerMethodRunIntentV1.model_validate(
                    gc._value_load_ref_payload(fresh_store, basis.intent_ref)
                )
                assignment = gc.ValueOwnerSourceVariableAssignmentV1.model_validate(
                    gc._value_load_ref_payload(fresh_store, intent.assignment_ref)
                )
                assert all(
                    gc.ValueDataProfile.model_validate(
                        gc._value_load_ref_payload(fresh_store, role.profile_ref)
                    ).schema_version
                    == "policyos.runtime.value_data_profile.v3"
                    for role in assignment.role_profiles
                )
                first_role = assignment.role_profiles[0]
                scoped_profile = gc.ValueDataProfile.model_validate(
                    gc._value_load_ref_payload(fresh_store, first_role.profile_ref)
                )
                wrong_profile = gc._value_artifact_ref(
                    put_json_artifact(
                        fresh_store,
                        scoped_profile.model_dump(mode="json"),
                        kind="runtime.value_data_profile",
                        schema_name="runtime.value_data_profile.v2",
                        schema_version="2.0",
                        inputs=[
                            gc._value_input_ref(
                                first_role.projection_ref, role="activated_source_projection"
                            )
                        ],
                        canon_spec=CanonSpec(forbid_floats=False),
                        return_selected_profile=True,
                    )
                )
                assert wrong_profile.artifact_id == first_role.profile_ref.artifact_id
                assert wrong_profile.manifest_profile_sha256 != (
                    first_role.profile_ref.manifest_profile_sha256
                )
                changed_roles = (
                    first_role.model_copy(update={"profile_ref": wrong_profile}),
                    *assignment.role_profiles[1:],
                )
                assignment_payload = assignment.model_dump(mode="json", exclude={"content_hash"})
                assignment_payload["role_profiles"] = [
                    role.model_dump(mode="json") for role in changed_roles
                ]
                wrong_assignment = gc.ValueOwnerSourceVariableAssignmentV1.model_validate(
                    {**assignment_payload, "content_hash": gc.gy_content_hash(assignment_payload)}
                )
                assignment_edges = [
                    edge
                    for role in wrong_assignment.role_profiles
                    for edge in (
                        gc._value_input_ref(
                            role.profile_ref,
                            role=f"selected_source_profile:{role.role}:{role.variable_id}",
                        ),
                        gc._value_input_ref(
                            role.projection_ref,
                            role=f"selected_source_projection:{role.role}:{role.variable_id}",
                        ),
                    )
                ]
                wrong_assignment_ref = _persist_json(
                    fresh_store,
                    wrong_assignment.model_dump(mode="json"),
                    kind="runtime.value_owner_source_variable_assignment",
                    schema="runtime.value_owner_source_variable_assignment.v1",
                    inputs=assignment_edges,
                )
                with pytest.raises(ValueError, match="value_owner_source_profile_schema_mismatch"):
                    gc._value_source_profiles_from_store(
                        fresh_store, wrong_assignment, wrong_assignment_ref
                    )
                trust = gc.DataTrust(
                    tier="candidate_fixture",
                    trust_cap=0.0,
                    trust_multiplier=0.0,
                    min_coverage=0.0,
                    max_coverage=1.0,
                    promotion_floor=1.0,
                    authority_ref="candidate_fixture://value_method_run",
                )
                consumer_inputs = {
                    "store": fresh_store,
                    "run_basis_ref": basis_ref,
                    "world_record": world,
                    "data_trust": trust,
                    "source_gateway": gateway,
                    "candidate": candidate,
                    "problem": problem,
                    "registry": registry,
                    "registry_report": report,
                    "selection_inputs": port._selection_inputs(),
                }
                fresh_value = gc._value_outer_set_from_owner_method_run_basis(**consumer_inputs)
                selected = _reconcile_selected_outer_set(
                    fresh_store,
                    value_ref=value_ref,
                    run_basis_ref=basis_ref,
                    recomputed=fresh_value,
                )
                assert selected.representation_status == "search_only"
                assert not selected.promotion_decision().promotable

                changed_request = request.model_copy(
                    update={
                        "measurement_scope": scope.model_copy(
                            update={"period_start": date(1879, 1, 1)}
                        )
                    }
                )
                changed_gateway = replace(gateway, source_projection_request=changed_request)
                with pytest.raises(ValueError, match="value_owner_source_fresh_profile_changed"):
                    gc._value_outer_set_from_owner_method_run_basis(
                        **{**consumer_inputs, "source_gateway": changed_gateway}
                    )

                raw_blob = store._member_path(
                    ArtifactID.model_validate(outcome_passport.raw_artifact_id), "blob", None
                )
                original = raw_blob.read_bytes()
                raw_blob.unlink()
                try:
                    with pytest.raises(gc.ValueOwnerAccessError) as refused:
                        gc._value_outer_set_from_owner_method_run_basis(**consumer_inputs)
                    assert (
                        refused.value.code
                        == "acquire_data:active_observation_owner_readback_failed"
                    )
                finally:
                    raw_blob.write_bytes(original)
                assert (
                    gc._value_outer_set_from_owner_method_run_basis(**consumer_inputs) == selected
                )
    finally:
        source.overlay.close()
