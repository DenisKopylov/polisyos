import type { Meta, StoryObj } from "@storybook/react-vite";

import { QuantileDotplot } from "./QuantileDotplot";

const meta = {
  title: "Charts/Uncertainty/QuantileDotplot",
  component: QuantileDotplot,
  args: {
    label: "VAT multiplier distribution",
    samples: [
      0.09, 0.11, 0.14, 0.16, 0.18, 0.19, 0.2, 0.21, 0.21, 0.22, 0.22, 0.22,
      0.23, 0.23, 0.23, 0.23, 0.24, 0.24, 0.24, 0.24, 0.25, 0.25, 0.25, 0.26,
      0.26, 0.27, 0.27, 0.28, 0.29, 0.31, 0.33, 0.35, 0.37,
    ],
  },
} satisfies Meta<typeof QuantileDotplot>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Horizontal: Story = {};

export const Vertical: Story = {
  args: {
    orientation: "vertical",
  },
};
