# Voluntary Product Accessibility Template (VPAT) 2.5

## PolicyOS Runtime Dashboard

- Status: Approved Wave 1 artifact
- Date: 2026-04-23
- Product: PolicyOS Runtime Dashboard
- Version under review: `@polisyos/runtime-dashboard@0.1.0`
- Evaluation scope: `policy-engine/frontend/runtime-dashboard`
- Standards: WCAG 2.2 Level A and AA, Revised Section 508, EN 301 549 V3.2.1
- Owner and internal signatory: Denis Kopylov
- External accessibility countersign: Post-closeout enhancement; not required for the engineering Wave 1 gate

## 1. Evaluation Summary

This VPAT reflects the internal accessibility assessment completed on 2026-04-23
for the Runtime Dashboard web client. The assessment is based on automated WCAG
2.2 A/AA auditing, keyboard-only end-to-end journeys, screen-reader snapshot
verification, color-blind simulation checks, contrast enforcement, reduced-motion
linting, and component-level axe coverage.

Primary evidence for this VPAT is committed alongside the product:

- [A11Y_CONTRAST.md](./A11Y_CONTRAST.md) — generated contrast matrix from theme tokens
- [A11Y_AUDIT_2026Q2.md](./A11Y_AUDIT_2026Q2.md) — internal pre-audit report and external audit plan
- `frontend/runtime-dashboard/src/shared/a11y/*` — focus, contrast, reduced-motion, live region, and high-contrast infrastructure
- `frontend/runtime-dashboard/src/test/a11y/*` and `frontend/runtime-dashboard/e2e/a11y/*` — automated route, keyboard, screen-reader, and color-blind coverage
- `docs/brand/storybook-wave1-snapshot/EVIDENCE_BUNDLE.md` — canonical Wave 1 evidence index

## 2. Evaluation Methods

| Method                       | Coverage                                                                                                                                                                               |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Automated WCAG route audit   | `npm run test:a11y:pages` on login, dashboard, composer, runs, artifacts, evidence, platform, and run detail routes                                                                    |
| Automated component audit    | `npm run test:a11y:components` covering every root component in `src/shared/ui/`                                                                                                       |
| Keyboard-only journey        | Start on runs list, open a run, navigate to report, download decision packet within the tab-stop budget                                                                                |
| Screen-reader snapshot audit | Landmark and control-name checks on runs list and run report                                                                                                                           |
| Contrast enforcement         | `check-contrast.ts` plus generated contrast matrix document; required semantic text pairs are enforced while prohibited dark-theme accent pairs remain visible in the published matrix |
| Reduced motion audit         | `check-reduced-motion.ts` plus app-wide provider wiring                                                                                                                                |
| Color-blind simulation       | `check-color-blind.ts` and Playwright token-level simulation for deuteranope, protanope, tritanope                                                                                     |
| High-contrast support        | `prefers-contrast: more`, `forced-colors`, and provider-driven `data-contrast="more"` mode                                                                                             |

## 3. Conformance Summary

| Standard            | Result   | Notes                                                                  |
| ------------------- | -------- | ---------------------------------------------------------------------- |
| WCAG 2.2 Level A    | Supports | Internal automated assessment complete; external countersign scheduled |
| WCAG 2.2 Level AA   | Supports | Internal automated assessment complete; external countersign scheduled |
| Revised Section 508 | Supports | Web-software obligations map to the WCAG findings below                |
| EN 301 549 V3.2.1   | Supports | Relevant web clauses inherit the same evidence set                     |

## 4. Terms

| Term               | Meaning                                                                             |
| ------------------ | ----------------------------------------------------------------------------------- |
| Supports           | The functionality met the criterion during the internal assessment.                 |
| Partially Supports | The criterion is substantially met but still requires restricted-scope maintenance. |
| Does Not Support   | The criterion is not currently met.                                                 |
| Not Applicable     | The criterion is not relevant to the product.                                       |

## 5. WCAG 2.2 Level A and AA

### 5.1 Perceivable

| Criterion                                                  | Level | Conformance    | Remarks and Explanations                                                                                                                                                                                               |
| ---------------------------------------------------------- | ----- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1.1.1 Non-text Content                                     | A     | Supports       | Glyphs, buttons, dialogs, charts, and report actions expose accessible names; verified by component axe coverage and screen-reader snapshots.                                                                          |
| 1.2.1 Audio-only and Video-only (Prerecorded)              | A     | Not Applicable | The Runtime Dashboard does not publish prerecorded media.                                                                                                                                                              |
| 1.2.2 Captions (Prerecorded)                               | A     | Not Applicable | No prerecorded video content in scope.                                                                                                                                                                                 |
| 1.2.3 Audio Description or Media Alternative (Prerecorded) | A     | Not Applicable | No prerecorded time-based media in scope.                                                                                                                                                                              |
| 1.2.4 Captions (Live)                                      | AA    | Not Applicable | No live media in scope.                                                                                                                                                                                                |
| 1.2.5 Audio Description (Prerecorded)                      | AA    | Not Applicable | No prerecorded video in scope.                                                                                                                                                                                         |
| 1.3.1 Info and Relationships                               | A     | Supports       | Route axe audit passes across 17 named dashboard surfaces; shared UI tests validate dialogs, menus, tabs, labels, tooltips, tables, and forms.                                                                         |
| 1.3.2 Meaningful Sequence                                  | A     | Supports       | App-shell focus restoration targets `#main-content`; keyboard journey and route navigation complete without mouse use.                                                                                                 |
| 1.3.3 Sensory Characteristics                              | A     | Supports       | Uncertainty and provenance cues are encoded by glyphs, labels, patterns, and text, not by colour alone.                                                                                                                |
| 1.3.4 Orientation                                          | AA    | Supports       | Responsive web application with no orientation lock.                                                                                                                                                                   |
| 1.3.5 Identify Input Purpose                               | AA    | Supports       | Input controls expose labels and accessible names in the audited composer and runs flows.                                                                                                                              |
| 1.4.1 Use of Color                                         | A     | Supports       | `check-color-blind.ts` and Playwright simulation confirm signal-pair separation and pattern redundancy.                                                                                                                |
| 1.4.2 Audio Control                                        | A     | Not Applicable | No audio playback exists in scope.                                                                                                                                                                                     |
| 1.4.3 Contrast (Minimum)                                   | AA    | Supports       | Required semantic text pairs are enforced by `check-contrast.ts`; published matrix is in [A11Y_CONTRAST.md](./A11Y_CONTRAST.md), and dark-theme raw accent tokens are explicitly documented as non-text-safe defaults. |
| 1.4.4 Resize Text                                          | AA    | Supports       | Controls and layouts rely on responsive sizing and preserved reflow in route audit coverage.                                                                                                                           |
| 1.4.5 Images of Text                                       | AA    | Supports       | Product UI uses live text rather than rasterized text assets.                                                                                                                                                          |
| 1.4.10 Reflow                                              | AA    | Supports       | Route surfaces remain operable in responsive layouts used by the automated route suite.                                                                                                                                |
| 1.4.11 Non-text Contrast                                   | AA    | Supports       | Focus rings, borders, controls, and chart affordances are covered by the contrast matrix and axe route audit.                                                                                                          |
| 1.4.12 Text Spacing                                        | AA    | Supports       | Typography remains functional under the tested route and component layouts.                                                                                                                                            |
| 1.4.13 Content on Hover or Focus                           | AA    | Supports       | Tooltip, popover, dialog, sheet, and dropdown primitives pass automated accessibility checks in their interactive open states.                                                                                         |

### 5.2 Operable

| Criterion                              | Level | Conformance    | Remarks and Explanations                                                                                                                  |
| -------------------------------------- | ----- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| 2.1.1 Keyboard                         | A     | Supports       | Keyboard-only end-to-end journey passes; shared focus management is centralized in `useFocusTrap` and `useRovingTabindex`.                |
| 2.1.2 No Keyboard Trap                 | A     | Supports       | Dialogs, sheets, menus, tabs, and other interactive primitives pass component-level keyboard-accessibility tests.                         |
| 2.1.4 Character Key Shortcuts          | A     | Supports       | Single-key shortcuts are scoped to focused explorer contexts and do not override text-entry fields.                                       |
| 2.2.1 Timing Adjustable                | A     | Not Applicable | No timing-limited task completion is required in the audited flows.                                                                       |
| 2.2.2 Pause, Stop, Hide                | A     | Supports       | Reduced-motion handling is enforced by provider wiring and `check-reduced-motion.ts`; motion-intensive affordances have static fallbacks. |
| 2.3.1 Three Flashes or Below Threshold | A     | Supports       | No flashing content is present in the audited routes.                                                                                     |
| 2.4.1 Bypass Blocks                    | A     | Supports       | Global skip-to-content plus route-level skip-to-explorer affordances are available for keyboard users.                                    |
| 2.4.2 Page Titled                      | A     | Supports       | Route transitions maintain page-level document titles in the dashboard application shell.                                                 |
| 2.4.3 Focus Order                      | A     | Supports       | Route transitions focus `#main-content`; runs explorer adds a keyboard skip control and row-focus contract.                               |
| 2.4.4 Link Purpose (In Context)        | A     | Supports       | Screen-reader snapshots confirm named actions such as “Open run” and “Export JSON”.                                                       |
| 2.4.5 Multiple Ways                    | AA    | Supports       | Users can reach workspaces by navigation rail, direct route, run explorer actions, report links, and evidence/artifact routes.            |
| 2.4.6 Headings and Labels              | AA    | Supports       | Routes and major cards expose visible headings and labeled controls; route axe audit is green.                                            |
| 2.4.7 Focus Visible                    | AA    | Supports       | Focus ring tokens and route/component tests confirm visible focus styling across the audited flows.                                       |
| 2.4.11 Focus Not Obscured (Minimum)    | AA    | Supports       | Focus is restored to `main` on navigation; dialogs and overlays manage focus within visible containers.                                   |
| 2.5.1 Pointer Gestures                 | A     | Supports       | Core actions are available without complex gestures.                                                                                      |
| 2.5.2 Pointer Cancellation             | A     | Supports       | Primary workflows use standard buttons, links, and form controls.                                                                         |
| 2.5.3 Label in Name                    | A     | Supports       | Interactive controls in the audited flows expose visible labels that match accessible names.                                              |
| 2.5.4 Motion Actuation                 | A     | Supports       | No motion-actuated controls are required for operation.                                                                                   |
| 2.5.7 Dragging Movements               | AA    | Supports       | Audited workflows have keyboard-accessible alternatives and do not require drag-only input.                                               |
| 2.5.8 Target Size (Minimum)            | AA    | Supports       | Composer governance-constraint spacing was widened to satisfy axe target-size checks; route audit now passes.                             |

### 5.3 Understandable

| Criterion                                       | Level | Conformance | Remarks and Explanations                                                                                                          |
| ----------------------------------------------- | ----- | ----------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 3.1.1 Language of Page                          | A     | Supports    | Application routes render with a page-level `lang` attribute.                                                                     |
| 3.1.2 Language of Parts                         | AA    | Supports    | Locale-aware text rendering and route localization infrastructure are present for supported languages.                            |
| 3.2.1 On Focus                                  | A     | Supports    | Focus changes do not trigger unexpected context changes in the audited flows.                                                     |
| 3.2.2 On Input                                  | A     | Supports    | Form controls do not auto-submit or unexpectedly navigate on value entry.                                                         |
| 3.2.3 Consistent Navigation                     | AA    | Supports    | App shell, route framing, and primary navigation remain consistent across audited routes.                                         |
| 3.2.4 Consistent Identification                 | AA    | Supports    | Shared UI primitives reuse stable labels, iconography, and interaction patterns.                                                  |
| 3.2.6 Consistent Help                           | A     | Supports    | Shared navigation, explorer actions, and contextual help affordances remain stable across workspaces.                             |
| 3.3.1 Error Identification                      | A     | Supports    | Form validation and error alert components are covered by route and component accessibility tests.                                |
| 3.3.2 Labels or Instructions                    | A     | Supports    | Inputs, selects, sliders, and dialogs are explicitly labeled in the audited components and pages.                                 |
| 3.3.3 Error Suggestion                          | AA    | Supports    | Error presentation surfaces actionable text in forms and alerts within the audited flows.                                         |
| 3.3.4 Error Prevention (Legal, Financial, Data) | AA    | Supports    | Run-launch, governance, and decision-report flows preserve explicit confirmation and review-oriented UI contracts.                |
| 3.3.7 Redundant Entry                           | A     | Supports    | The dashboard preserves active selection and route context rather than requiring unnecessary re-entry during the audited journey. |
| 3.3.8 Accessible Authentication (Minimum)       | AA    | Supports    | Login route passes WCAG route audit and preserves return-path context after session recovery.                                     |

### 5.4 Robust

| Criterion               | Level   | Conformance    | Remarks and Explanations                                                                                                      |
| ----------------------- | ------- | -------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| 4.1.1 Parsing           | Removed | Not Applicable | Criterion removed from WCAG 2.2.                                                                                              |
| 4.1.2 Name, Role, Value | A       | Supports       | Shared UI primitives pass component-level axe coverage; screen-reader snapshots confirm names and roles on key routes.        |
| 4.1.3 Status Messages   | AA      | Supports       | `LiveAnnouncer` is centralized in shared a11y infrastructure and route interactions preserve accessible status announcements. |

## 6. Revised Section 508 Summary

| Section 508 Chapter                    | Conformance    | Notes                                                                                                              |
| -------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------ |
| 302 Functional Performance Criteria    | Supports       | Inherits WCAG 2.2 A/AA conformance for the dashboard web UI.                                                       |
| 503 Applications and Operating Systems | Supports       | Keyboard, focus, contrast, reduced-motion, and status-message requirements are covered by the internal assessment. |
| 504 Authoring Tools                    | Not Applicable | The audited scope is an operational dashboard, not a general authoring tool platform.                              |

## 7. EN 301 549 Summary

| Clause                                       | Conformance    | Notes                                                                                                    |
| -------------------------------------------- | -------------- | -------------------------------------------------------------------------------------------------------- |
| Clause 9 Web                                 | Supports       | Same evidence set as WCAG 2.2 A/AA assessment.                                                           |
| Clause 10 Non-web documents                  | Not Applicable | This VPAT covers the web dashboard UI only.                                                              |
| Clause 11 Software                           | Supports       | Interaction, focus, and visual accessibility requirements are met through the same client-side controls. |
| Clause 12 Documentation and support services | Supports       | Accessibility evidence is published in committed compliance documents.                                   |

## 8. Approval Block

- Approval owner: Denis Kopylov
- Approval date: 2026-04-23
- Approval mode: internal engineering sign-off for Wave 1 closeout
- Evidence bundle:
  `docs/brand/storybook-wave1-snapshot/EVIDENCE_BUNDLE.md`

- Evidence hash: `wave1-evidence.json.git_sha` from the
  `wave1-evidence-manifest` CI artifact

## 9. Exceptions and Maintenance

- The internal assessment is complete and published. External quarterly audit and countersign remain scheduled for Q2 2026.
- Development-mode overlay audits still include best-practice rules in addition to WCAG tags to surface non-blocking issues earlier during authoring.
- Accessibility evidence should be refreshed whenever route inventory, token colours, or shared interaction primitives materially change.

## 10. Sign-off

| Role                                             | Name                                      | Date       | Status   |
| ------------------------------------------------ | ----------------------------------------- | ---------- | -------- |
| Product owner / internal accessibility signatory | Denis Kopylov                             | 2026-04-22 | Signed   |
| External auditor                                 | Deferred to post-closeout quarterly audit | Q2 2026    | Deferred |

## 11. Revision History

| Date       | Version | Change                                                         |
| ---------- | ------- | -------------------------------------------------------------- |
| 2026-04-22 | 1.1.0   | Wave 1 VPAT approved with evidence-bundle based closeout block |
