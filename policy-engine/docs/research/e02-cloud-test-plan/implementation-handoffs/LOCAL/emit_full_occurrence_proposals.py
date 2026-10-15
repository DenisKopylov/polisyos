#!/usr/bin/env python3
"""R7 dual-plane source-read-closed prototype for the E02 full-occurrence report.

This virtual companion composes the existing R3 report builder, R1 fixture
producer, R2 whole-object consumer, and canonical proposal emitter. It derives
the source set from file opens during the complete build and consumer controls;
it does not claim candidate execution, semantic alignment, or formal closure.
"""

from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import inspect
import json
import marshal
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar


def _git_executable() -> str:
    """Resolve Git once per process without relying on a partial PATH command."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is not available on PATH")
    return str(Path(executable).resolve(strict=True))


LOCAL = Path("policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL")
R3_COMPANION = (
    LOCAL / "raw/q0-full-report-registration-author-r3-20261012/registration-companion.py"
)
R7_DIR = LOCAL / "raw/q0-full-report-registration-author-r7-20261012"
DEFAULT_REPORT = R7_DIR / "generated-full-report-r7.json"
DEFAULT_CONTROLS = R7_DIR / "generated-consumer-controls-r7.json"
TRACE_PATH = R7_DIR / "runtime-read-trace-r7.json"
MANIFEST_PATH = R7_DIR / "source-read-closure-r7.json"
PACKET_PATH = R7_DIR / "source-closure-packet-r7.json"
CHECK_PATH = R7_DIR / "checks/source-closure-check-r7.json"
PROPOSED_REGISTERED_TOOL = LOCAL / "emit_full_occurrence_proposals.py"


class ReadClosureError(ValueError):
    """Raised when runtime reads and their source bindings do not agree."""


def stable_json(value: object) -> bytes:
    """Return deterministic, human-readable JSON bytes."""
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256(raw: bytes) -> str:
    """Hash exact bytes with SHA-256."""
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    """Raise a fail-closed error when a source-binding invariant is false."""
    if not condition:
        raise ReadClosureError(message)


def repo_root() -> Path:
    """Locate the product checkout from this companion's path."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "policy-engine").is_dir():
            return parent
    raise ReadClosureError("repository root not found")


def _run_git(
    root: Path, *args: str, text: bool = False
) -> subprocess.CompletedProcess[str | bytes]:
    """Run an allowlisted read-only Git query without a shell."""
    readonly_commands = {"--version", "ls-tree", "cat-file", "rev-parse", "merge-base"}
    command = args[1] if args[:1] == ("--literal-pathspecs",) and len(args) > 1 else args[0]
    if command not in readonly_commands or any("\0" in arg for arg in args):
        raise ReadClosureError("Git helper accepts only NUL-free, read-only query arguments")
    # S603: the executable is resolved absolutely and the command family above is read-only.
    return subprocess.run(  # noqa: S603
        [_git_executable(), *args],
        cwd=root,
        text=text,
        capture_output=True,
        check=False,
        shell=False,
    )


def git(root: Path, *args: str) -> str:
    """Run a read-only Git query and preserve its failure details."""
    result = _run_git(root, *args, text=True)
    if result.returncode:
        raise ReadClosureError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def source_import(name: str, path: Path) -> object:
    """Import repository code from source bytes without Python bytecode caches."""
    raw = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path.resolve())
    module.__package__ = name.rpartition(".")[0]
    sys.modules[name] = module
    # S102: execute the exact source bytes that the read trace is meant to observe.
    exec(compile(raw, module.__file__, "exec"), module.__dict__)  # noqa: S102
    return module


class RuntimeReadTrace:
    """Capture repository opens and completed child-process results during one build."""

    _WRITE_BITS = (
        getattr(os, "O_WRONLY", 1)
        | getattr(os, "O_RDWR", 2)
        | getattr(os, "O_CREAT", 0)
        | getattr(os, "O_TRUNC", 0)
        | getattr(os, "O_APPEND", 0)
    )
    _PROCESS_EVENTS: ClassVar[frozenset[str]] = frozenset(
        {"os.system", "os.exec", "os.posix_spawn", "os.spawn"}
    )

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.stdlib_root = Path(sysconfig.get_paths().get("stdlib", "/nonexistent")).resolve()
        self.modules_before_trace = frozenset(sys.modules)
        self.events: collections.Counter[tuple[str, str]] = collections.Counter()
        self.reads: dict[str, dict[str, Any]] = {}
        self.writes: dict[str, dict[str, Any]] = {}
        self.directories: dict[str, int] = {}
        self.external: dict[str, dict[str, Any]] = {}
        self.nonregular_reads: dict[str, dict[str, Any]] = {}
        self.missing_open_attempts: dict[str, dict[str, Any]] = {}
        self.symlink_reads: set[str] = set()
        self.unbound_symlinks: list[dict[str, Any]] = []
        self.process_results: dict[str, dict[str, Any]] = {}
        self.audit_process_event_count = 0
        self.unsupported_process_events: list[dict[str, Any]] = []
        self.audit_errors: list[dict[str, Any]] = []
        self._hook = self._audit
        self._original_popen = None
        self._original_popen_signature: inspect.Signature | None = None
        self._original_os_open = None
        self._original_os_write = None
        self._pending_osopen_path: Path | None = None
        self._stdin_fd_owners: dict[int, Any] = {}
        self._enabled = False

    @staticmethod
    def _mode_is_write(mode: object, flags: object) -> bool:
        if isinstance(mode, str) and any(char in mode for char in "wax+"):
            return True
        return isinstance(flags, int) and bool(flags & RuntimeReadTrace._WRITE_BITS)

    def _callsite(self) -> dict[str, Any]:
        frame = sys._getframe(2)
        fallback: dict[str, Any] | None = None
        while frame:
            filename = frame.f_code.co_filename
            try:
                relative = Path(filename).resolve().relative_to(self.root).as_posix()
            except (OSError, ValueError):
                relative = None
            item = {
                "path": relative or filename,
                "line": frame.f_lineno,
                "function": frame.f_code.co_name,
            }
            if fallback is None:
                fallback = item
            if relative is not None and not relative.startswith(
                "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/q0-full-report-registration-author-r7-20261012/"
            ):
                return item
            frame = frame.f_back
        return fallback or {"path": "<unknown>", "line": 0, "function": "<unknown>"}

    def _path(self, value: object) -> Path | None:
        if not isinstance(value, (str, bytes, os.PathLike)):
            return None
        try:
            candidate = Path(os.fsdecode(value))
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
            return Path(os.path.abspath(candidate))
        except (OSError, TypeError, ValueError):
            return None

    def _relative(self, path: Path) -> str | None:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return None

    def _audit(self, event: str, args: tuple[Any, ...]) -> None:
        if not self._enabled:
            return
        try:
            self._audit_impl(event, args)
        except BaseException as exc:
            self.audit_errors.append(
                {"event": event, "error_type": type(exc).__name__, "callsite": self._callsite()}
            )

    def _audit_impl(self, event: str, args: tuple[Any, ...]) -> None:
        if event == "subprocess.Popen":
            self.audit_process_event_count += 1
            return
        if event in self._PROCESS_EVENTS:
            self.unsupported_process_events.append({"event": event, "callsite": self._callsite()})
            return
        if event == "os.symlink" and len(args) >= 2:
            candidate = self._path(args[1])
            if candidate is not None:
                relative = self._relative(candidate)
                if relative is not None:
                    item = self.writes.setdefault(
                        relative, {"first_callsite": self._callsite(), "opens": 0}
                    )
                    item["kind"] = "symlink_created_during_run"
                    item["target_argument_sha256"] = sha256(os.fsencode(args[0]))
            return
        if event != "open" or not args:
            return
        candidate = self._pending_osopen_path or self._path(args[0])
        if candidate is None:
            return
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else None
        write = self._mode_is_write(mode, flags)
        callsite = self._callsite()
        lexical_rel = self._relative(candidate)
        if lexical_rel is None:
            try:
                is_runtime = candidate.resolve(strict=False).is_relative_to(self.stdlib_root)
            except (OSError, ValueError):
                is_runtime = False
            category = "python_runtime" if is_runtime else "external_or_temporary"
            key = f"{category}:{candidate.name}"
            item = self.external.setdefault(
                key,
                {
                    "category": category,
                    "basename": candidate.name,
                    "first_callsite": callsite,
                    "read_opens": 0,
                    "write_opens": 0,
                },
            )
            item["write_opens" if write else "read_opens"] += 1
            self.events[(category, "write" if write else "read")] += 1
            return
        if lexical_rel == ".git" or lexical_rel.startswith(".git/"):
            self.events[("git_metadata", "write" if write else "read")] += 1
            return
        try:
            info = candidate.lstat()
        except OSError:
            info = None
        if info is not None and stat.S_ISDIR(info.st_mode):
            self.directories[lexical_rel] = self.directories.get(lexical_rel, 0) + 1
            self.events[("repository_directory", "write" if write else "read")] += 1
            return
        if write:
            item = self.writes.setdefault(lexical_rel, {"first_callsite": callsite, "opens": 0})
            item["opens"] += 1
            self.events[("repository_file", "write")] += 1
            return
        if info is not None and stat.S_ISLNK(info.st_mode):
            target_text = os.readlink(candidate)
            item = self.reads.setdefault(
                lexical_rel,
                {
                    "first_callsite": callsite,
                    "read_opens": 0,
                    "filesystem_kind": "symlink",
                    "symlink_target": target_text,
                },
            )
            item["read_opens"] += 1
            self.symlink_reads.add(lexical_rel)
            self.events[("repository_symlink", "read")] += 1
            try:
                resolved = candidate.resolve(strict=True)
                target_rel = self._relative(resolved)
            except (OSError, ValueError) as exc:
                target_rel = None
                self.unbound_symlinks.append(
                    {
                        "path": lexical_rel,
                        "target": target_text,
                        "error_type": type(exc).__name__,
                        "callsite": callsite,
                    }
                )
            if target_rel is not None and target_rel != lexical_rel:
                row = self.reads.setdefault(
                    target_rel,
                    {
                        "first_callsite": callsite,
                        "read_opens": 0,
                        "symlink_target_for": lexical_rel,
                    },
                )
                row["read_opens"] += 1
            return
        if info is None:
            item = self.missing_open_attempts.setdefault(
                lexical_rel, {"first_callsite": callsite, "attempts": 0}
            )
            item["attempts"] += 1
            self.events[("repository_open_attempt", "missing_at_observation")] += 1
            return
        if not stat.S_ISREG(info.st_mode):
            item = self.nonregular_reads.setdefault(
                lexical_rel,
                {"first_callsite": callsite, "opens": 0, "mode": stat.S_IFMT(info.st_mode)},
            )
            item["opens"] += 1
            self.events[("repository_nonregular", "read")] += 1
            return
        item = self.reads.setdefault(
            lexical_rel, {"first_callsite": callsite, "read_opens": 0, "filesystem_kind": "regular"}
        )
        item["read_opens"] += 1
        self.events[("repository_file", "read")] += 1

    @staticmethod
    def _normalize_text(value: str) -> str:
        value = re.sub(
            r"\.ignored-raw-parent-symlink-self-check-[^/]+",
            "<parent-symlink-self-check-temp>",
            value,
        )
        value = re.sub(
            r"\.ignored-raw-symlink-self-check-[^/]+", "<symlink-self-check-temp>", value
        )
        return value

    def _normalize_command(self, value: object) -> str:
        text = os.fsdecode(value)
        candidate = Path(text)
        if candidate.is_absolute():
            relative = self._relative(candidate)
            if relative is not None:
                return relative
        return self._normalize_text(text)

    def _descriptor_origin(self, descriptor: int) -> dict[str, Any]:
        """Describe a constructor-supplied stdin descriptor without claiming its bytes."""
        try:
            info = os.fstat(descriptor)
            identity: dict[str, Any] = {
                "descriptor_kind": stat.S_IFMT(info.st_mode),
                "mode_octal": f"{stat.S_IMODE(info.st_mode):04o}",
                "device": info.st_dev,
                "inode": info.st_ino,
                "size_at_launch": info.st_size if stat.S_ISREG(info.st_mode) else None,
            }
        except (OSError, TypeError, ValueError) as exc:
            return {"descriptor_identity": None, "resolution": f"unavailable:{type(exc).__name__}"}
        path: str | None = None
        try:
            if sys.platform == "darwin":
                import fcntl

                raw = fcntl.fcntl(descriptor, fcntl.F_GETPATH, b"\0" * 1023)
                path = raw.split(b"\0", 1)[0].decode("utf-8", errors="surrogateescape")
            else:
                for proc_path in (
                    Path(f"/proc/self/fd/{descriptor}"),
                    Path(f"/dev/fd/{descriptor}"),
                ):
                    try:
                        path = os.readlink(proc_path)
                        break
                    except OSError:
                        continue
        except (OSError, ImportError, ValueError):
            path = None
        if path is not None:
            candidate = Path(path)
            relative = self._relative(
                candidate if candidate.is_absolute() else Path.cwd() / candidate
            )
            identity["path"] = relative or "<outside-repository>"
        else:
            identity["path"] = None
        return {
            "descriptor_identity": identity,
            "resolution": "metadata_only_consumed_bytes_unobserved",
        }

    def _stdin_constructor(
        self,
        value: object,
        *,
        provided: bool,
        form: str,
        sealed_omission: bool,
    ) -> dict[str, Any]:
        """Classify effective stdin after binding against the captured real Popen signature."""
        if sealed_omission:
            return {
                "argument": "omitted_default_sealed",
                "source_argument_presence": "omitted",
                "argument_form": "omitted_default",
                "effective_value": "DEVNULL",
                "seal_action": "omitted_default_replaced_with_DEVNULL",
                "origin": "known_empty_device",
                "bytes_binding": "no_child_source_bytes",
            }
        if not provided:
            return {
                "argument": "unbound_signature_default",
                "source_argument_presence": "not_established",
                "argument_form": "unknown",
                "origin": "unclassified_constructor_stdin",
                "bytes_binding": "not_established",
            }
        if value is None:
            return {
                "argument": "explicit_none",
                "source_argument_presence": "explicit",
                "argument_form": form,
                "effective_value": "None",
                "origin": "inherited_parent_stdin",
                "bytes_binding": "unobserved_external_stream",
            }
        if isinstance(value, int) and value == subprocess.PIPE:
            return {
                "argument": "stdin_pipe",
                "source_argument_presence": "explicit",
                "argument_form": form,
                "effective_value": "PIPE",
                "origin": "managed_pipe",
                "bytes_binding": "communicate_or_stream_observation",
            }
        if isinstance(value, int) and value == subprocess.DEVNULL:
            return {
                "argument": "explicit_devnull",
                "source_argument_presence": "explicit",
                "argument_form": form,
                "effective_value": "DEVNULL",
                "origin": "known_empty_device",
                "bytes_binding": "no_child_source_bytes",
            }
        if isinstance(value, int) and value == subprocess.STDOUT:
            return {
                "argument": "stdout_alias",
                "source_argument_presence": "explicit",
                "argument_form": form,
                "origin": "invalid_or_runtime_rejected",
                "bytes_binding": "not_established",
            }
        if isinstance(value, int):
            return {
                "argument": "integer_descriptor",
                "source_argument_presence": "explicit",
                "argument_form": form,
                "origin": "inherited_descriptor",
                "descriptor_number": value,
                **self._descriptor_origin(value),
            }
        fileno = getattr(value, "fileno", None)
        if callable(fileno):
            try:
                descriptor = int(fileno())
            except (OSError, TypeError, ValueError) as exc:
                return {
                    "argument": "file_object",
                    "source_argument_presence": "explicit",
                    "argument_form": form,
                    "origin": "file_object_unresolved",
                    "name": self._normalize_text(os.fspath(value.name))
                    if isinstance(getattr(value, "name", None), (str, bytes, os.PathLike))
                    else None,
                    "descriptor_error": type(exc).__name__,
                    "bytes_binding": "unobserved_external_stream",
                }
            name = getattr(value, "name", None)
            if isinstance(name, (str, bytes, os.PathLike)):
                name_text = os.fsdecode(name)
                name_path = Path(name_text)
                if name_path.is_absolute():
                    name_text = self._relative(name_path) or "<outside-repository>"
                else:
                    name_text = self._normalize_text(name_text)
            else:
                name_text = None
            return {
                "argument": "file_object",
                "source_argument_presence": "explicit",
                "argument_form": form,
                "origin": "file_object_descriptor",
                "name": name_text,
                "descriptor_number": descriptor,
                **self._descriptor_origin(descriptor),
            }
        return {
            "argument": f"unsupported:{type(value).__name__}",
            "source_argument_presence": "explicit",
            "argument_form": form,
            "origin": "unclassified_constructor_stdin",
            "bytes_binding": "not_established",
        }

    def _invocation_value(self, name: str, value: object) -> tuple[dict[str, object], bool]:
        """Return a content-safe canonical description of one effective Popen parameter."""
        if value is None:
            return {"kind": "none"}, True
        if isinstance(value, bool):
            return {"kind": "bool", "value": value}, True
        if isinstance(value, int):
            return {"kind": "int", "value": value}, True
        if isinstance(value, float):
            return {"kind": "float", "value": value.hex()}, True
        if isinstance(value, str):
            return {"kind": "str", "value": value}, True
        if isinstance(value, bytes):
            return {"kind": "bytes", "length": len(value), "sha256": sha256(value)}, True
        if isinstance(value, os.PathLike):
            return {"kind": "path", "value": self._normalize_command(os.fspath(value))}, True
        if isinstance(value, Mapping):
            if name == "env":
                entries = sorted(
                    (str(key), sha256(os.fsencode(item))) for key, item in value.items()
                )
                return {
                    "kind": "environment_mapping",
                    "entries": len(entries),
                    "sha256": sha256(stable_json(entries)),
                }, True
            entries = sorted(
                (str(key), self._invocation_value(str(key), item)[0]) for key, item in value.items()
            )
            return {
                "kind": "mapping",
                "entries": len(entries),
                "sha256": sha256(stable_json(entries)),
            }, True
        if isinstance(value, (list, tuple)):
            children = [self._invocation_value(name, item)[0] for item in value]
            return {
                "kind": type(value).__name__,
                "items": len(children),
                "sha256": sha256(stable_json(children)),
            }, True
        if isinstance(value, (set, frozenset)):
            children = [self._invocation_value(name, item)[0] for item in value]
            children.sort(key=stable_json)
            return {
                "kind": type(value).__name__,
                "items": len(children),
                "sha256": sha256(stable_json(children)),
            }, True
        if callable(value):
            code = getattr(value, "__code__", None)
            closure = getattr(value, "__closure__", None)
            if code is None:
                return {
                    "kind": "callable",
                    "type": f"{type(value).__module__}.{type(value).__qualname__}",
                    "complete": False,
                }, False
            code_hash = sha256(marshal.dumps(code))
            complete = not closure
            return {
                "kind": "callable",
                "module": getattr(value, "__module__", None),
                "qualname": getattr(value, "__qualname__", None),
                "code_sha256": code_hash,
                "closure_cells": len(closure or ()),
                "complete": complete,
            }, complete
        fileno = getattr(value, "fileno", None)
        if callable(fileno):
            try:
                descriptor = int(fileno())
            except (OSError, TypeError, ValueError) as exc:
                return {
                    "kind": "file_object",
                    "type": f"{type(value).__module__}.{type(value).__qualname__}",
                    "resolution": type(exc).__name__,
                }, False
            return {
                "kind": "file_object",
                "type": f"{type(value).__module__}.{type(value).__qualname__}",
                **self._descriptor_origin(descriptor),
            }, True
        return {
            "kind": "opaque",
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
        }, False

    def _popen_binding(
        self,
        original: object,
        instance: object,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        "Bind against the captured real Popen signature, then seal only an omitted stdin default."
        if original is not self._original_popen:
            return {
                "status": "unbound",
                "error": "constructor_is_not_captured_real_popen",
                "call_kwargs": kwargs,
            }
        signature = self._original_popen_signature
        if signature is None:
            return {
                "status": "unbound",
                "error": "captured_real_popen_signature_unavailable",
                "call_kwargs": kwargs,
            }
        try:
            bound = signature.bind(instance, *args, **kwargs)
        except TypeError as exc:
            return {
                "status": "unbound",
                "error": f"signature_bind:{type(exc).__name__}",
                "call_kwargs": kwargs,
            }
        explicit = set(bound.arguments) - {"self"}
        forms: dict[str, str] = {}
        positional_names = [
            parameter.name
            for parameter in signature.parameters.values()
            if parameter.name != "self"
            and parameter.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
        ]
        for index, name in enumerate(positional_names):
            if index < len(args):
                forms[name] = "positional"
            elif name in kwargs:
                forms[name] = "keyword"
            else:
                forms[name] = "omitted_default"
        for parameter in signature.parameters.values():
            if parameter.name == "self" or parameter.kind not in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }:
                forms[parameter.name] = "keyword" if parameter.name in kwargs else "omitted_default"
        bound.apply_defaults()
        effective = {name: value for name, value in bound.arguments.items() if name != "self"}
        stdin_provided = "stdin" in explicit
        sealed_omission = not stdin_provided
        call_kwargs = dict(kwargs)
        if sealed_omission:
            if "stdin" not in signature.parameters or forms.get("stdin") != "omitted_default":
                return {
                    "status": "unbound",
                    "error": "cannot_safely_seal_signature_stdin_default",
                    "call_kwargs": kwargs,
                }
            effective["stdin"] = subprocess.DEVNULL
            call_kwargs["stdin"] = subprocess.DEVNULL
        parameter_bindings: dict[str, Any] = {}
        unsupported: list[str] = []
        for name, value in effective.items():
            if name == "stdin":
                description = self._stdin_constructor(
                    value,
                    provided=stdin_provided,
                    form=forms.get(name, "unknown"),
                    sealed_omission=sealed_omission,
                )
                complete = description.get("origin") not in {
                    "unclassified_constructor_stdin",
                    "file_object_unresolved",
                    "invalid_or_runtime_rejected",
                }
                kind = "stdin_origin"
            elif name in {"stdout", "stderr"} and isinstance(value, int):
                description = {
                    "kind": "stream_constant",
                    "value": {
                        0: "STDIN",
                        1: "STDOUT",
                        2: "STDERR",
                        subprocess.PIPE: "PIPE",
                        subprocess.DEVNULL: "DEVNULL",
                        subprocess.STDOUT: "STDOUT",
                    }.get(value, "descriptor"),
                    "descriptor": value
                    if value not in {subprocess.PIPE, subprocess.DEVNULL, subprocess.STDOUT}
                    else None,
                }
                if description["value"] == "descriptor":
                    description.update(self._descriptor_origin(value))
                complete, kind = True, "stream_destination"
            elif name == "env" and value is None:
                inherited = sorted(
                    (key, sha256(os.fsencode(item))) for key, item in os.environ.items()
                )
                description = {
                    "kind": "inherited_environment",
                    "entries": len(inherited),
                    "sha256": sha256(stable_json(inherited)),
                }
                complete, kind = True, "environment"
            else:
                description, complete = self._invocation_value(name, value)
                kind = description.get("kind", "unknown")
            if not complete:
                unsupported.append(name)
            parameter_bindings[name] = {
                "argument_form": forms.get(
                    name, "keyword" if name in explicit else "omitted_default"
                ),
                "explicit": name in explicit,
                "kind": kind,
                "value_sha256": sha256(stable_json(description)),
                "complete": complete,
            }
        signature_text = str(signature)
        return {
            "status": "bound",
            "signature": signature_text,
            "signature_sha256": sha256(signature_text.encode("utf-8")),
            "signature_parameters": [name for name in signature.parameters if name != "self"],
            "explicit_parameters": sorted(explicit),
            "stdin_argument_form": forms.get("stdin", "unavailable"),
            "stdin_was_omitted": not stdin_provided,
            "stdin_default_sealed": sealed_omission,
            "effective_parameter_bindings": parameter_bindings,
            "unsupported_parameter_bindings": sorted(unsupported),
            "call_kwargs": call_kwargs,
            "effective": effective,
        }

    def _communicate_input(
        self, value: object, *, provided: bool, stream: object, text_mode: bool
    ) -> dict[str, Any]:
        """Bind exact bytes supplied through communicate(input=...), without retaining them."""
        if not provided:
            return {
                "argument_presence": "omitted",
                "python_type": None,
                "capture": "no_argument",
                "bytes": None,
                "sha256": None,
            }
        if value is None:
            return {
                "argument_presence": "explicit",
                "python_type": "NoneType",
                "capture": "explicit_none",
                "bytes": None,
                "sha256": None,
            }
        if isinstance(value, str):
            if not text_mode or stream is None:
                return {
                    "argument_presence": "explicit",
                    "python_type": "str",
                    "capture": "unsupported_text_without_text_pipe",
                    "bytes": None,
                    "sha256": None,
                }
            encoding = getattr(stream, "encoding", None)
            errors = getattr(stream, "errors", None)
            if not encoding:
                return {
                    "argument_presence": "explicit",
                    "python_type": "str",
                    "capture": "unsupported_missing_encoding",
                    "encoding": encoding,
                    "errors": errors,
                    "bytes": None,
                    "sha256": None,
                }
            try:
                raw = value.encode(encoding, errors or "strict")
            except (LookupError, UnicodeError) as exc:
                return {
                    "argument_presence": "explicit",
                    "python_type": "str",
                    "capture": f"encoding_error:{type(exc).__name__}",
                    "encoding": encoding,
                    "errors": errors,
                    "bytes": None,
                    "sha256": None,
                }
            return {
                "argument_presence": "explicit",
                "python_type": "str",
                "capture": "text_encoded_as_subprocess_input",
                "encoding": encoding,
                "errors": errors or "strict",
                "bytes": len(raw),
                "sha256": sha256(raw),
            }
        if isinstance(value, bytes):
            raw = value
            python_type = "bytes"
        elif isinstance(value, bytearray):
            raw = bytes(value)
            python_type = "bytearray"
        elif isinstance(value, memoryview):
            raw = value.tobytes()
            python_type = "memoryview"
        else:
            return {
                "argument_presence": "explicit",
                "python_type": type(value).__name__,
                "capture": "unsupported_input_type",
                "bytes": None,
                "sha256": None,
            }
        return {
            "argument_presence": "explicit",
            "python_type": python_type,
            "capture": "exact_argument_bytes",
            "bytes": len(raw),
            "sha256": sha256(raw),
        }

    def _stream_write(self, stream: object, value: object) -> dict[str, object]:
        """Summarize a direct Popen.stdin.write argument before it reaches the pipe."""
        if isinstance(value, bytes):
            raw, python_type, capture = value, "bytes", "exact_argument_bytes"
        elif isinstance(value, bytearray):
            raw, python_type, capture = bytes(value), "bytearray", "exact_argument_bytes"
        elif isinstance(value, memoryview):
            raw, python_type, capture = value.tobytes(), "memoryview", "exact_argument_bytes"
        elif isinstance(value, str):
            encoding = getattr(stream, "encoding", None)
            errors = getattr(stream, "errors", None)
            if not encoding:
                return {
                    "python_type": "str",
                    "capture": "unsupported_missing_encoding",
                    "bytes": None,
                    "sha256": None,
                }
            try:
                raw = value.encode(encoding, errors or "strict")
            except (LookupError, UnicodeError) as exc:
                return {
                    "python_type": "str",
                    "capture": f"encoding_error:{type(exc).__name__}",
                    "bytes": None,
                    "sha256": None,
                }
            python_type, capture = "str", "encoded_argument_newline_translation_not_observed"
        else:
            return {
                "python_type": type(value).__name__,
                "capture": "unsupported_stream_write_type",
                "bytes": None,
                "sha256": None,
            }
        return {
            "python_type": python_type,
            "capture": capture,
            "bytes": len(raw),
            "sha256": sha256(raw),
            "encoding": getattr(stream, "encoding", None) if isinstance(value, str) else None,
            "errors": getattr(stream, "errors", None) if isinstance(value, str) else None,
        }

    def _process_context(
        self,
        binding: dict[str, Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """Project process fields from the captured real Popen signature binding."""
        if binding.get("status") == "bound":
            effective = binding["effective"]
            provided = "stdin" in binding["explicit_parameters"]
            constructor = self._stdin_constructor(
                effective.get("stdin"),
                provided=provided,
                form=binding.get("stdin_argument_form", "unknown"),
                sealed_omission=bool(binding.get("stdin_default_sealed")),
            )
            invocation = {
                key: value
                for key, value in binding.items()
                if key not in {"call_kwargs", "effective"}
            }
        else:
            effective = {
                "args": args[0] if args else kwargs.get("args", "<unknown>"),
                **kwargs,
            }
            constructor = self._stdin_constructor(
                None, provided=False, form="unknown", sealed_omission=False
            )
            invocation = {
                key: value
                for key, value in binding.items()
                if key not in {"call_kwargs", "effective"}
            }
        command = effective.get("args", "<unknown>")
        argv = (
            [self._normalize_command(value) for value in command]
            if isinstance(command, (list, tuple))
            else [self._normalize_command(command)]
        )
        cwd = effective.get("cwd")
        cwd_path = Path.cwd() if cwd is None else self._path(cwd)
        cwd_rel = None if cwd_path is None else self._relative(cwd_path)
        env = effective.get("env")
        effective_env = os.environ if env is None else env
        git_environment = {
            key: {
                "value_sha256": sha256(os.fsencode(value)),
                "value": value
                if key in {"GIT_PAGER", "GIT_NO_REPLACE_OBJECTS", "GIT_CONFIG_NOSYSTEM"}
                else None,
            }
            for key, value in sorted(effective_env.items())
            if key.startswith("GIT_")
        }
        return {
            "argv": argv,
            "cwd": cwd_rel if cwd_rel is not None else "<outside-repository>",
            "shell": bool(effective.get("shell", False)),
            "git_environment": git_environment,
            "stdout_is_pipe": effective.get("stdout") == subprocess.PIPE,
            "stderr_is_pipe": effective.get("stderr") == subprocess.PIPE,
            "text_mode": bool(
                effective.get("text")
                or effective.get("universal_newlines")
                or effective.get("encoding")
                or effective.get("errors")
            ),
            "stdin_constructor": constructor,
            "popen_invocation": invocation,
        }

    def _record_process(
        self,
        context: dict[str, Any],
        returncode: int | None,
        stdout: object,
        stderr: object,
        observation: str,
        stdin_observation: dict[str, Any] | None = None,
    ) -> None:
        def output_record(value: object, *, was_pipe: bool) -> dict[str, object]:
            if value is None:
                return {"capture": "not_returned", "bytes": None, "sha256": None, "pipe": was_pipe}
            raw = value.encode("utf-8") if isinstance(value, str) else bytes(value)
            return {
                "capture": "text_decoded" if isinstance(value, str) else "raw_bytes",
                "bytes": len(raw),
                "sha256": sha256(raw),
                "pipe": was_pipe,
            }

        row_context = {key: value for key, value in context.items() if key != "stdin_constructor"}
        row = {
            **row_context,
            "returncode": returncode,
            "stdout": output_record(stdout, was_pipe=context["stdout_is_pipe"]),
            "stderr": output_record(stderr, was_pipe=context["stderr_is_pipe"]),
            "observation": observation,
            "stdin": stdin_observation
            or {
                "constructor": context["stdin_constructor"],
                "communicate_inputs": [],
                "direct_stream_writes": [],
                "descriptor_escape": False,
                "stream_status": "process_launch_failed_before_stream_observation",
            },
        }
        key = sha256(stable_json(row))
        if key not in self.process_results:
            self.process_results[key] = {**row, "calls": 0}
        self.process_results[key]["calls"] += 1

    def install(self) -> None:
        """Observe all child results and audit opens before loading report code."""
        if self._original_popen is not None:
            raise ReadClosureError("runtime process observer already installed")
        self._enabled = True
        self._original_popen = subprocess.Popen
        self._original_os_open = os.open
        trace = self
        original = self._original_popen
        try:
            self._original_popen_signature = inspect.signature(original.__init__)
        except (TypeError, ValueError):
            self._original_popen_signature = None
        original_os_open = self._original_os_open

        def fd_path(descriptor: int) -> Path:
            if sys.platform == "darwin":
                import fcntl

                raw = fcntl.fcntl(descriptor, fcntl.F_GETPATH, b"\0" * 1023)
                name = raw.split(b"\0", 1)[0].decode("utf-8", errors="surrogateescape")
                return Path(name)
            for proc_path in (Path(f"/proc/self/fd/{descriptor}"), Path(f"/dev/fd/{descriptor}")):
                try:
                    return Path(os.readlink(proc_path))
                except OSError:
                    continue
            raise ReadClosureError("cannot resolve relative os.open dir_fd")

        def captured_os_open(
            path: object, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
        ) -> int:
            old_pending = trace._pending_osopen_path
            try:
                candidate = Path(os.fsdecode(path))
                if not candidate.is_absolute() and dir_fd is not None:
                    candidate = fd_path(dir_fd) / candidate
                elif not candidate.is_absolute():
                    candidate = Path.cwd() / candidate
                trace._pending_osopen_path = Path(os.path.abspath(candidate))
                return (
                    original_os_open(path, flags, mode, dir_fd=dir_fd)
                    if dir_fd is not None
                    else original_os_open(path, flags, mode)
                )
            finally:
                trace._pending_osopen_path = old_pending

        os.open = captured_os_open

        class CapturingPopen(original):
            def __init__(self, *args: object, **kwargs: object) -> None:
                binding = trace._popen_binding(original, self, args, kwargs)
                self._q0_context = trace._process_context(binding, args, kwargs)
                actual_kwargs = binding.get("call_kwargs", kwargs)
                self._q0_in_communicate = False
                self._q0_recorded = False
                self._q0_stdin_observation = {
                    "constructor": self._q0_context["stdin_constructor"],
                    "communicate_inputs": [],
                    "direct_stream_writes": [],
                    "descriptor_escape": False,
                    "descriptor_escape_operations": [],
                    "stream_status": "not_a_managed_pipe",
                }
                self._q0_stdin_fd: int | None = None
                try:
                    super().__init__(*args, **actual_kwargs)
                except BaseException as exc:
                    trace._record_process(
                        self._q0_context, None, None, None, f"launch_error:{type(exc).__name__}"
                    )
                    self._q0_recorded = True
                    raise
                if (
                    self.stdin is not None
                    and self._q0_context["stdin_constructor"]["origin"] == "managed_pipe"
                ):
                    underlying_stdin = self.stdin
                    try:
                        self._q0_stdin_fd = int(underlying_stdin.fileno())
                        trace._stdin_fd_owners[self._q0_stdin_fd] = self
                        self.stdin = self.ObservedStdin(underlying_stdin, self)
                        self._q0_stdin_observation["stream_status"] = (
                            "python_stream_writes_observed; raw_fd_escape_is_residual"
                        )
                    except (OSError, TypeError, ValueError) as exc:
                        self._q0_stdin_observation["stream_status"] = (
                            f"managed_pipe_stream_unresolved:{type(exc).__name__}"
                        )

            class ObservedStdin:
                """Proxy child stdin so direct Python stream writes enter the result row."""

                def __init__(self, stream: object, owner: object) -> None:
                    self._stream = stream
                    self._owner = owner

                def write(self, value: object) -> object:
                    row = trace._stream_write(self._stream, value)
                    row["ordinal"] = (
                        len(self._owner._q0_stdin_observation["direct_stream_writes"]) + 1
                    )
                    try:
                        result = self._stream.write(value)
                    except BaseException as exc:
                        row["write_result"] = f"error:{type(exc).__name__}"
                        self._owner._q0_stdin_observation["direct_stream_writes"].append(row)
                        raise
                    row["write_result"] = "accepted"
                    row["accepted_count"] = result
                    self._owner._q0_stdin_observation["direct_stream_writes"].append(row)
                    return result

                def fileno(self) -> int:
                    if not self._owner._q0_in_communicate:
                        self._owner._q0_stdin_observation["descriptor_escape"] = True
                        self._owner._q0_stdin_observation["descriptor_escape_operations"].append(
                            "fileno"
                        )
                    return int(self._stream.fileno())

                def __getattr__(self, name: str) -> object:
                    if name in {"raw", "buffer", "detach"} and not self._owner._q0_in_communicate:
                        self._owner._q0_stdin_observation["descriptor_escape"] = True
                        self._owner._q0_stdin_observation["descriptor_escape_operations"].append(
                            name
                        )
                    return getattr(self._stream, name)

                def close(self) -> object:
                    try:
                        return self._stream.close()
                    finally:
                        owner_fd = self._owner._q0_stdin_fd
                        if (
                            owner_fd is not None
                            and trace._stdin_fd_owners.get(owner_fd) is self._owner
                        ):
                            trace._stdin_fd_owners.pop(owner_fd, None)

                def __enter__(self) -> object:
                    return self

                def __exit__(self, *args: object) -> object:
                    return self._stream.__exit__(*args)

            def _q0_finish(
                self,
                stdout: object = None,
                stderr: object = None,
                observation: str = "wait_without_capture",
            ) -> None:
                if self._q0_recorded:
                    return
                if (
                    self._q0_stdin_fd is not None
                    and trace._stdin_fd_owners.get(self._q0_stdin_fd) is self
                ):
                    trace._stdin_fd_owners.pop(self._q0_stdin_fd, None)
                self._q0_stdin_observation["stream_closed_at_record"] = (
                    bool(getattr(self.stdin, "closed", True)) if self.stdin is not None else True
                )
                trace._record_process(
                    self._q0_context,
                    self.returncode,
                    stdout,
                    stderr,
                    observation,
                    self._q0_stdin_observation,
                )
                self._q0_recorded = True

            def communicate(self, *args: object, **kwargs: object) -> object:
                input_provided = bool(args) or "input" in kwargs
                input_value = args[0] if args else kwargs.get("input")
                input_row = trace._communicate_input(
                    input_value,
                    provided=input_provided,
                    stream=self.stdin,
                    text_mode=bool(getattr(self, "text_mode", False)),
                )
                input_row["constructor_origin"] = self._q0_stdin_observation["constructor"][
                    "origin"
                ]
                input_row["transmission"] = (
                    "communicate_pipe"
                    if self._q0_stdin_observation["constructor"]["origin"] == "managed_pipe"
                    else "not_proven_transmitted_to_child"
                )
                self._q0_stdin_observation["communicate_inputs"].append(input_row)
                self._q0_in_communicate = True
                try:
                    output = super().communicate(*args, **kwargs)
                except BaseException as exc:
                    self._q0_finish(None, None, f"communicate_error:{type(exc).__name__}")
                    raise
                finally:
                    self._q0_in_communicate = False
                stdout, stderr = output
                self._q0_finish(stdout, stderr, "communicate_complete")
                return output

            def wait(self, *args: object, **kwargs: object) -> object:
                result = super().wait(*args, **kwargs)
                if not self._q0_in_communicate:
                    self._q0_finish(None, None, "wait_without_captured_result")
                return result

            def poll(self) -> object:
                result = super().poll()
                if result is not None and not self._q0_in_communicate:
                    self._q0_finish(None, None, "poll_without_captured_result")
                return result

        subprocess.Popen = CapturingPopen
        sys.addaudithook(self._hook)

    def restore(self) -> None:
        """Disable capture and restore subprocess.Popen before verifier queries."""
        self._enabled = False
        if self._original_popen is not None:
            subprocess.Popen = self._original_popen
        if self._original_os_open is not None:
            os.open = self._original_os_open

    def source_paths(self) -> set[str]:
        """Derive opened source paths, excluding only run-created untracked outputs."""
        result: set[str] = set()
        for path in self.reads:
            if path in self.writes:
                self.root / path
                probe = _run_git(self.root, "ls-tree", "-z", "HEAD", "--", path)
                if not probe.stdout:
                    continue
            result.add(path)
        return result

    def process_rows(self) -> list[dict[str, Any]]:
        """Return all child result observations in stable order."""
        return [self.process_results[key] for key in sorted(self.process_results)]

    def as_json(self, source_paths: list[str]) -> dict[str, Any]:
        """Return bounded read diagnostics without storing source payloads."""
        return {
            "schema": "policyos.e02.q0_runtime_read_trace.r7.v1",
            "scope": (
                "full report build and R2 controls; filesystem opens and child "
                "results bind to the effective parameter set from "
                "inspect.signature.bind on captured real Popen; only truly omitted "
                "stdin is sealed to DEVNULL; explicit inherited/file-descriptor stdin "
                "and low-level stream escapes remain explicit residuals"
            ),
            "repository_source_reads": [
                {"path": path, **self.reads[path]} for path in source_paths
            ],
            "repository_source_read_count": len(source_paths),
            "repository_directory_open_counts": dict(sorted(self.directories.items())),
            "repository_write_events": [
                {"path": path, **self.writes[path]} for path in sorted(self.writes)
            ],
            "repository_nonregular_reads": [
                {"path": path, **self.nonregular_reads[path]}
                for path in sorted(self.nonregular_reads)
            ],
            "repository_missing_open_attempts": [
                {"path": path, **self.missing_open_attempts[path]}
                for path in sorted(self.missing_open_attempts)
            ],
            "repository_symlink_reads": sorted(self.symlink_reads),
            "unbound_symlink_targets": self.unbound_symlinks,
            "child_process_audit_event_count": self.audit_process_event_count,
            "child_process_result_groups": self.process_rows(),
            "child_process_result_invocation_count": sum(
                row["calls"] for row in self.process_results.values()
            ),
            "unsupported_process_events": self.unsupported_process_events,
            "audit_callback_errors": self.audit_errors,
            "outside_repository_open_summary": [
                self.external[key] for key in sorted(self.external)
            ],
            "event_class_counts": {
                f"{scope}:{operation}": count
                for (scope, operation), count in sorted(self.events.items())
            },
        }


def _git_bytes(root: Path, *args: str) -> bytes:
    """Run a read-only Git query and return exact stdout bytes."""
    result = _run_git(root, *args)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReadClosureError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _tree_entry(root: Path, commit: str, path: str) -> tuple[str, str, str] | None:
    """Resolve one literal Git path to mode, object type, and object id."""
    raw = _git_bytes(root, "--literal-pathspecs", "ls-tree", "-z", commit, "--", path)
    if not raw:
        return None
    rows = raw.split(b"\0")
    if rows[-1] == b"":
        rows.pop()
    matches = []
    for row in rows:
        metadata, result_path = row.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        if result_path.decode("utf-8", errors="surrogateescape") == path:
            matches.append((mode, kind, oid))
    if len(matches) != 1:
        raise ReadClosureError(f"Git tree lookup was not one exact entry: {path}")
    return matches[0]


def _filesystem_record(root: Path, commit: str, relative: str, *, strict: bool) -> dict[str, Any]:
    """Bind a regular file or symlink's filesystem bytes and HEAD object."""
    path = root / relative
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raw = os.fsencode(os.readlink(path))
        filesystem_kind = "symlink"
    elif stat.S_ISREG(info.st_mode):
        raw = path.read_bytes()
        filesystem_kind = "regular"
    else:
        raise ReadClosureError(f"opened source is not regular file or symlink: {relative}")
    filesystem_mode = f"{stat.S_IMODE(info.st_mode):04o}"
    entry = _tree_entry(root, commit, relative)
    if entry is None:
        require(not strict, f"source is not present in committed HEAD: {relative}")
        return {
            "path": relative,
            "filesystem_kind": filesystem_kind,
            "bytes": len(raw),
            "sha256": sha256(raw),
            "filesystem_mode_octal": filesystem_mode,
            "git_tree_mode": None,
            "git_object_type": None,
            "git_object_id": None,
            "source_commit": None,
            "availability": "local_readback_only_untracked",
        }
    git_mode, git_type, object_id = entry
    expected_mode = (
        "120000"
        if filesystem_kind == "symlink"
        else ("100755" if info.st_mode & 0o111 else "100644")
    )
    object_type = "commit" if git_mode == "160000" else ("tree" if git_type == "tree" else "blob")
    git_raw = _git_bytes(root, "cat-file", object_type, object_id)
    exact = raw == git_raw and git_mode == expected_mode
    if strict:
        require(exact, f"filesystem bytes or mode differ from committed HEAD: {relative}")
    return {
        "path": relative,
        "filesystem_kind": filesystem_kind,
        "bytes": len(raw),
        "sha256": sha256(raw),
        "filesystem_mode_octal": filesystem_mode,
        "git_tree_mode": git_mode,
        "git_object_type": object_type,
        "git_object_id": object_id,
        "source_commit": commit,
        "availability": "committed_HEAD_exact_bytes_and_mode"
        if exact
        else "local_readback_only_dirty_against_HEAD",
    }


def bind_source_paths(
    root: Path, commit: str, paths: set[str], *, strict: bool
) -> list[dict[str, Any]]:
    """Bind every recomputed filesystem path, including symlink object bytes."""
    records = []
    for relative in sorted(paths):
        try:
            records.append(_filesystem_record(root, commit, relative, strict=strict))
        except Exception as exc:
            records.append(
                {
                    "path": relative,
                    "availability": "unavailable_or_nonregular",
                    "binding_error": f"{type(exc).__name__}: {exc}",
                }
            )
    return records


def _git_command(argv: list[str]) -> str | None:
    commands = {
        "show",
        "cat-file",
        "rev-parse",
        "ls-tree",
        "diff",
        "status",
        "log",
        "rev-list",
        "merge-base",
        "grep",
        "blame",
        "archive",
        "hash-object",
        "check-ignore",
        "ls-files",
    }
    return next((item for item in argv[1:] if item in commands), None)


def _git_path_refs(process_rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Derive commit:path inputs from actual Git argv, not a declared path list."""
    refs: set[tuple[str, str]] = set()
    pattern = re.compile(r"^([0-9a-f]{40}|[0-9a-f]{64}):(.+)$")
    for row in process_rows:
        argv = row["argv"]
        if not argv or Path(argv[0]).name != "git":
            continue
        for arg in argv:
            match = pattern.match(arg)
            if match:
                refs.add((match.group(1), match.group(2)))
    return refs


def _resolve_git_path_refs(
    root: Path, head: str, process_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Bind every observed commit:path to availability, mode, blob, and bytes hash."""
    refs = _git_path_refs(process_rows)
    records: list[dict[str, Any]] = []
    issues: list[str] = []
    process_by_ref: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in process_rows:
        argv = row["argv"]
        if not argv or Path(argv[0]).name != "git":
            continue
        for arg in argv:
            match = re.match(r"^([0-9a-f]{40}|[0-9a-f]{64}):(.+)$", arg)
            if match:
                process_by_ref[(match.group(1), match.group(2))].append(row)
    for requested_commit, path in sorted(refs):
        attempts = process_by_ref[(requested_commit, path)]
        successful_attempts = [row for row in attempts if row.get("returncode") == 0]
        if attempts and not successful_attempts:
            records.append(
                {
                    "requested_commit": requested_commit,
                    "path": path,
                    "lookup_status": "negative_lookup_result_recorded",
                    "object_available_in_local_git_database": False,
                    "observed_process_result_count": sum(row["calls"] for row in attempts),
                    "process_result_sha256s": [sha256(stable_json(row)) for row in attempts],
                    "qualification": (
                        "failed lookup is captured as a result, not misrepresented as source bytes"
                    ),
                }
            )
            continue
        try:
            resolved = (
                _git_bytes(root, "rev-parse", "--verify", f"{requested_commit}^{{commit}}")
                .decode("ascii")
                .strip()
            )
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", resolved):
                raise ReadClosureError("Git did not return a full commit object id")
            entry = _tree_entry(root, resolved, path)
            if entry is None:
                raise ReadClosureError("referenced path is unavailable at the selected commit")
            mode, kind, object_id = entry
            object_type = "commit" if mode == "160000" else ("tree" if kind == "tree" else "blob")
            raw = _git_bytes(root, "cat-file", object_type, object_id)
            ancestor = _run_git(root, "merge-base", "--is-ancestor", resolved, head)
            if ancestor.returncode not in (0, 1):
                raise ReadClosureError("Git could not establish source commit reachability")
            content_results = []
            ref_token = f"{requested_commit}:{path}"
            candidates = list(process_by_ref[(requested_commit, path)])
            candidates.extend(
                process
                for process in process_rows
                if _git_command(process["argv"]) == "cat-file" and object_id in process["argv"]
            )
            for process in candidates:
                command = _git_command(process["argv"])
                stdout = process["stdout"]
                if command in {"show", "cat-file"} and stdout.get("capture") == "raw_bytes":
                    exact = stdout.get("bytes") == len(raw) and stdout.get("sha256") == sha256(raw)
                    if exact:
                        content_results.append(
                            {
                                "command": command,
                                "process_result_sha256": sha256(stable_json(process)),
                                "stdout_sha256": stdout["sha256"],
                                "stdout_bytes": stdout["bytes"],
                            }
                        )
                    elif command == "show" and ref_token in process["argv"]:
                        issues.append(
                            f"git show output did not equal resolved object bytes: {ref_token}"
                        )
            records.append(
                {
                    "requested_commit": requested_commit,
                    "resolved_commit": resolved,
                    "path": path,
                    "git_tree_mode": mode,
                    "git_object_type": object_type,
                    "git_object_id": object_id,
                    "bytes": len(raw),
                    "sha256": sha256(raw),
                    "object_available_in_local_git_database": True,
                    "source_commit_is_ancestor_of_report_HEAD": ancestor.returncode == 0,
                    "observed_process_result_count": sum(
                        row["calls"] for row in process_by_ref[(requested_commit, path)]
                    ),
                    "matched_exact_content_result_count": len(content_results),
                    "matched_exact_content_results": content_results,
                }
            )
        except Exception as exc:
            issues.append(
                f"cannot bind Git object reference "
                f"{requested_commit}"
                f":"
                f"{path}"
                f": "
                f"{type(exc).__name__}"
                f": "
                f"{exc}"
            )
            records.append(
                {
                    "requested_commit": requested_commit,
                    "path": path,
                    "object_available_in_local_git_database": False,
                    "binding_error": f"{type(exc).__name__}: {exc}",
                }
            )
    return records, issues


def _git_content_object_reads(
    root: Path, process_rows: list[dict[str, Any]], path_refs: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Bind object-only cat-file results when no commit:path reference was passed."""
    by_oid = {row.get("git_object_id"): row for row in path_refs if row.get("git_object_id")}
    records: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    for process in process_rows:
        argv = process["argv"]
        if not argv or Path(argv[0]).name != "git" or _git_command(argv) != "cat-file":
            continue
        if (
            process["stdout"].get("capture") != "raw_bytes"
            or process["stdout"].get("bytes", 0) == 0
        ):
            continue
        object_ids = [arg for arg in argv if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", arg)]
        for object_id in object_ids:
            if object_id in by_oid:
                continue
            try:
                object_type = _git_bytes(root, "cat-file", "-t", object_id).decode("ascii").strip()
                raw = _git_bytes(root, "cat-file", object_type, object_id)
                exact = (
                    len(raw) == process["stdout"]["bytes"]
                    and sha256(raw) == process["stdout"]["sha256"]
                )
                if not exact:
                    issues.append(
                        f"captured cat-file output was not exact Git object bytes: {object_id}"
                    )
                records[object_id] = {
                    "git_object_id": object_id,
                    "git_object_type": object_type,
                    "bytes": len(raw),
                    "sha256": sha256(raw),
                    "object_available_in_local_git_database": True,
                    "path_binding": None,
                    "matched_exact_content_result_count": 1 if exact else 0,
                    "observed_process_result_sha256": sha256(stable_json(process)),
                }
            except Exception as exc:
                issues.append(
                    f"cannot bind Git object-only read {object_id}: {type(exc).__name__}: {exc}"
                )
                records[object_id] = {
                    "git_object_id": object_id,
                    "object_available_in_local_git_database": False,
                    "binding_error": f"{type(exc).__name__}: {exc}",
                }
    return [records[key] for key in sorted(records)], issues


def validate_closure_records(
    observed_paths: set[str],
    expected_paths: set[str],
    expected_records: list[dict[str, Any]],
    actual_records: list[dict[str, Any]],
    expected_processes: list[dict[str, Any]],
    actual_processes: list[dict[str, Any]],
    expected_git_refs: list[dict[str, Any]],
    actual_git_refs: list[dict[str, Any]],
    expected_object_reads: list[dict[str, Any]],
    actual_object_reads: list[dict[str, Any]],
) -> list[str]:
    """Compare complete live filesystem and Git-result closures."""
    issues: list[str] = []
    if observed_paths != expected_paths:
        issues.append("filesystem source path set differs from the observed open set")
    for label, expected, actual in (
        ("filesystem bindings", expected_records, actual_records),
        ("child-process results", expected_processes, actual_processes),
        ("Git path references", expected_git_refs, actual_git_refs),
        ("Git object-only reads", expected_object_reads, actual_object_reads),
    ):
        if sorted(stable_json(row) for row in expected) != sorted(
            stable_json(row) for row in actual
        ):
            issues.append(f"{label} differ from independently recomputed live rows")
    return issues


def source_closure_controls(
    paths: set[str],
    file_records: list[dict[str, Any]],
    process_rows: list[dict[str, Any]],
    git_refs: list[dict[str, Any]],
    object_reads: list[dict[str, Any]],
) -> dict[str, Any]:
    """Falsify every live input row and identity field with generic row comparison."""
    groups = [file_records, process_rows, git_refs, object_reads]
    labels = ("filesystem", "child-process result", "Git path reference", "Git object-only read")
    actual_signature = inspect.signature(subprocess.Popen.__init__)
    actual_signature_text = str(actual_signature)
    actual_signature_hash = sha256(actual_signature_text.encode("utf-8"))
    actual_parameter_names = [name for name in actual_signature.parameters if name != "self"]
    omitted_stdin_sealed = 0
    explicit_none_stdin = 0
    positional_stdin = 0
    for row in process_rows:
        binding = row.get("popen_invocation")
        if not isinstance(binding, dict) or binding.get("status") != "bound":
            raise ReadClosureError(
                "actual process row has no successful real-Popen signature binding"
            )
        if (
            binding.get("signature_sha256") != actual_signature_hash
            or binding.get("signature") != actual_signature_text
        ):
            raise ReadClosureError(
                "process row was not bound to the currently captured real Popen signature"
            )
        if binding.get("signature_parameters") != actual_parameter_names:
            raise ReadClosureError(
                "process row omitted or reordered a real Popen signature parameter"
            )
        if list(binding.get("effective_parameter_bindings", {})) != actual_parameter_names:
            raise ReadClosureError(
                "process row lacks an effective binding for every real Popen parameter"
            )
        stdin = row.get("stdin", {})
        constructor = stdin.get("constructor", {}) if isinstance(stdin, dict) else {}
        if binding.get("stdin_was_omitted"):
            if (
                not binding.get("stdin_default_sealed")
                or constructor.get("origin") != "known_empty_device"
                or constructor.get("source_argument_presence") != "omitted"
                or constructor.get("effective_value") != "DEVNULL"
            ):
                raise ReadClosureError(
                    "omitted real-Popen stdin did not reach the child as the recorded DEVNULL seal"
                )
            omitted_stdin_sealed += 1
        elif (
            binding.get("stdin_default_sealed")
            or constructor.get("source_argument_presence") != "explicit"
        ):
            raise ReadClosureError(
                "explicit real-Popen stdin was collapsed into an omission or synthetic default"
            )
        if binding.get("stdin_argument_form") == "positional":
            positional_stdin += 1
        if constructor.get("argument") == "explicit_none":
            explicit_none_stdin += 1

    def validator_issues(actual_groups: list[list[dict[str, Any]]]) -> list[str]:
        return validate_closure_records(
            paths,
            paths,
            file_records,
            actual_groups[0],
            process_rows,
            actual_groups[1],
            git_refs,
            actual_groups[2],
            object_reads,
            actual_groups[3],
        )

    def replace_row(
        index: int, old_row: dict[str, Any], new_row: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        changed = list(groups[index])
        old_bytes = stable_json(old_row)
        row_index = next(
            (position for position, row in enumerate(changed) if stable_json(row) == old_bytes),
            None,
        )
        if row_index is None:
            raise ReadClosureError(f"source closure control could not locate {labels[index]} row")
        if new_row is None:
            changed.pop(row_index)
        else:
            changed[row_index] = new_row
        return changed

    def must_reject(index: int, changed_rows: list[dict[str, Any]], label: str) -> None:
        actual = [list(rows) for rows in groups]
        actual[index] = changed_rows
        if not validator_issues(actual):
            raise ReadClosureError(
                f"actual closure validator accepted {label} with status markers intact"
            )

    removals = {}
    for index, label in enumerate(
        ("filesystem", "child_process_result", "git_path_reference", "git_object_only_read")
    ):
        rejected = 0
        for row in groups[index]:
            must_reject(index, replace_row(index, row, None), f"{label} row removal")
            rejected += 1
        removals[label] = {"probes": rejected, "rejected": rejected}

    field_counts: collections.Counter[str] = collections.Counter()
    for index, (group_name, rows) in enumerate(
        zip(("filesystem", "child_process", "git_path", "git_object"), groups, strict=False)
    ):
        for row in rows:
            for field, value in row.items():
                mutated = copy.deepcopy(row)
                if isinstance(value, bool):
                    mutated[field] = not value
                elif isinstance(value, int):
                    mutated[field] = value + 1
                elif isinstance(value, str):
                    mutated[field] = "corrupt:" + value
                elif value is None:
                    mutated[field] = "corrupt"
                elif isinstance(value, list):
                    mutated[field] = [*value, {"corrupt": True}]
                elif isinstance(value, dict):
                    mutated[field] = {**value, "corrupt": True}
                else:
                    continue
                must_reject(
                    index, replace_row(index, row, mutated), f"{group_name}.{field} mutation"
                )
                field_counts[f"{group_name}.{field}"] += 1

    process_hash_mutations = 0
    for row in process_rows:
        mutated = copy.deepcopy(row)
        mutated["stdout"] = {**mutated["stdout"], "sha256": "f" * 64}
        must_reject(1, replace_row(1, row, mutated), "child stdout hash mutation")
        process_hash_mutations += 1

    parameter_binding_mutations = 0
    parameter_binding_removals = 0
    invocation_binding_removals = 0
    if process_rows:
        row = process_rows[0]
        for name in actual_parameter_names:
            mutated = copy.deepcopy(row)
            binding_value = mutated["popen_invocation"]["effective_parameter_bindings"][name]
            binding_value["value_sha256"] = "f" * 64
            must_reject(
                1,
                replace_row(1, row, mutated),
                f"real Popen {name} binding mutation with markers intact",
            )
            parameter_binding_mutations += 1
            mutated = copy.deepcopy(row)
            mutated["popen_invocation"]["effective_parameter_bindings"].pop(name)
            must_reject(
                1,
                replace_row(1, row, mutated),
                f"real Popen {name} binding removal with markers intact",
            )
            parameter_binding_removals += 1
        mutated = copy.deepcopy(row)
        mutated.pop("popen_invocation")
        must_reject(
            1,
            replace_row(1, row, mutated),
            "real Popen invocation binding removal with process markers intact",
        )
        invocation_binding_removals += 1

    removed_stdin_bindings = 0
    changed_input_bytes = 0
    for row in process_rows:
        if "stdin" not in row:
            raise ReadClosureError("child process row is missing its generic stdin binding")
        mutated = copy.deepcopy(row)
        mutated.pop("stdin")
        must_reject(1, replace_row(1, row, mutated), "child stdin binding removal")
        removed_stdin_bindings += 1
    input_rows = [
        (process_row, input_row)
        for process_row in process_rows
        for input_row in process_row.get("stdin", {}).get("communicate_inputs", [])
        if input_row.get("bytes") is not None and input_row.get("sha256") is not None
    ]
    if not input_rows:
        raise ReadClosureError(
            "actual process-input controls require at least one byte-bound communicate input"
        )
    process_row, input_row = input_rows[0]
    mutated = copy.deepcopy(process_row)
    changed = next(item for item in mutated["stdin"]["communicate_inputs"] if item == input_row)
    changed["bytes"] = changed["bytes"] + 1
    changed["sha256"] = "f" * 64
    must_reject(
        1,
        replace_row(1, process_row, mutated),
        "different stdin bytes with argv/result markers unchanged",
    )
    changed_input_bytes += 1

    return {
        "schema": "policyos.e02.q0_runtime_read_closure_controls.r7.v1",
        "status": "PASS",
        "remove_one_row_keep_markers": removals,
        "bound_row_field_mutations": dict(sorted(field_counts.items())),
        "process_stdout_hash_mutations": {
            "probes": process_hash_mutations,
            "rejected": process_hash_mutations,
        },
        "process_input_binding_controls": {
            "remove_stdin_binding_keep_process_markers": {
                "probes": removed_stdin_bindings,
                "rejected": removed_stdin_bindings,
            },
            "different_input_same_argv_returncode_stdout_stderr": {
                "probes": 1,
                "rejected": changed_input_bytes,
            },
        },
        "popen_signature_binding_controls": {
            "status": "PASS",
            "captured_real_signature_sha256": actual_signature_hash,
            "signature_parameter_count": len(actual_parameter_names),
            "process_result_groups_checked": len(process_rows),
            "all_signature_parameters_bound_per_group": True,
            "omitted_stdin_default_sealed_groups": omitted_stdin_sealed,
            "explicit_none_stdin_groups": explicit_none_stdin,
            "positional_stdin_groups": positional_stdin,
            "effective_parameter_mutations_keep_markers": {
                "probes": parameter_binding_mutations,
                "rejected": parameter_binding_mutations,
            },
            "effective_parameter_removals_keep_markers": {
                "probes": parameter_binding_removals,
                "rejected": parameter_binding_removals,
            },
            "invocation_binding_removals_keep_process_markers": {
                "probes": invocation_binding_removals,
                "rejected": invocation_binding_removals,
            },
        },
        "property": (
            "the comparator binds every effective Popen parameter through "
            "inspect.signature.bind on the captured real constructor; the "
            "controls derive parameter names from that actual signature and "
            "falsify every effective parameter hash while process status markers "
            "remain intact; omitted stdin defaults are sealed to DEVNULL, while "
            "explicit stdin origins and observed input bytes remain separately "
            "bound"
        ),
    }


def environment_profile(root: Path, modules_before_trace: frozenset[str]) -> dict[str, Any]:
    """Describe the runtime needed to interpret source code without vendoring stdlib."""
    version = _run_git(root, "--version", text=True)
    modules: dict[str, dict[str, str]] = {}
    stdlib = Path(sysconfig.get_paths().get("stdlib", "/nonexistent")).resolve()
    site_roots = [
        Path(value).resolve()
        for key, value in sysconfig.get_paths().items()
        if "purelib" in key or "platlib" in key
    ]
    for name, module in sorted(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin)
        try:
            resolved = path.resolve()
        except OSError:
            continue
        try:
            resolved.relative_to(root)
            continue
        except ValueError:
            pass
        try:
            resolved.relative_to(stdlib)
            category = "python_standard_library_or_runtime"
        except ValueError:
            category = "external_import_origin"
            if any(_is_relative_to(resolved, site) for site in site_roots):
                category = "third_party_site_package"
        modules[name] = {"origin": str(resolved), "category": category}
    imported_during_run = {
        name: row for name, row in modules.items() if name not in modules_before_trace
    }
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": sys.version,
        "python_executable": str(Path(sys.executable).resolve()),
        "python_platform": sys.platform,
        "machine": platform.machine(),
        "sys_prefix": sys.prefix,
        "stdlib_root": str(stdlib),
        "site_package_roots": [str(path) for path in site_roots],
        "git_version": version.stdout.strip() if version.returncode == 0 else "unavailable",
        "loaded_module_origins": modules,
        "preloaded_third_party_module_count": sum(
            row["category"] == "third_party_site_package" and name in modules_before_trace
            for name, row in modules.items()
        ),
        "third_party_module_count": sum(
            row["category"] == "third_party_site_package" for row in imported_during_run.values()
        ),
        "unbound_external_module_count": sum(
            row["category"] == "external_import_origin" for row in imported_during_run.values()
        ),
        "modules_imported_during_report_build": imported_during_run,
        "qualification": (
            "runtime identity only; no standard-library source files copied or "
            "hashed; any third-party imports require a separate pinned runtime "
            "dependency record"
        ),
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def collect_report(
    root: Path, trace: RuntimeReadTrace
) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    """Build the full report through R3/R1/R2 under the installed read audit."""
    r3_path = root / R3_COMPANION
    # R3's helper originally delegates its remaining code imports to spec.loader,
    # which can consult __pycache__. Rebind that one exact consumer seam to the
    # source-only importer while preserving canonical-emitter reuse.
    source = r3_path.read_bytes()
    anchor = "return original_import(name, path)"
    if source.count(anchor.encode()) != 1:
        raise ReadClosureError("R3 consumer import seam changed; source review required")
    patched_source = source.replace(anchor.encode(), b"return import_source(name, path)")
    r3 = types.ModuleType("q0_r7_source_read_closed_r3_overlay")
    r3.__file__ = str(r3_path.resolve())
    r3.__package__ = ""
    sys.modules[r3.__name__] = r3
    r3.import_source = source_import
    # S102: patched_source is constructed from the pinned R3 source bytes in this verifier.
    exec(compile(patched_source, r3.__file__, "exec"), r3.__dict__)  # noqa: S102
    r3.import_path = source_import
    report_raw, controls_raw, receipt = r3.build_registered_report(root, strict=False)
    packet = json.loads(report_raw)
    json.loads(controls_raw)
    if packet["registration"]["candidate_evaluation"] != "UNRUN for all 291 occurrences":
        raise ReadClosureError("candidate evaluation state changed during report composition")
    if (
        packet["registration"]["criterion_owner_alignment"]
        != "not_established for all 291 occurrences; scoped owner assertion remains separate"
    ):
        raise ReadClosureError("criterion/owner alignment was promoted during report composition")
    return packet, controls_raw, receipt


def _process_stdin_residuals(process_rows: list[dict[str, Any]]) -> list[str]:
    """Fail closed on explicit constructor streams or bypasses whose bytes are not observed."""
    unbound_origins: collections.Counter[str] = collections.Counter()
    unsupported_inputs = 0
    fd_escapes = 0
    unsupported_stream_writes = 0
    partial_stream_writes = 0
    unresolved_pipes = 0
    missing_bindings = 0
    unresolved_popen_bindings = 0
    unsupported_popen_parameters = 0
    unsealed_omitted_stdin = 0
    for row in process_rows:
        invocation = row.get("popen_invocation")
        if not isinstance(invocation, dict) or invocation.get("status") != "bound":
            unresolved_popen_bindings += 1
        elif invocation.get("unsupported_parameter_bindings"):
            unsupported_popen_parameters += len(invocation["unsupported_parameter_bindings"])
        if (
            isinstance(invocation, dict)
            and invocation.get("status") == "bound"
            and invocation.get("stdin_was_omitted")
            and not invocation.get("stdin_default_sealed")
        ):
            unsealed_omitted_stdin += 1
        stdin = row.get("stdin")
        if not isinstance(stdin, dict):
            missing_bindings += 1
            continue
        constructor = stdin.get("constructor", {})
        origin = constructor.get("origin", "missing_constructor_origin")
        if origin not in {"managed_pipe", "known_empty_device"}:
            unbound_origins[origin] += 1
        if stdin.get("descriptor_escape"):
            fd_escapes += 1
        if origin == "managed_pipe" and not str(stdin.get("stream_status", "")).startswith(
            "python_stream_writes_observed"
        ):
            unresolved_pipes += 1
        for item in stdin.get("communicate_inputs", []):
            if item.get("capture") in {
                "unsupported_input_type",
                "unsupported_text_without_text_pipe",
                "unsupported_missing_encoding",
            } or str(item.get("capture", "")).startswith("encoding_error:"):
                unsupported_inputs += 1
            if item.get("bytes") is not None and item.get("transmission") != "communicate_pipe":
                unsupported_inputs += 1
        for item in stdin.get("direct_stream_writes", []):
            if item.get("capture") != "exact_argument_bytes":
                unsupported_stream_writes += 1
            accepted = item.get("accepted_count")
            offered = item.get("bytes")
            if isinstance(accepted, int) and isinstance(offered, int) and accepted != offered:
                partial_stream_writes += 1
    issues: list[str] = []
    if missing_bindings:
        issues.append(f"child stdin binding absent for {missing_bindings} process result groups")
    if unresolved_popen_bindings:
        issues.append(
            f"actual Popen invocation could not bind to captured real signature "
            f"for "
            f"{unresolved_popen_bindings}"
            f" process result groups"
        )
    if unsupported_popen_parameters:
        issues.append(
            f"effective Popen parameter value could not be source-described: "
            f"{unsupported_popen_parameters}"
            f" bindings"
        )
    if unsealed_omitted_stdin:
        issues.append(
            f"omitted Popen stdin default was not sealed to DEVNULL for "
            f"{unsealed_omitted_stdin}"
            f" process result groups"
        )
    if unbound_origins:
        issues.append(
            f"child constructor stdin origin not byte-bound: "
            f"{dict(sorted(unbound_origins.items()))}"
        )
    if unsupported_inputs:
        issues.append(
            f"communicate input not byte-bound or not transmitted through a "
            f"captured pipe: "
            f"{unsupported_inputs}"
            f" rows"
        )
    if fd_escapes:
        issues.append(
            f"managed child stdin descriptor escaped the Python stream observer: "
            f"{fd_escapes}"
            f" process result groups"
        )
    if unsupported_stream_writes:
        issues.append(
            f"direct child stdin stream writes lack exact bytes: {unsupported_stream_writes} writes"
        )
    if partial_stream_writes:
        issues.append(
            f"direct child stdin stream write accepted only a partial argument: "
            f"{partial_stream_writes}"
            f" writes"
        )
    if unresolved_pipes:
        issues.append(
            f"managed child stdin pipe stream could not be wrapped for exact write "
            f"observation: "
            f"{unresolved_pipes}"
            f" process result groups"
        )
    return issues


def build_r7(root: Path, *, strict: bool, controls_path: Path) -> dict[str, Any]:
    """Recompute the full report and filesystem/Git result closure."""
    start_head = git(root, "rev-parse", "HEAD")
    start_tree = git(root, "rev-parse", "HEAD^{tree}")
    trace = RuntimeReadTrace(root)
    trace.install()
    try:
        packet, controls_raw, r3_receipt = collect_report(root, trace)
    finally:
        trace.restore()
    end_head = git(root, "rev-parse", "HEAD")
    end_tree = git(root, "rev-parse", "HEAD^{tree}")
    if start_head != end_head or start_tree != end_tree:
        raise ReadClosureError("HEAD/tree changed during the source-read closure run")
    self_path = Path(__file__).resolve()
    try:
        self_rel = self_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ReadClosureError("executing tool source is outside repository") from exc
    source_paths = trace.source_paths()
    source_paths.add(self_rel)
    trace.reads.setdefault(
        self_rel,
        {
            "first_callsite": {"path": self_rel, "line": 1, "function": "<executing_tool_source>"},
            "read_opens": 0,
            "filesystem_kind": "executing_tool_source",
        },
    )
    records = bind_source_paths(root, end_head, source_paths, strict=False)
    if {row["path"] for row in records} != source_paths:
        raise ReadClosureError(
            "filesystem source bindings do not match the exact observed path set"
        )
    process_rows = trace.process_rows()
    result_count = sum(row["calls"] for row in process_rows)
    strict_issues: list[str] = []
    if trace.audit_errors:
        strict_issues.append(f"audit callback failures: {trace.audit_errors[:3]}")
    if trace.unsupported_process_events:
        strict_issues.append(
            f"unsupported process launch events: {trace.unsupported_process_events[:3]}"
        )
    if trace.audit_process_event_count != result_count:
        strict_issues.append(
            f"process audit/result invocation mismatch: audit="
            f"{trace.audit_process_event_count}"
            f"; results="
            f"{result_count}"
        )
    for row in process_rows:
        if row["shell"]:
            strict_issues.append("shell-mediated child process has no argv source classification")
            break
        if row["stdout_is_pipe"] and row["observation"] != "communicate_complete":
            strict_issues.append(
                f"child stdout pipe result was not completely observed: {row['observation']}"
            )
            break
    strict_issues.extend(_process_stdin_residuals(process_rows))
    if trace.unbound_symlinks:
        strict_issues.append(f"unbound symlink targets: {trace.unbound_symlinks[:3]}")
    generated_nonregular = {
        path
        for path in trace.nonregular_reads
        if path in trace.writes and not (root / path).exists()
    }
    unknown_nonregular = sorted(set(trace.nonregular_reads) - generated_nonregular)
    if unknown_nonregular:
        strict_issues.append(
            f"non-regular repository reads are not source-bound: {unknown_nonregular[:8]}"
        )
    for row in records:
        if row.get("availability") != "committed_HEAD_exact_bytes_and_mode":
            strict_issues.append(
                f"filesystem source is not committed byte/mode exact: "
                f"{row['path']}"
                f" ("
                f"{row.get('availability')}"
                f")"
            )
    git_refs, git_ref_issues = _resolve_git_path_refs(root, end_head, process_rows)
    object_reads, object_read_issues = _git_content_object_reads(root, process_rows, git_refs)
    strict_issues.extend(git_ref_issues)
    strict_issues.extend(object_read_issues)
    matched_result_hashes = {
        item["process_result_sha256"]
        for ref in git_refs
        for item in ref.get("matched_exact_content_results", [])
    }
    matched_result_hashes.update(row.get("observed_process_result_sha256") for row in object_reads)
    unclassified_content = []
    for row in process_rows:
        if not row["argv"] or Path(row["argv"][0]).name != "git":
            continue
        if _git_command(row["argv"]) in {"show", "cat-file", "archive"} and row["stdout"].get(
            "bytes", 0
        ):
            metadata_show = (
                _git_command(row["argv"]) == "show"
                and "-s" in row["argv"]
                and any(arg.startswith("--format=") for arg in row["argv"])
            )
            if not metadata_show and sha256(stable_json(row)) not in matched_result_hashes:
                unclassified_content.append(sha256(stable_json(row)))
    if unclassified_content:
        strict_issues.append(
            f"Git content-result groups lack an exact path/object binding: "
            f"{unclassified_content[:4]}"
        )
    environment = environment_profile(root, trace.modules_before_trace)
    if environment["third_party_module_count"] or environment["unbound_external_module_count"]:
        strict_issues.append(
            "non-standard-library modules imported during the build lack a pinned "
            "runtime dependency record"
        )
    object_format = _git_bytes(root, "rev-parse", "--show-object-format").decode("ascii").strip()
    closure_controls = source_closure_controls(
        source_paths, records, process_rows, git_refs, object_reads
    )
    closure = {
        "schema": "policyos.e02.q0_runtime_source_read_closure.r7.v1",
        "status": "SOURCE_BOUND_CURRENT_HEAD"
        if not strict_issues
        else "LOCAL_READBACK_ONLY_NOT_SOURCE_REGISTERED",
        "source_commit": end_head,
        "source_tree": end_tree,
        "git_object_format": object_format,
        "filesystem_source_count": len(records),
        "git_process_result_group_count": len(process_rows),
        "git_process_result_invocation_count": result_count,
        "git_path_reference_count": len(git_refs),
        "git_object_only_read_count": len(object_reads),
        "read_property": (
            "complete observed filesystem source opens and child-process results, "
            "including effective parameters bound from the captured real Popen "
            "signature, exact communicate input arguments, and observed "
            "Python-stream stdin writes; only a truly omitted stdin default is "
            "sealed to DEVNULL, while explicit inherited/file/descriptor streams "
            "and descriptor escapes remain fail-closed residuals; Git commit:path "
            "references carry resolved commit, path, mode, object id, "
            "availability, reachability, byte count and SHA-256, with no payload "
            "copies"
        ),
        "environment_profile": environment,
        "files": records,
        "git_process_results": process_rows,
        "git_path_references": git_refs,
        "git_object_only_reads": object_reads,
        "strict_admission_issues": strict_issues,
        "qualification": (
            "source-read closure only; outcomes remain UNRUN, whole-criterion "
            "alignment remains not_established, formal G remains not_adjudicated"
        ),
    }
    closure_raw = stable_json(closure)
    closure_sha = sha256(closure_raw)
    trace_json = trace.as_json(sorted(source_paths))
    trace_json["source_commit_at_start"] = start_head
    trace_json["source_tree_at_start"] = start_tree
    trace_json["source_commit_at_end"] = end_head
    trace_json["source_tree_at_end"] = end_tree
    trace_json["runtime_environment_profile"] = environment
    trace_json["git_path_reference_count"] = len(git_refs)
    trace_json["git_object_only_read_count"] = len(object_reads)
    trace_raw = stable_json(trace_json)
    snapshot = packet["registration"]["source_snapshot"]
    snapshot["source_snapshot_status_before_r7"] = snapshot["status"]
    snapshot["status"] = (
        "committed_source_read_closure_not_final_freeze"
        if not strict_issues
        else "local_readback_only_prototype_snapshot"
    )
    snapshot["files"] = records
    snapshot["runtime_read_closure"] = {
        "path": MANIFEST_PATH.as_posix(),
        "sha256": closure_sha,
        "filesystem_source_count": len(records),
        "git_path_reference_count": len(git_refs),
        "trace_path": TRACE_PATH.as_posix(),
        "trace_sha256": sha256(trace_raw),
        "property": closure["read_property"],
    }
    packet["registration"]["source_read_closure_r7"] = {
        "status": closure["status"],
        "manifest_path": MANIFEST_PATH.as_posix(),
        "manifest_sha256": closure_sha,
        "trace_path": TRACE_PATH.as_posix(),
        "trace_sha256": sha256(trace_raw),
        "filesystem_source_count": len(records),
        "git_process_result_group_count": len(process_rows),
        "git_path_reference_count": len(git_refs),
        "git_object_only_read_count": len(object_reads),
        "candidate_registered_tool_target": PROPOSED_REGISTERED_TOOL.as_posix(),
        "candidate_tool_source_currently_executed": self_rel,
        "candidate_tool_target_preimage": "ABSENT_VERIFIED; root retains source writer authority",
        "environment_profile": environment,
        "strict_admission_issues": strict_issues,
        "qualification": (
            "R7 dual-plane source-read closure prototype; no row is promoted to a "
            "current result or closure"
        ),
    }
    packet["registration"]["candidate_evaluation"] = "UNRUN for all 291 occurrences"
    packet["registration"]["criterion_owner_alignment"] = (
        "not_established for all 291 occurrences; scoped owner assertion remains separate"
    )
    packet["registration"]["formal_G"] = "not_adjudicated"
    packet["registration"]["formal_closure_ids"] = []
    controls = json.loads(controls_raw)
    controls["source_read_closure_r7"] = closure_controls
    controls["source_read_closure_admission"] = {
        "status": "PASS" if not strict_issues else "RED_SOURCE_INPUTS_NOT_REGISTERED",
        "filesystem_source_count": len(records),
        "git_process_result_group_count": len(process_rows),
        "git_path_reference_count": len(git_refs),
        "git_object_only_read_count": len(object_reads),
        "strict_issue_count": len(strict_issues),
        "strict_issues": strict_issues,
        "property": (
            "live filesystem plus captured Git result closure, not registry "
            "fields or status markers"
        ),
    }
    controls_raw = stable_json(controls)
    packet["registration_controls_ref"] = {
        "schema": controls["schema"],
        "path": controls_path.as_posix(),
        "sha256": sha256(controls_raw),
        "qualification": (
            "paired control output from this exact regeneration; source and "
            "semantic status remain separately qualified"
        ),
    }
    require(
        packet["registration_controls_ref"]["sha256"] == sha256(controls_raw),
        "report control pointer does not bind the exact paired controls bytes",
    )
    report_raw = stable_json(packet)
    check = {
        "schema": "policyos.e02.q0_runtime_source_read_closure_check.r7.v1",
        "status": "PASS_LOCAL_BEHAVIORAL_CONTROLS_SOURCE_ADMISSION_RED"
        if strict_issues
        else "PASS_SOURCE_READ_CLOSURE",
        "source_commit": end_head,
        "source_tree": end_tree,
        "report_sha256": sha256(report_raw),
        "controls_sha256": sha256(controls_raw),
        "paired_controls_pointer": {
            "path": packet["registration_controls_ref"]["path"],
            "sha256": packet["registration_controls_ref"]["sha256"],
            "matches_control_bytes": packet["registration_controls_ref"]["sha256"]
            == sha256(controls_raw),
        },
        "closure_manifest_sha256": closure_sha,
        "trace_sha256": sha256(trace_raw),
        "report_denominator": {
            "finding_ids": packet["denominator"]["finding_ids"],
            "canonical_occurrences": packet["denominator"]["canonical_occurrences"],
            "task_assignment_refs": packet["denominator"]["distinct_task_assignment_refs"],
            "expanded_occurrence_routes": packet["denominator"]["expanded_occurrence_route_refs"],
        },
        "status_preservation": {
            "historical_source_author_closed_ids": r3_receipt[
                "historical_source_author_closed_ids"
            ],
            "candidate_states": {"UNRUN": 291},
            "criterion_owner_alignment": "not_established for all 291 occurrences",
            "formal_G": "not_adjudicated",
            "formal_closure_ids": [],
        },
        "source_read_admission_issues": strict_issues,
        "qualification": (
            "local report build plus dual-plane source closure controls; semantic "
            "outcomes remain unadjudicated"
        ),
    }
    return {
        "report": report_raw,
        "controls": controls_raw,
        "trace": trace_raw,
        "manifest": closure_raw,
        "check": stable_json(check),
        "receipt": r3_receipt,
        "closure": closure,
        "strict_issues": strict_issues,
    }


def write_new(root: Path, path: Path, raw: bytes, *, replace_local: bool = False) -> None:
    """Write one declared raw output, replacing only on an explicit refresh."""
    full = root / path
    if full.is_symlink() or (full.exists() and not replace_local):
        raise ReadClosureError(f"refusing to overwrite existing output: {path.as_posix()}")
    if replace_local and not _is_relative_to(full.resolve(), (root / R7_DIR).resolve()):
        raise ReadClosureError("refresh may replace files only inside the declared R7 raw lease")
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(raw)


def main(argv: list[str] | None = None) -> int:
    """Emit or check the full source-bound report through caller-selected paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--emit", action="store_true", help="write report and controls")
    modes.add_argument(
        "--check", action="store_true", help="recompute and compare report and controls"
    )
    modes.add_argument(
        "--self-check",
        action="store_true",
        help="run local controls without claiming source registration",
    )
    parser.add_argument("--output", type=Path, help="new report path inside LOCAL/crosswalk")
    parser.add_argument(
        "--controls-output", type=Path, help="new controls path inside LOCAL/crosswalk"
    )
    parser.add_argument(
        "--self-check-artifact-dir",
        type=Path,
        help="new raw output directory for this immutable self-check",
    )
    args = parser.parse_args(argv)
    root = repo_root()
    if args.self_check:
        artifact_dir = args.self_check_artifact_dir or R7_DIR
        require(
            not artifact_dir.is_absolute(),
            "self-check artifact directory must be repository-relative",
        )
        artifact_full = root / artifact_dir
        require(
            not artifact_full.exists() and not artifact_full.is_symlink(),
            "self-check artifact directory already exists",
        )
        try:
            artifact_full.parent.resolve(strict=True).relative_to(
                (root / R7_DIR).resolve(strict=True)
            )
        except (OSError, ValueError) as exc:
            raise ReadClosureError(
                "self-check outputs must remain inside the R7 raw lease"
            ) from exc
        global DEFAULT_REPORT, DEFAULT_CONTROLS, TRACE_PATH, MANIFEST_PATH, CHECK_PATH
        DEFAULT_REPORT = artifact_dir / "generated-full-report.json"
        DEFAULT_CONTROLS = artifact_dir / "generated-consumer-controls.json"
        TRACE_PATH = artifact_dir / "runtime-read-trace.json"
        MANIFEST_PATH = artifact_dir / "source-read-closure.json"
        CHECK_PATH = artifact_dir / "source-closure-check.json"
    controls_destination = args.controls_output or DEFAULT_CONTROLS
    result = build_r7(root, strict=args.check or args.emit, controls_path=controls_destination)
    if args.self_check:
        outputs = (
            (DEFAULT_REPORT, result["report"]),
            (DEFAULT_CONTROLS, result["controls"]),
            (TRACE_PATH, result["trace"]),
            (MANIFEST_PATH, result["manifest"]),
            (CHECK_PATH, result["check"]),
        )
        for path, raw in outputs:
            write_new(root, path, raw, replace_local=False)
        sys.stdout.write(
            json.dumps(
                {
                    "schema": "policyos.e02.q0_full_report_registration_r7_self_check.v1",
                    "status": (
                        "PASS_LOCAL_CONTROLS_SOURCE_ADMISSION_RED"
                        if result["strict_issues"]
                        else "PASS_SOURCE_READ_CLOSURE"
                    ),
                    "report_path": DEFAULT_REPORT.as_posix(),
                    "report_sha256": sha256(result["report"]),
                    "controls_path": DEFAULT_CONTROLS.as_posix(),
                    "controls_sha256": sha256(result["controls"]),
                    "trace_path": TRACE_PATH.as_posix(),
                    "trace_sha256": sha256(result["trace"]),
                    "manifest_path": MANIFEST_PATH.as_posix(),
                    "manifest_sha256": sha256(result["manifest"]),
                    "filesystem_source_count": result["closure"]["filesystem_source_count"],
                    "git_path_reference_count": result["closure"]["git_path_reference_count"],
                    "strict_admission_issues": result["strict_issues"],
                    "qualification": (
                        "virtual R7 source-closure candidate; not registered, not final freeze, "
                        "no semantic status promoted"
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        return 0
    if args.output is None or args.controls_output is None:
        raise ReadClosureError("--output and --controls-output are required for --emit/--check")
    absolute: list[Path] = []
    for relative in (args.output, args.controls_output):
        require(not relative.is_absolute(), "output paths must be repository-relative")
        full = root / relative
        require(
            full.parent.is_dir() and not full.parent.is_symlink(),
            f"output parent must exist and not be symlink: {relative}",
        )
        try:
            full.parent.resolve(strict=True).relative_to(
                (root / LOCAL / "crosswalk").resolve(strict=True)
            )
        except (OSError, ValueError) as exc:
            raise ReadClosureError("outputs must be inside LOCAL/crosswalk") from exc
        absolute.append(full)
    require(absolute[0] != absolute[1], "report and controls output paths must differ")
    if result["strict_issues"]:
        sys.stdout.write(
            json.dumps(
                {
                    "status": "RED_SOURCE_INPUTS_NOT_REGISTERED",
                    "source_commit": result["closure"]["source_commit"],
                    "source_tree": result["closure"]["source_tree"],
                    "strict_issues": result["strict_issues"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        return 1
    expected = {absolute[0]: result["report"], absolute[1]: result["controls"]}
    if args.emit:
        require(
            all(not path.exists() and not path.is_symlink() for path in expected),
            "--emit refuses to overwrite existing report files",
        )
        for path, raw in expected.items():
            path.write_bytes(raw)
    for path, raw in expected.items():
        require(
            path.is_file() and not path.is_symlink() and path.read_bytes() == raw,
            f"generated report byte drift: {path.relative_to(root)}",
        )
    sys.stdout.write(
        json.dumps(
            {
                "status": "PASS_SOURCE_READ_CLOSURE",
                "source_commit": result["closure"]["source_commit"],
                "source_tree": result["closure"]["source_tree"],
                "report_sha256": sha256(result["report"]),
                "controls_sha256": sha256(result["controls"]),
                "source_file_count": result["closure"]["filesystem_source_count"],
                "git_path_reference_count": result["closure"]["git_path_reference_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
