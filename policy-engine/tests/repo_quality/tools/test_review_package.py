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


def _init_repo(tmp_path: Path, *, name: str = "fixture-repo") -> tuple[Path, str]:
    """Create a temporary repository with one committed baseline file."""

    repo = tmp_path / name
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
    _git(repo, "config", "color.diff.meta", "red bold")
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
        "GIT_DIFF_OPTS": "--unified=12",
        "GIT_EXTERNAL_DIFF": str(hostile_driver),
        "GIT_ATTR_SOURCE": base,
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
        "color.diff.meta",
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
    assert b"diff --git" not in _section_payload(first_bytes, "diff_stat")
    assert b"diff --git" not in _section_payload(first_bytes, "name_status")
    assert b"diff --git" in _section_payload(first_bytes, "patch")


def test_submodule_gitlink_change_survives_hostile_ignore_configuration(tmp_path: Path) -> None:
    """Catch a configured submodule ignore that silently removes a changed gitlink."""

    child, _ = _init_repo(tmp_path, name="submodule-source")
    parent, _ = _init_repo(tmp_path, name="parent-repo")
    _git(
        parent,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(child),
        "vendor/sub",
    )
    prior_review_point = _commit(parent, "add reviewed submodule")

    (child / "module.py").write_text("VERSION = 2\n", encoding="utf-8")
    child_head = _commit(child, "advance submodule")
    checkout = parent / "vendor" / "sub"
    _git(checkout, "-c", "protocol.file.allow=always", "fetch", "origin")
    _git(checkout, "checkout", child_head)
    head = _commit(parent, "advance submodule gitlink")
    _git(parent, "config", "diff.ignoreSubmodules", "all")
    _git(parent, "config", "diff.submodule", "log")
    output = parent / "submodule.review"

    result = _run_builder(
        parent,
        base=prior_review_point,
        head=head,
        output=output,
    )

    assert result.returncode == 0, result.stderr
    package = output.read_bytes()
    assert _section_payload(package, "name_status") == b"M\tvendor/sub\n"
    patch = _section_payload(package, "patch")
    assert b"Subproject commit " in patch
    assert child_head.encode() in patch
    assert b"Submodule vendor/sub " not in patch


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


def test_same_range_ignores_worktree_attributes_and_refuses_info_attributes(
    tmp_path: Path,
) -> None:
    """Catch unversioned attributes changing the bytes for two resolved commits."""

    repo, _ = _init_repo(tmp_path)
    policy = repo / "policy.txt"
    policy.write_text("line one\nold decision\nline three\n", encoding="utf-8")
    base = _commit(repo, "add policy")
    policy.write_text("line one\nnew decision\nline three\n", encoding="utf-8")
    head = _commit(repo, "change policy")
    clean_output = repo / "clean.review"
    clean = _run_builder(repo, base=base, head=head, output=clean_output)
    assert clean.returncode == 0, clean.stderr

    (repo / ".gitattributes").write_text("policy.txt -diff\n", encoding="utf-8")
    dirty_output = repo / "dirty.review"
    dirty = _run_builder(repo, base=base, head=head, output=dirty_output)

    assert dirty.returncode == 0, dirty.stderr
    assert dirty_output.read_bytes() == clean_output.read_bytes()

    info_attributes_raw = _git(repo, "rev-parse", "--git-path", "info/attributes").stdout.strip()
    info_attributes = Path(info_attributes_raw)
    if not info_attributes.is_absolute():
        info_attributes = repo / info_attributes
    info_attributes.parent.mkdir(parents=True, exist_ok=True)
    info_attributes.write_text("policy.txt -diff\n", encoding="utf-8")
    existing_output = repo / "existing.review"
    existing_output.write_bytes(b"previous-valid-package\n")
    refused = _run_builder(repo, base=base, head=head, output=existing_output)

    assert refused.returncode != 0
    assert "info/attributes" in refused.stderr
    assert existing_output.read_bytes() == b"previous-valid-package\n"


def test_unbound_local_diff_setting_fails_closed_without_replacing_output(
    tmp_path: Path,
) -> None:
    """Catch an arbitrary repository-local diff setting changing reviewed bytes."""

    repo, _ = _init_repo(tmp_path)
    policy = repo / "policy.py"
    policy.write_text("first = 1\n\nlast = 3\n", encoding="utf-8")
    base = _commit(repo, "add policy")
    policy.write_text("first = 2\n\nlast = 3\n", encoding="utf-8")
    head = _commit(repo, "change policy")
    output = repo / "review" / "existing.review"
    output.parent.mkdir()
    clean = _run_builder(repo, base=base, head=head, output=output)
    assert clean.returncode == 0, clean.stderr
    clean_bytes = output.read_bytes()

    _git(repo, "config", "diff.suppressBlankEmpty", "true")
    configured = _run_builder(repo, base=base, head=head, output=output)

    assert configured.returncode != 0
    assert "local:diff.suppressblankempty" in configured.stderr.lower()
    assert output.read_bytes() == clean_bytes


def test_unbound_local_diff_driver_setting_fails_closed_for_committed_attributes(
    tmp_path: Path,
) -> None:
    """Catch a local driver setting changing a diff selected by committed attributes."""

    repo, _ = _init_repo(tmp_path)
    (repo / ".gitattributes").write_text("*.py diff=hostile\n", encoding="utf-8")
    policy = repo / "policy.py"
    policy.write_text("DECISION = 'limited'\n", encoding="utf-8")
    base = _commit(repo, "add attributed policy")
    policy.write_text("DECISION = 'admissible'\n", encoding="utf-8")
    head = _commit(repo, "change attributed policy")
    output = repo / "existing.review"
    clean = _run_builder(repo, base=base, head=head, output=output)
    assert clean.returncode == 0, clean.stderr
    clean_bytes = output.read_bytes()

    _git(repo, "config", "diff.hostile.binary", "true")
    configured = _run_builder(repo, base=base, head=head, output=output)

    assert configured.returncode != 0
    assert "local:diff.hostile.binary" in configured.stderr.lower()
    assert output.read_bytes() == clean_bytes


def test_unbound_worktree_diff_driver_variant_fails_closed(
    tmp_path: Path,
) -> None:
    """Catch an arbitrary output-affecting driver key in worktree config scope."""

    repo, _ = _init_repo(tmp_path)
    (repo / ".gitattributes").write_text("*.py diff=hostile\n", encoding="utf-8")
    policy = repo / "policy.py"
    policy.write_text(
        "def decide() -> str:\n    return 'limited'\n",
        encoding="utf-8",
    )
    base = _commit(repo, "add attributed policy")
    policy.write_text(
        "def decide() -> str:\n    return 'admissible'\n",
        encoding="utf-8",
    )
    head = _commit(repo, "change attributed policy")
    output = repo / "existing.review"
    clean = _run_builder(repo, base=base, head=head, output=output)
    assert clean.returncode == 0, clean.stderr
    clean_bytes = output.read_bytes()

    _git(repo, "config", "extensions.worktreeConfig", "true")
    _git(repo, "config", "--worktree", "diff.hostile.xfuncname", "^def ")
    configured = _run_builder(repo, base=base, head=head, output=output)

    assert configured.returncode != 0
    assert "worktree:diff.hostile.xfuncname" in configured.stderr.lower()
    assert output.read_bytes() == clean_bytes


@pytest.mark.parametrize(
    ("scope", "key", "value"),
    [
        ("local", "core.bigFileThreshold", "1"),
        ("worktree", "core.abbrev", "4"),
    ],
)
def test_unbound_non_diff_repository_configuration_fails_closed(
    tmp_path: Path,
    scope: str,
    key: str,
    value: str,
) -> None:
    """Catch non-diff configuration escaping the repository config boundary."""

    repo, _ = _init_repo(tmp_path)
    policy = repo / "policy.txt"
    policy.write_text("line one\nold decision\nline three\n", encoding="utf-8")
    base = _commit(repo, "add policy")
    policy.write_text("line one\nnew decision\nline three\n", encoding="utf-8")
    head = _commit(repo, "change policy")
    output = repo / "existing.review"
    clean = _run_builder(repo, base=base, head=head, output=output)
    assert clean.returncode == 0, clean.stderr
    clean_bytes = output.read_bytes()

    config_scope: tuple[str, ...] = ()
    if scope == "worktree":
        _git(repo, "config", "extensions.worktreeConfig", "true")
        config_scope = ("--worktree",)
    _git(repo, "config", *config_scope, key, value)
    configured = _run_builder(repo, base=base, head=head, output=output)

    assert configured.returncode != 0
    assert f"{scope}:{key}".lower() in configured.stderr.lower()
    assert output.read_bytes() == clean_bytes


def test_non_diff_configuration_added_during_render_prevents_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch repository configuration changing after the initial boundary check."""

    repo, base = _init_repo(tmp_path)
    (repo / "policy.txt").write_text("changed policy\n", encoding="utf-8")
    head = _commit(repo, "change policy")
    output = repo / "existing.review"
    output.write_bytes(b"previous-valid-package\n")
    render_package = review_package._render_package

    def _render_then_configure(
        worktree: Path,
        *,
        base_commit: str,
        head_commit: str,
        prior_findings: bytes | None,
    ) -> bytes:
        package = render_package(
            worktree,
            base_commit=base_commit,
            head_commit=head_commit,
            prior_findings=prior_findings,
        )
        _git(repo, "config", "core.bigFileThreshold", "1")
        return package

    monkeypatch.setattr(review_package, "_render_package", _render_then_configure)

    with pytest.raises(review_package.ReviewPackageError, match=r"core\.bigfilethreshold"):
        review_package.build_review_package(
            base_revision=base,
            head_revision=head,
            output_path=output,
            invocation_cwd=repo,
        )

    assert output.read_bytes() == b"previous-valid-package\n"


def test_core_worktree_cannot_pivot_the_invoking_repository(tmp_path: Path) -> None:
    """Catch repository config redirecting all post-discovery Git commands."""

    source, _ = _init_repo(tmp_path, name="source-repo")
    source_policy = source / "policy.txt"
    source_policy.write_text("source old\n", encoding="utf-8")
    source_base = _commit(source, "source base")
    source_policy.write_text("source new\n", encoding="utf-8")
    source_head = _commit(source, "source head")

    foreign, _ = _init_repo(tmp_path, name="foreign-repo")
    foreign_policy = foreign / "policy.txt"
    foreign_policy.write_text("foreign old\n", encoding="utf-8")
    foreign_base = _commit(foreign, "foreign base")
    foreign_policy.write_text("foreign new\n", encoding="utf-8")
    foreign_head = _commit(foreign, "foreign head")

    _git(source, "config", "core.worktree", str(foreign))
    output = source / "source.review"
    result = _run_builder(
        source,
        base="HEAD^",
        head="HEAD",
        output=output,
    )

    assert result.returncode == 0, result.stderr
    package = output.read_bytes()
    assert f"base_commit={source_base}\n".encode() in package
    assert f"head_commit={source_head}\n".encode() in package
    assert b"source new" in package
    assert foreign_base.encode() not in package
    assert foreign_head.encode() not in package
    assert b"foreign new" not in package


def test_info_grafts_cannot_forge_the_ancestry_gate(tmp_path: Path) -> None:
    """Catch an unversioned graft making unrelated histories reviewable."""

    repo, base = _init_repo(tmp_path)
    _git(repo, "switch", "--orphan", "foreign")
    _git(
        repo,
        "rm",
        "-rf",
        "--ignore-unmatch",
        "--",
        ".gitignore",
        "README.md",
        "config.ini",
        "obsolete.txt",
    )
    (repo / "foreign.txt").write_text("foreign history\n", encoding="utf-8")
    head = _commit(repo, "foreign root")
    grafts = repo / ".git" / "info" / "grafts"
    grafts.write_text(f"{head} {base}\n", encoding="ascii")
    output = repo / "existing.review"
    output.write_bytes(b"previous-valid-package\n")

    result = _run_builder(repo, base=base, head=head, output=output)

    assert result.returncode != 0
    assert "not an ancestor" in result.stderr
    assert output.read_bytes() == b"previous-valid-package\n"


def test_shallow_metadata_cannot_change_commit_list_bytes(tmp_path: Path) -> None:
    """Catch a repository shallow boundary hiding a side-parent commit."""

    repo, base = _init_repo(tmp_path)
    _git(repo, "switch", "-c", "side")
    (repo / "side-one.txt").write_text("side one\n", encoding="utf-8")
    side_one = _commit(repo, "side one")
    (repo / "side-two.txt").write_text("side two\n", encoding="utf-8")
    side_two = _commit(repo, "side two")
    _git(repo, "switch", "main")
    (repo / "main.txt").write_text("main\n", encoding="utf-8")
    _commit(repo, "main change")
    _git(repo, "merge", "--no-gpg-sign", "--no-ff", "side", "-m", "merge side")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    clean_output = repo / "clean.review"
    clean = _run_builder(repo, base=base, head=head, output=clean_output)
    assert clean.returncode == 0, clean.stderr
    clean_bytes = clean_output.read_bytes()
    assert side_one.encode() in clean_bytes
    assert side_two.encode() in clean_bytes

    (repo / ".git" / "shallow").write_text(f"{side_two}\n", encoding="ascii")
    shallow_output = repo / "shallow.review"
    shallow = _run_builder(repo, base=base, head=head, output=shallow_output)

    assert shallow.returncode == 0, shallow.stderr
    assert shallow_output.read_bytes() == clean_bytes


def test_transient_configuration_cannot_change_rendered_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch a byte-affecting setting installed only during Git rendering."""

    repo, _ = _init_repo(tmp_path)
    policy = repo / "policy.txt"
    policy.write_text("old decision\n", encoding="utf-8")
    base = _commit(repo, "policy base")
    policy.write_text("new decision\n", encoding="utf-8")
    head = _commit(repo, "policy head")
    clean_output = repo / "clean.review"
    clean_package = review_package.build_review_package(
        base_revision=base,
        head_revision=head,
        output_path=clean_output,
        invocation_cwd=repo,
    )
    render_package = review_package._render_package
    injected = False

    def _render_with_transient_configuration(*args: object, **kwargs: object) -> bytes:
        nonlocal injected
        injected = True
        _git(repo, "config", "core.bigFileThreshold", "1")
        try:
            return render_package(*args, **kwargs)
        finally:
            _git(repo, "config", "--unset-all", "core.bigFileThreshold")

    monkeypatch.setattr(review_package, "_render_package", _render_with_transient_configuration)
    raced_output = repo / "raced.review"
    raced_package = review_package.build_review_package(
        base_revision=base,
        head_revision=head,
        output_path=raced_output,
        invocation_cwd=repo,
    )

    assert injected is True
    assert raced_package == clean_package
    assert raced_output.read_bytes() == clean_output.read_bytes()


def test_inherited_git_template_cannot_change_rendered_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch a caller template seeding byte-affecting bare-repository attributes."""

    repo, _ = _init_repo(tmp_path)
    policy = repo / "policy.txt"
    policy.write_text("old decision\n", encoding="utf-8")
    base = _commit(repo, "policy base")
    policy.write_text("new decision\n", encoding="utf-8")
    head = _commit(repo, "policy head")
    clean_output = repo / "clean.review"
    clean_package = review_package.build_review_package(
        base_revision=base,
        head_revision=head,
        output_path=clean_output,
        invocation_cwd=repo,
    )

    template = tmp_path / "git-template"
    (template / "info").mkdir(parents=True)
    (template / "info" / "attributes").write_text("*.txt -diff\n", encoding="utf-8")
    monkeypatch.setenv("GIT_TEMPLATE_DIR", str(template))
    templated_output = repo / "templated.review"
    templated_package = review_package.build_review_package(
        base_revision=base,
        head_revision=head,
        output_path=templated_output,
        invocation_cwd=repo,
    )

    assert templated_package == clean_package
    assert templated_output.read_bytes() == clean_output.read_bytes()


def test_output_parent_swap_cannot_escape_the_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch an output parent replaced by a symlink after path validation."""

    repo, base = _init_repo(tmp_path)
    (repo / "fix.py").write_text("FIXED = True\n", encoding="utf-8")
    head = _commit(repo, "fix")
    output_parent = repo / "review"
    output_parent.mkdir()
    output = output_parent / "existing.review"
    output.write_bytes(b"previous-valid-package\n")
    displaced_parent = repo / "review-before-swap"
    outside = tmp_path / "outside"
    outside.mkdir()
    render_package = review_package._render_package

    def _render_then_swap_parent(*args: object, **kwargs: object) -> bytes:
        package = render_package(*args, **kwargs)
        output_parent.rename(displaced_parent)
        output_parent.symlink_to(outside, target_is_directory=True)
        return package

    monkeypatch.setattr(review_package, "_render_package", _render_then_swap_parent)

    with pytest.raises(review_package.ReviewPackageError):
        review_package.build_review_package(
            base_revision=base,
            head_revision=head,
            output_path=output,
            invocation_cwd=repo,
        )

    assert not (outside / output.name).exists()
    assert (displaced_parent / output.name).read_bytes() == b"previous-valid-package\n"


def test_output_parent_swap_during_replace_restores_prior_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch the final parent-check/replace window destroying a displaced package."""

    repo, base = _init_repo(tmp_path)
    (repo / "fix.py").write_text("FIXED = True\n", encoding="utf-8")
    head = _commit(repo, "fix")
    output_parent = repo / "review"
    output_parent.mkdir()
    output = output_parent / "existing.review"
    original = b"previous-valid-package\n"
    output.write_bytes(original)
    displaced_parent = repo / "review-before-replace-swap"
    outside = tmp_path / "outside"
    outside.mkdir()
    replace = review_package.os.replace
    swapped = False

    def _swap_parent_then_replace(
        source: str | bytes,
        destination: str | bytes,
        **kwargs: object,
    ) -> None:
        nonlocal swapped
        if not swapped and destination == output.name and kwargs.get("dst_dir_fd") is not None:
            output_parent.rename(displaced_parent)
            output_parent.symlink_to(outside, target_is_directory=True)
            swapped = True
        replace(source, destination, **kwargs)

    monkeypatch.setattr(review_package.os, "replace", _swap_parent_then_replace)

    with pytest.raises(review_package.ReviewPackageError, match="output parent changed"):
        review_package.build_review_package(
            base_revision=base,
            head_revision=head,
            output_path=output,
            invocation_cwd=repo,
        )

    assert swapped is True
    assert not (outside / output.name).exists()
    assert (displaced_parent / output.name).read_bytes() == original
    assert list(displaced_parent.glob(".polisyos-review-*.tmp")) == []


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


def test_delta_rejects_casefolded_and_hardlinked_checklist_output_aliases(
    tmp_path: Path,
) -> None:
    """Catch filesystem aliases that bypass a lexical output/checklist comparison."""

    repo, base = _init_repo(tmp_path)
    (repo / "fix.py").write_text("FIXED = True\n", encoding="utf-8")
    head = _commit(repo, "fix")
    findings = repo / "Findings.md"
    findings_bytes = b"Important finding\n"
    findings.write_bytes(findings_bytes)

    casefolded_output = repo / "findings.md"
    if casefolded_output.exists() and casefolded_output.samefile(findings):
        casefolded = _run_builder(
            repo,
            base=base,
            head=head,
            output=casefolded_output,
            prior_findings=findings,
        )
        assert casefolded.returncode != 0
        assert findings.read_bytes() == findings_bytes

    hardlinked_output = repo / "hardlinked-output.review"
    os.link(findings, hardlinked_output)
    hardlinked = _run_builder(
        repo,
        base=base,
        head=head,
        output=hardlinked_output,
        prior_findings=findings,
    )
    assert hardlinked.returncode != 0
    assert findings.read_bytes() == findings_bytes
    assert hardlinked_output.read_bytes() == findings_bytes


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

    def _interrupt_replace(
        _source: str | bytes,
        _destination: str | bytes,
        **_kwargs: object,
    ) -> None:
        raise OSError("simulated interruption before atomic replace")

    monkeypatch.setattr(review_package.os, "replace", _interrupt_replace)

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
    full_package = full_output.read_bytes()
    diff_stat = _section_payload(full_package, "diff_stat")
    patch = _section_payload(full_package, "patch")
    assert b"diff --git" not in diff_stat
    assert len(diff_stat) * 10 < len(patch)
    assert len(full_package) < len(patch) * 1.25
