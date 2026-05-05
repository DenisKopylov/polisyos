# Accessibility Audit 2026 Q2

## PolicyOS Runtime Dashboard

- Audit type: Internal pre-audit evidence packet and external audit handoff
- Audit status: Internal pre-audit complete
- Internal completion date: 2026-04-22
- External audit status: Scheduled for Q2 2026, vendor countersign pending
- Product under review: `@polisyos/runtime-dashboard@0.1.0`
- Evaluation scope: `policy-engine/frontend/runtime-dashboard`
- Standards targeted: WCAG 2.2 Level A and AA, Revised Section 508, EN 301 549 V3.2.1
- Assessment owner: Denis Kopylov

## 1. Executive Summary

This document records the internal accessibility pre-audit completed on
2026-04-22 for the Runtime Dashboard web client. It is the repository-backed
evidence packet used to support the published [VPAT.md](./VPAT.md) and to brief
the external accessibility auditor scheduled for Q2 2026. It does not replace
the planned third-party countersign.

Phase 1.3 accessibility infrastructure is exercised by the same command used
for dashboard merge gating:

```bash
npm run test:a11y
```

Internal outcome on 2026-04-22:

- WCAG 2.2 A/AA route audit: `0` violations across all `17` named dashboard surfaces.
- Playwright accessibility suite: `21` checks passing (`17` route scans, `1` keyboard journey, `2` screen-reader snapshots, `1` color-blind simulation).
- Shared UI accessibility coverage: `31` root-level `.a11y.test.tsx` files passing in `src/shared/ui/`, including the inventory guard; nested `authored-text` coverage also passes.
- Keyboard-only journey: start on runs list, open a run, reach the audit report, and trigger the snapshot export in `<= 20` tab stops.
- Screen-reader snapshot review: named landmarks and actions confirmed on runs list and run report.
- Contrast, reduced-motion, and color-blind gates: all passing in the same tooling used by pre-commit and CI.

No P0 or P1 findings remain open at the end of the internal pre-audit. The
only open compliance item is external countersign and the normal evidence
refresh cadence.

## 2. Assessment Method and Reproduction

| Method                          | Evidence                                                            | Reproduction command           |
| ------------------------------- | ------------------------------------------------------------------- | ------------------------------ |
| Aggregate accessibility gate    | Full internal pre-audit bundle                                      | `npm run test:a11y`            |
| Route WCAG audit                | `e2e/a11y/routes.a11y.spec.ts` with axe-core on `17` named surfaces | `npm run test:a11y:pages`      |
| Component accessibility audit   | `src/shared/ui/**/*.a11y.test.tsx`                                  | `npm run test:a11y:components` |
| Contrast enforcement            | Required token-pair gate plus generated matrix                      | `npm run a11y:contrast`        |
| Reduced-motion enforcement      | Provider wiring plus animation guard scan                           | `npm run a11y:motion`          |
| Color-blind enforcement         | Token simulation plus required uncertainty patterns                 | `npm run a11y:color-blind`     |
| Screen-reader regression checks | `src/test/a11y/screen-reader-snapshots.spec.ts`                     | `npm run test:a11y:pages`      |
| Keyboard-only regression check  | `src/test/a11y/keyboard-journeys.spec.ts`                           | `npm run test:a11y:pages`      |

Assessment notes:

- Automated route scans intentionally gate on WCAG-tagged axe rules only. Development-mode overlays may still surface best-practice diagnostics, but those are not treated as release-blocking conformance failures.
- Screen-reader snapshots are used as a regression harness for naming, landmarks, and action labels. They are not a substitute for the full external assistive-technology review.
- `check-contrast.ts` blocks curated required token pairs used for production text and control states. The generated [A11Y_CONTRAST.md](./A11Y_CONTRAST.md) matrix is broader and also shows exploratory combinations that are not all approved for body-text usage.

## 3. Route Inventory Covered by the Internal Audit

The automated route audit runs against the following dashboard surfaces:

| Surface          | Path pattern                                                                         |
| ---------------- | ------------------------------------------------------------------------------------ |
| `login`          | `/login`                                                                             |
| `dashboard`      | `/`                                                                                  |
| `composer`       | `/compose`                                                                           |
| `runs-list`      | `/runs`                                                                              |
| `run-compare`    | `/runs/compare?base={core_run_id}&target={core_run_id_secondary}`                    |
| `run-report`     | `/runs/{core_run_id}/report`                                                         |
| `run-overview`   | `/runs/{core_run_id}/overview`                                                       |
| `run-governance` | `/runs/{core_run_id}/governance`                                                     |
| `run-evidence`   | `/runs/{core_run_id}/evidence`                                                       |
| `run-workflow`   | `/runs/{core_run_id}/workflow`                                                       |
| `run-artifacts`  | `/runs/{core_run_id}/artifacts`                                                      |
| `run-agents`     | `/runs/{core_run_id}/agents`                                                         |
| `run-debug`      | `/runs/{core_run_id}/debug`                                                          |
| `artifact`       | `/artifacts/{root_artifact_id}`                                                      |
| `evidence`       | `/evidence?runId={core_run_id}&focus=promotion&promotionId={promotion_candidate_id}` |
| `knowledge`      | `/knowledge`                                                                         |
| `platform`       | `/platform`                                                                          |

Route-surface readiness is enforced by explicit `data-testid` markers before axe
analysis runs. This keeps the audit tied to rendered application state rather
than to intermediate loading shells.

## 4. Evidence Pack Produced

| Evidence                                       | Location                                                                                          | Status      | Notes                                                                     |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------- |
| VPAT publication                               | [VPAT.md](./VPAT.md)                                                                              | Published   | Internal sign-off document linked to this audit packet                    |
| Contrast matrix                                | [A11Y_CONTRAST.md](./A11Y_CONTRAST.md)                                                            | Generated   | Broader than the PR gate; includes exploratory token combinations         |
| Shared a11y runtime infrastructure             | `frontend/runtime-dashboard/src/shared/a11y/`                                                     | Implemented | Focus, roving tabindex, live announcements, high contrast, reduced motion |
| Route accessibility specs                      | `frontend/runtime-dashboard/e2e/a11y/`                                                            | Passing     | Axe route coverage for the full surface inventory                         |
| Keyboard, screen-reader, and color-blind specs | `frontend/runtime-dashboard/src/test/a11y/`                                                       | Passing     | Regression coverage for non-mouse use and signal distinguishability       |
| Pre-commit and CI gates                        | `policy-engine/tools/design/check-contrast.ts`, `check-reduced-motion.ts`, `check-color-blind.ts` | Passing     | Same tooling used locally and in CI                                       |
| Hook wiring                                    | `frontend/runtime-dashboard/lefthook.yml`                                                         | Active      | PR gate runs before commits land                                          |

## 5. Findings Closed During Phase 1.3

| Finding                                                                 | Severity | Resolution                                                                                                   |
| ----------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| Missing coverage for several `shared/ui` root components                | P1       | Added the inventory guard and missing `.a11y.test.tsx` files; root-level coverage now passes end to end      |
| Inconsistent high-contrast selector contract                            | P1       | Unified provider-driven `data-contrast="more"` support with theme selectors and media-query handling         |
| Composer governance-constraint controls failed WCAG 2.5.8 target-size   | P1       | Increased interactive spacing and re-verified the composer route with axe                                    |
| Keyboard journey depended on a long tab chain through the runs page     | P1       | Added a skip-to-run-explorer control and verified the full journey in Playwright                             |
| Route audit mixed best-practice diagnostics with WCAG conformance gates | P2       | Restricted automated route gating to WCAG A/AA tags while keeping broader diagnostics in development tooling |

## 6. Residual Risk and Monitoring Items

These items are not blocking Phase 1.3 acceptance, but they remain part of the
operational watchlist:

- External third-party countersign is still pending. Procurement-facing attachments should be refreshed after the vendor review lands.
- The contrast matrix intentionally includes token combinations that are not all approved for normal-text use. A `Fail` entry in the generated matrix is a design watchlist item unless that exact pair is promoted into production UI without an exemption.
- Screen-reader snapshots cover naming and landmarks well, but the external manual audit should still include NVDA or VoiceOver verification on the release candidate.
- JSDOM-based component tests still emit non-blocking warnings from some Radix portal internals (`act(...)`, canvas, pseudo-element warnings). They do not fail the suite and do not indicate a current WCAG regression.
- General dashboard `typecheck` is currently affected by unrelated composer typing work outside this accessibility stream. Accessibility gating itself passes independently.

## 7. External Audit Handoff Checklist

| Item                                                                  | Owner                                  | Status          |
| --------------------------------------------------------------------- | -------------------------------------- | --------------- |
| Publish internal evidence packet in repository                        | Internal owner                         | Complete        |
| Publish and sign internal VPAT                                        | Internal owner                         | Complete        |
| Attach vendor name and audit window                                   | Internal owner                         | Pending Q2 2026 |
| Run manual WCAG 2.2 AA checklist on the release candidate             | External auditor with internal support | Pending Q2 2026 |
| Record external findings and remediation notes in this document       | External auditor and internal owner    | Pending Q2 2026 |
| Refresh contrast matrix and rerun full gate after material UI changes | Product team                           | Ongoing         |

## 8. Recommended Cadence

| Cadence                    | Action                                                                                                                                         |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Every pull request         | Run `npm run test:a11y` and block merges on failure                                                                                            |
| Weekly                     | Refresh accessibility evidence in CI and review trendlines for regressions                                                                     |
| Quarterly                  | Refresh VPAT, rerun the internal audit bundle, and collect external countersign where scheduled                                                |
| Before procurement release | Re-run the full suite, regenerate [A11Y_CONTRAST.md](./A11Y_CONTRAST.md), and confirm the sign-off table below still matches the shipped build |

## 9. Sign-off

| Role                  | Name               | Date       | Status    |
| --------------------- | ------------------ | ---------- | --------- |
| Internal audit owner  | Denis Kopylov      | 2026-04-22 | Signed    |
| External audit vendor | Pending assignment | Q2 2026    | Scheduled |

## 10. Revision History

| Date       | Version | Change                                                                                |
| ---------- | ------- | ------------------------------------------------------------------------------------- |
| 2026-04-22 | 1.1.0   | Expanded internal pre-audit into a full evidence packet and external handoff document |
| 2026-04-22 | 1.0.0   | Initial internal pre-audit summary committed                                          |
