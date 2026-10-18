from __future__ import annotations

import base64
import gzip
import json
import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from uuid import uuid4

import pytest

from tools.registry import TOOL_SPECS


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "docs-review@example.invalid")
    _git(root, "config", "user.name", "Docs review test")
    (root / "README.md").write_text("# Initial\n", encoding="utf-8")
    (root / ".gitignore").write_text("_build/\n", encoding="utf-8")
    _commit(root, "baseline")
    return root


def _review():
    return import_module("tools.quality.validation.check_docs_review")


def _receipt(root: Path) -> Path:
    return (
        root / "_build" / "docs-maintenance" / "docs-review" / f"run-{uuid4().hex}" / "review.json"
    )


def _allocated_receipt(root: Path) -> Path:
    path = _receipt(root)
    path.parent.mkdir(parents=True, mode=0o700)
    return path


def test_docs_review_is_discovered_by_the_validation_cli() -> None:
    discovered = [
        spec
        for spec in TOOL_SPECS
        if spec.category == "validation" and spec.name == "check-docs-review"
    ]

    assert len(discovered) == 1
    assert discovered[0].module == "tools.quality.validation.check_docs_review"
    assert discovered[0].callable_name == "main"


def test_git_window_facade_uses_current_selection_bindings(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review()
    calls: list[str] = []
    commit = "a" * 40

    def resolve_commit(_repo_root: Path, ref: str) -> str:
        calls.append(f"commit:{ref}")
        return commit

    def select_changed_paths(
        _repo_root: Path, *, comparison_base: str | None, head: str
    ) -> tuple[bytes, ...]:
        calls.append(f"paths:{comparison_base}:{head}")
        return (b"docs/selected.md",)

    monkeypatch.setattr(review, "_resolve_commit", resolve_commit)
    monkeypatch.setattr(review, "_select_changed_paths", select_changed_paths)

    window = review._resolve_git_window(git_repo, base_ref=None, head_ref=None)

    assert window.checkout_commit == commit
    assert window.paths == ("docs/selected.md",)
    assert calls == ["commit:HEAD", "paths:None:HEAD"]


def test_main_uses_the_current_facade_output_root_binding(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    review = _review()
    alternate_output_root = Path("_build/alternate-docs-review")
    monkeypatch.setattr(review, "OUTPUT_ROOT", alternate_output_root)
    (git_repo / "README.md").write_text("# Changed\n", encoding="utf-8")

    code = review.main(["--repo-root", str(git_repo), "--dry-run"])

    output = json.loads(capsys.readouterr().out)
    assert code == 2
    assert output["receipt"].startswith(f"{alternate_output_root.as_posix()}/run-")


def test_dry_run_uses_real_worktree_changes_and_executes_no_checks(git_repo: Path) -> None:
    review = _review()
    (git_repo / "README.md").write_text("# Edited\n", encoding="utf-8")
    (git_repo / "docs").mkdir()
    (git_repo / "docs" / "new.md").write_text("# New\n", encoding="utf-8")
    receipt_path = _receipt(git_repo)

    code = review.main(["--repo-root", str(git_repo), "--dry-run", "--receipt", str(receipt_path)])

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert code == 2
    assert receipt["status"] == "UNRUN"
    assert receipt["inputs"]["changed_path_count"] == 2
    assert receipt["inputs"]["head_commit"] is None
    assert receipt["inputs"]["checkout_head_commit"]
    assert receipt["inputs"]["changed_path_artifact"]["sha256"]
    assert receipt["gate"]["status"] == "UNRUN"
    assert {child["status"] for child in receipt["gate"]["children"]} == {"PLANNED"}
    assert not list((git_repo / "_build").rglob("*.stdout.gz"))


def test_explicit_commit_range_excludes_worktree_only_paths(git_repo: Path) -> None:
    review = _review()
    base = _git(git_repo, "rev-parse", "HEAD")
    (git_repo / "docs").mkdir()
    (git_repo / "docs" / "committed.md").write_text("# Committed\n", encoding="utf-8")
    head = _commit(git_repo, "committed docs page")
    clean_window = review._resolve_git_window(git_repo, base_ref=base, head_ref=head)
    assert clean_window.workspace_matches_head is True
    assert clean_window.worktree_status == b""
    (git_repo / "docs" / "working.md").write_text("# Worktree only\n", encoding="utf-8")
    receipt_path = _receipt(git_repo)

    code = review.main(
        [
            "--repo-root",
            str(git_repo),
            "--base-ref",
            base,
            "--head-ref",
            head,
            "--dry-run",
            "--run-independent",
            "--receipt",
            str(receipt_path),
        ]
    )

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert code == 2
    assert receipt["inputs"]["changed_path_count"] == 1
    assert receipt["inputs"]["head_commit"] == head
    assert receipt["inputs"]["workspace_matches_head"] is False
    assert receipt["inputs"]["worktree_status_artifact"]["path"]
    assert receipt["independent"]["impact"]["status"] == "PLANNED"
    assert receipt["gate"]["status"] == "UNRUN"
    assert receipt["gate"]["children"][0]["status"] == "UNRUN"
    assert receipt["independent"]["style"]["status"] == "UNRUN"
    assert receipt["independent"]["build"]["status"] == "UNRUN"
    assert receipt["independent"]["rendered_links"]["status"] == "UNRUN"
    artifact_path = git_repo / receipt["inputs"]["changed_path_artifact"]["path"]
    assert "working.md" not in gzip.decompress(artifact_path.read_bytes()).decode("utf-8")


def test_explicit_refs_must_be_supplied_together(git_repo: Path) -> None:
    review = _review()

    with pytest.raises(SystemExit) as error:
        review.main(["--repo-root", str(git_repo), "--base-ref", "HEAD"])

    assert error.value.code == 2


def test_explicit_refs_at_current_head_select_an_exact_empty_commit_window(
    git_repo: Path,
) -> None:
    review = _review()
    head = _git(git_repo, "rev-parse", "HEAD")
    window = review._resolve_git_window(git_repo, base_ref=head, head_ref=head)
    assert window.comparison_base == head
    assert window.paths == ()
    assert window.raw_paths == ()
    assert window.workspace_matches_head is True

    receipt_path = _receipt(git_repo)
    code = review.main(
        [
            "--repo-root",
            str(git_repo),
            "--base-ref",
            head,
            "--head-ref",
            head,
            "--dry-run",
            "--receipt",
            str(receipt_path),
        ]
    )

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert code == 2
    assert receipt["inputs"]["changed_path_count"] == 0
    assert receipt["inputs"]["base_commit"] == head
    assert receipt["inputs"]["head_commit"] == head


def test_git_z_selector_preserves_newline_and_leading_whitespace_paths(
    git_repo: Path,
) -> None:
    review = _review()
    base = _git(git_repo, "rev-parse", "HEAD")
    leading = "  leading name.md"
    newline = "first\nsecond.md"
    (git_repo / leading).write_text("# Leading\n", encoding="utf-8")
    (git_repo / newline).write_text("# Newline\n", encoding="utf-8")
    raw_name = b"nonutf-\xff.md"
    window = review._resolve_git_window(git_repo, base_ref=None, head_ref=None)

    assert set(window.paths) == {leading, newline}
    assert set(window.raw_paths) == {os.fsencode(leading), os.fsencode(newline)}

    receipt_path = _receipt(git_repo)
    code = review.main(["--repo-root", str(git_repo), "--dry-run", "--receipt", str(receipt_path)])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    artifact_path = git_repo / receipt["inputs"]["changed_path_artifact"]["path"]
    rows = [
        json.loads(line)
        for line in gzip.decompress(artifact_path.read_bytes()).decode("utf-8").splitlines()
    ]

    assert code == 2
    assert {row["display_path"] for row in rows} == {leading, newline}
    assert {base64.b64decode(row["path_bytes_base64"]) for row in rows} == {
        os.fsencode(leading),
        os.fsencode(newline),
    }

    head = _commit(git_repo, "commit special paths")
    immutable = review._resolve_git_window(git_repo, base_ref=base, head_ref=head)
    assert set(immutable.raw_paths) == {os.fsencode(leading), os.fsencode(newline)}


def test_path_manifest_preserves_non_utf8_identity_as_base64(git_repo: Path) -> None:
    review = _review()
    raw_name = b"nonutf-\xff.md"
    output_path = _allocated_receipt(git_repo)
    artifact = review._changed_paths_artifact(git_repo, output_path, (raw_name,), {"used": 0})
    rows = [
        json.loads(line)
        for line in gzip.decompress((git_repo / artifact["path"]).read_bytes())
        .decode("utf-8")
        .splitlines()
    ]

    assert rows == [
        {
            "display_path": raw_name.decode("utf-8", errors="surrogateescape"),
            "path_bytes_base64": base64.b64encode(raw_name).decode("ascii"),
        }
    ]


def test_main_includes_tracked_docs_readme_regular_to_symlink_type_change(
    git_repo: Path,
) -> None:
    review = _review()
    docs_readme = git_repo / "docs" / "README.md"
    docs_readme.parent.mkdir()
    docs_readme.write_text("# Tracked docs readme\n", encoding="utf-8")
    base = _commit(git_repo, "add tracked docs README")
    docs_readme.unlink()
    docs_readme.symlink_to("../README.md")
    receipt_path = _receipt(git_repo)

    code = review.main(["--repo-root", str(git_repo), "--dry-run", "--receipt", str(receipt_path)])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert code == 2
    assert receipt["status"] == "UNRUN"
    assert receipt["inputs"]["changed_path_count"] == 1
    assert receipt["inputs"]["path_scope"]["included"].startswith("all Git-selected paths")
    assert "repository-root AGENTS.md" in receipt["inputs"]["path_scope"]["excluded"]
    assert receipt["inputs"]["changed_path_artifact"]["path"]
    assert any(
        "docs/README.md" in child["argv"] or child["key"] == "docs_accuracy"
        for child in receipt["plan"]["gate_commands"]
    )
    assert docs_readme.is_symlink()

    head = _commit(git_repo, "replace docs README with symlink")
    immutable_receipt = _receipt(git_repo)
    immutable_code = review.main(
        [
            "--repo-root",
            str(git_repo),
            "--base-ref",
            base,
            "--head-ref",
            head,
            "--dry-run",
            "--receipt",
            str(immutable_receipt),
        ]
    )
    immutable = json.loads(immutable_receipt.read_text(encoding="utf-8"))

    assert immutable_code == 2
    assert immutable["inputs"]["changed_path_count"] == 1
    assert any(child["key"] == "docs_accuracy" for child in immutable["plan"]["gate_commands"])


def test_main_preserves_both_rename_endpoints_for_d6_classification(
    git_repo: Path,
) -> None:
    review = _review()
    old_path = Path("docs/plans/active/legacy-plan.md")
    old_file = git_repo / old_path
    old_file.parent.mkdir(parents=True)
    old_file.write_text("# Historical plan\n", encoding="utf-8")
    base = _commit(git_repo, "add active plan")
    new_path = Path("misc/legacy-plan.md")
    new_file = git_repo / new_path
    new_file.parent.mkdir(parents=True)
    old_file.rename(new_file)
    worktree_window = review._resolve_git_window(git_repo, base_ref=None, head_ref=None)
    assert set(worktree_window.paths) == {old_path.as_posix(), new_path.as_posix()}
    head = _commit(git_repo, "move plan outside docs")
    receipt_path = _receipt(git_repo)

    code = review.main(
        [
            "--repo-root",
            str(git_repo),
            "--base-ref",
            base,
            "--head-ref",
            head,
            "--dry-run",
            "--receipt",
            str(receipt_path),
        ]
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    artifact_path = git_repo / receipt["inputs"]["changed_path_artifact"]["path"]
    rows = [
        json.loads(line)
        for line in gzip.decompress(artifact_path.read_bytes()).decode("utf-8").splitlines()
    ]
    changed = {row["display_path"] for row in rows}

    assert code == 2
    assert changed == {old_path.as_posix(), new_path.as_posix()}
    assert any(child["key"] == "docs_lifecycle" for child in receipt["plan"]["gate_commands"])
    assert receipt["inputs"]["path_scope"]["excluded"]


def test_corrupt_git_index_cannot_be_reported_as_an_empty_pass(
    git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    review = _review()
    (git_repo / "README.md").write_text("# Changed\n", encoding="utf-8")
    corrupt_index = tmp_path / "corrupt-index"
    corrupt_index.write_bytes(b"not a git index")
    monkeypatch.setenv("GIT_INDEX_FILE", str(corrupt_index))
    receipt_path = _receipt(git_repo)

    code = review.main(["--repo-root", str(git_repo), "--receipt", str(receipt_path)])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["verdict"] == "UNRUN"
    assert "index file smaller than expected" in output["reason"]
    assert not receipt_path.exists()


def test_tracked_output_paths_are_rejected_without_overwrite(
    git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review = _review()
    owned = git_repo / "_build" / "docs-maintenance" / "docs-review" / "review.json"
    owned.parent.mkdir(parents=True)
    owned.write_text('{"owner":"keep"}\n', encoding="utf-8")
    _git(git_repo, "add", "-f", "_build/docs-maintenance/docs-review/review.json")
    _commit(git_repo, "track owned docs review output")
    before = owned.read_bytes()

    code = review.main(["--repo-root", str(git_repo), "--receipt", str(owned), "--dry-run"])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["verdict"] == "UNRUN"
    assert owned.read_bytes() == before


def test_tracked_run_subtree_is_rejected_without_overwrite(
    git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review = _review()
    run_name = "run-11111111111111111111111111111111"
    owned = (
        git_repo
        / "_build"
        / "docs-maintenance"
        / "docs-review"
        / run_name
        / "raw"
        / "changed-paths.jsonl.gz"
    )
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"owned artifact\n")
    _git(
        git_repo,
        "add",
        "-f",
        f"_build/docs-maintenance/docs-review/{run_name}/raw/changed-paths.jsonl.gz",
    )
    _commit(git_repo, "track docs review raw output")
    before = owned.read_bytes()
    requested_receipt = owned.parents[1] / "review.json"

    code = review.main(
        [
            "--repo-root",
            str(git_repo),
            "--receipt",
            str(requested_receipt),
            "--dry-run",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["verdict"] == "UNRUN"
    assert "tracked paths" in output["reason"]
    assert owned.read_bytes() == before


def test_symlinked_output_root_is_rejected_without_writing_through(
    git_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review = _review()
    external = tmp_path / "external"
    external.mkdir()
    (git_repo / "_build").symlink_to(external, target_is_directory=True)
    receipt_path = _receipt(git_repo)

    code = review.main(["--repo-root", str(git_repo), "--dry-run", "--receipt", str(receipt_path)])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["verdict"] == "UNRUN"
    assert not list(external.iterdir())


def test_symlinked_run_directory_is_rejected_without_writing_through(
    git_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review = _review()
    external = tmp_path / "external"
    external.mkdir()
    output_root = git_repo / "_build" / "docs-maintenance" / "docs-review"
    output_root.mkdir(parents=True)
    run_name = "run-22222222222222222222222222222222"
    (output_root / run_name).symlink_to(external, target_is_directory=True)
    receipt_path = output_root / run_name / "review.json"

    code = review.main(["--repo-root", str(git_repo), "--dry-run", "--receipt", str(receipt_path)])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["verdict"] == "UNRUN"
    assert not list(external.iterdir())


def test_existing_run_directory_receipt_is_never_overwritten(
    git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review = _review()
    receipt_path = _receipt(git_repo)
    first = review.main(["--repo-root", str(git_repo), "--dry-run", "--receipt", str(receipt_path)])
    before = receipt_path.read_bytes()
    capsys.readouterr()

    second = review.main(
        ["--repo-root", str(git_repo), "--dry-run", "--receipt", str(receipt_path)]
    )
    output = json.loads(capsys.readouterr().out)

    assert first == 2
    assert second == 2
    assert output["verdict"] == "UNRUN"
    assert receipt_path.read_bytes() == before


def test_d6_early_failure_blocks_later_children_and_preserves_full_logs(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review()
    gate = import_module("tools.quality.validation.check_docs_gate")
    (git_repo / "README.md").write_text("# Changed\n", encoding="utf-8")
    marker = git_repo / "later-child-ran"
    plan = gate.GatePlan(
        commands=(
            gate.GateCommand(
                key="first",
                label="expected failure",
                argv=(sys.executable, "-c", "import sys; print('first-output'); sys.exit(1)"),
            ),
            gate.GateCommand(
                key="second",
                label="must be blocked",
                argv=(
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('later-child-ran').write_text('bad')",
                ),
            ),
        ),
        findings=(),
    )
    monkeypatch.setattr(review.check_docs_gate, "build_gate_plan", lambda _paths: plan)
    receipt_path = _receipt(git_repo)

    code = review.main(["--repo-root", str(git_repo), "--receipt", str(receipt_path)])

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    first, second = receipt["gate"]["children"]
    stdout = gzip.decompress((git_repo / first["stdout"]["path"]).read_bytes()).decode("utf-8")
    assert code == 1
    assert first["status"] == "FAIL"
    assert "first-output" in stdout
    assert second["status"] == "BLOCKED"
    assert second["blocked_by"] == "first"
    assert not marker.exists()


def test_impact_review_queue_is_not_mislabeled_as_a_gate_failure(
    git_repo: Path,
) -> None:
    review = _review()
    output_path = _allocated_receipt(git_repo)
    child_receipt = output_path.parent / "children" / "docs-impact.json"
    command = (
        sys.executable,
        "-c",
        (
            "import json, pathlib, sys; "
            "pathlib.Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True); "
            "pathlib.Path(sys.argv[1]).write_text(json.dumps({"
            "'status': 'REVIEW_REQUIRED', 'summary': {'human_review_page_count': 2}})); "
            "print(json.dumps({'status': 'REVIEW_REQUIRED', 'summary': "
            "{'human_review_page_count': 2}, 'receipt_path': sys.argv[1]})); sys.exit(1)"
        ),
        str(child_receipt),
    )

    result = review._run_child(
        git_repo,
        output_path,
        lane="independent",
        sequence=2,
        key="docs_impact",
        label="source impact",
        argv=command,
        budget_state={"used": 0},
        receipt_path=child_receipt,
    )

    assert result["status"] == "REVIEW_REQUIRED"
    assert result["impact_status"] == "REVIEW_REQUIRED"
    assert result["human_review_page_count"] == 2
    overall = review._overall_status(
        {"status": "PASS"},
        {
            "requested": True,
            "style": {"status": "PASS"},
            "impact": result,
            "build": {"status": "PASS"},
            "rendered_links": {"status": "PASS"},
        },
        dry_run=False,
    )
    assert overall == "REVIEW_REQUIRED"


def test_missing_impact_receipt_keeps_review_queue_unrun(git_repo: Path) -> None:
    review = _review()
    output_path = _allocated_receipt(git_repo)
    child_receipt = output_path.parent / "children" / "missing-impact.json"
    command = (
        sys.executable,
        "-c",
        (
            "import json, sys; print(json.dumps({'status': 'REVIEW_REQUIRED', "
            "'summary': {'human_review_page_count': 1}})); sys.exit(1)"
        ),
    )

    result = review._run_child(
        git_repo,
        output_path,
        lane="independent",
        sequence=2,
        key="docs_impact",
        label="source impact without receipt",
        argv=command,
        budget_state={"used": 0},
        receipt_path=child_receipt,
    )

    assert result["status"] == "UNRUN"
    assert result["process_status"] == "REVIEW_REQUIRED"
    assert result["child_receipt_status"] == "UNRUN"


def test_explicit_site_output_must_match_mkdocs_configuration(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review()
    configured_site = git_repo / "_build" / "site"
    monkeypatch.setattr(
        review,
        "_mkdocs_site_configuration",
        lambda _root: (configured_site, "https://example.test/docs/"),
    )

    selected, site_url, reason = review._site_choice(
        git_repo, git_repo / "_build" / "alternate-site"
    )

    assert selected == configured_site
    assert site_url == "https://example.test/docs/"
    assert (
        reason
        == "--site-dir does not match the configured MkDocs site_dir; no alternate build is run"
    )


def test_independent_build_runs_after_d6_blocks_it_and_is_not_repeated(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review()
    gate = import_module("tools.quality.validation.check_docs_gate")
    plan = gate.GatePlan(
        commands=(
            gate.GateCommand("docs_lifecycle", "lifecycle", ("d6-first",)),
            gate.GateCommand("strict_docs_build", "strict build", ("strict-build",)),
        ),
        findings=(),
    )
    gate_result = {
        "status": "UNRUN",
        "children": [
            {"key": "docs_lifecycle", "status": "UNRUN"},
            {"key": "strict_docs_build", "status": "BLOCKED", "blocked_by": "docs_lifecycle"},
        ],
        "findings": [],
    }
    calls: list[str] = []

    def fake_child(
        _repo_root: Path,
        _output_path: Path,
        *,
        key: str,
        argv,
        receipt_path=None,
        **_kwargs,
    ):
        calls.append(key)
        if key == "docs_impact":
            return {"key": key, "status": "UNRUN", "reason": "test has no immutable refs"}
        if key == "rendered_links":
            assert "--site-dir" in argv
            assert "--site-url" in argv
            assert receipt_path is not None
        return {"key": key, "status": "PASS", "argv": list(argv)}

    monkeypatch.setattr(review, "_run_child", fake_child)
    monkeypatch.setattr(
        review,
        "_mkdocs_site_configuration",
        lambda root: (root / "_build" / "site", "https://example.test/docs/"),
    )

    independent = review._run_independent(
        git_repo,
        _allocated_receipt(git_repo),
        review.GitWindow(None, None, None, None, None, None, None, ("README.md",), "test"),
        plan,
        gate_result,
        {"used": 0},
        dry_run=False,
        run_independent=True,
        requested_site_dir=None,
        workspace_mismatch_reason=None,
    )

    assert calls == ["docs_style", "strict_docs_build", "rendered_links"]
    assert independent["impact"]["status"] == "UNRUN"
    assert independent["build"]["status"] == "PASS"
    assert independent["rendered_links"]["status"] == "PASS"
    assert gate_result["children"][1]["status"] == "BLOCKED"


def test_unretained_child_output_cannot_be_reported_as_a_pass(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review()
    monkeypatch.setattr(review, "MAX_COMPRESSED_LOG_BYTES", 0)

    child = review._run_child(
        git_repo,
        _allocated_receipt(git_repo),
        lane="test",
        sequence=1,
        key="simple",
        label="print one line",
        argv=(sys.executable, "-c", "print('output')"),
        budget_state={"used": 0},
    )

    assert child["exit_code"] == 0
    assert child["status"] == "UNRUN"
    assert child["log_status"] == "UNRUN"
    assert "exceed" in child["log_reason"]
