import type { Meta, StoryObj } from "@storybook/react-vite";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { Quantity } from "./Quantity";
import type { QuantityValue } from "./quantity.types";

const storybookQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

const baseQuantity: QuantityValue = {
  point: 0.23456,
  unit: { code: "1", system: "ucum", display: "ratio" },
  metric_id: "employment_rate_delta",
  lineage: {
    id: "artifact:sha256:fixture",
    status: "verified",
    freshness: "current",
    summary: { source: "QES 2024 Q3" },
    compact_summary: [
      { kind: "source", label: "QES 2024 Q3" },
      { kind: "model", label: "DoubleML v2.1" },
      { kind: "result", label: "employment_rate_delta" },
    ],
  },
  uncertainty: {
    ci_95: [0.15, 0.31],
    method: "bootstrap",
    identifiability: "estimated",
    disputed: false,
  },
  time: {
    valid_at: "2026-04-15T12:00:00Z",
    tx_at: "2026-04-16T09:20:00Z",
  },
  quantity_class: "decision",
  label: "Employment delta",
};

const meta = {
  title: "Shared UI/Quantity",
  component: Quantity,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <QueryClientProvider client={storybookQueryClient}>
        <Story />
      </QueryClientProvider>
    ),
  ],
  args: {
    value: baseQuantity,
    precision: 3,
  },
} satisfies Meta<{
  precision?: number;
  value: QuantityValue;
}>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Verified: Story = {};

export const States: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Quantity value={baseQuantity} />
      <Quantity
        value={{
          ...baseQuantity,
          lineage: { ...baseQuantity.lineage, status: "pending" },
        }}
      />
      <Quantity
        value={{
          ...baseQuantity,
          uncertainty: {
            ...baseQuantity.uncertainty,
            disputed: true,
            identifiability:
              baseQuantity.uncertainty?.identifiability ?? "unknown",
          },
        }}
      />
      <Quantity
        value={{
          ...baseQuantity,
          lineage: {
            id: "untraced",
            status: "untraced",
            freshness: "unknown",
            reason_code: "fixture_without_lineage",
            tracking_issue: "POLICYOS-QUANTITY-0",
          },
        }}
      />
    </div>
  ),
};
