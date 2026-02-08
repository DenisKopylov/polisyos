from __future__ import annotations

import pytest

from polisyos.core.security.tee import (
    AttestationPolicy,
    AttestationReport,
    AttestationResult,
    AttestationStatus,
    TEEPlatform,
)
from polisyos.core.security.tee_middleware import AttestationDeniedError, TEEGatekeeper


class _StaticVerifier:
    def __init__(self, result: AttestationResult) -> None:
        self.calls = 0
        self._result = result

    def fetch_report(self, *, nonce=None, timeout_seconds=10.0):  # noqa: ANN001, ANN003
        self.calls += 1
        return AttestationReport(
            platform=TEEPlatform.SEV_SNP,
            measurement="m",
            host_data="h",
            guest_svn=1,
            tcb_version=1,
            report_data_hex="",
            signature_validated=True,
        )

    def verify(self, report, policy, *, nonce=None):  # noqa: ANN001
        del report
        del policy
        del nonce
        return self._result


def test_gatekeeper_cache_hit() -> None:
    verifier = _StaticVerifier(
        AttestationResult(status=AttestationStatus.VERIFIED, platform=TEEPlatform.SEV_SNP)
    )
    gatekeeper = TEEGatekeeper(
        cell_tier="dedicated",
        policy=AttestationPolicy(enabled=True, fail_closed=True),
        enforce_tiers=frozenset({"dedicated"}),
        verifier=verifier,
        cache_ttl_seconds=300,
    )

    first = gatekeeper.gate(node_id="n1")
    second = gatekeeper.gate(node_id="n1")

    assert first.status == AttestationStatus.VERIFIED
    assert second.cached is True
    assert verifier.calls == 1


def test_gatekeeper_skip_for_shared_tier() -> None:
    verifier = _StaticVerifier(
        AttestationResult(status=AttestationStatus.VERIFIED, platform=TEEPlatform.SEV_SNP)
    )
    gatekeeper = TEEGatekeeper(
        cell_tier="shared",
        policy=AttestationPolicy(enabled=True, fail_closed=True),
        enforce_tiers=frozenset({"dedicated"}),
        verifier=verifier,
        cache_ttl_seconds=300,
    )

    result = gatekeeper.gate(node_id="n1")
    assert result.status == AttestationStatus.SKIPPED
    assert verifier.calls == 0


def test_gatekeeper_enforce_raises_when_denied() -> None:
    verifier = _StaticVerifier(
        AttestationResult(
            status=AttestationStatus.FAILED,
            platform=TEEPlatform.SEV_SNP,
            errors=["measurement mismatch"],
        )
    )
    gatekeeper = TEEGatekeeper(
        cell_tier="dedicated",
        policy=AttestationPolicy(enabled=True, fail_closed=True),
        enforce_tiers=frozenset({"dedicated"}),
        verifier=verifier,
        cache_ttl_seconds=300,
    )

    with pytest.raises(AttestationDeniedError, match="measurement mismatch"):
        gatekeeper.enforce(node_id="n1")
