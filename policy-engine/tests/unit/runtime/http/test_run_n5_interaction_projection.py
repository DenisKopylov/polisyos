"""Readonly display compatibility; numerical-owner qualification lives in SIM tests."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from polisyos.runtime.http.routes.runs import (
    _n5_interaction_evidence_projection,
    _n5_interaction_projection_blockers,
    _n8_interaction_qualification_fields,
)


def _result(version: str) -> SimpleNamespace:
    summary = SimpleNamespace(
        status="estimated",
        replicate_count=2,
        seeds=(41, 42),
        samples=(
            SimpleNamespace(seed=41, effects={"derived_effect": 0.0}),
            SimpleNamespace(seed=42, effects={"derived_effect": 0.0}),
        ),
        effects_standard_error={"derived_effect": 0.0},
    )
    return SimpleNamespace(
        schema_version=f"policyos.runtime.joint_simulation_horizon.{version}",
        feedback_classification=SimpleNamespace(
            numeric_interaction="additive",
            numeric_interaction_basis="finite_checked_model_point_estimate_only",
            interaction_sampling_status="estimated",
            checked_interaction_orders=(1, 2),
        ),
        interaction_terms=(
            SimpleNamespace(
                atom_ids=("a", "b"),
                outcome="outcome-a",
                by_step={0: 0.0},
                replication_sampling_by_step={0: summary},
            ),
        ),
        higher_order_residuals={},
        higher_order_residual_sampling={},
    )


@pytest.mark.parametrize("version", ["v4", "v5"])
def test_projection_preserves_paired_vectors_without_promoting_the_v4_numeric_label(
    version: str,
) -> None:
    result = _result(version)
    before = deepcopy(result)
    projection = _n5_interaction_evidence_projection(result)
    assert projection is not None
    assert projection["numeric_interaction"] == ("unsupported" if version == "v4" else "additive")
    assert projection["interaction_sampling_status"] == "estimated"
    assert projection["numeric_interaction_basis"] == "finite_checked_model_point_estimate_only"
    assert projection["interaction_terms"][0]["replication_sampling_by_step"]["0"]["samples"] == [
        {"seed": 41, "value": 0.0},
        {"seed": 42, "value": 0.0},
    ]
    assert result == before
    blockers = _n5_interaction_projection_blockers(result, ("existing_limit",))
    assert blockers == (
        ("existing_limit", "interaction_numeric_classification_unsupported")
        if version == "v4"
        else ("existing_limit",)
    )


def test_old_n8_record_stays_readable_but_fresh_projection_withholds_its_v4_numeric_class() -> None:
    value = SimpleNamespace(
        numeric_interaction="non_additive",
        numeric_interaction_basis="finite_checked_model_point_estimate_only",
        interaction_sampling_status="estimated",
        status="value_conditional",
        authority_blockers=("prior_limit",),
    )
    before = deepcopy(value)
    projected = _n8_interaction_qualification_fields(value, n5_result=_result("v4"))
    assert projected["n8_numeric_interaction"] == "unsupported"
    assert projected["n8_interaction_sampling_status"] == "estimated"
    assert projected["n8_status"] == "value_conditional"
    assert projected["n8_authority_blockers"] == (
        "prior_limit",
        "interaction_numeric_classification_unsupported",
    )
    assert value == before
    fallback = _n8_interaction_qualification_fields(
        value, include_status=False, n5_result=_result("v4")
    )
    assert fallback == {
        "n8_numeric_interaction": "unsupported",
        "n8_numeric_interaction_basis": "finite_checked_model_point_estimate_only",
        "n8_interaction_sampling_status": "estimated",
    }
    assert _n5_interaction_projection_blockers(_result("v4"), value.authority_blockers) == (
        "prior_limit",
        "interaction_numeric_classification_unsupported",
    )
    historical = _n8_interaction_qualification_fields(value)
    assert historical["n8_numeric_interaction"] == "non_additive"


def test_recorded_attempt_projection_requires_the_exact_owner_history_problem() -> None:
    """Projection/control coverage only; the real CYC-04 test supplies owner replay."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.runtime.http.routes.runs import _candidate_evaluation_attempt_projection
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.generation_cycle import (
        CandidateEvaluationAttempt,
        GenerationCycleContextHistoryBinding,
        GenerationCycleContextHistoryProjection,
        SimulationPortObservation,
        ValuePortObservation,
        _candidate_evaluation_attempt_ref,
    )
    from tests._helpers.controlled_candidate_profile import _problem

    problem = _problem()
    result_ref = ArtifactRef(
        artifact_id=f"sha256:{'a' * 64}",
        kind="polisyos.runtime.joint_simulation_result",
        media_type="application/json",
    )
    simulation = SimulationPortObservation(
        candidate_id="attempt-first",
        status="joint_simulated",
        simulation_ref=f"sha256:{'b' * 64}",
        simulation_result_ref=result_ref,
        authority_blockers=("simulation_only_k_sim_not_world_evidence",),
    )
    value = ValuePortObservation(
        status="value_blocked",
        candidate_id="attempt-first",
        decision_grade="blocked",
        authority_blockers=("candidate_value_unavailable",),
    )
    fields = {
        "candidate_id": "attempt-first",
        "candidate_content_hash": f"sha256:{'c' * 64}",
        "cycle_index": 2,
        "problem_ref": cycle_job_design_problem_ref(problem),
        "failure_stage": "n8",
        "simulation": simulation,
        "value": value,
    }
    attempt = CandidateEvaluationAttempt(
        **fields,
        attempt_ref=_candidate_evaluation_attempt_ref(**fields),
    )
    cycle_run = SimpleNamespace(candidate_summaries=(SimpleNamespace(evaluation_attempt=attempt),))
    context_ref = result_ref.model_copy(
        update={"kind": "runtime.quality.cycle_substrate_context_job"}
    )
    binding = GenerationCycleContextHistoryBinding(
        cycle_index=2, problem=problem, context_job_ref=context_ref, context=None
    )
    history = GenerationCycleContextHistoryProjection(
        status="resolved", bindings=(binding,), issues=()
    )
    rows, limitation = _candidate_evaluation_attempt_projection(
        node_ref="problem://attempt", cycle_run=cycle_run, context_history=history
    )
    assert limitation is None and len(rows) == 1
    assert rows[0].attempt_ref == attempt.attempt_ref
    assert rows[0].simulation_result_ref == result_ref
    assert rows[0].simulation_status == "joint_simulated"
    assert rows[0].value_status == "value_blocked"
    assert rows[0].numerical_result_verification == "not_established"
    for unavailable in (
        None,
        GenerationCycleContextHistoryProjection(status="not_established", bindings=(), issues=()),
        GenerationCycleContextHistoryProjection(status="resolved", bindings=(), issues=()),
        GenerationCycleContextHistoryProjection(
            status="resolved",
            bindings=(
                GenerationCycleContextHistoryBinding(
                    cycle_index=2,
                    problem=_problem("foreign_problem"),
                    context_job_ref=context_ref,
                    context=None,
                ),
            ),
            issues=(),
        ),
    ):
        assert _candidate_evaluation_attempt_projection(
            node_ref="problem://attempt", cycle_run=cycle_run, context_history=unavailable
        ) == ((), "candidate_attempt_context_history_not_established")


def test_candidate_history_second_fold_invalidates_stale_current_view() -> None:
    from polisyos.core.contracts.runtime import (
        RunCandidateSimulationContinuationFronts,
        RunCandidateSourceCurrentProjection,
    )
    from polisyos.runtime.http.routes.runs import _candidate_history_reconcile_current_basis

    current = RunCandidateSourceCurrentProjection(
        status="resolved",
        generation_run_content_hash="sha256:" + "1" * 64,
        basis_transition_content_hash="sha256:" + "2" * 64,
        basis_cycle_index=2,
        fronts=RunCandidateSimulationContinuationFronts(
            decision_candidate_ids=(),
            research_candidate_ids=(),
            quarantine_candidate_ids=(),
            portfolio_candidate_ids=(),
        ),
    )
    same = _candidate_history_reconcile_current_basis(
        current,
        generation_run_content_hash="sha256:" + "1" * 64,
        basis_transition_content_hash="sha256:" + "2" * 64,
        basis_cycle_index=2,
    )
    assert same is current
    changed = _candidate_history_reconcile_current_basis(
        current,
        generation_run_content_hash="sha256:" + "3" * 64,
        basis_transition_content_hash="sha256:" + "4" * 64,
        basis_cycle_index=3,
    )
    assert changed is not None and changed.status == "not_established"
    assert changed.issues == ("candidate_source_current_between_read_snapshot_mismatch",)
    assert changed.fronts is None and not changed.occurrences


def test_failed_stage_requires_selected_terminal_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.http.routes.runs import _failed_candidate_stage_from_terminal
    from polisyos.runtime.http.services.adapters import core_run

    refs = tuple(
        ArtifactRef(
            artifact_id="sha256:" + str(i) * 64,
            kind=f"test.{i}",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "a" * 64,
        )
        for i in range(1, 5)
    )
    manifest = SimpleNamespace(
        run_id="core",
        control_job_id="job",
        tenant_id="tenant",
        cell_id="cell",
        status="error",
        outputs=list(refs),
        errors=[{"stage": "value_projection"}],
    )
    terminal = SimpleNamespace(run_id="core", tenant_id="tenant", cell_id="cell", manifest=manifest)
    monkeypatch.setattr(core_run, "load_terminal_core_run_source", lambda **_: terminal)

    def read() -> str | None:
        return _failed_candidate_stage_from_terminal(
            run_id="core",
            control_job_id="job",
            tenant_id="tenant",
            cell_id="cell",
            required_roots=refs,
            store=object(),
            control_service=SimpleNamespace(_core_runs_root=object()),
        )

    assert read() == "value_projection"
    manifest.errors = [{"stage": "revision"}]
    assert read() == "revision"
    manifest.errors = [{}]
    assert read() is None
    manifest.errors = [{"stage": "revision"}, {"stage": "value_projection"}]
    assert read() is None
    manifest.errors = [{"stage": "value_projection"}]
    manifest.control_job_id = "other"
    assert read() is None
    manifest.control_job_id = "job"
    manifest.outputs[0] = refs[0].model_copy(
        update={"manifest_profile_sha256": "sha256:" + "b" * 64}
    )
    assert read() is None
    manifest.outputs = list(refs)
    terminal.cell_id = "other"
    assert read() is None


def test_failed_stage_preserves_canonical_profile_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.runtime.http.routes.runs import _failed_candidate_stage_from_terminal
    from polisyos.runtime.http.services.adapters import core_run

    def refuse(**_: object) -> None:
        raise CanonicalProfileRefusalError("refused")

    monkeypatch.setattr(core_run, "load_terminal_core_run_source", refuse)
    with pytest.raises(CanonicalProfileRefusalError):
        _failed_candidate_stage_from_terminal(
            run_id="core",
            control_job_id="job",
            tenant_id="tenant",
            cell_id="cell",
            required_roots=(),
            store=object(),
            control_service=SimpleNamespace(_core_runs_root=object()),
        )


@pytest.mark.parametrize("wrapped", [False, True])
def test_failed_stage_preserves_owner_access_refusal(
    monkeypatch: pytest.MonkeyPatch, wrapped: bool
) -> None:
    from polisyos.core.artifacts import ArtifactOwnershipError
    from polisyos.runtime.http.routes.runs import _failed_candidate_stage_from_terminal
    from polisyos.runtime.http.services.adapters import core_run

    def refuse(**_: object) -> None:
        denial = ArtifactOwnershipError("different scope")
        if wrapped:
            raise ValueError("reader failed") from denial
        raise denial

    monkeypatch.setattr(core_run, "load_terminal_core_run_source", refuse)
    with pytest.raises(ArtifactOwnershipError):
        _failed_candidate_stage_from_terminal(
            run_id="core",
            control_job_id="job",
            tenant_id="tenant",
            cell_id="cell",
            required_roots=(),
            store=object(),
            control_service=SimpleNamespace(_core_runs_root=object()),
        )
