# ir.analytics

`ir.analytics` — контрактный слой аналитических результатов и их CAS-персистенции.

## Роль

- стандартизирует causal/uncertainty/hte/distribution/backtest отчёты;
- описывает transportability, SCM и causal-query контракты;
- содержит applicability/runtime data-view модели;
- предоставляет `persist_*` / `load_*` helpers через `ir.artifacts`.

## Состав модулей

### Базовые аналитические контракты

| Файл | Назначение |
|---|---|
| `uncertainty.py` | `UncertaintyEnvelope`, интервальная семантика, `gate_eligible` |
| `causal.py` | `CausalEffectReport`, diagnostics/refutation/placebo, `to_uncertainty_envelope()` |
| `sensitivity.py` | `SensitivityResult`, `EValueResult` |
| `hte.py` | `HTEResult`, `PolicyRecommendation`, targeting rules |
| `distributional.py` | cohort breakdowns, winners/losers, equity checks |
| `backtest.py` | сценарные ретроспективные сравнения `y_pred/y_true` и bias summary |

### Causal infrastructure и переносимость

| Файл | Назначение |
|---|---|
| `causal_graph.py` | `CausalGraphModel`, `CausalEdge`, проверки DAG/PAG |
| `causal_graph_kuzu.py` | интеграция causal graph с Kuzu (опциональный backend) |
| `causal_discovery.py` | `CausalDiscoveryReport` и CAS helpers |
| `causal_queries.py` | `CausalQuery`, `CausalQueryResult`, soft/atomic interventions |
| `causal_ensemble.py` | ансамбль causal моделей (`CausalModelEnsemble`) |
| `structural_causal_model.py` | `StructuralCausalModelSpec`, `NodeMechanism` |
| `transportability.py` | `TransportabilityResult`, selection diagram, data gaps |
| `partial_identification.py` | Manski bounds (`PartialIdentificationResult`) |

### Literature/context/alignment

| Файл | Назначение |
|---|---|
| `literature.py` | extraction result, literature causal priors, reconciliation diagnostics |
| `context.py` | `ContextProfile`, context distance/enrichment helpers |
| `parameters.py` | context-adaptive parameter bundle и applicability оценка |
| `abm_bridge.py` | `ABMAlignmentReport` (SCM ↔ ABM consistency) |
| `alignment_certification.py` | policy/certificate/outer-search helpers для alignment протокола |

### Governance-adjacent и runtime API

| Файл | Назначение |
|---|---|
| `applicability.py` | `NormApplicability`, `IdSelector`, `TimeWindow` |
| `data_views.py` | runtime `DataViewRequest` (`panel/snapshot/network`) |
| `calibration.py` | `CalibrationConfig`, trainable params, fidelity/loss настройки |
| `ddl/kuzu_causal.cypher` | DDL для Kuzu-представления causal графа |

## Важные особенности

- Для большинства аналитических отчётов persist-функции используют `CanonSpec(forbid_floats=False)`.
- `CausalEffectReport.to_uncertainty_envelope()` покрывает оба режима:
  - успешная оценка -> статистический envelope;
  - failure status -> heuristic envelope (`gate_eligible=False`).
- `data_views.py` и `ir/queries.py` содержат разные `DataViewRequest`:
  - `analytics.data_views.DataViewRequest` — runtime-аналитический запрос;
  - `queries.DataViewRequest` — query-layer контракт.
- Версии схем в текущем коде:
  - большинство аналитических артефактов: `schema_version="1.0"`;
  - `CalibrationConfig`: `schema_version="0.1"`;
  - `ArticleExtractionResult` из `literature.py`: `schema_version="1.1"` (с backward compatibility для legacy payload).

## Где используется

| Директория | Использование |
|---|---|
| `foundry/methods` | causal inference, transportability, uncertainty |
| `scientist/` | policy evaluation, governance preflight, decision packet inputs |
| `fabric/` | confidence/conflict pipelines через uncertainty и refs |
| `core/` | CAS refs и compatibility-слой аналитических артефактов |

## Быстрый импорт

```python
from polisyos.ir.analytics import CausalEffectReport, HTEResult, UncertaintyEnvelope
```
