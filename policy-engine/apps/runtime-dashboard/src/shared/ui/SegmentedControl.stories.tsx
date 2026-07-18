import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";
import {
  ChartColumnBig,
  LaptopMinimal,
  MoonStar,
  SunMedium,
} from "lucide-react";
import { expect, userEvent, within } from "storybook/test";

import { SegmentedControl } from "@polisyos/atlas-ui";

const WORKSPACE_OPTIONS = [
  {
    description: "Queue health, source coverage, and governance signals.",
    label: "Command center",
    value: "command",
  },
  {
    description: "Problem framing, interventions, and constraints.",
    label: "Scenario composer",
    value: "scenario",
  },
  {
    description: "Narrative rationale, impact bands, and uncertainty.",
    label: "Decision workspace",
    value: "decision",
  },
] as const;

type WorkspaceSurface = (typeof WORKSPACE_OPTIONS)[number]["value"];

const THEME_OPTIONS = [
  {
    icon: <SunMedium size={16} />,
    label: "Light",
    value: "light",
  },
  {
    icon: <MoonStar size={16} />,
    label: "Dark",
    value: "dark",
  },
  {
    icon: <LaptopMinimal size={16} />,
    label: "System",
    value: "system",
  },
] as const;

type ThemeMode = (typeof THEME_OPTIONS)[number]["value"];

const meta = {
  title: "Shared UI/SegmentedControl",
  component: SegmentedControl,
  tags: ["autodocs"],
  args: {
    ariaLabel: "Segmented control",
    onValueChange: () => undefined,
    options: WORKSPACE_OPTIONS,
    value: "scenario",
  },
  parameters: {
    docs: {
      description: {
        component:
          "Use segmented controls for small mutually exclusive sets that operators should compare at a glance, such as workspace mode, density, or theme.",
      },
    },
  },
} satisfies Meta<typeof SegmentedControl>;

export default meta;

type Story = StoryObj<typeof meta>;

function WorkspaceModesStory() {
  const [value, setValue] = useState<WorkspaceSurface>("scenario");

  return (
    <SegmentedControl
      ariaLabel="Primary workspace surface"
      className="xl:grid-cols-3"
      value={value}
      onValueChange={setValue}
      options={WORKSPACE_OPTIONS}
    />
  );
}

function RailThemeStory() {
  const [value, setValue] = useState<ThemeMode>("system");

  return (
    <div className="max-w-xl rounded-[28px] border border-white/10 bg-[#131920] p-5 text-[#f6eee0] shadow-[0_24px_80px_rgba(7,8,10,0.45)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-[0.68rem] font-semibold tracking-[0.18em] text-white/55 uppercase">
            Rail variant
          </p>
          <h3 className="mt-1 text-base font-semibold">Shell appearance</h3>
        </div>
        <ChartColumnBig size={18} className="text-white/55" />
      </div>
      <SegmentedControl
        ariaLabel="Theme preference"
        className="grid-cols-3"
        tone="rail"
        size="sm"
        value={value}
        onValueChange={setValue}
        options={THEME_OPTIONS}
      />
    </div>
  );
}

export const WorkspaceModes: Story = {
  render: () => <WorkspaceModesStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const decisionLabel = canvas.getByText("Decision workspace");
    const decisionRadio = canvas.getByRole("radio", {
      name: /decision workspace/i,
    });

    await userEvent.click(decisionLabel);
    await expect(decisionRadio).toBeChecked();
  },
  parameters: {
    docs: {
      description: {
        story:
          "Primary story for mode switching when all options should stay visible. Use this over radios when the set is compact and the current choice should read like a workspace tab.",
      },
    },
  },
};

export const RailCompact: Story = {
  render: () => <RailThemeStory />,
  parameters: {
    docs: {
      description: {
        story:
          "Dark-rail variant for sidebars, command chrome, and compact settings clusters.",
      },
    },
  },
};
