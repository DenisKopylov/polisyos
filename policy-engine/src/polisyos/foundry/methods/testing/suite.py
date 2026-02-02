"""
Comprehensive test suite for FoundryMethod protocol verification.

Tests:
    - Protocol compliance (signature, metadata, staticmethod)
    - Law F enforcement (arrays-only inputs/outputs)
    - JAX compatibility (jit, vmap, grad)
    - Numerical stability (NaN/Inf detection)
    - Determinism (eager and JIT outputs)
    - Compile key determinism (Law H)
"""
from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, ClassVar

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.foundry.methods.base import (
    FoundryMethod,
    MethodMetadata,
    MethodSignature,
)
from polisyos.foundry.methods.specialization import specialization_from_signature_and_state

try:  # JAX >= 0.4
    from jax.tree_util import tree_flatten_with_path
except Exception:  # pragma: no cover - fallback
    def tree_flatten_with_path(tree: Any):
        leaves, treedef = jax.tree_util.tree_flatten(tree)
        return [((), leaf) for leaf in leaves], treedef


# =============================================================================
# Result Types
# =============================================================================


class CheckCategory(Enum):
    """Categories of test checks."""

    PROTOCOL = auto()
    SIGNATURE = auto()
    LAW_F = auto()
    JAX_JIT = auto()
    JAX_VMAP = auto()
    JAX_GRAD = auto()
    NUMERICAL = auto()
    DETERMINISM = auto()


@dataclass(frozen=True, slots=True)
class TestCheck:
    """
    A single test check result.

    Attributes:
        name: Unique identifier for this check
        category: Classification of check type
        passed: Whether the check succeeded
        message: Human-readable description (empty if passed)
        duration_ms: Time taken to execute check (if measured)
    """

    name: str
    category: CheckCategory
    passed: bool
    message: str = ""
    duration_ms: float | None = None

    def __bool__(self) -> bool:
        return self.passed

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        base = f"[{status}] {self.name}"
        if self.message:
            base += f": {self.message}"
        if self.duration_ms is not None:
            base += f" ({self.duration_ms:.2f}ms)"
        return base


@dataclass(slots=True)
class TestResult:
    """
    Aggregated result of running a test suite.

    Provides summary statistics and filtering capabilities for
    analyzing test outcomes.
    """

    method_fqn: str
    checks: list[TestCheck] = field(default_factory=list)
    total_duration_ms: float = 0.0

    @property
    def passed(self) -> bool:
        """True if all checks passed."""
        return all(c.passed for c in self.checks)

    @property
    def passed_count(self) -> int:
        """Number of passing checks."""
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed_count(self) -> int:
        """Number of failing checks."""
        return sum(1 for c in self.checks if not c.passed)

    @property
    def total_count(self) -> int:
        """Total number of checks."""
        return len(self.checks)

    def by_category(self, category: CheckCategory) -> list[TestCheck]:
        """Filter checks by category."""
        return [c for c in self.checks if c.category == category]

    def failures(self) -> list[TestCheck]:
        """Get all failing checks."""
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        """Human-readable summary string."""
        status = "PASS" if self.passed else "FAIL"
        return (
            f"{self.method_fqn}: {status} "
            f"({self.passed_count}/{self.total_count} checks, "
            f"{self.total_duration_ms:.1f}ms)"
        )

    def __str__(self) -> str:
        lines = [self.summary(), ""]
        for check in self.checks:
            lines.append(f"  {check}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"TestResult(fqn={self.method_fqn!r}, "
            f"passed={self.passed_count}/{self.total_count})"
        )


# =============================================================================
# Helper Functions
# =============================================================================


def _timed_check(
    name: str,
    category: CheckCategory,
    func: Callable[[], tuple[bool, str]],
) -> TestCheck:
    """Execute a check function and time it."""
    start = time.perf_counter()
    try:
        passed, message = func()
    except Exception as exc:  # pragma: no cover - defensive
        passed, message = False, f"Exception: {type(exc).__name__}: {exc}"
    duration_ms = (time.perf_counter() - start) * 1000
    return TestCheck(
        name=name,
        category=category,
        passed=passed,
        message=message,
        duration_ms=duration_ms,
    )


def _format_path(path: tuple[Any, ...]) -> str:
    if not path:
        return "root"
    parts: list[str] = []
    for key in path:
        if hasattr(key, "key"):
            parts.append(f"[{key.key!r}]")
        elif hasattr(key, "idx"):
            parts.append(f"[{key.idx}]")
        elif hasattr(key, "name"):
            parts.append(f".{key.name}")
        else:
            parts.append(f"[{key!r}]")
    rendered = "".join(parts)
    return rendered[1:] if rendered.startswith(".") else rendered


def _is_array_like(value: Any) -> bool:
    return hasattr(value, "shape") and hasattr(value, "dtype")


def _collect_non_array_leaves(tree: Any) -> list[str]:
    issues: list[str] = []
    paths_and_leaves, _ = tree_flatten_with_path(tree)
    for path, leaf in paths_and_leaves:
        if _is_array_like(leaf):
            arr = np.asarray(leaf)
            if arr.dtype == object:
                issues.append(f"{_format_path(path)} (object dtype)")
            continue
        issues.append(f"{_format_path(path)} ({type(leaf).__name__})")
    return issues


def _trees_allclose(
    a: Any,
    b: Any,
    rtol: float = 1e-5,
    atol: float = 1e-8,
    equal_nan: bool = True,
) -> bool:
    """Check if two pytrees are approximately equal."""
    a_leaves, a_def = jax.tree_util.tree_flatten(a)
    b_leaves, b_def = jax.tree_util.tree_flatten(b)

    if a_def != b_def:
        return False

    for la, lb in zip(a_leaves, b_leaves):
        if _is_array_like(la) and _is_array_like(lb):
            la_arr = np.asarray(la)
            lb_arr = np.asarray(lb)
            if la_arr.shape != lb_arr.shape:
                return False
            if la_arr.dtype != lb_arr.dtype:
                return False
            if not np.allclose(la_arr, lb_arr, rtol=rtol, atol=atol, equal_nan=equal_nan):
                return False
        elif isinstance(la, (int, float)) and isinstance(lb, (int, float)):
            if not np.isclose(la, lb, rtol=rtol, atol=atol, equal_nan=equal_nan):
                return False
        elif la != lb:
            return False

    return True


def _trees_equal(a: Any, b: Any) -> bool:
    """Check if two pytrees are exactly equal (bit-wise for arrays)."""
    a_leaves, a_def = jax.tree_util.tree_flatten(a)
    b_leaves, b_def = jax.tree_util.tree_flatten(b)

    if a_def != b_def:
        return False

    for la, lb in zip(a_leaves, b_leaves):
        if _is_array_like(la) and _is_array_like(lb):
            la_arr = np.asarray(la)
            lb_arr = np.asarray(lb)
            if la_arr.shape != lb_arr.shape:
                return False
            if la_arr.dtype != lb_arr.dtype:
                return False
            if not np.array_equal(la_arr, lb_arr, equal_nan=True):
                return False
        elif la != lb:
            return False

    return True


def _block_until_ready(tree: Any) -> Any:
    def _block(x: Any) -> Any:
        if hasattr(x, "block_until_ready"):
            return x.block_until_ready()
        return x

    return jax.tree_util.tree_map(_block, tree)


def _check_finite(tree: Any) -> tuple[bool, list[str]]:
    """Check all arrays in pytree for NaN/Inf values."""
    problems: list[str] = []
    paths_and_leaves, _ = tree_flatten_with_path(tree)
    for path, leaf in paths_and_leaves:
        if _is_array_like(leaf):
            arr = np.asarray(leaf)
            if not np.all(np.isfinite(arr)):
                nan_count = int(np.sum(np.isnan(arr)))
                inf_count = int(np.sum(np.isinf(arr)))
                problems.append(
                    f"{_format_path(path)}: {nan_count} NaN, {inf_count} Inf"
                )
    return len(problems) == 0, problems


# =============================================================================
# MethodTestSuite
# =============================================================================


class MethodTestSuite:
    """
    Comprehensive test suite for any FoundryMethod implementation.
    """

    DEFAULT_DETERMINISM_RUNS: ClassVar[int] = 3
    DEFAULT_RTOL: ClassVar[float] = 1e-5
    DEFAULT_ATOL: ClassVar[float] = 1e-8

    def __init__(
        self,
        method_class: type[FoundryMethod],
        *,
        rtol: float | None = None,
        atol: float | None = None,
        vmap_in_axes: Any | None = None,
        vmap_batch_size: int = 2,
    ):
        """
        Initialize test suite for a FoundryMethod.

        Args:
            method_class: The FoundryMethod class to test
            rtol: Relative tolerance for numerical comparisons
            atol: Absolute tolerance for numerical comparisons
            vmap_in_axes: Optional in_axes for vmap (state, params)
            vmap_batch_size: Batch size used for vmap testing
        """
        self.method = method_class
        self._rtol = rtol if rtol is not None else self.DEFAULT_RTOL
        self._atol = atol if atol is not None else self.DEFAULT_ATOL
        self._vmap_in_axes = vmap_in_axes
        self._vmap_batch_size = vmap_batch_size

        self.sig: MethodSignature | None = getattr(method_class, "signature", None)
        self.meta: MethodMetadata | None = getattr(method_class, "metadata", None)

    def run_all(
        self,
        sample_state: Any,
        sample_params: dict[str, Any],
        *,
        determinism_runs: int | None = None,
        skip_grad: bool = False,
    ) -> TestResult:
        """Run all test categories."""
        start_time = time.perf_counter()
        checks: list[TestCheck] = []

        checks.extend(self.check_protocol())
        checks.extend(self.check_signature())
        checks.extend(self.check_arrays_only_inputs(sample_state, sample_params))
        checks.extend(
            self.check_jax_ops(
                sample_state,
                sample_params,
                skip_grad=skip_grad,
            )
        )
        checks.extend(self.check_numerical_stability(sample_state, sample_params))
        checks.extend(self.check_arrays_only_output(sample_state, sample_params))
        checks.extend(
            self.check_determinism(
                sample_state,
                sample_params,
                n_runs=determinism_runs or self.DEFAULT_DETERMINISM_RUNS,
            )
        )
        checks.extend(self.check_compile_key_determinism(sample_state, sample_params))

        total_duration = (time.perf_counter() - start_time) * 1000
        fqn = self.sig.fqn if self.sig else f"{self.method.__module__}.{self.method.__name__}"

        return TestResult(
            method_fqn=fqn,
            checks=checks,
            total_duration_ms=total_duration,
        )

    # ------------------------------------------------------------------
    # Protocol Compliance Checks
    # ------------------------------------------------------------------

    def check_protocol(self) -> list[TestCheck]:
        """Verify FoundryMethod protocol compliance."""
        checks: list[TestCheck] = []

        has_sig = hasattr(self.method, "signature")
        checks.append(
            TestCheck(
                name="has_signature",
                category=CheckCategory.PROTOCOL,
                passed=has_sig,
                message="" if has_sig else "Missing 'signature' class attribute",
            )
        )

        if has_sig:
            sig = getattr(self.method, "signature")
            is_sig_type = isinstance(sig, MethodSignature)
            checks.append(
                TestCheck(
                    name="signature_type",
                    category=CheckCategory.PROTOCOL,
                    passed=is_sig_type,
                    message="" if is_sig_type else f"Expected MethodSignature, got {type(sig).__name__}",
                )
            )

        has_meta = hasattr(self.method, "metadata")
        checks.append(
            TestCheck(
                name="has_metadata",
                category=CheckCategory.PROTOCOL,
                passed=has_meta,
                message="" if has_meta else "Missing 'metadata' class attribute",
            )
        )

        if has_meta:
            meta = getattr(self.method, "metadata")
            is_meta_type = isinstance(meta, MethodMetadata)
            checks.append(
                TestCheck(
                    name="metadata_type",
                    category=CheckCategory.PROTOCOL,
                    passed=is_meta_type,
                    message="" if is_meta_type else f"Expected MethodMetadata, got {type(meta).__name__}",
                )
            )

        has_pure_step = hasattr(self.method, "pure_step")
        checks.append(
            TestCheck(
                name="has_pure_step",
                category=CheckCategory.PROTOCOL,
                passed=has_pure_step,
                message="" if has_pure_step else "Missing 'pure_step' method",
            )
        )

        if has_pure_step:
            pure_step_attr = inspect.getattr_static(self.method, "pure_step")
            is_static = isinstance(pure_step_attr, staticmethod)
            checks.append(
                TestCheck(
                    name="pure_step_is_static",
                    category=CheckCategory.PROTOCOL,
                    passed=is_static,
                    message="" if is_static else "pure_step must be @staticmethod (Law F)",
                )
            )

        if self.sig is not None:
            params = getattr(type(self.sig), "__dataclass_params__", None)
            is_frozen = bool(params and params.frozen)
            checks.append(
                TestCheck(
                    name="signature_frozen",
                    category=CheckCategory.PROTOCOL,
                    passed=is_frozen,
                    message="" if is_frozen else "Signature must be frozen dataclass",
                )
            )

        return checks

    # ------------------------------------------------------------------
    # Signature Validity Checks
    # ------------------------------------------------------------------

    def check_signature(self) -> list[TestCheck]:
        """Verify signature is well-formed."""
        checks: list[TestCheck] = []

        if self.sig is None:
            checks.append(
                TestCheck(
                    name="signature_available",
                    category=CheckCategory.SIGNATURE,
                    passed=False,
                    message="No signature to validate",
                )
            )
            return checks

        has_slots = bool(self.sig.input_slots or self.sig.output_slots)
        checks.append(
            TestCheck(
                name="has_slots",
                category=CheckCategory.SIGNATURE,
                passed=has_slots,
                message="" if has_slots else "Method needs input or output slots",
            )
        )

        try:
            parts = self.sig.version.split(".")
            is_semver = (
                len(parts) == 3
                and all(p.isdigit() for p in parts)
                and all(int(p) >= 0 for p in parts)
            )
        except Exception:
            is_semver = False
        checks.append(
            TestCheck(
                name="valid_version",
                category=CheckCategory.SIGNATURE,
                passed=is_semver,
                message="" if is_semver else f"Invalid semver: {self.sig.version!r}",
            )
        )

        ns = self.sig.namespace
        ns_parts = ns.split(".") if ns else []
        valid_ns = bool(ns_parts) and all(p.isidentifier() for p in ns_parts)
        checks.append(
            TestCheck(
                name="valid_namespace",
                category=CheckCategory.SIGNATURE,
                passed=valid_ns,
                message="" if valid_ns else f"Invalid namespace: {ns!r}",
            )
        )

        all_slots = list(self.sig.input_slots) + list(self.sig.output_slots)
        slot_names = [s.name for s in all_slots]
        unique_names = len(slot_names) == len(set(slot_names))
        checks.append(
            TestCheck(
                name="unique_slot_names",
                category=CheckCategory.SIGNATURE,
                passed=unique_names,
                message="" if unique_names else "Duplicate slot names detected",
            )
        )

        return checks

    # ------------------------------------------------------------------
    # Law F Checks
    # ------------------------------------------------------------------

    def check_arrays_only_inputs(self, state: Any, params: dict[str, Any]) -> list[TestCheck]:
        """Ensure state and params contain only array leaves."""
        checks: list[TestCheck] = []

        def check_inputs() -> tuple[bool, str]:
            issues = _collect_non_array_leaves(state)
            issues += _collect_non_array_leaves(params)
            if issues:
                sample = ", ".join(issues[:3])
                return False, f"Non-array inputs: {sample}"
            return True, ""

        checks.append(_timed_check("arrays_only_inputs", CheckCategory.LAW_F, check_inputs))
        return checks

    def check_arrays_only_output(self, state: Any, params: dict[str, Any]) -> list[TestCheck]:
        """Ensure method output contains only array leaves."""
        checks: list[TestCheck] = []

        if not hasattr(self.method, "pure_step"):
            return checks

        def check_output() -> tuple[bool, str]:
            output = self.method.pure_step(state, params)
            issues = _collect_non_array_leaves(output)
            if issues:
                sample = ", ".join(issues[:3])
                return False, f"Non-array output: {sample}"
            return True, ""

        checks.append(_timed_check("arrays_only_output", CheckCategory.LAW_F, check_output))
        return checks

    # ------------------------------------------------------------------
    # JAX Compatibility Checks
    # ------------------------------------------------------------------

    def _resolve_vmap_in_axes(self) -> Any | None:
        if self._vmap_in_axes is not None:
            return self._vmap_in_axes
        if hasattr(self.method, "vmap_in_axes"):
            return getattr(self.method, "vmap_in_axes")
        if hasattr(self.method, "__vmap_in_axes__"):
            return getattr(self.method, "__vmap_in_axes__")
        return None

    def _expand_in_axes(self, tree: Any, axes: Any) -> Any:
        if axes is None or isinstance(axes, int):
            return jax.tree_util.tree_map(lambda _: axes, tree)
        return axes

    def _batch_tree(self, tree: Any, axes_tree: Any) -> Any:
        def batch_leaf(leaf: Any, axis: Any) -> Any:
            if axis is None:
                return leaf
            if not isinstance(axis, int):
                raise TypeError(f"Unsupported vmap axis type: {type(axis).__name__}")
            if not _is_array_like(leaf):
                raise TypeError("Non-array leaf cannot be vmapped")
            return jnp.stack([leaf] * self._vmap_batch_size, axis=axis)

        return jax.tree_util.tree_map(batch_leaf, tree, axes_tree)

    def check_jax_ops(
        self,
        state: Any,
        params: dict[str, Any],
        *,
        skip_grad: bool = False,
    ) -> list[TestCheck]:
        """Test JAX transformations (jit, vmap, grad)."""
        checks: list[TestCheck] = []

        if not hasattr(self.method, "pure_step"):
            return checks

        pure_step = self.method.pure_step

        supports_jit = self.sig.supports_jit if self.sig else True
        if supports_jit:
            def check_jit() -> tuple[bool, str]:
                jitted = jax.jit(pure_step)
                result = jitted(state, params)
                result = _block_until_ready(result)
                if result is None:
                    return False, "JIT returned None"
                return True, ""

            checks.append(_timed_check("jit_compiles", CheckCategory.JAX_JIT, check_jit))

        supports_vmap = self.sig.supports_vmap if self.sig else True
        if supports_vmap:
            def check_vmap() -> tuple[bool, str]:
                vmap_in_axes = self._resolve_vmap_in_axes()
                if vmap_in_axes is None:
                    return True, "Skipped (no vmap_in_axes provided)"
                if not (isinstance(vmap_in_axes, tuple) and len(vmap_in_axes) == 2):
                    return False, "vmap_in_axes must be a (state_axes, params_axes) tuple"

                state_axes, params_axes = vmap_in_axes
                state_axes_tree = self._expand_in_axes(state, state_axes)
                params_axes_tree = self._expand_in_axes(params, params_axes)
                batch_state = self._batch_tree(state, state_axes_tree)
                batch_params = self._batch_tree(params, params_axes_tree)

                vmapped = jax.vmap(pure_step, in_axes=(state_axes, params_axes))
                result = vmapped(batch_state, batch_params)
                result = _block_until_ready(result)
                if result is None:
                    return False, "vmap returned None"
                return True, ""

            checks.append(_timed_check("vmap_works", CheckCategory.JAX_VMAP, check_vmap))

        supports_grad = self.sig.supports_grad if self.sig else True
        if supports_grad and not skip_grad:
            def check_grad() -> tuple[bool, str]:
                diff_params: dict[str, Any] = {}
                for key, value in params.items():
                    if _is_array_like(value):
                        arr = np.asarray(value)
                        if np.issubdtype(arr.dtype, np.floating):
                            diff_params[key] = value

                if not diff_params:
                    return True, "Skipped (no floating params to differentiate)"

                def scalar_loss(p: dict[str, Any]) -> jnp.ndarray:
                    merged = {**params, **p}
                    result = pure_step(state, merged)
                    leaves = jax.tree_util.tree_leaves(result)
                    arrays = []
                    for leaf in leaves:
                        if not _is_array_like(leaf):
                            continue
                        arr = jnp.asarray(leaf)
                        if arr.dtype.kind in ("f", "c"):
                            arrays.append(arr)
                    if not arrays:
                        return jnp.array(0.0)
                    values = [jnp.sum(jnp.abs(a)) for a in arrays]
                    return jnp.sum(jnp.stack(values))

                grads = jax.grad(scalar_loss)(diff_params)
                grads = _block_until_ready(grads)
                is_finite, problems = _check_finite(grads)
                if not is_finite:
                    return False, f"Non-finite gradients: {problems[:3]}"

                return True, ""

            checks.append(_timed_check("grad_works", CheckCategory.JAX_GRAD, check_grad))

        return checks

    # ------------------------------------------------------------------
    # Numerical Stability Checks
    # ------------------------------------------------------------------

    def check_numerical_stability(
        self,
        state: Any,
        params: dict[str, Any],
    ) -> list[TestCheck]:
        """Check for numerical issues in method output."""
        checks: list[TestCheck] = []

        if not hasattr(self.method, "pure_step"):
            return checks

        def check_finite() -> tuple[bool, str]:
            result = self.method.pure_step(state, params)
            result = _block_until_ready(result)
            is_finite, problems = _check_finite(result)
            if not is_finite:
                return False, f"Non-finite values: {', '.join(problems[:3])}"
            return True, ""

        checks.append(_timed_check("output_finite", CheckCategory.NUMERICAL, check_finite))
        return checks

    # ------------------------------------------------------------------
    # Determinism Checks
    # ------------------------------------------------------------------

    def check_determinism(
        self,
        state: Any,
        params: dict[str, Any],
        n_runs: int = 3,
    ) -> list[TestCheck]:
        """Verify method produces identical results across multiple runs."""
        checks: list[TestCheck] = []

        if not hasattr(self.method, "pure_step"):
            return checks

        pure_step = self.method.pure_step

        def check_eager() -> tuple[bool, str]:
            results = []
            for _ in range(n_runs):
                result = pure_step(state, params)
                result = _block_until_ready(result)
                results.append(result)

            first = results[0]
            if all(_trees_equal(first, r) for r in results[1:]):
                return True, ""

            all_close = all(
                _trees_allclose(first, r, rtol=self._rtol, atol=self._atol)
                for r in results[1:]
            )
            if all_close:
                return True, f"Approximate match (rtol={self._rtol}, atol={self._atol})"

            return False, f"Results differ across {n_runs} eager runs"

        checks.append(
            _timed_check("deterministic_eager", CheckCategory.DETERMINISM, check_eager)
        )

        supports_jit = self.sig.supports_jit if self.sig else True
        if supports_jit:
            def check_jitted() -> tuple[bool, str]:
                jitted = jax.jit(pure_step)
                warm = jitted(state, params)
                _block_until_ready(warm)

                results = []
                for _ in range(n_runs):
                    result = jitted(state, params)
                    result = _block_until_ready(result)
                    results.append(result)

                first = results[0]
                if all(_trees_equal(first, r) for r in results[1:]):
                    return True, ""

                all_close = all(
                    _trees_allclose(first, r, rtol=self._rtol, atol=self._atol)
                    for r in results[1:]
                )
                if all_close:
                    return True, f"Approximate match (rtol={self._rtol}, atol={self._atol})"

                return False, f"Results differ across {n_runs} JIT runs"

            checks.append(
                _timed_check("deterministic_jit", CheckCategory.DETERMINISM, check_jitted)
            )

        return checks

    def check_compile_key_determinism(
        self,
        state: Any,
        params: dict[str, Any],
    ) -> list[TestCheck]:
        """Verify deterministic compile key (Law H)."""
        checks: list[TestCheck] = []

        if self.sig is None:
            return checks

        def check_key() -> tuple[bool, str]:
            static_params = {
                k: v for k, v in params.items() if k in self.sig.static_param_names
            }
            spec_a = specialization_from_signature_and_state(
                self.sig.fqn,
                static_params,
                self.sig.input_slots,
                state,
            )
            spec_b = specialization_from_signature_and_state(
                self.sig.fqn,
                static_params,
                self.sig.input_slots,
                state,
            )
            if spec_a.cache_key != spec_b.cache_key:
                return False, "Cache key is not deterministic"
            return True, ""

        checks.append(
            _timed_check("compile_key_deterministic", CheckCategory.DETERMINISM, check_key)
        )
        return checks

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_check(
        self,
        state: Any,
        params: dict[str, Any],
    ) -> bool:
        """Run minimal checks and return pass/fail boolean."""
        result = self.run_all(state, params, determinism_runs=2, skip_grad=True)
        return result.passed
