# IR (`polisyos.ir`)

`polisyos.ir` задает канонический контрактный слой PolicyOS: Trinity payload,
registry-aware governance модели, world/analytics артефакты, CAS references и
новый observation surface для causal readiness и execution bundles. Модуль не
исполняет симуляции сам, а фиксирует типы и сериализационные границы, через
которые общаются `lex`, `fabric`, `foundry`, `scientist` и `core`.

## Роль в системе

- **Зависит от:** `polisyos.ir.kernel`, `polisyos.ir.artifacts`, `polisyos.ir.governance`, `polisyos.ir.trinity`
- **Используется в:** `polisyos.foundry`, `polisyos.scientist`, `polisyos.fabric`, `polisyos.lex`, `polisyos.core`
- Root package выступает lazy facade: `ir.__init__` реэкспортирует 160 публичных имен и стабилизирует import surface для соседних модулей.

## Ключевые концепции

- **TrinityBundle** — канонический payload `ProblemFrame + PolicySpec + ModelSpec`.
- **Registry-bound linking** — `RegistryBundle` и `link_trinity()` валидируют policy contracts против slots, mechanisms, metrics и units.
- **Observation layer** — `observation/` добавляет семейства наблюдений, measurement registries, governance mappings и компиляторы в foundry/scientist contracts.
- **Analytics artifacts** — causal, transportability, HTE, backtest и strategic IR модели живут в `analytics/`.
- **Typed CAS refs** — `refs.py` связывает доменные артефакты с canonical `ArtifactID`; новые типы включают `CausalReadinessBundleRef` и `CausalExecutionBundleRef`.
- **Deterministic canon** — `KernelModel` и canonical encoding задают воспроизводимую сериализацию и хэширование.

## Public API

| Type/Function | Description |
|---|---|
| `load_policy()` | Высокоуровневый загрузчик канонического Trinity payload |
| `ProblemFrame`, `PolicySpec`, `ModelSpec` | Три базовых контракта policy analysis |
| `TrinityBundle` | Канонический контейнер policy IR версии `1.0` |
| `link_trinity()` | Линкует Trinity bundle c registry и возвращает `LinkedTrinityBundle` + `LinkReport` |
| `ObservationRecord`, `ObservationPanel` | Базовые observation contracts для panel and record data |
| `CausalReadinessBundle`, `CausalExecutionBundle` | Observation-driven bundles для readiness checks и executable causal tasks |
| `GovernancePassMappingBundle` | Mapping между canonical governance surface и runtime passes |
| `CausalEffectReport`, `TransportabilityResult`, `StrategicResponseBundle` | Ключевые аналитические IR артефакты |

Full reference: [docs/reference/ir/](../../../docs/reference/ir/index.md)

## Where to Start

- Public facade / compatibility: `src/polisyos/ir/__init__.py` and `docs/reference/public-surface.md`
- ABI registry / snapshot ownership: `schemas/abi_models.py`, `schemas/snapshots/`, `tools/diagnostics/gen_schema.py`
- Trinity / policy contracts: `src/polisyos/ir/trinity/` and `src/polisyos/ir/governance/`
- Observation and analytics expansion: `src/polisyos/ir/observation/` and `src/polisyos/ir/analytics/`

## Текущее состояние

- Последнее обновление: 2026-04-03
- Files: 18 top-level Python files plus 8 subpackages
- Exports: 160 public names in `ir.__init__` (`159` unique; duplicate only for `GovernancePassMappingBundle`)
- Recent delta: добавлены `observation/`, strategic persistence helpers, temporal intervention contracts и cell-level kernel surface
