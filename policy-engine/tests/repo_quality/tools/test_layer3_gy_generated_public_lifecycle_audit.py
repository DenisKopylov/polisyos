from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import runpy
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterator
from contextlib import redirect_stderr, redirect_stdout
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if not (REPO_ROOT / "architecture/generated_artifacts.toml").is_file():
    _current = Path.cwd().resolve()
    _product = _current / "policy-engine"
    if (_current / "architecture/generated_artifacts.toml").is_file():
        REPO_ROOT = _current
    elif (_product / "architecture/generated_artifacts.toml").is_file():
        REPO_ROOT = _product
AUDIT_PATH = (
    REPO_ROOT
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_generated_public_lifecycle_audit.json"
)


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=repo_root, check=True)


def _validator() -> Any:
    return import_module(
        "tools.quality.validation.check_layer3_gy_generated_public_lifecycle_audit"
    )


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _row(audit: dict[str, Any], row_id: str) -> dict[str, Any]:
    for row in audit["lifecycle_matrix"]:
        if row.get("row_id") == row_id:
            return row
    raise AssertionError(f"missing row {row_id}")


def _surface(audit: dict[str, Any], surface_id: str) -> dict[str, Any]:
    for row in audit["public_surface_lifecycle"]:
        if row.get("surface_id") == surface_id:
            return row
    raise AssertionError(f"missing surface {surface_id}")


def _negative(audit: dict[str, Any], negative_id: str) -> dict[str, Any]:
    for row in audit["negative_assertions"]:
        if row.get("id") == negative_id:
            return row
    raise AssertionError(f"missing negative assertion {negative_id}")


def test_gy_generated_public_lifecycle_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


@pytest.mark.parametrize("registered", [False, True])
def test_inventory_registration_is_recomputed_from_custody(
    tmp_path: Path, registered: bool
) -> None:
    """The inventory's own custody is a measured registry fact, not a constant."""
    architecture = tmp_path / "architecture"
    (architecture / "policy_design_case").mkdir(parents=True)
    (architecture / "public_surface").mkdir()
    (architecture / "generated_artifacts.toml").write_text(
        '[[family]]\nid = "pdc-source"\noutputs = '
        + ('["architecture/policy_design_case/inventory.json"]' if registered else "[]")
        + "\n",
        encoding="utf-8",
    )
    (architecture / "policy_design_case/inventory.json").write_text(
        '{"artifacts": []}\n', encoding="utf-8"
    )
    (architecture / "public_surface/contract.toml").write_text("", encoding="utf-8")
    report = {
        "discovered_artifacts": [],
        "registered_outputs": [],
        "producer_declared_outputs": [],
        "source_committed_outputs": [],
        "output_root_files": [],
        "unaccounted_output_root_files": [],
        "registered_artifact_count": 0,
        "orphan_count": 0,
        "phantom_output_count": 0,
        "duplicate_claim_count": 0,
    }
    facts = _validator()._lifecycle_facts(tmp_path, report)
    assert facts["policy_design_case_inventory_registered_in_generated_artifacts"] is registered


@pytest.mark.parametrize("suffix", [".blob", ".jsonl"])
def test_output_root_census_includes_unregistered_cas_members(tmp_path: Path, suffix: str) -> None:
    _init_git_repo(tmp_path)
    root = tmp_path / "architecture/cas"
    root.mkdir(parents=True)
    artifact = root / f"unregistered{suffix}"
    artifact.write_bytes(b"source evidence\n")
    observed = _validator()._iter_contract_derived_output_root_files(tmp_path, {"architecture/cas"})
    assert observed == [artifact.relative_to(tmp_path).as_posix()]


def test_output_root_inventory_preserves_file_symlink_members_and_markers(
    tmp_path: Path,
) -> None:
    """Output inventory keeps file links while source-read eligibility rejects them."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_git_repo(repo_root)
    output_root = repo_root / "corr/out"
    output_root.mkdir(parents=True)
    private_inputs = repo_root / "private-inputs"
    private_inputs.mkdir()
    marker_payload = private_inputs / "marker-payload.txt"
    marker_bytes = b'{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n'
    marker_payload.write_bytes(marker_bytes)
    internal_link = output_root / "linked.json"
    internal_link.symlink_to(Path(os.path.relpath(marker_payload, output_root)))

    outside_root = tmp_path / "outside-repository"
    outside_root.mkdir()
    outside_payload = outside_root / "outside-marker.txt"
    outside_payload.write_bytes(marker_bytes)
    external_link = output_root / "external.json"
    external_link.symlink_to(outside_payload)

    validator = _load_source_read_candidate_validator()
    output_files = validator._iter_contract_derived_output_root_files(repo_root, {"corr/out"})
    internal_relative = internal_link.relative_to(repo_root).as_posix()
    external_relative = external_link.relative_to(repo_root).as_posix()
    assert output_files == sorted([internal_relative, external_relative])
    assert validator._repo_file_is_safe(repo_root, internal_relative)
    assert not validator._repo_source_file_is_safe(repo_root, internal_relative)
    assert not validator._repo_file_is_safe(repo_root, external_relative)

    markers = validator._iter_gy_marked_artifact_files(
        repo_root, (set(), set()), extra_candidate_paths=output_files
    )
    assert markers == [internal_relative]

    snapshot_before = validator._snapshot_selected_output_root_files(repo_root, {"corr/out"})
    assert snapshot_before is not None
    assert set(snapshot_before) == {internal_relative, external_relative}
    assert snapshot_before[internal_relative][0] == "symlink"
    assert snapshot_before[external_relative][0] == "symlink"

    second_payload = private_inputs / "second-marker-payload.txt"
    second_payload.write_bytes(marker_bytes)
    internal_link.unlink()
    internal_link.symlink_to(Path(os.path.relpath(second_payload, output_root)))
    snapshot_after = validator._snapshot_selected_output_root_files(repo_root, {"corr/out"})
    assert snapshot_after is not None
    assert snapshot_after != snapshot_before


def test_complete_output_root_membership_does_not_depend_on_marker_format_or_scope(
    tmp_path: Path,
) -> None:
    """Every current root member stays accountable when marker parsing cannot classify it."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    repo_root = _write_ignored_owner_output_registry(
        repo_root,
        source="generated_artifacts",
        output_declaration='["owner-output/manifest.json"]',
    )
    root = repo_root / "owner-output/nested"
    private = repo_root / "private-inputs"
    private.mkdir()
    marker = b'{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n'
    marker_txt = root / "committed-marker.txt"
    marker_txt.write_bytes(marker)
    excluded_marker = root / "excluded-marker.json"
    excluded_marker.write_bytes(marker)
    no_extension = root / "unclassified-marker"
    no_extension.write_bytes(marker)
    corrupt_json = root / "corrupt.json"
    corrupt_json.write_bytes(b"\xff\x00not-json")
    opaque_binary = root / "opaque.bin"
    opaque_binary.write_bytes(b"\x00\xff\x01")
    source = private / "source.json"
    source.write_bytes(b'{"source":"ordinary"}\n')
    hardlink_alias = root / "source-alias.bin"
    os.link(source, hardlink_alias)
    internal_link = root / "internal-link.json"
    internal_link.symlink_to(Path(os.path.relpath(source, root)))
    dangling_link = root / "dangling-link.json"
    dangling_link.symlink_to("missing-target.json")
    outside = tmp_path / "outside"
    outside.mkdir()
    hidden_marker = outside / "hidden.json"
    hidden_marker.write_bytes(marker)
    directory_link = root / "directory-link"
    directory_link.symlink_to(outside, target_is_directory=True)
    fifo = root / "nonregular.pipe"
    if hasattr(os, "mkfifo"):
        os.mkfifo(fifo)

    generated = repo_root / "architecture/generated_artifacts.toml"
    with generated.open("a", encoding="utf-8") as stream:
        stream.write(
            "\n[[gy_marker_scan_exclusion]]\n"
            'id = "explicit-marker-scan-exclusion"\n'
            'owner = "tests"\n'
            'rationale = "the marker classifier intentionally excludes this exact path"\n'
            'paths = ["owner-output/nested/excluded-marker.json"]\n'
        )

    tracked = [
        "owner-output/nested/committed-marker.txt",
        "owner-output/nested/excluded-marker.json",
        "owner-output/nested/unclassified-marker",
        "owner-output/nested/corrupt.json",
        "owner-output/nested/opaque.bin",
        "private-inputs/source.json",
        "owner-output/nested/source-alias.bin",
        "owner-output/nested/internal-link.json",
        "owner-output/nested/dangling-link.json",
        "owner-output/nested/directory-link",
    ]
    subprocess.run(["git", "add", "--force", "--", *tracked], cwd=repo_root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "fixture members",
        ],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", tracked[0]],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    validator = _validator()
    report = validator.validate_gy_lifecycle_registry(repo_root)
    expected = set(tracked) - {"private-inputs/source.json"}
    expected.update(
        {
            "owner-output/manifest.json",
            "owner-output/nested/marker.json",
        }
    )
    if hasattr(os, "mkfifo"):
        expected.add("owner-output/nested/nonregular.pipe")
    assert expected <= set(report["output_root_files"])
    assert expected - {"owner-output/nested/marker.json"} <= set(
        report["unaccounted_output_root_files"]
    )
    assert "owner-output/nested/committed-marker.txt" not in report["marker_detected_outputs"]
    assert "owner-output/nested/excluded-marker.json" not in report["marker_detected_outputs"]
    assert any(
        issue.get("code") == "layer3_gy_unaccounted_output_root_file"
        and issue.get("path") == "owner-output/nested/committed-marker.txt"
        for issue in report["issues"]
    )
    assert "owner-output/nested/directory-link/hidden.json" not in report["output_root_files"]

    snapshot_before = validator._snapshot_selected_output_root_files(
        repo_root,
        {"owner-output"},
    )
    assert snapshot_before is not None
    assert expected <= set(snapshot_before)
    if hasattr(os, "mkfifo"):
        assert snapshot_before["owner-output/nested/nonregular.pipe"][0] == "other"
    assert snapshot_before["owner-output/nested/directory-link"][0] == "symlink"

    marker_txt.write_bytes(marker + b"changed\n")
    snapshot_after_content_change = validator._snapshot_selected_output_root_files(
        repo_root,
        {"owner-output"},
    )
    assert snapshot_after_content_change is not None
    assert snapshot_after_content_change != snapshot_before

    new_member = root / "fresh-untracked-no-extension"
    new_member.write_bytes(b"new output")
    snapshot_after_addition = validator._snapshot_selected_output_root_files(
        repo_root,
        {"owner-output"},
    )
    assert snapshot_after_addition is not None
    assert "owner-output/nested/fresh-untracked-no-extension" in snapshot_after_addition
    assert snapshot_after_addition != snapshot_after_content_change
    new_member.unlink()
    snapshot_after_removal = validator._snapshot_selected_output_root_files(
        repo_root,
        {"owner-output"},
    )
    assert snapshot_after_removal == snapshot_after_content_change


def test_missing_committed_output_root_member_remains_unaccounted(tmp_path: Path) -> None:
    """A committed selected-root member cannot disappear when its worktree file is absent."""
    repo_root = _write_ignored_owner_output_registry(
        tmp_path,
        source="generated_artifacts",
        output_declaration='["owner-output/manifest.json"]',
    )
    missing_relative = "owner-output/nested/missing-committed.txt"
    missing_path = repo_root / missing_relative
    missing_path.write_text("committed output member\n", encoding="utf-8")
    subprocess.run(["git", "add", "--force", "--", missing_relative], cwd=repo_root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "committed selected-root member",
        ],
        cwd=repo_root,
        check=True,
    )
    missing_path.unlink()

    validator = _validator()
    report = validator.validate_gy_lifecycle_registry(repo_root)
    assert missing_relative in report["output_root_files"]
    assert missing_relative in report["unaccounted_output_root_files"]
    assert any(
        issue.get("code") == "layer3_gy_unaccounted_output_root_file"
        and issue.get("path") == missing_relative
        for issue in report["issues"]
    )
    assert validator._snapshot_selected_output_root_files(repo_root, {"owner-output"}) is None


def test_committed_members_are_scoped_to_nested_product_roots(tmp_path: Path) -> None:
    """Git tree membership uses the product prefix and only selected roots."""
    _init_git_repo(tmp_path)
    product_root = tmp_path / "product"
    selected = product_root / "owner-output/nested/committed.bin"
    unrelated = tmp_path / "unrelated/committed.bin"
    selected.parent.mkdir(parents=True)
    unrelated.parent.mkdir()
    selected.write_bytes(b"selected")
    unrelated.write_bytes(b"outside selected root")
    subprocess.run(
        [
            "git",
            "add",
            "--",
            "product/owner-output/nested/committed.bin",
            "unrelated/committed.bin",
        ],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "nested product roots",
        ],
        cwd=tmp_path,
        check=True,
    )
    selected.unlink()

    validator = _validator()
    members, incomplete = validator._committed_output_root_member_paths(
        product_root, ("owner-output",)
    )
    assert members == ("owner-output/nested/committed.bin",)
    assert incomplete == ()


def test_unreadable_output_subtree_is_typed_and_never_a_green_empty_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed subtree read rejects the inventory and source-read snapshot."""
    repo_root = tmp_path / "repo"
    selected_root = repo_root / "corr/out"
    (selected_root / "locked").mkdir(parents=True)
    _init_git_repo(repo_root)
    validator = _validator()
    original_walk = validator.os.walk

    def denied_walk(
        root: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        del args
        onerror = kwargs["onerror"]
        onerror(PermissionError(13, "permission denied", str(Path(root) / "locked")))
        yield str(root), ["locked"], []

    monkeypatch.setattr(validator.os, "walk", denied_walk)
    issues: list[dict[str, Any]] = []
    assert (
        validator._iter_contract_derived_output_root_files(
            repo_root,
            {"corr/out"},
            issues=issues,
        )
        == []
    )
    assert issues == [
        {
            "code": "layer3_gy_output_root_inventory_incomplete",
            "path": "corr/out/locked",
        }
    ]
    assert validator._snapshot_selected_output_root_files(repo_root, {"corr/out"}) is None


@pytest.mark.parametrize(
    ("prefix", "schema"),
    [
        ("policyos.gy_n10.cg1_l2_prior_census", "policyos.gy_n10.cg1_l2_prior_census.compact.v1"),
        (
            "policyos.policy_design_case.gy_n13a.acquisition_census",
            "policyos.policy_design_case.gy_n13a.acquisition_census.v1",
        ),
        ("policyos.layer3.gy.n13b", "policyos.layer3.gy.n13b.lifecycle_manifest.v3"),
    ],
)
def test_actual_producer_namespaces_have_bounded_lifecycle_custody(
    tmp_path: Path, prefix: str, schema: str
) -> None:
    artifact = tmp_path / "receipt.json"
    artifact.write_text(json.dumps({"schema_version": schema}), encoding="utf-8")
    family = {"id": "actual-owner", "lifecycle_schema_prefixes": [prefix]}
    issues = []
    validator = _validator()
    assert validator._family_lifecycle_schema_prefixes(family, issues) == (prefix,)
    validator._validate_producer_output_provenance(tmp_path, family, "receipt.json", issues)
    assert issues == []


@pytest.mark.parametrize(
    "prefix",
    [
        "policyos",
        "policyos.layer3",
        "policyos.layer3.gy",
        "policyos.gy_",
        "policyos.policy_design_case",
    ],
)
def test_lifecycle_custody_rejects_unbounded_namespaces(prefix: str) -> None:
    assert not _validator()._is_bounded_family_lifecycle_schema_prefix(prefix)


def test_inventory_byte_drift_reaches_its_registered_verifier(tmp_path: Path) -> None:
    """Exercise the real registry's inventory owner through M1's actual consumer."""
    _init_git_repo(tmp_path)
    relative = "architecture/policy_design_case/inventory.json"
    registry = (REPO_ROOT / "architecture/generated_artifacts.toml").read_text()
    blocks = ["[[family]]" + block for block in registry.split("[[family]]")[1:]]
    owners = [
        block
        for block in blocks
        if relative in tomllib.loads(block)["family"][0].get("outputs", [])
    ]
    assert len(owners) == 1
    inventory = tmp_path / relative
    inventory.parent.mkdir(parents=True)
    inventory.write_bytes((REPO_ROOT / relative).read_bytes())
    digest = "sha256:" + hashlib.sha256(inventory.read_bytes()).hexdigest()
    block = re.sub(
        r'(source_integrity_sha256\."' + re.escape(relative) + r'" = ")[^"]+("\s*)',
        lambda match: match[1] + digest + match[2],
        owners[0],
    )
    (tmp_path / "architecture/generated_artifacts.toml").write_text(block)
    validator = _validator()
    before = validator.validate_gy_lifecycle_registry(tmp_path)
    assert not any(
        issue["code"] == "layer3_gy_source_output_integrity_drift" for issue in before["issues"]
    )
    inventory.write_bytes(inventory.read_bytes() + b"\n")
    after = validator.validate_gy_lifecycle_registry(tmp_path)
    assert any(
        issue["code"] == "layer3_gy_source_output_integrity_drift" and issue.get("path") == relative
        for issue in after["issues"]
    )


def test_real_alternative_namespaces_are_discovered_without_registration(tmp_path: Path) -> None:
    """Removing an entire family cannot hide its real producer's schema markers."""
    _init_git_repo(tmp_path)
    family_ids = {
        "policy-design-case-layer3-gy-n10-cg1-l2-relation-census",
        "policy-design-case-layer3-gy-n13a-acquisition-census",
        "policy-design-case-layer3-gy-n13b-acquisition-executor",
    }
    families = tomllib.loads((REPO_ROOT / "architecture/generated_artifacts.toml").read_text())[
        "family"
    ]
    selected = [family for family in families if family["id"] in family_ids]
    assert {family["id"] for family in selected} == family_ids
    expected = set()
    for family in selected:
        assert family["outputs"]
        for relative in family["outputs"]:
            destination = tmp_path / "new-location" / Path(relative).name
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes((REPO_ROOT / relative).read_bytes())
            expected.add(destination.relative_to(tmp_path).as_posix())
    assert expected == {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*.json")}
    assert set(_validator()._iter_gy_marked_artifact_files(tmp_path, (set(), set()))) == expected


def test_marker_scan_covers_git_visible_files_and_refreshes_after_mutation(tmp_path: Path) -> None:
    git_root = tmp_path
    repo_root = git_root / "product"
    repo_root.mkdir()
    _init_git_repo(git_root)
    (repo_root / ".gitignore").write_text("ignored-source/\nowner-output/\n", encoding="utf-8")
    tracked = repo_root / "tracked.json"
    tracked.write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "product/tracked.json"], cwd=git_root, check=True)
    sibling = git_root / "sibling.json"
    sibling.write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    fresh = repo_root / "fresh-scope" / "new_marker.json"
    ignored = repo_root / "ignored-source" / "hidden.json"
    ignored.parent.mkdir()
    ignored.write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    with tempfile.TemporaryDirectory(dir=tmp_path.parent) as outside_dir:
        outside = Path(outside_dir)
        (outside / "external.json").write_text(
            '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
            encoding="utf-8",
        )
        (repo_root / "linked-source").symlink_to(outside, target_is_directory=True)
        validator = _validator()
        observed = set(validator._iter_gy_marked_artifact_files(repo_root, (set(), set())))
        assert observed == {"tracked.json"}

        fresh.parent.mkdir()
        fresh.write_text(
            '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
            encoding="utf-8",
        )
        assert set(validator._iter_gy_marked_artifact_files(repo_root, (set(), set()))) == {
            "tracked.json",
            "fresh-scope/new_marker.json",
        }
        ignore_file = repo_root / ".gitignore"
        ignore_file.write_text(
            "ignored-source/\nowner-output/\nfresh-scope/new_marker.json\n",
            encoding="utf-8",
        )
        assert set(validator._iter_gy_marked_artifact_files(repo_root, (set(), set()))) == {
            "tracked.json"
        }
        ignore_file.write_text("ignored-source/\nowner-output/\n", encoding="utf-8")
        assert set(validator._iter_gy_marked_artifact_files(repo_root, (set(), set()))) == {
            "tracked.json",
            "fresh-scope/new_marker.json",
        }
        fresh.write_text('{"schema_version":"ordinary.v1"}\n', encoding="utf-8")
        assert set(validator._iter_gy_marked_artifact_files(repo_root, (set(), set()))) == {
            "tracked.json"
        }
        fresh.write_text(
            '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
            encoding="utf-8",
        )
        assert "fresh-scope/new_marker.json" in set(
            validator._iter_gy_marked_artifact_files(repo_root, (set(), set()))
        )
        fresh.unlink()
        assert set(validator._iter_gy_marked_artifact_files(repo_root, (set(), set()))) == {
            "tracked.json"
        }


@pytest.mark.parametrize(
    "output_path",
    [
        "nested/deep/../marker.json",
        "nested/../marker.json",
        "../marker.json",
        "/nested/marker.json",
        "C:/nested/marker.json",
        "nested\\marker.json",
        "nested//marker.json",
        "nested/./marker.json",
        " nested/marker.json",
        "nested/marker.json/",
    ],
)
@pytest.mark.parametrize("source", ["generated_artifacts", "public_surface", "producer"])
def test_malformed_declared_gy_output_path_refuses_without_root_walk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    output_path: str,
) -> None:
    """Malformed output declarations must not widen an owner-root scan."""
    _init_git_repo(tmp_path)
    nested = tmp_path / "nested" / "deep"
    nested.mkdir(parents=True)
    marker = tmp_path / "nested" / "marker.json"
    marker.write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    architecture = tmp_path / "architecture"
    architecture.mkdir()
    family_output = json.dumps(output_path)
    (architecture / "generated_artifacts.toml").write_text(
        "[[family]]\n"
        'id = "gy-path-probe"\n'
        'owner = "tests"\n'
        "gy_lifecycle_family = true\n"
        + (
            'lifecycle = "generated_committed"\n'
            if source == "producer"
            else 'lifecycle = "surface_out_of_scope"\n'
        )
        + ('workflow = "tools/gy_path_probe.py"\n' if source == "producer" else "")
        + (
            'surface_out_of_scope_rationale = "path validation fixture"\n'
            if source != "producer"
            else ""
        )
        + (
            "outputs = [" + family_output + "]\n"
            if source == "generated_artifacts"
            else "outputs = []\n"
        ),
        encoding="utf-8",
    )
    if source == "producer":
        workflow = tmp_path / "tools/gy_path_probe.py"
        workflow.parent.mkdir()
        workflow.write_text(
            "OUTPUTS = [" + family_output + "]\n\ndef declared_outputs():\n    return OUTPUTS\n",
            encoding="utf-8",
        )
    public_surface = architecture / "public_surface"
    public_surface.mkdir()
    (public_surface / "contract.toml").write_text(
        "[[generated_artifact_family]]\n"
        'id = "gy-path-probe"\n'
        + (
            "outputs = [" + family_output + "]\n"
            if source == "public_surface"
            else "outputs = []\n"
        ),
        encoding="utf-8",
    )

    validator = _validator()
    walked: list[Path] = []
    original_walk = validator.os.walk

    def recording_walk(
        root: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        walked.append(Path(root))
        yield from original_walk(root, *args, **kwargs)

    monkeypatch.setattr(validator.os, "walk", recording_walk)
    report = validator.validate_gy_lifecycle_registry(tmp_path)
    expected_code = (
        "layer3_gy_producer_declared_output_bad_path"
        if source == "producer"
        else "layer3_gy_output_path_bad_path"
    )

    assert report["status"] == "fail"
    assert any(
        issue.get("code") == expected_code and issue.get("path") == output_path
        for issue in report["issues"]
    )
    assert "nested/marker.json" in report["marker_detected_outputs"]
    assert walked == []


@pytest.mark.parametrize(
    ("toml_value", "python_value", "expected_type"),
    [
        ("42", "42", "int"),
        ("true", "True", "bool"),
        ('["nested/deep/marker.json"]', '["nested/deep/marker.json"]', "list"),
        (
            '{path = "nested/deep/marker.json"}',
            '{"path": "nested/deep/marker.json"}',
            "dict",
        ),
    ],
)
@pytest.mark.parametrize("source", ["generated_artifacts", "public_surface", "producer"])
def test_non_string_declared_gy_output_values_refuse_without_root_walk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    toml_value: str,
    python_value: str,
    expected_type: str,
) -> None:
    """Non-string declarations must fail before deriving an output root."""
    _init_git_repo(tmp_path)
    nested = tmp_path / "nested" / "deep"
    nested.mkdir(parents=True)
    marker = tmp_path / "nested" / "marker.json"
    marker.write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    architecture = tmp_path / "architecture"
    architecture.mkdir()
    (architecture / "generated_artifacts.toml").write_text(
        "[[family]]\n"
        'id = "gy-path-probe"\n'
        'owner = "tests"\n'
        "gy_lifecycle_family = true\n"
        + (
            'lifecycle = "generated_committed"\n'
            if source == "producer"
            else 'lifecycle = "surface_out_of_scope"\n'
        )
        + ('workflow = "tools/gy_path_probe.py"\n' if source == "producer" else "")
        + (
            'surface_out_of_scope_rationale = "path validation fixture"\n'
            if source != "producer"
            else ""
        )
        + (
            "outputs = [" + toml_value + "]\n"
            if source == "generated_artifacts"
            else "outputs = []\n"
        ),
        encoding="utf-8",
    )
    if source == "producer":
        workflow = tmp_path / "tools/gy_path_probe.py"
        workflow.parent.mkdir()
        workflow.write_text(
            "OUTPUTS = [" + python_value + "]\ndef declared_outputs():\n    return OUTPUTS\n",
            encoding="utf-8",
        )
    public_surface = architecture / "public_surface"
    public_surface.mkdir()
    (public_surface / "contract.toml").write_text(
        "[[generated_artifact_family]]\n"
        'id = "gy-path-probe"\n'
        + ("outputs = [" + toml_value + "]\n" if source == "public_surface" else "outputs = []\n"),
        encoding="utf-8",
    )

    validator = _validator()
    walked: list[Path] = []
    original_walk = validator.os.walk

    def recording_walk(
        root: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        walked.append(Path(root))
        yield from original_walk(root, *args, **kwargs)

    monkeypatch.setattr(validator.os, "walk", recording_walk)
    report = validator.validate_gy_lifecycle_registry(tmp_path)
    expected_code = (
        "layer3_gy_producer_declared_output_bad_type"
        if source == "producer"
        else "layer3_gy_output_path_bad_type"
    )

    assert report["status"] == "fail"
    assert any(
        issue.get("code") == expected_code
        and issue.get("value_type") == expected_type
        and "path" not in issue
        for issue in report["issues"]
    )
    assert "nested/marker.json" in report["marker_detected_outputs"]
    assert walked == []


def test_producer_path_object_is_not_stringified_into_an_output_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path-like object cannot gain authority by stringifying to a valid path."""
    _init_git_repo(tmp_path)
    nested = tmp_path / "nested" / "deep"
    nested.mkdir(parents=True)
    marker = tmp_path / "nested" / "marker.json"
    marker.write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    architecture = tmp_path / "architecture"
    architecture.mkdir()
    (architecture / "generated_artifacts.toml").write_text(
        "[[family]]\n"
        'id = "gy-path-probe"\n'
        'owner = "tests"\n'
        "gy_lifecycle_family = true\n"
        'lifecycle = "generated_committed"\n'
        'workflow = "tools/gy_path_probe.py"\n'
        "outputs = []\n",
        encoding="utf-8",
    )
    workflow = tmp_path / "tools/gy_path_probe.py"
    workflow.parent.mkdir()
    workflow.write_text(
        "class OutputPath:\n"
        "    def __str__(self):\n        return 'nested/marker.json'\n\n"
        "def declared_outputs():\n    return [OutputPath()]\n",
        encoding="utf-8",
    )
    public_surface = architecture / "public_surface"
    public_surface.mkdir()
    (public_surface / "contract.toml").write_text(
        '[[generated_artifact_family]]\nid = "gy-path-probe"\noutputs = []\n',
        encoding="utf-8",
    )

    validator = _validator()
    walked: list[Path] = []
    original_walk = validator.os.walk

    def recording_walk(
        root: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        walked.append(Path(root))
        yield from original_walk(root, *args, **kwargs)

    monkeypatch.setattr(validator.os, "walk", recording_walk)
    report = validator.validate_gy_lifecycle_registry(tmp_path)

    assert report["status"] == "fail"
    assert any(
        issue.get("code") == "layer3_gy_producer_declared_output_bad_type"
        and issue.get("value_type") == "OutputPath"
        and "path" not in issue
        for issue in report["issues"]
    )
    assert "nested/marker.json" in report["marker_detected_outputs"]
    assert walked == []


def test_git_prefix_preserves_carriage_return_path_components(tmp_path: Path) -> None:
    """The Git prefix terminator is removed without rewriting valid POSIX names."""
    _init_git_repo(tmp_path)
    repo_root = tmp_path / "nested\rproduct"
    repo_root.mkdir()
    marker = repo_root / "marker.json"
    marker.write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )

    validator = _validator()
    assert validator._git_worktree_prefix(repo_root) == "nested\rproduct"
    assert validator._iter_gy_marked_artifact_files(repo_root, (set(), set())) == ["marker.json"]


def _write_ignored_owner_output_registry(
    tmp_path: Path,
    *,
    source: str,
    output_declaration: str | None = None,
    producer_return: str | None = None,
) -> Path:
    _init_git_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("owner-output/\n", encoding="utf-8")
    owner_root = tmp_path / "owner-output"
    nested = owner_root / "nested"
    nested.mkdir(parents=True)
    (owner_root / "manifest.json").write_text('{"kind":"ordinary"}\n', encoding="utf-8")
    marker = nested / "marker.json"
    marker.write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )

    architecture = tmp_path / "architecture"
    architecture.mkdir()
    family_lines = [
        "[[family]]",
        'id = "gy-path-probe"',
        'owner = "tests"',
        "gy_lifecycle_family = true",
    ]
    if source == "producer":
        family_lines.extend(
            [
                'lifecycle = "generated_committed"',
                'workflow = "tools/gy_path_probe.py"',
                "outputs = []",
            ]
        )
        workflow = tmp_path / "tools/gy_path_probe.py"
        workflow.parent.mkdir()
        workflow.write_text(
            "def declared_outputs():\n    return " + str(producer_return) + "\n",
            encoding="utf-8",
        )
    else:
        family_lines.extend(
            [
                'lifecycle = "surface_out_of_scope"',
                'surface_out_of_scope_rationale = "output collection fixture"',
            ]
        )
        if source == "generated_artifacts":
            if output_declaration is not None:
                family_lines.append("outputs = " + output_declaration)
        else:
            family_lines.append("outputs = []")
    (architecture / "generated_artifacts.toml").write_text(
        "\n".join(family_lines) + "\n", encoding="utf-8"
    )

    public_surface = architecture / "public_surface"
    public_surface.mkdir()
    contract_lines = [
        "[[generated_artifact_family]]",
        'id = "gy-path-probe"',
    ]
    if source == "public_surface":
        if output_declaration is not None:
            contract_lines.append("outputs = " + output_declaration)
    else:
        contract_lines.append("outputs = []")
    (public_surface / "contract.toml").write_text(
        "\n".join(contract_lines) + "\n", encoding="utf-8"
    )
    assert marker.is_file()
    return tmp_path


@pytest.mark.parametrize(
    ("toml_value", "python_expression", "expected_type"),
    [
        pytest.param("false", "False", "bool", id="false"),
        pytest.param("true", "True", "bool", id="true"),
        pytest.param("0", "0", "int", id="zero"),
        pytest.param("7", "7", "int", id="positive-int"),
        pytest.param('""', '""', "str", id="empty-string"),
        pytest.param(
            '"owner-output/manifest.json"',
            '"owner-output/manifest.json"',
            "str",
            id="nonempty-string",
        ),
        pytest.param("{}", "{}", "dict", id="empty-mapping"),
        pytest.param(
            '{path = "owner-output/manifest.json"}',
            '{"path": "owner-output/manifest.json"}',
            "dict",
            id="nonempty-mapping",
        ),
    ],
)
@pytest.mark.parametrize("source", ["generated_artifacts", "public_surface", "producer"])
def test_non_collection_declared_outputs_fail_closed_before_root_walk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    toml_value: str,
    python_expression: str,
    expected_type: str,
) -> None:
    """Present scalar output collections cannot suppress an ignored-root scan."""
    repo_root = _write_ignored_owner_output_registry(
        tmp_path,
        source=source,
        output_declaration=toml_value,
        producer_return=python_expression,
    )
    validator = _validator()
    walked: list[Path] = []
    original_walk = validator.os.walk

    def recording_walk(
        root: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        walked.append(Path(root))
        yield from original_walk(root, *args, **kwargs)

    monkeypatch.setattr(validator.os, "walk", recording_walk)
    report = validator.validate_gy_lifecycle_registry(repo_root)
    expected_code = (
        "layer3_gy_producer_declared_outputs_bad_type"
        if source == "producer"
        else "layer3_gy_output_paths_bad_type"
    )
    expected_source = {
        "generated_artifacts": "generated_artifacts.family.outputs",
        "public_surface": "public_surface.generated_artifact_family.outputs",
        "producer": "workflow.declared_outputs",
    }[source]
    marker_path = "owner-output/nested/marker.json"

    assert report["status"] == "fail"
    assert any(
        issue.get("code") == expected_code
        and issue.get("source") == expected_source
        and issue.get("value_type") == expected_type
        and "path" not in issue
        for issue in report["issues"]
    )
    assert (repo_root / marker_path).is_file()
    assert marker_path not in report["marker_detected_outputs"]
    assert report["output_root_files"] == []
    assert walked == []


def test_producer_none_output_collection_fails_closed_before_root_walk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A producer cannot use None to suppress its declared output collection."""
    repo_root = _write_ignored_owner_output_registry(
        tmp_path,
        source="producer",
        producer_return="None",
    )
    validator = _validator()
    walked: list[Path] = []
    original_walk = validator.os.walk

    def recording_walk(
        root: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        walked.append(Path(root))
        yield from original_walk(root, *args, **kwargs)

    monkeypatch.setattr(validator.os, "walk", recording_walk)
    report = validator.validate_gy_lifecycle_registry(repo_root)

    assert report["status"] == "fail"
    assert any(
        issue.get("code") == "layer3_gy_producer_declared_outputs_bad_type"
        and issue.get("value_type") == "NoneType"
        for issue in report["issues"]
    )
    assert "owner-output/nested/marker.json" not in report["marker_detected_outputs"]
    assert report["output_root_files"] == []
    assert walked == []


@pytest.mark.parametrize(
    ("source", "output_declaration", "producer_return"),
    [
        pytest.param("generated_artifacts", None, None, id="family-absent-default"),
        pytest.param("generated_artifacts", "[]", None, id="family-empty-list"),
        pytest.param("public_surface", None, None, id="surface-absent-default"),
        pytest.param("public_surface", "[]", None, id="surface-empty-list"),
        pytest.param("producer", None, "[]", id="producer-empty-list"),
    ],
)
def test_absent_and_empty_output_collections_remain_valid_defaults(
    tmp_path: Path,
    source: str,
    output_declaration: str | None,
    producer_return: str | None,
) -> None:
    """Absent collection defaults and explicit empty lists remain admissible."""
    repo_root = _write_ignored_owner_output_registry(
        tmp_path,
        source=source,
        output_declaration=output_declaration,
        producer_return=producer_return,
    )
    report = _validator().validate_gy_lifecycle_registry(repo_root)

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert report["output_root_files"] == []
    assert "owner-output/nested/marker.json" not in report["marker_detected_outputs"]
    assert (repo_root / "owner-output/nested/marker.json").is_file()


@pytest.mark.parametrize("source", ["generated_artifacts", "public_surface", "producer"])
def test_declared_output_roots_reveal_ignored_owner_markers(tmp_path: Path, source: str) -> None:
    """A correctly typed root declaration still reveals fresh ignored markers."""
    repo_root = _write_ignored_owner_output_registry(
        tmp_path,
        source=source,
        output_declaration='["owner-output/manifest.json"]',
        producer_return='["owner-output/manifest.json"]',
    )
    report = _validator().validate_gy_lifecycle_registry(repo_root)

    assert "owner-output/nested/marker.json" in report["output_root_files"]
    assert "owner-output/nested/marker.json" in report["marker_detected_outputs"]
    assert not any(
        issue.get("code")
        in {
            "layer3_gy_output_paths_bad_type",
            "layer3_gy_output_path_bad_type",
            "layer3_gy_producer_declared_outputs_bad_type",
            "layer3_gy_producer_declared_output_bad_type",
        }
        for issue in report["issues"]
    )


def test_output_root_walks_overlapping_roots_once_and_records_directory_symlink_leaves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path
    _init_git_repo(repo_root)
    owner_root = repo_root / "owner-output"
    nested = owner_root / "nested"
    nested.mkdir(parents=True)
    (repo_root / ".gitignore").write_text("owner-output/\n", encoding="utf-8")
    owned = nested / "untracked.json"
    owned.write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    with tempfile.TemporaryDirectory(dir=tmp_path.parent) as outside_dir:
        outside = Path(outside_dir)
        (outside / "external.json").write_text('{"schema_version":"ordinary.v1"}\n')
        (owner_root / "linked").symlink_to(outside, target_is_directory=True)

        validator = _validator()
        original_walk = validator.os.walk
        visited_roots: list[str] = []

        def recording_walk(
            root: str | Path,
            *args: Any,
            **kwargs: Any,
        ) -> Iterator[tuple[str, list[str], list[str]]]:
            visited_roots.append(Path(root).relative_to(repo_root).as_posix())
            yield from original_walk(root, *args, **kwargs)

        monkeypatch.setattr(validator.os, "walk", recording_walk)
        observed = validator._iter_contract_derived_output_root_files(
            repo_root,
            {"owner-output", "owner-output/nested"},
        )

        assert observed == ["owner-output/linked", "owner-output/nested/untracked.json"]
        assert visited_roots == ["owner-output"]
        markers = validator._iter_gy_marked_artifact_files(
            repo_root,
            (set(), set()),
            extra_candidate_paths=observed,
        )
        assert markers == ["owner-output/nested/untracked.json"]
        assert visited_roots == ["owner-output"]


def test_gy_generated_public_lifecycle_rejects_missing_gy_family_registration() -> None:
    validator = _validator()
    audit = _load_audit()
    gy = _row(audit, "layer3_gy_task0_audit_artifacts")
    gy["registered"] = False
    gy["family_id"] = None
    gy["outputs_registered_count"] = 0
    gy["stale_output_behavior"] = "missing_registry"
    audit["summary"]["gy_generated_family_registered"] = False
    audit["summary"]["gy_artifact_files_registered_count"] = 0

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "gy_family_registration_drift" in codes
    assert "gy_family_id_drift" in codes
    assert "gy_registered_output_count_drift" in codes
    assert "gy_stale_policy_drift" in codes


def test_gy_generated_public_lifecycle_rejects_public_surface_family_drift() -> None:
    validator = _validator()
    audit = _load_audit()
    surface = _surface(audit, "policy_design_case_generated_audit_surfaces_section")
    surface["gy_surface_registered"] = False
    audit["summary"]["gy_public_surface_family_registered"] = False

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "gy_public_surface_registration_drift" in codes


def test_gy_generated_public_lifecycle_rejects_projection_refs_as_api_enforcement() -> None:
    validator = _validator()
    audit = _load_audit()
    projection = _surface(audit, "layer3_public_export_projection_refs")
    projection["api_dashboard_enforcement"] = True
    projection["public_export_route_registered"] = True
    _negative(
        audit,
        "do_not_count_projection_refs_as_api_dashboard_enforcement",
    )["assertion_holds"] = False

    codes = _codes(validator.validate(audit))
    assert "projection_refs_api_enforcement_laundering" in codes
    assert "projection_refs_public_export_laundering" in codes
    assert "negative_assertion_not_enforced" in codes


def test_gy_generated_public_lifecycle_rejects_missing_registered_stale_policy() -> None:
    validator = _validator()
    audit = _load_audit()
    openapi = _row(audit, "runtime_openapi_snapshot")
    openapi["stale_output_behavior"] = ""

    codes = _codes(validator.validate(audit))
    assert "registered_family_missing_lifecycle_metadata" in codes


def test_gy_generated_public_lifecycle_rejects_missing_pdc_inventory_gy_entries() -> None:
    validator = _validator()
    audit = _load_audit()
    pdc = _row(audit, "policy_design_case_inventory")
    pdc["contains_gy_entries"] = False
    audit["summary"]["policy_design_case_inventory_gy_entries"] = 0

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "pdc_inventory_gy_entry_missing" in codes


def test_gy_generated_public_lifecycle_rejects_file_inventory_drift() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["gy_artifact_inventory"]["paths"] = audit["gy_artifact_inventory"]["paths"][:-1]
    audit["summary"]["gy_artifact_files_detected"] -= 1

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "gy_detected_artifact_list_drift" in codes


def test_gy_generated_public_lifecycle_rejects_missing_pattern_and_acceptance() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["classification"]["patterns"] = [
        pattern for pattern in audit["classification"]["patterns"] if pattern != "P31"
    ]
    audit["acceptance_signal"] = [
        item for item in audit["acceptance_signal"] if "producer write-closure" not in item
    ]

    codes = _codes(validator.validate(audit))
    assert "pattern_coverage_drift" in codes
    assert "missing_acceptance_guardrail" in codes


def _load_source_read_candidate_validator() -> Any:
    candidate_path = (
        Path(__file__).resolve().parents[3]
        / "tools/quality/validation/check_layer3_gy_generated_public_lifecycle_audit.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_la021_source_read_candidate_lifecycle_validator",
        candidate_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _product_root_for_grounding_producer() -> tuple[Path, Path]:
    module_name = "tools.quality.validation.check_grounding_refusal_sensitivity"
    spec = importlib.util.find_spec(module_name)
    assert spec is not None and isinstance(spec.origin, str)
    producer_path = Path(spec.origin).resolve()
    return producer_path.parents[3], producer_path


def _invoke_grounding_producer(
    product_root: Path,
    producer_path: Path,
    arguments: list[str],
) -> None:
    module_name = "tools.quality.validation.check_grounding_refusal_sensitivity"
    old_argv = sys.argv
    old_path = list(sys.path)
    old_cwd = Path.cwd()
    sys.path[:0] = [str(product_root), str(product_root / "src")]
    sys.argv = [str(producer_path), *arguments]
    os.chdir(product_root)
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = 0
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                runpy.run_module(module_name, run_name="__main__", alter_sys=True)
            except SystemExit as exc:
                exit_code = (
                    0 if exc.code is None else int(exc.code) if isinstance(exc.code, int) else 1
                )
    finally:
        sys.argv = old_argv
        sys.path[:] = old_path
        os.chdir(old_cwd)
    assert exit_code == 0, f"grounding producer failed: {stderr.getvalue()}"


def test_lifecycle_source_input_requires_observed_real_producer_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only actual bound reads can classify source candidates under output roots."""
    product_root, producer_path = _product_root_for_grounding_producer()
    fixture_root = tmp_path / "scanner-repository"
    fixture_root.mkdir()
    _init_git_repo(fixture_root)

    from tests._helpers.world_model_record import _build_record

    _store, built, _model_spec, _registry_ref = _build_record(tmp_path / "world-model")
    cas_root = tmp_path / "world-model/cas"
    world_ref = str(built.record_ref.artifact_id)
    output_relative = "architecture/policy_design_case/corr/grounding_refusal_sensitivity.json"
    declarations = fixture_root / "architecture/policy_design_case/corr/grounding-2026-09-08"
    frame_path = declarations / "frame.json"
    suite_path = declarations / "suite.json"
    unused_path = fixture_root / "architecture/policy_design_case/corr/unused-safe.json"
    sibling_path = (
        fixture_root / "architecture/policy_design_case/corr/same-parent-stray-marker.json"
    )
    report_path = fixture_root / output_relative

    common_arguments = [
        "--repo-root",
        str(product_root),
        "--world-cas",
        str(cas_root),
        "--world-ref",
        world_ref,
        "--declarations",
        str(declarations),
        "--report",
        str(report_path),
    ]
    _invoke_grounding_producer(product_root, producer_path, ["--declare", *common_arguments])
    unused_path.write_text('{"example":"declared but unread"}\n', encoding="utf-8")
    sibling_path.write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    _invoke_grounding_producer(product_root, producer_path, ["--write", *common_arguments])
    assert frame_path.is_file() and suite_path.is_file() and report_path.is_file()

    workflow_relative = "tools/quality/validation/check_grounding_refusal_sensitivity.py"
    workflow_path = fixture_root / workflow_relative
    workflow_path.parent.mkdir(parents=True)
    workflow_path.write_bytes(producer_path.read_bytes())
    frame_relative = frame_path.relative_to(fixture_root).as_posix()
    suite_relative = suite_path.relative_to(fixture_root).as_posix()
    unused_relative = unused_path.relative_to(fixture_root).as_posix()
    source_of_truth = ", ".join(
        (frame_relative, suite_relative, unused_relative, workflow_relative)
    )
    module_name = "tools.quality.validation.check_grounding_refusal_sensitivity"
    check_command = [
        "uv",
        "run",
        "python",
        "-m",
        module_name,
        "--check",
        *common_arguments,
    ]
    regenerate_command = [
        "uv",
        "run",
        "python",
        "-m",
        module_name,
        "--write",
        *common_arguments,
    ]
    family = {
        "id": "policy-design-case-grounding-refusal-sensitivity",
        "owner": "tests",
        "approval_owner": "tests",
        "lifecycle": "generated_committed",
        "gy_lifecycle_family": True,
        "generator": "genuine typed WMR producer fixture",
        "verifier": "same-process exact read and output recheck",
        "promotion_target": "source read-use only",
        "stale_output_behavior": "fail",
        "drift_gate": "automated",
        "source_of_truth": source_of_truth,
        "outputs": [output_relative],
        "regenerate_commands": [" ".join(regenerate_command)],
        "workflow": workflow_relative,
        "check_cwd": str(product_root),
        "check_command": check_command,
    }
    registry = "[[family]]\n" + "\n".join(
        f"{key} = {json.dumps(value)}" for key, value in family.items()
    )
    (fixture_root / "architecture/generated_artifacts.toml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (fixture_root / "architecture/generated_artifacts.toml").write_text(
        registry + "\n", encoding="utf-8"
    )
    (fixture_root / "architecture/public_surface").mkdir(parents=True)
    (fixture_root / "architecture/public_surface/contract.toml").write_text("", encoding="utf-8")

    validator = _load_source_read_candidate_validator()
    report = validator.validate_gy_lifecycle_registry(fixture_root)
    frame = frame_relative
    suite = suite_relative
    unused = unused_relative
    sibling = sibling_path.relative_to(fixture_root).as_posix()
    assert set(report["source_input_read_paths"]) == {frame, suite}
    assert frame not in report["unaccounted_output_root_files"]
    assert suite not in report["unaccounted_output_root_files"]
    assert unused in report["unaccounted_output_root_files"]
    assert sibling in report["unaccounted_output_root_files"]
    assert sibling in report["marker_detected_outputs"]

    # Remove the read witness while retaining the same declarations and marker bytes.
    monkeypatch.setattr(
        validator, "_verified_source_input_read_paths", lambda *args, **kwargs: set()
    )
    without_read_witness = validator.validate_gy_lifecycle_registry(fixture_root)
    assert frame in without_read_witness["unaccounted_output_root_files"]
    assert suite in without_read_witness["unaccounted_output_root_files"]
    assert sibling in without_read_witness["marker_detected_outputs"]


def test_source_read_bridge_fails_closed_on_removed_or_stale_witness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synthetic runner controls bind source reads, writer, env, and outputs."""
    product_root, _producer_path = _product_root_for_grounding_producer()
    fixture_root = tmp_path / "probe-repository"
    fixture_root.mkdir()
    (fixture_root / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    (fixture_root / ".venv").symlink_to(product_root / ".venv", target_is_directory=True)
    _init_git_repo(fixture_root)
    module_relative = "la021probe/tools/quality/validation/source_read_probe.py"
    module_path = fixture_root / module_relative
    module_path.parent.mkdir(parents=True)
    for package in (
        fixture_root / "la021probe/__init__.py",
        fixture_root / "la021probe/tools/__init__.py",
        fixture_root / "la021probe/tools/quality/__init__.py",
        fixture_root / "la021probe/tools/quality/validation/__init__.py",
    ):
        package.write_text("", encoding="utf-8")
    original_module = """
import os
import sys
from pathlib import Path

OUTPUTS = ["corr/output.json"]

def declared_outputs():
    return OUTPUTS

def main():
    flags = set(sys.argv[1:])
    frame = Path("corr/frame.json")
    suite = Path("corr/suite.json")
    if "--no-read" not in flags:
        if "--text-read" in flags:
            frame.read_text(encoding="utf-8")
        else:
            frame.read_bytes()
        suite.read_bytes()
    if "--read-output-hardlink" in flags:
        Path("corr/output-hardlink.json").read_bytes()
    if "--read-symlink-leaf" in flags:
        Path("corr/frame-symlink.json").read_bytes()
    if "--read-symlink-parent" in flags:
        Path("corr/linked-directory/frame.json").read_bytes()
    if "--mutate-input" in flags:
        frame.write_bytes(frame.read_bytes() + b"changed")
    if "--mutate-writer" in flags:
        Path(__file__).write_text("# changed writer\\n", encoding="utf-8")
    if "--mutate-output" in flags:
        Path("corr/output.json").write_bytes(b"changed output\\n")
    if "--add-sibling" in flags:
        Path("corr/new-sibling.txt").write_bytes(b"unregistered sibling\\n")
    if "--mutate-sibling" in flags:
        Path("corr/same-parent-stray-marker.json").write_bytes(b'{"changed":true}\\n')
    if "--delete-sibling" in flags:
        Path("corr/same-parent-stray-marker.json").unlink()
    if "--mutate-env" in flags:
        os.environ["LA021_SOURCE_READ_ENV_CONTROL"] = "changed"
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""
    module_path.write_text(original_module, encoding="utf-8")
    corr = fixture_root / "corr"
    corr.mkdir()
    frame = corr / "frame.json"
    suite = corr / "suite.json"
    unused = corr / "unused.json"
    output = corr / "output.json"
    frame.write_bytes(b'{"frame":true}\n')
    suite.write_bytes(b'{"suite":true}\n')
    unused.write_bytes(b'{"unused":true}\n')
    output.write_bytes(b'{"output":true}\n')
    sibling = corr / "same-parent-stray-marker.json"
    sibling_bytes = b'{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n'
    sibling.write_bytes(sibling_bytes)
    output_alias = corr / "output-hardlink.json"
    os.link(output, output_alias)
    frame_symlink = corr / "frame-symlink.json"
    frame_symlink.symlink_to(frame)
    external = tmp_path / "external"
    external.mkdir()
    external_frame = external / "frame.json"
    external_frame.write_bytes(frame.read_bytes())
    parent_symlink = corr / "linked-directory"
    parent_symlink.symlink_to(external, target_is_directory=True)
    module_name = "la021probe.tools.quality.validation.source_read_probe"
    base_arguments = ("--check",)
    family = {
        "workflow": module_relative,
        "check_cwd": ".",
        "check_command": ["uv", "run", "python", "-m", module_name, *base_arguments],
    }
    candidates = (
        "corr/frame.json",
        "corr/suite.json",
        "corr/unused.json",
        "corr/output-hardlink.json",
        "corr/frame-symlink.json",
        "corr/linked-directory/frame.json",
    )
    outputs = ("corr/output.json",)
    validator = _load_source_read_candidate_validator()
    monkeypatch.syspath_prepend(str(fixture_root))

    def observed(*extra: str) -> set[str]:
        family["check_command"] = [
            "uv",
            "run",
            "python",
            "-m",
            module_name,
            *base_arguments,
            *extra,
        ]
        return validator._execute_bound_family_check_for_source_reads(
            fixture_root,
            family,
            candidates=candidates,
            outputs=outputs,
            output_root_directories=("corr",),
            scope_exclusions=(set(), set()),
        )

    assert observed() == {"corr/frame.json", "corr/suite.json"}
    assert observed("--no-read") == set()
    assert observed("--text-read") == {"corr/suite.json"}
    assert observed("--read-output-hardlink") == {"corr/frame.json", "corr/suite.json"}
    assert observed("--read-symlink-leaf") == {"corr/frame.json", "corr/suite.json"}
    assert observed("--read-symlink-parent") == {"corr/frame.json", "corr/suite.json"}
    assert validator._repo_file_is_safe(fixture_root, "corr/frame-symlink.json")
    assert not validator._repo_source_file_is_safe(fixture_root, "corr/frame-symlink.json")
    assert not validator._repo_file_is_safe(fixture_root, "corr/linked-directory/frame.json")
    assert not validator._repo_source_file_is_safe(fixture_root, "corr/linked-directory/frame.json")

    output_before = output.read_bytes()
    assert observed("--mutate-output") == set()
    output.write_bytes(output_before)

    assert observed("--add-sibling") == set()
    (corr / "new-sibling.txt").unlink()
    assert observed("--mutate-sibling") == set()
    sibling.write_bytes(sibling_bytes)
    assert observed("--delete-sibling") == set()
    sibling.write_bytes(sibling_bytes)

    frame_before = frame.read_bytes()
    assert observed("--mutate-input") == set()
    frame.write_bytes(frame_before)

    writer_before = module_path.read_bytes()
    assert observed("--mutate-writer") == set()
    module_path.write_bytes(writer_before)

    environment_key = "LA021_SOURCE_READ_ENV_CONTROL"
    assert environment_key not in os.environ
    assert observed("--mutate-env") == set()
    assert environment_key not in os.environ
