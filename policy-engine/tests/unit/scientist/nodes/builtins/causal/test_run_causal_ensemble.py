"""Gap-coverage tests for RunCausalEnsembleNode."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

import polisyos.scientist.nodes.builtins.causal.run_causal_ensemble as ensemble_module
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts._profiled_ref import profile_bound_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.causal_queries import (
    CausalQuery,
    CausalQueryResult,
    QueryType,
)
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
    persist_structural_causal_model_spec,
)
from polisyos.runtime.http.resilience import guard_runtime_cas
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import (
    RunCausalEnsembleNode,
    _run_member_query,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
)
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)


def test_skip_when_ensemble_not_enabled(execution_context, minimal_state):
    """causal_ensemble_enabled not True -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = RunCausalEnsembleNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("not true" in e.message.lower() for e in outcome.events)


def test_skip_when_no_candidates_and_no_scm(execution_context, minimal_state):
    """Ensemble enabled but no members and no SCM in artifacts_index -> skip."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_ensemble_enabled": True,
            },
        },
    )
    outcome = RunCausalEnsembleNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("No structural candidates" in e.message for e in outcome.events)


def test_fail_when_members_payload_invalid(execution_context, minimal_state):
    """causal_ensemble_members with invalid content -> fail."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_ensemble_enabled": True,
                # Each member entry must validate as _MemberPayload; a bare int will fail
                "causal_ensemble_members": [42],
            },
        },
    )
    outcome = RunCausalEnsembleNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE


def test_causal_ensemble_member_assertion_is_not_swallowed(
    execution_context, minimal_state, monkeypatch: pytest.MonkeyPatch
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_ensemble_enabled": True,
                "causal_ensemble_members": [
                    {"structural_causal_model_spec_ref": "sha256:" + "a" * 64}
                ],
            },
        },
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("ensemble-member-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble._MemberPayload.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="ensemble-member-broken"):
        RunCausalEnsembleNode().execute(execution_context, state)


def test_run_causal_ensemble_uses_branch_state_for_success_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    graph_ref = artifact_ref_factory(kind="ir.causal_graph_model")
    ensemble_ref = profile_bound_ref(
        execution_context.store, artifact_ref_factory(kind="ir.causal_model_ensemble")
    )
    envelope_ref = profile_bound_ref(
        execution_context.store, artifact_ref_factory(kind="ir.uncertainty_envelope")
    )
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )
    query_result = CausalQueryResult(
        query=query,
        result_mean=1.05,
        result_std=0.1,
        result_ci=(0.8, 1.3),
        result_distribution=[1.0, 1.1],
    )
    graph = CausalGraphModel.model_validate(
        {
            "graph_type": "dag",
            "nodes": ["X", "Y"],
            "edges": [{"src": "X", "dst": "Y"}],
        }
    )
    scm_ref = persist_structural_causal_model_spec(
        _ensure_ir_artifact_store(execution_context.store),
        StructuralCausalModelSpec(
            graph=graph,
            mechanisms=[
                NodeMechanism(
                    variable="Y",
                    parents=["X"],
                    family=MechanismFamily.LINEAR,
                    family_params={
                        "intercept": 0.0,
                        "coefficients": {"X": 1.0},
                        "noise_std": 0.1,
                    },
                    source=MechanismSource.DEFAULT,
                )
            ],
            fit_method="manual",
        ),
    )
    assert scm_ref.manifest_profile_sha256 is not None
    candidate = SimpleNamespace(
        order=0,
        scm_inline=None,
        scm_ref=scm_ref,
        graph_ref=None,
        query_result_ref=None,
        discovery_report_ref=None,
        discovery_method="pc",
        explicit_weight=0.7,
        bootstrap_stability=0.8,
    )

    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "causal_ensemble_enabled": True,
            "causal_query": {
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 1.0,
                "outcome_variable": "Y",
            },
            "nested": {"baseline": True},
        }
    )
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble._resolve_members",
            return_value=([candidate], []),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.ensure_causal_methods_registered",
            return_value=None,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.load_structural_causal_model_spec",
            return_value=SimpleNamespace(fit_method="pc"),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble._load_graph_for_candidate",
            return_value=(graph, graph_ref),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble._run_member_query",
            return_value=query_result,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble._build_consensus_graph",
            return_value=(None, []),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.persist_causal_model_ensemble",
            return_value=ensemble_ref,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.persist_uncertainty_envelope",
            return_value=envelope_ref,
        ),
    ):
        outcome = RunCausalEnsembleNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "params.causal_ensemble_member_count",
        "params.causal_ensemble_methods",
        "params.causal_ensemble_warning",
        "artifacts_index.causal_ensemble_ref",
        "artifacts_index.causal_ensemble_envelope_ref",
        "artifacts_index.causal_envelope_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_CAUSAL_ENSEMBLE_REF not in state.artifacts_index
    ensemble_output_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_REF]
    assert ensemble_output_ref.model_dump(mode="json") == ensemble_ref.model_dump(mode="json")
    assert ensemble_output_ref.manifest_profile_sha256 is not None
    ensemble_envelope_output_ref = outcome.state.artifacts_index[
        ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF
    ]
    assert ensemble_envelope_output_ref.model_dump(mode="json") == envelope_ref.model_dump(
        mode="json"
    )
    causal_envelope_output_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF]
    assert causal_envelope_output_ref.model_dump(mode="json") == envelope_ref.model_dump(
        mode="json"
    )


def test_member_query_accepts_guarded_rooted_store_and_checks_root_value(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileSystemCAS(tmp_path)
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="policy",
        treatment_value=1.0,
        outcome_variable="outcome",
    )
    query_payload = {
        "query": query.model_dump(mode="json"),
        "result_mean": 0.5,
        "result_std": 0.1,
        "result_ci": [0.3, 0.7],
    }
    observed: dict[str, object] = {}

    monkeypatch.setattr(ensemble_module, "SCMQueryData", lambda **_: object())

    def _run_job(_spec, *, cas_root, method_state):
        del method_state
        observed["cas_root"] = cas_root
        return SimpleNamespace(issues=(), final_state={"query_result": query_payload})

    monkeypatch.setattr(ensemble_module, "run_job", _run_job)
    result = _run_member_query(
        ctx=SimpleNamespace(store=guard_runtime_cas(store)),
        query=query,
        scm_spec=object(),
        seed=7,
    )

    assert result.result_mean == 0.5
    assert observed["cas_root"] == tmp_path
    with pytest.raises(RuntimeError, match="causal_ensemble_rooted_store_required"):
        _run_member_query(
            ctx=SimpleNamespace(store=SimpleNamespace(root=tmp_path)),
            query=query,
            scm_spec=object(),
            seed=7,
        )
