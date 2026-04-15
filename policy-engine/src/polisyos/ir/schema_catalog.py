"""Unified reflection catalog for IR contracts, facades, and schema snapshots."""
from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any, ForwardRef, get_args, get_origin

from pydantic import BaseModel, RootModel

try:  # pragma: no cover - available in repo/test env, optional for slim installs.
    from schemas.abi_models import ABIModelEntry, select_abi_entries
except ImportError:  # pragma: no cover
    ABIModelEntry = Any  # type: ignore[assignment]

    def select_abi_entries(  # type: ignore[no-redef]
        filters: object,
        *,
        include_deprecated: bool = False,
    ) -> tuple[Any, ...]:
        del filters, include_deprecated
        return ()

from polisyos.ir.migrations.base import CompatibilityMode, get_schema_rule

_IR_PACKAGE = "polisyos.ir"
_SECTION_ORDER = (
    "analytics",
    "artifacts",
    "governance",
    "kernel",
    "linker",
    "migrations",
    "observation",
    "trinity",
    "world",
)


class IRTypeKind(str, Enum):
    """Classify the structural shape of one IR symbol."""

    PYDANTIC_MODEL = "pydantic_model"
    ROOT_MODEL = "root_model"
    ENUM = "enum"
    DATACLASS = "dataclass"
    PROTOCOL = "protocol"
    CLASS = "class"


class IRPublicStatus(str, Enum):
    """Describe how a symbol becomes part of the supported IR surface."""

    ROOT_FACADE = "root_facade"
    PACKAGE_FACADE = "package_facade"
    SNAPSHOT_ONLY = "snapshot_only"
    INTERNAL = "internal"


@dataclass(frozen=True)
class IRFieldInfo:
    """Structured field metadata exposed by the reflection catalog."""

    name: str
    annotation: str
    required: bool
    default: str | None
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class IRTypeInfo:
    """Catalog entry for one IR class or enum."""

    name: str
    qualname: str
    fqn: str
    module: str
    kind: IRTypeKind
    schema_version: str | None
    public_status: IRPublicStatus
    exported_from: tuple[str, ...]
    docs_link: str
    summary: str | None
    fields: tuple[IRFieldInfo, ...] = ()
    refs: tuple[str, ...] = ()
    enum_values: tuple[str, ...] = ()
    abi_key: str | None = None
    abi_schema_file: str | None = None
    abi_priority: str | None = None
    compat_mode: CompatibilityMode | None = None
    compat_readable_versions: tuple[str, ...] = ()
    compat_writable_versions: tuple[str, ...] = ()

    @property
    def field_count(self) -> int:
        return len(self.fields)

    @property
    def section(self) -> str:
        remainder = self.module.removeprefix(f"{_IR_PACKAGE}.")
        return remainder.split(".", 1)[0] if remainder else "root"


@dataclass(frozen=True)
class IRExportInfo:
    """One exported symbol from a package facade."""

    package: str
    export_name: str
    target_fqn: str


@dataclass(frozen=True)
class IRSchemaCatalog:
    """Snapshot of the current importable IR type surface."""

    types: tuple[IRTypeInfo, ...]
    exports: tuple[IRExportInfo, ...]

    @property
    def public_types(self) -> tuple[IRTypeInfo, ...]:
        return tuple(
            entry
            for entry in self.types
            if entry.public_status in {IRPublicStatus.ROOT_FACADE, IRPublicStatus.PACKAGE_FACADE}
        )

    @property
    def snapshot_types(self) -> tuple[IRTypeInfo, ...]:
        return tuple(entry for entry in self.types if entry.abi_key is not None)

    @property
    def sections(self) -> tuple[str, ...]:
        present = {entry.section for entry in self.types}
        ordered = [section for section in _SECTION_ORDER if section in present]
        extras = sorted(present.difference(_SECTION_ORDER))
        return tuple(ordered + extras)

    def get(self, name_or_fqn: str) -> IRTypeInfo:
        lookup = str(name_or_fqn)
        for entry in self.types:
            if entry.fqn == lookup or entry.name == lookup:
                return entry
        raise KeyError(f"Unknown IR type: {lookup}")

    def list(
        self,
        *,
        public_only: bool = False,
        section: str | None = None,
        kind: IRTypeKind | str | None = None,
    ) -> tuple[IRTypeInfo, ...]:
        items = self.types
        if public_only:
            items = tuple(
                entry
                for entry in items
                if entry.public_status is not IRPublicStatus.INTERNAL
            )
        if section is not None:
            items = tuple(entry for entry in items if entry.section == section)
        if kind is not None:
            kind_value = IRTypeKind(kind)
            items = tuple(entry for entry in items if entry.kind is kind_value)
        return items

    def export_enumeration(self, package: str | None = None) -> tuple[IRExportInfo, ...]:
        if package is None:
            return self.exports
        normalized = package if package.startswith(_IR_PACKAGE) else f"{_IR_PACKAGE}.{package}"
        if normalized == f"{_IR_PACKAGE}.root":
            normalized = _IR_PACKAGE
        return tuple(entry for entry in self.exports if entry.package == normalized)


def catalog_anchor(fqn: str) -> str:
    """Return the stable anchor slug used in generated reference pages."""

    normalized = re.sub(r"[^a-z0-9]+", "-", fqn.lower())
    return normalized.strip("-")


def list_ir_types(
    *,
    public_only: bool = False,
    section: str | None = None,
    kind: IRTypeKind | str | None = None,
) -> tuple[IRTypeInfo, ...]:
    """List reflected IR types with optional filtering."""

    return get_ir_schema_catalog().list(public_only=public_only, section=section, kind=kind)


def get_ir_type(name_or_fqn: str) -> IRTypeInfo:
    """Look up one IR type by short name or fully qualified name."""

    return get_ir_schema_catalog().get(name_or_fqn)


def inspect_ir_schema(name_or_fqn: str) -> IRTypeInfo:
    """Alias for :func:`get_ir_type` used by tooling/readability docs."""

    return get_ir_type(name_or_fqn)


def enumerate_ir_exports(package: str | None = None) -> tuple[IRExportInfo, ...]:
    """Enumerate the exported names declared by root/package facades."""

    return get_ir_schema_catalog().export_enumeration(package=package)


@lru_cache(maxsize=1)
def get_ir_schema_catalog() -> IRSchemaCatalog:
    """Build and cache the unified IR reflection catalog."""

    modules = _import_ir_modules()
    type_map = _collect_type_symbols(modules)
    export_map = _collect_export_map()
    abi_entries = _collect_abi_entries()
    types = tuple(
        sorted(
            (
                _build_type_info(
                    obj,
                    fqn=fqn,
                    export_map=export_map,
                    abi_entry=abi_entries.get(fqn),
                    type_index=type_map,
                )
                for fqn, obj in type_map.items()
            ),
            key=lambda entry: (entry.section, entry.module, entry.name),
        )
    )
    exports = tuple(
        sorted(
            (
                IRExportInfo(package=package, export_name=name, target_fqn=target_fqn)
                for target_fqn, package_exports in export_map.items()
                for package, name in sorted(package_exports)
            ),
            key=lambda entry: (entry.package, entry.export_name),
        )
    )
    return IRSchemaCatalog(types=types, exports=exports)


def _import_ir_modules() -> tuple[Any, ...]:
    root = importlib.import_module(_IR_PACKAGE)
    modules = [root]
    for module_info in pkgutil.walk_packages(root.__path__, prefix=f"{_IR_PACKAGE}."):
        if ".ddl." in module_info.name:
            continue
        modules.append(importlib.import_module(module_info.name))
    return tuple(sorted(modules, key=lambda module: module.__name__))


def _collect_type_symbols(modules: tuple[Any, ...]) -> dict[str, type[Any]]:
    result: dict[str, type[Any]] = {}
    for module in modules:
        for name, obj in vars(module).items():
            if name.startswith("_") or not inspect.isclass(obj):
                continue
            if obj.__module__ != module.__name__:
                continue
            if not obj.__module__.startswith(_IR_PACKAGE):
                continue
            result[f"{obj.__module__}.{obj.__qualname__}"] = obj
    return result


def _collect_export_map() -> dict[str, set[tuple[str, str]]]:
    from polisyos.ir.public_surface import PACKAGE_FACADE_EXPORTS

    result: dict[str, set[tuple[str, str]]] = {}
    for package in _public_packages():
        module = importlib.import_module(package)
        package_key = package.removeprefix(f"{_IR_PACKAGE}.")
        manifest_exports = PACKAGE_FACADE_EXPORTS.get(package_key)
        if manifest_exports is not None:
            for export_name, (target_module, target_name) in manifest_exports.items():
                target_fqn = f"{target_module}.{target_name}"
                result.setdefault(target_fqn, set()).add((package, export_name))
            continue
        lazy_imports = getattr(module, "_LAZY_IMPORTS", None)
        if isinstance(lazy_imports, dict):
            for export_name, (target_module, target_name) in lazy_imports.items():
                target_fqn = f"{target_module}.{target_name}"
                result.setdefault(target_fqn, set()).add((package, export_name))
            continue
        for export_name in getattr(module, "__all__", ()):
            target = getattr(module, export_name)
            target_module = getattr(target, "__module__", None)
            target_name = getattr(target, "__qualname__", export_name)
            if target_module is None or not str(target_module).startswith(_IR_PACKAGE):
                continue
            target_fqn = f"{target_module}.{target_name}"
            result.setdefault(target_fqn, set()).add((package, export_name))
    return result


def _public_packages() -> tuple[str, ...]:
    root = importlib.import_module(_IR_PACKAGE)
    packages = [_IR_PACKAGE]
    for module_info in pkgutil.iter_modules(root.__path__, prefix=f"{_IR_PACKAGE}."):
        if not module_info.ispkg:
            continue
        package = importlib.import_module(module_info.name)
        if getattr(package, "__all__", None):
            packages.append(module_info.name)
    return tuple(sorted(packages))


def _collect_abi_entries() -> dict[str, ABIModelEntry]:
    entries = select_abi_entries(None, include_deprecated=True)
    return {entry.fqn: entry for entry in entries}


def _build_type_info(
    obj: type[Any],
    *,
    fqn: str,
    export_map: dict[str, set[tuple[str, str]]],
    abi_entry: ABIModelEntry | None,
    type_index: dict[str, type[Any]],
) -> IRTypeInfo:
    kind = _kind_for(obj)
    fields = _fields_for(obj)
    refs = tuple(sorted({ref for field in fields for ref in field.references}))
    exported_from = tuple(
        sorted(
            f"{package}:{export_name}" if package != _IR_PACKAGE else f"{package}:{export_name}"
            for package, export_name in export_map.get(fqn, set())
        )
    )
    public_status = _public_status_for(exported_from, abi_entry)
    schema_version = _schema_version_for(obj, abi_entry)
    compat_mode: CompatibilityMode | None = None
    readable_versions: tuple[str, ...] = ()
    writable_versions: tuple[str, ...] = ()
    if abi_entry is not None and schema_version is not None:
        rule = get_schema_rule(abi_entry.abi_key, schema_version)
        if rule is not None:
            compat_mode = rule.mode
            readable_versions = tuple(sorted(rule.readable_versions))
            writable_versions = tuple(sorted(rule.writable_versions))
    docs_link = f"schema-catalog.md#{catalog_anchor(fqn)}"
    return IRTypeInfo(
        name=obj.__name__,
        qualname=obj.__qualname__,
        fqn=fqn,
        module=obj.__module__,
        kind=kind,
        schema_version=schema_version,
        public_status=public_status,
        exported_from=exported_from,
        docs_link=docs_link,
        summary=_summary_for(obj),
        fields=fields,
        refs=refs,
        enum_values=_enum_values_for(obj),
        abi_key=getattr(abi_entry, "abi_key", None),
        abi_schema_file=getattr(abi_entry, "schema_file", None),
        abi_priority=getattr(getattr(abi_entry, "priority", None), "value", None),
        compat_mode=compat_mode,
        compat_readable_versions=readable_versions,
        compat_writable_versions=writable_versions,
    )


def _kind_for(obj: type[Any]) -> IRTypeKind:
    if inspect.isclass(obj) and issubclass(obj, Enum):
        return IRTypeKind.ENUM
    if inspect.isclass(obj) and issubclass(obj, RootModel):
        return IRTypeKind.ROOT_MODEL
    if inspect.isclass(obj) and issubclass(obj, BaseModel):
        return IRTypeKind.PYDANTIC_MODEL
    if getattr(obj, "_is_protocol", False):
        return IRTypeKind.PROTOCOL
    if dataclasses.is_dataclass(obj):
        return IRTypeKind.DATACLASS
    return IRTypeKind.CLASS


def _public_status_for(
    exported_from: tuple[str, ...],
    abi_entry: ABIModelEntry | None,
) -> IRPublicStatus:
    if any(entry.startswith(f"{_IR_PACKAGE}:") for entry in exported_from):
        return IRPublicStatus.ROOT_FACADE
    if exported_from:
        return IRPublicStatus.PACKAGE_FACADE
    if abi_entry is not None:
        return IRPublicStatus.SNAPSHOT_ONLY
    return IRPublicStatus.INTERNAL


def _schema_version_for(obj: type[Any], abi_entry: ABIModelEntry | None) -> str | None:
    version_field = getattr(abi_entry, "version_field", "schema_version")
    if version_field is None:
        return None

    model_fields = getattr(obj, "model_fields", None)
    if isinstance(model_fields, dict) and version_field in model_fields:
        default = getattr(model_fields[version_field], "default", None)
        if default not in {None, inspect._empty}:
            return str(default)

    default_value = getattr(obj, version_field, None)
    if default_value is not None:
        return str(default_value)
    return None


def _summary_for(obj: type[Any]) -> str | None:
    doc = inspect.getdoc(obj)
    if not doc:
        return None
    return doc.strip().splitlines()[0]


def _enum_values_for(obj: type[Any]) -> tuple[str, ...]:
    if not (inspect.isclass(obj) and issubclass(obj, Enum)):
        return ()
    return tuple(str(member.value) for member in obj)


def _fields_for(obj: type[Any]) -> tuple[IRFieldInfo, ...]:
    kind = _kind_for(obj)
    if kind in {IRTypeKind.PYDANTIC_MODEL, IRTypeKind.ROOT_MODEL}:
        model_fields = getattr(obj, "model_fields", {})
        return tuple(
            IRFieldInfo(
                name=name,
                annotation=_format_annotation(field.annotation),
                required=bool(field.is_required()),
                default=_default_repr(getattr(field, "default", None)),
                references=tuple(sorted(_collect_ir_refs(field.annotation))),
            )
            for name, field in sorted(model_fields.items())
        )
    if kind is IRTypeKind.DATACLASS:
        return tuple(
            IRFieldInfo(
                name=field.name,
                annotation=_format_annotation(field.type),
                required=field.default is dataclasses.MISSING
                and field.default_factory is dataclasses.MISSING,
                default=_dataclass_default_repr(field),
                references=tuple(sorted(_collect_ir_refs(field.type))),
            )
            for field in dataclasses.fields(obj)
        )
    annotations = getattr(obj, "__annotations__", {})
    return tuple(
        IRFieldInfo(
            name=name,
            annotation=_format_annotation(annotation),
            required=True,
            default=None,
            references=tuple(sorted(_collect_ir_refs(annotation))),
        )
        for name, annotation in sorted(annotations.items())
    )


def _default_repr(value: Any) -> str | None:
    if value is None or repr(value) == "PydanticUndefined":
        return None
    return repr(value)


def _dataclass_default_repr(field: dataclasses.Field[Any]) -> str | None:
    if field.default is not dataclasses.MISSING:
        return repr(field.default)
    if field.default_factory is not dataclasses.MISSING:  # type: ignore[comparison-overlap]
        return f"{field.default_factory.__name__}()"
    return None


def _format_annotation(annotation: Any) -> str:
    if annotation is None:
        return "None"
    if isinstance(annotation, str):
        return annotation
    if isinstance(annotation, ForwardRef):
        return annotation.__forward_arg__
    origin = get_origin(annotation)
    if origin is None:
        if annotation is Any:
            return "Any"
        if getattr(annotation, "__module__", "") == "builtins":
            return annotation.__name__
        if hasattr(annotation, "__qualname__"):
            module = getattr(annotation, "__module__", "")
            if module.startswith(_IR_PACKAGE):
                return f"{module}.{annotation.__qualname__}"
            return annotation.__qualname__
        return repr(annotation).replace("typing.", "")

    args = tuple(arg for arg in get_args(annotation) if arg is not Ellipsis)
    if str(origin).endswith("Annotated"):
        return _format_annotation(args[0]) if args else "Any"
    if origin in {list, set, tuple, frozenset}:
        label = origin.__name__
        inner = ", ".join(_format_annotation(arg) for arg in args) if args else "Any"
        return f"{label}[{inner}]"
    if origin is dict:
        inner = ", ".join(_format_annotation(arg) for arg in args) if args else "Any, Any"
        return f"dict[{inner}]"
    union_name = getattr(origin, "__name__", repr(origin))
    if union_name in {"UnionType", "Union"}:
        return " | ".join(_format_annotation(arg) for arg in args)
    inner = ", ".join(_format_annotation(arg) for arg in args)
    return f"{_format_annotation(origin)}[{inner}]"


def _collect_ir_refs(annotation: Any) -> set[str]:
    refs: set[str] = set()
    if annotation is None:
        return refs
    if isinstance(annotation, ForwardRef):
        return refs
    if isinstance(annotation, str):
        return refs

    origin = get_origin(annotation)
    if origin is None:
        module = getattr(annotation, "__module__", "")
        qualname = getattr(annotation, "__qualname__", None)
        if module.startswith(_IR_PACKAGE) and qualname is not None:
            refs.add(f"{module}.{qualname}")
        return refs

    for arg in get_args(annotation):
        if arg is Ellipsis:
            continue
        refs.update(_collect_ir_refs(arg))
    refs.update(_collect_ir_refs(origin))
    return refs


def abi_snapshot_path(entry: IRTypeInfo) -> str | None:
    """Return the repo-relative snapshot path for an ABI-backed entry."""

    if entry.abi_schema_file is None:
        return None
    module_dir = "fabric" if entry.fqn.startswith("polisyos.ir.world.abi.") else "ir"
    return str(PurePosixPath("schemas") / "snapshots" / module_dir / entry.abi_schema_file)


__all__ = [
    "IRExportInfo",
    "IRFieldInfo",
    "IRPublicStatus",
    "IRSchemaCatalog",
    "IRTypeInfo",
    "IRTypeKind",
    "abi_snapshot_path",
    "catalog_anchor",
    "enumerate_ir_exports",
    "get_ir_schema_catalog",
    "get_ir_type",
    "inspect_ir_schema",
    "list_ir_types",
]
