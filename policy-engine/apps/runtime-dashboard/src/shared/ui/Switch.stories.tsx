import { useId, useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { Switch } from "@/shared/ui/Switch";

const meta = {
  title: "Shared UI/Switch",
  component: Switch,
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Use switches for immediate binary preferences or live system behaviors that take effect as soon as the control flips.",
      },
    },
  },
} satisfies Meta<typeof Switch>;

export default meta;

type Story = StoryObj<typeof meta>;

function SwitchRowStory() {
  const [checked, setChecked] = useState(true);
  const labelId = useId();
  const descriptionId = useId();

  return (
    <div
      className="atlas-toggle-row"
      data-selected={checked ? "true" : "false"}
    >
      <div className="atlas-toggle-row__body">
        <span id={labelId} className="atlas-toggle-row__title">
          Allow explore fallback
        </span>
        <span id={descriptionId} className="atlas-toggle-row__meta">
          Let Atlas pull adjacent sources when the primary connector graph has
          low coverage.
        </span>
      </div>
      <Switch
        checked={checked}
        onCheckedChange={setChecked}
        aria-labelledby={labelId}
        aria-describedby={descriptionId}
      />
    </div>
  );
}

export const Default: Story = {
  render: () => <SwitchRowStory />,
};

export const Disabled: Story = {
  render: () => {
    const labelId = "switch-story-disabled-label";
    const descriptionId = "switch-story-disabled-description";

    return (
      <div className="atlas-toggle-row" data-selected="false">
        <div className="atlas-toggle-row__body">
          <span id={labelId} className="atlas-toggle-row__title">
            Auto-promote evidence
          </span>
          <span id={descriptionId} className="atlas-toggle-row__meta">
            Locked until governance policy checks are complete.
          </span>
        </div>
        <Switch
          disabled
          aria-labelledby={labelId}
          aria-describedby={descriptionId}
        />
      </div>
    );
  },
  parameters: {
    docs: {
      description: {
        story:
          "Keep disabled switch rows explicit about why the behavior is unavailable; avoid silent lockouts.",
      },
    },
  },
};
