# `runtime-dashboard`

`runtime-dashboard` это React/TypeScript control-plane для Runtime API. Базовая цель приложения: typed end-to-end data flow от FastAPI/OpenAPI до React Query и route-level workspace surfaces без размывания архитектурных границ.

## Что покрывает UI

| Route                    | Назначение                                                                             |
| ------------------------ | -------------------------------------------------------------------------------------- |
| `/`                      | `Command Center`: операторская очередь по runs, governance, evidence и decision review |
| `/compose`               | `Scenario Composer`: запуск `workflow` и `natural-language` сценариев                  |
| `/runs`                  | `Runs & Decisions`: explorer с фильтрами и переходами в decision workspace             |
| `/runs/:runId`           | Детальная карточка run с decision/governance/debug/workflow surfaces                   |
| `/artifacts/:artifactId` | Artifact inspector с registry-based viewers для runtime artifacts                      |
| `/evidence`              | `Evidence Fabric`: resolve/discover/preview/promotion + connectors/source profiles     |
| `/knowledge`             | `Lex & Knowledge`: Lex pipeline, graph stats и semantic search                         |
| `/platform`              | `Platform Health`: runtime health, capability manifest и operational posture           |

Legacy URLs `/launch`, `/sources`, `/data`, `/lex`, `/health` сохранены только как redirects.

## Legacy Migration Matrix

| Legacy page             | Feature replacement                                       | Compatibility contract                                          |
| ----------------------- | --------------------------------------------------------- | --------------------------------------------------------------- |
| `Dashboard.tsx`         | `src/features/dashboard/routes/DashboardPage.tsx`         | canonical `/`                                                   |
| `LaunchRun.tsx`         | `src/features/composer/routes/LaunchRunPage.tsx`          | redirect `/launch -> /compose`                                  |
| `RunsList.tsx`          | `src/features/runs/routes/RunsListPage.tsx`               | canonical `/runs`                                               |
| `RunDetail.tsx`         | `src/features/runs/routes/RunDetailLayout.tsx` + `tabs/*` | canonical `/runs/:runId/:tab`, legacy tab query stays supported |
| `ArtifactInspector.tsx` | `src/features/artifacts/routes/ArtifactInspectorPage.tsx` | canonical `/artifacts/:artifactId`                              |
| `LexKnowledgeGraph.tsx` | `src/features/lex/routes/LexKnowledgeGraphPage.tsx`       | redirect `/lex -> /knowledge`                                   |
| `SystemHealth.tsx`      | `src/features/platform/routes/PlatformHealthPage.tsx`     | redirect `/health -> /platform`                                 |
| `SourcesManagement.tsx` | `src/features/evidence/routes/EvidenceFabricPage.tsx`     | redirect `/sources -> /evidence`                                |
| `DataManagement.tsx`    | `src/features/evidence/routes/EvidenceFabricPage.tsx`     | redirect `/data -> /evidence`                                   |

## Архитектура модулей

Детализация находится в `src/README.md`.

Канонические слои:

- `src/app/*` — app shell, providers, workspace registry, router, route loaders.
- `src/features/*` — vertical feature slices c public API через `src/features/<feature>/index.ts`.
- `src/shared/*` — shared UI и shared components без зависимости на feature/app.
- `src/api/*` — transport, hooks, query keys, validators, optimistic update helpers.
- `src/lib/*` — domain helpers, feature flags, capability utils, non-UI shared logic.
- `src/i18n/*` — locale catalogs и provider.

Guardrails:

- `src/pages/*` и `src/components/*` считаются legacy; архитектурные проверки падают и на импортах, и на самом появлении файлов в этих директориях.
- cross-feature imports разрешены только через public barrel `index.ts`.
- `shared` и `lib` не импортируют `features` или `app`.
- workspace bootstrap живёт в `src/app/workspaces.ts`, а data orchestration в route loaders.

## API и контрактная стратегия

- Транспорт: `openapi-fetch` (`src/api/client.ts`).
- Типы: `src/api/types.ts` (генерируется из `schemas/runtime_api_v1.openapi.json`).
- Capability manifest: `/api/v1/control/capabilities` приходит через тот же generated OpenAPI contract, без отдельного transport layer.
- Кэш и состояние: React Query (`queryKeys`, invalidate после mutation).
- Route bootstrap: React Router loaders вызывают `queryClient.ensureQueryData(...)` для workspace/run entry-point данных.
- Ошибки: единый `RuntimeApiRequestError` (`src/api/http.ts`).
- Валидация:
  - runtime read-paths валидируются через `zod` (`src/api/validators.ts`);
  - control-plane endpoints используют OpenAPI-typed payloads.

Дополнительные app-level слои:

- `FeatureFlagProvider` — typed env-driven flags и workspace gating.
- `ThemeProvider` — `light | dark | system` через `data-theme`.
- `TelemetryProvider` — Web Vitals, structured telemetry, custom UI latency metrics и runtime incident hooks.
- `AuthSessionProvider` — in-memory access token, single-flight silent refresh и one-shot request replay через refresh endpoint.
- `RunsLiveProvider` — live transport с degraded/polling fallback.

## Команды

```bash
npm ci --ignore-scripts
npm run generate:api
npm run typecheck
npm run lint
npm run format:check
npm run check:architecture
npm run test:components
npm run test:coverage
npm run test:a11y
npm run build
npm run dev
```

Дополнительно:

```bash
npm run preview
npm run dev:mock
npm run build-storybook
npm run test:journeys
npm run test:journeys:smoke
npm run test:visual
npm run analyze:bundle
npm run check:bundle
npm run bundle:stats
npm run lighthouse:ci
npm run audit:ci
```

## Test Taxonomy

- `frontend component`: `npm run test:components`
- `frontend journey`: `npm run test:journeys`
- `visual`: `npm run test:visual`

Shared Playwright semantics:

- `@smoke`: smallest representative confidence slice
- `@slow`: intentionally outside the fastest loop
- `@flaky`: unstable and needs owner follow-up
- `@quarantine`: excluded by default; opt in with `PLAYWRIGHT_INCLUDE_QUARANTINE=1`

If a Playwright test uses `@flaky` or `@quarantine`, the exact tagged test title must also appear as a `runner = "playwright"` selector in [`tests/quarantine.toml`](/Users/deniskopylov/polisyos/policy-engine/tests/quarantine.toml). CI validates this mapping.

Explicit quarantine selectors:

```bash
npm run test:journeys:quarantine
npm run test:journeys:flaky
npm run test:visual:quarantine
```

`dev:mock` только выставляет `VITE_USE_MOCKS=true`; встроенных mock-handlers в репозитории нет.

## Quality Gates

Frontend CI теперь должен проверять:

- `typecheck`
- `lint`
- `format:check`
- `check:architecture`
- `test:coverage`
- `build`
- `build-storybook`
- `check:bundle`
- `bundle diff` PR summary
- `Lighthouse CI` PR summary
- `dependency audit` PR artifact/comment
- `test:journeys:smoke`
- `test:visual` + diff artifacts
- `generate:api` drift against checked-in `src/api/types.ts`

Локальные git hooks через `lefthook`:

- `pre-commit`: `prettier --write` + `eslint --fix` по staged файлам
- `pre-push`: `typecheck` + `vitest run`

## Генерация API типов

```bash
./scripts/generate-api-client.sh
```

Скрипт:

- читает `schemas/runtime_api_v1.openapi.json`;
- обновляет `frontend/runtime-dashboard/src/api/types.ts`.

Изменение Runtime API считается завершённым только после синхронного обновления:

- `schemas/runtime_api_v1.openapi.json`;
- `frontend/runtime-api-client/runtimeApiClient.ts/js`;
- `frontend/runtime-dashboard/src/api/types.ts`.

## Конфигурация Runtime API

- Vite proxy по умолчанию: `http://127.0.0.1:8000`.
- Переменная `RUNTIME_API_URL` меняет proxy target в dev-сервере.
- Переменная `VITE_RUNTIME_API_URL` задает базовый URL напрямую для `openapi-fetch`.
- `VITE_AUTH_REFRESH_URL` включает silent refresh flow; refresh token остаётся backend-managed `HttpOnly` cookie.
- `frontend/runtime-dashboard/.env.example` — безопасная стартовая точка только для public `VITE_*` config; CI/release secrets вроде `SENTRY_AUTH_TOKEN` в frontend `.env` не хранятся.

## Observability и security artifacts

- `VITE_SENTRY_DSN`, `VITE_SENTRY_ENVIRONMENT`, `VITE_SENTRY_RELEASE` включают browser-side Sentry и release attribution.
- Production build использует hidden sourcemaps; upload в Sentry происходит только если на CI заданы `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`.
- После `npm run build` postbuild script добавляет SRI к HTML-referenced assets и пишет `dist/security/csp-report-only.txt` + `dist/security/headers.json` для edge/static-host конфигурации.
- `time_to_decision_ms` и `time_to_insight_ms` публикуются как custom performance telemetry поверх route transition start, а не как Core Web Vitals.

## Ограничения

- Silent refresh зависит от backend refresh endpoint и CSRF contract; UI не хранит refresh token в JS storage.
- Persisted UI state ограничен locale/theme preferences и route/search state.
- Часть control-plane payloads рендерится best-effort (без доменной валидации уровня runtime validators).
- Feature flags пока локальные/env-driven; remote manifest остаётся backend dependency.
