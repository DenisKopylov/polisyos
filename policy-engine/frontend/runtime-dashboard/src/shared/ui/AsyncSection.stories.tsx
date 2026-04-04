import type { Meta, StoryObj } from "@storybook/react-vite";

import { AsyncSection } from "@/shared/ui/AsyncSection";
import { Card } from "@/shared/ui/Card";
import { EmptyState } from "@/shared/ui/EmptyState";
import { PanelSkeleton } from "@/shared/ui/Skeleton";

const meta = {
  title: "Shared UI/AsyncSection",
  component: AsyncSection,
  tags: ["autodocs"],
  args: {
    query: { isLoading: false, isError: false },
    children: null,
  },
} satisfies Meta<typeof AsyncSection>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Success: Story = {
  args: {
    query: { isLoading: false, isError: false },
    children: null,
  },
  render: () => (
    <AsyncSection query={{ isLoading: false, isError: false }}>
      <Card>
        <h3 className="text-xl font-semibold">Live data rendered</h3>
        <p className="text-muted mt-2 text-sm">
          This section swaps loading, error, and empty shells in one place.
        </p>
      </Card>
    </AsyncSection>
  ),
};

export const Loading: Story = {
  args: {
    query: { isLoading: true, isError: false },
    children: null,
  },
  render: () => (
    <AsyncSection
      query={{ isLoading: true }}
      loading={<PanelSkeleton rows={4} />}
    >
      <div />
    </AsyncSection>
  ),
};

export const Empty: Story = {
  args: {
    query: { isLoading: false, isError: false },
    children: null,
  },
  render: () => (
    <AsyncSection
      query={{ isLoading: false, isError: false }}
      empty
      emptyState={
        <EmptyState
          title="No evidence plans"
          body="Run context did not return any fetch plans."
        />
      }
    >
      <div />
    </AsyncSection>
  ),
};
