from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.governance.game_design import (
    BayesianTypeSpec,
    MechanismConstraintType,
    MechanismDesignConstraint,
    MechanismDesignSpec,
    MechanismGameRepresentation,
)
from polisyos.ir.governance.mechanism_semantics import (
    FiniteOutcomeRuleEntry,
    FiniteOutcomeSpec,
    FiniteValueTableEntry,
    MechanismSemanticsSpec,
    MechanismUtilityModelKind,
    MechanismUtilityModelSpec,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, MechanismBinding, PolicySpec
from polisyos.ir.governance.problem_frame import (
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
)
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import FidelityLevel, ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_layer.types import OptimizationDirection
from polisyos.scientist.governance.passes.incentive_compatibility_pass import (
    IncentiveCompatibilityPass,
)


def _bundle(*, high_payment: str | None) -> TrinityBundle:
    design = MechanismDesignSpec(
        design_id="single_buyer",
        representation=MechanismGameRepresentation.BAYESIAN,
        players=("buyer",),
        mechanism_ids=("posted_price",),
        action_spaces={"buyer": ("low", "high")},
        bayesian_types=[
            BayesianTypeSpec(
                player_id="buyer",
                type_space=("low", "high"),
                prior_probabilities={"low": 0.5, "high": 0.5},
            )
        ],
        constraints=[
            MechanismDesignConstraint(
                constraint_id="buyer_dsic",
                constraint_type=MechanismConstraintType.DOMINANT_STRATEGY_IC,
                applies_to_players=("buyer",),
            )
        ],
        semantics=(
            None
            if high_payment is None
            else MechanismSemanticsSpec(
                semantics_id="single_buyer_semantics",
                finite_outcomes=[
                    FiniteOutcomeSpec(outcome_id="lose", allocation_by_player={"buyer": "lose"}),
                    FiniteOutcomeSpec(outcome_id="win", allocation_by_player={"buyer": "win"}),
                ],
                allocation_rule=[
                    FiniteOutcomeRuleEntry(report_profile={"buyer": "low"}, outcome_id="lose"),
                    FiniteOutcomeRuleEntry(
                        report_profile={"buyer": "high"},
                        outcome_id="win",
                        payments_by_player={"buyer": high_payment},
                    ),
                ],
                utility_model=MechanismUtilityModelSpec(
                    kind=MechanismUtilityModelKind.QUASI_LINEAR_SCALAR,
                    value_table=[
                        FiniteValueTableEntry(
                            player_id="buyer",
                            type_label="low",
                            outcome_values={"lose": "0", "win": "1"},
                        ),
                        FiniteValueTableEntry(
                            player_id="buyer",
                            type_label="high",
                            outcome_values={"lose": "0", "win": "10"},
                        ),
                    ],
                ),
            )
        ),
    )
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="ic_problem",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="welfare",
                    metric_id="social_welfare",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
        ),
        policy_spec=PolicySpec(
            policy_id="ic_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="posted_price",
                    kind="posted_price",
                    target=SelectorPredicate(field="income", operator=">=", value=Decimal("0")),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"price": Decimal("5")},
                )
            ],
            mechanism_bindings=[
                MechanismBinding(
                    binding_id="posted_price_binding",
                    mechanism_id="posted_price",
                    intervention_ids=["posted_price"],
                )
            ],
            mechanism_design=design,
        ),
        model_spec=ModelSpec(
            model_id="ic_model",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            fidelity_level=FidelityLevel.HYBRID,
        ),
    )


def _family_tax_bundle() -> TrinityBundle:
    mechanism_id = "bayes_tax_pl_v1"
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="ic_problem",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="welfare",
                    metric_id="social_welfare",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
        ),
        policy_spec=PolicySpec(
            policy_id="ic_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="income_tax",
                    kind="income_tax_piecewise_linear",
                    target=SelectorPredicate(field="income", operator=">=", value=Decimal("0")),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={
                        "type_grid": [Decimal("1.0"), Decimal("1.5"), Decimal("2.0")],
                        "earnings_schedule": [
                            Decimal("0.85"),
                            Decimal("1.20"),
                            Decimal("1.55"),
                        ],
                        "prior_weights": [
                            Decimal("0.25"),
                            Decimal("0.50"),
                            Decimal("0.25"),
                        ],
                        "u0": Decimal("0"),
                    },
                )
            ],
            mechanism_bindings=[
                MechanismBinding(
                    binding_id="income_tax_binding",
                    mechanism_id=mechanism_id,
                    intervention_ids=["income_tax"],
                )
            ],
            mechanism_design=MechanismDesignSpec(
                design_id="tax_design",
                representation=MechanismGameRepresentation.BAYESIAN,
                players=("taxpayer",),
                mechanism_ids=(mechanism_id,),
                action_spaces={"taxpayer": ("low", "middle", "high")},
                bayesian_types=[
                    BayesianTypeSpec(
                        player_id="taxpayer",
                        type_space=("low", "middle", "high"),
                        prior_probabilities={"low": 1 / 3, "middle": 1 / 3, "high": 1 / 3},
                    )
                ],
                constraints=[
                    MechanismDesignConstraint(
                        constraint_id="taxpayer_bic",
                        constraint_type=MechanismConstraintType.BAYESIAN_IC,
                        applies_to_players=("taxpayer",),
                    )
                ],
            ),
        ),
        model_spec=ModelSpec(
            model_id="ic_model",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            fidelity_level=FidelityLevel.HYBRID,
        ),
    )


def test_incentive_compatibility_pass_writes_artifacts_for_positive_claim(tmp_path) -> None:
    bundle = _bundle(high_payment="5")
    store = FileSystemCAS(tmp_path / "cas")
    ctx = PassContext(
        ir=bundle,
        state={"_store": store, "artifacts_index": {}},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="run_ic_positive",
    )

    issues = IncentiveCompatibilityPass().validate(ctx)

    assert issues == []
    assert "dominant_strategy_ic_report_ref" in ctx.state["artifacts_index"]
    assert "dominant_strategy_ic_certificate_ref" in ctx.state["artifacts_index"]


def test_incentive_compatibility_pass_blocks_false_claim_in_strict_mode(tmp_path) -> None:
    bundle = _bundle(high_payment="0")
    store = FileSystemCAS(tmp_path / "cas")
    ctx = PassContext(
        ir=bundle,
        state={"_store": store, "artifacts_index": {}},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="run_ic_negative",
    )

    issues = IncentiveCompatibilityPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "INCENTIVE_COMPATIBILITY_VIOLATED"
    assert "dominant_strategy_ic_negative_certificate_ref" in ctx.state["artifacts_index"]


def test_incentive_compatibility_pass_warns_when_claim_is_uncertified_in_mvp_mode() -> None:
    ctx = PassContext(
        ir=_bundle(high_payment=None),
        state={"artifacts_index": {}},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="run_ic_uncertified",
    )

    issues = IncentiveCompatibilityPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "INCENTIVE_COMPATIBILITY_UNCERTIFIED"


def test_incentive_compatibility_pass_blocks_false_ex_post_ir_claim(tmp_path) -> None:
    bundle = _bundle(high_payment="12")
    policy_spec = bundle.policy_spec.model_copy(
        update={
            "mechanism_design": bundle.policy_spec.mechanism_design.model_copy(
                update={
                    "constraints": [
                        MechanismDesignConstraint(
                            constraint_id="buyer_ir",
                            constraint_type=MechanismConstraintType.EX_POST_IR,
                            applies_to_players=("buyer",),
                        )
                    ]
                }
            )
        }
    )
    bundle = bundle.model_copy(update={"policy_spec": policy_spec})
    store = FileSystemCAS(tmp_path / "cas")
    ctx = PassContext(
        ir=bundle,
        state={"_store": store, "artifacts_index": {}},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="run_ir_negative",
    )

    issues = IncentiveCompatibilityPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "INCENTIVE_COMPATIBILITY_VIOLATED"
    assert "ex_post_ir_negative_certificate_ref" in ctx.state["artifacts_index"]


def test_incentive_compatibility_pass_indexes_family_sidecar_artifacts(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ctx = PassContext(
        ir=_family_tax_bundle(),
        state={"_store": store, "artifacts_index": {}},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="run_family_tax",
    )

    issues = IncentiveCompatibilityPass().validate(ctx)

    assert issues == []
    artifacts_index = ctx.state["artifacts_index"]
    assert "bayesian_ic_report_ref" in artifacts_index
    assert "bayesian_ic_certificate_ref" in artifacts_index
    assert "bayesian_ic_mechanism_family_spec_ref" in artifacts_index
    assert "bayesian_ic_mechanism_ic_certificate_ref" in artifacts_index
    assert "bayesian_ic_mechanism_welfare_loss_bound_ref" in artifacts_index
