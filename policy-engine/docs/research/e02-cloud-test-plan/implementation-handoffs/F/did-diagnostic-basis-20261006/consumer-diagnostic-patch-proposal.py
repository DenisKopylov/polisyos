"""Portable root-owned consumer patch: proposed body extension, not repository mutation."""
from typing import Any
from polisyos.foundry.methods.catalog.causal.did import StaggeredDifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.causal import CausalEffectReport,EstimationStatus


def verify_selected_did_diagnostics(output: Any, *, observational_data: PanelObservationalData) -> None:
    """Recompute all diagnostic inputs and compare the complete typed projection."""
    if not isinstance(output,dict) or 'report' not in output:
        raise ValueError('selected DiD output is missing its report')
    report=CausalEffectReport.model_validate(output['report'])
    # Existing target helper is SUCCESS-only. Producer also emits genuine diagnostic
    # contracts for degenerate influence ASSUMPTION_FAILED; verify those when present.
    # INPUT_INVALID reports that never computed diagnostics must remain invalid.
    if report.status is not EstimationStatus.SUCCESS and not report.diagnostics:
        return
    expected=StaggeredDifferenceInDifferences._diagnostic_contract(observational_data)
    if any(report.method_params.get(key)!=value for key,value in expected.items()):
        raise ValueError('selected DiD diagnostic basis/result does not bind current panel')
    if [d.model_dump(mode='json') for d in report.diagnostics]!=expected['diagnostic_contract']['diagnostics']:
        raise ValueError('selected DiD diagnostics do not project the current panel')
