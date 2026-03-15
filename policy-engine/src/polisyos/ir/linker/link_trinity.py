"""Trinity linker — binds interventions, mechanisms and constraints into a linked bundle."""
from __future__ import annotations

from polisyos.ir.linker._trinity_linker import link_trinity
from polisyos.ir.linker._trinity_models import (
    LinkedIntervention,
    LinkedTrinityBundle,
    TrinityBindings,
)

__all__ = [
    "LinkedIntervention",
    "LinkedTrinityBundle",
    "TrinityBindings",
    "link_trinity",
]
