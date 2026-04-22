import type { Meta, StoryObj } from "@storybook/react-vite";

import { Glyph } from "./Glyph";
import { GLYPH_NAMES } from "./glyph-vocabulary";

const meta = {
  title: "Brand/Glyphs",
  component: Glyph,
  tags: ["autodocs"],
  args: {
    name: "intervention",
    size: 24,
    intent: "default",
    strokeStyle: "solid",
  },
  argTypes: {
    name: { control: { type: "select" }, options: GLYPH_NAMES },
    size: { control: { type: "inline-radio" }, options: [12, 14, 16, 24] },
    intent: {
      control: { type: "inline-radio" },
      options: ["default", "verified", "blocked", "pending"],
    },
    strokeStyle: {
      control: { type: "inline-radio" },
      options: ["solid", "dashed", "double"],
    },
    diacritic: {
      control: { type: "inline-radio" },
      options: [undefined, "strict", "assumed", "scoped"],
    },
  },
} satisfies Meta<typeof Glyph>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const AllRadicalsAtEverySize: Story = {
  render: () => (
    <div className="space-y-4">
      {([12, 14, 16, 24] as const).map((size) => (
        <div key={size} className="flex items-center gap-4">
          <span className="w-10 font-mono text-xs">{size}px</span>
          {GLYPH_NAMES.map((name) => (
            <Glyph key={name} name={name} size={size} title={name} />
          ))}
        </div>
      ))}
    </div>
  ),
};

export const IntentPalette: Story = {
  render: () => (
    <div className="grid grid-cols-5 items-center gap-4">
      {(["default", "verified", "blocked", "pending"] as const).map((intent) =>
        GLYPH_NAMES.map((name) => (
          <Glyph key={`${intent}-${name}`} name={name} intent={intent} size={24} />
        )),
      )}
    </div>
  ),
};

export const StrokeStyles: Story = {
  render: () => (
    <div className="flex items-center gap-4">
      <Glyph name="evidence" strokeStyle="solid" size={24} />
      <Glyph name="evidence" strokeStyle="dashed" size={24} />
      <Glyph name="evidence" strokeStyle="double" size={24} />
    </div>
  ),
};
