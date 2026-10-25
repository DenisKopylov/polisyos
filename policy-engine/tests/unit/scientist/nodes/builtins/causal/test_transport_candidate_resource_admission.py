from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.analytics.transportability import TransportabilityCandidateRequestV1
from polisyos.scientist.nodes.builtins.causal import resolve_transport as resolver
from polisyos.scientist.nodes.builtins.causal.resolve_transport import RunTransportabilityNode
from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.orchestration.workflows.causal_full import (
    CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM,
    causal_full_transport_resource_policy_snapshot,
)

_CANON = CanonSpec(forbid_floats=False, sort_keys=True, exclude_none=False)


def _ref(label: str, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + label * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )


def _attempt_context(policy_snapshot: dict[str, Any]):
    workflow = WorkflowSpec(
        workflow_id="resource_policy_fixture",
        nodes=[
            NodeInvocation(
                alias="run_transportability",
                node_id="scientist.node_run_transportability@1.0.0",
                params={CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM: policy_snapshot},
                timeout_s=120.0,
            )
        ],
    )
    workflow_ref = _ref("a", "scientist.workflow_spec")
    state_ref = _ref("b", "scientist.experiment_state")
    basis_ref = _ref("c", "run.invocation_started")
    basis = SimpleNamespace(
        run_id="run-resource-policy",
        node_alias="run_transportability",
        component_id="scientist.node_run_transportability@1.0.0",
        outcome=None,
        implementation_identity=object(),
        attempt_id="6c1dfed2-4d97-4d83-9a79-d55ff474d532",
        attempt_number=1,
        started_at=None,
        workflow_spec_ref=workflow_ref,
        input_state_ref=state_ref,
    )
    attempt = SimpleNamespace(basis=basis, basis_ref=basis_ref, outcome=None)

    class Store:
        def verify(self, ref):
            del ref
            return SimpleNamespace(ok=True)

        def get_manifest(self, ref):
            del ref
            return SimpleNamespace(
                kind="scientist.workflow_spec",
                artifact_schema=SimpleNamespace(
                    name="polisyos.scientist.orchestration.engine.WorkflowSpec",
                    version="1.0",
                ),
            )

        def get_bytes(self, ref):
            del ref
            return to_canonical_bytes(workflow.model_dump(mode="json"), _CANON)

    run = SimpleNamespace(
        run_manifest=SimpleNamespace(run_id="run-resource-policy"),
        read_runtime_invocation_attempts=lambda: [attempt],
    )
    context = SimpleNamespace(
        _engine_invocation=_EngineInvocationBinding(
            run_id="run-resource-policy",
            attempt_id=basis.attempt_id,
            basis_ref=basis_ref,
        ),
        run=run,
        store=Store(),
    )
    state = SimpleNamespace(run_id="run-resource-policy", params={})
    return context, state, RunTransportabilityNode()


@pytest.mark.parametrize("drift_kind", ["forged_limits", "owner_policy_changed"])
def test_frozen_resource_policy_drift_refuses_before_input_state_or_generation(
    drift_kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen = causal_full_transport_resource_policy_snapshot()
    if drift_kind == "forged_limits":
        supplied = deepcopy(frozen)
        supplied["limits"]["max_evaluations"] = 63
        context, state, node = _attempt_context(supplied)
    else:
        context, state, node = _attempt_context(frozen)
        changed_current = deepcopy(frozen)
        changed_current["limits"]["max_evaluations"] = 63
        monkeypatch.setattr(
            resolver,
            "causal_full_transport_resource_policy_snapshot",
            lambda: changed_current,
        )

    def unexpected_input_state_load(*args, **kwargs):
        del args, kwargs
        raise AssertionError("input state load must not run after policy drift")

    monkeypatch.setattr(
        resolver,
        "_load_engine_owned_invocation_input_state",
        unexpected_input_state_load,
    )
    request = TransportabilityCandidateRequestV1(
        profile_id="transport.conditional.resolved_graph",
        profile_revision="1",
        selection_identity="transport-candidate.standard.v1",
    )

    with pytest.raises(
        ValueError,
        match="conditional_transport_resource_policy_snapshot_mismatch",
    ):
        resolver._bind_conditional_candidate_attempt(
            ctx=context,
            current_state=state,
            request=request,
            node=node,
        )


def test_work_policy_freezes_graph_derived_budget_units() -> None:
    snapshot = causal_full_transport_resource_policy_snapshot()

    assert snapshot["policy_revision"] == "g528-conditional-transport-resources.v2"
    limits = snapshot["limits"]
    units = snapshot["limit_units"]
    assert limits["max_estimated_dsep_queries"] == 8192
    assert units["max_estimated_dsep_queries"] == "d_separation_query_count"
    assert limits["max_expanded_graph_element_query_units"] == 524288
    assert units["max_expanded_graph_element_query_units"] == "expanded_graph_element_query_units"
