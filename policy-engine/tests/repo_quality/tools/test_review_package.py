from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.quality.testing import build_review_package as review_package

REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_PACKAGE_BUILDER = REPO_ROOT / "tools" / "quality" / "testing" / "build_review_package.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run Git in a real temporary repository with deterministic test identity."""

    return subprocess.run(  # noqa: S603 - arguments are controlled test fixtures.
        [
            "git",
            "-c",
            "user.name=PolicyOS Test",
            "-c",
            "user.email=policyos-test@example.invalid",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _commit(repo: Path, message: str) -> str:
    """Commit the temporary repository and return its full object id."""

    _git(repo, "add", "-A")
    _git(repo, "commit", "--no-gpg-sign", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    """Create a temporary repository with one committed baseline file."""

    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / ".gitignore").write_text("*.review\n", encoding="utf-8")
    (repo / "README.md").write_text("# Fixture\n", encoding="utf-8")
    (repo / "config.ini").write_text("status=limited\n", encoding="utf-8")
    (repo / "obsolete.txt").write_text("remove me\n", encoding="utf-8")
    return repo, _commit(repo, "initial")


def _run_builder(
    repo: Path,
    *,
    base: str,
    head: str,
    output: Path,
    prior_findings: Path | None = None,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the standalone builder exactly as a reviewer workflow would."""

    argv = [
        sys.executable,
        str(REVIEW_PACKAGE_BUILDER),
        "--base",
        base,
        "--head",
        head,
        "--output",
        str(output),
    ]
    if prior_findings is not None:
        argv.extend(("--prior-findings", str(prior_findings)))
    return subprocess.run(  # noqa: S603 - repository-local script and controlled argv.
        argv,
        cwd=cwd or repo,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _section_payload(package: bytes, name: str) -> bytes:
    """Extract a length-delimited section without interpreting its payload."""

    marker = f"section={name}\n".encode("ascii")
    metadata_start = package.index(marker) + len(marker)
    payload_start = package.index(b"\n\n", metadata_start) + 2
    metadata = package[metadata_start : payload_start - 2].splitlines()
    length_line = next(line for line in metadata if line.startswith(b"length="))
    length = int(length_line.removeprefix(b"length="))
    return package[payload_start : payload_start + length]


def test_full_package_is_deterministic_and_contains_every_changed_path(tmp_path: Path) -> None:
    """Catch volatile output or a renderer that omits part of the reviewed change."""

    repo, base = _init_repo(tmp_path)
    source = repo / "src" / "policy.py"
    source.parent.mkdir()
    source.write_text("def decide() -> str:\n    return 'admissible'\n", encoding="utf-8")
    asset = repo / "assets" / "evidence.bin"
    asset.parent.mkdir()
    asset.write_bytes(b"\x00policy-evidence\xff")
    docs = repo / "docs"
    docs.mkdir()
    (repo / "README.md").rename(docs / "README.md")
    (repo / "config.ini").write_text("status=admissible\n", encoding="utf-8")
    (repo / "obsolete.txt").unlink()
    (repo / ".gitattributes").write_text("config.ini diff=hostile\n", encoding="utf-8")
    head = _commit(repo, "add policy decision")
    nested_cwd = repo / "review" / "work"
    nested_cwd.mkdir(parents=True)
    first = repo / "review" / "full-one.review"
    second = repo / "review" / "full-two.review"
    external_diff_sentinel = repo / "EXTERNAL_DIFF_EXECUTED"
    hostile_driver = repo / "hostile-external-diff.sh"
    hostile_driver.write_text(
        "#!/bin/sh\nprintf invoked > " + str(external_diff_sentinel) + "\nexit 71\n",
        encoding="utf-8",
    )
    hostile_driver.chmod(0o755)
    hostile_order = repo / "hostile-diff-order"
    hostile_order.write_text(
        "obsolete.txt\nconfig.ini\ndocs/README.md\nassets/evidence.bin\nsrc/policy.py\n",
        encoding="utf-8",
    )
    _git(repo, "config", "color.ui", "always")
    _git(repo, "config", "core.quotePath", "false")
    _git(repo, "config", "diff.algorithm", "minimal")
    _git(repo, "config", "diff.context", "9")
    _git(repo, "config", "diff.external", str(hostile_driver))
    _git(repo, "config", "diff.hostile.textconv", str(hostile_driver))
    _git(repo, "config", "diff.indentHeuristic", "true")
    _git(repo, "config", "diff.interHunkContext", "7")
    _git(repo, "config", "diff.mnemonicPrefix", "true")
    _git(repo, "config", "diff.noprefix", "true")
    _git(repo, "config", "diff.orderFile", str(hostile_order))
    _git(repo, "config", "diff.renameLimit", "1")
    hostile_environment = {
        **os.environ,
        "GIT_COMMON_DIR": str(repo / "foreign-common-dir"),
        "GIT_DIR": str(repo / "foreign-git-dir"),
        "GIT_EXTERNAL_DIFF": str(hostile_driver),
        "GIT_OBJECT_DIRECTORY": str(repo / "foreign-objects"),
        "GIT_PAGER": str(hostile_driver),
        "GIT_WORK_TREE": str(repo / "foreign-worktree"),
    }

    first_run = _run_builder(
        repo,
        base=base,
        head=head,
        output=first,
        cwd=repo,
        environment=hostile_environment,
    )
    for key in (
        "color.ui",
        "core.quotePath",
        "diff.algorithm",
        "diff.context",
        "diff.external",
        "diff.hostile.textconv",
        "diff.indentHeuristic",
        "diff.interHunkContext",
        "diff.mnemonicPrefix",
        "diff.noprefix",
        "diff.orderFile",
        "diff.renameLimit",
    ):
        _git(repo, "config", "--unset-all", key)
    second_run = _run_builder(repo, base=base, head=head, output=second, cwd=nested_cwd)

    assert first_run.returncode == 0, first_run.stderr
    assert second_run.returncode == 0, second_run.stderr
    first_bytes = first.read_bytes()
    assert second.read_bytes() == first_bytes
    assert b"schema_version=1\n" in first_bytes
    assert b"package_kind=full\n" in first_bytes
    assert f"base_commit={base}\n".encode() in first_bytes
    assert f"head_commit={head}\n".encode() in first_bytes
    assert b"src/policy.py" in first_bytes
    assert b"assets/evidence.bin" in first_bytes
    assert b"config.ini" in first_bytes
    assert b".gitattributes" in first_bytes
    assert b"obsolete.txt" in first_bytes
    assert b"README.md" in first_bytes
    assert str(first).encode() not in first_bytes
    assert str(second).encode() not in first_bytes
    assert b"created_at" not in first_bytes
    assert not external_diff_sentinel.exists()


def test_invalid_revisions_and_non_ancestor_ranges_fail_without_replacing_output(
    tmp_path: Path,
) -> None:
    """Catch trust-by-form revisions or a failed build that destroys a valid package."""

    repo, base = _init_repo(tmp_path)
    (repo / "main.txt").write_text("main\n", encoding="utf-8")
    main_head = _commit(repo, "main change")
    _git(repo, "switch", "-c", "side", base)
    (repo / "side.txt").write_text("side\n", encoding="utf-8")
    side_head = _commit(repo, "side change")
    output = repo / "review" / "existing.review"
    output.parent.mkdir()
    original = b"previous-valid-package\n"
    output.write_bytes(original)

    invalid = _run_builder(repo, base="does-not-exist", head=side_head, output=output)
    non_ancestor = _run_builder(repo, base=main_head, head=side_head, output=output)

    assert invalid.returncode != 0
    assert non_ancestor.returncode != 0
    assert "not an ancestor" in non_ancestor.stderr
    assert output.read_bytes() == original


def test_delta_contains_only_fix_and_preserves_binary_findings_exactly(tmp_path: Path) -> None:
    """Catch a re-review that repeats old code or mutates its findings checklist."""

    repo, base = _init_repo(tmp_path)
    feature = repo / "policy" / "owner.py"
    feature.parent.mkdir()
    feature.write_text("AUTHORITY = 'verified'\n", encoding="utf-8")
    prior_review_point = _commit(repo, "add authority owner")
    fix = repo / "policy" / "fix.py"
    fix.write_text("FAIL_CLOSED = True\n", encoding="utf-8")
    head = _commit(repo, "fail closed on invalid evidence")
    findings_bytes = (
        b"Important: fail closed on malformed evidence.\r\n"
        b"section=patch\r\nlength=999\x00\r\n$(touch SHOULD_NOT_RUN)\xff"
    )
    findings = repo / "review;findings.bin"
    findings.write_bytes(findings_bytes)
    output = repo / "delta;review.package"

    result = _run_builder(
        repo,
        base=prior_review_point,
        head=head,
        output=output,
        prior_findings=findings,
    )

    assert result.returncode == 0, result.stderr
    package = output.read_bytes()
    assert b"package_kind=delta\n" in package
    assert f"base_commit={prior_review_point}\n".encode() in package
    assert b"policy/fix.py" in package
    assert b"policy/owner.py" not in package
    assert _section_payload(package, "prior_findings") == findings_bytes
    crlf_digest = hashlib.sha256(findings_bytes).hexdigest()
    assert f"sha256={crlf_digest}\n".encode() in package
    assert not (repo / "SHOULD_NOT_RUN").exists()
    assert base != prior_review_point

    lf_findings_bytes = findings_bytes.replace(b"\r\n", b"\n")
    lf_findings = repo / "lf-findings.bin"
    lf_findings.write_bytes(lf_findings_bytes)
    lf_output = repo / "lf-delta.review"
    lf_result = _run_builder(
        repo,
        base=prior_review_point,
        head=head,
        output=lf_output,
        prior_findings=lf_findings,
    )
    assert lf_result.returncode == 0, lf_result.stderr
    lf_digest = hashlib.sha256(lf_findings_bytes).hexdigest()
    assert lf_digest != crlf_digest
    assert f"sha256={lf_digest}\n".encode() in lf_output.read_bytes()


def test_delta_rejects_invalid_checklists_and_worktree_path_escapes(tmp_path: Path) -> None:
    """Catch a missing checklist or escaped path being accepted as review evidence."""

    repo, base = _init_repo(tmp_path)
    (repo / "fix.py").write_text("FIXED = True\n", encoding="utf-8")
    head = _commit(repo, "fix")
    review_dir = repo / "review"
    review_dir.mkdir()
    missing = review_dir / "missing.md"
    directory = review_dir / "findings-dir"
    directory.mkdir()
    empty = review_dir / "empty.md"
    empty.write_bytes(b"")
    outside = tmp_path / "outside-findings.md"
    outside.write_text("Important finding\n", encoding="utf-8")
    outside_link = review_dir / "outside-link.md"
    outside_link.symlink_to(outside)
    output = review_dir / "existing.review"
    output.write_bytes(b"previous-valid-package\n")

    for invalid_findings in (missing, directory, empty, outside, outside_link):
        result = _run_builder(
            repo,
            base=base,
            head=head,
            output=output,
            prior_findings=invalid_findings,
        )
        assert result.returncode != 0, invalid_findings
        assert output.read_bytes() == b"previous-valid-package\n"

    valid_findings = review_dir / "findings.md"
    valid_findings.write_text("No blocking findings.\n", encoding="utf-8")
    escaped_output = tmp_path / "outside.review"
    escaped = _run_builder(
        repo,
        base=base,
        head=head,
        output=escaped_output,
        prior_findings=valid_findings,
    )
    assert escaped.returncode != 0
    assert not escaped_output.exists()


def test_review_paths_reject_git_admin_targets_symlinks_and_input_output_aliases(
    tmp_path: Path,
) -> None:
    """Catch a package write that can corrupt Git state or overwrite its checklist."""

    repo, base = _init_repo(tmp_path)
    (repo / "fix.py").write_text("FIXED = True\n", encoding="utf-8")
    head = _commit(repo, "fix")
    findings = repo / "findings.md"
    findings.write_text("Important finding\n", encoding="utf-8")

    git_admin_output = repo / ".git" / "review.package"
    admin_result = _run_builder(repo, base=base, head=head, output=git_admin_output)
    assert admin_result.returncode != 0
    assert not git_admin_output.exists()

    casefolded_git_dir = repo / ".GIT"
    if casefolded_git_dir.exists():
        casefolded_admin_output = casefolded_git_dir / "casefold-review.package"
        casefolded_result = _run_builder(
            repo,
            base=base,
            head=head,
            output=casefolded_admin_output,
        )
        assert casefolded_result.returncode != 0
        assert not casefolded_admin_output.exists()

    linked_worktree = tmp_path / "linked-worktree"
    _git(repo, "worktree", "add", "--detach", str(linked_worktree), head)
    git_marker = linked_worktree / ".git"
    marker_bytes = git_marker.read_bytes()
    marker_result = _run_builder(
        linked_worktree,
        base=base,
        head=head,
        output=git_marker,
    )
    assert marker_result.returncode != 0
    assert git_marker.read_bytes() == marker_bytes

    common_dir_raw = _git(linked_worktree, "rev-parse", "--git-common-dir").stdout.strip()
    common_dir = Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = linked_worktree / common_dir
    common_dir_output = common_dir.resolve() / "review.package"
    common_dir_result = _run_builder(
        linked_worktree,
        base=base,
        head=head,
        output=common_dir_output,
    )
    assert common_dir_result.returncode != 0
    assert not common_dir_output.exists()

    real_output_dir = repo / "real-output"
    real_output_dir.mkdir()
    symlink_parent = repo / "linked-output"
    symlink_parent.symlink_to(real_output_dir, target_is_directory=True)
    linked_output = symlink_parent / "review.package"
    linked_result = _run_builder(repo, base=base, head=head, output=linked_output)
    assert linked_result.returncode != 0
    assert not (real_output_dir / "review.package").exists()

    existing_target = real_output_dir / "existing.package"
    existing_target.write_bytes(b"sentinel")
    output_symlink = repo / "output-link.package"
    output_symlink.symlink_to(existing_target)
    output_link_result = _run_builder(repo, base=base, head=head, output=output_symlink)
    assert output_link_result.returncode != 0
    assert existing_target.read_bytes() == b"sentinel"

    alias_result = _run_builder(
        repo,
        base=base,
        head=head,
        output=findings,
        prior_findings=findings,
    )
    assert alias_result.returncode != 0
    assert findings.read_bytes() == b"Important finding\n"


def test_late_git_failure_preserves_prior_valid_output(tmp_path: Path) -> None:
    """Catch partial output replacement after validation but before diff collection completes."""

    repo, base = _init_repo(tmp_path)
    changed = repo / "changed.txt"
    changed.write_text("content whose blob will be corrupted\n", encoding="utf-8")
    head = _commit(repo, "add changed blob")
    blob = _git(repo, "rev-parse", f"{head}:changed.txt").stdout.strip()
    object_path = repo / ".git" / "objects" / blob[:2] / blob[2:]
    object_path.chmod(0o644)
    object_path.write_bytes(b"corrupt-object")
    output = repo / "review" / "existing.review"
    output.parent.mkdir()
    output.write_bytes(b"previous-valid-package\n")

    result = _run_builder(repo, base=base, head=head, output=output)

    assert result.returncode != 0
    assert output.read_bytes() == b"previous-valid-package\n"


def test_interrupted_atomic_swap_preserves_prior_valid_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch a direct write that can tear or replace a valid package during interruption."""

    repo, base = _init_repo(tmp_path)
    (repo / "fix.py").write_text("FIXED = True\n", encoding="utf-8")
    head = _commit(repo, "fix")
    output = repo / "review" / "existing.review"
    output.parent.mkdir()
    output.write_bytes(b"previous-valid-package\n")

    def _interrupt_replace(_source: str | bytes, _destination: str | bytes) -> None:
        raise OSError("simulated interruption before atomic replace")

    monkeypatch.setattr("tools.lib.fs.os.replace", _interrupt_replace)

    with pytest.raises(OSError, match="simulated interruption"):
        review_package.build_review_package(
            base_revision=base,
            head_revision=head,
            output_path=output,
            invocation_cwd=repo,
        )

    assert output.read_bytes() == b"previous-valid-package\n"
    assert list(output.parent.glob(".*.tmp")) == []


def test_shell_metacharacters_in_revisions_and_paths_are_never_executed(tmp_path: Path) -> None:
    """Catch a builder that sends caller-controlled values through a shell."""

    repo, base = _init_repo(tmp_path)
    (repo / "fix.py").write_text("FIXED = True\n", encoding="utf-8")
    head = _commit(repo, "fix")
    marker = repo / "SHELL_EXECUTED"
    output = repo / "review;touch SHELL_EXECUTED"

    valid = _run_builder(repo, base=base, head=head, output=output)
    malicious_revision = _run_builder(
        repo,
        base=base,
        head=f"{head};touch SHELL_EXECUTED",
        output=output,
    )

    assert valid.returncode == 0, valid.stderr
    valid_bytes = output.read_bytes()
    assert malicious_revision.returncode != 0
    assert output.read_bytes() == valid_bytes
    assert not marker.exists()


def test_typical_fix_delta_is_at_most_one_tenth_of_its_full_package(tmp_path: Path) -> None:
    """Catch a delta renderer that repeats a realistically large first-review patch."""

    repo, base = _init_repo(tmp_path)
    feature = repo / "policy" / "admissibility_rules.py"
    feature.parent.mkdir()
    rules = [
        "from __future__ import annotations",
        "",
        "# A representative first review adds a substantial rule implementation.",
    ]
    for index in range(180):
        rules.extend(
            (
                f"def rule_{index:03d}(authority: str, status: str) -> bool:",
                f'    """Evaluate authority/status composition rule {index:03d}."""',
                f"    allowed = {{'authority-{index:03d}', 'delegated-{index:03d}'}}",
                "    return authority in allowed and status not in {'blocked', 'contested'}",
                "",
            )
        )
    feature.write_text("\n".join(rules), encoding="utf-8")
    prior_review_point = _commit(repo, "implement admissibility rule family")
    full_output = repo / "reviews" / "full.review"
    full = _run_builder(repo, base=base, head=prior_review_point, output=full_output)
    assert full.returncode == 0, full.stderr

    (repo / "policy" / "review_fix.py").write_text(
        "FAIL_CLOSED = True\n",
        encoding="utf-8",
    )
    head = _commit(repo, "refuse unverified evidence")
    findings = repo / "reviews" / "prior-findings.md"
    findings.write_text(
        "Important: unverified evidence must fail closed before promotion.\n",
        encoding="utf-8",
    )
    delta_output = repo / "reviews" / "delta.review"
    delta = _run_builder(
        repo,
        base=prior_review_point,
        head=head,
        output=delta_output,
        prior_findings=findings,
    )

    assert delta.returncode == 0, delta.stderr
    assert delta_output.stat().st_size <= full_output.stat().st_size / 10
