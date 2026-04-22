import type { Meta, StoryObj } from "@storybook/react-vite";

import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";

import { ProvenanceStrip } from "./ProvenanceStrip";

const comfortableItems: ProvenanceItem[] = [
  { id: "freshness", glyph: "freshness", label: "Fresh", intent: "verified" },
  {
    id: "governance",
    glyph: "governance-pass",
    label: "Governance pass",
    intent: "verified",
  },
  {
    id: "evidence",
    glyph: "evidence",
    label: "Strong evidence",
    intent: "verified",
  },
  {
    id: "intervention",
    glyph: "intervention",
    label: "policy-action",
  },
];

const compactItems: ProvenanceItem[] = [
  { id: "freshness", glyph: "freshness", label: "Stale", intent: "blocked" },
  {
    id: "governance",
    glyph: "blocker",
    label: "Governance blocked",
    intent: "blocked",
  },
  {
    id: "evidence",
    glyph: "evidence",
    label: "Weak evidence",
    intent: "pending",
    strokeStyle: "dashed",
  },
];

const meta = {
  title: "Brand/Provenance Strip",
  component: ProvenanceStrip,
  tags: ["autodocs"],
  args: {
    items: comfortableItems,
    title: "Provenance",
    density: "comfortable",
  },
  argTypes: {
    density: {
      control: { type: "inline-radio" },
      options: ["comfortable", "compact"],
    },
  },
} satisfies Meta<typeof ProvenanceStrip>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Compact: Story = {
  args: { items: compactItems, density: "compact", title: "Provenance" },
};

export const DualDensity: Story = {
  render: () => (
    <div className="space-y-3">
      <ProvenanceStrip
        items={comfortableItems}
        title="Comfortable"
        density="comfortable"
      />
      <ProvenanceStrip items={compactItems} title="Compact" density="compact" />
    </div>
  ),
};
