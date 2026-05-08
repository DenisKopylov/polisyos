---
title: PolicyOS Atlas Product, Marketing, Client Surfaces Master Plan
status: active
owner: team-polisyos
created: 2026-05-06
last_verified: 2026-05-07
stability: draft
related:
  - docs/plans/active/REPOSITORY_BEST_IN_CLASS_REMEDIATION_MASTER_PLAN.md
  - docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md
  - docs/plans/active/FRONTEND_SOTA_PLAN.md
  - docs/plans/active/DOCUMENTATION_SOTA_PLAN.md
  - docs/plans/active/INFRASTRUCTURE_SOTA_PLAN.md
  - docs/brand/ATLAS_DESIGN_SYSTEM.md
  - docs/brand/GLYPH_SPECIFICATION.md
  - docs/brand/MOTION.md
  - docs/brand/PRINT_AND_EXPORT.md
  - docs/brand/TYPOGRAPHY_UA_RU.md
  - docs/reference/frontend/workspace-contract.md
  - docs/reference/security-compliance.md
  - schemas/runtime_api_v1.openapi.json
---

# PolicyOS Atlas Product, Marketing, Client Surfaces Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax where a phase is ready for
> execution tracking.

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

- `/Users/deniskopylov/Downloads/PolicyOS Atlas Design System-6.zip`;
- existing Atlas frontend code under `apps/runtime-dashboard/**`;
- existing brand docs under `docs/brand/**`;
- public marketing, procurement, documentation, support, auth, billing,
  settings, and domain-specific ideas listed by Denis on 2026-05-06;
- plan-review additions received on 2026-05-07 covering backend contracts,
  content ownership, analytics/attribution, continuous gates, jurisdiction,
  lead routing, sandbox architecture, early email/OG, public telemetry, and
  AI Act readiness.

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

Baseline verified locally on 2026-05-07.

### Zip Inventory

`PolicyOS Atlas Design System-6.zip` contains:

| Zip area | Verified contents | Production interpretation |
| --- | --- | --- |
| `README.md` and `SKILL.md` | Atlas visual, tone, typography, iconography, motion, and product workflow guidance | Keep as design-system reference input. Reconcile with `docs/brand/**` and current production tokens. |
| `colors_and_type.css` | CSS custom properties and semantic colors | Use as drift fixture, not direct import. |
| `assets/**` and `landing/assets/**` | Atlas logos, Janus medallion, favicon, 10 glyph SVGs | Already mostly present in `apps/runtime-dashboard/public/atlas/**`; run geometry/hash drift checks before overwriting. |
| `landing/index.html` | Static marketing page with hero, workflows, capabilities, glyph alphabet, compare, pricing, CTA, footer | Prototype for first public site wave. Missing segmentation, trust, content, service, procurement, interactive sandbox, public roadmap, and legal depth. |
| `landing/auth.html` | Static sign-in, sign-up, checkout concepts | Prototype only. Missing forgot/reset, verification, MFA, SSO picker, magic link, invite, tenant picker, onboarding, step-up, suspicious activity, full billing lifecycle. |
| `landing/docs.html` | Static docs handbook longread with sidebar, search input, lanes, quickstart, contracts, runbooks, ADR shelf, right TOC | Prototype only. Missing routed docs IA, article view, OpenAPI explorer, versioning, search results, tutorial engine, ADR detail, glossary, print/PDF, status snippet, docs assistant. |
| `landing/design-canvas.jsx` | Design exploration canvas | Treat as visual reference and Storybook seed, not product route. |
| `preview/*.html` | Tokens, buttons, badges, cards, glyphs, logo, type, shadows, uncertainty previews | Convert into Storybook/design-reference stories and automated token drift fixtures. |
| `ui_kits/dashboard/*.jsx` | 30+ prototype dashboard/product surfaces | Most are product-feature backlog items already partially tracked by `DESIGN_BEST_IN_CLASS_PLAN.md`; use only for missing domain-specific surfaces listed in this plan. |
| `policy-engine/apps/runtime-dashboard/public/atlas/**` | Legacy destination path from the zip | Canonical repo has moved toward `apps/runtime-dashboard/**`; do not revive old `apps/runtime-dashboard/**` as a primary app path. |

### Current Production Anchors

| Area | Existing anchor | Current state |
| --- | --- | --- |
| Canonical frontend app | `apps/runtime-dashboard/**` | React/Vite app exists with routes, providers, Storybook, tests, a11y, visual, Lighthouse scripts. |
| Canonical app path transition | Canonical app path target = `apps/runtime-dashboard/**`; current/legacy transition path to reconcile = `policy-engine/apps/runtime-dashboard/**` until Phase 0.1 closes the rename PR gap | Phase 0.1 must close the rename/topology gap before Wave 1.1; until then, agents verify actual paths with `rg --files` before editing. |
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
| Backend contract lock | team-runtime | ad hoc fixture/API assumptions | every Wave 4-8 UI flow is `ready`, `stub-locked`, or `blocked` before implementation |
| Content register ownership | team-content | content types named, owners not complete | every localized public content type has register owner and register tag policy |
| Public analytics/attribution | team-growth | consent-gated analytics only | every CTA/form/demo event has taxonomy, destination, and consent-aware experiment policy |
| Continuous gates ratchet | team-quality | launch gates concentrated in Wave 10 | security, privacy, route, content, a11y, bundle, and claim gates ratchet from Wave 0 |
| Jurisdiction scope | team-legal | UA/EU implied but not fully tagged | every legal/trust/procurement claim and page has jurisdiction tag and risk posture |
| Lead routing health | team-revenue | downstream owner declared only | every public form has destination system and green health-check fixture |
| Public telemetry | team-ops | Lighthouse lab checks only | RUM, JS error reporting, and synthetic checks cover public critical routes |

### Subplan Relationship

| Existing plan | Relationship |
| --- | --- |
| `DESIGN_BEST_IN_CLASS_PLAN.md` | Owns deep Atlas product interaction backlog. This plan owns marketing/client/trust/procurement/support/auth/billing/settings expansion. |
| `FRONTEND_SOTA_PLAN.md` | Owns frontend architecture, UX principles, accessibility, performance, and shell quality. This plan consumes those gates. |
| `DOCUMENTATION_SOTA_PLAN.md` | Owns repository documentation lifecycle. This plan adds public docs/support product surfaces and must not fork factual docs source of truth. |
| `INFRASTRUCTURE_SOTA_PLAN.md` | Owns deployment, CI, release, supply-chain, and platform controls. This plan queues public app/deployment/security changes through it. |
| `REPOSITORY_BEST_IN_CLASS_REMEDIATION_MASTER_PLAN.md` | Owns repository-wide safety, queue, and closeout discipline. This plan mirrors its wave-first execution model. |

## Finding Ledger

| ID | Severity | Gap | Primary fence | Target wave |
| --- | --- | --- | --- | --- |
| MKT-01 | P0 | Public marketing site is only a minimal landing route and zip prototype. | public marketing | 1-2 |
| MKT-02 | P1 | No persona/use-case segmentation for analyst, ministry, regulator, NGO, academia. | public marketing | 2 |
| MKT-03 | P1 | No customers/case studies with detailed simulation/verification/result pages. | public marketing | 2 |
| MKT-04 | P1 | No Methodology/Science page for causal estimates, identifiability, JAX, validation, literature/ADR links. | public marketing | 2 |
| MKT-05 | P1 | No blog/insights, resource library, webinars/events, press/media kit, glossary, about, careers, partners, contact/demo route families. | public marketing | 2 and 7 |
| MKT-06 | P1 | Homepage lacks playable product demo, sandbox, decision packet sample, ROI/TCO calculator, and live counters. | interactive demo | 2 |
| MKT-07 | P1 | Contact/demo, career applications, partner inquiries, and roadmap votes need scheduling, qualification, privacy, moderation, and downstream handoff contracts. | public marketing | 0 and 2 |
| CONTRACT-01 | P0 | Wave 4-8 UI flows can drift if they start from fixtures without accepted OpenAPI or locked stubs. | API/contracts | 0 |
| CONTENT-01 | P1 | Localized public routes can be registered without named register owners for formal uk/ru copy. | public marketing | 0 |
| ANALYTICS-01 | P1 | Consent-gated analytics exists conceptually, but CTA/form/demo events lack taxonomy, attribution, and experiment destinations. | QA/performance + public marketing | 0 and 1 |
| GATE-01 | P0 | Security/privacy/performance/content gates are concentrated too late if Wave 10 is first enforcement. | QA/performance | 0 |
| JUR-01 | P0 | UA/EU jurisdiction scope, out-of-scope jurisdictions, FOI, e-invoicing, e-signature, and AI Act posture are not locked before sales/procurement pages. | trust/legal/procurement | 0 |
| LEAD-01 | P1 | Public forms can collect leads without health-checked CRM/calendar/support/careers/newsletter destinations. | API/contracts | 0 |
| SANDBOX-01 | P1 | Public sandbox engine choice is an architecture fork that affects performance and demo quality. | interactive public demo | 0 |
| TRUST-01 | P0 | No public Trust Center with SOC 2/ISO/GDPR/residency/subprocessors/DPA/AUP/SLA/security questionnaire/VPAT/a11y/on-prem evidence. | trust/legal | 3 |
| TRUST-02 | P0 | No public legal route family for ToS, Privacy, DPA, AUP, SLA, subprocessors, cookies. | trust/legal | 3 |
| TRUST-03 | P1 | No status page with incident history/RCA, public changelog, or public roadmap. | trust/status | 3 |
| TRUST-04 | P1 | No procurement playbook, tender boilerplate, CPV/Prozorro/EDRPOU/VAT content, quote builder, or reference architecture for gov IT. | procurement | 3 and 5 |
| AUTH-01 | P0 | Auth has no forgot/reset/email verification/MFA/SSO/magic link/invite/tenant picker/first-run/session security flows. | auth/onboarding | 4 |
| AUTH-03 | P1 | Session expired, account locked, suspicious activity, logout confirmation, and leave-organization states are listed but need explicit implementation phases. | auth/onboarding | 4 |
| AUTH-02 | P0 | Governance-sensitive actions lack visible step-up auth states. | auth/onboarding | 4 and 8 |
| BILL-01 | P0 | No in-app billing/procurement surfaces. | billing | 5 |
| BILL-02 | P1 | No invoices, receipts, failed payment timeline, trial expiration, cancellation, add-ons, coupons, usage metering, quote/procurement order. | billing | 5 |
| SET-01 | P0 | No workspace admin settings for organization, members, roles, teams, invitations, SSO, SCIM, audit, keys, webhooks, integrations. | workspace settings | 6 |
| SET-02 | P1 | No governance settings for quorum, approvers, escalation, freeze windows, blockers. | workspace settings | 6 |
| SET-03 | P1 | No personal settings beyond appearance controls. | personal settings | 6 |
| DOCS-01 | P1 | Docs prototype is a long page; public docs IA, article view, API explorer, tutorials, search, versions, ADR detail, glossary missing. | docs/support | 7 |
| DOCS-02 | P1 | No grounded docs assistant from ADR/docs/OpenAPI with source citations. | docs/support | 9 |
| SUP-01 | P1 | No help center, ticket forms/list/detail, incident detail, or DSAR request flow. | docs/support | 7 |
| SYS-01 | P1 | Empty/loading/error/401/403/404/500/region/browser/maintenance/offline/license states are not systematic across new surfaces. | cross-cutting | 9 |
| SYS-02 | P1 | Notification center, browser notification setup, and public+app Cmd-K search are incomplete. | cross-cutting | 9 |
| DOM-01 | P1 | Public decision record is partial and not fully productized for transparency, SEO, PDF, and case-study reuse. | domain product | 8 |
| DOM-02 | P1 | Governance inbox and mobile quick approve are missing. | domain product | 8 |
| DOM-03 | P1 | Evidence Fabric source detail and lineage map need standalone board/product route. | domain product | 8 |
| DOM-04 | P2 | Civic data hub, read-only regulator SKU, and EU AI Act transparency snippet are missing. | domain product | 8 |
| BRAND-01 | P2 | Animated glyphs, Atlas Codex, email design system, designed invoices/receipts, social previews, dark landing, motion language examples missing. | brand-as-product | 9 |
| EMAIL-01 | P1 | Transactional email foundation must exist before auth/support/governance flows ship. | brand-as-product | 1 |
| TELEMETRY-01 | P1 | Public RUM, JS error reporting, and synthetic uptime checks are absent from early public launch gates. | QA/performance | 1 |
| PERF-01 | P0 | Public marketing performance budgets and Lighthouse 100 target are not enforced. | QA/performance | 0 and 10 |
| SEO-01 | P1 | Public sitemap, robots, canonical URLs, structured data, and share metadata need explicit launch gates. | QA/performance | 0 and 10 |
| I18N-01 | P1 | Localization is not marketed as a feature and not complete across proposed surfaces. | cross-cutting | 2-10 |

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

Rule: all phases inside a wave are parallel by default. If two phases need the
same ownership fence, registry queue, lockfile, route ID, API contract, i18n
catalog, legal copy approval, or design-token patch, move one phase to the next
wave instead of making an exception inside the wave.

### Wave 0 - Inventory, Decisions, And Contracts

Purpose: make the program measurable and unblock parallel implementation.
Wave 0 phases are mostly C0/C1 contract work and can prepare in parallel even
when they share a broad fence. Their final registry patches still serialize
through the relevant queue. The topology decision becomes C5 only if it creates
a new public app. Wave 4-8 phases may not start implementation until Phase 0.7
classifies their backend contract row as `ready`, `stub-locked`, or `blocked`.

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
  canonical app path, or records a reverse decision, before Phase 1.1 route
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
- Treat the budget as provisional until Phase 0.13 records the sandbox engine
  choice; the final public homepage/sandbox budget must include that decision.

Acceptance:

- A dated decision note exists and links to bundle evidence.
- Public route budget is enforceable by `check:bundle` or a new public budget
  script.
- Implementation branches know where routes live before Wave 1 starts.

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
- Legal pages have owners before Wave 3 route work begins.

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

- No Wave 4+ phase starts implementation without a registry row.
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

#### Phase 0.13 - Sandbox Engine Choice

Primary fence: interactive public demo.

Dependencies: Wave 0.2 draft topology and budget assumptions.

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
- Wave 2 sandbox tasks inherit this decision instead of choosing locally.

Verification:

- sandbox engine decision note;
- bundle/perf evidence;
- fixture or prototype smoke test for chosen path.

### Wave 1 - Foundation Routes, Content Runtime, Email, OG, Telemetry, And Public Shell

Purpose: create the scaffolding that lets teams implement page families without
fighting for routes, i18n, content, email, OG, telemetry, or shell primitives.

#### Phase 1.1 - Public Shell And Navigation

Primary fence: public marketing.

Dependencies: Wave 0.2 and 0.3.

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

#### Phase 1.2 - Content Registry And Localized Copy Pipeline

Primary fence: public marketing.

Dependencies: Wave 0.3 and 0.8.

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

#### Phase 1.3 - Atlas Public Page Primitives

Primary fence: brand-as-product.

Dependencies: Wave 0.1.

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

#### Phase 1.4 - Cookie, Privacy, Analytics, And Consent Foundation

Primary fence: trust/legal/procurement.

Dependencies: Wave 0.5, 0.9, and 0.11.

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

#### Phase 1.5 - Atlas Email Foundation

Primary fence: brand-as-product.

Dependencies: Wave 0.8, Wave 0.9, Wave 1.2.

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

#### Phase 1.6 - OG/Social Preview Generator

Primary fence: brand-as-product.

Dependencies: Wave 0.3, Wave 1.2, Wave 1.3.

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

#### Phase 1.7 - Public RUM, Error Reporting, And Synthetic Checks

Primary fence: QA/performance.

Dependencies: Wave 0.9, 0.10, and 1.4.

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
- Synthetic checks are operational before Wave 2 public route launch.
- Trust/status can link to real public web vitals evidence, not only lab
  Lighthouse runs.

Verification:

- RUM consent tests;
- PII scrubber tests;
- synthetic-check fixture tests;
- public telemetry dashboard smoke.

### Wave 2 - Marketing Site And Interactive Product Surface

Purpose: ship the buyer-facing site and "living product in marketing" layer.
Most phases are C1/C2 and can run in parallel after Wave 1.

#### Phase 2.1 - Homepage Upgrade With Playable Demo Entry

Primary fence: public marketing.

Dependencies: Wave 0.10, Wave 1.1, 1.3, 1.6, and 1.7.

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
- Public homepage remains within Wave 0 performance budget.

Verification:

- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run test:visual`
- `corepack pnpm --dir policy-engine/apps/runtime-dashboard run lighthouse:ci`
- bundle budget check.

#### Phase 2.2 - Persona Solutions And Use Cases

Primary fence: public marketing.

Dependencies: Wave 1.2 and 1.6.

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

#### Phase 2.3 - Customers And Case Studies

Primary fence: public marketing.

Dependencies: Wave 1.2, 1.6, Wave 2.6 public sandbox fixtures.

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

#### Phase 2.4 - Methodology And Science Surface

Primary fence: public marketing.

Dependencies: Wave 1.2, docs evidence map.

Scope:

- Create methodology/science landing and longread pages:
  - causal estimates;
  - identifiability;
  - transportability;
  - partial identification/bounds;
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

#### Phase 2.5 - Public Sandbox And Playable Demo

Primary fence: interactive public demo.

Dependencies: Wave 0.4, 0.7, 0.13, Wave 1.3.

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
- Implement the sandbox using the engine strategy selected in Phase 0.13.

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

#### Phase 2.6 - Decision Packet Sample

Primary fence: interactive public demo.

Dependencies: existing `PublicDecisionViewerPage`, Wave 0.4, 0.7, and 1.6.

Scope:

- Productize a public anonymized decision packet:
  - readable public URL;
  - summary;
  - argument map;
  - evidence/provenance;
  - governance pass state;
  - uncertainty/caveats;
  - PDF/download action;
  - print layout with Instrument Serif pull quote / decision rationale block;
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

#### Phase 2.7 - ROI/TCO Calculator And Live Counters

Primary fence: interactive public demo.

Dependencies: Wave 0.4, 0.9, 0.12, Wave 1.4.

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

#### Phase 2.8 - Service, Conversion, Careers, And Partner Routes

Primary fence: public marketing.

Dependencies: Wave 0.3, 0.4, 0.8, 0.9, 0.12, Wave 1.4.

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

#### Phase 2.9 - Public Governance-On-The-Go Demo

Primary fence: interactive public demo.

Dependencies: Wave 0.7, 0.9, 0.13, Wave 1.3, Wave 2.6.

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
- Keep full production governance inbox and mobile quick approve in Phase 8.2.

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

### Wave 3 - Trust, Legal, Status, Roadmap, And Procurement

Purpose: build the trust pack as a product surface and make procurement a
first-class journey.

#### Phase 3.1 - Trust Center

Primary fence: trust/legal/procurement.

Dependencies: Wave 0.5, 0.11, Wave 1.3.

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

#### Phase 3.2 - Status, Changelog, Release Notes, And Roadmap

Primary fence: trust/status.

Dependencies: Wave 0.4, 0.9, 0.10, 0.12.

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

#### Phase 3.3 - Legal Route Family

Primary fence: trust/legal/procurement.

Dependencies: Wave 0.5, 0.11, legal/compliance queue.

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

#### Phase 3.4 - Procurement Playbook And Tender Pack

Primary fence: trust/legal/procurement.

Dependencies: Wave 0.5, 0.11, Wave 2.7.

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

#### Phase 3.5 - Public Quote Builder Shell

Primary fence: trust/legal/procurement.

Dependencies: Wave 0.4, 0.7, 0.11, 0.12, Wave 3.4.

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
- It can hand off to in-app billing/procurement order in Wave 5.

Verification:

- pricing formula tests;
- PDF snapshot;
- form validation tests.

### Wave 4 - Auth, Onboarding, Tenant Selection, And Session Safety

Purpose: expand the current minimal login route into a full identity journey.
Auth phases can prepare in parallel by flow but serialize API/session state.
No Wave 4 implementation starts unless Phase 0.7 marks the relevant contract
row as `ready` or `stub-locked`.

#### Phase 4.1 - Auth Flow State Machine

Primary fence: auth/onboarding.

Dependencies: Wave 0.4 and 0.7.

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

#### Phase 4.2 - Recovery, Verification, Magic Link

Primary fence: auth/onboarding.

Dependencies: Wave 4.1.

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

#### Phase 4.3 - MFA And Recovery Codes

Primary fence: auth/onboarding.

Dependencies: Wave 4.1.

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

#### Phase 4.4 - SSO, Government Identity, Invites, Tenant Picker

Primary fence: auth/onboarding.

Dependencies: Wave 0.7 and Wave 4.1.

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

#### Phase 4.5 - First-Run Onboarding Wizard

Primary fence: auth/onboarding.

Dependencies: Wave 4.1, Wave 2 sandbox content.

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

#### Phase 4.6 - Session, Risk, Logout, And Organization Exit States

Primary fence: auth/onboarding.

Dependencies: Wave 4.1, Wave 6.6 danger-zone policy draft.

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

### Wave 5 - Billing, Procurement Orders, Usage, And Subscription Lifecycle

Purpose: make revenue and government procurement usable inside the product.
No Wave 5 implementation starts unless Phase 0.7 locks the relevant billing,
quote, usage, invoice, and procurement contracts.

#### Phase 5.1 - Billing Contract And Navigation

Primary fence: billing/procurement-in-app.

Dependencies: Wave 0.4, 0.7, 0.11, 0.12, Wave 3.5.

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

#### Phase 5.2 - Plan Picker, Add-Ons, Trial Lifecycle

Primary fence: billing/procurement-in-app.

Dependencies: Wave 5.1.

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

#### Phase 5.3 - Payment Methods, Billing Address, VAT/EDRPOU

Primary fence: billing/procurement-in-app.

Dependencies: Wave 5.1.

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

#### Phase 5.4 - Invoices, Receipts, Failed Payment, Dunning

Primary fence: billing/procurement-in-app.

Dependencies: Wave 5.1, brand invoice artifact work.

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

#### Phase 5.5 - Cancel, Downgrade, Pause, Coupons, Usage

Primary fence: billing/procurement-in-app.

Dependencies: Wave 5.1.

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

### Wave 6 - Workspace And Personal Settings

Purpose: create the admin and personal configuration layer missing from the kit.
No Wave 6 implementation starts unless Phase 0.7 locks the relevant settings,
audit, SSO, SCIM, webhook, integration, and governance contracts.

#### Phase 6.1 - Settings Route Family And IA

Primary fence: workspace settings.

Dependencies: Wave 0.6, Wave 5.1 for billing links.

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

#### Phase 6.2 - Workspace General, Members, Roles, Teams, Invitations

Primary fence: workspace settings.

Dependencies: Wave 6.1.

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

#### Phase 6.3 - SSO, SCIM, Audit, API Keys, Webhooks

Primary fence: workspace settings.

Dependencies: Wave 6.1, Wave 4.4.

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

#### Phase 6.4 - Integrations, Notifications, Residency, Retention, Branding

Primary fence: workspace settings.

Dependencies: Wave 6.1.

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

#### Phase 6.5 - Governance Settings

Primary fence: workspace settings.

Dependencies: Wave 0.7 and Wave 6.1.

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

#### Phase 6.6 - Personal Profile, Security, Preferences, Danger Zone

Primary fence: personal settings.

Dependencies: Wave 6.1, Wave 4 auth flows.

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

### Wave 7 - Public Docs, Support, Content Engine, And Community

Purpose: turn docs/support/content from scattered artifacts into a client-facing
engine. Support, ticket, DSAR, FOI, and docs-assistant surfaces depend on
Phase 0.7 contract rows and Phase 0.12 destination health where forms are
involved.

#### Phase 7.1 - Public Docs IA And Article View

Primary fence: docs/support.

Dependencies: Wave 1.2, docs nav queue.

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

#### Phase 7.2 - API Reference, SDK/CLI Quickstarts, Tutorials

Primary fence: docs/support.

Dependencies: Wave 0.4.

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

#### Phase 7.3 - Search, Cmd-K Public Provider, ADR Index, Glossary

Primary fence: docs/support.

Dependencies: Wave 7.1, Wave 9 Cmd-K foundation if started.

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

#### Phase 7.4 - Help Center, Tickets, Incident Detail, DSAR, And FOI

Primary fence: docs/support.

Dependencies: Wave 0.4, 0.7, 0.11, 0.12, Wave 3.2.

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

#### Phase 7.5 - Editorial Content Engine And Community

Primary fence: public marketing.

Dependencies: Wave 1.2.

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

### Wave 8 - PolicyOS Domain Differentiators

Purpose: implement the product surfaces that make PolicyOS visibly different.
No Wave 8 implementation starts unless Phase 0.7 locks the relevant public
decision, governance, quick-approve, source-lineage, civic-data, and
transparency contracts.

#### Phase 8.1 - Public Decision Record Productization

Primary fence: domain product.

Dependencies: Wave 2.6, Wave 3 trust/status links.

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

#### Phase 8.2 - Governance Inbox And Mobile Quick Approve

Primary fence: domain product.

Dependencies: Wave 0.7, Wave 6.5, Wave 4 step-up auth.

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

#### Phase 8.3 - Evidence Fabric Source Detail And Lineage Map

Primary fence: domain product.

Dependencies: existing Evidence Fabric, Wave 0.4 and 0.7.

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

#### Phase 8.4 - Civic Data Hub And Regulator Read-Only SKU

Primary fence: domain product.

Dependencies: Wave 0.7, 0.11, Wave 3 trust/legal, Wave 5 billing plan model.

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

#### Phase 8.5 - EU AI Act Transparency And Conformity Readiness

Primary fence: domain product.

Dependencies: Wave 0.11, Wave 3 compliance matrix, Wave 8.1.

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

### Wave 9 - Brand-As-Product And Cross-Cutting System Layer

Purpose: polish the surfaces users notice as premium and reliable.

#### Phase 9.1 - Animated Glyphs And Motion Language

Primary fence: brand-as-product.

Dependencies: Wave 1.3.

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

#### Phase 9.2 - Advanced Email, Invoice, Receipt, And Social Artifacts

Primary fence: brand-as-product.

Dependencies: Wave 1.5, Wave 1.6, Wave 5 invoice routes, Wave 7 content engine.

Scope:

- Extend the Phase 1.5 email foundation for:
  - invoice;
  - receipt;
  - failed payment;
  - public decision published;
  - weekly briefing;
  - annual report release;
  - longread/resource nurture.
- Build marketing email and weekly briefing templates.
- Build designed invoice/receipt artifact style.
- Extend the Phase 1.6 OG generator with custom OG/Twitter/LinkedIn artwork per
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

#### Phase 9.3 - Global Empty, Loading, Error, Offline, License States

Primary fence: platform/cross-cutting.

Dependencies: Wave 0.6.

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

#### Phase 9.4 - Notification Center And Global Cmd-K

Primary fence: platform/cross-cutting.

Dependencies: route/surface registry, Wave 7 search.

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

#### Phase 9.5 - Atlas Codex And Localization-As-Feature

Primary fence: brand-as-product.

Dependencies: Wave 1.2, Wave 9.1.

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

#### Phase 9.6 - Grounded Docs Assistant

Primary fence: docs/support.

Dependencies: Wave 0.7, Wave 7 docs/search.

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

### Wave 10 - Hardening, Performance, Launch Gates, And Closeout

Purpose: turn the implementation into a launchable, measurable, maintainable
surface set. Wave 10 tightens and proves the ratchets introduced in Phase 0.10;
it must not be the first moment security, privacy, route, content, a11y, or
bundle gates run.

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

The table below is the intended execution shape after Wave 0. "Parallel" means
branches can be active simultaneously if they keep to their ownership fence and
send shared files through queues.

| Wave | Parallel lanes | Serialized gates |
| --- | --- | --- |
| 0 | zip ledger, content model, API inventory, legal evidence map, state matrix, backend contract lock, content ownership, analytics/attribution, continuous gates, jurisdiction, lead destination, sandbox engine | public topology decision if app split is required; final registry patches per queue |
| 1 | public shell, content registry, primitives, cookie/analytics, email foundation, OG generator, public RUM/error/synthetic checks | public routes, i18n, design token patches, analytics/experiments queue |
| 2 | homepage, personas, cases, methodology, sandbox, packet sample, calculator, service/conversion/careers/partners, mobile quick-approve preview | route registration, sandbox fixtures, public counters API, form intake contracts |
| 3 | trust center, status/changelog/roadmap, legal, procurement playbook, quote shell | legal/compliance copy, quote pricing model |
| 4 | recovery/verification, MFA, SSO/invites/tenant, onboarding, session/risk/logout/organization-exit states | auth state/API contract, session provider changes |
| 5 | plan picker, payment methods, invoices/receipts, usage/cancel/coupons | billing API/OpenAPI, invoice legal artifact |
| 6 | settings IA, members/RBAC, SSO/SCIM/audit/keys/webhooks, integrations/residency, governance settings, personal settings | workspace registry, permission registry, audit contract |
| 7 | docs article/API/tutorial/search, support tickets/DSAR, content engine/community | docs nav/search index, public Cmd-K provider |
| 8 | public decision, governance inbox/mobile approve, source lineage, civic hub/regulator SKU, transparency snippet | governance API, public decision signing, legal/privacy |
| 9 | animated glyphs, email/social/invoice artifacts, global states, notifications/Cmd-K, Atlas Codex, docs assistant | design tokens, notification source, assistant grounding contract |
| 10 | route/sitemap, a11y/visual/print, performance, security/privacy, closeout | release/deployment gates |

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

## Open Decisions

These decisions must be made in Wave 0 or early Wave 1:

| Decision | Default | Required evidence |
| --- | --- | --- |
| Single app vs separate public app | Single app with aggressive lazy splitting | Bundle and Lighthouse evidence for public routes |
| Sandbox engine | Precomputed fixtures, escalate to WASM only with bundle/perf evidence | Wave 0.13 decision note |
| Jurisdictional scope | UA + EU in scope, RF out of scope until legal review | Wave 0.11 jurisdiction registry |
| CRM/lead destination | Single declared system per form, health-checked | Wave 0.12 destination registry |
| Email kit foundation | Atlas-tokenized transactional templates from Wave 1 | Wave 1.5 snapshots and provider owner |
| Provider lock-in / portability strategy | Provider-neutral email templates with adapter boundary for Postmark, Resend, and SES until provider selection is signed | Wave 1.5 portability note |
| Mobile quick-approve visibility | Public preview from Wave 2 demo set | Wave 2.9 public demo evidence |
| Public telemetry | Consent-aware RUM + error tracking + synthetic checks from Wave 1 | Wave 1.7 telemetry evidence |
| Atlas Codex topology | Publication layer over Storybook/design docs, single source | Wave 9.5 ADR |
| AI Act readiness | Conformity assessment posture in trust center | Wave 8.5 evidence package |
| Public roadmap slip-comms policy | Public template + channel before voting flag flips | Wave 3.2 roadmap policy |
| Public counters source | Fixture-labeled until telemetry contract exists | API/telemetry contract and privacy review |
| Trust center claim level | Publish only evidence-mapped claims | Legal/security evidence map |
| Quote builder binding status | Non-binding draft quote until legal approval | Legal/procurement review |
| Government identity wording | "Ready/planned/supported" only when evidence exists | Integration contracts and legal copy |
| Public roadmap voting | Feature-flagged after abuse/spam moderation decision | Product/security review |
| Docs assistant launch | Source-grounded only, no generic model claims | Grounding tests and source policy |

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
