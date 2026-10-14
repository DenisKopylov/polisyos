# Search Strategies (`polisyos.scientist.methods.search.strategies`)

`search.strategies` содержит candidate generators и runtime helpers для
sample-efficient policy search: от базовых random/grid вариантов до optional
Bayesian и multi-objective контуров.

## Роль в системе

- **Зависит от:** `search`, optional `torch`/`botorch`/`gpytorch`
- **Используется в:** `SearchController`, policy-design optimization loops
- Пакет отделяет пространство параметров и генерацию кандидатов от orchestration-кода `search.controller`.

## Ключевые концепции

- **SearchStrategy** — базовый protocol для генераторов кандидатов.
- **SearchSpace + codecs** — описание параметров и их приведение к runtime форме.
- **Deterministic baselines** — `RandomSearchStrategy`, `GridSearchStrategy`.
- **Advanced optimizers** — optional Bayesian и multi-objective backends.
- **WS-3C policy toolkit** — offline-gated BOHB/ASHA, CMA-ES, learned VOI,
  learned routing, GP surrogate, constraint propagation and PBT helpers.

- **Resource arbitration** — лимиты памяти/ресурсов для дорогих strategy paths.

## Public API

- `SearchStrategy`, `BaseSearchStrategy`, `StrategyAdapter`
- `SearchSpace`, `ParameterCodec`, `ScalarParameterCodec`
- `PolicyCandidate`, `Evaluation`, `StrategyState`
- `RandomSearchStrategy`, `GridSearchStrategy`
- `ResourceArbiter`, `ResourceMode`, `memory_cleanup(...)`
- optional: `BayesianConfig`, `BayesianOptimizer`, `MOConfig`, `MOBayesianOptimizer`
- WS-3C: `AdvancedSearchPolicyConfig`, `ASHAScheduler`, `BOHBSampler`,
  `CMAESExplorer`, `GaussianProcessCheapStageSurrogate`,
  `ExplicitConstraintPropagator`, `LearnedVOIPolicy`, `LearnedRoutingPolicy`,
  `PopulationBasedTrainingScheduler`

Подробности: [Reference →](../../../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-10-14
  - WS-3C advanced policy surface обновлён: 2026-04-12
  - Canonical path moved under `polisyos.scientist.methods.search`: 2026-05-05
- Исходники Python: 24 модуля кроме `__init__.py` (25 файлов `.py` вместе с
  `__init__.py`) в snapshot `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`.
- Статическая публичная поверхность: 36 имён в `__all__`, включая 18 базовых и 18
  WS-3C toolkit names; optional Bayesian imports can append four names when their
  dependencies load successfully.
- README синхронизирован с текущим lazy/optional import поведением пакета

`BayesianOptimizer.warm_start` сохраняет каждую отклонённую `Evaluation` вместе
с исходной причиной отказа в `StrategyState.metadata.warm_start_rejections`
(version 1). `StrategyState.to_artifact/from_artifact` и `set_state/get_state`
переносят эту историю независимо от optional GP backend. Snapshot сохраняет
полный candidate ID, provenance, параметры, исходы и metadata; повторные
отклонённые обращения остаются отдельными записями. Эти записи не входят в
training corpus и не меняют существующие compatibility/admission predicates.
Для старого checkpoint без ledger `complete=false` явно сохраняет ограничение:
прежние исчезнувшие записи и причины не восстановлены. Поле не доказывает
scientific provenance, refinement permission или production admission law.

Cold-start Sobol index и adaptive single-candidate acquisition planning получают
тот же admitted/deduplicated corpus, что training path: whole и warm+current
представления одинаковых разрешённых записей дают согласованный план. Batch
сохраняет существующий fixed qEI путь; current-request iteration и full-refit
counters не меняют своего прежнего значения от warm-history count.

### Кэш истории transfer

TransferLearningManager удерживает в LRU только проверенные canonical bytes истории. Ключ связывает полный ArtifactRef (artifact ID, kind, media type и выбранный manifest profile) с полной идентичностью запуска. При каждом попадании кэш повторно проверяет выбранный CAS profile и digest байтов, затем заново декодирует запись; изменяемые Evaluation и вложенные значения между чтениями не разделяются.

Кэш ограничен 128 записями и 32 MiB суммарной длины сохранённых payload bytes (len(raw_payload_bytes)). Это граница retained payload, а не оценка RSS или Python overhead. История больше лимита читается и проверяется, но не сохраняется в кэше. Eviction не удаляет CAS-артефакт и не меняет возможность прочитать старый точный ref. Новые записи индекса сохраняют profile hash, возвращённый тем же CAS write; у прежних строк индекса без него остаётся profileless compatibility ref, который всё равно проходит канонический reader.
