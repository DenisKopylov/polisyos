import { useMemo } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, userEvent, within } from "storybook/test";

import { queryKeys } from "@/api/queryKeys";
import RunsListPage from "@/features/runs/routes/RunsListPage";
import { NetworkStatusProvider } from "@/shared/network";

const runsData = {
  page: {
    count: 2,
    cursor: null,
    next_cursor: "cursor-2",
    total: 2,
  },
  runs: [
    {
      duration_ms: 180000,
      root_artifact_count: 4,
      run_id: "run-001",
      source_kind: "workflow",
      started_at: "2026-03-09T08:00:00Z",
      status: "completed",
    },
    {
      duration_ms: 420000,
      root_artifact_count: 7,
      run_id: "run-002",
      source_kind: "operator",
      started_at: "2026-03-09T08:15:00Z",
      status: "running",
    },
  ],
};

function SeededRunsListPage() {
  const queryClient = useMemo(() => {
    const nextClient = new QueryClient({
      defaultOptions: {
        queries: {
          gcTime: Infinity,
          retry: false,
        },
      },
    });
    nextClient.setQueryDefaults(queryKeys.runsRoot(), {
      queryFn: () => Promise.resolve(runsData),
      staleTime: Number.POSITIVE_INFINITY,
    });
    nextClient.setQueryData(
      queryKeys.runs({
        cursor: undefined,
        from_ts: undefined,
        limit: 50,
        status: undefined,
        to_ts: undefined,
      }),
      runsData,
    );
    return nextClient;
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <NetworkStatusProvider>
        <RunsListPage />
      </NetworkStatusProvider>
    </QueryClientProvider>
  );
}

const meta = {
  title: "Features/Runs/RunsListPage",
  component: SeededRunsListPage,
  tags: ["autodocs"],
} satisfies Meta<typeof SeededRunsListPage>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const runLink = canvas.getByRole("link", { name: "run-002" });
    await userEvent.hover(runLink);
    await expect(runLink.closest("tr")).toHaveAttribute(
      "aria-selected",
      "true",
    );
  },
};
