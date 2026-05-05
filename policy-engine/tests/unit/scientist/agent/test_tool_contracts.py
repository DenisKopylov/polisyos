from __future__ import annotations

from polisyos.scientist.agent.tool_contracts import (
    summarize_tool_contracts,
    tool_contract_default_blockers,
)
from polisyos.scientist.agent.tools.schema import ToolDefinition


def _tool(
    name: str = "safe_search",
    *,
    additional_properties: bool | None = False,
    response_max_chars: int | None = 4096,
) -> ToolDefinition:
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    if additional_properties is not None:
        schema["additionalProperties"] = additional_properties
    return ToolDefinition(
        name=name,
        description="Search safe sources",
        parameters=schema,
        timeout_s=10.0,
        response_max_chars=response_max_chars,
    )


def test_tool_contract_summary_marks_strict_tools_default_ready() -> None:
    summary = summarize_tool_contracts([_tool()])

    assert summary.default_enable_ready is True
    assert summary.schema_ready is True
    assert summary.runtime_caps_ready is True
    assert summary.structured_error_taxonomy_ready is True
    assert tool_contract_default_blockers(summary) == []


def test_tool_contract_summary_blocks_open_schema_and_missing_response_cap() -> None:
    summary = summarize_tool_contracts(
        [
            _tool(
                additional_properties=True,
                response_max_chars=None,
            )
        ]
    )

    blockers = tool_contract_default_blockers(summary)

    assert summary.default_enable_ready is False
    assert "tool_schema_not_ready" in blockers
    assert "tool_runtime_caps_not_ready" in blockers
    assert any("schema_allows_additional_properties" in blocker for blocker in blockers)
    assert any("runtime_missing_response_cap" in blocker for blocker in blockers)
