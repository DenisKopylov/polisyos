---
title: PolicyOS Universal Policy Designer (Layer-3, Grounding & Subordination) Implementation Plan
status: active-draft
owner: team-architecture
created: 2026-06-03
revised: 2026-06-06 (free-growth/search discipline: discovery posture, replayable search frontier, no-hardcode closure)
source_design_doc: ../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
organizing_constitution: ../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
governed_inventory: ../../../architecture/policy_design_case/cluster_ownership_map.toml
capability_ratchet: ../../../architecture/policy_design_case/capability_reality_report.json
failure_patterns: ../../reference/policy-design-case-failure-patterns.md
extends_plans:
  - ./POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md   # S0-S14 built the shadow designer mechanism
adr: ../../adr/0174-policy-evidence-capability-graph.md
scope:
  - engine-subordination-ports-adapters
  - grounding-shadow-to-authority
  - promotion-gate-d38
  - bounded-llm-agent
  - proving-ground-conversion
  - health-metric-instrumentation
  - anti-laundering-at-scale
---

# PolicyOS Universal Policy Designer (Layer-3, Grounding & Subordination) Implementation Plan

This plan executes the **next phase after Layer 2**: subordinating the **useful**
existing code — ~20 candidate capability sources (the largest: `foundry` ~309k,
`scientist` ~202k, `data_forge` ~110k, `fabric` ~81k, `ir` ~79k, plus `lex`,
`scholar`, the requirement modules, and more) **and the already-collected and
processed data assets** — to the runtime/quality discipline, while **triaging out
the code that should not be integrated** (conceptual legacy that violates the
organizing rules, not merely badly-implemented code). It grounds the shadow design
loop into real authority, builds the promotion gate (D3.8), adds a bounded LLM
agent, and converts the proving ground from typed blockers into grounded designs
or honest grounded abstentions.

"Subordinating all useful code" is bounded by what the waist can express: a
capability that maps to no existing Port is integrated only after a deliberate,
governed waist change (a new Port — constitution T5), never automatically. This
plan integrates everything the current Port set can carry and records the rest as
governed open questions.

It is governed by the organizing constitution
(`docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md`).
Read the constitution first; this plan does not re-derive its twelve invariants,
its ports/adapters/registry/conformance discipline, or its seven necessary
tradeoffs — it executes them. Where this plan says "the discipline", it means §5
and §7 of the constitution. Where it says "the tradeoffs" or "the health
metrics", it means §8.

## Read This Before Anything Else

Six rules shape everything below.

1. **Grounding leads generation.** Layer 2 proved the *mechanism* composes (depth
   1, shadow). The proving ground is still 0/13 because nothing is **grounded**,
   not because nothing is **generated**. Do not add the agent (G6) or widen (G7)
   until at least one case grounds through the waist (G5). Generation without
   grounding only manufactures more honest shadow blockers.

2. **The waist stays narrow; capability sources are subordinated, never absorbed.**
   No slice pulls source code into the core. `pdc` never imports any capability
   source (`foundry`/`scientist`/`data_forge`/`fabric`/`ir`/`lex`/…). A source
   enters the authority graph **only** through a conformance-proven,
   registry-admitted adapter that fails closed and downgrades (constitution §7).
   Widening the waist to match the sources is the P13 gravity well and is
   forbidden.

3. **Instrument the tradeoffs from slice one.** The five health metrics
   (envelope-expansion-rate, adapter-semantic-loss, governance-throughput,
   demand-pull-vs-abstention, search-recall@known-seeds + index-staleness) are
   frozen in G0 and measured every slice. **A stalled envelope-expansion-rate at
   healthy governance-throughput and healthy search recall/freshness is a
   first-class finding — a domain ceiling (T1), not a slice failure.** A stall with
   weak recall or stale indexes is a **search ceiling** — a repairable system
   defect, not a domain limit. This plan succeeds by honestly establishing
   reality, including a ceiling, never by faking a conversion.

4. **Honest objective still governs (Rule 5).** Optimize grounded-envelope
   expansion, calibration, reuse, and honest abstention — **never
   `useful_design_rate`**. A grounded honest abstention is a successful Layer-3
   output. Widening "useful" by lowering the grounding bar is the T6 inertia
   failure and a closure violation.

5. **Triage before adapter — not all code should be integrated.** Before any
   capability source or dataset gets an adapter, it is classified in G0 against a
   single criterion: *can its concept be expressed within the organizing rules
   (§5)?* Sound concept, any implementation quality → integrate (the adapter
   shields the core from bad implementation; refactor or strangle behind it).
   **Concept that violates the rules → quarantine, never integrate** — adapting it
   would launder a wrong concept into the authority graph, and conformance (an
   implementation/calibration check) will not catch a conceptual defect. The known
   examples already in-tree — `scenario_family` as an authority selector (forbidden
   by C1) and binary (non-graded) `lex` — are quarantine/strangle candidates, not
   integration targets.

6. **Universality or nothing — capability via search, never enumeration**
   (constitution Rule 12). Search discovers, adapters discipline, and the
   authority gate admits. Every adapter owns or invokes a **corpus-search path**:
   given a typed request, it searches the engine's indexes (the L1 dataset
   catalog's ~56k metric-bindings, the L2 claim graph, the L3 legal-norm graph,
   Foundry's method registry, the agent registry) for what might ground the
   request. A search result is `discoverable` or `executable`; it becomes
   `admitted_authority` only after adapter conformance for a declared purpose. The
   adapter carries **no hand-maintained list** of constructs, datasets, methods, or
   variables. **Search must hit the canonical corpus layer for the claimed
   capability.** A construct-scoped derivative index can help transition,
   acquisition routing, or consumer binding, but it cannot satisfy the layer-search
   claim, free-growth proof, or strangle replacement while the canonical layer is
   available. Adding a correctly-implemented resource — more processed data, a new
   source, a new Foundry method, a new agent — must raise capability with **zero
   new code**; if it does not, the implementation does not work as claimed. **No
   crutches, no hardcode fallbacks** — a fallback is not saved functionality, it is
   false reassurance that hides the real gap. The fixed procedure for any
   hardcoded enumeration found (e.g. `capability_index_compiler.KNOWN_CONSTRUCTS`,
   a manual Foundry-method list): mark it, build the discovery-search so a
   correctly-added resource becomes visible and executable, then **delete the
   fallback**; if deletion breaks something, that is the honest signal of where to
   work next, not a reason to restore the list. The **mechanism stays universal;
   only the validation is narrow** (prove on UA-MSME first). G0 is rebuilt under
   this rule — prior G0 work is not protected as done; at most it reduces the new
   G0's effort.

## Execution Doctrine (every slice obeys these)

- **Vertical, with a full closure contract.** Each slice carries one grounding
  capability end-to-end and must satisfy:
  - **Producer** — the adapter / gate / agent component (typed).
  - **Persisted artifact** — the admission record, grounded contract, or
    promotion record stored/emitted.
  - **Bridge + consumer** — who in the composed loop consumes the grounded output.
  - **Surface** — PUBLIC/REVIEWER/EXPERT/MACHINE projection of the grounded result
    and its envelope (constitution Rule = P03).
  - **Conformance** — the per-adapter adversarial-against-A battery the component
    passes before admission (this is the Layer-3 analogue of the semantic test;
    contract-only wrapping is P01 at the adapter level).
  - **Negative control** — the laundering the slice must block (engine output as
    authority without conformance; calibration over-claim; promotion without
    A-completeness; agent orchestration leakage).
  - **Health-metric delta** — which of the five metrics the slice moves, recorded.
  - **Registry/ratchet delta** — which port gains an admitted adapter at which
    maturity (`fail_closed` → `predictive` → `calibrated`).
- **Shadow until promoted.** Every engine/adapter/agent output is candidate/shadow
  until it passes conformance, is registry-admitted at a governed maturity, and
  (for authority) clears the promotion gate (G4). Generation never satisfies an
  authority slot (constitution Rules 1–2).
- **Conformance is the admission gate.** No adapter reaches an authority slot
  without passing its conformance battery. Admission maturity never exceeds the
  calibration evidence.
- **Reuse the discipline; define new contracts once.** The shared Layer-3
  contracts (Port, AdapterAdmissionRecord, conformance harness, health-metric
  ledgers) live **once in G0** and are referenced, never re-birthed per slice
  (anti-P13, constitution Rule 10).
- **Adversarial-against-A runs during grounding, not after.** Real grounding is
  when laundering and calibration-gaming first become live (constitution §9). The
  T2 red-team is a standing obligation raised by every new admitted adapter.
- **Search frontiers are persisted before they influence authority.** Every
  authority-relevant search records the request, searched indexes, index/rule
  versions, selected and rejected candidates, cutoffs, and absence or
  incompleteness reason before a selected result, no-hit, or abstention can affect
  a port. A search frontier is control-plane evidence, not producer authority
  (P25).
- **Search recall is measured, not assumed.** A replayable no-hit is auditable but
  not automatically adequate. Any abstention, no-hit, or domain-ceiling claim
  depends on known-groundable seed recall and index freshness for the declared
  envelope; otherwise the honest diagnosis is search-ceiling/system repair.
- **Engineering quality is not optional (every G slice).** Each slice uses
  best-in-class, well-maintained libraries and the repo's standardized stack
  (`duckdb` for catalogs/KGs, `pyarrow`/columnar for panels, strict `pydantic` for
  contracts, the existing `hnsw`/vector indexes for similarity) — never a
  hand-rolled equivalent of something the ecosystem already does well. Search
  engines are **index-backed, lazy, and streaming** (indexed catalog queries +
  vector search, not O(n) scans or eager full loads): they scale with corpus
  growth, which is partly *why* free growth (constitution Rule 12 / read-first
  Rule 6) holds — a hand-rolled,
  non-indexed engine does not free-grow, it chokes as data grows. **Index-backed
  also means backed by the canonical corpus layer being claimed, not only by a
  smaller construct-scoped cache derived from the hardcoded list being strangled.**
  Correctness =
  strict types + deterministic replay + fail-closed error handling (no silent broad
  `except`). Every slice's task plan **names the libraries/indexes it uses and
  includes a scaling/performance check**; "passes on the pinned case" is not enough
  if it cannot scale to the full corpus. A technically weak implementation is a
  defect, not a shortcut.

**Dependency gate.** Slices advance on a dependency DAG (below), not a linear
gate. A slice may start once its prerequisites pass conformance and admit their
adapters. The critical path is sequential; off-path adapters parallelize.

**Execution granularity (roadmap vs task plans).** This document is the
**roadmap**: strategy, sequencing, doctrine, the dependency DAG, and the per-slice
*closure contract*. It is **not** the coding spec. When a slice reaches the front
of the DAG, expand its closure contract into a separate executable task plan under
`docs/plans/active/layer3-slices/G{N}-*.md` — with exact files, typed
contracts/modules, exact test files + names (conformance and negative-control,
written red-first), exact validation commands + expected output, and the precise
registry/health-metric delta. Write task plans just-in-time; shared contracts are
defined once in G0 and referenced.

## Controlled Vocabulary (extends Layer 2)

| Kind | Examples | Rule |
| --- | --- | --- |
| Adapter maturity | `fail_closed`, `predictive`, `calibrated` | reuse the capability-ratchet maturity vocabulary; never invent adapter-only states |
| Grounding disposition | `grounded_binding`, `grounded_limited`, `grounded_abstention`, `ungrounded_blocked` | machine status for a port's grounded output |
| Promotion state | `shadow`, `governed_promoted`, `promotion_blocked` | the D3.8 gate output; promotion never skips A-completeness |
| Discovery posture | `discoverable`, `executable`, `admitted_authority` | search visibility is candidate state; authority requires adapter conformance and admission |
| Conversion outcome | `typed_blocker -> grounded_limited`, `typed_blocker -> grounded_abstention`, `unchanged_blocker` | proving-ground conversion classification |
| Health-metric trend | `expanding`, `flat`, `shrinking` (envelope); `clean`, `lossy` (semantic); `flowing`, `stalled` (throughput); `fresh`, `stale`, `recall_degraded` (search) | first-class governed signals (constitution §8.3) |
| Capability disposition (triage) | `integrate_as_is`, `integrate_after_refactor`, `wrap_then_strangle`, `quarantine` | G0 classification by constitutional-concept alignment; `quarantine` = conceptual legacy, deny-registered, never adapted |
| Data integration kind | `data_asset` (existing processed dataset), `acquisition` (newly fetched), `processing_transform` (`data_forge`) | distinct data paths; existing assets are **not** the acquisition loop and carry their own lineage/contamination checks |

## Proving Ground

The same 13 W12.D real_producer cases are the standing proving ground
(`runtime_useful_design_rate = 0/13`, all 13 `typed_blocker`). Layer 3's honest
target is to convert them — **case by case, through real grounding** — into:

- `grounded_limited` designs (a useful design inside a declared, calibrated
  envelope), or
- `grounded_abstention` (an honest "construct observed but no credible causal
  support / out of envelope", grounded in real substrate/analytics, not a shadow
  guess).

A case that cannot ground stays `unchanged_blocker` and is recorded as such. The
conversion rate and the **reason** for non-conversion (domain ceiling vs
search-ceiling vs missing adapter) are the phase's primary signal, not a target to
be maximized.

## Corpus Potential & Free Growth (what search lifts — a snapshot, never a ceiling)

The corpus is already a seven-layer, calibrated, capability-ready substrate. The
slices' search engines **lift it into authority only through adapters and
admission**; they do not rebuild it, and they bind to its **schema**, never its
current rows — so growth is free (constitution Rule 12 / read-first Rule 6).

| Layer | What it holds (current snapshot) | Lifted by |
| --- | --- | --- |
| L1 — Dataset catalog (DCAT) | ~137k datasets, ~56k metric-bindings, ~3.7M observations, quality/coverage/transport scores, 30+ sources | G1 substrate search |
| L2 — Academic claim graph (SKG) | ~7.9k curated causal claims (transport score, CI, contested, design-quality tier), ~62k parameter estimates, variable alignments | G2 causal + G3 analytics |
| L3 — Legal KG | ~6M provisions, ~374k rule-thresholds (metric/operator/value/unit), ~156k amendments (effective_from), norms | GL legal/mandate search |
| L4 — Domain panels (e.g. Ukraine) | normalized panels, unified schema (period_id, record_hash, schema_version, source_snapshot_id) | G1/G2 |
| L5 — Calibration registries | trust tiers (trust_cap/min_coverage), identification modes (point/partial/proxy), schema regimes (changepoints) | consumed as authority/envelope metadata by G1/G2/GL |
| L6 — Method/intervention routing | observation→method contracts (family→Foundry method), intervention-knob dictionary, lex→intervention map | drives adapter routing (port→method) |

**The numbers are a snapshot, never a ceiling.** The current G1 production L1
target is
`production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb`
table `ds_metric_bindings`; a capability-index or compiler-derived construct
cache is not an L1 substitute. More datasets, sources, Foundry
methods, or agents must raise capability with zero new code (constitution Rule
12). The **free-growth test is mandatory per adapter**: add a correctly-formed
synthetic resource (a new metric-binding, claim, method, or agent), refresh the
relevant index, and the engine discovers and uses it without a code change. An
engine that needs editing to see new data is not universal; an engine whose stale
index misses new data is not fresh enough to support abstention.

## G0 — Capability & Data Inventory, Triage & Discipline Freeze (gate before any adapter)

G0 is the readiness gate, mirroring Layer 2's S0: it **inventories and triages
what exists**, then freezes the shared Layer-3 discipline so later slices consume,
not birth, it. No adapter (G1+) starts until G0 is frozen and owned.

**Three gates, three failure modes.** Integration passes three distinct checks, in
order — collapsing them is the central error:

```text
TRIAGE (concept fits the rules?) → ADAPTER (translate + downgrade) → CONFORMANCE (calibrate / fail-closed)
  catches conceptual legacy          shields bad implementation        catches calibration-gaming
  (governance, upfront)              (ACL: refuse foreign concepts)    (per-adapter red-team)
```

Conformance checks implementation and calibration, **not concept** — so conceptual
legacy must be caught at triage, before any adapter is written.

G0 freezes, as committed artifacts:

1. **The Capability & Data Inventory** — every `src/polisyos/*` capability source
   (~20, not three) and every collected/processed data asset (`production_data/`,
   `tools/ops_runners/ukraine_data`, the corpora) enumerated with size, owner, and
   current authority touch-points.
2. **The `CapabilityTriageRecord` + `QuarantineRegistry`** — each inventory entry
   classified `integrate_as_is` / `integrate_after_refactor` / `wrap_then_strangle`
   / `quarantine` against the single criterion *can its concept be expressed within
   the organizing rules (§5)?* The `QuarantineRegistry` is the deny side of
   admission: conceptual legacy (e.g. `scenario_family`-as-authority, binary `lex`)
   is recorded here and **never adapted**.
3. **The `Port` contract** — the core's authority slots declared as typed
   interfaces a source must fill, derived from the cluster-map
   `publishes`/`consumes` edges (constitution §7.1). The Port set is fixed by the
   architecture's named authority slots; G0 does not invent Ports. A capability
   that maps to no Port is recorded as a governed waist-change open question, not
   silently dropped.
4. **The `AdapterAdmissionRecord`** — binds an adapter (extending
   `adapter_contracts.AdapterContractRegistry`) to a Port, an owner, a governed
   maturity, and its conformance evidence. Unregistered output is candidate/shadow
   only.
5. **The `DataAssetPort` + data-asset contract** — the path for **existing
   processed data** (distinct from the acquisition loop): wraps a dataset in
   `SourceContract` + provenance/lineage + rights + freshness + fitness + a
   contamination/leakage check (C41 + sealed-battery integrity). Existing data is
   grounded through this Port; newly fetched data through the acquisition adapter
   (G1).
6. **The conformance-harness skeleton** — extends `validate_adapter_preservation`
   (semantic-loss / `AdapterLossBlocker`) with the per-adapter
   adversarial-against-A battery interface. Conformance is the admission gate.
7. **The discovery/search discipline** — the shared `discoverable` → `executable`
   → `admitted_authority` posture, replayable search-frontier ledger, and absence
   / incompleteness semantics used by every G1+ search adapter, plus recall and
   freshness gates for known-groundable seeds. This is the P25/T7 firewall for
   Rule 12: search can widen candidate space, but cannot itself fill an authority
   slot or justify abstention when recall is unmeasured.
8. **The five health-metric ledgers** — envelope-expansion-rate,
   adapter-semantic-loss, governance-throughput, demand-pull-vs-abstention,
   search-recall@known-seeds + index-staleness
   (constitution §8.3), as governed config with owners and revision rules.
9. **The import-firewall lint** — `pdc` never imports any capability source; every
   `runtime/quality` source touch-point must resolve to a registered
   `AdapterContract`; and **quarantined modules are actively blocked** from the
   authority graph (not "un-adapted" but "must-not-adapt"). Extends the existing
   no-import test pattern.
10. **The constitution → ADR promotion** — lift §5 (twelve invariants) and §7
   (ports/adapters/registry/conformance) into an accepted ADR that repository
   gates can cite. Resolve the §8.4 open questions to "tracked, empirically open".
11. **The empty-port map** — for the proving ground, which authority slots are
    currently unfilled (the typed_blocker causes), ranked by binding-constraint
    order: substrate → causal support → calibration.
12. **The adapter-cost map** — which source outputs are already near-typed
    (IR-analytics proof-carrying, `foundry/methods/api`) vs raw — to sequence the
    cheapest-high-value groundings first.
13. **First validation case** — pinned to UA-MSME (S3 already pinned its constructs;
    `tools/ops_runners/ukraine_data` is its data asset).

- **Done when:** the inventory and triage cover every capability source and data
  asset; the `QuarantineRegistry` is populated and enforced by the import-firewall
  lint; the thirteen artifacts are committed, owned, and referenced by the
  conformance harness; the ADR is accepted; the discovery/search discipline is
  available to G1+; and the empty-port, adapter-cost, and data-asset maps cover
  the proving ground.

**Dependency DAG (critical path bold):**

```text
G0 ──▶ **G1** ──▶ **G4** ──▶ **G5** ──▶ **G6** ──▶ **G7**
 │       │                      ▲
 │       └▶ G2 ─────────────────┤
 │       └▶ G3 ─────────────────┘
 └▶ G8 (cross-cutting health-metric governance; instruments G1.. , formalized late)
```

## Slice Sequence (overview)

| # | Slice | Adds (minimal) | Unifying abstraction | Path |
| --- | --- | --- | --- | --- |
| G0 | Inventory, triage & discipline freeze | Capability+data inventory, `CapabilityTriageRecord`, `QuarantineRegistry`, Port, AdapterAdmissionRecord, DataAssetPort, conformance harness, discovery/search discipline, 5 health ledgers, import-firewall lint, ADR | triage + the narrow-waist admission contract | gate |
| G1 | Substrate grounding **search engine** | construct-agnostic search over L1 DCAT (~56k metric-bindings) + L5 calibration + L6 routing → `SourceContract`; **strangles** `KNOWN_CONSTRUCTS`/`REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS` | D1 binding constraint; capability via search | critical |
| G2 | Causal/forecast **search engine** | search L2 claim graph (transport/CI) + Foundry method registry → `ForecastSupport`; calibration on observable subset | tiered forecast authority | off-path |
| G3 | Analytics **search engine** | search L2/IR proof-carrying analytics → `ProofCarryingAnalyticsRecord` (generalize `ir_analytics_bridge`) | proof-carrying claims | off-path |
| GL | Legal/mandate **search engine** | search L3 lex KG (rule_thresholds, amendments, norms) → mandate/legal-threshold authority + temporal competence; binds via `lex_intervention_map` | legal authority; off-path sibling of G2/G3 | off-path |
| G4 | Promotion gate (D3.8) | shadow → governed authority gate; A-completeness + delegation rails | the missing shadow→authority lever | critical |
| G5 | First proving-ground conversion | composed loop + G1–G4 on the pinned case | typed_blocker → grounded design/abstention | critical |
| G6 | Bounded agent | LLM orchestrator/generator (reuse `scientist/orchestration/llm`); orchestration-choice audit | candidate-not-authority at agent scale | critical |
| G7 | Envelope widening | one case → region; sublinear marginal grounding cost; feed S14 battery | mechanism generality on real grounding | critical |
| G8 | Health-metric governance & re-basing | T1–T6 governed signals; D4.4 corpus re-basing rule | watch the tradeoffs or they go silent | cross-cutting |

The phase progress meter is the **adapter-admission registry coverage** (ports
with an admitted adapter, at what maturity) plus the **proving-ground conversion
classification** — not the Layer-2 cluster-map burn-down (already complete).

---

## Per-Slice Detail

Template fields: Goal · Prereqs · Adds (minimal) · Not yet (fence) · Closure
(producer / persisted / bridge+consumer / **surface** / conformance / negative) ·
Firewalls · Health metric · Promotion · Done when.

### G1 — Substrate Grounding Search Engine (the binding constraint)
- **Goal:** build a **construct-agnostic grounding search engine** (Rule 12): given
  any construct/metric, search the real L1 DCAT catalog
  (`production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb`
  table `ds_metric_bindings`, ~56k metric-bindings) for binding datasets, rank by
  L5 calibration (trust tier, identification mode, schema regime), route via L6
  (family→method), and emit a conformance-validated
  `SourceContract` — or fail closed / abstain. **Validate** it narrowly on the
  UA-MSME constructs (existing Ukraine assets via `data_forge`, `fabric`
  acquisition for gaps), proving `construct_not_observed → grounded_binding` or
  honest `observed_but_uncertain`. The engine carries **no construct/dataset list**.
- **Prereqs:** G0 (`DataAssetPort`, L1/L5/L6 indexes lifted, triage).
- **Adds:** (a) the **substrate search** over L1 metric-bindings + L5 calibration +
  L6 routing → `SourceContract`, with provenance/lineage + rights + freshness +
  fitness + contamination checks and a replayable search-frontier ledger; (b) the
  **strangle** of
  `capability_index_compiler.KNOWN_CONSTRUCTS` /
  `REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS` / `capability_resolver` pinned
  fixtures — replaced by the real DCAT search and deleted with no fallback (T5);
  the capability-index may remain only as transition/acquisition evidence, never
  as the L1 search path; (c) the **free-growth test** (a new synthetic
  metric-binding grounds through the real DCAT path with zero code change) and the
  **mechanism-generality test** (≥2 distinct constructs grounded by the same
  engine). Admission `fail_closed`/`predictive`.
- **Not yet:** no causal estimates (G2); no promotion to authority (G4).
- **Closure:** producer = the substrate search adapter; persisted =
  `AdapterAdmissionRecord` + search-frontier ledger + grounded `SourceContract` +
  a lineage record; bridge/consumer = S3 acquisition loop and the substrate consume
  the binding; **surface** = coverage/lineage/abstention in EXPERT/MACHINE;
  conformance = adapters fail closed on absent rights / contaminated lineage,
  incomplete search, and over-claimed coverage; negative = raw
  `data_forge`/`fabric` output cannot satisfy a construct slot without the adapter,
  a no-hit without a replayable search frontier cannot ground abstention, and a
  dataset failing the contamination check cannot ground.
- **Firewalls:** P15-at-scale, P01 (contract-only), C41 (data contamination),
  import-firewall.
- **Health metric:** adapter-semantic-loss (first reading); governance-throughput.
- **Promotion:** shadow/governed-for-binding only.
- **Done when:** the same construct-agnostic engine, with no pinned construct or
  dataset enumeration, handles at least two distinct validation constructs (binding,
  uncertainty, or grounded abstention), discovers a correctly-added synthetic
  metric-binding without code change, and grounds at least one real UA-MSME data
  path or honestly records the ceiling. A domain ceiling requires healthy recall
  and fresh indexes; otherwise the outcome is search-ceiling repair. Raw-output,
  incomplete-search, no-ledger-abstention, false-abstention, and contaminated-data
  negative controls fail closed.

### G2 — Causal/Forecast Search Engine
- **Goal:** ground effect claims through search over the L2 claim graph and
  Foundry method registry, then translate conformance-valid candidates into
  `ForecastSupport`, calibrated **only on the observable subset**, with honest
  tiers (`simulation_only`/`contested` by default at scale).
- **Prereqs:** G1 (needs grounded substrate to estimate over).
- **Adds:** the causal/forecast search path, search-frontier ledger, adapter,
  calibration check, transport-limit declaration, and admission at
  `predictive`/`calibrated` only where calibration passes.
- **Not yet:** no large-scale equilibrium authority; no promotion (G4).
- **Closure:** producer = search + adapter; persisted = search-frontier ledger +
  grounded `ForecastSupport`; bridge/consumer = S10 prediction consumes it;
  **surface** = forecast tier + uncertainty; conformance = the adapter cannot emit
  a tier above its calibration or treat a search hit as support without adapter
  validation; negative = an over-claimed tier is downgraded/blocked.
- **Firewalls:** calibration-gaming, regime ⟂ forecast tier, P15.
- **Health metric:** envelope-expansion-rate (first real reading); semantic-loss.
- **Promotion:** governed where calibrated; contested stays advisory.
- **Done when:** calibration passes on the observable subset; over-claim negative
  control is downgraded; non-observable cases honestly tiered.

### G3 — Analytics Search Engine
- **Goal:** generalize `ir_analytics_bridge` into the standard analytics search
  and adapter path: find proof-carrying analytics candidates and translate valid
  `scientist`/IR outputs into `ProofCarryingAnalyticsRecord`, binding claims to
  proof-carrying certificates.
- **Prereqs:** G0 (may parallelize with G1/G2).
- **Adds:** the analytics search path, search-frontier ledger, generalized
  adapter, proof-carrying binding, and fail-closed behavior when a required
  certificate is missing (the exemplar already does this).
- **Not yet:** no promotion (G4); no agent (G6).
- **Closure:** producer = search + adapter; persisted = search-frontier ledger +
  proof-carrying bindings; bridge/consumer = S11 analytics consumers; **surface**
  = certificate refs in EXPERT/MACHINE; conformance = missing-certificate fails
  closed and search hits cannot substitute for certificates; negative =
  uncertified claim cannot bind.
- **Firewalls:** P15, proof-carrying integrity.
- **Health metric:** semantic-loss; governance-throughput.
- **Promotion:** governed where certified.
- **Done when:** a claim binds to a real certificate; uncertified negative control
  fails closed; `ir_analytics_bridge` behavior preserved as a regression anchor.

### GL — Legal/Mandate Search Engine
- **Goal:** ground legal mandate, thresholds, and temporal competence through
  search over the L3 legal KG (`rule_thresholds`, amendments, norms, references)
  and translate conformance-valid candidates into legal/mandate authority records
  for the relevant port. Search may discover legal candidates; it never grants
  legal authority without adapter validation and temporal replay evidence.
- **Prereqs:** G0 (search-frontier discipline, legal source triage); may parallelize
  with G2/G3.
- **Adds:** legal/mandate search path, search-frontier ledger, amendment/time
  replay boundary, `lex_intervention_map` binding where applicable, and fail-closed
  legal authority projection.
- **Not yet:** no lowering of evidence or mandate floors; no promotion (G4).
- **Closure:** producer = legal search + adapter; persisted = search-frontier
  ledger + mandate/legal-threshold authority record + temporal lineage;
  bridge/consumer = design constraints and promotion gate consume the legal
  boundary; **surface** = threshold/mandate/temporal competence in EXPERT/MACHINE;
  conformance = missing effective-time, authority-level, or amendment lineage
  fails closed; negative = retrieved legal text without temporal/authority
  validation cannot bind.
- **Firewalls:** P05/P15/P22 (mandate laundering), P07/P08 (rule/time replay),
  P25 (search frontier laundering).
- **Health metric:** semantic-loss; governance-throughput.
- **Promotion:** governed where validated; otherwise limitation/blocker.
- **Done when:** one legal threshold or mandate boundary binds through the legal
  search adapter with replayable temporal authority, and retrieval-only or
  stale-amendment negatives fail closed.

### G4 — Promotion Gate (D3.8) — the missing lever
- **Goal:** convert a grounded B output from `shadow` to `governed_promoted`, the
  piece neither Layer 2 nor the constitution's current code provides.
- **Prereqs:** G1 (at least one grounded port).
- **Adds:** the D3.8 gate: checks A-completeness for the envelope region, requires
  the grounded contracts (G1–G3) for every promoted claim, and routes high-stakes
  promotions through S7 delegation / `HumanDecisionRecord`. Emits a typed
  `PromotionRecord` (`governed_promoted` / `promotion_blocked`).
- **Not yet:** no production/rollout authority; promotion is to **governed**, not
  production.
- **Closure:** producer = the gate; persisted = `PromotionRecord`; bridge/consumer
  = closeout reads promotion state; **surface** = promotion state + envelope in all
  four audiences; conformance = promotion without grounded contracts or without
  A-completeness is blocked; negative = a shadow output cannot self-promote; a
  promotion missing an A-firewall ref is blocked.
- **Firewalls:** promotion-without-A-completeness, P26 (human accountability for
  high-stakes promotion), shadow-self-promotion.
- **Health metric:** governance-throughput (admit/stall of promotions).
- **Promotion:** this slice *is* the promotion mechanism; it grants governed, never
  production.
- **Done when:** a grounded output promotes to governed with a `PromotionRecord`;
  every bypass negative control fails closed.

### G5 — First Proving-Ground Conversion (the milestone)
- **Goal:** run the full composed loop (S4–S14) + G1–G4 on the pinned case and
  convert it from `typed_blocker` to `grounded_limited` **or**
  `grounded_abstention` — not shadow. First real Layer-3 value.
- **Prereqs:** G1, G4 (for a grounded abstention); G2/G3 additionally (for a
  grounded design).
- **Adds:** the integration wiring that lets the composed loop consume grounded
  contracts and a promotion state; the first `envelope-expansion-rate` measurement.
- **Not yet:** no widening (G7); no arbitrary requests (G6).
- **Closure:** producer = the converted case record; persisted = the conversion
  classification + envelope-expansion reading; bridge/consumer = W12.D emits the
  conversion; **surface** = the grounded result + envelope + limitations in all
  audiences; conformance = the conversion is replayable and grounded (no shadow
  laundering); negative = a "conversion" without grounded contracts is rejected.
- **Firewalls:** shadow-as-grounded laundering, honesty-inertia (T6: abstention
  must be grounded, not a hidden refusal).
- **Health metric:** **envelope-expansion-rate** (the phase's headline reading).
- **Promotion:** governed for the converted case.
- **Done when:** the pinned case is `grounded_limited` or `grounded_abstention`
  with real evidence/calibration/envelope, replayable, and the expansion-rate is
  recorded — even if the honest result is a grounded abstention (T1).

### G6 — Bounded Agent (arbitrary request → grounded result-or-abstention)
- **Goal:** take an arbitrary natural-language policy request and produce a
  grounded result inside the envelope or an honest grounded abstention outside it,
  via a bounded LLM agent reusing `scientist/orchestration/llm`.
- **Prereqs:** G5 (a working grounded loop to orchestrate).
- **Adds:** the agent as **candidate-generator + search-controller + tool
  orchestrator**: NL → grammar expansion (candidate; grammar-first, anti-P15) →
  grounding-demand identification → adapter orchestration → counterexample-refine
  loop → DesignRecord. The agent never fills an authority slot; A verifies.
- **Not yet:** no agent authority; no production; no unbounded tool access.
- **Closure:** producer = the agent loop; persisted = the search ledger including
  **orchestration choices** (tool/evidence selection, framing — per T4);
  bridge/consumer = the composed loop consumes agent candidates; **surface** = the
  grounded result + envelope, with the agent's role marked candidate-only;
  conformance = the agent cannot satisfy an authority slot and its
  orchestration-choice audit is replayable; negative = agent fluent output as
  authority is blocked; an out-of-envelope request yields a grounded abstention.
- **Firewalls:** P15/P25 (agent stays candidate/orchestrator), T4 authority-gradient
  / selection-framing leakage, structured-deterministic tool interfaces.
- **Health metric:** demand-pull-vs-abstention (does demand move grounded output?).
- **Promotion:** shadow candidates; authority only via A + G4.
- **Done when:** an arbitrary request yields a grounded result inside the envelope
  or a grounded abstention outside it; the orchestration-choice audit is
  replayable; every agent-laundering negative control fails closed.

### G7 — Envelope Widening (one case → region)
- **Goal:** scale grounding from one case to a region (e.g. UA-MSME-adjacent
  cases), proving **sublinear marginal grounding cost** (mechanism reuse, not
  bespoke per case), and feed S14's universality battery with **real grounded
  breadth** rather than fixtures.
- **Prereqs:** G5, G6.
- **Adds:** region-level grounding via reused adapters; the marginal-cost
  measurement; the S14 battery fed by grounded cases.
- **Not yet:** no "universal" claim beyond what the certified envelope covers (S14
  still gates).
- **Closure:** producer = the region conversions; persisted = marginal-cost +
  reuse-rate + region envelope-expansion; bridge/consumer = S14 battery consumes
  grounded breadth; **surface** = per-region scorecard + envelope; conformance =
  reuse is real (not relabeled bespoke); negative = bespoke per-case grounding
  counted as mechanism generality is flagged (reuses S12/S14 bespoke detection).
- **Firewalls:** bespoke-disguise (S14 defeater), envelope honesty (Rule 6).
- **Health metric:** envelope-expansion-rate (region); semantic-loss (region).
- **Promotion:** governed per grounded case; S14 gates any universal wording.
- **Done when:** a region grounds with sublinear marginal cost; S14 battery passes
  on real grounded cases or honestly limits the claim.

### G8 — Health-Metric Governance & Corpus Re-basing (cross-cutting)
- **Goal:** make the five tradeoff metrics first-class governed signals and add the
  D4.4 corpus re-basing rule S14 deferred, so the tradeoffs are watched and the
  battery cannot stale into gameability.
- **Prereqs:** G0 (instrument from G1 onward); formalized after G5.
- **Adds:** governed wiring of envelope-expansion-rate, adapter-semantic-loss,
  governance-throughput, demand-pull-vs-abstention, and search-recall@known-seeds
  + index-staleness; the D4.4 re-basing rule with freeze-hash discipline;
  empirical answers to the §8.4 open questions.
- **Not yet:** nothing fenced; this is the standing instrumentation track.
- **Closure:** producer = the metric ledgers + re-basing rule; persisted = the
  governed signals + re-basing receipts; bridge/consumer = readiness/closeout read
  the signals; **surface** = the five metrics in EXPERT/MACHINE; conformance =
  re-basing cannot leak sealed answers; negative = a metric "improved" by lowering
  a bar is blocked (T6), and a search recall miss cannot be reported as a domain
  ceiling (T7).
- **Firewalls:** re-basing contamination, metric-gaming, honesty-inertia,
  false-abstention/search-ceiling laundering.
- **Health metric:** all five (this slice owns their governance).
- **Promotion:** governed signals; never authority.
- **Done when:** the five metrics are live and governed; D4.4 re-basing is
  implemented with integrity; §8.4 open questions carry empirical answers
  (including, if true, a recorded domain ceiling distinct from search ceiling).

---

## Cross-Cutting Tracks

- **T0 — Adapter registry & health-metric ledger.** Every slice updates the
  `AdapterAdmissionRecord` registry and the five health ledgers; CI reports
  registry coverage and metric trends. This is the single Layer-3 progress meter
  (the Layer-2 cluster-map burn-down is complete).
- **T1 — Adversarial-against-A (raised by grounding).** Standing red-team for
  adapters that pass conformance but launder/over-claim. Every admitted adapter
  raises it (constitution §9).
- **T2 — Waist-stability watch.** Monitor `AdapterLossBlocker` / semantic-loss as
  the empirical detector that the waist is placed too thin (constitution T2/T5).
  Forced waist changes are the highest-governance changes.
- **T3 — Import-firewall & replay invariants.** `pdc`-never-imports-a-source,
  adapter-registered touch-points, and replay integrity on every slice.
- **T4 — Quarantine & strangler retirement.** The `QuarantineRegistry` (the deny
  side of admission) records conceptual-legacy modules; the import-firewall
  actively **blocks** them from the authority graph. `wrap_then_strangle`
  capabilities route their useful sub-capability through a new adapter while the
  bad concept is retired; no quarantined concept is resurrected through an adapter
  without re-triage.
- **T5 — Free-growth, anti-hardcode & search-frontier integrity (Rule 12).** Every
  adapter slice runs four standing gates: a **no-hardcode-enumeration lint**
  (literal construct/dataset/method/variable lists in adapter code = fail), a
  **free-growth test** (a correctly-formed synthetic resource — metric-binding,
  claim, method, agent — is discovered and used with zero code change), and a
  **search-frontier replay test** (selected candidates, rejected candidates,
  cutoffs, and absence/incompleteness reasons are replayable before they influence
  any port), and a **known-groundable recall/freshness test** (seeded resources are
  found after index refresh, so no-hit can be distinguished from search failure).
  The **strangle backlog** —
  `capability_index_compiler.KNOWN_CONSTRUCTS`,
  `capability_resolution.REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS`,
  `capability_resolver` pinned fixtures, any manual Foundry-method list — is
  tracked here; each entry is marked, replaced by search, and **deleted with no
  fallback**. For G1, "replaced by search" means the real L1
  `ds_metric_bindings` path, not the capability-index produced from those same
  constructs. Breakage on deletion is a tracked next-work signal, never a reason to
  restore the list.

## Ambition Map — Resolving The Constitution's Open Questions

This phase is complete only when the §8.4 open questions carry **empirical**
answers and S14's battery holds on **real grounded** breadth. Any "universal"
claim before that is laundering (S14 enforces this).

| Constitution open question | Resolved by | Done? |
| --- | --- | --- |
| Is the waist vocabulary at the right altitude (T2/T5)? | G1–G3 semantic-loss readings | ☐ |
| Is real grounding achievable at acceptable cost, or is the honest equilibrium abstention (T1)? | G5 + G7 envelope-expansion-rate | ☐ |
| Is demand-pull strong enough to overcome abstention inertia (T6)? | G6 demand-pull-vs-abstention | ☐ |
| Does the bounded agent leak authority via orchestration choices (T4)? | G6 orchestration-choice audit | ☐ |
| Promotion gate (D3.8) exists and gates shadow→authority? | G4 | ☐ |
| Proving ground converted (or ceiling honestly established)? | G5 + G7 conversion classification | ☐ |
| Useful code + data integrated through the waist; conceptual legacy quarantined? | G0 triage + per-slice adapters + `QuarantineRegistry` | ☐ |
| Free growth: capability via search, zero hardcoded enumeration; strangle backlog deleted with no fallback? | Rule 12 + T5 (no-hardcode lint + free-growth test); strangle of `KNOWN_CONSTRUCTS` et al. | ☐ |
| Search frontier integrity: hits, no-hits, and abstentions are replayable and not projected as authority? | G0 search discipline + T5 search-frontier replay tests; P25 negatives in G1/G2/G3/GL/G6 | ☐ |
| Search recall/freshness: false abstention is distinguished from domain ceiling? | G0 search discipline + T5 known-groundable recall/freshness tests; G8 search-recall@known-seeds + index-staleness | ☐ |

**Plan-level done:** every useful capability source and data asset is either
integrated through a conformance-admitted adapter or recorded as a governed
waist-change open question, and all conceptual legacy is quarantined and
firewall-blocked; the registry covers the binding-constraint ports with admitted
adapters; authority-relevant search frontiers are replayable and cannot substitute
for producer evidence; search recall/freshness is measured so false abstention is
not mistaken for domain ceiling; at least one proving-ground case is grounded (or
its non-conversion is honestly attributed to a domain ceiling); the five health
metrics are governed and live; the agent handles arbitrary requests within the
envelope; and S14 passes on real grounded breadth. Establishing a **domain
ceiling** is a valid, successful outcome only after search ceiling is ruled out
(Rule 3, T1, T7).

## Validation

Run with `cwd = policy-engine`. Per-slice commands are added to each slice's task
plan when it opens. Phase-level gates:

```bash
cd policy-engine

# Discipline integrity (every slice):
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py   # (waist + slices stay green)
# import-firewall: pdc never imports engines; runtime/quality engine touch-points are adapter-registered (G0 lint)
# conformance: every admitted adapter passes its adversarial-against-A battery

# Proving ground (the phase signal):
uv run python tools/quality/validation/run_universal_outcome_corpus.py --mode real_producer
# (Layer-3 target: ≥1 case converts typed_blocker -> grounded_limited|grounded_abstention,
#  expansion-rate recorded, health metrics live; floors intact, closeout_honesty preserved)
```

A slice is "done" only when its closure contract holds, its conformance battery
passes, its health-metric delta is recorded, and the registry/readiness gates stay
green.

## Relationship To The Existing Plans And Docs

- **Layer 2** (`POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md`)
  built the **shadow designer mechanism** (S0–S14, depth-1). This plan grounds it
  into authority. Layer 2's cluster-map burn-down is complete and is not this
  plan's meter.
- **The constitution**
  (`universal-policy-design-system-vision-and-organizing-rules.md`) is the
  governing law: §5 invariants, §7 discipline, §8 tradeoffs/metrics, §9 direction.
  This plan executes it; it does not amend it. If execution reveals the
  constitution is wrong, change the constitution first, deliberately.
- **The capability graph** (ADR-0174) is the substrate authority spine the
  adapters extend; the cluster map's `publishes`/`consumes` edges are the port map.
- **D3.8** (promotion gate) and **D4.4** (corpus re-basing) in the target
  architecture are realized here (G4, G8) — the two named pieces Layer 2 deferred.
