import { useEffect, type CSSProperties, type ReactNode } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { AtlasBrand } from "@/shared/brand/AtlasBrand";
import { Glyph } from "@/shared/brand/Glyph";
import { GLYPH_NAMES } from "@/shared/brand/glyph-vocabulary";
import { Badge } from "@/shared/ui/Badge";
import { Button } from "@/shared/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/Card";
import { MetricCard } from "@/shared/ui/MetricCard";

const colorTokens = [
  ["Paper", "--paper", "Primary app background"],
  ["Sand", "--sand", "Muted surface"],
  ["Ink", "--ink", "Primary text"],
  ["Graphite", "--graphite", "Dense rail and headers"],
  ["Slate", "--slate", "Muted text"],
  ["Line", "--line", "Borders"],
  ["Teal", "--teal", "Approved, live, primary"],
  ["Ember", "--ember", "Risk, failed, blocked"],
  ["Gold", "--gold", "Pending, review, partial"],
  ["Panel", "--panel", "Glass panel"],
  ["Surface", "--surface", "Nested surface"],
] as const;

const semanticColorTokens = [
  ["Success", "--success", "Positive runtime signal"],
  ["Warning", "--warning", "Review or partial state"],
  ["Danger", "--danger", "Stop or destructive state"],
  ["Chart primary", "--chart-primary", "Primary chart series"],
  ["Chart secondary", "--chart-secondary", "Secondary chart series"],
  ["Focus ring", "--focus-ring", "Keyboard focus"],
] as const;

const typeTokens = [
  ["2xs", "--text-2xs", "Mono metadata"],
  ["xs", "--text-xs", "Eyebrows and compact labels"],
  ["sm", "--text-sm", "Secondary copy"],
  ["base", "--text-base", "Body text"],
  ["lg", "--text-lg", "Reading emphasis"],
  ["xl", "--text-xl", "Card heading"],
  ["2xl", "--text-2xl", "Panel heading"],
  ["3xl", "--text-3xl", "Page heading"],
  ["4xl", "--text-4xl", "Largest runtime heading"],
] as const;

const shadowTokens = [
  ["XS", "--shadow-xs"],
  ["SM", "--shadow-sm"],
  ["MD", "--shadow-md"],
  ["LG", "--shadow-lg"],
  ["XL", "--shadow-xl"],
] as const;

function ThemeDecorator({
  children,
  theme,
}: {
  children: ReactNode;
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

function ReferenceShell({ children }: { children: ReactNode }) {
  return <div className="max-w-6xl space-y-8 p-6">{children}</div>;
}

function Section({
  children,
  description,
  title,
}: {
  children: ReactNode;
  description?: string;
  title: string;
}) {
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <p className="text-muted font-mono text-xs tracking-[0.14em] uppercase">
          Atlas v4 reference
        </p>
        <h2 className="text-2xl font-extrabold tracking-tight">{title}</h2>
        {description ? (
          <p className="text-muted max-w-3xl text-sm">{description}</p>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function Swatch({
  description,
  label,
  token,
}: {
  description: string;
  label: string;
  token: string;
}) {
  return (
    <article className="border-line bg-panel rounded-[var(--radius-card)] border p-4 shadow-[var(--shadow-xs)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold">{label}</h3>
          <p className="text-muted mt-1 font-mono text-xs">{token}</p>
        </div>
        <span
          aria-hidden="true"
          className="border-line h-12 w-12 rounded-[var(--radius-sm)] border"
          style={{ background: `var(${token})` }}
        />
      </div>
      <p className="text-muted mt-4 text-sm">{description}</p>
    </article>
  );
}

function TypeSpec({
  label,
  sample,
  token,
}: {
  label: string;
  sample: string;
  token: string;
}) {
  const style: CSSProperties = {
    fontSize: `var(${token})`,
  };

  return (
    <article className="border-line flex min-h-24 items-center justify-between gap-4 border-b py-4">
      <div className="min-w-28">
        <p className="text-muted font-mono text-xs tracking-[0.14em] uppercase">
          {label}
        </p>
        <p className="text-muted font-mono text-xs">{token}</p>
      </div>
      <p className="flex-1 leading-tight font-extrabold" style={style}>
        {sample}
      </p>
    </article>
  );
}

const meta = {
  title: "Design System/Atlas V4 Reference",
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Canonical Atlas v4 adoption review surface for color, type, shadows, glyphs, buttons, badges, and cards.",
      },
    },
  },
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

export const Color: Story = {
  render: () => (
    <ReferenceShell>
      <Section
        title="Color"
        description="Warm neutrals with teal, ember, and gold as the only product signal colors."
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {colorTokens.map(([label, token, description]) => (
            <Swatch
              key={token}
              description={description}
              label={label}
              token={token}
            />
          ))}
        </div>
      </Section>
      <Section title="Semantic color">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {semanticColorTokens.map(([label, token, description]) => (
            <Swatch
              key={token}
              description={description}
              label={label}
              token={token}
            />
          ))}
        </div>
      </Section>
    </ReferenceShell>
  ),
};

export const ColorDark: Story = {
  decorators: [
    (Story) => (
      <ThemeDecorator theme="dark">
        <Story />
      </ThemeDecorator>
    ),
  ],
  render: () => (
    <ReferenceShell>
      <Section
        title="Warm dark color"
        description="Production keeps warm dark as canonical; the archive blue dark palette is documented as a rejected reference."
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[...colorTokens, ...semanticColorTokens].map(
            ([label, token, description]) => (
              <Swatch
                key={token}
                description={description}
                label={label}
                token={token}
              />
            ),
          )}
        </div>
      </Section>
    </ReferenceShell>
  ),
};

export const Type: Story = {
  render: () => (
    <ReferenceShell>
      <Section
        title="Type"
        description="Runtime Atlas uses Manrope for interface text and IBM Plex Mono for identifiers, timestamps, and compact labels."
      >
        <div className="border-line bg-panel rounded-[var(--radius-panel)] border px-5">
          {typeTokens.map(([label, token, sample]) => (
            <TypeSpec key={token} label={label} sample={sample} token={token} />
          ))}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <article className="border-line bg-panel rounded-[var(--radius-card)] border p-5">
            <p className="text-muted font-mono text-xs tracking-[0.14em] uppercase">
              Mono grammar
            </p>
            <p className="text-muted mt-3 font-mono text-sm tracking-[0.08em]">
              RUN:2026-04-29T11:42Z / POLICY:V3.4
            </p>
          </article>
          <article className="border-line bg-panel rounded-[var(--radius-card)] border p-5">
            <p className="text-muted font-mono text-xs tracking-[0.14em] uppercase">
              Reading prose
            </p>
            <p className="mt-3 max-w-[68ch] text-[17px] leading-[1.65]">
              The decision packet prioritizes claims by confidence, provenance,
              and open objections.
            </p>
          </article>
        </div>
      </Section>
    </ReferenceShell>
  ),
};

export const Shadows: Story = {
  render: () => (
    <ReferenceShell>
      <Section
        title="Shadows"
        description="Elevation is restrained and warm. Major panels use the shell shadow; cards usually stay quiet."
      >
        <div className="grid gap-4 md:grid-cols-5">
          {shadowTokens.map(([label, token]) => (
            <article
              key={token}
              className="border-line bg-panel rounded-[var(--radius-card)] border p-5"
              style={{ boxShadow: `var(${token})` }}
            >
              <p className="text-lg font-extrabold">{label}</p>
              <p className="text-muted mt-2 font-mono text-xs">{token}</p>
            </article>
          ))}
        </div>
      </Section>
    </ReferenceShell>
  ),
};

export const Glyphs: Story = {
  render: () => (
    <ReferenceShell>
      <Section
        title="Glyphs"
        description="The 10 radical alphabet is closed. Domain concepts map to these glyphs rather than to third-party icon sets."
      >
        <div className="flex flex-wrap gap-3">
          {GLYPH_NAMES.map((name) => (
            <article
              key={name}
              className="border-line bg-panel flex min-w-48 items-center gap-3 rounded-[var(--radius-card)] border p-4"
            >
              <Glyph name={name} size={24} title={name} />
              <div>
                <p className="font-semibold">{name}</p>
                <p className="text-muted font-mono text-xs">24px radical</p>
              </div>
            </article>
          ))}
        </div>
        <div
          className="border-line rounded-[var(--radius-panel)] border p-5"
          style={{ background: "var(--rail-surface)" }}
        >
          <AtlasBrand inverted size={180} />
        </div>
      </Section>
    </ReferenceShell>
  ),
};

export const Buttons: Story = {
  render: () => (
    <ReferenceShell>
      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            leading={<Glyph decorative name="intervention" size={16} />}
            variant="primary"
          >
            Launch scenario
          </Button>
          <Button leading={<Glyph decorative name="evidence" size={16} />}>
            Review evidence
          </Button>
          <Button
            leading={<Glyph decorative name="blocker" size={16} />}
            variant="danger"
          >
            Block run
          </Button>
          <Button
            leading={<Glyph decorative name="reproducibility" size={16} />}
            variant="outline"
          >
            Replay
          </Button>
        </div>
      </Section>
    </ReferenceShell>
  ),
};

export const Badges: Story = {
  render: () => (
    <ReferenceShell>
      <Section title="Badges">
        <div className="flex flex-wrap gap-3">
          <Badge kind="ok">Approved</Badge>
          <Badge kind="warn">Review</Badge>
          <Badge kind="fail">Blocked</Badge>
          <Badge kind="neutral">Snapshot</Badge>
          <Badge kind="info">Live</Badge>
          <Badge kind="outline">Traceable</Badge>
        </div>
      </Section>
    </ReferenceShell>
  ),
};

export const Cards: Story = {
  render: () => (
    <ReferenceShell>
      <Section title="Cards">
        <div className="grid gap-4 md:grid-cols-3">
          <MetricCard
            badge={<Badge kind="ok">OK</Badge>}
            label="Confidence"
            meta="Verified evidence"
            value="0.82"
          />
          <MetricCard
            badge={<Badge kind="warn">Partial</Badge>}
            label="Freshness"
            meta="2 sources delayed"
            value="74%"
          />
          <MetricCard
            badge={<Badge kind="fail">Blocker</Badge>}
            label="Objections"
            meta="Legal review open"
            value="2"
          />
        </div>
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>Decision packet</CardTitle>
              <CardDescription>
                Glass panel, warm border, stable radius, and concise copy.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-muted text-sm">
                A card frames one repeated item or one tool. Metric cards sit
                beside it, not inside it, so the layout keeps a single frame
                hierarchy.
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge kind="ok">Traceable</Badge>
                <Badge kind="warn">Partial bounds</Badge>
                <Badge kind="outline">Signed packet</Badge>
              </div>
            </CardContent>
          </Card>
          <Card className="space-y-4">
            <div className="flex items-center gap-3">
              <Glyph name="provenance" size={24} title="provenance" />
              <div>
                <h3 className="font-extrabold">Trace summary</h3>
                <p className="text-muted text-sm">
                  Every surfaced number keeps its lineage visible.
                </p>
              </div>
            </div>
            <div className="border-line bg-surface rounded-[var(--radius-card)] border p-4">
              <p className="text-muted font-mono text-xs tracking-[0.12em] uppercase">
                Source chain
              </p>
              <p className="mt-2 text-sm">
                {"Dataset -> model card -> policy version -> decision packet."}
              </p>
            </div>
          </Card>
        </div>
      </Section>
    </ReferenceShell>
  ),
};
