"""Source-of-truth lattice contracts for authority-bearing runtime fields."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_TRUTH_LATTICE_PATH = (
    Path(__file__).resolve().parents[4]
    / "architecture/production_quality/source_truth_lattice.toml"
)

MINIMUM_AUTHORITY_FIELD_FAMILIES = frozenset(
    {
        "runtime_refs",
        "final_claims",
        "source_data_context",
        "legal_context",
        "foundry_method_context",
        "scorecard_identity_and_gates",
        "approval_readiness_public_status",
        "mode_and_fallback_records",
    }
)
DEFAULT_LOSING_AUTHORITY_RECORD_FIELDS = (
    "record_schema",
    "field_family",
    "authoritative_producer",
    "authoritative_surface",
    "losing_surface",
    "lost_fields",
    "failure_code",
    "owner",
    "next_diagnostic_command",
)
SOURCE_TRUTH_CONFLICT_SCHEMA = "policyos.runtime.quality.source_truth_conflict.v1"


class SourceTruthContractError(ValueError):
    """Raised when the source-truth lattice is malformed or misused."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class SourceTruthFieldFamily:
    """One authority-bearing field-family declaration from the lattice."""

    id: str
    authoritative_producer: str
    allowed_projection_surfaces: tuple[str, ...]
    allowed_package_surfaces: tuple[str, ...]
    losing_authority_record_required_fields: tuple[str, ...]
    conflict_failure_code: str
    adapter_semantic_preservation_requirements: tuple[str, ...]
    required_semantic_fields: tuple[str, ...]
    owner: str
    next_diagnostic_command: str
    description: str | None = None

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        default_record_fields: Sequence[str],
        default_semantic_fields: Sequence[str],
        default_next_diagnostic_command: str,
    ) -> SourceTruthFieldFamily:
        family_id = _required_text(payload, "id")
        return cls(
            id=family_id,
            authoritative_producer=_required_text(payload, "authoritative_producer"),
            allowed_projection_surfaces=_required_text_tuple(
                payload,
                "allowed_projection_surfaces",
                family_id=family_id,
            ),
            allowed_package_surfaces=_required_text_tuple(
                payload,
                "allowed_package_surfaces",
                family_id=family_id,
            ),
            losing_authority_record_required_fields=_text_tuple(
                payload.get("losing_authority_record_required_fields"),
                default=default_record_fields,
                field=f"{family_id}.losing_authority_record_required_fields",
            ),
            conflict_failure_code=_required_text(payload, "conflict_failure_code"),
            adapter_semantic_preservation_requirements=_required_text_tuple(
                payload,
                "adapter_semantic_preservation_requirements",
                family_id=family_id,
            ),
            required_semantic_fields=_text_tuple(
                payload.get("required_semantic_fields"),
                default=default_semantic_fields,
                field=f"{family_id}.required_semantic_fields",
            ),
            owner=_required_text(payload, "owner"),
            next_diagnostic_command=_text_or_default(
                payload.get("next_diagnostic_command"),
                default=default_next_diagnostic_command,
            ),
            description=_optional_text(payload.get("description")),
        )


@dataclass(frozen=True)
class SourceTruthLattice:
    """Validated lattice loaded from ``source_truth_lattice.toml``."""

    schema_version: str
    owner: str
    field_families: dict[str, SourceTruthFieldFamily]
    adapter_semantic_fields: tuple[str, ...]
    losing_authority_record_schema: str
    losing_authority_record_required_fields: tuple[str, ...]
    next_diagnostic_command: str
    path: Path

    def losing_authority_record(
        self,
        *,
        field_family: str,
        authoritative_surface: str,
        losing_surface: str,
        lost_fields: Sequence[str],
        authoritative_ref: str | None = None,
        losing_ref: str | None = None,
        details: Mapping[str, Any] | None = None,
        recorded_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Return a typed record for a lower-authority surface losing semantics."""

        family = self._family(field_family)
        normalized_lost_fields = _clean_text_sequence(
            lost_fields,
            field=f"{field_family}.lost_fields",
        )
        if not normalized_lost_fields:
            raise SourceTruthContractError(
                "source_truth_lost_fields_missing",
                f"{field_family} losing-authority record has no lost fields",
            )
        record = {
            "record_schema": self.losing_authority_record_schema,
            "field_family": family.id,
            "authoritative_producer": family.authoritative_producer,
            "authoritative_surface": authoritative_surface,
            "losing_surface": losing_surface,
            "authoritative_ref": authoritative_ref,
            "losing_ref": losing_ref,
            "lost_fields": list(normalized_lost_fields),
            "failure_code": family.conflict_failure_code,
            "owner": family.owner,
            "next_diagnostic_command": family.next_diagnostic_command,
            "recorded_at": _utc(recorded_at).isoformat(),
            "details": dict(details or {}),
        }
        missing = [
            field
            for field in family.losing_authority_record_required_fields
            if not _present(record.get(field))
        ]
        if missing:
            raise SourceTruthContractError(
                "source_truth_losing_record_malformed",
                f"{field_family} losing-authority record is missing {missing}",
            )
        return record

    def assert_projection_allowed(self, field_family: str, surface: str) -> None:
        """Raise if ``surface`` is not an allowed projection for a field family."""

        family = self._family(field_family)
        if surface not in family.allowed_projection_surfaces:
            raise SourceTruthContractError(
                "source_truth_projection_surface_disallowed",
                f"{surface} may not project authority family {field_family}",
            )

    def assert_package_allowed(self, field_family: str, surface: str) -> None:
        """Raise if ``surface`` is not an allowed package/summarize surface."""

        family = self._family(field_family)
        if surface not in family.allowed_package_surfaces:
            raise SourceTruthContractError(
                "source_truth_package_surface_disallowed",
                f"{surface} may not package authority family {field_family}",
            )

    def _family(self, field_family: str) -> SourceTruthFieldFamily:
        try:
            return self.field_families[field_family]
        except KeyError as exc:
            raise SourceTruthContractError(
                "source_truth_field_family_unknown",
                f"Unknown source-truth field family: {field_family}",
            ) from exc


def detect_source_truth_conflict(
    *,
    field_family: str,
    authoritative_source: str,
    authoritative_surface: str,
    authoritative_values: Mapping[str, Any],
    conflicting_source: str,
    conflicting_surface: str,
    conflicting_values: Mapping[str, Any],
    fields: Sequence[str],
    downstream_impact: str,
    runtime_event_refs: Sequence[str] = (),
    cas_refs: Sequence[str] = (),
    authoritative_ref: str | None = None,
    conflicting_ref: str | None = None,
    details: Mapping[str, Any] | None = None,
    lattice: SourceTruthLattice | None = None,
    recorded_at: datetime | None = None,
) -> dict[str, Any] | None:
    """Return a typed conflict record when a reader sees lower-authority drift.

    Reader boundaries use this before accepting authority-bearing values from
    progress summaries, API/dashboard projections, canary bundles, readiness
    aggregators, public exports, or approval packets.  Matching values return
    ``None``; mismatches return a complete source-truth conflict record with a
    nested losing-authority record from the lattice.
    """

    active_lattice = lattice or load_source_truth_lattice()
    family = active_lattice._family(field_family)
    normalized_fields = _clean_text_sequence(fields, field=f"{field_family}.fields")
    if not normalized_fields:
        raise SourceTruthContractError(
            "source_truth_conflict_fields_missing",
            f"{field_family} conflict check must include at least one field",
        )

    lost_fields = tuple(
        field
        for field in normalized_fields
        if _authority_value_differs(
            _field_value(authoritative_values, field),
            _field_value(conflicting_values, field),
        )
    )
    if not lost_fields:
        return None

    authoritative_ref = authoritative_ref or _first_ref(authoritative_values)
    conflicting_ref = conflicting_ref or _first_ref(conflicting_values)
    merged_runtime_event_refs = _merge_text_refs(
        runtime_event_refs,
        _runtime_event_refs(authoritative_values),
        _runtime_event_refs(conflicting_values),
    )
    merged_cas_refs = _merge_text_refs(
        cas_refs,
        _cas_refs(authoritative_values),
        _cas_refs(conflicting_values),
        (authoritative_ref,) if authoritative_ref else (),
        (conflicting_ref,) if conflicting_ref else (),
    )
    impact = _optional_text(downstream_impact) or (
        "Authority-bearing projection rejected before approval or publication."
    )
    conflict_details = {
        "authoritative_source": authoritative_source,
        "conflicting_source": conflicting_source,
        "downstream_impact": impact,
        **dict(details or {}),
    }
    losing_record = active_lattice.losing_authority_record(
        field_family=field_family,
        authoritative_surface=authoritative_surface,
        losing_surface=conflicting_surface,
        lost_fields=lost_fields,
        authoritative_ref=authoritative_ref,
        losing_ref=conflicting_ref,
        details=conflict_details,
        recorded_at=recorded_at,
    )
    return {
        "schema_version": SOURCE_TRUTH_CONFLICT_SCHEMA,
        "authoritative_source": authoritative_source,
        "authoritative_surface": authoritative_surface,
        "conflicting_source": conflicting_source,
        "conflicting_surface": conflicting_surface,
        "field_family": family.id,
        "lost_fields": list(lost_fields),
        "runtime_event_refs": list(merged_runtime_event_refs),
        "cas_refs": list(merged_cas_refs),
        "authoritative_ref": authoritative_ref,
        "conflicting_ref": conflicting_ref,
        "losing_authority_record": losing_record,
        "failure_code": family.conflict_failure_code,
        "owner": family.owner,
        "downstream_impact": impact,
        "next_diagnostic_command": family.next_diagnostic_command,
        "recorded_at": losing_record["recorded_at"],
        "details": conflict_details,
    }


def load_source_truth_lattice(
    path: str | Path | None = None,
) -> SourceTruthLattice:
    """Load and validate the source-truth lattice registry."""

    lattice_path = Path(path or DEFAULT_SOURCE_TRUTH_LATTICE_PATH)
    document = _load_toml(lattice_path)
    metadata = _mapping(document.get("metadata"), field="metadata")
    semantic_preservation = _mapping(
        document.get("semantic_preservation"),
        field="semantic_preservation",
    )
    record_format = _mapping(
        document.get("losing_authority_record_format"),
        field="losing_authority_record_format",
    )
    default_record_fields = _text_tuple(
        record_format.get("required_fields"),
        default=DEFAULT_LOSING_AUTHORITY_RECORD_FIELDS,
        field="losing_authority_record_format.required_fields",
    )
    default_semantic_fields = _required_text_tuple(
        semantic_preservation,
        "required_fields",
        family_id="semantic_preservation",
    )
    next_diagnostic_command = _required_text(metadata, "next_diagnostic_command")

    families: dict[str, SourceTruthFieldFamily] = {}
    raw_families = document.get("field_families")
    if not isinstance(raw_families, list):
        raise SourceTruthContractError(
            "source_truth_field_families_missing",
            "source_truth_lattice.toml must declare [[field_families]] entries",
        )
    for raw_family in raw_families:
        family = SourceTruthFieldFamily.from_mapping(
            _mapping(raw_family, field="field_families[]"),
            default_record_fields=default_record_fields,
            default_semantic_fields=default_semantic_fields,
            default_next_diagnostic_command=next_diagnostic_command,
        )
        if family.id in families:
            raise SourceTruthContractError(
                "source_truth_field_family_duplicate",
                f"Duplicate field-family declaration: {family.id}",
            )
        families[family.id] = family

    missing = sorted(MINIMUM_AUTHORITY_FIELD_FAMILIES - set(families))
    if missing:
        raise SourceTruthContractError(
            "source_truth_minimum_families_missing",
            f"Missing minimum authority field families: {missing}",
        )

    return SourceTruthLattice(
        schema_version=_required_text(metadata, "schema_version"),
        owner=_required_text(metadata, "owner"),
        field_families=families,
        adapter_semantic_fields=default_semantic_fields,
        losing_authority_record_schema=_required_text(record_format, "schema"),
        losing_authority_record_required_fields=default_record_fields,
        next_diagnostic_command=next_diagnostic_command,
        path=lattice_path,
    )


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise SourceTruthContractError(
            "source_truth_lattice_missing",
            f"Source-truth lattice not found at {path}",
        ) from exc
    if not isinstance(data, dict):
        raise SourceTruthContractError(
            "source_truth_lattice_malformed",
            f"Source-truth lattice at {path} is not a TOML table",
        )
    return data


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SourceTruthContractError(
            "source_truth_table_missing",
            f"{field} must be a TOML table",
        )
    return value


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    text = _optional_text(payload.get(key))
    if text is None:
        raise SourceTruthContractError(
            "source_truth_required_field_missing",
            f"Required source-truth field is missing or blank: {key}",
        )
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_or_default(value: object, *, default: str) -> str:
    return _optional_text(value) or default


def _required_text_tuple(
    payload: Mapping[str, Any],
    key: str,
    *,
    family_id: str,
) -> tuple[str, ...]:
    return _text_tuple(
        payload.get(key),
        default=(),
        field=f"{family_id}.{key}",
        require_non_empty=True,
    )


def _text_tuple(
    value: object,
    *,
    default: Sequence[str],
    field: str,
    require_non_empty: bool = False,
) -> tuple[str, ...]:
    values = tuple(default) if value is None else _clean_text_sequence(value, field=field)
    if require_non_empty and not values:
        raise SourceTruthContractError(
            "source_truth_list_empty",
            f"{field} must contain at least one value",
        )
    return values


def _clean_text_sequence(value: object, *, field: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise SourceTruthContractError(
            "source_truth_list_malformed",
            f"{field} must be a TOML array of strings",
        )
    cleaned: list[str] = []
    for item in value:
        text = _optional_text(item)
        if text is None:
            raise SourceTruthContractError(
                "source_truth_list_value_blank",
                f"{field} contains a blank value",
            )
        cleaned.append(text)
    return tuple(dict.fromkeys(cleaned))


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping | Sequence) and not isinstance(value, str):
        return bool(value)
    return True


def _field_value(payload: Mapping[str, Any], field: str) -> Any:
    current: Any = payload
    for part in field.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _authority_value_differs(authoritative_value: Any, conflicting_value: Any) -> bool:
    if not _present(authoritative_value):
        return False
    if not _present(conflicting_value):
        return True
    return _json_fingerprint(authoritative_value) != _json_fingerprint(conflicting_value)


def _json_fingerprint(value: Any) -> str:
    return json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_json_safe(child) for child in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _first_ref(payload: Mapping[str, Any]) -> str | None:
    refs = _merge_text_refs(_cas_refs(payload), _runtime_event_refs(payload))
    return refs[0] if refs else None


def _runtime_event_refs(payload: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for key in (
        "runtime_event_ref",
        "diagnostic_event_ref",
        "event_ref",
        "runtime_event_id",
        "diagnostic_event_id",
        "event_id",
    ):
        text = _optional_text(payload.get(key))
        if text is not None:
            refs.append(text)
    for key in ("runtime_event_refs", "diagnostic_event_refs", "event_refs"):
        refs.extend(_text_refs_from_value(payload.get(key)))
    return tuple(dict.fromkeys(refs))


def _cas_refs(payload: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for key, value in payload.items():
        key_text = str(key)
        if key_text in {"cas_ref", "runtime_cas_ref", "artifact_ref", "ref"}:
            refs.extend(_text_refs_from_value(value))
        elif key_text.endswith("_ref"):
            refs.extend(
                ref for ref in _text_refs_from_value(value) if _looks_like_cas_ref(ref)
            )
    return tuple(dict.fromkeys(refs))


def _text_refs_from_value(value: Any) -> tuple[str, ...]:
    text = _optional_text(value)
    if text is not None:
        return (text,)
    if isinstance(value, Mapping):
        refs: list[str] = []
        for key in ("artifact_id", "ref", "uri", "path"):
            refs.extend(_text_refs_from_value(value.get(key)))
        return tuple(dict.fromkeys(refs))
    if isinstance(value, Sequence) and not isinstance(value, str):
        refs = []
        for item in value:
            refs.extend(_text_refs_from_value(item))
        return tuple(dict.fromkeys(refs))
    return ()


def _looks_like_cas_ref(value: str) -> bool:
    return value.startswith("sha256:") or value.startswith("cas://")


def _merge_text_refs(*groups: Sequence[str | None]) -> tuple[str, ...]:
    refs: list[str] = []
    for group in groups:
        for value in group:
            text = _optional_text(value)
            if text is not None:
                refs.append(text)
    return tuple(dict.fromkeys(refs))


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "DEFAULT_SOURCE_TRUTH_LATTICE_PATH",
    "MINIMUM_AUTHORITY_FIELD_FAMILIES",
    "SOURCE_TRUTH_CONFLICT_SCHEMA",
    "SourceTruthContractError",
    "SourceTruthFieldFamily",
    "SourceTruthLattice",
    "detect_source_truth_conflict",
    "load_source_truth_lattice",
]
