import type { Meta, StoryObj } from "@storybook/react-vite";

import { AtlasBrand } from "./AtlasBrand";

const meta = {
  title: "Brand/Atlas",
  component: AtlasBrand,
  tags: ["autodocs"],
  args: {
    size: 32,
    variant: "mark",
    inverted: false,
  },
  argTypes: {
    size: { control: { type: "inline-radio" }, options: [16, 24, 32, 48] },
    variant: {
      control: { type: "inline-radio" },
      options: ["mark", "lockup"],
    },
    inverted: { control: { type: "boolean" } },
  },
} satisfies Meta<typeof AtlasBrand>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const MarksAtAllSizes: Story = {
  render: () => (
    <div className="flex items-end gap-6">
      <AtlasBrand size={16} variant="mark" />
      <AtlasBrand size={24} variant="mark" />
      <AtlasBrand size={32} variant="mark" />
      <AtlasBrand size={48} variant="mark" />
    </div>
  ),
};

export const Lockups: Story = {
  render: () => (
    <div className="space-y-6">
      <AtlasBrand size={184} variant="lockup" />
      <div className="rounded-lg bg-black p-6">
        <AtlasBrand inverted size={184} variant="lockup" />
      </div>
    </div>
  ),
};
