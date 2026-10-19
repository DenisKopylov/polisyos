import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { useQuantityRuntimeBridge } from "./QuantityRuntimeBridge";
import type {
  LineageBatchResponsePayload,
  LineageBatchSelector,
  LineageGraphView,
  ProfileBindingContext,
  QuantityValue,
  SelectedArtifactRef,
  TemporalRef,
} from "./quantity.types";

type TemporalScopeState = TemporalRef | null | undefined;

type LineageBindingRequest = {
  runId?: string;
  temporalScope: TemporalScopeState;
  responseTemporalScope: TemporalScopeState;
};

export function lineageIdsFromQuantities(quantities: readonly QuantityValue[]) {
  return lineageSelectorsFromQuantities(quantities).map(
    (selector) => selector.lineageId,
  );
}

export function lineageSelectorsFromQuantities(
  quantities: readonly QuantityValue[],
): LineageBatchSelector[] {
  const selectors = new Map<string, LineageBatchSelector>();
  for (const quantity of quantities) {
    const lineage = quantity.lineage;
    const lineageId = lineage.id;
    if (!lineageId || lineageId === "untraced") continue;
    const selector: LineageBatchSelector = {
      lineageId,
      selectedArtifactRef: selectedArtifactRef(lineage.artifact_ref),
      artifactRefProvenance: lineage.artifact_ref_provenance ?? null,
      sourceRunId: lineage.source_run_id ?? null,
    };
    selectors.set(lineageSelectorKey(selector), selector);
  }
  return [...selectors.values()];
}

export function selectedArtifactRef(
  value: unknown,
): SelectedArtifactRef | null {
  if (!isRecord(value)) return null;
  const artifactId = value.artifact_id;
  const kind = value.kind;
  const mediaType = value.media_type;
  const profile = value.manifest_profile_sha256;
  if (
    typeof artifactId !== "string" ||
    typeof kind !== "string" ||
    typeof mediaType !== "string" ||
    typeof profile !== "string" ||
    !/^sha256:[0-9a-f]{64}$/.test(profile)
  ) {
    return null;
  }
  return {
    artifact_id: artifactId,
    kind,
    media_type: mediaType,
    manifest_profile_sha256: profile,
  };
}

export function lineageSelectorKey(selector: LineageBatchSelector): string {
  const ref = selector.selectedArtifactRef;
  return JSON.stringify([
    selector.lineageId,
    ref === undefined
      ? ["omitted"]
      : ref === null
        ? ["null"]
        : [
            ref.artifact_id,
            ref.kind,
            ref.media_type,
            ref.manifest_profile_sha256,
          ],
    optionalIdentityValue(selector.artifactRefProvenance),
    optionalIdentityValue(selector.sourceRunId),
  ]);
}

export type ProfileBindingAdmission = {
  generation: number;
  outcome: "unadmitted" | "pending" | "admitted" | "rejected";
  graph?: BoundLineageQueryData;
};

export type BoundLineageQueryData = {
  meta?: LineageBatchResponsePayload["meta"];
  temporal_scope?: TemporalScopeState;
  lineage: LineageGraphView;
  profileBindingGeneration?: number;
};

const UNADMITTED_PROFILE_BINDING: ProfileBindingAdmission = {
  generation: 0,
  outcome: "unadmitted",
};

export function profileBindingIdentityKey(
  selector: LineageBatchSelector,
  runId: string | undefined,
  temporalScope: TemporalScopeState,
): string {
  return JSON.stringify([
    lineageSelectorKey(selector),
    runId === undefined ? ["omitted"] : ["value", runId],
    temporalKey(temporalScope),
  ]);
}

export function profileBindingAdmissionQueryKey(
  selector: LineageBatchSelector,
  runId: string | undefined,
  temporalScope: TemporalScopeState,
) {
  return [
    "quantity-lineage-admission",
    profileBindingIdentityKey(selector, runId, temporalScope),
  ] as const;
}

export function profileBindingAdmissionForQueryClient(
  queryClient: ReturnType<typeof useQueryClient>,
  selector: LineageBatchSelector,
  runId: string | undefined,
  temporalScope: TemporalScopeState,
): ProfileBindingAdmission {
  return (
    queryClient.getQueryData<ProfileBindingAdmission>(
      profileBindingAdmissionQueryKey(selector, runId, temporalScope),
    ) ?? UNADMITTED_PROFILE_BINDING
  );
}

export function useProfileBindingAdmission(
  selector: LineageBatchSelector,
  runId: string | undefined,
  temporalScope: TemporalScopeState,
): ProfileBindingAdmission {
  const query = useQuery<ProfileBindingAdmission>({
    queryKey: profileBindingAdmissionQueryKey(selector, runId, temporalScope),
    queryFn: () => Promise.resolve(UNADMITTED_PROFILE_BINDING),
    initialData: UNADMITTED_PROFILE_BINDING,
    enabled: false,
  });
  return query.data ?? UNADMITTED_PROFILE_BINDING;
}

export function useProfileBindingAdmissions(
  selectors: readonly LineageBatchSelector[],
  runId: string | undefined,
  temporalScope: TemporalScopeState,
): ProfileBindingAdmission[] {
  const queries = useQueries({
    queries: selectors.map((selector) => ({
      queryKey: profileBindingAdmissionQueryKey(selector, runId, temporalScope),
      queryFn: () => Promise.resolve(UNADMITTED_PROFILE_BINDING),
      initialData: UNADMITTED_PROFILE_BINDING,
      enabled: false,
    })),
  });
  return queries.map((query) => query.data ?? UNADMITTED_PROFILE_BINDING);
}

export function admittedProfileBindingContext(
  selector: LineageBatchSelector,
  lineage: LineageGraphView,
  request: LineageBindingRequest,
  admission: ProfileBindingAdmission,
  graphGeneration: number | undefined,
): ProfileBindingContext | null {
  if (
    admission.outcome !== "admitted" ||
    graphGeneration === undefined ||
    graphGeneration <= 0 ||
    admission.generation !== graphGeneration
  ) {
    return null;
  }
  const context = exactProfileBindingContext(selector, lineage, request);
  return context ? { ...context, admissionGeneration: graphGeneration } : null;
}

export function boundLineageQueryKey(
  selector: LineageBatchSelector,
  runId: string | undefined,
  temporalScope: TemporalScopeState,
) {
  return [
    "quantity-lineage-bound",
    profileBindingIdentityKey(selector, runId, temporalScope),
  ] as const;
}

/**
 * Return the complete server-bound profile context, or null when any member is
 * absent or differs. Unknown run, origin, or time values never act as wildcards.
 */
export function exactProfileBindingContext(
  selector: LineageBatchSelector,
  lineage: LineageGraphView,
  request: LineageBindingRequest,
): ProfileBindingContext | null {
  const selectedRef = selector.selectedArtifactRef;
  const sourceRunId = selector.sourceRunId;
  const origin = selector.artifactRefProvenance;
  if (
    !selectedRef ||
    !sourceRunId ||
    !origin ||
    !request.runId ||
    request.runId !== sourceRunId ||
    request.temporalScope === undefined ||
    request.responseTemporalScope === undefined
  ) {
    return null;
  }
  if (
    lineage.id !== selector.lineageId ||
    lineage.profile_binding_status !== "verified" ||
    !sameArtifactRef(lineage.selected_artifact_ref, selectedRef) ||
    lineage.source_run_id !== sourceRunId ||
    lineage.artifact_ref_provenance !== origin ||
    !sameTemporalScope(request.responseTemporalScope, request.temporalScope)
  ) {
    return null;
  }
  return {
    status: "verified",
    lineageId: selector.lineageId,
    selectedArtifactRef: selectedRef,
    sourceRunId,
    origin,
    temporalScope: request.temporalScope,
  };
}

export function sameProfileBindingContext(
  left: ProfileBindingContext,
  right: ProfileBindingContext,
): boolean {
  return (
    sameProfileBindingIdentity(left, right) &&
    left.admissionGeneration === right.admissionGeneration
  );
}

export function sameProfileBindingIdentity(
  left: ProfileBindingContext,
  right: ProfileBindingContext,
): boolean {
  return (
    left.status === right.status &&
    left.lineageId === right.lineageId &&
    sameArtifactRef(left.selectedArtifactRef, right.selectedArtifactRef) &&
    left.sourceRunId === right.sourceRunId &&
    left.origin === right.origin &&
    sameTemporalScope(left.temporalScope, right.temporalScope)
  );
}

/**
 * Confirm that a projected quantity still carries the exact profile context
 * used to admit its trust metadata.
 */
export function quantityHasExactProfileTrust(quantity: QuantityValue): boolean {
  const binding = quantity.profile_binding_context;
  const metadata = quantity.lineage.trust_metadata;
  return Boolean(
    quantity.profile_binding_status === "verified" &&
    binding?.status === "verified" &&
    binding.lineageId === quantity.lineage.id &&
    binding.selectedArtifactRef &&
    binding.sourceRunId &&
    binding.origin &&
    Number.isInteger(binding.admissionGeneration) &&
    (binding.admissionGeneration ?? 0) > 0 &&
    binding.temporalScope !== undefined &&
    sameArtifactRef(
      binding.selectedArtifactRef,
      quantity.lineage.artifact_ref,
    ) &&
    binding.sourceRunId === quantity.lineage.source_run_id &&
    binding.origin === quantity.lineage.artifact_ref_provenance &&
    metadata &&
    sameTemporalScope(metadata.temporal_scope, binding.temporalScope),
  );
}

export function alignLineageBatchResponses(
  selectors: readonly LineageBatchSelector[],
  response: LineageBatchResponsePayload,
  options: {
    runId?: string;
    temporalScope?: TemporalScopeState;
  } = {},
): Array<{ requestIndex: number; lineage: LineageGraphView }> {
  const lineages = response.lineages ?? [];
  const resolutions = response.lineage_resolutions;
  if (resolutions != null && resolutions.length !== lineages.length) {
    throw new Error(
      "Lineage batch resolutions do not align with returned lineages",
    );
  }
  if (!sameTemporalScope(response.temporal_scope, options.temporalScope)) {
    throw new Error("Lineage batch temporal scope differs from its request");
  }

  const profileBindingRequested =
    options.runId !== undefined ||
    selectors.some(
      (selector) =>
        selector.selectedArtifactRef != null ||
        selector.sourceRunId != null ||
        selector.artifactRefProvenance != null,
    );
  const aligned: Array<{ requestIndex: number; lineage: LineageGraphView }> =
    [];
  let requestIndex = 0;
  for (const [responseIndex, lineage] of lineages.entries()) {
    const resolution = resolutions?.[responseIndex];
    if (resolution && resolution.resolved_lineage_id !== lineage.id) {
      throw new Error(
        "Lineage batch resolution does not match its returned lineage",
      );
    }
    const requestedId = resolution?.requested_lineage_id ?? lineage.id;
    let matchedIndex = -1;
    for (
      let candidate = requestIndex;
      candidate < selectors.length;
      candidate += 1
    ) {
      const selector = selectors[candidate];
      if (selector.lineageId !== requestedId) continue;
      if (
        profileBindingRequested &&
        !lineageMatchesSelector(
          lineage,
          selector,
          options,
          response.temporal_scope,
        )
      ) {
        continue;
      }
      matchedIndex = candidate;
      break;
    }
    if (matchedIndex < 0) {
      throw new Error(
        "Lineage batch response contains an unrequested or unbound item",
      );
    }
    const selector = selectors[matchedIndex];
    if (!selector) {
      throw new Error("Lineage batch response lost its requested selector");
    }
    if (profileBindingRequested) {
      if (
        !lineageMatchesSelector(
          lineage,
          selector,
          options,
          response.temporal_scope,
        )
      ) {
        throw new Error("Lineage response does not match the selected profile");
      }
      if (
        lineage.trust_metadata &&
        !sameTemporalScope(
          lineage.trust_metadata.temporal_scope,
          response.temporal_scope,
        )
      ) {
        throw new Error(
          "Lineage trust metadata has a different temporal scope",
        );
      }
    }
    aligned.push({ requestIndex: matchedIndex, lineage });
    requestIndex = matchedIndex + 1;
  }
  return aligned;
}

function lineageMatchesSelector(
  lineage: LineageGraphView,
  selector: LineageBatchSelector,
  options: { runId?: string; temporalScope?: TemporalScopeState },
  responseTemporalScope: TemporalScopeState,
): boolean {
  const expectedRef = selector.selectedArtifactRef ?? null;
  if (expectedRef === null) {
    return (
      lineage.profile_binding_status === "not_established" &&
      lineage.trust_metadata == null &&
      lineage.selected_artifact_ref == null &&
      lineage.artifact_ref_provenance == null &&
      lineage.source_run_id == null
    );
  }
  const binding = exactProfileBindingContext(selector, lineage, {
    runId: options.runId,
    temporalScope: options.temporalScope,
    responseTemporalScope,
  });
  return (
    binding !== null &&
    (!lineage.trust_metadata ||
      sameTemporalScope(
        lineage.trust_metadata.temporal_scope,
        responseTemporalScope,
      ))
  );
}

function sameArtifactRef(left: unknown, right: unknown): boolean {
  const leftRef = selectedArtifactRef(left);
  const rightRef = selectedArtifactRef(right);
  return Boolean(
    leftRef &&
    rightRef &&
    leftRef.artifact_id === rightRef.artifact_id &&
    leftRef.kind === rightRef.kind &&
    leftRef.media_type === rightRef.media_type &&
    leftRef.manifest_profile_sha256 === rightRef.manifest_profile_sha256,
  );
}

export function sameTemporalScope(
  left: TemporalScopeState,
  right: TemporalScopeState,
): boolean {
  if (left === undefined || right === undefined) return left === right;
  if (left === null || right === null) return left === right;
  const leftScope = temporalParts(left);
  const rightScope = temporalParts(right);
  return JSON.stringify(leftScope) === JSON.stringify(rightScope);
}

function temporalParts(value: TemporalRef): string[][] {
  return [
    temporalIdentityValue(value.valid_at),
    temporalIdentityValue(value.tx_at),
    temporalIdentityValue(value.branch),
    temporalIdentityValue(value.snapshot_id),
    temporalIdentityValue(value.scenario_id),
  ];
}

function temporalKey(scope: TemporalScopeState): string {
  if (scope === undefined) return JSON.stringify(["omitted"]);
  if (scope === null) return JSON.stringify(["explicit-null"]);
  return JSON.stringify(["scope", temporalParts(scope)]);
}

function temporalIdentityValue(value: unknown): string[] {
  if (value === undefined) return ["omitted"];
  if (value === null) return ["null"];
  if (typeof value === "string") return ["value", value];
  return ["invalid", typeof value];
}

function optionalIdentityValue(value: string | null | undefined): unknown[] {
  if (value === undefined) return ["omitted"];
  if (value === null) return ["null"];
  return ["value", value];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function useLineageBatch(
  selectors: readonly LineageBatchSelector[],
  options: {
    enabled?: boolean;
    runId?: string;
    temporalScope?: TemporalScopeState;
  } = {},
) {
  const runtime = useQuantityRuntimeBridge();
  const queryClient = useQueryClient();
  const temporalScope = Object.hasOwn(options, "temporalScope")
    ? options.temporalScope
    : runtime.temporalScope;
  const uniqueSelectors = Array.from(
    new Map(
      selectors.map((selector) => [lineageSelectorKey(selector), selector]),
    ).values(),
  );
  const runId = options.runId;
  return useQuery({
    queryKey: [
      "quantity-lineage-batch",
      uniqueSelectors.map((selector) =>
        profileBindingIdentityKey(selector, runId, temporalScope),
      ),
    ],
    queryFn: async () => {
      const admissions = uniqueSelectors.map((selector) => ({
        selector,
        generation: beginProfileBindingAdmission(
          queryClient,
          selector,
          runId,
          temporalScope,
        ),
      }));
      try {
        const response = await runtime.fetchLineageBatch(
          uniqueSelectors,
          runId,
          temporalScope,
        );
        const aligned = alignLineageBatchResponses(uniqueSelectors, response, {
          runId,
          temporalScope,
        });
        const byRequestIndex = new Map(
          aligned.map(({ requestIndex, lineage }) => [requestIndex, lineage]),
        );
        for (const [
          requestIndex,
          { selector, generation },
        ] of admissions.entries()) {
          const lineage = byRequestIndex.get(requestIndex);
          const profileBindingContext = lineage
            ? exactProfileBindingContext(selector, lineage, {
                runId,
                temporalScope,
                responseTemporalScope: response.temporal_scope,
              })
            : null;
          const graphData = lineage
            ? {
                meta: response.meta,
                temporal_scope: response.temporal_scope,
                lineage,
                profileBindingGeneration: generation,
              }
            : undefined;
          settleProfileBindingAdmission(
            queryClient,
            selector,
            runId,
            temporalScope,
            generation,
            profileBindingContext ? "admitted" : "rejected",
            graphData,
          );
        }
        return response;
      } catch (error) {
        for (const { selector, generation } of admissions) {
          settleProfileBindingAdmission(
            queryClient,
            selector,
            runId,
            temporalScope,
            generation,
            "rejected",
          );
        }
        throw error;
      }
    },
    enabled: uniqueSelectors.length > 0 && (options.enabled ?? true),
  });
}

export function useBoundLineage(
  selector: LineageBatchSelector,
  options: {
    enabled?: boolean;
    runId?: string;
    temporalScope?: TemporalScopeState;
  } = {},
) {
  const runtime = useQuantityRuntimeBridge();
  const queryClient = useQueryClient();
  const temporalScope = Object.hasOwn(options, "temporalScope")
    ? options.temporalScope
    : runtime.temporalScope;
  const runId = options.runId;
  return useQuery({
    queryKey: boundLineageQueryKey(selector, runId, temporalScope),
    queryFn: async () => {
      const generation = beginProfileBindingAdmission(
        queryClient,
        selector,
        runId,
        temporalScope,
      );
      try {
        const response = await runtime.fetchLineageBatch(
          [selector],
          runId,
          temporalScope,
        );
        const [entry] = alignLineageBatchResponses([selector], response, {
          runId,
          temporalScope,
        });
        if (!entry || entry.requestIndex !== 0) {
          throw new Error("The selected lineage profile was not returned");
        }
        const profileBindingContext = exactProfileBindingContext(
          selector,
          entry.lineage,
          {
            runId,
            temporalScope,
            responseTemporalScope: response.temporal_scope,
          },
        );
        const settled = settleProfileBindingAdmission(
          queryClient,
          selector,
          runId,
          temporalScope,
          generation,
          profileBindingContext ? "admitted" : "rejected",
          {
            meta: response.meta,
            temporal_scope: response.temporal_scope,
            lineage: entry.lineage,
            profileBindingGeneration: generation,
          },
        );
        const currentAdmission = profileBindingAdmissionForQueryClient(
          queryClient,
          selector,
          runId,
          temporalScope,
        );
        if (!settled && currentAdmission.outcome === "admitted") {
          if (
            currentAdmission.graph?.profileBindingGeneration ===
            currentAdmission.generation
          ) {
            return currentAdmission.graph;
          }
        }
        return {
          meta: response.meta,
          temporal_scope: response.temporal_scope,
          lineage: entry.lineage,
          profileBindingGeneration: settled ? generation : undefined,
        } satisfies BoundLineageQueryData;
      } catch (error) {
        const settled = settleProfileBindingAdmission(
          queryClient,
          selector,
          runId,
          temporalScope,
          generation,
          "rejected",
        );
        if (!settled) {
          const currentAdmission = profileBindingAdmissionForQueryClient(
            queryClient,
            selector,
            runId,
            temporalScope,
          );
          if (
            currentAdmission.outcome === "admitted" &&
            currentAdmission.graph?.profileBindingGeneration ===
              currentAdmission.generation
          ) {
            return currentAdmission.graph;
          }
        }
        throw error;
      }
    },
    enabled: Boolean(selector.lineageId) && (options.enabled ?? true),
    staleTime: 30_000,
  });
}

export function useAdmittedBoundLineage(
  selector: LineageBatchSelector,
  options: {
    enabled?: boolean;
    runId?: string;
    temporalScope?: TemporalScopeState;
  } = {},
) {
  const query = useBoundLineage(selector, options);
  const runtime = useQuantityRuntimeBridge();
  const temporalScope = Object.hasOwn(options, "temporalScope")
    ? options.temporalScope
    : runtime.temporalScope;
  const runId = options.runId;
  const admission = useProfileBindingAdmission(selector, runId, temporalScope);
  const profileBindingContext = query.data
    ? admittedProfileBindingContext(
        selector,
        query.data.lineage,
        {
          runId,
          temporalScope,
          responseTemporalScope: query.data.temporal_scope,
        },
        admission,
        query.data.profileBindingGeneration,
      )
    : null;
  return { ...query, profileBindingContext };
}

function beginProfileBindingAdmission(
  queryClient: ReturnType<typeof useQueryClient>,
  selector: LineageBatchSelector,
  runId: string | undefined,
  temporalScope: TemporalScopeState,
): number {
  const key = profileBindingAdmissionQueryKey(selector, runId, temporalScope);
  const prior =
    queryClient.getQueryData<ProfileBindingAdmission>(key) ??
    UNADMITTED_PROFILE_BINDING;
  const next = {
    generation: prior.generation + 1,
    outcome: "pending",
  } as const;
  queryClient.setQueryData<ProfileBindingAdmission>(key, next);
  return next.generation;
}

function settleProfileBindingAdmission(
  queryClient: ReturnType<typeof useQueryClient>,
  selector: LineageBatchSelector,
  runId: string | undefined,
  temporalScope: TemporalScopeState,
  generation: number,
  outcome: "admitted" | "rejected",
  graph?: BoundLineageQueryData,
): boolean {
  const key = profileBindingAdmissionQueryKey(selector, runId, temporalScope);
  const current =
    queryClient.getQueryData<ProfileBindingAdmission>(key) ??
    UNADMITTED_PROFILE_BINDING;
  if (current.generation !== generation || current.outcome !== "pending") {
    return false;
  }
  if (outcome === "admitted" && !graph) {
    return false;
  }
  if (graph) {
    queryClient.setQueryData<BoundLineageQueryData>(
      boundLineageQueryKey(selector, runId, temporalScope),
      graph,
    );
  }
  queryClient.setQueryData<ProfileBindingAdmission>(key, {
    generation,
    outcome,
    ...(outcome === "admitted" && graph ? { graph } : {}),
  });
  return true;
}
