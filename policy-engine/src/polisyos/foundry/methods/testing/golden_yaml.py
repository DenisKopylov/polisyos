"""
YAML-driven golden test system for human-readable known-answer regression tests.

Complements the hash-based GoldenStore (golden.py) which does content-addressed
pytree comparison. This module provides:
- GoldenTestCase: a single known-answer test loaded from YAML
- GoldenRegistry: loads YAML files and runs verify_all against MethodRegistry
- Deep comparison of actual vs expected outputs with domain-appropriate tolerances
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field

from polisyos.foundry.methods.selection.registry import MethodRegistry

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class GoldenTestCase(BaseModel):
    """Single known-answer test loaded from YAML."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    method_fqn: str
    description: str = ""
    backend: str = "numpy"
    seed: int = 42
    input_data: dict[str, Any]
    input_params: dict[str, Any] = Field(default_factory=dict)
    expected_output: dict[str, Any]
    tolerances: dict[str, float] = Field(default_factory=lambda: {"rtol": 1e-5, "atol": 1e-8})
    tags: list[str] = Field(default_factory=list)
    skip_reason: str | None = None


class GoldenTestFile(BaseModel):
    """Collection of golden test cases from a single YAML file."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    version: str = "1.0"
    cases: list[GoldenTestCase]


class GoldenCaseResult(BaseModel):
    """Result of a single golden case verification."""

    case_id: str
    method_fqn: str
    passed: bool
    message: str = ""
    elapsed_ms: float = 0.0
    mismatches: list[str] = Field(default_factory=list)


class GoldenSuiteResult(BaseModel):
    """Aggregated result for a full golden verification run."""

    total: int
    passed: int
    failed: int
    skipped: int
    results: list[GoldenCaseResult]
    elapsed_ms: float = 0.0


# ---------------------------------------------------------------------------
# Deep comparison
# ---------------------------------------------------------------------------


def _deep_compare(
    actual: Any,
    expected: Any,
    rtol: float,
    atol: float,
    path: str = "",
) -> list[str]:
    """Recursively compare *actual* vs *expected*, returning mismatch descriptions."""
    mismatches: list[str] = []

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            mismatches.append(f"{path}: expected dict, got {type(actual).__name__}")
            return mismatches
        for key in expected:
            if key not in actual:
                mismatches.append(f"{path}.{key}: missing in actual output")
                continue
            mismatches.extend(
                _deep_compare(actual[key], expected[key], rtol, atol, f"{path}.{key}")
            )
        return mismatches

    if isinstance(expected, list):
        if not isinstance(actual, (list, tuple)):
            # actual might be ndarray
            if hasattr(actual, "tolist"):
                actual = actual.tolist()
            else:
                mismatches.append(f"{path}: expected list, got {type(actual).__name__}")
                return mismatches
        if len(actual) != len(expected):
            mismatches.append(
                f"{path}: length mismatch: actual={len(actual)}, expected={len(expected)}"
            )
            return mismatches
        for i, (a, e) in enumerate(zip(actual, expected)):
            mismatches.extend(_deep_compare(a, e, rtol, atol, f"{path}[{i}]"))
        return mismatches

    # Leaf comparison (scalar or array)
    try:
        a_val = _to_float(actual)
        e_val = _to_float(expected)
    except (TypeError, ValueError):
        # Non-numeric: exact equality
        if actual != expected:
            mismatches.append(f"{path}: {actual!r} != {expected!r}")
        return mismatches

    if not np.isfinite(e_val):
        if not np.isfinite(a_val) and np.sign(e_val) == np.sign(a_val):
            return mismatches
        mismatches.append(f"{path}: expected={e_val}, got={a_val}")
        return mismatches

    diff = abs(a_val - e_val)
    threshold = atol + rtol * abs(e_val)
    if diff > threshold:
        mismatches.append(
            f"{path}: expected={e_val}, got={a_val}, "
            f"diff={diff:.2e}, threshold={threshold:.2e} (rtol={rtol}, atol={atol})"
        )
    return mismatches


def _to_float(v: Any) -> float:
    """Convert scalar-like value to float."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, np.generic):
        return float(v)
    if hasattr(v, "item"):
        return float(v.item())
    raise TypeError(f"Cannot convert {type(v).__name__} to float")


# ---------------------------------------------------------------------------
# State construction helpers
# ---------------------------------------------------------------------------


def _try_construct_state(method_class: type, input_data: dict[str, Any]) -> Any:
    """Try to construct the expected state type for a method.

    Some methods expect Pydantic models (PanelData, TabularData, etc.).
    We try ``materialize_input`` first, then pass the raw dict.
    """
    if hasattr(method_class, "materialize_input"):
        try:
            return method_class.materialize_input(input_data, input_data)
        except Exception:
            pass

    # Convert list values to numpy arrays for methods that expect them
    converted: dict[str, Any] = {}
    for k, v in input_data.items():
        if isinstance(v, list):
            try:
                arr = np.asarray(v, dtype=float)
                converted[k] = arr
            except (TypeError, ValueError):
                converted[k] = v
        else:
            converted[k] = v
    return converted


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class GoldenRegistry:
    """Loads and manages YAML golden test files."""

    def __init__(self, golden_dir: Path | str) -> None:
        self._dir = Path(golden_dir)
        self._files: list[GoldenTestFile] | None = None

    def load_all(self) -> list[GoldenTestFile]:
        if self._files is not None:
            return self._files
        files: list[GoldenTestFile] = []
        if not self._dir.exists():
            self._files = files
            return files
        for yaml_path in sorted(self._dir.glob("*.yaml")):
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if raw is None:
                continue
            files.append(GoldenTestFile.model_validate(raw))
        self._files = files
        return files

    def all_cases(self) -> list[GoldenTestCase]:
        cases: list[GoldenTestCase] = []
        for f in self.load_all():
            cases.extend(f.cases)
        return cases

    def cases_by_domain(self, domain: str) -> list[GoldenTestCase]:
        for f in self.load_all():
            if f.domain == domain:
                return list(f.cases)
        return []

    def cases_by_tag(self, tag: str) -> list[GoldenTestCase]:
        return [c for c in self.all_cases() if tag in c.tags]

    def verify_case(self, case: GoldenTestCase, registry: MethodRegistry) -> GoldenCaseResult:
        t0 = time.perf_counter()
        try:
            method_class = registry.get(case.method_fqn)
        except (KeyError, Exception) as exc:
            return GoldenCaseResult(
                case_id=case.id,
                method_fqn=case.method_fqn,
                passed=False,
                message=f"Method lookup failed: {exc}",
                elapsed_ms=(time.perf_counter() - t0) * 1000,
            )

        state = _try_construct_state(method_class, case.input_data)

        np.random.seed(case.seed)
        try:
            output = method_class.pure_step(state, case.input_params)
        except Exception as exc:
            return GoldenCaseResult(
                case_id=case.id,
                method_fqn=case.method_fqn,
                passed=False,
                message=f"pure_step raised {type(exc).__name__}: {exc}",
                elapsed_ms=(time.perf_counter() - t0) * 1000,
            )

        # Normalize output: if tuple (e.g. optimization), take first element
        if isinstance(output, tuple):
            output = output[0]

        # Normalize Pydantic result models to dicts
        actual = _normalize_output(output)

        rtol = case.tolerances.get("rtol", 1e-5)
        atol = case.tolerances.get("atol", 1e-8)
        mismatches = _deep_compare(actual, case.expected_output, rtol, atol)

        elapsed = (time.perf_counter() - t0) * 1000
        if mismatches:
            return GoldenCaseResult(
                case_id=case.id,
                method_fqn=case.method_fqn,
                passed=False,
                message=f"{len(mismatches)} mismatch(es)",
                elapsed_ms=elapsed,
                mismatches=mismatches,
            )
        return GoldenCaseResult(
            case_id=case.id,
            method_fqn=case.method_fqn,
            passed=True,
            message="OK",
            elapsed_ms=elapsed,
        )

    def verify_all(
        self,
        registry: MethodRegistry,
        *,
        domain: str | None = None,
    ) -> GoldenSuiteResult:
        cases = self.cases_by_domain(domain) if domain else self.all_cases()
        t0 = time.perf_counter()
        results: list[GoldenCaseResult] = []
        passed = failed = skipped = 0
        for case in cases:
            if case.skip_reason:
                skipped += 1
                results.append(
                    GoldenCaseResult(
                        case_id=case.id,
                        method_fqn=case.method_fqn,
                        passed=True,
                        message=f"SKIPPED: {case.skip_reason}",
                    )
                )
                continue
            r = self.verify_case(case, registry)
            results.append(r)
            if r.passed:
                passed += 1
            else:
                failed += 1
        return GoldenSuiteResult(
            total=len(cases),
            passed=passed,
            failed=failed,
            skipped=skipped,
            results=results,
            elapsed_ms=(time.perf_counter() - t0) * 1000,
        )


# ---------------------------------------------------------------------------
# Output normalization
# ---------------------------------------------------------------------------


def _normalize_output(output: Any) -> Any:
    """Recursively convert Pydantic models and ndarrays to plain dicts/lists."""
    if isinstance(output, BaseModel):
        return _normalize_output(output.model_dump())
    if isinstance(output, dict):
        return {k: _normalize_output(v) for k, v in output.items()}
    if isinstance(output, (list, tuple)):
        return [_normalize_output(x) for x in output]
    if isinstance(output, np.ndarray):
        return output.tolist()
    if isinstance(output, np.generic):
        return output.item()
    return output
