from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence

import jax
import jax.numpy as jnp


@dataclass
class Bijector:
    forward: Callable[[jnp.ndarray], jnp.ndarray]
    inverse: Callable[[jnp.ndarray], jnp.ndarray]


def _identity() -> Bijector:
    return Bijector(forward=lambda x: x, inverse=lambda x: x)


def make_bijector(lower: float | None, upper: float | None, eps: float = 1e-6) -> Bijector:
    """Строим простую биекцию для ограничения параметров."""
    if lower is None and upper is None:
        return _identity()
    if lower is not None and upper is None:
        # [lower, +inf) -> lower + softplus
        return Bijector(
            forward=lambda u: lower + jax.nn.softplus(u),
            inverse=lambda x: jnp.log(jnp.exp(jnp.maximum(x - lower, 0.0)) - 1.0 + eps),
        )
    if lower is None and upper is not None:
        # (-inf, upper] -> upper - softplus
        return Bijector(
            forward=lambda u: upper - jax.nn.softplus(u),
            inverse=lambda x: jnp.log(jnp.exp(jnp.maximum(upper - x, 0.0)) - 1.0 + eps),
        )
    if lower is not None and upper is not None:
        width = upper - lower
        # "Температура" для sigmoid-параметризации: меньшие значения дают более сильный
        # градиент в ограниченном пространстве (полезно для быстрой сходимости калибратора).
        temperature = 0.5
        return Bijector(
            forward=lambda u: jax.nn.sigmoid(u / temperature) * width + lower,
            inverse=lambda x: temperature * jnp.log((x - lower) / (upper - x + eps)),
        )
    return _identity()


def to_unconstrained(values: Sequence[jnp.ndarray], bijectors: Sequence[Bijector]) -> List[jnp.ndarray]:
    return [b.inverse(v) for b, v in zip(bijectors, values)]


def from_unconstrained(
    unconstrained: Sequence[jnp.ndarray], bijectors: Sequence[Bijector]
) -> List[jnp.ndarray]:
    return [b.forward(u) for b, u in zip(bijectors, unconstrained)]
