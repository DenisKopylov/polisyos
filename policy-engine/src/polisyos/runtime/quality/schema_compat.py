"""Schema compatibility decisions for runtime-quality evidence readers."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COMPATIBILITY_DECISIONS = (
    "compatible",
    "compatible_with_migration",
    "legacy_quarantined",
    "unknown_schema_blocked",
    "incompatible_blocked",
    "stale_schema_blocked",
)

COMPATIBLE_DECISIONS = frozenset({"compatible", "compatible_with_migration"})
PRODUCTION_CLOSEOUT_BLOCKING_DECISIONS = frozenset(
    {
        "legacy_quarantined",
        "unknown_schema_blocked",
        "incompatible_blocked",
        "stale_schema_blocked",
    }
)
REQUIRED_READERS = frozenset(
    {
        "scorecard",
        "readiness",
        "bundle_assembler",
        "dashboard_projection",
        "approval_packet_builder",
    }
)
DEFAULT_SCHEMA_COMPATIBILITY_REGISTRY_PATH = (
    Path(__file__).resolve().parents[4]
    / "architecture/production_quality/schema_compatibility.toml"
)

SCORECARD_REPORT_SCHEMA_FAMILIES = {
    "production_data_quality": "policyos.runtime.production_data_quality",
    "normative_evidence": "policyos.lex.normative_applicability_report",
    "fabric_retrieval_trace": "policyos.fabric.source_selection_trace",
    "foundry_method_report": "policyos.foundry.method_quality_report",
    "policy_grounding_matrix": "policyos.scientist.policy_grounding_matrix",
    "conflict_check": "policyos.lex.policy_conflict_check",
    "causal_statistical_validity": "policyos.foundry.causal_statistical_validity",
    "replay_manifest": "policyos.replay_manifest",
    "drift_explanation": "policyos.drift_explanation",
    "resilience_matrix": "policyos.runtime.resilience_matrix",
    "human_review_calibration": "policyos.human_review_calibration_report",
    "decision_artifact_quality": "policyos.scientist.decision_artifact_quality",
    "privacy_compliance_report": "policyos.privacy_compliance_report",
    "continuous_governance_stale": "policyos.runtime.governance_lifecycle_report",
    "continuous_governance_reissue": "policyos.runtime.governance_lifecycle_report",
    "continuous_governance_supersede": "policyos.runtime.governance_lifecycle_report",
    "continuous_governance_withdraw": "policyos.runtime.governance_lifecycle_report",
}
SCORECARD_REPORT_SCHEMA_FAMILY_ALIASES = {
    **{
        report_key: (schema_family,)
        for report_key, schema_family in SCORECARD_REPORT_SCHEMA_FAMILIES.items()
    },
    "resilience_matrix": (
        "policyos.runtime.resilience_matrix",
        "policyos.runtime_resilience_matrix",
    ),
}

_SCHEMA_VERSION_PATTERN = re.compile(
    r"^(?P<family>.+)\.v(?P<version>\d+(?:\.\d+){0,2})$"
)


@dataclass(frozen=True)
class SchemaIdentity:
    """Parsed producer schema identity."""

    raw: str | None
    family: str | None
    version: tuple[int, int, int] | None

    @property
    def version_text(self) -> str | None:
        if self.version is None:
            return None
        major, minor, patch = self.version
        if patch:
            return f"{major}.{minor}.{patch}"
        if minor:
            return f"{major}.{minor}"
        return str(major)


@dataclass(frozen=True)
class ReaderSchemaRange:
    """One schema range accepted by a runtime-quality reader."""

    reader: str
    schema_family: str
    min_version: str
    max_version: str
    current_version: str
    migration_versions: tuple[str, ...] = ()
    legacy_versions: tuple[str, ...] = ("0",)

    def min_tuple(self) -> tuple[int, int, int]:
        return parse_version_text(self.min_version)

    def max_tuple(self) -> tuple[int, int, int]:
        return parse_version_text(self.max_version)

    def current_tuple(self) -> tuple[int, int, int]:
        return parse_version_text(self.current_version)

    def migration_tuples(self) -> frozenset[tuple[int, int, int]]:
        return frozenset(parse_version_text(version) for version in self.migration_versions)

    def legacy_tuples(self) -> frozenset[tuple[int, int, int]]:
        return frozenset(parse_version_text(version) for version in self.legacy_versions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reader": self.reader,
            "schema_family": self.schema_family,
            "min_version": self.min_version,
            "max_version": self.max_version,
            "current_version": self.current_version,
            "migration_versions": list(self.migration_versions),
            "legacy_versions": list(self.legacy_versions),
        }


@dataclass(frozen=True)
class SchemaCompatibilityResult:
    """Compatibility decision plus the gate semantics a consumer should enforce."""

    decision: str
    reader: str
    schema_raw: str | None
    schema_family: str | None
    schema_version: str | None
    reason: str
    diagnostic_readable: bool
    production_closeout_allowed: bool
    migration_required: bool = False
    migration_verified: bool = False
    missing_semantic_fields: tuple[str, ...] = ()
    expected_schema_families: tuple[str, ...] = ()

    def to_gate_details(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reader": self.reader,
            "schema_version": self.schema_raw,
            "schema_family": self.schema_family,
            "schema_version_number": self.schema_version,
            "reason": self.reason,
            "diagnostic_readable": self.diagnostic_readable,
            "production_closeout_allowed": self.production_closeout_allowed,
            "migration_required": self.migration_required,
            "migration_verified": self.migration_verified,
            "missing_semantic_fields": list(self.missing_semantic_fields),
            "expected_schema_families": list(self.expected_schema_families),
        }


class SchemaCompatibilityRegistryError(ValueError):
    """Raised when the runtime schema compatibility registry is incomplete."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


def _quality_report_schema_families() -> tuple[str, ...]:
    families: list[str] = []
    for aliases in SCORECARD_REPORT_SCHEMA_FAMILY_ALIASES.values():
        for schema_family in aliases:
            if schema_family not in families:
                families.append(schema_family)
    return tuple(families)


def _quality_report_ranges(reader: str) -> tuple[ReaderSchemaRange, ...]:
    return tuple(
        ReaderSchemaRange(
            reader=reader,
            schema_family=schema_family,
            min_version="1",
            max_version="1",
            current_version="1",
        )
        for schema_family in _quality_report_schema_families()
    )


_SCORECARD_QUALITY_REPORT_RANGES = _quality_report_ranges("scorecard")
_BUNDLE_ASSEMBLER_QUALITY_REPORT_RANGES = _quality_report_ranges("bundle_assembler")

READER_SCHEMA_DECLARATIONS: dict[str, tuple[ReaderSchemaRange, ...]] = {
    "scorecard": _SCORECARD_QUALITY_REPORT_RANGES,
    "readiness": (
        ReaderSchemaRange(
            reader="readiness",
            schema_family="policyos.quality_scorecard",
            min_version="1",
            max_version="1",
            current_version="1",
        ),
        ReaderSchemaRange(
            reader="readiness",
            schema_family="policyos.canary_evidence",
            min_version="1",
            max_version="1",
            current_version="1",
        ),
    ),
    "bundle_assembler": (
        *_BUNDLE_ASSEMBLER_QUALITY_REPORT_RANGES,
        ReaderSchemaRange(
            reader="bundle_assembler",
            schema_family="policyos.quality_scorecard",
            min_version="1",
            max_version="1",
            current_version="1",
        ),
        ReaderSchemaRange(
            reader="bundle_assembler",
            schema_family="policyos.canary_evidence",
            min_version="1",
            max_version="1",
            current_version="1",
        ),
    ),
    "dashboard_projection": (
        ReaderSchemaRange(
            reader="dashboard_projection",
            schema_family="policyos.quality_scorecard",
            min_version="1",
            max_version="1",
            current_version="1",
        ),
        ReaderSchemaRange(
            reader="dashboard_projection",
            schema_family="policyos.canary_evidence",
            min_version="1",
            max_version="1",
            current_version="1",
        ),
        ReaderSchemaRange(
            reader="dashboard_projection",
            schema_family="policyos.production_approval_packet",
            min_version="1",
            max_version="1",
            current_version="1",
        ),
    ),
    "approval_packet_builder": (
        ReaderSchemaRange(
            reader="approval_packet_builder",
            schema_family="policyos.quality_scorecard",
            min_version="1",
            max_version="1",
            current_version="1",
        ),
    ),
}


def reader_schema_ranges() -> dict[str, tuple[ReaderSchemaRange, ...]]:
    """Return runtime-quality reader declarations from the TOML registry."""

    try:
        return load_schema_compatibility_registry().reader_ranges
    except FileNotFoundError:
        return {reader: tuple(ranges) for reader, ranges in READER_SCHEMA_DECLARATIONS.items()}


@dataclass(frozen=True)
class SchemaCompatibilityRegistry:
    """Loaded producer-reader schema compatibility declarations."""

    reader_ranges: dict[str, tuple[ReaderSchemaRange, ...]]
    schema_contracts: tuple[str, ...]
    path: Path


def load_schema_compatibility_registry(
    path: str | Path = DEFAULT_SCHEMA_COMPATIBILITY_REGISTRY_PATH,
) -> SchemaCompatibilityRegistry:
    registry_path = Path(path)
    with registry_path.open("rb") as handle:
        payload = tomllib.load(handle)
    decisions = payload.get("decisions")
    if set(decisions or ()) != set(COMPATIBILITY_DECISIONS):
        raise SchemaCompatibilityRegistryError(
            "schema_compatibility_decisions_invalid",
            "Schema compatibility registry must declare the full decision taxonomy.",
            details={"path": str(registry_path)},
        )
    rows = payload.get("readers")
    if not isinstance(rows, list) or not rows:
        raise SchemaCompatibilityRegistryError(
            "schema_compatibility_readers_missing",
            "Schema compatibility registry must declare reader ranges.",
            details={"path": str(registry_path)},
        )
    reader_ranges: dict[str, tuple[ReaderSchemaRange, ...]] = {}
    seen_readers: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise SchemaCompatibilityRegistryError(
                "schema_compatibility_reader_invalid",
                "Every schema compatibility reader row must be a table.",
            )
        reader = str(row.get("name") or "").strip()
        families = row.get("accepted_schema_families")
        if (
            not reader
            or not isinstance(families, list)
            or not families
            or not str(row.get("min_version") or "").strip()
            or not str(row.get("max_version") or "").strip()
            or not str(row.get("current_version") or "").strip()
            or not str(row.get("production_closeout_policy") or "").strip()
            or not str(row.get("diagnostic_policy") or "").strip()
        ):
            raise SchemaCompatibilityRegistryError(
                "schema_compatibility_reader_incomplete",
                "Schema compatibility reader row is incomplete.",
                details={"reader": reader},
            )
        if reader in seen_readers:
            raise SchemaCompatibilityRegistryError(
                "schema_compatibility_reader_duplicate",
                "Schema compatibility reader row is duplicated.",
                details={"reader": reader},
            )
        seen_readers.add(reader)
        reader_ranges[reader] = tuple(
            ReaderSchemaRange(
                reader=reader,
                schema_family=str(family).strip(),
                min_version=str(row["min_version"]),
                max_version=str(row["max_version"]),
                current_version=str(row["current_version"]),
                migration_versions=tuple(
                    str(value).strip()
                    for value in row.get("migration_versions", [])
                    if str(value).strip()
                ),
                legacy_versions=tuple(
                    str(value).strip()
                    for value in row.get("legacy_versions", [])
                    if str(value).strip()
                ),
            )
            for family in families
            if str(family).strip()
        )
    missing = sorted(REQUIRED_READERS - seen_readers)
    if missing:
        raise SchemaCompatibilityRegistryError(
            "schema_compatibility_required_reader_missing",
            "Schema compatibility registry is missing required readers.",
            details={"missing": missing},
        )
    schema_contracts = tuple(
        str(row.get("schema_contract")).strip()
        for row in payload.get("schema_compatibility", [])
        if isinstance(row, Mapping) and str(row.get("schema_contract") or "").strip()
    )
    return SchemaCompatibilityRegistry(
        reader_ranges=reader_ranges,
        schema_contracts=schema_contracts,
        path=registry_path,
    )


def evaluate_schema_compatibility(
    payload: Mapping[str, Any] | str | None,
    *,
    reader: str,
    expected_schema_family: str | tuple[str, ...] | None = None,
    declarations: Mapping[str, tuple[ReaderSchemaRange, ...]] | None = None,
    migration: Mapping[str, Any] | None = None,
    required_semantic_fields: Sequence[str] = (),
) -> SchemaCompatibilityResult:
    """Decide whether a producer payload is readable by a named consumer."""

    ranges_by_reader = declarations or reader_schema_ranges()
    ranges = tuple(ranges_by_reader.get(reader, ()))
    expected_families = tuple(declaration.schema_family for declaration in ranges)
    explicit_expected_families = _expected_schema_family_tuple(expected_schema_family)
    identity = extract_schema_identity(
        payload,
        expected_schema_family=(
            explicit_expected_families[0] if len(explicit_expected_families) == 1 else None
        ),
    )
    expected_family_set = set(expected_families)
    known_family_set = {
        declaration.schema_family
        for declarations_for_reader in ranges_by_reader.values()
        for declaration in declarations_for_reader
    }

    if identity.raw is None:
        return _result(
            "legacy_quarantined",
            reader=reader,
            identity=identity,
            reason="missing_schema_version",
            expected_schema_families=expected_families,
        )
    if identity.family is None or identity.version is None:
        return _result(
            "unknown_schema_blocked",
            reader=reader,
            identity=identity,
            reason="unparseable_schema_version",
            expected_schema_families=expected_families,
        )
    if explicit_expected_families and identity.family not in explicit_expected_families:
        decision = (
            "incompatible_blocked"
            if identity.family in known_family_set
            else "unknown_schema_blocked"
        )
        return _result(
            decision,
            reader=reader,
            identity=identity,
            reason="schema_family_mismatch",
            expected_schema_families=explicit_expected_families,
        )
    if identity.family not in expected_family_set:
        decision = (
            "incompatible_blocked"
            if identity.family in known_family_set
            else "unknown_schema_blocked"
        )
        return _result(
            decision,
            reader=reader,
            identity=identity,
            reason=(
                "reader_does_not_accept_schema_family"
                if decision == "incompatible_blocked"
                else "unknown_schema_family"
            ),
            expected_schema_families=expected_families,
        )

    declaration = next(item for item in ranges if item.schema_family == identity.family)
    if identity.version in declaration.legacy_tuples() or identity.version[0] == 0:
        return _result(
            "legacy_quarantined",
            reader=reader,
            identity=identity,
            reason="legacy_schema_version",
            expected_schema_families=expected_families,
        )
    if identity.version < declaration.min_tuple():
        return _result(
            "stale_schema_blocked",
            reader=reader,
            identity=identity,
            reason="schema_version_below_reader_minimum",
            expected_schema_families=expected_families,
        )
    if identity.version > declaration.max_tuple():
        return _result(
            "incompatible_blocked",
            reader=reader,
            identity=identity,
            reason="schema_version_above_reader_maximum",
            expected_schema_families=expected_families,
        )
    if (
        identity.version != declaration.current_tuple()
        and identity.version in declaration.migration_tuples()
    ):
        migration_record = _migration_record(payload, migration)
        if migration_record is None:
            return _result(
                "legacy_quarantined",
                reader=reader,
                identity=identity,
                reason="migration_required_without_verified_payload_identity",
                expected_schema_families=expected_families,
                migration_required=True,
            )
        verification = _verify_schema_migration(
            payload=payload,
            migration=migration_record,
            declaration=declaration,
            required_semantic_fields=required_semantic_fields,
        )
        if not verification["verified"]:
            return _result(
                "legacy_quarantined",
                reader=reader,
                identity=identity,
                reason=str(verification["reason"]),
                expected_schema_families=expected_families,
                migration_required=True,
                missing_semantic_fields=tuple(verification["missing_semantic_fields"]),
            )
        return _result(
            "compatible_with_migration",
            reader=reader,
            identity=identity,
            reason="verified_lossless_migration",
            expected_schema_families=expected_families,
            migration_required=True,
            migration_verified=True,
        )
    missing_semantic_fields = _missing_semantic_fields(
        payload,
        required_semantic_fields,
    )
    if missing_semantic_fields:
        return _result(
            "legacy_quarantined",
            reader=reader,
            identity=identity,
            reason="missing_required_semantic_fields",
            expected_schema_families=expected_families,
            missing_semantic_fields=missing_semantic_fields,
        )
    return _result(
        "compatible",
        reader=reader,
        identity=identity,
        reason="schema_version_in_reader_range",
        expected_schema_families=expected_families,
    )


def extract_schema_identity(
    payload: Mapping[str, Any] | str | None,
    *,
    expected_schema_family: str | None = None,
) -> SchemaIdentity:
    """Extract a dotted ``family.vN`` schema identity from common payload shapes."""

    raw: Any = payload
    if isinstance(payload, Mapping):
        raw = payload.get("schema_version")
        schema = payload.get("schema")
        if raw is None and isinstance(schema, Mapping):
            schema_name = schema.get("name")
            schema_version = schema.get("version")
            if schema_name is not None and schema_version is not None:
                raw = f"{schema_name}.v{schema_version}"
    if raw is None:
        return SchemaIdentity(raw=None, family=None, version=None)

    raw_text = str(raw).strip()
    if not raw_text:
        return SchemaIdentity(raw=raw_text, family=None, version=None)
    match = _SCHEMA_VERSION_PATTERN.match(raw_text)
    if match:
        return SchemaIdentity(
            raw=raw_text,
            family=match.group("family"),
            version=parse_version_text(match.group("version")),
        )
    if expected_schema_family is not None:
        version = _parse_version_only(raw_text)
        if version is not None:
            return SchemaIdentity(
                raw=raw_text,
                family=expected_schema_family,
                version=version,
            )
    return SchemaIdentity(raw=raw_text, family=None, version=None)


def parse_version_text(version: str) -> tuple[int, int, int]:
    """Parse ``1``, ``1.2``, ``v1`` or ``v1.2.3`` into a comparable tuple."""

    parsed = _parse_version_only(version)
    if parsed is None:
        raise ValueError(f"Invalid schema version: {version!r}")
    return parsed


def stable_payload_sha256(payload: object) -> str:
    """Return the stable SHA-256 identity for a JSON-like payload."""

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _expected_schema_family_tuple(
    expected_schema_family: str | tuple[str, ...] | None,
) -> tuple[str, ...]:
    if expected_schema_family is None:
        return ()
    if isinstance(expected_schema_family, str):
        return (expected_schema_family,)
    return tuple(
        schema_family for schema_family in expected_schema_family if schema_family
    )


def _parse_version_only(version: str) -> tuple[int, int, int] | None:
    cleaned = str(version).strip().removeprefix("v")
    parts = cleaned.split(".")
    if not 1 <= len(parts) <= 3 or any(not part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)  # type: ignore[return-value]


def _migration_record(
    payload: Mapping[str, Any] | str | None,
    explicit: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if explicit is not None:
        return explicit
    if not isinstance(payload, Mapping):
        return None
    for key in ("schema_migration", "migration", "migration_record"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _verify_schema_migration(
    *,
    payload: Mapping[str, Any] | str | None,
    migration: Mapping[str, Any],
    declaration: ReaderSchemaRange,
    required_semantic_fields: Sequence[str],
) -> dict[str, Any]:
    source_payload = _source_payload_without_migration_metadata(payload)
    target_payload = _migration_target_payload(migration)
    if source_payload is None:
        return _migration_failure("migration_source_payload_not_mapping")
    if target_payload is None:
        return _migration_failure("migration_target_payload_missing")

    source_digest = _digest_from_record(
        migration,
        "source_payload_sha256",
        "original_payload_sha256",
        "payload_sha256",
    )
    if source_digest is None:
        return _migration_failure("source_payload_identity_missing")
    if source_digest != stable_payload_sha256(source_payload):
        return _migration_failure("source_payload_identity_mismatch")

    target_digest = _digest_from_record(
        migration,
        "target_payload_sha256",
        "migrated_payload_sha256",
    )
    if target_digest is None:
        return _migration_failure("target_payload_identity_missing")
    if target_digest != stable_payload_sha256(target_payload):
        return _migration_failure("target_payload_identity_mismatch")

    target_identity = extract_schema_identity(target_payload)
    if (
        target_identity.family != declaration.schema_family
        or target_identity.version != declaration.current_tuple()
    ):
        return _migration_failure("migration_target_schema_mismatch")

    if _migration_declares_semantic_loss(migration):
        return _migration_failure("legacy_migration_semantic_loss")

    semantic_fields = tuple(required_semantic_fields) or _required_semantic_fields_from(
        migration
    )
    missing_fields = _missing_semantic_fields(target_payload, semantic_fields)
    if missing_fields:
        return _migration_failure(
            "missing_required_semantic_fields",
            missing_semantic_fields=missing_fields,
        )

    if _field_mapping_has_semantic_loss(source_payload, target_payload, migration):
        return _migration_failure("legacy_migration_semantic_loss")

    return {
        "verified": True,
        "reason": "verified_lossless_migration",
        "missing_semantic_fields": (),
    }


def _migration_failure(
    reason: str,
    *,
    missing_semantic_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "verified": False,
        "reason": reason,
        "missing_semantic_fields": missing_semantic_fields,
    }


def _source_payload_without_migration_metadata(
    payload: Mapping[str, Any] | str | None,
) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    return {
        str(key): value
        for key, value in payload.items()
        if str(key) not in {"schema_migration", "migration", "migration_record"}
    }


def _migration_target_payload(migration: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("target_payload", "migrated_payload", "payload"):
        value = migration.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _digest_from_record(record: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if not isinstance(value, str):
            continue
        digest = value.strip().lower()
        if digest.startswith("sha256:"):
            digest = digest.removeprefix("sha256:")
        elif digest.startswith("cas://sha256/"):
            digest = digest.removeprefix("cas://sha256/")
        if len(digest) == 64 and all(char in "0123456789abcdef" for char in digest):
            return digest
    return None


def _migration_declares_semantic_loss(migration: Mapping[str, Any]) -> bool:
    for key in ("semantic_loss", "lossy", "semantic_loss_detected"):
        if bool(migration.get(key)):
            return True
    for key in ("lost_fields", "dropped_fields", "removed_fields"):
        value = migration.get(key)
        if isinstance(value, Sequence) and not isinstance(value, str) and value:
            return True
    return False


def _field_mapping_has_semantic_loss(
    source_payload: Mapping[str, Any],
    target_payload: Mapping[str, Any],
    migration: Mapping[str, Any],
) -> bool:
    field_mappings = migration.get("field_mappings")
    if not isinstance(field_mappings, Mapping):
        return False
    for source_field, target_field in field_mappings.items():
        source_value, source_present = _field_value(source_payload, str(source_field))
        target_value, target_present = _field_value(target_payload, str(target_field))
        if source_present and (not target_present or source_value != target_value):
            return True
    return False


def _required_semantic_fields_from(migration: Mapping[str, Any]) -> tuple[str, ...]:
    value = migration.get("required_semantic_fields")
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(str(field) for field in value if str(field).strip())


def _missing_semantic_fields(
    payload: Mapping[str, Any] | str | None,
    required_semantic_fields: Sequence[str],
) -> tuple[str, ...]:
    if not required_semantic_fields:
        return ()
    if not isinstance(payload, Mapping):
        return tuple(str(field) for field in required_semantic_fields)
    missing: list[str] = []
    for field in required_semantic_fields:
        field_text = str(field).strip()
        if not field_text:
            continue
        value, present = _field_value(payload, field_text)
        if not present or value is None or value == "":
            missing.append(field_text)
    return tuple(missing)


def _field_value(payload: Mapping[str, Any], field_path: str) -> tuple[Any, bool]:
    current: Any = payload
    for part in field_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None, False
        current = current[part]
    return current, True


def _result(
    decision: str,
    *,
    reader: str,
    identity: SchemaIdentity,
    reason: str,
    expected_schema_families: tuple[str, ...],
    migration_required: bool = False,
    migration_verified: bool = False,
    missing_semantic_fields: tuple[str, ...] = (),
) -> SchemaCompatibilityResult:
    diagnostic_readable = decision in {
        "compatible",
        "compatible_with_migration",
        "legacy_quarantined",
    }
    production_closeout_allowed = decision in COMPATIBLE_DECISIONS
    return SchemaCompatibilityResult(
        decision=decision,
        reader=reader,
        schema_raw=identity.raw,
        schema_family=identity.family,
        schema_version=identity.version_text,
        reason=reason,
        diagnostic_readable=diagnostic_readable,
        production_closeout_allowed=production_closeout_allowed,
        migration_required=migration_required,
        migration_verified=migration_verified,
        missing_semantic_fields=missing_semantic_fields,
        expected_schema_families=expected_schema_families,
    )


__all__ = [
    "COMPATIBILITY_DECISIONS",
    "COMPATIBLE_DECISIONS",
    "PRODUCTION_CLOSEOUT_BLOCKING_DECISIONS",
    "READER_SCHEMA_DECLARATIONS",
    "SCORECARD_REPORT_SCHEMA_FAMILIES",
    "SCORECARD_REPORT_SCHEMA_FAMILY_ALIASES",
    "ReaderSchemaRange",
    "SchemaCompatibilityRegistry",
    "SchemaCompatibilityRegistryError",
    "SchemaCompatibilityResult",
    "SchemaIdentity",
    "evaluate_schema_compatibility",
    "extract_schema_identity",
    "load_schema_compatibility_registry",
    "parse_version_text",
    "reader_schema_ranges",
    "stable_payload_sha256",
]
