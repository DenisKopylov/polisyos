# Runtime Dashboard Shared Frontend

- Owner: team-frontend
- Purpose: shared runtime-dashboard UI, accessibility, brand, network, telemetry, export, and utility modules reused across feature slices.
- Allowed contents: generic frontend components, shared hooks/helpers, typed client utilities, Storybook stories, and colocated unit or accessibility tests.
- Local verification: `corepack pnpm --filter @polisyos/runtime-dashboard test`
- Maintenance: feature-specific code should remain in feature directories; shared additions require reusable ownership and accessible component coverage.
