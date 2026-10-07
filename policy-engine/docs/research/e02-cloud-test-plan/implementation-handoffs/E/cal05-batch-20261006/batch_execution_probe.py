"""Replay numeric batch execution and its property-removal discriminator.

Run from policy-engine with PYTHONPATH=src using the admitted JAX environment.
The fixture comes from the tracked native test; the independent oracle is the
analytic derivative of x + log(x), with an identity inactive row.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.foundry.calibration import pure_executor

if TYPE_CHECKING:
    from polisyos.foundry.contracts.state import GlobalState


def main() -> None:
    """Emit actual numerical values and callback observations as JSON lines."""
    spec = importlib.util.spec_from_file_location(
        "batch_fixture", Path("tests/unit/foundry/calibration/test_pure_executor_batch.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("tracked batch fixture could not be loaded")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    observed: list[list[float]] = []

    class LogEmitter:
        def emit_patches(
            self,
            state: GlobalState,
            key: jax.Array,
            *,
            target_mask: jax.Array | None = None,
        ) -> tuple[dict[str, Any], jax.Array]:
            del target_mask
            jax.debug.callback(lambda x: observed.append(x.tolist()), state.agents.income)
            return {"agents.income": [{"delta": jnp.log(state.agents.income)}]}, key

    bundle = fixture._bundle(LogEmitter())
    times = jnp.array([0, 1], dtype=jnp.int32)
    income = jnp.array([[-1.0], [2.0]], dtype=jnp.float32)

    def run(x: jax.Array) -> jax.Array:
        return fixture._run(x, times, bundle)[1]["agents.income"]

    for transform in ["eager", "jit", "grad", "hessian"]:
        observed.clear()
        actual = fixture._transform(run, income, transform)
        expected = {
            "eager": [[-1.0], [2.0 + np.log(2.0)]],
            "jit": [[-1.0], [2.0 + np.log(2.0)]],
            "grad": [[1.0], [1.5]],
            "hessian": np.diag([0.0, -0.25]).reshape(2, 1, 2, 1),
        }[transform]
        np.testing.assert_allclose(actual, expected, rtol=1e-6)
        if observed != [[2.0]]:
            raise RuntimeError(f"inactive numerical emission under {transform}: {observed}")
        sys.stdout.write(
            json.dumps(
                {
                    "case": "scalar_map_" + transform,
                    "backend": jax.default_backend(),
                    "dtype": str(actual.dtype),
                    "actual": actual.tolist(),
                    "numerical_emissions": observed,
                    "outcome": "PASS",
                }
            )
            + "\n"
        )
    original_map = pure_executor.jax.lax.map
    original_admission = pure_executor._admit_schedule_predicate
    try:
        pure_executor.jax.lax.map = lambda fn, xs: jax.vmap(fn)(xs)
        pure_executor._admit_schedule_predicate = lambda active: active
        observed.clear()
        actual = run(income)
        actual.block_until_ready()
        jax.effects_barrier()
        if not np.all(np.isfinite(actual)) or observed != [[-1.0], [2.0]]:
            raise RuntimeError("property-removal discriminator did not execute as expected")
        sys.stdout.write(
            json.dumps(
                {
                    "case": "remove_scalar_map_and_mapped_guard_keep_markers",
                    "actual": actual.tolist(),
                    "numerical_emissions": observed,
                    "finite_state_proxy": "PASS",
                    "no_inactive_numerical_emission": "FAIL",
                    "control_detected": "PASS",
                }
            )
            + "\n"
        )
    finally:
        pure_executor.jax.lax.map = original_map
        pure_executor._admit_schedule_predicate = original_admission


if __name__ == "__main__":
    main()
