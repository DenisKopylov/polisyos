# `src/api/hooks` — endpoint hooks Runtime/Control API

This directory contains React Query hooks built on the `openapi-fetch` client.

## Hook Groups

- Runtime read:
  - `useHealth`
  - `useRuns`, `useRunDetails`, `useRunTimeline`, `useRunNodes`, `useRunLineage`, `useRunAgents`, `useRunWorkflow`, `useRunPredictiveCalibration`
  - `useNodeDebug`, `useGovernanceDebug`, `useRunErrors`
  - `useArtifactManifest`, `useArtifactContent`, `useArtifactSchema`, `useArtifactLineage`
- Control data:
  - `useSourceProfiles`, `useConnectors`, `useCacheStatus`, `useDataIndexStats`
  - `useResolveDataNeeds`, `useDiscoverDataSources`, `usePreviewFetchPlan`
  - `useDataCatalogSearch`, `useDataPromotionCandidates`
  - `useApprovePromotionCandidate`, `useRejectPromotionCandidate`
  - `useIngestData`
- Control runs/models:
  - `useLaunchRun`, `useLaunchNlRun`, `useLlmProfiles`
- Lex:
  - `useLexTrigger`, `useLexPipelineStatus`, `useLexGraphStats`, `useLexSearch`

## Conventions

- Each hook:
  - makes one API call;
  - throws `RuntimeApiRequestError` through `createRuntimeApiError` on failure;
  - returns a normalized payload (some runtime hooks are additionally validated with `zod` schemas from `../validators`).
- Query hooks use `queryKeys` from `../queryKeys`.
- Mutation hooks invalidate dependent query keys after a successful call.
- `useCreateRunPredictiveCalibration` sends a separate `intent_id`; a retry after an indeterminate response preserves the original request and refreshes the read.

## When to Update Hooks

When OpenAPI changes:

1. Regenerate `src/api/types.ts`.
2. Check hook signatures and endpoint paths.
3. Update `queryKeys` and `validators` if needed.

## Run-bound predictive calibration

- useRunPredictiveCalibration reads the fresh, profile-validated run attachment.
- useCreateRunPredictiveCalibration posts the strict candidate request and invalidates the read after success.
