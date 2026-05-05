# Wave 1 Evidence Bundle

This bundle is the repository-backed proof surface used by Wave 1 closeout and
the release notes. The canonical CI publisher is
`.github/workflows/design-wave1-evidence.yml`; it emits fixed-name immutable
artifacts and a machine-readable manifest.

## Immutable CI Artifact Contract

- Workflow: `.github/workflows/design-wave1-evidence.yml`
- Manifest artifact name: `wave1-evidence-manifest`
- Manifest file: `wave1-evidence.json`
- Storybook artifact name: `wave1-storybook-static`
- Playwright report artifact name: `wave1-playwright-report`
- Visual report artifact name: `wave1-visual-report`
- Contrast artifact name: `wave1-contrast-artifact`
- Manifest run fields: `git_sha`, `github_run_id`, `github_run_attempt`,
  `storybook_artifact_name`, `playwright_report_artifact_name`,
  `visual_report_artifact_name`, `a11y_suite_status`,
  `openapi_sync_status`, `generated_at_utc`

## Storybook

- Static build: `_build/frontend/runtime-dashboard/storybook-static/`
- Snapshot manifest: `docs/brand/storybook-wave1-snapshot/stories.index.json`
- Rollout manifest: `docs/brand/storybook-wave1-snapshot/staging-feature-flags.all_on.json`
- Team walkthrough script:
  `docs/brand/storybook-wave1-snapshot/SESSION_RECORDING_SCRIPT.md`

## Accessibility

- Generated contrast artifact: `docs/compliance/A11Y_CONTRAST.md`
- VPAT: `docs/compliance/VPAT.md`
- Internal audit report: `docs/compliance/A11Y_AUDIT_2026Q2.md`
- Route/component a11y suite:
  `frontend/runtime-dashboard/src/test/a11y/` and
  `frontend/runtime-dashboard/e2e/a11y/`

## Design-System Integrity

- Glyph parity script:
  `frontend/runtime-dashboard/scripts/check-glyph-vocabulary.mjs`

- ADR lint: `tools/design/adr_lint.py`
- Contrast gate: `tools/design/check-contrast.ts`
- Reduced-motion gate: `tools/design/check-reduced-motion.ts`
- Color-blind gate: `tools/design/check-color-blind.ts`

## API and Types

- Runtime OpenAPI: `schemas/runtime_api_v1.openapi.json`
- Generated TypeScript client types:
  `frontend/runtime-dashboard/src/api/types.ts`

- API client generation script:
  `frontend/runtime-dashboard/scripts/generate-api-client.sh`
