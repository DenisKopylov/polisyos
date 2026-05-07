import type { Meta, StoryObj } from "@storybook/react-vite";

import { UncertaintyBand } from "./UncertaintyBand";

const meta = {
  title: "Charts/Uncertainty/UncertaintyBand",
  component: UncertaintyBand,
  args: {
    label: "Transport-adjusted fiscal effect",
  },
} satisfies Meta<typeof UncertaintyBand>;

export default meta;

type Story = StoryObj<typeof meta>;

export const ScalarInterval: Story = {
  args: {
    estimate: 0.23,
    bands: [{ lower: 0.09, upper: 0.37, level: 0.95 }],
  },
};

export const IdentifiedSeries: Story = {
  args: {
    data: [
      {
        x: "Q1",
        y: 0.12,
        ci80Lower: 0.08,
        ci80Upper: 0.16,
        ci95Lower: 0.03,
        ci95Upper: 0.2,
      },
      {
        x: "Q2",
        y: 0.18,
        ci80Lower: 0.12,
        ci80Upper: 0.24,
        ci95Lower: 0.07,
        ci95Upper: 0.29,
      },
      {
        x: "Q3",
        y: 0.22,
        ci80Lower: 0.17,
        ci80Upper: 0.27,
        ci95Lower: 0.12,
        ci95Upper: 0.32,
      },
    ],
    identifiability: "identified",
  },
};

export const EstimatedCounterfactual: Story = {
  args: {
    data: [
      {
        x: "Q1",
        y: 0.12,
        ci80Lower: 0.08,
        ci80Upper: 0.16,
        ci95Lower: 0.03,
        ci95Upper: 0.2,
      },
      {
        x: "Q2",
        y: 0.18,
        ci80Lower: 0.12,
        ci80Upper: 0.24,
        ci95Lower: 0.07,
        ci95Upper: 0.29,
      },
      {
        x: "Q3",
        y: 0.22,
        ci80Lower: 0.17,
        ci80Upper: 0.27,
        ci95Lower: 0.12,
        ci95Upper: 0.32,
      },
    ],
    counterfactual: [
      { x: "Q1", y: 0.09 },
      { x: "Q2", y: 0.12 },
      { x: "Q3", y: 0.15 },
    ],
    disputed: true,
    identifiability: "estimated",
  },
};
