import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { Radio } from "@polisyos/atlas-ui";

const meta = {
  title: "Shared UI/Radio",
  component: Radio,
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Use radios when one option must win and the operator benefits from reading supporting copy before choosing.",
      },
    },
  },
} satisfies Meta<typeof Radio>;

export default meta;

type Story = StoryObj<typeof meta>;

type SourceMode = "registry" | "hybrid" | "manual";

function RadioCardsStory() {
  const [value, setValue] = useState<SourceMode>("hybrid");

  return (
    <div className="grid gap-3 md:grid-cols-3">
      {[
        {
          description: "Strictly use source-backed interventions and evidence.",
          label: "Registry only",
          value: "registry",
        },
        {
          description:
            "Prefer registry data, but allow operator framing inputs.",
          label: "Hybrid compose",
          value: "hybrid",
        },
        {
          description: "Start from analyst framing and enrich later in review.",
          label: "Manual draft",
          value: "manual",
        },
      ].map((option) => (
        <div
          key={option.value}
          className="atlas-choice-card"
          data-selected={value === option.value ? "true" : "false"}
        >
          <Radio
            id={`radio-story-source-${option.value}`}
            name="story-radio-source"
            aria-labelledby={`radio-story-source-${option.value}-label`}
            aria-describedby={`radio-story-source-${option.value}-meta`}
            checked={value === option.value}
            onChange={() => setValue(option.value as SourceMode)}
          />
          <span className="atlas-choice-card__body">
            <span
              id={`radio-story-source-${option.value}-label`}
              className="atlas-choice-card__title"
            >
              {option.label}
            </span>
            <span
              id={`radio-story-source-${option.value}-meta`}
              className="atlas-choice-card__meta"
            >
              {option.description}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

export const Default: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-6">
      <div className="inline-flex items-center gap-3">
        <Radio
          id="radio-story-inline-registry"
          name="story-radio-inline"
          aria-labelledby="radio-story-inline-registry-label"
          defaultChecked
        />
        <span
          id="radio-story-inline-registry-label"
          className="text-sm font-medium"
        >
          Registry only
        </span>
      </div>
      <div className="inline-flex items-center gap-3">
        <Radio
          id="radio-story-inline-hybrid"
          name="story-radio-inline"
          aria-labelledby="radio-story-inline-hybrid-label"
        />
        <span
          id="radio-story-inline-hybrid-label"
          className="text-sm font-medium"
        >
          Hybrid compose
        </span>
      </div>
    </div>
  ),
};

export const ChoiceCards: Story = {
  render: () => <RadioCardsStory />,
  parameters: {
    docs: {
      description: {
        story:
          "Radio cards are the default Atlas treatment for short exclusive choices that need context, such as source mode, execution stage, or model family.",
      },
    },
  },
};
