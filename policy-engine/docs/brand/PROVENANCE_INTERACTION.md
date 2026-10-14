# Provenance Interaction

Freshness: 2026-04-24.
Owner: `@runtime-dashboard-owners`
Source of truth:
`src/polisyos/core/contracts/runtime.py`,
`apps/runtime-dashboard/src/shared/ui/quantity/Quantity.tsx`

This is an interaction contract, not a claim that every decision-bearing value
is wired through the component or that the interaction has passed browser or
deployment review. The current code path inspected at
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb` is mapped in the
[current frontend surface map](../reference/frontend/current-surface-map.md).
Its component and API tests were inspected but not run for this documentation
pass. A `verified` lineage status is a bounded verification projection; it is
not policy correctness, current policy authority, or publication approval.

Provenance is not a decorative hover. It is the way PolicyOS lets a reader
trust a quantitative claim without leaving the decision context.

## Law

When a decision-bearing number is rendered through `<Quantity />`, the design
requires a complete `QuantityValue` envelope. The interaction has three
layers:

| Layer     | Trigger                         | Payload                                             |
| --------- | ------------------------------- | --------------------------------------------------- |
| Inline    | Always visible                  | Value, unit, verification status, dispute/freshness |
| Popover   | Hover, focus, or keyboard open  | Compact lineage summary and uncertainty             |
| Deep dive | Explicit inspect/open action    | Full lineage graph, exports, related artifacts      |

The phase labels in this document are retained planning history; they are not
current acceptance receipts. The pinned source map identifies the implemented
`Quantity`, lineage bridge, and current test references without claiming that
every decision-bearing number uses this path.

## Inline Rules

- The value and unit are always adjacent.
- Verification state is machine-readable through `data-lineage-status`.
- Untraced values are visually distinct and remain keyboard-addressable.
- The component accepts one `QuantityValue` prop. It must not accept detached
  `value`, `unit`, and `lineageId` props.

## Popover Rules

- The popover opens from the value itself, not from a separate help icon.
- Compact summaries are ordered source to result where possible.
- Uncertainty and freshness are shown before the graph link.
- Full graph loading is lazy and cancellable.

## Deep-Dive Rules

- Full graph views use `/api/v1/lineage/{lineage_id}`.
- Batch prefetch uses `/api/v1/lineage/batch` for visible tables.
- External interoperability uses the OpenLineage and PROV export links returned
  with the graph.

## Accessibility

- Hover-only provenance is forbidden.
- Keyboard focus must reveal the same compact provenance available on hover.
- Screen-reader labels use the formatted value, unit, and lineage status.
- Disputed or untraced values must be announced through status text or an
  equivalent accessible label.
