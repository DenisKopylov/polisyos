"""Game/mechanism-design contracts for strategic policy authoring."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from polisyos.ir._internal.validation import ensure_finite_numeric, ensure_unique_ids
from polisyos.ir.governance.mechanism_semantics import MechanismSemanticsSpec
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel


class MechanismGameRepresentation(str, Enum):
    """Supported mechanism/game representations for governance artifacts."""

    NORMAL_FORM = "normal_form"
    EXTENSIVE_FORM = "extensive_form"
    BAYESIAN = "bayesian"


class MechanismConstraintType(str, Enum):
    """Mechanism-design properties disclosed by the policy author."""

    DOMINANT_STRATEGY_IC = "dominant_strategy_ic"
    BAYESIAN_IC = "bayesian_ic"
    EX_POST_IR = "ex_post_ir"
    EX_INTERIM_IR = "ex_interim_ir"
    BUDGET_BALANCE = "budget_balance"
    REVENUE_MONOTONICITY = "revenue_monotonicity"


class RepeatedGameHorizon(str, Enum):
    """Repeated-game horizon semantics."""

    ONE_SHOT = "one_shot"
    FINITE = "finite"
    INFINITE = "infinite"


class BayesianTypeSpec(KernelModel):
    """Private-type support for one strategic participant."""

    player_id: str = Field(..., pattern=ID_PATTERN)
    type_space: tuple[str, ...] = Field(..., min_length=1)
    prior_probabilities: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_type_support(self) -> BayesianTypeSpec:
        ensure_unique_ids(self.type_space, key_fn=lambda item: item, label="bayesian type")
        if self.prior_probabilities:
            if set(self.prior_probabilities) != set(self.type_space):
                raise ValueError("prior_probabilities must match type_space exactly")
            total = 0.0
            for key, value in self.prior_probabilities.items():
                ensure_finite_numeric(value, field_name=f"prior_probabilities.{key}")
                numeric = float(value)
                if numeric < 0.0:
                    raise ValueError("prior probabilities must be non-negative")
                total += numeric
            if abs(total - 1.0) > 1e-6:
                raise ValueError("prior probabilities must sum to 1.0")
        return self


class ExtensiveFormNode(KernelModel):
    """One node in an extensive-form policy/mechanism game."""

    node_id: str = Field(..., pattern=ID_PATTERN)
    actor_id: str | None = Field(None, pattern=ID_PATTERN)
    parent_node_id: str | None = Field(None, pattern=ID_PATTERN)
    information_set_id: str | None = Field(None, pattern=ID_PATTERN)
    available_actions: tuple[str, ...] = ()
    chance_probabilities: dict[str, float] | None = None
    terminal_payoffs: dict[str, float] | None = None

    @model_validator(mode="after")
    def validate_node(self) -> ExtensiveFormNode:
        if self.parent_node_id == self.node_id:
            raise ValueError("parent_node_id cannot equal node_id")
        if self.terminal_payoffs is not None:
            if self.available_actions:
                raise ValueError("terminal nodes cannot declare available_actions")
            if self.chance_probabilities is not None:
                raise ValueError("terminal nodes cannot declare chance_probabilities")
            for player_id, payoff in self.terminal_payoffs.items():
                if not player_id:
                    raise ValueError("terminal payoff player ids must be non-empty")
                ensure_finite_numeric(payoff, field_name=f"terminal_payoffs.{player_id}")
            return self
        if not self.available_actions:
            raise ValueError("non-terminal nodes require available_actions")
        ensure_unique_ids(
            self.available_actions,
            key_fn=lambda item: item,
            label="extensive form action",
        )
        if self.chance_probabilities is not None:
            if self.actor_id is not None:
                raise ValueError("chance nodes cannot declare actor_id")
            if set(self.chance_probabilities) != set(self.available_actions):
                raise ValueError("chance_probabilities must match available_actions exactly")
            total = 0.0
            for action, probability in self.chance_probabilities.items():
                ensure_finite_numeric(
                    probability,
                    field_name=f"chance_probabilities.{action}",
                )
                numeric = float(probability)
                if numeric < 0.0:
                    raise ValueError("chance probabilities must be non-negative")
                total += numeric
            if abs(total - 1.0) > 1e-6:
                raise ValueError("chance probabilities must sum to 1.0")
        elif self.actor_id is None:
            raise ValueError("decision nodes require actor_id when not chance-controlled")
        return self


class RepeatedGameMetadata(KernelModel):
    """Repeated-game metadata layered on top of one-shot mechanism design."""

    horizon: RepeatedGameHorizon = RepeatedGameHorizon.ONE_SHOT
    n_rounds: int | None = Field(None, ge=1)
    discount_factor: float | None = Field(None, ge=0.0, le=1.0)
    public_signal_fields: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_repeated_game(self) -> RepeatedGameMetadata:
        if self.horizon is RepeatedGameHorizon.ONE_SHOT:
            if self.n_rounds is not None or self.discount_factor is not None:
                raise ValueError(
                    "one-shot repeated-game metadata cannot declare rounds/discount_factor"
                )
        elif self.horizon is RepeatedGameHorizon.FINITE:
            if self.n_rounds is None:
                raise ValueError("finite repeated games require n_rounds")
        elif self.discount_factor is None:
            raise ValueError("infinite repeated games require discount_factor")
        return self


class MechanismDesignConstraint(KernelModel):
    """One incentive-compatibility or participation constraint."""

    constraint_id: str = Field(..., pattern=ID_PATTERN)
    constraint_type: MechanismConstraintType
    applies_to_players: tuple[str, ...] = ()
    tolerance: float | None = Field(None, ge=0.0)
    notes: tuple[str, ...] = ()


class MechanismDesignSpec(KernelModel):
    """Richer strategic/mechanism-design metadata for a policy surface."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    design_id: str = Field(..., pattern=ID_PATTERN)
    representation: MechanismGameRepresentation
    players: tuple[str, ...] = Field(..., min_length=1)
    mechanism_ids: tuple[str, ...] = ()
    action_spaces: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    extensive_form_nodes: list[ExtensiveFormNode] = Field(default_factory=list)
    bayesian_types: list[BayesianTypeSpec] = Field(default_factory=list)
    semantics: MechanismSemanticsSpec | None = None
    constraints: list[MechanismDesignConstraint] = Field(default_factory=list)
    repeated_game: RepeatedGameMetadata | None = None
    objective: str | None = Field(None, max_length=240)

    @model_validator(mode="after")
    def validate_design(self) -> MechanismDesignSpec:
        ensure_unique_ids(self.players, key_fn=lambda item: item, label="mechanism player")
        if set(self.action_spaces) != set(self.players):
            raise ValueError("action_spaces must match players exactly")
        for player_id, actions in self.action_spaces.items():
            if not actions:
                raise ValueError(f"action_spaces.{player_id} must be non-empty")
            ensure_unique_ids(
                actions,
                key_fn=lambda item: item,
                label=f"action_spaces.{player_id}",
            )

        ensure_unique_ids(
            self.constraints,
            key_fn=lambda item: item.constraint_id,
            label="mechanism design constraint_id",
        )
        for constraint in self.constraints:
            unknown_players = set(constraint.applies_to_players) - set(self.players)
            if unknown_players:
                raise ValueError(
                    f"constraint '{constraint.constraint_id}' references unknown players "
                    f"{sorted(unknown_players)}"
                )

        if self.representation is MechanismGameRepresentation.EXTENSIVE_FORM:
            if not self.extensive_form_nodes:
                raise ValueError("extensive_form representation requires extensive_form_nodes")
            ensure_unique_ids(
                self.extensive_form_nodes,
                key_fn=lambda item: item.node_id,
                label="extensive form node_id",
            )
            node_ids = {node.node_id for node in self.extensive_form_nodes}
            for node in self.extensive_form_nodes:
                if node.parent_node_id is not None and node.parent_node_id not in node_ids:
                    raise ValueError(
                        f"extensive form node '{node.node_id}' references unknown parent_node_id"
                    )
                if node.actor_id is not None and node.actor_id not in self.players:
                    raise ValueError(
                        f"extensive form node '{node.node_id}' references unknown actor_id"
                    )
        elif self.extensive_form_nodes:
            raise ValueError("extensive_form_nodes are only valid for extensive_form games")

        if self.representation is MechanismGameRepresentation.BAYESIAN:
            if not self.bayesian_types:
                raise ValueError("bayesian representation requires bayesian_types")
            ensure_unique_ids(
                self.bayesian_types,
                key_fn=lambda item: item.player_id,
                label="bayesian player_id",
            )
            if {item.player_id for item in self.bayesian_types} != set(self.players):
                raise ValueError("bayesian_types must match players exactly")
        elif self.bayesian_types:
            raise ValueError("bayesian_types are only valid for bayesian games")

        if self.semantics is not None:
            self.semantics.validate_against_declared_structure(
                players=self.players,
                action_spaces=self.action_spaces,
                type_spaces={item.player_id: item.type_space for item in self.bayesian_types},
            )
        return self


__all__ = [
    "BayesianTypeSpec",
    "ExtensiveFormNode",
    "MechanismConstraintType",
    "MechanismDesignConstraint",
    "MechanismDesignSpec",
    "MechanismGameRepresentation",
    "MechanismSemanticsSpec",
    "RepeatedGameHorizon",
    "RepeatedGameMetadata",
]
