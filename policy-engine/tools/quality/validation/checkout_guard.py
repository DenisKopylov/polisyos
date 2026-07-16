"""Reject proof execution when PolicyOS resolves from another checkout."""

from __future__ import annotations

from pathlib import Path

__all__ = ["WrongCheckoutResolvedError", "assert_current_checkout"]


class WrongCheckoutResolvedError(RuntimeError):
    """Raised when the imported PolicyOS package belongs to another checkout."""


def assert_current_checkout(repo_root: Path) -> Path:
    """Require the imported PolicyOS package to live below this checkout's source root.

    Args:
        repo_root: Policy Engine checkout root expected to own the imported package.

    Returns:
        The resolved path to the imported ``polisyos`` package file.

    Raises:
        WrongCheckoutResolvedError: If ``polisyos`` resolves outside this checkout's ``src`` root.
    """

    resolved_repo_root = repo_root.resolve()
    expected_src_root = (resolved_repo_root / "src").resolve()

    import polisyos

    resolved_package_path = Path(polisyos.__file__).resolve()
    if not resolved_package_path.is_relative_to(expected_src_root):
        raise WrongCheckoutResolvedError(f"wrong_checkout_resolved:{resolved_package_path}")
    return resolved_package_path
