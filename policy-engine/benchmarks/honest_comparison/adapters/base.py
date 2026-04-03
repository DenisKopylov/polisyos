"""Base protocol and result dataclass for all estimator adapters."""

from __future__ import annotations

import hashlib
import json
import sys
import time
import traceback
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np


@dataclass
class EstimatorResult:
    """Standardised output from every adapter."""

    ate: float | None = None
    ate_se: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    cate: np.ndarray | None = None
    elapsed_s: float = 0.0
    memory_mb: float = 0.0
    failed: bool = False
    failure_reason: str | None = None
    config_digest: str = ""


@runtime_checkable
class EstimatorAdapter(Protocol):
    """Protocol every adapter must satisfy."""

    name: str
    library: str

    def fit_predict(
        self,
        X: np.ndarray,
        T: np.ndarray,
        Y: np.ndarray,
        config: dict[str, Any],
        seed: int,
    ) -> EstimatorResult: ...

    def supports_cate(self) -> bool: ...


def config_digest(config: dict[str, Any]) -> str:
    raw = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def safe_run(
    fn,
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    config: dict[str, Any],
    seed: int,
    timeout_s: float = 300.0,
) -> EstimatorResult:
    """Run fn(X, T, Y, config, seed) with timing and error capture."""
    import resource

    digest = config_digest(config)
    t0 = time.perf_counter()
    try:
        mem_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result: EstimatorResult = fn(X, T, Y, config, seed)
        mem_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result.elapsed_s = time.perf_counter() - t0
        divisor = 1024 if sys.platform == "linux" else (1024 * 1024)
        result.memory_mb = max(0, (mem_after - mem_before)) / divisor
        result.config_digest = digest
        return result
    except Exception as exc:
        return EstimatorResult(
            failed=True,
            failure_reason=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-500:]}",
            elapsed_s=time.perf_counter() - t0,
            config_digest=digest,
        )
