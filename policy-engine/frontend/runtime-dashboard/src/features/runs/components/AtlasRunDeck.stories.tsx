import { useEffect } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  AtlasRunDeck,
  DEFAULT_ATLAS_RUN_DECK_COPY,
} from "@/features/runs/components/AtlasRunDeck";
import { ATLAS_STANDALONE_DECK_TEMPLATE } from "@/features/runs/domain/deckTemplate";

function ThemeDecorator({
  children,
  theme,
}: {
  children: React.ReactNode;
  theme: "dark" | "light";
}) {
  useEffect(() => {
    const previousTheme = document.documentElement.dataset.theme;
    document.documentElement.dataset.theme = theme;
    return () => {
      if (previousTheme) {
        document.documentElement.dataset.theme = previousTheme;
        return;
      }
      delete document.documentElement.dataset.theme;
    };
  }, [theme]);

  return <>{children}</>;
}

const meta = {
  title: "Features/Runs/AtlasRunDeck",
  component: AtlasRunDeck,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
    docs: {
      description: {
        component:
          "Shared Atlas slide grammar for both runtime-generated decks and the standalone executive template.",
      },
    },
  },
} satisfies Meta<typeof AtlasRunDeck>;

export default meta;

type Story = StoryObj<typeof meta>;

export const StandaloneTemplate: Story = {
  args: {
    copy: DEFAULT_ATLAS_RUN_DECK_COPY,
    deck: ATLAS_STANDALONE_DECK_TEMPLATE,
  },
  render: (args) => (
    <div className="atlas-shell-frame py-8">
      <AtlasRunDeck {...args} />
    </div>
  ),
};

export const StandaloneTemplateDark: Story = {
  decorators: [
    (Story) => (
      <ThemeDecorator theme="dark">
        <Story />
      </ThemeDecorator>
    ),
  ],
  args: {
    copy: DEFAULT_ATLAS_RUN_DECK_COPY,
    deck: ATLAS_STANDALONE_DECK_TEMPLATE,
  },
  render: (args) => (
    <div className="atlas-shell-frame py-8">
      <AtlasRunDeck {...args} />
    </div>
  ),
};
