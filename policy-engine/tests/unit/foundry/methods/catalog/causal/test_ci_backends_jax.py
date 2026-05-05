from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.causal.ci_backends import (
    partial_corr,
    partial_corr_batch,
    resolve_discovery_ci_backend,
)


def test_partial_corr_jax_matches_numpy_on_same_inputs() -> None:
    rng = np.random.default_rng(11)
    x = rng.normal(0.0, 1.0, size=512)
    z = rng.normal(0.0, 1.0, size=(512, 2))
    y = 0.8 * x + 0.3 * z[:, 0] + rng.normal(0.0, 0.3, size=512)

    corr_numpy = partial_corr(x, y, z, backend="numpy")
    corr_jax = partial_corr(x, y, z, backend="jax")

    assert np.isfinite(corr_numpy)
    assert np.isfinite(corr_jax)
    assert abs(corr_numpy - corr_jax) < 1e-5


def test_partial_corr_batch_jax_matches_numpy() -> None:
    rng = np.random.default_rng(23)
    x = rng.normal(0.0, 1.0, size=(400, 4))
    z = rng.normal(0.0, 1.0, size=(400, 3))
    y = 0.7 * x + 0.2 * z[:, :1] + rng.normal(0.0, 0.25, size=(400, 4))

    out_numpy = partial_corr_batch(x, y, z, backend="numpy")
    out_jax = partial_corr_batch(x, y, z, backend="jax")

    assert out_numpy.shape == (4,)
    assert out_jax.shape == (4,)
    assert np.max(np.abs(out_numpy - out_jax)) < 1e-5


def test_ci_backend_resolution_supports_auto_jax_and_fallback() -> None:
    auto = resolve_discovery_ci_backend("auto")
    explicit_jax = resolve_discovery_ci_backend("jax")
    bad = resolve_discovery_ci_backend("bad_backend")

    assert auto.used in {"jax", "numpy"}
    assert explicit_jax.requested == "jax"
    assert explicit_jax.used in {"jax", "numpy"}
    assert bad.used == "numpy"
    assert bad.fallback_reason is not None
