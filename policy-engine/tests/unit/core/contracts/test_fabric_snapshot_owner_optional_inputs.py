from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.fabric import (
    AcquiredObservationDataSnapshotLineage,
    DataSnapshot,
    DataSnapshotOwnerBound,
    DataViewRequestRef,
    EvidenceBundleRef,
    FabricBridgeDataSnapshotLineage,
    MeasurementRootDataSnapshotLineage,
    UncertaintyBoundsRef,
    WarningsRef,
    data_snapshot_owner_input_requirements,
)


def _ref(index: int, kind: str = "fixture.artifact") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(f"{index:064x}"),
        kind=kind,
        media_type="application/json",
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
