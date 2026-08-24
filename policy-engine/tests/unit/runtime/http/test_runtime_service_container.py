"""Composition-root witnesses for the DS9 human-decision service."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import resolve_human_decision_service
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
