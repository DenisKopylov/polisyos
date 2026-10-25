"""Public migrations base module API."""

from __future__ import annotations

import json
import marshal
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
from threading import RLock
from types import MappingProxyType
from typing import Any

from polisyos.common import migrations as common_migrations

MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]

_MIGRATIONS: dict[str, dict[str, MigrationEdge]] = {}
_SCHEMA_REGISTRY: dict[str, dict[str, SchemaCompatibilityRule]] = {}
_REGISTRY_LOCK = RLock()


class MigrationError(ValueError):
    """Base error for IR migration compatibility failures."""


class MigrationSchemaVersionError(MigrationError):
    """Raised when a migrator returns an incompatible schema_version."""


class MigrationCompatibilityError(MigrationError):
    """Raised when a migration edge violates declared schema compatibility policy."""


def _native_identity_text(value: object, field_name: str, *, optional: bool = False) -> str | None:
    """Detach a trusted registry identity from mutable str subclass behavior."""
    if optional and value is None:
        return None
    if not isinstance(value, str):
        expected = "a non-empty string or explicit None" if optional else "a non-empty string"
        raise MigrationCompatibilityError(f"{field_name} must be {expected}")
    try:
        normalized = str.encode(value, "utf-8", "surrogatepass").decode("utf-8", "surrogatepass")
    except Exception as exc:
        raise MigrationCompatibilityError(f"{field_name} must be a stable string") from exc
    if not normalized.strip():
        expected = "a non-empty string or explicit None" if optional else "a non-empty string"
        raise MigrationCompatibilityError(f"{field_name} must be {expected}")
    return normalized


class CompatibilityMode(str, Enum):
    """Declared direct-read compatibility mode for a schema version."""

    FULL = "full"
    BACKWARD = "backward"
    FORWARD = "forward"
    NONE = "none"


@dataclass(frozen=True)
class IRRepresentationKey:
    """Exact manifest and embedded-payload identity for one IR representation."""

    schema_name: str
    schema_version: str
    payload_version: str | None

    def __post_init__(self) -> None:
        """Freeze and validate each string that participates in representation identity."""
        object.__setattr__(
            self, "schema_name", _native_identity_text(self.schema_name, "schema_name")
        )
        object.__setattr__(
            self, "schema_version", _native_identity_text(self.schema_version, "schema_version")
        )
        object.__setattr__(
            self,
            "payload_version",
            _native_identity_text(self.payload_version, "payload_version", optional=True),
        )


def _normalized_representation_key(value: object) -> IRRepresentationKey:
    """Copy a supported key subclass into an exact immutable native key."""
    if not isinstance(value, IRRepresentationKey):
        raise MigrationCompatibilityError(
            "readable_from must contain exact IRRepresentationKey values"
        )
    try:
        return IRRepresentationKey(
            schema_name=object.__getattribute__(value, "schema_name"),
            schema_version=object.__getattribute__(value, "schema_version"),
            payload_version=object.__getattribute__(value, "payload_version"),
        )
    except (AttributeError, TypeError) as exc:
        raise MigrationCompatibilityError("IR representation key is malformed") from exc


@dataclass(frozen=True)
class IRRepresentationRegistration:
    """One explicitly registered owner, DTO ABI, and wire tuple."""

    registry_key: str
    owner_ref: str
    dto_abi: str
    wire_policy_ref: str
    wire_policy_revision: str
    schema_name: str
    schema_version: str
    payload_version: str | None
    profile_ref: str | None = None
    readable: bool = True
    writable: bool = False
    current: bool = False
    default_write: bool = False
    readable_from: tuple[IRRepresentationKey, ...] = ()

    def __post_init__(self) -> None:
        """Store exact native text and relation keys in every immutable registry row."""
        for field_name in (
            "registry_key",
            "owner_ref",
            "dto_abi",
            "wire_policy_ref",
            "wire_policy_revision",
            "schema_name",
            "schema_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _native_identity_text(
                    object.__getattribute__(self, field_name),
                    field_name,
                ),
            )
        object.__setattr__(
            self,
            "payload_version",
            _native_identity_text(
                object.__getattribute__(self, "payload_version"),
                "payload_version",
                optional=True,
            ),
        )
        object.__setattr__(
            self,
            "profile_ref",
            _native_identity_text(
                object.__getattribute__(self, "profile_ref"),
                "profile_ref",
                optional=True,
            ),
        )
        readable_from = object.__getattribute__(self, "readable_from")
        if type(readable_from) is not tuple:
            raise MigrationCompatibilityError(
                "readable_from must contain exact IRRepresentationKey values"
            )
        object.__setattr__(
            self,
            "readable_from",
            tuple(_normalized_representation_key(key) for key in readable_from),
        )

    @property
    def key(self) -> IRRepresentationKey:
        """Return the exact source-declared tuple key."""
        return IRRepresentationKey(self.schema_name, self.schema_version, self.payload_version)


@dataclass(frozen=True)
class SchemaCompatibilityRule:
    """Compatibility declaration for one artifact schema version."""

    artifact: str
    version: str
    mode: CompatibilityMode
    readable_versions: frozenset[str] = frozenset()
    writable_versions: frozenset[str] = frozenset()
    additive_optional_fields: frozenset[str] = frozenset()
    removed_fields: frozenset[str] = frozenset()
    renamed_fields: frozenset[tuple[str, str]] = frozenset()
    canonical_defaults: frozenset[tuple[str, str]] = frozenset()
    notes: tuple[str, ...] = ()
    representations: tuple[IRRepresentationRegistration, ...] = ()


@dataclass(frozen=True)
class MigrationEdge:
    """Registered migration edge with its declared compatibility intent."""

    to_version: str
    fn: MigrationFn
    compatibility: CompatibilityMode
    fingerprint: str


@dataclass(frozen=True)
class SchemaCompatibilityDecision:
    """Rule-based answer for producer/consumer schema negotiation."""

    artifact: str
    producer_version: str
    consumer_version: str
    can_read: bool
    mode: CompatibilityMode
    migration_required: bool = False
    reason: str = ""


@dataclass(frozen=True)
class IRRepresentationPreflight:
    """Non-authorizing metadata result before payload bytes are read."""

    registry_key: str
    owner_ref: str
    schema_name: str
    schema_version: str
    candidates: tuple[IRRepresentationRegistration, ...]
    snapshot_revision: str


@dataclass(frozen=True)
class IRRegistrySnapshot:
    """Immutable registry view pinned for one owned artifact operation."""

    revision: str
    schema_rules: Mapping[tuple[str, str], SchemaCompatibilityRule]
    migration_edges: Mapping[tuple[str, str], MigrationEdge]
    representation_records: tuple[IRRepresentationRegistration, ...]

    @property
    def representations(self) -> tuple[IRRepresentationRegistration, ...]:
        """Return all exact registrations in this snapshot."""
        return self.representation_records


class IRCompatibilityKind(str, Enum):
    """Exact route selected by strict owner admission."""

    EXACT = "exact"
    DIRECT = "direct"
    MIGRATION = "migration"


@dataclass(frozen=True)
class ResolvedSchemaAdmission:
    """Exact source row and current reader route selected from one snapshot."""

    source_registration: IRRepresentationRegistration
    current_registration: IRRepresentationRegistration
    snapshot_revision: str
    compatibility_kind: IRCompatibilityKind
    migration_path: tuple[str, ...] = ()
    profile_ref: str | None = None


def _schema_rule(
    artifact: str,
    version: str,
    *,
    compatibility: CompatibilityMode | str = CompatibilityMode.NONE,
    readable_versions: tuple[str, ...] = (),
    writable_versions: tuple[str, ...] = (),
    additive_optional_fields: tuple[str, ...] = (),
    removed_fields: tuple[str, ...] = (),
    renamed_fields: tuple[tuple[str, str], ...] = (),
    canonical_defaults: tuple[tuple[str, str], ...] = (),
    notes: tuple[str, ...] = (),
) -> SchemaCompatibilityRule:
    return SchemaCompatibilityRule(
        artifact=str(artifact),
        version=str(version),
        mode=_coerce_compatibility_mode(compatibility),
        readable_versions=frozenset(str(item) for item in readable_versions),
        writable_versions=frozenset(str(item) for item in writable_versions),
        additive_optional_fields=frozenset(str(item) for item in additive_optional_fields),
        removed_fields=frozenset(str(item) for item in removed_fields),
        renamed_fields=frozenset((str(old), str(new)) for old, new in renamed_fields),
        canonical_defaults=frozenset(
            (str(field), str(value)) for field, value in canonical_defaults
        ),
        notes=tuple(str(item) for item in notes),
    )


def register_schema_version(
    artifact: str,
    version: str,
    *,
    compatibility: CompatibilityMode | str = CompatibilityMode.NONE,
    readable_versions: tuple[str, ...] = (),
    writable_versions: tuple[str, ...] = (),
    additive_optional_fields: tuple[str, ...] = (),
    removed_fields: tuple[str, ...] = (),
    renamed_fields: tuple[tuple[str, str], ...] = (),
    canonical_defaults: tuple[tuple[str, str], ...] = (),
    notes: tuple[str, ...] = (),
) -> SchemaCompatibilityRule:
    """Register a schema version; identical repeats are idempotent."""

    rule = _schema_rule(
        artifact,
        version,
        compatibility=compatibility,
        readable_versions=readable_versions,
        writable_versions=writable_versions,
        additive_optional_fields=additive_optional_fields,
        removed_fields=removed_fields,
        renamed_fields=renamed_fields,
        canonical_defaults=canonical_defaults,
        notes=notes,
    )
    with _REGISTRY_LOCK:
        versions = _SCHEMA_REGISTRY.setdefault(rule.artifact, {})
        existing = versions.get(rule.version)
        if existing is not None:
            if replace(existing, representations=()) != rule:
                raise MigrationCompatibilityError(
                    f"Conflicting schema registration for {rule.artifact}@{rule.version}"
                )
            return existing
        versions[rule.version] = rule
        return rule


def register_ir_representation(
    *,
    registry_key: str,
    owner_ref: str,
    dto_abi: str,
    wire_policy_ref: str,
    wire_policy_revision: str,
    schema_name: str,
    schema_version: str,
    payload_version: str | None,
    profile_ref: str | None = None,
    readable: bool = True,
    writable: bool = False,
    current: bool = False,
    default_write: bool = False,
    readable_from: tuple[IRRepresentationKey, ...] = (),
) -> IRRepresentationRegistration:
    """Register one exact owner-bound manifest/payload tuple on an existing rule.

    None payload_version explicitly means that the payload has no embedded
    version discriminator; it is never a wildcard or a copy of manifest version.
    """
    text_values = {
        "registry_key": _native_identity_text(registry_key, "registry_key"),
        "owner_ref": _native_identity_text(owner_ref, "owner_ref"),
        "dto_abi": _native_identity_text(dto_abi, "dto_abi"),
        "wire_policy_ref": _native_identity_text(wire_policy_ref, "wire_policy_ref"),
        "wire_policy_revision": _native_identity_text(wire_policy_revision, "wire_policy_revision"),
        "schema_name": _native_identity_text(schema_name, "schema_name"),
        "schema_version": _native_identity_text(schema_version, "schema_version"),
    }
    registry_key = text_values["registry_key"]
    owner_ref = text_values["owner_ref"]
    dto_abi = text_values["dto_abi"]
    wire_policy_ref = text_values["wire_policy_ref"]
    wire_policy_revision = text_values["wire_policy_revision"]
    schema_name = text_values["schema_name"]
    schema_version = text_values["schema_version"]
    payload_version = _native_identity_text(payload_version, "payload_version", optional=True)
    profile_ref = _native_identity_text(profile_ref, "profile_ref", optional=True)
    if any(type(value) is not bool for value in (readable, writable, current, default_write)):
        raise MigrationCompatibilityError("IR representation lifecycle flags must be booleans")
    if not (readable or writable):
        raise MigrationCompatibilityError("IR representation must be readable or writable")
    if current and not readable:
        raise MigrationCompatibilityError("Current IR representation must be readable")
    if default_write and not (current and writable):
        raise MigrationCompatibilityError("Default IR writer must be current and writable")
    if type(readable_from) is not tuple:
        raise MigrationCompatibilityError(
            "readable_from must contain exact IRRepresentationKey values"
        )
    readable_from = tuple(_normalized_representation_key(key) for key in readable_from)

    record = IRRepresentationRegistration(
        registry_key=registry_key,
        owner_ref=owner_ref,
        dto_abi=dto_abi,
        wire_policy_ref=wire_policy_ref,
        wire_policy_revision=wire_policy_revision,
        schema_name=schema_name,
        schema_version=schema_version,
        payload_version=payload_version,
        profile_ref=profile_ref,
        readable=readable,
        writable=writable,
        current=current,
        default_write=default_write,
        readable_from=readable_from,
    )
    with _REGISTRY_LOCK:
        versions = _SCHEMA_REGISTRY.get(registry_key)
        rule = None if versions is None else versions.get(schema_version)
        if rule is None:
            raise MigrationCompatibilityError(
                f"No schema compatibility rule exists for {registry_key}@{schema_version}"
            )
        existing = next(
            (
                item
                for item in rule.representations
                if item.owner_ref == owner_ref and item.key == record.key
            ),
            None,
        )
        if existing is not None:
            if existing != record:
                raise MigrationCompatibilityError(
                    "Conflicting IR representation registration for "
                    f"{registry_key}:{owner_ref}:{record.key}"
                )
            return existing
        candidate = replace(rule, representations=(*rule.representations, record))
        copied_rules = {key: dict(value) for key, value in _SCHEMA_REGISTRY.items()}
        copied_rules[registry_key][schema_version] = candidate
        records = _all_representation_records(copied_rules)
        _validate_representation_records(copied_rules, records)
        versions[schema_version] = candidate
    return record


def get_schema_rule(artifact: str, version: str) -> SchemaCompatibilityRule | None:
    """Return the registered compatibility rule for ``artifact@version``."""

    with _REGISTRY_LOCK:
        return _SCHEMA_REGISTRY.get(str(artifact), {}).get(str(version))


def negotiate_schema_version(
    artifact: str,
    producer_version: str,
    consumer_version: str,
) -> SchemaCompatibilityDecision:
    """Return whether a consumer can read a producer payload version.

    The decision distinguishes direct compatibility from migration-required
    compatibility so release checks can fail closed instead of treating all
    schema-version mismatches as equivalent.
    """

    artifact = str(artifact)
    producer_version = str(producer_version)
    consumer_version = str(consumer_version)
    if producer_version == consumer_version:
        return SchemaCompatibilityDecision(
            artifact=artifact,
            producer_version=producer_version,
            consumer_version=consumer_version,
            can_read=True,
            mode=CompatibilityMode.FULL,
            reason="same_version",
        )

    consumer_rule = get_schema_rule(artifact, consumer_version)
    if consumer_rule is None:
        return SchemaCompatibilityDecision(
            artifact=artifact,
            producer_version=producer_version,
            consumer_version=consumer_version,
            can_read=False,
            mode=CompatibilityMode.NONE,
            reason="unknown_consumer_version",
        )

    direct = _direct_compatibility_decision(
        consumer_rule,
        producer_version=producer_version,
    )
    if direct is not None:
        return direct

    if _has_migration_path(artifact, producer_version, consumer_version):
        return SchemaCompatibilityDecision(
            artifact=artifact,
            producer_version=producer_version,
            consumer_version=consumer_version,
            can_read=True,
            mode=consumer_rule.mode,
            migration_required=True,
            reason="migration_available",
        )

    return SchemaCompatibilityDecision(
        artifact=artifact,
        producer_version=producer_version,
        consumer_version=consumer_version,
        can_read=False,
        mode=CompatibilityMode.NONE,
        reason="not_compatible",
    )


def can_read_schema(artifact: str, producer_version: str, consumer_version: str) -> bool:
    """Return whether ``consumer_version`` can read ``producer_version``."""

    return negotiate_schema_version(artifact, producer_version, consumer_version).can_read


def _stable_migration_value(value: object) -> object:
    """Encode immutable migration inputs and captured values deterministically."""
    if value is None or type(value) in {bool, int, str}:
        return {"type": type(value).__name__, "value": value}
    if type(value) is float:
        return {"type": "float", "value": value.hex()}
    if type(value) is bytes:
        return {"type": "bytes", "value": value.hex()}
    if isinstance(value, Enum):
        return {
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _stable_migration_value(value.value),
        }
    if isinstance(value, Mapping):
        pairs = [
            (_stable_migration_value(key), _stable_migration_value(item))
            for key, item in value.items()
        ]
        return {
            "type": "mapping",
            "items": sorted(
                pairs,
                key=lambda item: json.dumps(item[0], sort_keys=True, separators=(",", ":")),
            ),
        }
    if isinstance(value, (tuple, list)):
        return {
            "type": type(value).__name__,
            "items": [_stable_migration_value(item) for item in value],
        }
    if isinstance(value, (set, frozenset)):
        encoded = [_stable_migration_value(item) for item in value]
        return {
            "type": type(value).__name__,
            "items": sorted(
                encoded,
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            ),
        }
    if isinstance(value, type):
        return {"type": "class", "identity": f"{value.__module__}.{value.__qualname__}"}
    if callable(value):
        return {
            "type": "callable",
            "identity": f"{getattr(value, '__module__', type(value).__module__)}."
            f"{getattr(value, '__qualname__', type(value).__qualname__)}",
            "fingerprint": _migration_function_fingerprint(value),
        }
    raise MigrationCompatibilityError(
        "Migration defaults and closure values must have deterministic supported identities"
    )


def _migration_function_fingerprint(fn: MigrationFn) -> str:
    """Fingerprint code and its bound inputs for migration identity and snapshots."""
    code = getattr(fn, "__code__", None)
    if code is None:
        callable_identity = (
            f"{getattr(fn, '__module__', type(fn).__module__)}."
            f"{getattr(fn, '__qualname__', type(fn).__qualname__)}"
        )
        code_hash = None
    else:
        callable_identity = f"{fn.__module__}.{getattr(code, 'co_qualname', fn.__qualname__)}"
        code_hash = sha256(marshal.dumps(code)).hexdigest()
    defaults = _stable_migration_value(getattr(fn, "__defaults__", None))
    kwdefaults = _stable_migration_value(getattr(fn, "__kwdefaults__", None))
    closure = getattr(fn, "__closure__", None)
    closure_values = []
    if closure is not None:
        for cell in closure:
            try:
                closure_values.append(_stable_migration_value(cell.cell_contents))
            except ValueError:
                closure_values.append({"type": "empty_cell"})
    identity = {
        "callable": callable_identity,
        "code_sha256": code_hash,
        "defaults": defaults,
        "kwdefaults": kwdefaults,
        "closure": closure_values,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def register_migration(
    artifact: str,
    from_version: str,
    to_version: str,
    *,
    compatibility: CompatibilityMode | str = CompatibilityMode.BACKWARD,
) -> Callable[[MigrationFn], MigrationFn]:
    """Register one deterministic migration edge without replacing another meaning."""

    def decorator(fn: MigrationFn) -> MigrationFn:
        mode = _coerce_compatibility_mode(compatibility)
        fingerprint = _migration_function_fingerprint(fn)
        edge = MigrationEdge(
            to_version=to_version,
            fn=fn,
            compatibility=mode,
            fingerprint=fingerprint,
        )
        with _REGISTRY_LOCK:
            edges = _MIGRATIONS.setdefault(artifact, {})
            existing = edges.get(from_version)
            if existing is not None:
                if (
                    existing.to_version != edge.to_version
                    or existing.compatibility is not edge.compatibility
                    or existing.fingerprint != edge.fingerprint
                ):
                    raise MigrationCompatibilityError(
                        f"Conflicting migration edge for {artifact} {from_version}"
                    )
                return fn
            if from_version == to_version or _has_migration_path(
                artifact, to_version, from_version
            ):
                raise MigrationCompatibilityError(
                    f"Migration edge for {artifact} {from_version}->{to_version} creates a cycle"
                )

            source_rule = _schema_rule(
                artifact,
                from_version,
                compatibility=CompatibilityMode.FORWARD,
                writable_versions=(to_version,),
            )
            target_rule = _schema_rule(
                artifact,
                to_version,
                compatibility=mode,
                readable_versions=(from_version,) if mode in _BACKWARD_READ_MODES else (),
            )
            for rule in (source_rule, target_rule):
                prior = _SCHEMA_REGISTRY.get(artifact, {}).get(rule.version)
                if prior is not None and replace(prior, representations=()) != rule:
                    # Existing schema policy remains authoritative; the explicit
                    # migration edge is a separate registered route.
                    continue
            for rule in (source_rule, target_rule):
                prior = _SCHEMA_REGISTRY.get(artifact, {}).get(rule.version)
                if prior is None:
                    _SCHEMA_REGISTRY.setdefault(artifact, {})[rule.version] = rule
            edges[from_version] = edge
        return fn

    return decorator


def _record_identity(
    registration: IRRepresentationRegistration,
) -> tuple[str, str, IRRepresentationKey]:
    return registration.registry_key, registration.owner_ref, registration.key


def _all_representation_records(
    rules: Mapping[str, Mapping[str, SchemaCompatibilityRule]],
) -> tuple[IRRepresentationRegistration, ...]:
    return tuple(
        sorted(
            (
                registration
                for versions in rules.values()
                for rule in versions.values()
                for registration in rule.representations
            ),
            key=lambda item: (
                item.registry_key,
                item.owner_ref,
                item.schema_name,
                item.schema_version,
                item.payload_version or "",
                item.dto_abi,
            ),
        )
    )


def _validate_representation_records(
    rules: Mapping[str, Mapping[str, SchemaCompatibilityRule]],
    records: tuple[IRRepresentationRegistration, ...],
) -> None:
    exact: dict[tuple[str, str, IRRepresentationKey], IRRepresentationRegistration] = {}
    schema_owners: dict[tuple[str, str, str], tuple[str, str]] = {}
    current: dict[tuple[str, str, str], IRRepresentationRegistration] = {}
    defaults: dict[tuple[str, str], IRRepresentationRegistration] = {}
    for record in records:
        if rules.get(record.registry_key, {}).get(record.schema_version) is None:
            raise MigrationCompatibilityError(
                "Representation has no compatibility rule: "
                f"{record.registry_key}@{record.schema_version}"
            )
        identity = _record_identity(record)
        if identity in exact:
            raise MigrationCompatibilityError(
                "Ambiguous exact IR representation: "
                f"{record.registry_key}:{record.owner_ref}:{record.key}"
            )
        exact[identity] = record
        schema_identity = (
            record.registry_key,
            record.schema_name,
            record.schema_version,
        )
        owner_abi = (record.owner_ref, record.dto_abi)
        prior_owner = schema_owners.get(schema_identity)
        if prior_owner is not None and prior_owner != owner_abi:
            raise MigrationCompatibilityError(
                f"Conflicting owner/DTO mapping for schema identity {schema_identity}"
            )
        schema_owners[schema_identity] = owner_abi
        lifecycle_identity = (record.registry_key, record.owner_ref, record.schema_name)
        if record.current:
            if lifecycle_identity in current:
                raise MigrationCompatibilityError(
                    f"Ambiguous current IR representation for {lifecycle_identity}"
                )
            current[lifecycle_identity] = record
        if record.default_write:
            default_identity = (record.registry_key, record.owner_ref)
            if default_identity in defaults:
                raise MigrationCompatibilityError(
                    f"Ambiguous default IR writer for {record.registry_key}:{record.owner_ref}"
                )
            defaults[default_identity] = record
        if record.current and not record.readable:
            raise MigrationCompatibilityError("Current IR representation must be readable")
        if record.default_write and not (record.current and record.writable):
            raise MigrationCompatibilityError("Default IR writer must be current and writable")
        if record.readable_from and not record.current:
            raise MigrationCompatibilityError(
                "Only a current IR representation may declare direct read sources"
            )

    for record in records:
        seen: set[IRRepresentationKey] = set()
        for source_key in record.readable_from:
            if source_key in seen:
                raise MigrationCompatibilityError(
                    "Duplicate direct-read relation for "
                    f"{record.registry_key}:{record.owner_ref}:{record.key}"
                )
            seen.add(source_key)
            source = exact.get((record.registry_key, record.owner_ref, source_key))
            if source is None or not source.readable:
                raise MigrationCompatibilityError(
                    f"Direct-read relation does not name a readable exact row: {source_key}"
                )
            if source_key == record.key:
                raise MigrationCompatibilityError(
                    "An IR representation cannot directly read itself"
                )


def _registry_revision(
    rules: Mapping[tuple[str, str], SchemaCompatibilityRule],
    edges: Mapping[tuple[str, str], MigrationEdge],
) -> str:
    def record_value(record: IRRepresentationRegistration) -> dict[str, object]:
        return {
            "registry_key": record.registry_key,
            "owner_ref": record.owner_ref,
            "dto_abi": record.dto_abi,
            "wire_policy_ref": record.wire_policy_ref,
            "wire_policy_revision": record.wire_policy_revision,
            "schema_name": record.schema_name,
            "schema_version": record.schema_version,
            "payload_version": record.payload_version,
            "profile_ref": record.profile_ref,
            "readable": record.readable,
            "writable": record.writable,
            "current": record.current,
            "default_write": record.default_write,
            "readable_from": [
                [key.schema_name, key.schema_version, key.payload_version]
                for key in record.readable_from
            ],
        }

    rule_values: list[dict[str, object]] = []
    for key, rule in sorted(rules.items()):
        rule_values.append(
            {
                "key": list(key),
                "mode": rule.mode.value,
                "readable_versions": sorted(rule.readable_versions),
                "writable_versions": sorted(rule.writable_versions),
                "additive_optional_fields": sorted(rule.additive_optional_fields),
                "removed_fields": sorted(rule.removed_fields),
                "renamed_fields": sorted([list(item) for item in rule.renamed_fields]),
                "canonical_defaults": sorted([list(item) for item in rule.canonical_defaults]),
                "notes": list(rule.notes),
                "representations": [record_value(item) for item in rule.representations],
            }
        )
    edge_values: list[dict[str, object]] = []
    for (artifact, from_version), edge in sorted(edges.items()):
        edge_values.append(
            {
                "artifact": artifact,
                "from_version": from_version,
                "to_version": edge.to_version,
                "compatibility": edge.compatibility.value,
                "function_module": getattr(edge.fn, "__module__", ""),
                "function_qualname": getattr(edge.fn, "__qualname__", ""),
                "function_fingerprint": edge.fingerprint,
            }
        )
    encoded = json.dumps(
        {"rules": rule_values, "edges": edge_values},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + sha256(encoded).hexdigest()


def _validate_migration_edges(
    rules: Mapping[str, Mapping[str, SchemaCompatibilityRule]],
    edges: Mapping[str, Mapping[str, MigrationEdge]],
) -> None:
    for artifact, by_source in edges.items():
        for source in by_source:
            seen: set[str] = set()
            current = source
            while current in by_source:
                if current in seen:
                    raise MigrationCompatibilityError(
                        f"Migration cycle registered for {artifact} at {current}"
                    )
                seen.add(current)
                edge = by_source[current]
                if (
                    rules.get(artifact, {}).get(current) is None
                    or rules.get(artifact, {}).get(edge.to_version) is None
                ):
                    raise MigrationCompatibilityError(
                        "Migration edge has an unregistered endpoint: "
                        f"{artifact} {current}->{edge.to_version}"
                    )
                current = edge.to_version


def get_ir_owner_registry_snapshot() -> IRRegistrySnapshot:
    """Freeze the current owner/compatibility registrations for one operation."""
    with _REGISTRY_LOCK:
        copied_rules = {artifact: dict(versions) for artifact, versions in _SCHEMA_REGISTRY.items()}
        copied_edges = {artifact: dict(versions) for artifact, versions in _MIGRATIONS.items()}
    records = _all_representation_records(copied_rules)
    _validate_representation_records(copied_rules, records)
    _validate_migration_edges(copied_rules, copied_edges)
    flat_rules = {
        (artifact, version): rule
        for artifact, versions in copied_rules.items()
        for version, rule in versions.items()
    }
    flat_edges = {
        (artifact, source): edge
        for artifact, versions in copied_edges.items()
        for source, edge in versions.items()
    }
    frozen_rules = MappingProxyType(flat_rules)
    frozen_edges = MappingProxyType(flat_edges)
    return IRRegistrySnapshot(
        revision=_registry_revision(frozen_rules, frozen_edges),
        schema_rules=frozen_rules,
        migration_edges=frozen_edges,
        representation_records=records,
    )


def find_owned_representation(
    snapshot: IRRegistrySnapshot,
    registry_key: str,
    *,
    owner_ref: str,
    schema_name: str,
    schema_version: str,
) -> IRRepresentationPreflight | None:
    """Resolve exact manifest metadata without granting payload admission."""
    candidates = tuple(
        record
        for record in snapshot.representation_records
        if record.registry_key == registry_key
        and record.owner_ref == owner_ref
        and record.schema_name == schema_name
        and record.schema_version == schema_version
        and record.readable
    )
    if not candidates:
        return None
    return IRRepresentationPreflight(
        registry_key=registry_key,
        owner_ref=owner_ref,
        schema_name=schema_name,
        schema_version=schema_version,
        candidates=candidates,
        snapshot_revision=snapshot.revision,
    )


def find_writable_representation(
    snapshot: IRRegistrySnapshot,
    registry_key: str,
    *,
    owner_ref: str,
    schema_name: str,
    schema_version: str,
    payload_version: str | None,
) -> IRRepresentationRegistration | None:
    """Resolve one exact explicitly writable tuple before persistence."""
    matches = tuple(
        record
        for record in snapshot.representation_records
        if record.registry_key == registry_key
        and record.owner_ref == owner_ref
        and record.schema_name == schema_name
        and record.schema_version == schema_version
        and record.payload_version == payload_version
        and record.writable
    )
    if len(matches) > 1:
        raise MigrationCompatibilityError(
            "Ambiguous writable IR representation for "
            f"{registry_key}:{owner_ref}:{schema_name}@{schema_version}"
        )
    return matches[0] if matches else None


def get_current_ir_representation(
    snapshot: IRRegistrySnapshot,
    registry_key: str,
    *,
    owner_ref: str,
    schema_name: str,
) -> IRRepresentationRegistration | None:
    """Select the one current read representation for an exact manifest name."""
    matches = tuple(
        record
        for record in snapshot.representation_records
        if record.registry_key == registry_key
        and record.owner_ref == owner_ref
        and record.schema_name == schema_name
        and record.current
    )
    if len(matches) > 1:
        raise MigrationCompatibilityError(
            f"Ambiguous current IR representation for {registry_key}:{owner_ref}:{schema_name}"
        )
    return matches[0] if matches else None


def get_default_write_representation(
    snapshot: IRRegistrySnapshot,
    registry_key: str,
    *,
    owner_ref: str,
) -> IRRepresentationRegistration | None:
    """Select one registered default writer or refuse an ambiguous owner."""
    matches = tuple(
        record
        for record in snapshot.representation_records
        if record.registry_key == registry_key
        and record.owner_ref == owner_ref
        and record.current
        and record.writable
        and record.default_write
    )
    if len(matches) > 1:
        raise MigrationCompatibilityError(
            f"Ambiguous default IR writer for {registry_key}:{owner_ref}"
        )
    return matches[0] if matches else None


def _migration_route_version(record: IRRepresentationRegistration) -> str:
    """Return an explicit graph key without changing the exact stored tuple.

    Payload-less representations are routed by manifest schema version only
    for migration graph lookup. Their admitted payload_version remains None.
    """
    if record.payload_version is None:
        return record.schema_version
    return record.payload_version


def _strict_migration_path(
    snapshot: IRRegistrySnapshot,
    registry_key: str,
    source_version: str,
    target_version: str,
) -> tuple[str, ...] | None:
    if source_version == target_version:
        return None
    path = [source_version]
    seen = {source_version}
    current = source_version
    while current != target_version:
        edge = snapshot.migration_edges.get((registry_key, current))
        if edge is None:
            return None
        current = edge.to_version
        if current in seen or (registry_key, current) not in snapshot.schema_rules:
            return None
        seen.add(current)
        path.append(current)
    return tuple(path)


def resolve_owned_representation(
    snapshot: IRRegistrySnapshot,
    registry_key: str,
    *,
    owner_ref: str,
    schema_name: str,
    schema_version: str,
    payload_version: str | None,
) -> ResolvedSchemaAdmission | None:
    """Resolve one exact source tuple and its explicit current-reader route."""
    preflight = find_owned_representation(
        snapshot,
        registry_key,
        owner_ref=owner_ref,
        schema_name=schema_name,
        schema_version=schema_version,
    )
    if preflight is None:
        return None
    source_matches = tuple(
        record for record in preflight.candidates if record.payload_version == payload_version
    )
    if len(source_matches) != 1:
        return None
    source = source_matches[0]
    current = get_current_ir_representation(
        snapshot,
        registry_key,
        owner_ref=owner_ref,
        schema_name=schema_name,
    )
    if current is None or not current.readable:
        return None
    if source.key == current.key:
        return ResolvedSchemaAdmission(
            source_registration=source,
            current_registration=current,
            snapshot_revision=snapshot.revision,
            compatibility_kind=IRCompatibilityKind.EXACT,
            profile_ref=source.profile_ref,
        )
    if source.key in current.readable_from or (
        source.wire_policy_ref == current.wire_policy_ref
        and source.wire_policy_revision == current.wire_policy_revision
    ):
        return ResolvedSchemaAdmission(
            source_registration=source,
            current_registration=current,
            snapshot_revision=snapshot.revision,
            compatibility_kind=IRCompatibilityKind.DIRECT,
            profile_ref=source.profile_ref,
        )

    source_version = _migration_route_version(source)
    target_version = _migration_route_version(current)
    path = _strict_migration_path(snapshot, registry_key, source_version, target_version)
    if path is None:
        return None
    for intermediate_version in path[1:-1]:
        intermediate = tuple(
            record
            for record in snapshot.representation_records
            if record.registry_key == registry_key
            and record.owner_ref == owner_ref
            and record.dto_abi == source.dto_abi
            and record.schema_name == schema_name
            and _migration_route_version(record) == intermediate_version
            and record.readable
        )
        if len(intermediate) != 1:
            return None
    return ResolvedSchemaAdmission(
        source_registration=source,
        current_registration=current,
        snapshot_revision=snapshot.revision,
        compatibility_kind=IRCompatibilityKind.MIGRATION,
        migration_path=path,
        profile_ref=source.profile_ref,
    )


def _apply_migration(
    data: dict[str, Any],
    *,
    artifact: str,
    from_version: str,
    to_version: str,
    fn: MigrationFn,
) -> dict[str, Any]:
    migrated = fn(data)
    if not isinstance(migrated, dict):
        raise MigrationError(
            f"Migrator for '{artifact}' from {from_version} to {to_version} must return a dict"
        )

    declared_version = migrated.get("schema_version")
    if declared_version is not None and str(declared_version) != to_version:
        raise MigrationSchemaVersionError(
            f"Migrator for '{artifact}' from {from_version} to {to_version} "
            f"returned schema_version={declared_version!r}"
        )

    result = dict(migrated)
    result["schema_version"] = to_version
    return result


def _prepare_ir_payload(
    data: dict[str, Any],
    artifact: str,
) -> tuple[dict[str, Any], str]:
    if "schema_version" not in data:
        raise ValueError(f"Missing schema_version for artifact '{artifact}'")
    return data, str(data["schema_version"])


def _lookup_ir_edge(artifact: str, from_version: str) -> MigrationEdge | None:
    with _REGISTRY_LOCK:
        return _MIGRATIONS.get(artifact, {}).get(from_version)


def _ir_edge_target(edge: MigrationEdge) -> str:
    return edge.to_version


def _apply_ir_step(
    data: dict[str, Any],
    edge: MigrationEdge,
    artifact: str,
    from_version: str,
    to_version: str,
) -> dict[str, Any]:
    return _apply_migration(
        data,
        artifact=artifact,
        from_version=from_version,
        to_version=to_version,
        fn=edge.fn,
    )


_IR_PROFILE = common_migrations.LinearMigrationProfile(
    prepare=_prepare_ir_payload,
    no_op=lambda payload: payload,
    edge_target=_ir_edge_target,
    apply_step=_apply_ir_step,
)


def migrate_artifact(data: dict[str, Any], artifact: str, target_version: str) -> dict[str, Any]:
    """Migrate artifact helper.

    Migration functions may omit ``schema_version`` and let the framework stamp
    the registered ``to_version``. If they return their own ``schema_version``,
    it must match the registered edge; incompatible versions are errors rather
    than being silently overwritten.
    """
    return common_migrations.run_linear_migration(
        data,
        artifact=artifact,
        target_version=target_version,
        edge_lookup=_lookup_ir_edge,
        profile=_IR_PROFILE,
    )


_BACKWARD_READ_MODES = {
    CompatibilityMode.FULL,
    CompatibilityMode.BACKWARD,
}


def _coerce_compatibility_mode(mode: CompatibilityMode | str) -> CompatibilityMode:
    if isinstance(mode, CompatibilityMode):
        return mode
    try:
        return CompatibilityMode(str(mode).lower())
    except ValueError as exc:
        raise MigrationCompatibilityError(f"Unknown compatibility mode: {mode!r}") from exc


def _direct_compatibility_decision(
    consumer_rule: SchemaCompatibilityRule,
    *,
    producer_version: str,
) -> SchemaCompatibilityDecision | None:
    if producer_version in consumer_rule.readable_versions:
        return SchemaCompatibilityDecision(
            artifact=consumer_rule.artifact,
            producer_version=producer_version,
            consumer_version=consumer_rule.version,
            can_read=True,
            mode=consumer_rule.mode,
            reason="declared_readable_version",
        )

    producer_tuple = _parse_version_tuple(producer_version)
    consumer_tuple = _parse_version_tuple(consumer_rule.version)
    if producer_tuple is None or consumer_tuple is None or producer_tuple[0] != consumer_tuple[0]:
        return None

    if consumer_rule.mode is CompatibilityMode.FULL:
        return SchemaCompatibilityDecision(
            artifact=consumer_rule.artifact,
            producer_version=producer_version,
            consumer_version=consumer_rule.version,
            can_read=True,
            mode=CompatibilityMode.FULL,
            reason="same_major_full",
        )
    if consumer_rule.mode is CompatibilityMode.BACKWARD and producer_tuple <= consumer_tuple:
        return SchemaCompatibilityDecision(
            artifact=consumer_rule.artifact,
            producer_version=producer_version,
            consumer_version=consumer_rule.version,
            can_read=True,
            mode=CompatibilityMode.BACKWARD,
            reason="same_major_backward",
        )
    if consumer_rule.mode is CompatibilityMode.FORWARD and producer_tuple >= consumer_tuple:
        return SchemaCompatibilityDecision(
            artifact=consumer_rule.artifact,
            producer_version=producer_version,
            consumer_version=consumer_rule.version,
            can_read=True,
            mode=CompatibilityMode.FORWARD,
            reason="same_major_forward",
        )
    return None


def _has_migration_path(artifact: str, from_version: str, to_version: str) -> bool:
    with _REGISTRY_LOCK:
        visited: set[str] = set()
        current = from_version
        while current != to_version:
            if current in visited:
                return False
            visited.add(current)
            edge = _MIGRATIONS.get(artifact, {}).get(current)
            if edge is None:
                return False
            current = edge.to_version
        return True


def _parse_version_tuple(version: str) -> tuple[int, int] | None:
    parts = str(version).split(".")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


__all__ = [
    "CompatibilityMode",
    "IRCompatibilityKind",
    "IRRegistrySnapshot",
    "IRRepresentationKey",
    "IRRepresentationPreflight",
    "IRRepresentationRegistration",
    "MigrationCompatibilityError",
    "MigrationEdge",
    "MigrationError",
    "MigrationFn",
    "MigrationSchemaVersionError",
    "ResolvedSchemaAdmission",
    "SchemaCompatibilityDecision",
    "SchemaCompatibilityRule",
    "can_read_schema",
    "find_owned_representation",
    "find_writable_representation",
    "get_current_ir_representation",
    "get_default_write_representation",
    "get_ir_owner_registry_snapshot",
    "get_schema_rule",
    "migrate_artifact",
    "negotiate_schema_version",
    "register_ir_representation",
    "register_migration",
    "register_schema_version",
    "resolve_owned_representation",
]
