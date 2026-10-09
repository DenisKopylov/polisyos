#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PRODUCT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
WORKSPACE_ROOT="$(cd "${PRODUCT_ROOT}/.." && pwd)"
OUT_DIR="${OUT_DIR:-${PRODUCT_ROOT}/_build/ops/gcp_bundle}"
BUCKET_NAME="${BUCKET_NAME:-}"
UPLOAD="${UPLOAD:-0}"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
GIT_SHA="$(git -C "${WORKSPACE_ROOT}" rev-parse --short HEAD 2> /dev/null || echo local)"
ARCHIVE_PATH="${OUT_DIR}/policy-engine-${TIMESTAMP}-${GIT_SHA}.tar.gz"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "${OUT_DIR}"

"${PYTHON_BIN}" - "${WORKSPACE_ROOT}" "${ARCHIVE_PATH}" << 'PY'
from __future__ import annotations

import os
import stat
import sys
import tarfile
import tomllib
from pathlib import Path

workspace_root = Path(sys.argv[1])
archive_path = Path(sys.argv[2])
product_root = workspace_root / "policy-engine"
include_paths = [
    "policy-engine/README.md",
    "policy-engine/pyproject.toml",
    "policy-engine/hatch.toml",
    "policy-engine/uv.lock",
    "policy-engine/src",
    "policy-engine/tools",
    "policy-engine/schemas",
    "policy-engine/ops",
]
manifest = tomllib.loads((product_root / "hatch.toml").read_text())
force_include = manifest["build"]["targets"]["wheel"]["force-include"]


def force_include_source_path(source: str) -> Path:
    relative_source = Path(source)
    if (
        relative_source.is_absolute()
        or not relative_source.parts
        or ".." in relative_source.parts
    ):
        raise SystemExit(f"Invalid Hatch wheel force-include source: {source}")
    return product_root / relative_source


for source in force_include:
    source_path = force_include_source_path(source)
    include_paths.append(str(source_path.relative_to(workspace_root)))
include_paths = list(dict.fromkeys(include_paths))
skip_parts = {"__pycache__", ".git"}
skip_suffixes = {".pyc", ".pyo"}
skip_names = {".DS_Store"}


def should_skip(path: Path) -> bool:
    if any(part in skip_parts for part in path.parts):
        return True
    if path.name in skip_names:
        return True
    if path.suffix in skip_suffixes:
        return True
    if ".egg-info" in path.parts:
        return True
    return False


def should_skip_subtree(path: Path) -> bool:
    return any(part in skip_parts for part in path.parts) or ".egg-info" in path.parts


def iter_paths(root: Path):
    if should_skip_subtree(root):
        return

    try:
        mode = root.lstat().st_mode
    except FileNotFoundError:
        if not should_skip(root):
            yield root
        return
    if not should_skip(root):
        yield root
    if not stat.S_ISDIR(mode):
        return

    try:
        with os.scandir(root) as entries:
            children = []
            for entry in entries:
                path = Path(entry.path)
                if should_skip(path):
                    continue
                children.append((path, entry.stat(follow_symlinks=False).st_mode))
    except OSError as error:
        raise SystemExit(f"Unable to enumerate GCP archive source: {root}: {error}")

    for path, child_mode in sorted(children, key=lambda child: child[0].name):
        if stat.S_ISDIR(child_mode):
            if not should_skip_subtree(path):
                yield from iter_paths(path)
        elif not should_skip(path):
            yield path


def archive_name(path: Path) -> str:
    return path.relative_to(workspace_root).as_posix()


try:
    product_mode = product_root.lstat().st_mode
    product_root_resolved = product_root.resolve(strict=True)
except OSError as error:
    raise SystemExit(f"Invalid GCP archive product root: {error}") from error
if stat.S_ISLNK(product_mode) or not stat.S_ISDIR(product_mode):
    raise SystemExit("Invalid GCP archive product root")


def validate_archive_member(path: Path) -> None:
    name = archive_name(path)
    try:
        relative_path = path.relative_to(product_root)
    except ValueError as error:
        raise SystemExit(f"Invalid GCP archive member: {name} (outside product root)") from error

    current = product_root
    parts = relative_path.parts
    if not parts:
        raise SystemExit(f"Invalid GCP archive member: {name} (product root is not an archive member)")

    for index, part in enumerate(parts):
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError as error:
            raise SystemExit(f"Invalid GCP archive member: {name} (path unavailable)") from error
        if stat.S_ISLNK(mode):
            raise SystemExit(f"Invalid GCP archive member: {name} (symlink component)")
        is_final = index == len(parts) - 1
        if not is_final and not stat.S_ISDIR(mode):
            raise SystemExit(f"Invalid GCP archive member: {name} (non-directory path component)")
        if is_final and not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise SystemExit(f"Invalid GCP archive member: {name} (non-regular member)")

    try:
        if not current.resolve(strict=True).is_relative_to(product_root_resolved):
            raise SystemExit(f"Invalid GCP archive member: {name} (outside product root)")
    except OSError as error:
        raise SystemExit(f"Invalid GCP archive member: {name} (path unavailable)") from error


archive_members = []
seen_members = set()
for rel in include_paths:
    source = workspace_root / rel
    for path in iter_paths(source):
        name = archive_name(path)
        if name in seen_members:
            continue
        seen_members.add(name)
        archive_members.append((path, Path(name)))

for path, _ in archive_members:
    validate_archive_member(path)

with tarfile.open(archive_path, "w:gz", format=tarfile.GNU_FORMAT) as tar:
    for path, name in archive_members:
        tar.add(path, arcname=name, recursive=False)
PY

echo "Created ${ARCHIVE_PATH}"

if [ "${UPLOAD}" = "1" ]; then
  if [ -z "${BUCKET_NAME}" ]; then
    echo "Set BUCKET_NAME when UPLOAD=1"
    exit 1
  fi
  DEST="gs://${BUCKET_NAME}/bootstrap/repo/$(basename "${ARCHIVE_PATH}")"
  gcloud storage cp "${ARCHIVE_PATH}" "${DEST}"
  echo "Uploaded ${DEST}"
fi
