"""Map bounded trainable parameters to unconstrained optimizer coordinates.

`Calibrator` optimizes in unconstrained space and then projects values back to
mechanism parameter domains through these bijectors. The helpers are pure JAX
transformations and do not touch CAS or mutate mechanism state in place.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import jax
import jax.numpy as jnp

from polisyos.foundry._numeric import (
    NumericDomain,
    clip_probability,
    epsilon_for,
    softplus_inverse,
    stable_logit,
)


@dataclass
class Bijector:
    """Pair forward/inverse transforms for one optimizer parameter block.

    Attributes:
        forward: Map an unconstrained optimizer value into the constrained
            mechanism parameter domain.
        inverse: Map a constrained parameter value back to unconstrained
            coordinates.
        log_det_jacobian: Optional log-Jacobian term for future Bayesian or
            density-aware calibration extensions.
    """

    forward: Callable[[jnp.ndarray], jnp.ndarray]
    inverse: Callable[[jnp.ndarray], jnp.ndarray]
    log_det_jacobian: Callable[[jnp.ndarray], jnp.ndarray] | None = None


def _identity() -> Bijector:
    return Bijector(
        forward=lambda x: x,
        inverse=lambda x: x,
        log_det_jacobian=lambda x: jnp.zeros_like(x),
    )


def make_bijector(lower: float | None, upper: float | None, eps: float = 1e-6) -> Bijector:
    """Build a box-constraint bijector for a trainable parameter.

    Args:
        lower: Inclusive lower bound, or `None` for no lower constraint.
        upper: Inclusive upper bound, or `None` for no upper constraint.
        eps: Numerical stabilizer used by inverse transforms near boundaries.

    Returns:
        Identity, softplus, reverse-softplus, or logistic box bijector matching
        the supplied bounds.
    """
    eps = max(float(eps), epsilon_for(NumericDomain.POSITIVE))
    if lower is None and upper is None:
        return _identity()
    if lower is not None and upper is None:
        # [lower, +inf) -> lower + softplus
        return Bijector(
            forward=lambda u: lower + jax.nn.softplus(u),
            inverse=lambda x: softplus_inverse(jnp.asarray(x) - lower, eps=eps),
            log_det_jacobian=lambda u: jnp.log(jax.nn.sigmoid(u)),
        )
    if lower is None and upper is not None:
        # (-inf, upper] -> upper - softplus
        return Bijector(
            forward=lambda u: upper - jax.nn.softplus(u),
            inverse=lambda x: softplus_inverse(upper - jnp.asarray(x), eps=eps),
            log_det_jacobian=lambda u: jnp.log(jax.nn.sigmoid(u)),
        )
    if lower is not None and upper is not None:
        width = upper - lower
        if width <= 0.0:
            raise ValueError("upper bound must exceed lower bound")
        return Bijector(
            forward=lambda u: jax.nn.sigmoid(u) * width + lower,
            inverse=lambda x: stable_logit(
                clip_probability((jnp.asarray(x) - lower) / width, eps=eps),
                eps=eps,
            ),
            log_det_jacobian=lambda u: (
                jnp.log(jax.nn.sigmoid(u)) + jnp.log1p(-jax.nn.sigmoid(u)) + jnp.log(width)
            ),
        )
    return _identity()


# ---------------------------------------------------------------------------
# Named bijector factories
# ---------------------------------------------------------------------------


def log_bijector(eps: float = 1e-8) -> Bijector:
    """Bijector: unconstrained -> positive via exp/log."""
    eps = max(float(eps), epsilon_for(NumericDomain.POSITIVE))
    return Bijector(
        forward=lambda u: jnp.exp(u),
        inverse=lambda x: jnp.log(jnp.maximum(x, eps)),
        log_det_jacobian=lambda u: u,  # d/du exp(u) = exp(u), log|.| = u
    )


def logit_bijector(eps: float = 1e-8) -> Bijector:
    """Bijector: unconstrained -> (0, 1) via sigmoid/logit."""
    eps = max(float(eps), epsilon_for(NumericDomain.PROBABILITY))
    return Bijector(
        forward=lambda u: jax.nn.sigmoid(u),
        inverse=lambda x: stable_logit(x, eps=eps),
        log_det_jacobian=lambda u: (jnp.log(jax.nn.sigmoid(u)) + jnp.log(1.0 - jax.nn.sigmoid(u))),
    )


def softplus_bijector(lower: float = 0.0) -> Bijector:
    """Bijector: unconstrained -> (lower, +inf) via softplus."""
    return Bijector(
        forward=lambda u: lower + jax.nn.softplus(u),
        inverse=lambda x: softplus_inverse(jnp.asarray(x) - lower),
        log_det_jacobian=lambda u: jnp.log(jax.nn.sigmoid(u)),
    )


def affine_bijector(loc: float, scale: float) -> Bijector:
    """Bijector: x -> loc + scale * x."""
    log_abs_scale = jnp.log(jnp.abs(jnp.array(scale)))
    return Bijector(
        forward=lambda u: loc + scale * u,
        inverse=lambda x: (x - loc) / scale,
        log_det_jacobian=lambda u: jnp.broadcast_to(log_abs_scale, jnp.shape(u)),
    )


def chain_bijector(*bijectors: Bijector) -> Bijector:
    """Compose bijectors left-to-right: chain(f, g)(x) = g(f(x)).

    log_det_jacobian is the sum of individual ldjs evaluated at the correct
    intermediate values.
    """
    if not bijectors:
        return _identity()
    if len(bijectors) == 1:
        return bijectors[0]

    def _forward(x: jnp.ndarray) -> jnp.ndarray:
        for b in bijectors:
            x = b.forward(x)
        return x

    def _inverse(y: jnp.ndarray) -> jnp.ndarray:
        for b in reversed(bijectors):
            y = b.inverse(y)
        return y

    def _ldj(x: jnp.ndarray) -> jnp.ndarray:
        total = jnp.zeros_like(x)
        for b in bijectors:
            if b.log_det_jacobian is not None:
                total = total + b.log_det_jacobian(x)
            x = b.forward(x)
        return total

    return Bijector(forward=_forward, inverse=_inverse, log_det_jacobian=_ldj)


def inverse_bijector(b: Bijector) -> Bijector:
    """Swap forward and inverse, negate log_det_jacobian."""
    ldj: Callable[[jnp.ndarray], jnp.ndarray] | None = None
    if b.log_det_jacobian is not None:
        ldj = lambda u, _b=b: -_b.log_det_jacobian(_b.inverse(u))
    return Bijector(forward=b.inverse, inverse=b.forward, log_det_jacobian=ldj)


# ---------------------------------------------------------------------------
# Utility helpers (unchanged API)
# ---------------------------------------------------------------------------


def to_unconstrained(
    values: Sequence[jnp.ndarray], bijectors: Sequence[Bijector]
) -> list[jnp.ndarray]:
    """Transform constrained parameter values into optimizer coordinates."""
    return [b.inverse(v) for b, v in zip(bijectors, values)]


def from_unconstrained(
    unconstrained: Sequence[jnp.ndarray], bijectors: Sequence[Bijector]
) -> list[jnp.ndarray]:
    """Transform optimizer coordinates back into constrained parameter values."""
    return [b.forward(u) for b, u in zip(bijectors, unconstrained)]
