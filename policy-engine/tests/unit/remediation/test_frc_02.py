"""Test-first witness for FRC-02 backtest reference transport.

The plan already owns model and policy specification references.  This slice
proves that the existing orchestrator and matrix persistence paths must carry
those references into the persisted ``BacktestReport`` without changing its
public DTO.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
from polisyos.ir.registry.refs import BacktestReportRef
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixRunner
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource


def _persist_spec_ref(store: FileSystemCAS, *, spec_kind: str) -> str:
    ref = store.put_json(
        {"spec_id": f"frc-02-{spec_kind}", "source": "test_frc_02"},
        PutOptions(
            kind=f"test.frc02.{spec_kind}_spec",
            media_type="application/json",
        ),
    )
    return str(ref.artifact_id)


def _plan(
    tmp_path: Path,
    *,
    model_spec_ref: str,
    policy_spec_ref: str,
) -> HistoricalValidationPlan:
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps({"metric": [1.0, 1.05, 1.1, 1.15]}),
        encoding="utf-8",
    )
    return HistoricalValidationPlan(
        plan_id="frc-02-ref-transport",
        plan_label="FRC-02 reference transport",
        historical_data_path=str(history_path),
        intervention_step=2,
        ground_truth_outcomes={"metric": [1.1, 1.15]},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [1.08, 1.13]},
        model_spec_ref=model_spec_ref,
        policy_spec_ref=policy_spec_ref,
    )


@pytest.mark.parametrize(
    "runner_name",
    ("orchestrator", "matrix"),
    ids=("orchestrator", "matrix"),
)
def test_plan_model_policy_refs_survive_orchestrator_and_matrix_persisted_report_roundtrip(
    runner_name: str,
    tmp_path: Path,
) -> None:
    """Persisted reports retain both refs supplied by their validation plan."""

    store = FileSystemCAS(tmp_path / f"{runner_name}-cas")
    model_spec_ref = _persist_spec_ref(store, spec_kind="model")
    policy_spec_ref = _persist_spec_ref(store, spec_kind="policy")
    plan = _plan(
        tmp_path,
        model_spec_ref=model_spec_ref,
        policy_spec_ref=policy_spec_ref,
    )

    if runner_name == "orchestrator":
        report = BacktestOrchestrator(cas=store).run([plan])
        assert report.cas_artifact_id is not None
        report_ref = BacktestReportRef.model_validate(
            {"artifact_id": report.cas_artifact_id}
        )
    else:
        bundle = BacktestPlanBundle(
            contract_target=ContractCompatibilityTarget(
                contract_id="frc02_ref_transport",
                contract_fqn="polisyos.tests.FRC02ReferenceTransport",
            ),
            required_fields=["metric"],
            plans=[plan.model_dump(mode="json")],
            historical_payloads={"household": {"metric": [1.0, 1.05, 1.1, 1.15]}},
        )
        result = BacktestMatrixRunner(store).run({BacktestKind.HOUSEHOLD: bundle})
        assert result.backtest_report_ref is not None
        report_ref = result.backtest_report_ref

    persisted = load_backtest_report(store, report_ref)

    assert persisted.model_spec_ref == model_spec_ref
    assert persisted.policy_spec_ref == policy_spec_ref
