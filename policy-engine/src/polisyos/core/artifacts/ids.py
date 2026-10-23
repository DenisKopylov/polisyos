"""Define the stable `ArtifactID` ABI for CAS-backed content addresses."""

from __future__ import annotations

import builtins as _builtins
import re
from typing import Annotated, Any, ClassVar

from pydantic import ConfigDict, RootModel, WithJsonSchema, field_validator

_SHA256_HEX_RE = re.compile(r"[0-9a-f]{64}")


_ARTIFACT_ID_VALIDATION_SCHEMA_PATTERN = r"^[0-9A-Fa-f]{64}$"
_ARTIFACT_ID_SERIALIZATION_SCHEMA_PATTERN = r"^[0-9a-f]{64}$"


def _add_artifact_id_json_schema_constraints(schema: dict[str, Any], model: type[Any]) -> None:
    """Bind schema-only wire grammar to the owning ArtifactID prefix."""
    schema_pattern = schema.get("pattern")
    if schema_pattern == _ARTIFACT_ID_VALIDATION_SCHEMA_PATTERN:
        hex_pattern = "[0-9A-Fa-f]"
    elif schema_pattern == _ARTIFACT_ID_SERIALIZATION_SCHEMA_PATTERN:
        hex_pattern = "[0-9a-f]"
    else:
        raise ValueError("ArtifactID JSON Schema is missing its typed wire marker")

    prefix = _builtins.str.__str__(model.prefix)
    wire_length = _builtins.len(prefix) + 64
    schema.update(
        {
            "pattern": f"^{re.escape(prefix)}{hex_pattern}{{64}}$",
            "minLength": wire_length,
            "maxLength": wire_length,
        }
    )


class ArtifactID(
    RootModel[
        Annotated[
            str,
            WithJsonSchema(
                {
                    "type": "string",
                    "pattern": _ARTIFACT_ID_VALIDATION_SCHEMA_PATTERN,
                    "minLength": 64,
                    "maxLength": 64,
                },
                mode="validation",
            ),
            WithJsonSchema(
                {
                    "type": "string",
                    "pattern": _ARTIFACT_ID_SERIALIZATION_SCHEMA_PATTERN,
                    "minLength": 64,
                    "maxLength": 64,
                },
                mode="serialization",
            ),
        ]
    ]
):
    """Represent a normalized CAS identifier in `sha256:<64hex>` form.

    The `sha256:` prefix and lowercase 64-hex digest are part of the stable ABI
    used in manifests, runtime URLs, CLI arguments, and signature statements.
    """

    model_config = ConfigDict(json_schema_extra=_add_artifact_id_json_schema_constraints)

    prefix: ClassVar[str] = "sha256:"

    @field_validator("root", mode="before")
    @classmethod
    def validate_root(cls, v: object) -> str:
        """Validate and normalize the serialized artifact identifier.

        Raises:
            TypeError: If the provided value is not a string.
            ValueError: If the value is missing the `sha256:` prefix or digest
                format is invalid.
        """
        if _builtins.isinstance(v, _builtins.str):
            # Validate the native string payload without invoking subclass overrides
            # for __str__, startswith, slicing, or lower.
            v = _builtins.str.__str__(v)
        else:
            # Non-string __str__ callbacks may return a str subclass on Python 3.14.
            # Normalize that result through the exact native descriptor as well.
            v = _builtins.str.__str__(_builtins.str(v))
        prefix = _builtins.str.__str__(cls.prefix)
        if not v.startswith(prefix):
            raise ValueError("ArtifactID must start with sha256:")
        hex64 = v[_builtins.len(prefix) :].lower()
        if not _SHA256_HEX_RE.fullmatch(hex64):
            raise ValueError("sha256 hex must be 64 lowercase characters [0-9a-f]")
        return f"{prefix}{hex64}"

    @classmethod
    def from_sha256_hex(cls, hex64: str) -> ArtifactID:
        """Build an `ArtifactID` from a raw 64-hex digest.

        Args:
            hex64: Lowercase or uppercase SHA-256 digest without the `sha256:`
                prefix.

        Returns:
            A normalized `ArtifactID` with the stable `sha256:` prefix.

        Raises:
            ValueError: If `hex64` is not exactly 64 hexadecimal characters.
        """
        if _builtins.isinstance(hex64, _builtins.str):
            # A string subclass may override lower; normalize through the native
            # descriptor before invoking any string operations.
            hex64 = _builtins.str.__str__(hex64)
        hex64 = hex64.lower()
        if _builtins.isinstance(hex64, _builtins.str):
            # An external lower() method may itself return a str subclass.
            hex64 = _builtins.str.__str__(hex64)
        if not _SHA256_HEX_RE.fullmatch(hex64):
            raise ValueError("sha256 hex must be 64 characters [0-9a-f]")
        prefix = _builtins.str.__str__(cls.prefix)
        return cls(f"{prefix}{hex64}")

    @property
    def algo(self) -> str:
        """Return the digest algorithm prefix encoded in the artifact ID."""
        return self.root.split(":", 1)[0]

    @property
    def hex(self) -> str:
        """Return the normalized 64-hex digest without the `sha256:` prefix.

        Raises:
            ValueError: If the identifier does not use the supported `sha256`
                algorithm or the digest payload is malformed.
        """
        algo, hex64 = self.root.split(":", 1)
        if algo != "sha256":
            raise ValueError(f"Unsupported algo: {algo}")
        if not _SHA256_HEX_RE.fullmatch(hex64):
            raise ValueError("Invalid sha256 hex")
        return hex64

    def __str__(self) -> str:
        """Return the canonical wire representation used by APIs and manifests."""
        return self.root
