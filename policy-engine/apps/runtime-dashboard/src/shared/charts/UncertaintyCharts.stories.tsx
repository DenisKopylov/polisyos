import { useEffect, type ReactNode } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { Card } from "@polisyos/atlas-ui";
import { FanChart } from "./FanChart";
import { QuantileDotplot } from "./QuantileDotplot";
import { UncertaintyBand } from "./UncertaintyBand";
import type {
  ConfidenceInterval,
  QuantileSeriesPoint,
  TimeSeriesDataPoint,
} from "./types";

const bandSeries: TimeSeriesDataPoint[] = [
  {
    x: "Q1",
    y: 0.12,
    ci50Lower: 0.08,
    ci50Upper: 0.16,
    ci80Lower: 0.03,
    ci80Upper: 0.2,
    ci95Lower: -0.02,
    ci95Upper: 0.24,
  },
  {
    x: "Q2",
    y: 0.18,
    ci50Lower: 0.12,
    ci50Upper: 0.22,
    ci80Lower: 0.07,
    ci80Upper: 0.28,
    ci95Lower: 0.02,
    ci95Upper: 0.33,
  },
  {
    x: "Q3",
    y: 0.23,
    ci50Lower: 0.18,
    ci50Upper: 0.27,
    ci80Lower: 0.13,
    ci80Upper: 0.31,
    ci95Lower: 0.08,
    ci95Upper: 0.36,
  },
  {
    x: "Q4",
    y: 0.27,
    ci50Lower: 0.21,
    ci50Upper: 0.31,
    ci80Lower: 0.16,
    ci80Upper: 0.36,
    ci95Lower: 0.11,
    ci95Upper: 0.42,
  },
];

const scalarBands: ConfidenceInterval[] = [
  { lower: 0.09, upper: 0.37, level: 0.95 },
];

const forecastSeries: QuantileSeriesPoint[] = [
  { x: "Now", p10: 51.2, p25: 52.4, p50: 53.2, p75: 54.1, p90: 55.6 },
  { x: "+6m", p10: 50.7, p25: 52.0, p50: 53.0, p75: 54.7, p90: 56.3 },
  { x: "+12m", p10: 50.2, p25: 51.7, p50: 53.4, p75: 55.1, p90: 57.0 },
  { x: "+18m", p10: 49.9, p25: 51.4, p50: 53.8, p75: 55.5, p90: 57.7 },
];

const multiplierSamples = [
  0.09, 0.11, 0.14, 0.16, 0.18, 0.19, 0.2, 0.21, 0.21, 0.22, 0.22, 0.22, 0.23,
  0.23, 0.23, 0.23, 0.24, 0.24, 0.24, 0.24, 0.25, 0.25, 0.25, 0.26, 0.26, 0.27,
  0.27, 0.28, 0.29, 0.31, 0.33, 0.35, 0.37,
];

function ThemeDecorator({
  children,
  theme,
}: {
  children: ReactNode;
  theme: "dark" | "light";
}) {
  useEffect(() => {
    const previousTheme = document.documentElement.dataset.theme;
    document.documentElement.dataset.theme = theme;
    return () => {
      if (previousTheme) {
        document.documentElement.dataset.theme = previousTheme;
        return;
      }
      delete document.documentElement.dataset.theme;
    };
  }, [theme]);

  return <>{children}</>;
}

const meta = {
  title: "Design System/Uncertainty",
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Uncertainty primitives for atlas-style policy interpretation. These components cover scalar intervals, time-based envelopes, forecast fans, and frequency-framed sample distributions.",
      },
    },
  },
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

export const AtlasPreview: Story = {
  render: () => (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="space-y-4">
        <UncertaintyBand
          estimate={0.23}
          bands={scalarBands}
          label="GDP effect"
          unit="%"
        />
        <UncertaintyBand
          data={bandSeries}
          label="Transport-adjusted fiscal effect"
          asOfIndex={1}
          identifiability="estimated"
        />
      </Card>
      <Card className="space-y-4">
        <FanChart
          data={forecastSeries}
          label="Employment rate forecast"
          asOfIndex={1}
          identifiability="assumed"
        />
        <QuantileDotplot
          samples={multiplierSamples}
          label="VAT multiplier distribution"
        />
      </Card>
    </div>
  ),
};

export const DarkTheme: Story = {
  decorators: [
    (Story) => (
      <ThemeDecorator theme="dark">
        <Story />
      </ThemeDecorator>
    ),
  ],
  render: () => (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="space-y-4">
        <UncertaintyBand
          data={bandSeries}
          label="Disputed transport effect"
          asOfIndex={1}
          disputed
        />
      </Card>
      <Card className="space-y-4">
        <FanChart data={forecastSeries} label="Dark-theme fan chart" disputed />
      </Card>
    </div>
  ),
};
