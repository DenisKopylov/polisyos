import type { Meta, StoryObj } from "@storybook/react-vite";

import JsonPreview from "@/shared/ui/JsonPreview";

const meta = {
  title: "Shared UI/JsonPreview",
  component: JsonPreview,
  tags: ["autodocs"],
  args: {
    data: {
      verdict: "APPROVE_WITH_CONDITIONS",
      blockers: 1,
      transport: {
        status: "legal_review",
        channel: "governance.transport",
      },
    },
  },
} satisfies Meta<typeof JsonPreview>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Empty: Story = {
  args: {
    data: undefined,
  },
};
