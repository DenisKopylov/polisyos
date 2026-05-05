from __future__ import annotations

import jax
import jax.numpy as jnp
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
