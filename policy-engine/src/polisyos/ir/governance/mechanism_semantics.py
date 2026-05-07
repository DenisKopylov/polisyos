"""Typed semantics for machine-checkable mechanism verification."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from fractions import Fraction
from typing import Annotated

from pydantic import BeforeValidator, Field, model_validator

from polisyos.ir._internal.validation import ensure_unique_ids
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel


def _fraction_to_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _coerce_exact_number(value: object) -> str:
    if isinstance(value, bool):
        raise ValueError("bool is not a valid exact numeric value")
    if isinstance(value, float):
        raise ValueError("float forbidden; use int, Decimal, or rational string")
    if isinstance(value, Fraction):
        return _fraction_to_text(value)
    if isinstance(value, Decimal):
        return _fraction_to_text(Fraction(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("exact numeric string cannot be empty")
        try:
            return _fraction_to_text(Fraction(text))
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(
                "exact numeric values must be integers, decimal strings, or rational strings"
            ) from exc
    raise TypeError("exact numeric values must be int, Decimal, Fraction, or str")


ExactNumber = Annotated[str, BeforeValidator(_coerce_exact_number)]


class MechanismSemanticFragment(str, Enum):
    """Supported exact semantic fragments for proof-carrying verification."""

    FINITE_DIRECT = "finite_direct"
    ENVELOPE_1D = "envelope_1d"
    CYCMON_GRID = "cycmon_grid"


class MechanismRevelationMode(str, Enum):
    """Whether the authored mechanism is direct or indirect."""

    DIRECT = "direct"
    INDIRECT = "indirect"


class MechanismOutcomeMode(str, Enum):
    """Whether the reported outcome rule is deterministic or randomized."""

    DETERMINISTIC = "deterministic"
    RANDOMIZED = "randomized"


class MechanismUtilityModelKind(str, Enum):
    """Supported utility semantics for the finite exact MVP."""

    QUASI_LINEAR_SCALAR = "quasi_linear_scalar"
    EXPLICIT_TABLE = "explicit_table"


class MechanismPriorKind(str, Enum):
    """Supported exact prior semantics for finite Bayesian verification."""

    INDEPENDENT_EXACT = "independent_exact"
    JOINT_EXACT_TABLE = "joint_exact_table"


class FiniteOutcomeSpec(KernelModel):
    """One named outcome in the exact finite mechanism codomain."""

    outcome_id: str = Field(..., pattern=ID_PATTERN)
    allocation_by_player: dict[str, str] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()


class FiniteOutcomeRuleEntry(KernelModel):
    """Map one report profile to one deterministic outcome plus exact payments."""

    report_profile: dict[str, str]
    outcome_id: str = Field(..., pattern=ID_PATTERN)
    payments_by_player: dict[str, ExactNumber] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()


class FiniteValueTableEntry(KernelModel):
    """Exact per-outcome value semantics for one player/type pair."""

    player_id: str = Field(..., pattern=ID_PATTERN)
    type_label: str = Field(..., min_length=1)
    outcome_values: dict[str, ExactNumber]


class FiniteUtilityTableEntry(KernelModel):
    """Exact utility for one player, true type, and full report profile."""

    player_id: str = Field(..., pattern=ID_PATTERN)
    true_type: str = Field(..., min_length=1)
    report_profile: dict[str, str]
    utility: ExactNumber


class MechanismUtilityModelSpec(KernelModel):
    """Utility semantics closed enough for exact finite replay."""

    kind: MechanismUtilityModelKind
    value_table: list[FiniteValueTableEntry] = Field(default_factory=list)
    utility_table: list[FiniteUtilityTableEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_utility_model(self) -> MechanismUtilityModelSpec:
        if self.kind is MechanismUtilityModelKind.QUASI_LINEAR_SCALAR:
            if not self.value_table:
                raise ValueError("quasi_linear_scalar utility_model requires value_table")
            if self.utility_table:
                raise ValueError("quasi_linear_scalar utility_model cannot declare utility_table")
        elif not self.utility_table:
            raise ValueError("explicit_table utility_model requires utility_table")
        return self


class ExactPlayerPriorSpec(KernelModel):
    """Exact per-player marginal prior used by independent finite Bayesian checks."""

    player_id: str = Field(..., pattern=ID_PATTERN)
    probabilities: dict[str, ExactNumber]


class ExactJointPriorEntry(KernelModel):
    """Exact joint-support atom for correlated finite Bayesian types."""

    type_profile: dict[str, str]
    probability: ExactNumber


class MechanismPriorSpec(KernelModel):
    """Exact prior semantics used for BIC expectation replay."""

    kind: MechanismPriorKind
    player_priors: list[ExactPlayerPriorSpec] = Field(default_factory=list)
    joint_support: list[ExactJointPriorEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_prior(self) -> MechanismPriorSpec:
        if self.kind is MechanismPriorKind.INDEPENDENT_EXACT:
            if not self.player_priors:
                raise ValueError("independent_exact prior requires player_priors")
            if self.joint_support:
                raise ValueError("independent_exact prior cannot declare joint_support")
            ensure_unique_ids(
                self.player_priors,
                key_fn=lambda item: item.player_id,
                label="exact prior player_id",
            )
            for entry in self.player_priors:
                if not entry.probabilities:
                    raise ValueError(
                        f"independent_exact prior for '{entry.player_id}' requires probabilities"
                    )
                total = Fraction(0)
                for value in entry.probabilities.values():
                    probability = Fraction(value)
                    if probability < 0:
                        raise ValueError("exact prior probabilities must be non-negative")
                    total += probability
                if total != 1:
                    raise ValueError(
                        f"independent_exact prior for '{entry.player_id}' must sum to 1"
                    )
            return self

        if not self.joint_support:
            raise ValueError("joint_exact_table prior requires joint_support")
        if self.player_priors:
            raise ValueError("joint_exact_table prior cannot declare player_priors")
        total = Fraction(0)
        seen: set[tuple[tuple[str, str], ...]] = set()
        for entry in self.joint_support:
            probability = Fraction(entry.probability)
            if probability < 0:
                raise ValueError("joint_exact_table probabilities must be non-negative")
            total += probability
            key = tuple(sorted(entry.type_profile.items()))
            if key in seen:
                raise ValueError("joint_exact_table cannot repeat the same type_profile")
            seen.add(key)
        if total != 1:
            raise ValueError("joint_exact_table probabilities must sum to 1")
        return self


class Envelope1DPointSpec(KernelModel):
    """One direct-report point in a single-parameter quasi-linear mechanism."""

    type_label: str = Field(..., min_length=1)
    type_value: ExactNumber
    allocation: ExactNumber
    payment: ExactNumber | None = None


class Envelope1DSemanticsSpec(KernelModel):
    """Single-player exact direct-mechanism fragment certified by envelope checks."""

    player_id: str = Field(..., pattern=ID_PATTERN)
    points: list[Envelope1DPointSpec] = Field(default_factory=list)
    normalization_type_label: str | None = Field(None, min_length=1)
    normalization_utility: ExactNumber = "0"

    @model_validator(mode="after")
    def validate_envelope_fragment(self) -> Envelope1DSemanticsSpec:
        if not self.points:
            raise ValueError("envelope_1d semantics require at least one point")
        ensure_unique_ids(
            self.points,
            key_fn=lambda item: item.type_label,
            label="envelope_1d type_label",
        )
        values = [Fraction(point.type_value) for point in self.points]
        for idx in range(1, len(values)):
            if values[idx] <= values[idx - 1]:
                raise ValueError("envelope_1d type_value entries must be strictly increasing")
        if self.normalization_type_label is not None and self.normalization_type_label not in {
            point.type_label for point in self.points
        }:
            raise ValueError("normalization_type_label must reference an envelope_1d point")
        return self


class CycMonTypePointSpec(KernelModel):
    """One multidimensional type-grid point used by the exact cycmon route."""

    type_label: str = Field(..., min_length=1)
    coords: tuple[ExactNumber, ...] = Field(..., min_length=1)


class CycMonAllocationPointSpec(KernelModel):
    """Allocation and optional payment for one multidimensional report label."""

    type_label: str = Field(..., min_length=1)
    allocation: tuple[ExactNumber, ...] = Field(..., min_length=1)
    payment: ExactNumber | None = None


class CycMonGridSemanticsSpec(KernelModel):
    """Finite-grid multidimensional direct mechanism certified by utility potentials."""

    player_id: str = Field(..., pattern=ID_PATTERN)
    type_points: list[CycMonTypePointSpec] = Field(default_factory=list)
    allocation_points: list[CycMonAllocationPointSpec] = Field(default_factory=list)
    normalization_type_label: str | None = Field(None, min_length=1)
    normalization_utility: ExactNumber = "0"

    @model_validator(mode="after")
    def validate_cycmon_fragment(self) -> CycMonGridSemanticsSpec:
        if not self.type_points:
            raise ValueError("cycmon_grid semantics require type_points")
        if not self.allocation_points:
            raise ValueError("cycmon_grid semantics require allocation_points")
        ensure_unique_ids(
            self.type_points,
            key_fn=lambda item: item.type_label,
            label="cycmon_grid type_label",
        )
        ensure_unique_ids(
            self.allocation_points,
            key_fn=lambda item: item.type_label,
            label="cycmon_grid allocation type_label",
        )
        labels = {point.type_label for point in self.type_points}
        if labels != {point.type_label for point in self.allocation_points}:
            raise ValueError(
                "cycmon_grid allocation_points must match type_points exactly by type_label"
            )
        type_dim = len(self.type_points[0].coords)
        alloc_dim = len(self.allocation_points[0].allocation)
        if type_dim != alloc_dim:
            raise ValueError("cycmon_grid requires allocation vectors to match type dimension")
        for point in self.type_points:
            if len(point.coords) != type_dim:
                raise ValueError("cycmon_grid type_points must share the same dimension")
        for point in self.allocation_points:
            if len(point.allocation) != alloc_dim:
                raise ValueError("cycmon_grid allocation_points must share the same dimension")
        if (
            self.normalization_type_label is not None
            and self.normalization_type_label not in labels
        ):
            raise ValueError("normalization_type_label must reference a cycmon_grid point")
        return self


class MechanismSemanticsSpec(KernelModel):
    """Semantic closure for exact finite and exact constructive IC fragments."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    semantics_id: str = Field(..., pattern=ID_PATTERN)
    fragment: MechanismSemanticFragment = MechanismSemanticFragment.FINITE_DIRECT
    revelation_mode: MechanismRevelationMode = MechanismRevelationMode.DIRECT
    outcome_mode: MechanismOutcomeMode = MechanismOutcomeMode.DETERMINISTIC
    tie_breaking_rule: str | None = Field(None, max_length=240)
    finite_outcomes: list[FiniteOutcomeSpec] = Field(default_factory=list)
    allocation_rule: list[FiniteOutcomeRuleEntry] = Field(default_factory=list)
    utility_model: MechanismUtilityModelSpec | None = None
    prior: MechanismPriorSpec | None = None
    envelope_1d: Envelope1DSemanticsSpec | None = None
    cycmon_grid: CycMonGridSemanticsSpec | None = None
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_semantics(self) -> MechanismSemanticsSpec:
        if self.fragment is MechanismSemanticFragment.FINITE_DIRECT:
            if not self.finite_outcomes:
                raise ValueError("finite_direct semantics require finite_outcomes")
            if not self.allocation_rule:
                raise ValueError("finite_direct semantics require allocation_rule")
            if self.utility_model is None:
                raise ValueError("finite_direct semantics require utility_model")
            if self.envelope_1d is not None or self.cycmon_grid is not None:
                raise ValueError(
                    "finite_direct semantics cannot also declare envelope_1d or cycmon_grid"
                )
            ensure_unique_ids(
                self.finite_outcomes,
                key_fn=lambda item: item.outcome_id,
                label="mechanism outcome_id",
            )
            seen_profiles: set[tuple[tuple[str, str], ...]] = set()
            for entry in self.allocation_rule:
                key = tuple(sorted(entry.report_profile.items()))
                if key in seen_profiles:
                    raise ValueError("allocation_rule cannot repeat the same report_profile")
                seen_profiles.add(key)
            return self

        if self.fragment is MechanismSemanticFragment.ENVELOPE_1D:
            if self.envelope_1d is None:
                raise ValueError("envelope_1d fragment requires envelope_1d semantics")
            if self.finite_outcomes or self.allocation_rule or self.utility_model is not None:
                raise ValueError(
                    "envelope_1d fragment cannot declare finite_direct outcome or utility tables"
                )
            if self.cycmon_grid is not None:
                raise ValueError("envelope_1d fragment cannot also declare cycmon_grid")
            if self.prior is not None:
                raise ValueError("envelope_1d fragment does not use prior semantics")
            return self

        if self.cycmon_grid is None:
            raise ValueError("cycmon_grid fragment requires cycmon_grid semantics")
        if self.finite_outcomes or self.allocation_rule or self.utility_model is not None:
            raise ValueError(
                "cycmon_grid fragment cannot declare finite_direct outcome or utility tables"
            )
        if self.envelope_1d is not None:
            raise ValueError("cycmon_grid fragment cannot also declare envelope_1d")
        if self.prior is not None:
            raise ValueError("cycmon_grid fragment does not use prior semantics")
        return self

    def validate_against_declared_structure(
        self,
        *,
        players: tuple[str, ...],
        action_spaces: dict[str, tuple[str, ...]],
        type_spaces: dict[str, tuple[str, ...]],
    ) -> MechanismSemanticsSpec:
        player_set = set(players)
        if self.revelation_mode is not MechanismRevelationMode.DIRECT:
            raise ValueError("MVP mechanism semantics currently support only direct revelation")
        if self.outcome_mode is not MechanismOutcomeMode.DETERMINISTIC:
            raise ValueError(
                "MVP mechanism semantics currently support only deterministic outcomes"
            )
        if self.fragment is MechanismSemanticFragment.FINITE_DIRECT:
            return self._validate_finite_direct_structure(
                players=players,
                action_spaces=action_spaces,
                type_spaces=type_spaces,
            )

        if len(players) != 1:
            raise ValueError(
                f"{self.fragment.value} semantics currently support exactly one strategic player"
            )
        if set(type_spaces) != player_set:
            raise ValueError(
                "direct mechanism semantics require finite type spaces for every player"
            )
        player_id = players[0]
        declared_reports = tuple(action_spaces.get(player_id, ()))
        declared_types = tuple(type_spaces.get(player_id, ()))
        if set(declared_reports) != set(declared_types):
            raise ValueError(
                "direct mechanism semantics require action_spaces to match bayesian type labels"
            )
        if self.fragment is MechanismSemanticFragment.ENVELOPE_1D:
            if self.envelope_1d is None or self.envelope_1d.player_id != player_id:
                raise ValueError("envelope_1d player_id must match the declared player")
            labels = {point.type_label for point in self.envelope_1d.points}
            if labels != set(declared_types):
                raise ValueError("envelope_1d points must match declared type labels exactly")
            return self

        if self.cycmon_grid is None or self.cycmon_grid.player_id != player_id:
            raise ValueError("cycmon_grid player_id must match the declared player")
        labels = {point.type_label for point in self.cycmon_grid.type_points}
        if labels != set(declared_types):
            raise ValueError("cycmon_grid type_points must match declared type labels exactly")
        return self

    def _validate_finite_direct_structure(
        self,
        *,
        players: tuple[str, ...],
        action_spaces: dict[str, tuple[str, ...]],
        type_spaces: dict[str, tuple[str, ...]],
    ) -> MechanismSemanticsSpec:
        player_set = set(players)
        if set(type_spaces) != player_set:
            raise ValueError(
                "direct mechanism semantics require finite type spaces for every player"
            )
        for player_id in players:
            declared_actions = tuple(action_spaces.get(player_id, ()))
            declared_types = tuple(type_spaces.get(player_id, ()))
            if set(declared_actions) != set(declared_types):
                raise ValueError(
                    "direct mechanism semantics require action_spaces to match bayesian type labels"
                )

        outcome_ids = {outcome.outcome_id for outcome in self.finite_outcomes}
        for outcome in self.finite_outcomes:
            unknown_players = set(outcome.allocation_by_player) - player_set
            if unknown_players:
                raise ValueError(
                    f"finite outcome '{outcome.outcome_id}' references unknown players "
                    f"{sorted(unknown_players)}"
                )

        for entry in self.allocation_rule:
            if set(entry.report_profile) != player_set:
                raise ValueError(
                    "allocation_rule report_profile must name every player exactly once"
                )
            if entry.outcome_id not in outcome_ids:
                raise ValueError(
                    f"allocation_rule references unknown outcome_id '{entry.outcome_id}'"
                )
            unknown_payers = set(entry.payments_by_player) - player_set
            if unknown_payers:
                raise ValueError(
                    f"allocation_rule payments reference unknown players {sorted(unknown_payers)}"
                )
            for player_id, report_label in entry.report_profile.items():
                if report_label not in action_spaces[player_id]:
                    raise ValueError(
                        f"allocation_rule report_profile for '{player_id}' uses undeclared "
                        f"report '{report_label}'"
                    )

        if self.utility_model is None:
            raise ValueError("utility_model is required when allocation_rule is provided")
        if self.utility_model.kind is MechanismUtilityModelKind.QUASI_LINEAR_SCALAR:
            for entry in self.utility_model.value_table:
                if entry.player_id not in player_set:
                    raise ValueError(
                        f"value_table references unknown player_id '{entry.player_id}'"
                    )
                if entry.type_label not in type_spaces[entry.player_id]:
                    raise ValueError(
                        f"value_table for '{entry.player_id}' references unknown type "
                        f"'{entry.type_label}'"
                    )
                unknown_outcomes = set(entry.outcome_values) - outcome_ids
                if unknown_outcomes:
                    raise ValueError(
                        f"value_table references unknown outcome_ids {sorted(unknown_outcomes)}"
                    )
        else:
            for entry in self.utility_model.utility_table:
                if entry.player_id not in player_set:
                    raise ValueError(
                        f"utility_table references unknown player_id '{entry.player_id}'"
                    )
                if entry.true_type not in type_spaces[entry.player_id]:
                    raise ValueError(
                        f"utility_table for '{entry.player_id}' references unknown type "
                        f"'{entry.true_type}'"
                    )
                if set(entry.report_profile) != player_set:
                    raise ValueError(
                        "utility_table report_profile must name every player exactly once"
                    )
                for player_id, report_label in entry.report_profile.items():
                    if report_label not in action_spaces[player_id]:
                        raise ValueError(
                            f"utility_table report_profile for '{player_id}' uses undeclared "
                            f"report '{report_label}'"
                        )

        if self.prior is not None and self.prior.kind is MechanismPriorKind.INDEPENDENT_EXACT:
            if {entry.player_id for entry in self.prior.player_priors} != player_set:
                raise ValueError("independent_exact prior must name every player exactly once")
            for entry in self.prior.player_priors:
                if set(entry.probabilities) != set(type_spaces[entry.player_id]):
                    raise ValueError(
                        f"independent_exact prior for '{entry.player_id}' must match the declared "
                        "type labels exactly"
                    )
        if self.prior is not None and self.prior.kind is MechanismPriorKind.JOINT_EXACT_TABLE:
            for entry in self.prior.joint_support:
                if set(entry.type_profile) != player_set:
                    raise ValueError(
                        "joint_exact_table prior type_profile must name every player exactly once"
                    )
                for player_id, type_label in entry.type_profile.items():
                    if type_label not in type_spaces[player_id]:
                        raise ValueError(
                            f"joint_exact_table prior for '{player_id}' uses undeclared type "
                            f"'{type_label}'"
                        )
        return self


__all__ = [
    "CycMonAllocationPointSpec",
    "CycMonGridSemanticsSpec",
    "CycMonTypePointSpec",
    "Envelope1DPointSpec",
    "Envelope1DSemanticsSpec",
    "ExactJointPriorEntry",
    "ExactNumber",
    "ExactPlayerPriorSpec",
    "FiniteOutcomeRuleEntry",
    "FiniteOutcomeSpec",
    "FiniteUtilityTableEntry",
    "FiniteValueTableEntry",
    "MechanismOutcomeMode",
    "MechanismPriorKind",
    "MechanismPriorSpec",
    "MechanismRevelationMode",
    "MechanismSemanticFragment",
    "MechanismSemanticsSpec",
    "MechanismUtilityModelKind",
    "MechanismUtilityModelSpec",
]
