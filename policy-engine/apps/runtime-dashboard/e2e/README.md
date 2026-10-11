# Runtime Dashboard E2E Tests

Owner: `team-frontend`

This subtree contains Playwright end-to-end journeys, accessibility checks,
helpers, and reviewed visual snapshots for the runtime dashboard. Tests here
exercise the built dashboard through browser-level flows; reusable unit helpers
belong under `apps/runtime-dashboard/src/test`.

The opt-in `catalog-profile-source-bound.spec.ts` suite also checks the artifact inspector's full-reference selector. Its controlled server fixture stores identical content bytes under two distinct manifest profiles, registers both under the fixture tenant, and scopes the fixture authority to the runtime artifact-inspection and dashboard-display routes while forbidding publication, promotion, and claim authority. This is a test-only boundary, not a production authority fixture. The browser changes the URL selector without reloading so the same React Query client must fetch the selected sibling view; the check covers profile-specific ETags and refusal of a cross-profile typed reference or absent profile.

From `apps/runtime-dashboard/`, run the opt-in browser witness with:

```sh
POLISYOS_DASHBOARD_SOURCE_BOUND_PROFILE_FIXTURE=1 CI=1 PLAYWRIGHT_RETRIES=0 corepack pnpm exec playwright test e2e/journeys/catalog-profile-source-bound.spec.ts --project=chromium --workers=1
```
