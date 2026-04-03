"""Environment-driven configuration for Sigstore-backed SLSA attestation workflows."""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.env_parsing import parse_bool, parse_float, parse_int


class SlsaMode(str, Enum):
    """Slsa mode public type."""
    OFF = "off"
    LOCAL = "local"
    PRIVATE = "private"
    PUBLIC = "public"


class SlsaPolicy(str, Enum):
    """Whether SLSA signing is optional or must succeed before a run is accepted."""
    BEST_EFFORT = "best_effort"
    REQUIRED = "required"


class SLSAConfig(BaseModel):
    """Configuration for SLSA attestation signing + transparency logging."""

    model_config = ConfigDict(extra="forbid")

    mode: SlsaMode = SlsaMode.OFF
    policy: SlsaPolicy = SlsaPolicy.BEST_EFFORT

    fulcio_url: str = "https://fulcio.sigstore.dev"
    rekor_url: str = "https://rekor.sigstore.dev"

    oidc_issuer: str = ""
    oidc_client_id: str = "polisyos-scientist"
    oidc_token_env: str = "POLISYOS_SLSA_OIDC_TOKEN"
    oidc_subject_fallback: str = "system@local"

    timeout_seconds: float = 30.0
    max_retries: int = 2

    local_transparency_log: Path = Field(
        default=Path(".polisyos/security/slsa/transparency.jsonl")
    )

    retain_ed25519_signatures: bool = True

    @property
    def enabled(self) -> bool:
        return self.mode != SlsaMode.OFF

    @property
    def require_success(self) -> bool:
        return self.policy == SlsaPolicy.REQUIRED

    @classmethod
    def from_env(cls) -> "SLSAConfig":
        mode_raw = os.getenv("POLISYOS_SLSA_MODE", SlsaMode.OFF.value).strip().lower()
        policy_raw = os.getenv(
            "POLISYOS_SLSA_POLICY", SlsaPolicy.BEST_EFFORT.value
        ).strip().lower()

        try:
            mode = SlsaMode(mode_raw)
        except ValueError:
            mode = SlsaMode.OFF

        try:
            policy = SlsaPolicy(policy_raw)
        except ValueError:
            policy = SlsaPolicy.BEST_EFFORT

        return cls(
            mode=mode,
            policy=policy,
            fulcio_url=os.getenv("POLISYOS_SLSA_FULCIO_URL", "https://fulcio.sigstore.dev"),
            rekor_url=os.getenv("POLISYOS_SLSA_REKOR_URL", "https://rekor.sigstore.dev"),
            oidc_issuer=os.getenv("POLISYOS_SLSA_OIDC_ISSUER", ""),
            oidc_client_id=os.getenv("POLISYOS_SLSA_OIDC_CLIENT_ID", "polisyos-scientist"),
            oidc_token_env=os.getenv("POLISYOS_SLSA_OIDC_TOKEN_ENV", "POLISYOS_SLSA_OIDC_TOKEN"),
            oidc_subject_fallback=os.getenv("POLISYOS_SLSA_OIDC_SUBJECT", "system@local"),
            timeout_seconds=parse_float(os.getenv("POLISYOS_SLSA_TIMEOUT_SECONDS"), 30.0),
            max_retries=max(0, parse_int(os.getenv("POLISYOS_SLSA_MAX_RETRIES"), 2)),
            local_transparency_log=Path(
                os.getenv(
                    "POLISYOS_SLSA_LOCAL_TRANSPARENCY_LOG",
                    ".polisyos/security/slsa/transparency.jsonl",
                )
            ),
            retain_ed25519_signatures=parse_bool(
                os.getenv("POLISYOS_SLSA_RETAIN_ED25519"), True,
            ),
        )

    def with_overrides(
        self,
        *,
        mode: str | None = None,
        policy: str | None = None,
    ) -> "SLSAConfig":
        resolved_mode = self.mode
        resolved_policy = self.policy

        if mode:
            resolved_mode = SlsaMode(mode.strip().lower())
        if policy:
            resolved_policy = SlsaPolicy(policy.strip().lower())

        return self.model_copy(update={"mode": resolved_mode, "policy": resolved_policy})
