import { useId, useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  Badge,
  Button,
  Card,
  Checkbox,
  DetailLayout,
  FilterPanel,
  Radio,
  SegmentedControl,
  Switch,
  ToggleButton,
} from "@polisyos/atlas-ui";
import { SearchableList } from "@/shared/ui";

const meta = {
  title: "Design System/Patterns",
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Patterns compose primitives and compounds into reusable workspace scaffolding. They should absorb layout, filtering, and selection semantics before feature code reaches for bespoke markup.",
      },
    },
  },
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

const candidates = [
  {
    id: "cand-1",
    metric: "Inflation outlook",
    owner: "Evidence Ops",
    state: "ready",
  },
  {
    id: "cand-2",
    metric: "Food security baseline",
    owner: "Governance",
    state: "review",
  },
  {
    id: "cand-3",
    metric: "Fuel subsidy exposure",
    owner: "Policy Ops",
    state: "ready",
  },
];

function PatternsDemo() {
  const [query, setQuery] = useState("");

  return (
    <DetailLayout
      header={
        <Card className="space-y-2">
          <p className="text-muted text-xs font-semibold tracking-[0.18em] uppercase">
            Workspace pattern
          </p>
          <h2 className="text-2xl font-semibold">
            Queue triage with shareable filter state
          </h2>
          <p className="text-muted text-sm">
            Use patterns to keep filter chrome, searchable queues, and detail
            panes structurally consistent across runs, evidence, and governance.
          </p>
        </Card>
      }
      sidebar={
        <div className="space-y-4">
          <FilterPanel
            title="Queue filters"
            description="Persist these controls to URL state in feature routes."
            actions={
              <Button size="sm" variant="ghost">
                Reset
              </Button>
            }
          >
            <div className="text-muted space-y-2 text-sm">
              <div className="atlas-choice-card" data-selected="true">
                <Checkbox
                  id="patterns-governance-waiting"
                  aria-labelledby="patterns-governance-waiting-label"
                  aria-describedby="patterns-governance-waiting-meta"
                  defaultChecked
                />
                <span className="atlas-choice-card__body">
                  <span
                    id="patterns-governance-waiting-label"
                    className="atlas-choice-card__title"
                  >
                    Include governance waiting states
                  </span>
                  <span
                    id="patterns-governance-waiting-meta"
                    className="atlas-choice-card__meta"
                  >
                    Keep queue triage aware of items blocked by policy review.
                  </span>
                </span>
              </div>
              <div className="atlas-choice-card" data-selected="true">
                <Checkbox
                  id="patterns-stale-cache"
                  aria-labelledby="patterns-stale-cache-label"
                  aria-describedby="patterns-stale-cache-meta"
                  defaultChecked
                />
                <span className="atlas-choice-card__body">
                  <span
                    id="patterns-stale-cache-label"
                    className="atlas-choice-card__title"
                  >
                    Show stale cached data
                  </span>
                  <span
                    id="patterns-stale-cache-meta"
                    className="atlas-choice-card__meta"
                  >
                    Highlight evidence packets that may need refresh before use.
                  </span>
                </span>
              </div>
              <div className="atlas-choice-card" data-selected="false">
                <Checkbox
                  id="patterns-destructive-actions"
                  aria-labelledby="patterns-destructive-actions-label"
                  aria-describedby="patterns-destructive-actions-meta"
                />
                <span className="atlas-choice-card__body">
                  <span
                    id="patterns-destructive-actions-label"
                    className="atlas-choice-card__title"
                  >
                    Only destructive actions
                  </span>
                  <span
                    id="patterns-destructive-actions-meta"
                    className="atlas-choice-card__meta"
                  >
                    Narrow the queue to interventions that require extra review.
                  </span>
                </span>
              </div>
            </div>
          </FilterPanel>
          <Card className="space-y-2">
            <p className="text-sm font-semibold">Usage rules</p>
            <ul className="text-muted list-disc space-y-1 pl-5 text-sm">
              <li>
                Keep filter semantics in search params, not local-only state.
              </li>
              <li>
                Use compounds for metric, decision, evidence, and timeline UI.
              </li>
              <li>Keep detail panes resilient when one panel degrades.</li>
            </ul>
          </Card>
        </div>
      }
      content={
        <SearchableList
          items={candidates}
          query={query}
          onQueryChange={setQuery}
          getItemKey={(item) => item.id}
          getSearchText={(item) => `${item.metric} ${item.owner} ${item.state}`}
          placeholder="Search queue items"
          emptyTitle="No matching candidates"
          emptyBody="Widen the search query or clear a filter."
          renderItem={(item) => (
            <Card className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold">{item.metric}</p>
                  <p className="text-muted mt-1 text-sm">{item.owner}</p>
                </div>
                <Badge kind={item.state === "ready" ? "ok" : "warn"}>
                  {item.state}
                </Badge>
              </div>
              <p className="text-muted text-sm">
                This item uses the shared search/list/detail shell instead of
                feature-local queue markup.
              </p>
            </Card>
          )}
        />
      }
    />
  );
}

export const WorkspaceScaffold: Story = {
  render: () => <PatternsDemo />,
};

type SelectionSurface = "queue" | "compose" | "decision";
type SourceMode = "registry" | "hybrid" | "manual";

function StoryChoiceCard({
  checked,
  description,
  label,
  onChange,
  type,
}: {
  checked: boolean;
  description: string;
  label: string;
  onChange: () => void;
  type: "checkbox" | "radio";
}) {
  const inputId = useId();
  const labelId = useId();
  const descriptionId = useId();

  return (
    <div
      className="atlas-choice-card"
      data-selected={checked ? "true" : "false"}
    >
      {type === "checkbox" ? (
        <Checkbox
          id={inputId}
          checked={checked}
          onChange={onChange}
          aria-labelledby={labelId}
          aria-describedby={descriptionId}
        />
      ) : (
        <Radio
          id={inputId}
          checked={checked}
          onChange={onChange}
          name="selection-story"
          aria-labelledby={labelId}
          aria-describedby={descriptionId}
        />
      )}
      <span className="atlas-choice-card__body">
        <span id={labelId} className="atlas-choice-card__title">
          {label}
        </span>
        <span id={descriptionId} className="atlas-choice-card__meta">
          {description}
        </span>
      </span>
    </div>
  );
}

function StoryToggleRow({
  checked,
  description,
  label,
  onCheckedChange,
}: {
  checked: boolean;
  description: string;
  label: string;
  onCheckedChange: (checked: boolean) => void;
}) {
  const labelId = useId();
  const descriptionId = useId();

  return (
    <div
      className="atlas-toggle-row"
      data-selected={checked ? "true" : "false"}
    >
      <div className="atlas-toggle-row__body">
        <span id={labelId} className="atlas-toggle-row__title">
          {label}
        </span>
        <span id={descriptionId} className="atlas-toggle-row__meta">
          {description}
        </span>
      </div>
      <Switch
        checked={checked}
        onCheckedChange={onCheckedChange}
        aria-labelledby={labelId}
        aria-describedby={descriptionId}
      />
    </div>
  );
}

function SelectionPatternsDemo() {
  const [surface, setSurface] = useState<SelectionSurface>("compose");
  const [sourceMode, setSourceMode] = useState<SourceMode>("hybrid");
  const [includeGovernanceWaiting, setIncludeGovernanceWaiting] =
    useState(true);
  const [showStaleCache, setShowStaleCache] = useState(true);
  const [allowExploreFallback, setAllowExploreFallback] = useState(true);
  const [readingView, setReadingView] = useState(false);

  return (
    <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
      <Card className="space-y-5">
        <div className="space-y-2">
          <p className="text-muted text-xs font-semibold tracking-[0.18em] uppercase">
            Selection vocabulary
          </p>
          <h2 className="text-2xl font-semibold">
            Match the control to the decision semantics
          </h2>
          <p className="text-muted max-w-3xl text-sm">
            Keep the control language stable across Atlas surfaces: segmented
            controls for visible mode switches, radio cards for exclusive inputs
            with context, checkboxes for additive filters, switches for live
            preferences, and toggle buttons for compact toolbar modes.
          </p>
        </div>

        <section className="space-y-3">
          <div>
            <h3 className="text-base font-semibold">Segmented control</h3>
            <p className="text-muted mt-1 text-sm">
              Use when the operator should compare all modes at a glance.
            </p>
          </div>
          <SegmentedControl
            ariaLabel="Primary workspace surface"
            className="lg:grid-cols-3"
            value={surface}
            onValueChange={setSurface}
            options={[
              {
                description: "Monitor queue health and coverage.",
                label: "Command center",
                value: "queue",
              },
              {
                description: "Frame the scenario and constraints.",
                label: "Scenario composer",
                value: "compose",
              },
              {
                description: "Inspect rationale and uncertainty.",
                label: "Decision workspace",
                value: "decision",
              },
            ]}
          />
        </section>

        <section className="space-y-3">
          <div>
            <h3 className="text-base font-semibold">Radio cards</h3>
            <p className="text-muted mt-1 text-sm">
              Use for exclusive choices that need a short explanation before
              commit.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <StoryChoiceCard
              type="radio"
              checked={sourceMode === "registry"}
              onChange={() => setSourceMode("registry")}
              label="Registry only"
              description="Strictly use source-backed evidence and interventions."
            />
            <StoryChoiceCard
              type="radio"
              checked={sourceMode === "hybrid"}
              onChange={() => setSourceMode("hybrid")}
              label="Hybrid compose"
              description="Prefer registry data, but allow analyst framing."
            />
            <StoryChoiceCard
              type="radio"
              checked={sourceMode === "manual"}
              onChange={() => setSourceMode("manual")}
              label="Manual draft"
              description="Start from operator input and enrich downstream."
            />
          </div>
        </section>
      </Card>

      <div className="space-y-4">
        <FilterPanel
          title="Additive filters"
          description="Checkboxes stay reserved for filters where more than one slice can be active."
        >
          <div className="space-y-3">
            <StoryChoiceCard
              type="checkbox"
              checked={includeGovernanceWaiting}
              onChange={() =>
                setIncludeGovernanceWaiting((current) => !current)
              }
              label="Include governance waiting states"
              description="Keep blocked items visible during queue triage."
            />
            <StoryChoiceCard
              type="checkbox"
              checked={showStaleCache}
              onChange={() => setShowStaleCache((current) => !current)}
              label="Show stale cached data"
              description="Flag evidence packets that may need refresh."
            />
          </div>
        </FilterPanel>

        <Card className="space-y-4">
          <div>
            <h3 className="text-base font-semibold">Immediate state flips</h3>
            <p className="text-muted mt-1 text-sm">
              Use switches for settings with immediate effect, and toggle
              buttons when the state belongs in a toolbar.
            </p>
          </div>
          <StoryToggleRow
            checked={allowExploreFallback}
            onCheckedChange={setAllowExploreFallback}
            label="Allow explore fallback"
            description="Let Atlas pull adjacent sources when connector coverage is thin."
          />
          <ToggleButton
            size="sm"
            label="Reading view"
            pressed={readingView}
            onPressedChange={setReadingView}
            trailing={
              <span className="rounded-full border border-current/20 px-1.5 py-0.5 text-[0.62rem] leading-none opacity-80">
                R
              </span>
            }
          />
        </Card>
      </div>
    </div>
  );
}

export const SelectionVocabulary: Story = {
  render: () => <SelectionPatternsDemo />,
  parameters: {
    docs: {
      description: {
        story:
          "Canonical Atlas guidance for selection-heavy surfaces. Reach for these combinations before building feature-local controls or styling raw browser inputs.",
      },
    },
  },
};
