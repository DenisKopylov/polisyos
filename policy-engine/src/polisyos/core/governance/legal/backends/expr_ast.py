"""
Safe AST Expression Evaluator and RuleBackend Implementation.

This module provides:
1. SafeExpressionEvaluator - Interprets whitelisted AST nodes
2. ExpressionASTBackend - Integrates with LegalPass pipeline

SECURITY: Uses ASTPolicy for validation before ANY evaluation.
          No eval(), no exec(), no compile().
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any, Dict, List

from polisyos.common.logger import get_logger
from polisyos.core.governance.legal.ast_policy import (
    ASTLimits,
    ASTPolicy,
    SecurityError,
)
from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
)

if TYPE_CHECKING:
    from polisyos.ir.norm_pack import NormPack, NormRule


logger = get_logger(__name__)


class SafeExpressionEvaluator:
    """
    Safe interpreter for AST-subset expressions.

    Evaluates expressions by walking the AST and manually
    implementing each allowed operation.

    Properties:
        - No side effects
        - No function calls
        - No attribute access
        - Context-isolated variable lookup

    Thread Safety: Instances are safe to share if context is not mutated.
    """

    def __init__(
        self,
        context: Dict[str, Any],
        *,
        limits: ASTLimits | None = None,
    ):
        """
        Initialize evaluator with context.

        Args:
            context: Variable name -> value mapping.
                     Only keys in this dict are accessible.
            limits: Optional custom AST limits.
        """
        self._context = context
        self._limits = limits or ASTLimits()
        self._ast_cache: Dict[str, ast.Expression] = {}

    @property
    def available_names(self) -> frozenset[str]:
        """Names available in the evaluation context."""
        return frozenset(self._context.keys())

    def evaluate(self, expr: str) -> Any:
        """
        Safely evaluate an expression.

        Args:
            expr: Expression string (e.g., "x > 10 and y < 5")

        Returns:
            Evaluation result (bool, int, float, or str)

        Raises:
            SecurityError: If expression violates policy
            ValueError: If evaluation fails (e.g., missing variable)
        """
        is_valid, error = ASTPolicy.validate(expr, limits=self._limits)
        if not is_valid:
            raise SecurityError(error, expression=expr)

        tree = self._get_cached_ast(expr)
        return self._eval_node(tree.body)

    def _get_cached_ast(self, expr: str) -> ast.Expression:
        """Get or parse AST with caching."""
        if expr not in self._ast_cache:
            self._ast_cache[expr] = ast.parse(expr, mode="eval")
        return self._ast_cache[expr]

    def _eval_node(self, node: ast.AST) -> Any:
        """
        Recursively evaluate an AST node.

        Each node type has an explicit handler.
        Unknown nodes raise SecurityError (fail-safe).
        """
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            name = node.id
            if name not in self._context:
                raise ValueError(f"Unknown variable: {name}")
            return self._context[name]

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value in node.values:
                    if not self._eval_node(value):
                        return False
                return True

            if isinstance(node.op, ast.Or):
                for value in node.values:
                    if self._eval_node(value):
                        return True
                return False

        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)

            if isinstance(node.op, ast.Not):
                return not operand
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand

        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)

            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ValueError("Division by zero")
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                if right == 0:
                    raise ValueError("Division by zero")
                return left // right
            if isinstance(node.op, ast.Mod):
                if right == 0:
                    raise ValueError("Modulo by zero")
                return left % right

        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)

            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator)

                if isinstance(op, ast.Eq):
                    if not (left == right):
                        return False
                elif isinstance(op, ast.NotEq):
                    if not (left != right):
                        return False
                elif isinstance(op, ast.Lt):
                    if not (left < right):
                        return False
                elif isinstance(op, ast.LtE):
                    if not (left <= right):
                        return False
                elif isinstance(op, ast.Gt):
                    if not (left > right):
                        return False
                elif isinstance(op, ast.GtE):
                    if not (left >= right):
                        return False
                else:
                    raise SecurityError(
                        f"Unknown comparison operator: {type(op).__name__}"
                    )

                left = right

            return True

        raise SecurityError(
            f"Unexpected node type during evaluation: {type(node).__name__}. "
            "This should have been caught by validation."
        )


class EvaluationError(Exception):
    """Raised when rule evaluation fails (non-security)."""

    def __init__(
        self,
        message: str,
        norm_id: str,
        expression: str | None = None,
    ):
        self.norm_id = norm_id
        self.expression = expression
        super().__init__(message)


class ExpressionASTBackend:
    """
    RuleBackend implementation using safe AST expression evaluation.

    Integrates SafeExpressionEvaluator with the LegalPass pipeline.

    Rule Format (in NormRule.backend_metadata):
        when: <expression>      # Applicability condition (optional)
        must: <expression>      # Obligation (for rule_type=OBLIGATION)
        must_not: <expression>  # Prohibition (for rule_type=PROHIBITION)
    """

    def __init__(self, *, limits: ASTLimits | None = None):
        """
        Initialize backend with optional custom limits.

        Args:
            limits: Custom AST limits (uses defaults if None)
        """
        self._limits = limits or ASTLimits()

    @property
    def backend_id(self) -> str:
        """Unique identifier for this backend."""
        return "expr_ast"

    def evaluate(
        self,
        norm_pack: "NormPack | None",
        context: dict,
    ) -> List[ComplianceIssue]:
        """
        Evaluate all applicable rules in the norm pack.

        Args:
            norm_pack: Collection of norms to evaluate
            context: State dictionary containing simulation data

        Returns:
            List of ComplianceIssue objects for violations/warnings
        """
        if norm_pack is None or not norm_pack.norms:
            return []

        issues: List[ComplianceIssue] = []
        evaluator = SafeExpressionEvaluator(context, limits=self._limits)

        for norm in norm_pack.norms:
            if self.backend_id not in norm.backend_refs:
                continue

            norm_issues = self._evaluate_single_norm(norm, evaluator)
            issues.extend(norm_issues)

        return issues

    def _evaluate_single_norm(
        self,
        norm: "NormRule",
        evaluator: SafeExpressionEvaluator,
    ) -> List[ComplianceIssue]:
        """
        Evaluate a single norm.

        Returns list of issues (0 if compliant, 1+ if violation/error).
        """
        try:
            metadata = getattr(norm, "backend_metadata", {}) or {}
            when_expr = metadata.get("when")
            must_expr = metadata.get("must")
            must_not_expr = metadata.get("must_not")

            if not any([when_expr, must_expr, must_not_expr]):
                return [
                    ComplianceIssue(
                        pass_id="legal",
                        path=["norm_pack", norm.norm_id],
                        message=(
                            f"Norm '{norm.norm_id}' has no evaluable expressions "
                            "(missing when/must/must_not in metadata)"
                        ),
                        severity=IssueSeverity.INFO,
                        code="NO_EXPRESSIONS",
                        suggestion="Add 'when', 'must', or 'must_not' to metadata",
                    )
                ]

            if when_expr:
                try:
                    is_applicable = evaluator.evaluate(when_expr)
                    if not is_applicable:
                        return []
                except ValueError as e:
                    return [
                        ComplianceIssue(
                            pass_id="legal",
                            path=["norm_pack", norm.norm_id, "when"],
                            message=(
                                f"Applicability check failed for '{norm.norm_id}': {e}"
                            ),
                            severity=IssueSeverity.INFO,
                            code="WHEN_EVAL_ERROR",
                            input_value=when_expr,
                        )
                    ]

            if must_expr:
                is_satisfied = evaluator.evaluate(must_expr)
                if not is_satisfied:
                    return [
                        ComplianceIssue(
                            pass_id="legal",
                            path=["norm_pack", norm.norm_id, "must"],
                            message=f"Obligation not met: {norm.description}",
                            severity=IssueSeverity.BLOCKER,
                            code=norm.norm_id,
                            input_value=must_expr,
                            suggestion=self._format_suggestion(
                                norm, must_expr, evaluator
                            ),
                        )
                    ]

            if must_not_expr:
                is_violated = evaluator.evaluate(must_not_expr)
                if is_violated:
                    return [
                        ComplianceIssue(
                            pass_id="legal",
                            path=["norm_pack", norm.norm_id, "must_not"],
                            message=f"Prohibition violated: {norm.description}",
                            severity=IssueSeverity.BLOCKER,
                            code=norm.norm_id,
                            input_value=must_not_expr,
                            suggestion=self._format_suggestion(
                                norm, must_not_expr, evaluator
                            ),
                        )
                    ]

            return []

        except SecurityError as e:
            return [
                ComplianceIssue(
                    pass_id="legal",
                    path=["norm_pack", norm.norm_id],
                    message=f"SECURITY: Invalid expression in norm: {e}",
                    severity=IssueSeverity.BLOCKER,
                    code="SECURITY_VIOLATION",
                    input_value=e.expression,
                )
            ]

        except ValueError as e:
            return [
                ComplianceIssue(
                    pass_id="legal",
                    path=["norm_pack", norm.norm_id],
                    message=f"Evaluation error in '{norm.norm_id}': {e}",
                    severity=IssueSeverity.WARNING,
                    code="EVAL_ERROR",
                )
            ]

        except (SyntaxError, TypeError, ValueError) as e:
            logger.debug(
                "Unexpected error evaluating norm %s: %s",
                norm.norm_id,
                e,
            )
            return [
                ComplianceIssue(
                    pass_id="legal",
                    path=["norm_pack", norm.norm_id],
                    message=f"Unexpected error evaluating '{norm.norm_id}': {e}",
                    severity=IssueSeverity.WARNING,
                    code="UNEXPECTED_ERROR",
                )
            ]

    def _format_suggestion(
        self,
        norm: "NormRule",
        expr: str,
        evaluator: SafeExpressionEvaluator,
    ) -> str | None:
        """
        Generate a helpful suggestion based on current values.

        Example: "Current: budget_deficit_pct=3.5, threshold is 3.0"
        """
        try:
            names = ASTPolicy.extract_names(expr)
            values = []
            for name in sorted(names):
                if name in evaluator._context:
                    value = evaluator._context[name]
                    if isinstance(value, float):
                        values.append(f"{name}={value:.4f}")
                    else:
                        values.append(f"{name}={value}")

            if values:
                return f"Current values: {', '.join(values)}"
        except (AttributeError, TypeError, ValueError) as exc:
            logger.debug(
                "Failed to build suggestion payload for rule %s: %s",
                norm.norm_id,
                exc,
            )
        return None


__all__ = [
    "SafeExpressionEvaluator",
    "ExpressionASTBackend",
    "EvaluationError",
]
