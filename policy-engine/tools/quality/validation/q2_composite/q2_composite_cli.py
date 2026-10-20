"""Launch the source-bound Q2 host/Linux profile composite from an R6 receipt.

The command verifies the actual R6 build/transfer receipt, recomputes the R7
composite plan from its source inputs, constructs the concrete host and worker
consumers, and routes all callbacks through R7's common primary barrier. It
does not build or install dependencies; host profile installs are offline,
wheel-only consumer actions performed by the selected executor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from . import worker_host_driver as worker_host_driver_module
from .host_profile_executor import (
    HostProfileExecutor,
    SupplementalProfileExecutor,
)
from .worker_host_driver import (
    SourceBundle,
    WorkerHostDriver,
    load_composed_source_bundle,
)

HERE = Path(__file__).resolve().parent
RAW_RELATIVE = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw"
)
R6_MANIFEST_SHA256 = "5e9aa6be859c6237d1a4a335d73688326737b20480f9d7e1720195a7a2ae884e"
R6_MEMBER_HASHES = {
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q2-split-candidate-r6-20261020/split_protocol.py": (
        "0e94c5c038486d9d2610d60f7025ea1c00b7c211906971b971ddfc93bc8c9c41"
    ),
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q2-split-candidate-r6-20261020/split_source_runner.py": (
        "2ed80b38dcc526a3023bce28798b75f72407750aad3c8114a49142b315c912b4"
    ),
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q2-split-candidate-r6-20261020/split_consumer.py": (
        "e7ff32ad0bd88f39e21e854e10cdddd6ca1e54216a14f88f4dc180c1c9095bd1"
    ),
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q2-split-candidate-r6-20261020/test_split_protocol.py": (
        "607d9a97b763f604e2a3e872bebf117ea24365780e337cad7658f33a5c5666d1"
    ),
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q2-split-candidate-r6-20261020/hatch_sdist_selection.py": (
        "f56ad5d92c9056aa52d081b72c1e339bff926e6704b468700f4f288a8003becc"
    ),
}
Q2_RUNNER_RELATIVE = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py"
)
SUPPLEMENTAL_RUNNER_RELATIVE = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
    "q2-packaging/raw/supplemental_run.py"
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE_RE = re.compile(r"[0-9a-f]{40}\Z")
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
R6_REQUEST_SCHEMA = "policyos.e02.q2.split-consumer-request.v2"
COMPOSITE_RECEIPT_SCHEMA = "policyos.e02.q2.profile-composite-run-receipt.v2"


class CompositeCLIError(RuntimeError):
    """Raised when the source-bound Q2 composite cannot be admitted or run."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _raw_root(repo_root: Path) -> Path:
    return repo_root / RAW_RELATIVE


def _repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() and (candidate / "policy-engine").is_dir():
            return candidate
    raise CompositeCLIError("Q2 coordinator cannot locate its source repository")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _git_source_identity(repo: Path) -> dict[str, str]:
    """Read the selected worktree's current commit and tree from local Git."""
    identity: dict[str, str] = {}
    for label, revision in (("commit", "HEAD^{commit}"), ("tree", "HEAD^{tree}")):
        try:
            result = subprocess.run(  # noqa: S603 -- fixed local Git read-only invocation.
                ["/usr/bin/git", "-C", str(repo), "rev-parse", "--verify", revision],
                cwd=repo,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise CompositeCLIError(
                "selected source identity cannot be read from local Git"
            ) from error
        value = result.stdout.strip()
        if result.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise CompositeCLIError("selected source identity returned an invalid Git object ID")
        identity[label] = value
    return identity


def _read_regular(path: Path, label: str) -> bytes:
    if not path.is_absolute():
        raise CompositeCLIError(f"{label} path must be absolute: {path}")
    if any(component in {".", ".."} for component in path.parts[1:]):
        raise CompositeCLIError(f"{label} path is not canonical: {path}")
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current = current / component
        try:
            current.lstat()
        except OSError as error:
            raise CompositeCLIError(f"{label} path cannot be inspected: {current}") from error
        if current.is_symlink():
            raise CompositeCLIError(f"{label} path traverses a symlink: {current}")
        if current == path and not current.is_file():
            raise CompositeCLIError(f"{label} must be a regular file: {path}")
        if current != path and not current.is_dir():
            raise CompositeCLIError(f"{label} parent is not a directory: {current}")
    try:
        if not path.is_file() or path.is_symlink():
            raise CompositeCLIError(f"{label} must be a regular file: {path}")
        return path.read_bytes()
    except OSError as error:
        raise CompositeCLIError(f"{label} cannot be read: {path}") from error


def _read_pinned_json(path: Path, sha256: str, label: str) -> dict[str, Any]:
    raw = _read_regular(path, label)
    if _sha256(raw) != sha256:
        raise CompositeCLIError(f"{label} differs from its external SHA-256 pin")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CompositeCLIError(f"{label} is not valid JSON") from error
    if type(value) is not dict:
        raise CompositeCLIError(f"{label} root must be an object")
    return value


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value or "\0" in value:
        raise CompositeCLIError(f"{label} is not a canonical relative POSIX path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise CompositeCLIError(f"{label} is not a canonical relative POSIX path")
    return path


def _pinned_relative_file(
    root: Path, relative: object, expected_sha256: object, label: str
) -> Path:
    rel = _safe_relative(relative, label)
    if type(expected_sha256) is not str or _SHA256_RE.fullmatch(expected_sha256) is None:
        raise CompositeCLIError(f"{label} hash is malformed")
    path = root.joinpath(*rel.parts)
    if _sha256(_read_regular(path, label)) != expected_sha256:
        raise CompositeCLIError(f"{label} differs from its declared SHA-256")
    return path


def verify_r6_source_members(repo_root: Path, *, source_bundle: SourceBundle) -> dict[str, str]:
    """Verify historical R6/R7 source receipts without importing their RAW code."""
    raw_root = _raw_root(repo_root)
    r6_root = raw_root / "q2-split-candidate-r6-20261020"
    r7_root = raw_root / "q2-split-candidate-r7-20261020"
    manifest_path = r6_root / "manifest-r6.json"
    manifest_raw = _read_regular(manifest_path, "R6 candidate manifest")
    if _sha256(manifest_raw) != R6_MANIFEST_SHA256:
        raise CompositeCLIError("R6 manifest differs from its frozen SHA-256")
    try:
        manifest = json.loads(manifest_raw)
    except json.JSONDecodeError as error:
        raise CompositeCLIError("R6 candidate manifest is not valid JSON") from error
    entries = manifest.get("source_file_set") if type(manifest) is dict else None
    if type(entries) is not list or len(entries) != len(R6_MEMBER_HASHES):
        raise CompositeCLIError("R6 source manifest has an incomplete member denominator")
    if (
        source_bundle.repo_root.resolve(strict=True) != repo_root.resolve(strict=True)
        or source_bundle.r6_root.resolve(strict=True) != r6_root.resolve(strict=True)
        or source_bundle.r7_root.resolve(strict=True) != r7_root.resolve(strict=True)
    ):
        raise CompositeCLIError("R6/R7 source bundle does not match the selected source roots")
    r7_manifest_path = source_bundle.r7_root / "manifest-r7-final-v3.json"
    r7_manifest_raw = _read_regular(r7_manifest_path, "R7 composed source manifest")
    if _sha256(r7_manifest_raw) != worker_host_driver_module.R7_MANIFEST_SHA256:
        raise CompositeCLIError("R7 manifest differs from its frozen source pin")
    try:
        r7_manifest = json.loads(r7_manifest_raw)
    except json.JSONDecodeError as error:
        raise CompositeCLIError("R7 composed source manifest is not valid JSON") from error
    _r7_manifest, r7_digest, _legacy_r7_digest = (
        worker_host_driver_module._verify_frozen_source_set(
            r7_manifest_raw,
            expected_manifest_sha256=worker_host_driver_module.R7_MANIFEST_SHA256,
            repository_root=repo_root,
            expected_file_count=11,
        )
    )
    if r7_digest != source_bundle.upstream_r7_source_set_sha256:
        raise CompositeCLIError("R7 provenance set differs from its historical source bytes")
    r7_source_set = r7_manifest.get("source_set") if type(r7_manifest) is dict else None
    r7_rows = r7_source_set.get("files") if type(r7_source_set) is dict else None
    if (
        type(r7_rows) is not list
        or r7_source_set.get("file_count") != len(r7_rows)
        or len(r7_rows) != 11
    ):
        raise CompositeCLIError("R7 composed source set has an incomplete denominator")
    r7_hashes: dict[str, str] = {}
    for row in r7_rows:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            raise CompositeCLIError("R7 composed source row has an unsupported shape")
        relative = _safe_relative(row["path"], "R7 composed source path")
        key = relative.as_posix()
        digest = row["sha256"]
        if (
            key in r7_hashes
            or type(row["bytes"]) is not int
            or row["bytes"] < 0
            or type(digest) is not str
            or _SHA256_RE.fullmatch(digest) is None
        ):
            raise CompositeCLIError("R7 composed source set has invalid or duplicate members")
        r7_hashes[key] = digest
    observed: dict[str, str] = {}
    for row in entries:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            raise CompositeCLIError("R6 source member row has an unsupported shape")
        relative = _safe_relative(row["path"], "R6 source member path")
        key = relative.as_posix()
        if key in observed or key not in R6_MEMBER_HASHES:
            raise CompositeCLIError("R6 source manifest has an unexpected or duplicate member")
        path = repo_root.joinpath(*relative.parts)
        raw = _read_regular(path, "R6/R7 composed source member")
        # The R6 row remains pinned as history. R7's complete, loaded source
        # set selects the current bytes for overlapping helper paths.
        selected_hash = r7_hashes.get(key, row["sha256"])
        if _sha256(raw) != selected_hash or row["sha256"] != R6_MEMBER_HASHES[key]:
            raise CompositeCLIError(
                f"R6/R7 composed source member differs from its selected bytes: {key}"
            )
        observed[key] = selected_hash
    if set(observed) != set(R6_MEMBER_HASHES):
        raise CompositeCLIError("R6 source manifest does not contain its complete pinned set")
    return observed


def implementation_source_bindings(
    repo_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Bind every tracked Q2 implementation and test member in the R10 set."""
    repo = (
        Path(repo_root).resolve(strict=True)
        if repo_root is not None
        else _repository_root(Path(__file__).resolve(strict=True))
    )
    manifest, _source_digest, _manifest_sha = worker_host_driver_module._canonical_source_rows(repo)
    observed: list[dict[str, Any]] = []
    for row in manifest["source_set"]["files"]:
        path = repo.joinpath(*PurePosixPath(row["path"]).parts)
        raw = _read_regular(path, "R10 selected source member")
        observed.append(
            {
                "path": str(path.resolve(strict=True)),
                "bytes": len(raw),
                "sha256": _sha256(raw),
            }
        )
    return observed


def build_plan_from_host_receipt(
    *,
    repo_root: str | Path,
    build_receipt_path: str | Path,
    build_receipt_sha256: str,
    expected_commit: str,
    expected_tree: str,
    source_bundle: SourceBundle,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recompute R7's plan from one exact R6 build/transfer receipt."""
    repo = Path(repo_root).resolve(strict=True)
    product = repo / "policy-engine"
    if not product.is_dir():
        raise CompositeCLIError("selected checkout has no policy-engine product root")
    if _SOURCE_RE.fullmatch(expected_commit) is None or _SOURCE_RE.fullmatch(expected_tree) is None:
        raise CompositeCLIError("expected source identity must contain exact Git SHA-1 values")
    verify_r6_source_members(repo, source_bundle=source_bundle)

    receipt_path = Path(build_receipt_path).resolve(strict=True)
    receipt = _read_pinned_json(receipt_path, build_receipt_sha256, "R6 host-build receipt")
    source = {"commit": expected_commit, "tree": expected_tree}
    if _git_source_identity(repo) != source:
        raise CompositeCLIError("selected checkout commit/tree differs from the R6 build source")
    if (
        receipt.get("schema") != "policyos.e02.q2.split-host-build-receipt.v1"
        or receipt.get("status") != "ready_for_independent_review_and_worker_admission"
        or receipt.get("source") != source
    ):
        raise CompositeCLIError("R6 host-build receipt is not the selected successful source build")

    transfer_receipt = receipt.get("artifacts", {}).get("transfer")
    if type(transfer_receipt) is not dict:
        raise CompositeCLIError("R6 receipt does not contain the worker transfer contract")
    request_path = Path(transfer_receipt.get("request_path", ""))
    if not request_path.is_absolute():
        raise CompositeCLIError("R6 transfer request path is not absolute")
    transfer_root = request_path.parent.resolve(strict=True)
    if transfer_receipt.get("directory") != str(transfer_root):
        raise CompositeCLIError("R6 transfer root differs from its producer receipt")
    request_raw = _read_regular(request_path, "R6 split-consumer request")
    request_sha256 = _sha256(request_raw)
    if request_sha256 != transfer_receipt.get("request_sha256"):
        raise CompositeCLIError("R6 split-consumer request differs from its producer SHA-256")
    try:
        request = json.loads(request_raw)
    except json.JSONDecodeError as error:
        raise CompositeCLIError("R6 split-consumer request is not valid JSON") from error
    if (
        type(request) is not dict
        or request.get("schema") != source_bundle.split_protocol.REQUEST_SCHEMA
        or request.get("schema") != R6_REQUEST_SCHEMA
        or request.get("source") != source
        or request.get("manifest_sha256") != receipt.get("manifest", {}).get("sha256")
    ):
        raise CompositeCLIError("R6 split-consumer request is not bound to the selected source")

    profiles = list(source_bundle.composite.PROFILE_CHAIN_KEYS)
    artifacts_request = request.get("artifacts")
    if (
        type(artifacts_request) is not list
        or [row.get("profile") if type(row) is dict else None for row in artifacts_request]
        != profiles
    ):
        raise CompositeCLIError("R6 request does not carry the complete ordered profile artifacts")
    artifact_rows: list[dict[str, Any]] = []
    artifact_by_profile: dict[str, dict[str, Any]] = {}
    for row in artifacts_request:
        if type(row) is not dict or set(row) != {
            "profile",
            "chain_key",
            "file",
            "bytes",
            "sha256",
        }:
            raise CompositeCLIError("R6 profile artifact row has an unsupported shape")
        profile = row["profile"]
        expected_chain_key = source_bundle.composite.PROFILE_CHAIN_KEYS.get(profile)
        relative = _safe_relative(row["file"], f"{profile} transfer artifact")
        if row["chain_key"] != expected_chain_key or not str(relative).startswith(
            f"wheels/{profile}/"
        ):
            raise CompositeCLIError(f"{profile} artifact does not match its producer profile")
        wheel_path = transfer_root.joinpath(*relative.parts)
        wheel_raw = _read_regular(wheel_path, f"{profile} source-derived wheel")
        if (
            type(row["bytes"]) is not int
            or row["bytes"] != len(wheel_raw)
            or type(row["sha256"]) is not str
            or _SHA256_RE.fullmatch(row["sha256"]) is None
            or _sha256(wheel_raw) != row["sha256"]
        ):
            raise CompositeCLIError(f"{profile} wheel differs from its source producer row")
        artifact_by_profile[profile] = row
        artifact_rows.append(
            {
                "profile": profile,
                "chain_key": row["chain_key"],
                "path": str(wheel_path),
                "bytes": row["bytes"],
                "sha256": row["sha256"],
            }
        )

    chain = request.get("artifact_chain")
    if type(chain) is not dict or set(chain) != set(source_bundle.composite.ARTIFACT_CHAIN_KEYS):
        raise CompositeCLIError("R6 artifact lineage is not the complete admitted chain")
    for profile, chain_key in source_bundle.composite.PROFILE_CHAIN_KEYS.items():
        if chain.get(chain_key) != artifact_by_profile[profile]["sha256"]:
            raise CompositeCLIError(f"{profile} artifact differs from the R6 artifact chain")

    source_audit = request.get("source_audit")
    harness = request.get("harness")
    worker_profile = request.get("worker_profile")
    selection = request.get("consumer_selection")
    if any(type(value) is not dict for value in (source_audit, harness, worker_profile, selection)):
        raise CompositeCLIError("R6 request omits required source or consumer profile fields")

    def transfer_file(relative_value: object, expected: object, label: str) -> Path:
        return _pinned_relative_file(transfer_root, relative_value, expected, label)

    primary_ref = receipt.get("manifest")
    inventory_ref = receipt.get("source_package_inventory")
    if type(primary_ref) is not dict or type(inventory_ref) is not dict:
        raise CompositeCLIError("R6 producer receipt omits its manifest or source inventory")
    primary_path = Path(primary_ref.get("path", ""))
    if not primary_path.is_absolute():
        raise CompositeCLIError("R6 primary manifest path is not absolute")
    primary_raw = _read_regular(primary_path, "R6 primary source manifest")
    if _sha256(primary_raw) != primary_ref.get("sha256"):
        raise CompositeCLIError("R6 primary manifest differs from its producer receipt")
    try:
        primary_manifest = json.loads(primary_raw)
    except json.JSONDecodeError as error:
        raise CompositeCLIError("R6 primary source manifest is not valid JSON") from error
    source_map = primary_manifest.get("current_primary_suite", {}).get("source_file_sha256")
    if type(source_map) is not dict or not source_map:
        raise CompositeCLIError("R6 primary manifest omits its complete selected source closure")
    normalized_source_map = {str(key): value for key, value in sorted(source_map.items())}
    test_source_closure_sha256 = _sha256(_canonical_json_bytes(normalized_source_map))

    audit_path = transfer_file(
        source_audit.get("receipt_file"),
        source_audit.get("receipt_sha256"),
        "R6 source-audit receipt",
    )
    supplemental_manifest_path = transfer_file(
        source_audit.get("supplemental_manifest_file"),
        source_audit.get("supplemental_manifest_sha256"),
        "R6 supplemental manifest",
    )
    transfer_file(
        source_audit.get("supplemental_runner_file"),
        source_audit.get("supplemental_runner_sha256"),
        "R6 supplemental runner",
    )
    source_inventory_transfer = transfer_file(
        Path(transfer_receipt.get("inventory_path", "")).name,
        inventory_ref.get("sha256"),
        "R6 transfer source inventory",
    )
    if (
        Path(transfer_receipt.get("inventory_path", "")).parent.resolve(strict=True)
        != transfer_root
    ):
        raise CompositeCLIError("R6 inventory transfer path escapes its transfer root")
    inventory_path = Path(inventory_ref.get("path", ""))
    inventory_raw = _read_regular(inventory_path, "R6 source package inventory")
    if (
        _sha256(inventory_raw) != inventory_ref.get("sha256")
        or _read_regular(source_inventory_transfer, "transferred R6 source inventory")
        != inventory_raw
    ):
        raise CompositeCLIError("R6 complete source inventory differs across transfer boundary")
    try:
        source_inventory = json.loads(inventory_raw)
    except json.JSONDecodeError as error:
        raise CompositeCLIError("R6 source inventory is not valid JSON") from error
    if type(source_inventory) is not dict:
        raise CompositeCLIError("R6 source inventory root must be an object")
    try:
        source_bundle.split_protocol.validate_request_binding(
            request,
            primary_manifest,
            source_inventory,
            manifest_sha256=primary_ref["sha256"],
            inventory_sha256=inventory_ref["sha256"],
            expected_commit=expected_commit,
            expected_tree=expected_tree,
            wheel_paths={
                row["profile"]: transfer_root.joinpath(
                    *_safe_relative(row["file"], row["profile"]).parts
                )
                for row in artifacts_request
            },
        )
    except (KeyError, RuntimeError, ValueError) as error:
        raise CompositeCLIError(
            "R6 request does not pass the complete source/artifact/allocation binding"
        ) from error

    owner_path = Path(inventory_ref.get("runtime_owner_inventory_path", ""))
    owner_raw = _read_regular(owner_path, "R6 runtime resource-owner inventory")
    if _sha256(owner_raw) != inventory_ref.get("runtime_owner_inventory_sha256"):
        raise CompositeCLIError("R6 runtime owner inventory differs from its producer pin")

    manifest_transfer = transfer_file(
        Path(transfer_receipt.get("manifest_path", "")).name,
        primary_ref.get("sha256"),
        "transferred R6 primary manifest",
    )
    if Path(transfer_receipt.get("manifest_path", "")).parent.resolve(strict=True) != transfer_root:
        raise CompositeCLIError("R6 manifest transfer path escapes its transfer root")
    if _read_regular(manifest_transfer, "transferred R6 primary manifest") != primary_raw:
        raise CompositeCLIError("R6 primary manifest changed at its transfer boundary")
    q2_runner_path = product.joinpath(*PurePosixPath(Q2_RUNNER_RELATIVE).parts)
    build_profile_path = product / _safe_relative(
        harness.get("build_profile_relative"), "Q2 build profile"
    )
    dependency_profile_path = product / _safe_relative(
        worker_profile.get("dowhy_lock_relative"), "worker dependency lock"
    )
    consumer_runner_path = transfer_file(
        harness.get("consumer_file"),
        harness.get("consumer_sha256"),
        "R6 split consumer",
    )

    host_profile = receipt.get("host_profile")
    uv_binding = receipt.get("uv")
    if type(host_profile) is not dict or type(uv_binding) is not dict:
        raise CompositeCLIError("R6 producer receipt omits its host Python and locked uv inputs")
    app_python = Path(host_profile.get("executable", ""))
    dependency_site = Path(host_profile.get("purelib", ""))
    uv_path = Path(uv_binding.get("path", ""))
    if not all(path.is_absolute() for path in (app_python, dependency_site, uv_path)):
        raise CompositeCLIError("R6 host profile paths are not absolute")
    if _sha256(_read_regular(uv_path, "selected uv executable")) != uv_binding.get("sha256"):
        raise CompositeCLIError("selected uv executable differs from the R6 source-build receipt")
    if not app_python.is_file() or not dependency_site.is_dir():
        raise CompositeCLIError("selected host Python/dependency profile is no longer available")

    input_pins = {
        "primary_manifest_sha256": primary_ref.get("sha256"),
        "supplemental_manifest_sha256": source_audit.get("supplemental_manifest_sha256"),
        "source_audit_receipt_sha256": source_audit.get("receipt_sha256"),
        "source_inventory_sha256": inventory_ref.get("sha256"),
        "resource_owner_inventory_sha256": inventory_ref.get("runtime_owner_inventory_sha256"),
        "build_profile_sha256": harness.get("build_profile_sha256"),
        "consumer_runner_sha256": harness.get("consumer_sha256"),
        "supplemental_runner_sha256": source_audit.get("supplemental_runner_sha256"),
        "test_source_closure_sha256": test_source_closure_sha256,
        "dependency_profile_sha256": worker_profile.get("dowhy_lock_sha256"),
    }
    if set(input_pins) != set(source_bundle.composite.INPUT_PIN_KEYS) or any(
        type(value) is not str or _SHA256_RE.fullmatch(value) is None
        for value in input_pins.values()
    ):
        raise CompositeCLIError("R6 input pin map is incomplete or malformed")
    if not isinstance(selection.get("primary_node_ids"), list) or not isinstance(
        selection.get("supplemental_node_ids"), list
    ):
        raise CompositeCLIError("R6 consumer selector denominator is malformed")

    plan = source_bundle.composite.create_composite_plan(
        source=source,
        input_pins=input_pins,
        expected_artifact_chain=chain,
        artifacts=artifact_rows,
        product_root=product,
        primary_manifest_path=primary_path,
        supplemental_manifest_path=supplemental_manifest_path,
        source_audit_receipt_path=audit_path,
        source_inventory_path=source_inventory_transfer,
        owner_inventory_path=owner_path,
        build_profile_path=build_profile_path,
        consumer_runner_path=consumer_runner_path,
        dependency_profile_path=dependency_profile_path,
        expected_primary_count=len(selection["primary_node_ids"]),
        expected_supplemental_count=len(selection["supplemental_node_ids"]),
    )
    if plan["source_inputs"]["canonical_q2_runner"]["path"] != str(q2_runner_path) or plan[
        "source_inputs"
    ]["canonical_supplemental_runner"]["path"] != str(
        product.joinpath(*PurePosixPath(SUPPLEMENTAL_RUNNER_RELATIVE).parts)
    ):
        raise CompositeCLIError("R7 recomputation did not bind current canonical runner paths")
    metadata = {
        "schema": "policyos.e02.q2.r9-admission.v1",
        "host_build_receipt": {
            "path": str(receipt_path),
            "sha256": build_receipt_sha256,
        },
        "r6_transfer_request": {
            "path": str(request_path),
            "sha256": request_sha256,
        },
        "source": source,
        "input_pins": input_pins,
        "host_profile": {
            "python": str(app_python),
            "purelib": str(dependency_site),
            "uv": str(uv_path),
            "uv_sha256": uv_binding["sha256"],
        },
        "plan_sha256": plan["plan_sha256"],
        "primary_denominator": plan["primary"],
        "supplemental_denominator": plan["supplemental"],
    }
    return plan, {"receipt": receipt, "request": request, "metadata": metadata}


def execute_composite_plan(
    *,
    plan: dict[str, Any],
    worker_driver: WorkerHostDriver,
    host_executor: HostProfileExecutor,
    supplemental_executor: SupplementalProfileExecutor,
) -> dict[str, Any]:
    """Connect the selected plan to its real host, Linux and supplemental consumers."""
    if (
        worker_driver.plan.get("plan_sha256") != plan.get("plan_sha256")
        or host_executor.plan.get("plan_sha256") != plan.get("plan_sha256")
        or supplemental_executor.plan.get("plan_sha256") != plan.get("plan_sha256")
        or supplemental_executor.host is not host_executor
    ):
        raise CompositeCLIError("composite callers do not share one recomputed source-bound plan")
    result = worker_driver.execute(
        run_host_partition=host_executor.run_partition,
        run_supplemental_partition=supplemental_executor.run_profile,
    )
    execution = result.get("receipt")
    if type(execution) is not dict:
        raise CompositeCLIError("R7 common executor did not return a composite receipt")
    expected_primary = {
        (profile, executor) for profile in plan["profiles"] for executor in ("host", "linux-worker")
    }
    primary = execution.get("primary")
    if type(primary) is not dict or set(primary) != expected_primary:
        raise CompositeCLIError("composite run did not reconcile all six primary partitions")
    barrier = execution.get("barrier")
    if (
        type(barrier) is not dict
        or barrier.get("status") != "primary_profiles_complete"
        or barrier.get("execution_row_count") != len(expected_primary)
    ):
        raise CompositeCLIError("composite run did not satisfy the complete primary barrier")
    supplemental = execution.get("supplemental")
    if type(supplemental) is not dict or set(supplemental) != set(plan["profiles"]):
        raise CompositeCLIError("composite run did not execute all selected supplemental profiles")
    if set(supplemental_executor.completed) != set(plan["profiles"]):
        raise CompositeCLIError("supplemental consumer did not attest every selected profile")
    return result


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
    if _read_regular(path, "Q2 composite execution receipt") != raw:
        raise CompositeCLIError("composite execution receipt readback differs")
    return _sha256(raw)


def run_composite(
    *,
    repo_root: str | Path,
    build_receipt_path: str | Path,
    build_receipt_sha256: str,
    expected_commit: str,
    expected_tree: str,
    output_root: str | Path,
    state_parent: str | Path,
) -> Path:
    """Run the complete selected primary and supplemental Q2 consumer flow."""
    repo = Path(repo_root).resolve(strict=True)
    product = repo / "policy-engine"
    raw_root = _raw_root(repo)
    state_root = Path(state_parent).resolve(strict=True)
    if not state_root.is_dir() or state_root == repo or repo in state_root.parents:
        raise CompositeCLIError(
            "worker neutral state parent must be an existing external directory"
        )
    output = Path(output_root).absolute()
    expected_parent = raw_root / "q2-composite-r10" / "runs"
    if output.parent != expected_parent or _TOKEN_RE.fullmatch(output.name) is None:
        raise CompositeCLIError("output must be a unique named child of the R9 runs directory")
    if output.exists() or output.is_symlink():
        raise CompositeCLIError("composite output directory must be fresh")
    expected_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if expected_parent.is_symlink() or not expected_parent.is_dir():
        raise CompositeCLIError("composite output parent must be a real directory")
    output.mkdir(mode=0o700, exist_ok=False)

    attempt_id = uuid.uuid4().hex
    attempt_state = state_root / f"e02-q2-r10-{attempt_id}"
    neutral_cwd = attempt_state / "neutral-cwd"
    start_path = output / "composite-run-start.json"
    receipt_path = output / "composite-run-receipt.json"
    implementation_bindings = implementation_source_bindings(repo)
    receipt: dict[str, Any] = {
        "schema": COMPOSITE_RECEIPT_SCHEMA,
        "status": "running",
        "attempt_id": attempt_id,
        "started_utc": datetime.now(UTC).isoformat(),
        "source_expected": {"commit": expected_commit, "tree": expected_tree},
        "r10_composed_source_bindings": implementation_bindings,
        "host_build_receipt": {
            "path": str(Path(build_receipt_path).absolute()),
            "sha256": build_receipt_sha256,
        },
        "output_root": str(output),
        "neutral_state": {
            "path": str(attempt_state),
            "neutral_cwd": str(neutral_cwd),
            "retention": "retained; no temporary data is deleted by the coordinator",
        },
        "runtime_status": (
            "pending; source authoring did not execute Docker, builds, installs, or consumers"
        ),
    }
    _write_exclusive_json(start_path, receipt)
    try:
        attempt_state.mkdir(mode=0o700, exist_ok=False)
        neutral_cwd.mkdir(mode=0o700, exist_ok=False)
        # R7 is the composed helper source set; verify it before allowing its
        # manifest to supersede any overlapping R6 source member.
        bundle = load_composed_source_bundle(repo, raw_root)
        verify_r6_source_members(repo, source_bundle=bundle)
        if _git_source_identity(repo) != {
            "commit": expected_commit,
            "tree": expected_tree,
        }:
            raise CompositeCLIError(
                "selected checkout commit/tree differs from the R6 build source"
            )
        plan, admission = build_plan_from_host_receipt(
            repo_root=repo,
            build_receipt_path=build_receipt_path,
            build_receipt_sha256=build_receipt_sha256,
            expected_commit=expected_commit,
            expected_tree=expected_tree,
            source_bundle=bundle,
        )
        plan_path = output / "composite-plan.json"
        plan_sha = _write_exclusive_json(plan_path, plan)
        host_profile = admission["receipt"]["host_profile"]
        uv = admission["receipt"]["uv"]
        gate_path = product / "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
        gate_path = gate_path / "q2-packaging/raw/installed_origin_gate_r4.py"
        gate_sha = bundle.split_consumer._raw_sha256(
            bundle.split_consumer._read_regular(gate_path, "R6 installed-origin gate")
        )
        transfer_request = admission["request"]
        if gate_sha != transfer_request.get("harness", {}).get("installed_origin_gate_sha256"):
            raise CompositeCLIError(
                "installed-origin gate differs from the exact R6 transfer request"
            )

        host_executor = HostProfileExecutor(
            plan=plan,
            source_bundle=bundle,
            source_root=repo,
            product_root=product,
            app_python=Path(host_profile["executable"]),
            uv=Path(uv["path"]),
            dependency_site=Path(host_profile["purelib"]),
            output_root=output / "host",
        )
        supplemental_executor = SupplementalProfileExecutor(host_executor)
        worker_driver = WorkerHostDriver(
            plan=plan,
            runtime_contract=None,
            source_bundle=bundle,
            source_root=repo,
            output_root=output / "worker-driver",
            origin_gate_path=gate_path,
            neutral_cwd=neutral_cwd,
        )
        execution = execute_composite_plan(
            plan=plan,
            worker_driver=worker_driver,
            host_executor=host_executor,
            supplemental_executor=supplemental_executor,
        )
        if _git_source_identity(repo) != {
            "commit": expected_commit,
            "tree": expected_tree,
        }:
            raise CompositeCLIError("selected Git source identity changed during Q2 composition")
        if implementation_source_bindings(repo) != implementation_bindings:
            raise CompositeCLIError("R10 composed source changed during this run")
        receipt.update(
            {
                "status": "complete",
                "finished_utc": datetime.now(UTC).isoformat(),
                "runtime_status": (
                    "physical_subprocess_result_recorded"
                    if execution["execution_mode"] == "live_subprocess"
                    else "controlled_test_adapter_only"
                ),
                "admission": admission["metadata"],
                "plan": {"path": str(plan_path), "sha256": plan_sha},
                "execution": {
                    "path": execution["receipt_path"],
                    "sha256": execution["receipt_sha256"],
                    "execution_mode": execution["execution_mode"],
                },
                "formal_status": {
                    "closure_ids": [],
                    "g_acceptance": "not_claimed",
                    "physical_runtime": execution["execution_mode"],
                },
            }
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as error:
        receipt.update(
            {
                "status": "failed",
                "finished_utc": datetime.now(UTC).isoformat(),
                "failure": {"type": type(error).__name__, "message": str(error)},
                "formal_status": {"closure_ids": [], "g_acceptance": "not_claimed"},
            }
        )
        _write_exclusive_json(receipt_path, receipt)
        raise
    _write_exclusive_json(receipt_path, receipt)
    return receipt_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--build-receipt", required=True, type=Path)
    parser.add_argument("--build-receipt-sha256", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-source-tree", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--state-parent", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        receipt_path = run_composite(
            repo_root=args.repo,
            build_receipt_path=args.build_receipt,
            build_receipt_sha256=args.build_receipt_sha256,
            expected_commit=args.expected_source_commit,
            expected_tree=args.expected_source_tree,
            output_root=args.output_root,
            state_parent=args.state_parent,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as error:
        sys.stderr.write(f"Q2 composite coordinator failed: {type(error).__name__}: {error}\n")
        return 1
    sys.stdout.write(f"Q2 composite coordinator retained receipt: {receipt_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
