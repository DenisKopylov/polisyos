"""Legacy shim for Trinity migration.

Canonical migration logic lives in ``polisyos.ir.legacy.migrations``.
This module preserves the previous API surface for callers that still
import from ``polisyos.ir.migrations.trinity_migration``.
"""
from __future__ import annotations

from polisyos.ir.legacy.migrations.surface_to_trinity import (
    is_legacy_trinity_bundle_payload,
    is_trinity_bundle_payload,
    migrate_surface_ir_to_trinity,
    migrate_trinity_bundle_v0_to_trinity,
    migrate_trinity_to_surface_ir,
)
from polisyos.ir.legacy.surface import PolicySurfaceIR
from polisyos.ir.trinity import TrinityBundle


def split_surface_ir(legacy_ir: PolicySurfaceIR):
    bundle, _ = migrate_surface_ir_to_trinity(legacy_ir)
    return bundle.problem_frame, bundle.policy_spec, bundle.model_spec


def split_to_bundle(legacy_ir: PolicySurfaceIR) -> TrinityBundle:
    bundle, _ = migrate_surface_ir_to_trinity(legacy_ir)
    return bundle


def merge_to_surface_ir(
    problem_frame,
    policy_spec,
    model_spec,
    *,
    target_schema_version: str = "2.0",
):
    bundle = TrinityBundle(
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=model_spec,
    )
    surface, _ = migrate_trinity_to_surface_ir(
        bundle,
        target_schema_version=target_schema_version,
    )
    return surface


def is_trinity_migrated(data: dict) -> bool:
    return is_trinity_bundle_payload(data)


__all__ = [
    "is_trinity_migrated",
    "merge_to_surface_ir",
    "split_surface_ir",
    "split_to_bundle",
    "migrate_surface_ir_to_trinity",
    "migrate_trinity_to_surface_ir",
    "migrate_trinity_bundle_v0_to_trinity",
    "is_trinity_bundle_payload",
    "is_legacy_trinity_bundle_payload",
]
