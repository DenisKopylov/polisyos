from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

import pytest

from tools.devx.architecture import guardrails

REPO_ROOT = Path(__file__).resolve().parents[3]


def _inventory() -> list[guardrails.PackageInventory]:
    policies = guardrails._parse_public_surface(
        REPO_ROOT / "architecture/public_surface/contract.toml"
    )
    return guardrails.build_public_surface_inventory(policies)


def test_public_surface_inventory_enumerates_every_supported_entrypoint_facade() -> None:
    manifest = tomllib.loads(
        (REPO_ROOT / "architecture/public_surface/contract.toml").read_text(
            encoding="utf-8"
        )
    )
    expected = {
        entrypoint
        for package in manifest["package"]
        for entrypoint in package["supported_entrypoints"]
    }
    observed = {
        entrypoint.module for package in _inventory() for entrypoint in package.entrypoints
    }

    assert observed == expected


def test_supported_entrypoint_inventory_resolves_module_and_package_facades() -> None:
    entrypoints = {
        entrypoint.module: entrypoint
        for package in _inventory()
        for entrypoint in package.entrypoints
    }

    for module in ("polisyos.ir.api", "polisyos.fabric.api", "polisyos.foundry.api"):
        assert entrypoints[module].source_file == f"src/{module.replace('.', '/')}.py"
    for module in (
        "polisyos.foundry.compile",
        "polisyos.foundry.execute",
        "polisyos.runtime.quality",
        "polisyos.data_forge.read_api",
        "polisyos.scientist.methods.research_dag",
    ):
        assert entrypoints[module].source_file == (
            f"src/{module.replace('.', '/')}/__init__.py"
        )


def test_foundry_public_surface_exposes_only_embedding_contract_from_backends() -> None:
    foundry = next(package for package in _inventory() if package.module == "polisyos.foundry")
    root_exports = set(foundry.exports)
    internal_backend_exports = set(
        guardrails._entrypoint_inventory("polisyos.foundry.methods.backends").exports
    )
    embedding_exports = {
        "EmbedderProtocol",
        "SentenceTransformerEmbedder",
        "TFIDFEmbedder",
    }

    assert "polisyos.foundry.methods.backends" not in foundry.supported_entrypoints
    assert embedding_exports <= root_exports
    assert root_exports.isdisjoint(internal_backend_exports)


def test_supported_entrypoint_inventory_rejects_missing_or_ambiguous_facade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "src"
    monkeypatch.setattr(guardrails, "SRC_ROOT", source_root)
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)

    with pytest.raises(FileNotFoundError, match=r"polisyos\.fixture.*found 0"):
        guardrails._facade_source_for("polisyos.fixture")

    module_path = source_root / "polisyos" / "fixture.py"
    package_path = source_root / "polisyos" / "fixture" / "__init__.py"
    module_path.parent.mkdir(parents=True)
    package_path.parent.mkdir(parents=True)
    module_path.write_text('__all__ = ["module_arm"]\n', encoding="utf-8")
    package_path.write_text('__all__ = ["package_arm"]\n', encoding="utf-8")

    with pytest.raises(FileNotFoundError, match=r"polisyos\.fixture.*found 2"):
        guardrails._facade_source_for("polisyos.fixture")


def test_runtime_quality_inventory_contains_human_decision_record() -> None:
    entrypoint = next(
        entrypoint
        for package in _inventory()
        for entrypoint in package.entrypoints
        if entrypoint.module == "polisyos.runtime.quality"
    )

    assert entrypoint.source_file == "src/polisyos/runtime/quality/__init__.py"
    assert "HumanDecisionRecord" in entrypoint.exports


def test_public_surface_inventory_corrupt_supported_entrypoint_fails_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "src"
    package_root = source_root / "polisyos" / "fixture"
    package_root.mkdir(parents=True)
    facade = package_root / "__init__.py"
    facade.write_text(
        '"""Fixture facade."""\n__all__ = ["HumanDecisionRecord"]\n',
        encoding="utf-8",
    )
    (package_root / "README.md").write_text(
        "Last updated: 2026-08-24\n\n## Where to Start\n",
        encoding="utf-8",
    )
    reference_doc = tmp_path / "docs" / "reference.md"
    reference_doc.parent.mkdir(parents=True)
    reference_doc.write_text("fixture\n", encoding="utf-8")
    manifest = tmp_path / "public.toml"
    manifest.write_text(
        "\n".join(
            (
                "[[package]]",
                'module = "polisyos.fixture"',
                'classification = "public_experimental"',
                'facade_mode = "eager_exports"',
                'owner = "test-owner"',
                'readme = "src/polisyos/fixture/README.md"',
                'reference_doc = "docs/reference.md"',
                'supported_entrypoints = ["polisyos.fixture"]',
                "major_subsystem = false",
                'notes = "fixture"',
                "",
            )
        ),
        encoding="utf-8",
    )
    generated_manifest = tmp_path / "generated.toml"
    generated_manifest.write_text("", encoding="utf-8")
    generated_md = tmp_path / "generated.md"
    generated_md.write_text(
        guardrails.render_generated_artifacts_markdown([]), encoding="utf-8"
    )
    exceptions = tmp_path / "exceptions.toml"
    exceptions.write_text("", encoding="utf-8")
    exception_registry = tmp_path / "exceptions.md"
    exception_registry.write_text("| id | state |\n| --- | --- |\n", encoding="utf-8")

    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(guardrails, "SRC_ROOT", source_root)
    monkeypatch.setattr(guardrails, "DEFAULT_MODULE_SIZE_BUDGET", tmp_path / "none.toml")
    monkeypatch.setattr(guardrails, "_check_workflow_toolchain_guardrails", lambda: [])
    policies = guardrails._parse_public_surface(manifest)
    initial = guardrails.build_public_surface_inventory(policies)
    public_json = tmp_path / "inventory.json"
    public_json.write_text(guardrails.render_public_surface_json(initial), encoding="utf-8")
    public_md = tmp_path / "public.md"
    public_md.write_text(guardrails.render_public_surface_markdown(initial), encoding="utf-8")
    deep_baseline = tmp_path / "deep.json"
    deep_baseline.write_text(
        guardrails.render_deep_import_baseline_json(
            guardrails.collect_deep_import_edges(policies)
        ),
        encoding="utf-8",
    )

    facade.write_text('"""Fixture facade."""\n__all__ = []\n', encoding="utf-8")
    args = argparse.Namespace(
        public_manifest=manifest,
        public_json=public_json,
        public_md=public_md,
        generated_manifest=generated_manifest,
        generated_md=generated_md,
        deep_import_baseline=deep_baseline,
        exceptions=exceptions,
        exceptions_registry=exception_registry,
        max_expiry_days=90,
        skip_generated_checks=True,
        all_generated_checks=False,
        generated_expected_root=tmp_path,
    )

    assert guardrails.run_check(args) == 1
    output = capsys.readouterr().out
    assert "Public surface inventory JSON drift detected" in output
    assert '"HumanDecisionRecord"' in output


def test_generated_inventory_serializes_each_resolved_facade() -> None:
    payload = json.loads(guardrails.render_public_surface_json(_inventory()))
    runtime_quality = next(
        row for row in payload["packages"] if row["module"] == "polisyos.runtime.quality"
    )

    assert runtime_quality["classification"] == "public_experimental"
    assert [row["module"] for row in runtime_quality["entrypoints"]] == [
        "polisyos.runtime.quality"
    ]
