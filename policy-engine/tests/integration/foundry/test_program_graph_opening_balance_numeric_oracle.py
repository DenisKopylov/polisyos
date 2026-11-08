"""Numerical oracle for an actual bound input consumed by selected Foundry."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.execute import admit_execution_source
from polisyos.foundry.execute.executor import load_state_snapshot
from tests._helpers.program_graph_tax_subsidy_input import (
    INCOME_VALUES,
    SUBSIDY_RATE,
    execute_program_graph_tax_subsidy_input_case,
    prepare_program_graph_tax_subsidy_input_case,
)


@pytest.mark.integration
def test_selected_program_graph_consumes_persisted_opening_balance(
    tmp_path: Path,
) -> None:
    """A public Foundry execution must consume the bound stock, not an empty default."""
    expected_subsidy = sum(INCOME_VALUES) * SUBSIDY_RATE
    assert expected_subsidy == 37.5

    for opening_balance, expected_final in ((1000, 962.5), (2000, 1962.5)):
        case = prepare_program_graph_tax_subsidy_input_case(
            tmp_path / str(int(opening_balance)),
            opening_balance_usd=opening_balance,
        )
        try:
            execution = execute_program_graph_tax_subsidy_input_case(case)
            reader = FileSystemCAS(case.store_root)
            admission = admit_execution_source(reader, execution.simulation_result_ref)
            assert admission.mode == "single_step_basis"
            assert admission.basis is not None
            assert admission.basis_ref is not None
            assert admission.simulation_result.execution_source_status == "single_step_basis"
            assert admission.simulation_result.execution_input_basis_ref == admission.basis_ref
            assert admission.basis.exec_plan_ref == case.exec_plan_ref
            assert admission.basis.program_graph_ref == case.program_graph_ref
            assert admission.basis.input_bindings_ref == case.input_bindings_ref
            assert admission.basis.bound_state_snapshot_ref == case.bound_state_snapshot_ref
            assert admission.basis.base_state_snapshot_ref == case.bound_state_snapshot_ref
            assert admission.basis.effective_step == 0
            assert admission.simulation_result.state_snapshot_ref is not None

            source = json.loads(reader.get_bytes(case.source_ref))
            assert source == {
                "agents": {"income": list(INCOME_VALUES)},
                "government_balance": opening_balance,
            }
            initial_state = load_state_snapshot(
                reader,
                snapshot_ref=case.bound_state_snapshot_ref,
            )
            final_state = load_state_snapshot(
                reader,
                snapshot_ref=admission.simulation_result.state_snapshot_ref,
            )
            np.testing.assert_allclose(
                np.asarray(initial_state.agents.income),
                np.asarray(INCOME_VALUES),
                rtol=0.0,
                atol=1e-6,
            )
            assert float(np.asarray(initial_state.government_balance).item()) == pytest.approx(
                opening_balance,
                rel=0.0,
                abs=1e-6,
            )
            np.testing.assert_allclose(
                np.asarray(final_state.agents.income),
                np.asarray((112.5, 225.0)),
                rtol=0.0,
                atol=1e-5,
            )
            assert float(np.asarray(final_state.government_balance).item()) == pytest.approx(
                opening_balance - expected_subsidy,
                rel=0.0,
                abs=1e-5,
            )
            assert float(np.asarray(final_state.government_balance).item()) == pytest.approx(
                expected_final,
                rel=0.0,
                abs=1e-5,
            )
        finally:
            case.close()
