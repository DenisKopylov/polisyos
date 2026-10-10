#!/usr/bin/env python3
"""Run the frozen composed Mac replay queue with append-only raw receipts.

This harness is intentionally external to the product tree's source and tests.
It binds the supplied Git freeze and root-pinned wrapper/plugin digests before,
and rechecks them around every command. It never removes or overwrites an
output, and stops after the first failed/incomplete command.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import platform
import re
import selectors
import signal
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


WORKTREE = Path("/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos")
PRODUCT_ROOT = WORKTREE / "policy-engine"
LOCAL_RAW = PRODUCT_ROOT / "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw"
PLUGIN_FILE = LOCAL_RAW / "composed_mac_pytest_origin_plugin.py"
NOTE_REL = Path("docs/research/e02-cloud-test-plan/integration/composed-mac-current-source-replay-plan-2026-10-10.md")
PLAN_SCHEMA = "policyos.e02.composed_mac_current_source_replay_plan.v1"
SUPPLEMENT_SCHEMA = "policyos.e02.composed_mac_light_gap_supplement.v1"
SOURCE_INPUT_MANIFEST_SCHEMA = "policyos.composed_mac_local_source_inputs.v3"
THREAD_ENV = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)
REPORT_ROOT_RELS = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/",
    "LOCAL/",
)
CAPTURE_TOOL_REL_PATHS = {
    Path(__file__).resolve().relative_to(PRODUCT_ROOT.resolve()).as_posix(),
    Path("docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_pytest_origin_plugin.py").as_posix(),
}
SOURCE_SUFFIX_PATHSPECS = (
    "*.py", "*.pyi", "*.pyx", "*.pxd", "*.js", "*.mjs", "*.cjs", "*.jsx",
    "*.ts", "*.tsx", "*.java", "*.kt", "*.go", "*.rs", "*.c", "*.h",
    "*.cpp", "*.hpp", "*.sh", "*.sql", "*.toml", "*.yaml", "*.yml",
    "*.ini", "*.cfg", "*.json", "*.md", "*.rst", "*.txt", "*.html", "*.css",
    "*.scss", "*.vue", "*.svelte", "*.xml", "*.graphql", "*.proto", "*.swift",
    "*.m", "*.mm", "*.php", "*.rb", "*.pl", "*.ex", "*.exs", "*.scala",
    "*.clj", "*.cljs", "*.dart", "*.lua", "*.r", "*.R", "*.jl", "*.tf", "*.hcl",
    "*.gradle", "*.properties", "*.lock", "*.ipynb",
)
PYTHON_IMPORT_SUFFIXES = frozenset({
    ".py", ".pyi", ".pyx", ".pxd", ".pyc", ".pyo", ".so", ".dylib", ".dll", ".pyd",
})
PYTHON_IMPORT_SUFFIX_PATHSPECS = tuple(f"*{suffix}" for suffix in sorted(PYTHON_IMPORT_SUFFIXES))
LOCAL_EXECUTABLE_CONFIG_SUFFIXES = frozenset({
    *PYTHON_IMPORT_SUFFIXES,
    ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".sh",
    ".toml", ".yaml", ".yml", ".cfg", ".ini", ".properties",
})
LOCAL_SOURCE_ROOT_RELS = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL",
    "LOCAL",
)
LOCAL_SOURCE_SUFFIX_PATHSPECS = tuple(f"*{suffix}" for suffix in sorted(LOCAL_EXECUTABLE_CONFIG_SUFFIXES))
COMMAND_OUTPUT_EXCLUSION_RULE = (
    "Only validated command output directories, declared scratch directories, and exact output files "
    "derived from root-pinned plan bytes are excluded from source scanning. Their complete produced "
    "filesystem entries "
    "are inventoried separately after each command."
)
RAW_IMPORT_ROOT_REL = Path(
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw"
).as_posix()
RAW_C12_PROFILE_REL = f"{RAW_IMPORT_ROOT_REL}/c12-real-encoder-profile"
RAW_C12_VENV_REL = f"{RAW_C12_PROFILE_REL}/venv"
RAW_C12_HF_CACHE_REL = f"{RAW_C12_PROFILE_REL}/hf-cache"
RAW_C12_PROFILE_ROOT = PRODUCT_ROOT / RAW_C12_PROFILE_REL
RAW_C12_VENV = PRODUCT_ROOT / RAW_C12_VENV_REL
RAW_C12_HF_CACHE = PRODUCT_ROOT / RAW_C12_HF_CACHE_REL
RAW_C12_RECIPE_REL_PATHS = (
    f"{RAW_C12_PROFILE_REL}/uv-sync-offline.txt",
    f"{RAW_C12_PROFILE_REL}/uv-sync-online.txt",
    f"{RAW_C12_PROFILE_REL}/download.command.txt",
)
RAW_C12_EXCLUDED_ROOTS = (RAW_C12_VENV_REL, RAW_C12_HF_CACHE_REL)
LOCAL_BROWSER_CORE_ENV_REL = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/browser-core-venv"
)
LOCAL_BROWSER_CORE_RECIPE_REL_PATHS = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/browser-core-host-env.md",
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/profile-protocol-addendum.md",
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/"
    "browser-core-install-receipt/browser-core-network-install.command.json",
)
LOCAL_BROWSER_CORE_PROJECT_INPUTS = ("pyproject.toml", "uv.lock")
LOCAL_NAMED_ENVIRONMENT_ROOTS = (*RAW_C12_EXCLUDED_ROOTS, LOCAL_BROWSER_CORE_ENV_REL)
RAW_DASHBOARD_NODE_MODULES_REL = (
    f"{RAW_IMPORT_ROOT_REL}/can-options/generator-default-fidelity/"
    "dashboard-prototype/node_modules"
)
RAW_DASHBOARD_NODE_MODULES_TARGET_REL = "apps/runtime-dashboard/node_modules"
RAW_DASHBOARD_PACKAGE_IDENTITY_PATHS = (
    "apps/runtime-dashboard/package.json",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
)
RAW_IMPORT_RUNTIME_EXCLUSIONS = {
    "rationale": "The declared raw import root is scanned recursively except for two exact, named research-environment roots. The C12 virtual environment is a separately provisioned interpreter, never the selected composed-Mac interpreter; its absolute entrypoint, pyvenv config, uv recipes, full installed-distribution inventory, and runtime sys.path basis are bound separately. The HF cache is model input data, never executable source, and receives its own file-level input manifest. No blanket cache, build, LOCAL, or raw exclusion is applied.",
    "excluded_roots": [
        {
            "path": RAW_C12_VENV_REL,
            "kind": "separate_research_virtual_environment",
            "basis": "raw/c12-real-encoder-profile/download.command.txt invokes this exact absolute venv/bin/python only for the separately provisioned C12 encoder profile; composed-Mac command plans select policy-engine/.venv/bin/python. Bind the venv entrypoint, pyvenv.cfg, lock recipes, installed package inventory, and runtime import path separately.",
        },
        {
            "path": RAW_C12_HF_CACHE_REL,
            "kind": "model_asset_input",
            "basis": "Hugging Face cache for intfloat/multilingual-e5-large, reached by the separate C12 profile via HF_HOME; data bytes are not importable program source and are represented by the separate model-asset input manifest.",
        },
    ],
}
IGNORED_GENERATED_PATHSPEC_EXCLUSIONS = (
    ":(exclude).venv/**", ":(exclude)**/.venv/**", ":(exclude)_cache/**",
    ":(exclude)**/_cache/**", ":(exclude)node_modules/**",
    ":(exclude)**/node_modules/**", ":(exclude)**/__pycache__/**",
    ":(exclude)**/.pytest_cache/**", ":(exclude)**/.mypy_cache/**",
    ":(exclude)**/.ruff_cache/**", ":(exclude)**/.tox/**", ":(exclude)**/.nox/**",
    ":(exclude)**/build/**", ":(exclude)**/dist/**", ":(exclude)**/production_data/**",
    ":(exclude)production_data",
    ":(exclude).polisyos/**", ":(exclude).tmp/**", ":(exclude)**/.cache/**",
    ":(exclude).polisyos-tools/**", ":(exclude).pytest_cache/**",
    ":(exclude).ruff_cache/**", ":(exclude)__pycache__/**",
    ":(exclude)production_data/**", ":(exclude)src/_build/**",
)
R4_EXPECTED_CHILD_STREAMS = (
    "cap-1-configured.stdout.txt", "cap-1-configured.stderr.txt",
    "cap-2-configured.stdout.txt", "cap-2-configured.stderr.txt",
    "cap-1-removal.stdout.txt", "cap-1-removal.stderr.txt",
)
SENSITIVE_KEY = re.compile(
    r"secret|token|password|credential|private|(?:api|access)[_-]?key|cookie|auth|dsn|(?:_url|_uri)$", re.I
)


class CaptureError(RuntimeError):
    """A fail-closed capture precondition or receipt error."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", "-C", str(PRODUCT_ROOT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise CaptureError(
            f"git {' '.join(args)} failed ({result.returncode}): "
            f"{result.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return result


@lru_cache(maxsize=1)
def product_git_prefix() -> str:
    """Derive and verify PRODUCT_ROOT's prefix inside the actual Git worktree."""
    repository_root_raw = run_git(["rev-parse", "--show-toplevel"]).stdout.decode().strip()
    repository_root = Path(repository_root_raw).resolve()
    product_root = PRODUCT_ROOT.resolve()
    try:
        product_relative = product_root.relative_to(repository_root)
    except ValueError as exc:
        raise CaptureError("product root is not strictly contained by the Git worktree") from exc
    expected_prefix = "" if product_relative == Path(".") else f"{product_relative.as_posix()}/"
    actual_prefix = run_git(["rev-parse", "--show-prefix"]).stdout.decode().rstrip("\n")
    if actual_prefix != expected_prefix:
        raise CaptureError(
            "Git --show-prefix does not match the resolved product-root location: "
            f"expected={expected_prefix!r}, actual={actual_prefix!r}"
        )
    return expected_prefix.rstrip("/")


def product_git_path(product_relative_path: str) -> str:
    """Map a strictly product-contained path to its Git-object path."""
    relative = PurePosixPath(product_relative_path)
    if (
        not product_relative_path
        or relative.is_absolute()
        or "\\" in product_relative_path
        or ".." in relative.parts
    ):
        raise CaptureError(f"product-relative Git path is not canonical: {product_relative_path!r}")
    product_root = PRODUCT_ROOT.resolve()
    lexical_path = Path(os.path.abspath(product_root.joinpath(*relative.parts)))
    try:
        normalized_relative = lexical_path.relative_to(product_root).as_posix()
    except ValueError as exc:
        raise CaptureError(
            f"Git object path escapes the product root: {product_relative_path!r}"
        ) from exc
    prefix = product_git_prefix()
    return f"{prefix}/{normalized_relative}" if prefix else normalized_relative


def ensure_inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    resolved_root = root.resolve()
    if not resolved.is_relative_to(resolved_root):
        raise CaptureError(f"{label} escapes the permitted root: {path}")
    return resolved


def redact_mapping(values: dict[str, str]) -> dict[str, str]:
    return {
        key: "<redacted>" if SENSITIVE_KEY.search(key) else value
        for key, value in sorted(values.items())
    }


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    try:
        os.write(fd, encoded)
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json_once(path: Path, item: dict[str, Any]) -> None:
    """Atomically create a JSON receipt without replacing an existing path."""
    if path.exists() or path.is_symlink():
        raise CaptureError(f"refusing to overwrite existing receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    encoded = (json.dumps(item, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    with temporary.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, path)
    except FileExistsError as exc:
        raise CaptureError(f"refusing to overwrite existing receipt: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def git_blob_bytes(commit: str, relpath: str) -> bytes:
    result = run_git(["show", f"{commit}:{product_git_path(relpath)}"])
    return result.stdout


def _nul_paths(data: bytes) -> list[str]:
    return [item.decode("utf-8", errors="surrogateescape") for item in data.split(b"\0") if item]


def _path_set_digest(paths: list[str]) -> str:
    return sha256_bytes("\0".join(sorted(paths)).encode("utf-8", errors="surrogateescape"))


def is_allowlisted_report_path(path: str) -> bool:
    return any(path.startswith(root) for root in REPORT_ROOT_RELS) or path == NOTE_REL.as_posix()


def is_python_import_source(path: str) -> bool:
    """Return whether a path is loadable source from the declared raw import root."""
    normalized = path.replace("\\", "/")
    return normalized.startswith(f"{RAW_IMPORT_ROOT_REL}/") and Path(normalized).suffix.lower() in PYTHON_IMPORT_SUFFIXES


def is_local_executable_or_config_path(path: str) -> bool:
    """Return whether a path under either LOCAL root is executable or runtime config."""
    normalized = path.replace("\\", "/")
    under_local = any(
        normalized == root or normalized.startswith(f"{root}/")
        for root in LOCAL_SOURCE_ROOT_RELS
    )
    return under_local and Path(normalized).suffix.lower() in LOCAL_EXECUTABLE_CONFIG_SUFFIXES


def _relative_product_path(path: Path) -> str:
    resolved = ensure_inside(path, PRODUCT_ROOT, "source input")
    return resolved.relative_to(PRODUCT_ROOT.resolve()).as_posix()


def _path_below(relative: str, root: str) -> bool:
    return relative == root or relative.startswith(f"{root}/")


def _lexical_product_relative(path: Path, label: str) -> str:
    """Normalize an absolute path lexically without following an output symlink."""
    if not path.is_absolute():
        raise CaptureError(f"{label} must be absolute: {path}")
    normalized = Path(os.path.abspath(path))
    try:
        return normalized.relative_to(PRODUCT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise CaptureError(f"{label} is outside the product root: {path}") from exc


def _output_root_contains(relative: str, output_roots: list[dict[str, Any]]) -> bool:
    """Return whether a product-relative path belongs to a plan-derived output root."""
    for root in output_roots:
        root_path = root.get("path")
        kind = root.get("kind")
        if not isinstance(root_path, str) or kind not in {"directory", "file"}:
            continue
        if relative == root_path or (kind == "directory" and _path_below(relative, root_path)):
            return True
    return False


def _assert_no_symlink_components(path: Path, label: str) -> None:
    """Reject existing symlink components so declared outputs have one lexical owner."""
    absolute = Path(os.path.abspath(path))
    if not absolute.is_relative_to(PRODUCT_ROOT.resolve()):
        raise CaptureError(f"{label} escapes the product root: {path}")
    current = PRODUCT_ROOT.resolve()
    for part in absolute.relative_to(current).parts:
        current = current / part
        if current.is_symlink():
            raise CaptureError(f"{label} crosses an existing symlink: {current}")


def _command_output_roots(command: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive every source-excluded and inventory root from one validated command."""
    outputs = command["outputs"]
    command_directory = Path(outputs["directory"])
    roots: dict[tuple[str, str], set[str]] = {}

    def add(path: Path, kind: str, role: str) -> None:
        relative = _lexical_product_relative(path, f"{command['id']} {role}")
        if relative == RAW_IMPORT_ROOT_REL or not _path_below(relative, RAW_IMPORT_ROOT_REL):
            raise CaptureError(f"{command['id']} {role} must remain below LOCAL/raw: {path}")
        _assert_no_symlink_components(path, f"{command['id']} {role}")
        key = (relative, kind)
        roots.setdefault(key, set()).add(role)

    add(command_directory, "directory", "command_output_directory")
    for label in ("stdout", "stderr", "metadata", "junit"):
        raw_value = outputs.get(label)
        if raw_value is None:
            continue
        output_file = Path(raw_value)
        relative = _lexical_product_relative(output_file, f"{command['id']} {label}")
        directory_relative = _lexical_product_relative(
            command_directory, f"{command['id']} output directory",
        )
        if relative != directory_relative and not _path_below(relative, directory_relative):
            add(output_file, "file", f"command_{label}")
    environment = command.get("environment", {})
    for key in ("POLISYOS_CACHE_HOME", "POLISYOS_R4_RECEIPT_DIR"):
        value = environment.get(key)
        if value:
            add(Path(value), "directory", key.lower())
    pytest_basetemp: Path | None = None
    for argument in command.get("argv", []):
        if isinstance(argument, str) and argument.startswith("--basetemp="):
            pytest_basetemp = Path(argument.partition("=")[2])
            break
    if command.get("command_type") == "pytest" and pytest_basetemp is None:
        pytest_basetemp = command_directory / "pytest-tmp"
    if pytest_basetemp is not None:
        add(pytest_basetemp, "directory", "pytest_basetemp")
    return [
        {"path": path, "kind": kind, "roles": sorted(roles)}
        for (path, kind), roles in sorted(roots.items())
    ]


def _plan_output_binding(plan_path: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Bind a plan's bytes and every command output root derived from its validated DTO."""
    plan_path = ensure_inside(plan_path, PRODUCT_ROOT, "output-binding plan")
    command_bindings = []
    for command in plan["execution"]["commands"]:
        command_bindings.append({
            "id": command["id"],
            "order": command["order"],
            "roots": _command_output_roots(command),
        })
    output_root = _lexical_product_relative(
        Path(plan["execution"]["output_root"]), "plan output root",
    )
    if output_root == RAW_IMPORT_ROOT_REL or not _path_below(output_root, RAW_IMPORT_ROOT_REL):
        raise CaptureError("plan output root must be a strict descendant of LOCAL/raw")
    return {
        "plan_path": plan_path.relative_to(PRODUCT_ROOT.resolve()).as_posix(),
        "plan_sha256": sha256_file(plan_path),
        "source_schema": plan.get("_adapter_metadata", {}).get("source_schema", plan.get("schema")),
        "output_root": output_root,
        "commands": command_bindings,
    }


def admit_plan_output_root(plan_path: Path, plan: dict[str, Any]) -> Path:
    """Admit the exact output root derived from a previously validated plan DTO.

    The plan binding validates that the root is a strict descendant of LOCAL/raw
    and captures every command output root. This keeps output placement plan-bound
    without relying on a dated directory-name convention.
    """
    binding = _plan_output_binding(plan_path.resolve(), plan)
    relative = binding["output_root"]
    for command in binding["commands"]:
        for root in command["roots"]:
            if root["path"] != relative and not _path_below(root["path"], relative):
                raise CaptureError(
                    f"{command['id']} output root escapes the plan-bound capture root: {root['path']}"
                )
    output_root = PRODUCT_ROOT / relative
    _assert_no_symlink_components(output_root, "plan output root")
    return output_root


def _manifest_output_bindings(
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Recompute pinned output-root associations from the plan files in a source manifest."""
    bindings = manifest.get("plan_output_bindings")
    if not isinstance(bindings, list) or not bindings:
        raise CaptureError("source manifest has no plan-derived output-root bindings")
    actual_bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for expected in bindings:
        if not isinstance(expected, dict):
            raise CaptureError("source manifest plan output binding is malformed")
        relative = expected.get("plan_path")
        if (
            not isinstance(relative, str)
            or relative in seen
            or not is_allowlisted_report_path(relative)
        ):
            raise CaptureError(
                "source manifest plan path is missing, duplicated, or outside LOCAL report roots"
            )
        seen.add(relative)
        path = ensure_inside(PRODUCT_ROOT / relative, PRODUCT_ROOT, "output-binding plan")
        if (
            path.is_symlink()
            or not path.is_file()
            or sha256_file(path) != expected.get("plan_sha256")
        ):
            raise CaptureError(f"source manifest plan bytes changed: {relative}")
        actual_plan = load_and_validate_plan(path)
        actual = _plan_output_binding(path, actual_plan)
        if actual != expected:
            raise CaptureError(f"source manifest plan/output-root association changed: {relative}")
        actual_bindings.append(actual)
    flattened: list[dict[str, Any]] = []
    owned_roots: list[tuple[str, dict[str, Any]]] = []
    for binding in actual_bindings:
        for command in binding["commands"]:
            owner = {"plan_path": binding["plan_path"], "command_id": command["id"]}
            for root in command["roots"]:
                flattened.append(root)
                owned_roots.append((f"{binding['plan_path']}:{command['id']}", root))
    for index, (owner, root) in enumerate(owned_roots):
        for other_owner, other in owned_roots[index + 1 :]:
            if owner == other_owner:
                continue
            overlaps = (
                root["path"] == other["path"]
                or (root["kind"] == "directory" and _path_below(other["path"], root["path"]))
                or (other["kind"] == "directory" and _path_below(root["path"], other["path"]))
            )
            if overlaps:
                raise CaptureError(
                    f"distinct planned commands share output roots: {owner}={root['path']}, "
                    f"{other_owner}={other['path']}"
                )
    # Equal roots from distinct plans are only valid when they name the same command's
    # same output root; the prepared base and supplement use disjoint command paths.
    unique: dict[tuple[str, str], set[str]] = {}
    for root in flattened:
        key = (root["path"], root["kind"])
        unique.setdefault(key, set()).update(root["roles"])
    output_roots = [
        {"path": path, "kind": kind, "roles": sorted(roles)}
        for (path, kind), roles in sorted(unique.items())
    ]
    return actual_bindings, output_roots


def _installed_environment_inventory(python: Path, module_names: tuple[str, ...]) -> dict[str, Any]:
    """Read a venv's complete installed distribution metadata and import origins."""
    query = r'''import importlib.metadata as metadata, importlib.util, json, sys
distributions = []
file_count = 0
for dist in metadata.distributions():
    name = dist.metadata.get("Name") or ""
    version = dist.version or ""
    entries = []
    for item in dist.files or ():
        entries.append((str(item), getattr(getattr(item, "hash", None), "mode", None),
                        getattr(getattr(item, "hash", None), "value", None),
                        getattr(item, "size", None)))
    entries.sort()
    file_count += len(entries)
    distributions.append((name.lower(), version, entries))
distributions.sort()
inventory_bytes = json.dumps(distributions, sort_keys=True, separators=(",", ":")).encode()
modules = {}
for name in __MODULE_NAMES__:
    spec = importlib.util.find_spec(name)
    modules[name] = None if spec is None else {
        "origin": spec.origin,
        "search_locations": list(spec.submodule_search_locations or ()),
    }
print(json.dumps({
    "executable": sys.executable,
    "prefix": sys.prefix,
    "base_prefix": sys.base_prefix,
    "sys_path": sys.path,
    "distribution_count": len(distributions),
    "distribution_file_entry_count": file_count,
    "distribution_inventory_sha256": __import__("hashlib").sha256(inventory_bytes).hexdigest(),
    "module_origins": modules,
}, sort_keys=True))'''
    query = query.replace("__MODULE_NAMES__", repr(module_names))
    query_env = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "HF_HOME", "HF_HUB_CACHE", "TRANSFORMERS_CACHE"):
        query_env.pop(key, None)
    query_env["PYTHONDONTWRITEBYTECODE"] = "1"
    probe = subprocess.run(
        [str(python), "-I", "-c", query], cwd=PRODUCT_ROOT,
        env=query_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if probe.returncode != 0:
        raise CaptureError(
            f"environment package inventory failed ({probe.returncode}): "
            f"{probe.stderr.decode('utf-8', errors='replace')[-2000:]}"
        )
    try:
        return json.loads(probe.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaptureError(f"environment package inventory returned invalid JSON: {exc}") from exc


def _c12_environment_binding() -> dict[str, Any]:
    """Bind the separately provisioned C12 venv without treating it as source."""
    environment_root = ensure_inside(RAW_C12_VENV, LOCAL_RAW, "C12 virtual environment")
    python = environment_root / "bin/python"
    config = environment_root / "pyvenv.cfg"
    if not python.is_file() or not os.access(python, os.X_OK) or not config.is_file():
        raise CaptureError("named C12 virtual-environment inputs are missing or not executable")
    recipes: dict[str, dict[str, Any]] = {}
    for relative in RAW_C12_RECIPE_REL_PATHS:
        recipe = PRODUCT_ROOT / relative
        if recipe.is_symlink() or not recipe.is_file():
            raise CaptureError(f"named C12 environment recipe is missing or not regular: {relative}")
        recipes[relative] = {"byte_count": recipe.stat().st_size, "sha256": sha256_file(recipe)}
    runtime = _installed_environment_inventory(
        python, ("sentence_transformers", "torch", "transformers", "huggingface_hub", "onnxruntime"),
    )
    resolved_python = python.resolve(strict=True)
    return {
        "environment_root": str(environment_root.resolve()),
        "entrypoint": str(python),
        "resolved_entrypoint": str(resolved_python),
        "entrypoint_sha256": sha256_file(resolved_python),
        "pyvenv_cfg": {"byte_count": config.stat().st_size, "sha256": sha256_file(config)},
        "recipe_files": recipes,
        "runtime": runtime,
        "binding_scope": "separate C12 profile environment; composed-Mac commands use policy-engine/.venv/bin/python",
    }


def _browser_core_environment_binding() -> dict[str, Any]:
    """Bind the separately provisioned browser-core venv by its exact recipe and inventory."""
    environment_root = PRODUCT_ROOT / LOCAL_BROWSER_CORE_ENV_REL
    if environment_root.is_symlink() or not environment_root.is_dir():
        raise CaptureError("named browser-core environment is missing, not a directory, or a symlink")
    python = environment_root / "bin/python"
    config = environment_root / "pyvenv.cfg"
    expected_link_target = "/opt/homebrew/opt/python@3.14/bin/python3.14"
    if (
        not python.is_symlink() or os.readlink(python) != expected_link_target
        or not python.is_file() or not os.access(python, os.X_OK) or not config.is_file()
    ):
        raise CaptureError("named browser-core interpreter or pyvenv configuration changed")
    command_path = PRODUCT_ROOT / LOCAL_BROWSER_CORE_RECIPE_REL_PATHS[2]
    try:
        command = json.loads(command_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError(f"browser-core provision command receipt is invalid: {exc}") from exc
    expected_argv = [
        "/opt/homebrew/bin/uv", "sync", "--project", str(PRODUCT_ROOT),
        "--python", "3.14.0", "--locked", "--extra", "runtime-http",
        "--extra", "test", "--group", "dev", "--no-install-project",
    ]
    if command.get("argv") != expected_argv or command.get("env", {}).get("UV_PROJECT_ENVIRONMENT") != str(environment_root):
        raise CaptureError("browser-core environment command does not match its named locked profile")
    uv_path = Path(expected_argv[0])
    if not uv_path.is_file() or not os.access(uv_path, os.X_OK):
        raise CaptureError("browser-core provisioning uv executable is missing or not executable")
    uv_version = subprocess.run(
        [str(uv_path), "--version"], cwd=PRODUCT_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if uv_version.returncode != 0:
        raise CaptureError("browser-core provisioning uv version readback failed")
    version_text = uv_version.stdout.decode("utf-8", errors="replace").strip()
    if version_text.split()[:2] != ["uv", "0.10.6"]:
        raise CaptureError(f"browser-core provisioning uv version changed: {version_text!r}")
    project_inputs: dict[str, dict[str, Any]] = {}
    for relative in LOCAL_BROWSER_CORE_PROJECT_INPUTS:
        source = PRODUCT_ROOT / relative
        if source.is_symlink() or not source.is_file():
            raise CaptureError(f"browser-core locked project input is missing or not regular: {relative}")
        project_inputs[relative] = {"byte_count": source.stat().st_size, "sha256": sha256_file(source)}
    receipt_inputs = command.get("input_sha256_before", {})
    for relative, facts in project_inputs.items():
        receipt_path = str((PRODUCT_ROOT / relative).resolve())
        if receipt_inputs.get(receipt_path) != facts["sha256"]:
            raise CaptureError(f"browser-core installed profile was provisioned from different {relative} bytes")
    recipe_files: dict[str, dict[str, Any]] = {}
    for relative in LOCAL_BROWSER_CORE_RECIPE_REL_PATHS:
        recipe = PRODUCT_ROOT / relative
        if recipe.is_symlink() or not recipe.is_file():
            raise CaptureError(f"browser-core environment recipe is missing or not regular: {relative}")
        recipe_files[relative] = {"byte_count": recipe.stat().st_size, "sha256": sha256_file(recipe)}
    runtime = _installed_environment_inventory(
        python, ("fastapi", "httpx", "pytest", "jax", "jwt", "uvicorn", "polisyos"),
    )
    resolved_python = python.resolve(strict=True)
    if runtime.get("prefix") != str(environment_root.resolve()) or runtime.get("executable") != str(python):
        raise CaptureError("browser-core interpreter runtime does not resolve into its named venv")
    config_bytes = config.read_bytes()
    return {
        "environment_root": str(environment_root.resolve()),
        "entrypoint": str(python),
        "entrypoint_link_target_text": os.readlink(python),
        "resolved_entrypoint": str(resolved_python),
        "entrypoint_sha256": sha256_file(resolved_python),
        "pyvenv_cfg": {"byte_count": len(config_bytes), "sha256": sha256_bytes(config_bytes)},
        "uv": {
            "path": str(uv_path),
            "resolved_path": str(uv_path.resolve(strict=True)),
            "sha256": sha256_file(uv_path.resolve(strict=True)),
            "version": version_text,
        },
        "project_inputs": project_inputs,
        "recipe_files": recipe_files,
        "runtime": runtime,
        "binding_scope": (
            "separate documented browser-core dependency profile; not used by the current composed-Mac queue, "
            "which selects policy-engine/.venv/bin/python"
        ),
    }


def _dashboard_node_modules_binding() -> dict[str, Any]:
    """Bind the one historical dashboard package symlink without copying its tree."""
    link = PRODUCT_ROOT / RAW_DASHBOARD_NODE_MODULES_REL
    if not link.absolute().parent.is_relative_to(LOCAL_RAW.resolve()):
        raise CaptureError("named dashboard package-tree link is outside the raw report root")
    target = PRODUCT_ROOT / RAW_DASHBOARD_NODE_MODULES_TARGET_REL
    if not link.is_symlink():
        raise CaptureError("named dashboard package-tree link is missing or is no longer a symlink")
    target_resolved = target.resolve(strict=True)
    if not target_resolved.is_dir() or link.resolve(strict=True) != target_resolved:
        raise CaptureError("named dashboard package-tree link resolves to an unexpected target")
    local_package_path = PRODUCT_ROOT / RAW_DASHBOARD_PACKAGE_IDENTITY_PATHS[0]
    root_package_path = PRODUCT_ROOT / RAW_DASHBOARD_PACKAGE_IDENTITY_PATHS[1]
    try:
        local_package = json.loads(local_package_path.read_text(encoding="utf-8"))
        root_package = json.loads(root_package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError(f"dashboard package identity inputs are invalid: {exc}") from exc
    tracked_inputs: dict[str, dict[str, Any]] = {}
    for relative in RAW_DASHBOARD_PACKAGE_IDENTITY_PATHS:
        path = PRODUCT_ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise CaptureError(f"dashboard package identity input is missing or not regular: {relative}")
        tracked_inputs[relative] = {"byte_count": path.stat().st_size, "sha256": sha256_file(path)}
    return {
        "link_path": RAW_DASHBOARD_NODE_MODULES_REL,
        "link_target_text": os.readlink(link),
        "resolved_target": target_resolved.relative_to(PRODUCT_ROOT.resolve()).as_posix(),
        "package_identity": {
            "application_name": local_package.get("name"),
            "application_version": local_package.get("version"),
            "workspace_package_manager": root_package.get("packageManager"),
            "tracked_lock_and_manifest_inputs": tracked_inputs,
        },
        "binding_scope": (
            "exact historical dashboard prototype symlink; current composed-Mac queue is Python-only "
            "and does not consume this JS package tree; the full node_modules tree is not copied or claimed immutable"
        ),
    }


def _local_report_alias_binding(path: Path, relative: str) -> dict[str, Any]:
    """Bind a report-root symlink only when its target is inside a scanned LOCAL root."""
    target = path.resolve(strict=True)
    target_relative = _relative_product_path(target)
    if not any(_path_below(target_relative, root) for root in LOCAL_SOURCE_ROOT_RELS):
        raise CaptureError("report-root symlink target is outside the scanned LOCAL roots")
    if not target.is_file() and not target.is_dir():
        raise CaptureError("report-root symlink target is not a regular file or directory")
    binding: dict[str, Any] = {
        "path": relative,
        "link_target_text": os.readlink(path),
        "resolved_target": target_relative,
        "target_kind": "directory" if target.is_dir() else "regular_file",
    }
    if target.is_file() and Path(relative).suffix.lower() in LOCAL_EXECUTABLE_CONFIG_SUFFIXES:
        binding["target_byte_count"] = target.stat().st_size
        binding["target_sha256"] = sha256_file(target)
    return binding


def _hf_model_asset_inventory() -> dict[str, Any]:
    """Describe C12 model-cache inputs separately from executable source files."""
    root = ensure_inside(RAW_C12_HF_CACHE, LOCAL_RAW, "C12 HF cache")
    if root.is_symlink() or not root.is_dir():
        raise CaptureError("named C12 HF model cache is missing, not a directory, or a symlink")
    entries: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            issues.append({"path": str(directory), "reason": f"scan_error:{type(exc).__name__}:{exc}"})
            continue
        for child in children:
            path = Path(child.path)
            relative = path.relative_to(root).as_posix()
            try:
                if child.is_symlink():
                    target = path.resolve(strict=True)
                    ensure_inside(target, root, "C12 HF cache symlink target")
                    if not target.is_file():
                        issues.append({"path": relative, "reason": "symlink_target_not_regular_file"})
                        continue
                    entries.append({
                        "path": relative, "kind": "snapshot_symlink",
                        "target": target.relative_to(root).as_posix(),
                        "target_byte_count": target.stat().st_size,
                    })
                elif child.is_dir(follow_symlinks=False):
                    stack.append(path)
                elif child.is_file(follow_symlinks=False):
                    blob_name = path.name if path.parent.name == "blobs" else None
                    entries.append({
                        "path": relative, "kind": "regular_asset",
                        "byte_count": path.stat(follow_symlinks=False).st_size,
                        "content_address_name": blob_name,
                        "content_sha256_recomputed": False if blob_name else None,
                        "sha256": sha256_file(path) if blob_name is None and path.stat().st_size <= 1_048_576 else None,
                    })
                else:
                    issues.append({"path": relative, "reason": "non_regular_cache_entry"})
            except (OSError, CaptureError) as exc:
                issues.append({"path": relative, "reason": f"admission_error:{type(exc).__name__}:{exc}"})
    entries.sort(key=lambda item: item["path"])
    payload = {"root": str(root.resolve()), "files": entries, "issues": issues}
    payload["inventory_sha256"] = sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return payload


def discover_raw_source_inputs(
    explicit_paths: list[str], output_roots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Enumerate source/config files under the raw import root and declared inputs."""
    output_roots = output_roots or []
    files: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, str]] = []
    root = ensure_inside(LOCAL_RAW, PRODUCT_ROOT, "raw import root")
    if root.is_symlink() or not root.is_dir():
        raise CaptureError(f"raw import root is missing, not a directory, or a symlink: {root}")

    excluded_paths = set(RAW_C12_EXCLUDED_ROOTS)
    excluded_seen: set[str] = set()
    package_tree_binding: dict[str, Any] | None = None
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            issues.append({"path": str(directory), "reason": f"scan_error:{type(exc).__name__}:{exc}"})
            continue
        for entry in entries:
            candidate = Path(entry.path)
            relative = candidate.relative_to(PRODUCT_ROOT).as_posix()
            try:
                if _output_root_contains(relative, output_roots):
                    continue
                if entry.is_symlink():
                    if entry.is_dir(follow_symlinks=True):
                        if relative == RAW_DASHBOARD_NODE_MODULES_REL:
                            try:
                                package_tree_binding = _dashboard_node_modules_binding()
                            except (OSError, CaptureError) as exc:
                                issues.append({"path": relative, "reason": f"named_package_tree_binding_failed:{type(exc).__name__}:{exc}"})
                        else:
                            issues.append({"path": relative, "reason": "symlink_directory_in_import_root"})
                    elif candidate.suffix.lower() in LOCAL_EXECUTABLE_CONFIG_SUFFIXES:
                        issues.append({"path": relative, "reason": "symlink_source_in_import_root"})
                elif entry.is_dir(follow_symlinks=False):
                    if relative in excluded_paths:
                        excluded_seen.add(relative)
                    else:
                        stack.append(candidate)
                elif entry.is_file(follow_symlinks=False) and candidate.suffix.lower() in LOCAL_EXECUTABLE_CONFIG_SUFFIXES:
                    files[relative] = {
                        "path": relative,
                        "byte_count": candidate.stat(follow_symlinks=False).st_size,
                        "sha256": sha256_file(candidate),
                        "role": (
                            "python_import_tree"
                            if candidate.suffix.lower() in PYTHON_IMPORT_SUFFIXES
                            else "local_runtime_source_or_config"
                        ),
                    }
                elif not entry.is_file(follow_symlinks=False):
                    issues.append({"path": relative, "reason": "non_regular_import_root_entry"})
            except OSError as exc:
                issues.append({"path": relative, "reason": f"read_error:{type(exc).__name__}:{exc}"})

    for relative in sorted(excluded_paths - excluded_seen):
        issues.append({"path": relative, "reason": "named_exclusion_root_missing_or_not_directory"})
    if package_tree_binding is None:
        issues.append({
            "path": RAW_DASHBOARD_NODE_MODULES_REL,
            "reason": "named_dashboard_package_tree_link_missing_or_unbound",
        })

    for relative in sorted(set(explicit_paths)):
        normalized = Path(relative).as_posix()
        if _output_root_contains(normalized, output_roots):
            issues.append({"path": normalized, "reason": "declared_source_input_overlaps_command_output"})
            continue
        if not is_allowlisted_report_path(normalized):
            continue
        candidate = PRODUCT_ROOT / normalized
        if candidate.is_symlink():
            issues.append({"path": normalized, "reason": "symlink_declared_local_input"})
            continue
        try:
            resolved = ensure_inside(candidate, PRODUCT_ROOT, "declared local input")
        except CaptureError as exc:
            issues.append({"path": normalized, "reason": f"outside_product_root:{exc}"})
            continue
        if not resolved.is_file():
            issues.append({"path": normalized, "reason": "declared_local_input_not_regular_file"})
            continue
        files[normalized] = {
            "path": normalized,
            "byte_count": resolved.stat().st_size,
            "sha256": sha256_file(resolved),
            "role": "explicit_local_plan_or_fixture",
        }
    return {
        "roots": [RAW_IMPORT_ROOT_REL],
        "excluded_roots": sorted(excluded_paths),
        "named_package_tree_exclusion": package_tree_binding,
        "exact_paths": sorted(set(explicit_paths)),
        "files": [files[path] for path in sorted(files)],
        "issues": issues,
    }


def discover_local_source_inputs(
    explicit_paths: list[str], output_roots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Enumerate executable/config inputs across both LOCAL report roots."""
    output_roots = output_roots or []
    raw = discover_raw_source_inputs(explicit_paths, output_roots)
    files = {entry["path"]: entry for entry in raw["files"]}
    issues = list(raw["issues"])
    symlink_aliases: list[dict[str, Any]] = []
    excluded_paths = set(LOCAL_NAMED_ENVIRONMENT_ROOTS)
    roots = [PRODUCT_ROOT / relative for relative in LOCAL_SOURCE_ROOT_RELS]
    for local_root in roots:
        if local_root.is_symlink() or not local_root.is_dir():
            issues.append({"path": str(local_root), "reason": "local_source_root_missing_or_not_directory"})
            continue
        stack = [local_root]
        while stack:
            directory = stack.pop()
            try:
                entries = sorted(os.scandir(directory), key=lambda item: item.name)
            except OSError as exc:
                issues.append({"path": str(directory), "reason": f"scan_error:{type(exc).__name__}:{exc}"})
                continue
            for entry in entries:
                candidate = Path(entry.path)
                relative = candidate.relative_to(PRODUCT_ROOT).as_posix()
                if relative == RAW_IMPORT_ROOT_REL and candidate.is_dir() and not candidate.is_symlink():
                    # The raw root has its own import-aware walk above, including named exclusions.
                    continue
                try:
                    if _output_root_contains(relative, output_roots):
                        continue
                    if relative in excluded_paths:
                        continue
                    if relative == RAW_DASHBOARD_NODE_MODULES_REL and entry.is_symlink():
                        # The exact historical prototype tree is bound separately; do not traverse/copy it.
                        continue
                    if entry.is_symlink():
                        try:
                            alias = _local_report_alias_binding(candidate, relative)
                        except (OSError, CaptureError) as exc:
                            issues.append({"path": relative, "reason": f"unbound_local_symlink:{type(exc).__name__}:{exc}"})
                        else:
                            symlink_aliases.append(alias)
                            if alias["target_kind"] == "regular_file" and candidate.suffix.lower() in LOCAL_EXECUTABLE_CONFIG_SUFFIXES:
                                files[relative] = {
                                    "path": relative,
                                    "byte_count": alias["target_byte_count"],
                                    "sha256": alias["target_sha256"],
                                    "role": "local_symlink_source_alias",
                                }
                    elif entry.is_dir(follow_symlinks=False):
                        stack.append(candidate)
                    elif entry.is_file(follow_symlinks=False) and candidate.suffix.lower() in LOCAL_EXECUTABLE_CONFIG_SUFFIXES:
                        if relative not in files:
                            files[relative] = {
                                "path": relative,
                                "byte_count": candidate.stat(follow_symlinks=False).st_size,
                                "sha256": sha256_file(candidate),
                                "role": "local_executable_or_config_source",
                            }
                    elif not entry.is_file(follow_symlinks=False) and candidate.suffix.lower() in LOCAL_EXECUTABLE_CONFIG_SUFFIXES:
                        issues.append({"path": relative, "reason": "non_regular_local_source_root_entry"})
                except OSError as exc:
                    issues.append({"path": relative, "reason": f"read_error:{type(exc).__name__}:{exc}"})
    return {
        "roots": list(LOCAL_SOURCE_ROOT_RELS),
        "excluded_roots": sorted(excluded_paths),
        "named_package_tree_exclusion": raw["named_package_tree_exclusion"],
        "symlink_aliases": sorted(symlink_aliases, key=lambda item: item["path"]),
        "exact_paths": raw["exact_paths"],
        "files": [files[path] for path in sorted(files)],
        "issues": issues,
    }


def source_manifest_digest(manifest: dict[str, Any]) -> str:
    """Hash a canonical source manifest without its self-referential digest field."""
    payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def verify_raw_source_manifest(path: Path, expected_sha256: str) -> dict[str, Any]:
    """Verify a root-pinned manifest against every importable raw source byte."""
    if path.is_symlink() or not path.is_file():
        return {"status": "FAIL", "reason": "manifest_missing_or_not_regular", "path": str(path)}
    actual_file_sha = sha256_file(path)
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256) or actual_file_sha != expected_sha256.lower():
        return {
            "status": "FAIL", "reason": "manifest_file_hash_mismatch", "path": str(path),
            "expected_sha256": expected_sha256.lower(), "actual_sha256": actual_file_sha,
        }
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "FAIL", "reason": f"manifest_invalid:{type(exc).__name__}:{exc}", "path": str(path)}
    if manifest.get("schema") != SOURCE_INPUT_MANIFEST_SCHEMA:
        return {"status": "FAIL", "reason": "manifest_schema_mismatch", "path": str(path)}
    if manifest.get("manifest_sha256") != source_manifest_digest(manifest):
        return {"status": "FAIL", "reason": "manifest_content_digest_mismatch", "path": str(path)}
    binding = manifest.get("runtime_import_binding", {})
    if (
        not isinstance(binding, dict)
        or binding.get("root") != RAW_IMPORT_ROOT_REL
        or binding.get("recursive") is not True
        or binding.get("suffixes") != sorted(PYTHON_IMPORT_SUFFIXES)
        or binding.get("excluded_roots") != RAW_IMPORT_RUNTIME_EXCLUSIONS["excluded_roots"]
        or binding.get("exclusion_basis") != RAW_IMPORT_RUNTIME_EXCLUSIONS["rationale"]
    ):
        return {"status": "FAIL", "reason": "manifest_runtime_import_profile_mismatch", "path": str(path)}
    local_binding = manifest.get("local_source_binding")
    if (
        not isinstance(local_binding, dict)
        or local_binding.get("roots") != list(LOCAL_SOURCE_ROOT_RELS)
        or local_binding.get("recursive") is not True
        or local_binding.get("suffixes") != sorted(LOCAL_EXECUTABLE_CONFIG_SUFFIXES)
        or local_binding.get("excluded_runtime_roots") != sorted(LOCAL_NAMED_ENVIRONMENT_ROOTS)
        or local_binding.get("command_output_exclusion_rule") != COMMAND_OUTPUT_EXCLUSION_RULE
    ):
        return {"status": "FAIL", "reason": "manifest_local_source_profile_mismatch", "path": str(path)}
    try:
        actual_plan_bindings, output_roots = _manifest_output_bindings(manifest)
    except (OSError, json.JSONDecodeError, CaptureError, KeyError, TypeError) as exc:
        return {
            "status": "FAIL", "reason": "manifest_output_root_binding_mismatch", "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    exact_paths = manifest.get("exact_paths")
    if (
        not isinstance(exact_paths, list)
        or not all(isinstance(value, str) and is_allowlisted_report_path(value) for value in exact_paths)
        or exact_paths != sorted(set(exact_paths))
    ):
        return {"status": "FAIL", "reason": "manifest_exact_path_profile_mismatch", "path": str(path)}
    current = discover_local_source_inputs(exact_paths, output_roots)
    raw_current = discover_raw_source_inputs([], output_roots)
    expected_files = manifest.get("files")
    if not isinstance(expected_files, list):
        return {"status": "FAIL", "reason": "manifest_files_invalid", "path": str(path)}
    expected_by_path = {entry.get("path"): entry for entry in expected_files if isinstance(entry, dict)}
    current_by_path = {entry["path"]: entry for entry in current["files"]}
    same_paths = set(current_by_path) == set(expected_by_path)
    same_bytes = same_paths and all(
        current_by_path[key].get("sha256") == expected_by_path[key].get("sha256")
        and current_by_path[key].get("byte_count") == expected_by_path[key].get("byte_count")
        for key in expected_by_path
    )
    expected_raw_files = manifest.get("raw_import_files")
    if not isinstance(expected_raw_files, list):
        return {"status": "FAIL", "reason": "manifest_raw_import_files_invalid", "path": str(path)}
    expected_raw_path_list = sorted(
        entry.get("path") for entry in expected_raw_files
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    )
    if (
        len(expected_raw_path_list) != len(expected_raw_files)
        or binding.get("path_count") != len(expected_raw_path_list)
        or binding.get("path_set_sha256") != _path_set_digest(expected_raw_path_list)
    ):
        return {"status": "FAIL", "reason": "manifest_raw_import_path_binding_mismatch", "path": str(path)}
    expected_raw_by_path = {
        entry.get("path"): entry for entry in expected_raw_files if isinstance(entry, dict)
    }
    current_raw_by_path = {
        entry["path"]: entry for entry in raw_current["files"]
        if is_python_import_source(entry["path"])
    }
    same_raw_paths = set(current_raw_by_path) == set(expected_raw_by_path)
    same_raw_bytes = same_raw_paths and all(
        current_raw_by_path[key].get("sha256") == expected_raw_by_path[key].get("sha256")
        and current_raw_by_path[key].get("byte_count") == expected_raw_by_path[key].get("byte_count")
        for key in expected_raw_by_path
    )
    current_package_tree = current.get("named_package_tree_exclusion")
    expected_package_tree = local_binding.get("named_package_tree_exclusion")
    package_tree_matches = current_package_tree == expected_package_tree
    local_symlink_aliases_match = current.get("symlink_aliases") == local_binding.get("symlink_aliases")
    no_issues = not current["issues"] and not raw_current["issues"]
    excluded_runtime_inputs = manifest.get("excluded_runtime_inputs")
    excluded_runtime_status = "FAIL"
    excluded_runtime_error: str | None = None
    try:
        if not isinstance(excluded_runtime_inputs, dict):
            raise CaptureError("manifest excluded_runtime_inputs is missing")
        current_environment = _c12_environment_binding()
        if current_environment != excluded_runtime_inputs.get("c12_environment"):
            raise CaptureError("named C12 environment binding changed")
        current_browser_environment = _browser_core_environment_binding()
        if current_browser_environment != excluded_runtime_inputs.get("browser_core_environment"):
            raise CaptureError("named browser-core environment binding changed")
        asset_ref = excluded_runtime_inputs.get("model_asset_manifest")
        if not isinstance(asset_ref, dict):
            raise CaptureError("separate model-asset manifest reference is missing")
        asset_path = ensure_inside(PRODUCT_ROOT / str(asset_ref.get("path", "")), LOCAL_RAW, "model-asset manifest")
        if asset_path.is_symlink() or not asset_path.is_file():
            raise CaptureError("separate model-asset manifest is missing or not regular")
        if sha256_file(asset_path) != asset_ref.get("file_sha256"):
            raise CaptureError("separate model-asset manifest file hash changed")
        asset = json.loads(asset_path.read_text(encoding="utf-8"))
        if (
            not isinstance(asset, dict)
            or asset.get("schema") != "policyos.composed_mac_separate_model_asset_inputs.v1"
            or asset.get("status") != "asset_inventory_prepared_not_execution_receipt"
            or asset.get("inventory_sha256") != asset_ref.get("inventory_sha256")
        ):
            raise CaptureError("separate model-asset manifest binding is invalid")
        current_assets = _hf_model_asset_inventory()
        if current_assets != {
            "root": asset.get("root"), "files": asset.get("files"),
            "issues": asset.get("issues"), "inventory_sha256": asset.get("inventory_sha256"),
        }:
            raise CaptureError("separate model-asset input inventory changed")
        excluded_runtime_status = "PASS"
    except (OSError, json.JSONDecodeError, CaptureError, TypeError, KeyError) as exc:
        excluded_runtime_error = f"{type(exc).__name__}: {exc}"
    return {
        "status": "PASS" if (
            same_paths and same_bytes and same_raw_paths and same_raw_bytes and package_tree_matches
            and local_symlink_aliases_match and no_issues and excluded_runtime_status == "PASS"
            and actual_plan_bindings == manifest.get("plan_output_bindings")
        ) else "FAIL",
        "path": str(path),
        "manifest_file_sha256": actual_file_sha,
        "expected_manifest_file_sha256": expected_sha256.lower(),
        "manifest_content_sha256": manifest.get("manifest_sha256"),
        "actual_source_file_count": len(current_by_path),
        "expected_source_file_count": len(expected_by_path),
        "source_path_set_matches": same_paths,
        "source_bytes_match": same_bytes,
        "issues": [*current["issues"], *raw_current["issues"]],
        "raw_import_source_path_count": len(current_raw_by_path),
        "expected_raw_import_source_path_count": len(expected_raw_by_path),
        "raw_import_source_set_and_bytes_match": same_raw_paths and same_raw_bytes,
        "local_source_roots": list(LOCAL_SOURCE_ROOT_RELS),
        "plan_output_bindings": actual_plan_bindings,
        "declared_output_roots": output_roots,
        "local_source_path_count": len(current_by_path),
        "expected_local_source_path_count": len(expected_by_path),
        "local_source_set_and_bytes_match": same_paths and same_bytes,
        "named_package_tree_binding_matches": package_tree_matches,
        "local_symlink_aliases_match": local_symlink_aliases_match,
        "excluded_runtime_inputs_status": excluded_runtime_status,
        "excluded_runtime_inputs_error": excluded_runtime_error,
        "added_paths": sorted(set(current_by_path) - set(expected_by_path)),
        "missing_paths": sorted(set(expected_by_path) - set(current_by_path)),
        "changed_paths": sorted(
            key for key in set(current_by_path) & set(expected_by_path)
            if current_by_path[key].get("sha256") != expected_by_path[key].get("sha256")
        ),
        "source_paths_sha256": _path_set_digest(sorted(current_by_path)),
    }


def declared_local_source_paths(plan_path: Path, plan: dict[str, Any]) -> list[str]:
    """Return local plan/config inputs named by the selected plan and its base plan."""
    paths: set[str] = {
        _relative_product_path(plan_path),
        *RAW_C12_RECIPE_REL_PATHS,
        *LOCAL_BROWSER_CORE_RECIPE_REL_PATHS,
    }
    for value in plan.get("_source_plan_paths", []):
        if isinstance(value, str):
            paths.add(Path(value).as_posix())
    manifest = plan.get("execution", {}).get("freeze_input_manifest", {})
    for key in ("source_input_paths", "selected_test_paths"):
        for value in manifest.get(key, []):
            if isinstance(value, str) and is_allowlisted_report_path(Path(value).as_posix()):
                paths.add(Path(value).as_posix())
    for fixture in manifest.get("fixture_inputs", []):
        if isinstance(fixture, dict):
            for key in ("path", "file_path", "source_path"):
                value = fixture.get(key)
                if isinstance(value, str) and is_allowlisted_report_path(Path(value).as_posix()):
                    paths.add(Path(value).as_posix())
    return sorted(paths)


def _plan_uses_only_product_python(plan: dict[str, Any]) -> bool:
    """Confirm every selected command enters through the frozen product Python."""
    commands = plan.get("execution", {}).get("commands", [])
    expected = (PRODUCT_ROOT / ".venv/bin/python").resolve()
    if not isinstance(commands, list) or not commands:
        return False
    for command in commands:
        if not isinstance(command, dict):
            return False
        argv = command.get("argv")
        cwd = Path(command.get("cwd", PRODUCT_ROOT))
        if not isinstance(argv, list) or not argv or not isinstance(argv[0], str):
            return False
        executable = Path(argv[0])
        if not executable.is_absolute():
            executable = cwd / executable
        try:
            if executable.resolve(strict=True) != expected:
                return False
        except OSError:
            return False
    return True


def _is_output_binding_only_plan(plan: dict[str, Any]) -> bool:
    """Recognize the explicit non-executable plan DTO used only for root binding."""
    mode = plan.get("execution_mode")
    execution = plan.get("execution")
    if not isinstance(mode, dict) or not isinstance(execution, dict):
        return False
    commands = execution.get("commands")
    return (
        plan.get("status") == "plan_only_output_binding_routes_not_execution_receipts"
        and mode.get("capture_cli_execution_compatible") is False
        and mode.get("no_execution_performed") is True
        and isinstance(mode.get("purpose"), str)
        and bool(mode["purpose"].strip())
        and isinstance(mode.get("reason"), str)
        and bool(mode["reason"].strip())
        and isinstance(commands, list)
        and bool(commands)
        and all(
            isinstance(command, dict)
            and command.get("command_type") == "external_output_binding"
            for command in commands
        )
    )


def _plan_declares_non_executable_route(plan: dict[str, Any]) -> bool:
    """Fail closed on non-executable or malformed execution-mode declarations."""
    if plan.get("status") == "plan_only_output_binding_routes_not_execution_receipts":
        return True
    if "execution_mode" in plan:
        mode = plan.get("execution_mode")
        if (
            not isinstance(mode, dict)
            or mode.get("capture_cli_execution_compatible") is not True
        ):
            return True
    execution = plan.get("execution")
    commands = execution.get("commands", []) if isinstance(execution, dict) else []
    return isinstance(commands, list) and any(
        isinstance(command, dict)
        and command.get("command_type") == "external_output_binding"
        for command in commands
    )


def _require_capture_cli_selected_plan(plan: dict[str, Any]) -> None:
    """Refuse plans that only describe outputs or do not affirm CLI compatibility."""
    if _plan_declares_non_executable_route(plan):
        raise CaptureError(
            "selected plan is not declared executable by the composed capture CLI"
        )


def create_raw_source_manifest(
    plan_path: Path,
    plan: dict[str, Any],
    *,
    additional_plan_paths: list[Path] | None = None,
    model_asset_manifest_path: Path,
) -> dict[str, Any]:
    """Build the one-time frozen executable/config source set across both LOCAL roots."""
    primary_plan_path = ensure_inside(plan_path, PRODUCT_ROOT, "source manifest plan")
    extra_plan_paths = additional_plan_paths or []
    extra_plan_relatives = {_relative_product_path(path) for path in extra_plan_paths}
    plan_paths = [primary_plan_path, *extra_plan_paths]
    for referenced_path in plan.get("_source_plan_paths", []):
        if isinstance(referenced_path, str):
            candidate = Path(referenced_path)
            plan_paths.append(candidate if candidate.is_absolute() else PRODUCT_ROOT / candidate)
    plan_bindings: list[dict[str, Any]] = []
    explicit_paths: set[str] = set()
    seen_plan_paths: set[str] = set()
    for candidate_path in plan_paths:
        candidate_path = ensure_inside(candidate_path, PRODUCT_ROOT, "source manifest plan")
        relative = candidate_path.relative_to(PRODUCT_ROOT.resolve()).as_posix()
        if relative in seen_plan_paths:
            continue
        seen_plan_paths.add(relative)
        is_primary_plan = candidate_path == primary_plan_path
        candidate_plan = (
            plan if is_primary_plan else load_and_validate_plan(candidate_path)
        )
        output_binding_only = _is_output_binding_only_plan(candidate_plan)
        if output_binding_only:
            if is_primary_plan or relative not in extra_plan_relatives:
                raise CaptureError(
                    "output-binding-only plan must be explicitly named as an additional plan"
                )
            for command in candidate_plan["execution"]["commands"]:
                assert_command_output_roots_absent(command)
        elif _plan_declares_non_executable_route(candidate_plan):
            raise CaptureError(
                "non-executable plan does not satisfy the typed output-binding-only DTO"
            )
        elif not _plan_uses_only_product_python(candidate_plan):
            raise CaptureError("plan output-root binding requires the selected product Python runtime")
        plan_bindings.append(_plan_output_binding(candidate_path, candidate_plan))
        explicit_paths.update(declared_local_source_paths(candidate_path, candidate_plan))
    plan_bindings.sort(key=lambda item: item["plan_path"])
    _, output_roots = _manifest_output_bindings({"plan_output_bindings": plan_bindings})
    if not _plan_uses_only_product_python(plan):
        raise CaptureError("the named dashboard package-tree exclusion is valid only for the Python-only Mac queue")
    if any(_output_root_contains(path, output_roots) for path in explicit_paths):
        raise CaptureError("plan/config/fixture inputs must not overlap command output roots")
    raw_scan = discover_raw_source_inputs([], output_roots)
    source_scan = discover_local_source_inputs(sorted(explicit_paths), output_roots)
    if source_scan["issues"]:
        raise CaptureError(f"raw source import scan found inadmissible entries: {source_scan['issues']}")
    if raw_scan["issues"]:
        raise CaptureError(f"raw Python import scan found inadmissible entries: {raw_scan['issues']}")
    raw_import_files = [entry for entry in raw_scan["files"] if is_python_import_source(entry["path"])]
    manifest: dict[str, Any] = {
        "schema": SOURCE_INPUT_MANIFEST_SCHEMA,
        "created_before_commands": True,
        "product_root": str(PRODUCT_ROOT.resolve()),
        "runtime_import_binding": {
            "root": RAW_IMPORT_ROOT_REL,
            "mechanism": "the capture runner prepends LOCAL/raw to PYTHONPATH for pytest commands",
            "recursive": True,
            "suffixes": sorted(PYTHON_IMPORT_SUFFIXES),
            "excluded_roots": list(RAW_IMPORT_RUNTIME_EXCLUSIONS["excluded_roots"]),
            "exclusion_basis": RAW_IMPORT_RUNTIME_EXCLUSIONS["rationale"],
            "path_count": len(raw_import_files),
            "path_set_sha256": _path_set_digest([entry["path"] for entry in raw_import_files]),
        },
        "local_source_binding": {
            "roots": list(LOCAL_SOURCE_ROOT_RELS),
            "recursive": True,
            "suffixes": sorted(LOCAL_EXECUTABLE_CONFIG_SUFFIXES),
            "excluded_runtime_roots": sorted(LOCAL_NAMED_ENVIRONMENT_ROOTS),
            "named_package_tree_exclusion": source_scan["named_package_tree_exclusion"],
            "symlink_aliases": source_scan["symlink_aliases"],
            "command_output_exclusion_rule": COMMAND_OUTPUT_EXCLUSION_RULE,
            "package_tree_usage_scope": (
                "The current prepared Mac queue uses the product Python interpreter for pytest and tools CLI only. "
                "It contains no Node/package command; this one exact historical prototype link is bound to its "
                "application package identity and workspace lock, without copying the installed JS tree."
            ),
        },
        "excluded_runtime_inputs": {
            "c12_environment": _c12_environment_binding(),
            "browser_core_environment": _browser_core_environment_binding(),
            "model_asset_manifest": {
                "path": _relative_product_path(model_asset_manifest_path),
                "file_sha256": sha256_file(model_asset_manifest_path),
                "inventory_sha256": json.loads(model_asset_manifest_path.read_text(encoding="utf-8"))["inventory_sha256"],
                "scope": "separate model-asset input manifest; not executable import source",
            },
        },
        "other_runtime_bindings": {
            "capture_wrapper": "separately root-pinned by --frozen-capture-wrapper-sha256 and included by the raw import scan",
            "pytest_plugin": "separately root-pinned by --frozen-capture-plugin-sha256 and included by the raw import scan",
            "product_tree": "full tracked tree, index, and working tree are compared to the supplied Git freeze before and after each command",
            "interpreter_environment": "exact planned interpreter path and package-version readback are retained per frozen run",
        },
        "exact_paths": sorted(explicit_paths),
        "plan_output_bindings": plan_bindings,
        "declared_output_roots": output_roots,
        "raw_import_files": raw_import_files,
        "files": source_scan["files"],
        "path_count": len(source_scan["files"]),
        "path_set_sha256": _path_set_digest([entry["path"] for entry in source_scan["files"]]),
        "local_source_roots": source_scan["roots"],
    }
    manifest["manifest_sha256"] = source_manifest_digest(manifest)
    return manifest


def prepare_raw_source_manifest(
    plan_path: Path,
    plan: dict[str, Any],
    destination: Path,
    *,
    additional_plan_paths: list[Path] | None = None,
    model_asset_manifest_destination: Path | None = None,
) -> dict[str, Any]:
    """Write a new manifest exactly once for root review and CLI pinning."""
    destination = ensure_inside(destination, LOCAL_RAW, "source-input manifest output")
    if destination.suffix.lower() != ".json":
        raise CaptureError("source-input manifest output must be a .json file")
    if destination.exists() or destination.is_symlink():
        raise CaptureError(f"refusing to overwrite source-input manifest: {destination}")
    if model_asset_manifest_destination is None:
        model_asset_manifest_destination = destination.with_name(f"{destination.stem}.model-assets.json")
    model_asset_manifest_destination = ensure_inside(
        model_asset_manifest_destination, LOCAL_RAW, "model-asset manifest output",
    )
    if model_asset_manifest_destination.suffix.lower() != ".json":
        raise CaptureError("model-asset manifest output must be a .json file")
    if model_asset_manifest_destination.exists() or model_asset_manifest_destination.is_symlink():
        raise CaptureError(f"refusing to overwrite model-asset manifest: {model_asset_manifest_destination}")
    model_assets = {
        "schema": "policyos.composed_mac_separate_model_asset_inputs.v1",
        "status": "asset_inventory_prepared_not_execution_receipt",
        "model_id": "intfloat/multilingual-e5-large",
        "cache_root": RAW_C12_HF_CACHE_REL,
        "content_identity_boundary": "HF blob names are recorded as upstream cache identifiers; large blob bytes are not rehashed by the source gate.",
        **_hf_model_asset_inventory(),
    }
    write_json_once(model_asset_manifest_destination, model_assets)
    manifest = create_raw_source_manifest(
        plan_path, plan, additional_plan_paths=additional_plan_paths,
        model_asset_manifest_path=model_asset_manifest_destination,
    )
    write_json_once(destination, manifest)
    return {
        "status": "SOURCE_INPUT_MANIFEST_PREPARED_NOT_EXECUTED",
        "path": str(destination),
        "file_sha256": sha256_file(destination),
        "manifest_content_sha256": manifest["manifest_sha256"],
        "path_count": manifest["path_count"],
        "path_set_sha256": manifest["path_set_sha256"],
        "import_root": manifest["runtime_import_binding"],
        "excluded_runtime_inputs": manifest["excluded_runtime_inputs"],
        "model_asset_manifest": {
            "path": str(model_asset_manifest_destination),
            "file_sha256": sha256_file(model_asset_manifest_destination),
            "inventory_sha256": model_assets["inventory_sha256"],
            "file_count": len(model_assets["files"]),
        },
        "paths": manifest["files"],
    }


def evaluate_source_identity_facts(
    *,
    head: str,
    head_tree: str,
    frozen_tree: str,
    commit: str,
    tree: str,
    worktree_diff_status: int,
    staged_diff_status: int,
    untracked_paths: list[str],
    ignored_source_paths: list[str],
    actual_plan_sha256: str,
    expected_plan_sha256: str,
    raw_source_paths: list[str] | None = None,
    expected_raw_source_paths: list[str] | None = None,
    raw_source_hashes: dict[str, str] | None = None,
    expected_raw_source_hashes: dict[str, str] | None = None,
    local_source_paths: list[str] | None = None,
    expected_local_source_paths: list[str] | None = None,
    local_source_hashes: dict[str, str] | None = None,
    expected_local_source_hashes: dict[str, str] | None = None,
    manifested_local_source_paths: list[str] | None = None,
    declared_output_roots: list[dict[str, Any]] | None = None,
    actual_source_manifest_sha256: str | None = None,
    expected_source_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    """Evaluate the complete frozen-source boundary from independently collected facts."""
    reasons: list[str] = []
    declared_output_roots = declared_output_roots or []

    def is_command_output(path: str) -> bool:
        return _output_root_contains(Path(path).as_posix(), declared_output_roots)

    external_untracked_paths = [path for path in untracked_paths if not is_allowlisted_report_path(path)]
    if head != commit:
        reasons.append("HEAD_CHANGED")
    if head_tree != tree or frozen_tree != tree:
        reasons.append("FROZEN_TREE_CHANGED")
    if worktree_diff_status != 0:
        reasons.append("TRACKED_WORKTREE_DIFF")
    if staged_diff_status != 0:
        reasons.append("TRACKED_INDEX_DIFF")
    if external_untracked_paths:
        reasons.append("UNTRACKED_PATHS_OUTSIDE_REPORT_ROOT")
    raw_paths = sorted(raw_source_paths or [])
    expected_raw_paths = sorted(expected_raw_source_paths or [])
    raw_hashes = raw_source_hashes or {}
    expected_raw_hashes = expected_raw_source_hashes or {}
    local_paths = sorted(local_source_paths if local_source_paths is not None else raw_paths)
    expected_local_paths = sorted(
        expected_local_source_paths if expected_local_source_paths is not None else expected_raw_paths
    )
    local_hashes = local_source_hashes if local_source_hashes is not None else raw_hashes
    expected_local_hashes = expected_local_source_hashes if expected_local_source_hashes is not None else expected_raw_hashes
    manifested_paths = set(
        manifested_local_source_paths if manifested_local_source_paths is not None else expected_local_paths
    )
    ignored_unbound = [
        path for path in ignored_source_paths
        if not is_command_output(path) and not is_allowlisted_report_path(path) and path not in manifested_paths
    ]
    if ignored_unbound:
        reasons.append("IGNORED_UNTRACKED_SOURCE_PATHS_OUTSIDE_REPORT_ROOT")
    if (raw_paths != expected_raw_paths or raw_hashes != expected_raw_hashes
            or actual_source_manifest_sha256 != expected_source_manifest_sha256):
        reasons.append("RAW_IMPORT_SOURCE_MANIFEST_MISMATCH")
    if local_paths != expected_local_paths or local_hashes != expected_local_hashes:
        reasons.append("LOCAL_EXECUTABLE_CONFIG_MANIFEST_MISMATCH")
    local_source_candidates = sorted({
        path for path in [*untracked_paths, *ignored_source_paths]
        if is_local_executable_or_config_path(path) and not is_command_output(path)
    })
    unmanifested_local_sources = [path for path in local_source_candidates if path not in manifested_paths]
    if unmanifested_local_sources:
        reasons.append("UNMANIFESTED_LOCAL_EXECUTABLE_OR_CONFIG_PATHS")
    if actual_plan_sha256 != expected_plan_sha256:
        reasons.append("PLAN_BYTES_CHANGED")
    report_paths = [path for path in untracked_paths if is_allowlisted_report_path(path)]
    return {
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "frozen_commit": commit,
        "frozen_tree": tree,
        "head": head,
        "head_tree": head_tree,
        "commit_tree": frozen_tree,
        "tracked_worktree_diff_clean": worktree_diff_status == 0,
        "tracked_index_diff_clean": staged_diff_status == 0,
        "allowlisted_untracked_report_path_count": len(report_paths),
        "allowlisted_untracked_report_paths_sha256": _path_set_digest(report_paths),
        "external_untracked_path_count": len(external_untracked_paths),
        "external_untracked_paths_sha256": _path_set_digest(external_untracked_paths),
        "external_untracked_path_samples": external_untracked_paths[:20],
        "ignored_untracked_source_path_count": len(ignored_unbound),
        "ignored_untracked_source_paths_sha256": _path_set_digest(ignored_unbound),
        "ignored_untracked_source_path_samples": ignored_unbound[:20],
        "unmanifested_local_source_path_count": len(unmanifested_local_sources),
        "unmanifested_local_source_paths_sha256": _path_set_digest(unmanifested_local_sources),
        "unmanifested_local_source_path_samples": unmanifested_local_sources[:20],
        "raw_import_source_path_count": len(raw_paths),
        "raw_import_source_paths_sha256": _path_set_digest(raw_paths),
        "expected_raw_import_source_paths_sha256": _path_set_digest(expected_raw_paths),
        "raw_import_source_set_and_bytes_match": raw_paths == expected_raw_paths and raw_hashes == expected_raw_hashes,
        "local_source_path_count": len(local_paths),
        "expected_local_source_path_count": len(expected_local_paths),
        "local_source_paths_sha256": _path_set_digest(local_paths),
        "expected_local_source_paths_sha256": _path_set_digest(expected_local_paths),
        "local_source_set_and_bytes_match": local_paths == expected_local_paths and local_hashes == expected_local_hashes,
        "source_manifest_sha256": actual_source_manifest_sha256,
        "expected_source_manifest_sha256": expected_source_manifest_sha256,
        "declared_output_root_count": len(declared_output_roots),
        "declared_output_roots_sha256": sha256_bytes(json.dumps(
            declared_output_roots, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")),
        "plan_sha256": actual_plan_sha256,
        "expected_plan_sha256": expected_plan_sha256,
        "tracked_path_count": None,
    }


def inspect_source_identity(
    commit: str,
    tree: str,
    plan_path: Path,
    plan_sha256: str,
    source_manifest_path: Path,
    source_manifest_sha256: str,
) -> dict[str, Any]:
    """Recheck every tracked byte and all untracked source paths against the frozen source."""
    head = run_git(["rev-parse", "HEAD"]).stdout.decode().strip()
    head_tree = run_git(["rev-parse", "HEAD^{tree}"]).stdout.decode().strip()
    frozen_tree = run_git(["rev-parse", f"{commit}^{{tree}}"]).stdout.decode().strip()
    worktree_diff = run_git(
        ["diff", "--quiet", "--no-ext-diff", "--ignore-submodules=none", commit, "--"], check=False
    ).returncode
    staged_diff = run_git(
        ["diff", "--cached", "--quiet", "--no-ext-diff", "--ignore-submodules=none", commit, "--"], check=False
    ).returncode
    untracked = _nul_paths(
        run_git(["ls-files", "--others", "--exclude-standard", "-z"]).stdout
    )
    ignored_source_candidates = _nul_paths(run_git([
        "ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--",
        *SOURCE_SUFFIX_PATHSPECS, *IGNORED_GENERATED_PATHSPEC_EXCLUSIONS,
    ]).stdout)
    if source_manifest_path.is_symlink():
        raise CaptureError("source-input manifest is a symlink")
    manifest_path = ensure_inside(source_manifest_path, LOCAL_RAW, "source-input manifest")
    raw_manifest_check = verify_raw_source_manifest(manifest_path, source_manifest_sha256)
    output_roots: list[dict[str, Any]] = []
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        plan_bindings, output_roots = _manifest_output_bindings(raw_manifest)
        current_plan_rel = _relative_product_path(plan_path)
        if not any(
            item.get("plan_path") == current_plan_rel and item.get("plan_sha256") == plan_sha256.lower()
            for item in plan_bindings
        ):
            raise CaptureError("selected plan bytes/output roots are not bound by the source manifest")
        exact_paths = list(raw_manifest.get("exact_paths", []))
        local_actual = discover_local_source_inputs(exact_paths, output_roots)
        raw_actual = discover_raw_source_inputs([], output_roots)
        local_expected_files = raw_manifest.get("files", [])
        local_actual_hashes = {entry["path"]: entry["sha256"] for entry in local_actual["files"]}
        local_expected_hashes = {
            entry["path"]: entry["sha256"] for entry in local_expected_files if isinstance(entry, dict)
        }
        local_actual_paths = sorted(local_actual_hashes)
        local_expected_paths = sorted(local_expected_hashes)
        raw_expected_files = raw_manifest.get("raw_import_files", [])
        raw_actual_hashes = {
            entry["path"]: entry["sha256"] for entry in raw_actual["files"]
            if is_python_import_source(entry["path"])
        }
        raw_expected_hashes = {
            entry["path"]: entry["sha256"] for entry in raw_expected_files if isinstance(entry, dict)
        }
        raw_actual_paths = sorted(raw_actual_hashes)
        raw_expected_paths = sorted(raw_expected_hashes)
    except (OSError, json.JSONDecodeError, CaptureError, KeyError, TypeError) as exc:
        raw_manifest = {}
        local_actual = {"files": [], "issues": []}
        raw_actual = {"files": [], "issues": [{"path": str(source_manifest_path), "reason": f"manifest_read_error:{type(exc).__name__}:{exc}"}]}
        local_actual_hashes = {}
        local_expected_hashes = {}
        local_actual_paths = []
        local_expected_paths = []
        raw_actual_hashes = {}
        raw_expected_hashes = {}
        raw_actual_paths = []
        raw_expected_paths = []
        raw_manifest_check = {
            "status": "FAIL", "reason": "manifest_or_source_scan_unavailable",
            "path": str(source_manifest_path), "error": f"{type(exc).__name__}: {exc}",
        }
    local_source_paths_set = set(local_actual_paths)
    ignored_source = [
        path for path in ignored_source_candidates
        if not is_allowlisted_report_path(path)
        or (is_local_executable_or_config_path(path) and path in local_source_paths_set)
    ]
    result = evaluate_source_identity_facts(
        head=head, head_tree=head_tree, frozen_tree=frozen_tree, commit=commit, tree=tree,
        worktree_diff_status=worktree_diff, staged_diff_status=staged_diff,
        untracked_paths=untracked, ignored_source_paths=ignored_source,
        actual_plan_sha256=sha256_file(plan_path), expected_plan_sha256=plan_sha256,
        raw_source_paths=raw_actual_paths,
        expected_raw_source_paths=raw_expected_paths,
        raw_source_hashes=raw_actual_hashes,
        expected_raw_source_hashes=raw_expected_hashes,
        local_source_paths=local_actual_paths,
        expected_local_source_paths=local_expected_paths,
        local_source_hashes=local_actual_hashes,
        expected_local_source_hashes=local_expected_hashes,
        manifested_local_source_paths=local_expected_paths,
        declared_output_roots=output_roots,
        actual_source_manifest_sha256=raw_manifest_check.get("manifest_file_sha256"),
        expected_source_manifest_sha256=source_manifest_sha256.lower(),
    )
    if raw_manifest_check.get("status") != "PASS" and "RAW_IMPORT_SOURCE_MANIFEST_MISMATCH" not in result["reasons"]:
        result["status"] = "FAIL"
        result["reasons"].append("RAW_IMPORT_SOURCE_MANIFEST_MISMATCH")
    result["raw_source_manifest"] = raw_manifest_check
    tree_entries = _nul_paths(run_git(["ls-tree", "-r", "-z", "--name-only", commit]).stdout)
    result["tracked_path_count"] = len(tree_entries)
    result["tracked_tree_path_list_sha256"] = _path_set_digest(tree_entries)
    result["untracked_nonignored_path_count"] = len(untracked)
    result["untracked_nonignored_path_set_sha256"] = _path_set_digest(untracked)
    result["ignored_source_scan"] = {
        "suffix_pathspecs": list(SOURCE_SUFFIX_PATHSPECS),
        "generated_exclusions": list(IGNORED_GENERATED_PATHSPEC_EXCLUSIONS),
        "local_source_roots": list(LOCAL_SOURCE_ROOT_RELS),
        "local_executable_config_suffixes": sorted(LOCAL_EXECUTABLE_CONFIG_SUFFIXES),
        "local_source_files_manifested": len(local_expected_paths),
        "declared_output_root_count": len(output_roots),
        "declared_output_roots_sha256": sha256_bytes(json.dumps(
            output_roots, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")),
        "raw_import_root": RAW_IMPORT_ROOT_REL,
        "raw_import_suffixes": sorted(PYTHON_IMPORT_SUFFIXES),
        "raw_import_runtime_exclusions": RAW_IMPORT_RUNTIME_EXCLUSIONS,
        "raw_import_source_manifest_file_count": len(raw_expected_paths),
        "raw_import_source_manifest_paths_sha256": _path_set_digest(raw_expected_paths),
        "named_package_tree_exclusion": raw_manifest.get("local_source_binding", {}).get("named_package_tree_exclusion"),
    }
    return result


def inspect_capture_tool_identity(expected_wrapper_sha256: str, expected_plugin_sha256: str) -> dict[str, Any]:
    """Compare both ignored capture executables to root-pinned hashes; never reset the baseline."""
    wrapper_path = Path(__file__).absolute()
    plugin_path = PLUGIN_FILE.absolute()
    regular_paths = {
        "wrapper": wrapper_path.is_file() and not wrapper_path.is_symlink(),
        "plugin": plugin_path.is_file() and not plugin_path.is_symlink(),
    }
    expected = {
        "wrapper": expected_wrapper_sha256.lower(),
        "plugin": expected_plugin_sha256.lower(),
    }
    actual = {
        "wrapper": sha256_file(wrapper_path) if regular_paths["wrapper"] else None,
        "plugin": sha256_file(plugin_path) if regular_paths["plugin"] else None,
    }
    valid_expected = all(re.fullmatch(r"[0-9a-f]{64}", value) for value in expected.values())
    matches = valid_expected and all(regular_paths.values()) and all(actual[key] == expected[key] for key in expected)
    return {
        "status": "PASS" if matches else "FAIL",
        "path_assertions": regular_paths,
        "paths": {"wrapper": str(wrapper_path), "plugin": str(plugin_path)},
        "expected_sha256": expected,
        "actual_sha256": actual,
        "matches_pinned_runtime_inputs": matches,
    }


def inspect_live_identity(
    commit: str,
    tree: str,
    plan_path: Path,
    plan_sha256: str,
    expected_wrapper_sha256: str,
    expected_plugin_sha256: str,
    source_manifest_path: Path,
    source_manifest_sha256: str,
) -> dict[str, Any]:
    try:
        source = inspect_source_identity(
            commit, tree, plan_path, plan_sha256, source_manifest_path, source_manifest_sha256,
        )
    except (CaptureError, OSError) as exc:
        source = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
    try:
        tools = inspect_capture_tool_identity(expected_wrapper_sha256, expected_plugin_sha256)
    except OSError as exc:
        tools = {
            "status": "FAIL",
            "expected_sha256": {
                "wrapper": expected_wrapper_sha256.lower(),
                "plugin": expected_plugin_sha256.lower(),
            },
            "actual_sha256": {},
            "matches_pinned_runtime_inputs": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "status": "PASS" if source["status"] == "PASS" and tools["status"] == "PASS" else "FAIL",
        "source": source,
        "capture_tools": tools,
    }


def verify_branch_and_freeze(
    commit: str,
    tree: str,
    *,
    plan_path: Path,
    plan_sha256: str,
    expected_wrapper_sha256: str,
    expected_plugin_sha256: str,
    source_manifest_path: Path,
    source_manifest_sha256: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", commit):
        raise CaptureError("--frozen-commit must be a full hexadecimal Git object id")
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", tree):
        raise CaptureError("--frozen-tree must be a full hexadecimal Git tree id")
    branch = run_git(["symbolic-ref", "--quiet", "--short", "HEAD"]).stdout.decode().strip()
    if not branch:
        raise CaptureError("HEAD is detached; refusing to run the frozen replay")
    head = run_git(["rev-parse", "HEAD"]).stdout.decode().strip()
    head_tree = run_git(["rev-parse", "HEAD^{tree}"]).stdout.decode().strip()
    frozen_tree = run_git(["rev-parse", f"{commit}^{{tree}}"]).stdout.decode().strip()
    if head != commit:
        raise CaptureError(f"attached HEAD {head} does not equal supplied freeze {commit}")
    if head_tree != tree or frozen_tree != tree:
        raise CaptureError(
            f"tree mismatch: HEAD={head_tree}, frozen_commit_tree={frozen_tree}, supplied={tree}"
        )
    for tool_rel in CAPTURE_TOOL_REL_PATHS:
        # Check the configured path policy independently of source publication.
        # A tracked tool still has to satisfy every frozen byte/clean-tree check.
        ignored = run_git(["check-ignore", "--no-index", "--quiet", "--", tool_rel], check=False)
        if ignored.returncode != 0:
            raise CaptureError(f"capture tool path is outside the configured ignore policy: {tool_rel}")
    identity = inspect_live_identity(
        commit, tree, plan_path, plan_sha256, expected_wrapper_sha256, expected_plugin_sha256,
        source_manifest_path, source_manifest_sha256,
    )
    if identity["status"] != "PASS":
        raise CaptureError(
            "initial frozen-source/runtime identity failed: "
            + json.dumps(identity, sort_keys=True, ensure_ascii=False)
        )
    return {"branch": branch, "head": head, "tree": head_tree, "identity": identity}


def verify_input_manifest(
    plan_path: Path,
    plan: dict[str, Any],
    commit: str,
    source_manifest_path: Path,
) -> dict[str, Any]:
    manifest = plan["execution"]["freeze_input_manifest"]
    relpaths = list(dict.fromkeys(
        [
            *manifest["source_input_paths"], *manifest["selected_test_paths"],
            *plan.get("_base_input_paths", []), NOTE_REL.as_posix(),
        ]
    ))
    plan_rel = plan_path.resolve().relative_to(PRODUCT_ROOT.resolve()).as_posix()
    relpaths = list(dict.fromkeys([*relpaths, plan_rel]))
    try:
        raw_source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        external_source_shas = {
            item["path"]: item["sha256"]
            for item in raw_source_manifest.get("files", [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise CaptureError(f"cannot read frozen raw source manifest: {type(exc).__name__}: {exc}") from exc
    comparisons: list[dict[str, str]] = []
    git_prefix = product_git_prefix()
    for rel in relpaths:
        candidate = PRODUCT_ROOT / rel
        if candidate.is_symlink():
            raise CaptureError(f"planned input is a symlink: {rel}")
        path = ensure_inside(candidate, PRODUCT_ROOT, f"input {rel}")
        if not path.is_file():
            raise CaptureError(f"planned input is not a regular non-symlink file: {rel}")
        worktree_sha = sha256_file(path)
        git_rel = product_git_path(rel)
        tracked = run_git(["cat-file", "-e", f"{commit}:{git_rel}"], check=False).returncode == 0
        if tracked:
            frozen_sha = sha256_bytes(git_blob_bytes(commit, rel))
            evidence_kind = "git_frozen_blob"
        elif is_allowlisted_report_path(rel) and rel in external_source_shas:
            frozen_sha = external_source_shas[rel]
            evidence_kind = "root_pinned_raw_source_manifest"
        else:
            raise CaptureError(f"planned input is absent from the Git freeze and raw-source manifest: {rel}")
        if worktree_sha != frozen_sha:
            raise CaptureError(
                f"frozen/worktree content mismatch for {rel}: Git={frozen_sha}, worktree={worktree_sha}"
            )
        comparison = {
            "path": rel, "evidence_kind": evidence_kind,
            "frozen_sha256": frozen_sha, "worktree_sha256": worktree_sha,
        }
        if tracked:
            comparison["git_repository_path"] = git_rel
        comparisons.append(comparison)
    return {
        "status": "PASS",
        "coverage_kind": "declared Git inputs plus root-pinned local plans/raw import sources",
        "git_product_prefix": git_prefix,
        "path_count": len(comparisons),
        "files": comparisons,
    }


def validate_canonical_plan(plan: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    """Validate a canonical execution plan without altering its command contract."""
    execution = plan.get("execution", {})
    if Path(execution.get("cwd", "")).resolve() != PRODUCT_ROOT.resolve():
        raise CaptureError("plan cwd does not match the owned product root")
    concurrency = execution.get("concurrency", {})
    if concurrency.get("max_parallel_commands") != 1 or concurrency.get("numerical_threads") != 1:
        raise CaptureError("plan must remain strictly serial with one numerical thread")
    if concurrency.get("xdist") is not False or concurrency.get("pytest_workers") != 1:
        raise CaptureError("plan must not enable pytest xdist or multiple workers")
    for key in THREAD_ENV:
        if execution.get("common_environment", {}).get(key) != "1":
            raise CaptureError(f"plan no longer fixes {key}=1")
    commands = execution.get("commands", [])
    ids = [command.get("id") for command in commands]
    if not commands or len(ids) != len(set(ids)):
        raise CaptureError("plan commands are empty or command IDs are duplicated")
    for expected_order, command in enumerate(commands, 1):
        if command.get("order") != expected_order or command.get("run_status_before_freeze") != "UNRUN":
            raise CaptureError(f"command order/status changed: {command.get('id')}")
        output = command.get("outputs", {})
        directory = Path(output.get("directory", ""))
        if not directory.is_absolute() or directory.is_symlink():
            raise CaptureError(f"command output directory is not absolute: {command.get('id')}")
        ensure_inside(directory, Path(execution["output_root"]), f"output for {command['id']}")
        if output.get("junit") is not None:
            junit_args = [arg.partition("=")[2] for arg in command["argv"] if arg.startswith("--junitxml=")]
            if len(junit_args) != 1 or Path(junit_args[0]).resolve() != Path(output["junit"]).resolve():
                raise CaptureError(f"JUnit path/argv mismatch for {command['id']}")
        for target in ("stdout", "stderr", "metadata", "junit"):
            value = output.get(target)
            if value is not None:
                path = Path(value)
                if not path.is_absolute() or path.is_symlink():
                    raise CaptureError(f"{target} output is not absolute for {command['id']}")
                ensure_inside(path, Path(execution["output_root"]), f"{target} for {command['id']}")
        if not isinstance(command.get("environment"), dict) or not isinstance(command.get("argv"), list):
            raise CaptureError(f"invalid argv/environment for {command['id']}")
    declared_tests = set(plan["execution"]["freeze_input_manifest"]["selected_test_paths"])
    command_tests = {
        arg.split("::", 1)[0]
        for command in commands
        for arg in command["argv"]
        if arg.startswith("tests/")
    }
    if command_tests != declared_tests:
        raise CaptureError("selected_test_paths do not exactly match the command argv test-file set")
    plan["_path"] = str(plan_path.resolve())
    plan.setdefault("_adapter_metadata", {"source_schema": PLAN_SCHEMA, "adapter": "canonical"})
    return plan


def normalize_supplement_document(document: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    """Adapt the explicit 11-command supplement into the common capture contract."""
    if document.get("schema") != SUPPLEMENT_SCHEMA:
        raise CaptureError(f"unexpected supplement schema: {document.get('schema')!r}")
    if document.get("read_only_preparation") is not True or document.get("status") != "plan_only_not_receipt":
        raise CaptureError("supplement must remain a prepared plan, not a prior execution receipt")
    if Path(document.get("product_root", "")).resolve() != PRODUCT_ROOT.resolve():
        raise CaptureError("supplement product_root does not match the owned product root")
    capture_root = Path(document.get("capture_root", ""))
    if not capture_root.is_absolute() or capture_root.is_symlink():
        raise CaptureError("supplement capture_root must be an absolute non-symlink path")
    capture_root = ensure_inside(capture_root, LOCAL_RAW, "supplement capture_root")
    base_value = document.get("base_plan")
    if not isinstance(base_value, str) or not base_value:
        raise CaptureError("supplement must identify its canonical base_plan")
    base_path = Path(base_value)
    if not base_path.is_absolute():
        base_path = PRODUCT_ROOT / base_path
    base_path = ensure_inside(base_path, PRODUCT_ROOT, "supplement base_plan")
    base_plan = load_and_validate_plan(base_path)
    if base_plan.get("schema") != PLAN_SCHEMA:
        raise CaptureError("supplement base_plan must use the canonical plan schema")

    raw_commands = document.get("commands")
    if not isinstance(raw_commands, list) or len(raw_commands) != 11:
        raise CaptureError("supplement must retain its declared 11-command roster")
    normalized: list[dict[str, Any]] = []
    selected_test_paths: list[str] = []
    selected_targets_all: list[str] = []
    command_ids: set[str] = set()
    output_paths: set[str] = set()
    common_environment = {key: "1" for key in THREAD_ENV}
    for order, raw in enumerate(raw_commands, 1):
        if not isinstance(raw, dict):
            raise CaptureError(f"supplement command {order} is not an object")
        ident = raw.get("id")
        if not isinstance(ident, str) or not ident or ident in command_ids:
            raise CaptureError(f"supplement command {order} has an empty or duplicate ID")
        command_ids.add(ident)
        if raw.get("phase") != "light" or raw.get("run_status_before_freeze") != "UNRUN":
            raise CaptureError(f"supplement command must be light and UNRUN: {ident}")
        command_type = raw.get("command_type")
        if command_type not in {"pytest", "source_cli_readback"}:
            raise CaptureError(f"unsupported supplement command type for {ident}: {command_type!r}")
        argv = raw.get("argv")
        environment = raw.get("environment")
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) for arg in argv):
            raise CaptureError(f"supplement command argv is invalid: {ident}")
        if not isinstance(environment, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in environment.items()):
            raise CaptureError(f"supplement command environment is invalid: {ident}")
        for key in THREAD_ENV:
            if environment.get(key) != "1":
                raise CaptureError(f"supplement command {ident} does not fix {key}=1")
        if environment.get("PYTHONDONTWRITEBYTECODE") != "1":
            raise CaptureError(f"supplement command {ident} must disable bytecode writes")
        cwd = Path(raw.get("cwd", ""))
        if not cwd.is_absolute() or cwd.resolve() != PRODUCT_ROOT.resolve():
            raise CaptureError(f"supplement command cwd does not match product root: {ident}")
        planned_python = Path(argv[0])
        if planned_python.is_absolute() or (Path(raw["cwd"]) / planned_python).resolve() != (PRODUCT_ROOT / ".venv/bin/python").resolve():
            raise CaptureError(f"supplement command must use product .venv Python: {ident}")
        output = raw.get("outputs")
        if not isinstance(output, dict):
            raise CaptureError(f"supplement command outputs are missing: {ident}")
        mapped_output = {
            "directory": output.get("directory"),
            "stdout": output.get("stdout"),
            "stderr": output.get("stderr"),
            "metadata": output.get("metadata"),
            "junit": output.get("junit"),
        }
        for label, value in mapped_output.items():
            if label == "junit" and command_type == "source_cli_readback":
                if value is not None:
                    raise CaptureError(f"source CLI command must not claim a JUnit file: {ident}")
                continue
            if not isinstance(value, str) or not Path(value).is_absolute() or Path(value).is_symlink():
                raise CaptureError(f"supplement {label} output must be an absolute non-symlink path: {ident}")
            resolved = ensure_inside(Path(value), capture_root, f"supplement {label} for {ident}")
            if str(resolved) in output_paths:
                raise CaptureError(f"supplement output path is reused: {resolved}")
            output_paths.add(str(resolved))
        directory = Path(mapped_output["directory"])
        if command_type == "pytest":
            if raw.get("backend") != "product .venv / pytest" or environment.get("PYTHONPATH") != "src":
                raise CaptureError(f"supplement pytest backend/profile changed: {ident}")
            if "-m" not in argv or argv[argv.index("-m") + 1:argv.index("-m") + 2] != ["pytest"]:
                raise CaptureError(f"supplement pytest command does not invoke pytest: {ident}")
            if any(arg in {"-n", "--numprocesses", "--dist"} or arg.startswith("-n=") or arg.startswith("--numprocesses=") for arg in argv):
                raise CaptureError(f"supplement pytest command must remain single-process: {ident}")
            targets = raw.get("selected_targets")
            argv_targets = [arg for arg in argv if arg.startswith("tests/")]
            if not isinstance(targets, list) or targets != argv_targets or not targets:
                raise CaptureError(f"supplement selected_targets differ from actual pytest argv: {ident}")
            junit = mapped_output["junit"]
            junit_args = [arg.partition("=")[2] for arg in argv if arg.startswith("--junitxml=")]
            if not isinstance(junit, str) or len(junit_args) != 1 or Path(junit_args[0]).resolve() != Path(junit).resolve():
                raise CaptureError(f"supplement JUnit output does not match its argv: {ident}")
            selected_test_paths.extend(arg.split("::", 1)[0] for arg in argv_targets)
            selected_targets_all.extend(argv_targets)
        else:
            if raw.get("backend") != "product .venv / public tools CLI" or environment.get("PYTHONPATH") != "src:.":
                raise CaptureError(f"supplement source CLI backend/profile changed: {ident}")
            if "-m" not in argv or argv[argv.index("-m") + 1:argv.index("-m") + 2] != ["tools.cli"]:
                raise CaptureError(f"source CLI command does not invoke tools.cli: {ident}")
            required_args = ["validation", "schema-fqn-census", "--output-format", "json", "--repo-root", str(PRODUCT_ROOT)]
            if not all(value in argv for value in required_args):
                raise CaptureError(f"source CLI command does not request the declared JSON census: {ident}")
        normalized.append({
            "id": ident,
            "order": order,
            "phase": "light",
            "run_status_before_freeze": "UNRUN",
            "command_type": command_type,
            "argv": argv,
            "cwd": str(PRODUCT_ROOT),
            "environment": environment,
            "outputs": mapped_output,
            "purpose": raw.get("purpose", ""),
            "prior_wall_time": raw.get("prior_wall_time"),
            "_supplement_source_command": raw,
        })
    if len(set(selected_targets_all)) != len(selected_targets_all):
        raise CaptureError("supplement repeats a pytest selector across commands")
    declared_tests = sorted(set(selected_test_paths))
    base_execution = base_plan["execution"]
    base_manifest = base_execution["freeze_input_manifest"]
    source_inputs = list(dict.fromkeys([
        *base_manifest["source_input_paths"],
        "tools/cli.py",
        "tools/quality/validation/schema_fqn_census.py",
    ]))
    base_input_paths = list(dict.fromkeys([
        *base_manifest["source_input_paths"], *base_manifest["selected_test_paths"],
    ]))
    execution = {
        "cwd": str(PRODUCT_ROOT),
        "output_root": str(capture_root),
        "common_environment": common_environment,
        "concurrency": {
            "max_parallel_commands": 1, "numerical_threads": 1,
            "xdist": False, "pytest_workers": 1,
        },
        "freeze_input_manifest": {
            "path": str(capture_root / "supplement-frozen-input-manifest.json"),
            "status": "derived_direct_paths_from_base_and_supplement_argv",
            "source_input_paths": source_inputs,
            "selected_test_paths": declared_tests,
            "fixture_inputs": list(base_manifest.get("fixture_inputs", [])),
        },
        "commands": normalized,
    }
    plan = {
        "schema": PLAN_SCHEMA,
        "title": document.get("title"),
        "execution": execution,
        "source_scope": base_plan.get("source_scope", {}),
        "_path": str(plan_path.resolve()),
        "_normalized_from_supplement": True,
        "_capture_root": str(capture_root),
        "_base_input_paths": base_input_paths,
        "_source_plan_paths": [
            _relative_product_path(plan_path), _relative_product_path(base_path),
        ],
        "_source_readback_history_paths": [
            str(Path(base_execution["output_root"]) / "runner-history.jsonl"),
            str(capture_root / "runner-history.jsonl"),
        ],
        "_base_plan_sha256": sha256_file(base_path),
        "_supplement_document": document,
        "_adapter_metadata": {
            "source_schema": SUPPLEMENT_SCHEMA,
            "adapter": "explicit_light_gap_supplement_v1",
            "command_order_source": "source document list order, validated as 11 commands",
            "source_document_sha256": sha256_file(plan_path),
            "base_plan_path": str(base_path),
            "base_plan_sha256": sha256_file(base_path),
            "preserved_top_level_context_keys": sorted(set(document) - {"commands"}),
            "preserved_command_field_keys": sorted({key for item in raw_commands for key in item}),
        },
    }
    # Retain the full source document as the adapter's auditable provenance; only
    # the validated execution fields above drive the common runner.
    return validate_canonical_plan(plan, plan_path)


def load_and_validate_plan(plan_path: Path) -> dict[str, Any]:
    if plan_path.is_symlink():
        raise CaptureError("plan path is a symlink")
    plan_path = plan_path.resolve()
    ensure_inside(plan_path, PRODUCT_ROOT, "plan path")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("schema") == SUPPLEMENT_SCHEMA:
        return normalize_supplement_document(plan, plan_path)
    if plan.get("schema") != PLAN_SCHEMA:
        raise CaptureError(f"unexpected plan schema: {plan.get('schema')!r}")
    return validate_canonical_plan(plan, plan_path)


def select_commands(plan: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    commands = plan["execution"]["commands"]
    by_id = {command["id"]: command for command in commands}
    ids = [command["id"] for command in commands]
    if args.only:
        if args.start or args.stop:
            raise CaptureError("use --only or --start/--stop, not both")
        unknown = sorted(set(args.only) - set(by_id))
        if unknown:
            raise CaptureError(f"unknown command IDs: {unknown}")
        selected_ids = [ident for ident in ids if ident in set(args.only)]
        if len(selected_ids) != len(set(args.only)):
            raise CaptureError("--only contains duplicate IDs")
    else:
        start = args.start or ids[0]
        stop = args.stop or ids[-1]
        if start not in by_id or stop not in by_id:
            raise CaptureError("--start/--stop must name command IDs from this plan")
        first, last = ids.index(start), ids.index(stop)
        if first > last:
            raise CaptureError("--start comes after --stop in the frozen queue")
        selected_ids = ids[first : last + 1]
    selected = [by_id[ident] for ident in selected_ids]
    if any(command["phase"] == "heavy" for command in selected) and not args.allow_heavy:
        raise CaptureError("selected queue contains heavy work; pass --allow-heavy after root releases the slot")
    if args.allow_heavy and not any(command["phase"] == "heavy" for command in selected):
        raise CaptureError("--allow-heavy is only valid when a selected command is heavy")
    if not selected:
        raise CaptureError("no commands selected")
    if selected[0]["id"] != "SOURCE_MODULE_READBACK":
        if not has_source_readback_receipt(
            plan, args.frozen_commit, args.frozen_tree, args.frozen_source_input_manifest_sha256,
        ):
            raise CaptureError("SOURCE_MODULE_READBACK has not passed for this plan/freeze; run it first")
    return selected


def history_path(plan: dict[str, Any]) -> Path:
    return Path(plan["execution"]["output_root"]) / "runner-history.jsonl"


def has_source_readback_receipt(
    plan: dict[str, Any],
    frozen_commit: str,
    frozen_tree: str,
    source_manifest_sha256: str,
) -> bool:
    """Bind the prerequisite to shared frozen-source identity, not one plan's bytes."""
    paths = plan.get("_source_readback_history_paths", [str(history_path(plan))])
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file() or path.is_symlink():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                if (
                    item.get("event") == "command_completed"
                    and item.get("command_id") == "SOURCE_MODULE_READBACK"
                    and item.get("status") == "PREFLIGHT_PASS"
                    and item.get("frozen_commit") == frozen_commit
                    and item.get("frozen_tree") == frozen_tree
                    and item.get("source_input_manifest_sha256") == source_manifest_sha256.lower()
                ):
                    return True
        except (OSError, json.JSONDecodeError):
            continue
    return False


def acquire_lock(plan: dict[str, Any]) -> int:
    path = Path(plan["execution"]["output_root"]) / "runner.lock"
    ensure_inside(path, Path(plan["execution"]["output_root"]), "runner lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise CaptureError("runner lock path is a symlink")
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise CaptureError("another capture process holds the serialized run lock") from exc
    return fd


def checked_paths_for_commands(
    plan: dict[str, Any], commands: list[dict[str, Any]]
) -> dict[str, dict[str, Path]]:
    configured_root = Path(plan["execution"]["output_root"])
    if not configured_root.is_absolute() or configured_root.is_symlink():
        raise CaptureError("plan output_root must be absolute and not a symlink")
    root = configured_root.resolve()
    scratch: dict[str, dict[str, Path]] = {}
    all_dirs: list[tuple[str, Path]] = []
    file_targets: set[Path] = set()
    for command in commands:
        ident = command["id"]
        assert_command_output_roots_absent(command)
        outputs = command["outputs"]
        raw_directory = Path(outputs["directory"])
        if raw_directory.is_symlink():
            raise CaptureError(f"command output directory is a symlink: {raw_directory}")
        directory = ensure_inside(raw_directory, root, f"{ident} output")
        targets: dict[str, Path] = {"directory": directory}
        for key in ("stdout", "stderr", "metadata", "junit"):
            if outputs.get(key):
                raw_path = Path(outputs[key])
                if raw_path.is_symlink():
                    raise CaptureError(f"output file is a symlink: {raw_path}")
                path = ensure_inside(raw_path, root, f"{ident} {key}")
                if path in file_targets:
                    raise CaptureError(f"output file collision: {path}")
                file_targets.add(path)
                if path.exists() or path.is_symlink():
                    raise CaptureError(f"refusing to reuse existing output: {path}")
                targets[key] = path
        if directory.exists() or directory.is_symlink():
            raise CaptureError(f"refusing to reuse existing command output directory: {directory}")
        all_dirs.append((ident, directory))

        scratch_dirs: list[tuple[str, Path]] = []
        env = command["environment"]
        for key in ("POLISYOS_CACHE_HOME", "POLISYOS_R4_RECEIPT_DIR"):
            value = env.get(key)
            if value:
                raw_scratch = Path(value)
                if not raw_scratch.is_absolute() or raw_scratch.is_symlink():
                    raise CaptureError(f"{ident} {key} must be absolute and not a symlink")
                scratch_path = ensure_inside(raw_scratch, root, f"{ident} {key}")
                scratch_dirs.append((key, scratch_path))
        for arg in command["argv"]:
            if arg.startswith("--basetemp="):
                value = arg.partition("=")[2]
                raw_scratch = Path(value)
                if not raw_scratch.is_absolute() or raw_scratch.is_symlink():
                    raise CaptureError(f"{ident} pytest basetemp must be absolute and not a symlink")
                scratch_path = ensure_inside(raw_scratch, root, f"{ident} pytest basetemp")
                scratch_dirs.append(("pytest_basetemp", scratch_path))
        if command["command_type"] == "pytest" and not any(k == "pytest_basetemp" for k, _ in scratch_dirs):
            scratch_dirs.append(("pytest_basetemp", ensure_inside(directory / "pytest-tmp", root, f"{ident} pytest basetemp")))
        for key, path in scratch_dirs:
            if path.exists() or path.is_symlink():
                raise CaptureError(f"refusing to reuse existing {key} path: {path}")
            all_dirs.append((ident + ":" + key, path))
        if "POLISYOS_R4_RECEIPT_DIR" in env:
            receipt = Path(env["POLISYOS_R4_RECEIPT_DIR"])
            for name in (
                "cap-1-configured.stdout.txt", "cap-1-configured.stderr.txt",
                "cap-2-configured.stdout.txt", "cap-2-configured.stderr.txt",
                "cap-1-removal.stdout.txt", "cap-1-removal.stderr.txt",
            ):
                file_path = receipt / name
                if file_path.exists() or file_path.is_symlink():
                    raise CaptureError(f"refusing to overwrite R4 child stream: {file_path}")
        scratch[ident] = {key: path for key, path in scratch_dirs}

    for index, (ident, path) in enumerate(all_dirs):
        for other_ident, other in all_dirs[index + 1 :]:
            nested_basetemp = (
                other_ident == ident + ":pytest_basetemp" and other.is_relative_to(path)
            ) or (
                ident == other_ident + ":pytest_basetemp" and path.is_relative_to(other)
            )
            if not nested_basetemp and (
                path == other or path.is_relative_to(other) or other.is_relative_to(path)
            ):
                raise CaptureError(f"scratch/output directory overlap: {ident}={path}, {other_ident}={other}")
    return scratch


def assert_command_output_roots_absent(command: dict[str, Any]) -> list[dict[str, Any]]:
    """Require every declared path for this command to be absent before execution."""
    checked: list[dict[str, Any]] = []
    for root in _command_output_roots(command):
        path = PRODUCT_ROOT / root["path"]
        _assert_no_symlink_components(path, f"{command['id']} preflight output root")
        if path.exists() or path.is_symlink():
            raise CaptureError(
                f"refusing command output root present at per-command preflight: {path}"
            )
        checked.append(root)
    return checked


def refuse_unadmitted_unselected_outputs(
    plan: dict[str, Any], selected_commands: list[dict[str, Any]],
) -> None:
    """Refuse same-plan resume when an unselected command already produced outputs.

    A prior output is reusable only with a source/tool/input-bound receipt and a
    complete inventory admission path. This capture contract has no such prior-run
    admission capability, so existing unselected roots fail closed.
    """
    selected_ids = {command["id"] for command in selected_commands}
    for command in plan["execution"]["commands"]:
        if command["id"] in selected_ids:
            continue
        for root in _command_output_roots(command):
            path = PRODUCT_ROOT / root["path"]
            _assert_no_symlink_components(path, f"{command['id']} prior output root")
            if path.exists() or path.is_symlink():
                raise CaptureError(
                    "same-plan resume is unsupported without a source/input-bound prior-output "
                    f"receipt and complete inventory: {command['id']} {root['path']}"
                )


def inventory_command_outputs(command: dict[str, Any]) -> dict[str, Any]:
    """Capture regular files and symlink entries beneath the plan-derived command roots."""
    all_roots = _command_output_roots(command)
    inventory_roots: list[dict[str, Any]] = []
    for root in sorted(all_roots, key=lambda item: (item["path"].count("/"), item["path"])):
        if any(
            parent["kind"] == "directory"
            and _path_below(root["path"], parent["path"])
            for parent in inventory_roots
        ):
            continue
        inventory_roots.append(root)

    files: list[dict[str, Any]] = []
    symlinks: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    missing_required: list[str] = []
    output_dir = _lexical_product_relative(
        Path(command["outputs"]["directory"]), "command output directory",
    )
    for root in inventory_roots:
        path = PRODUCT_ROOT / root["path"]
        required = root["path"] == output_dir or any(
            command["outputs"].get(key)
            and _lexical_product_relative(
                Path(command["outputs"][key]), f"{command['id']} {key}",
            ) == root["path"]
            for key in ("stdout", "stderr", "junit")
        )
        if not path.exists() and not path.is_symlink():
            if required:
                missing_required.append(root["path"])
            continue

        def record_symlink(candidate: Path) -> None:
            target_text = os.readlink(candidate)
            lexical_target = Path(os.path.abspath(candidate.parent / target_text))
            try:
                target_rel = lexical_target.relative_to(PRODUCT_ROOT.resolve()).as_posix()
            except ValueError:
                target_rel = None
            symlinks.append({
                "path": candidate.relative_to(PRODUCT_ROOT).as_posix(),
                "link_target_text": target_text,
                "lexical_target_product_path": target_rel,
            })

        if path.is_symlink():
            record_symlink(path)
            issues.append({
                "path": root["path"], "reason": "declared_output_root_is_symlink",
            })
            continue
        if root["kind"] == "file":
            if path.is_file():
                files.append({
                    "path": root["path"], "byte_count": path.stat(follow_symlinks=False).st_size,
                    "sha256": sha256_file(path),
                })
            else:
                issues.append({"path": root["path"], "reason": "declared_output_file_not_regular"})
            continue
        if not path.is_dir():
            issues.append({
                "path": root["path"], "reason": "declared_output_directory_not_directory",
            })
            continue
        stack = [path]
        while stack:
            directory = stack.pop()
            try:
                children = sorted(os.scandir(directory), key=lambda item: item.name)
            except OSError as exc:
                issues.append({
                    "path": directory.relative_to(PRODUCT_ROOT).as_posix(),
                    "reason": f"scan_error:{type(exc).__name__}:{exc}",
                })
                continue
            for child in children:
                candidate = Path(child.path)
                relative = candidate.relative_to(PRODUCT_ROOT).as_posix()
                try:
                    if child.is_symlink():
                        record_symlink(candidate)
                    elif child.is_dir(follow_symlinks=False):
                        stack.append(candidate)
                    elif child.is_file(follow_symlinks=False):
                        files.append({
                            "path": relative,
                            "byte_count": candidate.stat(follow_symlinks=False).st_size,
                            "sha256": sha256_file(candidate),
                        })
                    else:
                        issues.append({"path": relative, "reason": "non_regular_output_entry"})
                except OSError as exc:
                    issues.append({"path": relative, "reason": f"read_error:{type(exc).__name__}:{exc}"})
    files.sort(key=lambda item: item["path"])
    symlinks.sort(key=lambda item: item["path"])
    issues.sort(key=lambda item: (item["path"], item["reason"]))
    missing_required.sort()
    return {
        "status": "PASS" if not issues and not missing_required else "FAIL",
        "complete": not issues and not missing_required,
        "inventory_kind": "all_plan_derived_command_outputs_no_follow",
        "command_id": command["id"],
        "bound_roots": all_roots,
        "scanned_roots": inventory_roots,
        "regular_file_count": len(files),
        "regular_files": files,
        "symlink_count": len(symlinks),
        "symlinks": symlinks,
        "missing_required_roots": missing_required,
        "issues": issues,
    }


def package_versions(python_path: Path) -> dict[str, Any]:
    script = r"""import importlib.metadata as m,json,platform,sys
names=('pytest','numpy','torch','botorch','gpytorch','pydantic','jax')
versions={}
for name in names:
    try:
        versions[name]=m.version(name)
    except m.PackageNotFoundError:
        versions[name]=None
distributions=[]
for dist in m.distributions():
    name=dist.metadata.get('Name')
    if isinstance(name,str) and name:
        distributions.append({'name':name,'version':dist.version})
distributions.sort(key=lambda item:(item['name'].casefold(),item['name'],item['version']))
print(json.dumps({
    'python':platform.python_version(),
    'executable':sys.executable,
    'prefix':sys.prefix,
    'base_prefix':sys.base_prefix,
    'packages':versions,
    'installed_distribution_count':len(distributions),
    'installed_distributions':distributions,
},sort_keys=True))"""
    result = subprocess.run(
        [str(python_path), "-c", script],
        cwd=PRODUCT_ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return {"status": "unavailable", "exit_code": result.returncode, "stderr": result.stderr.decode(errors="replace")}
    try:
        return {"status": "read", **json.loads(result.stdout)}
    except json.JSONDecodeError:
        return {"status": "malformed", "stdout": result.stdout.decode(errors="replace")}


def selected_product_python(command: dict[str, Any], plan: dict[str, Any]) -> tuple[Path, Path]:
    """Preserve the selected venv entrypoint while validating its target separately."""
    if not _plan_uses_only_product_python(plan):
        raise CaptureError("all planned commands must use the product virtualenv Python")
    cwd = Path(command["cwd"])
    selected = Path(command["argv"][0])
    if not selected.is_absolute():
        selected = cwd / selected
    lexical_path = Path(os.path.abspath(selected))
    expected_path = Path(os.path.abspath(PRODUCT_ROOT / ".venv/bin/python"))
    if lexical_path != expected_path or not lexical_path.is_relative_to(PRODUCT_ROOT):
        raise CaptureError(f"planned Python entrypoint is outside the product virtualenv: {lexical_path}")
    try:
        resolved_target = lexical_path.resolve(strict=True)
        expected_target = expected_path.resolve(strict=True)
    except OSError as exc:
        raise CaptureError(f"planned product Python target is unavailable: {lexical_path}") from exc
    if resolved_target != expected_target:
        raise CaptureError(f"planned Python target differs from product virtualenv target: {resolved_target}")
    if not lexical_path.is_file() or not os.access(lexical_path, os.X_OK):
        raise CaptureError(f"planned Python executable unavailable: {lexical_path}")
    return lexical_path, resolved_target


def validate_product_python_profile(
    report: dict[str, Any], selected_path: Path, resolved_target: Path,
) -> dict[str, Any]:
    """Fail closed unless package inventory came from the selected product venv."""
    if report.get("status") != "read":
        raise CaptureError(f"selected product Python profile could not be read: {report.get('status')}")
    expected_prefix = (PRODUCT_ROOT / ".venv").resolve(strict=True)
    try:
        prefix = Path(report["prefix"]).resolve(strict=True)
        base_prefix = Path(report["base_prefix"]).resolve(strict=True)
        executable = Path(report["executable"]).resolve(strict=True)
    except (KeyError, OSError, TypeError) as exc:
        raise CaptureError("selected Python profile omitted a valid executable/prefix binding") from exc
    if prefix != expected_prefix:
        raise CaptureError(
            f"selected interpreter prefix is not the product virtualenv: {prefix}"
        )
    if base_prefix == expected_prefix:
        raise CaptureError("selected interpreter reports the product virtualenv as its base prefix")
    if executable != resolved_target:
        raise CaptureError(
            f"selected interpreter executable differs from the planned target: {executable}"
        )
    return {
        **report,
        "selected_executable_path": str(selected_path),
        "resolved_executable_target": str(resolved_target),
        "expected_prefix": str(expected_prefix),
        "prefix_matches_product_venv": True,
    }


def product_python_profile_sha256(profile: dict[str, Any]) -> str:
    """Hash a JSON-stable selected-interpreter and installed-distribution inventory."""
    if (
        not isinstance(profile, dict)
        or profile.get("status") != "read"
        or profile.get("prefix_matches_product_venv") is not True
    ):
        raise CaptureError("selected product Python profile is not a verified inventory")
    canonical = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_bytes(canonical.encode("utf-8"))


def read_product_python_profile(command: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Re-read the command's selected product interpreter and all installed versions."""
    selected_path, resolved_target = selected_product_python(command, plan)
    report = package_versions(selected_path)
    return validate_product_python_profile(report, selected_path, resolved_target)

def actual_argv(
    command: dict[str, Any], scratch: dict[str, Path],
    source_manifest_path: Path | None = None,
    source_manifest_sha256: str | None = None,
) -> tuple[list[str], list[str]]:
    planned = list(command["argv"])
    if command["command_type"] != "pytest":
        if command.get("command_type") == "python" and "--self-test" in planned:
            if len(planned) < 2:
                raise CaptureError("self-test command is missing its Python script")
            script = Path(planned[1])
            if not script.is_absolute():
                script = Path(command.get("cwd", PRODUCT_ROOT)) / script
            try:
                is_self_wrapper = script.resolve(strict=True) == Path(__file__).resolve(strict=True)
            except OSError:
                is_self_wrapper = False
            if is_self_wrapper:
                if planned.count("--self-test") != 1:
                    raise CaptureError("self-test command must contain --self-test exactly once")
                context_options = (
                    "--source-input-manifest",
                    "--frozen-source-input-manifest-sha256",
                )
                if any(
                    argument == option or argument.startswith(f"{option}=")
                    for option in context_options for argument in planned
                ):
                    raise CaptureError("self-test plan argv must not pre-supply root source-manifest context")
                if (
                    source_manifest_path is None
                    or not source_manifest_path.is_absolute()
                    or source_manifest_sha256 is None
                    or re.fullmatch(r"[0-9a-fA-F]{64}", source_manifest_sha256) is None
                ):
                    raise CaptureError("self-test command requires the root-pinned source-manifest context")
                inserted = [
                    "--source-input-manifest", str(source_manifest_path),
                    "--frozen-source-input-manifest-sha256", source_manifest_sha256.lower(),
                ]
                return planned + inserted, inserted
        return planned, []
    try:
        marker = planned.index("pytest", planned.index("-m") + 1)
    except (ValueError, IndexError) as exc:
        raise CaptureError(f"cannot identify pytest argument boundary for {command['id']}") from exc
    inserted: list[str] = []
    if "pytest_basetemp" not in scratch:
        raise CaptureError(f"missing unique basetemp for {command['id']}")
    if not any(arg.startswith("--basetemp=") for arg in planned):
        inserted.append(f"--basetemp={scratch['pytest_basetemp']}")
    actual = planned[: marker + 1] + inserted + planned[marker + 1 :]
    return actual, inserted


def parse_junit(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"valid": False, "reason": "junit_missing", "testcases": []}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {"valid": False, "reason": f"junit_invalid:{type(exc).__name__}:{exc}", "testcases": []}
    results: list[dict[str, Any]] = []
    counts = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0}
    for case in root.iter("testcase"):
        if case.find("error") is not None:
            status = "ERROR"
            detail_node = case.find("error")
        elif case.find("failure") is not None:
            status = "FAIL"
            detail_node = case.find("failure")
        elif case.find("skipped") is not None:
            status = "SKIP"
            detail_node = case.find("skipped")
        else:
            status = "PASS"
            detail_node = None
        counts[status] += 1
        nodeid = f"{case.get('classname', '<unknown>')}::{case.get('name', '<unnamed>')}"
        result: dict[str, Any] = {
            "nodeid": nodeid,
            "status": status,
            "time_seconds": case.get("time"),
        }
        if detail_node is not None:
            result["message"] = detail_node.get("message")
            result["text"] = (detail_node.text or "")
        results.append(result)
    return {"valid": True, "counts": counts, "testcase_count": len(results), "testcases": results}


def process_rss_kb(pid: int) -> int | None:
    try:
        result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, check=False)
        if result.returncode != 0:
            return None
        value = result.stdout.decode().strip()
        return int(value) if value else None
    except (OSError, ValueError):
        return None


def capture_process(
    argv: list[str], cwd: Path, environment: dict[str, str], stdout_path: Path, stderr_path: Path
) -> tuple[int, float, str, str, int | None, int]:
    start_utc = utc_now()
    started = time.monotonic()
    with stdout_path.open("xb") as stdout_file, stderr_path.open("xb") as stderr_file:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
        )
        assert process.stdout is not None and process.stderr is not None
        selector = selectors.DefaultSelector()
        streams = {process.stdout: (stdout_file, "stdout"), process.stderr: (stderr_file, "stderr")}
        for stream in streams:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        max_rss: int | None = None
        next_rss_sample = started
        interrupted = False
        while selector.get_map():
            try:
                events = selector.select(timeout=0.2)
            except KeyboardInterrupt:
                interrupted = True
                try:
                    os.killpg(process.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass
                continue
            for key, _ in events:
                stream = key.fileobj
                data = os.read(stream.fileno(), 65536)
                if data:
                    output_file, _name = streams[stream]
                    output_file.write(data)
                    output_file.flush()
                else:
                    selector.unregister(stream)
                    stream.close()
            now = time.monotonic()
            if now >= next_rss_sample:
                sample = process_rss_kb(process.pid)
                if sample is not None:
                    max_rss = sample if max_rss is None else max(max_rss, sample)
                next_rss_sample = now + 1.0
        selector.close()
        return_code = process.wait()
        stdout_file.flush()
        stderr_file.flush()
        os.fsync(stdout_file.fileno())
        os.fsync(stderr_file.fileno())
    ended = time.monotonic()
    end_utc = utc_now()
    return return_code, ended - started, start_utc, end_utc, max_rss, process.pid


def check_module_origin_receipts(output_dir: Path, parent_pid: int | None) -> dict[str, Any]:
    paths = sorted(output_dir.glob("module-origins-*.json"))
    if not paths:
        return {"status": "MISSING", "passed": False, "receipts": []}
    receipts: list[dict[str, Any]] = []
    parent_seen = False
    for path in paths:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            receipts.append({"path": str(path), "status": "INVALID", "passed": False, "error": str(exc)})
            continue
        assertion = manifest.get("assertion", {})
        pid_match = path.stem.rsplit("-", 1)[-1]
        if parent_pid is not None and pid_match == str(parent_pid):
            parent_seen = True
        receipts.append({
            "path": str(path), "sha256": sha256_file(path),
            "status": "PASS" if assertion.get("passed") is True else "FAIL",
            "passed": assertion.get("passed") is True,
            "process_id": pid_match,
            "module_count": manifest.get("module_count"),
            "outside_product_root": assertion.get("outside_product_root", []),
        })
    passed = parent_seen and bool(receipts) and all(item.get("passed") is True for item in receipts)
    return {"status": "PASS" if passed else "FAIL", "passed": passed, "parent_process_receipt_seen": parent_seen, "receipts": receipts}


def inventory_child_output_directory(path: Path, expected_names: tuple[str, ...]) -> dict[str, Any]:
    """Inventory all produced regular child files before deciding the outer test result."""
    issues: list[dict[str, str]] = []
    files: list[dict[str, Any]] = []
    if path.is_symlink():
        return {
            "status": "FAIL", "complete": False, "directory": str(path),
            "reason": "receipt_directory_is_symlink", "files": [],
            "missing_expected_files": list(expected_names), "issues": [],
        }
    if not path.exists():
        return {
            "status": "FAIL", "complete": False, "directory": str(path),
            "reason": "receipt_directory_missing", "files": [],
            "missing_expected_files": list(expected_names), "issues": [],
        }
    if not path.is_dir():
        return {
            "status": "FAIL", "complete": False, "directory": str(path),
            "reason": "receipt_path_not_directory", "files": [],
            "missing_expected_files": list(expected_names), "issues": [],
        }

    stack = [path]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            issues.append({"path": str(directory), "reason": f"scan_error:{type(exc).__name__}:{exc}"})
            continue
        for entry in entries:
            child = Path(entry.path)
            relative = child.relative_to(path).as_posix()
            try:
                if entry.is_symlink():
                    issues.append({"path": relative, "reason": "symlink_not_admitted"})
                elif entry.is_dir(follow_symlinks=False):
                    stack.append(child)
                elif entry.is_file(follow_symlinks=False):
                    files.append({
                        "path": relative,
                        "byte_count": child.stat(follow_symlinks=False).st_size,
                        "sha256": sha256_file(child),
                    })
                else:
                    issues.append({"path": relative, "reason": "non_regular_filesystem_entry"})
            except OSError as exc:
                issues.append({"path": relative, "reason": f"read_error:{type(exc).__name__}:{exc}"})
    files.sort(key=lambda item: item["path"])
    present = {item["path"] for item in files}
    missing = [name for name in expected_names if name not in present]
    complete = not issues and not missing
    return {
        "status": "PASS" if complete else "FAIL",
        "complete": complete,
        "directory": str(path),
        "inventory_kind": "recursive_regular_file_inventory_no_symlinks",
        "file_count": len(files),
        "files": files,
        "missing_expected_files": missing,
        "issues": issues,
        "expected_file_names": list(expected_names),
    }


def classify(
    command: dict[str, Any],
    return_code: int,
    junit: dict[str, Any] | None,
    origin: dict[str, Any] | None,
) -> str:
    if return_code == -signal.SIGINT:
        return "INTERRUPTED"
    if command["command_type"] != "pytest":
        return "PREFLIGHT_PASS" if return_code == 0 else "EXIT_NONZERO"
    if return_code not in (0, 1):
        return "EXIT_NONZERO"
    if junit is None or not junit.get("valid"):
        return "JUNIT_INVALID" if return_code == 0 else "EXIT_NONZERO"

    counts = junit.get("counts", {})
    if return_code == 1:
        if counts.get("ERROR", 0):
            return "ERROR"
        if counts.get("FAIL", 0):
            return "FAIL"
        return "EXIT_NONZERO"
    if counts.get("ERROR", 0):
        return "ERROR"
    if counts.get("FAIL", 0):
        return "FAIL"
    if counts.get("SKIP", 0):
        return "UNCLASSIFIED_SKIP"
    if counts.get("PASS", 0) != junit.get("testcase_count") or junit.get("testcase_count", 0) == 0:
        return "JUNIT_INCOMPLETE"
    if origin is None or not origin.get("passed"):
        return "MODULE_ORIGIN_ASSERTION_FAIL"
    return "PASS"


def _continuation_root_signature(roots: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(roots, list):
        return ()
    signature: list[tuple[str, str]] = []
    for item in roots:
        if not isinstance(item, dict):
            return ()
        path = item.get("path")
        kind = item.get("kind")
        if not isinstance(path, str) or not isinstance(kind, str):
            return ()
        signature.append((path, kind))
    return tuple(sorted(signature))


def captured_pytest_failure_continuation(
    command: dict[str, Any],
    receipt: dict[str, Any],
    control: dict[str, Any],
    *,
    expected_commit: str,
    expected_tree: str,
    expected_plan_sha256: str,
    expected_input_manifest_sha256: str,
    expected_source_manifest_sha256: str,
    expected_wrapper_sha256: str,
    expected_plugin_sha256: str,
    expected_runtime_profile_sha256: str,
) -> dict[str, Any]:
    """Admit continuation only for a fully captured ordinary pytest test failure."""
    reasons: list[str] = []
    if command.get("command_type") != "pytest":
        reasons.append("not_a_pytest_command")
    if receipt.get("status") not in ("FAIL", "ERROR"):
        reasons.append("not_a_typed_test_failure")
    if receipt.get("pytest_result_status") != receipt.get("status"):
        reasons.append("test_failure_status_was_overridden")
    if receipt.get("command_id") != command.get("id") or receipt.get("order") != command.get("order"):
        reasons.append("command_receipt_identity_mismatch")
    if control.get("command_id") != command.get("id"):
        reasons.append("queue_control_command_identity_mismatch")
    if receipt.get("exit_code") != 1:
        reasons.append("not_pytest_test_failure_exit_code")
    if receipt.get("launch_error") is not None or receipt.get("timed_out") is not False:
        reasons.append("launch_or_timeout_status_not_admitted")
    if receipt.get("frozen_commit") != expected_commit or receipt.get("frozen_tree") != expected_tree:
        reasons.append("frozen_git_identity_mismatch")
    if receipt.get("plan_sha256") != expected_plan_sha256:
        reasons.append("plan_identity_mismatch")
    if receipt.get("input_manifest_sha256") != expected_input_manifest_sha256:
        reasons.append("input_manifest_identity_mismatch")
    if receipt.get("source_input_manifest_sha256") != expected_source_manifest_sha256.lower():
        reasons.append("source_input_manifest_identity_mismatch")

    profile = receipt.get("python_and_package_versions")
    if (
        not isinstance(profile, dict)
        or profile.get("status") != "read"
        or profile.get("prefix_matches_product_venv") is not True
    ):
        reasons.append("selected_runtime_profile_not_verified")
    else:
        try:
            if product_python_profile_sha256(profile) != expected_runtime_profile_sha256:
                reasons.append("frozen_runtime_profile_baseline_mismatch")
        except CaptureError:
            reasons.append("frozen_runtime_profile_baseline_invalid")
    if receipt.get("runtime_profile_expected_sha256") != expected_runtime_profile_sha256:
        reasons.append("runtime_profile_freeze_identity_mismatch")
    for phase in ("before", "after"):
        observed_profile = receipt.get(f"runtime_profile_{phase}")
        observed_sha256 = receipt.get(f"runtime_profile_{phase}_sha256")
        if (
            not isinstance(observed_profile, dict)
            or observed_profile.get("status") != "read"
            or observed_profile.get("prefix_matches_product_venv") is not True
            or observed_sha256 != expected_runtime_profile_sha256
            or receipt.get(f"runtime_profile_{phase}_matches_frozen") is not True
        ):
            reasons.append(f"runtime_profile_{phase}_not_frozen")
        else:
            try:
                if product_python_profile_sha256(observed_profile) != observed_sha256:
                    reasons.append(f"runtime_profile_{phase}_receipt_hash_mismatch")
            except CaptureError:
                reasons.append(f"runtime_profile_{phase}_invalid")

    expected_tools = {
        "wrapper": expected_wrapper_sha256.lower(),
        "plugin": expected_plugin_sha256.lower(),
    }
    for phase in ("source_identity_before", "source_identity_after"):
        identity = receipt.get(phase)
        if not isinstance(identity, dict) or identity.get("status") != "PASS":
            reasons.append(f"{phase}_not_pass")
            continue
        source_identity = identity.get("source")
        if not isinstance(source_identity, dict) or source_identity.get("status") != "PASS":
            reasons.append(f"{phase}_source_not_pass")
            continue
        tools = identity.get("capture_tools")
        if not isinstance(tools, dict) or (
            tools.get("status") != "PASS"
            or tools.get("matches_pinned_runtime_inputs") is not True
            or tools.get("actual_sha256") != expected_tools
        ):
            reasons.append(f"{phase}_capture_tools_not_pinned")
        raw_manifest = source_identity.get("raw_source_manifest")
        if not isinstance(raw_manifest, dict) or (
            raw_manifest.get("status") != "PASS"
            or raw_manifest.get("manifest_file_sha256")
            != expected_source_manifest_sha256.lower()
        ):
            reasons.append(f"{phase}_source_manifest_not_pinned")

    expected_roots = _continuation_root_signature(_command_output_roots(command))
    before_roots = _continuation_root_signature(
        receipt.get("declared_output_roots_absent_before")
    )
    control_roots = _continuation_root_signature(control.get("output_roots_absent_before"))
    if not expected_roots or before_roots != expected_roots or control_roots != expected_roots:
        reasons.append("output_roots_not_freshly_bound")
    before_inventory = receipt.get("command_output_inventory_before_metadata")
    if (
        not isinstance(before_inventory, dict)
        or before_inventory.get("status") != "PASS"
        or before_inventory.get("complete") is not True
        or _continuation_root_signature(before_inventory.get("bound_roots")) != expected_roots
    ):
        reasons.append("pre_receipt_output_inventory_incomplete")
    final_inventory = control.get("final_output_inventory")
    if (
        not isinstance(final_inventory, dict)
        or final_inventory.get("status") != "PASS"
        or final_inventory.get("complete") is not True
        or _continuation_root_signature(final_inventory.get("bound_roots")) != expected_roots
    ):
        reasons.append("final_output_inventory_incomplete")

    expected_output_hashes: dict[str, Any] = {}
    for output_key, receipt_key in (
        ("stdout", "stdout_sha256"), ("stderr", "stderr_sha256"), ("junit", "junit_sha256")
    ):
        output_path = command.get("outputs", {}).get(output_key)
        if not isinstance(output_path, str):
            reasons.append(f"{output_key}_output_path_missing")
            continue
        try:
            relative_path = _lexical_product_relative(Path(output_path), f"{command['id']} {output_key}")
        except (CaptureError, OSError, TypeError, ValueError):
            reasons.append(f"{output_key}_output_path_invalid")
            continue
        expected_output_hashes[relative_path] = receipt.get(receipt_key)
    for inventory_name, inventory in (
        ("pre_receipt", before_inventory), ("final", final_inventory)
    ):
        files = inventory.get("regular_files", []) if isinstance(inventory, dict) else []
        file_hashes = {
            item.get("path"): item.get("sha256")
            for item in files if isinstance(item, dict)
        } if isinstance(files, list) else {}
        for relative_path, expected_hash in expected_output_hashes.items():
            if not isinstance(expected_hash, str) or file_hashes.get(relative_path) != expected_hash:
                reasons.append(f"{inventory_name}_capture_file_hash_mismatch:{relative_path}")

    junit = receipt.get("junit")
    observed = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0}
    if not isinstance(junit, dict) or junit.get("valid") is not True:
        reasons.append("junit_not_valid")
    else:
        counts = junit.get("counts")
        cases = junit.get("testcases")
        testcase_count = junit.get("testcase_count")
        if not isinstance(counts, dict) or not isinstance(cases, list):
            reasons.append("junit_counts_or_cases_missing")
        else:
            cases_valid = True
            for case in cases:
                if not isinstance(case, dict) or case.get("status") not in observed:
                    cases_valid = False
                    continue
                observed[case["status"]] += 1
            if not cases_valid or observed != counts:
                reasons.append("junit_case_count_mismatch")
            if (
                not isinstance(testcase_count, int)
                or isinstance(testcase_count, bool)
                or testcase_count <= 0
                or testcase_count != len(cases)
                or sum(observed.values()) != testcase_count
            ):
                reasons.append("junit_testcase_denominator_invalid")
            if observed["SKIP"]:
                reasons.append("junit_contains_unclassified_skips")
            expected_failure_status = (
                "ERROR" if observed["ERROR"] else "FAIL" if observed["FAIL"] else None
            )
            if expected_failure_status != receipt.get("status"):
                reasons.append("junit_does_not_explain_command_failure")

    origin = receipt.get("module_origin_assertion")
    if not isinstance(origin, dict) or (
        origin.get("status") != "PASS" or origin.get("passed") is not True
    ):
        reasons.append("pytest_module_origin_receipt_not_pass")
    receipt_directory = command.get("environment", {}).get("POLISYOS_R4_RECEIPT_DIR")
    child_output = receipt.get("child_output_inventory")
    if receipt_directory and (
        not isinstance(child_output, dict)
        or child_output.get("status") != "PASS"
        or child_output.get("complete") is not True
    ):
        reasons.append("required_child_stream_inventory_incomplete")
    elif child_output is not None and (
        not isinstance(child_output, dict)
        or child_output.get("status") != "PASS"
        or child_output.get("complete") is not True
    ):
        reasons.append("child_stream_inventory_incomplete")

    for field in ("stdout_sha256", "stderr_sha256", "junit_sha256"):
        value = receipt.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            reasons.append(f"{field}_missing_or_invalid")

    return {
        "eligible": not reasons,
        "status": "PASS" if not reasons else "REFUSED",
        "rule": "actual ordinary pytest FAIL/ERROR status plus complete captured evidence",
        "reasons": reasons,
        "evidence": {
            "command_id": command.get("id"),
            "command_type": command.get("command_type"),
            "status": receipt.get("status"),
            "pytest_result_status": receipt.get("pytest_result_status"),
            "exit_code": receipt.get("exit_code"),
            "junit_counts": junit.get("counts") if isinstance(junit, dict) else None,
            "junit_testcase_count": junit.get("testcase_count") if isinstance(junit, dict) else None,
            "source_identity_before": receipt.get("source_identity_before", {}).get("status")
            if isinstance(receipt.get("source_identity_before"), dict) else None,
            "source_identity_after": receipt.get("source_identity_after", {}).get("status")
            if isinstance(receipt.get("source_identity_after"), dict) else None,
            "output_roots": [path for path, _kind in expected_roots],
            "pre_receipt_output_inventory": before_inventory.get("status")
            if isinstance(before_inventory, dict) else None,
            "final_output_inventory": final_inventory.get("status")
            if isinstance(final_inventory, dict) else None,
            "module_origin_assertion": origin.get("status")
            if isinstance(origin, dict) else None,
            "child_output_inventory": child_output.get("status")
            if isinstance(child_output, dict) else None,
        },
    }


def preflight_assertion(stdout_path: Path, cwd: Path) -> dict[str, Any]:
    raw = stdout_path.read_text(encoding="utf-8")
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"passed": False, "reason": f"source_readback_json_invalid:{exc}"}
    expected_root = (cwd / "src" / "polisyos").resolve()
    modules = report.get("modules", {})
    mismatch = {
        name: origin for name, origin in modules.items()
        if not Path(origin).resolve().is_relative_to(expected_root)
    }
    required = {"polisyos.common.async_tools", "polisyos.scientist.compute.runner", "polisyos.runtime.http.services.control.run_lifecycle"}
    missing = sorted(required - set(modules))
    return {
        "passed": bool(modules) and not mismatch and not missing,
        "python": report.get("python"),
        "executable": report.get("executable"),
        "module_count": len(modules),
        "mismatched_origins": mismatch,
        "missing_required_modules": missing,
    }


def source_cli_assertion(stdout_path: Path, frozen_commit: str) -> dict[str, Any]:
    """Validate the actual JSON census output and bind its reported HEAD to freeze."""
    try:
        raw = stdout_path.read_text(encoding="utf-8")
        report = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return {"passed": False, "reason": f"source_cli_json_invalid:{type(exc).__name__}:{exc}"}
    if not isinstance(report, dict):
        return {"passed": False, "reason": "source_cli_json_root_not_object"}
    git = report.get("git_enumeration", {})
    selection = report.get("selection", {})
    denominator = report.get("scanned_denominator", {})
    if not isinstance(git, dict) or not isinstance(selection, dict) or not isinstance(denominator, dict):
        return {"passed": False, "reason": "source_cli_required_sections_not_objects"}
    read_paths = denominator.get("read_paths", [])
    if not isinstance(read_paths, list):
        read_paths = []
    selected_count = denominator.get("selected_paths")
    result = report.get("result")
    criteria = {
        "schema": report.get("schema") == "polisyos.schema_fqn_census.v2",
        "complete_result": result == "complete_for_selected_local_text_inputs",
        "reported_head_matches_freeze": report.get("head") == frozen_commit,
        "git_enumeration_complete": git.get("complete_verdict") is True,
        "selected_path_count_is_integer": isinstance(selected_count, int),
        "all_selected_paths_read": isinstance(selected_count, int) and selected_count == len(read_paths),
        "no_unreadable_paths": report.get("unreadable_paths") == [],
        "no_rejected_outside_root_paths": report.get("rejected_outside_root_paths") == [],
        "selection_count_matches_denominator": selection.get("selected_path_count") == selected_count,
    }
    return {
        "passed": all(criteria.values()),
        "criteria": criteria,
        "schema": report.get("schema"),
        "result": result,
        "reported_head": report.get("head"),
        "frozen_commit": frozen_commit,
        "selected_path_count": selected_count,
        "successful_byte_read_count": len(read_paths) if isinstance(read_paths, list) else None,
        "git_enumeration_complete": git.get("complete_verdict"),
        "criterion_verdict": report.get("interpretation_boundary", {}).get("criterion_verdict"),
        "stdout_sha256": sha256_file(stdout_path),
    }


def run_one(
    command: dict[str, Any],
    scratch: dict[str, Path],
    *,
    run_dir: Path,
    plan: dict[str, Any],
    plan_path: Path,
    frozen_commit: str,
    frozen_tree: str,
    plan_sha: str,
    input_manifest_sha: str,
    source_manifest_path: Path,
    source_manifest_sha256: str,
    versions: dict[str, Any],
    expected_wrapper_sha256: str,
    expected_plugin_sha256: str,
    expected_runtime_profile_sha256: str,
) -> dict[str, Any]:
    output_roots_before = assert_command_output_roots_absent(command)
    identity_before = inspect_live_identity(
        frozen_commit, frozen_tree, plan_path, plan_sha,
        expected_wrapper_sha256, expected_plugin_sha256,
        source_manifest_path, source_manifest_sha256,
    )
    runtime_profile_before: dict[str, Any] | None = None
    runtime_profile_before_sha256: str | None = None
    runtime_profile_before_error: str | None = None
    try:
        runtime_profile_before = read_product_python_profile(command, plan)
        runtime_profile_before_sha256 = product_python_profile_sha256(runtime_profile_before)
    except (CaptureError, OSError, TypeError, ValueError) as exc:
        runtime_profile_before_error = f"{type(exc).__name__}: {exc}"
    runtime_profile_before_matches = (
        runtime_profile_before_sha256 == expected_runtime_profile_sha256
    )
    preflight_status = (
        "FROZEN_SOURCE_IDENTITY_FAIL"
        if identity_before["status"] != "PASS"
        else "FROZEN_RUNTIME_PROFILE_FAIL"
        if not runtime_profile_before_matches
        else None
    )
    if preflight_status is not None:
        failure = {
            "schema": "policyos.composed_mac_command_receipt.v2",
            "status": preflight_status,
            "command_id": command["id"], "order": command["order"],
            "frozen_commit": frozen_commit, "frozen_tree": frozen_tree,
            "source_input_manifest_sha256": source_manifest_sha256,
            "source_identity_before": identity_before,
            "runtime_profile_expected_sha256": expected_runtime_profile_sha256,
            "runtime_profile_before": runtime_profile_before,
            "runtime_profile_before_sha256": runtime_profile_before_sha256,
            "runtime_profile_before_matches_frozen": runtime_profile_before_matches,
            "runtime_profile_before_error": runtime_profile_before_error,
            "declared_output_roots_absent_before": output_roots_before,
            "stdout_path": command["outputs"].get("stdout"),
            "stderr_path": command["outputs"].get("stderr"),
            "junit_path": command["outputs"].get("junit"),
            "command_started": False,
        }
        metadata_path = Path(command["outputs"]["metadata"])
        failure["metadata_path"] = str(metadata_path)
        write_json_once(metadata_path, failure)
        failure["metadata_sha256"] = sha256_file(metadata_path)
        append_jsonl(run_dir / "events.jsonl", {
            "event": "command_preflight_failed", "at_utc": utc_now(),
            "command_id": command["id"], "status": failure["status"],
            "source_identity_before": identity_before,
            "runtime_profile_before_sha256": runtime_profile_before_sha256,
            "runtime_profile_before_matches_frozen": runtime_profile_before_matches,
            "metadata_path": failure["metadata_path"],
            "metadata_sha256": failure["metadata_sha256"],
        })
        append_jsonl(history_path(plan), {
            "event": "command_preflight_failed", "at_utc": utc_now(),
            "command_id": command["id"], "status": failure["status"],
            "frozen_commit": frozen_commit, "frozen_tree": frozen_tree,
            "plan_sha256": plan_sha, "source_input_manifest_sha256": source_manifest_sha256,
            "run_id": run_dir.name,
        })
        return failure

    outputs = command["outputs"]
    output_dir = Path(outputs["directory"])
    output_dir.mkdir(parents=True, exist_ok=False)
    for key in ("stdout", "stderr", "metadata"):
        if Path(outputs[key]).exists():
            raise CaptureError(f"refusing to overwrite {outputs[key]}")
    for key in ("POLISYOS_CACHE_HOME", "POLISYOS_R4_RECEIPT_DIR"):
        value = command["environment"].get(key)
        if value:
            Path(value).mkdir(parents=True, exist_ok=False)
    origin_base = output_dir / "module-origins.json"
    actual, inserted = actual_argv(command, scratch, source_manifest_path, source_manifest_sha256)
    environment = os.environ.copy()
    planned_environment = {str(k): str(v) for k, v in command["environment"].items()}
    environment.update(planned_environment)
    runner_environment: dict[str, str] = {}
    if command["command_type"] == "pytest":
        old_pythonpath = environment.get("PYTHONPATH", "")
        effective_pythonpath = os.pathsep.join(value for value in (str(LOCAL_RAW), old_pythonpath) if value)
        environment["PYTHONPATH"] = effective_pythonpath
        environment["POLISYOS_CAPTURE_ORIGIN_FILE"] = str(origin_base)
        environment["POLISYOS_CAPTURE_PRODUCT_ROOT"] = str(PRODUCT_ROOT)
        existing_plugins = [value.strip() for value in environment.get("PYTEST_PLUGINS", "").split(",") if value.strip()]
        if "composed_mac_pytest_origin_plugin" not in existing_plugins:
            existing_plugins.append("composed_mac_pytest_origin_plugin")
        environment["PYTEST_PLUGINS"] = ",".join(existing_plugins)
        runner_environment = {
            "PYTHONPATH": effective_pythonpath,
            "POLISYOS_CAPTURE_ORIGIN_FILE": str(origin_base),
            "POLISYOS_CAPTURE_PRODUCT_ROOT": str(PRODUCT_ROOT),
            "PYTEST_PLUGINS": environment["PYTEST_PLUGINS"],
        }
    append_jsonl(run_dir / "events.jsonl", {
        "event": "command_started", "at_utc": utc_now(), "command_id": command["id"],
        "order": command["order"], "source_identity": identity_before["source"],
        "capture_tool_identity": identity_before["capture_tools"],
    })
    append_jsonl(history_path(plan), {
        "event": "command_started", "at_utc": utc_now(), "command_id": command["id"],
        "order": command["order"], "frozen_commit": frozen_commit, "frozen_tree": frozen_tree,
        "plan_sha256": plan_sha, "source_input_manifest_sha256": source_manifest_sha256,
        "run_id": run_dir.name,
        "wrapper_sha256": identity_before["capture_tools"]["actual_sha256"]["wrapper"],
        "pytest_origin_plugin_sha256": identity_before["capture_tools"]["actual_sha256"]["plugin"],
    })
    launch_error: str | None = None
    process_pid: int | None = None
    try:
        rc, elapsed, start_utc, end_utc, max_rss, process_pid = capture_process(
            actual, Path(command["cwd"]), environment, Path(outputs["stdout"]), Path(outputs["stderr"])
        )
    except OSError as exc:
        rc = 127
        elapsed = 0.0
        start_utc = end_utc = utc_now()
        max_rss = None
        launch_error = f"{type(exc).__name__}: {exc}"
    child_output = None
    receipt_dir_value = command["environment"].get("POLISYOS_R4_RECEIPT_DIR")
    if receipt_dir_value:
        child_output = inventory_child_output_directory(Path(receipt_dir_value), R4_EXPECTED_CHILD_STREAMS)
    command_output_inventory = inventory_command_outputs(command)
    junit = parse_junit(Path(outputs["junit"])) if outputs.get("junit") else None
    origin = check_module_origin_receipts(output_dir, process_pid) if command["command_type"] == "pytest" else None
    source_readback = preflight_assertion(Path(outputs["stdout"]), Path(command["cwd"])) if command["id"] == "SOURCE_MODULE_READBACK" and rc == 0 else None
    cli_readback = source_cli_assertion(Path(outputs["stdout"]), frozen_commit) if command["command_type"] == "source_cli_readback" else None
    status = classify(command, rc, junit, origin)
    if launch_error is not None:
        status = "HARNESS_LAUNCH_ERROR"
    elif command["command_type"] == "source_cli_readback" and rc == 0:
        status = "SOURCE_CLI_PASS" if cli_readback and cli_readback.get("passed") else "SOURCE_CLI_ASSERTION_FAIL"
    pytest_result_status = status if command["command_type"] == "pytest" else None
    identity_after = inspect_live_identity(
        frozen_commit, frozen_tree, plan_path, plan_sha,
        expected_wrapper_sha256, expected_plugin_sha256,
        source_manifest_path, source_manifest_sha256,
    )
    runtime_profile_after: dict[str, Any] | None = None
    runtime_profile_after_sha256: str | None = None
    runtime_profile_after_error: str | None = None
    try:
        runtime_profile_after = read_product_python_profile(command, plan)
        runtime_profile_after_sha256 = product_python_profile_sha256(runtime_profile_after)
    except (CaptureError, OSError, TypeError, ValueError) as exc:
        runtime_profile_after_error = f"{type(exc).__name__}: {exc}"
    runtime_profile_after_matches = (
        runtime_profile_after_sha256 == expected_runtime_profile_sha256
    )
    if identity_after["status"] != "PASS":
        status = "FROZEN_SOURCE_IDENTITY_DRIFT"
    elif not runtime_profile_after_matches:
        status = "FROZEN_RUNTIME_PROFILE_DRIFT"
    elif not command_output_inventory["complete"] and status in ("PASS", "PREFLIGHT_PASS", "SOURCE_CLI_PASS"):
        status = "COMMAND_OUTPUT_INVENTORY_INCOMPLETE"
    elif child_output is not None and not child_output["complete"] and status == "PASS":
        status = "CHILD_OUTPUT_INCOMPLETE"
    if command["id"] == "SOURCE_MODULE_READBACK" and status == "PREFLIGHT_PASS":
        status = "PREFLIGHT_PASS" if source_readback and source_readback.get("passed") else "PREFLIGHT_ORIGIN_FAIL"
    metadata: dict[str, Any] = {
        "schema": "policyos.composed_mac_command_receipt.v2",
        "status": status,
        "pytest_result_status": pytest_result_status,
        "command_id": command["id"],
        "order": command["order"],
        "phase": command["phase"],
        "planned_argv": command["argv"],
        "actual_argv": actual,
        "harness_added_argv": inserted,
        "cwd": str(Path(command["cwd"]).resolve()),
        "planned_environment_overrides": redact_mapping(planned_environment),
        "capture_environment_overrides": redact_mapping(runner_environment),
        "effective_environment_nonsecret": redact_mapping(environment),
        "frozen_commit": frozen_commit,
        "frozen_tree": frozen_tree,
        "plan_sha256": plan_sha,
        "input_manifest_sha256": input_manifest_sha,
        "source_input_manifest_path": str(source_manifest_path),
        "source_input_manifest_sha256": source_manifest_sha256,
        "source_identity_before": identity_before,
        "declared_output_roots_absent_before": output_roots_before,
        "source_identity_after": identity_after,
        "command_output_inventory_before_metadata": command_output_inventory,
        "capture_tool_identity": identity_after["capture_tools"],
        "wrapper_sha256": identity_after["capture_tools"].get("actual_sha256", {}).get("wrapper"),
        "pytest_origin_plugin_sha256": identity_after["capture_tools"].get("actual_sha256", {}).get("plugin"),
        "python_and_package_versions": versions,
        "runtime_profile_expected_sha256": expected_runtime_profile_sha256,
        "runtime_profile_before": runtime_profile_before,
        "runtime_profile_before_sha256": runtime_profile_before_sha256,
        "runtime_profile_before_matches_frozen": runtime_profile_before_matches,
        "runtime_profile_before_error": runtime_profile_before_error,
        "runtime_profile_after": runtime_profile_after,
        "runtime_profile_after_sha256": runtime_profile_after_sha256,
        "runtime_profile_after_matches_frozen": runtime_profile_after_matches,
        "runtime_profile_after_error": runtime_profile_after_error,
        "platform": platform.platform(),
        "start_utc": start_utc,
        "end_utc": end_utc,
        "monotonic_elapsed_seconds": elapsed,
        "exit_code": rc,
        "timed_out": False,
        "launch_error": launch_error,
        "max_sampled_process_rss_kb": max_rss,
        "stdout_sha256": sha256_file(Path(outputs["stdout"])),
        "stderr_sha256": sha256_file(Path(outputs["stderr"])),
        "junit_path": outputs.get("junit"),
        "junit_sha256": sha256_file(Path(outputs["junit"])) if outputs.get("junit") and Path(outputs["junit"]).is_file() else None,
        "junit": junit,
        "skip_disposition": (
            {
                "status": "UNCLASSIFIED_SKIP",
                "requiredness": "unknown_without_explicit_route_policy",
                "review_required": True,
                "case_record_location": "junit.testcases",
            }
            if junit is not None and junit.get("counts", {}).get("SKIP", 0)
            else None
        ),
        "child_output_inventory": child_output,
        "module_origin_receipt_glob": str(output_dir / "module-origins-<pid>.json") if command["command_type"] == "pytest" else None,
        "module_origin_assertion": origin,
        "source_readback_assertion": source_readback,
        "source_cli_assertion": cli_readback,
        "prior_wall_time_context": command.get("prior_wall_time"),
        "supplement_source_command": command.get("_supplement_source_command"),
        "purpose": command["purpose"],
    }
    write_json_once(Path(outputs["metadata"]), metadata)
    final_output_inventory = inventory_command_outputs(command)
    append_jsonl(run_dir / "events.jsonl", {
        "event": "command_output_inventory", "at_utc": utc_now(),
        "command_id": command["id"], "plan_sha256": plan_sha,
        "source_input_manifest_sha256": source_manifest_sha256,
        "status": final_output_inventory["status"],
        "inventory": final_output_inventory,
    })
    event = {
        "event": "command_completed", "at_utc": utc_now(), "command_id": command["id"],
        "order": command["order"], "status": status, "exit_code": rc,
        "monotonic_elapsed_seconds": elapsed, "frozen_commit": frozen_commit,
        "frozen_tree": frozen_tree, "plan_sha256": plan_sha, "run_id": run_dir.name,
        "source_input_manifest_sha256": source_manifest_sha256,
        "metadata_path": outputs["metadata"], "metadata_sha256": sha256_file(Path(outputs["metadata"])),
        "command_output_inventory_status": final_output_inventory["status"],
        "command_output_inventory_regular_file_count": final_output_inventory["regular_file_count"],
        "command_output_inventory_symlink_count": final_output_inventory["symlink_count"],
        "wrapper_sha256": identity_after["capture_tools"].get("actual_sha256", {}).get("wrapper"),
        "pytest_origin_plugin_sha256": identity_after["capture_tools"].get("actual_sha256", {}).get("plugin"),
        "source_identity_status_before": identity_before["status"],
        "source_identity_status_after": identity_after["status"],
        "child_output_status": child_output["status"] if child_output is not None else None,
    }
    append_jsonl(run_dir / "events.jsonl", event)
    append_jsonl(history_path(plan), event)
    print(f"[{status}] {command['id']} exit={rc} elapsed={elapsed:.2f}s; receipt={outputs['metadata']}", flush=True)
    metadata["_queue_control"] = {
        "command_id": command["id"],
        "output_roots_absent_before": output_roots_before,
        "final_output_inventory": final_output_inventory,
    }
    return metadata


def _self_test_static_arguments(
    runtime_arguments: list[str], source_input_manifest_path: Path,
    expected_source_input_manifest_sha256: str,
) -> list[str]:
    """Remove only the dynamic, root-pinned source-manifest context from argv."""
    context_values: dict[str, str | None] = {
        "--source-input-manifest": None,
        "--frozen-source-input-manifest-sha256": None,
    }
    static_arguments: list[str] = []
    index = 0
    while index < len(runtime_arguments):
        argument = runtime_arguments[index]
        matched = False
        for option in context_values:
            if argument == option:
                if context_values[option] is not None or index + 1 >= len(runtime_arguments):
                    raise CaptureError(f"self-test requires one value for {option}")
                value = runtime_arguments[index + 1]
                if not value or value.startswith("--"):
                    raise CaptureError(f"self-test requires one value for {option}")
                context_values[option] = value
                index += 2
                matched = True
                break
            if argument.startswith(f"{option}="):
                if context_values[option] is not None:
                    raise CaptureError(f"self-test repeats {option}")
                value = argument.partition("=")[2]
                if not value:
                    raise CaptureError(f"self-test requires one value for {option}")
                context_values[option] = value
                index += 1
                matched = True
                break
        if not matched:
            static_arguments.append(argument)
            index += 1
    if any(value is None for value in context_values.values()):
        raise CaptureError("self-test invocation is missing its root-pinned source-manifest context")
    supplied_manifest = Path(context_values["--source-input-manifest"] or "")
    if not supplied_manifest.is_absolute():
        supplied_manifest = PRODUCT_ROOT / supplied_manifest
    supplied_manifest = Path(os.path.abspath(supplied_manifest))
    if supplied_manifest != Path(os.path.abspath(source_input_manifest_path)):
        raise CaptureError("self-test argv source-manifest path differs from the parsed argument")
    supplied_sha256 = context_values["--frozen-source-input-manifest-sha256"] or ""
    if supplied_sha256.lower() != expected_source_input_manifest_sha256.lower():
        raise CaptureError("self-test argv source-manifest hash differs from the parsed argument")
    return static_arguments


def _self_test_output_directory_from_plan(
    prepared_source_binding: dict[str, Any], output_directory: Path,
    runtime_arguments: list[str], source_input_manifest_path: Path,
    expected_source_input_manifest_sha256: str,
) -> Path:
    """Resolve exactly one planned Python self-test and its owned output child."""
    static_arguments = _self_test_static_arguments(
        runtime_arguments, source_input_manifest_path,
        expected_source_input_manifest_sha256,
    )
    if not output_directory.is_absolute():
        raise CaptureError("self-test output directory must be absolute")
    output_directory = Path(os.path.abspath(output_directory))
    output_relative = _lexical_product_relative(output_directory, "self-test output directory")
    if output_directory.exists() or output_directory.is_symlink():
        raise CaptureError("self-test output directory must not exist before the command")

    matches: list[tuple[Path, dict[str, Any]]] = []
    for expected_binding in prepared_source_binding["plan_output_bindings"]:
        plan_path = PRODUCT_ROOT / expected_binding["plan_path"]
        plan = load_and_validate_plan(plan_path)
        actual_binding = _plan_output_binding(plan_path, plan)
        if actual_binding != expected_binding:
            raise CaptureError(f"self-test plan binding changed: {expected_binding['plan_path']}")
        for command in plan["execution"]["commands"]:
            if command.get("command_type") != "python":
                continue
            argv = command.get("argv")
            if not isinstance(argv, list) or len(argv) < 3 or not all(isinstance(value, str) for value in argv):
                continue
            cwd = Path(command.get("cwd", plan["execution"]["cwd"]))
            if not cwd.is_absolute() or cwd.resolve() != PRODUCT_ROOT.resolve():
                continue
            executable = Path(argv[0])
            if not executable.is_absolute():
                executable = cwd / executable
            script = Path(argv[1])
            if not script.is_absolute():
                script = cwd / script
            try:
                is_capture_command = (
                    executable.resolve(strict=True) == Path(sys.executable).resolve(strict=True)
                    and script.resolve(strict=True) == Path(__file__).resolve(strict=True)
                )
            except OSError:
                is_capture_command = False
            if not is_capture_command or argv[2:] != static_arguments:
                continue
            runtime_context = plan.get("source_scope", {}).get("runtime_context", {})
            declared_manifest = runtime_context.get("source_input_manifest_path")
            if not isinstance(declared_manifest, str) or not declared_manifest:
                raise CaptureError("self-test owner plan has no source-manifest runtime path")
            declared_path = Path(declared_manifest)
            if not declared_path.is_absolute():
                declared_path = PRODUCT_ROOT / declared_path
            declared_relative = _lexical_product_relative(declared_path, "self-test plan source manifest")
            supplied_relative = _lexical_product_relative(source_input_manifest_path, "self-test source manifest")
            if declared_relative != supplied_relative:
                raise CaptureError("self-test source-manifest path differs from the matched owner plan")
            planned_output_args = [
                argv[index + 1]
                for index, argument in enumerate(argv[2:], start=2)
                if argument == "--self-test-output-directory" and index + 1 < len(argv)
            ]
            if (
                argv[2:].count("--self-test") != 1
                or len(planned_output_args) != 1
                or planned_output_args[0] != str(output_directory)
            ):
                raise CaptureError("planned Python command is not the exact self-test invocation")
            output = command["outputs"]
            command_directory = Path(output["directory"])
            if not command_directory.is_absolute():
                raise CaptureError("planned self-test command output directory must be absolute")
            command_relative = _lexical_product_relative(
                command_directory, "planned self-test command output directory",
            )
            command_owner = next(
                (
                    item for item in expected_binding["commands"]
                    if item["id"] == command["id"]
                ),
                None,
            )
            if command_owner is None or not any(
                root["path"] == command_relative
                and root["kind"] == "directory"
                and "command_output_directory" in root["roles"]
                for root in command_owner["roots"]
            ):
                raise CaptureError("self-test command has no matching plan-owned output directory")
            if output_relative == command_relative or not _path_below(output_relative, command_relative):
                raise CaptureError("self-test artifacts must be a strict child of their command output directory")
            if not _output_root_contains(output_relative, prepared_source_binding["declared_output_roots"]):
                raise CaptureError("self-test artifact directory is outside the verified output-root set")
            matches.append((command_directory, command))
    if len(matches) != 1:
        raise CaptureError(
            "self-test argv must match exactly one source-manifest-bound Python command; "
            f"matched {len(matches)}"
        )
    command_directory = matches[0][0]
    _assert_no_symlink_components(command_directory, "planned self-test command output directory")
    if command_directory.is_symlink() or not command_directory.is_dir():
        raise CaptureError("planned self-test command output directory must already be a real directory")
    _assert_no_symlink_components(output_directory, "self-test output directory")
    return output_directory


def self_test(
    source_input_manifest_path: Path, expected_source_input_manifest_sha256: str,
    output_directory: Path, runtime_arguments: list[str],
) -> int:
    """Exercise capture helpers inside this command's verified plan-owned output."""
    _lexical_product_relative(source_input_manifest_path, "self-test source manifest")
    _assert_no_symlink_components(source_input_manifest_path, "self-test source manifest")
    source_manifest_relative = _lexical_product_relative(
        source_input_manifest_path, "self-test source manifest",
    )
    if not _path_below(source_manifest_relative, RAW_IMPORT_ROOT_REL):
        raise CaptureError("self-test source manifest must remain below LOCAL/raw")
    prepared_source_binding = verify_raw_source_manifest(
        source_input_manifest_path, expected_source_input_manifest_sha256,
    )
    if prepared_source_binding["status"] != "PASS":
        raise CaptureError(
            "self-test requires a verified root-pinned source manifest: "
            f"{prepared_source_binding.get('reason')}"
        )
    root = _self_test_output_directory_from_plan(
        prepared_source_binding, output_directory, runtime_arguments,
        source_input_manifest_path, expected_source_input_manifest_sha256,
    )
    root.mkdir(parents=False, exist_ok=False)
    out = root / "stdout.bin"
    err = root / "stderr.bin"
    rc, elapsed, start, end, rss, _pid = capture_process(
        [sys.executable, "-c", "import sys; print('capture-out'); print('capture-err', file=sys.stderr)"],
        Path.cwd(), os.environ.copy(), out, err,
    )
    assert rc == 0 and out.read_bytes() == b"capture-out\n" and err.read_bytes() == b"capture-err\n"
    junit_path = root / "sample-junit.xml"
    junit_path.write_text(
        '<testsuite><testcase classname="a" name="ok"/><testcase classname="b" name="skip"><skipped message="fixture"/></testcase></testsuite>',
        encoding="utf-8",
    )
    parsed = parse_junit(junit_path)
    assert parsed["counts"] == {"PASS": 1, "FAIL": 0, "ERROR": 0, "SKIP": 1}
    assert parsed["testcases"][1]["status"] == "SKIP"
    assert parsed["testcases"][1]["message"] == "fixture"
    skipped_status = classify(
        {"command_type": "pytest"}, 0, parsed, {"passed": True}
    )
    assert skipped_status == "UNCLASSIFIED_SKIP"
    assert classify({"command_type": "pytest"}, 137, parsed, {"passed": True}) == "EXIT_NONZERO"
    assert "OOM" not in classify({"command_type": "pytest"}, 137, parsed, {"passed": True})
    identity_good = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=[REPORT_ROOT_RELS[0] + "review.md", "LOCAL/review.json"], ignored_source_paths=[],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
    )
    assert identity_good["status"] == "PASS"
    assert identity_good["allowlisted_untracked_report_path_count"] == 2
    identity_source_drift = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=1, staged_diff_status=0,
        untracked_paths=[REPORT_ROOT_RELS[0] + "review.md"], ignored_source_paths=[],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
    )
    assert identity_source_drift["status"] == "FAIL"
    assert "TRACKED_WORKTREE_DIFF" in identity_source_drift["reasons"]
    identity_untracked_source = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=["src/polisyos/untracked.py"], ignored_source_paths=[],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
    )
    assert identity_untracked_source["status"] == "FAIL"
    assert "UNTRACKED_PATHS_OUTSIDE_REPORT_ROOT" in identity_untracked_source["reasons"]
    identity_ignored_source = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=[], ignored_source_paths=["src/polisyos/ignored_candidate.py"],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
    )
    assert identity_ignored_source["status"] == "FAIL"
    assert "IGNORED_UNTRACKED_SOURCE_PATHS_OUTSIDE_REPORT_ROOT" in identity_ignored_source["reasons"]
    local_raw_source = f"{RAW_IMPORT_ROOT_REL}/untracked_exec.py"
    identity_local_raw_source_escape = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=[local_raw_source], ignored_source_paths=[local_raw_source],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
        raw_source_paths=[local_raw_source], expected_raw_source_paths=[],
        raw_source_hashes={local_raw_source: "c" * 64}, expected_raw_source_hashes={},
        actual_source_manifest_sha256="b" * 64, expected_source_manifest_sha256="b" * 64,
    )
    assert identity_local_raw_source_escape["status"] == "FAIL"
    assert "RAW_IMPORT_SOURCE_MANIFEST_MISMATCH" in identity_local_raw_source_escape["reasons"]
    identity_local_raw_source_pinned = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=[local_raw_source], ignored_source_paths=[local_raw_source],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
        raw_source_paths=[local_raw_source], expected_raw_source_paths=[local_raw_source],
        raw_source_hashes={local_raw_source: "c" * 64}, expected_raw_source_hashes={local_raw_source: "c" * 64},
        actual_source_manifest_sha256="b" * 64, expected_source_manifest_sha256="b" * 64,
    )
    assert identity_local_raw_source_pinned["status"] == "PASS"
    outside_raw_source_paths = ["LOCAL/research/untracked_exec.py", "LOCAL/research/untracked_runtime.toml"]
    identity_local_source_escape = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=outside_raw_source_paths, ignored_source_paths=[outside_raw_source_paths[1]],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
        actual_source_manifest_sha256="b" * 64, expected_source_manifest_sha256="b" * 64,
    )
    assert identity_local_source_escape["status"] == "FAIL"
    assert "UNMANIFESTED_LOCAL_EXECUTABLE_OR_CONFIG_PATHS" in identity_local_source_escape["reasons"]
    identity_local_source_pinned = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=outside_raw_source_paths, ignored_source_paths=[outside_raw_source_paths[1]],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
        local_source_paths=outside_raw_source_paths,
        expected_local_source_paths=outside_raw_source_paths,
        local_source_hashes={path: "d" * 64 for path in outside_raw_source_paths},
        expected_local_source_hashes={path: "d" * 64 for path in outside_raw_source_paths},
        manifested_local_source_paths=outside_raw_source_paths,
        actual_source_manifest_sha256="b" * 64, expected_source_manifest_sha256="b" * 64,
    )
    assert identity_local_source_pinned["status"] == "PASS"
    raw_probe = root / "untracked-import-probe.py"
    raw_probe.write_text("SYNTHETIC_RAW_IMPORT_PROBE = True\n", encoding="utf-8")
    raw_probe_rel = _relative_product_path(raw_probe)
    raw_scan = discover_raw_source_inputs([])
    raw_scanned_hashes = {entry["path"]: entry["sha256"] for entry in raw_scan["files"]}
    raw_scanned_paths = sorted(raw_scanned_hashes)
    assert raw_probe_rel in raw_scanned_hashes
    assert set(raw_scan["excluded_roots"]) == set(RAW_C12_EXCLUDED_ROOTS)
    unbounded_local_scan = discover_local_source_inputs([])
    unbounded_local_paths = {entry["path"] for entry in unbounded_local_scan["files"]}
    assert raw_probe_rel in unbounded_local_paths
    local_scan = discover_local_source_inputs([], prepared_source_binding["declared_output_roots"])
    assert local_scan["issues"] == []
    bounded_local_paths = {entry["path"] for entry in local_scan["files"]}
    assert raw_probe_rel not in bounded_local_paths
    assert local_scan["named_package_tree_exclusion"]["resolved_target"] == RAW_DASHBOARD_NODE_MODULES_TARGET_REL
    assert local_scan["named_package_tree_exclusion"]["package_identity"]["tracked_lock_and_manifest_inputs"]
    assert {LOCAL_BROWSER_CORE_ENV_REL, *RAW_C12_EXCLUDED_ROOTS} <= set(local_scan["excluded_roots"])
    assert local_scan["symlink_aliases"]
    assert not any(_path_below(path, excluded) for path in raw_scanned_paths for excluded in RAW_C12_EXCLUDED_ROOTS)
    raw_old_expected_paths = [path for path in raw_scanned_paths if path != raw_probe_rel]
    raw_old_expected_hashes = {path: raw_scanned_hashes[path] for path in raw_old_expected_paths}
    actual_untracked_local_raw = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=[raw_probe_rel], ignored_source_paths=[raw_probe_rel],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
        raw_source_paths=raw_scanned_paths, expected_raw_source_paths=raw_old_expected_paths,
        raw_source_hashes=raw_scanned_hashes, expected_raw_source_hashes=raw_old_expected_hashes,
        actual_source_manifest_sha256="b" * 64, expected_source_manifest_sha256="b" * 64,
    )
    assert actual_untracked_local_raw["status"] == "FAIL"
    assert "RAW_IMPORT_SOURCE_MANIFEST_MISMATCH" in actual_untracked_local_raw["reasons"]
    actual_manifested_local_raw = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=[raw_probe_rel], ignored_source_paths=[raw_probe_rel],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
        raw_source_paths=raw_scanned_paths, expected_raw_source_paths=raw_scanned_paths,
        raw_source_hashes=raw_scanned_hashes, expected_raw_source_hashes=raw_scanned_hashes,
        actual_source_manifest_sha256="b" * 64, expected_source_manifest_sha256="b" * 64,
    )
    assert actual_manifested_local_raw["status"] == "PASS"
    c12_environment = _c12_environment_binding()
    browser_core_environment = _browser_core_environment_binding()
    c12_assets = _hf_model_asset_inventory()
    assert c12_environment["runtime"]["distribution_count"] > 0
    assert c12_environment["runtime"]["distribution_inventory_sha256"]
    assert c12_environment["runtime"]["executable"] == c12_environment["entrypoint"]
    assert browser_core_environment["runtime"]["distribution_count"] > 0
    assert browser_core_environment["runtime"]["distribution_inventory_sha256"]
    assert browser_core_environment["uv"]["version"].split()[:2] == ["uv", "0.10.6"]
    assert c12_assets["issues"] == [] and c12_assets["files"]
    assert any(item.get("kind") == "snapshot_symlink" for item in c12_assets["files"])
    source_plan_path = PRODUCT_ROOT / (
        "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/"
        "composed-mac-current-source-replay-plan-20261010.json"
    )
    source_plan = load_and_validate_plan(source_plan_path)
    manifest_probe = root / "manifest-contract-probe"
    manifest_probe.mkdir()
    asset_manifest_path = manifest_probe / "model-assets.json"
    asset_manifest = {
        "schema": "policyos.composed_mac_separate_model_asset_inputs.v1",
        "status": "asset_inventory_prepared_not_execution_receipt",
        "model_id": "intfloat/multilingual-e5-large",
        "cache_root": RAW_C12_HF_CACHE_REL,
        "content_identity_boundary": "HF blob names are recorded as upstream cache identifiers; large blob bytes are not rehashed by the source gate.",
        **c12_assets,
    }
    write_json_once(asset_manifest_path, asset_manifest)
    complete_manifest = create_raw_source_manifest(
        source_plan_path, source_plan,
        additional_plan_paths=[
            PRODUCT_ROOT / binding["plan_path"]
            for binding in prepared_source_binding["plan_output_bindings"]
            if binding["plan_path"] != _relative_product_path(source_plan_path)
        ],
        model_asset_manifest_path=asset_manifest_path,
    )
    complete_manifest_path = manifest_probe / "source-inputs.json"
    write_json_once(complete_manifest_path, complete_manifest)
    complete_manifest_check = verify_raw_source_manifest(
        complete_manifest_path, sha256_file(complete_manifest_path),
    )
    assert complete_manifest_check["status"] == "PASS"
    assert complete_manifest_check["local_source_path_count"] == complete_manifest["path_count"]
    assert complete_manifest_check["raw_import_source_set_and_bytes_match"] is True
    synthetic_output_dir = root / "synthetic-command-output"
    synthetic_basetemp = synthetic_output_dir / "pytest-tmp"
    synthetic_command = {
        "id": "SYNTHETIC_OUTPUT_ROOT_BOUNDARY",
        "command_type": "pytest",
        "argv": [sys.executable, "-m", "pytest", f"--basetemp={synthetic_basetemp}"],
        "environment": {},
        "outputs": {
            "directory": str(synthetic_output_dir),
            "stdout": str(synthetic_output_dir / "stdout.bin"),
            "stderr": str(synthetic_output_dir / "stderr.bin"),
            "metadata": str(synthetic_output_dir / "metadata.json"),
            "junit": None,
        },
    }
    synthetic_roots = _command_output_roots(synthetic_command)
    self_test_scan_roots = [
        *prepared_source_binding["declared_output_roots"],
        *synthetic_roots,
    ]
    before_output_sources = discover_local_source_inputs([], self_test_scan_roots)
    assert_command_output_roots_absent(synthetic_command)
    synthetic_output_dir.mkdir()
    synthetic_basetemp.mkdir()
    Path(synthetic_command["outputs"]["stdout"]).write_bytes(b"stdout\n")
    Path(synthetic_command["outputs"]["stderr"]).write_bytes(b"stderr\n")
    generated_work = synthetic_basetemp / "pytest-of-harness"
    census_root = generated_work / "repo"
    (census_root / "configs").mkdir(parents=True)
    linked_target = generated_work / "dfk_external_schema_fqn.json"
    linked_target.write_text('{"generated": true}\n', encoding="utf-8")
    linked_data = census_root / "configs" / "linked.json"
    linked_data.symlink_to(linked_target)
    internal_target = synthetic_output_dir / "regular-payload.bin"
    internal_target.write_bytes(b"captured regular output payload")
    after_output_sources = discover_local_source_inputs([], self_test_scan_roots)
    assert after_output_sources["issues"] == []
    assert [entry["path"] for entry in after_output_sources["files"]] == [
        entry["path"] for entry in before_output_sources["files"]
    ]
    assert after_output_sources["symlink_aliases"] == before_output_sources["symlink_aliases"]
    synthetic_inventory = inventory_command_outputs(synthetic_command)
    assert synthetic_inventory["complete"] is True
    linked_record = next(
        (
            item for item in synthetic_inventory["symlinks"]
            if item["path"].endswith("/pytest-tmp/pytest-of-harness/repo/configs/linked.json")
        ),
        None,
    )
    assert linked_record is not None
    assert linked_record["lexical_target_product_path"] == _relative_product_path(linked_target)
    assert any(
        item["path"] == _relative_product_path(internal_target)
        for item in synthetic_inventory["regular_files"]
    )
    assert any(
        item["path"] == _relative_product_path(linked_target)
        for item in synthetic_inventory["regular_files"]
    )
    precreated_source_dir = root / "precreated-source-output"
    precreated_source_dir.mkdir()
    (precreated_source_dir / "injected.py").write_text("INJECTED_SOURCE = True\n", encoding="utf-8")
    precreated_command = {
        **synthetic_command,
        "id": "SYNTHETIC_PRECREATED_SOURCE_REFUSAL",
        "argv": [
            sys.executable, "-m", "pytest",
            f"--basetemp={precreated_source_dir / 'pytest-tmp'}",
        ],
        "outputs": {
            **synthetic_command["outputs"],
            "directory": str(precreated_source_dir),
            "stdout": str(precreated_source_dir / "stdout.bin"),
            "stderr": str(precreated_source_dir / "stderr.bin"),
            "metadata": str(precreated_source_dir / "metadata.json"),
        },
    }
    try:
        assert_command_output_roots_absent(precreated_command)
    except CaptureError as exc:
        precreated_output_refusal = str(exc)
    else:
        raise AssertionError("precreated source under a plan-derived output root was not refused")
    assert "present at per-command preflight" in precreated_output_refusal
    output_source_identity = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=[f"{_relative_product_path(synthetic_output_dir)}/generated.py"],
        ignored_source_paths=[], actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
        declared_output_roots=synthetic_roots,
    )
    assert output_source_identity["status"] == "PASS"
    source_elsewhere_identity = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=["LOCAL/research/untracked_exec.py"], ignored_source_paths=[],
        actual_plan_sha256="a" * 64, expected_plan_sha256="a" * 64,
        declared_output_roots=synthetic_roots,
    )
    assert source_elsewhere_identity["status"] == "FAIL"
    assert "UNMANIFESTED_LOCAL_EXECUTABLE_OR_CONFIG_PATHS" in source_elsewhere_identity["reasons"]
    source_cli_file = root / "source-cli-report.json"
    source_cli_file.write_text(json.dumps({
        "schema": "polisyos.schema_fqn_census.v2",
        "result": "complete_for_selected_local_text_inputs",
        "head": "frozen-head",
        "git_enumeration": {"complete_verdict": True},
        "selection": {"selected_path_count": 1},
        "scanned_denominator": {"selected_paths": 1, "read_paths": ["a.py"]},
        "unreadable_paths": [],
        "rejected_outside_root_paths": [],
        "interpretation_boundary": {"criterion_verdict": "local_static_census_only"},
    }), encoding="utf-8")
    source_cli_pass = source_cli_assertion(source_cli_file, "frozen-head")
    assert source_cli_pass["passed"] is True
    source_cli_file.write_text(source_cli_file.read_text(encoding="utf-8").replace("frozen-head", "other-head"), encoding="utf-8")
    source_cli_wrong_head = source_cli_assertion(source_cli_file, "frozen-head")
    assert source_cli_wrong_head["passed"] is False
    assert source_cli_wrong_head["criteria"]["reported_head_matches_freeze"] is False
    identity_plan_drift = evaluate_source_identity_facts(
        head="commit", head_tree="tree", frozen_tree="tree", commit="commit", tree="tree",
        worktree_diff_status=0, staged_diff_status=0,
        untracked_paths=[], ignored_source_paths=[],
        actual_plan_sha256="b" * 64, expected_plan_sha256="a" * 64,
    )
    assert identity_plan_drift["status"] == "FAIL"
    tool_hash_good = inspect_capture_tool_identity(
        sha256_file(Path(__file__).resolve()), sha256_file(PLUGIN_FILE.resolve())
    )
    tool_hash_mutated = inspect_capture_tool_identity("0" * 64, "0" * 64)
    assert tool_hash_good["matches_pinned_runtime_inputs"] is True
    assert tool_hash_mutated["matches_pinned_runtime_inputs"] is False
    original_sha256_file = globals()["sha256_file"]
    pinned_wrapper_sha = tool_hash_good["actual_sha256"]["wrapper"]
    pinned_plugin_sha = tool_hash_good["actual_sha256"]["plugin"]
    try:
        def mutated_capture_tool_sha(path: Path) -> str:
            if Path(path).resolve() in {Path(__file__).resolve(), PLUGIN_FILE.resolve()}:
                return "f" * 64
            return original_sha256_file(path)
        globals()["sha256_file"] = mutated_capture_tool_sha
        tool_file_mutated = inspect_capture_tool_identity(pinned_wrapper_sha, pinned_plugin_sha)
    finally:
        globals()["sha256_file"] = original_sha256_file
    assert tool_file_mutated["matches_pinned_runtime_inputs"] is False

    complete_child_dir = root / "complete-child-output"
    complete_child_dir.mkdir()
    for name in R4_EXPECTED_CHILD_STREAMS:
        (complete_child_dir / name).write_bytes((name + "\n").encode())
    (complete_child_dir / "extra.bin").write_bytes(b"complete child stream bytes")
    complete_children = inventory_child_output_directory(complete_child_dir, R4_EXPECTED_CHILD_STREAMS)
    assert complete_children["complete"] is True and complete_children["file_count"] == 7
    first_child_sha = next(
        item["sha256"] for item in complete_children["files"]
        if item["path"] == R4_EXPECTED_CHILD_STREAMS[0]
    )
    (complete_child_dir / R4_EXPECTED_CHILD_STREAMS[0]).write_bytes(b"changed complete child stream bytes")
    changed_children = inventory_child_output_directory(complete_child_dir, R4_EXPECTED_CHILD_STREAMS)
    changed_child_sha = next(
        item["sha256"] for item in changed_children["files"]
        if item["path"] == R4_EXPECTED_CHILD_STREAMS[0]
    )
    assert first_child_sha != changed_child_sha and changed_children["complete"] is True
    incomplete_child_dir = root / "incomplete-child-output"
    incomplete_child_dir.mkdir()
    for name in R4_EXPECTED_CHILD_STREAMS[:-1]:
        (incomplete_child_dir / name).write_bytes((name + "\n").encode())
    incomplete_children = inventory_child_output_directory(incomplete_child_dir, R4_EXPECTED_CHILD_STREAMS)
    assert incomplete_children["complete"] is False
    assert incomplete_children["missing_expected_files"] == [R4_EXPECTED_CHILD_STREAMS[-1]]
    symlink_child_dir = root / "symlink-child-output"
    symlink_child_dir.mkdir()
    (symlink_child_dir / "real.txt").write_bytes(b"actual file")
    (symlink_child_dir / "link.txt").symlink_to(symlink_child_dir / "real.txt")
    symlink_children = inventory_child_output_directory(symlink_child_dir, ())
    assert symlink_children["complete"] is False
    assert any(issue["reason"] == "symlink_not_admitted" for issue in symlink_children["issues"])

    boundary_run_dir = root / "synthetic-source-drift-run"
    boundary_run_dir.mkdir()
    boundary_identity_before = {
        "status": "PASS",
        "source": {"status": "PASS", "tracked_worktree_diff_clean": True},
        "capture_tools": tool_hash_good,
    }
    boundary_identity_after = {
        "status": "FAIL",
        "source": {"status": "FAIL", "reasons": ["TRACKED_WORKTREE_DIFF"]},
        "capture_tools": tool_hash_good,
    }
    original_inspect_live_identity = globals()["inspect_live_identity"]
    original_read_product_python_profile = globals()["read_product_python_profile"]
    identity_sequence = iter((boundary_identity_before, boundary_identity_after))
    synthetic_self_test_runtime_profile = {
        "status": "read",
        "prefix_matches_product_venv": True,
        "self_test_profile": "synthetic_source_drift",
    }
    synthetic_runtime_profile_sha256 = product_python_profile_sha256(
        synthetic_self_test_runtime_profile
    )

    def read_synthetic_self_test_runtime_profile(
        _command: dict[str, Any], _plan: dict[str, Any]
    ) -> dict[str, Any]:
        return dict(synthetic_self_test_runtime_profile)

    boundary_command_dir = root / "synthetic-source-drift-command"
    boundary_command = {
        "id": "SYNTHETIC_SOURCE_DRIFT_BOUNDARY",
        "order": 1,
        "phase": "light",
        "command_type": "python",
        "argv": [sys.executable, "-c", "print('synthetic boundary stdout')"],
        "cwd": str(Path.cwd()),
        "environment": {},
        "outputs": {
            "directory": str(boundary_command_dir),
            "stdout": str(boundary_command_dir / "stdout.bin"),
            "stderr": str(boundary_command_dir / "stderr.bin"),
            "metadata": str(boundary_command_dir / "metadata.json"),
            "junit": None,
        },
        "purpose": "prove post-command source drift blocks PASS",
        "prior_wall_time": None,
    }
    try:
        globals()["inspect_live_identity"] = (
            lambda *_args, **_kwargs: next(identity_sequence)
        )
        # Keep the synthetic run isolated from product runtime-profile admission.
        globals()["read_product_python_profile"] = read_synthetic_self_test_runtime_profile
        boundary_result = run_one(
            boundary_command, {}, run_dir=boundary_run_dir,
            plan={"execution": {"output_root": str(root)}},
            plan_path=Path(__file__).resolve(), frozen_commit="synthetic-commit",
            frozen_tree="synthetic-tree", plan_sha="a" * 64,
            input_manifest_sha="b" * 64, versions={},
            source_manifest_path=root / "synthetic-source-input-manifest.json",
            source_manifest_sha256="c" * 64,
            expected_wrapper_sha256=tool_hash_good["actual_sha256"]["wrapper"],
            expected_plugin_sha256=tool_hash_good["actual_sha256"]["plugin"],
            expected_runtime_profile_sha256=synthetic_runtime_profile_sha256,
        )
    finally:
        globals()["inspect_live_identity"] = original_inspect_live_identity
        globals()["read_product_python_profile"] = original_read_product_python_profile
    assert boundary_result["status"] == "FROZEN_SOURCE_IDENTITY_DRIFT"
    assert boundary_result["source_identity_before"]["status"] == "PASS"
    assert boundary_result["source_identity_after"]["status"] == "FAIL"
    import runpy
    namespace = runpy.run_path(str(PLUGIN_FILE))
    fake_root = root / "product"
    source_file = fake_root / "src/polisyos/fake.py"
    external_file = root / "foreign/polisyos/fake.py"
    import types
    inside = types.ModuleType("polisyos")
    inside.__file__ = str(fake_root / "src/polisyos/__init__.py")
    owned = types.ModuleType("polisyos.fake")
    owned.__file__ = str(source_file)
    manifest = namespace["build_origin_manifest"]({"polisyos": inside, "polisyos.fake": owned}, fake_root)
    assert manifest["assertion"]["passed"] is True
    bad = types.ModuleType("polisyos.bad")
    bad.__file__ = str(external_file)
    rejected = namespace["build_origin_manifest"]({"polisyos": inside, "polisyos.bad": bad}, fake_root)
    assert rejected["assertion"]["passed"] is False
    saved_modules = {
        name: module for name, module in sys.modules.items()
        if name == "polisyos" or name.startswith("polisyos.") or name == "tools" or name.startswith("tools.")
    }
    for name in list(saved_modules):
        sys.modules.pop(name, None)
    sys.modules["polisyos"] = inside
    sys.modules["polisyos.fake"] = owned
    prior_origin = os.environ.get("POLISYOS_CAPTURE_ORIGIN_FILE")
    prior_root = os.environ.get("POLISYOS_CAPTURE_PRODUCT_ROOT")
    origin_base = root / "module-origins.json"
    os.environ["POLISYOS_CAPTURE_ORIGIN_FILE"] = str(origin_base)
    os.environ["POLISYOS_CAPTURE_PRODUCT_ROOT"] = str(fake_root)
    try:
        namespace["pytest_sessionfinish"](None, 0)
    finally:
        for name in ("polisyos", "polisyos.fake"):
            sys.modules.pop(name, None)
        sys.modules.update(saved_modules)
        if prior_origin is None:
            os.environ.pop("POLISYOS_CAPTURE_ORIGIN_FILE", None)
        else:
            os.environ["POLISYOS_CAPTURE_ORIGIN_FILE"] = prior_origin
        if prior_root is None:
            os.environ.pop("POLISYOS_CAPTURE_PRODUCT_ROOT", None)
        else:
            os.environ["POLISYOS_CAPTURE_PRODUCT_ROOT"] = prior_root
    plugin_receipt = root / f"module-origins-{os.getpid()}.json"
    assert json.loads(plugin_receipt.read_text(encoding="utf-8"))["assertion"]["passed"] is True
    origin_receipt_check = check_module_origin_receipts(root, os.getpid())
    assert origin_receipt_check["passed"] is True
    receipt = {
        "status": "PASS",
        "elapsed_seconds": elapsed,
        "start_utc": start,
        "end_utc": end,
        "max_sampled_process_rss_kb": rss,
        "stdout_sha256": sha256_file(out),
        "stderr_sha256": sha256_file(err),
        "junit_status_counts": parsed["counts"],
        "junit_sample_case_records": parsed["testcases"],
        "skip_classification": skipped_status,
        "exit_137_classification": "EXIT_NONZERO_WITHOUT_OOM_INFERENCE",
        "source_identity_positive": identity_good,
        "source_identity_tracked_change_negative": identity_source_drift,
        "source_identity_untracked_source_negative": identity_untracked_source,
        "source_identity_ignored_source_negative": identity_ignored_source,
        "local_raw_untracked_import_source_negative": identity_local_raw_source_escape,
        "local_raw_manifested_import_source_positive": identity_local_raw_source_pinned,
        "local_raw_discovered_untracked_import_source_negative": {
            "probe_path": raw_probe_rel,
            "status": actual_untracked_local_raw["status"],
            "reasons": actual_untracked_local_raw["reasons"],
            "source_count": len(raw_scanned_paths),
            "excluded_roots": RAW_IMPORT_RUNTIME_EXCLUSIONS["excluded_roots"],
        },
        "local_raw_manifested_untracked_import_source_positive": actual_manifested_local_raw,
        "c12_separate_environment_binding": c12_environment,
        "c12_model_asset_inventory": c12_assets,
        "source_identity_plan_byte_change_negative": identity_plan_drift,
        "plan_derived_output_roots": {
            "plan_bindings": complete_manifest["plan_output_bindings"],
            "synthetic_data_symlink_inventory": synthetic_inventory,
            "source_files_unchanged_by_generated_data_alias": {
                "before_count": len(before_output_sources["files"]),
                "after_count": len(after_output_sources["files"]),
                "source_alias_sets_equal": (
                    before_output_sources["symlink_aliases"]
                    == after_output_sources["symlink_aliases"]
                ),
            },
            "precreated_source_root_refusal": precreated_output_refusal,
            "code_outside_declared_output_root_still_refused": {
                "status": source_elsewhere_identity["status"],
                "reasons": source_elsewhere_identity["reasons"],
            },
        },
        "source_cli_json_readback_positive": source_cli_pass,
        "source_cli_wrong_head_negative": source_cli_wrong_head,
        "capture_tool_pin_positive": tool_hash_good,
        "capture_tool_pin_mismatch_negative": tool_hash_mutated,
        "capture_tool_file_mutation_negative": tool_file_mutated,
        "child_output_inventory_positive": complete_children,
        "child_output_content_hash_change_negative": {
            "before_sha256": first_child_sha, "after_sha256": changed_child_sha,
            "changed": first_child_sha != changed_child_sha,
        },
        "child_output_missing_file_negative": incomplete_children,
        "child_output_symlink_negative": symlink_children,
        "per_command_source_identity_drift_negative": {
            "status": boundary_result["status"],
            "source_identity_before": boundary_result["source_identity_before"]["status"],
            "source_identity_after": boundary_result["source_identity_after"]["status"],
            "metadata_sha256": sha256_file(boundary_command_dir / "metadata.json"),
            "full_synthetic_stdout_sha256": sha256_file(boundary_command_dir / "stdout.bin"),
        },
        "origin_assertion_positive": manifest["assertion"],
        "origin_assertion_negative": rejected["assertion"],
        "pytest_hook_receipt_sha256": sha256_file(plugin_receipt),
        "origin_receipt_group_check": origin_receipt_check,
    }
    write_json_once(root / "selftest-receipt.json", receipt)
    print(json.dumps({"selftest": "PASS", "receipt": str(root / "selftest-receipt.json")}, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", type=Path, help="absolute or product-root-relative composed plan JSON")
    ap.add_argument("--supplement-plan", type=Path, help="optional prepared supplement whose bytes must also enter the raw-source manifest")
    ap.add_argument("--frozen-plan-sha256", help="root-pinned SHA-256 for the selected plan JSON")
    ap.add_argument("--frozen-commit", help="exact root-supplied frozen HEAD commit")
    ap.add_argument("--frozen-tree", help="exact root-supplied complete tree id")
    ap.add_argument("--frozen-capture-wrapper-sha256", help="root-pinned SHA-256 for this ignored wrapper")
    ap.add_argument("--frozen-capture-plugin-sha256", help="root-pinned SHA-256 for the ignored pytest-origin plugin")
    ap.add_argument("--source-input-manifest", type=Path, help="root-reviewed immutable manifest of LOCAL/raw import sources and local plan/config files")
    ap.add_argument("--frozen-source-input-manifest-sha256", help="root-pinned SHA-256 for --source-input-manifest")
    ap.add_argument("--prepare-source-input-manifest", action="store_true", help="prepare a one-time raw source input manifest without running product commands")
    ap.add_argument("--source-input-manifest-output", type=Path, help="new non-existing JSON output path for --prepare-source-input-manifest")
    ap.add_argument("--start", help="inclusive command ID to start at")
    ap.add_argument("--stop", help="inclusive command ID to stop after")
    ap.add_argument("--only", action="append", help="explicit command ID; may be repeated for independent resume")
    ap.add_argument("--continue-command-failures", action="store_true", help="continue only after a fully captured pytest FAIL/ERROR; final status remains nonzero")
    ap.add_argument("--allow-heavy", action="store_true", help="required for any heavy-phase command after root releases the slot")
    ap.add_argument("--self-test", action="store_true", help="run the capture-harness self-test inside a verified plan-owned output directory")
    ap.add_argument("--self-test-output-directory", type=Path, help="new output child declared by the verified self-test plan")
    ap.add_argument("--validate-only", action="store_true", help="verify freeze/input/output preconditions without running a plan command")
    return ap


def main() -> int:
    args = parser().parse_args()
    if args.self_test:
        if any((args.plan, args.frozen_commit, args.frozen_tree,
                args.frozen_capture_wrapper_sha256, args.frozen_capture_plugin_sha256,
                args.supplement_plan, args.frozen_plan_sha256, args.prepare_source_input_manifest,
                args.source_input_manifest_output,
                args.start, args.stop, args.only, args.allow_heavy, args.continue_command_failures, args.validate_only)):
            raise CaptureError("--self-test cannot be combined with execution options")
        if not all((args.source_input_manifest, args.frozen_source_input_manifest_sha256,
                    args.self_test_output_directory)):
            raise CaptureError(
                "--self-test requires --source-input-manifest, "
                "--frozen-source-input-manifest-sha256, and --self-test-output-directory"
            )
        source_input_manifest_path = args.source_input_manifest
        if not source_input_manifest_path.is_absolute():
            source_input_manifest_path = PRODUCT_ROOT / source_input_manifest_path
        return self_test(
            source_input_manifest_path, args.frozen_source_input_manifest_sha256,
            args.self_test_output_directory, sys.argv[1:],
        )
    if args.self_test_output_directory is not None:
        raise CaptureError("--self-test-output-directory requires --self-test")
    if args.prepare_source_input_manifest:
        if not args.plan or not args.source_input_manifest_output:
            raise CaptureError("manifest preparation requires --plan and --source-input-manifest-output")
        if any((args.frozen_plan_sha256, args.frozen_commit, args.frozen_tree,
                args.frozen_capture_wrapper_sha256, args.frozen_capture_plugin_sha256,
                args.source_input_manifest, args.frozen_source_input_manifest_sha256,
                args.start, args.stop, args.only, args.allow_heavy, args.continue_command_failures, args.validate_only)):
            raise CaptureError("manifest preparation cannot be combined with execution/freeze options")
        plan_path = args.plan if args.plan.is_absolute() else PRODUCT_ROOT / args.plan
        plan = load_and_validate_plan(plan_path)
        _require_capture_cli_selected_plan(plan)
        extra_plan_paths: list[Path] = []
        if args.supplement_plan:
            supplement_path = args.supplement_plan if args.supplement_plan.is_absolute() else PRODUCT_ROOT / args.supplement_plan
            supplement = load_and_validate_plan(supplement_path)
            if not supplement.get("_normalized_from_supplement"):
                raise CaptureError("--supplement-plan must use the supported light-gap supplement schema")
            base_from_supplement = Path(supplement["_source_plan_paths"][1]).as_posix()
            if base_from_supplement != _relative_product_path(plan_path):
                raise CaptureError("supplement base_plan does not match the supplied canonical --plan")
            extra_plan_paths.append(supplement_path)
        manifest_output = args.source_input_manifest_output
        if not manifest_output.is_absolute():
            manifest_output = LOCAL_RAW / manifest_output
        result = prepare_raw_source_manifest(
            plan_path.resolve(), plan, manifest_output,
            additional_plan_paths=extra_plan_paths,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if not all((args.plan, args.frozen_plan_sha256, args.frozen_commit, args.frozen_tree,
                args.frozen_capture_wrapper_sha256, args.frozen_capture_plugin_sha256,
                args.source_input_manifest, args.frozen_source_input_manifest_sha256)):
        raise CaptureError(
            "execution requires the plan, its root-pinned SHA-256, frozen commit/tree, both capture-tool SHA-256 values, and source manifest path/hash"
        )
    if args.continue_command_failures and args.validate_only:
        raise CaptureError("--continue-command-failures cannot be combined with --validate-only")
    plan_path = args.plan if args.plan.is_absolute() else PRODUCT_ROOT / args.plan
    plan = load_and_validate_plan(plan_path)
    _require_capture_cli_selected_plan(plan)
    plan["_path"] = str(plan_path.resolve())
    source_manifest_path = args.source_input_manifest
    if not source_manifest_path.is_absolute():
        source_manifest_path = PRODUCT_ROOT / source_manifest_path
    plan_sha = sha256_file(plan_path.resolve())
    if not re.fullmatch(r"[0-9a-fA-F]{64}", args.frozen_plan_sha256):
        raise CaptureError("--frozen-plan-sha256 must be a 64-character hexadecimal SHA-256")
    if plan_sha != args.frozen_plan_sha256.lower():
        raise CaptureError("selected plan bytes do not match the root-pinned --frozen-plan-sha256")
    declared_commit = plan.get("source_scope", {}).get("final_commit")
    declared_tree = plan.get("source_scope", {}).get("final_tree")
    if declared_commit is not None and declared_commit != args.frozen_commit:
        raise CaptureError("plan final_commit conflicts with root-supplied freeze")
    if declared_tree is not None and declared_tree != args.frozen_tree:
        raise CaptureError("plan final_tree conflicts with root-supplied freeze")
    execution = plan["execution"]
    output_root = admit_plan_output_root(plan_path, plan)
    if plan.get("_normalized_from_supplement"):
        capture_root = Path(plan["_capture_root"])
        capture_root_relative = _lexical_product_relative(
            capture_root, "supplement capture root",
        )
        if capture_root_relative != output_root.relative_to(PRODUCT_ROOT).as_posix():
            raise CaptureError("supplement output_root differs from its frozen capture_root")
    output_root.mkdir(parents=True, exist_ok=True)
    lock_fd = acquire_lock(plan)
    try:
        frozen = verify_branch_and_freeze(
            args.frozen_commit, args.frozen_tree,
            plan_path=plan_path.resolve(), plan_sha256=plan_sha,
            expected_wrapper_sha256=args.frozen_capture_wrapper_sha256,
            expected_plugin_sha256=args.frozen_capture_plugin_sha256,
            source_manifest_path=source_manifest_path,
            source_manifest_sha256=args.frozen_source_input_manifest_sha256,
        )
        input_manifest = verify_input_manifest(
            plan_path.resolve(), plan, args.frozen_commit, source_manifest_path,
        )
        selected = select_commands(plan, args)
        scratch = checked_paths_for_commands(plan, selected)
        refuse_unadmitted_unselected_outputs(plan, selected)
        # Preserve the product venv entrypoint so Python discovers its own prefix;
        # validate the resolved target independently and bind the actual runtime profile.
        first_command = selected[0]
        python_path, python_target = selected_product_python(first_command, plan)
        versions = validate_product_python_profile(
            package_versions(python_path), python_path, python_target,
        )
        runtime_profile_sha256 = product_python_profile_sha256(versions)
        input_manifest["selected_runtime_profile_sha256"] = runtime_profile_sha256
        input_manifest["frozen_commit"] = args.frozen_commit
        input_manifest["frozen_tree"] = args.frozen_tree
        input_manifest["plan_sha256"] = plan_sha
        input_manifest["source_input_manifest_path"] = str(source_manifest_path.resolve())
        input_manifest["source_input_manifest_sha256"] = args.frozen_source_input_manifest_sha256.lower()
        input_manifest["plan_adapter"] = plan.get("_adapter_metadata")
        fixture_inputs = []
        for fixture in execution["freeze_input_manifest"].get("fixture_inputs", []):
            copied = dict(fixture)
            if isinstance(copied.get("value"), str):
                copied["value_sha256"] = sha256_bytes(copied["value"].encode("utf-8"))
            fixture_inputs.append(copied)
        input_manifest["fixture_inputs_at_freeze"] = fixture_inputs
        input_manifest["capture_tool_inputs"] = {
            "wrapper": {
                "path": str(Path(__file__).resolve()),
                "sha256": args.frozen_capture_wrapper_sha256.lower(),
            },
            "pytest_origin_plugin": {
                "path": str(PLUGIN_FILE.resolve()),
                "sha256": args.frozen_capture_plugin_sha256.lower(),
            },
            "pin_source": "root-supplied immutable CLI values; rechecked before and after every command",
        }
        manifest_sha = sha256_bytes(json.dumps(input_manifest, sort_keys=True).encode())
        if args.validate_only:
            print(json.dumps({
                "status": "VALIDATED_NOT_RUN", "branch": frozen["branch"], "head": frozen["head"],
                "tree": frozen["tree"], "plan_sha256": plan_sha,
                "input_manifest_sha256": manifest_sha, "input_count": input_manifest["path_count"],
                "source_input_manifest_sha256": args.frozen_source_input_manifest_sha256.lower(),
                "capture_tool_identity": frozen["identity"]["capture_tools"],
                "selected_command_ids": [c["id"] for c in selected], "python_and_package_versions": versions,
                "selected_runtime_profile_sha256": runtime_profile_sha256,
            }, indent=2))
            return 0
        frozen_manifest_path = Path(execution["freeze_input_manifest"]["path"])
        ensure_inside(frozen_manifest_path, output_root, "frozen input manifest output")
        serialized_manifest = {
            "schema": "policyos.composed_mac_frozen_input_manifest.v2",
            **input_manifest,
            "manifest_sha256": manifest_sha,
        }
        if frozen_manifest_path.exists() or frozen_manifest_path.is_symlink():
            existing = json.loads(frozen_manifest_path.read_text(encoding="utf-8"))
            if existing != serialized_manifest:
                raise CaptureError(f"existing frozen-input manifest differs; refusing overwrite: {frozen_manifest_path}")
        else:
            write_json_once(frozen_manifest_path, serialized_manifest)
        run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex
        run_dir = output_root / "_capture_runs" / run_id
        if run_dir.exists() or run_dir.is_symlink():
            raise CaptureError(f"run directory collision: {run_dir}")
        run_dir.mkdir(parents=True, exist_ok=False)
        write_json_once(run_dir / "run-manifest.json", {
            "schema": "policyos.composed_mac_capture_run.v2", "run_id": run_id,
            "started_utc": utc_now(), "status": "RUNNING", "branch": frozen["branch"],
            "frozen_commit": args.frozen_commit, "frozen_tree": args.frozen_tree,
            "plan_path": str(plan_path.resolve()), "plan_sha256": plan_sha,
            "plan_adapter": plan.get("_adapter_metadata"),
            "source_input_manifest_path": str(source_manifest_path.resolve()),
            "source_input_manifest_sha256": args.frozen_source_input_manifest_sha256.lower(),
            "wrapper_path": str(Path(__file__).resolve()),
            "wrapper_sha256": args.frozen_capture_wrapper_sha256.lower(),
            "pytest_origin_plugin_path": str(PLUGIN_FILE.resolve()),
            "pytest_origin_plugin_sha256": args.frozen_capture_plugin_sha256.lower(),
            "capture_tool_identity_at_start": frozen["identity"]["capture_tools"],
            "input_manifest_sha256": manifest_sha, "input_manifest": input_manifest,
            "python_and_package_versions": versions,
            "selected_runtime_profile_sha256": runtime_profile_sha256,
            "selected_command_ids": [c["id"] for c in selected],
            "queue_status": {c["id"]: "UNRUN" for c in plan["execution"]["commands"]},
            "no_wall_timeout": True,
        })
        append_jsonl(run_dir / "events.jsonl", {
            "event": "run_started", "at_utc": utc_now(),
            "selected_command_ids": [c["id"] for c in selected],
            "source_identity": frozen["identity"]["source"],
            "capture_tool_identity": frozen["identity"]["capture_tools"],
        })
        outcomes: list[dict[str, Any]] = []
        stopped = False
        for command in selected:
            result = run_one(
                command, scratch[command["id"]], run_dir=run_dir, plan=plan,
                plan_path=plan_path.resolve(), frozen_commit=args.frozen_commit,
                frozen_tree=args.frozen_tree, plan_sha=plan_sha,
                input_manifest_sha=manifest_sha, versions=versions,
                source_manifest_path=source_manifest_path,
                source_manifest_sha256=args.frozen_source_input_manifest_sha256,
                expected_wrapper_sha256=args.frozen_capture_wrapper_sha256,
                expected_plugin_sha256=args.frozen_capture_plugin_sha256,
                expected_runtime_profile_sha256=runtime_profile_sha256,
            )
            control = result.pop("_queue_control", {})
            outcomes.append(result)
            if result["status"] in ("PASS", "PREFLIGHT_PASS", "SOURCE_CLI_PASS"):
                continue

            can_continue = False
            continuation_evidence: dict[str, Any] | None = None
            if result.get("status") in ("FAIL", "ERROR"):
                continuation_evidence = captured_pytest_failure_continuation(
                    command,
                    result,
                    control,
                    expected_commit=args.frozen_commit,
                    expected_tree=args.frozen_tree,
                    expected_plan_sha256=plan_sha,
                    expected_input_manifest_sha256=manifest_sha,
                    expected_source_manifest_sha256=args.frozen_source_input_manifest_sha256,
                    expected_wrapper_sha256=args.frozen_capture_wrapper_sha256,
                    expected_plugin_sha256=args.frozen_capture_plugin_sha256,
                    expected_runtime_profile_sha256=runtime_profile_sha256,
                )
                can_continue = (
                    args.continue_command_failures
                    and continuation_evidence["eligible"]
                )
                decision = {
                    "event": "command_failure_continuation_decided",
                    "at_utc": utc_now(),
                    "command_id": command["id"],
                    "order": command["order"],
                    "status": result["status"],
                    "requested": args.continue_command_failures,
                    "decision": (
                        "CONTINUE" if can_continue
                        else "STOP_EVIDENCE_REFUSED" if args.continue_command_failures
                        else "STOP_POLICY_NOT_REQUESTED"
                    ),
                    "evidence": continuation_evidence,
                    "run_id": run_id,
                    "plan_sha256": plan_sha,
                    "source_input_manifest_sha256": args.frozen_source_input_manifest_sha256.lower(),
                }
                append_jsonl(run_dir / "events.jsonl", decision)
                append_jsonl(history_path(plan), decision)
                if can_continue:
                    print(
                        f"[FAILURE_CONTINUED] {command['id']} remains {result['status']}; "
                        "selected queue continues with nonzero final status",
                        flush=True,
                    )
                    continue

            stopped = True
            append_jsonl(run_dir / "events.jsonl", {
                "event": "queue_stopped", "at_utc": utc_now(), "after_command": command["id"],
                "reason": result["status"],
                "failure_continuation": continuation_evidence,
                "remaining_selected_ids": [c["id"] for c in selected[len(outcomes):]],
                "global_remaining_status": "UNRUN",
            })
            break
        failed_command_ids = [
            item["command_id"] for item in outcomes
            if (
                item.get("status") in ("FAIL", "ERROR")
                or item.get("pytest_result_status") in ("FAIL", "ERROR")
            )
        ]
        final_status = (
            "STOPPED_UNRUN_REMAINDER"
            if stopped
            else "SELECTED_RANGE_COMPLETE_WITH_FAILURES"
            if failed_command_ids
            else "SELECTED_RANGE_COMPLETE"
        )
        final = {
            "schema": "policyos.composed_mac_capture_completion.v2", "run_id": run_id,
            "completed_utc": utc_now(), "status": final_status,
            "frozen_commit": args.frozen_commit, "frozen_tree": args.frozen_tree,
            "plan_sha256": plan_sha, "input_manifest_sha256": manifest_sha,
            "source_input_manifest_sha256": args.frozen_source_input_manifest_sha256.lower(),
            "selected_runtime_profile_sha256": runtime_profile_sha256,
            "capture_tool_identity": frozen["identity"]["capture_tools"],
            "executed_command_ids": [item["command_id"] for item in outcomes],
            "command_statuses": {item["command_id"]: item["status"] for item in outcomes},
            "queue_status": {
                command["id"]: next(
                    (
                        item["status"] for item in outcomes
                        if item["command_id"] == command["id"]
                    ),
                    "UNRUN",
                )
                for command in plan["execution"]["commands"]
            },
            "failed_command_ids": failed_command_ids,
            "remaining_selected_ids": [c["id"] for c in selected[len(outcomes):]],
            "all_unselected_and_remaining_status": "UNRUN",
            "run_directory": str(run_dir),
        }
        write_json_once(run_dir / "completion.json", final)
        append_jsonl(run_dir / "events.jsonl", {"event": "run_completed", **final})
        append_jsonl(history_path(plan), {"event": "run_completed", **final})
        print(json.dumps(final, indent=2, ensure_ascii=False))
        return 1 if stopped or failed_command_ids else 0
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CaptureError as exc:
        print(f"capture refused: {exc}", file=sys.stderr)
        raise SystemExit(2)
