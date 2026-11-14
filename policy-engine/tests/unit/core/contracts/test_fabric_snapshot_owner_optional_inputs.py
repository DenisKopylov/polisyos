from __future__ import annotations

from hashlib import sha256

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.fabric import (
    AcquiredObservationDataSnapshotLineage,
    DataSnapshot,
    DataSnapshotOwnerBound,
    DataViewRequestRef,
    DerivedModelInputDataSnapshotLineage,
    EvidenceBundleRef,
    FabricBridgeDataSnapshotLineage,
    MeasurementRootDataSnapshotLineage,
    UncertaintyBoundsRef,
    WarningsRef,
    data_snapshot_manifest_inputs_match,
    data_snapshot_owner_input_requirements,
)
from polisyos.core.contracts.semantic_derived_binding import (
    DerivedInputCorrespondenceRef,
    DerivedInputProfileRef,
)
from polisyos.core.contracts.semantic_input_binding import ResolvedDerivedInput
from polisyos.core.contracts.variable_binding import SelectedVariableBindingRef


def _ref(index: int, kind: str = "fixture.artifact") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(f"{index:064x}"),
        kind=kind,
        media_type="application/json",
    )


def _selected_ref(index: int, kind: str) -> SelectedVariableBindingRef:
    return SelectedVariableBindingRef.model_validate(
        _ref(index, kind).model_dump(mode="python")
        | {"manifest_profile_sha256": "sha256:" + f"{index + 100:064x}"}
    )


def _resolved_derived_input(index: int, *, binding_id: str, year: int) -> ResolvedDerivedInput:
    return ResolvedDerivedInput(
        binding_id=binding_id,
        model_input_obligation_ref=_selected_ref(index, "runtime.quality.model_input_obligation"),
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
        source_path=f"outputs.{year}",
    )


def _bridge_snapshot(
    snapshot_type: type[DataSnapshot],
    *,
    evidence_ref: EvidenceBundleRef | None = None,
    warnings_ref: WarningsRef | None = None,
    uncertainty_ref: UncertaintyBoundsRef | None = None,
) -> DataSnapshot:
    return snapshot_type(
        data_ref=_ref(1, "fabric.tabular_payload"),
        data_schema_ref=_ref(2, "fabric.data_schema"),
        evidence_ref=evidence_ref,
        quality_report_ref=_ref(3, "fabric.quality_report"),
        warnings_ref=warnings_ref,
        uncertainty_ref=uncertainty_ref,
        source_lineage=FabricBridgeDataSnapshotLineage(
            data_view_request_ref=DataViewRequestRef(
                artifact_id=ArtifactID.from_sha256_hex(f"{4:064x}"),
                kind="ir.data_view_request",
                media_type="application/json",
            )
        ),
    )


@pytest.mark.parametrize("snapshot_type", [DataSnapshot, DataSnapshotOwnerBound])
def test_fabric_bridge_owner_inputs_allow_absent_optional_fetch_refs(
    snapshot_type: type[DataSnapshot],
) -> None:
    snapshot = _bridge_snapshot(snapshot_type)

    requirements = data_snapshot_owner_input_requirements(snapshot)

    assert [role for _ref, role in requirements] == [
        "data_ref",
        "data_schema_ref",
        "quality_report_ref",
        "data_view_request_ref",
    ]


@pytest.mark.parametrize("snapshot_type", [DataSnapshot, DataSnapshotOwnerBound])
def test_fabric_bridge_owner_inputs_include_optional_refs_when_present(
    snapshot_type: type[DataSnapshot],
) -> None:
    snapshot = _bridge_snapshot(
        snapshot_type,
        evidence_ref=EvidenceBundleRef(
            artifact_id=ArtifactID.from_sha256_hex(f"{5:064x}"),
            kind="fabric.evidence_bundle",
            media_type="application/json",
        ),
        warnings_ref=WarningsRef(
            artifact_id=ArtifactID.from_sha256_hex(f"{6:064x}"),
            kind="fabric.warnings",
            media_type="application/json",
        ),
    )

    requirements = data_snapshot_owner_input_requirements(snapshot)

    assert [role for _ref, role in requirements] == [
        "data_ref",
        "data_schema_ref",
        "evidence_ref",
        "quality_report_ref",
        "warnings_ref",
        "data_view_request_ref",
    ]


@pytest.mark.parametrize("snapshot_type", [DataSnapshot, DataSnapshotOwnerBound])
def test_owner_input_requirements_preserve_none_semantics_for_all_families(
    snapshot_type: type[DataSnapshot],
) -> None:
    bridge = _bridge_snapshot(snapshot_type)
    measurement = snapshot_type(
        data_ref=_ref(7, "fabric.fetch_payload"),
        source_lineage=MeasurementRootDataSnapshotLineage(
            measurement_root_ref=_ref(8, "policyos.gy.measurement_root_payload"),
            fetch_receipt_ref=_ref(9, "fabric.fetch_receipt"),
            catalog_binding_ref=_ref(10, "fabric.catalog_binding"),
        ),
    )
    acquired = snapshot_type(
        data_ref=_ref(11, "fabric.production_data_state_payload"),
        source_lineage=AcquiredObservationDataSnapshotLineage(
            base_data_snapshot_ref=_ref(12, "fabric.data_snapshot"),
            overlay_admission_receipt_ref=_ref(13, "evidence.overlay_admission_receipt"),
            passport_ref=_ref(14, "evidence.acquisition_passport"),
        ),
    )

    bridge_inputs = data_snapshot_owner_input_requirements(bridge)
    measurement_inputs = data_snapshot_owner_input_requirements(measurement)
    acquired_inputs = data_snapshot_owner_input_requirements(acquired)

    assert len(bridge_inputs) == 4
    assert [role for _ref, role in measurement_inputs] == [
        "fetched_payload",
        "measurement_root",
        "fabric_fetch",
        "catalog_binding",
    ]
    assert [role for _ref, role in acquired_inputs] == [
        "payload.acquired_observation_candidate",
        "input.base_data_snapshot",
        "evidence.overlay_admission_receipt",
        "evidence.acquisition_passport",
    ]


def test_legacy_data_snapshot_payload_bytes_remain_unchanged() -> None:
    legacy = DataSnapshot(data_ref=_ref(70, "fabric.tabular_payload"))
    owner_bound = _bridge_snapshot(DataSnapshotOwnerBound)

    legacy_bytes = to_canonical_bytes(legacy.model_dump(mode="json"), CanonSpec())
    owner_bound_bytes = to_canonical_bytes(owner_bound.model_dump(mode="json"), CanonSpec())

    assert sha256(legacy_bytes).hexdigest() == (
        "9cbe3d9ee453ca0a9fb851cc43cf635b27d3c512863e752ac068938bb9172d16"
    )
    assert sha256(owner_bound_bytes).hexdigest() == (
        "406589fd72e20855da2c7bd484284ec5cee4bc2f48f34c3a784cc7c676a4886d"
    )


def test_derived_model_input_snapshot_uses_complete_selected_lineage_edges() -> None:
    selections = (
        _resolved_derived_input(20, binding_id="annual-2024", year=2024),
        _resolved_derived_input(30, binding_id="annual-2025", year=2025),
    )
    lineage = DerivedModelInputDataSnapshotLineage(
        base_data_snapshot_ref=_ref(18, "fabric.data_snapshot").model_copy(
            update={"manifest_profile_sha256": "sha256:" + f"{118:064x}"}
        ),
        model_input_obligation_set_ref=_ref(
            19, "runtime.quality.model_input_obligation_set"
        ).model_copy(update={"manifest_profile_sha256": "sha256:" + f"{119:064x}"}),
        selections=selections,
    )
    snapshot = DataSnapshotOwnerBound(
        data_ref=_ref(17, "runtime.quality.derived_semantic_input_payload"),
        source_lineage=lineage,
    )

    requirements = data_snapshot_owner_input_requirements(snapshot)
    expected_selection_roles = [
        edge.role for selection in selections for edge in selection.lineage_inputs()
    ]
    assert [role for _ref, role in requirements] == [
        "payload.derived_model_input",
        "input.base_data_snapshot",
        "selected_obligation_set",
        *expected_selection_roles,
    ]
    assert lineage.authority_purpose == "candidate_simulation_input_only"
    assert lineage.lineage_status == "not_established"

    actual_inputs = [
        InputRef(
            artifact_id=ref.artifact_id,
            role=role,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        for ref, role in requirements
    ]
    assert data_snapshot_manifest_inputs_match(snapshot, actual_inputs, schema_version="0.3.0")
    assert not data_snapshot_manifest_inputs_match(
        snapshot, actual_inputs[:-1], schema_version="0.3.0"
    )
    assert not data_snapshot_manifest_inputs_match(
        snapshot,
        [*actual_inputs, actual_inputs[-1]],
        schema_version="0.3.0",
    )


def test_derived_model_input_snapshot_rejects_duplicate_selection_denominator_rows() -> None:
    selected = _resolved_derived_input(40, binding_id="annual-2024", year=2024)
    base_fields = {
        "base_data_snapshot_ref": _ref(38, "fabric.data_snapshot").model_copy(
            update={"manifest_profile_sha256": "sha256:" + f"{138:064x}"}
        ),
        "model_input_obligation_set_ref": _ref(
            39, "runtime.quality.model_input_obligation_set"
        ).model_copy(update={"manifest_profile_sha256": "sha256:" + f"{139:064x}"}),
    }
    with pytest.raises(ValueError, match="derived_model_input_snapshot_selections_not_unique"):
        DerivedModelInputDataSnapshotLineage(
            **base_fields,
            selections=(selected, selected.model_copy(update={"binding_id": "duplicate"})),
        )

    with pytest.raises(ValueError, match="derived_model_input_snapshot_selections_not_unique"):
        DerivedModelInputDataSnapshotLineage(
            **base_fields,
            selections=(
                selected,
                selected.model_copy(update={"year": 2025, "source_path": "outputs.2025"}),
            ),
        )


def test_derived_model_input_snapshot_requires_selected_base_and_obligation_set() -> None:
    selected = _resolved_derived_input(60, binding_id="annual-2024", year=2024)
    valid = {
        "base_data_snapshot_ref": _ref(58, "fabric.data_snapshot").model_copy(
            update={"manifest_profile_sha256": "sha256:" + f"{158:064x}"}
        ),
        "model_input_obligation_set_ref": _ref(
            59, "runtime.quality.model_input_obligation_set"
        ).model_copy(update={"manifest_profile_sha256": "sha256:" + f"{159:064x}"}),
        "selections": (selected,),
    }
    with pytest.raises(ValueError, match="derived_model_input_snapshot_lineage_ref_mismatch"):
        DerivedModelInputDataSnapshotLineage(
            **(valid | {"base_data_snapshot_ref": _ref(58, "fabric.data_snapshot")})
        )
    with pytest.raises(ValueError, match="derived_model_input_snapshot_lineage_ref_mismatch"):
        DerivedModelInputDataSnapshotLineage(
            **(
                valid
                | {
                    "model_input_obligation_set_ref": _ref(
                        59, "runtime.quality.model_input_obligation_set"
                    ).model_copy(update={"manifest_profile_sha256": None})
                }
            )
        )
    with pytest.raises(ValidationError):
        DerivedModelInputDataSnapshotLineage(**(valid | {"unexpected_authority": True}))
    with pytest.raises(ValidationError):
        DerivedModelInputDataSnapshotLineage(**(valid | {"lineage_status": "verified"}))
    with pytest.raises(ValidationError):
        DerivedModelInputDataSnapshotLineage(**(valid | {"authority_purpose": "publication"}))
    with pytest.raises(ValidationError):
        DerivedModelInputDataSnapshotLineage(**(valid | {"selections": ()}))


@pytest.mark.parametrize("snapshot_type", [DataSnapshot, DataSnapshotOwnerBound])
def test_owner_input_requirements_reject_missing_required_and_unexpected_refs(
    snapshot_type: type[DataSnapshot],
) -> None:
    valid_snapshot = _bridge_snapshot(snapshot_type)
    missing_required = (
        valid_snapshot.model_copy(update={"data_schema_ref": None}),
        valid_snapshot.model_copy(update={"quality_report_ref": None}),
    )
    unexpected = _bridge_snapshot(
        snapshot_type,
        uncertainty_ref=UncertaintyBoundsRef(
            artifact_id=ArtifactID.from_sha256_hex(f"{15:064x}"),
            kind="fabric.uncertainty_bounds",
            media_type="application/json",
        ),
    )

    for snapshot in (*missing_required, unexpected):
        with pytest.raises(ValueError, match="data_snapshot_owner_fields_do_not_match_lineage"):
            data_snapshot_owner_input_requirements(snapshot)


@pytest.mark.parametrize("snapshot_type", [DataSnapshot, DataSnapshotOwnerBound])
def test_owner_input_requirements_refuse_malformed_present_optional_refs(
    snapshot_type: type[DataSnapshot],
) -> None:
    snapshot = _bridge_snapshot(snapshot_type)
    snapshot.evidence_ref = "not-an-artifact-ref"  # type: ignore[assignment]

    with pytest.raises(ValidationError):
        data_snapshot_owner_input_requirements(snapshot)


@pytest.mark.parametrize("snapshot_type", [DataSnapshot, DataSnapshotOwnerBound])
@pytest.mark.parametrize(("include_evidence", "include_warnings"), [(True, False), (False, True)])
def test_fabric_bridge_owner_inputs_allow_independent_optional_refs(
    snapshot_type: type[DataSnapshot],
    include_evidence: bool,
    include_warnings: bool,
) -> None:
    evidence = EvidenceBundleRef(
        artifact_id=ArtifactID.from_sha256_hex(f"{5:064x}"),
        kind="fabric.evidence_bundle",
        media_type="application/json",
    )
    warnings = WarningsRef(
        artifact_id=ArtifactID.from_sha256_hex(f"{6:064x}"),
        kind="fabric.warnings",
        media_type="application/json",
    )
    snapshot = _bridge_snapshot(
        snapshot_type,
        evidence_ref=evidence if include_evidence else None,
        warnings_ref=warnings if include_warnings else None,
    )

    requirements = data_snapshot_owner_input_requirements(snapshot)

    roles = {role for _ref, role in requirements}
    assert ("evidence_ref" in roles) is include_evidence
    assert ("warnings_ref" in roles) is include_warnings
    assert len(requirements) == 5
