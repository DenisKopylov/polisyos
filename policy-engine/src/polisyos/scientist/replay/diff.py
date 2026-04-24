"""Semantic replay diff — structural comparison of workflow outputs."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.errors import ErrorCategory, PolicyOSError

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import ArtifactStore


class ReplayDiffInputError(PolicyOSError):
    """Raised when replay diff inputs are missing or structurally invalid."""

    default_stage = "scientist.replay.diff"
    default_category = ErrorCategory.VALIDATION


class DiffToleranceConfig(BaseModel):
    """Configuration for structural comparison tolerances."""

    model_config = ConfigDict(extra="forbid")

    numeric_rtol: float = 1e-5
    numeric_atol: float = 1e-8
    string_similarity_threshold: float = 0.95
    ignore_fields: list[str] = Field(default_factory=list)
    ignore_timestamps: bool = True

    # Distribution comparison (KS-test)
    distribution_p_threshold: float = 0.05
    distribution_min_samples: int = 10

    # Reordered list matching
    list_match_key: dict[str, str] = Field(default_factory=dict)
    allow_list_reorder: bool = False


class FieldDiff(BaseModel):
    """Diff result for a single field."""

    model_config = ConfigDict(extra="forbid")

    path: str
    original: Any = None
    replayed: Any = None
    similarity: float = Field(ge=0.0, le=1.0)
    tolerance_met: bool = True


class ReplayDiffResult(BaseModel):
    """Result of comparing original and replayed workflow outputs."""

    model_config = ConfigDict(extra="forbid")

    overall_similarity: float = Field(ge=0.0, le=1.0)
    field_diffs: list[FieldDiff] = Field(default_factory=list)
    structural_match: bool = True
    tolerance_config: DiffToleranceConfig = Field(default_factory=DiffToleranceConfig)
    causal_links: list[Any] = Field(default_factory=list)


# Type alias for custom comparator functions: (a, b, config) -> similarity
ComparatorFn = Callable[[Any, Any, DiffToleranceConfig], float]


def compute_replay_diff(
    original: dict[str, Any],
    replayed: dict[str, Any],
    config: DiffToleranceConfig | None = None,
    comparators: ComparatorRegistry | None = None,
) -> ReplayDiffResult:
    """Compute structural diff between original and replayed outputs.

    Recursively compares nested dicts, lists, numbers, and strings.
    Numbers use rtol/atol, strings use Levenshtein ratio.
    Lists of numbers can use KS-test for distribution comparison.
    """
    _validate_diff_inputs(original=original, replayed=replayed)
    cfg = config or DiffToleranceConfig()
    diffs: list[FieldDiff] = []

    _compare_recursive(original, replayed, "", cfg, diffs, comparators)

    if not diffs:
        return ReplayDiffResult(
            overall_similarity=1.0,
            field_diffs=[],
            structural_match=True,
            tolerance_config=cfg,
        )

    similarities = [d.similarity for d in diffs]
    overall = sum(similarities) / len(similarities) if similarities else 1.0
    structural = all(d.tolerance_met for d in diffs)

    return ReplayDiffResult(
        overall_similarity=overall,
        field_diffs=diffs,
        structural_match=structural,
        tolerance_config=cfg,
    )


def _validate_diff_inputs(
    *,
    original: dict[str, Any],
    replayed: dict[str, Any],
) -> None:
    if not isinstance(original, dict) or not original:
        raise ReplayDiffInputError(
            "original replay payload must be a non-empty object",
            code="empty_original",
        )
    if not isinstance(replayed, dict) or not replayed:
        raise ReplayDiffInputError(
            "replayed payload must be a non-empty object",
            code="empty_replayed",
        )


def _compare_recursive(
    a: Any,
    b: Any,
    path: str,
    cfg: DiffToleranceConfig,
    diffs: list[FieldDiff],
    comparators: ComparatorRegistry | None = None,
) -> None:
    """Recursively compare two values and accumulate diffs."""
    if path in cfg.ignore_fields:
        return

    if cfg.ignore_timestamps and _is_timestamp_field(path):
        return

    # Check custom comparator first
    if comparators is not None:
        comp = comparators.get(path)
        if comp is not None:
            sim = comp(a, b, cfg)
            if sim < 1.0:
                diffs.append(
                    FieldDiff(
                        path=path,
                        original=a,
                        replayed=b,
                        similarity=sim,
                        tolerance_met=sim >= 0.95,
                    )
                )
            return

    if isinstance(a, dict) and isinstance(b, dict):
        all_keys = set(a.keys()) | set(b.keys())
        for key in sorted(all_keys):
            child_path = f"{path}.{key}" if path else key
            if key not in a:
                diffs.append(
                    FieldDiff(
                        path=child_path,
                        original=None,
                        replayed=b[key],
                        similarity=0.0,
                        tolerance_met=False,
                    )
                )
            elif key not in b:
                diffs.append(
                    FieldDiff(
                        path=child_path,
                        original=a[key],
                        replayed=None,
                        similarity=0.0,
                        tolerance_met=False,
                    )
                )
            else:
                _compare_recursive(a[key], b[key], child_path, cfg, diffs, comparators)
        return

    if isinstance(a, list) and isinstance(b, list):
        # Distribution comparison for numeric lists
        if (
            len(a) >= cfg.distribution_min_samples
            and len(b) >= cfg.distribution_min_samples
            and _is_numeric_list(a)
            and _is_numeric_list(b)
        ):
            sim, tol_met = _distribution_similarity(
                [float(x) for x in a],
                [float(x) for x in b],
                cfg.distribution_p_threshold,
            )
            if sim < 1.0:
                diffs.append(
                    FieldDiff(
                        path=path,
                        original=f"<distribution n={len(a)}>",
                        replayed=f"<distribution n={len(b)}>",
                        similarity=sim,
                        tolerance_met=tol_met,
                    )
                )
            return

        # Reordered list matching
        if cfg.allow_list_reorder and a and b:
            key_field = cfg.list_match_key.get(path)
            if key_field is not None:
                _compare_list_by_key(a, b, path, key_field, cfg, diffs, comparators)
                return
            # Greedy similarity matching for small lists
            if len(a) <= 100 and len(b) <= 100:
                _compare_list_greedy(a, b, path, cfg, diffs, comparators)
                return

        # Default positional comparison
        max_len = max(len(a), len(b))
        for i in range(max_len):
            child_path = f"{path}[{i}]"
            if i >= len(a):
                diffs.append(
                    FieldDiff(
                        path=child_path,
                        original=None,
                        replayed=b[i],
                        similarity=0.0,
                        tolerance_met=False,
                    )
                )
            elif i >= len(b):
                diffs.append(
                    FieldDiff(
                        path=child_path,
                        original=a[i],
                        replayed=None,
                        similarity=0.0,
                        tolerance_met=False,
                    )
                )
            else:
                _compare_recursive(a[i], b[i], child_path, cfg, diffs, comparators)
        return

    # Leaf comparison
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        sim = _numeric_similarity(a, b, cfg.numeric_rtol, cfg.numeric_atol)
        if sim < 1.0:
            within = math.isclose(a, b, rel_tol=cfg.numeric_rtol, abs_tol=cfg.numeric_atol)
            diffs.append(
                FieldDiff(
                    path=path,
                    original=a,
                    replayed=b,
                    similarity=sim,
                    tolerance_met=within,
                )
            )
        return

    if isinstance(a, str) and isinstance(b, str):
        sim = _string_similarity(a, b)
        if sim < 1.0:
            diffs.append(
                FieldDiff(
                    path=path,
                    original=a,
                    replayed=b,
                    similarity=sim,
                    tolerance_met=sim >= cfg.string_similarity_threshold,
                )
            )
        return

    # Type mismatch or other types
    if a != b:
        sim = 1.0 if a == b else 0.0
        diffs.append(
            FieldDiff(
                path=path,
                original=a,
                replayed=b,
                similarity=sim,
                tolerance_met=False,
            )
        )


# ---------------------------------------------------------------------------
# Distribution comparison
# ---------------------------------------------------------------------------


def _is_numeric_list(lst: list[Any]) -> bool:
    """Check if all elements are numeric."""
    return all(isinstance(x, (int, float)) for x in lst)


def _distribution_similarity(
    a: list[float],
    b: list[float],
    p_threshold: float,
) -> tuple[float, bool]:
    """KS-test based distribution comparison with graceful fallback."""
    try:
        from scipy.stats import ks_2samp

        stat, p_value = ks_2samp(a, b)
        return (1.0 - stat, p_value >= p_threshold)
    except ImportError:
        # Fallback: compare means and stds
        mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
        std_a = (sum((x - mean_a) ** 2 for x in a) / len(a)) ** 0.5
        std_b = (sum((x - mean_b) ** 2 for x in b) / len(b)) ** 0.5
        mean_diff = abs(mean_a - mean_b) / max(abs(mean_a), abs(mean_b), 1e-10)
        std_diff = abs(std_a - std_b) / max(std_a, std_b, 1e-10)
        sim = max(0.0, 1.0 - (mean_diff + std_diff) / 2)
        return (sim, sim >= 1.0 - p_threshold)


# ---------------------------------------------------------------------------
# Reordered list matching
# ---------------------------------------------------------------------------


def _compare_list_by_key(
    a: list[Any],
    b: list[Any],
    path: str,
    key_field: str,
    cfg: DiffToleranceConfig,
    diffs: list[FieldDiff],
    comparators: ComparatorRegistry | None = None,
) -> None:
    """Match list elements by a key field, then compare matched pairs."""
    b_index: dict[Any, Any] = {}
    for item in b:
        if isinstance(item, dict) and key_field in item:
            b_index[item[key_field]] = item

    matched_b_keys: set[Any] = set()
    for item_a in a:
        if not isinstance(item_a, dict) or key_field not in item_a:
            continue
        key_val = item_a[key_field]
        if key_val in b_index:
            matched_b_keys.add(key_val)
            child_path = f"{path}[{key_field}={key_val}]"
            _compare_recursive(item_a, b_index[key_val], child_path, cfg, diffs, comparators)
        else:
            diffs.append(
                FieldDiff(
                    path=f"{path}[{key_field}={key_val}]",
                    original=item_a,
                    replayed=None,
                    similarity=0.0,
                    tolerance_met=False,
                )
            )

    for item_b in b:
        if isinstance(item_b, dict) and key_field in item_b:
            if item_b[key_field] not in matched_b_keys:
                diffs.append(
                    FieldDiff(
                        path=f"{path}[{key_field}={item_b[key_field]}]",
                        original=None,
                        replayed=item_b,
                        similarity=0.0,
                        tolerance_met=False,
                    )
                )


def _compare_list_greedy(
    a: list[Any],
    b: list[Any],
    path: str,
    cfg: DiffToleranceConfig,
    diffs: list[FieldDiff],
    comparators: ComparatorRegistry | None = None,
) -> None:
    """Greedy similarity-based list matching (order-independent)."""
    used_b: set[int] = set()
    for i, item_a in enumerate(a):
        best_j = -1
        best_sim = -1.0
        for j, item_b in enumerate(b):
            if j in used_b:
                continue
            sim = _quick_similarity(item_a, item_b, cfg)
            if sim > best_sim:
                best_sim = sim
                best_j = j
        if best_j >= 0 and best_sim > 0.5:
            used_b.add(best_j)
            child_path = f"{path}[~{i}]"
            _compare_recursive(item_a, b[best_j], child_path, cfg, diffs, comparators)
        else:
            diffs.append(
                FieldDiff(
                    path=f"{path}[{i}]",
                    original=item_a,
                    replayed=None,
                    similarity=0.0,
                    tolerance_met=False,
                )
            )

    for j, item_b in enumerate(b):
        if j not in used_b:
            diffs.append(
                FieldDiff(
                    path=f"{path}[+{j}]",
                    original=None,
                    replayed=item_b,
                    similarity=0.0,
                    tolerance_met=False,
                )
            )


def _quick_similarity(a: Any, b: Any, cfg: DiffToleranceConfig) -> float:
    """Quick similarity score for greedy matching (no recursion into diffs)."""
    if a == b:
        return 1.0
    if type(a) is not type(b):
        return 0.0
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return _numeric_similarity(a, b, cfg.numeric_rtol, cfg.numeric_atol)
    if isinstance(a, str) and isinstance(b, str):
        return _string_similarity(a, b)
    if isinstance(a, dict) and isinstance(b, dict):
        if not a and not b:
            return 1.0
        all_keys = set(a.keys()) | set(b.keys())
        common = sum(1 for k in all_keys if k in a and k in b and a[k] == b[k])
        return common / len(all_keys) if all_keys else 1.0
    return 0.0


# ---------------------------------------------------------------------------
# Leaf comparison helpers
# ---------------------------------------------------------------------------


def _numeric_similarity(a: float, b: float, rtol: float, atol: float) -> float:
    """Compute similarity between two numbers using rtol/atol."""
    if a == b:
        return 1.0
    diff = abs(a - b)
    threshold = atol + rtol * abs(b)
    if threshold == 0:
        return 0.0 if diff > 0 else 1.0
    ratio = diff / threshold
    return max(0.0, 1.0 - ratio)


def _string_similarity(a: str, b: str) -> float:
    """Compute similarity ratio using simple character-level comparison."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    # Simple ratio based on longest common subsequence length
    max_len = max(len(a), len(b))
    common = sum(1 for ca, cb in zip(a, b, strict=False) if ca == cb)
    return common / max_len


def _is_timestamp_field(path: str) -> bool:
    """Heuristic: detect timestamp-like field names."""
    lower = path.lower().rsplit(".", 1)[-1] if "." in path else path.lower()
    return any(
        kw in lower
        for kw in (
            "timestamp",
            "created_at",
            "updated_at",
            "started_at",
            "ended_at",
            "_at",
            "_time",
        )
    )


# ---------------------------------------------------------------------------
# Diff report persistence
# ---------------------------------------------------------------------------


def save_diff_report(
    result: ReplayDiffResult,
    store: ArtifactStore,
    run_id: str,
) -> Any:
    """Persist diff report to CAS as a JSON artifact."""
    from polisyos.core.artifacts.store import PutOptions

    return store.put_json(
        result.model_dump(mode="json"),
        PutOptions(
            kind=f"scientist.replay.diff_report.{run_id}",
            media_type="application/json",
        ),
    )


# ---------------------------------------------------------------------------
# Comparator registry (re-exported from comparators module)
# ---------------------------------------------------------------------------


class ComparatorRegistry:
    """Registry of custom field comparators for replay diff."""

    def __init__(self) -> None:
        self._comparators: dict[str, ComparatorFn] = {}

    def register(self, field_pattern: str, comparator: ComparatorFn) -> None:
        """Register a comparator for fields matching the pattern (fnmatch)."""
        self._comparators[field_pattern] = comparator

    def get(self, path: str) -> ComparatorFn | None:
        """Find a comparator for the given path (exact match, then fnmatch)."""
        if path in self._comparators:
            return self._comparators[path]
        import fnmatch

        for pattern, comp in self._comparators.items():
            if fnmatch.fnmatch(path, pattern):
                return comp
        return None
