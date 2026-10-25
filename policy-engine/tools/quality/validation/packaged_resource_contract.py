#!/usr/bin/env python3
"""Derive and verify the package resources required by their runtime owners.

The source inventory exercises the catalog resource profile, dependency-registry
reader, DoWhy worker assets, and package resources read by the runtime OpenAPI
example consumer. The isolated installed mode repeats those owner reads from a
built wheel and proves that ``importlib.resources`` resolves the same bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.resources
import json
import os
import re
import sys
import sysconfig
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

_SCHEMA = "polisyos.packaged-resource-contract.v1"


class ResourceContractError(ValueError):
    """A package resource inventory is incomplete or differs from its owner."""


class _ObservedResource:
    """Record the package path and bytes read by an actual runtime owner."""

    def __init__(
        self,
        delegate: Traversable,
        package_name: str | None,
        parts: tuple[str, ...],
        reads: list[tuple[str | None, tuple[str, ...], Path | None, bytes]],
    ) -> None:
        self._delegate = delegate
        self._package_name = package_name
        self._parts = parts
        self._reads = reads

    def joinpath(self, *descendants: str) -> _ObservedResource:
        if any(type(part) is not str or not part for part in descendants):
            raise ResourceContractError("runtime owner used a malformed package resource path")
        return _ObservedResource(
            self._delegate.joinpath(*descendants),
            self._package_name,
            (*self._parts, *descendants),
            self._reads,
        )

    def read_bytes(self) -> bytes:
        data = self._delegate.read_bytes()
        path = self._delegate if isinstance(self._delegate, Path) else None
        self._reads.append((self._package_name, self._parts, path, data))
        return data


def _canonical_relative(value: object, *, label: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value:
        raise ResourceContractError(f"{label} must be a canonical relative POSIX path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ResourceContractError(f"{label} must be a canonical relative POSIX path: {value!r}")
    return path


def _module_path(module: ModuleType, *, source_anchor: Path, label: str) -> Path:
    raw = getattr(module, "__file__", None)
    if type(raw) is not str or not raw:
        raise ResourceContractError(f"{label} has no file-backed module origin")
    path = Path(raw)
    if path.is_symlink():
        raise ResourceContractError(f"{label} module origin is a symlink: {path}")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(source_anchor)
    except (OSError, RuntimeError, ValueError) as error:
        raise ResourceContractError(f"{label} module origin escaped its package anchor") from error
    if not resolved.is_file():
        raise ResourceContractError(f"{label} module origin is not a regular file")
    return resolved


def _load_owner_modules() -> tuple[
    ModuleType, ModuleType, ModuleType, ModuleType, ModuleType, ModuleType
]:
    package = importlib.import_module("polisyos")
    catalog = importlib.import_module("polisyos.data_forge.domains.catalog._resources")
    authority = importlib.import_module("polisyos.foundry.methods.catalog.dependency_authority")
    worker = importlib.import_module("polisyos.foundry.methods.catalog.causal._dowhy_worker")
    runtime_http = importlib.import_module("polisyos.runtime.http")
    openapi = importlib.import_module("polisyos.runtime.http.openapi_contract")
    return package, catalog, authority, worker, runtime_http, openapi


def _target_from_module_file(module_file: Path, anchor: Path, *parts: str) -> str:
    try:
        relative = module_file.resolve(strict=True).relative_to(anchor)
    except (OSError, RuntimeError, ValueError) as error:
        raise ResourceContractError(
            f"owner module is outside its package anchor: {module_file}"
        ) from error
    return PurePosixPath(relative.parent, *parts).as_posix()


def _target_from_resource_path(path: Path, anchor: Path, *, label: str) -> str:
    try:
        relative = path.resolve(strict=False).relative_to(anchor)
    except (OSError, RuntimeError, ValueError) as error:
        raise ResourceContractError(f"{label} escapes its package anchor: {path}") from error
    return PurePosixPath(relative).as_posix()


def _invoke_openapi_example_reader(
    openapi: ModuleType,
) -> list[tuple[str | None, tuple[str, ...], Path | None, bytes]]:
    reader = getattr(openapi, "_confidence_ledger_risk_spend_example", None)
    if not callable(reader):
        raise ResourceContractError("runtime OpenAPI example owner has no executable reader")
    clear_cache = getattr(reader, "cache_clear", None)
    if callable(clear_cache):
        clear_cache()
    original_files = getattr(openapi, "files", None)
    if not callable(original_files):
        raise ResourceContractError(
            "runtime OpenAPI example owner has no importlib.resources reader"
        )

    reads: list[tuple[str | None, tuple[str, ...], Path | None, bytes]] = []

    def observed_files(package: object) -> _ObservedResource:
        package_name = package if type(package) is str else getattr(package, "__name__", None)
        if package_name is not None and type(package_name) is not str:
            package_name = None
        return _ObservedResource(original_files(package), package_name, (), reads)

    openapi.files = observed_files
    try:
        example = reader()
    except Exception as error:
        raise ResourceContractError(
            "runtime OpenAPI example reader could not read and admit its package resource"
        ) from error
    finally:
        openapi.files = original_files

    if type(example) is not dict or not reads:
        raise ResourceContractError("runtime OpenAPI example reader produced no observed resource")
    return reads


def _owner_rows(
    *,
    package: ModuleType,
    catalog: ModuleType,
    authority: ModuleType,
    worker: ModuleType,
    runtime_http: ModuleType,
    openapi: ModuleType,
    package_anchor: Path,
    product_root: Path | None,
) -> dict[str, Any]:
    from typing import get_args

    _module_path(package, source_anchor=package_anchor, label="polisyos")
    catalog_file = _module_path(
        catalog, source_anchor=package_anchor, label="catalog resource owner"
    )
    _module_path(authority, source_anchor=package_anchor, label="dependency registry owner")
    worker_file = _module_path(worker, source_anchor=package_anchor, label="DoWhy worker owner")
    runtime_http_file = _module_path(
        runtime_http, source_anchor=package_anchor, label="runtime HTTP resource package"
    )
    openapi_file = _module_path(
        openapi, source_anchor=package_anchor, label="runtime OpenAPI example owner"
    )
    if runtime_http_file.parent != openapi_file.parent:
        raise ResourceContractError("runtime OpenAPI owner is outside its resource package")

    openapi_rows_by_target: dict[str, dict[str, Any]] = {}
    for package_name, parts, read_path, read_bytes in _invoke_openapi_example_reader(openapi):
        if package_name != runtime_http.__name__ or not parts:
            raise ResourceContractError(
                "runtime OpenAPI reader did not select a resource from its own package"
            )
        resource_path = PurePosixPath(*parts)
        _canonical_relative(resource_path.as_posix(), label="OpenAPI runtime resource")
        wheel = _target_from_module_file(openapi_file, package_anchor, *resource_path.parts)
        source_path = package_anchor.joinpath(*PurePosixPath(wheel).parts)
        if read_path is None or read_path.is_symlink() or source_path.is_symlink():
            raise ResourceContractError("runtime OpenAPI resource is not a regular package file")
        try:
            resolved_read = read_path.resolve(strict=True)
            resolved_source = source_path.resolve(strict=True)
            resolved_source.relative_to(package_anchor)
        except (OSError, RuntimeError, ValueError) as error:
            raise ResourceContractError(
                "runtime OpenAPI resource escaped its selected package anchor"
            ) from error
        if resolved_read != resolved_source or not resolved_source.is_file():
            raise ResourceContractError(
                "runtime OpenAPI reader selected a different package resource"
            )
        try:
            source_bytes = resolved_source.read_bytes()
        except OSError as error:
            raise ResourceContractError("runtime OpenAPI resource is missing") from error
        if source_bytes != read_bytes:
            raise ResourceContractError("runtime OpenAPI reader bytes differ from its owner path")
        previous = openapi_rows_by_target.get(wheel)
        row = {
            "name": resource_path.as_posix(),
            "source_path": resolved_source,
            "wheel": wheel,
        }
        if previous is not None:
            if previous != row:
                raise ResourceContractError("runtime OpenAPI reader selected conflicting resources")
            continue
        openapi_rows_by_target[wheel] = row
    openapi_rows = list(openapi_rows_by_target.values())
    if not openapi_rows:
        raise ResourceContractError("runtime OpenAPI example owner exposed no package resources")

    catalog_rows = []
    for name in get_args(catalog.CatalogDefaultResource):
        if type(name) is not str or Path(name).name != name:
            raise ResourceContractError("catalog owner exposed a non-basename resource")
        source = Path(catalog.catalog_default_resource_path(name))
        wheel = _target_from_module_file(catalog_file, package_anchor, "_resources", name)
        catalog_rows.append({"name": name, "source_path": source, "wheel": wheel})

    registry_source = Path(authority._DIGEST_REGISTRY_PATH)
    registry_target_path = Path(authority._PACKAGED_DIGEST_REGISTRY_PATH)
    registry_wheel = _target_from_resource_path(
        registry_target_path, package_anchor, label="packaged digest registry target"
    )
    registry_row = {
        "name": registry_target_path.name,
        "source_path": registry_source,
        "wheel": registry_wheel,
    }

    required_worker_assets = getattr(worker, "_WORKER_PROFILE_REQUIRED_ASSETS", None)
    if type(required_worker_assets) is not frozenset or not required_worker_assets:
        raise ResourceContractError("DoWhy runtime owner has no finite worker resource set")
    worker_source_dir = Path(worker._worker_directory())
    worker_target_dir = worker_file.parent / "_dowhy_profile"
    worker_rows = []
    for name in sorted(required_worker_assets):
        if type(name) is not str or Path(name).name != name:
            raise ResourceContractError("DoWhy runtime owner exposed a non-basename resource")
        worker_rows.append(
            {
                "name": name,
                "source_path": worker_source_dir / name,
                "wheel": _target_from_resource_path(
                    worker_target_dir / name,
                    package_anchor,
                    label="DoWhy packaged worker target",
                ),
            }
        )

    groups = [catalog_rows, [registry_row], worker_rows, openapi_rows]
    all_rows = [row for group in groups for row in group]
    wheels = [row["wheel"] for row in all_rows]
    if len(wheels) != len(set(wheels)):
        raise ResourceContractError("runtime owners selected duplicate package resource targets")

    def serialize_owner_row(row: dict[str, Any]) -> dict[str, str]:
        source_path = Path(row["source_path"])
        if source_path.is_symlink():
            raise ResourceContractError(f"runtime resource source is a symlink: {source_path}")
        try:
            source_real = source_path.resolve(strict=True)
            if product_root is None:
                source = source_real.relative_to(package_anchor).as_posix()
            else:
                source = source_real.relative_to(product_root).as_posix()
        except (OSError, RuntimeError, ValueError) as error:
            raise ResourceContractError(
                f"runtime resource source is missing or outside the product: {source_path}"
            ) from error
        if not source_real.is_file():
            raise ResourceContractError(f"runtime resource source is not a file: {source_real}")
        _canonical_relative(source, label="resource source")
        _canonical_relative(row["wheel"], label="resource target")
        return {"name": row["name"], "source": source, "wheel": row["wheel"]}

    catalog_inventory = [serialize_owner_row(row) for row in catalog_rows]
    registry_inventory = serialize_owner_row(registry_row)
    worker_inventory = [serialize_owner_row(row) for row in worker_rows]
    openapi_inventory = [serialize_owner_row(row) for row in openapi_rows]
    owners = {
        "catalog_defaults": catalog_inventory,
        "digest_registry": registry_inventory,
        "worker_profile_assets": worker_inventory,
        "openapi_example_resources": openapi_inventory,
    }
    asset_root = product_root if product_root is not None else package_anchor
    assets = [
        _asset_record(asset_root, row["source"], row["wheel"])
        for row in (
            *catalog_inventory,
            registry_inventory,
            *worker_inventory,
            *openapi_inventory,
        )
    ]
    return {
        "schema": _SCHEMA,
        "owners": owners,
        "assets": sorted(assets, key=lambda row: row["wheel"]),
    }


def _asset_record(product_root: Path, source: str, wheel: str) -> dict[str, Any]:
    source_relative = _canonical_relative(source, label="resource source")
    _canonical_relative(wheel, label="resource target")
    path = product_root.joinpath(*source_relative.parts)
    if path.is_symlink():
        raise ResourceContractError(f"runtime resource source is a symlink: {source}")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ResourceContractError(f"runtime resource source is missing: {source}") from error
    return {
        "source": source,
        "wheel": wheel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def source_resource_inventory(product_root: str | Path) -> dict[str, Any]:
    """Import runtime resource owners from a source checkout and derive its inventory."""
    product = Path(product_root).resolve(strict=True)
    package_anchor = (product / "src").resolve(strict=True)
    if not (product / "pyproject.toml").is_file() or not (package_anchor / "polisyos").is_dir():
        raise ResourceContractError("product root is not a src-layout PolicyOS checkout")
    if any(name == "polisyos" or name.startswith("polisyos.") for name in sys.modules):
        raise ResourceContractError(
            "source inventory requires a fresh process without loaded PolicyOS modules"
        )
    sys.path.insert(0, str(package_anchor))
    try:
        package, catalog, authority, worker, runtime_http, openapi = _load_owner_modules()
        for module, label in (
            (package, "polisyos"),
            (catalog, "catalog resource owner"),
            (authority, "dependency registry owner"),
            (worker, "DoWhy worker owner"),
            (runtime_http, "runtime HTTP resource package"),
            (openapi, "runtime OpenAPI example owner"),
        ):
            _module_path(module, source_anchor=package_anchor, label=label)
        return _owner_rows(
            package=package,
            catalog=catalog,
            authority=authority,
            worker=worker,
            runtime_http=runtime_http,
            openapi=openapi,
            package_anchor=package_anchor,
            product_root=product,
        )
    finally:
        sys.path.pop(0)


def validate_manifest_resources(
    owner_inventory: dict[str, Any],
    manifest_assets: object,
    force_include: object,
) -> None:
    """Require manifest and wheel mappings to equal runtime-owned resources."""
    if owner_inventory.get("schema") != _SCHEMA:
        raise ResourceContractError("runtime owner inventory has an unsupported schema")
    owner_assets = owner_inventory.get("assets")
    if type(owner_assets) is not list or not owner_assets:
        raise ResourceContractError("runtime owners supplied no package resources")
    if type(manifest_assets) is not list or type(force_include) is not dict:
        raise ResourceContractError("manifest assets or Hatch wheel mapping are malformed")

    def rows_by_source(rows: list[Any], label: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        targets: set[str] = set()
        for row in rows:
            if type(row) is not dict:
                raise ResourceContractError(f"{label} resource rows must be objects")
            source = _canonical_relative(row.get("source"), label=f"{label} source").as_posix()
            wheel = _canonical_relative(row.get("wheel"), label=f"{label} target").as_posix()
            if source in result or wheel in targets:
                raise ResourceContractError(f"{label} resource rows contain duplicate paths")
            count, digest = row.get("bytes"), row.get("sha256")
            if (
                type(count) is not int
                or count < 0
                or type(digest) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                raise ResourceContractError(f"{label} byte binding is malformed: {source}")
            result[source] = {"wheel": wheel, "bytes": count, "sha256": digest}
            targets.add(wheel)
        return result

    expected = rows_by_source(owner_assets, "runtime")
    observed = rows_by_source(manifest_assets, "manifest")
    if observed != expected:
        raise ResourceContractError(
            "manifest resource set or byte bindings differ from runtime owners"
        )
    expected_force = {source: row["wheel"] for source, row in expected.items()}
    if force_include != expected_force:
        raise ResourceContractError("Hatch wheel mapping differs from runtime-owned resource set")


def verify_source_resource_bytes(product_root: str | Path, assets: list[dict[str, Any]]) -> None:
    """Re-read every source resource and compare it with its owner-derived binding."""
    product = Path(product_root).resolve(strict=True)
    for expected in assets:
        if type(expected) is not dict:
            raise ResourceContractError("runtime source resource rows must be objects")
        source = _canonical_relative(expected.get("source"), label="resource source")
        expected_bytes = expected.get("bytes")
        expected_sha256 = expected.get("sha256")
        if (
            type(expected_bytes) is not int
            or expected_bytes < 0
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        ):
            raise ResourceContractError(
                f"runtime source resource byte binding is malformed: {source}"
            )
        path = product.joinpath(*source.parts)
        if path.is_symlink():
            raise ResourceContractError(f"runtime resource source is a symlink: {source}")
        try:
            data = path.read_bytes()
        except OSError as error:
            raise ResourceContractError(f"runtime resource source is missing: {source}") from error
        if len(data) != expected_bytes or hashlib.sha256(data).hexdigest() != expected_sha256:
            raise ResourceContractError(f"runtime resource source bytes changed: {source}")


def verify_importlib_resource_bytes(
    package_resources: Traversable,
    package_name: str,
    assets: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Read every expected target through a real ``importlib.resources`` Traversable."""
    if type(assets) is not list or not assets:
        raise ResourceContractError("installed runtime resource list must be nonempty")
    rows: dict[str, dict[str, Any]] = {}
    for expected in assets:
        if type(expected) is not dict:
            raise ResourceContractError("installed runtime resource rows must be objects")
        target = _canonical_relative(expected.get("wheel"), label="resource target")
        if not target.parts or target.parts[0] != package_name or len(target.parts) < 2:
            raise ResourceContractError(
                f"resource target is outside package {package_name!r}: {target}"
            )
        if target.as_posix() in rows:
            raise ResourceContractError(
                f"installed runtime resource target is duplicated: {target}"
            )
        expected_bytes = expected.get("bytes")
        expected_sha256 = expected.get("sha256")
        if (
            type(expected_bytes) is not int
            or expected_bytes < 0
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        ):
            raise ResourceContractError(
                f"installed runtime resource byte binding is malformed: {target}"
            )
        resource = package_resources.joinpath(*target.parts[1:])
        if not resource.is_file():
            raise ResourceContractError(f"installed package resource is missing: {target}")
        try:
            data = resource.read_bytes()
        except OSError as error:
            raise ResourceContractError(
                f"installed package resource cannot be read: {target}"
            ) from error
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != expected_bytes or digest != expected_sha256:
            raise ResourceContractError(f"installed package resource bytes differ: {target}")
        rows[target.as_posix()] = {"bytes": len(data), "sha256": digest}
    return rows


def installed_resource_inventory(
    expected_inventory: dict[str, Any],
    *,
    purelib: str | Path | None = None,
    forbidden_roots: tuple[str | Path, ...] = (),
) -> dict[str, Any]:
    """Verify the runtime-derived resource set and all bytes via installed package APIs."""
    expected_assets = expected_inventory.get("assets")
    if (
        expected_inventory.get("schema") != _SCHEMA
        or type(expected_assets) is not list
        or not expected_assets
    ):
        raise ResourceContractError("source runtime resource inventory is malformed")
    if not sys.flags.isolated:
        raise ResourceContractError("installed resource inspection requires Python isolated mode")
    if "PYTHONPATH" in os.environ:
        raise ResourceContractError("installed resource inspection refuses PYTHONPATH")
    actual_purelib = Path(sysconfig.get_paths()["purelib"]).resolve(strict=True)
    expected_purelib = actual_purelib if purelib is None else Path(purelib).resolve(strict=True)
    if actual_purelib != expected_purelib:
        raise ResourceContractError(
            "installed interpreter purelib differs from the selected profile"
        )
    forbidden = tuple(Path(root).resolve(strict=True) for root in forbidden_roots)
    for entry in sys.path:
        if not entry:
            continue
        path = Path(entry).resolve(strict=False)
        if any(path == root or path.is_relative_to(root) for root in forbidden):
            raise ResourceContractError(
                f"installed interpreter can import from a source root: {path}"
            )

    package, catalog, authority, worker, runtime_http, openapi = _load_owner_modules()
    package_dir = Path(package.__file__).resolve(strict=True).parent
    if not package_dir.is_relative_to(expected_purelib):
        raise ResourceContractError("PolicyOS package did not load from selected installed purelib")
    for module, label in (
        (package, "polisyos"),
        (catalog, "catalog resource owner"),
        (authority, "dependency registry owner"),
        (worker, "DoWhy worker owner"),
        (runtime_http, "runtime HTTP resource package"),
        (openapi, "runtime OpenAPI example owner"),
    ):
        _module_path(module, source_anchor=expected_purelib, label=label)

    actual_owners = _owner_rows(
        package=package,
        catalog=catalog,
        authority=authority,
        worker=worker,
        runtime_http=runtime_http,
        openapi=openapi,
        package_anchor=expected_purelib,
        product_root=None,
    )
    # Installed owners point to their private package targets; source paths are not
    # reconstructed from declarations or the pyproject resource mapping.
    expected_targets = {row["wheel"] for row in expected_inventory.get("assets", [])}
    owner_targets = {row["wheel"] for row in actual_owners.get("assets", [])}
    if not expected_targets or owner_targets != expected_targets:
        raise ResourceContractError(
            "installed runtime owners differ from the frozen source resource set"
        )

    package_resources = importlib.resources.files("polisyos")
    importlib_rows = verify_importlib_resource_bytes(package_resources, "polisyos", expected_assets)

    canonical_readers: dict[str, str] = {}
    for owner_row in actual_owners["owners"]["catalog_defaults"]:
        path = Path(catalog.catalog_default_resource_path(owner_row["name"])).resolve(strict=True)
        expected = package_resources.joinpath(*PurePosixPath(owner_row["wheel"]).parts[1:])
        if not isinstance(expected, Path) or path != expected.resolve(strict=True):
            raise ResourceContractError(
                f"catalog reader does not select installed target: {owner_row['name']}"
            )
        canonical_readers[f"catalog:{owner_row['name']}"] = str(path)

    registry_path = Path(authority._DIGEST_REGISTRY_PATH).resolve(strict=True)
    packaged_registry_path = Path(authority._PACKAGED_DIGEST_REGISTRY_PATH).resolve(strict=True)
    if registry_path != packaged_registry_path:
        raise ResourceContractError("dependency registry reader selected a non-packaged path")
    registry = authority.load_digest_domain_registry(registry_path)
    if not registry.statement.domains:
        raise ResourceContractError("installed dependency registry consumer returned no domains")
    canonical_readers["dependency-authority:digest-registry"] = str(registry_path)

    runtime_http_root = Path(runtime_http.__file__).resolve(strict=True).parent
    runtime_http_parts = tuple(runtime_http.__name__.split("."))
    for owner_row in actual_owners["owners"]["openapi_example_resources"]:
        target = PurePosixPath(owner_row["wheel"])
        if target.parts[: len(runtime_http_parts)] != runtime_http_parts:
            raise ResourceContractError("OpenAPI resource target is outside its runtime package")
        resource_parts = target.parts[len(runtime_http_parts) :]
        if not resource_parts:
            raise ResourceContractError("OpenAPI resource target does not name a file")
        owner_path = runtime_http_root.joinpath(*resource_parts).resolve(strict=True)
        expected = package_resources.joinpath(*target.parts[1:])
        if not isinstance(expected, Path) or owner_path != expected.resolve(strict=True):
            raise ResourceContractError(
                f"OpenAPI reader does not select installed target: {owner_row['name']}"
            )
        canonical_readers[f"openapi-example:{owner_row['name']}"] = str(owner_path)

    worker_dir = Path(worker._worker_directory()).resolve(strict=True)
    first_worker_target = PurePosixPath(
        actual_owners["owners"]["worker_profile_assets"][0]["wheel"]
    )
    expected_worker_dir = expected_purelib.joinpath(*first_worker_target.parts[:-1])
    if worker_dir != expected_worker_dir:
        raise ResourceContractError("DoWhy worker reader selected a non-packaged profile directory")
    if any(
        not (worker_dir / row["name"]).is_file()
        for row in actual_owners["owners"]["worker_profile_assets"]
    ):
        raise ResourceContractError("DoWhy worker profile is missing a runtime-required resource")
    canonical_readers["dowhy-worker:profile-directory"] = str(worker_dir)

    return {
        "schema": _SCHEMA,
        "purelib": str(expected_purelib),
        "runtime_owner_targets": sorted(owner_targets),
        "importlib_resources": importlib_rows,
        "canonical_readers": canonical_readers,
    }


def _read_inventory(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ResourceContractError(f"resource inventory is unreadable: {path}") from error
    if type(data) is not dict or data.get("schema") != _SCHEMA:
        raise ResourceContractError("resource inventory has an unsupported schema")
    return data


def main(argv: list[str] | None = None) -> int:
    """Run source or installed resource inspection and print one JSON receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    source = subparsers.add_parser(
        "source", help="derive the resource set from source runtime owners"
    )
    source.add_argument("--product-root", required=True)
    installed = subparsers.add_parser(
        "installed", help="read all resources from an installed package"
    )
    installed.add_argument("--expected-inventory", required=True)
    installed.add_argument("--purelib")
    installed.add_argument("--forbidden-root", action="append", default=[])
    arguments = parser.parse_args(argv)
    try:
        if arguments.mode == "source":
            result = source_resource_inventory(arguments.product_root)
        else:
            result = installed_resource_inventory(
                _read_inventory(arguments.expected_inventory),
                purelib=arguments.purelib,
                forbidden_roots=tuple(arguments.forbidden_root),
            )
    except ResourceContractError as error:
        sys.stderr.write(f"resource contract failed: {error}\n")
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
