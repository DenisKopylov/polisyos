# Integration Tests

`tests/integration` содержит сквозные сценарии на стыке `core` и `scientist`, где важна корректность полной цепочки исполнения.

Актуально на **17 февраля 2026**.

## Текущее покрытие

- `1` файл `test_*.py`: `test_human_gate_audit.py`
- `2` сценария:
  - проверка цикла `human_gate -> approve` с аудит-трейлом;
  - проверка `escalate` (рост `iteration`, новый `request_id`, приоритет `critical`).

## Что важно

- Тест не помечен `@pytest.mark.integration`, поэтому входит в обычный прогон `pytest`.
- Проверяются события trace: `GATE_REQUESTED`, `GATE_DECIDED`.

## Связи с кодом

- `policy-engine/src/polisyos/core/run`
- `policy-engine/src/polisyos/scientist/nodes/builtins/governance`
- `policy-engine/src/polisyos/scientist/engine`

## Запуск

```bash
pytest tests/integration -q
pytest tests/integration/test_human_gate_audit.py -q
```
