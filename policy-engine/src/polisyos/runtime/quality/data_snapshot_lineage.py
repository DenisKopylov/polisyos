"""Reconcile versioned DataSnapshot owner-lineage witnesses with source artifacts.

The Core DTO carries typed owner references, while this runtime module checks
that those references reproduce the actual owner payload/manifest relations.
It deliberately does not infer edges by recursively scanning arbitrary JSON.
"""

from __future__ import annotations

from collections.abc import Mapping

from polisyos.core import contracts
from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactRef,
    ArtifactStore,
    CanonInfo,
    CanonSpec,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import (
    DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,
    AcquiredObservationDataSnapshotLineage,
    DataSnapshot,
    DataSnapshotOwnerLineage,
    FabricBridgeDataSnapshotLineage,
    MeasurementRootDataSnapshotLineage,
    data_snapshot_manifest_inputs_match,
    data_snapshot_owner_input_requirements,
    data_snapshot_reference_fields,
)


class DataSnapshotLineageError(ValueError):
    """Raised when a DataSnapshot fails its typed source or owner-derived closure."""


def validate_data_snapshot_owner_lineage(
    store: ArtifactStore,
    snapshot_ref: ArtifactRef,
    snapshot: DataSnapshot,
    *,
    binding_lineage_refs: tuple[str, ...] | None = None,
    _seen: frozenset[tuple[str, str | None]] = frozenset(),
) -> None:
    """Verify the selected DataSnapshot transport and any recognized owner source.

    Owner family comes from the selected data payload and its actual typed source
    marker, never from the submitted schema version. Schema 0.2 generic snapshots
    retain their exact typed-field/role contract; recognized owners receive the
    same producer verification under 0.2 and 0.3. A 0.2 snapshot cannot carry an
    unverified 0.3 lineage field or downgrade a malformed owner payload.
    """
    current_key = (str(snapshot_ref.artifact_id), snapshot_ref.manifest_profile_sha256)
    if current_key in _seen:
        raise DataSnapshotLineageError("data_snapshot_owner_cycle_detected")
    seen = _seen | {current_key}

    parent = _verified_manifest(store, snapshot_ref)
    schema = parent.artifact_schema
    if (
        parent.kind != DataSnapshot.ARTIFACT_KIND
        or parent.media_type != DataSnapshot.ARTIFACT_MEDIA_TYPE
        or schema is None
        or schema.name != DataSnapshot.ARTIFACT_SCHEMA_NAME
        or schema.version not in DataSnapshot.ARTIFACT_SCHEMA_VERSIONS
    ):
        raise DataSnapshotLineageError("data_snapshot_owner_schema_invalid")
    if schema.version == DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION:
        if snapshot.source_lineage is None:
            raise DataSnapshotLineageError("data_snapshot_owner_lineage_missing")
    elif snapshot.source_lineage is not None:
        raise DataSnapshotLineageError("data_snapshot_legacy_lineage_field_unbound")

    payload_manifest = _verified_manifest(store, snapshot.data_ref)
    family = _owner_family(store, snapshot.data_ref, payload_manifest)
    lineage = snapshot.source_lineage
    if family is None:
        if lineage is not None or schema.version != DataSnapshot.ARTIFACT_SCHEMA_VERSION:
            raise DataSnapshotLineageError("data_snapshot_owner_family_or_lineage_mismatch")
        if not data_snapshot_manifest_inputs_match(
            snapshot,
            parent.inputs,
            schema_version=schema.version,
        ):
            raise DataSnapshotLineageError("data_snapshot_manifest_inputs_mismatch")
        for field_name in data_snapshot_reference_fields():
            ref = getattr(snapshot, field_name)
            if ref is not None:
                _verified_manifest(store, ref)
        return

    if schema.version == DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION:
        if lineage is None or _lineage_family(lineage) != family:
            raise DataSnapshotLineageError("data_snapshot_owner_family_or_lineage_mismatch")
    else:
        lineage = _legacy_owner_lineage(
            store,
            family=family,
            snapshot=snapshot,
            parent=parent,
            payload_manifest=payload_manifest,
        )

    expected_snapshot = snapshot.model_copy(update={"source_lineage": lineage})
    expected = data_snapshot_owner_input_requirements(expected_snapshot)
    try:
        _require_exact_owner_edges(store, manifest=parent, expected=expected)
    except DataSnapshotLineageError as exc:
        raise DataSnapshotLineageError("data_snapshot_owner_parent_inputs_mismatch") from exc

    if family == "measurement_root":
        if not isinstance(lineage, MeasurementRootDataSnapshotLineage):
            raise DataSnapshotLineageError("measurement_root_lineage_invalid")
        _verify_measurement_root_owner(store, snapshot, lineage)
    elif family == "fabric_bridge":
        if not isinstance(lineage, FabricBridgeDataSnapshotLineage):
            raise DataSnapshotLineageError("fabric_bridge_lineage_invalid")
        _verify_fabric_bridge_owner(store, snapshot, lineage)
    else:
        if not isinstance(lineage, AcquiredObservationDataSnapshotLineage):
            raise DataSnapshotLineageError("acquired_observation_lineage_invalid")
        _verify_acquired_observation_owner(store, snapshot, lineage, seen=seen)
        if binding_lineage_refs is not None:
            expected_binding_refs = tuple(
                _data_forge_cas_uri(ref)
                for ref in (
                    lineage.base_data_snapshot_ref,
                    lineage.overlay_admission_receipt_ref,
                    lineage.passport_ref,
                    snapshot.data_ref,
                )
            )
            if binding_lineage_refs != expected_binding_refs:
                raise DataSnapshotLineageError("acquired_observation_binding_lineage_mismatch")


def _legacy_owner_lineage(
    store: ArtifactStore,
    *,
    family: str,
    snapshot: DataSnapshot,
    parent: ArtifactManifest,
    payload_manifest: ArtifactManifest,
) -> DataSnapshotOwnerLineage:
    """Recover 0.2 owner refs from existing producer-bound source bytes.

    Parent role names are only locators here. Each recovered ref is reverified
    and then matched to owner-owned bytes by the family verifier below.
    """
    if family == "measurement_root":
        refs = {
            role: _single_ref_for_role(store, parent.inputs, role)
            for role in ("measurement_root", "fabric_fetch", "catalog_binding")
        }
        return MeasurementRootDataSnapshotLineage(
            measurement_root_ref=refs["measurement_root"],
            fetch_receipt_ref=refs["fabric_fetch"],
            catalog_binding_ref=refs["catalog_binding"],
        )
    if family == "fabric_bridge":
        request_ref = _single_ref_for_role(
            store,
            payload_manifest.inputs,
            "data_view_request_ref",
        )
        from polisyos.core.contracts.fabric import DataViewRequestRef

        return FabricBridgeDataSnapshotLineage(
            data_view_request_ref=DataViewRequestRef.model_validate(
                request_ref.model_dump(mode="json")
            )
        )
    if family == "acquired_observation_overlay":
        raw_payload = load_core_json_artifact(store, snapshot.data_ref)
        if not isinstance(raw_payload, Mapping):
            raise DataSnapshotLineageError("acquired_observation_payload_invalid")
        owner = raw_payload.get("_policyos_acquisition")
        if not isinstance(owner, Mapping):
            raise DataSnapshotLineageError("acquired_observation_owner_fields_missing")
        try:
            return AcquiredObservationDataSnapshotLineage(
                base_data_snapshot_ref=ArtifactRef.model_validate(owner["base_data_snapshot_ref"]),
                overlay_admission_receipt_ref=ArtifactRef.model_validate(owner["receipt_ref"]),
                passport_ref=ArtifactRef.model_validate(owner["passport_ref"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataSnapshotLineageError("acquired_observation_owner_refs_invalid") from exc
    raise DataSnapshotLineageError("data_snapshot_owner_family_unrecognized")


def _single_ref_for_role(
    store: ArtifactStore,
    inputs: list[InputRef],
    role: str,
) -> ArtifactRef:
    matches = [row for row in inputs if row.role == role]
    if len(matches) != 1:
        raise DataSnapshotLineageError("data_snapshot_owner_source_edges_mismatch")
    edge = matches[0]
    manifest = (
        store.get_manifest(edge.artifact_id)
        if edge.manifest_profile_sha256 is None
        else store.get_manifest_by_profile(
            edge.artifact_id,
            edge.manifest_profile_sha256,
        )
    )
    if manifest.artifact_id != edge.artifact_id:
        raise DataSnapshotLineageError("data_snapshot_lineage_ref_unverified")
    return ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )


def _owner_family(
    store: ArtifactStore,
    ref: ArtifactRef,
    manifest: object,
) -> str | None:
    kind = getattr(manifest, "kind", None)
    if kind == "fabric.fetch_payload":
        return "measurement_root"
    if kind == "fabric.tabular_payload":
        return "fabric_bridge"
    if kind != "fabric.production_data_state_payload":
        return None
    schema = getattr(manifest, "artifact_schema", None)
    if getattr(schema, "name", None) == "polisyos.runtime.quality.AcquisitionDataStatePayload":
        return "acquired_observation_overlay"
    raw_payload = load_core_json_artifact(store, ref)
    if isinstance(raw_payload, Mapping) and isinstance(
        raw_payload.get("_policyos_acquisition"), Mapping
    ):
        return "acquired_observation_overlay"
    from polisyos.runtime.quality.data_state_substrate import DATA_STATE_SUBSTRATE_SCHEMA_VERSION

    if schema == SchemaInfo(
        name="polisyos.runtime.quality.DataStatePayload",
        version=DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
    ):
        return None
    raise DataSnapshotLineageError("data_snapshot_owner_source_schema_invalid")


def _lineage_family(lineage: DataSnapshotOwnerLineage) -> str:
    if isinstance(lineage, MeasurementRootDataSnapshotLineage):
        return "measurement_root"
    if isinstance(lineage, FabricBridgeDataSnapshotLineage):
        return "fabric_bridge"
    if isinstance(lineage, AcquiredObservationDataSnapshotLineage):
        return "acquired_observation_overlay"
    raise DataSnapshotLineageError("data_snapshot_owner_lineage_unsupported")


def _verified_manifest(store: ArtifactStore, ref: ArtifactRef) -> ArtifactManifest:
    if not isinstance(ref, ArtifactRef):
        raise DataSnapshotLineageError("data_snapshot_lineage_ref_untyped")
    manifest = store.get_manifest(ref)
    profile = artifact_manifest_profile_sha256(manifest)
    if (
        manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
        or not profile
        or (ref.manifest_profile_sha256 is not None and profile != ref.manifest_profile_sha256)
        or not store.verify(ref).ok
    ):
        raise DataSnapshotLineageError("data_snapshot_lineage_ref_unverified")
    return manifest


def _edge_matches_owner_ref(
    store: ArtifactStore,
    *,
    edge: object,
    ref: ArtifactRef,
    role: str,
) -> bool:
    if getattr(edge, "artifact_id", None) != ref.artifact_id or getattr(edge, "role", None) != role:
        return False
    edge_profile = getattr(edge, "manifest_profile_sha256", None)
    if edge_profile is not None:
        if ref.manifest_profile_sha256 is not None:
            return edge_profile == ref.manifest_profile_sha256
        default_ref = ArtifactRef.model_validate(
            ref.model_dump(mode="json") | {"manifest_profile_sha256": None}
        )
        default_profile = artifact_manifest_profile_sha256(store.get_manifest(default_ref))
        return default_profile == edge_profile
    if ref.manifest_profile_sha256 is None:
        return True
    # Existing root-producer manifests sometimes name the correct child id/role
    # as a default view. Keep that historical selection only when the current
    # default manifest resolves to the exact producer-selected profile.
    default_ref = ArtifactRef.model_validate(
        ref.model_dump(mode="json") | {"manifest_profile_sha256": None}
    )
    return artifact_manifest_profile_sha256(store.get_manifest(default_ref)) == (
        ref.manifest_profile_sha256
    )


def _require_exact_owner_edges(
    store: ArtifactStore,
    *,
    manifest: object,
    expected: tuple[tuple[ArtifactRef, str], ...],
) -> None:
    inputs = getattr(manifest, "inputs", None)
    if not isinstance(inputs, list) or len(inputs) != len(expected):
        raise DataSnapshotLineageError("data_snapshot_owner_source_edges_mismatch")
    unmatched = set(range(len(inputs)))
    for ref, role in expected:
        matches = [
            index
            for index in unmatched
            if _edge_matches_owner_ref(store, edge=inputs[index], ref=ref, role=role)
        ]
        if len(matches) != 1:
            raise DataSnapshotLineageError("data_snapshot_owner_source_edges_mismatch")
        unmatched.remove(matches[0])


def _verify_measurement_root_owner(
    store: ArtifactStore,
    snapshot: DataSnapshot,
    lineage: MeasurementRootDataSnapshotLineage,
) -> None:
    from polisyos.fabric.retrieval.custody import FabricFetchReceipt
    from polisyos.runtime.quality.data_forge_binding import (
        FABRIC_MEASUREMENT_ROOT_SCHEMA_VERSION,
        FabricMeasurementRootPayload,
        _read_validated_measurement_snapshot_artifact,
    )

    root_manifest = _verified_manifest(store, lineage.measurement_root_ref)
    root_raw = _read_validated_measurement_snapshot_artifact(
        store=store,
        artifact_ref=lineage.measurement_root_ref,
        expected_kind="policyos.gy.measurement_root_payload",
        expected_media_type="application/json",
        expected_schema=SchemaInfo(name=FABRIC_MEASUREMENT_ROOT_SCHEMA_VERSION, version="v2"),
        expected_producer=_measurement_root_producer(),
        expected_inputs=(
            InputRef(
                artifact_id=lineage.fetch_receipt_ref.artifact_id,
                role="fabric_fetch",
            ),
        ),
        expected_canon=CanonInfo(forbid_floats=False),
    )
    root_payload = FabricMeasurementRootPayload.model_validate(from_canonical_bytes(root_raw))
    if (
        lineage.measurement_root_ref.kind != "policyos.gy.measurement_root_payload"
        or root_manifest.media_type != "application/json"
        or root_manifest.artifact_schema
        != SchemaInfo(name=FABRIC_MEASUREMENT_ROOT_SCHEMA_VERSION, version="v2")
        or root_payload.payload_ref != snapshot.data_ref
        or root_payload.fetch_receipt_ref != lineage.fetch_receipt_ref
        or root_payload.catalog_binding_ref != lineage.catalog_binding_ref
    ):
        raise DataSnapshotLineageError("measurement_root_owner_payload_mismatch")

    producer = _fetch_producer()
    receipt_raw = _read_validated_measurement_snapshot_artifact(
        store=store,
        artifact_ref=lineage.fetch_receipt_ref,
        expected_kind="fabric.fetch_receipt",
        expected_media_type="application/json",
        expected_schema=SchemaInfo(name="polisyos.fabric.fetch_receipt.v1", version="1.0.0"),
        expected_producer=producer,
        expected_inputs=(
            InputRef(artifact_id=root_payload.payload_ref.artifact_id, role="fetched_payload"),
            InputRef(
                artifact_id=lineage.catalog_binding_ref.artifact_id,
                role="catalog_binding",
            ),
        ),
        expected_canon=CanonInfo.from_spec(CanonSpec(forbid_floats=False, exclude_none=False)),
    )
    receipt = FabricFetchReceipt.model_validate(from_canonical_bytes(receipt_raw))
    if (
        receipt.result.data != snapshot.data_ref
        or receipt.catalog_binding_ref != lineage.catalog_binding_ref
    ):
        raise DataSnapshotLineageError("measurement_root_fetch_receipt_mismatch")

    payload_media = {
        "canonical_json": "application/json",
        "pandas_arrow_ipc": "application/vnd.apache.arrow.stream",
        "arrow_ipc": "application/vnd.apache.arrow.stream",
    }.get(receipt.payload_encoding)
    if payload_media is None:
        raise DataSnapshotLineageError("measurement_root_payload_encoding_invalid")
    payload_canon = (
        CanonInfo.from_spec(CanonSpec(forbid_floats=False, exclude_none=False))
        if payload_media == "application/json"
        else None
    )
    _read_validated_measurement_snapshot_artifact(
        store=store,
        artifact_ref=snapshot.data_ref,
        expected_kind="fabric.fetch_payload",
        expected_media_type=payload_media,
        expected_schema=SchemaInfo(name="polisyos.fabric.fetch_payload.v1", version="1.0.0"),
        expected_producer=producer,
        expected_inputs=(),
        expected_canon=payload_canon,
    )
    _read_validated_measurement_snapshot_artifact(
        store=store,
        artifact_ref=lineage.catalog_binding_ref,
        expected_kind="fabric.catalog_fetch_binding",
        expected_media_type="application/json",
        expected_schema=SchemaInfo(
            name="polisyos.data_forge.catalog_fetch_binding.v1",
            version="1.0.0",
        ),
        expected_producer=producer,
        expected_inputs=(),
        expected_canon=CanonInfo.from_spec(CanonSpec(forbid_floats=False, exclude_none=False)),
    )


def _verify_fabric_bridge_owner(
    store: ArtifactStore,
    snapshot: DataSnapshot,
    lineage: FabricBridgeDataSnapshotLineage,
) -> None:
    request_manifest = _verified_manifest(store, lineage.data_view_request_ref)
    data_manifest = _verified_manifest(store, snapshot.data_ref)
    if (
        lineage.data_view_request_ref.kind != "ir.data_view_request"
        or lineage.data_view_request_ref.media_type != "application/json"
        or request_manifest.artifact_schema
        != SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0")
        or snapshot.data_ref.kind != "fabric.tabular_payload"
        or snapshot.data_ref.media_type != "application/json"
        or data_manifest.artifact_schema
        != SchemaInfo(name="polisyos.fabric.TabularPayload", version="1.0")
    ):
        raise DataSnapshotLineageError("fabric_bridge_owner_manifest_mismatch")
    _require_exact_owner_edges(
        store,
        manifest=data_manifest,
        expected=((lineage.data_view_request_ref, "data_view_request_ref"),),
    )
    load_core_json_artifact(store, lineage.data_view_request_ref)
    load_core_json_artifact(store, snapshot.data_ref)
    for ref, _role in data_snapshot_owner_input_requirements(snapshot):
        _verified_manifest(store, ref)


def _verify_acquired_observation_owner(
    store: ArtifactStore,
    snapshot: DataSnapshot,
    lineage: AcquiredObservationDataSnapshotLineage,
    *,
    seen: frozenset[tuple[str, str | None]],
) -> None:
    payload_ref = snapshot.data_ref
    payload_manifest = _verified_manifest(store, payload_ref)
    if (
        payload_ref.kind != "fabric.production_data_state_payload"
        or payload_ref.media_type != "application/json"
        or payload_manifest.artifact_schema
        != SchemaInfo(
            name="polisyos.runtime.quality.AcquisitionDataStatePayload",
            version="policyos.runtime.acquisition_data_state.v2",
        )
    ):
        raise DataSnapshotLineageError("acquired_observation_payload_manifest_mismatch")
    raw_payload = load_core_json_artifact(store, payload_ref)
    if not isinstance(raw_payload, Mapping):
        raise DataSnapshotLineageError("acquired_observation_payload_invalid")
    owner = raw_payload.get("_policyos_acquisition")
    if not isinstance(owner, Mapping):
        raise DataSnapshotLineageError("acquired_observation_owner_fields_missing")
    try:
        payload_base_ref = ArtifactRef.model_validate(owner["base_data_snapshot_ref"])
        payload_receipt_ref = ArtifactRef.model_validate(owner["receipt_ref"])
        payload_passport_ref = ArtifactRef.model_validate(owner["passport_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DataSnapshotLineageError("acquired_observation_owner_refs_invalid") from exc
    if (
        payload_base_ref != lineage.base_data_snapshot_ref
        or payload_receipt_ref != lineage.overlay_admission_receipt_ref
        or payload_passport_ref != lineage.passport_ref
        or str(owner.get("base_data_snapshot_id"))
        != str(lineage.base_data_snapshot_ref.artifact_id)
    ):
        raise DataSnapshotLineageError("acquired_observation_owner_refs_mismatch")

    _require_exact_owner_edges(
        store,
        manifest=payload_manifest,
        expected=(
            input_ref_from_artifact_ref(
                lineage.base_data_snapshot_ref,
                role="input.base_data_snapshot",
            ),
            input_ref_from_artifact_ref(
                lineage.overlay_admission_receipt_ref,
                role="evidence.overlay_admission_receipt",
            ),
            input_ref_from_artifact_ref(
                lineage.passport_ref,
                role="evidence.acquisition_passport",
            ),
        ),
    )
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        OverlayAdmissionReceipt,
        content_sha256,
        validate_overlay_admission_receipt,
    )
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

    try:
        base_snapshot = validate_core_model_json_artifact(
            DataSnapshot,
            store,
            lineage.base_data_snapshot_ref,
        )
        validate_data_snapshot_owner_lineage(
            store,
            lineage.base_data_snapshot_ref,
            base_snapshot,
            _seen=seen,
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise DataSnapshotLineageError("acquired_observation_base_snapshot_unavailable") from exc
    receipt_manifest = _verified_manifest(store, lineage.overlay_admission_receipt_ref)
    passport_manifest = _verified_manifest(store, lineage.passport_ref)
    if (
        lineage.base_data_snapshot_ref.kind != "fabric.data_snapshot"
        or lineage.base_data_snapshot_ref.media_type != "application/json"
        or lineage.overlay_admission_receipt_ref.kind != "epoch.activated_overlay_admission_receipt"
        or lineage.passport_ref.kind != "epoch.acquisition_passport_snapshot"
        or receipt_manifest.media_type != "application/json"
        or passport_manifest.media_type != "application/json"
    ):
        raise DataSnapshotLineageError("acquired_observation_owner_child_mismatch")
    receipt_statement = contracts.epoch.load_verified_epoch_statement(
        store=store,
        ref=lineage.overlay_admission_receipt_ref,
        expected_kind="epoch.activated_overlay_admission_receipt",
    )
    passport_mapping = contracts.epoch.load_verified_epoch_statement(
        store=store,
        ref=lineage.passport_ref,
        expected_kind="epoch.acquisition_passport_snapshot",
    )
    receipt = contracts.epoch.ActivatedOverlayAdmissionStatement.model_validate(receipt_statement)
    passport = AdmissionPassport.model_validate(passport_mapping)
    receipt_hash = content_sha256(receipt.model_dump(mode="json"))
    passport_hash = content_sha256(passport_mapping)
    if (
        owner.get("receipt_content_sha256") != receipt_hash
        or owner.get("passport_content_sha256") != passport_hash
        or receipt.epoch_id != passport.epoch_id
        or receipt.passport_id != passport.passport_id
        or receipt.epoch_id != owner.get("epoch_id")
        or receipt.passport_id != passport_mapping.get("passport_id")
        or receipt.admission_content_sha256 != owner.get("admission_content_sha256")
        or receipt.activation_state != "active"
    ):
        raise DataSnapshotLineageError("acquired_observation_owner_content_mismatch")
    try:
        owner_receipt = OverlayAdmissionReceipt(
            **receipt.model_dump(mode="python"),
            receipt_ref=lineage.overlay_admission_receipt_ref,
            receipt_content_hash=receipt_hash,
            replayed=True,
        )
        validate_overlay_admission_receipt(owner_receipt)
    except (TypeError, ValueError) as exc:
        raise DataSnapshotLineageError(
            "acquired_observation_receipt_owner_validation_failed"
        ) from exc


def _measurement_root_producer() -> ProducerInfo:
    return ProducerInfo(
        component="polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer",
        version="2.0.0",
    )


def _fetch_producer() -> ProducerInfo:
    return ProducerInfo(
        component="polisyos.fabric.retrieval.executor.FetchExecutor", version="1.0.0"
    )


def _data_forge_cas_uri(ref: ArtifactRef) -> str:
    return f"cas://sha256/{str(ref.artifact_id).removeprefix('sha256:')}"


__all__ = [
    "DataSnapshotLineageError",
    "validate_data_snapshot_owner_lineage",
]
