from __future__ import annotations

from pathlib import Path


def test_pyproject_has_no_legacy_method_or_connector_entrypoint_groups() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

    assert '[project.entry-points."polisyos.methods"]' not in pyproject
    assert '[project.entry-points."polisyos.connectors"]' not in pyproject
