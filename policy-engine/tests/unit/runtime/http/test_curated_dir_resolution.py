from __future__ import annotations

import json
from pathlib import Path

from polisyos.runtime.http.services.control.artifacts import _resolve_curated_dir


def test_resolve_curated_dir_honors_explicit_env(
    monkeypatch,
    tmp_path: Path,
) -> None:
    configured = tmp_path / "custom-curated"
    monkeypatch.setenv("POLISYOS_CURATED_DIR", str(configured))

    assert _resolve_curated_dir() == configured


def test_resolve_curated_dir_discovers_production_data_canonical_curated(
    monkeypatch,
    tmp_path: Path,
) -> None:
    curated = (
        tmp_path
        / "production_data"
        / "canonical"
        / "local_data_20260501"
        / "policy_engine_data"
        / "curated"
    )
    curated.mkdir(parents=True)
    (curated / "data_contracts.json").write_text('{"contracts": []}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POLISYOS_CURATED_DIR", raising=False)
    monkeypatch.delenv("POLISYOS_FABRIC_CURATED_DIR", raising=False)

    assert (tmp_path / _resolve_curated_dir()).resolve() == curated.resolve()


def test_resolve_curated_dir_prefers_catalog_bearing_dir_over_empty_legacy_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    legacy = tmp_path / "data" / "curated"
    legacy.mkdir(parents=True)
    curated = (
        tmp_path
        / "production_data"
        / "canonical"
        / "local_data_20260501"
        / "policy_engine_data"
        / "curated"
    )
    curated.mkdir(parents=True)
    (curated / "source_bindings.json").write_text('{"bindings": []}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POLISYOS_CURATED_DIR", raising=False)
    monkeypatch.delenv("POLISYOS_FABRIC_CURATED_DIR", raising=False)

    assert (tmp_path / _resolve_curated_dir()).resolve() == curated.resolve()


def test_resolve_curated_dir_uses_production_data_manifest_role(
    monkeypatch,
    tmp_path: Path,
) -> None:
    curated = (
        tmp_path
        / "production_data"
        / "canonical"
        / "local_data_20990101"
        / "policy_engine_data"
        / "curated"
    )
    curated.mkdir(parents=True)
    (curated / "data_contracts.json").write_text('{"contracts": []}', encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "bundles": {
            "curated": {
                "role": "fabric_curated_catalog",
                "version_id": "local_data_20990101",
                "path": "canonical/local_data_20990101/policy_engine_data/curated",
            }
        },
    }
    (tmp_path / "production_data" / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POLISYOS_CURATED_DIR", raising=False)
    monkeypatch.delenv("POLISYOS_FABRIC_CURATED_DIR", raising=False)

    assert (tmp_path / _resolve_curated_dir()).resolve() == curated.resolve()
