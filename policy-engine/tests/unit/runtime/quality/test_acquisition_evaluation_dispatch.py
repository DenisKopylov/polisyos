"""Exercise the ordinary retained dispatcher through the real source reader."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality.acquisition_evaluation import AcquisitionEvaluationBasis
from polisyos.runtime.quality.generation_cycle import GenerationCycleRun
from polisyos.runtime.quality.generation_source import GenerationSourceRepository
from polisyos.runtime.quality.substrate_registry import current_catalog_serving_source
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.quality.test_generation_cycle_model_input_wire import _v3_fixture
from tests.unit.runtime.quality.test_n5_prepared_configuration_owner import (
    _candidate_context_fixture,
)


def test_ordinary_retention_composes_current_owner_and_reopens_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adapt the lease and N5 basis inputs while exercising composition and CAS reads."""
    _, handoff, store = _candidate_context_fixture(tmp_path)
    repo_root = Path(__file__).resolve().parents[4]
    service = _build_control_service(tmp_path, artifact_store=store, repo_root=repo_root)
    catalog = service.catalog_serving_source

    def save(value: dict[str, object], kind: str) -> artifacts.ArtifactRef:
        return store.put_json(
            value,
            artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    source_payload_ref = save({"llm_models": ["fixture-model"]}, "test.source_payload")
    basis_ref = save({"effective_native_values_hex": "08"}, "test.current_basis")
    # The fixture deliberately carries no historical N4/N5 execution. The real
    # reader must reach the exact selected source, then refuse its unsupported view.
    source_ref = save({"fixture_source": "selected"}, "test.unqualified_retained_source")
    _, wire = _v3_fixture()
    run = GenerationCycleRun.model_validate(wire)
    old = run.cycles[-1]
    simulation = old.simulation.model_copy(
        update={
            "status": "joint_simulated",
            "simulation_result_ref": basis_ref,
            "candidate_simulation_n5_input_ref": basis_ref,
            "candidate_simulation_context_job_ref": handoff.context_job_ref,
            "diagnostics": {
                "candidate_simulation_n4_source_selected_ref": source_ref.model_dump(mode="json"),
            },
        }
    )
    cycle = old.model_copy(update={"simulation": simulation})
    run = run.model_copy(update={"run_id": handoff.run_id, "cycles": (*run.cycles[:-1], cycle)})
    prepared = SimpleNamespace(n5_execution_configuration=None)
    selection = SimpleNamespace(
        closure=SimpleNamespace(
            source_payload_ref=source_payload_ref,
            generation_run=run,
            source_cycle=cycle,
            design_problem_basis=None,
        ),
        phase_ref=basis_ref,
        growth_ref=basis_ref,
        growth=SimpleNamespace(selection=SimpleNamespace(reentry_budget_usd="0.5")),
        projection=object(),
        prepared=prepared,
        admitted_source_ref=source_ref,
    )
    bridge = SimpleNamespace(
        artifact_store=store,
        event_log=service._diagnostic_event_log,
        repo_root=repo_root,
        promotion_runtime=service._promotion_runtime,
        _source_control_service=service,
    )
    prior = SimpleNamespace(handoff=handoff)
    basis = AcquisitionEvaluationBasis.model_construct(
        comparison_profile="fixture",
        predicate_provenance="recomputed",
        reason_codes=(),
        preparation_inputs=prepared,
        effective_native_values_hex="08",
    )
    monkeypatch.setattr(dispatch, "_current_selection", lambda _: selection)
    monkeypatch.setattr(dispatch, "_basis_for_current", lambda *_: basis)

    def read_basis(*, store, event_log, ref, kind):
        assert event_log is service._diagnostic_event_log and kind == "basis"
        payload = artifacts.load_core_json_artifact(store, ref)
        return basis.model_copy(update=payload)

    monkeypatch.setattr(dispatch, "read_acquisition_basis_or_decision_artifact", read_basis)
    reopened = []
    real_source_read = GenerationSourceRepository.load_candidate_scenario_source_in_owner_scope

    def observe_read(self, ref, **expected):
        assert self.store is store and current_catalog_serving_source() is catalog
        reopened.append((ref, expected))
        return real_source_read(self, ref, **expected)

    monkeypatch.setattr(
        GenerationSourceRepository, "load_candidate_scenario_source_in_owner_scope", observe_read
    )
    owner = dispatch.AcquisitionEvaluationCurrentOwner(bridge, basis_ref, selection, prior)
    assert owner.currentness_resolver() is True
    result = dispatch._current_cheap_continuation(owner)
    assert result.reason_code == "retained_cheap_prior_source_unresolved"
    assert reopened == [
        (
            source_ref,
            {
                "expected_run_id": handoff.run_id,
                "expected_tenant_id": handoff.tenant_id,
                "expected_cell_id": handoff.cell_id,
            },
        ),
    ]
    assert current_catalog_serving_source() is None

    changed_ref = save({"effective_native_values_hex": "09"}, "test.current_basis")
    changed = replace(owner, current_basis_ref=changed_ref)
    assert changed.currentness_resolver() is False
    with pytest.raises(ValueError, match=r"^acquisition_retained_current_basis_changed$"):
        dispatch._current_cheap_continuation(changed)
    assert len(reopened) == 1
    assert current_catalog_serving_source() is None
