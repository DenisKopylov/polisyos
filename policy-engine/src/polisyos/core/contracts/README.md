# Contracts — типизированный ABI PolisyOS

`core/contracts` фиксирует межмодульные data-контракты: typed `ArtifactRef`, DTO для запросов/ответов и общие модели lineage/runtime.
Это основной способ синхронизировать границы `fabric`, `foundry`, `scientist`, `lex`, `runtime`, `scholar`.

## Принцип

Базовый паттерн для ссылок:

```python
class FabricResultRef(ArtifactRef):
    kind: Literal["fabric.result_bundle"] = "fabric.result_bundle"
    media_type: Literal["application/json"] = "application/json"
```

Что это дает:

- строгую валидацию `kind/media_type`;
- совместимость с CAS-манифестами (`core.artifacts.manifest.ArtifactRef`);
- более безопасный обмен между командами/модулями.

## Структура контрактов

| Файл | Роль |
|---|---|
| `fabric.py` | запросы/планы/evidence/results data-plane |
| `foundry.py` | compile/execute/state/input_bindings/simulation артефакты |
| `scientist.py` | артефакты оркестрации экспериментов и governance |
| `scholar.py` | исследовательские intent/bundle/freshness контракты |
| `lex.py` | compliance контракты и `RuleBackend` protocol |
| `trinity.py` | typed refs для `ProblemFrame/PolicySpec/ModelSpec` |
| `compiler.py` | ссылки на compile/link отчеты |
| `runtime.py` | модели API runtime-debug/lineage/timeline |
| `provenance.py` | core lineage graph (`Entity/Activity/Agent/Edge`) |
| `backtest.py`, `causal.py`, `distributional.py`, `hte.py`, `uncertainty.py` | compatibility facades на `polisyos.ir.refs` |

## Что важно после миграций

- Контракты аналитических рефов (`BacktestReportRef`, `CausalEffectReportRef`, `DistributionalReportRef`, `HTEResultRef`, `PolicyRecommendationRef`, `UncertaintyEnvelopeRef`) теперь canonical в `polisyos.ir.refs`; в `core/contracts/*` оставлены фасады совместимости.
- Контракты runtime API (`runtime.py`) находятся в `core`, поэтому `runtime/http` и внешние клиенты опираются на единый типовой слой.
- Для Foundry canonical data-plane handoff: `foundry.input_bindings` (`FoundryInputBindingsRef`).

## Кто использует

- `foundry/`: `contracts.foundry`, `contracts.compiler`, `contracts.trinity`
- `fabric/`: `contracts.fabric`, `contracts.provenance`
- `scientist/`: `contracts.scientist`, `contracts.scholar`, `contracts.lex`
- `runtime/`: `contracts.runtime` + refs из `foundry/fabric`
- `lex/`: `contracts.lex` и governance-проходы

## Правила эволюции

- Не меняйте `kind/media_type` существующего typed-ref без migration window.
- Для нового межмодульного артефакта сначала добавляется typed-ref в `core/contracts`, потом запись/чтение в доменном модуле.
- Если тип canonical уже в `ir.refs`, в `core/contracts` добавляйте только facade-реэкспорт для обратной совместимости.
