import { useQuery } from "@tanstack/react-query";

import { useQuantityRuntimeBridge } from "./QuantityRuntimeBridge";
import type { LineageExportPayload, TemporalRef } from "./quantity.types";

export function useLineage(
  lineageId: string | null | undefined,
  options: {
    enabled?: boolean;
    temporalScope?: TemporalRef | null;
  } = {},
) {
  const runtime = useQuantityRuntimeBridge();
  const temporalScope = options.temporalScope ?? runtime.temporalScope;
  return useQuery({
    queryKey: ["quantity-lineage", lineageId ?? "unknown", temporalScope],
    queryFn: () => runtime.fetchLineage(lineageId ?? "", temporalScope),
    enabled: Boolean(lineageId) && (options.enabled ?? true),
  });
}

export function useLineageExport(
  lineageId: string | null | undefined,
  format: LineageExportPayload["format"],
  options: {
    enabled?: boolean;
    temporalScope?: TemporalRef | null;
  } = {},
) {
  const runtime = useQuantityRuntimeBridge();
  const temporalScope = options.temporalScope ?? runtime.temporalScope;
  return useQuery({
    queryKey: [
      "quantity-lineage-export",
      lineageId ?? "unknown",
      format,
      temporalScope,
    ],
    queryFn: () =>
      runtime.fetchLineageExport(lineageId ?? "", format, temporalScope),
    enabled: Boolean(lineageId) && (options.enabled ?? false),
  });
}
