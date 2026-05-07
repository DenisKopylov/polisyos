import type { Meta, StoryObj } from "@storybook/react-vite";

import { FanChart } from "./FanChart";

const meta = {
  title: "Charts/Uncertainty/FanChart",
  component: FanChart,
  args: {
    label: "Employment rate forecast",
    data: [
      { x: "Now", p10: 51.2, p25: 52.4, p50: 53.2, p75: 54.1, p90: 55.6 },
      { x: "+6m", p10: 50.7, p25: 52.0, p50: 53.0, p75: 54.7, p90: 56.3 },
      { x: "+12m", p10: 50.2, p25: 51.7, p50: 53.4, p75: 55.1, p90: 57.0 },
      { x: "+18m", p10: 49.9, p25: 51.4, p50: 53.8, p75: 55.5, p90: 57.7 },
    ],
  },
} satisfies Meta<typeof FanChart>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Identified: Story = {};

export const Assumed: Story = {
  args: {
    identifiability: "assumed",
    disputed: true,
  },
};
