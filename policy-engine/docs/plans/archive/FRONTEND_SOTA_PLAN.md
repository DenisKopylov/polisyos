---
title: PolicyOS Frontend SOTA Improvement Plan
status: superseded
owner: team-frontend
created: 2026-04-06
last_verified: 2026-07-16
stability: archived
archived: 2026-07-16
superseded_by:
  - ../active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - ../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
disposition_record: ../../brand/ATLAS_SOURCE_OF_TRUTH.md
---

# PolicyOS Frontend — SOTA Improvement Plan

> **Archived 2026-07-16.** This plan is retained as historical frontend
> research and has no execution authority. The Atlas surface constitution and
> Revision 2 master plan supersede it; see
> [the DS0 disposition](../../brand/ATLAS_SOURCE_OF_TRUTH.md#atlas-d1).

> Comprehensive plan to bring the PolicyOS frontend to state-of-the-art
> without compromises in design, functionality, personalization, explainability,
> and intuitiveness.
>
> Date: 2026-04-06 | Status: approved plan (v2 — expanded with 2026 SOTA research)

---

## Contents

1. [Current State & Audit](#1-current-state--audit)
2. [SOTA Principles for GovTech/Research Frontends](#2-sota-principles-for-govtechresearch-frontends)
3. [Explainability & Trust](#3-explainability--trust)
4. [Progressive Disclosure & Dual-Persona UX](#4-progressive-disclosure--dual-persona-ux)
5. [Data Storytelling & Narrative Visualization](#5-data-storytelling--narrative-visualization)
6. [Causal Visualization Engine](#6-causal-visualization-engine)
7. [Uncertainty Visualization](#7-uncertainty-visualization)
8. [Personalization & Adaptive UI](#8-personalization--adaptive-ui)
9. [Design System Evolution](#9-design-system-evolution)
10. [Micro-Interactions & Motion Design](#10-micro-interactions--motion-design)
11. [Accessibility (WCAG 2.2 AAA)](#11-accessibility-wcag-22-aaa)
12. [Performance & Architecture](#12-performance--architecture)
13. [Real-Time Collaboration](#13-real-time-collaboration)
14. [Chat & Conversational UX (Clerk Mode)](#14-chat--conversational-ux-clerk-mode)
15. [Keyboard-First & Power User Features](#15-keyboard-first--power-user-features)
16. [Run Comparison & Reproducibility](#16-run-comparison--reproducibility)
17. [What-If Analysis & Interactive Parameters](#17-what-if-analysis--interactive-parameters)
18. [Internationalization](#18-internationalization)
19. [Responsive & Mobile](#19-responsive--mobile)
20. [Legal Compliance](#20-legal-compliance)
21. [Observability & Analytics](#21-observability--analytics)
22. [Implementation Phases](#22-implementation-phases)
23. [Success Metrics](#23-success-metrics)

---

## 1. Current State & Audit

### Strengths (what we already have)

| Area                  | Level         | Details                                                                                                                                                                             |
| --------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Component library** | Good          | 50+ components: Button, Card, Badge, DataTable, VirtualTable, VirtualList, LineageGraph, JsonPreview, StatusTimeline, DecisionCard, EvidenceChain, etc.                             |
| **Design tokens**     | Good          | `designTokens.ts` with foundation (13 color, 3 motion, 3 radius, 2 shadow, 4 spacing, 2 typography) and semantic (action, evidence, governance, severity, status, transport) tokens |
| **Theming**           | Good          | Full dark mode via CSS custom properties with `data-theme="dark"`, glass morphism, radial gradients                                                                                 |
| **Accessibility**     | Good baseline | `.a11y.test.tsx` per shared component, skip-to-content, focus-visible, LiveAnnouncerProvider, prefers-reduced-motion                                                                |
| **API layer**         | Excellent     | 50+ React Query hooks, type-safe openapi-fetch from OpenAPI schema, queryKeys factory, retry policy, optimistic updates                                                             |
| **Real-time**         | Good          | SSE transport with XState state machine (`runsLiveMachine.ts`), degradation fallback, heartbeat/reconnection                                                                        |
| **i18n**              | Basic         | 2 locales (en/uk), `useI18n().t()` pattern                                                                                                                                          |
| **Storybook**         | Good          | Stories for shared components, Vitest addon                                                                                                                                         |
| **Testing**           | Good          | 99 test files, 258 tests, a11y tests, Playwright E2E, visual regression                                                                                                             |
| **Feature flags**     | Complete      | Remote manifest + localStorage + env vars, 5-priority resolution                                                                                                                    |
| **Offline**           | Basic         | Service worker, OfflineQueueProvider, IndexedDB drafts, Background Sync                                                                                                             |
| **Providers**         | 14 providers  | Auth -> Authz -> FeatureFlags -> InterfaceMode -> Theme, etc.                                                                                                                       |
| **Architecture**      | Mature        | eslint-plugin-boundaries + dependency-cruiser enforced feature slices                                                                                                               |
| **Security**          | Good          | Auth session, silent refresh, 401 replay, SRI on assets, CSP report                                                                                                                 |
| **Bundle**            | Good          | Manual code splitting (7 vendor chunks), lazy route components                                                                                                                      |

### Gaps -- what is missing for SOTA

| Area                       | Gap                                                                         | Criticality |
| -------------------------- | --------------------------------------------------------------------------- | ----------- |
| **Explainability**         | No UI for causal decision explanation (SHAP, DAG, proof steps)              | CRITICAL    |
| **Uncertainty viz**        | No visualization for confidence intervals, bounds, uncertainty envelopes    | CRITICAL    |
| **Causal DAG**             | No interactive causal graph -- backend is ready (discovery, identification) | CRITICAL    |
| **Component foundation**   | Custom primitives instead of battle-tested accessible library (shadcn/ui)   | CRITICAL    |
| **Data storytelling**      | No narrative flow for analysis results                                      | HIGH        |
| **Progressive disclosure** | Analyst dashboard shows everything at once, no layered drill-down           | HIGH        |
| **Personalization**        | No adaptive layout, saved views, user preferences                           | HIGH        |
| **Charting**               | Only chartTheme.ts -- no production charting library integrated             | HIGH        |
| **Run comparison**         | Cannot compare 2+ runs side-by-side (W&B-style)                             | HIGH        |
| **What-if analysis**       | No parameter sliders showing instant impact on outcomes                     | HIGH        |
| **Collaboration**          | ReviewCollaborationHub exists on backend, no frontend implementation        | HIGH        |
| **Split-pane layout**      | No resizable panels for simultaneous DAG + evidence + results view          | HIGH        |
| **Governance UI**          | Governance tab exists but no interactive pass/fail exploration              | MEDIUM      |
| **Keyboard shortcuts**     | No command palette, no global shortcuts                                     | MEDIUM      |
| **Onboarding**             | No guided tours, contextual help, tooltips                                  | MEDIUM      |
| **Animation**              | Only CSS transitions, no orchestrated motion                                | MEDIUM      |
| **Activity feed**          | No reverse-chronological event log for team awareness                       | MEDIUM      |
| **AI diff view**           | No review interface for AI-generated policy drafts (Hex pattern)            | MEDIUM      |
| **Density toggle**         | No compact/spacious mode for different user segments                        | MEDIUM      |
| **Responsive**             | Basic breakpoints, sidebar collapse, but complex layouts not adapted        | MEDIUM      |
| **Reproducibility**        | No "reproduce this run" button from run detail                              | MEDIUM      |
| **Print/export**           | dataExport.ts (CSV/JSON) but no PDF report generation                       | LOW         |

---

## 2. SOTA Principles for GovTech/Research Frontends

Based on research: USWDS (US Web Design System), GOV.UK Design System, Palantir Foundry UX, Bloomberg Terminal, Tableau, Linear, W&B, Hex, Observable, and academic XAI/HCI sources (2025-2026).

### 2.1 Five Pillars (from USWDS Design Principles, adapted)

1. **Start with real user needs** -- every screen solves a concrete task for a clerk or analyst
2. **Earn trust** -- show provenance, methodology, uncertainty; never hide limitations
3. **Embrace accessibility** -- WCAG 2.2 AA minimum, strive for AAA in key flows
4. **Be consistent, not uniform** -- unified design system, adapted to context (clerk != analyst)
5. **Make the hard things possible** -- progressive disclosure: simple by default, powerful when needed

### 2.2 Additional Principles for PolicyOS

1. **Honest uncertainty** -- NegativeCertificate and bounds are as important as point estimates. UI must make uncertainty a first-class citizen
2. **Explainability by default** -- every result has drill-down to methodology, data sources, proof steps
3. **Narrative over noise** -- data tells a story: question -> analysis -> evidence -> decision -> governance
4. **Audit-ready** -- every screen can be exported as a reproducible report
5. **Calm technology** -- notifications and alerts proportional to severity; no alarm fatigue
6. **Keyboard-first for power users** -- every action reachable via keyboard, CMD+K as the universal entry point (Linear pattern)
7. **Governed AI context** -- NL interface grounded in domain ontology, not raw schemas (ThoughtSpot/Hex pattern)

### 2.3 Reference Platforms and What We Learn from Each

| Platform                   | Key Lesson for PolicyOS                                                                                          |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Palantir Foundry**       | Split-pane layouts for simultaneous views; DAG lineage visualization; composition over configuration             |
| **Bloomberg Terminal**     | Information density for power users; keyboard-first operation; dark-theme optimized                              |
| **Linear**                 | CMD+K command palette as universal entry; keyboard-only mode; micro-interactions that guide attention            |
| **W&B (Weights & Biases)** | Run comparison with parallel coordinates; experiment tracking UI; synchronized multi-panel views                 |
| **Hex**                    | Notebook + diff view for AI-proposed changes; question-to-first-draft experience; version history for governance |
| **Observable**             | Reactive notebooks; linked views with brushing/filtering; Plot library for rapid exploration                     |
| **Tableau**                | Progressive disclosure in analytics; LOD (Level of Detail) expressions; visual drag-and-drop                     |
| **Neptune AI**             | 100K+ run comparison at scale; parameter summary per run; artifact lineage trees                                 |
| **DAGitty**                | Interactive causal DAG editing; identifies adjustment sets (frontdoor, backdoor) in browser                      |
| **USWDS / GOV.UK**         | Government-grade accessibility; mobile-first design; trust patterns                                              |

---

## 3. Explainability & Trust

### 3.1 Problem

Backend PolicyOS generates rich explainability artifacts:

- `ProofBundle` with proof_status, theorem_family, estimand_ast, proof_trace
- `EvidenceBundle` with data_provenance, compilation_steps, estimation_steps, diagnostic_scores
- `NegativeCertificate` with blocking_type, suggested_experiments
- `CrossGraphEvidenceProfile` with 4D confidence (academic x dataset x legal x transport)
- 20 governance passes with `ComplianceIssue` per pass
- `CalibrationReport` with fit_quality, identifiability, series comparisons

The frontend currently shows only tables and JSON preview.

### 3.2 XAI Dashboard Framework

**Principle**: every AI/ML result is accompanied by three explanation levels (per XAI best practices 2025-2026, Carloni et al.):

| Level         | Audience            | Content                                                         |
| ------------- | ------------------- | --------------------------------------------------------------- |
| **Glance**    | Clerk, executive    | 1-sentence verdict + confidence badge + traffic light           |
| **Summary**   | Analyst             | Key factors, methodology, data quality, governance status       |
| **Deep dive** | Researcher, auditor | Full proof trace, SHAP/attribution, raw data, alternative specs |

#### New Components

```text
src/shared/ui/compounds/
  ExplainabilityCard.tsx        -- 3-level drill-down card for any result
  ConfidenceIndicator.tsx       -- visual confidence (gauge, bar, traffic light)
  ProvenanceChain.tsx           -- clickable provenance trail: data -> method -> result
  GovernancePassGrid.tsx        -- visual grid of 20 passes: pass/fail/warning/skip
  MethodologyBadge.tsx          -- shows method (DiD, SC, TMLE) with tooltip explanation
  NegativeCertificateCard.tsx   -- "why we cannot give a precise answer" + suggested experiments
  EvidenceCoverageRadar.tsx     -- 4D radar chart (academic x dataset x legal x transport)
```

#### ExplainabilityCard -- the key component

```tsx
<ExplainabilityCard
  level="summary" // glance | summary | deep
  verdict={{ status: "approved", confidence: 0.87 }}
  methodology="difference-in-differences"
  keyFactors={[
    { label: "Treatment effect", value: "+2.3%", direction: "positive" },
    { label: "Parallel trends", value: "passed", direction: "neutral" },
    { label: "Sample size", value: "n=12,400", direction: "positive" },
  ]}
  governance={{ passed: 18, failed: 1, warnings: 1, blockers: ["equity"] }}
  expandTo="deep" // button for drill-down
/>
```

### 3.3 Attribution Visualization

For causal analysis results -- adaptation of SHAP waterfall for policy context:

```text
src/features/runs/components/
  AttributionWaterfall.tsx      -- SHAP-like waterfall: base -> feature contributions -> prediction
  FactorImportanceChart.tsx     -- horizontal bars with influence direction
  SensitivitySpider.tsx         -- sensitivity analysis spider/radar chart
```

**Waterfall flow**: base prediction -> covariate adjustments -> treatment effect -> bounds -> final estimate. Each step clickable for drill-down to underlying data.

### 3.4 Trust Calibration

Implementation of trust calibration principles from HCI research:

- **Confidence calibration display** -- show not only point estimate but also "how often this model is right" from historical data
- **Disagreement alerts** -- when multiple methods give different answers, explicitly show the spread with a forest plot
- **Limitation cards** -- explicitly list assumptions and where they may not hold
- **"Why you should NOT trust this"** section -- counter-arguments and refutation results
- **Historical accuracy** -- "In past analyses with this methodology, our predictions were within the 95% CI in X% of cases"

### 3.5 AI Reasoning Chain Transparency

When the system produces a policy claim via the NL interface, display the full reasoning chain:

```text
User question -> Interpreted query -> Data retrieved -> Causal analysis -> Conclusion
```

Each step is expandable and shows:

- What the system decided to do
- What data it used
- What alternatives it considered
- Why it chose this approach

This is the **governed context** pattern from ThoughtSpot/Hex that separates production tools from demos.

---

## 4. Progressive Disclosure & Dual-Persona UX

### 4.1 Principle

NN/Group 2025: "Progressive disclosure reduces users' cognitive load by gradually revealing information as needed." For PolicyOS:

- **Clerk**: sees the answer, confidence, one sentence; can expand "Details"
- **Analyst**: sees dashboard with metrics; can drill-down into each metric
- **Researcher**: sees full proof trace, raw data, specification curves

### 4.2 Layered Information Architecture

```text
Level 0: Verdict Card
  +-- Status badge (approved/rejected/review)
  +-- Confidence gauge
  +-- One-sentence summary

Level 1: Key Metrics (click "Details")
  +-- Treatment effect +/- CI
  +-- Methodology used
  +-- Data quality score
  +-- Governance status
  +-- Key risk factors

Level 2: Analysis Deep Dive (click "Full Analysis")
  +-- Causal DAG
  +-- Estimation details
  +-- Specification curves
  +-- Sensitivity analysis
  +-- Evidence coverage radar
  +-- Full governance report

Level 3: Audit Trail (click "Audit Package")
  +-- Proof bundle
  +-- Raw data provenance
  +-- Computation lineage
  +-- Artifact signatures
  +-- Export as PDF/DOCX
```

### 4.3 Analyst Dashboard Redesign

Current dashboard -- flat list. SOTA redesign:

```text
src/features/dashboard/
  components/
    DashboardCanvas.tsx           -- configurable grid layout (react-grid-layout or @dnd-kit)
    WidgetRegistry.tsx            -- registry of draggable widgets
    QuickInsightsPanel.tsx        -- AI-generated summary of recent activity
    RecentRunsTimeline.tsx        -- chronological timeline with status indicators
    ActiveAlertsStrip.tsx         -- governance blockers needing attention
    DataFreshnessMatrix.tsx       -- connector health grid
    SystemHealthPulse.tsx         -- animated system status indicator
    ActivityFeed.tsx              -- reverse-chronological team event log
```

**Widget-based dashboard**: user can drag widgets, save layouts. Default layout per mode (clerk/analyst).

### 4.4 Density Toggle

Analytical users want compact tables; executive users want spacious cards. Palantir's pattern of user-segmented density:

```typescript
type DensityPreference = "compact" | "comfortable" | "spacious";
```

| Density     | Row height | Font size | Padding   | Target user                    |
| ----------- | ---------- | --------- | --------- | ------------------------------ |
| Compact     | 32px       | 13px      | 4px 8px   | Power analyst, Bloomberg-style |
| Comfortable | 44px       | 14px      | 8px 12px  | Default analyst                |
| Spacious    | 56px       | 16px      | 12px 16px | Clerk, executive               |

Toggle available in user preferences and workspace-level override.

### 4.5 Split-Pane Resizable Layout

Users need to see the DAG, the evidence table, and the results simultaneously. Use resizable panels (`react-resizable-panels`) instead of modal overlays:

```text
src/shared/ui/layout/
  ResizablePanelGroup.tsx        -- wrapper for resizable panel groups
  ResizablePanel.tsx             -- individual resizable panel
  ResizableHandle.tsx            -- drag handle between panels
```

**Key layouts**:

- Run detail: DAG (left) | Details (center) | Evidence (right) -- 3-pane
- Evidence review: Source list (left) | Document preview (right) -- 2-pane
- Causal analysis: Graph (top) | Estimation details (bottom) -- vertical split

All panel sizes persisted to user preferences.

### 4.6 Workspace-Specific Information Density

| Workspace      | Clerk Density                           | Analyst Density                                                       |
| -------------- | --------------------------------------- | --------------------------------------------------------------------- |
| Command Center | 1 verdict card, timeline, activity feed | Widget grid, metrics, alerts                                          |
| Runs           | Status + one-line summary               | Full table + filters + comparisons                                    |
| Run Detail     | Summary card + actions                  | Tabs: Overview, Timeline, DAG, Governance, Evidence, Artifacts, Debug |
| Evidence       | Hidden                                  | Full evidence fabric + search + promotion                             |
| Knowledge      | Hidden                                  | Lex knowledge graph + search                                          |
| Platform       | Hidden                                  | Health metrics + connector status                                     |

---

## 5. Data Storytelling & Narrative Visualization

### 5.1 Principle

From research: "A well-designed dashboard should have a logical flow like a good novel: introduction, development, climax, conclusion." PolicyOS has a natural narrative:

```text
Policy Question -> Causal Discovery -> Identification -> Estimation ->
Bounds -> Sensitivity -> Strategic Response -> Governance -> Decision
```

### 5.2 Run Narrative View

New mode for viewing run results -- not tables, but a story:

```text
src/features/runs/components/narrative/
  RunNarrativeView.tsx           -- full-page scrollable narrative
  NarrativeChapter.tsx           -- chapter wrapper with anchor navigation
  QuestionSetup.tsx              -- "The question being asked"
  DataLandscape.tsx              -- "What data is available" (evidence coverage)
  MethodSelection.tsx            -- "How we approached this" (methodology rationale)
  FindingsPresentation.tsx       -- "What we found" (treatment effects, charts)
  RobustnessCheck.tsx            -- "How confident are we" (sensitivity, bounds)
  GovernanceVerdict.tsx          -- "Is this safe to act on" (governance passes)
  RecommendationSummary.tsx      -- "What to do next" (decision packet)

  shared/
    NarrativeTransition.tsx      -- animated transition between chapters
    InsightCallout.tsx           -- highlighted insight boxes
    AnnotatedChart.tsx           -- chart with AI-generated annotations
```

### 5.3 Annotated Charts

Every chart is accompanied by contextual annotations:

```tsx
<AnnotatedChart
  type="timeseries"
  data={treatmentEffectOverTime}
  annotations={[
    { x: "2024-06", label: "Policy enacted", type: "event" },
    { x: "2024-09", label: "Effect becomes significant", type: "insight" },
    { x: "2025-01", label: "Strategic response detected", type: "warning" },
  ]}
  confidenceBand={{ upper: upperBound, lower: lowerBound }}
/>
```

### 5.4 Charting Library Strategy

**Dual-library approach** (based on 2026 landscape analysis):

| Library             | Role                             | Bundle        | Use cases                                                                      |
| ------------------- | -------------------------------- | ------------- | ------------------------------------------------------------------------------ |
| **Recharts** (keep) | High-level standard charts       | ~45KB         | Dashboard KPIs, time series, bar comparisons, quick prototyping                |
| **visx** (add)      | Custom analytical visualizations | ~15KB modular | Causal DAG, uncertainty plots, SHAP waterfall, specification curves, novel viz |

**Why visx**: Airbnb's low-level React primitives for D3-like visualizations with full control. Modular architecture means you only import needed packages. Gives D3-level control for novel analytical visualizations without abandoning Recharts for standard charts.

**For tables with 50K+ rows**: existing `@tanstack/react-virtual` + TanStack Table for sortable, resizable, pinnable columns with virtualization.

**Monitor**: ECharts if >100K data points needed (Canvas rendering for massive datasets where SVG struggles).

```text
src/shared/charts/
  index.ts
  AreaChart.tsx                  -- time series with confidence bands
  BarChart.tsx                   -- comparison bars
  WaterfallChart.tsx             -- attribution waterfall
  RadarChart.tsx                 -- multi-dimension comparison
  ForceGraph.tsx                 -- interactive DAG/network
  ParallelCoordinates.tsx        -- multi-variable exploration (W&B pattern)
  SpecificationCurve.tsx         -- specification curve plot
  FunnelChart.tsx                -- conversion/pipeline funnel
  ForestPlot.tsx                 -- multi-study effect comparison
  chartAccessibility.ts          -- ARIA descriptions, pattern fills for colorblind
  chartTheme.ts                  -- extended theme with semantic chart tokens
```

---

## 6. Causal Visualization Engine

### 6.1 Motivation

Backend PolicyOS contains one of the most advanced causal inference systems. The frontend must visualize:

1. **Causal DAG** -- directed acyclic graph of causal relationships
2. **Identification status** -- which paths are identified, which are not
3. **Estimation results** -- treatment effects per edge
4. **Transport map** -- which results transfer between contexts
5. **Strategic response** -- where agent adaptation is expected
6. **Adjustment sets** -- backdoor, frontdoor, instrumental variable sets (DAGitty pattern)

### 6.2 Interactive Causal Graph

Inspired by DAGitty (browser-based causal DAG editor) and Palantir Foundry lineage view:

```text
src/features/causal/
  components/
    CausalGraphCanvas.tsx        -- interactive canvas (zoom, pan, select) via visx
    CausalNode.tsx               -- node with type indicators (treatment, outcome, confounder, mediator, collider)
    CausalEdge.tsx               -- edge with direction, strength, status overlay
    CausalGraphControls.tsx      -- toolbar: layout algorithm, filter, highlight paths
    IdentificationOverlay.tsx    -- highlight identified vs unidentified paths
    TransportOverlay.tsx         -- show which edges transport across contexts
    InterferenceOverlay.tsx      -- network/interference visualization
    AdjustmentSetHighlight.tsx   -- highlight backdoor/frontdoor adjustment sets

  panels/
    NodeDetailPanel.tsx          -- side panel: variable details, evidence, data availability
    EdgeDetailPanel.tsx          -- edge: effect estimate, CI, methodology, literature support
    PathAnalysisPanel.tsx        -- causal path analysis: direct, indirect, total effects
    CompareGraphsPanel.tsx       -- overlay two causal graphs from different runs

  layouts/
    dagittyLayout.ts             -- constraint-based layout (DAGitty-style, uses d3-dag)
    forceLayout.ts               -- force-directed layout
    hierarchicalLayout.ts        -- top-down hierarchical
```

**Rendering strategy**: SVG for graphs up to ~100 nodes (visx); Canvas (via pixi.js or custom) for 100+ nodes. Virtualize off-screen nodes for performance.

### 6.3 Visual Language for the Causal Graph

| Element            | Visual                    | Meaning                    |     |                 |
| ------------------ | ------------------------- | -------------------------- | --- | --------------- |
| Treatment node     | Teal fill, diamond shape  | Treatment variable         |     |                 |
| Outcome node       | Gold fill, circle         | Target outcome             |     |                 |
| Confounder         | Slate fill, square        | Confounder                 |     |                 |
| Mediator           | Accent fill, rounded rect | Mediator                   |     |                 |
| Collider           | Warning fill, hexagon     | Collider                   |     |                 |
| Identified edge    | Solid line, teal          | Identified relationship    |     |                 |
| Unidentified edge  | Dashed line, ember        | Unidentified relationship  |     |                 |
| Bounds-only edge   | Dotted line, gold         | Only bounds available      |     |                 |
| S-node (transport) | Red diamond overlay       | Selection node (transport) |     |                 |
| Edge thickness     | Proportional to           | effect                     |     | Effect strength |
| Edge label         | Effect +/- CI             | Point estimate             |     |                 |

**Keyboard navigation**: arrow keys to traverse nodes, Enter to select, Tab to cycle panels. Screen reader announces node type, connections, and effect estimates.

### 6.4 Method-Specific Causal Visualizations

Each causal method has its canonical visualization pattern:

**Difference-in-Differences (DiD)**:

- Treatment group (solid line) vs control group (dashed line) over time
- Vertical annotation line at intervention point
- Counterfactual trajectory as dashed extension of pre-treatment trend
- Gap between actual and counterfactual = causal effect
- Confidence bands around estimated effect

**Synthetic Control**:

- Treated unit (solid) vs synthetic control (dashed) -- pre/post intervention
- Pre-intervention fit quality as visual trust indicator
- Placebo test overlay: effects for each control unit -- treated unit's effect should be largest
- Weights table: which control units compose the synthetic

**Regression Discontinuity (RDD)**:

- Scatter plot: running variable (x) vs outcome (y)
- Vertical cutoff line at threshold
- Separate polynomial fits on each side with confidence bands
- Discontinuity (jump) at cutoff = causal effect
- McCrary density test visualization (no manipulation check)

**BSTS (Bayesian Structural Time Series)**:

- Observed series vs posterior predictive distribution (shaded band)
- Pointwise causal effect with credible interval
- Cumulative causal effect over time

**Meta-Learners (HTE)**:

- CATE distribution across subgroups
- Feature importance for treatment effect heterogeneity
- Policy targeting rules visualization

```text
src/features/causal/components/methods/
  DiDVisualization.tsx           -- parallel trends + treatment effect
  SyntheticControlViz.tsx        -- treated vs synthetic + placebo tests
  RDDVisualization.tsx           -- scatter + cutoff + local polynomial
  BSTSVisualization.tsx          -- observed vs counterfactual prediction
  MetaLearnerViz.tsx             -- CATE distribution (HTE)
  ForestPlot.tsx                 -- forest plot for multi-study effects
```

### 6.5 Pipeline Progress Visualization

For running workflows -- visual pipeline with real-time status:

```text
src/features/runs/components/
  PipelineProgressView.tsx       -- horizontal pipeline stages
  StageCard.tsx                  -- individual stage card with progress
  StageTransition.tsx            -- animated transition between stages
```

Pipeline stages map to Scientist workflow nodes:

```text
Preflight -> Discovery -> Identification -> Estimation -> Bounds ->
Sensitivity -> Strategic Response -> Transport -> Governance -> Decision
```

Each stage shows: status (pending/running/complete/failed), duration, key metrics. Running stages show animated progress indicator.

---

## 7. Uncertainty Visualization

### 7.1 Principle

From research (Claus Wilke "Fundamentals of Data Visualization", Confidence Visualization Patterns from agentic-design.ai):

- Expert users: graded error bars, specification curves, sensitivity plots
- Non-expert users: frequency framing, icon arrays, traffic lights
- Both: graded confidence bands at 50%, 80%, 95% intervals (more informative than single CI)

PolicyOS generates `UncertaintyEnvelope` for every result. The UI must visualize this.

### 7.2 Dual-Audience Uncertainty Display

**Clerk (intuitive)**:

```text
+---------------------------------------------+
|  Policy effect: POSITIVE                     |
|                                              |
|  =====================------ 87% confident   |
|                                              |
|  "In 87 out of 100 scenarios this law        |
|   increases employment by 1.5-3.2%"          |
|                                              |
|  [Details]                                   |
+---------------------------------------------+
```

**Analyst (statistical)**:

```text
+---------------------------------------------+
|  ATE: 2.3% [95% CI: 1.5%, 3.2%]            |
|  Method: DML (Double Machine Learning)       |
|                                              |
|  ---+  +------[====]------+  +---            |
|  0%     1.5%    2.3%      3.2%    5%         |
|                                              |
|  Bounds: [0.8%, 4.1%] (partial ID)           |
|  Sensitivity: gamma = 2.1 (robust)           |
|  Specification curve: 94% positive           |
|                                              |
|  [Specification Curve] [Bounds Detail]       |
+---------------------------------------------+
```

### 7.3 Graded Confidence Bands

Show 50%, 80%, and 95% intervals using progressively lighter fills. This is more informative than a single CI and is the SOTA pattern (Wilke 2025):

```text
Darkest fill:  50% interval (most likely range)
Medium fill:   80% interval
Lightest fill: 95% interval
```

Applied to all time series, effect estimates, and prediction visualizations.

### 7.4 Frequency Framing Toggle

Let users switch between statistical and frequency-framed representations:

- **Statistical**: "The estimated effect is 12.3% (95% CI: 8.1-16.5%)"
- **Frequency**: "In 19 out of 20 analyses, the effect falls between 8.1% and 16.5%"

For Clerk mode, default to frequency framing. For Analyst mode, default to statistical.

### 7.5 New Components

```text
src/shared/ui/compounds/
  UncertaintyDisplay.tsx         -- dual-mode uncertainty visualization
  ConfidenceGauge.tsx            -- circular gauge with confidence level
  FrequencyDots.tsx              -- "icon array" visualization (100 dots, N highlighted)
  GradedErrorBar.tsx             -- confidence interval with graded shading (50/80/95%)
  BoundsComparisonChart.tsx      -- compare point estimate vs bounds
  SpecificationCurveChart.tsx    -- specification curve with highlighted main spec
  SensitivityPlot.tsx            -- Gamma-sensitivity plot (Rosenbaum bounds)
  ConfidenceDial.tsx             -- Low/Medium/High dial with color gradient (for quick scanning)
```

### 7.6 Uncertainty-First Design Tokens

```css
:root {
  --color-confidence-high: var(--teal);
  --color-confidence-medium: var(--gold);
  --color-confidence-low: var(--ember);
  --color-bounds-fill: rgba(28, 139, 130, 0.08);
  --color-bounds-stroke: rgba(28, 139, 130, 0.3);
  --color-ci-50: rgba(28, 139, 130, 0.25);
  --color-ci-80: rgba(28, 139, 130, 0.15);
  --color-ci-95: rgba(28, 139, 130, 0.06);
}
```

---

## 8. Personalization & Adaptive UI

### 8.1 Principle

From research 2025-2026: "Adaptive UI dynamically changes structure and behavior based on contextual inputs -- rearranging dashboards, modifying navigation, displaying personalized content."

### 8.2 User Preferences System

```text
src/app/state/
  useUserPreferences.ts          -- Zustand store + localStorage/server sync
```

**Persistence model**:

```typescript
type UserPreferences = {
  // Layout
  dashboardLayout: WidgetLayout[];
  defaultWorkspace: WorkspaceKey;
  sidebarCollapsed: boolean;
  density: "compact" | "comfortable" | "spacious";
  panelSizes: Record<string, number[]>; // persisted split-pane sizes

  // Data display
  preferredMetricFormat: "percentage" | "absolute" | "per_capita";
  uncertaintyDisplayMode: "intuitive" | "statistical" | "both";
  defaultConfidenceLevel: 0.9 | 0.95 | 0.99;
  frequencyFraming: boolean; // use frequency framing for uncertainty

  // Analysis
  favoriteMethodologies: string[];
  pinnedConnectors: string[];
  recentSearches: string[];
  recentJurisdictions: string[];

  // Notifications
  alertSeverityThreshold: "blocker" | "warning" | "info";
  emailDigestFrequency: "daily" | "weekly" | "never";

  // Accessibility
  reducedMotion: boolean;
  highContrast: boolean;
  fontSize: "default" | "large" | "xlarge";
};
```

### 8.3 Saved Views

Analyst can save dashboard configurations:

```text
src/features/dashboard/state/
  useSavedViews.ts               -- CRUD for saved dashboard configurations
```

Each saved view includes: widget layout, active filters, sort order, selected time range, selected jurisdictions, density preference.

### 8.4 Smart Defaults (Learning from Behavior)

The system learns from user behavior patterns:

- **Recent jurisdictions** -> pre-fill in launch form
- **Frequently used methods** -> higher in selection list
- **Common time ranges** -> quick-select buttons
- **Typical governance profile** -> auto-select
- **Most-used workspaces** -> pin in sidebar
- **Preferred chart types** -> default in visualizations

Implementation: track usage counts in localStorage; no server-side tracking needed.

### 8.5 Contextual Recommendations

```text
src/shared/ui/compounds/
  ContextualTip.tsx              -- non-intrusive tips based on context
  SuggestedAction.tsx            -- "You might want to..." recommendations
  RelatedRuns.tsx                -- "Similar analyses" panel
  SuggestedQuestions.tsx         -- context-aware suggested queries (AI-generated)
```

**Suggested questions** based on current view context:

- Run detail: "What are the main confounders for this estimate?"
- Evidence view: "How does the data quality compare to the last analysis?"
- Governance failure: "What would it take to pass the equity check?"

---

## 9. Design System Evolution

### 9.1 Component Foundation: shadcn/ui Adoption

**Why shadcn/ui**: 65K+ GitHub stars (2026), adopted by Vercel/Supabase, Tailwind-native, supports both Radix UI and Base UI backends, ships dashboard blocks out-of-the-box, unstyled + fully customizable, tree-shakeable.

**Migration strategy**:

1. Install shadcn/ui CLI: `npx shadcn@latest init`
2. Configure to use existing Tailwind 4 + CSS custom properties
3. Generate base components: Button, Card, Badge, Input, Select, Dialog, etc.
4. Migrate existing components incrementally (old component -> shadcn wrapper -> remove old)
5. Use shadcn dashboard blocks as starting points for new views

**Key shadcn components to adopt immediately**:

- `Command` (cmdk-based command palette)
- `Dialog`, `Sheet` (drawer), `Popover`, `Tooltip`
- `Tabs`, `Accordion`, `Collapsible`
- `Slider`, `Switch`, `RadioGroup`, `Checkbox`
- `DataTable` (TanStack Table + shadcn styling)
- `Calendar`, `DatePicker`
- `ResizablePanelGroup` (for split-pane layouts)
- `Skeleton` variants

### 9.2 Component Library Gaps

Beyond shadcn/ui primitives, PolicyOS-specific components:

```text
src/shared/ui/
  # Data input (shadcn-based)
  DateRangePicker.tsx            -- temporal range selection (shadcn Calendar + custom)
  MultiSelect.tsx                -- multi-select with search and chips
  Autocomplete.tsx               -- search with autocomplete

  # Navigation
  CommandPalette.tsx             -- Cmd+K command palette (shadcn Command)
  Breadcrumbs.tsx                -- breadcrumb navigation
  Pagination.tsx                 -- cursor-based pagination UI

  # Layout
  Resizable.tsx                  -- resizable panels (shadcn ResizablePanelGroup)

  # Display
  Avatar.tsx                     -- user avatar (collaboration)
  Timeline.tsx                   -- vertical timeline
  Stepper.tsx                    -- multi-step workflow indicator
  CopyButton.tsx                 -- click-to-copy
  CodeBlock.tsx                  -- syntax highlighted code
  Diff.tsx                       -- visual diff viewer (for AI proposal review)
  Tag.tsx                        -- removable tag/chip
```

### 9.3 Design Tokens Extension

Current tokens are good. Add:

```typescript
// Elevation system (depth)
elevation: {
  base: { cssVar: "--elevation-base", description: "Flat surface" },
  raised: { cssVar: "--elevation-raised", description: "Cards, panels" },
  overlay: { cssVar: "--elevation-overlay", description: "Dropdowns, popovers" },
  modal: { cssVar: "--elevation-modal", description: "Modals, command palette" },
},

// Z-index scale
zIndex: {
  dropdown: 100,
  sticky: 200,
  overlay: 300,
  modal: 400,
  popover: 500,
  toast: 600,
  tooltip: 700,
},

// Breakpoints
breakpoint: {
  sm: "640px",
  md: "768px",
  lg: "1024px",
  xl: "1280px",
  xxl: "1536px",
},

// Typography scale
type: {
  xs: { size: "12px", lineHeight: "16px" },
  sm: { size: "14px", lineHeight: "20px" },
  base: { size: "16px", lineHeight: "24px" },
  lg: { size: "18px", lineHeight: "28px" },
  xl: { size: "20px", lineHeight: "28px" },
  "2xl": { size: "24px", lineHeight: "32px" },
  "3xl": { size: "30px", lineHeight: "36px" },
  "4xl": { size: "36px", lineHeight: "40px" },
  "5xl": { size: "48px", lineHeight: "1" },
},
```

### 9.4 Icon System

**Lucide** (MIT, monoline stroke 1.5px, tree-shakeable, React components):

```bash
corepack pnpm add lucide-react
```

Usage: `import { BarChart3, Shield, AlertTriangle, Check } from "lucide-react";`

Custom icons for domain-specific concepts (causal graph nodes, governance passes, method types).

### 9.5 Typography Refinement

| Context         | Font          | Weight | Size    | Tracking |
| --------------- | ------------- | ------ | ------- | -------- |
| Hero heading    | Manrope       | 800    | 48-56px | -0.04em  |
| Section heading | Manrope       | 700    | 28-32px | -0.03em  |
| Card heading    | Manrope       | 700    | 20-24px | -0.02em  |
| Body            | Manrope       | 400    | 15-16px | 0        |
| Clerk chat body | Manrope       | 400    | 17-18px | 0        |
| Data/metrics    | IBM Plex Mono | 600    | 14-25px | -0.02em  |
| Eyebrow/label   | IBM Plex Mono | 500    | 12px    | 0.14em   |
| Code/JSON       | IBM Plex Mono | 400    | 13px    | 0        |

---

## 10. Micro-Interactions & Motion Design

### 10.1 Principle

Gartner 2025: 75% customer-facing apps will incorporate micro-interactions as standard. Adobe: 12% increase in engagement.

**PolicyOS rule**: every animation solves a task -- shows state change, guides attention, confirms action. No decorative animations.

### 10.2 Motion Vocabulary

| Action                  | Animation                           | Duration | Easing      |
| ----------------------- | ----------------------------------- | -------- | ----------- |
| Panel open              | Slide + fade                        | 200ms    | ease-out    |
| Panel close             | Slide + fade                        | 160ms    | ease-in     |
| Data load               | Skeleton shimmer -> content fade-in | 300ms    | ease-out    |
| Status change           | Color morph + subtle scale pulse    | 250ms    | spring      |
| Filter apply            | Content crossfade                   | 180ms    | ease-in-out |
| Run status update (SSE) | Soft pulse + value slide            | 200ms    | ease-out    |
| Governance pass result  | Sequential reveal (stagger 50ms)    | 50ms x N | ease-out    |
| Chart data update       | Smooth interpolation                | 400ms    | ease-in-out |
| Tab switch              | Slide + crossfade                   | 200ms    | ease-out    |
| Toast appear            | Slide up + fade                     | 250ms    | spring      |
| Toast dismiss           | Slide right + fade                  | 160ms    | ease-in     |
| Confidence gauge fill   | Animated arc fill                   | 600ms    | spring      |
| Number counter          | Counting animation to target        | 500ms    | ease-out    |

### 10.3 Implementation

**framer-motion** (declarative, spring physics, layout animations, AnimatePresence for exit animations):

```bash
corepack pnpm add framer-motion
```

Shared motion presets:

```text
src/shared/motion/
  presets.ts                     -- motion presets (fadeIn, slideUp, scaleIn, stagger)
  AnimatedContainer.tsx          -- wrapper for animated enter/exit
  AnimatedList.tsx               -- animated list with staggered children
  AnimatedNumber.tsx             -- number counter animation
  AnimatedProgress.tsx           -- smooth progress bar
  useReducedMotion.ts            -- respects prefers-reduced-motion
```

### 10.4 Skeleton Loading

Each data-dependent section uses content-shaped skeleton:

```text
src/shared/ui/
  Skeleton.tsx                   -- existing, extend:
    SkeletonText.tsx             -- text placeholder lines
    SkeletonChart.tsx            -- chart placeholder
    SkeletonCard.tsx             -- card-shaped placeholder
    SkeletonTable.tsx            -- table rows placeholder
    SkeletonDAG.tsx              -- graph placeholder
```

Shimmer animation via CSS gradient sweep (not JavaScript) for minimal overhead.

---

## 11. Accessibility (WCAG 2.2 AAA)

### 11.1 Current Level

Good baseline: a11y tests, skip-to-content, focus-visible, LiveAnnouncerProvider, prefers-reduced-motion. But for a SOTA government application -- need AAA compliance in key flows.

### 11.2 Gaps and Improvements

| Area                 | Current                | Target                                                       |
| -------------------- | ---------------------- | ------------------------------------------------------------ |
| Focus management     | focus-visible outline  | Roving tabindex in tabs, command palette trap focus          |
| Screen reader        | LiveAnnouncerProvider  | ARIA live regions for SSE updates, chart descriptions        |
| Color contrast       | AA (4.5:1 text)        | AAA (7:1 text, 4.5:1 large)                                  |
| Charts               | chartTheme.ts colors   | Pattern fills + textures for colorblind; alt-text summaries  |
| Keyboard             | Tab navigation         | Full keyboard operation: shortcuts, arrow keys in grids      |
| Forms                | Basic labels           | Associated descriptions, error messages, required indicators |
| Motion               | prefers-reduced-motion | Graceful degradation: reduced motion -> instant transitions  |
| Touch targets        | Variable               | Min 44x44px touch targets (WCAG 2.2 Target Size)             |
| Error identification | ApiErrorAlert          | Clear, specific error messages with suggestions              |
| Causal graph         | Mouse-only             | Keyboard navigable nodes, screen reader graph summary        |

### 11.3 Chart Accessibility (SOTA)

Every chart must have (per AG Charts, W3C SVG Accessibility):

1. `role="img"` on SVG container + descriptive `<title>` element
2. `aria-label` with auto-generated statistical summary
3. Hidden data table alternative (`<details>` toggle): "View as table"
4. Pattern fills (hatching, dots, diagonal lines) alongside color to distinguish series
5. High contrast mode: monochrome with patterns only
6. Keyboard navigation through data points (arrow keys)
7. ARIA live regions that announce chart updates from SSE

```typescript
// chartAccessibility.ts
export function generateChartAriaLabel(config: {
  type: string;
  title: string;
  dataPoints: number;
  trend?: "up" | "down" | "stable";
  range?: { min: number; max: number };
}): string;

export function generatePatternDefs(seriesCount: number): SVGPatternElement[];
```

### 11.4 Accessibility Automation

```text
src/lib/
  a11yAudit.ts                   -- runtime axe-core integration (dev only)

# CI/CD
vitest.setup.ts                  -- add vitest-axe matchers
playwright/                      -- add a11y checks to E2E tests
```

Enforce in CI: `eslint-plugin-jsx-a11y` set to **strict** mode (not just "recommended").

---

## 12. Performance & Architecture

### 12.1 Bundle Optimization

| Strategy                   | Implementation                                                        |
| -------------------------- | --------------------------------------------------------------------- |
| Route-based code splitting | All route components -- `React.lazy()` (already done)                 |
| Feature-based splitting    | Heavy features (causal graph, charting) -- dynamic imports            |
| Library chunking           | Vite `manualChunks`: react, react-query, framer-motion, visx, zustand |
| Tree-shaking               | Lucide icons tree-shake by default; shadcn same                       |
| Preloading                 | `<link rel="modulepreload">` for likely-next routes                   |
| Hover prefetching          | Prefetch run details when hovering run row in table                   |
| Service worker caching     | API responses + static assets (already have SW)                       |

**Per-route chunk budgets** (enforce via `analyze:bundle` script):

| Chunk                            | Budget (gzipped) |
| -------------------------------- | ---------------- |
| Initial (shell + routing)        | < 100KB          |
| Vendor: react + react-dom        | < 50KB           |
| Vendor: tanstack-query           | < 25KB           |
| Each lazy route                  | < 50KB           |
| Causal graph (heavy)             | < 80KB           |
| Total loaded for typical session | < 400KB          |

### 12.2 Rendering Performance

| Strategy              | Where to apply                                                                   |
| --------------------- | -------------------------------------------------------------------------------- |
| Virtualization        | VirtualTable, VirtualList (already have), add for DAG nodes                      |
| Memoization           | `React.memo` for chart components, `useMemo` for expensive transforms            |
| Debouncing            | Search inputs, filter changes, resize observers                                  |
| Web Workers           | JSON parsing for large artifacts, DAG layout calculations, heavy data transforms |
| Canvas rendering      | Causal graph on canvas (not SVG) for 100+ nodes                                  |
| Progressive hydration | Landing page: static HTML -> hydrate interactive parts                           |

**Web Workers detail**:

```text
src/workers/
  dagLayout.worker.ts            -- offload d3-dag layout computation
  jsonParse.worker.ts            -- parse large artifact JSON off main thread
  dataTransform.worker.ts        -- heavy data aggregation/filtering
```

### 12.3 Data Layer Optimization

| Strategy                | Implementation                                            |
| ----------------------- | --------------------------------------------------------- |
| Stale-while-revalidate  | React Query defaults (already done)                       |
| Background refetch      | Configurable per-query refetch intervals                  |
| Optimistic updates      | For mutations (launch, approve/reject) -- already partial |
| Parallel queries        | `useQueries` for independent data                         |
| Hover prefetching       | Prefetch on hover (run details when hovering run row)     |
| SSE-driven invalidation | SSE events -> queryClient.invalidateQueries()             |

**Hover prefetching pattern**:

```typescript
function RunRow({ run }: { run: Run }) {
  const queryClient = useQueryClient();
  const prefetch = () => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.runs.detail(run.id),
      queryFn: () => fetchRunDetail(run.id),
      staleTime: 30_000,
    });
  };
  return <tr onMouseEnter={prefetch}>...</tr>;
}
```

### 12.4 Performance Budgets

| Metric                           | Target                                 |
| -------------------------------- | -------------------------------------- |
| FCP (First Contentful Paint)     | < 1.2s                                 |
| LCP (Largest Contentful Paint)   | < 2.0s                                 |
| TTI (Time to Interactive)        | < 3.0s                                 |
| CLS (Cumulative Layout Shift)    | < 0.05                                 |
| INP (Interaction to Next Paint)  | < 200ms                                |
| Bundle size (gzipped)            | < 250KB initial, < 500KB total session |
| SSE latency (render after event) | < 100ms                                |

### 12.5 Architecture Note: Stay with Vite SPA

Moving to RSC/Next.js would be a large migration with limited benefit for this use case (authenticated dashboard, not SEO-critical). The React Server Components ecosystem with Vite is still maturing. Revisit when Vite gets native RSC support. Current Vite SPA with code splitting + service worker caching achieves comparable perceived performance.

**Monitor**: TanStack DB (beta 2025) as potential replacement for Zustand stores with built-in optimistic mutations and offline sync.

---

## 13. Real-Time Collaboration

### 13.1 Backend Readiness

`ReviewCollaborationHub` on backend already supports:

- Multi-user review sessions
- Cursor tracking
- Locks on sections
- Real-time comments

### 13.2 Frontend Implementation

```text
src/features/collaboration/
  components/
    CollaborationToolbar.tsx      -- toolbar: participants, share, comments
    PresenceBubbles.tsx           -- avatar bubbles showing who is viewing (Velt-inspired)
    CollaborativeCursors.tsx      -- multiplayer cursors (Figma-style)
    CommentThread.tsx             -- threaded comments on artifacts
    ReviewChecklistPanel.tsx      -- shared review checklist
    ShareDialog.tsx               -- share analysis with other users
    ActivityFeed.tsx              -- real-time team activity feed

  hooks/
    useCollaborationSession.ts   -- WebSocket connection for real-time sync
    usePresence.ts               -- presence awareness (Yjs Awareness protocol)
    useCursors.ts                -- cursor position broadcasting
```

### 13.3 CRDT Strategy for Collaborative Editing

If collaborative scenario editing becomes a requirement, adopt **Yjs** (dominant CRDT library, 2026):

- `Y.Map` for shared scenario parameters
- `Y.Array` for shared evidence lists
- `Y.Text` for collaborative annotations
- **Awareness protocol** for presence (cursors, avatars, online status) without custom code
- Transport: `y-websocket` provider connecting to backend

### 13.4 Activity Feed

Reverse-chronological event log for team awareness:

```text
src/features/collaboration/components/
  ActivityFeed.tsx               -- scrollable event list
  ActivityItem.tsx               -- single event (run launched, review submitted, etc.)
```

Backed by existing API, polled via TanStack Query with 10s stale time. Events: run started, run completed, governance passed/failed, review submitted, evidence promoted, scenario modified.

### 13.5 Annotation & Commenting

Analyst can:

- Annotate specific points on charts
- Comment on governance pass results
- Tag colleagues for review
- Create review checklist

Each annotation linked to `artifact_id` for auditability.

---

## 14. Chat & Conversational UX (Clerk Mode)

### 14.1 Current State

Basic ChatContainer + ChatInput + ChatMessage + ChatStreamIndicator. Works but far from SOTA.

### 14.2 SOTA Improvements

#### Structured Responses

```text
src/features/clerk/components/
  ClerkStructuredResponse.tsx    -- rich response cards instead of plain text
  ClerkResultCard.tsx            -- improve: add confidence gauge, key factors
  ClerkSuggestionChips.tsx       -- "Try asking about..." suggestions
  ClerkFollowUpBar.tsx           -- contextual follow-up questions
  ClerkDomainSelector.tsx        -- visual domain picker (icons + descriptions)
```

#### Conversation Intelligence

```text
src/features/clerk/hooks/
  useConversationContext.ts      -- track conversation context for follow-ups
  useSuggestedQuestions.ts       -- AI-generated follow-up suggestions based on current view
  useClerkHistory.ts             -- conversation history with search
```

#### Streaming UX

- **Token-by-token streaming** for NL explanations (SSE from backend)
- **Progressive card building** -- result card builds up as data arrives
- **Status chips** inline in conversation: "Collecting data...", "Building causal graph...", "Checking governance..."

#### Conversational Patterns (from research 2025-2026)

- **Clarification requests** -- if question is ambiguous, chat asks for clarification
- **Confidence disclaimers** -- inline in response: "Confidence: high / medium / low"
- **Source citations** -- clickable links to data sources in response text
- **Comparison mode** -- "Compare with previous analysis" in chat
- **Export from chat** -- export conversation + results as report

#### AI Diff View for Policy Drafts (Hex Pattern)

When AI generates a policy draft or scenario modification, show it in a diff view:

```text
src/features/clerk/components/
  AIDiffView.tsx                 -- side-by-side diff of current vs AI-proposed
  DiffAcceptReject.tsx           -- accept/reject/edit controls per section
```

This is the pattern Hex uses for notebook agents: show what the AI proposes, let the user accept/reject/edit each change. Critical for trust in AI-assisted policy analysis.

#### Governed NL Context

Ground the NL interface in the PolicyOS domain ontology:

- When AI generates a query, it references formal PolicyOS types (not raw column names)
- Responses cite `TrinityBundle` components, `GovernancePass` names, `UncertaintyEnvelope` fields
- This creates a controlled vocabulary that ensures consistency and verifiability
- Map user natural language to formal concepts via the `ir/` type system

---

## 15. Keyboard-First & Power User Features

### 15.1 Command Palette (Cmd+K)

Inspired by Linear, Vercel, GitHub. Use shadcn `Command` component (based on `cmdk`, ~4KB):

```text
src/shared/ui/
  CommandPalette.tsx             -- Cmd+K global command palette
```

**Commands**:

- Navigate to workspace: `Go to Runs`, `Go to Evidence`
- Launch run: `Launch new run`
- Search: `Search runs`, `Search evidence`, `Search lex`
- Actions: `Switch to dark mode`, `Switch to clerk mode`, `Change density`
- Recent: last 5 navigated items
- Fuzzy search across all commands
- Recent runs: quick access to last 10 runs
- Reproduce run: `Reproduce run <id>`

### 15.2 Global Keyboard Shortcuts

| Shortcut    | Action                                        |
| ----------- | --------------------------------------------- |
| `Cmd+K`     | Command palette                               |
| `Cmd+/`     | Help / keyboard shortcuts                     |
| `Cmd+1-6`   | Navigate to workspace 1-6                     |
| `Cmd+N`     | New run                                       |
| `Cmd+F`     | Focus search                                  |
| `Cmd+M`     | Toggle mode (clerk <-> analyst)               |
| `Cmd+D`     | Toggle dark mode                              |
| `Cmd+B`     | Toggle sidebar                                |
| `Cmd+\`     | Toggle density (compact/comfortable/spacious) |
| `Escape`    | Close modal / drawer / palette                |
| `?`         | Show keyboard shortcuts overlay               |
| `j/k`       | Navigate list items (Vim-style)               |
| `Enter`     | Open selected item                            |
| `Cmd+Enter` | Launch action on selected item                |

### 15.3 Focus Management

```text
src/shared/hooks/
  useKeyboardShortcuts.ts        -- global shortcut registry
  useFocusTrap.ts                -- trap focus in modals/drawers
  useRovingTabIndex.ts           -- roving tabindex for tab lists, grids
```

---

## 16. Run Comparison & Reproducibility

### 16.1 Run Comparison View (W&B / Neptune Pattern)

Let users select 2-N runs and see a side-by-side diff of parameters and outcomes:

```text
src/features/runs/components/comparison/
  RunComparisonView.tsx          -- main comparison layout
  RunSelector.tsx                -- multi-select runs to compare
  ParameterDiff.tsx              -- side-by-side parameter comparison with diff highlighting
  OutcomeDiff.tsx                -- side-by-side outcome comparison
  ParallelCoordinatesChart.tsx   -- multi-dimensional parameter comparison (W&B pattern)
  EffectComparisonForest.tsx     -- forest plot comparing effects across runs
  MethodologyComparison.tsx      -- compare methodologies used
  GovernanceComparison.tsx       -- compare governance outcomes
  CausalGraphDiff.tsx            -- overlay two causal graphs, highlight differences
```

**Key patterns**:

- **Parallel coordinates**: each axis is a parameter or metric, each run is a colored line. Brushing on any axis filters to relevant runs.
- **Forest plot**: effect estimates from multiple runs with CIs, sorted by magnitude.
- **Diff highlighting**: parameters that differ between runs highlighted in amber; shared parameters in muted.

### 16.2 Reproducibility

**"Reproduce This Run" button** on every run detail page:

```text
src/features/runs/components/
  ReproduceRunButton.tsx         -- pre-fills launch form with exact parameters of a previous run
```

- Copies all parameters from the selected run into the Scenario Composer
- Shows what has changed since the original run (data freshness, connector status)
- Warns if original data sources have been updated
- Links to artifact provenance chain for full traceability

### 16.3 Run Lineage

Show which runs were derived from which scenarios, creating a DAG of analyses:

```text
src/features/runs/components/
  RunLineageGraph.tsx            -- DAG showing run derivation history
```

This maps to DVC's version control concept applied to policy analysis.

---

## 17. What-If Analysis & Interactive Parameters

### 17.1 Motivation

From 2025-2026 research: "What-if analysis with parameter sliders that show instant impact on key metrics" is a major trend in analytical dashboards.

PolicyOS `PolicySpec` contains `parameters: list[ParameterSpec]` with `min`, `max`, and `sensitivity_priority`. This maps directly to interactive sliders.

### 17.2 What-If Panel

```text
src/features/composer/components/
  WhatIfPanel.tsx                -- interactive parameter exploration panel
  ParameterSlider.tsx            -- range slider for a single parameter
  ImpactPreview.tsx              -- instant visual feedback showing predicted impact
  ScenarioSnapshot.tsx           -- save current parameter combination as a scenario
```

**UX flow**:

1. User opens a completed run's What-If panel
2. Parameter sliders show current values from the run
3. Moving a slider instantly shows predicted impact on key outcome metrics
4. Multiple parameters can be adjusted simultaneously
5. "Save as Scenario" creates a new scenario for full analysis
6. "Compare" opens the Run Comparison view with original and what-if

### 17.3 Sensitivity Exploration

Connect What-If to sensitivity analysis results:

- Parameters with high sensitivity priority get visual emphasis
- Sliders show "sensitivity zone" where small changes cause large outcome changes
- Color gradient on slider track: green (stable) -> red (sensitive)

---

## 18. Internationalization

### 18.1 Current Level

2 locales (en/uk), `useI18n().t()` pattern. Good baseline.

### 18.2 SOTA Improvements

| Improvement                | Details                                                                 |
| -------------------------- | ----------------------------------------------------------------------- |
| **Plural rules**           | `t("runs.count", { count })` with ICU MessageFormat                     |
| **Date/number formatting** | `Intl.DateTimeFormat`, `Intl.NumberFormat` per locale                   |
| **RTL preparation**        | CSS logical properties (`margin-inline-start` instead of `margin-left`) |
| **Dynamic locale loading** | Lazy load locale bundles (don't load uk if en active)                   |
| **Content negotiation**    | `Accept-Language` header -> backend response locale                     |
| **Translation coverage**   | 100% coverage check in CI                                               |
| **Contextual help**        | i18n for tooltips, error messages, onboarding                           |

### 18.3 CSS Logical Properties Migration

Since Tailwind 4 supports logical properties natively, migrate:

- `ml-4` -> `ms-4` (margin-inline-start)
- `mr-4` -> `me-4` (margin-inline-end)
- `pl-4` -> `ps-4` (padding-inline-start)
- `text-left` -> `text-start`

This makes RTL support nearly free if Arabic or Hebrew locale is added later. Ukrainian is LTR so no immediate need, but the foundation should be in place.

### 18.4 Number Formatting

```typescript
src/i18n/
  formatters.ts                  -- locale-aware formatters
    formatNumber(value, locale, options)
    formatPercent(value, locale, decimals)
    formatDuration(ms, locale)
    formatDate(date, locale, style)
    formatCurrency(amount, currency, locale)
    formatRelativeTime(date, locale)
    formatStatistic(value, ci, locale) -- "2.3% [1.5%, 3.2%]" locale-aware
```

---

## 19. Responsive & Mobile

### 19.1 Current Breakpoints

3 breakpoints: 1480px, 1100px, 760px. Sidebar collapses at 1100px.

### 19.2 SOTA Mobile Strategy

For government applications mobile is not optional (USWDS: "mobile-first"):

| Breakpoint  | Layout             | Adaptation                                                                 |
| ----------- | ------------------ | -------------------------------------------------------------------------- |
| < 640px     | Single column      | Bottom nav, collapsible cards, simplified charts, single-series with swipe |
| 640-768px   | Single column wide | Side panel as drawer, table -> card list                                   |
| 768-1024px  | Compact grid       | Narrower sidebar, 2-column grid                                            |
| 1024-1280px | Standard           | Full sidebar, 3-column grid                                                |
| > 1280px    | Expanded           | Full layout with extra panel space, 3-pane split views                     |

**Mobile focus on "check status" use case**: run list with status badges, individual run summary with top 3 metrics.

### 19.3 Mobile-Specific Components

```text
src/shared/ui/
  BottomSheet.tsx                -- mobile bottom sheet (instead of dropdown)
  SwipeableDrawer.tsx            -- swipeable navigation drawer
  PullToRefresh.tsx              -- pull to refresh for lists
  MobileNav.tsx                  -- bottom tab navigation bar (4-5 icons)
```

### 19.4 Touch Optimization

- Minimum 44x44px touch targets (WCAG 2.2)
- Swipe gestures for navigation between tabs
- Long-press for context menus
- No hover-dependent functionality
- Charts: swipe to scroll through time, pinch to zoom (via `@use-gesture/react`)
- For mobile charts: reduce to single-series views with swipe between series

### 19.5 Responsive Sidebar

Collapse sidebar to bottom navigation on mobile:

- < 768px: sidebar hidden, bottom tab bar with 5 workspace icons
- 768-1100px: narrow sidebar (icons only, expand on hover)
- > 1100px: full sidebar with labels

---

## 20. Legal Compliance

### 20.1 EU European Accessibility Act (EAA)

In force since June 2025. Makes WCAG 2.2 AA a legal requirement for digital products serving EU users. PolicyOS, as a government-facing tool, must comply.

**Action items**:

- Ensure all flows meet WCAG 2.2 AA (current: partial)
- Key flows (run review, governance approval, evidence promotion) must meet AAA
- Document compliance evidence for audit
- Add EAA compliance badge to footer

### 20.2 US ADA Title II

DOJ ADA Title II Web Accessibility Rule requires WCAG 2.1 AA by April 2026.

**Action items**:

- Same as EAA (WCAG 2.2 is backwards-compatible with 2.1)
- Ensure screen reader compatibility for all decision workflows
- Provide text alternatives for all visual content

### 20.3 NIST 800-53 Controls (Frontend Aspects)

PolicyOS backend already maps 17 NIST SP 800-53 Rev. 5 controls. Frontend contributes to:

- **AC-2 (Account Management)**: Auth UI, session management display
- **AU-2 (Auditable Events)**: Telemetry, user action logging
- **IA-2 (Identification & Authentication)**: Login flow, MFA UI
- **SC-8 (Transmission Confidentiality)**: HTTPS enforcement, no mixed content

---

## 21. Observability & Analytics

### 21.1 Current Level

TelemetryProvider with `track()` for route views and transitions.

### 21.2 SOTA Telemetry

```text
src/app/providers/
  TelemetryProvider.tsx          -- extend:
```

| Event Category       | Events                                                                                 |
| -------------------- | -------------------------------------------------------------------------------------- |
| **Navigation**       | route.view, route.transition (already have)                                            |
| **Interaction**      | feature.used, filter.applied, chart.interacted, export.triggered, command_palette.used |
| **Performance**      | page.load, ttfb, fcp, lcp, cls, inp, api.latency                                       |
| **Errors**           | error.boundary, api.error, runtime.error                                               |
| **Engagement**       | session.duration, workspace.time, mode.switch, density.change                          |
| **Accessibility**    | a11y.shortcut_used, a11y.screen_reader_detected, a11y.high_contrast_enabled            |
| **Feature adoption** | feature_flag.impression, onboarding.step_completed, saved_view.created                 |
| **Collaboration**    | review.started, comment.added, share.triggered                                         |

### 21.3 Error Boundary Enhancement

```text
src/app/routes/
  RouteErrorElement.tsx          -- extend:

    - Structured error display (code, message, suggestion)
    - "Report this issue" button
    - Recovery actions (retry, go home)
    - Telemetry auto-report
    - Context preservation (what was the user trying to do)
```

---

## 22. Implementation Phases

### Phase 1: Foundation (2-3 weeks)

**Goal**: strengthen design system and infrastructure

| Task                                                          | Priority | Effort |
| ------------------------------------------------------------- | -------- | ------ |
| shadcn/ui init + base component migration                     | CRITICAL | 3d     |
| Icon system (Lucide)                                          | HIGH     | 1d     |
| Extended design tokens (elevation, z-index, typography scale) | HIGH     | 1d     |
| Motion library setup (framer-motion + presets)                | HIGH     | 2d     |
| Command Palette (Cmd+K) via shadcn Command                    | HIGH     | 2d     |
| Keyboard shortcuts system                                     | HIGH     | 1d     |
| User preferences store (Zustand + localStorage)               | HIGH     | 1d     |
| Density toggle (compact/comfortable/spacious)                 | MEDIUM   | 1d     |
| Skeleton loading variants (Text, Chart, Card, Table)          | MEDIUM   | 1d     |
| i18n formatters (date, number, duration)                      | MEDIUM   | 1d     |
| CSS logical properties migration                              | MEDIUM   | 1d     |

### Phase 2: Charting & Visualization (2-3 weeks)

**Goal**: charting library and core visualization components

| Task                                                        | Priority | Effort |
| ----------------------------------------------------------- | -------- | ------ |
| visx integration + chart theme                              | CRITICAL | 2d     |
| AreaChart, BarChart, WaterfallChart                         | CRITICAL | 3d     |
| RadarChart, SpecificationCurveChart                         | HIGH     | 2d     |
| ForestPlot, ParallelCoordinates                             | HIGH     | 2d     |
| Chart accessibility (patterns, alt-text, data tables, ARIA) | HIGH     | 2d     |
| ConfidenceGauge, GradedErrorBar (50/80/95%)                 | HIGH     | 1d     |
| UncertaintyDisplay (dual-mode with frequency framing)       | HIGH     | 2d     |
| FrequencyDots (icon array)                                  | MEDIUM   | 1d     |
| ConfidenceDial                                              | MEDIUM   | 0.5d   |
| AnimatedNumber, AnimatedProgress                            | MEDIUM   | 1d     |

### Phase 3: Explainability Layer (2-3 weeks)

**Goal**: XAI components and explainability framework

| Task                                            | Priority | Effort |
| ----------------------------------------------- | -------- | ------ |
| ExplainabilityCard (3-level)                    | CRITICAL | 3d     |
| GovernancePassGrid                              | CRITICAL | 2d     |
| NegativeCertificateCard                         | HIGH     | 1d     |
| ProvenanceChain                                 | HIGH     | 2d     |
| AttributionWaterfall (SHAP-like)                | HIGH     | 2d     |
| Trust calibration display (historical accuracy) | HIGH     | 1d     |
| MethodologyBadge                                | MEDIUM   | 0.5d   |
| EvidenceCoverageRadar (4D)                      | MEDIUM   | 2d     |
| SensitivityPlot                                 | MEDIUM   | 1d     |
| FactorImportanceChart                           | MEDIUM   | 1d     |
| AI reasoning chain display                      | MEDIUM   | 1d     |

### Phase 4: Causal Graph (2-3 weeks)

**Goal**: interactive causal graph

| Task                                                            | Priority | Effort |
| --------------------------------------------------------------- | -------- | ------ |
| CausalGraphCanvas (zoom, pan, select) via visx                  | CRITICAL | 3d     |
| CausalNode + CausalEdge visual language                         | CRITICAL | 2d     |
| Layout algorithms (hierarchical, force, dagitty via d3-dag)     | HIGH     | 2d     |
| IdentificationOverlay, TransportOverlay, AdjustmentSetHighlight | HIGH     | 2d     |
| NodeDetailPanel, EdgeDetailPanel                                | HIGH     | 2d     |
| PathAnalysisPanel                                               | MEDIUM   | 1d     |
| Canvas rendering for 100+ nodes                                 | MEDIUM   | 2d     |
| Keyboard navigation for DAG                                     | MEDIUM   | 1d     |
| Pipeline progress visualization                                 | MEDIUM   | 2d     |

### Phase 5: Narrative, Dashboard & Comparison (3 weeks)

**Goal**: data storytelling, analyst dashboard redesign, run comparison

| Task                                    | Priority | Effort |
| --------------------------------------- | -------- | ------ |
| RunNarrativeView with chapters          | HIGH     | 3d     |
| AnnotatedChart                          | HIGH     | 2d     |
| Dashboard widget system (@dnd-kit)      | HIGH     | 3d     |
| Run comparison view (side-by-side)      | HIGH     | 3d     |
| ParallelCoordinatesChart for comparison | HIGH     | 1d     |
| ReproduceRunButton                      | MEDIUM   | 1d     |
| SavedViews system                       | MEDIUM   | 2d     |
| QuickInsightsPanel                      | MEDIUM   | 1d     |
| Run lineage graph                       | MEDIUM   | 1d     |

### Phase 6: What-If & Interactive Parameters (1-2 weeks)

**Goal**: interactive parameter exploration

| Task                                    | Priority | Effort |
| --------------------------------------- | -------- | ------ |
| WhatIfPanel with parameter sliders      | HIGH     | 2d     |
| ImpactPreview (instant visual feedback) | HIGH     | 2d     |
| ScenarioSnapshot (save & compare)       | MEDIUM   | 1d     |
| Sensitivity zone indicators on sliders  | MEDIUM   | 1d     |
| Connection to run comparison view       | MEDIUM   | 1d     |

### Phase 7: Clerk Enhancement (1-2 weeks)

**Goal**: SOTA conversational UX

| Task                                                      | Priority | Effort |
| --------------------------------------------------------- | -------- | ------ |
| ClerkStructuredResponse                                   | HIGH     | 2d     |
| ClerkSuggestionChips + FollowUpBar                        | HIGH     | 1d     |
| Streaming improvements (token-by-token, progressive card) | HIGH     | 2d     |
| AI Diff View for policy drafts                            | HIGH     | 2d     |
| Governed NL context (domain ontology grounding)           | HIGH     | 2d     |
| Conversation history search                               | MEDIUM   | 1d     |
| Export conversation as report                             | MEDIUM   | 1d     |

### Phase 8: Collaboration (1-2 weeks)

**Goal**: real-time collaboration features

| Task                                   | Priority | Effort |
| -------------------------------------- | -------- | ------ |
| CollaborationToolbar + PresenceBubbles | HIGH     | 2d     |
| CommentThread (artifact-linked)        | HIGH     | 2d     |
| ActivityFeed (team event log)          | HIGH     | 1d     |
| ShareDialog                            | MEDIUM   | 1d     |
| CollaborativeCursors (stretch goal)    | LOW      | 3d     |

### Phase 9: Polish, Mobile & Compliance (2-3 weeks)

**Goal**: responsive design, accessibility, performance, legal compliance

| Task                                                    | Priority | Effort |
| ------------------------------------------------------- | -------- | ------ |
| Responsive breakpoints + mobile layouts                 | HIGH     | 3d     |
| Bottom navigation bar for mobile                        | HIGH     | 1d     |
| WCAG 2.2 AA full audit + fixes                          | HIGH     | 2d     |
| Chart accessibility audit (patterns, ARIA, data tables) | HIGH     | 2d     |
| Performance budgets + bundle optimization               | HIGH     | 2d     |
| Web Workers for heavy computation                       | MEDIUM   | 2d     |
| Extended telemetry events                               | MEDIUM   | 1d     |
| Hover prefetching for run details                       | MEDIUM   | 0.5d   |
| Guided onboarding tour                                  | MEDIUM   | 2d     |
| EAA/ADA compliance documentation                        | MEDIUM   | 1d     |
| Print/PDF export                                        | LOW      | 2d     |
| Touch gesture support (use-gesture)                     | LOW      | 1d     |

---

## 23. Success Metrics

### Quantitative

| Metric                      | Baseline        | Target                |
| --------------------------- | --------------- | --------------------- |
| Lighthouse Performance      | --              | >= 90                 |
| Lighthouse Accessibility    | --              | >= 95                 |
| Lighthouse Best Practices   | --              | >= 95                 |
| FCP                         | --              | < 1.2s                |
| LCP                         | --              | < 2.0s                |
| INP                         | --              | < 200ms               |
| CLS                         | --              | < 0.05                |
| Bundle size (gzip)          | --              | < 250KB initial       |
| Test coverage               | ~80%            | >= 90%                |
| a11y test coverage          | ~40% components | 100% components       |
| i18n coverage               | --              | 100% keys             |
| TypeScript strict           | Yes             | Yes                   |
| axe-core violations (CI)    | --              | 0 critical, 0 serious |
| Chart pattern fill coverage | 0%              | 100% of series        |

### Qualitative

| Criterion           | Verification                                                                            |
| ------------------- | --------------------------------------------------------------------------------------- |
| **Explainability**  | Every AI result has 3-level explanation drill-down                                      |
| **Trust**           | Uncertainty always visible; limitations explicitly listed; "Why NOT trust this" section |
| **Dual-persona**    | Clerk can work without training; Analyst has full control                               |
| **Narrative**       | Run results can be read as a story, not just a table                                    |
| **Causal viz**      | Causal graph interactive, navigable via keyboard + screen reader                        |
| **Governance**      | 20 governance passes visualized with drill-down                                         |
| **Comparison**      | 2+ runs can be compared side-by-side with parallel coordinates                          |
| **Reproducibility** | Any run can be reproduced with one click                                                |
| **What-if**         | Parameters adjustable with instant impact preview                                       |
| **AI interface**    | NL queries grounded in domain ontology; AI proposals shown in diff view                 |
| **Collaboration**   | Two analysts can review one run simultaneously                                          |
| **Responsive**      | All key flows work on 768px screen                                                      |
| **Performance**     | No jank during SSE updates, charts render smoothly                                      |
| **Accessibility**   | Full WCAG 2.2 AA, key flows -- AAA                                                      |
| **Legal**           | EAA + ADA Title II compliant                                                            |
| **Command palette** | Every action reachable via Cmd+K                                                        |

---

## Appendix A: References

### Government Design Systems

- **USWDS** (US Web Design System) -- 40+ accessible components, design principles
- **GOV.UK Design System** -- UK government service patterns
- **Australia Design System** -- Government UX patterns

### Analytics & AI Platforms

- **Palantir Foundry** -- data lineage, operational apps, DAG visualization, split-pane layouts
- **Palantir Blueprint** -- open-source design system for data-dense desktop applications
- **Bloomberg Terminal** -- information density, keyboard-first, dark theme
- **Tableau** -- progressive disclosure in analytics, LOD expressions
- **Linear** -- command palette, keyboard shortcuts, motion design, keyboard-only mode
- **Vercel** -- developer dashboard UX, real-time, command palette
- **W&B (Weights & Biases)** -- run comparison, parallel coordinates, experiment tracking
- **Hex** -- notebook agent, diff view for AI proposals, version history
- **Neptune AI** -- 100K+ run comparison, parameter summary, artifact lineage
- **Observable** -- reactive notebooks, Plot library, linked views
- **ThoughtSpot Spotter** -- governed NL analytics, business context grounding
- **Databricks Genie** -- conversational data exploration
- **MLflow** -- experiment tracking, reproducibility

### XAI & Visualization

- **DAGitty** -- interactive causal DAG editor (browser-based), adjustment set identification
- **d3-dag** (Erik Brinkman) -- layout algorithms for DAG visualization in JavaScript
- **SHAP library** -- waterfall plots, feature importance
- **Claus Wilke "Fundamentals of Data Visualization"** -- uncertainty viz, graded confidence bands
- **VisXAI Workshop** -- academic XAI visualization research
- **Confidence Visualization Patterns** -- agentic-design.ai framework

### Component Libraries & Tools

- **shadcn/ui** (65K+ stars) -- Tailwind-native, Radix + Base UI, dashboard blocks
- **visx** (Airbnb) -- low-level React chart primitives, D3-level control
- **Recharts** -- high-level React charts
- **Lucide** -- MIT icon library, tree-shakeable
- **framer-motion** -- declarative animation, spring physics
- **cmdk** -- command palette primitive (~4KB)
- **Yjs** -- CRDT library for collaborative editing
- **react-resizable-panels** -- resizable panel groups

### Accessibility

- **AG Charts** -- chart accessibility (keyboard nav, ARIA, contrast)
- **ARIAKit** -- unstyled accessible React primitives
- **eslint-plugin-jsx-a11y** -- accessibility linting

### Academic

- Carloni 2025 -- "Causality in Explainable AI" (WIREs Data Mining)
- NN/Group -- Progressive Disclosure (2025)
- Smashing Magazine -- "UX Strategies for Real-Time Dashboards" (2025)
- ScienceDirect -- "Systematic design of storytelling dashboards" (2025)
- Frontiers -- "Evaluating chatbot architectures for public service" (2025)
- DOJ ADA Title II Web Accessibility Rule -- WCAG 2.1 AA by April 2026
- EU European Accessibility Act (EAA) -- in force June 2025

### Legal

- EU EAA (European Accessibility Act) -- June 2025, WCAG 2.2 AA required
- US ADA Title II -- April 2026, WCAG 2.1 AA required
- NIST SP 800-53 Rev. 5 -- 17 controls mapped in PolicyOS

---

## Appendix B: Technology Stack (additions)

| Library                  | Purpose                                 | Size                               |
| ------------------------ | --------------------------------------- | ---------------------------------- |
| `shadcn/ui`              | Component foundation (Radix + Tailwind) | ~0KB (copies code, no runtime dep) |
| `lucide-react`           | Icon system                             | ~2KB per icon (tree-shake)         |
| `framer-motion`          | Animation library                       | ~32KB gzip                         |
| `@visx/visx`             | Low-level chart primitives              | ~15-40KB per package               |
| `recharts`               | High-level charts (keep)                | ~50KB gzip                         |
| `d3-dag`                 | DAG layout algorithms                   | ~8KB gzip                          |
| `@dnd-kit/core`          | Drag and drop (dashboard widgets)       | ~12KB gzip                         |
| `cmdk`                   | Command palette primitive               | ~4KB gzip                          |
| `react-hotkeys-hook`     | Keyboard shortcuts                      | ~3KB gzip                          |
| `react-resizable-panels` | Resizable split-pane layouts            | ~5KB gzip                          |
| `@use-gesture/react`     | Touch gestures (mobile charts)          | ~8KB gzip                          |

Total estimated addition: ~140-180KB gzip (loaded lazily across routes).

---

## Appendix C: Target File Structure

```text
src/
+-- api/                         # (existing) API hooks, types, query infrastructure
+-- app/
|   +-- auth/                    # (existing) AuthSessionProvider
|   +-- authz/                   # (existing) + permissions extended
|   +-- layout/                  # (existing) AppShell, Header, Sidebar + enhancements
|   +-- offline/                 # (existing) SW, offline queue
|   +-- providers/               # (existing) 14 providers
|   +-- realtime/                # (existing) SSE transport
|   +-- routes/                  # (existing) ModeAware* routes
|   +-- state/
|   |   +-- useUserPreferences.ts  # NEW: user preferences store
|   +-- workspaces.ts            # (existing) + layout enhancements
+-- features/
|   +-- artifacts/               # (existing)
|   +-- auth/                    # (existing)
|   +-- causal/                  # NEW: causal graph visualization
|   |   +-- components/
|   |   |   +-- methods/         # DiD, SC, RDD, BSTS, MetaLearner visualizations
|   |   +-- panels/
|   |   +-- layouts/
|   +-- clerk/                   # (existing) + structured responses, AI diff view
|   +-- collaboration/           # NEW: real-time collaboration
|   |   +-- components/          # Toolbar, presence, cursors, comments, activity feed
|   |   +-- hooks/
|   +-- composer/                # (existing) + what-if panel
|   +-- dashboard/               # (existing) + widget system
|   +-- evidence/                # (existing)
|   +-- landing/                 # (existing)
|   +-- lex/                     # (existing)
|   +-- platform/                # (existing)
|   +-- runs/                    # (existing) + narrative view, comparison, reproducibility
|   |   +-- components/
|   |       +-- narrative/       # NEW: storytelling components
|   |       +-- comparison/      # NEW: run comparison components
+-- i18n/
|   +-- formatters.ts            # NEW: locale-aware formatters
|   +-- messages/                # (existing) en.ts, uk.ts -- extended
|   +-- LocaleProvider.tsx       # (existing)
+-- lib/
|   +-- featureFlags.ts          # (existing)
|   +-- a11yAudit.ts             # NEW: dev-only axe-core
+-- shared/
|   +-- charts/                  # NEW: charting library
|   |   +-- AreaChart.tsx
|   |   +-- BarChart.tsx
|   |   +-- WaterfallChart.tsx
|   |   +-- RadarChart.tsx
|   |   +-- ForceGraph.tsx
|   |   +-- ParallelCoordinates.tsx
|   |   +-- SpecificationCurve.tsx
|   |   +-- ForestPlot.tsx
|   |   +-- chartAccessibility.ts
|   |   +-- chartTheme.ts        # (existing) enhanced
|   +-- hooks/                   # NEW: shared hooks
|   |   +-- useKeyboardShortcuts.ts
|   |   +-- useFocusTrap.ts
|   |   +-- useRovingTabIndex.ts
|   +-- motion/                  # NEW: animation presets
|   |   +-- presets.ts
|   |   +-- AnimatedContainer.tsx
|   |   +-- AnimatedList.tsx
|   |   +-- AnimatedNumber.tsx
|   |   +-- useReducedMotion.ts
|   +-- ui/                      # (existing) + shadcn/ui based components
|   |   +-- compounds/           # + ExplainabilityCard, UncertaintyDisplay, etc.
|   |   +-- layout/              # + ResizablePanelGroup, BottomSheet, etc.
|   |   +-- patterns/            # + CommandPalette
|   |   +-- primitives/          # shadcn: Toggle, Slider, Tabs, Tooltip, etc.
|   |   +-- tokens/              # + extended tokens
+-- workers/                     # NEW: web workers
|   +-- dagLayout.worker.ts
|   +-- jsonParse.worker.ts
|   +-- dataTransform.worker.ts
+-- sw.ts                        # (existing) service worker
```
