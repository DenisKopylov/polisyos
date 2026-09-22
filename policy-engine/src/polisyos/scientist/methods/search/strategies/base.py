"""Base protocols and helpers for search strategies."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    PolicyCandidate,
    StrategyState,
)


_PYTHON_RANDOM_CODEC = "python_random"
_PYTHON_RANDOM_CODEC_VERSION = 1
_PYTHON_RANDOM_STATE_VERSION = random.Random().getstate()[0]
_PYTHON_RANDOM_STATE_LENGTH = len(random.Random().getstate()[1])
_SOBOL_CODEC = "sobol_prefix"
_SOBOL_CODEC_VERSION = 1
_SOBOL_ALGORITHM = "scrambled_sobol"
_SOBOL_ALGORITHM_VERSION = 1
_SOBOL_SAMPLER_IDENTITIES = {
    "torch.quasirandom.SobolEngine",
    "scipy.stats.qmc.Sobol",
    "python.random.Random",
}
_SOBOL_FALLBACK_IDENTITY = "python.random.Random"


@runtime_checkable
class SearchStrategy(Protocol):
    """Protocol for strategy implementations."""

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        """Suggest one candidate."""

    def suggest_batch(
        self,
        evaluations: list[Evaluation],
        batch_size: int,
    ) -> list[PolicyCandidate]:
        """Suggest a batch of candidates for parallel evaluation."""

    def update(self, evaluation: Evaluation) -> None:
        """Update strategy state after receiving a finished evaluation."""

    def get_state(self) -> StrategyState:
        """Serialize strategy state for checkpointing."""

    def set_state(self, state: StrategyState) -> None:
        """Restore strategy state from checkpoint."""


class BaseSearchStrategy(ABC):
    """Common functionality for concrete strategies."""

    def __init__(self, space: SearchSpace, seed: int = 42):
        self._space = space
        self._seed = seed
        self._rng = random.Random(seed)
        self._iteration = 0
        self._sobol_cache: list[tuple[float, ...]] = []
        self._sobol_seed = seed
        self._sobol_cursor = 0
        self._sobol_sampler_identity: str | None = None
        self._sobol_sampler_version: str | None = None
        self._sobol_checkpoint_compatible = True

    @abstractmethod
    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        """Suggest one candidate."""

    def suggest_batch(
        self,
        evaluations: list[Evaluation],
        batch_size: int,
    ) -> list[PolicyCandidate]:
        candidates: list[PolicyCandidate] = []
        for _ in range(batch_size):
            candidates.append(self.suggest(evaluations, pending=candidates))
        return candidates

    def warm_start(self, evaluations: list[Evaluation]) -> None:
        """Pre-seed the strategy with historical evaluations (default: no-op).

        Subclasses override to incorporate warm-start data into their model.
        """

    def update(self, evaluation: Evaluation) -> None:
        del evaluation

    def get_state(self) -> StrategyState:
        return StrategyState(
            strategy_name=self.__class__.__name__,
            iteration=self._iteration,
            rng_state={
                "python": _encode_python_random_state(self._rng.getstate()),
                "sobol": self._sobol_state(),
            },
            metadata={
                "seed": self._seed,
                "space": self._space.sobol_space_fingerprint(),
            },
        )

    def set_state(self, state: StrategyState) -> None:
        if state.strategy_name != self.__class__.__name__:
            raise ValueError(
                "Strategy checkpoint is incompatible: strategy identity changed"
            )
        if isinstance(state.iteration, bool) or not isinstance(state.iteration, int):
            raise ValueError("Strategy iteration must be an integer")
        if not isinstance(state.rng_state, Mapping):
            raise ValueError("Strategy RNG state must be an object")
        if not isinstance(state.metadata, Mapping):
            raise ValueError("Strategy checkpoint metadata must be an object")
        checkpoint_space = state.metadata.get("space")
        if checkpoint_space is not None and checkpoint_space != (
            self._space.sobol_space_fingerprint()
        ):
            raise ValueError("Strategy checkpoint is incompatible: search space changed")
        checkpoint_seed = state.metadata.get("seed")
        if checkpoint_seed is not None and (
            isinstance(checkpoint_seed, bool) or not isinstance(checkpoint_seed, int)
        ):
            raise ValueError("Strategy checkpoint seed must be an integer")

        rng_state = state.rng_state.get("python")
        if rng_state is None:
            raise ValueError("Python random state is missing")
        decoded_python = _decode_python_random_state(rng_state)

        sobol_state = state.rng_state.get("sobol")
        if sobol_state is None:
            decoded_sobol = None
        else:
            decoded_sobol = self._validated_sobol_state(sobol_state)
        if (
            checkpoint_seed is not None
            and decoded_sobol is not None
            and decoded_sobol[0] != checkpoint_seed
        ):
            raise ValueError("Strategy checkpoint is incompatible: seed metadata changed")

        # Validate the effective sampler before changing strategy state.  An
        # importable backend may still fail at runtime and fall back, so a
        # persisted availability label is not enough for checkpoint identity.
        if decoded_sobol is not None and decoded_sobol[2]:
            (
                seed,
                cursor,
                cache,
                sampler_identity,
                sampler_version,
            ) = decoded_sobol
            assert sampler_identity is not None
            assert sampler_version is not None
            self._space.validate_sobol_sampler(
                seed=seed,
                expected_identity=sampler_identity,
                expected_version=sampler_version,
                expected_prefix=cache,
            )

        # All persisted fields and the effective sampler have now been
        # validated.  The native RNG setter is the only remaining mutating
        # validator and is expected to accept the strict codec above.
        self._rng.setstate(decoded_python)
        if checkpoint_seed is not None:
            self._seed = checkpoint_seed
        self._iteration = state.iteration
        if decoded_sobol is None:
            self._sobol_checkpoint_compatible = False
            self._sobol_cache = []
            self._sobol_cursor = 0
            self._sobol_sampler_identity = None
            self._sobol_sampler_version = None
        else:
            (
                seed,
                cursor,
                cache,
                sampler_identity,
                sampler_version,
            ) = decoded_sobol
            self._sobol_seed = seed
            self._sobol_cursor = cursor
            self._sobol_cache = cache
            self._sobol_sampler_identity = sampler_identity
            self._sobol_sampler_version = sampler_version
            self._sobol_checkpoint_compatible = True

    def _random_candidate(self, source: str = "random") -> PolicyCandidate:
        vector = tuple(self._rng.random() for _ in range(self._space.dim))
        return PolicyCandidate(
            params=self._space.denormalize(vector),
            params_normalized=vector,
            source_strategy=source,
        )

    def _sobol_candidate(self, index: int, source: str = "sobol_init") -> PolicyCandidate:
        if index < 0:
            raise ValueError(f"Sobol index must be non-negative, got {index}")
        if not self._sobol_checkpoint_compatible:
            raise ValueError(
                "Sobol checkpoint is incompatible: versioned sampler state is missing"
            )
        if index >= len(self._sobol_cache):
            generated = self._space.sample_sobol(
                n_samples=index + 1,
                seed=self._sobol_seed,
            )
            if len(generated) < index + 1:
                raise ValueError(
                    "Sobol sampler returned an incomplete prefix: "
                    f"expected {index + 1}, got {len(generated)}"
                )
            generated_prefix = [tuple(float(value) for value in vector) for vector in generated]
            sampler_identity = self._space.last_sobol_sampler_identity
            sampler_version = self._space.last_sobol_sampler_version
            if sampler_identity not in _SOBOL_SAMPLER_IDENTITIES:
                raise ValueError(
                    "Sobol sampler did not report an effective identity"
                )
            if (
                not isinstance(sampler_version, str)
                or not sampler_version
                or sampler_version.lower() == "unknown"
            ):
                raise ValueError(
                    "Sobol sampler did not report a verified implementation version"
                )
            if self._sobol_sampler_identity is not None and (
                sampler_identity != self._sobol_sampler_identity
                or sampler_version != self._sobol_sampler_version
            ):
                raise ValueError(
                    "Sobol checkpoint is incompatible: effective sampler identity changed"
                )
            if generated_prefix[: len(self._sobol_cache)] != self._sobol_cache:
                raise ValueError("Sobol checkpoint is incompatible: cached prefix diverges")
            self._sobol_cache = generated_prefix
            self._sobol_sampler_identity = sampler_identity
            self._sobol_sampler_version = sampler_version
        self._sobol_cursor = max(self._sobol_cursor, index + 1)
        vector = self._sobol_cache[index]
        return PolicyCandidate(
            params=self._space.denormalize(vector),
            params_normalized=vector,
            source_strategy=source,
        )

    def _sobol_state(self) -> dict[str, Any]:
        identity = self._sobol_sampler_identity
        version = self._sobol_sampler_version
        if bool(self._sobol_cache) != (identity is not None):
            raise ValueError("Sobol checkpoint is incompatible: sampler identity/cache mismatch")
        if identity is None:
            if version is not None:
                raise ValueError(
                    "Sobol checkpoint is incompatible: sampler version without identity"
                )
        else:
            if identity not in _SOBOL_SAMPLER_IDENTITIES:
                raise ValueError(
                    "Sobol sampler did not report an effective identity"
                )
            if (
                not isinstance(version, str)
                or not version
                or version.lower() == "unknown"
            ):
                raise ValueError(
                    "Sobol sampler did not report a verified implementation version"
                )
        fallback = identity == _SOBOL_FALLBACK_IDENTITY
        return {
            "algorithm": _SOBOL_ALGORITHM,
            "algorithm_version": _SOBOL_ALGORITHM_VERSION,
            "codec": _SOBOL_CODEC,
            "codec_version": _SOBOL_CODEC_VERSION,
            "seed": self._sobol_seed,
            "dimension": self._space.dim,
            "space": self._space.sobol_space_fingerprint(),
            "sampler_identity": identity,
            "sampler_version": version,
            "fallback": fallback,
            "scramble": (
                None
                if identity is None
                else not fallback
            ),
            "cursor": self._sobol_cursor,
            "cache": [list(vector) for vector in self._sobol_cache],
        }

    def _validated_sobol_state(
        self,
        value: Any,
    ) -> tuple[int, int, list[tuple[float, ...]], str | None, str | None]:
        if not isinstance(value, Mapping):
            raise ValueError("Sobol checkpoint is incompatible: state must be an object")
        expected_keys = {
            "algorithm",
            "algorithm_version",
            "cache",
            "codec",
            "codec_version",
            "cursor",
            "dimension",
            "fallback",
            "sampler_identity",
            "sampler_version",
            "seed",
            "scramble",
            "space",
        }
        if set(value) != expected_keys:
            raise ValueError("Sobol checkpoint is incompatible: state fields changed")
        if value.get("codec") != _SOBOL_CODEC:
            raise ValueError("Sobol checkpoint is incompatible: unknown codec")
        if value.get("codec_version") != _SOBOL_CODEC_VERSION:
            raise ValueError("Sobol checkpoint is incompatible: unsupported codec version")
        if value.get("algorithm") != _SOBOL_ALGORITHM:
            raise ValueError("Sobol checkpoint is incompatible: unknown algorithm")
        if value.get("algorithm_version") != _SOBOL_ALGORITHM_VERSION:
            raise ValueError(
                "Sobol checkpoint is incompatible: unsupported algorithm version"
            )

        seed = value.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("Sobol checkpoint is incompatible: seed must be an integer")
        if value.get("dimension") != self._space.dim:
            raise ValueError("Sobol checkpoint is incompatible: search-space dimension changed")
        if value.get("space") != self._space.sobol_space_fingerprint():
            raise ValueError("Sobol checkpoint is incompatible: search space changed")

        sampler_identity = value.get("sampler_identity")
        sampler_version = value.get("sampler_version")
        if sampler_identity is None:
            if sampler_version is not None:
                raise ValueError(
                    "Sobol checkpoint is incompatible: sampler version without identity"
                )
            if value.get("fallback") is not False or value.get("scramble") is not None:
                raise ValueError(
                    "Sobol checkpoint is incompatible: uninitialized sampler metadata"
                )
        else:
            if (
                not isinstance(sampler_identity, str)
                or sampler_identity not in _SOBOL_SAMPLER_IDENTITIES
            ):
                raise ValueError(
                    "Sobol checkpoint is incompatible: effective sampler identity is missing"
                )
            if (
                not isinstance(sampler_version, str)
                or not sampler_version
                or sampler_version.lower() == "unknown"
            ):
                raise ValueError(
                    "Sobol checkpoint is incompatible: sampler version is missing or unknown"
                )
            expected_fallback = sampler_identity == _SOBOL_FALLBACK_IDENTITY
            if value.get("fallback") is not expected_fallback:
                raise ValueError(
                    "Sobol checkpoint is incompatible: fallback mode changed"
                )
            expected_scramble = not expected_fallback
            if value.get("scramble") is not expected_scramble:
                raise ValueError("Sobol checkpoint is incompatible: scramble mode changed")

        cursor = value.get("cursor")
        if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
            raise ValueError("Sobol checkpoint is incompatible: cursor must be non-negative")
        cache_value = value.get("cache")
        if not isinstance(cache_value, list):
            raise ValueError("Sobol checkpoint is incompatible: cache must be a list")

        cache: list[tuple[float, ...]] = []
        for vector in cache_value:
            if not isinstance(vector, list):
                raise ValueError("Sobol checkpoint is incompatible: cache vector must be a list")
            if len(vector) != self._space.dim:
                raise ValueError("Sobol checkpoint is incompatible: cache dimension changed")
            normalized: list[float] = []
            for coordinate in vector:
                if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
                    raise ValueError(
                        "Sobol checkpoint is incompatible: cache coordinate must be numeric"
                    )
                coordinate_float = float(coordinate)
                if not 0.0 <= coordinate_float <= 1.0:
                    raise ValueError(
                        "Sobol checkpoint is incompatible: cache coordinate out of range"
                    )
                normalized.append(coordinate_float)
            cache.append(tuple(normalized))
        if cursor != len(cache):
            raise ValueError("Sobol checkpoint is incompatible: cursor/cache mismatch")

        if bool(cache) != (sampler_identity is not None):
            raise ValueError(
                "Sobol checkpoint is incompatible: sampler identity/cache mismatch"
            )

        return seed, cursor, cache, sampler_identity, sampler_version


def _encode_python_random_state(state: tuple[Any, ...]) -> dict[str, Any]:
    version, internal_state, gauss_next = _validate_python_random_state(state)
    return {
        "codec": _PYTHON_RANDOM_CODEC,
        "codec_version": _PYTHON_RANDOM_CODEC_VERSION,
        "version": version,
        "state": list(internal_state),
        "gauss_next": gauss_next,
    }


def _decode_python_random_state(value: Any) -> tuple[int, tuple[int, ...], float | None]:
    if isinstance(value, tuple):
        return _validate_python_random_state(value)
    if not isinstance(value, Mapping):
        raise ValueError(
            "Python random state codec is missing; expected a versioned state object"
        )
    expected_keys = {"codec", "codec_version", "gauss_next", "state", "version"}
    if set(value) != expected_keys:
        raise ValueError("Python random state codec fields are incompatible")
    if value.get("codec") != _PYTHON_RANDOM_CODEC:
        raise ValueError("Python random state codec is incompatible")
    if value.get("codec_version") != _PYTHON_RANDOM_CODEC_VERSION:
        raise ValueError("Python random state codec version is unsupported")
    version = value.get("version")
    internal_state = value.get("state")
    gauss_next = value.get("gauss_next")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("Python random state version is missing or invalid")
    if version != _PYTHON_RANDOM_STATE_VERSION:
        raise ValueError(
            "Python random state version "
            f"{version} is unsupported; expected {_PYTHON_RANDOM_STATE_VERSION}"
        )
    if not isinstance(internal_state, list):
        raise ValueError("Python random state vector must be a JSON list")
    decoded = tuple(internal_state)
    if gauss_next is not None and (
        isinstance(gauss_next, bool) or not isinstance(gauss_next, (int, float))
    ):
        raise ValueError("Python random gaussian state must be numeric or null")
    return _validate_python_random_state((version, decoded, gauss_next))


def _validate_python_random_state(state: Any) -> tuple[int, tuple[int, ...], float | None]:
    if not isinstance(state, tuple) or len(state) != 3:
        raise ValueError("Python random state must be a three-item tuple")
    version, internal_state, gauss_next = state
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("Python random state version is missing or invalid")
    if version != _PYTHON_RANDOM_STATE_VERSION:
        raise ValueError(
            "Python random state version "
            f"{version} is unsupported; expected {_PYTHON_RANDOM_STATE_VERSION}"
        )
    if not isinstance(internal_state, tuple) or len(internal_state) != _PYTHON_RANDOM_STATE_LENGTH:
        raise ValueError("Python random state vector has an incompatible shape")
    if any(
        isinstance(item, bool) or not isinstance(item, int) or not 0 <= item < 2**32
        for item in internal_state
    ):
        raise ValueError("Python random state vector contains an invalid value")
    if gauss_next is not None and (
        isinstance(gauss_next, bool) or not isinstance(gauss_next, (int, float))
    ):
        raise ValueError("Python random gaussian state must be numeric or null")
    return version, internal_state, gauss_next
