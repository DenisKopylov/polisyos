#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PRODUCT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
WORKSPACE_ROOT="$(cd "${PRODUCT_ROOT}/.." && pwd -P)"
OUT_DIR="${OUT_DIR:-${PRODUCT_ROOT}/_build/ops/gcp_bundle}"
BUCKET_NAME="${BUCKET_NAME:-}"
UPLOAD="${UPLOAD:-0}"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
SOURCE_GIT_ROOT="$(GIT_NO_REPLACE_OBJECTS=1 git -C "${WORKSPACE_ROOT}" rev-parse --show-toplevel 2> /dev/null || true)"
if [ -z "${SOURCE_GIT_ROOT}" ] || [ "$(cd "${SOURCE_GIT_ROOT}" && pwd -P)" != "${WORKSPACE_ROOT}" ]; then
  echo "GCP source archive requires a committed Git source tree at the selected workspace root" >&2
  exit 1
fi
GIT_COMMIT="$(GIT_NO_REPLACE_OBJECTS=1 git -C "${WORKSPACE_ROOT}" rev-parse --verify HEAD 2> /dev/null || true)"
if [ -z "${GIT_COMMIT}" ]; then
  echo "GCP source archive requires a committed Git source tree" >&2
  exit 1
fi
GIT_SHA="$(GIT_NO_REPLACE_OBJECTS=1 git -C "${WORKSPACE_ROOT}" rev-parse --short "${GIT_COMMIT}")"
ARCHIVE_PATH="${OUT_DIR}/policy-engine-${TIMESTAMP}-${GIT_SHA}.tar.gz"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "${OUT_DIR}"

"${PYTHON_BIN}" - "${WORKSPACE_ROOT}" "${ARCHIVE_PATH}" "${GIT_COMMIT}" << 'PY'
from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path, PurePosixPath

workspace_root = Path(sys.argv[1])
archive_path = Path(sys.argv[2])
git_commit = sys.argv[3]
product_root = workspace_root / "policy-engine"
git_env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"}
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


def git_output(*args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(workspace_root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=git_env,
        ).stdout
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode(errors="replace").strip()
        raise SystemExit(f"Unable to resolve committed GCP archive source: {detail}") from error


manifest = tomllib.loads(
    git_output("show", f"{git_commit}:policy-engine/hatch.toml").decode("utf-8")
)
force_include = manifest["build"]["targets"]["wheel"]["force-include"]


def force_include_source_path(source: str) -> Path:
    relative_source = Path(source)
    if relative_source.is_absolute() or not relative_source.parts or ".." in relative_source.parts:
        raise SystemExit(f"Invalid Hatch wheel force-include source: {source}")
    if relative_source.parts[0].casefold() == "production_data":
        raise SystemExit(f"Refusing protected production_data force-include source: {source}")
    return product_root / relative_source


for source in force_include:
    source_path = force_include_source_path(source)
    include_paths.append(source_path.relative_to(workspace_root).as_posix())
include_paths = list(dict.fromkeys(include_paths))

skip_parts = {"__pycache__", ".git"}
skip_suffixes = {".pyc", ".pyo"}
skip_names = {".DS_Store"}


def should_skip(name: str) -> bool:
    parts = PurePosixPath(name).parts
    if not parts or parts[0] != "policy-engine":
        return False
    product_parts = parts[1:]
    if any(part in skip_parts for part in product_parts):
        return True
    if PurePosixPath(name).name in skip_names:
        return True
    if PurePosixPath(name).suffix in skip_suffixes:
        return True
    return any(part.endswith(".egg-info") for part in product_parts)


def is_within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


pathspecs = [f":(top,literal){path}" for path in include_paths]
for relative_path in include_paths:
    try:
        git_output("cat-file", "-e", f"{git_commit}:{relative_path}")
    except SystemExit as error:
        raise SystemExit(f"Missing committed GCP archive source: {relative_path}") from error

untracked_sources = git_output(
    "ls-files", "--others", "--full-name", "-z", "--", *pathspecs
).split(b"\0")
for raw_name in untracked_sources:
    if not raw_name:
        continue
    name = os.fsdecode(raw_name)
    if not should_skip(name):
        raise SystemExit(f"Uncommitted GCP archive source is outside the source freeze: {name}")

listing = git_output("ls-tree", "-r", "-z", "--full-tree", git_commit, "--", *pathspecs)
entries: dict[str, tuple[str, str]] = {}
for record in listing.split(b"\0"):
    if not record:
        continue
    metadata, raw_name = record.split(b"\t", 1)
    mode, object_type, object_id = metadata.decode("ascii").split()
    name = os.fsdecode(raw_name)
    if not name.startswith("policy-engine/") or ".." in PurePosixPath(name).parts:
        raise SystemExit(f"Invalid committed GCP archive member: {name}")
    if not any(is_within(name, root) for root in include_paths):
        raise SystemExit(f"Unexpected committed GCP archive member: {name}")
    if should_skip(name):
        continue
    if object_type != "blob" or mode not in {"100644", "100755"}:
        raise SystemExit(f"Invalid committed GCP archive member type: {name}")
    entries[name] = (mode, object_id)

root_kinds: dict[str, str] = {}
for relative_path in include_paths:
    kind = git_output("cat-file", "-t", f"{git_commit}:{relative_path}").decode().strip()
    root_kinds[relative_path] = kind
    if kind not in {"blob", "tree"}:
        raise SystemExit(f"Invalid committed GCP archive source type: {relative_path}")
    if kind == "blob" and f"{relative_path}" not in entries:
        if not should_skip(relative_path):
            raise SystemExit(f"Missing committed GCP archive file: {relative_path}")
    if kind == "tree" and not any(is_within(name, relative_path) for name in entries):
        if not should_skip(relative_path):
            raise SystemExit(f"Empty committed GCP archive directory: {relative_path}")


def directory_members() -> list[str]:
    directories: set[str] = set()
    for root, kind in root_kinds.items():
        if kind != "tree" or should_skip(root):
            continue
        directories.add(root)
        for name in entries:
            if not is_within(name, root) or name == root:
                continue
            parent = PurePosixPath(name).parent.as_posix()
            while is_within(parent, root):
                directories.add(parent)
                if parent == root:
                    break
                parent = PurePosixPath(parent).parent.as_posix()
    return sorted(directories, key=lambda name: (name.count("/"), name))


commit_time = int(git_output("show", "-s", "--format=%ct", git_commit).decode().strip())
creation_flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
if hasattr(os, "O_NOFOLLOW"):
    creation_flags |= os.O_NOFOLLOW
try:
    archive_fd = os.open(archive_path, creation_flags, 0o666)
except FileExistsError as error:
    raise SystemExit(f"Refusing existing GCP archive destination: {archive_path}") from error
upload_fd = os.dup(archive_fd) if os.environ.get("UPLOAD", "0") == "1" else None


class LimitedReader:
    def __init__(self, stream, size: int) -> None:
        self._stream = stream
        self.remaining = size

    def read(self, size: int = -1) -> bytes:
        if self.remaining == 0:
            return b""
        if size < 0 or size > self.remaining:
            size = self.remaining
        data = self._stream.read(size)
        if not data:
            raise OSError("Git object stream ended before the declared blob size")
        self.remaining -= len(data)
        return data


cat_file = subprocess.Popen(
    ["git", "-C", str(workspace_root), "cat-file", "--batch"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=git_env,
)
try:
    with os.fdopen(archive_fd, "wb") as archive_stream:
        with tarfile.open(fileobj=archive_stream, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
            for name in directory_members():
                directory = tarfile.TarInfo(name + "/")
                directory.type = tarfile.DIRTYPE
                directory.mode = 0o755
                directory.uid = directory.gid = 0
                directory.uname = directory.gname = ""
                directory.mtime = commit_time
                tar.addfile(directory)

            assert cat_file.stdin is not None
            assert cat_file.stdout is not None
            for name, (mode, object_id) in sorted(entries.items()):
                cat_file.stdin.write(object_id.encode("ascii") + b"\n")
                cat_file.stdin.flush()
                header = cat_file.stdout.readline().split()
                if len(header) != 3 or header[1] != b"blob":
                    raise OSError(f"Unable to read committed GCP source blob: {name}")
                size = int(header[2])
                info = tarfile.TarInfo(name)
                info.size = size
                info.mode = 0o755 if mode == "100755" else 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = commit_time
                source = LimitedReader(cat_file.stdout, size)
                tar.addfile(info, source)
                if source.remaining != 0 or cat_file.stdout.read(1) != b"\n":
                    raise OSError(f"Invalid committed GCP source blob framing: {name}")
    cat_file.stdin.close()
    stderr = cat_file.stderr.read() if cat_file.stderr is not None else b""
    status = cat_file.wait()
    if status != 0:
        raise OSError(stderr.decode(errors="replace").strip() or "git cat-file failed")
except Exception as error:
    if cat_file.stdin is not None and not cat_file.stdin.closed:
        cat_file.stdin.close()
    cat_file.wait()
    if upload_fd is not None:
        os.close(upload_fd)
    raise SystemExit(
        f"GCP archive creation failed; partial output retained at {archive_path}: {error}"
    ) from error

if upload_fd is not None:
    try:
        bucket_name = os.environ.get("BUCKET_NAME", "")
        if not bucket_name:
            raise SystemExit(
                f"Set BUCKET_NAME when UPLOAD=1; local archive retained at {archive_path}"
            )
        destination = f"gs://{bucket_name}/bootstrap/repo/{archive_path.name}"
        os.lseek(upload_fd, 0, os.SEEK_SET)
        try:
            upload = subprocess.run(
                ["gcloud", "storage", "cp", "-", destination],
                stdin=upload_fd,
                check=False,
            )
        except OSError as error:
            raise SystemExit(
                f"GCP upload failed; local archive retained at {archive_path}: {error}"
            ) from error
        if upload.returncode != 0:
            raise SystemExit(
                f"GCP upload failed with exit {upload.returncode}; local archive retained at {archive_path}"
            )
        print(f"Uploaded {destination}")
    finally:
        os.close(upload_fd)
PY

echo "Created ${ARCHIVE_PATH} from committed source ${GIT_COMMIT}"
