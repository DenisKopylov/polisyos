"""Reconcile versioned DataSnapshot owner-lineage witnesses with source artifacts.

The Core DTO carries typed owner references, while this runtime module checks
that those references reproduce the actual owner payload/manifest relations.
It deliberately does not infer edges by recursively scanning arbitrary JSON.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from polisyos.core import contracts
from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactRef,
    ArtifactStore,
    CanonInfo,
    CoreJsonReadLimits,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    read_core_json_artifact_bounded,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts import (
    DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,
    AcquiredObservationDataSnapshotLineage,
    CandidateAcquisitionSourceDataSnapshotLineage,
    DataSnapshot,
    DataSnapshotOwnerLineage,
    DerivedModelInputDataSnapshotLineage,
    FabricBridgeDataSnapshotLineage,
    MeasurementRootDataSnapshotLineage,
    data_snapshot_manifest_inputs_match,
    data_snapshot_owner_input_requirements,
    data_snapshot_reference_fields,
    data_snapshot_reference_input_roles,
)
from polisyos.core.contracts.fabric import (
    DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION,
    AcquiredObservationSemanticInputDataSnapshotLineage,
)

_VERSIONED_DATA_SNAPSHOT_LINEAGE_VERSIONS = frozenset(
    {DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION, DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION}
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import CoreJSONArtifactBoundedMemberReader
    from polisyos.core.contracts import ResolvedDerivedInput


class DataSnapshotLineageError(ValueError):
    """Raised when a DataSnapshot fails its typed source or owner-derived closure."""


ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION = "acquired_source_row_revalidation_not_established"
CANDIDATE_SOURCE_LIMITATIONS = (
    "candidate_source_not_an_observation",
    "source_time_not_established",
    "measurement_authority_not_established",
    "publication_authority_not_established",
)
DERIVED_MODEL_INPUT_LIMITATIONS = (
    "derived_input_not_acquired_observation",
    "source_time_not_established",
    "causal_coupling_not_established",
    "external_empirical_context_not_established",
    "derivation_uncertainty_not_established",
)
_CANDIDATE_PAYLOAD_SCHEMAS = tuple(
    SchemaInfo(
        name="polisyos.runtime.quality.CandidateAcquisitionDataStatePayload",
        version=f"policyos.runtime.candidate_acquisition_data_state.v{version}",
    )
    for version in (1, 2)
)


def _candidate_source_limitations_for_payload_schema(schema_version: str) -> tuple[str, ...]:
    """Retain legacy limitations without confusing provenance with admission."""
    if schema_version == _CANDIDATE_PAYLOAD_SCHEMAS[0].version:
        return CANDIDATE_SOURCE_LIMITATIONS
    if schema_version == _CANDIDATE_PAYLOAD_SCHEMAS[1].version:
        return ("candidate_source_not_observed_admission", *CANDIDATE_SOURCE_LIMITATIONS[1:])
    raise DataSnapshotLineageError("candidate_acquisition_source_payload_version_unsupported")


DATA_SNAPSHOT_OWNER_BAND_READ_LIMITS = CoreJsonReadLimits(
    max_bytes=64 * 1024 * 1024,
    max_depth=128,
    max_elements=1_000_000,
    max_manifest_bytes=1024 * 1024,
)


class DataSnapshotSourceRowNotEstablishedError(DataSnapshotLineageError):
    """Refuse protected admission without a current acquired-source row witness."""

    def __init__(self) -> None:
        self.code = ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION
        super().__init__(self.code)


@dataclass(frozen=True)
class DataSnapshotLineageResult:
    """Scope of the store-only verification, distinct from source-row authority."""

    acquisition_source_row_status: Literal["not_applicable", "not_established"] = "not_applicable"
    candidate_source_limitations: tuple[str, ...] = ()

    @property
    def required_admissibility_blockers(self) -> tuple[str, ...]:
        """Return the limitation required by any candidate-band consumer."""
        if self.acquisition_source_row_status == "not_established":
            return tuple(
                dict.fromkeys(
                    (
                        ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,
                        *self.candidate_source_limitations,
                    )
                )
            )
        return tuple(dict.fromkeys(self.candidate_source_limitations))


def validate_data_snapshot_owner_lineage(
    store: ArtifactStore,
    snapshot_ref: ArtifactRef,
    snapshot: DataSnapshot,
    *,
    binding_lineage_refs: tuple[str, ...] | None = None,
    candidate_only: bool = False,
    _seen: frozenset[tuple[str, str | None]] = frozenset(),
) -> DataSnapshotLineageResult:
    """Verify selected lineage; acquired-source rows remain candidate-only.

    Owner family comes from the selected data payload and its actual typed source
    marker, never from the submitted schema version. Schema 0.2 generic snapshots
    retain their exact typed-field/role contract; recognized owners receive the
    same producer verification under 0.2 and 0.3. A 0.2 snapshot cannot carry an
    unverified 0.3 lineage field or downgrade a malformed owner payload.

    Immutable epoch statements and selected CAS edges do not reconcile an
    acquired selected value/history with the current native source owner. With
    no overlay/authority resolver inputs here, acquired rows fail closed by
    default. ``candidate_only=True`` returns a typed not-established limitation;
    its consumer must remain in the candidate band and retain the required
    admissibility blocker. It never establishes source-row or basis authority.
    """
    current_key = (str(snapshot_ref.artifact_id), snapshot_ref.manifest_profile_sha256)
    if current_key in _seen:
        raise DataSnapshotLineageError("data_snapshot_owner_cycle_detected")
    seen = _seen | {current_key}

    parent = _manifest_view(store, snapshot_ref)
    schema = parent.artifact_schema
    if (
        parent.kind != DataSnapshot.ARTIFACT_KIND
        or parent.media_type != DataSnapshot.ARTIFACT_MEDIA_TYPE
        or schema is None
        or schema.name != DataSnapshot.ARTIFACT_SCHEMA_NAME
        or schema.version not in DataSnapshot.ARTIFACT_SCHEMA_VERSIONS
    ):
        raise DataSnapshotLineageError("data_snapshot_owner_schema_invalid")
    if schema.version in _VERSIONED_DATA_SNAPSHOT_LINEAGE_VERSIONS:
        if snapshot.source_lineage is None:
            raise DataSnapshotLineageError("data_snapshot_owner_lineage_missing")
        semantic_owner = isinstance(
            snapshot.source_lineage, AcquiredObservationSemanticInputDataSnapshotLineage
        )
        if (
            schema.version == DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION
        ) != semantic_owner:
            raise DataSnapshotLineageError("data_snapshot_owner_version_lineage_mismatch")
    elif snapshot.source_lineage is not None:
        raise DataSnapshotLineageError("data_snapshot_legacy_lineage_field_unbound")

    payload_manifest = _manifest_view(store, snapshot.data_ref)
    raw_payload = _read_owner_band_payload(store, payload_manifest)
    family = _owner_family(snapshot, parent, payload_manifest, raw_payload=raw_payload)
    lineage = snapshot.source_lineage
    legacy_acquisition_probe = family is None and _legacy_acquisition_probe_required(
        snapshot.data_ref, payload_manifest
    )
    if family is None:
        if legacy_acquisition_probe and snapshot.data_ref.manifest_profile_sha256 is None:
            raise DataSnapshotLineageError("data_snapshot_owner_profile_unselected")
        parent = _verified_manifest(store, snapshot_ref)
        payload_manifest = _verified_manifest(
            store,
            snapshot.data_ref,
            require_selected_profile=legacy_acquisition_probe,
        )
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
        if not isinstance(raw_payload, Mapping) or "_policyos_acquisition" not in raw_payload:
            return DataSnapshotLineageResult()
        if not legacy_acquisition_probe:
            raise DataSnapshotLineageError("acquired_observation_payload_manifest_mismatch")
        family = "acquired_observation_overlay"

    _require_selected_owner_closure(
        snapshot_ref=snapshot_ref,
        snapshot=snapshot,
        parent=parent,
        payload_manifest=payload_manifest,
    )
    if schema.version in _VERSIONED_DATA_SNAPSHOT_LINEAGE_VERSIONS:
        if lineage is None or _lineage_family(lineage) != family:
            raise DataSnapshotLineageError("data_snapshot_owner_family_or_lineage_mismatch")
        selected_expected = data_snapshot_owner_input_requirements(snapshot)
        try:
            _require_exact_owner_edges(store, manifest=parent, expected=selected_expected)
        except DataSnapshotLineageError as exc:
            raise DataSnapshotLineageError("data_snapshot_owner_parent_inputs_mismatch") from exc
        if family == "acquired_observation_overlay":
            _require_exact_owner_edges(
                store,
                manifest=payload_manifest,
                expected=_acquired_observation_payload_requirements(snapshot, lineage),
            )
    parent = _verified_manifest(store, snapshot_ref, require_selected_profile=True)
    payload_manifest = _verified_manifest(store, snapshot.data_ref, require_selected_profile=True)

    if schema.version in _VERSIONED_DATA_SNAPSHOT_LINEAGE_VERSIONS:
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
    elif family == "derived_model_input":
        if not isinstance(lineage, DerivedModelInputDataSnapshotLineage):
            raise DataSnapshotLineageError("derived_model_input_lineage_invalid")
        try:
            base_result = _verify_derived_model_input_owner(
                store, snapshot, lineage, raw_payload=raw_payload, seen=seen
            )
        except DataSnapshotLineageError:
            raise
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            raise DataSnapshotLineageError("derived_model_input_owner_replay_failed") from exc
        if binding_lineage_refs is not None and binding_lineage_refs != tuple(
            _data_forge_cas_uri(ref)
            for ref, _role in data_snapshot_owner_input_requirements(snapshot)
        ):
            raise DataSnapshotLineageError("derived_model_input_binding_lineage_mismatch")
        if not candidate_only:
            raise DataSnapshotLineageError("derived_model_input_candidate_only")
        return DataSnapshotLineageResult(
            candidate_source_limitations=tuple(
                dict.fromkeys(
                    (*DERIVED_MODEL_INPUT_LIMITATIONS, *base_result.required_admissibility_blockers)
                )
            )
        )
    elif family == "candidate_acquisition_source":
        if not isinstance(lineage, CandidateAcquisitionSourceDataSnapshotLineage):
            raise DataSnapshotLineageError("candidate_acquisition_source_lineage_invalid")
        source_limitations = _verify_candidate_acquisition_source_owner(
            store, snapshot_ref, snapshot, lineage, seen=seen
        )
        if binding_lineage_refs is not None:
            expected_binding_refs = tuple(
                _data_forge_cas_uri(ref)
                for ref in (
                    lineage.base_data_snapshot_ref,
                    lineage.candidate_source_ref,
                    snapshot.data_ref,
                )
            )
            if binding_lineage_refs != expected_binding_refs:
                raise DataSnapshotLineageError(
                    "candidate_acquisition_source_binding_lineage_mismatch"
                )
        if not candidate_only:
            raise DataSnapshotSourceRowNotEstablishedError()
        payload_schema = _manifest_view(store, snapshot.data_ref).artifact_schema
        if payload_schema is None:  # pragma: no cover - verified by owner replay
            raise DataSnapshotLineageError("candidate_acquisition_source_payload_manifest_mismatch")
        candidate_limitations = _candidate_source_limitations_for_payload_schema(
            payload_schema.version
        )
        return DataSnapshotLineageResult(
            acquisition_source_row_status="not_established",
            candidate_source_limitations=tuple(
                dict.fromkeys((*candidate_limitations, *source_limitations))
            ),
        )
    else:
        if not isinstance(
            lineage,
            (
                AcquiredObservationDataSnapshotLineage,
                AcquiredObservationSemanticInputDataSnapshotLineage,
            ),
        ):
            raise DataSnapshotLineageError("acquired_observation_lineage_invalid")
        base_result = _verify_acquired_observation_owner(
            store, snapshot_ref, snapshot, lineage, seen=seen
        )
        if binding_lineage_refs is not None:
            lineage_refs = (
                lineage.base_data_snapshot_ref,
                lineage.overlay_admission_receipt_ref,
                lineage.passport_ref,
            )
            if isinstance(lineage, AcquiredObservationSemanticInputDataSnapshotLineage):
                lineage_refs = (
                    *lineage_refs,
                    *(ref for ref, _role in lineage.selection.lineage_refs()),
                )
            expected_binding_refs = tuple(
                _data_forge_cas_uri(ref) for ref in (*lineage_refs, snapshot.data_ref)
            )
            if binding_lineage_refs != expected_binding_refs:
                raise DataSnapshotLineageError("acquired_observation_binding_lineage_mismatch")
        if not candidate_only:
            raise DataSnapshotSourceRowNotEstablishedError()
        return DataSnapshotLineageResult(
            acquisition_source_row_status="not_established",
            candidate_source_limitations=base_result.required_admissibility_blockers,
        )
    return DataSnapshotLineageResult()


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
        from polisyos.core.contracts import DataViewRequestRef

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
    if edge.manifest_profile_sha256 is None:
        raise DataSnapshotLineageError("data_snapshot_owner_profile_unselected")
    manifest = store.get_manifest_by_profile(edge.artifact_id, edge.manifest_profile_sha256)
    if manifest.artifact_id != edge.artifact_id:
        raise DataSnapshotLineageError("data_snapshot_lineage_ref_unverified")
    return ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )


def _legacy_acquisition_probe_required(
    ref: ArtifactRef,
    manifest: ArtifactManifest,
) -> bool:
    """Identify the one legacy payload profile whose bytes may carry acquisition ownership."""
    if ref.kind != "fabric.production_data_state_payload":
        return False
    from polisyos.runtime.quality.data_state_substrate import DATA_STATE_SUBSTRATE_SCHEMA_VERSION

    return manifest.artifact_schema == SchemaInfo(
        name="polisyos.runtime.quality.DataStatePayload",
        version=DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
    )


def _read_owner_band_payload(store: ArtifactStore, manifest: ArtifactManifest) -> object:
    """Inspect actual Core JSON within a fixed profile, never a MIME guess.

    Binary owners retain their existing typed codec checks. A Core JSON view
    which is unavailable or exceeds the declared resource profile cannot
    establish an observed band. No unbounded payload scan or parser is added.
    """
    if manifest.canon is None:
        return None
    try:
        selected = read_core_json_artifact_bounded(
            cast("CoreJSONArtifactBoundedMemberReader", store),
            artifact_ref_for_manifest(manifest),
            limits=DATA_SNAPSHOT_OWNER_BAND_READ_LIMITS,
        )
        return selected.value
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise DataSnapshotLineageError("data_snapshot_owner_band_not_established") from exc


def _owner_family(
    snapshot: DataSnapshot,
    parent: ArtifactManifest,
    manifest: ArtifactManifest,
    *,
    raw_payload: object,
) -> str | None:
    kind = getattr(manifest, "kind", None)
    from polisyos.core.contracts import DERIVED_MODEL_INPUT_PAYLOAD_KIND

    if kind == DERIVED_MODEL_INPUT_PAYLOAD_KIND or manifest.artifact_schema == SchemaInfo(
        name="polisyos.runtime.quality.DerivedModelInputPayload", version="1.0"
    ):
        if not isinstance(snapshot.source_lineage, DerivedModelInputDataSnapshotLineage):
            raise DataSnapshotLineageError("derived_model_input_lineage_missing")
        return "derived_model_input"
    if (
        kind == "runtime.quality.candidate_acquisition_source"
        or getattr(getattr(manifest, "artifact_schema", None), "name", None)
        in {
            "polisyos.runtime.candidate_acquisition_source.v1",
            "polisyos.runtime.candidate_acquisition_source.v2",
            "polisyos.runtime.candidate_acquisition_source.v3",
        }
        or (
            isinstance(raw_payload, Mapping)
            and raw_payload.get("schema_version")
            in {
                "polisyos.runtime.candidate_acquisition_source.v1",
                "polisyos.runtime.candidate_acquisition_source.v2",
                "polisyos.runtime.candidate_acquisition_source.v3",
            }
        )
    ):
        raise DataSnapshotLineageError("candidate_acquisition_source_lineage_missing")
    if isinstance(raw_payload, Mapping):
        # Classify actual owner content before a submitted family can mask it.
        # Either genuine descendant can retain the other's historical marker.
        # Only a matching typed owner and selected payload schema chooses its
        # current family; full owner replay and base verification follow below.
        if (
            isinstance(snapshot.source_lineage, CandidateAcquisitionSourceDataSnapshotLineage)
            and manifest.artifact_schema in _CANDIDATE_PAYLOAD_SCHEMAS
        ):
            return "candidate_acquisition_source"
        if (
            isinstance(
                snapshot.source_lineage,
                (
                    AcquiredObservationDataSnapshotLineage,
                    AcquiredObservationSemanticInputDataSnapshotLineage,
                ),
            )
            or (
                snapshot.source_lineage is None
                and parent.artifact_schema
                == SchemaInfo(name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version="0.2.0")
            )
        ) and manifest.artifact_schema == SchemaInfo(
            name="polisyos.runtime.quality.AcquisitionDataStatePayload",
            version="policyos.runtime.acquisition_data_state.v2",
        ):
            return "acquired_observation_overlay"
        if "_policyos_candidate_acquisition" in raw_payload:
            raise DataSnapshotLineageError("candidate_acquisition_source_lineage_missing")
        if "_policyos_acquisition" in raw_payload:
            return "acquired_observation_overlay"
    if snapshot.source_lineage is not None:
        return _lineage_family(snapshot.source_lineage)
    if kind == "fabric.fetch_payload":
        return "measurement_root"
    if kind == "fabric.tabular_payload":
        return "fabric_bridge"
    if kind != "fabric.production_data_state_payload":
        return None
    schema = getattr(manifest, "artifact_schema", None)
    if getattr(schema, "name", None) == "polisyos.runtime.quality.AcquisitionDataStatePayload":
        return "acquired_observation_overlay"
    if (
        getattr(schema, "name", None)
        == "polisyos.runtime.quality.CandidateAcquisitionDataStatePayload"
    ):
        return "candidate_acquisition_source"
    if any(
        edge.role
        in {"payload.candidate_acquisition_source", "evidence.candidate_acquisition_source"}
        for edge in parent.inputs
    ):
        raise DataSnapshotLineageError("candidate_acquisition_source_payload_schema_invalid")
    owner_roles = {
        "payload.acquired_observation_candidate",
        "input.base_data_snapshot",
        "evidence.overlay_admission_receipt",
        "evidence.acquisition_passport",
    }
    if any(edge.role in owner_roles for edge in parent.inputs):
        if getattr(schema, "name", None) == "polisyos.runtime.quality.DataStatePayload":
            return "acquired_observation_overlay"
        raise DataSnapshotLineageError("data_snapshot_owner_source_schema_invalid")
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
    if isinstance(lineage, AcquiredObservationSemanticInputDataSnapshotLineage):
        return "acquired_observation_overlay"
    if isinstance(lineage, CandidateAcquisitionSourceDataSnapshotLineage):
        return "candidate_acquisition_source"
    if isinstance(lineage, DerivedModelInputDataSnapshotLineage):
        return "derived_model_input"
    raise DataSnapshotLineageError("data_snapshot_owner_lineage_unsupported")


def _manifest_view(store: ArtifactStore, ref: ArtifactRef) -> ArtifactManifest:
    if not isinstance(ref, ArtifactRef):
        raise DataSnapshotLineageError("data_snapshot_lineage_ref_untyped")
    if ref.manifest_profile_sha256 is None:
        manifest = store.get_manifest(ref)
    else:
        manifest = store.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256)
    profile = artifact_manifest_profile_sha256(manifest)
    if (
        manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
        or not profile
        or (ref.manifest_profile_sha256 is not None and profile != ref.manifest_profile_sha256)
    ):
        raise DataSnapshotLineageError("data_snapshot_lineage_ref_unverified")
    return manifest


def _verified_manifest(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    require_selected_profile: bool = False,
) -> ArtifactManifest:
    if require_selected_profile and ref.manifest_profile_sha256 is None:
        raise DataSnapshotLineageError("data_snapshot_owner_profile_unselected")
    manifest = _manifest_view(store, ref)
    if not store.verify(ref).ok:
        raise DataSnapshotLineageError("data_snapshot_lineage_ref_unverified")
    return manifest


def _require_selected_owner_closure(
    *,
    snapshot_ref: ArtifactRef,
    snapshot: DataSnapshot,
    parent: ArtifactManifest,
    payload_manifest: ArtifactManifest,
) -> None:
    refs = [snapshot_ref, snapshot.data_ref]
    refs.extend(
        getattr(snapshot, field_name)
        for field_name in data_snapshot_reference_fields()
        if getattr(snapshot, field_name) is not None
    )
    if snapshot.source_lineage is not None:
        refs.extend(ref for ref, _role in data_snapshot_owner_input_requirements(snapshot))
    if any(ref.manifest_profile_sha256 is None for ref in refs):
        raise DataSnapshotLineageError("data_snapshot_owner_profile_unselected")
    if any(edge.manifest_profile_sha256 is None for edge in parent.inputs):
        raise DataSnapshotLineageError("data_snapshot_owner_profile_unselected")
    if any(edge.manifest_profile_sha256 is None for edge in payload_manifest.inputs):
        raise DataSnapshotLineageError("data_snapshot_owner_profile_unselected")


def _edge_matches_owner_ref(
    _store: ArtifactStore,
    *,
    edge: object,
    ref: ArtifactRef,
    role: str,
) -> bool:
    if getattr(edge, "artifact_id", None) != ref.artifact_id or getattr(edge, "role", None) != role:
        return False
    return getattr(edge, "manifest_profile_sha256", None) == ref.manifest_profile_sha256


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
    from polisyos.fabric import FabricFetchReceipt
    from polisyos.runtime.quality.data_forge_binding import (
        FABRIC_MEASUREMENT_ROOT_SCHEMA_VERSION,
        FabricMeasurementRootPayload,
        _read_validated_measurement_snapshot_artifact,
    )

    _require_selected_refs(
        snapshot.data_ref,
        lineage.measurement_root_ref,
        lineage.fetch_receipt_ref,
        lineage.catalog_binding_ref,
    )
    root_manifest = _manifest_view(store, lineage.measurement_root_ref)
    root_expected_inputs = (
        input_ref_from_artifact_ref(lineage.fetch_receipt_ref, role="fabric_fetch"),
    )
    if root_manifest.inputs != list(root_expected_inputs):
        raise DataSnapshotLineageError("measurement_root_owner_source_edges_mismatch")
    root_raw = _read_validated_measurement_snapshot_artifact(
        store=store,
        artifact_ref=lineage.measurement_root_ref,
        expected_kind="policyos.gy.measurement_root_payload",
        expected_media_type="application/json",
        expected_schema=SchemaInfo(name=FABRIC_MEASUREMENT_ROOT_SCHEMA_VERSION, version="v2"),
        expected_producer=_measurement_root_producer(),
        expected_inputs=root_expected_inputs,
        expected_canon=CanonInfo(forbid_floats=False),
        require_selected_profile=True,
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
            input_ref_from_artifact_ref(root_payload.payload_ref, role="fetched_payload"),
            input_ref_from_artifact_ref(lineage.catalog_binding_ref, role="catalog_binding"),
        ),
        expected_canon=CanonInfo.from_spec(CanonSpec(forbid_floats=False, exclude_none=False)),
        require_selected_profile=True,
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
        require_selected_profile=True,
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
        require_selected_profile=True,
    )


def _verify_fabric_bridge_owner(
    store: ArtifactStore,
    snapshot: DataSnapshot,
    lineage: FabricBridgeDataSnapshotLineage,
) -> None:
    _require_selected_refs(snapshot.data_ref, lineage.data_view_request_ref)
    request_manifest = _manifest_view(store, lineage.data_view_request_ref)
    data_manifest = _manifest_view(store, snapshot.data_ref)
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
    _verified_manifest(store, lineage.data_view_request_ref, require_selected_profile=True)
    _verified_manifest(store, snapshot.data_ref, require_selected_profile=True)
    load_core_json_artifact(store, lineage.data_view_request_ref)
    load_core_json_artifact(store, snapshot.data_ref)
    for ref, _role in data_snapshot_owner_input_requirements(snapshot):
        _verified_manifest(store, ref, require_selected_profile=True)


def _acquired_observation_payload_requirements(
    snapshot: DataSnapshot,
    lineage: AcquiredObservationDataSnapshotLineage
    | AcquiredObservationSemanticInputDataSnapshotLineage,
) -> tuple[tuple[ArtifactRef, str], ...]:
    """Derive source-only payload edges from the canonical Core owner contract.

    Parent requirements include the DataSnapshot's data-ref edge. Its payload
    manifest consumes the remaining owner refs, never its own data-ref edge.
    Keep the canonical (selected ArtifactRef, role) pairs used by the strict
    matcher; InputRef transport models belong to manifest-writing APIs.
    """
    owner_snapshot = snapshot.model_copy(update={"source_lineage": lineage})
    parent_requirements = data_snapshot_owner_input_requirements(owner_snapshot)
    data_ref_roles = data_snapshot_reference_input_roles("data_ref")
    return tuple((ref, role) for ref, role in parent_requirements if role not in data_ref_roles)


def _verify_acquired_observation_owner(
    store: ArtifactStore,
    snapshot_ref: ArtifactRef,
    snapshot: DataSnapshot,
    lineage: AcquiredObservationDataSnapshotLineage
    | AcquiredObservationSemanticInputDataSnapshotLineage,
    *,
    seen: frozenset[tuple[str, str | None]],
) -> DataSnapshotLineageResult:
    payload_ref = snapshot.data_ref
    _require_selected_refs(
        payload_ref,
        lineage.base_data_snapshot_ref,
        lineage.overlay_admission_receipt_ref,
        lineage.passport_ref,
    )
    payload_manifest = _manifest_view(store, payload_ref)
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
    _require_exact_owner_edges(
        store,
        manifest=payload_manifest,
        expected=_acquired_observation_payload_requirements(snapshot, lineage),
    )
    payload_manifest = _verified_manifest(store, payload_ref, require_selected_profile=True)
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
    _require_selected_refs(payload_base_ref, payload_receipt_ref, payload_passport_ref)
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
        expected=_acquired_observation_payload_requirements(snapshot, lineage),
    )
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.data_forge.read_api.catalog import (
        OverlayAdmissionReceipt,
        validate_overlay_admission_receipt,
    )
    from polisyos.fabric.data_plane import content_sha256
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

    try:
        base_manifest = _manifest_view(store, lineage.base_data_snapshot_ref)
        if any(edge.manifest_profile_sha256 is None for edge in base_manifest.inputs):
            raise DataSnapshotLineageError("acquired_observation_base_profile_unselected")
        base_snapshot = validate_core_model_json_artifact(
            DataSnapshot,
            store,
            lineage.base_data_snapshot_ref,
        )
        _require_selected_refs(base_snapshot.data_ref)
        base_payload_manifest = _manifest_view(store, base_snapshot.data_ref)
        try:
            _require_selected_owner_closure(
                snapshot_ref=lineage.base_data_snapshot_ref,
                snapshot=base_snapshot,
                parent=base_manifest,
                payload_manifest=base_payload_manifest,
            )
        except DataSnapshotLineageError as exc:
            raise DataSnapshotLineageError("acquired_observation_base_profile_unselected") from exc
        base_result = validate_data_snapshot_owner_lineage(
            store,
            lineage.base_data_snapshot_ref,
            base_snapshot,
            # Recursion verifies structure only; the enclosing acquired result
            # carries the source-row limitation or refuses protected admission.
            candidate_only=True,
            _seen=seen,
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise DataSnapshotLineageError("acquired_observation_base_snapshot_unavailable") from exc
    # Protected owner closure requires exact selected views. The Core epoch
    # reader owns each statement's kind/media/schema/canon/input/byte contract;
    # do not add a conflicting generic-JSON law beside that canonical codec.
    _verified_manifest(
        store,
        lineage.overlay_admission_receipt_ref,
        require_selected_profile=True,
    )
    _verified_manifest(
        store,
        lineage.passport_ref,
        require_selected_profile=True,
    )
    try:
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
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise DataSnapshotLineageError("acquired_observation_owner_child_mismatch") from exc
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

    from polisyos.runtime.quality.data_state_substrate import (
        verify_acquired_observation_snapshot_payload,
    )

    try:
        verify_acquired_observation_snapshot_payload(
            store=store,
            snapshot_ref=snapshot_ref,
            snapshot=snapshot,
            base_data_snapshot_ref=lineage.base_data_snapshot_ref,
            receipt_ref=lineage.overlay_admission_receipt_ref,
            passport_ref=lineage.passport_ref,
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise DataSnapshotLineageError("acquired_observation_owner_replay_failed") from exc
    return base_result


def _replay_derived_selection_value(
    store: ArtifactStore, selection: ResolvedDerivedInput
) -> object:
    """Replay the existing arithmetic owner, without claiming source authority."""
    from polisyos.core.contracts import (
        load_derived_input_correspondence,
        load_derived_input_profile,
        load_registered_derived_input_correspondence,
        load_registered_derived_input_profile,
    )
    from polisyos.core.derivations import (
        load_composition_recipe_artifact,
        load_derivation_recipe_artifact,
        resolve_certified_composition,
        resolve_certified_derivation,
    )

    schema = _verified_manifest(
        store, selection.correspondence_ref, require_selected_profile=True
    ).artifact_schema
    if schema == SchemaInfo(
        name="polisyos.catalog.RegisteredDerivedInputCorrespondence", version="2.0"
    ):
        proof = load_registered_derived_input_correspondence(store, selection.correspondence_ref)
        profile = load_registered_derived_input_profile(store, proof.profile_ref)
        recipe = load_composition_recipe_artifact(store, selection.recipe_ref)
        resolution = resolve_certified_composition(
            store,
            certificate_ref=selection.certificate_ref,
            consumer_method_id="polisyos.runtime.derived-data-snapshot-lineage.v1",
        )
    elif schema == SchemaInfo(
        name="polisyos.catalog.DerivedInputCorrespondenceBasis", version="1.0"
    ):
        proof = load_derived_input_correspondence(store, selection.correspondence_ref)
        profile = load_derived_input_profile(store, proof.profile_ref)
        recipe = load_derivation_recipe_artifact(store, selection.recipe_ref)
        resolution = resolve_certified_derivation(
            store,
            certificate_ref=selection.certificate_ref,
            consumer_method_id="polisyos.runtime.derived-data-snapshot-lineage.v1",
        )
    else:
        raise DataSnapshotLineageError("derived_model_input_correspondence_profile_unsupported")
    if any(
        artifact_ref_identity_key(getattr(selection, field))
        != artifact_ref_identity_key(getattr(proof, field))
        for field in (
            "model_input_obligation_ref",
            "model_interface_ref",
            "profile_ref",
            "recipe_ref",
            "certificate_ref",
            "output_ref",
        )
    ) or (selection.year, selection.model_port_id) != (proof.year, proof.model_port_id):
        raise DataSnapshotLineageError("derived_model_input_selected_proof_mismatch")
    certified_output = resolution.certificate.derived_artifact_ref
    if (
        recipe != resolution.certificate.recipe
        or certified_output is None
        or artifact_ref_identity_key(certified_output)
        != artifact_ref_identity_key(selection.output_ref)
    ):
        raise DataSnapshotLineageError("derived_model_input_selected_output_mismatch")
    points = tuple(point for point in resolution.series.points if point.year == selection.year)
    if len(points) != 1:
        raise DataSnapshotLineageError("derived_model_input_selected_year_missing")
    value = points[0].value
    return value if profile.output_projection == "scalar" else [value]


def _verify_derived_model_input_owner(
    store: ArtifactStore,
    snapshot: DataSnapshot,
    lineage: DerivedModelInputDataSnapshotLineage,
    *,
    raw_payload: object,
    seen: frozenset[tuple[str, str | None]],
) -> DataSnapshotLineageResult:
    """Rebuild the full candidate payload from its actual predecessor and outputs.

    Arithmetic uses the existing Core certificate replay. Semantic correspondence
    remains the Foundry binding owner's separate check; this transport verifier
    grants neither observed-source authority nor native currentness.
    """
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts import (
        DERIVED_MODEL_INPUT_PAYLOAD_KIND,
        load_model_input_obligation_set,
    )
    from polisyos.foundry.data_plane import load_input_bindings

    _require_selected_refs(
        snapshot.data_ref,
        lineage.base_data_snapshot_ref,
        lineage.model_input_obligation_set_ref,
    )
    payload_manifest = _verified_manifest(store, snapshot.data_ref, require_selected_profile=True)
    for ref, _role in data_snapshot_owner_input_requirements(snapshot):
        _verified_manifest(store, ref, require_selected_profile=True)
    if (
        snapshot.data_ref.kind != DERIVED_MODEL_INPUT_PAYLOAD_KIND
        or payload_manifest.artifact_schema
        != SchemaInfo(name="polisyos.runtime.quality.DerivedModelInputPayload", version="1.0")
        or not isinstance(raw_payload, Mapping)
    ):
        raise DataSnapshotLineageError("derived_model_input_payload_manifest_mismatch")
    base_snapshot = validate_core_model_json_artifact(
        DataSnapshot, store, lineage.base_data_snapshot_ref
    )
    base_result = validate_data_snapshot_owner_lineage(
        store,
        lineage.base_data_snapshot_ref,
        base_snapshot,
        candidate_only=True,
        _seen=seen,
    )
    selected_set, obligations = load_model_input_obligation_set(
        store, lineage.model_input_obligation_set_ref
    )
    expected_members = tuple(artifact_ref_identity_key(ref) for ref in selected_set.obligation_refs)
    actual_members = tuple(
        artifact_ref_identity_key(item.model_input_obligation_ref) for item in lineage.selections
    )
    if (
        not actual_members
        or len(actual_members) != len(set(actual_members))
        or set(actual_members) != set(expected_members)
    ):
        raise DataSnapshotLineageError("derived_model_input_complete_target_set_required")
    predecessor = load_input_bindings(store, selected_set.invocation.input_bindings_ref)
    if artifact_ref_identity_key(predecessor.data_snapshot_ref) != artifact_ref_identity_key(
        lineage.base_data_snapshot_ref
    ):
        raise DataSnapshotLineageError("derived_model_input_base_context_mismatch")
    by_member = dict(zip(expected_members, obligations, strict=True))
    base_payload = _read_owner_band_payload(
        store, _verified_manifest(store, base_snapshot.data_ref)
    )
    if not isinstance(base_payload, dict) or "derived_inputs" in base_payload:
        raise DataSnapshotLineageError("derived_model_input_base_payload_profile_unsupported")
    expected_payload = copy.deepcopy(base_payload)
    derived_values: dict[str, dict[str, object]] = {}
    payload_edges: list[tuple[ArtifactRef, str]] = [
        (base_snapshot.data_ref, "context.base_payload")
    ]
    for selection in lineage.selections:
        obligation = by_member[artifact_ref_identity_key(selection.model_input_obligation_ref)]
        if (
            artifact_ref_identity_key(selection.model_interface_ref)
            != artifact_ref_identity_key(selected_set.invocation.interface_ref)
            or selection.model_port_id != obligation.port.port_id
        ):
            raise DataSnapshotLineageError("derived_model_input_selected_port_mismatch")
        key = hashlib.sha256(selection.binding_id.encode()).hexdigest()[:20]
        if key in derived_values or selection.source_path != f"derived_inputs.{key}.value":
            raise DataSnapshotLineageError("derived_model_input_source_path_collision")
        derived_values[key] = {"value": _replay_derived_selection_value(store, selection)}
        payload_edges.extend(
            (
                (selection.output_ref, selection.payload_output_role()),
                (selection.correspondence_ref, "derived.correspondence"),
            )
        )
    _require_exact_owner_edges(store, manifest=payload_manifest, expected=tuple(payload_edges))
    expected_payload["derived_inputs"] = derived_values
    spec = CanonSpec(forbid_floats=False)
    if to_canonical_bytes(raw_payload, spec) != to_canonical_bytes(expected_payload, spec):
        raise DataSnapshotLineageError("derived_model_input_payload_replay_mismatch")
    return base_result


def _verify_candidate_acquisition_source_owner(
    store: ArtifactStore,
    snapshot_ref: ArtifactRef,
    snapshot: DataSnapshot,
    lineage: CandidateAcquisitionSourceDataSnapshotLineage,
    *,
    seen: frozenset[tuple[str, str | None]],
) -> tuple[str, ...]:
    """Replay the candidate owner without borrowing observed-epoch authority."""
    from polisyos.core.artifacts import validate_core_model_json_artifact

    _require_selected_refs(
        snapshot.data_ref,
        lineage.base_data_snapshot_ref,
        lineage.candidate_source_ref,
    )
    payload_manifest = _manifest_view(store, snapshot.data_ref)
    if (
        snapshot.data_ref.kind != "fabric.production_data_state_payload"
        or snapshot.data_ref.media_type != "application/json"
        or payload_manifest.artifact_schema not in _CANDIDATE_PAYLOAD_SCHEMAS
        or lineage.candidate_source_ref.kind != "runtime.quality.candidate_acquisition_source"
        or lineage.candidate_source_ref.media_type != "application/json"
    ):
        raise DataSnapshotLineageError("candidate_acquisition_source_payload_manifest_mismatch")
    _require_exact_owner_edges(
        store,
        manifest=payload_manifest,
        expected=(
            (lineage.base_data_snapshot_ref, "input.base_data_snapshot"),
            (lineage.candidate_source_ref, "evidence.candidate_acquisition_source"),
        ),
    )
    _verified_manifest(store, lineage.base_data_snapshot_ref, require_selected_profile=True)
    _verified_manifest(store, lineage.candidate_source_ref, require_selected_profile=True)
    try:
        base_snapshot = validate_core_model_json_artifact(
            DataSnapshot, store, lineage.base_data_snapshot_ref
        )
        base_result = validate_data_snapshot_owner_lineage(
            store,
            lineage.base_data_snapshot_ref,
            base_snapshot,
            candidate_only=True,
            _seen=seen,
        )
        from polisyos.runtime.quality.data_state_substrate import (
            verify_candidate_acquisition_snapshot_payload,
        )

        verify_candidate_acquisition_snapshot_payload(
            store=store,
            snapshot_ref=snapshot_ref,
            snapshot=snapshot,
            base_data_snapshot_ref=lineage.base_data_snapshot_ref,
            candidate_source_ref=lineage.candidate_source_ref,
        )
        payload = load_core_json_artifact(store, snapshot.data_ref)
        marker = payload.get("_policyos_candidate_acquisition")
        limitations = marker.get("limitation_codes") if isinstance(marker, Mapping) else None
        if not isinstance(limitations, list) or any(
            type(value) is not str for value in limitations
        ):
            raise DataSnapshotLineageError("candidate_acquisition_source_limitations_invalid")
        return tuple(dict.fromkeys((*limitations, *base_result.required_admissibility_blockers)))
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise DataSnapshotLineageError("candidate_acquisition_source_owner_replay_failed") from exc


def _measurement_root_producer() -> ProducerInfo:
    return ProducerInfo(
        component="polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer",
        version="2.0.0",
    )


def _fetch_producer() -> ProducerInfo:
    return ProducerInfo(
        component="polisyos.fabric.retrieval.executor.FetchExecutor", version="1.0.0"
    )


def _require_selected_refs(*refs: ArtifactRef) -> None:
    if any(not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None for ref in refs):
        raise DataSnapshotLineageError("data_snapshot_owner_profile_unselected")


def _data_forge_cas_uri(ref: ArtifactRef) -> str:
    return f"cas://sha256/{str(ref.artifact_id).removeprefix('sha256:')}"


__all__ = [
    "ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION",
    "CANDIDATE_SOURCE_LIMITATIONS",
    "DERIVED_MODEL_INPUT_LIMITATIONS",
    "DataSnapshotLineageError",
    "DataSnapshotLineageResult",
    "DataSnapshotSourceRowNotEstablishedError",
    "validate_data_snapshot_owner_lineage",
]
