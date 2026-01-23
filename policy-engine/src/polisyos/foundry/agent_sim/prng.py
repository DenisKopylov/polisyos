from __future__ import annotations

import chex
import jax
import jax.numpy as jnp
from jaxtyping import Array, Int


@chex.dataclass(frozen=True)
class PRNGState:
    master_key: chex.PRNGKey
    step_counter: Int[Array, ""]


def get_mechanism_key(
    master_key: chex.PRNGKey,
    step_counter: jnp.ndarray,
    salt: int,
) -> chex.PRNGKey:
    step_key = jax.random.fold_in(master_key, step_counter)
    return jax.random.fold_in(step_key, int(salt))


def advance_prng(prng: PRNGState) -> PRNGState:
    return prng.replace(step_counter=prng.step_counter + 1)
