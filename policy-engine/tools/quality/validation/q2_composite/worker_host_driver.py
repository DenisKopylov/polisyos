"""Run the source-pinned Q2 host/Linux primary barrier through real worker commands.

This module is the host-side bridge around the frozen R7 plan and worker
helpers. It prepares one profile-bound request, creates and starts the isolated
worker, records field-limited Docker inspection, finalizes and launches the
request, then returns the worker result to the R7 receipt reconciler. The
existing composite executor remains responsible for the six-partition barrier
and supplemental admission.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

R6_MANIFEST_SHA256 = "5e9aa6be859c6237d1a4a335d73688326737b20480f9d7e1720195a7a2ae884e"
R7_MANIFEST_SHA256 = "a4325fcc172729b0a25f79af738b8d96210340495d46f9568c248a309e22e8bc"
R7_CONSUMER_SHA256 = "575870f362b0b9a325179cc98706ae0d31548917953ebc796fb13fdca46e193c"
R7_PROFILE_COMPOSITE_SHA256 = "9e917403e64b9e3c5fb3da1bb68052df40341dec18617fef2016165bd9413f8c"
R7_PARTITION_RUNNER_SHA256 = "0d6185477bc4f79d90a4a4adf0c5ac5713ceb217ef5e62e43a58aeb69f17a20e"
R7_WORKER_MOUNTS_SHA256 = "95e04719efd8f137781f1a4df1a8e5608c3d37d3925f24374d45b4d81eba54d8"
WORKER_RUNTIME_BINDING_RELATIVE = Path("root-q2-worker-runtime-binding-input-3c13-20261020-r1")
WORKER_RUNTIME_REPORT_SHA256 = "12ea47a9b7bc5c651431bb1f3a73c65b5ea61e138a6364bb29e9036f6adb9c2c"
WORKER_RUNTIME_CORRIGENDUM_SHA256 = (
    "5ef2d20d8d893083e5ea29ba079015a4a3140f689f80617934d1ac60a695a2ad"
)
RUNTIME_SEQUENCE_SCHEMA = "policyos.e02.q2.worker-host-driver-sequence.v2"
_PROFILE_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,48}\Z")
_CONTAINER_ID_RE = re.compile(r"[0-9a-f]{64}\Z")
CANONICAL_SOURCE_MANIFEST = Path(__file__).with_name("source-manifest-r10.json")
CANONICAL_SOURCE_SCHEMA = "policyos.e02.q2.canonical-composed-source.r10.v1"


class WorkerHostDriverError(RuntimeError):
    """Raised when a source-bound host/worker execution transition fails."""


@dataclass(frozen=True)
class SourceBundle:
    """Verified canonical helpers with R6/R7 history retained as provenance."""

    repo_root: Path
    r6_root: Path
    r7_root: Path
    source_dir: Path
    split_protocol: ModuleType
    composite: ModuleType
    partition_runner: ModuleType
    worker_mounts: ModuleType
    split_consumer: ModuleType
    source_set_sha256: str
    source_manifest_sha256: str
    upstream_r7_source_set_sha256: str
    legacy_declared_source_set_sha256: str | None


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_source_set_digest(entries: list[tuple[str, str]]) -> str:
    """Hash a complete unique set of canonical POSIX paths and byte hashes."""
    if not entries:
        raise WorkerHostDriverError("source set must contain at least one member")
    seen: set[str] = set()
    for relative, digest in entries:
        if type(relative) is not str or not relative or "\\" in relative or "\0" in relative:
            raise WorkerHostDriverError("source-set path is not a canonical relative POSIX path")
        path = PurePosixPath(relative)
        if (
            path.is_absolute()
            or path.as_posix() != relative
            or any(part in {"", ".", ".."} for part in path.parts)
            or relative in seen
        ):
            raise WorkerHostDriverError("source set contains a noncanonical or duplicate path")
        if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise WorkerHostDriverError("source-set member hash is not a lowercase SHA-256")
        seen.add(relative)
    encoded = b"".join(
        relative.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\n"
        for relative, digest in sorted(entries, key=lambda item: item[0].encode("utf-8"))
    )
    return _sha256(encoded)


def _regular_bytes(path: Path, label: str) -> bytes:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except OSError as error:
            raise WorkerHostDriverError(f"{label} path cannot be inspected: {current}") from error
        if stat.S_ISLNK(info.st_mode):
            raise WorkerHostDriverError(f"{label} path traverses a symlink: {current}")
    try:
        info = path.lstat()
    except OSError as error:
        raise WorkerHostDriverError(f"{label} is unavailable: {path}") from error
    if not stat.S_ISREG(info.st_mode):
        raise WorkerHostDriverError(f"{label} must be a regular file: {path}")
    return path.read_bytes()


def _repo_root(path: Path) -> Path:
    for candidate in path.resolve(strict=True).parents:
        marker = candidate / ".git"
        if marker.is_file() or marker.is_dir():
            return candidate
    raise WorkerHostDriverError("Q2 driver cannot locate its containing Git worktree")


def _verify_frozen_source_set(
    manifest_raw: bytes,
    *,
    expected_manifest_sha256: str,
    repository_root: Path,
    expected_file_count: int,
) -> tuple[dict[str, Any], str, str | None]:
    """Verify pinned manifest bytes and recompute its complete member set."""
    if _sha256(manifest_raw) != expected_manifest_sha256:
        raise WorkerHostDriverError("source manifest differs from its frozen SHA-256")
    try:
        manifest = json.loads(manifest_raw)
    except json.JSONDecodeError as error:
        raise WorkerHostDriverError("source manifest is not valid JSON") from error
    if type(manifest) is not dict:
        raise WorkerHostDriverError("source manifest root must be an object")
    source_set = manifest.get("source_set")
    rows = source_set.get("files") if type(source_set) is dict else None
    if (
        type(rows) is not list
        or type(expected_file_count) is not int
        or expected_file_count <= 0
        or len(rows) != expected_file_count
        or type(source_set.get("file_count")) is not int
        or source_set.get("file_count") != expected_file_count
    ):
        raise WorkerHostDriverError("source manifest has an incomplete member denominator")
    entries: list[tuple[str, str]] = []
    observed: set[str] = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            raise WorkerHostDriverError("source manifest member row has an unsupported shape")
        relative = row["path"]
        if type(relative) is not str or not relative or "\\" in relative or "\0" in relative:
            raise WorkerHostDriverError("source manifest path is not canonical POSIX")
        posix = PurePosixPath(relative)
        if (
            posix.is_absolute()
            or not posix.parts
            or posix.as_posix() != relative
            or any(part in {"", ".", ".."} for part in posix.parts)
            or relative in observed
        ):
            raise WorkerHostDriverError("source manifest contains a duplicate or unsafe path")
        if type(row["bytes"]) is not int or row["bytes"] < 0:
            raise WorkerHostDriverError("source manifest member byte count is malformed")
        digest = row["sha256"]
        if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise WorkerHostDriverError("source manifest member hash is malformed")
        path = repository_root.joinpath(*posix.parts)
        raw_bytes = _regular_bytes(path, "frozen source member")
        if len(raw_bytes) != row["bytes"] or _sha256(raw_bytes) != digest:
            raise WorkerHostDriverError(f"frozen source member changed: {relative}")
        observed.add(relative)
        entries.append((relative, digest))
    source_digest = _canonical_source_set_digest(entries)
    declared_digest = source_set.get("path_sha256_set_digest")
    return (
        manifest,
        source_digest,
        declared_digest if type(declared_digest) is str else None,
    )


def _load_verified_module(name: str, path: Path) -> ModuleType:
    expected = path.resolve(strict=True)
    current = sys.modules.get(name)
    if current is not None:
        actual = getattr(current, "__file__", None)
        if actual is None or Path(actual).resolve(strict=True) != expected:
            raise WorkerHostDriverError(
                f"module {name!r} was already loaded from a different source path"
            )
        return current
    importlib.invalidate_caches()
    sys.path.insert(0, str(expected.parent))
    try:
        module = importlib.import_module(name)
    except Exception as error:
        raise WorkerHostDriverError(
            f"frozen source module {name!r} could not be imported"
        ) from error
    actual = getattr(module, "__file__", None)
    if actual is None or Path(actual).resolve(strict=True) != expected:
        raise WorkerHostDriverError(f"module {name!r} resolved outside its pinned source file")
    return module


def _canonical_source_rows(repo: Path) -> tuple[dict[str, Any], str, str]:
    """Verify the complete tracked Q2 source/test set from its local manifest."""
    source_dir = Path(__file__).resolve(strict=True).parent
    test_dir = repo / "policy-engine/tests/repo_quality/tools/q2_composite"
    manifest_raw = _regular_bytes(CANONICAL_SOURCE_MANIFEST, "R10 source manifest")
    try:
        manifest = json.loads(manifest_raw)
    except json.JSONDecodeError as error:
        raise WorkerHostDriverError("R10 source manifest is not valid JSON") from error
    if type(manifest) is not dict or manifest.get("schema") != CANONICAL_SOURCE_SCHEMA:
        raise WorkerHostDriverError("R10 source manifest has an unsupported schema")
    source_set = manifest.get("source_set")
    rows = source_set.get("files") if type(source_set) is dict else None
    if type(rows) is not list or not rows:
        raise WorkerHostDriverError("R10 source manifest has no complete file set")
    if (
        type(source_set) is not dict
        or source_set.get("file_count") != len(rows)
        or type(source_set.get("sorted_path_sha256_digest")) is not str
    ):
        raise WorkerHostDriverError("R10 source manifest has an incomplete set binding")

    discovered: set[str] = set()
    for root in (source_dir, test_dir):
        if root.is_symlink() or not root.is_dir():
            raise WorkerHostDriverError("R10 source or test root is not a real directory")
        for path in root.rglob("*"):
            if path.is_symlink():
                raise WorkerHostDriverError(f"R10 source tree contains a symlink: {path}")
            if path.is_file() and path.suffix == ".py":
                discovered.add(path.relative_to(repo).as_posix())
    observed: set[str] = set()
    entries: list[tuple[str, str]] = []
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            raise WorkerHostDriverError("R10 source member has an unsupported shape")
        relative = row["path"]
        if type(relative) is not str or not relative or "\\" in relative or "\0" in relative:
            raise WorkerHostDriverError("R10 source member path is not canonical")
        posix = PurePosixPath(relative)
        if (
            posix.is_absolute()
            or posix.as_posix() != relative
            or any(part in {"", ".", ".."} for part in posix.parts)
            or relative in observed
        ):
            raise WorkerHostDriverError("R10 source manifest has an unsafe or duplicate member")
        digest = row["sha256"]
        if (
            type(row["bytes"]) is not int
            or row["bytes"] < 0
            or type(digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise WorkerHostDriverError("R10 source member size or SHA-256 is malformed")
        path = repo.joinpath(*posix.parts)
        raw_bytes = _regular_bytes(path, "R10 canonical source member")
        if len(raw_bytes) != row["bytes"] or _sha256(raw_bytes) != digest:
            raise WorkerHostDriverError(f"R10 canonical source member changed: {relative}")
        observed.add(relative)
        entries.append((relative, digest))
    if observed != discovered:
        missing = sorted(discovered - observed)
        stale = sorted(observed - discovered)
        raise WorkerHostDriverError(
            f"R10 source manifest differs from discovered source/test files: missing={missing}, stale={stale}"
        )
    source_digest = _canonical_source_set_digest(entries)
    if source_set["sorted_path_sha256_digest"] != source_digest:
        raise WorkerHostDriverError("R10 source-set digest differs from recomputed members")
    return manifest, source_digest, _sha256(manifest_raw)


def load_composed_source_bundle(repo_root: str | Path, raw_root: str | Path) -> SourceBundle:
    """Load executable helpers from the tracked R10 package, not from RAW."""
    repo = Path(repo_root).resolve(strict=True)
    raw = Path(raw_root).resolve(strict=True)
    r7 = raw / "q2-split-candidate-r7-20261020"
    r6 = raw / "q2-split-candidate-r6-20261020"
    expected_raw = repo / (
        "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw"
    )
    if raw != expected_raw.resolve(strict=True):
        raise WorkerHostDriverError("historical R6/R7 receipts are outside the selected repository")
    source_dir = Path(__file__).resolve(strict=True).parent
    manifest, source_digest, source_manifest_sha = _canonical_source_rows(repo)

    upstream = manifest.get("upstream", {})
    r6_upstream = upstream.get("r6") if type(upstream) is dict else None
    r7_upstream = upstream.get("r7") if type(upstream) is dict else None
    expected_r6_path = (
        "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
        "q2-split-candidate-r6-20261020/manifest-r6.json"
    )
    expected_r7_path = (
        "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
        "q2-split-candidate-r7-20261020/manifest-r7-final-v3.json"
    )
    if (
        type(r6_upstream) is not dict
        or r6_upstream.get("manifest_path") != expected_r6_path
        or r6_upstream.get("manifest_sha256") != R6_MANIFEST_SHA256
        or type(r7_upstream) is not dict
        or r7_upstream.get("manifest_path") != expected_r7_path
        or r7_upstream.get("manifest_sha256") != R7_MANIFEST_SHA256
    ):
        raise WorkerHostDriverError("R10 source manifest lost its upstream provenance pins")

    r7_manifest_path = r7 / "manifest-r7-final-v3.json"
    r7_manifest_raw = _regular_bytes(r7_manifest_path, "historical R7 source manifest")
    _upstream_manifest, upstream_digest, legacy_declared_digest = _verify_frozen_source_set(
        r7_manifest_raw,
        expected_manifest_sha256=R7_MANIFEST_SHA256,
        repository_root=repo,
        expected_file_count=11,
    )
    row_by_path = {row["path"]: row for row in manifest["source_set"]["files"]}
    package_prefix = source_dir.relative_to(repo).as_posix() + "/"
    filenames = {
        "split_protocol": "split_protocol.py",
        "worker_mounts": "worker_mounts.py",
        "profile_partition_runner": "profile_partition_runner.py",
        "profile_composite": "profile_composite.py",
        "split_consumer": "split_consumer.py",
    }
    modules: dict[str, ModuleType] = {}
    for name in (
        "split_protocol",
        "worker_mounts",
        "profile_partition_runner",
        "profile_composite",
        "split_consumer",
    ):
        relative = package_prefix + filenames[name]
        row = row_by_path.get(relative)
        if row is None:
            raise WorkerHostDriverError(f"R10 source manifest omits executable module {name!r}")
        path = repo.joinpath(*PurePosixPath(relative).parts)
        if _sha256(_regular_bytes(path, f"R10 executable module {name}")) != row["sha256"]:
            raise WorkerHostDriverError(f"R10 executable module {name!r} differs from its pin")
        modules[name] = _load_verified_module(name, path)
    return SourceBundle(
        repo_root=repo,
        r6_root=r6,
        r7_root=r7,
        source_dir=source_dir,
        split_protocol=modules["split_protocol"],
        composite=modules["profile_composite"],
        partition_runner=modules["profile_partition_runner"],
        worker_mounts=modules["worker_mounts"],
        split_consumer=modules["split_consumer"],
        source_set_sha256=source_digest,
        source_manifest_sha256=source_manifest_sha,
        upstream_r7_source_set_sha256=upstream_digest,
        legacy_declared_source_set_sha256=legacy_declared_digest,
    )


def _load_live_worker_runtime(
    bundle: SourceBundle,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Derive the live profile from the exact operator-readback packet."""
    raw_root = bundle.r7_root.parent
    binding_root = raw_root / WORKER_RUNTIME_BINDING_RELATIVE
    report_path = binding_root / "report-v1.json"
    corrigendum_path = binding_root / "corrigendum-v1.json"
    report_raw = _regular_bytes(report_path, "worker runtime binding report")
    corrigendum_raw = _regular_bytes(corrigendum_path, "worker runtime corrigendum")
    if _sha256(report_raw) != WORKER_RUNTIME_REPORT_SHA256:
        raise WorkerHostDriverError("worker runtime report differs from its frozen SHA-256")
    if _sha256(corrigendum_raw) != WORKER_RUNTIME_CORRIGENDUM_SHA256:
        raise WorkerHostDriverError("worker runtime corrigendum differs from its frozen SHA-256")
    report = bundle.worker_mounts._strict_json_object(report_raw, "worker runtime binding report")
    corrigendum = bundle.worker_mounts._strict_json_object(
        corrigendum_raw, "worker runtime corrigendum"
    )
    if report.get("schema") != "q2_worker_runtime_binding_input_v1":
        raise WorkerHostDriverError("worker runtime report schema is unsupported")
    if corrigendum.get("schema") != "q2_worker_runtime_binding_readback_corrigendum_v1":
        raise WorkerHostDriverError("worker runtime corrigendum schema is unsupported")
    target_report = corrigendum.get("target_report")
    if (
        type(target_report) is not dict
        or target_report.get("path") != str(report_path)
        or target_report.get("sha256") != WORKER_RUNTIME_REPORT_SHA256
    ):
        raise WorkerHostDriverError("worker runtime corrigendum does not bind the exact report")
    commands = report.get("readback_commands")
    if type(commands) is not list or not commands:
        raise WorkerHostDriverError("worker runtime report omits command readbacks")
    known_nonzero_readbacks: list[dict[str, Any]] = []
    for row in commands:
        if (
            type(row) is not dict
            or type(row.get("argv")) is not list
            or type(row.get("returncode")) is not int
        ):
            raise WorkerHostDriverError("worker runtime command readback is malformed")
        if any("Config.Env" in str(argument) for argument in row["argv"]):
            raise WorkerHostDriverError("worker runtime readback includes environment contents")
        if row["returncode"] != 0:
            if row["returncode"] != 2 or row["argv"][-4:] != [
                "/usr/local/bin/uv",
                "python",
                "find",
                "3.14",
            ]:
                raise WorkerHostDriverError("worker runtime has an unqualified failed readback")
            known_nonzero_readbacks.append(
                {
                    "name": row.get("name"),
                    "argv": row["argv"],
                    "returncode": row["returncode"],
                    "stderr_sha256": row.get("stderr_sha256"),
                    "meaning": (
                        "uv discovery miss; explicit Python 3.14 path is separately verified"
                    ),
                }
            )
        for field, output_field in (
            ("stdout_sha256", "stdout"),
            ("stderr_sha256", "stderr"),
        ):
            output = row.get(output_field)
            if type(output) is not str:
                raise WorkerHostDriverError(f"worker runtime command {output_field} is malformed")
            if (
                type(row.get(field)) is not str
                or re.fullmatch(r"[0-9a-f]{64}", row[field]) is None
                or _sha256(output.encode("utf-8")) != row[field]
            ):
                raise WorkerHostDriverError(f"worker runtime command {field} is malformed")
    frame = report.get("source_frame")
    existing = report.get("existing_worker")
    future = report.get("future_container_intent_not_executed")
    if type(frame) is not dict or type(existing) is not dict or type(future) is not dict:
        raise WorkerHostDriverError("worker runtime report omits its measured source boundary")
    if (
        future.get("status") != "draft_only; no new container identity/image/mounts exist yet"
        or future.get("source_checkout_mount")
        != "forbidden; do not mount /Users/deniskopylov/polisyos or the managed worktree "
        "into the test container"
    ):
        raise WorkerHostDriverError("worker runtime report claims an unmeasured new container")
    identity = {
        "report_path": str(report_path),
        "report_sha256": WORKER_RUNTIME_REPORT_SHA256,
        "corrigendum_path": str(corrigendum_path),
        "corrigendum_sha256": WORKER_RUNTIME_CORRIGENDUM_SHA256,
        "source_frame_head": frame.get("head"),
        "source_frame_tree": frame.get("tree"),
        "existing_container_id": existing.get("container_id"),
        "existing_image_id": existing.get("image_id"),
        "future_intent_status": future["status"],
        "source_checkout_mount_policy": future["source_checkout_mount"],
        "new_container_status": "not_created",
        "nonzero_runtime_readbacks": known_nonzero_readbacks,
        "provenance_note": (
            "R7 loader status equality was incompatible with the exact pinned report wording"
        ),
    }
    runtime = bundle.worker_mounts.runtime_contract_from_binding_input(report)
    validated_runtime = bundle.worker_mounts.validate_runtime_contract(runtime)
    return validated_runtime, identity


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _write_exclusive_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_json_bytes(value) + b"\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    if _regular_bytes(path, "Q2 host-driver receipt") != raw:
        raise WorkerHostDriverError(f"Q2 host-driver receipt readback differs: {path}")
    return _sha256(raw)


def _command_observation(
    argv: list[str], *, cwd: Path, timeout_seconds: int, runner: Callable[..., Any]
) -> dict[str, Any]:
    try:
        process = runner(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if type(stdout) is bytes:
            stdout = stdout.decode("utf-8", errors="backslashreplace")
        if type(stderr) is bytes:
            stderr = stderr.decode("utf-8", errors="backslashreplace")
        return {
            "argv": list(argv),
            "cwd": str(cwd),
            "returncode": None,
            "timed_out": True,
            "stdout": stdout,
            "stderr": stderr,
        }
    stdout = process.stdout
    stderr = process.stderr
    if type(process.returncode) is not int or type(stdout) is not str or type(stderr) is not str:
        raise WorkerHostDriverError("Docker runner returned a malformed process result")
    return {
        "argv": list(argv),
        "cwd": str(cwd),
        "returncode": process.returncode,
        "timed_out": False,
        "stdout": stdout,
        "stderr": stderr,
    }


def _require_success(observation: dict[str, Any], label: str) -> str:
    if observation.get("timed_out") is not False or observation.get("returncode") != 0:
        raise WorkerHostDriverError(f"{label} command failed or timed out")
    stdout = observation.get("stdout")
    stderr = observation.get("stderr")
    if type(stdout) is not str or type(stderr) is not str:
        raise WorkerHostDriverError(f"{label} command output is malformed")
    return stdout


class WorkerHostDriver:
    """Compose the frozen Q2 plan with actual process-backed Docker callbacks.

    ``run_host_partition`` and ``run_supplemental_partition`` are the existing
    host consumers from the source-bound Q2 runner. This class owns the worker
    half and invokes the shared executor, which recomputes every receipt and
    holds all supplementals behind the six-partition primary barrier.
    """

    def __init__(
        self,
        *,
        plan: dict[str, Any],
        runtime_contract: dict[str, Any] | None,
        source_bundle: SourceBundle,
        source_root: str | Path,
        output_root: str | Path,
        origin_gate_path: str | Path,
        neutral_cwd: str | Path,
        command_runner: Callable[..., Any] | None = None,
        command_execution_mode: str | None = None,
        command_timeout_seconds: int = 120,
        launch_timeout_seconds: int = 600,
    ) -> None:
        self.plan = plan
        self.bundle = source_bundle
        self.mounts = source_bundle.worker_mounts
        self.partition = source_bundle.partition_runner
        self.composite = source_bundle.composite
        self.source_set_binding = {
            "r10_manifest_sha256": source_bundle.source_manifest_sha256,
            "r10_recomputed_sorted_source_set_sha256": source_bundle.source_set_sha256,
            "r7_manifest_sha256": R7_MANIFEST_SHA256,
            "r7_recomputed_sorted_source_set_sha256": (source_bundle.upstream_r7_source_set_sha256),
            "r7_legacy_declared_source_set_sha256": (
                source_bundle.legacy_declared_source_set_sha256
            ),
            "r7_legacy_declared_digest_role": "provenance_only_not_an_admission_predicate",
        }
        self.source_root = Path(source_root).resolve(strict=True)
        if str(self.source_root) != plan.get("source_checkout", {}).get("path"):
            raise WorkerHostDriverError("driver source root differs from the frozen plan")
        self.output_root = Path(output_root).absolute()
        self.origin_gate_path = Path(origin_gate_path).resolve(strict=True)
        self.neutral_cwd = Path(neutral_cwd).resolve(strict=True)
        if self.source_root == self.neutral_cwd or self.source_root in self.neutral_cwd.parents:
            raise WorkerHostDriverError("Docker commands must run outside the source checkout")
        if self.neutral_cwd == self.output_root or self.output_root in self.neutral_cwd.parents:
            raise WorkerHostDriverError("neutral Docker cwd must be separate from output roots")
        if type(command_timeout_seconds) is not int or command_timeout_seconds <= 0:
            raise WorkerHostDriverError("Docker command timeout must be a positive integer")
        if type(launch_timeout_seconds) is not int or launch_timeout_seconds <= 0:
            raise WorkerHostDriverError("worker launch timeout must be a positive integer")
        if command_runner is None:
            if command_execution_mode not in (None, "live_subprocess"):
                raise WorkerHostDriverError("live Docker execution mode requires subprocess.run")
            if runtime_contract is not None:
                raise WorkerHostDriverError(
                    "live runtime expectations must be derived from frozen worker readback"
                )
            self.command_runner = subprocess.run
            self.command_execution_mode = "live_subprocess"
            self.runtime, self.runtime_binding_identity = _load_live_worker_runtime(source_bundle)
        else:
            if command_execution_mode != "recorded_test":
                raise WorkerHostDriverError(
                    "an injected Docker command runner must be marked recorded_test"
                )
            if runtime_contract is None:
                raise WorkerHostDriverError(
                    "recorded-test Docker commands require a controlled runtime fixture"
                )
            self.command_runner = command_runner
            self.command_execution_mode = "recorded_test"
            self.runtime = self.mounts.validate_runtime_contract(runtime_contract)
            self.runtime_binding_identity = {
                "new_container_status": "not_created",
                "status": "recorded_test_fixture_not_runtime",
            }
        self.command_timeout_seconds = command_timeout_seconds
        self.launch_timeout_seconds = launch_timeout_seconds
        self.command_rows: list[dict[str, Any]] = []
        self._prepared_by_profile: dict[str, dict[str, Any]] = {}
        self._mappings_by_profile: dict[str, dict[str, Any]] = {}
        self._sequence_refs_by_profile: dict[str, dict[str, str]] = {}
        self._create_output_root()
        self.shared_artifacts_root = self.output_root / "worker-shared-artifacts"
        self.shared_artifacts_root.mkdir(mode=0o700)

    def _create_output_root(self) -> None:
        if self.output_root.exists() or self.output_root.is_symlink():
            raise WorkerHostDriverError("driver output root must be a fresh, absent directory")
        self.output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        if self.output_root.is_symlink() or not self.output_root.is_dir():
            raise WorkerHostDriverError("driver output root is not a regular directory")

    def _profile_mount_map(self, partition: dict[str, Any]) -> dict[str, Any]:
        profile = partition.get("profile")
        if type(profile) is not str or _PROFILE_RE.fullmatch(profile) is None:
            raise WorkerHostDriverError("Linux partition has an unsupported profile identity")
        run = next(
            (
                row
                for row in self.plan.get("run_plan", [])
                if row.get("profile") == profile and row.get("executor") == "linux-worker"
            ),
            None,
        )
        if type(run) is not dict or partition != run:
            raise WorkerHostDriverError("Linux callback differs from the selected run-plan row")
        plan_sha = self.plan.get("plan_sha256")
        profile_root = self.output_root / "profiles" / profile
        profile_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        roots = {
            "inputs": profile_root / "inputs",
            "artifacts": self.shared_artifacts_root,
            "profile-prefix": profile_root / "prefix",
            "receipts": profile_root / "receipts",
        }
        for root in roots.values():
            if root == self.shared_artifacts_root:
                continue
            root.mkdir(mode=0o700, exist_ok=False)
        # Each disposable container sees one selected profile, so the worker
        # destinations stay stable while host-side profile roots remain disjoint.
        worker_roots = {
            "inputs": "/mnt/e02-q2/inputs",
            "artifacts": "/mnt/e02-q2/artifacts",
            "profile-prefix": "/mnt/e02-q2/prefix",
            "receipts": "/mnt/e02-q2/receipts",
        }
        mapping = self.mounts.build_mount_map(
            source=self.plan["source"],
            plan_sha256=plan_sha,
            profile=profile,
            artifact_sha256=run["artifact_sha256"],
            node_ids_sha256=run["node_ids_sha256"],
            runtime_contract=self.runtime,
            host_roots=roots,
            worker_roots=worker_roots,
        )
        self._mappings_by_profile[profile] = mapping
        return mapping

    def _run_docker(self, label: str, argv: list[str], receipt_root: Path) -> dict[str, Any]:
        observation = _command_observation(
            argv,
            cwd=self.neutral_cwd,
            timeout_seconds=self.command_timeout_seconds,
            runner=self.command_runner,
        )
        row = {"label": label, **observation}
        command_root = receipt_root / "driver-commands"
        command_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        safe_label = re.sub(r"[^a-z0-9-]+", "-", label.lower()).strip("-")
        path = command_root / f"{len(self.command_rows):02d}-{safe_label}.json"
        receipt_sha = _write_exclusive_json(path, row)
        returned = {**row, "receipt_ref": {"path": str(path), "sha256": receipt_sha}}
        self.command_rows.append(returned)
        return returned

    def run_linux_partition(self, partition: dict[str, Any]) -> Path:
        """Execute the actual create/start/inspect/finalize/launch worker route."""
        mapping = self._profile_mount_map(partition)
        profile = partition["profile"]
        prepared = self.partition.prepare_worker_profile_mounts(
            self.plan,
            profile=profile,
            source_root=self.source_root,
            mount_map=mapping,
            runtime_contract=self.runtime,
            split_consumer_path=self.bundle.source_dir / "split_consumer.py",
            partition_runner_path=(self.bundle.source_dir / "profile_partition_runner.py"),
            worker_mounts_path=self.bundle.source_dir / "worker_mounts.py",
            origin_gate_path=self.origin_gate_path,
        )
        self._prepared_by_profile[profile] = prepared
        receipt_root = Path(
            next(row["host_root"] for row in mapping["mounts"] if row["role"] == "receipts")
        )
        lifecycle: dict[str, Any] = {
            "schema": RUNTIME_SEQUENCE_SCHEMA,
            "source": self.plan["source"],
            "plan_sha256": self.plan["plan_sha256"],
            "profile": profile,
            "artifact_sha256": partition["artifact_sha256"],
            "node_ids_sha256": partition["node_ids_sha256"],
            "source_set_binding": self.source_set_binding,
            "mount_map_sha256": _sha256(_canonical_json_bytes(mapping)),
            "runtime_contract_sha256": _sha256(_canonical_json_bytes(self.runtime)),
            "runtime_binding_input": self.runtime_binding_identity,
            "execution_mode": self.command_execution_mode,
            "runtime_binding_status": (
                "operator_intent_requires_actual_inspect"
                if self.command_execution_mode == "live_subprocess"
                else "recorded_test_fixture_not_runtime"
            ),
            "worker_result_status": "not_launched",
            "commands": [],
        }
        try:
            # Every attempt owns a fresh, inspectable container identity.  The
            # plan/profile remain in the retained lifecycle record; the name
            # never doubles as an ownership or source-authority claim. The
            # pinned R7 worker helper accepts the bounded form ``e02-q2-*``.
            attempt_id = uuid.uuid4().hex
            name = f"e02-q2-{attempt_id}"
            lifecycle["attempt_id"] = attempt_id
            lifecycle["container_name"] = name
            create_argv = self.mounts.worker_container_create_argv(
                self.runtime,
                mapping,
                container_name=name,
                resource_limits=self.runtime["resources"],
            )
            create = self._run_docker("container-create", create_argv, receipt_root)
            lifecycle["commands"].append(create["receipt_ref"])
            create_stdout = _require_success(create, "Docker create")
            lines = create_stdout.splitlines()
            if len(lines) != 1 or _CONTAINER_ID_RE.fullmatch(lines[0].strip()) is None:
                raise WorkerHostDriverError("Docker create did not return one full container ID")
            container_id = lines[0].strip()
            lifecycle["container_id"] = container_id

            start_argv = [
                "docker",
                "--config",
                self.runtime["docker"]["config_path"],
                "--context",
                self.runtime["docker"]["context"],
                "start",
                container_id,
            ]
            start = self._run_docker("container-start", start_argv, receipt_root)
            lifecycle["commands"].append(start["receipt_ref"])
            if _require_success(start, "Docker start").strip() != container_id:
                raise WorkerHostDriverError("Docker start returned another container identity")

            inspect_rows: list[dict[str, Any]] = []
            for command in self.mounts.worker_container_inspect_argv(self.runtime, container_id):
                field = command["field"]
                observed = self._run_docker(
                    f"container-inspect-{field}", command["argv"], receipt_root
                )
                lifecycle["commands"].append(observed["receipt_ref"])
                if observed["timed_out"] is not False:
                    raise WorkerHostDriverError(f"Docker inspect timed out for {field}")
                inspect_rows.append(
                    {
                        **command,
                        "returncode": observed["returncode"],
                        "stdout": observed["stdout"],
                        "stderr": observed["stderr"],
                    }
                )
            inspect_receipt = {
                "schema": "policyos.e02.q2.worker-container-inspect.v1",
                "commands": inspect_rows,
            }
            identity = self.mounts.validate_worker_container_inspect_receipt(
                inspect_receipt,
                self.runtime,
                mapping,
                expected_container_id=container_id,
            )
            lifecycle["runtime_binding_status"] = (
                "measured_by_fresh_field_limited_inspect"
                if self.command_execution_mode == "live_subprocess"
                else "recorded_test_fixture_not_runtime"
            )
            lifecycle["inspected_identity"] = identity

            bundle = self.partition.finalize_worker_profile_request(
                self.plan,
                prepared,
                profile=profile,
                runtime_contract=self.runtime,
                container_inspect_receipt=inspect_receipt,
                expected_container_id=container_id,
                mount_map=mapping,
                request_relative_path=f"requests/{profile}.json",
                receipt_relative_path=f"results/{profile}/primary-result.json",
                entrypoint_name="ukraine-data",
            )
            lifecycle["request_sha256"] = bundle["request_sha256"]
            result_path = self.partition.launch_worker_profile_partition(
                bundle,
                timeout_seconds=self.launch_timeout_seconds,
            )
            expected_result = Path(bundle["expected_output_host_path"])
            if (
                result_path != expected_result
                or result_path.is_symlink()
                or not result_path.is_file()
            ):
                raise WorkerHostDriverError("worker launch returned an unexpected result path")
            result_raw = _regular_bytes(result_path, "worker execution result")
            result = json.loads(result_raw)
            if (
                result.get("source") != self.plan["source"]
                or result.get("plan_sha256") != self.plan["plan_sha256"]
                or result.get("profile") != profile
                or result.get("artifact_sha256") != partition["artifact_sha256"]
                or result.get("executor") != "linux-worker"
            ):
                raise WorkerHostDriverError("launched worker result differs from its selected plan")
            lifecycle["worker_result_status"] = (
                "returned_for_common_reconciliation"
                if self.command_execution_mode == "live_subprocess"
                else "fixture_result_not_runtime"
            )
            lifecycle["worker_result"] = {
                "path": str(result_path),
                "bytes": len(result_raw),
                "sha256": _sha256(result_raw),
                "request_sha256": bundle["request_sha256"],
            }
            lifecycle["host_launch_path"] = str(result_path.parent / "host-launch.json")
            lifecycle["host_launch_sha256"] = _sha256(
                _regular_bytes(result_path.parent / "host-launch.json", "worker launch receipt")
            )
            return result_path
        finally:
            container_id = lifecycle.get("container_id")
            active_error = sys.exc_info()[1]
            stop_command_status = "not_created_or_no_verified_full_id"
            stop_failure: dict[str, Any] | None = None
            post_stop_inspection: dict[str, Any] = {
                "status": "unknown",
                "container_id_observed": None,
                "state_running_observed": None,
                "commands": [],
            }
            if type(container_id) is str and _CONTAINER_ID_RE.fullmatch(container_id):
                stop_argv = [
                    "docker",
                    "--config",
                    self.runtime["docker"]["config_path"],
                    "--context",
                    self.runtime["docker"]["context"],
                    "stop",
                    "--time",
                    "10",
                    container_id,
                ]
                try:
                    stopped = self._run_docker("container-stop-owned", stop_argv, receipt_root)
                    lifecycle["commands"].append(stopped["receipt_ref"])
                    if stopped.get("timed_out") is not False or stopped.get("returncode") != 0:
                        stop_command_status = "failed"
                        stop_failure = {
                            "returncode": stopped.get("returncode"),
                            "timed_out": stopped.get("timed_out"),
                        }
                    else:
                        stop_command_status = "succeeded_for_exact_owned_container_id"
                except BaseException as error:
                    stop_command_status = "command_error"
                    stop_failure = {
                        "exception_type": type(error).__name__,
                        "message": str(error),
                    }
                observed_fields: dict[str, str] = {}
                inspection_errors: list[dict[str, str]] = []
                try:
                    inspect_rows = {
                        row["field"]: row
                        for row in self.mounts.worker_container_inspect_argv(
                            self.runtime, container_id
                        )
                        if row["field"] in {"Id", "State.Running"}
                    }
                except BaseException as error:
                    inspect_rows = {}
                    inspection_errors.append(
                        {
                            "field": "command-construction",
                            "exception_type": type(error).__name__,
                            "message": str(error),
                        }
                    )
                for field in ("Id", "State.Running"):
                    if field not in inspect_rows:
                        inspection_errors.append(
                            {
                                "field": field,
                                "exception_type": "MissingCommand",
                                "message": "",
                            }
                        )
                        continue
                    command = inspect_rows[field]
                    try:
                        observed = self._run_docker(
                            f"container-post-stop-inspect-{field}",
                            command["argv"],
                            receipt_root,
                        )
                        lifecycle["commands"].append(observed["receipt_ref"])
                        post_stop_inspection["commands"].append(observed["receipt_ref"])
                        if (
                            observed.get("timed_out") is False
                            and observed.get("returncode") == 0
                            and type(observed.get("stdout")) is str
                        ):
                            observed_fields[field] = observed["stdout"].strip()
                    except BaseException as error:
                        inspection_errors.append(
                            {
                                "field": field,
                                "exception_type": type(error).__name__,
                                "message": str(error),
                            }
                        )
                observed_id = observed_fields.get("Id")
                observed_running = observed_fields.get("State.Running")
                post_stop_inspection["container_id_observed"] = observed_id
                post_stop_inspection["state_running_observed"] = observed_running
                if inspection_errors:
                    post_stop_inspection["errors"] = inspection_errors
                if set(observed_fields) != {"Id", "State.Running"}:
                    post_stop_inspection["status"] = "unknown"
                elif observed_id != container_id:
                    post_stop_inspection["status"] = "identity_mismatch"
                elif observed_running == "true":
                    post_stop_inspection["status"] = "still_running"
                elif observed_running == "false":
                    post_stop_inspection["status"] = "verified_not_running"
                else:
                    post_stop_inspection["status"] = "unknown"

            cleanup_status = "unknown"
            if post_stop_inspection["status"] == "still_running":
                cleanup_status = "still_running"
            elif post_stop_inspection["status"] == "identity_mismatch":
                cleanup_status = "identity_mismatch"
            elif post_stop_inspection["status"] == "verified_not_running":
                cleanup_status = (
                    "stopped_and_verified"
                    if stop_command_status == "succeeded_for_exact_owned_container_id"
                    else "stop_command_failed_state_not_running"
                )
            lifecycle["stop_command_status"] = stop_command_status
            lifecycle["stop_failure"] = stop_failure
            lifecycle["post_stop_inspection"] = post_stop_inspection
            lifecycle["cleanup_status"] = cleanup_status
            sequence_path = receipt_root / "host-driver-sequence.json"
            lifecycle["command_count"] = len(lifecycle["commands"])
            lifecycle["complete"] = (
                lifecycle["worker_result_status"]
                in {
                    "returned_for_common_reconciliation",
                    "fixture_result_not_runtime",
                }
                and cleanup_status == "stopped_and_verified"
            )
            sequence_sha256 = _write_exclusive_json(sequence_path, lifecycle)
            self._sequence_refs_by_profile[profile] = {
                "path": str(sequence_path),
                "sha256": sequence_sha256,
            }
            if cleanup_status != "stopped_and_verified" and active_error is None:
                raise WorkerHostDriverError(
                    "owned worker container cleanup was not verified "
                    f"({cleanup_status}); lifecycle evidence retained"
                )

    def execute(
        self,
        *,
        run_host_partition: Callable[[dict[str, Any]], str | Path],
        run_supplemental_partition: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Run six source-selected primary partitions and release six supplementals."""
        execution = self.composite.execute_composite_plan_with_worker(
            self.plan,
            run_host_partition=run_host_partition,
            run_linux_worker_partition=self.run_linux_partition,
            run_supplemental_partition=run_supplemental_partition,
        )
        path = self.output_root / "composite-execution.json"
        if execution.get("schema") != "policyos.e02.q2.composite-execution-receipt.v1":
            raise WorkerHostDriverError("common composite executor returned an unknown receipt")
        if set(self._sequence_refs_by_profile) != set(self.plan["profiles"]):
            raise WorkerHostDriverError(
                "common executor returned without one stopped-container record per profile"
            )
        lifecycle_rows: list[dict[str, Any]] = []
        for profile in self.plan["profiles"]:
            reference = self._sequence_refs_by_profile[profile]
            sequence_path = Path(reference["path"])
            raw = _regular_bytes(sequence_path, "retained worker lifecycle sequence")
            if _sha256(raw) != reference["sha256"]:
                raise WorkerHostDriverError(
                    "worker lifecycle sequence changed before reconciliation"
                )
            try:
                sequence = json.loads(raw)
            except json.JSONDecodeError as error:
                raise WorkerHostDriverError("worker lifecycle sequence is invalid JSON") from error
            expected_worker_result = (
                "returned_for_common_reconciliation"
                if self.command_execution_mode == "live_subprocess"
                else "fixture_result_not_runtime"
            )
            if (
                type(sequence) is not dict
                or sequence.get("profile") != profile
                or sequence.get("complete") is not True
                or sequence.get("stop_command_status") != "succeeded_for_exact_owned_container_id"
                or sequence.get("post_stop_inspection", {}).get("status") != "verified_not_running"
                or sequence.get("cleanup_status") != "stopped_and_verified"
                or sequence.get("execution_mode") != self.command_execution_mode
                or sequence.get("worker_result_status") != expected_worker_result
            ):
                raise WorkerHostDriverError(
                    "worker lifecycle sequence is not complete for its selected profile"
                )
            lifecycle_rows.append(
                {
                    "profile": profile,
                    "container_id": sequence["container_id"],
                    "attempt_id": sequence["attempt_id"],
                    "stop_command_status": sequence["stop_command_status"],
                    "post_stop_inspection_status": sequence["post_stop_inspection"]["status"],
                    "cleanup_status": sequence["cleanup_status"],
                    "sequence": {
                        "path": sequence_path.relative_to(self.output_root).as_posix(),
                        "sha256": reference["sha256"],
                    },
                }
            )
        persisted = {
            "schema": "policyos.e02.q2.worker-host-driver-composite-receipt.v1",
            "source": execution["source"],
            "plan_sha256": execution["plan_sha256"],
            "source_set_binding": self.source_set_binding,
            "worker_runtime_binding_input": self.runtime_binding_identity,
            "primary": [
                execution["primary"][(profile, executor)]
                for profile in self.plan["profiles"]
                for executor in ("host", "linux-worker")
            ],
            "barrier": execution["barrier"],
            "supplemental": execution["supplemental"],
            "worker_lifecycle": lifecycle_rows,
        }
        receipt_sha = _write_exclusive_json(path, persisted)
        return {
            "execution_mode": self.command_execution_mode,
            "receipt": execution,
            "persisted_receipt": persisted,
            "receipt_path": str(path),
            "receipt_sha256": receipt_sha,
        }
