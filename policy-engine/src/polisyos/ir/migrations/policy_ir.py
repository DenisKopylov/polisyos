"""Public migrations policy ir module API."""

from __future__ import annotations

from polisyos.ir.migrations.base import (
    CompatibilityMode,
    register_schema_version,
)
from polisyos.ir.trinity import TrinityBundle

POLICY_IR_CURRENT_VERSION = "1.0"
TRINITY_CURRENT_VERSION = "1.0"


register_schema_version(
    "policy_ir",
    POLICY_IR_CURRENT_VERSION,
    compatibility=CompatibilityMode.FULL,
    notes=("Trinity policy IR 1.0 is the current canonical baseline.",),
)


def migrate_policy_ir_identity(data: dict) -> dict:
    """Validate canonical Trinity policy identity for existing helper callers."""
    bundle = TrinityBundle.model_validate(data)
    return bundle.model_dump(mode="python")


__all__ = [
    "POLICY_IR_CURRENT_VERSION",
    "TRINITY_CURRENT_VERSION",
    "migrate_policy_ir_identity",
]
