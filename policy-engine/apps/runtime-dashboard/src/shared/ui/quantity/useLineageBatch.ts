import { useQuery } from "@tanstack/react-query";

import { useQuantityRuntimeBridge } from "./QuantityRuntimeBridge";
import type { QuantityValue, TemporalRef } from "./quantity.types";

export function lineageIdsFromQuantities(quantities: readonly QuantityValue[]) {
  return Array.from(
    new Set(
      quantities
        .map((quantity) => quantity.lineage.id)
        .filter((lineageId) => lineageId && lineageId !== "untraced"),
    ),
  );
}

export function useLineageBatch(
  lineageIds: readonly string[],
  options: {
    enabled?: boolean;
    temporalScope?: TemporalRef | null;
  } = {},
) {
  const runtime = useQuantityRuntimeBridge();
  const temporalScope = options.temporalScope ?? runtime.temporalScope;
  const uniqueLineageIds = Array.from(new Set(lineageIds)).filter(Boolean);
  return useQuery({
    queryKey: ["quantity-lineage-batch", uniqueLineageIds, temporalScope],
    queryFn: () => runtime.fetchLineageBatch(uniqueLineageIds, temporalScope),
    enabled: uniqueLineageIds.length > 0 && (options.enabled ?? true),
  });
}
