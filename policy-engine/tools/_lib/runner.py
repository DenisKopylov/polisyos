"""Trusted subprocess and tool-dispatch helpers for repo tooling."""

from __future__ import annotations

import importlib
import inspect
import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

_SHELL_CONTROL_SNIPPETS = ("&&", "||", ";", "|", "`", "$(", "<", ">", "\n", "\r")


class ToolStatus(StrEnum):
    """Lifecycle state exposed by the unified tools registry."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class ToolSpec:
    """Metadata contract for a command exposed through ``polisyos-tools``."""

    name: str
    zone: str
    category: str
    module: str
    summary: str = ""
    callable_name: str = "main"
    required_extras: tuple[str, ...] = ()
    required_imports: tuple[str, ...] = ()
    external_dependencies: tuple[str, ...] = ()
    output_formats: tuple[str, ...] = ("text", "json")
    dependencies: tuple[str, ...] = ()
    status: ToolStatus = ToolStatus.ACTIVE
    replacement: str | None = None
    reason: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def qualified_name(self) -> str:
        return f"{self.category}.{self.name}"

    @property
    def deprecated(self) -> bool:
        return self.status in {ToolStatus.DEPRECATED, ToolStatus.QUARANTINED}


class ToolExecutionError(RuntimeError):
    """Raised when a tool cannot be dispatched safely through the registry."""


def parse_trusted_command(
    command: str,
    *,
    allowed_prefixes: Sequence[Sequence[str]] | None = None,
) -> tuple[str, ...]:
    """Parse a fixed command spec and reject shell-control syntax."""

    rendered = str(command or "").strip()
    if not rendered:
        raise ValueError("Command spec must not be empty")
    for snippet in _SHELL_CONTROL_SNIPPETS:
        if snippet in rendered:
            raise ValueError(f"Unsafe shell control token in command spec: {snippet!r}")

    argv = tuple(shlex.split(rendered, posix=True))
    if not argv:
        raise ValueError("Command spec produced an empty argv")
    if allowed_prefixes is not None:
        validate_command_prefix(argv, allowed_prefixes=allowed_prefixes)
    return argv


def validate_command_prefix(
    argv: Sequence[str],
    *,
    allowed_prefixes: Sequence[Sequence[str]],
) -> tuple[str, ...]:
    """Ensure a command starts with one of the explicit allowlisted prefixes."""

    tokens = tuple(str(part) for part in argv)
    if not tokens:
        raise ValueError("Command argv must not be empty")
    for prefix in allowed_prefixes:
        candidate = tuple(str(part) for part in prefix)
        if tokens[: len(candidate)] == candidate:
            return tokens
    allowed = ", ".join(shlex.join(list(prefix)) for prefix in allowed_prefixes)
    raise ValueError(f"Command prefix is not allowlisted: {shlex.join(list(tokens))}; allowed: {allowed}")


def render_command(argv: Sequence[str]) -> str:
    """Render argv for logs."""

    return shlex.join([str(part) for part in argv])


def run_command(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    allowed_prefixes: Sequence[Sequence[str]] | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a subprocess without going through a shell."""

    tokens = tuple(str(part) for part in argv)
    if allowed_prefixes is not None:
        validate_command_prefix(tokens, allowed_prefixes=allowed_prefixes)
    return subprocess.run(list(tokens), cwd=cwd, env=dict(env) if env is not None else None, **kwargs)


def invoke_tool_main(spec: ToolSpec, argv: Sequence[str] | None = None) -> int:
    """Import a registered tool lazily and invoke its entry point.

    New tools should expose ``main(argv: Sequence[str] | None = None) -> int``.
    Legacy tools are still supported by temporarily patching ``sys.argv`` when
    their callable accepts no arguments. That keeps old script paths working
    while the unified CLI provides a normalized public boundary.
    """

    args = [str(part) for part in (argv or ())]
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src"
    for import_root in (repo_root, src_root):
        rendered_root = str(import_root)
        if import_root.exists() and rendered_root not in sys.path:
            sys.path.insert(0, rendered_root)
    try:
        module = importlib.import_module(spec.module)
    except Exception as exc:  # pragma: no cover - exact import failure varies by optional extra.
        raise ToolExecutionError(f"failed to import {spec.module}: {exc}") from exc

    try:
        target = getattr(module, spec.callable_name)
    except AttributeError as exc:
        raise ToolExecutionError(
            f"{spec.module} does not expose callable {spec.callable_name!r}"
        ) from exc

    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        signature = None

    try:
        old_argv = sys.argv
        sys.argv = [f"polisyos-tools {spec.category} {spec.name}", *args]
        try:
            if signature is not None and len(signature.parameters) == 0:
                result = target()
            else:
                result = target(args)
        finally:
            sys.argv = old_argv
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 0 if exc.code is None else 1

    if result is None:
        return 0
    if isinstance(result, int):
        return result
    raise ToolExecutionError(
        f"{spec.qualified_name} returned unsupported result type: {type(result).__name__}"
    )
