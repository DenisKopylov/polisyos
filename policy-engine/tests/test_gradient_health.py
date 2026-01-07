import jax.numpy as jnp

from polisyos.foundry.utils import gradient_health_report


def test_gradient_health_clipping() -> None:
    grads = jnp.array([10.0, 0.0, 0.0])
    report, clipped = gradient_health_report(grads, clip_norm=1.0)
    clipped_norm = float(jnp.linalg.norm(jnp.ravel(jnp.asarray(clipped))))
    assert report.clipped
    assert clipped_norm <= 1.0 + 1e-6
