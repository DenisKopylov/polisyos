"""BindingProfileRegistry — thread-safe singleton registry of binding profiles."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import BindingProfile


class BindingProfileRegistry:
    """Thread-safe singleton registry of BindingProfile instances."""

    _instance: BindingProfileRegistry | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._profiles: dict[str, BindingProfile] = {}

    @classmethod
    def get_instance(cls) -> BindingProfileRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = cls()
                    inst._bootstrap()
                    cls._instance = inst
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    def register(self, profile: BindingProfile, *, override: bool = False) -> None:
        if profile.profile_id in self._profiles and not override:
            raise ValueError(
                f"Binding profile '{profile.profile_id}' already registered"
            )
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> BindingProfile | None:
        return self._profiles.get(profile_id)

    def list_all(self) -> list[BindingProfile]:
        return sorted(self._profiles.values(), key=lambda p: p.profile_id)

    def list_by_family(self, schema_family: str) -> list[BindingProfile]:
        return sorted(
            [p for p in self._profiles.values() if p.schema_family == schema_family],
            key=lambda p: p.profile_id,
        )

    def _bootstrap(self) -> None:
        from .builtin_profiles import BUILTIN_BINDING_PROFILES

        for profile in BUILTIN_BINDING_PROFILES:
            self.register(profile)


__all__ = ["BindingProfileRegistry"]
