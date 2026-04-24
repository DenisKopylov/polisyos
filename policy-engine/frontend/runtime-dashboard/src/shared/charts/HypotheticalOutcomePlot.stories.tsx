import type { Meta, StoryObj } from "@storybook/react-vite";

import { HypotheticalOutcomePlot } from "./HypotheticalOutcomePlot";

const meta = {
  title: "Charts/Uncertainty/HypotheticalOutcomePlot",
  component: HypotheticalOutcomePlot,
  args: {
    label: "Counterfactual outcome realizations",
    samples: [
      {
        id: "sample-a",
        points: [
          { x: "Q1", y: 10 },
          { x: "Q2", y: 12 },
          { x: "Q3", y: 13 },
          { x: "Q4", y: 15 },
        ],
      },
      {
        id: "sample-b",
        points: [
          { x: "Q1", y: 9 },
          { x: "Q2", y: 11 },
          { x: "Q3", y: 14 },
          { x: "Q4", y: 16 },
        ],
      },
      {
        id: "sample-c",
        points: [
          { x: "Q1", y: 11 },
          { x: "Q2", y: 12 },
          { x: "Q3", y: 12.5 },
          { x: "Q4", y: 14.5 },
        ],
      },
    ],
  },
} satisfies Meta<typeof HypotheticalOutcomePlot>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Animated: Story = {};

export const QuantileFallback: Story = {
  args: {
    reducedMotionFallback: "quantile-dotplot",
    disputed: true,
  },
};
