# Integration Tests

`tests/integration` содержит сквозные сценарии между слоями `core` и `scientist`, когда важна не изолированная функция, а поведение всей цепочки.

Актуально на **10 февраля 2026**.

## Текущее состояние

- `1` файл `test_*.py`
- `1` Python-файл
- `0` `conftest.py`
- `1` `README.md`

## Что проверяется сейчас

### `test_human_gate_audit.py`

Сценарий подтверждает корректность human-gate цикла в governance node:

- создаётся `gate_request` и соответствующий артефакт `ir.gate_request`;
- при решении `approve` формируется итоговый verdict;
- в trace фиксируются события `GATE_REQUESTED` и `GATE_DECIDED`;
- при решении `escalate` создаётся новый запрос с увеличенной итерацией и повышенным приоритетом.

## Связи с другими директориями

| Здесь | Связанные директории | Назначение связи |
|---|---|---|
| `tests/integration/` | `src/polisyos/core` | CAS, canon, run context, registry bundle |
| `tests/integration/` | `src/polisyos/scientist` | Governance node и state machine исполнения |

## Важно про маркеры

- Текущий тест **не** помечен `@pytest.mark.integration`.
- Поэтому он входит в обычный прогон `pytest` и не исключается `-m "not integration"`.

## Запуск

Команды из `policy-engine/`:

```bash
# весь текущий integration-контур
pytest tests/integration -q

# конкретный сквозной сценарий
pytest tests/integration/test_human_gate_audit.py -q
```
