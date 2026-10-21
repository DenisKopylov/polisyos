"""Fresh method-metric owner identities partition funnel continuation caches."""

from __future__ import annotations

import pickle
from copy import copy, deepcopy
from dataclasses import asdict

import pytest

from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import FunnelStageResult, UncertaintyEnvelope
from polisyos.scientist.methods.search.objective import ObjectiveScoreStatus


class _CountingStage:
    fidelity_level = 0
    stage_name = "method-metric-cache-identity"
    estimated_cost_usd = 0.0

    def __init__(self) -> None:
        self.calls = 0
        self.received_basis = None

    def evaluate(self, candidate, context):
        self.calls += 1
        self.received_basis = context.get("_funnel_method_metric_projection_basis")
        return FunnelStageResult(
            policy_candidate=dict(candidate),
            objective_value=None,
            is_promising=True,
            score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
            stage_name=self.stage_name,
            uncertainty_envelope=UncertaintyEnvelope.deterministic(),
            fidelity_level=self.fidelity_level,
        )


def test_owner_revalidation_and_revocation_identity_prevent_positive_cache_reuse() -> None:
    """A changed current owner result cannot reuse a prior source-qualified ticket."""
    stage = _CountingStage()
    orchestrator = FunnelOrchestrator([stage])
    candidate = {"candidate_id": "method-metric-source-cache"}
    selected_owner_identity = {
        "request_status": "requested",
        "requested_source_run_id": "source-run",
        "resolved_status": "selected",
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "selected_source": {
            "source_run_id": "source-run",
            "projection_vector_ref": {
                "artifact_id": "sha256:" + "a" * 64,
                "manifest_profile_sha256": "sha256:" + "b" * 64,
            },
            "verifier_revision": "1.0",
            "verifier_implementation_sha256": "c" * 64,
        },
    }
    selected_ticket = orchestrator.submit(
        candidate,
        {"_funnel_method_metric_projection_identity": selected_owner_identity},
    )
    orchestrator.advance(selected_ticket)

    revoked_owner_identity = {
        "request_status": "requested",
        "requested_source_run_id": "source-run",
        "resolved_status": "verification_missing",
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "limitations": ["completed_method_metric_source_not_established"],
    }
    limited_ticket = orchestrator.submit(
        candidate,
        {"_funnel_method_metric_projection_identity": revoked_owner_identity},
    )
    assert limited_ticket is not selected_ticket
    orchestrator.advance(limited_ticket)
    assert stage.calls == 2


def test_same_source_cache_identity_requires_exact_selected_vector_profile() -> None:
    """A manifest-profile change partitions the same vector content identity."""
    stage = _CountingStage()
    orchestrator = FunnelOrchestrator([stage])
    candidate = {"candidate_id": "method-metric-profile-cache"}
    owner_identity = {
        "request_status": "requested",
        "requested_source_run_id": "source-run",
        "resolved_status": "selected",
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "selected_source": {
            "source_run_id": "source-run",
            "projection_vector_ref": {
                "artifact_id": "sha256:" + "a" * 64,
                "manifest_profile_sha256": "sha256:" + "b" * 64,
            },
            "verifier_revision": "1.0",
            "verifier_implementation_sha256": "c" * 64,
        },
    }
    first = orchestrator.submit(
        candidate, {"_funnel_method_metric_projection_identity": owner_identity}
    )
    orchestrator.advance(first)
    changed_profile = {
        **owner_identity,
        "selected_source": {
            **owner_identity["selected_source"],
            "projection_vector_ref": {
                "artifact_id": "sha256:" + "a" * 64,
                "manifest_profile_sha256": "sha256:" + "d" * 64,
            },
        },
    }
    second = orchestrator.submit(
        candidate, {"_funnel_method_metric_projection_identity": changed_profile}
    )

    assert second is not first
    orchestrator.advance(second)
    assert stage.calls == 2


def test_ephemeral_basis_is_not_stored_or_exported_with_funnel_ticket() -> None:
    """Stage intake receives the basis, while ticket copies and exports omit it."""
    stage = _CountingStage()
    orchestrator = FunnelOrchestrator([stage])
    basis = object()
    ticket = orchestrator.submit(
        {"candidate_id": "method-metric-ticket-capability"},
        {
            "_funnel_method_metric_projection_basis": basis,
            "_funnel_method_metric_score_required": True,
            "_funnel_method_metric_projection_identity": {
                "resolved_status": "selected",
                "vector_ref": "selected-ref-fingerprint",
            },
        },
    )

    assert "_funnel_method_metric_projection_basis" not in ticket.context
    assert ticket._method_metric_projection_basis is basis
    orchestrator.advance(ticket)
    assert stage.received_basis is basis
    assert "_method_metric_projection_basis" not in asdict(ticket)
    assert "_funnel_method_metric_projection_basis" not in asdict(ticket)["context"]
    assert getattr(copy(ticket), "_method_metric_projection_basis", None) is None
    assert getattr(deepcopy(ticket), "_method_metric_projection_basis", None) is None
    with pytest.raises(TypeError, match="explicit bounded work-packet serializer"):
        pickle.dumps(ticket)
