#!/usr/bin/env python3
"""Recompute Q2 source/selector/resource inputs from an exact committed checkout.

This LOCAL-only admission utility does not build or install a package and does not
execute collected tests. Its `prepare` mode writes candidate manifest rebindings
to a new raw output directory. Its `check` mode additionally requires the source
manifest, supplement, and timeout-driver pins to equal those recomputations.
"""

from __future__ import annotations

import argparse
import ast
import base64
import copy
import csv
import difflib
import email.parser
import gzip
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import time
import tomllib
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any
from xml.parsers import expat

if TYPE_CHECKING:
    from collections.abc import Callable

HANDOFF_REL = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging"
)
AUDIT_HELPER_REL = f"{HANDOFF_REL}/raw/q2-freeze-input-audit-v2-20261011.py"
TRUSTED_GIT = Path("/usr/bin/git")
MANIFEST_REL = f"{HANDOFF_REL}/installed-wave-manifest.json"
RUNNER_REL = f"{HANDOFF_REL}/raw/run.py"
TIMEOUT_REL = f"{HANDOFF_REL}/raw/timeout_driver.py"
SUPPLEMENT_REL = f"{HANDOFF_REL}/raw/supplemental_run.py"
SUPPLEMENT_MANIFEST_REL = f"{HANDOFF_REL}/raw/supplemental-manifest.json"
SITE_CUSTOMIZE_REL = (
    "policy-engine/docs/research/e02-cloud-test-plan/"
    "implementation-handoffs/LOCAL/linux-profile/raw/sitecustomize.py"
)
REVIEWED_PROFILE_NAMES = (
    "source-wheel",
    "rebuilt-sdist-wheel",
    "rebuilt-gcp-archive-wheel",
)
COLLECTION_PLUGIN_NAME = "q2_source_freeze_capture"
COLLECTION_PLUGIN_SOURCE = """
from __future__ import annotations

import base64
import csv
import email.parser
import importlib.machinery
import hashlib
import io
import json
import math
import marshal
import os
import re
import site
import stat
import sys
import sysconfig
import types
from pathlib import Path, PurePosixPath

import pytest

_STARTUP_MODULES = sys.modules.copy()


def _intrinsic_origin_evidence(name, module, module_namespace, module_file, spec, spec_origin):
    if type(spec) is importlib.machinery.ModuleSpec and spec.loader is not None:
        loader = spec.loader
        loader_namespace = vars(loader) if type(loader) is type else vars(type(loader))
        loader_module = loader_namespace.get("__module__")
        loader_qualname = loader_namespace.get("__qualname__")
        spec_loader = (
            f"{loader_module}.{loader_qualname}"
            if type(loader_module) is str and type(loader_qualname) is str
            else None
        )
    else:
        spec_loader = None
    return {
        "module_name": module_namespace.get("__name__")
        if type(module_namespace.get("__name__")) is str
        else None,
        "exact_module_type": type(module) is type(sys),
        "file_is_none": module_file is None,
        "spec_is_standard": type(spec) is importlib.machinery.ModuleSpec,
        "spec_name": spec.name if type(spec) is importlib.machinery.ModuleSpec else None,
        "spec_origin": spec_origin if type(spec_origin) is str else None,
        "spec_loader": spec_loader,
        "startup_present": name in _STARTUP_MODULES,
        "startup_identity": _STARTUP_MODULES.get(name) is module,
    }


def _record_claim_path(root, value, active_site_roots):
    if not isinstance(value, str) or not value or "\\\\" in value or "\\x00" in value:
        return None, False
    if PurePosixPath(value).is_absolute():
        return None, False
    if not isinstance(root, Path) or not root.is_absolute():
        return None, False
    roots = tuple(Path(site_root) for site_root in active_site_roots)
    if not roots or not any(root.is_relative_to(site_root) for site_root in roots):
        return None, False
    try:
        candidate = root / value
        physical = candidate.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None, False
    if not physical.is_absolute():
        return None, False
    within_site_profile = any(physical.is_relative_to(site_root) for site_root in roots)
    parts = value.split("/")
    safe = (
        within_site_profile
        and PurePosixPath(value).as_posix() == value
        and all(part not in {"", ".", ".."} for part in parts)
        and physical == candidate
    )
    return physical, safe


def _canonical_dist_info_names(name, version):
    if (
        not isinstance(name, str)
        or not name
        or name != name.strip()
        or "/" in name
        or "\\\\" in name
        or not isinstance(version, str)
        or not version
        or version != version.strip()
        or "/" in version
        or "\\\\" in version
    ):
        return set()
    name_forms = {
        name.lower(),
        name.lower().replace("-", "_"),
        re.sub(r"[-_.]+", "_", name).lower(),
    }
    version_forms = {version, re.sub(r"[-_.]+", "_", version)}
    return {
        f"{name_form}-{version_form}.dist-info"
        for name_form in name_forms
        for version_form in version_forms
    }


def _metadata_identity(data):
    try:
        message = email.parser.BytesParser().parsebytes(data)
        names = message.get_all("Name", [])
        versions = message.get_all("Version", [])
    except (TypeError, ValueError):
        return None, None
    if len(names) != 1 or len(versions) != 1:
        return None, None
    name, version = names[0], versions[0]
    if not isinstance(name, str) or not isinstance(version, str):
        return None, None
    if (
        not name.strip()
        or not version.strip()
        or name != name.strip()
        or version != version.strip()
    ):
        return None, None
    return name, version


def _read_path(path):
    try:
        data = path.read_bytes()
        observed = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError:
        return None, False
    direct = (
        stat.S_ISREG(observed.st_mode)
        and not stat.S_ISLNK(observed.st_mode)
        and resolved == path
    )
    return data, direct


def _record_claims(data, root, active_site_roots):
    claims = {}
    well_formed = True
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""))
        for row in reader:
            if len(row) != 3:
                well_formed = False
                continue
            path, safe = _record_claim_path(root, row[0], active_site_roots)
            if path is None:
                well_formed = False
                continue
            algorithm, separator, value = row[1].partition("=")
            if not separator:
                algorithm, value = "", ""
            claims.setdefault(str(path), []).append(
                {
                    "hash_algorithm": algorithm,
                    "hash_value": value,
                    "size": row[2],
                    "safe_path": safe,
                }
            )
    except (UnicodeDecodeError, csv.Error):
        well_formed = False
    return claims, well_formed



class _CaptureMetadata:
    def __init__(self, active_site_roots):
        self.active_site_roots = tuple(
            sorted(
                {
                    Path(value).resolve(strict=True)
                    for value in active_site_roots
                    if isinstance(value, str) and Path(value).is_dir()
                }
            )
        )
        self._record_distributions = None

    def _search_roots(self):
        roots = set()
        for value in sys.path:
            candidate = Path(os.path.abspath(value or os.getcwd()))
            try:
                resolved = candidate.resolve(strict=True)
            except OSError:
                continue
            if not resolved.is_dir():
                continue
            if any(resolved.is_relative_to(root) for root in self.active_site_roots):
                roots.add(resolved)
        return tuple(sorted(roots))

    def _snapshot_dist_info(self, root, info_dir):
        info_stat = None
        try:
            info_stat = info_dir.lstat()
            info_resolved = info_dir.resolve(strict=True)
        except OSError:
            pass
        direct_info_dir = (
            info_stat is not None
            and stat.S_ISDIR(info_stat.st_mode)
            and not stat.S_ISLNK(info_stat.st_mode)
            and info_resolved == info_dir
        )
        record_path = info_dir / "RECORD"
        metadata_path = info_dir / "METADATA"
        record_bytes, direct_record = _read_path(record_path)
        metadata_bytes, direct_metadata = _read_path(metadata_path)
        record_sha256 = (
            hashlib.sha256(record_bytes).hexdigest() if record_bytes is not None else None
        )
        metadata_sha256 = (
            hashlib.sha256(metadata_bytes).hexdigest() if metadata_bytes is not None else None
        )
        name, version = _metadata_identity(metadata_bytes or b"")
        claims, record_well_formed = _record_claims(
            record_bytes or b"", root, self.active_site_roots
        )
        identity_valid = bool(
            direct_info_dir
            and direct_record
            and direct_metadata
            and record_bytes is not None
            and metadata_bytes is not None
            and record_well_formed
            and info_dir.name in _canonical_dist_info_names(name, version)
        )
        return {
            "root": root,
            "dist_info_path": info_dir,
            "record_path": record_path,
            "metadata_path": metadata_path,
            "name": name,
            "version": version,
            "record_sha256": record_sha256,
            "metadata_sha256": metadata_sha256,
            "claims": claims,
            "record_well_formed": record_well_formed,
            "identity_valid": identity_valid,
        }

    @staticmethod
    def _fingerprint(snapshot):
        claims = tuple(
            (
                path,
                tuple(
                    (
                        row["hash_algorithm"],
                        row["hash_value"],
                        row["size"],
                        row["safe_path"],
                    )
                    for row in rows
                ),
            )
            for path, rows in sorted(snapshot["claims"].items())
        )
        return (
            str(snapshot["root"]),
            str(snapshot["dist_info_path"]),
            str(snapshot["record_path"]),
            str(snapshot["metadata_path"]),
            snapshot["name"],
            snapshot["version"],
            snapshot["record_sha256"],
            snapshot["metadata_sha256"],
            snapshot["identity_valid"],
            claims,
        )

    def distribution_records(self):
        if self._record_distributions is None:
            snapshots = []
            for root in self._search_roots():
                for info_dir in sorted(root.glob("*.dist-info")):
                    record_path = info_dir / "RECORD"
                    try:
                        record_path.lstat()
                    except FileNotFoundError:
                        continue
                    except OSError as error:
                        raise RuntimeError(
                            "cannot inventory a visible distribution RECORD"
                        ) from error
                    snapshot = self._snapshot_dist_info(root, info_dir)
                    if snapshot["record_sha256"] is None:
                        raise RuntimeError("cannot read a visible distribution RECORD")
                    if not snapshot["record_well_formed"]:
                        raise RuntimeError(
                            "cannot completely enumerate a visible distribution RECORD"
                        )
                    snapshots.append(snapshot)
            unique = {}
            for snapshot in snapshots:
                unique.setdefault(self._fingerprint(snapshot), snapshot)
            self._record_distributions = tuple(
                unique[key] for key in sorted(unique, key=repr)
            )
        return self._record_distributions


def _distribution_result(snapshot):
    if not snapshot["identity_valid"]:
        return None
    return {
        "name": snapshot["name"],
        "version": snapshot["version"],
        "record_path": str(snapshot["record_path"]),
        "distribution_record_sha256": snapshot["record_sha256"],
        "dist_info_path": str(snapshot["dist_info_path"]),
        "metadata_path": str(snapshot["metadata_path"]),
        "metadata_sha256": snapshot["metadata_sha256"],
    }


def _distribution_for(_module_name, origin, metadata):
    try:
        physical_origin = origin.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    if (
        physical_origin != origin
        or not any(
            physical_origin.is_relative_to(root) for root in metadata.active_site_roots
        )
    ):
        return None
    owners = []
    for snapshot in metadata.distribution_records():
        for claim in snapshot["claims"].get(str(physical_origin), ()):
            owners.append((snapshot, claim))
    if len(owners) != 1 or not owners[0][1]["safe_path"]:
        return None
    snapshot, claim = owners[0]
    distribution = _distribution_result(snapshot)
    if distribution is None:
        return None
    distribution["record_hash_algorithm"] = claim["hash_algorithm"]
    distribution["record_hash_value"] = claim["hash_value"]
    return distribution


def _namespace_distributions(_module_name, locations, metadata):
    rows = []
    snapshots = metadata.distribution_records()
    owned_by_snapshot = {}
    for value in locations:
        location = Path(value)
        try:
            physical_location = location.resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            continue
        if (
            physical_location != location
            or not any(
                physical_location.is_relative_to(root)
                for root in metadata.active_site_roots
            )
        ):
            continue
        owners = []
        claims_by_path = {}
        malformed = False
        for snapshot in snapshots:
            try:
                relative = physical_location.relative_to(snapshot["root"])
            except ValueError:
                continue
            if not relative.parts:
                continue
            owned_paths = []
            for claim_path, claim_rows in snapshot["claims"].items():
                target = Path(claim_path)
                if target == physical_location or not target.is_relative_to(physical_location):
                    continue
                owned_paths.append(claim_path)
                if len(claim_rows) != 1 or any(
                    not claim["safe_path"] for claim in claim_rows
                ):
                    malformed = True
                claims_by_path.setdefault(claim_path, []).append(snapshot)
            if not owned_paths:
                continue
            if not snapshot["identity_valid"]:
                malformed = True
            owners.append((snapshot, owned_paths))
        if any(len(path_owners) != 1 for path_owners in claims_by_path.values()):
            malformed = True
        if malformed:
            continue
        for snapshot, _owned_paths in owners:
            key = _CaptureMetadata._fingerprint(snapshot)
            owned_by_snapshot.setdefault(key, {"snapshot": snapshot, "locations": []})[
                "locations"
            ].append(value)
    for key in sorted(owned_by_snapshot):
        item = owned_by_snapshot[key]
        distribution = _distribution_result(item["snapshot"])
        if distribution is None:
            continue
        distribution["search_locations"] = sorted(set(item["locations"]))
        rows.append(distribution)
    return rows


def _file_record(label, path):
    data = path.read_bytes()
    return {"label": label, "origin": str(path), "sha256": hashlib.sha256(data).hexdigest()}


def _runtime_data_value(value, active=None):
    value_type = type(value)
    if value is None:
        return ["none"]
    if value_type is bool:
        return ["bool", value]
    if value_type is int:
        return ["int", str(value)]
    if value_type is float:
        if not math.isfinite(value):
            raise TypeError("non-finite float")
        return ["float", value.hex()]
    if value_type is str:
        return ["str", value]
    if value_type is bytes:
        return ["bytes", base64.b64encode(value).decode("ascii")]
    if value_type in (list, tuple, dict):
        active = set() if active is None else active
        identity = id(value)
        if identity in active:
            raise TypeError("cyclic runtime data")
        active.add(identity)
        try:
            if value_type is list:
                return ["list", [_runtime_data_value(item, active) for item in value]]
            if value_type is tuple:
                return ["tuple", [_runtime_data_value(item, active) for item in value]]
            rows = [
                [_runtime_data_value(key, active), _runtime_data_value(item, active)]
                for key, item in value.items()
            ]
            rows.sort(
                key=lambda row: json.dumps(
                    row[0], ensure_ascii=True, sort_keys=True, separators=(",", ":")
                )
            )
            return ["dict", rows]
        finally:
            active.remove(identity)
    raise TypeError("unsupported runtime data value")



def _is_module_instance(value):
    # Use the actual type MRO, never an instance's spoofable __class__.
    actual_type = type(value)
    try:
        actual_mro = type.__getattribute__(actual_type, "__mro__")
    except (AttributeError, TypeError):
        return False
    return type(actual_mro) is tuple and any(
        class_type is types.ModuleType for class_type in actual_mro
    )


def _runtime_type_label(value):
    actual_type = type(value)
    try:
        module_name = type.__getattribute__(actual_type, "__module__")
        qualname = type.__getattribute__(actual_type, "__qualname__")
    except (AttributeError, TypeError):
        return "<unidentified-runtime-type>"
    if type(module_name) is not str or type(qualname) is not str:
        return "<unidentified-runtime-type>"
    return f"{module_name}.{qualname}"


def _module_namespace(module):
    if not _is_module_instance(module):
        raise TypeError("value is not a ModuleType instance")
    return types.ModuleType.__getattribute__(module, "__dict__")


def _type_identity(class_type):
    if type(class_type) is not type:
        raise TypeError("module subclass uses an unsupported metaclass")
    module_name = type.__getattribute__(class_type, "__module__")
    qualname = type.__getattribute__(class_type, "__qualname__")
    name = type.__getattribute__(class_type, "__name__")
    if any(type(value) is not str or not value for value in (module_name, qualname, name)):
        raise TypeError("module subclass contains an invalid class identity")
    return {"module": module_name, "qualname": qualname, "name": name}


def _plugin_module_identity(plugin):
    # Bind module/class/instance plugin objects to one actual loaded module.
    if _is_module_instance(plugin):
        module_name = _module_namespace(plugin).get("__name__")
        if (
            type(module_name) is not str
            or not module_name
            or sys.modules.get(module_name) is not plugin
        ):
            raise RuntimeError("pytest module plugin is not bound under its claimed module name")
        return module_name

    plugin_type = plugin if isinstance(plugin, type) else type(plugin)
    try:
        module_name = type.__getattribute__(plugin_type, "__module__")
        qualname = type.__getattribute__(plugin_type, "__qualname__")
    except (AttributeError, TypeError) as error:
        raise RuntimeError("pytest plugin type has no readable module identity") from error
    if (
        type(module_name) is not str
        or not module_name
        or type(qualname) is not str
        or not qualname
    ):
        raise RuntimeError("pytest plugin type has a malformed module identity")
    module = sys.modules.get(module_name)
    if not _is_module_instance(module):
        raise RuntimeError("pytest plugin type module is absent from sys.modules")
    resolved = _module_namespace(module)
    for part in qualname.split("."):
        if not part or part == "<locals>":
            raise RuntimeError("pytest plugin type has no stable module namespace path")
        if type(resolved) is dict:
            resolved = resolved.get(part)
        elif isinstance(resolved, type):
            resolved = type.__getattribute__(resolved, "__dict__").get(part)
        else:
            raise RuntimeError("pytest plugin type namespace path is not resolvable")
    if resolved is not plugin_type:
        raise RuntimeError("pytest plugin type is not bound by its claimed module")
    return module_name


def _module_class_provenance(module):
    # Capture actual type ancestry and source-associated class shape.
    actual_type = type(module)
    try:
        actual_mro = type.__getattribute__(actual_type, "__mro__")
    except (AttributeError, TypeError) as error:
        raise TypeError("module subclass has no readable runtime MRO") from error
    if (
        type(actual_mro) is not tuple
        or not any(class_type is types.ModuleType for class_type in actual_mro)
        or not any(class_type is object for class_type in actual_mro)
    ):
        raise TypeError("runtime type is outside the ModuleType ancestry")
    if actual_type is types.ModuleType:
        return None
    if type(actual_type) is not type:
        raise TypeError("module subclass uses an unsupported metaclass")

    class_rows = []
    for class_type in actual_mro:
        if class_type is types.ModuleType or class_type is object:
            continue
        identity = _type_identity(class_type)
        namespace = type.__getattribute__(class_type, "__dict__")
        attributes = []
        for attribute, value in sorted(namespace.items()):
            if type(attribute) is not str:
                raise TypeError("module subclass has a non-string class attribute")
            if type(value) is types.FunctionType:
                code = value.__code__
                if type(code) is not types.CodeType:
                    raise TypeError("module subclass method has an unsupported code object")
                filename = code.co_filename
                if type(filename) is not str or not filename:
                    raise TypeError("module subclass method has no source filename")
                attributes.append(
                    {
                        "name": attribute,
                        "kind": "function",
                        "filename": filename,
                        "firstlineno": code.co_firstlineno,
                        "qualname": code.co_qualname,
                        "code_sha256": hashlib.sha256(marshal.dumps(code)).hexdigest(),
                    }
                )
            else:
                attributes.append(
                    {
                        "name": attribute,
                        "kind": "data",
                        "value": _runtime_data_value(value),
                    }
                )
        bases = [
            _type_identity(base)
            for base in type.__getattribute__(class_type, "__bases__")
        ]
        class_rows.append(
            {
                **identity,
                "bases": bases,
                "attributes": attributes,
            }
        )
    if not class_rows:
        raise TypeError("module subclass has no source-associated class record")
    return {
        "exact_module_type": False,
        "mro": [_type_identity(class_type) for class_type in actual_mro],
        "classes": class_rows,
    }

def _module_data_digest(module):
    if type(module) is not type(sys):
        return {"supported": False, "bytes": None, "sha256": None}
    try:
        canonical = _runtime_data_value(vars(module))
        data = json.dumps(
            canonical,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (RecursionError, TypeError, ValueError):
        return {"supported": False, "bytes": None, "sha256": None}
    return {
        "supported": True,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _module_rows(metadata):
    module_items = tuple(sys.modules.copy().items())
    if any(type(name) is not str for name, _value in module_items):
        raise RuntimeError("sys.modules contains a non-string key")
    module_items = tuple(sorted(module_items))
    rows = []
    parent_bindings = {}
    for parent_name, parent_module in module_items:
        if not _is_module_instance(parent_module):
            continue
        for attribute, value in _module_namespace(parent_module).items():
            if type(attribute) is str and _is_module_instance(value):
                parent_bindings.setdefault(id(value), []).append(
                    {"parent": parent_name, "attribute": attribute}
                )
    for name, module in module_items:
        if not _is_module_instance(module):
            raise RuntimeError(
                "sys.modules contains a non-module value: "
                f"name={name!r} type={_runtime_type_label(module)}"
            )
        try:
            module_class_provenance = _module_class_provenance(module)
        except (AttributeError, TypeError, ValueError) as error:
            raise RuntimeError(
                "sys.modules module subtype has unsupported class provenance: "
                f"name={name!r} type={_runtime_type_label(module)}"
            ) from error
        module_namespace = _module_namespace(module)
        spec = module_namespace.get("__spec__")
        if spec is not None and type(spec) is not importlib.machinery.ModuleSpec:
            locations = None
            spec_origin = None
        else:
            locations = spec.submodule_search_locations if spec is not None else None
            spec_origin = spec.origin if spec is not None else None
        module_file = module_namespace.get("__file__")
        value = module_file if module_file is not None else spec_origin
        if value is None and locations:
            search_locations = sorted(str(Path(item).absolute()) for item in locations)
            rows.append(
                {
                    "module": name,
                    "origin": None,
                    "sha256": None,
                    "distribution": None,
                    "namespace_distributions": _namespace_distributions(
                        name, search_locations, metadata
                    ),
                    "search_locations": search_locations,
                    "module_class_provenance": module_class_provenance,
                }
            )
            continue
        if value is None or value in {"built-in", "frozen"}:
            row = {
                "module": name,
                "origin": value,
                "sha256": None,
                "distribution": None,
                "search_locations": sorted(str(item) for item in locations or ()),
                "module_class_provenance": module_class_provenance,
            }
            if value is None:
                row["runtime_generated_data"] = {
                    "exact_module_type": type(module) is type(sys),
                    "file_is_none": module_file is None,
                    "path_is_none": module_namespace.get("__path__") is None,
                    "spec_is_none": module_namespace.get("__spec__") is None,
                    "parent_bindings": sorted(
                        parent_bindings.get(id(module), []),
                        key=lambda item: (item["parent"], item["attribute"]),
                    ),
                    **_module_data_digest(module),
                }
            elif value in {"built-in", "frozen"}:
                row["intrinsic_origin_evidence"] = _intrinsic_origin_evidence(
                    name, module, module_namespace, module_file, spec, spec_origin
                )
            rows.append(row)
            continue
        origin = Path(os.path.abspath(str(value)))
        record = _file_record(name, origin)
        rows.append(
            {
                "module": name,
                **record,
                "distribution": _distribution_for(name, origin, metadata),
                "search_locations": sorted(str(item) for item in locations or ()),
                "module_class_provenance": module_class_provenance,
            }
        )
    return rows

def _startup_files():
    rows = {}
    for directory in site.getsitepackages():
        root = Path(directory)
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.pth")):
            rows[str(path)] = _file_record("site_pth", path)
        for name in ("sitecustomize.py", "usercustomize.py"):
            path = root / name
            if path.is_file():
                rows[str(path)] = _file_record(name.removesuffix(".py"), path)
    return [rows[key] for key in sorted(rows)]


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    plugins = []
    for plugin in config.pluginmanager.get_plugins():
        module_name = _plugin_module_identity(plugin)
        plugins.append(
            {
                "name": config.pluginmanager.get_name(plugin),
                "module": module_name,
            }
        )
    pytest_path = Path(os.path.abspath(pytest.__file__))
    sysconfig_paths = sysconfig.get_paths()
    sysconfig_profile_paths = {
        key: str(Path(value).absolute())
        for key, value in sorted(sysconfig_paths.items())
        if isinstance(value, str) and value
    }
    prefix_path = Path(sys.prefix).absolute()
    base_prefix_path = Path(sys.base_prefix).absolute()
    pyvenv_cfg_path = prefix_path / "pyvenv.cfg"
    pyvenv_cfg = None
    if pyvenv_cfg_path.is_file():
        pyvenv_cfg_bytes = pyvenv_cfg_path.read_bytes()
        pyvenv_cfg = {
            "path": str(pyvenv_cfg_path),
            "bytes": len(pyvenv_cfg_bytes),
            "sha256": hashlib.sha256(pyvenv_cfg_bytes).hexdigest(),
        }
    site_roots = sorted(
        {
            str(Path(value).absolute())
            for value in [
                *site.getsitepackages(),
                sysconfig_paths.get("purelib"),
                sysconfig_paths.get("platlib"),
            ]
            if value
        }
    )
    capture_metadata = _CaptureMetadata(site_roots)
    output = {
        "node_ids": [item.nodeid for item in session.items],
        "collection_exitstatus": int(exitstatus),
        "effective_environment": dict(sorted(os.environ.items())),
        "python": {
            "runtime_profile": {
                "executable": str(Path(sys.executable).absolute()),
                "resolved_executable": str(Path(sys.executable).resolve(strict=True)),
                "version": sys.version,
                "implementation": sys.implementation.name,
                "sysconfig_paths": sysconfig_profile_paths,
                "prefix": str(prefix_path),
                "base_prefix": str(base_prefix_path),
                "pyvenv_cfg": pyvenv_cfg,
                "site_roots": site_roots,
                "stdlib_roots": sorted(
                    {
                        str(Path(sysconfig_paths[key]).absolute())
                        for key in ("stdlib", "platstdlib")
                        if key in sysconfig_paths
                    }
                ),
            },
            "sys_path": [str(Path(item or os.getcwd()).absolute()) for item in sys.path],
        },
        "pytest": {
            "version": pytest.__version__,
            "origin": str(pytest_path),
        },
        "plugins": sorted(plugins, key=lambda row: (str(row["name"]), str(row["module"]))),
        "module_origins": _module_rows(capture_metadata),
        "config_origin": str(Path(config.inifile).absolute()) if config.inifile else None,
        "startup_files": _startup_files(),
    }
    destination = Path(os.environ["POLISYOS_Q2_COLLECTION_RESULT"])
    destination.write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\\n",
        encoding="utf-8",
    )
"""
HATCH_REL = "policy-engine/hatch.toml"
APP_PROJECT_REL = "policy-engine/pyproject.toml"
APP_LOCK_REL = "policy-engine/uv.lock"
GITIGNORE_REL = "policy-engine/.gitignore"
DOWHY_PROJECT_REL = "policy-engine/workers/dowhy-014/pyproject.toml"
DOWHY_LOCK_REL = "policy-engine/workers/dowhy-014/uv.lock"
DOWHY_PYTHON_REL = "policy-engine/workers/dowhy-014/.python-version"
DOWHY_README_REL = "policy-engine/workers/dowhy-014/README.md"
GCP_PACKAGE_REL = "policy-engine/ops/cloud/gcp/package_repo.sh"


class AuditError(RuntimeError):
    """Raised when source-derived Q2 inputs do not satisfy the current runner."""


AuditFailure = AuditError


def exact_nonbool_count_matches(value: object, expected: object) -> bool:
    """Match JSON integer values only when both operands are exact non-boolean integers."""
    return type(value) is int and type(expected) is int and value == expected


def json_values_match_exactly(actual: object, expected: object) -> bool:
    """Compare JSON-shaped values without Python's bool/int or int/float aliases."""
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        expected_dict = expected
        return actual.keys() == expected_dict.keys() and all(
            json_values_match_exactly(actual[key], expected_dict[key]) for key in actual
        )
    if isinstance(actual, list):
        expected_list = expected
        return len(actual) == len(expected_list) and all(
            json_values_match_exactly(left, right)
            for left, right in zip(actual, expected_list, strict=True)
        )
    return actual == expected


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_ids_sha256(ids: set[str] | list[str]) -> str:
    return sha256(("\n".join(sorted(ids)) + "\n").encode("utf-8"))


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in value:
        raise AuditFailure(f"unsafe source-relative path: {value!r}")
    return path


def git_run(repo: Path, *args: str, binary: bool = False) -> bytes | str:
    environment = {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }
    if not TRUSTED_GIT.is_absolute() or not TRUSTED_GIT.is_file():
        raise AuditFailure("trusted Git executable is unavailable at /usr/bin/git")
    argv = [
        str(TRUSTED_GIT),
        "-C",
        str(repo),
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.excludesFile={os.devnull}",
        *args,
    ]
    result = subprocess.run(  # noqa: S603 -- fixed absolute Git path, fixed env, validated internal argv.
        argv, capture_output=True, check=False, env=environment
    )
    if result.returncode:
        stderr = result.stderr.decode("utf-8", "replace").strip()
        raise AuditFailure(f"git {' '.join(args)} failed ({result.returncode}): {stderr}")
    return result.stdout if binary else result.stdout.decode("utf-8", "strict").strip()


def commit_blob_record(repo: Path, commit: str, relative: str) -> tuple[str, bytes]:
    """Read one regular commit blob and return its object id and bytes."""
    safe_relative(relative)
    raw = git_run(repo, "ls-tree", "-z", commit, "--", relative, binary=True)
    if not isinstance(raw, bytes):
        raise AuditFailure("Git tree lookup did not return bytes")
    entries = [entry for entry in raw.split(b"\0") if entry]
    if len(entries) != 1:
        raise AuditFailure(f"source object is absent or ambiguous at {commit}:{relative}")
    try:
        header, actual_path = entries[0].split(b"\t", 1)
        fields = header.decode("ascii").split()
    except (UnicodeDecodeError, ValueError) as error:
        raise AuditFailure(f"Git returned a malformed tree entry for {relative}") from error
    if len(fields) != 3:
        raise AuditFailure(f"Git returned an incomplete tree entry for {relative}")
    mode, kind, object_id = fields
    if actual_path.decode("utf-8", "strict") != relative:
        raise AuditFailure(f"Git path mismatch for {relative}")
    if mode not in {"100644", "100755"} or kind != "blob":
        raise AuditFailure(f"source object must be a regular file: {relative} ({mode} {kind})")
    data = git_run(repo, "cat-file", "blob", object_id, binary=True)
    if not isinstance(data, bytes):
        raise AuditFailure(f"Git blob lookup did not return bytes: {relative}")
    return object_id, data


def commit_tree_oid(repo: Path, commit: str, relative: str) -> str:
    """Resolve one exact directory tree from the selected commit."""
    safe_relative(relative)
    raw = git_run(repo, "ls-tree", "-d", "-z", commit, "--", relative, binary=True)
    if not isinstance(raw, bytes):
        raise AuditFailure("Git tree lookup did not return bytes")
    entries = [entry for entry in raw.split(b"\0") if entry]
    if len(entries) != 1:
        raise AuditFailure(f"source tree is absent or ambiguous at {commit}:{relative}")
    header, actual_path = entries[0].split(b"\t", 1)
    mode, kind, object_id = header.decode("ascii").split()
    if actual_path.decode("utf-8", "strict") != relative or mode != "040000" or kind != "tree":
        raise AuditFailure(f"source tree path differs from its commit object: {relative}")
    return object_id


def read_commit_blob(repo: Path, commit: str, relative: str) -> bytes:
    """Read one regular blob directly from a commit object; reject symlinks."""
    return commit_blob_record(repo, commit, relative)[1]


def git_oracle_profile(repo: Path) -> dict[str, Any]:
    """Bind Git object queries to the fixed executable and its effective environment."""
    try:
        resolved = TRUSTED_GIT.resolve(strict=True)
        executable = read_regular_local(resolved)
        identity = resolved.stat()
    except (OSError, AuditFailure) as error:
        raise AuditFailure(f"trusted Git executable could not be read: {error}") from error
    return {
        "requested_path": str(TRUSTED_GIT),
        "resolved_path": str(resolved),
        "sha256": sha256(executable),
        "stat": {
            "device": identity.st_dev,
            "inode": identity.st_ino,
            "mode": identity.st_mode,
            "size": identity.st_size,
            "mtime_ns": identity.st_mtime_ns,
        },
        "version": git_run(repo, "--version"),
        "effective_environment": {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        },
    }


def require_frozen_checkout(repo: Path, source_sha: str, source_tree: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise AuditFailure("source SHA must be a full 40-character commit SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", source_tree):
        raise AuditFailure("source tree must be a full 40-character tree SHA")
    root = Path(str(git_run(repo, "rev-parse", "--show-toplevel"))).resolve(strict=True)
    if root != repo.resolve(strict=True):
        raise AuditFailure(f"repo must be the attached checkout root: {root}")
    if git_run(repo, "symbolic-ref", "-q", "HEAD") == "":
        raise AuditFailure("source checkout is detached")
    if git_run(repo, "rev-parse", "HEAD") != source_sha:
        raise AuditFailure("attached source HEAD differs from supplied freeze SHA")
    if git_run(repo, "rev-parse", f"{source_sha}^{{tree}}") != source_tree:
        raise AuditFailure("supplied source tree differs from the commit object")
    if git_run(repo, "status", "--porcelain=v1", "--untracked-files=no"):
        raise AuditFailure(
            "tracked source is dirty; source-object readback is not an executable freeze"
        )


def read_regular_local(path: Path) -> bytes:
    """Read an ignored local input through a no-follow descriptor walk of every component."""
    if not path.is_absolute():
        raise AuditFailure(f"input path must be absolute: {path}")
    path = Path(os.path.abspath(path))
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise AuditFailure("local input cannot be opened safely on this platform")
    if os.open not in os.supports_dir_fd or os.stat not in os.supports_dir_fd:
        raise AuditFailure("local input cannot be opened safely with directory descriptors")
    parts = path.parts[1:]
    if path.anchor != os.sep or not parts:
        raise AuditFailure(f"local input must name a file below the filesystem root: {path}")

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_fds: list[int] = []
    directory_identities: list[tuple[int, int]] = []
    file_descriptor = -1
    try:
        current_fd = os.open(path.anchor, directory_flags)
        directory_fds.append(current_fd)
        for component in parts[:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            directory_fds.append(next_fd)
            named = os.stat(component, dir_fd=current_fd, follow_symlinks=False)
            opened = os.fstat(next_fd)
            if (
                not stat.S_ISDIR(named.st_mode)
                or not stat.S_ISDIR(opened.st_mode)
                or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                raise AuditFailure(
                    f"local input contains a replaced or symlinked directory: {component}"
                )
            directory_identities.append((opened.st_dev, opened.st_ino))
            current_fd = next_fd

        final_name = parts[-1]
        before = os.stat(final_name, dir_fd=current_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise AuditFailure(f"input must be a regular non-symlink file: {path}")
        file_descriptor = os.open(final_name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=current_fd)
        with os.fdopen(file_descriptor, "rb") as stream:
            file_descriptor = -1
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
                before.st_dev,
                before.st_ino,
            ):
                raise AuditFailure(f"input was replaced before it was opened: {path}")
            data = stream.read()
            after_open = os.fstat(stream.fileno())

        after_name = os.stat(final_name, dir_fd=current_fd, follow_symlinks=False)

        def file_signature(item: os.stat_result) -> tuple[int, int, int, int, int, int]:
            return (
                item.st_dev,
                item.st_ino,
                item.st_size,
                item.st_mtime_ns,
                item.st_ctime_ns,
                item.st_mode,
            )

        if (
            file_signature(before) != file_signature(opened)
            or file_signature(opened) != file_signature(after_open)
            or file_signature(before) != file_signature(after_name)
            or len(data) != after_open.st_size
        ):
            raise AuditFailure(f"input changed while it was read: {path}")

        cursor = Path(path.anchor)
        for component_index, component in enumerate(parts):
            cursor = cursor / component
            observed = cursor.lstat()
            if stat.S_ISLNK(observed.st_mode):
                raise AuditFailure(f"local input contains a symlinked path component: {cursor}")
            if component_index < len(directory_identities):
                expected_identity = directory_identities[component_index]
                if (
                    not stat.S_ISDIR(observed.st_mode)
                    or (observed.st_dev, observed.st_ino) != expected_identity
                ):
                    raise AuditFailure(f"local input path changed while it was read: {cursor}")
            elif file_signature(observed) != file_signature(before):
                raise AuditFailure(f"local input path changed while it was read: {cursor}")
        if path.resolve(strict=True) != path:
            raise AuditFailure(f"local input path does not resolve to its supplied path: {path}")
        return data
    except AuditFailure:
        raise
    except (OSError, NotImplementedError, TypeError) as error:
        raise AuditFailure(
            f"input could not be read without following symlinks: {path}: {error}"
        ) from error
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        for descriptor in reversed(directory_fds):
            os.close(descriptor)


def parse_json(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditFailure(f"invalid UTF-8 JSON in {label}: {error}") from error
    if not isinstance(value, dict):
        raise AuditFailure(f"JSON root must be an object: {label}")
    if not exact_nonbool_count_matches(value.get("schema_version"), 1):
        raise AuditFailure(f"unsupported manifest schema version: {label}")
    return value


def bind_audit_helper(
    repo: Path, source_sha: str, *, authorized_index_sha256: str | None = None
) -> dict[str, Any]:
    """Bind the running producer to its canonical path and a real Git blob."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise AuditFailure("audit-helper source SHA must be a full commit SHA")
    canonical = repo / AUDIT_HELPER_REL
    invoked = Path(os.path.abspath(__file__))
    if invoked != canonical or canonical.is_symlink():
        raise AuditFailure("Q2 audit helper was not invoked from its canonical source path")
    data = read_regular_local(canonical)
    object_id, committed = commit_blob_record(repo, source_sha, AUDIT_HELPER_REL)
    if data == committed:
        return {
            "path": AUDIT_HELPER_REL,
            "bytes": len(data),
            "sha256": sha256(data),
            "provenance": {
                "kind": "tracked_source_commit_blob",
                "source_sha": source_sha,
                "git_blob_oid": object_id,
            },
        }

    index_raw = git_run(repo, "ls-files", "--stage", "-z", "--", AUDIT_HELPER_REL, binary=True)
    if not isinstance(index_raw, bytes):
        raise AuditFailure("Git index lookup did not return bytes for the audit helper")
    entries = [entry for entry in index_raw.split(b"\0") if entry]
    if len(entries) != 1:
        raise AuditFailure("audit helper is not one unambiguous stage-0 index entry")
    try:
        header, actual_path = entries[0].split(b"\t", 1)
        fields = header.decode("ascii").split()
    except (UnicodeDecodeError, ValueError) as error:
        raise AuditFailure("Git returned a malformed index entry for the audit helper") from error
    if len(fields) != 3:
        raise AuditFailure("Git returned an incomplete index entry for the audit helper")
    mode, index_oid, stage = fields
    index_data = git_run(repo, "cat-file", "blob", index_oid, binary=True)
    if not isinstance(index_data, bytes):
        raise AuditFailure("Git index blob lookup did not return bytes for the audit helper")
    if (
        actual_path.decode("utf-8", "strict") != AUDIT_HELPER_REL
        or mode not in {"100644", "100755"}
        or stage != "0"
        or data != index_data
        or authorized_index_sha256 != sha256(data)
    ):
        raise AuditFailure(
            "audit helper is neither the selected commit nor an authorized index blob"
        )
    return {
        "path": AUDIT_HELPER_REL,
        "bytes": len(data),
        "sha256": sha256(data),
        "provenance": {
            "kind": "tracked_index_stage0_candidate",
            "git_blob_oid": index_oid,
            "claim_band": "candidate_until_committed",
            "root_authorized_sha256": authorized_index_sha256,
        },
    }


def junit_testcase_attributes(data: bytes) -> list[dict[str, str]]:
    """Read JUnit case attributes while refusing all DTD and entity declarations."""
    test_cases: list[dict[str, str]] = []
    parser = expat.ParserCreate()

    def start_element(name: str, attributes: dict[str, str]) -> None:
        if name == "testcase":
            test_cases.append(attributes)

    def reject_declaration(*_arguments: object) -> None:
        raise AuditFailure("DOCTYPE or entity declarations are not allowed in baseline JUnit")

    def reject_external_entity(*_arguments: object) -> int:
        raise AuditFailure("external entities are not allowed in baseline JUnit")

    parser.StartElementHandler = start_element
    parser.StartDoctypeDeclHandler = reject_declaration
    parser.EntityDeclHandler = reject_declaration
    parser.ExternalEntityRefHandler = reject_external_entity
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.Parse(data, True)
    return test_cases


def baseline_ids_from_junit(compressed: bytes, manifest: dict[str, Any]) -> set[str]:
    baseline = manifest["original_q2_suite"]
    if sha256(compressed) != baseline["baseline_junit_sha256"]:
        raise AuditFailure("source JUnit bytes differ from the original baseline digest")
    try:
        cases = junit_testcase_attributes(gzip.decompress(compressed))
    except (OSError, expat.ExpatError) as error:
        raise AuditFailure(f"original Q2 JUnit is unreadable: {error}") from error
    if not exact_nonbool_count_matches(baseline.get("baseline_case_count"), len(cases)):
        raise AuditFailure(
            f"original Q2 JUnit count differs: {len(cases)} != {baseline['baseline_case_count']}"
        )
    test_paths = baseline["test_paths"]
    ids: set[str] = set()
    for case in cases:
        classname = case.get("classname", "")
        name = case.get("name", "")
        if not classname or not name:
            raise AuditFailure("original Q2 JUnit case omits classname or name")
        if classname == "test_installed_catalog_defaults":
            test_path = test_paths[-1]
        else:
            parts = classname.split(".")
            test_path = "/".join([*parts[:-1], parts[-1] + ".py"])
        if test_path not in test_paths:
            raise AuditFailure(
                f"original Q2 JUnit case falls outside baseline source paths: {classname}"
            )
        ids.add(f"{test_path}::{name}")
    if len(ids) != len(cases):
        raise AuditFailure("original Q2 JUnit contains duplicate reconstructed node IDs")
    return ids


def normalized_distribution_name(value: str) -> str:
    """Normalize a package name using the lock profile's PEP 503 comparison."""
    return re.sub(r"[-_.]+", "-", value).lower()


def canonical_dist_info_names(name: str, version: str) -> set[str]:
    """Derive accepted canonical metadata-directory spellings from identity fields."""
    if (
        not name
        or name != name.strip()
        or "/" in name
        or "\\" in name
        or not version
        or version != version.strip()
        or "/" in version
        or "\\" in version
    ):
        return set()
    name_forms = {
        name.lower(),
        name.lower().replace("-", "_"),
        re.sub(r"[-_.]+", "_", name).lower(),
    }
    version_forms = {version, re.sub(r"[-_.]+", "_", version)}
    return {
        f"{name_form}-{version_form}.dist-info"
        for name_form in name_forms
        for version_form in version_forms
    }


def record_claim_path(
    value: object, root: Path, site_roots: list[Path]
) -> tuple[Path | None, bool]:
    """Resolve one RECORD row physically and mark only direct in-root paths safe."""
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return None, False
    if PurePosixPath(value).is_absolute():
        return None, False
    if not root.is_absolute():
        return None, False
    if not site_roots or not any(root.is_relative_to(site_root) for site_root in site_roots):
        return None, False
    try:
        candidate = root / value
        physical = candidate.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None, False
    if not physical.is_absolute():
        return None, False
    within_site_profile = any(physical.is_relative_to(site_root) for site_root in site_roots)
    parts = value.split("/")
    safe = (
        within_site_profile
        and PurePosixPath(value).as_posix() == value
        and all(part not in {"", ".", ".."} for part in parts)
        and physical == candidate
    )
    return physical, safe


def safe_record_relative_path(value: object) -> PurePosixPath | None:
    """Return only a canonical non-traversing RECORD-relative path."""
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        return None
    if any(part in {"", ".", ".."} for part in value.split("/")):
        return None
    return path


def physical_record_claim_inventory(
    search_roots: list[Path], site_roots: list[Path]
) -> tuple[
    dict[str, list[tuple[str, str, str, bool]]],
    list[dict[str, Any]],
]:
    """Resolve every visible physical RECORD row and retain each RECORD as recheck evidence."""
    claims: dict[str, list[tuple[str, str, str, bool]]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    inspected_records: set[str] = set()
    for raw_root in sorted(set(search_roots)):
        try:
            root = raw_root.resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as error:
            raise AuditFailure(
                f"effective installed-package search root is unavailable: {raw_root}"
            ) from error
        if root != raw_root or not root.is_dir():
            raise AuditFailure(f"effective installed-package root is not canonical: {raw_root}")
        if not any(root.is_relative_to(site_root) for site_root in site_roots):
            continue
        for info_dir in sorted(root.glob("*.dist-info")):
            record_path = info_dir / "RECORD"
            try:
                record_path.lstat()
            except FileNotFoundError:
                continue
            except OSError as error:
                raise AuditFailure(
                    f"cannot inventory a visible installed RECORD: {record_path}"
                ) from error
            record_key = str(record_path)
            if record_key in inspected_records:
                continue
            inspected_records.add(record_key)
            record_data = read_regular_local(record_path)
            try:
                reader = csv.reader(io.StringIO(record_data.decode("utf-8"), newline=""))
                for row in reader:
                    if len(row) != 3:
                        raise AuditFailure(f"installed RECORD has a malformed row: {record_path}")
                    physical, safe = record_claim_path(row[0], root, site_roots)
                    if physical is None:
                        raise AuditFailure(
                            f"installed RECORD contains an invalid path claim: {record_path}"
                        )
                    claims.setdefault(str(physical), []).append((record_key, row[1], row[2], safe))
            except (UnicodeDecodeError, csv.Error) as error:
                raise AuditFailure(f"installed RECORD is unreadable: {record_path}") from error
            evidence[record_key] = {
                "kind": "locked_python_distribution_record",
                "origin": record_key,
                "bytes": len(record_data),
                "sha256": sha256(record_data),
            }
    return claims, [evidence[key] for key in sorted(evidence)]


def locked_python_versions(repo: Path, source_sha: str) -> dict[str, set[str]]:
    """Read the existing application lock's package-version profile."""
    try:
        lock = tomllib.loads(read_commit_blob(repo, source_sha, APP_LOCK_REL).decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise AuditFailure(
            "application lock cannot define the collection package profile"
        ) from error
    packages = lock.get("package")
    if not isinstance(packages, list):
        raise AuditFailure("application lock omits its package records")
    versions: dict[str, set[str]] = {}
    for package in packages:
        if not isinstance(package, dict):
            raise AuditFailure("application lock contains a malformed package record")
        name = package.get("name")
        version = package.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise AuditFailure("application lock package omits its name or version")
        versions.setdefault(normalized_distribution_name(name), set()).add(version)
    return versions


def locked_distribution_record(
    distribution: dict[str, object],
    lock_versions: dict[str, set[str]],
    site_roots: list[Path],
    context: str,
    record_cache: dict[tuple[str, ...], dict[str, Any]] | None = None,
    record_rows_cache: dict[tuple[str, ...], dict[str, list[tuple[str, str, bool]]]] | None = None,
    *,
    record_owner_inventory: dict[str, list[tuple[str, str, str, bool]]],
    file_origin: Path | None = None,
    file_bytes: bytes | None = None,
    namespace_location: Path | None = None,
) -> dict[str, Any]:
    """Bind a canonical metadata RECORD and its actual file or namespace claim."""
    name = distribution.get("name")
    version = distribution.get("version")
    record_path_value = distribution.get("record_path")
    record_sha = distribution.get("distribution_record_sha256")
    metadata_path_value = distribution.get("metadata_path")
    metadata_sha = distribution.get("metadata_sha256")
    dist_info_path_value = distribution.get("dist_info_path")
    if not isinstance(name, str) or not isinstance(version, str):
        raise AuditFailure(f"installed distribution identity is malformed: {context}")
    if version not in lock_versions.get(normalized_distribution_name(name), set()):
        raise AuditFailure(
            f"installed module distribution is not pinned by uv.lock: {name}=={version}"
        )
    if (
        not isinstance(record_path_value, str)
        or not Path(record_path_value).is_absolute()
        or not isinstance(record_sha, str)
        or not re.fullmatch(r"[0-9a-f]{64}", record_sha)
        or not isinstance(metadata_path_value, str)
        or not Path(metadata_path_value).is_absolute()
        or not isinstance(metadata_sha, str)
        or not re.fullmatch(r"[0-9a-f]{64}", metadata_sha)
        or not isinstance(dist_info_path_value, str)
        or not Path(dist_info_path_value).is_absolute()
    ):
        raise AuditFailure(f"installed distribution metadata identity is malformed: {name}")
    path = Path(os.path.abspath(record_path_value))
    metadata_path = Path(os.path.abspath(metadata_path_value))
    dist_info_path = Path(os.path.abspath(dist_info_path_value))
    expected_dist_info_names = canonical_dist_info_names(name, version)
    if (
        not expected_dist_info_names
        or path.name != "RECORD"
        or path.parent.name not in expected_dist_info_names
        or dist_info_path != path.parent
        or metadata_path != path.parent / "METADATA"
    ):
        raise AuditFailure(
            f"installed distribution RECORD is not its canonical metadata path: {name}"
        )
    root = path.parent.parent
    try:
        canonical_root = root.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise AuditFailure(f"installed distribution search root is unavailable: {name}") from error
    if canonical_root != root or not any(
        root.is_relative_to(site_root) for site_root in site_roots
    ):
        raise AuditFailure(f"installed distribution RECORD is outside active site roots: {name}")
    if (file_origin is None) == (namespace_location is None):
        raise AuditFailure(f"installed distribution claim has no unique origin context: {context}")
    if file_origin is not None and not isinstance(file_bytes, bytes):
        raise AuditFailure(f"installed module claim omits source bytes: {context}")

    cache_key = (
        name,
        version,
        str(path),
        record_sha,
        str(metadata_path),
        metadata_sha,
    )
    record = record_cache.get(cache_key) if record_cache is not None else None
    record_rows = record_rows_cache.get(cache_key) if record_rows_cache is not None else None
    if record is None or record_rows is None:
        record_data = read_regular_local(path)
        if sha256(record_data) != record_sha:
            raise AuditFailure(f"installed distribution RECORD changed during collection: {name}")
        metadata_data = read_regular_local(metadata_path)
        if sha256(metadata_data) != metadata_sha:
            raise AuditFailure(f"installed distribution METADATA changed during collection: {name}")
        try:
            message = email.parser.BytesParser().parsebytes(metadata_data)
            metadata_names = message.get_all("Name", [])
            metadata_versions = message.get_all("Version", [])
        except (TypeError, ValueError) as error:
            raise AuditFailure(f"installed distribution METADATA is unreadable: {name}") from error
        if (
            len(metadata_names) != 1
            or len(metadata_versions) != 1
            or metadata_names[0] != name
            or metadata_versions[0] != version
            or path.parent.name
            not in canonical_dist_info_names(metadata_names[0], metadata_versions[0])
        ):
            raise AuditFailure(
                f"installed distribution identity differs from canonical METADATA: {name}"
            )
        parsed_rows: dict[str, list[tuple[str, str, bool]]] = {}
        try:
            reader = csv.reader(io.StringIO(record_data.decode("utf-8"), newline=""))
            for row in reader:
                if len(row) != 3:
                    raise AuditFailure(f"installed distribution RECORD has a malformed row: {name}")
                physical, safe = record_claim_path(row[0], root, site_roots)
                if physical is None:
                    raise AuditFailure(
                        f"installed distribution RECORD has an invalid path claim: {name}"
                    )
                parsed_rows.setdefault(str(physical), []).append((row[1], row[2], safe))
        except (UnicodeDecodeError, csv.Error) as error:
            raise AuditFailure(f"installed distribution RECORD is unreadable: {name}") from error
        record = {
            "kind": "locked_python_distribution_record",
            "origin": str(path),
            "distribution": name,
            "version": version,
            "bytes": len(record_data),
            "sha256": record_sha,
            "metadata_origin": str(metadata_path),
            "metadata_bytes": len(metadata_data),
            "metadata_sha256": metadata_sha,
        }
        record_rows = parsed_rows
        if record_cache is not None:
            record_cache[cache_key] = record
        if record_rows_cache is not None:
            record_rows_cache[cache_key] = record_rows

    if file_origin is not None:
        try:
            physical_origin = file_origin.resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as error:
            raise AuditFailure(f"installed module origin is unavailable: {context}") from error
        if physical_origin != file_origin or not any(
            physical_origin.is_relative_to(site_root) for site_root in site_roots
        ):
            raise AuditFailure(f"installed module is outside its canonical site root: {context}")
        matching = record_rows.get(str(physical_origin), [])
        all_owners = record_owner_inventory.get(str(physical_origin), [])
        if (
            len(all_owners) != 1
            or all_owners[0][0] != str(path)
            or not all_owners[0][3]
            or len(matching) != 1
            or not matching[0][2]
        ):
            raise AuditFailure(
                f"installed module does not have one safe canonical RECORD row: {context}"
            )
        hash_field, size_field, _safe_claim = matching[0]
        algorithm, separator, value = hash_field.partition("=")
        expected_hash = (
            base64.urlsafe_b64encode(hashlib.sha256(file_bytes).digest())
            .decode("ascii")
            .rstrip("=")
        )
        if (
            not separator
            or algorithm != "sha256"
            or value != expected_hash
            or distribution.get("record_hash_algorithm") != algorithm
            or distribution.get("record_hash_value") != value
            or not size_field.isdigit()
            or int(size_field) != len(file_bytes)
        ):
            raise AuditFailure(
                f"installed module bytes differ from its canonical wheel RECORD: {context}"
            )
    else:
        if namespace_location is None:
            raise AuditFailure(f"namespace claim omits its search location: {context}")
        try:
            physical_location = namespace_location.resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as error:
            raise AuditFailure(f"namespace location is unavailable: {context}") from error
        if physical_location != namespace_location or not any(
            physical_location.is_relative_to(site_root) for site_root in site_roots
        ):
            raise AuditFailure(
                f"namespace location is outside canonical active site roots: {context}"
            )
        try:
            namespace_relative = physical_location.relative_to(root)
        except ValueError as error:
            raise AuditFailure(
                f"namespace location is outside its canonical distribution root: {context}"
            ) from error
        if not namespace_relative.parts:
            raise AuditFailure(
                f"namespace location is not a contained package directory: {context}"
            )
        namespace_claims = [
            (Path(claim_path), claim_rows)
            for claim_path, claim_rows in record_rows.items()
            if Path(claim_path) != physical_location
            and Path(claim_path).is_relative_to(physical_location)
        ]
        if not namespace_claims or any(
            len(claim_rows) != 1 or not claim_rows[0][2]
            for _claim_path, claim_rows in namespace_claims
        ):
            raise AuditFailure(f"namespace location has no exact contained RECORD claim: {context}")
        inventory_namespace_claims = [
            (Path(claim_path), owner_rows)
            for claim_path, owner_rows in record_owner_inventory.items()
            if Path(claim_path) != physical_location
            and Path(claim_path).is_relative_to(physical_location)
        ]
        if (
            not inventory_namespace_claims
            or any(
                len(owner_rows) != 1 or not owner_rows[0][3]
                for _claim_path, owner_rows in inventory_namespace_claims
            )
            or not any(
                any(owner[0] == str(path) for owner in owner_rows)
                for _claim_path, owner_rows in inventory_namespace_claims
            )
        ):
            raise AuditFailure(
                f"namespace location has ambiguous physical RECORD ownership: {context}"
            )
    return record


def directory_identity(path: Path) -> dict[str, int]:
    """Read the identity of a real directory without accepting symlinked paths."""
    try:
        observed = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise AuditFailure(f"collection search directory is unavailable: {path}") from error
    if stat.S_ISLNK(observed.st_mode) or not stat.S_ISDIR(observed.st_mode) or resolved != path:
        raise AuditFailure(f"collection search location is not a direct directory: {path}")
    return {
        "device": observed.st_dev,
        "inode": observed.st_ino,
        "mode": observed.st_mode,
        "mtime_ns": observed.st_mtime_ns,
    }


def literal_pytest_plugins(data: bytes, relative: str) -> set[str]:
    """Read only explicit top-level literal pytest plugin declarations from source."""
    try:
        tree = ast.parse(data.decode("utf-8", "strict"), filename=relative)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise AuditFailure(
            f"tracked Python module cannot be parsed for plugin declarations: {relative}"
        ) from error
    declared: set[str] = set()
    for statement in tree.body:
        value = None
        targets: list[ast.expr] = []
        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
            value = statement.value
        if not any(
            isinstance(target, ast.Name) and target.id == "pytest_plugins" for target in targets
        ):
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            declared.add(value.value)
        elif isinstance(value, (ast.Tuple, ast.List)) and all(
            isinstance(item, ast.Constant) and isinstance(item.value, str) for item in value.elts
        ):
            declared.update(item.value for item in value.elts)
        else:
            raise AuditFailure(f"pytest_plugins must be a literal string sequence in {relative}")
    return declared


def python_executable_record(python: Path) -> dict[str, Any]:
    """Bind the selected launcher path, resolved binary, and adjacent venv config."""
    if not python.is_absolute():
        raise AuditFailure(f"collector Python launcher must be absolute: {python}")
    launcher = Path(os.path.abspath(python))
    try:
        launcher_identity = launcher.lstat()
        resolved = launcher.resolve(strict=True)
        data = read_regular_local(resolved)
        identity = resolved.stat()
    except OSError as error:
        raise AuditFailure(f"collector Python launcher is unavailable: {launcher}") from error
    if not (stat.S_ISREG(launcher_identity.st_mode) or stat.S_ISLNK(launcher_identity.st_mode)):
        raise AuditFailure(f"collector Python launcher is not a file or symlink: {launcher}")
    if not stat.S_ISREG(identity.st_mode) or not os.access(launcher, os.X_OK):
        raise AuditFailure(f"collector Python target is not an executable regular file: {resolved}")

    launcher_record: dict[str, Any] = {
        "path": str(launcher),
        "kind": "symlink" if stat.S_ISLNK(launcher_identity.st_mode) else "regular_file",
        "stat": {
            "device": launcher_identity.st_dev,
            "inode": launcher_identity.st_ino,
            "mode": launcher_identity.st_mode,
            "size": launcher_identity.st_size,
            "mtime_ns": launcher_identity.st_mtime_ns,
        },
    }
    if stat.S_ISLNK(launcher_identity.st_mode):
        launcher_record["symlink_target"] = os.readlink(launcher)

    runtime_profile = None
    for ancestor in launcher.parents:
        config_path = ancestor / "pyvenv.cfg"
        try:
            config_identity = config_path.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise AuditFailure(f"venv configuration is unavailable: {config_path}") from error
        if stat.S_ISLNK(config_identity.st_mode) or not stat.S_ISREG(config_identity.st_mode):
            raise AuditFailure(f"venv configuration is not a regular file: {config_path}")
        config_bytes = read_regular_local(config_path)
        runtime_profile = {
            "kind": "venv",
            "root": str(ancestor),
            "pyvenv_cfg": {
                "path": str(config_path),
                "bytes": len(config_bytes),
                "sha256": sha256(config_bytes),
            },
        }
        break

    return {
        "requested_path": str(launcher),
        "launcher": launcher_record,
        "resolved_path": str(resolved),
        "sha256": sha256(data),
        "stat": {
            "device": identity.st_dev,
            "inode": identity.st_ino,
            "mode": identity.st_mode,
            "size": identity.st_size,
            "mtime_ns": identity.st_mtime_ns,
        },
        "runtime_profile": runtime_profile or {"kind": "global_python"},
    }


def environment_mapping(value: object, context: str) -> dict[str, str]:
    """Require a complete environment object with valid string keys and values."""
    if not isinstance(value, dict):
        raise AuditFailure(f"{context} is not an environment object")
    if any(
        type(key) is not str
        or not key
        or "=" in key
        or "\x00" in key
        or type(item) is not str
        or "\x00" in item
        for key, item in value.items()
    ):
        raise AuditFailure(f"{context} contains a malformed environment key or value")
    return value


PYTHON_RUNTIME_PROFILE_PROBE = """\\
import hashlib
import io
import json
import os
import site
import sys
import sysconfig
from pathlib import Path

startup_environment = dict(sorted(os.environ.items()))
paths = {
    key: str(Path(value).absolute())
    for key, value in sorted(sysconfig.get_paths().items())
    if isinstance(value, str) and value
}
prefix_path = Path(sys.prefix).absolute()
base_prefix_path = Path(sys.base_prefix).absolute()
cfg_path = prefix_path / "pyvenv.cfg"
cfg_bytes = cfg_path.read_bytes() if cfg_path.is_file() else None
pyvenv_cfg = {
    "path": str(cfg_path),
    "bytes": len(cfg_bytes),
    "sha256": hashlib.sha256(cfg_bytes).hexdigest(),
} if cfg_bytes is not None else None
site_roots = sorted(
    {
        str(Path(value).absolute())
        for value in [
            *site.getsitepackages(),
            sysconfig.get_paths().get("purelib"),
            sysconfig.get_paths().get("platlib"),
        ]
        if isinstance(value, str) and value
    }
)
stdlib_roots = sorted(
    {
        paths[key]
        for key in ("stdlib", "platstdlib")
        if key in paths
    }
)
runtime_profile = {
    "executable": str(Path(sys.executable).absolute()),
    "resolved_executable": str(Path(sys.executable).resolve(strict=True)),
    "version": sys.version,
    "implementation": sys.implementation.name,
    "prefix": str(prefix_path),
    "base_prefix": str(base_prefix_path),
    "pyvenv_cfg": pyvenv_cfg,
    "sysconfig_paths": paths,
    "site_roots": site_roots,
    "stdlib_roots": stdlib_roots,
}
profile = {
    "runtime_profile": runtime_profile,
    "bootstrap_sys_path": [
        str(Path(item or os.getcwd()).absolute()) for item in sys.path
    ],
    "startup_environment": startup_environment,
    "isolated": sys.flags.isolated,
    "no_site": sys.flags.no_site,
    "optimize": sys.flags.optimize,
}
print(json.dumps(profile, sort_keys=True, separators=(",", ":")))
"""


PYTHON_GENERATED_MODULE_PROBE = """\
import base64
import hashlib
import importlib
import importlib.machinery
import json
import math
import os
import site
import sys
import sysconfig
from pathlib import Path


def runtime_value(value, active=None):
    value_type = type(value)
    if value is None:
        return ["none"]
    if value_type is bool:
        return ["bool", value]
    if value_type is int:
        return ["int", str(value)]
    if value_type is float:
        if not math.isfinite(value):
            raise TypeError("non-finite float")
        return ["float", value.hex()]
    if value_type is str:
        return ["str", value]
    if value_type is bytes:
        return ["bytes", base64.b64encode(value).decode("ascii")]
    if value_type in (list, tuple, dict):
        active = set() if active is None else active
        identity = id(value)
        if identity in active:
            raise TypeError("cyclic runtime data")
        active.add(identity)
        try:
            if value_type is list:
                return ["list", [runtime_value(item, active) for item in value]]
            if value_type is tuple:
                return ["tuple", [runtime_value(item, active) for item in value]]
            rows = [
                [runtime_value(key, active), runtime_value(item, active)]
                for key, item in value.items()
            ]
            rows.sort(
                key=lambda row: json.dumps(
                    row[0], ensure_ascii=True, sort_keys=True, separators=(",", ":")
                )
            )
            return ["dict", rows]
        finally:
            active.remove(identity)
    raise TypeError("unsupported runtime data value")


def module_digest(module):
    if type(module) is not type(sys):
        return {"supported": False, "bytes": None, "sha256": None}
    try:
        canonical = runtime_value(vars(module))
        data = json.dumps(
            canonical,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (RecursionError, TypeError, ValueError):
        return {"supported": False, "bytes": None, "sha256": None}
    return {
        "supported": True,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def loader_name(spec):
    if type(spec) is not importlib.machinery.ModuleSpec or spec.loader is None:
        return None
    loader = spec.loader
    namespace = vars(loader) if type(loader) is type else vars(type(loader))
    module_name = namespace.get("__module__")
    qualname = namespace.get("__qualname__")
    if type(module_name) is not str or type(qualname) is not str:
        return None
    return f"{module_name}.{qualname}"


def capture_originless_sysmodules(modules_before):
    for module_key, module_value in sys.modules.items():
        if type(module_key) is not str:
            raise RuntimeError("selected runtime sys.modules has a non-string key")
        if modules_before.get(module_key) is module_value:
            continue
        if type(module_value) is not type(sys):
            continue
        namespace = vars(module_value)
        if (
            namespace.get("__file__") is None
            and namespace.get("__path__") is None
            and namespace.get("__spec__") is None
        ):
            generated_module_names.add(module_key)


def intrinsic_module_row(name):
    if name in sys.builtin_module_names:
        inventory_origin = "built-in"
    else:
        try:
            frozen_spec = importlib.machinery.FrozenImporter.find_spec(name, None)
        except (ImportError, ValueError):
            frozen_spec = None
        inventory_origin = (
            "frozen"
            if type(frozen_spec) is importlib.machinery.ModuleSpec
            and frozen_spec.origin == "frozen"
            else None
        )
    if inventory_origin is None:
        return {
            "name": name,
            "origin": None,
            "module_name": None,
            "exact_module_type": False,
            "file_is_none": False,
            "spec_is_standard": False,
            "spec_name": None,
            "spec_origin": None,
            "spec_loader": None,
        }
    try:
        module = importlib.import_module(name)
    except (ImportError, ValueError):
        module = None
    if type(module) is not type(sys):
        return {
            "name": name,
            "origin": inventory_origin,
            "module_name": None,
            "exact_module_type": False,
            "file_is_none": False,
            "spec_is_standard": False,
            "spec_name": None,
            "spec_origin": None,
            "spec_loader": None,
        }
    namespace = vars(module)
    spec = namespace.get("__spec__")
    spec_is_standard = type(spec) is importlib.machinery.ModuleSpec
    spec_origin = spec.origin if spec_is_standard else None
    module_file = namespace.get("__file__")
    actual_origin = module_file if module_file is not None else spec_origin
    return {
        "name": name,
        "origin": actual_origin,
        "module_name": namespace.get("__name__")
        if type(namespace.get("__name__")) is str
        else None,
        "exact_module_type": True,
        "file_is_none": module_file is None,
        "spec_is_standard": spec_is_standard,
        "spec_name": spec.name if spec_is_standard else None,
        "spec_origin": spec_origin if type(spec_origin) is str else None,
        "spec_loader": loader_name(spec) if spec_is_standard else None,
    }


request = json.load(sys.stdin)
if not isinstance(request, dict) or set(request) != {"parents", "intrinsic_claims"}:
    raise RuntimeError("selected-runtime provenance probe request differs from its schema")
paths = sysconfig.get_paths()
sysconfig_paths = {
    key: str(Path(value).absolute())
    for key, value in sorted(paths.items())
    if isinstance(value, str) and value
}
site_roots = sorted(
    {
        str(Path(value).absolute())
        for value in [
            *site.getsitepackages(),
            paths.get("purelib"),
            paths.get("platlib"),
        ]
        if value
    }
)
stdlib_roots = sorted(
    {
        sysconfig_paths[key]
        for key in ("stdlib", "platstdlib")
        if key in sysconfig_paths
    }
)
prefix = Path(sys.prefix).absolute()
base_prefix = Path(sys.base_prefix).absolute()
config_path = prefix / "pyvenv.cfg"
pyvenv_cfg = None
if config_path.is_file():
    config_data = config_path.read_bytes()
    pyvenv_cfg = {
        "path": str(config_path),
        "bytes": len(config_data),
        "sha256": hashlib.sha256(config_data).hexdigest(),
    }
runtime_profile = {
    "executable": str(Path(sys.executable).absolute()),
    "resolved_executable": str(Path(sys.executable).resolve(strict=True)),
    "version": sys.version,
    "implementation": sys.implementation.name,
    "prefix": str(prefix),
    "base_prefix": str(base_prefix),
    "pyvenv_cfg": pyvenv_cfg,
    "sysconfig_paths": sysconfig_paths,
    "site_roots": site_roots,
    "stdlib_roots": stdlib_roots,
}
parents = []
generated_module_names = set()
intrinsic_modules = []
requested_parents = request["parents"]
requested_intrinsic = request["intrinsic_claims"]
if not isinstance(requested_parents, list) or not isinstance(requested_intrinsic, list):
    raise RuntimeError("selected-runtime provenance requests are not lists")
for requested in requested_parents:
    if not isinstance(requested, dict) or set(requested) != {
        "name",
        "kind",
        "origin",
        "sha256",
    }:
        raise RuntimeError("generated-module parent differs from its schema")
    name = requested["name"]
    if (
        not isinstance(name, str)
        or not name
        or any(not part.isidentifier() for part in name.split("."))
        or requested["kind"] not in {"builtin", "frozen", "stdlib"}
    ):
        raise RuntimeError("generated-module parent name or kind is invalid")
    modules_before = sys.modules.copy()
    parent = importlib.import_module(name)
    if type(parent) is not type(sys) or getattr(parent, "__name__", None) != name:
        raise RuntimeError("selected runtime imported a different parent module")
    spec = getattr(parent, "__spec__", None)
    origin = getattr(parent, "__file__", None) or getattr(spec, "origin", None)
    capture_originless_sysmodules(modules_before)
    actual_children = []
    for attribute, child in vars(parent).items():
        if type(child) is not type(parent):
            continue
        child_name = vars(child).get("__name__")
        if not isinstance(child_name, str) or sys.modules.get(child_name) is not child:
            continue
        child_spec = vars(child).get("__spec__")
        if (
            vars(child).get("__file__") is not None
            or vars(child).get("__path__") is not None
            or child_spec is not None
        ):
            continue
        actual_children.append(
            {
                "name": child_name,
                "attribute": attribute,
                "exact_module_type": True,
                "file_is_none": True,
                "path_is_none": True,
                "spec_is_none": True,
                **module_digest(child),
            }
        )
    actual_children.sort(key=lambda row: (row["name"], row["attribute"]))
    if requested["kind"] in {"builtin", "frozen"}:
        if origin != requested["origin"] or requested["sha256"] is not None:
            raise RuntimeError("selected parent intrinsic origin differs from its bound row")
        if requested["kind"] == "builtin" and name not in sys.builtin_module_names:
            raise RuntimeError("selected builtin parent is not in builtin_module_names")
    else:
        if not isinstance(origin, str) or not Path(origin).is_absolute():
            raise RuntimeError("selected standard-library parent has no absolute file origin")
        parent_path = Path(origin)
        if parent_path.resolve(strict=True) != parent_path:
            raise RuntimeError("selected standard-library parent origin is not canonical")
        parent_sha = hashlib.sha256(parent_path.read_bytes()).hexdigest()
        if origin != requested["origin"] or parent_sha != requested["sha256"]:
            raise RuntimeError("selected standard-library parent bytes differ from their row")
    parents.append(
        {
            "name": name,
            "kind": requested["kind"],
            "origin": origin,
            "sha256": requested["sha256"],
            "children": actual_children,
        }
    )
for requested in requested_intrinsic:
    if not isinstance(requested, dict) or set(requested) != {"name", "origin"}:
        raise RuntimeError("selected-runtime intrinsic claim differs from its schema")
    name = requested["name"]
    if (
        not isinstance(name, str)
        or not name
        or any(not part.isidentifier() for part in name.split("."))
        or requested["origin"] not in {"built-in", "frozen"}
    ):
        raise RuntimeError("selected-runtime intrinsic claim name or origin is invalid")
    modules_before = sys.modules.copy()
    intrinsic_modules.append(intrinsic_module_row(name))
    capture_originless_sysmodules(modules_before)
intrinsic_modules.sort(key=lambda row: row["name"])
print(
    json.dumps(
        {
            "runtime_profile": runtime_profile,
            "bootstrap_sys_path": [
                str(Path(item or os.getcwd()).absolute()) for item in sys.path
            ],
            "startup_environment": dict(sorted(os.environ.items())),
            "isolated": sys.flags.isolated,
            "no_site": sys.flags.no_site,
            "optimize": sys.flags.optimize,
            "parents": parents,
            "generated_module_names": sorted(generated_module_names),
            "intrinsic_modules": intrinsic_modules,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
)
"""


def selected_python_runtime_profile(
    python: Path,
    *,
    home: Path,
    timeout_seconds: float,
    probe_environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Derive runtime roles and startup environment through the bound launcher.

    The isolated probe disables site processing so these keys are interpreter-startup
    additions, not sitecustomize or pytest plugin claims.
    """
    if not python.is_absolute() or not home.is_absolute() or not home.is_dir() or home.is_symlink():
        raise AuditFailure("isolated runtime profile requires an absolute launcher and safe HOME")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise AuditFailure("isolated runtime profile timeout must be a positive number")
    if timeout_seconds <= 0:
        raise AuditFailure("isolated runtime profile timeout must be a positive number")
    launcher_record = python_executable_record(python)
    environment = (
        {
            "HOME": str(home),
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        }
        if probe_environment is None
        else environment_mapping(probe_environment, "isolated launcher probe input")
    )
    if environment.get("HOME") != str(home):
        raise AuditFailure("isolated launcher probe input does not preserve its selected HOME")
    try:
        result = subprocess.run(  # noqa: S603 -- absolute launcher and fixed standard-library probe argv.
            [
                str(python),
                "-I",
                "-S",
                "-B",
                "-c",
                PYTHON_RUNTIME_PROFILE_PROBE,
            ],
            cwd=Path("/"),
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AuditFailure("isolated selected-launcher profile probe did not complete") from error
    if result.returncode:
        raise AuditFailure(f"isolated selected-launcher profile probe exited {result.returncode}")
    try:
        profile = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AuditFailure("isolated selected-launcher profile is malformed JSON") from error
    if not isinstance(profile, dict):
        raise AuditFailure("isolated selected-launcher profile root is not an object")
    if set(profile) != {
        "runtime_profile",
        "bootstrap_sys_path",
        "startup_environment",
        "isolated",
        "no_site",
        "optimize",
    }:
        raise AuditFailure("isolated selected-launcher probe envelope differs from its schema")
    startup_environment = environment_mapping(
        profile.get("startup_environment"), "isolated selected-launcher startup environment"
    )
    if any(startup_environment.get(key) != value for key, value in environment.items()):
        raise AuditFailure(
            "selected launcher changed its explicit environment before profile capture"
        )
    runtime_profile = profile.get("runtime_profile")
    required_roles = {
        "executable",
        "resolved_executable",
        "version",
        "implementation",
        "prefix",
        "base_prefix",
        "pyvenv_cfg",
        "sysconfig_paths",
        "site_roots",
        "stdlib_roots",
    }
    if not isinstance(runtime_profile, dict) or not required_roles.issubset(runtime_profile):
        raise AuditFailure("isolated selected-launcher profile omits runtime roles")
    if (
        type(profile.get("isolated")) is not int
        or profile["isolated"] != 1
        or type(profile.get("no_site")) is not int
        or profile["no_site"] != 1
        or type(profile.get("optimize")) is not int
        or profile["optimize"] != 0
    ):
        raise AuditFailure("selected-launcher probe did not run with -I -S -B")
    if runtime_profile.get("resolved_executable") != launcher_record.get("resolved_path"):
        raise AuditFailure("isolated probe executable differs from the bound launcher target")
    runtime = launcher_record.get("runtime_profile")
    if not isinstance(runtime, dict):
        raise AuditFailure("selected launcher has no source-bound runtime classification")
    if runtime.get("kind") == "venv":
        if runtime_profile.get("prefix") != runtime.get("root") or runtime_profile.get(
            "pyvenv_cfg"
        ) != runtime.get("pyvenv_cfg"):
            raise AuditFailure("isolated probe prefix or pyvenv.cfg differs from its launcher")
    elif runtime.get("kind") == "global_python":
        if (
            runtime_profile.get("prefix") != runtime_profile.get("base_prefix")
            or runtime_profile.get("pyvenv_cfg") is not None
        ):
            raise AuditFailure("isolated global Python probe reported a venv profile")
    else:
        raise AuditFailure("selected launcher has an unknown runtime classification")
    collection_profile_directories(runtime_profile, "site_roots")
    collection_profile_directories(runtime_profile, "stdlib_roots")
    bootstrap = profile.get("bootstrap_sys_path")
    if (
        not isinstance(bootstrap, list)
        or not bootstrap
        or any(not isinstance(value, str) or not Path(value).is_absolute() for value in bootstrap)
    ):
        raise AuditFailure("isolated selected-launcher profile has malformed bootstrap paths")
    if python_executable_record(python) != launcher_record:
        raise AuditFailure("selected launcher or venv configuration changed during isolated probe")
    return {
        "launcher_record": launcher_record,
        "runtime_profile": runtime_profile,
        "bootstrap_sys_path": bootstrap,
        "startup_environment": startup_environment,
        "probe_flags": {
            "isolated": profile["isolated"],
            "no_site": profile["no_site"],
            "optimize": profile["optimize"],
        },
    }


def selected_python_generated_module_rows(
    python: Path,
    parents: list[dict[str, Any]],
    intrinsic_claims: list[dict[str, Any]],
    expected_runtime: dict[str, Any],
    python_executable: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """Recompute intrinsic origins and generated-data children in the selected runtime."""
    if not python.is_absolute() or not (parents or intrinsic_claims):
        raise AuditFailure("selected-runtime provenance probe requires a launcher and claims")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise AuditFailure("generated-module probe timeout must be positive")
    if timeout_seconds <= 0:
        raise AuditFailure("generated-module probe timeout must be positive")
    launcher_record = expected_runtime.get("launcher_record")
    startup_environment = environment_mapping(
        expected_runtime.get("startup_environment"), "generated-module probe environment"
    )
    if (
        launcher_record != python_executable
        or python_executable_record(python) != python_executable
    ):
        raise AuditFailure("generated-module probe launcher differs from the frozen runtime")
    ordered_parents = sorted(parents, key=lambda item: item["name"])
    ordered_intrinsic = sorted(intrinsic_claims, key=lambda item: item["name"])
    if len({item["name"] for item in ordered_intrinsic}) != len(ordered_intrinsic):
        raise AuditFailure("selected-runtime intrinsic claims repeat a module name")
    payload = json.dumps(
        {"parents": ordered_parents, "intrinsic_claims": ordered_intrinsic},
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        result = subprocess.run(  # noqa: S603 -- absolute selected Python and fixed isolated probe argv.
            [str(python), "-I", "-S", "-B", "-c", PYTHON_GENERATED_MODULE_PROBE],
            cwd=Path("/"),
            env=startup_environment,
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AuditFailure("selected-runtime generated-module probe did not complete") from error
    if result.returncode:
        raise AuditFailure("selected-runtime generated-module probe exited unsuccessfully")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AuditFailure(
            "selected-runtime generated-module probe returned malformed JSON"
        ) from error
    if not isinstance(report, dict) or set(report) != {
        "runtime_profile",
        "bootstrap_sys_path",
        "startup_environment",
        "isolated",
        "no_site",
        "optimize",
        "parents",
        "generated_module_names",
        "intrinsic_modules",
    }:
        raise AuditFailure("selected-runtime provenance probe schema differs")
    if report.get("runtime_profile") != expected_runtime.get("runtime_profile"):
        raise AuditFailure(
            "generated-module probe runtime profile differs from the selected profile"
        )
    if report.get("bootstrap_sys_path") != expected_runtime.get("bootstrap_sys_path"):
        raise AuditFailure("generated-module probe import path differs from the selected profile")
    if report.get("startup_environment") != startup_environment:
        raise AuditFailure("generated-module probe environment differs from the selected profile")
    if (report.get("isolated"), report.get("no_site"), report.get("optimize")) != (1, 1, 0):
        raise AuditFailure("generated-module probe did not run with -I -S -B")
    if python_executable_record(python) != python_executable:
        raise AuditFailure("selected launcher changed during generated-module reconciliation")
    returned_parents = report.get("parents")
    if not isinstance(returned_parents, list) or len(returned_parents) != len(ordered_parents):
        raise AuditFailure("generated-module probe did not return every requested parent")
    if [row.get("name") for row in returned_parents if isinstance(row, dict)] != [
        parent["name"] for parent in ordered_parents
    ]:
        raise AuditFailure("generated-module probe parent set differs from its request")
    returned_intrinsic = report.get("intrinsic_modules")
    if not isinstance(returned_intrinsic, list) or [
        row.get("name") for row in returned_intrinsic if isinstance(row, dict)
    ] != [claim["name"] for claim in ordered_intrinsic]:
        raise AuditFailure("selected-runtime intrinsic module set differs from its request")
    generated_names = report.get("generated_module_names")
    if (
        not isinstance(generated_names, list)
        or any(not isinstance(name, str) for name in generated_names)
        or generated_names != sorted(set(generated_names))
    ):
        raise AuditFailure("generated-module probe set is malformed or incomplete")
    return report


def reconcile_generated_module_rows(
    modules: dict[str, dict[str, Any]],
    source_records: dict[str, dict[str, Any]],
    runtime_profile: dict[str, Any],
    python: Path,
    python_executable: dict[str, Any],
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    """Reconcile every intrinsic claim and originless data module to runtime truth."""
    intrinsic_claims: list[dict[str, Any]] = []
    intrinsic_evidence_by_name: dict[str, dict[str, Any]] = {}
    intrinsic_fields = {
        "module_name",
        "exact_module_type",
        "file_is_none",
        "spec_is_standard",
        "spec_name",
        "spec_origin",
        "spec_loader",
        "startup_present",
        "startup_identity",
    }
    for module_name, row in modules.items():
        origin = row.get("origin")
        evidence = row.get("intrinsic_origin_evidence")
        if origin in {"built-in", "frozen"}:
            if not isinstance(evidence, dict) or set(evidence) != intrinsic_fields:
                raise AuditFailure("intrinsic module source differs from selected runtime")
            if (
                evidence.get("module_name") != module_name
                or evidence.get("exact_module_type") is not True
                or type(evidence.get("file_is_none")) is not bool
                or type(evidence.get("spec_is_standard")) is not bool
                or type(evidence.get("startup_present")) is not bool
                or type(evidence.get("startup_identity")) is not bool
                or evidence["startup_present"] != evidence["startup_identity"]
            ):
                raise AuditFailure("intrinsic module source differs from selected runtime")
            intrinsic_claims.append({"name": module_name, "origin": origin})
            intrinsic_evidence_by_name[module_name] = evidence
        elif evidence is not None:
            raise AuditFailure("nonintrinsic module carries intrinsic-origin evidence")
    candidates = {
        name: row
        for name, row in modules.items()
        if row.get("origin") is None and row.get("search_locations") == []
    }
    if not candidates and not intrinsic_claims:
        return []
    parent_specs: dict[str, dict[str, Any]] = {}
    actual_bindings: set[tuple[str, str, str]] = set()
    candidate_data: dict[str, dict[str, Any]] = {}
    for module_name, row in candidates.items():
        evidence = row.get("runtime_generated_data")
        if not isinstance(evidence, dict) or set(evidence) != {
            "exact_module_type",
            "file_is_none",
            "path_is_none",
            "spec_is_none",
            "parent_bindings",
            "supported",
            "bytes",
            "sha256",
        }:
            raise AuditFailure(
                f"originless module omits complete runtime-data evidence: {module_name}"
            )
        if any(
            evidence.get(field) is not True
            for field in (
                "exact_module_type",
                "file_is_none",
                "path_is_none",
                "spec_is_none",
                "supported",
            )
        ):
            raise AuditFailure(f"originless module is not a strict data-only module: {module_name}")
        if (
            type(evidence.get("bytes")) is not int
            or evidence["bytes"] < 0
            or not isinstance(evidence.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", evidence["sha256"])
        ):
            raise AuditFailure(f"originless module data digest is malformed: {module_name}")
        bindings = evidence.get("parent_bindings")
        if not isinstance(bindings, list) or not bindings:
            raise AuditFailure(f"originless module has no verified parent binding: {module_name}")
        if any(
            not isinstance(binding, dict)
            or set(binding) != {"parent", "attribute"}
            or not isinstance(binding.get("parent"), str)
            or not isinstance(binding.get("attribute"), str)
            for binding in bindings
        ):
            raise AuditFailure(f"originless module parent binding is malformed: {module_name}")
        ordered_bindings = sorted(
            bindings, key=lambda binding: (binding["parent"], binding["attribute"])
        )
        if bindings != ordered_bindings or len(
            {(binding["parent"], binding["attribute"]) for binding in bindings}
        ) != len(bindings):
            raise AuditFailure(
                f"originless module parent bindings are not unique and ordered: {module_name}"
            )
        candidate_data[module_name] = evidence
        for binding in bindings:
            parent_name = binding["parent"]
            parent_row = modules.get(parent_name)
            parent_record = source_records.get(parent_name)
            if not isinstance(parent_row, dict) or not isinstance(parent_record, dict):
                raise AuditFailure(
                    f"originless module parent has no admitted source row: {module_name}"
                )
            if parent_row.get("module") != parent_name:
                raise AuditFailure(
                    f"originless module parent name differs from its row: {module_name}"
                )
            if parent_record.get("kind") == "python_builtin_or_frozen":
                origin = parent_row.get("origin")
                if origin not in {"built-in", "frozen"}:
                    raise AuditFailure(f"runtime-generated parent origin changed: {parent_name}")
                kind = "builtin" if origin == "built-in" else "frozen"
                parent_sha = None
            elif parent_record.get("kind") == "selected_python_standard_library":
                origin = parent_row.get("origin")
                if not isinstance(origin, str) or not Path(origin).is_absolute():
                    raise AuditFailure(
                        f"runtime-generated stdlib parent has no file origin: {parent_name}"
                    )
                kind = "stdlib"
                parent_sha = parent_record.get("sha256")
            else:
                raise AuditFailure(
                    "runtime-generated module parent is outside builtin/frozen/stdlib custody: "
                    f"{parent_name}"
                )
            candidate_parent = {
                "name": parent_name,
                "kind": kind,
                "origin": origin,
                "sha256": parent_sha,
            }
            existing = parent_specs.setdefault(parent_name, candidate_parent)
            if existing != candidate_parent:
                raise AuditFailure(
                    f"runtime-generated parent has conflicting source rows: {parent_name}"
                )
            actual_bindings.add((parent_name, binding["attribute"], module_name))

    probe = selected_python_generated_module_rows(
        python,
        list(parent_specs.values()),
        intrinsic_claims,
        runtime_profile,
        python_executable,
        timeout_seconds,
    )
    intrinsic_rows = probe["intrinsic_modules"]
    if len(intrinsic_rows) != len(intrinsic_claims):
        raise AuditFailure("intrinsic module source differs from selected runtime")
    intrinsic_rows_by_name = {
        row.get("name"): row for row in intrinsic_rows if isinstance(row, dict)
    }
    if set(intrinsic_rows_by_name) != set(intrinsic_evidence_by_name):
        raise AuditFailure("intrinsic module source differs from selected runtime")
    for claim in intrinsic_claims:
        module_name = claim["name"]
        runtime_row = intrinsic_rows_by_name[module_name]
        evidence = intrinsic_evidence_by_name[module_name]
        if not isinstance(runtime_row, dict) or set(runtime_row) != {
            "name",
            "origin",
            "module_name",
            "exact_module_type",
            "file_is_none",
            "spec_is_standard",
            "spec_name",
            "spec_origin",
            "spec_loader",
        }:
            raise AuditFailure("intrinsic module source differs from selected runtime")
        if runtime_row.get("origin") != claim["origin"] or any(
            runtime_row.get(field) != evidence.get(field)
            for field in (
                "module_name",
                "exact_module_type",
                "file_is_none",
                "spec_is_standard",
                "spec_name",
                "spec_origin",
                "spec_loader",
            )
        ):
            raise AuditFailure("intrinsic module source differs from selected runtime")
        source_record = source_records.get(module_name)
        if (
            not isinstance(source_record, dict)
            or source_record.get("kind") != "python_builtin_or_frozen"
            or source_record.get("origin") != claim["origin"]
        ):
            raise AuditFailure("intrinsic module source differs from selected runtime")
        source_record["intrinsic_origin_predicate"] = "independently_reconciled"
        source_record["python_executable_sha256"] = python_executable["sha256"]
        source_record["live_execution_provenance"] = "not_established"
    if set(probe["generated_module_names"]) != set(candidates):
        raise AuditFailure("complete selected-runtime generated sys.modules set differs")
    expected_bindings: set[tuple[str, str, str]] = set()
    expected_data: dict[tuple[str, str, str], dict[str, Any]] = {}
    for parent in probe["parents"]:
        if not isinstance(parent, dict) or set(parent) != {
            "name",
            "kind",
            "origin",
            "sha256",
            "children",
        }:
            raise AuditFailure("selected-runtime generated-module parent row differs from schema")
        parent_name = parent["name"]
        if parent_name not in parent_specs or any(
            parent.get(field) != parent_specs[parent_name].get(field)
            for field in ("kind", "origin", "sha256")
        ):
            raise AuditFailure(
                "selected-runtime generated-module parent differs from its bound row"
            )
        children = parent.get("children")
        if not isinstance(children, list):
            raise AuditFailure(
                f"selected-runtime parent omits its complete child set: {parent_name}"
            )
        for child in children:
            if not isinstance(child, dict) or set(child) != {
                "name",
                "attribute",
                "exact_module_type",
                "file_is_none",
                "path_is_none",
                "spec_is_none",
                "supported",
                "bytes",
                "sha256",
            }:
                raise AuditFailure(f"selected-runtime generated child is malformed: {parent_name}")
            child_name = child.get("name")
            attribute = child.get("attribute")
            binding = (parent_name, attribute, child_name)
            if (
                not isinstance(child_name, str)
                or not isinstance(attribute, str)
                or child_name not in candidates
                or any(
                    child.get(field) is not True
                    for field in (
                        "exact_module_type",
                        "file_is_none",
                        "path_is_none",
                        "spec_is_none",
                        "supported",
                    )
                )
                or type(child.get("bytes")) is not int
                or child["bytes"] < 0
                or not isinstance(child.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", child["sha256"])
            ):
                raise AuditFailure(
                    f"selected-runtime generated child is not admissible: {parent_name}"
                )
            if binding in expected_data:
                raise AuditFailure(
                    f"selected-runtime repeats a generated child binding: {parent_name}"
                )
            expected_bindings.add(binding)
            expected_data[binding] = child

    if actual_bindings != expected_bindings:
        raise AuditFailure("complete selected-runtime generated-module set differs from collection")
    records_by_module: dict[str, dict[str, Any]] = {}
    for binding in sorted(actual_bindings):
        parent_name, attribute, module_name = binding
        actual = candidate_data[module_name]
        expected = expected_data[binding]
        if (actual["bytes"], actual["sha256"]) != (expected["bytes"], expected["sha256"]):
            raise AuditFailure(
                f"runtime-generated module data differs from selected Python: {module_name}"
            )
        parent = parent_specs[parent_name]
        record = records_by_module.setdefault(
            module_name,
            {
                "kind": "selected_python_generated_data_module",
                "module": module_name,
                "parent_bindings": [],
                "parent_sources": [],
                "python_executable_sha256": python_executable["sha256"],
                "data_bytes": actual["bytes"],
                "data_sha256": actual["sha256"],
                "content_predicate": "independently_reconciled",
                "live_execution_provenance": "not_established",
            },
        )
        record["parent_bindings"].append({"parent": parent_name, "attribute": attribute})
        record["parent_sources"].append(
            {
                "module": parent_name,
                "origin": parent["origin"],
                "sha256": parent["sha256"],
            }
        )
    for record in records_by_module.values():
        record["parent_bindings"].sort(key=lambda item: (item["parent"], item["attribute"]))
        record["parent_sources"].sort(key=lambda item: item["module"])
    return [records_by_module[name] for name in sorted(records_by_module)]


def collection_profile_directories(python_profile: dict[str, Any], field: str) -> list[Path]:
    """Resolve a nonempty runtime directory set from the actual child report."""
    values = python_profile.get(field)
    if not isinstance(values, list) or not values:
        raise AuditFailure(f"pytest runtime profile omits {field}")
    roots = []
    for value in values:
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise AuditFailure(f"pytest runtime profile has an invalid {field} entry")
        try:
            root = Path(value).resolve(strict=True)
        except OSError as error:
            raise AuditFailure(
                f"pytest runtime profile directory is unavailable: {value}"
            ) from error
        if not root.is_dir():
            raise AuditFailure(f"pytest runtime profile entry is not a directory: {value}")
        roots.append(root)
    return list(dict.fromkeys(roots))


def validate_python_runtime_profile(
    expected_runtime: dict[str, Any], observed_profile: dict[str, Any]
) -> None:
    """Reconcile the complete runtime role object to its isolated selected-launcher probe."""
    if not isinstance(expected_runtime, dict) or not isinstance(observed_profile, dict):
        raise AuditFailure("collector Python runtime profile is malformed")
    launcher_record = expected_runtime.get("launcher_record")
    expected_profile = expected_runtime.get("runtime_profile")
    probe_flags = expected_runtime.get("probe_flags")
    if not isinstance(launcher_record, dict) or not isinstance(expected_profile, dict):
        raise AuditFailure("isolated selected-launcher runtime record is malformed")
    if not isinstance(probe_flags, dict):
        raise AuditFailure("isolated selected-launcher probe flags are missing")
    requested_path = launcher_record.get("requested_path")
    if not isinstance(requested_path, str) or not Path(requested_path).is_absolute():
        raise AuditFailure("collector Python launcher record omits its absolute path")
    if python_executable_record(Path(requested_path)) != launcher_record:
        raise AuditFailure("collector Python launcher or runtime config changed before collection")
    if probe_flags != {"isolated": 1, "no_site": 1, "optimize": 0}:
        raise AuditFailure("runtime expectation was not derived with -I -S -B")
    observed_runtime = observed_profile.get("runtime_profile")
    if not isinstance(observed_runtime, dict):
        raise AuditFailure("pytest report omits its complete runtime role object")
    if observed_runtime != expected_profile:
        differing_fields = sorted(
            key
            for key in set(expected_profile) | set(observed_runtime)
            if expected_profile.get(key) != observed_runtime.get(key)
        )
        raise AuditFailure(
            "pytest runtime role object differs from isolated launcher probe: "
            + ", ".join(differing_fields)
        )
    if not isinstance(expected_profile.get("prefix"), str) or not isinstance(
        expected_profile.get("base_prefix"), str
    ):
        raise AuditFailure("isolated runtime role object omits its interpreter prefixes")
    if not isinstance(expected_profile.get("sysconfig_paths"), dict):
        raise AuditFailure("isolated runtime role object omits sysconfig paths")
    collection_profile_directories(expected_profile, "site_roots")
    collection_profile_directories(expected_profile, "stdlib_roots")


def collection_environment(product: Path, output_root: Path, result_path: Path) -> dict[str, str]:
    """Build the source collector's complete environment without inheriting ambient keys."""
    directories = {
        name: output_root / name for name in ("home", "tmp", "cache", "config", "pycache")
    }
    for directory in directories.values():
        directory.mkdir(exist_ok=True)
        if not directory.is_dir() or directory.is_symlink():
            raise AuditFailure(f"collection environment directory is unsafe: {directory}")
    return {
        "HOME": str(directories["home"]),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
        "POLISYOS_Q2_COLLECTION_RESULT": str(result_path),
        "POLISYOS_RUN_INTEGRATION": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": os.pathsep.join((str(output_root), str(product / "src"), str(product))),
        "PYTHONPYCACHEPREFIX": str(directories["pycache"]),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "TMPDIR": str(directories["tmp"]),
        "XDG_CACHE_HOME": str(directories["cache"]),
        "XDG_CONFIG_HOME": str(directories["config"]),
    }


def parse_collected_ids(report: dict[str, Any], allowed_paths: set[str]) -> set[str]:
    """Parse every machine-recorded pytest item and reject, never filter, unexpected paths."""
    values = report.get("node_ids")
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise AuditFailure("pytest collection report omits its complete string node-id list")
    if not values:
        raise AuditFailure("pytest collect-only produced no canonical node IDs")
    result = set(values)
    if len(result) != len(values):
        raise AuditFailure("pytest collection report repeats a node ID")
    for value in values:
        path, separator, selector = value.partition("::")
        if not separator or not selector or path not in allowed_paths:
            raise AuditFailure(f"pytest collection produced an unexpected item: {value!r}")
    return result


def validate_module_class_provenance(
    module_rows: dict[str, dict[str, Any]],
    source_records: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Reconcile each non-exact module type to class source rows and verified module origins."""

    def identity(class_type: type) -> tuple[str, str, str]:
        module_name = type.__getattribute__(class_type, "__module__")
        qualname = type.__getattribute__(class_type, "__qualname__")
        name = type.__getattribute__(class_type, "__name__")
        if any(type(value) is not str or not value for value in (module_name, qualname, name)):
            raise AuditFailure("module subclass class identity is malformed")
        return module_name, qualname, name

    module_type_identity = identity(type(sys))
    object_identity = identity(object)
    subclass_rows: dict[str, dict[str, Any]] = {}
    identity_fields = frozenset({"module", "qualname", "name"})
    class_record_fields = frozenset({"module", "qualname", "name", "bases", "attributes"})

    def identity_row(
        row: object,
        module_name: str,
        *,
        expected_fields: frozenset[str],
    ) -> tuple[str, str, str]:
        if not isinstance(row, dict) or set(row) != expected_fields:
            raise AuditFailure(
                f"module class provenance contains a malformed identity: {module_name}"
            )
        values = (row.get("module"), row.get("qualname"), row.get("name"))
        if any(not isinstance(value, str) or not value for value in values):
            raise AuditFailure(f"module class provenance contains an empty identity: {module_name}")
        return values

    for module_name, module_row in module_rows.items():
        if "module_class_provenance" not in module_row:
            raise AuditFailure(
                f"module inventory omits its complete runtime type classification: {module_name}"
            )
        evidence = module_row["module_class_provenance"]
        if evidence is None:
            continue
        if not isinstance(evidence, dict) or set(evidence) != {
            "exact_module_type",
            "mro",
            "classes",
        }:
            raise AuditFailure(f"module class provenance is malformed: {module_name}")
        if evidence.get("exact_module_type") is not False:
            raise AuditFailure(f"module subclass provenance claims an exact type: {module_name}")
        mro = evidence.get("mro")
        classes = evidence.get("classes")
        if not isinstance(mro, list) or not isinstance(classes, list) or not classes:
            raise AuditFailure(
                f"module subclass provenance omits complete class ancestry: {module_name}"
            )

        mro_identities = [
            identity_row(row, module_name, expected_fields=identity_fields) for row in mro
        ]
        if (
            mro_identities.count(module_type_identity) != 1
            or mro_identities.count(object_identity) != 1
            or mro_identities[0] == module_type_identity
        ):
            raise AuditFailure(
                "module subclass ancestry does not include the selected ModuleType base: "
                f"{module_name}"
            )
        class_identities = [
            identity_row(row, module_name, expected_fields=class_record_fields) for row in classes
        ]
        expected_class_identities = [
            item for item in mro_identities if item not in {module_type_identity, object_identity}
        ]
        if class_identities != expected_class_identities or len(set(class_identities)) != len(
            class_identities
        ):
            raise AuditFailure(
                f"module subclass class records differ from the actual MRO: {module_name}"
            )

        source_modules = []
        for class_row, class_identity in zip(classes, class_identities, strict=True):
            if not isinstance(class_row, dict) or set(class_row) != {
                "module",
                "qualname",
                "name",
                "bases",
                "attributes",
            }:
                raise AuditFailure(f"module subclass class record is malformed: {module_name}")
            defining_module, class_qualname, _class_name = class_identity
            defining_row = module_rows.get(defining_module)
            defining_source = source_records.get(defining_module)
            source_origin = defining_row.get("origin") if isinstance(defining_row, dict) else None
            if (
                not isinstance(defining_row, dict)
                or not isinstance(defining_source, dict)
                or not isinstance(source_origin, str)
                or not Path(source_origin).is_absolute()
                or defining_row.get("sha256") != defining_source.get("sha256")
                or defining_source.get("kind")
                not in {
                    "tracked_source_commit_blob",
                    "locked_python_distribution",
                    "selected_python_standard_library",
                    "helper_generated_collection_plugin",
                }
            ):
                raise AuditFailure(
                    f"module subclass class has no verified defining source module: "
                    f"{defining_module}.{class_qualname}"
                )
            source_modules.append(defining_module)
            bases = class_row.get("bases")
            attributes = class_row.get("attributes")
            if not isinstance(bases, list) or not isinstance(attributes, list):
                raise AuditFailure(
                    f"module subclass class omits its complete bases or attributes: "
                    f"{defining_module}.{class_qualname}"
                )
            base_identities = [
                identity_row(base, module_name, expected_fields=identity_fields) for base in bases
            ]
            if len(set(base_identities)) != len(base_identities) or any(
                base not in mro_identities for base in base_identities
            ):
                raise AuditFailure(
                    f"module subclass base is absent or repeated in the actual MRO: "
                    f"{defining_module}.{class_qualname}"
                )

            attribute_names = []
            function_count = 0
            for attribute in attributes:
                if not isinstance(attribute, dict) or not isinstance(attribute.get("name"), str):
                    raise AuditFailure(
                        f"module subclass attribute inventory is malformed: "
                        f"{defining_module}.{class_qualname}"
                    )
                attribute_names.append(attribute["name"])
                if attribute.get("kind") == "function":
                    if set(attribute) != {
                        "name",
                        "kind",
                        "filename",
                        "firstlineno",
                        "qualname",
                        "code_sha256",
                    }:
                        raise AuditFailure(
                            f"module subclass function record is malformed: "
                            f"{defining_module}.{class_qualname}"
                        )
                    filename = attribute.get("filename")
                    firstlineno = attribute.get("firstlineno")
                    qualname = attribute.get("qualname")
                    code_sha256 = attribute.get("code_sha256")
                    if (
                        filename != source_origin
                        or type(firstlineno) is not int
                        or firstlineno < 1
                        or qualname != f"{class_qualname}.{attribute['name']}"
                        or not isinstance(code_sha256, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", code_sha256)
                    ):
                        raise AuditFailure(
                            f"module subclass method is detached from its verified source: "
                            f"{defining_module}.{class_qualname}.{attribute['name']}"
                        )
                    function_count += 1
                elif attribute.get("kind") == "data":
                    if set(attribute) != {"name", "kind", "value"} or not isinstance(
                        attribute.get("value"), list
                    ):
                        raise AuditFailure(
                            f"module subclass data attribute is malformed: "
                            f"{defining_module}.{class_qualname}"
                        )
                else:
                    raise AuditFailure(
                        f"module subclass attribute kind is unsupported: "
                        f"{defining_module}.{class_qualname}"
                    )
            if (
                attribute_names != sorted(attribute_names)
                or len(set(attribute_names)) != len(attribute_names)
                or function_count == 0
            ):
                raise AuditFailure(
                    f"module subclass class is not fully source-associated: "
                    f"{defining_module}.{class_qualname}"
                )
            encoded_module_name = next(
                (
                    attribute.get("value")
                    for attribute in attributes
                    if attribute.get("name") == "__module__" and attribute.get("kind") == "data"
                ),
                None,
            )
            qualname_namespace_row = next(
                (attribute for attribute in attributes if attribute.get("name") == "__qualname__"),
                None,
            )
            qualname_namespace_matches = qualname_namespace_row is None or (
                qualname_namespace_row.get("kind") == "data"
                and qualname_namespace_row.get("value") == ["str", class_qualname]
            )
            # The producer's identity row comes from type.__getattribute__; attributes is
            # the separate type.__dict__ snapshot. The namespace may omit special metadata.
            # If it contains __qualname__, reconcile it; MRO and method-code checks above
            # already bind the type-level qualname to the source-associated class identity.
            if encoded_module_name != ["str", defining_module] or not qualname_namespace_matches:
                raise AuditFailure(
                    f"module subclass class labels differ from its source row: "
                    f"{defining_module}.{class_qualname}"
                )

        if not isinstance(module_row.get("module"), str) or module_row["module"] != module_name:
            raise AuditFailure(
                f"module subclass name differs from its sys.modules key: {module_name}"
            )
        subclass_rows[module_name] = {
            "module_origin": module_row.get("origin"),
            "module_sha256": module_row.get("sha256"),
            "class_record_sha256": canonical_json_sha256(evidence),
            "class_source_modules": sorted(set(source_modules)),
            "module_type_predicate": "independently_reconciled",
            "live_execution_provenance": "not_established",
        }
    return subclass_rows


def bind_collection_origins(
    repo: Path,
    source_sha: str,
    report: dict[str, Any],
    plugin_path: Path,
    plugin_bytes: bytes,
    lock_versions: dict[str, set[str]],
    expected_runtime_profile: dict[str, Any],
    python: Path,
    python_executable: dict[str, Any],
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    """Bind every loaded module, config, startup file, plugin, and conftest origin."""
    python_profile = report.get("python")
    modules = report.get("module_origins")
    if not isinstance(python_profile, dict) or not isinstance(modules, list):
        raise AuditFailure("pytest collection report omits its runtime or module-origin inventory")
    sys_path = python_profile.get("sys_path")
    if not isinstance(sys_path, list):
        raise AuditFailure("pytest collection report omits its effective import path")
    runtime_roles = expected_runtime_profile.get("runtime_profile")
    if not isinstance(runtime_roles, dict):
        raise AuditFailure("isolated runtime profile omits its role object")
    active_site_roots = collection_profile_directories(runtime_roles, "site_roots")
    stdlib_roots = collection_profile_directories(runtime_roles, "stdlib_roots")
    bootstrap_values = expected_runtime_profile.get("bootstrap_sys_path")
    if not isinstance(bootstrap_values, list) or not bootstrap_values:
        raise AuditFailure("isolated runtime profile omits its bootstrap import path")
    bootstrap_paths = {
        Path(value).resolve(strict=False)
        for value in bootstrap_values
        if isinstance(value, str) and Path(value).is_absolute()
    }
    python_roots = active_site_roots + stdlib_roots
    record_search_roots: set[Path] = set()
    for value in sys_path:
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise AuditFailure("pytest collection report has a non-absolute sys.path entry")
        entry = Path(os.path.abspath(value)).resolve(strict=False)
        if entry.is_relative_to(repo) or entry in bootstrap_paths:
            continue
        if any(entry.is_relative_to(root) for root in python_roots):
            if any(entry.is_relative_to(root) for root in active_site_roots):
                try:
                    search_root = Path(value).resolve(strict=True)
                except OSError:
                    continue
                if search_root.is_dir():
                    record_search_roots.add(search_root)
            continue
        raise AuditFailure(
            f"pytest import path is outside the reconciled source/runtime roots: {entry}"
        )
    module_rows: dict[str, dict[str, Any]] = {}
    for module in modules:
        if not isinstance(module, dict) or not isinstance(module.get("module"), str):
            raise AuditFailure("pytest module-origin inventory contains a malformed row")
        module_name = module["module"]
        if "module_class_provenance" not in module:
            raise AuditFailure(f"module inventory omits runtime type provenance: {module_name}")
        if module_name in module_rows:
            raise AuditFailure(f"pytest module-origin inventory repeats {module_name}")
        module_rows[module_name] = module

    def retain_record(record: dict[str, Any], module_name: str | None = None) -> None:
        key = str(record.get("origin", f"intrinsic:{record.get('module')}"))
        if key in origin_rows:
            if module_name is not None:
                origin_rows[key].setdefault("modules", []).append(module_name)
        else:
            if module_name is not None:
                record["modules"] = [module_name]
            origin_rows[key] = record

    origin_rows: dict[str, dict[str, Any]] = {}
    distribution_record_cache: dict[tuple[str, ...], dict[str, Any]] = {}
    distribution_record_rows_cache: dict[
        tuple[str, ...], dict[str, list[tuple[str, str, bool]]]
    ] = {}
    declared_plugin_modules: set[str] = set()
    loaded_conftest_modules: set[str] = set()
    source_records: dict[str, dict[str, Any]] = {}
    record_owner_inventory, record_inventory_evidence = physical_record_claim_inventory(
        sorted(record_search_roots), active_site_roots
    )
    for module in modules:
        module_name = module["module"]
        origin = module.get("origin")
        if isinstance(origin, str) and origin in {"built-in", "frozen"}:
            record = {
                "kind": "python_builtin_or_frozen",
                "module": module_name,
                "origin": origin,
                "search_locations": module.get("search_locations", []),
                "intrinsic_origin_predicate": "independently_reconciled",
                "python_executable_sha256": python_executable["sha256"],
                "live_execution_provenance": "not_established",
            }
            retain_record(record, module_name)
            source_records[module_name] = record
            continue
        if origin is None:
            locations = module.get("search_locations")
            if not isinstance(locations, list):
                raise AuditFailure(
                    f"originless module search locations are malformed: {module_name}"
                )
            if not locations:
                continue
            namespace_distributions = module.get("namespace_distributions")
            if not isinstance(namespace_distributions, list):
                raise AuditFailure(
                    f"namespace origin omits package-profile bindings: {module_name}"
                )
            for location_value in locations:
                if not isinstance(location_value, str) or not Path(location_value).is_absolute():
                    raise AuditFailure(f"namespace search location is malformed: {module_name}")
                location = Path(os.path.abspath(location_value))
                identity = directory_identity(location)
                base_record: dict[str, Any] = {
                    "kind": "python_namespace_search_directory",
                    "origin": str(location),
                    "path_kind": "directory",
                    "directory_identity": identity,
                }
                in_site_profile = any(location.is_relative_to(root) for root in active_site_roots)
                in_standard_library = any(location.is_relative_to(root) for root in stdlib_roots)
                if location.is_relative_to(repo) and not (in_site_profile or in_standard_library):
                    relative = location.relative_to(repo).as_posix()
                    base_record["source_sha"] = source_sha
                    base_record["git_tree_oid"] = commit_tree_oid(repo, source_sha, relative)
                    base_record["source_relative_path"] = relative
                else:
                    if not (in_site_profile or in_standard_library):
                        raise AuditFailure(
                            f"namespace search location is outside active Python roots: {location}"
                        )
                    if in_site_profile or not in_standard_library:
                        matched = [
                            distribution
                            for distribution in namespace_distributions
                            if isinstance(distribution, dict)
                            and location_value in distribution.get("search_locations", [])
                        ]
                        if not matched:
                            raise AuditFailure(
                                f"namespace package location has no locked distribution: {location}"
                            )
                        for distribution in matched:
                            record = locked_distribution_record(
                                distribution,
                                lock_versions,
                                active_site_roots,
                                module_name,
                                record_cache=distribution_record_cache,
                                record_rows_cache=distribution_record_rows_cache,
                                record_owner_inventory=record_owner_inventory,
                                namespace_location=location,
                            )
                            retain_record(record, module_name)
                retain_record(base_record, module_name)
            continue
        if not isinstance(origin, str) or not Path(origin).is_absolute():
            raise AuditFailure(f"loaded module has a non-absolute origin: {module_name}")
        path = Path(os.path.abspath(origin))
        data = read_regular_local(path)
        observed_sha = sha256(data)
        if module.get("sha256") != observed_sha:
            raise AuditFailure(f"loaded module origin changed during collection: {origin}")
        if path == plugin_path:
            if data != plugin_bytes:
                raise AuditFailure("generated collection plugin differs from its helper source")
            record = {
                "kind": "helper_generated_collection_plugin",
                "module": module_name,
                "origin": str(path),
                "bytes": len(data),
                "sha256": observed_sha,
            }
        else:
            try:
                relative = path.relative_to(repo).as_posix()
            except ValueError:
                relative = None
            in_site_profile = any(path.is_relative_to(root) for root in active_site_roots)
            in_standard_library = any(path.is_relative_to(root) for root in stdlib_roots)
            if relative is not None and not (in_site_profile or in_standard_library):
                object_id, committed = commit_blob_record(repo, source_sha, relative)
                if data != committed:
                    raise AuditFailure(
                        f"loaded checkout origin differs from its source blob: {relative}"
                    )
                record = {
                    "kind": "tracked_source_commit_blob",
                    "module": module_name,
                    "origin": relative,
                    "local_path": str(path),
                    "source_sha": source_sha,
                    "git_blob_oid": object_id,
                    "bytes": len(data),
                    "sha256": observed_sha,
                }
                if path.suffix == ".py":
                    declared_plugin_modules.update(literal_pytest_plugins(data, relative))
                if path.name == "conftest.py" and module_name.endswith("conftest"):
                    loaded_conftest_modules.add(module_name)
            else:
                if not (in_site_profile or in_standard_library):
                    raise AuditFailure(
                        f"loaded module origin is outside active Python roots: {origin}"
                    )
                distribution = module.get("distribution")
                if distribution is None and in_standard_library and not in_site_profile:
                    record = {
                        "kind": "selected_python_standard_library",
                        "module": module_name,
                        "origin": str(path),
                        "bytes": len(data),
                        "sha256": observed_sha,
                    }
                else:
                    if not in_site_profile:
                        raise AuditFailure(
                            f"installed module origin is outside active site roots: {origin}"
                        )
                    if not isinstance(distribution, dict):
                        raise AuditFailure(
                            f"loaded installed module has no distribution identity: {origin}"
                        )
                    algorithm = distribution.get("record_hash_algorithm")
                    recorded_hash = distribution.get("record_hash_value")
                    if algorithm != "sha256" or not isinstance(recorded_hash, str):
                        raise AuditFailure(
                            f"installed module has no SHA-256 wheel RECORD binding: {origin}"
                        )
                    expected_record_hash = (
                        base64.urlsafe_b64encode(hashlib.sha256(data).digest())
                        .decode("ascii")
                        .rstrip("=")
                    )
                    if recorded_hash != expected_record_hash:
                        raise AuditFailure(
                            f"installed module bytes differ from its wheel RECORD: {origin}"
                        )
                    distribution_record = locked_distribution_record(
                        distribution,
                        lock_versions,
                        active_site_roots,
                        module_name,
                        record_cache=distribution_record_cache,
                        record_rows_cache=distribution_record_rows_cache,
                        record_owner_inventory=record_owner_inventory,
                        file_origin=path,
                        file_bytes=data,
                    )
                    retain_record(distribution_record, module_name)
                    name = distribution["name"]
                    version = distribution["version"]
                    record = {
                        "kind": "locked_python_distribution",
                        "module": module_name,
                        "origin": str(path),
                        "distribution": name,
                        "version": version,
                        "distribution_record_sha256": distribution["distribution_record_sha256"],
                        "bytes": len(data),
                        "sha256": observed_sha,
                    }
        if record.get("kind") == "helper_generated_collection_plugin":
            record["local_path"] = str(path)
        retain_record(record, module_name)
        source_records[module_name] = record

    module_class_records = validate_module_class_provenance(module_rows, source_records)
    for module_name, class_record in module_class_records.items():
        origin_rows[f"module-class:{module_name}"] = {
            "kind": "loaded_module_subclass_class_origin",
            "module": module_name,
            **class_record,
        }

    for record in reconcile_generated_module_rows(
        module_rows,
        source_records,
        expected_runtime_profile,
        python,
        python_executable,
        timeout_seconds,
    ):
        retain_record(record, record["module"])

    plugin_rows = report.get("plugins")
    if not isinstance(plugin_rows, list):
        raise AuditFailure("pytest collection report omits the loaded plugin inventory")
    for plugin in plugin_rows:
        if (
            not isinstance(plugin, dict)
            or not isinstance(plugin.get("name"), str)
            or not isinstance(plugin.get("module"), str)
            or plugin["module"] not in module_rows
        ):
            raise AuditFailure("loaded pytest plugin has no corresponding module-origin record")
        module_name = plugin["module"]
        module_row = module_rows[module_name]
        if module_name == COLLECTION_PLUGIN_NAME:
            continue
        distribution = module_row.get("distribution")
        distribution_name = (
            normalized_distribution_name(distribution.get("name", ""))
            if isinstance(distribution, dict)
            else ""
        )
        if (
            module_name == "pytest" or module_name.startswith(("pytest.", "_pytest."))
        ) and distribution_name == "pytest":
            continue
        if module_name.startswith("pluggy.") and distribution_name == "pluggy":
            continue
        if module_name in declared_plugin_modules:
            continue
        origin_value = module_row.get("origin")
        if (
            isinstance(origin_value, str)
            and Path(origin_value).name == "conftest.py"
            and module_name in loaded_conftest_modules
        ):
            continue
        raise AuditFailure(f"pytest loaded an unlisted collection plugin: {module_name}")

    config_origin = report.get("config_origin")
    if config_origin is not None:
        if not isinstance(config_origin, str) or not Path(config_origin).is_absolute():
            raise AuditFailure("pytest configuration origin is malformed")
        config_path = Path(os.path.abspath(config_origin))
        config_bytes = read_regular_local(config_path)
        try:
            relative = config_path.relative_to(repo).as_posix()
        except ValueError as error:
            raise AuditFailure("pytest configuration is outside the frozen checkout") from error
        object_id, committed = commit_blob_record(repo, source_sha, relative)
        if config_bytes != committed:
            raise AuditFailure(f"pytest configuration differs from its source object: {relative}")
        origin_rows[relative] = {
            "kind": "tracked_source_commit_config",
            "origin": relative,
            "local_path": str(config_path),
            "source_sha": source_sha,
            "git_blob_oid": object_id,
            "bytes": len(config_bytes),
            "sha256": sha256(config_bytes),
        }

    startup_files = report.get("startup_files")
    if not isinstance(startup_files, list):
        raise AuditFailure("pytest collection report omits Python startup-file inventory")
    for startup in startup_files:
        if not isinstance(startup, dict) or not isinstance(startup.get("origin"), str):
            raise AuditFailure("Python startup-file inventory contains a malformed row")
        origin = Path(startup["origin"])
        if not origin.is_absolute() or not any(
            origin.is_relative_to(root) for root in active_site_roots
        ):
            raise AuditFailure(f"Python startup file is outside active site roots: {origin}")
        data = read_regular_local(origin)
        if sha256(data) != startup.get("sha256"):
            raise AuditFailure(f"Python startup file changed during collection: {origin}")
        origin_rows[str(origin)] = {
            "kind": "selected_python_startup_profile",
            "origin": str(origin),
            "label": startup.get("label"),
            "bytes": len(data),
            "sha256": sha256(data),
        }
    for record_evidence in record_inventory_evidence:
        key = str(record_evidence["origin"])
        existing = origin_rows.get(key)
        if existing is None:
            origin_rows[key] = record_evidence
            continue
        if (
            existing.get("bytes") != record_evidence["bytes"]
            or existing.get("sha256") != record_evidence["sha256"]
        ):
            raise AuditFailure(f"installed RECORD changed during complete ownership census: {key}")
    return [origin_rows[key] for key in sorted(origin_rows)]


def bound_pytest_environment(
    report: dict[str, Any],
    origins: list[dict[str, Any]],
    lock_versions: dict[str, set[str]],
) -> dict[str, str]:
    """Derive pytest's environment contribution from its locked installed origin and RECORD."""
    pytest_profile = report.get("pytest")
    module_inventory = report.get("module_origins")
    if not isinstance(pytest_profile, dict) or not isinstance(module_inventory, list):
        raise AuditFailure("pytest environment source omits its runtime module identity")
    if not isinstance(origins, list) or any(not isinstance(row, dict) for row in origins):
        raise AuditFailure("pytest environment source has malformed bound origin records")
    if any(not isinstance(row, dict) for row in module_inventory):
        raise AuditFailure("pytest environment source has malformed module-origin records")
    version = pytest_profile.get("version")
    origin = pytest_profile.get("origin")
    if not isinstance(version, str) or not version or not isinstance(origin, str):
        raise AuditFailure("pytest environment source has a malformed version or origin")
    if not Path(origin).is_absolute() or version not in lock_versions.get("pytest", set()):
        raise AuditFailure("pytest environment source is outside the locked version profile")
    module_rows = [
        row for row in module_inventory if isinstance(row, dict) and row.get("module") == "pytest"
    ]
    if len(module_rows) != 1 or module_rows[0].get("origin") != origin:
        raise AuditFailure("pytest version does not identify exactly one loaded module origin")
    module_row = module_rows[0]
    distribution = module_row.get("distribution")
    if not isinstance(distribution, dict):
        raise AuditFailure("pytest loaded origin has no installed distribution identity")
    distribution_name = distribution.get("name")
    distribution_version = distribution.get("version")
    record_path = distribution.get("record_path")
    record_sha256 = distribution.get("distribution_record_sha256")
    if (
        not isinstance(distribution_name, str)
        or normalized_distribution_name(distribution_name) != "pytest"
        or distribution_version != version
        or not isinstance(record_path, str)
        or not Path(record_path).is_absolute()
        or not isinstance(record_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", record_sha256)
    ):
        raise AuditFailure("pytest module identity is not bound to its locked RECORD digest")
    module_bindings = [
        row
        for row in origins
        if row.get("kind") == "locked_python_distribution"
        and row.get("module") == "pytest"
        and row.get("origin") == origin
        and isinstance(row.get("distribution"), str)
        and normalized_distribution_name(row["distribution"]) == "pytest"
        and row.get("version") == version
        and row.get("distribution_record_sha256") == record_sha256
        and row.get("sha256") == module_row.get("sha256")
    ]
    if len(module_bindings) != 1:
        raise AuditFailure("pytest module bytes lack one locked distribution-origin binding")
    record_bindings = [
        row
        for row in origins
        if row.get("kind") == "locked_python_distribution_record"
        and row.get("origin") == record_path
        and isinstance(row.get("distribution"), str)
        and normalized_distribution_name(row["distribution"]) == "pytest"
        and row.get("version") == version
        and row.get("sha256") == record_sha256
        and isinstance(row.get("modules"), list)
        and "pytest" in row["modules"]
    ]
    if len(record_bindings) != 1:
        raise AuditFailure("pytest RECORD bytes lack one source-bound installed-origin record")
    return {"PYTEST_VERSION": module_bindings[0]["version"]}


def reconcile_effective_collection_environment(
    declared_environment: object,
    startup_environment: object,
    framework_environment: object,
    effective_environment: object,
) -> dict[str, dict[str, str]]:
    """Reconcile every effective collection key across declared, startup, and framework roles."""
    declared = environment_mapping(declared_environment, "declared collection environment")
    startup = environment_mapping(startup_environment, "isolated launcher startup environment")
    framework = environment_mapping(framework_environment, "bound framework environment")
    effective = environment_mapping(effective_environment, "effective collection environment")
    if any(startup.get(key) != value for key, value in declared.items()):
        raise AuditFailure("selected launcher changed a declared collection environment value")
    role_overlap = sorted(set(startup) & set(framework))
    if role_overlap:
        raise AuditFailure(
            "startup and framework environment roles overlap: " + ", ".join(role_overlap)
        )
    expected = {**startup, **framework}
    if effective != expected:
        missing = sorted(set(expected) - set(effective))
        unexpected = sorted(set(effective) - set(expected))
        changed = sorted(
            key for key in set(expected) & set(effective) if expected[key] != effective[key]
        )
        reasons = []
        if missing:
            reasons.append("missing=" + ",".join(missing))
        if unexpected:
            reasons.append("unexpected=" + ",".join(unexpected))
        if changed:
            reasons.append("changed=" + ",".join(changed))
        raise AuditFailure(
            "effective pytest environment differs from the complete reconciled transition: "
            + "; ".join(reasons)
        )
    return {
        "declared": declared,
        "startup": startup,
        "framework": framework,
        "effective": effective,
    }


def recheck_collection_origins(rows: list[dict[str, Any]]) -> None:
    """Require every file origin captured at collection to retain the same bytes."""
    for row in rows:
        if row.get("path_kind") == "directory":
            origin = row.get("origin")
            if not isinstance(origin, str) or not Path(origin).is_absolute():
                raise AuditFailure("captured namespace directory path is malformed")
            if directory_identity(Path(origin)) != row.get("directory_identity"):
                raise AuditFailure(f"collection search directory changed after capture: {origin}")
            continue
        origin = row.get("local_path", row.get("origin"))
        if not isinstance(origin, str) or not Path(origin).is_absolute():
            continue
        data = read_regular_local(Path(origin))
        if len(data) != row.get("bytes") or sha256(data) != row.get("sha256"):
            raise AuditFailure(f"collection input changed after it was read: {origin}")
        metadata_origin = row.get("metadata_origin")
        if metadata_origin is not None:
            if not isinstance(metadata_origin, str) or not Path(metadata_origin).is_absolute():
                raise AuditFailure("captured distribution METADATA path is malformed")
            metadata_data = read_regular_local(Path(metadata_origin))
            if len(metadata_data) != row.get("metadata_bytes") or sha256(metadata_data) != row.get(
                "metadata_sha256"
            ):
                raise AuditFailure(
                    f"distribution METADATA changed after it was read: {metadata_origin}"
                )


def collect_ids(
    *,
    repo: Path,
    source_sha: str,
    python: Path,
    product: Path,
    selectors: list[str],
    allowed_paths: set[str],
    output_root: Path,
    label: str,
    timeout_seconds: float,
) -> tuple[set[str], dict[str, Any]]:
    plugin_path = output_root / f"{COLLECTION_PLUGIN_NAME}.py"
    plugin_bytes = COLLECTION_PLUGIN_SOURCE.encode("utf-8")
    if plugin_path.exists() or plugin_path.is_symlink():
        if read_regular_local(plugin_path) != plugin_bytes:
            raise AuditFailure("collection plugin path is occupied by different bytes")
    else:
        plugin_path.write_bytes(plugin_bytes)
    result_path = output_root / f"{label}.collection.json"
    if result_path.exists() or result_path.is_symlink():
        raise AuditFailure(f"collection result path already exists: {result_path}")
    python_before = python_executable_record(python)
    environment = collection_environment(product, output_root, result_path)
    isolated_runtime_before = selected_python_runtime_profile(
        python,
        home=Path(environment["HOME"]),
        timeout_seconds=timeout_seconds,
        probe_environment=environment,
    )
    if isolated_runtime_before["launcher_record"] != python_before:
        raise AuditFailure("selected Python launcher changed before isolated profile capture")
    args = [
        str(python),
        "-B",
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "-p",
        COLLECTION_PLUGIN_NAME,
        "--collect-only",
        "-q",
        "--no-header",
        "--no-summary",
        "--color=no",
        "-o",
        "addopts=",
        "--import-mode=importlib",
        "--confcutdir",
        str(product / "tests/unit"),
        "--rootdir",
        str(product),
        *selectors,
    ]
    started = time.monotonic()
    try:
        result = subprocess.run(  # noqa: S603 -- explicit Python profile and fixed pytest collection argv.
            args,
            cwd=product,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = (
            error.stdout.decode("utf-8", "replace")
            if isinstance(error.stdout, bytes)
            else (error.stdout or "")
        )
        stderr = (
            error.stderr.decode("utf-8", "replace")
            if isinstance(error.stderr, bytes)
            else (error.stderr or "")
        )
        (output_root / f"{label}.stdout.txt").write_text(stdout, encoding="utf-8")
        (output_root / f"{label}.stderr.txt").write_text(stderr, encoding="utf-8")
        raise AuditFailure(
            f"source pytest collection timed out after {timeout_seconds}s: {label}"
        ) from error
    wall = time.monotonic() - started
    (output_root / f"{label}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (output_root / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    record = {
        "argv": args,
        "cwd": str(product),
        "returncode": result.returncode,
        "timeout_seconds": timeout_seconds,
        "wall_seconds": wall,
        "stdout_sha256": sha256(result.stdout.encode("utf-8")),
        "stderr_sha256": sha256(result.stderr.encode("utf-8")),
        "collected_node_count": None,
        "collected_node_ids_sha256": None,
    }
    if result.returncode:
        raise AuditFailure(f"source pytest collection exited {result.returncode}: {label}")
    try:
        report = json.loads(read_regular_local(result_path))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditFailure(
            f"pytest did not write a valid complete collection report: {label}"
        ) from error
    if not isinstance(report, dict):
        raise AuditFailure(f"pytest collection report root is not an object: {label}")
    captured_environment = report.get("effective_environment")
    python_profile = report.get("python")
    if not isinstance(python_profile, dict):
        raise AuditFailure("pytest collection report omits its Python runtime profile")
    validate_python_runtime_profile(isolated_runtime_before, python_profile)
    if report.get("collection_exitstatus") != 0:
        raise AuditFailure(
            "pytest collection report does not confirm a complete successful session"
        )
    ids = parse_collected_ids(report, allowed_paths)
    lock_versions = locked_python_versions(repo, source_sha)
    origins = bind_collection_origins(
        repo,
        source_sha,
        report,
        plugin_path,
        plugin_bytes,
        lock_versions,
        isolated_runtime_before,
        python,
        python_before,
        timeout_seconds,
    )
    if not any(row.get("kind") == "helper_generated_collection_plugin" for row in origins):
        raise AuditFailure("the source-bound collection capture plugin was not loaded")
    pytest_profile = report.get("pytest")
    if not isinstance(pytest_profile, dict):
        raise AuditFailure("pytest collection report omits pytest identity")
    try:
        child_executable = Path(
            str(python_profile["runtime_profile"]["resolved_executable"])
        ).resolve(strict=True)
    except (KeyError, OSError) as error:
        raise AuditFailure(
            "pytest collection report has no resolvable Python executable"
        ) from error
    if child_executable != Path(python_before["resolved_path"]):
        raise AuditFailure("pytest collection used a different Python executable")
    if not isinstance(pytest_profile.get("version"), str):
        raise AuditFailure("pytest collection report has no version")
    if pytest_profile["version"] not in lock_versions.get("pytest", set()):
        raise AuditFailure("pytest version is not pinned by the frozen application lock")
    framework_environment = bound_pytest_environment(report, origins, lock_versions)
    environment_transition = reconcile_effective_collection_environment(
        environment,
        isolated_runtime_before["startup_environment"],
        framework_environment,
        captured_environment,
    )
    isolated_runtime_after = selected_python_runtime_profile(
        python,
        home=Path(environment["HOME"]),
        timeout_seconds=timeout_seconds,
        probe_environment=environment,
    )
    if isolated_runtime_after != isolated_runtime_before:
        raise AuditFailure("selected Python runtime profile changed during source collection")
    python_after = python_executable_record(python)
    if python_after != python_before:
        raise AuditFailure("collector Python executable changed during source collection")
    record["collected_node_count"] = len(ids)
    record["collected_node_ids_sha256"] = canonical_ids_sha256(ids)
    record["collected_node_ids"] = sorted(ids)
    record["complete_collection_report_sha256"] = sha256(read_regular_local(result_path))
    record["declared_environment"] = environment_transition["declared"]
    record["startup_environment"] = environment_transition["startup"]
    record["framework_environment"] = environment_transition["framework"]
    record["effective_environment"] = environment_transition["effective"]
    record["declared_environment_sha256"] = canonical_json_sha256(
        environment_transition["declared"]
    )
    record["startup_environment_sha256"] = canonical_json_sha256(environment_transition["startup"])
    record["framework_environment_sha256"] = canonical_json_sha256(
        environment_transition["framework"]
    )
    record["effective_environment_sha256"] = canonical_json_sha256(
        environment_transition["effective"]
    )
    record["plugin_policy"] = {
        "autoload_disabled": True,
        "explicit_capture_plugin": COLLECTION_PLUGIN_NAME,
        "cacheprovider_disabled": True,
        "pytest_plugins_environment_inherited": False,
        "external_plugins_from_locked_source_declarations_only": True,
    }
    record["python_executable"] = python_before
    record["isolated_python_runtime_profile"] = isolated_runtime_before
    record["python_runtime_profile"] = python_profile
    record["pytest_profile"] = pytest_profile
    record["loaded_plugins"] = report.get("plugins")
    record["loaded_module_origins"] = origins
    record["config_origin"] = report.get("config_origin")
    record["startup_files"] = report.get("startup_files")
    return ids, record


def selected_group_ids(group: dict[str, Any], collected: set[str]) -> set[str]:
    path = group["test_path"]
    selectors = group["selectors"]
    if not isinstance(path, str) or not isinstance(selectors, list) or not selectors:
        raise AuditFailure("installed consumer group must have a test_path and selectors")
    resolved: set[str] = set()
    for selector in selectors:
        if not isinstance(selector, str) or not selector:
            raise AuditFailure(f"invalid selector in {path}: {selector!r}")
        stem = f"{path}::{selector}"
        if "[" in selector:
            matches = {node_id for node_id in collected if node_id == stem}
        else:
            matches = {
                node_id
                for node_id in collected
                if node_id == stem or node_id.startswith(stem + "[")
            }
        if not matches:
            raise AuditFailure(f"declared selector did not resolve in actual collection: {stem}")
        resolved.update(matches)
    return resolved


def asset_rows_from_config(
    repo: Path, source_sha: str, manifest: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    hatch = tomllib.loads(read_commit_blob(repo, source_sha, HATCH_REL).decode("utf-8"))
    build = hatch["build"]["targets"]
    force_include = build["wheel"]["force-include"]
    sdist_include = set(build["sdist"]["include"])
    if not isinstance(force_include, dict) or not force_include:
        raise AuditFailure("frozen hatch.toml must define a nonempty wheel force-include map")
    rows: list[dict[str, Any]] = []
    for source, wheel in sorted(force_include.items()):
        if not isinstance(source, str) or not isinstance(wheel, str):
            raise AuditFailure("wheel force-include entries must map strings to strings")
        source_rel = f"policy-engine/{safe_relative(source).as_posix()}"
        archive = f"policy-engine/{source}"
        if source not in sdist_include:
            raise AuditFailure(f"source distribution omits wheel resource source: {source}")
        data = read_commit_blob(repo, source_sha, source_rel)
        rows.append(
            {
                "source": source,
                "archive": archive,
                "wheel": wheel,
                "bytes": len(data),
                "sha256": sha256(data),
            }
        )
    return rows, {
        "hatch_config_sha256": sha256(read_commit_blob(repo, source_sha, HATCH_REL)),
        "wheel_force_include_count": len(rows),
        "sdist_include_reconciled": True,
        "force_include_map_sha256": canonical_json_sha256(force_include),
        "asset_targets_sha256": canonical_json_sha256(rows),
        "source_derived_resource_count": len(rows),
        "source_resource_map_nonempty": bool(rows),
        "assets": rows,
        "resource_wheel_targets": sorted(str(row["wheel"]) for row in rows),
    }


def canonical_json_sha256(value: object) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(data)


def installed_origin_gate_binding(primary_source: bytes) -> tuple[str, str]:
    """Resolve the exact ignored local gate filename/hash declared by the frozen runner."""
    try:
        tree = ast.parse(primary_source.decode("utf-8", "strict"), filename=RUNNER_REL)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise AuditFailure(
            "primary runner cannot be parsed for its installed-origin gate"
        ) from error
    values: dict[str, ast.expr] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        for name in ("INSTALLED_ORIGIN_GATE_PATH", "INSTALLED_ORIGIN_GATE_SHA256"):
            if name in targets:
                if targets != [name] or name in values:
                    raise AuditFailure(f"primary runner has an ambiguous {name} binding")
                values[name] = node.value
    if set(values) != {"INSTALLED_ORIGIN_GATE_PATH", "INSTALLED_ORIGIN_GATE_SHA256"}:
        raise AuditFailure("primary runner omits its exact installed-origin gate binding")
    path_value = values["INSTALLED_ORIGIN_GATE_PATH"]
    if not (
        isinstance(path_value, ast.BinOp)
        and isinstance(path_value.op, ast.Div)
        and isinstance(path_value.left, ast.Name)
        and path_value.left.id == "HERE"
        and isinstance(path_value.right, ast.Constant)
        and type(path_value.right.value) is str
    ):
        raise AuditFailure("installed-origin gate path is not a literal HERE-relative filename")
    filename = path_value.right.value
    if (
        not filename.endswith(".py")
        or Path(filename).name != filename
        or filename in {"", ".", ".."}
        or chr(92) in filename
        or "/" in filename
    ):
        raise AuditFailure("installed-origin gate filename is not one safe Python source member")
    digest_value = values["INSTALLED_ORIGIN_GATE_SHA256"]
    if (
        not isinstance(digest_value, ast.Constant)
        or type(digest_value.value) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", digest_value.value)
    ):
        raise AuditFailure("installed-origin gate SHA-256 is not one full lowercase digest")
    relative = f"{HANDOFF_REL}/raw/{filename}"
    safe_relative(relative)
    return relative, digest_value.value


def bind_local_q2_raw_input(
    repo: Path, source_sha: str, relative: str, expected_sha256: str
) -> tuple[bytes, dict[str, Any]]:
    """Bind a dynamic Q2 raw input to Git or to the one explicit local-input rule."""
    raw_dir = PurePosixPath(HANDOFF_REL) / "raw"
    candidate = safe_relative(relative)
    if candidate.parent != raw_dir or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]*", candidate.name
    ):
        raise AuditFailure(f"dynamic Q2 input must be one direct Q2 raw member: {relative}")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise AuditFailure(f"dynamic Q2 input SHA-256 is malformed: {relative}")

    data = read_regular_local(repo / relative)
    if sha256(data) != expected_sha256:
        raise AuditFailure(f"dynamic Q2 input differs from its exact SHA pin: {relative}")

    def object_bytes(entry: bytes, expected_path: str, *, tree: bool) -> tuple[str, bytes]:
        header, actual_path = entry.split(b"\t", 1)
        fields = header.decode("ascii").split()
        if actual_path.decode("utf-8", "strict") != expected_path:
            raise AuditFailure(f"Git object path mismatch for dynamic Q2 input: {relative}")
        if tree:
            if len(fields) != 3:
                raise AuditFailure(f"malformed source tree entry for {relative}")
            mode, kind, object_id = fields
            if mode not in {"100644", "100755"} or kind != "blob":
                raise AuditFailure(f"dynamic Q2 source must be a regular blob: {relative}")
        else:
            if len(fields) != 3:
                raise AuditFailure(f"malformed index entry for {relative}")
            mode, object_id, stage = fields
            if mode not in {"100644", "100755"} or stage != "0":
                raise AuditFailure(f"dynamic Q2 index entry must be stage 0 regular: {relative}")
        blob = git_run(repo, "cat-file", "blob", object_id, binary=True)
        if not isinstance(blob, bytes):
            raise AuditFailure("Git blob lookup did not return bytes")
        return object_id, blob

    source_raw = git_run(repo, "ls-tree", "-z", source_sha, "--", relative, binary=True)
    index_raw = git_run(repo, "ls-files", "--stage", "-z", "--", relative, binary=True)
    if not isinstance(source_raw, bytes) or not isinstance(index_raw, bytes):
        raise AuditFailure("Git tree/index lookup did not return bytes")
    source_entries = [entry for entry in source_raw.split(b"\0") if entry]
    index_entries = [entry for entry in index_raw.split(b"\0") if entry]
    if len(source_entries) > 1 or len(index_entries) > 1:
        raise AuditFailure(f"dynamic Q2 input has ambiguous Git ownership: {relative}")
    source_blob = object_bytes(source_entries[0], relative, tree=True) if source_entries else None
    index_blob = object_bytes(index_entries[0], relative, tree=False) if index_entries else None
    if source_blob is not None and data == source_blob[1]:
        return data, {
            "kind": "tracked_source_commit_blob",
            "source_sha": source_sha,
            "git_blob_oid": source_blob[0],
        }
    if index_blob is not None and data == index_blob[1]:
        return data, {
            "kind": "tracked_index_stage0_candidate",
            "git_blob_oid": index_blob[0],
            "claim_band": "candidate_until_committed",
        }
    if source_blob is not None or index_blob is not None:
        raise AuditFailure(f"dynamic Q2 input differs from its tracked Git object: {relative}")

    ignored = git_run(repo, "check-ignore", "--verbose", "--no-index", "--", relative)
    rows = ignored.splitlines()
    if len(rows) != 1:
        raise AuditFailure(f"dynamic Q2 ignore provenance is ambiguous: {relative}")
    binding, separator, reported_path = rows[0].partition("\t")
    fields = binding.split(":", 2)
    if (
        not separator
        or reported_path != relative
        or len(fields) != 3
        or fields[0] != "policy-engine/.gitignore"
        or fields[2] != "docs/research/**/raw/"
    ):
        raise AuditFailure(
            f"dynamic Q2 input is not admitted by the tracked Q2 raw ignore rule: {relative}"
        )
    try:
        rule_line = int(fields[1])
    except ValueError as error:
        raise AuditFailure(f"dynamic Q2 ignore rule line is malformed: {relative}") from error
    ignore_rules = (
        read_commit_blob(repo, source_sha, "policy-engine/.gitignore")
        .decode("utf-8", "strict")
        .splitlines()
    )
    if rule_line < 1 or rule_line > len(ignore_rules) or ignore_rules[rule_line - 1] != fields[2]:
        raise AuditFailure(f"dynamic Q2 ignore rule differs from the frozen source: {relative}")
    return data, {
        "kind": "explicit_repo_ignored_local_candidate",
        "claim_band": "candidate_only",
        "ignore_rule": {
            "path": fields[0],
            "line": rule_line,
            "pattern": fields[2],
        },
    }


def input_file_records(
    repo: Path,
    source_sha: str,
    supplemental_manifest_value: str,
    supplemental_manifest_sha256: str,
    *,
    helper_record: dict[str, Any],
    git_profile: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, bytes]]:
    tracked = (
        AUDIT_HELPER_REL,
        GITIGNORE_REL,
        MANIFEST_REL,
        RUNNER_REL,
        TIMEOUT_REL,
        SUPPLEMENT_REL,
        SUPPLEMENT_MANIFEST_REL,
        SITE_CUSTOMIZE_REL,
        HATCH_REL,
        APP_PROJECT_REL,
        APP_LOCK_REL,
        DOWHY_PROJECT_REL,
        DOWHY_LOCK_REL,
        DOWHY_PYTHON_REL,
        DOWHY_README_REL,
        GCP_PACKAGE_REL,
    )
    tracked_rows: dict[str, Any] = {}
    capsule_contents: dict[str, bytes] = {}
    for relative in tracked:
        data = read_commit_blob(repo, source_sha, relative)
        tracked_rows[relative] = {"bytes": len(data), "sha256": sha256(data)}
        capsule_contents[relative] = data
    if (
        helper_record.get("path") != AUDIT_HELPER_REL
        or helper_record.get("sha256") != tracked_rows[AUDIT_HELPER_REL]["sha256"]
    ):
        raise AuditFailure("running audit helper differs from its canonical source capsule bytes")
    tracked_rows[AUDIT_HELPER_REL]["provenance"] = helper_record["provenance"]
    supplemental_manifest_path = Path(supplemental_manifest_value)
    if not supplemental_manifest_path.is_absolute():
        raise AuditFailure("supplemental manifest path must be absolute")
    supplemental_manifest_path = Path(os.path.abspath(supplemental_manifest_path))
    try:
        supplemental_manifest_relative = supplemental_manifest_path.relative_to(repo).as_posix()
    except ValueError as error:
        raise AuditFailure(
            "supplemental manifest must be inside the attached repository"
        ) from error
    safe_relative(supplemental_manifest_relative)
    if not re.fullmatch(r"[0-9a-f]{64}", supplemental_manifest_sha256):
        raise AuditFailure("supplemental manifest SHA-256 must be full lowercase hex")
    supplemental_provenance: dict[str, Any] | None = None
    if supplemental_manifest_relative == SUPPLEMENT_MANIFEST_REL:
        supplemental_manifest_bytes = capsule_contents[SUPPLEMENT_MANIFEST_REL]
    else:
        supplemental_manifest_path = repo / supplemental_manifest_relative
        supplemental_manifest_bytes, supplemental_provenance = bind_local_q2_raw_input(
            repo,
            source_sha,
            supplemental_manifest_relative,
            supplemental_manifest_sha256,
        )
        capsule_contents[supplemental_manifest_relative] = supplemental_manifest_bytes

    tracked_index_rows: dict[str, Any] = {}
    raw_rows: dict[str, Any] = {}
    origin_gate_relative, origin_gate_sha256 = installed_origin_gate_binding(
        capsule_contents[RUNNER_REL]
    )
    origin_gate_bytes, origin_gate_provenance = bind_local_q2_raw_input(
        repo, source_sha, origin_gate_relative, origin_gate_sha256
    )
    origin_gate_row = {
        "bytes": len(origin_gate_bytes),
        "sha256": sha256(origin_gate_bytes),
        "provenance": origin_gate_provenance,
    }
    if origin_gate_provenance["kind"] == "tracked_source_commit_blob":
        tracked_rows[origin_gate_relative] = origin_gate_row
    elif origin_gate_provenance["kind"] == "tracked_index_stage0_candidate":
        tracked_index_rows[origin_gate_relative] = origin_gate_row
    else:
        raw_rows[origin_gate_relative] = origin_gate_row
    capsule_contents[origin_gate_relative] = origin_gate_bytes
    if sha256(supplemental_manifest_bytes) != supplemental_manifest_sha256:
        raise AuditFailure(
            "explicit supplemental manifest SHA-256 differs from its exact input bytes"
        )
    if (
        supplemental_manifest_relative != SUPPLEMENT_MANIFEST_REL
        and supplemental_provenance is not None
    ):
        supplemental_row = {
            "bytes": len(supplemental_manifest_bytes),
            "sha256": sha256(supplemental_manifest_bytes),
            "provenance": supplemental_provenance,
        }
        if supplemental_provenance["kind"] == "tracked_source_commit_blob":
            tracked_rows[supplemental_manifest_relative] = supplemental_row
        elif supplemental_provenance["kind"] == "tracked_index_stage0_candidate":
            tracked_index_rows[supplemental_manifest_relative] = supplemental_row
        else:
            raw_rows[supplemental_manifest_relative] = supplemental_row
    return {
        "tracked_git_objects": tracked_rows,
        "tracked_index_candidates": tracked_index_rows,
        "ignored_local_inputs": raw_rows,
        "direct_source_path_lease": list(tracked),
        "git_oracle": git_profile,
        "canonical_helper": helper_record,
        "supplemental_manifest_path": str(supplemental_manifest_path),
        "supplemental_manifest_sha256": supplemental_manifest_sha256,
    }, capsule_contents


def profile_names_from_runner_sources(
    primary_source: bytes, supplemental_source: bytes
) -> tuple[list[str], list[str]]:
    """Extract the three literal profile contracts from both existing runners."""
    primary_tree = ast.parse(primary_source.decode("utf-8"), filename=RUNNER_REL)
    supplemental_tree = ast.parse(supplemental_source.decode("utf-8"), filename=SUPPLEMENT_REL)
    primary_candidates: list[list[str]] = []
    for node in ast.walk(primary_tree):
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "profiles" for target in node.targets
        ):
            continue
        value = node.value
        if isinstance(value, ast.List) and all(
            isinstance(item, ast.Tuple)
            and item.elts
            and isinstance(item.elts[0], ast.Constant)
            and isinstance(item.elts[0].value, str)
            for item in value.elts
        ):
            primary_candidates.append([item.elts[0].value for item in value.elts])
    supplemental_names: list[str] | None = None
    for node in supplemental_tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "PROFILE_NAMES"
                for target in node.targets
            )
            and isinstance(node.value, (ast.Tuple, ast.List))
            and all(
                isinstance(item, ast.Constant) and isinstance(item.value, str)
                for item in node.value.elts
            )
        ):
            supplemental_names = [item.value for item in node.value.elts]
    if len(primary_candidates) != 1 or supplemental_names is None:
        raise AuditFailure("cannot derive one literal profile list from both existing Q2 runners")
    return primary_candidates[0], supplemental_names


def profile_contract_is_supported(
    manifest_names: list[str], primary_names: list[str], supplemental_names: list[str]
) -> bool:
    return (
        tuple(manifest_names) == REVIEWED_PROFILE_NAMES
        and tuple(primary_names) == REVIEWED_PROFILE_NAMES
        and tuple(supplemental_names) == REVIEWED_PROFILE_NAMES
    )


def primary_manifest_matches_collection(
    manifest: dict[str, Any],
    expected_ids: set[str],
    expected_assets: list[dict[str, Any]],
    source_hashes: dict[str, str],
) -> bool:
    """Reconcile all current primary count-bearing declarations to source objects."""
    suite = manifest.get("current_primary_suite")
    candidate = manifest.get("candidate_baseline")
    if not isinstance(suite, dict) or not isinstance(candidate, dict):
        return False
    ids = suite.get("selected_node_ids")
    return (
        isinstance(ids, list)
        and ids == sorted(expected_ids)
        and exact_nonbool_count_matches(suite.get("selected_node_count"), len(expected_ids))
        and suite.get("selected_node_ids_sha256") == canonical_ids_sha256(expected_ids)
        and json_values_match_exactly(suite.get("source_file_sha256"), source_hashes)
        and exact_nonbool_count_matches(candidate.get("force_include_count"), len(expected_assets))
        and json_values_match_exactly(candidate.get("force_include_assets"), expected_assets)
    )


def supplemental_manifest_count_mismatches(
    manifest: dict[str, Any], *, asset_count: int, supplemental_id_count: int
) -> list[str]:
    """Return source-freeze count fields that fail exact typed content reconciliation."""
    mismatches: list[str] = []
    primary_inputs = manifest.get("primary_inputs")
    supplement = manifest.get("supplemental_suite")
    if not isinstance(primary_inputs, dict) or not exact_nonbool_count_matches(
        primary_inputs.get("force_include_asset_count_per_profile"), asset_count
    ):
        mismatches.append("force_include_asset_count_per_profile")
    if not isinstance(supplement, dict) or not exact_nonbool_count_matches(
        supplement.get("expected_node_count"), supplemental_id_count
    ):
        mismatches.append("supplemental_suite.expected_node_count")
    return mismatches


def manifest_mismatches(
    current: dict[str, Any], proposed: dict[str, Any], current_raw: bytes, proposed_raw: bytes
) -> list[str]:
    mismatches: list[str] = []
    if current_raw != proposed_raw:
        for key in ("candidate_baseline", "current_primary_suite"):
            if not json_values_match_exactly(current.get(key), proposed.get(key)):
                mismatches.append(key)
    return mismatches


def rebind_timeout_driver(source: str, runner_sha: str) -> tuple[str, bytes]:
    if not re.fullmatch(r"[0-9a-f]{64}", runner_sha):
        raise AuditFailure("reviewed runner SHA-256 must be full lowercase hex")
    tree = ast.parse(source)
    bindings: list[ast.Assign] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "EXPECTED_RUNNER_SHA256" in targets:
                if targets != ["EXPECTED_RUNNER_SHA256"]:
                    raise AuditFailure("timeout driver runner pin binding is ambiguous")
                bindings.append(node)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "EXPECTED_RUNNER_SHA256"
        ):
            raise AuditFailure("timeout driver runner pin binding is ambiguous")
    if len(bindings) != 1:
        raise AuditFailure("timeout driver must expose one reviewed runner SHA pin")
    value_node = bindings[0].value
    if (
        not isinstance(value_node, ast.Constant)
        or not isinstance(value_node.value, str)
        or not re.fullmatch(r"[0-9a-f]{64}", value_node.value)
    ):
        raise AuditFailure("timeout driver runner pin is not one full literal SHA-256")
    literal = ast.get_source_segment(source, value_node)
    if not isinstance(literal, str) or literal not in {
        repr(value_node.value),
        f'"{value_node.value}"',
        f"'{value_node.value}'",
    }:
        raise AuditFailure("timeout driver runner pin literal is not one simple quoted value")
    if source.count(literal) != 1:
        raise AuditFailure("cannot safely rebind exactly one timeout-driver runner pin")
    quote = literal[0]
    updated = source.replace(literal, f"{quote}{runner_sha}{quote}", 1)
    return updated, updated.encode("utf-8")


def validate_recomputed_ids(
    manifest: dict[str, Any],
    expected_ids: set[str],
    expected_assets: list[dict[str, Any]] | None = None,
) -> None:
    suite = manifest.get("current_primary_suite")
    if not isinstance(suite, dict):
        raise AuditFailure("manifest omits current_primary_suite")
    declared = suite.get("selected_node_ids")
    if not isinstance(declared, list) or declared != sorted(set(declared)):
        raise AuditFailure("selected_node_ids must be sorted and unique")
    if not exact_nonbool_count_matches(suite.get("selected_node_count"), len(declared)):
        raise AuditFailure("selected_node_count does not equal the declared ID list length")
    if suite.get("selected_node_ids_sha256") != canonical_ids_sha256(declared):
        raise AuditFailure("selected_node_ids_sha256 does not recompute from the ID list")
    if set(declared) != expected_ids:
        missing = sorted(expected_ids - set(declared))
        extra = sorted(set(declared) - expected_ids)
        raise AuditFailure(
            f"declared node IDs differ from actual source collection: "
            f"missing={missing[:8]} extra={extra[:8]}"
        )
    if expected_assets is not None:
        candidate = manifest.get("candidate_baseline")
        actual_assets = (
            candidate.get("force_include_assets") if isinstance(candidate, dict) else None
        )
        if (
            not isinstance(candidate, dict)
            or not exact_nonbool_count_matches(
                candidate.get("force_include_count"), len(expected_assets)
            )
            or not json_values_match_exactly(actual_assets, expected_assets)
        ):
            raise AuditFailure(
                "manifest force-include resources differ from frozen hatch.toml and source bytes"
            )


def validate_supplemental_node_ids(manifest: dict[str, Any], expected_ids: set[str]) -> None:
    suite = manifest.get("supplemental_suite")
    if not isinstance(suite, dict):
        raise AuditFailure("supplemental manifest omits its suite")
    declared = suite.get("selected_node_ids")
    if (
        not isinstance(declared, list)
        or not declared
        or any(not isinstance(item, str) for item in declared)
    ):
        raise AuditFailure("supplemental selected IDs must be a nonempty string list")
    if declared != sorted(set(declared)):
        raise AuditFailure("supplemental selected IDs must be sorted and unique")
    declared_count = suite.get("expected_node_count")
    if not exact_nonbool_count_matches(declared_count, len(declared)):
        raise AuditFailure("supplemental selected-ID count differs from its full list")
    if suite.get("selected_node_ids_sha256") != canonical_ids_sha256(declared):
        raise AuditFailure("supplemental selected-ID digest differs from its full list")
    if set(declared) != expected_ids:
        raise AuditFailure("supplemental manifest IDs differ from actual source collection")
    group = {"test_path": suite.get("test_path"), "selectors": suite.get("selectors")}
    if selected_group_ids(group, expected_ids) != expected_ids:
        raise AuditFailure("supplemental source collection contains undeclared selector IDs")


def self_test_origin_gate_symlink() -> dict[str, bool]:
    """Exercise both trusted root spellings and reject cross-boundary aliases."""
    import importlib.machinery
    import importlib.util
    import runpy
    import tempfile

    gate_path = Path(__file__).resolve(strict=True).with_name("installed_origin_gate_r4.py")
    if not gate_path.is_file():
        raise AuditFailure(f"installed-origin gate source is missing: {gate_path}")
    verify = runpy.run_path(str(gate_path)).get("verify_loaded_module_origins")
    if not callable(verify):
        raise AuditFailure("installed-origin gate has no generic loaded-module verifier")

    def load_module(name: str, path: Path) -> object:
        loader = importlib.machinery.SourceFileLoader(name, str(path))
        spec = importlib.machinery.ModuleSpec(name, loader, origin=str(path))
        spec.has_location = True
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module

    with tempfile.TemporaryDirectory(prefix="q2-origin-") as scratch:
        root = Path(scratch)
        purelib_storage, outside = root / "site-packages-storage", root / "outside"
        purelib_storage.mkdir()
        outside.mkdir()
        purelib = root / "site-packages"
        purelib.symlink_to(purelib_storage, target_is_directory=True)
        nested = outside / "nested"
        nested.mkdir()
        source = purelib / "origin_probe.py"
        payload = b"VALUE = 17\n"
        source.write_bytes(payload)
        outside_target = outside / "origin_probe.py"
        outside_target.write_bytes(payload)
        direct_alias = outside / "origin_probe_alias.py"
        direct_alias.symlink_to(source)
        escape = purelib / "escape"
        escape.symlink_to(nested, target_is_directory=True)
        inside_outside_alias = purelib / "outside_alias.py"
        inside_outside_alias.symlink_to(outside_target)
        if any(
            path.read_bytes() != source.read_bytes()
            for path in (outside_target, direct_alias, inside_outside_alias)
        ):
            raise AuditFailure("origin controls do not preserve identical bytes")

        reported_module = load_module("polisyos.origin_probe_reported_root", source)
        _, reported_errors = verify(purelib, {reported_module.__name__: reported_module})
        reported_root_accepted = not reported_errors

        canonical_source = source.resolve(strict=True)
        canonical_module = load_module("polisyos.origin_probe_canonical_root", canonical_source)
        _, canonical_errors = verify(purelib, {canonical_module.__name__: canonical_module})
        canonical_root_accepted = not canonical_errors

        direct_module = load_module("polisyos.origin_probe_outside_to_inside", direct_alias)
        if (
            not Path(direct_module.__file__)
            .resolve(strict=True)
            .is_relative_to(purelib.resolve(strict=True))
        ):
            raise AuditFailure("outside-to-inside alias did not resolve to the inside target")
        _, direct_errors = verify(purelib, {direct_module.__name__: direct_module})
        outside_to_inside_rejected = any(
            error.get("module") == direct_module.__name__ for error in direct_errors
        )

        inside_outside_module = load_module(
            "polisyos.origin_probe_inside_to_outside", inside_outside_alias
        )
        if (
            Path(inside_outside_module.__file__)
            .resolve(strict=True)
            .is_relative_to(purelib.resolve(strict=True))
        ):
            raise AuditFailure("inside-to-outside alias did not resolve outside the installed root")
        _, inside_outside_errors = verify(
            purelib, {inside_outside_module.__name__: inside_outside_module}
        )
        inside_to_outside_rejected = any(
            error.get("module") == inside_outside_module.__name__ for error in inside_outside_errors
        )

        # SourceFileLoader preserves the link/.. traversal before stat.
        traversal_path = purelib / "escape" / ".." / "origin_probe.py"
        traversal_name = "polisyos.origin_probe_parent_escape"
        traversal_module = load_module(traversal_name, traversal_path)
        reported = Path(traversal_module.__file__)
        if reported != traversal_path:
            raise AuditFailure(
                "source loader did not preserve the reported parent-traversal origin"
            )
        resolved = reported.resolve(strict=True)
        if (
            resolved.is_relative_to(purelib.resolve(strict=True))
            or resolved.read_bytes() != source.read_bytes()
        ):
            raise AuditFailure(
                "parent-traversal control did not load identical bytes from outside purelib"
            )
        _, traversal_errors = verify(purelib, {traversal_name: traversal_module})
        parent_traversal_rejected = any(
            error.get("module") == traversal_name for error in traversal_errors
        )

        return {
            "reported-root-alias-positive": reported_root_accepted,
            "canonical-root-positive": canonical_root_accepted,
            "outside-to-inside-identical-byte-alias-rejected": outside_to_inside_rejected,
            "inside-to-outside-identical-byte-alias-rejected": inside_to_outside_rejected,
            "parent-traversal-identical-byte-origin-rejected": parent_traversal_rejected,
        }


def self_test_environment_reconciliation() -> dict[str, bool]:
    """Exercise full environment transition and bound pytest-version falsifiers."""
    version = "9.0.2"
    module_origin = "/fixture/site-packages/pytest/__init__.py"
    record_origin = "/fixture/site-packages/pytest-9.0.2.dist-info/RECORD"
    record_sha256 = "a" * 64
    module_sha256 = "b" * 64
    report: dict[str, Any] = {
        "pytest": {"version": version, "origin": module_origin},
        "module_origins": [
            {
                "module": "pytest",
                "origin": module_origin,
                "sha256": module_sha256,
                "distribution": {
                    "name": "pytest",
                    "version": version,
                    "record_path": record_origin,
                    "distribution_record_sha256": record_sha256,
                },
            }
        ],
    }
    origins: list[dict[str, Any]] = [
        {
            "kind": "locked_python_distribution",
            "module": "pytest",
            "origin": module_origin,
            "distribution": "pytest",
            "version": version,
            "distribution_record_sha256": record_sha256,
            "sha256": module_sha256,
        },
        {
            "kind": "locked_python_distribution_record",
            "origin": record_origin,
            "distribution": "pytest",
            "version": version,
            "sha256": record_sha256,
            "modules": ["pytest"],
        },
    ]
    framework = bound_pytest_environment(report, origins, {"pytest": {version}})
    declared = {"HOME": "/fixture/home", "LANG": "C"}
    startup = {**declared, "PROFILE_PROBE_MARKER": "independently-derived"}
    effective = {**startup, **framework}
    reconciled = reconcile_effective_collection_environment(declared, startup, framework, effective)
    cases = {
        "complete-declared-startup-and-bound-framework-transition": (
            reconciled["effective"] == effective
            and reconciled["framework"] == {"PYTEST_VERSION": version}
        ),
        "unowned-key-added-with-source-roles-unchanged-rejected": False,
        "declared-value-changed-rejected": False,
        "startup-addition-removed-with-profile-marker-unchanged-rejected": False,
        "startup-addition-changed-with-profile-marker-unchanged-rejected": False,
        "framework-version-marker-changed-rejected": False,
        "malformed-environment-value-rejected": False,
        "startup-and-framework-role-overlap-rejected": False,
        "pytest-self-reported-version-without-matching-locked-origin-rejected": False,
        "pytest-origin-changed-with-version-marker-unchanged-rejected": False,
        "pytest-record-claim-changed-with-version-marker-unchanged-rejected": False,
        "pytest-origin-without-matching-record-binding-rejected": False,
        "pytest-record-digest-mismatch-with-version-marker-unchanged-rejected": False,
    }

    def rejected(operation: Callable[[], object]) -> bool:
        try:
            operation()
        except AuditFailure:
            return True
        return False

    unexpected = {**effective, "UNDECLARED_PROFILE_VALUE": "candidate"}
    cases["unowned-key-added-with-source-roles-unchanged-rejected"] = rejected(
        lambda: reconcile_effective_collection_environment(declared, startup, framework, unexpected)
    )
    changed_declared = {**effective, "LANG": "changed"}
    cases["declared-value-changed-rejected"] = rejected(
        lambda: reconcile_effective_collection_environment(
            declared, startup, framework, changed_declared
        )
    )
    missing_startup = dict(effective)
    missing_startup.pop("PROFILE_PROBE_MARKER")
    cases["startup-addition-removed-with-profile-marker-unchanged-rejected"] = rejected(
        lambda: reconcile_effective_collection_environment(
            declared, startup, framework, missing_startup
        )
    )
    changed_startup = {**effective, "PROFILE_PROBE_MARKER": "different"}
    cases["startup-addition-changed-with-profile-marker-unchanged-rejected"] = rejected(
        lambda: reconcile_effective_collection_environment(
            declared, startup, framework, changed_startup
        )
    )
    changed_framework = {**effective, "PYTEST_VERSION": "9.0.3"}
    cases["framework-version-marker-changed-rejected"] = rejected(
        lambda: reconcile_effective_collection_environment(
            declared, startup, framework, changed_framework
        )
    )
    malformed_environment = {**effective, "LANG": 1}
    cases["malformed-environment-value-rejected"] = rejected(
        lambda: reconcile_effective_collection_environment(
            declared, startup, framework, malformed_environment
        )
    )
    overlapping_startup = {**startup, "PYTEST_VERSION": version}
    cases["startup-and-framework-role-overlap-rejected"] = rejected(
        lambda: reconcile_effective_collection_environment(
            declared, overlapping_startup, framework, effective
        )
    )
    false_version_report = copy.deepcopy(report)
    false_version_report["pytest"]["version"] = "9.0.3"
    cases["pytest-self-reported-version-without-matching-locked-origin-rejected"] = rejected(
        lambda: bound_pytest_environment(false_version_report, origins, {"pytest": {version}})
    )
    false_origin_report = copy.deepcopy(report)
    false_origin_report["pytest"]["origin"] = "/fixture/other/pytest/__init__.py"
    cases["pytest-origin-changed-with-version-marker-unchanged-rejected"] = rejected(
        lambda: bound_pytest_environment(false_origin_report, origins, {"pytest": {version}})
    )
    false_record_claim_report = copy.deepcopy(report)
    false_record_claim_report["module_origins"][0]["distribution"]["distribution_record_sha256"] = (
        "c" * 64
    )
    cases["pytest-record-claim-changed-with-version-marker-unchanged-rejected"] = rejected(
        lambda: bound_pytest_environment(false_record_claim_report, origins, {"pytest": {version}})
    )
    missing_record_origins = [origins[0]]
    cases["pytest-origin-without-matching-record-binding-rejected"] = rejected(
        lambda: bound_pytest_environment(report, missing_record_origins, {"pytest": {version}})
    )
    changed_record_origins = copy.deepcopy(origins)
    changed_record_origins[1]["sha256"] = "c" * 64
    cases["pytest-record-digest-mismatch-with-version-marker-unchanged-rejected"] = rejected(
        lambda: bound_pytest_environment(report, changed_record_origins, {"pytest": {version}})
    )
    failures = sorted(name for name, passed in cases.items() if not passed)
    if failures:
        raise AuditFailure(
            "effective environment self-test falsifier remained green: " + ", ".join(failures)
        )
    return cases


def self_test_record_origin_inventory() -> dict[str, bool]:
    """Exercise physical RECORD ownership and metadata-path boundary controls."""
    import tempfile
    import types

    sentinel = object()
    prior_pytest = sys.modules.get("pytest", sentinel)
    pytest_stub = types.ModuleType("pytest")
    pytest_stub.hookimpl = lambda **_kwargs: (lambda function: function)
    sys.modules["pytest"] = pytest_stub
    plugin_namespace: dict[str, Any] = {"__name__": "q2_source_freeze_capture_test"}
    try:
        exec(  # noqa: S102 -- executes only the exact owned capture source in an in-memory fixture.
            compile(COLLECTION_PLUGIN_SOURCE, "q2-source-freeze-capture", "exec"),
            plugin_namespace,
        )
    finally:
        if prior_pytest is sentinel:
            sys.modules.pop("pytest", None)
        else:
            sys.modules["pytest"] = prior_pytest

    capture_type = plugin_namespace["_CaptureMetadata"]
    distribution_for = plugin_namespace["_distribution_for"]
    namespace_distributions = plugin_namespace["_namespace_distributions"]
    module_data_digest = plugin_namespace["_module_data_digest"]
    plugin_module_identity = plugin_namespace["_plugin_module_identity"]

    def capture_for(site_root: Path) -> object:
        previous = sys.path[:]
        sys.path.insert(0, str(site_root))
        try:
            capture = capture_type([str(site_root)])
            capture.distribution_records()
            return capture
        finally:
            sys.path[:] = previous

    def make_record(
        info_dir: Path,
        name: str | None,
        version: str,
        claims: dict[str, bytes],
    ) -> tuple[Path, Path, bytes, bytes]:
        info_dir.mkdir(parents=True)
        metadata_lines = []
        if name is not None:
            metadata_lines.append(f"Name: {name}")
        metadata_lines.append(f"Version: {version}")
        metadata_bytes = ("\n".join(metadata_lines) + "\n\n").encode("utf-8")
        metadata_path = info_dir / "METADATA"
        metadata_path.write_bytes(metadata_bytes)
        root = info_dir.parent
        record_rows = []
        for relative, contents in sorted(claims.items()):
            safe_relative = safe_record_relative_path(relative)
            if safe_relative is not None:
                target = root / safe_relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(contents)
            digest = (
                base64.urlsafe_b64encode(hashlib.sha256(contents).digest())
                .decode("ascii")
                .rstrip("=")
            )
            record_rows.append((relative, f"sha256={digest}", str(len(contents))))
        record_rows.extend(
            [
                (f"{info_dir.name}/METADATA", "", ""),
                (f"{info_dir.name}/RECORD", "", ""),
            ]
        )
        output = io.StringIO(newline="")
        csv.writer(output).writerows(record_rows)
        record_bytes = output.getvalue().encode("utf-8")
        record_path = info_dir / "RECORD"
        record_path.write_bytes(record_bytes)
        return record_path, metadata_path, record_bytes, metadata_bytes

    cases: dict[str, bool] = {}
    plugin_module_name = "q2_plugin_class_origin_control"
    prior_plugin_module = sys.modules.get(plugin_module_name)
    plugin_module = types.ModuleType(plugin_module_name)
    plugin_class = type("Plugin", (), {})
    plugin_class.__module__ = plugin_module_name
    plugin_class.__qualname__ = "Plugin"
    plugin_class.__name__ = "LegacyTmpdirPlugin"
    plugin_module.Plugin = plugin_class
    sys.modules[plugin_module_name] = plugin_module

    def plugin_rejected(plugin: object) -> bool:
        try:
            plugin_module_identity(plugin)
        except RuntimeError:
            return True
        return False

    try:
        cases["plugin-class-object-uses-bound-class-module-not-class-name"] = (
            plugin_module_identity(plugin_class) == plugin_module_name
        )
        cases["plugin-instance-uses-bound-runtime-type-module"] = (
            plugin_module_identity(plugin_class()) == plugin_module_name
        )
        cases["plugin-module-object-reconciles-sysmodules-identity"] = (
            plugin_module_identity(plugin_module) == plugin_module_name
        )
        unbound_class = type("UnboundPlugin", (), {})
        unbound_class.__module__ = plugin_module_name
        unbound_class.__qualname__ = "UnboundPlugin"
        cases["plugin-class-self-label-without-module-object-binding-rejected"] = plugin_rejected(
            unbound_class
        )
        spoof_module = types.ModuleType("q2_plugin_module_spoof")
        spoof_module.__name__ = plugin_module_name
        sys.modules["q2_plugin_module_spoof"] = spoof_module
        cases["plugin-module-self-name-without-sysmodules-identity-rejected"] = plugin_rejected(
            spoof_module
        )
    finally:
        sys.modules.pop("q2_plugin_module_spoof", None)
        sys.modules.pop(plugin_module_name, None)
        if prior_plugin_module is not None:
            sys.modules[plugin_module_name] = prior_plugin_module

    typed_module = types.ModuleType("q2.runtime.data.control")
    typed_module.payload = {1: "integer-key", "1": "string-key", b"1": "bytes-key"}
    typed_digest = module_data_digest(typed_module)
    reordered_module = types.ModuleType("q2.runtime.data.control")
    reordered_module.payload = {b"1": "bytes-key", "1": "string-key", 1: "integer-key"}
    reordered_digest = module_data_digest(reordered_module)
    changed_module = types.ModuleType("q2.runtime.data.control")
    changed_module.payload = {1: "integer-key", "1": "changed", b"1": "bytes-key"}
    changed_digest = module_data_digest(changed_module)
    cases["runtime-data-digest-preserves-typed-keys-and-map-order"] = bool(
        typed_digest["supported"] is True
        and typed_digest["sha256"] == reordered_digest["sha256"]
        and typed_digest["sha256"] != changed_digest["sha256"]
    )
    unsupported_module = types.ModuleType("q2.runtime.data.control")
    unsupported_module.payload = object()
    cases["runtime-data-digest-fails-closed-on-object-values"] = (
        module_data_digest(unsupported_module)["supported"] is False
    )
    cyclic_module = types.ModuleType("q2.runtime.data.control")
    cyclic_value: list[Any] = []
    cyclic_value.append(cyclic_value)
    cyclic_module.payload = cyclic_value
    cases["runtime-data-digest-fails-closed-on-cycles"] = (
        module_data_digest(cyclic_module)["supported"] is False
    )
    with tempfile.TemporaryDirectory(prefix="q2-record-owner-") as scratch:
        root = Path(scratch)
        valid_site = root / "site-packages"
        valid_site.mkdir()
        module_bytes = b"one exact installed module\n"
        valid_info = valid_site / "pkg-1.0.dist-info"
        valid_record, valid_metadata, valid_record_bytes, valid_metadata_bytes = make_record(
            valid_info,
            "pkg",
            "1.0",
            {"pkg/module.py": module_bytes, "pkg/valid.py": b"x=1\n"},
        )
        data_record = valid_site / "data" / "RECORD"
        data_record.parent.mkdir()
        data_record.write_bytes(valid_record_bytes)
        module_path = valid_site / "pkg" / "module.py"
        valid_capture = capture_for(valid_site)
        valid_inventory, _valid_inventory_evidence = physical_record_claim_inventory(
            [valid_site], [valid_site]
        )
        valid_row = distribution_for("__main__", module_path, valid_capture)
        cases["canonical-metadata-record-positive"] = bool(
            valid_row
            and valid_row["record_path"] == str(valid_record)
            and valid_row["metadata_path"] == str(valid_metadata)
            and valid_row["dist_info_path"] == str(valid_info)
        )
        cases["data-record-equal-bytes-does-not-replace-metadata-record"] = bool(
            valid_row and data_record.read_bytes() == valid_record.read_bytes()
        )
        if valid_row is None:
            raise AuditFailure("canonical RECORD fixture did not identify its module owner")
        bound = locked_distribution_record(
            valid_row,
            {"pkg": {"1.0"}},
            [valid_site],
            "record-inventory positive control",
            record_cache={},
            record_rows_cache={},
            record_owner_inventory=valid_inventory,
            file_origin=module_path,
            file_bytes=module_bytes,
        )
        cases["metadata-and-record-bytes-reconciled"] = bool(
            bound.get("metadata_origin") == str(valid_metadata)
            and bound.get("metadata_sha256") == hashlib.sha256(valid_metadata_bytes).hexdigest()
        )
        forged_metadata_row = dict(valid_row)
        forged_metadata_row["metadata_path"] = str(data_record)
        forged_metadata_row["dist_info_path"] = str(data_record.parent)
        try:
            locked_distribution_record(
                forged_metadata_row,
                {"pkg": {"1.0"}},
                [valid_site],
                "counterfeit metadata path control",
                record_owner_inventory=valid_inventory,
                file_origin=module_path,
                file_bytes=module_bytes,
            )
        except AuditFailure:
            cases["counterfeit-metadata-path-with-equal-bytes-rejected"] = True
        else:
            cases["counterfeit-metadata-path-with-equal-bytes-rejected"] = False

        nameless_info = valid_site / "nameless-1.0.dist-info"
        make_record(nameless_info, None, "1.0", {"pkg/module.py": module_bytes})
        nameless_capture = capture_for(valid_site)
        cases["nameless-overlapping-claim-retained-and-fails-closed"] = (
            len(nameless_capture.distribution_records()) == 2
            and distribution_for("__main__", module_path, nameless_capture) is None
        )

        conflicting_info = valid_site / "shadow-9.0.dist-info"
        make_record(conflicting_info, "shadow", "9.0", {"pkg/module.py": module_bytes})
        conflict_capture = capture_for(valid_site)
        cases["duplicate-file-claim-from-distinct-records-rejected"] = (
            distribution_for("__main__", module_path, conflict_capture) is None
        )

        reentry_site = root / "reentry-fixture" / "site-packages"
        reentry_site.mkdir(parents=True)
        reentry_valid_info = reentry_site / "pkg-1.0.dist-info"
        make_record(
            reentry_valid_info,
            "pkg",
            "1.0",
            {"pkg/module.py": module_bytes, "pkg/valid.py": b"x=1\n"},
        )
        reentry_module_path = reentry_site / "pkg" / "module.py"
        reentry_namespace_path = reentry_site / "pkg"
        reentry_info = reentry_site / "shadow-2.0.dist-info"
        reentry_record, _reentry_metadata, _record_bytes, _metadata_bytes = make_record(
            reentry_info, "shadow", "2.0", {}
        )
        reentry_hash = (
            base64.urlsafe_b64encode(hashlib.sha256(module_bytes).digest())
            .decode("ascii")
            .rstrip("=")
        )
        reentry_rows = list(csv.reader(io.StringIO(reentry_record.read_text(encoding="utf-8"))))
        reentry_rows.append(
            ("../site-packages/pkg/module.py", f"sha256={reentry_hash}", str(len(module_bytes)))
        )
        reentry_output = io.StringIO(newline="")
        csv.writer(reentry_output).writerows(reentry_rows)
        reentry_record.write_text(reentry_output.getvalue(), encoding="utf-8")
        reentry_capture = capture_for(reentry_site)
        reentry_claims = [
            claim
            for snapshot in reentry_capture.distribution_records()
            for claim in snapshot["claims"].get(str(reentry_module_path), ())
        ]
        cases["physical-inventory-retains-valid-and-reentered-rows"] = (
            len(reentry_claims) == 2 and sum(claim["safe_path"] for claim in reentry_claims) == 1
        )
        cases["reentered-in-root-row-blocks-valid-owner"] = (
            distribution_for("__main__", reentry_module_path, reentry_capture) is None
        )
        cases["reentered-in-root-row-blocks-namespace-owner"] = (
            namespace_distributions(
                "sample_namespace", [str(reentry_namespace_path)], reentry_capture
            )
            == []
        )
        reentry_snapshots = reentry_capture.distribution_records()
        reentry_snapshot = next(
            snapshot for snapshot in reentry_snapshots if snapshot["dist_info_path"] == reentry_info
        )
        reentry_distribution = plugin_namespace["_distribution_result"](reentry_snapshot)
        reentry_valid_snapshot = next(
            snapshot
            for snapshot in reentry_snapshots
            if snapshot["dist_info_path"] == reentry_valid_info
        )
        reentry_valid_distribution = plugin_namespace["_distribution_result"](
            reentry_valid_snapshot
        )
        if reentry_distribution is None or reentry_valid_distribution is None:
            raise AuditFailure("re-entry fixture lost one canonical physical RECORD identity")
        reentry_distribution["record_hash_algorithm"] = "sha256"
        reentry_distribution["record_hash_value"] = reentry_hash
        reentry_valid_distribution["record_hash_algorithm"] = "sha256"
        reentry_valid_distribution["record_hash_value"] = reentry_hash
        reentry_inventory, _reentry_evidence = physical_record_claim_inventory(
            [reentry_site], [reentry_site]
        )
        cases["parent-inventory-retains-two-physical-owners"] = (
            len(reentry_inventory.get(str(reentry_module_path), [])) == 2
        )
        try:
            locked_distribution_record(
                reentry_valid_distribution,
                {"pkg": {"1.0"}},
                [reentry_site],
                "re-entry parent valid-row competitor control",
                record_owner_inventory=reentry_inventory,
                file_origin=reentry_module_path,
                file_bytes=module_bytes,
            )
        except AuditFailure:
            cases["parent-census-rejects-valid-row-with-reentered-competitor"] = True
        else:
            cases["parent-census-rejects-valid-row-with-reentered-competitor"] = False
        try:
            locked_distribution_record(
                reentry_distribution,
                {"shadow": {"2.0"}},
                [reentry_site],
                "re-entry parent module control",
                record_owner_inventory=reentry_inventory,
                file_origin=reentry_module_path,
                file_bytes=module_bytes,
            )
        except AuditFailure:
            cases["parent-census-rejects-reentered-competing-row"] = True
        else:
            cases["parent-census-rejects-reentered-competing-row"] = False
        try:
            locked_distribution_record(
                reentry_valid_distribution,
                {"pkg": {"1.0"}},
                [reentry_site],
                "re-entry parent namespace control",
                record_owner_inventory=reentry_inventory,
                namespace_location=reentry_namespace_path,
            )
        except AuditFailure:
            cases["parent-census-rejects-reentered-namespace-row"] = True
        else:
            cases["parent-census-rejects-reentered-namespace-row"] = False

        external_site = root / "venv" / "lib" / "python3.14" / "site-packages"
        external_site.mkdir(parents=True)
        external_bin = root / "venv" / "bin"
        external_bin.mkdir(parents=True)
        external_script = external_bin / "entrypoint"
        external_script_bytes = b"#!/usr/bin/env python3\n"
        external_script.write_bytes(external_script_bytes)
        external_info = external_site / "pkg-1.0.dist-info"
        external_record, _external_metadata, _record_bytes, _metadata_bytes = make_record(
            external_info, "pkg", "1.0", {"pkg/module.py": module_bytes}
        )
        external_hash = (
            base64.urlsafe_b64encode(hashlib.sha256(external_script_bytes).digest())
            .decode("ascii")
            .rstrip("=")
        )
        external_rows = list(csv.reader(io.StringIO(external_record.read_text(encoding="utf-8"))))
        external_rows.append(
            ("../../../bin/entrypoint", f"sha256={external_hash}", str(len(external_script_bytes)))
        )
        external_output = io.StringIO(newline="")
        csv.writer(external_output).writerows(external_rows)
        external_record.write_text(external_output.getvalue(), encoding="utf-8")
        external_capture = capture_for(external_site)
        external_owner = distribution_for(
            "__main__", external_site / "pkg" / "module.py", external_capture
        )
        external_inventory, _external_evidence = physical_record_claim_inventory(
            [external_site], [external_site]
        )
        external_rows_for_script = external_inventory.get(str(external_script), [])
        cases["external-installed-script-kept-outside-in-root-owner-set"] = bool(
            external_owner
            and external_rows_for_script
            and all(not row[3] for row in external_rows_for_script)
            and not external_script.is_relative_to(external_site)
        )
        if external_owner is not None:
            external_owner["record_hash_algorithm"] = "sha256"
            external_owner["record_hash_value"] = (
                base64.urlsafe_b64encode(hashlib.sha256(module_bytes).digest())
                .decode("ascii")
                .rstrip("=")
            )
            try:
                locked_distribution_record(
                    external_owner,
                    {"pkg": {"1.0"}},
                    [external_site],
                    "external installed script parent control",
                    record_owner_inventory=external_inventory,
                    file_origin=external_site / "pkg" / "module.py",
                    file_bytes=module_bytes,
                )
            except AuditFailure:
                cases["parent-preserves-external-script-with-in-root-module"] = False
            else:
                cases["parent-preserves-external-script-with-in-root-module"] = True
        else:
            cases["parent-preserves-external-script-with-in-root-module"] = False

        namespace_path = valid_site / "pkg"
        valid_namespace = namespace_distributions(
            "sample_namespace", [str(namespace_path)], valid_capture
        )
        cases["namespace-component-containment-positive"] = bool(
            len(valid_namespace) == 1
            and valid_namespace[0]["search_locations"] == [str(namespace_path)]
        )

        counterfeit_site = root / "counterfeit-site"
        counterfeit_site.mkdir()
        counterfeit_info = counterfeit_site / "pkg-1.0.dist-info"
        make_record(counterfeit_info, "impostor", "1.0", {"pkg/module.py": module_bytes})
        counterfeit_module = counterfeit_site / "pkg" / "module.py"
        counterfeit_capture = capture_for(counterfeit_site)
        cases["counterfeit-metadata-name-keeps-claim-but-is-not-an-owner"] = (
            len(counterfeit_capture.distribution_records()) == 1
            and distribution_for("__main__", counterfeit_module, counterfeit_capture) is None
        )

        data_only_site = root / "data-only-site"
        data_only_site.mkdir()
        data_only_info = data_only_site / "pkg-1.0.dist-info"
        data_only_info.mkdir()
        (data_only_info / "METADATA").write_bytes(b"Name: pkg\nVersion: 1.0\n\n")
        data_only_module = data_only_site / "pkg" / "module.py"
        data_only_module.parent.mkdir()
        data_only_module.write_bytes(module_bytes)
        data_only_record = data_only_site / "data" / "RECORD"
        data_only_record.parent.mkdir()
        data_only_record.write_bytes(valid_record_bytes)
        data_only_capture = capture_for(data_only_site)
        cases["noncanonical-data-record-alone-cannot-own-module"] = (
            distribution_for("__main__", data_only_module, data_only_capture) is None
        )

        invalid_site = root / "invalid-site"
        invalid_site.mkdir()
        invalid_info = invalid_site / "pkg-1.0.dist-info"
        invalid_record, _invalid_metadata, _record_bytes, _metadata_bytes = make_record(
            invalid_info, "pkg", "1.0", {}
        )
        invalid_rows = list(csv.reader(io.StringIO(invalid_record.read_text(encoding="utf-8"))))
        invalid_rows.append(("/etc/passwd", "", ""))
        invalid_output = io.StringIO(newline="")
        csv.writer(invalid_output).writerows(invalid_rows)
        invalid_record.write_text(invalid_output.getvalue(), encoding="utf-8")
        try:
            capture_for(invalid_site)
        except RuntimeError:
            cases["child-rejects-unresolvable-absolute-record-row"] = True
        else:
            cases["child-rejects-unresolvable-absolute-record-row"] = False
        try:
            physical_record_claim_inventory([invalid_site], [invalid_site])
        except AuditFailure:
            cases["parent-rejects-unresolvable-absolute-record-row"] = True
        else:
            cases["parent-rejects-unresolvable-absolute-record-row"] = False

        traversal_site = root / "traversal-site"
        traversal_site.mkdir()
        traversal_info = traversal_site / "ns-1.0.dist-info"
        make_record(traversal_info, "ns", "1.0", {"pkg/../../outside.py": b"x=1\n"})
        traversal_capture = capture_for(traversal_site)
        cases["namespace-traversal-row-does-not-own-contained-directory"] = (
            namespace_distributions(
                "sample_namespace", [str(traversal_site / "pkg")], traversal_capture
            )
            == []
        )

    failures = sorted(name for name, passed in cases.items() if not passed)
    if failures:
        raise AuditFailure("canonical RECORD self-test failed: " + ", ".join(failures))
    return cases


def self_test() -> dict[str, Any]:
    """Exercise manifest drift controls without a repository, build, or test suite."""
    baseline = {"tests/unit/test_source.py::test_baseline"}
    selected = {"tests/unit/test_consumer.py::test_consumes_bound_artifact"}
    actual = baseline | selected
    expected_assets = [{"source": "x", "wheel": "pkg/_resources/x", "bytes": 1, "sha256": "a" * 64}]
    template: dict[str, Any] = {
        "current_primary_suite": {
            "selected_node_ids": sorted(actual),
            "selected_node_count": len(actual),
            "selected_node_ids_sha256": canonical_ids_sha256(actual),
        },
        "additional_installed_consumers": {
            "consumer": {
                "test_path": "tests/unit/test_consumer.py",
                "selectors": ["test_consumes_bound_artifact"],
            }
        },
        "candidate_baseline": {
            "force_include_count": len(expected_assets),
            "force_include_assets": expected_assets,
        },
    }
    # Prove the unmodified fixture is valid before any drift control runs.
    validate_recomputed_ids(template, actual, expected_assets)

    cases: dict[str, bool] = {
        "baseline-validates-before-drift": True,
        "force-include-count-derived-from-asset-list": (
            template["candidate_baseline"]["force_include_count"] == len(expected_assets)
        ),
    }
    junit_case = b"<testsuite><testcase classname='sample.test_module' name='case'/></testsuite>"
    cases["junit-ordinary-testcase-parsed"] = junit_testcase_attributes(junit_case) == [
        {"classname": "sample.test_module", "name": "case"}
    ]
    for control_name, payload in (
        (
            "junit-internal-doctype-rejected",
            b"<!DOCTYPE testsuite [<!ENTITY x 'expanded'>]>"
            b"<testsuite><testcase classname='x' name='&x;'/></testsuite>",
        ),
        (
            "junit-external-doctype-rejected",
            b"<!DOCTYPE testsuite SYSTEM 'file:///etc/passwd'>"
            b"<testsuite><testcase classname='x' name='case'/></testsuite>",
        ),
    ):
        try:
            junit_testcase_attributes(payload)
        except AuditFailure as error:
            cases[control_name] = "DOCTYPE" in str(error) or "external entities" in str(error)
        else:
            cases[control_name] = False
    if not all(
        cases[name]
        for name in (
            "junit-ordinary-testcase-parsed",
            "junit-internal-doctype-rejected",
            "junit-external-doctype-rejected",
        )
    ):
        raise AuditFailure("JUnit parser did not preserve cases and reject DTD/entity inputs")
    expanded_actual = actual | {
        "tests/unit/test_registry.py::test_registry[missing]",
        "tests/unit/test_registry.py::test_registry[unreadable]",
        "tests/unit/test_registry.py::test_registry[corrupt]",
    }
    expanded_manifest = copy.deepcopy(template)
    expanded_suite = expanded_manifest["current_primary_suite"]
    expanded_suite["selected_node_ids"] = sorted(expanded_actual)
    expanded_suite["selected_node_count"] = len(expanded_actual)
    expanded_suite["selected_node_ids_sha256"] = canonical_ids_sha256(expanded_actual)
    validate_recomputed_ids(expanded_manifest, expanded_actual, expected_assets)
    cases["count-derived-from-complete-variable-collection"] = expanded_suite[
        "selected_node_count"
    ] == len(expanded_actual) and len(expanded_actual) != len(actual)
    for name, expected_failure, mutate in (
        (
            "corrupt-count-mismatch",
            "selected_node_count does not equal the declared ID list length",
            lambda value: value["current_primary_suite"].update(
                selected_node_count=len(actual) + 1
            ),
        ),
        (
            "float-count-alias",
            "selected_node_count does not equal the declared ID list length",
            lambda value: value["current_primary_suite"].update(
                selected_node_count=float(len(actual))
            ),
        ),
        (
            "boolean-count-alias",
            "selected_node_count does not equal the declared ID list length",
            lambda value: value["current_primary_suite"].update(selected_node_count=True),
        ),
        (
            "string-count-alias",
            "selected_node_count does not equal the declared ID list length",
            lambda value: value["current_primary_suite"].update(
                selected_node_count=str(len(actual))
            ),
        ),
        (
            "negative-count",
            "selected_node_count does not equal the declared ID list length",
            lambda value: value["current_primary_suite"].update(selected_node_count=-1),
        ),
        (
            "corrupt-digest",
            "selected_node_ids_sha256 does not recompute from the ID list",
            lambda value: value["current_primary_suite"].update(selected_node_ids_sha256="0" * 64),
        ),
        # Keep the selector marker, but remove one independently collected ID.
        (
            "remove-selected-id-with-marker-preserved",
            "declared node IDs differ from actual source collection",
            lambda value: value["current_primary_suite"].update(
                selected_node_ids=sorted(baseline),
                selected_node_count=len(baseline),
                selected_node_ids_sha256=canonical_ids_sha256(baseline),
            ),
        ),
        (
            "force-include-count-mismatch",
            "manifest force-include resources differ from frozen hatch.toml and source bytes",
            lambda value: value["candidate_baseline"].update(
                force_include_count=len(expected_assets) + 1
            ),
        ),
        (
            "remove-config-derived-resource-with-map-preserved",
            "manifest force-include resources differ from frozen hatch.toml and source bytes",
            lambda value: value["candidate_baseline"].update(
                force_include_assets=[],
                force_include_count=len(expected_assets),
            ),
        ),
    ):
        candidate = copy.deepcopy(template)
        mutate(candidate)
        try:
            validate_recomputed_ids(candidate, actual, expected_assets)
        except AuditFailure as error:
            cases[name] = str(error).startswith(expected_failure)
        else:
            cases[name] = False
    if not all(cases.values()):
        raise AuditFailure(f"self-test failed to reject drift controls: {cases}")
    gate_source = (
        "from pathlib import Path\n"
        "HERE = Path(__file__).resolve().parent\n"
        'INSTALLED_ORIGIN_GATE_PATH = HERE / "installed_origin_gate_r4.py"\n'
        f'INSTALLED_ORIGIN_GATE_SHA256 = "{"a" * 64}"\n'
    ).encode()
    expected_gate_binding = (f"{HANDOFF_REL}/raw/installed_origin_gate_r4.py", "a" * 64)
    if installed_origin_gate_binding(gate_source) != expected_gate_binding:
        raise AuditFailure("runner origin-gate binding did not resolve exact literal inputs")
    try:
        installed_origin_gate_binding(gate_source.replace(("a" * 64).encode(), b"bad"))
    except AuditFailure:
        cases["malformed-runner-gate-digest-rejected"] = True
    else:
        cases["malformed-runner-gate-digest-rejected"] = False
    if not cases["malformed-runner-gate-digest-rejected"]:
        raise AuditFailure("source audit accepted a non-full runner gate digest")
    origin_controls = self_test_origin_gate_symlink()
    cases.update({f"installed-origin-{name}": passed for name, passed in origin_controls.items()})
    record_controls = self_test_record_origin_inventory()
    cases.update({f"record-owner-{name}": passed for name, passed in record_controls.items()})
    cases["outside-identical-byte-symlink-and-parent-traversal-origin-controls"] = all(
        origin_controls.values()
    )
    if not cases["outside-identical-byte-symlink-and-parent-traversal-origin-controls"]:
        raise AuditFailure(
            "installed-origin verifier failed a trusted-root alias or boundary control"
        )
    class_actual = {
        "tests/unit/test_supplemental.py::TestSupplemental::test_parameterized[a]",
        "tests/unit/test_supplemental.py::TestSupplemental::test_parameterized[b]",
        "tests/unit/test_supplemental.py::TestSupplemental::test_refusal",
    }
    class_resolved = selected_group_ids(
        {
            "test_path": "tests/unit/test_supplemental.py",
            "selectors": [
                "TestSupplemental::test_parameterized",
                "TestSupplemental::test_refusal",
            ],
        },
        class_actual,
    )
    cases["class-and-parameterized-node-id-resolution"] = class_resolved == class_actual
    if class_resolved != class_actual:
        raise AuditFailure("class-qualified parameterized node IDs did not resolve completely")

    supplemental_actual = {
        "tests/unit/test_supplemental.py::test_parameterized[a]",
        "tests/unit/test_supplemental.py::test_parameterized[b]",
    }
    supplemental_template = {
        "supplemental_suite": {
            "test_path": "tests/unit/test_supplemental.py",
            "selectors": ["test_parameterized"],
            "selected_node_ids": sorted(supplemental_actual),
            "expected_node_count": len(supplemental_actual),
            "selected_node_ids_sha256": canonical_ids_sha256(supplemental_actual),
        }
    }
    validate_supplemental_node_ids(supplemental_template, supplemental_actual)
    supplemental_removal = copy.deepcopy(supplemental_template)
    supplemental_removal["supplemental_suite"]["selected_node_ids"] = sorted(
        supplemental_actual - {"tests/unit/test_supplemental.py::test_parameterized[b]"}
    )
    supplemental_removal["supplemental_suite"]["expected_node_count"] = 1
    supplemental_removal["supplemental_suite"]["selected_node_ids_sha256"] = canonical_ids_sha256(
        supplemental_removal["supplemental_suite"]["selected_node_ids"]
    )
    try:
        validate_supplemental_node_ids(supplemental_removal, supplemental_actual)
    except AuditFailure:
        cases["supplemental-parameterized-id-removal-with-selector-preserved"] = True
    else:
        cases["supplemental-parameterized-id-removal-with-selector-preserved"] = False
    if not cases["supplemental-parameterized-id-removal-with-selector-preserved"]:
        raise AuditFailure("supplemental selector marker survived selected-node removal")
    profile_contract_control = profile_contract_is_supported(
        list(REVIEWED_PROFILE_NAMES), list(REVIEWED_PROFILE_NAMES), list(REVIEWED_PROFILE_NAMES)
    ) and not profile_contract_is_supported(
        list(REVIEWED_PROFILE_NAMES), ["source-wheel"], list(REVIEWED_PROFILE_NAMES)
    )
    if not profile_contract_control:
        raise AuditFailure("self-test failed to reject a divergent primary profile contract")
    environment_controls = self_test_environment_reconciliation()
    return {
        "status": "pass",
        "product_source_read": False,
        "pytest_collection": False,
        "build_or_install": False,
        "actual_node_ids": len(actual),
        "corrupt_field_and_marker_preserving_removal_controls": cases,
        "effective_environment_reconciliation_controls": environment_controls,
        "profile_contract_divergence_control": profile_contract_control,
    }


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).resolve(strict=True)
    product = repo / "policy-engine"
    python_argument = Path(args.python)
    if not python_argument.is_absolute():
        raise AuditFailure(f"collector Python launcher must be absolute: {args.python}")
    python = Path(os.path.abspath(python_argument))
    if not python.is_file() or not os.access(python, os.X_OK):
        raise AuditFailure(f"collector Python launcher is unavailable: {python}")
    if args.collection_timeout_seconds <= 0:
        raise AuditFailure("collection timeout must be positive and explicit")
    output = Path(args.output_root).resolve()
    if output.exists():
        raise AuditFailure(f"output directory already exists; preserve old receipts: {output}")
    git_profile = git_oracle_profile(repo)
    helper_record = bind_audit_helper(repo, args.source_sha)
    if helper_record["provenance"].get("kind") != "tracked_source_commit_blob":
        raise AuditFailure("only a helper committed in the selected source can produce a freeze")
    python_record = python_executable_record(python)
    require_frozen_checkout(repo, args.source_sha, args.source_tree)
    output.mkdir(parents=True, exist_ok=False)

    helper_sha = helper_record["sha256"]
    input_records, local_capsule_bytes = input_file_records(
        repo,
        args.source_sha,
        args.supplemental_manifest,
        args.supplemental_manifest_sha256,
        helper_record=helper_record,
        git_profile=git_profile,
    )
    supplemental_manifest_relative = input_records["supplemental_manifest_path"]
    supplemental_manifest_relative = (
        Path(supplemental_manifest_relative).relative_to(repo).as_posix()
    )

    original_manifest_bytes = read_commit_blob(repo, args.source_sha, MANIFEST_REL)
    manifest = parse_json(original_manifest_bytes, MANIFEST_REL)
    if (repo / MANIFEST_REL).read_bytes() != original_manifest_bytes:
        raise AuditFailure("working manifest bytes differ from frozen Git object")
    baseline_junit_relative = safe_relative(
        manifest["original_q2_suite"]["baseline_junit_path"]
    ).as_posix()
    baseline_junit_path = f"policy-engine/{baseline_junit_relative}"
    baseline_junit_oid, baseline_junit_bytes = commit_blob_record(
        repo, args.source_sha, baseline_junit_path
    )
    input_records["tracked_git_objects"][baseline_junit_path] = {
        "bytes": len(baseline_junit_bytes),
        "sha256": sha256(baseline_junit_bytes),
        "git_blob_oid": baseline_junit_oid,
        "provenance": {
            "kind": "tracked_source_commit_blob",
            "source_sha": args.source_sha,
        },
    }
    input_records["original_baseline_junit"] = {
        "path": baseline_junit_path,
        "bytes": len(baseline_junit_bytes),
        "sha256": sha256(baseline_junit_bytes),
        "git_blob_oid": baseline_junit_oid,
    }
    original = baseline_ids_from_junit(baseline_junit_bytes, manifest)
    if not exact_nonbool_count_matches(
        manifest["original_q2_suite"].get("baseline_case_count"), len(original)
    ):
        raise AuditFailure("baseline Q2 ID denominator does not equal its declared count")

    baseline_paths = manifest["original_q2_suite"]["test_paths"]
    if manifest["current_primary_suite"]["selection"]["baseline_paths"] != baseline_paths:
        raise AuditFailure("current primary baseline paths diverge from the original Q2 path set")
    baseline_ids, baseline_collection = collect_ids(
        repo=repo,
        source_sha=args.source_sha,
        python=python,
        product=product,
        selectors=baseline_paths,
        allowed_paths=set(baseline_paths),
        output_root=output,
        label="collect-primary-baseline",
        timeout_seconds=args.collection_timeout_seconds,
    )
    collection_records = [baseline_collection]
    if not original <= baseline_ids:
        raise AuditFailure(
            f"source collection lost original Q2 cases: {sorted(original - baseline_ids)}"
        )

    groups = manifest["additional_installed_consumers"]
    group_paths: dict[str, list[str]] = {}
    for group in groups.values():
        path = group["test_path"]
        if path in baseline_paths:
            raise AuditFailure(
                f"current runner cannot select a consumer twice across baseline/group: {path}"
            )
        group_paths.setdefault(path, []).extend(group["selectors"])
    extra_ids: set[str] = set()
    additional_collections = {}
    for index, (path, selectors) in enumerate(sorted(group_paths.items())):
        specs = [f"{path}::{selector}" for selector in selectors]
        collected, record = collect_ids(
            repo=repo,
            source_sha=args.source_sha,
            python=python,
            product=product,
            selectors=specs,
            allowed_paths={path},
            output_root=output,
            label=f"collect-primary-consumers-{index:02d}",
            timeout_seconds=args.collection_timeout_seconds,
        )
        path_group = [group for group in groups.values() if group["test_path"] == path]
        resolved: set[str] = set()
        for group in path_group:
            resolved.update(selected_group_ids(group, collected))
        if resolved != collected:
            raise AuditFailure(
                f"actual collection contains undeclared IDs for {path}: "
                f"{sorted(collected - resolved)}"
            )
        extra_ids.update(resolved)
        additional_collections[path] = record
        collection_records.append(record)

    primary_ids = baseline_ids | extra_ids
    if not primary_ids:
        raise AuditFailure("source-derived Q2 primary selector set is empty")
    if not original <= primary_ids:
        raise AuditFailure("source-derived primary selectors omit original Q2 cases")

    historical = set(original)
    for group_name in ("dependency_profile", "canonical_bridge_and_worker"):
        if group_name not in groups:
            raise AuditFailure(f"historical Q2 subset owner group is missing: {group_name}")
        historical.update(selected_group_ids(groups[group_name], extra_ids))
    if historical != set(original) | {
        node_id
        for node_id in extra_ids
        if node_id.split("::", 1)[0]
        in {
            groups["dependency_profile"]["test_path"],
            groups["canonical_bridge_and_worker"]["test_path"],
        }
    }:
        raise AuditFailure("historical Q2 subset resolution is inconsistent")
    historical_decl = manifest["current_primary_suite"]["historical_baseline_subset"]
    if not exact_nonbool_count_matches(
        historical_decl.get("selected_node_count"), len(historical)
    ) or historical_decl.get("selected_node_ids_sha256") != canonical_ids_sha256(historical):
        raise AuditFailure(
            "historical 91-plus-nine subset does not recompute from its original "
            "baseline and named groups"
        )
    if not historical <= primary_ids:
        raise AuditFailure(
            "source-derived primary suite does not retain the historical baseline subset"
        )

    supplemental_bytes = local_capsule_bytes[supplemental_manifest_relative]
    supplemental = parse_json(supplemental_bytes, supplemental_manifest_relative)
    supplemental_path = supplemental["supplemental_suite"]["test_path"]
    supplemental_selectors = supplemental["supplemental_suite"]["selectors"]
    if (
        supplemental["primary_inputs"]["required_profiles"]
        != manifest["required_outcome"]["profiles"]
    ):
        raise AuditFailure("primary and supplemental profile contracts differ")
    if supplemental_path in group_paths or supplemental_path in baseline_paths:
        raise AuditFailure("supplemental selection duplicates a primary module")
    supplement_specs = [f"{supplemental_path}::{selector}" for selector in supplemental_selectors]
    supplemental_collected, supplemental_collection = collect_ids(
        repo=repo,
        source_sha=args.source_sha,
        python=python,
        product=product,
        selectors=supplement_specs,
        allowed_paths={supplemental_path},
        output_root=output,
        label="collect-supplemental-consumers",
        timeout_seconds=args.collection_timeout_seconds,
    )
    collection_records.append(supplemental_collection)
    supplemental_group = {"test_path": supplemental_path, "selectors": supplemental_selectors}
    supplemental_ids = selected_group_ids(supplemental_group, supplemental_collected)
    if supplemental_ids != supplemental_collected:
        raise AuditFailure("supplemental collection includes an undeclared selector")
    direct_supplemental_ids = {
        f"{supplemental_path}::{selector}" for selector in supplemental_selectors
    }

    source_paths = sorted(set(baseline_paths) | set(group_paths))
    if set(manifest["current_primary_suite"]["source_file_sha256"]) != set(source_paths):
        raise AuditFailure(
            "manifest source digest paths do not equal the complete selected test module set"
        )
    source_hashes = {
        path: sha256(read_commit_blob(repo, args.source_sha, f"policy-engine/{path}"))
        for path in source_paths
    }
    supplement_test_sha = sha256(
        read_commit_blob(repo, args.source_sha, f"policy-engine/{supplemental_path}")
    )
    fixture_paths = groups["canonical_bridge_and_worker"].get("fixture_paths", {})
    fixture_file_records = {}
    for relative in sorted(set(fixture_paths.values())):
        data = read_commit_blob(repo, args.source_sha, f"policy-engine/{relative}")
        fixture_file_records[relative] = {"bytes": len(data), "sha256": sha256(data)}
    fixture_hashes = {relative: row["sha256"] for relative, row in fixture_file_records.items()}

    assets, asset_receipt = asset_rows_from_config(repo, args.source_sha, manifest)
    lock_and_build_paths = (
        HATCH_REL,
        APP_PROJECT_REL,
        APP_LOCK_REL,
        DOWHY_PROJECT_REL,
        DOWHY_LOCK_REL,
        DOWHY_PYTHON_REL,
        DOWHY_README_REL,
        GCP_PACKAGE_REL,
    )
    locked_inputs = {
        path: {"bytes": len(data), "sha256": sha256(data)}
        for path in lock_and_build_paths
        for data in [read_commit_blob(repo, args.source_sha, path)]
    }
    input_records["collection_source_inputs"] = {
        "original_baseline_junit": input_records["original_baseline_junit"],
        "original_baseline_test_paths": list(baseline_paths),
        "selected_primary_test_modules": source_hashes,
        "selected_supplemental_test_module": {
            supplemental_path: {
                "bytes": len(
                    read_commit_blob(repo, args.source_sha, f"policy-engine/{supplemental_path}")
                ),
                "sha256": supplement_test_sha,
            }
        },
        "transitive_fixture_paths": fixture_file_records,
        "force_include_archive_wheel_resources": assets,
        "lock_build_archive_inputs": locked_inputs,
    }

    proposed = copy.deepcopy(manifest)
    # candidate_baseline.source_sha/tree identify the historical asset candidate.
    # Keep them unchanged: putting this commit's SHA in its own tracked manifest
    # would make the commit identity self-referential. The actual freeze belongs
    # in this external audit receipt and in the caller's command parameters.
    proposed["candidate_baseline"]["force_include_count"] = len(assets)
    proposed["candidate_baseline"]["force_include_assets"] = assets
    suite = proposed["current_primary_suite"]
    suite["selected_node_ids"] = sorted(primary_ids)
    suite["selected_node_count"] = len(primary_ids)
    suite["selected_node_ids_sha256"] = canonical_ids_sha256(primary_ids)
    suite["source_file_sha256"] = source_hashes
    proposed_manifest_bytes = (json.dumps(proposed, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    proposed_manifest_sha = sha256(proposed_manifest_bytes)

    proposed_supplement = copy.deepcopy(supplemental)
    proposed_supplement["primary_inputs"]["manifest_sha256"] = proposed_manifest_sha
    proposed_supplement["primary_inputs"]["runner_sha256"] = sha256(
        read_commit_blob(repo, args.source_sha, RUNNER_REL)
    )
    proposed_supplement["primary_inputs"]["force_include_asset_count_per_profile"] = len(assets)
    proposed_supplement["supplemental_suite"]["test_sha256"] = supplement_test_sha
    proposed_supplement["supplemental_suite"]["expected_node_count"] = len(supplemental_ids)
    proposed_supplement["supplemental_suite"]["selected_node_ids"] = sorted(supplemental_ids)
    proposed_supplement["supplemental_suite"]["selected_node_ids_sha256"] = canonical_ids_sha256(
        supplemental_ids
    )
    validate_supplemental_node_ids(proposed_supplement, supplemental_ids)
    proposed_supplement_bytes = (
        json.dumps(proposed_supplement, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    proposed_supplement_sha = sha256(proposed_supplement_bytes)

    runner_bytes = read_commit_blob(repo, args.source_sha, RUNNER_REL)
    supplemental_runner_bytes = local_capsule_bytes[SUPPLEMENT_REL]
    primary_profile_names, supplemental_profile_names = profile_names_from_runner_sources(
        runner_bytes, supplemental_runner_bytes
    )
    timeout_bytes = read_commit_blob(repo, args.source_sha, TIMEOUT_REL)
    timeout_text = timeout_bytes.decode("utf-8")
    rebound_timeout, _ = rebind_timeout_driver(timeout_text, sha256(runner_bytes))
    timeout_patch = "".join(
        difflib.unified_diff(
            timeout_text.splitlines(keepends=True),
            rebound_timeout.splitlines(keepends=True),
            fromfile=TIMEOUT_REL,
            tofile=f"{TIMEOUT_REL} (rebound proposal)",
        )
    ).encode("utf-8")

    profiles = proposed["required_outcome"]["profiles"]
    runner_limitations = []
    direct_primary_ids = {
        f"{group['test_path']}::{selector}"
        for group in groups.values()
        for selector in group["selectors"]
    }
    primary_group_ids = {
        node_id for group in groups.values() for node_id in selected_group_ids(group, primary_ids)
    }
    primary_group_expansions = sorted(primary_group_ids - direct_primary_ids)
    if (
        tuple(profiles) != REVIEWED_PROFILE_NAMES
        or tuple(primary_profile_names) != REVIEWED_PROFILE_NAMES
        or tuple(supplemental_profile_names) != REVIEWED_PROFILE_NAMES
    ):
        runner_limitations.append(
            "primary runner, supplemental runner, and manifest do not share the "
            "reviewed three-profile contract"
        )
    profile_case_count = len(profiles) * (len(primary_ids) + len(supplemental_ids))

    # Run the existing AST/fixture binding verifier on the source-derived proposal.
    import importlib.util

    runner_path = repo / RUNNER_REL
    actual_runner_sha = sha256(read_commit_blob(repo, args.source_sha, RUNNER_REL))
    if sha256(read_regular_local(runner_path)) != actual_runner_sha:
        raise AuditFailure("working runner differs from its frozen Git object")
    spec = importlib.util.spec_from_file_location("q2_source_audit_existing_runner", runner_path)
    if spec is None or spec.loader is None:
        raise AuditFailure("cannot import existing Q2 source verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_ids = module.baseline_node_ids(product, proposed)
    transitive = None
    transitive = module.verify_transitive_test_bindings(product, proposed, original_ids)

    collection_origins_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for collection in collection_records:
        origins = collection.get("loaded_module_origins")
        if not isinstance(origins, list):
            raise AuditFailure("one collection pass omitted its loaded-origin inventory")
        for origin in origins:
            if not isinstance(origin, dict):
                raise AuditFailure("collection origin inventory contains a malformed row")
            key = (
                str(origin.get("kind")),
                str(origin.get("origin")),
                str(origin.get("sha256")),
                str(origin.get("git_blob_oid")),
            )
            collection_origins_by_key.setdefault(key, origin)
    collection_origins = list(collection_origins_by_key.values())
    recheck_collection_origins(collection_origins)
    if python_executable_record(python) != python_record:
        raise AuditFailure("collector Python executable changed during the complete source audit")
    if bind_audit_helper(repo, args.source_sha) != helper_record:
        raise AuditFailure("canonical source audit helper changed during collection")
    if git_oracle_profile(repo) != git_profile:
        raise AuditFailure(
            "trusted Git executable or effective environment changed during collection"
        )
    require_frozen_checkout(repo, args.source_sha, args.source_tree)

    current_manifest_pin = sha256(original_manifest_bytes)
    current_supplement_pin = sha256(supplemental_bytes)
    current_supp_manifest = parse_json(supplemental_bytes, supplemental_manifest_relative)
    expected_timeout_values = {"runner_sha256": actual_runner_sha}
    timeout_mismatches = []
    for _key, expected in expected_timeout_values.items():
        constant = "EXPECTED_RUNNER_SHA256"
        try:
            rebound_timeout_text, _ = rebind_timeout_driver(timeout_text, expected)
        except AuditFailure:
            timeout_mismatches.append(constant)
        else:
            if rebound_timeout_text != timeout_text:
                timeout_mismatches.append(constant)
    supplement_mismatches = []
    for key, expected in (
        ("runner_sha256", actual_runner_sha),
        ("manifest_sha256", proposed_manifest_sha),
        ("required_profiles", profiles),
    ):
        if not json_values_match_exactly(
            current_supp_manifest["primary_inputs"].get(key), expected
        ):
            supplement_mismatches.append(key)
    supplement_mismatches.extend(
        supplemental_manifest_count_mismatches(
            current_supp_manifest,
            asset_count=len(assets),
            supplemental_id_count=len(supplemental_ids),
        )
    )
    if current_supp_manifest["supplemental_suite"].get("test_sha256") != supplement_test_sha:
        supplement_mismatches.append("supplemental_suite.test_sha256")
    if current_supp_manifest["supplemental_suite"].get("selected_node_ids") != sorted(
        supplemental_ids
    ):
        supplement_mismatches.append("supplemental_suite.selected_node_ids")
    if current_supp_manifest["supplemental_suite"].get(
        "selected_node_ids_sha256"
    ) != canonical_ids_sha256(supplemental_ids):
        supplement_mismatches.append("supplemental_suite.selected_node_ids_sha256")

    receipt = {
        "schema_version": 1,
        "status": "source_collection_and_content_audit_only",
        "source_sha": args.source_sha,
        "source_tree": args.source_tree,
        "audit_helper_sha256": helper_sha,
        "repo": str(repo),
        "frozen_checkout_clean_tracked": True,
        "build_started": False,
        "install_started": False,
        "tests_executed": False,
        "pytest_collection_only": True,
        "primary": {
            "baseline_ids": len(baseline_ids),
            "original_q2_ids": len(original),
            "additional_ids": len(extra_ids),
            "source_derived_ids": len(primary_ids),
            "source_derived_node_ids": sorted(primary_ids),
            "source_derived_ids_sha256": canonical_ids_sha256(primary_ids),
            "manifest_ids_equal_source_collection": primary_manifest_matches_collection(
                manifest, primary_ids, assets, source_hashes
            ),
            "current_manifest_sha256": current_manifest_pin,
            "proposed_manifest_sha256": proposed_manifest_sha,
            "source_file_sha256": source_hashes,
            "baseline_collection": baseline_collection,
            "additional_collections": additional_collections,
        },
        "supplemental": {
            "source_derived_ids": len(supplemental_ids),
            "source_derived_node_ids": sorted(supplemental_ids),
            "source_derived_ids_sha256": canonical_ids_sha256(supplemental_ids),
            "current_manifest_sha256": current_supplement_pin,
            "proposed_manifest_sha256": proposed_supplement_sha,
            "test_sha256": supplement_test_sha,
            "collection": supplemental_collection,
        },
        "profiles": profiles,
        "primary_runner_profile_names": primary_profile_names,
        "supplemental_runner_profile_names": supplemental_profile_names,
        "source_derived_profile_case_count": profile_case_count,
        "reviewed_route_count_comparison": {
            "primary_source_collection": len(primary_ids),
            "primary_manifest_ids": len(proposed["current_primary_suite"]["selected_node_ids"]),
            "primary_collection_matches_manifest": set(
                proposed["current_primary_suite"]["selected_node_ids"]
            )
            == primary_ids,
            "supplemental_source_collection": len(supplemental_ids),
            "supplemental_manifest_ids": len(
                proposed_supplement["supplemental_suite"]["selected_node_ids"]
            ),
            "supplemental_collection_matches_manifest": set(
                proposed_supplement["supplemental_suite"]["selected_node_ids"]
            )
            == supplemental_ids,
            "required_profiles": list(profiles),
            "profile_cases_from_source_counts": profile_case_count,
            "is_acceptance": False,
        },
        "runner_limitations": sorted(set(runner_limitations)),
        "primary_selector_expansions": primary_group_expansions,
        "supplemental_selector_expansion_detected": supplemental_ids != direct_supplemental_ids,
        "count_is_not_runtime_acceptance": True,
        "primary_selection_finality": "FINAL_SOURCE_REQUIRED",
        "resource_config": asset_receipt,
        "transitive_fixture_sha256": fixture_hashes,
        "lock_build_and_archive_inputs": locked_inputs,
        "source_freeze_input_capsule": input_records,
        "source_collection_input_closure": {
            "collection_passes": len(collection_records),
            "unique_loaded_origin_records": len(collection_origins),
            "direct_source_path_lease_count": len(input_records["direct_source_path_lease"]),
            "selected_primary_test_module_count": len(source_hashes),
            "selected_supplemental_test_module_path": supplemental_path,
            "transitive_fixture_path_count": len(fixture_file_records),
            "force_include_resource_count": len(assets),
            "locked_build_archive_input_count": len(locked_inputs),
            "original_baseline_test_path_count": len(baseline_paths),
            "original_baseline_test_paths": list(baseline_paths),
            "loaded_origin_files_rechecked_after_all_passes": True,
            "canonical_helper_rechecked": True,
            "trusted_git_profile_rechecked": True,
            "collector_python_rechecked": True,
            "frozen_source_head_and_tracked_worktree_rechecked": True,
        },
        "timeout_driver_stale_constants": timeout_mismatches,
        "supplement_manifest_stale_fields": supplement_mismatches,
        "existing_runner_static_transitive_binding": transitive,
        "required_runtime_followup": [
            (
                "Only the actual frozen installed wheel, rebuilt sdist wheel, and rebuilt "
                "archive wheel waves can establish consumer behavior and installed origins."
            ),
            (
                "Every profile must reconcile complete collected IDs to JUnit and zero "
                "skips/failures/errors, then verify all source/archive/wheel/installed "
                "resource bytes."
            ),
            "The source collection here is not installed-package evidence or G adjudication.",
        ],
    }
    current_mismatches = manifest_mismatches(
        manifest, proposed, original_manifest_bytes, proposed_manifest_bytes
    )
    receipt["manifest_rebind_fields_needed"] = current_mismatches
    receipt["source_object_and_actual_collection_reconcile"] = (
        primary_manifest_matches_collection(manifest, primary_ids, assets, source_hashes)
        and not current_mismatches
    )
    receipt["capsule_bindings_current"] = not timeout_mismatches and not supplement_mismatches

    collection_records = [
        baseline_collection,
        *additional_collections.values(),
        supplemental_collection,
    ]
    for collection in collection_records:
        recheck_collection_origins(collection["loaded_module_origins"])
    if python_executable_record(python) != python_record:
        raise AuditFailure("collector Python executable changed during the source audit")
    if bind_audit_helper(repo, args.source_sha) != helper_record:
        raise AuditFailure("canonical Q2 audit helper changed or lost its Git binding")
    if git_oracle_profile(repo) != git_profile:
        raise AuditFailure(
            "trusted Git executable or effective environment changed during the audit"
        )
    final_input_records, _ = input_file_records(
        repo,
        args.source_sha,
        args.supplemental_manifest,
        args.supplemental_manifest_sha256,
        helper_record=helper_record,
        git_profile=git_profile,
    )
    if final_input_records != input_records:
        raise AuditFailure("one or more source-freeze audit inputs changed during collection")

    (output / "proposed-installed-wave-manifest.json").write_bytes(proposed_manifest_bytes)
    (output / "proposed-supplemental-manifest.json").write_bytes(proposed_supplement_bytes)
    (output / "proposed-timeout-driver.patch").write_bytes(timeout_patch)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test", help="run lightweight in-memory drift controls")
    for command in ("prepare", "check"):
        sub = subparsers.add_parser(
            command, help="collect source IDs and rebind source-object inputs"
        )
        sub.add_argument("--repo", required=True, help="attached source checkout root")
        sub.add_argument("--source-sha", required=True, help="full final commit SHA")
        sub.add_argument("--source-tree", required=True, help="full final tree SHA")
        sub.add_argument(
            "--python",
            required=True,
            help="absolute existing Python with pytest and locked test dependencies",
        )
        sub.add_argument(
            "--collection-timeout-seconds",
            type=float,
            required=True,
            help="measured/approved collect-only timeout",
        )
        sub.add_argument(
            "--output-root", required=True, help="new absent ignored raw output directory"
        )
        sub.add_argument(
            "--supplemental-manifest",
            required=True,
            help="absolute ignored versioned supplement manifest path",
        )
        sub.add_argument(
            "--supplemental-manifest-sha256",
            required=True,
            help="exact supplement manifest SHA-256",
        )
    args = parser.parse_args()
    if args.command == "self-test":
        sys.stdout.write(json.dumps(self_test(), indent=2, sort_keys=True) + "\n")
        return 0
    output = Path(args.output_root).resolve()
    output_was_present = output.exists()
    try:
        receipt = run_audit(args)
        (output / "source-input-audit.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        exact = (
            receipt["source_object_and_actual_collection_reconcile"]
            and receipt["capsule_bindings_current"]
            and not receipt["runner_limitations"]
        )
        receipt_status = "source_preflight_exact" if exact else "source_preflight_rebind_required"
        receipt["status"] = receipt_status
        (output / "source-input-audit.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        success_summary = json.dumps(
            {
                "status": receipt_status,
                "source_sha": args.source_sha,
                "source_tree": args.source_tree,
                "primary_ids": receipt["primary"]["source_derived_ids"],
                "supplemental_ids": receipt["supplemental"]["source_derived_ids"],
                "profile_cases": receipt["source_derived_profile_case_count"],
                "outputs": str(output),
            },
            sort_keys=True,
        )
        sys.stdout.write(success_summary + "\n")
        return 0 if args.command == "prepare" or exact else 1
    except (
        AuditFailure,
        OSError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        subprocess.SubprocessError,
    ) as error:
        if output_was_present:
            sys.stderr.write(
                "Q2 source input audit refused existing output directory without changing "
                f"it: {output}\n"
            )
            return 2
        output.mkdir(parents=True, exist_ok=True)
        failure = {
            "status": "source_preflight_error",
            "source_sha": getattr(args, "source_sha", None),
            "source_tree": getattr(args, "source_tree", None),
            "build_started": False,
            "install_started": False,
            "tests_executed": False,
            "error": f"{type(error).__name__}: {error}",
        }
        (output / "source-input-audit.json").write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sys.stderr.write(f"Q2 source input audit failed before any build: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
