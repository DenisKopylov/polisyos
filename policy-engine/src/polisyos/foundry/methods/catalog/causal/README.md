# Causal Catalog (`polisyos.foundry.methods.catalog.causal`)

`methods/catalog/causal` — канонический каталог causal-методов Foundry после миграции из legacy путей `methods/causal/*`.

Актуально по коду на 2026-03-11.

## Роль в системе

Каталог предоставляет типизированные causal-методы для:

- оценки эффектов и policy-аналитики;
- discovery и согласования причинных графов;
- transportability/parameter transfer между контекстами;
- диагностик устойчивости и чувствительности.

Методы регистрируются в `MethodRegistry` и вызываются либо напрямую через `methods` API, либо как `method`-узлы в Foundry execution graph.

## Структура каталога

- `protocols.py`: входные контракты (`PanelObservationalData`, `GraphCausalData`, `TimeSeriesCausalData`, `ParameterTransferData` и др.).
- `_registry_boot.py`: централизованный список классов для регистрации каталога.
- `_common.py`, `_graph_projection.py`: общие вычислительные утилиты и графовые преобразования.
- `ci_backends.py`: выбор backend-а условной независимости (`auto|numpy|jax`).
- `capabilities.py`: runtime-capability contract для causal/transport backends и identification families.
- `full_transport_bridge.py`: проверка доступности symbolic backend (`y0`/`r_causaleffect`) и нормализация transport-формул.
- `transport_engine.py`: канонический transport/TRSO orchestrator (`y0 -> r_causaleffect -> bounds`, `simplified_legacy` только по explicit opt-in).

## Группы методов

- Effect estimation: `did.py`, `rdd.py`, `synthetic_control.py`, `structural_time_series.py`, `dowhy_identify_estimate.py`, `dowhy_refute.py`.
- SCM/query: `gcm_fit.py`, `gcm_query.py`.
- Graph discovery: `constraint_discovery.py`, `pcmci_discovery.py`, `dagma_discovery.py`.
- Graph governance: `graph_reconciliation.py`, `literature_prior.py`.
- Transportability: `transport_engine.py`, `transport_check.py`, `symbolic_identify.py`, `parameter_transfer.py`.
- Sensitivity: `sensitivity_metrics.py`.
- Optional HTE/policy learning: `cate.py`, `dml.py`, `meta_learners.py`, `policy_learning.py`.

## Регистрация и совместимость

- Основной реестр строится через `register_causal_methods()` из `_registry_boot.py`.
- `ensure_causal_methods_registered()` в `__init__.py` регистрирует методы idempotent-путем.
- Legacy импорт `polisyos.foundry.methods.causal.*` сохранен как facade и реэкспортирует этот каталог.

## Runtime capability contract

- Capability posture теперь строится через `CausalCapabilityContract`.
- Contract фиксирует:
  - доступность backend-ов: `y0`, `r_causaleffect`, `bounds_only`, `simplified_legacy`;
  - support по identification families: `frontdoor`, `do_calculus_rule2`, `do_calculus_rule3`, `c_component_factorization`, `bounds_manski`;
  - dependency fingerprint и degradation policy.
- `transport_check.py` и `symbolic_identify.py` больше не являются независимыми standard-path solver-ами:
  - `transport_check.py` — legacy simplified shim;
  - `symbolic_identify.py` — compatibility shim поверх канонического transport engine.

## Зависимости и деградация

- Базовые методы работают на `numpy` + внутренних контрактах.
- Optional dependency profiles:
  - `causal-core`
  - `causal-symbolic-y0`
  - `causal-symbolic-r`
  - `causal-full`
- R-path требует `rpy2` и установленный R package `causaleffect`; pip extras проверяют только `rpy2`, сам `causaleffect` валидируется probe-ом во runtime.
- В текущем репо-окружении symbolic deps не установлены, поэтому full symbolic families будут помечены runtime contract-ом как unavailable/unsupported, а не silently downgraded.

## Связь с другими директориями

- Контракты результатов: `polisyos/ir/analytics/causal*`, `transportability`, `sensitivity`, `hte`.
- Оркестрация использования: `polisyos/scientist/nodes/builtins/causal/*`.
- Исполнение в Foundry: через `methods` registry/dispatcher и method-узлы program graph.

## Текущее состояние

- Каталог активно расширяется (новые discovery/symbolic/transportability модули).
- Для стабильного прод-контура важно фиксировать optional dependency matrix в окружении запуска.
