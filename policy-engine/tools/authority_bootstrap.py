"""Start a fresh, source-recorded local tooling process.

The host launch is a bounded evidence producer. It does not appoint an authority
profile, issue a deployment identity, or seal the confidence ledger. The initial
profile records local measurements and leaves unsupported providers, state and
through-use protection unavailable. Invoke directly with ``python -I -S -B`` for
an isolated host; a normal console-script parent cannot attest its own startup.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import importlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from types import CodeType, FunctionType, GetSetDescriptorType, ModuleType
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest

_PRODUCT = Path(__file__).resolve().parents[1]
_REPOSITORY = _PRODUCT.parent
_HOST_MODULE = "_polisyos_early_host"
_CAPTURE_MODULE = "_polisyos_loaded_source_capture"
_HOST_SLOT = "_polisyos_loaded_host_v1"
_HOST_SESSION: object | None = None
_MAX_MESSAGE = 8 * 1024 * 1024
_ENTRY_TARGETS = {
    "tools": ("tools.cli", "main", True),
    "runtime": ("tools.ops_runners.runtime_cli", "main", True),
    "foundry": ("tools.ops_runners.runtime_cli", "foundry_main", True),
    "server": ("polisyos.runtime.http.profiled_server", "main", True),
    "polisy": ("polisyos.foundry.plugins.cli", "main", False),
    "causal-capabilities": ("polisyos.foundry.methods.catalog.causal.capabilities", "main", False),
    "ukraine-data": ("tools.ops_runners.ukraine_data_cli", "main", True),
}

# These values are a narrowly measured local reference, not a signed build
# attestation or a complete dependency profile. The wheel/member relationships
# were measured independently against the selected locked wheel bytes.
_LOCAL_MEASUREMENTS = {
    "python_executable": "14a816f493d6b12ff5f1edec695edcb3590d683c3a904f9e6ea8c171c7a6f403",
    "libpython": "d8c6a79cb92d8551d067d8ae72a0c42fcba46482aad5532e851c5e29619c1ca7",
    "typing": "b474bb90d72d4ea28d0b4635a4fbc42ac54e459b8468a01034f2773656e47a00",
    "annotationlib": "3b8a0f169da1855b873179e2242ea2229413644c738c5e2713864df7206dbc19",
    "functools": "046ec9660146db48862c7b22c78e2ef3818eaed6920e5cbf35f551ef09fec6cd",
    "pydantic/__init__.py": "e62127278c07bf5384cdd2903f368a69929f3b8a524000bae4e0eb608ebf4bc6",
    "pydantic/_internal/_model_construction.py": (
        "c24f9b3460c026f76e686be7d14d3ff33125d06111bb4b2126f37cfd97e461ac"
    ),
    "pydantic_core/__init__.py": "9cad6292b75254af606a970aae9bff6e5ae9f0b08089cd63acafa391b60794d2",
    "pydantic_core/_pydantic_core.cpython-314-darwin.so": (
        "ac3118649cd44d45d951143cc152b34a82d524a499bf74d235a0f827ec3cd771"
    ),
    "uv.lock": "ccfdca0e741dc77795f5af61871af5d62e73feebf55c7ffb28cd16e55fe207e9",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_environment() -> dict[str, str]:
    """Exclude ambient Git repository, object and configuration overrides."""

    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(
        GIT_OPTIONAL_LOCKS="0",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_NO_REPLACE_OBJECTS="1",
    )
    return env


def _module_name(relative: str) -> str | None:
    path = Path(relative)
    if path.parts[:2] == ("src", "polisyos"):
        parts = list(path.parts[1:])
    elif path.parts and path.parts[0] == "tools":
        parts = list(path.parts)
    else:
        return None
    if not parts[-1].endswith(".py"):
        return None
    parts[-1] = parts[-1][:-3]
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts and all(part.isidentifier() for part in parts) else None


def _source_export_candidates(
    module_name: str, relative: str, content: bytes
) -> dict[str, set[str]]:
    """Derive possible provider bindings from this selected source, without importing it.

    These are candidates for retention, not evidence that an import ran or that
    its selected provider is trustworthy. Missing, dynamic and otherwise opaque
    lookups still need to be reconciled by the identity owner.
    """

    tree = ast.parse(content, filename=relative)
    package = module_name if relative.endswith("/__init__.py") else module_name.rpartition(".")[0]
    exports: dict[str, set[str]] = {}
    aliases: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.partition(".")[0]
                import_provider = alias.name if alias.asname else alias.name.partition(".")[0]
                aliases.setdefault(local, set()).add(import_provider)
        elif isinstance(node, ast.ImportFrom):
            try:
                provider = (
                    importlib.util.resolve_name("." * node.level + (node.module or ""), package)
                    if node.level
                    else node.module
                )
            except (ImportError, ValueError):
                continue
            if not provider:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                exports.setdefault(provider, set()).add(alias.name)
                aliases.setdefault(alias.asname or alias.name, set()).add(
                    f"{provider}.{alias.name}"
                )
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        names = [node.attr]
        value = node.value
        while isinstance(value, ast.Attribute):
            names.append(value.attr)
            value = value.value
        if not isinstance(value, ast.Name):
            continue
        names.reverse()
        for provider in aliases.get(value.id, ()):
            owner = ".".join((provider, *names[:-1]))
            exports.setdefault(owner, set()).add(names[-1])
    return exports


def _git(*arguments: str) -> bytes:
    # The local profile trusts this fixed Git executable; its output is still
    # checked against source bytes and is not an authority appointment.
    return subprocess.run(  # noqa: S603
        ["/usr/bin/git", "-C", str(_REPOSITORY), *arguments],
        check=True,
        capture_output=True,
        timeout=30,
        env=_git_environment(),
    ).stdout


def _selected_snapshot() -> tuple[
    dict[str, tuple[str, str]], dict[str, list[str]], list[str], dict[str, str], bytes, bytes
]:
    """Select tracked source bytes; compare host inputs and loaded files separately."""

    head = _git("rev-parse", "HEAD").strip().decode("ascii")
    tree = _git("rev-parse", "HEAD^{tree}").strip().decode("ascii")
    names = (
        "policy-engine/src/polisyos",
        "policy-engine/tools",
        "policy-engine/pyproject.toml",
        "policy-engine/uv.lock",
    )
    listing = _git("ls-tree", "-rz", "--full-tree", "HEAD", "--", *names)
    selected: list[tuple[str, str]] = []
    for row in listing.split(b"\0"):
        if not row:
            continue
        metadata, path_bytes = row.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split(" ")
        path = path_bytes.decode("utf-8")
        relative = path.removeprefix("policy-engine/")
        if _module_name(relative) is None and relative not in (
            "pyproject.toml",
            "uv.lock",
            "tools/authority",
        ):
            continue
        if kind != "blob" or mode not in ("100644", "100755"):
            raise RuntimeError("selected_source_mode_unsupported")
        selected.append((relative, oid))
    if not selected:
        raise RuntimeError("selected_source_snapshot_empty")
    # A fixed executable and verb stream only Git blobs for the selected tree.
    process = subprocess.Popen(  # noqa: S603
        ["/usr/bin/git", "-C", str(_REPOSITORY), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_git_environment(),
    )
    if process.stdin is None or process.stdout is None:
        raise RuntimeError("git_blob_stream_unavailable")
    sources: dict[str, tuple[str, str]] = {}
    exports: dict[str, set[str]] = {}
    unparsed: list[str] = []
    extras: dict[str, bytes] = {}
    try:
        for relative, oid in selected:
            process.stdin.write((oid + "\n").encode("ascii"))
            process.stdin.flush()
            header = process.stdout.readline().decode("ascii").strip().split(" ")
            if len(header) != 3 or header[0] != oid or header[1] != "blob":
                raise RuntimeError("selected_git_blob_unavailable")
            size = int(header[2])
            if size < 0 or size > 16 * 1024 * 1024:
                raise RuntimeError("selected_git_blob_size_unsupported")
            content = process.stdout.read(size)
            if len(content) != size or process.stdout.read(1) != b"\n":
                raise RuntimeError("selected_git_blob_incomplete")
            name = _module_name(relative)
            if name is not None:
                if name in sources:
                    raise RuntimeError("selected_module_name_ambiguous")
                sources[name] = (relative, _sha(content))
                try:
                    candidates = _source_export_candidates(name, relative, content)
                except (SyntaxError, ValueError):
                    unparsed.append(name)
                else:
                    for provider, bindings in candidates.items():
                        exports.setdefault(provider, set()).update(bindings)
            if relative in (
                "tools/authority",
                "tools/authority_bootstrap.py",
                "tools/loaded_execution_capture.py",
                "uv.lock",
                "pyproject.toml",
            ):
                source_path = _PRODUCT / relative
                if (
                    source_path.resolve(strict=True) != source_path
                    or source_path.read_bytes() != content
                ):
                    raise RuntimeError(f"selected_host_input_mismatch:{relative}")
                extras[relative] = content
    finally:
        with suppress(OSError):
            process.stdin.close()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise
    if process.returncode != 0 or set(extras) != {
        "tools/authority",
        "tools/authority_bootstrap.py",
        "tools/loaded_execution_capture.py",
        "uv.lock",
        "pyproject.toml",
    }:
        raise RuntimeError("selected_host_inputs_missing")
    if (
        _git("rev-parse", "HEAD").strip().decode("ascii") != head
        or _git("rev-parse", "HEAD^{tree}").strip().decode("ascii") != tree
    ):
        raise RuntimeError("selected_source_frame_changed")
    return (
        sources,
        {name: sorted(bindings) for name, bindings in sorted(exports.items()) if name in sources},
        sorted(unparsed),
        {
            "head": head,
            "tree": tree,
            "lock_sha256": _sha(extras["uv.lock"]),
            "pyproject_sha256": _sha(extras["pyproject.toml"]),
            "host_launcher_sha256": _sha(extras["tools/authority"]),
        },
        extras["tools/authority_bootstrap.py"],
        extras["tools/loaded_execution_capture.py"],
    )


def _measure_profile() -> dict[str, object]:
    """Compare named local assets with the independently retained local reference."""

    base = Path(sys.base_prefix)
    site = Path(sys.prefix) / "lib/python3.14/site-packages"
    paths = {
        "python_executable": Path(sys.executable).resolve(),
        "libpython": base / "lib/libpython3.14.dylib",
        "typing": base / "lib/python3.14/typing.py",
        "annotationlib": base / "lib/python3.14/annotationlib.py",
        "functools": base / "lib/python3.14/functools.py",
        "uv.lock": _PRODUCT / "uv.lock",
    }
    for name in _LOCAL_MEASUREMENTS:
        if name.startswith(("pydantic/", "pydantic_core/")):
            paths[name] = site / name
    rows: dict[str, object] = {}
    for role, path in paths.items():
        try:
            digest = _file_sha(path)
        except OSError:
            digest = None
        rows[role] = {
            "sha256": digest,
            "matches_local_reference": digest == _LOCAL_MEASUREMENTS[role],
        }
    return {
        "profile": "local-cpython-3.14.3-measurement-only",
        "flags": {
            "isolated": sys.flags.isolated,
            "no_site": sys.flags.no_site,
            "dont_write_bytecode": sys.flags.dont_write_bytecode,
            "optimize": sys.flags.optimize,
        },
        "implementation": sys.implementation.name,
        "version": tuple(sys.version_info[:3]),
        "assets": rows,
        "classification": "host_measured_not_independent_build_or_origin_proof",
        "wheel_member_reference": (
            "four selected installed files compared to full locked wheel archives; "
            "other members and actual loaded providers unqualified"
        ),
        "authority": False,
        "unresolved": (
            "host_appointment",
            "stdlib_native_build_mapping",
            "complete_provider_graph",
            "material_state",
            "protected_through_use",
        ),
    }


def _sanitized_environment() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PYTHON", "DYLD_", "LD_"))
        and key not in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS", "VIRTUAL_ENV"}
    }
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def _receive(channel: socket.socket) -> bytes:
    def exact(size: int) -> bytes:
        parts = bytearray()
        while len(parts) < size:
            part = channel.recv(size - len(parts))
            if not part:
                raise RuntimeError("host_channel_closed")
            parts.extend(part)
        return bytes(parts)

    size = int.from_bytes(exact(8), "big")
    if size <= 0 or size > _MAX_MESSAGE:
        raise RuntimeError("host_channel_message_size_invalid")
    return exact(size)


# The child executes this small bootstrap supplied as an argument by its actual
# parent, then compiles the exact host bytes delivered over the inherited socket.
_CHILD = r"""import base64, hashlib, json, os, socket, sys, types
fd = int(sys.argv[1])
channel = socket.socket(fileno=fd)
def read_exact(n):
    out = bytearray()
    while len(out) < n:
        block = channel.recv(n - len(out))
        if not block:
            raise RuntimeError("host_channel_closed")
        out.extend(block)
    return bytes(out)
n = int.from_bytes(read_exact(8), "big")
if n <= 0 or n > 8388608:
    raise RuntimeError("host_channel_message_size_invalid")
request = json.loads(read_exact(n))
if os.getppid() != request["parent_pid"]:
    raise RuntimeError("host_parent_mismatch")
source = base64.b64decode(request["host_source"], validate=True)
if hashlib.sha256(source).hexdigest() != request["host_sha256"]:
    raise RuntimeError("host_source_mismatch")
module = types.ModuleType("_polisyos_early_host")
module.__file__ = request["host_path"]
sys.modules[module.__name__] = module
host_code = compile(source, module.__file__, "exec", dont_inherit=True)
module.__dict__["_HOST_EXECUTION_CODE"] = host_code
exec(host_code, module.__dict__)
raise SystemExit(module._child_main(channel, request))
"""


def _launch(mode: str, argv: Sequence[str]) -> int:
    if (
        not (_PRODUCT / "src/polisyos").is_dir()
        or not (_PRODUCT / "uv.lock").is_file()
        or not (_PRODUCT / ".venv/bin/python").is_file()
    ):
        # Installed/source-export candidate use keeps its existing entry path.
        # It does not acquire a source-checkout host or an identity issuer.
        return _invoke_entry(mode, list(argv), candidate_reason="source_checkout_unavailable")
    try:
        (
            sources,
            exports,
            unparsed,
            source_frame,
            host_source,
            recorder_source,
        ) = _selected_snapshot()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"source execution evidence unavailable: {type(exc).__name__}", file=sys.stderr)
        return _invoke_entry(mode, list(argv), candidate_reason="source_snapshot_unavailable")
    parent, child = socket.socketpair()
    request = {
        "parent_pid": os.getpid(),
        "mode": mode,
        "argv": list(argv),
        "root": str(_PRODUCT),
        "source_frame": source_frame,
        "sources": sources,
        "exports": exports,
        "unparsed_sources": unparsed,
        "host_path": str(_PRODUCT / "tools/authority_bootstrap.py"),
        "host_source": base64.b64encode(host_source).decode("ascii"),
        "host_sha256": _sha(host_source),
        "recorder_path": str(_PRODUCT / "tools/loaded_execution_capture.py"),
        "recorder_source": base64.b64encode(recorder_source).decode("ascii"),
        "recorder_sha256": _sha(recorder_source),
        "parent_startup_isolated": bool(
            sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
        ),
    }
    payload = json.dumps(request, separators=(",", ":")).encode("utf-8")
    if len(payload) > _MAX_MESSAGE:
        raise RuntimeError("host_channel_message_size_invalid")
    process: subprocess.Popen[bytes] | None = None
    try:
        # Only the selected checkout interpreter receives the fixed child
        # trampoline; arguments are passed without a shell.
        process = subprocess.Popen(  # noqa: S603
            [
                str(_PRODUCT / ".venv/bin/python"),
                "-I",
                "-S",
                "-B",
                "-c",
                _CHILD,
                str(child.fileno()),
            ],
            cwd=str(_PRODUCT),
            env=_sanitized_environment(),
            pass_fds=(child.fileno(),),
        )
        child.close()
        parent.sendall(len(payload).to_bytes(8, "big") + payload)
        acknowledgement = bytearray()
        while len(acknowledgement) < len(b"installed\n"):
            block = parent.recv(len(b"installed\n") - len(acknowledgement))
            if not block:
                process.wait()
                raise RuntimeError("child_capture_installation_unavailable")
            acknowledgement.extend(block)
        if bytes(acknowledgement) not in (b"installed\n", b"candidate\n"):
            process.wait()
            raise RuntimeError("child_capture_installation_unavailable")
        return process.wait()
    except BaseException:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        raise
    finally:
        parent.close()
        child.close()


def _retained_recorder_surface(
    recorder: ModuleType, recorder_code: CodeType
) -> tuple[
    type[object],
    tuple[tuple[str, object], ...],
    tuple[tuple[str, object], ...],
    tuple[tuple[object, ...], ...],
    tuple[tuple[object, ...], ...],
]:
    """Retain the recorder's source-owned callable and class surface.

    Mutable values reachable from those bindings, external modules and use-time
    mutation ownership remain separate, unestablished premises.
    """

    recorder_type = recorder.__dict__["SourceExecutionCapture"]
    if not isinstance(recorder_type, type):
        raise RuntimeError("recorder_type_unavailable")
    code_tree: list[CodeType] = []
    pending = [recorder_code]
    while pending:
        code = pending.pop()
        code_tree.append(code)
        pending.extend(value for value in code.co_consts if type(value) is CodeType)
    descriptors: list[tuple[str, object]] = []
    referenced_names: set[str] = set()
    pending_functions: list[FunctionType] = []
    pending_classes: list[type[object]] = [recorder_type]
    seen_functions: set[int] = set()
    seen_classes: set[int] = set()
    function_holds: list[tuple[object, ...]] = []
    class_holds: list[tuple[object, ...]] = []

    def descriptor_functions(value: object) -> tuple[FunctionType, ...]:
        if type(value) is FunctionType:
            return (value,)
        if type(value) is property:
            return cast(
                "tuple[FunctionType, ...]",
                tuple(
                    function
                    for function in (value.fget, value.fset, value.fdel)
                    if function is not None
                ),
            )
        if type(value) is classmethod:
            return (cast("FunctionType", value.__func__),)
        if type(value) is staticmethod:
            return (cast("FunctionType", value.__func__),)
        return ()

    for name, value in type.__getattribute__(recorder_type, "__dict__").items():
        if type(value) not in (FunctionType, property, classmethod, staticmethod):
            continue
        functions = descriptor_functions(value)
        if type(name) is not str or any(
            type(function) is not FunctionType
            or not any(function.__code__ is code for code in code_tree)
            or function.__globals__ is not recorder.__dict__
            for function in functions
        ):
            raise RuntimeError("recorder_descriptor_not_source_owned")
        descriptors.append((name, value))

    while pending_functions or pending_classes:
        if pending_classes:
            cls = pending_classes.pop()
            if id(cls) in seen_classes:
                continue
            seen_classes.add(id(cls))
            namespace = type.__getattribute__(cls, "__dict__")
            bases = type.__getattribute__(cls, "__bases__")
            fields = tuple(namespace.items())
            class_holds.append((cls, bases, fields))
            for _, value in fields:
                pending_functions.extend(descriptor_functions(value))
            continue
        function = pending_functions.pop()
        if type(function) is not FunctionType or id(function) in seen_functions:
            continue
        seen_functions.add(id(function))
        kwdefaults = function.__kwdefaults__
        if kwdefaults is not None and (
            type(kwdefaults) is not dict or any(type(key) is not str for key in kwdefaults)
        ):
            raise RuntimeError("recorder_function_defaults_unsupported")
        kwitems = () if kwdefaults is None else tuple(kwdefaults.items())
        closure = function.__closure__
        cells: list[tuple[object, bool, object]] = []
        for cell in closure or ():
            try:
                cells.append((cell, True, cell.cell_contents))
            except ValueError:
                cells.append((cell, False, None))
        function_holds.append(
            (
                function,
                function.__code__,
                function.__defaults__,
                kwdefaults,
                kwitems,
                closure,
                tuple(cells),
            )
        )
        if function.__globals__ is recorder.__dict__:
            names = _code_names(function.__code__)
            referenced_names.update(names)
            for name in names:
                value = recorder.__dict__.get(name)
                if type(value) is FunctionType and value.__globals__ is recorder.__dict__:
                    pending_functions.append(value)
                elif (
                    type(value) is type
                    and type.__getattribute__(value, "__module__") == recorder.__name__
                ):
                    pending_classes.append(value)
    globals_ = tuple(
        (name, recorder.__dict__[name])
        for name in sorted(referenced_names)
        if name in recorder.__dict__
    )
    return recorder_type, tuple(descriptors), globals_, tuple(function_holds), tuple(class_holds)


def _code_names(root: CodeType) -> set[str]:
    """Return the names referenced by a function's nested compiler code tree."""

    names: set[str] = set()
    pending = [root]
    while pending:
        code = pending.pop()
        names.update(code.co_names)
        pending.extend(item for item in code.co_consts if type(item) is CodeType)
    return names


def _same_named_references(expected: object, observed: object) -> bool:
    if type(expected) is not tuple or type(observed) is not tuple or len(expected) != len(observed):
        return False
    return all(
        type(left) is tuple
        and type(right) is tuple
        and len(left) == len(right) == 2
        and type(left[0]) is str
        and type(right[0]) is str
        and left[0] == right[0]
        and left[1] is right[1]
        for left, right in zip(expected, observed, strict=True)
    )


def _same_recorder_surface(expected: object, observed: object) -> bool:
    """Compare the retained recorder surface without calling its functions."""

    if (
        type(expected) is not tuple
        or type(observed) is not tuple
        or len(expected) != 5
        or len(observed) != 5
    ):
        return False
    if (
        expected[0] is not observed[0]
        or not _same_named_references(expected[1], observed[1])
        or not _same_named_references(expected[2], observed[2])
        or any(
            type(rows) is not tuple for rows in (expected[3], observed[3], expected[4], observed[4])
        )
    ):
        return False
    functions = {id(row[0]): row for row in observed[3] if type(row) is tuple and len(row) == 7}
    classes = {id(row[0]): row for row in observed[4] if type(row) is tuple and len(row) == 3}
    if len(functions) != len(expected[3]) or len(classes) != len(expected[4]):
        return False
    for held in expected[3]:
        if type(held) is not tuple or len(held) != 7:
            return False
        current = functions.get(id(held[0]))
        if (
            current is None
            or any(held[index] is not current[index] for index in (0, 1, 2, 3, 5))
            or not _same_named_references(held[4], current[4])
            or type(held[6]) is not tuple
            or type(current[6]) is not tuple
            or len(held[6]) != len(current[6])
            or any(
                type(left) is not tuple
                or type(right) is not tuple
                or len(left) != 3
                or len(right) != 3
                or any(a is not b for a, b in zip(left, right, strict=True))
                for left, right in zip(held[6], current[6], strict=True)
            )
        ):
            return False
    for held in expected[4]:
        if type(held) is not tuple or len(held) != 3:
            return False
        current_class = classes.get(id(held[0]))
        if (
            current_class is None
            or held[0] is not current_class[0]
            or type(held[1]) is not tuple
            or type(current_class[1]) is not tuple
            or len(held[1]) != len(current_class[1])
            or any(a is not b for a, b in zip(held[1], current_class[1], strict=True))
            or not _same_named_references(held[2], current_class[2])
        ):
            return False
    return True


def _recorder_surface_unchanged(session: dict[str, object]) -> bool:
    """Reconcile retained recorder callables before the host invokes any."""

    recorder = session.get("recorder")
    recorder_code = session.get("recorder_code")
    expected = session.get("recorder_surface")
    capture = session.get("capture")
    if (
        type(recorder) is not ModuleType
        or type(recorder_code) is not CodeType
        or type(expected) is not tuple
        or len(expected) != 5
        or type(expected[0]) is not type
        or type(capture) is not expected[0]
    ):
        return False
    try:
        class_namespace = type.__getattribute__(expected[0], "__dict__")
        if type(class_namespace.get("__dict__")) is not GetSetDescriptorType:
            return False
        namespace = object.__getattribute__(capture, "__dict__")
        if type(namespace) is not dict or type(expected[1]) is not tuple:
            return False
        if any(
            type(row) is not tuple or len(row) != 2 or type(row[0]) is not str
            for row in expected[1]
        ):
            return False
        descriptor_names = {row[0] for row in expected[1]}
        if any(type(key) is str and key in descriptor_names for key in namespace):
            return False
        observed = _retained_recorder_surface(recorder, recorder_code)
        return _same_recorder_surface(expected, observed)
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
        return False


def _child_main(channel: socket.socket, request: dict[str, object]) -> int:
    global _HOST_SESSION
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):
        raise RuntimeError("child_startup_flags_invalid")
    if os.getppid() != request["parent_pid"] or Path(str(request["root"])).resolve() != _PRODUCT:
        raise RuntimeError("child_host_binding_invalid")
    if _HOST_SLOT in sys.__dict__ or _HOST_SESSION is not None:
        raise RuntimeError("child_host_already_installed")
    recorder_bytes = base64.b64decode(str(request["recorder_source"]), validate=True)
    if _sha(recorder_bytes) != request["recorder_sha256"]:
        raise RuntimeError("child_recorder_source_mismatch")
    recorder = ModuleType(_CAPTURE_MODULE)
    recorder.__file__ = str(request["recorder_path"])
    sys.modules[_CAPTURE_MODULE] = recorder
    # The child executes exactly the parent-selected recorder bytes; this is
    # evidence collection, not an authority grant or an arbitrary code sandbox.
    recorder_code = compile(recorder_bytes, recorder.__file__, "exec", dont_inherit=True)
    exec(recorder_code, recorder.__dict__)  # noqa: S102
    sources = {
        name: recorder.ExpectedSource(relative, digest)
        for name, (relative, digest) in cast(
            "dict[str, tuple[str, str]]", request["sources"]
        ).items()
    }
    capture = None
    capture_failure = None
    try:
        exports = {
            name: set(bindings)
            for name, bindings in cast("dict[str, list[str]]", request["exports"]).items()
        }
        # The owner handoff is a private bootstrap protocol, not a domain-symbol
        # exception. It is retained before the owner module completes.
        exports.setdefault("polisyos.runtime.quality.confidence_ledger", set()).update(
            {"_observe_unsealed_host_capture", "_seal_loaded_execution_capture"}
        )
        capture = recorder.SourceExecutionCapture(_PRODUCT, sources, exports=exports)
        capture.install()
    except (recorder.CaptureError, OSError, ValueError) as exc:
        capture_failure = type(exc).__name__
        # Constructor failure is an attempted generation too. Do not let a
        # later recorder module adopt imports from this failed startup.
        if recorder._PROCESS_OWNER_SLOT not in sys.__dict__:
            sys.__dict__[recorder._PROCESS_OWNER_SLOT] = object()
    host_code = globals().get("_HOST_EXECUTION_CODE")
    if type(host_code) is not CodeType:
        raise RuntimeError("host_execution_code_unavailable")
    recorder_surface = _retained_recorder_surface(recorder, recorder_code)
    (
        recorder_type,
        recorder_descriptors,
        recorder_globals,
        recorder_functions,
        recorder_classes,
    ) = recorder_surface
    # Strong live references stay in this child; a serialized request or parent
    # process cannot provide an installed capture to a different process.
    profile = _measure_profile()
    profile["parent_startup_isolated"] = request["parent_startup_isolated"]
    profile["parent_startup_classification"] = "host_reported_not_independent_appointment"
    session = {
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "channel": channel,
        "recorder": recorder,
        "host_code": host_code,
        "recorder_code": recorder_code,
        "recorder_type": recorder_type,
        "recorder_descriptors": recorder_descriptors,
        "recorder_globals": recorder_globals,
        "recorder_functions": recorder_functions,
        "recorder_classes": recorder_classes,
        "recorder_surface": recorder_surface,
        "capture": capture,
        "profile": profile,
        "source_frame": request["source_frame"],
        "host_sha256": request["host_sha256"],
        "recorder_sha256": request["recorder_sha256"],
        "unparsed_sources": tuple(cast("list[str]", request["unparsed_sources"])),
        "phase": "collecting" if capture_failure is None else "failed",
        "last_owner_diagnostic": None
        if capture_failure is None
        else {"status": "not_established", "failure": capture_failure},
        "handoff": handoff_if_ready,
    }
    _HOST_SESSION = session
    sys.__dict__[_HOST_SLOT] = session
    site = Path(sys.prefix) / "lib/python3.14/site-packages"
    sys.path[:0] = [str(_PRODUCT / "src"), str(_PRODUCT), str(site)]
    channel.sendall(b"installed\n" if capture_failure is None else b"candidate\n")
    mode = str(request["mode"])
    arguments = list(cast("list[str]", request["argv"]))
    return _invoke_entry(mode, arguments)


def _attach_tools_handoff() -> None:
    """Install the held host callback only into the actually captured runner."""

    session = _HOST_SESSION
    if type(session) is not dict or session["phase"] != "collecting":
        return
    if not _recorder_surface_unchanged(session):
        session["phase"] = "failed"
        session["last_owner_diagnostic"] = {
            "status": "not_established",
            "failure": "host_recorder_surface_changed",
        }
        return
    capture = session["capture"]
    try:
        runner = capture.completed("tools.lib.runner").module
        for name in ("_HOST_HANDOFF", "_HOST_HANDOFF_ANCHOR", "_HOST_HANDOFF_GLOBALS"):
            found, value = session["recorder"]._passive_lookup(runner.__dict__, name)
            if not found or value is not None:
                return
        runner.__dict__["_HOST_HANDOFF"] = handoff_if_ready
        runner.__dict__["_HOST_HANDOFF_ANCHOR"] = handoff_if_ready
        runner.__dict__["_HOST_HANDOFF_GLOBALS"] = handoff_if_ready.__globals__
    except (AttributeError, ImportError, TypeError):
        return


def _invoke_entry(mode: str, arguments: list[str], *, candidate_reason: str | None = None) -> int:
    # An unavailable source snapshot stays candidate work, including when the
    # parent was started with -I -S and has no checkout or venv site on sys.path.
    site = Path(sys.prefix) / "lib/python3.14/site-packages"
    for path in reversed((_PRODUCT / "src", _PRODUCT, site)):
        rendered = str(path)
        if path.is_dir() and rendered not in sys.path:
            sys.path.insert(0, rendered)
    if mode == "test":
        previous_autoload = os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD")
        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        try:
            pytest = importlib.import_module("pytest")
            # pytest.ini uses these plugins even when no external tests are selected.
            # Explicit loading is not itself plugin authority qualification.
            plugin_args = ["-p", "pytest_benchmark.plugin", "-p", "pytest_asyncio.plugin"]
            return int(pytest.main([*plugin_args, *arguments], plugins=[_CollectionHandoff()]))
        finally:
            if previous_autoload is None:
                os.environ.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
            else:
                os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = previous_autoload
    if mode == "diagnose":
        if arguments:
            raise RuntimeError("host_diagnostic_arguments_unsupported")
        session = _HOST_SESSION
        if candidate_reason is None and type(session) is dict:
            importlib.import_module("polisyos.runtime.quality.confidence_ledger")
            handoff_if_ready()
            report = {"profile": session["profile"], "owner": session["last_owner_diagnostic"]}
        else:
            report = {
                "profile": {"authority": False},
                "owner": {
                    "status": "not_established",
                    "failure": candidate_reason or "source_execution_capture_unavailable",
                },
            }
        print(json.dumps(report, sort_keys=True))
        return 0
    if mode not in _ENTRY_TARGETS:
        raise RuntimeError("host_target_unsupported")
    module_name, callable_name, accepts_argv = _ENTRY_TARGETS[mode]
    target_module = importlib.import_module(module_name)
    if mode == "tools":
        _attach_tools_handoff()
    handoff_if_ready()
    target = getattr(target_module, callable_name)
    if accepts_argv:
        result = target(arguments)
    else:
        previous_argv = sys.argv
        sys.argv = ["polisy" if mode == "polisy" else "polisyos-causal-capabilities", *arguments]
        try:
            result = target()
        finally:
            sys.argv = previous_argv
    return result if type(result) is int else 0


class _CollectionHandoff:
    def pytest_configure(self, config: pytest.Config) -> None:
        workers = config.getoption("numprocesses", default=None)
        transports = config.getoption("tx", default=())
        distribution = config.getoption("dist", default="no")
        if workers not in (None, 0, "0") or (transports and distribution != "no"):
            raise RuntimeError("parallel_test_workers_require_independent_bootstrap")

    def pytest_collection_finish(self, session: object) -> None:
        handoff_if_ready()


def handoff_if_ready() -> None:
    """Offer live capture to the ledger after its initializer has completed."""

    session = _HOST_SESSION
    if type(session) is not dict or sys.__dict__.get(_HOST_SLOT) is not session:
        return
    if session["phase"] != "collecting":
        return
    if session["pid"] != os.getpid() or session["parent_pid"] != os.getppid():
        session["phase"] = "failed"
        return
    if not _recorder_surface_unchanged(session):
        session["phase"] = "failed"
        session["last_owner_diagnostic"] = {
            "status": "not_established",
            "failure": "host_recorder_surface_changed",
        }
        return
    module = sys.modules.get("polisyos.runtime.quality.confidence_ledger")
    if type(module) is not ModuleType:
        return
    try:
        capture = session["capture"]
        callback = capture.completed_binding(module.__name__, "_observe_unsealed_host_capture")
        execution = capture.completed(module.__name__)
        if (
            type(callback) is not FunctionType
            or callback.__globals__ is not module.__dict__
            or not capture._code_belongs_to(execution.code, callback.__code__)
        ):
            raise RuntimeError("owner_diagnostic_binding_unavailable")
        session["last_owner_diagnostic"] = callback(session["recorder"], session["capture"])
    except Exception as exc:
        session["last_owner_diagnostic"] = {
            "status": "not_established",
            "failure": type(exc).__name__,
        }
    # No diagnostic can seal authority: external profile and through-use owners
    # are intentionally not supplied by this producer.


def tools_main(argv: Sequence[str] | None = None) -> int:
    """Launch the existing unified tools entry in a fresh recorder process."""
    return _launch("tools", sys.argv[1:] if argv is None else argv)


def runtime_main(argv: Sequence[str] | None = None) -> int:
    """Launch the existing runtime CLI in a fresh recorder process."""
    return _launch("runtime", sys.argv[1:] if argv is None else argv)


def foundry_main(argv: Sequence[str] | None = None) -> int:
    """Launch the existing Foundry entry in a fresh recorder process."""
    return _launch("foundry", sys.argv[1:] if argv is None else argv)


def polisy_main(argv: Sequence[str] | None = None) -> int:
    """Launch the existing policy plugin CLI in a fresh recorder process."""
    return _launch("polisy", sys.argv[1:] if argv is None else argv)


def causal_capabilities_main(argv: Sequence[str] | None = None) -> int:
    """Launch the existing causal-capabilities CLI in a fresh recorder process."""
    return _launch("causal-capabilities", sys.argv[1:] if argv is None else argv)


def ukraine_data_main(argv: Sequence[str] | None = None) -> int:
    """Launch the existing Ukraine-data CLI in a fresh recorder process."""
    return _launch("ukraine-data", sys.argv[1:] if argv is None else argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Select an existing CLI, HTTP server, or serial pytest entry."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in {*_ENTRY_TARGETS, "test", "diagnose"}:
        raise SystemExit(
            "usage: authority_bootstrap.py "
            "{tools|runtime|foundry|server|polisy|causal-capabilities|"
            "ukraine-data|test|diagnose} [arguments...]"
        )
    return _launch(args[0], args[1:])


if __name__ == "__main__":
    raise SystemExit(main())
