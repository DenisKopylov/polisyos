"""Public legal ast policy module API."""
from __future__ import annotations

import warnings

from polisyos.core.governance.legal.ast_policy import ASTLimits, ASTPolicy, SecurityError

warnings.warn(
    "polisyos.scientist.governance.legal.ast_policy is deprecated; use polisyos.core.governance.legal.ast_policy",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["ASTPolicy", "ASTLimits", "SecurityError"]
