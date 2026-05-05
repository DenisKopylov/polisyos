> **Archived:** This document reflects plans as of 2026-03-25.
> See [current docs](../../explanation/index.md) for up-to-date information.

# Foundry (non-causal): Бескомпромиссный план доведения до absolute SOTA

> **Версия**: 1.0 | **Дата**: 2026-03-25
> **Scope**: весь foundry кроме `methods/catalog/causal/` (описан в CAUSAL_ENGINE_SOTA_PLAN.md)
> **Масштаб модуля**: ~393 файла, 16 catalog доменов, ~158 non-causal методов
> **Текущая оценка**: 6.5/10 | **Целевая**: 9.5/10
>
> Каждая фаза содержит: обоснование, конкретные файлы, функции, тесты, критерии приёмки.
> Фазы упорядочены по архитектурной зависимости: каждая следующая опирается на предыдущую.

---

## Содержание

1. [Текущее состояние: сильные стороны и разрывы](#1-текущее-состояние)
2. [Матрица зрелости](#2-матрица-зрелости)
3. [Phase 1 — Architectural Decoupling & Fail Semantics](#3-phase-1)
4. [Phase 2 — Constraint Engine v2](#4-phase-2)
5. [Phase 3 — Uncertainty Engine v2](#5-phase-3)
6. [Phase 4 — Calibration Hardening](#6-phase-4)
7. [Phase 5 — Evidence-Conditioned Method Selection](#7-phase-5)
8. [Phase 6 — Runtime Intelligence](#8-phase-6)
9. [Phase 7 — Composition & Execution Hardening](#9-phase-7)
10. [Phase 8 — Catalog Verification Density](#10-phase-8)
11. [Phase 9 — Purity & Operational Polish](#11-phase-9)
12. [Phase 10 — Benchmark Matrix & Golden Regressions](#12-phase-10)
13. [Зависимости между фазами](#13-зависимости)
14. [Критерии приёмки 9.5/10](#14-критерии-приёмки)
15. [Архитектурные инварианты](#15-инварианты)

---

## 1. Текущее состояние {#1-текущее-состояние}

### Что реально сильно

| Компонент | Файлы | Оценка | Обоснование |
|-----------|-------|--------|-------------|
| Trinity compile path | `compile/trinity_compiler.py`, `compile/_graph.py`, `compile/_lowering.py` | 9.0 | CAS-in/CAS-out, link/lower/conflict/cost/layout/ExecPlan — каноничный конвейер |
| Method ABI & Registry | `methods/base.py`, `methods/registry.py` | 9.0 | O(1) FQN lookup, thread-safe RLock, lifecycle, version resolution, type stubs |
| DAG composition | `methods/composer.py`, `methods/linker.py` | 8.5 | Deterministic topological sort, slot linking, type adaptation |
| Backend dispatch | `methods/backends/dispatch.py`, `backends/circuit_breaker.py` | 8.5 | Multi-runner (JAX/NumPy/Ray/Solver/Bayesian), circuit breaker, timing, reproducibility fingerprint |
| Data plane bindings | `data_plane/bindings.py` | 8.5 | Input rules, bound snapshot, auto-rules, lineage |
| Purity enforcement | `tools/quality/lint/lint_foundry.py` | 8.0 | AST-level lint, 4 policy tiers (standard/infra/mixed/no_jax) |
| Artifact chain | `methods/artifacts.py`, `methods/_artifacts_*.py` | 8.0 | store/chain/evidence, fingerprint, provenance |

### Критические разрывы (сводка)

| ID | Severity | Разрыв | Где | Почему критично |
|----|----------|--------|-----|-----------------|
| G-01 | P0 | Causal privilege — безусловный import | `catalog/__init__.py:5` | Ломает модульность, единственный домен без try/except |
| G-02 | P1 | Fail-open execution — silent skip | `_executor_graph.py:339-344` | Валидный результат с молча выпавшими методами |
| G-03 | P1 | Scalar-only constraints | `constraints_engine.py:40-41` | ValueError на любом vector/array state |
| G-04 | P1 | Analytical propagation dead code | `uncertainty/dispatcher.py:86-87` | preferred="analytical" → Monte Carlo |
| G-05 | P1 | Calibrator без Hessian | `calibration/calibrator.py` | Разрывает uncertainty pipeline |
| G-06 | P1 | Runtime step() placeholder | `runtime/__init__.py:141-143` | Compute kernel = no-op |
| G-07 | P1 | Selection без evidence loop | `methods/selection.py:354-400` | Static scoring, no VOI/runtime predictor |
| G-08 | P2 | Circuit breaker fallback hardcoded NumPy | `backends/dispatch.py` | Нет валидации совместимости |
| G-09 | P2 | Semantic validation opt-in | `methods/composer.py` | validate_semantics=False по умолчанию |
| G-10 | P2 | DAG node key без upstream context | `methods/composer.py:55-59` | Cache unsoundness |
| G-11 | P2 | No provenance tracking в executor | `_executor_graph.py` | Patch → method tracing невозможен |
| G-12 | P3 | RegistryAuditLog.export_jsonl NameError | `methods/registry.py:154-168` | Missing `from pathlib import Path` |
| G-13 | P3 | Compile timing 95/5 heuristic | `runtime/__init__.py:116-120` | Hardcode вместо measurement |
| G-14 | P3 | Purity exceptions вместо структуры пакета | `lint_foundry.py:69-94` | Transitional, не финальное |

---

## 2. Матрица зрелости {#2-матрица-зрелости}

| Подсистема | Сейчас | Цель | Дельта | Фаза |
|-----------|--------|------|--------|------|
| Catalog bootstrap / isolation | 6.0 | 9.5 | +3.5 | Phase 1 |
| Execution semantics (fail mode) | 5.0 | 9.5 | +4.5 | Phase 1 |
| Constraint engine | 5.5 | 9.0 | +3.5 | Phase 2 |
| Uncertainty engine | 5.5 | 9.5 | +4.0 | Phase 3 |
| Calibration subsystem | 6.5 | 9.0 | +2.5 | Phase 4 |
| Method selection / routing | 5.0 | 9.5 | +4.5 | Phase 5 |
| Runtime intelligence | 4.0 | 9.0 | +5.0 | Phase 6 |
| Composition & linking | 8.0 | 9.5 | +1.5 | Phase 7 |
| Non-causal catalog tests | 3.5 | 9.0 | +5.5 | Phase 8 |
| Purity & ops polish | 7.0 | 9.5 | +2.5 | Phase 9 |
| Benchmark matrix / golden | 2.0 | 9.0 | +7.0 | Phase 10 |
| **Средневзвешенная** | **6.5** | **9.5** | **+3.0** | |

---

## 3. Phase 1 — Architectural Decoupling & Fail Semantics {#3-phase-1}

> **Блокер**: без Phase 1 вся остальная чистота мнимая.
> **Закрывает**: G-01, G-02, G-11, G-12

### 1.1 — Causal isolation в catalog bootstrap

**Что:** обернуть causal import в try/except как все остальные 15 доменов.

**Файлы:**

- `src/polisyos/foundry/methods/catalog/__init__.py` (line 5):

```python
# BEFORE (единственный безусловный import):
from .causal import ensure_causal_methods_registered

# AFTER:
try:
    from .causal import ensure_causal_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_causal_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None
```

**Тесты:**
- `tests/unit/foundry/methods/catalog/test_catalog_isolation.py`:
  - `test_ensure_all_methods_registered_without_causal()` — mock causal import failure, assert remaining 15 domains load
  - `test_ensure_all_methods_registered_with_causal()` — baseline: all 16 domains load
  - `test_catalog_snapshot_without_causal()` — snapshot builder produces valid output when causal unavailable

**Критерий приёмки:** `uv run --extra methods-milestone2 pytest tests/unit/foundry/methods/catalog/test_catalog_isolation.py -q` проходит без `causal-core` extra.

### 1.2 — Fail-closed execution с typed FailureCard

**Что:** заменить silent skip на structured failure reporting с configurable strictness.

**Файлы:**

- `src/polisyos/foundry/_executor_models.py` — добавить:

```python
class FailureSeverity(str, Enum):
    """Severity classification for method execution failures."""
    FATAL = "fatal"            # Shape mismatch, contract violation
    RECOVERABLE = "recoverable"  # Missing optional dep, timeout
    DEGRADED = "degraded"      # Partial output, numerical instability

class FailureCard(BaseModel, frozen=True, extra="forbid"):
    """Structured failure report for a method node execution."""
    node_id: str
    method_fqn: str
    severity: FailureSeverity
    error_type: str              # Exception class name
    error_message: str
    traceback_hash: str          # For deduplication
    timestamp: float
    retry_eligible: bool
    suggested_fallback: str | None = None

class ExecutionStrictness(str, Enum):
    """Configurable strictness level for program graph execution."""
    FAIL_CLOSED = "fail_closed"  # Any FATAL → abort entire run
    DEGRADED = "degraded"        # FATAL → abort, RECOVERABLE → continue with flag
    RESEARCH = "research"        # Log all, continue (current behavior)
```

- `src/polisyos/foundry/_executor_graph.py` (lines 314-345) — заменить:

```python
# BEFORE:
except Exception as exc:
    logger.debug("Failed to execute method node '%s' (method=%s): %s", node_id, method_fqn, exc)
    skipped_nodes += 1

# AFTER:
except Exception as exc:
    severity = _classify_failure(exc)
    card = FailureCard(
        node_id=node_id,
        method_fqn=method_fqn,
        severity=severity,
        error_type=type(exc).__name__,
        error_message=str(exc),
        traceback_hash=_hash_traceback(exc),
        timestamp=time.time(),
        retry_eligible=severity == FailureSeverity.RECOVERABLE,
    )
    failure_cards.append(card)
    logger.warning("Method node '%s' failed: %s [%s]", node_id, exc, severity.value)
    if strictness == ExecutionStrictness.FAIL_CLOSED and severity == FailureSeverity.FATAL:
        raise MethodExecutionAbortError(card) from exc
    if strictness == ExecutionStrictness.DEGRADED and severity == FailureSeverity.FATAL:
        raise MethodExecutionAbortError(card) from exc
    skipped_nodes += 1
```

- Добавить классификатор:

```python
def _classify_failure(exc: Exception) -> FailureSeverity:
    if isinstance(exc, (TypeError, ValueError, ShapeMismatchError, ContractViolationError)):
        return FailureSeverity.FATAL
    if isinstance(exc, (ModuleNotFoundError, ImportError, TimeoutError)):
        return FailureSeverity.RECOVERABLE
    if isinstance(exc, (FloatingPointError, RuntimeWarning)):
        return FailureSeverity.DEGRADED
    return FailureSeverity.FATAL  # Default: fail-closed
```

- `execute_program_graph()` — добавить `failure_cards: list[FailureCard]` в возвращаемые artifacts и `is_degraded: bool` flag.

**Тесты:**
- `tests/unit/foundry/runtime/test_executor_fail_semantics.py`:
  - `test_fail_closed_aborts_on_fatal()` — TypeError → MethodExecutionAbortError
  - `test_fail_closed_continues_on_recoverable()` — ModuleNotFoundError → continue with card
  - `test_degraded_mode_records_cards()` — multiple failures → all recorded
  - `test_research_mode_preserves_current_behavior()` — silent skip (backward compat)
  - `test_failure_card_fields_populated()` — all fields non-None
  - `test_failure_card_in_execution_result()` — cards appear in result artifacts

**Критерий приёмки:** default strictness = FAIL_CLOSED; все существующие тесты проходят с явным `strictness=RESEARCH`.

### 1.3 — Provenance tracking в executor

**Что:** записывать method_fqn → patch mapping для audit trail.

**Файлы:**

- `src/polisyos/foundry/_executor_graph.py`:
  - Добавить `provenance: dict[str, list[str]]` (slot_id → [method_fqn, ...])
  - При каждом patch_records update: `provenance.setdefault(slot_id, []).append(method_fqn)`
  - Включить provenance в ExecuteArtifacts

**Тесты:**
- `tests/unit/foundry/runtime/test_executor_provenance.py`:
  - `test_provenance_records_method_per_patch()`
  - `test_provenance_multi_writer_same_slot()`

### 1.4 — Fix RegistryAuditLog.export_jsonl NameError

**Что:** добавить missing import.

**Файл:** `src/polisyos/foundry/methods/registry.py`

```python
# Line 154, method export_jsonl:
def export_jsonl(self, path: "Path") -> None:
    import json as _json
    from pathlib import Path  # <-- ADD THIS
    with self._lock:
        ...
```

**Тесты:**
- `tests/unit/foundry/methods/test_registry_audit.py`:
  - `test_export_jsonl_writes_valid_file(tmp_path)`
  - `test_export_jsonl_empty_log(tmp_path)`

**Критерий приёмки Phase 1:** все новые тесты + `pytest tests/unit/foundry/ -q --tb=short` green.

---

## 4. Phase 2 — Constraint Engine v2 {#4-phase-2}

> **Закрывает:** G-03
> **Зависимость:** Phase 1 (fail semantics для constraint violations)

### 2.1 — Vector/tensor constraint support

**Что:** расширить `check_constraints()` для поддержки array state с aggregation functions.

**Файлы:**

- `src/polisyos/foundry/constraints_engine.py` — расширить:

```python
class AggregationFunction(str, Enum):
    """Aggregation for vector/tensor slots before comparison."""
    SCALAR = "scalar"       # Текущее поведение: np.ndim == 0
    MIN = "min"
    MAX = "max"
    MEAN = "mean"
    MEDIAN = "median"
    SUM = "sum"
    ALL = "all"             # Все элементы удовлетворяют
    ANY = "any"             # Хотя бы один удовлетворяет
    QUANTILE = "quantile"   # С параметром q
    WEIGHTED_MEAN = "weighted_mean"  # С вектором весов
    COUNT_VIOLATING = "count_violating"  # Количество нарушающих элементов
```

- Заменить scalar-only check (lines 40-42):

```python
# BEFORE:
if np.ndim(state_value) != 0:
    raise ValueError("Constraint expects scalar slot value")
actual = Decimal(str(float(state_value)))

# AFTER:
aggregation = getattr(constraint, 'aggregation', AggregationFunction.SCALAR)
if np.ndim(state_value) == 0:
    actual = Decimal(str(float(state_value)))
else:
    actual = _aggregate(state_value, aggregation, constraint)
```

- Добавить `_aggregate()`:

```python
def _aggregate(
    state_value: np.ndarray,
    aggregation: AggregationFunction,
    constraint: LoweredConstraint,
) -> Decimal:
    if aggregation == AggregationFunction.SCALAR:
        raise ValueError(f"Constraint '{constraint.constraint_id}' expects scalar; got ndim={np.ndim(state_value)}")
    if aggregation == AggregationFunction.MIN:
        return Decimal(str(float(np.min(state_value))))
    if aggregation == AggregationFunction.MAX:
        return Decimal(str(float(np.max(state_value))))
    if aggregation == AggregationFunction.MEAN:
        return Decimal(str(float(np.mean(state_value))))
    if aggregation == AggregationFunction.MEDIAN:
        return Decimal(str(float(np.median(state_value))))
    if aggregation == AggregationFunction.SUM:
        return Decimal(str(float(np.sum(state_value))))
    if aggregation == AggregationFunction.QUANTILE:
        q = getattr(constraint, 'quantile_param', 0.5)
        return Decimal(str(float(np.quantile(state_value, q))))
    ...
```

### 2.2 — Element-wise constraint reporting

**Что:** для `ALL`/`ANY` aggregations, записывать per-element violation map в `ConstraintViolation.events`.

```python
if aggregation == AggregationFunction.ALL:
    element_violations = _check_elementwise(state_value, constraint.operator, expected)
    actual = Decimal("1") if all(not v for v in element_violations) else Decimal("0")
    # expected = Decimal("1") for "all elements satisfy"
    events.append({
        "event": "elementwise_check",
        "n_total": len(element_violations),
        "n_violating": sum(element_violations),
        "violating_indices": [i for i, v in enumerate(element_violations) if v][:100],  # cap at 100
    })
```

### 2.3 — Compositional constraints (stretch)

**Что:** поддержка constraint expressions: `slot_a / slot_b >= 0.5`, `slot_a + slot_b <= budget`.

**Файлы:**
- `src/polisyos/foundry/constraints_engine.py` — добавить `CompositeConstraint`:

```python
class CompositeConstraint(BaseModel, frozen=True):
    """Constraint involving multiple slots combined via arithmetic expression."""
    constraint_id: str
    expression: str  # e.g. "income_mean / gdp_per_capita"
    slot_refs: list[str]  # slots referenced in expression
    operator: str
    expected: str
    severity: str = "hard"
```

- Safe expression evaluator (no eval(), ast.literal_eval + operator whitelist).

**Тесты:**
- `tests/unit/foundry/validation/test_constraints_v2.py`:
  - `test_vector_constraint_mean()` — np.mean aggregation
  - `test_vector_constraint_all()` — elementwise check
  - `test_vector_constraint_quantile()` — percentile check
  - `test_scalar_constraint_backward_compat()` — existing behavior preserved
  - `test_composite_constraint_ratio()` — slot_a / slot_b
  - `test_composite_constraint_sum_budget()` — slot_a + slot_b <= budget
  - Property test: `test_aggregation_monotonicity()` — min ≤ mean ≤ max

**Критерий приёмки:** все 6 aggregation functions + compositional + backward compat; `_is_violated()` unchanged.

---

## 5. Phase 3 — Uncertainty Engine v2 {#5-phase-3}

> **Закрывает:** G-04, blueprint §4 (typed multi-axis uncertainty)
> **Зависимость:** Phase 1 (fail semantics), Phase 2 (vector constraints для uncertainty bounds)
> **Текущее:** 710 строк, 9 файлов, single-envelope propagation
> **Целевое:** typed multi-axis envelope, quasi-MC, adaptive stopping, sensitivity decomposition

### 3.1 — Wire analytical propagation

**Что:** исправить dead code в dispatcher.

**Файл:** `src/polisyos/foundry/uncertainty/dispatcher.py` (line 86-87):

```python
# BEFORE:
if preferred == "analytical":
    return PropagationMethod.MONTE_CARLO

# AFTER:
if preferred == "analytical":
    return PropagationMethod.ANALYTICAL
```

- Добавить в `propagate()` маршрутизацию ANALYTICAL → `analytical.propagate_linear_combination()`.
- Fallback: if ANALYTICAL fails (non-linear function), log warning + fallback to DELTA_METHOD → MONTE_CARLO.

**Тесты:**
- `tests/unit/foundry/uncertainty/test_dispatcher_routing.py`:
  - `test_analytical_preferred_routes_correctly()`
  - `test_analytical_fallback_to_delta_on_nonlinear()`
  - `test_analytical_output_matches_delta_for_linear()`

### 3.2 — Quasi-Monte Carlo (Sobol/Halton)

**Что:** добавить low-discrepancy sequences для variance reduction.

**Файл:** `src/polisyos/foundry/uncertainty/quasi_mc.py` (новый):

```python
class QuasiMCSampler:
    """Low-discrepancy sequence sampler for uncertainty propagation."""

    def __init__(self, method: str = "sobol", scramble: bool = True):
        self.method = method
        self.scramble = scramble

    def sample(self, n_samples: int, n_dims: int, seed: int = 42) -> np.ndarray:
        """Generate quasi-random samples in [0, 1]^n_dims."""
        if self.method == "sobol":
            from scipy.stats.qmc import Sobol
            sampler = Sobol(d=n_dims, scramble=self.scramble, seed=seed)
            return sampler.random(n_samples)
        if self.method == "halton":
            from scipy.stats.qmc import Halton
            sampler = Halton(d=n_dims, scramble=self.scramble, seed=seed)
            return sampler.random(n_samples)
        raise ValueError(f"Unknown QMC method: {self.method}")
```

- Интеграция в `monte_carlo.py`: новый параметр `sampling_method: str = "random"` в `PropagationConfig`. Значения: `"random"`, `"sobol"`, `"halton"`.
- При `sampling_method != "random"` → использовать `QuasiMCSampler` + inverse CDF transform для каждого distribution family.

### 3.3 — Adaptive stopping для Monte Carlo

**Что:** вместо фиксированного `mc_n_samples=1000`, остановка по convergence criterion.

**Файл:** `src/polisyos/foundry/uncertainty/monte_carlo.py`:

```python
class AdaptiveStoppingConfig(BaseModel, frozen=True):
    """Criteria for adaptive MC stopping."""
    enabled: bool = False
    min_samples: int = 200
    max_samples: int = 10_000
    ci_half_width_target: float = 0.01  # Relative to point estimate
    check_interval: int = 100  # Check convergence every N samples
```

- После каждого batch: проверить `(ci_hi - ci_lo) / abs(point) < ci_half_width_target`.
- Если converged для всех output metrics → early stop.

### 3.4 — Sensitivity decomposition

**Что:** при MC propagation, записывать Sobol first-order indices (какие inputs drive output uncertainty).

**Файл:** `src/polisyos/foundry/uncertainty/sensitivity.py` (новый):

```python
def compute_first_order_indices(
    samples: np.ndarray,   # (n_samples, n_inputs)
    outputs: np.ndarray,   # (n_samples, n_outputs)
    input_names: list[str],
    output_names: list[str],
) -> dict[str, dict[str, float]]:
    """Compute Sobol first-order sensitivity indices from MC samples.

    Returns: {output_name: {input_name: S_i}}
    """
```

- Включить indices в `PropagationResult.metadata["sensitivity_indices"]`.

### 3.5 — Tail-risk metrics

**Что:** добавить CVaR (Expected Shortfall), extreme quantiles в PropagationResult.

**Файл:** `src/polisyos/foundry/uncertainty/monte_carlo.py`:

```python
# В _build_result(), после percentile CI:
tail_metrics = {}
if valid_count > 100:
    tail_metrics["cvar_5pct"] = float(np.mean(valid_outputs[valid_outputs <= np.quantile(valid_outputs, 0.05)]))
    tail_metrics["quantile_1pct"] = float(np.quantile(valid_outputs, 0.01))
    tail_metrics["quantile_99pct"] = float(np.quantile(valid_outputs, 0.99))
```

### 3.6 — Multi-aggregation strategy

**Что:** расширить `aggregator.py` за пределы "widest".

```python
class AggregationStrategy(str, Enum):
    WIDEST = "widest"             # Текущее: min(lo), max(hi)
    PRECISION_WEIGHTED = "precision_weighted"  # Inverse-variance weighting
    BAYESIAN_COMBINATION = "bayesian_combination"  # Posterior combination
```

- `precision_weighted`: point = Σ(point_i / var_i) / Σ(1/var_i), var = 1 / Σ(1/var_i).
- `bayesian_combination`: Gaussian conjugate update.

**Тесты:**
- `tests/unit/foundry/uncertainty/test_analytical_routing.py`
- `tests/unit/foundry/uncertainty/test_quasi_mc.py`:
  - `test_sobol_samples_uniformity()` — Kolmogorov-Smirnov test
  - `test_sobol_variance_reduction()` — QMC CI width < random MC CI width for same n_samples
  - `test_halton_dimensionality()`
- `tests/unit/foundry/uncertainty/test_adaptive_stopping.py`:
  - `test_adaptive_stops_early_on_convergence()`
  - `test_adaptive_respects_min_samples()`
  - `test_adaptive_respects_max_samples()`
- `tests/unit/foundry/uncertainty/test_sensitivity_indices.py`:
  - `test_linear_model_sobol_indices()` — known analytical solution
  - `test_independent_inputs_sum_to_one()`
- `tests/unit/foundry/uncertainty/test_tail_risk.py`:
  - `test_cvar_less_than_quantile()` — CVaR ≤ 5th percentile
- `tests/unit/foundry/uncertainty/test_aggregation_strategies.py`:
  - `test_precision_weighted_narrows_ci()`
  - `test_widest_backward_compat()`
  - Property test: `test_aggregated_ci_contains_all_points()`

**Критерий приёмки Phase 3:** uncertainty engine ≥1500 строк, 6+ strategies, все тесты green, sensitivity indices для linear model match analytical.

---

## 6. Phase 4 — Calibration Hardening {#6-phase-4}

> **Закрывает:** G-05
> **Зависимость:** Phase 3 (uncertainty engine для Hessian → envelope)

### 4.1 — Hessian computation в Calibrator

**Что:** после оптимизации, вычислить Hessian → Fisher information → parameter uncertainty.

**Файл:** `src/polisyos/foundry/calibration/calibrator.py`:

```python
def _compute_hessian(
    self,
    loss_fn: Callable,
    optimal_params: jnp.ndarray,
) -> HessianResult:
    """Compute Hessian of loss at optimum for uncertainty estimation.

    Strategy:
    1. Try JAX hessian (exact, requires 2nd-order differentiability)
    2. Fallback: finite-difference Hessian
    3. Eigenvalue repair: clip negative eigenvalues to jitter floor
    """
    try:
        H = jax.hessian(loss_fn)(optimal_params)
    except Exception:
        H = _finite_difference_hessian(loss_fn, optimal_params, eps=1e-5)

    # Symmetrize + eigenvalue repair
    H = 0.5 * (H + H.T)
    eigvals, eigvecs = jnp.linalg.eigh(H)
    eigvals = jnp.maximum(eigvals, 1e-8)
    H_repaired = eigvecs @ jnp.diag(eigvals) @ eigvecs.T

    # Covariance = H^{-1} (Fisher information inverse)
    cov = jnp.linalg.inv(H_repaired)
    std = jnp.sqrt(jnp.diag(cov))

    return HessianResult(
        hessian=H_repaired,
        covariance=cov,
        std=std,
        eigenvalues=eigvals,
        condition_number=float(eigvals[-1] / eigvals[0]),
        n_repaired=int(jnp.sum(eigvals < 1e-8)),
    )
```

- Интегрировать в `Calibrator.run()`: после optimization loop, вызвать `_compute_hessian()`, записать в `CalibrationReport.uncertainties`.

### 4.2 — Multi-start optimization

**Что:** запуск из N начальных точек, выбор лучшего.

```python
class MultiStartConfig(BaseModel, frozen=True):
    n_starts: int = 5
    perturbation_scale: float = 0.1
    selection: str = "best_loss"  # или "best_identifiability"
```

- Каждый start: perturb initial params, run optimization, record (loss, params, Hessian).
- Выбор: минимальный loss + stable Hessian (condition number < threshold).

### 4.3 — Identifiability diagnostics

**Что:** проверить, что calibrated parameters идентифицируемы.

```python
def diagnose_identifiability(hessian_result: HessianResult, param_names: list[str]) -> IdentifiabilityReport:
    """Check parameter identifiability via Hessian eigenstructure.

    Returns per-parameter report:
    - identified: eigenvalue > threshold
    - sloppy: eigenvalue in (jitter, threshold) — parameter poorly constrained
    - non_identified: eigenvalue ≈ jitter — parameter not identifiable from data
    """
```

- Thresholds: `identified > 1e-3`, `sloppy ∈ (1e-8, 1e-3)`, `non_identified ≤ 1e-8`.

### 4.4 — Bijector library расширение

**Файл:** `src/polisyos/foundry/calibration/bijectors.py`:

Добавить: `LogBijector`, `LogitBijector`, `SoftplusBijector`, `AffineBijector`, `ChainBijector`, `InverseBijector`.

Каждый: `forward(x)`, `inverse(y)`, `log_det_jacobian(x)`.

**Тесты:**
- `tests/unit/foundry/calibration/test_hessian.py`:
  - `test_hessian_quadratic_function()` — known answer: H = 2I
  - `test_hessian_eigenvalue_repair()`
  - `test_finite_difference_matches_exact()`
- `tests/unit/foundry/calibration/test_multi_start.py`:
  - `test_multi_start_finds_global_minimum()`
  - `test_multi_start_identifiability_selection()`
- `tests/unit/foundry/calibration/test_identifiability.py`:
  - `test_identified_parameter()`
  - `test_sloppy_parameter_flagged()`
  - `test_non_identified_parameter_flagged()`
- `tests/unit/foundry/calibration/test_bijectors.py`:
  - `test_log_roundtrip()`
  - `test_logit_roundtrip()`
  - `test_chain_bijector_composition()`
  - Property test: `test_inverse_is_left_inverse()`

**Критерий приёмки Phase 4:** `Calibrator.run()` produces `CalibrationReport` с non-None uncertainties; identifiability report для каждого параметра; uncertainty_adapter → UncertaintyEnvelope pipeline end-to-end.

---

## 7. Phase 5 — Evidence-Conditioned Method Selection {#7-phase-5}

> **Закрывает:** G-07, blueprint §6 (VOI/risk/runtime-driven routing)
> **Зависимость:** Phase 4 (calibration priors), Phase 3 (uncertainty for VOI)

### 5.1 — Execution history store

**Что:** записывать outcome каждого method dispatch для learning.

**Файл:** `src/polisyos/foundry/methods/selection_history.py` (новый):

```python
class MethodExecutionRecord(BaseModel, frozen=True):
    """Single method execution outcome for selection learning."""
    method_fqn: str
    timestamp: float
    latency_ms: float
    success: bool
    output_quality: float | None = None  # Domain-specific quality metric
    data_characteristics: dict[str, Any] = {}  # n_obs, n_features, etc.
    failure_type: str | None = None

class SelectionHistoryStore:
    """Thread-safe store for method execution history."""

    def record(self, record: MethodExecutionRecord) -> None: ...
    def success_rate(self, method_fqn: str, window_hours: float = 168) -> float: ...
    def mean_latency_ms(self, method_fqn: str) -> float: ...
    def quality_quantiles(self, method_fqn: str) -> tuple[float, float, float]: ...  # p25, p50, p75
```

### 5.2 — Runtime predictor

**Что:** предсказать latency метода по data characteristics.

```python
class RuntimePredictor:
    """Predict method execution time from data characteristics.

    Uses simple linear model: log(latency) ~ log(n_obs) + log(n_features) + backend_factor.
    Fitted from SelectionHistoryStore.
    """

    def predict_ms(self, method_fqn: str, n_obs: int, n_features: int = 1) -> float: ...
    def fit(self, history: SelectionHistoryStore) -> None: ...
```

### 5.3 — Evidence-conditioned scorer

**Что:** заменить static scoring на evidence-aware.

**Файл:** `src/polisyos/foundry/methods/selection.py` — расширить `_score_entry()`:

```python
def _score_entry_v2(
    entry: MethodCatalogEntry,
    criteria: MethodSelectionCriteria,
    history: SelectionHistoryStore | None = None,
    runtime_predictor: RuntimePredictor | None = None,
    runtime_budget_ms: float | None = None,
) -> float:
    # Base score (existing logic)
    score = _score_entry(entry, criteria)

    if history is not None:
        # Evidence adjustments
        sr = history.success_rate(entry.fqn)
        score += 30.0 * sr  # Up to +30 for 100% success rate
        score -= 15.0 * (1.0 - sr)  # Penalty for failures

        quality = history.quality_quantiles(entry.fqn)
        if quality is not None:
            score += 20.0 * quality[1]  # Median quality bonus

    if runtime_predictor is not None and runtime_budget_ms is not None:
        predicted_ms = runtime_predictor.predict_ms(entry.fqn, criteria.n_obs or 1000)
        if predicted_ms > runtime_budget_ms:
            score -= 50.0  # Heavy penalty for budget violation
        else:
            # Bonus for efficiency: faster relative to budget = better
            score += 10.0 * (1.0 - predicted_ms / runtime_budget_ms)

    return score
```

### 5.4 — VOI-based scheduling (stretch)

**Что:** Value of Information для решения "стоит ли запускать более дорогой метод?"

```python
def compute_voi(
    current_uncertainty: UncertaintyEnvelope,
    method_expected_reduction: float,  # From history
    method_cost_ms: float,
    decision_value: float,  # Stakes of the decision
) -> float:
    """Expected net benefit of running a method.

    VOI = P(changes decision) * decision_value - method_cost
    """
    ci_width = current_uncertainty.confidence_interval[1] - current_uncertainty.confidence_interval[0]
    p_changes = min(1.0, method_expected_reduction / ci_width) if ci_width > 0 else 0.0
    return p_changes * decision_value - method_cost_ms * COST_PER_MS
```

**Тесты:**
- `tests/unit/foundry/methods/test_selection_v2.py`:
  - `test_evidence_scorer_prefers_high_success_rate()`
  - `test_evidence_scorer_penalizes_budget_violation()`
  - `test_runtime_predictor_linear_scaling()`
  - `test_voi_positive_for_high_stakes()`
  - `test_voi_negative_for_low_stakes_expensive_method()`
  - `test_backward_compat_without_history()` — v2 scorer = v1 when history=None

**Критерий приёмки Phase 5:** method selection incorporates execution history; runtime predictor calibrated on ≥100 historical records; VOI-based scheduling доступен как opt-in.

---

## 8. Phase 6 — Runtime Intelligence {#8-phase-6}

> **Закрывает:** G-06, G-13
> **Зависимость:** Phase 1 (fail semantics)

### 6.1 — Specialize step() с mechanism dispatch

**Что:** заменить no-op placeholder на реальный compute kernel.

**Файл:** `src/polisyos/foundry/runtime/__init__.py` (lines 141-143):

```python
# BEFORE:
def step(state, controls, root_key, t, static_bundle=None):
    return state, {}  # placeholder

# AFTER:
def step(state, controls, root_key, t, static_bundle=None):
    """Pure JAX step: apply all mechanism nodes from static_bundle."""
    if static_bundle is None:
        return state, {"skipped": True}

    trace = {}
    new_state = state
    for node in static_bundle.nodes:
        key, root_key = jax.random.split(root_key)
        node_result = _apply_node_pure(new_state, controls, node, key, t)
        new_state = _merge_state(new_state, node_result)
        trace[node.node_id] = node_result

    return new_state, trace
```

### 6.2 — Precise compile/execute timing

**Что:** измерять, а не предполагать 95/5 split.

**Файл:** `src/polisyos/foundry/runtime/__init__.py` (lines 116-120):

```python
# BEFORE:
if ctx.is_warmup:
    ctx.compile_seconds = ctx.total_seconds * 0.95
    ctx.execute_seconds = ctx.total_seconds * 0.05

# AFTER:
if ctx.is_warmup:
    # Measure actual compile time via JAX tracing callback
    compile_start = time.perf_counter()
    _ = jax.jit(lambda: None).lower().compile()  # Force XLA compile
    compile_overhead = time.perf_counter() - compile_start
    ctx.compile_seconds = min(ctx.total_seconds * 0.99, ctx.total_seconds - compile_overhead)
    ctx.execute_seconds = ctx.total_seconds - ctx.compile_seconds
```

Альтернативно: использовать `jax.profiler` callbacks для precise measurement.

### 6.3 — NaN guard integration в step()

**Что:** при `profile == STRICT`, проверять NaN после каждого node в step().

```python
if nan_guard_enabled:
    nan_check = _check_nan(new_state)
    if nan_check.has_nan:
        trace[node.node_id]["nan_detected"] = nan_check
        if strictness == ExecutionStrictness.FAIL_CLOSED:
            raise NaNDetectedError(node.node_id, nan_check)
```

**Тесты:**
- `tests/unit/foundry/runtime/test_step_specialization.py`:
  - `test_step_with_static_bundle_applies_nodes()`
  - `test_step_without_bundle_returns_identity()`
  - `test_step_nan_guard_strict_raises()`
  - `test_step_nan_guard_research_logs()`
- `tests/unit/foundry/runtime/test_timing.py`:
  - `test_compile_execute_timing_separation()`
  - `test_warmup_vs_cached_timing()`

**Критерий приёмки Phase 6:** `step()` не no-op; timing measurement ≤10% error vs actual; NaN guard configurable.

---

## 9. Phase 7 — Composition & Execution Hardening {#9-phase-7}

> **Закрывает:** G-08, G-09, G-10
> **Зависимость:** Phase 1 (fail semantics), Phase 5 (selection for fallback)

### 7.1 — Pluggable fallback strategy в dispatch

**Файл:** `src/polisyos/foundry/methods/backends/dispatch.py`:

```python
class FallbackStrategy(Protocol):
    """Strategy for choosing fallback backend when primary fails."""
    def select_fallback(
        self,
        method_class: type,
        signature: MethodSignature,
        failed_backend: ComputeBackend,
    ) -> ComputeBackend | None: ...

class SignatureAwareFallback:
    """Default fallback: check signature compatibility before falling back."""

    FALLBACK_ORDER = [ComputeBackend.NUMPY, ComputeBackend.SCIPY]

    def select_fallback(self, method_class, signature, failed_backend):
        for backend in self.FALLBACK_ORDER:
            if backend == failed_backend:
                continue
            if self._is_compatible(signature, backend):
                return backend
        return None

    def _is_compatible(self, signature, backend):
        # JAX-specific features (vmap, grad) incompatible with NumPy
        if backend == ComputeBackend.NUMPY and signature.requires_autodiff:
            return False
        return True
```

- Заменить hardcoded NumPy fallback на `FallbackStrategy.select_fallback()`.
- Inject strategy через `MethodDispatcher.__init__()`.

### 7.2 — Semantic validation default-on

**Файл:** `src/polisyos/foundry/methods/composer.py`:

```python
# BEFORE:
def build(self, ..., validate_semantics: bool = False) -> CompiledMethodChain:

# AFTER:
def build(self, ..., validate_semantics: bool = True) -> CompiledMethodChain:
```

- Добавить `SemanticValidationLevel` enum: `STRICT` (error), `WARN` (warning), `OFF`.
- Default: `WARN` (not breaking, but visible).

### 7.3 — DAG node key с upstream context

**Файл:** `src/polisyos/foundry/methods/composer.py` (lines 55-59):

```python
# BEFORE:
def _stable_params_digest(self) -> str:
    return _hash_dict(self.static_params)

# AFTER:
def _stable_params_digest(self) -> str:
    upstream_keys = sorted(self._upstream_digests)  # From incoming edges
    combined = {
        "static_params": self.static_params,
        "upstream_digests": upstream_keys,
        "backend": self.backend.value if self.backend else None,
    }
    return _hash_dict(combined)
```

### 7.4 — Requirements edges validation

**Файл:** `src/polisyos/foundry/methods/composer.py`:

```python
# BEFORE (line ~476-479): missing requirement → warning
# AFTER: missing requirement → error in STRICT, warning in WARN, silent in OFF
if validate_semantics_level == SemanticValidationLevel.STRICT:
    raise MissingRequirementError(method_fqn, required_fqn)
```

**Тесты:**
- `tests/unit/foundry/methods/test_dispatch_fallback.py`:
  - `test_fallback_skips_incompatible_backend()`
  - `test_fallback_selects_compatible_backend()`
  - `test_fallback_returns_none_when_no_option()`
- `tests/unit/foundry/methods/test_composer_hardening.py`:
  - `test_semantic_validation_default_on()`
  - `test_dag_node_key_includes_upstream()`
  - `test_missing_requirement_strict_raises()`

**Критерий приёмки Phase 7:** circuit breaker fallback validated; semantic validation enabled; cache keys sound.

---

## 10. Phase 8 — Catalog Verification Density {#10-phase-8}

> **Закрывает:** test coverage gaps
> **Зависимость:** Phase 1-7 (infrastructure tests depend on new APIs)
> **Стратегия:** domain-by-domain, prioritized by gap size

### 8.1 — Infrastructure test suite

**Новые тест-файлы (приоритет 1):**

| Файл | Covers | Min tests |
|------|--------|-----------|
| `tests/unit/foundry/compile/test_trinity_compiler.py` | Link → lower → graph → plan | 8 |
| `tests/unit/foundry/compile/test_graph.py` | build_program_graph, exec_order | 5 |
| `tests/unit/foundry/compile/test_lowering.py` | lower_trinity, coverage tracking | 5 |
| `tests/unit/foundry/calibration/test_calibrator.py` | Calibrator.run() e2e | 6 |
| `tests/unit/foundry/calibration/test_pure_executor.py` | compile_program, run_pure_scan | 5 |
| `tests/unit/foundry/calibration/test_loss.py` | loss_components (huber, MSE) | 4 |
| `tests/unit/foundry/calibration/test_preflight.py` | Preflight checks | 4 |
| `tests/unit/foundry/uncertainty/test_dispatcher.py` | Strategy routing | 5 |
| `tests/unit/foundry/uncertainty/test_delta.py` | Jacobian propagation | 5 |
| `tests/unit/foundry/uncertainty/test_monte_carlo.py` | Sampling, batch, heuristic fallback | 6 |
| `tests/unit/foundry/uncertainty/test_covariance.py` | build_covariance_matrix, repair | 4 |
| `tests/unit/foundry/uncertainty/test_aggregator.py` | Widest, precision_weighted | 4 |
| `tests/unit/foundry/contracts/test_fidelity.py` | FidelityLevel contracts | 3 |
| `tests/unit/foundry/data_plane/test_bindings.py` | load_input_bindings | 4 |
| `tests/unit/foundry/runtime/test_nan_guard.py` | NaN detection | 4 |
| `tests/unit/foundry/runtime/test_fingerprint.py` | Library version capture | 3 |
| **Итого** | | **75 тестов** |

### 8.2 — Domain test gap closure (приоритет 2)

**Domains с 0% покрытием — полный coverage:**

| Домен | Модулей | Тесты нужны | Файлы |
|-------|---------|-------------|-------|
| Forecasting | 4 | 8 | `test_univariate.py`, `test_advanced.py` |
| Mechanism | 3 | 6 | `test_runtime.py` |
| Validation | 4 | 8 | `test_diagnostics.py`, `test_scoring.py` |

**Domains <30% — targeted coverage:**

| Домен | Текущее | Тесты нужны | Приоритетные модули |
|-------|---------|-------------|-------------------|
| Distributional (14%) | 1 | 8 | `mobility.py`, `polarization.py`, `poverty_advanced.py` |
| Survey (17%) | 1 | 8 | `design.py`, `estimation.py`, `imputation.py`, `weighting.py` |
| Sensitivity (20%) | 1 | 6 | `sobol.py`, `screening.py`, `specification.py` |
| Network (25%) | 1 | 5 | `analysis.py` |
| Simulation (25%) | 1 | 5 | `dynamics.py`, `inference.py` |

### 8.3 — Property tests для каждого домена

**Что:** hypothesis-based property tests для ключевых инвариантов.

```python
# Example: distributional methods
@given(income=arrays(np.float64, shape=(100,), elements=st.floats(100, 100000)))
def test_gini_bounded_zero_one(income):
    """Gini coefficient must be in [0, 1]."""
    result = gini_method.run(income=income)
    assert 0.0 <= result["gini"] <= 1.0

@given(data=arrays(np.float64, shape=(50,), elements=st.floats(0, 1)))
def test_poverty_rate_monotone_in_threshold(data):
    """Higher threshold → higher poverty rate."""
    low = poverty_method.run(income=data, threshold=0.3)
    high = poverty_method.run(income=data, threshold=0.7)
    assert low["headcount"] <= high["headcount"]
```

- Минимум 2 property tests per domain (30 total).

### 8.4 — Agent sim coverage (приоритет 3)

**39 модулей, 1 тест. Минимум:**

| Файл | Tests |
|------|-------|
| `tests/unit/foundry/agent_sim/test_executor.py` | 4 |
| `tests/unit/foundry/agent_sim/test_mechanisms.py` | 4 |
| `tests/unit/foundry/agent_sim/test_distributions.py` | 4 |
| `tests/unit/foundry/agent_sim/test_training.py` | 3 |
| `tests/unit/foundry/agent_sim/test_evolution.py` | 3 |
| `tests/unit/foundry/agent_sim/test_population.py` | 3 |

**Критерий приёмки Phase 8:** ≥75 infrastructure tests + ≥45 domain tests + ≥30 property tests + ≥21 agent_sim tests = **≥171 новых тестов**; overall non-causal test count ≥ 250.

---

## 11. Phase 9 — Purity & Operational Polish {#11-phase-9}

> **Закрывает:** G-14
> **Зависимость:** Phase 1-8

### 9.1 — Структурная изоляция вместо policy exceptions

**Что:** перенести purity exceptions из lint rules в package structure.

**Текущее состояние** (`lint_foundry.py:69-94`): `runtime/`, `agent_sim/`, `plugins/` исключены из purity policy.

**Целевое:**

```
foundry/
├── pure/                    # ← Строгая purity: standard policy
│   ├── compile/
│   ├── constraints_engine.py
│   ├── cost_model.py
│   ├── merge_engine.py
│   ├── methods/base.py, registry.py, composer.py, ...
│   └── uncertainty/
├── mixed/                   # ← Mixed policy: scientific Python allowed
│   ├── methods/catalog/     # Method implementations
│   └── methods/backends/    # Runner implementations
└── infra/                   # ← No restrictions
    ├── runtime/
    ├── agent_sim/
    ├── plugins/
    └── calibration/
```

**Реализация:** lint rules по directory membership, не по exception list.

**Примечание:** это рефакторинг, НЕ блокер. Можно отложить если directory restructure слишком дорог — достаточно задокументировать границы в lint config.

### 9.2 — Data-plane lint расширение

**Файл:** `tools/quality/lint/lint_foundry_data_plane.py`:

Добавить проверки:
- Все slots referenced в constraints_engine имеют state_path в SlotRegistry
- Все mechanism specs в `foundry/mechanisms/` зарегистрированы в foundry.registry
- Input bindings не ссылаются на несуществующие slots

### 9.3 — Hot reload safety

**Файл:** `src/polisyos/foundry/methods/hot_reload.py`:

Проверить:
- Thread safety при hot reload method (RLock на registry)
- Cache invalidation (CompilationCache.reset() при method update)
- Version bump при reload (prevent stale cache hits)

**Тесты:**
- `tests/unit/foundry/hygiene/test_purity_boundaries.py`:
  - `test_pure_zone_no_banned_imports()`
  - `test_mixed_zone_allows_scipy()`
  - `test_infra_zone_no_restrictions()`
- `tests/unit/foundry/methods/test_hot_reload_safety.py`:
  - `test_reload_invalidates_cache()`
  - `test_reload_thread_safe()`

**Критерий приёмки Phase 9:** lint rules structural, not exception-based; data-plane lint catches cross-reference errors; hot reload thread-safe.

---

## 12. Phase 10 — Benchmark Matrix & Golden Regressions {#12-phase-10}

> **Зависимость:** Phase 8 (tests exist), Phase 5 (selection history)

### 10.1 — Golden regression infrastructure

**Что:** заполнить пустой `methods/testing/golden.py` реальными golden outputs.

**Файлы:**

- `src/polisyos/foundry/methods/testing/golden.py`:

```python
class GoldenTestCase(BaseModel, frozen=True):
    """Known-answer test for method regression detection."""
    method_fqn: str
    input_data: dict[str, Any]
    expected_output: dict[str, Any]
    tolerance: float = 1e-6
    backend: ComputeBackend = ComputeBackend.NUMPY
    seed: int = 42
    description: str = ""

class GoldenRegistry:
    """Registry of golden test cases, loaded from YAML."""
    def load(self, path: Path) -> list[GoldenTestCase]: ...
    def verify_all(self, registry: MethodRegistry) -> GoldenReport: ...
```

- `tests/unit/foundry/golden/` — YAML golden files per domain:

```yaml
# tests/unit/foundry/golden/econometrics.yaml
- method_fqn: "econometrics.panel.fixed_effects@1.0"
  input_data:
    y: [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
    X: [[1.0], [2.0], [3.0]]
    entity_ids: [0, 0, 1]
  expected_output:
    coefficients: [2.0]
    r_squared: 0.95
  tolerance: 0.05
```

### 10.2 — Domain benchmark matrix

**Что:** per-domain accuracy benchmarks с known datasets.

**Файл:** `benchmarks/foundry/` (новый каталог):

```
benchmarks/foundry/
├── conftest.py
├── test_econometrics_accuracy.py     # Wage equation, Mincer, panel data
├── test_optimization_convergence.py  # Rosenbrock, LP duality gap
├── test_bayesian_coverage.py         # Posterior calibration check
├── test_distributional_consistency.py # Gini invariants, Lorenz ordering
├── test_spatial_moran.py             # Known Moran's I for lattice data
├── test_survey_design_effect.py      # Design effect for known sampling schemes
└── test_ml_generalization.py         # Cross-validation on UCI datasets
```

Каждый benchmark:
- Known dataset (synthetic or canonical)
- Expected answer (analytical or reference implementation)
- Tolerance (domain-appropriate)
- Runs as pytest with `--benchmark` marker

### 10.3 — Cross-backend consistency tests

**Что:** один и тот же method, NumPy vs JAX vs Ray → same output (within tolerance).

```python
@pytest.mark.parametrize("backend", [ComputeBackend.NUMPY, ComputeBackend.JAX])
def test_ols_cross_backend_consistency(backend):
    result = dispatch(OLSEstimator, data, backend=backend)
    np.testing.assert_allclose(result["coefficients"], expected, rtol=1e-5)
```

### 10.4 — Method selection A/B benchmark

**Что:** benchmark для method selection quality.

```python
def test_selection_accuracy_on_known_problems():
    """For each problem type, verify that top-ranked method is the correct choice."""
    scenarios = [
        {"data": panel_data, "expected_best": "econometrics.panel.fixed_effects"},
        {"data": cross_section, "expected_best": "econometrics.ols"},
        {"data": time_series, "expected_best": "forecasting.arima"},
    ]
    for scenario in scenarios:
        ranked = rank_method_catalog_entries(catalog, criteria_from(scenario["data"]))
        assert ranked[0].fqn == scenario["expected_best"]
```

**Тесты:**
- Минимум 5 golden cases per domain × 10 domains = **50 golden tests**
- 7 benchmark files × ~5 tests each = **35 benchmark tests**
- 10 cross-backend consistency tests

**Критерий приёмки Phase 10:** golden regression suite ≥50 tests, all green; benchmark matrix covers all non-causal domains; cross-backend consistency for all NumPy+JAX methods.

---

## 13. Зависимости между фазами {#13-зависимости}

```
Phase 1 (Decoupling & Fail Semantics)
  │
  ├──► Phase 2 (Constraints v2)
  │       │
  │       └──► Phase 3 (Uncertainty v2)
  │               │
  │               └──► Phase 4 (Calibration)
  │                       │
  │                       └──► Phase 5 (Selection)
  │
  ├──► Phase 6 (Runtime)
  │
  ├──► Phase 7 (Composition Hardening)
  │
  └──► Phase 8 (Test Coverage) ──► Phase 10 (Benchmarks)

Phase 9 (Purity) ← depends on Phase 1-8 being stable
```

**Параллелизация:**
- Phase 2 + Phase 6 + Phase 7 можно делать параллельно (после Phase 1)
- Phase 8 можно начинать параллельно с Phase 3-7 (для уже стабильных подсистем)
- Phase 9 + Phase 10 — финальные, последовательно

---

## 14. Критерии приёмки 9.5/10 {#14-критерии-приёмки}

### Обязательные (hard gates)

| Критерий | Метрика | Порог |
|----------|---------|-------|
| Catalog isolation | Все 16 доменов — try/except | 16/16 |
| Fail semantics | Default = FAIL_CLOSED, typed FailureCard | 100% coverage |
| Constraint engine | Vector + compositional support | ≥10 aggregation functions |
| Uncertainty engine | ≥4 propagation strategies | Delta + MC + QMC + Analytical |
| Calibration | Hessian + identifiability | End-to-end pipeline |
| Method selection | Evidence-conditioned scoring | History + runtime predictor |
| Runtime step() | Specialized compute kernel | Not no-op |
| Test count (non-causal) | Total tests | ≥400 |
| Golden regressions | Per-domain golden suites | ≥50 cases |
| Cross-backend consistency | NumPy vs JAX agreement | ≤1e-5 rtol |
| Benchmark matrix | Domain accuracy benchmarks | ≥7 domains covered |
| No NameError/ImportError | Static analysis clean | 0 issues |

### Рекомендуемые (soft targets)

| Критерий | Метрика | Порог |
|----------|---------|-------|
| Property tests | hypothesis-based | ≥30 |
| VOI scheduling | Compute-economic routing | Available opt-in |
| Quasi-MC | Sobol/Halton variance reduction | Measurable improvement |
| Multi-start calibration | Global optimization | ≥3 starts default |
| Sensitivity decomposition | Sobol indices in PropagationResult | For MC runs |
| Purity structural | Lint by directory, not exceptions | 0 exception entries |
| Agent sim tests | Module coverage | ≥50% |

---

## 15. Архитектурные инварианты {#15-инварианты}

Эти инварианты должны сохраняться на протяжении всех фаз:

1. **CAS-in/CAS-out**: каждый compile/execute → artifact refs в FileSystemCAS. Никаких side-channel outputs.

2. **Pure functional core**: `foundry/pure/` zone — no I/O, no randomness без explicit key, no global mutable state.

3. **Protocol-driven**: все абстракции — `typing.Protocol`. Никаких abstract base classes с implementation.

4. **Thread-safe singletons**: Registry, Dispatcher, CompilationCache — RLock protected.

5. **Backward compatibility**: все v1 APIs остаются callable. Новые APIs — additive. Breaking changes → `compat.py` migration.

6. **Deterministic builds**: `_stable_digest()` для cache keys, не `__hash__`. Reproducible across processes.

7. **Typed uncertainty**: каждый CI claim — `UncertaintyEnvelope` с `IntervalSemantics`. Никаких untyped floats как confidence bounds.

8. **Fail-closed default**: execution strictness = FAIL_CLOSED. Research mode — explicit opt-in.

9. **No causal privilege**: все 16 catalog доменов — equal citizens. Никаких unconditional imports.

10. **Evidence over heuristics**: method selection informed by execution history. Static weights — fallback, not primary.

---

> **Общий объём работы:** ~3500-4500 LOC новый код, ~500 LOC рефакторинг, ~400+ новых тестов.
> **Порядок приоритетов:** Phase 1 → Phase 2-3 → Phase 4-7 → Phase 8-10.
