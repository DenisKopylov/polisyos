"""
Jupyter / Interactive Sandbox API for Foundry methods.

``MethodSandbox`` provides an ergonomic interface for exploring Foundry
methods in Jupyter notebooks and interactive Python sessions:

- ``run()``    — run a single method invocation with auto-state resolution
- ``profile()``— profile a method invocation (wall time + peak memory)
- ``validate()``— validate the method class against the ABI contract
- ``compare()`` — run multiple methods on the same state and compare outputs
- ``html_repr()`` — rich HTML summary for Jupyter display

Usage (Jupyter notebook)
------------------------
::

    from polisyos.foundry.methods.testing.sandbox import MethodSandbox

    sb = MethodSandbox("bayesian.regression.linear_regression@1.0.0")

    # Simple run
    result = sb.run(features=X, target=y, seed=42)

    # Profile
    result, profile = sb.profile(features=X, target=y)
    print(profile.to_markdown_table())

    # HTML display in notebook
    from IPython.display import HTML
    display(HTML(sb.html_repr()))

    # Validate
    report = sb.validate()
    report.print_summary()

    # Compare two implementations
    comparison = MethodSandbox.compare(
        fqns=["bayesian.regression.linear_regression@1.0.0",
              "bayesian.variational.mean_field_vi@1.0.0"],
        features=X, target=y,
    )
    comparison.print()
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

__all__ = [
    "MethodSandbox",
    "SandboxResult",
    "ComparisonResult",
]


# ---------------------------------------------------------------------------
# SandboxResult
# ---------------------------------------------------------------------------


@dataclass
class SandboxResult:
    """
    Result of a single ``MethodSandbox.run()`` invocation.

    Attributes
    ----------
    fqn:
        Fully-qualified method name.
    output:
        Raw output dict from ``pure_step``.
    wall_time_ms:
        Wall-clock time for the invocation.
    params_used:
        Effective parameters passed to ``pure_step``.
    """

    fqn: str
    output: dict[str, Any]
    wall_time_ms: float
    params_used: dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        """Access an output key with a default."""
        return self.output.get(key, default)

    def keys(self) -> list[str]:
        """Return output keys."""
        return list(self.output.keys())

    def summary(self) -> str:
        lines = [
            f"SandboxResult({self.fqn})",
            f"  wall_time: {self.wall_time_ms:.2f} ms",
            f"  output keys: {self.keys()}",
        ]
        for k, v in self.output.items():
            if isinstance(v, np.ndarray):
                lines.append(f"    {k}: ndarray{v.shape} dtype={v.dtype}")
            elif isinstance(v, (int, float)):
                lines.append(f"    {k}: {v:.4f}")
            elif isinstance(v, dict) and len(str(v)) < 200:
                lines.append(f"    {k}: {v}")
            elif isinstance(v, str):
                lines.append(f"    {k}: {v!r}")
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        rows = ""
        for k, v in self.output.items():
            if isinstance(v, np.ndarray):
                val_str = f"ndarray{v.shape} dtype={v.dtype}"
            elif isinstance(v, (int, float)):
                val_str = f"{v:.4f}"
            elif hasattr(v, "model_dump"):
                val_str = f"&lt;{type(v).__name__}&gt;"
            else:
                val_str = str(v)[:120]
            rows += f"<tr><td><code>{k}</code></td><td>{val_str}</td></tr>"
        return (
            f"<h4>SandboxResult: {self.fqn}</h4>"
            f"<p><b>Wall time:</b> {self.wall_time_ms:.2f} ms</p>"
            f"<table border='1' style='border-collapse:collapse'>"
            f"<tr><th>Key</th><th>Value</th></tr>"
            f"{rows}</table>"
        )

    def __repr__(self) -> str:
        return self.summary()


# ---------------------------------------------------------------------------
# ComparisonResult
# ---------------------------------------------------------------------------


@dataclass
class ComparisonResult:
    """Result of comparing multiple methods on the same inputs."""

    results: dict[str, SandboxResult]
    shared_keys: list[str]

    def print(self) -> None:
        print(f"\nComparison ({len(self.results)} methods)")
        print(f"Shared output keys: {self.shared_keys}")
        print("-" * 60)
        for fqn, res in self.results.items():
            print(f"\n  {fqn}  ({res.wall_time_ms:.2f} ms)")
            for k in self.shared_keys:
                v = res.output.get(k)
                if v is not None:
                    print(f"    {k}: {_fmt_value(v)}")

    def _repr_html_(self) -> str:
        header = "<tr><th>Key</th>"
        for fqn in self.results:
            header += f"<th>{fqn}</th>"
        header += "</tr>"

        rows = ""
        for k in self.shared_keys:
            row = f"<tr><td><code>{k}</code></td>"
            for res in self.results.values():
                v = res.output.get(k)
                row += f"<td>{_fmt_value(v)}</td>"
            row += "</tr>"
            rows += row

        return (
            "<h4>Method Comparison</h4>"
            "<table border='1' style='border-collapse:collapse'>"
            f"{header}{rows}</table>"
        )


def _fmt_value(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, np.ndarray):
        return f"array{v.shape}"
    if isinstance(v, float):
        return f"{v:.4f}"
    if hasattr(v, "model_dump"):
        return f"&lt;{type(v).__name__}&gt;"
    return str(v)[:80]


# ---------------------------------------------------------------------------
# MethodSandbox
# ---------------------------------------------------------------------------


class MethodSandbox:
    """
    Interactive sandbox for a single Foundry method.

    Parameters
    ----------
    fqn:
        Fully-qualified method name, e.g. ``"bayesian.regression.linear_regression@1.0.0"``.
    registry:
        ``MethodRegistry`` to look up the method in.  Defaults to global registry.
    """

    def __init__(self, fqn: str, registry: Any = None) -> None:
        self.fqn = fqn
        self._registry = registry
        self._method_class: type | None = None

    @property
    def method_class(self) -> type:
        if self._method_class is None:
            from polisyos.foundry.methods.registry import get_registry
            reg = self._registry or get_registry()
            self._method_class = reg.get(self.fqn)
        return self._method_class

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        state: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SandboxResult:
        """
        Run the method.

        Parameters
        ----------
        state:
            Input state dict.  If None, *kwargs* are used as state.
        params:
            Parameter dict.  Defaults to empty.
        **kwargs:
            Convenience: if *state* is None, all kwargs are treated as state.

        Returns
        -------
        SandboxResult
        """
        if state is None:
            state = kwargs
        params = params or {}

        t0 = time.perf_counter()
        output = self.method_class.pure_step(state, params)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if not isinstance(output, dict):
            output = {"output": output}

        return SandboxResult(
            fqn=self.fqn,
            output=output,
            wall_time_ms=elapsed_ms,
            params_used=params,
        )

    def profile(
        self,
        state: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[SandboxResult, Any]:
        """
        Profile the method invocation.

        Returns
        -------
        (SandboxResult, MethodExecutionProfile)
        """
        from polisyos.foundry.methods.profiler import MethodProfiler
        if state is None:
            state = kwargs
        params = params or {}
        profiler = MethodProfiler()
        raw_result, profile = profiler.profile(self.method_class, state, params)
        if not isinstance(raw_result, dict):
            raw_result = {"output": raw_result}
        sandbox_result = SandboxResult(
            fqn=self.fqn,
            output=raw_result,
            wall_time_ms=profile.wall_time_ms,
            params_used=params,
        )
        return sandbox_result, profile

    def validate(self, run_smoke_test: bool = True) -> Any:
        """
        Validate the method class against the ABI contract.

        Returns a ``ValidationReport``.
        """
        from polisyos.foundry.methods.cli.validator import MethodValidator
        return MethodValidator(run_smoke_test=run_smoke_test).validate_class(
            self.method_class
        )

    def signature(self) -> Any:
        """Return the method's ``MethodSignature``."""
        return self.method_class.signature

    def metadata(self) -> Any:
        """Return the method's ``MethodMetadata``."""
        return self.method_class.metadata

    def html_repr(self) -> str:
        """Return an HTML summary of this method for Jupyter display."""
        sig = self.method_class.signature
        meta = self.method_class.metadata
        in_slots = "".join(
            f"<li><code>{s.name}</code> ({s.slot_type.value})</li>"
            for s in sorted(sig.input_slots, key=lambda x: x.name)
        )
        out_slots = "".join(
            f"<li><code>{s.name}</code> ({s.slot_type.value})</li>"
            for s in sorted(sig.output_slots, key=lambda x: x.name)
        )
        params = "".join(
            f"<li><code>{p.name}</code> = {p.default}</li>"
            for p in (sig.parameters or [])
        )
        tags = ", ".join(f"<code>{t}</code>" for t in sorted(meta.tags))
        return f"""
        <div style="border:1px solid #ccc; padding:12px; font-family:monospace">
          <h3>🔬 {self.fqn}</h3>
          <p><b>Description:</b> {meta.description}</p>
          <p><b>Backend:</b> {sig.backend.value} &nbsp;
             <b>Fidelity:</b> {sig.fidelity.value} &nbsp;
             <b>Complexity:</b> {sig.complexity.value if sig.complexity else '?'}</p>
          <p><b>Tags:</b> {tags}</p>
          <details><summary><b>Input Slots ({len(sig.input_slots)})</b></summary>
            <ul>{in_slots}</ul></details>
          <details><summary><b>Output Slots ({len(sig.output_slots)})</b></summary>
            <ul>{out_slots}</ul></details>
          <details><summary><b>Parameters ({len(sig.parameters or [])})</b></summary>
            <ul>{params}</ul></details>
        </div>
        """

    def _repr_html_(self) -> str:
        try:
            return self.html_repr()
        except Exception:
            return f"<code>MethodSandbox({self.fqn})</code>"

    def __repr__(self) -> str:
        return f"MethodSandbox(fqn={self.fqn!r})"

    # ------------------------------------------------------------------
    # Static comparison helper
    # ------------------------------------------------------------------

    @staticmethod
    def compare(
        fqns: list[str],
        state: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        registry: Any = None,
        **kwargs: Any,
    ) -> ComparisonResult:
        """
        Run multiple methods on the same inputs and compare outputs.

        Parameters
        ----------
        fqns:
            List of FQNs to compare.
        state:
            Input state dict.  If None, *kwargs* are used.
        params:
            Shared parameters.
        registry:
            Optional registry.

        Returns
        -------
        ComparisonResult
        """
        if state is None:
            state = kwargs
        params = params or {}
        results: dict[str, SandboxResult] = {}
        for fqn in fqns:
            sb = MethodSandbox(fqn, registry=registry)
            try:
                results[fqn] = sb.run(state=state, params=params)
            except Exception as exc:
                results[fqn] = SandboxResult(
                    fqn=fqn,
                    output={"error": str(exc)},
                    wall_time_ms=0.0,
                    params_used=params,
                )
        # Find shared output keys
        if results:
            shared = set.intersection(*[set(r.output.keys()) for r in results.values()])
        else:
            shared = set()
        return ComparisonResult(
            results=results,
            shared_keys=sorted(shared),
        )
