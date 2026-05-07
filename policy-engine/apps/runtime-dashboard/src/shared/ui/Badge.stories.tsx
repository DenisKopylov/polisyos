import type { Meta, StoryObj } from "@storybook/react-vite";

import { Badge } from "@/shared/ui/Badge";

const meta = {
  title: "Shared UI/Badge",
  component: Badge,
  tags: ["autodocs"],
  args: {
    children: "Running",
    kind: "warn",
  },
} satisfies Meta<typeof Badge>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const AllKinds: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <Badge kind="ok">OK</Badge>
      <Badge kind="warn">Warn</Badge>
      <Badge kind="fail">Fail</Badge>
      <Badge kind="info">Live</Badge>
      <Badge kind="neutral">Neutral</Badge>
    </div>
  ),
};
