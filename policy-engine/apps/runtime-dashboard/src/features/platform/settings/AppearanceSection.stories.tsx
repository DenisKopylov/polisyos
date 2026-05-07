import type { Meta, StoryObj } from "@storybook/react-vite";

import { AppearanceSection } from "./AppearanceSection";

const meta = {
  title: "Features/Platform/AppearanceSection",
  component: AppearanceSection,
  parameters: {
    layout: "padded",
  },
} satisfies Meta<typeof AppearanceSection>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};
