import type { Meta, StoryObj } from "@storybook/react-vite";
import type { VerificationMetadata } from "@polisyos/runtime-api-client";

import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";

import { ProvenanceStrip } from "./ProvenanceStrip";

const comfortableItems: ProvenanceItem[] = [
  { id: "freshness", glyph: "freshness", label: "Fresh" },
  {
    id: "governance",
    glyph: "governance-pass",
    label: "Governance pass",
  },
  {
    id: "evidence",
    glyph: "evidence",
    label: "Strong evidence",
  },
  {
    id: "intervention",
    glyph: "intervention",
    label: "policy-action",
  },
];

const verifiedMetadata = {
  dispute_status: "none",
  freshness: "current",
  verification_method: "content_hash",
  verification_status: "verified",
  verified_at: "2026-07-31T10:00:00Z",
  verified_by: "runtime-verifier",
} satisfies VerificationMetadata;

const compactItems: ProvenanceItem[] = [
  {
    id: "freshness",
    glyph: "freshness",
    label: "Fresh",
    trustMetadata: verifiedMetadata,
  },
  {
    id: "governance",
    glyph: "governance-pass",
    label: "Governance pass",
    trustMetadata: verifiedMetadata,
  },
  {
    id: "evidence",
    glyph: "evidence",
    label: "Verified evidence",
    trustMetadata: verifiedMetadata,
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

export const GeneratedVerificationMetadata: Story = {
  args: { items: compactItems, density: "compact", title: "Provenance" },
};

export const DualDensity: Story = {
  render: () => (
    <div className="space-y-3">
      <ProvenanceStrip
        items={comfortableItems}
        title="No verification metadata"
        density="comfortable"
      />
      <ProvenanceStrip
        items={compactItems}
        title="Generated verification metadata"
        density="compact"
      />
    </div>
  ),
};
