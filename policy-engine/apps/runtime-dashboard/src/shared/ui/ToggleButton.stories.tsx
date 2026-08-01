import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { BookOpenText, ScanSearch } from "lucide-react";
import { expect, userEvent, within } from "storybook/test";

import { ToggleButton } from "@polisyos/atlas-ui";

const meta = {
  title: "Shared UI/ToggleButton",
  component: ToggleButton,
  tags: ["autodocs"],
  args: {
    label: "Reading view",
    onPressedChange: () => undefined,
    pressed: false,
  },
  parameters: {
    docs: {
      description: {
        component:
          "Use toggle buttons for a single explicit mode flip, especially in toolbars and inspectors where the label must stay visible in both states.",
      },
    },
  },
} satisfies Meta<typeof ToggleButton>;

export default meta;

type Story = StoryObj<typeof meta>;

function ReadingViewStory() {
  const [pressed, setPressed] = useState(false);

  return (
    <ToggleButton
      icon={<BookOpenText size={16} />}
      label="Reading view"
      pressed={pressed}
      onPressedChange={setPressed}
      trailing={
        <span className="rounded-full border border-current/20 px-1.5 py-0.5 text-[0.62rem] leading-none opacity-80">
          R
        </span>
      }
    />
  );
}

function RailToolbarStory() {
  const [pressed, setPressed] = useState(true);

  return (
    <div className="max-w-sm rounded-[28px] border border-white/10 bg-[#131920] p-5 text-[#f6eee0] shadow-[0_24px_80px_rgba(7,8,10,0.45)]">
      <ToggleButton
        tone="rail"
        size="sm"
        icon={<ScanSearch size={16} />}
        label="Uncertainty bounds"
        pressed={pressed}
        onPressedChange={setPressed}
      />
    </div>
  );
}

export const Default: Story = {
  render: () => <ReadingViewStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const button = canvas.getByRole("button", { name: /reading view/i });

    await expect(button).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(button);
    await expect(button).toHaveAttribute("aria-pressed", "true");
  },
  parameters: {
    docs: {
      description: {
        story:
          "Default toolbar treatment for one-off modes such as reading view, uncertainty overlays, or inspection affordances.",
      },
    },
  },
};

export const RailCompact: Story = {
  render: () => <RailToolbarStory />,
  parameters: {
    docs: {
      description: {
        story:
          "Rail variant for compact shells where the control should inherit dark chrome while staying obviously active or inactive.",
      },
    },
  },
};
