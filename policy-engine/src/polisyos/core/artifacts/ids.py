from __future__ import annotations

import re
from typing import ClassVar

from pydantic import RootModel, field_validator

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class ArtifactID(RootModel[str]):
    """Format: sha256:<64hex>"""

    prefix: ClassVar[str] = "sha256:"

    @field_validator("root")
    @classmethod
    def validate_root(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError("ArtifactID must be a string")
        if not v.startswith(cls.prefix):
            raise ValueError("ArtifactID must start with sha256:")
        hex64 = v[len(cls.prefix) :].lower()
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
    def algo(self) -> str:
        return self.root.split(":", 1)[0]

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
