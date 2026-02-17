# `src/api/hooks` — endpoint hooks Runtime/Control API

Папка содержит React Query hooks поверх `openapi-fetch` клиента.

## Группы hooks

- Runtime read:
  - `useHealth`
  - `useRuns`, `useRunDetails`, `useRunTimeline`, `useRunNodes`, `useRunLineage`, `useRunAgents`, `useRunWorkflow`
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

## Соглашения в этой папке

- Каждый hook:
  - делает один API-вызов;
  - бросает `RuntimeApiRequestError` через `createRuntimeApiError` при ошибке;
  - возвращает нормализованный payload (часть runtime hooks дополнительно валидируется `zod` схемами из `../validators`).
- Query hooks используют `queryKeys` из `../queryKeys`.
- Mutation hooks инвалидируют зависимые query-ключи после успешного вызова.

## Когда обновлять hooks

При изменении OpenAPI:
1. перегенерировать `src/api/types.ts`;
2. сверить сигнатуры hooks и endpoint paths;
3. при необходимости обновить `queryKeys` и `validators`.
