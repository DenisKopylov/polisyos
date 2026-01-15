"""Legacy compiler stub (PolicySurfaceIR)."""
from __future__ import annotations

import warnings

warnings.warn(
    "polisyos.scientist.orchestrator.compiler (PolicySurfaceIR) is deprecated; "
    "use the Surface IR compiler.",
    DeprecationWarning,
    stacklevel=2,
)


def compile_policy(*_args, **_kwargs):  # noqa: D401
    """Deprecated legacy entrypoint; use polisyos.foundry.compiler.compile_surface_policy."""
    raise NotImplementedError(
        "compile_policy is no longer supported. Use polisyos.foundry.compiler.compile_surface_policy "
        "or build_workflow() instead."
    )
