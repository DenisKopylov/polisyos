import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  MetricsSkeleton,
  PageSkeleton,
  PanelSkeleton,
} from "@/shared/ui/Skeleton";

const meta = {
  title: "Shared UI/Skeleton",
  component: PanelSkeleton,
  tags: ["autodocs"],
} satisfies Meta<typeof PanelSkeleton>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Panel: Story = {
  render: () => <PanelSkeleton rows={5} />,
};

export const Page: Story = {
  render: () => <PageSkeleton />,
};

export const Metrics: Story = {
  render: () => <MetricsSkeleton count={4} />,
};
