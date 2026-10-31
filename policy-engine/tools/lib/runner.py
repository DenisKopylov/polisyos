"""Trusted subprocess and tool-dispatch helpers for repo tooling."""

from __future__ import annotations

import dis
import hashlib
import importlib
import inspect
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import CodeType, FunctionType, ModuleType
from typing import Any, cast

from .fs import _open_absolute_directory, active_secure_output_root

_SHELL_CONTROL_SNIPPETS = ("&&", "||", ";", "|", "`", "$(", "<", ">", "\n", "\r")
_HOST_HANDOFF: FunctionType | None = None
_HOST_HANDOFF_ANCHOR: FunctionType | None = None
_HOST_HANDOFF_GLOBALS: dict[str, object] | None = None


def _passive_host_lookup(mapping: object, name: str) -> object | None:
    """Read an exact string key without calling candidate equality methods."""

    if type(mapping) is not dict:
        return None
    try:
        for key, value in cast("dict[object, object]", mapping).items():
            if type(key) is str and key == name:
                return value
    except RuntimeError:
        return None
    return None


def _same_compiled_value(left: object, right: object) -> bool:
    """Compare compiler values without invoking equality on candidate objects."""

    if type(left) is not type(right):
        return False
    if type(left) is CodeType:
        fields = (
            "co_argcount",
            "co_posonlyargcount",
            "co_kwonlyargcount",
            "co_nlocals",
            "co_stacksize",
            "co_flags",
            "co_code",
            "co_names",
            "co_varnames",
            "co_freevars",
            "co_cellvars",
            "co_name",
            "co_qualname",
            "co_filename",
            "co_firstlineno",
            "co_linetable",
            "co_exceptiontable",
            "co_consts",
        )
        return all(
            _same_compiled_value(getattr(left, field), getattr(right, field)) for field in fields
        )
    if type(left) is tuple:
        if type(right) is not tuple:
            return False
        return len(left) == len(right) and all(
            _same_compiled_value(a, b) for a, b in zip(left, right, strict=True)
        )
    if type(left) is frozenset:
        if type(right) is not frozenset:
            return False
        allowed = (type(None), bool, int, float, complex, str, bytes, tuple, frozenset)
        if any(type(item) not in allowed for item in (*left, *right)):
            return False
        # Compiler-produced frozenset constants contain only recursively safe
        # immutable values; reject any nested unsupported object before equality.
        return all(_same_compiled_value(item, item) for item in (*left, *right)) and left == right
    if type(left) is slice:
        if type(right) is not slice:
            return False
        return all(
            _same_compiled_value(a, b)
            for a, b in zip(
                (left.start, left.stop, left.step),
                (right.start, right.stop, right.step),
                strict=True,
            )
        )
    if type(left) in (type(None), bool, int, float, complex, str, bytes):
        return left == right
    return left is Ellipsis and right is Ellipsis


def _offer_host_handoff() -> None:
    """Offer a late diagnostic handoff only to the selected early-host code.

    The handoff does not establish authority. Direct or counterfeit callers can
    continue candidate work without an authenticated host callback.
    """

    callback = _HOST_HANDOFF
    host = _passive_host_lookup(sys.modules, "_polisyos_early_host")
    session = _passive_host_lookup(sys.__dict__, "_polisyos_loaded_host_v1")
    if (
        type(callback) is not FunctionType
        or callback is not _HOST_HANDOFF_ANCHOR
        or type(host) is not ModuleType
        or type(session) is not dict
        or callback.__globals__ is not host.__dict__
        or _HOST_HANDOFF_GLOBALS is not host.__dict__
        or _passive_host_lookup(host.__dict__, "handoff_if_ready") is not callback
        or _passive_host_lookup(host.__dict__, "_HOST_SESSION") is not session
        or _passive_host_lookup(session, "handoff") is not callback
    ):
        return
    phase = _passive_host_lookup(session, "phase")
    pid = _passive_host_lookup(session, "pid")
    parent_pid = _passive_host_lookup(session, "parent_pid")
    host_code = _passive_host_lookup(session, "host_code")
    expected_sha = _passive_host_lookup(session, "host_sha256")
    if (
        type(phase) is not str
        or phase != "collecting"
        or type(pid) is not int
        or pid != os.getpid()
        or type(parent_pid) is not int
        or parent_pid != os.getppid()
        or type(host_code) is not CodeType
        or host_code is not _passive_host_lookup(host.__dict__, "_HOST_EXECUTION_CODE")
        or type(expected_sha) is not str
    ):
        return
    host_path = Path(__file__).resolve().parents[1] / "authority_bootstrap.py"
    git_env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    git_env.update(
        GIT_OPTIONAL_LOCKS="0",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_NO_REPLACE_OBJECTS="1",
    )
    try:
        source = host_path.read_bytes()
        selected = subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(host_path.parents[2]),
                "show",
                "HEAD:policy-engine/tools/authority_bootstrap.py",
            ],
            env=git_env,
            capture_output=True,
            check=True,
            timeout=30,
        ).stdout
        compiled = compile(source, str(host_path), "exec", dont_inherit=True)
        if (
            source != selected
            or hashlib.sha256(source).hexdigest() != expected_sha
            or not _same_compiled_value(host_code, compiled)
        ):
            return
    except (OSError, SyntaxError, TypeError, ValueError, subprocess.SubprocessError):
        return
    code_tree: list[CodeType] = []
    pending_codes = [host_code]
    while pending_codes:
        code = pending_codes.pop()
        code_tree.append(code)
        pending_codes.extend(item for item in code.co_consts if type(item) is CodeType)
    pending_functions = [("handoff_if_ready", callback)]
    seen: set[int] = set()
    while pending_functions:
        name, function = pending_functions.pop()
        if id(function) in seen:
            continue
        seen.add(id(function))
        matches = [code for code in code_tree if code.co_qualname == name]
        if (
            len(matches) != 1
            or function.__code__ is not matches[0]
            or function.__globals__ is not host.__dict__
        ):
            return
        nested = [function.__code__]
        while nested:
            code = nested.pop()
            for instruction in dis.get_instructions(code):
                if instruction.opname not in {
                    "LOAD_GLOBAL",
                    "LOAD_NAME",
                    "LOAD_FROM_DICT_OR_GLOBALS",
                }:
                    continue
                referenced = instruction.argval
                if type(referenced) is not str:
                    return
                value = _passive_host_lookup(host.__dict__, referenced)
                source_functions = [item for item in code_tree if item.co_qualname == referenced]
                if source_functions:
                    if (
                        len(source_functions) != 1
                        or type(value) is not FunctionType
                        or value.__globals__ is not host.__dict__
                        or value.__code__ is not source_functions[0]
                    ):
                        return
                    pending_functions.append((referenced, value))
            nested.extend(item for item in code.co_consts if type(item) is CodeType)
    callback()


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


class FilesystemWriteBoundaryUnavailableError(RuntimeError):
    """Raised when the host cannot confine a child process to its scratch root."""

    def __init__(self, backend: str, reason: str) -> None:
        super().__init__(reason)
        self.backend = backend
        self.reason = reason


def resolve_external_temporary_base(
    repo_root: Path, *, env: Mapping[str, str] | None = None
) -> Path:
    """Validate the selected temporary base before a caller allocates scratch.

    Explicit TMPDIR/TEMP/TMP values must already be absolute, normalized,
    existing directories without symlink components. When none is supplied,
    POSIX systems use the canonical form of ``/tmp`` without asking
    ``tempfile.gettempdir()`` to probe candidate directories by writing files.

    Args:
        repo_root: The checkout that must remain untouched during setup.
        env: Environment mapping to inspect; defaults to the current environment.

    Returns:
        A canonical temporary base that is neither inside nor above the checkout.

    Raises:
        FilesystemWriteBoundaryUnavailableError: No supported default exists.
        ValueError: The selected base is malformed, non-canonical, or unsafe.
    """
    root = repo_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repo_root must be an existing directory")

    process_env = os.environ if env is None else env
    selected_name = next((name for name in ("TMPDIR", "TEMP", "TMP") if name in process_env), None)
    is_default = selected_name is None
    if is_default:
        if os.name != "posix":
            raise FilesystemWriteBoundaryUnavailableError(
                "temporary-root-unavailable", "no POSIX temporary directory default is available"
            )
        selected = Path("/tmp").resolve(strict=True)
    else:
        raw = process_env[selected_name]
        if not raw or "\x00" in raw:
            raise ValueError(f"{selected_name} must be a non-empty path without NUL bytes")
        candidate = Path(raw)
        if not candidate.is_absolute():
            raise ValueError(f"{selected_name} must be absolute")
        normalized = os.path.normpath(raw)
        if raw not in {normalized, normalized + os.sep}:
            raise ValueError(
                f"{selected_name} must be normalized and must not contain dot segments"
            )
        selected = Path(os.path.abspath(raw))
        if selected != candidate:
            raise ValueError(f"{selected_name} must be a canonical absolute path")

    try:
        descriptor = _open_absolute_directory(selected)
    except OSError as error:
        label = "platform temporary directory" if is_default else selected_name
        raise ValueError(
            f"{label} must be an existing directory without symlink components"
        ) from error
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ValueError("selected temporary base must be a directory")
    finally:
        os.close(descriptor)

    canonical = selected.resolve(strict=True)
    if selected != canonical:
        label = "platform temporary directory" if is_default else selected_name
        raise ValueError(f"{label} must resolve to its canonical path without symlink components")
    if canonical.is_relative_to(root) or root.is_relative_to(canonical):
        raise ValueError("temporary base must be outside and not an ancestor of the checkout")
    return canonical


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
    raise ValueError(
        f"Command prefix is not allowlisted: {shlex.join(list(tokens))}; allowed: {allowed}"
    )


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
    output_root = active_secure_output_root()
    if output_root is None:
        process_env = dict(env) if env is not None else None
        return subprocess.run(list(tokens), cwd=cwd, env=process_env, **kwargs)

    if os.name != "posix":
        raise OSError("secure output scope requires POSIX descriptor inheritance")
    process_env = dict(os.environ) if env is None else dict(env)
    process_env.update(output_root.inherited_scope_environment())
    inherited_fds = set(kwargs.pop("pass_fds", ()))
    inherited_fds.add(output_root.descriptor)
    return subprocess.run(
        list(tokens),
        cwd=cwd,
        env=process_env,
        pass_fds=tuple(sorted(inherited_fds)),
        **kwargs,
    )


def _filesystem_write_boundary_prefix(
    *, repo_root: Path, writable_root: Path
) -> tuple[tuple[str, ...], str]:
    """Return the host-native command prefix that confines filesystem writes."""

    if sys.platform == "darwin":
        executable = shutil.which("sandbox-exec")
        if executable is None:
            raise FilesystemWriteBoundaryUnavailableError(
                "macos-sandbox-exec-unavailable", "sandbox-exec is not installed"
            )
        profile = (
            "(version 1)(deny default)(allow process*)(allow file-read*)"
            '(allow file-write-data (literal "/dev/null"))'
            "(allow sysctl-read)(allow network*)(allow file-write* "
            f"(subpath {json.dumps(str(writable_root))}))"
        )
        return (executable, "-p", profile), "macos-sandbox-exec"

    if sys.platform.startswith("linux"):
        executable = shutil.which("bwrap")
        if executable is None:
            raise FilesystemWriteBoundaryUnavailableError(
                "linux-bubblewrap-unavailable", "bwrap is not installed"
            )
        return (
            executable,
            "--die-with-parent",
            "--new-session",
            "--ro-bind",
            "/",
            "/",
            "--bind",
            str(writable_root),
            str(writable_root),
            "--setenv",
            "TMPDIR",
            str(writable_root),
            "--chdir",
            str(repo_root),
            "--",
        ), "linux-bubblewrap"

    raise FilesystemWriteBoundaryUnavailableError(
        "unsupported-platform", f"no filesystem write fence is defined for {sys.platform}"
    )


def run_with_filesystem_write_boundary(
    argv: Sequence[str],
    *,
    repo_root: Path,
    cwd: Path,
    writable_root: Path,
    env: Mapping[str, str] | None = None,
    timeout: float = 600,
) -> subprocess.CompletedProcess[str]:
    """Run a command with read-only checkout access and one fresh output root.

    Persistent writes are confined to the output root. On macOS, the kernel
    ``/dev/null`` discard sink additionally permits data I/O required by native
    subprocesses; creation, renaming and deletion outside the root stay denied.

    Args:
        argv: Exact child argument vector. Shell syntax is never interpreted.
        repo_root: The checkout whose files must stay read-only for the process tree.
        cwd: Child working directory, which must be inside ``repo_root``.
        writable_root: Empty, canonical directory outside ``repo_root`` for temporary writes.
        env: Optional child environment. ``TMPDIR`` and bytecode writes are constrained here.
        timeout: Maximum child duration in seconds.

    Returns:
        The complete text-mode subprocess result.

    Raises:
        FilesystemWriteBoundaryUnavailableError: The platform lacks a supported OS boundary.
        ValueError: Paths, scratch state, or command arguments violate the write contract.
        subprocess.TimeoutExpired: The child exceeds ``timeout``.
    """

    if not argv:
        raise ValueError("filesystem-confined command must not be empty")
    if timeout <= 0:
        raise ValueError("filesystem-confined command timeout must be positive")
    root = repo_root.resolve(strict=True)
    working_directory = cwd.resolve(strict=True)
    requested_writable = Path(os.path.abspath(writable_root))
    scratch = writable_root.resolve(strict=True)
    if requested_writable != scratch:
        raise ValueError("writable_root must not contain symlink components")
    if not root.is_dir() or not working_directory.is_relative_to(root):
        raise ValueError("cwd must be inside the read-only checkout")
    if not scratch.is_dir():
        raise ValueError("writable_root must be an existing directory")
    if scratch.is_relative_to(root) or root.is_relative_to(scratch):
        raise ValueError("writable_root must be outside the read-only checkout")
    if any(scratch.iterdir()):
        raise ValueError("writable_root must be empty before child launch")
    if active_secure_output_root() is not None:
        raise FilesystemWriteBoundaryUnavailableError(
            "inherited-write-descriptor",
            "an active secure-output descriptor cannot be inherited by a confined child",
        )

    prefix, backend = _filesystem_write_boundary_prefix(repo_root=root, writable_root=scratch)
    process_env = dict(os.environ) if env is None else dict(env)
    process_env["TMPDIR"] = str(scratch)
    process_env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        preflight = run_command(
            [*prefix, sys.executable, "-B", "-c", "pass"],
            cwd=working_directory,
            env=process_env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            close_fds=True,
            timeout=min(timeout, 5),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise FilesystemWriteBoundaryUnavailableError(
            backend, f"backend preflight could not execute: {type(error).__name__}: {error}"
        ) from error
    if preflight.returncode != 0:
        detail = preflight.stderr.strip()[-1000:]
        raise FilesystemWriteBoundaryUnavailableError(
            backend, f"backend preflight failed (exit={preflight.returncode}): {detail}"
        )
    return run_command(
        [*prefix, *(str(item) for item in argv)],
        cwd=working_directory,
        env=process_env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        close_fds=True,
        timeout=timeout,
    )


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
    _offer_host_handoff()

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
