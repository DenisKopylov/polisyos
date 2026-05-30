from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from tools.lib.fs import normalize_filesystem_path
from tools.lib.runner import parse_trusted_command
from tools.lib.sql import validate_sql_identifier
from tools.ops_runners.migrations import migrate_duckdb_to_pg
from tools.quality.diagnostics import scan_fabric

REPO_ROOT = Path(__file__).resolve().parents[3]

TARGET_SHELL_SCRIPTS = (
    REPO_ROOT / "tools" / "ops_runners" / "cloud" / "run_datasets_validation.sh",
    REPO_ROOT / "tools" / "ops_runners" / "cloud" / "check_progress.sh",
    REPO_ROOT / "tools" / "ops_runners" / "cloud" / "prepare_shards.sh",
    REPO_ROOT / "tools" / "quality" / "ci" / "install_actionlint.sh",
    REPO_ROOT / "tools" / "quality" / "ci" / "install_supply_chain_tools.sh",
    REPO_ROOT / "tools" / "ops_runners" / "cloud" / "run_pipeline.sh",
)


def test_validate_sql_identifier_rejects_malicious_values() -> None:
    with pytest.raises(ValueError):
        validate_sql_identifier("safe_name; DROP TABLE users")
    with pytest.raises(ValueError):
        validate_sql_identifier("CamelCase")
    with pytest.raises(ValueError):
        validate_sql_identifier("1leading_digit")


def test_parse_trusted_command_rejects_shell_control_tokens() -> None:
    with pytest.raises(ValueError):
        parse_trusted_command("uv run python tools/x.py; rm -rf /")
    with pytest.raises(ValueError):
        parse_trusted_command("uv run python tools/x.py && whoami")


def test_normalize_filesystem_path_rejects_nul_bytes() -> None:
    with pytest.raises(ValueError):
        normalize_filesystem_path("bad\x00path", kind="test path")


def test_scan_duckdb_skips_unsafe_table_identifiers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "example.duckdb"
    db_path.write_text("", encoding="utf-8")

    executed: list[str] = []

    class _Result:
        def __init__(self, rows: list[tuple[object, ...]]) -> None:
            self._rows = rows

        def fetchall(self) -> list[tuple[object, ...]]:
            return self._rows

    class _Connection:
        def execute(self, query: str) -> _Result:
            executed.append(query)
            if query == "SHOW TABLES":
                return _Result([("safe_table",), ("unsafe;drop",)])
            if query == "DESCRIBE safe_table":
                return _Result([("safe_column", "VARCHAR")])
            raise AssertionError(f"Unexpected query: {query}")

        def close(self) -> None:
            return None

    monkeypatch.setattr(scan_fabric.duckdb, "connect", lambda *_args, **_kwargs: _Connection())

    contracts = scan_fabric.scan_duckdb(db_path)

    assert len(contracts) == 1
    assert contracts[0]["source_table"] == "safe_table"
    assert all("unsafe;drop" not in query for query in executed)


def test_migrate_duckdb_to_pg_rejects_malicious_column_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "integration.duckdb"
    duckdb_path.write_text("", encoding="utf-8")

    class _Frame:
        def __init__(self) -> None:
            self.columns = ["safe_column", "bad;drop"]
            self.empty = False

        def __setitem__(self, key: str, _value: object) -> None:
            if key not in self.columns:
                self.columns.append(key)

        def __len__(self) -> int:
            return 1

    class _DuckResult:
        def fetchdf(self) -> _Frame:
            return _Frame()

    class _DuckConnection:
        def execute(self, query: str) -> _DuckResult:
            assert query.startswith("SELECT * FROM ")
            return _DuckResult()

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        migrate_duckdb_to_pg,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {
                "duckdb_path": str(duckdb_path),
                "pg_dsn": "postgresql://unused",
                "tenant_id": str(uuid.uuid4()),
                "batch_size": 100,
                "dry_run": True,
            },
        )(),
    )
    monkeypatch.setattr(
        migrate_duckdb_to_pg.duckdb, "connect", lambda *_args, **_kwargs: _DuckConnection()
    )

    with pytest.raises(ValueError, match="Unsafe column"):
        migrate_duckdb_to_pg.main()


def test_merge_shards_requires_confirmation_without_yes(tmp_path: Path) -> None:
    shard_a = tmp_path / "shard_a"
    shard_b = tmp_path / "shard_b"
    shard_a.mkdir()
    shard_b.mkdir()
    output_dir = tmp_path / "merged"

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "ops_runners" / "cloud" / "merge_shards.py"),
            str(shard_a),
            str(shard_b),
            "--output",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "refusing to overwrite merged output without --yes" in result.stderr


def test_run_pipeline_dry_run_resumes_existing_snapshot_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    topics_dir = data_root / "topics"
    snapshot_root = data_root / "output" / "policyos_snapshot_fixed-run"
    (repo_root / ".venv" / "bin").mkdir(parents=True)
    (repo_root / ".venv" / "bin" / "activate").write_text("", encoding="utf-8")
    (repo_root / ".env").write_text(
        "GONKA_API_KEY=test-key\nUNPAYWALL_EMAIL=test@example.com\n",
        encoding="utf-8",
    )
    topics_dir.mkdir(parents=True)
    (topics_dir / "relevant_topics_sample.csv").write_text(
        "topic_id,name\n1,Test topic\n", encoding="utf-8"
    )
    snapshot_root.mkdir(parents=True)

    env = os.environ | {
        "POLISYOS_REPO_ROOT": str(repo_root),
        "POLISYOS_DATA_ROOT": str(data_root),
    }
    result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "tools" / "ops_runners" / "cloud" / "run_pipeline.sh"),
            "--dry-run",
            "--run-id",
            "fixed-run",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Resume:      yes" in result.stdout
    assert str(snapshot_root) in result.stdout
    assert "--resume" in result.stdout


def test_prepare_shards_generates_templates_without_embedded_secrets(tmp_path: Path) -> None:
    topics_csv = tmp_path / "topics.csv"
    deploy_dir = tmp_path / "deploy"
    topics_csv.write_text(
        "topic_id,name\n1,Health\n2,Climate\n3,Transport\n4,Governance\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "tools" / "ops_runners" / "cloud" / "prepare_shards.sh"),
            str(topics_csv),
            "--deploy-dir",
            str(deploy_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert (deploy_dir / "topics_shard_1.csv").exists()
    env_template = (deploy_dir / ".env.server_1.example").read_text(encoding="utf-8")
    assert "GONKA_API_KEY=" in env_template
    assert "gp-" not in env_template
    assert "DEPLOYMENT_NOTES.txt" in result.stdout


def test_target_shell_scripts_are_hardened() -> None:
    for path in TARGET_SHELL_SCRIPTS:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash"), path
        assert "set -euo pipefail" in text, path
        assert "/opt/policyos" not in text, path


def test_no_shell_true_in_tools_tree() -> None:
    offenders: list[str] = []
    for path in (REPO_ROOT / "tools").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "shell=True" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_tool_directories_are_importable_packages() -> None:
    missing: list[str] = []
    for path in (REPO_ROOT / "tools").iterdir():
        if not path.is_dir() or path.name in {"__pycache__", "design"}:
            continue
        if not (path / "__init__.py").exists():
            missing.append(str(path.relative_to(REPO_ROOT)))
    assert missing == []


def test_unified_tools_entry_point_is_packaged() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'polisyos-tools = "tools.cli:main"' in pyproject
    assert "click>=8.1.7" in pyproject
    assert 'packages = ["src/polisyos", "tools"]' in pyproject


def test_required_tools_readmes_exist() -> None:
    missing = [
        path
        for path in (
            REPO_ROOT / "tools" / "ci" / "README.md",
            REPO_ROOT / "tools" / "ops_runners" / "cloud" / "README.md",
            REPO_ROOT / "tools" / "ops_runners" / "ukraine_data" / "README.md",
            REPO_ROOT / "tools" / "quality" / "validation" / "README.md",
            REPO_ROOT / "tools" / "ops_runners" / "calibration" / "README.md",
            REPO_ROOT / "tools" / "ops_runners" / "release" / "README.md",
        )
        if not path.exists()
    ]
    assert missing == []


def test_type_checking_ast_helper_is_shared() -> None:
    offenders: list[str] = []
    for path in (REPO_ROOT / "tools").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if path == REPO_ROOT / "tools" / "lib" / "imports.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "def is_type_checking_test" in text or "def _is_type_checking_test" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
