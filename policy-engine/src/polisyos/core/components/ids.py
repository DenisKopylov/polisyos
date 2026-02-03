from __future__ import annotations

import re
from typing import ClassVar

from pydantic import RootModel, field_validator

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
_COMPONENT_ID_RE = re.compile(
    rf"^(?P<namespace>[a-z][a-z0-9_]*)\.(?P<name>[a-z][a-z0-9_]*)@(?P<version>{_SEMVER_RE.pattern})$"
)


class ComponentId(RootModel[str]):
    """Component identifier: namespace.name@semver."""

    pattern: ClassVar[re.Pattern[str]] = _COMPONENT_ID_RE

    @field_validator("root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("ComponentId must be a string")
        if not cls.pattern.match(value):
            raise ValueError("ComponentId must match namespace.name@semver")
        return value

    @classmethod
    def parse(cls, value: str) -> "ComponentId":
        return cls(value)

    @property
    def namespace(self) -> str:
        match = self.pattern.match(self.root)
        if not match:
            raise ValueError("Invalid ComponentId")
        return match.group("namespace")

    @property
    def name(self) -> str:
        match = self.pattern.match(self.root)
        if not match:
            raise ValueError("Invalid ComponentId")
        return match.group("name")

    @property
    def version(self) -> str:
        match = self.pattern.match(self.root)
        if not match:
            raise ValueError("Invalid ComponentId")
        return match.group("version")

    def __str__(self) -> str:
        return self.root
