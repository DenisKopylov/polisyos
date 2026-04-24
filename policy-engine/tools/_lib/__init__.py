"""Shared helpers for hardened repository tooling."""

from .fs import (
    atomic_replace_path,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    exclusive_lock,
    normalize_filesystem_path,
    write_json_exclusive,
    write_text_exclusive,
)
from .imports import ensure_repo_import_roots, is_type_checking_test, repo_root_from
from .output import OUTPUT_FORMATS, ToolMessage, ToolResult, format_tool_result, write_tool_result
from .preflight import PreflightIssue, PreflightResult, PreflightStatus, run_preflight
from .runner import (
    ToolExecutionError,
    ToolSpec,
    ToolStatus,
    invoke_tool_main,
    parse_trusted_command,
    render_command,
    run_command,
    validate_command_prefix,
)
from .sql import (
    quote_sql_string_literal,
    render_qualified_identifier,
    validate_qualified_sql_identifier,
    validate_sql_identifier,
)
from .timing import (
    ToolRunRecord,
    append_timing_record,
    make_timing_record,
    timed_tool_run,
    timing_log_from_env,
)

__all__ = [
    "OUTPUT_FORMATS",
    "PreflightIssue",
    "PreflightResult",
    "PreflightStatus",
    "ToolExecutionError",
    "ToolMessage",
    "ToolResult",
    "ToolRunRecord",
    "ToolSpec",
    "ToolStatus",
    "append_timing_record",
    "atomic_replace_path",
    "atomic_write_bytes",
    "atomic_write_json",
    "atomic_write_text",
    "ensure_repo_import_roots",
    "exclusive_lock",
    "format_tool_result",
    "invoke_tool_main",
    "is_type_checking_test",
    "make_timing_record",
    "normalize_filesystem_path",
    "parse_trusted_command",
    "quote_sql_string_literal",
    "render_command",
    "render_qualified_identifier",
    "repo_root_from",
    "run_command",
    "run_preflight",
    "timed_tool_run",
    "timing_log_from_env",
    "validate_command_prefix",
    "validate_qualified_sql_identifier",
    "validate_sql_identifier",
    "write_json_exclusive",
    "write_text_exclusive",
    "write_tool_result",
]
