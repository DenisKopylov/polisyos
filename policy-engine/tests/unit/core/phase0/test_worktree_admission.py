"""Exercise commissioning admission against disposable, real Git repositories."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.devx.workspace import doctor


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path, monkeypatch):
    root = tmp_path.resolve() / "repository"
    root.mkdir()
    _git(root, "init", "-b", "main")
    (root / "seed").write_text("initial\n")
    _git(root, "add", "seed")
    _git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "initial",
    )
    monkeypatch.setattr(doctor, "PRODUCT_ROOT", root)

    def forbidden(*args, **kwargs):
        pytest.fail("admission entered normal doctor or dependency checks")

    for name in (
        "_check_python",
        "_check_node",
        "_check_uv",
        "_check_playwright",
        "_check_lockfiles",
        "_check_generated_contracts",
        "_check_optional_surfaces",
    ):
        monkeypatch.setattr(doctor, name, forbidden)
    return root


def _linked(root: Path, branch: str = "codex/active", name: str = "active") -> Path:
    path = root.parent / name
    _git(root, "worktree", "add", "-b", branch, str(path))
    return path


def _admit(capsys, mode: str, branch: str, path: Path | str):
    code = doctor.main(["--worktree-admission", mode, "--branch", branch, "--path", str(path)])
    return code, json.loads(capsys.readouterr().out)


def _state(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def test_available_pair_admitted_despite_unrelated_stale_registration(repository, capsys):
    stale = _linked(repository)
    shutil.rmtree(stale)
    before = _state(repository)
    path = repository.parent / "new"
    code, report = _admit(capsys, "create", "codex/new", path)
    assert code == 0
    assert report["status"] == "admitted"
    assert report["complete_verdict"] is True
    assert report["requested"] == {"mode": "create", "branch": "codex/new", "path": str(path)}
    assert len(report["registrations"]) == 2
    assert len(report["admin_records"]) == 1
    assert report["registrations"][1]["path_state"]["exists"] is False
    assert report["commands"] and report["filesystem_reads"]
    assert {row["boundary"] for row in report["unresolved_by_construction"]} >= {
        "moved_directories_outside_registered_paths",
        "non_atomic_observation",
        "name_reservation",
    }
    assert _state(repository) == before
    assert not path.exists()


def test_original_occupied_branch_and_stale_path_both_rejected(repository, capsys):
    path = _linked(repository, "codex/missing-producers", "producers")
    shutil.rmtree(path)
    code, report = _admit(capsys, "create", "codex/missing-producers", path)
    assert code == 1
    assert {row["code"] for row in report["findings"]} >= {"branch_occupied", "path_registered"}
    assert report["admin_records"][0]["worktree"] == str(path)
    assert report["complete_verdict"] is True


def test_stale_path_alone_cannot_be_admitted(repository, capsys):
    path = _linked(repository)
    shutil.rmtree(path)
    code, report = _admit(capsys, "create", "codex/free", path)
    assert code == 1
    assert "path_registered" in {row["code"] for row in report["findings"]}
    assert "branch_occupied" not in {row["code"] for row in report["findings"]}


def test_occupied_branch_alone_cannot_be_admitted(repository, capsys):
    _git(repository, "branch", "codex/occupied")
    code, report = _admit(capsys, "create", "codex/occupied", repository.parent / "free")
    assert code == 1
    assert "branch_occupied" in {row["code"] for row in report["findings"]}


def test_exact_linked_pair_resumes_with_live_admin_evidence(repository, capsys):
    path = _linked(repository, name="a path with spaces")
    before = _state(repository)
    code, report = _admit(capsys, "resume", "codex/active", path)
    assert code == 0
    assert report["complete_verdict"] is True
    row = next(row for row in report["registrations"] if row["worktree"] == str(path))
    assert row["live"]["branch"] == "refs/heads/codex/active"
    assert row["live"]["common_dir"] == str(repository / ".git")
    assert row["live"]["git_dir"] == report["admin_records"][0]["admin_dir"]
    assert _state(repository) == before


@pytest.mark.parametrize("mutation", ["wrong_branch", "detached", "missing"])
def test_resume_requires_real_exact_attachment(repository, capsys, mutation):
    path = _linked(repository)
    branch = "codex/active"
    if mutation == "wrong_branch":
        branch = "main"
    elif mutation == "detached":
        _git(path, "checkout", "--detach")
    else:
        shutil.rmtree(path)
    code, report = _admit(capsys, "resume", branch, path)
    assert code == 1
    assert report["status"] == "rejected"
    assert "resume_attachment_mismatch" in {row["code"] for row in report["findings"]}


@pytest.mark.parametrize("mutation", ["missing_commondir", "foreign_commondir", "bad_backlink"])
def test_incomplete_or_contradictory_admin_evidence_never_means_available(
    repository, capsys, mutation
):
    path = _linked(repository)
    admin = Path(_git(path, "rev-parse", "--absolute-git-dir"))
    if mutation == "missing_commondir":
        (admin / "commondir").unlink()
    elif mutation == "foreign_commondir":
        (admin / "commondir").write_text(str(repository.parent / "foreign") + "\n")
    else:
        (path / ".git").write_text("gitdir: /nonexistent/admin\n")
    code, report = _admit(capsys, "create", "codex/free", repository.parent / "free")
    assert code == 2
    assert report["status"] == "unrun"
    assert report["complete_verdict"] is False
    assert report["unresolved_inputs"]
    assert report["commands"] and report["filesystem_reads"]


@pytest.mark.parametrize("kind", ["directory", "file", "dangling_symlink", "parent_alias"])
def test_filesystem_occupancy_and_aliases_reject_exact_create_path(repository, capsys, kind):
    path = repository.parent / "occupied"
    if kind == "directory":
        path.mkdir()
    elif kind == "file":
        path.write_text("occupied")
    elif kind == "dangling_symlink":
        path.symlink_to(repository.parent / "missing")
    else:
        path.symlink_to(repository, target_is_directory=True)
        path = path / "unused"
    code, report = _admit(capsys, "create", "codex/free", path)
    assert code == 1
    assert report["requested"]["path"] == str(path)
    assert {row["code"] for row in report["findings"]} & {"path_exists", "path_alias"}


@pytest.mark.parametrize(
    ("branch", "path"),
    [
        ("HEAD", "/unused"),
        ("@{-1}", "/unused"),
        ("refs/heads/x", "/unused"),
        ("codex/valid", "relative"),
        ("codex/bad..ref", "/unused"),
    ],
)
def test_invalid_selectors_are_not_substituted(repository, capsys, branch, path):
    code, report = _admit(capsys, "create", branch, path)
    assert code != 0
    assert report["requested"]["branch"] == branch
    assert report["requested"]["path"] == path


def test_missing_selectors_do_not_enter_normal_doctor(repository, capsys):
    code = doctor.main(["--worktree-admission", "create"])
    report = json.loads(capsys.readouterr().out)
    assert code == 2
    assert report["complete_verdict"] is False


def test_resume_rejects_an_unregistered_repository(repository, capsys):
    code, report = _admit(capsys, "resume", "main", repository.parent)
    assert code == 1
    assert report["status"] == "rejected"


def test_unresolvable_symlink_emits_incomplete_receipt(repository, capsys):
    path = repository.parent / "cycle"
    path.symlink_to(path)
    code, report = _admit(capsys, "create", "codex/free", path)
    assert code == 2
    assert report["complete_verdict"] is False
    assert report["unresolved_inputs"]
    assert any(row.get("status") == "unreadable" for row in report["filesystem_reads"])
