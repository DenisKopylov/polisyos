from __future__ import annotations

import warnings

from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
    PassContext,
    ValidatorPass,
)

warnings.warn(
    "polisyos.scientist.governance.passes.base is deprecated; use polisyos.core.governance.passes.base",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "ComplianceIssue",
    "IssueSeverity",
    "PassContext",
    "ValidatorPass",
]
