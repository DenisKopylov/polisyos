"""The governed deployment owns acquisition trust, including its empty state."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.runtime.http import deployment_security as security
from tests.unit.runtime.http.test_runtime_deployment_security import _config_mapping


def test_empty_acquisition_deployment_is_constructed_and_attested(tmp_path: Path) -> None:
    first = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    second = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    slot = first.acquisition_authority
    assert not slot.authority_available
    assert slot.config.mandates == ()
    assert slot.signing_slot.signer is None
    assert first.acquisition_authority is not second.acquisition_authority
    object.__setattr__(first, "acquisition_authority", second.acquisition_authority)
    with pytest.raises(TypeError, match="factory attestation is invalid"):
        security.require_factory_produced_deployment_security(first)


def test_acquisition_key_trust_drift_invalidates_deployment(tmp_path: Path) -> None:
    from polisyos.core.artifacts.signing import KeyPair

    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    runtime.acquisition_authority.verifier.add_trusted_key(
        KeyPair.generate().public_key, identity="self-appointed-mandate-authority"
    )
    with pytest.raises(TypeError, match="factory attestation is invalid"):
        security.require_factory_produced_deployment_security(runtime)
