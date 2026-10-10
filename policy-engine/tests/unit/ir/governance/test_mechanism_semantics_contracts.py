from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.ir.governance.game_design import (
    BayesianTypeSpec,
    MechanismConstraintType,
    MechanismDesignConstraint,
    MechanismDesignSpec,
    MechanismGameRepresentation,
)
from polisyos.ir.governance.mechanism_semantics import (
    CycMonAllocationPointSpec,
    CycMonGridSemanticsSpec,
    CycMonTypePointSpec,
    Envelope1DPointSpec,
    Envelope1DSemanticsSpec,
    FiniteOutcomeRuleEntry,
    FiniteOutcomeSpec,
    FiniteValueTableEntry,
    MechanismSemanticFragment,
    MechanismSemanticsSpec,
    MechanismUtilityModelKind,
    MechanismUtilityModelSpec,
)


def _base_semantics(*, high_payment: str = "5") -> MechanismSemanticsSpec:
    return MechanismSemanticsSpec(
        semantics_id="buyer_direct_semantics",
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


def test_mechanism_design_accepts_exact_finite_semantics() -> None:
    design = MechanismDesignSpec(
        design_id="direct_buyer_game",
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
        semantics=_base_semantics(),
    )

    assert design.semantics is not None
    assert design.semantics.allocation_rule[1].payments_by_player["buyer"] == "5"


def test_mechanism_design_rejects_direct_semantics_when_actions_do_not_match_types() -> None:
    with pytest.raises(ValidationError, match="action_spaces to match bayesian type labels"):
        MechanismDesignSpec(
            design_id="bad_direct_game",
            representation=MechanismGameRepresentation.BAYESIAN,
            players=("buyer",),
            mechanism_ids=("posted_price",),
            action_spaces={"buyer": ("truthful", "misreport")},
            bayesian_types=[
                BayesianTypeSpec(
                    player_id="buyer",
                    type_space=("low", "high"),
                    prior_probabilities={"low": 0.5, "high": 0.5},
                )
            ],
            semantics=_base_semantics(),
        )


def test_mechanism_semantics_rejects_float_exact_numbers() -> None:
    with pytest.raises(ValidationError, match="float forbidden"):
        MechanismSemanticsSpec(
            semantics_id="bad_numeric_semantics",
            finite_outcomes=[FiniteOutcomeSpec(outcome_id="win")],
            allocation_rule=[
                FiniteOutcomeRuleEntry(
                    report_profile={"buyer": "high"},
                    outcome_id="win",
                    payments_by_player={"buyer": 0.5},
                )
            ],
            utility_model=MechanismUtilityModelSpec(
                kind=MechanismUtilityModelKind.QUASI_LINEAR_SCALAR,
                value_table=[
                    FiniteValueTableEntry(
                        player_id="buyer",
                        type_label="high",
                        outcome_values={"win": "1"},
                    )
                ],
            ),
        )


def test_mechanism_design_accepts_envelope_1d_semantics() -> None:
    design = MechanismDesignSpec(
        design_id="buyer_envelope_game",
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
        semantics=MechanismSemanticsSpec(
            semantics_id="buyer_envelope_semantics",
            fragment=MechanismSemanticFragment.ENVELOPE_1D,
            envelope_1d=Envelope1DSemanticsSpec(
                player_id="buyer",
                points=[
                    Envelope1DPointSpec(type_label="low", type_value="1", allocation="0"),
                    Envelope1DPointSpec(type_label="high", type_value="3", allocation="1"),
                ],
            ),
        ),
    )

    assert design.semantics is not None
    assert design.semantics.fragment is MechanismSemanticFragment.ENVELOPE_1D


def test_mechanism_design_accepts_cycmon_grid_semantics() -> None:
    design = MechanismDesignSpec(
        design_id="buyer_cycmon_game",
        representation=MechanismGameRepresentation.BAYESIAN,
        players=("buyer",),
        mechanism_ids=("bundle",),
        action_spaces={"buyer": ("t00", "t10")},
        bayesian_types=[
            BayesianTypeSpec(
                player_id="buyer",
                type_space=("t00", "t10"),
                prior_probabilities={"t00": 0.5, "t10": 0.5},
            )
        ],
        semantics=MechanismSemanticsSpec(
            semantics_id="buyer_cycmon_semantics",
            fragment=MechanismSemanticFragment.CYCMON_GRID,
            cycmon_grid=CycMonGridSemanticsSpec(
                player_id="buyer",
                type_points=[
                    CycMonTypePointSpec(type_label="t00", coords=("0", "0")),
                    CycMonTypePointSpec(type_label="t10", coords=("1", "0")),
                ],
                allocation_points=[
                    CycMonAllocationPointSpec(type_label="t00", allocation=("0", "0")),
                    CycMonAllocationPointSpec(type_label="t10", allocation=("1", "0")),
                ],
            ),
        ),
    )

    assert design.semantics is not None
    assert design.semantics.fragment is MechanismSemanticFragment.CYCMON_GRID


def test_mechanism_semantics_rejects_mixed_fragment_payloads() -> None:
    with pytest.raises(ValidationError, match="cannot also declare envelope_1d"):
        MechanismSemanticsSpec(
            semantics_id="mixed_semantics",
            finite_outcomes=[FiniteOutcomeSpec(outcome_id="win")],
            allocation_rule=[
                FiniteOutcomeRuleEntry(report_profile={"buyer": "high"}, outcome_id="win")
            ],
            utility_model=MechanismUtilityModelSpec(
                kind=MechanismUtilityModelKind.QUASI_LINEAR_SCALAR,
                value_table=[
                    FiniteValueTableEntry(
                        player_id="buyer",
                        type_label="high",
                        outcome_values={"win": "1"},
                    )
                ],
            ),
            envelope_1d=Envelope1DSemanticsSpec(
                player_id="buyer",
                points=[Envelope1DPointSpec(type_label="high", type_value="1", allocation="1")],
            ),
        )
