"""LLM cost anomaly detection via rolling z-score."""
from __future__ import annotations

import math
from collections import deque


class CostAnomalyDetector:
    """Detects anomalous LLM call costs (> 3σ from rolling mean).

    Uses a rolling window of recent costs to compute mean and standard
    deviation.  A cost is flagged as anomalous when it exceeds
    ``mean + z_threshold * std``.

    Thread safety is **not** provided — callers must hold their own lock
    if used from multiple threads (the ``LLMBudgetEnforcer`` already does).
    """

    def __init__(self, window_size: int = 50, z_threshold: float = 3.0) -> None:
        self._window: deque[float] = deque(maxlen=window_size)
        self._z_threshold = z_threshold

    def check(self, cost: float) -> bool:
        """Return ``True`` if *cost* is anomalous, then append to window."""
        if len(self._window) < 2:
            self._window.append(cost)
            return False

        mean = sum(self._window) / len(self._window)
        variance = sum((x - mean) ** 2 for x in self._window) / len(self._window)
        std = math.sqrt(variance)

        if std > 0:
            is_anomaly = cost > mean + self._z_threshold * std
        else:
            # Zero variance: any cost significantly different from mean is anomalous
            is_anomaly = abs(cost - mean) > mean * 0.5 if mean > 0 else cost > 0
        self._window.append(cost)
        return is_anomaly
