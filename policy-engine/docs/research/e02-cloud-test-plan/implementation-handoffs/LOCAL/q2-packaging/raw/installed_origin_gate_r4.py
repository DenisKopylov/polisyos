from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any


class InstalledOriginError(ValueError):
    """The installed resource or frozen builder input violates its path/content binding."""


def _parts(value: object, *, label: str, allow_parent: bool = False) -> tuple[str, ...]:
    if type(value) is not str or not value or "\\" in value:
        raise InstalledOriginError(f"{label} is not a canonical POSIX path")
    parsed = PurePosixPath(value)
    forbidden = {"", "."} | (set() if allow_parent else {".."})
    if (
        parsed.is_absolute()
        or parsed.as_posix() != value
        or any(part in forbidden for part in parsed.parts)
    ):
        raise InstalledOriginError(f"{label} is not a canonical relative path: {value!r}")
    return parsed.parts


def _inside(root: Path, candidate: Path, label: str) -> Path:
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise InstalledOriginError(
            f"{label} is missing, cyclic, or outside its verified root"
        ) from error
    if not (stat.S_ISREG(resolved.stat().st_mode) or stat.S_ISDIR(resolved.stat().st_mode)):
        raise InstalledOriginError(f"{label} resolves to a special filesystem object")
    return resolved


def _module_path(
    reported_root: Path,
    canonical_root: Path,
    raw_path: object,
    label: str,
    *,
    directory: bool = False,
) -> tuple[Path, Path]:
    """Bind a reported path to a trusted root spelling and canonical object."""
    if type(raw_path) is not str or not raw_path:
        raise InstalledOriginError(f"{label} has no absolute filesystem path")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        raise InstalledOriginError(f"{label} is not absolute: {raw_path!r}")
    try:
        if ".." in candidate.parts:
            raise ValueError("reported path contains a parent path segment")
        lexical = candidate
        if not (lexical.is_relative_to(reported_root) or lexical.is_relative_to(canonical_root)):
            raise ValueError("reported path is outside both trusted root spellings")
        resolved = lexical.resolve(strict=True)
        resolved.relative_to(canonical_root)
        observed = resolved.stat()
    except (OSError, RuntimeError, ValueError) as error:
        raise InstalledOriginError(
            f"{label} is missing or its reported/resolved path escapes installed purelib"
        ) from error
    if directory:
        if not stat.S_ISDIR(observed.st_mode):
            raise InstalledOriginError(f"{label} is not a directory")
    elif not stat.S_ISREG(observed.st_mode):
        raise InstalledOriginError(f"{label} is not a regular file")
    return lexical, resolved


def _is_q2_origin_subject(name: object) -> bool:
    """Select all loaded PolicyOS/tools modules plus the runner gate/plugin."""
    if type(name) is not str:
        return False
    return (
        name == "polisyos"
        or name.startswith("polisyos.")
        or name == "tools"
        or name.startswith("tools.")
        or name in {"q2_installed_origin_gate", "q2_installed_origin_plugin"}
    )


def _module_origin_row(
    reported_root: Path, canonical_root: Path, name: str, module: object
) -> dict[str, Any]:
    spec = getattr(module, "__spec__", None)
    module_file = getattr(module, "__file__", None)
    if module_file is not None:
        file_path, resolved_file = _module_path(
            reported_root, canonical_root, module_file, f"module {name} __file__"
        )
        spec_origin = getattr(spec, "origin", None)
        if type(spec_origin) is not str or spec_origin in {"built-in", "frozen"}:
            raise InstalledOriginError(f"module {name} has no file-backed import spec")
        spec_path, resolved_spec = _module_path(
            reported_root, canonical_root, spec_origin, f"module {name} spec.origin"
        )
        try:
            same_loaded_file = os.path.samefile(file_path, spec_path)
        except OSError as error:
            raise InstalledOriginError(
                f"module {name} import identity cannot be compared"
            ) from error
        if not same_loaded_file:
            raise InstalledOriginError(
                f"module {name} __file__ and spec.origin name different file objects"
            )
        return {
            "file": str(file_path),
            "resolved_file": str(resolved_file),
            "spec_origin": str(spec_path),
            "resolved_spec_origin": str(resolved_spec),
        }
    locations = tuple(getattr(spec, "submodule_search_locations", ()) or ())
    if locations:
        bound = []
        for index, location in enumerate(locations):
            lexical, resolved = _module_path(
                reported_root,
                canonical_root,
                location,
                f"namespace module {name} search location {index}",
                directory=True,
            )
            bound.append({"path": str(lexical), "resolved_path": str(resolved)})
        return {"namespace_locations": bound}
    raise InstalledOriginError(f"module {name} has no inspectable file or namespace origin")


def verify_loaded_module_origins(
    purelib: str | Path, modules: object
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    """Check all Q2-managed loaded module origins by path and resolved file identity."""
    reported_root = Path(purelib)
    if not reported_root.is_absolute() or ".." in reported_root.parts:
        raise InstalledOriginError(
            "installed purelib reported path must be absolute and contain no parent segment"
        )
    try:
        canonical_root = reported_root.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise InstalledOriginError("installed purelib is missing or cyclic") from error
    if not canonical_root.is_dir():
        raise InstalledOriginError("installed purelib is not a directory")
    if type(modules) is not dict:
        return {}, [{"reason": "loaded module inventory is not a dict"}]
    subjects = {name: module for name, module in modules.items() if _is_q2_origin_subject(name)}
    if not subjects:
        return {}, [{"reason": "no Q2-managed module origin was observed"}]
    origins: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    for name, module in sorted(subjects.items()):
        try:
            origins[name] = _module_origin_row(reported_root, canonical_root, name, module)
        except InstalledOriginError as error:
            errors.append({"module": name, "reason": str(error)})
    return origins, errors


def verify_installed_resources(
    purelib: str | Path, expected_assets: object, reader_paths: object
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    (
        """Verify the complete declared asset mapping and actual canonical reader paths """
        """under purelib."""
    )
    root = Path(purelib).resolve(strict=True)
    if (
        not root.is_dir()
        or type(expected_assets) is not dict
        or not expected_assets
        or type(reader_paths) is not dict
        or not reader_paths
    ):
        raise InstalledOriginError(
            "purelib, complete assets, and canonical reader paths are required"
        )
    rows: dict[str, dict[str, Any]] = {}
    for target, expected in expected_assets.items():
        parts = _parts(target, label="asset target")
        if type(expected) is not dict:
            raise InstalledOriginError(f"asset expectation is not an object: {target}")
        count, digest = expected.get("bytes"), expected.get("sha256")
        if (
            type(count) is not int
            or count < 0
            or type(digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise InstalledOriginError(f"asset expectation is malformed: {target}")
        path = _inside(root, root.joinpath(*parts), f"asset {target}")
        if not stat.S_ISREG(path.stat().st_mode):
            raise InstalledOriginError(f"asset is not a regular file: {target}")
        data = path.read_bytes()
        observed = hashlib.sha256(data).hexdigest()
        if len(data) != count or observed != digest:
            raise InstalledOriginError(f"asset bytes differ from the frozen expectation: {target}")
        rows[target] = {
            "bytes": len(data),
            "sha256": observed,
            "installed_path": str(path),
        }
    readers: dict[str, str] = {}
    for label, raw_path in reader_paths.items():
        if type(label) is not str or not label or not isinstance(raw_path, (str, Path)):
            raise InstalledOriginError("canonical reader labels and paths must be nonempty")
        readers[label] = str(_inside(root, Path(raw_path), f"canonical reader {label}"))
    return rows, readers


def verify_hatchling_distribution(
    site: str | Path,
    environment_prefix: str | Path,
    inventory_path: str | Path,
    inventory_sha256: str,
) -> dict[str, Any]:
    """Bind all Hatchling RECORD files and its console script to the frozen app-venv snapshot."""
    site_root, prefix = (
        Path(site).resolve(strict=True),
        Path(environment_prefix).resolve(strict=True),
    )
    try:
        site_rel = site_root.relative_to(prefix).as_posix()
    except ValueError as error:
        raise InstalledOriginError("builder dependency site lies outside app venv") from error
    raw = Path(inventory_path).read_bytes()
    observed_inventory = hashlib.sha256(raw).hexdigest()
    if observed_inventory != inventory_sha256:
        raise InstalledOriginError("builder inventory differs from its frozen hash")
    inv = json.loads(raw)
    if type(inv) is not dict or (
        inv.get("schema"),
        inv.get("name"),
        inv.get("version"),
        inv.get("installer"),
        inv.get("site_relative_to_app_venv"),
    ) != ("e02.q2.hatchling_installed_input.r3", "hatchling", "1.27.0", "uv", site_rel):
        raise InstalledOriginError("builder identity or app site differs from inventory")
    cfg = _inside(prefix, prefix / "pyvenv.cfg", "app venv config")
    if hashlib.sha256(cfg.read_bytes()).hexdigest() != inv.get("app_venv_pyvenv_cfg_sha256"):
        raise InstalledOriginError("app venv config differs from frozen builder input")
    files = inv.get("files")
    if type(files) is not list or not files:
        raise InstalledOriginError("builder inventory has no complete RECORD file set")
    by_record: dict[str, dict[str, Any]] = {}
    by_prefix: set[str] = set()
    for row in files:
        if type(row) is not dict:
            raise InstalledOriginError("builder inventory row is malformed")
        record_parts = _parts(row.get("record_path"), label="RECORD path", allow_parent=True)
        prefix_parts = _parts(row.get("prefix_path"), label="app prefix path")
        rec, pref = (
            PurePosixPath(*record_parts).as_posix(),
            PurePosixPath(*prefix_parts).as_posix(),
        )
        if rec in by_record or pref in by_prefix:
            raise InstalledOriginError(f"builder inventory has duplicate file path: {rec}")
        if (
            type(row.get("bytes")) is not int
            or row["bytes"] < 0
            or type(row.get("sha256")) is not str
            or re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None
        ):
            raise InstalledOriginError(f"builder file hash/size is malformed: {rec}")
        by_record[rec] = row
        by_prefix.add(pref)
    dist = _inside(site_root, site_root / "hatchling-1.27.0.dist-info", "Hatchling dist-info")
    if not stat.S_ISDIR(dist.stat().st_mode):
        raise InstalledOriginError("Hatchling dist-info is not a directory")
    record_rel = "hatchling-1.27.0.dist-info/RECORD"
    if record_rel not in by_record:
        raise InstalledOriginError("Hatchling RECORD missing from input inventory")
    record_real = _inside(site_root, site_root / record_rel, "Hatchling RECORD")
    record_bytes = record_real.read_bytes()
    if hashlib.sha256(record_bytes).hexdigest() != by_record[record_rel]["sha256"]:
        raise InstalledOriginError("installed Hatchling RECORD changed")
    try:
        rows = list(csv.reader(record_bytes.decode("utf-8").splitlines()))
    except (UnicodeDecodeError, csv.Error) as error:
        raise InstalledOriginError("installed Hatchling RECORD is malformed") from error
    names: set[str] = set()
    for row in rows:
        if len(row) != 3:
            raise InstalledOriginError("installed Hatchling RECORD row is malformed")
        rel, record_hash, record_size = row
        rel = PurePosixPath(
            *_parts(rel, label="Hatchling RECORD path", allow_parent=True)
        ).as_posix()
        if rel in names or rel not in by_record:
            raise InstalledOriginError(f"RECORD row duplicate or absent from inventory: {rel}")
        names.add(rel)
        expected = by_record[rel]
        if record_size and record_size != str(expected["bytes"]):
            raise InstalledOriginError(f"RECORD size differs from inventory: {rel}")
        if record_hash:
            algorithm, separator, value = record_hash.partition("=")
            wanted = (
                base64.urlsafe_b64encode(bytes.fromhex(expected["sha256"]))
                .rstrip(b"=")
                .decode("ascii")
            )
            if algorithm != "sha256" or not separator or value != wanted:
                raise InstalledOriginError(f"RECORD digest differs from inventory: {rel}")
        elif rel != record_rel or record_size:
            raise InstalledOriginError(f"only RECORD may omit self hash and size: {rel}")
    if names != set(by_record):
        raise InstalledOriginError("inventory file set does not equal RECORD file set")
    for rel, expected in by_record.items():
        path = _inside(
            prefix,
            site_root.joinpath(*PurePosixPath(rel).parts),
            f"Hatchling file {rel}",
        )
        bound = prefix.joinpath(*PurePosixPath(expected["prefix_path"]).parts).resolve(strict=True)
        if path != bound or not stat.S_ISREG(path.stat().st_mode):
            raise InstalledOriginError(f"Hatchling RECORD origin differs from inventory: {rel}")
        data = path.read_bytes()
        if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
            raise InstalledOriginError(f"installed Hatchling bytes changed: {rel}")
    metadata = (site_root / "hatchling-1.27.0.dist-info/METADATA").read_text(encoding="utf-8")
    installer = (
        (site_root / "hatchling-1.27.0.dist-info/INSTALLER").read_text(encoding="utf-8").strip()
    )
    if (
        "Name: hatchling\n" not in metadata
        or "Version: 1.27.0\n" not in metadata
        or installer != "uv"
    ):
        raise InstalledOriginError("Hatchling METADATA or installer identity differs")
    aggregate = hashlib.sha256(
        "".join(
            f"{r['record_path']}\0{r['bytes']}\0{r['sha256']}\n"
            for r in sorted(files, key=lambda x: x["record_path"])
        ).encode()
    ).hexdigest()
    if aggregate != inv.get("files_sha256"):
        raise InstalledOriginError("Hatchling aggregate differs from frozen inventory")
    return {
        "name": "hatchling",
        "version": "1.27.0",
        "origin": str(dist),
        "inventory_sha256": observed_inventory,
        "record_sha256": hashlib.sha256(record_bytes).hexdigest(),
        "file_count": len(files),
        "files_sha256": aggregate,
        "app_venv_pyvenv_cfg_sha256": inv["app_venv_pyvenv_cfg_sha256"],
        "provenance_limit": (
            "installed distribution snapshot only; upstream wheel/source origin not established"
        ),
    }
