"""
Compatibility Matrix — which method versions work with which runtime versions.

``CompatibilityMatrix`` answers the question:
    "Is method ``causal.did.standard@1.0.0`` compatible with runtime 4.x?"

Compatibility is defined by version range rules stored on ``MethodMetadata``.
When no explicit range is declared, a method registered in the current runtime
is treated as COMPATIBLE with the current runtime major version.

Usage::

    from polisyos.foundry.methods.lifecycle.compat_matrix import CompatibilityMatrix

    matrix = CompatibilityMatrix()
    matrix.generate(registry, runtime_versions=["3.x", "4.x"])

    print(matrix.to_markdown())
    df = matrix.to_dataframe()   # requires pandas
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd

    from polisyos.foundry.methods.base import MethodSignature
    from polisyos.foundry.methods.selection.registry import MethodRegistry

__all__ = [
    "CellStatus",
    "CompatibilityCell",
    "CompatibilityMatrix",
]

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

CellStatus = Literal["COMPATIBLE", "DEPRECATED", "INCOMPATIBLE", "UNKNOWN"]

_CURRENT_RUNTIME_VERSION = "4.x"


@dataclass(frozen=True)
class CompatibilityCell:
    """A single cell in the compatibility matrix."""

    method_fqn: str
    runtime_version: str
    status: CellStatus
    note: str = ""


# ---------------------------------------------------------------------------
# CompatibilityMatrix
# ---------------------------------------------------------------------------


@dataclass
class CompatibilityMatrix:
    """
    Compatibility matrix between method versions and runtime versions.

    Attributes
    ----------
    runtime_versions:
        The runtime versions to include as columns (e.g. ``["3.x", "4.x"]``).
    method_fqns:
        Ordered list of method FQNs (row keys).
    cells:
        Mapping ``(method_fqn, runtime_version) → CellStatus``.
    """

    runtime_versions: list[str] = field(default_factory=list)
    method_fqns: list[str] = field(default_factory=list)
    cells: dict[tuple[str, str], CompatibilityCell] = field(default_factory=dict)

    def generate(
        self,
        registry: MethodRegistry,
        runtime_versions: list[str] | None = None,
    ) -> None:
        """
        Populate the matrix from a live *registry*.

        Parameters
        ----------
        registry:
            The :class:`~polisyos.foundry.methods.selection.registry.MethodRegistry`
            to inspect.
        runtime_versions:
            Runtime versions to include.  Defaults to ``["3.x", "4.x"]``.
        """
        self.runtime_versions = runtime_versions or ["3.x", "4.x"]
        sigs = list(registry.list_all())
        self.method_fqns = sorted(sig.fqn for sig in sigs)
        self.cells.clear()

        for sig in sigs:
            entry = registry.get_entry(sig.fqn)
            meta = entry.metadata if entry else None

            for rv in self.runtime_versions:
                status, note = self._classify(sig, meta, rv)
                self.cells[(sig.fqn, rv)] = CompatibilityCell(
                    method_fqn=sig.fqn,
                    runtime_version=rv,
                    status=status,
                    note=note,
                )

    def _classify(
        self,
        sig: MethodSignature,  # type: ignore[name-defined]  # forward ref
        meta: object | None,
        runtime_version: str,
    ) -> tuple[CellStatus, str]:
        """Return (status, note) for a method × runtime version pair."""
        from polisyos.foundry.methods.selection.resolution import SemVer

        # Methods with deprecated tags are marked DEPRECATED
        if meta is not None:
            tags = getattr(meta, "tags", frozenset())
            if "deprecated" in tags:
                return "DEPRECATED", "tagged deprecated"

        # Parse method version
        try:
            method_ver = SemVer.parse(sig.version)
        except ValueError:
            return "UNKNOWN", f"unparseable version {sig.version!r}"

        # Runtime version major (e.g. "4.x" → 4)
        try:
            rt_major = int(runtime_version.split(".")[0])
        except (ValueError, IndexError):
            return "UNKNOWN", f"unparseable runtime {runtime_version!r}"

        # Pre-1.0 methods are experimental — only compatible with current runtime
        if method_ver.major == 0:
            current_major = int(_CURRENT_RUNTIME_VERSION.split(".")[0])
            if rt_major == current_major:
                return "COMPATIBLE", "pre-1.0 method, current runtime only"
            return "INCOMPATIBLE", "pre-1.0 method only supported in current runtime"

        # Methods v1+ are compatible with runtime >= their major version
        if rt_major >= method_ver.major:
            return "COMPATIBLE", ""

        return "INCOMPATIBLE", f"method v{method_ver.major} requires runtime {method_ver.major}.x+"

    # ------------------------------------------------------------------
    # Output formatters
    # ------------------------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:  # type: ignore[name-defined]
        """
        Return the matrix as a ``pandas.DataFrame``.

        Columns are runtime versions; rows are method FQNs.

        Raises
        ------
        ImportError
            If pandas is not installed.
        """
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "pandas is required for to_dataframe(). Install with: pip install pandas"
            ) from exc

        rows = []
        for fqn in self.method_fqns:
            row: dict[str, str] = {"method": fqn}
            for rv in self.runtime_versions:
                cell = self.cells.get((fqn, rv))
                row[rv] = cell.status if cell else "UNKNOWN"
            rows.append(row)

        return pd.DataFrame(rows).set_index("method")

    def to_markdown(self) -> str:
        """Return the matrix as a Markdown table."""
        if not self.method_fqns or not self.runtime_versions:
            return "_Empty compatibility matrix._"

        header = "| Method | " + " | ".join(self.runtime_versions) + " |"
        sep = (
            "|--------|" + "|".join("-" * max(5, len(rv) + 2) for rv in self.runtime_versions) + "|"
        )

        lines = [header, sep]
        for fqn in self.method_fqns:
            cells_row = []
            for rv in self.runtime_versions:
                cell = self.cells.get((fqn, rv))
                status = cell.status if cell else "UNKNOWN"
                emoji = {
                    "COMPATIBLE": "✅",
                    "DEPRECATED": "⚠️",
                    "INCOMPATIBLE": "❌",
                    "UNKNOWN": "❓",
                }.get(status, "❓")
                cells_row.append(f"{emoji} {status}")
            lines.append(f"| `{fqn}` | " + " | ".join(cells_row) + " |")

        summary = self._summary()
        lines.append("")
        lines.append(summary)
        return "\n".join(lines)

    def _summary(self) -> str:
        from collections import Counter

        counts: Counter[str] = Counter()
        for cell in self.cells.values():
            counts[cell.status] += 1
        parts = [
            f"**{v}**: {counts[v]}"
            for v in ("COMPATIBLE", "DEPRECATED", "INCOMPATIBLE", "UNKNOWN")
            if v in counts
        ]
        return "_Summary: " + " | ".join(parts) + "_"

    def compatible_runtimes(self, method_fqn: str) -> list[str]:
        """Return the list of runtime versions compatible with *method_fqn*."""
        return [
            rv
            for rv in self.runtime_versions
            if self.cells.get((method_fqn, rv), CompatibilityCell(method_fqn, rv, "UNKNOWN")).status
            == "COMPATIBLE"
        ]

    def incompatible_methods(self, runtime_version: str) -> list[str]:
        """Return FQNs of methods incompatible with *runtime_version*."""
        return [
            fqn
            for fqn in self.method_fqns
            if self.cells.get(
                (fqn, runtime_version), CompatibilityCell(fqn, runtime_version, "UNKNOWN")
            ).status
            == "INCOMPATIBLE"
        ]

    def __repr__(self) -> str:
        return (
            f"<CompatibilityMatrix "
            f"methods={len(self.method_fqns)} "
            f"runtimes={self.runtime_versions}>"
        )
