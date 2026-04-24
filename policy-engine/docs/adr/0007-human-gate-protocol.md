# ADR-0007: Human Gate Protocol in IR

- **Дата**: 2026-02-06
- **Статус**: Accepted
- **Решение**: Вынести Human Gate контракты в `polisyos.ir.governance.gate` и централизовать lifecycle в `HumanGateProtocol`.

## Контекст

Human gate ранее был распределён между:

- `ExperimentState.params["require_human_gate"]`
- `ExperimentState.params["gate_decision"]` (строка/словарь)
- `scientist.kernel.human_gate` (legacy модели)

Не было формального CAS audit trail и стабильного request identity для ретраев.

## Решение

Введены typed контракты:

- `GateContext`
- `GateRequest`
- `GateDecision`
- `GateEvent`

и orchestration-сервис:

- `HumanGateProtocol` (`src/polisyos/scientist/kernel/gate_protocol.py`)

Ключевые свойства:

- Детерминированный `request_id`:
  `sha256("{run_id}:{phase}:{node_alias}:{iteration}")`

- Персистенс `GateRequest`/`GateDecision` в CAS (`ir.gate_request`, `ir.gate_decision`)
- Запись `GATE_REQUESTED`/`GATE_DECIDED` в `trace.jsonl`
- Корреляция с OTel trace/span id
- Логика escalation без бесконечного цикла:
  `iteration += 1`, `is_escalated=true`, `priority=critical`

## Миграция и совместимость

- `RunGovernanceNode` мигрирован на `HumanGateProtocol`.
- Legacy форматы решения (`"approve"`, `"reject"`, `{approved: bool}`) поддерживаются парсером.
- `scientist.kernel.human_gate` оставлен как compatibility shim и помечен deprecated.
- `ExperimentState.params` расширен до JSON-like структуры для typed payload.

## Последствия

### Плюсы

- Формальный, воспроизводимый audit trail по gate-решениям.
- Идемпотентный request identity для retry-сценариев.
- Единый protocol слой для Scientist/UI/API.

### Минусы

- Больше состояния в `params` и больше CAS артефактов.

### Риски

- Legacy потребители могут полагаться на старые поля.

### Митигации

- Сохранён fallback-парсинг и compatibility shim.
