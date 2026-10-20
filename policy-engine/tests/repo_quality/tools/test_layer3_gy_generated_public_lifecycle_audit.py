from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import tomllib
from collections.abc import Iterator
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
    root = tmp_path / "architecture/cas"
    root.mkdir(parents=True)
    artifact = root / f"unregistered{suffix}"
    artifact.write_bytes(b"source evidence\n")
    observed = _validator()._iter_contract_derived_output_root_files(
        tmp_path, {"architecture/cas"}, (set(), set())
    )
    assert observed == [artifact.relative_to(tmp_path).as_posix()]


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
    original_iter_files = validator.iter_files

    def recording_iter_files(root: Path) -> Iterator[Path]:
        walked.append(root)
        yield from original_iter_files(root)

    monkeypatch.setattr(validator, "iter_files", recording_iter_files)
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
    original_iter_files = validator.iter_files

    def recording_iter_files(root: Path) -> Iterator[Path]:
        walked.append(root)
        yield from original_iter_files(root)

    monkeypatch.setattr(validator, "iter_files", recording_iter_files)
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
    original_iter_files = validator.iter_files

    def recording_iter_files(root: Path) -> Iterator[Path]:
        walked.append(root)
        yield from original_iter_files(root)

    monkeypatch.setattr(validator, "iter_files", recording_iter_files)
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
    original_iter_files = validator.iter_files

    def recording_iter_files(root: Path) -> Iterator[Path]:
        walked.append(root)
        yield from original_iter_files(root)

    monkeypatch.setattr(validator, "iter_files", recording_iter_files)
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
    original_iter_files = validator.iter_files

    def recording_iter_files(root: Path) -> Iterator[Path]:
        walked.append(root)
        yield from original_iter_files(root)

    monkeypatch.setattr(validator, "iter_files", recording_iter_files)
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


def test_output_root_walks_overlapping_ignored_roots_once_and_skips_symlinks(
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
        original_iter_files = validator.iter_files
        visited_roots: list[str] = []

        def recording_iter_files(root: Path) -> Iterator[Path]:
            visited_roots.append(root.relative_to(repo_root).as_posix())
            yield from original_iter_files(root)

        monkeypatch.setattr(validator, "iter_files", recording_iter_files)
        observed = validator._iter_contract_derived_output_root_files(
            repo_root,
            {"owner-output", "owner-output/nested"},
            (set(), set()),
        )

        assert observed == ["owner-output/nested/untracked.json"]
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
