"""In-memory registry of built-in and test-provided ``SourceProfile`` definitions.

The registry is a metadata catalog only: it resolves profile ids and connector families but does
not validate live endpoint health, enforce throttling, or guarantee that a connector family
supports every capability hinted by a profile.
"""

from __future__ import annotations

import threading

from .models import SourceProfile


class SourceProfileRegistry:
    """Thread-safe singleton registry of ``SourceProfile`` instances.

    The registry bootstraps built-in profiles once and then serves lookup and
    enumeration APIs for connector planning and test overrides.
    """

    _instance: SourceProfileRegistry | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._profiles: dict[str, SourceProfile] = {}

    @classmethod
    def get_instance(cls) -> SourceProfileRegistry:
        """Return the singleton registry, bootstrapping built-ins if needed."""

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
        """Register a profile, optionally replacing an existing definition."""

        if profile.profile_id in self._profiles and not override:
            raise ValueError(f"Profile '{profile.profile_id}' already registered")
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> SourceProfile | None:
        """Look up one profile by identifier."""

        return self._profiles.get(profile_id)

    def list_all(self) -> list[SourceProfile]:
        """List all registered profiles sorted by ``profile_id``."""

        return sorted(self._profiles.values(), key=lambda p: p.profile_id)

    def list_by_family(self, connector_family: str) -> list[SourceProfile]:
        """List all registered profiles for one connector family."""

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
