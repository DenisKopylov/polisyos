# ir.analytics

`ir.analytics` содержит контракты аналитических результатов и функции их CAS-персистенции.

## Роль

- стандартизирует отчёты uncertainty/causal/hte/distributional/backtest;
- хранит applicability-контракты для норм;
- описывает runtime data-view запросы для аналитики;
- даёт `persist_*` / `load_*` helpers поверх `ir.artifacts`.

## Состав

| Файл | Назначение |
|---|---|
| `uncertainty.py` | `UncertaintyEnvelope`, интервальная семантика и gate-eligibility |
| `causal.py` | `CausalEffectReport`, diagnostics/placebo, конверсия в uncertainty envelope |
| `hte.py` | `HTEResult`, `PolicyRecommendation`, targeting rules |
| `distributional.py` | distributional breakdowns, winners/losers, equity checks |
| `backtest.py` | retrospective сравнение `y_pred`/`y_true`, bias summary |
| `calibration.py` | `CalibrationConfig` и target/trainable конфигурация |
| `applicability.py` | `NormApplicability` и селекторы actor/concept/jurisdiction |
| `data_views.py` | runtime `DataViewRequest` для panel/snapshot/network |

## Особенности

- Для отчётов с float-полями persist функции используют `CanonSpec(forbid_floats=False)`.
- `CausalEffectReport.to_uncertainty_envelope()` поддерживает и success, и failure режимы.
- В `data_views.py` контракт отличается от `ir/queries.py`:
  - `analytics.data_views.DataViewRequest` ориентирован на runtime-аналитику;
  - `queries.DataViewRequest` ориентирован на query-layer API.

## Где используется

| Директория | Использование |
|---|---|
| `foundry/uncertainty` | расчёт и агрегация `UncertaintyEnvelope` |
| `fabric/claims/conflicts` | uncertainty adaptation при resolve/confidence |
| `scientist/` | аналитические контракты для оценки политик |
| `core/contracts` | compatibility facades на `ir.refs` |

## Быстрый импорт

```python
from polisyos.ir.analytics import CausalEffectReport, HTEResult, UncertaintyEnvelope
```
