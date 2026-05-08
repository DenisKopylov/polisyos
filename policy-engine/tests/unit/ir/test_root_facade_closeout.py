from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path

import pytest


def test_ir_root_contains_only_facade_python_files() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    ir_root = repo_root / "src" / "polisyos" / "ir"
    allowed = {"__init__.py", "api.py", "_api.py"}

    root_python_files = sorted(path.name for path in ir_root.glob("*.py"))

    assert root_python_files
    assert set(root_python_files) <= allowed
    assert root_python_files == sorted(name for name in root_python_files if name in allowed)


def test_legacy_ir_public_module_shims_resolve_to_canonical_packages() -> None:
    from polisyos.ir.loading.citations import CitationRef as CanonicalCitationRef
    from polisyos.ir.registry.refs import ArtifactRefModel as CanonicalArtifactRefModel
    from polisyos.ir.schemas import get_ir_type as canonical_get_ir_type

    legacy_citations = _import_legacy_ir_module_with_warning("polisyos.ir.citations")
    legacy_references = _import_legacy_ir_module_with_warning("polisyos.ir.references")
    nested_legacy_references = _import_legacy_ir_module_with_warning(
        "polisyos.ir.references.refs"
    )
    legacy_refs = _import_legacy_ir_module_with_warning("polisyos.ir.refs")
    legacy_schema_catalog = _import_legacy_ir_module_with_warning("polisyos.ir.schema_catalog")

    CitationRef = legacy_citations.CitationRef
    LegacyReferencesCitationRef = legacy_references.CitationRef
    LegacyReferencesArtifactRefModel = legacy_references.ArtifactRefModel
    NestedLegacyArtifactRefModel = nested_legacy_references.ArtifactRefModel
    ArtifactRefModel = legacy_refs.ArtifactRefModel
    get_ir_type = legacy_schema_catalog.get_ir_type

    assert CitationRef is CanonicalCitationRef
    assert LegacyReferencesCitationRef is CanonicalCitationRef
    assert LegacyReferencesArtifactRefModel is CanonicalArtifactRefModel
    assert NestedLegacyArtifactRefModel is CanonicalArtifactRefModel
    assert ArtifactRefModel is CanonicalArtifactRefModel
    assert get_ir_type is canonical_get_ir_type


def test_ir_refs_and_references_no_longer_collide_as_sibling_implementations() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    ir_root = repo_root / "src" / "polisyos" / "ir"

    assert not (ir_root / "refs").exists()
    assert not (ir_root / "references").exists()
    assert (ir_root / "registry" / "refs.py").is_file()
    assert not (ir_root / "registry" / "references.py").exists()
    assert (ir_root / "loading" / "citations.py").is_file()

    package_contract = tomllib.loads(
        (repo_root / "architecture" / "packages" / "ir.toml").read_text(encoding="utf-8")
    )

    assert {
        entry.get("name") for entry in package_contract.get("allowed_name_collision", [])
    }.isdisjoint({"refs-vs-references", "refs/references", "refs"})


def test_ir_phase_0_3_import_map_declares_shell_group_targets() -> None:
    expected_targets = {
        "polisyos.ir._internal": "polisyos.ir._internal",
        "polisyos.ir._lazy_facade": "polisyos.ir.api",
        "polisyos.ir.canon": "polisyos.ir.model_layer.canon",
        "polisyos.ir.citations": "polisyos.ir.loading.citations",
        "polisyos.ir.connectors": "polisyos.ir.connectors",
        "polisyos.ir.fact_log": "polisyos.ir.loading.fact_log",
        "polisyos.ir.loaders": "polisyos.ir.loading.loaders",
        "polisyos.ir.migration_report": "polisyos.ir.loading.migration_report",
        "polisyos.ir.model_spec": "polisyos.ir.model_layer.model_spec",
        "polisyos.ir.norm_pack": "polisyos.ir.loading.norm_pack",
        "polisyos.ir.portfolio": "polisyos.ir.loading.portfolio",
        "polisyos.ir.predicate": "polisyos.ir.model_layer.predicate",
        "polisyos.ir.public_surface": "polisyos.ir.registry.public_surface",
        "polisyos.ir.queries": "polisyos.ir.model_layer.queries",
        "polisyos.ir.references": "polisyos.ir.api",
        "polisyos.ir.refs": "polisyos.ir.registry.refs",
        "polisyos.ir.registry_fragments": "polisyos.ir.registry.registry_fragments",
        "polisyos.ir.schema_catalog": "polisyos.ir.loading.schema_catalog",
        "polisyos.ir.schemas": "polisyos.ir.schemas.catalog",
        "polisyos.ir.trinity": "polisyos.ir.trinity",
        "polisyos.ir.types": "polisyos.ir.model_layer.types",
        "polisyos.ir.units": "polisyos.ir.model_layer.units",
    }
    repo_root = Path(__file__).resolve().parents[3]
    payload = tomllib.loads((repo_root / "architecture/shims.toml").read_text(encoding="utf-8"))
    planned = {entry["source_fqn"]: entry for entry in payload["planned_source_move"]}

    for source_fqn, target_fqn in expected_targets.items():
        entry = planned[source_fqn]

        assert entry["target_fqn"] == target_fqn
        assert entry["owner"] == "team-ir"
        assert entry["sunset"] == "2026-12-31"
        assert entry["test"].endswith("test_ir_phase_0_3_import_map_declares_shell_group_targets")


def test_ir_phase_5_3_import_map_has_explicit_compatibility_behavior() -> None:
    supported_decisions = {
        "moved_with_reexport_shim",
        "retained_with_dated_exception",
        "removed_with_documented_release_note",
    }
    repo_root = Path(__file__).resolve().parents[3]
    payload = tomllib.loads((repo_root / "architecture/shims.toml").read_text(encoding="utf-8"))
    planned = [
        entry
        for entry in payload["planned_source_move"]
        if entry["owner"] == "team-ir" and entry["wave"] == "3.2"
    ]

    assert planned
    for entry in planned:
        assert entry["decision"] in supported_decisions
        assert entry["release_note"].startswith("docs/archive/reports/")
        assert entry["sunset"] == "2026-12-31"
        if entry["decision"] == "removed_with_documented_release_note":
            assert entry.get("removal_release")
        else:
            assert entry["target_fqn"]


def test_ir_package_contract_covers_live_first_level_roots() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    ir_root = repo_root / "src" / "polisyos" / "ir"
    package_contract = tomllib.loads(
        (repo_root / "architecture" / "packages" / "ir.toml").read_text(encoding="utf-8")
    )
    declared_roots = {
        Path(entry).name for entry in package_contract["layout"]["implementation_roots"]
    }
    live_roots = {
        path.name
        for path in ir_root.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }

    assert live_roots <= declared_roots


def _import_legacy_ir_module_with_warning(module_name: str) -> object:
    _drop_module(module_name)
    importlib.import_module("polisyos.ir")
    with pytest.warns(DeprecationWarning, match=module_name):
        return importlib.import_module(module_name)


def _drop_module(module_name: str) -> None:
    for loaded_name in list(sys.modules):
        if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
            sys.modules.pop(loaded_name, None)
