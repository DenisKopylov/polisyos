import type { Meta, StoryObj } from "@storybook/react-vite";

import { Textarea } from "@/shared/ui/Textarea";

const meta = {
  title: "Shared UI/Textarea",
  component: Textarea,
  tags: ["autodocs"],
  args: {
    placeholder: "Describe the scenario, guardrails, and decision framing",
    rows: 4,
  },
} satisfies Meta<typeof Textarea>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Filled: Story = {
  args: {
    defaultValue:
      "Evaluate food price controls against inflation, household welfare, and supply reliability.",
  },
};
