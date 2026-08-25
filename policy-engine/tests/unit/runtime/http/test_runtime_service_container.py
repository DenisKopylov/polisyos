"""Composition-root witnesses for the DS9 human-decision service."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import (
    resolve_human_decision_service,
    resolve_production_approval_resolver,
)
from polisyos.runtime.http.services.human_decisions import HumanDecisionService
from tests.unit.runtime.http.test_runtime_deployment_security import (
    _config_mapping,
    _config_mapping_with_human_decision_custody,
    _deployment_security_module,
)


def _runtime(raw: dict[str, object]) -> Any:
    security = _deployment_security_module()
    return security.build_deployment_security(security.DeploymentSecurityConfig.from_mapping(raw))


def test_runtime_container_installs_exact_human_decision_dependencies(
    tmp_path,
) -> None:
    runtime = _runtime(_config_mapping_with_human_decision_custody(tmp_path / "configured"))
    app = create_runtime_api_app(
        cas_root=tmp_path / "cas",
        deployment_security=runtime,
    )

    with TestClient(app) as client:
        container = cast("Any", client.app).state.runtime_container
        service = resolve_human_decision_service(client.app)
        assert type(service) is HumanDecisionService
        assert service is container.human_decision_service
        assert service.custody is runtime.human_decision_custody
        assert service.authority_sink is container.control_service.human_decision_sink
        dependency = client.get("/health").json()["lifecycle"]["dependencies"][
            "human_decision_service"
        ]
        assert dependency == {
            "status": "ready",
            "type": "HumanDecisionService",
        }


def test_runtime_container_surfaces_typed_unavailable_custody_without_failing_health(
    tmp_path,
) -> None:
    config_root = tmp_path / "unconfigured"
    config_root.mkdir()
    runtime = _runtime(_config_mapping(config_root))
    app = create_runtime_api_app(
        cas_root=tmp_path / "cas",
        deployment_security=runtime,
    )

    with TestClient(app) as client:
        service = resolve_human_decision_service(client.app)
        assert type(service) is HumanDecisionService
        assert service.available is False
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["lifecycle"]["dependencies"]["human_decision_service"] == {
            "status": "unavailable",
            "type": "HumanDecisionService",
            "reason": "DS9-DECISION-PRODUCER-MISSING",
        }


def test_runtime_container_rejects_custody_alias_substitution(tmp_path) -> None:
    installed = _runtime(_config_mapping_with_human_decision_custody(tmp_path / "installed"))
    replacement = _runtime(_config_mapping_with_human_decision_custody(tmp_path / "replacement"))
    app = create_runtime_api_app(
        cas_root=tmp_path / "cas",
        deployment_security=installed,
    )
    container = cast("Any", app).state.runtime_container
    container.runtime_security = replace(
        container.runtime_security,
        human_decision_custody=replacement.human_decision_custody,
    )

    with pytest.raises(TypeError, match="custody identity changed"), TestClient(app):
        pass


def test_runtime_container_installs_registered_attested_production_approval_resolver(
    tmp_path,
) -> None:
    runtime = _runtime(_config_mapping_with_human_decision_custody(tmp_path / "resolver"))
    app = create_runtime_api_app(
        cas_root=tmp_path / "cas",
        deployment_security=runtime,
    )

    with TestClient(app) as client:
        container = cast("Any", client.app).state.runtime_container
        resolver = resolve_production_approval_resolver(client.app)

        assert resolver is container.production_approval_resolver
        assert resolver is not None
        assert resolver.issuer_epoch == runtime.human_decision_custody.verifier_epoch


def test_runtime_container_rejects_cross_app_production_approval_resolver(
    tmp_path,
) -> None:
    first_runtime = _runtime(_config_mapping_with_human_decision_custody(tmp_path / "first"))
    second_runtime = _runtime(_config_mapping_with_human_decision_custody(tmp_path / "second"))
    first_app = create_runtime_api_app(
        cas_root=tmp_path / "first-cas",
        deployment_security=first_runtime,
    )
    second_app = create_runtime_api_app(
        cas_root=tmp_path / "second-cas",
        deployment_security=second_runtime,
    )

    with TestClient(first_app) as first_client, TestClient(second_app) as second_client:
        first_container = cast("Any", first_client.app).state.runtime_container
        second_resolver = resolve_production_approval_resolver(second_client.app)
        assert second_resolver is not None

        first_container.production_approval_resolver = second_resolver

        assert resolve_production_approval_resolver(first_client.app) is None


def test_operational_consumers_reject_unregistered_exact_resolver(tmp_path) -> None:
    runtime = _runtime(_config_mapping_with_human_decision_custody(tmp_path / "unregistered"))
    app = create_runtime_api_app(
        cas_root=tmp_path / "cas",
        deployment_security=runtime,
    )

    with TestClient(app) as client:
        service = resolve_human_decision_service(client.app)
        from polisyos.runtime.quality.approval import (
            ProductionApprovalResolutionError,
            _issue_production_decision_packet_resolver,
        )

        unregistered = _issue_production_decision_packet_resolver(
            service,
            expected_audience="polisyos-runtime",
            deployment_security=runtime,
        )
        with pytest.raises(ProductionApprovalResolutionError) as exc_info:
            unregistered.require_currentness(
                packet_ref="sha256:" + "0" * 64,
                tenant_id="tenant-a",
                run_id="run-a",
                expected_consumer="polisyos.runtime.quality.agent_action_authority",
                expected_audience="polisyos-runtime",
            )
        assert exc_info.value.code == "DS9-APPROVAL-RESOLVER-UNATTESTED"


def test_registered_resolver_rejects_consumer_constructed_issuance_grant(tmp_path) -> None:
    runtime = _runtime(_config_mapping_with_human_decision_custody(tmp_path / "forged-grant"))
    app = create_runtime_api_app(
        cas_root=tmp_path / "cas",
        deployment_security=runtime,
    )

    with TestClient(app) as client:
        resolver = resolve_production_approval_resolver(client.app)
        assert resolver is not None
        from polisyos.runtime.quality import approval

        forged = approval._ResolvedProductionApprovalAuthority(
            inputs=cast("Any", object()),
            expected_consumer="polisyos.runtime.production_approval",
            expected_audience="polisyos-runtime",
            evaluated_at=cast("Any", object()),
            _seal=approval._RESOLVER_SEAL,
        )
        with pytest.raises(approval.ProductionApprovalResolutionError) as exc_info:
            resolver.persist_authorized_packet(
                forged,
                cast("Any", object()),
                write_context=object(),
            )
        assert exc_info.value.code == "DS9-RAW-APPROVAL-NOT-AUTHORITY"
