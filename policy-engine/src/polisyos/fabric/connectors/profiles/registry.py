"""SourceProfileRegistry — in-memory registry of available source profiles."""

from __future__ import annotations

import threading

from .models import SourceProfile


class SourceProfileRegistry:
    """Thread-safe singleton registry of SourceProfile instances."""

    _instance: SourceProfileRegistry | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._profiles: dict[str, SourceProfile] = {}

    @classmethod
    def get_instance(cls) -> SourceProfileRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = cls()
                    inst._bootstrap()
                    cls._instance = inst
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton — useful for testing."""
        with cls._lock:
            cls._instance = None

    def register(self, profile: SourceProfile, *, override: bool = False) -> None:
        if profile.profile_id in self._profiles and not override:
            raise ValueError(f"Profile '{profile.profile_id}' already registered")
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> SourceProfile | None:
        return self._profiles.get(profile_id)

    def list_all(self) -> list[SourceProfile]:
        return sorted(self._profiles.values(), key=lambda p: p.profile_id)

    def list_by_family(self, connector_family: str) -> list[SourceProfile]:
        return [
            p
            for p in self._profiles.values()
            if p.connector_family == connector_family
        ]

    def _bootstrap(self) -> None:
        from .builtin_profiles import BUILTIN_PROFILES

        for profile in BUILTIN_PROFILES:
            self.register(profile)


__all__ = ["SourceProfileRegistry"]
