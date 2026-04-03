"""Public artifacts contracts module API."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, Sequence, runtime_checkable

from pydantic import BaseModel, ConfigDict, RootModel, field_validator

from polisyos.ir.canon import CanonSpec

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class ArtifactID(RootModel[str]):
    """IR-local artifact ID model compatible with CAS interfaces."""

    prefix: ClassVar[str] = "sha256:"

    @field_validator("root", mode="before")
    @classmethod
    def validate_root(cls, value: Any) -> str:
        if not isinstance(value, str):
            value = str(value)
        if not value.startswith(cls.prefix):
            raise ValueError("ArtifactID must start with sha256:")
        hex64 = value[len(cls.prefix) :].lower()
        if not _SHA256_HEX_RE.match(hex64):
            raise ValueError("sha256 hex must be 64 lowercase characters [0-9a-f]")
        return f"{cls.prefix}{hex64}"

    @classmethod
    def from_sha256_hex(cls, hex64: str) -> "ArtifactID":
        hex64 = hex64.lower()
        if not _SHA256_HEX_RE.match(hex64):
            raise ValueError("sha256 hex must be 64 characters [0-9a-f]")
        return cls(f"{cls.prefix}{hex64}")

    @property
    def hex(self) -> str:
        algo, hex64 = self.root.split(":", 1)
        if algo != "sha256":
            raise ValueError(f"Unsupported algo: {algo}")
        if not _SHA256_HEX_RE.match(hex64):
            raise ValueError("Invalid sha256 hex")
        return hex64

    def __str__(self) -> str:
        return self.root


class SchemaInfo(BaseModel):
    """Schema info data model."""
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str


class CanonInfo(BaseModel):
    """Canon info data model."""
    model_config = ConfigDict(extra="forbid")

    name: str = "polisyos.canon.json"
    version: str = "0.1.0"
    forbid_floats: bool = True
    forbid_nan_inf: bool = True
    sort_keys: bool = True
    separators: tuple[str, str] = (",", ":")
    ensure_ascii: bool = False

    @classmethod
    def from_spec(cls, spec: CanonSpec) -> "CanonInfo":
        return cls(
            name=spec.name,
            version=spec.version,
            forbid_floats=spec.forbid_floats,
            forbid_nan_inf=spec.forbid_nan_inf,
            sort_keys=spec.sort_keys,
            separators=spec.separators,
            ensure_ascii=spec.ensure_ascii,
        )


class InputRef(BaseModel):
    """Input ref data model."""
    model_config = ConfigDict(extra="forbid")
    artifact_id: ArtifactID
    role: str


@dataclass(frozen=True)
class PutOptions:
    """Put options data model."""
    kind: str
    media_type: str
    schema: SchemaInfo | None = None
    producer: Any = None
    env: Any = None
    inputs: list[InputRef] | None = None
    canon: CanonInfo | None = None


@dataclass(frozen=True)
class StorePutOptions:
    """Duck-typed options compatible with core FileSystemCAS.put_json."""

    kind: str
    media_type: str
    schema: dict[str, Any] | None = None
    producer: Any = None
    env: Any = None
    inputs: list[dict[str, Any]] | None = None
    canon: dict[str, Any] | None = None


@runtime_checkable
class ArtifactStore(Protocol):
    """Artifact store implementation."""
    def put_json(
        self,
        obj: Any,
        opts: Any,
        canon_spec: CanonSpec | None = None,
    ) -> Any: ...

    def get_bytes(self, artifact_id: Any) -> bytes: ...


def _as_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump(mode="python"))
    return {
        "artifact_id": getattr(value, "artifact_id", value),
        "role": getattr(value, "role", "input"),
    }


def normalize_input_refs(inputs: Sequence[Any] | None) -> list[InputRef]:
    """Normalize input refs helper."""
    if not inputs:
        return []
    normalized: list[InputRef] = []
    for value in inputs:
        payload = _as_payload(value)
        if "artifact_id" in payload:
            payload["artifact_id"] = str(payload["artifact_id"])
        normalized.append(InputRef.model_validate(payload))
    return normalized


def to_store_put_options(opts: PutOptions) -> StorePutOptions:
    """Convert to store put options."""
    schema = opts.schema.model_dump(mode="python") if opts.schema is not None else None
    canon = opts.canon.model_dump(mode="python") if opts.canon is not None else None
    inputs = [entry.model_dump(mode="python") for entry in (opts.inputs or [])] or None
    return StorePutOptions(
        kind=opts.kind,
        media_type=opts.media_type,
        schema=schema,
        producer=opts.producer,
        env=opts.env,
        inputs=inputs,
        canon=canon,
    )


def normalize_artifact_ref(ref: Any) -> dict[str, str]:
    """Normalize artifact ref helper."""
    payload = _as_payload(ref)
    artifact_id = payload.get("artifact_id")
    kind = payload.get("kind")
    media_type = payload.get("media_type")
    if artifact_id is None or kind is None or media_type is None:
        raise ValueError("artifact ref payload must include artifact_id, kind, media_type")
    return {
        "artifact_id": str(artifact_id),
        "kind": str(kind),
        "media_type": str(media_type),
    }


__all__ = [
    "ArtifactID",
    "ArtifactStore",
    "CanonInfo",
    "InputRef",
    "PutOptions",
    "SchemaInfo",
    "StorePutOptions",
    "normalize_artifact_ref",
    "normalize_input_refs",
    "to_store_put_options",
]
