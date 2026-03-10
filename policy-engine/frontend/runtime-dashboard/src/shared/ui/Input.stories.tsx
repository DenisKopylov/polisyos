import type { Meta, StoryObj } from "@storybook/react-vite";

import { Input } from "@/shared/ui/Input";

const meta = {
  title: "Shared UI/Input",
  component: Input,
  tags: ["autodocs"],
  args: {
    placeholder: "Search run_id or artifact id",
    defaultValue: "",
  },
} satisfies Meta<typeof Input>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Filled: Story = {
  args: {
    defaultValue: "run-2026-03-09-14",
  },
};
