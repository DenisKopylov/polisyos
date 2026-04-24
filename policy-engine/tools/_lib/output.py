"""Common output formatters for repository tools."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TextIO

OutputFormat = Literal["text", "json", "sarif", "junit"]
OUTPUT_FORMATS: tuple[OutputFormat, ...] = ("text", "json", "sarif", "junit")


@dataclass(frozen=True)
class ToolMessage:
    """Structured message emitted by a tool boundary."""

    level: str
    message: str
    path: str | None = None
    line: int | None = None
    rule_id: str | None = None


@dataclass(frozen=True)
class ToolResult:
    """Structured execution result used by the unified CLI."""

    tool: str
    status: str
    summary: str = ""
    exit_code: int = 0
    messages: tuple[ToolMessage, ...] = ()
    data: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, tool: str, summary: str = "", **data: Any) -> ToolResult:
        return cls(tool=tool, status="ok", summary=summary, data=data)

    @classmethod
    def failed(cls, tool: str, summary: str, *, exit_code: int = 1, **data: Any) -> ToolResult:
        return cls(tool=tool, status="failed", summary=summary, exit_code=exit_code, data=data)


def _json_default(value: object) -> object:
    if hasattr(value, "__fspath__"):
        return value.__fspath__()  # type: ignore[no-any-return]
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _result_to_dict(result: ToolResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["messages"] = [asdict(message) for message in result.messages]
    payload["data"] = dict(result.data)
    return payload


def _format_text(result: ToolResult) -> str:
    lines = [f"{result.tool}: {result.status}"]
    if result.summary:
        lines.append(result.summary)
    for message in result.messages:
        location = ""
        if message.path:
            location = message.path
            if message.line is not None:
                location += f":{message.line}"
            location += ": "
        lines.append(f"[{message.level}] {location}{message.message}")
    if result.data:
        for key, value in result.data.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def _format_sarif(result: ToolResult) -> str:
    sarif_results: list[dict[str, Any]] = []
    rules: dict[str, dict[str, Any]] = {}
    for idx, message in enumerate(result.messages, start=1):
        rule_id = message.rule_id or f"{result.tool}.{idx}"
        rules.setdefault(rule_id, {"id": rule_id, "name": rule_id})
        sarif_result: dict[str, Any] = {
            "ruleId": rule_id,
            "level": "error" if message.level in {"error", "failed"} else "warning",
            "message": {"text": message.message},
        }
        if message.path:
            region: dict[str, int] = {}
            if message.line is not None:
                region["startLine"] = message.line
            sarif_result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": message.path},
                        "region": region,
                    }
                }
            ]
        sarif_results.append(sarif_result)

    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": result.tool,
                        "informationUri": "https://github.com/polisyos/policy-engine",
                        "rules": list(rules.values()),
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n"


def _format_junit(result: ToolResult) -> str:
    skipped_count = sum(1 for message in result.messages if message.level == "skipped")
    if result.status == "skipped" and skipped_count == 0:
        skipped_count = 1
    testsuite = ET.Element(
        "testsuite",
        {
            "name": result.tool,
            "tests": str(max(len(result.messages), 1)),
            "failures": str(
                sum(1 for message in result.messages if message.level in {"error", "failed"})
            ),
            "errors": "0",
            "skipped": str(skipped_count),
        },
    )
    if not result.messages:
        testcase = ET.SubElement(testsuite, "testcase", {"name": result.summary or result.tool})
        if result.status == "skipped":
            skipped = ET.SubElement(testcase, "skipped", {"message": result.summary or "skipped"})
            skipped.text = result.summary or "skipped"
    for idx, message in enumerate(result.messages, start=1):
        testcase = ET.SubElement(
            testsuite, "testcase", {"name": message.rule_id or f"message-{idx}"}
        )
        if message.level in {"error", "failed"}:
            failure = ET.SubElement(testcase, "failure", {"message": message.message})
            failure.text = message.message
        elif message.level == "skipped":
            skipped = ET.SubElement(testcase, "skipped", {"message": message.message})
            skipped.text = message.message
    return ET.tostring(testsuite, encoding="unicode") + "\n"


def format_tool_result(result: ToolResult, output_format: OutputFormat = "text") -> str:
    if output_format == "text":
        return _format_text(result)
    if output_format == "json":
        return (
            json.dumps(_result_to_dict(result), indent=2, sort_keys=True, default=_json_default)
            + "\n"
        )
    if output_format == "sarif":
        return _format_sarif(result)
    if output_format == "junit":
        return _format_junit(result)
    raise ValueError(f"Unsupported output format: {output_format}")


def write_tool_result(
    result: ToolResult,
    *,
    output_format: OutputFormat = "text",
    stream: TextIO | None = None,
) -> None:
    target = stream or sys.stdout
    target.write(format_tool_result(result, output_format=output_format))


def messages_from_strings(level: str, messages: Sequence[str]) -> tuple[ToolMessage, ...]:
    return tuple(ToolMessage(level=level, message=message) for message in messages)
