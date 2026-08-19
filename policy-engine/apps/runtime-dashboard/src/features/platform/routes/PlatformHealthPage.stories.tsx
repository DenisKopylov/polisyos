import { useMemo } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { queryKeys } from "@/api/queryKeys";
import { AuthzProvider } from "@/app/authz/AuthzProvider";
import PlatformHealthPage from "@/features/platform/routes/PlatformHealthPage";
import { TEST_AUTH_ME } from "@/test/fixtures/authMe";

const healthData = {
  service: "runtime-http",
  status: "ok",
  ts: "2026-03-09T09:00:00Z",
};

const capabilitiesData = {
  constraints: {
    max_runs: 12,
  },
  default_locale: "en",
  features: [
    {
      category: "runtime",
      description: "Scenario Composer",
      enabled: true,
      key: "enableScenarioComposer",
      label: "Scenario Composer",
      stage: "active",
    },
    {
      category: "runtime",
      description: "Lex Knowledge",
      enabled: false,
      key: "enableLexKnowledge",
      label: "Lex Knowledge",
      stage: "beta",
    },
  ],
  runtime_api_version: "1.0.0",
};

const connectorsData = {
  connectors: [
    {
      connector_id: "edrnpa",
      last_health_check: "2026-03-09T08:55:00Z",
      loaded: true,
    },
    {
      connector_id: "transport",
      last_health_check: null,
      loaded: false,
    },
  ],
};

const runsData = {
  page: {
    count: 1,
    cursor: null,
    next_cursor: null,
    total: 1,
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
  ],
};

function SeededPlatformHealthPage() {
  const queryClient = useMemo(() => {
    const nextClient = new QueryClient({
      defaultOptions: {
        queries: {
          gcTime: Infinity,
          retry: false,
        },
      },
    });
    nextClient.setQueryDefaults(queryKeys.health(), {
      queryFn: () => Promise.resolve(healthData),
      refetchInterval: false,
      staleTime: Number.POSITIVE_INFINITY,
    });
    nextClient.setQueryDefaults(queryKeys.capabilities(), {
      queryFn: () => Promise.resolve(capabilitiesData),
      staleTime: Number.POSITIVE_INFINITY,
    });
    nextClient.setQueryDefaults(queryKeys.connectors(), {
      queryFn: () => Promise.resolve(connectorsData),
      staleTime: Number.POSITIVE_INFINITY,
    });
    nextClient.setQueryDefaults(queryKeys.runsRoot(), {
      queryFn: () => Promise.resolve(runsData),
      staleTime: Number.POSITIVE_INFINITY,
    });
    nextClient.setQueryData(queryKeys.health(), healthData);
    nextClient.setQueryData(queryKeys.capabilities(), capabilitiesData);
    nextClient.setQueryData(queryKeys.connectors(), connectorsData);
    nextClient.setQueryData(queryKeys.runs({ limit: 12 }), runsData);
    nextClient.setQueryData(queryKeys.authMe(), TEST_AUTH_ME);
    return nextClient;
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthzProvider>
        <PlatformHealthPage />
      </AuthzProvider>
    </QueryClientProvider>
  );
}

const meta = {
  title: "Features/Platform/PlatformHealthPage",
  component: SeededPlatformHealthPage,
  tags: ["autodocs"],
} satisfies Meta<typeof SeededPlatformHealthPage>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Healthy: Story = {};
