# Orchestrator (`polisyos.scientist.orchestrator`)

`orchestrator` публикует presentation-friendly readout поверх итогового
`DecisionPacket`: компактные decision cards, issue summaries и key metrics
для CLI, UI и reporting consumers.

## Роль в системе

- **Зависит от:** decision-packet payloads from Scientist runtime
- **Используется в:** human-facing summaries, reporting and presentation layers
- Пакет не исполняет workflow logic и не модифицирует run-state.

## Ключевые концепции

- **DecisionCard** — короткая карточка policy decision.
- **IssuesSummary** — свернутое представление governance/problem issues.
- **KeyMetric** — нормализованный metric snippet для summary surfaces.

## Public API

- `DecisionCard`
- `IssuesSummary`
- `KeyMetric`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 2
- Exports: 3
- README переписан по общему шаблону; пакет остается intentionally small
