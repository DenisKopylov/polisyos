# `runtime-dashboard/src` — карта модулей

Этот уровень хранит runtime/control-plane логику приложения без сборочных артефактов.

## Структура

| Путь             | Роль                                                                             |
| ---------------- | -------------------------------------------------------------------------------- |
| `src/main.tsx`   | Точка входа React и глобальные стили                                             |
| `src/App.tsx`    | Вход в `app/` shell и data-router                                                |
| `src/app/`       | Workspace registry, providers, layout, data-router, loaders, typed search params |
| `src/features/`  | Вертикальные feature slices: route shells, domain helpers, local components      |
| `src/shared/`    | Shared UI primitives, generic error boundaries, low-level reusable pieces        |
| `src/api/`       | HTTP-клиент, hooks, query keys, validators, generated OpenAPI types              |
| `src/lib/`       | Общие утилиты, capability helpers и доменные адаптеры payload -> view model      |
| `src/i18n/`      | Locale provider, catalogs, locale persistence                                    |
| `src/styles.css` | Глобальные стили и токены темы                                                   |

## Архитектурные принципы

- Workspaces описываются единым registry в `src/app/workspaces.ts`: path, aliases, layout, requiredCapabilities, feature flags и bootstrap metadata.
- Route-level код живёт внутри feature slices; `src/pages/` и `src/components/` больше не считаются valid extension points и блокируются архитектурными проверками.
- Data fetch orchestration идёт через route loaders (`src/app/routes/loaders.ts`) и extracted priming helpers (`src/app/routes/prefetch.ts`): loaders и viewport/intent prefetch используют один и тот же bootstrap path.
- Cross-feature импорты идут через `@/*` alias и публичные entrypoints `src/features/*/index.ts`.
- Новые независимые feature-блоки по умолчанию используют `FeatureAsyncBoundary` (`Suspense` + `FeatureErrorBoundary`); `AsyncSection` остаётся legacy-паттерном для interactive/conditional query UX.
- Парсинг сложных artifact payload-ов остаётся в `src/lib/domain/*`.
- React Query хранит только server-derived cache и optimistic server updates; layout preferences, draft inputs, selection и scroll-local UI state идут через Zustand stores в `src/app/state/*` и `src/features/*/state/*`.
- Virtual scrolling для больших tables/lists строится через shared primitives `VirtualTable` и `VirtualList`, но не меняет URL/cursor pagination contract сам по себе.
- Web Vitals и route transition telemetry публикуются из `TelemetryProvider`; CWV остаются initial/hard-navigation сигналом, а SPA route latency измеряется событиями `route.transition.*` и custom metrics `time_to_decision_ms` / `time_to_insight_ms`.
- Offline-first v1 ограничен static asset caching через service worker, IndexedDB drafts и queue-aware promotion decisions; authenticated API GET cache не считается offline contract.
- Ошибки API нормализуются в `src/api/http.ts` и рендерятся через `src/shared/ui`.
- Structured logging идёт через `src/shared/telemetry/logger.ts`; dev пишет в console, prod отправляет envelope в telemetry sink и Sentry breadcrumbs/exceptions.
- Shared слой не импортирует `features` или `app`; `lib` не тянет UI.
- Архитектурные ограничения валидируются через `eslint-plugin-boundaries`, `dependency-cruiser` и `scripts/check-architecture.mjs`.

## App-level Providers

- `AppProviders` собирает `QueryClientProvider`, `LocaleProvider`, `TelemetryProvider`, `AuthSessionProvider`, `NetworkStatusProvider`, `OfflineQueueProvider`, `FeatureFlagProvider`, `ThemeProvider`.
- `RuntimeApiProvider` и `RunsLiveProvider` поднимаются на route shell уровне, чтобы chromeless/login surface не тащил лишние workspace зависимости.
- `ThemeProvider` хранит `light | dark | system` preference и пишет `data-theme` на `documentElement`.
- `TelemetryProvider` публикует `useTelemetry`, `markUiMilestone`, `measureUiLatency`, route-context enrichment и Web Vitals events (`INP/LCP/CLS/TTFB`, optional legacy `FID` when available).
- `AuthSessionProvider` даёт `useAuthSession`; transport слой живёт в `src/app/auth/authSession.ts` и отвечает за single-flight refresh/replay.
- `FeatureFlagProvider` определяет UI/workspace availability без изменения feature code.
- `NetworkStatusProvider` централизует online/offline и connection-quality signals для prefetch gating и offline queue flush.

## Build и CI артефакты

- `scripts/postbuild-security.mjs` добавляет SRI к `index.html` assets и генерирует CSP `Report-Only` header artifact для edge/static host.
- `scripts/emit-bundle-stats.mjs` и `scripts/compare-bundle-stats.mjs` обслуживают PR bundle diff comments.
- `scripts/run-audit.mjs` применяет advisory allowlist из `audit-allowlist.json` и пишет machine-readable + markdown summary reports.
- `scripts/summarize-lighthouse.mjs` и `scripts/summarize-playwright-visual.mjs` делают review-friendly PR comments/artifacts поверх Lighthouse и visual regression jobs.

## Куда добавлять новый функционал

- Новый экран/route: `src/features/<feature>/routes/*` + экспорт из feature barrel + запись в `src/app/routes/routes.tsx`.
- Новый endpoint: hook в `src/api/hooks/*` + `queryKeys` (если query) + optional validator.
- Новый reusable UI primitive: `src/shared/ui/*`.
- Новый доменный viewer: компонент в соответствующей `src/features/*/components/*` + адаптер в `src/lib/domain/*` при необходимости.
- Новый workspace bootstrap query: описать key в `src/app/workspaces.ts`, собрать queryOptions helper в `src/api/hooks/*`, затем подключить loader.
- Новый typed search param contract: `src/app/routes/searchParams.ts` через `zod`.
