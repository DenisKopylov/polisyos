#!/usr/bin/env python3
"""Lightweight synthetic tests for Q2 adaptive timeout binding."""

from __future__ import annotations

import hashlib
import importlib.resources
import importlib.util
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    from types import ModuleType


import pytest
from defusedxml import ElementTree as SafeET


def _git_executable() -> str:
    """Resolve Git once per process without relying on a partial PATH command."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is not available on PATH")
    return str(Path(executable).resolve(strict=True))


def _run_test_process(
    argv: list[str],
    *,
    check: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run only Git metadata or a source-local Python control without a shell."""
    if not argv or argv[0] not in {_git_executable(), sys.executable}:
        raise RuntimeError("test child executable is outside the Git/Python allowlist")
    # S603: fixed absolute Git/Python executables, explicit argv, no shell, and local test source.
    return subprocess.run(  # noqa: S603
        argv,
        capture_output=True,
        check=check,
        text=True,
        timeout=timeout,
        shell=False,
    )


HERE = Path(__file__).resolve().parent
PRODUCT_ROOT = HERE.parents[6]
REPO_ROOT = PRODUCT_ROOT.parent
RESOURCE_CONTRACT_PATH = PRODUCT_ROOT / "tools/quality/validation/packaged_resource_contract.py"


def _task_temp_root() -> Path:
    """Resolve the explicit task temp root, honoring TMPDIR and never using source paths."""
    configured = os.environ.get("TMPDIR")
    root = Path(configured) if configured else Path(tempfile.gettempdir())
    if not root.is_absolute():
        raise RuntimeError("Q2 test TMPDIR must be an absolute path")
    try:
        root.mkdir(parents=True, exist_ok=True)
        resolved = root.resolve(strict=True)
    except OSError as error:
        raise RuntimeError(f"Q2 test TMPDIR is not available: {root}") from error
    if not resolved.is_dir():
        raise RuntimeError(f"Q2 test TMPDIR is not a directory: {resolved}")
    return resolved


def _new_harness_output_dir(prefix: str) -> Path:
    """Create a private, retained harness output directory below TMPDIR."""
    return Path(tempfile.mkdtemp(prefix=prefix, dir=_task_temp_root()))


def _flatten_owner_groups(owners: Any) -> list[dict[str, Any]]:
    """Flatten every declared runtime owner group without enumerating group names."""
    if not isinstance(owners, dict) or not owners:
        raise AssertionError("runtime owner inventory must be a nonempty mapping")
    rows: list[dict[str, Any]] = []
    for name, group in owners.items():
        if isinstance(group, list):
            group_rows = group
        elif isinstance(group, dict):
            group_rows = [group]
        else:
            raise AssertionError(f"runtime owner group {name!r} must be a list or one row")
        for row in group_rows:
            if not isinstance(row, dict):
                raise AssertionError(f"runtime owner group {name!r} contains a non-object row")
            if not isinstance(row.get("source"), str) or not isinstance(row.get("wheel"), str):
                raise AssertionError(f"runtime owner group {name!r} lacks source/wheel bindings")
            rows.append(row)
    return rows
spec = importlib.util.spec_from_file_location(
    "q2_timeout_driver_under_test", HERE / "timeout_driver.py"
)
driver = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(driver)
TERMINAL_EVIDENCE_RECEIPTS: dict[str, Any] = {}


def _load_sibling_module(module_name: str, path: Path) -> ModuleType:
    sibling_spec = importlib.util.spec_from_file_location(module_name, path)
    if sibling_spec is None or sibling_spec.loader is None:
        raise RuntimeError(f"cannot load Q2 test module: {path}")
    sibling = importlib.util.module_from_spec(sibling_spec)
    sibling_spec.loader.exec_module(sibling)
    return sibling


runner_api = _load_sibling_module("q2_primary_runner_under_test", HERE / "run.py")
resource_contract_api = _load_sibling_module(
    "q2_packaged_resource_contract_under_test", RESOURCE_CONTRACT_PATH
)
supplemental_api = _load_sibling_module(
    "q2_supplemental_runner_under_test", HERE / "supplemental_run.py"
)
audit_api = _load_sibling_module(
    "q2_source_audit_under_test", HERE / "q2-freeze-input-audit-v2-20261011.py"
)


def _current_audit_binding(repo: Path) -> tuple[str, dict[str, Any], dict[str, Any]]:
    source_sha = _run_test_process(
        [_git_executable(), "-C", str(repo), "rev-parse", "HEAD"]
    ).stdout.strip()
    helper_record = audit_api.bind_audit_helper(repo, source_sha)
    git_profile = audit_api.git_oracle_profile(repo)
    return source_sha, helper_record, git_profile


@pytest.fixture(scope="module")
def source_resource_inventory() -> dict[str, Any]:
    result = _run_test_process(
        [
            sys.executable,
            "-I",
            str(RESOURCE_CONTRACT_PATH),
            "source",
            "--product-root",
            str(PRODUCT_ROOT),
        ],
        check=False,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_source_resource_contract_derives_complete_set_from_runtime_owners(
    source_resource_inventory: dict[str, Any],
) -> None:
    inventory = source_resource_inventory
    owner_rows = _flatten_owner_groups(inventory["owners"])
    assets = inventory["assets"]
    owner_bindings = {(row["source"], row["wheel"]) for row in owner_rows}
    asset_bindings = {(row["source"], row["wheel"]) for row in assets}
    assert len(owner_rows) == len(owner_bindings)
    assert len(assets) == len(asset_bindings)
    assert asset_bindings == owner_bindings
    assert len({row["wheel"] for row in assets}) == len(assets)
    assert all(row["bytes"] >= 0 and len(row["sha256"]) == 64 for row in assets)


def test_owner_inventory_blocks_manifest_mapping_and_byte_omissions(
    source_resource_inventory: dict[str, Any],
) -> None:
    assets = source_resource_inventory["assets"]
    force_include = {row["source"]: row["wheel"] for row in assets}
    manifest_assets = [{**row, "archive": "policy-engine/" + row["source"]} for row in assets]
    resource_contract_api.validate_manifest_resources(
        source_resource_inventory, manifest_assets, force_include
    )

    with pytest.raises(resource_contract_api.ResourceContractError, match="runtime owners"):
        resource_contract_api.validate_manifest_resources(
            source_resource_inventory, manifest_assets[:-1], force_include
        )
    missing_target = dict(force_include)
    missing_target.pop(assets[-1]["source"])
    with pytest.raises(resource_contract_api.ResourceContractError, match="Hatch wheel mapping"):
        resource_contract_api.validate_manifest_resources(
            source_resource_inventory, manifest_assets, missing_target
        )
    tampered = [dict(row) for row in manifest_assets]
    tampered[-1]["sha256"] = "0" * 64
    with pytest.raises(resource_contract_api.ResourceContractError, match="byte bindings"):
        resource_contract_api.validate_manifest_resources(
            source_resource_inventory, tampered, force_include
        )
    malformed_digest = [dict(row) for row in manifest_assets]
    malformed_digest[-1]["sha256"] = "z" * 64
    with pytest.raises(
        resource_contract_api.ResourceContractError, match="byte binding is malformed"
    ):
        resource_contract_api.validate_manifest_resources(
            source_resource_inventory, malformed_digest, force_include
        )


def test_primary_runner_admits_only_the_owner_derived_source_resource_manifest(
    source_resource_inventory: dict[str, Any],
) -> None:
    assets = source_resource_inventory["assets"]
    sdist_include = set(
        tomllib.loads((PRODUCT_ROOT / "hatch.toml").read_text(encoding="utf-8"))["build"][
            "targets"
        ]["sdist"]["include"]
    )
    parent_selected_assets = [
        row
        for row in assets
        if any(row["source"].startswith(f"{entry.rstrip('/')}/") for entry in sdist_include)
    ]
    assert parent_selected_assets, "the source fixture must be selected through a Hatch directory"
    assert any(row["source"] not in sdist_include for row in parent_selected_assets)
    manifest = {
        "schema_version": 1,
        "candidate_baseline": {
            "force_include_count": len(assets),
            "force_include_assets": [
                {**row, "archive": f"policy-engine/{row['source']}"} for row in assets
            ],
        },
    }
    parsed, observed = runner_api.read_asset_manifest(
        PRODUCT_ROOT, manifest, source_resource_inventory
    )
    if parsed is not manifest or observed != manifest["candidate_baseline"]["force_include_assets"]:
        raise AssertionError("primary runner did not preserve the complete owner-derived manifest")

    counterfeit = json.loads(json.dumps(manifest))
    counterfeit["candidate_baseline"]["force_include_assets"][-1]["sha256"] = "0" * 64
    with pytest.raises(runner_api.WaveFailure, match="runtime-owned resource contract failed"):
        runner_api.read_asset_manifest(PRODUCT_ROOT, counterfeit, source_resource_inventory)


def test_importlib_resource_reader_rejects_missing_and_tampered_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "e02_q2_resource_fixture"
    resource = package / "assets" / "one.bin"
    resource.parent.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Resource API fixture."""\n', encoding="utf-8")
    payload = b"source-bound resource bytes\n"
    resource.write_bytes(payload)
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    row = {
        "source": "resources/one.bin",
        "wheel": "e02_q2_resource_fixture/assets/one.bin",
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    root = importlib.resources.files("e02_q2_resource_fixture")
    assert (
        resource_contract_api.verify_importlib_resource_bytes(
            root, "e02_q2_resource_fixture", [row]
        )[row["wheel"]]["sha256"]
        == row["sha256"]
    )
    resource.write_bytes(b"tampered\n")
    with pytest.raises(resource_contract_api.ResourceContractError, match="bytes differ"):
        resource_contract_api.verify_importlib_resource_bytes(
            root, "e02_q2_resource_fixture", [row]
        )
    resource.unlink()
    with pytest.raises(resource_contract_api.ResourceContractError, match="resource is missing"):
        resource_contract_api.verify_importlib_resource_bytes(
            root, "e02_q2_resource_fixture", [row]
        )


def test_source_resource_reader_rejects_missing_and_changed_owner_bytes(
    tmp_path: Path, source_resource_inventory: dict[str, Any]
) -> None:
    row = source_resource_inventory["assets"][0]
    product = tmp_path / "source-product"
    source = product / row["source"]
    source.parent.mkdir(parents=True)
    source.write_bytes((PRODUCT_ROOT / row["source"]).read_bytes())
    resource_contract_api.verify_source_resource_bytes(product, [row])
    source.write_bytes(b"changed source bytes\n")
    with pytest.raises(resource_contract_api.ResourceContractError, match="bytes changed"):
        resource_contract_api.verify_source_resource_bytes(product, [row])
    source.unlink()
    with pytest.raises(resource_contract_api.ResourceContractError, match="source is missing"):
        resource_contract_api.verify_source_resource_bytes(product, [row])


def test_installed_resource_inspector_rejects_present_but_empty_pythonpath(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_resource_inventory: dict[str, Any],
) -> None:
    expected_path = tmp_path / "runtime-owner-inventory.json"
    expected_path.write_text(
        json.dumps(source_resource_inventory, sort_keys=True), encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", "")
    result = _run_test_process(
        [
            sys.executable,
            "-I",
            str(RESOURCE_CONTRACT_PATH),
            "installed",
            "--expected-inventory",
            str(expected_path),
        ],
        check=False,
        timeout=30,
    )
    assert result.returncode == 2
    assert result.stderr.strip() == (
        "resource contract failed: installed resource inspection refuses PYTHONPATH"
    )


def test_archive_reader_refuses_one_omitted_runtime_owned_asset(
    tmp_path: Path, source_resource_inventory: dict[str, Any]
) -> None:
    assets = source_resource_inventory["assets"]
    archive_path = tmp_path / "incomplete-source.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for row in assets[:-1]:
            source = PRODUCT_ROOT / row["source"]
            data = source.read_bytes()
            member = tarfile.TarInfo("policy-engine/" + row["source"])
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    with pytest.raises(runner_api.WaveFailure, match="omitted force-include sources"):
        runner_api.verify_tar_assets(
            archive_path,
            assets,
            member_prefix="policy-engine/",
            exact_force_directories=False,
        )


def test_audit_recomputes_frozen_resource_hashes_from_the_checkout() -> None:
    repo = REPO_ROOT
    source_sha = _run_test_process(
        [_git_executable(), "-C", str(repo), "rev-parse", "HEAD"]
    ).stdout.strip()
    assets, receipt = audit_api.asset_rows_from_config(repo, source_sha, {})
    assert assets
    assert receipt["wheel_force_include_count"] == len(assets)
    assert receipt["sdist_inclusion_status"] == "deferred_to_actual_archive_member_check"
    assert all(len(asset["sha256"]) == 64 for asset in assets)


def test_audit_accepts_nested_source_selected_by_hatch_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = REPO_ROOT
    source_sha = _run_test_process(
        [_git_executable(), "-C", str(repo), "rev-parse", "HEAD"]
    ).stdout.strip()
    source = "src/polisyos/__init__.py"
    wheel = "polisyos/_resources/q2-source-preflight-nested.py"
    sdist_include = ["src/polisyos"]
    hatch = (
        "[build.targets.wheel.force-include]\n"
        f'"{source}" = "{wheel}"\n\n'
        "[build.targets.sdist]\n"
        f"include = {json.dumps(sdist_include)}\n"
    ).encode()
    original = audit_api.read_commit_blob

    def read_source(repository: Path, commit: str, relative: str) -> bytes:
        if relative == audit_api.HATCH_REL:
            return hatch
        return original(repository, commit, relative)

    monkeypatch.setattr(audit_api, "read_commit_blob", read_source)
    rows, receipt = audit_api.asset_rows_from_config(repo, source_sha, {})
    source_bytes = original(repo, source_sha, f"policy-engine/{source}")
    assert source not in sdist_include
    assert any(source.startswith(f"{entry.rstrip('/')}/") for entry in sdist_include)
    assert rows == [
        {
            "source": source,
            "archive": f"policy-engine/{source}",
            "wheel": wheel,
            "bytes": len(source_bytes),
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
    ]
    assert receipt["sdist_inclusion_status"] == "deferred_to_actual_archive_member_check"


def test_freeze_audit_binds_supplemental_sources_and_linux_capture_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = REPO_ROOT
    source_sha, helper_record, git_profile = _current_audit_binding(repo)
    supplemental_runner = (HERE / "supplemental_run.py").read_bytes()
    supplemental_manifest = (HERE / "supplemental-manifest.json").read_bytes()
    supplemental_manifest_rel = f"{audit_api.HANDOFF_REL}/raw/supplemental-manifest.json"
    capture_hook_rel = audit_api.SITE_CUSTOMIZE_REL
    capture_hook = (repo / capture_hook_rel).read_bytes()
    resource_contract_rel = audit_api.PACKAGED_RESOURCE_CONTRACT_REL
    resource_contract = (repo / resource_contract_rel).read_bytes()
    originals = audit_api.read_commit_blob
    source_objects = {
        audit_api.SUPPLEMENT_REL: supplemental_runner,
        supplemental_manifest_rel: supplemental_manifest,
        capture_hook_rel: capture_hook,
        resource_contract_rel: resource_contract,
    }

    def read_source_object(repository: Path, commit: str, relative: str) -> bytes:
        if relative in source_objects:
            return source_objects[relative]
        return originals(repository, commit, relative)

    monkeypatch.setattr(audit_api, "read_commit_blob", read_source_object)
    manifest_path = repo / supplemental_manifest_rel
    records, capsule_bytes = audit_api.input_file_records(
        repo,
        source_sha,
        str(manifest_path),
        hashlib.sha256(supplemental_manifest).hexdigest(),
        helper_record=helper_record,
        git_profile=git_profile,
    )

    for relative, payload in source_objects.items():
        assert records["tracked_git_objects"][relative] == {
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        assert capsule_bytes[relative] == payload
    assert records["tracked_git_objects"][capture_hook_rel] == {
        "bytes": len(capture_hook),
        "sha256": hashlib.sha256(capture_hook).hexdigest(),
    }
    assert capsule_bytes[capture_hook_rel] == capture_hook


def test_freeze_audit_refuses_missing_tracked_supplemental_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = REPO_ROOT
    source_sha, helper_record, git_profile = _current_audit_binding(repo)
    supplemental_runner = (HERE / "supplemental_run.py").read_bytes()
    supplemental_manifest_rel = f"{audit_api.HANDOFF_REL}/raw/supplemental-manifest.json"
    originals = audit_api.read_commit_blob

    def read_source_object(repository: Path, commit: str, relative: str) -> bytes:
        if relative == audit_api.SUPPLEMENT_REL:
            return supplemental_runner
        if relative == supplemental_manifest_rel:
            raise audit_api.AuditFailure("source object missing: supplemental manifest")
        return originals(repository, commit, relative)

    monkeypatch.setattr(audit_api, "read_commit_blob", read_source_object)
    manifest_path = repo / supplemental_manifest_rel
    with pytest.raises(
        audit_api.AuditFailure, match="source object missing: supplemental manifest"
    ):
        audit_api.input_file_records(
            repo,
            source_sha,
            str(manifest_path),
            hashlib.sha256((HERE / "supplemental-manifest.json").read_bytes()).hexdigest(),
            helper_record=helper_record,
            git_profile=git_profile,
        )


def test_freeze_audit_refuses_missing_tracked_linux_capture_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = REPO_ROOT
    source_sha, helper_record, git_profile = _current_audit_binding(repo)
    originals = audit_api.read_commit_blob

    def read_source_object(repository: Path, commit: str, relative: str) -> bytes:
        if relative == audit_api.SITE_CUSTOMIZE_REL:
            raise audit_api.AuditFailure("source object missing: Linux capture hook")
        if relative == audit_api.SUPPLEMENT_REL:
            return (HERE / "supplemental_run.py").read_bytes()
        if relative == audit_api.SUPPLEMENT_MANIFEST_REL:
            return (HERE / "supplemental-manifest.json").read_bytes()
        return originals(repository, commit, relative)

    monkeypatch.setattr(audit_api, "read_commit_blob", read_source_object)
    manifest = (HERE / "supplemental-manifest.json").read_bytes()
    manifest_path = repo / audit_api.SUPPLEMENT_MANIFEST_REL
    with pytest.raises(audit_api.AuditFailure, match="source object missing: Linux capture hook"):
        audit_api.input_file_records(
            repo,
            source_sha,
            str(manifest_path),
            hashlib.sha256(manifest).hexdigest(),
            helper_record=helper_record,
            git_profile=git_profile,
        )


def test_freeze_audit_refuses_missing_runtime_resource_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = REPO_ROOT
    source_sha, helper_record, git_profile = _current_audit_binding(repo)
    supplemental_manifest = (HERE / "supplemental-manifest.json").read_bytes()
    source_objects = {
        audit_api.SUPPLEMENT_REL: (HERE / "supplemental_run.py").read_bytes(),
        audit_api.SUPPLEMENT_MANIFEST_REL: supplemental_manifest,
        audit_api.SITE_CUSTOMIZE_REL: (repo / audit_api.SITE_CUSTOMIZE_REL).read_bytes(),
    }
    originals = audit_api.read_commit_blob

    def read_source_object(repository: Path, commit: str, relative: str) -> bytes:
        if relative == audit_api.PACKAGED_RESOURCE_CONTRACT_REL:
            raise audit_api.AuditFailure("source object missing: runtime resource contract")
        if relative in source_objects:
            return source_objects[relative]
        return originals(repository, commit, relative)

    monkeypatch.setattr(audit_api, "read_commit_blob", read_source_object)
    manifest_path = repo / audit_api.SUPPLEMENT_MANIFEST_REL
    with pytest.raises(
        audit_api.AuditFailure, match="source object missing: runtime resource contract"
    ):
        audit_api.input_file_records(
            repo,
            source_sha,
            str(manifest_path),
            hashlib.sha256(supplemental_manifest).hexdigest(),
            helper_record=helper_record,
            git_profile=git_profile,
        )


def test_source_bound_json_readers_reject_parent_and_final_symlinks(tmp_path: Path) -> None:
    external_directory = tmp_path / "external"
    external_directory.mkdir()
    sentinel = external_directory / "manifest.json"
    sentinel_bytes = b'{"outside":"must-not-be-admitted"}\n'
    sentinel.write_bytes(sentinel_bytes)
    alias_parent = tmp_path / "parent-link"
    alias_parent.symlink_to(external_directory, target_is_directory=True)
    alias_file = alias_parent / sentinel.name
    digest = hashlib.sha256(sentinel_bytes).hexdigest()

    for reader, error_type, label in (
        (runner_api.load_verified_json_file, runner_api.WaveFailure, "primary"),
        (
            supplemental_api.read_verified_json_input,
            supplemental_api.SupplementalError,
            "supplemental",
        ),
    ):
        with pytest.raises(error_type, match="symlink"):
            reader(alias_file, digest, f"{label} external input")
        final_link = tmp_path / f"{label}-final-link.json"
        final_link.symlink_to(sentinel)
        with pytest.raises(error_type, match="symlink"):
            reader(final_link, digest, f"{label} final link")
        final_link.unlink()
        assert sentinel.read_bytes() == sentinel_bytes

    with pytest.raises(audit_api.AuditFailure, match="symlink"):
        audit_api.read_regular_local(alias_file)
    audit_final_link = tmp_path / "audit-final-link.json"
    audit_final_link.symlink_to(sentinel)
    with pytest.raises(audit_api.AuditFailure, match="symlink"):
        audit_api.read_regular_local(audit_final_link)
    assert sentinel.read_bytes() == sentinel_bytes

    regular = tmp_path / "regular.json"
    regular.write_bytes(sentinel_bytes)
    path, parsed, actual_digest = runner_api.load_verified_json_file(
        regular, digest, "primary positive control"
    )
    assert path == regular
    assert parsed == {"outside": "must-not-be-admitted"}
    assert actual_digest == digest
    assert audit_api.read_regular_local(regular) == sentinel_bytes
    supplement_path, supplement_parsed, supplement_digest = (
        supplemental_api.read_verified_json_input(regular, digest, "supplemental positive control")
    )
    assert supplement_path == regular
    assert supplement_parsed == parsed
    assert supplement_digest == digest


def test_supplemental_resource_count_rejects_float_and_boolean_counterfeits() -> None:
    supplemental_api.require_exact_resource_count(11, 11)
    for counterfeit in (11.0, True, "11", -1, 12):
        with pytest.raises(supplemental_api.SupplementalError, match="exact positive integer"):
            supplemental_api.require_exact_resource_count(counterfeit, 11)


def load_reviewed_runner() -> ModuleType:
    manifest_path = HERE.parent / "installed-wave-manifest.json"
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return driver._load_reviewed_runner(HERE / "timeout_driver.py", manifest_path, manifest_sha256)


def _manifest() -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "original_q2_suite": {
            "test_paths": ["tests/original.py"],
            "baseline_case_count": 91,
        },
        "additional_installed_consumers": {
            "dependency_profile": {
                "test_path": "tests/additional.py",
                "selectors": [f"test_extra_{index}" for index in range(5)],
            },
            "canonical_bridge_and_worker": {
                "test_path": "tests/additional.py",
                "selectors": [f"test_extra_{index}" for index in range(5, 9)],
            },
        },
    }
    historical = {
        *(f"tests/original.py::test_original_{index}" for index in range(91)),
        *(f"tests/additional.py::test_extra_{index}" for index in range(9)),
    }
    current = historical | {f"tests/original.py::test_current_extra_{index}" for index in range(25)}
    manifest["current_primary_suite"] = {
        "source_file_sha256": {
            "tests/original.py": "a" * 64,
            "tests/additional.py": "b" * 64,
        },
        "selected_node_count": len(current),
        "selected_node_ids_sha256": hashlib.sha256(
            ("\n".join(sorted(current)) + "\n").encode("utf-8")
        ).hexdigest(),
        "selected_node_ids": sorted(current),
        "historical_baseline_subset": {
            "name": "original-q2-91-plus-nine-installed-consumers",
            "selected_node_count": len(historical),
            "selected_node_ids_sha256": hashlib.sha256(
                ("\n".join(sorted(historical)) + "\n").encode("utf-8")
            ).hexdigest(),
        },
    }
    return manifest


class SyntheticRunner:
    class WaveFailure(RuntimeError):  # noqa: N818 - fixtures preserve the serialized error class.
        pass

    WaveFailureError = WaveFailure

    def __init__(self, *, timeout_profile: str | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.timeout_profile = timeout_profile

    @staticmethod
    def json_write(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def sha256_file(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def node_ids_sha256(node_ids: set[str] | list[str]) -> str:
        return hashlib.sha256(("\n".join(sorted(node_ids)) + "\n").encode("utf-8")).hexdigest()

    @staticmethod
    def baseline_node_ids(source_product: Path, manifest: dict[str, Any]) -> set[str]:
        del source_product, manifest
        return {f"tests/original.py::test_original_{index}" for index in range(91)}

    @staticmethod
    def historical_baseline_subset_ids(
        manifest: dict[str, Any], expected_original_ids: set[str]
    ) -> set[str]:
        expected = set(expected_original_ids)
        for group in manifest["additional_installed_consumers"].values():
            expected.update(f"{group['test_path']}::{selector}" for selector in group["selectors"])
        declared = manifest["current_primary_suite"]["historical_baseline_subset"]
        if declared["selected_node_count"] != len(expected):
            raise SyntheticRunner.WaveFailure("historical subset count mismatch")
        if declared["selected_node_ids_sha256"] != SyntheticRunner.node_ids_sha256(expected):
            raise SyntheticRunner.WaveFailure("historical subset digest mismatch")
        return expected

    @staticmethod
    def verify_current_primary_suite_sources(
        frozen_product: Path, manifest: dict[str, Any], expected_original_ids: set[str]
    ) -> set[str]:
        del frozen_product
        declaration = manifest["current_primary_suite"]
        ids = declaration["selected_node_ids"]
        if ids != sorted(set(ids)) or declaration["selected_node_count"] != len(ids):
            raise SyntheticRunner.WaveFailure("current suite IDs are not complete and canonical")
        if declaration["selected_node_ids_sha256"] != SyntheticRunner.node_ids_sha256(ids):
            raise SyntheticRunner.WaveFailure("current suite digest mismatch")
        historical = SyntheticRunner.historical_baseline_subset_ids(manifest, expected_original_ids)
        if not historical <= set(ids):
            raise SyntheticRunner.WaveFailure("current suite omits historical subset IDs")
        return set(ids)

    @staticmethod
    def junit_node_ids(junit_path: Path, original_doc_path: str) -> tuple[set[str], dict[str, int]]:
        root = SafeET.parse(junit_path).getroot()
        ids: set[str] = set()
        counts = {"tests": 0, "skipped": 0, "failures": 0, "errors": 0}
        for case in root.iter("testcase"):
            classname = case.attrib["classname"]
            dotted = classname.split(".")
            path = (
                original_doc_path
                if classname == "test_installed_catalog_defaults"
                else ("/".join([*dotted[:-1], dotted[-1] + ".py"]))
            )
            ids.add(f"{path}::{case.attrib['name']}")
            counts["tests"] += 1
            counts["skipped"] += case.find("skipped") is not None
            counts["failures"] += case.find("failure") is not None
            counts["errors"] += case.find("error") is not None
        return ids, counts

    def run_command(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        log_stem: Path,
        check: bool = True,
        stream_output: bool = False,
        timeout_seconds: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, env, check
        profile = log_stem.parent.name
        call = {
            "profile": profile,
            "timeout_seconds": timeout_seconds,
            "stream_output": stream_output,
        }
        self.calls.append(call)
        stdout_path = log_stem.with_suffix(".stdout.txt")
        stderr_path = log_stem.with_suffix(".stderr.txt")
        stdout_path.write_text(f"{profile} stdout\n", encoding="utf-8")
        stderr_path.write_text(f"{profile} stderr\n", encoding="utf-8")
        timed_out = profile == self.timeout_profile and timeout_seconds is not None
        command = {
            "argv": argv,
            "returncode": None if timed_out else 0,
            "stream_output": stream_output,
            "timeout_seconds": timeout_seconds,
            "timed_out": timed_out,
        }
        log_stem.with_suffix(".command.json").write_text(
            json.dumps(command, sort_keys=True) + "\n", encoding="utf-8"
        )
        if timed_out:
            raise self.WaveFailure("synthetic timeout after partial output")
        return subprocess.CompletedProcess(argv, 0, "", "")


def expected_ids(runner: SyntheticRunner, manifest: dict[str, Any], run_root: Path) -> set[str]:
    return driver._expected_selected_ids(runner, manifest, run_root)


def _junit_case(parent: ET.Element, node_id: str, *, failing: bool) -> None:
    path, name = node_id.split("::", 1)
    classname = {"tests/original.py": "tests.original", "tests/additional.py": "tests.additional"}[
        path
    ]
    case = ET.SubElement(parent, "testcase", {"classname": classname, "name": name})
    if failing:
        ET.SubElement(case, "failure", {"message": "synthetic failing prior profile"})


def write_profile_receipt(
    runner: SyntheticRunner,
    manifest: dict[str, Any],
    run_root: Path,
    profile: str,
    *,
    ids: set[str] | None = None,
    failing_junit: bool = False,
    timeout_seconds: int | None = None,
) -> None:
    output = run_root / "consumer-runs" / profile
    output.mkdir(parents=True, exist_ok=True)
    ids = ids or expected_ids(runner, manifest, run_root)
    nodeids_path = output / "collected-nodeids.json"
    nodeids_path.write_text(json.dumps(sorted(ids)) + "\n", encoding="utf-8")
    junit_path = output / "wave-junit.xml"
    root = ET.Element("testsuite", {"tests": str(len(ids))})
    failing_id = sorted(ids)[0] if failing_junit else None
    for node_id in sorted(ids):
        _junit_case(root, node_id, failing=node_id == failing_id)
    ET.ElementTree(root).write(junit_path, encoding="utf-8", xml_declaration=True)
    origin_path = output / "origin-proof.json"
    origin_path.write_text('{"verified": true}\n', encoding="utf-8")
    stdout_path = output / "consumer-suite.stdout.txt"
    stderr_path = output / "consumer-suite.stderr.txt"
    if not stdout_path.exists():
        stdout_path.write_text("synthetic stdout\n", encoding="utf-8")
    if not stderr_path.exists():
        stderr_path.write_text("synthetic stderr\n", encoding="utf-8")
    _, counts = runner.junit_node_ids(junit_path, manifest["original_q2_suite"]["test_paths"][-1])
    consumers = {
        "returncode": 0,
        "counts": counts,
        "original_q2_ids": 91,
        "selected_node_ids": len(ids),
        "selected_node_ids_sha256": runner.node_ids_sha256(ids),
        "all_original_q2_ids_present": True,
        "collected_nodeids_path": str(nodeids_path),
        "junit_path": str(junit_path),
        "origin_proof_path": str(origin_path),
        "process_output": {
            "stdout_path": str(stdout_path),
            "stdout_bytes": stdout_path.stat().st_size,
            "stdout_sha256": driver.sha256_file(stdout_path),
            "stderr_path": str(stderr_path),
            "stderr_bytes": stderr_path.stat().st_size,
            "stderr_sha256": driver.sha256_file(stderr_path),
        },
    }
    command_path = output / "consumer-suite.command.json"
    if not command_path.exists():
        command_path.write_text(
            json.dumps(
                {
                    "returncode": 0,
                    "timed_out": False,
                    "timeout_seconds": timeout_seconds,
                    "stream_output": True,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    run_root.mkdir(parents=True, exist_ok=True)
    run_receipt_path = run_root / "run-receipt.json"
    receipt = (
        json.loads(run_receipt_path.read_text(encoding="utf-8"))
        if run_receipt_path.is_file()
        else {"profiles": {}}
    )
    receipt["profiles"][profile] = {"consumers": consumers}
    runner.json_write(run_receipt_path, receipt)


class TimeoutDriverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_root = _new_harness_output_dir("q2-timeout-driver-case-")
        (self.run_root / "frozen-source" / "policy-engine").mkdir(parents=True)
        self.runner = SyntheticRunner()
        self.manifest = _manifest()

    def call_profile(self, state: dict[str, object], profile: str) -> object:
        output = self.run_root / "consumer-runs" / profile
        output.mkdir(parents=True, exist_ok=True)
        return self.runner.run_command(
            ["synthetic pytest"],
            cwd=self.run_root,
            env={},
            log_stem=output / "consumer-suite",
            check=False,
            stream_output=True,
        )

    def test_success_calibrates_each_next_profile_from_exact_passed_ids(self) -> None:
        state = driver.install_adaptive_run_command(self.runner, self.manifest)
        ticks = iter([10.0, 12.0, 20.0, 22.1, 30.0, 31.0])
        with patch.object(driver.time, "monotonic", side_effect=lambda: next(ticks)):
            self.call_profile(state, "source-wheel")
            write_profile_receipt(self.runner, self.manifest, self.run_root, "source-wheel")
            self.call_profile(state, "rebuilt-sdist-wheel")
            write_profile_receipt(
                self.runner,
                self.manifest,
                self.run_root,
                "rebuilt-sdist-wheel",
                timeout_seconds=4,
            )
            self.call_profile(state, "rebuilt-gcp-archive-wheel")
            write_profile_receipt(
                self.runner,
                self.manifest,
                self.run_root,
                "rebuilt-gcp-archive-wheel",
                timeout_seconds=5,
            )
        assert [call["timeout_seconds"] for call in self.runner.calls] == [None, 4, 5]
        if not all(call["stream_output"] for call in self.runner.calls):
            raise AssertionError("consumer commands did not retain direct stream output")
        if not state["profiles"][1]["predecessor_validation"][
            "exact_current_suite_collection_and_junit_verified"
        ]:
            raise AssertionError("prior profile did not verify the complete current selector set")
        manifest_path = self.run_root / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest, sort_keys=True) + "\n", encoding="utf-8")
        sidecar = driver._write_calibration_sidecar(
            self.runner,
            state,
            driver_path=HERE / "timeout_driver.py",
            runner_path=HERE / "run.py",
            manifest_path=manifest_path,
            driver_sha=driver.sha256_file(HERE / "timeout_driver.py"),
            runner_sha=driver.sha256_file(HERE / "run.py"),
            manifest_sha=driver.sha256_file(manifest_path),
            source_sha="c" * 40,
            source_tree="d" * 40,
            status="passed",
            failure=None,
        )
        assert sidecar == self.run_root / "timeout-calibration.json"
        sidecar_record = json.loads(sidecar.read_text(encoding="utf-8"))
        assert sidecar_record["status"] == "passed"
        for profile in sidecar_record["profiles"]:
            assert profile["terminal_evidence_verification"]["status"] == "verified"
            assert driver.verify_terminal_command_evidence(profile["terminal_evidence"])
        TERMINAL_EVIDENCE_RECEIPTS["successful_profiles_sidecar"] = {
            "path": str(sidecar),
            "sha256": hashlib.sha256(sidecar.read_bytes()).hexdigest(),
        }
        sidecar_content = sidecar.read_text(encoding="utf-8")
        assert "synthetic stdout" not in sidecar_content
        assert '"stdout"' in sidecar_content
        assert '"command_record"' in sidecar_content

    def test_failed_prior_junit_blocks_next_profile(self) -> None:
        state = driver.install_adaptive_run_command(self.runner, self.manifest)
        self.call_profile(state, "source-wheel")
        write_profile_receipt(
            self.runner,
            self.manifest,
            self.run_root,
            "source-wheel",
            failing_junit=True,
        )
        before = len(self.runner.calls)
        with pytest.raises(self.runner.WaveFailure):
            self.call_profile(state, "rebuilt-sdist-wheel")
        assert len(self.runner.calls) == before

    def test_wrong_node_set_with_current_suite_count_blocks_next_profile(self) -> None:
        state = driver.install_adaptive_run_command(self.runner, self.manifest)
        self.call_profile(state, "source-wheel")
        ids = expected_ids(self.runner, self.manifest, self.run_root)
        ids.remove("tests/original.py::test_current_extra_24")
        ids.add("tests/additional.py::test_unselected_impostor")
        write_profile_receipt(self.runner, self.manifest, self.run_root, "source-wheel", ids=ids)
        before = len(self.runner.calls)
        with pytest.raises(self.runner.WaveFailure):
            self.call_profile(state, "rebuilt-sdist-wheel")
        assert len(self.runner.calls) == before
        if len(ids) != len(self.manifest["current_primary_suite"]["selected_node_ids"]):
            raise AssertionError("wrong-ID probe did not preserve the selected-set count")

    def test_removed_current_id_with_stale_manifest_digest_is_rejected(self) -> None:
        runner_path = HERE / "run.py"
        manifest_path = HERE.parent / "installed-wave-manifest.json"
        module_spec = importlib.util.spec_from_file_location(
            "q2_primary_runner_for_binding", runner_path
        )
        if module_spec is None or module_spec.loader is None:
            raise AssertionError("primary runner module spec could not be loaded")
        primary_runner = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(primary_runner)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        product = PRODUCT_ROOT
        expected_original = primary_runner.baseline_node_ids(product, manifest)
        selected = manifest["current_primary_suite"]["selected_node_ids"]
        binding = primary_runner.verify_transitive_test_bindings(
            product, manifest, expected_original
        )
        if binding["current_primary_suite_node_ids"] != len(selected):
            raise AssertionError(
                "transitive binding did not cover the complete current selector set"
            )
        current_ids = primary_runner.verify_current_primary_suite_sources(
            product, manifest, expected_original
        )
        if len(current_ids) != len(selected):
            raise AssertionError("source binding did not verify the complete current selector set")
        manifest["current_primary_suite"]["selected_node_ids"].remove(selected[-1])
        try:
            primary_runner.current_primary_suite_ids(manifest, expected_original)
        except primary_runner.WaveFailure:
            pass
        else:
            raise AssertionError("a removed current selector with a stale digest was accepted")

    def test_later_timeout_delegates_partial_stream_retention(self) -> None:
        self.runner.timeout_profile = "rebuilt-sdist-wheel"
        state = driver.install_adaptive_run_command(self.runner, self.manifest)
        ticks = iter([1.0, 2.0, 5.0, 5.25])
        with patch.object(driver.time, "monotonic", side_effect=lambda: next(ticks)):
            self.call_profile(state, "source-wheel")
            write_profile_receipt(self.runner, self.manifest, self.run_root, "source-wheel")
            with pytest.raises(self.runner.WaveFailure):
                self.call_profile(state, "rebuilt-sdist-wheel")
        assert [call["timeout_seconds"] for call in self.runner.calls] == [None, 2]
        timed_out = state["profiles"][-1]
        assert timed_out["outcome"] == "timed_out"
        assert Path(timed_out["stdout_path"]).is_file()
        assert Path(timed_out["stderr_path"]).is_file()
        assert driver.verify_terminal_command_evidence(timed_out["terminal_evidence"])
        manifest_path = self.run_root / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest, sort_keys=True) + "\n", encoding="utf-8")
        sidecar = driver._write_calibration_sidecar(
            self.runner,
            state,
            driver_path=HERE / "timeout_driver.py",
            runner_path=HERE / "run.py",
            manifest_path=manifest_path,
            driver_sha=driver.sha256_file(HERE / "timeout_driver.py"),
            runner_sha=driver.sha256_file(HERE / "run.py"),
            manifest_sha=driver.sha256_file(manifest_path),
            source_sha="c" * 40,
            source_tree="d" * 40,
            status="failed",
            failure="synthetic timeout",
        )
        sidecar_record = json.loads(sidecar.read_text(encoding="utf-8"))
        assert sidecar_record["status"] == "failed"
        assert sidecar_record["profiles"][-1]["outcome"] == "timed_out"
        assert (
            sidecar_record["profiles"][-1]["terminal_evidence_verification"]["status"] == "verified"
        )
        TERMINAL_EVIDENCE_RECEIPTS["timed_out_profile_sidecar"] = {
            "path": str(sidecar),
            "sha256": hashlib.sha256(sidecar.read_bytes()).hexdigest(),
        }

    def test_reviewed_runner_timeout_retains_both_partial_streams(self) -> None:
        runner, _, _, _, _, _ = load_reviewed_runner()
        log_stem = self.run_root / "real-run-command-timeout"
        program = (
            "import sys,time; print('Q2_DRIVER_TIMEOUT_STDOUT', flush=True); "
            "print('Q2_DRIVER_TIMEOUT_STDERR', file=sys.stderr, flush=True); time.sleep(5)"
        )
        with pytest.raises(runner.WaveFailure):
            runner.run_command(
                [sys.executable, "-c", program],
                cwd=self.run_root,
                env=runner.clean_child_env(),
                log_stem=log_stem,
                check=False,
                stream_output=True,
                timeout_seconds=0.2,
            )
        assert b"Q2_DRIVER_TIMEOUT_STDOUT" in log_stem.with_suffix(".stdout.txt").read_bytes()
        assert b"Q2_DRIVER_TIMEOUT_STDERR" in log_stem.with_suffix(".stderr.txt").read_bytes()
        command = json.loads(log_stem.with_suffix(".command.json").read_text(encoding="utf-8"))
        assert command["timed_out"]
        assert command["timeout_seconds"] == 0.2
        evidence = driver.capture_terminal_command_evidence(log_stem)
        assert driver.verify_terminal_command_evidence(evidence)
        assert evidence["command_record"]["path"] == str(log_stem.with_suffix(".command.json"))
        assert evidence["stdout"]["available"]
        assert evidence["stderr"]["available"]
        TERMINAL_EVIDENCE_RECEIPTS["actual_timeout_child"] = evidence

    def test_reviewed_runner_nonzero_child_binds_command_and_stream_bytes(self) -> None:
        runner, _, _, _, _, _ = load_reviewed_runner()
        state = driver.install_adaptive_run_command(runner, _manifest())
        log_stem = self.run_root / "consumer-runs" / "source-wheel" / "consumer-suite"
        program = (
            "import sys; print('Q2_DRIVER_FAILED_STDOUT', flush=True); "
            "print('Q2_DRIVER_FAILED_STDERR', file=sys.stderr, flush=True); sys.exit(17)"
        )
        result = runner.run_command(
            [sys.executable, "-c", program],
            cwd=self.run_root,
            env=runner.clean_child_env(),
            log_stem=log_stem,
            check=False,
            stream_output=True,
        )
        assert result.returncode == 17
        evidence = state["profiles"][-1]["terminal_evidence"]
        assert driver.verify_terminal_command_evidence(evidence)
        command = json.loads(log_stem.with_suffix(".command.json").read_text(encoding="utf-8"))
        assert evidence["command_record"]["sha256"] == runner.sha256_file(
            log_stem.with_suffix(".command.json")
        )
        assert command["returncode"] == 17
        assert evidence["stdout"]["bytes"] == log_stem.with_suffix(".stdout.txt").stat().st_size
        assert evidence["stderr"]["bytes"] == log_stem.with_suffix(".stderr.txt").stat().st_size
        command_path = Path(evidence["command_record"]["path"])
        command_path.write_bytes(b"{}\n")
        assert command_path.exists()
        TERMINAL_EVIDENCE_RECEIPTS["actual_nonzero_child"] = {
            "captured_terminal_evidence": evidence,
            "same_path_after_tamper": {
                "path": str(command_path),
                "bytes": command_path.stat().st_size,
                "sha256": hashlib.sha256(command_path.read_bytes()).hexdigest(),
            },
        }
        with pytest.raises(driver.DriverFailure):
            driver.verify_terminal_command_evidence(evidence)

    def test_same_path_partial_stream_tampering_fails_terminal_evidence_verification(self) -> None:
        runner, _, _, _, _, _ = load_reviewed_runner()
        log_stem = self.run_root / "real-run-command-tamper"
        program = (
            "import sys,time; print('Q2_DRIVER_TAMPER_STDOUT', flush=True); "
            "print('Q2_DRIVER_TAMPER_STDERR', file=sys.stderr, flush=True); time.sleep(5)"
        )
        with pytest.raises(runner.WaveFailure):
            runner.run_command(
                [sys.executable, "-c", program],
                cwd=self.run_root,
                env=runner.clean_child_env(),
                log_stem=log_stem,
                check=False,
                stream_output=True,
                timeout_seconds=0.2,
            )
        evidence = driver.capture_terminal_command_evidence(log_stem)
        assert driver.verify_terminal_command_evidence(evidence)
        stdout_path = Path(evidence["stdout"]["path"])
        assert stdout_path == log_stem.with_suffix(".stdout.txt")
        stdout_path.write_bytes(b"X" * evidence["stdout"]["bytes"])
        assert stdout_path.exists()
        TERMINAL_EVIDENCE_RECEIPTS["partial_stream_same_path_tamper"] = {
            "captured_terminal_evidence": evidence,
            "same_path_after_tamper": {
                "path": str(stdout_path),
                "bytes": stdout_path.stat().st_size,
                "sha256": hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
            },
        }
        with pytest.raises(driver.DriverFailure):
            driver.verify_terminal_command_evidence(evidence)

    def test_missing_terminal_stream_is_explicit_unavailable_evidence(self) -> None:
        runner, _, _, _, _, _ = load_reviewed_runner()
        log_stem = self.run_root / "real-run-command-missing-stream"
        runner.run_command(
            [sys.executable, "-c", "print('Q2_DRIVER_MISSING_STREAM')"],
            cwd=self.run_root,
            env=runner.clean_child_env(),
            log_stem=log_stem,
            check=False,
            stream_output=True,
        )
        stderr_path = log_stem.with_suffix(".stderr.txt")
        stderr_path.unlink()
        evidence = driver.capture_terminal_command_evidence(log_stem)
        assert not evidence["stderr"]["available"]
        assert evidence["stderr"]["unavailable_reason"] == "file_missing"
        TERMINAL_EVIDENCE_RECEIPTS["explicit_missing_stream"] = evidence
        with pytest.raises(driver.DriverFailure):
            driver.verify_terminal_command_evidence(evidence)

    def test_fifo_capture_without_writer_is_nonblocking_and_nonregular(self) -> None:
        fifo_path = self.run_root / "fifo-without-writer"
        os.mkfifo(fifo_path)
        program = (
            "import importlib.util,json,sys; "
            "spec=importlib.util.spec_from_file_location('q2_fifo_driver',sys.argv[1]); "
            "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
            "print(json.dumps(module._capture_file_binding(__import__('pathlib').Path(sys.argv[2]))))"
        )
        result = _run_test_process(
            [sys.executable, "-B", "-c", program, str(HERE / "timeout_driver.py"), str(fifo_path)],
            check=True,
            timeout=0.75,
        )
        binding = json.loads(result.stdout)
        assert not binding["available"]
        assert binding["unavailable_reason"] == "not_regular_file"
        TERMINAL_EVIDENCE_RECEIPTS["fifo_without_writer"] = binding

    def test_nonregular_family_and_changed_regular_file_controls(self) -> None:
        regular_target = self.run_root / "symlink-target.txt"
        regular_target.write_text("regular target\n", encoding="utf-8")
        symlink_path = self.run_root / "regular-symlink"
        symlink_path.symlink_to(regular_target)
        directory_path = self.run_root / "directory-path"
        directory_path.mkdir()
        socket_dir = self.run_root / "socket-fixture"
        socket_dir.mkdir()
        socket_path = socket_dir / "s"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        family_receipt = {}
        try:
            nonregular_paths = [
                symlink_path,
                directory_path,
                socket_path,
                Path("/dev/null"),
            ]
            for path in nonregular_paths:
                with self.subTest(path=str(path)):
                    binding = driver._capture_file_binding(path)
                    assert not binding["available"]
                    assert binding["unavailable_reason"] == "not_regular_file"
                    family_receipt[path.name] = {
                        "path": str(path),
                        "available": binding["available"],
                        "unavailable_reason": binding["unavailable_reason"],
                    }
        finally:
            listener.close()
        TERMINAL_EVIDENCE_RECEIPTS["nonregular_file_family"] = family_receipt

        log_stem = self.run_root / "regular-control" / "consumer-suite"
        log_stem.parent.mkdir(parents=True, exist_ok=True)
        log_stem.with_suffix(".command.json").write_text(
            json.dumps({"returncode": 0, "timed_out": False, "stream_output": True}) + "\n",
            encoding="utf-8",
        )
        log_stem.with_suffix(".stdout.txt").write_bytes(b"regular stdout\n")
        log_stem.with_suffix(".stderr.txt").write_bytes(b"regular stderr\n")
        evidence = driver.capture_terminal_command_evidence(log_stem)
        assert driver.verify_terminal_command_evidence(evidence)
        stdout_path = Path(evidence["stdout"]["path"])
        stdout_path.write_bytes(b"changed stdout\n")
        with pytest.raises(driver.DriverFailure):
            driver.verify_terminal_command_evidence(evidence)
        TERMINAL_EVIDENCE_RECEIPTS["changed_regular_control"] = {
            "captured_sha256": evidence["stdout"]["sha256"],
            "same_path": evidence["stdout"]["path"],
            "changed_bytes": stdout_path.stat().st_size,
            "changed_sha256": hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
        }

    def test_wrapper_sidecar_completes_for_fifo_without_writer(self) -> None:
        log_dir = self.run_root / "consumer-runs" / "source-wheel"
        log_dir.mkdir(parents=True, exist_ok=True)
        fifo_path = log_dir / "consumer-suite.stdout.txt"
        os.mkfifo(fifo_path)
        program = "\n".join(
            (
                "import importlib.util,json,sys,time",
                "from pathlib import Path",
                "import subprocess",
                "spec=importlib.util.spec_from_file_location('q2_fifo_driver',sys.argv[1])",
                "driver=importlib.util.module_from_spec(spec); spec.loader.exec_module(driver)",
                "class Runner:",
                "    class WaveFailure(RuntimeError): pass",
                "    @staticmethod",
                "    def json_write(path,value):",
                "        path.parent.mkdir(parents=True,exist_ok=True)",
                "        path.write_text(json.dumps(value)+'\\n',encoding='utf-8')",
                "runner=Runner()",
                "log_stem=Path(sys.argv[3])",
                (
                    "def original(argv,*,cwd,env,log_stem,check=True,stream_output=False,"
                    "timeout_seconds=None):"
                ),
                "    log_stem.parent.mkdir(parents=True,exist_ok=True)",
                (
                    "    log_stem.with_suffix('.stderr.txt').write_text('retained "
                    "stderr\\n',encoding='utf-8')"
                ),
                (
                    "    Runner.json_write(log_stem.with_suffix('.command.json'),{'return"
                    "code':0,'timed_out':False,'stream_output':True,'timeout_seconds':tim"
                    "eout_seconds})"
                ),
                "    return subprocess.CompletedProcess(argv,0,'','')",
                "runner.run_command=original",
                "state=driver.install_adaptive_run_command(runner,{})",
                "started=time.monotonic()",
                "try:",
                (
                    "    runner.run_command(['synthetic "
                    "child'],cwd=Path(sys.argv[2]),env={},log_stem=log_stem,check=False,s"
                    "tream_output=True)"
                ),
                "except Runner.WaveFailure as error:",
                "    wrapper_error=str(error)",
                "else:",
                "    raise RuntimeError('wrapper accepted a FIFO stdout path')",
                "manifest_path=Path(sys.argv[2])/'manifest.json'",
                "manifest_path.write_text('{}\\n',encoding='utf-8')",
                "runner_path=Path(sys.argv[1]).with_name('run.py')",
                "sidecar=driver._write_calibration_sidecar(runner,state,driver_path=Path(sys.argv[1]),runner_path=runner_path,manifest_path=manifest_path,driver_sha=driver.sha256_file(Path(sys.argv[1])),runner_sha=driver.sha256_file(runner_path),manifest_sha=driver.sha256_file(manifest_path),source_sha='c'*40,source_tree='d'*40,status='failed',failure=wrapper_error)",
                "record=json.loads(sidecar.read_text(encoding='utf-8'))",
                "profile=record['profiles'][0]",
                "print(json.dumps({'elapsed_seconds':time.monotonic()-started,'sidecar_status':record['status'],'verification':profile['terminal_evidence_verification'],'stdout':profile['terminal_evidence']['stdout'],'sidecar_path':str(sidecar)}))",
            )
        )
        result = _run_test_process(
            [
                sys.executable,
                "-B",
                "-c",
                program,
                str(HERE / "timeout_driver.py"),
                str(self.run_root),
                str(log_dir / "consumer-suite"),
            ],
            check=True,
            timeout=1.0,
        )
        receipt = json.loads(result.stdout)
        assert receipt["sidecar_status"] == "failed"
        assert receipt["verification"]["status"] == "failed"
        assert not receipt["stdout"]["available"]
        assert receipt["stdout"]["unavailable_reason"] == "not_regular_file"
        sidecar_path = Path(receipt["sidecar_path"])
        TERMINAL_EVIDENCE_RECEIPTS["fifo_wrapper_sidecar"] = {
            "elapsed_seconds": receipt["elapsed_seconds"],
            "path": str(sidecar_path),
            "sha256": hashlib.sha256(sidecar_path.read_bytes()).hexdigest(),
            "status": receipt["sidecar_status"],
            "verification": receipt["verification"],
            "stdout": receipt["stdout"],
        }


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TimeoutDriverTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "successful": result.wasSuccessful(),
        "terminal_evidence_receipts": TERMINAL_EVIDENCE_RECEIPTS,
    }
    report_root = _new_harness_output_dir("q2-timeout-driver-report-")
    report_path = report_root / "report.json"
    report["harness_output_root"] = str(report_root)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)


COUNT_COUNTERFEITS = (2.0, True, "2", -1, 3)


def _count_counterfeits(expected: int) -> tuple[object, ...]:
    return (float(expected), True, str(expected), -1, expected + 1)


def _replace_count(
    manifest: dict[str, Any], path: tuple[str, ...], value: object
) -> dict[str, Any]:
    mutated = json.loads(json.dumps(manifest))
    current: Any = mutated
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
    return mutated


def test_all_source_manifest_count_guards_reject_numeric_aliases(tmp_path: Path) -> None:
    repo = REPO_ROOT
    product = PRODUCT_ROOT
    manifest = json.loads(
        (HERE.parent / "installed-wave-manifest.json").read_text(encoding="utf-8")
    )
    original_ids = runner_api.baseline_node_ids(product, manifest)
    _, assets = runner_api.read_asset_manifest(product, manifest)
    current_ids = runner_api.current_primary_suite_ids(manifest, original_ids)
    historical_ids = runner_api.historical_baseline_subset_ids(manifest, original_ids)
    assert original_ids
    assert current_ids
    assert historical_ids
    assert len(assets) == manifest["candidate_baseline"]["force_include_count"]

    count_paths = (
        ("original_q2_suite", "baseline_case_count"),
        ("candidate_baseline", "force_include_count"),
        ("current_primary_suite", "selected_node_count"),
        ("current_primary_suite", "historical_baseline_subset", "selected_node_count"),
    )

    def validate_count(candidate: dict[str, Any], path: tuple[str, ...]) -> None:
        if path == ("original_q2_suite", "baseline_case_count"):
            runner_api.baseline_node_ids(product, candidate)
        elif path == ("candidate_baseline", "force_include_count"):
            runner_api.read_asset_manifest(product, candidate)
        elif path == ("current_primary_suite", "selected_node_count"):
            runner_api.current_primary_suite_ids(candidate, original_ids)
        else:
            runner_api.historical_baseline_subset_ids(candidate, original_ids)

    for path in count_paths:
        expected_count: Any = manifest
        for key in path:
            expected_count = expected_count[key]
        for counterfeit in _count_counterfeits(expected_count):
            candidate = _replace_count(manifest, path, counterfeit)
            with pytest.raises(runner_api.WaveFailure):
                validate_count(candidate, path)
    for asset_index, asset in enumerate(assets):
        for counterfeit in (
            float(asset["bytes"]),
            True,
            str(asset["bytes"]),
            -1,
            asset["bytes"] + 1,
        ):
            candidate = json.loads(json.dumps(manifest))
            candidate["candidate_baseline"]["force_include_assets"][asset_index]["bytes"] = (
                counterfeit
            )
            with pytest.raises(runner_api.WaveFailure):
                runner_api.read_asset_manifest(product, candidate)


def test_audit_status_and_supplemental_count_guards_reject_aliases(tmp_path: Path) -> None:
    repo = REPO_ROOT
    product = PRODUCT_ROOT
    primary = json.loads((HERE.parent / "installed-wave-manifest.json").read_text(encoding="utf-8"))
    original_ids = runner_api.baseline_node_ids(product, primary)
    current_ids = runner_api.current_primary_suite_ids(primary, original_ids)
    _, assets = runner_api.read_asset_manifest(product, primary)

    audit_api.validate_recomputed_ids(primary, current_ids, assets)
    assert audit_api.primary_manifest_matches_collection(
        primary,
        current_ids,
        assets,
        primary["current_primary_suite"]["source_file_sha256"],
    )
    current_count = primary["current_primary_suite"]["selected_node_count"]
    for counterfeit in _count_counterfeits(current_count):
        candidate = _replace_count(
            primary, ("current_primary_suite", "selected_node_count"), counterfeit
        )
        with pytest.raises(audit_api.AuditFailure):
            audit_api.validate_recomputed_ids(candidate, current_ids, assets)
        assert not audit_api.primary_manifest_matches_collection(
            candidate,
            current_ids,
            assets,
            primary["current_primary_suite"]["source_file_sha256"],
        )

    for asset_index, asset in enumerate(assets):
        for counterfeit in (
            float(asset["bytes"]),
            True,
            str(asset["bytes"]),
            -1,
            asset["bytes"] + 1,
        ):
            candidate = json.loads(json.dumps(primary))
            candidate["candidate_baseline"]["force_include_assets"][asset_index]["bytes"] = (
                counterfeit
            )
            assert not audit_api.primary_manifest_matches_collection(
                candidate,
                current_ids,
                assets,
                primary["current_primary_suite"]["source_file_sha256"],
            )
            with pytest.raises(audit_api.AuditFailure):
                audit_api.validate_recomputed_ids(candidate, current_ids, assets)

    candidate = _replace_count(
        primary, ("current_primary_suite", "selected_node_count"), float(len(current_ids))
    )
    candidate_raw = json.dumps(candidate, sort_keys=True).encode("utf-8")
    proposed_raw = json.dumps(primary, sort_keys=True).encode("utf-8")
    assert "current_primary_suite" in audit_api.manifest_mismatches(
        candidate, primary, candidate_raw, proposed_raw
    )

    original_junit = product / primary["original_q2_suite"]["baseline_junit_path"]
    original_junit_bytes = original_junit.read_bytes()
    audit_api.baseline_ids_from_junit(original_junit_bytes, primary)
    baseline_count = primary["original_q2_suite"]["baseline_case_count"]
    for counterfeit in _count_counterfeits(baseline_count):
        candidate = _replace_count(
            primary, ("original_q2_suite", "baseline_case_count"), counterfeit
        )
        with pytest.raises(audit_api.AuditFailure):
            audit_api.baseline_ids_from_junit(original_junit_bytes, candidate)

    # The currently supplied supplement is a pre-collection manifest with six selectors.
    # Keep that input pinned while exercising its content-bound count contract with an
    # independent one-test source fixture whose positive node-ID set is genuinely materialized.
    source_supplement = json.loads(
        (HERE.parent / "raw" / "supplemental-manifest.json").read_text(encoding="utf-8")
    )
    selectors = source_supplement["supplemental_suite"]["selectors"]
    assert (
        audit_api.supplemental_manifest_count_mismatches(
            source_supplement,
            asset_count=len(assets),
            supplemental_id_count=len(selectors),
        )
        == []
    )
    supplemental_api.require_exact_resource_count(len(assets), len(assets))
    for counterfeit in _count_counterfeits(len(assets)):
        bad = _replace_count(
            source_supplement,
            ("primary_inputs", "force_include_asset_count_per_profile"),
            counterfeit,
        )
        assert (
            "force_include_asset_count_per_profile"
            in audit_api.supplemental_manifest_count_mismatches(
                bad, asset_count=len(assets), supplemental_id_count=len(selectors)
            )
        )
        with pytest.raises(supplemental_api.SupplementalError):
            supplemental_api.require_exact_resource_count(counterfeit, len(assets))

    test_path = "tests/test_count_guard.py"
    test_source = "def test_count_guard():\n    assert True\n"
    test_file = tmp_path / "product" / test_path
    test_file.parent.mkdir(parents=True)
    test_file.write_text(test_source, encoding="utf-8")
    selected_ids = [f"{test_path}::test_count_guard"]
    supplemental = {
        "supplemental_suite": {
            "test_path": test_path,
            "test_sha256": hashlib.sha256(test_source.encode("utf-8")).hexdigest(),
            "selectors": ["test_count_guard"],
            "selected_node_ids": selected_ids,
            "expected_node_count": 1,
            "selected_node_ids_sha256": audit_api.canonical_ids_sha256(selected_ids),
        }
    }
    selected_set = set(selected_ids)
    audit_api.validate_supplemental_node_ids(supplemental, selected_set)
    assert supplemental_api.suite_node_ids(tmp_path / "product", supplemental) == selected_set
    for counterfeit in _count_counterfeits(1):
        bad = _replace_count(
            supplemental, ("supplemental_suite", "expected_node_count"), counterfeit
        )
        assert (
            "supplemental_suite.expected_node_count"
            in audit_api.supplemental_manifest_count_mismatches(
                {"primary_inputs": {"force_include_asset_count_per_profile": len(assets)}, **bad},
                asset_count=len(assets),
                supplemental_id_count=1,
            )
        )
        with pytest.raises(audit_api.AuditFailure):
            audit_api.validate_supplemental_node_ids(bad, selected_set)
        with pytest.raises(supplemental_api.SupplementalError):
            supplemental_api.suite_node_ids(tmp_path / "product", bad)


def test_timed_driver_expected_baseline_count_is_typed_before_timeout_use(tmp_path: Path) -> None:
    class MinimalRunner:
        class WaveFailureError(RuntimeError):
            pass

        WaveFailure = WaveFailureError

        @staticmethod
        def baseline_node_ids(product: Path, manifest: dict[str, Any]) -> set[str]:
            del product, manifest
            return {"tests/a.py::test_a", "tests/a.py::test_b"}

        @staticmethod
        def verify_current_primary_suite_sources(
            product: Path, manifest: dict[str, Any], original_ids: set[str]
        ) -> set[str]:
            del product, manifest
            return original_ids

    baseline = {"original_q2_suite": {"baseline_case_count": 2}, "current_primary_suite": {}}
    assert driver._expected_selected_ids(MinimalRunner, baseline, tmp_path) == {
        "tests/a.py::test_a",
        "tests/a.py::test_b",
    }
    for counterfeit in COUNT_COUNTERFEITS:
        candidate = _replace_count(
            baseline, ("original_q2_suite", "baseline_case_count"), counterfeit
        )
        with pytest.raises(driver.DriverFailure):
            driver._expected_selected_ids(MinimalRunner, candidate, tmp_path)


def test_exact_count_matchers_reject_bool_float_string_negative_and_mismatch() -> None:
    for matcher in (
        runner_api.exact_nonbool_count_matches,
        supplemental_api.exact_nonbool_count_matches,
        driver.exact_nonbool_count_matches,
        audit_api.exact_nonbool_count_matches,
    ):
        assert matcher(2, 2)
        for counterfeit in COUNT_COUNTERFEITS:
            assert not matcher(counterfeit, 2)


def test_supplemental_consumer_denominator_counts_reject_numeric_aliases(
    tmp_path: Path,
) -> None:
    output = tmp_path / "supplemental-output"
    output.mkdir()
    purelib = tmp_path / "installed" / "lib"
    purelib.mkdir(parents=True)
    dependency_site = tmp_path / "dependency-site"
    dependency_site.mkdir()
    source_product = tmp_path / "source-product"
    source_product.mkdir()
    live_product = tmp_path / "live-product"
    live_product.mkdir()
    expected_ids = {"tests/test_supplemental.py::test_consumer"}
    denominator_properties = {
        "source_contract_package_definitions": 2,
        "source_contract_supported_entrypoints": 3,
        "ast_inventory_unresolved_package_rows": 4,
        "runtime_declared_exports_resolved": 5,
    }
    (output / "collected-nodeids.json").write_text(
        json.dumps(sorted(expected_ids)), encoding="utf-8"
    )
    junit = ET.Element("testsuite")
    case = ET.SubElement(
        junit, "testcase", classname="tests.test_supplemental", name="test_consumer"
    )
    properties = ET.SubElement(case, "properties")
    for key, value in denominator_properties.items():
        ET.SubElement(properties, "property", name=key, value=str(value))
    ET.ElementTree(junit).write(output / "supplemental-junit.xml", encoding="unicode")
    origin = {
        "verified": True,
        "errors": [],
        "purelib": str(purelib),
        "origins": {"polisyos": [str(purelib / "polisyos/__init__.py")]},
        "sys_path": [str(purelib), str(dependency_site)],
    }
    (output / "origin-proof.json").write_text(json.dumps(origin), encoding="utf-8")
    (output / "consumer-suite.stdout.txt").write_text("stdout\n", encoding="utf-8")
    (output / "consumer-suite.stderr.txt").write_text("stderr\n", encoding="utf-8")

    def verify(expected: dict[str, Any]) -> dict[str, Any]:
        return supplemental_api.verify_supplemental_run(
            result=subprocess.CompletedProcess([], 0),
            output=output,
            expected_ids=expected_ids,
            purelib=purelib,
            source_product=source_product,
            live_product=live_product,
            dependency_site=dependency_site,
            expected_denominator_properties=expected,
        )

    assert verify(denominator_properties)["returncode"] == 0
    for key, expected in denominator_properties.items():
        for counterfeit in _count_counterfeits(expected):
            candidate = {**denominator_properties, key: counterfeit}
            with pytest.raises(supplemental_api.SupplementalError):
                verify(candidate)


def _primary_profile_fixture(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    run_root = tmp_path / "primary-run"
    run_root.mkdir()
    purelib = tmp_path / "venv" / "lib"
    purelib.mkdir(parents=True)
    dependency_site = tmp_path / "dependency-site"
    dependency_site.mkdir()
    source_product = tmp_path / "source-product"
    source_product.mkdir()
    live_product = tmp_path / "live-product"
    live_product.mkdir()
    asset_bytes = b"x"
    wheel_target = "fixture/_resources/one.bin"
    asset = {
        "source": "fixture/one.bin",
        "archive": "policy-engine/fixture/one.bin",
        "wheel": wheel_target,
        "bytes": len(asset_bytes),
        "sha256": hashlib.sha256(asset_bytes).hexdigest(),
    }
    assets = [asset]
    wheel_path = run_root / "source-wheel.whl"
    with zipfile.ZipFile(wheel_path, "w") as archive:
        archive.writestr(wheel_target, asset_bytes)
    wheel_proof = runner_api.verify_wheel(wheel_path, assets)

    stdout_path = run_root / "consumer-suite.stdout.txt"
    stderr_path = run_root / "consumer-suite.stderr.txt"
    stdout_path.write_bytes(b"stdout\n")
    stderr_path.write_bytes(b"stderr\n")
    command_path = run_root / "consumer-suite.command.json"
    command_path.write_text(json.dumps({"returncode": 0, "timed_out": False}), encoding="utf-8")
    collected_path = run_root / "collected-nodeids.json"
    expected_ids = {"tests/sample.py::test_sample"}
    collected_path.write_text(json.dumps(sorted(expected_ids)), encoding="utf-8")
    junit_path = run_root / "wave-junit.xml"
    junit = ET.Element("testsuite", tests="1")
    ET.SubElement(junit, "testcase", classname="tests.sample", name="test_sample")
    junit_path.write_bytes(ET.tostring(junit))
    origin_path = run_root / "origin-proof.json"
    product_origin = purelib / "polisyos.py"
    product_origin.write_text("", encoding="utf-8")
    origin_path.write_text(
        json.dumps(
            {
                "verified": True,
                "purelib": str(purelib),
                "origins": {"polisyos": str(product_origin)},
                "sys_path": [str(purelib), str(dependency_site)],
            }
        ),
        encoding="utf-8",
    )
    installed_path = purelib / wheel_target
    installed_path.parent.mkdir(parents=True)
    installed_path.write_bytes(asset_bytes)
    stream = {
        "stdout_path": str(stdout_path),
        "stdout_bytes": stdout_path.stat().st_size,
        "stdout_sha256": hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
        "stderr_path": str(stderr_path),
        "stderr_bytes": stderr_path.stat().st_size,
        "stderr_sha256": hashlib.sha256(stderr_path.read_bytes()).hexdigest(),
    }
    consumer = {
        "returncode": 0,
        "selected_node_ids": len(expected_ids),
        "selected_node_ids_sha256": runner_api.node_ids_sha256(expected_ids),
        "all_original_q2_ids_present": True,
        "collected_nodeids_path": str(collected_path),
        "junit_path": str(junit_path),
        "origin_proof_path": str(origin_path),
        "process_output": stream,
    }
    profile = {
        "wheel": {
            "path": str(wheel_path),
            "sha256": wheel_proof["sha256"],
            "assets": wheel_proof["assets"],
        },
        "consumers": consumer,
        "installed_runtime": {
            "assets": {
                wheel_target: {
                    "installed_path": str(installed_path),
                    "bytes": len(asset_bytes),
                    "sha256": hashlib.sha256(asset_bytes).hexdigest(),
                }
            }
        },
    }
    primary_manifest = {"original_q2_suite": {"test_paths": ["tests/sample.py"]}}
    call = {
        "runner": runner_api,
        "run_root": run_root,
        "profile_name": "source-wheel",
        "profile": profile,
        "primary_manifest": primary_manifest,
        "expected_ids": expected_ids,
        "assets": assets,
        "purelib": purelib,
        "source_product": source_product,
        "live_product": live_product,
        "dependency_site": dependency_site,
    }
    return call, profile


def test_supplemental_primary_consumer_counts_and_asset_bytes_are_strict(tmp_path: Path) -> None:
    call, profile = _primary_profile_fixture(tmp_path)
    positive = supplemental_api.verify_primary_profile(**call)
    assert positive["primary_selected_node_ids"] == 1
    count_fields = (
        (("consumers", "selected_node_ids"), 1),
        (
            ("consumers", "process_output", "stdout_bytes"),
            profile["consumers"]["process_output"]["stdout_bytes"],
        ),
        (
            ("consumers", "process_output", "stderr_bytes"),
            profile["consumers"]["process_output"]["stderr_bytes"],
        ),
        (("wheel", "assets", "fixture/_resources/one.bin", "bytes"), 1),
        (("installed_runtime", "assets", "fixture/_resources/one.bin", "bytes"), 1),
    )
    for path, expected in count_fields:
        for counterfeit in (float(expected), True, str(expected), -1, expected + 1):
            candidate = json.loads(json.dumps(profile))
            target: Any = candidate
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = counterfeit
            bad_call = {**call, "profile": candidate}
            with pytest.raises(supplemental_api.SupplementalError):
                supplemental_api.verify_primary_profile(**bad_call)


def _timeout_profile_fixture(
    tmp_path: Path,
) -> tuple[Any, dict[str, Any], Path, dict[str, Any], dict[str, Any]]:
    run_root = tmp_path / "timeout-run"
    run_root.mkdir()
    output_root = run_root / "source-wheel"
    output_root.mkdir()
    streams_root = output_root / "streams"
    streams_root.mkdir()
    stdout_path = streams_root / "consumer-suite.stdout.txt"
    stderr_path = streams_root / "consumer-suite.stderr.txt"
    stdout_path.write_bytes(b"stdout\n")
    stderr_path.write_bytes(b"stderr\n")
    command_path = streams_root / "consumer-suite.command.json"
    command_path.write_text(
        json.dumps(
            {"returncode": 0, "timed_out": False, "timeout_seconds": 5, "stream_output": True}
        ),
        encoding="utf-8",
    )
    collected_path = output_root / "collected-nodeids.json"
    expected_ids = {"tests/sample.py::test_sample", "tests/sample.py::test_second"}
    collected_path.write_text(json.dumps(sorted(expected_ids)), encoding="utf-8")
    junit_path = output_root / "wave-junit.xml"
    junit_path.write_text("<testsuite />", encoding="utf-8")
    origin_path = output_root / "origin-proof.json"
    origin_path.write_text(json.dumps({"verified": True}), encoding="utf-8")

    class MinimalRunner:
        class WaveFailureError(RuntimeError):
            pass

        WaveFailure = WaveFailureError

        @staticmethod
        def baseline_node_ids(product: Path, manifest: dict[str, Any]) -> set[str]:
            del product, manifest
            return set(expected_ids)

        @staticmethod
        def verify_current_primary_suite_sources(
            product: Path, manifest: dict[str, Any], original_ids: set[str]
        ) -> set[str]:
            del product, manifest
            return original_ids

        @staticmethod
        def junit_node_ids(path: Path, doc_path: str) -> tuple[set[str], dict[str, int]]:
            del path, doc_path
            return set(expected_ids), {
                "tests": len(expected_ids),
                "skipped": 0,
                "failures": 0,
                "errors": 0,
            }

        @staticmethod
        def node_ids_sha256(ids: set[str]) -> str:
            return runner_api.node_ids_sha256(ids)

        @staticmethod
        def historical_baseline_subset_ids(
            manifest: dict[str, Any], original_ids: set[str]
        ) -> set[str]:
            del manifest
            return original_ids

    consumer = {
        "returncode": 0,
        "selected_node_ids": len(expected_ids),
        "selected_node_ids_sha256": runner_api.node_ids_sha256(expected_ids),
        "collected_nodeids_path": str(collected_path),
        "junit_path": str(junit_path),
        "origin_proof_path": str(origin_path),
        "process_output": {
            "stdout_path": str(stdout_path),
            "stdout_bytes": stdout_path.stat().st_size,
            "stdout_sha256": hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
            "stderr_path": str(stderr_path),
            "stderr_bytes": stderr_path.stat().st_size,
            "stderr_sha256": hashlib.sha256(stderr_path.read_bytes()).hexdigest(),
        },
    }
    receipt_path = run_root / "run-receipt.json"
    receipt_path.write_text(
        json.dumps({"profiles": {"source-wheel": {"consumers": consumer}}}),
        encoding="utf-8",
    )
    manifest = {
        "original_q2_suite": {
            "baseline_case_count": len(expected_ids),
            "test_paths": ["tests/sample.py"],
        },
        "current_primary_suite": {},
    }
    evidence = {
        "schema_version": 1,
        "command_record": driver._capture_file_binding(command_path),
        "stdout": driver._capture_file_binding(stdout_path),
        "stderr": driver._capture_file_binding(stderr_path),
    }
    return MinimalRunner, manifest, run_root, consumer, evidence


def test_timeout_consumer_and_stream_count_receipts_reject_numeric_aliases(tmp_path: Path) -> None:
    runner, manifest, run_root, consumer, evidence = _timeout_profile_fixture(tmp_path)
    result = driver.validate_completed_profile(
        runner,
        manifest,
        run_root,
        "source-wheel",
        expected_timeout_seconds=5,
        terminal_evidence=evidence,
    )
    assert result["exact_current_suite_collection_and_junit_verified"] is True
    for counterfeit in (2.0, True, "2", -1, 3):
        receipt_path = run_root / "run-receipt.json"
        original_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        original_receipt["profiles"]["source-wheel"]["consumers"]["selected_node_ids"] = counterfeit
        receipt_path.write_text(json.dumps(original_receipt), encoding="utf-8")
        with pytest.raises(driver.DriverFailure):
            driver.validate_completed_profile(
                runner,
                manifest,
                run_root,
                "source-wheel",
                expected_timeout_seconds=5,
                terminal_evidence=evidence,
            )
        original_receipt["profiles"]["source-wheel"]["consumers"]["selected_node_ids"] = len(
            {"tests/sample.py::test_sample", "tests/sample.py::test_second"}
        )
        receipt_path.write_text(json.dumps(original_receipt), encoding="utf-8")

    for evidence_key in ("command_record", "stdout", "stderr"):
        for counterfeit in (
            float(evidence[evidence_key]["bytes"]),
            True,
            str(evidence[evidence_key]["bytes"]),
            -1,
            evidence[evidence_key]["bytes"] + 1,
        ):
            bad_evidence = json.loads(json.dumps(evidence))
            bad_evidence[evidence_key]["bytes"] = counterfeit
            with pytest.raises(driver.DriverFailure):
                driver.verify_terminal_command_evidence(bad_evidence)
    for stream_name in ("stdout", "stderr"):
        for counterfeit in (
            float(consumer["process_output"][f"{stream_name}_bytes"]),
            True,
            str(consumer["process_output"][f"{stream_name}_bytes"]),
            -1,
            consumer["process_output"][f"{stream_name}_bytes"] + 1,
        ):
            receipt = json.loads((run_root / "run-receipt.json").read_text(encoding="utf-8"))
            receipt["profiles"]["source-wheel"]["consumers"]["process_output"][
                f"{stream_name}_bytes"
            ] = counterfeit
            (run_root / "run-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            with pytest.raises(driver.DriverFailure):
                driver.validate_completed_profile(
                    runner,
                    manifest,
                    run_root,
                    "source-wheel",
                    expected_timeout_seconds=5,
                    terminal_evidence=evidence,
                )
            receipt["profiles"]["source-wheel"]["consumers"]["process_output"][
                f"{stream_name}_bytes"
            ] = consumer["process_output"][f"{stream_name}_bytes"]
            (run_root / "run-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


def test_q2_schema_versions_use_exact_nonbool_integer_protocol(tmp_path: Path) -> None:
    for matcher in (
        runner_api.exact_nonbool_count_matches,
        supplemental_api.exact_nonbool_count_matches,
        driver.exact_nonbool_count_matches,
        audit_api.exact_nonbool_count_matches,
    ):
        if not matcher(1, 1):
            raise AssertionError("exact version 1 was rejected")
        if not matcher(2, 2):
            raise AssertionError("exact version 2 was rejected")
    for version in (1, 2):
        manifest_path = tmp_path / f"schema-{version}.json"
        manifest_path.write_text(json.dumps({"schema_version": version}), encoding="utf-8")
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        _, manifest, observed_digest = runner_api.load_verified_json_file(
            manifest_path,
            digest,
            "versioned manifest fixture",
            expected_schema_version=version,
        )
        if manifest["schema_version"] != version:
            raise AssertionError("manifest reader changed an exact integer version")
        if observed_digest != digest:
            raise AssertionError("manifest reader changed its verified digest")
        for counterfeit in (True, 1.0, "1", None):
            if matcher(counterfeit, 1):
                raise AssertionError(f"integer alias was accepted: {counterfeit!r}")


def _versioned_primary_fixture(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    product = tmp_path / "product"
    source = product / "assets" / "fixture.bin"
    source.parent.mkdir(parents=True)
    payload = b"resource-payload"
    source.write_bytes(payload)
    (product / "hatch.toml").write_text(
        "[build.targets.wheel.force-include]\n"
        '"assets/fixture.bin" = "polisyos/data_forge/domains/catalog/_resources/fixture.bin"\n'
        "[build.targets.sdist]\n"
        'include = ["assets/fixture.bin"]\n',
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "candidate_baseline": {
            "force_include_count": 1,
            "force_include_assets": [
                {
                    "source": "assets/fixture.bin",
                    "archive": "policy-engine/assets/fixture.bin",
                    "wheel": "polisyos/data_forge/domains/catalog/_resources/fixture.bin",
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            ],
        },
    }
    return product, manifest


def test_primary_asset_manifest_rejects_schema_version_aliases(tmp_path: Path) -> None:
    product, primary = _versioned_primary_fixture(tmp_path)
    positive = runner_api.read_asset_manifest(product, primary)
    if positive != (primary, primary["candidate_baseline"]["force_include_assets"]):
        raise AssertionError("valid schema version 1 did not preserve its manifest")
    for counterfeit in (True, 1.0, "1", None, 2):
        candidate = json.loads(json.dumps(primary))
        candidate["schema_version"] = counterfeit
        with pytest.raises(runner_api.WaveFailure, match="schema version"):
            runner_api.read_asset_manifest(product, candidate)


def test_primary_manifest_file_reader_rejects_schema_version_aliases(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "primary-manifest.json"
    for version in (1, True, 1.0, "1", None, 2):
        manifest_path.write_text(json.dumps({"schema_version": version}), encoding="utf-8")
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        if type(version) is int and version == 1:
            _, manifest, observed_digest = runner_api.load_verified_json_file(
                manifest_path,
                digest,
                "primary manifest fixture",
                expected_schema_version=1,
            )
            if manifest["schema_version"] != 1:
                raise AssertionError("primary manifest version changed during read")
            if observed_digest != digest:
                raise AssertionError("primary manifest digest changed during read")
        else:
            with pytest.raises(runner_api.WaveFailure, match="schema version"):
                runner_api.load_verified_json_file(
                    manifest_path,
                    digest,
                    "primary manifest fixture",
                    expected_schema_version=1,
                )


def test_supplemental_manifest_rejects_schema_version_aliases(
    tmp_path: Path,
) -> None:
    primary_path = tmp_path / "primary-manifest.json"
    primary_path.write_text('{"schema_version": 1}\n', encoding="utf-8")
    primary_sha256 = hashlib.sha256(primary_path.read_bytes()).hexdigest()
    supplemental_path = tmp_path / "supplemental-manifest.json"
    for version in (1, True, 1.0, "1", None, 2):
        supplemental_path.write_text(
            json.dumps(
                {
                    "schema_version": version,
                    "primary_inputs": {
                        "manifest_sha256": primary_sha256,
                        "runner_sha256": "",
                    },
                    "supplemental_suite": {"selectors": ["test_fixture"]},
                }
            ),
            encoding="utf-8",
        )
        args = type(
            "Args",
            (),
            {
                "supplemental_manifest": str(supplemental_path),
                "supplemental_manifest_sha256": hashlib.sha256(
                    supplemental_path.read_bytes()
                ).hexdigest(),
                "primary_manifest": str(primary_path),
                "primary_manifest_sha256": primary_sha256,
            },
        )()
        if type(version) is int and version == 1:
            with pytest.raises(supplemental_api.SupplementalError, match="primary runner bytes"):
                supplemental_api.run_supplement(args)
        else:
            with pytest.raises(supplemental_api.SupplementalError, match="schema"):
                supplemental_api.run_supplement(args)


def test_source_audit_manifest_parser_rejects_schema_version_aliases() -> None:
    parsed = audit_api.parse_json(b'{"schema_version": 1}', "primary fixture")
    if parsed["schema_version"] != 1:
        raise AssertionError("source audit did not preserve valid schema version 1")
    for counterfeit in (True, 1.0, "1", None, 2):
        payload = json.dumps({"schema_version": counterfeit}).encode("utf-8")
        with pytest.raises(audit_api.AuditFailure, match="schema version"):
            audit_api.parse_json(payload, "primary fixture")


def test_source_audit_entrypoint_rejects_primary_schema_alias_before_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = REPO_ROOT
    source_sha, _, _ = _current_audit_binding(repo)
    source_tree = _run_test_process(
        [_git_executable(), "-C", str(repo), "rev-parse", f"{source_sha}^{{tree}}"]
    ).stdout.strip()
    monkeypatch.setattr(audit_api, "require_frozen_checkout", lambda *args: None)
    monkeypatch.setattr(
        audit_api,
        "input_file_records",
        lambda *args, **kwargs: (
            {"supplemental_manifest_path": str(repo / "supplied-supplement.json")},
            {},
        ),
    )
    original_read_bytes = Path.read_bytes
    manifest_path = (repo / audit_api.MANIFEST_REL).resolve(strict=True)

    def read_manifest_bytes(path: Path) -> bytes:
        if path.resolve(strict=False) == manifest_path:
            return current_payload
        return original_read_bytes(path)

    for index, counterfeit in enumerate((True, 1.0, "1", None, 2)):
        current_payload = json.dumps({"schema_version": counterfeit}).encode("utf-8")
        monkeypatch.setattr(
            audit_api,
            "read_commit_blob",
            lambda *args, payload=current_payload: payload,
        )
        monkeypatch.setattr(Path, "read_bytes", read_manifest_bytes)
        args = type(
            "Args",
            (),
            {
                "repo": str(repo),
                "python": sys.executable,
                "collection_timeout_seconds": 1,
                "output_root": str(tmp_path / f"audit-{index}"),
                "source_sha": source_sha,
                "source_tree": source_tree,
                "supplemental_manifest": str(repo / "supplied-supplement.json"),
                "supplemental_manifest_sha256": "c" * 64,
            },
        )()
        with pytest.raises(audit_api.AuditFailure, match="unsupported manifest schema version"):
            audit_api.run_audit(args)


def test_audit_helper_refuses_a_noncanonical_invocation_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = REPO_ROOT
    source_sha, _, _ = _current_audit_binding(repo)
    monkeypatch.setattr(audit_api, "__file__", str(tmp_path / "copied-audit-helper.py"))
    with pytest.raises(audit_api.AuditFailure, match="canonical source path"):
        audit_api.bind_audit_helper(repo, source_sha)


def test_timeout_loader_rejects_primary_schema_version_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner_path = tmp_path / "run.py"
    runner_path.write_bytes((HERE / "run.py").read_bytes())
    runner_sha256 = hashlib.sha256(runner_path.read_bytes()).hexdigest()
    monkeypatch.setattr(driver, "EXPECTED_RUNNER_SHA256", runner_sha256)
    driver_path = tmp_path / "timeout_driver.py"
    manifest_path = tmp_path / "installed-wave-manifest.json"
    for version in (1, True, 1.0, "1", None, 2):
        manifest_path.write_text(json.dumps({"schema_version": version}), encoding="utf-8")
        manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        if type(version) is int and version == 1:
            _, manifest, _, _, _, observed_sha256 = driver._load_reviewed_runner(
                driver_path, manifest_path, manifest_sha256
            )
            if manifest["schema_version"] != 1 or observed_sha256 != manifest_sha256:
                raise AssertionError("timeout reader did not preserve a valid manifest binding")
        else:
            with pytest.raises(driver.DriverFailure, match="schema version"):
                driver._load_reviewed_runner(driver_path, manifest_path, manifest_sha256)


def test_terminal_evidence_rejects_schema_version_aliases(tmp_path: Path) -> None:
    _, _, _, _, evidence = _timeout_profile_fixture(tmp_path)
    verified = driver.verify_terminal_command_evidence(evidence)
    if verified.get("returncode") != 0 or verified.get("timed_out") is not False:
        raise AssertionError("valid terminal evidence did not preserve its command outcome")
    for counterfeit in (True, 1.0, "1", None, 2):
        candidate = json.loads(json.dumps(evidence))
        candidate["schema_version"] = counterfeit
        with pytest.raises(driver.DriverFailure, match="schema version"):
            driver.verify_terminal_command_evidence(candidate)


def test_failure_receipt_type_names_remain_wire_compatible() -> None:
    wave_error = runner_api.WaveFailure("wire-control")
    driver_error = driver.DriverFailure("wire-control")
    actual_runner_sha = hashlib.sha256(Path(runner_api.__file__).read_bytes()).hexdigest()
    assert actual_runner_sha == driver.EXPECTED_RUNNER_SHA256
    assert runner_api.WaveFailureError is runner_api.WaveFailure
    assert driver.DriverFailureError is driver.DriverFailure
    assert runner_api._failure_receipt_text(wave_error) == "WaveFailure: wire-control"
    assert driver._failure_receipt_text(driver_error) == "DriverFailure: wire-control"


def test_primary_runner_cli_preserves_status_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(runner_api, "parse_args", lambda argv=None: object())
    monkeypatch.setattr(runner_api, "run_wave", lambda args: tmp_path / "q2-cli-control")
    assert runner_api.main([]) == 0
    success = capsys.readouterr()
    assert success.out == f"Q2 frozen installed wave passed: {tmp_path / 'q2-cli-control'}\n"
    monkeypatch.setattr(
        runner_api,
        "run_wave",
        lambda args: (_ for _ in ()).throw(runner_api.WaveFailure("cli-control")),
    )
    assert runner_api.main([]) == 1
    failure = capsys.readouterr()
    assert failure.err == "Q2 frozen installed wave failed: cli-control\n"


def test_timeout_driver_cli_preserves_status_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    args = SimpleNamespace(source_sha="a" * 40, source_tree="b" * 40)
    runner = SimpleNamespace(
        parse_args=lambda: args,
        run_wave=lambda _parsed: tmp_path / "timeout-wave",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "timeout_driver.py",
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--manifest-sha256",
            "c" * 64,
        ],
    )
    monkeypatch.setattr(
        driver,
        "_load_reviewed_runner",
        lambda *_args: (
            runner,
            {},
            tmp_path / "runner.py",
            tmp_path / "manifest.json",
            "d" * 64,
            "c" * 64,
        ),
    )
    monkeypatch.setattr(driver, "install_adaptive_run_command", lambda *_args: {})
    monkeypatch.setattr(driver, "_write_calibration_sidecar", lambda *_args, **_kwargs: None)
    assert driver.main() == 0
    success = capsys.readouterr()
    assert success.out == f"Q2 frozen installed wave passed: {tmp_path / 'timeout-wave'}\n"

    def fail(_parsed: object) -> Path:
        raise driver.DriverFailure("timeout-cli-control")

    runner.run_wave = fail
    assert driver.main() == 1
    failure = capsys.readouterr()
    assert failure.err == "Q2 timeout driver failed: timeout-cli-control\n"


def test_collection_capture_binds_external_nonmodules_through_receipt_and_fails_removal() -> None:
    cases = audit_api.self_test_non_module_sys_modules_capture()
    required = {
        "producer-captures-actual-builtin-module",
        "producer-captures-real-six-moves-module-subtype",
        "source-binds-module-subtype-class-to-verified-owner",
        "consumer-refuses-class-with-detached-source-hash",
        "opaque-external-class-state-is-explicitly-unestablished",
        "producer-records-external-nonmodule-with-runtime-type",
        "cyclic-class-data-is-explicitly-not-established",
        "cyclic-module-data-digest-remains-fail-closed",
        "bound-collection-receipt-preserves-module-subtype-and-nonmodule",
        "remove-class-property-keep-markers-fails-closed",
        "consumer-rejects-unsupported-module-inventory-schema",
        "consumer-recomputes-state-instead-of-trusting-marker",
        "consumer-rejects-malformed-opaque-type-record",
        "producer-refuses-unbound-module-subclass-class",
        "producer-refuses-owned-module-subtype-with-opaque-data",
        "producer-refuses-owned-source-nonmodule:polisyos._q2_owned_nonmodule",
        "producer-refuses-owned-source-nonmodule:tools._q2_owned_nonmodule",
        "consumer-refuses-owned-source-nonmodule:polisyos._q2_owned_nonmodule",
        "consumer-refuses-owned-source-nonmodule:tools._q2_owned_nonmodule",
        "producer-refuses-owned-module-alias:polisyos._q2_forged_module_alias",
        "producer-refuses-owned-module-alias:tools._q2_forged_module_alias",
        "consumer-refuses-owned-module-alias:polisyos._q2_forged_module_alias",
        "consumer-refuses-owned-module-alias:tools._q2_forged_module_alias",
    }
    assert required <= cases.keys(), cases
    assert all(cases.values()), cases
