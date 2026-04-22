import type { Meta, StoryObj } from "@storybook/react-vite";

import { EvidenceSigil } from "./EvidenceSigil";

const meta = {
  title: "Brand/Evidence Sigil",
  component: EvidenceSigil,
  tags: ["autodocs"],
  args: {
    bundleHash: "1a7f3d9b6e2c405aa9d18c0f5e7b63f2",
    frescProfile: "corroborated",
    identifiability: 0.72,
    size: 64,
  },
  argTypes: {
    bundleHash: { control: { type: "text" } },
    frescProfile: {
      control: { type: "inline-radio" },
      options: [
        "unclassified",
        "reconnaissance",
        "corroborated",
        "replicated",
        "canonical",
      ],
    },
    identifiability: {
      control: { type: "range", min: 0, max: 1, step: 0.05 },
    },
    size: { control: { type: "inline-radio" }, options: [48, 64, 96] },
  },
} satisfies Meta<typeof EvidenceSigil>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Spectrum: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-6">
      {[
        ["unclassified", 0.1, "aabbccddeeff0011"],
        ["reconnaissance", 0.3, "112233445566778899"],
        ["corroborated", 0.55, "99aabbccddeeff001122"],
        ["replicated", 0.78, "deadbeefcafe00112233"],
        ["canonical", 0.95, "fedcba9876543210fedc"],
      ].map(([profile, id, hash]) => (
        <EvidenceSigil
          key={String(profile)}
          bundleHash={String(hash)}
          frescProfile={profile as never}
          identifiability={Number(id)}
          size={64}
        />
      ))}
    </div>
  ),
};

export const Sizes: Story = {
  render: () => (
    <div className="flex items-end gap-6">
      <EvidenceSigil bundleHash="deadbeefcafef00d" size={48} />
      <EvidenceSigil bundleHash="deadbeefcafef00d" size={64} />
      <EvidenceSigil bundleHash="deadbeefcafef00d" size={96} />
    </div>
  ),
};
