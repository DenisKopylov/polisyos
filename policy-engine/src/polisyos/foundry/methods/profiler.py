"""
Method Execution Profiler for Foundry.

``MethodProfiler`` wraps a single ``pure_step`` invocation and captures:

- Wall-clock time (ms)
- Peak memory (MB) via ``tracemalloc``
- Number of JIT compilations (JAX only — detected by ``jax.monitoring``)
- Input and output array shapes

The profiler is **non-invasive**: it never modifies the method or the
registry and can be used without any prior setup.

Usage
-----
::

    from polisyos.foundry.methods.profiler import MethodProfiler

    profiler = MethodProfiler()
    result, profile = profiler.profile(
        method_class=MyMethod,
        state={"outcome": arr, "treatment": trt},
        params={"seed": 0},
    )
    print(profile.wall_time_ms, profile.peak_memory_mb)
    print(profile.to_markdown_table())

Speedscope Export
-----------------
::

    json_str = profile.to_speedscope_json()
    Path("/tmp/profile.json").write_text(json_str)
    # Open at https://www.speedscope.app
"""
from __future__ import annotations

import json
import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Any

import numpy as np

__all__ = [
    "MethodExecutionProfile",
    "MethodProfiler",
]


# ---------------------------------------------------------------------------
# MethodExecutionProfile
# ---------------------------------------------------------------------------


@dataclass
class MethodExecutionProfile:
    """
    Execution profile for a single ``pure_step`` call.

    Attributes
    ----------
    fqn:
        Fully-qualified method name.
    wall_time_ms:
        Total wall-clock time in milliseconds.
    peak_memory_mb:
        Peak additional memory allocated during the call (MB).
    n_jit_compilations:
        Number of JAX XLA compilations triggered (0 for non-JAX methods).
    input_shapes:
        Mapping of input key → shape tuple for array inputs.
    output_shapes:
        Mapping of output key → shape tuple for array outputs.
    """

    fqn: str
    wall_time_ms: float
    peak_memory_mb: float
    n_jit_compilations: int = 0
    input_shapes: dict[str, tuple[int, ...]] = field(default_factory=dict)
    output_shapes: dict[str, tuple[int, ...]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def to_markdown_table(self) -> str:
        """Return a Markdown summary table for notebooks / CLI output."""
        lines = [
            "| Metric | Value |",
            "|--------|-------|",
            f"| FQN | `{self.fqn}` |",
            f"| Wall time | {self.wall_time_ms:.2f} ms |",
            f"| Peak memory | {self.peak_memory_mb:.2f} MB |",
            f"| JIT compilations | {self.n_jit_compilations} |",
        ]
        if self.input_shapes:
            shapes_str = ", ".join(f"{k}:{v}" for k, v in self.input_shapes.items())
            lines.append(f"| Input shapes | {shapes_str} |")
        if self.output_shapes:
            shapes_str = ", ".join(f"{k}:{v}" for k, v in self.output_shapes.items())
            lines.append(f"| Output shapes | {shapes_str} |")
        return "\n".join(lines)

    def to_speedscope_json(self) -> str:
        """
        Export a minimal speedscope-compatible JSON profile.

        The profile represents a single frame with name=fqn and
        total=wall_time_ms.  Open at https://www.speedscope.app.
        """
        profile_data = {
            "$schema": "https://www.speedscope.app/file-format-schema.json",
            "shared": {"frames": [{"name": self.fqn}]},
            "profiles": [
                {
                    "type": "evented",
                    "name": self.fqn,
                    "unit": "milliseconds",
                    "startValue": 0,
                    "endValue": self.wall_time_ms,
                    "events": [
                        {"type": "O", "frame": 0, "at": 0},
                        {"type": "C", "frame": 0, "at": self.wall_time_ms},
                    ],
                }
            ],
            "activeProfileIndex": 0,
            "exporter": "polisyos.foundry.profiler",
            "name": self.fqn,
        }
        return json.dumps(profile_data, indent=2)

    def __repr__(self) -> str:
        return (
            f"<MethodExecutionProfile fqn={self.fqn!r} "
            f"wall_time={self.wall_time_ms:.2f}ms "
            f"peak_mem={self.peak_memory_mb:.2f}MB>"
        )


# ---------------------------------------------------------------------------
# MethodProfiler
# ---------------------------------------------------------------------------


class MethodProfiler:
    """
    Non-invasive profiler for Foundry method invocations.

    The profiler wraps ``method_class.pure_step()`` with:
    - ``tracemalloc`` for peak memory tracking
    - ``time.perf_counter()`` for wall-clock timing
    - JAX compilation counter (when JAX is available)

    Parameters
    ----------
    enable_tracemalloc:
        If False, memory profiling is disabled (lower overhead).
        Default: True.
    """

    def __init__(self, enable_tracemalloc: bool = True) -> None:
        self._tracemalloc = enable_tracemalloc

    def profile(
        self,
        method_class: type,
        state: dict[str, Any],
        params: dict[str, Any],
    ) -> tuple[Any, MethodExecutionProfile]:
        """
        Execute ``method_class.pure_step(state, params)`` and profile it.

        Parameters
        ----------
        method_class:
            A Foundry method class with a ``pure_step`` static method.
        state:
            Input state dict passed to ``pure_step``.
        params:
            Parameter dict passed to ``pure_step``.

        Returns
        -------
        (result, profile)
            - ``result``: the return value of ``pure_step``
            - ``profile``: ``MethodExecutionProfile`` with timing/memory data
        """
        fqn = getattr(getattr(method_class, "signature", None), "fqn", method_class.__name__)
        input_shapes = _extract_shapes(state)

        jit_before = _count_jax_compilations()

        if self._tracemalloc:
            tracemalloc.start()

        t0 = time.perf_counter()
        result = method_class.pure_step(state, params)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        peak_mb = 0.0
        if self._tracemalloc:
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_mb = peak_bytes / (1024 * 1024)

        jit_after = _count_jax_compilations()
        n_jit = max(0, jit_after - jit_before)

        output_shapes = _extract_shapes(result) if isinstance(result, dict) else {}

        profile = MethodExecutionProfile(
            fqn=fqn,
            wall_time_ms=elapsed_ms,
            peak_memory_mb=peak_mb,
            n_jit_compilations=n_jit,
            input_shapes=input_shapes,
            output_shapes=output_shapes,
        )
        return result, profile

    def profile_batch(
        self,
        method_class: type,
        states: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[tuple[Any, MethodExecutionProfile]]:
        """Profile multiple invocations and return all (result, profile) pairs."""
        return [self.profile(method_class, state, params) for state in states]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_shapes(data: dict[str, Any]) -> dict[str, tuple[int, ...]]:
    """Extract shapes of all numpy arrays in a dict."""
    shapes: dict[str, tuple[int, ...]] = {}
    for key, value in data.items():
        if isinstance(value, np.ndarray):
            shapes[str(key)] = tuple(int(d) for d in value.shape)
        elif hasattr(value, "shape"):
            # JAX arrays and other array-like objects
            try:
                shapes[str(key)] = tuple(int(d) for d in value.shape)
            except Exception:
                pass
    return shapes


def _count_jax_compilations() -> int:
    """
    Return current JAX XLA compilation count.

    Returns 0 if JAX is not installed or the counter is not accessible.
    """
    try:
        import jax._src.monitoring as jax_monitoring  # type: ignore[import]
        counter = jax_monitoring._event_counts.get(
            "/jax/jit/compile_time_saved/num_traces_from_compilation", 0
        )
        return int(counter)
    except Exception:
        return 0
