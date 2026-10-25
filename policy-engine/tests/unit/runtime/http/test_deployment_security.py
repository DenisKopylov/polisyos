"""Focused behavioral tests for runtime deployment security."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.runtime.http.test_runtime_deployment_security import (
    _config_mapping,
    _deployment_security_module,
)


def test_deployment_security_config_is_strict_and_typed(tmp_path: Path) -> None:
    security = _deployment_security_module()
    config = security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))

    assert len(config.service_principals) == 1
    grant = config.service_principals[0]
    assert type(grant) is security.ServicePrincipalGrant
    assert {permission.value for permission in grant.permissions} == {
        "runs.launch",
        "runs.view",
    }
    assert type(config.identity_verifier.provenance) is security.VerifierProvenance
    assert type(config.step_up_verifier.provenance) is security.VerifierProvenance
    runtime = security.build_deployment_security(config)
    assert type(runtime.identity_provider) is security.DeploymentIdentityProvider
    assert runtime.identity_provider.deployment_provenance.reference == (
        "POLISYOS_RUNTIME_IDENTITY_VERIFIER"
    )
    assert runtime.step_up_verifier.deployment_provenance.reference == (
        "POLISYOS_RUNTIME_STEP_UP_VERIFIER"
    )

    malformed = _config_mapping(tmp_path)
    malformed["unexpected"] = True
    with pytest.raises((TypeError, ValueError)):
        security.DeploymentSecurityConfig.from_mapping(malformed)
