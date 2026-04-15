"""Public migrations policy ir module API."""
from __future__ import annotations

from polisyos.ir.migrations.base import (
    CompatibilityMode,
    register_migration,
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


@register_migration("policy_ir", "1.0", "1.0", compatibility=CompatibilityMode.FULL)
def migrate_policy_ir_identity(data: dict) -> dict:
    """Identity migration for canonical Trinity policy payloads."""
    bundle = TrinityBundle.model_validate(data)
    return bundle.model_dump(mode="python")

__all__ = [
    "POLICY_IR_CURRENT_VERSION",
    "TRINITY_CURRENT_VERSION",
    "migrate_policy_ir_identity",
]
