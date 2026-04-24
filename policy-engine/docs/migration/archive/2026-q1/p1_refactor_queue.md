# P1 Refactor Queue

## Приоритеты

1. `P0/P1` циклы и нарушения в data-plane (`fabric -> foundry -> scientist`) при наличии.
2. `P1` цикл `lex -> scientist`.
3. `P1` зависимости `core -> fabric/runtime`.
4. `P1` цикл `core/fabric/ir/runtime`.
5. `P2` дубли и унификация component discovery.

## Очередь работ

1. Q1: Разорвать цикл `CYCLE-002` (`polisyos.foundry <-> polisyos.foundry.domain`).

- Источник: `arch_cycles_register.csv`.
- Цель: выделить стабильный domain facade, убрать обратный импорт.
- Фаза: `P5` (выполнено).
- Owner: `team-foundry`.
- Статус: `Done` (`2026-02-09`), введены `foundry/contracts` и `foundry/mechanisms`, цикл закрыт в `arch_cycles_register.csv`.

1. Q2: Разорвать цикл `CYCLE-003` (`polisyos.lex <-> polisyos.scientist`).

- Источник: `arch_cycles_register.csv`.
- Цель: вынести governance contracts в neutral слой (`core/common`) и заменить прямые зависимости.
- Фаза: `P2` (выполнено).
- Owner: `team-lex, team-scientist`.
- Статус: `Done` (`2026-02-09`), цикл закрыт в `arch_cycles_register.csv`.

1. Q3: Устранить `ARCH001` core -> fabric/runtime (`ARCH001-0033..0036`).

- Источник: `import_debt_register.csv`.
- Цель: перейти на публичные фасады и события вместо прямых импортов.
- Фаза: `P3` (выполнено).
- Owner: `team-core`.
- Статус: `Done` (`2026-02-09`), удалены `E-2026-02-CORE-FABRIC-001` и `E-2026-02-CORE-RUNTIME-001`, debt-строки `ARCH001-0033..0036` закрыты.

1. Q4: Устранить `ARCH001` lex -> scientist (`ARCH001-0029..0032`).

- Источник: `import_debt_register.csv`.
- Цель: внедрить интерфейс policy-governance API между lex и scientist.
- Фаза: `P2` (выполнено).
- Owner: `team-lex, team-scientist`.
- Статус: `Done` (`2026-02-09`), debt-строки удалены из `import_debt_register.csv`.

1. Q5: Устранить `ARCH001` ir -> core (`ARCH001-0001..0028`).

- Источник: `import_debt_register.csv`.
- Цель: перенести общие контракты в IR-safe фасад, убрать прямой импорт core internals.
- Фаза: `P4` (выполнено).
- Owner: `team-ir, team-core`.
- Статус: `Done` (`2026-02-09`), удалены `E-2026-02-IR-CORE-001..010`, debt-строки `ARCH001-0001..0028` закрыты.

1. Q6: Снизить `stale_sources_missing_paths_count`.

- Источник: `summary.json`, `stale_sources_missing_paths.txt`.
- Цель: пересобрать packaging metadata и удалить несуществующие пути из `SOURCES.txt` генерацией актуального sdist.
- Фаза: `P1`.
- Owner: `team-core`.

1. Q7: Component discovery cleanup.

- Источник: архитектурный обзор P2.
- Цель: унифицировать точки обнаружения компонентов и убрать дубли.
- Фаза: `P6` (выполнено).
- Owner: `team-core, team-fabric, team-foundry`.
- Статус: `Done` (`2026-02-10`), discovery/bootstrap для connectors/methods/nodes/evaluators/extractors/providers унифицированы через `core.components` и adapter-bridge слой.

1. Q8: Connector platform hardening.

- Источник: `p7_connector_platform_hardening_spec.md`.
- Цель: ввести `HTTPConnectorBase`, убрать дубли runtime-helper’ов в production connectors и стабилизировать envelope/ingestion contracts.
- Фаза: `P7` (выполнено).
- Owner: `team-fabric, team-core`.
- Статус: `Done` (`2026-02-10`), `world_bank/eurostat/ukons` переведены на shared HTTP runtime, добавлены hardening lint + P7 tests, ingestion fetch activity расширен полями freshness/duration/quality flags.

1. Q9: Foundry data-plane input bindings.

- Источник: `p8_foundry_data_plane_spec.md`.
- Цель: внедрить canonical `foundry.input_bindings`, deterministic binding/materialization путь, pre-simulation data-plane gate и replay completeness для binding-артефактов.
- Фаза: `P8` (выполнено).
- Owner: `team-foundry, team-scientist, team-fabric, team-core`.
- Статус: `Done` (`2026-02-10`), добавлены contracts/data-plane module/nodes/workflow wiring, replay+decision packet integration, lint `lint_foundry_data_plane.py` и P8 regression tests.

1. Q10: Runtime API + Frontend foundation.

- Источник: `p9_runtime_api_frontend_foundation_spec.md`.
- Цель: внедрить Runtime HTTP API v1 (`/api/v1`) для Run Explorer/Debug/Artifact Inspector, typed contracts, core+legacy run adapters, OpenAPI export, generated frontend client и reference UI shell; зафиксировать API-first cutover и перевести `dashboard.py` в demo-only.
- Фаза: `P9` (выполнено).
- Owner: `team-runtime, team-scientist, team-core, team-security, team-platform-ui`.
- Статус: `Done` (`2026-02-10`), реализованы routes/services/adapters/contracts/tests, tenant/authz checks, OpenAPI + generated client + reference shell, docs cutover.

1. Q11: Cutover & legacy removal.

- Источник: `p10_cutover_legacy_removal_spec.md`.
- Цель: завершить API/data-plane cutover и удалить отложенные compatibility paths из P5-P9: runtime legacy lifecycle/manifest + legacy run adapters, foundry state-source fallback, foundry/domain facades, legacy plugin bootstrap groups (`polisyos.connectors`, `polisyos.methods`), а также закрыть legacy dashboard path.
- Фаза: `P10` (выполнено).
- Owner: `team-runtime, team-foundry, team-scientist, team-core, team-fabric, team-platform-ui`.
- Статус: `Done` (`2026-02-10`), legacy runtime/foundry/bootstrap paths удалены, contracts/docs/lints обновлены, добавлены P10 regression tests и tooling (`tools/runtime/*`, `tools/lint/lint_legacy_cutover.py`).
