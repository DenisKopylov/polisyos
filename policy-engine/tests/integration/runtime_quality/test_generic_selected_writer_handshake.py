"""Actual worker-scoped generic writes must return their selected CAS views."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.integration.runtime_quality.test_generic_n4_child_profile_set_served import (
    controlled_candidate_gateway as _gateway_fixture,
)

controlled_candidate_gateway = _gateway_fixture


class _StopAfterWriterControlsError(Exception):
    """End the real worker after the handoff checks, before N4 or N5 work."""


class _SuppressSelectedReply:
    """Delegate actual CAS writes, suppressing only a selected return value."""

    def __init__(self, delegate: Any, kind: str) -> None:
        self.delegate = delegate
        self.kind = kind
        self.written_refs: list[Any] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    def put_json(
        self,
        obj: Any,
        opts: Any,
        canon_spec: Any = None,
        *,
        return_selected_profile: bool = False,
    ) -> Any:
        ref = self.delegate.put_json(
            obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
        )
        if opts.kind != self.kind:
            return ref
        assert return_selected_profile is True
        assert ref.manifest_profile_sha256 is not None
        self.written_refs.append(ref)
        return ref.model_copy(update={"manifest_profile_sha256": None})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_generic_worker_refuses_suppressed_selected_writer_replies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Actual issued scope and real CAS positive distinguish all three refusals."""
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control import generation_cycle as service_owner
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        CycleSubstrateContextOwnerError,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.generic_n4_served_replay import prepare_generic_n4_served_replay
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    claims = build_fixture_identity_claims()
    assert claims.cell_id is not None
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        controlled_candidate_gateway=controlled_candidate_gateway,
        tenant_id=claims.tenant_id,
        cell_id=claims.cell_id,
        recording_mode="served_tax_global_scalar",
        child_count=1,
        materialize_source_parameters=True,
        synthetic_settled_provider=True,
    )
    original_compiler = service_owner.build_design_problem_from_nl_request

    async def real_compiler(**kwargs: Any) -> Any:
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(service_owner, "build_design_problem_from_nl_request", real_compiler)
    original_handoff = GenericCycleSimulationAdmissionOwner.persist_handoff
    observed: dict[str, Any] = {}

    def check_real_writes(owner: Any, **kwargs: Any) -> Any:
        scope = kwargs["verified_nl_job_scope"]
        assert scope._was_issued_by_verified_nl_execution_owner is True
        handoff = original_handoff(owner, **kwargs)
        assert (
            owner.resolve_handoff(
                handoff=handoff,
                problem=kwargs["problem"],
                verified_nl_job_scope=scope,
                context_owner=kwargs["context_owner"],
                repo_root=kwargs["repo_root"],
            )
            == handoff
        )
        assert all(
            ref is not None and ref.manifest_profile_sha256 is not None
            for ref in (
                handoff.profile_ref,
                handoff.context_job_ref,
                handoff.n4_child_profile_family_ref,
            )
        )
        observed["positive"] = True
        for kind, code in (
            (
                "runtime.quality.cycle_substrate_context_job",
                "cycle_substrate_context_writer_profile_not_established",
            ),
            (
                "runtime.quality.generic_cycle_simulation_profile",
                "generic_cycle_simulation_profile_selected_profile_not_returned",
            ),
            (
                "runtime.quality.generic_cycle_simulation_child_profile_family",
                "generic_cycle_simulation_child_family_selected_profile_not_returned",
            ),
        ):
            writer = _SuppressSelectedReply(owner.store, kind)
            refusing_owner = GenericCycleSimulationAdmissionOwner(
                profiles=owner.profiles, store=writer
            )
            original_context_owner = kwargs["context_owner"]
            context_owner = CycleSubstrateContextArtifactOwner(
                store=writer,
                control_store=original_context_owner._control_store,
                context_admission_verifier=original_context_owner._context_admission_verifier,
            )
            with pytest.raises(CycleSubstrateContextOwnerError) as refused:
                original_handoff(refusing_owner, **{**kwargs, "context_owner": context_owner})
            assert refused.value.code == code
            assert writer.written_refs
            assert all(writer.delegate.verify(ref).ok for ref in writer.written_refs)
            observed[kind] = code
        raise _StopAfterWriterControlsError("generic_selected_writer_controls_complete")

    monkeypatch.setattr(GenericCycleSimulationAdmissionOwner, "persist_handoff", check_real_writes)
    numerical_calls: list[Any] = []
    actual_n5 = JointSimulationHorizonController.run

    def observe_n5(controller: Any, request: Any) -> Any:
        numerical_calls.append(request)
        return actual_n5(controller, request)

    monkeypatch.setattr(JointSimulationHorizonController, "run", observe_n5)
    with TestClient(create_runtime_api_app(**prepared.app_kwargs)) as client:
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": "generic-selected-writer-handshakes"},
            json={**prepared.request_json, "max_iterations": 1},
        )
        assert response.status_code == 200, response.text
        accepted = response.json()
        service = client.app.state._control_service
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=accepted["job_id"],
            )
            == accepted["job_id"]
        )
        job = service._control_store.get_job(accepted["job_id"])
        assert job is not None
        assert observed.get("positive") is True, job.error_message
        assert len(observed) == 4, job.error_message
        assert job.state == "failed"
        assert "generic_selected_writer_controls_complete" in str(job.error_message)
        assert numerical_calls == []
