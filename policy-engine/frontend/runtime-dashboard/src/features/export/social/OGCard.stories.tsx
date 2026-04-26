import type { Meta, StoryObj } from "@storybook/react-vite";

import { runShareFixture, scenarioShareFixture } from "./email-fixtures";
import { OGCard } from "./OGCard";

const meta = {
  component: OGCard,
  title: "Export/Social/OGCard",
} satisfies Meta<typeof OGCard>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Run: Story = {
  args: {
    summary: runShareFixture,
  },
};

export const Scenario: Story = {
  args: {
    summary: scenarioShareFixture,
  },
};
