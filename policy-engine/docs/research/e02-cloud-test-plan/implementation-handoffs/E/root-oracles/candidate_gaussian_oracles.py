"""Independent numerical properties on an explicitly selected candidate source.

Run with the candidate backend environment and an absolute policy-engine root:
    python candidate_gaussian_oracles.py /path/to/checkout/policy-engine
Prints observed numbers; never establishes production input or served authority.
"""

import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
if not (root / "src/polisyos").is_dir():
    raise ValueError("argument must be the policy-engine root")
sys.path.insert(0, str(root / "src"))
import jax, jax.numpy as jnp, numpy as np
from polisyos.foundry.calibration.loss import reduce_weighted_loss
from polisyos.foundry.calibration.hessian import compute_hessian
from polisyos.foundry.uncertainty.covariance import build_covariance_matrix
from polisyos.foundry.uncertainty import monte_carlo as candidate_module
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator

assert pathlib.Path(candidate_module.__file__).resolve().is_relative_to(root / "src")
print(
    json.dumps(
        {
            "candidate_source": str(root),
            "monte_carlo_module": candidate_module.__file__,
            "jax": jax.__version__,
            "jax_x64": jax.config.jax_enable_x64,
            "backend": jax.default_backend(),
        }
    )
)
from polisyos.foundry.uncertainty.config import PropagationConfig, AdaptiveStoppingConfig
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    ParametricFitCarrier,
)


def envelope(point, std, row=None, order=None):
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


def record(name, **kwargs):
    row = {"oracle": name, **kwargs}
    evidence.append(row)
    print(json.dumps(row))


x = jnp.array([1.0, -2.0, 3.0], dtype=jnp.float32)
w = jnp.zeros_like(x)
f = lambda v: reduce_weighted_loss(v * v, w)
v = float(f(x))
g = np.asarray(jax.grad(f)(x))
h = np.asarray(jax.hessian(f)(x))
assert v == 0 and np.array_equal(g, np.zeros(3)) and np.array_equal(h, np.zeros((3, 3)))
bad = lambda v: jnp.where(jnp.sum(w) > 0, jnp.sum(v * v * w) / jnp.sum(w), 0.0)
bad_grad = np.asarray(jax.grad(bad)(x))
assert not np.isfinite(bad_grad).all()
record(
    "B181 zero support JAX primal/gradient/Hessian",
    value=v,
    gradient=g.tolist(),
    hessian=h.tolist(),
    negative_proxy_value=float(bad(x)),
    negative_proxy_gradient_finite=bool(np.isfinite(bad_grad).all()),
)

A = jnp.array([[4.0, 1.0, 0.3], [1.0, 3.0, -0.2], [0.3, -0.2, 2.0]])
quadratic = lambda v: 0.5 * v @ A @ v
result = compute_hessian(quadratic, x, ["a", "b", "c"], damping=0, jitter_floor=1e-12)
np.testing.assert_allclose(result.hessian, A, atol=1e-6)
np.testing.assert_allclose(result.covariance, np.linalg.inv(A), atol=1e-6)
record(
    "CAL true JAX Hessian/covariance",
    hessian_max_error=float(np.max(np.abs(result.hessian - A))),
    covariance_max_error=float(np.max(np.abs(result.covariance - np.linalg.inv(A)))),
    backend=jax.default_backend(),
)

Sigma = np.array([[1.0, 0.2, -0.1], [0.2, 4.0, 0.6], [-0.1, 0.6, 9.0]])
names = ["a", "b", "c"]
columns = ["c", "a", "b"]
idx = [2, 0, 1]
envs = {
    name: envelope(0, np.sqrt(Sigma[i, i]), Sigma[i, idx].tolist(), columns)
    for i, name in enumerate(names)
}
cov = np.asarray(build_covariance_matrix(names, envs, use_full_covariance=True, jitter=0))
np.testing.assert_allclose(cov, Sigma, atol=1e-6)
proxy = Sigma[np.ix_(idx, idx)]
assert not np.allclose(proxy, Sigma)
record(
    "B187 covariance 3 distinct axes",
    computed=cov.tolist(),
    expected=Sigma.tolist(),
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
    assert np.all(correlated_samples == 0), "joint draw support lost"
    assert abs(float(np.var(independent_samples)) - 2) < 0.3, (
        "independent negative control collapsed"
    )
    assert correlated.envelope.gate_eligible is False, "declared law gained authority"
    record(
        "B188 Gaussian shared difference",
        method=method,
        shared_variance=float(np.var(correlated_samples)),
        independent_control_variance=float(np.var(independent_samples)),
        shared_draws_zero=bool(np.all(correlated_samples == 0)),
        max_abs_shared=float(np.max(np.abs(correlated_samples))),
        baseline_gap=bool(np.any(correlated_samples != 0)),
    )
print(json.dumps({"oracle_count": len(evidence), "result": "PASS"}))
