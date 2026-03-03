# Contracts — typed ABI между подсистемами

`core.contracts` фиксирует межмодульные типы обмена:
- typed `ArtifactRef` (kind/media_type)
- DTO для runtime/control API
- модели lineage/provenance

Это canonical точка согласования между `fabric`, `foundry`, `scientist`, `lex`, `runtime`, `scholar`.

## Структура контрактов

| Группа | Файлы |
|---|---|
| Data-plane refs | `fabric.py`, `foundry.py`, `scientist.py`, `scholar.py`, `trinity.py`, `compiler.py`, `lex.py`, `execution_plan.py` |
| Runtime/control API | `runtime.py`, `control.py`, `cursor.py` |
| Provenance | `provenance.py` |
| Compatibility facades на `polisyos.ir.refs` | `backtest.py`, `causal.py`, `distributional.py`, `hte.py`, `uncertainty.py` |

## Принцип typed ref

```python
class FabricResultRef(ArtifactRef):
    kind: Literal["fabric.result_bundle"] = "fabric.result_bundle"
    media_type: Literal["application/json"] = "application/json"
```

Что это дает:
- строгую валидацию kind/media-type на границе модулей;
- совместимость с CAS manifest (`core.artifacts.manifest.ArtifactRef`);
- более безопасные migration-переходы в data-plane.

## Что важно после миграций

- Аналитические refs (`BacktestReportRef`, causal/distributional/hte/uncertainty refs) canonical в `polisyos.ir.refs`; в `core.contracts` оставлены совместимые re-export фасады.
- Runtime API модели централизованы в `runtime.py`, чтобы `runtime/http` и внешние клиенты использовали единый типовой слой.
- Планирование исполнения и preflight артефакты зафиксированы в `execution_plan.py` (`ExecutionPlanRef`, `PreflightReportRef`, `EvaluatorReportRef`, ...).

## Правила эволюции

- Не менять `kind/media_type` существующего ref без migration window.
- Новый межмодульный артефакт: сначала typed ref в `core/contracts`, затем producer/consumer в доменном модуле.
- Если canonical ref уже в `polisyos.ir.refs`, в `core/contracts` добавляется только фасад для обратной совместимости.
