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
    source_path = product_root / relative_source
    component = product_root
    for part in relative_source.parts:
        component = component / part
        if component.is_symlink():
            raise SystemExit(f"Invalid Hatch wheel force-include source: {source}")
    if not source_path.resolve().is_relative_to(product_root.resolve()):
        raise SystemExit(f"Invalid Hatch wheel force-include source: {source}")
    if not source_path.is_file() and not source_path.is_dir():
        raise SystemExit(f"Invalid Hatch wheel force-include source: {source}")
    if source_path.is_dir():
        def fail_walk(error: OSError) -> None:
            raise error

        for directory, dirnames, filenames in os.walk(
            source_path, followlinks=False, onerror=fail_walk
        ):
            for name in [*dirnames, *filenames]:
                member = Path(directory) / name
                if member.is_symlink() or (not member.is_file() and not member.is_dir()):
                    raise SystemExit(f"Invalid Hatch wheel force-include source: {source}")
    return source_path


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


def iter_paths(root: Path):
    if root.is_file():
        if not should_skip(root):
            yield root
        return

    if not should_skip(root):
        yield root

    for path in sorted(root.rglob("*")):
        if should_skip(path):
            continue
        yield path


with tarfile.open(archive_path, "w:gz", format=tarfile.GNU_FORMAT) as tar:
    for rel in include_paths:
        source = workspace_root / rel
        for path in iter_paths(source):
            tar.add(path, arcname=path.relative_to(workspace_root), recursive=False)
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
