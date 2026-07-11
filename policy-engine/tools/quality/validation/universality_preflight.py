"""Fail-closed environment preflight for GY-N10 proof execution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tools.quality.validation.checkout_guard import assert_current_checkout

if TYPE_CHECKING:
    from polisyos.runtime.quality.credal_reference import GroundingBackendAvailability

__all__ = [
    "CgSubstrateUnavailableError",
    "assert_universality_preflight",
]


class CgSubstrateUnavailableError(RuntimeError):
    """Raised when an owner-required causal-grounding backend is unavailable."""


def assert_universality_preflight(
    repo_root: Path,
) -> tuple[Path, GroundingBackendAvailability]:
    """Require the current checkout and its owner-declared CG substrate.

    The checkout assertion deliberately precedes the runtime-owner import so a
    foreign ``polisyos`` package cannot become proof authority. Backend
    availability is derived by the canonical CG0 owner; this guard does not
    maintain a second list of required dependencies.

    Args:
        repo_root: Policy Engine checkout root expected to own proof execution.

    Returns:
        The resolved package path and content-addressed backend availability record.

    Raises:
        WrongCheckoutResolvedError: If PolicyOS resolves from another checkout.
        CgSubstrateUnavailableError: If the canonical owner cannot be loaded or
            reports its required grounding backend unavailable.
    """

    resolved_package_path = assert_current_checkout(repo_root)
    try:
        from polisyos.runtime.quality.credal_reference import (
            build_grounding_backend_availability,
        )

        availability = build_grounding_backend_availability()
    except Exception as exc:
        raise CgSubstrateUnavailableError(
            "cg_substrate_unavailable:grounding_backend_availability:"
            f"{type(exc).__name__}"
        ) from exc

    if availability.required_backend_status != "available":
        solver_name = str(availability.solver.get("name") or "required_solver")
        solver_error = str(availability.solver.get("error") or "unavailable")
        raise CgSubstrateUnavailableError(
            f"cg_substrate_unavailable:{solver_name}:{solver_error}"
        )
    return resolved_package_path, availability
