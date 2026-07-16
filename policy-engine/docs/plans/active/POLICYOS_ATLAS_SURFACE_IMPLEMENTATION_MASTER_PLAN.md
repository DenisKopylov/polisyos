---
title: PolicyOS Atlas Surface & Frontend Implementation Master Plan
status: revised - Revision 2 re-derived against the GY-N closure; Phase A may start now; Phase B+ activates on GY-N10 merge
owner: team-design
runtime_co_owner: team-architecture  # producers, bridges, and authz enforcement land in runtime code; named per task plan
created: 2026-06-10
revised: 2026-07-16 (Revision 2 - re-derived against the GY-N campaign closure: GY input contract, Cycle Board hero, new slices DS15-DS18, re-stated activation and public gates)
last_reviewed: 2026-07-16
surface_constitution: ../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
atlas_source_of_truth: ../../brand/ATLAS_SOURCE_OF_TRUTH.md
organizing_constitution: ../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
source_design_doc: ../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
governed_inventory: ../../../architecture/policy_design_case/cluster_ownership_map.toml
capability_ratchet: ../../../architecture/policy_design_case/capability_reality_report.json
failure_patterns: ../../reference/policy-design-case-failure-patterns.md
workspace_contract: ../../reference/frontend/workspace-contract.md
upstream_plans:
  - ./layer3-slices/GY-engine-subordination.md  # THE active Layer-3 execution plan (Rev 17): supplies the capstone, value gate, ledgers, censuses, acquisition (N13a/b), confidence ledger (N11), epochs (N12), O-block agent
  - ./POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md  # historical G-naming retained in place; DS0 records no execution authority
supersedes_as_execution_master:
  - ./POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md  # DS0-retained material source for DS11-DS13; no execution authority
  - ../archive/FRONTEND_SOTA_PLAN.md            # archived by DS0; active path is a compatibility stub
  - ../archive/DESIGN_BEST_IN_CLASS_PLAN.md     # archived by DS0; active path is a compatibility stub
evidence:
  atlas_v15_archive:
    path: ../../../design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip
    sha256: 28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969
    admission_status: implemented_but_not_orchestrated
scope:
  - design-source-of-truth-admission
  - status-grammar-and-enforcement-waist
  - backend-producers-and-bridges      # in-slice runtime exporters/endpoints; surfaces are full-stack verticals
  - authz-audience-subordination       # PUBLIC/REVIEWER/EXPERT/MACHINE as enforced access classes
  - offline-cache-staleness-discipline
  - proving-ground-board
  - runtime-workspace-deepening
  - capability-discovery-surfaces
  - machine-twins-in-slice
  - trust-docs-posture
  - public-accountability-gated
  - bounded-agent-surface-gated
  - accessibility-performance-evidence-infrastructure
---

# PolicyOS Atlas Surface & Frontend Implementation Master Plan

This plan executes the
[surface constitution](../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md):
it subordinates the frontend, design system, and public surfaces to the runtime
authority discipline, closes `surface_missing` capability links, and admits the
Atlas v15 archive as a governed substrate through the same admission logic the
runtime uses for engines. Atlas renders the authority system; it never produces
authority. DS0 source ownership and governing decisions live once in the
[Atlas source-of-truth record](../../brand/ATLAS_SOURCE_OF_TRUTH.md).

**A surface here is a full-stack vertical, not a React layer.** Every slice
carries its capability from the typed runtime contract through the producer
(runtime exporter or HTTP endpoint), the OpenAPI schema, the generated client,
the UI, and the evidence — because most of the artifacts this plan renders
(capability reality report, cluster map, conversion records, adapter registry)
exist today only as repository files with **no HTTP producer**. Building those
producers and bridges is in-slice work, never an external dependency to wait
on.

## Read This Before Anything Else

**Revision 2 (2026-07-16) — this IS the re-derivation.** The Layer-3 closeout
the original draft waited for has happened, under GY naming: the **GY-N
campaign** (docs/plans/active/layer3-slices/GY-engine-subordination.md, Rev 17)
closed GY-N4–N10 — the full plain-language → generate → ground → simulate →
value → promote cycle is contract-generic across domains, with a frozen
**depth-N universality capstone** (three plain-language runs, three honest
`acquisition_required` terminals with structurally distinct evidence classes),
a 55/390-method value gate, a disposition ledger, two censuses, and the CGF
grounding firewall. The measured system truth: **the machinery is universal and
honest; the substrate is thin; every gap routes to a typed, costed acquisition
plan.** The GY plan's next wave (N13a/N13b acquisition execution → N11
confidence ledger → N12 epochs → Phase-6 learning loop) is exactly the future
data this plan's later surfaces render.

**Activation gate (re-stated).**

- **Phase A (DS0–DS2) may start NOW** — its inputs (the v15 archive, the v4/v7
  brand docs, the live route/feature/authz/cache inventory) are
  GY-independent, and Phase A does not touch the GY worktree.
- **Phase B+ activates when the GY-N10 branch merges to main** (the capstone
  and its sibling artifacts become main-tree data). No further re-derivation
  ceremony is required — this revision replaces it; if the final N10 audit
  materially changes the capstone vocabulary, amend the Input Contract before
  DS3, not during it.
- Later slices carry **explicit GY gates** (N13a, N13b, N11, N12, first
  governed promotion, Phase-6 agent) stated per slice and in the start-now
  ladder below.

**Execution granularity (roadmap vs task plans).** This document is the
**roadmap**: strategy, sequencing, doctrine, the dependency DAG, and the
per-slice closure contract. It is **not** the coding spec. When a slice reaches
the front of the DAG, expand its closure contract into a separate executable
task plan under `docs/plans/active/atlas-slices/DS{N}-*.md` — exact files, typed
contracts, exact test names (negatives written red-first), exact validation
commands, **and the named backend deliverables with their runtime co-owner**.
Task plans are written just-in-time; shared machinery is defined once in
DS0/DS3/DS4 and referenced.

**Sizing principle.** Slices target comparable effort: one task plan, one
closure contract, one review each. If execution reveals a disproportionate
slice, the roadmap is amended and slices are re-cut with continuous numbering —
never suffixed (`DS7a`) and never silently inflated.

**Ownership.** `team-design` owns the plan and the surfaces; producers,
bridges, schema changes, and authz enforcement land in runtime code and are
co-owned with `team-architecture`. A task plan that needs a producer or
endpoint **names it as its own deliverable** with both owners — "blocked on
backend" is not a valid slice state in this plan.

**Honesty defaults.** No slice claims a surface is implemented without the full
capability chain. Fixture data is typed and visually marked `fixture_only` and
never occupies an authority slot. Cached data renders with its staleness.
Public gates are constitutional, not schedule-driven.

## Input Contract — What This Plan Consumes From The GY Campaign (Revision 2)

All GY artifacts are frozen JSON contracts under
`architecture/policy_design_case/` with **recomputing validators, byte-stable
canonical writers, corrupt-drift lanes, and source-flip harnesses** — the
strongest producer substrate a surface plan has ever had here. The HTTP
producers are thin projections of already-verified artifacts, never new logic.

| Input | Source artifact (GY name) | HTTP producer today? | Feeds | Status (2026-07-16) |
| --- | --- | --- | --- | --- |
| Typed terminal + evidence vocabulary: `SearchTerminalState`, evidence classes (`owner_acquisition_route` / `estimand_binding_refusal` / `owner_data_gap`), decision grades, CGF dispositions (`bound`/`shadow_bound`/`candidate_unbound`), acquisition strategies (ADR-0166) | core contracts + the capstone validator's structural recomputation (`_domain_evidence_kind` pattern) | partially (runtime contracts) | DS4 grammar binding; every surface | **live** — frozen + recomputed, not pinned (GY §3.5.10) |
| Depth-N universality capstone: three plain-language runs, per-stage traces, embedded proof recordings, per-domain terminal distributions | `layer3_gy_depth_n_universality_contract.json` | **no — built in DS3** | DS7 Cycle Board hero rows; DS8 drill-down | live on N10 merge (final audit in flight) |
| Value gate: 390/55 method denominator, advisor selection receipts, `ValueOuterSet` (set-valued, `unknown`/incomparable), six-family projections, transport receipts | `layer3_gy_value_gate_contract.json` | **no — built in DS3** | DS16 value grammar; DS7 columns | live on N10 merge |
| Disposition ledger + engine census + Fork-B CG1/L2 census (13,092 relations, 0 admissible positives) | `layer3_gy_generation_cycle_disposition_ledger.json`; census artifacts | **no — built in DS3** | DS7 columns; DS10 discovery; honesty copy | live on N10 merge |
| Acquisition routes with costed plans (N7 planner reports: strategy, cost, VOI, requirement gap) | capstone terminals + `layer3_gy_acquisition_contract` artifacts | **no — built in DS3/DS15** | DS15 refusal-with-a-path; DS7 route column | live on N10 merge |
| Acquisition-layer census: connector scorecard, liveness map, catalog↔runtime metric resolution, D2 growth backlog (VOI-ranked) | GY-N13a census artifact | **no — built in DS15** | DS15 growth surfaces | **pending GY-N13a** |
| World growth: epoch-stamped overlay store, admission passports, quarantine, re-entry traces, derivation certificates + basis vocabulary (GY §3.5.12) | GY-N13b artifacts | **no — built in DS15/DS16** | DS15 live loop; DS16 derived-data provenance | **pending GY-N13b** |
| Confidence ledger: δ-budget, risk-spend per obligation class × instrument, refusal/acquisition instruments as first-class rows | GY-N11 ledger artifact | **no — built in DS17** | DS17 | **pending GY-N11** |
| Epochs: stale certificates, `revalidation_required`, revision triggers, OpenWorldRisk | GY-N12 artifacts | **no — built in DS18** | DS18 chrome; every time-bearing surface | **pending GY-N12** |
| 13-case proving ground (legacy honest signal; still real) | proving-ground artifacts | **no — built in DS3** | DS7 legacy rows | live |
| Bounded-agent contract + orchestration-choice audit ledger | Phase-6 O-block contracts | **no — built in DS14** | DS14 | **pending Phase 6** |
| Updated cluster ownership map (`surface_missing` inventory) | `cluster_ownership_map.toml` | **no — built in DS3** | backlog generator #1; closure targets | live; refresh at N10 merge |

The "no HTTP producer" column is the honest bridge debt this plan owns. Two
binding rules inherited from the GY plan apply to every producer built here:
**§3.5.10 recompute-not-pin** (surface payloads carry recomputed structural
properties, never pinned terminal labels) and **§3.5.11 projection-scoped
provenance** (a surface producer binds to the narrowest upstream projection
hash, so GY artifact churn does not ripple through every endpoint).

## Code-Grounded Technical State (Snapshot 2026-06-10)

A deep pass over the app, the client package, and the runtime HTTP layer was
made before activation. The expected pattern — rich content, weak
orchestration — holds, but in a sharper form: **the components are excellent
and the semantics are parallel.** The dashboard is a large, tested, accessible
system that grew its own semantic universe disconnected from the runtime
authority machinery. The dominant work of this plan is therefore **rebinding
and subordination, not greenfield building.**

| Area | What exists (anchors) | What is missing / divergent | Feeds |
| --- | --- | --- | --- |
| Scale & quality infra | 908 TS/TSX files, ~137k LOC, 230 test files; Storybook configured; 44 stories; Playwright e2e (`e2e/a11y`, `e2e/journeys`, **visual spec + snapshots**); per-component `.a11y.test.tsx` across ~40 `shared/ui` components; 388 `aria-` usages | no evidence storage convention; visual/a11y coverage not tied to the maturity bar | DS4, DS6 |
| Typed waist | `openapi-fetch` `createClient<paths>` over generated types with auth-aware fetch and API events (`src/api/client.ts`); 4.4k-line generated TS client; 89 OpenAPI operations (runs, debug, fabric, lineage, analysis, mobility, control) | ~10 files hand-fetch outside `src/api/` (collaboration hooks, lex graph page, auth/prefetch/network); **no endpoints** for capability report, cluster map, conversions, adapter registry, public records | DS3, DS5 |
| Status semantics | ≥8 UI-local status enums; `DisputeStatus` defined three times with diverging values (`runs/domain/disputes.ts`, `shared/ui/quantity/quantity.types.ts`, `shared/ui/trust-view/trust-glyphs.ts`) | **zero authority-lattice statuses anywhere in the app** — the UI predates Layer 2/3 entirely; P04 live | DS4, DS5 |
| Evidence ontology | `quantity.types.ts`: `VerificationMetadata` (hash, status, freshness, dispute), bitemporal `TemporalRef`, `LineageRef`, `QuantityClass` (`decision`/`telemetry`/`layout`/`debug`); `ProvenanceStrip`, `trust-view` glyphs, `temporal`, `counterfactual`, `authored-text` families; compounds incl. `DecisionCard`, `EvidenceChain`, `ExplainabilityCard`, `AttributionWaterfall`, `DataFreshnessBadge` | an entire **parallel evidence vocabulary**, UI-local, not bound to runtime contracts | DS4 |
| Publication | `publicationPacket.ts` (~1.4k lines): Toulmin argument maps, projection fail-closed client logic, decision packet **built and "signed" in the browser** (`signatureForPayload` = salted `stableHash`), **verified client-side from the URL payload** | the "Verified" badge is decorative — forgeable by construction; no server-side signing, verification, or public-records producer | DS1, DS12 |
| Authz | `/api/v1/auth/me` with role→permission map (`http/routes/auth.py`); client `PERMISSION_KEYS` + workspace/tab gating (`app/authz/permissions.ts`); tenant check on the review path | **fixture identity fallback** (`allow_fixture_identity`); permission vocabulary duplicated server+client; **no per-permission deny found on mutating endpoints** (e.g. production-approval); no step-up auth | DS5, DS9 |
| Offline | Workbox precache of static assets only — the SW **denylists `/api/`** from caching; `OfflineQueueProvider` + background `sync` flush; **`useQueuedPromotionDecision` queues evidence promotion approve/reject offline — a live authority action in the offline queue** | freshness rendering; revalidation protocol; authority-action queue exclusion | DS1, DS5 |
| i18n | `en`/`uk`/`ru` catalogs have structural parity; DS0 measured 2,449 string leaves each, while 80.16% of `ru` equals English; runtime capability contracts admit `en`/`uk` | D4 recommends `uk` primary + `en` baseline + frozen legacy `ru` UI continuity, but remains `pending_owner_ratification`; DS12 cannot publish locale claims before ratification | DS5, DS12 |
| Tokens / design system | `shared/ui/tokens/designTokens.ts` + `AtlasV4Reference.stories` — a living, coded v4; theming `light`/`dark`/`system` + density preferences | DS0 selects future one-way DTCG generation and sunsets hand-maintained TS authority; v15 values/modes remain unadmitted until DS2 and no migration occurs before DS4 | DS2, DS4 |
| Agent surface | `features/clerk` — a full NL chat (streaming, history, structured responses, `AIDiffView`) over `POST /control/runs/nl`; **`clerk` is one of two app-level interface modes** (`InterfaceMode = clerk \| analyst`, flag- and permission-gated) — the chat-first posture, not a side feature | candidate-clothing discipline; G6 contracts; orchestration-choice audit | DS1, DS14 |
| Realtime & off-contract endpoints | dual client transport (`websocketTransport.ts`, `sseTransport.ts`); server WS hub `/api/v1/review/live`; SSE `GET /runs/live` and `GET /runs/{id}/live` — both **`include_in_schema=False`**, deliberately hidden from the contract | collaboration REST `/api/v1/collaboration/*` called by the UI has **no server route found** (vite only proxies to the runtime) — a phantom API; off-contract channels have no typed coverage | DS1, DS3 |
| Feature flags & shadow shipping | 12 manifest-driven flags (all observed defaults `true`) plus the separate `/auth/me.enableReviewCollaboration` vocabulary; four declared keys have no consumer | DS0 records owner/intent/sunset and one-registry direction; DS5 must create the machine registry, reject unknown keys, separate authz, and wire-or-retire the four `consumer_missing` gates | DS1, DS5 |
| Observability & audit | Sentry wired (`@sentry/react` + vite plugin, `shared/telemetry/sentry.ts`); server-side **append-only access audit** (`http/access_audit.py`), compliance export/retention, CSRF protection | public-route telemetry posture vs the no-tracker bar; review-effectiveness telemetry not yet drawing on the audit trail | DS6, DS9, DS12 |
| Discovery seeds & machine exports | `GET /control/capabilities` (live endpoint), `control/data/catalog/search`, lineage exports (`openlineage`, `prov`), artifact packet export/render, decision-validity endpoints | the capability manifest is a **hand-maintained `CapabilityFeatureInfo` enumeration** in `services/control/capabilities.py` — a live Rule-12 violation; exports cover lineage/packets, not the Layer 3 artifacts | DS3, DS10 |
| Non-web surface artifacts | `packages/cli` styleguide plus email/print/CLI/bureaucratic/glyph/motion/contrast specs | DS0 assigns them to DS2/DS3/DS4/DS6/DS8; email alone is explicitly `surface_out_of_scope` until a typed notification/privacy/delivery slice exists | DS2, DS3, DS4, DS6, DS8 |

Three consequences are folded into the slices below:

1. **DS4 is a rebinding slice, not a component-building slice.** The
   evidence-bearing primitives largely exist; what they lack is binding to the
   authority lattice and the retirement of UI-local vocabularies.
2. **DS2 adjudicates two living systems, not one archive.** The repo already
   runs a coded v4 (tokens + ~40 components with a11y evidence); v15 admission
   is a migration between two real systems, not an import into a void.
3. **DS12 replaces a decorative mechanism, not a missing one.** Client-side
   "signing" is a useful UX prototype and a live overclaim risk at once; the
   slice's first negative is that a forged packet must stop rendering as
   "Verified".

## Backlog Generators (where slice scope comes from)

Slice deliverables are **derived, not invented**, from three machine-readable
sources:

1. **`surface_missing` / `implemented_but_not_orchestrated` links** in the
   cluster ownership map — the runtime's debt to the glass.
2. **DS0–DS2 adoption-ledger verdicts** — the design system's debt to the
   repo: which v15 components/tokens/patterns are admitted, deferred, or
   rejected.
3. **The `[to build]` enforcement column** of the surface constitution's
   Derived Surface Laws — every named-but-missing lint, test, or registry is a
   first-class deliverable of a named slice.

A deliverable that traces to none of the three generators is out of scope
(anti-P13: contract gravity well). The traceability is recorded per slice.

## Execution Doctrine (every slice obeys these)

- **Vertical and full-stack, with a full closure contract.** Each slice carries
  surfaces end-to-end and must satisfy: **producer** (runtime exporter/endpoint
  — built in-slice when missing) → **persisted artifact** → **bridge** (OpenAPI
  schema → `packages/runtime-api-client` regeneration) → **consumer**
  (route/component) → **verification** (unit, contract, browser, visual,
  accessibility — matched to risk) → **surface**
  (PUBLIC/REVIEWER/EXPERT/MACHINE or explicit out-of-scope) → **negative +
  semantic test**. A missing link is named precisely, never rounded up — and if
  the missing link is a producer or bridge, building it is this slice's work.
- **The MACHINE twin ships in-slice.** Every surface slice delivers its own
  MACHINE projection (typed export, replayable packet, stable URL) using the
  shared export machinery from DS3, with a surface↔twin parity test. A surface
  without its twin does not close — there is no separate "twins later" slice.
- **Audience is access control, not styling.** PUBLIC/REVIEWER/EXPERT/MACHINE
  map to authz permission classes through one define-once mapping (DS5),
  enforced **server-side**. The UI may hide what the server denies; it never
  substitutes for the denial. Rendering an audience without enforcing it is
  laundering.
- **Cached and offline state is honest state.** Anything served from a cache,
  service worker, or offline store renders with its as-of/staleness posture.
  Authority-bearing actions (approval, promotion, publication, revocation)
  never execute from an offline queue without explicit revalidation against
  live state.
- **Laws traceability.** Each slice names the surface-constitution laws (1–12)
  it operationalizes and the `[to build]` enforcement it lands.
- **Pattern-pass negatives.** Each slice carries laundering negatives with
  exact register IDs (P01, P03, P04, P05, P06, P10, P13, P15, P25, P26 as
  applicable), written red-first in the task plan.
- **Real data or marked fixture.** `fixture_only` data is typed, visually
  marked, lint-enforced, and barred from authority slots. Demo data presented
  as live state is P05 at the surface level.
- **Define once, reference.** Grammar, registries, ledgers, mappings, and lints
  live in DS0/DS3/DS4/DS5 and are referenced; no slice re-derives vocabulary
  (anti-P13, constitution Rule 10).
- **Strangle, don't fork.** Changes land in `apps/runtime-dashboard`. A
  parallel rebuild is P06 in code form.
- **The ledger is updated at closure, and CI checks it.** Every slice closure
  updates the surface readiness ledger; a CI validator (DS6) compares ledger
  claims against the tests and evidence that actually exist — the surface
  analogue of the Layer 3 readiness validator.
- **Accessibility evidence is proportional and real.** Archive lint never
  counts as evidence (P10). `stable` components need WCAG 2.2 AA intent, APG
  behavior for custom widgets, browser + keyboard evidence, and manual
  assistive-technology evidence for high-risk patterns.
- **Engineering quality is not optional.** Generated typed client only;
  established libraries over hand-rolled equivalents; performance budgets on
  public routes; deterministic visual regression; fail-closed error rendering.
- **"Not yet" is mandatory.** Every slice states what it explicitly does not
  claim, in the slice plan and in the surface readiness ledger.

## Controlled Vocabulary (references, then extends)

Authority statuses, interaction states, and surface states are defined in the
surface constitution's Status Grammar and the Layer 3 controlled vocabulary.
This plan adds only the values below. DS0 encodes them in the
[adoption-ledger schema](../../../architecture/atlas_surfaces/adoption-ledger.schema.json)
and
[surface-readiness schema](../../../architecture/atlas_surfaces/surface-readiness-ledger.schema.json);
the table remains the vocabulary source and later slices reference the schemas
rather than minting local values.

| Kind | Values | Rule |
| --- | --- | --- |
| Surface readiness | `contract_only`, `producer_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `surface_missing`, `semantic_test_missing`, `implemented` | reuse capability-reality-bar labels; never invent UI-only readiness states |
| Data provenance posture | `live`, `replay`, `fixture_only` | `fixture_only` is visually marked and lint-enforced; never in authority slots |
| Freshness posture | `live`, `cached(as_of)`, `stale`, `offline_queued` | orthogonal to provenance; rendered wherever data is decision-bearing; `offline_queued` never applies to authority-bearing actions |
| Component maturity | `experimental`, `beta`, `stable`, `deprecated` | from the surface constitution's component bar |
| Adoption verdict (DS2) | `admit_as_is`, `admit_after_refactor`, `wrap_then_strangle`, `reject`, `defer` | reuse G0 triage semantics for design artifacts; `defer` is the default for components without a consuming surface in this DAG |
| Surface audience | `PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE` | enforced access classes mapped to authz permissions (DS5 mapping); every surface declares its audiences; the server denies, the UI reflects |

## Surface Proving Ground

Two pinned proving grounds, mirroring how the runtime proves mechanisms on
`ua-msme-affordable-loans-2022` before scaling:

1. **The Cycle Board itself (DS7).** The board must render the GY-N10
   capstone's three plain-language domains (first-vertical, education,
   unseen/no-pack — three honest `acquisition_required` terminals with
   structurally distinct evidence classes) plus Layer 3's 13 canonical legacy
   cases truthfully — it is the surface on which every law (fail-closed
   rendering, weakest-boundary, candidate clothing, refusal-with-a-path,
   search-frontier honesty) is first proven.
2. **The live route inventory of `apps/runtime-dashboard`** (snapshot
   2026-06-10): routes `/`, `/login`, `/welcome`, `compose`, `launch`, `data`,
   `evidence`, `health`, `knowledge`, `lex`, `platform`, `sources`,
   `artifacts/:artifactId`, `public/decisions/:signedId`; feature modules
   `artifacts`, `auth`, `causal`, `clerk`, `collaboration`, `commandPalette`,
   `composer`, `dashboard`, `evidence`, `export`, `landing`, `layout`, `lex`,
   `onboarding`, `platform`, `runs`, `whatif`. DS1 audits each route/feature
   against the capability chain and assigns an adoption verdict. This plan does
   not pre-judge dispositions — the audit does.

**Named audit hotspots (DS1 must report on each explicitly; recon findings
from the technical snapshot are recorded inline as confirmed starting points):**

- `public/decisions/:signedId` — inherited public route, **frozen** until
  DS12's gate. *Recon confirmed:* the packet is built **and** verified
  client-side; `signatureForPayload` is a salted hash computed in the browser,
  forgeable by construction; the "Verified" badge is decorative. DS1
  quantifies the blast radius (who links to these URLs, what claims they
  carry).
- `causal`, `whatif`, `lex`, `composer`, `clerk` — engine/LLM-output surfaces
  that predate the candidate-clothing discipline; audit each for P15/P05
  laundering (engine or LLM output rendered in authority dress). `clerk` is a
  full NL chat over `POST /control/runs/nl` and the future DS14 strangle
  target.
- `app/authz/` (`AuthzProvider`, `permissions.ts`), `features/auth`,
  `features/clerk` (incl. `routes.public.ts`) — map the live permission model
  against the audience classes. *Recon confirmed:* the permission vocabulary
  is duplicated server-side (`http/routes/auth.py` `_ROLE_PERMISSIONS`) and
  client-side (`PERMISSION_KEYS`); identity has a fixture fallback; no
  per-permission deny was found on mutating endpoints. DS1 names every
  UI-hides-but-server-allows gap.
- `sw.ts` (Workbox precache) and `app/offline/` (`offlineQueueRepository`) —
  inventory what is cached and what is queued offline. *Recon confirmed:*
  `useQueuedPromotionDecision` queues evidence promotion approve/reject
  offline — a live authority action in the queue. DS1 inventories the full
  cache/queue scope.
- `src/workers/` (`dataTransform.worker.ts` and peers) and
  `shared/lib/domain/projectionFailClosed.ts` — check client-side transforms
  and fail-closed normalization against law 9's boundary: layout/sorting
  derivations are allowed, authority recomputation and authority-adjacent
  re-derivation are not.
- **Off-contract and phantom channels.** *Recon confirmed:* SSE
  `GET /runs/live` and `GET /runs/{id}/live` are `include_in_schema=False`;
  the review WebSocket hub (`/api/v1/review/live`) is unrepresented in the
  contract; the collaboration REST paths the UI calls
  (`/api/v1/collaboration/*`) have **no server route in `runtime/http`** —
  vite only proxies to the runtime, so they are presumed phantom (404). DS1
  inventories every off-contract or phantom path and what UX silently degrades
  when they fail.
- **Feature flags.** *Recon confirmed:* 12 manifest-driven flags gate whole
  workspaces (`enableRunsWorkspace`, `enableClerkMode`, `enableAtlasV2`,
  `enableDarkMode`, …) with a second flag source in `/auth/me`
  `feature_overrides`; no owner/intent/sunset governance found. DS1 audits the
  flag inventory against the DS0 registry decision.
- **Public telemetry.** *Recon confirmed:* Sentry is wired app-wide
  (`shared/telemetry/sentry.ts`). DS1 maps what data leaves the app on which
  routes, feeding DS12's no-tracker posture.

## Strangler Decision

`apps/runtime-dashboard` is the only live consumer of the generated client and
is the strangle target: DS4 primitives land inside it, admitted v15 substance
replaces its pieces feature-by-feature, and the surface readiness ledger tracks
migration coverage. `apps/runtime-reference-shell` stays an intentionally
narrow read-path diagnostics tool and must not grow product surfaces. A
greenfield rebuild is rejected (P06: canonical ownership ambiguity, in code).

## Slice Sequence (overview)

Phases group slices by readiness, not by team. Numbering is continuous and
roughly chronological; the DAG, not the numbers, governs start order.

| Slice | Theme | Gate / prereqs | Phase |
| --- | --- | --- | --- |
| DS0 | Source-of-truth freeze & governing decisions | none (GY-independent) | A |
| DS1 | Live application audit | DS0 | A |
| DS2 | Atlas v15 adjudication | DS0 | A |
| DS3 | Runtime producers & export infrastructure (GY artifact projections) | **GY-N10 merged to main** | B |
| DS4 | Status-grammar rebinding & test harness (GY vocabulary) | DS3 | B |
| DS5 | Enforcement waist: lints, audience mapping, cache discipline | DS4; DS1 reports | B |
| DS6 | Evidence workflow & instrumentation | DS4 | B |
| DS7 | **Cycle Board** (hero; supersedes "proving-ground board") | DS5 | C |
| DS8 | Case & evidence workspace: stage-trace drill-down (strangling) | DS7 | C |
| DS9 | Human decision integrity | DS8 | C |
| DS10 | Capability discovery | DS5 + disposition-ledger/census content | C |
| DS15 | Acquisition routes & data-pool growth surfaces | DS7; read parts after **GY-N13a**, live loop after **GY-N13b** | C |
| DS16 | Value, uncertainty & derived-data grammar | DS4; value parts live at merge, derived parts after **GY-N13b** | C |
| DS17 | Confidence-ledger & risk-spend surface | DS7; **GY-N11 closed** | C/D |
| DS18 | Epoch & staleness chrome | DS4; **GY-N12 closed** | C/D |
| DS11 | Trust/docs posture | DS9; DS6 | D |
| DS12 | Public publication foundation | **first governed promotion through the GY-N9 gate with N11 δ-accounting and N12 epoch validity live** AND DS11 | D |
| DS13 | Accountability ledgers & transparency | DS12 | D |
| DS14 | Bounded-agent surface | **Phase-6 bounded-agent contracts closed (O-block)** AND DS9 | D |

```text
Phase A (start NOW):        DS0 ─▶ { DS1, DS2 }
        ───── activation: GY-N10 merged to main ─────
Phase B (waist):            DS3 ─▶ DS4 ─▶ DS5
                                    └──▶ DS6  (gates all later `stable` claims)
Phase C (workspace):        DS5 ─▶ DS7 ─▶ DS8 ─▶ DS9
                            DS10: after DS5 + ledger/census producers
                            DS15: after DS7 (+N13a read / +N13b live loop)
                            DS16: after DS4 (+N13b for derived-data parts)
                            DS17: after DS7 + GY-N11
                            DS18: after DS4 + GY-N12
Phase D (outward):          DS11: after DS9 + DS6
                            DS12: after DS11 + first governed promotion (N9+N11+N12)
                            DS13: after DS12
                            DS14: after DS9 + Phase-6 O-block
```

The runtime gates encode the constitutional subordination order: public
surfaces never outrun the promotion gate; the agent surface never precedes the
bounded agent.

### Start-Now Ladder (what runs when, against the GY plan)

| GY milestone | Unblocked surface work |
| --- | --- |
| **Now** (audit in flight; nothing merged) | DS0, DS1, DS2 — decisions, live-app audit, v15 adjudication. Zero GY coupling; does not touch the GY worktree. |
| **GY-N10 merged** (imminent) | DS3 producers over the capstone/value-gate/ledger/census artifacts → DS4 grammar rebinding → DS5/DS6 waist → **DS7 Cycle Board on real capstone data** → DS8 stage-trace workspace → DS9; DS10 discovery over the disposition ledger + method/dataset catalogs; DS16's value/uncertainty grammar (ValueOuterSet is live data). |
| **GY-N13a closed** | DS15 read surfaces: connector scorecard, liveness map, D2 growth backlog ("what the system wants to learn next and why"). |
| **GY-N13b closed** | DS15 live loop: approve-acquisition CTA → world-growth event → case re-entry rendered truthfully; admission passports and quarantine views; DS16 derived-data provenance (derivation certificates, basis/deflator assumption chips). |
| **GY-N11 closed** | DS17 δ-budget and risk-spend surfaces (refusal/acquisition instruments first — that is the data that exists). |
| **GY-N12 closed** | DS18 epoch chrome: `as_of`/epoch/`revalidation_required` badges everywhere; stale-certificate and revision-trigger views. |
| **First governed promotion** (N9 + N11 + N12 live; per Rule 5 this may be distant) | DS12 public publication → DS13 accountability ledgers. |
| **Phase-6 O-block closed** | DS14 bounded-agent surface (strangles `features/clerk`). |

## Per-Slice Detail

### Phase A — Pre-Activation (Layer-3-independent)

#### DS0 — Source-Of-Truth Freeze & Governing Decisions

The surface analogue of G0's discipline freeze: decisions and schemas, before
any audit or build.

Canonical governing record:
[Atlas Source-Of-Truth And Governing Decisions](../../brand/ATLAS_SOURCE_OF_TRUTH.md).

**Status (2026-07-16):** DS0 is complete on
`codex/atlas-ds0-source-of-truth` and awaits architect review. D4's locale
recommendation is deliberately `pending_owner_ratification`; no locale policy
is implied by DS0 closure.

- **Goal:** one canonical design source of truth and the governing decisions
  every later slice references.
- **Deliverables:** v4/v7/v15 **supersession decision**
  (`docs/brand/ATLAS_DESIGN_SYSTEM.md`, `ATLAS_V4_ADOPTION.md` superseded as
  governing sources but retained as v4 evidence; `FRONTEND_SOTA_PLAN.md` and
  `DESIGN_BEST_IN_CLASS_PLAN.md` archived via docs lifecycle; v7 retained only
  as DS11-DS13 material; historical G naming retained without execution
  authority);
  **token pipeline decision** (one source of truth, sunset for the loser —
  closes T6); **package home + versioning decision** (e.g. `packages/atlas-ui`,
  release policy, Figma source-vs-projection status with parity ownership);
  **i18n/locale evidence package and recommendation** (`ru` retention remains
  `pending_owner_ratification`; includes RTL posture and owner);
  **feature-flag registry decision** (the 12
  manifest-driven flags get owner, intent, sunset, and an explicit role in the
  shadow-shipping discipline; the dual flag source — manifest vs `/auth/me`
  overrides — collapses to one governed path); **non-web surface disposition**
  (`packages/cli` styleguide, `docs/brand/` email/print/CLI/glyph/motion
  specs: each named surface family is admitted into a slice's scope or
  recorded explicitly out-of-scope); **adoption ledger schema** and **surface
  readiness ledger schema**, each with a valid example and in-fence
  self-validation, under `architecture/atlas_surfaces/`.
- **Laws / patterns:** Rule 10; closes P06.
- **Negative controls:** every decision records rejected alternatives and
  revisit conditions.
- **Not yet:** nothing is audited, adjudicated, or shipped here — DS0 decides
  and defines.

#### DS1 — Live Application Audit

- **Goal:** an honest chain status for everything the app already ships.
- **Prereqs:** DS0 (ledger schemas).
- **Deliverables:** **route/feature chain audit** of the full proving-ground
  inventory with an adoption verdict and capability-chain status per
  route/feature; the five **named audit hotspots** reported explicitly
  (inherited public route incl. signing mechanics; `causal`/`whatif`/`lex`/
  `composer` P15/P05 laundering check; **authz/audience gap report** — every
  UI-hides-but-server-allows gap named; **cache/offline policy report** — what
  may be cached with what staleness rendering, what is barred from the offline
  queue; workers boundary check against law 9); seeded red-first negatives for
  later slices.
- **Laws / patterns:** capability reality bar; seeds P15/P05/P26 negatives.
- **Negative controls:** the audit itself is evidence-bearing — every verdict
  links to the code it judged.
- **Not yet:** findings are classified, not fixed; nothing is unfrozen.

#### DS2 — Atlas v15 Adjudication

- **Goal:** the v15 archive fully adjudicated into the adoption ledger —
  against the **living coded v4** (`shared/ui` ~40 components with a11y tests
  and stories, `designTokens.ts`), not into a void: every verdict is a
  migration decision between two real systems.
- **Prereqs:** DS0 (ledger schema, token/package decisions).
- **Deliverables:** **conformance battery** for archive claims (what "PASS" in
  the zip proves; what requires browser/AT/runtime evidence); per
  token-set/component/pattern **verdict** (`admit_as_is` /
  `admit_after_refactor` / `wrap_then_strangle` / `reject` / `defer`) with
  maturity, evidence, consuming surface, rejected deltas, sunset dates,
  **and the disposition of the in-repo v4 counterpart** where one exists;
  `defer` by default where no surface in this DAG consumes the item (anti-P13).
- **Laws / patterns:** Rule 10; P06, P10, P13.
- **Negative controls:** archive PASS reports cannot mark anything `stable`;
  every rejection records its reason and revisit condition.
- **Not yet:** admission into the ledger is not admission into production
  surfaces; no component ships to users from this slice.

### Phase B — The Waist (post-activation)

#### DS3 — Runtime Producers & Export Infrastructure

- **Goal:** the artifacts this plan renders get real HTTP producers, plus the
  shared export machinery every later twin reuses.
- **Gate:** GY-N10 merged to main.
- **Producer & bridge work (the slice IS producer work):** typed runtime API
  endpoints (or governed static exports) for the **GY frozen artifacts** — the
  depth-N capstone (`layer3_gy_depth_n_universality_contract.json`), the value
  gate contract, the disposition ledger, the engine + Fork-B censuses, the
  acquisition planner reports — plus `capability_reality_report.json`,
  `cluster_ownership_map.toml`, the 13-case proving-ground records,
  health-metric ledgers, and the surface readiness ledger — each payload
  carrying **as-of/freshness metadata** and each producer **binding the
  narrowest upstream projection hash (GY §3.5.11)**, so artifact rebaselines
  upstream do not ripple through every endpoint; payloads expose recomputed
  structural properties, never pinned terminal labels (GY §3.5.10); **shared export machinery**: stable
  addressing, replay pinning, typed packet conventions — **extending the
  existing export endpoints** (lineage `openlineage`/`prov`, artifact packet
  export/render, decision-validity), not reinventing them; **off-contract
  channel governance**: the two `include_in_schema=False` SSE endpoints and
  the review WebSocket hub get typed/governed contract coverage or an explicit
  out-of-scope record, and the phantom collaboration REST gets a
  build-or-remove decision; OpenAPI schema + `runtime-api-client`
  regeneration.
- **Laws:** 9; the producer/bridge half of the capability bar.
- **Negative controls:** P01 at the producer level — an endpoint that
  re-derives instead of projecting the governed artifact fails its semantic
  test; payloads without as-of metadata fail contract tests.
- **Not yet:** no UI; producers are proven by contract tests and the
  reference shell, not by new screens.

#### DS4 — Status-Grammar Rebinding & Test Harness

- **Goal:** the define-once visual grammar of authority, bound to generated
  contracts. Per the technical snapshot this is a **rebinding slice, not a
  component-building slice**: `ProvenanceStrip`, `trust-view`, `quantity`,
  `temporal`, `Badge`, `EmptyState` and peers already exist with a11y tests —
  what they lack is binding to the authority lattice.
- **Gate:** DS3 (regenerated client types).
- **Deliverables:** evidence-bearing primitives — `AuthorityBadge`,
  `CandidateFrame`, `BlockerCard`, `EnvelopeChip`, `EvidenceLink`,
  `ProvenancePopover`, `TimeSemanticsLabel` (covers `cached(as_of)`/`stale`
  rendering), `WeakestLinkExplainer` — **built by rebinding the existing
  component families to generated client types** (names indicative; task plan
  finalizes the build-vs-rebind call per component); **retirement of UI-local
  status vocabularies** — the ≥8 local enums (incl. `DisputeStatus` ×3)
  migrate to lattice-derived types or get explicit non-authority
  classification; `fixture_only` marking machinery (type + visual treatment);
  the existing Storybook/a11y harness and the **existing Playwright visual
  spec + snapshots** extended to cover the primitives and wired into CI;
  primitives proven on one existing strangled panel.
- **Laws:** 1, 2, 3, 4, 6, 8, 10.
- **Negative controls:** candidate output rendered in authority dress fails
  visual regression; weakest-boundary explanations come from the API, and a
  client-side recomputation fails its semantic test; a revived UI-local status
  enum fails review against the retirement ledger.
- **Not yet:** no new product routes; no lints yet (DS5).

#### DS5 — Enforcement Waist: Lints, Audience Mapping, Cache Discipline

- **Goal:** the laws become mechanical.
- **Gate:** DS4; DS1 reports (authz gaps, cache policy).
- **Producer & bridge work (in-slice):** the **audience↔permission mapping**
  projected server-side with deny enforcement; weakest-boundary/status
  composition exposed in the schema where not yet projected; client
  regeneration.
- **Deliverables:** the `[to build]` lints from laws 8/9/10/12 —
  unauthorized-status-enum lint, no-hand-written-authority-fetch lint (the ~10
  known hand-fetch files are its first targets), capability-menu lint,
  duplicate-label/static-copy lint; **single permission vocabulary** — the
  server/client duplication (`_ROLE_PERMISSIONS` vs `PERMISSION_KEYS`)
  collapses to one source projected through the schema; **per-permission deny
  on mutating endpoints** (none found in recon — this is the load-bearing
  half); **cache/staleness rendering rules** implementing the DS1 policy
  (cached payloads carry as-of; authority actions barred from the offline
  queue or carrying an explicit revalidation protocol — `useQueuedPromotionDecision`
  is the first migration); server-side **deny tests** per audience class.
- **Laws:** 8, 9, 10, 12; 11 (audience enforcement half).
- **Negative controls:** a UI-defined status enum turns the lint red; a
  hand-written fetch to an authority endpoint fails CI; a PUBLIC-class request
  for REVIEWER data is denied server-side in a contract test; an authority
  action enqueued offline fails its negative test.
- **Not yet:** enforcement covers the waist and existing strangled panels;
  un-migrated legacy features carry honest lint-debt entries in the ledger.

#### DS6 — Evidence Workflow & Instrumentation

- **Goal:** the machinery that makes "stable" and "honest" measurable —
  gates every later `stable` claim.
- **Gate:** DS4 (harness).
- **Deliverables:** browser + keyboard + manual **AT evidence workflow** with
  a storage convention for evidence artifacts, wired to the component maturity
  bar; **surface-readiness-ledger CI validator** (ledger claims vs the tests
  and evidence that actually exist); **health-metric instrumentation** for the
  metrics table below, incl. review-effectiveness telemetry collection;
  **honesty-comprehension protocol** — a lightweight recurring reviewer-task
  procedure (find the weakest link, find the active blockers) with cadence and
  owner.
- **Laws:** 5; P10 closure.
- **Negative controls:** a component claiming `stable` without stored evidence
  fails the validator; a ledger entry claiming `implemented` without its
  negative/semantic test fails CI.
- **Not yet:** no product surfaces; DS6 measures, it does not ship screens.

### Phase C — Workspace Surfaces

#### DS7 — Cycle Board (the hero surface; supersedes "proving-ground board")

- **Goal:** the REVIEWER/EXPERT board — the interface that is proud to say
  "we do not know yet", **and shows exactly what it would take to know**.
  Revision 2 upgrades the hero from the static 13-case board to the living
  board of the GY cycle.
- **Gate:** DS5.
- **Shape:** one row per `DesignProblem` the cycle has ever run — the three
  N10 capstone domains first (first-vertical, education, unseen/no-pack), the
  13 legacy proving-ground cases as a second cohort, and every future
  plain-language submission. Columns: typed terminal kind; **structural
  evidence class** (`owner_acquisition_route` / `estimand_binding_refusal` /
  `owner_data_gap` — recomputed, never a label); weakest missing link; the
  **costed acquisition route** (strategy, cost, VOI from the N7 planner
  report) with its execution status; responsible slice (GY-N13+ / DS-slice);
  stage-trace drill-down link (DS8); surface readiness; public-safe
  explanation. The board displays the **as-of/staleness of its own data
  sources** (law 7 applies to the board too) and renders the **surface
  readiness ledger** — this plan's own progress is an Atlas surface.
- **The refusal-with-a-path pattern is the board's core interaction:** a
  blocked row never dead-ends — it opens into what is known, the exact typed
  missing link, and the costed route; after GY-N13b, a route that closes
  renders as **movement** ("gap closed by acquisition {date} → case
  re-entered → deeper terminal"), making the flywheel visible.
- **MACHINE twin (in-slice):** typed JSON export on DS3 machinery with a
  parity test.
- **Laws:** 3, 4, 5, 12; P25 negatives (frontier shown as control-plane
  evidence, never as exhaustiveness).
- **Closure:** semantic test — the board's weakest-link and evidence-class
  claims equal the artifact's recomputed values, not a client-side
  recomputation and not a pinned string.
- **Not yet:** REVIEWER/EXPERT only; the board does not go PUBLIC before
  DS12's gate; the movement row is honest-empty until N13b actually closes a
  route (no simulated motion).

#### DS8 — Case & Evidence Workspace (strangling)

- **Goal:** case inspection over real artifacts, and the legacy features
  brought through the waist.
- **Gate:** DS7.
- **Producer & bridge work (in-slice):** case/DesignRecord inspection
  endpoints where missing; schema + client regeneration.
- **Deliverables:** DesignRecord/case inspection with grounding/admission/
  promotion state; blockers, limitations, objections, abstentions as
  first-class objects; **strangle moves**: `evidence`, `runs`, `artifacts`
  features migrate to DS4 primitives, with ledger-tracked migration coverage;
  MACHINE twin per shipped view.
- **Laws:** 3, 4, 6, 7.
- **Negative controls:** closed-case views pin versions (law 7) and a mutation
  attempt fails; P15 negatives land on any engine-output panel the audit
  flagged.
- **Not yet:** no public projection of cases; no NL entry points; approval
  flows stay read-only until DS9.

#### DS9 — Human Decision Integrity

- **Goal:** approval, override, and blocking flows a principal can be
  accountable for.
- **Gate:** DS8.
- **Producer & bridge work (in-slice):** `HumanDecisionRecord` read/write
  endpoints with **step-up authentication** enforcement (law 11's `[to build]`
  half) and review-effectiveness telemetry events — drawing on the existing
  **append-only access-audit trail** (`http/access_audit.py`) rather than a
  new log. The existing `POST /runs/{run_id}/production-approval` endpoint
  (recon: no per-permission deny) is brought under the same enforcement.
- **Deliverables:** approval/override/blocking flows showing mandate, evidence
  exposure, dissent, override reason; step-up auth on high-stakes actions;
  MACHINE twin of decision records.
- **Laws:** 11; 7.
- **Negative controls:** P26 negatives — a rubber-stamp approval (no evidence
  opened, no mandate shown) is blocked and surfaced; an approval attempted
  from the offline queue is rejected pending revalidation.
- **Not yet:** no delegation-chain UI beyond what `HumanDecisionRecord`
  carries; no public rendering of decisions (DS12).

#### DS10 — Capability Discovery

- **Goal:** navigation and pickers that are search-driven over typed indexes —
  the Rule 12 dual, made real.
- **Gate:** DS5; meaningful adapter-registry content.
- **Producer & bridge work (in-slice):** typed search/discovery endpoints over
  the corpus indexes and the search-frontier ledger projection (request,
  selected and rejected candidates, cutoffs, incompleteness reasons);
  **re-grounding of the existing capability manifest** — `GET
  /control/capabilities` is today a hand-maintained `CapabilityFeatureInfo`
  enumeration (`services/control/capabilities.py`), a live Rule-12 case: DS10
  rebuilds it on registry/discovery search or re-classifies it as fixed app
  chrome with a strangle note; `control/data/catalog/search` is the discovery
  seed to extend.
- **Deliverables:** discovery surfaces for methods, datasets, sources, legal
  norms, cases, agents rendering the three postures (`discoverable` /
  `executable` / `admitted_authority`) and the frontier honestly; fixed
  workspace chrome explicitly separated from capability discovery.
- **Laws:** 2, 12.
- **Negative controls:** the capability-menu lint goes red on a hardcoded
  enumeration; the **free-growth UI test** — a correctly admitted new adapter
  appears with zero frontend code change; P25 negatives on no-hit/recall
  rendering.
- **Not yet:** discovery never implies admission; `discoverable` is visibly
  candidate-grade.

### Phase D — Outward Surfaces

#### DS11 — Trust / Docs Posture

- **Goal:** posture honestly stated before any performance claims exist.
- **Gate:** DS9; DS6 (evidence workflow operational).
- **Producer & bridge work (in-slice):** the **claims register** as a typed,
  owned artifact (source, jurisdiction, owner, review date,
  `authoritative_for` / `may_not_use_for` per claim) with its producer and CI
  check.
- **Deliverables:** methodology, envelope and limitations, accessibility
  conformance evidence surfaces; supported/planned/blocked register; MACHINE
  twin of the register.
- **Laws:** 5, 6.
- **Negative controls:** P05 negative — copy that upgrades `planned` or
  `candidate` to `supported` fails the claims-register check.
- **Not yet:** no grounded-performance claims until the runtime earns them.

#### DS12 — Public Publication Foundation

- **Gate (constitutional, re-stated in Revision 2):** the **first governed
  promotion** exists — a design promoted through the GY-N9 gate with GY-N11
  δ-accounting and GY-N12 epoch validity live — **and** DS11. Per Rule 5 the
  runtime never forces this milestone; the public surface waits honestly.
  Before it, the public-facing story is DS11 posture + the Cycle Board's
  public-safe projection (honest status, not recommendations).
- **Goal:** the first honest public surface: one promoted decision record,
  published end-to-end, verifiable by a citizen.
- **Producer & bridge work (in-slice):** public record/certificate endpoints;
  the **signing and verification chain** — server-side signing with real keys,
  server-backed verification, citizen verification UX, key-management/
  transparency posture, published not implied. This **replaces the decorative
  client-side mechanism** found in recon (browser-computed salted hash,
  forgeable): the existing packet builder is kept only as a rendering view
  model, never as the authority or signature source.
- **Deliverables:** the **public operational bar as CI checks** — no
  third-party trackers, Core Web Vitals budgets, security headers,
  mobile/responsive support, the DS0 i18n decision implemented,
  plain-language register; an explicit **public telemetry posture** (Sentry is
  wired app-wide today — on PUBLIC routes error telemetry is self-hosted,
  scrubbed, or absent; never silently third-party); the inherited
  `public/decisions/:signedId` route strangled onto the server-backed chain;
  public MACHINE twin.
- **Laws:** 4, 5, 7.
- **Negative controls:** **a forged packet must stop rendering as
  "Verified"** — the first red-first negative of the slice; P05 negatives at
  the public boundary; a public page ahead of the runtime envelope fails the
  envelope check; an unauthenticated request for non-PUBLIC data is denied
  server-side.
- **Not yet:** one record published well beats many published loosely;
  dispute/consultation/history surfaces arrive in DS13.

#### DS13 — Accountability Ledgers & Transparency

- **Goal:** the public record becomes contestable and historical, not just
  visible.
- **Gate:** DS12.
- **Producer & bridge work (in-slice):** dispute/consultation ledger and
  supersession/revocation history endpoints; transparency feed producer.
- **Deliverables:** dispute and consultation ledgers with
  response-to-comment records; supersession, revocation, and learning history
  (law 7 rendering: "this case" vs "new evidence"); transparency feed; MACHINE
  twins throughout.
- **Laws:** 5, 7.
- **Negative controls:** a closed public record cannot be mutated by new
  evidence — only superseded with visible lineage; P26 negatives on
  consultation-response accountability.
- **Not yet:** no automated dispute resolution; ledgers record and project,
  humans decide.

#### DS14 — Bounded-Agent Surface

- **Gate:** Phase-6 bounded-agent contracts closed (the GY plan's O-block /
  bounded LLM agent, formerly "G6"); DS9. The agent surface obeys the GY
  §3.5.9 live-carrier gates by construction — its transcript UI renders the
  constrained-carrier lifecycle honestly (typed refusals, truncation
  dispositions, characterization posture), never a smoothed chat illusion.
- **Goal:** the NL/orchestration interface in **candidate clothing**:
  request → grounded-result-or-abstention flows, the orchestration-choice
  audit view, abstention-first UX. The agent's fluency never upgrades its
  authority.
- **Producer & bridge work (in-slice):** agent session and orchestration-audit
  endpoints over the G6 contracts; schema + client regeneration.
- **Strangle target:** `features/clerk` — the existing NL chat (streaming,
  history, structured responses) is the UX substrate; DS14 re-grounds it on G6
  contracts and candidate clothing instead of building a second chat. Recon:
  `clerk` is **one of two app-level interface modes** (`clerk | analyst`,
  flag- and permission-gated) — the chat-first posture may be the default for
  non-analyst users, which makes candidate-clothing discipline here
  product-critical, not cosmetic.
- **Laws:** 1, 2, 11.
- **Negative controls:** P15 negatives — fluent agent text cannot populate an
  authority slot, an approval field, or a public claim; orchestration choices
  render with their audit trail.
- **Not yet:** no agent output on PUBLIC surfaces; agent surfaces stay
  REVIEWER/EXPERT until a separate, explicit decision.

### New Slices (Revision 2 — the GY-N13/N11/N12 surface duals)

#### DS15 — Acquisition Routes & Data-Pool Growth Surfaces

- **Goal:** the surface dual of GY-N13 — the product's distinctive loop:
  **refusal-with-a-path becomes refusal-with-a-button.** The user sees why a
  case is blocked, what closing it costs, and (post-N13b) approves the
  acquisition and watches the world grow and the case re-enter.
- **Gate:** DS7. Read surfaces after **GY-N13a**; the live loop after
  **GY-N13b**.
- **Producer & bridge work (in-slice):** projections of the N13a census
  (connector scorecard, liveness map, catalog↔runtime metric resolution, the
  D2 VOI-ranked growth backlog) and, post-N13b, the acquisition execution
  surfaces (route status, admission passports, quarantine ledger, overlay
  epoch events, re-entry traces); schema + client regeneration.
- **Deliverables:** route detail view (typed requirement → costed plan →
  strategy → VOI → status); growth-backlog board ("what the system wants to
  learn next and why"); connector scorecard + liveness surfaces with tier
  decay honestly shown; post-N13b: the **approve-acquisition flow** (a
  DS9-class human decision with mandate + step-up, never one-click), the
  passport view (schema/units/alignment/license/PII/trust checks, each typed),
  the quarantine view (what arrived but was NOT admitted, and why), and the
  world-growth event feed; MACHINE twins throughout.
- **Laws:** 3, 5, 11, 12; GY §3.5.12 D1–D6 rendered, never re-derived.
- **Negative controls:** a fetched row without a full passport must render as
  quarantined, never as world data (P05 at the data plane); an acquisition
  approval from the offline queue is rejected; the growth backlog cannot be
  reordered client-side against its VOI ranking without showing the override.
- **Not yet:** no auto-execution UX — acquisition stays a gated human
  decision; no PUBLIC projection of the backlog before DS12's gate.

#### DS16 — Value, Uncertainty & Derived-Data Grammar

- **Goal:** the visualization grammar that makes set-valued honesty readable:
  values as sets/intervals with `unknown` and `incomparable` as **designed
  states**, and every derived number wearing its recipe.
- **Gate:** DS4. Value/uncertainty parts are live at N10 merge
  (`ValueOuterSet`, advisor receipts); derived-data parts after **GY-N13b**.
- **Producer & bridge work (in-slice):** value-gate projections (outer sets,
  advisor receipts, method denominators); post-N13b: derivation-certificate
  projections (recipe = inputs × method+params × auxiliaries) and the basis
  vocabulary (GY §3.5.12-D6).
- **Deliverables:** the set-valued value viz family (never collapses to a
  point; `unknown`/incomparable rendered as first-class, not as gaps); basis
  chips on every monetary/unit-bearing chart (`real, base-2020,
  deflator=CPI` — the assumption is a visible, clickable element resolving to
  its certificate); derivation-recipe popover (what this number was computed
  from, by what, under which declared assumptions); provenance-class marking
  (`observed` / `derived` / `deployment_update`) wherever data is
  decision-bearing.
- **Laws:** 1, 3, 4, 5; the chart obligations of the constitution's Data And
  API Boundaries (source, uncertainty, time semantics — extended with basis).
- **Negative controls:** a set-valued value rendered as a point estimate fails
  visual regression; a derived series rendered without its provenance class
  fails the semantic test; a class-(iv) model output styled as observed data
  is the data-plane P15 and must fail.
- **Not yet:** no transform-planner UI (the GY plan defers transform chains);
  single-transform provenance only.

#### DS17 — Confidence-Ledger & Risk-Spend Surface

- **Goal:** δ-accounting on the glass: what promotion risk has been spent, on
  which obligation classes, through which instruments.
- **Gate:** DS7; **GY-N11 closed**.
- **Producer & bridge work (in-slice):** ledger projections (δ-split,
  risk-spend per obligation class × instrument, good-event posture); schema +
  client regeneration.
- **Deliverables:** the δ-budget view (spent vs remaining, per class); the
  instrument register — **refusal and acquisition instruments first**, because
  that is the data that exists (positive promotion certificates render
  honestly empty until they exist); over-spend and non-anytime-valid
  certificate states rendered as hard blockers; MACHINE twin.
- **Laws:** 3, 4, 5, 8.
- **Negative controls:** an over-spent scope cannot render as promotable; a
  Bayesian credible interval without a coverage argument cannot appear as a
  promotion certificate (the N11 negative, surfaced).
- **Not yet:** no public δ claims before DS12; the view is REVIEWER/EXPERT
  accounting, not a marketing score.

#### DS18 — Epoch & Staleness Chrome

- **Goal:** time semantics as universal chrome: every decision-bearing
  surface shows `as_of`, epoch, and validity — and stale things look stale.
- **Gate:** DS4 (the `TimeSemanticsLabel` primitive); **GY-N12 closed** for
  real epoch semantics.
- **Producer & bridge work (in-slice):** epoch/staleness projections (current
  epoch per scope, stale-certificate sets, revision triggers, OpenWorldRisk);
  schema + client regeneration.
- **Deliverables:** epoch badges and `revalidation_required` states wired into
  DS4 primitives everywhere; the stale-certificates view (what went stale,
  which revision trigger, what revalidation would take); derived-data
  staleness inheritance rendered (input revision → dependent derivations
  flagged, recompute status); OpenWorldRisk freeze states; MACHINE twin.
- **Laws:** 3, 6, 7.
- **Negative controls:** a stale certificate rendered as current fails the
  semantic test; a chart without `as_of` on a decision-bearing surface fails
  the DS5 lint battery (extended here); crossing an epoch boundary in a replay
  view must show the boundary, not blend across it.
- **Not yet:** epoch chrome does not invent time semantics — it renders GY-N12
  and §3.5.12-D6 outputs only; scopes without regime data render honest
  `epoch_scope_unresolved`.

## Tensions (watch these or they go silent)

| # | Tension | Mitigation |
| --- | --- | --- |
| T1 | Status-lattice churn during late Layer 3 vs DS4 freeze | DS4 binds to generated types, not strings; Phase B waits for closeout re-derivation; lattice changes trigger re-derivation, not patching |
| T2 | v15 gravity well: 56 components invite bulk adoption (P13) | DS2 admission is per-component and consumer-driven; `defer` is the default verdict without a consuming surface in the DAG |
| T3 | Design polish cadence vs evidence bar | `fixture_only` work is allowed in Storybook/`experimental` freely; the bar applies at `beta`/`stable` and authority slots |
| T4 | Pressure for public surfaces before promotion exists | DS12's gate is constitutional; DS11 posture surfaces give marketing honest material earlier |
| T5 | Reference-shell drift into a parallel product | ownership note + review check: diagnostics-only scope |
| T6 | Token drift between v15 DTCG pipeline and current dashboard styles | DS0 picks one token source of truth with a sunset for the loser |
| T7 | Offline/cache capability vs staleness honesty | freshness posture vocabulary + DS1 cache policy + DS5 rendering rules; authority actions barred from the offline queue |
| T8 | Cross-team coupling: surface slices needing runtime producers stall | full-stack slice definition + named backend deliverables with runtime co-owner in every task plan; "blocked on backend" is not a valid slice state |
| T9 | Slice-count creep: 15 slices invite ceremony (P13) | one task plan, one closure contract, one review per slice; re-cut via roadmap amendment when disproportionate, never suffix or inflate |
| T10 | Off-contract channels: SSE/WS and `include_in_schema=False` quietly grow a second, untyped API beside the waist | DS3 brings channels under typed/governed contracts or explicit out-of-scope; the DS5 lint battery covers raw `EventSource`/`WebSocket`/fetch construction outside the sanctioned transports |
| T11 | GY frozen-artifact churn (rebaselines, provenance ripples) vs UI binding stability | producers bind narrow projection hashes (GY §3.5.11) and recomputed structural properties (GY §3.5.10); a rebaseline that changes only provenance must not break a surface contract test |
| T12 | The refusal-with-a-button loop (DS15) creates product pressure to "make acquisitions succeed" — the surface twin of forcing `useful_design_rate` | Rule 5 on the glass: quarantine and failed passports render as prominently as admissions; the growth backlog shows VOI ranking, not conversion targets; no surface KPI rewards acquisition volume |

## Health Metrics (instrument these, or the honesty goes silent)

| Metric | Definition | Honest direction |
| --- | --- | --- |
| Primitive adoption | share of decision-bearing renders flowing through DS4 primitives | rising; 100% for authority slots |
| Fail-closed fidelity | share of blocker/abstention/out-of-envelope/stale-cached states rendered as typed states (vs generic empty/error) | rising to 100% |
| Audience enforcement | share of audience-scoped endpoints with passing server-side deny tests | 100% before DS12 |
| `surface_missing` closure | open `surface_missing` / `implemented_but_not_orchestrated` links in the cluster map | falling |
| Evidence coverage | share of `stable` components with browser + AT evidence | 100% for `stable` |
| Machine-twin parity | share of shipped surfaces with a passing twin parity test | 100% — twins ship in-slice |
| Honesty comprehension | reviewer-task success at locating the weakest link / active blockers (DS6 protocol) | measured and reported |

Never targeted: screen fullness, dashboard green-ness, conversion copy
performance (constitution Rule 5). `useful_design_rate` remains a runtime
metric and is reported on the board, never optimized by surface work.

## Validation (plan closure contract)

This plan is closed when all of the following hold:

1. Every `[to build]` enforcement item in the surface constitution's laws table
   exists and runs in CI.
2. The v15 archive is fully adjudicated in the adoption ledger (no `pending`
   verdicts); v4/v7 docs are superseded; the legacy plans are archived.
3. The Cycle Board runs on the live GY artifacts (capstone + ledgers +
   censuses + 13 legacy cases) **through in-repo HTTP producers** with its
   MACHINE twin and semantic test green, and its evidence-class claims are
   recomputed, never pinned (GY §3.5.10).
4. The `surface_missing` closure target — set at activation from the post-L3
   cluster map count — is met, with each closure traceable to a slice.
5. At least one public decision record is published end-to-end through the
   promotion gate with provenance certificate, working citizen verification,
   and MACHINE twin (DS12).
6. Audience enforcement is proven: server-side deny tests cover every
   audience-scoped endpoint; step-up auth covers high-stakes actions; no
   UI-hides-but-server-allows gap from the DS1 report remains open.
7. The cache/offline policy is enforced: cached renders carry freshness;
   authority actions cannot execute from the offline queue without
   revalidation.
8. DS6 machinery is operational: evidence workflow, ledger CI validator,
   health-metric instrumentation, honesty-comprehension protocol.
9. Every shipped surface carries its MACHINE twin with a passing parity test
   (in-slice doctrine, no retrofit backlog).
10. The surface readiness ledger is green-or-honestly-red in CI and rendered
    on the board.
11. The refusal-with-a-path loop is proven end-to-end: at least one
    acquisition route renders with its costed plan (DS15 read), and — once
    GY-N13b has closed a route — the world-growth re-entry renders truthfully
    with its passports and quarantine honestly shown.

Closure converts the surface constitution's Promotion Criteria into fact:

| Surface-constitution promotion criterion | Satisfied by |
| --- | --- |
| 1. DS0 classifies v4/v7/v15 adoption | DS0 + DS2 |
| 2. Proving-ground board slice plan accepted | DS7 task plan |
| 3. Status-grammar lint/contract tests | DS5 |
| 4. API/client boundary checks | DS5 |
| 5. Accessibility evidence in CI/browser/manual workflows | DS6 |
| 6. ≥1 real `surface_missing` closure without weakening authority | DS7/DS8 |

## Relationship To Existing Plans And Docs

| Document | Disposition |
| --- | --- |
| `layer3-slices/GY-engine-subordination.md` (Rev 17) | **the upstream dependency** — supplies the Input Contract, the artifact vocabulary, and the gate milestones (N10 merge, N13a/b, N11, N12, first promotion, O-block) |
| `POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md` | historical G-naming context retained in place with no execution authority; GY Rev 17 owns current vocabulary, artifacts, and gates |
| `POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md` | superseded as execution master; retained material source for DS11–DS13 until those task plans disposition every item |
| `docs/plans/archive/FRONTEND_SOTA_PLAN.md` | archived 2026-07-16 as vision-superseded; active path is a compatibility stub |
| `docs/plans/archive/DESIGN_BEST_IN_CLASS_PLAN.md` | archived 2026-07-16 as vision-superseded v4 history; active path preserves provenance anchors |
| `docs/brand/ATLAS_DESIGN_SYSTEM.md`, `docs/brand/ATLAS_V4_ADOPTION.md` | superseded as governing sources; retained as v4 baseline/adoption evidence for DS2/DS4 |
| `docs/brand/ATLAS_SOURCE_OF_TRUTH.md` | canonical DS0 source-disposition and governing-decision record |
| `docs/reference/frontend/workspace-contract.md` | binding; DS5 lints implement its boundary mechanically |
| `design/atlas-v15/` archive | evidence source under DS2 admission; never a source of authority by itself |
