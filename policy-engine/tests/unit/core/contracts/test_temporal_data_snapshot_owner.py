from __future__ import annotations

import json
from datetime import date

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.contracts.fabric import (
    DataSnapshotOwnerBound,
    DerivedModelInputDataSnapshotLineage,
    DerivedModelInputStepDataSnapshotLineage,
    data_snapshot_manifest_inputs_match,
    data_snapshot_owner_input_requirements,
)
from polisyos.core.contracts.model_input_period_steps import ModelInputStepScope
from polisyos.core.contracts.semantic_derived_binding import (
    DerivedInputCorrespondenceRef,
    DerivedInputProfileRef,
)
from polisyos.core.contracts.semantic_input_binding import (
    ResolvedDerivedInput,
    ResolvedDerivedInputAtStep,
)
from polisyos.core.contracts.variable_binding import ModelInputScope, SelectedVariableBindingRef


def _ref(index: int, kind: str, *, media_type: str = "application/json") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(f"{index:064x}"),
        kind=kind,
        media_type=media_type,
        manifest_profile_sha256=f"sha256:{index + 100:064x}",
    )


def _selected_ref(index: int, kind: str) -> SelectedVariableBindingRef:
    return SelectedVariableBindingRef.model_validate(_ref(index, kind).model_dump(mode="python"))


def _resolved_derived_input(
    index: int,
    *,
    binding_id: str,
    year: int,
    source_path: str | None = None,
    obligation_ref: SelectedVariableBindingRef | None = None,
) -> ResolvedDerivedInput:
    return ResolvedDerivedInput(
        binding_id=binding_id,
        model_input_obligation_ref=obligation_ref
        or _selected_ref(index, "runtime.quality.model_input_obligation"),
        model_interface_ref=_selected_ref(
            index + 1, "runtime.quality.program_graph_input_interface"
        ),
        model_port_id="method.input.value",
        recipe_ref=_selected_ref(index + 2, "polisyos.runtime.derivation_recipe"),
        certificate_ref=_selected_ref(index + 3, "polisyos.runtime.derivation_certificate"),
        output_ref=_selected_ref(index + 4, "polisyos.runtime.derived_economic_series"),
        year=year,
        correspondence_ref=DerivedInputCorrespondenceRef.model_validate(
            _selected_ref(index + 5, "catalog.derived_input_correspondence").model_dump(
                mode="python"
            )
        ),
        profile_ref=DerivedInputProfileRef.model_validate(
            _selected_ref(index + 6, "catalog.derived_input_profile").model_dump(mode="python")
        ),
        source_path=source_path or f"outputs.{year}",
    )


def _at_step(
    index: int,
    *,
    binding_id: str,
    step: int,
    year: int,
    source_path: str | None = None,
    obligation_ref: SelectedVariableBindingRef | None = None,
    port_id: str = "method.input.value",
) -> ResolvedDerivedInputAtStep:
    scope = ModelInputScope(
        population_ref="population:fixture",
        geography_ref="UA",
        jurisdiction_ref="jurisdiction:fixture",
        period_start=date(year, 1, 1),
        period_end=date(year, 12, 31),
        time_role="observation_time",
        period_basis="calendar_year",
    )
    return ResolvedDerivedInputAtStep(
        step_scope=ModelInputStepScope(port_id=port_id, step=step, scope=scope),
        selection=_resolved_derived_input(
            index,
            binding_id=binding_id,
            year=year,
            source_path=source_path,
            obligation_ref=obligation_ref,
        ),
    )


def _lineage(
    selections: tuple[ResolvedDerivedInputAtStep, ...],
) -> DerivedModelInputStepDataSnapshotLineage:
    return DerivedModelInputStepDataSnapshotLineage(
        base_data_snapshot_ref=_selected_ref(900, "fabric.data_snapshot"),
        model_input_obligation_set_ref=_selected_ref(
            901, "runtime.quality.model_input_obligation_set"
        ),
        selections=selections,
    )


def _snapshot(lineage: DerivedModelInputStepDataSnapshotLineage) -> DataSnapshotOwnerBound:
    return DataSnapshotOwnerBound(
        data_ref=_ref(902, "runtime.quality.derived_semantic_input_payload"),
        source_lineage=lineage,
    )


def _manifest_inputs(snapshot: DataSnapshotOwnerBound) -> list[InputRef]:
    return [
        InputRef(
            artifact_id=ref.artifact_id,
            role=role,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        for ref, role in data_snapshot_owner_input_requirements(snapshot)
    ]


def test_old_derived_model_input_lineage_round_trips_literal_one_step_json() -> None:
    expected_payload = {
        "schema_version": "polisyos.core.DataSnapshotOwnerLineage.v1",
        "owner": "derived_model_input",
        "authority_purpose": "candidate_simulation_input_only",
        "lineage_status": "not_established",
        "base_data_snapshot_ref": {
            "artifact_id": "sha256:" + "1" * 64,
            "kind": "fabric.data_snapshot",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "a" * 64,
        },
        "model_input_obligation_set_ref": {
            "artifact_id": "sha256:" + "2" * 64,
            "kind": "runtime.quality.model_input_obligation_set",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "b" * 64,
        },
        "selections": [
            {
                "binding_id": "annual-2024",
                "model_input_obligation_ref": {
                    "artifact_id": "sha256:" + "3" * 64,
                    "kind": "runtime.quality.model_input_obligation",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "c" * 64,
                },
                "model_interface_ref": {
                    "artifact_id": "sha256:" + "4" * 64,
                    "kind": "runtime.quality.program_graph_input_interface",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "d" * 64,
                },
                "model_port_id": "method.input.value",
                "recipe_ref": {
                    "artifact_id": "sha256:" + "5" * 64,
                    "kind": "polisyos.runtime.derivation_recipe",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "e" * 64,
                },
                "certificate_ref": {
                    "artifact_id": "sha256:" + "6" * 64,
                    "kind": "polisyos.runtime.derivation_certificate",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "f" * 64,
                },
                "output_ref": {
                    "artifact_id": "sha256:" + "7" * 64,
                    "kind": "polisyos.runtime.derived_economic_series",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "0" * 64,
                },
                "year": 2024,
                "correspondence_ref": {
                    "artifact_id": "sha256:" + "8" * 64,
                    "kind": "catalog.derived_input_correspondence",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "9" * 64,
                },
                "profile_ref": {
                    "artifact_id": "sha256:" + "a" * 64,
                    "kind": "catalog.derived_input_profile",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "b" * 64,
                },
                "source_path": "outputs.2024",
            }
        ],
    }

    lineage = DerivedModelInputDataSnapshotLineage.model_validate_json(json.dumps(expected_payload))

    assert lineage.model_dump(mode="json") == expected_payload


def test_step_lineage_allows_same_obligation_at_distinct_steps_and_partial_candidate() -> None:
    first = _at_step(index=10, binding_id="growth-2020", step=0, year=2020)
    second = _at_step(
        index=20,
        binding_id="growth-2021",
        step=1,
        year=2021,
        obligation_ref=first.selection.model_input_obligation_ref,
    )
    two_steps = _lineage((first, second))

    assert tuple(
        (item.step_scope.port_id, item.step_scope.step) for item in two_steps.selections
    ) == (("method.input.value", 0), ("method.input.value", 1))
    assert (
        two_steps.selections[0].selection.model_input_obligation_ref.artifact_id
        == two_steps.selections[1].selection.model_input_obligation_ref.artifact_id
    )

    partial = _lineage((first,))
    assert len(partial.selections) == 1
    assert partial.authority_purpose == "candidate_simulation_input_only"
    assert partial.lineage_status == "not_established"
    assert "completeness" not in partial.model_dump(mode="json")


def test_step_owner_requirements_reconcile_exact_full_edges_and_reject_changes() -> None:
    selections = (
        _at_step(index=30, binding_id="growth-2020", step=0, year=2020),
        _at_step(index=40, binding_id="growth-2021", step=1, year=2021),
    )
    snapshot = _snapshot(_lineage(selections))
    requirements = data_snapshot_owner_input_requirements(snapshot)
    selection_roles = [role for selection in selections for _ref, role in selection.lineage_refs()]
    assert [role for _ref, role in requirements] == [
        "payload.derived_model_input_steps",
        "input.base_data_snapshot",
        "selected_obligation_set",
        *selection_roles,
    ]
    assert selection_roles == [
        f"binding.{binding_id}.{suffix}"
        for binding_id in ("growth-2020", "growth-2021")
        for suffix in (
            "obligation",
            "interface",
            "recipe",
            "certificate",
            "output",
            "correspondence",
            "profile",
        )
    ]

    actual_inputs = _manifest_inputs(snapshot)
    assert data_snapshot_manifest_inputs_match(snapshot, actual_inputs, schema_version="0.3.0")
    assert not data_snapshot_manifest_inputs_match(
        snapshot, actual_inputs[:-1], schema_version="0.3.0"
    )
    grafted = list(actual_inputs)
    grafted[-1] = grafted[-1].model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
    assert not data_snapshot_manifest_inputs_match(snapshot, grafted, schema_version="0.3.0")


def test_step_lineage_rejects_duplicate_step_binding_and_source_path_keys() -> None:
    with pytest.raises(ValueError, match="derived_model_input_step_snapshot_steps_not_unique"):
        _lineage(
            (
                _at_step(index=50, binding_id="growth-a", step=0, year=2020),
                _at_step(index=60, binding_id="growth-b", step=0, year=2020),
            )
        )

    with pytest.raises(ValueError, match="derived_model_input_step_snapshot_selections_not_unique"):
        _lineage(
            (
                _at_step(index=70, binding_id="growth-same", step=0, year=2020),
                _at_step(index=80, binding_id="growth-same", step=1, year=2021),
            )
        )

    with pytest.raises(ValueError, match="derived_model_input_step_snapshot_selections_not_unique"):
        _lineage(
            (
                _at_step(
                    index=90,
                    binding_id="growth-a",
                    step=0,
                    year=2020,
                    source_path="outputs.selected",
                ),
                _at_step(
                    index=100,
                    binding_id="growth-b",
                    step=1,
                    year=2021,
                    source_path="outputs.selected",
                ),
            )
        )


def test_step_lineage_requires_sorted_coordinates_and_selected_root_refs() -> None:
    with pytest.raises(ValueError, match="derived_model_input_step_snapshot_steps_not_sorted"):
        _lineage(
            (
                _at_step(index=110, binding_id="growth-2021", step=1, year=2021),
                _at_step(index=120, binding_id="growth-2020", step=0, year=2020),
            )
        )

    selected = _at_step(index=130, binding_id="growth-2020", step=0, year=2020)
    fields = {
        "selections": (selected,),
        "base_data_snapshot_ref": _selected_ref(131, "fabric.data_snapshot"),
        "model_input_obligation_set_ref": _selected_ref(
            132, "runtime.quality.model_input_obligation_set"
        ),
    }
    with pytest.raises(ValueError, match="derived_model_input_step_snapshot_lineage_ref_mismatch"):
        DerivedModelInputStepDataSnapshotLineage(
            **(fields | {"base_data_snapshot_ref": _selected_ref(131, "fixture.foreign")})
        )
    with pytest.raises(ValueError, match="derived_model_input_step_snapshot_lineage_ref_mismatch"):
        DerivedModelInputStepDataSnapshotLineage(
            **(
                fields
                | {
                    "model_input_obligation_set_ref": fields[
                        "model_input_obligation_set_ref"
                    ].model_copy(update={"manifest_profile_sha256": None})
                }
            )
        )
    with pytest.raises(ValueError, match="derived_model_input_step_snapshot_lineage_ref_mismatch"):
        DerivedModelInputStepDataSnapshotLineage(
            **(
                fields
                | {
                    "base_data_snapshot_ref": _ref(
                        131, "fabric.data_snapshot", media_type="text/plain"
                    )
                }
            )
        )


def test_step_lineage_rejects_unsupported_authority_fields_and_values() -> None:
    selected = _at_step(index=140, binding_id="growth-2020", step=0, year=2020)
    fields = {
        "base_data_snapshot_ref": _selected_ref(141, "fabric.data_snapshot"),
        "model_input_obligation_set_ref": _selected_ref(
            142, "runtime.quality.model_input_obligation_set"
        ),
        "selections": (selected,),
    }

    with pytest.raises(ValidationError):
        DerivedModelInputStepDataSnapshotLineage(
            **(fields | {"publication_authority_ref": _ref(143, "fixture.authority")})
        )
    with pytest.raises(ValidationError):
        DerivedModelInputStepDataSnapshotLineage(**(fields | {"authority_purpose": "publishable"}))
    with pytest.raises(ValidationError):
        DerivedModelInputStepDataSnapshotLineage(**(fields | {"lineage_status": "resolved"}))
