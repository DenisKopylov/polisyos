---
plan_id: layer3-gy-engine-subordination
title: "GY - Engine Subordination (scientist DAG / fabric / scholar through the waist)"
type: slice-plan
status: draft
created: 2026-06-13
slice: GY
scope: cross-slice
depends_on:
  - docs/plans/active/layer3-slices/GX-universal-free-growth-runtime-hardening.md
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/reference/policy-design-case-failure-patterns.md
floor_id: layer3_grounding_subordination
metric: layer3_engine_subordination
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# GY - Engine Subordination

## For Agentic Workers

GX hardened the waist so it stops passing by authored summaries. GY connects the
**already-built** engine capability to that hardened waist, so the proving ground
can move past the honest blocker GX records. GY is where capability grows; GX is
the rail that keeps the growth honest.

Two rules govern every GY task, both from the GX Asset Registry section:

```text
1. Subordinate, do not rebuild. The capability exists (Asset Registry). A GY
   task that builds a parallel engine, pipeline, or agent is mis-specified.
2. No pass for the smart component. A subordinated engine output is authority
   only if it flows through GX rails — resolver, reducer, and a producer-root
   chain that reaches measurement roots. DAG sophistication is not a root.
```

GY does not amend GX. Every GY artifact is validated by the GX hardening
validator (`check_policy_design_case_layer3_gx_hardening.py`): reducer
provenance, producer-root chain, resolver dereference, runtime literal lint. A GY
subordination that cannot pass those rails is not done; it is a typed blocker.

## Precondition (hard gate) — SATISFIED (2026-06-13)

GY may not start until **GX provisional Task 12 has recorded a measured,
reducer-authored outcome** for the pinned route. This is **met**:
`layer3_gx_provisional_pinned_route_outcome_report.json` records outcome
`typed_blocker` from `reduce_g5_conversion_outcome`, and
`layer3_gx_expected_red_checks.json` carries `provisional_task12_complete: true`.
The honest baseline GY moves from is: g1 grounding closure `typed_blocker`, g4
`promotion_blocked`, g5 `unchanged_blocker`, with g1 search measured (`pass`).

Before starting, confirm one thing the gate does **not** prove: that the GX
validator's red set equals the `expected_red_checks` catalogue (no uncatalogued
drift on the consolidated branch). GY's job is to drive that catalogued red —
~1184 `reducer_provenance_missing` on `g2/g3/gl/g6/g7/g8` — to zero (real
provenance via subordination) or to honest demotion. **That count is GY's
progress meter.**

## Why Subordination, Not Construction

The June 2026 `src/polisyos` sweep found the target architecture already built
across four engines; the gap was seams, not systems — and several seams are
**already partly wired**, which is exactly where the "build vs integrate" trap
lives. GY wires (or completes the wiring of) these seams:

| Layer | Asset (exists) | Already-wired? | Seam GY completes |
| --- | --- | --- | --- |
| supply | `data_forge` `DatasetCatalogGraph` (hnsw+text, 137k datasets, 56.8k bindings) | no — runtime `RetrievalService` passes no `dataset_catalog` | wire it in (GY-1) |
| computation | `foundry` ID/bounds/transport/DRO (~410 methods), `ir/analytics` contracts | partially — DAG calls foundry via `scientist/adapters/foundry_bridge.py` | reality census (GY-0) |
| design process | `scientist_policy_design` DAG | **yes — runtime already calls `run_experiment` at `run_lifecycle.py:1408`** | govern that output into the G5 route (GY-2) |
| design space | `lex/interventions` (`TemporalInterventionSequencer`, `HierarchicalPolicySearchAdapter`) | **yes — DAG node `run_hierarchical_policy_search` already calls it** | knob-provenance via GY-2 (GY-5 folds in) |
| acquisition | `fabric` connectors + `foundry` `RequiredDataSpec` + `scientist/agent` `DataNeedExtractor`/`DataNeedSpec` | partially — NL→`DataNeedSpec` exists; gap→DataNeed does not | add `RequiredDataSpec` as a second source (GY-3) |
| agent | `scientist/agent` platform (PI/drafter/supervisor, tool-loop) | yes — but audit is synthetic, not event-backed | event-backed G6 audit (GY-4) |
| L2 growth | `scholar/search` pipeline (provider failover) | no OpenAlex/Crossref provider | add provider (GY-6) |

**The recurring trap, restated for GY.** Two seams are *already wired in
production* (`run_experiment` is called; lex is called by the DAG). A GY task
that says "build the DAG adapter" or "subordinate lex" from scratch repeats the
G1-hollow pattern — building beside a live path. For those rows the real work is
**govern the existing output**, not construct a new one. GY-0 census must first
report what the existing wiring produces and whether it reaches the waist.

## The Evidence Ladder (organizing frame for growth)

GY does not promise "any policy." It promises that, when direct measurement is
absent, the system descends a typed ladder of evidence producers instead of bare
abstention, and reports which rung it reached. Each rung is a producer type with
its own authority ceiling; composition follows the weakest-boundary rule
(constitution Rule 4).

| Rung | Producer | Asset | Authority ceiling |
| --- | --- | --- | --- |
| 0 direct measurement | catalog binding → panel | `DatasetCatalogGraph` + fabric fetch | per trust tier (L5) |
| 1 derivation | deflate / per-capita / aggregate | `data_forge` recipes + `foundry` | near-lossless |
| 2 proxy | validated substitute | L5 proxy_mappings + `ir.transportability` | proxy_identified |
| 3 transport | cross-jurisdiction estimate | `ir.transportability` + L2 transport scores | limited |
| 4 bounds | partial identification | `foundry.distributional_bounds`, `ir.partial_identification` | bounds, not point |
| 5 simulation | calibrated structural model | `foundry.agent_sim` + `calibration` | simulation_only |
| 6 elicitation | expert / LLM panel with track record | `scientist/agent` + scholar | elicited_prior |
| 7 acquisition plan | RequiredDataSpec → fetch / pilot | `foundry` ID engine + fabric (GY-3) | plan, not evidence |

Gap → ladder descent replaces bare abstention: a no-hit at rung 0 routes to rung
k+1 until a producer grounds or rung 7 emits an acquisition plan with a cost. The
rung reached is the T1 measurement the constitution asks for. **Adding a rung is a
follow-on slice, not part of GY's minimal set** — GY wires rungs 0–5 that already
have assets and proves the descent mechanism on the pinned case.

## Producer-Root Rule (inherited, restated)

Every subordinated output carries a typed producer record (GX Producer Root Chain
Rule). For GY specifically:

- `DatasetCatalogGraph` query → `measurement` (corpus + snapshot hash).
- fabric fetch → `measurement` (CAS digest = snapshot hash).
- a `scientist_policy_design` node bundle → `derivation`; its chain must reach the
  measurement roots it consumed (panels, SKG). A bundle with no measurement
  ancestry is a candidate, never authority.
- `foundry` method output → `derivation` over its input data snapshot.
- elicitation (LLM/expert) → `elicitation`; ceiling `elicited_prior`, never higher.

A GY adapter that emits a positive port status without a measurement-rooted chain
fails the GX validator. This is the firewall against subordinating fluency.

---

## GY-0 - Engine Reality Census (the keystone — everything downstream is re-derived from it)

This is the most important task in GY, and the one most likely to be done
shallowly. **Both reviewers of this system repeatedly confused "exists" with
"wired" with "works".** The G1 search was called hollow when it had been fixed;
the DAG was told to be "built" when it was already invoked in production; a
"DataNeed translator" was specified while `DataNeedSpec` already existed. The
census exists to end that confusion *before* a single wire is changed. The user's
framing is the test the census must pass: **if everything exists yet nothing
works, then something specific was missing — name it precisely for every asset.**

A capability that "exists but doesn't work" is never a mystery; it is always one
of a small set of concrete gaps. The census's job is to assign each asset to
exactly one gap, by **execution, not by label**.

### Census discipline (non-negotiable)

- **No label is evidence.** `execution_tier`, registry maturity, README claims,
  prior plan prose, this conversation's findings, and assistant memory are NOT
  evidence. The only evidence is a recorded run on real input. Every asset starts
  at `execution_status: unknown` and may not leave it without a run.
- **Existence is one field, not a verdict.** "The module is there" answers nothing.
  An asset is not done in the census until reachability, execution, dataflow,
  authority, and gap-class are all filled.
- **Trace to a named consumer.** An asset is not "wired" because it is imported.
  It is wired only if its output reaches a *named* downstream consumer. Record the
  consumer, or mark the output `dropped`/`logged_only`.
- **Smart-component check.** Any asset whose output already reaches a surface or
  authority slot **without** producer-root provenance is flagged
  `laundering_candidate` — a finding to fix, never a pass.
- **Scope = the pinned route only.** Census every asset the pinned UA-MSME case
  actually touches, traced end to end. Do not census all 308k of foundry; census
  what the route invokes. Out-of-route assets are listed as `out_of_route`, not
  inspected.

### The census record (one committed artifact, one row per asset)

Artifact: `architecture/policy_design_case/layer3_gy_engine_census.json`. Each
row carries:

```text
asset_id
module_path                 # file
entrypoint                  # function/class actually invoked
existence_status            # present | absent
reachability:
  imported_by               # call sites (file:line)
  called_from_production     # bool + cite (runtime/http path) | tools-only | tests-only | dead
execution_status            # runs_e2e_on_real | runs_with_deadline_adapter | fails | never_invoked | unknown
execution_evidence          # smoke command + output hash (required if not never_invoked)
consumes                    # corpus / contract refs it reads
emits                       # contract it produces
output_destination          # waist_port:<id> | CAS | dropped | logged_only | another_engine:<id>
authority_status            # governed | laundered | candidate_only | none
gap_class                   # see taxonomy
canonical_vs_duplicate      # canonical | shim_of:<asset> | dead | duplicate_of:<asset>
recommended_gy_action       # govern | wire | repair | build | demote | delete | none
evidence_refs               # file:line, smoke hash, artifact refs
```

### Gap taxonomy (the central deliverable — answers "why doesn't it work")

Every census row is assigned exactly one. The class dictates the downstream verb;
the downstream task may not use a verb that contradicts the class.

| gap_class | Meaning | Downstream verb |
| --- | --- | --- |
| `wired_and_works` | called from production, runs e2e, output reaches a consumer | **govern** into waist (provenance) — never "build" |
| `wired_but_ungoverned` | output reaches a surface but bypasses producer-root | **govern/repair** the flow; laundering finding |
| `wired_but_rotten` | called, but fails / deadline-adapter on real input | **repair** the asset first |
| `built_not_wired` | exists, never called from production | **wire** it (the cheapest real gain) |
| `contract_without_producer` | type/contract exists, nothing emits it | **build** the producer (genuine new code) |
| `producer_without_consumer` | emits, but nobody reads the output | **wire** the consumer |
| `partial` | works for pinned scope, not general | **extend** within budget |
| `missing` | genuinely absent | **build** (genuine new code) |

The honest answer to "if everything exists why doesn't it work" will, for almost
every asset, be `built_not_wired`, `wired_but_ungoverned`, or
`contract_without_producer` — not `missing`. The census proves which.

### The three sub-censuses (each fills rows of the one artifact)

- **Foundry method census.** For each registered method on the pinned route, run a
  smoke against a minimal real panel; fill execution_status with the run result,
  not the registry's truthfulness label. Report executable-on-real vs registered
  counts.
- **Fabric connector census.** For each connector id the pinned route's bindings
  resolve to (worldbank.wdi, ckan.resource, unesco_uis, socrata, rest.json, sdmx,
  eurostat, …), one integration smoke (real fetch in an optional network suite +
  replay fixture). Report honest "executable bindings" count vs the 42k
  `transport_ready` estimate — the gap is the finding.
- **Scientist DAG node census.** Two parts. (a) Run `run_policy_design_workflow`
  on the pinned case; map each node → execution_status + the bundle it persists +
  output_destination. (b) **Trace the existing production invocation**:
  `run_lifecycle.py` calls `run_experiment(state_payload, ...)` at line 1408 —
  record exactly what that call currently produces, where its output goes, and
  whether it reaches a surface / G5 route or is dropped. This determines whether
  GY-2 is `govern` (it reaches a surface) or `wire` (it is dropped).

### Seed findings (verified 2026-06-13 — extend, do not redo)

These rows are pre-filled from this conversation's verification. The census must
*confirm and complete* them (fill execution_status by a real run), not re-derive
or contradict them silently:

| asset | verified fact | provisional gap_class |
| --- | --- | --- |
| scientist DAG | `run_experiment` called at `run_lifecycle.py:1408` | wired — destination UNKNOWN (must trace) |
| RetrievalService catalog | built at `run_lifecycle.py:223` + `nl_pipeline.py:4290` with **no** `dataset_catalog` | `built_not_wired` |
| `DatasetCatalogGraph.search_datasets` | canonical hnsw+text, `data_forge/.../search.py:242` | canonical; `built_not_wired` into runtime |
| fabric `SemanticCatalogIndex` (hashing-BOW) | runtime semantic path | `duplicate_of` the canonical engine |
| `DataNeedSpec` + `DataNeedExtractor` | exist in `scientist/agent` (NL→DataNeed) | contract present |
| `RequiredDataSpec` | foundry id_engine contract | `contract_without_producer` for the DataNeed bridge |
| lex `HierarchicalPolicySearchAdapter` | called by node `run_hierarchical_policy_search` | `wired_and_works` (into DAG) |
| `scientist/adapters/{foundry,fabric}_bridge.py` | engine-side ports (DAG→engine) | canonical engine-side adapters |
| ~1184 `reducer_provenance_missing` (g2..g8) | legacy artifacts lacking provenance | each is a census target → demote or provenance |

**Done when:** every Asset Registry row and every pinned-route-touched module has a
census row with `execution_status` filled by a **real run** (zero rows left at
`unknown` or existence-only); every row has exactly one `gap_class` and a
`recommended_gy_action` consistent with it; the duplication map names the canonical
implementation per capability (search engine, memory, calibration); the artifact
is committed and passes a census-completeness check (a small validator that fails
on any `unknown`, any verb/gap mismatch, or any asset reaching authority without
provenance). The census is the single source of truth the re-spec gate and every
later GY task cite by row.

## GY-0.5 - Re-Specification Gate (rewrite GY-1..GY-7 from the census)

**Hard stop after GY-0.** Before any wiring, re-derive the downstream tasks from
the census, because the census will move tasks between verbs (it already moved
GY-2 from "build" to "govern" and GY-3 from "invent type" to "reuse type" mid-
review — expect more). Do not proceed to GY-1 on the current task text; proceed on
the re-spec.

Required:

- Each of GY-1..GY-7 is rewritten to cite the census row(s) it acts on and their
  `gap_class`, and its verb must match the class (a task that says "build" on a
  `wired_and_works` row is rejected and rewritten to "govern").
- Tasks the census proves already done are **deleted** (with the census row as
  proof), not executed.
- Pieces the census proves `missing` or `contract_without_producer` get **new**
  tasks with explicit "genuine new code" scope — the only places GY is allowed to
  build.
- A `wired_but_rotten` finding inserts a repair task **before** its governance
  task; governance of a rotten asset is forbidden.
- The re-spec is recorded as a diff against this plan
  (`layer3_gy_respec_note.md` or an edit to this file with a changelog), reviewed,
  and only then does GY-1 (renumbered if needed) begin.

**Done when:** every downstream GY task cites a census row and a matching verb;
no `build` verb survives on an asset the census classified as already-present;
the re-spec diff is committed; the census has zero `unknown` rows.

## GY-1 - Fabric Catalog Wiring (the cheapest capability gain)

Wire the real L1 catalog into the runtime retrieval path. Today both production
`RetrievalService` constructions
(`runtime/http/services/control/run_lifecycle.py`,
`.../nl_pipeline.py`) pass no `dataset_catalog`, so runtime resolves against ~3
curated contracts instead of 56.8k bindings, and uses hashing-BOW instead of the
real hnsw engine.

- Pass `dataset_catalog=DatasetCatalogGraph(<production L1>)` (lazy, read-only) to
  both constructions; demote the curated dir to a pin/override layer.
- Route the fabric semantic path to `DatasetCatalogStore.search_by_vector`
  (hnsw); demote/delete `SemanticCatalogIndex` hashing-BOW or mark it
  `bounded_surrogate` for curated-only.
- License gate: build `FetchPlan` rights from L1 `access_license` (a G1
  conformance requirement currently unenforced in the fetch path).
- Freshness: compare source watermark to catalog snapshot at fetch time; emit
  staleness into search-health (T7), not a perpetual fresh pass.

**Done when:** a pinned-construct `DataNeed` resolves through the real catalog to
an executable `FetchPlan`; production search-health names the canonical corpus
path + snapshot hash (GX Task 2 contract); the GX free-growth mutation test runs
against the real catalog, not a temp store only.

## GY-2 - Govern the Existing Design-DAG Output (reframed GX Task 8)

**The DAG is already invoked in production** (`run_experiment` at
`run_lifecycle.py:1408`); foundry/fabric are already reached via
`scientist/adapters/foundry_bridge.py` and `fabric_bridge.py`. So GY-2 is **not**
"build a DAG adapter" — that would build beside a live path (the G1-hollow trap).
GY-2 governs the output of the existing invocation into the waist. Start from the
GY-0 census of where that output currently flows.

- **Govern, don't rebuild.** Take the bundles the existing `run_experiment`
  invocation already persists (`build_literature_prior` /
  `reconcile_causal_graph` → world-model/causal evidence; `run_causal_readiness` +
  `counterfactual_identification_gate` → identification status; `run_simulation` +
  distributional/welfare/uncertainty → `ForecastSupport`, rung 5
  `simulation_only`; `run_metric_validation` → calibration evidence) and route
  them through the resolver + reducers into G2/G3 port contracts. Do not
  re-execute the DAG behind a new wrapper.
- Reuse `ir/analytics` contracts as the port vocabulary; do not re-declare types
  in `runtime/quality`.
- DAG internal gates (judge stack, candidate funnel, normative arbitration) are
  engine-local; they do not satisfy a waist authority slot. If the census shows
  the existing invocation already treats a DAG verdict as a surface, that is a
  laundering finding to fix, not a flow to bless.
- Producer-root: every bundle resolves to its measurement ancestry or is marked
  candidate-only. A `calibrated` maturity is reducer-only with measurement-rooted
  calibration evidence and non-zero denominator.

**Done when:** the existing pinned-case `run_experiment` output is governed into
resolver-clean `ForecastSupport`/analytics ports with measurement-rooted
provenance; no second DAG execution path was created; a no-edge / no-calibration
pinned case still fails forecast admission; a synthetic DAG bundle without
measurement ancestry is rejected by the GX validator; the corresponding
`reducer_provenance_missing` entries for g2/g3 leave `expected_red_checks`.

## GY-3 - Acquisition Loop (RequiredDataSpec → DataNeed)

Close the demand-pull loop so a gap routes to acquisition (ladder rung 7) instead
of bare abstention. **Reuse the existing demand contract; do not invent a DataNeed
type.** `scientist/agent` already has `DataNeedExtractor` (Mock + LLM) producing
`DataNeedSpec` from a `ProblemFrame` — that is the NL→demand source. `foundry`
already emits `RequiredDataSpec` from its ID engine. GY-3 adds the *second*
source, not a new type.

- Add a producer that maps `foundry` ID-engine `RequiredDataSpec` (emitted on
  `ORACLE_NEEDED` / hedge) into the **existing** `DataNeedSpec` contract — an
  identification-gap source alongside the existing NL source.
- Route the `DataNeedSpec` to fabric (GY-1) for fetch, or — when no source
  exists — to an `AcquisitionPlanRecord` with cost (rung 7).
- The acquisition plan is a `plan`, never evidence; it carries a producer-root of
  `external_request` (the demand) plus the measurement gap that justifies it.

**Done when:** the pinned-case identification gap produces a `DataNeedSpec` via
the new source that resolves either to a fetch (GY-1) or to an
`AcquisitionPlanRecord` with a named missing distribution and cost; G5's
`grounded_abstention` cites a real acquisition plan instead of an authored
demand-pull string; no parallel DataNeed type was created.

## GY-4 - G6 over the Existing Agent (reframed GX Task 10)

Subordinate the `scientist/agent` platform; emit an event-backed orchestration
audit. No synthetic rejected tools/branches/evidence.

- Build the G6 audit from traced tool-loop events (event ids, selected/rejected
  tool calls, selected/rejected candidate refs, resolver outcomes).
- No tool loop → `not_measured` or typed blocker; never a populated synthetic
  audit (the prior `rejected_tool_names=("unbounded_web_search",)` constant is the
  banned pattern).
- Selected evidence refs resolve through the shared resolver before counting;
  demand-pull records are persisted producer outputs (GY-3), not inline refs.

**Done when:** a real agent run records its exact tool-loop events; a no-client
run blocks with no synthetic memory; G7/G8 cite G6 demand-pull health only when
the audit is event-backed.

## GY-5 - Design-Space Knob Provenance (folds into GY-2)

**Lex is already subordinated into the DAG**: node
`run_hierarchical_policy_search` already calls `HierarchicalPolicySearchAdapter`
+ `TemporalInterventionSequencer`. So there is **no separate "subordinate lex"
task** — that would double-count what the DAG already does. GY-5 is a thin
provenance check folded into GY-2, not its own construction:

- Verify the knob vectors flowing through the GY-2 adapter resolve their source to
  L6 data (`lex_intervention_map` / `intervention_knob_dictionary`), **not** code
  literals (Rule 12). If any knob is a Python constant, that is a GX runtime-literal
  lint finding to fix.
- Verify welfare/social-weight choices surface as S8 value-choice /
  `HumanDecisionRecord` inputs (P26), never code constants.
- Candidate design records (structure + parameters + phasing) stay candidate-only
  with measurement/`external_request` producer roots until A grounds them.

**Done when:** the GY-2-governed candidates carry lex-knob provenance to L6 data
with effective-time windows; no design knob is a runtime literal; the lex path
created no second subordination outside GY-2.

## GY-6 - L2 Growth (scholar literature provider) — follow-on

Add an OpenAlex/Crossref provider to the existing `scholar/search` pipeline so L2
(the scarcest corpus, 7.9k claims) grows for the pinned topic. Extraction is
`derivation` over documents (`measurement` root), span-grounded, with a calibrated
extractor (sampled human audit; accuracy enters provenance). This is the cheapest
real capability gain after GY-1 but is **follow-on**: GY's minimal set proves the
mechanism on the existing corpus first.

**Done when:** a credit-guarantee→firm-survival literature query ingests
span-grounded, design-quality-tiered claims into L2 via the existing pipeline with
zero new search engine; extractor accuracy is measured and recorded.

## GY-7 - DAG-Route Outcome Run (the value check)

The GY analogue of GX Task 12: run the pinned case through the **subordinated**
route and persist the reducer-produced outcome.

```text
pinned request
-> GY-1 canonical fetch  -> GY-2 DAG bundles -> ladder descent (rungs 0..7)
-> resolver + producer-root validation -> G4/G5 reducers
-> reducer-produced outcome + rung reached + (if blocked) acquisition plan
```

Allowed outcomes (reducer-produced, measurement-rooted): `grounded_limited`,
`grounded_abstention`, `search_ceiling_repair_required`, or a typed blocker with
the exact missing producer/corpus/method ref. A real `grounded_limited` is not
rejected merely because the GX baseline was a blocker — that is the capability
gain GY exists to produce. Forcing useful-design credit is forbidden.

**Done when:** the pinned case produces a reducer-authored outcome that differs
from (or honestly equals) the GX baseline, with every reducer's input hashes,
output hash, producer roots, and rung reached recorded and replayable; the GX
validator passes on the new artifacts.

---

## Execution Order

**GY-1..GY-7 below are PROVISIONAL until GY-0.5 rewrites them from the census.**
The sequence is:

1. GY-0 census (three sub-censuses; parallelizable, read-only). Gate everything on
   it. The scientist-DAG census also traces the existing `run_experiment` flow.
   No row may stay `unknown`.
2. **GY-0.5 re-spec gate (hard stop).** Rewrite GY-1..GY-7 from census gap-classes;
   delete proven-done tasks; add tasks for `missing`/`contract_without_producer`;
   insert repairs before governance for `wired_but_rotten`. Commit the diff.
3. GY-1 fabric wiring (cheapest gain; needed by GY-2/3/7) — verb confirmed by census.
4. GY-2 govern the existing DAG output (only for census-green nodes; rotten nodes
   → repair first). GY-5 (knob provenance) folds in here.
5. GY-3 acquisition loop (reuse `DataNeedSpec`).
6. GY-4 G6 agent audit.
7. GY-7 DAG-route outcome run.
8. GY-6 L2 growth (follow-on; may run any time after GY-1).

The numbers above are the *expected* order; GY-0.5 may reorder, drop, or add steps.
Trust the re-spec, not this list, once the census exists.

Stop rules: a census-red asset converts its subordination task into an
engine-repair blocker — record it, do not stub past it. A census that finds an
already-wired flow (`run_experiment`, lex-in-DAG) converts its task from "build"
to "govern the existing flow" — building beside it is forbidden (Asset Registry,
rebuild-over-subordinate). Any GY task whose output cannot pass the GX validator
is not done. Budget overrun triggers a stop-and-review note before more wiring.

## Global Acceptance Bar

- GX provisional Task 12 outcome existed before GY started (satisfied 2026-06-13).
- The census artifact (`layer3_gy_engine_census.json`) is committed with **zero
  `unknown` rows**, every row execution-verified (not label-verified), every row
  with one `gap_class` and a matching verb; it passes its completeness check.
- The re-spec gate (GY-0.5) ran: GY-1..GY-7 were rewritten from census gap-classes,
  the diff is committed, and no `build` verb survives on a present asset.
- Every GY artifact passes the GX hardening validator (reducer provenance,
  producer-root chain, resolver, runtime literal lint).
- The `expected_red_checks` count is driven down: every `reducer_provenance_missing`
  entry GY touches (g2/g3/gl/g6/g7) leaves the catalogue via real provenance or is
  honestly demoted. GY is not complete while it leaves catalogued red it claimed to
  resolve.
- The three engine censuses are committed; each subordination task cites them, and
  the scientist-DAG census records where the existing `run_experiment` output flows.
- Runtime `RetrievalService` resolves against the real L1 catalog; no production
  search-health passes as canonical while running on a surrogate.
- A subordinated DAG bundle is authority only with a measurement-rooted chain.
- The pinned case has a GY-7 reducer-produced outcome with rung reached recorded.
- No parallel engine/pipeline/agent/DataNeed-type was built where an Asset Registry
  entry exists; already-wired flows (`run_experiment`, lex-in-DAG) were governed,
  not duplicated.
- Ladder descent is real: a rung-0 no-hit routes to k+1 or to an acquisition plan,
  never to bare abstention.

## Required Closeout Evidence

- `layer3_gy_engine_census.json` (one row per pinned-route asset: existence,
  reachability, execution_status by real run, dataflow, authority, gap_class,
  verb), its completeness-check validator, and the duplication map (canonical impl
  per capability). Includes the existing-`run_experiment`-flow trace.
- `layer3_gy_respec_note.md` — the GY-0.5 diff rewriting GY-1..GY-7 from the census.
- Fabric catalog-wiring report (real-catalog resolve + canonical snapshot hash).
- DAG-output governance report with producer-root chains and lex-knob provenance
  (GY-2 + folded GY-5).
- Acquisition loop report (`RequiredDataSpec`→existing `DataNeedSpec` /
  `AcquisitionPlanRecord`).
- G6 event-backed audit report.
- GY-7 pinned-route outcome report (reducers, hashes, roots, rung reached).
- `expected_red_checks` delta report: which catalogued red GY resolved/demoted.
- GX validator pass over all GY artifacts.

## Relationship To GX And The Roadmap

GX guarantees honesty (the waist cannot lie); GY grows capability (the engines
reach the waist). GX completes at an honest blocker; GY is the first move from
that blocker toward a grounded design — still bounded, still ladder-typed, never a
universal claim. The constitution's open questions T1 (groundable at acceptable
cost?) and T6 (does demand overcome abstention inertia?) become empirically
answerable only after GY-7 records a real ladder descent on the pinned case.
