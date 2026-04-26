export const counterfactualTokens = {
  actual: {
    className: "border-border bg-background text-foreground",
    lineClassName: "border-solid border-foreground",
  },
  scenario: {
    className:
      "border-[color-mix(in_srgb,var(--chart-info)_36%,transparent)] bg-[color-mix(in_srgb,var(--chart-info)_10%,transparent)] text-foreground",
    lineClassName: "border-dashed border-[var(--chart-info)]",
  },
  delta: {
    className:
      "border-[color-mix(in_srgb,var(--chart-warning)_34%,transparent)] bg-[color-mix(in_srgb,var(--chart-warning)_9%,transparent)] text-foreground",
    lineClassName: "border-dotted border-[var(--chart-warning)]",
  },
  stale: {
    className:
      "border-[color-mix(in_srgb,var(--color-status-pending)_34%,transparent)] bg-[color-mix(in_srgb,var(--color-status-pending)_10%,transparent)] text-foreground",
    lineClassName: "border-dashed border-[var(--color-status-pending)]",
  },
} as const;
