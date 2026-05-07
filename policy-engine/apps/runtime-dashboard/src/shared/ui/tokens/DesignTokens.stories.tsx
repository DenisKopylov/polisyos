import { useEffect } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  designTokens,
  type DesignTokenDefinition,
} from "@/shared/ui/tokens/designTokens";

type TokenGroup = Record<string, DesignTokenDefinition>;

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

function TokenSwatch({
  name,
  token,
}: {
  name: string;
  token: DesignTokenDefinition;
}) {
  return (
    <article className="border-line bg-panel shadow-panel rounded-[var(--radius-card)] border p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{name}</p>
          <p className="text-muted mt-1 text-xs">{token.cssVar}</p>
        </div>
        <span
          aria-hidden="true"
          className="border-line h-10 w-10 rounded-2xl border"
          style={{ backgroundColor: `var(${token.cssVar})` }}
        />
      </div>
      <p className="text-muted mt-3 text-sm">{token.description}</p>
    </article>
  );
}

function TokenSection({
  groups,
  title,
}: {
  groups: Record<string, TokenGroup>;
  title: string;
}) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">{title}</h2>
      </div>
      <div className="space-y-5">
        {Object.entries(groups).map(([groupName, tokens]) => (
          <div key={groupName} className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-muted text-sm font-semibold tracking-[0.18em] uppercase">
                {groupName}
              </h3>
              <p className="text-muted text-xs">
                {Object.keys(tokens).length} tokens
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {Object.entries(tokens).map(([tokenName, token]) => (
                <TokenSwatch
                  key={`${groupName}-${tokenName}`}
                  name={`${groupName}.${tokenName}`}
                  token={token}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

const meta = {
  title: "Design System/Tokens",
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Foundation tokens define raw visual primitives. Semantic tokens carry product meaning and should be preferred in governance, evidence, and control-plane surfaces.",
      },
    },
  },
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

export const Foundations: Story = {
  render: () => (
    <TokenSection groups={designTokens.foundation} title="Foundation Tokens" />
  ),
  parameters: {
    docs: {
      description: {
        story:
          "Use foundation tokens for spacing, radius, motion, typography, and neutral palette decisions. Do not encode policy meaning here.",
      },
    },
  },
};

export const Semantic: Story = {
  render: () => (
    <TokenSection groups={designTokens.semantic} title="Semantic Tokens" />
  ),
  parameters: {
    docs: {
      description: {
        story:
          "Semantic tokens are the first choice for runtime state, severity, governance, transport health, and destructive action affordances.",
      },
    },
  },
};

export const SemanticDark: Story = {
  decorators: [
    (Story) => (
      <ThemeDecorator theme="dark">
        <Story />
      </ThemeDecorator>
    ),
  ],
  render: () => (
    <TokenSection
      groups={designTokens.semantic}
      title="Semantic Tokens in Dark Theme"
    />
  ),
  parameters: {
    docs: {
      description: {
        story:
          "Dark-theme snapshot for semantic coverage. Use this to review contrast and meaning preservation across themes.",
      },
    },
  },
};
