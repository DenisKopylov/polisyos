"""Build extension examples as regular local wheels with a source-bound tool profile.

This profile has a separate bounded purpose from Q2's installed-wave profile.
It reuses Q2's exact portable wheel lock and verifier primitives; it makes no
product, publisher, or source-closure claim.
"""

from __future__ import annotations

import base64
import contextlib
import csv
import hashlib
import importlib.metadata as importlib_metadata
import io
import json
import os
import platform
import re
import secrets
import shutil
import stat
import subprocess
import sys
import sysconfig
import tomllib
import zipfile
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

from tools.quality.validation import q2_build_tool_wheel_lock as q2

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

PROFILE_PATH = "architecture/packaging/extension_example_build_tools.toml"
PROFILE_SCHEMA = "policyos.native-extension-example-build-tools.v1"
PROFILE_PURPOSE = "native-extension-example-wheel-build-only"
CACHE_MANIFEST = ".policyos-native-example-build-tools.json"
VENV_BOOTSTRAP_RECIPE = "stdlib-venv-without-pip-v1"
_INSTALLER_OWNED_DIST_INFO_FILES: dict[str, frozenset[str]] = {
    "uv": frozenset({"uv_cache.json"}),
}
EXPECTED_PROFILE: dict[str, object] = {
    "schema": PROFILE_SCHEMA,
    "purpose": PROFILE_PURPOSE,
    "helper_path": "tools/quality/validation/extension_example_build_tools.py",
    "q2_helper_path": "tools/quality/validation/q2_build_tool_wheel_lock.py",
    "q2_helper_sha256": "86f31671b26c84baa9a7a1647553d8e42d5d8cab154097c285393742738ec8bd",
    "lock_path": (
        "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
        "q2-packaging/builder-inputs/hatchling-1.27.0-wheel-lock-r1.json"
    ),
    "lock_sha256": "51eeac7775d87981a1da901ac23c1e86a666cb149234265b4a3c8b24ff4c93ad",
    "build_backend": "hatchling.build",
    "build_system_requirement": "hatchling>=1.27.0",
    "root_requirement": "hatchling==1.27.0",
    "python_implementation": "CPython",
    "python_version": "3.14",
    "selected_extras": [],
    "wheel_tag": "py3-none-any",
    "index_policy": "offline-only",
    "install_policy": "verified-wheelhouse-no-deps-no-builds",
    "cache_path": ".cache/native-extension-example-build-tools",
}


class ExampleBuildToolsError(RuntimeError):
    """A source profile, locked tool environment, or local wheel is invalid."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ExampleBuildToolsError(f"{label} contains a duplicate key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExampleBuildToolsError(f"{label} is not strict UTF-8 JSON") from error
    if type(value) is not dict:
        raise ExampleBuildToolsError(f"{label} must be a JSON object")
    return value


def _parse_profile(raw: bytes) -> dict[str, object]:
    try:
        profile = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ExampleBuildToolsError(
            "native example build-tools profile is invalid TOML"
        ) from error
    if type(profile) is not dict or profile != EXPECTED_PROFILE:
        raise ExampleBuildToolsError(
            "native example build-tools profile differs from its bounded source contract"
        )
    return profile


def _source_inputs(
    repo_root: Path,
) -> tuple[dict[str, object], bytes, dict[str, Any], bytes, bytes]:
    profile_path = repo_root / PROFILE_PATH
    profile_raw = profile_path.read_bytes()
    profile = _parse_profile(profile_raw)
    native_helper_path = repo_root / str(profile["helper_path"])
    if Path(__file__).resolve() != native_helper_path.resolve():
        raise ExampleBuildToolsError("loaded native helper differs from its profile path")
    helper_path = repo_root / str(profile["q2_helper_path"])
    helper_raw = helper_path.read_bytes()
    if _sha256(helper_raw) != profile["q2_helper_sha256"]:
        raise ExampleBuildToolsError("Q2 verifier helper bytes differ from the native profile")
    if Path(q2.__file__).resolve() != helper_path.resolve():
        raise ExampleBuildToolsError("loaded Q2 helper is not the source-bound repository helper")
    lock_path = repo_root / str(profile["lock_path"])
    lock_raw = lock_path.read_bytes()
    lock = q2.load_lock(lock_raw, expected_sha256=str(profile["lock_sha256"]))
    q2_profile = {
        "build_system_requirement": profile["build_system_requirement"],
        "build_backend": profile["build_backend"],
        "root_requirement": profile["root_requirement"],
        "selected_extras": profile["selected_extras"],
        "wheel_tag": profile["wheel_tag"],
        "python_implementation": profile["python_implementation"],
        "python_version": profile["python_version"],
        "index_policy": profile["index_policy"],
        "install_policy": profile["install_policy"],
    }
    q2.verify_profile_lock(q2_profile, lock)
    return profile, profile_raw, lock, lock_raw, helper_raw


def _sha256_file(path: Path) -> str:
    try:
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as error:
        raise ExampleBuildToolsError(f"interpreter bytes cannot be read: {path}") from error


def _current_interpreter_identity() -> dict[str, object]:
    executable = Path(sys.executable).resolve(strict=True)
    stdlib = Path(sysconfig.get_path("stdlib")).resolve(strict=True)
    if not executable.is_file() or not stdlib.is_dir():
        raise ExampleBuildToolsError("selected Python executable or standard library is missing")
    return {
        "implementation": platform.python_implementation(),
        "version": list(sys.version_info[:3]),
        "cache_tag": sys.implementation.cache_tag,
        "soabi": sysconfig.get_config_var("SOABI"),
        "platform": sysconfig.get_platform(),
        "executable": str(executable),
        "executable_sha256": _sha256_file(executable),
        "stdlib": str(stdlib),
    }


def _interpreter_identity(profile: Mapping[str, object]) -> dict[str, object]:
    identity = _current_interpreter_identity()
    if identity["implementation"] != profile["python_implementation"]:
        raise ExampleBuildToolsError(
            "extension build tools require the profiled Python implementation"
        )
    version = identity["version"]
    if (
        not isinstance(version, list)
        or ".".join(map(str, version[:2])) != profile["python_version"]
    ):
        raise ExampleBuildToolsError("extension build tools require the profiled Python version")
    return identity


def _cache_key(
    profile_raw: bytes,
    lock_raw: bytes,
    q2_helper_raw: bytes,
    own_helper_raw: bytes,
    interpreter: Mapping[str, object],
    uv_identity: Mapping[str, str],
) -> str:
    identity = {
        "purpose": PROFILE_PURPOSE,
        "profile_sha256": _sha256(profile_raw),
        "lock_sha256": _sha256(lock_raw),
        "q2_helper_sha256": _sha256(q2_helper_raw),
        "native_helper_sha256": _sha256(own_helper_raw),
        "venv_bootstrap_recipe": VENV_BOOTSTRAP_RECIPE,
        "interpreter": dict(interpreter),
        "uv": dict(uv_identity),
    }
    return _sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())


def _assert_regular_path(path: Path, *, within: Path) -> None:
    if ".." in path.parts or ".." in within.parts:
        raise ExampleBuildToolsError("cache path contains a parent traversal")
    root = Path(os.path.abspath(within))
    target = Path(os.path.abspath(path))
    try:
        relative = target.relative_to(root)
        root_stat = root.lstat().st_mode
        if (
            stat.S_ISLNK(root_stat)
            or not stat.S_ISDIR(root_stat)
            or root.resolve(strict=True) != root
        ):
            raise ExampleBuildToolsError(f"cache owner is not a physical directory: {root}")
    except ExampleBuildToolsError:
        raise
    except (OSError, ValueError) as error:
        raise ExampleBuildToolsError(f"cache path is outside its physical owner: {path}") from error
    cursor = root
    for index, part in enumerate(relative.parts):
        cursor = cursor / part
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            return
        except OSError as error:
            raise ExampleBuildToolsError(f"cache path cannot be inspected: {cursor}") from error
        if stat.S_ISLNK(info.st_mode):
            raise ExampleBuildToolsError(f"cache path contains a symlink: {cursor}")
        try:
            if cursor.resolve(strict=True) != cursor:
                raise ExampleBuildToolsError(f"cache path resolves through an alias: {cursor}")
        except OSError as error:
            raise ExampleBuildToolsError(f"cache path cannot be resolved: {cursor}") from error
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ExampleBuildToolsError(f"cache path parent is not a directory: {cursor}")


def _safe_mkdir(path: Path, *, within: Path, must_be_new: bool = False) -> Path:
    _assert_regular_path(path, within=within)
    root = Path(os.path.abspath(within))
    target = Path(os.path.abspath(path))
    relative = target.relative_to(root)
    if must_be_new:
        if target.exists() or target.is_symlink():
            raise ExampleBuildToolsError(f"refusing to reuse existing cache directory: {target}")
        _safe_mkdir(target.parent, within=root)
        try:
            target.mkdir(mode=0o700, exist_ok=False)
        except OSError as error:
            raise ExampleBuildToolsError(
                f"cache directory could not be created exclusively: {target}"
            ) from error
        _assert_regular_path(target, within=root)
        return target
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        try:
            cursor.mkdir(mode=0o700, exist_ok=False)
        except FileExistsError:
            pass
        except OSError as error:
            raise ExampleBuildToolsError(
                f"cache directory could not be created safely: {cursor}"
            ) from error
        _assert_regular_path(cursor, within=root)
        if not cursor.is_dir():
            raise ExampleBuildToolsError(f"cache path is not a directory: {cursor}")
    return target


def _ensure_cache_root(cache_root: Path, owner_root: Path) -> Path:
    return _safe_mkdir(cache_root, within=owner_root)


def _safe_component(name: str) -> None:
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise ExampleBuildToolsError("cache path component is invalid")


def _new_cache_path(parent: Path, prefix: str, *, within: Path) -> Path:
    _safe_component(prefix)
    _safe_mkdir(parent, within=within)
    for _ in range(16):
        candidate = parent / f"{prefix}-{secrets.token_hex(12)}"
        _assert_regular_path(candidate, within=within)
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
    raise ExampleBuildToolsError("could not allocate a fresh cache path")


def _new_cache_directory(parent: Path, prefix: str, *, within: Path) -> Path:
    candidate = _new_cache_path(parent, prefix, within=within)
    return _safe_mkdir(candidate, within=within, must_be_new=True)


def _write_new_cache_file(
    directory: Path,
    name: str,
    contents: bytes,
    *,
    within: Path,
) -> Path:
    _safe_component(name)
    _safe_mkdir(directory, within=within)
    target = directory / name
    _assert_regular_path(target, within=within)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        fd = os.open(str(target), flags, 0o600)
    except FileExistsError as error:
        raise ExampleBuildToolsError(
            f"refusing to overwrite an existing cache object: {target}"
        ) from error
    except OSError as error:
        raise ExampleBuildToolsError(
            f"cache file could not be created exclusively: {target}"
        ) from error
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ExampleBuildToolsError(f"new cache file is not regular: {target}")
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if fd >= 0:
            os.close(fd)
    _assert_regular_path(target, within=within)
    return target


def _initialize_cache_lock(handle, lock_path: Path) -> None:
    handle.seek(0)
    contents = handle.read(2)
    if contents not in {b"", b"\0"}:
        raise ExampleBuildToolsError(f"cache lock contains unexpected bytes: {lock_path}")
    if not contents:
        handle.seek(0)
        handle.write(b"\0")
        handle.flush()
        os.fsync(handle.fileno())


@contextlib.contextmanager
def _cache_lock(cache_root: Path) -> Iterator[None]:
    _safe_mkdir(cache_root, within=cache_root.parent)
    lock_path = cache_root / ".extension-example-build-tools.lock"
    _assert_regular_path(lock_path, within=cache_root)
    try:
        existing = lock_path.lstat()
    except FileNotFoundError:
        existing = None
    except OSError as error:
        raise ExampleBuildToolsError(f"cache lock cannot be inspected: {lock_path}") from error
    if existing is not None and (not stat.S_ISREG(existing.st_mode) or existing.st_nlink != 1):
        raise ExampleBuildToolsError(f"cache lock is not a private regular file: {lock_path}")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        fd = os.open(str(lock_path), flags, 0o600)
    except OSError as error:
        raise ExampleBuildToolsError(
            f"cache lock could not be opened without following aliases: {lock_path}"
        ) from error
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        raise ExampleBuildToolsError(f"cache lock is not a private regular file: {lock_path}")
    handle = os.fdopen(fd, "r+b")
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                _initialize_cache_lock(handle, lock_path)
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                _initialize_cache_lock(handle, lock_path)
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


_COMMAND_TIMEOUT_SECONDS = 300
_PROBE_TIMEOUT_SECONDS = 60


def _cache_directory(cache_root: Path, name: str) -> Path:
    _safe_component(name)
    _safe_mkdir(cache_root, within=cache_root.parent)
    return _safe_mkdir(cache_root / name, within=cache_root)


def _child_environment(cache_root: Path) -> dict[str, str]:
    """Return the small, credential-free environment for locked build commands."""
    _safe_mkdir(cache_root, within=cache_root.parent)
    process_root = _new_cache_directory(cache_root, "process", within=cache_root)
    uv_cache = _new_cache_directory(process_root, "uv-cache", within=cache_root)
    xdg_cache = _new_cache_directory(process_root, "xdg-cache", within=cache_root)
    hatch_cache = _new_cache_directory(process_root, "hatch-cache", within=cache_root)
    temp = _new_cache_directory(process_root, "tmp", within=cache_root)
    allowed = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")
    environment = {name: os.environ[name] for name in allowed if name in os.environ}
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUTF8": "1",
            "UV_CACHE_DIR": str(uv_cache),
            "XDG_CACHE_HOME": str(xdg_cache),
            "HATCH_CACHE_DIR": str(hatch_cache),
            "TMPDIR": str(temp),
            "TEMP": str(temp),
            "TMP": str(temp),
        }
    )
    return environment


def _uv_command(uv: str, cache_root: Path, *arguments: str) -> list[str]:
    _safe_mkdir(cache_root, within=cache_root.parent)
    uv_cache = _new_cache_directory(cache_root, "uv-cache", within=cache_root)
    return [uv, "--no-config", "--cache-dir", str(uv_cache), *arguments]


def _run(
    argv: Sequence[str],
    *,
    cache_root: Path,
    cwd: Path | None = None,
    timeout: float = _COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    environment = _child_environment(cache_root)
    try:
        result = subprocess.run(
            list(argv),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise ExampleBuildToolsError(
            f"locked build-tools command timed out after {timeout:g}s: {argv[0]}"
        ) from error
    if result.returncode:
        detail = (result.stderr or result.stdout)[-4000:]
        raise ExampleBuildToolsError(
            f"locked build-tools command failed ({result.returncode}): {argv[0]}\n{detail}"
        )
    return result


def _uv_identity(cache_root: Path) -> tuple[str, dict[str, str]]:
    executable = shutil.which("uv")
    if executable is None:
        raise ExampleBuildToolsError("the uv executable is required for the locked offline recipe")
    resolved = str(Path(executable).resolve())
    version = _run(
        _uv_command(resolved, cache_root, "--version"),
        cache_root=cache_root,
        timeout=_PROBE_TIMEOUT_SECONDS,
    ).stdout.strip()
    if not version:
        raise ExampleBuildToolsError("uv returned no version identity")
    return resolved, {"path": resolved, "version": version}


def _ensure_wheelhouse(
    cache_root: Path,
    lock: dict[str, Any],
    lock_raw: bytes,
) -> Path:
    wheelhouses = _cache_directory(cache_root, "wheelhouses")
    lock_key = _sha256(lock_raw)
    candidates = sorted(
        path
        for path in wheelhouses.iterdir()
        if path.name == lock_key or path.name.startswith(lock_key + "-")
    )
    for destination in candidates:
        try:
            _assert_regular_path(destination, within=cache_root)
            if destination.is_symlink() or not destination.is_dir():
                continue
            q2.validate_quarantine(lock, destination)
        except (ExampleBuildToolsError, q2.BuildToolsInputError, OSError):
            # Preserve failed attempts; only verifier-clean caches are reused.
            continue
        return destination

    destination = _new_cache_path(wheelhouses, lock_key, within=cache_root)
    q2.fetch_locked_inputs(lock, destination)
    _assert_regular_path(destination, within=cache_root)
    q2.validate_quarantine(lock, destination)
    return destination


def _build_python(env_path: Path) -> Path:
    if os.name == "nt":
        return env_path / "Scripts" / "python.exe"
    return env_path / "bin" / "python"


def _verify_host_interpreter(
    interpreter: Mapping[str, object],
) -> tuple[Path, Path]:
    """Recheck the selected host executable and standard library before execution."""
    expected_executable = Path(str(interpreter["executable"]))
    expected_digest = str(interpreter["executable_sha256"])
    expected_stdlib = Path(str(interpreter["stdlib"]))
    try:
        if (
            expected_executable.resolve(strict=True) != expected_executable
            or not expected_executable.is_file()
            or _sha256_file(expected_executable) != expected_digest
        ):
            raise ExampleBuildToolsError("selected host Python identity changed")
        stdlib_path = expected_stdlib.resolve(strict=True)
        if stdlib_path != expected_stdlib or not stdlib_path.is_dir():
            raise ExampleBuildToolsError("selected host standard library identity changed")
    except ExampleBuildToolsError:
        raise
    except OSError as error:
        raise ExampleBuildToolsError("selected host Python identity cannot be read") from error
    return expected_executable, expected_stdlib


def _verify_build_python(
    python: Path,
    env_path: Path,
    cache_root: Path,
    interpreter: Mapping[str, object],
) -> None:
    """Bind a cached interpreter and its standard-library selection before execution."""
    _assert_regular_path(env_path, within=cache_root)
    _assert_regular_path(python.parent, within=cache_root)
    expected_executable, _ = _verify_host_interpreter(interpreter)
    try:
        python_info = python.lstat()
    except OSError as error:
        raise ExampleBuildToolsError(f"cached Python identity cannot be read: {python}") from error

    if stat.S_ISLNK(python_info.st_mode):
        try:
            resolved_python = python.resolve(strict=True)
        except OSError as error:
            raise ExampleBuildToolsError(f"cached Python symlink is broken: {python}") from error
        if resolved_python != expected_executable:
            raise ExampleBuildToolsError(
                "cached Python symlink does not resolve to the selected host interpreter"
            )
    elif stat.S_ISREG(python_info.st_mode):
        if _sha256_file(python) != str(interpreter["executable_sha256"]):
            raise ExampleBuildToolsError(
                "cached Python bytes differ from the selected host interpreter"
            )
    else:
        raise ExampleBuildToolsError(f"cached Python is not a regular executable: {python}")
    if os.name != "nt" and not os.access(python, os.X_OK):
        raise ExampleBuildToolsError(f"cached Python is not executable: {python}")

    config_path = env_path / "pyvenv.cfg"
    _assert_regular_path(config_path, within=cache_root)
    if config_path.is_symlink() or not config_path.is_file():
        raise ExampleBuildToolsError("cached virtual environment lacks a regular pyvenv.cfg")
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ExampleBuildToolsError("cached pyvenv.cfg is unreadable") from error
    config: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not key or key in config:
            raise ExampleBuildToolsError("cached pyvenv.cfg contains malformed or duplicate fields")
        config[key] = value
    required = {
        "home",
        "include-system-site-packages",
        "version",
        "executable",
        "command",
    }
    if set(config) != required:
        raise ExampleBuildToolsError(
            "cached pyvenv.cfg has an incomplete or unknown stdlib field set"
        )
    configured_home = Path(config["home"])
    configured_executable = Path(config["executable"])
    expected_home = expected_executable.parent
    expected_version = ".".join(str(value) for value in interpreter["version"])
    expected_command = f"{expected_executable} -m venv --without-pip {env_path}"
    try:
        resolved_home = configured_home.resolve(strict=True)
        resolved_cfg_executable = configured_executable.resolve(strict=True)
    except OSError as error:
        raise ExampleBuildToolsError("cached pyvenv.cfg names a missing host path") from error
    if (
        not configured_home.is_absolute()
        or ".." in configured_home.parts
        or resolved_home != expected_home
        or not configured_executable.is_absolute()
        or ".." in configured_executable.parts
        or resolved_cfg_executable != expected_executable
        or config["version"] != expected_version
        or config["include-system-site-packages"] != "false"
        or config["command"] != expected_command
    ):
        raise ExampleBuildToolsError(
            "cached pyvenv.cfg differs from the selected stdlib virtual environment profile"
        )


def _create_build_tools_venv(
    env_path: Path,
    cache_root: Path,
    interpreter: Mapping[str, object],
) -> Path:
    """Create and verify a stdlib-only venv for the locked wheel installer."""
    if not env_path.is_absolute():
        raise ExampleBuildToolsError("build-tools environment path must be absolute")
    _assert_regular_path(env_path, within=cache_root)
    if env_path.exists() or env_path.is_symlink():
        raise ExampleBuildToolsError(f"refusing to reuse build-tools environment: {env_path}")
    host_python, _ = _verify_host_interpreter(interpreter)
    _run(
        [
            str(host_python),
            "-I",
            "-S",
            "-m",
            "venv",
            "--without-pip",
            str(env_path),
        ],
        cache_root=cache_root,
    )
    python = _build_python(env_path)
    if not python.is_file():
        raise ExampleBuildToolsError("stdlib did not create the isolated build-tools interpreter")
    _verify_build_python(python, env_path, cache_root, interpreter)
    return python


def _probe_source(lock: dict[str, Any], env_path: Path) -> str:
    """Bind the locked probe to this venv and allow safe execution under -I -S."""
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    purelib = (
        env_path / "Lib" / "site-packages"
        if os.name == "nt"
        else env_path / "lib" / version / "site-packages"
    )
    source = q2.installed_probe_code(lock)
    replacements = (
        (
            'purelib = Path(sysconfig.get_paths()["purelib"]).resolve()',
            f"purelib = Path({str(purelib)!r}).resolve()",
        ),
        ("prefix = Path(sys.prefix).resolve()", f"prefix = Path({str(env_path)!r}).resolve()"),
    )
    for old, new in replacements:
        if source.count(old) != 1:
            raise ExampleBuildToolsError("locked probe source lacks its unique path binding")
        source = source.replace(old, new)
    return source


def _probe_command(python: Path, lock: dict[str, Any], env_path: Path) -> list[str]:
    return [str(python), "-I", "-S", "-c", _probe_source(lock, env_path)]


def _probe_build_tools(
    python: Path,
    env_path: Path,
    lock: dict[str, Any],
    wheelhouse: Path,
    cache_root: Path,
    interpreter: Mapping[str, object],
) -> dict[str, Any]:
    _verify_build_python(python, env_path, cache_root, interpreter)
    result = _run(
        _probe_command(python, lock, env_path),
        cache_root=cache_root,
        timeout=_PROBE_TIMEOUT_SECONDS,
    )
    try:
        payload = _strict_json(result.stdout.strip().splitlines()[-1].encode(), "installed probe")
    except (IndexError, UnicodeEncodeError) as error:
        raise ExampleBuildToolsError(
            "installed build-tools probe returned no JSON result"
        ) from error
    if payload.get("verified") is not True:
        raise ExampleBuildToolsError("installed build-tools probe did not establish its closure")
    if (
        payload.get("version") != sys.version
        or payload.get("implementation") != sys.implementation.name
    ):
        raise ExampleBuildToolsError("installed probe interpreter differs from the selected host")
    prefix = Path(str(payload.get("prefix", "")))
    if prefix.resolve() != env_path.resolve():
        raise ExampleBuildToolsError(
            "installed build-tools prefix differs from the isolated environment"
        )
    purelib = Path(str(payload.get("purelib", "")))
    if (
        not purelib.is_dir()
        or purelib.is_symlink()
        or not purelib.resolve().is_relative_to(env_path.resolve())
    ):
        raise ExampleBuildToolsError(
            "installed build-tools purelib is outside its isolated environment"
        )
    expected: dict[str, str] = {}
    for row in lock["artifacts"]:
        with zipfile.ZipFile(wheelhouse / row["filename"]) as wheel:
            for info in wheel.infolist():
                if info.is_dir():
                    continue
                if any(part.endswith(".dist-info") for part in PurePosixPath(info.filename).parts):
                    continue
                relative = PurePosixPath(info.filename).as_posix()
                if relative in expected:
                    raise ExampleBuildToolsError(f"locked build-tool wheels overlap at {relative}")
                expected[relative] = _sha256(wheel.read(info.filename))
    actual: dict[str, str] = {}
    for path in purelib.rglob("*"):
        if path.is_symlink():
            raise ExampleBuildToolsError(f"installed build-tools site contains a symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(purelib).as_posix()
        parts = PurePosixPath(relative).parts
        if (
            any(part.endswith(".dist-info") or part == "__pycache__" for part in parts)
            or path.suffix == ".pyc"
        ):
            continue
        actual[relative] = _sha256(path.read_bytes())
    if actual != expected:
        missing, extra = sorted(set(expected) - set(actual)), sorted(set(actual) - set(expected))
        changed = sorted(p for p in expected.keys() & actual.keys() if expected[p] != actual[p])
        raise ExampleBuildToolsError(
            f"installed build-tool bytes differ from locked wheels: missing={missing[:8]} extra={extra[:8]} changed={changed[:8]}"
        )
    payload["installed_module_files_sha256"] = _sha256(
        json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()
    )
    return payload


def _ensure_build_tools_python(
    repo_root: Path,
    profile: Mapping[str, object],
    profile_raw: bytes,
    lock: dict[str, Any],
    lock_raw: bytes,
    q2_helper_raw: bytes,
    wheelhouse: Path,
    interpreter: Mapping[str, object],
    uv: str,
    uv_identity: Mapping[str, str],
) -> tuple[Path, dict[str, Any]]:
    own_helper_raw = Path(__file__).read_bytes()
    cache_root = _ensure_cache_root(repo_root / str(profile["cache_path"]), repo_root)
    key = _cache_key(profile_raw, lock_raw, q2_helper_raw, own_helper_raw, interpreter, uv_identity)
    environments = _cache_directory(cache_root, "environments")
    expected_manifest = {
        "schema": "policyos.native-extension-example-build-tools-cache.v2",
        "purpose": PROFILE_PURPOSE,
        "cache_key": key,
        "venv_bootstrap_recipe": VENV_BOOTSTRAP_RECIPE,
        "profile_sha256": _sha256(profile_raw),
        "lock_sha256": _sha256(lock_raw),
        "q2_helper_sha256": _sha256(q2_helper_raw),
        "native_helper_sha256": _sha256(own_helper_raw),
        "interpreter": dict(interpreter),
        "uv": dict(uv_identity),
    }
    candidates = [environments / key, *sorted(environments.glob(key + "-*"))]
    for env_path in candidates:
        if not env_path.exists() and not env_path.is_symlink():
            continue
        _assert_regular_path(env_path, within=cache_root)
        if env_path.is_symlink() or not env_path.is_dir():
            raise ExampleBuildToolsError(
                f"cached build-tools environment is not a physical directory: {env_path}"
            )
        marker = env_path / CACHE_MANIFEST
        if not marker.exists() and not marker.is_symlink():
            continue
        _assert_regular_path(marker, within=cache_root)
        if marker.is_symlink() or not marker.is_file():
            raise ExampleBuildToolsError(
                f"cached build-tools marker is not a regular file: {marker}"
            )
        if _strict_json(marker.read_bytes(), "build-tools cache marker") != expected_manifest:
            raise ExampleBuildToolsError(
                "cached build-tools environment identity differs from current inputs"
            )
        python = _build_python(env_path)
        if not python.is_file():
            raise ExampleBuildToolsError("cached build-tools interpreter is missing or nonregular")
        return python, _probe_build_tools(
            python, env_path, lock, wheelhouse, cache_root, interpreter
        )

    env_path = _new_cache_path(environments, key, within=cache_root)
    requirements_directory = _cache_directory(cache_root, "requirements")
    requirements_path = _write_new_cache_file(
        requirements_directory,
        f"{key}-{secrets.token_hex(12)}.txt",
        q2.requirements_text(lock).encode("utf-8"),
        within=cache_root,
    )
    python = _create_build_tools_venv(env_path, cache_root, interpreter)
    _run(
        _uv_command(
            uv,
            cache_root,
            "pip",
            "install",
            "--offline",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "--only-binary",
            ":all:",
            "--no-deps",
            "--require-hashes",
            "--python",
            str(python),
            "-r",
            str(requirements_path),
        ),
        cache_root=cache_root,
    )
    probe = _probe_build_tools(python, env_path, lock, wheelhouse, cache_root, interpreter)
    _write_new_cache_file(
        env_path,
        CACHE_MANIFEST,
        (json.dumps(expected_manifest, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        within=cache_root,
    )
    return python, probe


def _validate_project_build_system(
    project_path: Path,
    profile: Mapping[str, object],
    lock: dict[str, Any],
) -> dict[str, object]:
    pyproject_path = project_path / "pyproject.toml"
    try:
        document = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ExampleBuildToolsError("example pyproject.toml is missing or invalid") from error
    build_system = document.get("build-system")
    requirements = build_system.get("requires") if type(build_system) is dict else None
    if (
        type(build_system) is not dict
        or build_system.get("build-backend") != profile["build_backend"]
        or type(requirements) is not list
        or len(requirements) != 1
        or type(requirements[0]) is not str
    ):
        raise ExampleBuildToolsError("example build-system differs from the locked backend profile")
    try:
        requirement = Requirement(requirements[0])
    except InvalidRequirement as error:
        raise ExampleBuildToolsError("example build requirement is invalid") from error
    if (
        canonicalize_name(requirement.name) != "hatchling"
        or requirement.extras
        or requirement.marker is not None
    ):
        raise ExampleBuildToolsError("example build-system has an unsupported backend dependency")
    locked_version = str(profile["root_requirement"]).split("==", 1)[1]
    if not requirement.specifier.contains(Version(locked_version), prereleases=True):
        raise ExampleBuildToolsError(
            "locked Hatchling version does not satisfy the example pyproject"
        )
    project = document.get("project")
    if (
        type(project) is not dict
        or not isinstance(project.get("name"), str)
        or not project.get("name")
    ):
        raise ExampleBuildToolsError("example pyproject lacks a project name")
    if not isinstance(project.get("version"), str) or not project.get("version"):
        raise ExampleBuildToolsError("example pyproject lacks a static project version")
    entry_points = project.get("entry-points", {})
    if type(entry_points) is not dict:
        raise ExampleBuildToolsError("example entry-point declarations are malformed")
    return {"name": project["name"], "version": project["version"], "entry_points": entry_points}


def _entry_point_bytes_from_project(
    entry_points: Mapping[str, object],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for group, raw_entries in entry_points.items():
        if type(group) is not str or type(raw_entries) is not dict:
            raise ExampleBuildToolsError("example entry-point declarations are malformed")
        values: dict[str, str] = {}
        for name, target in raw_entries.items():
            if type(name) is not str or type(target) is not str:
                raise ExampleBuildToolsError("example entry-point declaration is not string typed")
            values[name] = target
        result[group] = values
    return result


def _record_rows(raw: bytes, label: str) -> dict[str, tuple[str, str]]:
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as error:
        raise ExampleBuildToolsError(f"{label} is not valid UTF-8 CSV") from error
    parsed: dict[str, tuple[str, str]] = {}
    for row in rows:
        if len(row) != 3:
            raise ExampleBuildToolsError(f"{label} contains a malformed RECORD row")
        path, digest, size = row
        member = PurePosixPath(path)
        if (
            not path
            or "\\" in path
            or member.is_absolute()
            or member.as_posix() != path
            or any(p in {"", ".", ".."} for p in member.parts)
            or "\x00" in path
            or path in parsed
        ):
            raise ExampleBuildToolsError(f"{label} contains an unsafe or duplicate RECORD path")
        parsed[path] = (digest, size)
    return parsed


def _record_manifest(
    rows, *, names: set[str], record_path: str, read_member, label: str
) -> dict[str, dict[str, object]]:
    if set(rows) != names:
        raise ExampleBuildToolsError(f"{label} does not cover the complete file set")
    if rows.get(record_path) != ("", ""):
        raise ExampleBuildToolsError(f"{label} must leave only its own RECORD hash empty")
    manifest: dict[str, dict[str, object]] = {}
    for path in sorted(names):
        if path == record_path:
            continue
        digest, size_text = rows[path]
        match = re.fullmatch(r"sha256=([A-Za-z0-9_-]+)", digest)
        if match is None:
            raise ExampleBuildToolsError(f"{label} has an unsupported hash for {path}")
        raw = read_member(path)
        actual = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
        try:
            size = int(size_text)
        except ValueError as error:
            raise ExampleBuildToolsError(f"{label} has an invalid size for {path}") from error
        if size < 0 or size != len(raw) or match.group(1) != actual:
            raise ExampleBuildToolsError(f"{label} hash or size differs for {path}")
        manifest[path] = {"sha256": _sha256(raw), "bytes": len(raw)}
    return manifest


def _validate_wheel_identity(
    wheel_path: Path, project: Mapping[str, object], profile: Mapping[str, object]
) -> dict[str, object]:
    try:
        filename_name, filename_version, build_tag, tags = parse_wheel_filename(wheel_path.name)
        with zipfile.ZipFile(wheel_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ExampleBuildToolsError("built wheel contains duplicate members")
            for name in names:
                parts = name.replace("\\", "/").split("/")
                if (
                    name.startswith(("/", "\\"))
                    or "\\" in name
                    or ".." in parts
                    or "\x00" in name
                    or PurePosixPath(name).as_posix() != name
                ):
                    raise ExampleBuildToolsError("built wheel contains an unsafe path")
            member_names = {n for n in names if not n.endswith("/")}
            dist_infos = sorted({n.split("/", 1)[0] for n in member_names if ".dist-info/" in n})
            if len(dist_infos) != 1:
                raise ExampleBuildToolsError("built wheel must contain one dist-info directory")
            dist_info = dist_infos[0]
            expected_info = f"{canonicalize_name(str(project['name'])).replace('-', '_')}-{str(Version(str(project['version']))).replace('-', '_')}.dist-info"
            if dist_info != expected_info:
                raise ExampleBuildToolsError(
                    "built wheel dist-info identity differs from pyproject"
                )
            metadata = Parser().parsestr(archive.read(f"{dist_info}/METADATA").decode("utf-8"))
            if (
                canonicalize_name(metadata.get("Name", ""))
                != canonicalize_name(str(project["name"]))
                or metadata.get("Version") != project["version"]
                or canonicalize_name(str(filename_name)) != canonicalize_name(str(project["name"]))
                or str(filename_version) != metadata.get("Version")
                or build_tag
            ):
                raise ExampleBuildToolsError("built wheel metadata differs from example pyproject")
            wheel_headers = Parser().parsestr(archive.read(f"{dist_info}/WHEEL").decode("utf-8"))
            try:
                wheel_version = Version(wheel_headers.get("Wheel-Version", ""))
            except Exception as error:
                raise ExampleBuildToolsError("built wheel has invalid WHEEL metadata") from error
            expected_tag = str(profile["wheel_tag"])
            if (
                wheel_version.major != 1
                or wheel_headers.get("Root-Is-Purelib", "").lower() != "true"
                or {str(tag) for tag in tags} != {expected_tag}
                or set(wheel_headers.get_all("Tag", [])) != {expected_tag}
            ):
                raise ExampleBuildToolsError(
                    "built wheel tag or WHEEL metadata differs from profile"
                )
            ep_path = f"{dist_info}/entry_points.txt"
            parser = ConfigParser(interpolation=None, strict=True)
            parser.optionxform = str
            if ep_path in member_names:
                parser.read_string(archive.read(ep_path).decode("utf-8"))
            observed = {
                section: dict(parser.items(section, raw=True)) for section in parser.sections()
            }
            if observed != _entry_point_bytes_from_project(project["entry_points"]):
                raise ExampleBuildToolsError(
                    "built wheel entry points differ from example pyproject"
                )
            record_path = f"{dist_info}/RECORD"
            rows = _record_rows(archive.read(record_path), "built wheel RECORD")
            files = _record_manifest(
                rows,
                names=member_names,
                record_path=record_path,
                read_member=archive.read,
                label="built wheel RECORD",
            )
            return {
                "name": metadata.get("Name", ""),
                "version": metadata.get("Version", ""),
                "filename": wheel_path.name,
                "wheel_sha256": _sha256(wheel_path.read_bytes()),
                "dist_info": dist_info,
                "entry_points": observed,
                "files": files,
            }
    except ExampleBuildToolsError:
        raise
    except ConfigParserError as error:
        raise ExampleBuildToolsError("built wheel entry_points.txt is malformed") from error
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, ValueError) as error:
        raise ExampleBuildToolsError("built wheel is not a valid distribution archive") from error


def _inside_regular_file(path: Path, root: Path, label: str) -> Path:
    if root.is_symlink():
        raise ExampleBuildToolsError(f"{label} root is a symlink")
    resolved_root = root.resolve(strict=True)
    cursor = path
    while cursor != resolved_root and resolved_root in cursor.parents:
        if cursor.is_symlink():
            raise ExampleBuildToolsError(f"{label} contains a symlink: {cursor}")
        cursor = cursor.parent
    if cursor != resolved_root:
        raise ExampleBuildToolsError(f"{label} escapes its distribution root")
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(resolved_root):
        raise ExampleBuildToolsError(f"{label} is not a regular file inside its distribution")
    return resolved


def _verify_installed_wheel_identity(
    wheel_identity: Mapping[str, object],
    provider_binding: Mapping[str, object],
    *,
    group: str,
    entry_point_name: str,
) -> dict[str, object]:
    """Compare fresh discovery to the exact wheel installed by this invocation."""
    name, version = str(wheel_identity["name"]), str(wheel_identity["version"])
    try:
        distribution = importlib_metadata.distribution(name)
    except importlib_metadata.PackageNotFoundError as error:
        raise ExampleBuildToolsError("installed wheel distribution is missing") from error
    if (
        canonicalize_name(distribution.metadata.get("Name", "")) != canonicalize_name(name)
        or distribution.version != version
    ):
        raise ExampleBuildToolsError("installed distribution identity differs from the built wheel")
    direct_raw = distribution.read_text("direct_url.json")
    if direct_raw is None:
        raise ExampleBuildToolsError("installed distribution lacks direct wheel provenance")
    direct = _strict_json(direct_raw.encode("utf-8"), "installed direct_url.json")
    parsed = urlparse(str(direct.get("url", "")))
    archive_info, dir_info = direct.get("archive_info"), direct.get("dir_info", {})
    if (
        parsed.scheme != "file"
        or parsed.netloc not in {"", "localhost"}
        or Path(unquote(parsed.path)).name != wheel_identity["filename"]
        or type(archive_info) is not dict
        or type(dir_info) is not dict
        or dir_info.get("editable") is True
    ):
        raise ExampleBuildToolsError("installed distribution is not the exact regular local wheel")
    hashes = archive_info.get("hashes")
    if type(hashes) is dict and hashes.get("sha256") not in {None, wheel_identity["wheel_sha256"]}:
        raise ExampleBuildToolsError("installed direct-wheel digest differs from built artifact")
    expected_entries = wheel_identity["entry_points"]
    installed_entries: dict[str, dict[str, str]] = {}
    for row in distribution.entry_points:
        installed_entries.setdefault(row.group, {})[row.name] = row.value
    if installed_entries != expected_entries:
        raise ExampleBuildToolsError("installed entry points differ from the built wheel")
    target = expected_entries.get(group, {}).get(entry_point_name)
    if target is None:
        raise ExampleBuildToolsError("built wheel lacks the selected entry point")
    if (
        provider_binding.get("status") != "verified"
        or provider_binding.get("group") != group
        or provider_binding.get("name") != entry_point_name
        or provider_binding.get("value") != target
    ):
        raise ExampleBuildToolsError("fresh discovery did not bind the selected wheel entry point")
    files = wheel_identity["files"]
    if type(files) is not dict:
        raise ExampleBuildToolsError("built wheel file identity is malformed")
    installed_rows = distribution.files
    installed_record = distribution.read_text("RECORD")
    if installed_rows is None or installed_record is None:
        raise ExampleBuildToolsError("installed distribution lacks a complete RECORD inventory")
    rows = _record_rows(installed_record.encode("utf-8"), "installed RECORD")
    if {str(item).replace("\\", "/") for item in installed_rows} != set(rows):
        raise ExampleBuildToolsError("installed distribution RECORD and file inventory disagree")
    dist_info = str(wheel_identity["dist_info"])
    record_path = f"{dist_info}/RECORD"
    installer_path = f"{dist_info}/INSTALLER"
    expected_names = set(files)
    permitted_installer_metadata = {
        installer_path,
        f"{dist_info}/REQUESTED",
        f"{dist_info}/direct_url.json",
    }
    installer_owned_candidates = {
        f"{dist_info}/{member}"
        for members in _INSTALLER_OWNED_DIST_INFO_FILES.values()
        for member in members
    }
    if not expected_names <= set(rows) or not set(rows) <= (
        expected_names | permitted_installer_metadata | installer_owned_candidates | {record_path}
    ):
        raise ExampleBuildToolsError("installed distribution file inventory differs from the wheel")
    root = Path(distribution.locate_file(""))
    if root.is_symlink():
        raise ExampleBuildToolsError("installed distribution root is a symlink")
    root = root.resolve(strict=True)
    installed_manifest = {}
    installer_bytes: bytes | None = None
    for member in sorted(rows):
        if member == record_path:
            if rows[member] != ("", ""):
                raise ExampleBuildToolsError("installed RECORD has a self-hash")
            continue
        try:
            path = _inside_regular_file(
                distribution.locate_file(PurePosixPath(member)), root, "installed distribution"
            )
            raw = path.read_bytes()
        except OSError as error:
            raise ExampleBuildToolsError(
                f"installed RECORD member cannot be read: {member}"
            ) from error
        digest, size = rows[member]
        match = re.fullmatch(r"sha256=([A-Za-z0-9_-]+)", digest)
        actual = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
        if match is None or match.group(1) != actual or size != str(len(raw)):
            raise ExampleBuildToolsError(f"installed RECORD hash or size differs for {member}")
        if member == installer_path:
            installer_bytes = raw
        if member in files:
            expected = files[member]
            if type(expected) is not dict or expected.get("sha256") != _sha256(raw):
                raise ExampleBuildToolsError(
                    f"installed payload differs from built wheel: {member}"
                )
            installed_manifest[member] = True

    # Installer metadata is considered only after every RECORD member has been
    # resolved and its digest and size have been verified above.
    installer_owned_rows = set(rows) & installer_owned_candidates
    if installer_owned_rows:
        try:
            installer_name = installer_bytes.decode("utf-8").strip() if installer_bytes else ""
        except UnicodeDecodeError as error:
            raise ExampleBuildToolsError(
                "installed installer-owned metadata lacks a verified installer identity"
            ) from error
        permitted_by_installer = _INSTALLER_OWNED_DIST_INFO_FILES.get(installer_name, frozenset())
        permitted_installer_owned = {f"{dist_info}/{member}" for member in permitted_by_installer}
        if installer_bytes is None or not installer_owned_rows <= permitted_installer_owned:
            raise ExampleBuildToolsError(
                "installed distribution file inventory differs from the wheel"
            )
    module_files = provider_binding.get("module_files")
    if type(module_files) is not list or not module_files:
        raise ExampleBuildToolsError("fresh discovery has no provider module-origin rows")
    for row in module_files:
        if type(row) is not dict:
            raise ExampleBuildToolsError("fresh discovery provider module row is malformed")
        rel = row.get("relative_path")
        expected = files.get(rel) if type(rel) is str else None
        if (
            type(expected) is not dict
            or row.get("sha256") != expected.get("sha256")
            or row.get("byte_count") != expected.get("bytes")
        ):
            raise ExampleBuildToolsError(
                "fresh provider module origin differs from the exact built wheel"
            )
    return {
        "status": "installed-distribution-entry-point-and-provider-bytes-match-built-wheel",
        "installed_file_count": len(installed_manifest),
        "wheel_sha256": wheel_identity["wheel_sha256"],
        "provider_module_count": len(module_files),
    }


def _build_command(uv: str, python: Path, output: Path, cache_root: Path) -> list[str]:
    _verify_build_python(
        python,
        python.parent.parent,
        cache_root,
        _current_interpreter_identity(),
    )
    return _uv_command(
        uv,
        cache_root,
        "build",
        "--offline",
        "--no-build-isolation",
        "--python",
        str(python),
        "--wheel",
        "--out-dir",
        str(output),
    )


def _select_built_wheel(output: Path) -> Path:
    candidates = sorted(output.glob("*.whl"))
    if len(candidates) != 1:
        raise ExampleBuildToolsError(
            f"fresh build output must contain exactly one wheel, found {len(candidates)}"
        )
    wheel = candidates[0]
    if wheel.is_symlink() or not wheel.is_file() or wheel.stat().st_size == 0:
        raise ExampleBuildToolsError("built wheel is not a nonempty regular file")
    return wheel


def _assert_repo_owned_example(repo_root: Path, example_path: str) -> Path:
    relative = PurePosixPath(example_path)
    if (
        relative.is_absolute()
        or len(relative.parts) < 3
        or relative.parts[:2] != ("examples", "extensions")
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ExampleBuildToolsError("wheel build target is outside examples/extensions")
    root = repo_root.resolve()
    project = repo_root.joinpath(*relative.parts)
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ExampleBuildToolsError(f"wheel build target contains a symlink: {cursor}")
    if not project.is_dir() or not project.resolve().is_relative_to(root):
        raise ExampleBuildToolsError("wheel build target is missing or escapes the repository")
    return project.resolve()


def _target_environment_python() -> Path:
    """Return the lexical interpreter path for the active install environment."""
    executable = Path(os.path.abspath(sys.executable))
    prefix = Path(os.path.abspath(sys.prefix))
    base_prefix = Path(os.path.abspath(sys.base_prefix))
    if prefix == base_prefix:
        raise ExampleBuildToolsError("wheel installation requires an active virtual environment")
    if not executable.is_file() or not executable.is_relative_to(prefix):
        raise ExampleBuildToolsError(
            "target Python executable must be inside the active virtual environment"
        )
    return executable


def _target_python_install_argv(uv: str, cache_root: Path, wheel: Path) -> list[str]:
    """Build the install command with the active environment's lexical interpreter."""
    return _uv_command(
        uv,
        cache_root,
        "pip",
        "install",
        "--offline",
        "--no-index",
        "--reinstall",
        "--no-deps",
        "--python",
        str(_target_environment_python()),
        str(wheel),
    )


def build_and_install_example(repo_root: Path, example_path: str) -> dict[str, object]:
    """Build a fresh regular wheel, install it, and return its content identity."""
    repo_root = repo_root.resolve()
    project_path = _assert_repo_owned_example(repo_root, example_path)
    profile, profile_raw, lock, lock_raw, q2_helper_raw = _source_inputs(repo_root)
    project = _validate_project_build_system(project_path, profile, lock)
    interpreter = _interpreter_identity(profile)
    cache_root = _ensure_cache_root(repo_root / str(profile["cache_path"]), repo_root)
    uv, uv_identity = _uv_identity(cache_root)
    with _cache_lock(cache_root):
        wheelhouse = _ensure_wheelhouse(cache_root, lock, lock_raw)
        build_python, tool_probe = _ensure_build_tools_python(
            repo_root,
            profile,
            profile_raw,
            lock,
            lock_raw,
            q2_helper_raw,
            wheelhouse,
            interpreter,
            uv,
            uv_identity,
        )
        output_parent = _cache_directory(cache_root, "outputs")
        output = _new_cache_directory(
            output_parent,
            "extension-example-wheel",
            within=cache_root,
        )
        _run(
            _build_command(uv, build_python, output, cache_root),
            cache_root=cache_root,
            cwd=project_path,
        )
        wheel = _select_built_wheel(output)
        wheel_identity = _validate_wheel_identity(wheel, project, profile)
        _run(
            _target_python_install_argv(uv, cache_root, wheel),
            cache_root=cache_root,
        )
        receipt = {
            "status": "regular_wheel_built_and_exact_artifact_installed",
            "purpose": PROFILE_PURPOSE,
            "profile_sha256": _sha256(profile_raw),
            "lock_sha256": _sha256(lock_raw),
            "build_tools_cache_key": _cache_key(
                profile_raw,
                lock_raw,
                q2_helper_raw,
                Path(__file__).read_bytes(),
                interpreter,
                uv_identity,
            ),
            "tool_probe": tool_probe,
            "example": example_path,
            "wheel": {
                "filename": wheel_identity["filename"],
                "wheel_sha256": wheel_identity["wheel_sha256"],
            },
            "wheel_identity": wheel_identity,
            "publisher_identity": "not_established",
            "transitive_source_closure": "not_established",
        }
        print("[extension-example-wheel] " + json.dumps(receipt, sort_keys=True))
        return receipt
