"""
Method Version Resolution Policies.

This module implements semantic versioning resolution for the Foundry Method
Registry. It supports four resolution policies:

- EXACT: Requires an exact version match
- LATEST_COMPATIBLE: Latest version within the caret-compatible range
- LATEST: Always resolves to the newest available version
- PINNED: Uses a version explicitly specified in a lockfile

SemVer 2.0 precedence rules are used, including proper caret behavior for 0.x.
Prerelease versions are excluded unless explicitly requested or allowed.

Architecture Law K: Explicit resolution policy - all version resolution
must go through this module with an explicitly chosen policy.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from functools import total_ordering
from typing import TYPE_CHECKING

from polisyos.foundry.methods.exceptions import ResolutionError

if TYPE_CHECKING:
    from packaging.specifiers import SpecifierSet

    from polisyos.foundry.methods.registry import MethodRegistry

__all__ = [
    "ResolutionError",
    "ResolutionPolicy",
    "VersionConstraint",
    "compare_versions",
    "find_compatible_versions",
    "is_compatible_upgrade",
    "parse_pip_specifier",
    "resolve_by_specifier",
    "resolve_method_version",
    "resolve_version",
]


_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)

Identifier = int | str


def _split_identifiers(value: str | None) -> tuple[Identifier, ...] | None:
    if value is None:
        return None
    parts = value.split(".")
    identifiers: list[Identifier] = []
    for part in parts:
        if part.isdigit():
            identifiers.append(int(part))
        else:
            identifiers.append(part)
    return tuple(identifiers)


@total_ordering
@dataclass(frozen=True, slots=True)
class SemVer:
    """Sem ver public type."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[Identifier, ...] | None = None
    build: tuple[Identifier, ...] | None = None

    @classmethod
    def parse(cls, version: str) -> SemVer:
        if not isinstance(version, str) or not version:
            raise ValueError(f"Invalid semver: {version!r}")
        match = _SEMVER_RE.match(version)
        if not match:
            raise ValueError(f"Invalid semver: {version!r}")
        major, minor, patch, prerelease, build = match.groups()
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=_split_identifiers(prerelease),
            build=_split_identifiers(build),
        )

    @property
    def is_prerelease(self) -> bool:
        return self.prerelease is not None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (
            self.major,
            self.minor,
            self.patch,
            self.prerelease,
        ) == (
            other.major,
            other.minor,
            other.patch,
            other.prerelease,
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch
        return _compare_prerelease(self.prerelease, other.prerelease) < 0


def _compare_prerelease(
    left: tuple[Identifier, ...] | None,
    right: tuple[Identifier, ...] | None,
) -> int:
    if left is None and right is None:
        return 0
    if left is None:
        return 1
    if right is None:
        return -1
    for l_item, r_item in zip(left, right):
        cmp = _compare_identifier(l_item, r_item)
        if cmp != 0:
            return cmp
    if len(left) < len(right):
        return -1
    if len(left) > len(right):
        return 1
    return 0


def _compare_identifier(left: Identifier, right: Identifier) -> int:
    left_is_int = isinstance(left, int)
    right_is_int = isinstance(right, int)
    if left_is_int and right_is_int:
        if left < right:
            return -1
        if left > right:
            return 1
        return 0
    if left_is_int and not right_is_int:
        return -1
    if not left_is_int and right_is_int:
        return 1
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def _format_semver(version: SemVer) -> str:
    base = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease is not None:
        base += "-" + ".".join(str(part) for part in version.prerelease)
    return base


class ResolutionPolicy(Enum):
    """
    Policy for resolving method versions from available options.

    Each policy defines a different strategy for selecting which version
    of a method to use when multiple versions are available.
    """

    EXACT = auto()
    """Require exact version match. The requested version must exist."""

    LATEST_COMPATIBLE = auto()
    """
    Latest version within the caret-compatible range (SemVer ^).

    Given requested version 1.2.3:
    - Will match 1.9.9 (same major, higher minor/patch)
    - Will match 1.2.4 (same major/minor, higher patch)
    - Will NOT match 2.0.0 (different major)
    - Will NOT match 1.1.0 (lower minor)

    For 0.x:
    - ^0.2.3 resolves >=0.2.3 and <0.3.0
    - ^0.0.3 resolves >=0.0.3 and <0.0.4
    """

    LATEST = auto()
    """Always resolve to the newest available version regardless of major."""

    PINNED = auto()
    """
    Use a version explicitly specified in a lockfile or constraint.

    Similar to EXACT but semantically indicates the version comes from
    external configuration rather than direct specification.
    """


@dataclass(frozen=True, slots=True)
class VersionConstraint:
    """
    Semantic version constraint for filtering available versions.

    Supports partial version matching:
    - VersionConstraint(major=1) matches any 1.x.x
    - VersionConstraint(major=1, minor=2) matches >=1.2.0 and <2.0.0
    - VersionConstraint(major=1, minor=2, patch=3) matches >=1.2.3 and <2.0.0

    For 0.x, caret compatibility is stricter:
    - 0.2.3 matches >=0.2.3 and <0.3.0
    - 0.0.3 matches >=0.0.3 and <0.0.4
    """

    major: int
    minor: int | None = None
    patch: int | None = None
    prerelease: tuple[Identifier, ...] | None = None
    include_prerelease: bool = False

    def __post_init__(self) -> None:
        if self.major < 0:
            raise ValueError(f"Major version must be non-negative, got {self.major}")
        if self.minor is not None and self.minor < 0:
            raise ValueError(f"Minor version must be non-negative, got {self.minor}")
        if self.patch is not None:
            if self.patch < 0:
                raise ValueError(f"Patch version must be non-negative, got {self.patch}")
            if self.minor is None:
                raise ValueError("Cannot specify patch without minor version")

    def _bounds(self) -> tuple[SemVer, SemVer]:
        minor = 0 if self.minor is None else self.minor
        patch = 0 if self.patch is None else self.patch
        lower = SemVer(
            major=self.major,
            minor=minor,
            patch=patch,
            prerelease=self.prerelease,
        )

        if self.minor is None:
            upper = SemVer(self.major + 1, 0, 0)
        elif self.patch is None:
            if self.major == 0:
                upper = SemVer(0, self.minor + 1, 0)
            else:
                upper = SemVer(self.major + 1, 0, 0)
        else:
            if self.major > 0:
                upper = SemVer(self.major + 1, 0, 0)
            elif self.minor > 0:
                upper = SemVer(0, self.minor + 1, 0)
            else:
                upper = SemVer(0, 0, self.patch + 1)

        return lower, upper

    def _allows_prerelease(self, include_prerelease: bool | None) -> bool:
        if include_prerelease is not None:
            return include_prerelease
        return self.include_prerelease or self.prerelease is not None

    def matches(self, version: str, *, include_prerelease: bool | None = None) -> bool:
        """
        Check if a version string satisfies this constraint.

        Args:
            version: SemVer version string (e.g., "1.2.3")

        Returns:
            True if version matches constraint, False otherwise

        Raises:
            ValueError: If version string is not valid semver
        """
        parsed = SemVer.parse(version)
        if parsed.is_prerelease and not self._allows_prerelease(include_prerelease):
            return False
        lower, upper = self._bounds()
        return lower <= parsed < upper

    @classmethod
    def from_version(cls, version: str) -> VersionConstraint:
        """
        Create a caret-style constraint from a version string.

        This creates a LATEST_COMPATIBLE style constraint matching the
        caret-compatible range for the given version.
        """
        parsed = SemVer.parse(version)
        include_prerelease = parsed.prerelease is not None
        return cls(
            major=parsed.major,
            minor=parsed.minor,
            patch=parsed.patch,
            prerelease=parsed.prerelease,
            include_prerelease=include_prerelease,
        )

    @classmethod
    def major_only(cls, major: int) -> VersionConstraint:
        """Create a constraint matching any version with given major."""
        return cls(major=major)

    def __str__(self) -> str:
        lower, upper = self._bounds()
        return f">={_format_semver(lower)},<{_format_semver(upper)}"


def _parse_and_sort_versions(
    versions: Sequence[str],
    descending: bool = True,
) -> list[tuple[SemVer, str]]:
    """
    Parse and sort version strings.

    Args:
        versions: List of version strings
        descending: If True, sort newest first

    Returns:
        List of (parsed_version, original_string) tuples, sorted

    Raises:
        ValueError: If any version string is invalid
    """
    parsed: list[tuple[SemVer, str]] = []
    for v_str in versions:
        try:
            parsed.append((SemVer.parse(v_str), v_str))
        except ValueError as exc:
            raise ValueError(f"Invalid semver in available versions: {v_str!r}") from exc

    parsed.sort(key=lambda item: item[0], reverse=descending)
    return parsed


def _requested_has_prerelease(requested: str | None) -> bool:
    if requested is None:
        return False
    try:
        return SemVer.parse(requested).is_prerelease
    except ValueError:
        return False


def resolve_version(
    available: Sequence[str],
    requested: str | None,
    policy: ResolutionPolicy,
    constraint: VersionConstraint | None = None,
    *,
    include_prerelease: bool | None = None,
) -> str:
    """
    Resolve a version from available versions according to policy.

    This is the primary entry point for version resolution. It implements
    the four resolution policies defined in ResolutionPolicy.

    Args:
        available: List of available version strings (semver format)
        requested: Explicitly requested version (required for EXACT/PINNED)
        policy: Resolution policy to apply
        constraint: Optional version constraint (used by LATEST_COMPATIBLE)
        include_prerelease: Override prerelease filtering behavior

    Returns:
        Resolved version string from the available list

    Raises:
        ResolutionError: If no matching version found
        ValueError: If arguments are invalid for the policy
    """
    if not available:
        raise ResolutionError(
            policy=policy,
            requested=requested,
            available=[],
            constraint=constraint,
            reason="No versions available",
        )

    if requested is not None:
        SemVer.parse(requested)

    # Parse and sort versions (newest first)
    try:
        sorted_versions = _parse_and_sort_versions(available, descending=True)
    except ValueError as exc:
        raise ResolutionError(
            policy=policy,
            requested=requested,
            available=available,
            constraint=constraint,
            reason=str(exc),
        ) from exc

    if policy == ResolutionPolicy.EXACT:
        return _resolve_exact(available, requested, sorted_versions)

    if policy == ResolutionPolicy.PINNED:
        return _resolve_pinned(available, requested, sorted_versions)

    if policy == ResolutionPolicy.LATEST:
        allow_prerelease = include_prerelease
        if allow_prerelease is None and _requested_has_prerelease(requested):
            allow_prerelease = True
        return _resolve_latest(
            available,
            requested,
            sorted_versions,
            allow_prerelease=bool(allow_prerelease),
        )

    if policy == ResolutionPolicy.LATEST_COMPATIBLE:
        allow_prerelease = include_prerelease
        if allow_prerelease is None:
            allow_prerelease = _requested_has_prerelease(requested)
            if constraint and constraint._allows_prerelease(None):
                allow_prerelease = True
        return _resolve_latest_compatible(
            available,
            requested,
            sorted_versions,
            constraint,
            allow_prerelease=bool(allow_prerelease),
        )

    raise ValueError(f"Unknown resolution policy: {policy}")


def _resolve_exact(
    available: Sequence[str],
    requested: str | None,
    sorted_versions: list[tuple[SemVer, str]],
) -> str:
    """Resolve with EXACT policy - version must match exactly."""
    if requested is None:
        raise ValueError("EXACT policy requires an explicit version")

    available_set = set(available)
    if requested in available_set:
        return requested

    requested_parsed = SemVer.parse(requested)
    for parsed, v_str in sorted_versions:
        if parsed == requested_parsed:
            return v_str

    raise ResolutionError(
        policy=ResolutionPolicy.EXACT,
        requested=requested,
        available=available,
    )


def _resolve_pinned(
    available: Sequence[str],
    requested: str | None,
    sorted_versions: list[tuple[SemVer, str]],
) -> str:
    """Resolve with PINNED policy - similar to EXACT but from lockfile."""
    if requested is None:
        raise ValueError("PINNED policy requires an explicit version from lockfile")

    available_set = set(available)
    if requested in available_set:
        return requested

    requested_parsed = SemVer.parse(requested)
    for parsed, v_str in sorted_versions:
        if parsed == requested_parsed:
            return v_str

    raise ResolutionError(
        policy=ResolutionPolicy.PINNED,
        requested=requested,
        available=available,
    )


def _resolve_latest(
    available: Sequence[str],
    requested: str | None,
    sorted_versions: list[tuple[SemVer, str]],
    *,
    allow_prerelease: bool,
) -> str:
    """Resolve with LATEST policy - return newest version."""
    for parsed, v_str in sorted_versions:
        if allow_prerelease or not parsed.is_prerelease:
            return v_str

    raise ResolutionError(
        policy=ResolutionPolicy.LATEST,
        requested=requested,
        available=available,
        reason="No release versions available (prerelease excluded)",
    )


def _resolve_latest_compatible(
    available: Sequence[str],
    requested: str | None,
    sorted_versions: list[tuple[SemVer, str]],
    constraint: VersionConstraint | None,
    *,
    allow_prerelease: bool,
) -> str:
    """
    Resolve with LATEST_COMPATIBLE policy.

    If no constraint provided but requested version given, derives
    constraint from requested version (caret-compatible range).
    """
    effective_constraint = constraint
    if effective_constraint is None and requested is not None:
        effective_constraint = VersionConstraint.from_version(requested)

    if effective_constraint is None:
        highest_major = sorted_versions[0][0].major
        effective_constraint = VersionConstraint.major_only(highest_major)

    for _, v_str in sorted_versions:
        if effective_constraint.matches(v_str, include_prerelease=allow_prerelease):
            return v_str

    raise ResolutionError(
        policy=ResolutionPolicy.LATEST_COMPATIBLE,
        requested=requested,
        available=available,
        constraint=effective_constraint,
    )


def find_compatible_versions(
    available: Sequence[str],
    constraint: VersionConstraint,
    *,
    include_prerelease: bool | None = None,
) -> list[str]:
    """
    Find all versions matching a constraint.

    Args:
        available: List of available version strings
        constraint: Version constraint to match
        include_prerelease: Override prerelease filtering behavior

    Returns:
        List of matching versions, sorted newest first
    """
    sorted_versions = _parse_and_sort_versions(available, descending=True)
    return [
        v_str
        for _, v_str in sorted_versions
        if constraint.matches(v_str, include_prerelease=include_prerelease)
    ]


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two version strings.

    Args:
        v1: First version string
        v2: Second version string

    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
    """
    parsed1 = SemVer.parse(v1)
    parsed2 = SemVer.parse(v2)

    if parsed1 < parsed2:
        return -1
    if parsed1 > parsed2:
        return 1
    return 0


def is_compatible_upgrade(current: str, target: str) -> bool:
    """
    Check if upgrading from current to target is backward-compatible.

    A compatible upgrade is one where the major version remains the same
    and the target version is >= current version.
    """
    current_parsed = SemVer.parse(current)
    target_parsed = SemVer.parse(target)

    return target_parsed.major == current_parsed.major and target_parsed >= current_parsed


# ---------------------------------------------------------------------------
# Pip-style specifier support (requires ``packaging`` — always available as
# it is a core dependency listed in pyproject.toml).
# ---------------------------------------------------------------------------


def parse_pip_specifier(specifier: str) -> SpecifierSet:
    """
    Parse a pip-style version specifier string into a SpecifierSet.

    Supported forms:
    - ``~=1.2``          compatible release (>=1.2, ==1.*)
    - ``>=1.0,<2.0``     range constraint
    - ``==1.0.0``        exact pin
    - ``!=1.3``          exclusion
    - ``1.0.0``          bare version — treated as exact (==1.0.0)

    Args:
        specifier: Pip-style version specifier string.

    Returns:
        A :class:`packaging.specifiers.SpecifierSet` instance.

    Raises:
        ValueError: If *specifier* cannot be parsed.
    """
    try:
        from packaging.specifiers import InvalidSpecifier, SpecifierSet
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "The 'packaging' library is required for pip-style specifier support. "
            "Install it with: pip install packaging"
        ) from exc

    # Bare version string (e.g. "1.0.0") → treat as exact match
    stripped = specifier.strip()
    if stripped and stripped[0].isdigit():
        stripped = f"=={stripped}"

    try:
        return SpecifierSet(stripped, prereleases=False)
    except InvalidSpecifier as exc:
        raise ValueError(f"Invalid pip-style specifier {specifier!r}: {exc}") from exc


def resolve_by_specifier(
    available: Sequence[str],
    specifier: str,
    *,
    include_prerelease: bool = False,
) -> str:
    """
    Resolve the highest available version matching a pip-style *specifier*.

    Args:
        available: Sequence of version strings (semver format).
        specifier: Pip-style constraint, e.g. ``"~=1.2"``, ``">=1.0,<2.0"``,
            ``"==1.0.0"``, or bare ``"1.0.0"``.
        include_prerelease: When True, pre-release versions are also considered.

    Returns:
        The highest-matching version string from *available*.

    Raises:
        ResolutionError: When no version in *available* satisfies *specifier*.
        ValueError: When *specifier* or any version string is invalid.
    """
    try:
        from packaging.version import Version as PkgVersion
    except ImportError as exc:  # pragma: no cover
        raise ImportError("The 'packaging' library is required.") from exc

    spec_set = parse_pip_specifier(specifier)
    if include_prerelease:
        spec_set = type(spec_set)(str(spec_set), prereleases=True)

    # Convert our SemVer strings to packaging.Version for filtering.
    candidates: list[tuple[PkgVersion, str]] = []
    for v_str in available:
        try:
            pv = PkgVersion(v_str)
        except Exception:
            # Skip un-parseable strings rather than crashing.
            continue
        if spec_set.contains(pv, prereleases=include_prerelease):
            candidates.append((pv, v_str))

    if not candidates:
        raise ResolutionError(
            policy=ResolutionPolicy.LATEST_COMPATIBLE,
            requested=specifier,
            available=list(available),
            reason=f"No version satisfies specifier {specifier!r}",
        )

    # Return the original string corresponding to the highest version.
    best_pv, best_str = max(candidates, key=lambda pair: pair[0])
    return best_str


def resolve_method_version(
    fqn_base: str,
    specifier: str | None,
    registry: MethodRegistry,  # type: ignore[name-defined]  # forward ref
) -> str:
    """
    High-level helper: resolve a versioned FQN for *fqn_base* using a
    pip-style *specifier*.

    When *specifier* is ``None`` the LATEST stable version is returned.

    Args:
        fqn_base: Base method name, e.g. ``"causal.did.standard"``.
        specifier: Pip-style constraint (``"~=1.0"``, ``">=1.0,<2.0"``,
            ``"1.0.0"``), or ``None`` for latest.
        registry: The :class:`~polisyos.foundry.methods.registry.MethodRegistry`
            instance to query.

    Returns:
        The resolved FQN, e.g. ``"causal.did.standard@1.2.0"``.

    Raises:
        ResolutionError: When no version satisfies the specifier or the
            *fqn_base* is not registered.
        ValueError: When *specifier* is malformed.
    """
    available_versions = registry.list_versions(fqn_base)
    if not available_versions:
        raise ResolutionError(
            policy=ResolutionPolicy.LATEST,
            requested=specifier,
            available=[],
            reason=f"No versions registered for {fqn_base!r}",
        )

    if specifier is None:
        # LATEST stable
        resolved = resolve_version(
            available=available_versions,
            requested=None,
            policy=ResolutionPolicy.LATEST,
        )
    else:
        resolved = resolve_by_specifier(available_versions, specifier)

    return f"{fqn_base}@{resolved}"


# Note: MethodRegistry is only used as a string forward reference in
# resolve_method_version() to avoid a circular import (registry.py imports this module).
