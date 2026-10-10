#!/usr/bin/env python3
"""Run the frozen Q2 source -> archive -> rebuilt wheel consumer wave."""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
HANDOFF_ROOT = HERE.parent
MANIFEST_PATH = HANDOFF_ROOT / "installed-wave-manifest.json"
REQUIRED_PRODUCT = "policy-engine"
PROFILE_TARGET_ROOT = "polisyos/foundry/methods/catalog/causal/_dowhy_profile/"
RESOURCE_TARGET_ROOTS = (
    "polisyos/data_forge/domains/catalog/_resources/",
    "polisyos/foundry/methods/catalog/_resources/",
)
FORBIDDEN_ARCHIVE_SIBLING_ROOTS = (
    "policy-engine/data/dataset_catalog/",
    "policy-engine/architecture/production_quality/",
    "policy-engine/workers/dowhy-014/",
)


class WaveFailure(RuntimeError):
    """Raised when a required frozen-wave invariant is not established."""


class HashingReader:
    """A read-only stream wrapper which hashes bytes consumed by tarfile."""

    def __init__(self, stream: Any) -> None:
        self.stream = stream
        self.digest = hashlib.sha256()
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        data = self.stream.read(size)
        self.digest.update(data)
        self.bytes_read += len(data)
        return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_stem: Path,
    check: bool = True,
    stream_output: bool = False,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command while retaining complete stdout/stderr, including on timeout."""
    log_stem.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = log_stem.with_suffix(".stdout.txt")
    stderr_path = log_stem.with_suffix(".stderr.txt")
    timed_out = False
    try:
        if stream_output:
            with stdout_path.open("wb") as stdout_stream, stderr_path.open("wb") as stderr_stream:
                raw_result = subprocess.run(
                    argv,
                    cwd=cwd,
                    env=env,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                    check=False,
                    timeout=timeout_seconds,
                )
            result = subprocess.CompletedProcess(
                argv,
                raw_result.returncode,
                stdout_path.read_text(encoding="utf-8", errors="replace"),
                stderr_path.read_text(encoding="utf-8", errors="replace"),
            )
        else:
            result = subprocess.run(
                argv,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
            stdout_path.write_text(result.stdout, encoding="utf-8")
            stderr_path.write_text(result.stderr, encoding="utf-8")
    except subprocess.TimeoutExpired as error:
        timed_out = True
        if not stream_output:
            for path, partial in ((stdout_path, error.stdout), (stderr_path, error.stderr)):
                if isinstance(partial, str):
                    path.write_bytes(partial.encode("utf-8"))
                elif isinstance(partial, bytes):
                    path.write_bytes(partial)
                else:
                    path.write_bytes(b"")
        result = subprocess.CompletedProcess(
            argv,
            None,
            stdout_path.read_text(encoding="utf-8", errors="replace"),
            stderr_path.read_text(encoding="utf-8", errors="replace"),
        )
    json_write(
        log_stem.with_suffix(".command.json"),
        {
            "argv": argv,
            "cwd": str(cwd),
            "returncode": result.returncode,
            "stream_output": stream_output,
            "timeout_seconds": timeout_seconds,
            "timed_out": timed_out,
            "pythonpath_unset": "PYTHONPATH" not in env,
            "controlled_environment": {
                key: value
                for key, value in sorted(env.items())
                if key.startswith("E02_")
                or key
                in {
                    "OUT_DIR",
                    "UPLOAD",
                    "PYTHON_BIN",
                    "UV_PROJECT_ENVIRONMENT",
                }
            },
        },
    )
    if timed_out:
        raise WaveFailure(
            f"Command timed out after {timeout_seconds}s; full output retained at {log_stem}"
        )
    if check and result.returncode:
        raise WaveFailure(
            f"Command failed ({result.returncode}); full output retained at {log_stem}"
        )
    return result


def clean_child_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PYTHON",
    ):
        env.pop(key, None)
    for key in tuple(env):
        if key.startswith("E02_"):
            env.pop(key)
    return env


def require_absolute_file(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise WaveFailure(f"{label} must be an absolute path: {value}")
    if not path.is_file():
        raise WaveFailure(f"{label} is unavailable: {path}")
    # Keep a venv's symlinked bin/python spelling; resolving it would escape the venv.
    return Path(os.path.abspath(path))


def git_text(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise WaveFailure(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def frozen_source_preflight(repo: Path, source_sha: str, source_tree: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise WaveFailure("--source-sha must be the actual full 40-character frozen commit")
    if not re.fullmatch(r"[0-9a-f]{40}", source_tree):
        raise WaveFailure("--source-tree must be the actual full 40-character frozen tree")
    head = git_text(repo, "rev-parse", "HEAD")
    if head != source_sha:
        raise WaveFailure(f"HEAD differs from the supplied freeze: HEAD={head}, supplied={source_sha}")
    actual_tree = git_text(repo, "rev-parse", f"{source_sha}^{{tree}}")
    if actual_tree != source_tree:
        raise WaveFailure(
            f"commit tree differs from supplied freeze: actual={actual_tree}, supplied={source_tree}"
        )
    if git_text(repo, "symbolic-ref", "-q", "HEAD") == "":
        raise WaveFailure("frozen source checkout is detached; attach the intended branch first")
    tracked_changes = git_text(repo, "status", "--porcelain=v1", "--untracked-files=no")
    if tracked_changes:
        raise WaveFailure("tracked source changes remain after freeze; no build was started")


def safe_relative_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise WaveFailure(f"unsafe archive member path: {name!r}")
    return path


def extract_git_archive(repo: Path, source_sha: str, destination: Path, log_dir: Path) -> dict[str, Any]:
    """Extract the selected committed product without storing a second full tar."""
    destination.mkdir(parents=True, exist_ok=False)
    command = ["git", "-C", str(repo), "archive", source_sha, "--", REQUIRED_PRODUCT]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    reader = HashingReader(process.stdout)
    member_count = 0
    file_count = 0
    try:
        with tarfile.open(fileobj=reader, mode="r|") as archive:
            for member in archive:
                member_count += 1
                relative = safe_relative_member(member.name)
                if relative.parts[0] != REQUIRED_PRODUCT:
                    raise WaveFailure(f"git archive emitted a path outside {REQUIRED_PRODUCT}: {member.name}")
                tail = PurePosixPath(*relative.parts[1:])
                if not tail.parts:
                    continue
                target = destination.joinpath(*tail.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise WaveFailure(f"git archive contains unsupported member kind: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = archive.extractfile(member)
                if payload is None:
                    raise WaveFailure(f"unable to read git archive member: {member.name}")
                with payload, target.open("wb") as output:
                    shutil.copyfileobj(payload, output, length=1024 * 1024)
                target.chmod(member.mode & 0o777)
                file_count += 1
        while reader.read(1024 * 1024):
            pass
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        returncode = process.wait()
        (log_dir / "git-archive.stderr.txt").write_text(stderr, encoding="utf-8")
        json_write(
            log_dir / "git-archive.json",
            {
                "argv": command,
                "returncode": returncode,
                "sha256": reader.digest.hexdigest(),
                "archive_bytes": reader.bytes_read,
                "members": member_count,
                "regular_files": file_count,
                "extracted_to": str(destination),
            },
        )
        if returncode:
            raise WaveFailure(f"git archive failed ({returncode}); stderr retained")
        return {"sha256": reader.digest.hexdigest(), "archive_bytes": reader.bytes_read}
    except BaseException as error:
        if process.poll() is None:
            process.kill()
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        process.wait()
        (log_dir / "git-archive.stderr.txt").write_text(stderr, encoding="utf-8")
        json_write(
            log_dir / "git-archive-partial.json",
            {
                "argv": command,
                "failure": f"{type(error).__name__}: {error}",
                "partial_sha256": reader.digest.hexdigest(),
                "archive_bytes_read": reader.bytes_read,
                "members_seen": member_count,
                "extracted_to": str(destination),
            },
        )
        raise


def read_asset_manifest(frozen_product: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assets = manifest["candidate_baseline"]["force_include_assets"]
    config = tomllib.loads((frozen_product / "hatch.toml").read_text(encoding="utf-8"))
    force_include = config["build"]["targets"]["wheel"]["force-include"]
    expected_mapping = {asset["source"]: asset["wheel"] for asset in assets}
    if force_include != expected_mapping:
        raise WaveFailure(
            "frozen hatch.toml force-include map differs from the reviewed 11-row manifest; "
            "reconcile the manifest before running the wave"
        )
    for asset in assets:
        if asset["archive"] != f"policy-engine/{asset['source']}":
            raise WaveFailure(f"manifest GCP archive path does not match source path: {asset['source']}")
    sdist_include = set(config["build"]["targets"]["sdist"]["include"])
    missing_sdist = sorted(set(expected_mapping) - sdist_include)
    if missing_sdist:
        raise WaveFailure(f"frozen sdist config omits force-include source files: {missing_sdist}")
    if (
        len(assets) != manifest["candidate_baseline"]["force_include_count"]
        or manifest["candidate_baseline"]["force_include_count"] != 11
    ):
        raise WaveFailure("the reviewed force-include denominator is no longer eleven")
    for asset in assets:
        path = frozen_product / asset["source"]
        if not path.is_file() or path.is_symlink():
            raise WaveFailure(f"force-include source is absent or symlinked: {asset['source']}")
        data = path.read_bytes()
        observed = {"bytes": len(data), "sha256": sha256_bytes(data)}
        expected = {key: asset[key] for key in ("bytes", "sha256")}
        if observed != expected:
            raise WaveFailure(
                f"frozen asset differs from candidate baseline; reconcile first: {asset['source']} "
                f"expected={expected} actual={observed}"
            )
    return manifest, assets


def profile_target_members(assets: list[dict[str, Any]]) -> set[str]:
    return {asset["wheel"] for asset in assets if asset["wheel"].startswith(PROFILE_TARGET_ROOT)}


def verify_wheel(wheel_path: Path, assets: list[dict[str, Any]]) -> dict[str, Any]:
    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        if len(names) != len(wheel.namelist()):
            raise WaveFailure(f"wheel has duplicate member names: {wheel_path}")
        rows = {}
        for asset in assets:
            target = asset["wheel"]
            if target not in names:
                raise WaveFailure(f"wheel omitted force-include target: {target} in {wheel_path}")
            data = wheel.read(target)
            observed = {"bytes": len(data), "sha256": sha256_bytes(data)}
            expected = {key: asset[key] for key in ("bytes", "sha256")}
            if observed != expected:
                raise WaveFailure(f"wheel asset differs: {wheel_path}!{target}: {observed} != {expected}")
            rows[target] = observed
        actual_profile = {
            name for name in names if name.startswith(PROFILE_TARGET_ROOT) and not name.endswith("/")
        }
        if actual_profile != profile_target_members(assets):
            raise WaveFailure(
                f"wheel DoWhy profile target has undeclared/missing members: "
                f"actual={sorted(actual_profile)} expected={sorted(profile_target_members(assets))}"
            )
        return {"path": str(wheel_path), "sha256": sha256_file(wheel_path), "assets": rows}


def verify_tar_assets(
    archive_path: Path,
    assets: list[dict[str, Any]],
    *,
    member_prefix: str,
    exact_force_directories: bool,
) -> dict[str, Any]:
    with tarfile.open(archive_path, "r:*") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(set(names)) != len(names):
            raise WaveFailure(f"archive repeats member names: {archive_path}")
        regular = {member.name: member for member in members if member.isfile()}
        directories = [member for member in members if member.isdir()]
        special = [member for member in members if not member.isfile() and not member.isdir()]
        if member_prefix == "policy-engine/" and special:
            raise WaveFailure(
                f"GCP archive contains symlink/special members: "
                f"{[(member.name, member.type) for member in special]}"
            )
        names_by_source = {
            asset["source"]: f"{member_prefix}{asset['source']}" for asset in assets
        }
        missing = sorted(
            archive_name
            for archive_name in names_by_source.values()
            if archive_name not in regular
        )
        if missing:
            raise WaveFailure(f"archive omitted force-include sources: {missing} from {archive_path}")
        rows = {}
        for asset in assets:
            archive_name = names_by_source[asset["source"]]
            member = regular[archive_name]
            stream = archive.extractfile(member)
            if stream is None:
                raise WaveFailure(f"cannot read archive asset {member.name} from {archive_path}")
            with stream:
                data = stream.read()
            observed = {"bytes": len(data), "sha256": sha256_bytes(data)}
            expected = {key: asset[key] for key in ("bytes", "sha256")}
            if observed != expected:
                raise WaveFailure(f"archive asset differs: {archive_path}:{member.name}: {observed} != {expected}")
            rows[member.name] = observed
        if exact_force_directories:
            for root in FORBIDDEN_ARCHIVE_SIBLING_ROOTS:
                expected = {asset["archive"] for asset in assets if asset["archive"].startswith(root)}
                observed = {name for name in regular if name.startswith(root)}
                if observed != expected:
                    raise WaveFailure(
                        f"archive selected undeclared sibling(s) under {root}: "
                        f"actual={sorted(observed)} expected={sorted(expected)}"
                    )
        return {
            "path": str(archive_path),
            "sha256": sha256_file(archive_path),
            "archive_member_denominator": {
                "members": len(members),
                "regular_files": len(regular),
                "directories": len(directories),
                "symlinks_or_specials": len(special),
            },
            "force_include_assets": rows,
            "exact_force_directories": exact_force_directories,
            "member_prefix": member_prefix,
        }


def one_matching_file(directory: Path, pattern: str) -> Path:
    found = sorted(directory.glob(pattern))
    if len(found) != 1 or not found[0].is_file():
        raise WaveFailure(f"expected exactly one {pattern} under {directory}; found {found}")
    return found[0]


def product_root_from_sdist(
    archive_path: Path,
    destination: Path,
    source_product: Path,
    expected_prefix: str,
) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    seen_prefixes: set[str] = set()
    seen_files: set[str] = set()
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive:
            relative = safe_relative_member(member.name)
            seen_prefixes.add(relative.parts[0])
            if relative.parts[0] != expected_prefix:
                raise WaveFailure(f"unexpected sdist root: {member.name}, wanted {expected_prefix}/")
            tail = PurePosixPath(*relative.parts[1:])
            if not tail.parts:
                continue
            target = destination.joinpath(*tail.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise WaveFailure(f"sdist has unsupported member kind: {member.name}")
            if tail.as_posix() in seen_files:
                raise WaveFailure(f"sdist repeats a member: {member.name}")
            seen_files.add(tail.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = archive.extractfile(member)
            if stream is None:
                raise WaveFailure(f"cannot read sdist member: {member.name}")
            temporary = target.with_name(target.name + ".q2-writing")
            digest = hashlib.sha256()
            hardlinked = False
            try:
                with stream, temporary.open("wb") as output:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                        output.write(block)
                original = source_product / tail
                if (
                    original.is_file()
                    and not original.is_symlink()
                    and sha256_file(original) == digest.hexdigest()
                    and (original.stat().st_mode & 0o777) == (member.mode & 0o777)
                ):
                    os.link(original, target)
                    temporary.unlink()
                    hardlinked = True
                else:
                    os.replace(temporary, target)
                if not hardlinked:
                    target.chmod(member.mode & 0o777)
            except BaseException:
                # Keep any incomplete member for diagnosis; do not clean run scratch on failure.
                raise
    if seen_prefixes != {expected_prefix}:
        raise WaveFailure(f"sdist has unexpected top-level roots: {sorted(seen_prefixes)}")
    return destination


def product_root_from_gcp(archive_path: Path, destination: Path, source_product: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    expected_prefix = "policy-engine"
    seen_prefixes: set[str] = set()
    seen_files: set[str] = set()
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive:
            relative = safe_relative_member(member.name)
            seen_prefixes.add(relative.parts[0])
            if relative.parts[0] != expected_prefix:
                raise WaveFailure(f"unexpected GCP archive root: {member.name}")
            tail = PurePosixPath(*relative.parts[1:])
            if not tail.parts:
                continue
            target = destination.joinpath(*tail.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise WaveFailure(f"GCP archive has unsupported member kind: {member.name}")
            if tail.as_posix() in seen_files:
                raise WaveFailure(f"GCP archive repeats a member: {member.name}")
            seen_files.add(tail.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = archive.extractfile(member)
            if stream is None:
                raise WaveFailure(f"cannot read GCP archive member: {member.name}")
            temporary = target.with_name(target.name + ".q2-writing")
            digest = hashlib.sha256()
            hardlinked = False
            try:
                with stream, temporary.open("wb") as output:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                        output.write(block)
                original = source_product / tail
                if (
                    original.is_file()
                    and not original.is_symlink()
                    and sha256_file(original) == digest.hexdigest()
                    and (original.stat().st_mode & 0o777) == (member.mode & 0o777)
                ):
                    os.link(original, target)
                    temporary.unlink()
                    hardlinked = True
                else:
                    os.replace(temporary, target)
                if not hardlinked:
                    target.chmod(member.mode & 0o777)
            except BaseException:
                # Keep any incomplete member for diagnosis; do not clean run scratch on failure.
                raise
    if seen_prefixes != {expected_prefix}:
        raise WaveFailure(f"GCP archive has unexpected top-level roots: {sorted(seen_prefixes)}")
    return destination


def run_build(
    uv: str,
    build_python: Path,
    product: Path,
    output: Path,
    *,
    wheel: bool,
    sdist: bool,
    log_dir: Path,
    env: dict[str, str],
) -> Path | tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=False)
    argv = [uv, "build", "--offline", "--no-build-isolation", "--python", str(build_python)]
    if wheel:
        argv.append("--wheel")
    if sdist:
        argv.append("--sdist")
    argv.extend(["--out-dir", str(output)])
    run_command(argv, cwd=product, env=env, log_stem=log_dir / output.name)
    wheel_path = one_matching_file(output, "*.whl") if wheel else None
    sdist_path = one_matching_file(output, "*.tar.gz") if sdist else None
    if wheel and sdist:
        assert wheel_path and sdist_path
        return wheel_path, sdist_path
    if wheel:
        assert wheel_path
        return wheel_path
    if sdist_path:
        return sdist_path
    raise WaveFailure("no build target requested")


def interpreter_info(python: Path, *, log_dir: Path, name: str) -> dict[str, Any]:
    """Inspect a venv without importing `site` or executing any `.pth` file."""
    code = (
        "import json, sys, sysconfig; "
        "print(json.dumps({'version': list(sys.version_info[:3]), 'executable': sys.executable, "
        "'base_executable': sys._base_executable, 'prefix': sys.prefix, "
        "'purelib': sysconfig.get_paths()['purelib']}))"
    )
    result = subprocess.run(
        [str(python), "-S", "-c", code],
        env=clean_child_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    (log_dir / f"{name}-info.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (log_dir / f"{name}-info.stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise WaveFailure(f"unable to inspect {name} interpreter; output retained")
    info = json.loads(result.stdout)
    venv_root = python.parent.parent
    if (venv_root / "pyvenv.cfg").is_file():
        version = info["version"]
        info["prefix"] = str(venv_root)
        info["purelib"] = str(
            venv_root / "lib" / f"python{version[0]}.{version[1]}" / "site-packages"
        )
    info["hatchling"] = distribution_version(Path(info["purelib"]), "hatchling")
    return info


def distribution_version(site: Path, distribution: str) -> str | None:
    prefix = distribution.replace("-", "_").lower() + "-"
    for metadata in sorted(site.glob("*.dist-info/METADATA")):
        if not metadata.parent.name.lower().startswith(prefix):
            continue
        for line in metadata.read_text(encoding="utf-8").splitlines():
            if line.startswith("Version: "):
                return line.removeprefix("Version: ").strip()
    return None


def configure_build_env(
    uv: str,
    base_python: Path,
    app_dependency_site: Path,
    run_root: Path,
    env: dict[str, str],
    log_dir: Path,
) -> Path:
    """Create one clean build tool venv whose site appends deps without `.pth` processing."""
    venv = run_root / "build-tools-env"
    run_command(
        [uv, "venv", "--python", str(base_python), str(venv)],
        cwd=run_root,
        env=env,
        log_stem=log_dir / "create-build-tools-env",
    )
    python = venv / "bin" / "python"
    info = interpreter_info(python, log_dir=log_dir, name="build-tools-env")
    if info["version"][:2] != [3, 14]:
        raise WaveFailure(f"build tools env must use CPython 3.14: {info['version']}")
    if distribution_version(app_dependency_site, "hatchling") != "1.27.0":
        raise WaveFailure("existing app dependency site must provide Hatchling 1.27.0")
    if not app_dependency_site.is_dir():
        raise WaveFailure(f"locked app dependency site is missing: {app_dependency_site}")
    purelib = Path(info["purelib"]).resolve()
    if tuple(purelib.glob("*.pth")):
        raise WaveFailure("build tools venv contains a .pth file; refusing to execute it")
    sitecustomize = (
        "from pathlib import Path\n"
        "import sys\n"
        f"_q2_dependency_site = Path({str(app_dependency_site)!r}).resolve()\n"
        "if not _q2_dependency_site.is_dir():\n"
        "    raise RuntimeError(f'Q2 dependency site is missing: {_q2_dependency_site}')\n"
        "_q2_dependency_text = str(_q2_dependency_site)\n"
        "if _q2_dependency_text in sys.path:\n"
        "    raise RuntimeError('Q2 dependency site was already processed; editable .pth injection is forbidden')\n"
        "sys.path.append(_q2_dependency_text)\n"
    )
    (purelib / "sitecustomize.py").write_text(sitecustomize, encoding="utf-8")
    proof = run_command(
        [
            str(python),
            "-I",
            "-c",
            "import json,sys,sysconfig; import importlib.metadata as metadata; "
            "import hatchling; from pathlib import Path; "
            f"site=Path({str(app_dependency_site)!r}).resolve(); "
            "assert sys.path[-1]==str(site),sys.path; "
            "assert not any(p and '/src' in p for p in sys.path),sys.path; "
            "assert metadata.version('hatchling')=='1.27.0'; "
            "assert Path(hatchling.__file__).resolve().is_relative_to(site); "
            "print(json.dumps({'prefix':sys.prefix,'purelib':sysconfig.get_paths()['purelib'],"
            "'hatchling_origin':str(Path(hatchling.__file__).resolve()),"
            "'app_dependency_site_appended':sys.path[-1],'isolated':sys.flags.isolated}))",
        ],
        cwd=run_root,
        env=env,
        log_stem=log_dir / "build-tools-env-path-proof",
    )
    if not json.loads(proof.stdout).get("isolated"):
        raise WaveFailure("build tool environment did not start in Python isolated mode")
    json_write(
        run_root / "build-tools-env-config.json",
        {
            "python": str(python),
            "purelib": str(purelib),
            "base_executable": str(base_python),
            "app_dependency_site_appended_without_pth_processing": str(app_dependency_site),
            "hatchling": "1.27.0",
        },
    )
    return python


def configure_installed_env(
    uv: str,
    base_python: Path,
    run_root: Path,
    app_dependency_site: Path,
    source_product: Path,
    env: dict[str, str],
    log_dir: Path,
) -> tuple[Path, Path]:
    venv = run_root / "installed-consumer-env"
    run_command(
        [uv, "venv", "--python", str(base_python), str(venv)],
        cwd=run_root,
        env=env,
        log_stem=log_dir / "create-installed-consumer-env",
    )
    python = venv / "bin" / "python"
    if not python.is_file():
        raise WaveFailure(f"expected Unix virtual-environment interpreter: {python}")
    info = interpreter_info(python, log_dir=log_dir, name="installed-consumer-env")
    if info["version"][:2] != [3, 14]:
        raise WaveFailure(f"installed consumer env must use CPython 3.14, got {info['version']}")
    purelib = Path(info["purelib"]).resolve()
    prefix = Path(info["prefix"]).resolve()
    if not purelib.is_relative_to(prefix):
        raise WaveFailure(f"installed site-packages escapes isolated prefix: {purelib} vs {prefix}")
    if tuple(purelib.glob("*.pth")):
        raise WaveFailure("fresh installed consumer venv contains a .pth file; refusing to execute it")
    if not app_dependency_site.is_dir():
        raise WaveFailure(f"locked dependency site is missing: {app_dependency_site}")
    sitecustomize = (
        "from pathlib import Path\n"
        "import sys\n"
        f"_q2_dependency_site = Path({str(app_dependency_site)!r}).resolve()\n"
        "if not _q2_dependency_site.is_dir():\n"
        "    raise RuntimeError(f'Q2 dependency site is missing: {_q2_dependency_site}')\n"
        "_q2_dependency_text = str(_q2_dependency_site)\n"
        "if _q2_dependency_text in sys.path:\n"
        "    raise RuntimeError('Q2 dependency site was already processed; editable .pth injection is forbidden')\n"
        "sys.path.append(_q2_dependency_text)\n"
    )
    (purelib / "sitecustomize.py").write_text(sitecustomize, encoding="utf-8")
    origin_plugin = '''from __future__ import annotations
import json, os, sys, sysconfig
from pathlib import Path
import pytest

def _under(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (OSError, ValueError):
        return False

def pytest_collection_finish(session):
    out = Path(os.environ["E02_NODEIDS_REPORT"])
    out.write_text(json.dumps(sorted(item.nodeid for item in session.items), indent=2) + "\\n")

def pytest_sessionfinish(session, exitstatus):
    purelib = Path(sysconfig.get_paths()["purelib"]).resolve()
    dependency_site = Path(os.environ["E02_DEPENDENCY_SITE"]).resolve()
    source = Path(os.environ["E02_SOURCE_ROOT"]).resolve()
    live_product = Path(os.environ["E02_LIVE_PRODUCT_ROOT"]).resolve()
    forbidden_roots = [source, live_product]
    forbidden_sys_path = [p for p in sys.path if p and any(_under(p, root) for root in forbidden_roots)]
    origins = {}
    errors = []
    for name, module in sorted(sys.modules.copy().items()):
        if not (name == "polisyos" or name.startswith("polisyos.") or name == "tools" or name.startswith("tools.")):
            continue
        module_file = getattr(module, "__file__", None)
        spec = getattr(module, "__spec__", None)
        locations = list(getattr(spec, "submodule_search_locations", ()) or ())
        if module_file:
            origin = str(Path(module_file).resolve())
            origins[name] = origin
            if not _under(origin, purelib):
                errors.append({"module": name, "origin": origin, "reason": "outside installed purelib"})
        elif locations:
            resolved = [str(Path(location).resolve()) for location in locations]
            origins[name] = resolved
            if not all(_under(location, purelib) for location in resolved):
                errors.append({"module": name, "origin": resolved, "reason": "namespace outside installed purelib"})
        else:
            errors.append({"module": name, "origin": None, "reason": "no inspectable module origin"})
    if forbidden_sys_path:
        errors.append({"sys_path": forbidden_sys_path, "reason": "source or test path injected"})
    normalized_sys_path = [str(Path(path).resolve()) for path in sys.path]
    try:
        installed_index = normalized_sys_path.index(str(purelib))
        dependency_index = normalized_sys_path.index(str(dependency_site))
        if installed_index >= dependency_index:
            errors.append({"sys_path": normalized_sys_path, "reason": "installed site does not precede dependency site"})
    except ValueError:
        errors.append({"sys_path": normalized_sys_path, "reason": "installed/dependency site missing"})
    report = {"verified": not errors, "purelib": str(purelib), "sys_path": sys.path, "origins": origins, "errors": errors}
    Path(os.environ["E02_ORIGIN_REPORT"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\\n")
    if errors:
        print("Q2 installed-origin proof failed: " + json.dumps(errors, sort_keys=True), file=sys.stderr)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
'''
    (purelib / "q2_installed_origin_plugin.py").write_text(origin_plugin, encoding="utf-8")
    json_write(
        run_root / "installed-env-config.json",
        {
            "venv": str(venv),
            "python": str(python),
            "purelib": str(purelib),
            "app_dependency_site_appended_without_pth_processing": str(app_dependency_site),
            "source_product": str(source_product),
            "PYTHONPATH": None,
            "installation_mode": "one venv reused sequentially with uv pip --reinstall --no-deps",
        },
    )
    return python, purelib


def installed_runtime_proof(
    python: Path,
    purelib: Path,
    assets: list[dict[str, Any]],
    source_product: Path,
    live_product: Path,
    app_dependency_site: Path,
    run_root: Path,
    profile: str,
    env: dict[str, str],
    log_dir: Path,
) -> dict[str, Any]:
    expected = {asset["wheel"]: {"bytes": asset["bytes"], "sha256": asset["sha256"]} for asset in assets}
    code = '''import hashlib, importlib, importlib.metadata, json, os, sys, sysconfig
from pathlib import Path
purelib=Path(sysconfig.get_paths()["purelib"]).resolve()
prefix=Path(sys.prefix).resolve()
source=Path(os.environ["E02_SOURCE_ROOT"]).resolve()
live_product=Path(os.environ["E02_LIVE_PRODUCT_ROOT"]).resolve()
dependency_site=Path(os.environ["E02_DEPENDENCY_SITE"]).resolve()
forbidden_roots=(source,live_product)
assert purelib.is_relative_to(prefix)
assert sys.flags.isolated
assert not os.environ.get("PYTHONPATH")
assert not any(p and any(Path(p).resolve()==root or Path(p).resolve().is_relative_to(root) for root in forbidden_roots) for p in sys.path)
normalized_sys_path=[Path(p).resolve() for p in sys.path]
assert normalized_sys_path.index(purelib)<normalized_sys_path.index(dependency_site),sys.path
assets=json.loads(Path(os.environ["E02_ASSET_EXPECTED_JSON"]).read_text())
import polisyos, tools
from polisyos.data_forge.domains.catalog import _resources
from polisyos.foundry.methods.catalog import dependency_authority
from polisyos.foundry.methods.catalog.causal import _dowhy_worker
module_origins={name:str(Path(module.__file__).resolve()) for name,module in sys.modules.copy().items() if (name=="polisyos" or name.startswith("polisyos.") or name=="tools" or name.startswith("tools.")) and getattr(module,"__file__",None)}
assert module_origins
assert all(Path(origin).is_relative_to(purelib) for origin in module_origins.values()), module_origins
asset_rows={}
for target,expected in assets.items():
    path=purelib/target
    data=path.read_bytes()
    observed={"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
    assert observed==expected,(target,observed,expected)
    asset_rows[target]={**observed,"installed_path":str(path)}
assert Path(_resources.__file__).resolve().is_relative_to(purelib)
assert Path(dependency_authority.__file__).resolve().is_relative_to(purelib)
assert Path(_dowhy_worker.__file__).resolve().is_relative_to(purelib)
registry_path=Path(dependency_authority._DIGEST_REGISTRY_PATH).resolve()
assert registry_path==Path(dependency_authority._PACKAGED_DIGEST_REGISTRY_PATH).resolve()
registry_bytes=registry_path.read_bytes()
assert hashlib.sha256(registry_bytes).hexdigest()==assets["polisyos/foundry/methods/catalog/_resources/method_catalog_dependency_digest_domains.toml"]["sha256"]
registry=dependency_authority.load_digest_domain_registry(registry_path)
assert registry.statement.domains
print(json.dumps({"python":sys.version,"prefix":str(prefix),"purelib":str(purelib),"policyos_origin":str(Path(polisyos.__file__).resolve()),"tools_origin":str(Path(tools.__file__).resolve()),"module_origins":module_origins,"assets":asset_rows},sort_keys=True))
'''
    child_env = clean_child_env()
    child_env.update(
        {
            "E02_SOURCE_ROOT": str(source_product),
            "E02_LIVE_PRODUCT_ROOT": str(live_product),
            "E02_DEPENDENCY_SITE": str(app_dependency_site),
            "E02_ASSET_EXPECTED_JSON": str(run_root / "asset-targets-expected.json"),
        }
    )
    json_write(run_root / "asset-targets-expected.json", expected)
    result = run_command(
        [str(python), "-I", "-c", code],
        cwd=run_root,
        env=child_env,
        log_stem=log_dir / f"{profile}-installed-runtime-proof",
    )
    proof = json.loads(result.stdout)
    if Path(proof["purelib"]).resolve() != purelib.resolve():
        raise WaveFailure(f"installed proof used unexpected purelib: {proof['purelib']}")
    if len(proof["assets"]) != 11:
        raise WaveFailure(f"installed proof did not cover all 11 force-includes: {len(proof['assets'])}")
    return proof


def baseline_node_ids(source_product: Path, manifest: dict[str, Any]) -> set[str]:
    relative = manifest["original_q2_suite"]["baseline_junit_path"]
    baseline_path = source_product / relative
    compressed = baseline_path.read_bytes()
    if sha256_bytes(compressed) != manifest["original_q2_suite"]["baseline_junit_sha256"]:
        raise WaveFailure("tracked original Q2 JUnit baseline checksum changed; reconcile before running")
    root = ET.fromstring(gzip.decompress(compressed))
    rows = list(root.iter("testcase"))
    if len(rows) != manifest["original_q2_suite"]["baseline_case_count"]:
        raise WaveFailure(f"original Q2 baseline denominator differs: {len(rows)}")
    ids: set[str] = set()
    for case in rows:
        classname = case.attrib["classname"]
        if classname == "test_installed_catalog_defaults":
            test_path = manifest["original_q2_suite"]["test_paths"][-1]
        else:
            dotted = classname.split(".")
            test_path = "/".join(dotted[:-1] + [dotted[-1] + ".py"])
        if not any(test_path == candidate for candidate in manifest["original_q2_suite"]["test_paths"]):
            raise WaveFailure(f"baseline JUnit case falls outside declared original suite: {classname}")
        ids.add(f"{test_path}::{case.attrib['name']}")
    if len(ids) != len(rows):
        raise WaveFailure("original baseline JUnit contains duplicate node IDs")
    return ids


def node_ids_sha256(node_ids: set[str] | list[str]) -> str:
    """Hash a canonical, sorted, newline-delimited node-ID set."""
    return sha256_bytes(("\n".join(sorted(node_ids)) + "\n").encode("utf-8"))


def historical_baseline_subset_ids(
    manifest: dict[str, Any], expected_original_ids: set[str]
) -> set[str]:
    """Rebuild and validate the named 91-baseline-plus-nine-consumer subset."""
    expected = set(expected_original_ids)
    additional = manifest["additional_installed_consumers"]
    for group in (additional["dependency_profile"], additional["canonical_bridge_and_worker"]):
        for selector in group["selectors"]:
            node_id = f"{group['test_path']}::{selector}"
            if node_id in expected:
                raise WaveFailure(
                    f"historical installed consumer duplicates an original ID: {node_id}"
                )
            expected.add(node_id)

    declaration = manifest.get("current_primary_suite", {}).get("historical_baseline_subset")
    if not isinstance(declaration, dict):
        raise WaveFailure("current primary suite omits the named historical baseline subset")
    if declaration.get("selected_node_count") != len(expected):
        raise WaveFailure(
            "historical baseline subset count differs from its recomputed IDs: "
            f"declared={declaration.get('selected_node_count')} actual={len(expected)}"
        )
    if declaration.get("selected_node_ids_sha256") != node_ids_sha256(expected):
        raise WaveFailure("historical baseline subset ID digest differs from its recomputed IDs")
    if not isinstance(declaration.get("name"), str) or not declaration["name"].strip():
        raise WaveFailure("historical baseline subset must have a nonempty name")
    return expected


def current_primary_suite_ids(
    manifest: dict[str, Any], expected_original_ids: set[str]
) -> set[str]:
    """Load the content-bound exact current profile selector set from the manifest."""
    suite = manifest.get("current_primary_suite")
    if not isinstance(suite, dict):
        raise WaveFailure("manifest omits current_primary_suite")
    raw_ids = suite.get("selected_node_ids")
    if (
        not isinstance(raw_ids, list)
        or not raw_ids
        or any(not isinstance(item, str) for item in raw_ids)
    ):
        raise WaveFailure("current primary suite node IDs must be a nonempty string list")
    if raw_ids != sorted(set(raw_ids)):
        raise WaveFailure("current primary suite node IDs must be sorted and unique")
    if suite.get("selected_node_count") != len(raw_ids):
        raise WaveFailure("current primary suite count differs from its complete node-ID list")
    if suite.get("selected_node_ids_sha256") != node_ids_sha256(raw_ids):
        raise WaveFailure("current primary suite digest differs from its complete node-ID list")

    declared_paths = set(manifest["original_q2_suite"]["test_paths"])
    additional = manifest["additional_installed_consumers"]
    declared_paths.update(group["test_path"] for group in additional.values())
    source_hashes = suite.get("source_file_sha256")
    if not isinstance(source_hashes, dict) or set(source_hashes) != declared_paths:
        raise WaveFailure(
            "current primary suite source-hash paths differ from the complete selected path set"
        )
    for path, digest in source_hashes.items():
        safe_relative_member(path)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise WaveFailure(f"current primary suite has an invalid source hash for {path}")

    ids = set(raw_ids)
    for node_id in raw_ids:
        pieces = node_id.split("::")
        if len(pieces) != 2 or pieces[0] not in declared_paths:
            raise WaveFailure(
                f"current primary suite contains an unbound source-qualified ID: {node_id}"
            )
        function_name = pieces[1].split("[", 1)[0]
        if not function_name.startswith("test_"):
            raise WaveFailure(f"current primary suite contains a non-test selector: {node_id}")

    historical = historical_baseline_subset_ids(manifest, expected_original_ids)
    if not historical <= ids:
        raise WaveFailure(
            "current primary suite omits IDs from the historical 91-plus-nine subset: "
            f"{sorted(historical - ids)}"
        )
    for group in additional.values():
        for selector in group["selectors"]:
            node_id = f"{group['test_path']}::{selector}"
            if node_id not in ids:
                raise WaveFailure(
                    f"current primary suite omits required installed consumer: {node_id}"
                )
    return ids


def verify_current_primary_suite_sources(
    frozen_product: Path, manifest: dict[str, Any], expected_original_ids: set[str]
) -> set[str]:
    """Verify every source file that contributes the current selected pytest collection."""
    ids = current_primary_suite_ids(manifest, expected_original_ids)
    source_hashes = manifest["current_primary_suite"]["source_file_sha256"]
    for relative, expected_sha in sorted(source_hashes.items()):
        source = frozen_product.joinpath(*safe_relative_member(relative).parts)
        if not source.is_file() or source.is_symlink():
            raise WaveFailure(f"current primary suite source is absent or symlinked: {relative}")
        actual_sha = sha256_file(source)
        if actual_sha != expected_sha:
            raise WaveFailure(
                f"current primary suite source changed; reconcile ID manifest first: {relative} "
                f"expected={expected_sha} actual={actual_sha}"
            )
    return ids


def _module_function_index(tree: ast.Module) -> dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]:
    functions: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.setdefault(node.name, []).append(node)
    return functions


def _local_function_closure(
    root_name: str,
    functions: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]],
    *,
    source_path: str,
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    closure: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    pending = [root_name]
    while pending:
        name = pending.pop()
        if name in closure:
            continue
        candidates = functions.get(name, [])
        if len(candidates) != 1:
            raise WaveFailure(
                f"selected test/helper {name!r} in {source_path} is absent or ambiguous"
            )
        function = candidates[0]
        closure[name] = function
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in functions
                and node.func.id not in closure
            ):
                pending.append(node.func.id)
    return closure


def _is_file_fixture_loader(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "spec_from_file_location"
        for node in ast.walk(function)
    )


def _verify_fixture_loader_key(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    source_path: str,
) -> str:
    parameters = function.args.posonlyargs + function.args.args
    if not parameters:
        raise WaveFailure(f"file fixture loader in {source_path} has no kind parameter")
    kind_parameter = parameters[0].arg
    env_keys = [
        node.slice
        for node in ast.walk(function)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "os"
        and node.value.attr == "environ"
    ]
    matching = []
    for expression in env_keys:
        text = ast.unparse(expression)
        if (
            "E02_" in text
            and "_FIXTURE_PATH" in text
            and f"{kind_parameter}.upper()" in text
        ):
            matching.append(text)
    if len(matching) != 1:
        raise WaveFailure(
            f"file fixture loader in {source_path} must derive one E02_<KIND>_FIXTURE_PATH "
            f"from its kind argument; found {matching}"
        )
    return matching[0]


def _verify_call_arity(
    call: ast.Call,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    label: str,
) -> None:
    if any(isinstance(argument, ast.Starred) for argument in call.args):
        raise WaveFailure(f"fixture callback uses an unresolved starred argument: {label}")
    if any(keyword.arg is None for keyword in call.keywords):
        raise WaveFailure(f"fixture callback uses unresolved **kwargs: {label}")
    positional = function.args.posonlyargs + function.args.args
    positional_names = [argument.arg for argument in positional]
    if len(call.args) > len(positional) and function.args.vararg is None:
        raise WaveFailure(f"fixture callback passes too many positional arguments: {label}")
    supplied_positional = positional_names[: len(call.args)]
    supplied_keywords = [keyword.arg for keyword in call.keywords if keyword.arg is not None]
    if set(supplied_positional) & set(supplied_keywords):
        raise WaveFailure(f"fixture callback binds an argument twice: {label}")
    accepted_keywords = {argument.arg for argument in function.args.args} | {
        argument.arg for argument in function.args.kwonlyargs
    }
    if function.args.kwarg is None and not set(supplied_keywords) <= accepted_keywords:
        raise WaveFailure(f"fixture callback passes an unknown keyword: {label}")
    if len(call.args) < len(positional) - len(function.args.defaults):
        required_positional = set(positional_names[: len(positional) - len(function.args.defaults)])
        if not required_positional <= set(supplied_positional + supplied_keywords):
            raise WaveFailure(f"fixture callback omits a required positional argument: {label}")
    required_keyword_only = {
        argument.arg
        for argument, default in zip(
            function.args.kwonlyargs, function.args.kw_defaults, strict=True
        )
        if default is None
    }
    if not required_keyword_only <= set(supplied_keywords):
        raise WaveFailure(f"fixture callback omits a required keyword-only argument: {label}")


def verify_transitive_test_bindings(
    frozen_product: Path,
    manifest: dict[str, Any],
    expected_original_ids: set[str],
) -> dict[str, Any]:
    """Resolve every selected test through any dynamic fixture module to its callable target."""
    current_ids = verify_current_primary_suite_sources(
        frozen_product, manifest, expected_original_ids
    )
    additional = manifest["additional_installed_consumers"]
    selected_ids = set(current_ids)
    historical_ids = historical_baseline_subset_ids(manifest, expected_original_ids)
    if not historical_ids <= selected_ids:
        raise WaveFailure("current transitive selector set omits the historical baseline subset")

    selected_by_path: dict[str, set[str]] = {}
    for node_id in selected_ids:
        pieces = node_id.split("::")
        if len(pieces) != 2:
            raise WaveFailure(f"transitive binding needs a module-level test node ID: {node_id}")
        test_path, test_case = pieces
        function_name = test_case.split("[", 1)[0]
        if not function_name.startswith("test_"):
            raise WaveFailure(f"transitive binding found an unsupported test node ID: {node_id}")
        selected_by_path.setdefault(test_path, set()).add(function_name)

    module_cache: dict[str, tuple[ast.Module, dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]]] = {}
    for test_path in selected_by_path:
        relative = safe_relative_member(test_path)
        source = frozen_product.joinpath(*relative.parts)
        if not source.is_file() or source.is_symlink():
            raise WaveFailure(f"selected test source is absent or symlinked: {test_path}")
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=test_path)
        module_cache[test_path] = (tree, _module_function_index(tree))
        for function_name in selected_by_path[test_path]:
            if len(module_cache[test_path][1].get(function_name, [])) != 1:
                raise WaveFailure(
                    f"selected test node {test_path}::{function_name} has no unique function body"
                )

    fixture_paths = additional["canonical_bridge_and_worker"].get("fixture_paths")
    if not isinstance(fixture_paths, dict) or not all(
        isinstance(kind, str) and isinstance(path, str) for kind, path in fixture_paths.items()
    ):
        raise WaveFailure("canonical worker consumers must declare a kind-to-fixture-path mapping")

    fixture_kinds: set[str] = set()
    callback_calls: dict[str, list[tuple[str, str, ast.Call]]] = {}
    fixture_details: dict[str, dict[str, Any]] = {}
    for test_path, test_names in selected_by_path.items():
        _, functions = module_cache[test_path]
        for test_name in test_names:
            closure = _local_function_closure(test_name, functions, source_path=test_path)
            loader_names = {
                name for name, function in closure.items() if _is_file_fixture_loader(function)
            }
            if not loader_names:
                continue
            loader_patterns = {
                name: _verify_fixture_loader_key(function, source_path=test_path)
                for name, function in closure.items()
                if name in loader_names
            }
            if test_name in loader_names:
                raise WaveFailure(
                    f"selected test {test_path}::{test_name} loads a fixture inline; "
                    "the loader-to-callable binding is not statically resolvable"
                )
            for scope_name, scope in closure.items():
                variables: dict[str, str] = {}
                loader_calls = [
                    node
                    for node in ast.walk(scope)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in loader_patterns
                ]
                for call in loader_calls:
                    if len(call.args) != 1 or not isinstance(call.args[0], ast.Constant):
                        raise WaveFailure(
                            f"selected test {test_path}::{test_name} has a nonliteral fixture kind"
                        )
                    kind = call.args[0].value
                    if not isinstance(kind, str) or not kind:
                        raise WaveFailure(
                            f"selected test {test_path}::{test_name} has an invalid fixture kind"
                        )
                    fixture_kinds.add(kind)
                    targets: list[str] = []
                    for node in ast.walk(scope):
                        if isinstance(node, ast.Assign) and node.value is call:
                            targets.extend(
                                target.id
                                for target in node.targets
                                if isinstance(target, ast.Name)
                            )
                        elif isinstance(node, ast.AnnAssign) and node.value is call:
                            if isinstance(node.target, ast.Name):
                                targets.append(node.target.id)
                    if len(targets) != 1:
                        raise WaveFailure(
                            f"selected fixture module in {test_path}::{test_name} must bind to "
                            "one local name"
                        )
                    variables[targets[0]] = kind
                for node in ast.walk(scope):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in variables
                    ):
                        kind = variables[node.func.value.id]
                        callback_calls.setdefault(kind, []).append(
                            (test_path, node.func.attr, node)
                        )
            if loader_patterns:
                for name in loader_names:
                    if name not in closure:
                        raise WaveFailure(f"unresolved fixture loader {name!r} in {test_path}")

    if fixture_kinds != set(fixture_paths):
        raise WaveFailure(
            "manifest fixture kinds differ from transitive selected-test bindings: "
            f"used={sorted(fixture_kinds)} declared={sorted(fixture_paths)}"
        )
    for kind in sorted(fixture_kinds):
        relative = safe_relative_member(fixture_paths[kind])
        fixture_source = frozen_product.joinpath(*relative.parts)
        if not fixture_source.is_file() or fixture_source.is_symlink():
            raise WaveFailure(f"fixture source for {kind!r} is absent or symlinked: {relative}")
        fixture_tree = ast.parse(
            fixture_source.read_text(encoding="utf-8"), filename=relative.as_posix()
        )
        functions = _module_function_index(fixture_tree)
        calls = callback_calls.get(kind, [])
        if not calls:
            raise WaveFailure(f"selected tests load fixture {kind!r} without calling a bound function")
        callback_receipts = []
        transitive_functions: set[str] = set()
        for test_path, callback_name, call in calls:
            candidates = functions.get(callback_name, [])
            if len(candidates) != 1:
                raise WaveFailure(
                    f"fixture callback {kind}.{callback_name} from {test_path} is absent or ambiguous"
                )
            _verify_call_arity(
                call,
                candidates[0],
                label=f"{test_path} -> {relative.as_posix()}::{callback_name}",
            )
            closure = _local_function_closure(
                callback_name,
                functions,
                source_path=relative.as_posix(),
            )
            transitive_functions.update(closure)
            callback_receipts.append(
                {
                    "selected_test_path": test_path,
                    "callback": callback_name,
                    "line": candidates[0].lineno,
                }
            )
        fixture_details[kind] = {
            "path": relative.as_posix(),
            "sha256": sha256_file(fixture_source),
            "callbacks": callback_receipts,
            "transitive_local_functions": sorted(transitive_functions),
        }
    return {
        "historical_baseline_subset_node_ids": len(historical_ids),
        "historical_baseline_subset_sha256": node_ids_sha256(historical_ids),
        "current_primary_suite_node_ids": len(current_ids),
        "current_primary_suite_sha256": node_ids_sha256(current_ids),
        "selected_test_functions_by_file": {
            path: len(names) for path, names in sorted(selected_by_path.items())
        },
        "fixture_bindings": fixture_details,
    }


def pytest_arguments(
    python: Path,
    frozen_product: Path,
    manifest: dict[str, Any],
    output: Path,
) -> list[str]:
    paths = manifest["original_q2_suite"]["test_paths"]
    args = [str(frozen_product / path) for path in paths]
    for group in manifest["additional_installed_consumers"].values():
        group_path = str(frozen_product / group["test_path"])
        args.extend(f"{group_path}::{selector}" for selector in group["selectors"])
    return [
        str(python),
        "-I",
        "-m",
        "pytest",
        "-p",
        "q2_installed_origin_plugin",
        "-o",
        "addopts=",
        "-o",
        f"cache_dir={output / 'pytest-cache'}",
        "--import-mode=importlib",
        "--confcutdir",
        str(frozen_product / "tests/unit"),
        "--strict-markers",
        "-q",
        "-ra",
        "-s",
        "--junitxml",
        str(output / "wave-junit.xml"),
        "--basetemp",
        str(output / "pytest-tmp"),
        *args,
    ]


def junit_node_ids(junit_path: Path, original_doc_path: str) -> tuple[set[str], dict[str, int]]:
    root = ET.parse(junit_path).getroot()
    cases = list(root.iter("testcase"))
    node_ids: set[str] = set()
    counts = {"tests": len(cases), "skipped": 0, "failures": 0, "errors": 0}
    for case in cases:
        classname = case.attrib["classname"]
        if classname == "test_installed_catalog_defaults":
            path = original_doc_path
        else:
            dotted = classname.split(".")
            path = "/".join(dotted[:-1] + [dotted[-1] + ".py"])
        node_ids.add(f"{path}::{case.attrib['name']}")
        counts["skipped"] += case.find("skipped") is not None
        counts["failures"] += case.find("failure") is not None
        counts["errors"] += case.find("error") is not None
    if len(node_ids) != len(cases):
        raise WaveFailure("pytest JUnit repeats a node ID")
    return node_ids, counts


def verify_consumer_run(
    result: subprocess.CompletedProcess[str],
    *,
    run_root: Path,
    output: Path,
    manifest: dict[str, Any],
    expected_original_ids: set[str],
    expected_current_ids: set[str],
) -> dict[str, Any]:
    nodeids_path = output / "collected-nodeids.json"
    origin_path = output / "origin-proof.json"
    junit_path = output / "wave-junit.xml"
    stdout_path = output / "consumer-suite.stdout.txt"
    stderr_path = output / "consumer-suite.stderr.txt"
    for path in (nodeids_path, origin_path, junit_path, stdout_path, stderr_path):
        if not path.is_file():
            raise WaveFailure(f"pytest did not produce required evidence: {path}")
    collected_list = json.loads(nodeids_path.read_text(encoding="utf-8"))
    collected = set(collected_list)
    if len(collected) != len(collected_list):
        raise WaveFailure("pytest collection contains duplicate IDs")
    missing_original = expected_original_ids - collected
    if missing_original:
        raise WaveFailure(f"frozen run omitted original Q2 IDs: {sorted(missing_original)}")
    historical_ids = historical_baseline_subset_ids(manifest, expected_original_ids)
    if not historical_ids <= expected_current_ids:
        raise WaveFailure("expected current suite omits its named historical baseline subset")
    if collected != expected_current_ids:
        raise WaveFailure(
            "collected consumer set differs from the content-bound current primary suite: "
            f"extra={sorted(collected - expected_current_ids)} "
            f"missing={sorted(expected_current_ids - collected)}"
        )
    actual, counts = junit_node_ids(
        junit_path,
        manifest["original_q2_suite"]["test_paths"][-1],
    )
    if actual != collected:
        raise WaveFailure(
            f"executed JUnit IDs differ from collection: missing={sorted(collected - actual)} "
            f"extra={sorted(actual - collected)}"
        )
    origin = json.loads(origin_path.read_text(encoding="utf-8"))
    if not origin.get("verified"):
        raise WaveFailure(f"installed origin/sys.path proof failed: {origin.get('errors')}")
    if counts["tests"] != len(expected_current_ids):
        raise WaveFailure(
            f"JUnit count differs from content-bound current suite: "
            f"actual={counts['tests']} expected={len(expected_current_ids)}"
        )
    if counts["skipped"] or counts["failures"] or counts["errors"]:
        raise WaveFailure(f"consumer suite did not complete cleanly: {counts}")
    if result.returncode:
        raise WaveFailure(f"pytest exited {result.returncode}; full output retained in {output}")
    if counts["tests"] != len(collected):
        raise WaveFailure(f"JUnit test count differs from collected node IDs: {counts} vs {len(collected)}")
    return {
        "returncode": result.returncode,
        "counts": counts,
        "original_q2_ids": len(expected_original_ids),
        "selected_node_ids": len(collected),
        "selected_node_ids_sha256": node_ids_sha256(collected),
        "historical_baseline_subset_node_ids": len(historical_ids),
        "historical_baseline_subset_sha256": node_ids_sha256(historical_ids),
        "all_original_q2_ids_present": True,
        "additional_collected_ids": len(collected - expected_original_ids),
        "collected_nodeids_path": str(nodeids_path),
        "junit_path": str(junit_path),
        "origin_proof_path": str(origin_path),
        "process_output": {
            "capture_mode": "pytest -s; complete child/test stdout and stderr captured by run_command",
            "stdout_path": str(stdout_path),
            "stdout_bytes": stdout_path.stat().st_size,
            "stdout_sha256": sha256_file(stdout_path),
            "stderr_path": str(stderr_path),
            "stderr_bytes": stderr_path.stat().st_size,
            "stderr_sha256": sha256_file(stderr_path),
        },
    }


def run_worker_profile(
    uv: str,
    supplied_python: str | None,
    frozen_product: Path,
    run_root: Path,
    env: dict[str, str],
    log_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    lock = frozen_product / "workers/dowhy-014/uv.lock"
    lock_hash_before = sha256_file(lock)
    if supplied_python:
        python = require_absolute_file(supplied_python, "--worker-python")
        mode = "pre-existing separate locked worker interpreter supplied by caller"
    else:
        if platform.system() != "Linux":
            raise WaveFailure(
                "worker provisioning is limited to Linux; supply an existing Linux worker interpreter "
                "or run this frozen wave on the supported Linux worker"
            )
        worker_env = run_root / "worker-profile-env"
        worker_env.mkdir(parents=True, exist_ok=False)
        setup_env = clean_child_env()
        setup_env["UV_PROJECT_ENVIRONMENT"] = str(worker_env / ".venv")
        profile = frozen_product / "workers/dowhy-014"
        offline = run_command(
            [uv, "sync", "--locked", "--offline", "--project", str(profile), "--python", "3.12"],
            cwd=run_root,
            env=setup_env,
            log_stem=log_dir / "worker-profile-sync-offline",
            check=False,
        )
        if offline.returncode:
            # Retain the failed offline evidence, then make the authorized locked online attempt.
            online = run_command(
                [uv, "sync", "--locked", "--project", str(profile), "--python", "3.12"],
                cwd=run_root,
                env=setup_env,
                log_stem=log_dir / "worker-profile-sync-online-fallback",
                check=False,
            )
            if online.returncode:
                raise WaveFailure(
                    "locked worker profile failed both offline setup and the online locked fallback; "
                    "both complete logs are retained"
                )
        python = worker_env / ".venv" / "bin" / "python"
        if not python.is_file():
            raise WaveFailure(f"locked worker sync did not produce the requested interpreter: {python}")
        mode = "one locked profile env; offline first with retained online fallback if needed"
    info = interpreter_info(python, log_dir=log_dir, name="dowhy-worker")
    if info["version"][:2] != [3, 12]:
        raise WaveFailure(f"worker interpreter must be Python 3.12, got {info['version']}")
    version = distribution_version(Path(info["purelib"]), "dowhy")
    (log_dir / "dowhy-worker-version.stdout.txt").write_text(f"{version or ''}\n", encoding="utf-8")
    (log_dir / "dowhy-worker-version.stderr.txt").write_text("", encoding="utf-8")
    if version != "0.14":
        raise WaveFailure(f"worker environment must contain DoWhy 0.14: {version}")
    lock_hash_after = sha256_file(lock)
    if lock_hash_before != lock_hash_after:
        raise WaveFailure("worker setup changed the frozen uv.lock")
    return python, {
        "python": str(python),
        "mode": mode,
        "python_version": info["version"],
        "dowhy_version": version,
        "lock_sha256_before": lock_hash_before,
        "lock_sha256_after": lock_hash_after,
    }


def run_wave(args: argparse.Namespace) -> Path:
    repo = Path(args.repo).resolve(strict=True)
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        raise WaveFailure(f"--repo must be the attached repository root: {repo}")
    if platform.system() != "Linux":
        raise WaveFailure("the installed worker profile wave is scoped to the supported Linux host")
    frozen_source_preflight(repo, args.source_sha, args.source_tree)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_root = Path(args.output_root).resolve() if args.output_root else HANDOFF_ROOT / "raw" / "runs"
    output_root.mkdir(parents=True, exist_ok=True)
    run_root = output_root / f"{args.source_sha}-{stamp}-pid{os.getpid()}"
    run_root.mkdir(parents=False, exist_ok=False)
    (run_root / "logs").mkdir()
    receipt: dict[str, Any] = {
        "status": "running",
        "source_sha": args.source_sha,
        "source_tree": args.source_tree,
        "repo": str(repo),
        "started_utc": datetime.now(UTC).isoformat(),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "uv": None,
        "profiles": {},
        "retention": "all files are retained; this runner has no cleanup path",
    }
    receipt_path = run_root / "run-receipt.json"
    json_write(receipt_path, receipt)
    try:
        env = clean_child_env()
        uv = shutil.which("uv")
        if not uv:
            raise WaveFailure("uv executable is not available on PATH")
        uv_version = run_command(
            [uv, "--version"], cwd=repo, env=env, log_stem=run_root / "logs" / "uv-version"
        ).stdout.strip()
        app_python = require_absolute_file(args.app_python, "--app-python")
        app_info = interpreter_info(app_python, log_dir=run_root / "logs", name="app-build")
        if app_info["version"][:2] != [3, 14]:
            raise WaveFailure(f"application build interpreter must be Python 3.14: {app_info['version']}")
        if app_info["hatchling"] != "1.27.0":
            raise WaveFailure(
                f"frozen app build environment must retain Hatchling 1.27.0, got {app_info['hatchling']}"
            )
        base_python = require_absolute_file(app_info["base_executable"], "app base Python")
        dependency_site = Path(app_info["purelib"]).resolve()
        receipt["uv"] = {"executable": str(Path(uv).resolve()), "version": uv_version}
        receipt["app_build_interpreter"] = app_info
        receipt["tooling_note"] = (
            "Observed uv version is recorded above; repository guidance cites uv 0.9.21. "
            "The runner does not silently substitute the documented version."
        )
        build_python = configure_build_env(
            uv,
            base_python,
            dependency_site,
            run_root,
            env,
            run_root / "logs",
        )
        json_write(receipt_path, receipt)

        source_root = run_root / "frozen-source"
        archive_receipt = extract_git_archive(repo, args.source_sha, source_root, run_root / "logs")
        frozen_product = source_root / REQUIRED_PRODUCT
        manifest, assets = read_asset_manifest(frozen_product)
        project_metadata = tomllib.loads((frozen_product / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        sdist_prefix = project_metadata["name"].replace("-", "_") + f"-{project_metadata['version']}"
        expected_original_ids = baseline_node_ids(frozen_product, manifest)
        if len(expected_original_ids) != 91:
            raise WaveFailure(f"original Q2 expected ID denominator changed: {len(expected_original_ids)}")
        current_primary_ids = verify_current_primary_suite_sources(
            frozen_product, manifest, expected_original_ids
        )
        transitive_bindings = verify_transitive_test_bindings(
            frozen_product,
            manifest,
            expected_original_ids,
        )
        receipt["git_archive"] = archive_receipt
        receipt["force_include_assets"] = assets
        receipt["force_include_count"] = len(assets)
        receipt["original_q2_ids"] = len(expected_original_ids)
        receipt["current_primary_suite_node_ids"] = len(current_primary_ids)
        receipt["current_primary_suite_sha256"] = node_ids_sha256(current_primary_ids)
        receipt["historical_baseline_subset_node_ids"] = len(
            historical_baseline_subset_ids(manifest, expected_original_ids)
        )
        receipt["transitive_test_bindings"] = transitive_bindings
        json_write(receipt_path, receipt)

        source_build = run_build(
            uv,
            build_python,
            frozen_product,
            run_root / "dist-source",
            wheel=True,
            sdist=True,
            log_dir=run_root / "logs",
            env=env,
        )
        assert isinstance(source_build, tuple)
        source_wheel, source_sdist = source_build
        source_wheel_receipt = verify_wheel(source_wheel, assets)
        sdist_receipt = verify_tar_assets(
            source_sdist,
            assets,
            member_prefix=f"{sdist_prefix}/",
            exact_force_directories=False,
        )
        sdist_product = product_root_from_sdist(
            source_sdist,
            run_root / "sdist-extracted" / sdist_prefix,
            frozen_product,
            sdist_prefix,
        )
        sdist_wheel = run_build(
            uv,
            build_python,
            sdist_product,
            run_root / "dist-sdist",
            wheel=True,
            sdist=False,
            log_dir=run_root / "logs",
            env=env,
        )
        assert isinstance(sdist_wheel, Path)
        sdist_wheel_receipt = verify_wheel(sdist_wheel, assets)

        gcp_output = run_root / "gcp-archive"
        package_script = frozen_product / "ops/cloud/gcp/package_repo.sh"
        package_env = clean_child_env()
        package_env.update({"OUT_DIR": str(gcp_output), "UPLOAD": "0", "PYTHON_BIN": str(build_python)})
        run_command(
            ["bash", str(package_script)],
            cwd=frozen_product,
            env=package_env,
            log_stem=run_root / "logs" / "gcp-package-archive",
        )
        gcp_archive = one_matching_file(gcp_output, "policy-engine-*.tar.gz")
        gcp_receipt = verify_tar_assets(
            gcp_archive,
            assets,
            member_prefix="policy-engine/",
            exact_force_directories=True,
        )
        gcp_product = product_root_from_gcp(
            gcp_archive,
            run_root / "gcp-extracted" / "policy-engine",
            frozen_product,
        )
        gcp_wheel = run_build(
            uv,
            build_python,
            gcp_product,
            run_root / "dist-gcp",
            wheel=True,
            sdist=False,
            log_dir=run_root / "logs",
            env=env,
        )
        assert isinstance(gcp_wheel, Path)
        gcp_wheel_receipt = verify_wheel(gcp_wheel, assets)

        worker_python, worker_info = run_worker_profile(
            uv,
            args.worker_python,
            frozen_product,
            run_root,
            env,
            run_root / "logs",
        )
        installed_python, purelib = configure_installed_env(
            uv,
            base_python,
            run_root,
            dependency_site,
            frozen_product,
            env,
            run_root / "logs",
        )

        run_inputs = {
            "E02_CATALOG_EXPECTED_JSON": run_root / "catalog-expected.json",
            "E02_PROFILE_EXPECTED_JSON": run_root / "profile-expected.json",
        }
        resources = {}
        for asset in assets:
            if asset["wheel"].startswith(RESOURCE_TARGET_ROOTS[0]):
                resources[Path(asset["source"]).name] = {
                    "bytes": asset["bytes"],
                    "sha256": asset["sha256"],
                }
        worker_assets = {
            Path(asset["source"]).name: {"bytes": asset["bytes"], "sha256": asset["sha256"]}
            for asset in assets
            if asset["source"].startswith("workers/dowhy-014/")
        }
        json_write(run_inputs["E02_CATALOG_EXPECTED_JSON"], {"resources": resources})
        json_write(run_inputs["E02_PROFILE_EXPECTED_JSON"], {"assets": worker_assets})
        receipt["inputs"] = {key: str(path) for key, path in run_inputs.items()}
        receipt["worker"] = worker_info

        profiles = [
            ("source-wheel", source_wheel, source_wheel_receipt),
            ("rebuilt-sdist-wheel", sdist_wheel, sdist_wheel_receipt),
            ("rebuilt-gcp-archive-wheel", gcp_wheel, gcp_wheel_receipt),
        ]
        bridge_consumers = manifest["additional_installed_consumers"][
            "canonical_bridge_and_worker"
        ]
        for name, wheel_path, wheel_receipt in profiles:
            output = run_root / "consumer-runs" / name
            output.mkdir(parents=True, exist_ok=False)
            install = run_command(
                [
                    uv,
                    "pip",
                    "install",
                    "--offline",
                    "--reinstall",
                    "--no-deps",
                    "--python",
                    str(installed_python),
                    str(wheel_path),
                ],
                cwd=run_root,
                env=env,
                log_stem=output / "install-wheel",
            )
            del install
            if tuple(purelib.glob("*.pth")):
                raise WaveFailure(f"wheel install created a .pth file in the isolated env: {name}")
            runtime_proof = installed_runtime_proof(
                installed_python,
                purelib,
                assets,
                frozen_product,
                repo / REQUIRED_PRODUCT,
                dependency_site,
                run_root,
                name,
                env,
                output,
            )
            worker_test_env = clean_child_env()
            worker_test_env.update(
                {
                    **{key: str(value) for key, value in run_inputs.items()},
                    "E02_TEST_DOWHY_WORKER_PYTHON": str(worker_python),
                    "E02_SOURCE_ROOT": str(frozen_product),
                    "E02_LIVE_PRODUCT_ROOT": str(repo / REQUIRED_PRODUCT),
                    "E02_DEPENDENCY_SITE": str(dependency_site),
                    "E02_NODEIDS_REPORT": str(output / "collected-nodeids.json"),
                    "E02_ORIGIN_REPORT": str(output / "origin-proof.json"),
                }
            )
            for kind, relative_path in bridge_consumers["fixture_paths"].items():
                worker_test_env[f"E02_{kind.upper()}_FIXTURE_PATH"] = str(
                    frozen_product / relative_path
                )
            result = run_command(
                pytest_arguments(installed_python, frozen_product, manifest, output),
                cwd=repo,
                env=worker_test_env,
                log_stem=output / "consumer-suite",
                check=False,
                stream_output=True,
            )
            consumer_receipt = verify_consumer_run(
                result,
                run_root=run_root,
                output=output,
                manifest=manifest,
                expected_original_ids=expected_original_ids,
                expected_current_ids=current_primary_ids,
            )
            receipt["profiles"][name] = {
                "wheel": wheel_receipt,
                "installed_runtime": runtime_proof,
                "consumers": consumer_receipt,
            }
            json_write(receipt_path, receipt)

        receipt["artifacts"] = {
            "source_wheel": source_wheel_receipt,
            "source_sdist": sdist_receipt,
            "rebuilt_sdist_wheel": sdist_wheel_receipt,
            "gcp_archive": gcp_receipt,
            "rebuilt_gcp_wheel": gcp_wheel_receipt,
        }
        receipt["status"] = "pass"
        receipt["finished_utc"] = datetime.now(UTC).isoformat()
        json_write(receipt_path, receipt)
        return run_root
    except BaseException as error:
        receipt["status"] = "failed"
        receipt["failure"] = f"{type(error).__name__}: {error}"
        receipt["finished_utc"] = datetime.now(UTC).isoformat()
        json_write(receipt_path, receipt)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="attached, clean repository root")
    parser.add_argument("--source-sha", required=True, help="actual full SHA of the frozen commit")
    parser.add_argument("--source-tree", required=True, help="actual full tree SHA of that commit")
    parser.add_argument("--app-python", required=True, help="absolute existing Python 3.14 build/test dependency interpreter")
    parser.add_argument("--worker-python", help="absolute existing Python 3.12 DoWhy 0.14 worker interpreter")
    parser.add_argument("--output-root", help="optional new-run parent; defaults to this ignored LOCAL raw/runs")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        completed_run = run_wave(parse_args())
    except (OSError, WaveFailure, KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"Q2 frozen installed wave failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Q2 frozen installed wave passed: {completed_run}")
