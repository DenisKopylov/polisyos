"""Define reusable training and rollout metrics for agent-simulation experiments."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum

import chex
import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.state import GlobalState


class MetricType(str, Enum):
    """Metric type public type."""

    SCALAR = "scalar"
    HISTOGRAM = "histogram"
    TRAJECTORY = "trajectory"
    AGGREGATE = "aggregate"


@dataclass(frozen=True)
class MetricDefinition:
    """Metric definition public type."""

    name: str
    metric_type: MetricType
    compute_fn: Callable[[GlobalState], jnp.ndarray]
    frequency: int = 1
    tags: dict[str, str] = field(default_factory=dict)


@chex.dataclass(frozen=True)
class MetricsBuffer:
    """Metrics buffer public type."""

    scalars: dict[str, jnp.ndarray]
    histograms: dict[str, jnp.ndarray]
    write_idx: jnp.ndarray
    max_size: int

    @classmethod
    def create(
        cls,
        scalar_names: Sequence[str],
        histogram_names: Sequence[str],
        *,
        max_size: int = 10000,
        n_bins: int = 50,
    ) -> MetricsBuffer:
        scalars = {name: jnp.zeros((max_size,), dtype=jnp.float32) for name in scalar_names}
        histograms = {
            name: jnp.zeros((max_size, n_bins), dtype=jnp.float32) for name in histogram_names
        }
        return cls(
            scalars=scalars,
            histograms=histograms,
            write_idx=jnp.array(0, dtype=jnp.int32),
            max_size=int(max_size),
        )

    def write_scalar_at(self, name: str, value: jnp.ndarray, idx: jnp.ndarray) -> MetricsBuffer:
        if name not in self.scalars:
            return self
        new_scalars = {
            k: (v.at[idx].set(value) if k == name else v) for k, v in self.scalars.items()
        }
        return self.replace(scalars=new_scalars)

    def write_scalar(self, name: str, value: jnp.ndarray) -> MetricsBuffer:
        idx = self.write_idx % self.max_size
        return self.write_scalar_at(name, value, idx)

    def write_histogram_at(
        self,
        name: str,
        values: jnp.ndarray,
        bins: jnp.ndarray,
        idx: jnp.ndarray,
    ) -> MetricsBuffer:
        if name not in self.histograms:
            return self
        values = jnp.ravel(values)
        finite = jnp.isfinite(values)
        safe_values = jnp.where(finite, values, bins[0])
        weights = finite.astype(jnp.float32)
        hist, _ = jnp.histogram(safe_values, bins=bins, weights=weights)
        hist = hist / jnp.maximum(jnp.sum(hist), 1.0)
        new_histograms = {
            k: (v.at[idx].set(hist) if k == name else v) for k, v in self.histograms.items()
        }
        return self.replace(histograms=new_histograms)

    def write_histogram(self, name: str, values: jnp.ndarray, bins: jnp.ndarray) -> MetricsBuffer:
        idx = self.write_idx % self.max_size
        return self.write_histogram_at(name, values, bins, idx)

    def advance(self, step: int = 1) -> MetricsBuffer:
        return self.replace(write_idx=self.write_idx + int(step))


@chex.dataclass(frozen=True, init=False, mappable_dataclass=False)
class MetricsCollector:
    """Metrics collector public type."""

    definitions: tuple[MetricDefinition, ...]
    buffer: MetricsBuffer
    step_counter: jnp.ndarray

    def __init__(
        self,
        definitions: Sequence[MetricDefinition],
        max_history: int = 10000,
        buffer: MetricsBuffer | None = None,
        step_counter: jnp.ndarray | None = None,
    ):
        object.__setattr__(self, "definitions", tuple(definitions))
        if buffer is None:
            scalar_names = [d.name for d in self.definitions if d.metric_type == MetricType.SCALAR]
            histogram_names = [
                d.name for d in self.definitions if d.metric_type == MetricType.HISTOGRAM
            ]
            buffer = MetricsBuffer.create(scalar_names, histogram_names, max_size=max_history)
        object.__setattr__(self, "buffer", buffer)
        if step_counter is None:
            step_counter = jnp.array(0, dtype=jnp.int32)
        object.__setattr__(self, "step_counter", step_counter)

    def collect(self, state: GlobalState) -> MetricsCollector:
        buffer = self.buffer
        idx = buffer.write_idx % buffer.max_size

        for defn in self.definitions:
            should_collect = (self.step_counter % defn.frequency) == 0

            def _collect(buf: MetricsBuffer) -> MetricsBuffer:
                value = defn.compute_fn(state)
                if defn.metric_type == MetricType.SCALAR:
                    return buf.write_scalar_at(defn.name, value, idx)
                if defn.metric_type == MetricType.HISTOGRAM:
                    n_bins = buf.histograms[defn.name].shape[1]
                    bins = _safe_histogram_bins(value, n_bins)
                    return buf.write_histogram_at(defn.name, value, bins, idx)
                return buf

            buffer = jax.lax.cond(should_collect, _collect, lambda b: b, buffer)

        buffer = buffer.advance(1)
        return self.replace(buffer=buffer, step_counter=self.step_counter + 1)

    def get_scalar_history(self, name: str) -> jnp.ndarray:
        n_samples = jnp.minimum(self.step_counter, self.buffer.max_size)
        return self.buffer.scalars[name][:n_samples]

    def get_latest(self, name: str) -> jnp.ndarray:
        idx = (self.step_counter - 1) % self.buffer.max_size
        if name in self.buffer.scalars:
            return self.buffer.scalars[name][idx]
        return self.buffer.histograms[name][idx]


def standard_training_metrics() -> list[MetricDefinition]:
    """Declare the default state metrics tracked during agent training."""

    def _active_mean(values: jnp.ndarray, active: jnp.ndarray) -> jnp.ndarray:
        active_f = active.astype(jnp.float32)
        denom = jnp.maximum(jnp.sum(active_f), 1.0)
        return jnp.sum(values * active_f) / denom

    return [
        MetricDefinition(
            name="mean_wealth",
            metric_type=MetricType.SCALAR,
            compute_fn=lambda s: _active_mean(s.agents.wealth, s.agents.active),
        ),
        MetricDefinition(
            name="gini_wealth",
            metric_type=MetricType.SCALAR,
            compute_fn=lambda s: s.distributions.gini_wealth,
        ),
        MetricDefinition(
            name="gdp",
            metric_type=MetricType.SCALAR,
            compute_fn=lambda s: _active_mean(s.agents.income, s.agents.active)
            * jnp.sum(s.agents.active.astype(jnp.float32)),
        ),
        MetricDefinition(
            name="mean_consumption",
            metric_type=MetricType.SCALAR,
            compute_fn=lambda s: _active_mean(s.agents.consumption, s.agents.active),
        ),
        MetricDefinition(
            name="n_active_agents",
            metric_type=MetricType.SCALAR,
            compute_fn=lambda s: jnp.sum(s.agents.active.astype(jnp.float32)),
        ),
        MetricDefinition(
            name="wealth_distribution",
            metric_type=MetricType.HISTOGRAM,
            compute_fn=lambda s: jnp.where(s.agents.active, s.agents.wealth, jnp.nan),
            frequency=10,
        ),
        MetricDefinition(
            name="income_distribution",
            metric_type=MetricType.HISTOGRAM,
            compute_fn=lambda s: jnp.where(s.agents.active, s.agents.income, jnp.nan),
            frequency=10,
        ),
    ]


def training_loss_metrics() -> list[MetricDefinition]:
    """Declare PPO loss diagnostics tracked alongside training runs."""
    return [
        MetricDefinition(
            name="policy_loss",
            metric_type=MetricType.SCALAR,
            compute_fn=lambda s: jnp.array(0.0, dtype=jnp.float32),
        ),
        MetricDefinition(
            name="value_loss",
            metric_type=MetricType.SCALAR,
            compute_fn=lambda s: jnp.array(0.0, dtype=jnp.float32),
        ),
        MetricDefinition(
            name="entropy",
            metric_type=MetricType.SCALAR,
            compute_fn=lambda s: jnp.array(0.0, dtype=jnp.float32),
        ),
        MetricDefinition(
            name="mean_reward",
            metric_type=MetricType.SCALAR,
            compute_fn=lambda s: jnp.array(0.0, dtype=jnp.float32),
        ),
        MetricDefinition(
            name="mean_advantage",
            metric_type=MetricType.SCALAR,
            compute_fn=lambda s: jnp.array(0.0, dtype=jnp.float32),
        ),
    ]


def _safe_histogram_bins(values: jnp.ndarray, n_bins: int) -> jnp.ndarray:
    values = jnp.ravel(values)
    finite = jnp.isfinite(values)
    safe_min = jnp.min(jnp.where(finite, values, jnp.inf))
    safe_max = jnp.max(jnp.where(finite, values, -jnp.inf))
    has_finite = jnp.any(finite)
    min_val = jax.lax.select(has_finite, safe_min, jnp.array(0.0, dtype=values.dtype))
    max_val = jax.lax.select(has_finite, safe_max, jnp.array(1.0, dtype=values.dtype))
    max_val = jnp.where(max_val <= min_val, min_val + 1.0, max_val)
    return jnp.linspace(min_val - 1e-6, max_val + 1e-6, int(n_bins) + 1)
