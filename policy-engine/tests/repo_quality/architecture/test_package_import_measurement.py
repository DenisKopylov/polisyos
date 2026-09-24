"""Exercise incomplete repository measurements through the package gate owner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools.quality.validation import check_package_import_gates as gate


def _fixture(root: Path, *, root_name: str = "runs", local: bool = True) -> None:
    contracts = root / "architecture/policies/directory_contracts.toml"
    contracts.parent.mkdir(parents=True)
    contracts.write_text(
        '[[contract]]\npath = "architecture"\n'
        '[[contract]]\npath = "docs"\n'
        f'[[contract]]\npath = "{root_name}"\n'
        f'status = "{"local_only" if local else "active"}"\n'
        f'topology_commit_policy = "{"ignored" if local else "committed"}"\n'
        f'[[non_product_python_root]]\npath = "{root_name}"\n'
        'policy = "fixture"\nowner = "team-quality"\n'
        'allowed_reason = "Fixture boundary"\n'
        'product_import_policy = "Product imports forbidden"\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)


@pytest.mark.parametrize("root_name", ["production_data", "runs"])
def test_missing_local_mount_is_named_unmeasured(tmp_path: Path, root_name: str) -> None:
    _fixture(tmp_path, root_name=root_name)
    measurement = {}

    findings = gate._check_importable_root_contracts(tmp_path, measurement=measurement)

    assert findings == []
    assert measurement["unmeasured_local_roots"] == [root_name]
    assert "not inspected" in measurement["omission"]


def test_missing_required_root_remains_a_finding(tmp_path: Path) -> None:
    _fixture(tmp_path, root_name="required_source", local=False)
    measurement = {}

    findings = gate._check_importable_root_contracts(tmp_path, measurement=measurement)

    assert [item.subject for item in findings] == ["required_source"]
    assert measurement["unmeasured_local_roots"] == []


def test_ignored_python_is_excluded_with_a_named_tracked_denominator(tmp_path: Path) -> None:
    _fixture(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "witness.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "docs/witness.py"], check=True)
    (tmp_path / ".gitignore").write_text("docs/raw/\n", encoding="utf-8")
    (docs / "raw").mkdir()
    (docs / "raw/ignored.py").write_text("VALUE = 2\n", encoding="utf-8")
    (docs / "untracked.py").write_text("VALUE = 3\n", encoding="utf-8")
    measurement = {}

    findings = gate._check_importable_root_contracts(tmp_path, measurement=measurement)

    docs_finding = next(item for item in findings if item.subject == "docs")
    assert docs_finding.detail == "tracked_python_files=1 tracked_init_files=0"
    assert measurement["python_denominator"] == "git ls-files: tracked .py files only"
    assert "untracked and ignored Python" in measurement["omission"]


def test_missing_contract_is_unrun_even_without_fail_closed(tmp_path: Path, capsys) -> None:
    assert gate.main(["--repo-root", str(tmp_path)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "UNRUN"
    assert payload["complete_verdict"] is False
    assert payload["finding_coverage"] == "partial"
    assert "Not measured:" in payload["measurement"]["omission"]


def test_unavailable_git_denominator_does_not_become_an_empty_scan(tmp_path: Path) -> None:
    contracts = tmp_path / "architecture/policies/directory_contracts.toml"
    contracts.parent.mkdir(parents=True)
    contracts.write_text('[[contract]]\npath = "architecture"\n', encoding="utf-8")

    with pytest.raises(subprocess.CalledProcessError):
        gate._check_importable_root_contracts(tmp_path)
