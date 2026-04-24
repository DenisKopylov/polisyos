"""Deprecated compatibility re-exports for governance base contracts.

Use `polisyos.core.governance.passes.base` for new code. This shim remains in
place so older Scientist integrations and docs can import `ComplianceIssue`,
`IssueSeverity`, `PassContext`, and `ValidatorPass` from the legacy path while
receiving a deprecation warning.
"""

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
