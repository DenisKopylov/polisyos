"""
AST Safety Policy for Safe Expression Evaluation.

This module defines the security boundaries for the expression evaluator.
NO CODE EXECUTION OCCURS HERE - only validation.

Security Principle: DENY by default, ALLOW only explicitly whitelisted nodes.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import FrozenSet, Set


@dataclass(frozen=True)
class ASTLimits:
    """Resource limits to prevent DoS attacks."""

    MAX_NODES: int = 100
    MAX_DEPTH: int = 10
    MAX_EXPRESSION_LENGTH: int = 1024
    MAX_NAMES: int = 20


class ASTPolicy:
    """
    Defines which AST nodes are allowed in safe expression evaluation.

    Design Philosophy:
    - Explicit whitelist (default DENY)
    - No function calls, imports, or attribute access
    - Resource limits to prevent DoS

    This class is stateless and immutable.
    """

    ALLOWED_NODES: FrozenSet[type] = frozenset({
        # Expression wrapper
        ast.Expression,

        # Boolean operations
        ast.BoolOp,
        ast.And,
        ast.Or,

        # Unary operations
        ast.UnaryOp,
        ast.Not,
        ast.USub,
        ast.UAdd,

        # Comparison operations
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,

        # Binary arithmetic operations
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.FloorDiv,

        # Values
        ast.Name,
        ast.Load,
        ast.Constant,
    })

    LIMITS: ASTLimits = ASTLimits()

    @classmethod
    def validate(
        cls,
        expr: str,
        *,
        limits: ASTLimits | None = None,
    ) -> tuple[bool, str | None]:
        """
        Validate expression against security policy.

        Args:
            expr: Expression string to validate
            limits: Optional custom limits (uses LIMITS if None)

        Returns:
            (is_valid, error_message) tuple.
            error_message is None if valid.

        Security: This method performs validation ONLY.
                  It does NOT evaluate the expression.
        """
        limits = limits or cls.LIMITS

        if not expr or not isinstance(expr, str):
            return False, "Expression must be a non-empty string"

        if len(expr) > limits.MAX_EXPRESSION_LENGTH:
            return False, (
                f"Expression too long ({len(expr)} chars, "
                f"max {limits.MAX_EXPRESSION_LENGTH})"
            )

        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            return False, f"Syntax error at position {e.offset}: {e.msg}"

        all_nodes = list(ast.walk(tree))
        node_count = len(all_nodes)
        if node_count > limits.MAX_NODES:
            return False, (
                f"Expression too complex ({node_count} nodes, "
                f"max {limits.MAX_NODES})"
            )

        depth = cls._compute_depth(tree)
        if depth > limits.MAX_DEPTH:
            return False, (
                f"Expression too deeply nested ({depth} levels, "
                f"max {limits.MAX_DEPTH})"
            )

        names: Set[str] = set()

        for node in all_nodes:
            node_type = type(node)
            if node_type not in cls.ALLOWED_NODES:
                return False, (
                    f"Forbidden node type: {node_type.__name__}. "
                    f"Only safe expressions are allowed."
                )

            if isinstance(node, ast.Name):
                names.add(node.id)
                if node.id.startswith("__") or node.id.endswith("__"):
                    return False, f"Dunder names forbidden: {node.id}"

        if len(names) > limits.MAX_NAMES:
            return False, (
                f"Too many unique variables ({len(names)}, "
                f"max {limits.MAX_NAMES})"
            )

        return True, None

    @classmethod
    def extract_names(cls, expr: str) -> Set[str]:
        """
        Extract variable names from a validated expression.

        Args:
            expr: Expression string (should be pre-validated)

        Returns:
            Set of variable names used in the expression.

        Raises:
            ValueError: If expression is invalid.
        """
        is_valid, error = cls.validate(expr)
        if not is_valid:
            raise ValueError(f"Invalid expression: {error}")

        tree = ast.parse(expr, mode="eval")
        return {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }

    @classmethod
    def _compute_depth(cls, node: ast.AST, current: int = 0) -> int:
        """
        Compute maximum depth of AST.

        Iterative implementation to avoid Python recursion limit issues.
        """
        max_depth = current
        stack: list[tuple[ast.AST, int]] = [(node, current)]

        while stack:
            current_node, depth = stack.pop()
            max_depth = max(max_depth, depth)

            for child in ast.iter_child_nodes(current_node):
                stack.append((child, depth + 1))

        return max_depth


class SecurityError(Exception):
    """Raised when an expression violates security policy."""

    def __init__(self, message: str, expression: str | None = None):
        self.expression = expression
        super().__init__(message)


__all__ = ["ASTPolicy", "ASTLimits", "SecurityError"]
