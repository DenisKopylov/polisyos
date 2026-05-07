from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATION_SCRIPT = (
    REPO_ROOT / "tools" / "quality" / "validation" / "repository_structure_phase0.py"
)
CONCERN_CONTRACT = REPO_ROOT / "architecture" / "cross_cutting_concerns.toml"
NAME_REGISTRY = REPO_ROOT / "architecture" / "name_registry.toml"

PHASE_4_8_CONCERNS = {
    "observability",
    "security",
    "registry",
    "discovery",
    "governance",
    "contracts",
    "calibration",
    "runtime",
    "trace",
}


def _load_validation_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("repository_structure_phase0", VALIDATION_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _module_exists(module_name: str) -> bool:
    if not module_name:
        return True
    module_path = REPO_ROOT / "src" / Path(*module_name.split("."))
    return (
        module_path.with_suffix(".py").exists()
        or (module_path / "__init__.py").exists()
        or module_path.exists()
    )


def _concerns_by_name() -> dict[str, dict[str, Any]]:
    payload = _load_toml(CONCERN_CONTRACT)
    return {entry["name"]: entry for entry in payload.get("concern", [])}


def test_phase4_8_cross_cutting_contract_covers_required_concerns() -> None:
    payload = _load_toml(CONCERN_CONTRACT)
    concerns = _concerns_by_name()

    assert payload["cross_cutting_concerns"]["status"] == "contract_only"
    assert PHASE_4_8_CONCERNS <= set(concerns)


def test_phase4_8_concerns_have_owner_import_rule_visibility_and_axis() -> None:
    payload = _load_toml(CONCERN_CONTRACT)
    defaults = payload["defaults"]
    allowed_decisions = set(defaults["allowed_decisions"])
    required_fields = set(defaults["required_concern_fields"])

    for concern in payload.get("concern", []):
        missing = [
            field
            for field in sorted(required_fields)
            if concern.get(field) in (None, "", [])
        ]
        assert missing == [], f"{concern['name']} is missing {missing}"
        assert concern["decision"] in allowed_decisions
        assert concern["semantic_axis"] != "qualified imports required"
        assert concern["import_rule"] != "qualified imports required"


def test_phase4_8_global_concepts_have_one_canonical_interface_and_adapters() -> None:
    payload = _load_toml(CONCERN_CONTRACT)
    concerns = _concerns_by_name()

    for name in payload["defaults"]["global_concepts_requiring_adapters"]:
        concern = concerns[name]

        assert concern["decision"] == "canonical_interface_plus_package_adapters"
        assert concern["canonical_package"] == concern["canonical_interface"]
        assert _module_exists(concern["canonical_interface"])
        assert concern["allowed_adapters"]
        assert concern["unresolved_collisions"] == []

        adapter_modules = {adapter["module"] for adapter in concern["allowed_adapters"]}
        assert concern["canonical_interface"] not in adapter_modules
        for adapter in concern["allowed_adapters"]:
            assert adapter["sunset"] == "none"
            assert _module_exists(adapter["module"])


def test_phase4_8_concern_decisions_are_executable() -> None:
    for concern in _concerns_by_name().values():
        decision = concern["decision"]
        if decision == "canonical_interface_plus_package_adapters":
            assert concern["canonical_interface"]
            assert _module_exists(concern["canonical_interface"])
            assert concern["allowed_adapters"]
            for adapter in concern["allowed_adapters"]:
                assert _module_exists(adapter["module"])
        elif decision == "package_local_bounded_context":
            assert concern["allowed_contexts"]
            assert concern["canonical_interface"] == ""
            for context in concern["allowed_contexts"]:
                assert _module_exists(context["module"])
        elif decision == "rename_or_sunset":
            assert concern["canonical_interface"]
            assert concern["sunset"] != "none"
            assert concern["unresolved_collisions"]


def test_phase4_8_concerns_are_registered_or_backlogged_by_name_registry() -> None:
    registry = _load_toml(NAME_REGISTRY)
    shared = {entry["name"] for entry in registry.get("shared_name", [])}
    backlog = {entry["name"] for entry in registry.get("rename_backlog", [])}

    assert PHASE_4_8_CONCERNS <= shared | backlog
    for entry in registry.get("shared_name", []):
        assert entry["disambiguation"]


def test_phase4_8_no_unregistered_shared_package_names_remain() -> None:
    validation = _load_validation_module()

    findings = validation.collect_gate_findings(REPO_ROOT, "name_collision")

    assert findings == []
