"""Compatibility facade for IR-owned slot-layout helpers."""

from polisyos.ir import (
    SlotFamily,
    SlotFamilyManifest,
    SlotLayout,
    build_slot_family_manifest,
    build_slot_layout,
)

__all__ = [
    "SlotFamily",
    "SlotFamilyManifest",
    "SlotLayout",
    "build_slot_family_manifest",
    "build_slot_layout",
]
