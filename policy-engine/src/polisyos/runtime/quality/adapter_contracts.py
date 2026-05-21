"""Adapter semantic-preservation checks for source-truth field families."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.source_truth import (
    DEFAULT_SOURCE_TRUTH_LATTICE_PATH,
    MINIMUM_AUTHORITY_FIELD_FAMILIES,
    SourceTruthLattice,
    load_source_truth_lattice,
)


class AdapterContractError(ValueError):
    """Raised when adapter preservation contracts are malformed or misused."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class AdapterContract:
    """One declared adapter boundary that must preserve authority semantics."""

    id: str
    source_surface: str
    target_surface: str
    field_families: tuple[str, ...]
    required_semantic_fields: tuple[str, ...]
    blocker_code: str
    owner: str
    next_diagnostic_command: str


@dataclass(frozen=True)
class AdapterContractRegistry:
    """Adapter preservation registry backed by the source-truth lattice."""

    adapter_paths: dict[str, AdapterContract]
    lattice: SourceTruthLattice
    path: Path


@dataclass(frozen=True)
class AdapterSurfacePayload:
    """Authority-bearing payloads visible on one adapter surface."""

    surface: str
    field_families: Mapping[str, Mapping[str, Any]]

    def payload_for(self, field_family: str) -> Mapping[str, Any] | None:
        payload = self.field_families.get(field_family)
        if payload is None:
            return None
        if not isinstance(payload, Mapping):
            raise AdapterContractError(
                "hds_adapter_payload_malformed",
                f"{field_family} payload on {self.surface} is not a mapping",
            )
        return payload


@dataclass(frozen=True)
class AdapterLossBlocker:
    """A blocking semantic-loss finding for one adapter field family."""

    code: str
    adapter_path: str
    field_family: str
    source_surface: str
    target_surface: str
    lost_fields: tuple[str, ...]
    owner: str
    next_diagnostic_command: str
    losing_authority_record: Mapping[str, Any]

    def to_failure(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "adapter_path": self.adapter_path,
            "field_family": self.field_family,
            "source_surface": self.source_surface,
            "target_surface": self.target_surface,
            "lost_fields": list(self.lost_fields),
            "owner": self.owner,
            "next_diagnostic_command": self.next_diagnostic_command,
            "losing_authority_record": dict(self.losing_authority_record),
        }


@dataclass(frozen=True)
class AdapterPreservationReport:
    """Result of checking one adapter boundary for semantic loss."""

    adapter_path: str
    status: str
    blockers: tuple[AdapterLossBlocker, ...]
    checked_field_families: tuple[str, ...]

    def to_blocking_failures(self) -> list[dict[str, Any]]:
        return [blocker.to_failure() for blocker in self.blockers]


@dataclass(frozen=True)
class AdapterSemanticDifference:
    """Typed semantic difference across one adapter field-family payload."""

    lost_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    conflicting_fields: tuple[str, ...]


def adapter_surface_payload_from_envelope(
    envelope: Mapping[str, Any] | AdapterSurfacePayload,
    *,
    expected_surface: str | None = None,
) -> AdapterSurfacePayload:
    """Read an adapter surface from its typed source-truth envelope."""

    if isinstance(envelope, AdapterSurfacePayload):
        if expected_surface is not None and envelope.surface != expected_surface:
            raise AdapterContractError(
                "hds_adapter_envelope_surface_mismatch",
                f"Expected {expected_surface}, got {envelope.surface}",
            )
        return envelope

    typed_payload = envelope.get("source_truth")
    if typed_payload is None:
        typed_payload = envelope
    if not isinstance(typed_payload, Mapping):
        raise AdapterContractError(
            "hds_adapter_envelope_malformed",
            "source_truth envelope must be a mapping",
        )

    surface = _optional_text(typed_payload.get("surface")) or expected_surface
    if surface is None:
        raise AdapterContractError(
            "hds_adapter_envelope_surface_missing",
            "source_truth envelope must declare a surface",
        )
    if expected_surface is not None and surface != expected_surface:
        raise AdapterContractError(
            "hds_adapter_envelope_surface_mismatch",
            f"Expected {expected_surface}, got {surface}",
        )

    field_families = typed_payload.get("field_families")
    if field_families is None and expected_surface is not None:
        field_families = typed_payload
    if not isinstance(field_families, Mapping):
        raise AdapterContractError(
            "hds_adapter_envelope_field_families_missing",
            "source_truth envelope must declare field_families",
        )
    return AdapterSurfacePayload(surface=surface, field_families=field_families)


def load_adapter_contract_registry(
    path: str | Path | None = None,
) -> AdapterContractRegistry:
    """Load adapter preservation contracts from the source-truth lattice file."""

    registry_path = Path(path or DEFAULT_SOURCE_TRUTH_LATTICE_PATH)
    lattice = load_source_truth_lattice(registry_path)
    document = _load_toml(registry_path)
    raw_paths = document.get("adapter_paths")
    if not isinstance(raw_paths, list):
        raise AdapterContractError(
            "hds_adapter_paths_missing",
            "source_truth_lattice.toml must declare [[adapter_paths]] entries",
        )

    adapters: dict[str, AdapterContract] = {}
    for raw_path in raw_paths:
        payload = _mapping(raw_path, field="adapter_paths[]")
        contract = AdapterContract(
            id=_required_text(payload, "id"),
            source_surface=_required_text(payload, "source_surface"),
            target_surface=_required_text(payload, "target_surface"),
            field_families=_text_tuple(
                payload.get("field_families"),
                field="adapter_paths[].field_families",
            ),
            required_semantic_fields=_text_tuple(
                payload.get("required_semantic_fields"),
                field="adapter_paths[].required_semantic_fields",
            )
            or lattice.adapter_semantic_fields,
            blocker_code=_required_text(payload, "blocker_code"),
            owner=_required_text(payload, "owner"),
            next_diagnostic_command=_required_text(payload, "next_diagnostic_command"),
        )
        if contract.id in adapters:
            raise AdapterContractError(
                "hds_adapter_path_duplicate",
                f"Duplicate adapter path declaration: {contract.id}",
            )
        unknown_families = sorted(set(contract.field_families) - set(lattice.field_families))
        if unknown_families:
            raise AdapterContractError(
                "hds_adapter_unknown_field_family",
                f"{contract.id} references unknown field families: {unknown_families}",
            )
        missing_minimum = sorted(MINIMUM_AUTHORITY_FIELD_FAMILIES - set(contract.field_families))
        if missing_minimum:
            raise AdapterContractError(
                "hds_adapter_minimum_families_missing",
                f"{contract.id} omits minimum authority families: {missing_minimum}",
            )
        adapters[contract.id] = contract

    return AdapterContractRegistry(adapter_paths=adapters, lattice=lattice, path=registry_path)


def validate_adapter_preservation(
    *,
    adapter_path: str,
    before: AdapterSurfacePayload,
    after: AdapterSurfacePayload,
    registry: AdapterContractRegistry | None = None,
) -> AdapterPreservationReport:
    """Check that a declared adapter did not drop authority-bearing semantics."""

    active_registry = registry or load_adapter_contract_registry()
    try:
        contract = active_registry.adapter_paths[adapter_path]
    except KeyError as exc:
        raise AdapterContractError(
            "hds_adapter_path_unknown",
            f"Unknown adapter path: {adapter_path}",
        ) from exc

    if before.surface != contract.source_surface:
        raise AdapterContractError(
            "hds_adapter_source_surface_mismatch",
            f"{adapter_path} expects source {contract.source_surface}, got {before.surface}",
        )
    if after.surface != contract.target_surface:
        raise AdapterContractError(
            "hds_adapter_target_surface_mismatch",
            f"{adapter_path} expects target {contract.target_surface}, got {after.surface}",
        )

    blockers: list[AdapterLossBlocker] = []
    checked: list[str] = []
    for field_family in contract.field_families:
        before_payload = before.payload_for(field_family)
        if before_payload is None:
            continue
        checked.append(field_family)
        after_payload = after.payload_for(field_family)
        family = active_registry.lattice.field_families[field_family]
        difference = _semantic_difference(
            before_payload=before_payload,
            after_payload=after_payload,
            required_fields=_required_semantic_fields(contract, family),
        )
        lost_fields = difference.lost_fields
        if not lost_fields:
            continue

        losing_record = active_registry.lattice.losing_authority_record(
            field_family=field_family,
            authoritative_surface=before.surface,
            losing_surface=after.surface,
            lost_fields=lost_fields,
            authoritative_ref=_ref_from_payload(before_payload),
            losing_ref=_ref_from_payload(after_payload),
            details={
                "adapter_path": adapter_path,
                "family_conflict_failure_code": family.conflict_failure_code,
                "preservation_requirements": list(
                    family.adapter_semantic_preservation_requirements
                ),
                "missing_fields": list(difference.missing_fields),
                "conflicting_fields": list(difference.conflicting_fields),
            },
        )
        blockers.append(
            AdapterLossBlocker(
                code=contract.blocker_code,
                adapter_path=contract.id,
                field_family=field_family,
                source_surface=before.surface,
                target_surface=after.surface,
                lost_fields=lost_fields,
                owner=contract.owner,
                next_diagnostic_command=contract.next_diagnostic_command,
                losing_authority_record=losing_record,
            )
        )

    return AdapterPreservationReport(
        adapter_path=contract.id,
        status="blocked" if blockers else "pass",
        blockers=tuple(blockers),
        checked_field_families=tuple(checked),
    )


def _required_semantic_fields(
    contract: AdapterContract,
    family: Any,
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            [
                *contract.required_semantic_fields,
                *getattr(family, "required_semantic_fields", ()),
            ]
        )
    )


def _semantic_difference(
    *,
    before_payload: Mapping[str, Any],
    after_payload: Mapping[str, Any] | None,
    required_fields: Sequence[str],
) -> AdapterSemanticDifference:
    missing: list[str] = []
    conflicting: list[str] = []
    for field in required_fields:
        before_value = before_payload.get(field)
        if not _present(before_value):
            continue
        after_value = after_payload.get(field) if after_payload is not None else None
        if not _present(after_value):
            missing.append(field)
        elif not _semantic_values_equal(before_value, after_value):
            conflicting.append(field)
    return AdapterSemanticDifference(
        lost_fields=tuple(dict.fromkeys([*missing, *conflicting])),
        missing_fields=tuple(missing),
        conflicting_fields=tuple(conflicting),
    )


def _lost_semantic_fields(
    *,
    before_payload: Mapping[str, Any],
    after_payload: Mapping[str, Any] | None,
    required_fields: Sequence[str],
) -> tuple[str, ...]:
    return _semantic_difference(
        before_payload=before_payload,
        after_payload=after_payload,
        required_fields=required_fields,
    ).lost_fields


def _semantic_values_equal(before_value: Any, after_value: Any) -> bool:
    return _semantic_fingerprint(before_value) == _semantic_fingerprint(after_value)


def _semantic_fingerprint(value: Any) -> str:
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


def _ref_from_payload(payload: Mapping[str, Any] | None) -> str | None:
    if payload is None:
        return None
    lineage = payload.get("lineage")
    if isinstance(lineage, Mapping):
        for key in ("output_ref", "artifact_ref", "cas_ref", "runtime_ref"):
            value = _optional_text(lineage.get(key))
            if value is not None:
                return value
    for key in ("artifact_ref", "cas_ref", "runtime_ref", "ref"):
        value = _optional_text(payload.get(key))
        if value is not None:
            return value
    return None


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise AdapterContractError(
            "hds_adapter_contract_registry_missing",
            f"Adapter contract registry not found at {path}",
        ) from exc
    if not isinstance(data, dict):
        raise AdapterContractError(
            "hds_adapter_contract_registry_malformed",
            f"Adapter contract registry at {path} is not a TOML table",
        )
    return data


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AdapterContractError(
            "hds_adapter_table_missing",
            f"{field} must be a TOML table",
        )
    return value


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    text = _optional_text(payload.get(key))
    if text is None:
        raise AdapterContractError(
            "hds_adapter_required_field_missing",
            f"Required adapter contract field is missing or blank: {key}",
        )
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise AdapterContractError(
            "hds_adapter_list_malformed",
            f"{field} must be a TOML array of strings",
        )
    cleaned: list[str] = []
    for item in value:
        text = _optional_text(item)
        if text is None:
            raise AdapterContractError(
                "hds_adapter_list_value_blank",
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


__all__ = [
    "AdapterContract",
    "AdapterContractError",
    "AdapterContractRegistry",
    "AdapterLossBlocker",
    "AdapterPreservationReport",
    "AdapterSemanticDifference",
    "AdapterSurfacePayload",
    "adapter_surface_payload_from_envelope",
    "load_adapter_contract_registry",
    "validate_adapter_preservation",
]
