from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.ir.artifacts import get_json_artifact
from polisyos.scientist.nodes.builtins.simulate.welfare_draws import (
    _MonteCarloCounters,
    _MonteCarloDrawSet,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_reports import (
    _persist_welfare_mc_report,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_types import _WelfareNodeFailure


def _envelope() -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=2.0,
        confidence_interval=(1.0, 3.0),
        distribution_family=DistributionFamily.UNKNOWN,
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata={"param_name": "rate"},
    )


def _outcome(
    draw_index: int,
    outcome_code: str,
    sample_index: int | None,
) -> dict[str, object]:
    attempt = {
        "draw_index": draw_index,
        "attempt_number": 1,
        "sampled_input_sha256": f"sha256:{draw_index:064x}",
        "outcome_code": outcome_code,
    }
    return {
        "draw_index": draw_index,
        "sampled_input_sha256": attempt["sampled_input_sha256"],
        "outcome_code": outcome_code,
        "sample_index": sample_index,
        "execution_attempt_count": 1,
        "execution_attempts": [attempt],
    }


def _provenance(
    *,
    requested: int,
    attempted: int,
    simulation_attempts: int,
    successful: int,
    outcomes: list[dict[str, object]],
) -> dict[str, object]:
    failed = sum(row["outcome_code"] != "success" for row in outcomes)
    return {
        "schema_version": "1.2",
        "requested_draw_count": requested,
        "attempted_draw_count": attempted,
        "simulation_attempt_count": simulation_attempts,
        "retry_attempt_count": simulation_attempts - attempted,
        "max_attempts_per_draw": 2,
        "successful_draw_count": successful,
        "failed_draw_count": failed,
        "unattempted_draw_count": requested - attempted,
        "outcome_denominator_complete": len(outcomes) == requested,
        "summary_semantics": (
            "successful_draws_only_conditional_on_execution"
            if failed or requested > attempted
            else "complete_requested_draws"
        ),
        "outcomes": outcomes,
    }


def _draw_summary() -> dict[str, float]:
    return {
        "welfare_mean": 2.0,
        "welfare_std": 0.5,
        "welfare_pe_mean": 2.0,
        "welfare_ge_mean": 0.0,
    }


def test_partial_report_keeps_conditional_summary_and_selected_input_lineage(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    envelope = _envelope()
    envelope_ref = persist_uncertainty_envelope(ensure_ir_artifact_store(store), envelope)
    partial_outcomes = [
        _outcome(0, "success", 0),
        _outcome(1, "success", 1),
        _outcome(2, "sample_domain_inapplicable", None),
    ]
    partial_draws = _MonteCarloDrawSet(
        welfare=[1.5, 2.5],
        welfare_pe=[1.5, 2.5],
        welfare_ge=[0.0, 0.0],
        terminal_outcomes=partial_outcomes,
        counters=_MonteCarloCounters(attempted_draw_count=3, simulation_attempt_count=3),
        requested_draw_count=3,
        dependence_sampler={"applied": False},
        calibration_resolution=None,
    )
    partial_ref = _persist_welfare_mc_report(
        SimpleNamespace(store=store),
        draws=partial_draws,
        input_envelopes={"rate": envelope},
        input_envelope_refs={"rate": envelope_ref},
        calibration_source=None,
        context=SimpleNamespace(dependence_structure_ref=None),
        requested_method="monte_carlo",
        provenance=_provenance(
            requested=3,
            attempted=3,
            simulation_attempts=3,
            successful=2,
            outcomes=partial_outcomes,
        ),
        summary=_draw_summary(),
        complete_draws=False,
        sample_bundle_ref=None,
    )
    fresh_store = FileSystemCAS(tmp_path)
    fresh_ir_store = ensure_ir_artifact_store(fresh_store)
    partial = get_json_artifact(fresh_ir_store, partial_ref)
    manifest = fresh_ir_store.get_manifest(partial_ref)

    assert partial["valid_draw_count"] == 2
    assert partial["conditional_draw_summary"] == _draw_summary()
    assert partial["draw_outcome_provenance"]["successful_draw_count"] == 2
    assert partial["draw_outcome_provenance"]["failed_draw_count"] == 1
    assert partial["draw_outcome_provenance"]["unattempted_draw_count"] == 0
    assert (
        partial["draw_outcome_provenance"]["successful_draw_count"]
        + partial["draw_outcome_provenance"]["failed_draw_count"]
        + partial["draw_outcome_provenance"]["unattempted_draw_count"]
        == partial["draw_outcome_provenance"]["requested_draw_count"]
    )
    assert "draw_summary" not in partial
    assert any(item.role == "input_envelope.rate" for item in manifest.inputs)

    complete_outcomes = [_outcome(0, "success", 0), _outcome(1, "success", 1)]
    complete_draws = _MonteCarloDrawSet(
        welfare=[1.5, 2.5],
        welfare_pe=[1.5, 2.5],
        welfare_ge=[0.0, 0.0],
        terminal_outcomes=complete_outcomes,
        counters=_MonteCarloCounters(attempted_draw_count=2, simulation_attempt_count=2),
        requested_draw_count=2,
        dependence_sampler={"applied": False},
        calibration_resolution=None,
    )
    complete_ref = _persist_welfare_mc_report(
        SimpleNamespace(store=store),
        draws=complete_draws,
        input_envelopes={"rate": envelope},
        input_envelope_refs={"rate": envelope_ref},
        calibration_source=None,
        context=SimpleNamespace(dependence_structure_ref=None),
        requested_method="monte_carlo",
        provenance=_provenance(
            requested=2,
            attempted=2,
            simulation_attempts=2,
            successful=2,
            outcomes=complete_outcomes,
        ),
        summary=_draw_summary(),
        complete_draws=True,
        sample_bundle_ref=None,
    )
    complete = get_json_artifact(fresh_ir_store, complete_ref)

    assert complete["draw_summary"] == _draw_summary()
    assert "conditional_draw_summary" not in complete


def test_unattempted_draws_remain_partial_in_fresh_report_reader(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    envelope = _envelope()
    envelope_ref = persist_uncertainty_envelope(ensure_ir_artifact_store(store), envelope)
    outcomes = [_outcome(0, "success", 0), _outcome(1, "success", 1)]
    draws = _MonteCarloDrawSet(
        welfare=[1.5, 2.5],
        welfare_pe=[1.5, 2.5],
        welfare_ge=[0.0, 0.0],
        terminal_outcomes=outcomes,
        counters=_MonteCarloCounters(attempted_draw_count=2, simulation_attempt_count=2),
        requested_draw_count=3,
        dependence_sampler={"applied": False},
        calibration_resolution=None,
    )
    provenance = _provenance(
        requested=3,
        attempted=2,
        simulation_attempts=2,
        successful=2,
        outcomes=outcomes,
    )
    report_ref = _persist_welfare_mc_report(
        SimpleNamespace(store=store),
        draws=draws,
        input_envelopes={"rate": envelope},
        input_envelope_refs={"rate": envelope_ref},
        calibration_source=None,
        context=SimpleNamespace(dependence_structure_ref=None),
        requested_method="monte_carlo",
        provenance=provenance,
        summary=_draw_summary(),
        complete_draws=False,
        sample_bundle_ref=None,
    )

    fresh_report = get_json_artifact(ensure_ir_artifact_store(FileSystemCAS(tmp_path)), report_ref)

    assert fresh_report["valid_draw_count"] == 2
    assert fresh_report["draw_outcome_provenance"]["requested_draw_count"] == 3
    assert fresh_report["draw_outcome_provenance"]["attempted_draw_count"] == 2
    assert fresh_report["draw_outcome_provenance"]["successful_draw_count"] == 2
    assert fresh_report["draw_outcome_provenance"]["failed_draw_count"] == 0
    assert fresh_report["draw_outcome_provenance"]["unattempted_draw_count"] == 1
    assert (
        fresh_report["draw_outcome_provenance"]["successful_draw_count"]
        + fresh_report["draw_outcome_provenance"]["failed_draw_count"]
        + fresh_report["draw_outcome_provenance"]["unattempted_draw_count"]
        == fresh_report["draw_outcome_provenance"]["requested_draw_count"]
    )
    assert fresh_report["draw_outcome_provenance"]["outcome_denominator_complete"] is False
    assert (
        fresh_report["draw_outcome_provenance"]["summary_semantics"]
        == "successful_draws_only_conditional_on_execution"
    )
    assert fresh_report["conditional_draw_summary"] == _draw_summary()
    assert "draw_summary" not in fresh_report


@pytest.mark.parametrize("claim", ["completion_flag", "provenance_counts"])
def test_report_refuses_complete_claim_when_draw_record_is_partial(tmp_path, claim: str) -> None:
    store = FileSystemCAS(tmp_path)
    envelope = _envelope()
    envelope_ref = persist_uncertainty_envelope(ensure_ir_artifact_store(store), envelope)
    outcomes = [_outcome(0, "success", 0), _outcome(1, "sample_domain_inapplicable", None)]
    draws = _MonteCarloDrawSet(
        welfare=[2.0],
        welfare_pe=[2.0],
        welfare_ge=[0.0],
        terminal_outcomes=outcomes,
        counters=_MonteCarloCounters(attempted_draw_count=2, simulation_attempt_count=2),
        requested_draw_count=3,
        dependence_sampler={"applied": False},
        calibration_resolution=None,
    )
    provenance = _provenance(
        requested=3,
        attempted=2,
        simulation_attempts=2,
        successful=1,
        outcomes=outcomes,
    )
    complete_claim = False
    if claim == "completion_flag":
        complete_claim = True
    else:
        provenance = _provenance(
            requested=3,
            attempted=2,
            simulation_attempts=2,
            successful=2,
            outcomes=outcomes,
        )

    with pytest.raises(_WelfareNodeFailure) as failure:
        _persist_welfare_mc_report(
            SimpleNamespace(store=store),
            draws=draws,
            input_envelopes={"rate": envelope},
            input_envelope_refs={"rate": envelope_ref},
            calibration_source=None,
            context=SimpleNamespace(dependence_structure_ref=None),
            requested_method="monte_carlo",
            provenance=provenance,
            summary={
                "welfare_mean": 2.0,
                "welfare_std": 0.0,
                "welfare_pe_mean": 2.0,
                "welfare_ge_mean": 0.0,
            },
            complete_draws=complete_claim,
            sample_bundle_ref=None,
        )

    assert failure.value.error.code == "ERROR_MONTE_CARLO_NOT_CONVERGED"
