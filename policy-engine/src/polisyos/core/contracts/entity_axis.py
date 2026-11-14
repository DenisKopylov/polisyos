"""Typed identity for finite, candidate-scoped entity axes."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.manifest import SchemaInfo

_SHA256 = r"^sha256:[0-9a-f]{64}$"
_AXIS_SCHEMA_VERSION = "polisyos.core.selected_entity_axis.v2"


class EntityAxisMemberId(BaseModel):
    """One stable axis key with its scalar type retained in identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["string", "integer"]
    value: StrictStr | StrictInt

    @model_validator(mode="after")
    def _kind_matches_value(self) -> EntityAxisMemberId:
        if self.kind == "string":
            if type(self.value) is not str or not self.value:
                raise ValueError("entity_axis_string_id_invalid")
        elif type(self.value) is not int:
            # type() intentionally excludes bool, which is an int subclass.
            raise ValueError("entity_axis_integer_id_invalid")
        return self


class SelectedEntityAxis(BaseModel):
    """Content-bound finite membership for one candidate computation.

    This identifies membership in a selected source view or caller-declared
    axis. It does not assert that the members represent a real-world target
    population, nor that their identities have external institutional
    authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ARTIFACT_KIND: ClassVar[str] = "foundry.selected_entity_axis"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.SelectedEntityAxis"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "2.0"
    ARTIFACT_SCHEMA: ClassVar[SchemaInfo] = SchemaInfo(
        name=ARTIFACT_SCHEMA_NAME,
        version=ARTIFACT_SCHEMA_VERSION,
    )

    schema_version: Literal[_AXIS_SCHEMA_VERSION] = _AXIS_SCHEMA_VERSION
    identity_basis: Literal["selected_source_view", "caller_declared_model_axis"]
    namespace: str = Field(min_length=1, strict=True)
    source_view_ref: ArtifactRef | None = None
    model_revision: str | None = Field(default=None, min_length=1, strict=True)
    member_values_pointer: str | None = Field(default=None, min_length=1, strict=True)
    membership_provenance: Literal["recomputed_from_selected_view", "consumer_asserted"]
    model_selection_status: Literal["not_established"] = "not_established"
    members: tuple[EntityAxisMemberId, ...] = Field(min_length=1)
    cardinality: Annotated[int, Field(gt=0, strict=True)]
    canonical_order: Literal["typed_id_ascending_v1"] = "typed_id_ascending_v1"
    membership_sha256: str = Field(pattern=_SHA256)
    axis_sha256: str = Field(pattern=_SHA256)
    scope: Literal["candidate_selected_view_or_caller_axis"] = (
        "candidate_selected_view_or_caller_axis"
    )

    @model_validator(mode="after")
    def _identity_and_membership_are_coherent(self) -> SelectedEntityAxis:
        if self.namespace != self.namespace.strip():
            raise ValueError("entity_axis_namespace_not_trimmed")
        source_basis = self.identity_basis == "selected_source_view"
        if source_basis:
            if (
                type(self.source_view_ref) is not ArtifactRef
                or self.source_view_ref.manifest_profile_sha256 is None
                or self.model_revision is not None
                or not _is_pointer(self.member_values_pointer)
                or self.membership_provenance != "recomputed_from_selected_view"
            ):
                raise ValueError("entity_axis_selected_source_identity_invalid")
        elif (
            self.source_view_ref is not None
            or self.model_revision is None
            or self.model_revision != self.model_revision.strip()
            or self.member_values_pointer is not None
            or self.membership_provenance != "consumer_asserted"
        ):
            raise ValueError("entity_axis_caller_declared_identity_invalid")

        if self.cardinality != len(self.members):
            raise ValueError("entity_axis_cardinality_mismatch")
        keys = tuple(_member_sort_key(member) for member in self.members)
        if len(set(keys)) != len(keys):
            raise ValueError("entity_axis_duplicate_member")
        if keys != tuple(sorted(keys)):
            raise ValueError("entity_axis_member_order_noncanonical")
        if self.membership_sha256 != _membership_digest(self.members):
            raise ValueError("entity_axis_membership_digest_mismatch")
        if self.axis_sha256 != _axis_digest(
            identity_basis=self.identity_basis,
            namespace=self.namespace,
            source_view_ref=self.source_view_ref,
            model_revision=self.model_revision,
            member_values_pointer=self.member_values_pointer,
            membership_provenance=self.membership_provenance,
            model_selection_status=self.model_selection_status,
            members=self.members,
            cardinality=self.cardinality,
        ):
            raise ValueError("entity_axis_digest_mismatch")
        return self


def _is_pointer(value: str | None) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("/")
        and not value.endswith("/")
        and "//" not in value
    )


def _member_sort_key(member: EntityAxisMemberId) -> tuple[str, int | str]:
    return (member.kind, member.value)  # type: ignore[return-value]


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _membership_digest(members: tuple[EntityAxisMemberId, ...]) -> str:
    payload = [member.model_dump(mode="json") for member in members]
    return "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()


def _axis_digest(
    *,
    identity_basis: str,
    namespace: str,
    source_view_ref: ArtifactRef | None,
    model_revision: str | None,
    member_values_pointer: str | None,
    membership_provenance: str,
    model_selection_status: str,
    members: tuple[EntityAxisMemberId, ...],
    cardinality: int,
) -> str:
    payload = {
        "schema_version": _AXIS_SCHEMA_VERSION,
        "identity_basis": identity_basis,
        "namespace": namespace,
        "source_view_ref": (
            None if source_view_ref is None else source_view_ref.model_dump(mode="json")
        ),
        "model_revision": model_revision,
        "member_values_pointer": member_values_pointer,
        "membership_provenance": membership_provenance,
        "model_selection_status": model_selection_status,
        "members": [member.model_dump(mode="json") for member in members],
        "cardinality": cardinality,
        "canonical_order": "typed_id_ascending_v1",
    }
    return "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()
