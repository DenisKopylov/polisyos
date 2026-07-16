---
title: PolicyOS Atlas Product, Marketing, Client Surfaces Master Plan
status: superseded
owner: team-polisyos
created: 2026-05-06
last_verified: 2026-07-16
stability: retained-material
execution_authority: superseded
superseded_by: docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
retained_for: [DS11, DS12, DS13]
disposition_record: docs/brand/ATLAS_SOURCE_OF_TRUTH.md
related:
  - docs/plans/active/REPOSITORY_BEST_IN_CLASS_REMEDIATION_MASTER_PLAN.md
  - docs/plans/archive/DESIGN_BEST_IN_CLASS_PLAN.md
  - docs/plans/archive/FRONTEND_SOTA_PLAN.md
  - docs/plans/active/DOCUMENTATION_SOTA_PLAN.md
  - docs/plans/active/INFRASTRUCTURE_SOTA_PLAN.md
  - docs/brand/ATLAS_DESIGN_SYSTEM.md
  - docs/brand/ATLAS_V4_ADOPTION.md
  - docs/brand/GLYPH_SPECIFICATION.md
  - docs/brand/MOTION.md
  - docs/brand/PRINT_AND_EXPORT.md
  - docs/brand/TYPOGRAPHY_UA_RU.md
  - docs/brand/EMAIL_TEMPLATES.md
  - docs/brand/SOCIAL_TEMPLATES.md
  - docs/brand/TRUST_VIEW.md
  - docs/brand/UNCERTAINTY_LANGUAGE.md
  - docs/reference/frontend/workspace-contract.md
  - docs/reference/security-compliance.md
  - schemas/runtime_api_v1.openapi.json
inputs:
  - PolicyOS Atlas Design System-7.zip (current)
  - PolicyOS Atlas Design System-6.zip (prior)
  - PolicyOS Atlas Design System-4.zip (referenced by DESIGN_BEST_IN_CLASS_PLAN.md)
---

# PolicyOS Atlas Product, Marketing, Client Surfaces Master Plan

> **DS0 lifecycle disposition (2026-07-16): retained material, not an
> execution master.** Do not execute this v7-era plan. DS11-DS13 may mine its
> trust, public-publication, and accountability material through the
> [Revision 2 master plan](./POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md)
> and the [DS0 decision](../../brand/ATLAS_SOURCE_OF_TRUTH.md#atlas-d1).

**Goal:** turn the Atlas design package and the marketing/client ideas into a
production-grade public web, authenticated product shell, procurement journey,
trust center, documentation/support system, and public accountability surface.

**Architecture:** keep the production implementation inside the canonical
`policy-engine/` workspace and treat the zip as a design/content prototype, not
as directly shippable code. Public, auth, billing, settings, docs, support,
trust, and domain-specific surfaces must be implemented as independently
owned route families with shared route, i18n, content, design-token, and API
registry queues serialized in short patches.

**Tech Stack:** React 19, TypeScript, Vite, React Router 7, TanStack Query,
Radix/shadcn-style primitives, Tailwind v4 tokens, Recharts, cmdk, OpenAPI
client generated from `schemas/runtime_api_v1.openapi.json`, MkDocs for
repository docs, Playwright/Vitest/Lighthouse for verification.

---

## Scope

This plan covers the missing and partially implemented product, marketing, and
client-facing surfaces implied by:

- `/Users/deniskopylov/Downloads/PolicyOS Atlas Design System-7.zip` (current
  design package; supersedes v6 and v4);
- existing Atlas frontend code under `apps/runtime-dashboard/**`;
- existing brand docs under `docs/brand/**`;
- existing best-in-class design backlog under
  `docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md` (Tracks A–G for advanced
  product surfaces);
- public marketing, procurement, documentation, support, auth, billing,
  settings, and domain-specific ideas listed by Denis on 2026-05-06;
- plan-review additions received on 2026-05-07 covering backend contracts,
  content ownership, analytics/attribution, continuous gates, jurisdiction,
  lead routing, sandbox architecture, early email/OG, public telemetry, and
  AI Act readiness;
- progressive additions received on 2026-05-20 covering v7 zip expansion
  (calculator, trust, status, case-study, decision-packet, emails, mobile,
  components, api, onboarding, empty-states, states, error-pages,
  design-canvas, iOS Liquid Glass frame, 25 advanced A1–E5 dashboard
  surfaces), multi-domain topology, content backend choice, v7 design-token
  drift (Janus medallion as decision stamp, Instrument Serif citation,
  density modes, CI tokens, waterfall, rim-light, soft-fill, semantic
  typography classes), and a new new post-launch product platform tier (consolidated into Wave 9 in the restructure)
  (operator certification, transparency report, bug bounty / CVD,
  open-source strategy, research consortium, multi-tenant white-label,
  auditor portal, public consultations, EU AI Office machine-readable
  transparency feed, Atlas Codex governance, sovereign cloud variants).

In scope:

- public marketing site around the current `landing/index.html` prototype;
- interactive public sandbox, playable demo, calculators, public decision
  packet samples, and re-run-from-case-study flows;
- trust center, status, changelog, roadmap, legal, cookie, procurement, and
  sovereign deployment pages;
- about/mission/team, careers, partners/resellers, contact, and book-a-demo
  conversion journeys;
- auth/onboarding extensions beyond current minimal login screen;
- billing, procurement, invoices, usage, and subscription lifecycle inside the
  product;
- workspace and personal settings inside the app;
- docs site expansion beyond the current `landing/docs.html` long-form
  prototype and existing MkDocs reference content;
- support/help center, tickets, DSAR/compliance request flows;
- cross-cutting empty/loading/error/offline/license/notification/Cmd-K states;
- PolicyOS-specific surfaces: public decision records, governance inbox,
  decision packet PDF, mobile quick approve, Evidence Fabric source detail and
  lineage, civic data hub, transparency snippets, and UA/EU identity/procurement
  features;
- brand-as-product surfaces: animated glyphs, email system, invoice/receipt
  artifacts, OG/social previews, print-to-procurement, Atlas Codex.

Out of scope:

- copying `landing/*.html` or `ui_kits/dashboard/*.jsx` wholesale into
  production without routing, accessibility, i18n, testing, and API boundaries;
- replacing existing runtime dashboard workspaces already marked baseline in
  `DESIGN_BEST_IN_CLASS_PLAN.md`;
- inventing unverified compliance claims without evidence docs, legal owner
  approval, and dated source-of-truth content;
- implementing real payment, SSO, procurement, or government identity
  integrations without backend contracts and security review;
- changing repository-wide topology, lockfiles, or shared architecture
  registries outside the queue rules in this plan and the repository master
  plan.

## Verified Baseline

Baseline verified locally on 2026-05-20.

### Zip Inventory

`PolicyOS Atlas Design System-7.zip` contains (current design package; v6
content folded in plus the additions below; v4 content remains the canonical
reference inside `DESIGN_BEST_IN_CLASS_PLAN.md`):

| Zip area | Verified contents | Production interpretation |
| --- | --- | --- |
| `README.md` and `SKILL.md` | Atlas visual, tone, typography, iconography, motion, and product workflow guidance; v7 SKILL.md is `user-invocable` and ships short design-system essentials block | Keep as design-system reference input. Reconcile with `docs/brand/**`. Mirror SKILL.md as an internal agent skill descriptor only — never as production code. |
| `colors_and_type.css` | CSS custom properties for light/dark themes, semantic colors, spacing, radii, shadow, motion, font stacks, type scale, line-height/tracking, semantic typography classes (`.t-display`, `.t-h1..h4`, `.t-body`, `.t-small`, `.t-eyebrow`, `.t-mono`, `.t-metric`, `.t-metric-md`, `.t-prose`, `.t-citation`), CI/bounds/confidence/waterfall/rail tokens, rim-light, page-gradient stops, panel/surface/shell-glass tokens, soft-fill tokens | Drift fixture only. Production tokens stay in `apps/runtime-dashboard/src/styles*`. New v7 tokens (CI, bounds, waterfall, rim-light, page-gradient, soft-fill, panel-strong, surface, shell-glass-base, semantic `.t-*` classes) must enter production through a single design-token patch. |
| `fonts/README.md`, `fonts/download.sh`, `fonts/fonts.css` | Manrope (sans), IBM Plex Mono (mono), Instrument Serif (italic) font-face plumbing and download script | Reconcile with current font loading; record license, hosting, and offline fallback. Instrument Serif italic is mandatory for citations/blockquotes/decision packet pull-quotes. |
| `assets/**` and `landing/assets/**` | Atlas logos (atlas, atlas-inverse, mark, mark-inverse), Janus medallion (`logo-janus.svg`), favicon set (.svg/16/32/48/192/512/512-maskable/apple-touch), webmanifest, OG default/changelog/case-study (PNG + `og-template.html`), 10 glyph SVGs | Already mostly present in `apps/runtime-dashboard/public/atlas/**`. Run geometry/hash drift checks before overwriting. **Janus medallion** must be wired as decision stamp / score ring inside Public Decision Record, Decision Packet PDF, and the Trust Center seal block. |
| `preview/*.html` (12 files) | `colors-base`, `colors-semantic`, `type-scale`, `type-faces`, `spacing-radii`, `shadows`, `buttons`, `badges`, `cards`, `glyphs`, `logo`, `uncertainty` | Convert into Storybook/design-reference stories and automated token-drift fixtures. The `uncertainty` and `colors-semantic` previews are the reference for confidence bands, bounds fill, waterfall, severity, and signal tokens. |
| `landing/index.html` | Static marketing page with hero, workflows, capabilities, glyph alphabet, compare, pricing teaser, CTA, footer | Prototype for first public site wave. Use as visual reference, not source. |
| `landing/auth.html` | Static Sign in · Sign up · Checkout concepts (single surface) | Prototype only. Missing forgot/reset, verification, MFA, SSO picker, magic link, invite, tenant picker, onboarding, step-up, suspicious activity, full billing lifecycle. |
| `landing/docs.html` | Static docs handbook longread with sidebar, search input, lanes, quickstart, contracts, runbooks, ADR shelf, right TOC | Prototype only. Productized via Phase 2.15 (docs IA). |
| `landing/api.html` | Static Atlas API Reference longread for PolicyOS v1 | Prototype reference for Phase 1.16 (API quickstarts) and Phase 2.18 (API longread) and Phase 2.18 (API longread). Schema source of truth remains `schemas/runtime_api_v1.openapi.json`. |
| `landing/pricing.html` | Static pricing page with three tiers (Bench, Atlas, Sovereign) metered by JAX node-hours | Prototype only. Cross-check tiers/units against Phase 6.1 (plan picker) and Phase 4.3 quote builder before publishing. |
| `landing/calculator.html` | ROI calculator wireframe — CFO-targeted framing | Productize via Phase 2.9. Treat as visual reference; pricing formulas come from Phase 0.4 fixtures. |
| `landing/trust.html` | trust.policyos.eu — Atlas trust center prototype | Productize via Phase 2.11. Subdomain decision sits in Phase 1.5. |
| `landing/status.html` | status.policyos.eu — Atlas runtime status prototype | Productize via Phase 1.15. Subdomain decision sits in Phase 1.5. |
| `landing/changelog.html` | Atlas changelog / release notes prototype, framed as CAS artifacts (signed, ratchet-tested, ADR-cited) | Productize via Phase 1.15. The CAS framing is a public-claim and must be evidence-mapped before publish. |
| `landing/case-study.html` | "Forty-eight hours of replay, folded into one signed packet" — 48hr→38min narrative, Nordic Council Tier-2 fiscal cell anchor | Productize via Phase 4.1. Anonymize until named-case approval is on file. |
| `landing/decision-packet.html` | 4-page A4 signed decision packet (`DP-2026-08-14-7C4A`) with verdict, regulator citation, governance trace, provenance DAG, reproducibility manifest, ed25519 multi-party seal | Productize via Phase 3.3 + Phase 4.5. PDF/print layout is the reference for the decision packet print spec. |
| `landing/emails.html` | Atlas transactional emails wireframe | Productize via Phase 2.4 (foundation) + Phase 7.8 (advanced templates). |
| `landing/mobile.html` | Atlas mobile — landing · docs · dashboard in a single surface | Productize via Phase 4.2 (preview) + Phase 9.1 (mobile system). |
| `landing/onboarding.html` | First-run onboarding flow prototype | Productize via Phase 3.6 first-run wizard. |
| `landing/components.html` | Components page — 10-radical glyph alphabet, semantic buttons/pills, governance gates, run rows, sign panel; scoped to `.c-*`; live preview + copy-paste code | Public component gallery (Phase 3.8) and Atlas Codex anchor (Phase 3.10). Source of truth remains Storybook. |
| `landing/empty-states.html` | Three empty-states: Composer day-zero, Decision Workspace before-the-run, Evidence Fabric first-connect | Productize via Phase 1.10 with editorial Atlas treatment. |
| `landing/states.html` | Atlas states reference: empty · loading · errors · degraded | Convert to Storybook reference for Phase 1.10 state matrix. |
| `landing/404.html`, `landing/500.html`, `landing/offline.html`, `landing/error-pages.css` | Shared error-pages stylesheet with `body[data-error="404\|500\|offline"]` variant attribute, serif italic display title, mono status line, ASCII reference block, blocker glyph | Productize via Phase 1.10 service pages. Localized via Phase 1.8 register tags. |
| `landing/design-canvas.jsx` | Figma-ish design canvas wrapper: grid bg, sections, reorderable artboards, inline-editable labels, fullscreen focus overlay, Post-It notes, sidecar `.design-canvas.state.json` persistence | Treat as Storybook seed / Atlas Codex working canvas (Phase 4.7). Not a public product route. |
| `landing/ios-frame.jsx` | iOS 26 "Liquid Glass" device frame: `IOSDevice`, `IOSStatusBar`, `IOSNavBar`, `IOSGlassPill`, `IOSList`, `IOSListRow`, `IOSKeyboard` | Treat as design-canvas component for mobile preview surfaces (Phase 9.1) until iOS scope is decided in Phase 2.1. |
| `landing/site.webmanifest` | Web app manifest skeleton | Reconcile with current PWA manifest; record subdomain split if Phase 1.5 chooses multi-domain. |
| `ui_kits/dashboard/index.html` + 30 `*.jsx` | Interactive hi-fi prototype with 25 named advanced surfaces (A1–E5) plus shared primitives (`Components.jsx`, `Sidebar.jsx`, `Composer.jsx`, `Dashboard.jsx`, `EvidenceFabric.jsx`, `RunDetail.jsx`) | Each named surface is cross-referenced to `DESIGN_BEST_IN_CLASS_PLAN.md` Tracks A–G via the v7 Surface Register in Phase 1.1. This plan does not duplicate that tracking; it only owns the public/marketing/trust/print/embed/transparency cross-surfaces. |
| `policy-engine/apps/runtime-dashboard/public/atlas/**` | Legacy destination path from the zip | Canonical repo has moved toward `apps/runtime-dashboard/**`; do not revive old `apps/runtime-dashboard/**` as a primary app path. |

### v7 Advanced Surface Register (cross-reference, not duplicate tracking)

The v7 `ui_kits/dashboard/*.jsx` package contains 25 named advanced product
surfaces. Implementation of each surface is owned by `DESIGN_BEST_IN_CLASS_PLAN.md`
(Tracks A–G). This master plan owns only the public/marketing/trust/print/embed/
transparency cross-surfaces that ride on top.

The register below is a thin pointer table. It must not be edited to add
implementation status — that lives in DESIGN_BEST_IN_CLASS_PLAN. Update only when
v7 ID, DESIGN plan slug, or this-plan cross-surface link changes.

| v7 ID | Surface | DESIGN plan section | This-plan cross-surface (public/print/embed) |
| --- | --- | --- | --- |
| A1 | Causal Atlas | DESIGN §5.A1 | Methodology longread (Phase 2.7); ADR/glossary cross-link (Phase 3.7) |
| A2 | Identifiability Surface | DESIGN §5.A2 | Methodology longread (Phase 2.7); EU AI Act conformity evidence (Phase 5.2) |
| A3 | Sensitivity Rotor (E-value) | DESIGN §5.A3 | Methodology longread (Phase 2.7); transparency snippet (Phase 5.2) |
| A4 | Cohort Time-Traveler | DESIGN §5.A4 | Case study re-run (Phase 4.1); sandbox preset (Phase 2.8) |
| A5 | Stress-Test Theatre | DESIGN §5.A5 | Trust center evidence link (Phase 2.11); transparency snippet (Phase 5.2) |
| B1 | Freshness Braid | DESIGN §6.B1 | Public Evidence Fabric snippet (Phase 2.19); status snippet (Phase 1.15) |
| B2 | Connector Character Cards | DESIGN §6.B2 | Trust center integrations matrix (Phase 2.11) |
| B3 | Schema Migration Storyboard | DESIGN §6.B3 | Changelog/release-notes anchor (Phase 1.15) |
| B4 | Quality Budget Dashboard | DESIGN §6.B4 | Trust center reliability page (Phase 2.11) |
| B5 | Profile Drift as Narrative | DESIGN §6.B5 | Public decision record evidence drilldown (Phase 4.5) |
| B6 | Lineage Gravity Map | DESIGN §6.B6 | Evidence Fabric source detail + lineage board (Phase 2.19) |
| C1 | Dispute / Objection Registry | DESIGN §7.C1 | Public dispute ledger surface (Phase 5.5) |
| C2 | Stakeholder Lens Switcher | DESIGN §7.C2 | Persona pages copy variants (Phase 3.2); transparency snippet (Phase 5.2) |
| C3 | Fairness / Bias Audit Panel | DESIGN §7.C3 | Trust center fairness posture page (Phase 2.11); EU AI Act conformity (Phase 5.2) |
| C4 | Embargo / Blackout Overlay | DESIGN §7.C5 | Trust center embargo / data residency page (Phase 2.11); decision packet caveat block (Phase 3.3 / 8.1) |
| C5 | Provenance Certificate | DESIGN §8.D2 / §7 | Public decision packet seal block (Phase 4.5); auditor portal evidence (Phase 5.7) |
| D1 | Run Choreography | DESIGN §8.D1 | Status incident detail timeline (Phase 1.15) |
| D2 | Live Run Monitor | DESIGN §8.D5 | Status / observability snippet (Phase 1.15) |
| D3 | Failure Triage | DESIGN §8.D5 | Status incident RCA library (Phase 1.15) |
| D4 | Capacity Planner | DESIGN §8.D4 | Calculator (Phase 2.9); quote builder (Phase 4.3) |
| D5 | Ops Audit Trail | DESIGN §8.D2 / §11 | Auditor portal SKU (Phase 5.7) |
| E1 | Argument Map (Toulmin) | DESIGN §9.E1 | Decision packet rationale (Phase 4.5); methodology longread (Phase 2.7) |
| E2 | Reasoning Chain | DESIGN §9.E2 | Decision packet evidence trail (Phase 4.5) |
| E3 | Uncertainty Decomposer (epistemic vs aleatoric) | DESIGN §9.E5 | Methodology longread (Phase 2.7); transparency snippet (Phase 5.2) |
| E4 | Counterfactual Explorer | DESIGN §9 / §10 | Sandbox preset (Phase 2.8); public consultation surface (Phase 6.6) |
| E5 | Evidence Synthesis (forest plot, meta-analytic weights) | DESIGN §9.E5 / §10 | Bibliography (Phase 2.17); methodology longread (Phase 2.7) |

### Current Production Anchors

| Area | Existing anchor | Current state |
| --- | --- | --- |
| Canonical frontend app | `apps/runtime-dashboard/**` | React/Vite app exists with routes, providers, Storybook, tests, a11y, visual, Lighthouse scripts. |
| Canonical app path transition | Canonical app path target = `apps/runtime-dashboard/**`; current/legacy transition path to reconcile = `policy-engine/apps/runtime-dashboard/**` until Phase 0.1 closes the rename PR gap | Phase 0.1 must close the rename/topology gap before Phase 1.7; until then, agents verify actual paths with `rg --files` before editing. |
| Public landing | `apps/runtime-dashboard/src/features/landing/**` | Minimal `LandingPage` with hero/capabilities/timeline/CTA and locale switch. Not a complete marketing site. |
| Auth | `apps/runtime-dashboard/src/features/auth/routes/LoginPage.tsx` | Minimal login/redirect surface only. No real flow matrix. |
| Product shell | `apps/runtime-dashboard/src/app/layout/**`, `src/app/workspaces.ts` | Six workspaces: Command Center, Scenario Composer, Runs/Decisions, Evidence Fabric, Lex Knowledge, Platform Health. |
| Command palette | `apps/runtime-dashboard/src/features/commandPalette/**` | Exists for app surfaces, not public web/docs/search/support/procurement. |
| Platform/settings | `apps/runtime-dashboard/src/features/platform/**` | Runtime health and appearance settings only. No workspace admin or personal settings depth. |
| Public decision viewer | `apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx` | Exists as signed public decision page, but needs real public decision record productization, SEO, PDF, transparency, and case-study links. |
| Decision/report/deck | `apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`, `RunDeckPage.tsx` | Exists for internal artifacts. Needs procurement/public packet variants and PDF-quality decision packet flow. |
| Evidence Fabric | `apps/runtime-dashboard/src/features/evidence/**` | Exists. Needs source detail, lineage map, public/civic data variants, and trust center links. |
| Docs | `docs/**`, `mkdocs.yml`, `landing/docs.html` prototype | Strong repository docs exist; public docs product surface is not implemented as an app experience. |
| Brand | `docs/brand/**`, `apps/runtime-dashboard/src/shared/brand/**`, `public/atlas/**` | Strong Atlas foundation. Needs Atlas Codex, animated glyphs, email/invoice/social artifacts, marketing dark mode, motion examples. |
| Compliance docs | `docs/compliance/**`, `docs/reference/security-compliance.md` | Internal evidence exists; public trust center/legal content and downloadable trust pack are not implemented. |
| Billing/procurement | no dedicated feature directory found | Missing. |
| Workspace admin settings | only appearance settings found | Missing. |
| Support/help center/tickets | no dedicated feature directory found | Missing. |
| Marketing content engine | no blog/resource/webinar/press/careers route families found | Missing. |

## Target State

### Public Market Surface

- A fast, mostly static, public Atlas site with distinct persona paths for
  analyst, ministry, regulator, NGO, academia, and procurement users.
- The first viewport shows PolicyOS/Atlas as the product, not abstract
  decoration.
- The homepage includes a playable demo, not only screenshots.
- Case studies can re-run into sandbox scenarios.
- Trust, procurement, docs, status, roadmap, changelog, resources, press,
  careers, and legal surfaces are first-class routed pages.
- Public pages expose `Save as PDF for tender pack` where procurement users
  need offline artifacts.
- Public conversion flows preserve procurement seriousness: demo booking,
  contact, career applications, partner inquiries, and roadmap voting have
  explicit privacy, spam/moderation, owner, and handoff rules.

### Authenticated Client Surface

- Auth covers password recovery, email verification, MFA, SSO, magic link,
  invite acceptance, tenant picker, first-run onboarding, step-up auth,
  session expiry, suspicious activity, account locked, logout confirmation, and
  leave-organization confirmation.
- Billing covers plan upgrade, procurement purchase order, VAT/EDRPOU/IBAN,
  VAT/НДС display, invoices, receipts, failed payment, trial lifecycle,
  cancellation/downgrade, add-ons, coupons, quote builder, and usage metering.
- Settings covers workspace, members, teams, roles, invitations, SSO, SCIM,
  audit log, API keys, PATs, webhooks, integrations, notifications, data
  residency, retention, branding, governance policy, profile, security,
  localization, appearance, connected accounts, data export, and danger zone.

### Documentation And Support

- Public docs become an information architecture, not one long page: landing,
  article, API explorer, SDK/CLI quickstarts, tutorials, search, examples,
  migration, version selector, ADR index/detail, glossary, print/PDF view,
  status incident snippet, and grounded docs assistant.
- Support has help center, knowledge-base article, ticket submission, ticket
  list/detail, incident detail, and DSAR/compliance request flows.

### Domain Differentiators

- Public decision record is a PR and accountability asset, not a hidden export.
- Governance inbox gives approvers a queue with apply/block/reason actions.
- Mobile quick approve is optimized for regulators outside the office.
- Evidence Fabric has source detail and lineage map.
- Procurement, UA/EU identity, EUDI Wallet readiness, EU AI Act transparency,
  civic data hub, and read-only regulator SKU become visible product surfaces.
- Reasoning is exposed editorially: Toulmin argument structure (claim → grounds
  → warrant → backing → rebuttal → qualifier), step-by-step reasoning chain with
  confidence delta per step, epistemic vs aleatoric uncertainty decomposition,
  counterfactual feature flip, and weight-of-evidence synthesis (forest plot)
  are visible on the public decision record and methodology longread, not only
  in the operator workspace.
- Identifiability is exposed at marketing depth: back-door / front-door / IV /
  RDD / DiD strategies, point/partial/set-identified taxonomy, E-value,
  Manski/Robins bounds appear in the methodology longread and Atlas Codex
  glossary so regulators and academics can verify claims.
- Bitemporal versioning (`valid_at` vs `transaction_at`) of every policy
  artifact, model card, schema, and ADR is a first-class concept across public
  surfaces — case study re-runs, changelog, public decision record, and quote
  builder all carry a bitemporal handle.

### Brand-As-Product Completeness

- v7 design-token deltas are productized: Janus medallion as decision stamp /
  score ring, Instrument Serif italic for citations/blockquotes/decision packet
  pull-quotes, density modes (×1.0 comfortable / ×0.75 compact / ×0.5
  condensed), CI tokens (50/80/95) and bounds-fill/stroke for uncertainty
  rendering, waterfall chart tokens (positive/negative/total), rim-light token
  for panels, soft-fill tokens for status pills, and the semantic typography
  classes `.t-display`, `.t-h1..h4`, `.t-body`, `.t-small`, `.t-eyebrow`,
  `.t-mono`, `.t-metric`, `.t-metric-md`, `.t-prose`, `.t-citation`.
- Janus medallion is consistently used as the decision stamp inside Public
  Decision Record, Decision Packet PDF, Trust Center seal block, and the
  signed-by avatar inside the governance inbox.
- All public surfaces support the three density modes by token, not by
  per-surface CSS. Density is set at workspace and personal-settings level.
- Mobile is a first-class surface family with its own landing, docs, and
  dashboard reading mode; the iOS Liquid Glass frame is treated as a design
  canvas / mockup vehicle, not a delivery target unless Phase 2.1 records a
  native commitment.
- A working design canvas (Storybook-backed) is a public Atlas Codex surface,
  not only an internal Figma proxy.

### Multi-Domain Topology

- Product runs on `atlas.policyos.dev` (or the equivalent canonical product
  domain chosen in Phase 1.5).
- Trust center runs on `trust.policyos.eu`.
- Status page runs on `status.policyos.eu`.
- Docs may run on a subdomain (`docs.policyos.dev` or
  `handbook.policyos.dev`) if Phase 1.5 records evidence that a split improves
  Lighthouse, search, or CSP posture; otherwise docs sit under the product
  domain.
- Subdomain choice is made once in Wave 0 with CSP/SRI, sitemap-per-domain,
  CDN, robots/canonical, RSS/ATOM feed, and OG metadata implications written
  down. Multi-tenant white-label subdomains (Phase 8.3) inherit this policy.

### Post-Launch Product Platform

- An operator certification program (training, exam, certificate, public
  certified-operator registry) exists from Wave 9 onward.
- An annual transparency report and a public benchmark vs alternative tools
  (with reproducible methodology) is published on a recurring cadence.
- A bug-bounty program, coordinated vulnerability disclosure policy,
  `security.txt`, and public ATOM/RSS feeds for changelog and decision record
  exist as first-class trust artifacts.
- An open-source strategy declares which parts of PolicyOS are open, the
  contribution path, the CLA model, and the license boundary; license header
  drift is gated.
- A research consortium and academic license exist with named partner
  institutions, code of conduct, and moderation policy.
- A multi-tenant white-label / ministry-branded subdomain mode and an external
  auditor portal SKU are available without breaking the canonical brand or
  trust posture.
- A public consultation surface lets citizens comment on proposed policy
  interventions with moderation, accessibility, and disclosure rules.
- A machine-readable transparency feed compatible with EU AI Office reporting
  expectations is exposed alongside the human-readable transparency snippet.

## Execution Principles

1. Ship from the current canonical app layout. Use `apps/runtime-dashboard/**`
   unless Wave 0 proves that a separate public app is required for bundle,
   routing, or deployment isolation.
2. Treat zip files as reference prototypes. Rebuild with production components,
   route modules, i18n, API hooks, accessibility, visual tests, and content
   contracts.
3. Maximize parallelism by path fence. Marketing pages, auth flows, billing,
   settings, docs, support, trust/legal, and domain product surfaces can
   prepare in parallel if they do not edit shared registries directly.
4. Serialize shared route, i18n, content schema, design-token, API, mock data,
   lockfile, and docs nav changes through short integration patches.
5. Separate public claims from internal evidence. Compliance/security/legal
   pages can publish only claims mapped to `docs/reference/**`,
   `docs/compliance/**`, runbooks, or approved legal copy.
6. Treat public forms as regulated intake surfaces. Every demo/contact/support,
   career, partner, DSAR, quote, and roadmap-vote form needs retention,
   consent, abuse/spam, attachment, and downstream-system ownership before
   launch.
7. Keep bundle budgets explicit. Public marketing should have a stricter JS
   budget than authenticated app workspaces.
8. Keep print as a product feature. Decision packets, docs articles,
   procurement pages, quotes, invoices, and trust artifacts need tested print
   styles.
9. Every page has loading, empty, error, unauthorized, region/license, degraded,
   offline, and print/read-only considerations before closeout.
10. Every form has validation, submission state, optimistic/non-optimistic
   policy, auditability, rate-limit copy, and privacy copy.
11. English, Ukrainian, and Russian are product requirements, not polish.
12. Governance features require step-up auth and audit events by default.
13. The plan exits into ADRs, reference docs, runbooks, content schemas,
    route manifests, visual evidence, and closeout reports.

## Parallel Safety Model

### Risk Classes

| Class | Work type | Parallel rule | Examples |
| --- | --- | --- | --- |
| C0 | read-only inventory, content audit, mock-only design exploration | always parallel | page inventory, zip-to-route map, competitive trust center audit |
| C1 | isolated content pages or stories with no shared route/i18n edits | parallel by path owner | case study detail draft, press page shell, careers page draft |
| C2 | new feature route family behind a local manifest and tests | parallel by path owner, serialized route registration | auth reset route set, billing invoice route set, settings members route set |
| C3 | route families sharing auth, billing, tenant, audit, or user settings state | parallel preparation, serialized contract/registry merge | onboarding + tenant picker, SSO config + SSO login picker |
| C4 | shared route registry, i18n catalogs, OpenAPI schema, generated client, design tokens, mock service worker, package/lockfile | serialized through queue | `routes.tsx`, `workspaces.ts`, locale files, OpenAPI additions |
| C5 | deployment topology, public app split, payment provider enablement, real SSO/eID production switch, legal publish gate | singleton decision/merge window | creating `apps/atlas-public-site`, turning on Stripe/gov-SSO |

### Ownership Fences

Every branch should declare one primary fence:

- public marketing site: homepage, solutions, customers, methodology, resources,
  blog, webinars, press, careers, partners, contact;
- interactive public demo/sandbox: playable demo, sandbox scenarios,
  decision-packet sample, calculators, live counters;
- trust/legal/procurement: trust center, compliance, legal docs, status,
  changelog, roadmap, procurement playbook, quote builder, sovereign deploy;
- auth/onboarding: login, signup, recovery, verification, MFA, SSO, magic link,
  invites, tenant picker, onboarding, step-up/session/suspicious states;
- billing/procurement-in-app: plans, payment methods, invoices, receipts,
  dunning, trials, cancellation, add-ons, coupons, usage, quote/order;
- workspace settings: organization, members, teams, invitations, SSO, SCIM,
  audit log, API keys, webhooks, integrations, notifications, residency,
  retention, branding, governance settings;
- personal settings: profile, security, notifications, localization,
  appearance, connected accounts, export data, danger zone;
- docs/support: docs IA, API explorer, tutorials, search, ADRs, glossary,
  support KB, tickets, incident detail, DSAR;
- domain product: public decision records, governance inbox, decision packets,
  mobile quick approve, Evidence Fabric source detail, civic data hub,
  transparency snippets;
- brand-as-product: animated glyphs, Atlas Codex, email templates, invoice
  artifacts, OG/social previews, print stylesheet, dark landing;
- platform/cross-cutting: global errors, banners, notification center, Cmd-K,
  offline/degraded, browser unsupported, license states, analytics;
- API/contracts: backend endpoints, OpenAPI schemas, generated clients, MSW
  handlers, test fixtures;
- QA/performance: a11y, visual, Lighthouse, bundle budgets, route coverage,
  print snapshots, i18n completeness.

### Shared Registry Serialization Queue

These files or file families must be touched through short queue-owned patches:

| Queue | Files/families | Merge owner | Rule |
| --- | --- | --- | --- |
| public route queue | `src/app/routes/routes.tsx`, route imports, public route redirects | team-frontend | Route families prepare locally; one registration patch at a time. |
| workspace queue | `src/app/workspaces.ts`, sidebar/surface registry, workspace permissions | team-frontend | New authenticated workspaces require one serialized workspace patch. |
| surface/command queue | `src/app/surfaces/**`, `src/features/commandPalette/**` | team-frontend | Register commands after route IDs and permissions are stable. |
| i18n queue | locale catalogs under `src/shared/i18n/**` | team-content/team-frontend | Content branches may include local draft keys, but final key merge is serialized. |
| design token queue | `src/styles/**`, `docs/brand/**`, design check scripts | team-design | Zip token drift and public dark-mode changes merge as small token patches. |
| API/OpenAPI queue | `schemas/runtime_api_v1.openapi.json`, generated API client, `src/api/**` | team-runtime/team-frontend | Schema/client generation is single-writer. |
| mock/fixture queue | MSW handlers, fixture catalogs, public sandbox seed data | team-quality | Scenario fixture IDs and contract shapes merge once per wave. |
| analytics/experiments queue | public event taxonomy, attribution policy, experiment flags, RUM destinations | team-growth/team-quality | Consent-aware measurement changes merge before CTA/form launch. |
| lead destination queue | CRM/calendar/support/careers/newsletter/roadmap destination health fixtures | team-revenue/team-ops | No public intake form ships without a green destination health check. |
| package/lockfile queue | `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml` | team-devx | No source changes in lockfile-only patches. |
| docs nav queue | `mkdocs.yml`, generated docs nav, docs index pages | team-docs | Public docs IA and repository docs nav coordinate here. |
| legal/compliance queue | approved trust/legal copy, DPA/SLA/AUP/Subprocessor pages | team-legal/team-security | No unsupported public claims. |
| deployment queue | Vite config, public app split, CDN/Pages config, CSP/SRI | team-platform/team-security | Bundle/deployment topology changes are C5 singleton. |

### Safe Parallel Lanes

| Lane | Safe parallel units | Serialized points |
| --- | --- | --- |
| Marketing IA | solutions, customers, methodology, resources, blog, press, careers, partners | public route queue, i18n queue |
| Interactive demo | playable composer, sandbox scenarios, public decision sample, ROI/TCO calculator, live counters | mock fixture queue, API queue |
| Trust/procurement | trust center, legal, procurement playbook, quote builder, sovereign deploy, compliance matrix | legal/compliance queue, API queue for quote generation |
| Public measurement | event taxonomy, attribution, experiment flags, RUM, synthetic checks | analytics/experiments queue, consent queue |
| Public intake | demo/contact, partner, career, DSAR, FOI, newsletter, roadmap voting | lead destination queue, privacy/legal queue |
| Auth | recovery, verification, MFA, SSO, magic link, invites, tenant picker, onboarding, step-up | auth contract/API queue |
| Billing | plan picker, payment methods, invoices, receipts, dunning, trials, add-ons, usage | billing API/OpenAPI queue, legal/compliance queue |
| Settings | workspace admin, personal settings, governance settings, integrations | workspace queue, permission queue, audit API queue |
| Docs/support | docs IA, API explorer, SDK/CLI quickstart, support KB, tickets, DSAR | docs nav queue, search index queue |
| Domain differentiators | public decision record, governance inbox, PDF packet, mobile approve, lineage map, transparency widget | route queue, API queue, governance audit queue |
| Brand-as-product | animated glyphs, email, invoices, OG cards, print styles, Atlas Codex | design token queue, asset placement queue |
| QA | a11y, visual, Lighthouse, bundle, route coverage, print, i18n | test config/CI queue |

### Do-Not-Parallelize Pairs

These can prepare in parallel but should not merge physical/shared changes in
parallel:

- public app split with any route-wide refactor or Vite deployment change;
- marketing homepage route registration with landing route deletion/rename;
- SSO login picker with workspace SSO settings API contract;
- tenant picker with first-run onboarding state machine;
- billing plan picker with marketing pricing/quote pricing model;
- quote builder with invoice/receipt legal artifact templates;
- governance settings with governance inbox action contracts;
- public decision record with public decision packet signing contract changes;
- docs search index with global Cmd-K search provider changes;
- public status page with in-app degraded/incident banner source changes;
- public contact/demo scheduling with CRM/calendar integration changes;
- careers/application intake with PII retention and attachment handling
  changes;
- public roadmap voting with moderation/abuse controls;
- cookie consent with analytics instrumentation changes;
- i18n catalog normalization with broad page-content key migrations;
- Atlas token changes with visual snapshot regeneration;
- lockfile changes with source-heavy frontend branches.

## Program Control Ledger

### Severity Labels

| Severity | Definition | Exception authority |
| --- | --- | --- |
| P0 | Blocks real launch, compliance trust, auth safety, or procurement path. | security lead + legal lead + product lead joint sign-off, dated |
| P1 | Core buyer/user journey missing or misleading. | product lead + relevant fence owner |
| P2 | Important adoption, operability, support, or governance gap. | relevant fence owner |
| P3 | Brand/content/community/polish gap that materially affects premium trust. | relevant fence owner |
| P4 | Long-tail polish, content volume, or non-blocking enhancement. | relevant fence owner |

### Branch Naming Patterns

| Pattern | Intended fence |
| --- | --- |
| `codex/atlas-public-*` | public marketing, public docs, public sandbox |
| `codex/atlas-trust-*` | trust, legal, compliance, procurement, status |
| `codex/atlas-auth-*` | auth, onboarding, tenant picker, session states |
| `codex/atlas-billing-*` | billing, invoices, usage, quotes, procurement order |
| `codex/atlas-settings-*` | workspace/personal settings and admin surfaces |
| `codex/atlas-docs-*` | docs IA, API explorer, support KB, tickets |
| `codex/atlas-domain-*` | public decision records, governance inbox, lineage, civic data |
| `codex/atlas-brand-*` | animated glyphs, Atlas Codex, email/invoice/social/print |
| `codex/atlas-crosscutting-*` | empty/error/loading/offline/banners/Cmd-K/notifications |
| `codex/atlas-quality-*` | visual, a11y, bundle, Lighthouse, i18n, route coverage |

### Product Surface Dashboard

Every wave closeout updates this dashboard row with a measured value, evidence
link, or dated exception.

| Metric | Owner | Baseline on 2026-05-06 | Target |
| --- | --- | --- | --- |
| Public route coverage | team-frontend | minimal `/welcome` landing plus public decision viewer | all planned public routes have route IDs, tests, sitemap entries |
| Zip adoption coverage | team-design | assets mostly copied; landing/auth/docs prototypes not productionized | every zip file either adopted, archived as fixture, or explicitly rejected |
| Persona journey coverage | team-content | no dedicated persona routes | analyst, ministry, regulator, NGO, academia, procurement paths complete |
| Auth flow coverage | team-identity | minimal login screen only | all auth/onboarding/session states covered by route tests |
| Billing/procurement coverage | team-revenue | no dedicated route family | plans, invoices, usage, quote/procurement order, dunning, cancellation complete |
| Settings coverage | team-product | appearance section only | workspace and personal settings route families complete |
| Public trust coverage | team-security | internal compliance docs exist | public trust center has mapped evidence and approved claims |
| Docs/support coverage | team-docs | repository docs strong, public docs app missing | docs IA, search, API explorer, support/tickets/DSAR complete |
| Domain differentiator coverage | team-product | public decision viewer partial | public decisions, governance inbox, mobile approve, source lineage complete |
| Cross-cutting state coverage | team-quality | mixed local states | all major surfaces have empty/loading/error/offline/license/print states |
| i18n completeness | team-content | existing app locales partial by feature | en/uk/ru keys complete for all route families |
| Public performance | team-performance | no public-site budget for full marketing IA | public homepage Lighthouse 100/100/100/100 and JS budget agreed in Wave 0 |
| Print/PDF readiness | team-design | product print styles exist | tender pack, docs, decision packet, invoice, trust artifacts pass print snapshots |
| Backend contract lock | team-runtime | ad hoc fixture/API assumptions | every Wave 2-8 UI flow is `ready`, `stub-locked`, or `blocked` before implementation |
| Content register ownership | team-content | content types named, owners not complete | every localized public content type has register owner and register tag policy |
| Public analytics/attribution | team-growth | consent-gated analytics only | every CTA/form/demo event has taxonomy, destination, and consent-aware experiment policy |
| Continuous gates ratchet | team-quality | launch gates concentrated in Wave 10 | security, privacy, route, content, a11y, bundle, and claim gates ratchet from Wave 0 |
| Jurisdiction scope | team-legal | UA/EU implied but not fully tagged | every legal/trust/procurement claim and page has jurisdiction tag and risk posture |
| Lead routing health | team-revenue | downstream owner declared only | every public form has destination system and green health-check fixture |
| Public telemetry | team-ops | Lighthouse lab checks only | RUM, JS error reporting, and synthetic checks cover public critical routes |
| v7 surface adoption | team-design | v6 baseline only | every v7 landing surface (calculator, trust, status, case-study, decision-packet, emails, mobile, components, api, onboarding, empty-states, states, error-pages, design-canvas, iOS frame) is productized, archived as Storybook reference, or rejected with reason |
| Advanced surface register | team-design + team-product | not yet cross-referenced | every A1–E5 surface has a row in the v7 Advanced Surface Register pointing at the DESIGN plan |
| Multi-domain topology | team-platform + team-security | single canonical domain assumed | atlas.policyos.dev / trust.policyos.eu / status.policyos.eu / optional docs subdomain are decided with CSP/SRI/sitemap/CDN/RSS plan |
| Content backend | team-content + team-frontend | not declared | CMS choice (markdown-in-repo vs headless) is recorded with editorial PR flow, translator workflow, and preview environments |
| Brand-as-product completeness | team-design | partial v4/v6 tokens | Janus medallion, Instrument Serif citation, density modes, CI/bounds/waterfall/rim-light/soft-fill, semantic .t-* classes adopted with one design-token patch |
| Reasoning surface coverage | team-product + team-content | not surfaced in marketing | Toulmin, identifiability vocabulary, E-value, Manski/Robins, epistemic/aleatoric, forest-plot, bitemporal appear on methodology + Atlas Codex |
| Operator certification | team-product + team-content | absent | certification program (training, exam, certificate, public registry) is live or has dated launch plan |
| Transparency report cadence | team-trust + team-content | absent | annual transparency report and public benchmark methodology have owner, schedule, and reproducibility manifest |
| Bug bounty / CVD | team-security | absent | bug bounty + CVD policy + security.txt + ATOM/RSS feeds exist with named scope and budget |
| Open source strategy | team-platform + team-legal | absent | OSS license boundary, contribution path, CLA, and license-header drift gate exist |
| EU AI Office reporting feed | team-domain + team-security | absent | machine-readable transparency feed posture is recorded as ready/planned/blocked with evidence |

### Subplan Relationship

| Existing plan | Relationship |
| --- | --- |
| `DESIGN_BEST_IN_CLASS_PLAN.md` | Owns deep Atlas product interaction backlog (Tracks A–G; A1 Causal Atlas → G operator craft). This plan owns marketing/client/trust/procurement/support/auth/billing/settings expansion and the public/print/embed/transparency cross-surfaces that ride on top of those tracks. The v7 Advanced Surface Register is the canonical pointer; this plan must not duplicate Track-level tracking. |
| `FRONTEND_SOTA_PLAN.md` | Owns frontend architecture, UX principles, accessibility, performance, and shell quality. This plan consumes those gates. |
| `DOCUMENTATION_SOTA_PLAN.md` | Owns repository documentation lifecycle. This plan adds public docs/support product surfaces and must not fork factual docs source of truth. |
| `INFRASTRUCTURE_SOTA_PLAN.md` | Owns deployment, CI, release, supply-chain, and platform controls. This plan queues public app/deployment/security changes through it. |
| `REPOSITORY_BEST_IN_CLASS_REMEDIATION_MASTER_PLAN.md` | Owns repository-wide safety, queue, and closeout discipline. This plan mirrors its wave-first execution model. |

## Finding Ledger

| ID | Severity | Gap | Primary fence | Target wave |
| --- | --- | --- | --- | --- |
| MKT-01 | P0 | Public marketing site is only a minimal landing route and zip prototype. | public marketing | 1-3 (shell W1.7, primitives W2, homepage W3.1) |
| MKT-02 | P1 | No persona/use-case segmentation for analyst, ministry, regulator, NGO, academia. | public marketing | 3 (W3.2) |
| MKT-03 | P1 | No customers/case studies with detailed simulation/verification/result pages. | public marketing | 4 (W4.1) |
| MKT-04 | P1 | No Methodology/Science page for causal estimates, identifiability, JAX, validation, literature/ADR links. | public marketing | 2 (W2.7) |
| MKT-05 | P1 | No blog/insights, resource library, webinars/events, press/media kit, glossary, about, careers, partners, contact/demo route families. | public marketing | 2 (content engine W2.17, careers/partners W2.10) |
| MKT-06 | P1 | Homepage lacks playable product demo, sandbox, decision packet sample, ROI/TCO calculator, and live counters. | interactive demo | 2-3 (sandbox W2.8, calculator W2.9, packet sample W3.3, homepage W3.1) |
| MKT-07 | P1 | Contact/demo, career applications, partner inquiries, and roadmap votes need scheduling, qualification, privacy, moderation, and downstream handoff contracts. | public marketing | 0 (lead destination) + 2 (W2.10) |
| CONTRACT-01 | P0 | Wave 2-8 UI flows can drift if they start from fixtures without accepted OpenAPI or locked stubs. | API/contracts | 0 (W0.7) |
| CONTENT-01 | P1 | Localized public routes can be registered without named register owners for formal uk/ru copy. | public marketing | 0 (W0.8) |
| ANALYTICS-01 | P1 | Consent-gated analytics exists conceptually, but CTA/form/demo events lack taxonomy, attribution, and experiment destinations. | QA/performance + public marketing | 0 (W0.9) + 1 (W1.9 consent foundation) |
| GATE-01 | P0 | Security/privacy/performance/content gates are concentrated too late if Wave 10 is first enforcement. | QA/performance | 0 (W0.10) |
| JUR-01 | P0 | UA/EU jurisdiction scope, out-of-scope jurisdictions, FOI, e-invoicing, e-signature, and AI Act posture are not locked before sales/procurement pages. | trust/legal/procurement | 0 (W0.11) |
| LEAD-01 | P1 | Public forms can collect leads without health-checked CRM/calendar/support/careers/newsletter destinations. | API/contracts | 0 (W0.12) |
| SANDBOX-01 | P1 | Public sandbox engine choice is an architecture fork that affects performance and demo quality. | interactive public demo | 1 (W1.4) |
| TRUST-01 | P0 | No public Trust Center with SOC 2/ISO/GDPR/residency/subprocessors/DPA/AUP/SLA/security questionnaire/VPAT/a11y/on-prem evidence. | trust/legal | 2 (W2.11) |
| TRUST-02 | P0 | No public legal route family for ToS, Privacy, DPA, AUP, SLA, subprocessors, cookies. | trust/legal | 1 (W1.12) |
| TRUST-03 | P1 | No status page with incident history/RCA, public changelog, or public roadmap. | trust/status | 1 (W1.15) |
| TRUST-04 | P1 | No procurement playbook, tender boilerplate, CPV/Prozorro/EDRPOU/VAT content, quote builder, or reference architecture for gov IT. | procurement | 3 (W3.4) + 4 (W4.3 quote builder) |
| AUTH-01 | P0 | Auth has no forgot/reset/email verification/MFA/SSO/magic link/invite/tenant picker/first-run/session security flows. | auth/onboarding | 1 (W1.11 state machine) + 2 (W2.12-2.14 flows) + 3 (W3.6 onboarding) |
| AUTH-03 | P1 | Session expired, account locked, suspicious activity, logout confirmation, and leave-organization states are listed but need explicit implementation phases. | auth/onboarding | 7 (W7.1) |
| AUTH-02 | P0 | Governance-sensitive actions lack visible step-up auth states. | auth/onboarding | 2 (W2.13 MFA) + 8 (W8.1 governance inbox step-up) |
| BILL-01 | P0 | No in-app billing/procurement surfaces. | billing | 5 (W5.1 scaffold) + 6 (W6.1-6.4 detail) |
| BILL-02 | P1 | No invoices, receipts, failed payment timeline, trial expiration, cancellation, add-ons, coupons, usage metering, quote/procurement order. | billing | 6 (W6.1-6.4) |
| SET-01 | P0 | No workspace admin settings for organization, members, roles, teams, invitations, SSO, SCIM, audit, keys, webhooks, integrations. | workspace settings | 6 (W6.5 IA) + 7 (W7.2-7.4 detail) |
| SET-02 | P1 | No governance settings for quorum, approvers, escalation, freeze windows, blockers. | workspace settings | 7 (W7.5) |
| SET-03 | P1 | No personal settings beyond appearance controls. | personal settings | 7 (W7.6) |
| DOCS-01 | P1 | Docs prototype is a long page; public docs IA, article view, API explorer, tutorials, search, versions, ADR detail, glossary missing. | docs/support | 1 (W1.16 API/SDK quickstarts) + 2 (W2.15 docs IA, W2.18 API longread) + 3 (W3.7 search) |
| DOCS-02 | P1 | No grounded docs assistant from ADR/docs/OpenAPI with source citations. | docs/support | 5 (W5.6) |
| SUP-01 | P1 | No help center, ticket forms/list/detail, incident detail, or DSAR request flow. | docs/support | 2 (W2.16) |
| SYS-01 | P1 | Empty/loading/error/401/403/404/500/region/browser/maintenance/offline/license states are not systematic across new surfaces. | cross-cutting | 1 (W1.10) |
| SYS-02 | P1 | Notification center, browser notification setup, and public+app Cmd-K search are incomplete. | cross-cutting | 4 (W4.6) |
| DOM-01 | P1 | Public decision record is partial and not fully productized for transparency, SEO, PDF, and case-study reuse. | domain product | 4 (W4.5) |
| DOM-02 | P1 | Governance inbox and mobile quick approve are missing. | domain product | 8 (W8.1) |
| DOM-03 | P1 | Evidence Fabric source detail and lineage map need standalone board/product route. | domain product | 2 (W2.19) |
| DOM-04 | P2 | Civic data hub, read-only regulator SKU, and EU AI Act transparency snippet are missing. | domain product | 5 (W5.2 transparency) + 7 (W7.7 civic data) |
| BRAND-01 | P2 | Animated glyphs, Atlas Codex, email design system, designed invoices/receipts, social previews, dark landing, motion language examples missing. | brand-as-product | 2 (W2.20 animations) + 3 (W3.10 Codex) + 7 (W7.8 advanced email/invoice/social) |
| EMAIL-01 | P1 | Transactional email foundation must exist before auth/support/governance flows ship. | brand-as-product | 2 (W2.4) |
| TELEMETRY-01 | P1 | Public RUM, JS error reporting, and synthetic uptime checks are absent from early public launch gates. | QA/performance | 2 (W2.6) |
| PERF-01 | P0 | Public marketing performance budgets and Lighthouse 100 target are not enforced. | QA/performance | 0 (W0.2 budget) + 10 (W10.3 enforcement) |
| SEO-01 | P1 | Public sitemap, robots, canonical URLs, structured data, and share metadata need explicit launch gates. | QA/performance | 0 (W0.3 content model) + 10 (W10.1 route/sitemap gate) |
| I18N-01 | P1 | Localization is not marketed as a feature and not complete across proposed surfaces. | cross-cutting | 1-10 (content registry W1.8, ratchets across) |
| ZIP-V7-01 | P1 | v7 design surfaces (calculator, trust, status, case-study, decision-packet, emails, mobile, components, api, onboarding, empty-states, states, error-pages, design-canvas, iOS frame) are not yet productized. | brand-as-product + public marketing | 1-9 (spread across restructured waves) |
| ZIP-V7-02 | P2 | 25 advanced A1–E5 dashboard surfaces from v7 `ui_kits/dashboard/**` do not have a cross-reference register pointing at `DESIGN_BEST_IN_CLASS_PLAN.md`. | domain product + brand-as-product | 1 (W1.1) |
| TOPO-01 | P0 | Multi-domain topology (`atlas.policyos.dev`, `trust.policyos.eu`, `status.policyos.eu`, optional docs subdomain) is implied by v7 OG metadata but never decided. | platform/cross-cutting + trust/legal/procurement | 1 (W1.5 decision) + 3 (W3.5 rollout) |
| CMS-01 | P1 | Content backend (markdown-in-repo vs headless CMS such as Sanity/Strapi/Contentful) is not declared; editorial PR flow, translator workflow, and preview environments are undefined. | public marketing + docs/support | 1 (W1.6) |
| BRAND-02 | P2 | Janus medallion as decision stamp / score ring is not consistently used in Public Decision Record, Decision Packet PDF, Trust Center seal, or governance inbox signed-by avatar. | brand-as-product | 2 (W2.2 primitive) + 4 (W4.5 decision record) + 8 (W8.1 governance inbox) |
| BRAND-03 | P2 | v7 token deltas (Instrument Serif citation, density modes, CI/bounds/waterfall/rim-light/soft-fill tokens, `.t-*` semantic typography classes) are not yet enforced in public primitives. | brand-as-product | 1 (W1.2 drift diff) + 2 (W2.3 primitives) |
| DOM-05 | P2 | Toulmin argument structure, identifiability vocabulary, E-value, Manski/Robins bounds, epistemic vs aleatoric decomposition, forest-plot meta-analysis, and bitemporal versioning are not surfaced in marketing / methodology / Atlas Codex. | domain product + public marketing | 2 (W2.7 methodology) + 3 (W3.9 identifiability) + 5 (W5.3 reasoning surfaces) |
| DOM-06 | P2 | Provenance certificate (SHA-256 hash tree + ed25519 multi-party seal) is not a public surface beyond the decision packet print spec. | domain product | 5 (W5.4) |
| IOS-01 | P2 | iOS Liquid Glass mobile system and dedicated mobile landing/docs/dashboard reading mode are not declared as scope decisions; v7 ships `ios-frame.jsx` and `mobile.html` as prototypes only. | brand-as-product + interactive demo | 2 (W2.1 decision) + 9 (W9.1 implementation) |
| CANVAS-01 | P3 | v7 `design-canvas.jsx` (Figma-ish working canvas with sidecar persistence) has no production analogue; Atlas Codex working canvas is unscoped. | brand-as-product | 4 (W4.7) |
| OPS-CERT-01 | P2 | Operator certification program (training, exam, certificate, public certified-operator registry) is not scheduled. | post-launch product platform | 9 (W9.2) |
| TRANS-REPORT-01 | P2 | Annual transparency report cadence and public benchmark methodology are not scheduled. | post-launch product platform + trust/status | 1 (W1.13 scaffold) + 4 (W4.8 first issue) |
| BUG-BOUNTY-01 | P1 | Bug bounty / coordinated vulnerability disclosure policy, `security.txt`, and public ATOM/RSS feeds for changelog and decision record are absent. | trust/legal/procurement + post-launch product platform | 4 (W4.4) |
| OSS-01 | P2 | Open-source strategy (which parts open, contribution path, CLA, license header drift) is absent. | post-launch product platform | 1 (W1.17) |
| RESEARCH-CONS-01 | P2 | Research consortium / academic license program, named partner institutions, code of conduct, and moderation policy are absent. | post-launch product platform + public marketing | 3 (W3.11) |
| TENANT-WL-01 | P2 | Multi-tenant white-label / ministry-branded subdomain mode is not declared; inherits Phase 1.5 topology decision. | post-launch product platform + platform/cross-cutting | 8 (W8.2) |
| AUDITOR-01 | P2 | External auditor portal SKU (read-only audit access with provenance-certificate evidence) is absent. | post-launch product platform + domain product | 8 (W8.3) |
| CONSULT-01 | P2 | Public consultation surface (citizen comment on proposed interventions, moderation, accessibility, disclosure) is absent. | post-launch product platform + domain product | 5 (W5.7) |
| AI-OFFICE-01 | P1 | EU AI Office machine-readable transparency feed posture is not declared (separate from the human-readable Article 13/14 snippet). | trust/legal/procurement + domain product | 5 (W5.2 snippet) + 6 (W6.6 feed) |
| SOVEREIGN-01 | P2 | Sovereign cloud variants (AWS GovCloud, OVHcloud Strasbourg, Hetzner Frankfurt, UA Cloud Strategy) and air-gapped delivery kit posture are not declared. | trust/legal/procurement + post-launch product platform | 1 (W1.14) |
| CODEX-GOV-01 | P3 | Atlas Codex has no governance process (RFC / Atlas Improvement Proposal). | brand-as-product + post-launch product platform | 4 (W4.9) |

## File And Route Strategy

Wave 0 must choose between two topology options through a short decision note:

| Option | Shape | Use when | Risk |
| --- | --- | --- | --- |
| A. Single app, public route groups | Continue using `apps/runtime-dashboard/src/features/landing`, add `marketing`, `trust`, `docs`, `support`, `legal` route families inside current app | fastest adoption, fewer workspace changes | public bundle may inherit dashboard weight unless route splitting is strict |
| B. Separate public app | Create `apps/atlas-public-site/**` and shared `packages/atlas-ui` or carefully exported shared primitives | best public performance and deployment separation | C5 topology, lockfile, build/deploy, shared UI packaging work |

Default assumption until Wave 0 proves otherwise: start with Option A and keep
public routes aggressively lazy-split. Escalate to Option B only if public
homepage cannot meet the agreed JS and Lighthouse budget.

Planned route families under Option A:

| Route family | Primary directory | Notes |
| --- | --- | --- |
| Public home | `apps/runtime-dashboard/src/features/landing/**` | Expand current `LandingPage`; keep `/welcome`. |
| Marketing | `apps/runtime-dashboard/src/features/marketing/**` | Solutions, customers, case studies, methodology, blog, resources, webinars, press, about, careers, partners, contact. |
| Public sandbox | `apps/runtime-dashboard/src/features/publicSandbox/**` | Playable demo, scenario presets, re-run case, calculators, counters. |
| Trust/legal/procurement | `apps/runtime-dashboard/src/features/trust/**`, `features/legal/**`, `features/procurement/**` | Trust center, status, changelog, roadmap, legal pages, quote builder, tender pack. |
| Auth/onboarding | `apps/runtime-dashboard/src/features/auth/**`, `features/onboarding/**` | Extend existing auth and onboarding route modules. |
| Billing | `apps/runtime-dashboard/src/features/billing/**` | In-app billing, invoices, usage, subscriptions, procurement orders. |
| Settings | `apps/runtime-dashboard/src/features/settings/**` | New workspace and personal settings route family; platform health remains separate. |
| Public docs/support | `apps/runtime-dashboard/src/features/docs/**`, `features/support/**` | Public docs product shell and help center; do not duplicate factual docs source. |
| Domain public/accountability | `apps/runtime-dashboard/src/features/publicDecisions/**`, `features/governance/**` | Public decision record, governance inbox, mobile quick approve. |
| Brand artifacts | `apps/runtime-dashboard/src/features/brandArtifacts/**`, `src/shared/brand/**` | Atlas Codex, glyph animation, emails, OG, invoice/receipt, print. |

## Detailed Workstreams

Rule: all phases inside a wave are strictly parallel. Every phase
depends only on phases in PRIOR waves, never on a peer in the same wave.
If a phase needs an output from another phase, that other phase lives in
an earlier wave. This is the topological-tier structure of the program.

Shared registries (route, i18n, OpenAPI, design-token, etc.) still serialize
through their queue owner inside each wave — the queue is the merge gate,
not a dependency.

### Wave / Phase Crosswalk

New ID maps to the previous identifier from the v6/v7 plan history.
All historical references resolve through this table.

| New ID | Phase name | Old ID | New wave | Old wave |
| --- | --- | --- | --- | --- |
| 0.1 | Zip Adoption Ledger | 0.1 | W0 | W0 |
| 0.2 | Public Topology Decision | 0.2 | W0 | W0 |
| 0.3 | Public Content Model And Route Manifest | 0.3 | W0 | W0 |
| 0.4 | API/Fixture Contract Inventory | 0.4 | W0 | W0 |
| 0.5 | Legal, Compliance, And Claim Evidence Map | 0.5 | W0 | W0 |
| 0.6 | Cross-Cutting State Inventory | 0.6 | W0 | W0 |
| 0.7 | Backend Contract Lock | 0.7 | W0 | W0 |
| 0.8 | Content Capacity And Register Ownership | 0.8 | W0 | W0 |
| 0.9 | Analytics, Experiments, And Attribution Contract | 0.9 | W0 | W0 |
| 0.10 | Continuous Gates Ratchet | 0.10 | W0 | W0 |
| 0.11 | Jurisdictional Scope | 0.11 | W0 | W0 |
| 0.12 | Lead Routing And CRM Destination | 0.12 | W0 | W0 |
| 1.1 | v7 Advanced Surface Register Cross-Reference | 0.16 | W1 | W0 |
| 1.2 | v7 Design-Token Drift | 0.17 | W1 | W0 |
| 1.3 | Atlas Public Page Primitives | 1.3 | W1 | W1 |
| 1.4 | Sandbox Engine Choice | 0.13 | W1 | W0 |
| 1.5 | Multi-Domain Topology | 0.14 | W1 | W0 |
| 1.6 | Content Backend Strategy | 0.15 | W1 | W0 |
| 1.7 | Public Shell And Navigation | 1.1 | W1 | W1 |
| 1.8 | Content Registry And Localized Copy Pipeline | 1.2 | W1 | W1 |
| 1.9 | Cookie, Privacy, Analytics, And Consent Foundation | 1.4 | W1 | W1 |
| 1.10 | Global Empty, Loading, Error, Offline, License States | 9.3 | W1 | W9 |
| 1.11 | Auth Flow State Machine | 4.1 | W1 | W4 |
| 1.12 | Legal Route Family | 3.3 | W1 | W3 |
| 1.13 | Annual Transparency Report Scaffold | 3.8 | W1 | W3 |
| 1.14 | Sovereign Cloud Variants And Air-Gapped Delivery Kit | 3.9 | W1 | W3 |
| 1.15 | Status, Changelog, Release Notes, And Roadmap | 3.2 | W1 | W3 |
| 1.16 | API Reference, SDK/CLI Quickstarts, Tutorials | 7.2 | W1 | W7 |
| 1.17 | Open Source Strategy And Contribution Path | 11.3 | W1 | W11 |
| 2.1 | iOS / Mobile System Decision | 0.18 | W2 | W0 |
| 2.2 | Janus Medallion And Provenance Stamp Primitives | 1.8 | W2 | W1 |
| 2.3 | Citation Typography, Density Modes, And Reasoning Primitives | 1.9 | W2 | W1 |
| 2.4 | Atlas Email Foundation | 1.5 | W2 | W1 |
| 2.5 | OG/Social Preview Generator | 1.6 | W2 | W1 |
| 2.6 | Public RUM, Error Reporting, And Synthetic Checks | 1.7 | W2 | W1 |
| 2.7 | Methodology And Science Surface | 2.4 | W2 | W2 |
| 2.8 | Public Sandbox And Playable Demo | 2.5 | W2 | W2 |
| 2.9 | ROI/TCO Calculator And Live Counters | 2.7 | W2 | W2 |
| 2.10 | Service, Conversion, Careers, And Partner Routes | 2.8 | W2 | W2 |
| 2.11 | Trust Center | 3.1 | W2 | W3 |
| 2.12 | Recovery, Verification, Magic Link | 4.2 | W2 | W4 |
| 2.13 | MFA And Recovery Codes | 4.3 | W2 | W4 |
| 2.14 | SSO, Government Identity, Invites, Tenant Picker | 4.4 | W2 | W4 |
| 2.15 | Public Docs IA And Article View | 7.1 | W2 | W7 |
| 2.16 | Help Center, Tickets, Incident Detail, DSAR, And FOI | 7.4 | W2 | W7 |
| 2.17 | Editorial Content Engine And Community | 7.5 | W2 | W7 |
| 2.18 | Atlas API Reference Longread | 7.7 | W2 | W7 |
| 2.19 | Evidence Fabric Source Detail And Lineage Map | 8.3 | W2 | W8 |
| 2.20 | Animated Glyphs And Motion Language | 9.1 | W2 | W9 |
| 3.1 | Homepage Upgrade With Playable Demo Entry | 2.1 | W3 | W2 |
| 3.2 | Persona Solutions And Use Cases | 2.2 | W3 | W2 |
| 3.3 | Decision Packet Sample | 2.6 | W3 | W2 |
| 3.4 | Procurement Playbook And Tender Pack | 3.4 | W3 | W3 |
| 3.5 | Subdomain Rollout (Trust And Status) | 3.6 | W3 | W3 |
| 3.6 | First-Run Onboarding Wizard | 4.5 | W3 | W4 |
| 3.7 | Search, Cmd-K Public Provider, ADR Index, Glossary | 7.3 | W3 | W7 |
| 3.8 | Public Components Gallery | 7.6 | W3 | W7 |
| 3.9 | Identifiability Surface As Methodology Anchor | 8.9 | W3 | W8 |
| 3.10 | Atlas Codex And Localization-As-Feature | 9.5 | W3 | W9 |
| 3.11 | Research Consortium And Academic License | 11.4 | W3 | W11 |
| 4.1 | Customers And Case Studies | 2.3 | W4 | W2 |
| 4.2 | Public Governance-On-The-Go Demo | 2.9 | W4 | W2 |
| 4.3 | Public Quote Builder Shell | 3.5 | W4 | W3 |
| 4.4 | Bug Bounty, CVD, security.txt, RSS / ATOM Feeds | 3.7 | W4 | W3 |
| 4.5 | Public Decision Record Productization | 8.1 | W4 | W8 |
| 4.6 | Notification Center And Global Cmd-K | 9.4 | W4 | W9 |
| 4.7 | Atlas Codex Working Canvas (Design Canvas) | 9.8 | W4 | W9 |
| 4.8 | Annual Transparency Report And Public Benchmark | 11.2 | W4 | W11 |
| 4.9 | Atlas Codex Governance (Improvement Proposals) | 11.9 | W4 | W11 |
| 5.1 | Billing Contract And Navigation | 5.1 | W5 | W5 |
| 5.2 | EU AI Act Transparency And Conformity Readiness | 8.5 | W5 | W8 |
| 5.3 | Public Reasoning Surfaces (Cross-Surface Of E1-E5) | 8.6 | W5 | W8 |
| 5.4 | Public Provenance Certificate | 8.7 | W5 | W8 |
| 5.5 | Public Dispute Ledger Surface | 8.8 | W5 | W8 |
| 5.6 | Grounded Docs Assistant | 9.6 | W5 | W9 |
| 5.7 | Public Consultation Surface | 11.7 | W5 | W11 |
| 6.1 | Plan Picker, Add-Ons, Trial Lifecycle | 5.2 | W6 | W5 |
| 6.2 | Payment Methods, Billing Address, VAT/EDRPOU | 5.3 | W6 | W5 |
| 6.3 | Invoices, Receipts, Failed Payment, Dunning | 5.4 | W6 | W5 |
| 6.4 | Cancel, Downgrade, Pause, Coupons, Usage | 5.5 | W6 | W5 |
| 6.5 | Settings Route Family And IA | 6.1 | W6 | W6 |
| 6.6 | EU AI Office Machine-Readable Transparency Feed | 11.8 | W6 | W11 |
| 7.1 | Session, Risk, Logout, And Organization Exit States | 4.6 | W7 | W4 |
| 7.2 | Workspace General, Members, Roles, Teams, Invitations | 6.2 | W7 | W6 |
| 7.3 | SSO, SCIM, Audit, API Keys, Webhooks | 6.3 | W7 | W6 |
| 7.4 | Integrations, Notifications, Residency, Retention, Branding | 6.4 | W7 | W6 |
| 7.5 | Governance Settings | 6.5 | W7 | W6 |
| 7.6 | Personal Profile, Security, Preferences, Danger Zone | 6.6 | W7 | W6 |
| 7.7 | Civic Data Hub And Regulator Read-Only SKU | 8.4 | W7 | W8 |
| 7.8 | Advanced Email, Invoice, Receipt, And Social Artifacts | 9.2 | W7 | W9 |
| 8.1 | Governance Inbox And Mobile Quick Approve | 8.2 | W8 | W8 |
| 8.2 | Multi-Tenant White-Label / Ministry-Branded Subdomain Mode | 11.5 | W8 | W11 |
| 8.3 | External Auditor Portal SKU | 11.6 | W8 | W11 |
| 9.1 | iOS Liquid Glass Mobile System | 9.7 | W9 | W9 |
| 9.2 | Operator Certification Program | 11.1 | W9 | W11 |
| 9.3 | Forensic Mode And Coordinated Decision-Reversal Disclosure | 11.10 | W9 | W11 |
| 10.1 | Route Coverage And Sitemap Gate | 10.1 | W10 | W10 |
| 10.2 | A11y, Visual, Print, And Responsive Gate | 10.2 | W10 | W10 |
| 10.3 | Performance And Bundle Gate | 10.3 | W10 | W10 |
| 10.4 | Security, Privacy, And Compliance Gate | 10.4 | W10 | W10 |
| 10.5 | Launch Closeout | 10.5 | W10 | W10 |

### Wave 0 - Pure Inputs And Inventory

Purpose: gather the raw inputs, decisions, and contracts the rest of the program depends on. Every Wave 0 phase is strictly independent of every other Wave 0 phase. Phases that derive from a Wave 0 output live in Wave 1+.

Parallelism: all 12 phases run fully in parallel. Their final registry patches still serialize through the relevant queue (route, i18n, OpenAPI, design-token, etc.).

Gate to Wave 1: every Wave 0 phase has produced its dated decision note, registry, fixture, or inventory artifact. No Wave 1 phase starts on a Wave 0 input that is still under debate.

#### Phase 0.1 - Zip Adoption Ledger

Primary fence: brand-as-product.

Scope:

- Create `docs/reference/frontend/atlas-zip-6-adoption.md`.
- Map every zip file to one outcome: production source, design fixture,
  Storybook reference, archived prototype, or rejected with reason.
- Compare `assets/**` from zip to `apps/runtime-dashboard/public/atlas/**`.
- Record that `landing/index.html`, `landing/auth.html`, and
  `landing/docs.html` are prototypes to rebuild, not production files.

Acceptance:

- Every zip path has an owner and adoption status.
- Asset drift is measured with file hashes or visual glyph snapshot evidence.
- No old `apps/runtime-dashboard/**` path becomes canonical again.
- A rename/topology PR explicitly confirms `apps/runtime-dashboard/**` as the
  canonical app path, or records a reverse decision, before Phase 1.7 route
  work starts.

Verification:

- `unzip -l "/Users/deniskopylov/Downloads/PolicyOS Atlas Design System-6.zip"`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run test:glyph-vocabulary`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run design:atlas-v4`

#### Phase 0.2 - Public Topology Decision

Primary fence: platform/cross-cutting.

Scope:

- Decide Option A single app or Option B separate public app.
- Measure current lazy route bundle behavior for `/welcome` and
  `/public/decisions/:signedId`.
- Set public budgets:
  - homepage JS initial budget;
  - total CSS budget;
  - image/font budget;
  - Lighthouse 100/100/100/100 target;
  - accessibility and SEO thresholds.
- Default budget target: public homepage initial JavaScript is under 100 KB
  compressed unless Wave 0 records a dated exception with owner and measured
  user benefit.
- If Option B is required, add a short ADR before any code move.
- Treat the budget as provisional until Phase 1.4 records the sandbox engine
  choice; the final public homepage/sandbox budget must include that decision.

Acceptance:

- A dated decision note exists and links to bundle evidence.
- Public route budget is enforceable by `check:bundle` or a new public budget
  script.
- Implementation branches know where routes live before Wave 1 starts (derived-decisions tier).

Verification:

- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run build`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run check:bundle`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run lighthouse:ci`

#### Phase 0.3 - Public Content Model And Route Manifest

Primary fence: public marketing.

Scope:

- Define typed content models for:
  - persona/use-case pages;
  - case studies;
  - methodology/science longreads;
  - blog/insights;
  - resources/PDF previews;
  - webinars/events;
  - press/media kit;
  - about, mission, and team pages;
  - jobs;
  - job application forms and attachment policy;
  - partners/resellers;
  - contact/book-a-demo forms with scheduling and qualification questions;
  - glossary terms with glyph mapping;
  - legal/trust/procurement pages.
- Define route IDs, canonical slugs, SEO metadata, breadcrumb shape,
  social-preview metadata, structured data type, robots policy, print
  availability, localization status, and owner.
- Create a public sitemap matrix with launch priority.

Acceptance:

- Content model supports en/uk/ru and formal Ukrainian register.
- Every user-requested public page category has a route row.
- Routes can be created in parallel without inventing slug conventions.
- Public forms declare data retention, spam/abuse handling, attachment rules,
  and downstream system ownership before UI implementation.
- SEO metadata covers canonical URL, Open Graph/Twitter/LinkedIn image,
  schema.org type where appropriate, and sitemap/robots inclusion.

Verification:

- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run typecheck`
- content model unit tests for required fields and unique slugs.

#### Phase 0.4 - API/Fixture Contract Inventory

Primary fence: API/contracts.

Scope:

- Inventory backend/API needs for auth, billing, settings, support, quote
  builder, usage metering, status, changelog, roadmap, sandbox, public decision
  record, governance inbox, Evidence Fabric source detail, demo scheduling,
  contact intake, job applications, partner inquiries, roadmap votes, and
  newsletter/briefing signup.
- Classify each as:
  - existing runtime API;
  - static fixture acceptable for public launch;
  - mocked contract first;
  - backend required before UI can be honest.
- Add columns for destination system, destination owner, health-check fixture,
  and destination status where the UI flow submits public or customer data.
- Add MSW/fixture naming conventions for scenario presets and public demos.

Acceptance:

- No UI phase depends on an unnamed backend contract.
- Public demo and sandbox distinguish simulated fixture data from live
  telemetry.
- Governance/billing/auth flows mark which actions require real backend before
  production release.

Verification:

- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run contracts:verify`
- generated API client diff is empty unless a schema branch owns it.

#### Phase 0.5 - Legal, Compliance, And Claim Evidence Map

Primary fence: trust/legal/procurement.

Scope:

- Create a public-claim evidence map linking each trust/procurement/legal claim
  to internal docs, compliance evidence, runbook, policy, or legal owner.
- Classify claims as:
  - publish now;
  - publish as roadmap/non-certified posture;
  - gated by audit/legal review;
  - do not claim.
- Include SOC 2, ISO 27001, GDPR, data residency UA/EU, subprocessors, DPA,
  AUP, SLA, pen-test summary, VPAT, WCAG 2.2 AA, sovereign/on-prem, NIS2,
  EU AI Act, EUDI Wallet readiness, Diia SSO, Trembita/SEV DEIR references.
- Include e-invoicing posture:
  - UBL/PEPPOL for EU B2G;
  - Prozorro/source formats for UA procurement where applicable.
- Include e-signature/e-seal posture for UA and EU.
- Include FOI/right of access to public information posture, including UA Law
  No. 2939-VI.
- Include EU AI Act conformity assessment readiness for potentially high-risk
  systems, not only Article 13/14 transparency copy.
- Define public-claim exception authority:
  - security lead for security evidence exceptions;
  - legal lead for legal/compliance exceptions;
  - product lead for product availability exceptions;
  - joint dated sign-off for any P0 launch-blocking exception.

Acceptance:

- Public trust center has no unsupported certification language.
- Procurement pages can say "ready", "supported", "planned", or "deployment
  option" consistently.
- Legal pages have owners before Wave 2-3 trust/legal/procurement route work begins.

Verification:

- manual legal/security review checklist;
- links to `docs/compliance/**` and `docs/reference/security-compliance.md`
  resolve.

#### Phase 0.6 - Cross-Cutting State Inventory

Primary fence: platform/cross-cutting.

Scope:

- Build a required state matrix for every route family:
  - loading;
  - empty;
  - 401 unauthenticated;
  - 403 not authorized;
  - 403 not licensed;
  - 404;
  - 500;
  - region blocked;
  - browser unsupported;
  - maintenance;
  - offline;
  - degraded;
  - license expiring;
  - read-only/frozen;
  - print mode.
- Define reusable editorial empty-state and error-state components with glyph
  mapping.

Acceptance:

- Every route phase in Waves 2-9 can cite the state matrix.
- Error copy distinguishes "not licensed" from "not authorized".
- Maintenance and offline states have public and app variants.

Verification:

- state matrix test fixture validates every route family row.

#### Phase 0.7 - Backend Contract Lock

Primary fence: API/contracts.

Scope:

- Create a backend contract lock registry for every UI flow in Waves 4-8:
  - auth recovery, verification, MFA, SSO, magic link, invites, tenant picker,
    onboarding, step-up, session/risk/logout/organization exit;
  - billing, invoices, receipts, usage, quotes, procurement orders, coupons,
    dunning, trials, cancellation;
  - settings, SSO config, SCIM, audit log, API keys, PATs, webhooks,
    integrations, residency, retention, governance policy;
  - support tickets, DSAR, FOI, incident detail;
  - public decision records, governance inbox, quick approve, source detail,
    civic data, transparency snippets.
- For each row, record:
  - service owner;
  - OpenAPI path/schema if accepted;
  - signed stub contract if backend is not ready;
  - status: `ready`, `stub-locked`, or `blocked`;
  - fixture owner;
  - planned replacement wave.

Acceptance:

- No Wave 2+ implementation phase starts implementation without a registry row.
- `stub-locked` rows include request/response shape, error states, authz
  requirements, rate limits, audit events, and replacement owner.
- `blocked` rows are visible in the dashboard and cannot be hidden behind UI
  fixtures.

Verification:

- contract-lock registry uniqueness check;
- OpenAPI/stub schema validation;
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run contracts:verify`.

#### Phase 0.8 - Content Capacity And Register Ownership

Primary fence: public marketing.

Scope:

- Assign named role owners:
  - technical writer;
  - register editor for formal Ukrainian;
  - register editor for formal Russian;
  - methodology editor;
  - design-content owner.
- Extend the public content type catalog with ownership per type:
  - persona page;
  - case study;
  - methodology longread;
  - pricing/procurement;
  - legal/trust;
  - docs/support;
  - blog/resource/webinar/press;
  - careers/partner/contact/demo.
- Record register tags:
  - `formal-uk`;
  - `formal-ru`;
  - `formal-en` for regulated fallback copy;
  - `neutral-en`.

Acceptance:

- No localized route is registered until its content type has a register owner.
- Content ownership is about capacity and review responsibility, not a promise
  to produce a specific volume of pages in one wave.
- Pricing, legal, procurement, trust, support, and billing copy all require
  register tags before launch.

Verification:

- content owner registry check;
- register-tag completeness check;
- i18n fixture smoke for en/uk/ru.

#### Phase 0.9 - Analytics, Experiments, And Attribution Contract

Primary fence: QA/performance + public marketing.

Fence note: this is the only planned dual-fence Wave 0 contract because event
taxonomy is both measurement infrastructure and conversion content. Execution
branches still split by single fence; final taxonomy merges through the
analytics/experiments queue.

Scope:

- Define event taxonomy for public and client conversion events:
  - `page_view`;
  - `persona_path_select`;
  - `demo_book_started`;
  - `demo_book_completed`;
  - `sandbox_run_started`;
  - `sandbox_run_completed`;
  - `calculator_export`;
  - `packet_download`;
  - `pricing_view`;
  - `quote_started`;
  - `quote_exported`;
  - `doc_helpful`;
  - `ticket_submitted`;
  - `dsar_submitted`;
  - `foi_submitted`;
  - `roadmap_vote_submitted`;
  - `newsletter_signup_completed`.
- Define attribution policy:
  - UTM;
  - referrer;
  - last-touch;
  - lead-stage conversion;
  - tenant-safe handoff.
- Decide A/B infrastructure:
  - provider;
  - own feature flag;
  - or no A/B until a later wave.
- Require consent-aware bucketing and analytics suppression.

Acceptance:

- No public form or CTA launches without event mapping and declared
  destination.
- Events declare payload fields, PII policy, consent category, and retention.
- Experiment assignment is stable, consent-aware, and reversible.

Verification:

- event taxonomy lint;
- consent-gated event tests;
- attribution fixture tests.

#### Phase 0.10 - Continuous Gates Ratchet

Primary fence: QA/performance.

Scope:

- Turn the following checks into ratchets from Wave 0 onward:
  - `audit:ci`;
  - secret scan;
  - CSP/SRI;
  - evidence-map link check;
  - route-ID uniqueness;
  - content-registry uniqueness;
  - register-tag completeness;
  - a11y baseline;
  - public bundle budget;
  - public HTML license/PII leak scan;
  - destination health fixtures;
  - backend contract lock status.
- Define report-only windows and fail-closed thresholds.

Acceptance:

- Later waves may raise thresholds but may not lower them without the severity
  exception authority table.
- Threshold lowering requires the same joint exception authority as P0
  launch-blocking exceptions.
- Wave 10 is the final tightening and closeout, not the first time these gates
  run.
- P0 findings in auth, billing, legal, procurement, public forms, or public
  decision routes block launch unless a dated joint exception exists.

Verification:

- ratchet config check;
- baseline report committed or linked;
- CI command map updated.

#### Phase 0.11 - Jurisdictional Scope

Primary fence: trust/legal/procurement.

Scope:

- Declare jurisdictions in scope:
  - UA;
  - EU.
- Declare jurisdictions out of scope unless legal review changes the decision:
  - RF/152-FZ and any market requiring unsupported data-localization,
    sanctions, export-control, or procurement posture.
- For each in-scope jurisdiction record:
  - data-protection law;
  - e-invoicing requirements, including UBL/PEPPOL for EU B2G;
  - e-signature/e-seal equivalents;
  - FOI/public-information access law, including UA Law No. 2939-VI;
  - public procurement/tender format requirements;
  - EU AI Act posture and high-risk/conformity assessment notes.
- Define exception authority per claim class:
  - security lead for security posture;
  - legal lead for legal/compliance claims;
  - product lead for product availability claims;
  - joint sign-off for P0 launch-blocking exceptions.

Acceptance:

- Every legal, trust, procurement, pricing, quote, invoice, DSAR, FOI, and
  AI Act page declares jurisdiction tags.
- Out-of-scope jurisdictions cannot be implied by copy, lead routing, or
  pricing selectors.
- Jurisdiction tags are available to route, content, and public-claim checks.

Verification:

- jurisdiction registry check;
- public-claim evidence map cross-check;
- legal review.

#### Phase 0.12 - Lead Routing And CRM Destination

Primary fence: API/contracts.

Scope:

- For each public form, declare destination system and health-check fixture:
  - demo booking;
  - contact;
  - partner/reseller;
  - career application;
  - DSAR;
  - FOI;
  - newsletter/weekly briefing;
  - roadmap vote;
  - quote/procurement inquiry;
  - support ticket.
- Record destination owner, retry policy, failure UX, privacy/retention rule,
  attachment policy, and operational alert.

Acceptance:

- No public form is published without a green destination health check.
- Phase 0.4 API/fixture inventory includes a `destination system` column.
- Intake failures are visible to ops; leads cannot silently accumulate in an
  unmonitored inbox.

Verification:

- destination health fixture tests;
- form-to-destination mapping lint;
- ops alert review.

### Wave 1 - Pure-Foundations Tier

Purpose: lock the derived decisions and ship the foundations that touch the largest number of downstream phases. Every Wave 1 phase depends only on Wave 0 outputs, never on another Wave 1 phase.

Parallelism: all 17 phases run in parallel. They span brand/design tokens, multi-domain topology, sandbox engine, content backend, public shell, content registry, primitives, cookie/consent, auth state machine, legal route family, transparency report scaffold, sovereign cloud posture, status fixtures, docs API quickstarts, global states, and OSS strategy.

Gate to Wave 2: design tokens are merged, route shell exists, content registry compiles, auth state names are typed, and the legal/transparency scaffolds are evidence-mapped.

#### Phase 1.1 - v7 Advanced Surface Register Cross-Reference

Primary fence: domain product + brand-as-product.

Dependencies: Phase 0.1 (zip adoption ledger), DESIGN_BEST_IN_CLASS_PLAN.md
Tracks A–G.

Scope:

- Populate the v7 Advanced Surface Register (see Verified Baseline section)
  with each A1–E5 surface ID pointing at its DESIGN plan section and its
  cross-surface(s) inside this plan.
- For each row record:
  - surface ID and label;
  - DESIGN plan section;
  - status in DESIGN plan (do not duplicate — link only);
  - this-plan cross-surface(s) (public/print/embed/transparency);
  - shared fixture/contract owner;
  - cross-link drift owner.
- Add a drift check that fails CI if a v7 surface gains a public/print/embed
  cross-surface without a register row.

Acceptance:

- Every A1–E5 surface has at most one register row.
- DESIGN plan tracking authority is preserved; no duplicate status fields land
  here.
- A cross-surface added to this plan without a register row is detected by CI.

Verification:

- register lint;
- DESIGN plan link check;
- visual confirmation that every v7 JSX file is either registered or rejected.

#### Phase 1.2 - v7 Design-Token Drift

Primary fence: brand-as-product.

Dependencies: Phase 0.1.

Scope:

- Diff v7 `colors_and_type.css` against current production tokens in
  `apps/runtime-dashboard/src/styles*` and `docs/brand/**`.
- Identify additions and changes:
  - new CI tokens (`--color-ci-50/80/95`);
  - bounds-fill / bounds-stroke;
  - confidence levels (high/medium/low);
  - waterfall (positive/negative/total);
  - rail tokens (`--rail-active-bg`, `--rail-hover-bg`, `--rail-link`);
  - panel-strong / surface / shell-glass-base;
  - page-gradient stops;
  - soft-fill (teal-soft / ember-soft / gold-soft);
  - rim-light (`--rim-light`);
  - semantic typography classes (`.t-display`, `.t-h1..h4`, `.t-body`,
    `.t-small`, `.t-eyebrow`, `.t-mono`, `.t-metric`, `.t-metric-md`,
    `.t-prose`, `.t-citation`);
  - density mode parity (×1.0 / ×0.75 / ×0.5) with existing production density
    layer;
  - Janus medallion role tokens (decision-stamp dimensions, score ring).
- Decide one of: adopt, adapt, reject. Record why per token.
- Plan a single design-token patch through the design-token queue.
- Update `docs/brand/ATLAS_DESIGN_SYSTEM.md` and `docs/brand/ATLAS_V4_ADOPTION.md`
  with the v7 deltas.

Acceptance:

- The v7 token diff is recorded.
- Adopted tokens have a single merge patch and Storybook coverage.
- Density modes do not regress.
- High-contrast and forced-colors behavior is preserved.

Verification:

- design-token lint;
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run design:atlas-v4`;
- visual snapshots for v7-affected primitives.

#### Phase 1.3 - Atlas Public Page Primitives

Primary fence: brand-as-product.

Dependencies: Phase 0.1.

Scope:

- Build public page primitives:
  - `PublicHero`;
  - `PersonaPathSelector`;
  - `GlyphTermLink`;
  - `TrustEvidenceLink`;
  - `ProcurementPdfButton`;
  - `EditorialLongread`;
  - `ResourcePreviewCard`;
  - `CaseStudyCard`;
  - `PublicMetricCounter`;
  - `PublicStatusSnippet`.
- Convert selected `preview/*.html` examples into Storybook stories.

Acceptance:

- Primitives use production tokens and existing glyph vocabulary.
- No raw semantic domain icons from third-party libraries.
- Reduced-motion and forced-colors behavior is covered.

Verification:

- Storybook stories render;
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run design:polish`;
- visual snapshots for public primitives.

#### Phase 1.4 - Sandbox Engine Choice

Primary fence: interactive public demo.

Dependencies: Phase 0.2 draft topology and budget assumptions.

Scope:

- Decide public sandbox engine strategy before Wave 1:
  - precomputed lookup fixtures;
  - lightweight WASM mini-engine;
  - server-rendered sandbox runs;
  - hybrid staged approach.
- Measure effect on:
  - homepage and sandbox bundle budget;
  - latency;
  - offline/degraded behavior;
  - explainability;
  - ability to re-run case studies;
  - data/privacy risk.
- Record the decision next to the public topology decision.

Acceptance:

- A dated note records chosen engine and rejected alternatives.
- Bundle/performance evidence exists for the selected option.
- Explainability story is documented: regulator and academia users can see
  whether the sandbox shows mock, fixture, simulated, or real runtime behavior
  and where that disclosure appears in the UI.
- Phase 2.8 (public sandbox) inherit this decision instead of choosing locally.

Verification:

- sandbox engine decision note;
- bundle/perf evidence;
- fixture or prototype smoke test for chosen path.

#### Phase 1.5 - Multi-Domain Topology

Primary fence: platform/cross-cutting + trust/legal/procurement.

Dependencies: Phase 0.2 (public app topology).

Scope:

- Decide canonical domains:
  - product / app: `atlas.policyos.dev` (or equivalent);
  - trust center: `trust.policyos.eu`;
  - status page: `status.policyos.eu`;
  - docs: shared with product domain unless evidence justifies a split into
    `docs.policyos.dev` or `handbook.policyos.dev`;
  - landing/marketing: shared with product domain by default.
- Record per-domain:
  - CSP/SRI policy;
  - per-domain sitemap and robots policy;
  - canonical URL and OG metadata;
  - CDN/origin and certificate plan;
  - ATOM/RSS feed plan (changelog, decision record, blog where appropriate);
  - localized canonical strategy for en/uk/ru;
  - analytics and consent boundary (shared identity vs per-domain consent);
  - cross-domain redirect rules and link-preview behavior.
- Record multi-tenant white-label inheritance rules so Phase 8.3 can attach
  ministry-branded subdomains without re-opening this decision.
- Set deployment singleton: any change to domain map is a C5 merge window.

Acceptance:

- A dated decision note exists for each domain and its purpose.
- CSP/SRI, sitemap, robots, canonical, and OG rules are written down per
  domain.
- White-label inheritance is explicit, not implied.
- Trust center, status page, and product cross-link without leaking cookies,
  tokens, or tenant context.

Verification:

- domain decision note;
- CSP/SRI lint per domain;
- sitemap and canonical URL test fixtures.

#### Phase 1.6 - Content Backend Strategy

Primary fence: public marketing + docs/support.

Dependencies: Phase 0.3, 0.8.

Scope:

- Decide content backend per content type:
  - markdown-in-repo with editorial PR flow;
  - headless CMS (Sanity, Strapi, Contentful, Directus, or equivalent);
  - hybrid (regulated copy in repo, marketing copy in CMS).
- Define:
  - editorial PR/review process and required approvers per content type;
  - translator workflow for en/uk/ru and formal-register tagging;
  - preview environment for unmerged content;
  - content publish gate (a11y, SEO, link, register-tag, legal-evidence);
  - rollback procedure;
  - retention/versioning policy for legal, trust, and decision-record copy.
- Record provider lock-in / portability rules and adapter boundary if a CMS is
  selected.

Acceptance:

- Each public content type in Phase 0.3 has a declared backend and editorial
  flow.
- Regulated copy (legal, trust, procurement, billing) cannot ship from
  unreviewed CMS drafts.
- Translators can preview formal-register copy before publish.

Verification:

- content backend decision note;
- editorial flow tests for repo-backed types;
- preview-environment smoke test for CMS-backed types.

#### Phase 1.7 - Public Shell And Navigation

Primary fence: public marketing.

Dependencies: Phase 0.2 and 0.3.

Scope:

- Extend current landing shell into a public route shell with:
  - header/navigation;
  - footer groups;
  - persona switch affordance;
  - locale switch;
  - dark-mode toggle if Wave 0 allows;
  - cookie consent entry point;
  - public Cmd-K entry point slot;
  - print-to-procurement button slot.
- Keep public shell isolated from authenticated `AppShell`.

Acceptance:

- `/welcome` still works.
- Public shell has no authenticated sidebar or runtime providers unless needed.
- Mobile nav is accessible and route-aware.
- Header/footer link to every Wave 2-3 route as disabled, hidden, or active
  according to launch state.

Verification:

- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run test:components`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run test:a11y:components`

#### Phase 1.8 - Content Registry And Localized Copy Pipeline

Primary fence: public marketing.

Dependencies: Phase 0.3 and 0.8.

Scope:

- Implement content registry modules for public pages.
- Add localized content loading for en/uk/ru.
- Add compile-time checks for:
  - unique slugs;
  - required SEO fields;
  - required print metadata;
  - required glyph term references;
  - required register tag for public pricing, legal, procurement, trust,
    support, docs, and billing-facing strings;
  - no unsupported locale rows;
  - glossary cross-reference integrity.
- Add fallback policy:
  - `formal-uk` is preferred for Ukrainian public regulated copy;
  - if `formal-uk` is missing, fallback to approved `formal-en`;
  - never fallback from Ukrainian regulated copy to Russian;
  - never fallback from formal regulated copy to informal/neutral copy without
    owner approval.

Acceptance:

- Adding a new case study, resource, job, or glossary term does not require
  editing route code.
- Ukrainian and Russian fallbacks are explicit, not accidental English bleed.
- Register tags (`formal-uk`, `formal-ru`, `formal-en`, `neutral-en`) are
  mandatory for all public pricing, legal, procurement, trust, support, and
  billing copy.
- Content failures block CI in report-only mode first, then fail-closed in
  Wave 10.

Verification:

- content registry unit tests;
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run typecheck`.

#### Phase 1.9 - Cookie, Privacy, Analytics, And Consent Foundation

Primary fence: trust/legal/procurement.

Dependencies: Phase 0.5, 0.9, and 0.11.

Scope:

- Add cookie banner and cookie preferences modal.
- Separate strictly necessary, analytics, marketing, and support categories.
- Gate analytics and live counters behind consent where required.
- Add privacy-copy hooks to forms.

Acceptance:

- Public pages do not emit non-essential analytics before consent.
- Cookie preferences are reachable from footer and banner.
- Consent state is persisted and resettable.

Verification:

- unit tests for consent categories;
- Playwright check that analytics hooks are not called before consent.

#### Phase 1.10 - Global Empty, Loading, Error, Offline, License States

Primary fence: platform/cross-cutting.

Dependencies: Phase 0.6.

Scope:

- Implement reusable states:
  - empty states for no runs, evidence, decisions, audit events, invoices,
    tickets, docs search, roadmap votes;
  - loading skeletons;
  - 401;
  - 403 not licensed;
  - 403 not authorized;
  - 404;
  - 500;
  - region blocked;
  - browser unsupported;
  - maintenance;
  - offline;
  - degraded;
  - license expiring;
  - freeze/read-only banners.
- Build public service pages for:
  - 404;
  - 500;
  - offline;
  - planned maintenance;
  - unsupported browser;
  - region blocked.
- Use editorial Atlas treatment with the blocker glyph (`⊘`) where the state
  represents a halt, denial, or unavailable route.

Acceptance:

- Major route families use shared state components.
- Copy is editorial, domain-specific, and glyph-aware.
- Unauthorized and unlicensed states are distinct.
- Public 404/500/offline pages are routeable, localized, printable where useful,
  and do not expose internal stack or tenant data.

Verification:

- component tests;
- route-state matrix tests;
- visual snapshots.

#### Phase 1.11 - Auth Flow State Machine

Primary fence: auth/onboarding.

Dependencies: Phase 0.4 and 0.7.

Scope:

- Define typed auth flow states for:
  - sign in;
  - sign up;
  - forgot password;
  - email sent;
  - reset password;
  - reset done;
  - email verification required;
  - verification confirmed;
  - verification expired;
  - MFA enrollment;
  - MFA challenge;
  - recovery codes;
  - SSO picker;
  - magic link;
  - invite acceptance;
  - tenant picker;
  - first-run onboarding;
  - session expired;
  - step-up auth;
  - account locked;
  - suspicious activity;
  - logout confirmation;
  - leave organization confirmation.

Acceptance:

- Flow state names are stable before UI routes land.
- Auth routes can render fixture-backed states without backend.
- Step-up auth has governance-action context.

Verification:

- state machine unit tests;
- route search-param parsing tests.

#### Phase 1.12 - Legal Route Family

Primary fence: trust/legal/procurement.

Dependencies: Phase 0.5, 0.11, legal/compliance queue.

Scope:

- Build legal pages:
  - ToS;
  - Privacy;
  - DPA;
  - AUP;
  - SLA;
  - Subprocessor list;
  - Cookie policy;
  - data residency;
  - FOI/public transparency note if approved.
- Add version/date metadata and previous-version archive hooks.

Acceptance:

- Footer links resolve.
- Each legal page has owner, effective date, version, jurisdiction notes.
- Cookie preferences link back to cookie policy.

Verification:

- link check;
- legal owner approval.

#### Phase 1.13 - Annual Transparency Report Scaffold

Primary fence: trust/legal/procurement + post-launch product platform.

Dependencies: Phase 0.5, Phase 0.11.

Scope:

- Scaffold the annual transparency report template:
  - decisions issued, by category and jurisdiction;
  - governance escalations and outcomes;
  - challenge/dispute statistics;
  - reproducibility ratio;
  - data residency posture;
  - subprocessor changes;
  - security incident summary (linked to status RCA library);
  - AI Act / NIS2 / GDPR posture deltas;
  - methodology changes and ADR list;
  - bibliography updates.
- Record the publication cadence (annual default), publication channel, and
  signing rules.
- Decide whether report assets are also published as ATOM/RSS items.
- Record the reproducibility manifest format so academics can replicate
  selected analyses.

Acceptance:

- Report scaffold has owner, schedule, and reproducibility manifest format
  before Phase 4.8 implementation.
- Report does not duplicate factual sources — it links to docs, ADRs,
  decision records.
- Sensitive customer detail is anonymized or excluded.

Verification:

- scaffold rendering test;
- evidence map link check;
- legal/security review.

#### Phase 1.14 - Sovereign Cloud Variants And Air-Gapped Delivery Kit

Primary fence: trust/legal/procurement + platform/cross-cutting.

Dependencies: Phase 0.5, Phase 0.11.

Scope:

- Record sovereign deployment options as ready / planned / blocked /
  out-of-scope:
  - AWS GovCloud (US);
  - OVHcloud Strasbourg / Roubaix (EU);
  - Hetzner Frankfurt (EU);
  - UA Cloud Strategy hosts (where approved);
  - on-prem / private cloud;
  - air-gapped delivery kit (ISO/USB, offline ADR pack, offline docs).
- Map each option to data-residency, certifications, and integration
  evidence.
- Record what the trust center publishes vs what is only available under NDA.

Acceptance:

- Procurement and persona pages can refer to sovereign options without
  inventing certification language.
- Air-gapped delivery posture has a runbook and an offline content manifest
  before any customer commitment.
- Sovereign options inherit the same trust posture and Janus seal as the
  managed deployment.

Verification:

- evidence map link check;
- trust center claim review;
- delivery kit content manifest test.

#### Phase 1.15 - Status, Changelog, Release Notes, And Roadmap

Primary fence: trust/status.

Dependencies: Phase 0.4, 0.9, 0.10, 0.12.

Scope:

- Build public status page with uptime summary and incident history.
- Build incident detail/RCA page and public RCA library.
- Build public changelog/release notes stream.
- Build public roadmap with governance/evidence glyph tags and optional voting
  prepared behind a feature flag.
- Add status snippet to docs and public shell.

Acceptance:

- Status can run from static fixtures before live incident backend exists.
- Incidents have severity, component, timeline, RCA, customer impact, status.
- Changelog links to release notes and docs.
- Roadmap items link to public ADRs where appropriate.
- Roadmap voting, if enabled, has moderation, rate-limit, abuse/spam handling,
  duplicate vote policy, and customer attribution rules.
- Public roadmap voting has a slip-communications policy before voting is
  enabled:
  - delay/cancellation template;
  - publishing channel;
  - owner;
  - customer notification threshold;
  - link from roadmap item to explanation.
- RCA pages expose timeline, contributing factors, prevention work, and
  follow-up links without leaking customer-sensitive data.

Verification:

- fixture schema tests;
- route tests for incident detail and changelog item;
- status snippet visual test.

#### Phase 1.16 - API Reference, SDK/CLI Quickstarts, Tutorials

Primary fence: docs/support.

Dependencies: Phase 0.4.

Scope:

- Build OpenAPI explorer for `schemas/runtime_api_v1.openapi.json`.
- Build SDK/CLI quickstart by language/tool.
- Build tutorial/walkthrough layout.
- Build examples/cookbook index.
- Build migration guide with version selector.

Acceptance:

- API explorer uses generated schema, not hand-written endpoint lists.
- Quickstarts have copy buttons and tested snippets where possible.
- Version selector is visible on versioned docs pages.

Verification:

- OpenAPI schema load test;
- snippet smoke tests;
- route tests.

#### Phase 1.17 - Open Source Strategy And Contribution Path

Primary fence: post-launch product platform + platform/cross-cutting +
trust/legal/procurement.

Dependencies: Phase 0.5, Phase 0.11.

Scope:

- Decide which parts of PolicyOS are open source vs proprietary:
  - core scientist/runtime kernels;
  - design system tokens, glyph alphabet, Storybook;
  - SDKs and CLI;
  - example scenarios and fixtures;
  - reference architecture and runbooks.
- Decide license per part (Apache 2.0, MPL 2.0, AGPL 3.0, BSL, proprietary).
- Decide CLA model (DCO sign-off vs CLA agreement).
- Decide contribution path (forking, RFC, issue template, security
  disclosure).
- Wire a license-header drift gate.
- Record relationship between OSS scope and proprietary all-rights-reserved
  license already in repo.

Acceptance:

- OSS scope and license boundary are recorded in `LICENSE.md` updates and a
  dated ADR.
- Contribution path has owner and response SLA.
- License-header drift fails CI for files within OSS scope.

Verification:

- license-header drift test;
- ADR link check;
- legal review.

### Wave 2 - Production Primitives And Shells

Purpose: build the production primitives, shells, and ground-state pages that compose into public surfaces in later waves. Every Wave 2 phase depends only on Wave 0-1 outputs.

Parallelism: all 20 phases run in parallel — Janus/citation/density primitives, Email/OG/RUM, methodology, sandbox, calculator, careers/contact, trust center, auth flows (recovery/MFA/SSO), docs IA, help center, content engine, API longread, Evidence Fabric source detail, animated glyphs.

Gate to Wave 3: primitives and shells render in Storybook; trust center, sandbox, methodology, and docs IA can host real content; auth flows render fixture-backed states; status fixtures (from Wave 1) feed into the trust strip.

#### Phase 2.1 - iOS / Mobile System Decision

Primary fence: brand-as-product + interactive demo.

Dependencies: Phase 0.2, 1.4.

Scope:

- Decide mobile system scope:
  - PWA + responsive product (default);
  - dedicated mobile reading mode for landing, docs, dashboard;
  - native iOS shell using the v7 iOS Liquid Glass frame as design canvas;
  - native Android equivalent.
- For each mobile-only surface, record:
  - target user (regulator, citizen, on-the-go operator);
  - offline behavior;
  - notification posture;
  - performance budget;
  - distribution channel (App Store, EU enterprise distribution, internal).
- Record the iOS frame `ios-frame.jsx` as a design-canvas component only,
  unless a native commitment is recorded.

Acceptance:

- A dated decision note records mobile scope.
- Phase 4.2 public mobile preview, Phase 8.1 mobile quick approve, and Phase 9.1
  mobile system inherit this decision instead of redeciding locally.
- No native iOS code lands without the decision and a security/legal review.

Verification:

- mobile decision note;
- mobile bundle budget;
- iOS frame Storybook coverage if used as design canvas.

#### Phase 2.2 - Janus Medallion And Provenance Stamp Primitives

Primary fence: brand-as-product.

Dependencies: Phase 1.2, Phase 1.3.

Scope:

- Wire Janus medallion (`logo-janus.svg`) as a reusable primitive:
  - `JanusStamp` — decision stamp / score ring used inside Public Decision
    Record, Decision Packet PDF, Trust Center seal block, governance inbox
    signed-by avatar;
  - composition rules for size (16, 24, 32, 48, 64 px and 1.5×/2× print
    bleed);
  - state variants for signed / draft / expired / revoked;
  - role tokens from Phase 1.2.
- Wire `ProvenanceCertificateBlock` primitive for the ed25519 multi-party seal
  and SHA-256 hash tree.
- Document when Janus appears vs the standard Atlas mark.

Acceptance:

- Janus medallion is used consistently across Public Decision Record (Phase 4.5), Decision Packet PDF (Phase 3.3/8.1), Trust Center seal (Phase 2.11),
  and governance inbox avatar (Phase 8.1).
- The provenance certificate block is reusable in auditor portal (Phase 5.7)
  and EU AI Office feed (Phase 4.9) without duplication.
- Forced-colors, high-contrast, and print render the medallion legibly.

Verification:

- Storybook visual snapshots for each state and size;
- print snapshot for decision packet;
- a11y check for forced-colors variant.

#### Phase 2.3 - Citation Typography, Density Modes, And Reasoning Primitives

Primary fence: brand-as-product.

Dependencies: Phase 1.2, Phase 1.8.

Scope:

- Add `CitationBlock` primitive using Instrument Serif italic for blockquotes,
  decision-packet pull-quotes, methodology longread citations, and case-study
  quotes; honor the `.t-citation` semantic class from v7.
- Add `DensityProvider`-aware primitives for the three density modes
  (comfortable / compact / condensed) so public primitives respect user
  density without per-surface CSS.
- Add reasoning primitives:
  - `ArgumentMapBlock` (Toulmin) — claim, grounds, warrant, backing,
    rebuttal, qualifier;
  - `ReasoningChain` — step-by-step inference with confidence delta per step;
  - `UncertaintyDecomposition` — epistemic vs aleatoric stacked bar;
  - `CounterfactualFlip` — single-feature flip preview;
  - `ForestPlot` — weight-of-evidence visualization for synthesis;
  - `BitemporalHandle` — `valid_at` / `transaction_at` chip used across
    changelog, decision record, case study, and methodology pages.
- Add confidence-band rendering using CI tokens (50/80/95) and bounds-fill /
  bounds-stroke from Phase 1.2.

Acceptance:

- These primitives are used on the public decision record (Phase 4.5) and
  methodology longread (Phase 2.7) before Phase 5.3 (public reasoning surfaces) begins.
- Reduced-motion, forced-colors, and density modes are supported.
- Each primitive has a story showing it inside the print stylesheet.
- Bitemporal handles surface a hover/inspection state showing both `valid_at`
  and `transaction_at`.

Verification:

- Storybook stories for each primitive;
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run design:polish`;
- visual snapshots for desktop, mobile, dark, forced-colors, and print.

#### Phase 2.4 - Atlas Email Foundation

Primary fence: brand-as-product.

Dependencies: Phase 0.8, Phase 0.9, Phase 1.8.

Scope:

- Build email-safe Atlas transactional foundations:
  - verify email;
  - reset password;
  - invite;
  - MFA recovery;
  - ticket update;
  - governance request.
- Define email-safe token subset:
  - fonts/fallbacks;
  - colors;
  - button styles;
  - glyph fallback behavior;
  - dark-mode limitations;
  - legal footer slots.
- Add locale/register rules for en/uk/ru.

Acceptance:

- Auth, support, and governance flows in later waves do not ship with default
  provider templates.
- Email templates are source-controlled, versioned, and snapshot-tested.
- Templates declare event taxonomy mapping and destination/provider owner.

Verification:

- email HTML snapshot tests;
- register-tag check for email copy;
- accessibility/readability smoke for major clients where tooling exists.

#### Phase 2.5 - OG/Social Preview Generator

Primary fence: brand-as-product.

Dependencies: Phase 0.3, Phase 1.8, Phase 1.3.

Scope:

- Build default OG/Twitter/LinkedIn preview generator from content metadata.
- Support content types:
  - homepage;
  - persona pages;
  - case studies;
  - methodology pages;
  - resources;
  - changelog/roadmap items;
  - public decision records;
  - docs articles.
- Generate, not handcode, title, subtitle, glyph, locale, image alt, and
  freshness metadata.

Acceptance:

- Public pages can ship with generated social metadata from the content
  registry before custom art exists.
- Missing OG metadata fails content checks.
- Social previews use Atlas glyphs/tokens and avoid unsupported claims.

Verification:

- OG render tests;
- content metadata completeness tests;
- visual snapshots for default templates.

#### Phase 2.6 - Public RUM, Error Reporting, And Synthetic Checks

Primary fence: QA/performance.

Dependencies: Phase 0.9, 0.10, and 1.9.

Scope:

- Add consent-aware RUM for Core Web Vitals.
- Add JS error reporting without PII.
- Add synthetic uptime checks for:
  - homepage;
  - sandbox;
  - public decision record;
  - docs landing/article.
- Add public Core Web Vitals/status dashboard surface or feed that can be
  linked from trust/status pages.

Acceptance:

- RUM and error reporting honor cookie/consent categories.
- JS error payloads are scrubbed for PII, tokens, tenant IDs, and form values.
- Public dashboard data retention is declared and bounded.
- Synthetic checks are operational before Wave 3 public route launch.
- Trust/status can link to real public web vitals evidence, not only lab
  Lighthouse runs.

Verification:

- RUM consent tests;
- PII scrubber tests;
- synthetic-check fixture tests;
- public telemetry dashboard smoke.

#### Phase 2.7 - Methodology And Science Surface

Primary fence: public marketing.

Dependencies: Phase 1.8, docs evidence map.

Scope:

- Create methodology/science landing and longread pages:
  - causal estimates;
  - identifiability strategies (back-door, front-door, IV, RDD, DiD) with the
    point/partial/set-identified taxonomy as a navigation lens;
  - E-value sensitivity for unmeasured confounding;
  - Manski / Robins bounds for partial identification;
  - transportability;
  - Toulmin argument structure for decision rationale (links to E1 Argument
    Map and E2 Reasoning Chain in DESIGN plan);
  - epistemic vs aleatoric uncertainty decomposition (links to E3
    Uncertainty Decomposer);
  - weight-of-evidence synthesis with a forest plot (links to E5 Evidence
    Synthesis);
  - bitemporal versioning (`valid_at` vs `transaction_at`);
  - JAX engine;
  - validation/backtesting;
  - literature/ADR bibliography.
- Use scroll charts and native glyphs where useful.
- Link to ADRs and reference docs, not unsupported claims.

Acceptance:

- Every method claim links to docs/ADR/source evidence.
- Methodology page has print/PDF mode for regulators.
- Glossary terms cross-link to glyph alphabet.

Verification:

- link check;
- print snapshot;
- content evidence map check.

#### Phase 2.8 - Public Sandbox And Playable Demo

Primary fence: interactive public demo.

Dependencies: Phase 0.4, 0.7, 1.4, Phase 1.3.

Scope:

- Build a lightweight public sandbox with:
  - simplified Composer;
  - 3-4 scenario presets;
  - run button;
  - deterministic simulated result distribution;
  - governance pass preview;
  - evidence bundle preview;
  - decision packet sample link.
- Keep it honest: label fixture/simulated data clearly.
- Implement the sandbox using the engine strategy selected in Phase 1.4.

Acceptance:

- No login required.
- Works on mobile and desktop.
- Re-run links from case studies load scenario state.
- Does not call protected runtime APIs and does not relay sandbox runs to
  production telemetry beyond aggregate counters.

Verification:

- Playwright happy path for each preset;
- a11y and reduced-motion tests;
- public route bundle check.

#### Phase 2.9 - ROI/TCO Calculator And Live Counters

Primary fence: interactive public demo.

Dependencies: Phase 0.4, 0.9, 0.12, Phase 1.9.

Scope:

- Build ROI/TCO calculator that computes immediately without email capture.
- Add optional PDF export for tender pack.
- Add live counters for scenarios run, evidence bundles, governance passes in
  last 24 hours with fixture/live source classification.

Acceptance:

- Calculator explains assumptions and lets users adjust them.
- PDF output is procurement-friendly.
- Live counters are disabled or fixture-labeled if telemetry source is absent.

Verification:

- calculator unit tests for formula stability;
- print/PDF snapshot;
- consent-gated analytics test.

#### Phase 2.10 - Service, Conversion, Careers, And Partner Routes

Primary fence: public marketing.

Dependencies: Phase 0.3, 0.4, 0.8, 0.9, 0.12, Phase 1.9.

Scope:

- Build About, Mission, and Team pages with:
  - mission statement;
  - team profiles;
  - advisor/customer council links where approved;
  - public credibility facts without unsupported claims.
- Build Careers index, job detail, and application form:
  - role metadata;
  - location/remote policy;
  - language requirements;
  - attachments;
  - consent and retention copy;
  - confirmation and duplicate-application state.
- Build Partners/Resellers pages for government integrators:
  - partner types;
  - reseller qualification;
  - implementation responsibilities;
  - contact form;
  - procurement/trust links.
- Build Contact and Book a demo routes:
  - scheduling slot picker or calendar handoff;
  - qualifying questions for persona, organization, country/region, use case,
    procurement path, data residency, and urgency;
  - support/sales/rfp routing;
  - confirmation, reschedule, and cancellation states.

Acceptance:

- Demo/contact forms do not require email before showing useful content.
- All public intake forms declare retention, consent, abuse handling, and owner.
- Scheduling can run from fixture slots before a live calendar integration.
- Career application attachments are size/type constrained and privacy-reviewed.
- Partner inquiries route to procurement/trust content when government
  integration is selected.

Verification:

- form validation tests for demo, contact, partner, and career application;
- Playwright journey for book-a-demo qualification;
- privacy/retention copy review;
- route metadata and sitemap tests.

#### Phase 2.11 - Trust Center

Primary fence: trust/legal/procurement.

Dependencies: Phase 0.5, 0.11, Phase 1.3.

Scope:

- Build Trust Center landing and detail pages:
  - SOC 2 posture;
  - ISO 27001 posture;
  - GDPR;
  - data residency UA/EU;
  - subprocessors;
  - DPA;
  - AUP;
  - SLA;
  - pen-test summary;
  - security architecture diagram;
  - VPAT;
  - WCAG 2.2 AA/a11y page;
  - security questionnaire downloads: VSAQ, CAIQ, SIG Lite;
  - sovereign/on-prem/air-gapped deployment.

Acceptance:

- Every public claim maps to evidence or is labeled as planned/posture.
- Downloads are versioned and dated.
- Trust Center is linked from homepage, footer, pricing, procurement, docs.

Verification:

- evidence map check;
- link/download check;
- security review.

#### Phase 2.12 - Recovery, Verification, Magic Link

Primary fence: auth/onboarding.

Dependencies: Phase 1.11.

Scope:

- Implement forgot password, email sent, reset password, done.
- Implement email verification required/confirmed/expired.
- Implement magic-link request and pending state.

Acceptance:

- All forms have validation, submit/loading/error/success states.
- Expired links provide resend and support routes.
- Copy avoids leaking whether an account exists.

Verification:

- component tests;
- a11y tests;
- security copy review.

#### Phase 2.13 - MFA And Recovery Codes

Primary fence: auth/onboarding.

Dependencies: Phase 1.11.

Scope:

- Implement TOTP enrollment.
- Implement WebAuthn/hardware key enrollment shell.
- Implement MFA challenge.
- Implement recovery-code display/download/confirm state.
- Implement lost-device support route handoff.

Acceptance:

- Recovery codes are displayed once and require confirmation.
- Hardware-key unsupported browser state is explicit.
- MFA challenge supports step-up auth contexts.

Verification:

- component tests for TOTP/recovery code flows;
- browser unsupported state test.

#### Phase 2.14 - SSO, Government Identity, Invites, Tenant Picker

Primary fence: auth/onboarding.

Dependencies: Phase 0.7 and Phase 1.11.

Scope:

- Implement SSO provider picker for SAML/OIDC.
- Include Microsoft Entra, Google Workspace, government SSO/Diia, EU eID/EUDI
  Wallet-ready messaging where approved.
- Implement invite acceptance:
  - new user;
  - existing user;
  - expired invite;
  - wrong account;
  - domain SSO required.
- Implement workspace/tenant picker for users with multiple organizations.

Acceptance:

- IdP options come from fixtures/API, not hardcoded only in JSX.
- Government identity items link to integration/trust pages.
- Tenant picker handles no-access, suspended, and region-blocked workspaces.

Verification:

- route tests;
- a11y keyboard selection tests;
- i18n coverage.

#### Phase 2.15 - Public Docs IA And Article View

Primary fence: docs/support.

Dependencies: Phase 1.8, docs nav queue.

Scope:

- Build public docs landing with topic cards.
- Build article reading view:
  - left sidebar;
  - content;
  - right TOC;
  - "Was this helpful?";
  - Edit on GitHub;
  - status snippet;
  - print/PDF mode.
- Map repository docs topics into public docs without duplicating factual
  source.

Acceptance:

- Article route can render a docs fixture from Markdown/MDX/source registry.
- Print view is regulator-friendly.
- Status snippet appears when an incident fixture is active.

Verification:

- route tests;
- print snapshot;
- link check.

#### Phase 2.16 - Help Center, Tickets, Incident Detail, DSAR, And FOI

Primary fence: docs/support.

Dependencies: Phase 0.4, 0.7, 0.11, 0.12, Phase 1.15.

Scope:

- Build help center/KB landing.
- Build KB article with breadcrumbs.
- Build submit ticket form.
- Build my tickets list and ticket detail:
  - messages;
  - status;
  - attachments;
  - incident link.
- Build status incident detail.
- Build DSAR/compliance request form.
- Build FOI/right of access to public information request flow separately from
  DSAR:
  - UA Law No. 2939-VI copy;
  - public-body/requester distinction;
  - response deadline metadata;
  - public-body request acknowledgment receipt with reference number;
  - attachments;
  - jurisdiction tags;
  - escalation/support handoff.

Acceptance:

- Ticket forms have attachment, privacy, and rate-limit states.
- DSAR form has identity verification and region/legal copy.
- FOI form is not modeled as GDPR DSAR; it has its own jurisdiction, deadline,
  identity, and routing rules.
- FOI submission produces an acknowledgment receipt with a public-body reference
  number when the destination contract supports it.
- Incident detail shares source schema with status page.

Verification:

- form validation tests;
- attachment state tests;
- privacy copy review.

#### Phase 2.17 - Editorial Content Engine And Community

Primary fence: public marketing.

Dependencies: Phase 1.8.

Scope:

- Build blog/insights index and article pages.
- Build resource library with PDF preview.
- Build webinars/events.
- Build press/media kit:
  - logos;
  - bios;
  - fact sheets;
  - chart usage license.
- Build "State of Policy Ops" annual report template.
- Build weekly briefing landing/signup.
- Build bibliography page.
- Build customer council, office hours/book principal scientist, research
  consortium/partners pages.
- Add community program rules for the research consortium:
  - member eligibility;
  - code of conduct;
  - moderation/anti-spam policy;
  - Slack/Discord or equivalent channel naming that keeps an academic tone;
  - public/private boundary for shared research materials.
- Customer council pages use real names, titles, affiliations, and portraits
  only with explicit approval; otherwise they fall back to anonymized advisory
  roles without fake specificity.

Acceptance:

- Content types share registry patterns.
- Articles/resources generate OG previews.
- Bibliography links claims to source docs/ADR/literature.
- Community signup and office-hours booking have privacy, moderation, and
  scheduling ownership.

Verification:

- content registry tests;
- OG preview tests;
- print snapshot for annual report.

#### Phase 2.18 - Atlas API Reference Longread

Primary fence: docs/support.

Dependencies: Phase 0.4, Phase 1.16.

Scope:

- Build an editorial Atlas API Reference longread that complements the
  OpenAPI explorer:
  - launch a policy run;
  - fetch decision packet;
  - walk provenance;
  - verify ed25519 webhook signatures;
  - re-run case study from sandbox;
  - retrieve transparency snippet;
  - subscribe to changelog and decision ATOM/RSS feeds.
- Reference v7 `landing/api.html` as a layout guide.
- Treat the longread as derived content: the schema source of truth remains
  `schemas/runtime_api_v1.openapi.json`.

Acceptance:

- Longread fails CI if the OpenAPI schema or example payloads drift.
- Verification snippets cover ed25519 in the supported SDK languages.
- The longread links into the OpenAPI explorer at the exact operation, not a
  generic top-level page.

Verification:

- schema drift test;
- snippet smoke tests;
- route tests.

#### Phase 2.19 - Evidence Fabric Source Detail And Lineage Map

Primary fence: domain product.

Dependencies: existing Evidence Fabric, Phase 0.4 and 0.7.

Scope:

- Build source detail page:
  - source profile;
  - freshness;
  - confidence tier;
  - contracts;
  - lineage;
  - claims;
  - conflicts;
  - retention/residency;
  - connected runs/decisions.
- Build lineage map board from existing lineage primitives and zip
  `LineageGravityMap.jsx` reference.

Acceptance:

- Source detail is reachable from Evidence Fabric and decision records.
- Lineage map supports dense and readable modes.
- Empty/no lineage states are editorial and useful.

Verification:

- route tests;
- graph visual snapshot;
- a11y keyboard navigation test.

#### Phase 2.20 - Animated Glyphs And Motion Language

Primary fence: brand-as-product.

Dependencies: Phase 1.3.

Scope:

- Add short 160-240ms identifying animation for each of the 10 radicals.
- Document when to use each animation:
  - ledger flip;
  - slide-in;
  - status reveal;
  - no animation.
- Add reduced-motion fallbacks.
- Add Storybook examples and motion checks.

Acceptance:

- Animations do not obscure meaning.
- Reduced-motion mode avoids movement.
- Motion docs include examples, not only token numbers.

Verification:

- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run design:motion`
- visual/storybook interaction tests.

### Wave 3 - Composed Public Surfaces

Purpose: compose the primitives into the most user-visible public surfaces. Every Wave 3 phase depends only on Wave 0-2 outputs.

Parallelism: all 11 phases run in parallel — homepage upgrade, persona pages, decision packet sample, procurement playbook, subdomain rollout, first-run onboarding, public search/Cmd-K, components gallery, identifiability methodology anchor, Atlas Codex, research consortium.

Gate to Wave 4: homepage and persona paths are live; decision packet sample renders; procurement playbook generates tender pack; onboarding wizard hands off to first scenario.

#### Phase 3.1 - Homepage Upgrade With Playable Demo Entry

Primary fence: public marketing.

Dependencies: Phase 0.10, Phase 1.7, 1.3, 2.5, and 2.6.

Scope:

- Replace the minimal `LandingPage` composition with the zip v6 marketing
  structure rebuilt in production:
  - product-forward hero;
  - live product demo entry;
  - workflows;
  - capabilities;
  - glyph alphabet;
  - "why Atlas" comparison;
  - pricing/procurement teaser;
  - CTA;
  - public trust/status strip.
- Add dark landing variant if token checks pass.

Acceptance:

- First viewport clearly signals PolicyOS/Atlas.
- Hero leaves hint of next section on mobile and desktop.
- No stock-like imagery; visual assets are product/demo/glyph/data oriented.
- Public homepage remains within the Wave 0 performance budget recorded in Phase 0.2.

Verification:

- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run test:visual`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run lighthouse:ci`
- bundle budget check.

#### Phase 3.2 - Persona Solutions And Use Cases

Primary fence: public marketing.

Dependencies: Phase 1.8 and 2.5.

Scope:

- Create pages for:
  - analyst;
  - ministry;
  - regulator;
  - NGO researcher;
  - academia;
  - procurement/CISO.
- Each page includes:
  - persona-specific pain;
  - workflows;
  - relevant case studies;
  - demo/sandbox entry;
  - trust/procurement proof points;
  - pricing/procurement CTA;
  - docs/resources CTA.

Acceptance:

- Persona paths are reachable from homepage and public Cmd-K.
- Copy is not generic SaaS; it uses PolicyOS domain vocabulary.
- Each page has en/uk/ru route metadata and print availability.

Verification:

- route tests for each persona slug;
- content registry uniqueness tests.

#### Phase 3.3 - Decision Packet Sample

Primary fence: interactive public demo.

Dependencies: existing `PublicDecisionViewerPage`, Phase 0.4, 0.7, and 2.5.

Scope:

- Productize a public anonymized decision packet:
  - readable public URL;
  - summary;
  - argument map (Toulmin: claim, grounds, warrant, backing, rebuttal,
    qualifier);
  - reasoning chain with confidence delta per step;
  - evidence/provenance with bitemporal handle (`valid_at` /
    `transaction_at`);
  - governance pass state;
  - uncertainty/caveats with confidence-band rendering using v7 CI tokens
    (50/80/95);
  - epistemic vs aleatoric decomposition;
  - PDF/download action;
  - 4-page A4 print layout with Instrument Serif pull quote / decision
    rationale block (reference: v7 `landing/decision-packet.html`);
  - Janus medallion as decision stamp / score ring;
  - ed25519 multi-party seal block (reference: v7
    `ProvenanceCertificate.jsx`);
  - source/citation links.
- Connect homepage, case studies, sandbox, and trust center to it.

Acceptance:

- Public packet works without authenticated providers.
- Signed/verified state remains visible.
- Invalid/expired packet states are editorial and accessible.
- PDF print snapshot passes.

Verification:

- `PublicDecisionViewerPage` route tests;
- print snapshot;
- invalid signature test.

#### Phase 3.4 - Procurement Playbook And Tender Pack

Primary fence: trust/legal/procurement.

Dependencies: Phase 0.5, 0.11, Phase 2.9.

Scope:

- Build procurement pages:
  - how to buy Atlas;
  - CPV/procurement category guidance;
  - machine-readable CPV mapping artifact;
  - Prozorro-friendly tender boilerplate in web, PDF, and Word/DOCX-friendly
    form;
  - Prozorro tender pack format in XML/PDF/DOCX-ready sources;
  - e-invoicing UBL/PEPPOL readiness for EU B2G procurement;
  - EU procurement notes;
  - objections/FAQ;
  - framework contract notes;
  - implementation timeline;
  - reference architecture for gov IT;
  - Trembita/SEV DEIR/registry integration narrative where approved;
  - compliance matrix for GDPR, NIS2, EU AI Act, local equivalents.
- Add `Save as PDF for tender pack`.
- Add tender-pack assembly rules so procurement pages, trust pages, quote
  preview, decision packet sample, and reference architecture can be exported
  without app chrome.

Acceptance:

- Procurement path is visible from pricing, trust, homepage, and persona pages.
- Downloadable boilerplate has version/date/owner and identifies whether it is
  a public template, PDF, or DOCX-ready source.
- CPV mappings and tender pack formats are generated or validated as machine
  artifacts, not prose-only tables.
- Claims are evidence-mapped.

Verification:

- print snapshot;
- content evidence map check;
- legal/procurement review.

#### Phase 3.5 - Subdomain Rollout (Trust And Status)

Primary fence: trust/legal/procurement + platform/cross-cutting.

Dependencies: Phase 1.5, Phase 2.11, Phase 1.15.

Scope:

- Roll out `trust.policyos.eu` and `status.policyos.eu` as decided in Phase 1.5.
- Wire per-domain CSP/SRI, sitemap, robots, canonical URLs, OG metadata,
  RSS/ATOM feeds, and CDN/origin.
- Wire cross-domain link previews that do not leak cookies, tokens, or tenant
  context.
- Decide whether the docs subdomain rolls out here or stays under the product
  domain.
- Decide whether multi-tenant white-label inheritance from Phase 1.5 needs
  any plumbing in Wave 3 vs Phase 8.2.

Acceptance:

- Trust center and status page resolve at their declared subdomains with
  correct CSP/SRI, sitemap, and canonical posture.
- Status page can be embedded inside the product shell as a snippet without
  pulling product cookies.
- Subdomain SSL/CDN/DNS configuration is recorded as a runbook.

Verification:

- per-domain CSP/SRI tests;
- per-domain sitemap and canonical tests;
- DNS/cert renewal runbook check.

#### Phase 3.6 - First-Run Onboarding Wizard

Primary fence: auth/onboarding.

Dependencies: Phase 1.11, Phase 2.8 (public sandbox).

Scope:

- Implement first-run wizard:
  - profile;
  - role;
  - organization context;
  - invite teammates;
  - choose plan or procurement path;
  - first scenario task;
  - first evidence/governance orientation.

Acceptance:

- Wizard can be skipped only where policy allows.
- Role selection configures persona defaults, locale, density, and initial
  workspace.
- First scenario can use sandbox fixtures or real runtime depending on account
  state.

Verification:

- journey tests;
- onboarding persistence tests.

#### Phase 3.7 - Search, Cmd-K Public Provider, ADR Index, Glossary

Primary fence: docs/support.

Dependencies: Phase 2.15, Phase 4.6 (Cmd-K foundation) if started.

Scope:

- Build search results page.
- Extend Cmd-K to search docs, blog, pricing, changelog, and support.
- Build ADR index and ADR detail public views.
- Build glossary with glyph cross-links and mini-encyclopedia behavior.

Acceptance:

- Search results show content type, route, excerpt, and source freshness.
- ADR detail links to repository ADR.
- Glossary terms link to glyph alphabet and methodology pages.

Verification:

- search index fixture tests;
- keyboard tests;
- link integrity tests.

#### Phase 3.8 - Public Components Gallery

Primary fence: docs/support + brand-as-product.

Dependencies: Phase 1.3, Phase 2.2, Phase 2.3, Phase 2.15.

Scope:

- Build a public components gallery on the docs / Atlas Codex domain mirroring
  v7 `landing/components.html`:
  - 10-radical glyph alphabet with intent variants (default / verified /
    blocked / pending) and diacritics (strict / assumed / scoped);
  - semantic buttons and pills (ok / warn / fail / neutral / info);
  - governance gates;
  - run rows;
  - sign panel with Janus medallion;
  - decision packet seal block;
  - confidence-band and bounds-fill examples using CI tokens;
  - waterfall and forest-plot examples;
  - density mode toggles (×1.0 / ×0.75 / ×0.5);
  - light / dark / high-contrast / forced-colors toggles;
  - bitemporal handle widget.
- Provide live preview and copy-paste code snippets scoped to `.c-*`.
- Source of truth remains Storybook; the gallery renders from the same
  fixtures.

Acceptance:

- Gallery and Storybook never drift (CI check).
- Snippets respect register tags (formal-uk / formal-ru / formal-en /
  neutral-en).
- Glyph alphabet exposes intent variants, diacritics, and stroke styles
  (solid / dashed / double) so regulators can verify visual conventions.

Verification:

- gallery-vs-Storybook drift test;
- a11y check for each variant;
- copy-snippet syntactic validator.

#### Phase 3.9 - Identifiability Surface As Methodology Anchor

Primary fence: domain product + public marketing.

Dependencies: Phase 1.1 register row (A2), Phase 2.7 methodology longread.

Scope:

- Cross-surface A2 Identifiability Surface from DESIGN plan §5.A2 as a
  read-only public methodology anchor:
  - point-identified / partially-identified / set-identified / untraced
    parameter map for a published decision;
  - strategy chips (back-door, front-door, IV, RDD, DiD, Manski/Robins);
  - E-value column for sensitivity to unmeasured confounding;
  - bounds column where partial identification applies;
  - link to the run, ADR, and methodology page.
- This is the visible scientific honesty surface — used by regulators,
  academics, and journalists to verify claims.

Acceptance:

- Anchor is reachable from the public decision record and methodology
  longread.
- Untraced parameters are visible, not hidden.
- Strategy chips link to glossary terms in Atlas Codex.

Verification:

- route tests;
- glossary/ADR link integrity tests;
- print snapshot.

#### Phase 3.10 - Atlas Codex And Localization-As-Feature

Primary fence: brand-as-product.

Dependencies: Phase 1.8, Phase 2.20.

Scope:

- Build public Atlas Codex/design system site or route family:
  - tokens;
  - glyph reference;
  - motion examples;
  - print/export examples;
  - voice and uncertainty language;
  - typography for Ukrainian/Russian formal register.
- Build localization feature page:
  - Ukrainian, Russian, English examples;
  - bureaucratic vocabulary;
  - formal register examples;
  - locale-specific procurement/legal copy examples.

Acceptance:

- Atlas Codex links to `docs/brand/**` as source of truth.
- Localization page is visible from marketing and procurement.
- No mascot or unsupported brand metaphors.
- A one-page ADR declares Atlas Codex as a public publication layer over the
  same source data as Storybook/design docs, not a parallel design system.
- Atlas Codex and Storybook share source fixtures or generated data so drift is
  caught by CI.

Verification:

- link checks;
- visual snapshots;
- i18n completeness check.

#### Phase 3.11 - Research Consortium And Academic License

Primary fence: post-launch product platform + public marketing + docs/support.

Dependencies: Phase 2.17 community pages, Phase 1.17.

Scope:

- Productize the research consortium:
  - named partner institutions (KSE, KMA, KPI, Lviv Polytechnic, EU
    universities — only with signed agreements);
  - eligibility, code of conduct, moderation/anti-spam policy;
  - academic license terms (free / attribution / non-commercial);
  - shared scenario library;
  - publication agreement boundary;
  - office-hours / book principal scientist routing.
- Wire a contributor wall with consent rules; respect formal Ukrainian and
  Russian register for institutional names.

Acceptance:

- Consortium has signed agreements before institutions are listed.
- Academic license is consistent with Phase 1.17 OSS scope.
- Moderation/anti-spam rules are written before public channels open.

Verification:

- institutional consent check;
- license consistency check;
- moderation policy review.

### Wave 4 - Public Decision Productization And First Composed Deliveries

Purpose: productize the public decision record, case studies, mobile preview, quote builder, bug bounty, and the design canvas/notification surfaces that depend on Wave 3 composed surfaces. Every Wave 4 phase depends only on Wave 0-3 outputs.

Parallelism: all 9 phases run in parallel — case studies, mobile preview, quote builder, bug bounty/RSS/security.txt, public decision record productization, notification center, design canvas, annual transparency report (first issue), Atlas Codex governance (AIP).

Gate to Wave 5: public decision record renders signed and verified; case studies re-run into sandbox; quote builder hands off to billing scaffold.

#### Phase 4.1 - Customers And Case Studies

Primary fence: public marketing.

Dependencies: Phase 1.8, 2.5, Phase 3.3 public sandbox fixtures.

Scope:

- Build case study index and detail pages.
- Detail page structure:
  - problem statement;
  - scenario setup;
  - simulation;
  - verification;
  - governance/evidence result;
  - decision packet link;
  - "Re-run this scenario" action.
- Support anonymized and named case modes.
- Support real customer stories with approved names, titles, portraits/photos,
  and human quotes where procurement/privacy constraints allow; avoid logo-only
  cards as the default case-study pattern.

Acceptance:

- At least three launch cases map to sandbox presets:
  - minimum support program;
  - tax maneuver;
  - tariff/energy case;
  - migration or labor-market case.
- Re-run action loads scenario parameters into sandbox.
- Case pages generate OG previews.

Verification:

- route tests for case detail;
- sandbox parameter handoff test;
- OG card render test.

#### Phase 4.2 - Public Governance-On-The-Go Demo

Primary fence: interactive public demo.

Dependencies: Phase 0.7, 0.9, 1.4, Phase 1.3, Phase 3.3.

Scope:

- Build a mobile-only public preview of the quick-approve story:
  - compact decision summary;
  - governance pass status;
  - evidence caveat;
  - one-tap approve/block preview;
  - "how this works in production" explainer link;
  - no real approval action.
- Link the preview from homepage, regulator persona, case studies, public
  decision sample, and procurement pages.
- Keep full production governance inbox and mobile quick approve in Phase 8.1.

Acceptance:

- Preview is clearly marked as public demo and cannot be mistaken for a real
  governance action.
- Mobile viewport is the primary design target.
- The demo explains step-up auth, audit, and reason capture requirements for
  production.
- Events are mapped through Phase 0.9 taxonomy.

Verification:

- mobile Playwright demo journey;
- a11y/reduced-motion test;
- event taxonomy test;
- public route bundle check.

#### Phase 4.3 - Public Quote Builder Shell

Primary fence: trust/legal/procurement.

Dependencies: Phase 0.4, 0.7, 0.11, 0.12, Phase 3.4.

Scope:

- Build public quote builder with:
  - plan/usage configuration;
  - seats;
  - runs/compute quota;
  - evidence storage;
  - procurement/on-prem add-ons;
  - VAT/EDRPOU fields;
  - invoice-offer / рахунок-оферта / счет-оферта preview;
  - composition of work section;
  - export draft quote PDF.

Acceptance:

- Quote builder can run from deterministic pricing fixtures.
- It does not imply binding legal terms unless approved.
- It can hand off to in-app billing/procurement order in Phase 5.1 (billing scaffold) and Phase 6.1 (plan picker).

Verification:

- pricing formula tests;
- PDF snapshot;
- form validation tests.

#### Phase 4.4 - Bug Bounty, CVD, security.txt, RSS / ATOM Feeds

Primary fence: trust/legal/procurement + QA/performance.

Dependencies: Phase 0.5, Phase 0.11, Phase 3.5.

Scope:

- Publish a coordinated vulnerability disclosure (CVD) policy with named
  contacts, response SLA, scope, safe-harbor language, and reward tiers.
- Publish `security.txt` (RFC 9116) at root of each public domain.
- Decide bug bounty provider (HackerOne, Intigriti, Bugcrowd) or self-hosted
  reporting; record budget, scope, and out-of-scope rules.
- Publish ATOM/RSS feeds for:
  - changelog;
  - status incidents;
  - decision record stream (public, signed);
  - blog/insights.
- Wire feed discovery (`<link rel="alternate" type="application/atom+xml">`)
  into the relevant pages.

Acceptance:

- `security.txt` validates against RFC 9116 on every public domain.
- CVD policy is linked from the trust center and the legal route family.
- ATOM/RSS feeds validate and exclude tenant/PII data.
- Bug bounty scope is consistent with the public-claim evidence map.

Verification:

- `security.txt` validator;
- ATOM/RSS schema validator;
- CVD policy review by security and legal leads.

#### Phase 4.5 - Public Decision Record Productization

Primary fence: domain product.

Dependencies: Phase 3.3, Phase 1.15 (status / changelog / roadmap) and Phase 2.11 (trust center).

Scope:

- Expand public decision record beyond current signed viewer:
  - stable public page layout;
  - SEO metadata;
  - social preview;
  - verification summary;
  - public/citizen explanation;
  - evidence and governance drilldowns;
  - downloadable decision packet PDF;
  - print-first decision packet layout with serif quote/rationale treatment;
  - transparency widget embed;
  - case-study and sandbox re-run links.

Acceptance:

- Public decision record can be shared with parliament/public audiences.
- It distinguishes verified, expired, revoked, and draft states.
- It has print/PDF and OG preview coverage.

Verification:

- public decision route tests;
- signature state tests;
- OG/PDF snapshot.

#### Phase 4.6 - Notification Center And Global Cmd-K

Primary fence: platform/cross-cutting.

Dependencies: route/surface registry, Phase 3.7 (search).

Scope:

- Build in-app notification center:
  - inbox;
  - browser notifications setup;
  - categories;
  - read/unread;
  - action links;
  - incident/license/governance priority.
- Extend Cmd-K to:
  - app routes;
  - public docs;
  - blog/resources;
  - pricing/procurement;
  - changelog/roadmap;
  - support tickets;
  - settings actions.

Acceptance:

- Cmd-K works on public and authenticated shells with appropriate source sets.
- Browser notifications require explicit permission and explain categories.
- Notification actions respect permissions and tenant context.

Verification:

- keyboard tests;
- permission tests;
- notification permission state tests.

#### Phase 4.7 - Atlas Codex Working Canvas (Design Canvas)

Primary fence: brand-as-product.

Dependencies: Phase 1.3, Phase 3.8, Phase 3.10.

Scope:

- Productize an Atlas Codex working canvas modeled on v7
  `landing/design-canvas.jsx`:
  - grid background with warm sandstone tokens;
  - sections with subtitle slots;
  - reorderable artboards;
  - inline-editable labels and titles;
  - fullscreen focus overlay with `← → Esc` keyboard control;
  - Post-It notes;
  - sidecar persistence (`.design-canvas.state.json`) for design exploration
    sessions stored alongside the Codex.
- The canvas is a public Atlas Codex surface, not an internal Figma proxy. It
  must respect a11y, reduced-motion, and forced-colors.
- Source content (component states, artboards) is generated from Storybook
  fixtures so it never drifts.

Acceptance:

- The canvas is reachable from Atlas Codex.
- Stored sessions are scrubbed of PII before publish.
- The canvas does not require a CMS write-path beyond what Phase 1.6
  declares.
- Keyboard control and a11y pass for fullscreen focus mode.

Verification:

- Storybook fixture sync test;
- a11y/keyboard test;
- PII scrub test for stored sessions.

#### Phase 4.8 - Annual Transparency Report And Public Benchmark

Primary fence: post-launch product platform + trust/legal/procurement.

Dependencies: Phase 1.13 scaffold, Phase 3.9 identifiability anchor.

Scope:

- Publish the annual transparency report following the Phase 1.13 scaffold.
- Publish a public benchmark vs alternative tools with a reproducible
  methodology:
  - benchmark methodology ADR;
  - input dataset references;
  - score definitions;
  - reproducibility manifest;
  - bibliography;
  - fairness/uncertainty caveats.
- Publish both as signed CAS artifacts with ATOM/RSS entries.
- Cross-link from trust center, methodology, and procurement playbook.

Acceptance:

- Report and benchmark are reproducible end-to-end from public references.
- Benchmark does not cherry-pick scenarios; it includes adversarial and
  unfavorable cases.
- Public claims map to evidence and ADRs.

Verification:

- reproducibility manifest test;
- benchmark scenario completeness check;
- evidence map link check;
- legal/security review.

#### Phase 4.9 - Atlas Codex Governance (Improvement Proposals)

Primary fence: brand-as-product + post-launch product platform.

Dependencies: Phase 3.10 Atlas Codex.

Scope:

- Establish an Atlas Improvement Proposal (AIP) process:
  - RFC template;
  - proposal lifecycle (draft, review, accepted, rejected, superseded);
  - publication path (Atlas Codex + ADR + repository);
  - voting / objection model (consensus with named approvers, not majority);
  - relation to ADRs and to design-token, glyph, motion, and content
    changes.
- Wire an AIP index inside Atlas Codex.

Acceptance:

- AIP index is reachable from Atlas Codex.
- Active AIPs link to their PRs and ADRs.
- No AIP changes a design-token, glyph, or motion rule without an
  accompanying ADR.

Verification:

- AIP template lint;
- ADR cross-link test;
- index uniqueness test.

### Wave 5 - Reasoning, Provenance, And Billing Foundation

Purpose: layer reasoning, provenance, consultation, and billing scaffold on top of the public decision record. Every Wave 5 phase depends only on Wave 0-4 outputs.

Parallelism: all 7 phases run in parallel — billing contract scaffold, EU AI Act transparency snippet, public reasoning surfaces (E1-E5 embeds), provenance certificate, dispute ledger, grounded docs assistant, public consultation surface.

Gate to Wave 6: billing scaffold ready for plan picker; transparency snippet embeddable; provenance certificate verifiable; consultation surface moderated.

#### Phase 5.1 - Billing Contract And Navigation

Primary fence: billing/procurement-in-app.

Dependencies: Phase 0.4, 0.7, 0.11, 0.12, Phase 4.3.

Scope:

- Add billing route family and permissions.
- Define plan, subscription, invoice, receipt, usage, quote, procurement order,
  coupon, add-on, and payment method view models.
- Add billing entry points from settings, trial banners, plan gates, and public
  quote builder handoff.

Acceptance:

- Billing routes are permission-gated.
- "not licensed" routes can link to plan picker.
- Procurement order path is not treated as card checkout.

Verification:

- route tests;
- permission tests.

#### Phase 5.2 - EU AI Act Transparency And Conformity Readiness

Primary fence: domain product.

Dependencies: Phase 0.11, Phase 3.4 (procurement compliance matrix), Phase 4.5.

Scope:

- Build embeddable transparency snippet:
  - Article 13/14-style model explanation;
  - data/provenance summary;
  - human oversight note;
  - limitations;
  - source links;
  - decision record link.
- Provide preview and embed code generator.
- Build conformity assessment readiness posture:
  - identify which Atlas features may fall into high-risk categories;
  - map Article requirements to product evidence;
  - define evidence package contents;
  - link posture into the Trust Center and compliance matrix.

Acceptance:

- Snippet can be embedded without full app chrome.
- It cites the decision record and methodology sources.
- It has high-contrast and reduced-motion support.
- Trust Center exposes AI Act compliance posture beyond the embeddable
  transparency widget.
- High-risk/conformity assessment status is labeled as ready, planned, blocked,
  or out-of-scope with evidence.

Verification:

- iframe/embed snapshot;
- accessibility test;
- compliance copy review.

#### Phase 5.3 - Public Reasoning Surfaces (Cross-Surface Of E1-E5)

Primary fence: domain product + brand-as-product.

Dependencies: Phase 1.1 register, Phase 2.3 primitives, Phase 4.5.

Scope:

- Cross-surface the DESIGN plan reasoning tracks (E1–E5) into the public
  decision record and methodology longread as read-only embeds:
  - argument map (Toulmin) on the public decision record;
  - reasoning chain with per-step confidence delta;
  - uncertainty decomposition (epistemic vs aleatoric);
  - counterfactual flip preview;
  - forest plot for evidence synthesis.
- Reuse Phase 2.3 primitives. Do not duplicate DESIGN plan state machines.
- Each embed must respect reduced-motion, forced-colors, density mode, and
  print layout.

Acceptance:

- Embeds use Phase 2.3 primitives, not bespoke styles.
- Each surface links back to its source (decision record, methodology page,
  ADR).
- Print and OG previews remain within Wave 0 budgets.

Verification:

- visual snapshots for each embed (desktop, mobile, dark, forced-colors,
  print);
- a11y test;
- link integrity test.

#### Phase 5.4 - Public Provenance Certificate

Primary fence: domain product + trust/legal/procurement.

Dependencies: Phase 2.2, Phase 4.5.

Scope:

- Expose a public provenance certificate page for each signed decision packet:
  - SHA-256 hash tree of inputs (raw source, dataset, model, run, decision);
  - ed25519 multi-party seal with signatory list;
  - Janus medallion as decision stamp;
  - bitemporal handle for the certificate (`valid_at` / `transaction_at`);
  - verification snippet (curl / language SDKs);
  - revocation/expiry state;
  - linked decision record, run, ADR, and methodology page.
- The certificate is independently verifiable without the product app.

Acceptance:

- Certificate page works without authenticated providers.
- Verification snippet matches the API longread (Phase 2.18).
- Revoked and expired states are editorial and accessible.

Verification:

- ed25519 verification fixture tests;
- signature state route tests;
- print/PDF snapshot.

#### Phase 5.5 - Public Dispute Ledger Surface

Primary fence: domain product + trust/legal/procurement.

Dependencies: Phase 1.1 register row (C1), Phase 4.5.

Scope:

- Expose a public dispute ledger surface as a regulator-facing
  challenge-response history:
  - chronological list of disputes against published decision records;
  - severity, grounds, status (open / resolved / rejected);
  - timeline of challenge, response, finding, action, close;
  - resolution outcome;
  - link to the underlying decision record;
  - link to the originating challenger (where consent allows).
- Define the privacy/consent model for naming challengers (default
  anonymized; named only with explicit consent).
- Define how the ledger relates to FOI/DSAR flows (Phase 2.16): the ledger
  references the disputed decision, not the citizen identity.

Acceptance:

- Ledger surface respects privacy and consent rules.
- It is reachable from the public decision record, trust center, and
  procurement playbook.
- It distinguishes formally adjudicated outcomes from informal disagreements.

Verification:

- privacy/consent copy review;
- route tests;
- legal review.

#### Phase 5.6 - Grounded Docs Assistant

Primary fence: docs/support.

Dependencies: Phase 0.7, Phase 2.15 (docs IA) and Phase 3.7 (search).

Scope:

- Build docs assistant UI that answers only from:
  - public docs;
  - ADRs;
  - OpenAPI;
  - glossary;
  - trust/legal pages when approved.
- Every answer includes source links.
- Add refusal/unknown state when sources do not support answer.

Acceptance:

- Assistant is not a generic chatbot.
- Source citations are visible and clickable.
- It does not answer legal/compliance questions beyond approved sources.
- No streaming hallucinations: the assistant either returns a fully
  source-grounded answer or says it does not know and links to support.
- Legal, compliance, procurement, governance, government identity, SSO
  configuration, billing, and security-configuration questions outside approved
  sources follow an explicit refusal policy.
- Draft/partial answers are not streamed before source grounding completes.

Verification:

- source-grounding tests with fixtures;
- no-source refusal tests;
- security/privacy review.

#### Phase 5.7 - Public Consultation Surface

Primary fence: post-launch product platform + domain product +
trust/legal/procurement.

Dependencies: Phase 0.11, Phase 4.5.

Scope:

- Build a public consultation surface for citizen comment on proposed policy
  interventions:
  - editorial summary of the proposed intervention;
  - counterfactual flip explorer (Phase 2.3 primitive);
  - structured comment form with privacy, moderation, and abuse handling;
  - jurisdiction tag and identity verification rules;
  - response deadline metadata;
  - publication of aggregated, anonymized feedback;
  - link to the resulting decision record once issued.
- Define moderation, anti-spam, content removal, and appeals.
- Define accessibility commitment: large-text mode, screen reader, plain
  language (PL/UA-style accessible-language guidelines).

Acceptance:

- Consultation surface meets the formal Ukrainian and Russian register
  requirements where applicable.
- Comments cannot be silently removed; removal has a reason and a public
  audit-trail summary.
- The surface clearly distinguishes consultation from binding decision.

Verification:

- moderation/audit-of-removal test;
- a11y test (large text, screen reader, plain language);
- legal/privacy review.

### Wave 6 - Billing Detail, Settings Foundation, EU AI Office Feed

Purpose: implement billing detail surfaces (which depend on billing scaffold), settings foundation, and the machine-readable EU AI Office feed. Every Wave 6 phase depends only on Wave 0-5 outputs.

Parallelism: all 6 phases run in parallel — plan picker, payment methods, invoices, cancel/downgrade, settings IA, EU AI Office feed.

Gate to Wave 7: billing detail surfaces issue invoices; settings IA resolves; EU AI Office feed validates against schema.

#### Phase 6.1 - Plan Picker, Add-Ons, Trial Lifecycle

Primary fence: billing/procurement-in-app.

Dependencies: Phase 5.1.

Scope:

- Implement in-app plan picker distinct from marketing pricing.
- Add add-ons:
  - seats;
  - runs;
  - compute quota;
  - evidence storage.
- Add trial countdown banner and trial expired screen.

Acceptance:

- Upgrade/downgrade eligibility is explicit.
- Trial expired screen distinguishes read-only from locked account.
- Plan changes produce confirmation preview before submission.

Verification:

- component tests;
- route-level trial state tests.

#### Phase 6.2 - Payment Methods, Billing Address, VAT/EDRPOU

Primary fence: billing/procurement-in-app.

Dependencies: Phase 5.1.

Scope:

- Implement payment method routes:
  - card;
  - SEPA;
  - IBAN/bank transfer;
  - government procurement/PO;
  - pay-by-invoice with act.
- Implement billing address and VAT/EDRPOU/Tax ID forms.
- Show VAT/НДС/EDRPOU labels according to locale and jurisdiction.

Acceptance:

- Region-specific fields are validated.
- Procurement payment method routes to quote/order flow.
- Sensitive payment forms are provider-ready and do not store card data in app
  state.

Verification:

- validation tests;
- security review for payment data handling.

#### Phase 6.3 - Invoices, Receipts, Failed Payment, Dunning

Primary fence: billing/procurement-in-app.

Dependencies: Phase 5.1, brand invoice artifact work.

Scope:

- Implement invoices list.
- Implement invoice detail with PDF preview.
- Implement receipt/confirmation after payment.
- Implement failed payment state and dunning timeline.

Acceptance:

- Invoice/receipt visual design matches Atlas brand.
- PDF preview and print snapshot pass.
- Failed payment timeline has next-action dates and support handoff.

Verification:

- component tests;
- print/PDF snapshots;
- date/i18n tests.

#### Phase 6.4 - Cancel, Downgrade, Pause, Coupons, Usage

Primary fence: billing/procurement-in-app.

Dependencies: Phase 5.1.

Scope:

- Implement cancel/downgrade/pause subscription flows with retention offer.
- Implement coupons/vouchers.
- Implement usage/metering dashboard:
  - compute;
  - runs;
  - evidence storage;
  - seats;
  - exportable usage report.

Acceptance:

- Destructive subscription actions require confirmation and audit event.
- Usage dashboard matches invoice quantities.
- Coupon errors are precise and non-leaky.

Verification:

- destructive action tests;
- usage formatting tests;
- permission tests.

#### Phase 6.5 - Settings Route Family And IA

Primary fence: workspace settings.

Dependencies: Phase 0.6, Phase 5.1 for billing links.

Scope:

- Add settings route family with left navigation or tabbed layout.
- Separate workspace settings and personal settings.
- Add permission gates and admin affordances.
- Keep Platform Health separate but cross-link it.

Acceptance:

- `/settings` resolves to the correct default section.
- Non-admin users can access personal settings but not workspace admin pages.
- Settings route is available from AppShell, Cmd-K, and user menu.

Verification:

- route tests;
- permission tests;
- command palette tests.

#### Phase 6.6 - EU AI Office Machine-Readable Transparency Feed

Primary fence: post-launch product platform + trust/legal/procurement +
domain product.

Dependencies: Phase 5.2 transparency snippet, Phase 5.4 provenance
certificate, Phase 4.4 ATOM/RSS feeds.

Scope:

- Expose a machine-readable transparency feed aligned with EU AI Office
  reporting expectations:
  - JSON-LD / OpenAPI artifact;
  - per-decision metadata (estimand, confidence band, governance pass,
    provenance certificate hash, identifiability strategy, methodology
    reference);
  - feed-level metadata (publisher, jurisdiction, AI Act risk class,
    conformity status);
  - ed25519 feed signature;
  - rate limits and operator authentication for regulator subscribers.
- Wire a verification endpoint for regulators.

Acceptance:

- Feed validates against a published schema.
- Feed contents match the public decision record and provenance certificate.
- Feed signature is independently verifiable.

Verification:

- schema validation test;
- cross-source consistency test;
- signature verification fixture.

### Wave 7 - Settings Detail, Civic Data, Advanced Brand

Purpose: implement settings detail (which depends on settings IA), session/exit auth surfaces, civic data SKU, and the advanced email/invoice/social artifact pass. Every Wave 7 phase depends only on Wave 0-6 outputs.

Parallelism: all 8 phases run in parallel — session/risk/logout/exit states, workspace general/members, SSO/SCIM/audit/webhooks, integrations/residency/branding, governance settings, personal settings, civic data hub, advanced email/invoice/social.

Gate to Wave 8: governance settings expose quorum/approvers/freeze; audit log is queryable; civic data SKU is legally qualified.

#### Phase 7.1 - Session, Risk, Logout, And Organization Exit States

Primary fence: auth/onboarding.

Dependencies: Phase 1.11 (auth state machine), Phase 1.12 (legal route family — leave-organization legal copy lives there), Phase 0.5 (legal/compliance evidence map for danger-zone policy).

Note: the danger-zone *implementation* lives in Phase W7 personal-settings work and runs in parallel with this phase; the *policy text* it consumes is drafted upstream in Phase 0.5 / Phase 1.12 so neither phase blocks the other.

Scope:

- Implement session expired and session refresh failure screens.
- Implement account locked and suspicious activity screens.
- Implement step-up auth failure and retry state for governance/admin actions.
- Implement logout confirmation with active-work warning where needed.
- Implement leave organization confirmation for:
  - regular member;
  - last owner/admin;
  - pending billing responsibility;
  - active governance assignment;
  - suspended or region-blocked workspace.

Acceptance:

- Session expired returns users to the intended route after successful sign-in
  when safe.
- Account locked and suspicious activity states provide support/recovery
  without revealing sensitive security details.
- Leave-organization flow prevents last-owner orphaning and billing ambiguity.
- Logout/leave flows distinguish personal account exit from workspace exit.

Verification:

- route tests for each risk/session state;
- step-up retry tests;
- last-owner and billing-responsibility fixture tests;
- security copy review.

#### Phase 7.2 - Workspace General, Members, Roles, Teams, Invitations

Primary fence: workspace settings.

Dependencies: Phase 6.5.

Scope:

- Implement organization general settings:
  - name;
  - region;
  - locale;
  - default density;
  - organization logo in header.
- Implement members and roles with RBAC.
- Implement teams.
- Implement pending invitations.

Acceptance:

- Role changes require confirmation and audit copy.
- Pending invitations support resend/revoke states.
- Organization logo preview respects brand constraints.

Verification:

- form tests;
- RBAC/permission tests;
- visual tests for compact/condensed density.

#### Phase 7.3 - SSO, SCIM, Audit, API Keys, Webhooks

Primary fence: workspace settings.

Dependencies: Phase 6.5, Phase 2.14.

Scope:

- Implement SSO config:
  - SAML metadata upload/copy;
  - OIDC client settings;
  - domain verification;
  - test connection.
- Implement SCIM/directory sync.
- Implement audit log with object/user/time filters.
- Implement API keys and personal access tokens.
- Implement webhooks with secret display, replay, delivery status.

Acceptance:

- Secrets are shown once and masked thereafter.
- Audit log filter URLs are shareable.
- Webhook replay requires confirmation and logs result.

Verification:

- secret-display tests;
- audit filter tests;
- webhook replay UI tests.

#### Phase 7.4 - Integrations, Notifications, Residency, Retention, Branding

Primary fence: workspace settings.

Dependencies: Phase 6.5.

Scope:

- Implement integrations for data sources, Slack, Jira, GitHub, S3, BigQuery,
  govcloud, and approved government systems.
- Implement workspace notification defaults.
- Implement data residency/region controls.
- Implement retention and archival policy.
- Implement branding/logo controls.

Acceptance:

- Region changes show impact and require admin confirmation.
- Retention policy has preview of affected artifacts.
- Integrations show connected, degraded, revoked, and unsupported states.

Verification:

- destructive/impact confirmation tests;
- integration state visual tests.

#### Phase 7.5 - Governance Settings

Primary fence: workspace settings.

Dependencies: Phase 0.7 and Phase 6.5.

Scope:

- Implement governance settings screen:
  - quorum approvers;
  - approver groups;
  - escalation;
  - freeze windows;
  - blocker policy;
  - read-only/freeze behavior;
  - evidence recency thresholds;
  - publication policy.

Acceptance:

- Changes require step-up auth.
- Policy preview explains which runs/actions would be blocked.
- Audit event copy is visible before save.

Verification:

- step-up auth test;
- policy preview fixture tests;
- audit copy review.

#### Phase 7.6 - Personal Profile, Security, Preferences, Danger Zone

Primary fence: personal settings.

Dependencies: Phase 6.5, Phases 2.12-2.14 (auth flows).

Scope:

- Implement personal profile.
- Implement security:
  - password;
  - MFA;
  - active sessions;
  - devices.
- Implement per-user notifications.
- Implement localization en/uk/ru.
- Implement appearance:
  - theme;
  - comfortable/compact/condensed density.
- Implement connected accounts.
- Implement GDPR export account data.
- Implement danger zone:
  - delete account;
  - leave workspace.

Acceptance:

- Security actions require current password, MFA, or step-up according to risk.
- Delete/leave actions require explicit confirmation.
- Appearance preferences reuse existing providers.

Verification:

- account security tests;
- danger-zone confirmation tests;
- preference persistence tests.

#### Phase 7.7 - Civic Data Hub And Regulator Read-Only SKU

Primary fence: domain product.

Dependencies: Phase 0.7, 0.11, Phase 1.12 (legal) and Phase 2.11 (trust center), Phase 5.1 (billing scaffold) and Phase 6.1 (plan picker).

Scope:

- Build Civic Data Hub public/research license page.
- Define anonymized scenario snapshot catalog UI.
- Build NABU/NACP/Suspilne-style read-only regulator SKU page:
  - public price/policy;
  - role limits;
  - transparency ratings;
  - no "contact us for everything" ambiguity.

Acceptance:

- Civic data page is legally qualified and does not imply raw data exposure.
- Regulator SKU route links to procurement and trust pages.
- Read-only mode is reflected in app permission copy.

Verification:

- legal/privacy review;
- route tests.

#### Phase 7.8 - Advanced Email, Invoice, Receipt, And Social Artifacts

Primary fence: brand-as-product.

Dependencies: Phase 2.4, Phase 2.5, Phase 6.3 (invoice routes), Phase 2.17 (content engine).

Scope:

- Extend the Phase 2.4 email foundation for:
  - invoice;
  - receipt;
  - failed payment;
  - public decision published;
  - weekly briefing;
  - annual report release;
  - longread/resource nurture.
- Build marketing email and weekly briefing templates.
- Build designed invoice/receipt artifact style.
- Extend the Phase 2.5 OG generator with custom OG/Twitter/LinkedIn artwork per
  longread, case, decision, resource, invoice-safe receipt preview, and report.

Acceptance:

- Advanced templates reuse the email-safe Atlas foundation instead of forking
  provider-specific defaults.
- Social previews remain generated from content metadata even when custom art is
  available.
- Invoices/receipts pass print/PDF snapshots.

Verification:

- email HTML snapshot tests;
- OG render tests;
- print snapshots.

### Wave 8 - Governance Inbox, Multi-Tenant, Auditor Portal

Purpose: turn governance into a product surface (governance inbox + mobile quick approve), then ship multi-tenant white-label and auditor portal. Every Wave 8 phase depends only on Wave 0-7 outputs.

Parallelism: all 3 phases run in parallel — governance inbox/mobile quick approve, multi-tenant white-label, auditor portal SKU.

Gate to Wave 9: governance inbox approvals require step-up and audit chain; white-label tenants inherit trust posture; auditor portal is read-only and time-boxed.

#### Phase 8.1 - Governance Inbox And Mobile Quick Approve

Primary fence: domain product.

Dependencies: Phase 0.7, Phase 7.5, Phase 2.13 (step-up via MFA).

Scope:

- Build approver inbox:
  - queue of governance passes;
  - apply/block actions;
  - reason capture;
  - evidence summary;
  - conflict/blocker tags;
  - escalation state;
  - audit event preview.
- Build mobile quick-approve flow:
  - minimal decision summary;
  - confidence/evidence caveat;
  - approve/block/reason;
  - step-up auth;
  - offline/degraded behavior.

Acceptance:

- Approvals and blocks require reason where governance policy requires it.
- Mobile layout is not just desktop squeezed down.
- Actions are audited and reversible only according to policy.
- Reversal of an apply/block action requires step-up auth and an audit-event
  chain link to the original action.

Verification:

- Playwright mobile journey;
- step-up auth test;
- audit copy tests.

#### Phase 8.2 - Multi-Tenant White-Label / Ministry-Branded Subdomain Mode

Primary fence: post-launch product platform + platform/cross-cutting +
brand-as-product.

Dependencies: Phase 1.5, Phase 6.5 (settings IA) and Phase 7.2 (workspace general), Phase 3.5 subdomain
rollout.

Scope:

- Productize white-label tenancy:
  - ministry-branded subdomain mapping (e.g.
    `atlas.<ministry>.gov.ua`);
  - tenant-scoped logo override with Atlas mark coexistence rules;
  - tenant-scoped color override boundary (signal colors remain immutable);
  - tenant-scoped legal copy attachments;
  - tenant-scoped audit log and provenance certificate ownership;
  - tenant-scoped data residency choice;
  - cross-tenant analytics isolation.
- Define what white-label cannot change (governance gates, glyph alphabet,
  Janus medallion as decision stamp, transparency snippet).

Acceptance:

- White-label tenants inherit the trust posture without weakening it.
- Brand override boundary cannot be exploited to disguise Atlas claims.
- Subdomain routing reuses Phase 1.5 topology rules.

Verification:

- brand-override boundary test;
- tenant subdomain routing test;
- trust posture parity test.

#### Phase 8.3 - External Auditor Portal SKU

Primary fence: post-launch product platform + domain product.

Dependencies: Phase 7.3 (audit log inside SSO/SCIM/Audit/API Keys/Webhooks), Phase 5.4 provenance certificate.

Scope:

- Build an external auditor portal SKU with read-only access:
  - audit log filter by object/user/time;
  - provenance certificate viewer;
  - dispute ledger filter;
  - identifiability anchor;
  - decision record export (PDF + signed JSON);
  - tenant scope limited to the audit engagement;
  - time-boxed access with expiry and revocation;
  - audit-trail-of-the-audit (auditor actions are themselves audited).
- Wire billing/procurement order path so auditor access is metered and
  procurable.
- Coordinate the auditor portal with the Forensic Mode item (Phase 9.3) so
  contested decisions can be reviewed in immutable replay.

Acceptance:

- Auditor portal is read-only and time-boxed.
- Auditor actions are audited.
- It cannot leak cross-tenant data.

Verification:

- read-only enforcement test;
- audit-of-audit test;
- expiry/revocation test.

### Wave 9 - Mobile System And Post-Launch Programs

Purpose: deliver the mobile system on top of governance inbox, plus the post-launch programs that require the full product to exist. Every Wave 9 phase depends only on Wave 0-8 outputs.

Parallelism: all 3 phases run in parallel — iOS Liquid Glass mobile system, operator certification program, forensic mode and coordinated decision-reversal disclosure.

Gate to Wave 10: mobile journeys pass screen-reader smoke; certification artifacts verify like decision packets; forensic snapshots are immutable.

#### Phase 9.1 - iOS Liquid Glass Mobile System

Primary fence: brand-as-product + interactive demo.

Dependencies: Phase 2.1, Phase 4.2, Phase 8.1.

Scope:

- Productize the mobile system according to the Phase 2.1 decision:
  - PWA + responsive product (default);
  - dedicated mobile reading mode for landing, docs, dashboard;
  - native iOS shell using the v7 iOS Liquid Glass frame as design canvas
    (only if Phase 2.1 records a native commitment).
- For the design-canvas path, use the v7 `ios-frame.jsx` (`IOSDevice`,
  `IOSStatusBar`, `IOSNavBar`, `IOSGlassPill`, `IOSList`, `IOSListRow`,
  `IOSKeyboard`) as Storybook-only primitives to render mobile previews.
- Reuse Phase 2.3 density and reasoning primitives so the mobile reading
  mode does not fork visual language.

Acceptance:

- Mobile surfaces respect the Phase 2.1 decision and do not silently
  introduce native dependencies.
- Mobile reading mode passes a11y on screen readers in en/uk/ru on the
  critical journeys listed in Phase 10.2.
- Public mobile preview routes remain within the Wave 0 public bundle
  budget.

Verification:

- mobile Playwright journeys;
- per-locale screen-reader smoke;
- bundle budget check.

#### Phase 9.2 - Operator Certification Program

Primary fence: post-launch product platform + public marketing + docs/support.

Dependencies: Phase 2.15 / Phase 2.16 (docs / help), Phase 8.1 (governance inbox).

Scope:

- Build an operator certification program:
  - role-based curriculum (analyst, ministry, regulator, NGO, academia,
    procurement);
  - written training modules sourced from docs and ADRs;
  - exam (written, scenario-based, scored against rubric);
  - certificate issuance with Janus medallion seal and bitemporal handle;
  - public certified-operator registry (with consent);
  - re-certification cadence;
  - cancellation / revocation procedure.
- Decide whether certificates are issued via the in-app billing/procurement
  flow (Wave 5) or a dedicated certification page.
- Record exam integrity and proctoring posture; record DPA implications.

Acceptance:

- Certification program has owner, schedule, curriculum, exam, and
  registry.
- Certificate artifact (PDF + signed JSON) is verifiable like a decision
  packet (Phase 5.4).
- Registry respects consent and supports revocation.

Verification:

- exam rubric review;
- certificate artifact verification fixture;
- registry consent/revocation test.

#### Phase 9.3 - Forensic Mode And Coordinated Decision-Reversal Disclosure

Primary fence: post-launch product platform + domain product +
trust/legal/procurement.

Dependencies: Phase 4.5 public decision record, Phase 5.4 provenance
certificate, Phase 8.3 auditor portal.

Scope:

- Build a Forensic Mode that captures an immutable, signed snapshot of a
  contested decision (run, data, model, environment, ADR, provenance, raw
  artifacts) and exposes it via the auditor portal.
- Define a coordinated decision-reversal disclosure process for cases where
  an Atlas decision is overturned by external review:
  - public reversal notice template;
  - timeline obligations;
  - replacement decision record linkage;
  - communication to affected citizens / regulators / press;
  - lessons-learned ADR.
- The disclosure process must not be used to delete or hide the original
  record — it supersedes via the bitemporal handle.

Acceptance:

- Forensic snapshots are immutable and time-stamped.
- Reversal notices link to the original record, the replacement record, and
  a lessons-learned ADR.
- No decision can be silently deleted.

Verification:

- immutability test;
- bitemporal supersession test;
- legal/privacy review.

### Wave 10 - Hardening, Performance, Launch Gates, And Closeout

Purpose: turn the implementation into a launchable, measurable, maintainable surface set. Wave 10 tightens and proves the ratchets introduced in Phase 0.10; it is not the first moment security, privacy, route, content, a11y, or bundle gates run.

Parallelism: all 5 phases run in parallel — route/sitemap coverage, a11y/visual/print/responsive, performance/bundle, security/privacy/compliance, launch closeout.

#### Phase 10.1 - Route Coverage And Sitemap Gate

Primary fence: QA/performance.

Scope:

- Generate route inventory for public, auth, billing, settings, docs, support,
  trust, domain, and app routes.
- Validate route IDs, page titles, meta descriptions, canonical URLs, sitemap
  inclusion, robots policy, structured data/schema.org metadata, Open Graph and
  LinkedIn/Twitter previews, print support, locale availability, and owner.

Acceptance:

- No planned route lacks owner or launch state.
- Public sitemap contains all public launch routes.
- Authenticated routes are excluded from public sitemap.
- Public canonical URLs and structured data are deterministic across locales.

Verification:

- route inventory script;
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run typecheck`.

#### Phase 10.2 - A11y, Visual, Print, And Responsive Gate

Primary fence: QA/performance.

Scope:

- Add Playwright journeys for:
  - public marketing;
  - sandbox;
  - trust/procurement;
  - auth;
  - billing;
  - settings;
  - docs/support;
  - public decision;
  - governance inbox/mobile approve.
- Add visual snapshots for desktop, mobile, dark, forced-colors, print.
- Add print snapshots for tender pack, docs article, decision packet, invoice,
  receipt, trust artifact.
- Add screen-reader smoke checks for NVDA/VoiceOver or documented local
  equivalents on uk and ru locales for:
  - auth;
  - billing;
  - governance inbox;
  - public decision record;
  - mobile quick approve.

Acceptance:

- WCAG 2.2 AA route checks pass.
- Screen-reader smoke confirms formal Ukrainian and Russian flows are
  navigable and understandable in critical journeys.
- Mobile layouts do not overlap or truncate critical text.
- Print output is usable for regulators/procurement.

Verification:

- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run test:a11y`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run test:visual`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run design:print`

#### Phase 10.3 - Performance And Bundle Gate

Primary fence: QA/performance.

Scope:

- Enforce public route bundle budgets.
- Run Lighthouse for homepage, docs article, sandbox, trust center, pricing,
  public decision record.
- Ensure marketing homepage target remains Lighthouse 100/100/100/100 or has a
  dated exception with owner.
- Keep homepage JS under the Wave 0 agreed budget, with `<100 KB compressed`
  as the default target.
- Add a public performance badge only when it is backed by the latest CI
  Lighthouse/bundle evidence and links to the evidence report.

Acceptance:

- Public launch routes pass performance budgets.
- Heavy authenticated app chunks are not loaded on public homepage.
- Images/fonts are optimized and cached.
- The performance badge cannot be hardcoded; it is hidden or marked stale when
  evidence is older than the accepted freshness window.

Verification:

- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run build`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run check:bundle`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run lighthouse:ci`

#### Phase 10.4 - Security, Privacy, And Compliance Gate

Primary fence: QA/performance.

Scope:

- Review auth, billing, SSO, SCIM, API keys, webhooks, DSAR, cookies,
  analytics, public decision signing, transparency widgets, and support
  attachments.
- Validate CSP/SRI for public pages.
- Validate no secrets or sensitive tenant data leak into public routes.
- Validate public trust/legal claims against evidence map.

Acceptance:

- Security review findings are closed or have launch-blocking exceptions.
- Public pages have correct CSP/SRI posture.
- Billing/auth forms do not store sensitive secrets in client persistence.

Verification:

- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run audit:ci`
- targeted security tests;
- legal/compliance signoff.

#### Phase 10.5 - Launch Closeout

Primary fence: QA/performance.

Scope:

- Create closeout report under `docs/archive/reports/`.
- Update this plan dashboard.
- Move stable behavior into:
  - `docs/reference/frontend/**`;
  - `docs/reference/security-compliance.md`;
  - `docs/how-to/**`;
  - `docs/runbooks/**`;
  - ADRs where decisions are irreversible.
- Move this plan to `accepted/` when approved, then archive when complete.

Acceptance:

- All P0/P1 findings are either done or have explicit owner/date exception.
- All public claims have evidence.
- All route families have tests and ownership.
- The plan no longer acts as the only source of truth.

Verification:

- full frontend gate;
- docs link check;
- closeout review.

## Maximum Honest Parallelism Map

The table below is the intended execution shape after the topological
restructure. Inside each wave, every listed phase runs in parallel — no phase
depends on a peer in the same wave. Phases depend only on phases in PRIOR
waves. Shared files (route registry, i18n, OpenAPI, design tokens, etc.)
serialize through their queue owner; the queue is the merge gate, not a
dependency.

| Wave | # phases | Parallel lanes | Serialized gates (queues) |
| --- | --- | --- | --- |
| 0 | 12 | zip ledger, public topology decision, content model, API inventory, legal evidence map, state matrix, backend contract lock, content ownership, analytics/attribution, continuous gates, jurisdiction, lead destination | none — all inputs are independent |
| 1 | 17 | v7 surface register, v7 design-token drift, public page primitives, sandbox engine choice, multi-domain topology, content backend strategy, public shell, content registry, cookie/consent, global states, auth state machine, legal route family, transparency report scaffold, sovereign cloud, status/changelog/roadmap, API/SDK quickstarts, OSS strategy | design-token queue, route registry, content registry, i18n catalogs, OpenAPI |
| 2 | 20 | iOS / mobile decision, Janus medallion primitives, citation/density/reasoning primitives, email foundation, OG generator, RUM/error/synthetic, methodology longread, sandbox, ROI calculator, careers/contact/partners, trust center, auth recovery/MFA/SSO, docs IA, help center / DSAR / FOI, content engine, API longread, Evidence Fabric source detail, animated glyphs | OpenAPI/contracts, design-token, lead destination, public-claim evidence map |
| 3 | 11 | homepage upgrade, persona pages, decision packet sample, procurement playbook, subdomain rollout, first-run onboarding, public search/Cmd-K, components gallery, identifiability methodology anchor, Atlas Codex, research consortium | subdomain DNS/CSP queue, search index, Atlas Codex topology, route registry |
| 4 | 9 | case studies, mobile preview, quote builder, bug bounty / CVD / RSS, public decision record productization, notification center, design canvas, annual transparency report, Atlas Codex governance | governance API, billing handoff stub, public-decision signing |
| 5 | 7 | billing scaffold, EU AI Act transparency snippet, public reasoning surfaces (E1-E5 embeds), provenance certificate, dispute ledger, grounded docs assistant, public consultation | billing API/OpenAPI, assistant grounding contract, consultation moderation |
| 6 | 6 | plan picker, payment methods, invoices/receipts/dunning, cancel/downgrade/usage, settings IA, EU AI Office feed | billing legal artifacts, workspace registry, AI Office feed schema |
| 7 | 8 | session/risk/exit states, workspace general/members, SSO/SCIM/audit/webhooks, integrations/residency/branding, governance settings, personal settings, civic data hub, advanced email/social/invoice artifacts | permission registry, audit contract, integrations queue, governance settings audit |
| 8 | 3 | governance inbox + mobile quick approve, multi-tenant white-label, auditor portal SKU | governance API, white-label subdomain map, auditor portal access contract |
| 9 | 3 | iOS Liquid Glass mobile system, operator certification program, forensic mode + reversal disclosure | mobile distribution, certification artifact contract, forensic immutability contract |
| 10 | 5 | route/sitemap, a11y/visual/print/responsive, performance/bundle, security/privacy/compliance, launch closeout | release/deployment, evidence map signoff |

## Execution Checklists

### Per-Route Checklist

- [ ] Route ID is registered.
- [ ] Owner and launch status are recorded.
- [ ] SEO metadata exists for public pages.
- [ ] OG/Social preview metadata is generated from content metadata, not
      hardcoded.
- [ ] Register tag (`formal-uk`, `formal-ru`, `formal-en`, `neutral-en`) is
      checked by the content registry where public copy is localized.
- [ ] en/uk/ru copy exists or explicit fallback is approved.
- [ ] Loading, empty, error, unauthorized, unlicensed, offline/degraded states
      are implemented where applicable.
- [ ] Print behavior is defined.
- [ ] Analytics behavior respects consent.
- [ ] Permission and tenant behavior are tested.
- [ ] Route has component tests.
- [ ] Route has at least one Playwright journey if user-critical.
- [ ] Visual/mobile snapshot exists for launch-critical pages.
- [ ] Density mode (×1.0 / ×0.75 / ×0.5) renders correctly without per-surface
      CSS overrides.
- [ ] Dark / high-contrast / forced-colors modes render correctly.
- [ ] Citation typography uses Instrument Serif italic via `.t-citation`,
      not a hard-coded font stack.
- [ ] Janus medallion appears only on surfaces that carry a decision stamp /
      score ring; standard Atlas mark is used elsewhere.
- [ ] Bitemporal handle (`valid_at` / `transaction_at`) is rendered on any
      policy/decision/changelog/case-study artifact.
- [ ] Canonical URL respects the multi-domain topology decision from Phase 1.5.
- [ ] If the route lives on `trust.policyos.eu` or `status.policyos.eu`, the
      per-domain CSP/SRI/sitemap/robots rules from Phase 3.5 apply.

### Per-Form Checklist

- [ ] Field validation is typed and localized.
- [ ] Submit/loading/success/error states exist.
- [ ] Rate-limit and retry copy exists.
- [ ] Privacy/security copy exists.
- [ ] Retention period and downstream owner are declared.
- [ ] Destination system is declared and health-checked.
- [ ] Event taxonomy mapping is declared.
- [ ] Jurisdictional retention rule is declared for UA, EU, or both.
- [ ] Spam/abuse handling is declared for public forms.
- [ ] Attachments, if allowed, have type/size limits and malware-scan owner.
- [ ] Sensitive data persistence policy is explicit.
- [ ] No client-side persistence of card data, secrets, or tokens beyond the
      session.
- [ ] Audit event is previewed for admin/governance/billing actions.
- [ ] Destructive actions require confirmation.
- [ ] Step-up auth is required for high-risk actions.

### Per-Public-Claim Checklist

- [ ] Claim owner is listed.
- [ ] Evidence link exists.
- [ ] Certification status is exact.
- [ ] Jurisdiction and region are explicit where relevant.
- [ ] Jurisdictional scope tag is declared: UA, EU, or out-of-scope.
- [ ] If the claim is related to EU AI Act or NIS2, risk class and required
      artifact are listed.
- [ ] Last reviewed date exists.
- [ ] Legal/security approval exists for launch.

### Per-Artifact Checklist

- [ ] Screen view exists.
- [ ] Print/PDF view exists.
- [ ] Download metadata includes version/date/source.
- [ ] Social/OG preview exists when shareable.
- [ ] Accessibility and contrast are checked.
- [ ] Fixture/live data status is visible.
- [ ] If the artifact carries a verdict, it carries a Janus medallion as
      decision stamp / score ring with the state variant matching the
      artifact lifecycle (draft / signed / expired / revoked).
- [ ] If the artifact is signed, the ed25519 multi-party seal block is
      rendered and independently verifiable (Phase 5.4).
- [ ] If the artifact carries a confidence claim, CI tokens (50/80/95) and
      bounds-fill / bounds-stroke are used; the epistemic vs aleatoric split
      is visible.
- [ ] If the artifact references a causal claim, identifiability strategy
      (back-door / front-door / IV / RDD / DiD / Manski / Robins) is named
      and the parameter status (point / partial / set / untraced) is shown.
- [ ] If the artifact is supersedable, the bitemporal handle (`valid_at` /
      `transaction_at`) is visible and the supersession chain is linked.
- [ ] If the artifact is on a regulated subdomain, the per-domain trust
      posture from Phase 3.5 is preserved (no shared cookies/tokens).

## Open Decisions

These decisions must be made in Wave 0 or early Wave 1:

| Decision | Default | Required evidence |
| --- | --- | --- |
| Single app vs separate public app | Single app with aggressive lazy splitting | Bundle and Lighthouse evidence for public routes |
| Sandbox engine | Precomputed fixtures, escalate to WASM only with bundle/perf evidence | Phase 1.4 decision note |
| Jurisdictional scope | UA + EU in scope, RF out of scope until legal review | Phase 0.11 jurisdiction registry |
| CRM/lead destination | Single declared system per form, health-checked | Phase 0.12 destination registry |
| Email kit foundation | Atlas-tokenized transactional templates from Wave 1 | Phase 2.4 snapshots and provider owner |
| Provider lock-in / portability strategy | Provider-neutral email templates with adapter boundary for Postmark, Resend, and SES until provider selection is signed | Phase 2.4 portability note |
| Mobile quick-approve visibility | Public preview from Wave 2 demo set | Phase 4.2 public demo evidence |
| Public telemetry | Consent-aware RUM + error tracking + synthetic checks from Wave 1 | Phase 2.6 telemetry evidence |
| Atlas Codex topology | Publication layer over Storybook/design docs, single source | Phase 3.10 ADR |
| AI Act readiness | Conformity assessment posture in trust center | Phase 5.2 evidence package |
| Public roadmap slip-comms policy | Public template + channel before voting flag flips | Phase 1.15 roadmap policy |
| Public counters source | Fixture-labeled until telemetry contract exists | API/telemetry contract and privacy review |
| Trust center claim level | Publish only evidence-mapped claims | Legal/security evidence map |
| Quote builder binding status | Non-binding draft quote until legal approval | Legal/procurement review |
| Government identity wording | "Ready/planned/supported" only when evidence exists | Integration contracts and legal copy |
| Public roadmap voting | Feature-flagged after abuse/spam moderation decision | Product/security review |
| Docs assistant launch | Source-grounded only, no generic model claims | Grounding tests and source policy |
| Multi-domain topology | atlas.policyos.dev (product) + trust.policyos.eu + status.policyos.eu; docs subdomain only with evidence | Phase 1.5 decision note, per-domain CSP/SRI/sitemap/canonical/OG/RSS plan |
| Content backend / CMS | Hybrid: regulated copy markdown-in-repo, marketing/blog/case study optional CMS — decided in Phase 1.6 | Phase 1.6 decision note, editorial PR flow, translator workflow, preview env |
| Advanced surface tracking | Cross-reference register pointing at `DESIGN_BEST_IN_CLASS_PLAN.md`, not duplicated tracking here | Phase 1.1 register and CI link check |
| v7 design-token deltas | Adopt the additive deltas via a single design-token patch; reject any token that conflicts with current production tokens until Phase 1.2 records a reason | Phase 1.2 diff + ADR |
| iOS / mobile system scope | PWA + responsive product (default); native iOS only with a Phase 2.1 native commitment ADR | Phase 2.1 decision note, mobile budget |
| OSS license boundary | Default proprietary all-rights-reserved; OSS scope and license per-part decided in Phase 1.17 | Phase 1.17 ADR + license-header drift gate |
| Operator certification | Atlas-issued, signed like a decision packet; consent-based public registry | Phase 9.2 program note, exam rubric review |
| White-label tenancy | Brand override allowed; governance gates, glyph alphabet, Janus decision stamp, transparency snippet immutable | Phase 8.2 boundary test |
| Annual transparency report cadence | Annual default; benchmark methodology ADR before second issue | Phase 1.13 scaffold + Phase 4.8 first issue |
| EU AI Office feed | Machine-readable JSON-LD + ed25519 signature; rate-limited, regulator-authenticated subscription | Phase 6.6 schema and signature test |
| Forensic mode and decision reversal | Immutable signed snapshots, bitemporal supersession, no silent deletion | Phase 9.3 immutability and supersession test |

## Exit Criteria

This plan is ready to move from `active/` to `accepted/` when:

1. Wave 0 decisions are made and recorded.
2. P0/P1 findings have owners, target waves, and acceptance criteria.
3. Public topology, route registry, content registry, i18n, legal evidence, and
   API contract queues are accepted by their owners.
4. The implementation team agrees to the parallelism map and do-not-parallelize
   pairs.

This plan is ready to archive when:

1. Wave 10 closeout exists under `docs/archive/reports/`.
2. Stable behavior has moved into reference docs, how-to docs, runbooks, ADRs,
   or machine-readable contracts.
3. All P0/P1 findings are closed or have dated owner-approved exceptions.
4. Public launch routes pass route, a11y, visual, print, performance, security,
   privacy, and i18n gates.
5. Wave 9 post-launch items (operator certification, forensic mode, iOS
   mobile system) are either delivered, registered against a successor plan,
   or explicitly deferred with a dated owner; nothing in Wave 9 is silently
   dropped on archive.
6. The v7 Advanced Surface Register has no orphan rows — every entry points at
   either an implemented surface, a DESIGN plan track, or a dated removal
   note.
7. Every new wave's "Gate to next wave" criteria are recorded as met, with
   evidence — restructured topological tiers are honored across the closeout.
