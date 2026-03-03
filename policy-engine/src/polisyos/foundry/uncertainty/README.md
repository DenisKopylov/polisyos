# Uncertainty (`polisyos.foundry.uncertainty`)

`uncertainty` — подсистема propagation неопределенности для выходных метрик Foundry-симуляций.

Актуально по коду на 2026-03-03.

## Роль в системе

Подсистема принимает uncertainty envelopes входных параметров и оценивает, как неопределенность переносится на выходные метрики симуляции.

Типичный сценарий: `scientist` узел `propagate_uncertainty` после `run_simulation` или `calibration`.

## Архитектурный поток

```text
input envelopes + nominal params + simulation_fn + output_metric_ids
        |
        v
PropagationDispatcher
   |- DeltaMethodPropagator (jacobian-based)
   \- MonteCarloPropagator (sampling-based)
        |
        v
PropagationResult[] (metric_id -> UncertaintyEnvelope)
        |
        v
optional aggregate_envelopes(...)
```

## Ключевые модули

- `config.py`: `PropagationConfig` (confidence level, delta/mc параметры, auto policy).
- `dispatcher.py`: выбор стратегии (`delta`/`monte_carlo`/`auto`) и fallback.
- `delta.py`: линейная аппроксимация через Jacobian (`jax.jacfwd`) и ковариацию входов.
- `monte_carlo.py`: sampling по distribution families и эмпирические интервалы.
- `covariance.py`: сборка covariance и извлечение std.
- `aggregator.py`: объединение нескольких envelopes (сейчас `method="widest"`).
- `protocol.py`: `PropagationResult` / `PropagationStrategy` контракты.

## Логика выбора метода

`preferred_method` из `PropagationConfig`:

- `delta`: принудительный delta method;
- `monte_carlo`: принудительный Monte Carlo;
- `auto`: выбор по условиям применимости.

`auto` использует delta method только если одновременно выполняются условия:

- входные envelopes совместимы с normal-предпосылкой;
- simulation function дифференцируема для JAX;
- dry-run Jacobian проходит без ошибок.

Иначе используется Monte Carlo.

## Выходы

Результат — список `PropagationResult`, где для каждой метрики есть:

- `metric_id`;
- `UncertaintyEnvelope` (point estimate, interval, semantics, metadata);
- `method_used` и диагностические поля (`n_samples`, jacobian norms, fallback info).

## Связь с другими директориями

`uncertainty` зависит от:

- `ir/analytics/uncertainty` (канонические контракты envelope/метаданных);
- JAX (`jax`, `jax.numpy`, `jax.random`) для delta и sampling путей.

Используется в `scientist/nodes/builtins/simulate/propagate_uncertainty.py`.

## Текущее состояние и ограничения

- `preferred_method="analytical"` сейчас маппится на Monte Carlo fallback path.
- Для delta method требуется JAX-дифференцируемая функция симуляции.
- При нехватке валидных MC выборок формируется heuristic envelope (`gate_eligible=False`).
