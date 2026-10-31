"""Host-computed evidence for an installed component entry-point target."""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.machinery
import inspect
import io
import json
import os
import re
import sys
import tokenize
import tomllib
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path, PurePosixPath
from types import CodeType, FunctionType, MethodType, ModuleType
from typing import Literal
from urllib.parse import unquote, urlparse

from packaging.utils import InvalidName, canonicalize_name
from packaging.version import InvalidVersion, Version

OriginStatus = Literal["verified", "refused", "not_established"]
OriginBasis = Literal["distribution_record", "canonical_dev_source"]
ComponentFactoryStatus = Literal["verified", "delegated", "not_established"]


@dataclass(frozen=True, slots=True)
class ProviderModuleBinding:
    """Bind one loaded module file to its declaring distribution RECORD row."""

    role: str
    module: str
    relative_path: str
    byte_count: int
    sha256: str

    def as_dict(self) -> dict[str, str | int]:
        """Return the canonical file identity without copying source bytes."""
        return {
            "role": self.role,
            "module": self.module,
            "relative_path": self.relative_path,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class ProviderOriginBinding:
    """Record provider-target binding separately from delegated implementation origin."""

    group: str | None
    name: str | None
    value: str | None
    distribution_name: str | None
    distribution_version: str | None
    record_sha256: str | None
    entry_points_sha256: str | None
    status: OriginStatus
    reason_code: str | None
    target_kind: str
    module_files: tuple[ProviderModuleBinding, ...] = ()
    component_factory_status: ComponentFactoryStatus = "not_established"
    component_factory_module: str | None = None
    component_id: str | None = None
    origin_basis: OriginBasis | None = None

    @property
    def provider_target_is_bound(self) -> bool:
        """Return whether the entry-point module and callable target were host-bound."""
        return self.status == "verified"

    def as_dict(self) -> dict[str, object]:
        """Return canonical host evidence for the versioned discovery manifest."""
        return {
            "group": self.group,
            "name": self.name,
            "value": self.value,
            "distribution_name": self.distribution_name,
            "distribution_version": self.distribution_version,
            "record_sha256": self.record_sha256,
            "entry_points_sha256": self.entry_points_sha256,
            "status": self.status,
            "reason_code": self.reason_code,
            "target_kind": self.target_kind,
            "module_files": [row.as_dict() for row in self.module_files],
            "component_factory_status": self.component_factory_status,
            "component_factory_module": self.component_factory_module,
            "component_id": self.component_id,
            "origin_basis": self.origin_basis,
        }


@dataclass(frozen=True, slots=True)
class _OriginError(Exception):
    code: str
    status: OriginStatus


@dataclass(frozen=True, slots=True)
class _RecordContext:
    distribution: object
    distribution_name: str
    distribution_version: str
    base: Path
    files: dict[str, object]
    record_rows: dict[str, tuple[str, str]]
    record_sha256: str


@dataclass(frozen=True, slots=True)
class ProviderOriginContext:
    """Request-local owner context. This object is never serialized or exported."""

    record: _RecordContext
    entrypoint_module_name: str
    entrypoint_module_file: str
    canonical_source_root: Path | None = None


def _normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value.strip().lower())


def _relative_record_name(item: object) -> str:
    value = str(item).replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise _OriginError("record_path_unsupported", "not_established")
    return path.as_posix()


def _located_file(distribution: object, item: object, base: Path) -> tuple[Path, bytes]:
    try:
        path = Path(distribution.locate_file(item)).resolve(strict=True)
        if not path.is_file() or not path.is_relative_to(base):
            raise _OriginError("distribution_file_outside_root", "refused")
        return path, path.read_bytes()
    except _OriginError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _OriginError("distribution_file_unavailable", "not_established") from exc


def _canonical_dev_project_root(
    distribution: object,
    *,
    expected_distribution_name: str | None,
    editable_install: bool | None,
) -> Path | None:
    """Resolve the existing first-party editable profile only when all roots agree."""
    if editable_install is not True:
        return None
    try:
        read_text = getattr(distribution, "read_text", None)
        raw_direct_url = read_text("direct_url.json") if callable(read_text) else None
        direct_url = json.loads(raw_direct_url) if isinstance(raw_direct_url, str) else None
        if not isinstance(direct_url, dict):
            return None
        dir_info = direct_url.get("dir_info")
        parsed_url = urlparse(str(direct_url.get("url") or ""))
        if not isinstance(dir_info, dict) or dir_info.get("editable") is not True:
            return None
        if parsed_url.scheme != "file" or parsed_url.netloc not in {"", "localhost"}:
            return None
        declared_root = Path(unquote(parsed_url.path)).resolve(strict=True)

        package = sys.modules.get("polisyos")
        package_file_raw = getattr(package, "__file__", None)
        if not isinstance(package_file_raw, str):
            return None
        package_file = Path(package_file_raw).resolve(strict=True)
        if package_file.name != "__init__.py":
            return None
        project_root = package_file.parents[2]
        expected_package_file = project_root / "src" / "polisyos" / "__init__.py"
        if package_file != expected_package_file.resolve(strict=True):
            return None
        pyproject = project_root / "pyproject.toml"
        project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
        project_name = project.get("name") if isinstance(project, dict) else None
        if not isinstance(project_name, str):
            return None
        if _normalize_distribution_name(project_name) != expected_distribution_name:
            return None
        if declared_root != project_root.resolve(strict=True):
            return None
        return project_root
    except (OSError, RuntimeError, TypeError, UnicodeError, ValueError, tomllib.TOMLDecodeError):
        return None


def _canonical_module_file(root: Path, module_name: str) -> tuple[str, Path]:
    source_root = (root / "src").resolve(strict=True)
    matches: list[tuple[str, Path]] = []
    for name in _module_names(module_name):
        path = source_root / PurePosixPath(name)
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            continue
        if resolved.is_file() and resolved.is_relative_to(source_root):
            relative = resolved.relative_to(root).as_posix()
            matches.append((relative, resolved))
    if len(matches) != 1:
        raise _OriginError("canonical_dev_module_missing_or_ambiguous", "not_established")
    return matches[0]


def _bind_canonical_module(
    root: Path,
    module: ModuleType,
    *,
    role: str,
    expected_relative_path: str | None = None,
) -> ProviderModuleBinding:
    origin = _module_origin(module)
    if expected_relative_path is None:
        expected_relative_path, _ = _canonical_module_file(root, module.__name__)
    expected_path = (root / PurePosixPath(expected_relative_path)).resolve(strict=True)
    if origin != expected_path or not origin.is_relative_to(root / "src" / "polisyos"):
        raise _OriginError("canonical_dev_module_origin_mismatch", "refused")
    data = origin.read_bytes()
    return ProviderModuleBinding(
        role=role,
        module=module.__name__,
        relative_path=expected_relative_path,
        byte_count=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _editable_script_record_name(item: object) -> str:
    value = str(item).replace(chr(92), "/")
    parts = value.split("/")
    if (
        value.startswith("/")
        or len(parts) < 3
        or parts[-2] != "bin"
        or not parts[-1]
        or parts[-1] in {".", ".."}
        or not all(part == ".." for part in parts[:-2])
    ):
        raise _OriginError("record_path_unsupported", "not_established")
    return value


def _verify_editable_script_record(
    distribution: object,
    item: object,
    name: str,
    row: tuple[str, str],
) -> None:
    try:
        path = Path(distribution.locate_file(item)).resolve(strict=True)
        scripts_name = "Scripts" if os.name == "nt" else "bin"
        scripts_root = (Path(sys.prefix) / scripts_name).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _OriginError("editable_record_script_unavailable", "not_established") from exc
    if not path.is_file() or path.parent != scripts_root or path.name != name.rsplit("/", 1)[-1]:
        raise _OriginError("editable_record_script_outside_environment_bin", "refused")
    hash_field, size_field = row
    if not hash_field.startswith("sha256=") or not size_field.isdecimal():
        raise _OriginError("editable_record_script_hash_or_size_unsupported", "not_established")
    try:
        expected_digest = base64.urlsafe_b64decode(
            hash_field.removeprefix("sha256=")
            + "=" * (-len(hash_field.removeprefix("sha256=")) % 4)
        )
        data = path.read_bytes()
    except (OSError, ValueError, TypeError) as exc:
        raise _OriginError("editable_record_script_unavailable", "not_established") from exc
    if len(data) != int(size_field) or hashlib.sha256(data).digest() != expected_digest:
        raise _OriginError("editable_record_script_record_mismatch", "refused")


def _read_record_context(
    distribution: object,
    *,
    distribution_name: str,
    distribution_version: str,
    allow_editable_scripts: bool = False,
) -> _RecordContext:
    try:
        raw_files = getattr(distribution, "files", None)
        if raw_files is None:
            raise _OriginError("distribution_file_list_missing", "not_established")
        files: dict[str, object] = {}
        for item in raw_files:
            try:
                name = _relative_record_name(item)
            except _OriginError:
                if not allow_editable_scripts:
                    raise
                name = _editable_script_record_name(item)
            if name in files:
                raise _OriginError("distribution_file_list_ambiguous", "not_established")
            files[name] = item
        base = Path(distribution.locate_file("")).resolve(strict=True)
        record_names = [
            name
            for name in files
            if name.endswith(".dist-info/RECORD") and len(PurePosixPath(name).parts) >= 2
        ]
        if len(record_names) != 1:
            raise _OriginError("record_file_missing_or_ambiguous", "not_established")
        record_name = record_names[0]
        _, record_bytes = _located_file(distribution, files[record_name], base)
        rows: dict[str, tuple[str, str]] = {}
        for row in csv.reader(io.StringIO(record_bytes.decode("utf-8"), newline="")):
            if len(row) != 3:
                raise _OriginError("record_row_malformed", "refused")
            try:
                name = _relative_record_name(row[0])
            except _OriginError:
                if not allow_editable_scripts:
                    raise
                name = _editable_script_record_name(row[0])
            if name in rows:
                raise _OriginError("record_row_ambiguous", "refused")
            rows[name] = (row[1], row[2])
        if set(rows) != set(files):
            raise _OriginError("record_file_set_mismatch", "refused")
        if allow_editable_scripts:
            for name, item in files.items():
                try:
                    _relative_record_name(item)
                except _OriginError:
                    _verify_editable_script_record(distribution, item, name, rows[name])
        return _RecordContext(
            distribution=distribution,
            distribution_name=distribution_name,
            distribution_version=distribution_version,
            base=base,
            files=files,
            record_rows=rows,
            record_sha256=hashlib.sha256(record_bytes).hexdigest(),
        )
    except _OriginError:
        raise
    except (OSError, UnicodeError, csv.Error, RuntimeError, TypeError, ValueError) as exc:
        raise _OriginError("record_unavailable_or_malformed", "not_established") from exc


def _read_verified_file(
    context: _RecordContext,
    name: str,
    *,
    role: str,
    module: str,
) -> ProviderModuleBinding:
    item = context.files.get(name)
    row = context.record_rows.get(name)
    if item is None or row is None:
        raise _OriginError("target_file_not_in_record", "refused")
    hash_field, size_field = row
    if not hash_field.startswith("sha256=") or not size_field.isdecimal():
        raise _OriginError("target_record_hash_or_size_unsupported", "not_established")
    encoded_digest = hash_field.removeprefix("sha256=")
    try:
        expected_digest = base64.urlsafe_b64decode(
            encoded_digest + "=" * (-len(encoded_digest) % 4)
        )
        _, data = _located_file(context.distribution, item, context.base)
    except _OriginError:
        raise
    except (ValueError, TypeError, OSError) as exc:
        raise _OriginError("target_record_encoding_invalid", "refused") from exc
    if len(data) != int(size_field):
        raise _OriginError("target_record_size_mismatch", "refused")
    if hashlib.sha256(data).digest() != expected_digest:
        raise _OriginError("target_record_hash_mismatch", "refused")
    return ProviderModuleBinding(
        role=role,
        module=module,
        relative_path=name,
        byte_count=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _module_names(module_name: str) -> tuple[str, ...]:
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", module_name):
        raise _OriginError("entrypoint_module_name_unsupported", "not_established")
    base = module_name.replace(".", "/")
    names = [f"{base}.py", f"{base}/__init__.py"]
    names.extend(f"{base}{suffix}" for suffix in importlib.machinery.EXTENSION_SUFFIXES)
    names.extend(f"{base}/__init__{suffix}" for suffix in importlib.machinery.EXTENSION_SUFFIXES)
    return tuple(names)


def _module_file_name(context: _RecordContext, module_name: str) -> str:
    matches = sorted(set(_module_names(module_name)).intersection(context.files))
    if len(matches) != 1:
        raise _OriginError("entrypoint_module_record_missing_or_ambiguous", "refused")
    return matches[0]


def _module_origin(module: ModuleType) -> Path:
    spec = getattr(module, "__spec__", None)
    origin = getattr(spec, "origin", None)
    if not isinstance(origin, str) or not origin or origin in {"built-in", "frozen"}:
        raise _OriginError("module_origin_not_file", "not_established")
    try:
        path = Path(origin).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _OriginError("module_origin_unavailable", "not_established") from exc
    if not path.is_file():
        raise _OriginError("module_origin_not_regular_file", "not_established")
    return path


def _bind_loaded_module(
    context: _RecordContext,
    module: ModuleType,
    *,
    role: str,
    expected_name: str | None = None,
) -> ProviderModuleBinding:
    origin = _module_origin(module)
    name = expected_name or _module_file_name(context, module.__name__)
    path, _ = _located_file(context.distribution, context.files[name], context.base)
    if path != origin:
        raise _OriginError("loaded_module_origin_mismatch", "refused")
    return _read_verified_file(context, name, role=role, module=module.__name__)


def _module_for_globals(globals_dict: dict[str, object]) -> ModuleType:
    name = globals_dict.get("__name__")
    if not isinstance(name, str):
        raise _OriginError("callable_globals_module_missing", "not_established")
    module = sys.modules.get(name)
    if not isinstance(module, ModuleType) or module.__dict__ is not globals_dict:
        raise _OriginError("callable_globals_not_loaded_module", "not_established")
    return module


def _code_tree_contains(parent: CodeType, target: CodeType) -> bool:
    if parent == target:
        return True
    return any(
        _code_tree_contains(value, target)
        for value in parent.co_consts
        if isinstance(value, CodeType)
    )


def _callable_source(value: object) -> tuple[ModuleType, Path]:
    target = value
    while isinstance(target, partial):
        target = target.func
    if isinstance(target, MethodType):
        target = target.__func__
    function: FunctionType | None = None
    if isinstance(target, FunctionType):
        function = target
    elif isinstance(target, type):
        initializer = inspect.getattr_static(target, "__init__", None)
        if isinstance(initializer, FunctionType):
            function = initializer
    else:
        call = inspect.getattr_static(type(target), "__call__", None)
        if isinstance(call, FunctionType):
            function = call
    if function is None:
        raise _OriginError("callable_code_origin_unsupported", "not_established")
    module = _module_for_globals(function.__globals__)
    try:
        code_path = Path(function.__code__.co_filename).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _OriginError("callable_code_file_unavailable", "not_established") from exc
    if code_path != _module_origin(module):
        raise _OriginError("callable_code_module_mismatch", "refused")
    try:
        with tokenize.open(code_path) as source_file:
            module_source = source_file.read()
        source_code = compile(
            module_source,
            str(code_path),
            "exec",
            dont_inherit=True,
            optimize=sys.flags.optimize,
        )
    except (OSError, SyntaxError, UnicodeError, ValueError) as exc:
        raise _OriginError("callable_module_source_unavailable", "not_established") from exc
    if not _code_tree_contains(source_code, function.__code__):
        raise _OriginError("callable_code_not_in_module_source", "refused")
    return module, code_path


def describe_callable_source(function: object, *, expected_module: str) -> dict[str, str]:
    """Observe a direct Python callable's current source without invoking it.

    This reuses the component origin reader's code-to-module reconciliation.
    It does not authenticate dependencies, installation records, a publisher,
    permission, or subsequent executions. It is descriptive evidence only.

    Args:
        function: Direct Python function whose current source is observed.
        expected_module: Required module name or parent module namespace.

    Returns:
        Recomputed direct source coordinates and file digest, or only a
        ``not_established`` basis when the source cannot be reconciled.
    """
    if not isinstance(function, FunctionType):
        return {"basis": "not_established"}
    try:
        module, source = _callable_source(function)
        if module.__name__ != expected_module and not module.__name__.startswith(
            expected_module + "."
        ):
            return {"basis": "not_established"}
        return {
            "basis": "recomputed",
            "module": module.__name__,
            "qualname": function.__qualname__,
            "module_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    except (_OriginError, OSError, RuntimeError, TypeError, ValueError):
        return {"basis": "not_established"}


def _failure_binding(
    ep: object,
    *,
    status: OriginStatus,
    reason_code: str,
    distribution_name: str | None = None,
    distribution_version: str | None = None,
    record_sha256: str | None = None,
    entry_points_sha256: str | None = None,
    target_kind: str = "unknown",
) -> ProviderOriginBinding:
    def observed_text(field_name: str) -> str | None:
        try:
            value = getattr(ep, field_name, None)
        except (AttributeError, LookupError, RuntimeError, TypeError, ValueError):
            return None
        return value if isinstance(value, str) else None

    return ProviderOriginBinding(
        group=observed_text("group"),
        name=observed_text("name"),
        value=observed_text("value"),
        distribution_name=distribution_name,
        distribution_version=distribution_version,
        record_sha256=record_sha256,
        entry_points_sha256=entry_points_sha256,
        status=status,
        reason_code=reason_code,
        target_kind=target_kind,
    )


def preflight_entry_point_target(
    ep: object,
    *,
    expected_distribution_name: str | None,
    expected_distribution_version: str | None,
    expected_identity_is_bound: bool,
    expected_group: str,
    expected_name: str,
    expected_value: str,
    expected_entry_points_sha256: str | None,
    editable_install: bool | None,
) -> tuple[ProviderOriginBinding, ProviderOriginContext | None]:
    """Bind owner declaration and module bytes before importing the target."""
    distribution = getattr(ep, "dist", None)
    if distribution is None:
        return (
            _failure_binding(
                ep,
                status="not_established",
                reason_code="declaring_distribution_missing",
            ),
            None,
        )
    try:
        if expected_identity_is_bound is not True:
            raise _OriginError("entrypoint_identity_incomplete", "not_established")
        expected_fields = (expected_group, expected_name, expected_value)
        if any(not isinstance(value, str) or not value.strip() for value in expected_fields):
            raise _OriginError("entrypoint_identity_incomplete", "not_established")
        if (
            not isinstance(expected_entry_points_sha256, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", expected_entry_points_sha256) is None
        ):
            raise _OriginError("entrypoint_identity_incomplete", "not_established")
        if (
            not isinstance(expected_distribution_name, str)
            or not expected_distribution_name.strip()
            or not isinstance(expected_distribution_version, str)
            or not expected_distribution_version.strip()
        ):
            raise _OriginError("declaring_distribution_identity_incomplete", "not_established")
        if expected_distribution_version != expected_distribution_version.strip():
            raise _OriginError("declaring_distribution_identity_invalid", "not_established")
        try:
            normalized_expected_name = canonicalize_name(
                expected_distribution_name,
                validate=True,
            )
            Version(expected_distribution_version)
        except (InvalidName, InvalidVersion) as exc:
            raise _OriginError(
                "declaring_distribution_identity_invalid",
                "not_established",
            ) from exc
        if normalized_expected_name != expected_distribution_name:
            raise _OriginError("declaring_distribution_identity_invalid", "not_established")

        metadata = getattr(distribution, "metadata", None)
        get = getattr(metadata, "get", None)
        raw_name = get("Name") if callable(get) else None
        raw_version = getattr(distribution, "version", None)
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise _OriginError("declaring_distribution_name_missing", "not_established")
        if not isinstance(raw_version, str) or not raw_version.strip():
            raise _OriginError("declaring_distribution_version_missing", "not_established")
        if raw_version != raw_version.strip():
            raise _OriginError("declaring_distribution_identity_invalid", "not_established")
        try:
            actual_name = canonicalize_name(raw_name, validate=True)
            Version(raw_version)
        except (InvalidName, InvalidVersion) as exc:
            raise _OriginError(
                "declaring_distribution_identity_invalid",
                "not_established",
            ) from exc
        actual_version = raw_version
        if (
            actual_name != expected_distribution_name
            or actual_version != expected_distribution_version
        ):
            raise _OriginError("declaring_distribution_identity_mismatch", "refused")

        raw_group = getattr(ep, "group", None)
        raw_entry_name = getattr(ep, "name", None)
        raw_value = getattr(ep, "value", None)
        if not all(
            isinstance(value, str) and value.strip()
            for value in (raw_group, raw_entry_name, raw_value)
        ):
            raise _OriginError("entrypoint_declaration_incomplete", "not_established")
        group = raw_group
        name = raw_entry_name
        value = raw_value
        if (group, name, value) != expected_fields:
            raise _OriginError("entrypoint_identity_changed", "refused")
        raw_module_name = getattr(ep, "module", None)
        if not isinstance(raw_module_name, str) or not raw_module_name.strip():
            raise _OriginError("entrypoint_declaration_incomplete", "not_established")
        module_name = raw_module_name

        canonical_source_root = _canonical_dev_project_root(
            distribution,
            expected_distribution_name=expected_distribution_name,
            editable_install=editable_install,
        )
        if editable_install is True and canonical_source_root is None:
            raise _OriginError("editable_install_source_not_canonical", "not_established")
        record = _read_record_context(
            distribution,
            distribution_name=actual_name,
            distribution_version=actual_version,
            allow_editable_scripts=canonical_source_root is not None,
        )
        ep_files = [path for path in record.files if path.endswith(".dist-info/entry_points.txt")]
        if len(ep_files) != 1:
            raise _OriginError(
                "entrypoint_declaration_file_missing_or_ambiguous",
                "not_established",
            )
        ep_file = ep_files[0]
        declaration_binding = _read_verified_file(
            record,
            ep_file,
            role="entry_point_declaration",
            module="",
        )
        _, declaration_bytes = _located_file(
            record.distribution,
            record.files[ep_file],
            record.base,
        )
        declaration_identity_hash = "sha256:" + hashlib.sha256(declaration_bytes).hexdigest()
        if declaration_identity_hash != expected_entry_points_sha256:
            raise _OriginError("entrypoint_identity_declaration_bytes_mismatch", "refused")
        parser = ConfigParser(interpolation=None, strict=True)
        parser.optionxform = str
        parser.read_string(declaration_bytes.decode("utf-8"))
        if not parser.has_section(group) or not parser.has_option(group, name):
            raise _OriginError("entrypoint_declaration_not_in_recorded_file", "refused")
        if parser.get(group, name).strip() != value.strip():
            raise _OriginError("entrypoint_declaration_value_mismatch", "refused")

        if canonical_source_root is None:
            module_file = _module_file_name(record, module_name)
            module_binding = _read_verified_file(
                record,
                module_file,
                role="entrypoint_module",
                module=module_name,
            )
            origin_basis: OriginBasis = "distribution_record"
        else:
            module_file, module_path = _canonical_module_file(
                canonical_source_root,
                module_name,
            )
            module_bytes = module_path.read_bytes()
            module_binding = ProviderModuleBinding(
                role="entrypoint_module",
                module=module_name,
                relative_path=module_file,
                byte_count=len(module_bytes),
                sha256=hashlib.sha256(module_bytes).hexdigest(),
            )
            origin_basis = "canonical_dev_source"
        binding = ProviderOriginBinding(
            group=group,
            name=name,
            value=value,
            distribution_name=actual_name,
            distribution_version=actual_version,
            record_sha256=record.record_sha256,
            entry_points_sha256=hashlib.sha256(declaration_bytes).hexdigest(),
            status="verified",
            reason_code=None,
            target_kind="declared_module",
            module_files=(declaration_binding, module_binding),
            origin_basis=origin_basis,
        )
        return (
            binding,
            ProviderOriginContext(
                record,
                module_name,
                module_file,
                canonical_source_root=canonical_source_root,
            ),
        )
    except ConfigParserError:
        return _failure_binding(
            ep,
            status="refused",
            reason_code="entrypoint_declaration_malformed",
            distribution_name=expected_distribution_name,
            distribution_version=expected_distribution_version,
        ), None
    except _OriginError as exc:
        return _failure_binding(
            ep,
            status=exc.status,
            reason_code=exc.code,
            distribution_name=expected_distribution_name,
            distribution_version=expected_distribution_version,
        ), None
    except (
        AttributeError,
        LookupError,
        OSError,
        UnicodeError,
        csv.Error,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        return _failure_binding(
            ep,
            status="not_established",
            reason_code=f"origin_preflight_failed:{type(exc).__name__}",
            distribution_name=expected_distribution_name,
            distribution_version=expected_distribution_version,
        ), None


def bind_loaded_entry_point_target(
    context: ProviderOriginContext,
    binding: ProviderOriginBinding,
    loaded: object,
    *,
    is_component: bool,
) -> ProviderOriginBinding:
    """Check actual module and callable globals against pre-import owner evidence."""
    if binding.status != "verified":
        return binding
    try:
        module = sys.modules.get(context.entrypoint_module_name)
        if not isinstance(module, ModuleType):
            raise _OriginError("entrypoint_module_not_loaded", "not_established")
        if context.canonical_source_root is None:
            entrypoint_file = _bind_loaded_module(
                context.record,
                module,
                role="entrypoint_module",
                expected_name=context.entrypoint_module_file,
            )
        else:
            entrypoint_file = _bind_canonical_module(
                context.canonical_source_root,
                module,
                role="entrypoint_module",
                expected_relative_path=context.entrypoint_module_file,
            )
        files = [row for row in binding.module_files if row.role != "entrypoint_module"]
        files.append(entrypoint_file)
        target_kind = "component_object" if is_component else "declaration"
        if not is_component and callable(loaded):
            factory_module, _ = _callable_source(loaded)
            files.append(
                _bind_loaded_module(
                    context.record,
                    factory_module,
                    role="provider_factory",
                )
            )
            target_kind = "callable_factory"
        return replace(
            binding,
            target_kind=target_kind,
            module_files=tuple(
                sorted(
                    {(row.role, row.module, row.relative_path): row for row in files}.values(),
                    key=lambda row: (row.role, row.module, row.relative_path),
                )
            ),
        )
    except _OriginError as exc:
        return replace(binding, status=exc.status, reason_code=exc.code)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return replace(
            binding,
            status="not_established",
            reason_code=f"loaded_target_origin_failed:{type(exc).__name__}",
        )


def bind_component_factory_origin(
    context: ProviderOriginContext,
    binding: ProviderOriginBinding,
    component: object,
    *,
    component_id: str,
) -> ProviderOriginBinding:
    """Bind Component.create to its owner or label it as delegation for Fabric."""
    if binding.status != "verified":
        return replace(binding, component_id=component_id)
    try:
        method = inspect.getattr_static(component, "create", None)
        factory_module, _ = _callable_source(method)
        if context.canonical_source_root is None:
            factory_file = _bind_loaded_module(
                context.record,
                factory_module,
                role="component_factory",
            )
        else:
            factory_file = _bind_canonical_module(
                context.canonical_source_root,
                factory_module,
                role="component_factory",
            )
        files = [*binding.module_files, factory_file]
        return replace(
            binding,
            module_files=tuple(
                sorted(
                    {(row.role, row.module, row.relative_path): row for row in files}.values(),
                    key=lambda row: (row.role, row.module, row.relative_path),
                )
            ),
            component_factory_status="verified",
            component_factory_module=factory_module.__name__,
            component_id=component_id,
        )
    except _OriginError as exc:
        if exc.code in {
            "target_file_not_in_record",
            "entrypoint_module_record_missing_or_ambiguous",
        }:
            try:
                method = inspect.getattr_static(component, "create", None)
                factory_module, _ = _callable_source(method)
                return replace(
                    binding,
                    component_factory_status="delegated",
                    component_factory_module=factory_module.__name__,
                    component_id=component_id,
                )
            except _OriginError as nested:
                return replace(
                    binding,
                    component_factory_status="not_established",
                    reason_code=nested.code,
                    component_id=component_id,
                )
        return replace(
            binding,
            component_factory_status="not_established",
            reason_code=exc.code,
            component_id=component_id,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return replace(
            binding,
            component_factory_status="not_established",
            reason_code=f"component_factory_origin_failed:{type(exc).__name__}",
            component_id=component_id,
        )


def unbound_entry_point(ep: object, *, reason_code: str) -> ProviderOriginBinding:
    """Create host diagnostics when an entrypoint failed before a proof existed."""
    return _failure_binding(ep, status="not_established", reason_code=reason_code)
