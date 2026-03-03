# Causal Catalog (`polisyos.foundry.methods.catalog.causal`)

`methods/catalog/causal` — канонический каталог causal-методов Foundry после миграции из legacy путей `methods/causal/*`.

Актуально по коду на 2026-03-03.

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
- `full_transport_bridge.py`: проверка доступности symbolic backend (`y0`/`r`) и нормализация transport-формул.

## Группы методов

- Effect estimation: `did.py`, `rdd.py`, `synthetic_control.py`, `structural_time_series.py`, `dowhy_identify_estimate.py`, `dowhy_refute.py`.
- SCM/query: `gcm_fit.py`, `gcm_query.py`.
- Graph discovery: `constraint_discovery.py`, `pcmci_discovery.py`, `dagma_discovery.py`.
- Graph governance: `graph_reconciliation.py`, `literature_prior.py`.
- Transportability: `transport_check.py`, `symbolic_identify.py`, `parameter_transfer.py`.
- Sensitivity: `sensitivity_metrics.py`.
- Optional HTE/policy learning: `cate.py`, `dml.py`, `meta_learners.py`, `policy_learning.py`.

## Регистрация и совместимость

- Основной реестр строится через `register_causal_methods()` из `_registry_boot.py`.
- `ensure_causal_methods_registered()` в `__init__.py` регистрирует методы idempotent-путем.
- Legacy импорт `polisyos.foundry.methods.causal.*` сохранен как facade и реэкспортирует этот каталог.

## Зависимости и деградация

- Базовые методы работают на `numpy` + внутренних контрактах.
- Часть модулей использует optional deps (`econml`, `shap`, `dagma`, `y0`, `rpy2`, внешние CI/discovery стеки).
- При недоступности optional deps применяются fallback-ветки или методы не добавляются в bootstrap-список.

## Связь с другими директориями

- Контракты результатов: `polisyos/ir/analytics/causal*`, `transportability`, `sensitivity`, `hte`.
- Оркестрация использования: `polisyos/scientist/nodes/builtins/causal/*`.
- Исполнение в Foundry: через `methods` registry/dispatcher и method-узлы program graph.

## Текущее состояние

- Каталог активно расширяется (новые discovery/symbolic/transportability модули).
- Для стабильного прод-контура важно фиксировать optional dependency matrix в окружении запуска.
