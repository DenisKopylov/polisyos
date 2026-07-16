---
title: Atlas Phase-A Synthesis
status: review-ready
owner: team-design
created: 2026-07-16
last_reviewed: 2026-07-16
master_plan: ../../plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
ds0_record: ../../brand/ATLAS_SOURCE_OF_TRUTH.md
ds1_report: ./atlas-live-application-audit.md
ds1_ledger: ../../../architecture/atlas_surfaces/live-application-readiness-ledger.json
ds2_report: ./atlas-v15-adjudication.md
ds2_ledger: ../../../architecture/atlas_surfaces/atlas-v15-adoption-ledger.json
ds2_physical_map: ../../../architecture/atlas_surfaces/atlas-v15-archive-map.json
audiences: [REVIEWER, EXPERT, MACHINE]
---

# Atlas Phase-A Synthesis

## Purpose And Authority

This is the closing package for Atlas Phase A (DS0 + DS1 + DS2). It gives the
architect one compact input for master-plan Revision 3: governing decisions,
measured application reality, and the fully adjudicated v15 archive. It does
not modify the Revision-2 DAG, activate Phase B, admit archive code into
production, or override the GY activation gates.

The underlying artifacts remain canonical for detail:

- [DS0 source-of-truth record](../../brand/ATLAS_SOURCE_OF_TRUTH.md) owns D1-D6
  and the sole pending owner ratification.
- [DS1 live-application audit](./atlas-live-application-audit.md) and its
  [machine ledger](../../../architecture/atlas_surfaces/live-application-readiness-ledger.json)
  own the measured frontend/runtime state and `PI-01` through `PI-24`.
- [DS2 v15 adjudication](./atlas-v15-adjudication.md), strict
  [adoption ledger](../../../architecture/atlas_surfaces/atlas-v15-adoption-ledger.json),
  and [physical map](../../../architecture/atlas_surfaces/atlas-v15-archive-map.json)
  own archive item decisions and coverage.

## Phase-A Outcome

Phase A confirms the constitutional direction and materially changes the
execution estimate. The product is not awaiting a component library: it has a
large living frontend, two API-client homes, substantial route/test/story
estate, 89 shared/UI implementations in 12 families, and many useful
projection components. Its central deficit is binding: runtime authority,
status, provenance, permission, time, audience, and evidence semantics do not
yet flow through one governed waist.

V15 is likewise not empty design work. It contains 1,476 files and 233
normalized adjudication units, including 71 component identities, a valid DTCG
authoring graph, responsive/data-viz/form patterns, and static evidence
methods. But it is not a production package or maturity authority. DS2 assigns
120 `admit_after_refactor`, 62 `wrap_then_strangle`, 38 `defer`, 13 `reject`,
zero `admit_as_is`, and zero stable verdicts. The living v4 remains the
transitional winner until item-specific DS4/DS6 gates close.

The plan's Phase-B thesis therefore sharpens from “build a system and migrate
the app” to **project governed runtime truth through one client/package waist,
rebind the useful living families, selectively consume admitted v15 material,
and strangle every duplicate owner**.

## Governing Decisions Carried Into Revision 3

| DS0 decision | Phase-A result | Revision-3 consequence |
| --- | --- | --- |
| D1 source hierarchy | Confirmed. Constitution and active master own law/execution; living code is the production baseline; v15 is retained material after DS2. | Link DS2 item ledger instead of describing v15 as pending adjudication. Never reactivate v4/v7/v15 as parallel design authorities. |
| D2 DTCG token source | **Confirmed with named gaps.** DS2 result is `parity_achievable_with_named_gaps`; the revisit condition does not fire. | DS4 keeps one-way DTCG generation, but must explicitly close warm-dark, z-index, post-reference aliases, density/runtime controls, breakpoint projection, mode-provider, forced-color, motion, and print gaps before migration. |
| D3 package/Figma | Confirmed and strengthened. Wholesale v15 import and compiled mirrors are rejected; all 56 synthetic Figma mappings remain unaudited. | Build only under private `@polisyos/atlas-ui@0.1.x`; code is source, Figma is a versioned projection, and DS4/DS6 own parity. |
| D4 locale posture | Still `pending_owner_ratification`; DS1 confirmed structural `en`/`uk`/`ru` parity but 80.16% of `ru` equals English. | DS5 may prepare locale enforcement, but DS12 cannot publish locale-support claims until the product owner ratifies retention/removal and ownership. |
| D5 feature flags | DS1 confirms exactly four canonical flags are consumer-missing and auth permission is a thirteenth pseudo-source. | DS5 implements one strict exposure registry, wire-or-retire for four flags, unknown-key rejection, and a hard separation between rollout and authorization. |
| D6 non-web surfaces | DS1 existence-checks print/export and CLI material; DS2 defers archive landing/assets/fonts/UI kits without inventing work. | Preserve the named owning slices; email remains `surface_out_of_scope` until a typed notification/privacy/delivery slice exists. |

## Reality Rebaseline For Revision 3

| Planning input | Phase-A measured value | Consequence |
| --- | --- | --- |
| Frontend scale | Dashboard source 908 TS/TSX and 136,827 LOC; full frontend zone 944 and 145,033 | Estimate DS4/DS5 by dependency families and violations, not by greenfield screen count. |
| Tests and evidence | 251 test/spec files, 44 stories, 67 a11y files, 17 e2e specs, 16 visual baselines; structural a11y gate red; no manual-AT record | DS6 grows an evidence workflow around a real estate, but no family may inherit stable. |
| Shared UI | 89 implementations in 12 families; 23 files violate the no-API/no-app boundary | DS4 is a 12-family rebinding and dependency-severing program, not a ~40-component extraction. |
| Status vocabulary | 23 named + 24 inline UI-local definitions; `DisputeStatus` ×3 / two vocabularies | DS4's retirement inventory must derive all local definitions and distinguish operational from authority state. |
| API waist | 89 OpenAPI operations: 45 surface-consumed, seven hook-only, 37 without dashboard calls; dashboard and reference shell use different clients | DS3 chooses one generated client/package home and demand-maps producers to admitted DS7-DS18 consumers. |
| Raw/off-contract transport | Nine raw fetches in five production files; two hidden SSE endpoints; one review WS; phantom collaboration REST/WS | DS3 governs channels; DS5 uses typed exemptions and covers raw fetch/EventSource/WebSocket construction. |
| Authorization | 29/29 POST operations lack action-permission and step-up dependencies | DS5 is a structural server-enforcement re-cut, not a UI permission cleanup. |
| Offline/cache | Promotion approve/reject is the only queued mutation and replays without live authority checks; six local authority-like stores lack tenant/user/epoch binding | DS5 bars authority queueing or requires explicit revalidation; DS18 extends this into an epoch invariant. |
| Routes | 32 route objects, 29 effective patterns, 22 leaf UI patterns, five redirects, catch-all, duplicate root | DS6 derives route evidence; later slices strangle existing routes instead of assuming 14 clean screens. |
| V15 components | 56 manifest rows but 70 real exports + one phantom; 11 surplus duplicate implementations; 62/71 have state docs | DS4 consumes only item-ledger admissions, rejects the phantom and duplicate owners, and never imports archive maturity. |
| V15 tokens | Six root sets, 711 paths, 258 aliases, zero broken aliases; live 74-variable parity = 21 exact / 40 deltas / 8 missing / 1 conflict / 4 controls | D2 stands; DS4 must implement the named semantic adapter and preserve accepted v4 behavior until evidence passes. |
| V15 evidence | 45 physical / 32 logical reports; mostly archive-local, presence-, marker-, count-, or self-score-based | DS6 may reuse selected methods after refactor, but archive PASS cannot supply runtime/browser/manual-AT evidence. |

## DS3-DS18 Revision-3 Scope Matrix

### DS3 - Runtime Producers And Export Infrastructure

**Confirmed:** Revision 2 correctly makes DS3 producer/bridge work and the
shared export foundation. DS1 found real lineage/artifact/decision-validity
exports to extend and confirmed that GY artifacts still lack surface
producers.

**Re-scoped:** apply `PI-01` through `PI-03`: select one generated-client home
for dashboard and reference shell; demand-map the 45 consumed, seven hook-only,
and 37 uncalled OpenAPI operations; govern hidden SSE and review WS in the same
typed channel registry; default orphan collaboration to removal unless a real
consumer contract justifies producers. Every DS3 projection binds its narrow
upstream hash and as-of metadata.

**Invalidated:** “dashboard is the only client consumer,” REST/OpenAPI parity
alone is a complete waist, or all 89 operations deserve migration. DS2 adds no
v15 code to DS3; archive package/build material is only refactor input.

### DS4 - Status-Grammar Rebinding And Test Harness

**Confirmed:** the slice is rebinding, not component invention. Useful living
quantity, temporal, trust, counterfactual, primitive, Storybook, and a11y
substrates exist.

**Re-scoped:** apply `PI-04` through `PI-06`: plan by all 12 families/89
implementations; sever 23 API/app ownership violations; retire 23 named and 24
inline local status definitions from a derived inventory; land red-first
authority tests before rebinding causal, what-if, composer, projection, and
browser-signing semantics. Consume only DS2 ledger rows and build the D2 token
adapter under `@polisyos/atlas-ui`.

**Invalidated:** the ~40-component estimate; any v15 `stable`/manifest/Figma
label; wholesale component or generated-mirror import; archive
`DecisionTimeline`; cold-dark/blue token replacement; a second package owner.

### DS5 - Enforcement Waist

**Confirmed:** mechanical enforcement remains the load-bearing waist.

**Re-scoped:** apply `PI-07` through `PI-10`: typed exemptions for exactly nine
raw fetches and raw transports; one server-projected permission vocabulary;
resource binding before OPA; generic action-permission and step-up coverage for
all 29 POST operations; production fixture prohibition; strict unknown
identity; bar authority actions from the offline queue; tenant/user/expiry
partition every authority-like cache; implement D5's one flag registry and
wire-or-retire four consumer-missing gates.

**Invalidated:** UI hiding as authorization, optional coarse OPA as action
permission, optimistic replay of promotion authority, a blanket no-fetch rule,
or using auth permissions as rollout flags.

### DS6 - Evidence Workflow And Instrumentation

**Confirmed:** an evidence workflow must gate every stable claim and validate
the readiness ledger.

**Re-scoped:** apply `PI-11`/`PI-12`: ingest the existing 251-test/44-story/
67-a11y/17-e2e/16-image estate by evidence class; repair the red structural
a11y gate with DS4 ownership; derive 22 leaf routes and intentional aliases;
store browser, keyboard, visual, and manual-AT evidence with cadence/owner.
Selected DS2 contrast/schema/static methods are inputs after refactor, never
pre-existing product evidence.

**Invalidated:** story/test/file presence as maturity; archive PASS, self-score,
component health, or a static state matrix as browser/manual-AT proof.

### DS7 - Cycle Board

**Confirmed:** a rich run/dashboard layout substrate exists, but no current
route is the truthful GY Cycle Board.

**Re-scoped:** apply `PI-13`: reuse layout, table, navigation, and responsive
material only after DS3/DS4 binding. Board rows come from real capstone,
disposition, acquisition, and readiness producers; evidence class and weakest
link are server projections. V15 dashboard/data-viz patterns are experimental
substrates, and the conflicting breakpoint vocabularies must first collapse.

**Invalidated:** treating the current run list or v15 dashboard prototype as an
incremental Cycle Board producer, or simulating N13b movement.

### DS8 - Case And Evidence Workspace

**Confirmed:** runs, evidence, artifacts, causal, what-if, quantity, and print
surfaces provide extensive strangler targets.

**Re-scoped:** apply `PI-14`: maintain a per-panel migration map; wire typed
artifacts, demote local causal drafts, remove latent legacy WhatIf, and rebind
shared families through DS4. Reuse print/export only after source, provenance,
time, and surface/MACHINE parity. Selected v15 flow/layout semantics may be
admitted after refactor.

**Invalidated:** greenfield workspace assumptions, client-side causal/readiness
truth, and migrating latent or orphan paths because they exist.

### DS9 - Human Decision Integrity

**Confirmed:** principal-bound approval/override/blocking and step-up remain
necessary; existing access audit is the log to extend.

**Re-scoped:** apply `PI-15`: cover promotion, production approval, reissue,
validity, and acquisition decision classes; require mandate, evidence exposure,
principal binding, step-up, dissent, and override receipts; strangle local
Operator Craft/reviewer-like state and offline promotion. V15 governance/forms
are projection guidance only.

**Invalidated:** self-asserted reviewer/signature fields, client permission
gates, localStorage reviewer state, or an archive approval flow as integrity.

### DS10 - Capability Discovery

**Confirmed:** search-driven discovery and Rule-12 free growth remain correct;
Lex and catalog search are useful seeds.

**Re-scoped:** apply `PI-16`: extend Lex producer/DTO/UI/export so candidate,
grounding, hallucination, temporal, and frontier truth survive; re-ground or
strangle the hand-maintained capability manifest; reuse command-palette chrome
only behind strict D5 exposure and typed discovery posture.

**Invalidated:** building a new discovery shell, treating hardcoded capability
menus as a registry, or equating discoverable with executable/admitted.

### DS11 - Trust And Docs Posture

**Confirmed:** claims need a typed register and evidence workflow before any
performance posture.

**Re-scoped:** apply `PI-17`: include `/welcome` in route/a11y evidence and
define a public no-tracker/redaction posture before outward claims. Selected
v15 content, accessibility, and governance material may inform language and
methods after refactor, but the claims register remains the owner.

**Invalidated:** the forgeable decision URL, archive readiness score, or
landing prototype as proof of trust/support.

### DS12 - Public Publication Foundation

**Confirmed:** the constitutional first-governed-promotion gate remains and may
honestly remain closed.

**Re-scoped:** apply `PI-18`: freeze and strangle the existing route onto a
server-keyed persisted public record with real signature verification,
revocation/expiry, privacy classification, public accessibility, and a
surface/MACHINE parity test; cover all three packet builders and local Operator
Craft refs; structurally prevent signed IDs/payloads from beacon/Sentry egress;
implement the owner-ratified D4 locale posture.

**Invalidated:** the salted browser FNV hash as signing, browser verification
as authority, keyword-only private-data scans, or v15 landing/print material as
a public record. No live server artifact depends on the decorative URL.

### DS13 - Accountability Ledgers And Transparency

**Confirmed:** this slice must start after DS12 persisted identifiers and
governed producers.

**Re-scoped:** apply `PI-19`: build dispute, consultation, supersession,
revocation, response-to-comment, and transparency-feed projections from server
records; reuse no local dispute/history data as authority. V15 public-flow
material remains deferred guidance.

**Invalidated:** per-run localStorage disputes or browser publication history
as accountability records.

### DS14 - Bounded-Agent Surface

**Confirmed:** the live Clerk shell, history, streaming, and status UX are
reuse candidates after the Phase-6 O-block and DS9.

**Re-scoped:** apply `PI-20`: remove the duplicate direct index route;
candidate-bind or delete dormant structured verdict/confidence/diff;
partition/expire local sessions; add bounded-agent artifacts and orchestration
audit bridge; keep every fluent output out of authority/public slots.

**Invalidated:** treating dormant structured renderers as capability progress,
or building a second chat instead of strangling Clerk.

### DS15 - Acquisition Routes And Data-Pool Growth

**Confirmed:** existing Data Intelligence profile/catalog/connector/discovery/
preview/resolve calls provide a read-surface substrate; N13a/N13b gates remain.

**Re-scoped:** apply `PI-21`: bind reads to GY acquisition artifacts; wire or
delete the hook-only ingest path; route approve-acquisition through DS9 mandate,
permission, step-up, passport, quarantine, epoch, and re-entry records. V15
evidence-upload/search forms and provenance visualizations require DS4/DS6
refactor before use.

**Invalidated:** current API calls as proof of acquisition readiness, one-click
or offline execution, or fetched data rendered as admitted world data without
a complete passport.

### DS16 - Value, Uncertainty And Derived Data

**Confirmed:** living quantity/counterfactual/temporal components and v15 chart
substrates reduce greenfield rendering work, but neither is runtime-bound
authority.

**Re-scoped:** apply `PI-22` and the DS2 DS16 negative: rebind families to
`ValueOuterSet`; render `unknown` and incomparable first-class; require basis,
deflator, derivation recipe, certificate, and observed/derived/
deployment-update provenance; prohibit worker/client point collapse. Reuse
generic v15 grammar only after this adapter.

**Invalidated:** v15 `ChartPoint.value`/midpoint `UncertaintyBand` as universal
truth, UI-local quantity status, or a model/derived series styled as observed.

### DS17 - Confidence Ledger And Risk Spend

**Confirmed:** DS17 remains producer-gated on GY-N11 and should show refusal/
acquisition instruments before positive certificates.

**Re-scoped:** apply `PI-23`: count no existing generic confidence gauge or
v15 chart as progress; bind every visualization to typed delta-budget,
obligation-class, instrument, and anytime-validity fields, with blocker states
and a MACHINE twin.

**Invalidated:** Clerk/local confidence, archive scorecards, or chart confidence
bands as risk-spend authority.

### DS18 - Epoch And Staleness Chrome

**Confirmed:** temporal components and DS4's future `TimeSemanticsLabel` are
reuse candidates; GY-N12 remains the authority producer.

**Re-scoped:** apply `PI-24`: make epoch/as-of/revalidation a cross-cache and
cross-surface invariant, not decorative chrome; fail cached authority closed
on epoch advance; show derivation inheritance and replay boundaries. Keep live
v4 temporal family until this exists.

**Invalidated:** v15's phantom `DecisionTimeline`, archive mode/time prose, or
client timestamps as runtime epoch semantics.

## Cross-Slice Revision-3 Actions

1. Replace every stale June denominator and estimate with the DS1 corrected
   snapshot; preserve the 19-slice DAG and activation gates unless the
   architect makes an explicit new decision.
2. Make the DS2 adoption-ledger ID a required input to every DS4 migration
   task. No v15 path may enter a task merely by package/folder membership.
3. Re-estimate DS4, DS5, DS6, DS12, and DS18 upward for binding/enforcement;
   reduce greenfield UI estimates in DS8, DS10, DS14, and DS15 where living
   substrates exist.
4. Define one strangler register across live v4, v15 candidates, orphan/dead
   features, and duplicate clients/transports. A successor closes only when a
   real consumer and the old owner path are both proven.
5. Carry DS1 red-first negatives into owning task plans before implementation,
   especially authority laundering, 29-route authz, offline promotion,
   public signing/privacy/telemetry, and point-collapse uncertainty.
6. Keep `stable` unavailable until DS6 evidence exists. The single DS2 beta is
   an evidence method and cannot raise a component or surface.
7. Keep outward gates intact: DS11 after DS9+DS6; DS12 only after DS11 and the
   first governed promotion with N11/N12 validity; DS13 after DS12; DS14 after
   DS9 and the O-block.
8. Prevent archive gravity from manufacturing scope: DS10 has no directly
   consumed v15 row, DS13 has only three deferred asset/font/landing adjuncts,
   and DS17 has generic contract-only flow material rather than delta-ledger
   semantics. Record these absences in Revision 3.
9. Make false substrates explicit delete/strangle work: phantom collaboration,
   orphan onboarding, the empty feature-layout owner, latent WhatIf, duplicate
   Clerk index, local disputes/history, browser signing, and v15 compiled/
   preview/embedded copies.

## Pending Owner Ratification

There is exactly one Phase-A owner item: DS0 D4, the Ukraine-facing `ru`
locale retention/removal decision. Phase A recommends Ukrainian primary,
English baseline, and frozen legacy Russian continuity only if the product
owner explicitly accepts the political/public consequence and names an owner.
Until ratified, the current structural catalog is evidence, not a public
support claim, and DS12 remains barred from publishing that claim.

## Phase-A Closure Signal

Phase A is ready for architect review when DS2 closeout verification is green:
the 233-entry ledger validates against the frozen DS0 schema and corruption
probes fail; report/ledger parity and 1,476-member coverage are exact; links
resolve; the archive hash remains frozen; only permitted documentation and
`architecture/atlas_surfaces/**` paths changed; and the branch is clean. The
architect may then merge Phase A as one unit and author Revision 3. This branch
does not merge itself and does not start Phase B.
