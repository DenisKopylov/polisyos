#!/usr/bin/env python3
"""Enumerate current Hatchling sdist inputs without building an artifact."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import stat
import sys
from pathlib import Path, PurePosixPath

from hatchling.builders.sdist import SdistBuilder


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fail(message: str) -> None:
    raise ValueError(message)


def _relative(root: Path, path: Path, label: str) -> str:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError(f"{label} escapes the source root: {path}") from error
    parsed = PurePosixPath(relative)
    if (
        not relative
        or parsed.is_absolute()
        or parsed.as_posix() != relative
        or ".." in parsed.parts
    ):
        _fail(f"{label} is not a canonical product-relative path: {relative!r}")
    return relative


def _check_path(root: Path, path: Path, *, directory: bool, label: str) -> str:
    relative = _relative(root, path, label)
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        try:
            info = current.lstat()
        except OSError as error:
            raise ValueError(f"{label} is missing: {relative}") from error
        if stat.S_ISLNK(info.st_mode):
            _fail(f"{label} contains a symlink: {relative}")
    info = path.lstat()
    if directory and not stat.S_ISDIR(info.st_mode):
        _fail(f"{label} is not a regular directory: {relative}")
    if not directory and not stat.S_ISREG(info.st_mode):
        _fail(f"{label} is not a regular file: {relative}")
    return relative


def _protected_source(relative: str) -> bool:
    return PurePosixPath(relative).parts[0] == "production_data"


def _api_hashes(builder: SdistBuilder) -> dict[str, str]:
    import hatchling
    import hatchling.builders.constants as builder_constants
    from hatchling.builders.config import BuilderConfig
    from hatchling.builders.plugin.interface import BuilderInterface
    from hatchling.builders.utils import safe_walk
    from hatchling.utils import constants as hatch_constants

    package_root = Path(hatchling.__file__).resolve().parent
    owners = {
        "builders/config.py": BuilderConfig,
        "builders/constants.py": builder_constants,
        "builders/plugin/interface.py": BuilderInterface,
        "builders/sdist.py": SdistBuilder,
        "builders/utils.py": safe_walk,
        "utils/constants.py": hatch_constants,
        "metadata/core.py": type(builder.metadata.core),
    }
    hashes: dict[str, str] = {}
    for expected, owner in owners.items():
        source = Path(getattr(owner, "__file__", "") or inspect.getsourcefile(owner) or "").resolve(
            strict=True
        )
        try:
            relative = source.relative_to(package_root).as_posix()
        except ValueError as error:
            raise ValueError(f"Hatchling API source is outside its package: {source}") from error
        if relative != expected:
            raise ValueError(f"Hatchling API source moved unexpectedly: {relative} != {expected}")
        hashes[f"hatchling/{relative}"] = _sha256(source)
    return hashes


def _selected_inputs(
    builder: SdistBuilder,
    root: Path,
    force_sources: set[str],
    default_force_sources: set[str],
    default_vcs_sources: set[str],
) -> tuple[dict[str, str], dict[str, str], set[str]]:
    config = builder.config
    selected: dict[str, str] = {}
    forced: dict[str, str] = {}
    default_sources: set[str] = set()
    force_source_paths = {Path(os.path.abspath(source)).as_posix() for source in force_sources}

    for item in builder.recurse_included_files():
        source_path = Path(item.path)
        relative = _check_path(root, source_path, directory=False, label="selected sdist source")
        if item.relative_path != relative:
            _fail(
                "Hatchling selected-source path disagrees with its rooted source path: "
                f"{item.relative_path!r} != {relative!r}"
            )
        distribution = item.distribution_path
        if distribution != relative:
            _fail(
                "sdist source remapping is not represented by this inventory: "
                f"{relative} -> {distribution}"
            )
        if _protected_source(relative):
            _fail(f"selected sdist source is independently protected: {relative}")

        source_key = Path(os.path.abspath(item.path)).as_posix()
        if source_key in force_source_paths:
            if config.path_is_excluded(relative) and not (
                source_key in default_force_sources and source_key in default_vcs_sources
            ):
                _fail(f"force-included sdist source overrides a source exclusion: {relative}")
            prior = forced.setdefault(relative, distribution)
            if prior != distribution:
                _fail(f"force-included sdist source has conflicting paths: {relative}")
            if source_key in default_force_sources:
                default_sources.add(relative)
        else:
            prior = selected.setdefault(relative, distribution)
            if prior != distribution:
                _fail(f"selected sdist source has conflicting distribution paths: {relative}")

    return selected, forced, default_sources


def main() -> int:
    if len(sys.argv) != 2:
        _fail("expected exactly one source-root argument")
    root = Path(sys.argv[1]).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        _fail("source root must be an existing regular directory")

    from hatchling.builders.sdist import SdistBuilder

    builder = SdistBuilder(str(root))
    config = builder.config
    include_paths = config.target_config.get("include")
    if include_paths is None:
        include_paths = config.build_config.get("include")
    if (
        type(include_paths) is not list
        or any(type(value) is not str or not value for value in include_paths)
        or any(any(character in value for character in "*?[]") for value in include_paths)
    ):
        _fail("current sdist include inputs are not a literal supported list")

    build_data = builder.get_default_build_data()
    builder.set_build_data_defaults(build_data)
    hooks = builder.get_build_hooks(str(root))
    if hooks:
        _fail(f"active sdist build hooks are not source-enumerable: {sorted(hooks)}")

    default_force_sources = {
        Path(os.path.abspath(source)).as_posix() for source in build_data["force_include"]
    }
    default_vcs_sources = {
        Path(os.path.abspath(source)).as_posix()
        for paths in config.vcs_exclusion_files.values()
        for source in paths
    }

    with config.set_build_data(build_data):
        force_map = config.get_force_include()
        selected, forced, default_sources = _selected_inputs(
            builder,
            root,
            set(force_map),
            default_force_sources,
            default_vcs_sources,
        )

    all_files = dict(selected)
    for source, distribution in forced.items():
        prior = all_files.setdefault(source, distribution)
        if prior != distribution:
            _fail(f"sdist producer maps one source to multiple members: {source}")

    api_hashes = _api_hashes(builder)
    hatch_path = root / "hatch.toml"
    _check_path(root, hatch_path, directory=False, label="Hatch config")
    result = {
        "schema": "policyos.e02.q2.hatchling-sdist-selection.v1",
        "hatch_config_sha256": _sha256(hatch_path),
        "api_source_sha256": api_hashes,
        "license_files": list(builder.metadata.core.license_files),
        "configured_build_hooks": sorted(hooks),
        "default_force_include_sources": sorted(default_sources),
        "explicit_force_include_sources": sorted(set(forced) - default_sources),
        "selected_sources": sorted(selected),
        "force_include_sources": sorted(forced),
        "files": [
            {"source": source, "distribution": all_files[source]} for source in sorted(all_files)
        ],
    }
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        sys.stderr.write(f"{type(error).__name__}: {error}\n")
        raise SystemExit(2) from error
