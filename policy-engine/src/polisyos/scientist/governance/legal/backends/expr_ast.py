from __future__ import annotations

import warnings

from polisyos.core.governance.legal.backends.expr_ast import (
    EvaluationError,
    ExpressionASTBackend,
    SafeExpressionEvaluator,
)

warnings.warn(
    "polisyos.scientist.governance.legal.backends.expr_ast is deprecated; use polisyos.core.governance.legal.backends.expr_ast",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "SafeExpressionEvaluator",
    "ExpressionASTBackend",
    "EvaluationError",
]
