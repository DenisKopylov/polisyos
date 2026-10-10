from __future__ import annotations

import pytest

from polisyos.foundry.runtime.nan_guard import NaNDiagnostic, NaNGuardReport


class TestNaNDiagnostic:
    def test_nan_diagnostic_model_validation(self) -> None:
        diag = NaNDiagnostic(
            slot_id="income",
            mechanism_id="flat_tax",
            time_step=5,
            nan_count=3,
            inf_count=0,
            sample_indices=[0, 1, 2],
            possible_cause="division_by_zero",
        )
        assert diag.slot_id == "income"
        assert diag.mechanism_id == "flat_tax"
        assert diag.time_step == 5
        assert diag.nan_count == 3
        assert diag.inf_count == 0

    def test_nan_diagnostic_rejects_negative_step(self) -> None:
        with pytest.raises(Exception):
            NaNDiagnostic(
                slot_id="x",
                mechanism_id="m",
                time_step=-1,
                nan_count=0,
                inf_count=0,
                possible_cause="test",
            )


class TestNaNGuardReport:
    def test_nan_guard_report_ok_when_no_diagnostics(self) -> None:
        report = NaNGuardReport(ok=True, checks_performed=10)
        assert report.ok is True
        assert report.diagnostics == []
        assert report.first_failure_step is None

    def test_nan_guard_report_to_artifact_format(self) -> None:
        diag = NaNDiagnostic(
            slot_id="income",
            mechanism_id="tax",
            time_step=3,
            nan_count=2,
            inf_count=0,
            sample_indices=[0, 5],
            possible_cause="overflow",
        )
        report = NaNGuardReport(
            ok=False,
            checks_performed=5,
            first_failure_step=3,
            diagnostics=[diag],
        )
        artifact = report.to_artifact()
        assert artifact["ok"] is False
        assert artifact["checks_performed"] == 5
        assert artifact["first_failure_step"] == 3
        assert len(artifact["diagnostics"]) == 1
        assert artifact["diagnostics"][0]["slot_id"] == "income"

    def test_nan_guard_report_first_failure_step_set(self) -> None:
        report = NaNGuardReport(
            ok=False,
            checks_performed=10,
            first_failure_step=7,
            diagnostics=[
                NaNDiagnostic(
                    slot_id="s",
                    mechanism_id="m",
                    time_step=7,
                    nan_count=1,
                    inf_count=0,
                    possible_cause="numerical_instability",
                ),
            ],
        )
        assert report.first_failure_step == 7
