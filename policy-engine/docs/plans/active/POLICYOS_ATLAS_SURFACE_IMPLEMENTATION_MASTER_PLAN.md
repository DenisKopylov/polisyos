---
title: PolicyOS Atlas Surface & Frontend Implementation Master Plan
status: ACTIVE - Revision 3 grounded in Phase-A measured reality; activation satisfied (GY-N10 merged); Phase B unblocked
owner: team-design
runtime_co_owner: team-architecture  # producers, bridges, and authz enforcement land in runtime code; named per task plan
created: 2026-06-10
revised: 2026-08-29 (Revision 3.38 - DS15 CLOSED & MERGED `2c8e1c03c`, the first landing slice judged under DS18's armed freeze. 42/42 mechanism paths, 11/11 widening rounds, 25/25 closure criteria, eight declared non-closures registered; register denominator 130 -> 138. THE FREEZE PAID FOR ITSELF ON ITS FIRST CONSUMER: eleven new production files arrived outside the frozen 605 and the register named them under `landing_slice_reconciliation_required` instead of as an anonymous denominator drift, which is exactly what arming it during the DS18 reopening was for. All eleven classified from rendered behaviour, none left unknown, none needing an owner ruling. Census 605 -> 616 files, 719 -> 733 roots, obligated 77 -> 94 as 45 direct + 49 inherited, all covered - verified at merge by two independent derivations with zero digest mismatches across all 616, and DS18's frozen evidence untouched wherever DS15's own edits did not move it. Atlas suite 36 -> 35, zero branch-only. MY THIRD INSTRUCTION ERROR OF THE ROUND, and the agent caught it: I told the lane to work from a branch rebuilt onto current main while reserving the integration conflicts for myself and forbidding an inward merge. It refused to resolve the contradiction, stopped before touching a file and handed back an exact graph readback. That is the behaviour I want and it is the second time this month a correct stop cost a round that a wrong guess would have cost a merge. Standing pattern now four for four across this wave: where my orientation and a package disagreed, the package was right. Both frontend lanes are now closed; DS17 remains written and unstarted.)
last_reviewed: 2026-07-20
surface_constitution: ../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
atlas_source_of_truth: ../../brand/ATLAS_SOURCE_OF_TRUTH.md
phase_a_synthesis: ../../reference/frontend/atlas-phase-a-synthesis.md   # the Revision-3 input package: per-slice confirmed/re-scoped/invalidated + PI-01..PI-24
phase_a_audit: ../../reference/frontend/atlas-live-application-audit.md  # DS1: the measured reality of record (261-unit ledger, 23 seeded negatives)
phase_a_adjudication: ../../reference/frontend/atlas-v15-adjudication.md # DS2: 233-unit v15 verdicts; adoption-ledger IDs are the only door for v15 material
disposition_register: ../../../architecture/atlas_surfaces/frontend-disposition-register.json # DS19: the disposition authority (261 units) + standalone checker + baseline-debt manifests
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

**Revision 3 (2026-07-16) — grounded in Phase-A measured reality.** Phase A
(DS0 governing decisions, DS1 exhaustive live-application audit, DS2 v15
adjudication) is **closed and merged to main** (merge ed74537e8), and GY-N10 is
**merged to main** (7e035a426, GO-CONFIRMED capstone 6fcbd2c11) — **the
activation gate is SATISFIED and Phase B is unblocked.** Revision 3 exists for
one reason: to ground every remaining slice in what the code measurably IS,
and to make false confidence in the system's current abilities structurally
impossible. Three consequences:

1. **The denominators of record are the Phase-A artifacts, never estimates.**
   The measured reality: 944 TS/TSX files (145,033 LOC); 32 route objects / 29
   effective patterns; 17 features; **89 shared/UI implementations in 12
   families (none `stable`)**; 89 OpenAPI operations (45 surface-consumed, 7
   hook-only, **37 uncalled**); **47 UI-local status definitions**; 29/29
   mutating operations without action-permission or step-up; two API-client
   homes; a forgeable browser-side public "signature"; a red structural a11y
   gate; v15 = 233 adjudicated units with **0 `admit_as_is`, 0 `stable`**. Any
   task plan that assumes a capability not backed by the DS1 readiness ledger
   or the DS2 adoption ledger is wrong by construction.
2. **The Phase-B thesis is sharpened**: not "build a system and migrate the
   app" but **project governed runtime truth through ONE client/package waist,
   rebind the useful living families, selectively consume admitted v15
   material by adoption-ledger ID, and strangle every duplicate or false
   owner.** The living v4 estate is the transitional production winner until
   item-specific DS4/DS6 gates close.
3. **Per-slice re-scoping is defined once** in the
   [Phase-A synthesis](../../reference/frontend/atlas-phase-a-synthesis.md)
   (confirmed / re-scoped / invalidated + `PI-01`..`PI-24` per slice) — task
   plans consume it directly; this roadmap does not restate it.

**Activation status (Revision 3).**

- Phase A: **closed** (DS0/DS1/DS2 merged).
- Phase B: **ACTIVE** — DS3 (and DS19, which gates only on DS1 evidence) may
  start now; DS20 starts after DS3.
- Later slices keep their **explicit GY gates** (N13b, N11, N12, first
  governed promotion, Phase-6 agent) stated per slice and in the start-now
  ladder below. GY-N13a is closed on its branch (census artifact + live-probe
  journal) pending architect acceptance; its measured result — **all three
  capstone routes recompute to `not_a_data_gap` (grounding-relation/estimand
  gaps, not row gaps)** — is already reflected in the DS7/DS15 notes below.

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

## Code-Grounded Technical State (Snapshot 2026-06-10; DS1 Recount 2026-07-16)

A deep pass over the app, the client package, and the runtime HTTP layer was
made before activation. The expected pattern — rich content, weak
orchestration — holds, but in a sharper form: **the components are excellent
and the semantics are parallel.** The dashboard is a large, tested, accessible
system that grew its own semantic universe disconnected from the runtime
authority machinery. The dominant work of this plan is therefore **rebinding
and subordination, not greenfield building.**

| Area | What exists (anchors) | What is missing / divergent | Feeds |
| --- | --- | --- | --- |
| Scale & quality infra | dashboard `src`: 908 TS/TSX, 136,827 LOC, 230 `.test` + 3 `.spec`; full frontend zone: 944 TS/TSX, 145,033 LOC, 251 test/spec files; 44 stories; 89 `shared/ui` implementation TSX in 12 families; 67 `.a11y.test`, 390 `aria-` usages, 17 e2e specs, 16 visual baselines | structural shared/UI a11y gate is currently red; route axe covers 17/22 leaf patterns; no manual-AT record or evidence storage/cadence; zero families meet the `stable` bar | DS4, DS6 |
| Typed waist | `openapi-fetch` `createClient<paths>` over generated types with auth-aware fetch and API events (`src/api/client.ts`); 4.4k-line generated TS package client; 89 OpenAPI operations: 45 surface-consumed, 7 hook-only, 37 with no dashboard call; reference shell consumes 8 overlapping operations through the package client | dashboard and reference shell use two client homes; 9 raw `fetch` calls in 5 production files outside `src/api` (Lex is no longer one); **no endpoints** for capability report, cluster map, conversions, adapter registry, public records | DS3, DS5 |
| Status semantics | 23 named + 24 inline UI-local status definitions; `DisputeStatus` defined three times as two vocabularies (`runs/domain/disputes.ts`, `shared/ui/quantity/quantity.types.ts`, `shared/ui/trust-view/trust-glyphs.ts`) | **zero authority-lattice statuses anywhere in the app**; operational and authority-adjacent states share namespaces; P04 is materially broader than the ≥8 recon inventory | DS4, DS5 |
| Evidence ontology | `quantity.types.ts`: `VerificationMetadata` (hash, status, freshness, dispute), bitemporal `TemporalRef`, `LineageRef`, `QuantityClass` (`decision`/`telemetry`/`layout`/`debug`); `ProvenanceStrip`, `trust-view` glyphs, `temporal`, `counterfactual`, `authored-text` families; compounds incl. `DecisionCard`, `EvidenceChain`, `ExplainabilityCard`, `AttributionWaterfall`, `DataFreshnessBadge` | an entire **parallel evidence vocabulary**, UI-local, not bound to runtime contracts | DS4 |
| Publication | `publicationPacket.ts` (~1.4k lines): Toulmin maps and projection normalization; three run-detail builders produce a packet and exactly one link emits a payload + public-salt 32-bit FNV hash in the URL; browser recomputation alone renders `Verified` | forgeable by construction; structural validator does not bind packet hash; private-data scan is not on the builder path; no server signing/verifier/public-record producer or persisted public dependency | DS1, DS12 |
| Authz | `/api/v1/auth/me` with 12 server permission keys; client has 15 and workspace/tab gating; selected handlers enforce tenant ownership; coarse path/role OPA is optional | **29/29 POST operations have no action-permission or step-up dependency**; resource is bound after OPA reads it; client-only collaboration permission delta ×3; fixture identity and 11-permission UI placeholder fail open; production approval accepts self-asserted reviewer/signature | DS5, DS9 |
| Offline | Workbox precaches static assets and denies API caching; IndexedDB has exactly composer drafts + promotion queue; approve/reject is the only queued mutation class and is optimistically finalized/replayed | no live state/permission/step-up/tenant/epoch revalidation; six authority-looking local caches lack tenant+user+expiry+epoch binding; cache freshness rendering absent | DS1, DS5 |
| i18n | `en`/`uk`/`ru` catalogs have structural parity; DS0 measured 2,449 string leaves each, while 80.16% of `ru` equals English; runtime capability contracts admit `en`/`uk` | **D4 RATIFIED 2026-07-16** (`7b6933770`): `uk` primary + `en` baseline + **`ru` = `legacy_continuity_frozen`, not used, not deleted**. The gate is discharged — DS5's locale/semantic-ID lint and DS12's locale claims may proceed against the ratified posture, and no slice may loosen it. Open work is mechanical, not decisional: `parity.test.ts` still enforces full en/ru/uk key parity and must move to the frozen-set rule (**DS6**, with the 3 inherited `overBudget` failures)  **D4-A1 AMENDED 2026-08-19 by architect decision, and this REVERSES D4's primary/baseline relation**: `en` is the **primary** locale and the authored source of truth; `uk` is a **translation** of it, however accurate; `ru` is unchanged as `legacy_continuity_frozen`. Reason: a translation relation makes the authored language primary and the rest derived — `uk primary` inverted that and made English content a translation of Ukrainian, which is not how this product is authored. D4's own "no slice may loosen it" stands and is why only an architect decision can amend it. CONSEQUENCE, and it inverts the follow-up work D4 anticipated: verification written against an `en` default is **restored to correctness**, not updated. DS5's `C05a-R1` implemented D4 **as ratified** and is not at fault; its 56 component, 3 accessibility and locale-driven visual failures are the ratified posture meeting verification written against the prior one. The blast radius of this amendment is measured before implementation, not assumed. | DS5, DS6, DS12 |
| Tokens / design system | `shared/ui/tokens/designTokens.ts` + `AtlasV4Reference.stories` — a living, coded v4; theming `light`/`dark`/`system` + density preferences | DS0 selects future one-way DTCG generation and sunsets hand-maintained TS authority; v15 values/modes remain unadmitted until DS2 and no migration occurs before DS4 | DS2, DS4 |
| Agent surface | `features/clerk` is an app-level interface mode over `POST /control/runs/nl`; live path launches a run and consumes SSE status only; persisted store/renderers contain structured verdict/confidence/diff and `AIDiffView` | structured response and diff have no live producer (`producer_missing`) and would launder candidates if wired as-is; duplicate direct `/` index route is redundant; G6 contracts and storage partition absent | DS1, DS14 |
| Realtime & off-contract endpoints | two real `include_in_schema=False` SSE routes; real review WS hub with three channels; collaboration client declares four REST pairs + four WS channels | review WS browser-auth bridge is absent/undocumented; collaboration server producers are absent, but the whole feature is orphaned so current live UX does not call them; every admitted channel lacks one governed registry | DS1, DS3, DS5 |
| Feature flags & shadow shipping | 12 manifest keys, all defaults true, plus auth-derived `enableReviewCollaboration`; exactly four keys have no production read | causal/command-palette/what-if surfaces remain live outside their missing flags; collaboration feature is orphaned; unknown manifest keys are ignored; DS5 must strictly separate rollout from authz and wire-or-retire four gates | DS1, DS5 |
| Observability & audit | app-wide configurable beacon plus production-only Sentry (`sendDefaultPii:false`); both attach full path/route context and arbitrary payload/extras; server-side append-only access audit, compliance export/retention, CSRF | public-route no-tracker/redaction unproven; signed IDs/run/artifact refs can enter transport context; environment supplies destination ownership; review-effectiveness telemetry not yet drawing on audit trail | DS6, DS9, DS12 |
| Discovery seeds & machine exports | `GET /control/capabilities` (live endpoint), `control/data/catalog/search`, lineage exports (`openlineage`, `prov`), artifact packet export/render, decision-validity endpoints | the capability manifest is a **hand-maintained `CapabilityFeatureInfo` enumeration** in `services/control/capabilities.py` — a live Rule-12 violation; exports cover lineage/packets, not the Layer 3 artifacts | DS3, DS10 |
| Non-web surface artifacts | `packages/cli` styleguide plus email/print/CLI/bureaucratic/glyph/motion/contrast specs | DS0 assigns them to DS2/DS3/DS4/DS6/DS8; email alone is explicitly `surface_out_of_scope` until a typed notification/privacy/delivery slice exists | DS2, DS3, DS4, DS6, DS8 |

Three consequences are folded into the slices below:

1. **DS4 is a rebinding slice, not a component-building slice.** The
   evidence-bearing primitives largely exist; what they lack is binding to the
   authority lattice and the retirement of UI-local vocabularies.
2. **DS2 adjudicates two living systems, not one archive.** The repo already
   runs a coded v4 (tokens + 89 implementation TSX in 12 families with uneven
   a11y/story evidence); v15 admission
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
- **Seeded negatives are binding task-plan inputs (Revision 3).** DS1 seeded 23
  red-first negative specs (`N001`–`N023`, indexed in the live-application
  audit). A slice that owns any of them **must implement its negatives
  red-first before rebinding or building** — a task plan that starts its
  positive work with its seeded negatives unwritten is not accepted.
- **v15 enters only by adoption-ledger ID (Revision 3).** No v15 path may
  enter a task by package/folder membership; the DS2 ledger row (verdict,
  maturity, consuming surface, rejected deltas) is the only door, and archive
  maturity labels never transfer.
- **The frontend disposition law (Revision 3; the GY-N0 dual).** Every unit of
  the existing estate is eventually **used-as-is, rebound, or deleted** through
  the DS19 disposition register — never left as a live parallel owner. A
  successor closes only when a real consumer exists AND the old owner path is
  proven strangled (the P27/P28 duals on the glass). **The register is now
  LIVE** (`architecture/atlas_surfaces/frontend-disposition-register.json` +
  standalone checker): 261 units — 15 deleted, 200 `rebind_pending`, 25
  `retire`, 16 `wire`, 5 `use_as_is`.
- **Work preservation and history discipline (Revision 3.8; the DS5 lesson — full statement
  in GY plan §3.5.13 and `AGENTS.md`).** Two incidents in one slice put **reviewed,
  completed** work where git does not protect it. Neither was a reasoning failure.
  - **Uncommitted work is not storage.** Commit at every clean boundary. A stash is a
    transient for minutes, never a place to leave work across a stop, a handoff, or a
    context compaction. DS5 left 1,236 insertions of independently reviewed plan work in
    `stash@{0}` for a whole session while a rejected commit sat at HEAD.
  - **Branch history is append-only.** No `rebase`, `reset --hard`, `reset` onto an
    ancestor, `push --force`, `stash drop`/`clear`, or any `checkout` that moves HEAD off
    current work. **One exception:** `--amend` on the immediately preceding commit you
    authored this session and have not handed to review. A `rebase` left the DS5 **worktree
    in detached HEAD** two commits behind its own branch; the branch ref never lost anything
    (its reflog is forward-only), but a full session ran against the stale HEAD. **A detached
    worktree is invisible in ordinary output** — `git log -1` and `git status --short` look
    normal; only `git status -sb` or `git symbolic-ref -q HEAD` show it, and a commit made
    there is orphaned. Verify branch attachment, not just cleanliness, at session start and
    before every commit.
  - **A validator demanding a clean tree is satisfied by committing, not stashing.** That
    fence is legitimate; stashing to clear it is how reviewed work ends up unprotected.
  - **Unexpected history is an architect stop, not a self-repair.** The reflog makes these
    recoverable; improvised recovery is how a recoverable incident becomes permanent.
  - **No plan instruction names a commit hash** — name the relationship ("the immediately
    preceding commit you authored"). The DS5 plan said in four places that `b67084dd6` "is
    amended down"; true when written, impossible after a legitimate recovery moved HEAD past
    it, and literally following it would have required the very rewrite that caused the loss.
    Architect instructions prefer **forward-only** framing ("land the reduction as a commit").
    After any history-affecting recovery, re-read the task plan for instructions that
    referenced the pre-recovery state and correct them in the next commit.
- **Verification economics (Revision 3.7; measured across DS4/DS5 and the GY-N11 lane —
  the Atlas dual of GY §3.5.7 E11/E13/E14).** These rules change **when** verification is
  paid for and **how** it is observed. They reduce nothing that is verified; a slice that
  cites them to skip a gate has misread them.
  - **Freeze the source, then review, then re-run the expensive lanes — once.** Reviews run
    against the exact source **before** the slice pays for its full gate wave. A review that
    lands after the wave re-prices the whole wave: in GY-N11 one post-freeze repair produced
    **seven** consecutive full-chain reissues, and 17 of 36 commits (47%) were pure receipt
    churn. After the freeze, a **cosmetic** finding (import order, naming, docstring) is
    recorded as debt; a **blocking** one is batched with any others so the wave is paid once.
  - **Serialize the contended resource, not the session.** Name the contended set in the task
    plan. For Atlas it is: the Playwright browser/visual-snapshot lane, the Storybook runner,
    a dev server on a fixed port, and any writer touching the same governed
    `architecture/atlas_surfaces/**` artifact. **Everything else runs in parallel** — ESLint,
    typecheck, Vitest logic files, the production build, architecture/dependency-cruiser
    checks, read-only censuses. DS4 and the GY lane both idled non-contending work through
    long runs because the rule was written without a resource list.
    **Amended 2026-08-21 after `GY-DEF20`:** the resource list above is missing the one that
    now bites hardest. `schemas/runtime_api_v1.openapi.json` **and the five generated client
    outputs it produces** are a second contended set, and they must be held by **one writer at
    a time** exactly like the register family. Two reasons, both measured. First, `GY-DEF20`
    made generated-artifact freshness a **default-on** predicate of the required gate, so a
    lane whose clients do not match a fresh generation from its own schema now fails CI where
    it previously passed in silence. Second, and worse: a git merge will happily **auto-merge**
    generated `.js` outputs into bytes **no generator would ever emit**, which is a silent
    corruption the conflict markers never warn you about. The rule that follows is absolute:
    **generated outputs are resolved by regeneration, never by conflict resolution, and an
    auto-merged generated file is treated as a conflict even though git did not mark one.** The
    contended set is therefore: the Playwright visual lane, the Storybook runner, a fixed-port
    dev server, any writer touching a governed `architecture/atlas_surfaces/**` artifact, and
    **the OpenAPI schema plus its generated client family**. Slices that declare "schema +
    client regeneration" in-slice — `DS8`, `DS15`, `DS16`, `DS17` at least — queue on that
    second token; everything else about them still runs in parallel.
  - **Measured timeouts are a slice obligation.** Measure each suite's wall time **once** and
    set explicit per-suite timeouts from that baseline. DS4 repeatedly hit the default ~90 s
    ceiling on full Vitest and full ESLint, recorded honest non-receipts, and re-ran them —
    the loop was pure loss. An **unmeasured** budget that kills a healthy run is a harness
    finding, not a product signal. (Recording the non-receipt was correct; leaving the budget
    unmeasured was not.)
  - **Delta-only re-review.** The first independent review reads the full package; **every
    re-review after a fix reads the fix delta only**, with the original findings as its
    checklist. DS4 and GY-N11 both lost reviewer runs mid-flight to quota exhaustion on
    182 KB / 220 KB packages; DS4 did it right exactly once (a 28 KB delta package) — that is
    the rule, not the exception.
  - **Silent polling.** Poll long runs without narration; report only a state change — stage
    complete with its receipt, a RED, or a stop condition — one line each. Per-minute
    "still running" prose drove ~15 context compactions in a single GY-N11 session, each one
    risking state loss and re-derivation. Heartbeat **evidence** is required; heartbeat
    **prose** is waste.
- **DS-INFRA-1 — restore incrementality where it is provably safe (Revision 3.8; measured
  2026-08-02).** Owner: **team-design / frontend infra**. **Sequence after DS5 merges** — it
  edits `apps/runtime-dashboard/tsconfig*.json` and `package.json`, which are inside DS5's
  writable fence. Not a surface slice; it ships no product change and no test change.
  **Measured on main with warm dependencies:** `typecheck` **60.7 s** — three separate
  `tsc --noEmit` runs with **no `--incremental` anywhere**, and it runs at every cluster
  boundary *and again inside `build`*; full `lint` **>7 min cold** (it does pass
  `--cache`, but `_cache` is per-worktree so **every new slice worktree pays cold once** —
  this is the wall DS4 repeatedly hit and recorded as a tooling non-receipt);
  `quantity:coverage` **10.5 s with no `--cache` at all**, and DS4 ran it constantly against
  the 75-violation debt.
  **Three changes, all content-hash-invalidated and therefore semantics-preserving:**
  (a) `--incremental` + `tsBuildInfoFile` on the three tsconfigs — the largest lever, a
  warm typecheck should fall to seconds; (b) `--cache --cache-location` on
  `quantity:coverage`; (c) move `_cache` to a shared location so a fresh worktree starts
  warm, as uv and pnpm already do at user level (their caches are content-keyed, so
  cross-branch sharing is safe by construction).
  **Explicitly declined — do not "optimize" these:** Playwright `workers: 1` /
  `fullyParallel: false` is deliberate — parallel browsers destabilize visual snapshots and
  a11y routes share dev-server state (DS5 already hit an order-dependent connector
  bootstrap); trading determinism for speed is out of scope. Cross-process reuse of the
  custom scanners' `ts.Program` is a **gated candidate**, not part of this task: a stale
  Program view is the §3.5.6-gate-2 "trusted JSON" class and needs its own measurement gate
  and fail-closed conditions (the GY-INFRA-2 Part C shape).
  **Done when:** before/after wall times are recorded for typecheck, full lint, and
  `quantity:coverage`, and **every denominator is unchanged** — same Vitest file/test
  counts, same lint diagnostic set, same architecture violations, same governance numbers.
  A single changed denominator means the change was not semantics-preserving and is reverted.
- **DS-INFRA-2 — the Atlas lane has a measured-timeout LAW and no measurement SUBSTRATE
  (Revision 3.13; measured 2026-08-11 during DS5-C13a-R3).** Owner: **team-design / frontend
  infra**. Documentation-only registration; it ships no product change.
  **The law already exists** — Revision 3.7 makes measured per-suite timeouts a slice
  obligation, after DS4 repeatedly lost full Vitest and full ESLint to the default ~90 s
  ceiling. **Nothing accumulates the measurements.** The Atlas governed gates run through
  `pytest`/`npm`, never through `tools/cli.py`, so they never enter the repository timing log —
  it holds **zero** Atlas lanes. Every executor therefore guesses its ceiling and pays for the
  guess.
  **Measured this round, in one session:** the full Atlas enforcement module was killed at
  **`393.15` s with no failures** — a non-receipt, not a red — and then closed **terminal green
  at `754.20` s** under a second, larger ceiling; several other gates additionally lost their
  terminal receipts to overlapping scanner-heavy parents. Durable measurements now in hand:
  full Atlas `754.20` s, status-retirement module `135.663` s, disposition corruption battery
  `119.66` s, production build `47.29` s, focused dashboard behavior `14.417` s.
  **This is the GY lane's `GY-DI2` in Atlas clothing, in the same week.** There, a canonical
  writer was killed twice under budgets reconstructed from a different lane while its own six
  successful samples sat unused in the log; here, a module is killed under a guessed ceiling
  because no log exists at all. `GY-INFRA-2` Part A was built to prevent exactly this, and the
  transferable statement is that **a slice obligation without an accumulating substrate is not
  an obligation** — it is a re-discovery tax paid once per executor.
  **Closure:** a durable per-lane budget substrate for the Atlas gates — measured `p95` with a
  `2 x` recommended timeout, derived from **recorded successful runs** rather than a requested
  list, with any lane observed but unbudgeted **named at the point of use** so an executor
  learns its budget is a guess *before* spending one. **Binding negatives, inherited from the
  GY ruling (`GY-DI4`):** a killed run is a **non-receipt, never a duration sample**; admission
  is **completion, not success**, so a lane whose contract declares a non-zero healthy terminal
  is budgeted from its own completed runs while a genuinely failing lane stays unbudgeted; no
  ceiling is enlarged mid-run to make a run fit. **A measured budget encodes CONTENTION and is
  valid only under comparable load** — this host is 16 GB / 8 cores and was already 9 GB into
  swap when both spreads above were recorded (Atlas `393`→`754` s, GY's N10a write
  `194.9`–`426.3` s, `1.9x` and `2.2x` on identical work), so a memory-heavy lane running beside
  a governed lane does not merely slow it: it can push it past a cap the rules then read as a
  genuine regression. Heavy lanes are scheduled, never overlapped. **Sequence:** with `DS-INFRA-1`, after DS5
  merges — but the measured ceilings above are usable **immediately** as declared, labelled
  supplied values by any slice that needs one today.
- **`P38` — a gate that turns on a proxy misclassifies exactly at its own boundary
  (Revision 3.14; defined once, in the GY plan §3.5.14, and binding on both programmes).**
  Four measured instances between 2026-08-03 and 2026-08-11, two of them in this plan's lane:
  `DS5-LINE-ADDRESS-01` binds evidence by `file:line` when the property is *which construct*, and
  **DS5's own two-fix breaker** counts rounds that change mechanism bytes when the property is
  *is the mechanism wrong* — the latter cost C21b a completed migration over an unused local and an
  assigned lambda. **Repaired breaker predicate, binding on every DS slice:** a round consumes the
  breaker when it is triggered by *evidence that the mechanism is wrong* — a failing behavioural
  test, an independent review finding, or a governed RED. A round triggered **solely by a
  non-behavioural static diagnostic** does **not** consume it, provided it changes no test outcome
  and no governed artifact byte and that is **proven**; the exemption never covers a diagnostic that
  marks real dead or dropped logic, which is a mechanism finding like any other. The existing
  "zero mechanism bytes is free" clause is unchanged.
  **Standing rule when writing any gate:** state the property, state what the implementation tests,
  and name one case where they diverge. No divergent case means the implementation is the property;
  a divergent case means the gate consults the distinguishing context or records the divergence as a
  declared, bounded limitation.
- **Baseline-relative gating (Revision 3.1; the DS19 lesson).** Where main
  carries measured inherited debt, a slice's toolchain gates are: **absolute
  green** for typecheck, production build, and every test the slice owns or
  touches; **zero-NEW-diagnostics** against the hashed baseline manifests for
  inherited debt classes (post-state ⊆ baseline; removals shrink the debt,
  additions are RED). Weakening or suppressing an authority-relevant rule to
  make a gate pass is forbidden outright. Debt manifests live beside the
  disposition register and are updated only by the slice that closes the debt.

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
2. **The live route inventory of `apps/runtime-dashboard`** (DS1 recount
   2026-07-16): 32 declared route objects, 29 effective URL patterns, and 22
   leaf UI patterns. The full tree includes `/`, `/login`, `/welcome`,
   `/public/decisions/:signedId`, `/compose`, `/runs`, compare/report/deck and
   eight run-detail tabs, `/artifacts/:artifactId`, `/evidence`, `/knowledge`,
   `/platform`, five legacy redirects, and a catch-all; two sibling index
   objects redundantly target `/`. Feature modules remain
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

`apps/runtime-dashboard` is the product strangle target and uses a local
`openapi-fetch` generated-type client; `apps/runtime-reference-shell` is a
second live consumer through the generated package class. DS3 must collapse
that two-client seam to one governed home. DS4 primitives land inside the dashboard, admitted v15 substance
replaces its pieces feature-by-feature, and the surface readiness ledger tracks
migration coverage. `apps/runtime-reference-shell` stays an intentionally
narrow read-path diagnostics tool and must not grow product surfaces. A
greenfield rebuild is rejected (P06: canonical ownership ambiguity, in code).

## Slice Sequence (overview)

Phases group slices by readiness, not by team. Numbering is continuous and
roughly chronological; the DAG, not the numbers, governs start order.

| Slice | Theme | Gate / prereqs | Phase |
| --- | --- | --- | --- |
| DS0 | Source-of-truth freeze & governing decisions | **CLOSED** (merged) | A |
| DS1 | Live application audit | **CLOSED** (merged) | A |
| DS2 | Atlas v15 adjudication | **CLOSED** (merged) | A |
| DS3 | Runtime producers & export infrastructure (GY artifact projections; one-client consolidation) | **CLOSED** (merged e451cec56: 13 typed producers, owner-receipt cache law, replay binder, channel registry, canonical client twin) | B |
| DS19 | False-substrate strangle wave + frontend disposition register | **CLOSED** (merged f9f69e807: 33 files / −4,005 LOC; register live) | B |
| DS4 | Status-grammar rebinding & test harness (12 families / 47 statuses) | **CLOSED** (merged 7f450eb7b: 89 components at 27 package / 41 rebind / 18 use-as-is / 3 retire; lint 75→0, architecture 36→0, status retirement 19→0; DTCG token projection; harness + real-panel proof) | B |
| DS20 | **Server authorization enforcement (NEW, Rev 3 — split from DS5)** | **CLOSED** (merged 03ebc1ce8: DS20 29/29-op action-permission floor + step-up + fixture-identity removal + 33-value vocabulary; DS20-B B1 Rego bridge + B2 probe identity + B4 verifier provenance closed, deployment-authority attestation architect-reviewed) | B |
| DS5 | Enforcement waist: lints, audience mapping, cache discipline, flags | **CLOSED** (merged `c77888b7c`) | B |
| DS6 | Evidence workflow & instrumentation | **CLOSED & MERGED 2026-08-22 `176276ef0`**; C13 independently verified against DS8-A's repair | B |
| DS7 | **Cycle Board** (hero) | **CLOSED** (merged `74f26ca2d`: the Cycle Board hero on a static composed-v2 seam) | C |
| DS8 | Case & evidence workspace: stage-trace drill-down (strangling) — **CLOSED & MERGED 2026-08-22 `c8fff1e0b`**; production emits only the typed unavailable arm, `family_complete` false, six declared non-closures registered in the debt register | DS7 | C |
| DS9 | Human decision integrity — **CLOSED & MERGED 2026-08-25 `fd243d1ad`**; closure contract 24/24, 65/78 unique production paths, fourteen declared non-closures in the slice plan's `## Explicit non-closure`; the concurrent-PostgreSQL reservation property is an unproven residual registered as `ds9-postgres-reservation-proof` | DS8; DS20 | C |
| DS10 | Capability discovery — **CLOSED & MERGED 2026-08-26 `f935e0c2e`**; 22/22 closure items, 48/54 paths, 14/15 rounds. All twelve DS10-owned deep-import edges closed with the release gate at exit 0 and zero DS10 delta. Carried cost recorded at merge: declaring `polisyos.core.contracts` a supported entrypoint publishes 426 exports where DS10 needed 18 — a widening that should have consumed a round and did not. | DS5 + disposition-ledger/census content | C |
| DS15 | Acquisition routes & data-pool growth surfaces — **CLOSED & MERGED 2026-08-29 `2c8e1c03c`**; 42/42 mechanism paths, 11/11 widening rounds with R08 spent on generic root admission, 25/25 closure criteria, eight declared non-closures registered. **DS15 IS THE FIRST LANDING SLICE JUDGED UNDER DS18'S ARMED FREEZE, and the freeze earned itself on its first consumer**: eleven new production files arrived outside the frozen 605 and the register named them under `landing_slice_reconciliation_required` rather than as an anonymous denominator drift. All eleven were classified from rendered behaviour — seven decision-bearing with behavioural temporal proof, four `no_render_root` on their merits, and `AcquisitionRouteDetail` honestly declared with two roots rather than one. None was left unknown and none needed an owner ruling. Census 605→616 files, 719→733 roots, obligated 77→94 as 45 direct + 49 inherited, 94 covered — verified at merge by two independent derivations, 616 by manifest and 616 by a filesystem walk under the census rule, with zero missing files and zero digest mismatches across all 616. Exactly eleven files added, zero removed, two root inventories moved and three source receipts moved; DS18's frozen evidence is untouched everywhere DS15's own edits did not move it. The Atlas suite goes 36→35 with zero branch-only failures. THE ROUND ALSO COST ME AN INSTRUCTION ERROR: I told this lane to work from a branch "rebuilt from current main" while reserving the integration conflicts for myself and forbidding an inward merge — a contradiction the agent correctly refused to resolve, stopping with a precise graph readback and touching nothing. I built the landing branch myself and the round then ran clean. | C |
| DS16 | Value, uncertainty & derived-data grammar | **AUTHORITY HALF LANDED 2026-08-21** (merged `1f03d2cda`; was `blocked_on_ds5` since 2026-08-18); grammar body deferred to a successor gated on **DS7** — `DS4` defines the grammar but does not let it land | C |
| DS17 | Confidence-ledger & risk-spend surface | DS7; **GY-N11 closed** | C/D |
| DS18 | Epoch & staleness chrome — **CLOSED & MERGED 2026-08-28 `6b8ab3455`**; C01–C07 closed, 47/44 declared mechanism paths with the overrun recorded as widening rounds 5 and 6 of 7 rather than hidden, six carried non-closures and two owner stops registered. Universal coverage freeze at `3011c9584`: 605 production files, 719 roots, 33 decision-bearing + 44 inherited = 77 obligated, 77 covered — re-verified at merge with **zero missing files and zero source-digest mismatches**, and it survives the merge because no main commit since the base touched `apps/runtime-dashboard/src`. THE SLICE SHIPPED A FALSE RECEIPT AND THEN DIAGNOSED IT PROPERLY: C02–C04 asserted green architecture guardrails while 19 deep-import creep edges stood; the withdrawal names the mechanism as command-to-predicate binding failure — an aggregate wrapper exit promoted to proof of a named subpredicate it never evidenced. All 19 edges then closed with **stable facades and zero temporary exceptions**; branch and merged main both report zero creep and the deep-import baseline was never touched. THE MERGE SURFACED A SECOND MISS, AND IT WAS MINE: DS18 added the action-guarded `runtime.run.epoch_staleness` GET without extending the hand-authored Rego mirror, `test_rego_action_resource_contracts_match_live_guarded_router` failed on its own branch, and I merged without running that file — repaired in `49e969e16`, parity now 24/24. THE THIRD FINDING IS NOW CLOSED, and it opened a fourth that mattered more. The landing red was proven but unarmed, because C07 routed the freeze coordinate to the journal while the checker arms on the register. Reopening to arm it (`f722b1140`) surfaced that DS18 had also been carrying **37 register findings and 17 enforced test failures undisclosed**, of which only the four DS5 manifest ones were declared — its C07 closeout had hand-selected six waves from category names and the full disposition checker was in none of them. All 37 and all 17 are closed; the register CLI on main is back to the single `c13_print_receipt_invalid` that predates DS18. Two were real defects, not stale rows: historical candidates are no longer invalidated by later peer-schema additions, and the protected-signing classifier no longer reads function declarations as call expressions. Under an architect ruling the slice re-anchored exactly six DS5 content bindings — the six its own edits invalidated, verified to differ in those six sha256 values and nothing else. Public surface expanded additively — 15 exports to `core.contracts`, 9 to `scientist.governance.continuous`, which becomes a supported entrypoint — regenerated through its declared command, and the auto-merged generated outputs matched the generator byte-for-byte. `atlasHealthMetrics.test.ts` holds at the three owner-blocked reds with no fourth. | C/D |
| DS11 | Trust/docs posture — **CLOSED & MERGED 2026-08-27 `4ff11db52`**; closure contract 24/24, 30/34 mechanism paths, 9/9 widening rounds, ten declared non-closures registered in the debt register (nine open, one blocked). The committed MACHINE artifact carries 343 claims: 341 blocked, 1 planned, 1 supported. Carried at merge: three inherited page-a11y failures and the inherited DS6 C13 print receipt | DS9; DS6 | D |
| DS12 | Public publication foundation | **first governed promotion through the GY-N9 gate with N11 δ-accounting and N12 epoch validity live** AND DS11 | D |
| DS13 | Accountability ledgers & transparency | DS12 | D |
| DS14 | Bounded-agent surface | **Phase-6 bounded-agent contracts closed (O-block)** AND DS9 | D |

```text
Phase A: CLOSED (DS0 ─▶ {DS1, DS2} — merged ed74537e8)
        ───── activation: SATISFIED (GY-N10 merged 7e035a426) ─────
Phase B (waist, ACTIVE):    DS3 ─▶ DS4 ─▶ DS5
                            DS19: now, parallel to DS3 (gates on DS1 evidence only)
                            DS20: after DS3, parallel to DS4 (feeds DS5, DS9)
                            DS6: after DS4 (gates all later `stable` claims)
Phase C (workspace):        DS5 ─▶ DS7 ─▶ DS8 ─▶ DS9 (DS9 also needs DS20)
                            DS10: after DS5 + ledger/census producers
                            DS15: after DS7 (+N13a accepted / +N13b live loop)
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

### Start-Now Ladder (Revision 3 — what runs when)

| Milestone | Unblocked surface work |
| --- | --- |
| **Now** (Phase A + DS19 + DS3 + DS20 + **DS4 all closed & merged**; the typed HTTP waist, the server authorization floor, and the rebound status grammar are live) | **DS5 is mid-slice and its internal queue was re-sequenced by measurement on 2026-08-11 (Revision 3.13): the `DS5-LINE-ADDRESS-01` class repair runs FIRST, ahead of `C13b-R1` and the four other colliding clusters.** The decision was made on the number, not on preference — the complete collision census found **5 of 10** remaining executable clusters touching line-bound evidence (11 files, 13 cluster-file-row pairs), so paying a stop and a re-cut five more times is worse than paying the fix once. The rule it implements is narrow: **a `file:line` reference is legitimate as navigation and wrong as binding** — a row may cite a line so a human can find the finding, and no gate may fail because the line moved. Architect measurement carried into the repair, because the landed registration does not state it: of the `182` refs carrying `:line` across `73` files in `observed_refs` + `evidence_refs`, **`173` are TS/PY (symbol-resolvable), `5` are JSON, `3` Markdown, `1` TOML** — a JSON or TOML line resolves to a key path, never to a symbol, so that is up to **four mechanisms and not one**, and under the standing sizing bar each bespoke mechanism is its own cluster. The migration denominator is the **gated** subset, not the corpus. **`DS5-LINE-ADDRESS-01` is CLOSED (Revision 3.15, verified against the branch by the architect).** `C21a` `015fb8f08` established the TypeScript reference identity; `C21b-R1` `ceccb0746` (after the append-only restore `055345536` of checkpoint `3b0b721a4`) migrated the TypeScript corpus; `C21c` `db6c4c350` migrated the gated structured refs. **Independently reproduced final census: `270` total refs, `161` TypeScript identities, `6` structured identities, `15` navigation-only `:line` refs across 11 files** — and `161 + 6 + 15 = 182`, exactly the line-bearing corpus measured before the migration, so nothing is unaccounted. **The decisive property is witnessed, not asserted:** the real migrated construct moved with **no register update** and the full validator returned no errors, while renaming that same construct returned `typescript_reference_binding_missing_or_renamed`. **Sequencing result: 10 of 13 collision pairs are migrated and the remaining three Workbox refs are navigation-only, so `C13b-R1`, `C16a-R1`, `C16b-R1`, `C17a-R1` and `C19-R1` are all unblocked on this axis.** C21c's own review round caught a real `P32`/`P37` escape before landing — a forged absolute or `..` source path passing suffix checks and binding outside the repository root — closed with a canonical repo-relative predicate and its adversarial witnesses. **DS6 runs in parallel** and owns `apps/runtime-dashboard/src/shared/i18n/**` exclusively; the register, baseline manifest, status inventory, checker, its test and the generated report stay DS5's while C21 is in flight. **DS5** remains the critical-path Phase-B lane and started with three ready inputs: DS20's 33-value server-projected permission vocabulary (audience mapping), DS4's **three typed waist debts with exact generated-client anchors and single swap modules** (see the debt table), and the Rev-3.4 §6.5 lint row (M31·M6·M29) + INT-R6 semantic-ID rule. **DS6** (evidence workflow) is also unblocked by DS4 and owns the two remaining DS4-handed evidence debts (i18n parity ×3, axe-`incomplete` contrast ×4). |
| **DS5 closed** | **DS7 Cycle Board on real capstone data** → DS8 → DS9 (with DS20); DS10; DS16's value/uncertainty grammar (ValueOuterSet is live main-tree data now). |
| **DS5-`C21` register released** | DS6 `C03`/`C04`/`C06` — the three append-only register transitions DS6 is currently blocked on. |
| **DS8 print repair + two stable captures** | DS6 `C13` governed transition, then `C14` closes DS6. |
| **GY-N13a accepted/merged** | DS15 read surfaces: connector scorecard (12-family liveness), the growth backlog (`ranking_only_not_voi`, 15 `binding_gap` residuals), route projections — noting the routes are currently **structural gaps, not data gaps**. |
| **GY-N13b closed** | DS15 live loop (approve-acquisition → world-growth → re-entry), passports/quarantine; DS16 derived-data provenance (derivation certificates, basis chips). |
| **GY-N11 / GY-N12 closed** | DS17 δ-surfaces / DS18 epoch chrome. |
| **First governed promotion** (per Rule 5, may be distant) | DS12 → DS13. |
| **Phase-6 O-block closed** | DS14 (strangles `features/clerk`). |

## Per-Slice Detail

**Phase-A rebaseline binding (Revision 3).** Every slice below is re-scoped by
the [Phase-A synthesis](../../reference/frontend/atlas-phase-a-synthesis.md)'s
per-slice **confirmed / re-scoped / invalidated** matrix and its `PI-01`..`PI-24`
actions — that document is the binding re-scope of record and task plans MUST
consume their slice's section from it (this roadmap does not restate it;
Rule 10). Effort posture per the synthesis: DS4/DS5(+DS20)/DS6/DS9/DS12/DS18
**up** (binding and enforcement are the real work); DS8/DS10/DS14/DS15 **down**
on greenfield (living substrates exist); DS3 re-cut toward client/channel
consolidation. `stable` remains unavailable everywhere until DS6 evidence
exists — the single DS2 `beta` is an evidence method and raises no component.

**Inherited baseline debt of record (measured by DS19, 2026-07-16).** Main's
measured pre-existing debts — hashed manifests live in
`architecture/atlas_surfaces/frontend-baseline-debt-manifest.json`; every
slice gates baseline-relative against them (zero NEW diagnostics; see the
doctrine bullet); only the owning slice closes and re-manifests a debt:

| Debt | Measured | Owner | Closure expectation |
| --- | --- | --- | --- |
| ~~`policyos/quantity-must-be-wrapped` lint violations~~ | ~~75 errors across 22 untouched files~~ | **DS4** | **CLOSED** (7f450eb7b): 0 errors / 0 files across C06 20 + C07 37 + C08 18 exact resolutions; the rule was never weakened; live JSON comparator passes |
| ~~Inherited Vitest failures~~ | **5 → 3.** Closed: a11y coverage census (DS4-C12 added the real companion, no allowlist), temporal-cursor (DS4-C09 injected a test clock, product time meaning unchanged). **Open: 3 i18n parity** (`panels.agentPipeline.overBudget` en/uk/ru, one file) | i18n parity → **DS6** (Ruling 2 reassigned it from DS5; register class `i18n-count-message-parity`) | **CLOSED** (DS6-C03, merge `b0249e82d`): `baseline-test-i18n-count-debt` transitions to `repaired` against C16's landed 317/317-file, 983/983-test receipt through the canonical lifecycle producer, with two frozen receipt hashes and a content-bound landed-release binding. |
| ~~**`atlas-health-metric-replay-pins-uncommitted-paths`**~~ (registered by the architect 2026-08-18 while landing DS6-C10-R2) | `atlasHealthMetrics.test.ts` used revision status as a proxy for membership in the persistence-implementation set (`P38`). | **DS6** test debt | **CLOSED by `da1ff0398`, recomputed 2026-08-22 on clean `0440f0a8d`.** The persisted snapshot directly asserts the exact ordered six-path `HEALTH_IMPLEMENTATION_PATHS` set; replay remains covered by missing-path degradation, clean-versus-absent byte comparison, and inconsistent status/path-set rejection. Fresh focused receipt: 1/1 file, 22/22 tests green. This does not promote C11: the health capability remains `implemented_but_not_orchestrated`, with `consumer_missing` and `surface_missing`. |
| ~~**`i18n-plural-rule-covers-only-`{count}`**~~ (registered by the architect 2026-08-11 while verifying DS6-C01-R1; C01's repair remains correct and C19 closes the adjacent class it never covered) | DS6-C19 independently reconciled the complete active denominator at 2,451 string leaves, 244 non-`{count}` message paths, and 360 path-variable points in each locale: 720 locale instances, 149 names, zero parse failures, point-set SHA-256 `f463ac23…a362`. The owner partition is 71 quantitative-capable / 78 nonquantitative names. Each locale's 183 quantitative point uses was manually adjudicated: four require agreement and 179 do not. The old `blocked = 1` copy fails `plural_ownership_missing`; repaired output is `1 blocked packet` / `1 заблокований packet`, with English one/other and Ukrainian one/few/many/other branches. An invented variable fails `variable-kind-undeclared`; a numeric AST use contradicting a nonnumeric declaration fails `numeric-kind-conflict`; no-agreement and existing `{count}` cases remain admitted. The nonnumeric declaration is `institutionally_supplied` and retains a bounded P37 residual: the gate cannot recompute producer types without a typed producer-to-message argument manifest/call graph. `panels.reviewCollaboration.reviewers` is explicitly `declared, unenforced`. | **DS6 / C19** | **CLOSED** (DS6-C19, `c552d5b5ccce077b24f5126deb699400263186e9`): focused parity 38/38, targeted ESLint green, dashboard app TypeScript check exit 0; `ru` remains `legacy_continuity_frozen`. DS7 Task 8 must satisfy the widened fail-closed declaration rule for new active locale copy. |
| ~~Dashboard architecture-layer violations~~ | ~~36 violations across 28 files~~ | **DS4** severing, **DS5** lint enforcement | **CLOSED** (7f450eb7b): 0 violations in *both* engines (custom checker + dependency-cruiser over 1,019 modules / 4,150 edges) via C06 13 + C09 7 + C10 1 + C11 9 + C13 5 + C18 1. Note DS4 does **not** claim an independently measured 23→0 API/app denominator — Phase A never left a provenance-bound 23-item manifest; the governed claim is 36→0. **DS5 still owes the recurrence lints** |
| Worktree tooling gap | agent worktrees carry invalid `.venv`s (Playwright/py tooling non-receipts in DS1/DS19) | ops note — every future slice prompt | slices declare their toolchain baseline gate up front (the DS19 pattern) |
| ~~**`GY-DEF20`~~ — generated-client family staleness can pass a declared fail gate** (registered by DS7 on 2026-08-20 after the `P41` exact-base falsifier; `GY-DEF19` was already taken and a complete main-tree search found no `GY-DEF20` reservation) | At DS7's immutable slice base `40ef040bd`, with GAP4 absent and the workspace bootstrapped, regenerating both OpenAPI clients left `packages/runtime-api-client/types.ts` byte/AST-identical at 8,165 fields but moved the dashboard client from 7,672 to 8,165 fields: 7,632 unchanged / 40 changed / 0 removed / 493 added. The only changed pre-existing leaf is `AuthMeResponse.permissions`, `string[]` → `RuntimePermission[]`; 39 changes are derived containers. Complete manifest census: 59 families; `apps/runtime-dashboard/src/api/types.ts` has one output owner (`runtime-dashboard-api-types`, `drift_gate = automated`, `stale_output_behavior = "fail"`), while the current package `types.ts` has **zero** output owners. Its `runtime-api-client` family lists only raw TS/JS even though the package generator also emits `types.ts` and canonical TS/JS. The ordinary architecture check validates declarations but executes family freshness commands only with `--run-generated-checks`, so the declared gate is not itself an always-entered gate. Pattern: `P37`/`P38`; inherited `team-polisyos` generated-family defect, not GAP4 or DS7 mechanism drift. | **team-polisyos** (both generated-client families and the architecture generated-artifact gate) — **RE-OWNED to the Group A executor (2026-08-20)**; `team-polisyos` has no live lane. | Register every committed output emitted by the package generator under exactly one OpenAPI-derived family; make the required closeout/CI path execute both families' freshness checks without an opt-in omission; regenerate both clients from one pinned snapshot; then corrupt one declared output while leaving source and declarations intact and prove the required gate fails. Closure also requires a clean regeneration with zero diff and a complete output-owner census with no generated client unowned or multiply owned. **PREPARATION MEASURED 2026-08-20, and it names the omission exactly.** The opt-in is `architecture guardrails check --run-generated-checks`: the flag is `store_true` and family freshness commands run **only** when it is supplied, while the core release workflow calls plain `architecture guardrails check` and therefore executes **no** family freshness check at all. Standard CI checks both current clients separately, but the package checker compares only the raw TS/JS pair, leaving `types.ts` and both canonical outputs invisible. Reconciliation: **six** emitted outputs against **three** registered; three package outputs (`types.ts`, `canonicalRuntimeApiClient.ts`, `canonicalRuntimeApiClient.js`) are declared by **no** OpenAPI family; declared-by-more-than-one is empty; declared-but-no-longer-emitted is empty. **AUTHORIZED FOR EARLY EXECUTION**: both generators already accept explicit output paths, so the corruption falsifier runs entirely in scratch and the repair is uncontended end to end — it does not wait on DS7's regeneration.  **CLOSED 2026-08-21, merged at `518e04da5` (mechanism `390c754a8`).** All six generator-observed outputs are now owned exactly once across 59 families / 444 output entries — five by `runtime-api-client`, one by `runtime-dashboard-api-types`; unowned and multiply-owned are both empty. The `--run-generated-checks` opt-in is **gone from the repository**: plain `architecture guardrails check` runs both OpenAPI families by default, so the release-gate call site at `core-runtime-release-gate.yml:242` is unchanged and fixed by the default — the defect was the default, not the caller. **The repair is wider than the brief asked, and correctly so:** a reviewer found that removing a family's manifest flag reopened the same omission one level deeper, so membership is now derived from `source_of_truth == RUNTIME_OPENAPI_CLIENT_SOURCE` independently of the flag, which is only a checked record — the class is closed, not the instance, and its falsifier is `test_runtime_openapi_client_cannot_escape_default_check_by_removing_flag`. Architect-reproduced corruption witness: both families clean against a scratch expected root, then corrupting exactly one scratch output fails `runtime-api-client` naming that exact family and path while `runtime-dashboard-api-types` stays clean, with worktree status **empty before, between and after**. Five behavioural negatives green, including the emitted-but-unregistered escape that let three outputs hide. Because the gate is now default-on it needs a provisioned Node workspace; both affected release-gate jobs gained `./.github/actions/setup-runtime-dashboard` in the same commit. **One receipt is owed and is assigned:** the gate has not been run against DS7's regenerated clients on merged `main`, because the generator pipeline moved into `packages/runtime-api-client/scripts/generate-runtime-api-client.sh` (a faithful extraction, with `uv run` narrowed to `${PROJECT_ROOT}/.venv/bin/python`). The `GY-DEF21` migration executor takes that receipt as its first act, since it advances the base anyway. |
| ~~**`GY-DEF21`~~ — generated-client line addresses remain semantic bindings in the status inventory** (registered by DS7 on 2026-08-20; `git grep -F GY-DEF21` returned zero across all 9,883 tracked PolicyOS paths at current `main` `11781974d`, and zero at immutable DS7 base `40ef040bd`) | `architecture/atlas_surfaces/status-retirement-inventory.json` carries 383 integer line-bearing leaves, including 15 generated-anchor records carrying 30 `canonical_line` / `schema_line` integer bindings. GAP4's additive two-field regeneration changed no pre-existing symbol or field, yet eight records moved uniformly by canonical `+2` / schema `+7` and made the status gate fail. This is the `DS5-LINE-ADDRESS-01` / `P38` class surviving in a second governed family: the property is generated construct identity, while the gate binds a coordinate that moves by construction. DS7's derivable census (`architecture/atlas_surfaces/generated_client_receipt_census.py --check`) reconciles 18 fully enumerated structured records / 38 integer bindings across two binding artifacts; it separately enumerates 38 navigation-only references across two other artifacts. The status command consumes the census, so completeness is gated rather than manual. | **DS5** (status inventory, checker, and pinning test owner) — **RE-OWNED to the Group A executor (2026-08-20)**; DS5 is closed and merged. | Every generated-client anchor binds a uniquely resolvable construct identity; rename or removal fails, duplicate resolution fails as ambiguous, and a numeric line remains navigation-only and cannot fail the gate merely because it moved. Forbidden closures: a longer remembered anchor list, a line-drift tolerance or range, and scheduled re-anchoring. Preserve the Atlas register-family whole-file hash contract during migration. **SPLIT RECORDED 2026-08-20: the mechanism lands now, the inventory migration lands after DS7's Task 6 client regeneration.** The mechanism — the additive owner-qualified identity role, its census consumption and its negatives — needs no regeneration and is uncontended. Migrating the inventory writes `status-retirement-inventory.json` and requires the Atlas register-family lock, so it waits for the regeneration that proves a move is green and for a free family. **Measured in preparation:** 383 integer line-bearing leaves decompose exactly as `145 line + 103 start_line + 103 end_line + 15 canonical_line + 15 schema_line + 1 current_inline + 1 ds1_inline`; 18 primary anchors reconcile with 18 independently derived; the 15 status anchors carry 30 bindings resolving to **21 distinct constructs**. DS5's `#ts-identity` v1 shape **transfers, proven by parser replay** — all 30 hints minted and validated with zero errors — but needs **one additive role** inside the same envelope, because the existing `type_property` role collapses nested properties to names like `components.status`, where the measured 47-property population collides: two candidates for `RunWorkflowNodeView.status`, two for `ScenarioRef.status`, **five** for the lineage output. Changing the existing role would invalidate DS5's 155 current identities; adding one keeps them byte-identical.  **MECHANISM CLOSED 2026-08-21 at `60f089143`, merged `518e04da5`; MIGRATION AUTHORIZED, NOT BLOCKED.** The owner-qualified role `generated_schema_property` binding `components.schemas.<owner>.<field>` is added **beside an unchanged `type_property`**, inside the existing `#ts-identity` v1 envelope. The 155 existing DS5 identities are pinned byte-for-byte at `f1ac4d933af3c980190ee9ba31faae8e823d928ea651ff6d6117ec86f5fc42e2`. Move and reorder green; rename, removal and content drift red; duplicate resolution ambiguous; mixed legacy/identity mode red; numeric lines navigation-only. The proof runs against the **real** `types.ts` and the **real** five-candidate `LineageRef-Output.status` collision, where owner qualification resolves to exactly one match — not a synthetic substitute. Both `P40` rounds were consumed and both findings repaired: canonical-alias multiplicity must be exactly one match rather than one distinct owner, and scratch replay must be a closed source universe that cannot fall through to same-named real-worktree files. `status-retirement-inventory.json` is deliberately unmigrated (**zero** `ts-identity` references). **The deferral I recorded on 2026-08-21 is spent: every resume condition is met on `main`.** Both clients carry `getDepthNCycleBoardProjection`; `dc3e50a90` is an ancestor of `main`; `fea50aadd` (DS7 Task 6) is a regeneration newer than it touching both; no generator is running; and the Atlas register family is free (DS7 released explicitly at `df0484301`, DS6 released at `71b6189de`). What made the migration look blocked is only that the Group A branch was pinned at pre-DS7 `1e78542f1`, whose own tree has **zero** occurrences of the new operation — that is a base advance, not a blocker. The migration gets its **own** `0/2` budget: it is the deferred half of a declared split, not a continuation of an exhausted one.  **CLOSED 2026-08-21, merged at `3baa666d4`** (migration `0e02b8c0b`, companion `dd3fbb58b`). The census now reports **zero legacy line bindings across the whole 18-anchor population** with an empty error set: 18 anchors, 34 construct identities, 2 recomputed absence predicates, 34 navigation hints — `status-retirement-inventory.json` at 15 anchors / 30 identities / 0 legacy, `ds4-waist-debt-register.json` at 3 anchors / 4 identities / 0 legacy. **The scope was corrected mid-flight and the correction was mine:** I first scoped this to the 30 bindings inside the status inventory, when the census had always reported 18 anchors / 38 bindings across **two** binding artifacts — a `P35` failure of enumerating within a file instead of within the population the census defines. The three missing anchors were `GenerationCycleDispositionPayload`, `DecisionGrade` and `ProjectionFreshness`, in a field literally named `generated_client_anchor`. **`DecisionGrade` was adjudicated the honest way:** it is an *absence* claim, so no identity was manufactured for a construct that does not exist — its line range is removed outright and the anchor now carries `absence_scope = canonical_module_exports_and_schema_owners`, recomputing absence over the complete canonical export set and the exact `components.schemas` owner set. **The migration is measurably worth it:** across the real `d17ecd36e → fea50aadd` regeneration `ProjectionFreshness` moved `8164 → 8936` and `GenerationCycleDispositionPayload` moved `5850 → 6520`, and at the old tree the line this register pins today held an unrelated `need_id: string;` field. The DS5 pin was re-pinned to `147` / `e297ac8d…`, renamed so no count sits in the test's identity, and its docstring records **both** supersessions — `fea50aadd` changed the bytes while holding the count at 155, `df0484301` then retired eight references — with the lesson stated in the test itself: a count-only pin would have missed the first event, so the ordered byte digest is the binding assertion. One lock window; only `ds4-waist-debt-register.json` moved (`9ff2bb71…` → `cb5f4737…`). Inherited reds unchanged: 13 status diagnostics at `511bfd68…17f9`, and the six-edge deep-import drift untouched. |
| ~~Control-plane fixture drift~~ | 2 pre-existing test failures in `tests/unit/runtime/http/test_control_api.py`-adjacent run-control paths (`DecisionMonitoringContract` rejects fixture fields; reproduced on pre-DS3 base in isolation). **Identities supplied by the architect 2026-08-21 at DS7's merge, and the denominator measured:** the two are `tests/unit/runtime/http/test_runs_api.py::test_evaluate_feedback_endpoint_persists_monitoring_report` (`400`, expected `200`) and `tests/unit/runtime/http/test_runs_api.py::test_reissue_endpoint_fails_closed_without_durable_control_plane` (`400`, expected `422 durable_worker_required`). Both enter `ctx.feedback.evaluate_run_feedback` / the reissue path in `src/polisyos/runtime/http/services/feedback.py`, which is a `DecisionMonitoringContract` consumer — the same root cause this row already names. Measured on `main` at the DS7 merge: `test_runs_api.py` is **42 passed / 2 failed of 44**, and `test_control_api.py` is **60/60 green** — so the failures are adjacent to the control API, not in it. **DS7 rediscovered these two independently and could not attribute them, because this row named no test identity.** That is the finding worth keeping: a debt row whose subject is a set of failing tests must carry the test identities, or it will be re-found and re-investigated at the cost of a lane each time. No new row is opened; this one is widened | **runtime/GY lane** (the contract's owner) — not an Atlas surface debt | **CLOSED 2026-08-26 on the attached measurement-lies branch.** Red-first attribution found stale monitoring/client fixtures and, after they were corrected, a production fail-closed ordering defect. The strict contract remains unchanged; execution policy now resolves before feedback preparation; both named identities and eight adjacent feedback/reissue identities pass; and the durable-worker 422 falsifier proves no non-read-through CAS artifact or feedback reference is mutated. |
| ~~Producer availability denominator~~ **CLOSED 2026-08-22, re-owned** | DS3 measured 5 available / 7 `invalid_source` / 1 `artifact_missing` from a worktree WITHOUT `production_data` — environment-relative fail-closed, not artifact corruption | **DS7** (first consumer) re-measures on main with the catalog mounted and records the true availability row in the readiness ledger | the Cycle Board consumes measured availability, never the worktree-relative snapshot | **CLOSURE:** DS7 closed without re-measuring; the architect re-measured against an appointed read-only `production_data` root and **re-owned** the row — struck in the debt register the same day. This plan row was left unstruck and the generated ledger caught the disagreement (`register=closed, source=open`).
| DS20-B B3 promotion CAS | promotion authorize→mutate is not atomic — DS20 binds the revision before OPA and re-verifies after (409 on drift), but no public Fabric compare-and-set producer exists; N13b owns `fabric/retrieval/service.py` | **GY / fabric lane** — expose a generic public revision-CAS primitive (the scenario-head CAS is the reference shape); DS20's HTTP consumer is ready to call it | the fabric lane lands the primitive; a follow-on wires the promotion path to it and removes the typed limitation |
| DS20-B B5 PostgreSQL linearizability proofs | step-up one-use consumption and scenario-head CAS are proven on SQLite; the real-PG harness exists but is `environment_blocked` (no local DSN/`pg_isready`/docker daemon) — `tests/unit/runtime/http/test_runtime_postgres_linearizability.py`, run with `POLISYOS_..._POSTGRES_DSN` set | **cloud verification** (the user's backend-verify environment) | the four proofs run against real PostgreSQL with a DSN; the harness reports pass, never a SQLite fallback |
| DS20-B scorecard producer provenance | the production-approval path binds a persisted scorecard before OPA and refuses cross-run/absent `run_id`, but the authoritative scorecard *producer's* provenance is configured outside the DS20 fence | **DS9** (decision integrity) / ops config | DS9 binds the scorecard producer's declared provenance into the approval decision |
| DS20-B Helm policy mirror | the Helm chart carries a separate stale copy of the OPA policy; the canonical `ops/policy/policies/**` Rego is DS20-current, the Helm mirror was outside the extended fence | **ops / deploy lane** | the deploy lane regenerates the Helm mirror from the canonical Rego (or removes the duplicate in favor of the canonical source) |
| aiohttp Fabric connector cleanup | two unclosed `aiohttp` session/connector diagnostics surface from the authorized `discover_data_sources`/`resolve_data_needs` handler witnesses opening Fabric connector pools (not a test failure; DS20 added no HTTP bypass) | **GY / fabric lane** (connector lifecycle owner) | the fabric lane closes the connector-pool lifecycle; not an Atlas surface debt |
| **DS4 three canonical-waist vocabularies** (registered 2026-08-01; the register rows carry `master_inherited_debt_action = flag_for_architect_insertion_at_c20`, i.e. this insertion) | three vocabularies the generated client does not project, each already reduced to **one** presentation-only swap module that renders novel owner labels as explicit `unrecognized` and exports no value-level constants: **CGF disposition** (`canonicalRuntimeApiClient.ts:516`; `types.ts:5850-5879` `GenerationCycleDispositionPayload`) → `shared/ui/compounds/cgfDispositionPresentation.ts`; **decision grade** (missing `DecisionGrade` export; client export block `333-394`) → `shared/ui/compounds/decisionGradePresentation.ts`; **cache-age lattice** (`canonicalRuntimeApiClient.ts:737`; `types.ts:8164-8182` `ProjectionFreshness`) → `shared/ui/temporal/cacheAgePresentation.ts`. Authority: `architecture/atlas_surfaces/ds4-waist-debt-register.json`; estate denominator effect **none** | **DS5** (waist) — **RE-OWNED to the Group A executor (2026-08-20)**; DS5 is closed and merged. | DS5 supplies each closed union through the generated client and swaps it in at the single named module; **the two negatives per module survive** (novel label → explicit `unrecognized`; module exports no vocabulary constants). Terminal kinds and evidence classes stay opaque extensions end to end — DS5 does not close or order them **THE ROW SPLITS INTO THREE DIFFERENT STATES (measured 2026-08-20). All three names return zero occurrences in the generated package client and zero components among all 351 OpenAPI schemas, but the reason differs per vocabulary and the single closure signal is not executable as written.** (1) **`DecisionGrade` — EXECUTABLE.** A real canonical union exists: `Literal["unsupported", "descriptive_only", "advisory_admissible", "decision_admissible"]` in `pdc/_impl/layer2_readiness.py`. It rides the next regeneration through a real DTO/producer bridge and must not be bound to an unrelated evaluator or closeout verdict. (2) **`CgfDisposition` — re-typed `producer_missing`.** There is no public typed server owner. A private validator carries `USE_AS_IS` / `REWORK_TO_FIT` / `DELETE` while the generation-cycle disposition payload's owners field stays opaque JSON; copying that private set into a public contract would **invent authority**. The canonical generation-cycle owner must declare the public contract first — a producer decision, not a presentation bridge. (3) **`CacheAge` — RETIRED AS SUPERSEDED by architect decision.** No server owner exists and none should: **cache age is client-local by construction** — the server cannot know how long a given browser has held a copy. `ProjectionFreshness` is a different time role and says so in its own docstring, *"Separate source time from the time the HTTP producer observed it"*; equating the two would conflate source observation with cache staleness. `DS6-C11a`/`C11b` already answered this correctly a different way, making the branded dashboard `CacheObservation` the QueryObserver-lifecycle owner of the live/cached posture. This is a debt solved better by a later slice, not an abandoned one; the executor confirms the two negatives still hold under that answer and records the retirement. |
| ~~**`run-lifecycle-terminal-fact`** — producer-signed run terminality~~ **CLOSED 2026-08-22** | `GY-GAP4` now supplies producer-owned lifecycle terminality through the core run/trace contracts, governed event contracts, `RunSummary`, OpenAPI, and both generated clients. Lifecycle terminality remains distinct from design-search `terminal_kind`. The DS7 hero consumer and its absent-not-false and no-proxy semantic negatives have not landed yet. Anchors: `runtime/http/services/adapters/core_run.py`, `canonicalRuntimeApiClient.ts:865`, `types.ts:9240/9259/9286`, `docs/superpowers/journals/2026-08-16-gy-gap4-run-terminality.md` | **DS7** — receiving first consumer and current closure owner. The runtime / GY producer route is complete through `GY-GAP4`; DS7 projects the signed fact and never owns or re-derives temporal truth | DS7 renders `RunSummary.run_terminality` without status/timestamp derivation, renders an unbound lifecycle fact as absent rather than false, and keeps the C22 semantic negatives plus DS5 ownership lint green. Novel status labels remain opaque  **NOT DISCHARGED BY DS7, AND RE-OWNED (architect, 2026-08-21 while surveying what DS7's closure closed).** Measured on `main`: `run_terminality` occurs in the dashboard **only** inside generated `src/api/types.ts` — **zero production consumers**. DS7 built the Cycle Board, which renders `lifecycleTerminality` from its own composed-v2 payload; that is a **different fact on a different surface** from `RunSummary.run_terminality`, which this row names. DS7's pass-through and absent-not-false negatives are real and green, but they discharge the board's fact, not this binding. **The distinction is the finding:** naming a slice the *receiving first consumer* of a producer fact does not make whatever that slice ships into a consumer of it — the closure signal must be re-checked against the named field, not against the slice's completion. DS7 is closed, so under Revision 3.22's debt-row execution rule this row needs a new executor; ownership of **correctness** stays with the surface that will render `RunSummary.run_terminality`, and the row is executable independently of any slice's ladder position. | **CLOSURE:** the DS7 hero consumer landed — terminality is rendered at `RunsListPage.tsx:186` by direct member access, with no proxy. Struck in the debt register 2026-08-22 at `0440f0a8d`; this plan row was left unstruck and the generated ledger caught it.
| ~~**Readiness / scientific-depth producer binding**~~ | `PublicSectorReadinessPanel` and `ScientificDepthPanel` had dashboard-local synthesis minting unsigned readiness and scientific-composition values; DS4-C23 physically deleted both synthesis graphs and renders the panels constant `unavailable` / no-input. States: `producer_missing`, `artifact_missing`, `bridge_missing`, `semantic_test_missing`. **Re-typed 2026-08-02: this is a breach of ratified `S0-K07` — projection cannot mint authority** (`docs/system-design-decisions/stage0-custody-kernel-ratification.md`); dashboard-local synthesis of an unsigned readiness value is the prohibited case exactly, and DS4-C23 **contained** it without closing it | **DS16** (already carried in the DS16 section, Rev 3.5) | every named value resolves to a generated field or a registered typed refusal, and the C23 containment negatives (two no-input panels, exactly three prop-less mounts, zero reachability to the deleted graphs, six AST corruption witnesses) remain green  **CLOSED 2026-08-21, merged at `1f03d2cda`** (DS16 authority half, reconciled at `40bbafa18`). Both conjuncts of the closure signal are met. **Every named value now resolves through a generated field or a registered typed refusal**: `GET /api/v1/runs/{run_id}/authority-values` returns the complete `RunAuthorityProjection` for the retired DS4-C23 inventory through OpenAPI and both generated client families, and the release record states the honest limitation — **all 11 inventory members are typed refusals today because no runtime producer supplies them**. That is the point: the `S0-K07` breach was projection *minting* authority, and a typed refusal mints nothing. **The C23 containment negatives remain green** — the successor suite and the authority-value MACHINE twin pass 15/15, architect-run on the merged bytes. DS16's own record declares the one residual: the successor covers 10 of 11 ancestor corruptions, with the arbitrary-i18n-key gap declared rather than papered over. The value-**grammar** body remains deferred to its successor slice and is not part of this closure. |
| ~~**`adjacent-print-export` — run-detail A4 print regression**~~ | **Institutionally supplied provenance, independently verified closure:** the committed 724×2,113 PNG was a bulk-publish placeholder never derived against this surface. DS8-A replaced that proxy with the composed semantic/PDF gate and first-derived `run-report-identity-a4-print-chromium-darwin.png` under a new name. | **DS8** repaired (`69aca1e25`); **DS6-C13** independently verified and closed | **CLOSED 2026-08-22 by DS6's independent verification.** Two separate zero-retry, no-writer Chromium runs at the same committed revision and host/browser/font tuple passed 3/3 each; the 746×84 expectation remained SHA-256 `26cca8a75e61cfcf…` before, between, and after. The independently parsed PDFs were 5 and 30 pages, all MediaBox/CropBox dimensions were portrait A4 within 0.5 pt, admitted growth increased page count, and the complete semantic egress predicate passed. The canonical row is now `rebind_pending` / `strangled` with successor `run-report-paper-projection`: this closes the run-detail predecessor only. Broad print/PNG/CSV/JSON/server readiness remains DS8-owned `rebind_pending`. |
| ~~**Four axe-`incomplete` contrast clusters** (registered by the architect 2026-08-01 — DS4 recorded them honestly in its closure/journal but left **no machine-readable row**, so this table is their authority until DS6 creates one)~~ | axe reports these foregrounds as `incomplete` — neither violations nor passes — because translucent/gradient ancestors defeat computed contrast: **C01** neutral `Badge` variant; **C06** `ProvenancePopover` + `ProvenanceMiniGraph`; **C09** `TimeSemanticsLabel` inheritance; **C14** `CandidateFrame`, `NegativeCertificateCard`, `WeakestLinkExplainer`. They are not suppressed and not counted green; the automated a11y denominator (85/85 component, 21/21 browser) is green *around* them | **DS6** (a11y evidence owner) | **CLOSED** (DS6-C04 admitted the typed row, DS6-C06 repaired it; merge `b0249e82d`): `baseline-test-a11y-rendered-contrast-incomplete-debt` covers seven source identities through three evidence refs and is bound to the landed C16 contrast release `97d0c6208`. The real-browser opaque-background probe exists at `apps/runtime-dashboard/src/test/a11y/opaqueBackgroundContrast.ts`. |
| ~~**`deep-import-baseline-stale`** — the required release gate fails on `main`~~ **CLOSED 2026-08-23 `5cc68c43e`** (registered by the architect 2026-08-21, surfaced when GY-DEF21's executor stopped at the DEF20 receipt gate) | `architecture/baselines/imports/deep_import.json` is stale on `main` `04fa1b3b0`, and `uv run polisyos-tools architecture guardrails check` therefore **exits nonzero** — the exact command the core release gate runs at `core-runtime-release-gate.yml:242` and standard CI runs at `ci.yml:151`. The checker enumerates **six** unregistered creep edges itself: `http.services.channel_contracts → core.artifacts.manifest`; `→ core.contracts.decision_validity`; `http.services.control.lex_pipeline → lex.knowledge.store`; `http.services.control.lex_search_projection → core.contracts.runtime`; `→ lex.knowledge.types`; and `scientist.orchestration.engine.checkpoint → core.security.tenant_context`. DS7's replay reported a removed side of three; I did not independently re-derive that count and it is `not_established` here. **Not caused by DS7, DEF20 or DEF21** — the four source files were last touched by the GAP4/run-terminality lane (`dc3e50a90`, `1775cf8a5`, `ec7228eff`) and GY-DEF3 (`b66bf3f82`), and DS7 replayed the identical identities at both its slice base and its Task 6 base with edge-level introducers predating it. **The reason it matters more now:** GY-DEF20 made this same command carry generated-client freshness, so one stale baseline holds a gate that two separate properties depend on, and every lane that runs the required gate reads a red it did not cause. Closing it is a **governance act, not a sync** — `guardrails sync` would silently accept six new deep-import creeps. | **runtime/GY lane** (the owner of all four source modules); approval `team-architecture` | the owner adjudicates each of the six edges — stable facade, intentional baseline acceptance with a recorded reason, or a registered temporary exception — and the plain gate then exits zero on `main` with generated freshness still clean for both families | **CLOSURE:** adjudicated edge by edge — five stable-facade routes, one intentional baseline acceptance, **zero temporary exceptions**, correctly declining a register whose 26 entries are all expired. Baseline `3,650 − 3 stale + 1 candidate = 3,648` on two independent derivations; the gate now exits zero with both generated families fresh, reproduced independently by the architect. `guardrails sync` was never run — the whole point of the row.
| ~~**`case-record-not-run-bound` — no production run closure binds a `DesignRecord`**~~ (registered by the architect 2026-08-21 after DS8's C00 stop; `git grep -F case-record-not-run-bound` returned zero across all tracked paths) | `DesignRecordV0` and `CanonicalDesignRecord` are defined and the CAS persistence helper `persist_s2_design_search_run` exists at `src/polisyos/pdc/_impl/layer2_design_search.py:1393` and is exported from `pdc/__init__.py` — but it has **zero production callers**. Architect-verified: the only two `src/` occurrences are the re-export and the `__all__` entry, and all six call sites are in `tests/unit/pdc/test_layer2_s2_design_search.py`. DS8's independent whole-tree AST census over 5,579 tracked Python files agrees at zero ambiguous parses. The artifact additionally carries no run/case/tenant binding, so even a persisted record could not be resolved from a run. Reality-bar label: **`producer_missing`** — the capability is written and unwired, not absent. **Consequence:** DS8's case-inspection half is not executable, and DS8 stopped at its own declared `artifact_missing` condition rather than adding a builder, a global index, a mock authority, or an unrelated persistence path. This is the `GY-GAP4` shape one slice later: a producer route that exists but was never told it owns the binding. **DS8 is therefore re-cut into DS8-A and DS8-B (see the DS8 block); only DS8-B waits on this row.** | **runtime/GY lane** (`team-runtime`); approval `team-architecture` | a production run closure persists a content-bound `DesignRecord` with verifiable run/case/tenant identity and declared closure roles, resolvable from a run id without a builder or a global index; **DS8-B** is the consumer **CLOSED & MERGED 2026-08-28 `d9eba546e`.** A real `POST /api/v1/control/runs` launch and worker execution now select the governed `phase2.refine.layer2_s2_design_search` operation, persist one PDC-owned run/tenant/cell/case-bound binding, and resolve it from a run id through the trusted terminal trace and verified CAS chain — no builder and no global index. **DS8-B is unblocked.** DS8 still renders the verified record while abstaining through three typed authority non-receipts; `AvailableRunPaperCase` stays fail-closed. |

### Group A generated-client seam closeout receipt — 2026-08-21

`GY-DEF20`'s post-DS7 receipt is discharged on immutable integration base
`34f4df5fb02e7681a199e191d8ff714374e4b0dd`: the plain default-on gate
reported `runtime-api-client` 5/5 clean and `runtime-dashboard-api-types` 1/1
clean against one scratch expected root, while the attached worktree stayed
byte-clean before and after. Its composite exit remained nonzero only for the
separately registered `deep-import-baseline-stale` predicate; that red remains
owned by the runtime/GY lane with `team-architecture` approval.

`GY-DEF21`'s deferred inventory half is closed on the attached Group A branch.
All 15 generated anchors migrated atomically from 30 semantic integer bindings
to 30 v1 `#ts-identity` bindings; the same 30 integers remain navigation hints,
and all 353 other integer leaves are unchanged. The real DS7 Task 6 history
`d17ecd36e → fea50aadd` resolves all identities and makes all 30 old coordinate
bindings red. The real GAP4 history `40ef040bd → dc3e50a90` resolves the eight
uniform `+2` canonical / `+7` schema moves and the seven unchanged records.
Rename/removal, content drift, ambiguity, mixed mode, and hidden navigation
metadata remain fail-closed. The census transition is exactly 0 identities / 30
legacy bindings to 30 identities / 0 legacy bindings for the status artifact.

The register-family window and the exact verification receipts are recorded in
`docs/superpowers/journals/2026-08-21-gy-def21-register-migration.md`. One
pre-existing assertion cannot honestly be repeated as closed: the integration
base already carries 147 DS5 identities with ordered digest
`e297ac8da1a63c06ad9a1e15de760cdb347395900f14d59997bbf8e0af94d5da`,
not the stale 155 / `f1ac4d…` pin. The migration does not edit the DS5 register;
the reconciliation remains with the DS7/Atlas register owner and is not
re-baselined here.

**Companion correction and complete-denominator closeout.** The preceding pin
statement and file-local denominator were both superseded by a complete census.
The ordered DS5 corpus changed twice: Task 6 kept 155 occurrences but re-anchored
the bytes from `f1ac4d93…` to `656e271a…`; Task 10 then retired eight, leaving
147 / `e297ac8d…`. The count-free DEF21 test now pins that current ordered byte
sequence, while the register bytes remain unchanged. The census's other three
generated-client anchors in `ds4-waist-debt-register.json` are also closed:
`GenerationCycleDispositionPayload` and `ProjectionFreshness` carry four v1
construct identities plus four navigation hints. `DecisionGrade` has no
construct to identify, so its ignored export-window lines are removed and its
absence is recomputed over the complete canonical module exports and exact
`components.schemas` owners; direct/re-exported/schema presence fails, while
real Task 6 movement remains green. The complete 18-anchor population is now 34
construct identities + 2 absence predicates, 34 navigation hints, and **zero
legacy line bindings**. Across `d17ecd36e -> fea50aadd`, all four present
identities resolve, all six old present coordinates lose meaning, and the two
old DecisionGrade coordinates move while the legacy checker stays green only
because it never consumed them. The single governed window and exact hashes are
recorded in the migration journal; no generated client, status identity, other
383-leaf status coordinate, disposition-register byte, deep-import baseline, or
programme-plan line 7 moves.

**Debt-row execution rule (Revision 3.22, measured 2026-08-20).** A registered
debt row with an **executable closure signal** is executable independently of
where its owning slice sits in the Start-Now Ladder. **Ownership assigns
responsibility for correctness — who adjudicates that the repair is right — not
the moment of execution.** Reading an owner as a schedule parks real, small work
behind a container far larger than the work needs, and this plan has now measured
that happening.

Two corollaries, both from measurement rather than principle:

1. **A debt owned by a closed slice must be re-owned at closure.** DS5 is closed
   and merged, and two open rows still name it: `GY-DEF21` and the DS4 three
   canonical-waist vocabularies. The second was verified still open — `CgfDisposition`,
   `DecisionGrade` and `CacheAge` return **zero** occurrences in
   `packages/runtime-api-client/types.ts`, so the generated client does not project
   them. Neither row has an executor. The architect registered `GY-DEF21` against
   DS5 *after* DS5 had closed; that is the same error stated from the other side.
2. **A co-owned row may be executed by whichever owner can act.** The
   `adjacent-print-export` row already names **DS8** for the product repair and
   **DS6** for independent visual and semantic verification. DS8 is unentered and
   gated behind DS7; DS6 is live and blocked *by this row*. The live co-owner
   executes and the absent owner's adjudication is recorded as owed, rather than the
   whole row waiting.

**Measured audit at this revision:** of the sixteen open rows remaining after the
two DS6 closures, **six name an owner that cannot currently act** — `GY-DEF21`
and the waist vocabularies (DS5, closed), `adjacent-print-export` (DS8,
unentered), the DS20-B scorecard provenance (DS9, unentered), the readiness /
scientific-depth binding (DS16, unentered and gated on DS7), and `GY-DEF20`
(`team-polisyos`, no live lane). That is a distribution, not an incident, and it
is why this rule is written into the plan rather than applied once.

**What this rule does not authorize:** re-owning a capability away from its real
owner. Routing `GY-GAP3`, `GY-GAP5` and `GY-GAP6` to the GY-N12 lane is correct
and stays — a *capability* belongs to the owner that can hold it. This rule
governs *point repairs with executable closure signals*, which are a different
object.


The five formerly-phantom dependency declarations (+ the `workbox-window`
peer) and the `audience` fixture drift are already repaired (d01eaa572) and
recorded in the register.

**DS4 closure note (merged 7f450eb7b, 2026-08-01).** The rebinding waist is live
on main. The dashboard now projects producer-owned authority, time, evidence,
provenance, and quantity semantics through rebound families and the single
`@polisyos/atlas-ui` owner, and it no longer maintains a parallel status grammar.
Three architect-level facts govern how later slices read this closure:

1. **The realized 89-component disposition is `27 package / 41 rebind /
   18 use-as-is / 3 retire`** — not the pre-Ruling-3 plan of `35 / 42 / 12`.
   Five primitives were re-adjudicated (`DropdownMenu`/`Separator`/`Sheet` →
   retired for `no_production_consumer`; `ScrollArea`/`Tabs` → `use_as_is` under
   their exact DS2 conditions), and the C15/C16 live-consumer censuses moved a
   further four. **Later slices must quote the realized split**, never the plan
   numbers: refusing to migrate a component with no live consumer, or one whose
   DS2 ledger condition is unmet, is correct behavior, not shortfall.
2. **The closure is baseline-red on purpose.** Full Vitest keeps exactly three
   DS6-owned i18n parity failures; Playwright visual is honestly 17/18 with the
   DS8 print regression red and its expectation byte-unmodified. No gate was
   weakened, suppressed, quarantined, or tolerance-widened to produce green.
   Any later slice that reports these as green is reporting a regression in
   honesty, not progress.
3. **Everything DS4 refused to build was handed over typed**, not dropped: the
   three DS5 waist vocabularies, the DS16 producer binding, the reassigned
   `run-lifecycle-terminal-fact`, the DS8 print defect, and the DS6 i18n +
   contrast evidence — all now rows in the table above, each with an owner and
   an executable closure signal.

**Merge-time finding — content-bound receipts collide across parallel slices
(architect, 2026-08-01).** DS4 and DS20 ran in parallel and both bound governed
receipts to the *same* generated client. DS20 regenerated it (`+3` lines in
`canonicalRuntimeApiClient.ts`, `+6` before the affected anchors in `types.ts`,
purely additive for the permission vocabulary); DS4 branched earlier and pinned
the pre-DS20 hashes and line anchors. The merge was code-clean, but the status
inventory went **red on main** with 2 `inventory_source_hash_drift` + 7
`generated_anchor_drift`. Resolution: the architect re-anchored the seven units
after proving the shift is mechanical — every `export_symbol` still exists
exactly once, every `field` is unchanged, and the offset is uniform (+3 / +6) —
and refreshed the two client hashes. No semantic claim, ownership, denominator,
or classification moved; the corruption probes still pass, so the receipts kept
their protective power. **Two standing rules follow.** (1) A slice that
regenerates the client — **DS5 does** — must re-anchor every governed receipt
that points into it, in the same commit; anchor drift is expected mechanical
bookkeeping, hash drift with a *changed symbol or field* is a real finding and
must stop the slice. (2) The same merge exposed that a fresh `main` checkout had
never installed the workspace, so `@polisyos/*` did not resolve and the TypeScript
scanner reported two **false** `retired_semantic_definition_survives` findings
against live replacement adapters. Generated-owner proofs are only meaningful
under an installed workspace: **run `corepack pnpm install --frozen-lockfile`
before believing any red from the status scanner.**

Independently recomputed at architect review: status governance
`47 / 15 / 55 / 0 / 3` (classifications 15 lattice-derived / 24 interaction-state
/ 8 removed); disposition register 261 roots (denominator unmoved: 15 deleted /
200 rebind / 25 retire / 16 wire / 5 use-as-is), 13 supplemental findings, 23
seeded negatives, 8 censuses; Atlas governance unittests 98/98; the baseline
manifest carries `violations: []` for lint (75 resolutions) and architecture
(36 resolutions) and exactly one open Vitest debt class. The full Vitest,
production build, ESLint, Playwright, a11y-browser, and Storybook denominators
are the slice's and its independent reviewers' receipts, not re-run at architect
review. Fence: 669 paths, zero backend/schema/generated-client/v15/frozen-locale/
CI writes; lockfile `+106/−0`, importer-only.

**DS20 / DS20-B closure note (merged 03ebc1ce8, 2026-07-20).** The server
authorization floor is live on main: 29/29 unsafe operations structurally gated,
step-up for the 6 high-stakes ops, fixture identity prohibited outside dev, the
33-value permission vocabulary projected through OpenAPI into the generated client
(consumed by **DS5** audience mapping and **DS9** decision integrity), Rego↔server
vocabulary + decision parity guards standing. The deployment-authority attestation
hardening (`c33c4d450..7fa1b5f27` — forgery / same-object-mutation / TOCTOU /
perimeter-flip / WebSocket-fall-through defenses) received architect review in lieu
of the credit-blocked final automated pass and is sound. Guardrails carry the same
5 inherited DS3 deep-import edges (owner: runtime lane) with zero DS20 additions;
the SSE order-sensitive flake is inherited and isolated. The B3/B5/scorecard/Helm
typed limitations above must clear before a production-readiness claim.

### Phase A — Pre-Activation (Layer-3-independent)

#### DS0 — Source-Of-Truth Freeze & Governing Decisions

The surface analogue of G0's discipline freeze: decisions and schemas, before
any audit or build.

Canonical governing record:
[Atlas Source-Of-Truth And Governing Decisions](../../brand/ATLAS_SOURCE_OF_TRUTH.md).

**Status (2026-07-16):** DS0 is complete on
`codex/atlas-ds0-source-of-truth` and awaits architect review. **D4 was
RATIFIED the same day** (`7b6933770`, owner `@DenisKopylov`; recorded
`ratified` in `docs/brand/ATLAS_SOURCE_OF_TRUTH.md` §D4 and pinned in the
disposition register's DS0 source block, `decision_date: 2026-07-16`): `uk`
primary Ukraine-facing, `en` baseline/fallback, **`ru` UI catalog
`legacy_continuity_frozen` — not used, not deleted** (retained in-tree,
excluded from active locale exposure and from any public locale-support
claim). The 2026-06-11 DS0 draft's "frozen-but-served" wording is superseded.
Loosening the ratified posture is out of scope for every slice.

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
  **i18n/locale evidence package and recommendation** (delivered, and
  **ratified as D4 on 2026-07-16** — `ru` is `legacy_continuity_frozen`:
  not used, not deleted; includes RTL posture and owner);
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
  against the **living coded v4** (`shared/ui` 89 implementation TSX across 12
  families with uneven a11y/story coverage, `designTokens.ts`), not into a void: every verdict is a
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
  status vocabularies** — the 23 named + 24 inline local definitions (incl. `DisputeStatus` ×3)
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

- **INHERITED OBLIGATION from DS16 (registered 2026-08-18; corrected by the architect the same day
  after measuring it against DS5's own checker) — this is a POST-MERGE reconciliation, and neither
  branch can discharge it alone.** DS16 retired `readinessScientificContainment.test.ts` and bound
  both panels, which leaves the disposition register pointing at a deleted file. The first
  registration named DS5 as owner because the pinning checker is DS5's. That is where the checker
  lives, but it is **not** a task DS5 can execute, and the end state first recorded here was **not
  satisfiable**: following it produces checker errors, not zero. Measured on
  `codex/atlas-ds5-enforcement-waist` at `94e2c8ca0`:

  | fact | anchor on the DS5 branch |
  | --- | --- |
  | `C23_ROOT_IDS` — the four rows | `check_frontend_disposition_register.py:5549` |
  | `C23_SUCCESSOR_REFS` — third entry still the retired test | `:5558` |
  | `C23_RATIONALE` — still "until DS16 provides…" | `:5563` |
  | exact-equality compare on `consumer_refs` | `:7966` |
  | generic existence check on `consumer_refs` | `:7339` |

  The anchors `:1484` / `:3410` in the first registration are **DS16-branch coordinates**; on DS5 the
  same symbols sit at `:5558` and `:7966`. Cite the symbol, not the line.

  **Why the first end state fails.** `_validate_c23_containment_roots` pins
  `disposition == "rebind_pending"` for every root and compares `consumer_refs` for exact equality;
  the generic path additionally existence-checks each `consumer_ref` under
  `rebind_pending and strangled`, and emits `successor_on_non_rebound` when a successor survives any
  other disposition. Against those three guards:

  1. Following the instruction literally — change the third ref **and** move the four rows out of
     `rebind_pending` while keeping their successor blocks — yields four
     `c23_containment_root_drift` plus four `successor_on_non_rebound`: **eight errors**.
  2. The minimal variant — change the third ref and leave the rows in `rebind_pending` — yields four
     `rebound_consumer_missing`, because `ds16SuccessorContainment.test.ts` **does not exist on the
     DS5 branch**; it exists only on `codex/atlas-ds16-value-grammar`: **four errors**.
  3. Removing the successor blocks to escape (1) contradicts the same validator's
     `successor.unit_id == C23_SUCCESSOR_ID` requirement.

  **Correct disposition.** The pair goes green only in the **merged** tree, where the successor test
  file and the pinning checker coexist. Merge order is unchanged — DS5 lands first — so the
  reconciliation belongs to the **DS16 merge**, editing DS5's checker at that point.

  - **DS5 must not touch** the four C23 rows, `C23_SUCCESSOR_REFS`, or `C23_RATIONALE`. At C20 it
    records this as a named non-claim in the closure's explicit "what is not claimed" section,
    carrying the error identifiers above, so the successor inherits a proven statement rather than a
    guess.
  - **The DS16 reconciliation** then changes the third `C23_SUCCESSOR_REFS` entry to
    `ds16SuccessorContainment.test.ts`, rewrites `C23_RATIONALE` to the delivered state — its own
    condition, *"until DS16 provides producer-signed fields or registered typed refusal"*, is
    satisfied by the registered typed refusal — and **leaves the four rows in `rebind_pending`**,
    which is what the validator requires and what the successor block presupposes. Both closure
    conditions are already established on the DS16 branch: real consumer — panels bound to
    `useRunAuthorityValues` rendering typed refusals with behavioural proof; strangled — minting
    modules deleted at `bc1d01001`, witness retired in the rewire commit, successor covering 10 of 11
    ancestor corruptions with the one gap declared.

  **Also inherited:** `census_observation_drift:census-browser-signing-protected-live:reference_count`
  is a **coordinate move, not a membership change** — `quantityDecisionProducerHarness.tsx:139 → :148`,
  byte-identical line content, count unchanged at `28`. DS16 deliberately did not bump it because DS5
  is replacing line-numbered census references with content-addressed identity tokens, which removes
  this drift class structurally; it resolves on that migration rather than by editing a number.
  **Merge ordering:** DS5 lands **before** the DS16 branch — DS5 carries `+2,372` lines of the same
  register DS16 edited (measured at `94e2c8ca0`; `+2,315` was the figure at first registration), so
  the later DS16 merges the more it costs.

- **Goal:** the laws become mechanical. **(Revision 3 re-cut: the server-side
  authorization half — per-permission deny, step-up, fixture prohibition,
  OPA resource binding — moved to DS20; DS1 measured it as systemic (29/29
  mutating operations) and it must not wait behind the status grammar. DS5
  consumes DS20's single permission vocabulary.)**
- **Gate:** DS4 (**closed & merged 7f450eb7b**); DS20 vocabulary; DS1 reports
  (cache policy). **All gates are satisfied — DS5 is the critical-path Phase-B
  lane. DS6 is independently unblocked by DS4 and may run in parallel** (its
  paths are the evidence harness and i18n; DS5 must not take DS6's work).
- **Inherited entry contract from DS4 (registered 2026-08-01 — read this before
  scoping):** DS4 hands DS5 **three canonical-waist vocabularies the generated
  client does not project**, each already narrowed to exactly **one**
  presentation-only swap module, with the generated-client anchor measured:
  **CGF disposition** → `shared/ui/compounds/cgfDispositionPresentation.ts`
  (`canonicalRuntimeApiClient.ts:516`; `types.ts:5850-5879`
  `GenerationCycleDispositionPayload` — owner JSON currently passes opaquely);
  **decision grade** → `shared/ui/compounds/decisionGradePresentation.ts`
  (missing `DecisionGrade` export; client export block `333-394` — every owner
  label currently renders `unrecognized`); **cache-age lattice** →
  `shared/ui/temporal/cacheAgePresentation.ts` (`canonicalRuntimeApiClient.ts:737`;
  `types.ts:8164-8182` `ProjectionFreshness` — source freshness stays source
  truth, cache age is never inferred from timestamps). Authority:
  `architecture/atlas_surfaces/ds4-waist-debt-register.json`; estate denominator
  effect **none**. DS5 supplies the closed unions through the generated client
  and swaps them at those three modules — **it does not invent a frontend
  vocabulary**, and the two negatives per module (novel owner label → explicit
  `unrecognized`; module exports no value-level constants) must survive the
  swap. Terminal kinds and evidence classes remain opaque extensions end to end;
  DS5 does not close or order them. DS5 also inherits the **architecture
  recurrence lints**: DS4 severed 36→0 in both engines, and the DS5 battery is
  what makes the class unrepeatable.
- **Fence authorization (architect, 2026-08-01 — granted at the DS5-C00 stop
  gate).** DS5's C00 correctly refused to widen its own fence and stopped: the
  slice must regenerate the typed client, but the original writable list named
  only `src/polisyos/runtime/http/**` and omitted both the generated snapshot in
  between and the mirrored contract tests. That omission made a *governed
  obligation* a fence violation —
  `architecture/generated_artifacts.toml` declares
  `schemas/runtime_api_v1.openapi.json` with
  `source_of_truth = "src/polisyos/runtime/http/**"`, `commit_policy =
  "committed"`, `stale_output_behavior = "fail"`, and a freshness rule requiring
  regeneration whenever runtime routes or DTOs change; the client
  (`packages/runtime-api-client/**`) in turn declares the snapshot as *its*
  source of truth. Both ends of that chain were writable and the middle was not.
  **Now admitted, narrowly:** (a) `policy-engine/schemas/runtime_api_v1.openapi.json`
  **exclusively through the registered exporter** (`regenerate_commands` in
  `generated_artifacts.toml`) — any hand-authored diff to any `schemas/**` path
  is a STOP; (b) exactly five existing mirrored tests under
  `policy-engine/tests/unit/runtime/http/` —
  `test_authorization_audience_denials.py`,
  `test_runtime_permission_vocabulary.py`, `test_governed_projection_api.py`,
  `test_governed_projection_service.py`,
  `test_runtime_api_contract_hardening.py` — edited only for the DS5 HTTP/schema
  contract, in the same commits as their HTTP models and generated output. Any
  sixth backend test path is a STOP. Verified disjoint from the concurrent GY
  `runtime/quality` lane.
- **Enforcement-mechanism ruling (architect, 2026-08-02 — binding on every DS5
  lint).** DS5-C01 was stopped after three independent NO-GO reviews, each
  finding a *new* bypass class in a whole-program TypeScript dataflow analyzer
  (points-to, heap identity, CFG, abrupt completion, closures, HOFs — 1,609
  scanner lines). Three reviews finding three new classes is not an
  implementation-quality signal; it is proof the **mechanism** is wrong. Deciding
  "no unauthorized value reaches this sink by any path" is undecidable over real
  TypeScript, so a scanner that claims that invariant is P31/P33 — an optimistic
  completeness envelope that licenses false confidence.
  **The sound mechanism already exists and DS4 built it.**
  `packages/atlas-ui/src/primitives/AuthorityBadge.tsx` defines
  `AuthorityPresentation` as a branded type keyed by a **module-private, never
  exported** `unique symbol`; `createPresentation` is module-private; only three
  exported factories issue it, each deriving clothing from a *generated owner DTO
  field* rather than a caller-selected tone; runtime guards reject
  `fixture_only`, reject labels absent from the owner list, `Object.freeze` the
  result, and record issuance in a `WeakSet`; exhaustiveness is already compiled
  in via `satisfies Record<OperatorProjectionLabel["state"], BadgeTone>`. A raw
  unauthorized string therefore **cannot** be assigned to
  `AuthorityBadge.presentation` — TypeScript's assignability check, which *is*
  sound, rejects it regardless of how the value flowed. The decisive evidence is
  the third reviewer's own refutation witness: all six carriers (dynamic-key
  spread, computed key, assignment destructuring, component alias, `Array.map`,
  module-level JSX) require an explicit `cast(...)` assertion to reach the sink.
  That is the brand working, defeated only by an enumerable escape hatch.
  **Therefore every DS5 lint is re-cut onto this shape:** put the obligation in
  the **type system** (branded authority values, module-private issuers,
  compile-time exhaustiveness against generated unions) and let `tsc` be the
  enforcement engine; reduce the bespoke checker to **decidable, local, syntactic
  invariants** — the brand is constructed only inside authorized modules; no
  `as` / `as unknown as` / `any` / `@ts-ignore` / `@ts-expect-error` / unsafe
  `satisfies` on authority paths except through *typed, enumerated* exemptions;
  adapters bind exhaustively and return explicit `unrecognized` for runtime-novel
  values. **State the residual honestly:** the brand is compile-time, the
  escape-hatch lint is syntactic, runtime novelty is the adapters' job — DS5
  claims those three, and does not claim a complete flow invariant. No DS5 lint
  may reassert one.
- **Execution-order law (architect, 2026-08-02 — added after the ruling above was
  over-applied).** The mechanism ruling binds each lint **when that lint is
  built**; it is not a licence to re-derive the whole plan before writing code.
  Read literally as a task, it produced a session with **zero net output**: the
  slice plan grew 1,104 → 1,902 lines across ~15 independent plan reviews while
  HEAD stayed on a rejected commit and the work sat in a stash. That is the
  *over-specified-contract gravity well* and P01 contract-only capability — the
  exact anti-patterns this programme distilled. Three rules follow, binding on
  every Atlas slice.
  **(1) Re-derive at entry, not ahead.** A cluster's mechanism re-derivation
  happens in that cluster's own commit, when it is entered. Planning a cluster
  you are not about to execute is deferred work, not progress.
  **(2) Plan-only commits are capped.** After a slice's C00 is committed, a
  plan-only commit is allowed **once** per architect ruling that forces one.
  Every other commit must change product or test code. Plan prose has no
  fixpoint — code does (its tests pass) — so unbounded review of a document
  converges on nothing. Independent review remains mandatory for **code**;
  for plan text it is **one round**, scoped to the cluster about to be entered.
  **(3) A downstream owner gap never halts upstream clusters.** Pre-sized
  clusters exist to execute independently. When cluster N hits a canonical-owner
  gap, record it as a typed integrate-debt row with its owner and closure signal,
  **defer cluster N**, and continue with the clusters that do not depend on it.
  Halting the slice is correct only when the gap blocks the cluster actually in
  hand.
- **Producer & bridge work (in-slice):** the **audience↔permission mapping**
  over DS20's server-projected vocabulary; the three waist unions above;
  weakest-boundary/status composition exposed in the schema where not yet
  projected; client regeneration through the registered exporter.
- **Deliverables:** the `[to build]` lints from laws 8/9/10/12 —
  unauthorized-status-enum lint, no-hand-written-authority-fetch lint (the 9
  known production calls in 5 files are its first targets, with typed exemptions
  for sanctioned auth/flag/telemetry adapters), capability-menu lint,
  duplicate-label/static-copy lint; **cache/staleness rendering rules**
  implementing the DS1 policy (cached payloads carry as-of; authority actions
  barred from the offline queue or carrying an explicit revalidation protocol —
  `useQueuedPromotionDecision` is the first migration; tenant/user/expiry
  partition on the six authority-like local stores DS1 found); **the D5 flag
  registry** — one strict exposure registry, unknown-key rejection,
  wire-or-retire for the four `consumer_missing` flags, rollout hard-separated
  from authorization; server-side **deny tests** per audience class (over
  DS20's enforcement).
- **Laws:** 8, 9, 10, 12; 11 (audience enforcement half).
- **Negative controls:** a UI-defined status enum turns the lint red; a
  hand-written fetch to an authority endpoint fails CI; a PUBLIC-class request
  for REVIEWER data is denied server-side in a contract test; an authority
  action enqueued offline fails its negative test.
- **Distillation augment (Rev 3.4, post-DS4; §6.5 · M31·M6·M29 — the manifest row
  previously unapplied):** the lints enforce **weakest-boundary composition into the ONE
  lattice** — a composed status is the minimum over its load-bearing inputs, a passing lane
  can never lint-silently compensate a failing one, and a veto (`blocked`, rights-bar) can
  never be averaged away in any client-side aggregation; **recompute-not-pin** becomes
  mechanical — a status trusted by presence (pinned, cached without as-of revalidation,
  copied between stores) turns the lint red, extending the DS1 cache policy from payloads
  to statuses. **Research input (INT-R6):** the duplicate-label/static-copy and i18n
  enforcement anchor on **canonical semantic IDs, never string comparison**; a translation
  that upgrades a status's semantic strength (`limited` → "confirmed with caveat",
  `may_not_use_for` → optional recommendation) is the red-first negative of the locale
  lint. **D4 is ratified and D4-A1 amended it on 2026-08-19**, so this lint is
  unblocked and anchors on the amended posture: `en` authored primary, `uk`
  translation, `ru` `legacy_continuity_frozen` — a lint or exemption that re-exposes `ru` as an active
  product locale is itself a red-first negative.
- **Not yet:** enforcement covers the waist and existing strangled panels;
  un-migrated legacy features carry honest lint-debt entries in the ledger.

#### DS6 — Evidence Workflow & Instrumentation

- **Goal:** the machinery that makes "stable" and "honest" measurable —
  gates every later `stable` claim.
- **Gate:** DS4 (harness) — **closed & merged 7f450eb7b; DS6 is unblocked.**
- **Inherited entry contract from DS4 (registered 2026-08-01):** DS6 owns the
  two evidence debts DS4 refused to absorb. **(a) Three i18n parity failures**
  (`panels.agentPipeline.overBudget` en/uk/ru in
  `shared/i18n/parity.test.ts:88` — count-sensitive message without ICU plural
  syntax or an allowlist entry). Ruling 2 moved this class from DS5 to DS6; the
  register class is `i18n-count-message-parity` and the baseline comparator
  accepts exactly these three signatures. **(b) Four axe-`incomplete` contrast
  clusters** — C01 neutral `Badge`; C06 `ProvenancePopover` +
  `ProvenanceMiniGraph`; C09 `TimeSemanticsLabel` inheritance; C14
  `CandidateFrame`, `NegativeCertificateCard`, `WeakestLinkExplainer`. These are
  neither violations nor passes: translucent/gradient ancestors defeat computed
  contrast, so axe returns `incomplete`. DS4's automated a11y denominator
  (85/85 component, 21/21 browser) is green *around* them and does not count
  them green. **DS6 lands the real-browser opaque-background probe** that
  computes a WCAG-AA result for each named identity without attributing an
  `incomplete` node to the source — and **creates the typed register row**,
  since DS4 left this class as prose only and prose does not survive a census.
  DS6 also owns independent visual + semantic verification of the DS8-owned
  `adjacent-print-export` regression.
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
- **Research-input augment (Rev 3.4, post-DS4; INT-R3):** the honesty-comprehension
  protocol is the seed of the Wave-2 `AuthorityUIComprehensionBenchmark` — when that
  research lands, the reviewer-task procedure upgrades from "find the weakest link" to the
  **behavioral** battery (`false_action`, `false_pass`, `missed_blocker`,
  `unsafe_override`, time-to-correct, confidence-vs-correctness calibration; `unknown` ≠
  zero ≠ missing; `incomparable` = no-admissible-ranking; refusal of stale/quarantined —
  under keyboard-only, screen-reader, low-numeracy, time-pressure) and its thresholds
  join the `stable` bar for every **interactive authority surface** (DS7/DS9/DS15–DS18).
  DS6 owns the instrument; the benchmark's content arrives from INT-R3, not invented here.
- **Not yet:** no product surfaces; DS6 measures, it does not ship screens.
- **CARRIED DEBT (Rev 3.18, recorded 2026-08-18) — DS6's executable set is exhausted and the
  slice is `blocked_on_another_plan`, NOT closed.** `C14`, its own closure cluster, is deliberately
  unentered: closing it while executable work waits elsewhere is the overclaim this slice exists to
  prevent. Landed through `C10-R2` at `fa1f3e4d0`. Three debts survive the slice and each has a
  named owner, so none of this is re-derived when DS6 reopens:
  - **`C03`/`C04`/`C06` wait on DS5-`C21`.** The governed writes stay descriptive until the register
    owners are released. They then run as three separate append-only transitions, each rereading
    current owners and content-hash anchors at entry.
  - **`C13`'s governed transition waits on DS8** — a print repair, an independently established
    semantic-non-overlap result, and two consecutive stable no-update captures. `C13`'s verification
    half is already landed; only the transition is held.
  - **`transitive-runner-closure-unbound` is `absent/unallocated`.** `observed_by_reconciler` attests
    intake closure, not runner integrity under local code modification. Closing it needs an
    out-of-band runner identity; a falsifier over all `9,870` tracked files found none in this
    repository, so the label is earned rather than assumed.
  - Also open under their own owners: the `atlas-health-metric-replay-pins-uncommitted-paths` test
    defect in the inherited-Vitest row above, the `scenario composer dark theme` visual-lane
    instability, and the DS8 A4 print baseline.
  **Order on reopening:** DS5-`C21` → `C03`/`C04`/`C06`; DS8 repair → `C13`; then `C14` closes DS6.

- **C13/C14 closeout supersession (2026-08-22): DS6 is CLOSED.** Revision 3.24's
  three register transitions and C19 were already merged; DS8-A then supplied
  the missing paper repair at `69aca1e25`. DS6 independently recomputed every
  C13 predicate twice at bound product revision `0440f0a8d`: both no-writer
  browser invocations passed 3/3 with the same committed host/browser/font
  tuple; the governed PNG hash was identical before, between, and after; PDFs
  were 5 and 30 portrait-A4 pages within 0.5 pt; admitted growth added pages;
  and the complete report/overview/DOM/link/MACHINE/font-ready conjunction
  passed. The canonical transition therefore strangles only
  `adjacent-print-export` to `run-report-paper-projection`; the broader DS8
  export unit stays `rebind_pending`.
- C14's targeted closeout matrix passed the full register corruption probes,
  C13's 8/8 focused transition tests, readiness reconciliation at 33/33, the
  complete generated-client census, the 217-row/217-unique-path DS8 strangle
  census, and the one-to-one 18-screenshot/18-PNG census. The inherited status
  predicate remains exactly 13 diagnostics / 887 bytes at
  `511bfd68…17f9`. Architecture freshness is clean for all six generated
  outputs; the separately owned `deep-import-baseline-stale` predicate remains
  red at its same six edges. Neither completed inherited red is relabelled
  green.
- DS6 closure does **not** close
  `transitive-runner-closure-unbound` (`absent/unallocated`), the scenario
  composer dark-theme instability, or the broad DS8 export family. C17 stays
  unentered because C18 superseded it. C11's test debt is closed, while its
  health capability remains `implemented_but_not_orchestrated`,
  `consumer_missing`, and `surface_missing`; C12's content, observations, and
  thresholds remain `not_established`.

### Phase C — Workspace Surfaces

#### DS7 — Cycle Board (the hero surface; supersedes "proving-ground board")

- **Goal:** the REVIEWER/EXPERT board — the interface that is proud to say
  "we do not know yet", **and shows exactly what it would take to know**.
  Revision 2 upgrades the hero from the static 13-case board to the living
  board of the GY cycle.
- **Gate:** DS5. **Producer input closed by `GY-GAP4`:** `RunSummary` now
  carries the producer-owned lifecycle fact through OpenAPI and both generated
  clients. A missing binding remains `not_established` and must render absent,
  never `false`. DS7 is the first consumer and now owns the remaining
  consumer/surface/semantic-test debt. **DS7's own negative control: the board
  may not re-derive terminality** from status substrings, `finished_at`, or any
  other proxy — a re-derivation attempt turns the C22 semantic negatives red.
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
  **Revision 3 (the N13a lesson):** the pattern generalizes beyond data
  fetches — GY-N13a recomputed all three capstone routes as
  `not_a_data_gap` (grounding-relation / estimand-binding gaps, not row
  gaps). The board's "missing link" column renders **whatever the typed gap
  is** (a grounding relation, an owner lever, an estimand binding, OR a data
  need), each with its owning route — and never launders adjacent row counts
  into support for a structural gap.
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
- **DS7 branch closure (2026-08-21; no plan revision assigned):** the static
  v2 board is the sole human renderer and its MACHINE download preserves the
  exact response bytes. The real rendered-DOM decoder closes the semantic
  parity test with dropped-row, duplicate-row, defaulted-absence,
  omitted-source, fabricated-movement, and localized-raw mutations. GAP5 and
  GAP6 render as typed `not_established` absences with their owner routes and
  closure signals; known membership stays non-exhaustive and movement stays
  honestly empty. The surface renders owner-supplied terminal, structural,
  source, accounting, and bound planner-economics values, but policy substance
  remains refusal/gap-shaped: it renders no policy quantity, effect, or
  welfare value. DS16's stated value-surface re-entry condition is therefore
  **not satisfied**. The gate remains `runs.review`, audiences remain
  REVIEWER/EXPERT, and no PUBLIC claim is made.
- **DS7 verification standing, carried not closed (architect, 2026-08-21 at
  merge `74f26ca2d`).** The slice was merged on verified mechanism; two
  measurements did not complete and are recorded as unmeasured rather than
  green:
  - **Full dashboard ESLint is a non-receipt across four attempts** — three at
    a fixed 120 s ceiling and one at 300 s, each interrupted by its controller
    having emitted zero diagnostics. No ceiling was widened mid-run and no
    partial result was admitted, which is the correct handling; the consequence
    is that the whole-app lint population is **neither pass nor fail** at this
    merge. The exact Task 8 and Task 9 write-set lint receipts are green, so
    what is unmeasured is the population outside DS7's write set. Any lane that
    needs a whole-app lint receipt must take it on an uncontended host; it is
    not inherited as green from here.
  - **Raw-v1 API byte parity remains an environment non-receipt** — this
    worktree has no `production_data/manifest.json`, so the owner packet is a
    real `invalid_source` without the four replay pins. No mock, root-checkout
    read, or weaker tuple was substituted. This is the same standing environment
    gap the *Producer availability denominator* row already carries; it is not a
    DS7 finding.
  - Task 6's atomic generated commit has a 283,577-byte raw patch and its
    contemporaneous record did not preserve per-review-package byte breakdowns,
    so Task 6 per-package size compliance is **`not_established`** — not
    inferred from the later Task 8/9/10 review layout, which was individually
    bounded below 28 KB.

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
- **Inherited debt from DS4 (registered 2026-08-01):** the
  `adjacent-print-export` run-detail A4 print regression — the global
  `a[href]::after` print rule emits the full long signed public-decision URL
  into the report, overlapping content and preventing a stable capture
  (expected 724×2113, actual 770×13229). DS4 left the committed expectation
  **byte-unmodified** and reported the visual suite honestly as 17/18 rather
  than re-baselining a defect into green. DS8 owns the product repair; DS6
  owns independent verification. Closure signal: no generated link URL overlaps
  the report **and** two consecutive no-update real-browser A4 captures are
  stable.
- **ENTRY QUESTION FOR DS8, with a starting hypothesis and NOT a decision (recorded
  2026-08-20 after the DS6 diagnostic).** The `adjacent-print-export` cause recorded in
  the bullet above is **measured false** and is superseded here rather than rewritten.
  Three things were established by no-writer measurement and DS8 should not re-derive
  them:

  1. **The signed URL is not the cause.** Suppressing only the 17,206-character signed
     target moves the capture from `770×13269` to `770×12966`; suppressing *every* link
     target reaches `770×12918`. It contributes ~303 px of roughly 10,850 excess, and it
     cannot explain the width at all — pseudo-content cannot change an element's border-box
     width. DS6 landed the narrow signed-target exclusion; ordinary printed destinations
     are preserved.
  2. **The `724×2113` expectation was never a capture of this surface.** All five A4
     snapshot names were assigned the same 231,141-byte blob in bulk commit `45f330235`;
     four have since been re-derived to distinct dimensions and pass, while `run-detail`
     still holds that original blob. Independently: `.atlas-shell-frame` computed
     `100vw − 24px = 770px` from `3535d89f` on 2026-03-10, six weeks *before* the snapshot,
     so a 724-wide PNG cannot be a capture of a 770-wide element. Deriving a replacement is
     therefore a **first derivation**, not a re-baseline.
  3. **The real regression is print-visible interactive chrome.** `3f7af28e59` (2026-05-01)
     introduced `OperatorCraftPanel` — its own source calls it *reviewer workflow chrome* —
     and `AmbientTelemetryHud`, mounted at `RunDetailLayout.tsx:793`, neither print-hidden,
     although `print.css` already defines a chrome-exclusion boundary. A printed decision
     report containing forms, sliders, buttons and wallet actions is wrong on its own terms,
     independent of any pixel count.

  **The question DS8 must answer:** *what does a printed decision report contain from a
  mixed-content panel?* `OperatorCraftPanel` is not affordance-only. A complete source
  census found seven control sites **plus** persisted reviewer annotations, threshold state
  and impact values, saved evidence references, and onboarding audit state. And
  `AmbientTelemetryHud` is not separable overlay chrome: it holds
  `operatorCraftVersion`/`refreshOperatorCraft` and therefore *mounts* the panel, and it
  builds the signed public decision packet. Excluding it takes the panel with it.

  **Three answers, with their costs.** Exclude the panel wholesale — cheap, and it discards
  real report and audit content from paper. Leave it as-is — prints affordances, wrong by
  construction. Split it, so persisted state prints and affordances do not — more work,
  because it requires marking inside the panel what is state and what is control.

  **Starting hypothesis, explicitly not a ruling: the split.** It is where the architect
  would begin, for two reasons: printing values while suppressing the buttons that set them
  is ordinary print practice, and this codebase **already encodes that principle** — the
  `print.css` chrome-exclusion boundary lists `nav`, `aside.dashboard-shell`,
  `.app-sidebar`, `[data-a11y-overlay]`, `[data-print-hidden]`, and the two panels were
  simply never brought under it.

  **This is a base for the search, not its conclusion.** DS8 is expected to test it and may
  well find better. Reasons it could fail: some of the panel's state may be browser-local
  and genuinely out of scope for paper, which the DS6 census deliberately did **not**
  classify; the split may require a boundary the panel's structure cannot express without
  restructuring; or the honest answer may be that the run-detail print surface needs a
  distinct paper projection rather than a filtered screen tree. If a fourth answer fits the
  evidence better, take it and record why the split lost.

  **Also unresolved and DS8-adjacent:** whether a full-element raster of an unbounded-height
  surface is a valid governed expectation at all, or a `P38` gate that cannot distinguish a
  regression from legitimate growth. It failed for six weeks while pointing at the wrong
  cause. DS6 was stopped before adjudicating it; the candidates recorded are a paginated PDF
  under `@page size: A4` asserting page count and geometry, a bounded-region capture,
  semantic DOM invariants, or dimensions with a declared tolerance and growth policy.

  **BASELINE MOVED BY DS7 — every pixel figure above is pre-DS7 (recorded by the architect
  2026-08-21 at the DS7 merge).** DS7's strangle removed the stale in-panel run-detail
  renderer, which changes this same screenshot payload. DS7's serialized visual lane
  measured the run-detail A4 capture at **`770×12949`, 704,292 differing pixels**, against
  the unchanged committed expectation `724×2113`. DS7 did not update this block — correctly,
  since DS8 is not its slice — and it did not relabel the red or re-baseline the snapshot.
  Three consequences, and DS8 must not compute on the old numbers:

  1. **The entry question's arithmetic is stale.** Point 1 above reasons from `770×13269`:
     suppressing the signed target reaches `770×12966`, suppressing every link target reaches
     `770×12918`. The post-DS7 baseline of `12949` already sits **below** the
     signed-target figure and only **31 px** above the suppress-everything figure. Those three
     deltas must be re-derived at the post-DS7 base before any of them is used as evidence.
  2. **The hypothesis is untouched, and weakly corroborated.** DS7 removed print-visible
     interactive chrome and the capture fell by roughly 320 px — the same order as the entire
     ~303 px signed-URL contribution DS6 measured. That is consistent with point 3's claim
     that chrome, not the URL, is the regression. It is corroboration, not proof: DS7 removed
     a renderer for its own reasons and no controlled comparison was run.
  3. **Two pre-DS7 figures already disagreed, and neither is DS7's doing.** The inherited-debt
     bullet above and the debt-table row both record actual `770×13229`; Revision 3.22 and
     point 1 of this entry question record `770×13269`. That 40 px gap predates DS7 and is
     unexplained — most likely two captures at different commits recorded as one value. DS8
     inherits **three** superseded numbers, not one, and its first derivation should establish
     the post-DS7 value itself rather than reconcile the historical pair.

  **AMENDED at the DS6-C19 merge `fffd9013a` (2026-08-21): there are four states and three
  are measured.** DS6's scoped signed-target suppression (`1fc07ed01`) and DS7's strangle
  are now **both** in `main`, and no capture has been taken on that combination:

  | tree | A4 actual |
  | --- | --- |
  | neither change | `770×13,269` |
  | DS6 scoped repair only | `770×12,966` |
  | DS7 strangle only | `770×12,949` |
  | **both — current `main`** | **`not_established`** |

  DS8 must **measure** the fourth cell, never derive it. The `303` px signed-target
  contribution and the roughly `320` px of removed chrome were measured against different
  baselines, and nothing establishes them as disjoint layout regions, so subtracting them is
  arithmetic dressed as evidence. This does not change the verdict: the `724×2113`
  expectation is a placeholder, and a placeholder is wrong at all four heights.

- **Negative controls:** closed-case views pin versions (law 7) and a mutation
  attempt fails; P15 negatives land on any engine-output panel the audit
  flagged.
- **DS8 IS RE-CUT INTO DS8-A AND DS8-B (architect, 2026-08-21, after DS8's C00
  stop).** DS8's approved plan declared one canonical stop — *if C01 cannot resolve a
  real bound `DesignRecord` from the run artifact closure, stop with `artifact_missing`*
  — and C00 fired it on evidence I re-verified: the persistence helper
  `persist_s2_design_search_run` exists and is exported but has **zero production
  callers**, its six call sites are all in one test file, and the artifact carries no
  run/case/tenant binding. That is registered as `case-record-not-run-bound`
  (`producer_missing`, owner `team-runtime`).
  **The stop was correct and the slice-wide halt it implied was not.** Only the
  case-inspection authority depends on a bound `DesignRecord`; the rest of DS8 does not,
  and two other slices are queued behind the half that does not.
  - **DS8-A — executable now.** The distinct server-owned paper projection through
    `/runs/:runId/report`, the composed A4 expectation replacing the `P38` full-tree
    raster, the complete print/MACHINE egress closure, the support-only rebind of the four
    artifact/evidence components, `RunSummary.run_terminality` consumed by `RunsListPage`,
    and the 145-path register map. The case/DesignRecord section of the paper packet
    renders as a **typed unavailable**, which is this system's standing pattern and not a
    workaround — DS7 shipped `not_established` absences as first-class facts, and DS8's own
    producer list already contains a "typed available/unavailable response".
  - **DS8-B — blocked on `case-record-not-run-bound`.** The case-inspection endpoint, the
    resolver, the Case Workspace view and its MACHINE twin. Re-enters when the registered
    row closes.
  **What this unblocks:** DS6's `C13` needs the print repair, an independently established
  semantic non-overlap result, and two consecutive stable no-update captures — **none of
  which touches a `DesignRecord`** — so DS6 and then `C14` stop waiting on a producer gap
  they never depended on. `adjacent-print-export` is DS8-A's to repair. DS9 stays gated on
  DS8-B.
  **The general lesson, and it is mine:** a correct stop condition can still be scoped
  wider than the dependency that justifies it. A canonical stop should name **which
  clusters** it halts, not the slice — otherwise one missing producer parks every
  deliverable that never needed it, including deliverables other slices are waiting on.
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
- **Distillation augment (Rev 18, post-DS4; §6.5 · M34·M37):** render the **GY-PA2** delegation
  packet as a **pre-action gate**, not a post-hoc log — identity ∩ permission ∩ mandate-bounded
  delegation ∩ envelope ∩ live accountability; a wrong-role or expired-TTL approval, and a
  search-authority reused for `data_request`, both render `blocked` with reason. Contestability is
  **proven, not gestured**: an "Appeal here" control bound to no case, and a rubber-stamp review
  (reviewer independence / change-authority absent), both fail red.
- **Not yet:** delegation-chain UI now lands via **GY-PA2** (superseding the base deferral); no
  public rendering of decisions (DS12).

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
- **Identity augment (Rev 3.4, post-DS4):** the posture story is anchored in the
  **ratified identity** (`docs/system-design-decisions/policyos-identity-and-custody-boundary.md`):
  the public copy states what the system IS — the epistemic custodian of policy
  justification (grounded design or costed refusal; signatures kept honest over time) —
  and what it is NOT (the binding anti-roles: not an administrator, executor,
  case-management system, court, notification channel, payment system, or CRM —
  **seven**, as the ratified identity document binds them; this plan said six until
  DS11 derived the set from the document with two independent parsers). The claims
  register carries the custody promise as a first-class claim family: "every published
  signature is watched for staleness and superseded, never silently edited."
- **Negative controls:** P05 negative — copy that upgrades `planned` or
  `candidate` to `supported` fails the claims-register check; posture copy implying an
  anti-role capability (e.g., "manages your cases") fails the identity check.
- **Not yet:** no grounded-performance claims until the runtime earns them.

#### DS12 — Public Publication Foundation

- **Gate (constitutional, re-stated in Revision 2; research inputs added in
  Rev 3.4):** the **first governed promotion** exists — a design promoted through the
  GY-N9 gate with GY-N11 δ-accounting and GY-N12 epoch validity live — **and** DS11,
  **and** the Wave-2 research inputs that must close **before the first public record,
  not during it**: `INT-R7` (public-verification key lifecycle: rotation, revocation,
  archival verification, anti-equivocation, offline verification), `INT-R8`
  (compression-loss + cross-projection disclosure budget for the public views), `INT-R1`
  (the δ-conditional the public claim must carry), and the `INT-R9` first-promotion
  protocol **pre-registered before any promotion candidate is inspected**. Per Rule 5
  the runtime never forces this milestone; the public surface waits honestly. Before it,
  the public-facing story is DS11 posture + the Cycle Board's public-safe projection
  (honest status, not recommendations).
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
- **Distillation augment (Rev 18, post-DS4; §6.5 · M10·M34·M35 + P29 rider):** any public δ /
  promotion claim carries the explicit obligation-completeness conditional — **"risk ≤ δ *relative
  to the declared obligation set*"**, never unconditional (the INT-R1 dependency; distillation §6.3).
  The audience views are **one substrate → four projections** (PUBLIC/REVIEWER/EXPERT/MACHINE); the
  MACHINE twin must preserve reconstructable source/authority/audit refs (a projection that drops
  them is red). Contestability is proven (real recourse to a competent, change-authorized reviewer),
  not an "Appeal here" link. Any third-party model/data behind the claim carries a **graded
  supplier-evidence envelope** (vendor-run eval ≠ independent; "no incident found" ≠ "no incidents").
- **Ratified claim-semantics constraints (Revision 3.11; `INT-K01`–`INT-K08`,
  `docs/system-design-decisions/int-wave-claim-semantics-ratification.md`).** The INT-wave kernel is
  ratified, and DS12 is its largest product consumer. Four constraints bind this slice, and one
  architectural default is settled in its favour.
  - **The `INT-R9` gate input is discharged, and it resolved to a *nonnumeric* protocol.** The
    first-promotion protocol was amended to **Option B** — result-informed repair is kept, so every
    sequence-level number is withdrawn — and its independent conformance verification returned
    `CONFORMS_WITH_GAPS` with both gaps closed. The pre-registration requirement in the gate above
    is unchanged; what changed is what pre-registration buys. DS12 consumes a **custody** claim.
  - **What DS12 may publish about firstness (`INT-K06`).** A bounded custody and anti-selection
    statement: prospectivity, firstness, substitutions, chronology, adjudication, deviations,
    negative terminals, publication, correction — and the statement that no prohibited substitution
    was found in the governed record. It may **not** be projected as statistical family control,
    population performance, compliance, competence, or production readiness. This is a real public
    claim, checkable and falsifiable; it simply carries no probability.
  - **Every rendered `delta` carries its declared set (`INT-K02`).** A public δ must identify the
    declared obligation set and maintained assumptions and visibly carry the relative-basis rider.
    This ratifies and sharpens the Rev-18 P29 rider above: the conditional is not stylistic hedging,
    it is part of the claim's meaning, and a bare δ is not a smaller claim but a different and false
    one.
  - **No new lattice, no shortcut (`INT-K01`, `INT-K03`).** Coverage outcomes feed the **existing**
    status lattice; DS12 introduces no coverage-specific lattice. `bounded_complete` is **not
    issuable** and is not a fallback for an unresolved coverage disposition — issuing it requires
    constructed independence, which is dormant research (`INT-GAP-02`), not pending engineering.
  - **Architect default, settled: DS12 does not need a number, and should not ask for one.** A
    numeric first-promotion family claim would activate `GY-GAP2` (engineering: family declaration,
    chronology verifier, aggregate current-head projection) **and** `INT-GAP-01` (research: a
    selection-valid theorem for outcome-dependent repair) simultaneously, because the protocol keeps
    adaptive repair (`INT-K07`). The cost is disproportionate to what the number would add over the
    custody claim. Reopening this default is an architect decision, not a slice decision.
  - **`INT-K08` binds the empty case.** If the first-promotion protocol terminates with refusal,
    void, dispute, or exhaustion without promotion, that is a **completed** governed result. No
    launch deadline, success quota, substitution, or public compression may turn it into permission
    to weaken this slice's gate or hide the chronology. Per Rule 5 the public surface waits honestly
    — and under `INT-K08` it may also *say* that it waited, which is itself publishable.
- **Ratified public-verification and disclosure constraints (Revision 3.12; `PV-K01`–`PV-K09`,
  `docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md`).**
  The INT-R7/INT-R8 wave closed and its nine invariants are ratified. DS12 is their primary
  consumer, and the practical headline is about this slice's **gate**:
  - **All four named research inputs are now closeable as research inputs.** `INT-R1` and `INT-R9`
    were ratified 2026-08-04; `INT-R7` is `GO_WITH_REVISIONS` with its independent closure gate met
    (controlling head `3883b454`); `INT-R8` is `accepted_narrow_scope`, independently verified
    `CONFORMS` (controlling head `286ade10`). The seam between R7 and R8 was adjudicated item by
    item in both directions and holds. **The DS12 gate itself is unchanged and remains closed** —
    research-input closure is not implementation readiness, custody, institutional competence, or
    publication authority, and the gate still requires the first governed promotion and DS11.
  - **Consume the verification vector, never a signature Boolean (`PV-K01`).** A valid signature
    supports issuer-issuance authenticity and nothing more. Issuer issuance, projection
    faithfulness, public-history establishment, durable verifiability, current authority,
    status-snapshot selection and evidence obtainability are **separately falsifiable** and must be
    separately reportable. This is what makes the citizen surface useful rather than merely strict:
    it can say *which* dimension failed.
  - **Never let a present failure edit the past (`PV-K02`).** Withdrawal, revocation, supersession
    or stale currentness make current authority false without erasing a historically authentic
    record; historical authenticity never establishes current authority. `withdrawn-but-verifiable`
    is a first-class outcome this surface must render.
  - **The forged-packet negative control now has a ratified basis (`PV-K01`, `PV-K03`).** The
    inherited public-salt 32-bit FNV token is recomputed over attacker-selectable content; it is a
    `live_defect`, not a weak checksum. Strangle it so no recomputed packet can render a governed
    positive, and never let projection, transport or possession mint authority.
  - **Reuse the real producer (`bridge_missing`, not `producer_missing`).**
    `runtime/quality/public_export.py` is a real 2,103-line producer with no proof, evaluator or
    production route. Connect it; do not erase or duplicate it.
  - **Projection semantics (`PV-K04`, `PV-K05`).** Semantic parity is use-relative conservative
    protected-query parity, not byte equality: reduce detail, never amplify truth, certainty,
    authority, currency or permission. Three omissions block categorically — a bare `delta` without
    its declared basis, a hidden negative terminal, and a no-number custody claim missing a
    constitutive step. A link to the full record does **not** repair a misleading visible summary.
  - **No number, and the default is settled (`PV-K08`).** No canonical numerical disclosure claim
    may be projected. The refusal is premise-relative, not an impossibility theorem — determinism
    is explicitly *not* the obstruction — but the premises do not exist here and DS12 does not need
    a number.
  - **Any proof candidate must discharge the metadata channel (`PV-K09`).** Key identifiers,
    certificate paths, transparency-log positions, witness sets and proof-object sizes can
    reconstruct protected content through the proof machinery itself. A candidate that cannot show
    a proved-safe treatment under the declared model is blocked — and only that candidate.
  - **One dependency is newly visible:** `PV-K07` prefix discipline is ratified but **not issuable**
    until `GY-GAP3` (controlled release-family transcript) closes. DS12 must not present a release
    history as governed while that owner is absent.
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
- **Distillation augment (Rev 18, post-DS4; §6.5 · M38·M13·M14):** render the **GY-PA3**
  compression-loss ledger — each orchestration choice (selection / tool / framing / compression)
  shows its **authority delta** (candidate universe + rejected set + decision-policy;
  `authoritative_for = ∅`). A `CompressionLossReceipt` surfaces retained vs dropped limitations /
  denied-uses / counterevidence; a summary that dropped a retained-limitation renders **blocked, not
  clean**. Add a **cross-projection disclosure budget**: repeated PUBLIC/REVIEWER/MACHINE reveals
  cannot let a hidden fact be reconstructed via diff / hash / ordering / timing.
- **Not yet:** no agent output on PUBLIC surfaces; agent surfaces stay
  REVIEWER/EXPERT until a separate, explicit decision.

### New Slices (Revision 2 — the GY-N13/N11/N12 surface duals)

#### DS15 — Acquisition Routes & Data-Pool Growth Surfaces

- **Goal:** the surface dual of GY-N13 — the product's distinctive loop:
  **refusal-with-a-path becomes refusal-with-a-button.** The user sees why a
  case is blocked, what closing it costs, and (post-N13b) approves the
  acquisition and watches the world grow and the case re-enter.
- **Gate:** DS7. Read surfaces after **GY-N13a is accepted/merged**; the live
  loop after **GY-N13b**. **Revision 3 reality note:** N13a's census exists
  (12-family connector scorecard, 18 journaled live probes, the
  `ranking_only_not_voi` growth backlog with 15 `binding_gap` residuals) and
  measured that the current capstone routes are structural gaps, not data
  gaps — DS15's read surfaces render that truth as-is; the "approve
  acquisition" loop demonstrates on whatever honestly data-shaped gap N13b
  selects, never on a resurrected stale hypothesis.
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
- **Research-input augment (Rev 3.4, post-DS4; INT-R2):** the route detail view renders
  **non-data gap types as typed, visually distinct routes** — grounding-relation gap,
  estimand-binding gap, owner-writability gap, legal-mandate gap, capacity-evidence gap,
  human-decision gap — never forced into dataset-acquisition clothing (the N13a finding:
  the capstone routes were structural, not data gaps). Each type shows its own
  sufficiency bar and authority ceiling from the `GapAcquisitionCase` union when INT-R2
  lands; until then the surface renders the honest typed refusal, not a generic
  "fetch more data" affordance. **Falsifier (rendered):** adding rows must visibly NOT
  advance a relation/estimand/mandate route.
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
- **Distillation augment (Rev 18, post-DS4; §6.5 · M16·M23·M24·M26·M33):** the canonical object is
  the full set / partial-order — a scalar is a lossy view, never the authority. `incomparable`
  renders as **"no admissible ranking exists"**, distinct from `unknown` (missing) and from zero. A
  tail / worst-case-over-process value may **not** be shown as a cancelling average. A single ranked
  recommendation renders **only** when a **GY-PA1** `NormativeAuthorizationRecord` authorizes the
  aggregation; absent it, the surface shows the frontier + a `NormativeDecisionRequest`, never a
  silent scalarization.
- **Inherited debt from DS4-C23 (registered 2026-07-20, owner: DS16):** the DS4
  return-union census found two surfaces **minting** evidence-grade authority the
  runtime never produced — `PublicSectorReadinessPanel` composed readiness from
  local thresholds/regexes/dwell-state/disputes, and `ScientificDepthPanel`
  invented remedies, acquisition refs, **E-values, claim extinction, cohort
  timelines, and stress rankings** (`P15`/`P05`; "dashboards may project
  authority, they may not mint it"). **DS4-C23 performs containment only** —
  it strips the synthesis and renders `unavailable`/opaque. **DS16 owns the
  binding**: define/consume the typed producer contract for readiness
  composition and scientific-depth values, so these surfaces render a producer
  value or an honest `unknown`, never a locally computed one. *Closure signal:*
  each named value resolves to a generated field or a registered typed
  refusal; the DS4 containment negatives stay green afterwards. This is
  value/uncertainty semantics, which is why it is not DS4 work.
- **Not yet:** no transform-planner UI (the GY plan defers transform chains);
  single-transform provenance only.
- **Status (2026-08-18) — the authority half is CLOSED; the grammar body is not.** Branch
  `codex/atlas-ds16-value-grammar`, slice plan
  `docs/plans/active/atlas-slices/DS16-value-uncertainty-and-derived-data-grammar.md`.
  **The DS4-C23 producer binding is delivered**, and its outcome is not the one this section
  anticipated: all **eleven** inventory families — the record's "readiness composition" collapses six
  distinct builders into one phrase — have **no runtime producer at all**, measured with positive
  controls. So the binding is a typed contract of **eleven registered refusals**, each carrying its
  reason code and owning surface, served over `GET /api/v1/runs/{run_id}/authority-values`, with
  completeness enforced by a validator that raises on a dropped member. Both panels are bound, the
  `C23` containment witness is retired with a strangle proof, and the MACHINE twin ships with parity
  read from the rendered DOM.
- **The grammar body could not land here, and the reason is structural rather than a shortfall.**
  DS16's own surfaces render refusals and carry **zero** quantity references, so there is nothing
  unit-bearing to attach a basis chip to and nothing derived to open a recipe for. `C08` and `C09`
  have **real, exercised substrate** — `BasisSignature`/`BasisAttribute`/`BasisParameterBinding` and
  `DerivationRecipe`/`DerivationCertificate`, the latter with 32 call sites on
  `build_derivation_recipe` — and **zero served**; they could be bridged tomorrow and still have no
  consumer here. `ValueOuterSet` is different again: its only construction in the whole source tree is
  an empty placeholder and `.compare()` has zero callers, so bridging it would serve a placeholder.
  **Re-entry condition, stated as a property:** a surface exists that renders values rather than
  refusals — arriving with **DS7** on real capstone data.
- **Sequencing correction, and it is a finding about this plan.** The slice table and this section
  gate DS16 on `DS4`; the Start-Now ladder groups its value grammar under "DS5 closed". **Both are
  partly right:** `DS4` is the correct gate for *defining* the grammar, and it is insufficient for
  *landing* it. Read the two together, not as a contradiction to resolve in favour of one.
- **Vocabulary correction, measured and load-bearing.** This section's provenance triple
  `observed`/`derived`/`deployment_update` **conflates two enums**: `deployment_update` is a
  `BranchMode` member (world-branch semantics), not a provenance class. The provenance enum is
  `ObservationProvenanceClass` with **four** members — `observed`, `proxy`, `derived`, `model_output` —
  and the fourth is the "class-(iv) model output" this section's own negative polices. Worse for a
  consumer: the `provenance_class` that **is** served carries `ParticipationProvenanceClass`
  (ADR-0167, grades A–D, owned by `participation_requirement/`) — the **same field name, a different
  vocabulary, a different owner**. `ObservationProvenanceClass` is served nowhere under any name.
- **`OuterSetValue`** is built, proven against the slice's negatives, a11y-clean and has **zero
  production importers** — a finished component awaiting a surface, recorded as such and deliberately
  not mounted over a refusal string.

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
- **Distillation augment (Rev 3.4, post-DS4; §6.3 COND(P29) · INT-R1):** every rendered
  δ figure carries its **obligation-set conditional visibly** — "≤ δ *relative to the
  declared obligation set*" — as a first-class chip resolving to the
  `ObligationCoverageEnvelope` (declared scope, searched sources, exclusions, unknown
  remainder, TTL) once INT-R1 lands; until then the chip renders the honest
  `open_world_unresolved` state. A δ number displayed without its conditional is the
  surface-level P29 and fails the semantic test — the ledger's math is only as complete
  as the obligations the system knows.
  **INT-R1 has now landed (2026-08-03) and it changes what this bullet was waiting for.** Its
  result is `accepted_narrow_scope` with a formal *impossibility* finding: while an unobserved
  decisive obligation remains admissible, no finite trace can certify global obligation
  completeness — so the envelope's `bounded_complete` is always **relative to a declared closure
  basis and obligation language**, never to the world. Its independent audit adds the operative
  constraint: independence is specified but **not constructed**, therefore the pinned repository
  **cannot issue `bounded_complete` at all** today (`INT-R1-D-003`). Two consequences for DS17,
  neither of which is a wait: (1) `open_world_unresolved` stops being a placeholder pending
  research and becomes the **honest steady state** until an independent producer, scorer, and
  governance record exist — DS17 must render it as a settled position with its reason, not as a
  loading state; and (2) when a coverage value does become issuable, the chip renders it **with
  its basis** — declared scope, obligation-language version, cutoff, unknown remainder, TTL — and
  a `bounded_complete` shown without that basis is the same P29 failure as a bare δ. The typed
  refusal is the deliverable here; the value is not owed.
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
- **Distillation augment (Rev 18, post-DS4; §6.5 · M25·M36):** render the GY-N12 **post-publication
  perturbation cascade** — incident / appeal / correction / retraction / legal-change / bias are
  *distinct* event classes (not one "reopen"), each downgrade-only until adjudicated; a single upheld
  appeal shows **instance-scope, not class-scope**. A published record is **superseded with visible
  lineage, never silently edited** (recency ≠ strength); an `EvidenceValidityEvent` on an underlying
  source propagates source → evidence-line → claim → publication, and a claim that lost its support
  cannot stay current.
- **Not yet:** epoch chrome does not invent time semantics — it renders GY-N12
  and §3.5.12-D6 outputs only; scopes without regime data render honest
  `epoch_scope_unresolved`.

### New Slices (Revision 3 — grounded in Phase-A measurements)

#### DS19 — False-Substrate Strangle Wave + Frontend Disposition Register

- **Goal:** shrink every later slice's denominator by deleting what is
  provably false, and give the whole migration ONE disposition authority — the
  frontend dual of the GY-N0 disposition ledger: every estate unit is
  eventually **used-as-is / rebound / deleted**, never a live parallel owner.
- **Gate:** DS1 evidence (merged) — **may start now, parallel to DS3.**
- **Deliverables:** the **disposition register** (typed, in
  `architecture/atlas_surfaces/`, seeded from the DS1 readiness ledger and the
  DS2 adoption ledger) with per-unit disposition, evidence link, and strangle
  status; the **first deletion wave** over DS1's zero-consumer/false units —
  phantom collaboration REST/WS (+ its orphaned feature), orphan onboarding,
  latent legacy WhatIf, the duplicate Clerk index route, the empty
  feature-layout owner, the three zero-consumer worker modules, and the
  browser-side "signing" **call sites that nothing depends on** (the route
  itself stays frozen for DS12's strangle — deletion here covers only
  proven-dead paths); a **wire-or-retire disposition** (not implementation)
  for the 37 uncalled OpenAPI operations and the four `consumer_missing`
  flags, consumed by DS3/DS5.
- **Laws:** Rule 10; P06/P27/P28 duals; anti-P13 (deletion is scope reduction,
  not ceremony).
- **Negative controls:** every deletion carries its zero-consumer proof
  (DS1 evidence link + a fresh reference census at deletion time); a deletion
  without the fresh census is rejected; the register's CI check fails when a
  unit marked `deleted` still has references or a unit marked `rebound` lacks
  a successor consumer.
- **Not yet:** no rebinding (DS4), no producer building (DS3); DS19 deletes
  and registers only. Anything with ANY live consumer is out of scope for the
  wave and merely registered.

#### DS20 — Server Authorization Enforcement (split from DS5)

> **CLOSED & MERGED** (03ebc1ce8, 2026-07-20). DS20 (29/29-op action-permission
> floor, step-up for 6 high-stakes ops, fixture-identity removal, 33-value
> vocabulary through OpenAPI→client) + DS20-B cross-fence closure (B1 Rego bridge,
> B2 probe identity, B4 verifier provenance) landed; deployment-authority
> attestation architect-reviewed. Typed limitations carried as registered debt
> (see the inherited-debt table): B3 promotion CAS → fabric lane; B5 PostgreSQL
> proofs → cloud verification; scorecard producer provenance → DS9; Helm policy
> mirror → deploy lane.

- **Goal:** close the systemic authorization gap DS1 measured — this is
  today's production security posture, not UI debt, and it gates every
  authority-bearing surface that follows.
- **Gate:** DS3 (schema/client regeneration path); runs **parallel to DS4**.
- **Producer & bridge work (the slice IS server work, co-owned with
  team-architecture):** **generic action-permission dependency on all 29
  mutating operations** (a new mutating route cannot ship without one —
  enforced structurally, not by convention); **step-up authentication** for
  the high-stakes classes (promotion, production approval, publication,
  revocation, acquisition approval); **fixture identity prohibition in
  production mode** (the fail-open UI identity fallback dies with it);
  **resource binding before OPA evaluation**; the **single permission
  vocabulary** projected through the schema (collapsing the
  `_ROLE_PERMISSIONS` / `PERMISSION_KEYS` duplication); client regeneration.
- **Deliverables:** per-operation **server-side deny tests** (29/29, plus the
  audience classes); the DS1 seeded negatives N009–N013 implemented red-first;
  review-effectiveness telemetry hooks on the existing append-only access
  audit (consumed later by DS9).
- **Laws:** 9, 11 (enforcement half); the audience-is-access-control doctrine.
- **Negative controls:** a mutating endpoint without an action-permission
  dependency fails a structural test; a fixture identity in production mode is
  refused; an approval without step-up is denied server-side; UI-hides-but-
  server-allows is proven closed for every DS1-named gap.
- **Not yet:** no approval-flow UX (DS9 owns mandate/dissent/receipts); no
  audience mapping lints (DS5); DS20 is the server floor everything else
  stands on.

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
| T13 | DS19's deletion wave removes substrate a later slice silently depended on | every deletion carries a fresh zero-consumer census at deletion time (not only DS1's snapshot); the disposition register is the single authority and its CI check guards `deleted`-with-references |
| T14 | Post-Phase-A false confidence: task plans quietly assuming June-estimate capabilities | the Phase-A artifacts are the denominators of record; a task plan citing a capability without a DS1/DS2 ledger reference is rejected at review |

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
12. (Revision 3) The disposition register is complete and green: every estate
    unit carries a disposition, the DS19 deletion wave landed with
    zero-consumer proofs, no live parallel owner remains, and every DS1
    seeded negative (N001–N023) is implemented red-first in its owning slice.

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
