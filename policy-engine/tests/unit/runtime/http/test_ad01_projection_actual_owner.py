"""Real Runtime-owner source-selection witness; full E02 replay remains separate."""

from pathlib import Path
from typing import Any

import pytest
from _helpers.completed_ex_ante_runtime import launch_completed_ex_ante_source
from _helpers.control_worker import stop_embedded_control_worker

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.security import build_fixture_identity_claims
from polisyos.scientist.nodes.builtins.decide import policy_runtime_support
from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
    read_completed_admitted_method_metric_projection,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    persist_policy_evaluation_vector_to_store,
)
from tests.unit.scientist.nodes.builtins.decide.test_policy_runtime_method_metrics import (
    _exercise_public_execute_method_metric_source,
)


def test_real_completed_owner_is_reselected_for_current_vector_write(
    runtime_api_env: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    store = service._artifact_store
    tenant, cell = runtime_api_env["tenant_a"], runtime_api_env["cell_a"]
    principal = RuntimePrincipal.from_user_claims(build_fixture_identity_claims())
    assert principal.authenticated and principal.fixture_identity
    assert (principal.tenant_id, principal.cell_id) == (tenant, cell)
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        prepared = _exercise_public_execute_method_metric_source(
            tmp_path / "source", monkeypatch, artifact_store=store, prepare_only=True
        )
    completed = launch_completed_ex_ante_source(service, prepared, principal)
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        read = read_completed_admitted_method_metric_projection(
            store,
            owner=service,
            source_run_id=completed["launch"].run_id,
            candidate_ref=prepared["candidate_ref"],
            tenant_id=tenant,
            cell_id=cell,
        )
        assert read.status == "selected" and read.basis is not None
        # Safety bypass is confined to this synthetic association witness; it proves no grounding.
        monkeypatch.setattr(
            policy_runtime_support,
            "_production_policy_evaluation_safety_blockers",
            lambda **kwargs: [],
        )
        backend = policy_runtime_support.ProductionPolicyEvaluationBackend().with_method_metric_projection_basis(
            basis=read.basis, candidate_ref=prepared["candidate_ref"]
        )
        artifact = backend.evaluate(
            prepared["candidate"],
            fidelity="selection",
            simulation_metrics={},
            uncertainty=None,
            distributional_report=None,
            causal_effect_report=None,
            cross_graph_profile=None,
            governance_report=None,
        )
        ref = persist_policy_evaluation_vector_to_store(
            store,
            candidate_ref=prepared["candidate_ref"],
            evaluation_vector=artifact.evaluation_vector,
            completed_projection_basis=read.basis,
            completed_projection_binding=artifact.completed_projection_binding,
        )
        assert ref.manifest_profile_sha256 is not None
        roles = {edge.role for edge in store.get_manifest(ref).inputs}
        assert {
            "completed_projection_source_candidate",
            "completed_projection_source_state",
            "completed_projection_vector",
        } <= roles
