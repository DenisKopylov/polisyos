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
| `dynamic_regime.py` | dynamic treatment regimes, longitudinal results, `ContinuousTimeQuery`, `EffectTrajectoryBundle`, CAS helpers |
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
| `alignment_certification.py` | B.1-B.2 `VariableAlignmentCertificate`, `AlignmentReport`, `AlignmentVerificationConfig`, verification entrypoints, persist/load helpers, plus policy/outer-search helpers |
| `cross_graph.py` | `CrossGraphEvidenceProfile`, `SCMFragment`, derived interface schemas, `InterfaceMapping`, `CompositionCertificate`, CAS helpers |

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
  - `CrossGraphEvidenceProfile`: `schema_version="2.1"`.
- Phase B surface:
  - `verify_fragment_alignment()` / `verify_fragment_bundle_alignment()` возвращают детерминированные `AlignmentReport` + `InterfaceMapping`; bundle-верификация поддерживает optional topology override через `stitch_pairs`;
  - `AlignmentReport.metadata` фиксирует topology-aware diagnostics, включая `selected_stitch_pairs`, `boundary_interface_variables`, `disconnected_fragment_ids`;
  - `ComposeSCMFragments` строит `CompositionCertificate` поверх verified alignment и возвращает first-class `failure_cards` в result payload;
  - `check_query_preservation*()` и `evaluate_query_preservation*()` в Phase B гарантируют статусы только для query classes, редуцируемых к known graphical obligations; unsupported query classes возвращают явный `unknown` с reason-coded trace;
  - `FragmentInterfaceSchema` остаётся derived-only и в B.1/B.2 не хранится как отдельный CAS artifact.
- Phase C surface:
  - `ContinuousTimeQuery` фиксирует horizon, time scale, interpolation policy, `query_mode` (`fixed_intervention` vs `optimal_policy_discovery`), backend gating и runtime blockers как first-class temporal contract;
  - `TemporalInterventionTrajectory` является executable intervention artifact для engine-level temporal execution и materialization на compiled grid;
  - `DynamicTreatmentRegime` теперь также может жить как CAS-backed policy artifact для adaptive DTR temporal route; canonical adaptive execution публикует learned policy artifact плюс derived schedule artifact;
  - `EffectTrajectoryBundle` требует trajectory/band/solver diagnostics refs, truthfully различает continuous solve и `discrete_replay` fallback, и публикует `discretization_error` либо `discretization_note`;
  - publication-grade Phase C claims должны идти через `CausalEngine.temporal_causal_effect()` с CAS-backed query/intervention-or-derived-schedule/policy/trajectory/band/diagnostics lineage;
  - temporal benchmark acceptance для publication-grade claims требует reloadable CAS artifacts, а не только in-memory refs;
  - C.4 (`irregular_grid`, rough-path, `neural_*`) остаётся research-gated и в production/runtime surface завершается only safe rejection.

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
