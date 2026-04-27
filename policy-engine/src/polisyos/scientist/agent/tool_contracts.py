"""Read-only promotion checks for Scientist agent tool contracts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.agent.tools.schema import ToolDefinition

if TYPE_CHECKING:
    from polisyos.scientist.agent.tools.registry import ToolRegistry

__all__ = [
    "STRUCTURED_TOOL_ERROR_TYPES",
    "ToolContractIssue",
    "ToolContractSummary",
    "summarize_tool_contracts",
    "tool_contract_default_blockers",
]

STRUCTURED_TOOL_ERROR_TYPES: tuple[str, ...] = (
    "unknown_tool",
    "invalid_arguments",
    "timeout",
    "handler_error",
    "circuit_breaker_open",
)


class ToolContractIssue(BaseModel):
    """One promotion-relevant issue in a tool definition."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)
    issue_code: str = Field(min_length=1)
    severity: Literal["warning", "blocker"] = "blocker"
    message: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolContractSummary(BaseModel):
    """Aggregate readiness summary for a set of agent tools."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    tool_count: int = Field(default=0, ge=0)
    invalid_tool_count: int = Field(default=0, ge=0)
    schema_ready: bool = False
    runtime_caps_ready: bool = False
    structured_error_taxonomy_ready: bool = False
    response_cap_max_chars: int = Field(default=120_000, ge=64)
    issues: list[ToolContractIssue] = Field(default_factory=list)
    error_types: list[str] = Field(default_factory=lambda: list(STRUCTURED_TOOL_ERROR_TYPES))

    @property
    def default_enable_ready(self) -> bool:
        """Return True when tool contracts satisfy default-enable prerequisites."""

        return bool(
            self.tool_count > 0
            and self.schema_ready
            and self.runtime_caps_ready
            and self.structured_error_taxonomy_ready
            and not any(issue.severity == "blocker" for issue in self.issues)
        )


def summarize_tool_contracts(
    tools: Iterable[ToolDefinition] | ToolRegistry,
    *,
    response_cap_max_chars: int = 120_000,
) -> ToolContractSummary:
    """Inspect tool definitions for schema, timeout, response cap, and error readiness."""

    definitions = _definitions_from_tools(tools)
    issues: list[ToolContractIssue] = []
    seen_names: set[str] = set()
    for definition in definitions:
        issues.extend(
            _inspect_definition(
                definition,
                seen_names=seen_names,
                response_cap_max_chars=response_cap_max_chars,
            )
        )
        seen_names.add(definition.name)

    blocker_count = len({issue.tool_name for issue in issues if issue.severity == "blocker"})
    schema_ready = bool(definitions) and not any(
        issue.issue_code.startswith("schema_") and issue.severity == "blocker"
        for issue in issues
    )
    runtime_caps_ready = bool(definitions) and not any(
        issue.issue_code.startswith("runtime_") and issue.severity == "blocker"
        for issue in issues
    )
    structured_error_taxonomy_ready = set(STRUCTURED_TOOL_ERROR_TYPES).issubset(
        {"unknown_tool", "invalid_arguments", "timeout", "handler_error", "circuit_breaker_open"}
    )
    return ToolContractSummary(
        tool_count=len(definitions),
        invalid_tool_count=blocker_count,
        schema_ready=schema_ready,
        runtime_caps_ready=runtime_caps_ready,
        structured_error_taxonomy_ready=structured_error_taxonomy_ready,
        response_cap_max_chars=response_cap_max_chars,
        issues=issues,
    )


def tool_contract_default_blockers(summary: ToolContractSummary | None) -> list[str]:
    """Return promotion blockers implied by a tool-contract summary."""

    if summary is None:
        return ["tool_contract_summary_missing"]
    blockers: list[str] = []
    if summary.tool_count <= 0:
        blockers.append("tool_contracts_empty")
    if not summary.schema_ready:
        blockers.append("tool_schema_not_ready")
    if not summary.runtime_caps_ready:
        blockers.append("tool_runtime_caps_not_ready")
    if not summary.structured_error_taxonomy_ready:
        blockers.append("tool_structured_error_taxonomy_not_ready")
    blockers.extend(
        f"tool_contract_issue:{issue.tool_name}:{issue.issue_code}"
        for issue in summary.issues
        if issue.severity == "blocker"
    )
    return sorted(set(blockers))


def _definitions_from_tools(tools: Iterable[ToolDefinition] | ToolRegistry) -> list[ToolDefinition]:
    list_definitions = getattr(tools, "list_definitions", None)
    if callable(list_definitions):
        return list(list_definitions())
    return list(tools)


def _inspect_definition(
    definition: ToolDefinition,
    *,
    seen_names: set[str],
    response_cap_max_chars: int,
) -> list[ToolContractIssue]:
    issues: list[ToolContractIssue] = []
    schema = definition.parameters
    if definition.name in seen_names:
        issues.append(
            ToolContractIssue(
                tool_name=definition.name,
                issue_code="schema_duplicate_tool_name",
                message="Tool names must be unique within a promotion surface.",
            )
        )
    if not isinstance(schema, dict):
        issues.append(
            ToolContractIssue(
                tool_name=definition.name,
                issue_code="schema_not_mapping",
                message="Tool parameters must be a JSON Schema object.",
            )
        )
        return issues
    if schema.get("type") != "object":
        issues.append(
            ToolContractIssue(
                tool_name=definition.name,
                issue_code="schema_type_not_object",
                message="Tool parameters must use type=object.",
            )
        )
    properties = schema.get("properties")
    if properties is None or not isinstance(properties, dict):
        issues.append(
            ToolContractIssue(
                tool_name=definition.name,
                issue_code="schema_missing_properties",
                message="Tool parameters must define a properties mapping.",
            )
        )
    required = schema.get("required", [])
    if required is not None and not isinstance(required, list):
        issues.append(
            ToolContractIssue(
                tool_name=definition.name,
                issue_code="schema_required_not_list",
                message="Tool required fields must be represented as a list.",
            )
        )
    if schema.get("additionalProperties") is not False:
        issues.append(
            ToolContractIssue(
                tool_name=definition.name,
                issue_code="schema_allows_additional_properties",
                message="Default-eligible tools must reject undeclared arguments.",
            )
        )
    if definition.timeout_s <= 0:
        issues.append(
            ToolContractIssue(
                tool_name=definition.name,
                issue_code="runtime_missing_timeout",
                message="Tool definitions must have a positive timeout.",
            )
        )
    if definition.response_max_chars is None:
        issues.append(
            ToolContractIssue(
                tool_name=definition.name,
                issue_code="runtime_missing_response_cap",
                message="Default-eligible tools must cap rendered tool responses.",
            )
        )
    elif definition.response_max_chars > response_cap_max_chars:
        issues.append(
            ToolContractIssue(
                tool_name=definition.name,
                issue_code="runtime_response_cap_too_large",
                message="Tool response cap exceeds the promotion maximum.",
                metadata={
                    "response_max_chars": definition.response_max_chars,
                    "promotion_max_chars": response_cap_max_chars,
                },
            )
        )
    return issues
