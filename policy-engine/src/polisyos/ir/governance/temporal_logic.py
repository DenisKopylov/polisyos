"""Temporal logic contracts for governance/compliance policy constraints."""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from polisyos.ir._validation import (
    ensure_non_empty_dotted_path,
    validate_selector_expr,
    validate_selector_predicate_shape,
)
from polisyos.ir.governance.selector_expr import SelectorExpr, SelectorValue
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.types import SelectorOperator

MAX_TEMPORAL_FORMULA_DEPTH = 24
MAX_TEMPORAL_FORMULA_NODES = 128


class TemporalLogicFamily(str, Enum):
    """Supported temporal-logic subsets for policy/compliance contracts."""

    LTL = "ltl"
    CTL = "ctl"
    MTL = "mtl"


class TemporalExecutionSemantics(str, Enum):
    """Execution semantics expected by the runtime or compliance checker."""

    FINITE_TRACE = "finite_trace"
    BRANCHING_TREE = "branching_tree"
    WINDOWED_TRACE = "windowed_trace"


class TemporalEvaluationScope(str, Enum):
    """Where a temporal constraint is expected to be evaluated."""

    POLICY_SIMULATION = "policy_simulation"
    COMPLIANCE_TRACE = "compliance_trace"
    BRANCHING_FORECAST = "branching_forecast"


class TemporalTimeDomain(str, Enum):
    """Clock used by temporal-policy evaluation."""

    STEP = "step"
    EVENT_TIME = "event_time"


class TemporalUnaryOperator(str, Enum):
    """Unary operators used across LTL/MTL subsets."""

    NOT = "not"
    NEXT = "next"
    EVENTUALLY = "eventually"
    ALWAYS = "always"


class TemporalBinaryOperator(str, Enum):
    """Binary operators used across temporal-logic subsets."""

    IMPLIES = "implies"
    UNTIL = "until"
    RELEASE = "release"


class TemporalPathQuantifier(str, Enum):
    """CTL path quantifiers."""

    FOR_ALL_PATHS = "for_all_paths"
    EXISTS_PATH = "exists_path"


class TemporalAtom(KernelModel):
    """Atomic temporal proposition backed by selector or metric comparison."""

    kind: Literal["atom"] = "atom"
    proposition_id: str | None = Field(None, pattern=ID_PATTERN)
    selector: SelectorExpr | None = None
    metric_path: str | None = None
    operator: SelectorOperator | None = None
    value: SelectorValue | None = None
    description: str | None = Field(None, max_length=240)

    @model_validator(mode="after")
    def validate_atom(self) -> "TemporalAtom":
        if self.proposition_id is None and self.selector is None and self.metric_path is None:
            raise ValueError(
                "temporal atom requires proposition_id, selector, or metric_path"
            )
        if self.selector is not None:
            validate_selector_expr(
                self.selector,
                label="temporal atom selector",
                max_depth=16,
                max_nodes=128,
            )
        if self.metric_path is None:
            if self.operator is not None or self.value is not None:
                raise ValueError(
                    "metric operator/value are only allowed when metric_path is set"
                )
            return self
        ensure_non_empty_dotted_path(
            self.metric_path,
            field_name="metric_path",
            max_depth=8,
        )
        if self.operator is None or self.value is None:
            raise ValueError("metric_path atoms require operator and value")
        validate_selector_predicate_shape(
            field=self.metric_path,
            operator=self.operator,
            value=self.value,
        )
        return self


class TemporalNot(KernelModel):
    """Boolean negation over a temporal formula."""

    kind: Literal["not"] = "not"
    clause: "TemporalLogicExpr"


class TemporalAll(KernelModel):
    """Conjunction over temporal clauses."""

    kind: Literal["all_of"] = "all_of"
    clauses: list["TemporalLogicExpr"] = Field(..., min_length=1, max_length=32)


class TemporalAny(KernelModel):
    """Disjunction over temporal clauses."""

    kind: Literal["any_of"] = "any_of"
    clauses: list["TemporalLogicExpr"] = Field(..., min_length=1, max_length=32)


class TemporalUnaryFormula(KernelModel):
    """Unary temporal operator application."""

    kind: Literal["unary"] = "unary"
    operator: TemporalUnaryOperator
    clause: "TemporalLogicExpr"


class TemporalBinaryFormula(KernelModel):
    """Binary temporal operator application."""

    kind: Literal["binary"] = "binary"
    operator: TemporalBinaryOperator
    left: "TemporalLogicExpr"
    right: "TemporalLogicExpr"


class TemporalBoundedFormula(KernelModel):
    """MTL bounded temporal operator application."""

    kind: Literal["bounded"] = "bounded"
    operator: Literal["eventually", "always", "until"]
    lower_bound: Annotated[int, Field(ge=0)] = 0
    upper_bound: Annotated[int, Field(ge=0)]
    clause: TemporalLogicExpr | None = None
    left: TemporalLogicExpr | None = None
    right: TemporalLogicExpr | None = None

    @model_validator(mode="after")
    def validate_bounded_shape(self) -> "TemporalBoundedFormula":
        if self.upper_bound < self.lower_bound:
            raise ValueError("upper_bound must be >= lower_bound")
        if self.operator == "until":
            if self.left is None or self.right is None:
                raise ValueError("bounded until requires left and right clauses")
            if self.clause is not None:
                raise ValueError("bounded until does not allow clause")
            return self
        if self.clause is None:
            raise ValueError(f"bounded {self.operator} requires clause")
        if self.left is not None or self.right is not None:
            raise ValueError(
                f"bounded {self.operator} only allows the clause field"
            )
        return self


class TemporalPathFormula(KernelModel):
    """CTL path quantifier over a temporal formula."""

    kind: Literal["path"] = "path"
    quantifier: TemporalPathQuantifier
    clause: "TemporalLogicExpr"


TemporalLogicExpr = Annotated[
    TemporalAtom
    | TemporalNot
    | TemporalAll
    | TemporalAny
    | TemporalUnaryFormula
    | TemporalBinaryFormula
    | TemporalBoundedFormula
    | TemporalPathFormula,
    Field(discriminator="kind"),
]


class TemporalPolicyConstraint(KernelModel):
    """Versioned temporal constraint with explicit execution semantics."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    constraint_id: str = Field(..., pattern=ID_PATTERN)
    logic_family: TemporalLogicFamily
    execution_semantics: TemporalExecutionSemantics
    evaluation_scope: TemporalEvaluationScope
    time_domain: TemporalTimeDomain = TemporalTimeDomain.STEP
    clock_field: str | None = None
    formula: TemporalLogicExpr
    finite_horizon: Annotated[int, Field(ge=1)] | None = None
    notes: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_constraint(self) -> "TemporalPolicyConstraint":
        expected_semantics = {
            TemporalLogicFamily.LTL: TemporalExecutionSemantics.FINITE_TRACE,
            TemporalLogicFamily.CTL: TemporalExecutionSemantics.BRANCHING_TREE,
            TemporalLogicFamily.MTL: TemporalExecutionSemantics.WINDOWED_TRACE,
        }[self.logic_family]
        if self.execution_semantics is not expected_semantics:
            raise ValueError(
                "execution_semantics does not match logic_family policy"
            )
        if self.logic_family is TemporalLogicFamily.CTL:
            if self.evaluation_scope is not TemporalEvaluationScope.BRANCHING_FORECAST:
                raise ValueError(
                    "CTL constraints require branching_forecast evaluation_scope"
                )
        elif self.evaluation_scope is TemporalEvaluationScope.BRANCHING_FORECAST:
            raise ValueError(
                "branching_forecast evaluation_scope is only valid for CTL constraints"
            )
        if self.time_domain is TemporalTimeDomain.EVENT_TIME:
            if self.clock_field is None:
                raise ValueError("clock_field is required for event_time constraints")
            ensure_non_empty_dotted_path(
                self.clock_field,
                field_name="clock_field",
                max_depth=8,
            )
        elif self.clock_field is not None:
            raise ValueError("clock_field is only valid for event_time constraints")

        depth, nodes, path_nodes = _temporal_formula_stats(self.formula)
        if depth > MAX_TEMPORAL_FORMULA_DEPTH:
            raise ValueError(
                f"temporal formula depth {depth} exceeds limit {MAX_TEMPORAL_FORMULA_DEPTH}"
            )
        if nodes > MAX_TEMPORAL_FORMULA_NODES:
            raise ValueError(
                f"temporal formula nodes {nodes} exceeds limit {MAX_TEMPORAL_FORMULA_NODES}"
            )
        _validate_formula_family(self.formula, self.logic_family)
        if self.logic_family is TemporalLogicFamily.CTL and path_nodes == 0:
            raise ValueError("CTL constraints require at least one path quantifier")
        if self.logic_family is TemporalLogicFamily.MTL and self.finite_horizon is None:
            raise ValueError("MTL constraints require finite_horizon")
        return self


def _temporal_formula_stats(node: TemporalLogicExpr) -> tuple[int, int, int]:
    kind = getattr(node, "kind", None)
    if kind == "atom":
        return 1, 1, 0
    if kind == "not":
        depth, nodes, paths = _temporal_formula_stats(node.clause)
        return depth + 1, nodes + 1, paths
    if kind in {"all_of", "any_of"}:
        child_stats = [_temporal_formula_stats(clause) for clause in node.clauses]
        depth = max(stat[0] for stat in child_stats) + 1
        nodes = sum(stat[1] for stat in child_stats) + 1
        paths = sum(stat[2] for stat in child_stats)
        return depth, nodes, paths
    if kind == "unary":
        depth, nodes, paths = _temporal_formula_stats(node.clause)
        return depth + 1, nodes + 1, paths
    if kind == "binary":
        left_depth, left_nodes, left_paths = _temporal_formula_stats(node.left)
        right_depth, right_nodes, right_paths = _temporal_formula_stats(node.right)
        return (
            max(left_depth, right_depth) + 1,
            left_nodes + right_nodes + 1,
            left_paths + right_paths,
        )
    if kind == "bounded":
        if node.operator == "until":
            left_depth, left_nodes, left_paths = _temporal_formula_stats(node.left)
            right_depth, right_nodes, right_paths = _temporal_formula_stats(node.right)
            return (
                max(left_depth, right_depth) + 1,
                left_nodes + right_nodes + 1,
                left_paths + right_paths,
            )
        depth, nodes, paths = _temporal_formula_stats(node.clause)
        return depth + 1, nodes + 1, paths
    if kind == "path":
        depth, nodes, paths = _temporal_formula_stats(node.clause)
        return depth + 1, nodes + 1, paths + 1
    return 1, 1, 0


def _validate_formula_family(
    node: TemporalLogicExpr,
    family: TemporalLogicFamily,
) -> None:
    kind = getattr(node, "kind", None)
    if kind == "atom":
        return
    if kind == "bounded":
        if family is not TemporalLogicFamily.MTL:
            raise ValueError("bounded temporal operators are only allowed for MTL")
        if node.operator == "until":
            _validate_formula_family(node.left, family)
            _validate_formula_family(node.right, family)
        else:
            _validate_formula_family(node.clause, family)
        return
    if kind == "path":
        if family is not TemporalLogicFamily.CTL:
            raise ValueError("path quantifiers are only allowed for CTL")
        _validate_formula_family(node.clause, family)
        return
    if kind == "not":
        _validate_formula_family(node.clause, family)
        return
    if kind in {"all_of", "any_of"}:
        for clause in node.clauses:
            _validate_formula_family(clause, family)
        return
    if kind == "unary":
        _validate_formula_family(node.clause, family)
        return
    if kind == "binary":
        _validate_formula_family(node.left, family)
        _validate_formula_family(node.right, family)


__all__ = [
    "TemporalAtom",
    "TemporalBinaryFormula",
    "TemporalBinaryOperator",
    "TemporalBoundedFormula",
    "TemporalEvaluationScope",
    "TemporalExecutionSemantics",
    "TemporalLogicExpr",
    "TemporalLogicFamily",
    "TemporalNot",
    "TemporalAll",
    "TemporalAny",
    "TemporalPathFormula",
    "TemporalPathQuantifier",
    "TemporalPolicyConstraint",
    "TemporalTimeDomain",
    "TemporalUnaryFormula",
    "TemporalUnaryOperator",
]
