"""Public foundry utils module API."""
from dataclasses import dataclass

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
    """Gradient health helper."""
    report, _ = gradient_health_report(
        grads,
        clip_norm=None,
        vanishing_threshold=vanishing_threshold,
        exploding_threshold=exploding_threshold,
    )
    return report.to_dict()


@dataclass(frozen=True)
class GradientHealthReport:
    """Gradient health report data model."""
    nan_frac: float
    inf_frac: float
    grad_norm: float
    vanishing: bool
    exploding: bool
    clipped: bool
    clip_norm: float | None

    def to_dict(self) -> dict:
        return {
            "nan_frac": self.nan_frac,
            "inf_frac": self.inf_frac,
            "grad_norm": self.grad_norm,
            "vanishing": self.vanishing,
            "exploding": self.exploding,
            "clipped": self.clipped,
            "clip_norm": self.clip_norm,
        }


def _flatten_grads(grads) -> jnp.ndarray:
    leaves = tree_util.tree_leaves(grads)
    if not leaves:
        return jnp.array([])
    return jnp.concatenate([jnp.ravel(jnp.asarray(x)) for x in leaves])


def _clip_grads(grads, max_norm: float) -> tuple[object, bool, float]:
    flat = _flatten_grads(grads)
    if flat.size == 0:
        return grads, False, 0.0
    norm = jnp.linalg.norm(flat)
    scale = jnp.minimum(1.0, max_norm / (norm + 1e-12))
    clipped = tree_util.tree_map(lambda x: jnp.asarray(x) * scale, grads)
    return clipped, bool(norm > max_norm), float(norm)


def gradient_health_report(
    grads,
    clip_norm: float | None = None,
    vanishing_threshold: float = 1e-8,
    exploding_threshold: float = 1e3,
) -> tuple[GradientHealthReport, object]:
    """Gradient health report helper."""
    flat = _flatten_grads(grads)
    if flat.size == 0:
        report = GradientHealthReport(
            nan_frac=0.0,
            inf_frac=0.0,
            grad_norm=0.0,
            vanishing=True,
            exploding=False,
            clipped=False,
            clip_norm=clip_norm,
        )
        return report, grads

    nan_frac = float(jnp.mean(jnp.isnan(flat)))
    inf_frac = float(jnp.mean(jnp.isinf(flat)))
    norm = float(jnp.linalg.norm(flat))
    vanishing = bool(norm < vanishing_threshold)
    exploding = bool(norm > exploding_threshold)
    clipped = False
    clipped_grads = grads

    if clip_norm is not None:
        clipped_grads, clipped, norm = _clip_grads(grads, clip_norm)

    report = GradientHealthReport(
        nan_frac=nan_frac,
        inf_frac=inf_frac,
        grad_norm=norm,
        vanishing=vanishing,
        exploding=exploding,
        clipped=clipped,
        clip_norm=clip_norm,
    )
    return report, clipped_grads
