from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "tools" / "quality" / "validation"
EMPTY_NAMESPACE_GATE_SCRIPT = VALIDATION_DIR / "empty_namespace_gate.py"


def _load_empty_namespace_gate() -> ModuleType:
    sys.path.insert(0, str(VALIDATION_DIR))
    spec = importlib.util.spec_from_file_location(
        "empty_namespace_gate", EMPTY_NAMESPACE_GATE_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase1a_current_foundry_method_import_inventory_has_no_deep_imports() -> None:
    gate = _load_empty_namespace_gate()

    importers = gate.collect_foundry_methods_external_importers(REPO_ROOT)

    assert importers
    assert {item["kind"] for item in importers} == {"facade"}
    assert gate._deep_import_findings(importers) == []


def test_phase1a_empty_namespace_gate_fails_for_deep_domain_import(tmp_path: Path) -> None:
    gate = _load_empty_namespace_gate()
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "probe.py").write_text(
        "from polisyos.foundry.methods.causal.synthetic_control import SyntheticControlMethod\n",
        encoding="utf-8",
    )

    importers = gate.collect_foundry_methods_external_importers(tmp_path)
    findings = gate._deep_import_findings(importers)

    assert [item["kind"] for item in importers] == ["deep"]
    assert findings
    assert findings[0]["module"] == "polisyos.foundry.methods.causal.synthetic_control"
