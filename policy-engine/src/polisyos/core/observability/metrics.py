"""Decomposed module wrapper; implementation moved to `metrics_parts`."""

from __future__ import annotations

from .metrics_parts import GaugeProxy, HistogramTimer, MetricsRegistry, get_metrics

__all__ = [
    "GaugeProxy",
    "HistogramTimer",
    "MetricsRegistry",
    "get_metrics",
]
