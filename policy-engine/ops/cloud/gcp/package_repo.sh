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
product_root = workspace_root / "policy-engine"
config_path = product_root / "hatch.toml"
with config_path.open("rb") as config_file:
    hatch_config = tomllib.load(config_file)
force_include = (
    hatch_config.get("build", {})
    .get("targets", {})
    .get("wheel", {})
    .get("force-include", {})
)
if not isinstance(force_include, dict):
    raise SystemExit("Configured Hatch wheel force-include must be a mapping")
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


archive_members: dict[str, Path] = {}
for rel in include_paths:
    source = workspace_root / rel
    if not source.exists():
        raise SystemExit(f"Configured GCP package input is missing: {rel}")
    for path in iter_paths(source):
        archive_members[path.relative_to(workspace_root).as_posix()] = path

for source in force_include:
    if not isinstance(source, str) or not source:
        raise SystemExit("Configured Hatch wheel force-include source must be a nonempty path")
    candidate = Path(source)
    if not candidate.is_absolute():
        candidate = product_root / candidate
    resolved_source = candidate.resolve()
    try:
        resolved_source.relative_to(product_root.resolve())
    except ValueError as error:
        raise SystemExit(
            f"Configured Hatch wheel force-include source escapes policy-engine: {source}"
        ) from error
    if not resolved_source.exists():
        raise SystemExit(
            f"Configured Hatch wheel force-include source is missing: {source}"
        )
    if not resolved_source.is_file() and not resolved_source.is_dir():
        raise SystemExit(
            f"Configured Hatch wheel force-include source is not a file or directory: {source}"
        )
    for path in iter_paths(resolved_source):
        archive_members[path.relative_to(workspace_root).as_posix()] = path

with tarfile.open(archive_path, "w:gz", format=tarfile.GNU_FORMAT) as tar:
    for arcname, path in sorted(archive_members.items()):
        tar.add(path, arcname=arcname, recursive=False)
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
