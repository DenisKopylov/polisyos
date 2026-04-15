"""Comparator stack helpers shared by benchmark entrypoints."""

from __future__ import annotations

import os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmarks.runtime import ModuleProbe, probe_module


@dataclass(frozen=True)
class ComparatorSpec:
    label: str
    module_name: str
    distribution_name: str


_COMPARATOR_CATALOG: "OrderedDict[str, ComparatorSpec]" = OrderedDict(
    [
        ("econml", ComparatorSpec("econml", "econml", "econml")),
        ("zepid", ComparatorSpec("zepid", "zepid", "zepid")),
        ("stochtree", ComparatorSpec("stochtree", "stochtree", "stochtree")),
        ("dowhy", ComparatorSpec("dowhy", "dowhy", "dowhy")),
        ("y0", ComparatorSpec("y0", "y0", "y0")),
        ("lightgbm", ComparatorSpec("lightgbm", "lightgbm", "lightgbm")),
        ("causallib", ComparatorSpec("causallib", "causallib", "causallib")),
        ("causalml", ComparatorSpec("causalml", "causalml", "causalml")),
        ("pgmpy", ComparatorSpec("pgmpy", "pgmpy", "pgmpy")),
        ("ananke", ComparatorSpec("ananke", "ananke", "ananke-causal")),
        ("causal-learn", ComparatorSpec("causal-learn", "causallearn", "causal-learn")),
        ("tigramite", ComparatorSpec("tigramite", "tigramite", "tigramite")),
        ("pygformula", ComparatorSpec("pygformula", "pygformula", "pygformula")),
        ("pot", ComparatorSpec("pot", "ot", "pot")),
        ("openspiel", ComparatorSpec("openspiel", "pyspiel", "open_spiel")),
        ("nashpy", ComparatorSpec("nashpy", "nashpy", "nashpy")),
        ("pywhy-graphs", ComparatorSpec("pywhy-graphs", "pywhy_graphs", "pywhy-graphs")),
    ]
)

REQUIRED_ACCEPTANCE_COMPARATORS: "OrderedDict[str, str]" = OrderedDict(
    [
        (label, _COMPARATOR_CATALOG[label].distribution_name)
        for label in ("econml", "zepid", "stochtree", "dowhy", "y0", "lightgbm")
    ]
)

OPTIONAL_LEGACY_COMPARATORS: "OrderedDict[str, str]" = OrderedDict(
    [
        ("bartpy", "bartpy"),
        ("pymc_bart", "pymc-bart"),
    ]
)

COMPARATOR_GROUPS: "OrderedDict[str, tuple[str, ...]]" = OrderedDict(
    [
        (
            "effect_estimation_core",
            ("dowhy", "causallib", "econml", "causalml", "pgmpy", "zepid", "stochtree", "lightgbm"),
        ),
        (
            "symbolic_identification",
            ("y0", "ananke", "dowhy", "pgmpy"),
        ),
        (
            "discovery",
            ("causal-learn", "pgmpy", "tigramite"),
        ),
        (
            "temporal",
            ("pygformula", "tigramite", "econml"),
        ),
        (
            "distributional",
            ("pot",),
        ),
        (
            "strategic_solver",
            ("openspiel", "nashpy"),
        ),
        (
            "graph_ops",
            ("pywhy-graphs", "pgmpy"),
        ),
        (
            "legacy_acceptance_core",
            tuple(REQUIRED_ACCEPTANCE_COMPARATORS.keys()),
        ),
    ]
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _comparator_python_env_var(label: str) -> str:
    return f"BENCH_{label.upper().replace('-', '_')}_PYTHON"


def _candidate_python_executables(label: str) -> tuple[str, ...]:
    candidates: list[str] = []
    explicit = os.environ.get(_comparator_python_env_var(label), "").strip()
    if explicit:
        candidates.append(explicit)
    if label == "pygformula":
        temporal_explicit = os.environ.get("BENCH_TEMPORAL_PYTHON", "").strip()
        if temporal_explicit:
            candidates.append(temporal_explicit)
        candidates.extend(
            [
                str(_REPO_ROOT / ".venvs" / "bench-temporal" / "bin" / "python"),
                str(_REPO_ROOT / ".venv-bench-temporal" / "bin" / "python"),
                str(_REPO_ROOT / ".venvs" / "py311-bench" / "bin" / "python"),
            ]
        )
    ordered: list[str] = []
    for item in candidates:
        if item and item not in ordered:
            ordered.append(item)
    return tuple(ordered)


def probe_comparator(label: str) -> ModuleProbe:
    spec = _COMPARATOR_CATALOG[label]
    primary = probe_module(spec.module_name)
    if primary.available:
        return primary
    for python_executable in _candidate_python_executables(label):
        probe = probe_module(spec.module_name, python_executable=python_executable)
        if probe.available:
            return probe
    return primary


def _resolve_labels(
    *,
    required_labels: list[str] | tuple[str, ...] | set[str] | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
    default_to_legacy_required: bool = True,
) -> tuple[str, ...]:
    labels = OrderedDict.fromkeys(
        tuple(REQUIRED_ACCEPTANCE_COMPARATORS.keys()) if default_to_legacy_required else ()
    )
    for group_name in groups or ():
        if group_name not in COMPARATOR_GROUPS:
            raise ValueError(f"Unknown comparator group: {group_name}")
        for label in COMPARATOR_GROUPS[group_name]:
            labels[label] = None
    for label in required_labels or ():
        if label not in _COMPARATOR_CATALOG:
            raise ValueError(f"Unknown comparator label: {label}")
        labels[label] = None
    return tuple(labels.keys())


def all_comparator_distribution_names() -> dict[str, str]:
    """Return the full comparator catalog keyed by benchmark label."""
    return {
        label: spec.distribution_name
        for label, spec in _COMPARATOR_CATALOG.items()
    }


def comparator_labels_for_group(group_name: str) -> tuple[str, ...]:
    """Return comparator labels for a named suite-scoped group."""
    if group_name not in COMPARATOR_GROUPS:
        raise ValueError(f"Unknown comparator group: {group_name}")
    return tuple(COMPARATOR_GROUPS[group_name])


def comparator_distribution_names(
    *,
    required_labels: list[str] | tuple[str, ...] | set[str] | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
    default_to_legacy_required: bool = True,
) -> dict[str, str]:
    """Return distribution names for the selected comparator subset."""
    labels = _resolve_labels(
        required_labels=required_labels,
        groups=groups,
        default_to_legacy_required=default_to_legacy_required,
    )
    return {
        label: _COMPARATOR_CATALOG[label].distribution_name
        for label in labels
    }


def comparator_required_modules(
    *,
    required_labels: list[str] | tuple[str, ...] | set[str] | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
    default_to_legacy_required: bool = True,
) -> dict[str, bool]:
    """Return module availability flags for the selected comparator subset."""
    labels = _resolve_labels(
        required_labels=required_labels,
        groups=groups,
        default_to_legacy_required=default_to_legacy_required,
    )
    return {
        label: probe_comparator(label).available
        for label in labels
    }


def build_research_acceptance_comparator_status(
    *,
    required_labels: list[str] | tuple[str, ...] | set[str] | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
    default_to_legacy_required: bool = True,
) -> dict[str, str]:
    """Build a status map suitable for `preflight.comparator_status`."""
    labels = _resolve_labels(
        required_labels=required_labels,
        groups=groups,
        default_to_legacy_required=default_to_legacy_required,
    )
    return {
        label: _format_probe_status(probe_comparator(label))
        for label in labels
    }


def comparator_degraded_reasons(status: dict[str, Any]) -> list[str]:
    """Render human-readable degraded reasons from a comparator status map."""
    reasons: list[str] = []
    for label, value in status.items():
        if not str(value).startswith("available"):
            reasons.append(f"{label} comparator unavailable")
    return reasons


def _format_probe_status(probe: ModuleProbe) -> str:
    if probe.available:
        return "available"
    if probe.error:
        return f"{probe.status}: {probe.error}"
    return probe.status
