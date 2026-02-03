from __future__ import annotations

from polisyos.ir.migrations.base import register_migration

POLICY_IR_CURRENT_VERSION = "2.0"
TRINITY_CURRENT_VERSION = "1.0"


@register_migration("policy_surface_to_trinity", "2.0", "1.0")
def migrate_surface_to_trinity(data: dict) -> dict:
    """
    Convert PolicySurfaceIR dict to Trinity format dict.

    This is used for batch migration tools, not the normal loader path.
    """
    from polisyos.ir.surface import PolicySurfaceIR
    from polisyos.ir.migrations.trinity_migration import split_to_bundle

    ir = PolicySurfaceIR.model_validate(data)
    bundle = split_to_bundle(ir)
    return bundle.model_dump()


@register_migration("trinity_to_policy_surface", "1.0", "2.0")
def migrate_trinity_to_surface(data: dict) -> dict:
    """
    Convert Trinity format dict back to PolicySurfaceIR dict.
    """
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.ir.migrations.trinity_migration import merge_to_surface_ir

    bundle = TrinityBundle.model_validate(data)
    ir = merge_to_surface_ir(
        bundle.problem_frame,
        bundle.policy_spec,
        bundle.model_spec,
    )
    return ir.model_dump()


__all__ = [
    "POLICY_IR_CURRENT_VERSION",
    "TRINITY_CURRENT_VERSION",
    "migrate_surface_to_trinity",
    "migrate_trinity_to_surface",
]
