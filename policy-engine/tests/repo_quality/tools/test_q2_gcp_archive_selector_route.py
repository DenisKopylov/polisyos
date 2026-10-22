from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


def _repo_root() -> Path:
    supplied = os.environ.get("E02_Q2_SELECTOR_REPO_ROOT")
    if supplied:
        return Path(supplied).resolve(strict=True)
    return next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "policy-engine").is_dir()
        and ((parent / ".git").exists() or (parent / ".git").is_file())
    )


REPO_ROOT = _repo_root()
RUNNER_PATH = Path(
    os.environ.get(
        "E02_Q2_SELECTOR_RUNNER_PATH",
        str(
            REPO_ROOT / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
            "LOCAL/q2-packaging/raw/run.py"
        ),
    )
).resolve(strict=True)
PACKAGE_SCRIPT_PATH = Path(
    os.environ.get(
        "E02_Q2_SELECTOR_PACKAGE_SCRIPT_PATH",
        str(REPO_ROOT / "policy-engine/ops/cloud/gcp/package_repo.sh"),
    )
).resolve(strict=True)

_RUNNER_NAME = "e02_q2_frozen_gcp_route_under_test"
_RUNNER_SPEC = importlib.util.spec_from_file_location(_RUNNER_NAME, RUNNER_PATH)
if _RUNNER_SPEC is None or _RUNNER_SPEC.loader is None:
    raise RuntimeError("q2_frozen_gcp_route_runner_unavailable")
RUNNER = importlib.util.module_from_spec(_RUNNER_SPEC)
sys.modules[_RUNNER_NAME] = RUNNER
_RUNNER_SPEC.loader.exec_module(RUNNER)


def _git(repo: Path, *args: str) -> str:
    git = shutil.which("git")
    assert git is not None
    result = subprocess.run(  # noqa: S603 - argv is fixed to the local Git executable.
        [str(Path(git).resolve(strict=True)), "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def _fixture_repository(tmp_path: Path) -> tuple[Path, Path, str, str]:
    workspace = tmp_path / "workspace"
    product = workspace / "policy-engine"
    for relative in (
        "ops/cloud/gcp",
        "src",
        "tools",
        "schemas",
        "assets",
    ):
        (product / relative).mkdir(parents=True, exist_ok=True)
    (product / "README.md").write_bytes(b"fixture readme\n")
    (product / "pyproject.toml").write_bytes(
        b'[project]\nname = "q2-route-fixture"\nversion = "1.0"\n'
    )
    (product / "hatch.toml").write_bytes(
        b'[build.targets.wheel.force-include]\n"assets/probe.json" = "fixture/probe.json"\n'
    )
    (product / "uv.lock").write_bytes(b"version = 1\n")
    (product / "src/fixture.py").write_bytes(b"frozen fixture source = 1\n")
    (product / "tools/fixture.py").write_bytes(b"frozen fixture tool = 1\n")
    (product / "schemas/fixture.yaml").write_bytes(b"fixture: true\n")
    (product / "assets/probe.json").write_bytes(b'{"selected": "frozen"}\n')
    shutil.copyfile(
        PACKAGE_SCRIPT_PATH,
        product / "ops/cloud/gcp/package_repo.sh",
    )
    _git(workspace, "init", "-q")
    _git(workspace, "config", "user.name", "Q2 route fixture")
    _git(workspace, "config", "user.email", "q2-route@example.invalid")
    _git(workspace, "checkout", "-q", "-b", "q2-route-fixture")
    _git(workspace, "add", "--all")
    _git(workspace, "commit", "-q", "-m", "frozen selector fixture")
    source_sha = _git(workspace, "rev-parse", "HEAD")
    source_tree = _git(workspace, "rev-parse", "HEAD^{tree}")
    return workspace, product, source_sha, source_tree


def _frozen_product(tmp_path: Path, repo: Path, source_sha: str) -> Path:
    logs = tmp_path / "extract-logs"
    logs.mkdir()
    source_root = tmp_path / "frozen-source"
    _, frozen_product = RUNNER.extract_frozen_product(repo, source_sha, source_root, logs)
    assert frozen_product == source_root / "policy-engine"
    return frozen_product


def _run_selector(
    tmp_path: Path,
    repo: Path,
    frozen_product: Path,
    source_sha: str,
    source_tree: str,
    output: Path,
) -> dict[str, object]:
    return RUNNER.run_frozen_gcp_archive_selector(
        repo=repo,
        frozen_product=frozen_product,
        source_sha=source_sha,
        source_tree=source_tree,
        output=output,
        python_bin=Path(sys.executable),
        log_stem=tmp_path / "selector-logs" / "gcp-package",
    )


def test_frozen_selector_emits_pinned_archive_and_verifies_member_bytes(
    tmp_path: Path,
) -> None:
    repo, _, source_sha, source_tree = _fixture_repository(tmp_path)
    frozen_product = _frozen_product(tmp_path, repo, source_sha)
    output = tmp_path / "gcp-output"

    binding = _run_selector(tmp_path, repo, frozen_product, source_sha, source_tree, output)
    (tmp_path / "gcp-binding.json").write_text(
        json.dumps(binding, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    archive = Path(str(binding["archive_path"]))
    assert archive.is_file()
    assert binding["archive_sha256"] == RUNNER.sha256_file(archive)
    assert binding["source_sha"] == source_sha
    assert binding["source_tree"] == source_tree
    assert archive.name.endswith(f"-{binding['source_abbrev']}.tar.gz")
    assert set(binding["verified_members"]) == {
        "policy-engine/README.md",
        "policy-engine/pyproject.toml",
        "policy-engine/hatch.toml",
        "policy-engine/uv.lock",
        "policy-engine/ops/cloud/gcp/package_repo.sh",
    }
    assert binding["source_line"] == f"Created {archive} from committed source {source_sha}"
    assert (
        binding["selector_sha256"]
        == hashlib.sha256(
            (frozen_product / "ops/cloud/gcp/package_repo.sh").read_bytes()
        ).hexdigest()
    )
    assert "policy-engine/ops/cloud/gcp/package_repo.sh" in binding["verified_members"]
    with tarfile.open(archive, "r:gz") as bundle:
        source = bundle.extractfile("policy-engine/src/fixture.py")
        resource = bundle.extractfile("policy-engine/assets/probe.json")
        assert source is not None
        assert source.read() == b"frozen fixture source = 1\n"
        assert resource is not None
        assert resource.read() == b'{"selected": "frozen"}\n'


def test_frozen_selector_rejects_wrong_head_before_packaging(tmp_path: Path) -> None:
    repo, product, source_sha, source_tree = _fixture_repository(tmp_path)
    frozen_product = _frozen_product(tmp_path, repo, source_sha)
    (product / "README.md").write_bytes(b"a later committed source\n")
    _git(repo, "add", "policy-engine/README.md")
    _git(repo, "commit", "-q", "-m", "later source")
    output = tmp_path / "wrong-head-output"

    with pytest.raises(RUNNER.WaveFailure, match="HEAD differs from the supplied freeze"):
        _run_selector(tmp_path, repo, frozen_product, source_sha, source_tree, output)

    assert not output.exists()


def test_frozen_selector_rejects_tracked_dirty_source_before_packaging(
    tmp_path: Path,
) -> None:
    repo, product, source_sha, source_tree = _fixture_repository(tmp_path)
    frozen_product = _frozen_product(tmp_path, repo, source_sha)
    (product / "README.md").write_bytes(b"uncommitted tracked change\n")
    output = tmp_path / "dirty-output"

    with pytest.raises(RUNNER.WaveFailure, match="tracked source changes remain after freeze"):
        _run_selector(tmp_path, repo, frozen_product, source_sha, source_tree, output)

    assert not output.exists()


def test_frozen_selector_rejects_extracted_script_not_equal_to_git_blob(
    tmp_path: Path,
) -> None:
    repo, _, source_sha, source_tree = _fixture_repository(tmp_path)
    frozen_product = _frozen_product(tmp_path, repo, source_sha)
    selector = frozen_product / "ops/cloud/gcp/package_repo.sh"
    selector.write_bytes(selector.read_bytes() + b"\n# altered after git archive\n")
    output = tmp_path / "tampered-selector-output"

    with pytest.raises(RUNNER.WaveFailure, match="frozen archive GCP selector differs"):
        _run_selector(tmp_path, repo, frozen_product, source_sha, source_tree, output)

    assert not output.exists()


def test_package_selector_refuses_wrong_expected_commit(tmp_path: Path) -> None:
    repo, _, source_sha, _ = _fixture_repository(tmp_path)
    output = tmp_path / "wrong-expected-output"
    output.mkdir()
    env = os.environ.copy()
    env.update(
        OUT_DIR=str(output),
        UPLOAD="0",
        PYTHON_BIN=sys.executable,
        EXPECTED_SOURCE_SHA="0" * 40,
    )
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603 - invokes the selected test script with fixed argv.
        [
            str(Path(bash).resolve(strict=True)),
            str(repo / "policy-engine/ops/cloud/gcp/package_repo.sh"),
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode != 0
    assert "HEAD differs from expected frozen source commit" in result.stderr
    assert source_sha not in result.stdout
    assert not list(output.glob("policy-engine-*.tar.gz"))
