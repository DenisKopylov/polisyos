# Uncertainty (`polisyos.foundry.uncertainty`)

`uncertainty` — подсистема propagation неопределенности для метрик Foundry-симуляций.

Актуально по коду на 2026-02-17.

## Роль в системе

Подсистема принимает uncertainty envelopes входных параметров и оценивает, как неопределенность распространяется на выходные метрики симуляции.

Типичный путь использования: `scientist` узел `propagate_uncertainty` после `run_simulation`/`calibration`.

## Архитектурный поток

```text
input envelopes + nominal params + simulation_fn + output_metric_ids
        |
        v
PropagationDispatcher
   |- DeltaMethodPropagator (jax jacobian)
   \- MonteCarloPropagator (sampling)
        |
        v
PropagationResult[] (metric_id -> UncertaintyEnvelope)
        |
        v
optional aggregate_envelopes(...)
```

## Ключевые модули

- `config.py`
  - `PropagationConfig`: confidence level, delta/mc параметры, auto-select политика.

- `dispatcher.py`
  - `PropagationDispatcher` выбирает метод (`delta`/`monte_carlo`) и делает fallback при сбоях.

- `delta.py`
  - `DeltaMethodPropagator`: линейная аппроксимация через Jacobian (`jax.jacfwd`) и ковариацию входов.

- `monte_carlo.py`
  - `MonteCarloPropagator`: выборки из входных envelope distribution families и эмпирические интервалы по выходам.

- `covariance.py`
  - Сборка ковариационной матрицы и извлечение стандартных отклонений.

- `aggregator.py`
  - Агрегация нескольких envelopes (сейчас поддержан режим `widest`).

- `protocol.py`
  - Контракты `PropagationResult` / `PropagationStrategy`.

## Логика выбора метода

`preferred_method` из `PropagationConfig`:
- `delta` — принудительный delta method;
- `monte_carlo` — принудительный MC;
- `auto` — авто-выбор.

При `auto` используется delta method только если:
- входные envelopes имеют совместимый normal/statistical вид;
- execution function дифференцируема в JAX;
- dry-run Jacobian проходит без ошибок.

Иначе используется Monte Carlo.

## Выходы и семантика

Результат — список `PropagationResult`, где каждый элемент содержит:
- `metric_id`;
- `UncertaintyEnvelope` (point estimate, interval, confidence semantics, metadata);
- `method_used` и диагностические поля (sample counts, jacobian norms и т.д.).

## Связь с другими директориями

`uncertainty` зависит от:
- `ir/analytics/uncertainty` (канонические контракты envelope/метаданных);
- JAX (`jax`, `jax.numpy`, `jax.random`) для delta и sampling вычислений.

Используется в:
- `scientist/nodes/builtins/simulate/propagate_uncertainty.py`.

## Текущее состояние и ограничения

- Режим `analytical` в dispatcher сейчас маппится на Monte Carlo fallback path.
- Для delta method ожидается JAX-дифференцируемая функция симуляции.
- При нехватке валидных MC выборок формируется heuristic envelope (`gate_eligible=False`).
