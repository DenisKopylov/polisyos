import type { Meta, StoryObj } from "@storybook/react-vite";

import { EvidenceSigil } from "./EvidenceSigil";

const meta = {
  title: "Brand/Evidence Sigil",
  component: EvidenceSigil,
  tags: ["autodocs"],
  args: {
    bundleHash: "1a7f3d9b6e2c405aa9d18c0f5e7b63f2",
    size: 64,
  },
  argTypes: {
    bundleHash: { control: { type: "text" } },
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
        "aabbccddeeff0011",
        "112233445566778899",
        "99aabbccddeeff001122",
        "deadbeefcafe00112233",
        "fedcba9876543210fedc",
      ].map((hash) => (
        <EvidenceSigil key={hash} bundleHash={hash} size={64} />
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
