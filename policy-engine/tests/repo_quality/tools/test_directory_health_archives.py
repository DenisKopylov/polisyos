from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from tools.quality.validation import directory_health, directory_health_archives

ARCHIVE_ROOT = "docs/history"
INIT = ARCHIVE_ROOT + "/a/b/c/d/e/f/g/h/i/__init__.py"
BODY = b'"""Frozen input, not an active package."""\n'


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _commit(root: Path, message: str) -> None:
    _git(root, "add", ".")
    _git(
        root,
        "-c",
        "user.name=Directory Health Test",
        "-c",
        "user.email=directory-health@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--quiet",
        "-m",
        message,
    )


def _policy(project: Path, tree: str, *, active_root: str | None = None) -> dict:
    text = f'''[[archive_class]]
id = "history"
owner = "team-docs"
allowed_roots = ["{ARCHIVE_ROOT}/"]
frozen_scope_schema = "{directory_health_archives.SCOPE_SCHEMA}"
frozen_git_tree = "{tree}"
'''
    if active_root is not None:
        text += f'''\n[[contract]]
path = "{active_root}"
status = "active"
allowed_file_kinds = ["product_python_source"]
allowed_child_directory_kinds = ["python_package"]
'''
    path = project / "architecture/policies/directory_contracts.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return tomllib.loads(text)


@pytest.fixture
def archive_repo(tmp_path: Path) -> tuple[Path, Path, str, dict]:
    # A small real repository also exercises the product-root / Git-root split.
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    _git(checkout, "init", "--quiet")
    project = checkout / "policy-engine"
    old = project / INIT
    old.parent.mkdir(parents=True)
    old.write_bytes(BODY)
    plain = project / ARCHIVE_ROOT / "plain.txt"
    plain.write_bytes(b"frozen text\n")
    executable = project / ARCHIVE_ROOT / "script.sh"
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    (project / ARCHIVE_ROOT / "link.txt").symlink_to("plain.txt")
    _commit(checkout, "Retain historical input")
    tree = _git(checkout, "rev-parse", f"HEAD:policy-engine/{ARCHIVE_ROOT}")
    contract = _policy(project, tree)
    _commit(checkout, "Declare historical input scope")
    return checkout, project, tree, contract


def _scope(project: Path, contract: dict) -> directory_health_archives.FrozenArchiveScope:
    result = directory_health_archives.measure_frozen_archives(project, contract)
    assert result is not None
    return result


def _init_findings(project: Path, scope: directory_health_archives.FrozenArchiveScope) -> list:
    return directory_health._non_product_init_findings(
        project,
        {"allowed_non_product_init_roots": ["tests", "tools"]},
        historical_scope=scope,
    )


def _depth(project: Path, scope: directory_health_archives.FrozenArchiveScope) -> int:
    from tools.quality.validation import directory_health_dashboard

    depths = directory_health_dashboard.max_directory_depth_by_root(
        project,
        dependencies=directory_health._dashboard_dependencies(),
        excluded_directories=scope.directories,
    )
    return max(depths.values(), default=0)


def test_frozen_scope_reconciles_real_git_and_both_health_consumers(archive_repo) -> None:
    _, project, _, contract = archive_repo
    assert len(directory_health._non_product_init_findings(project, {})) == 1
    assert directory_health._max_directory_depth_by_root(project)["docs"] == 11

    scope = _scope(project, contract)

    assert _init_findings(project, scope) == []
    assert _depth(project, scope) <= 10
    row = scope.measurement["classes"][0]
    assert row["frozen_leaf_count"] == row["historical_leaf_count"] == 4
    assert row["head_leaf_count"] == row["index_stage_zero_leaf_count"] == 4
    assert row["filesystem_leaf_count"] == row["worktree_identity_read_count"] == 4
    assert row["leaf_dispositions"] == {"unchanged": 4}
    assert scope.measurement["complete"] is True
    assert scope.measurement["git_object_format"] == "sha1"
    assert scope.measurement["policy_read"]["sha256"]
    assert all(read["status"] == "read" for read in scope.measurement["git_reads"])


@pytest.mark.parametrize("state", ["untracked", "staged", "committed"])
def test_new_package_under_frozen_prefix_stays_active(archive_repo, state: str) -> None:
    checkout, project, _, contract = archive_repo
    package = (project / INIT).parent / "live"
    package.mkdir()
    (package / "__init__.py").write_text("value = 1\n")
    (package / "pyproject.toml").write_text('[project]\nname = "active-package"\n')
    if state == "staged":
        _git(checkout, "add", ".")
    elif state == "committed":
        _commit(checkout, "Add new active package")

    scope = _scope(project, contract)

    assert [row.subject for row in _init_findings(project, scope)] == [
        (package / "__init__.py").relative_to(project).as_posix()
    ]
    assert _depth(project, scope) == 12
    assert scope.measurement["classes"][0]["leaf_dispositions"]["outside_frozen_tree"] == 2


@pytest.mark.parametrize("change", ["unstaged", "staged_then_restored", "committed", "mode"])
def test_bound_path_and_marker_cannot_hide_changed_source(archive_repo, change: str) -> None:
    checkout, project, _, contract = archive_repo
    path = project / INIT
    if change == "mode":
        path.chmod(0o755)
    else:
        path.write_bytes(BODY + b"value = 'new active code'\n")
        if change == "staged_then_restored":
            _git(checkout, "add", ".")
            path.write_bytes(BODY)
        elif change == "committed":
            _commit(checkout, "Change retained path")

    scope = _scope(project, contract)

    assert INIT not in scope.files
    assert [row.subject for row in _init_findings(project, scope)] == [INIT]
    assert _depth(project, scope) == 11
    assert scope.measurement["classes"][0]["historical_leaf_count"] == 3


def test_explicit_active_package_contract_overrides_frozen_identity(archive_repo) -> None:
    _, project, tree, _ = archive_repo
    contract = _policy(project, tree, active_root=(Path(INIT).parent).as_posix())

    scope = _scope(project, contract)

    assert [row.subject for row in _init_findings(project, scope)] == [INIT]
    assert _depth(project, scope) == 11
    assert scope.measurement["classes"][0]["leaf_dispositions"]["active_source_contract"] == 1


@pytest.mark.parametrize(
    ("active_root", "permits_archive_children", "excluded"),
    [("docs", True, True), ("docs", False, False), (ARCHIVE_ROOT, True, False)],
)
def test_existing_contract_boundaries_decide_whether_an_archive_can_be_hosted(
    archive_repo, active_root: str, permits_archive_children: bool, excluded: bool
) -> None:
    _, project, tree, _ = archive_repo
    _policy(project, tree, active_root=active_root)
    policy = project / "architecture/policies/directory_contracts.toml"
    if permits_archive_children:
        policy.write_text(
            policy.read_text().replace(
                'allowed_child_directory_kinds = ["python_package"]',
                'allowed_child_directory_kinds = ["archive"]',
            )
        )

    scope = _scope(project, tomllib.loads(policy.read_text()))

    assert (INIT in scope.files) is excluded
    assert (not _init_findings(project, scope)) is excluded


@pytest.mark.parametrize("active_root", [".", ARCHIVE_ROOT + "/**"])
def test_unsupported_active_root_cannot_silently_lose_its_override(
    archive_repo, active_root: str
) -> None:
    _, project, tree, _ = archive_repo
    contract = _policy(project, tree, active_root=active_root)

    with pytest.raises(
        directory_health_archives.FrozenArchiveInspectionError, match="active_source_root_invalid"
    ):
        _scope(project, contract)


def test_symlink_cannot_relabel_archive_initializer_as_product_source(archive_repo) -> None:
    _, project, _, contract = archive_repo
    product = project / "src/polisyos/__init__.py"
    product.parent.mkdir(parents=True)
    product.write_bytes(BODY)
    path = project / INIT
    path.unlink()
    path.symlink_to(product)

    scope = _scope(project, contract)

    assert INIT not in scope.files
    assert [row.subject for row in _init_findings(project, scope)] == [INIT]
    assert _depth(project, scope) == 11
    assert os.readlink(path) == str(product)


def test_archive_root_alias_is_undecided_without_following_target(archive_repo, tmp_path) -> None:
    _, project, _, contract = archive_repo
    original = project / ARCHIVE_ROOT
    moved = tmp_path / "original-history"
    original.rename(moved)
    original.symlink_to(moved, target_is_directory=True)

    with pytest.raises(
        directory_health_archives.FrozenArchiveInspectionError,
        match="root_is_not_a_real_directory",
    ) as refused:
        _scope(project, contract)

    assert refused.value.measurement["complete"] is False
    assert not (project / ARCHIVE_ROOT).is_file()


def test_frozen_tree_is_available_in_real_shallow_checkout(archive_repo, tmp_path) -> None:
    checkout, _, _, _ = archive_repo
    shallow = tmp_path / "shallow"
    _git(tmp_path, "clone", "--quiet", "--depth=1", checkout.as_uri(), str(shallow))
    assert _git(shallow, "rev-parse", "--is-shallow-repository") == "true"
    project = shallow / "policy-engine"
    policy = project / "architecture/policies/directory_contracts.toml"

    scope = _scope(project, tomllib.loads(policy.read_text()))

    assert INIT in scope.files
    assert _init_findings(project, scope) == []


def test_missing_frozen_tree_is_unrun_with_partial_reads_in_both_cli_formats(
    archive_repo, capsys
) -> None:
    _, project, _, _ = archive_repo
    missing = "f" * 40
    _policy(project, missing)
    (project / "architecture/policies/directory_health.toml").write_text(
        "[directory_health]\nmode = 'fail_closed'\n"
    )

    assert directory_health.run_cli(["--repo-root", str(project)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "UNRUN"
    assert payload["complete_verdict"] is False
    reads = payload["historical_archive_scope"]
    assert reads["policy_read"]["bytes"] > 0
    assert reads["git_reads"][-1]["arguments"] == ["cat-file", "-t", missing]
    assert reads["git_reads"][-1]["status"] == "error"
    assert reads["unresolved_by_construction"] == ["frozen_archive_inspection_incomplete"]
    markdown = directory_health.render_markdown(payload)
    assert missing in markdown
    assert "UNRUN" in markdown
    assert "Frozen Historical Input Scope" in markdown


def test_unknown_scope_schema_is_not_a_path_exemption(archive_repo) -> None:
    _, project, tree, _ = archive_repo
    _policy(project, tree)
    path = project / "architecture/policies/directory_contracts.toml"
    path.write_text(path.read_text().replace("frozen-git-tree.v1", "frozen-git-tree.v2"))

    with pytest.raises(directory_health_archives.FrozenArchiveInspectionError, match="invalid"):
        _scope(project, tomllib.loads(path.read_text()))


def test_unreadable_deciding_file_is_unrun_instead_of_exempt(archive_repo, monkeypatch) -> None:
    _, project, _, contract = archive_repo

    def unreadable(*_args):
        raise PermissionError("deciding frozen body is unreadable")

    monkeypatch.setattr(directory_health_archives, "_worktree_identity", unreadable)

    with pytest.raises(directory_health_archives.FrozenArchiveInspectionError) as refused:
        _scope(project, contract)

    measurement = refused.value.measurement
    assert measurement["complete"] is False
    assert measurement["progress"]["worktree_path"].startswith(ARCHIVE_ROOT + "/")
    assert "PermissionError" in measurement["reason"]
    assert measurement["unresolved_by_construction"]


def test_new_entry_during_inspection_cannot_get_a_stale_directory_exemption(
    archive_repo, monkeypatch
) -> None:
    _, project, _, contract = archive_repo
    original = directory_health_archives._worktree_identity
    inserted = False

    def add_entry(*args):
        nonlocal inserted
        identity = original(*args)
        if not inserted:
            (project / INIT).with_name("new_active.py").write_text("value = 1\n")
            inserted = True
        return identity

    monkeypatch.setattr(directory_health_archives, "_worktree_identity", add_entry)

    with pytest.raises(
        directory_health_archives.FrozenArchiveInspectionError, match="paths_changed"
    ) as refused:
        _scope(project, contract)

    assert refused.value.measurement["complete"] is False


def test_missing_tree_in_promisor_repo_does_not_spawn_a_lazy_fetch(
    archive_repo, tmp_path, monkeypatch
) -> None:
    checkout, project, _, _ = archive_repo
    _git(checkout, "config", "extensions.partialclone", "origin")
    _git(checkout, "config", "remote.origin.promisor", "true")
    _git(checkout, "config", "remote.origin.url", (tmp_path / "absent-local-remote").as_uri())
    control_trace = tmp_path / "unrestricted-git-trace.jsonl"
    environment = {**os.environ, "GIT_TRACE2_EVENT": str(control_trace)}
    environment.pop("GIT_NO_LAZY_FETCH", None)
    control = subprocess.run(
        ["git", "cat-file", "-t", "f" * 40],
        cwd=checkout,
        env=environment,
        capture_output=True,
        check=False,
    )
    assert control.returncode != 0
    control_events = [json.loads(line) for line in control_trace.read_text().splitlines()]
    assert any(
        event.get("event") == "child_start" and "fetch" in event.get("argv", [])
        for event in control_events
    )
    trace = tmp_path / "git-trace.jsonl"
    monkeypatch.setenv("GIT_TRACE2_EVENT", str(trace))
    contract = _policy(project, "f" * 40)

    with pytest.raises(directory_health_archives.FrozenArchiveInspectionError):
        _scope(project, contract)

    events = [json.loads(line) for line in trace.read_text().splitlines()]
    children = [event for event in events if event.get("event") == "child_start"]
    assert not any("fetch" in event.get("argv", []) for event in children)


def test_missing_git_discloses_its_failed_selector(archive_repo, monkeypatch) -> None:
    _, project, _, contract = archive_repo

    def unavailable(*_args, **_kwargs):
        raise FileNotFoundError("git executable unavailable")

    monkeypatch.setattr(directory_health_archives.subprocess, "run", unavailable)

    with pytest.raises(directory_health_archives.FrozenArchiveInspectionError) as refused:
        _scope(project, contract)

    measurement = refused.value.measurement
    assert measurement["complete"] is False
    assert measurement["git_reads"][0]["arguments"] == ["rev-parse", "--show-toplevel"]
    assert measurement["git_reads"][0]["status"] == "error"
    assert measurement["git_reads"][0]["error_type"] == "FileNotFoundError"


def test_git_replace_cannot_enroll_new_code_in_the_frozen_tree(archive_repo) -> None:
    checkout, project, frozen_tree, contract = archive_repo
    package = (project / INIT).parent / "injected"
    package.mkdir()
    (package / "__init__.py").write_text("active = True\n")
    (package / "pyproject.toml").write_text('[project]\nname = "active-package"\n')
    _commit(checkout, "Add active package after archive freeze")
    new_tree = _git(checkout, "rev-parse", f"HEAD:policy-engine/{ARCHIVE_ROOT}")
    _git(checkout, "replace", frozen_tree, new_tree)
    environment = dict(os.environ)
    environment.pop("GIT_NO_REPLACE_OBJECTS", None)
    replaced = subprocess.check_output(
        ["git", "ls-tree", "--full-tree", "-rz", frozen_tree],
        cwd=checkout,
        env=environment,
    )
    assert b"injected/__init__.py" in replaced

    scope = _scope(project, contract)

    injected = (package / "__init__.py").relative_to(project).as_posix()
    assert injected not in scope.files
    assert [row.subject for row in _init_findings(project, scope)] == [injected]
    assert _depth(project, scope) == 12
    assert scope.measurement["classes"][0]["frozen_leaf_count"] == 4
    assert all(read["replace_objects"] == "disabled" for read in scope.measurement["git_reads"])
