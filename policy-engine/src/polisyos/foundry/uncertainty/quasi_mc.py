"""Public uncertainty quasi mc module API."""

from __future__ import annotations

import math

import numpy as np


class QuasiMCSampler:
    """Low-discrepancy sequence sampler for uncertainty propagation."""

    def __init__(
        self,
        method: str = "sobol",
        scramble: bool = True,
        seed: int = 42,
    ) -> None:
        if method not in ("sobol", "halton"):
            raise ValueError(f"Unknown QMC method: {method!r}. Use 'sobol' or 'halton'.")
        self.method = method
        self.scramble = scramble
        self.seed = seed

    def sample(self, n_samples: int, n_dims: int) -> np.ndarray:
        """Generate quasi-random samples in [0, 1]^n_dims.

        Returns array of shape ``(n_samples, n_dims)``.
        Sobol returns the entire next power-of-two net, including the rounded
        tail. Its effective row count can exceed the requested count.
        """
        if n_dims < 1:
            raise ValueError(f"n_dims must be >= 1, got {n_dims}")
        if n_samples < 1:
            raise ValueError(f"n_samples must be >= 1, got {n_samples}")

        if self.method == "sobol":
            from scipy.stats.qmc import Sobol

            # Sobol requires n = 2^m
            m = math.ceil(math.log2(n_samples))
            sampler = Sobol(d=n_dims, scramble=self.scramble, seed=self.seed)
            return sampler.random_base2(m)

        # halton
        from scipy.stats.qmc import Halton

        sampler = Halton(d=n_dims, scramble=self.scramble, seed=self.seed)
        return sampler.random(n_samples)
