"""
Cross-backend consistency tests: NumPy arrays vs JAX arrays as input.

Verifies that pure_step produces the same output regardless of whether
the input arrays are numpy.ndarray or jax.numpy.ndarray.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from polisyos.foundry.methods.registry import MethodRegistry

try:
    import jax.numpy as jnp
    import jax

    HAS_JAX = True
except ImportError:
    HAS_JAX = False

pytestmark = pytest.mark.skipif(not HAS_JAX, reason="JAX not available")


@pytest.fixture(scope="module")
def full_method_registry() -> MethodRegistry:
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered

    reg = MethodRegistry.get_instance()
    ensure_all_methods_registered(reg)
    return reg


def _to_jax(state: dict[str, Any]) -> dict[str, Any]:
    """Convert numpy arrays in state dict to JAX arrays."""
    result = {}
    for k, v in state.items():
        if isinstance(v, np.ndarray) and np.issubdtype(v.dtype, np.floating):
            result[k] = jnp.array(v)
        elif isinstance(v, list):
            try:
                arr = np.asarray(v, dtype=float)
                result[k] = jnp.array(arr)
            except (TypeError, ValueError):
                result[k] = v
        else:
            result[k] = v
    return result


def _extract_numerics(output: Any, path: str = "") -> dict[str, float]:
    """Flatten output to {path: float_value} for comparison."""
    results: dict[str, float] = {}
    if isinstance(output, dict):
        for k, v in output.items():
            results.update(_extract_numerics(v, f"{path}.{k}" if path else k))
    elif isinstance(output, (list, tuple)):
        for i, v in enumerate(output):
            results.update(_extract_numerics(v, f"{path}[{i}]"))
    elif isinstance(output, (int, float)):
        results[path] = float(output)
    elif isinstance(output, np.generic):
        results[path] = float(output)
    elif hasattr(output, "item"):
        try:
            results[path] = float(output.item())
        except (TypeError, ValueError):
            pass
    return results


# (fqn, state_dict, params_dict, rtol)
CROSS_BACKEND_CASES = [
    (
        "distributional.inequality.lorenz_curve@1.0.0",
        {"values": np.linspace(1, 100, 30)},
        {},
        1e-5,
    ),
    (
        "distributional.inequality.atkinson@1.0.0",
        {"values": np.linspace(1, 100, 30)},
        {"epsilon": 0.5},
        1e-5,
    ),
    (
        "distributional.inequality.generalized_entropy@1.0.0",
        {"values": np.linspace(1, 100, 30)},
        {"alpha": 1.0},
        1e-5,
    ),
    (
        "distributional.poverty.fgt@1.0.0",
        {"values": np.array([10.0, 20.0, 30.0, 60.0, 80.0]), "poverty_line": 50.0},
        {"alpha": 0.0},
        1e-5,
    ),
    (
        "distributional.inequality.theil@1.0.0",
        {"values": np.linspace(1, 50, 20)},
        {},
        1e-5,
    ),
    (
        "distributional.inequality.palma_ratio@1.0.0",
        {"values": np.linspace(1, 100, 20)},
        {},
        1e-5,
    ),
    (
        "distributional.inequality.generalized_gini@1.0.0",
        {"values": np.linspace(1, 100, 20)},
        {"nu": 2.0},
        1e-5,
    ),
    (
        "distributional.poverty.ordinal_multidimensional@1.0.0",
        {
            "category_matrix": np.array(
                [
                    [1.0, 1.0, 1.0],
                    [2.0, 2.0, 2.0],
                    [1.0, 3.0, 1.0],
                    [3.0, 1.0, 2.0],
                ]
            ),
            "weights": np.array([1 / 3, 1 / 3, 1 / 3]),
        },
        {
            "category_orders": [[1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0]],
            "deprivation_cutoffs": [2, 2, 1],
            "k_threshold": 2 / 3,
            "return_censored_scores": False,
            "return_cutoff_diagnostics": False,
        },
        1e-5,
    ),
    (
        "distributional.mobility.intergenerational_elasticity@1.0.0",
        {"parent_values": np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
         "child_values": np.array([15.0, 25.0, 35.0, 45.0, 55.0])},
        {},
        1e-5,
    ),
    (
        "sensitivity.specification.specification_curve@1.0.0",
        {"estimates": np.array([0.3, 0.5, 0.7, 0.4, 0.6]),
         "standard_errors": np.array([0.1, 0.1, 0.1, 0.1, 0.1])},
        {"significance_level": 0.05},
        1e-5,
    ),
    (
        "validation.probabilistic.normal_scores@1.0.0",
        {"observations": np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
         "predictive_mean": np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
         "predictive_std": np.array([0.5, 0.5, 0.5, 0.5, 0.5])},
        {},
        1e-4,
    ),
]


@pytest.mark.parametrize(
    "fqn,state,params,rtol",
    CROSS_BACKEND_CASES,
    ids=[c[0].split("@")[0].split(".")[-1] for c in CROSS_BACKEND_CASES],
)
def test_numpy_vs_jax_input(fqn, state, params, rtol, full_method_registry):
    """Same method called with np.array vs jnp.array → same numeric output."""
    method_cls = full_method_registry.get(fqn)

    # Run with numpy input
    np.random.seed(42)
    np_result = method_cls.pure_step(state, params)

    # Run with JAX input
    jax_state = _to_jax(state)
    np.random.seed(42)
    jax_result = method_cls.pure_step(jax_state, params)

    # Normalize outputs
    if isinstance(np_result, tuple):
        np_result = np_result[0]
    if isinstance(jax_result, tuple):
        jax_result = jax_result[0]

    np_nums = _extract_numerics(np_result)
    jax_nums = _extract_numerics(jax_result)

    for key in np_nums:
        if key not in jax_nums:
            continue
        np.testing.assert_allclose(
            np_nums[key],
            jax_nums[key],
            rtol=rtol,
            atol=1e-8,
            err_msg=f"Mismatch at {key} for {fqn}",
        )
