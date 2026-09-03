"""Canonical content-bound generation bases for persisted Data Forge artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, cast

GENERATION_BASIS_SCHEMA_VERSION = "policyos.generation_basis.v1"
_CONTENT_IDENTITY_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class GenerationBasisMember:
    """One content-bound member of an artifact generation basis."""

    identifier: str
    content_identity: str

    def to_dict(self) -> dict[str, str]:
        """Return the canonical persisted member shape."""
        return {
            "identifier": self.identifier,
            "content_identity": self.content_identity,
        }


@dataclass(frozen=True)
class GenerationBasis:
    """A versioned identity for the complete basis of one generated artifact."""

    schema_version: Literal["policyos.generation_basis.v1"]
    basis_kind: str
    generator_rule_version: str
    members: tuple[GenerationBasisMember, ...]
    basis_digest: str

    def to_dict(self) -> dict[str, object]:
        """Return the canonical persisted basis shape."""
        return {
            **_basis_payload(
                basis_kind=self.basis_kind,
                generator_rule_version=self.generator_rule_version,
                members=self.members,
            ),
            "basis_digest": self.basis_digest,
        }


@dataclass(frozen=True)
class GenerationBasisComparison:
    """Typed comparison between a persisted and current generation basis."""

    status: Literal["current", "missing", "malformed", "incompatible"]
    recorded_generation: str
    current_generation: str
    recorded_rule_version: str
    current_rule_version: str

    @property
    def is_current(self) -> bool:
        """Return whether the persisted basis exactly matches the current basis."""
        return self.status == "current"


def build_generation_basis(
    *,
    basis_kind: str,
    generator_rule_version: str,
    members: Iterable[tuple[str, bytes]],
) -> GenerationBasis:
    """Build a canonical basis while deriving every member identity from bytes."""
    if not basis_kind:
        raise ValueError("basis_kind must be non-empty")
    if not generator_rule_version:
        raise ValueError("generator_rule_version must be non-empty")
    bound_members = tuple(
        sorted(
            (
                GenerationBasisMember(
                    identifier=identifier,
                    content_identity=_sha256(raw),
                )
                for identifier, raw in members
            ),
            key=lambda member: member.identifier,
        )
    )
    identifiers = tuple(member.identifier for member in bound_members)
    if not identifiers or any(not identifier for identifier in identifiers):
        raise ValueError("generation basis members must be non-empty")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("generation basis member identifiers must be unique")
    payload = _basis_payload(
        basis_kind=basis_kind,
        generator_rule_version=generator_rule_version,
        members=bound_members,
    )
    return GenerationBasis(
        schema_version=GENERATION_BASIS_SCHEMA_VERSION,
        basis_kind=basis_kind,
        generator_rule_version=generator_rule_version,
        members=bound_members,
        basis_digest=_sha256(_canonical_json(payload)),
    )


def compare_generation_basis(
    recorded: object,
    *,
    current: GenerationBasis,
) -> GenerationBasisComparison:
    """Compare a persisted basis with the current basis without trusting its digest."""
    if recorded is None:
        return GenerationBasisComparison(
            status="missing",
            recorded_generation="unrecorded",
            current_generation=current.basis_digest,
            recorded_rule_version="unrecorded",
            current_rule_version=current.generator_rule_version,
        )
    try:
        parsed = _parse_generation_basis(recorded)
    except (TypeError, ValueError):
        return GenerationBasisComparison(
            status="malformed",
            recorded_generation="malformed",
            current_generation=current.basis_digest,
            recorded_rule_version="malformed",
            current_rule_version=current.generator_rule_version,
        )
    status: Literal["current", "incompatible"] = (
        "current" if parsed == current else "incompatible"
    )
    return GenerationBasisComparison(
        status=status,
        recorded_generation=parsed.basis_digest,
        current_generation=current.basis_digest,
        recorded_rule_version=parsed.generator_rule_version,
        current_rule_version=current.generator_rule_version,
    )


def _parse_generation_basis(value: object) -> GenerationBasis:
    if not isinstance(value, Mapping):
        raise TypeError("generation basis must be an object")
    raw = cast("Mapping[object, object]", value)
    expected_keys = {
        "schema_version",
        "basis_kind",
        "generator_rule_version",
        "members",
        "basis_digest",
    }
    if set(raw) != expected_keys:
        raise ValueError("generation basis keys differ from the closed contract")
    schema_version = raw["schema_version"]
    basis_kind = raw["basis_kind"]
    generator_rule_version = raw["generator_rule_version"]
    basis_digest = raw["basis_digest"]
    raw_members = raw["members"]
    if schema_version != GENERATION_BASIS_SCHEMA_VERSION:
        raise ValueError("generation basis schema version is unsupported")
    if not isinstance(basis_kind, str) or not basis_kind:
        raise ValueError("generation basis kind is invalid")
    if not isinstance(generator_rule_version, str) or not generator_rule_version:
        raise ValueError("generation basis rule version is invalid")
    if not isinstance(basis_digest, str) or not _CONTENT_IDENTITY_PATTERN.fullmatch(
        basis_digest
    ):
        raise ValueError("generation basis digest is invalid")
    if not isinstance(raw_members, list) or not raw_members:
        raise ValueError("generation basis members are invalid")

    members: list[GenerationBasisMember] = []
    for raw_member in raw_members:
        if not isinstance(raw_member, Mapping) or set(raw_member) != {
            "identifier",
            "content_identity",
        }:
            raise ValueError("generation basis member shape is invalid")
        identifier = raw_member["identifier"]
        content_identity = raw_member["content_identity"]
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("generation basis member identifier is invalid")
        if not isinstance(content_identity, str) or not _CONTENT_IDENTITY_PATTERN.fullmatch(
            content_identity
        ):
            raise ValueError("generation basis member identity is invalid")
        members.append(
            GenerationBasisMember(
                identifier=identifier,
                content_identity=content_identity,
            )
        )
    member_tuple = tuple(members)
    identifiers = tuple(member.identifier for member in member_tuple)
    if identifiers != tuple(sorted(identifiers)) or len(identifiers) != len(set(identifiers)):
        raise ValueError("generation basis members must be sorted and unique")
    payload = _basis_payload(
        basis_kind=basis_kind,
        generator_rule_version=generator_rule_version,
        members=member_tuple,
    )
    if basis_digest != _sha256(_canonical_json(payload)):
        raise ValueError("generation basis digest does not bind its payload")
    return GenerationBasis(
        schema_version=GENERATION_BASIS_SCHEMA_VERSION,
        basis_kind=basis_kind,
        generator_rule_version=generator_rule_version,
        members=member_tuple,
        basis_digest=basis_digest,
    )


def _basis_payload(
    *,
    basis_kind: str,
    generator_rule_version: str,
    members: tuple[GenerationBasisMember, ...],
) -> dict[str, object]:
    return {
        "schema_version": GENERATION_BASIS_SCHEMA_VERSION,
        "basis_kind": basis_kind,
        "generator_rule_version": generator_rule_version,
        "members": [member.to_dict() for member in members],
    }


def _canonical_json(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


__all__ = [
    "GENERATION_BASIS_SCHEMA_VERSION",
    "GenerationBasis",
    "GenerationBasisComparison",
    "GenerationBasisMember",
    "build_generation_basis",
    "compare_generation_basis",
]
