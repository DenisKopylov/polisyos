import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";
import type {
  TemporalCapabilitiesView,
  TemporalEventPoint as RuntimeTemporalEventPoint,
  TemporalSurfaceCapability as RuntimeTemporalSurfaceCapability,
} from "@polisyos/runtime-api-client";

import {
  fromApiTemporalScope,
  toApiTemporalRange,
  type TemporalCapabilities,
  type TemporalEventPoint,
  type TemporalSurfaceCapability,
} from "@/shared/lib/domain/temporal";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { temporalCapabilitiesSchema } from "../validators";

async function fetchTemporalCapabilities(
  runId: string | null | undefined,
): Promise<TemporalCapabilities> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/temporal/capabilities",
    {
      params: {
        query: runId ? { run_id: runId } : undefined,
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to load temporal capabilities",
    );
  }

  temporalCapabilitiesSchema.parse(data);
  const parsed: TemporalCapabilitiesView = data.capabilities;
  return {
    defaultScope: fromApiTemporalScope(parsed.default_scope),
    eventPoints: (parsed.event_points ?? []).map(toTemporalEventPoint),
    resolution: parsed.resolution,
    runId: parsed.run_id ?? null,
    surfaces: (parsed.surfaces ?? []).map(toTemporalSurfaceCapability),
    txRange: toApiTemporalRange(parsed.tx_range),
    validRange: toApiTemporalRange(parsed.valid_range),
  };
}

export function temporalCapabilitiesQueryOptions(
  runId: string | null | undefined,
) {
  return queryOptions({
    queryKey: queryKeys.temporalCapabilities(runId),
    queryFn: () => fetchTemporalCapabilities(runId),
  });
}

export function useTemporalRange(
  runId: string | null | undefined,
  enabled = true,
) {
  return useQuery({
    ...temporalCapabilitiesQueryOptions(runId),
    enabled: Boolean(runId) && enabled,
  });
}

export function useSuspenseTemporalRange(runId: string) {
  return useSuspenseQuery(temporalCapabilitiesQueryOptions(runId));
}

function toTemporalEventPoint(
  event: RuntimeTemporalEventPoint,
): TemporalEventPoint {
  return {
    id: event.id,
    kind: event.kind,
    label: event.label,
    observed: event.observed ?? true,
    timestamp: event.timestamp,
    txAt: event.tx_at ?? null,
    validAt: event.valid_at ?? null,
  };
}

function toTemporalSurfaceCapability(
  surface: RuntimeTemporalSurfaceCapability,
): TemporalSurfaceCapability {
  return {
    gaps: (surface.gaps ?? []).map((gap) => ({
      end: gap.end ?? null,
      label: gap.label ?? null,
      reasonCode: gap.reason_code,
      start: gap.start ?? null,
    })),
    nearestEventPoints: (surface.nearest_event_points ?? []).map(
      toTemporalEventPoint,
    ),
    reasonCode: surface.reason_code ?? null,
    resolution: surface.resolution,
    supported: surface.supported,
    surface: surface.surface,
    txRange: surface.tx_range ? toApiTemporalRange(surface.tx_range) : null,
    validRange: surface.valid_range
      ? toApiTemporalRange(surface.valid_range)
      : null,
  };
}
