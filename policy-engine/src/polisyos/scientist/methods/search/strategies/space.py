"""Search-space definition and parameter normalization helpers."""

from __future__ import annotations

import hashlib
import math
import platform
import random
from dataclasses import dataclass, field
from typing import Any

from polisyos.scientist.methods.search.strategies._deps import require_torch, torch
from polisyos.scientist.methods.search.strategies.types import (
    NormalizedVector,
    ParameterBounds,
    ParameterType,
    PolicyCandidate,
)


@dataclass(slots=True)
class SearchSpace:
    """
    Multi-dimensional search space with normalization support.

    Categorical parameters are expanded to one-hot dimensions for surrogate compatibility.
    """

    bounds: list[ParameterBounds] = field(default_factory=list)
    _expanded: list[tuple[ParameterBounds, int | None]] = field(
        init=False,
        repr=False,
        default_factory=list,
    )
    _last_sobol_sampler_identity: str | None = field(
        init=False,
        repr=False,
        default=None,
    )
    _last_sobol_sampler_version: str | None = field(
        init=False,
        repr=False,
        default=None,
    )

    def __post_init__(self) -> None:
        if not self.bounds:
            raise ValueError("SearchSpace must contain at least one parameter")
        self._expanded.clear()
        if len({bound.name for bound in self.bounds}) != len(self.bounds):
            raise ValueError("SearchSpace parameter names must be unique")
        for bound in self.bounds:
            if bound.dtype == ParameterType.CATEGORICAL:
                assert bound.categories is not None
                for idx in range(len(bound.categories)):
                    self._expanded.append((bound, idx))
            else:
                self._expanded.append((bound, None))

    @property
    def dim(self) -> int:
        return len(self._expanded)

    @property
    def names(self) -> list[str]:
        output: list[str] = []
        for bound, cat_idx in self._expanded:
            if cat_idx is None:
                output.append(bound.name)
            else:
                output.append(f"{bound.name}__{cat_idx}")
        return output

    def normalize(self, params: dict[str, Any]) -> NormalizedVector:
        values: list[float] = []
        for bound in self.bounds:
            if bound.dtype == ParameterType.CATEGORICAL:
                assert bound.categories is not None
                raw = params.get(bound.name)
                matches = [
                    type(raw) is type(candidate) and raw == candidate
                    for candidate in bound.categories
                ]
                if sum(matches) != 1:
                    raise ValueError(
                        f"Unknown category '{raw}' for parameter '{bound.name}'. "
                        f"Allowed: {bound.categories}"
                    )
                values.extend(1.0 if match else 0.0 for match in matches)
                continue
            value = params.get(bound.name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"Finite physical parameter required for '{bound.name}'")
            raw = float(value)
            if not bound.lower <= raw <= bound.upper:
                raise ValueError(f"Physical parameter '{bound.name}' is outside bounds")
            if bound.dtype == ParameterType.INTEGER and raw != int(raw):
                raise ValueError(f"Integer parameter required for '{bound.name}'")
            if bound.log_scale or bound.dtype == ParameterType.LOG_CONTINUOUS:
                log_lower = math.log(bound.lower)
                log_upper = math.log(bound.upper)
                raw = min(max(raw, bound.lower), bound.upper)
                raw_norm = (math.log(raw) - log_lower) / (log_upper - log_lower)
            else:
                raw_clipped = min(max(raw, bound.lower), bound.upper)
                raw_norm = (raw_clipped - bound.lower) / (bound.upper - bound.lower)
            values.append(float(min(max(raw_norm, 0.0), 1.0)))
        return tuple(values)

    def denormalize(self, vector: NormalizedVector) -> dict[str, Any]:
        if len(vector) != self.dim:
            raise ValueError(f"Expected vector length {self.dim}, got {len(vector)}")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in vector
        ):
            raise ValueError("Normalized coordinates must be finite numbers")

        params: dict[str, Any] = {}
        cursor = 0
        for bound in self.bounds:
            if bound.dtype == ParameterType.CATEGORICAL:
                assert bound.categories is not None
                chunk = vector[cursor : cursor + len(bound.categories)]
                if not chunk:
                    raise ValueError(f"Empty categorical chunk for '{bound.name}'")
                idx = max(range(len(chunk)), key=lambda i: chunk[i])
                params[bound.name] = bound.categories[idx]
                cursor += len(bound.categories)
                continue

            normalized = float(min(max(vector[cursor], 0.0), 1.0))
            if bound.log_scale or bound.dtype == ParameterType.LOG_CONTINUOUS:
                log_lower = math.log(bound.lower)
                log_upper = math.log(bound.upper)
                value = math.exp(log_lower + normalized * (log_upper - log_lower))
            else:
                value = bound.lower + normalized * (bound.upper - bound.lower)
            if bound.dtype == ParameterType.INTEGER:
                params[bound.name] = min(
                    math.floor(bound.upper), max(math.ceil(bound.lower), int(round(value)))
                )
            else:
                params[bound.name] = float(value)
            cursor += 1
        return params

    def candidate_from_vector(self, vector: NormalizedVector, **fields: Any) -> PolicyCandidate:
        """Bind the surrogate point to the action actually executed."""
        params = self.denormalize(vector)
        metadata = dict(fields.pop("metadata", {}))
        metadata["relaxed_proposal"] = list(vector)
        return PolicyCandidate(
            params=params, params_normalized=self.normalize(params), metadata=metadata, **fields
        )

    def sobol_backend(self) -> str:
        """Return the import-time backend preference for diagnostics only.

        Checkpoints persist the effective implementation recorded by
        :meth:`sample_sobol`, never this availability probe.
        """

        if torch is not None:  # pragma: no cover - environment dependent
            return "torch"
        try:
            from scipy.stats.qmc import Sobol  # type: ignore[import-not-found]
        except Exception:
            return "python"
        return "scipy"

    def sobol_space_fingerprint(self) -> str:
        """Return an identity for the bounds used by the Sobol stream."""

        signature = tuple(
            (
                bound.name,
                float(bound.lower),
                float(bound.upper),
                bound.dtype.value,
                bool(bound.log_scale),
                repr(bound.categories),
            )
            for bound in self.bounds
        )
        return hashlib.sha256(
            repr(("attainable_projection.v1", signature)).encode("utf-8")
        ).hexdigest()

    def same_execution(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        """Compare executed actions in their canonical typed coordinate domain."""
        try:
            return self.normalize(left) == self.normalize(right)
        except (TypeError, ValueError):
            return False

    @property
    def last_sobol_sampler_identity(self) -> str | None:
        """Return the implementation that produced the most recent samples."""

        return self._last_sobol_sampler_identity

    @property
    def last_sobol_sampler_version(self) -> str | None:
        """Return the implementation version for the most recent samples."""

        return self._last_sobol_sampler_version

    def validate_sobol_sampler(
        self,
        *,
        seed: int,
        expected_identity: str,
        expected_version: str,
        expected_prefix: list[NormalizedVector],
    ) -> None:
        """Validate the effective sampler before resuming a persisted prefix.

        Backend availability is not sufficient here: a library can import while
        its runtime path fails and falls back to the standard-library stream.
        Generate the complete persisted prefix once so both the identity and
        every cached point reflect the implementation that actually executed.
        """

        probe = SearchSpace(list(self.bounds))
        generated = probe.sample_sobol(n_samples=len(expected_prefix), seed=seed)
        actual_identity = probe.last_sobol_sampler_identity
        actual_version = probe.last_sobol_sampler_version
        if actual_identity != expected_identity or actual_version != expected_version:
            raise ValueError("Sobol checkpoint is incompatible: effective sampler identity changed")
        if generated != expected_prefix:
            raise ValueError("Sobol checkpoint is incompatible: cached prefix diverges")

    def sample_sobol(self, n_samples: int, seed: int = 42) -> list[NormalizedVector]:
        if n_samples <= 0:
            return []

        if torch is not None:  # pragma: no branch
            try:
                local_torch = require_torch()
                sobol_engine = local_torch.quasirandom.SobolEngine(
                    self.dim,
                    scramble=True,
                    seed=seed,
                )
                tensor = sobol_engine.draw(n_samples).tolist()
                self._record_sobol_sampler(
                    "torch.quasirandom.SobolEngine",
                    str(getattr(local_torch, "__version__", "unknown")),
                )
                return [tuple(float(v) for v in row) for row in tensor]
            except Exception:
                # A present import is not proof that the native sampler can
                # execute.  Continue through the same identity-recording path
                # as the other runtime fallbacks.
                pass

        try:
            import scipy  # type: ignore[import-not-found]
            from scipy.stats.qmc import Sobol  # type: ignore[import-not-found]

            qmc = Sobol(d=self.dim, scramble=True, seed=seed)
            samples = qmc.random(n=n_samples).tolist()
            self._record_sobol_sampler(
                "scipy.stats.qmc.Sobol",
                str(getattr(scipy, "__version__", "unknown")),
            )
            return [tuple(float(v) for v in row) for row in samples]
        except Exception:
            rng = random.Random(seed)
            self._record_sobol_sampler(
                "python.random.Random",
                platform.python_version(),
            )
            return [tuple(rng.random() for _ in range(self.dim)) for _ in range(n_samples)]

    def _record_sobol_sampler(self, identity: str, version: str) -> None:
        self._last_sobol_sampler_identity = identity
        self._last_sobol_sampler_version = version

    def to_botorch_bounds(self) -> Any:
        local_torch = require_torch()
        return local_torch.stack(
            [
                local_torch.zeros(self.dim, dtype=local_torch.float64),
                local_torch.ones(self.dim, dtype=local_torch.float64),
            ],
            dim=0,
        )
