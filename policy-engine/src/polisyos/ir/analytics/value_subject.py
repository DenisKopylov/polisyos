"""Reconcile declared scalar subjects across separate persisted value channels.

This reader establishes selected content and lineage consistency only. Subject
meaning, source rights, scientific validity and production admission remain with
their actual owners; a successful join cannot promote either channel.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common.canonical_profile import _manifest_profile_sha256
from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    declare_model_owner,
    owner_profile_for_spec,
)
from polisyos.ir.analytics.estimand import load_estimand_ast
from polisyos.ir.artifacts import ArtifactStore, InputRef, normalize_artifact_ref
from polisyos.ir.artifacts.io import (
    _get_owned_json_artifact,
    _put_owned_json_artifact,
    normalize_input_sequence,
)
from polisyos.ir.kernel.units import RateUnit, UnitSpecType
from polisyos.ir.migrations.base import CompatibilityMode
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel, EstimandASTRef

if TYPE_CHECKING:
    from polisyos.ir.artifacts import InputRefLike
    from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration

_VERSION = "1.1"
_CANON = CanonSpec(forbid_floats=False, exclude_none=False)
_SUBJECT_ROLE = "value_subject"
_RESERVED_ROLES = frozenset({_SUBJECT_ROLE, "value_estimand", "value_source", "value_model"})


class ValueArtifactSubjectRef(ArtifactRefModel):
    """Select one persisted declared scalar subject and its exact manifest view."""

    kind: Literal["ir.value_artifact_subject"] = "ir.value_artifact_subject"
    media_type: Literal["application/json"] = "application/json"


class ValueSubjectRelationRef(ArtifactRefModel):
    """Select a recomputable content join without granting value authority."""

    kind: Literal["ir.value_subject_relation"] = "ir.value_subject_relation"
    media_type: Literal["application/json"] = "application/json"


class ValueArtifactSubject(BaseModel):
    """Declare one quantity before persisting its separate analytical channels."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.1"] = "1.1"
    subject_provenance: Literal["consumer_asserted"] = "consumer_asserted"
    production_value_eligible: Literal[False] = False
    estimand_ref: EstimandASTRef
    estimand_id: str = Field(min_length=1)
    exposure: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    control_value: float
    treatment_value: float
    population: str = Field(min_length=1)
    unit: UnitSpecType
    scale: Literal["identity"] = "identity"
    time_horizon: str = Field(min_length=1)
    prediction_origin: str | None = None
    epoch: str = Field(min_length=1)
    source_refs: tuple[ArtifactRefModel, ...] = Field(min_length=1)
    model_ref: ArtifactRefModel | None = None

    @model_validator(mode="after")
    def _validate_subject(self) -> ValueArtifactSubject:
        if not all(math.isfinite(value) for value in (self.control_value, self.treatment_value)):
            raise ValueError("value_subject_nonfinite_contrast")
        refs = (
            self.estimand_ref,
            *self.source_refs,
            *((self.model_ref,) if self.model_ref else ()),
        )
        for ref in refs:
            _selected_ref(ref)
        source_keys = [_ref_key(ref) for ref in self.source_refs]
        if len(set(source_keys)) != len(source_keys):
            raise ValueError("value_subject_duplicate_source")
        return self


class ValueSubjectArtifactIdentity(BaseModel):
    """Retain the resolved payload and selected manifest identities of one input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: ArtifactRefModel
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    manifest_profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ValueSubjectRelation(BaseModel):
    """Keep identification and native uncertainty separate after a content join."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.1"] = "1.1"
    authority_scope: Literal["resolved_declared_content_join_only"] = (
        "resolved_declared_content_join_only"
    )
    subject_provenance: Literal["consumer_asserted"] = "consumer_asserted"
    production_value_eligible: Literal[False] = False
    identification: ValueSubjectArtifactIdentity
    native_uncertainty: ValueSubjectArtifactIdentity
    identification_subject: ValueSubjectArtifactIdentity
    native_subject: ValueSubjectArtifactIdentity
    resolved_subject: ValueArtifactSubject
    native_to_identification_factor: float = Field(gt=0, strict=True)
    verifier_provenance: Literal["selected_content_and_lineage_recomputed.v1.1"] = (
        "selected_content_and_lineage_recomputed.v1.1"
    )

    @model_validator(mode="after")
    def _validate_factor(self) -> ValueSubjectRelation:
        if self.native_to_identification_factor not in (0.01, 1.0, 100.0):
            raise ValueError("value_subject_unsupported_unit_factor")
        return self


def _selected_ref(ref: object) -> dict[str, str]:
    selected = normalize_artifact_ref(ref)
    if not selected.get("manifest_profile_sha256"):
        raise ValueError("value_subject_selected_profile_required")
    return selected


def _ref_key(ref: object) -> tuple[str, str, str, str]:
    selected = _selected_ref(ref)
    return (
        selected["artifact_id"],
        selected["kind"],
        selected["media_type"],
        selected["manifest_profile_sha256"],
    )


def _identity(
    store: ArtifactStore, ref: object
) -> tuple[ValueSubjectArtifactIdentity, dict[str, Any]]:
    selected = _selected_ref(ref)
    manifest = store.get_manifest(selected)
    if isinstance(manifest, BaseModel):
        payload = manifest.model_dump(mode="json", by_alias=True, exclude_none=True)
    elif isinstance(manifest, Mapping):
        payload = dict(manifest)
    else:
        raise ValueError("value_subject_manifest_invalid")
    # Freeze the typed manifest before another store operation can mutate a
    # mapping-backed view. This does not assert raw-manifest wire conformance.
    payload = json.loads(json.dumps(payload, allow_nan=False))
    if any(str(payload.get(key)) != selected[key] for key in ("artifact_id", "kind", "media_type")):
        raise ValueError("value_subject_manifest_identity_mismatch")
    profile = _manifest_profile_sha256(payload)
    if profile != selected["manifest_profile_sha256"]:
        raise ValueError("value_subject_manifest_profile_mismatch")
    raw = store.get_bytes(selected)
    if not isinstance(raw, bytes):
        raise TypeError("value_subject_payload_bytes_required")
    content = "sha256:" + hashlib.sha256(raw).hexdigest()
    if content != selected["artifact_id"]:
        raise ValueError("value_subject_artifact_content_mismatch")
    return (
        ValueSubjectArtifactIdentity(
            ref=ArtifactRefModel.model_validate(selected),
            content_hash=content,
            manifest_profile_sha256=profile,
        ),
        payload,
    )


def _input_key(edge: InputRef) -> tuple[str, str, str | None]:
    return edge.role, str(edge.artifact_id), edge.manifest_profile_sha256


def _manifest_inputs(manifest: Mapping[str, Any]) -> list[InputRef]:
    raw = manifest.get("inputs", [])
    if not isinstance(raw, list):
        raise ValueError("value_subject_lineage_invalid")
    return [InputRef.model_validate(edge) for edge in raw]


def _subject_inputs(subject: ValueArtifactSubject) -> list[InputRef]:
    refs: list[tuple[str, ArtifactRefModel]] = [("value_estimand", subject.estimand_ref)]
    refs.extend(("value_source", ref) for ref in subject.source_refs)
    if subject.model_ref is not None:
        refs.append(("value_model", subject.model_ref))
    return [
        InputRef(
            artifact_id=ref.artifact_id,
            role=role,
            manifest_profile_sha256=_selected_ref(ref)["manifest_profile_sha256"],
        )
        for role, ref in refs
    ]


def _validate_subject_dependencies(store: ArtifactStore, subject: ValueArtifactSubject) -> None:
    estimand = load_estimand_ast(store, subject.estimand_ref)
    if (
        estimand.object_kind != "scalar"
        or estimand.outcome != subject.outcome
        or estimand.treatment != subject.exposure
    ):
        raise ValueError("value_subject_estimand_mismatch")
    for ref in (
        subject.estimand_ref,
        *subject.source_refs,
        *((subject.model_ref,) if subject.model_ref else ()),
    ):
        _identity(store, ref)


def _model_owner[ModelT: BaseModel](
    model: type[ModelT], name: str
) -> ArtifactOwnerDeclaration[ModelT, ModelT]:
    return declare_model_owner(
        model,
        contract_id=f"ir.analytics.{name}.owner.v1",
        dto_fqn=f"{model.__module__}.{model.__qualname__}",
        abi_key=f"ir.analytics.{name}.dto-abi.v1",
        registry_key=f"ir.{name}",
        kind=f"ir.{name}",
        media_type="application/json",
        purpose="declared_value_subject_content_join",
        policy_revision=f"ir.analytics.{name}.admission.v1",
        accepted_wire_policies=((f"ir.analytics.{name}.wire-law", "1"),),
        payload_version_field="schema_version",
        validate_profile=owner_profile_for_spec(_CANON, profile_ref=None),
        representations=(
            OwnedJSONRepresentation(
                schema_name=f"ir.{name}",
                schema_version=_VERSION,
                payload_version=_VERSION,
                wire_policy_ref=f"ir.analytics.{name}.wire-law",
                wire_policy_revision="1",
                profile_ref=None,
                compatibility=CompatibilityMode.NONE,
                notes=("Selected content join only; subject semantics remain declared.",),
                readable=True,
                writable=True,
                current=True,
                default_write=True,
                readable_from=(),
            ),
        ),
    )


_SUBJECT_OWNER = _model_owner(ValueArtifactSubject, "value_artifact_subject")
_RELATION_OWNER = _model_owner(ValueSubjectRelation, "value_subject_relation")


def persist_value_artifact_subject(
    store: ArtifactStore, subject: ValueArtifactSubject
) -> ValueArtifactSubjectRef:
    """Persist a declared subject after resolving all selected dependencies.

    Args:
        store: CAS containing the selected estimand, source and optional model.
        subject: Caller-declared scalar meaning; this writer grants no authority.

    Returns:
        The exact manifest profile selected by this write.
    """
    subject = ValueArtifactSubject.model_validate(
        subject.model_dump(mode="python", round_trip=True)
    )
    _validate_subject_dependencies(store, subject)
    ref = _put_owned_json_artifact(
        store,
        subject.model_dump(mode="python", round_trip=True),
        owner=_SUBJECT_OWNER,
        schema_name="ir.value_artifact_subject",
        schema_version=_VERSION,
        inputs=_subject_inputs(subject),
        canon_spec=_CANON,
    )
    return ValueArtifactSubjectRef.from_selected_write(ref)


def load_value_artifact_subject(
    store: ArtifactStore, ref: ValueArtifactSubjectRef
) -> ValueArtifactSubject:
    """Read the exact subject and reconcile its complete declared lineage.

    Args:
        store: CAS from which to resolve all selected dependencies.
        ref: Complete subject reference, including its manifest profile.

    Returns:
        The content-bound declaration, with its candidate-only status preserved.
    """
    _, manifest = _identity(store, ref)
    subject = _get_owned_json_artifact(store, ref, owner=_SUBJECT_OWNER)
    if Counter(map(_input_key, _manifest_inputs(manifest))) != Counter(
        map(_input_key, _subject_inputs(subject))
    ):
        raise ValueError("value_subject_dependency_lineage_mismatch")
    _validate_subject_dependencies(store, subject)
    return subject


def value_subject_producer_inputs(
    store: ArtifactStore,
    subject_ref: ArtifactRefModel,
    *,
    inputs: Sequence[InputRefLike] | None = None,
) -> list[InputRef]:
    """Bind a producer to one selected subject without discarding other inputs.

    Args:
        store: CAS containing the selected subject and its dependencies.
        subject_ref: Exact subject profile to add to the producer's lineage.
        inputs: Existing non-reserved producer inputs to preserve.

    Returns:
        Existing inputs followed by the selected subject and dependency roster.
    """
    selected = ValueArtifactSubjectRef.model_validate(_selected_ref(subject_ref))
    subject = load_value_artifact_subject(store, selected)
    existing = normalize_input_sequence(inputs)
    if any(edge.role in _RESERVED_ROLES for edge in existing):
        raise ValueError("value_subject_reserved_producer_lineage")
    return [
        *existing,
        InputRef(
            artifact_id=selected.artifact_id,
            role=_SUBJECT_ROLE,
            manifest_profile_sha256=selected.manifest_profile_sha256,
        ),
        *_subject_inputs(subject),
    ]


def _subject_for_artifact(
    store: ArtifactStore, ref: ArtifactRefModel
) -> tuple[ValueSubjectArtifactIdentity, ValueSubjectArtifactIdentity, ValueArtifactSubject]:
    artifact, manifest = _identity(store, ref)
    inputs = _manifest_inputs(manifest)
    subject_edges = [edge for edge in inputs if edge.role == _SUBJECT_ROLE]
    if len(subject_edges) != 1:
        raise ValueError("value_subject_lineage_missing_or_duplicate")
    edge = subject_edges[0]
    subject_ref = ValueArtifactSubjectRef(
        artifact_id=edge.artifact_id, manifest_profile_sha256=edge.manifest_profile_sha256
    )
    subject = load_value_artifact_subject(store, subject_ref)
    expected = value_subject_producer_inputs(store, subject_ref)
    actual = [item for item in inputs if item.role in _RESERVED_ROLES]
    if Counter(map(_input_key, actual)) != Counter(map(_input_key, expected)):
        raise ValueError("value_subject_producer_lineage_mismatch")
    subject_identity, _ = _identity(store, subject_ref)
    return artifact, subject_identity, subject


def _unit_factor(native: ValueArtifactSubject, identification: ValueArtifactSubject) -> float:
    if native.model_dump(mode="python", exclude={"unit"}) != identification.model_dump(
        mode="python", exclude={"unit"}
    ):
        raise ValueError("value_subject_quantity_mismatch")
    if native.unit == identification.unit:
        return 1.0
    if isinstance(native.unit, RateUnit) and isinstance(identification.unit, RateUnit):
        return 100.0 if native.unit.base == "ratio" else 0.01
    raise ValueError("value_subject_unit_mismatch")


def resolve_value_subject_relation(
    store: ArtifactStore,
    *,
    identification_ref: ArtifactRefModel,
    native_uncertainty_ref: ArtifactRefModel,
) -> ValueSubjectRelation:
    """Resolve both owned channels and recompute their declared subject/unit join.

    Supported channels are an IR BoundsBundle and an UncertaintyEnvelope. Values
    and interval semantics remain unchanged; the factor is disclosed, not applied.
    Other producer inputs remain inspectable lineage, not proof that the producer
    consumed the declared sources or implemented the declared estimand.

    Args:
        store: CAS containing both selected channels and their dependencies.
        identification_ref: Owner-bound BoundsBundle reference.
        native_uncertainty_ref: Owner-bound UncertaintyEnvelope reference.

    Returns:
        A candidate-only relation; its declared meaning is not independently verified.
    """
    from polisyos.ir.analytics.partial_identification import load_bounds_bundle
    from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
    from polisyos.ir.registry.refs import BoundsBundleRef, UncertaintyEnvelopeRef

    identified_ref = BoundsBundleRef.model_validate(_selected_ref(identification_ref))
    native_ref = UncertaintyEnvelopeRef.model_validate(_selected_ref(native_uncertainty_ref))
    bounds = load_bounds_bundle(store, identified_ref)
    load_uncertainty_envelope(store, native_ref)
    identified, identified_subject, subject = _subject_for_artifact(store, identified_ref)
    native, native_subject, native_quantity = _subject_for_artifact(store, native_ref)
    if bounds.estimand_type != subject.estimand_id:
        raise ValueError("value_subject_bounds_estimand_mismatch")
    return ValueSubjectRelation(
        identification=identified,
        native_uncertainty=native,
        identification_subject=identified_subject,
        native_subject=native_subject,
        resolved_subject=subject,
        native_to_identification_factor=_unit_factor(native_quantity, subject),
    )


def _relation_inputs(relation: ValueSubjectRelation) -> list[InputRef]:
    return [
        InputRef(
            artifact_id=identity.ref.artifact_id,
            role=role,
            manifest_profile_sha256=identity.ref.manifest_profile_sha256,
        )
        for role, identity in (
            ("identification", relation.identification),
            ("native_uncertainty", relation.native_uncertainty),
            ("identification_subject", relation.identification_subject),
            ("native_subject", relation.native_subject),
        )
    ]


def persist_value_subject_relation(
    store: ArtifactStore,
    *,
    identification_ref: ArtifactRefModel,
    native_uncertainty_ref: ArtifactRefModel,
) -> ValueSubjectRelationRef:
    """Persist a recomputed join rather than accepting a verification marker.

    Args:
        store: CAS containing both selected channels and their dependencies.
        identification_ref: Owner-bound BoundsBundle reference.
        native_uncertainty_ref: Owner-bound UncertaintyEnvelope reference.

    Returns:
        The selected profile of the recomputed, candidate-only relation.
    """
    relation = resolve_value_subject_relation(
        store, identification_ref=identification_ref, native_uncertainty_ref=native_uncertainty_ref
    )
    ref = _put_owned_json_artifact(
        store,
        relation.model_dump(mode="python", round_trip=True),
        owner=_RELATION_OWNER,
        schema_name="ir.value_subject_relation",
        schema_version=_VERSION,
        inputs=_relation_inputs(relation),
        canon_spec=_CANON,
    )
    return ValueSubjectRelationRef.from_selected_write(ref)


def load_value_subject_relation(
    store: ArtifactStore, ref: ValueSubjectRelationRef
) -> ValueSubjectRelation:
    """Read a selected relation and freshly recompute both content-bound channels.

    Args:
        store: CAS from which to resolve the selected relation and all inputs.
        ref: Complete relation reference, including its manifest profile.

    Returns:
        The newly recomputed relation after comparison with the stored payload.
    """
    _, manifest = _identity(store, ref)
    relation = _get_owned_json_artifact(store, ref, owner=_RELATION_OWNER)
    if Counter(map(_input_key, _manifest_inputs(manifest))) != Counter(
        map(_input_key, _relation_inputs(relation))
    ):
        raise ValueError("value_subject_relation_lineage_mismatch")
    recomputed = resolve_value_subject_relation(
        store,
        identification_ref=relation.identification.ref,
        native_uncertainty_ref=relation.native_uncertainty.ref,
    )
    _require_relation_match(relation, recomputed)
    return recomputed


def _require_relation_match(stored: ValueSubjectRelation, recomputed: ValueSubjectRelation) -> None:
    if stored != recomputed:
        raise ValueError("value_subject_relation_stale_or_forged")


__all__ = [
    "ValueArtifactSubject",
    "ValueArtifactSubjectRef",
    "ValueSubjectArtifactIdentity",
    "ValueSubjectRelation",
    "ValueSubjectRelationRef",
    "load_value_artifact_subject",
    "load_value_subject_relation",
    "persist_value_artifact_subject",
    "persist_value_subject_relation",
    "resolve_value_subject_relation",
    "value_subject_producer_inputs",
]
