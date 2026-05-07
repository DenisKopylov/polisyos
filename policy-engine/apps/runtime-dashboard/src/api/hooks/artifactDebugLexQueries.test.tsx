import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useArtifactContent } from "@/api/hooks/useArtifactContent";
import { useArtifactLineage } from "@/api/hooks/useArtifactLineage";
import { useArtifactManifest } from "@/api/hooks/useArtifactManifest";
import { useArtifactSchema } from "@/api/hooks/useArtifactSchema";
import { useCacheStatus } from "@/api/hooks/useCacheStatus";
import {
  governanceDebugQueryOptions,
  useGovernanceDebug,
} from "@/api/hooks/useGovernanceDebug";
import { useLexGraphStats } from "@/api/hooks/useLexGraphStats";
import { useLexPipelineStatus } from "@/api/hooks/useLexPipelineStatus";
import { useNodeDebug } from "@/api/hooks/useNodeDebug";
import { useRunLineage } from "@/api/hooks/useRunLineage";
import { useRunTimeline } from "@/api/hooks/useRunTimeline";
import { queryKeys } from "@/api/queryKeys";
import { createQueryHookWrapper } from "@/test/queryHook";
import { mockRuntimeGetSuccess } from "@/test/runtimeApi";

const runId = "R_core_api_001";
const artifactId = "artifact-001";
const nodeAlias = "plan_builder";
const pipelineId = "pipeline-001";
const meta = {
  generated_at: "2026-03-09T10:00:00Z",
  request_id: "req-2",
  source_kinds: ["core_run"],
};

const artifactManifestPayload = {
  artifact: {
    artifact_id: artifactId,
    byte_size: 128,
    created_at: "2026-03-09T10:00:00Z",
    integrity_sha256: "abc123",
    kind: "json",
    media_type: "application/json",
  },
  meta,
};

const artifactContentPayload = {
  artifact: {
    artifact_id: artifactId,
    kind: "json",
    max_bytes: 512,
    media_type: "application/json",
    mode: "json",
    preview: {
      verdict: "ok",
    },
    size_bytes: 256,
    truncated: false,
  },
  meta,
};

const artifactSchemaPayload = {
  meta,
  schema: {
    artifact_id: artifactId,
    kind: "json",
    media_type: "application/json",
  },
};

const lineagePayload = {
  lineage: {
    is_complete: true,
    total_edges: 0,
    total_nodes: 0,
    total_size_bytes: 0,
  },
  meta,
};

const runLineagePayload = {
  lineage: lineagePayload.lineage,
  meta,
  run_id: runId,
};

const runTimelinePayload = {
  meta,
  timeline: {
    run_id: runId,
    source_kind: "core_run",
    summary: {
      run_id: runId,
      total_events: 0,
    },
  },
};

const governanceDebugPayload = {
  debug: {
    run_id: runId,
    source_kind: "core_run",
  },
  meta,
};

const nodeDebugPayload = {
  debug: {
    alias: nodeAlias,
    record: {
      alias: nodeAlias,
      duration_ms: 0,
      status: "ok",
    },
    run_id: runId,
    source_kind: "core_run",
  },
  meta,
};

const lexGraphStatsPayload = {
  nodes_total: 42,
  output_dir: "data/lex",
};

const lexPipelineStatusPayload = {
  pipeline_id: pipelineId,
  state: "running",
};

function useArtifactManifestHook() {
  return useArtifactManifest(artifactId);
}

function useArtifactContentHook() {
  return useArtifactContent(artifactId, { maxBytes: 512 });
}

function useArtifactSchemaHook() {
  return useArtifactSchema(artifactId);
}

function useArtifactLineageHook() {
  return useArtifactLineage(artifactId);
}

function useCacheStatusHook() {
  return useCacheStatus();
}

function useRunTimelineHook() {
  return useRunTimeline(runId);
}

function useRunLineageHook() {
  return useRunLineage(runId);
}

function useGovernanceDebugHook() {
  return useGovernanceDebug(runId);
}

function useNodeDebugHook() {
  return useNodeDebug(runId, nodeAlias);
}

function useLexGraphStatsHook() {
  return useLexGraphStats("data/lex");
}

function useLexPipelineStatusHook() {
  return useLexPipelineStatus(pipelineId);
}

describe("artifact, debug, and lex query hooks", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads artifact and cache resources through typed query keys", async () => {
    const scenarios = [
      {
        endpoint: "/api/v1/artifacts/{artifact_id}",
        hook: useArtifactManifestHook,
        payload: artifactManifestPayload,
        queryKey: queryKeys.artifactManifest(artifactId),
      },
      {
        endpoint: "/api/v1/artifacts/{artifact_id}/content",
        hook: useArtifactContentHook,
        payload: artifactContentPayload,
        queryKey: queryKeys.artifactContent(artifactId, 512),
      },
      {
        endpoint: "/api/v1/artifacts/{artifact_id}/schema",
        hook: useArtifactSchemaHook,
        payload: artifactSchemaPayload,
        queryKey: queryKeys.artifactSchema(artifactId),
      },
      {
        endpoint: "/api/v1/control/data/cache",
        hook: useCacheStatusHook,
        payload: {
          cache_entries: 3,
          hit_rate: 0.8,
        },
        queryKey: queryKeys.cacheStatus(),
      },
    ] as const;

    for (const scenario of scenarios) {
      const getSpy = mockRuntimeGetSuccess(scenario.payload);
      const { result, unmount } = renderHook(() => scenario.hook(), {
        wrapper: createQueryHookWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(getSpy.mock.calls[0]?.[0]).toBe(scenario.endpoint);
      expect(result.current.data).toEqual(scenario.payload);
      expect(scenario.queryKey).toBeTruthy();
      unmount();
      vi.restoreAllMocks();
    }
  });

  it("normalizes lineage, timeline, governance, and node debug payloads", async () => {
    const scenarios = [
      {
        endpoint: "/api/v1/artifacts/{artifact_id}/lineage",
        hook: useArtifactLineageHook,
        payload: lineagePayload,
        assertData: (data: {
          lineage: {
            corrupted_artifact_ids: unknown[];
            edges: unknown[];
            missing_artifact_ids: unknown[];
            nodes: unknown[];
            root_artifact_ids: unknown[];
          };
        }) => {
          expect(data.lineage.nodes).toEqual([]);
          expect(data.lineage.edges).toEqual([]);
          expect(data.lineage.root_artifact_ids).toEqual([]);
          expect(data.lineage.missing_artifact_ids).toEqual([]);
          expect(data.lineage.corrupted_artifact_ids).toEqual([]);
        },
      },
      {
        endpoint: "/api/v1/runs/{run_id}/timeline",
        hook: useRunTimelineHook,
        payload: runTimelinePayload,
        assertData: (data: {
          timeline: { events: unknown[]; notes: unknown[] };
        }) => {
          expect(data.timeline.events).toEqual([]);
          expect(data.timeline.notes).toEqual([]);
        },
      },
      {
        endpoint: "/api/v1/runs/{run_id}/lineage",
        hook: useRunLineageHook,
        payload: runLineagePayload,
        assertData: (data: {
          lineage: {
            corrupted_artifact_ids: unknown[];
            edges: unknown[];
            missing_artifact_ids: unknown[];
            nodes: unknown[];
            root_artifact_ids: unknown[];
          };
        }) => {
          expect(data.lineage.nodes).toEqual([]);
          expect(data.lineage.edges).toEqual([]);
          expect(data.lineage.root_artifact_ids).toEqual([]);
          expect(data.lineage.missing_artifact_ids).toEqual([]);
          expect(data.lineage.corrupted_artifact_ids).toEqual([]);
        },
      },
      {
        endpoint: "/api/v1/debug/runs/{run_id}/governance",
        hook: useGovernanceDebugHook,
        payload: governanceDebugPayload,
        assertData: (data: {
          debug: {
            fallback_from_decision_packet: boolean;
            issues: unknown[];
            notes: unknown[];
          };
        }) => {
          expect(data.debug.issues).toEqual([]);
          expect(data.debug.notes).toEqual([]);
          expect(data.debug.fallback_from_decision_packet).toBe(false);
        },
      },
      {
        endpoint: "/api/v1/debug/runs/{run_id}/nodes/{alias}",
        hook: useNodeDebugHook,
        payload: nodeDebugPayload,
        assertData: (data: {
          debug: {
            cache_bypasses: number;
            cache_hits: number;
            cache_stores: number;
            notes: unknown[];
            timeline_events: unknown[];
          };
        }) => {
          expect(data.debug.timeline_events).toEqual([]);
          expect(data.debug.notes).toEqual([]);
          expect(data.debug.cache_hits).toBe(0);
          expect(data.debug.cache_stores).toBe(0);
          expect(data.debug.cache_bypasses).toBe(0);
        },
      },
    ] as const;

    for (const scenario of scenarios) {
      const getSpy = mockRuntimeGetSuccess(scenario.payload);
      const { result, unmount } = renderHook(() => scenario.hook(), {
        wrapper: createQueryHookWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(getSpy.mock.calls[0]?.[0]).toBe(scenario.endpoint);
      scenario.assertData(result.current.data as never);

      unmount();
      vi.restoreAllMocks();
    }
  });

  it("loads lex graph and pipeline status with the expected polling keys", async () => {
    const graphSpy = mockRuntimeGetSuccess(lexGraphStatsPayload);
    const view = renderHook(() => useLexGraphStatsHook(), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      expect(view.result.current.data).toEqual(lexGraphStatsPayload);
    });

    expect(graphSpy).toHaveBeenCalledWith("/api/v1/control/lex/graph/stats", {
      params: {
        query: {
          output_dir: "data/lex",
        },
      },
    });

    vi.restoreAllMocks();

    {
      const pipelineSpy = mockRuntimeGetSuccess(lexPipelineStatusPayload);
      const view = renderHook(() => useLexPipelineStatusHook(), {
        wrapper: createQueryHookWrapper(),
      });

      await waitFor(() => {
        expect(view.result.current.data).toEqual(lexPipelineStatusPayload);
      });

      expect(pipelineSpy).toHaveBeenCalledWith(
        "/api/v1/control/lex/status/{pipeline_id}",
        {
          params: {
            path: {
              pipeline_id: pipelineId,
            },
          },
        },
      );
    }
    expect(queryKeys.lexGraphStats("data/lex")).toEqual([
      "lex",
      "graph",
      "stats",
      "data/lex",
    ]);
    expect(queryKeys.lexPipelineStatus(pipelineId)).toEqual([
      "lex",
      "pipeline",
      pipelineId,
    ]);
    expect(governanceDebugQueryOptions(runId).queryKey).toEqual(
      queryKeys.runGovernanceDebug(runId),
    );
  });
});
