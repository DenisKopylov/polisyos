"""ModelProfileRegistry — in-memory registry of available model profiles."""

from __future__ import annotations

import threading

from .models import ModelProfile


class ModelProfileRegistry:
    """Thread-safe singleton registry of model profiles."""

    _instance: ModelProfileRegistry | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._profiles: dict[str, ModelProfile] = {}

    @classmethod
    def get_instance(cls) -> ModelProfileRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = cls()
                    inst._bootstrap()
                    cls._instance = inst
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def register(self, profile: ModelProfile, *, override: bool = False) -> None:
        if profile.profile_id in self._profiles and not override:
            raise ValueError(f"Model profile '{profile.profile_id}' already registered")
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> ModelProfile | None:
        return self._profiles.get(profile_id)

    def list_all(self) -> list[ModelProfile]:
        return sorted(self._profiles.values(), key=lambda p: p.profile_id)

    def list_by_provider(self, provider: str) -> list[ModelProfile]:
        return [p for p in self._profiles.values() if p.provider == provider]

    def _bootstrap(self) -> None:
        from .builtin_profiles import BUILTIN_MODEL_PROFILES

        for profile in BUILTIN_MODEL_PROFILES:
            self.register(profile)


__all__ = ["ModelProfileRegistry"]
