from __future__ import annotations

import ast
from pathlib import Path

import pytest

from polisyos.foundry.methods.catalog.simulation.dynamics import (
    _abm_result_stub,
    build_content_bound_abm_result,
)
from polisyos.ir.analytics.phase4_dynamics import verify_strangle_receipt


def test_abm_stub_is_fixture_only_and_default_path_is_content_bound() -> None:
    payload = {
        "trajectory": [{"step": 0, "final_queue_length": 1.0}],
        "metrics": {"completed_count": 2},
    }
    diagnostics = {"warnings": [], "engine": "simulation.coupled_policy.des_abm"}

    with pytest.raises(RuntimeError, match="abm_result_stub_strangled"):
        _abm_result_stub(method_id="simulation.coupled_policy.des_abm", horizon=3)
    fixture = _abm_result_stub(
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        fixture_only=True,
    )
    assert "phase4_abm_result_stub" in fixture.model_dump_json()

    first = build_content_bound_abm_result(
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        payload=payload,
        diagnostics=diagnostics,
    )
    second = build_content_bound_abm_result(
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        payload=payload,
        diagnostics=diagnostics,
    )

    assert first == second
    assert first.identifiability_certificate is not None
    assert first.identifiability_certificate.status == "diagnostic_attached"
    assert first.notes
    assert "phase4_abm_result_stub" not in first.model_dump_json()
    receipt_note = next(note for note in first.notes if note.startswith("strangle_receipt:"))
    receipt = receipt_note.removeprefix("strangle_receipt:")
    verify_strangle_receipt(
        receipt,
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        payload=payload,
        diagnostics=diagnostics,
    )


def test_production_simulation_modules_have_zero_abm_stub_callers() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    relative_paths = (
        Path("src/polisyos/foundry/methods/catalog/simulation/dynamics.py"),
        Path("src/polisyos/foundry/methods/catalog/simulation/coupled.py"),
    )

    callers: list[str] = []
    for relative_path in relative_paths:
        module = ast.parse((repo_root / relative_path).read_text(encoding="utf-8"))
        callers.extend(
            f"{relative_path}:{node.lineno}"
            for node in ast.walk(module)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_abm_result_stub"
        )

    assert callers == []
