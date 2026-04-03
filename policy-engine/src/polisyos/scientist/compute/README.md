# Compute (`polisyos.scientist.compute`)

`compute` инкапсулирует исполнение Scientist job-ов поверх Foundry runtime: от
legacy program execution до method-based path и нового C7 advanced suite.

## Роль в системе

- **Зависит от:** `foundry.executor`, `foundry.methods`, `core.artifacts`
- **Используется в:** causal builtin nodes, advanced method orchestration, simulation bridges
- Пакет дает единый runtime facade для materialize/dispatch/persist циклов.

## Ключевые концепции

- **JobSpec / JobKey / JobResult** — typed контракт job-а, дедупликации и результата.
- **MethodBackend** — запуск Foundry methods через dispatcher/registry.
- **Legacy path** — поддержка `legacy_program` execution для старых flows.
- **C7 advanced suite** — новый набор advanced method runners и persisted artifacts.
- **CAS materialization** — входы/выходы передаются ссылками и фиксируются как artifacts.

## Public API

- `JobSpec`, `JobKey`, `JobResult`
- `run_job(...)`, `MethodBackend`
- `C7AdvancedInputs`, `C7AdvancedSuiteResult`, `C7PersistedArtifact`
- `run_c7_advanced_suite(...)`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 4
- Public surface: re-exports from `__init__.py` for job runtime and C7 advanced suite
- Недавний delta: добавлен `advanced_methods.py`, README раньше не отражал C7 path
