from __future__ import annotations

import pytest

from polisyos.core.security.exceptions import IdentityVerificationError
from polisyos.core.security.identity import (
    PolicyOSRole,
    SPIFFEIdentityProvider,
    infer_mfa_verified,
    map_roles_from_claims,
)


def test_map_roles_from_claims_combines_realm_and_client_roles() -> None:
    payload = {
        "realm_access": {"roles": ["polisyos_analyst"]},
        "resource_access": {"polisyos-web": {"roles": ["tenant_admin"]}},
    }

    roles = map_roles_from_claims(payload, client_id="polisyos-web")

    assert roles == frozenset({PolicyOSRole.ANALYST, PolicyOSRole.ADMIN})


def test_map_roles_defaults_to_viewer() -> None:
    roles = map_roles_from_claims({}, client_id="polisyos-web")
    assert roles == frozenset({PolicyOSRole.VIEWER})


def test_infer_mfa_verified_from_amr_and_acr() -> None:
    assert infer_mfa_verified({"amr": ["webauthn"]}) is True
    assert infer_mfa_verified({"acr": "2"}) is True
    assert infer_mfa_verified({"amr": ["pwd"]}) is False


def test_parse_spiffe_id_valid() -> None:
    parsed = SPIFFEIdentityProvider._parse_spiffe_id(  # noqa: SLF001 - intentional unit test
        "spiffe://polisyos.io/cell/cell-a/svc/scientist"
    )

    assert parsed["trust_domain"] == "polisyos.io"
    assert parsed["cell_id"] == "cell-a"
    assert parsed["service_name"] == "scientist"


def test_parse_spiffe_id_rejects_invalid() -> None:
    with pytest.raises(IdentityVerificationError):
        SPIFFEIdentityProvider._parse_spiffe_id("invalid-spiffe")  # noqa: SLF001
