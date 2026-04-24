"""Define component ID and semver contracts used by plugin registries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import ClassVar

from pydantic import RootModel, field_validator

_SEMVER_BODY = (
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
_SEMVER_RE = re.compile(rf"^{_SEMVER_BODY}$")
_COMPONENT_ID_RE = re.compile(
    rf"^(?P<path>[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)@(?P<version>{_SEMVER_BODY})$"
)


@total_ordering
@dataclass(frozen=True, slots=True)
class SemVer:
    """Represent a SemVer value with precedence rules used by component resolution."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: str) -> SemVer:
        """Parse a semantic version and validate prerelease/build syntax."""
        match = _SEMVER_RE.fullmatch(value.strip())
        if match is None:
            raise ValueError(f"Invalid semver: {value!r}")

        prerelease = tuple(token for token in (match.group("prerelease") or "").split(".") if token)
        build = tuple(token for token in (match.group("build") or "").split(".") if token)

        for token in prerelease:
            if token.isdigit() and len(token) > 1 and token.startswith("0"):
                raise ValueError(f"Invalid semver prerelease token: {token!r}")

        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=prerelease,
            build=build,
        )

    def _precedence(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        if self._precedence() != other._precedence():
            return self._precedence() < other._precedence()
        if not self.prerelease and not other.prerelease:
            return False
        if not self.prerelease:
            return False
        if not other.prerelease:
            return True
        return _compare_prerelease(self.prerelease, other.prerelease) < 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return False
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.prerelease == other.prerelease
            and self.build == other.build
        )

    def without_build(self) -> SemVer:
        """Return the same version without build metadata for precedence/range checks."""
        return SemVer(
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            prerelease=self.prerelease,
        )

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            value += f"-{'.'.join(self.prerelease)}"
        if self.build:
            value += f"+{'.'.join(self.build)}"
        return value


def _compare_prerelease(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    max_len = max(len(left), len(right))
    for idx in range(max_len):
        if idx >= len(left):
            return -1
        if idx >= len(right):
            return 1
        lval = left[idx]
        rval = right[idx]
        if lval == rval:
            continue

        lnum = lval.isdigit()
        rnum = rval.isdigit()
        if lnum and rnum:
            return -1 if int(lval) < int(rval) else 1
        if lnum and not rnum:
            return -1
        if rnum and not lnum:
            return 1
        return -1 if lval < rval else 1
    return 0


@dataclass(frozen=True, slots=True)
class SemverRange:
    """Represent a supported component version constraint expression."""

    raw: str
    clauses: tuple[tuple[str, SemVer], ...]

    @classmethod
    def parse(cls, value: str) -> SemverRange:
        """Parse exact, wildcard, or comparator-based version constraints."""
        raw = value.strip()
        if not raw:
            raise ValueError("SemverRange cannot be empty")

        wildcard_major = re.fullmatch(r"(0|[1-9]\d*)\.[xX]", raw)
        if wildcard_major is not None:
            major = int(wildcard_major.group(1))
            return cls(
                raw=raw,
                clauses=(
                    (">=", SemVer(major=major, minor=0, patch=0)),
                    ("<", SemVer(major=major + 1, minor=0, patch=0)),
                ),
            )

        wildcard_minor = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.[xX]", raw)
        if wildcard_minor is not None:
            major = int(wildcard_minor.group(1))
            minor = int(wildcard_minor.group(2))
            return cls(
                raw=raw,
                clauses=(
                    (">=", SemVer(major=major, minor=minor, patch=0)),
                    ("<", SemVer(major=major, minor=minor + 1, patch=0)),
                ),
            )

        tokens = [token.strip() for token in raw.split(",") if token.strip()]
        clauses: list[tuple[str, SemVer]] = []
        if len(tokens) == 1 and _SEMVER_RE.fullmatch(tokens[0]) is not None:
            semver = SemVer.parse(tokens[0]).without_build()
            return cls(raw=raw, clauses=((">=", semver), ("<=", semver)))

        comparator_re = re.compile(r"^(<=|>=|<|>|==|=)\s*(.+)$")
        for token in tokens:
            match = comparator_re.fullmatch(token)
            if match is None:
                raise ValueError(f"Invalid semver range token: {token!r}")
            op = "==" if match.group(1) == "=" else match.group(1)
            semver = SemVer.parse(match.group(2)).without_build()
            clauses.append((op, semver))

        if not clauses:
            raise ValueError(f"Invalid semver range: {value!r}")
        return cls(raw=raw, clauses=tuple(clauses))

    def matches(self, version: str | SemVer) -> bool:
        """Return whether `version` satisfies all parsed range clauses."""
        semver = version if isinstance(version, SemVer) else SemVer.parse(version)
        semver = semver.without_build()
        for op, target in self.clauses:
            if op == "==":
                if semver != target:
                    return False
            elif op == ">":
                if not semver > target:
                    return False
            elif op == ">=":
                if not (semver > target or semver == target):
                    return False
            elif op == "<":
                if not semver < target:
                    return False
            elif op == "<=":
                if not (semver < target or semver == target):
                    return False
            else:  # pragma: no cover - defensive
                raise ValueError(f"Unsupported semver comparator: {op}")
        return True


class ComponentId(RootModel[str]):
    """Component identifier: dot.path.name@semver."""

    pattern: ClassVar[re.Pattern[str]] = _COMPONENT_ID_RE

    @field_validator("root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        """Validate `seg(.seg)+@semver` format and parse the version component."""
        if not isinstance(value, str):
            raise TypeError("ComponentId must be a string")
        if not cls.pattern.match(value):
            raise ValueError("ComponentId must match seg(.seg)+@semver")
        _ = SemVer.parse(value.rsplit("@", 1)[1])
        return value

    @classmethod
    def parse(cls, value: str) -> ComponentId:
        """Parse a component identifier string into the normalized root model."""
        return cls(value)

    @property
    def path(self) -> str:
        """Return the dotted component path without the version suffix."""
        match = self.pattern.match(self.root)
        if not match:
            raise ValueError("Invalid ComponentId")
        return match.group("path")

    @property
    def base_id(self) -> str:
        """Return the versionless component ID used for multi-version lookups."""
        return self.path

    @property
    def namespace(self) -> str:
        """Return the dotted namespace portion of `base_id`."""
        return self.base_id.rsplit(".", 1)[0]

    @property
    def name(self) -> str:
        """Return the terminal component name segment."""
        return self.base_id.rsplit(".", 1)[1]

    @property
    def version(self) -> str:
        """Return the serialized SemVer suffix from the component ID."""
        match = self.pattern.match(self.root)
        if not match:
            raise ValueError("Invalid ComponentId")
        return match.group("version")

    @property
    def semver(self) -> SemVer:
        """Return the parsed SemVer object for this component ID."""
        return SemVer.parse(self.version)

    @property
    def version_sanitized(self) -> str:
        """Return a filesystem-friendly version string with `+` and `@` replaced."""
        return self.version.replace("+", "_").replace("@", "_")

    def __str__(self) -> str:
        return self.root


def compare_semver(left: str, right: str) -> int:
    """Compare two semantic versions using registry precedence rules."""
    left_semver = SemVer.parse(left)
    right_semver = SemVer.parse(right)
    if left_semver < right_semver:
        return -1
    if left_semver > right_semver:
        return 1
    return 0
