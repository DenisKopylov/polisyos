"""Define component metadata contracts used by discovery, compliance, and registry resolution."""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .capabilities import Capability
from .ids import ComponentId, SemverRange

_BASE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class ComponentKind(str, Enum):
    """Classify a plugin by the host subsystem and ABI family it implements."""

    IR_FRAGMENT = "ir_fragment"
    FOUNDRY_METHOD = "foundry_method"
    FABRIC_CONNECTOR = "fabric_connector"
    SCHOLAR_EXTRACTOR = "scholar_extractor"
    LEX_EXTRACTOR = "lex_extractor"
    LEX_EVALUATOR = "lex_evaluator"
    SCIENTIST_NODE = "scientist_node"
    NORM_PACK_PROVIDER = "norm_pack_provider"


class ComponentDep(BaseModel):
    """Declare a semver dependency on another component base ID and optional kind."""

    model_config = ConfigDict(extra="forbid")

    base_id: str
    version: str
    kind: ComponentKind | None = None

    @field_validator("base_id")
    @classmethod
    def _validate_base_id(cls, value: str) -> str:
        """Normalize and validate `seg(.seg)+` component base IDs."""
        normalized = value.strip()
        if _BASE_ID_RE.fullmatch(normalized) is None:
            raise ValueError("ComponentDep.base_id must match seg(.seg)+")
        return normalized

    @field_validator("version")
    @classmethod
    def _validate_version_range(cls, value: str) -> str:
        """Validate the dependency constraint with `SemverRange.parse`."""
        _ = SemverRange.parse(value)
        return value


class ComponentMetadata(BaseModel):
    """Advertise a component's ABI targets, discovery filters, and dependencies.

    `component_id` and `kind` define the stable registry identity. `abi_targets`
    maps host ABI names such as `ir_abi` or `fabric_connectors_api` to semver
    constraints checked by `validate_metadata`.
    """

    model_config = ConfigDict(extra="forbid")

    component_id: ComponentId
    kind: ComponentKind
    abi_targets: dict[str, str]
    domains: list[str] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    capabilities: Capability
    deps: list[ComponentDep] = Field(default_factory=list)

    display_name: str | None = None
    description: str | None = None
    provides: list[str] = Field(default_factory=list)
