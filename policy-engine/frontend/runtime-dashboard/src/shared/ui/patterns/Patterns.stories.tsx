import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  Badge,
  Button,
  Card,
  DetailLayout,
  FilterPanel,
  SearchableList,
} from "@/shared/ui";

const meta = {
  title: "Design System/Patterns",
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Patterns compose primitives and compounds into reusable workspace scaffolding. They should absorb common layout, filtering, and detail-view concerns before feature code reaches for bespoke markup.",
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
              <label className="flex items-center gap-2">
                <input
                  defaultChecked
                  type="checkbox"
                  className="accent-accent"
                />
                Include governance waiting states
              </label>
              <label className="flex items-center gap-2">
                <input
                  defaultChecked
                  type="checkbox"
                  className="accent-accent"
                />
                Show stale cached data
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" className="accent-accent" />
                Only destructive actions
              </label>
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
