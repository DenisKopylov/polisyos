"""Independent numerical properties on an explicitly selected candidate source.

Run with the candidate backend environment and an absolute policy-engine root:
    python candidate_gaussian_oracles.py /path/to/checkout/policy-engine
Prints observed numbers; never establishes production input or served authority.
"""

from __future__ import annotations

import json
import pathlib
import sys


def require(condition: bool, message: str) -> None:
    """Check an observed numerical property even when Python optimizations are enabled."""
    if not condition:
        raise AssertionError(message)


def main() -> None:
    root = pathlib.Path(sys.argv[1]).resolve()
    if not (root / "src/polisyos").is_dir():
        raise ValueError("argument must be the policy-engine root")
    sys.path.insert(0, str(root / "src"))
    import jax
    import jax.numpy as jnp
    import numpy as np

    from polisyos.foundry.calibration.hessian import compute_hessian
    from polisyos.foundry.calibration.loss import reduce_weighted_loss
    from polisyos.foundry.uncertainty import monte_carlo as candidate_module
    from polisyos.foundry.uncertainty.covariance import build_covariance_matrix
    from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator

    require(
        pathlib.Path(candidate_module.__file__).resolve().is_relative_to(root / "src"),
        "foreign candidate source",
    )
    sys.stdout.write(
        json.dumps(
            {
                "candidate_source": str(root),
                "monte_carlo_module": candidate_module.__file__,
                "jax": jax.__version__,
                "jax_x64": jax.config.jax_enable_x64,
                "backend": jax.default_backend(),
            }
        )
        + "\n"
    )
    from polisyos.foundry.uncertainty.config import PropagationConfig
    from polisyos.ir.analytics.uncertainty import (
        DistributionFamily,
        IntervalSemantics,
        ParametricFitCarrier,
        PropagationMethod,
        UncertaintyEnvelope,
        UncertaintySource,
    )

    def envelope(
        point: float,
        std: float,
        row: list[float] | None = None,
        order: list[str] | None = None,
    ) -> UncertaintyEnvelope:
        metadata = {} if row is None else {"covariance_row": row, "covariance_params": order}
        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(point - 1.96 * std, point + 1.96 * std),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            gate_eligible=True,
            distribution_payload=ParametricFitCarrier(
                family=DistributionFamily.NORMAL, parameters={"mean": point, "std": std}
            ),
            metadata=metadata,
        )

    evidence = []

    def record(name: str, **kwargs: object) -> None:
        row = {"oracle": name, **kwargs}
        evidence.append(row)
        sys.stdout.write(json.dumps(row) + "\n")

    x = jnp.array([1.0, -2.0, 3.0], dtype=jnp.float32)
    w = jnp.zeros_like(x)

    def f(v: jax.Array) -> jax.Array:
        return reduce_weighted_loss(v * v, w)

    v = float(f(x))
    g = np.asarray(jax.grad(f)(x))
    h = np.asarray(jax.hessian(f)(x))
    require(v == 0, "nonzero zero-support loss")
    require(np.array_equal(g, np.zeros(3)), "nonzero zero-support gradient")
    require(np.array_equal(h, np.zeros((3, 3))), "nonzero zero-support Hessian")

    def bad(v: jax.Array) -> jax.Array:
        return jnp.where(jnp.sum(w) > 0, jnp.sum(v * v * w) / jnp.sum(w), 0.0)

    bad_grad = np.asarray(jax.grad(bad)(x))
    require(not np.isfinite(bad_grad).all(), "unsafe negative control unexpectedly finite")
    record(
        "B181 zero support JAX primal/gradient/Hessian",
        value=v,
        gradient=g.tolist(),
        hessian=h.tolist(),
        negative_proxy_value=float(bad(x)),
        negative_proxy_gradient_finite=bool(np.isfinite(bad_grad).all()),
    )

    curvature = jnp.array([[4.0, 1.0, 0.3], [1.0, 3.0, -0.2], [0.3, -0.2, 2.0]])

    def quadratic(v: jax.Array) -> jax.Array:
        return 0.5 * v @ curvature @ v

    result = compute_hessian(quadratic, x, ["a", "b", "c"], damping=0, jitter_floor=1e-12)
    np.testing.assert_allclose(result.hessian, curvature, atol=1e-6)
    np.testing.assert_allclose(result.covariance, np.linalg.inv(curvature), atol=1e-6)
    record(
        "CAL true JAX Hessian/covariance",
        hessian_max_error=float(np.max(np.abs(result.hessian - curvature))),
        covariance_max_error=float(np.max(np.abs(result.covariance - np.linalg.inv(curvature)))),
        backend=jax.default_backend(),
    )

    sigma = np.array([[1.0, 0.2, -0.1], [0.2, 4.0, 0.6], [-0.1, 0.6, 9.0]])
    names = ["a", "b", "c"]
    columns = ["c", "a", "b"]
    idx = [2, 0, 1]
    envs = {
        name: envelope(0, np.sqrt(sigma[i, i]), sigma[i, idx].tolist(), columns)
        for i, name in enumerate(names)
    }
    cov = np.asarray(build_covariance_matrix(names, envs, use_full_covariance=True, jitter=0))
    np.testing.assert_allclose(cov, sigma, atol=1e-6)
    proxy = sigma[np.ix_(idx, idx)]
    require(not np.allclose(proxy, sigma), "axis negative control not distinct")
    record(
        "B187 covariance 3 distinct axes",
        computed=cov.tolist(),
        expected=sigma.tolist(),
        negative_row_column_permutation=proxy.tolist(),
    )

    for method in ["random", "sobol", "halton"]:
        common = {"a": envelope(0, 1, [1, 1], ["a", "b"]), "b": envelope(0, 1, [1, 1], ["a", "b"])}
        config = PropagationConfig(
            mc_n_samples=512,
            mc_batch_size=128,
            mc_sampling_method=method,
            mc_seed=19,
            compute_sensitivity=False,
            mc_min_valid_samples=20,
        )
        correlated = MonteCarloPropagator(config).propagate(
            lambda **p: {"y": p["a"] - p["b"]}, {"a": 0.0, "b": 0.0}, common, ["y"]
        )[0]
        independent = MonteCarloPropagator(config).propagate(
            lambda **p: {"y": p["a"] - p["b"]},
            {"a": 0.0, "b": 0.0},
            {"a": envelope(0, 1), "b": envelope(0, 1)},
            ["y"],
        )[0]
        correlated_samples = np.asarray(correlated.envelope.distribution_payload.samples)
        independent_samples = np.asarray(independent.envelope.distribution_payload.samples)
        require(bool(np.all(correlated_samples == 0)), "joint draw support lost")
        require(
            abs(float(np.var(independent_samples)) - 2) < 0.3,
            "independent negative control collapsed",
        )
        require(correlated.envelope.gate_eligible is False, "declared law gained authority")
        record(
            "B188 Gaussian shared difference",
            method=method,
            shared_variance=float(np.var(correlated_samples)),
            independent_control_variance=float(np.var(independent_samples)),
            shared_draws_zero=bool(np.all(correlated_samples == 0)),
            max_abs_shared=float(np.max(np.abs(correlated_samples))),
            baseline_gap=bool(np.any(correlated_samples != 0)),
        )
    sys.stdout.write(json.dumps({"oracle_count": len(evidence), "result": "PASS"}) + "\n")


if __name__ == "__main__":
    main()
