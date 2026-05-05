"""Public foundry profiles module API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CompileProfileLevel(str, Enum):
    """Foundry compile profile intensity levels."""

    FAST = "fast"
    MVP = "mvp"
    STRICT = "strict"


@dataclass(frozen=True)
class FoundryCompileProfile:
    """
    Compile-time profile for Foundry execution planning.

    Keeps compile-time knobs independent from Scientist governance profiles.
    """

    level: CompileProfileLevel

    @property
    def nan_guard_enabled(self) -> bool:
        return self.level == CompileProfileLevel.STRICT

    @classmethod
    def fast(cls) -> FoundryCompileProfile:
        return cls(level=CompileProfileLevel.FAST)

    @classmethod
    def mvp(cls) -> FoundryCompileProfile:
        return cls(level=CompileProfileLevel.MVP)

    @classmethod
    def strict(cls) -> FoundryCompileProfile:
        return cls(level=CompileProfileLevel.STRICT)


__all__ = ["CompileProfileLevel", "FoundryCompileProfile"]
