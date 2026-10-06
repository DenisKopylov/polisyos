from __future__ import annotations


def test_profiles_shim_points_to_core() -> None:
    from polisyos.core.governance.profiles import ValidationProfile as CoreValidationProfile
    from polisyos.scientist.governance.profiles import ValidationProfile as LegacyValidationProfile

    assert LegacyValidationProfile is CoreValidationProfile


def test_governance_facade_and_configured_registry_run_core_passes() -> None:
    """Builtin workflow loading and validation keep Core class identity and behavior."""

    from polisyos.core.governance.passes.base import PassContext as CorePassContext
    from polisyos.core.governance.passes.legal_pass import LegalPass as CoreLegalPass
    from polisyos.core.governance.passes.safety_pass import SafetyPass as CoreSafetyPass
    from polisyos.core.governance.profiles import ValidationProfile
    from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.loading.norm_pack import NormPack, NormRule, RuleType
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.governance.pass_registry import load_governance_passes
    from polisyos.scientist.governance.passes import (
        LegalPass as FacadeLegalPass,
    )
    from polisyos.scientist.governance.passes import (
        PassContext as FacadePassContext,
    )
    from polisyos.scientist.governance.passes import (
        SafetyPass as FacadeSafetyPass,
    )

    assert FacadePassContext is CorePassContext
    assert FacadeLegalPass is CoreLegalPass
    assert FacadeSafetyPass is CoreSafetyPass

    configured = {validator.pass_id: validator for validator in load_governance_passes()}
    legal = configured["legal"]
    safety = configured["safety"]
    assert type(legal) is CoreLegalPass
    assert type(safety) is CoreSafetyPass

    norm_pack = NormPack(
        pack_id="hyg02.norm_pack",
        jurisdiction="UA",
        effective_date="2026-01-01",
        norms=[
            NormRule(
                norm_id="hyg02.norm",
                rule_type=RuleType.OBLIGATION,
                description="The configured legal pass must produce its Core issue.",
            )
        ],
    )
    legal_context = CorePassContext(
        ir=None,
        state={"norm_pack": norm_pack},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="hyg02-legal",
    )
    legal_issues = legal.validate(legal_context)
    assert len(legal_issues) == 1
    assert legal_issues[0].code == "NORM_NOT_IMPLEMENTED"

    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="hyg02_problem", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="hyg02_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="hyg02_intervention",
                    kind="unregistered_mechanism",
                    target=SelectorPredicate(field="id", operator="==", value="all"),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="hyg02_model",
            data_snapshot_ref="sha256:" + "0" * 64,
        ),
    )
    safety_context = CorePassContext(
        ir=trinity,
        state={},
        registry_bundle={"mechanisms": {"known_mechanism": {}}},
        profile=ValidationProfile.strict(),
        run_id="hyg02-safety",
    )
    safety_issues = safety.validate(safety_context)
    assert len(safety_issues) == 1
    assert safety_issues[0].code == "UNKNOWN_MECHANISM"


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
