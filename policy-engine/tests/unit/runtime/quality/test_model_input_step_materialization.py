"""Actual native annual inputs, fixed-price arithmetic and temporal artifact replay."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from functools import partial as bind_arguments
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    SchemaInfo,
    artifact_ref_identity_key,
    load_core_json_artifact,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import (
    DataSnapshot,
    load_registered_derived_input_context,
    load_registered_derived_input_correspondence,
    load_resolved_input_binding_manifest,
    load_variable_representation,
)
from polisyos.core.contracts.semantic_composition_binding import (
    persist_registered_derived_input_profile,
)
from polisyos.core.contracts.semantic_step_binding import recompute_resolved_step_input_coverage
from polisyos.core.contracts.variable_binding import (
    VariableRepresentationRef,
    variable_representation_manifest_inputs,
)
from polisyos.core.derivations import resolve_certified_composition
from polisyos.runtime.quality.data_snapshot_lineage import (
    DataSnapshotLineageError,
    validate_data_snapshot_owner_lineage,
)
from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
from polisyos.runtime.quality.model_input_step_materialization import (
    RegisteredDerivedModelInputStepRequest,
    prepare_registered_derived_model_input_steps,
)
from tests._helpers import registered_derived_method_input as registered_fixture
from tests._helpers.registered_derived_method_input import prepare_registered_method_input_request
from tests._helpers.temporal_registered_method_inputs import (
    prepare_temporal_registered_method_inputs,
)
from tests._helpers.temporal_selected_method_input import constant_price_two_year_method_spec
from tests.unit.core.contracts.test_semantic_derived_binding import _put_contract
from tests.unit.foundry.data_plane.test_selected_method_input_bindings import _removed_blob


def test_native_step_preparation_replays_partial_and_complete_fixed_price_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = prepare_temporal_registered_method_inputs(tmp_path)
    case = fixture.case
    try:
        numerical_calls = []

        def forbid_n5(*args, **kwargs):
            numerical_calls.append(True)
            pytest.fail("temporal input preparation must not dispatch N5")

        monkeypatch.setattr(JointSimulationHorizonController, "run", forbid_n5)
        partial = prepare_registered_derived_model_input_steps(
            case.store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=fixture.preflight.obligation_set_ref,
            inputs=fixture.requests[:1],
        )
        fresh = FileSystemCAS.open_existing_read_only(case.store.root)
        partial_manifest = load_resolved_input_binding_manifest(
            fresh, partial.resolved_binding_manifest_ref
        )
        partial_bytes = fresh.get_bytes(partial.resolved_binding_manifest_ref)
        assert partial.coverage.missing_step_scopes == (fixture.requests[1].step_scope,)
        assert recompute_resolved_step_input_coverage(fresh, partial_manifest) == partial.coverage
        with pytest.raises(ValueError, match="model_input_step_coverage_incomplete"):
            partial.coverage.require_complete()
        partial_snapshot = validate_core_model_json_artifact(
            DataSnapshot, fresh, partial.data_snapshot_ref
        )
        assert fresh.get_manifest(partial_snapshot.data_ref).artifact_schema == SchemaInfo(
            name="polisyos.runtime.quality.DerivedModelInputPayload", version="1.1"
        )
        assert set(load_core_json_artifact(fresh, partial_snapshot.data_ref)) == {"derived_inputs"}
        validate_data_snapshot_owner_lineage(
            fresh, partial.data_snapshot_ref, partial_snapshot, candidate_only=True
        )
        assert not hasattr(partial, "input_bindings_ref")

        prepare_full = bind_arguments(
            prepare_registered_derived_model_input_steps,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=fixture.preflight.obligation_set_ref,
            inputs=tuple(reversed(fixture.requests)),
        )
        second_occurrence = fixture.requests[1].request.role_occurrences[0].occurrence_ref
        assert all(
            role.occurrence_ref.artifact_id != second_occurrence.artifact_id
            for role in fixture.requests[0].request.role_occurrences
        )
        with _removed_blob(case.store, second_occurrence):
            restarted = FileSystemCAS(case.store.root)
            with pytest.raises(ValueError, match=r"^selected_occurrence_source_replay_failed$"):
                prepare_full(restarted)

            fresh = FileSystemCAS.open_existing_read_only(case.store.root)
            assert fresh.get_bytes(partial.resolved_binding_manifest_ref) == partial_bytes
            retained = load_resolved_input_binding_manifest(
                fresh, partial.resolved_binding_manifest_ref
            )
            coverage = recompute_resolved_step_input_coverage(fresh, retained)
            assert coverage == partial.coverage
            with pytest.raises(ValueError, match=r"^model_input_step_coverage_incomplete$"):
                coverage.require_complete()
            manifests_at_refusal = set(
                (case.store.root / "artifacts" / "sha256").glob("*/*/*.manifest.json")
            )

        full = prepare_full(FileSystemCAS(case.store.root))
        for ref in (full.data_snapshot_ref, full.resolved_binding_manifest_ref):
            assert ref.manifest_profile_sha256 is not None
            selected_path = case.store._manifest_path_for_ref(
                ref.artifact_id, ref.manifest_profile_sha256
            )
            assert selected_path.is_file() and selected_path not in manifests_at_refusal
        fresh = FileSystemCAS.open_existing_read_only(case.store.root)
        full_manifest = load_resolved_input_binding_manifest(
            fresh, full.resolved_binding_manifest_ref
        )
        assert full.coverage.is_complete
        assert recompute_resolved_step_input_coverage(fresh, full_manifest) == full.coverage
        assert full_manifest.model_input_obligation_set_ref == (
            partial_manifest.model_input_obligation_set_ref
        )
        assert full_manifest.method_input_steps[0] == partial_manifest.method_input_steps[0]
        assert fresh.get_bytes(partial.resolved_binding_manifest_ref) == partial_bytes
        observed = []
        for row, expected in zip(full_manifest.method_input_steps, fixture.spec.rows, strict=True):
            proof = load_registered_derived_input_correspondence(
                fresh, row.selection.correspondence_ref
            )
            context = load_registered_derived_input_context(fresh, proof.context_ref)
            assert (context.schema_version, proof.schema_version) == ("1.1", "2.1")
            assert context.step_scope == proof.step_scope == row.step_scope
            assert context.output_scope == row.step_scope.scope
            assert artifact_ref_identity_key(
                context.obligation_set_ref
            ) == artifact_ref_identity_key(fixture.preflight.obligation_set_ref)
            resolved = resolve_certified_composition(
                fresh,
                certificate_ref=row.selection.certificate_ref,
                consumer_method_id="tests.temporal-fixed-price-input-oracle",
            )
            assert tuple((point.year, point.value) for point in resolved.series.points) == (
                (expected.year, expected.expected_flow),
            )
            observed.append(resolved.series.points[0].value)
        assert observed == [Decimal("-6000000000"), Decimal("4200000000")]
        full_snapshot = validate_core_model_json_artifact(
            DataSnapshot, fresh, full.data_snapshot_ref
        )
        validate_data_snapshot_owner_lineage(
            fresh, full.data_snapshot_ref, full_snapshot, candidate_only=True
        )
        with pytest.raises(
            DataSnapshotLineageError, match="derived_model_input_steps_candidate_only"
        ):
            validate_data_snapshot_owner_lineage(
                fresh, full.data_snapshot_ref, full_snapshot, candidate_only=False
            )
        assert numerical_calls == []
    finally:
        case.close()


def test_native_step_preparation_refuses_wrong_year_and_missing_selected_source(
    tmp_path: Path,
) -> None:
    original = constant_price_two_year_method_spec()
    first_input, second_input = original.rows
    equal_value_spec = replace(
        original,
        rows=(
            first_input,
            replace(
                second_input,
                ratio=first_input.ratio,
                denominator=first_input.denominator,
                expected_flow=first_input.expected_flow,
            ),
        ),
        expected_closing_stock=Decimal("-2000000000"),
    )
    fixture = prepare_temporal_registered_method_inputs(tmp_path, spec=equal_value_spec)
    case = fixture.case
    try:
        first, second = fixture.requests
        correct_second = prepare_registered_derived_model_input_steps(
            case.store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=fixture.preflight.obligation_set_ref,
            inputs=(second,),
        )
        selected = load_resolved_input_binding_manifest(
            case.store, correct_second.resolved_binding_manifest_ref
        ).method_input_steps[0]
        resolved = resolve_certified_composition(
            case.store,
            certificate_ref=selected.selection.certificate_ref,
            consumer_method_id="tests.same-value-different-year-positive",
        )
        assert resolved.series.points[0].value == first_input.expected_flow
        wrong_year = RegisteredDerivedModelInputStepRequest(
            step_scope=second.step_scope,
            request=first.request,
        )
        with pytest.raises(ValueError, match="composition_input_native_"):
            prepare_registered_derived_model_input_steps(
                case.store,
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=fixture.preflight.obligation_set_ref,
                inputs=(wrong_year,),
            )
        source_ref = first.request.role_occurrences[0].occurrence_ref
        with _removed_blob(case.store, source_ref), pytest.raises((ValueError, OSError)):
            prepare_registered_derived_model_input_steps(
                FileSystemCAS(case.store.root),
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=fixture.preflight.obligation_set_ref,
                inputs=(first,),
            )
        restored = prepare_registered_derived_model_input_steps(
            case.store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=fixture.preflight.obligation_set_ref,
            inputs=(first,),
        )
        assert restored.coverage.missing_step_scopes == (second.step_scope,)
    finally:
        case.close()


def test_native_step_preparation_refuses_a_foreign_price_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.data_forge.read_api import catalog
    from polisyos.ir.kernel import MoneyUnit
    from tests._helpers.semantic_epoch_native import NativeEpochFixtureCustodian

    activate = registered_fixture.make_native_multivariable_active_projections
    custodian: NativeEpochFixtureCustodian | None = None

    def activate_under_same_custodian(path, *, artifact_store, **kwargs):
        nonlocal custodian
        if custodian is None:
            custodian = NativeEpochFixtureCustodian.create(artifact_store, tmp_path / "custodian")
        return activate(path, artifact_store=artifact_store, fixture_custodian=custodian, **kwargs)

    monkeypatch.setattr(
        registered_fixture,
        "make_native_multivariable_active_projections",
        activate_under_same_custodian,
    )

    fixture = prepare_temporal_registered_method_inputs(tmp_path)
    case = fixture.case
    try:
        first = fixture.requests[0]
        original = prepare_registered_derived_model_input_steps(
            case.store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=fixture.preflight.obligation_set_ref,
            inputs=(first,),
        )
        assert original.coverage.supplied_step_scopes == (first.step_scope,)
        metadata = dict(fixture.metadata_by_step[0])
        setup = registered_fixture.prepare_registered_method_input_profile(case, metadata)
        role = setup.profile.denominator_role
        basis = next(item.basis for item in setup.profile.inputs if item.role == role)
        representation = load_variable_representation(case.store, basis.representation_ref)
        foreign_representation = representation.model_copy(
            update={
                "representation_id": representation.representation_id + ".foreign-price",
                "revision": "2",
                "money_unit": MoneyUnit(currency="USD", nominal_year=2024, price_base="current"),
            }
        )
        foreign_ref = VariableRepresentationRef.model_validate(
            _put_contract(
                case.store,
                foreign_representation,
                version="3.0",
                inputs=variable_representation_manifest_inputs(foreign_representation),
            ).model_dump(mode="python")
        )
        foreign_profile = setup.profile.model_copy(
            update={
                "inputs": tuple(
                    item.model_copy(
                        update={
                            "basis": item.basis.model_copy(
                                update={"representation_ref": foreign_ref}
                            )
                        }
                    )
                    if item.role == role
                    else item
                    for item in setup.profile.inputs
                )
            }
        )
        foreign_setup = replace(
            setup,
            profile=foreign_profile,
            profile_ref=persist_registered_derived_input_profile(case.store, foreign_profile),
            source_specs=tuple(
                {**spec, "source_representation_ref": foreign_ref}
                if spec["raw_field"] == role
                else spec
                for spec in setup.source_specs
            ),
        )
        # Configure only the synthetic provider fixture. The actual Catalog
        # activation, occurrence replay and production semantic guard remain real.
        with monkeypatch.context() as source_fixture:
            source_fixture.setattr(
                registered_fixture,
                "prepare_registered_method_input_profile",
                lambda *args, **kwargs: foreign_setup,
            )
            foreign = prepare_registered_method_input_request(
                case,
                metadata,
                preflight=fixture.preflight,
                model_input_obligation_ref=first.request.model_input_obligation_ref,
                ratio_value=fixture.spec.rows[0].ratio,
                denominator_value=fixture.spec.rows[0].denominator,
                binding_id="foreign-price-same-value",
                source_year=fixture.spec.rows[0].year,
            )
        original_ref = next(
            row.occurrence_ref for row in first.request.role_occurrences if row.role == role
        )
        changed_ref = next(
            row.occurrence_ref for row in foreign.role_occurrences if row.role == role
        )
        assert artifact_ref_identity_key(original_ref) != artifact_ref_identity_key(changed_ref)
        prior, _, _ = catalog.replay_selected_scoped_measurement_facts(case.store, original_ref)
        changed, _, _ = catalog.replay_selected_scoped_measurement_facts(case.store, changed_ref)
        assert Decimal(prior.canonical_value) == Decimal(changed.canonical_value)
        assert prior.source_scope == changed.source_scope
        with pytest.raises(
            ValueError,
            match=r"^registered_derived_model_input_semantic_refused:.*\bmoney_basis_not_established\b",
        ):
            prepare_registered_derived_model_input_steps(
                case.store,
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=fixture.preflight.obligation_set_ref,
                inputs=(
                    RegisteredDerivedModelInputStepRequest(
                        step_scope=first.step_scope, request=foreign
                    ),
                ),
            )
    finally:
        case.close()


def test_native_step_preparation_refuses_empty_or_duplicate_rows(tmp_path: Path) -> None:
    fixture = prepare_temporal_registered_method_inputs(tmp_path)
    case = fixture.case
    try:
        for inputs, reason in (
            ((), "registered_derived_step_input_no_verified_rows"),
            (
                (fixture.requests[0], fixture.requests[0]),
                "registered_derived_step_input_binding_id_duplicate",
            ),
        ):
            with pytest.raises(ValueError, match=reason):
                prepare_registered_derived_model_input_steps(
                    case.store,
                    base_data_snapshot_ref=case.data_snapshot_ref,
                    obligation_set_ref=fixture.preflight.obligation_set_ref,
                    inputs=inputs,
                )
    finally:
        case.close()
