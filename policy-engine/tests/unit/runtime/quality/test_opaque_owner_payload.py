from __future__ import annotations

import importlib
import json
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

from tests._helpers.catalog_source_admission import admit_fixture_catalog_source

MODULE_NAME = "polisyos.runtime.quality.generation_cycle"
_METHOD_FQN = "causal.treatment_effects.aipw@1.0.0"
_ROLE_BINDINGS = (
    ("outcome", "avg_income"),
    ("treatment", "observed_treatment"),
    ("covariate", "income_covariate"),
)


@pytest.fixture(scope="module")
def generation_cycle_module() -> ModuleType:
    """Return the canonical generation-cycle module from the product source tree."""
    module = importlib.import_module(MODULE_NAME)
    expected_source = (
        Path(__file__).resolve().parents[4] / "src/polisyos/runtime/quality/generation_cycle.py"
    ).resolve()
    assert Path(module.__file__).resolve() == expected_source
    return module


@pytest.fixture(scope="module")
def native_source_fixture(
    generation_cycle_module: ModuleType, tmp_path_factory: pytest.TempPathFactory
):
    """Build real active owner projections; no Foundry estimator is executed."""
    from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections

    source_rows: list[dict[str, object]] = []
    for index in range(200):
        treatment = float(index % 2)
        covariate = float((index // 2) % 2)
        outcome = float((index * 11) % 17 < (6 + int(treatment) + int(covariate)))
        source_rows.append(
            {
                "country_code": "UA",
                "year": 1800 + index,
                "avg_income": outcome,
                "observed_treatment": treatment,
                "income_covariate": covariate,
                "condition_json": '{"unit":"binary"}',
            }
        )
    return make_native_multivariable_active_projections(
        tmp_path_factory.mktemp("opaque-owner-payload-native-source"),
        source_rows=source_rows,
        variable_specs=(
            {
                "target_variable": "avg_income",
                "raw_field": "avg_income",
                "raw_unit": "binary",
                "canonical_unit": "binary",
            },
            {
                "target_variable": "observed_treatment",
                "raw_field": "observed_treatment",
                "raw_unit": "binary",
                "canonical_unit": "binary",
            },
            {
                "target_variable": "income_covariate",
                "raw_field": "income_covariate",
                "raw_unit": "binary",
                "canonical_unit": "binary",
            },
        ),
    )


def _test_helpers() -> ModuleType:
    return importlib.import_module("tests.unit.runtime.quality.test_value_gate")


def _catalog_source(source: object):
    from polisyos.runtime.quality.substrate_registry import (
        default_substrate_catalog_paths,
    )

    substrate_paths = replace(
        default_substrate_catalog_paths(source.repo_root),
        l1_dcat_path=source.baseline_path,
    )
    return admit_fixture_catalog_source(
        repo_root=source.repo_root, database_path=source.baseline_path
    )


def _load_profile(generation_cycle_module: ModuleType, source: object, variable_id: str):
    from polisyos.runtime.quality.data_state_substrate import l1_dcat_variable_availability

    availability = l1_dcat_variable_availability(
        source.repo_root,
        variable_id,
        overlay_path=source.overlay_path,
    )
    assert availability.status == "available"
    profile = generation_cycle_module._load_value_data_profile_from_l1_dcat(
        repo_root=source.repo_root,
        outcome=variable_id,
        owner_access_ref=availability.coverage_ref,
        overlay_path=source.overlay_path,
        artifact_store=source.artifact_store,
        activated_observation_projection=source.projections[variable_id],
    )
    assert isinstance(profile, generation_cycle_module.ValueDataProfile)
    return profile


def _estimand_json() -> str:
    return json.dumps(
        {
            "query_id": "n8-opaque-owner-payload",
            "estimand_id": "ATE",
            "outcome": "avg_income",
            "treatment_or_exposure": "observed_treatment",
            "covariates_or_conditioning": ["income_covariate"],
            "adjustment_set": ["income_covariate"],
            "population": "unspecified",
            "sample_filter": None,
            "time_horizon": None,
            "prediction_origin": None,
            "unit": "binary",
            "scale": "identity",
            "transform": None,
            "target_role": "estimate",
            "loss_or_utility_id": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _source_request(generation_cycle_module: ModuleType, source: object):
    return generation_cycle_module.ValueOwnerSourceProjectionRequestV1(
        selected_method_fqn=_METHOD_FQN,
        estimand_spec_json=_estimand_json(),
        variable_projections=tuple(
            generation_cycle_module.ValueOwnerSourceVariableProjectionV1(
                role=role,
                variable_id=variable_id,
                projection_payload=source.projections[variable_id].model_dump(mode="json"),
            )
            for role, variable_id in _ROLE_BINDINGS
        ),
        outcome_lower=0.0,
        outcome_upper=1.0,
        outcome_bounds_unit="binary",
        method_parameters_json="{}",
        seed=7,
    )


def test_l1_profile_uses_real_passport_and_rejects_present_invalid_owner(
    generation_cycle_module: ModuleType,
    native_source_fixture: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.acquisition_executor import AdmissionStatus
    from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope

    source = native_source_fixture
    projection = source.projections["avg_income"]
    with catalog_serving_source_scope(_catalog_source(source)):
        profile = _load_profile(generation_cycle_module, source, "avg_income")
        assert profile.outcome == "avg_income"
        assert profile.treatment_assignment_status == "owner_assignment_unresolved"
        assert profile.owner_row_count == 200

        real_projection, passport, passport_hash = (
            generation_cycle_module._read_canonical_active_source_projection(
                repo_root=source.repo_root,
                overlay_path=source.overlay_path,
                artifact_store=source.artifact_store,
                supplied_projection=projection,
            )
        )
        assert real_projection.model_dump(mode="json") == projection.model_dump(mode="json")
        assert passport.status in {AdmissionStatus.ADMITTED, AdmissionStatus.ADMITTED_DEGRADED}

        invalid_readbacks: tuple[tuple[object, object, object], ...] = (
            (object(), passport, passport_hash),
            ({"variable_id": "avg_income"}, passport, passport_hash),
            (real_projection, object(), passport_hash),
            (real_projection, {"passport_id": "present-but-untyped"}, passport_hash),
            (real_projection, passport, object()),
        )
        for invalid_projection, invalid_passport, invalid_passport_hash in invalid_readbacks:

            def present_untyped_readback(
                readback: tuple[object, object, object] = (
                    invalid_projection,
                    invalid_passport,
                    invalid_passport_hash,
                ),
                **kwargs: object,
            ) -> tuple[object, object, object]:
                del kwargs
                return readback

            with monkeypatch.context() as invalid_owner:
                invalid_owner.setattr(
                    generation_cycle_module,
                    "_read_canonical_active_source_projection",
                    present_untyped_readback,
                )
                with pytest.raises(generation_cycle_module.ValueOwnerAccessError) as caught:
                    _load_profile(generation_cycle_module, source, "avg_income")
                assert caught.value.code == (
                    "acquire_data:active_observation_projection_binding_mismatch"
                )

        read_canonical_projection = generation_cycle_module._read_canonical_active_source_projection

        def quarantined_passport(**kwargs: object):
            owner_projection, owner_passport, content_hash = read_canonical_projection(**kwargs)
            return (
                owner_projection,
                owner_passport.model_copy(update={"status": AdmissionStatus.QUARANTINED}),
                content_hash,
            )

        with monkeypatch.context() as refused_status:
            refused_status.setattr(
                generation_cycle_module,
                "_read_canonical_active_source_projection",
                quarantined_passport,
            )
            with pytest.raises(generation_cycle_module.ValueOwnerAccessError) as caught:
                _load_profile(generation_cycle_module, source, "avg_income")
            assert caught.value.code == (
                "acquire_data:active_observation_projection_binding_mismatch"
            )

        def unknown_status_passport(**kwargs: object):
            owner_projection, owner_passport, content_hash = read_canonical_projection(**kwargs)
            return (
                owner_projection,
                owner_passport.model_copy(update={"status": "future_unknown_status"}),
                content_hash,
            )

        with monkeypatch.context() as unknown_status:
            unknown_status.setattr(
                generation_cycle_module,
                "_read_canonical_active_source_projection",
                unknown_status_passport,
            )
            with pytest.raises(generation_cycle_module.ValueOwnerAccessError) as caught:
                _load_profile(generation_cycle_module, source, "avg_income")
            assert caught.value.code == (
                "acquire_data:active_observation_projection_binding_mismatch"
            )


def test_source_intent_and_hte_consumer_use_canonical_estimand_and_preserve_limits(
    generation_cycle_module: ModuleType,
    native_source_fixture: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
    from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope

    source = native_source_fixture
    helpers = _test_helpers()
    candidate = helpers._avg_income_candidate()
    problem = helpers._avg_income_problem()
    world = helpers._world_record()
    request = _source_request(generation_cycle_module, source)
    with catalog_serving_source_scope(_catalog_source(source)):
        outcome_profile = _load_profile(generation_cycle_module, source, "avg_income")
        assert (
            generation_cycle_module.ValueOwnerSourceProjectionRequestV1.model_validate(
                request.model_dump(mode="python")
            )
            == request
        )
        gateway = generation_cycle_module.RealValueOwnerGateway(
            repo_root=source.repo_root,
            catalog_overlay_path=source.overlay_path,
            catalog_serving_source=_catalog_source(source),
            artifact_store=source.artifact_store,
            activated_observation_projection=source.projections["avg_income"],
            source_projection_request=request,
        )
        intent = generation_cycle_module._value_owner_source_projection_intent(
            gateway=gateway,
            candidate=candidate,
            problem=problem,
            world_record=world,
            outcome_profile=outcome_profile,
            selected_method_fqn=_METHOD_FQN,
            request=request,
        )
        assert isinstance(intent, generation_cycle_module.ValueOwnerMethodRunIntentV1)
        assert intent.production_value_eligible is False

        ir_store = ensure_ir_artifact_store(source.artifact_store)
        assignment_payload = generation_cycle_module._value_load_ref_payload(
            ir_store, intent.assignment_ref
        )
        assignment = generation_cycle_module.ValueOwnerSourceVariableAssignmentV1.model_validate(
            assignment_payload
        )
        assert assignment.production_value_eligible is False
        assert assignment.assignment_provenance == "consumer_asserted"
        assert assignment.source_time_status == "not_established"
        profiles = generation_cycle_module._value_source_profiles_from_store(
            ir_store,
            assignment,
            intent.assignment_ref,
        )
        panel = generation_cycle_module._value_source_observational_data(assignment, profiles)
        assert isinstance(panel, HTEObservationalData)
        assert panel.outcome.shape == (200,)
        assert panel.metadata["authority_scope"] == "candidate_fixture_only"
        assert panel.metadata["assignment_provenance"] == "consumer_asserted"
        assert panel.metadata["source_time_status"] == "not_established"
        assert panel.metadata["unit_conversion"] == "not_performed"

        with pytest.raises(ValueError, match="value_owner_method_estimand_invalid"):
            generation_cycle_module._value_estimand_spec_from_json("{")

        untyped_estimands: tuple[object, ...] = (
            object(),
            {
                "estimand_id": "ATE",
                "outcome": "avg_income",
                "treatment_or_exposure": "observed_treatment",
            },
        )
        for untyped_estimand in untyped_estimands:

            def present_untyped_estimand(payload: str, result: object = untyped_estimand) -> object:
                del payload
                return result

            with monkeypatch.context() as invalid_estimand:
                invalid_estimand.setattr(
                    generation_cycle_module,
                    "_value_estimand_spec_from_json",
                    present_untyped_estimand,
                )
                with pytest.raises(ValidationError, match="value_owner_method_estimand_invalid"):
                    generation_cycle_module.ValueOwnerSourceProjectionRequestV1.model_validate(
                        request.model_dump(mode="python")
                    )
                with pytest.raises(ValidationError, match="value_owner_method_estimand_invalid"):
                    generation_cycle_module.ValueOwnerSourceVariableAssignmentV1.model_validate(
                        assignment_payload
                    )
                with pytest.raises(ValidationError, match="value_owner_method_estimand_invalid"):
                    generation_cycle_module.ValueOwnerMethodRunIntentV1.model_validate(
                        intent.model_dump(mode="python")
                    )
                with pytest.raises(ValueError, match="value_owner_method_estimand_invalid"):
                    generation_cycle_module._value_owner_source_projection_intent(
                        gateway=gateway,
                        candidate=candidate,
                        problem=problem,
                        world_record=world,
                        outcome_profile=outcome_profile,
                        selected_method_fqn=_METHOD_FQN,
                        request=request,
                    )
                with pytest.raises(ValueError, match="value_owner_method_estimand_invalid"):
                    generation_cycle_module._value_source_observational_data(assignment, profiles)


def test_foundry_value_port_decodes_real_and_present_invalid_selection_payloads_without_fit(
    generation_cycle_module: ModuleType,
    native_source_fixture: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope

    source = native_source_fixture
    helpers = _test_helpers()
    candidate = replace(
        helpers._avg_income_candidate(),
        diversity_key=("grant", "country", "avg_income"),
    )
    problem = helpers._avg_income_problem()
    world = helpers._world_record()
    source_scope = _catalog_source(source)
    simulation_payload = helpers._simulation(world, candidate_id=candidate.candidate_id).model_dump(
        mode="json"
    )
    simulation_payload["world_model_record"] = world
    simulation = generation_cycle_module.SimulationPortObservation.model_validate(
        simulation_payload
    )
    context = helpers._simulation_execution_context(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
    )
    gateway = generation_cycle_module.RealValueOwnerGateway(
        repo_root=source.repo_root,
        catalog_overlay_path=source.overlay_path,
        catalog_serving_source=source_scope,
        artifact_store=source.artifact_store,
        activated_observation_projection=source.projections["avg_income"],
    )
    port = generation_cycle_module.FoundryValuePort(
        evaluation_context=context,
        owner_gateway=gateway,
        requested_method_fqn=_METHOD_FQN,
        artifact_store=source.artifact_store,
    )

    def no_model_run(**kwargs: object) -> object:
        del kwargs
        pytest.fail("the focused value-owner probe must stop before any estimator run")

    monkeypatch.setattr(
        generation_cycle_module, "_produce_value_owner_method_run_basis", no_model_run
    )
    with catalog_serving_source_scope(source_scope):
        invalid_world_records: tuple[object, ...] = (
            object(),
            {
                "world_model_record_id": "world_model_record_0123456789abcdef",
                "content_hash": f"sha256:{'0' * 64}",
            },
        )
        for invalid_world_record in invalid_world_records:

            def untyped_world_record(
                value: object, result: object = invalid_world_record
            ) -> tuple[object, str, None]:
                del value
                return result, "built", None

            with monkeypatch.context() as invalid_wmr:
                invalid_wmr.setattr(
                    port,
                    "_world_record_from_simulation",
                    untyped_world_record,
                )
                invalid = port(
                    candidate=candidate,
                    simulation=simulation,
                    problem=problem,
                    cycle_index=0,
                )
                assert any(
                    blocker.startswith("world_model_record_invalid")
                    for blocker in invalid.authority_blockers
                )
                assert invalid.value_ref is None

        valid = port(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=0,
        )
        assert "treatment_assignment_not_owner_derived" in valid.authority_blockers
        assert valid.value_ref is None

        with monkeypatch.context() as malformed_receipt:
            malformed_receipt.setattr(
                generation_cycle_module,
                "_select_value_method",
                lambda **kwargs: {
                    "status": "selected",
                    "selected_method_fqn": _METHOD_FQN,
                    "selection_receipt": {"present_but_invalid": True},
                },
            )
            invalid = port(
                candidate=candidate,
                simulation=simulation,
                problem=problem,
                cycle_index=0,
            )
            assert "value_method_selection_authority_unresolved" in invalid.authority_blockers
            assert invalid.value_ref is None
