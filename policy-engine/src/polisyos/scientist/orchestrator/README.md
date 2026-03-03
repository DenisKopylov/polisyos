# Orchestrator Utilities (`polisyos.scientist.orchestrator`)

`orchestrator` содержит presentation-утилиты поверх итогового `DecisionPacket`.

## Что внутри

- `decision_card.py`
  - `DecisionCard.from_packet(...)` — сборка краткой управленческой карточки решения;
  - агрегирует verdict/confidence, key metrics, issues summary, distributional блок;
  - умеет сериализацию (`to_dict`) и markdown-рендер (`render_markdown`).
- `__init__.py`
  - публичные re-export: `DecisionCard`, `IssuesSummary`, `KeyMetric`.

## Роль в системе

- не участвует в обязательном execution DAG;
- используется как дополнительный слой человеко-читаемого summary для CLI/UI/reporting поверх уже собранного packet.

## Входные зависимости

- ожидает payload, совместимый с `scientist.decision_packet`;
- использует только read-only извлечение полей и агрегирование, без модификации состояния run.
