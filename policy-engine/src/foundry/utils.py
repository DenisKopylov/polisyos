import jax
import jax.numpy as jnp

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
