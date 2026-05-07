import type { Meta, StoryObj } from "@storybook/react-vite";

import { Select } from "@/shared/ui/Select";

const meta = {
  title: "Shared UI/Select",
  component: Select,
  tags: ["autodocs"],
} satisfies Meta<typeof Select>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => (
    <Select defaultValue="running">
      <option value="">All statuses</option>
      <option value="running">running</option>
      <option value="completed">completed</option>
      <option value="fail">fail</option>
    </Select>
  ),
};
