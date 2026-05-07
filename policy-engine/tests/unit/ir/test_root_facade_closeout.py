from __future__ import annotations

from pathlib import Path


def test_ir_root_contains_only_facade_python_files() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    ir_root = repo_root / "src" / "polisyos" / "ir"
    allowed = {"__init__.py", "api.py", "_api.py"}

    root_python_files = sorted(path.name for path in ir_root.glob("*.py"))

    assert root_python_files
    assert set(root_python_files) <= allowed
    assert root_python_files == sorted(name for name in root_python_files if name in allowed)


def test_legacy_ir_public_module_shims_resolve_to_canonical_packages() -> None:
    from polisyos.ir.citations import CitationRef
    from polisyos.ir.references import ArtifactRefModel as CanonicalArtifactRefModel
    from polisyos.ir.references import CitationRef as CanonicalCitationRef
    from polisyos.ir.refs import ArtifactRefModel
    from polisyos.ir.schema_catalog import get_ir_type
    from polisyos.ir.schemas import get_ir_type as canonical_get_ir_type

    assert CitationRef is CanonicalCitationRef
    assert ArtifactRefModel is CanonicalArtifactRefModel
    assert get_ir_type is canonical_get_ir_type
