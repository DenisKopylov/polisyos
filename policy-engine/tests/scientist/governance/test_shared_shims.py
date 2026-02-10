from __future__ import annotations


def test_profiles_shim_points_to_core() -> None:
    from polisyos.core.governance.profiles import ValidationProfile as CoreValidationProfile
    from polisyos.scientist.governance.profiles import ValidationProfile as LegacyValidationProfile

    assert LegacyValidationProfile is CoreValidationProfile


def test_pass_shims_point_to_core() -> None:
    from polisyos.core.governance.passes.base import PassContext as CorePassContext
    from polisyos.core.governance.passes.legal_pass import LegalPass as CoreLegalPass
    from polisyos.core.governance.passes.safety_pass import SafetyPass as CoreSafetyPass
    from polisyos.scientist.governance.passes.base import PassContext as LegacyPassContext
    from polisyos.scientist.governance.passes.legal_pass import LegalPass as LegacyLegalPass
    from polisyos.scientist.governance.passes.safety_pass import SafetyPass as LegacySafetyPass

    assert LegacyPassContext is CorePassContext
    assert LegacyLegalPass is CoreLegalPass
    assert LegacySafetyPass is CoreSafetyPass


def test_legal_backend_shims_point_to_core() -> None:
    from polisyos.core.governance.legal.ast_policy import ASTPolicy as CoreASTPolicy
    from polisyos.core.governance.legal.backends.expr_ast import (
        ExpressionASTBackend as CoreExpressionASTBackend,
    )
    from polisyos.core.governance.legal.backends.stub import StubBackend as CoreStubBackend
    from polisyos.scientist.governance.legal.ast_policy import ASTPolicy as LegacyASTPolicy
    from polisyos.scientist.governance.legal.backends.expr_ast import (
        ExpressionASTBackend as LegacyExpressionASTBackend,
    )
    from polisyos.scientist.governance.legal.backends.stub import StubBackend as LegacyStubBackend

    assert LegacyASTPolicy is CoreASTPolicy
    assert LegacyExpressionASTBackend is CoreExpressionASTBackend
    assert LegacyStubBackend is CoreStubBackend
