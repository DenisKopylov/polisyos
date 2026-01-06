import jax
import jax.numpy as jnp
from jax import tree_util

def soft_step(x: jnp.ndarray, k: float = 10.0) -> jnp.ndarray:
    """
    Дифференцируемая аппроксимация ступеньки (x > 0).
    Вместо `if x > 0: 1 else: 0` используем сигмоиду.
    k - коэффициент жесткости.
    """
    return jax.nn.sigmoid(k * x)

def soft_clamp(x: jnp.ndarray, min_val: float, max_val: float) -> jnp.ndarray:
    """
    Дифференцируемое ограничение значений.
    Вместо jnp.clip (у которого нулевой градиент за границами),
    можно использовать плавное насыщение, но для начала jnp.clip в JAX
    тоже пропускает градиент (identity в диапазоне).
    Для сложной логики можно использовать tanh.
    """
    return jnp.clip(x, min_val, max_val)


def gradient_health(
    grads,
    vanishing_threshold: float = 1e-8,
    exploding_threshold: float = 1e3,
) -> dict:
    leaves = tree_util.tree_leaves(grads)
    if not leaves:
        return {"nan_frac": 0.0, "inf_frac": 0.0, "grad_norm": 0.0, "vanishing": True, "exploding": False}

    flat = jnp.concatenate([jnp.ravel(jnp.asarray(x)) for x in leaves])
    nan_frac = jnp.mean(jnp.isnan(flat))
    inf_frac = jnp.mean(jnp.isinf(flat))
    norm = jnp.linalg.norm(flat)
    return {
        "nan_frac": float(nan_frac),
        "inf_frac": float(inf_frac),
        "grad_norm": float(norm),
        "vanishing": bool(norm < vanishing_threshold),
        "exploding": bool(norm > exploding_threshold),
    }
