"""Configured epoch queries reach promotion consumers without widening their grammar."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core import artifacts, contracts
from polisyos.runtime.quality.epoch_deployment import build_epoch_deployment
from polisyos.runtime.quality.open_world_risk import PromotionRuntime, PromotionRuntimeBatch
from polisyos.runtime.quality.semantic_epoch import SemanticEpochService
from tests.unit.runtime.quality.test_open_world_risk import _problem, _summary


def _consume_both_queries(runtime: PromotionRuntime, service: SemanticEpochService) -> None:
    calls = []
    original = service.qualify_chronology_query

    def observe(*, query):
        calls.append(query)
        return original(query=query)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(service, "qualify_chronology_query", observe)
        batch = runtime._prepare_completed_generation(problem=_problem(), summaries=(_summary(),))
        assert isinstance(batch, PromotionRuntimeBatch)
        assert len(calls) == 1
        subject = runtime.epoch_subject_authority.persist_for_n9(
            bound_member_ref=batch.contexts.ordered_bound_members[0].bound_member_ref
        )
        result = runtime.epoch_validity_gate.reconcile_before_n9(subject_ref=subject.subject_ref)
        assert len(calls) == 2
        assert calls[0] == calls[1]
        assert result.status == "not_established"
        assert result.code == "policy_admission_missing"


@pytest.mark.parametrize("composition", ["constructor", "installation"])
def test_configured_service_is_consumed_by_query_owner_and_pre_n9_gate(
    tmp_path: Path,
    composition: str,
) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    service = SemanticEpochService.for_deployment_policy_query(
        artifact_store=store, deployment=build_epoch_deployment(None)
    )
    if composition == "constructor":
        runtime = PromotionRuntime(store=store, semantic_epoch_service=service)
    else:
        runtime = PromotionRuntime(store=store)
        runtime.configure_semantic_epoch_service(semantic_epoch_service=service)
    _consume_both_queries(runtime, service)


def test_configured_positive_carrier_still_hits_unchanged_ep_d03_refusal(tmp_path: Path) -> None:
    from tests.unit.runtime.quality.test_epoch_deployment import _policy_configuration

    config, case = _policy_configuration(tmp_path)
    owner = build_epoch_deployment(config, native_policy_verifier=case.owner_verifier)
    service = SemanticEpochService.for_deployment_policy_query(
        artifact_store=case.store, deployment=owner
    )
    positive = service.qualify_chronology_query(query=case.query)
    assert isinstance(positive, contracts.NativeProjectionCustodyGap)
    runtime = PromotionRuntime(store=case.store, semantic_epoch_service=service)
    calls = []

    def supply_positive_carrier(*, query):
        # This is an actual qualified fixture carrier. It deliberately cannot
        # establish the promotion query's still-undecided positive semantics.
        calls.append(query)
        return positive

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(service, "qualify_chronology_query", supply_positive_carrier)
        with pytest.raises(ValueError, match="epoch_policy_missing_result_not_established"):
            runtime._prepare_completed_generation(problem=_problem(), summaries=(_summary(),))
    assert len(calls) == 1


def test_deployment_install_routes_temporal_epoch_service_to_promotion(tmp_path: Path) -> None:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.deployment_security import (
        DeploymentSecurityConfig,
        build_deployment_security,
    )
    from tests.unit.runtime.http.test_runtime_deployment_security import _config_mapping

    deployment = build_deployment_security(
        DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    app = create_runtime_api_app(cas_root=tmp_path / "cas", deployment_security=deployment)
    container = app.state.runtime_container
    _consume_both_queries(
        container.promotion_runtime, container.runtime_api_context.temporal._semantic_epoch_service
    )
