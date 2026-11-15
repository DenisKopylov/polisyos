"""Read selection/owner controls; real public custody is covered by retained HTTP.

The Control doubles exercise the existing canonical alias resolver, not an
institutional authority claim. The final case uses the actual custody producer.
"""

from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from fastapi import Request

from polisyos.core import artifacts
from polisyos.core.security import AccessScope, PIIAccessLevel, PolicyOSRole
from polisyos.runtime.http import resource_binding
from polisyos.runtime.http.authorization import (
    ActionPermissionVerification,
    principal_from_access_scope,
)
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.routes.human_decisions import _RECORD_AUTHZ
from polisyos.runtime.http.services.human_decisions import HumanDecisionOperationalResolutionError
from tests.unit.runtime.http.test_human_decision_control_run_binding import (
    _ControlOwner,
    _SourceRunIndex,
)
from tests.unit.runtime.http.test_human_decision_recovery import _case, _create

RECORD = "sha256:" + "c" * 64
PROFILE = "sha256:" + "d" * 64


def _bound_read(monkeypatch, *, selected=True, use_alias=True):
    control = _ControlOwner()

    class AliasIndex(_SourceRunIndex):
        def get_run(self, run_id):
            if run_id == control.job.run_id:
                raise KeyError(run_id)
            return super().get_run(run_id)

    ctx = SimpleNamespace(run_index=AliasIndex(control.terminal))
    monkeypatch.setattr(resource_binding, "_require_runtime_context", lambda request: ctx)
    monkeypatch.setattr(resource_binding, "resolve_control_service", lambda request: control)
    scope = AccessScope(
        tenant_id="tenant-1",
        cell_id="cell-1",
        principal_type="user",
        user_sub="record-reviewer",
        roles=frozenset({PolicyOSRole.ANALYST}),
        max_pii_tier=PIIAccessLevel.HIGH,
        mfa_verified=True,
        jwt_jti="record-reviewer-read",
    )
    run_id = control.job.run_id if use_alias else control.terminal.run_id
    query = {"record_ref": RECORD}
    if selected:
        query["manifest_profile_sha256"] = PROFILE
    path = f"/api/v1/runs/{run_id}/human-decisions"
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "path_params": {"run_id": run_id},
            "query_string": urlencode(query).encode(),
            "headers": [],
        }
    )
    request.state.authz_effective_scope = scope
    subject, tenant, jwt_id, roles = principal_from_access_scope(scope)
    requirement = _RECORD_AUTHZ.requirement
    request.state.action_permission_verification = ActionPermissionVerification(
        requirement=requirement,
        subject=subject,
        tenant_id=tenant,
        jwt_id=jwt_id,
        roles=roles,
        authorization_source="record-owner-selector-component",
        granted_permissions=(requirement.permission,),
    )
    bound = resource_binding.bind_authorization_resource(request, requirement, b"")
    request.state.authz_bound_resource = bound
    return request, ctx, control, run_id, bound


def _reopen(request, ctx, run_id, *, record=RECORD, profile=PROFILE):
    return resource_binding.human_decision_record_owner_from_bound_request(
        request,
        ctx=ctx,
        run_id=run_id,
        record_ref=record,
        manifest_profile_sha256=profile,
    )


def test_known_record_read_keeps_exact_profile_and_control_core_owner(monkeypatch):
    request, ctx, control, run_id, bound = _bound_read(monkeypatch)
    owner, selected = _reopen(request, ctx, run_id)
    assert run_id == control.job.run_id
    assert owner.run_id == control.terminal.run_id != run_id
    assert selected == artifacts.ArtifactRef(
        artifact_id=RECORD,
        kind="runtime_quality.agent_action_human_decision",
        media_type="application/json",
        manifest_profile_sha256=PROFILE,
    )
    context = resource_binding.get_bound_resource_context(
        request, expected_kind="runtime.human_decision.record.v1"
    )
    assert context["record_ref"] == selected.model_dump(mode="json")
    assert context["owned_run_binding"]["control_run_id"] == run_id
    assert dict(bound.canonical_selectors)["manifest_profile_sha256"] == f'"{PROFILE}"'
    assert control.source_calls == 2


@pytest.mark.parametrize("changed", ["record", "profile"])
def test_post_policy_record_or_profile_substitution_refuses(monkeypatch, changed):
    request, ctx, control, run_id, _bound = _bound_read(monkeypatch)
    kwargs = {changed: "sha256:" + "f" * 64}
    with pytest.raises(RuntimeHTTPError) as error:
        _reopen(request, ctx, run_id, **kwargs)
    assert error.value.code == "authorization_binding_context_mismatch"
    assert control.source_calls == 1


def test_post_policy_control_source_removal_refuses(monkeypatch):
    request, ctx, control, run_id, _bound = _bound_read(monkeypatch)
    control.source_error = ValueError("actual selected Core source unavailable")
    with pytest.raises(RuntimeHTTPError) as error:
        _reopen(request, ctx, run_id)
    assert error.value.code == "authorization_binding_context_mismatch"
    assert control.source_calls == 2


def test_unselected_core_read_preserves_the_legacy_binding(monkeypatch):
    request, ctx, control, run_id, bound = _bound_read(monkeypatch, selected=False, use_alias=False)
    owner, selected = _reopen(request, ctx, run_id, profile=None)
    assert owner is None
    assert selected == RECORD
    assert bound.resolved_context is None and bound.resolved_context_kind is None
    assert dict(bound.canonical_selectors) == {
        "run_id": f'"{run_id}"',
        "record_ref": f'"{RECORD}"',
    }
    assert control.source_calls == 0


def test_actual_custody_reader_never_substitutes_default_for_a_missing_profile(tmp_path):
    fixture, command = _case(tmp_path)
    receipt = _create(fixture, command)
    selected = artifacts.artifact_ref_for_manifest(fixture.store.get_manifest(receipt.record_ref))
    assert selected.manifest_profile_sha256 is not None
    read = fixture.service.read_record(
        selected, tenant_id=command.gate_input.tenant_id, run_id=command.gate_input.run_id
    )
    assert read == receipt.record
    foreign = selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
    with pytest.raises(HumanDecisionOperationalResolutionError):
        fixture.service.read_record(
            foreign, tenant_id=command.gate_input.tenant_id, run_id=command.gate_input.run_id
        )
    assert (
        fixture.service.read_record(
            selected, tenant_id=command.gate_input.tenant_id, run_id=command.gate_input.run_id
        )
        == read
    )
