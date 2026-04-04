import type { Meta, StoryObj } from "@storybook/react-vite";

import { Card } from "@/shared/ui/Card";
import { MetricCard } from "@/shared/ui/MetricCard";

const meta = {
  title: "Shared UI/Card",
  component: Card,
  tags: ["autodocs"],
} satisfies Meta<typeof Card>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => (
    <Card className="space-y-3">
      <p className="eyebrow">Runtime posture</p>
      <h3>Operator queue stays audit-first</h3>
      <p className="text-muted text-sm">
        Atlas surfaces only current runtime signals and leaves provenance
        intact.
      </p>
    </Card>
  ),
};

export const MetricsGrid: Story = {
  render: () => (
    <div className="grid gap-4 md:grid-cols-3">
      <MetricCard
        label="Decision score"
        value="0.82"
        meta="Approve with conditions"
      />
      <MetricCard label="Blockers" value="2" meta="Legal transport waiting" />
      <MetricCard label="Artifacts" value="14" meta="5 decision-linked refs" />
    </div>
  ),
};
