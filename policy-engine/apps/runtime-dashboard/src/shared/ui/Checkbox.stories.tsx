import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { Checkbox } from "@polisyos/atlas-ui";

const meta = {
  title: "Shared UI/Checkbox",
  component: Checkbox,
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Use checkboxes for additive filters and multi-select decisions where several options may be active at the same time.",
      },
    },
  },
} satisfies Meta<typeof Checkbox>;

export default meta;

type Story = StoryObj<typeof meta>;

function CheckboxClusterStory() {
  const [filters, setFilters] = useState({
    governanceWaiting: true,
    staleCached: true,
    destructiveOnly: false,
  });

  return (
    <div className="grid gap-3">
      <div
        className="atlas-choice-card"
        data-selected={filters.governanceWaiting ? "true" : "false"}
      >
        <Checkbox
          id="checkbox-governance-waiting"
          aria-labelledby="checkbox-governance-waiting-label"
          aria-describedby="checkbox-governance-waiting-meta"
          checked={filters.governanceWaiting}
          onChange={(event) =>
            setFilters((current) => ({
              ...current,
              governanceWaiting: event.currentTarget.checked,
            }))
          }
        />
        <span className="atlas-choice-card__body">
          <span
            id="checkbox-governance-waiting-label"
            className="atlas-choice-card__title"
          >
            Include governance waiting states
          </span>
          <span
            id="checkbox-governance-waiting-meta"
            className="atlas-choice-card__meta"
          >
            Keep decision queue triage aware of items blocked by policy review.
          </span>
        </span>
      </div>
      <div
        className="atlas-choice-card"
        data-selected={filters.staleCached ? "true" : "false"}
      >
        <Checkbox
          id="checkbox-stale-cached"
          aria-labelledby="checkbox-stale-cached-label"
          aria-describedby="checkbox-stale-cached-meta"
          checked={filters.staleCached}
          onChange={(event) =>
            setFilters((current) => ({
              ...current,
              staleCached: event.currentTarget.checked,
            }))
          }
        />
        <span className="atlas-choice-card__body">
          <span
            id="checkbox-stale-cached-label"
            className="atlas-choice-card__title"
          >
            Show stale cached data
          </span>
          <span
            id="checkbox-stale-cached-meta"
            className="atlas-choice-card__meta"
          >
            Surface runs that may need evidence refresh before promotion.
          </span>
        </span>
      </div>
      <div
        className="atlas-choice-card"
        data-selected={filters.destructiveOnly ? "true" : "false"}
      >
        <Checkbox
          id="checkbox-destructive-only"
          aria-labelledby="checkbox-destructive-only-label"
          aria-describedby="checkbox-destructive-only-meta"
          checked={filters.destructiveOnly}
          onChange={(event) =>
            setFilters((current) => ({
              ...current,
              destructiveOnly: event.currentTarget.checked,
            }))
          }
        />
        <span className="atlas-choice-card__body">
          <span
            id="checkbox-destructive-only-label"
            className="atlas-choice-card__title"
          >
            Only destructive actions
          </span>
          <span
            id="checkbox-destructive-only-meta"
            className="atlas-choice-card__meta"
          >
            Narrow the queue to interventions that require governance sign-off.
          </span>
        </span>
      </div>
    </div>
  );
}

export const Default: Story = {
  render: () => (
    <div className="inline-flex items-center gap-3">
      <Checkbox
        id="checkbox-uncertainty-overlays"
        aria-labelledby="checkbox-uncertainty-overlays-label"
        defaultChecked
      />
      <span
        id="checkbox-uncertainty-overlays-label"
        className="text-sm font-medium"
      >
        Include uncertainty overlays
      </span>
    </div>
  ),
};

export const FilterCluster: Story = {
  render: () => <CheckboxClusterStory />,
  parameters: {
    docs: {
      description: {
        story:
          "Default cluster pattern for filter rails and review queues. Use shared choice cards instead of naked browser inputs.",
      },
    },
  },
};
