"""Source-bound package inventory and split Q2 transport checks.

This RAW candidate derives wheel membership from the frozen Hatch configuration and
the existing Q2 source-freeze manifest. It does not maintain a parallel asset list.
"""

from __future__ import annotations

import ast
import base64
import csv
import email.parser
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

INVENTORY_SCHEMA = "policyos.e02.q2.complete-wheel-inventory.v3"
REQUEST_SCHEMA = "policyos.e02.q2.split-consumer-request.v2"
PROFILE_CHAIN_KEYS = {
    "source-wheel": "source_wheel_sha256",
    "rebuilt-sdist-wheel": "rebuilt_sdist_wheel_sha256",
    "rebuilt-gcp-archive-wheel": "rebuilt_gcp_wheel_sha256",
}
_SHA1 = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
MAX_WORKER_METADATA_BYTES = 4 * 1024 * 1024
MAX_WORKER_LOG_AND_TEST_TEMP_BYTES = 24 * 1024 * 1024
MAX_INSTALLER_METADATA_OVERHEAD_BYTES = 128 * 1024


class SplitProtocolError(ValueError):
    """A split Q2 request or artifact differs from its source-bound inputs."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SplitProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_bytes(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_no_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SplitProtocolError(f"{label} is not strict UTF-8 JSON") from error
    if type(value) is not dict:
        raise SplitProtocolError(f"{label} root must be an object")
    return value


def _relative(value: object, *, label: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value:
        raise SplitProtocolError(f"{label} must be a canonical relative POSIX path")
    parsed = PurePosixPath(value)
    if (
        parsed.is_absolute()
        or not parsed.parts
        or parsed.as_posix() != value
        or any(part in {"", ".", ".."} for part in parsed.parts)
    ):
        raise SplitProtocolError(f"{label} must be a canonical relative POSIX path: {value!r}")
    return parsed


def _rooted_file(root: Path, relative: object, *, label: str) -> tuple[Path, bytes]:
    rel = _relative(relative, label=label)
    path = root.joinpath(*rel.parts)
    current = root
    for component in rel.parts:
        current = current / component
        try:
            info = current.lstat()
        except OSError as error:
            raise SplitProtocolError(f"{label} is missing: {rel.as_posix()}") from error
        if stat.S_ISLNK(info.st_mode):
            raise SplitProtocolError(f"{label} contains a symlink: {current}")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise SplitProtocolError(f"{label} escapes its frozen source root") from error
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise SplitProtocolError(f"{label} is not a regular file: {rel.as_posix()}")
    return resolved, resolved.read_bytes()


def _file_row(root: Path, source: str, wheel: str, *, kind: str) -> dict[str, Any]:
    source_rel = _relative(source, label="inventory source")
    wheel_rel = _relative(wheel, label="inventory wheel target")
    _, data = _rooted_file(root, source_rel.as_posix(), label="packaged source")
    return {
        "kind": kind,
        "source": source_rel.as_posix(),
        "wheel": wheel_rel.as_posix(),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def _enumerate_package(root: Path, declared: object) -> tuple[list[dict[str, Any]], list[str]]:
    if type(declared) is not str:
        raise SplitProtocolError("Hatch wheel package declarations must be strings")
    rel = _relative(declared, label="Hatch wheel package")
    package_dir = root.joinpath(*rel.parts)
    current = root
    for component in rel.parts:
        current = current / component
        if current.is_symlink():
            raise SplitProtocolError(f"Hatch wheel package contains a symlink: {current}")
    try:
        resolved_dir = package_dir.resolve(strict=True)
        resolved_dir.relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise SplitProtocolError(f"Hatch wheel package is absent or escaped: {declared}") from error
    if package_dir.is_symlink() or not resolved_dir.is_dir():
        raise SplitProtocolError(f"Hatch wheel package is not a regular directory: {declared}")

    destination_root = rel.name
    rows: list[dict[str, Any]] = []
    for directory, dirnames, filenames in os.walk(resolved_dir, followlinks=False):
        current = Path(directory)
        for name in sorted(dirnames):
            path = current / name
            if path.is_symlink() or not path.is_dir():
                raise SplitProtocolError(
                    f"package tree contains a symlink/special directory: {path}"
                )
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink() or not path.is_file():
                raise SplitProtocolError(f"package tree contains a symlink/special file: {path}")
            source = path.relative_to(root).as_posix()
            inside = path.relative_to(resolved_dir).as_posix()
            target = PurePosixPath(destination_root, inside).as_posix()
            rows.append(_file_row(root, source, target, kind="package"))
    if not rows:
        raise SplitProtocolError(f"Hatch wheel package has no regular source files: {declared}")
    return rows, [destination_root]


def _regular_tree_rows(root: Path, relative: str, *, kind: str) -> list[dict[str, Any]]:
    """Enumerate every regular source file under one explicit packaging input."""
    rel = _relative(relative, label=f"{kind} source")
    target = root.joinpath(*rel.parts)
    try:
        info = target.lstat()
    except OSError as error:
        raise SplitProtocolError(f"{kind} source input is absent: {relative}") from error
    if stat.S_ISLNK(info.st_mode):
        raise SplitProtocolError(f"{kind} source input is a symlink: {relative}")
    if stat.S_ISREG(info.st_mode):
        return [_file_row(root, relative, relative, kind=kind)]
    if not stat.S_ISDIR(info.st_mode):
        raise SplitProtocolError(f"{kind} source input is not a regular file/tree: {relative}")
    rows: list[dict[str, Any]] = []
    for directory, dirnames, filenames in os.walk(target, followlinks=False):
        current = Path(directory)
        for name in sorted(dirnames):
            child = current / name
            if child.is_symlink() or not child.is_dir():
                raise SplitProtocolError(f"{kind} source tree has a symlink/special directory")
        for name in sorted(filenames):
            child = current / name
            if child.is_symlink() or not child.is_file():
                raise SplitProtocolError(f"{kind} source tree has a symlink/special file")
            source = child.relative_to(root).as_posix()
            rows.append(_file_row(root, source, source, kind=kind))
    if not rows:
        raise SplitProtocolError(f"{kind} source tree is empty: {relative}")
    return rows


def _gcp_recipe_contract(product: Path) -> tuple[list[str], str, dict[str, set[str]]]:
    """Read the producer's literal GCP include roots and skip policy from its pinned source."""
    recipe_path, recipe_bytes = _rooted_file(
        product, "ops/cloud/gcp/package_repo.sh", label="GCP package producer"
    )
    del recipe_path
    text = recipe_bytes.decode("utf-8", "strict")
    marker = "<< 'PY'\n"
    if text.count(marker) != 1:
        raise SplitProtocolError("GCP package producer has no unique embedded Python body")
    body = text.split(marker, 1)[1].rsplit("\nPY", 1)[0]
    try:
        tree = ast.parse(body, filename="package_repo.sh::<embedded-python>")
    except SyntaxError as error:
        raise SplitProtocolError("GCP package producer embedded Python is malformed") from error
    literals: dict[str, Any] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "include_paths",
                    "skip_parts",
                    "skip_suffixes",
                    "skip_names",
                }:
                    try:
                        literals[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        continue
    includes = literals.get("include_paths")
    if (
        type(includes) is not list
        or not includes
        or any(type(value) is not str for value in includes)
    ):
        raise SplitProtocolError("GCP producer include roots are not literal source inputs")
    skip = {
        "parts": set(literals.get("skip_parts", [])),
        "suffixes": set(literals.get("skip_suffixes", [])),
        "names": set(literals.get("skip_names", [])),
    }
    if any(type(value) is not set for value in skip.values()):
        raise SplitProtocolError("GCP producer skip policy is not a literal set contract")
    normalized: list[str] = []
    for value in includes:
        _relative(value, label="GCP archive include root")
        prefix = "policy-engine/"
        if not value.startswith(prefix):
            raise SplitProtocolError("GCP producer include root is outside policy-engine")
        product_rel = value[len(prefix) :]
        normalized.append(_relative(product_rel, label="GCP product include root").as_posix())
    return normalized, sha256_bytes(recipe_bytes), skip


def _gcp_source_rows(product: Path, manifest_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive complete GCP regular-file membership from producer inputs and source bytes."""
    roots, _recipe_sha, skip = _gcp_recipe_contract(product)
    hatch_raw = _rooted_file(product, "hatch.toml", label="Hatch config")[1]
    hatch = tomllib.loads(hatch_raw.decode("utf-8"))
    forced = hatch["build"]["targets"]["wheel"]["force-include"]
    sources = list(roots)
    sources.extend(forced.keys())
    rows_by_source: dict[str, dict[str, Any]] = {}
    for include in sources:
        rel = _relative(include, label="GCP source member").as_posix()
        path = product / rel
        candidates = _regular_tree_rows(product, rel, kind="gcp_source")
        for row in candidates:
            relative = row["source"]
            parts = PurePosixPath(relative).parts
            if (
                any(part in skip["parts"] or part.endswith(".egg-info") for part in parts)
                or PurePosixPath(relative).name in skip["names"]
                or PurePosixPath(relative).suffix in skip["suffixes"]
            ):
                continue
            rows_by_source[relative] = row
        if (
            path.is_file()
            and rel not in rows_by_source
            and not (
                PurePosixPath(rel).name in skip["names"]
                or PurePosixPath(rel).suffix in skip["suffixes"]
                or any(
                    part in skip["parts"] or part.endswith(".egg-info")
                    for part in PurePosixPath(rel).parts
                )
            )
        ):
            raise SplitProtocolError(f"explicit GCP file input was not enumerated: {rel}")
    forced_sources = {
        _relative(asset.get("source"), label="GCP forced source").as_posix()
        for asset in manifest_assets
    }
    if not forced_sources <= rows_by_source.keys():
        raise SplitProtocolError("GCP producer inventory omits a frozen force-include source")
    return [
        {**rows_by_source[key], "archive": f"policy-engine/{key}"} for key in sorted(rows_by_source)
    ]


def _project_build_metadata(product: Path, *, license_files: object) -> dict[str, Any]:
    """Derive the only root outside package roots that a built wheel may contain."""
    _, pyproject_bytes = _rooted_file(product, "pyproject.toml", label="project metadata")
    try:
        project = tomllib.loads(pyproject_bytes.decode("utf-8"))["project"]
        project_name, project_version = project["name"], project["version"]
    except (UnicodeDecodeError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise SplitProtocolError("wheel name/version must be statically source-declared") from error
    if (
        type(project_name) is not str
        or not project_name
        or type(project_version) is not str
        or not project_version
    ):
        raise SplitProtocolError("wheel name/version must be non-empty source strings")
    normalized = re.sub(r"[-_.]+", "_", project_name).lower()
    info_root = f"{normalized}-{project_version}.dist-info"
    generated = {"METADATA", "WHEEL", "RECORD"}
    if any(project.get(key) for key in ("scripts", "gui-scripts", "entry-points")):
        generated.add("entry_points.txt")
    entry_points: dict[str, dict[str, str]] = {}
    for field, group in (("scripts", "console_scripts"), ("gui-scripts", "gui_scripts")):
        values = project.get(field, {})
        if values:
            if type(values) is not dict or any(
                type(key) is not str or type(value) is not str for key, value in values.items()
            ):
                raise SplitProtocolError(f"project {field} metadata is malformed")
            entry_points[group] = dict(sorted(values.items()))
    declared_groups = project.get("entry-points", {})
    if type(declared_groups) is not dict:
        raise SplitProtocolError("project entry-points metadata is malformed")
    for group, values in declared_groups.items():
        if (
            type(group) is not str
            or type(values) is not dict
            or any(type(key) is not str or type(value) is not str for key, value in values.items())
        ):
            raise SplitProtocolError("project entry-point group is malformed")
        if values:
            entry_points[group] = dict(sorted(values.items()))
    if (
        type(license_files) is not list
        or any(type(source) is not str for source in license_files)
        or license_files != sorted(set(license_files))
    ):
        raise SplitProtocolError("Hatchling license-file selection is malformed")
    license_rows: list[dict[str, Any]] = []
    for source in license_files:
        source_path = _relative(source, label="Hatchling license file").as_posix()
        target = f"{info_root}/licenses/{source_path}"
        license_rows.append(_file_row(product, source_path, target, kind="wheel_license"))
        generated.add(f"licenses/{source_path}")
    generated_paths = [f"{info_root}/{name}" for name in sorted(generated)]
    return {
        "name": project_name,
        "version": project_version,
        "dist_info_root": info_root,
        "dist_info_members": generated_paths,
        "license_rows": license_rows,
        "entry_points": entry_points,
    }


def _validate_freeze(
    manifest: dict[str, Any], *, expected_commit: str, expected_tree: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 1:
        raise SplitProtocolError("source-freeze manifest has an unsupported schema version")
    if not _SHA1.fullmatch(expected_commit) or not _SHA1.fullmatch(expected_tree):
        raise SplitProtocolError("expected source commit and tree must be full SHA-1 identities")
    baseline = manifest.get("candidate_baseline")
    if type(baseline) is not dict:
        raise SplitProtocolError("source-freeze manifest has no candidate baseline")
    if (
        baseline.get("source_sha") != expected_commit
        or baseline.get("source_tree") != expected_tree
    ):
        raise SplitProtocolError("manifest source identity differs from the selected freeze")
    assets = baseline.get("force_include_assets")
    declared_count = baseline.get("force_include_count")
    if (
        type(assets) is not list
        or type(declared_count) is not int
        or declared_count != len(assets)
        or not assets
    ):
        raise SplitProtocolError("force-include asset denominator is malformed")
    return baseline, assets


def _hatchling_sdist_selection(
    product: Path, *, python_executable: str | Path | None = None
) -> tuple[dict[str, Any], str]:
    """Ask the selected Hatchling interpreter for its no-build sdist input set."""
    helper = Path(__file__).with_name("hatch_sdist_selection.py")
    if helper.is_symlink() or not helper.is_file():
        raise SplitProtocolError("source-derived Hatchling selector is missing or unsafe")
    locked_interpreter = python_executable is not None
    executable = Path(python_executable or sys.executable).absolute()
    if not executable.exists() or not executable.is_file():
        raise SplitProtocolError("selected Hatchling interpreter is missing or unsafe")
    command = [str(executable), "-B"]
    child_env = None
    if locked_interpreter:
        command.insert(1, "-I")
        child_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    command.extend((str(helper), str(product)))
    try:
        # This literal argv uses the interpreter admitted by the source-bound Q2 build profile.
        result = subprocess.run(  # noqa: S603
            command,
            cwd=Path.cwd(),
            env=child_env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SplitProtocolError(f"Hatchling source selection could not run: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no child output"
        raise SplitProtocolError(f"Hatchling source selection refused: {detail}")
    try:
        selection = load_json_bytes(result.stdout.encode("utf-8"), label="Hatchling selection")
    except (UnicodeEncodeError, SplitProtocolError) as error:
        raise SplitProtocolError("Hatchling selection output is not strict JSON") from error
    if selection.get("schema") != "policyos.e02.q2.hatchling-sdist-selection.v1":
        raise SplitProtocolError("Hatchling selection schema is unsupported")
    return selection, sha256_file(helper)


def build_source_inventory(
    product_root: str | Path,
    manifest: dict[str, Any],
    *,
    expected_commit: str,
    expected_tree: str,
    hatchling_python: str | Path | None = None,
) -> dict[str, Any]:
    """Derive every wheel package file and forced resource from frozen source."""
    product = Path(product_root).resolve(strict=True)
    if product.is_symlink() or not product.is_dir():
        raise SplitProtocolError("product root is not a regular source directory")
    _baseline, assets = _validate_freeze(
        manifest, expected_commit=expected_commit, expected_tree=expected_tree
    )
    _, hatch_bytes = _rooted_file(product, "hatch.toml", label="Hatch config")
    try:
        hatch = tomllib.loads(hatch_bytes.decode("utf-8"))
        wheel = hatch["build"]["targets"]["wheel"]
        sdist = hatch["build"]["targets"]["sdist"]
        packages = wheel["packages"]
        force_include = wheel["force-include"]
        sdist_include = sdist["include"]
    except (UnicodeDecodeError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise SplitProtocolError(
            "Hatch wheel/sdist membership configuration is malformed"
        ) from error
    if (
        type(packages) is not list
        or not packages
        or type(force_include) is not dict
        or not isinstance(sdist_include, list)
        or wheel.get("only-include") is not None
        or wheel.get("only-packages") is not None
        or wheel.get("sources") is not None
        or wheel.get("exclude") is not None
    ):
        raise SplitProtocolError(
            "wheel membership modifiers require a corresponding generic source enumerator"
        )
    if any(type(value) is not str for value in sdist_include):
        raise SplitProtocolError("Hatch sdist include paths must be strings")

    manifest_mapping: dict[str, str] = {}
    asset_by_source: dict[str, dict[str, Any]] = {}
    asset_targets: set[str] = set()
    for asset in assets:
        if type(asset) is not dict:
            raise SplitProtocolError("force-include manifest rows must be objects")
        source = _relative(asset.get("source"), label="force-include source").as_posix()
        target = _relative(asset.get("wheel"), label="force-include target").as_posix()
        archive = asset.get("archive")
        if archive != f"policy-engine/{source}":
            raise SplitProtocolError(f"force-include archive path is not source-bound: {source}")
        size, digest = asset.get("bytes"), asset.get("sha256")
        if (
            type(size) is not int
            or size < 0
            or type(digest) is not str
            or not _SHA256.fullmatch(digest)
            or source in manifest_mapping
            or target in asset_targets
        ):
            raise SplitProtocolError(
                f"force-include manifest row is malformed or duplicated: {source}"
            )
        manifest_mapping[source] = target
        asset_targets.add(target)
        asset_by_source[source] = asset
    if force_include != manifest_mapping:
        raise SplitProtocolError(
            "Hatch force-include mapping differs from the content-bound freeze manifest"
        )
    sdist_paths = {
        _relative(value, label="Hatch sdist include").as_posix() for value in sdist_include
    }
    missing_sdist = sorted(set(manifest_mapping) - sdist_paths)
    if missing_sdist:
        raise SplitProtocolError(f"sdist omits force-include source files: {missing_sdist}")

    rows: list[dict[str, Any]] = []
    package_roots: set[str] = set()
    for package in packages:
        package_rows, roots = _enumerate_package(product, package)
        rows.extend(package_rows)
        package_roots.update(roots)
    for source, target in sorted(manifest_mapping.items()):
        _, data = _rooted_file(product, source, label="force-include source")
        asset = asset_by_source[source]
        if type(asset["bytes"]) is not int or len(data) != asset["bytes"]:
            raise SplitProtocolError(f"force-include source byte length differs: {source}")
        if sha256_bytes(data) != asset["sha256"]:
            raise SplitProtocolError(f"force-include source bytes differ from freeze: {source}")
        rows.append(
            {
                "kind": "force_include",
                "source": source,
                "wheel": target,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            }
        )
        package_roots.add(PurePosixPath(target).parts[0])

    rows.sort(key=lambda row: (row["wheel"], row["source"], row["kind"]))
    targets = [row["wheel"] for row in rows]
    sources = [row["source"] for row in rows]
    if len(targets) != len(set(targets)):
        raise SplitProtocolError("wheel source mapping has duplicate package/resource targets")
    if len(sources) != len(set(sources)):
        raise SplitProtocolError("wheel source inventory repeats a source path")
    package_rows = [row for row in rows if row["kind"] == "package"]
    asset_rows = [row for row in rows if row["kind"] == "force_include"]
    if not package_rows or set(asset_by_source) != {row["source"] for row in asset_rows}:
        raise SplitProtocolError("complete package/resource inventory is empty or incomplete")

    selection, selection_helper_sha256 = _hatchling_sdist_selection(
        product, python_executable=hatchling_python
    )
    license_files = selection.get("license_files")
    if (
        type(license_files) is not list
        or any(type(source) is not str for source in license_files)
        or license_files != sorted(set(license_files))
    ):
        raise SplitProtocolError("Hatchling license-file selection is malformed")
    project_metadata = _project_build_metadata(product, license_files=license_files)
    if selection.get("hatch_config_sha256") != sha256_bytes(hatch_bytes):
        raise SplitProtocolError(
            "Hatchling selected a configuration outside the frozen source bytes"
        )
    selection_files = selection.get("files")
    if type(selection_files) is not list or not selection_files:
        raise SplitProtocolError("Hatchling source selection is empty or malformed")
    sdist_rows_by_source: dict[str, dict[str, Any]] = {}
    for selected in selection_files:
        if type(selected) is not dict:
            raise SplitProtocolError("Hatchling selected source row is malformed")
        source = _relative(selected.get("source"), label="Hatchling selected source").as_posix()
        distribution = _relative(
            selected.get("distribution"), label="Hatchling distribution path"
        ).as_posix()
        if distribution != source or source in sdist_rows_by_source:
            raise SplitProtocolError(
                f"Hatchling sdist source mapping is unsupported or duplicated: {source}"
            )
        raw = _rooted_file(product, source, label="Hatchling selected sdist source")[1]
        sdist_rows_by_source[source] = {
            "kind": "sdist_source",
            "source": source,
            "wheel": distribution,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
        }
    required_sdist_sources = set(manifest_mapping)
    if not required_sdist_sources <= sdist_rows_by_source.keys():
        raise SplitProtocolError("sdist source inventory omits a frozen force-include source")
    sdist_rows = [sdist_rows_by_source[key] for key in sorted(sdist_rows_by_source)]
    default_force_sources = selection.get("default_force_include_sources")
    api_source_hashes = selection.get("api_source_sha256")
    build_hooks = selection.get("configured_build_hooks")
    if (
        type(default_force_sources) is not list
        or any(type(source) is not str for source in default_force_sources)
        or default_force_sources != sorted(set(default_force_sources))
        or any(source not in sdist_rows_by_source for source in default_force_sources)
        or type(api_source_hashes) is not dict
        or not api_source_hashes
        or any(
            type(path) is not str
            or _relative(path, label="Hatchling API source").as_posix() != path
            or type(digest) is not str
            or not _SHA256.fullmatch(digest)
            for path, digest in api_source_hashes.items()
        )
        or build_hooks != []
    ):
        raise SplitProtocolError("Hatchling producer-selection proof is incomplete")
    sdist_pairs = [{"source": row["source"], "distribution": row["wheel"]} for row in sdist_rows]
    sdist_producer = {
        "builder_class": "hatchling.builders.sdist.SdistBuilder",
        "api_source_sha256": api_source_hashes,
        "configured_build_hooks": build_hooks,
        "default_force_include_sources": default_force_sources,
        "default_force_include_sources_sha256": sha256_bytes(
            canonical_json_bytes(default_force_sources)
        ),
        "selected_file_count": len(sdist_rows),
        "selected_files_sha256": sha256_bytes(canonical_json_bytes(sdist_pairs)),
        "selection_helper_sha256": selection_helper_sha256,
        "hatch_config_sha256": sha256_bytes(hatch_bytes),
    }

    gcp_rows = _gcp_source_rows(product, assets)
    if not gcp_rows:
        raise SplitProtocolError("GCP source inventory is empty")

    return {
        "schema": INVENTORY_SCHEMA,
        "source": {"commit": expected_commit, "tree": expected_tree},
        "hatch_config_sha256": sha256_bytes(hatch_bytes),
        "package_declarations": packages,
        "force_include_mapping": dict(sorted(manifest_mapping.items())),
        "package_roots": sorted(package_roots),
        "rows": rows,
        "assets": asset_rows,
        "rows_sha256": sha256_bytes(canonical_json_bytes(rows)),
        "package_file_count": len(package_rows),
        "package_bytes": sum(row["bytes"] for row in package_rows),
        "force_include_count": len(asset_rows),
        "project_metadata": project_metadata,
        "sdist_source_rows": sdist_rows,
        "sdist_source_rows_sha256": sha256_bytes(canonical_json_bytes(sdist_rows)),
        "sdist_producer": sdist_producer,
        "gcp_recipe_sha256": _gcp_recipe_contract(product)[1],
        "gcp_source_rows": gcp_rows,
        "gcp_source_rows_sha256": sha256_bytes(canonical_json_bytes(gcp_rows)),
    }


def validate_inventory(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate a transported inventory before using any path or content field."""
    source = inventory.get("source")
    rows = inventory.get("rows")
    roots = inventory.get("package_roots")
    if (
        inventory.get("schema") != INVENTORY_SCHEMA
        or type(source) is not dict
        or type(source.get("commit")) is not str
        or not _SHA1.fullmatch(source["commit"])
        or type(source.get("tree")) is not str
        or not _SHA1.fullmatch(source["tree"])
        or type(rows) is not list
        or not rows
        or type(roots) is not list
        or not roots
        or any(
            type(root) is not str or _relative(root, label="package root").as_posix() != root
            for root in roots
        )
        or roots != sorted(set(roots))
        or inventory.get("rows_sha256") != sha256_bytes(canonical_json_bytes(rows))
    ):
        raise SplitProtocolError("transported package inventory identity/schema is invalid")
    seen_targets: set[str] = set()
    seen_sources: set[str] = set()
    for row in rows:
        if type(row) is not dict:
            raise SplitProtocolError("transported package inventory row is malformed")
        source_path = _relative(row.get("source"), label="inventory source").as_posix()
        target = _relative(row.get("wheel"), label="inventory target").as_posix()
        size, digest, kind = row.get("bytes"), row.get("sha256"), row.get("kind")
        if (
            kind not in {"package", "force_include"}
            or type(size) is not int
            or size < 0
            or type(digest) is not str
            or not _SHA256.fullmatch(digest)
            or source_path in seen_sources
            or target in seen_targets
        ):
            raise SplitProtocolError(f"transported package inventory row is invalid: {source_path}")
        seen_sources.add(source_path)
        seen_targets.add(target)
    if type(inventory.get("package_file_count")) is not int or inventory[
        "package_file_count"
    ] != sum(row["kind"] == "package" for row in rows):
        raise SplitProtocolError("package file count differs from complete inventory")
    if type(inventory.get("force_include_count")) is not int or inventory[
        "force_include_count"
    ] != sum(row["kind"] == "force_include" for row in rows):
        raise SplitProtocolError("force-include count differs from complete inventory")
    if type(inventory.get("package_bytes")) is not int or inventory["package_bytes"] != sum(
        row["bytes"] for row in rows if row["kind"] == "package"
    ):
        raise SplitProtocolError("package byte total differs from complete inventory")
    expected_roots = sorted({PurePosixPath(row["wheel"]).parts[0] for row in rows})
    if roots != expected_roots:
        raise SplitProtocolError("wheel package roots differ from complete inventory")
    project = inventory.get("project_metadata")
    if (
        type(project) is not dict
        or type(project.get("name")) is not str
        or not project["name"]
        or type(project.get("version")) is not str
        or not project["version"]
        or type(project.get("dist_info_root")) is not str
        or type(project.get("dist_info_members")) is not list
        or not project["dist_info_members"]
        or type(project.get("license_rows")) is not list
        or type(project.get("entry_points")) is not dict
    ):
        raise SplitProtocolError("complete wheel metadata contract is malformed")
    normalized_name = re.sub(r"[-_.]+", "_", project["name"]).lower()
    if project["dist_info_root"] != f"{normalized_name}-{project['version']}.dist-info":
        raise SplitProtocolError("wheel metadata root is not derived from project identity")
    metadata_paths = project["dist_info_members"]
    if (
        metadata_paths != sorted(set(metadata_paths))
        or not {f"{project['dist_info_root']}/{name}" for name in ("METADATA", "WHEEL", "RECORD")}
        <= set(metadata_paths)
        or any(
            _relative(path, label="wheel metadata member").parts[0] != project["dist_info_root"]
            for path in metadata_paths
        )
    ):
        raise SplitProtocolError("wheel metadata membership is not complete and canonical")
    license_targets: set[str] = set()
    for row in project["license_rows"]:
        if type(row) is not dict:
            raise SplitProtocolError("wheel license source row is malformed")
        source_path = _relative(row.get("source"), label="wheel license source").as_posix()
        target = _relative(row.get("wheel"), label="wheel license target").as_posix()
        if (
            row.get("kind") != "wheel_license"
            or type(row.get("bytes")) is not int
            or row["bytes"] < 0
            or type(row.get("sha256")) is not str
            or not _SHA256.fullmatch(row["sha256"])
            or target not in metadata_paths
            or source_path in license_targets
        ):
            raise SplitProtocolError("wheel license source binding is invalid")
        license_targets.add(source_path)
    for field in ("sdist_source_rows", "gcp_source_rows"):
        source_rows = inventory.get(field)
        expected_digest = inventory.get(f"{field}_sha256")
        if (
            type(source_rows) is not list
            or not source_rows
            or expected_digest != sha256_bytes(canonical_json_bytes(source_rows))
        ):
            raise SplitProtocolError(f"complete {field} digest or set is malformed")
        seen: set[str] = set()
        for row in source_rows:
            if type(row) is not dict:
                raise SplitProtocolError(f"complete {field} row is malformed")
            source_path = _relative(row.get("source"), label=f"{field} source").as_posix()
            if (
                row.get("kind") not in {"sdist_source", "gcp_source"}
                or type(row.get("bytes")) is not int
                or row["bytes"] < 0
                or type(row.get("sha256")) is not str
                or not _SHA256.fullmatch(row["sha256"])
                or source_path in seen
            ):
                raise SplitProtocolError(f"complete {field} row is invalid")
            if field == "gcp_source_rows":
                archive_path = _relative(row.get("archive"), label="GCP archive source")
                if archive_path.as_posix() != f"policy-engine/{source_path}":
                    raise SplitProtocolError("GCP archive source path is not source-rooted")
            seen.add(source_path)
    producer = inventory.get("sdist_producer")
    source_rows = inventory.get("sdist_source_rows")
    if (
        type(producer) is not dict
        or producer.get("builder_class") != "hatchling.builders.sdist.SdistBuilder"
        or producer.get("configured_build_hooks") != []
        or type(producer.get("api_source_sha256")) is not dict
        or type(producer.get("default_force_include_sources")) is not list
        or not producer.get("default_force_include_sources")
        or type(inventory.get("hatch_config_sha256")) is not str
        or not _SHA256.fullmatch(inventory["hatch_config_sha256"])
        or type(producer.get("selected_file_count")) is not int
        or type(producer.get("selected_files_sha256")) is not str
        or not _SHA256.fullmatch(producer["selected_files_sha256"])
        or type(producer.get("selection_helper_sha256")) is not str
        or not _SHA256.fullmatch(producer["selection_helper_sha256"])
        or producer.get("hatch_config_sha256") != inventory.get("hatch_config_sha256")
    ):
        raise SplitProtocolError("Hatchling sdist producer record is malformed")
    selected_sources = [row["source"] for row in source_rows]
    default_sources = producer["default_force_include_sources"]
    if any(type(source) is not str for source in default_sources):
        raise SplitProtocolError("Hatchling default source list is malformed")
    if (
        selected_sources != sorted(selected_sources)
        or any(row.get("wheel") != row.get("source") for row in source_rows)
        or producer["selected_file_count"] != len(source_rows)
        or producer["selected_files_sha256"]
        != sha256_bytes(
            canonical_json_bytes(
                [{"source": source, "distribution": source} for source in selected_sources]
            )
        )
        or default_sources != sorted(set(default_sources))
        or any(
            _relative(source, label="Hatchling default source").as_posix() not in selected_sources
            for source in default_sources
        )
        or producer.get("default_force_include_sources_sha256")
        != sha256_bytes(canonical_json_bytes(default_sources))
    ):
        raise SplitProtocolError("Hatchling default or selected source membership is incomplete")
    api_sources = producer["api_source_sha256"]
    expected_api_sources = {
        "hatchling/builders/config.py",
        "hatchling/builders/constants.py",
        "hatchling/builders/plugin/interface.py",
        "hatchling/builders/sdist.py",
        "hatchling/builders/utils.py",
        "hatchling/metadata/core.py",
        "hatchling/utils/constants.py",
    }
    if set(api_sources) != expected_api_sources or any(
        type(digest) is not str or not _SHA256.fullmatch(digest) for digest in api_sources.values()
    ):
        raise SplitProtocolError("Hatchling API source identity is incomplete")
    if type(inventory.get("gcp_recipe_sha256")) is not str or not _SHA256.fullmatch(
        inventory["gcp_recipe_sha256"]
    ):
        raise SplitProtocolError("GCP producer source pin is malformed")
    return rows


def validate_source_audit_selection(
    receipt: dict[str, Any],
    *,
    expected_commit: str,
    expected_tree: str,
    manifest_sha256: str,
    supplemental_manifest_sha256: str,
) -> dict[str, Any]:
    """Bind the consumer matrix to a completed source-audit check and exact selected IDs."""
    if (
        type(receipt.get("schema_version")) is not int
        or receipt.get("schema_version") != 1
        or receipt.get("status") != "source_preflight_exact"
        or receipt.get("source_sha") != expected_commit
        or receipt.get("source_tree") != expected_tree
        or receipt.get("source_object_and_actual_collection_reconcile") is not True
        or receipt.get("capsule_bindings_current") is not True
        or receipt.get("frozen_checkout_clean_tracked") is not True
        or receipt.get("build_started") is not False
        or receipt.get("install_started") is not False
        or receipt.get("tests_executed") is not False
        or receipt.get("pytest_collection_only") is not True
        or receipt.get("runner_limitations") != []
    ):
        raise SplitProtocolError("source-audit receipt is not an exact source-only preflight")
    primary = receipt.get("primary")
    supplemental = receipt.get("supplemental")
    profiles = receipt.get("profiles")
    if type(primary) is not dict or type(supplemental) is not dict or type(profiles) is not list:
        raise SplitProtocolError("source-audit receipt omits its complete consumer matrix")
    if (
        primary.get("current_manifest_sha256") != manifest_sha256
        or supplemental.get("current_manifest_sha256") != supplemental_manifest_sha256
    ):
        raise SplitProtocolError("source-audit receipt manifest pins differ from worker inputs")

    def selected_ids(group: dict[str, Any], label: str) -> tuple[list[str], str]:
        values = group.get("source_derived_node_ids")
        declared_count = group.get("source_derived_ids")
        declared_sha = group.get("source_derived_ids_sha256")
        if (
            type(values) is not list
            or not values
            or any(type(value) is not str or not value for value in values)
            or values != sorted(set(values))
            or type(declared_count) is not int
            or declared_count != len(values)
            or type(declared_sha) is not str
            or not _SHA256.fullmatch(declared_sha)
        ):
            raise SplitProtocolError(f"source-audit {label} selector set is malformed")
        observed_sha = sha256_bytes(("\n".join(values) + "\n").encode("utf-8"))
        if observed_sha != declared_sha:
            raise SplitProtocolError(f"source-audit {label} selector digest differs from IDs")
        return values, observed_sha

    primary_ids, primary_sha = selected_ids(primary, "primary")
    supplemental_ids, supplemental_sha = selected_ids(supplemental, "supplemental")
    if set(primary_ids) & set(supplemental_ids):
        raise SplitProtocolError("source-audit primary and supplemental IDs overlap")
    if (
        not profiles
        or any(type(value) is not str or not value for value in profiles)
        or len(profiles) != len(set(profiles))
        or receipt.get("primary_runner_profile_names") != profiles
        or receipt.get("supplemental_runner_profile_names") != profiles
        or type(receipt.get("source_derived_profile_case_count")) is not int
        or receipt["source_derived_profile_case_count"]
        != len(profiles) * (len(primary_ids) + len(supplemental_ids))
    ):
        raise SplitProtocolError("source-audit primary/supplemental profile matrix is incomplete")
    return {
        "profiles": profiles,
        "primary_node_ids": primary_ids,
        "primary_node_ids_sha256": primary_sha,
        "supplemental_node_ids": supplemental_ids,
        "supplemental_node_ids_sha256": supplemental_sha,
        "profile_case_count": receipt["source_derived_profile_case_count"],
    }


def _wheel_file_table(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Reject unsafe ZIP members and return the complete regular-file table."""
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise SplitProtocolError("wheel has duplicate member names")
    result: dict[str, zipfile.ZipInfo] = {}
    for info in infos:
        raw_name = (
            info.filename[:-1] if info.is_dir() and info.filename.endswith("/") else info.filename
        )
        rel = _relative(raw_name, label="wheel member")
        mode = info.external_attr >> 16
        file_type = stat.S_IFMT(mode)
        if info.is_dir():
            if file_type not in {0, stat.S_IFDIR}:
                raise SplitProtocolError(f"wheel directory has a special mode: {info.filename}")
            continue
        if file_type not in {0, stat.S_IFREG}:
            raise SplitProtocolError(f"wheel member is not a regular file: {info.filename}")
        result[rel.as_posix()] = info
    return result


def _verify_entry_points(raw: bytes, expected: dict[str, dict[str, str]]) -> None:
    parser = __import__("configparser").ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    try:
        parser.read_string(raw.decode("utf-8", "strict"))
    except (UnicodeDecodeError, ValueError) as error:
        raise SplitProtocolError("wheel entry_points.txt is not valid UTF-8 INI") from error
    observed = {group: dict(parser.items(group)) for group in parser.sections()}
    if observed != expected:
        raise SplitProtocolError("wheel entry_points.txt differs from pyproject declarations")


def _validate_wheel_metadata(
    archive: zipfile.ZipFile,
    file_table: dict[str, zipfile.ZipInfo],
    inventory: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Validate the sole build-generated wheel root and its standard metadata records."""
    project = inventory["project_metadata"]
    expected_paths = set(project["dist_info_members"])
    info_root = project["dist_info_root"]
    # A path root is metadata only if its first component has the standard suffix.
    actual_roots = {
        name.split("/", 1)[0] for name in file_table if ".dist-info" in name.split("/", 1)[0]
    }
    if actual_roots != {info_root}:
        raise SplitProtocolError(
            "wheel distribution metadata root differs from the source project identity"
        )
    actual_paths = {name for name in file_table if name.split("/", 1)[0] == info_root}
    if actual_paths != expected_paths:
        raise SplitProtocolError(
            "wheel generated metadata member set differs from standard project metadata: "
            f"missing={sorted(expected_paths - actual_paths)} "
            f"unexpected={sorted(actual_paths - expected_paths)}"
        )
    metadata: dict[str, bytes] = {name: archive.read(name) for name in sorted(expected_paths)}
    try:
        headers = email.parser.BytesParser().parsebytes(metadata[f"{info_root}/METADATA"])
    except (KeyError, ValueError) as error:
        raise SplitProtocolError("wheel METADATA is missing or malformed") from error
    if headers.get("Name") != project["name"] or headers.get("Version") != project["version"]:
        raise SplitProtocolError("wheel METADATA name/version differs from pyproject")
    wheel_fields: dict[str, list[str]] = {}
    for line in metadata[f"{info_root}/WHEEL"].decode("utf-8", "strict").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        wheel_fields.setdefault(key.strip().lower(), []).append(value.strip())
    if (
        wheel_fields.get("wheel-version") != ["1.0"]
        or wheel_fields.get("root-is-purelib") != ["true"]
        or wheel_fields.get("tag") != ["py3-none-any"]
    ):
        raise SplitProtocolError(
            "wheel WHEEL metadata differs from the universal pure-Python profile"
        )
    if "entry_points.txt" in {Path(path).name for path in expected_paths}:
        _verify_entry_points(metadata[f"{info_root}/entry_points.txt"], project["entry_points"])
    license_by_target = {row["wheel"]: row for row in project["license_rows"]}
    receipts: dict[str, dict[str, Any]] = {}
    for name, raw in metadata.items():
        relative = name[len(info_root) + 1 :]
        if relative.startswith("licenses/"):
            row = license_by_target.get(name)
            if row is None or len(raw) != row["bytes"] or sha256_bytes(raw) != row["sha256"]:
                raise SplitProtocolError(f"wheel license member is not source-derived: {name}")
        receipts[name] = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
    record_name = f"{info_root}/RECORD"
    try:
        record_rows = list(csv.reader(io.StringIO(metadata[record_name].decode("utf-8", "strict"))))
    except (UnicodeDecodeError, csv.Error) as error:
        raise SplitProtocolError("wheel RECORD is malformed") from error
    observed_record: dict[str, tuple[str, str]] = {}
    for row in record_rows:
        if len(row) != 3:
            raise SplitProtocolError("wheel RECORD row does not have three fields")
        path = _relative(row[0], label="wheel RECORD member").as_posix()
        if path in observed_record:
            raise SplitProtocolError("wheel RECORD repeats a member")
        observed_record[path] = (row[1], row[2])
    if set(observed_record) != set(file_table):
        raise SplitProtocolError("wheel RECORD does not cover the complete regular-member set")
    for name, info in file_table.items():
        digest_field, size_field = observed_record[name]
        if name == record_name:
            if digest_field or size_field:
                raise SplitProtocolError("wheel RECORD self-entry must have empty digest and size")
            continue
        raw = archive.read(info)
        expected_digest = "sha256=" + base64.urlsafe_b64encode(
            hashlib.sha256(raw).digest()
        ).decode().rstrip("=")
        if digest_field != expected_digest or size_field != str(len(raw)):
            raise SplitProtocolError(f"wheel RECORD digest/size differs from member bytes: {name}")
    return receipts


def verify_wheel_inventory(
    wheel_path: str | Path,
    inventory: dict[str, Any],
    *,
    metadata_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Require complete package roots plus only authentic standard dist-info files."""
    rows = validate_inventory(inventory)
    wheel_file = Path(wheel_path)
    project = inventory["project_metadata"] if metadata_contract is None else metadata_contract
    if type(project) is not dict:
        raise SplitProtocolError("wheel metadata contract must be an exact object")
    expected = {row["wheel"]: row for row in rows}
    try:
        with zipfile.ZipFile(wheel_file) as archive:
            file_table = _wheel_file_table(archive)
            metadata_paths = set(project["dist_info_members"])
            expected_paths = set(expected) | metadata_paths
            if set(file_table) != expected_paths:
                raise SplitProtocolError(
                    "wheel complete member set differs from source payload and generated metadata: "
                    f"missing={sorted(expected_paths - set(file_table))[:20]} "
                    f"unexpected={sorted(set(file_table) - expected_paths)[:20]}"
                )
            metadata_receipts = _validate_wheel_metadata(
                archive, file_table, {**inventory, "project_metadata": project}
            )
            receipts: dict[str, dict[str, Any]] = {}
            for target, row in sorted(expected.items()):
                raw = archive.read(file_table[target])
                actual_sha = sha256_bytes(raw)
                if len(raw) != row["bytes"] or actual_sha != row["sha256"]:
                    raise SplitProtocolError(f"wheel member bytes differ from source: {target}")
                receipts[target] = {"bytes": len(raw), "sha256": actual_sha}
            receipts.update(metadata_receipts)
    except (OSError, zipfile.BadZipFile, RuntimeError, KeyError) as error:
        if isinstance(error, SplitProtocolError):
            raise
        raise SplitProtocolError(
            f"wheel cannot be read as a regular ZIP artifact: {wheel_file}"
        ) from error
    return {
        "path": str(wheel_file),
        "bytes": wheel_file.stat().st_size,
        "sha256": sha256_file(wheel_file),
        "member_count": len(receipts),
        "member_inventory_sha256": sha256_bytes(canonical_json_bytes(receipts)),
        "members": receipts,
        "complete_member_set": True,
    }


def wheel_uncompressed_bytes(wheel_path: str | Path) -> int:
    """Measure all regular wheel members, including installer-created dist-info bytes."""
    wheel_file = Path(wheel_path)
    try:
        with zipfile.ZipFile(wheel_file) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise SplitProtocolError("wheel has duplicate member names")
            total = 0
            for info in infos:
                if info.is_dir():
                    continue
                _relative(info.filename, label="wheel member")
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise SplitProtocolError(f"wheel contains a symlink member: {info.filename}")
                file_type = stat.S_IFMT(mode)
                if file_type not in {0, stat.S_IFREG}:
                    raise SplitProtocolError(f"wheel contains a special member: {info.filename}")
                total += info.file_size
            return total
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        if isinstance(error, SplitProtocolError):
            raise
        raise SplitProtocolError(f"wheel cannot be measured: {wheel_file}") from error


def _archive_member_table(
    archive: tarfile.TarFile, *, label: str
) -> tuple[dict[str, tarfile.TarInfo], set[str]]:
    """Reject unsafe tar members and return regular files plus explicit directories."""
    files: dict[str, tarfile.TarInfo] = {}
    directories: set[str] = set()
    seen: set[str] = set()
    for info in archive.getmembers():
        raw_name = info.name[:-1] if info.isdir() and info.name.endswith("/") else info.name
        name = _relative(raw_name, label=f"{label} member").as_posix()
        if name in seen:
            raise SplitProtocolError(f"{label} repeats archive member {name}")
        seen.add(name)
        if info.isdir():
            directories.add(name)
        elif info.isreg():
            files[name] = info
        else:
            raise SplitProtocolError(f"{label} contains a link or special member: {name}")
    return files, directories


def _verify_tar_files(
    archive_path: str | Path,
    expected: dict[str, dict[str, Any]],
    *,
    label: str,
    generated_metadata_path: str | None = None,
    project_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare every regular tar member with a source-bound full membership map."""
    tar_path = Path(archive_path)
    try:
        with tarfile.open(tar_path, "r:*") as archive:
            files, directories = _archive_member_table(archive, label=label)
            file_names = set(files)
            expected_names = set(expected)
            if generated_metadata_path is not None:
                if project_metadata is None:
                    raise SplitProtocolError(f"{label} metadata contract is absent")
                expected_names.add(generated_metadata_path)
            if file_names != expected_names:
                raise SplitProtocolError(
                    f"{label} complete regular-file set differs from frozen producer inputs: "
                    f"missing={sorted(expected_names - file_names)[:20]} "
                    f"unexpected={sorted(file_names - expected_names)[:20]}"
                )
            parent_names: set[str] = set()
            for name in expected_names:
                parts = PurePosixPath(name).parts
                parent_names.update("/".join(parts[:index]) for index in range(1, len(parts)))
            if not directories <= parent_names:
                raise SplitProtocolError(
                    f"{label} contains a directory outside all source-derived file paths: "
                    f"{sorted(directories - parent_names)[:20]}"
                )
            receipts: dict[str, dict[str, Any]] = {}
            for name, row in sorted(expected.items()):
                stream = archive.extractfile(files[name])
                if stream is None:
                    raise SplitProtocolError(f"{label} member cannot be read: {name}")
                raw = stream.read()
                if len(raw) != row["bytes"] or sha256_bytes(raw) != row["sha256"]:
                    raise SplitProtocolError(f"{label} member bytes differ from source: {name}")
                receipts[name] = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
            if generated_metadata_path is not None:
                stream = archive.extractfile(files[generated_metadata_path])
                if stream is None:
                    raise SplitProtocolError(f"{label} generated metadata cannot be read")
                metadata_raw = stream.read()
                metadata = email.parser.BytesParser().parsebytes(metadata_raw)
                if project_metadata is None:
                    raise SplitProtocolError(f"{label} metadata contract is absent")
                if (
                    metadata.get("Name") != project_metadata["name"]
                    or metadata.get("Version") != project_metadata["version"]
                ):
                    raise SplitProtocolError(f"{label} generated metadata name/version differs")
                receipts[generated_metadata_path] = {
                    "bytes": len(metadata_raw),
                    "sha256": sha256_bytes(metadata_raw),
                }
    except (OSError, tarfile.TarError, UnicodeDecodeError) as error:
        if isinstance(error, SplitProtocolError):
            raise
        raise SplitProtocolError(f"{label} is not a readable regular-file archive") from error
    return {
        "path": str(tar_path),
        "bytes": tar_path.stat().st_size,
        "sha256": sha256_file(tar_path),
        "member_count": len(receipts),
        "members": receipts,
        "complete_member_set": True,
    }


def verify_sdist_inventory(archive_path: str | Path, inventory: dict[str, Any]) -> dict[str, Any]:
    """Require exact Hatch sdist source files plus its one standard PKG-INFO file."""
    validate_inventory(inventory)
    project = inventory["project_metadata"]
    prefix = re.sub(r"[-_.]+", "_", project["name"]) + f"-{project['version']}"
    expected = {f"{prefix}/{row['source']}": row for row in inventory["sdist_source_rows"]}
    return _verify_tar_files(
        archive_path,
        expected,
        label="sdist",
        generated_metadata_path=f"{prefix}/PKG-INFO",
        project_metadata=project,
    )


def verify_gcp_archive_inventory(
    archive_path: str | Path, inventory: dict[str, Any]
) -> dict[str, Any]:
    """Require exact GCP producer files, rejecting every unrelated archive root."""
    validate_inventory(inventory)
    expected = {row["archive"]: row for row in inventory["gcp_source_rows"]}
    return _verify_tar_files(archive_path, expected, label="GCP archive")


def read_installed_member(package_root: str | Path, relative: str) -> bytes:
    """Read one regular installed package member without cwd or symlink fallback."""
    root = Path(package_root).resolve(strict=True)
    rel = _relative(relative, label="installed package member")
    candidate = root.joinpath(*rel.parts)
    current = root
    for part in rel.parts:
        current = current / part
        try:
            info = current.lstat()
        except OSError as error:
            raise SplitProtocolError(f"installed package member is missing: {relative}") from error
        if stat.S_ISLNK(info.st_mode):
            raise SplitProtocolError(f"installed package member contains a symlink: {relative}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise SplitProtocolError(
            f"installed package member escaped target root: {relative}"
        ) from error
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise SplitProtocolError(f"installed package member is not a regular file: {relative}")
    return resolved.read_bytes()


def snapshot_installed_tree(package_root: str | Path) -> dict[str, dict[str, Any]]:
    """Capture a lightweight before-state for every file in the existing purelib target."""
    candidate = Path(package_root)
    if candidate.is_symlink():
        raise SplitProtocolError("installed target snapshot root must not be a symlink")
    root = candidate.resolve(strict=True)
    if not root.is_dir():
        raise SplitProtocolError("installed target snapshot root must be a regular directory")
    result: dict[str, dict[str, Any]] = {}
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in (*dirnames, *filenames):
            path = current_path / name
            rel = path.relative_to(root).as_posix()
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                result[rel] = {"kind": "symlink", "target": os.readlink(path)}
            elif stat.S_ISREG(info.st_mode):
                result[rel] = {
                    "kind": "file",
                    "bytes": info.st_size,
                    "mtime_ns": info.st_mtime_ns,
                    "inode": info.st_ino,
                }
            elif stat.S_ISDIR(info.st_mode):
                continue
            else:
                result[rel] = {"kind": "special", "mode": stat.S_IFMT(info.st_mode)}
    return result


def _installed_tree_observations(root: Path) -> dict[str, dict[str, Any]]:
    return snapshot_installed_tree(root)


def _verify_installed_dist_info(
    root: Path,
    inventory: dict[str, Any],
    observed_members: set[str],
) -> dict[str, dict[str, Any]]:
    """Verify installed standard metadata, source licenses, entry points, and RECORD."""
    project = inventory["project_metadata"]
    info_root = project["dist_info_root"]
    metadata_paths = set(project["dist_info_members"])
    installer_paths = {
        f"{info_root}/INSTALLER",
        f"{info_root}/REQUESTED",
        f"{info_root}/direct_url.json",
    }
    receipts: dict[str, dict[str, Any]] = {}
    data: dict[str, bytes] = {}
    for relative in sorted(observed_members):
        if relative.startswith(f"{info_root}/"):
            raw = read_installed_member(root, relative)
            data[relative] = raw
            receipts[relative] = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
    if set(data) - metadata_paths - installer_paths:
        raise SplitProtocolError("installed dist-info contains a nonstandard member")
    for relative in metadata_paths:
        if relative not in data:
            raise SplitProtocolError(f"installed dist-info is missing standard member {relative}")
    headers = email.parser.BytesParser().parsebytes(data[f"{info_root}/METADATA"])
    if headers.get("Name") != project["name"] or headers.get("Version") != project["version"]:
        raise SplitProtocolError("installed METADATA name/version differs from source project")
    wheel_fields: dict[str, list[str]] = {}
    for line in data[f"{info_root}/WHEEL"].decode("utf-8", "strict").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            wheel_fields.setdefault(key.strip().lower(), []).append(value.strip())
    if (
        wheel_fields.get("wheel-version") != ["1.0"]
        or wheel_fields.get("root-is-purelib") != ["true"]
        or wheel_fields.get("tag") != ["py3-none-any"]
    ):
        raise SplitProtocolError("installed WHEEL metadata differs from universal profile")
    if f"{info_root}/entry_points.txt" in metadata_paths:
        _verify_entry_points(data[f"{info_root}/entry_points.txt"], project["entry_points"])
    for row in project["license_rows"]:
        relative = row["wheel"]
        raw = data.get(relative)
        if raw is None or len(raw) != row["bytes"] or sha256_bytes(raw) != row["sha256"]:
            raise SplitProtocolError(f"installed license member differs from source: {relative}")
    record_name = f"{info_root}/RECORD"
    try:
        record_rows = list(csv.reader(io.StringIO(data[record_name].decode("utf-8", "strict"))))
    except (UnicodeDecodeError, csv.Error) as error:
        raise SplitProtocolError("installed RECORD is malformed") from error
    observed_record: dict[str, tuple[str, str]] = {}
    for row in record_rows:
        if len(row) != 3:
            raise SplitProtocolError("installed RECORD row does not have three fields")
        relative = _relative(row[0], label="installed RECORD member").as_posix()
        if relative in observed_record:
            raise SplitProtocolError("installed RECORD repeats a member")
        observed_record[relative] = (row[1], row[2])
    if set(observed_record) != observed_members:
        raise SplitProtocolError("installed RECORD does not describe the complete target payload")
    for relative in sorted(observed_members):
        digest_field, size_field = observed_record[relative]
        if relative == record_name and not digest_field and not size_field:
            continue
        raw = data[relative] if relative in data else read_installed_member(root, relative)
        expected_digest = "sha256=" + base64.urlsafe_b64encode(
            hashlib.sha256(raw).digest()
        ).decode().rstrip("=")
        if digest_field != expected_digest or size_field != str(len(raw)):
            raise SplitProtocolError(f"installed RECORD differs from member bytes: {relative}")
    return receipts


def worker_write_budget(
    *,
    fast_forward_pack_bytes: int,
    checkout_growth_bytes: int,
    wheel_bytes: int,
    package_target_bytes: int,
    installer_transient_bytes: int,
    logs_and_test_temp_bytes: int,
    request_and_metadata_bytes: int,
) -> dict[str, Any]:
    """Bound new Linux worker writes while preserving the measured 4 GiB reserve."""
    values = {
        "thin_fast_forward_pack": fast_forward_pack_bytes,
        "checkout_growth": checkout_growth_bytes,
        "wheel_transfer": wheel_bytes,
        "installed_package_target": package_target_bytes,
        "installer_transient": installer_transient_bytes,
        "logs_and_test_temp": logs_and_test_temp_bytes,
        "request_and_metadata": request_and_metadata_bytes,
    }
    if any(type(value) is not int or value < 0 for value in values.values()):
        raise SplitProtocolError("worker write budget inputs must be non-negative exact integers")
    total = sum(values.values())
    if total > 262_144_000:
        raise SplitProtocolError(f"worker new-write budget exceeds 250 MiB: {total} bytes")
    return {
        "hard_cap_bytes": 262_144_000,
        "mandatory_free_reserve_bytes": 4_294_967_296,
        "allocations_bytes": values,
        "total_bytes": total,
        "future_write_bytes": total - fast_forward_pack_bytes - checkout_growth_bytes,
        "remaining_after_transfer_bytes": total
        - fast_forward_pack_bytes
        - checkout_growth_bytes
        - wheel_bytes
        - request_and_metadata_bytes,
    }


def require_worker_space(
    *, free_bytes: int, budget: dict[str, Any], after_transfer: bool = False
) -> dict[str, int]:
    """Require post-operation free space to retain the established Linux reserve."""
    if type(free_bytes) is not int or free_bytes < 0:
        raise SplitProtocolError("worker free-space observation is invalid")
    if (
        type(budget) is not dict
        or budget.get("hard_cap_bytes") != 262_144_000
        or budget.get("mandatory_free_reserve_bytes") != 4_294_967_296
        or type(budget.get("allocations_bytes")) is not dict
        or any(
            type(value) is not int or value < 0 for value in budget["allocations_bytes"].values()
        )
        or type(budget.get("total_bytes")) is not int
        or sum(budget["allocations_bytes"].values()) != budget["total_bytes"]
        or type(budget.get("future_write_bytes")) is not int
        or budget["future_write_bytes"]
        != budget["total_bytes"]
        - budget["allocations_bytes"].get("thin_fast_forward_pack", -1)
        - budget["allocations_bytes"].get("checkout_growth", -1)
        or budget.get("remaining_after_transfer_bytes")
        != budget["future_write_bytes"]
        - budget["allocations_bytes"].get("wheel_transfer", -1)
        - budget["allocations_bytes"].get("request_and_metadata", -1)
        or budget["total_bytes"] > budget["hard_cap_bytes"]
    ):
        raise SplitProtocolError("worker write budget receipt is malformed")
    required_future = (
        budget["remaining_after_transfer_bytes"] if after_transfer else budget["future_write_bytes"]
    )
    remaining = free_bytes - required_future
    if remaining < budget["mandatory_free_reserve_bytes"]:
        raise SplitProtocolError(
            f"worker free space would cross the required 4 GiB reserve: {remaining} bytes"
        )
    return {"free_before_bytes": free_bytes, "free_after_budget_bytes": remaining}


def verify_installed_inventory(
    package_root: str | Path,
    inventory: dict[str, Any],
    *,
    before_snapshot: dict[str, dict[str, Any]],
    wheel_path: str | Path | None = None,
) -> dict[str, Any]:
    """Read source payload bytes and reconcile the complete installed target delta."""
    rows = validate_inventory(inventory)
    root = Path(package_root).resolve(strict=True)
    receipts: dict[str, dict[str, Any]] = {}
    for row in rows:
        data = read_installed_member(root, row["wheel"])
        observed = {"bytes": len(data), "sha256": sha256_bytes(data)}
        if observed != {"bytes": row["bytes"], "sha256": row["sha256"]}:
            raise SplitProtocolError(
                f"installed member differs from source inventory: {row['wheel']}"
            )
        receipts[row["wheel"]] = observed
    observed_members: set[str] = set()
    for package_root_name in (
        *inventory["package_roots"],
        inventory["project_metadata"]["dist_info_root"],
    ):
        directory = root / package_root_name
        if directory.is_symlink() or not directory.is_dir():
            raise SplitProtocolError(
                f"installed package/metadata root is absent or symlinked: {package_root_name}"
            )
        for current, dirnames, filenames in os.walk(directory, followlinks=False):
            current_path = Path(current)
            for name in (*dirnames, *filenames):
                path = current_path / name
                if path.is_symlink():
                    raise SplitProtocolError(f"installed package contains a symlink: {path}")
            for name in filenames:
                path = current_path / name
                if not path.is_file():
                    raise SplitProtocolError(f"installed package contains a special file: {path}")
                observed_members.add(path.relative_to(root).as_posix())
    expected_members = {row["wheel"] for row in rows}
    expected_metadata = set(inventory["project_metadata"]["dist_info_members"])
    allowed_installer_metadata = {
        f"{inventory['project_metadata']['dist_info_root']}/INSTALLER",
        f"{inventory['project_metadata']['dist_info_root']}/REQUESTED",
        f"{inventory['project_metadata']['dist_info_root']}/direct_url.json",
    }
    expected_complete = expected_members | expected_metadata
    if (
        not expected_complete <= observed_members
        or observed_members - expected_complete - allowed_installer_metadata
    ):
        raise SplitProtocolError(
            "installed package and dist-info member set differs from source-derived wheel output: "
            f"missing={sorted(expected_complete - observed_members)[:20]} "
            "unexpected="
            f"{sorted(observed_members - expected_complete - allowed_installer_metadata)[:20]}"
        )
    metadata_receipts = _verify_installed_dist_info(root, inventory, observed_members)
    if type(before_snapshot) is not dict:
        raise SplitProtocolError("installed target before-snapshot is malformed")
    after_snapshot = _installed_tree_observations(root)
    before_keys, after_keys = set(before_snapshot), set(after_snapshot)
    changed = {
        name for name in before_keys & after_keys if before_snapshot[name] != after_snapshot[name]
    }
    new = after_keys - before_keys
    removed = before_keys - after_keys
    expected_delta = expected_complete | allowed_installer_metadata
    missing_expected = expected_complete - new
    unexpected = (new | changed) - expected_delta
    if removed or changed or missing_expected or unexpected:
        raise SplitProtocolError(
            "installed target changed outside the complete source-derived wheel delta: "
            f"removed={sorted(removed)[:10]} changed={sorted(changed)[:10]} "
            f"unexpected={sorted(unexpected)[:20]} missing={sorted(missing_expected)[:20]}"
        )
    for relative in allowed_installer_metadata & new:
        raw = read_installed_member(root, relative)
        if relative.endswith("/INSTALLER") and raw not in {b"uv\n", b"uv"}:
            raise SplitProtocolError("installed target has an unexpected INSTALLER marker")
        if relative.endswith("/REQUESTED") and raw:
            raise SplitProtocolError("installed target REQUESTED marker must be empty")
        if relative.endswith("/direct_url.json"):
            value = load_json_bytes(raw, label="installed wheel direct_url.json")
            if wheel_path is None or set(value) != {"url", "archive_info"}:
                raise SplitProtocolError("installed wheel direct_url.json lacks its source binding")
            if value.get("url") != Path(wheel_path).resolve(strict=True).as_uri():
                raise SplitProtocolError(
                    "installed wheel direct URL differs from transferred wheel"
                )
            archive_info = value.get("archive_info")
            wheel_sha = sha256_file(wheel_path)
            if archive_info not in (
                {"hash": f"sha256={wheel_sha}"},
                {"hashes": {"sha256": wheel_sha}},
            ):
                raise SplitProtocolError("installed wheel direct URL hash differs from wheel bytes")
    baseline_sha = sha256_bytes(canonical_json_bytes(before_snapshot))
    return {
        "package_root": str(root),
        "member_count": len(receipts) + len(metadata_receipts),
        "member_inventory_sha256": sha256_bytes(canonical_json_bytes(receipts)),
        "members": receipts,
        "generated_metadata_members": metadata_receipts,
        "whole_target_before_snapshot_sha256": baseline_sha,
        "whole_target_delta_reconciled": True,
    }


def validate_request_binding(
    request: dict[str, Any],
    manifest: dict[str, Any],
    inventory: dict[str, Any],
    *,
    manifest_sha256: str,
    inventory_sha256: str,
    expected_commit: str,
    expected_tree: str,
    wheel_paths: dict[str, str | Path],
) -> dict[str, Any]:
    """Bind all source-derived wheel profiles, selection sets, and worker allocations."""
    if request.get("schema") != REQUEST_SCHEMA:
        raise SplitProtocolError("unsupported split-consumer request schema")
    source = request.get("source")
    if (
        type(source) is not dict
        or source.get("commit") != expected_commit
        or source.get("tree") != expected_tree
    ):
        raise SplitProtocolError("split request source identity differs from checkout")
    if inventory.get("source") != {"commit": expected_commit, "tree": expected_tree}:
        raise SplitProtocolError("package inventory source identity differs from request")
    inventory_rows = validate_inventory(inventory)
    baseline, manifest_assets = _validate_freeze(
        manifest, expected_commit=expected_commit, expected_tree=expected_tree
    )
    expected_assets = sorted(
        (
            {
                "kind": "force_include",
                "source": row["source"],
                "wheel": row["wheel"],
                "bytes": row["bytes"],
                "sha256": row["sha256"],
            }
            for row in manifest_assets
        ),
        key=lambda row: (row["wheel"], row["source"], row["kind"]),
    )
    observed_assets = [row for row in inventory_rows if row["kind"] == "force_include"]
    if observed_assets != expected_assets:
        raise SplitProtocolError("package inventory resources differ from source-freeze manifest")
    if request.get("manifest_sha256") != manifest_sha256:
        raise SplitProtocolError("request manifest digest differs from supplied manifest")
    if request.get("inventory_sha256") != inventory_sha256:
        raise SplitProtocolError("request package inventory digest differs from supplied inventory")
    baseline, _ = _validate_freeze(
        manifest, expected_commit=expected_commit, expected_tree=expected_tree
    )
    if baseline.get("source_sha") != source["commit"]:
        raise SplitProtocolError("worker manifest source commit differs from request")
    selection = request.get("consumer_selection")
    artifacts = request.get("artifacts")
    if type(selection) is not dict or type(artifacts) is not list or not artifacts:
        raise SplitProtocolError("request omits its complete consumer/profile matrix")
    profiles = selection.get("profiles")
    expected_profiles = list(PROFILE_CHAIN_KEYS)
    if (
        type(profiles) is not list
        or profiles != expected_profiles
        or list(wheel_paths) != profiles
        or len(artifacts) != len(profiles)
    ):
        raise SplitProtocolError("source-derived profile and wheel sets differ")
    if set(profiles) != set(PROFILE_CHAIN_KEYS):
        raise SplitProtocolError("selected profiles differ from the three existing Q2 consumers")
    if (
        type(selection.get("primary_node_ids")) is not list
        or not selection["primary_node_ids"]
        or any(type(value) is not str or not value for value in selection["primary_node_ids"])
        or selection["primary_node_ids"] != sorted(set(selection["primary_node_ids"]))
        or type(selection.get("supplemental_node_ids")) is not list
        or not selection["supplemental_node_ids"]
        or any(type(value) is not str or not value for value in selection["supplemental_node_ids"])
        or selection["supplemental_node_ids"] != sorted(set(selection["supplemental_node_ids"]))
        or selection.get("manifest_driven") is not True
    ):
        raise SplitProtocolError("primary or supplemental consumer set is incomplete")
    for field in ("primary", "supplemental"):
        values = selection[f"{field}_node_ids"]
        observed_sha = sha256_bytes(("\n".join(values) + "\n").encode("utf-8"))
        if selection.get(f"{field}_node_ids_sha256") != observed_sha:
            raise SplitProtocolError(f"request {field} node-ID digest differs from its values")
    expected_case_count = len(profiles) * (
        len(selection["primary_node_ids"]) + len(selection["supplemental_node_ids"])
    )
    if (
        type(selection.get("profile_case_count")) is not int
        or selection["profile_case_count"] != expected_case_count
    ):
        raise SplitProtocolError("request consumer profile case count differs from its matrix")
    expected_plan = [
        {"phase": phase, "profile": profile}
        for phase in ("primary", "supplemental")
        for profile in profiles
    ]
    if selection.get("execution_plan") != expected_plan:
        raise SplitProtocolError("request does not represent the complete ordered consumer matrix")
    parsed_artifacts: dict[str, dict[str, Any]] = {}
    total_wheel_bytes = 0
    total_target_bytes = 0
    largest_wheel_bytes = 0
    artifact_records: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        if type(artifact) is not dict:
            raise SplitProtocolError("consumer profile artifact row is malformed")
        profile = artifact.get("profile")
        if profile not in profiles or profile in parsed_artifacts:
            raise SplitProtocolError("consumer profile artifact is absent or duplicated")
        wheel = Path(wheel_paths[profile])
        wheel_rel = _relative(artifact.get("file"), label="consumer wheel transfer path")
        if wheel_rel.as_posix() != f"wheels/{profile}/{wheel.name}" or not wheel.name.endswith(
            ".whl"
        ):
            raise SplitProtocolError("consumer wheel path is not profile-qualified")
        if (
            type(artifact.get("bytes")) is not int
            or artifact["bytes"] != wheel.stat().st_size
            or type(artifact.get("sha256")) is not str
            or not _SHA256.fullmatch(artifact["sha256"])
            or sha256_file(wheel) != artifact["sha256"]
        ):
            raise SplitProtocolError(f"{profile} wheel bytes differ from the host profile receipt")
        chain_key = PROFILE_CHAIN_KEYS[profile]
        if artifact.get("chain_key") != chain_key:
            raise SplitProtocolError(f"{profile} points at a different producer artifact")
        parsed_artifacts[profile] = dict(artifact)
        artifact_records[profile] = {
            "file": wheel_rel.as_posix(),
            "bytes": wheel.stat().st_size,
            "sha256": artifact["sha256"],
            "uncompressed_bytes": wheel_uncompressed_bytes(wheel),
        }
        total_wheel_bytes += wheel.stat().st_size
        total_target_bytes += artifact_records[profile]["uncompressed_bytes"]
        largest_wheel_bytes = max(largest_wheel_bytes, wheel.stat().st_size)
    if [artifact.get("profile") for artifact in artifacts] != profiles:
        raise SplitProtocolError(
            "wheel artifact rows do not preserve the source-derived profile order"
        )
    chain = request.get("artifact_chain")
    expected_chain_fields = {
        "source_archive_sha256",
        "source_wheel_sha256",
        "source_sdist_sha256",
        "rebuilt_sdist_wheel_sha256",
        "gcp_archive_sha256",
        "rebuilt_gcp_wheel_sha256",
    }
    if (
        type(chain) is not dict
        or set(chain) != expected_chain_fields
        or any(type(value) is not str or not _SHA256.fullmatch(value) for value in chain.values())
    ):
        raise SplitProtocolError("request artifact chain is incomplete")
    for profile, artifact in parsed_artifacts.items():
        if artifact["sha256"] != chain[PROFILE_CHAIN_KEYS[profile]]:
            raise SplitProtocolError(f"{profile} differs from the recorded source artifact chain")
    budget = request.get("worker_write_budget")
    target_overhead = request.get("installed_target_overhead_bytes")
    if (
        type(target_overhead) is not dict
        or set(target_overhead) != {"origin_gate", "origin_plugin", "installer_metadata_reserve"}
        or type(target_overhead.get("origin_gate")) is not int
        or target_overhead["origin_gate"] < 0
        or type(target_overhead.get("origin_plugin")) is not int
        or target_overhead["origin_plugin"] < 0
        or target_overhead.get("installer_metadata_reserve")
        != MAX_INSTALLER_METADATA_OVERHEAD_BYTES
    ):
        raise SplitProtocolError("installed target overhead receipt is malformed")
    if type(budget) is not dict:
        raise SplitProtocolError("request omits the measured worker write budget")
    allocation = budget.get("allocations_bytes")
    expected_allocations = {
        "thin_fast_forward_pack",
        "checkout_growth",
        "wheel_transfer",
        "installed_package_target",
        "installer_transient",
        "logs_and_test_temp",
        "request_and_metadata",
    }
    if (
        budget.get("hard_cap_bytes") != 262_144_000
        or budget.get("mandatory_free_reserve_bytes") != 4_294_967_296
        or type(allocation) is not dict
        or set(allocation) != expected_allocations
        or any(type(value) is not int or value < 0 for value in allocation.values())
        or type(budget.get("total_bytes")) is not int
        or budget["total_bytes"] != sum(allocation.values())
        or budget["total_bytes"] > budget["hard_cap_bytes"]
        or budget.get("future_write_bytes")
        != budget["total_bytes"]
        - allocation.get("thin_fast_forward_pack", -1)
        - allocation.get("checkout_growth", -1)
        or budget.get("remaining_after_transfer_bytes")
        != budget["future_write_bytes"]
        - allocation.get("wheel_transfer", -1)
        - allocation.get("request_and_metadata", -1)
        or allocation.get("wheel_transfer") != total_wheel_bytes
        or allocation.get("installed_package_target")
        != total_target_bytes
        + len(profiles)
        * (
            target_overhead["origin_gate"]
            + target_overhead["origin_plugin"]
            + target_overhead["installer_metadata_reserve"]
        )
        or allocation.get("installer_transient") != largest_wheel_bytes
    ):
        raise SplitProtocolError("worker write budget does not match the complete profile matrix")
    return {
        "source": dict(source),
        "manifest_sha256": manifest_sha256,
        "inventory_sha256": inventory_sha256,
        "artifacts": artifact_records,
        "artifact_chain": dict(chain),
    }
