from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy.testing as npt
import pytest

from polisyos.foundry.calibration.auxiliary import InterferenceLossComponent
from polisyos.ir.observation.bundles import InterferenceLossSpecBundle


def test_interference_loss_component_supports_gradient_flow() -> None:
    component = InterferenceLossComponent(
        InterferenceLossSpecBundle(
            specs=[
                {
                    "spec_id": "procurement_spillover",
                    "family": "procurement_flows",
                    "graph_layer": "procurement",
                    "predicted_metric_path": "metrics.procurement_spillover",
                    "observed_spillover": [0.4, 0.1],
                    "adjacency": [[0.0, 1.0], [1.0, 0.0]],
                    "trust_weight": [1.0, 1.0],
                    "coverage_estimate": [1.0, 1.0],
                }
            ]
        )
    )

    def _loss(x: jnp.ndarray) -> jnp.ndarray:
        loss, _ = component.compute(traces={"metrics.procurement_spillover": x})
        return loss

    grad = jax.grad(_loss)(jnp.asarray([0.1, 0.9], dtype=jnp.float32))

    assert jnp.all(jnp.isfinite(grad))
    assert float(jnp.linalg.norm(grad)) > 0.0


@pytest.mark.parametrize("quality", [1.0, 1e-9])
def test_auxiliary_sample_quality_scale_preserves_actual_penalty(quality) -> None:
    """The shared normalized reducer keeps an auxiliary positive measure meaningful."""
    component = InterferenceLossComponent(
        InterferenceLossSpecBundle(
            specs=[
                {
                    "spec_id": "bounded_quality",
                    "family": "procurement_flows",
                    "graph_layer": "procurement",
                    "predicted_metric_path": "metrics.spillover",
                    "observed_spillover": [0.0, 0.0],
                    "adjacency": [[1.0, 0.0], [0.0, 1.0]],
                    "normalization": "none",
                    "trust_weight": [quality, quality],
                    "coverage_estimate": [1.0, 1.0],
                }
            ]
        )
    )

    def objective(values):
        return component.compute(traces={"metrics.spillover": values})[0]

    values = jnp.asarray([1.0, 3.0], dtype=jnp.float32)
    npt.assert_allclose(objective(values), 5.0, rtol=1e-6, atol=1e-6)
    npt.assert_allclose(jax.grad(objective)(values), [1.0, 3.0], rtol=1e-6, atol=1e-6)
