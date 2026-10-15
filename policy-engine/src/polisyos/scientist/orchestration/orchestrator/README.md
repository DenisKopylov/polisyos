# Orchestrator (`polisyos.scientist.orchestration.orchestrator`)

`orchestrator` publishes a presentation-friendly readout over the final
`DecisionPacket`: compact decision cards, issue summaries, and key metrics
for CLI, UI, and reporting consumers.

## Role in the system

- **Depends on:** decision-packet payloads from the Scientist runtime
- **Used by:** human-facing summaries, reporting, and presentation layers
- The package does not execute workflow logic or modify run state.

## Key concepts

- **DecisionCard** — a concise policy-decision card.
- **IssuesSummary** — a compact representation of governance/problem issues.
- **KeyMetric** — a normalized metric snippet for summary surfaces.

## Public API

- `DecisionCard`
- `IssuesSummary`
- `KeyMetric`

Details: [Reference →](../../../../../docs/reference/scientist/index.md)

## Current state

- Last updated: 2026-10-14
- Python modules: 2
- Exports: 3
- The README was rewritten to follow the shared template; the package remains intentionally small.
