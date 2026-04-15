from __future__ import annotations

import ast
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

from tools._lib.imports import ensure_repo_import_roots, is_type_checking_test
from tools.ops.migrations import migrate
from tools.ops.ukraine_data import pre_shard_lex_corpus
from tools.quality.ci import check_action_freshness
from tools.quality.diagnostics.check_perf_regression import load_pytest_benchmark


def test_perf_regression_rejects_non_finite_stats(tmp_path: Path) -> None:
    payload = tmp_path / "bench.json"
    payload.write_text(
        '{"benchmarks":[{"name":"case","stats":{"mean":NaN,"stddev":0,"min":0,"max":1,"rounds":1}}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-finite"):
        load_pytest_benchmark(payload)


def test_shard_writer_cleanup_unlinks_unpublished_temp_file(tmp_path: Path) -> None:
    writers = pre_shard_lex_corpus._open_writers(tmp_path, shard_count=1, compression_level=1)
    writer = writers[("current", 0)]
    temp_path = writer.temp_path
    final_path = writer.path

    writer.close(publish=False)
    writer.close(publish=False)

    assert not temp_path.exists()
    assert not final_path.exists()


def test_action_freshness_reports_degraded_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args, **_kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(check_action_freshness, "fetch_json", _raise)

    result = check_action_freshness.fetch_latest_tag("actions/checkout")

    assert result.tag is None
    assert result.degraded_reason is not None
    assert "GitHub lookup degraded" in result.degraded_reason


def test_run_manifest_migration_writes_relative_paths_atomically(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "run" / "manifests"
    artifact_path = tmp_path / "run" / "artifacts" / "result.json"
    manifest_dir.mkdir(parents=True)
    artifact_path.parent.mkdir(parents=True)
    source = manifest_dir / "run.json"
    target = tmp_path / "migrated.json"
    source.write_text(
        f'{{"artifacts":[{{"path":"{artifact_path}"}}]}}',
        encoding="utf-8",
    )

    assert migrate.main(["run_manifest", str(source), str(target)]) == 0
    migrated = target.read_text(encoding="utf-8")

    assert '"relative_path": "artifacts/result.json"' in migrated
    assert '"run_root":' in migrated


def test_shared_import_helpers_cover_bootstrap_and_type_checking() -> None:
    repo_root, src_root = ensure_repo_import_roots(
        Path(__file__).resolve().parents[2] / "tools" / "diagnostics" / "check_setup.py",
        include_repo_root=True,
        include_src_root=True,
    )

    assert repo_root.name == "policy-engine"
    assert src_root == repo_root / "src"
    assert is_type_checking_test(ast.parse("if TYPE_CHECKING:\n    pass\n").body[0].test)
    assert is_type_checking_test(ast.parse("if typing.TYPE_CHECKING:\n    pass\n").body[0].test)


def test_runtime_archive_tool_runs_as_module() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "-m", "tools.runtime.archive_legacy_runs", "--help"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Archive legacy runs directory" in result.stdout
