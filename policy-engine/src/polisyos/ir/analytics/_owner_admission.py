"""Private owner-side declarations for analytics-family IR JSON artifacts.

This module registers caller-declared tuples and delegates admission and I/O to
the shared IR owner contract primitives. It contains no resource router or
history fallback.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration, CanonInfo
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRCompatibilityKind,
    IRRepresentationKey,
    IRRepresentationRegistration,
    ResolvedSchemaAdmission,
    get_ir_owner_registry_snapshot,
    get_schema_rule,
    register_ir_representation,
    register_schema_version,
    resolve_owned_representation,
)

if TYPE_CHECKING:
    from polisyos.ir.model_layer.canon import CanonSpec

_MISSING = object()


@dataclass(frozen=True, slots=True)
class OwnedJSONRepresentation:
    """One exact code-declared analytics JSON wire tuple."""

    schema_name: str
    schema_version: str
    payload_version: str | None
    wire_policy_ref: str
    wire_policy_revision: str
    profile_ref: str | None
    compatibility: CompatibilityMode
    notes: tuple[str, ...]
    readable: bool
    writable: bool
    current: bool
    default_write: bool
    readable_from: tuple[IRRepresentationKey, ...]


def declared_payload_version(payload: object, *, field_name: str | None) -> str | None:
    """Read only the code-declared version field; malformed presence never falls back."""
    if not isinstance(payload, Mapping):
        raise TypeError("owned JSON payload must be a mapping")
    if field_name is None:
        if "schema_version" in payload:
            raise ValueError("versionless owner received an embedded schema_version")
        return None
    if type(field_name) is not str or not field_name.strip():
        raise ValueError("owned JSON payload version field must be explicitly named")
    value = payload.get(field_name, _MISSING)
    if type(value) is not str or not value.strip():
        raise ValueError("owned JSON payload version is missing or malformed")
    return value


def validate_owner_payload[SourceT](
    payload: object,
    admission: ResolvedSchemaAdmission,
    *,
    payload_version_field: str | None,
    source_parser: Callable[[Mapping[str, Any]], SourceT],
    expected_rows: tuple[IRRepresentationRegistration, ...] | None = None,
    expected_types: tuple[type[BaseModel], ...],
    owner: ArtifactOwnerDeclaration[Any, Any] | None = None,
) -> SourceT:
    """Validate decoded bytes through a trusted owner-selected source DTO parser.

    The `owner` path validates the exact source/current rows already selected by
    the shared I/O layer from its frozen registry snapshot. This helper does not
    independently attest that a caller-constructed admission came from that
    snapshot; callers at artifact boundaries must pass the admission supplied
    by `_get_owned_json_artifact_with_bytes` or `_put_owned_json_artifact`.
    `expected_rows` remains for legacy family callbacks while they migrate.
    """
    if not isinstance(payload, Mapping):
        raise TypeError("owned JSON source must be a decoded mapping")
    if owner is not None:
        _validate_owner_admission(owner, admission)
        if expected_rows is not None:
            raise ValueError("owner-bound intake cannot also use a static row allowlist")
    else:
        if (
            admission.compatibility_kind
            not in (IRCompatibilityKind.EXACT, IRCompatibilityKind.DIRECT)
            or admission.migration_path
        ):
            raise ValueError("analytics typed intake requires an exact or direct source row")
        if expected_rows is None:
            raise ValueError("analytics typed intake requires a trusted owner or exact legacy rows")
    actual_version = declared_payload_version(payload, field_name=payload_version_field)
    if actual_version != admission.source_registration.payload_version:
        raise ValueError("analytics payload version does not match the exact registered tuple")
    if owner is None and (
        admission.source_registration not in expected_rows
        or admission.current_registration not in expected_rows
    ):
        raise ValueError("analytics source/current tuple is not registered by this owner")
    source = source_parser(dict(payload))
    if not expected_types or type(source) not in expected_types:
        raise TypeError("analytics source parser returned an undeclared DTO")
    return source


def _owner_row_matches_declaration(
    owner: ArtifactOwnerDeclaration[Any, Any],
    registration: IRRepresentationRegistration,
) -> bool:
    """Match the exact owner identity and one code-accepted wire adapter."""
    return (
        registration.registry_key == owner.registry_key
        and registration.owner_ref == owner.contract_id
        and registration.dto_abi == owner.dto_fqn
        and (registration.wire_policy_ref, registration.wire_policy_revision)
        in owner.accepted_wire_policies
    )


def _validate_owner_admission(
    owner: ArtifactOwnerDeclaration[Any, Any],
    admission: ResolvedSchemaAdmission,
) -> None:
    """Reconcile owner bindings and the directed route in a frozen admission."""
    if type(owner) is not ArtifactOwnerDeclaration:
        raise TypeError("analytics source validation requires the shared owner declaration")
    if type(admission) is not ResolvedSchemaAdmission:
        raise TypeError("analytics source validation requires an exact owner admission")
    source = admission.source_registration
    current = admission.current_registration
    if (
        type(source) is not IRRepresentationRegistration
        or type(current) is not IRRepresentationRegistration
        or not _owner_row_matches_declaration(owner, source)
        or not _owner_row_matches_declaration(owner, current)
        or source.schema_name != current.schema_name
        or not source.readable
        or not current.readable
        or not current.current
        or admission.profile_ref != source.profile_ref
    ):
        raise ValueError("analytics source/current rows do not match the trusted owner")
    if admission.compatibility_kind is IRCompatibilityKind.EXACT:
        if source.key != current.key:
            raise ValueError("exact analytics admission does not identify one registered tuple")
    elif admission.compatibility_kind is IRCompatibilityKind.DIRECT:
        same_wire_law = (
            source.wire_policy_ref == current.wire_policy_ref
            and source.wire_policy_revision == current.wire_policy_revision
        )
        if source.key not in current.readable_from and not same_wire_law:
            raise ValueError("direct analytics admission has no declared owner route")
    else:
        raise ValueError("analytics typed intake does not admit migration routes")
    if admission.migration_path:
        raise ValueError("analytics typed intake does not admit migration paths")


def resolve_registered_owner_payload_admission(
    owner: ArtifactOwnerDeclaration[Any, Any],
    payload: object,
    *,
    schema_name: str,
    snapshot_revision: str,
) -> ResolvedSchemaAdmission:
    """Resolve an embedded owner payload against the enclosing frozen registry.

    Embedded DTOs have no separate CAS manifest. Their schema name is therefore
    supplied by trusted code, while the embedded payload version may select only
    one exact readable registration already present in the same registry
    revision as the enclosing admission. The selected row's code-owned wire law
    still determines which parser runs.
    """
    if type(owner) is not ArtifactOwnerDeclaration:
        raise TypeError("embedded analytics intake requires the shared owner declaration")
    if type(schema_name) is not str or not schema_name.strip():
        raise ValueError("embedded analytics schema name must be code-selected")
    if type(snapshot_revision) is not str or not snapshot_revision.strip():
        raise ValueError("embedded analytics intake requires the enclosing registry revision")
    try:
        snapshot = get_ir_owner_registry_snapshot()
    except Exception as exc:
        raise ValueError("embedded analytics registry snapshot is unavailable") from exc
    if snapshot.revision != snapshot_revision:
        raise ValueError("embedded analytics registry revision changed during admission")
    payload_version = owner.payload_version_of(payload)
    if payload_version is not None and (
        type(payload_version) is not str or not payload_version.strip()
    ):
        raise ValueError("embedded analytics payload version is malformed")
    candidates = tuple(
        registration
        for registration in snapshot.representation_records
        if registration.schema_name == schema_name
        and registration.payload_version == payload_version
        and registration.readable
        and _owner_row_matches_declaration(owner, registration)
    )
    if len(candidates) != 1:
        raise ValueError("embedded analytics payload has no unique registered owner tuple")
    source = candidates[0]
    admission = resolve_owned_representation(
        snapshot,
        owner.registry_key,
        owner_ref=owner.contract_id,
        schema_name=schema_name,
        schema_version=source.schema_version,
        payload_version=payload_version,
    )
    if (
        admission is None
        or admission.snapshot_revision != snapshot_revision
        or admission.source_registration != source
    ):
        raise ValueError("embedded analytics payload has no exact owner reader route")
    _validate_owner_admission(owner, admission)
    return admission


def project_owner_source[SourceT](
    expected_types: tuple[type[BaseModel], ...],
    source: SourceT,
) -> SourceT:
    """Require projection to preserve the exact owner-declared model instance."""
    if not expected_types or type(source) not in expected_types:
        raise TypeError("analytics consumer projection does not match its declared DTO")
    return source


def owner_profile_for_spec(
    spec: CanonSpec, *, profile_ref: str | None
) -> Callable[[CanonInfo, IRRepresentationRegistration], bool]:
    """Bind an owner callback to one exact canonical profile and registry profile ref."""
    expected = CanonInfo.from_spec(spec)

    def validate_profile(profile: CanonInfo, registration: IRRepresentationRegistration) -> bool:
        return registration.profile_ref == profile_ref and profile == expected

    return validate_profile


def _ensure_schema_rule(
    registry_key: str,
    representation: OwnedJSONRepresentation,
) -> None:
    """Reuse only an identical existing schema law; never infer compatibility."""
    try:
        expected_mode = CompatibilityMode(representation.compatibility)
    except (TypeError, ValueError) as exc:
        raise ValueError("analytics schema compatibility must be declared") from exc
    existing = get_schema_rule(registry_key, representation.schema_version)
    if existing is None:
        register_schema_version(
            registry_key,
            representation.schema_version,
            compatibility=expected_mode,
            notes=representation.notes,
        )
        return
    if (
        existing.mode is not expected_mode
        or existing.notes != representation.notes
        or existing.readable_versions
        or existing.writable_versions
        or existing.additive_optional_fields
        or existing.removed_fields
        or existing.renamed_fields
        or existing.canonical_defaults
    ):
        raise ValueError(
            "analytics representation conflicts with the existing schema compatibility law"
        )


def register_owner_representations(
    owner: ArtifactOwnerDeclaration[Any, Any],
    representations: tuple[OwnedJSONRepresentation, ...],
) -> tuple[IRRepresentationRegistration, ...]:
    """Register only exact schema/payload/profile tuples declared by the owner."""
    if type(owner) is not ArtifactOwnerDeclaration:
        raise TypeError("analytics owner declaration must use the shared owner contract")
    if type(representations) is not tuple or not representations:
        raise ValueError("analytics owners require explicit representation rows")

    registrations: list[IRRepresentationRegistration] = []
    for representation in representations:
        if type(representation) is not OwnedJSONRepresentation:
            raise TypeError("analytics representation must use the exact declaration type")
        wire_policy = (
            representation.wire_policy_ref,
            representation.wire_policy_revision,
        )
        if wire_policy not in owner.accepted_wire_policies:
            raise ValueError("analytics representation uses an undeclared wire policy")
        _ensure_schema_rule(owner.registry_key, representation)
        registrations.append(
            register_ir_representation(
                registry_key=owner.registry_key,
                owner_ref=owner.contract_id,
                dto_abi=owner.dto_fqn,
                wire_policy_ref=representation.wire_policy_ref,
                wire_policy_revision=representation.wire_policy_revision,
                schema_name=representation.schema_name,
                schema_version=representation.schema_version,
                payload_version=representation.payload_version,
                profile_ref=representation.profile_ref,
                readable=representation.readable,
                writable=representation.writable,
                current=representation.current,
                default_write=representation.default_write,
                readable_from=representation.readable_from,
            )
        )
    return tuple(registrations)


def declare_model_owner[ModelT: BaseModel](
    model: type[ModelT],
    *,
    contract_id: str,
    dto_fqn: str,
    abi_key: str,
    registry_key: str,
    kind: str,
    media_type: str,
    purpose: str,
    policy_revision: str,
    accepted_wire_policies: tuple[tuple[str, str], ...],
    payload_version_field: str | None,
    validate_profile: Callable[[CanonInfo, IRRepresentationRegistration], bool],
    representations: tuple[OwnedJSONRepresentation, ...],
) -> ArtifactOwnerDeclaration[ModelT, ModelT]:
    """Bind a code-selected DTO parser, consumer projection, and explicit wire rows."""
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise TypeError("analytics owner requires a Pydantic model class")

    def payload_version_of(payload: object) -> str | None:
        return declared_payload_version(payload, field_name=payload_version_field)

    owner: ArtifactOwnerDeclaration[ModelT, ModelT] | None = None

    def validate_source(payload: object, admission: ResolvedSchemaAdmission) -> ModelT:
        if not isinstance(payload, Mapping):
            raise TypeError("analytics source must be a decoded mapping")
        if owner is None:
            raise RuntimeError("analytics owner callback ran before declaration was complete")
        return validate_owner_payload(
            payload,
            admission,
            payload_version_field=payload_version_field,
            source_parser=model.model_validate,
            expected_types=(model,),
            owner=owner,
        )

    def project_for_consumer(source: ModelT, _admission: ResolvedSchemaAdmission) -> ModelT:
        return project_owner_source((model,), source)

    owner = ArtifactOwnerDeclaration(
        contract_id=contract_id,
        dto_fqn=dto_fqn,
        abi_key=abi_key,
        registry_key=registry_key,
        kind=kind,
        media_type=media_type,
        purpose=purpose,
        policy_revision=policy_revision,
        accepted_wire_policies=accepted_wire_policies,
        payload_version_of=payload_version_of,
        validate_source=validate_source,
        project_for_consumer=project_for_consumer,
        validate_profile=validate_profile,
    )
    register_owner_representations(owner, representations)
    return owner
