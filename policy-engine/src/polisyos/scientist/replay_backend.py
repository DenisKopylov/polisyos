"""Compatibility shim for `polisyos.scientist.replay_backend`.

Canonical module: `polisyos.scientist.replay.backend`.
Sunset: 2026-11-30.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.replay.backend",
    public_names=(
        "DeadLetterCorruptedError",
        "DeadLetterError",
        "DeadLetterNotFoundError",
        "DeadLetterRecord",
        "ReplayBackendResult",
        "list_dead_letters",
        "load_dead_letter",
        "replay_dead_letter",
        "replay_packet",
    ),
    sunset_date="2026-11-30",
    migration_hint="Use polisyos.scientist.replay.backend for new imports.",
    shim_id="scientist.replay_backend-to-replay.backend",
)
