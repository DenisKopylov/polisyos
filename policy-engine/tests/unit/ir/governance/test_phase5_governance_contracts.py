from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.ir.governance.game_design import (
    BayesianTypeSpec,
    MechanismConstraintType,
    MechanismDesignConstraint,
    MechanismDesignSpec,
    MechanismGameRepresentation,
    RepeatedGameHorizon,
    RepeatedGameMetadata,
)
from polisyos.ir.governance.policy_composition import (
    PolicyCompatibilityConstraint,
    PolicyCompatibilityMode,
    PolicyCompositionPlan,
    PolicyLayerLevel,
    PolicyLayerSpec,
    PolicyOverrideMode,
    PolicyOverrideRule,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, MechanismBinding, PolicySpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import (
    SelectorAggregate,
    SelectorAggregationFunction,
    SelectorAll,
    SelectorPredicate,
    SelectorQuantifier,
    SelectorQuantifierKind,
    SelectorTemporalOperator,
    SelectorTemporalPredicate,
)
from polisyos.ir.governance.temporal_logic import (
    TemporalAll,
    TemporalAny,
    TemporalAtom,
    TemporalBinaryFormula,
    TemporalBinaryOperator,
    TemporalBoundedFormula,
    TemporalEvaluationScope,
    TemporalExecutionSemantics,
    TemporalLogicFamily,
    TemporalNot,
    TemporalPathFormula,
    TemporalPathQuantifier,
    TemporalPolicyConstraint,
    TemporalUnaryFormula,
    TemporalUnaryOperator,
)
from polisyos.ir.model_layer.types import SelectorOperator


def _policy_target() -> SelectorAll:
    return SelectorAll(
        clauses=[
            SelectorQuantifier(
                quantifier=SelectorQuantifierKind.AT_LEAST,
                collection_field="household.members",
                threshold=2,
                clause=SelectorPredicate(
                    field="age",
                    operator=SelectorOperator.GREATER_EQUAL,
                    value=18,
                ),
            ),
            SelectorAggregate(
                aggregation=SelectorAggregationFunction.COUNT,
                collection_field="benefits",
                operator=SelectorOperator.GREATER_EQUAL,
                value=1,
            ),
            SelectorTemporalPredicate(
                temporal_operator=SelectorTemporalOperator.ALWAYS_WITHIN,
                clause=SelectorPredicate(
                    field="compliance.score",
                    operator=SelectorOperator.GREATER_EQUAL,
                    value="0.8",
                ),
                upper_bound=4,
                clock_field="tx_time",
            ),
        ]
    )


def test_policy_spec_accepts_phase5_governance_surfaces() -> None:
    policy = PolicySpec(
        policy_id="phase5_policy",
        interventions=[
            InterventionSpec(
                intervention_id="targeted_subsidy",
                kind="eligibility_mechanism",
                target=_policy_target(),
                schedule=ScheduleSpec(start_step=0, duration_steps=3),
                params={"benefit_rate": Decimal("0.12")},
            )
        ],
        mechanism_bindings=[
            MechanismBinding(
                binding_id="eligibility_binding",
                mechanism_id="eligibility_mechanism",
                intervention_ids=["targeted_subsidy"],
            )
        ],
        temporal_constraints=[
            TemporalPolicyConstraint(
                constraint_id="sustained_compliance",
                logic_family=TemporalLogicFamily.LTL,
                execution_semantics=TemporalExecutionSemantics.FINITE_TRACE,
                evaluation_scope=TemporalEvaluationScope.COMPLIANCE_TRACE,
                formula=TemporalUnaryFormula(
                    operator=TemporalUnaryOperator.ALWAYS,
                    clause=TemporalAtom(
                        metric_path="metrics.compliance_rate",
                        operator=SelectorOperator.GREATER_EQUAL,
                        value="0.9",
                    ),
                ),
            )
        ],
        composition=PolicyCompositionPlan(
            composition_id="ua_procurement_stack",
            base_policy_id="phase5_policy",
            layers=[
                PolicyLayerSpec(
                    layer_id="fed",
                    level=PolicyLayerLevel.FEDERAL,
                    jurisdiction_id="ua",
                    policy_id="phase5_policy",
                    version_tag="1.0.0",
                    precedence=0,
                ),
                PolicyLayerSpec(
                    layer_id="city",
                    level=PolicyLayerLevel.LOCAL,
                    jurisdiction_id="kyiv",
                    policy_id="phase5_city_policy",
                    version_tag="1.0.0",
                    precedence=1,
                ),
            ],
            override_rules=[
                PolicyOverrideRule(
                    override_id="city_threshold_override",
                    source_layer_id="city",
                    target_layer_id="fed",
                    target_intervention_id="targeted_subsidy",
                    mode=PolicyOverrideMode.REPLACE,
                    justification="Local procurement threshold differs from national baseline.",
                )
            ],
            compatibility_constraints=[
                PolicyCompatibilityConstraint(
                    constraint_id="city_requires_federal_guardrail",
                    higher_layer_id="fed",
                    lower_layer_id="city",
                    mode=PolicyCompatibilityMode.REQUIRES_APPROVAL,
                    required_policy_refs=("phase5_policy",),
                )
            ],
        ),
        mechanism_design=MechanismDesignSpec(
            design_id="subsidy_screening_game",
            representation=MechanismGameRepresentation.BAYESIAN,
            players=("agency", "provider"),
            mechanism_ids=("eligibility_mechanism",),
            action_spaces={
                "agency": ("approve", "reject"),
                "provider": ("truthful", "misreport"),
            },
            bayesian_types=[
                BayesianTypeSpec(
                    player_id="agency",
                    type_space=("strict", "lenient"),
                    prior_probabilities={"strict": 0.5, "lenient": 0.5},
                ),
                BayesianTypeSpec(
                    player_id="provider",
                    type_space=("eligible", "ineligible"),
                    prior_probabilities={"eligible": 0.7, "ineligible": 0.3},
                ),
            ],
            constraints=[
                MechanismDesignConstraint(
                    constraint_id="bic_truthfulness",
                    constraint_type=MechanismConstraintType.BAYESIAN_IC,
                    applies_to_players=("provider",),
                ),
                MechanismDesignConstraint(
                    constraint_id="participation",
                    constraint_type=MechanismConstraintType.EX_INTERIM_IR,
                    applies_to_players=("provider",),
                ),
            ],
            repeated_game=RepeatedGameMetadata(
                horizon=RepeatedGameHorizon.FINITE,
                n_rounds=6,
            ),
        ),
    )

    restored = PolicySpec.model_validate_json(policy.model_dump_json())
    assert restored.model_dump(mode="json") == policy.model_dump(mode="json")


def test_temporal_policy_constraint_rejects_family_semantics_mismatch() -> None:
    with pytest.raises(ValueError, match="bounded temporal operators are only allowed for MTL"):
        TemporalPolicyConstraint(
            constraint_id="bad_ltl_window",
            logic_family=TemporalLogicFamily.LTL,
            execution_semantics=TemporalExecutionSemantics.FINITE_TRACE,
            evaluation_scope=TemporalEvaluationScope.COMPLIANCE_TRACE,
            formula=TemporalBoundedFormula(
                operator="always",
                lower_bound=0,
                upper_bound=3,
                clause=TemporalAtom(proposition_id="is_compliant"),
            ),
        )


def _temporal_atom_mapping(proposition_id: str) -> dict[str, str]:
    return {"kind": "atom", "proposition_id": proposition_id}


def _mtl_constraint_mapping(formula: dict[str, object]) -> dict[str, object]:
    return {
        "constraint_id": "mapped_temporal_constraint",
        "logic_family": "mtl",
        "execution_semantics": "windowed_trace",
        "evaluation_scope": "compliance_trace",
        "finite_horizon": 6,
        "formula": formula,
    }


def test_temporal_walkers_preserve_discriminated_mapping_branches() -> None:
    formula_mapping: dict[str, object] = {
        "kind": "all_of",
        "clauses": [
            {
                "kind": "not",
                "clause": _temporal_atom_mapping("not_atom"),
            },
            {
                "kind": "any_of",
                "clauses": [
                    {
                        "kind": "unary",
                        "operator": "eventually",
                        "clause": _temporal_atom_mapping("unary_atom"),
                    },
                    {
                        "kind": "binary",
                        "operator": "implies",
                        "left": _temporal_atom_mapping("binary_left"),
                        "right": {
                            "kind": "bounded",
                            "operator": "until",
                            "lower_bound": 1,
                            "upper_bound": 4,
                            "left": _temporal_atom_mapping("until_left"),
                            "right": _temporal_atom_mapping("until_right"),
                        },
                    },
                ],
            },
            {
                "kind": "bounded",
                "operator": "always",
                "upper_bound": 4,
                "clause": _temporal_atom_mapping("bounded_atom"),
            },
        ],
    }

    constraint = TemporalPolicyConstraint.model_validate(_mtl_constraint_mapping(formula_mapping))

    assert isinstance(constraint.formula, TemporalAll)
    assert isinstance(constraint.formula.clauses[0], TemporalNot)
    disjunction = constraint.formula.clauses[1]
    assert isinstance(disjunction, TemporalAny)
    assert isinstance(disjunction.clauses[0], TemporalUnaryFormula)
    implication = disjunction.clauses[1]
    assert isinstance(implication, TemporalBinaryFormula)
    assert implication.operator is TemporalBinaryOperator.IMPLIES
    assert isinstance(implication.right, TemporalBoundedFormula)
    assert isinstance(constraint.formula.clauses[2], TemporalBoundedFormula)

    with pytest.raises(
        ValueError,
        match="bounded temporal operators are only allowed for MTL",
    ):
        TemporalPolicyConstraint.model_validate(
            {
                "constraint_id": "nested_bounded_ltl",
                "logic_family": "ltl",
                "execution_semantics": "finite_trace",
                "evaluation_scope": "compliance_trace",
                "formula": formula_mapping,
            }
        )


def test_temporal_formula_depth_limit_uses_recursive_typed_children() -> None:
    formula: dict[str, object] = _temporal_atom_mapping("depth_atom")
    for _ in range(23):
        formula = {"kind": "not", "clause": formula}

    at_limit = TemporalPolicyConstraint.model_validate(
        {
            "constraint_id": "temporal_depth_at_limit",
            "logic_family": "ltl",
            "execution_semantics": "finite_trace",
            "evaluation_scope": "compliance_trace",
            "formula": formula,
        }
    )
    assert isinstance(at_limit.formula, TemporalNot)

    too_deep = {"kind": "not", "clause": formula}
    with pytest.raises(ValueError, match="temporal formula depth 25 exceeds limit 24"):
        TemporalPolicyConstraint.model_validate(
            {
                "constraint_id": "temporal_depth_over_limit",
                "logic_family": "ltl",
                "execution_semantics": "finite_trace",
                "evaluation_scope": "compliance_trace",
                "formula": too_deep,
            }
        )


def test_temporal_formula_node_limit_counts_nested_siblings() -> None:
    groups = [
        {
            "kind": "all_of",
            "clauses": [
                _temporal_atom_mapping(f"group_{group}_atom_{item}")
                for item in range(30 if group == 3 else 31)
            ],
        }
        for group in range(4)
    ]
    at_limit_formula: dict[str, object] = {"kind": "all_of", "clauses": groups}
    at_limit = TemporalPolicyConstraint.model_validate(_mtl_constraint_mapping(at_limit_formula))
    assert isinstance(at_limit.formula, TemporalAll)

    over_limit_formula: dict[str, object] = {
        "kind": "all_of",
        "clauses": [
            *groups,
            _temporal_atom_mapping("extra_node"),
        ],
    }
    with pytest.raises(ValueError, match="temporal formula nodes 129 exceeds limit 128"):
        TemporalPolicyConstraint.model_validate(_mtl_constraint_mapping(over_limit_formula))


def test_ctl_path_quantifier_is_counted_through_mapping_children() -> None:
    constraint = TemporalPolicyConstraint.model_validate(
        {
            "constraint_id": "mapped_ctl_path",
            "logic_family": "ctl",
            "execution_semantics": "branching_tree",
            "evaluation_scope": "branching_forecast",
            "formula": {
                "kind": "all_of",
                "clauses": [
                    {
                        "kind": "path",
                        "quantifier": "for_all_paths",
                        "clause": _temporal_atom_mapping("ctl_atom"),
                    }
                ],
            },
        }
    )
    assert isinstance(constraint.formula, TemporalAll)
    path_formula = constraint.formula.clauses[0]
    assert isinstance(path_formula, TemporalPathFormula)
    assert path_formula.quantifier is TemporalPathQuantifier.FOR_ALL_PATHS


def test_selector_temporal_predicate_requires_bounds_for_windowed_operator() -> None:
    with pytest.raises(ValueError, match="requires upper_bound"):
        SelectorTemporalPredicate(
            temporal_operator=SelectorTemporalOperator.EVENTUALLY_WITHIN,
            clause=SelectorPredicate(
                field="compliance.score",
                operator=SelectorOperator.GREATER_EQUAL,
                value="0.5",
            ),
        )
