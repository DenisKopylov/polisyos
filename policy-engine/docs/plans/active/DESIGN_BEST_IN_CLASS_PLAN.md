# PolicyOS Atlas - Best-in-Class Design Roadmap

> Дата: 2026-04-29
> Статус: active
> Версия: 3.0, post-implementation frontier plan
> Владелец: Denis Kopylov
> Scope: `policy-engine/frontend/runtime-dashboard/`, `policy-engine/docs/brand/`,
> `policy-engine/docs/compliance/`, runtime/fabric/scientist API contracts

---

## 0. Зачем обновлен этот план

Предыдущий `DESIGN_BEST_IN_CLASS_PLAN.md` описывал две волны: закрытие SOTA
пробелов и внедрение первых best-in-class примитивов. Эта работа теперь
считается baseline. В репозитории уже есть Atlas shell, брендовые глифы,
темы, density modes, accessibility tooling, provenance/quantity слой,
counterfactual controls, bitemporal scope, trust view, bureaucratic rendering,
reading view, chart primitives, Storybook и визуальные проверки.

Новый файл больше не планирует уже реализованное. Он планирует следующий слой:

1. Принять новый архив `PolicyOS Atlas Design System-4.zip` как дизайн-спеку
   и прототипный источник, но не копировать его React/inline-style код в
   production.
2. Реализовать поверхности, которые есть в новом дизайн-пакете, но отсутствуют
   или существуют только частично в репозитории.
3. Спроектировать и реализовать настоящую best-in-class систему поверх Atlas:
   causal/scientific UX, Fabric operations, trust/accountability, run
   choreography, comprehension, publication-grade output и operator craft.

**Главная формула:** PolicyOS должен перестать быть "dashboard around policy
runs" и стать **операционной средой доказуемой политики**, где causal graph,
time, provenance, uncertainty, trust, objections, publication и reviewer craft
являются первичными объектами интерфейса.

---

## 1. Текущий baseline: что уже считается реализованным

Эти слои не планируются заново. Их можно расширять, но нельзя ломать без ADR и
миграции.

### 1.1. Design-system foundation

| Слой                                         | Production anchor                                               | Статус                                 |
| -------------------------------------------- | --------------------------------------------------------------- | -------------------------------------- |
| Atlas shell, sandstone/glass/graphite layout | `frontend/runtime-dashboard/src/styles.css`                     | done                                   |
| Light theme tokens                           | `src/styles/theme-light.css`                                    | done                                   |
| Dark theme tokens                            | `src/styles/theme-dark.css`                                     | done, но требует v4 canonical decision |
| High contrast / forced colors                | `src/styles/theme-high-contrast.css`                            | done                                   |
| Motion/reduced motion                        | `src/styles/motion.css`, `tools/design/check-reduced-motion.ts` | done                                   |
| Density modes                                | `src/styles/density-*.css`, `DensityProvider`                   | done                                   |
| Print/export styling                         | `src/styles/print.css`                                          | done                                   |
| Tailwind v4/shadcn token bridge              | `@theme inline` in `src/styles.css`                             | done                                   |

### 1.2. Brand and glyph foundation

| Слой                         | Production anchor                                   | Статус |
| ---------------------------- | --------------------------------------------------- | ------ |
| Atlas assets                 | `public/atlas/`                                     | done   |
| Janus mark                   | `src/shared/brand/JanusGlyph.tsx`                   | done   |
| Atlas wordmark/mark resolver | `src/shared/brand/AtlasBrand.tsx`                   | done   |
| Ten-radical glyph alphabet   | `src/shared/brand/Glyph.tsx`, `glyph-vocabulary.ts` | done   |
| Glyph accessibility          | `Glyph.a11y.test.tsx`                               | done   |
| Evidence sigil               | `src/shared/brand/EvidenceSigil.tsx`                | done   |
| Provenance strip             | `src/shared/ui/ProvenanceStrip.tsx`                 | done   |

### 1.3. Decision-bearing number spine

| Слой                                     | Production anchor                                                              | Статус |
| ---------------------------------------- | ------------------------------------------------------------------------------ | ------ |
| Quantity primitives                      | `src/shared/ui/quantity/`                                                      | done   |
| Provenance popover/deep dive             | `src/shared/ui/quantity/ProvenancePopover.tsx`, `ProvenanceDeepDiveDialog.tsx` | done   |
| Counterfactual quantity                  | `src/shared/ui/quantity/CounterfactualQuantity.tsx`                            | done   |
| Fabric decision data adapter             | `src/shared/ui/quantity/fabric-decision-data.ts`                               | done   |
| API hooks for run quantities/fabric data | `src/api/hooks/useRunQuantities.ts`, `useRunFabricDecisionData.ts`             | done   |
| Trust view                               | `src/shared/ui/trust-view/`                                                    | done   |

### 1.4. Existing high-value feature surfaces

| Surface                   | Production anchor                                       | Статус                                    |
| ------------------------- | ------------------------------------------------------- | ----------------------------------------- |
| Command Center            | `src/features/dashboard/routes/DashboardPage.tsx`       | done, needs Atlas v4 expansion            |
| Scenario Composer         | `src/features/composer/routes/LaunchRunPage.tsx`        | done                                      |
| Runs / Decision Workspace | `src/features/runs/routes/RunDetailLayout.tsx` and tabs | done                                      |
| Evidence Fabric           | `src/features/evidence/routes/EvidenceFabricPage.tsx`   | done, needs Fabric v4 surfaces            |
| Causal canvas primitives  | `src/features/causal/`                                  | partial                                   |
| Counterfactual controls   | `src/shared/ui/counterfactual/`                         | done                                      |
| Policy diff               | `src/features/runs/compare/`                            | done, needs causal/dependency integration |
| Bureaucratic artifacts    | `src/features/artifacts/bureaucratic/`                  | done, needs editable forms                |
| Reading/monograph view    | `src/features/artifacts/reading-view/`                  | done                                      |
| Collaboration indicators  | `src/features/collaboration/`, `src/app/realtime/`      | partial                                   |
| Onboarding tours          | `src/features/onboarding/`                              | partial                                   |

### 1.5. Quality gates already available

| Gate                  | Anchor                                                | Must remain green |
| --------------------- | ----------------------------------------------------- | ----------------- |
| Component/unit tests  | `npm run test:components`                             | yes               |
| A11y suite            | `npm run test:a11y`, `tools/design/check-contrast.ts` | yes               |
| Design polish suite   | `npm run design:polish`                               | yes               |
| Visual snapshots      | `npm run test:visual`                                 | yes               |
| Architecture checks   | `npm run check:architecture`                          | yes               |
| Glyph vocabulary gate | `npm run test:glyph-vocabulary`                       | yes               |
| Quantity coverage     | `npm run quantity:coverage`                           | yes               |

---

## 2. Что дает новый Atlas Design System v4

Архив `PolicyOS Atlas Design System-4.zip` содержит не production replacement,
а три полезных слоя.

### 2.1. Canonical reference layer

| Из архива             | Как использовать                                                                                      |
| --------------------- | ----------------------------------------------------------------------------------------------------- |
| `README.md`           | Перенести в `docs/brand/ATLAS_DESIGN_SYSTEM.md` как живую спецификацию, сверенную с production tokens |
| `SKILL.md`            | Использовать как agent-facing summary, но после удаления прототипных неточностей                      |
| `colors_and_type.css` | Использовать как token fixture для drift-check, не импортировать напрямую в app                       |
| `preview/*.html`      | Превратить в Storybook/design-reference stories                                                       |
| `assets/`             | Сравнить с `public/atlas/`; менять только если геометрия/семантика реально отличаются                 |
| `fonts/`              | Не использовать напрямую: app уже self-hosts via `@fontsource`                                        |

### 2.2. Prototype layer

`ui_kits/dashboard/` содержит high-fidelity prototype screens. Часть из них
совпадает с текущими workspaces, часть является новым backlog.

| Prototype screen             | Track in this plan    | Production route strategy                                                                |
| ---------------------------- | --------------------- | ---------------------------------------------------------------------------------------- |
| `CausalAtlas.jsx`            | A1                    | Extend `features/causal`, nested inside Decision Workspace and Evidence/Science surfaces |
| `IdentifiabilitySurface.jsx` | A2                    | New `features/causal/identifiability`                                                    |
| `SensitivityRotor.jsx`       | A3 / G1               | Shared global threshold + causal sensitivity surface                                     |
| `CohortTimeTraveler.jsx`     | A4                    | New `features/cohorts` or nested under Scenario/Decision                                 |
| `StressTestTheatre.jsx`      | A5                    | New run evaluation tab and decision packet block                                         |
| `FreshnessBraid.jsx`         | B1                    | Evidence Fabric data-plane panel                                                         |
| `ConnectorCards.jsx`         | B2                    | Evidence Fabric connectors panel                                                         |
| `SchemaMigration.jsx`        | B3                    | Evidence Fabric schema/storyboard panel                                                  |
| `QualityBudget.jsx`          | B4                    | Evidence Fabric quality/SLO panel                                                        |
| `ProfileDriftNarrative.jsx`  | B5                    | Evidence Fabric drift narrative card                                                     |
| `LineageGravityMap.jsx`      | B6 / D4               | Shared lineage/dependency map                                                            |
| `DisputeLedger.jsx`          | C1                    | Decision Workspace trust/governance tab                                                  |
| `StakeholderLens.jsx`        | C2                    | Decision packet lens layer                                                               |
| `FairnessAudit.jsx`          | C3 / G4               | Decision packet fairness block                                                           |
| `EmbargoManager.jsx`         | C5                    | Global data masking overlay + Evidence Fabric panel                                      |
| `RunChoreography.jsx`        | D1                    | Runs detail operations tab                                                               |
| `LiveRunMonitor.jsx`         | D5                    | Ambient telemetry HUD and run monitor                                                    |
| `ProvenanceCertificate.jsx`  | D2                    | Export artifact from completed runs                                                      |
| `ArgumentMap.jsx`            | E1                    | Decision packet reasoning tab/block                                                      |
| `ReasoningChain.jsx`         | E1 / E6               | Extend existing reasoning display                                                        |
| `CounterfactualExplorer.jsx` | A3 / 2.4 continuation | Expand counterfactual controls                                                           |

### 2.3. Known v4 conflicts to resolve before adoption

| Conflict             | Current repo                                            | Archive v4                          | Decision needed                                                                 |
| -------------------- | ------------------------------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------- |
| Dark palette         | Warm dark paper/sepia                                   | Blue graphite dark                  | ADR required: keep warm dark unless procurement/testing proves blue is superior |
| `--panel` light      | `rgba(255,255,255,0.85)`                                | `rgba(251,248,242,0.82)`            | Decide by contrast and visual regression                                        |
| `--chart-secondary`  | semantic `color-mix`                                    | hard/blue-ish fallback in prototype | Keep semantic mix; no new blue category                                         |
| Density modes        | implemented                                             | documented as planned               | Update docs to "implemented"                                                    |
| Sidebar prototype    | 30+ flat nav items, raw Unicode symbols                 | current six workspaces              | Do not adopt flat nav; use nested surfaces                                      |
| Prototype components | inline styles, duplicate ids, no routing/a11y contracts | production components exist         | Rebuild using existing shared UI                                                |

---

## 3. Non-negotiable product laws

These rules apply to every item in Tracks A-G.

### 3.1. Design laws

- No raw decision-bearing numbers. Any number that can affect a decision uses
  `Quantity`, provenance, temporal scope, uncertainty and trust metadata.
- No new domain colors. Teal/ember/gold plus neutral remain the signal system.
  New distinctions use pattern, shape, density, glyph intent, diacritic or
  layout.
- No new domain glyphs without ADR retiring an existing radical. The
  ten-radical alphabet remains closed.
- No flat sidebar expansion. New surfaces live as nested panels, tabs, command
  palette entries, contextual deep links or workspace subroutes.
- No prototype inline-style adoption. Prototype screens are inspiration only;
  production uses shared components, CSS tokens and feature-slice boundaries.
- No dashboard vanity metrics. Every card must answer an operator question:
  "what changed?", "what is blocked?", "what should I inspect?", or "what is
  safe to approve?"

### 3.2. Engineering laws

- Every new surface has an explicit contract: schema, validator, fixture,
  React Query hook, empty/error/loading state and tests.
- Every new visualization has a non-visual fallback and screen-reader summary.
- Every interaction that changes interpretation must be URL-stable or
  replay-recordable.
- Every new route/panel gets Storybook stories, a11y tests and at least one
  visual snapshot if it changes layout materially.
- Every new backend field is additive for at least two releases before old
  fields can be deprecated.
- Every global overlay has escape behavior, focus behavior and reduced-motion
  behavior.

### 3.3. Procurement and public-sector laws

- EU AI Act readiness is a first-class design constraint: harm, fairness,
  traceability, human review, revocation and auditability must be visible, not
  only logged.
- Ukrainian bureaucratic register is not an export-only concern. Input,
  review and render surfaces must share one AST.
- Public viewer surfaces must be immutable, signed, read-only and provenance
  preserving.

---

## 4. Implementation architecture for all new tracks

Each capability follows the same implementation ladder.

### 4.1. Capability ladder

1. **Contract first** - schema under `schemas/` or OpenAPI extension, runtime
   types in `src/api/types.ts`, zod validator in `src/api/validators.ts`.
2. **Fixture second** - deterministic fixture in
   `src/test/contracts/fixtures/`.
3. **Data hook** - `src/api/hooks/use*.ts`, suspense and non-suspense variants
   where appropriate.
4. **Domain adapter** - pure functions under feature `domain/`; no React.
5. **Visualization primitive** - reusable chart/map/control under
   `src/shared/charts/`, `src/shared/ui/`, or feature-local if domain-specific.
6. **Surface shell** - page/tab/panel with loading/error/empty/degraded states.
7. **Storybook + a11y** - stories, component a11y tests, screen-reader summary.
8. **Route/deep link** - route manifest, command palette entry, prefetch link.
9. **Telemetry** - time-to-insight and interaction events via
   `shared/telemetry/performance`.
10. **Docs and acceptance** - design reference story, plan checkbox, operator
    acceptance narrative.

### 4.2. Suggested frontend file layout

```text
frontend/runtime-dashboard/src/features/
├── causal/                         # Track A causal/scientific layer
│   ├── atlas/
│   ├── identifiability/
│   ├── sensitivity/
│   └── stress-test/
├── cohorts/                        # A4 cohort time-traveler
├── evidence/                       # Track B Fabric/data-plane surfaces
│   ├── freshness/
│   ├── connectors/
│   ├── schema-migration/
│   ├── quality-budget/
│   ├── drift/
│   └── lineage-gravity/
├── governance/                     # Track C trust/accountability surfaces
│   ├── disputes/
│   ├── stakeholder-lens/
│   ├── fairness/
│   ├── harms/
│   ├── embargo/
│   ├── slow-review/
│   └── revocation/
├── operations/                     # Track D run operations
│   ├── choreography/
│   ├── reproducibility/
│   ├── replay/
│   ├── dependency-graph/
│   └── telemetry-hud/
├── comprehension/                  # Track E explanation and learning layer
│   ├── argument-map/
│   ├── semantic-overlay/
│   ├── narrate-provenance/
│   ├── glossary-lens/
│   ├── confidence-navigation/
│   └── deterministic-explanation/
├── publication/                    # Track F public/editorial-grade surfaces
│   ├── model-cards/
│   ├── public-viewer/
│   ├── coverage-map/
│   ├── threshold-contracts/
│   └── bureaucratic-forms/
└── operator-craft/                 # Track G personal reviewer layer
    ├── trust-threshold/
    ├── annotations/
    ├── evidence-wallet/
    └── onboarding/
```

Actual implementation may reuse existing folders when a feature already has a
home. The rule is architectural clarity, not directory proliferation.

### 4.3. Workspace strategy

Keep the current top-level workspaces:

- Command Center
- Scenario Composer
- Runs / Decisions
- Evidence Fabric
- Knowledge
- Platform

New surfaces enter through:

- tabs inside Run Detail / Decision Workspace;
- nested panels inside Evidence Fabric;
- command palette actions;
- contextual deep links from Quantity/Provenance/Trust popovers;
- public read-only routes under a dedicated immutable viewer namespace.

---

## 5. Track A - Causal and Scientific layer

**Thesis:** PolicyOS wins by turning causal inference into an operator-grade
interface. The DAG, identification status, sensitivity, cohort movement and
stress tests must be primary UX objects, not backend footnotes.

### A1. Causal Atlas - editable DAG as primary object

**Source:** v4 `CausalAtlas.jsx` plus existing `features/causal/`.

**Current baseline:** There is a causal graph canvas, nodes, edges, layout
algorithms and overlays, but no first-class editable DAG, no bitemporal model
version cursor, and no adversarial identification mode.

**Build:**

- Extend `features/causal/components/CausalGraphCanvas.tsx` into an editable
  DAG mode: add node, edit node role, draw edge, delete edge, annotate edge.
- Add domain types for cause, mediator, confounder, collider, instrument,
  treatment, outcome and policy intervention.
- Add edge hover panel that explains identification path:
  back-door, front-door, IV, RDD, DiD, synthetic control, interrupted time
  series, or "not identified".
- Add adversarial mode that highlights open back-door paths and unblocked
  colliders in ember, with a "why this path is open" explanation.
- Add model version timeline: `model_valid_at`, `model_tx_at`,
  `graph_version_id`, `policy_version_id`.
- Add DAG diff between versions: added/removed nodes, edge sign changes,
  changed assumptions, changed estimand.
- Add export into decision packet: graph snapshot hash, selected adjustment set,
  identification method and unresolved assumptions.

**Backend/API contract:**

- `GET /api/v1/causal/graphs/{graph_id}`
- `PATCH /api/v1/causal/graphs/{graph_id}`
- `GET /api/v1/causal/graphs/{graph_id}/identification`
- `GET /api/v1/causal/graphs/{graph_id}/versions`
- Add `causal_graph_ref` and `identification_summary` to run detail payloads.

**Acceptance:**

- Operator can edit a DAG without losing layout or provenance.
- Hovering an edge gives a deterministic identification explanation.
- Adversarial mode exposes at least one unblockable/open path in fixture data.
- Switching bitemporal cursor changes graph version and emits a visible diff.
- Every displayed estimand links to Quantity/provenance where available.
- Graph is keyboard navigable: node list, edge list, selected path list.

**Tests:**

- `CausalAtlas.test.tsx` for edit operations.
- `CausalAtlas.a11y.test.tsx` for keyboard and screen-reader summary.
- Contract fixture for graph versions and adversarial paths.
- Visual snapshot for normal, adversarial and diff modes.

### A2. Identifiability Surface - landscape of what is provable

**Source:** v4 `IdentifiabilitySurface.jsx`.

**Current baseline:** Identifiability appears in glyph language and some causal
components, but not as a full operator surface.

**Build:**

- Heat-map matrix of model parameters or claims:
  point-identified, partially identified, set-identified, not identified.
- Hover/click cell reveals bounds: Manski, Robins, IV bounds, monotonicity
  assumptions, sample restrictions and required estimand.
- Add "what would identify this?" wizard:
  dataset needed, RCT needed, valid IV needed, additional covariate needed,
  longer panel needed, better measurement needed.
- Connect gaps to Evidence Fabric: source profile, connector, schema and
  freshness constraints.
- Add decision impact: "this gap affects N decision-bearing quantities and M
  policy recommendations."

**Backend/API contract:**

- `GET /api/v1/causal/identifiability/{run_id}`
- `GET /api/v1/causal/identifiability/{run_id}/remedies`
- Add `identifiability_state`, `bounds`, `assumptions`, `remedy_refs` to
  Quantity metadata.

**Acceptance:**

- Operator can sort by weakest identifiability, highest decision impact and
  easiest remedy.
- Bounds are rendered as intervals, not prose-only.
- Remedy wizard creates an evidence need or scenario requirement.
- No cell relies only on color; pattern/label/glyph encode state.

### A3. Sensitivity Rotor - E-value crank

**Source:** v4 `SensitivityRotor.jsx`; extends current counterfactual and
uncertainty components.

**Current baseline:** There are uncertainty bands and counterfactual controls,
but no global sensitivity threshold that extinguishes claims live.

**Build:**

- Add global rotor control with E-value/sensitivity threshold.
- As threshold increases, decision-bearing quantities below robustness
  threshold fade, collapse or switch to "not decision-bearing".
- Show live counters: remaining claims, extinguished claims, policy verdict
  changed/not changed, fairness gate changed/not changed.
- Provide deterministic explanation per extinguished claim:
  "E-value 1.3 below threshold 1.8; hidden from decision view."
- Integrate with Track G1 global trust threshold while keeping sensitivity and
  confidence distinct controls.

**Backend/API contract:**

- Add `sensitivity` object to Quantity:
  `e_value`, `robustness_class`, `threshold_effects`, `claim_refs`.
- `GET /api/v1/runs/{run_id}/sensitivity`.

**Acceptance:**

- Rotor movement updates charts and decision packet sections in under 100 ms
  for fixture-scale data.
- Reduced-motion mode uses instant state changes, not animation.
- Rotor state is URL-stable and replay-recordable.

### A4. Cohort Time-Traveler

**Source:** v4 `CohortTimeTraveler.jsx`.

**Current baseline:** Temporal cursor exists; cohort movement across valid time
does not.

**Build:**

- Filter-builder for cohorts: geography, protected class, eligibility,
  exposure, baseline status, evidence coverage, policy version.
- Valid-time scrubber showing cohort membership changes.
- Sankey/alluvial flow between cohort states across time.
- Overlay policy effect: "this cohort would pass/fail under policy v3.4."
- Save cohort definitions as stable refs used by decisions and public viewer.

**Backend/API contract:**

- `POST /api/v1/cohorts/query`
- `GET /api/v1/cohorts/{cohort_id}/timeline`
- `GET /api/v1/cohorts/{cohort_id}/policy-effect`
- Add `cohort_ref` to scenario and decision packets.

**Acceptance:**

- Cohort query is reproducible from URL and saved definition.
- Sankey has text fallback table of state transitions.
- Policy overlay distinguishes observed membership from counterfactual
  eligibility.

### A5. Stress-Test Theatre

**Source:** v4 `StressTestTheatre.jsx`.

**Current baseline:** Backend has eval/challenge concepts in scientist area,
but runtime UI lacks theatre metaphor and decision-packet references.

**Build:**

- Scene sequence: boring case, missing data, adversarial labels, OOD source,
  legal blocker, fairness blocker, stale evidence.
- Each scene shows input fixture, expected reaction, actual reaction and diff
  from baseline run.
- Scene can be attached to decision packet as evidence of robustness/failure.
- Add "failure dramaturgy" summary: what failed, why, whether policy changed.

**Backend/API contract:**

- `GET /api/v1/runs/{run_id}/stress-scenes`
- `POST /api/v1/runs/{run_id}/stress-scenes/{scene_id}/replay`
- Add `stress_scene_refs` to decision packet artifacts.

**Acceptance:**

- Decision packet can cite a scene by immutable ref.
- Scenes are navigable by keyboard and screen-reader summary.
- Failures are not hidden behind green aggregate status.

---

## 6. Track B - Fabric and data plane

**Thesis:** Evidence Fabric must feel like an operational data plane, not a
source list. Freshness, connector behavior, schema drift, quality budgets and
lineage criticality become primary operational objects.

### B1. Freshness Braid

**Source:** v4 `FreshnessBraid.jsx`.

**Current baseline:** `DataFreshnessBadge` is point-level; there is no
multi-source freshness braid.

**Build:**

- Render each source as a thread: thickness = volume, color/texture =
  lag-vs-SLA, knots = joins/derived facts.
- Show governing lag: the slowest upstream source that determines derived fact
  freshness.
- Connect braid segments to source profiles, connector cards and lineage refs.
- Add compact braid preview in Evidence Fabric hero and full view panel.

**Backend/API contract:**

- `GET /api/v1/fabric/freshness-braid`
- Fields: `source_id`, `volume`, `lag_ms`, `sla_ms`, `governing_lag`,
  `join_nodes`, `derived_fact_refs`.

**Acceptance:**

- Operator can identify the governing lag source in one interaction.
- Braid has tabular fallback: source, lag, SLA, volume, derived facts.
- Color-blind simulation passes for ok/warn/fail threads.

### B2. Connector Character Cards

**Source:** v4 `ConnectorCards.jsx`.

**Current baseline:** Connectors exist through hooks and Evidence Fabric, but
not as operational fingerprints.

**Build:**

- Card per connector with p50/p95 latency, cost, error budget burn,
  retry profile, last-green pull, auth state and data domains served.
- Show "facts through this connector" and "decision packets depending on this
  connector."
- Add lineage badges: every fact can reveal connector path.
- Add connector compare mode for redundant sources.

**Backend/API contract:**

- `GET /api/v1/fabric/connectors/scorecards`
- Add connector id and connector version to lineage compact summary.

**Acceptance:**

- Connector card answers "what should I fix first?" without opening logs.
- Degraded connector propagates visible risk into related quantities.

### B3. Schema Migration Storyboard

**Source:** v4 `SchemaMigration.jsx`.

**Current baseline:** Schema files and validation exist; UI does not narrate
schema history or downstream impact.

**Build:**

- Chapter-by-chapter schema version timeline.
- Each chapter shows diff: added column, removed column, type change,
  semantic change, soft-deprecation, hard break.
- Downstream impact: runs, quantities, decision packets and public exports
  still using old version.
- Replay button scrubs through migrations and updates affected lineage graph.

**Backend/API contract:**

- `GET /api/v1/fabric/schemas/{schema_id}/migrations`
- `GET /api/v1/fabric/schemas/{schema_id}/migration-impact`

**Acceptance:**

- Operator can see whether a schema change is cosmetic, semantic or breaking.
- Replay is URL-stable and emits replay events for Track D3.

### B4. Quality Budget Dashboard

**Source:** v4 `QualityBudget.jsx`.

**Current baseline:** Quality signals exist in validation/fabric tools, but not
as SRE-style budgets in product UI.

**Build:**

- Budgets by dimension: completeness, consistency, accuracy, timeliness,
  reproducibility, identifiability coverage.
- Burn-rate chart, forecast exhaustion, owner/source that spent budget.
- Quarterly baseline and policy-domain comparison.
- Budget depletion can block or warn governance pass.

**Backend/API contract:**

- `GET /api/v1/fabric/quality-budgets`
- `GET /api/v1/fabric/quality-budgets/{budget_id}/burn`
- Add `quality_budget_refs` to governance report.

**Acceptance:**

- Budget panel supports "who spent the budget?" and "when will it exhaust?"
- Governance blockers link back to exact budget dimension.

### B5. Profile Drift as Narrative

**Source:** v4 `ProfileDriftNarrative.jsx`.

**Current baseline:** Drift signals are scattered; no narrative with
citation-grade micro-visuals.

**Build:**

- Deterministic narrative sentence blocks generated from drift stats.
- Embedded micro-viz per claim: sparkline, histogram, KS marker, missingness
  badge, cardinality change.
- Hover over each claim reveals raw stat, sample window, test method and
  source profile.
- Narrative can be inserted into decision packet evidence caveat.

**Backend/API contract:**

- `GET /api/v1/fabric/profiles/{profile_id}/drift-narrative`
- Drift stat schema with `stat_ref`, `method`, `window`, `p_value`,
  `effect_size`, `raw_metric`.

**Acceptance:**

- Narrative is deterministic and reproducible without LLM.
- Every sentence has a citation-grade hover.

### B6. Lineage Gravity Map

**Source:** v4 `LineageGravityMap.jsx`.

**Current baseline:** Lineage graphs and provenance popovers exist; no
force-directed criticality map.

**Build:**

- Force-directed map where node mass = downstream decision dependency.
- Hover answers: "how many decision packets/quantities fail if this source
  degrades?"
- Gravity mode by source, connector, schema, model card, policy and run.
- Integrate with D4 living dependency graph.

**Backend/API contract:**

- `GET /api/v1/fabric/lineage-gravity`
- Fields: `node_id`, `node_type`, `mass`, `blast_radius`, `downstream_refs`,
  `degradation_scenarios`.

**Acceptance:**

- Operator can rank top 10 repair priorities by blast radius.
- Map has accessible list/table and deterministic layout seed.

---

## 7. Track C - Trust, governance and accountability

**Thesis:** A public-sector policy system is not best-in-class unless
objections, fairness, harm, embargo, review friction and revocation are
first-class UX objects.

### C1. Dispute / Objection Registry

**Source:** v4 `DisputeLedger.jsx`.

**Build:**

- Registry timeline for each decision: who objected, when, legal/policy/data
  basis, affected claims, current status and resolution.
- Decision packet embeds open objections as a first-class block.
- Objection can target number, chart, paragraph, causal edge, dataset, model
  card or policy recommendation.

**Contracts:** `GET/POST /api/v1/decisions/{decision_id}/objections`.

**Acceptance:** An unresolved critical objection blocks approval unless a
policy-specific override reason is recorded and visible in audit trail.

### C2. Stakeholder Lens Switcher

**Source:** v4 `StakeholderLens.jsx`.

**Build:**

- Lenses: operator, regulator, appellant, data scientist, public viewer.
- Lens changes emphasis, terminology expansion, collapsed sections and risk
  order while deriving from one Decision AST.
- Add lens-diff test to prove no lens invents content.

**Contracts:** Add `decision_ast`, `lens_projection`, `lens_policy` to
decision packet render API.

**Acceptance:** Same decision hash, different lens projections; all projections
trace to same AST nodes.

### C3. Fairness / Bias Audit Panel

**Source:** v4 `FairnessAudit.jsx`; also Track G4 sentinel.

**Build:**

- Protected attribute slicing, disparate-impact ratio, 4/5ths rule,
  group-conditional confidence intervals, calibration-by-group.
- First-class block in decision packet and compact status in review header.
- Links to harmed cohort and coverage caveat.

**Contracts:** `GET /api/v1/runs/{run_id}/fairness-audit`.

**Acceptance:** Failing fairness criterion can block approval and creates
visible sentinel banner.

### C4. Ethics and Harm Surface

**Source:** not in repo, not in v4; required for serious procurement.

**Build:**

- Expected harm x likelihood x mitigation matrix tied to policy version.
- Required mitigations and residual risk statement.
- Gate integration: no approval until required harm sections are completed.
- EU AI Act mapping: risk class, human oversight, transparency, redress path.

**Contracts:** `GET/PATCH /api/v1/policies/{policy_id}/harm-assessment`.

**Acceptance:** A policy cannot enter approval-ready state with incomplete
critical harm controls.

### C5. Embargo / Blackout Overlay

**Source:** v4 `EmbargoManager.jsx`.

**Build:**

- Global overlay masks embargoed data while preserving structure, layout,
  reason code and unlock condition.
- Reversible reveal after embargo date/approval without changing node identity.
- Embargo awareness in public viewer and exports.

**Contracts:** Add `embargo_state`, `masking_policy`, `unlock_at`,
`reason_code` to data/quantity/lineage payloads.

**Acceptance:** No embargoed value appears in DOM/text export before unlock.

### C6. Slow Review Mode

**Source:** not in repo, not in v4; required to fight approve-by-reflex.

**Build:**

- Review progress shows required sections opened, scrolled, dwelled and
  acknowledged.
- Critical sections: objections, fairness, harm, provenance, uncertainty,
  identifiability, revocation impact.
- No modal. This is an explicit review lane with visible progress.

**Contracts:** `POST /api/v1/reviews/{review_id}/attention-events`.

**Acceptance:** Approval disabled until critical review requirements are met;
events are audit-grade and replayable.

### C7. Revocation Ledger

**Source:** not in repo, not in v4; required for policy lifecycle.

**Build:**

- Trace policy predecessor/successor chain, revoked runs, reprocessed
  decisions, public notices and replacement rationale.
- Bitemporal cursor shows what was valid then vs what is known now.
- Decision packet surfaces "this policy supersedes/revokes..." block.

**Contracts:** `GET /api/v1/policies/{policy_id}/revocation-ledger`.

**Acceptance:** Public viewer can show immutable revocation chain without
login.

---

## 8. Track D - Run choreography and operations

**Thesis:** Long-running policy simulations need operational clarity. The user
should see a run as a score, not a spinner.

### D1. Run Choreography

**Source:** v4 `RunChoreography.jsx`.

**Build:**

- Replace/extend linear timeline with score view:
  parse, plan, check, execute, audit, publish.
- Separate lanes for retries, branches, merges, SSE events, artifact creation,
  connector pulls and governance gates.
- Scrub through run time; selected timestamp updates visible artifacts.

**Contracts:** `GET /api/v1/runs/{run_id}/choreography`.

**Acceptance:** Operator can answer "where is the run stuck?" in one glance.

### D2. Reproducibility Certificate

**Source:** v4 `ProvenanceCertificate.jsx`.

**Build:**

- Generated recipe after run completion: manifest, inputs hashes, policy
  version, connector versions, scenario refs, model refs, environment hash.
- Export as JSON/PDF; signed and verifiable.
- Certificate becomes first-class artifact and public viewer block.

**Contracts:** `POST /api/v1/runs/{run_id}/reproducibility-certificate`.

**Acceptance:** Certificate can be verified offline against artifact hashes.

### D3. Replay Primitive

**Source:** not in v4; extends temporal/provenance work.

**Build:**

- Record drill-downs, threshold changes, scenario explored, lens changes,
  review attention and hover-to-narrate interactions.
- Replay URL reconstructs UX timeline deterministically.
- Use for audit, training and public education.

**Contracts:** `POST /api/v1/replay/sessions`,
`GET /api/v1/replay/sessions/{session_id}`.

**Acceptance:** A replay can be opened in a fresh browser and land on the same
visual states without server-side hidden context.

### D4. Living Dependency Graph

**Source:** extension of B6.

**Build:**

- Mid-level graph: dataset -> connector -> schema -> model card -> policy ->
  run -> decision packet.
- Time-travel aware and gravity-aware.
- Supports "impact of degradation" and "why is this policy coupled to that
  dataset?"

**Contracts:** `GET /api/v1/platform/dependency-graph`.

**Acceptance:** Graph distinguishes field-level lineage from architecture-level
dependency.

### D5. Ambient Telemetry HUD

**Source:** v4 `LiveRunMonitor.jsx`, plus existing run live provider.

**Build:**

- Small always-on dock: SSE pulse, transport health, temporal scope, trust
  threshold, feature flags, API state, offline queue.
- Non-interruptive, collapsible, keyboard reachable.
- Integrates with global sensitivity/trust controls.

**Contracts:** Extend runtime health/capabilities/live status payloads.

**Acceptance:** HUD never obscures primary action and has compact mobile mode.

---

## 9. Track E - Reasoning and comprehension

**Thesis:** Best-in-class means the interface can explain itself. Provenance is
not enough; users need semantic narration, argument structure and deterministic
explanations.

### E1. Argument Map (Toulmin)

**Source:** v4 `ArgumentMap.jsx`, `ReasoningChain.jsx`.

**Build:** Claim -> grounds -> warrant -> backing -> rebuttal graph. Operator
can attack a node; reviewer can certify a branch. Decision packet references
branches by stable ids.

**Contracts:** `GET/PATCH /api/v1/decisions/{decision_id}/argument-map`.

**Acceptance:** Any final recommendation has at least one claim path and
explicit rebuttal status.

### E2. Comprehension Layer

**Source:** not in v4; required for onboarding and accessibility.

**Build:** Global `?` / command action overlays every chart, badge, glyph and
quantity with semantic explanation: what it means, source, update time,
uncertainty and why it matters.

**Contracts:** Frontend semantic registry first; backend annotations later.

**Acceptance:** Every shared visualization registers a comprehension descriptor.

### E3. Hover-to-Narrate Provenance

**Source:** extension of existing provenance popover.

**Build:** Hover over a number animates or steps through lineage nodes in-place:
"show how this was derived." Reduced-motion mode uses stepped highlights.

**Contracts:** Add ordered derivation path to quantity lineage response.

**Acceptance:** Derivation path is visible both as animation and textual list.

### E4. Glossary Lens

**Source:** not in v4; extends lexical discipline.

**Build:** All canonical terms become hover/clickable. Definition carries ADR
source, date fixed, owner and related primitives.

**Contracts:** `docs/brand/LEXICON.md` -> generated JSON vocabulary.

**Acceptance:** No duplicate ad-hoc definitions in UI; glossary is generated
from one source.

### E5. Confidence Ladder Navigation

**Source:** not in v4; extends Trust View.

**Build:** Navigate decision packet by strongest claim, weakest link, disputed,
untraced, low-confidence, high-blast-radius.

**Contracts:** Add ranked claim index to decision AST.

**Acceptance:** Reviewer can jump directly to weakest decision-bearing claim.

### E6. Conversation-grade Deterministic Explanation

**Source:** not in v4; extends deterministic narratives.

**Build:** Every number can generate a non-LLM explanation:
"0.43 because X contributed 45%, Y 32%, residual 23%; vs Q3 dropped 0.07
because X moved +0.2."

**Contracts:** `explanation_parts` attached to Quantity and chart series.

**Acceptance:** Same input always produces same text; text links to raw parts.

---

## 10. Track F - Editorial and publication-grade surfaces

**Thesis:** PolicyOS output must stand up in public, academic and bureaucratic
contexts. It needs not only dashboards, but publishable artifacts.

### F1. Citation-grade Model Cards

**Build:** Academic-style model cards with footnotes, sidenotes, per-section
provenance and bibliography-grade references.

**Contracts:** `GET /api/v1/models/{model_id}/card`.

**Acceptance:** Model card can render as app view, print view and public
read-only view with same refs.

### F2. Public Viewer / Provenance Theatre

**Build:** No-login immutable signed URL for decision packet. Same primitives,
read-only, lens-aware, embargo-aware.

**Contracts:** `GET /public/decisions/{signed_id}` route plus signature
verification.

**Acceptance:** Public viewer never calls privileged APIs and preserves
provenance/trust context.

### F3. Live Coverage Map

**Build:** Geographic evidence coverage map: evidence density, low-coverage
regions and decision caveats.

**Contracts:** `GET /api/v1/evidence/coverage-map`.

**Acceptance:** Decision packet embeds coverage caveat when affected geography
has low evidence density.

### F4. Threshold Microcontract Overlay

**Build:** For policies with cutoffs, show density around threshold, edge
cases, appellants near line and calibration caveat.

**Contracts:** `GET /api/v1/policies/{policy_id}/threshold-contract`.

**Acceptance:** Reviewer can inspect all cases within configurable epsilon of
threshold.

### F5. Locale-aware Bureaucratic Forms

**Build:** Input surfaces for Ukrainian legal forms: наказ, розпорядження,
постанова, висновок. Edit surface and render surface share one AST.

**Contracts:** Extend bureaucratic rendering API with editable AST patches.

**Acceptance:** UA/RU/EN forms preserve ICU plurals, cyrillic typography and
legal section ordering.

---

## 11. Track G - Operator craft and personal reviewer layer

**Thesis:** The system should make expert reviewers more capable over time.
Personal thresholds, annotations, evidence collections and onboarding are part
of the product, not nice-to-have UX.

### G1. Global Sensitivity / Trust Dial

**Build:** HUD slider: hide or de-emphasize everything below confidence/trust
threshold. Distinct from causal E-value rotor but visually coordinated.

**Contracts:** Frontend preference plus optional server-saved reviewer profile.

**Acceptance:** Raising threshold updates all visible decision-bearing content
and shows how much remains.

### G2. Annotation Surface

**Build:** Reviewer can annotate any number, chart, paragraph, causal edge or
artifact. Annotation stores bitemporal snapshot and becomes audit-trail entry.

**Contracts:** `GET/POST /api/v1/annotations`.

**Acceptance:** Annotation reopens the exact snapshot the reviewer saw.

### G3. Evidence Wallet

**Build:** Personal collection of evidence refs, comments and cross-run saved
items. Citation-manager-like, decision-grade.

**Contracts:** `GET/POST /api/v1/evidence-wallet`.

**Acceptance:** Evidence wallet item can be inserted into review, objection or
decision packet note with provenance intact.

### G4. Fairness Sentinel Banner

**Build:** Automatic decision packet banner when fairness threshold fails.
Example: disparate impact ratio below 0.8 for group X blocks approval.

**Contracts:** Uses C3 fairness audit; no separate source of truth.

**Acceptance:** Sentinel cannot be dismissed without creating an audit event.

### G5. Reading-grade Onboarding Flow

**Build:** First-run guided reading, not tooltip tour. Uses glossary lens,
comprehension layer, hover-to-narrate and confidence ladder.

**Contracts:** `onboarding_progress` in preferences; fixture run for training.

**Acceptance:** Measure time-to-first-safe-approval and comprehension task
completion, not click-through.

---

## 12. Phasing and priority

### 12.1. Phase 3.0 - Atlas v4 canonicalization

**Implementation status:** Completed on 2026-04-29.

**Duration:** 1-2 weeks.

**Deliverables:**

- `docs/brand/ATLAS_DESIGN_SYSTEM.md` generated/adapted from v4 README and
  corrected against production.
- `docs/brand/ATLAS_V4_ADOPTION.md` with token conflicts and decisions.
- Storybook reference stories for color, type, shadows, glyphs, buttons,
  badges and cards.
- Drift check comparing `colors_and_type.css` reference tokens with production
  tokens, with intentional differences allowlisted.
- ADR for dark theme canonical choice.

**Acceptance:** Docs and production tokens agree or every difference has an
explicit design decision.

**Implemented artefacts:**

- `docs/brand/ATLAS_DESIGN_SYSTEM.md`
- `docs/brand/ATLAS_V4_ADOPTION.md`
- `docs/brand/atlas-v4/colors_and_type.css`
- `docs/adr/ADR-047-atlas-v4-dark-theme-canonicalization.md`
- `frontend/runtime-dashboard/src/shared/ui/tokens/AtlasV4Reference.stories.tsx`
- `tools/design/check-atlas-v4-token-drift.ts`
- `frontend/runtime-dashboard/package.json` script `design:atlas-v4`

### 12.2. Phase 3.1 - Surface infrastructure

**Implementation status:** Completed on 2026-04-29.

**Duration:** 2 weeks.

**Deliverables:**

- Surface registry for nested workspace panels/tabs.
- Command palette entries for new surfaces.
- Shared semantic explanation registry for Track E2.
- Replay event envelope for Track D3.
- Visual fixture harness for large graph/time visualizations.

**Acceptance:** New surfaces can be added without expanding top-level sidebar.

**Implemented artefacts:**

- `frontend/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts` defines the
  canonical workspace, run-tab and nested-panel registry, including parent
  surfaces, command metadata, route resolution, glyphs, permissions,
  capabilities, semantic explanation ids and visual fixture classification.
- `frontend/runtime-dashboard/src/features/runs/domain/runDetailTabs.ts` now
  derives run inspector tabs from the surface registry instead of maintaining a
  separate tab source of truth.
- `frontend/runtime-dashboard/src/features/commandPalette/CommandPalette.tsx`
  renders navigation, contextual run surfaces and workspace nested surfaces
  from the registry, with route context, feature flags, capabilities and
  permissions applied before entries are shown. Surface commands include
  labels, ids, route ids, aliases and legacy aliases in their searchable command
  value.
- `frontend/runtime-dashboard/src/app/surfaces/semanticExplanationRegistry.ts`
  provides the shared Track E2 explanation registry for surfaces, confidence
  intervals, Atlas glyphs and threshold controls.
- `frontend/runtime-dashboard/src/app/surfaces/replayEvents.ts` defines the
  Track D3 replay event envelope with stable ids, route context, actor context,
  temporal scope, first-class `surface.opened` events and runtime validation
  for replay import.
- `frontend/runtime-dashboard/src/app/surfaces/visualFixtureHarness.ts`
  provides deterministic large-graph and temporal fixtures for graph/time
  visualization stories and tests, including lookup by registered surface
  visualization metadata.
- `frontend/runtime-dashboard/src/app/workspaces.ts` imports run sample query
  options directly to avoid a feature barrel import cycle in surface
  infrastructure.
- Locale keys for command groups and registered nested surfaces are present in
  English, Ukrainian and Russian catalogs.

**Verification:**

- `npm exec vitest run src/app/surfaces/surfaceRegistry.test.ts src/app/surfaces/semanticExplanationRegistry.test.ts src/app/surfaces/replayEvents.test.ts src/app/surfaces/visualFixtureHarness.test.ts src/features/commandPalette/CommandPalette.test.tsx`
  plus `src/features/runs/routes/useRunDetailSummary.test.tsx` passed: 26
  tests.
- `npm run typecheck` passed.
- Targeted `eslint` for surface infrastructure, command palette, run tabs and
  workspace import boundaries passed.
- Phase 3.1 locale keys are present in `en`, `uk` and `ru`; full
  `src/i18n/parity.test.ts` still fails on pre-existing unrelated
  `policyDiff`, `counterfactual` and `quantity.miniGraph.hidden` catalog
  issues.

### 12.3. Phase 3.2 - First production slice

**Duration:** 4-6 weeks.

Implement the smallest cross-track slice that proves the architecture:

1. B1 Freshness Braid.
2. B2 Connector Character Cards.
3. D1 Run Choreography.
4. D5 Ambient Telemetry HUD.
5. A1 Causal Atlas read/edit MVP.
6. C1 Dispute Registry MVP.

**Acceptance:** A run can be inspected through data freshness, connector
health, causal graph, choreography and objection status without leaving Atlas.

**Implementation status:** Complete as of 2026-04-29.

**Implemented production slice:**

- B1 Freshness Braid is implemented in the Evidence Fabric workspace through
  `surface=freshness-braid`, using existing connector, source-profile and run
  evidence context hooks. `productionSlice.ts` derives thread volume,
  lag-vs-SLA state, governing lag, join nodes and decision-bearing derived fact
  pressure. It also falls back to source-profile-only braid threads when the
  connector inventory endpoint is empty or temporarily unavailable.
- B2 Connector Character Cards are implemented in the same Evidence Fabric
  surface switcher through `surface=connector-cards`, with connector
  fingerprint cards for loaded state, namespace/version, latency p50/p95, cost
  tier, error-budget burn, retry posture, profiles, datasets and facts routed
  through the connector.
- Phase 3.2 panel surfaces are registered in the Phase 3.1 surface registry and
  command palette. When opened from an active run, Freshness Braid and
  Connector Character Cards preserve `runId` in the `/evidence` URL so the
  operator lands on run-specific Fabric context.
- D1 Run Choreography is implemented in the run workflow tab, above the
  existing workflow DAG and lineage graph. The choreography adapter merges
  runtime timeline events and workflow nodes into stage lanes with timestamps,
  duration, artifact movement, retries, blocked/running/complete status and
  critical path context, plus branch/retry/artifact signals from span metadata.
- D5 Ambient Telemetry HUD is implemented inside the run detail layout as a
  fixed operator dock. It shows live/degraded transport, runtime transport
  status, temporal scope, active feature-flag posture and current surface while
  the operator remains inside the run inspector.
- A1 Causal Atlas read/edit MVP is implemented in the causal tab. Existing
  causal artifacts are loaded as the graph source; missing artifacts now open a
  draft scaffold instead of an empty state. The MVP supports adding causal
  nodes, selecting node kind, adding directed edges, recomputing simple paths
  and adversarial highlighting for non-identified edges. Draft causal edits are
  persisted locally per run until a canonical causal artifact exists.
- C1 Dispute Registry MVP is implemented in the governance tab. Governance
  issues are projected into objection records and reviewers can add local
  run-scoped objections with basis, target, status, opened timestamp and
  timeline rendering. Reviewer-added objections are persisted locally per run
  until the registry receives a write API.

**Acceptance route proof:**

- Data freshness and connector health are inspectable inside
  `/evidence?runId=:runId` through the Phase 3.2 production slice surface
  switcher.
- Causal graph inspection/editing remains inside `/runs/:runId/causal`.
- Choreography, workflow DAG and lineage remain inside `/runs/:runId/workflow`.
- Objection status remains inside `/runs/:runId/governance`.
- The ambient telemetry HUD follows the run detail shell, so operators keep
  transport and temporal confidence while moving across the Atlas run surfaces.

**Verification:**

- `npx vitest run src/app/surfaces/surfaceRegistry.test.ts src/features/evidence/domain/productionSlice.test.ts src/features/runs/domain/runChoreography.test.ts src/features/evidence/routes/EvidenceFabricPage.test.tsx src/features/runs/routes/runDetailSurfaces.test.tsx`
  passed: 27 tests.
- `npm run typecheck` passed.
- Targeted `eslint` passed for Phase 3.2 domain adapters, panels, routes,
  i18n-consuming components and route tests.
- `src/i18n/parity.test.ts` still fails on pre-existing unrelated locale
  catalog drift (`policyDiff`, `counterfactual`, and
  `shared.ui.quantity.miniGraph.hidden`). The new `phase32` keys are present in
  English, Ukrainian and Russian catalogs and do not introduce additional
  count-sensitive parity failures.

### 12.4. Phase 3.3 - Scientific depth

**Implementation status:** Complete as of 2026-04-29.

**Duration:** 6-8 weeks.

Implement A2, A3, A4, A5 with deterministic data contracts and decision packet
integration.

**Acceptance:** A decision packet can show what is identified, what fails under
sensitivity, which cohort changes over time and which stress scene justifies a
block/warning.

**Implemented production slice:**

- A2 Identifiability Surface is implemented through
  `frontend/runtime-dashboard/src/features/runs/domain/scientificDepth.ts` and
  rendered inside the Atlas decision packet by
  `ScientificDepthPanel.tsx`. Decision metrics are projected into a
  deterministic surface with `point`, `partial`, `set` and `not_identified`
  cells, confidence/Manski/Robins-style bounds method, assumption count,
  decision-impact pressure and a concrete remedy reference derived from the run
  evidence context. Each selected cell also exposes the deterministic
  "what would identify this?" wizard with dataset, covariate, panel, IV, RCT or
  measurement-audit candidates. The weakest cell is computed by identifiability
  rank and decision impact, so reviewer attention goes to the least defensible
  decision-bearing number first.
- A3 Sensitivity Rotor is implemented as a deterministic E-value threshold
  control inside the same packet. Each decision-bearing metric receives a
  reproducible sensitivity score from effect size, uncertainty, statistical
  support and assumption warnings. Moving the rotor live-recomputes which
  claims extinguish, what share of decision-bearing quantities disappears,
  whether an approval verdict would no longer survive and whether
  fairness-related governance gates are affected.
- A4 Cohort Time Traveler is implemented from distributional decision rows and
  the decision timestamp. The panel exposes a valid-time cursor with baseline,
  decision and policy-overlay points, then renders cohort flows with baseline,
  observed and overlay shares from coverage state to policy outcome state.
  Cohort filters and policy-overlay refs are explicit and deterministic, so the
  same decision packet always yields the same time-flow explanation.
- A5 Stress-Test Theatre is implemented as a fixed set of deterministic scenes:
  boring baseline, missing data, adversarial labels, out-of-distribution source,
  legal blocker, fairness blocker and stale evidence. Governance issues and
  evidence-context warnings are matched to scenes by code/message/pass id,
  scene outcomes are classified as pass/warn/block, each scene shows act,
  reaction, diff-vs-baseline and issue refs, and the packet cites the strongest
  immutable stress ref that justifies a warning or block.
- The Phase 3.3 surfaces are registered in the Phase 3.1 surface registry and
  command palette as nested Atlas panels:
  `runs.identifiabilitySurface`, `runs.sensitivityRotor`,
  `runs.cohortTimeTraveler` and `runs.stressTestTheatre`. They resolve into the
  run overview with stable `surface=` query parameters instead of expanding the
  top-level sidebar.
- English, Ukrainian and Russian locale catalogs include the Phase 3.3 panel
  labels, descriptions and decision-packet copy. The implementation uses
  deterministic front-end adapters over the current decision packet,
  governance-issue and evidence-context contracts; when runtime endpoints start
  emitting canonical A2-A5 artefacts, the same panel can swap the adapter input
  without changing the decision-packet surface.

**Acceptance route proof:**

- What is identified appears in `/runs/:runId/overview` inside the decision
  packet under the Identifiability Surface, with per-metric state, bounds,
  remedy, wizard options and impact.
- What fails under sensitivity appears in the Sensitivity Rotor, where the
  E-value threshold live-updates extinguished and remaining claims, the
  decision-bearing share removed, verdict effects and fairness-gate effects.
- Which cohort changes over time appears in the Cohort Time Traveler, where the
  valid-time cursor and distributional cohort flows show baseline, observed and
  policy-overlay outcomes.
- Which stress scene justifies a block/warning appears in Stress-Test Theatre as
  an immutable `stress:{runId}:{sceneId}` citation embedded in the decision
  packet, with scene act, reaction, diff and issue refs visible in the packet.

**Verification:**

- `npx vitest run src/features/runs/domain/scientificDepth.test.ts src/app/surfaces/surfaceRegistry.test.ts src/app/surfaces/semanticExplanationRegistry.test.ts src/app/surfaces/visualFixtureHarness.test.ts src/features/runs/routes/runDetailSurfaces.test.tsx`
  passed: 29 tests covering deterministic A2-A5 contracts, registry command
  routing, semantic explanation coverage, fixture backing and decision packet
  rendering.
- `npm run typecheck` passed.
- Targeted `eslint` passed for the Phase 3.3 domain adapter, panel, registry and
  route test files.
- Phase 3.3 locale keys are present and structurally matched across English,
  Ukrainian and Russian catalogs: `phase33` has 100 matched keys and each new
  surface-registry panel has matching label/description keys. Full
  `src/i18n/parity.test.ts` still fails on pre-existing unrelated catalog drift
  in `policyDiff`, `counterfactual` and `shared.ui.quantity.miniGraph.hidden`.

### 12.5. Phase 3.4 - Governance and public-sector readiness

**Implementation status:** Complete as of 2026-04-29.

**Duration:** 6-8 weeks.

Implement C2-C7 plus G4. Focus on EU AI Act, objections, fairness, harm,
embargo, slow review and revocation.

**Acceptance:** Approval flow can be blocked by fairness, harm, open objection,
embargo violation or insufficient review attention, with every block visible
and auditable.

**Implemented production slice:**

- C2 Stakeholder Lens Switcher is implemented in
  `frontend/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts`
  and rendered by `PublicSectorReadinessPanel.tsx`. Operator, regulator,
  appellant, data-scientist and public-viewer projections all derive from the
  same deterministic decision hash; each lens changes emphasis, collapsed
  sections, terminology and risk ordering without inventing new content.
- C3 Fairness / Bias Audit Panel and G4 Fairness Sentinel Banner are implemented
  in the same readiness adapter. Distributional rows are projected into
  protected-group audit rows with disparate-impact ratio, 4/5ths threshold,
  group confidence band, calibration delta and status. A failed criterion emits
  a first-class sentinel banner and an approval block with an audit ref.
- C4 Ethics and Harm Surface is implemented as an EU AI Act readiness gate with
  expected harm, likelihood, mitigation, residual risk, human oversight,
  transparency and redress path. Critical controls remain blocking until the
  harm review section is acknowledged and no blocking harm issue remains.
- C5 Embargo / Blackout Overlay is implemented as a masking model that preserves
  skeleton refs, reason codes, unlock metadata and audit refs while keeping raw
  embargoed values out of the overlay model. Active embargo masks block approval
  and public export readiness.
- C6 Slow Review Mode is implemented as a run-scoped attention lane with
  required sections for objections, fairness, harm, provenance, uncertainty,
  identifiability and revocation. Each section records open/acknowledge events,
  dwell seconds and replay-grade refs in local storage until the review API is
  available. Approval remains disabled until all required sections are opened,
  dwelled and acknowledged.
- C7 Revocation Ledger is implemented as a deterministic bitemporal policy chain
  with predecessor, current and successor entries, valid/known times, impacted
  runs and replacement rationale. Superseded/revoked policy states become
  visible approval blockers.
- C1 objections are now shared through
  `frontend/runtime-dashboard/src/features/runs/domain/disputes.ts`, so the
  Phase 3.2 Dispute Registry and Phase 3.4 approval gate use the same local
  objection store and governance issue projection.
- The Phase 3.4 nested surfaces are registered in the Phase 3.1 surface registry
  and command palette: `runs.stakeholderLens`, `runs.fairnessAudit`,
  `runs.harmSurface`, `runs.embargoOverlay`, `runs.slowReviewMode` and
  `runs.revocationLedger`.

**Acceptance route proof:**

- Fairness blocks are visible in `/runs/:runId/overview` and
  `/runs/:runId/governance` through the fairness sentinel banner, fairness audit
  panel and approval blocker list.
- Harm blocks are visible through the EU AI Act harm surface, including
  oversight, transparency and redress controls.
- Open objections block approval through the shared Dispute Registry records and
  the readiness blocker list.
- Embargo violations block approval through masked skeleton rows that expose
  reason/unlock/audit metadata without rendering raw restricted values.
- Insufficient review attention blocks approval through Slow Review Mode until
  every critical section is opened, dwelled and acknowledged.
- Revocation/supersession blocks are visible in the Revocation Ledger with
  bitemporal predecessor/current/successor entries and impacted run refs.
- Completeness hardening on 2026-04-29 tightened three production edge cases:
  missing protected-group fairness evidence is itself a fairness blocker,
  embargo masks clear only after `unlock_at` and never expose raw restricted
  values in the readiness model, and revocation chains prefer governance
  metadata for `policy_ref`, predecessor/successor refs, `valid_at`,
  `known_at` and impacted runs before falling back to deterministic local refs.

**Verification:**

- `npx vitest run src/features/runs/domain/publicSectorReadiness.test.ts src/features/runs/domain/scientificDepth.test.ts src/app/surfaces/surfaceRegistry.test.ts src/app/surfaces/semanticExplanationRegistry.test.ts src/app/surfaces/visualFixtureHarness.test.ts src/features/runs/routes/runDetailSurfaces.test.tsx`
  passed: 36 tests covering C2-C7/G4 blockers, lens hash invariants, embargo
  masking, shared objection projection, registry routing, semantic explanation
  coverage, fixture backing and decision packet/governance rendering.
- `npm run typecheck` passed.
- Targeted `eslint` passed for the Phase 3.4 domain adapters, panels, registry,
  governance tab and route tests.
- Phase 3.4 locale keys are present in English, Ukrainian and Russian catalogs.
  Full `src/i18n/parity.test.ts` still fails on pre-existing unrelated catalog
  drift in `policyDiff`, `counterfactual` and
  `shared.ui.quantity.miniGraph.hidden`.

### 12.6. Phase 3.5 - Explanation and publication

**Implementation status:** Complete as of 2026-04-29.

**Duration:** 6-8 weeks.

Implement E1-E6 and F1-F5.

**Acceptance:** A signed public viewer can present a decision, model card,
coverage caveat, threshold contract and deterministic explanations without
private context.

**Implemented production slice:**

- E1 Argument Map is implemented in
  `frontend/runtime-dashboard/src/features/runs/domain/publicationPacket.ts` as
  a deterministic Toulmin graph: claim, grounds, warrant, backing and rebuttal
  nodes with stable ids, statuses and public refs.
- E2 Comprehension Layer is implemented through the Phase 3.1 semantic surface
  registry plus packet-level descriptors for argument map, deterministic
  explanations and public viewer blocks.
- E3 Hover-to-Narrate Provenance is represented as ordered derivation paths for
  every deterministic explanation. The UI renders the public source -> artifact
  -> model -> publication path as a reduced-motion-safe textual sequence.
- E4 Glossary Lens is implemented as a canonical public glossary with term
  definition, owner, fixed date and provenance ref.
- E5 Confidence Ladder Navigation is implemented as ranked public attention
  targets: strongest claim, weakest link, disputed, untraced, low-confidence
  and high-blast-radius.
- E6 Conversation-grade Deterministic Explanation is implemented without LLMs:
  each published number renders a stable narrative from point estimate,
  uncertainty and public provenance parts.
- F1 Citation-grade Model Cards are generated in the same publication adapter
  with sections, footnote refs, provenance refs and bibliography-style
  references.
- F2 Public Viewer / Provenance Theatre is implemented as
  `/public/decisions/:signedId`, backed by a signed, verifiable public payload
  and no privileged run/evidence/governance hooks.
- F3 Live Coverage Map is implemented as a publication-grade coverage caveat:
  geography/evidence density regions mark low-coverage public warnings.
- F4 Threshold Microcontract Overlay is implemented with cutoff, epsilon,
  above/below counts, near-line count, edge cases and calibration caveat.
- F5 Locale-aware Bureaucratic Forms are implemented as public form input specs
  for `Наказ`, `Розпорядження`, `Постанова` and `Висновок`, all sharing a
  `bureaucratic_ast_patch.v1` contract and Ukrainian legal ordering.
- The run decision packet now renders `PublicationReadinessPanel.tsx` after the
  scientific and public-sector readiness gates, exposing the signed public URL
  and all publication blocks inside Atlas.
- Completeness hardening on 2026-04-29 moved `/public/decisions/:signedId` out
  of the runtime/private provider route, so the public viewer is not mounted
  under `RuntimeApiProvider`, `RunsLiveProvider` or the product shell. Public
  route tests assert that no product shell or route telemetry is mounted for
  signed public decisions.
- The publication adapter now applies public-redaction to decision summary text,
  metric labels, cohort labels, coverage region labels and public refs. SSN-like
  ids, long raw numbers, emails, private-reviewer wording, secret/confidential
  wording and raw restricted phrases are redacted before the packet is signed.
- Phase 3.5 surfaces are registered for command palette/deep-link discovery:
  `runs.argumentMap`, `runs.comprehensionLayer`, `runs.glossaryLens`,
  `runs.confidenceLadder`, `runs.modelCard`, `runs.publicViewer`,
  `runs.coverageMap`, `runs.thresholdContract` and `runs.bureaucraticForms`.

**Acceptance route proof:**

- A signed packet created by `buildSignedPublicDecisionPacket` verifies through
  `verifySignedPublicDecisionPacket` and opens at `/public/decisions/:signedId`.
- The public viewer renders the signed decision summary, model card, coverage
  caveat, threshold contract, deterministic explanations, argument map,
  confidence ladder, glossary lens and bureaucratic form specs from the signed
  payload only.
- The publication adapter strips raw governance issue text and raw restricted
  values; tests assert that private strings such as SSN-like values, long raw
  ids, secret/confidential wording and private-reviewer wording do not survive
  in the public packet model.
- Invalid or tampered signed ids are rejected with an explicit invalid-signature
  public state.

**Verification:**

- `npx vitest run src/features/runs/domain/publicationPacket.test.ts src/features/runs/routes/PublicDecisionViewerPage.test.tsx src/features/runs/domain/publicSectorReadiness.test.ts src/features/runs/domain/scientificDepth.test.ts src/app/surfaces/surfaceRegistry.test.ts src/app/surfaces/semanticExplanationRegistry.test.ts src/app/surfaces/visualFixtureHarness.test.ts src/app/routes/routeModules.test.ts src/app/routes/routes.test.tsx src/app/providers/RouteIconProvider.test.tsx src/features/runs/routes/runDetailSurfaces.test.tsx`
  passed: 55 tests covering E1-E6/F1-F5 packet construction, public redaction,
  signing, verification, isolated public rendering, command surfaces,
  route/provider boundaries and run-detail integration.
- `npm run typecheck` passed.
- Targeted `eslint` passed for Phase 3.5 domain, components, routes, surface
  registry and route metadata.
- Phase 3.5 locale keys are present in English, Ukrainian and Russian catalogs.
  Full `src/i18n/parity.test.ts` still fails on pre-existing unrelated catalog
  drift in `policyDiff`, `counterfactual` and
  `shared.ui.quantity.miniGraph.hidden`.

### 12.7. Phase 3.6 - Operator craft

**Implementation status:** Complete as of 2026-04-29.

**Duration:** 4-6 weeks.

Implement G1-G3 and G5. Tighten personal reviewer workflows and onboarding.

**Acceptance:** Reviewer can set threshold, annotate a snapshot, save evidence
to wallet and complete a reading-grade onboarding run.

**Implemented production slice:**

- G1 Global Sensitivity / Trust Dial is implemented in
  `frontend/runtime-dashboard/src/features/runs/domain/operatorCraft.ts` and
  rendered in both `OperatorCraftPanel.tsx` and the always-on
  `AmbientTelemetryHud.tsx`. The reviewer threshold is versioned in local
  storage, emits a `threshold.changed` replay envelope and recomputes visible
  vs hidden confidence-ladder claims from the signed decision packet.
- The ambient HUD now includes a compact trust slider next to SSE transport,
  temporal scope, feature flags and active surface. This makes the threshold a
  persistent reviewer control rather than a buried panel-only setting.
- G2 Annotation Surface is implemented as snapshot-bound reviewer annotations.
  Each annotation stores body, target kind/ref, reviewer id, `packetHash`,
  signed id, `validAt`, `txAt`, surface id and an `annotation.created` replay
  audit event. Targets are derived from verdict, argument-map nodes,
  deterministic explanations, coverage caveat, threshold contract and model
  card refs.
- G3 Evidence Wallet is implemented as a personal saved-evidence store with
  deduplication by evidence ref and packet hash. Wallet candidates are derived
  from public model-card references, deterministic explanation subjects,
  coverage regions and threshold edge cases; saved items keep snapshot refs and
  an `evidence.saved` replay audit event.
- G5 Reading-grade Onboarding Flow is implemented as a run-scoped, versioned
  onboarding state. Steps cover reading the decision packet, inspecting the
  argument map, narrating provenance, opening glossary lens, setting the
  threshold, saving evidence, annotating the packet snapshot and completing safe
  approval. Completion records time-to-first-safe-approval.
- Completeness hardening on 2026-04-29 made onboarding steps explicit rather
  than auto-completed from packet availability. The domain layer now blocks
  `safe_approval` until every required reading, provenance, glossary,
  threshold, wallet and annotation step is complete, and each completed step is
  preserved as an `onboarding.step.completed` replay audit event in the
  run-scoped onboarding state.
- Phase 3.6 replay support extends the Phase 3.1 envelope with
  `annotation.created`, `evidence.saved` and `onboarding.step.completed` event
  kinds, while retaining `threshold.changed` for the global trust dial.
- Phase 3.6 surfaces are registered for command palette/deep-link discovery:
  `runs.globalTrustDial`, `runs.annotationSurface`, `runs.evidenceWallet` and
  `runs.readingOnboarding`. All remain nested panels under existing run
  workspaces, so new reviewer craft does not expand the top-level sidebar.
- English, Ukrainian and Russian locale catalogs include Phase 3.6 copy and
  surface-registry labels/descriptions.

**Acceptance route proof:**

- A reviewer can set the threshold from the ambient HUD or the Operator Craft
  panel in `/runs/:runId/overview`; hidden and visible claims update against
  the signed packet's confidence ladder.
- A reviewer can create an annotation on a specific packet target; the stored
  record includes the exact packet hash, signed id and bitemporal snapshot
  timestamps.
- A reviewer can save evidence to the wallet from model-card, explanation,
  coverage and threshold candidates; repeated saves dedupe to the same wallet
  item for that packet.
- A reviewer can start and complete the reading-grade onboarding flow, with
  progress visible in the decision packet and time-to-first-safe-approval
  persisted after completion.

**Verification:**

- `npx vitest run src/features/runs/domain/operatorCraft.test.ts src/app/surfaces/surfaceRegistry.test.ts src/app/surfaces/replayEvents.test.ts src/features/runs/routes/runDetailSurfaces.test.tsx`
  passed: 27 tests covering threshold persistence, hidden claims, snapshot
  annotations, wallet dedupe, onboarding timing, replay event validation,
  surface registration and run-detail rendering.
- `npm run typecheck` passed.
- Targeted `eslint` passed for Phase 3.6 domain, component, HUD, route,
  replay-event and surface-registry files.
- Phase 3.6 locale keys are present and structurally matched across English,
  Ukrainian and Russian catalogs: `phase36` has 40 matched keys.
- Full `src/i18n/parity.test.ts` still fails on pre-existing unrelated catalog
  drift in `policyDiff`, `counterfactual` and
  `shared.ui.quantity.miniGraph.hidden`; Phase 3.6 keys are not part of that
  failure.

---

## 13. Success metrics

### 13.1. Operator comprehension

- New analyst completes first safe review in under 35 minutes.
- 90% of tested reviewers correctly explain provenance of a selected number.
- 90% correctly identify weakest claim in a decision packet.
- 85% correctly distinguish observed, counterfactual and embargo-masked data.

### 13.2. Scientific rigor

- 100% decision-bearing claims expose identification status.
- 100% causal recommendations link to DAG version and adjustment rationale.
- 100% sensitivity-hidden claims explain threshold failure.
- 0 untraced decision-bearing quantities in release gate.

### 13.3. Operational clarity

- Time to identify degraded upstream source under 20 seconds in Freshness Braid.
- Time to identify stuck run stage under 15 seconds in Run Choreography.
- Top 10 lineage blast-radius nodes visible in one view.
- Connector degradation propagates to affected quantities within one refresh.

### 13.4. Governance and audit

- 100% approvals have completed slow-review critical path.
- 100% overrides have reason, actor, timestamp and affected AST refs.
- 100% public exports have signature, revocation status and provenance refs.
- 0 embargoed values leak into public viewer or text export.

### 13.5. Design quality

- `npm run test:a11y` green.
- `npm run design:polish` green.
- Visual snapshots reviewed for every new surface.
- No new domain color outside token allowlist.
- No raw Unicode domain symbols in production JSX except documented anchors.

---

## 14. Risk register

| Risk                                        | Why it matters                                          | Mitigation                                                               |
| ------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------ |
| Prototype screens copied directly           | Inline styles and raw symbols bypass production quality | Rebuild via shared UI, route contracts and tests                         |
| Sidebar bloat                               | 30+ surfaces destroy orientation                        | Nested surfaces, command palette, contextual links                       |
| Graph visualizations become inaccessible    | Causal/lineage maps are visually dense                  | Mandatory list/table fallback and keyboard graph model                   |
| Too many global controls                    | HUD, trust dial, sensitivity rotor can compete          | Clear separation: trust filters confidence, sensitivity tests robustness |
| Backend contracts lag design                | Screens become mock-only                                | Contract-first ladder and fixture gate                                   |
| Public viewer leaks private data            | Procurement/legal blocker                               | Signed immutable payloads, embargo masking, no privileged API calls      |
| Slow review feels punitive                  | Reviewers may work around it                            | Visible progress, reasoned friction, no surprise modal gates             |
| Harm/fairness gates become checkbox theater | Trust erodes                                            | Tie every gate to evidence, metric, owner and override audit             |
| Dark theme drift                            | v4 archive and repo disagree                            | ADR, token diff, visual snapshots                                        |

---

## 15. Immediate checklist

- [x] Create `docs/brand/ATLAS_DESIGN_SYSTEM.md` from v4 archive, corrected for
      production reality.
- [x] Create `docs/brand/ATLAS_V4_ADOPTION.md` documenting token and dark-theme
      decisions.
- [x] Add Storybook reference stories for v4 preview categories.
- [x] Add token drift check between v4 reference and production tokens.
- [x] Define surface registry and command palette integration for nested
      surfaces.
- [x] Implement B1 Freshness Braid fixture, hook and panel.
- [x] Implement B2 Connector Character Cards fixture, hook and panel.
- [x] Implement D1 Run Choreography fixture, hook and panel.
- [x] Implement D5 Ambient Telemetry HUD MVP.
- [x] Implement A1 Causal Atlas editable MVP.
- [x] Implement C1 Dispute Registry MVP.

---

## 16. Definition of "best-in-class"

PolicyOS Atlas reaches the next best-in-class bar when an external reviewer can
open a decision, move through the same evidence as the internal operator, see
the causal graph and its identification status, understand which numbers are
robust, inspect objections and fairness/harm gates, replay the run
choreography, verify reproducibility, and read a public signed version without
losing provenance.

At that point the product is no longer competing on "better dashboard." It is
competing on a stronger primitive: **policy as inspectable, replayable,
contestable evidence machinery**.
