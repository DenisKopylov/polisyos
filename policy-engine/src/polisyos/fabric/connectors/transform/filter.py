"""Row filtering transform."""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from polisyos.fabric.connectors.transform._common import (
    build_lineage,
    resolve_copy_policy,
    stage_started_at,
)
from polisyos.fabric.connectors.transform.pipeline import (
    CopyPolicy,
    DataTransform,
    TransformContext,
    TransformError,
    TransformLineage,
)
from polisyos.fabric.quality.safety import UnsafeFilterExpressionError

__all__ = ["FilterTransform"]


def _evaluate_filter_condition(
    data: pd.DataFrame,
    condition: str,
) -> pd.Series:
    """Evaluate a restricted boolean expression against a DataFrame."""
    try:
        tree = ast.parse(condition, mode="eval")
    except SyntaxError as exc:
        raise UnsafeFilterExpressionError(f"Invalid filter syntax: {exc}") from exc

    result = _eval_ast_node(tree.body, data)
    if isinstance(result, bool):
        return pd.Series([result] * len(data), index=data.index, dtype="boolean")
    if not isinstance(result, pd.Series):
        raise UnsafeFilterExpressionError("Filter expression must evaluate to a boolean mask")
    try:
        return result.astype("boolean")
    except (TypeError, ValueError) as exc:
        raise UnsafeFilterExpressionError(
            "Filter expression must return boolean-compatible values"
        ) from exc


def _eval_ast_node(node: ast.AST, data: pd.DataFrame) -> object:
    if isinstance(node, ast.BoolOp):
        values = [_coerce_bool_like(_eval_ast_node(child, data)) for child in node.values]
        if not values:
            raise UnsafeFilterExpressionError("Boolean expressions must not be empty")
        result = values[0]
        for value in values[1:]:
            if isinstance(node.op, ast.And):
                result = result & value
            elif isinstance(node.op, ast.Or):
                result = result | value
            else:
                raise UnsafeFilterExpressionError("Unsupported boolean operator")
        return result

    if isinstance(node, ast.UnaryOp):
        operand = _eval_ast_node(node.operand, data)
        if isinstance(node.op, ast.Not):
            return ~_coerce_bool_like(operand)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        raise UnsafeFilterExpressionError("Unsupported unary operator")

    if isinstance(node, ast.Compare):
        left = _eval_ast_node(node.left, data)
        comparisons: list[object] = []
        for operator_node, comparator_node in zip(node.ops, node.comparators, strict=False):
            right = _eval_ast_node(comparator_node, data)
            comparisons.append(_apply_comparison(operator_node, left, right))
            left = right
        result = _coerce_bool_like(comparisons[0])
        for comparison in comparisons[1:]:
            result = result & _coerce_bool_like(comparison)
        return result

    if isinstance(node, ast.BinOp):
        left = _eval_ast_node(node.left, data)
        right = _eval_ast_node(node.right, data)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        raise UnsafeFilterExpressionError("Unsupported arithmetic operator")

    if isinstance(node, ast.Name):
        if node.id not in data.columns:
            raise UnsafeFilterExpressionError(f"Unknown filter field: {node.id!r}")
        return data[node.id]

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = [_eval_ast_node(child, data) for child in node.elts]
        if any(isinstance(value, pd.Series) for value in values):
            raise UnsafeFilterExpressionError(
                "Collection literals may not contain column references"
            )
        return values

    raise UnsafeFilterExpressionError(f"Unsupported filter expression node: {type(node).__name__}")


def _apply_comparison(
    operator_node: ast.cmpop,
    left: object,
    right: object,
) -> object:
    if isinstance(operator_node, ast.In):
        if isinstance(left, pd.Series):
            if isinstance(right, (list, tuple, set)):
                return left.isin(list(right))
            raise UnsafeFilterExpressionError(
                "Right-hand side of 'in' must be a literal collection"
            )
        return left in right
    if isinstance(operator_node, ast.NotIn):
        if isinstance(left, pd.Series):
            if isinstance(right, (list, tuple, set)):
                return ~left.isin(list(right))
            raise UnsafeFilterExpressionError(
                "Right-hand side of 'not in' must be a literal collection"
            )
        return left not in right
    if isinstance(operator_node, ast.Eq):
        return left == right
    if isinstance(operator_node, ast.NotEq):
        return left != right
    if isinstance(operator_node, ast.Gt):
        return left > right
    if isinstance(operator_node, ast.GtE):
        return left >= right
    if isinstance(operator_node, ast.Lt):
        return left < right
    if isinstance(operator_node, ast.LtE):
        return left <= right
    raise UnsafeFilterExpressionError(
        f"Unsupported comparison operator: {type(operator_node).__name__}"
    )


def _coerce_bool_like(value: object) -> pd.Series | bool:
    if isinstance(value, pd.Series):
        try:
            return value.astype("boolean")
        except (TypeError, ValueError) as exc:
            raise UnsafeFilterExpressionError(
                "Filter expressions must produce boolean-compatible masks"
            ) from exc
    if isinstance(value, bool):
        return value
    raise UnsafeFilterExpressionError(
        "Filter expressions must use comparisons that evaluate to booleans"
    )


@dataclass
class FilterTransform(DataTransform):
    """Filter rows based on a boolean condition or predicate."""

    condition: str | Callable[[pd.DataFrame], pd.Series]
    keep: bool = True
    max_drop_pct: float = 0.9

    @property
    def name(self) -> str:
        return "filter"

    def apply(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> tuple[pd.DataFrame, TransformLineage, list[str]]:
        start_time = stage_started_at()
        copy_policy = resolve_copy_policy(context)

        if isinstance(self.condition, str):
            try:
                mask = _evaluate_filter_condition(data, self.condition)
            except UnsafeFilterExpressionError as exc:
                raise TransformError(f"Unsafe filter condition: {exc}") from exc
            except Exception as exc:
                raise TransformError(f"Filter condition failed: {self.condition}: {exc}") from exc
        else:
            try:
                mask = self.condition(data)
            except Exception as exc:
                raise TransformError(f"Filter predicate failed: {exc}") from exc

        if not isinstance(mask, pd.Series):
            raise TransformError("Filter predicate must return a pandas Series")

        result = data[mask] if self.keep else data[~mask]

        if copy_policy == CopyPolicy.COPY:
            result = result.copy()

        dropped = len(data) - len(result)
        drop_pct = dropped / len(data) if len(data) else 0.0
        warnings: list[str] = []
        if drop_pct > self.max_drop_pct:
            warnings.append(f"Filter dropped {drop_pct:.1%} of rows (>{self.max_drop_pct:.1%})")

        lineage = build_lineage(
            stage_name=self.name,
            started_at=start_time,
            input_data=data,
            output_data=result,
            parameters={
                "condition": self.condition if isinstance(self.condition, str) else "<callable>",
                "keep": self.keep,
                "dropped_rows": dropped,
                "drop_pct": drop_pct,
            },
            context=context,
        )

        return result, lineage, warnings
