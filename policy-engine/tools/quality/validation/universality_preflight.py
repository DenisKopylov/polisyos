"""Fail-closed environment preflight for GY-N10 proof execution."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tools.quality.validation.checkout_guard import assert_current_checkout

if TYPE_CHECKING:
    from polisyos.runtime.quality.credal_reference import GroundingBackendAvailability

__all__ = [
    "CgSubstrateUnavailableError",
    "WrongInterpreterResolvedError",
    "assert_repository_interpreter",
    "assert_universality_preflight",
]


class CgSubstrateUnavailableError(RuntimeError):
    """Raised when an owner-required causal-grounding backend is unavailable."""


class WrongInterpreterResolvedError(RuntimeError):
    """Raised when proof execution does not use the repository virtual environment."""


def assert_repository_interpreter(repo_root: Path) -> Path:
    """Require proof execution to use the repository virtual environment.

    The environment prefix is authoritative because the repository ``.venv``
    may be a symlink whose interpreter binary resolves to the base Python
    executable.

    Args:
        repo_root: Policy Engine checkout root expected to own proof execution.

    Returns:
        The resolved repository virtual-environment prefix.

    Raises:
        WrongInterpreterResolvedError: If either runtime prefix differs from
            the repository virtual environment or the observed prefix is the
            base interpreter prefix.
    """

    expected_prefix = (repo_root / ".venv").resolve()
    observed_prefix = Path(sys.prefix).resolve()
    observed_exec_prefix = Path(sys.exec_prefix).resolve()
    base_prefix = Path(sys.base_prefix).resolve()
    if (
        observed_prefix != expected_prefix
        or observed_exec_prefix != expected_prefix
        or observed_prefix == base_prefix
    ):
        raise WrongInterpreterResolvedError(
            "wrong_interpreter_resolved:"
            f"observed_prefix={observed_prefix};"
            f"observed_exec_prefix={observed_exec_prefix};"
            f"expected_prefix={expected_prefix};"
            f"sys_executable={sys.executable};"
            f"base_prefix={base_prefix}"
        )
    return observed_prefix


def assert_universality_preflight(
    repo_root: Path,
) -> tuple[Path, GroundingBackendAvailability]:
    """Require the current checkout, repository interpreter, and CG substrate.

    Checkout and interpreter assertions deliberately precede the runtime-owner
    import so neither a foreign ``polisyos`` package nor a base interpreter can
    become proof authority. Backend availability is derived by the canonical
    CG0 owner; this guard does not maintain a second list of required
    dependencies.

    Args:
        repo_root: Policy Engine checkout root expected to own proof execution.

    Returns:
        The resolved package path and content-addressed backend availability record.

    Raises:
        WrongCheckoutResolvedError: If PolicyOS resolves from another checkout.
        WrongInterpreterResolvedError: If proof execution does not use the
            repository virtual environment.
        CgSubstrateUnavailableError: If the canonical owner cannot be loaded or
            reports its required grounding backend unavailable.
    """

    resolved_package_path = assert_current_checkout(repo_root)
    assert_repository_interpreter(repo_root)
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
