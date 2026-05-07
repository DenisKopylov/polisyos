# Storybook Wave 1 Snapshot

This folder freezes the Storybook review surface used for Wave 1 closeout on
`2026-04-22`.

It is intentionally manifest-centric:

- the canonical generated site stays in
  `_build/apps/runtime-dashboard/storybook-static/`

- this archive keeps the curated story index, rollout manifest, and onboarding
  script needed for release review and later audits

## Snapshot Metadata

- Source command: `corepack pnpm run build-storybook`
- Source output:
  `_build/apps/runtime-dashboard/storybook-static/`

- Archived story index: [`stories.index.json`](./stories.index.json)
- Story count: `92`
- Snapshot date: `2026-04-22`

## Files

- [`stories.index.json`](./stories.index.json) — copied Storybook index from the
  green Wave 1 build

- [`staging-feature-flags.all_on.json`](./staging-feature-flags.all_on.json) —
  staging rollout manifest for full-surface review

- [`SESSION_RECORDING_SCRIPT.md`](./SESSION_RECORDING_SCRIPT.md) — suggested
  screencast/Figma walkthrough for team onboarding

## Local Review

1. `cd policy-engine/apps/runtime-dashboard`
2. Serve `_build/apps/runtime-dashboard/storybook-static/` with any static
   file server.
3. Open `index.html` for navigation or use `iframe.html?id=<story-id>` for a
   direct anchor-artifact route.

## Anchor Routes

| Artifact                               | Story ID                                           |
| -------------------------------------- | -------------------------------------------------- |
| Updated favicon / Janus mark           | `brand-janus--sizes`                               |
| Decision packet cover / reading system | `artifacts-reading-view-monograph-layout--default` |
| Evidence sigil                         | `brand-evidence-sigil--default`                    |
| Provenance strip                       | `brand-provenance-strip--default`                  |
| Uncertainty showcase                   | `design-system-uncertainty--atlas-preview`         |
| Dark-theme uncertainty                 | `design-system-uncertainty--dark-theme`            |
| Density controls                       | `features-platform-appearancesection--default`     |
| AuthoredText mixed registers           | `shared-ui-authoredtext--prominent-audit-rail`     |
| Ukrainian typography                   | `shared-text--ukrainian-typography`                |

## Deployment Handoff

When the snapshot is published for stakeholder review, record:

- deploy date
- public URL
- commit SHA or release tag
- reviewer names
- whether the deployment used `all_on` exactly or an explicit flag object

Update `release/design-wave1-release-notes.md` after deployment so
the Wave 1 gate has a single source of truth.
