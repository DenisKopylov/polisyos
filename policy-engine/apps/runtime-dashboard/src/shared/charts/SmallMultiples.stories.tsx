import type { Meta, StoryObj } from "@storybook/react-vite";

import { SmallMultiples, type SmallMultipleDatum } from "./SmallMultiples";

const regions = [
  "North",
  "South",
  "East",
  "West",
  "Central",
  "Coastal",
  "Industrial",
  "Rural",
];
const sectors = [
  "Health",
  "Education",
  "Energy",
  "Transport",
  "Housing",
  "Labor",
  "SME",
  "Defense",
  "Justice",
  "Climate",
  "Digital",
  "Agriculture",
];

const demoData: SmallMultipleDatum[] = regions.flatMap((region, rowIndex) =>
  sectors.map((sector, columnIndex) => ({
    region,
    sector,
    verification: {
      freshness: columnIndex % 5 === 0 ? "stale" : "current",
      verification_status: columnIndex % 5 === 0 ? "pending" : "verified",
    } as const,
    value: Math.round((rowIndex + 1) * (columnIndex + 2) * 1.7),
  })),
);

const meta = {
  component: SmallMultiples,
  title: "Charts/SmallMultiples",
} satisfies Meta<typeof SmallMultiples>;

export default meta;

type Story = StoryObj<typeof meta>;

export const RegionalSectorScan: Story = {
  args: {
    data: demoData,
    selectedRegion: "Central",
    selectedSector: "Energy",
    valueDomain: [0, 180],
    valueLabel: "policy impact",
  },
};
