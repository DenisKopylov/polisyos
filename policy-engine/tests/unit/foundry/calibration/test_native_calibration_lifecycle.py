"""Native optimizer lifecycle, persisted split roles and OTel failure boundaries."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import jax.numpy as jnp
import numpy as np
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from polisyos.core.artifacts import FileSystemCAS
from polisyos.foundry.calibration import calibrator as owner
from polisyos.foundry.calibration.calibrator import Calibrator
from polisyos.foundry.calibration.execution_basis import read_calibration_report_source
from polisyos.ir.analytics.uncertainty import IntervalSemantics
from tests.unit.foundry.calibration.test_training_support import (
    _compile_observations,
    _tax_inputs,
)


def test_training_partition_roles_survive_actual_selected_report(tmp_path) -> None:
    """TRAIN and HOLDOUT retain their distinct roles through real CAS readback."""
    measured = _compile_observations([("fit", 1, 10.0), ("fit", 2, 30.0)])
    inputs = _tax_inputs(measured)
    store = FileSystemCAS(tmp_path / "calibration")
    report, selected = Calibrator(inputs).run_and_persist(store)
    restored = read_calibration_report_source(
        FileSystemCAS(tmp_path / "calibration"), ref=selected
    ).require_value()
    assert restored.model_dump(mode="json") == report.model_dump(mode="json")
    target_id = measured.targets[0].target_id
    fit = restored.execution_context["measurement_fit"][target_id]
    assert fit["role"] == "train"
    assert fit["effective_support_count"] == 1
    train = fit["evaluation_partitions"]["train"]
    holdout = fit["evaluation_partitions"]["holdout"]
    assert train["training_rows"] == 1 and train["contributes_to_training"]
    assert holdout["training_rows"] == 0 and not holdout["contributes_to_training"]
    assert train["observed_rows"] == holdout["observed_rows"] == 1
    prediction = restored.series_comparison[target_id].model[0]
    assert restored.total_loss == pytest.approx(((prediction - 10.0) / 10.0) ** 2)
    assert holdout["metrics"]["mse"] == pytest.approx((prediction - 30.0) ** 2)
    assert restored.series_comparison[target_id].real == [10.0, 30.0]
    assert restored.series_comparison[target_id].time == [
        float(date(2024, month, 1).toordinal()) for month in (1, 2)
    ]
    semantics = restored.execution_context["measurement_target_semantics"][target_id]
    assert semantics["declared_unit"] == "currency"
    assert semantics["unit_authority"] == "not_established"
    assert semantics["period_end"] == ["2024-01-01", "2024-02-01"]
    assert restored.uncertainties is not None
    assert restored.coordinate_projection is not None
    assert restored.coordinate_projection.coordinate_order == tuple(restored.uncertainties.params)
    assert restored.uncertainty_envelopes is not None
    envelope = restored.uncertainty_envelopes["tax.rate"]
    assert envelope.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
    assert envelope.confidence_level is None
    assert envelope.gate_eligible is False
    assert restored.execution_context["selection_reason"] == "single_run"


def test_native_two_starts_emit_distinct_finished_sdk_spans(monkeypatch) -> None:
    """Each genuine Optax restart owns a fresh SDK span and matching run index."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("native-calibration-lifecycle")
    monkeypatch.setattr(owner, "get_tracer", lambda: tracer)
    monkeypatch.setattr(owner, "is_hpc_observability_enabled", lambda: True)
    measured = _compile_observations([("fit", 1, 10.0)])
    report = Calibrator(_tax_inputs(measured, multi_start=2)).run()
    assert np.isfinite(report.total_loss)
    assert report.execution_context["selected_start_index"] in (0, 1)
    assert "Multi-start: selected run" in " ".join(report.diagnostics)
    spans = [span for span in exporter.get_finished_spans() if span.name == "calibration.run"]
    assert len(spans) == 2
    assert {span.attributes["calibration.start_index"] for span in spans} == {0, 1}
    assert len({span.context.span_id for span in spans}) == 2
    assert all(span.end_time is not None and span.end_time >= span.start_time for span in spans)
    assert all(span.attributes["calibration.total_steps"] == 1 for span in spans)
    assert all(span.attributes["calibration.convergence_reason"] == "max_steps" for span in spans)
    provider.shutdown()


class _BrokenExporter(SpanExporter):
    def export(self, spans):
        raise RuntimeError("controlled exporter failure")


class _FailingAuxiliary:
    component_name = "controlled_native_model_failure"

    def __init__(self, error):
        self.error = error

    def compute(self, *, traces):
        assert "government_balance" in traces
        raise self.error


class _LogDistanceAuxiliary:
    """A genuine differentiable diagnostic with a singular initial model point."""

    component_name = "log_distance_domain"

    def compute(self, *, traces):
        distance = traces["government_balance"] - jnp.asarray(9.9, dtype=jnp.float32)
        return jnp.sum(jnp.square(jnp.log(jnp.square(distance)))), {}


def test_native_invalid_start_cannot_hide_finite_independent_restart(tmp_path) -> None:
    """Nonfinite first-start diagnostics survive an actual useful sibling fit."""
    inputs = _tax_inputs(_compile_observations([("fit", 1, 10.0)]), multi_start=2)
    config = inputs.config.model_copy(
        update={
            "multi_start": inputs.config.multi_start.model_copy(update={"perturbation_scale": 1.0})
        }
    )
    inputs = replace(inputs, config=config, aux_loss_components=(_LogDistanceAuxiliary(),))
    root = tmp_path / "restart"
    report, ref = Calibrator(inputs).run_and_persist(FileSystemCAS(root))
    fresh = read_calibration_report_source(FileSystemCAS(root), ref=ref).require_value()
    assert np.isfinite(report.total_loss)
    attempts = fresh.execution_context["restart_diagnostics"]
    assert len(attempts) == 2
    assert attempts[0]["loss_status"] == "non_finite"
    assert attempts[0]["loss_history"][0] == "inf"
    assert attempts[0]["selected"] is False
    assert attempts[1]["loss_status"] == "finite"
    assert attempts[1]["selected"] is True
    assert fresh.execution_context["selected_start_index"] == 1
    assert fresh.loss_history == attempts[1]["loss_history"]
    assert fresh.grad_norm_history == attempts[1]["grad_norm_history"]
    assert fresh.total_loss == attempts[1]["final_loss"]
    assert fresh.model_dump(mode="json") == report.model_dump(mode="json")


def test_real_sdk_exporter_failure_cannot_replace_native_model_error(monkeypatch) -> None:
    """A real SDK processor fails while the real optimizer reports its primary error."""
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_BrokenExporter()))
    monkeypatch.setattr(owner, "get_tracer", lambda: provider.get_tracer("native-failure"))
    monkeypatch.setattr(owner, "is_hpc_observability_enabled", lambda: True)
    primary = RuntimeError("controlled native auxiliary model failure")
    inputs = _tax_inputs(_compile_observations([("fit", 1, 10.0)]), multi_start=2)
    inputs = replace(inputs, aux_loss_components=(_FailingAuxiliary(primary),))
    with pytest.raises(RuntimeError) as caught:
        Calibrator(inputs).run()
    assert caught.value is primary
    provider.shutdown()


def test_single_native_nonfinite_fit_refuses_with_inspectable_history() -> None:
    """The actual single caller passes finite admission and preserves failed evidence."""
    inputs = _tax_inputs(_compile_observations([("fit", 1, 10.0)]))
    inputs = replace(
        inputs,
        base_state=inputs.base_state.replace(
            government_balance=jnp.asarray(jnp.nan, dtype=jnp.float32)
        ),
    )
    with pytest.raises(ValueError, match="No run has a finite loss") as caught:
        Calibrator(inputs).run()
    notes = " ".join(getattr(caught.value, "__notes__", ()))
    assert "calibration_runs=" in notes
    assert "start_index" in notes and "loss_history" in notes
    assert "checked_parameters" in notes and "checked_weights" in notes


def test_native_constant_parameter_path_retains_raw_degeneracy() -> None:
    """A repaired covariance cannot relabel zero native curvature as missing evidence."""
    inputs = _tax_inputs(_compile_observations([("fit", 1, 10.0)]))
    state = inputs.base_state.replace(
        agents=inputs.base_state.agents.replace(reported_income=jnp.zeros(1, dtype=jnp.float32))
    )
    config = inputs.config.model_copy(
        update={"hessian": inputs.config.hessian.model_copy(update={"damping": 1e-3})}
    )
    report = Calibrator(replace(inputs, base_state=state, config=config)).run()
    assert np.isfinite(report.total_loss)
    assert report.execution_context["selection_reason"] == "single_run"
    assert report.execution_context["hessian"]["raw_condition_status"] == "non_finite"
    assert report.execution_context["hessian"]["raw_condition_value"] is None
    assert "hessian_raw_condition_non_finite" in report.diagnostics
    assert report.uncertainties is not None
    assert report.uncertainties.hessian_condition is None
