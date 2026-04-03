"""Public migrations policy ir module API."""
from __future__ import annotations

from polisyos.ir.migrations.base import register_migration
from polisyos.ir.trinity import TrinityBundle

POLICY_IR_CURRENT_VERSION = "1.0"
TRINITY_CURRENT_VERSION = "1.0"


@register_migration("policy_ir", "1.0", "1.0")
def migrate_policy_ir_identity(data: dict) -> dict:
    """Identity migration for canonical Trinity policy payloads."""
    bundle = TrinityBundle.model_validate(data)
    return bundle.model_dump(mode="python")

__all__ = [
    "POLICY_IR_CURRENT_VERSION",
    "TRINITY_CURRENT_VERSION",
    "migrate_policy_ir_identity",
]
