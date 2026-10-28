"""Observe real federation pytest or cold-worker execution in the deciding PID.

This is a test instrument, not an authority issuer. Receipts bind observed compile,
exec and call events to actual source bytes. Native execution and interpreter
bootstrap before this instrument are disclosed boundaries, not inferred reads.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
import runpy
import sys
import sysconfig
import time
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _package_info(name: str) -> dict[str, Any]:
    try:
        version = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        version = None
    return {"version": version, "origin": getattr(sys.modules.get(name), "__file__", None)}


def _snapshot(phase: str, cache: Path) -> dict[str, Any]:
    return {
        "phase": phase,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "executable": sys.executable,
        "dont_write_bytecode_flag": sys.flags.dont_write_bytecode,
        "dont_write_bytecode": sys.dont_write_bytecode,
        "pycache_prefix": sys.pycache_prefix,
        "cache_files": sorted(path.relative_to(cache).as_posix() for path in cache.rglob("*")),
        "safe_environment": {
            name: os.environ.get(name)
            for name in (
                "PYTHONHOME",
                "PYTHONPATH",
                "PYTEST_ADDOPTS",
                "PYTEST_PLUGINS",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                "PYTHONPYCACHEPREFIX",
            )
        },
        "semantic_control_names": sorted(
            name for name in os.environ if name.startswith(("E02_", "POLISYOS_"))
        ),
    }


def _load_code_identity(
    root: Path, expected: dict[str, str]
) -> tuple[Callable[[types.CodeType], str] | None, dict[str, Any]]:
    """Load the shared helper from its pinned physical bytes before observation."""
    path = (root / "tests/_helpers/code_identity.py").resolve()
    expected_value = expected.get("tests/_helpers/code_identity.py")
    record: dict[str, Any] = {
        "path": str(path),
        "expected": expected_value,
        "status": "not_established",
    }
    try:
        if not path.is_relative_to(root.resolve()):
            raise ValueError("code identity helper resolves outside checkout")
        content = path.read_bytes()
        sha = _sha(content)
        blob = hashlib.sha1(
            b"blob " + str(len(content)).encode() + b"\0" + content, usedforsecurity=False
        ).hexdigest()
        actual = "git:" + blob if expected_value and expected_value.startswith("git:") else sha
        record.update(source_sha256=sha, git_blob=blob)
        if not expected_value or expected_value != actual:
            raise ValueError("helper bytes absent from or differ from declared pinned input")
        namespace: dict[str, Any] = {"__name__": "_c93_shared_code_identity", "__file__": str(path)}
        # Execute the exact hash-admitted helper bytes rather than re-reading a mutable import path.
        exec(compile(content, str(path), "exec", dont_inherit=True), namespace)  # noqa: S102
        function = namespace["code_fingerprint"]
        if not callable(function):
            raise TypeError("shared code identity helper is not callable")
        record.update(status="matched_declared_source", scheme=namespace["CODE_FINGERPRINT_SCHEME"])
        return function, record
    except Exception as exc:
        record["reason"] = repr(exc)
        return None, record


class ExecutionObserver:
    """Collect project compile/exec/read/call facts without exporting input bytes."""

    def __init__(
        self,
        root: Path,
        expected: dict[str, str],
        inputs: list[Path],
        code_fingerprint: Callable[[types.CodeType], str] | None,
        code_identity_scheme: str | None = None,
    ) -> None:
        self.root = root.resolve()
        self.expected = expected
        self.inputs = {path.resolve() for path in inputs}
        self.code_fingerprint = code_fingerprint
        self.code_identity_scheme = code_identity_scheme
        runtime_paths = sysconfig.get_paths()
        self.environment_roots = {
            (self.root / ".venv").resolve(),
            (self.root / ".git").resolve(),
            *(
                Path(runtime_paths[key]).resolve()
                for key in ("purelib", "platlib")
                if runtime_paths.get(key)
            ),
        }
        self.busy = False
        self.reads: dict[str, dict[str, Any]] = {}
        self.compiles: dict[str, list[dict[str, Any]]] = {}
        self.calls: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self.boundaries: set[str] = {
            "native execution is outside Python call/compile observation",
            "profile is current-thread only; other threads require separate observation",
            "compile-event attribution beyond finite code-object/source matching is unobserved",
        }
        self.configurations: list[dict[str, Any]] = []
        self.reports: list[dict[str, Any]] = []
        self.nodes: list[str] = []
        self.origins: dict[tuple[str, str], Path | None] = {}
        self.code_hashes: dict[int, str | None] = {}
        self.code_objects: list[Any] = []
        self.recompiled: dict[str, dict[str, Any]] = {}
        self.initial_project_modules = sorted(
            name for name in sys.modules if name == "polisyos" or name.startswith("polisyos.")
        )

    def require_pristine_product_imports(self) -> None:
        """Refuse a deciding process whose product modules preceded observation."""
        if self.initial_project_modules:
            raise RuntimeError("Product modules already imported before deciding observer")

    def _project(self, filename: str, module: str = "") -> Path | None:
        identity = (filename, module)
        if identity in self.origins:
            return self.origins[identity]
        project_name = module in {"polisyos", "tests", "tools"} or module.startswith(
            ("polisyos.", "tests.", "tools.")
        )
        if filename.startswith("<"):
            if project_name:
                self.boundaries.add(f"dynamic code filename {filename} in {module}")
            self.origins[identity] = None
            return None
        path = Path(filename).resolve()
        parts = path.parts
        installed_candidate = any(
            parts[index] in {"site-packages", "dist-packages"} and parts[index + 1] == "polisyos"
            for index in range(len(parts) - 1)
        )
        in_environment = any(path.is_relative_to(root) for root in self.environment_roots)
        if project_name or installed_candidate:
            if in_environment or installed_candidate or not path.is_relative_to(self.root):
                self.boundaries.add(f"external or installed project-origin candidate: {path}")
            self.origins[identity] = path
            return path
        if path.is_relative_to(self.root) and not in_environment:
            self.origins[identity] = path
            return path
        self.origins[identity] = None
        return None

    def _read(self, path: Path, reason: str) -> dict[str, Any]:
        key = str(path)
        if key not in self.reads:
            content = path.read_bytes()
            relative = (
                path.relative_to(self.root).as_posix() if path.is_relative_to(self.root) else None
            )
            self.reads[key] = {
                "path": key,
                "relative_path": relative,
                "sha256": _sha(content),
                "bytes": len(content),
                "reasons": [],
                "inside_checkout": relative is not None,
                "git_blob": hashlib.sha1(
                    b"blob " + str(len(content)).encode() + b"\0" + content, usedforsecurity=False
                ).hexdigest(),
            }
        row = self.reads[key]
        if reason not in row["reasons"]:
            row["reasons"].append(reason)
        return row

    def audit(self, event: str, args: tuple[Any, ...]) -> None:
        if self.busy:
            return
        self.busy = True
        try:
            if event == "compile" and isinstance(args[1], str):
                path = self._project(args[1])
                if path is not None:
                    source = args[0]
                    if isinstance(source, (bytes, str)):
                        raw = source.encode() if isinstance(source, str) else source
                        entry = {"kind": "source", "sha256": _sha(raw), "bytes": len(raw)}
                    elif isinstance(source, ast.AST):
                        entry = {"kind": "AST_transform", "sha256": _sha(ast.dump(source).encode())}
                    else:
                        entry = {"kind": type(source).__name__}
                    self.compiles.setdefault(str(path), []).append(entry)
                    if path.is_file():
                        disk = self._read(path, "compile")
                        if entry["kind"] == "source" and entry["sha256"] != disk["sha256"]:
                            self.boundaries.add(
                                f"compile input differs from on-disk source: {path}"
                            )
                        elif entry["kind"] != "source":
                            self.boundaries.add(f"transformed or non-source compile input: {path}")
            elif event == "exec":
                code = args[0]
                path = self._project(code.co_filename)
                if path is not None and path.is_file():
                    self._read(path, "exec")
                    if str(path) not in self.compiles:
                        self.boundaries.add(f"exec without observed source compile: {path}")
            elif event == "subprocess.Popen":
                self.boundaries.add("spawned descendant requires its own observer receipt")
            elif event == "open" and isinstance(args[0], (str, bytes)):
                path = Path(os.fsdecode(args[0])).resolve()
                mode = args[1]
                if (path in self.inputs or self._project(str(path)) is not None) and path.is_file():
                    flags = args[2] if len(args) > 2 and isinstance(args[2], int) else None
                    readable = (isinstance(mode, str) and ("r" in mode or "+" in mode)) or (
                        flags is not None and flags & os.O_ACCMODE != os.O_WRONLY
                    )
                    if readable:
                        self._read(path, "open_read")
        finally:
            self.busy = False

    def _source_code_binding(
        self, path: Path, filename: str, code_sha: str | None, source: dict[str, Any]
    ) -> dict[str, Any]:
        """Match a called product function to nested code from its actual pinned file.

        Compilation inspects bytes only; it never executes the compiled code. A
        mismatch is an unresolved boundary, not proof of different semantics.
        """
        if self.code_fingerprint is None or code_sha is None:
            return {"status": "not_established", "reason": "shared code identity unavailable"}
        relative = source["relative_path"]
        if relative is None or not relative.startswith("src/polisyos/") or path.suffix != ".py":
            return {
                "status": "not_established",
                "reason": "outside ordinary checkout product Python",
            }
        expected = self.expected.get(relative)
        observed = (
            "git:" + source["git_blob"]
            if expected and expected.startswith("git:")
            else source["sha256"]
        )
        if expected is None or expected != observed:
            return {
                "status": "not_established",
                "reason": "source absent from or differs from pinned inputs",
            }
        identity = str(path) + "\0" + filename
        if identity not in self.recompiled:
            try:
                data = path.read_bytes()
                if _sha(data) != source["sha256"]:
                    raise ValueError("source changed before independent compile")
                module = compile(
                    data, filename, "exec", dont_inherit=True, optimize=sys.flags.optimize
                )
                pending = [module]
                hashes: set[str] = set()
                while pending:
                    item = pending.pop()
                    hashes.add(self.code_fingerprint(item))
                    pending.extend(
                        value for value in item.co_consts if isinstance(value, types.CodeType)
                    )
                self.recompiled[identity] = {
                    "hashes": hashes,
                    "source_sha256": _sha(data),
                    "error": None,
                }
            except Exception as exc:
                self.recompiled[identity] = {
                    "hashes": set(),
                    "source_sha256": source["sha256"],
                    "error": repr(exc),
                }
        witness = self.recompiled[identity]
        if code_sha not in witness["hashes"]:
            return {
                "status": "not_established",
                "reason": "called code does not match independently compiled source",
                "compile_error": witness["error"],
            }
        return {
            "status": "matched_declared_source",
            "source_sha256": witness["source_sha256"],
            "expected": expected,
            "filename": filename,
            "resolved_path": str(path),
            "optimize": sys.flags.optimize,
            "dont_inherit": True,
            "code_sha256": code_sha,
        }

    def profile(self, frame: Any, event: str, _argument: Any) -> None:
        if event != "call" or self.busy:
            return
        self.busy = True
        try:
            code = frame.f_code
            module = str(frame.f_globals.get("__name__", ""))
            path = self._project(code.co_filename, module)
            if path is None:
                return
            if not path.is_file():
                self.boundaries.add(
                    f"called project-origin candidate is not a readable file: {path}"
                )
                return
            source = self._read(path, "python_call")
            if id(code) not in self.code_hashes:
                self.code_objects.append(code)
                try:
                    self.code_hashes[id(code)] = (
                        self.code_fingerprint(code) if self.code_fingerprint is not None else None
                    )
                except Exception as exc:
                    self.code_hashes[id(code)] = None
                    self.boundaries.add(f"code fingerprint unavailable for {path}: {exc!r}")
            code_sha = self.code_hashes[id(code)]
            key = (str(path), module, code.co_qualname, code_sha or f"unavailable:{id(code)}")
            if key not in self.calls:
                self.calls[key] = {
                    "path": str(path),
                    "module": module,
                    "pid": os.getpid(),
                    "filename": code.co_filename,
                    "qualname": code.co_qualname,
                    "first_line": code.co_firstlineno,
                    "code_sha256": code_sha,
                    "code_identity_scheme": self.code_identity_scheme if code_sha else None,
                    "source_sha256": source["sha256"],
                    "calls": 0,
                    "source_code_binding": self._source_code_binding(
                        path, code.co_filename, code_sha, source
                    ),
                }
            self.calls[key]["calls"] += 1
        finally:
            self.busy = False

    def pytest_configure(self, config: Any) -> None:
        plugins = []
        for name, plugin in config.pluginmanager.list_name_plugin():
            if plugin is None:
                continue
            module_name = getattr(plugin, "__module__", getattr(plugin, "__name__", ""))
            module = sys.modules.get(module_name)
            plugins.append(
                {"name": name, "module": module_name, "origin": getattr(module, "__file__", None)}
            )
        self.configurations.append(
            {
                **_snapshot("pytest_configure", Path(sys.pycache_prefix)),
                "plugins": plugins,
                "inipath": str(config.inipath) if config.inipath else None,
                "rootpath": str(config.rootpath),
                "invocation_args": list(config.invocation_params.args),
                "effective_addopts": list(config.getini("addopts")),
                "effective_testpaths": list(config.getini("testpaths")),
            }
        )

    def pytest_sessionstart(self, session: Any) -> None:
        self.configurations.append(
            {
                **_snapshot("pytest_sessionstart", Path(sys.pycache_prefix)),
                "args": list(session.config.args),
            }
        )

    def pytest_collection_finish(self, session: Any) -> None:
        self.nodes = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report: Any) -> None:
        self.reports.append(
            {
                "nodeid": report.nodeid,
                "when": report.when,
                "outcome": report.outcome,
                "duration": report.duration,
            }
        )

    def result(self) -> dict[str, Any]:
        mismatches = []
        unbound = []
        for path, row in self.reads.items():
            relative = row["relative_path"]
            expected = self.expected.get(relative) if relative else None
            if relative is None:
                # Installed project modules are not silently called external.
                self.boundaries.add(f"project execution outside checkout: {path}")
            actual = (
                "git:" + row["git_blob"]
                if expected and expected.startswith("git:")
                else row["sha256"]
            )
            if expected is not None and expected != actual:
                mismatches.append({"path": path, "expected": expected, "actual": row["sha256"]})
            if expected is None and any(
                reason in row["reasons"] for reason in ("compile", "exec", "python_call")
            ):
                unbound.append(path)
            if _sha(Path(path).read_bytes()) != row["sha256"]:
                mismatches.append(
                    {"path": path, "reason": "source changed during deciding process"}
                )
        return {
            "actual_readset": sorted(self.reads.values(), key=lambda row: row["path"]),
            "compile_contexts": self.compiles,
            "executed_project_calls": sorted(
                self.calls.values(),
                key=lambda row: (
                    row["path"],
                    row["module"],
                    row["qualname"],
                    row["code_sha256"] or "",
                ),
            ),
            "source_mismatches": mismatches,
            "unobserved_boundaries": sorted(self.boundaries),
            "execution_binding": "not_established_until_required_actual_caller_rows_reconciled",
            "unbound_project_sources": sorted(unbound),
            "pytest_observations": self.configurations,
            "selected_nodes": self.nodes,
            "test_phases": self.reports,
        }


def main() -> int:
    """Run pytest or a declared cold script inside the observed interpreter."""
    original_argv = list(sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-sources", required=True, type=Path)
    parser.add_argument("--input", action="append", type=Path, default=[])
    parser.add_argument("--phase", default="positive")
    parser.add_argument("--script", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    cache = Path(sys.pycache_prefix or "")
    if (
        not sys.dont_write_bytecode
        or not sys.flags.dont_write_bytecode
        or not cache.is_dir()
        or any(cache.iterdir())
    ):
        raise SystemExit("A fresh -B process and initially empty private cache are required")
    before = _snapshot("before_product_and_pytest_import", cache)
    if (
        any(
            before["safe_environment"].get(name)
            for name in (
                "PYTHONHOME",
                "PYTHONPATH",
                "PYTEST_ADDOPTS",
                "PYTEST_PLUGINS",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
            )
        )
        or before["semantic_control_names"]
    ):
        raise SystemExit("Undeclared inherited pytest/Python/product semantic controls")
    expected_bytes = args.expected_sources.read_bytes()
    expected = json.loads(expected_bytes)
    code_fingerprint, helper_record = _load_code_identity(args.project_root, expected)
    observer = ExecutionObserver(
        args.project_root, expected, args.input, code_fingerprint, helper_record.get("scheme")
    )
    observer.require_pristine_product_imports()
    observer.boundaries.add(
        "shared code identity helper bootstrap precedes audit/profile installation"
    )
    if helper_record["status"] != "matched_declared_source":
        observer.boundaries.add("shared code identity helper source binding not established")
    sys.addaudithook(observer.audit)
    sys.setprofile(observer.profile)
    arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    exit_code = 1
    error = None
    started = time.monotonic()
    try:
        if args.script:
            sys.argv = [str(args.script), *arguments]
            runpy.run_path(str(args.script), run_name="__main__")
            exit_code = 0
        else:
            import pytest

            exit_code = int(pytest.main(arguments, plugins=[observer]))
    except SystemExit as exc:
        exit_code = int(exc.code or 0) if isinstance(exc.code, (int, type(None))) else 1
        if exit_code:
            error = repr(exc)
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        sys.setprofile(None)
        observer.busy = True
        observation = observer.result()
        if observation["source_mismatches"]:
            exit_code = 3
        receipt = {
            "schema": "policyos.federation.execution-observer/1",
            "phase": args.phase,
            "pid": os.getpid(),
            "pre_import": before,
            "post_run": _snapshot("post_run", cache),
            "elapsed_seconds": time.monotonic() - started,
            "exit_code": exit_code,
            "error": error,
            "actual_argv": original_argv,
            "executed_argv": list(sys.argv),
            "observer_arguments": arguments,
            "profile": {
                "script": str(args.script) if args.script else None,
                "phase": args.phase,
                "project_root": str(args.project_root.resolve()),
                "inputs": [str(x.resolve()) for x in args.input],
            },
            "loaded_project_modules": sorted(
                (
                    {"name": name, "origin": getattr(module, "__file__", None)}
                    for name, module in sys.modules.items()
                    if name == "polisyos" or name.startswith("polisyos.")
                ),
                key=lambda row: row["name"],
            ),
            "observer_source_sha256": _sha(Path(__file__).read_bytes()),
            "code_identity_helper": helper_record,
            "expected_sources_sha256": _sha(expected_bytes),
            "packages": {
                name: _package_info(name)
                for name in ("duckdb", "numpy", "pandas", "pyarrow", "pydantic", "pytest")
            },
            **observation,
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
