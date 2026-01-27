from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.ir.norm_pack import NormPack, NormRule, NormRef, RuleType
from polisyos.scientist.governance.passes.base import (
    PassContext,
    ComplianceIssue,
    IssueSeverity,
)
from polisyos.scientist.governance.passes.legal_pass import LegalPass
from polisyos.scientist.governance.legal.backends.base import RuleBackend
from polisyos.scientist.governance.legal.backends.stub import StubBackend
from polisyos.scientist.governance.profiles import ValidationProfile


@pytest.fixture
def sample_norm_pack() -> NormPack:
    """Create a sample NormPack for testing."""
    return NormPack(
        pack_id="test-pack-001",
        jurisdiction="EU",
        effective_date="2024-01-01",
        norms=[
            NormRule(
                norm_id="GDPR-5-1-a",
                provision_refs=[
                    NormRef(
                        provision_id="Art.5.1.a",
                        source_document="EU/GDPR/2016",
                    )
                ],
                rule_type=RuleType.OBLIGATION,
                description="Data must be processed lawfully",
                backend_refs=["ast", "llm"],
            ),
            NormRule(
                norm_id="GDPR-5-1-b",
                provision_refs=[
                    NormRef(
                        provision_id="Art.5.1.b",
                        source_document="EU/GDPR/2016",
                    )
                ],
                rule_type=RuleType.PROHIBITION,
                description="Purpose limitation",
                backend_refs=["ast"],
            ),
        ],
    )


@pytest.fixture
def fast_ctx(sample_norm_pack: NormPack) -> PassContext:
    """PassContext with FAST profile."""
    return PassContext(
        ir=None,
        state={"norm_pack": sample_norm_pack},
        registry_bundle=None,
        profile=ValidationProfile.fast(),
        run_id="test-fast-001",
    )


@pytest.fixture
def strict_ctx(sample_norm_pack: NormPack) -> PassContext:
    """PassContext with STRICT profile."""
    return PassContext(
        ir=None,
        state={"norm_pack": sample_norm_pack},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="test-strict-001",
    )


def test_legal_pass_calls_injected_backend(strict_ctx: PassContext) -> None:
    """Verify LegalPass delegates to injected backend."""
    mock_backend = MagicMock(spec=RuleBackend)
    mock_backend.backend_id = "mock"
    mock_backend.evaluate.return_value = [
        ComplianceIssue(
            pass_id="legal",
            path=["test"],
            message="Mock issue",
            severity=IssueSeverity.WARNING,
            code="MOCK_001",
        )
    ]

    legal_pass = LegalPass(backend=mock_backend)
    issues = legal_pass.validate(strict_ctx)

    mock_backend.evaluate.assert_called_once()
    assert len(issues) == 1
    assert issues[0].code == "MOCK_001"


def test_legal_pass_skips_in_fast_profile(fast_ctx: PassContext) -> None:
    """LegalPass returns empty in FAST profile."""
    legal_pass = LegalPass()
    issues = legal_pass.validate(fast_ctx)
    assert issues == []


def test_legal_pass_skips_in_mvp_profile(sample_norm_pack: NormPack) -> None:
    """LegalPass returns empty in MVP profile."""
    ctx = PassContext(
        ir=None,
        state={"norm_pack": sample_norm_pack},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="test-mvp-001",
    )
    legal_pass = LegalPass()
    issues = legal_pass.validate(ctx)
    assert issues == []


def test_legal_pass_runs_in_strict_profile(strict_ctx: PassContext) -> None:
    """LegalPass executes in STRICT profile."""
    legal_pass = LegalPass()
    issues = legal_pass.validate(strict_ctx)
    assert len(issues) == 2


def test_legal_pass_force_enabled_runs_in_fast(fast_ctx: PassContext) -> None:
    """enabled=True overrides profile check."""
    legal_pass = LegalPass(enabled=True)
    issues = legal_pass.validate(fast_ctx)
    assert len(issues) == 2


def test_norm_pack_json_roundtrip(sample_norm_pack: NormPack) -> None:
    """NormPack serializes and deserializes correctly."""
    json_str = sample_norm_pack.model_dump_json()
    restored = NormPack.model_validate_json(json_str)

    assert restored.pack_id == sample_norm_pack.pack_id
    assert restored.jurisdiction == sample_norm_pack.jurisdiction
    assert len(restored.norms) == len(sample_norm_pack.norms)
    assert restored.norms[0].norm_id == sample_norm_pack.norms[0].norm_id


def test_norm_pack_dict_roundtrip(sample_norm_pack: NormPack) -> None:
    """NormPack converts to/from dict correctly."""
    data = sample_norm_pack.model_dump()
    restored = NormPack.model_validate(data)
    assert restored == sample_norm_pack


def test_stub_backend_returns_info_issues(sample_norm_pack: NormPack) -> None:
    """StubBackend returns INFO for each norm."""
    backend = StubBackend()
    issues = backend.evaluate(sample_norm_pack, {})

    assert len(issues) == 2
    assert all(i.severity == IssueSeverity.INFO for i in issues)
    assert all(i.code == "NORM_NOT_IMPLEMENTED" for i in issues)


def test_stub_backend_handles_none_norm_pack() -> None:
    """StubBackend returns empty list for None."""
    backend = StubBackend()
    issues = backend.evaluate(None, {})
    assert issues == []


def test_stub_backend_is_runtime_checkable() -> None:
    """StubBackend satisfies RuleBackend protocol."""
    backend = StubBackend()
    assert isinstance(backend, RuleBackend)


def test_legal_pass_properties() -> None:
    """Verify LegalPass metadata properties."""
    legal_pass = LegalPass()
    assert legal_pass.pass_id == "legal"
    assert legal_pass.estimated_cost_ms == 100
    assert legal_pass.requires_data is True
