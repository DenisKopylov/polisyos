import { useMemo } from "react";

import { useCompareRuns } from "@/api/hooks/useCompareRuns";
import type { CompareRunsPayload } from "@/api/validators";
import type { QuantityValue } from "@/shared/ui/quantity/quantity.types";
import { selectedArtifactRef } from "@/shared/ui/quantity/useLineageBatch";

import type { CompareRunsDelta, DeltaQuantity } from "./compare-types";

type WireQuantity = NonNullable<CompareRunsDelta["a"]>;

export function toDisplayDeltas(
  payload: CompareRunsPayload | undefined,
): DeltaQuantity[] {
  if (!payload?.deltas) return [];
  const temporalScope = payload.temporal_scope;
  return payload.deltas.map((delta) => ({
    ...delta,
    a: toDisplayQuantity(delta.a, temporalScope),
    b: toDisplayQuantity(delta.b, temporalScope),
    delta_absolute: toDisplayQuantity(delta.delta_absolute, temporalScope),
    delta_relative: toDisplayQuantity(delta.delta_relative, temporalScope),
  }));
}

function toDisplayQuantity(
  quantity: WireQuantity | null | undefined,
  temporalScope: CompareRunsPayload["temporal_scope"],
): QuantityValue | null | undefined {
  if (quantity == null) return quantity;

  const { artifact_ref: rawArtifactRef, ...lineageWithoutArtifactRef } =
    quantity.lineage;
  const normalizedArtifactRef = selectedArtifactRef(rawArtifactRef);
  if (rawArtifactRef != null && normalizedArtifactRef === null) {
    throw new TypeError(
      "Comparison quantity carries an invalid selected artifact reference",
    );
  }

  return {
    ...quantity,
    lineage: {
      ...lineageWithoutArtifactRef,
      ...(rawArtifactRef === undefined
        ? {}
        : { artifact_ref: normalizedArtifactRef }),
    },
    profile_binding_status: "not_established",
    profile_binding_temporal_scope: temporalScope,
  };
}

export function useDiffData(
  runAId: string | undefined,
  runBId: string | undefined,
) {
  const query = useCompareRuns(runAId, runBId);
  const displayDeltas = useMemo(
    () => toDisplayDeltas(query.data),
    [query.data],
  );
  return { ...query, displayDeltas };
}
