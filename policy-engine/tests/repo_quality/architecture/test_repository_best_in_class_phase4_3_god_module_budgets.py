from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]

INITIAL_FOUNDRY_FOCUS = {
    "src/polisyos/foundry/methods/catalog/causal/causal_engine.py",
    "src/polisyos/foundry/methods/catalog/causal/interference.py",
    "src/polisyos/foundry/methods/catalog/causal/id_engine.py",
    "src/polisyos/foundry/methods/selection.py",
}

EXPECTED_COHESIVE_RESPONSIBILITIES = {
    "models/contracts",
    "validation",
    "graph transforms",
    "estimand compilation",
    "diagnostics",
    "execution adapters",
    "serialization",
}

ID_ENGINE_CHARACTERIZATION = (
    "tests/unit/foundry/methods/catalog/causal/test_id_engine_characterization.py"
)


def test_phase4_3_god_module_budgets_have_owner_ready_shrink_metadata() -> None:
    payload = _read_toml(REPO_ROOT / "architecture" / "module_size_budget.toml")
    header = payload["module_size_budget"]
    budgets = payload["budget"]
    budget_by_path = {budget["path"]: budget for budget in budgets}
    scoped_paths = set(budget_by_path)
    scoped_paths.update(str(budget.get("legacy_path", "")) for budget in budgets)

    assert header["phase_4_3_overlay"] == "characterization-tests-and-god-module-budgets"
    assert header["requires_current_lines"] is True
    assert header["requires_extraction_sequence"] is True
    assert header["requires_risk_notes"] is True
    assert INITIAL_FOUNDRY_FOCUS <= scoped_paths
    assert {"data_forge", "scientist", "runtime"} <= {budget["package"] for budget in budgets}

    for budget in budgets:
        path = REPO_ROOT / budget["path"]
        assert path.exists(), budget["path"]
        assert budget["owner"], budget["path"]
        assert budget["target_lines"] <= header["default_fail_closed_target_lines"], budget["path"]
        assert _count_lines(path) <= budget["current_lines"], budget["path"]
        assert budget["current_lines"] >= budget["target_lines"], budget["path"]
        assert budget["shrink_plan"].strip(), budget["path"]
        assert budget["risk_notes"].strip(), budget["path"]

        sequence = budget["extraction_sequence"]
        assert sequence, budget["path"]
        if budget["package"] == "tools-quality-validation":
            continue
        assert all(item in EXPECTED_COHESIVE_RESPONSIBILITIES for item in sequence), (
            budget["path"],
            sequence,
        )


def test_phase4_3_id_engine_has_characterization_tests_and_shrink_plan() -> None:
    payload = _read_toml(REPO_ROOT / "architecture" / "module_size_budget.toml")
    budget_by_path = {budget["path"]: budget for budget in payload["budget"]}
    id_engine = budget_by_path["src/polisyos/foundry/methods/catalog/causal/id_engine.py"]

    assert ID_ENGINE_CHARACTERIZATION in id_engine["characterization_tests"]
    assert (REPO_ROOT / ID_ENGINE_CHARACTERIZATION).exists()
    assert "status" in id_engine["shrink_plan"].lower()
    assert "proof" in id_engine["shrink_plan"].lower()
    assert id_engine["extraction_sequence"] == [
        "models/contracts",
        "validation",
        "graph transforms",
        "estimand compilation",
        "diagnostics",
        "execution adapters",
        "serialization",
    ]


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _count_lines(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _line in handle)
