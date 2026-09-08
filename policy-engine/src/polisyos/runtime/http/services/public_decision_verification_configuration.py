"""Load explicit deployment trust for verification reports, never policy issuance."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts
from polisyos.runtime.http.services.public_decision_verification import (
    PublicDecisionVerificationService,
    PublicDecisionVerificationTrustedKey,
)


class _KeyConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    public_key_path: str = Field(min_length=1)
    issuer_id: str = Field(min_length=1)
    purposes: list[str] = Field(min_length=1)
    revoked: bool = False


class _Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    issuer_id: str = Field(min_length=1)
    private_key_path: str | None = None
    trusted_keys: list[_KeyConfiguration]


def build_public_decision_verification_service(
    *, cas_root: Path
) -> PublicDecisionVerificationService:
    """Load server-owned key policy; absent configuration leaves issuance unavailable.

    ``POLISYOS_PUBLIC_VERIFICATION_CONFIG`` names a JSON file with an issuer ID,
    optional private key path, and explicit public-key/issuer/purpose bindings.
    Relative key paths resolve against that file. Malformed configured trust fails
    startup; keys are never generated or accepted from a request.
    """
    root = cas_root / "runtime" / "public-verification"
    configured_path = os.environ.get("POLISYOS_PUBLIC_VERIFICATION_CONFIG")
    signer = None
    trusted_keys: tuple[PublicDecisionVerificationTrustedKey, ...] = ()
    issuer_id = "unconfigured-verification-report-issuer"
    if configured_path is not None:
        path = Path(configured_path).resolve(strict=True)
        config = _Configuration.model_validate_json(path.read_bytes())
        issuer_id = config.issuer_id
        if config.private_key_path is not None:
            private_path = path.parent / config.private_key_path
            permitted, _ = artifacts.ensure_private_key_permissions(private_path)
            if not permitted:
                raise ValueError("public verification private key permissions invalid")
            signer = artifacts.Ed25519Signer.from_path(private_path)
        trusted_keys = tuple(
            PublicDecisionVerificationTrustedKey(
                public_key_pem=(path.parent / key.public_key_path).read_bytes(),
                issuer_id=key.issuer_id,
                purposes=frozenset(key.purposes),
                revoked=key.revoked,
            )
            for key in config.trusted_keys
        )
    return PublicDecisionVerificationService(
        store=artifacts.FileSystemCAS(root / "cas"),
        index_root=root / "issued",
        issuer_id=issuer_id,
        signer=signer,
        trusted_keys=trusted_keys,
    )
