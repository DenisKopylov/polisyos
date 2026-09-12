"""Exercise privileged issuance propagation and real tenant ownership boundaries."""

from __future__ import annotations

from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.quality.epoch_certificate_issuance import (
    DecisionPacketEpochIssuanceOwner,
    NoEpochCertificateIssuanceInputResolver,
)
from polisyos.runtime.quality.epoch_transition_verification import CanonicalEpochTransitionVerifier
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tests.unit.runtime.http.test_runtime_deployment_security import (
    _config_mapping,
    _deployment_security_module,
)


@pytest.mark.parametrize("configured", [False, True])
def test_container_propagates_exact_owner_to_actual_legacy_launch(
    tmp_path, monkeypatch, configured: bool
) -> None:
    """Removing either Runtime propagation link loses the configured concrete owner."""

    resolver = NoEpochCertificateIssuanceInputResolver() if configured else None
    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path)),
        epoch_certificate_issuance_input_resolver=resolver,
    )
    app = create_runtime_api_app(cas_root=tmp_path / "cas", deployment_security=runtime)
    captured: dict[str, Any] = {}

    def capture_launch(payload, **kwargs):
        captured.update(payload=payload, **kwargs)

    monkeypatch.setattr("polisyos.scientist.api.run_experiment", capture_launch)
    with TestClient(app) as client:
        container = cast("Any", client.app).state.runtime_container
        owner = container.epoch_certificate_issuance_owner
        assert type(owner) is DecisionPacketEpochIssuanceOwner
        assert owner.store is container.runtime_api_context.store
        assert container.control_service._epoch_certificate_issuance_owner is owner
        if configured:
            assert owner._input_resolver is resolver
        assert owner.prepare(run_id="absent-source", invocation_input_refs=()).status == (
            "not_established"
        )
        payload = {"run_id": "actual-legacy-launch", "params": {"epoch_owner": "candidate"}}
        container.control_service._run_legacy_scientist_workflow(payload)
        assert captured["epoch_certificate_issuance_owner"] is owner
        assert captured["store"] is owner.store
        assert captured["payload"] == payload
        assert "epoch_certificate_issuance_owner" not in captured["payload"]


def test_startup_verifier_provenance_is_readable_in_actual_tenant_scope(tmp_path) -> None:
    """Startup construction must not leave its real evidence unowned at request time."""

    store = artifacts.FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()

    class MissingOrigin:
        def resolve_admitted_origin_for_transition(self, **kwargs):
            raise ValueError("origin absent")

    verifier = CanonicalEpochTransitionVerifier(
        store=store,
        origins=cast("Any", MissingOrigin()),
        decision_validity_owner=DecisionValidityService(store),
    )
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        transition = store.put_bytes(
            b"refused candidate",
            artifacts.ArtifactWriteOptions(kind="test.transition", media_type="text/plain"),
        )
        with pytest.raises(ValueError):
            verifier.verify(
                transition_artifact_ref=transition,
                requested_query_context_ref="sha256:" + "a" * 64,
                expected_authority_purpose="decision_validity_epoch_transition",
            )
        assert store.get_bytes(verifier.verifier_provenance_ref.artifact_id)


def test_issuance_inventory_is_partitioned_by_active_tenant(tmp_path, monkeypatch) -> None:
    """One tenant's admitted rows cannot poison another tenant's owner denominator."""

    from tests.unit.scientist.validation.test_epoch_certificate_issuance import (
        _configured_fixture,
        _run_canonical_node,
    )

    filesystem_cas = artifacts.FileSystemCAS
    monkeypatch.setattr(
        artifacts,
        "FileSystemCAS",
        lambda root: filesystem_cas(root).with_ambient_ownership_enforcement(),
    )
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        _, store, owner, _, source, _ = _configured_fixture(tmp_path)
        _run_canonical_node(tmp_path, store, owner, source)
        assert owner.enumerate_registered_issuances()
    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
        assert owner.enumerate_registered_issuances() == ()
