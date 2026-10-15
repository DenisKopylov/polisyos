# `runtime-dashboard/src` — Module Map

This layer contains the application's runtime and control-plane logic, excluding build artifacts.

## Structure

| Path                 | Role                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------- |
| `src/main.tsx`       | React entry point and global styles                                                    |
| `src/App.tsx`        | Entry point to the `app/` shell and data router                                        |
| `src/app/`           | Workspace registry, providers, layout, data-router, loaders, typed search params       |
| `src/features/`      | Vertical feature slices: route shells, domain helpers, and local components            |
| `src/shared/`        | Shared UI primitives, i18n, generic error boundaries, low-level reusable pieces        |
| `src/shared/lib/`    | Shared utilities, capability helpers, and domain adapters from payloads to view models |
| `src/shared/charts/` | Shared chart primitives, stories, uncertainty renderers, palettes                      |
| `src/shared/i18n/`   | Locale provider, catalogs, ICU messages, locale persistence                            |
| `src/api/`           | HTTP client, hooks, query keys, validators, and generated OpenAPI types                |
| `src/styles.css`     | Global styles and theme tokens                                                         |

## Architecture Principles

- Workspaces are described by the single registry in `src/app/workspaces.ts`: path, aliases, layout, requiredCapabilities, feature flags, and bootstrap metadata.
- Route-level code lives inside feature slices; `src/pages/` and `src/components/` are no longer valid extension points and are blocked by architecture checks.
- Data-fetch orchestration runs through route loaders (`src/app/routes/loaders.ts`) and extracted priming helpers (`src/app/routes/prefetch.ts`): loaders and viewport/intent prefetch share the same bootstrap path.
- Cross-feature imports use the `@/*` alias and public entry points in `src/features/*/index.ts`.
- New independent feature blocks use `FeatureAsyncBoundary` (`Suspense` + `FeatureErrorBoundary`) by default; `AsyncSection` remains a legacy pattern for interactive or conditional-query UX.
- Parsing complex artifact payloads remains in `src/shared/lib/domain/*`.
- React Query stores only server-derived cache and optimistic server updates; layout preferences, draft inputs, selection, and scroll-local UI state use Zustand stores in `src/app/state/*` and `src/features/*/state/*`.
- Virtual scrolling for large tables and lists uses the shared `VirtualTable` and `VirtualList` primitives, but does not by itself change the URL/cursor pagination contract.
- Web Vitals and route-transition telemetry are published by `TelemetryProvider`; CWV remains an initial/hard-navigation signal, while SPA route latency is measured with `route.transition.*` events and the custom metrics `time_to_decision_ms` / `time_to_insight_ms`.
- Offline-first v1 is limited to static-asset caching through the service worker and IndexedDB drafts; authenticated API GET caching is not an offline contract.
- API errors are normalized in `src/api/http.ts` and rendered through `src/shared/ui`.
- Structured logging uses `src/shared/telemetry/logger.ts`; development writes to the console, while production sends an envelope to the telemetry sink and Sentry breadcrumbs/exceptions.
- The shared layer does not import `features` or `app`; `src/shared/lib` does not depend on UI.
- Architecture constraints are validated by `eslint-plugin-boundaries`, `dependency-cruiser`, and `scripts/check-architecture.mjs`.

## App-level Providers

- `AppProviders` composes `QueryClientProvider`, `LocaleProvider`, `TelemetryProvider`, `AuthSessionProvider`, `NetworkStatusProvider`, `FeatureFlagProvider`, and `ThemeProvider`.
- `RuntimeApiProvider` and `RunsLiveProvider` are mounted at the route-shell level so the chromeless/login surface does not pull in unnecessary workspace dependencies.
- `ThemeProvider` stores the `light | dark | system` preference and writes `data-theme` to `documentElement`.
- `TelemetryProvider` exposes `useTelemetry`, `markUiMilestone`, `measureUiLatency`, route-context enrichment, and Web Vitals events (`INP/LCP/CLS/TTFB`, with optional legacy `FID` when available).
- `AuthSessionProvider` exposes `useAuthSession`; the transport layer lives in `src/app/auth/authSession.ts` and handles single-flight refresh/replay.
- `FeatureFlagProvider` determines UI/workspace availability without changing feature code.
- `NetworkStatusProvider` centralizes online/offline and connection-quality signals for prefetch gating.
- `src/app/state/*` remains the persistence-only layer for app-wide Zustand stores; `src/app/providers/*` owns React context, runtime effects, and composition. Providers may read stores, but stores do not import providers.

## Build and CI Artifacts

- `scripts/postbuild-security.mjs` adds SRI to `index.html` assets and generates a CSP `Report-Only` header artifact for the edge/static host.
- `scripts/emit-bundle-stats.mjs` and `scripts/compare-bundle-stats.mjs` produce PR bundle-diff comments.
- `scripts/run-audit.mjs` applies the advisory allowlist from `audit-allowlist.json` and writes machine-readable and Markdown summary reports to `_build/apps/runtime-dashboard/audit/`.
- `scripts/summarize-lighthouse.mjs` and `scripts/summarize-playwright-visual.mjs` produce review-friendly PR comments and artifacts from Lighthouse and visual-regression jobs.

## Where to Add New Functionality

- New screen or route: `src/features/<feature>/routes/*`, an export from the feature barrel, and an entry in `src/app/routes/routes.tsx`.
- New endpoint: a hook in `src/api/hooks/*`, `queryKeys` (for queries), and an optional validator.
- New reusable UI primitive: `src/shared/ui/*`.
- New reusable chart or uncertainty visualization: `src/shared/charts/*` plus an export from `src/shared/charts/index.ts`.
- New domain viewer: a component in the relevant `src/features/*/components/*` plus an adapter in `src/shared/lib/domain/*` when needed.
- New workspace-bootstrap query: define the key in `src/app/workspaces.ts`, build a `queryOptions` helper in `src/api/hooks/*`, then connect the loader.
- New typed search-parameter contract: `src/app/routes/searchParams.ts` through `zod`.

## Subtree Contracts

- App shell: [`app/README.md`](app/README.md) and [`app/AUTHORING.md`](app/AUTHORING.md)
- Feature modules: [`features/README.md`](features/README.md) and [`features/AUTHORING.md`](features/AUTHORING.md)
- Shared UI: [`shared/ui/README.md`](shared/ui/README.md) and [`shared/ui/AUTHORING.md`](shared/ui/AUTHORING.md)
- Shared charts: [`shared/charts/README.md`](shared/charts/README.md) and [`shared/charts/AUTHORING.md`](shared/charts/AUTHORING.md)
- API client/hooks/generated types: [`api/README.md`](api/README.md) and [`api/AUTHORING.md`](api/AUTHORING.md)
- Test helpers and fixtures: [`test/README.md`](test/README.md) and [`test/AUTHORING.md`](test/AUTHORING.md)
