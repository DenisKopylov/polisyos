import type { Meta, StoryObj } from "@storybook/react-vite";

import { JanusGlyph } from "./JanusGlyph";

const meta = {
  title: "Brand/Janus",
  component: JanusGlyph,
  tags: ["autodocs"],
  args: {
    size: 24,
    variant: "mark",
    intent: "default",
  },
  argTypes: {
    size: { control: { type: "inline-radio" }, options: [16, 24, 32] },
    variant: {
      control: { type: "inline-radio" },
      options: ["mark", "line", "serif-punctuation"],
    },
    intent: {
      control: { type: "inline-radio" },
      options: ["default", "verified", "blocked", "pending"],
    },
  },
} satisfies Meta<typeof JanusGlyph>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Variants: Story = {
  render: () => (
    <div className="flex items-center gap-6">
      <JanusGlyph variant="mark" size={32} />
      <JanusGlyph variant="line" size={24} />
      <JanusGlyph variant="serif-punctuation" size={16} />
    </div>
  ),
};

export const Sizes: Story = {
  render: () => (
    <div className="flex items-end gap-6">
      <JanusGlyph variant="mark" size={16} />
      <JanusGlyph variant="mark" size={24} />
      <JanusGlyph variant="mark" size={32} />
    </div>
  ),
};

export const Inverted: Story = {
  render: () => (
    <div className="flex items-center gap-6 rounded-lg bg-black p-6">
      <JanusGlyph variant="mark" size={32} inverted />
      <JanusGlyph variant="line" size={24} inverted />
    </div>
  ),
};
