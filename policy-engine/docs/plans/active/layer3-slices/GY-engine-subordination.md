---
plan_id: layer3-gy-engine-subordination
title: "GY — Universal Execution Topology + Engine Subordination (blackboard control plane over an artifact graph)"
type: slice-plan
status: draft
created: 2026-06-13
revised: 2026-07-08
revision: 15
slice: GY
scope: cross-slice
depends_on:
  - docs/system-design-decisions/policy-design-execution-topology.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md
  - docs/system-design-decisions/policy-design-best-in-class-operating-model.md
  - docs/system-design-decisions/policy-design-search-target-spec.md
  - docs/reference/policy-design-search-RACE-HOG-PODS-v3.2-spec.md
  - docs/plans/active/layer3-slices/GX-universal-free-growth-runtime-hardening.md
  - docs/reference/policy-design-case-failure-patterns.md
  - architecture/policy_design_case/layer3_gy_task0_audit/  (Task 0 audit campaign — DONE)
floor_id: layer3_grounding_subordination
metric: layer3_engine_subordination
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
center: docs/system-design-decisions/policy-design-execution-topology.md
---

# GY — Universal Execution Topology + Engine Subordination

## 0. What changed

**Revision 1 (2026-06-14).** Task 0 (the audit campaign) is complete and moved the
center of gravity from "run the static `scientist_policy_design` DAG" to a **universal
execution topology**: a **blackboard control loop over a content-addressed artifact
graph**, engines subordinated as **Operations** behind a **two-ring waist**, the three
legacy workflows demoted to **playbooks**. Read the center doc
(`docs/system-design-decisions/policy-design-execution-topology.md`) first; this plan
is the big detailed build plan.

**Revision 2 (2026-06-14).** Applied the internal-review fixes:

- **Blocker:** added the **production-trigger** task (GY-B2) so the loop is reachable
  in production — without it the loop would repeat the Task-0 "built but untriggered"
  failure.
- **Coverage:** added the **artifact-lifecycle** task (GY-M) for the unregistered
  GY/loop generated/public-surface family + GX-reducer case-parameterization.
- **Sequencing:** moved the **anytime-exit core (GY-H)** ahead of acquisition (GY-E),
  which forward-depended on it (VOI + `acquisition_required`).
- **Size:** split the three mega-tasks into ~equal units — GY-C → C1/C2/C3
  (subordination / **spine-repair, separated per stop-rule** / foundry-consumption),
  GY-D → D1/D2/D3, GY-F → F1/F2/F3, GY-A → A1/A2.
- **Coherence:** the two rings are **field-level write-permission classes**, not type
  sets (Ring-2 fields are embedded in Ring-1 types); the `grade` enum is **reconciled
  with the evidence ladder** (added `derivation_near_lossless`, `bounds`);
  `CertifiedOperationEnvelope` is **operation-declared (Ring 1) + verifier-confirmed**;
  **VOI ownership** is assigned to GY-H (GY-B exposes only the ranking hook and a
  degenerate exit).

**Revision 3 (2026-06-14).** Closed seven residual risks (see §3.5 + the marked
edits): hard cut-lines for Vertical Slice 0 (anti-P13 contract gravity); a concrete
`pdc` ownership/import map (most of the waist already exists in `pdc/_impl` — reuse, do
not re-declare); explicit Operation-discovery sources + conformance criteria; a
single-authority-path transition rule in GY-B2; the `AuthorityBoundary` grade **split
into two orthogonal axes** (`evidence_kind` ⟂ `decision_grade`) with worked mixed
examples (§13); a governed benchmark artifact for GY-D3; and GY-M split with the
lifecycle registration promoted to a **Phase-0 hard gate** (GY-M1).

**Revision 4 (2026-06-15).** Tightened the execution details before implementation:
production proof now requires the actual durable path
`enqueue_job -> ControlWorker -> _execute_workflow -> WorkspaceLoop -> persisted
SearchExitContract`; Slice 0 now distinguishes active operation classes from
fail-closed registry stubs; task and acceptance wording now use the two-axis
`evidence_kind`/`decision_grade` semantics; GY-F now requires a complete
406 candidate-positive inventory, CAS digest/dedup/tamper/GC proof, explicit
time-role envelope, and repo-wide secret/PII scans across DAG bundles, connector
payloads, and raw artifact routes; §3.5.4 adds proof-packet schemas so implementers
do not invent the audit shape mid-flight.

**Revision 5 (2026-06-15).** Closed the remaining executor-ambiguity seams: A's
promotion step now has a deterministic Slice-0 `AuthorityBoundary` derivation rule and
an `AuthorityDerivationTrace`; `OperationContract.authority_transform` is explicitly a
Ring-1 hint, never trusted authority; Slice 0 now runs two fixtures (one
catalog-groundable, one search-ceiling/acquisition-heavy) with a deterministic
`BIND -> ESTIMATE -> VERIFY` seed trajectory rather than an agent/playbook; terminal
precedence is specified; agent-provided VOI/selection inputs are candidate-only and
normalized by GY-H; B2 now includes job-status honesty before F1; ConstraintStore
producers are named; and the plan states plainly that Slice 0 proves the loop and
grounding/abstention branches, not real policy-design synthesis.

**Revision 6 (2026-06-15).** Added the anti-simplification audit. Slice 0 now uses a
committed `Slice0FixtureManifest` instead of a vague "World-Bank style" label; the
positive Slice-0 terminal is estimate-scoped only; `BudgetVector` is constrained to a
minimal subset in Slice 0; `evidence_kind` is defined as a partial order with explicit
meet semantics instead of a fake total chain; and §3.6 adds a
capability-preservation matrix so implementation must consume the real
catalog/connectors/foundry/lex/agent/surface capabilities and close Task-0 findings
substantively, not by labels.

**Revision 7 (2026-06-15).** Added the **phase-0–2 implementation-review corrections**.
The review of the partial build found three recurring build-hygiene failures, now
formalized as register patterns P27/P28/P29
(`docs/reference/policy-design-case-failure-patterns.md`):
**P27 parallel re-implementation** beside live owners (`Slice0SearchLedger` vs canonical
`SearchLedger`; a second `AcquisitionPlanner`; the lex-bounds rule duplicated in
`gy_spine_repair.py` and `policy_design/search.py`; two fixture catalog graphs), plus the
dual symptom of a 2674-line `gy_loop.py` god-file;
**P28 un-strangled legacy** (the `require_explicit_parameter_bounds=False` default still
launders `None→0.0`; zero file deletions on a "subordinate the engine" branch; loop and
static DAG both live); and
**P29 authorial proof** (`ProductionLoopRunProof` hand-authored with placeholder ids and a
shape-only validator; F4/F7 "closed" on a trivially-separable 2-record catalog corpus); and
their upstream enabler **P30 provenance-named modules** (the `gy_*` files are named for the
plan, not the function they own, so the owner-first grep misses them and parallel files get
created — `gy_loop.py` is really `workspace_loop.py`).
§1 adds binding rules 8–11; §3.5.5 is the binding remediation + forward discipline
(**P28 strangle is the load-bearing one**, **P30 naming is the cheapest defense against P27**);
§3.5.4, §9, §10, and §11 are tightened to

**Correction status (2026-06-15).** The first remediation pass closed the highest-risk
P27/P28/P29 regressions with executable guardrails: `ProductionLoopRunProof` is now
recomputed through the durable worker validator, `_InMemorySlice0CatalogGraph` was removed
in favor of `build_slice0_fixture_catalog_graph`, `Slice0SearchLedger` extends canonical
`SearchLedger`, GY acquisition delegates to `runtime/quality/acquisition_planner.py`,
`gy_spine_repair.py` delegates lex-bounds checks to `policy_design/search.py`, and
`require_explicit_parameter_bounds` defaults to the explicit-bounds fail-closed path.
Remaining debt: `gy_loop.py` is still too broad, representative F4/F7 catalog evaluation is
not yet complete, and explicit legacy-shadow inferred-bounds paths still need final
sunset/deletion after their owners migrate.
enforce them. This revision does not change the topology — it makes the build do the
subordination it already promised instead of layering on top of legacy.

**Revision 8 (2026-06-24).** Added **Phase 5 — B-on-A Generation Cycle** before the
Deep Workability Verification close (renumbered to Phase 6). A deep two-lens repo
investigation found that the generative organs already exist as **decoupled parallel
worlds** — the Scientist `scientist_policy_design` DAG (plans NL, generates candidates,
hierarchical search), the foundry causal/optimization engine (econml/dowhy/statsmodels;
cvxpy/pymoo), and the layer-2 **shadow** design search (real refinement discipline but a
*hardcoded* candidate) — none subordinated to A and none in a cycle (`run_fixture`/
`run_intent` are single-pass, fixture-driven, `descriptive_only`, acquisition-as-terminal).
The heavy machinery (causal, optimization, generation, the `engine_simple`/legacy-LangGraph
cyclic engine) is **already a dependency and already used** — so the phase is **reuse +
subordination + promotion + acquisition execution + NL coupling**, not a from-scratch
build, with **no new heavy dependency** (the one risk: econml/dowhy gated `python<3.13` —
a GY-N0 availability gate). The phase is governed by the **no-parallel-worlds law** (every
asset used-as-is, reworked, or deleted — never left parallel), enforced by the GY-N0
disposition ledger.

**Revision 9 (2026-06-24).** Reformulated Phase 5 against the completed **GY-N0 five-pass
code investigation** (`architecture/policy_design_case/layer3_gy_n0_investigation.md`). The
investigation proved the cycle is **predominantly REWORK / WIRE over real organs** (generation,
causal, value, Bayesian, transport, VOI, joint-simulation, world-substrate organs all exist and
are real under Python 3.14) with a small set of **narrow BUILD-NEW bridges**, and corrected the
world-model status from greenfield to **UNIFY_EXISTING** (`fabric/world` epistemic facts +
foundry `GlobalState`/NCM/GCM mechanisms + SKG priors + `DataSnapshot` binding need one
`WorldModelRecord` bridge). Phase 5 is now **GY-N0..N10**: GY-N0 = disposition ledger +
consumption validator; GY-N1–N3 = the three **foundation bridges** (`DesignProblem`,
`InterventionAtomBinding`, `WorldModelRecord`) that precede the cycle because the value gate
must name its world version; GY-N4–N10 = the cycle (generation-under-A with a model-profile
preflight, the joint-simulation horizon controller, the cycle controller, closed acquisition,
value-as-gate, in-cycle promotion, depth-N). Added **Phase 6 — Deployed-Policy Learning Loop**
(GY-O1..O3), the one genuinely greenfield horizon where the world model *grows* from observation
(two contours on the firewall; reuses the real posterior / drift / FDR / feedback primitives).
Renumbered Deep Workability Verification to **Phase 7**. Tasks are scoped to roughly comparable
work. Stay on Python 3.14 (DoWhy/EconML/CVXPY unavailable and not required).

**Revision 10 (2026-06-25).** Added the **GY-S production-data substrate lift + free-grow**
foundation block to Phase 5 (after GY-N3), once the build surfaced that PolicyOS already holds
~32GB of richly preprocessed production data — L1 DCAT catalog (137k datasets, 3.7M
observations), L2 Scholar KG (7.9k curated causal claims, transport scores, 62k parameter
estimates), L3 Lex KG (6M provisions, 374k thresholds, 156k amendments), L4 Ukraine corpus
(8.8M agents + firm/distress/budget panels), L5 calibration internals (trust-tier /
identification-mode / schema-regime registries), L6 agent-sim bundle (intervention knobs,
lex→knob map, observation→method manifest) — most of it **not yet lifted to runtime authority**.
The world model and the cycle must ground / simulate / value against this REAL substrate, not toy
fixtures (the GY-N3 empty-world finding is the canary). GY-S0 builds a **free-grow substrate
registry** (content-addressed, versioned; a new source / family registers with no code change),
and GY-S1–S3 lift the data-state (L1/L4/L5), knowledge (L2/L3), and intervention (L6) substrates
to runtime authority — wire-existing, not rebuild. The GY-S0 registry is the shared growth
mechanism for GY-N7 acquisition and the Phase-6 learning loop, so the world model expands as data
arrives.

**Revision 11 (2026-06-27).** Adopted the externally authored **formal target
specification for policy-design search & selection** — `RACE-HOG-PODS v3.2` — registered as a
decision record (`docs/system-design-decisions/policy-design-search-target-spec.md`; verbatim
spec archived at `docs/reference/policy-design-search-RACE-HOG-PODS-v3.2-spec.md`). The spec is
the **formal twin of Phase 5** (it converged independently on our B-on-A firewall) and is the
**target architecture, not a from-scratch build**: its greenfield §27 build plan is **superseded**
by this plan's subordination mapping under the no-parallel-worlds law. The adoption is threaded
**at and after GY-S1** (the live task) and leaves the done backbone (GY-N0–N3, GY-S0) untouched:
(a) the **GY-S block** gains the credal-component → L1–L6 mapping + **set-valued value** +
CalCert-scope / DataTrust contracts (the spec's credal state IS our substrate, and this is exactly
the GY-S1 proxy-bounds fix); (b) a new foundation contract **GY-N-V `ValueOuterSet`** (the typed
set-valued value carrier S1/N8/N6 consume — landing with GY-S1); (c) bar-raises on **GY-N4
(firewall + surrogate), N5 (equilibrium-semantics taxonomy), N6 (four stratified fronts), N7
(eight acquisition families + affected-region revalidation), N8 (value-outer-set + honest
dominance + six eval modes), N9 (obligations compiler + δ-confidence ledger)**; (d) two new cycle
tasks **GY-N11 (honest confidence ledger)** and **GY-N12 (model-revision epochs + stale certs +
OpenWorldRisk, on L3 amendments + L5 schema-regime)**; (e) an **EvalSafety gate + evaluation-mode
ladder** bridging Phase 5 → Phase 6; and (f) an explicit **Phase-5 deferred list** (portfolio-as-
design, CHHV solvers, scenario-tree VOI, EXP3 meta-controller, full MCTS — adopt the contract now,
implement when a certified frontier exists). Two honest caveats carried from the decision record:
the δ-safety theorem is **conditional on obligation completeness + validator soundness** (our P29
regress — formalized, not closed), and joint-credal dominance is generally intractable so the
system lives in the **marginal-interval fallback** with a strict `unknown`/incomparable discipline.

**Revision 12 (2026-06-28).** Codified the **substrate / binding lift completeness gates** (new
§3.5.6) distilled from the GY-S build saga (S1/S2/S3 each took many adversarial rounds). The
recurring failure was a **shell that passes its own narrow probes** — coverage green on a curated
subset; authority **supplied, not derived** (for S3 it escaped one level deeper each round:
caller-supplied → hardcoded code-table → hand-injected into git-ignored data → a tracked JSON the
runtime merely *trusted*); the contract exercising only the happy-path. The four binding gates —
**(1)** full-denominator coverage, **(2)** fail-closed on a fake/novel input (owner-validation, not
trust), **(3)** data-only free-grow (generic, not enumerated), **(4)** the contract mutates the
**decisive** validation property (`P29`) — are now front-loaded into every impl/audit prompt and
`Done when` for any lift/resolve/bind task (the GY-S block + the cycle tasks N2/N4/N7/N8/N9). They
exist so the implementer builds to them on the first pass rather than rediscovering them through
rounds.

**Revision 13 (2026-06-30; restored 2026-07-08 — the original entry was lost from the working tree
before commit).** Adopted the **Causal Grounding Firewall (CGF)** as the third external target spec
(grounding layer; data = GY-S, grounding = CGF, search = RACE-HOG-PODS) after N6 production wiring
exposed N4's exact-name-match grounding. Added the **GY-CG block** (CG0 reference audit + credal
reference, CG1 JTCG+CRG relation engine — keystone, CG2 CAAB conservative bind gate, CG3 free-grow
admission, CG4 phrasing-invariant defense, CG5 active grounding, CG6 benchmark) with CGF hooks on
N2/N4/N6/N7/N8/N9/N11/N12. Decision doc:
`docs/system-design-decisions/policy-design-causal-grounding-firewall.md`; archived spec in
`docs/reference/`. **Status: the entire CG block executed and closed honest (2026-07-03).**

**Revision 14 (2026-07-04; restored 2026-07-08 — same loss).** Codified the **compute-economics
gates** (new §3.5.7, E1–E10) distilled from the GY-N4 saga (a correct closure cost ~4h because the
full world was rebuilt in every validator/probe/unit run), plus the **GY-INFRA-1** build task
(content-hash world cache proven byte-identical cold≡warm + one-process sweep-runner + heartbeats)
and compute-economics riders on N5–N10. **Status: GY-INFRA-1 executed and closed (warm closeout
sweep ~21min vs historical ~4h).** §3.5.7 binds every remaining task with expensive shared state or
a live provider (N9–N12, N10a, O0–O3, V-battery closeouts).

**Revision 15 (2026-07-08).** The universality audit after GY-N8 closed. N8 landed honest but as a
**panel/DID + governance-domain vertical** (six fix rounds tunneled it to one scenario); its two
hardcodes (governance transport covariates; panel-only S10 calibration credibility) are recorded as
**universality debt inside GY-N10** (see the N10 body). This revision adds the systemic guard so the
remaining tasks do not repeat the pattern: (a) new **§3.5.8 domain/method-family genericity gates
(U1–U4)**, front-loaded into every task downstream of the first vertical; (b) **universality riders**
on N9 (obligations compiler total over the typed taxonomy; unseen-shape probe so N9 built against
today's panel receipt does not need rework at N10), N11 (ledger generic over obligation class ×
certificate instrument), N12 (epoch boundaries derived from the FULL schema-regime/amendment data,
never the enumerated ukraine changepoint), O0/O1 (typed domain-pack-extensible vocabularies), and V3
(per-domain terminal distributions + a non-panel case + an unseen-third-domain smoke); (c) a new
**GY-N10a — second-domain substrate pack** (data-only free-grow proof) before N10, because the
second domain's levers/writability/covariates do not exist in the Ukraine-centric L6 substrate and
must arrive via data + N7 acquisition, not code; (d) N10's "≥2 distinct domains" sharpened with an
explicit **distinctness criterion** (two Ukraine-economics variants do not count).

**Revision 16 (2026-07-16).** GY-N10 closed **GO** (capstone
`architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json`, frozen at
ce847b9f2 on the N10 worktree branch, embedded proof recordings; final architect audit in
flight): the cycle is contract-generic and degrades through honest typed terminals from plain
language on three domains — but all three terminate `acquisition_required` with three distinct
evidence classes (`owner_acquisition_route` / `estimand_binding_refusal` / `owner_data_gap`),
and Fork B held (13,092-relation CG1 census, zero admissible positives). The binding constraint
is now **measured, not suspected: substrate, not machinery** — and the N10 recon found the
acquisition layer is **built but dark**: `dataset_catalog.duckdb` carries 56,846
metric→connector bindings (41,976 executable) + 3.7M local L1 observations over 101 canonical
vars; fabric has 20+ real connectors, `run_orchestrated_ingestion` (fetch→CAS→snapshot), and a
RetrievalService dataset-catalog lane that is never wired; N7's `_capture_fabric` is a probe
that never executes a fetch plan. This revision converts the measurement into the next wave +
the process lessons N10 paid for: (a) **NEW GY-N13a (acquisition-layer reality census) +
GY-N13b (acquisition executor — the world grows)**, closing one capstone route end-to-end and
the two typed N7 infrastructure residuals; (b) new **§3.5.9 live-carrier conformance gates
C1–C5** (the compiler saga generalized to every live LLM/data carrier); (c) new **§3.5.10
recompute-not-pin** (the expectation-transplant class fired three times in N10 — now a named
binding rule, with the earned-NO-GO stop-law refinement and batch-fix→single-ripple); (d) new
**§3.5.11 projection-scoped provenance binding** (ripple containment for the deepening frozen
chain); (e) riders — N11 accounts refusal/acquisition instruments as first-class ledger rows
(kills the measured vacuity risk), N12 admits acquisition events as live epoch-boundary
sources, O1/O3 consume the N13b executor as the world-growth spine, V3 consumes the N10
capstone's per-domain distributions directly. Execution order after N10: **N13a → N13b → N11 →
N12** — N13 first because world growth + cycle re-entry is the only unproven capability and N10
just paid for all its inputs.

**Revision 17 (2026-07-16).** The data-plane growth consultation (follow-on to Rev 16): how the
connector pool grows, and how **derived data** (a method applied to fetched data — e.g. inflation
adjustment — producing new data that is both a final result and an input to further methods,
alone or in composition) is identified, stored, trusted, and reused. Core decision: **no parallel
dataflow engine** — a derived dataset is an artifact in the EXISTING content-addressed artifact
graph, and a transformation is a subordinated Operation with a recorded envelope. Codified as
**§3.5.12 data-pool growth + derived-data gates D1–D6** and wired into the tasks: N13a gains the
**D2 demand signal** (typed `connector_gap`/`binding_gap` residuals seed a VOI-ranked
source-growth backlog; the liveness census becomes a recurring lane with tier decay); N13b gains
the **`derived` provenance class + derivation certificates**, with the real-terms/inflation
normalization family as the acceptance case (one derivation, two distinct method consumers,
cache-hit reuse, typed `basis_mismatch` refusal); the N12 rider gains derived-staleness
inheritance (input revision → automatic recompute via the certificate-as-recipe); and the **full
transform-planner** (certified transform CHAINS over the basis vocabulary) is carried on the
Phase-5 deferred list — N13b lands only single-transform matching + typed refusal.

## 1. Binding rules (for every GY task)

From the constitution and the execution-topology decision. A change that breaks one
is wrong regardless of test status.

1. **Subordinate, do not rebuild.** The capability exists (engine census). A task that
   builds a parallel engine/pipeline/agent is mis-specified. Engines stay below the
   waist; they enter only as Operations (adapters, pattern `ir_analytics_bridge`).
2. **A leads B; the two-ring waist is the agent boundary — enforced at the FIELD
   level.** Ring-1 fields are candidate/agent/engine-writable; **Ring-2 fields are
   verifier/governance-writable only.** Ring-2 fields are embedded inside Ring-1 types
   (e.g. `ArtifactEnvelope.authority_boundary`, `PortSpec.provided_authority`), so the
   boundary is a per-field write permission, not a type partition. The agent gets full
   freedom inside the loop but **cannot write a Ring-2 field** — "not a self-promoter,"
   enforced by construction.
3. **Fail closed and downgrade.** Missing grounding is a typed terminal or obligation,
   never a silent pass. An Operation emits the narrowest authority boundary it can
   prove: both `evidence_kind` and `decision_grade` are independently capped.
4. **Authority composes to the weakest boundary, on ports.** Realized by the
   port-authority `meet` + the three-stage composition (§7). Never average, never max.
5. **Optimize honesty, never `useful_design_rate`.** Calibration, honest abstention,
   reuse, envelope revision are the objectives; `useful_design_rate` is reported only.
6. **Capability discovered by search, never enumerated** (Rule 12). The Operation
   registry, the formal applicability gate, and corpus search are discovered from
   engine registries + adapter conformance, with replayable `SearchLedger` /
   incompleteness ledgers. No hand-maintained list of methods/constructs/datasets.
7. **Every GY artifact passes the GX hardening validator** (reducer provenance,
   producer-root chain, resolver dereference, runtime-literal lint). A subordinated
   output is authority only with a measurement-rooted producer-root chain.
8. **Owner-first; no parallel re-implementation (P27).** Before creating any new type,
   engine, gate, planner, or fixture, find the canonical owner (§3.5.2 + grep the concept
   root across `pdc/_impl/` and `runtime/quality/`) and **extend it**. A slice/plan name
   (`gy_*`, `slice0_*`) is not a module boundary; new files are only for the genuinely-new
   orchestration contracts in §3.5.2's build-new column. A `build-new` that shadows a live
   owner is wrong even if its tests pass. The dual failure is equally banned: do not pile
   orchestration into one slice god-file.
9. **Strangle, never layer (P28) — the load-bearing rule.** When a task replaces or
   subordinates a path, it must **delete or fence the predecessor in the same change** and
   **flip the default** to the corrected path. A fix gated behind a default-off flag, a
   legacy entrypoint left freely callable, or a branch with zero deletions is not a
   migration — it is a second laundering surface. Every subordination task ships a
   `StrangleReceipt` (§3.5.5). The universal loop must *replace* the static DAG, not sit
   on top of it.
10. **Proofs are emitted and recomputed, never authored (P29).** A proof, benchmark, or
    closure artifact counts only if the real run emits it and its validator re-derives it
    from live code/artifacts and fails on drift. Hand-authored packets (placeholder ids,
    round `…T00:00:00Z` times), shape-only validators, and metrics computed on a
    trivially-separable fixture corpus are laundering, not completion.
11. **Name by function, not by plan (P30).** A module, file, or public symbol is named
    for the capability it owns, never for the slice/plan that birthed it: `gy_loop.py`
    should be `workspace_loop.py`; a foundry-consumption helper belongs in/near the
    foundry owner, not `gy_foundry.py`. Provenance naming is the **upstream cause of P27** —
    it hides the owner so the next implementer cannot find the file they should extend, and
    re-creates it. If a provenance prefix is truly unavoidable, the module docstring must
    name the canonical owner(s) it extends and link related modules so reuse is the path of
    least resistance.

## 2. The center — Universal Execution Topology (summary)

Full statement: `docs/system-design-decisions/policy-design-execution-topology.md`.

- **Unit of state = Artifact** (content-addressed, immutable, provenance-carrying).
- **Unit of planning = Operation** (a coarse verb; internally a `MethodPlan` of
  foundry methods / agent steps / tool calls / human requests — an Operation ≠ a
  foundry method).
- **Workspace = the blackboard**: artifact graph + ConstraintStore + Frontier +
  Agenda + BudgetVector.
- **Two rings = two field-level write-permission classes.** Ring 1 (execution) lets
  the loop run and artifacts enter the shadow frontier; Ring 2 (promotion/honesty) is
  verifier-stamped and required before any promotion / composition / grounded exit.
- **Control loop** (CEGIS/CEGAR-shaped): A writes constraints before generation; B
  proposes operations; the formal gate filters by applicability; RefinementPolicy
  ranks by VOI; A verifies after; failures become typed counterexamples; loop until a
  typed `SearchExitContract`.
- **Two recursions**: problem decomposition (child Workspace → `SubDesignContract`)
  and operation expansion (Operation → `MethodPlan`). Scale-invariant: one Workspace
  for a local tourism policy; a tree of Workspaces (chapters), many cycles each, with
  operations on derived artifacts, for an international-accession program.
- **Migration**: build the loop directly on a minimal vertical slice; legacy is a
  quarry; legacy nodes → `LegacyNodeAdapter` Operations; the three workflows →
  `Playbook` trajectories the loop may follow and deviate from. **The loop is wired to
  a production trigger from day one (GY-B2) so it is never an untriggered path.**

## 3. What Task 0 established (the empirical basis — integrate, do not redo)

Task 0 artifacts live in `architecture/policy_design_case/layer3_gy_task0_audit/`
(16 audits + the coverage matrix + the global review, each with a recomputing
validator; suite green). The plan-shaping findings every task below must honor:

| # | Finding | Source audit | Task it shapes |
| --- | --- | --- | --- |
| F1 | The "~1184 reducer_provenance_missing" meter is stale → 0; baseline outcome = `search_ceiling_repair_required` (not `typed_blocker`) | engine census; GX validator | GY-H; acceptance bar |
| F2 | No production path selects `scientist_policy_design`; 3 static DAGs; variability is D3.2 (missing) | workflow-mode truth | GY-B, GY-B2, GY-C1 (loop + trigger + playbooks; intent→operation, not workflow_id) |
| F3 | Defect is bridge/surface/semantic-test, not absent capability (1/29 chains green) | coverage matrix | whole reframe; task postures |
| F4 | Catalog→fetch never reaches a measurement root (`persist_payload=True` writes 0 CAS; `DataContextMetric` drops root facts) | catalog-fetch | GY-D1 |
| F5 | Connector families not uniform (rest.json/unpd/ukons not execution-ready); replay fixtures are scaffolds | connector-family-truth | GY-D2 (per-connector formal gate) |
| F6 | 16-facet source-contract/`DataRequirementSpec` admission exists but is not orchestrated into FetchPlan | source-contract-admissibility; data-requirement-compiler | GY-D2 |
| F7 | Catalog top-k: construct+scope precision@5 = 0.0; country filters → 0; `similarity=1.0` for all (no calibrated relevance) | P2 | GY-D3 (semantic-adequacy gate + recall@seeds) |
| F8 | Lex node fails on optional-bounds `None→0.0` bug; P25 frontier-laundering risk untyped | lex-frontier-root-cause | GY-C2 (REFINE precondition + frontier provenance) |
| F9 | Governance/validation tail (judge stack) fails fatally on synthetic input; `run_normative_arbitration` outcome re-validation fails — the real shared-spine blocker, masked by lex | workflow-mode truth | GY-C2 (spine-rot repair before governance) |
| F10 | 389 foundry methods registered; `dag_consumed_method_outputs_count=0` (route never consumes a method output) | foundry-breadth | GY-C3 (ESTIMATE/SIMULATE consume real outputs) |
| F11 | Agent roles are runtime-telemetry only; no role-event artifacts; tool-loop off the NL path; KnowledgeToolkit 3/20 tools register | agent-workflow-event-backing; P2 | GY-I |
| F12 | Worker path launders workflow failure (job completes on `fail`; 1408 discards / 6596 captures); CAS has 0 `manifest.authority` and no proven digest/dedup/tamper/GC authority; raw `/artifacts/{id}/content`+`/download`, DAG bundles, and connector payloads require systematic secret/PII scans; time semantics exclude run_workflow/nodes/content; S12 G5 pass refs are authorial (hardcoded payload, don't dereference to S12 objects) | P0; P1; runtime-surface | GY-F1, GY-F2, GY-F3 |
| F13 | 406 candidate-positive statuses all firewall-excluded (`positive_status_count=0`) — diagnostic pass fields are the residual laundering surface and require a full row-level inventory, not only an aggregate count | P0 | GY-F3 |
| F14 | Depth-2 generalization fails: GX reducers pinned to ua-msme `data_home` (not case-parameterized); blocked-input nodes need concrete state reads (`causal_variables` route_omitted, `data_causal_graph` producer_missing, `observational_data_ref` available_elsewhere_not_wired) | P0 | GY-M2 (reducer case-param), GY-C2 (blocked-input producer + ports), GY-G (recursion) |
| F15 | Substrate (core/ir route-pinned; evidence/calibration/obligation/participation as authority ceilings to consume, not infer; evidence-independence = P14 anti-inflation) | substrate-package-capability | GY-A2 (ir ports), GY-C3 (ceilings as constraints), GY-G (P14 into composition) |
| F16 | `output_hash` evidence must be time-invariant (`gy_evidence_canon.py`); replay is 3-level, not byte-exact | evidence-replay | GY-A1 (canonical hashing), GY-B (SearchLedger + replay levels) |
| F17 | Graded outcomes is fork-independent near-term (`useful_design_rate` off 0; statuses exist, only routing missing) | D1; matrix | GY-J (parallel) |
| F18 | GY/loop artifacts are an **unregistered** generated/public-surface family (0/31 registered; `inventory.json` no GY; lifecycle classification undecided) | generated-public-lifecycle | GY-M1 (Phase-0 hard gate) |

The coverage matrix is GY's single progress meter. A task is done only when its
matrix rows move from `bridge_missing`/`surface_missing`/`absent` to a complete chain
with a semantic test.

## 3.5 Build discipline — cut-lines, ownership map, discovery sources

This plan is large; without discipline it becomes the very P13 "contract gravity well"
the constitution warns against. Four guards, binding before any build.

### 3.5.1 Vertical Slice 0 — hard cut-lines (anti-P13)

Slice 0 proves the loop **shape** end-to-end on the smallest two-fixture set, and
nothing widens until both honest exits are recorded. The cut-lines:

- **Artifact types: 4** — `PolicyIntent`, `BaseDataset`, `Estimate`,
  `SearchExitContract`. Not all 14 `artifact_type` values. Slice 0 does **not**
  synthesize a `DesignCandidate`; real policy-design synthesis starts after the
  lowering/drafter/lex path is subordinated in Phase 2+.
- **Active operation types: 3** — `BIND` (catalog→bound state, including the minimal
  internal fetch/preview needed to materialize `BaseDataset`), `ESTIMATE` (one real
  foundry method), `VERIFY` (formal gate + one authority stamp). Not the 14 operation
  classes. `DISCOVER`/`ACQUIRE`/`REFINE`/`LOWER` may exist only as registry enum values
  or fail-closed stubs until their owning tasks land; they must not execute in Slice 0.
- **Two Slice-0 fixtures, one production trigger** — `/runs` (workflow path) → loop
  (GY-B2) runs: (a) a catalog-supported groundable case identified by a committed
  `Slice0FixtureManifest` (`fixture_id: ua_msme_credit_worldbank_measurement`, exact
  construct/scope query, expected catalog binding ids or seed refs, expected connector
  profile, expected producer-root kind) and (b) a tourism/local-development ceiling
  probe expected to need search/acquisition repair under the no-`ACQUIRE` cut-line.
  This avoids pretending an acquisition-heavy tourism case proves grounding.
- **Two honest exits** — the groundable fixture must produce a measurement-rooted
  `grounded_partial_admissible` **estimate-port** outcome only; Slice 0 must not emit
  `grounded_admissible`, must not promote a `DesignCandidate`, and must not imply
  design-level authority. The ceiling fixture must produce
  `search_ceiling_repair_required` or `acquisition_required` with the ceiling gate
  (§8.4). The other terminals are stubs that fail closed until later.
- **No recursion, no composition, no full multi-budget, no agent proposer in Slice 0.**
  `DECOMPOSE`/`COMPOSE` (GY-G), the agent (GY-I), and the full V-battery are **deferred
  by contract** until Slice 0 records real exits. `BudgetVector` is limited to
  `{compute.max_operation_invocations, compute.max_wall_seconds,
  search_quality.min_recall_at_known_seeds, search_quality.required_source_classes}`;
  `acquisition`, `expert`, `calendar`, `novelty`, and `recursion` budgets are explicit
  zero/disabled stubs until their owning tasks land.

**Stop rule:** any Phase-1+ widening (more artifact/operation types, recursion,
surfaces) before Slice 0's recorded honest exits is a scope violation — stop and review.
Slice 0 = GY-A1(min) + GY-A2(min) + GY-B + GY-B2 + GY-H(core) + GY-D1 + GY-C2(only if
the selected ESTIMATE path needs the lex/tail repair) + GY-M1. It proves loop shape,
authority derivation, measurement grounding, and honest ceiling behavior; it does not
claim the system can yet synthesize a full design.

### 3.5.2 `pdc` ownership / import map (reuse, do not re-declare)

`pdc` already exists and `pdc/_impl/` already implements much of the waist. Most of §4
is **reuse/extend**, not build-new. Build-new declarations that duplicate a canonical
owner are a design-review failure.

| Contract | Owner today | GY move |
| --- | --- | --- |
| `ArtifactRef` | `core/artifacts/manifest.py` (canonical) | **reuse** |
| `ForecastSupport` | `ir/analytics/` (canonical port vocab) | **reuse** |
| `AuthorityBoundary`, `CertifiedOperationEnvelope`, `DesignRecord`, `ValueOfInformation` | `pdc/_impl/layer2_readiness.py` | **reuse/extend** (add the two-axis authority semantics, §13) |
| `TypedDiagnosticRecord`, `ConstraintStoreSnapshot`, `CounterexampleRecord`, `RefinementDecision`, `SearchLedger`, `DesignCandidate(V0)` | `pdc/_impl/layer2_design_search.py` | **reuse/extend** (these are D3.2 seeds) |
| `DataNeedSpec` | `scientist/agent/protocols.py` | **reuse** (GY-E) |
| `SourceContract` / `DataRequirementSpec` | `runtime/quality/...` + `data_requirement/` | **reuse** (GY-D2) |
| `WorkspaceContract`, `OperationContract`, `OperationInvocationRecord`, `ApplicabilityResult`, `PortSpec`, `FrontierSnapshot`, `SearchExitContract`, `SearchIncompletenessRecord`, `ObligationRecord`, `SubDesignContract`, `CompositionCertificate`, `BudgetVector`, `ArtifactEnvelope` | none | **build-new in `pdc`** |

So GY-A1/A2 are mostly *extend the existing pdc design-search contracts* + add the ~13
genuinely-new orchestration types. Adapters/loop live in `runtime/quality`; `pdc` stays
engine-free. §4 below is the target contract shape; §3.5.2 is the ownership source of
truth for reuse vs extend vs build-new.

### 3.5.3 Operation-discovery sources + conformance criteria (anti-hidden-table)

"Discovered, not enumerated" (Rule 12) is only real if the sources and admission
criteria are concrete and the no-hardcode lint bites. **First discovery sources:**
foundry method registry (`get_registry().list_all()` — 389 methods), fabric connector
registry (`PROFILE_ID_BY_CONNECTOR_ID` + connector discovery), `scientist/agent` tool
registry (KnowledgeToolkit/tools), `data_forge` catalog (`DatasetCatalogGraph`), `ir`
analytics contracts (port vocabulary). **Adapter conformance criteria** (all must hold
before an engine asset is admitted as an Operation): (1) a typed signature is
discoverable from the registry (input_slots/dtypes/`requires`); (2) it passes
`validate_adapter_preservation` + the derived formal-applicability check; (3) it declares
`consumes`/`produces` ports + an `authority_transform`; (4) a smoke runs it on a real
input (executable, not merely registered). **Free-growth test (Rule 12):** a correctly
added engine asset becomes an Operation with **zero new code**; any hand-maintained
operation/method/construct list is a lint failure to mark→replace→delete.

### 3.5.4 Required proof packets (anti-P01/P05/P08/P10/P25)

The following packets are not optional prose reports. Each named high-risk task must
persist the packet as a generated artifact with a recomputing validator. The packet is
the acceptance surface: reviewers should inspect fields, not only task summaries.

- **`ProductionLoopRunProof`** (GY-B2/GY-L/GY-V2): `{run_id, job_id, endpoint,
  job_kind, enqueued_at, worker_lease_id, worker_id, _execute_workflow_invocation_id,
  workspace_loop_invocation_id, control_store_state_transitions, input_artifacts,
  output_search_exit_contract_ref, output_cas_refs, artifacts_index_refs,
  surface_reads_checked, legacy_path_disposition}`. Required path:
  `enqueue_job -> ControlWorker -> _execute_workflow -> WorkspaceLoop -> CAS +
  artifacts_index + /runs readback`. A direct helper call does not satisfy this proof.
- **`Slice0FixtureManifest`** (GY-B/GY-D1/GY-H): `{fixture_id,
  construct_scope_query, jurisdiction, population, time_horizon,
  expected_catalog_binding_refs, expected_connector_profile,
  expected_producer_root_kind, expected_terminal, forbidden_terminals,
  negative_controls}`. The manifest is the committed source of truth for Slice-0
  fixture expectations; implementation may not replace it with an inline fixture table
  or a prose "World-Bank style" label.
- **`AuthorityDerivationTrace`** (GY-A2/GY-B/GY-V4): `{operation_invocation_id,
  output_artifact_ref, declared_authority_transform, computed_evidence_kind,
  computed_decision_grade, producer_root_classes, method_classification,
  applicability_result_ref, calibration_refs, counterexamples_closed,
  certified_envelope_ref, unresolved_blockers, resulting_authority_boundary_ref,
  transform_mismatch_disposition}`. This is the audit trail for `A.verify`; an
  Operation-declared transform is an input hint only and cannot be the stamped result.
- **`AuthorityCandidateInventory`** (GY-F3/GY-V4): one row per candidate-positive
  status, including `{producer_component, source_artifact_ref, field_path, status_text,
  candidate_positive_rule, firewall_name, exclusion_reason, resulting_boundary_ref,
  false_exclusion_review, reviewer, reviewed_at}`. The count must reconcile to 406 on
  the Task-0 baseline, and false exclusions must become explicit repair tickets.
- **`CASIntegrityReport`** (GY-F2/GY-V5): `{artifact_ref, payload_digest,
  canonicalization_rule_ref, blob_uri, manifest_ref, authority_manifest_ref,
  duplicate_group_id, referrers, report_index_refs, lineage_refs, tamper_probe_result,
  mutation_probe_result, gc_retain_reason, gc_dry_run_result}`. It must prove digest
  semantics, dedup, mutation/tamper rejection, and GC survivability.
- **`TimeSourceEnvelopeAudit`** (GY-F3/GY-V5): `{catalog_watermark,
  source_observed_at, source_published_at, source_updated_at, ingested_at,
  effective_time, legal_valid_time, transaction_time, as_of_time, replay_time,
  run_started_at, run_finished_at, node_started_at, node_finished_at,
  retention_or_expiry, mismatch_disposition}`. A mismatch must block, downgrade, or
  create an obligation; it cannot be logged as decoration.
- **`SecretAndPIIScanReport`** (GY-F2/GY-V4): scopes are `{DAG bundles, connector
  request/response payloads, CAS manifests, raw artifact content/download routes,
  dashboard/public/export packets}`. Records include `{scope, artifact_ref_or_route,
  detector_version, finding_kind, redaction_applied, authority_surface_blocked,
  negative_fixture_result}`.
- **`SemanticBenchmarkRun`** (GY-D3/GY-V3): `{benchmark_ref, benchmark_version,
  label_owner, reviewer, rule_version_ref, construct_scope, queries, returned_hits,
  precision_at_k, recall_at_known_seeds, known_seeds_missed, negative_controls_passed,
  threshold_disposition}`. The gate consumes this packet; it may not validate itself.
- **`VOISelectionAudit`** (GY-H/GY-I/GY-V4): `{workspace_id, cycle_index,
  candidate_actions, agent_suggested_scores, normalized_scores, deterministic_voi_inputs,
  rejected_or_clipped_inputs, selected_action, reason, authority_gain_basis,
  decision_value_basis, cost_basis, bias_probe_result}`. Agent estimates are Ring-1
  candidates; GY-H owns the deterministic normalization and selection decision.
- **`StrangleReceipt`** (every replace/subordinate task — see §3.5.5): `{predecessor_ref,
  replacement_ref, disposition: deleted|fenced_default_flipped, default_before,
  default_after, guard_ref, remaining_callers, remaining_callers_disposition, removed_loc,
  verified_by}`. It proves the predecessor was cut or fenced and the default flipped in the
  same change (P28). "Both paths reachable" or "zero deletions" fails the receipt.

**P29 — these packets are emitted, not authored.** Every packet above must be written by
the real run it claims and its validator must recompute it from live code/artifacts and
fail on drift. The phase-0 `ProductionLoopRunProof` was hand-authored with placeholder ids
and a shape-only validator — the exact `authorial-refs` laundering (F12) these packets
exist to prevent. A packet whose identifiers are round/placeholder, whose times are
`…T00:00:00Z`, or whose validator only checks shape, does **not** satisfy its task.

### 3.5.5 Phase-0–2 implementation-review corrections — strangle, owner-first, name-by-function, emit-proof (P27/P28/P29/P30)

The phase-0–2 review found three recurring build-hygiene failures (now register patterns
P27/P28/P29). They are binding on every remaining task: a task may not close while
re-creating one. **P28 (strangle) is load-bearing** — without it the universal loop
becomes "one more layer over the static DAG" instead of its replacement, which is the
whole point of the slice.

**A. Concrete debts to clear while fixing phases 0–2** (each move is owner-first +
strangle, not a new parallel file):

| Debt found in the partial build | Pattern | Correct move |
| --- | --- | --- |
| `Slice0SearchLedger` (`gy_loop.py`) beside canonical `SearchLedger` (`pdc/_impl/layer2_design_search.py`) | P27 | DONE first pass: `Slice0SearchLedger` extends canonical `SearchLedger`; remaining cleanup is to narrow GY sidecar fields as consumers migrate. |
| Second `AcquisitionPlanner` (`gy_loop.py`) beside `acquisition_planner.py` / `layer2_substrate_acquisition.py` | P27 | DONE first pass: GY-E delegates routing/disposition to `plan_requirement_gap_acquisition`; remaining cleanup is to move the thin façade out of `gy_loop.py`. |
| Lex-bounds rule duplicated in `gy_spine_repair.py` and `policy_design/search.py` | P27 | DONE first pass: one owner = the engine (`search.py`); GY façade calls it. |
| Two fixture catalog graphs (`_InMemorySlice0CatalogGraph` + `build_slice0_fixture_catalog_graph`) | P27 | DONE: one fixture builder over the real `DatasetCatalogGraph`; tests use the canonical builder. |
| `require_explicit_parameter_bounds=False` default still launders `None→0.0` | P28 | DONE first pass: default is explicit-bounds fail-closed; remaining legacy inferred-bounds calls must stay explicit until deleted. |
| 2674-line `gy_loop.py` holding B/D1/D2/D3/E/H | P27 (dual) | Move each gate/producer to its owning module; `gy_loop.py` keeps only the loop. |
| `ProductionLoopRunProof` hand-authored, shape-only validator | P29 | DONE: emitted from durable worker path and validator recomputes from CAS/index refs. |
| F4/F7 "closed" on a 2-record catalog corpus | P29 | Measure recall/precision on a representative corpus, or mark `surface_out_of_scope` with rationale. |

**B. Strangle protocol (P28).** A replace/subordinate task is not done until, **in the
same change**, it (1) deletes or fences the predecessor, (2) flips the default to the
corrected path, and (3) adds a guard (lint/test) that fails if a new caller reaches the
predecessor. It then persists a `StrangleReceipt` (§3.5.4) with a recomputing validator.
Legacy that genuinely cannot be cut yet is fenced as `legacy_shadow` / candidate-only
**and** listed in `remaining_callers` with a dated cut ticket — never left as a silent
default. This is exactly how GY-B2 already treats `/runs`, `/runs/nl`, and the
`workflow_run` job path; every later subordination (GY-C1 legacy nodes, GY-C2 lex/
governance, GY-F1 worker surfaces) follows the same pattern, not an additive layer.

**C. Owner-first protocol (P27).** Before `class Foo` or a new `gy_*.py`, consult the
§3.5.2 ownership map and run `grep -rl "<concept-root>" src/polisyos/{pdc/_impl,runtime/quality}`
for a live owner. If one exists, extend it. New files are for genuinely-new orchestration
contracts only. Free-growth still holds (§3.5.3): a correctly added engine asset becomes an
Operation with zero new code — if you are writing a hand-maintained list or a parallel
gate, stop.

**D. Emit-proof protocol (P29).** See the §3.5.4 P29 note: identifiers come from the run
(no placeholders), times are real, validators recompute, and any search/recall/precision
closure is measured on a representative substrate — not a fixture small enough to make the
metric vacuous. A committed Slice-0 `Slice0FixtureManifest` is allowed (§3.5.1); a
2-record corpus standing in for the *benchmark substrate* of an F4/F7 closure is not.

**E. Name-by-function protocol (P30) — so reuse is self-evident.** New files are named for
the capability they own (`workspace_loop.py`, not `gy_loop.py`); the owner-first grep (C)
is by *function word*, so it only finds owners if files are function-named. The phase-0–2
`gy_*` files are a standing P30 debt: either rename each to its function, or — where it
holds genuinely-new orchestration — add a module docstring that names the canonical owners
it extends (`SearchLedger`, `acquisition_planner`, `adapter_contracts`, `semantic_binding`,
`data_forge_binding`) and links related modules, so the next implementer reads them before
writing a parallel file. No new GY file may take a bare plan-provenance name without that
breadcrumb. Naming is not cosmetic: it decides which file the next person opens first, and
is the cheapest defense against re-creating P27.

**F. Standing gate for phases 2→5.** Every task's `Done when` now also requires: no second
live owner for any concept it touches (P27); a `StrangleReceipt` for any path it replaces,
with the default flipped (P28); function-named modules with owner breadcrumbs, never a bare
plan name (P30); and run-emitted, recomputed proof packets on a representative substrate
(P29). Checked at design review and at closeout, alongside the matrix/GX gates. A task whose
local tests pass but that leaves a parallel owner, an un-strangled default, a plan-named
file with no owner breadcrumb, or an authorial proof is **not done**.

### 3.5.6 Substrate / binding lift completeness gates (the GY-S lesson — binding for every lift / resolution / binding task)

The GY-S substrate lifts (S1 data-state, S2 knowledge, S3 intervention) cost many adversarial
rounds because each shipped a **shell** that passed its own narrow probes: coverage looked green but
on a curated subset; authority was **supplied, not derived**; the contract exercised only the
happy-path. The failure **escaped one level deeper each round** — for S3 the supplied authority went
caller-supplied → hardcoded code-table → hand-injected into git-ignored data → relocated into a
tracked JSON the runtime merely *trusted*; for S2 it was percent-only units / single-row lineage /
weight-synthetic contested. The disposition is always the same: **derive through the real owner +
validate (fail-closed on a fake input), never supply; be generic over the data, not enumerated; and
make the gate exercise the decisive property.** Four gates are now **binding on every task that
lifts, resolves, or binds authority** (the GY-S block and the cycle tasks N2/N4/N7/N8/N9 — their
contracts must encode all four for their decisive property):

1. **Full-denominator coverage.** Measure coverage against the **full real vocabulary** (count the
   real source files / registries), never a curated subset or a 2-record corpus. A green `N/N` is
   load-bearing only when `N` is the full real denominator — prove the denominator (`P10`).
2. **Fail-closed on a fake / novel input.** A binding to a **non-existent owner target** (a slot not
   in the real world model / `GlobalState`, a provision not in real L3), an unknown unit, or an
   out-of-domain parameter **must fail closed**. This proves the runtime **validates through the
   real owner**, not merely trusts a declared / curated / supplied value (`P32`, the
   resolve→content-bind→validate root). A tracked binding artifact is legitimate **only** if it is
   owner-validated this way — a JSON the runtime trusts is just a relocated name-map.
3. **Data-only free-grow.** A genuinely **new** entry (knob / law / family / claim / threshold)
   added via **data alone** must lift with **zero code change**; a malformed one fails closed. This
   proves the mechanism is **generic over the data**, not an enumerated / name-substring branch
   (Rule 12, `P31`). Reusing an existing mechanism for the "novel" case is a fake free-grow.
4. **The contract mutates the DECISIVE validation property (`P29`).** The behavioral contract must
   include a remove-the-property mutation for the **decisive** property — the fail-closed-on-fake
   owner validation of gate 2 — not only coverage / free-grow / no-hardcode. The gate must go **red**
   if owner-validation is removed while the happy-path bindings stay valid. A runtime that is correct
   today but whose contract would not catch that regression is **not done** (this is the exact
   verifier-completeness gap that held S3 to its last round).

Every impl/audit prompt and every `Done when` for a lift/resolution/binding task front-loads these
four — so the implementer builds to them on the first pass instead of rediscovering them through
rounds. Verification stays **targeted** (§Commands; blast-radius + recomputing validators + ruff +
guardrails), never full pytest.

### 3.5.7 Compute-economics gates (the GY-N4 lesson — binding for every task with expensive shared state or a live provider; restored Rev 15)

Distilled from the GY-N4 saga: a **correct** closure cost ~4 hours because the full world
(CredalReference + 792k-edge FTS index + composed WMR) was rebuilt in every validator/probe/unit
run. Strictness was never the cost — redundant rebuilds were. Ten gates, binding on N9–N12, N10a,
O0–O3, and every closeout sweep:

1. **E1 Content-hash-keyed shared-state cache.** Build reference/index/WMR/engines once; reuse by
   owner content hash. A cache hit is **identical to a rebuild by construction**; owner change →
   miss; **fail-closed on staleness** (a stale cache hit is exactly a §3.5.6-gate-2 "trusted JSON"
   hole). Built by GY-INFRA-1 (closed; cold≡warm proven byte-identical).
2. **E2 One-process sweep-runner** — the closeout sweep runs in ONE process over ONE build.
3. **E3 Three-lane pyramid** — Lane 0 (logic, synthetic mini-fixtures, <10s, zero owner I/O) /
   Lane 1 (real owners via the E1 cache) / Lane 2 (cold full, **once at closeout**).
4. **E4 Min-sufficient mutations** — one cached baseline + payload/policy flips; **≥1 real
   behavioral flip per property class preserved**; never a full recompute per mutation.
5. **E5 Validators record their own wall-time** — overrun (≈5min warm / ≈25min cold) is itself a
   finding (usually a missed cache reuse).
6. **E6 Journal-first for live tasks** — raw evidence persists at the earliest boundary;
   set-accumulation; archive without raw payload forbidden (built in N4 — reuse, never reinvent).
7. **E7 Pre-live gauntlet** — before any provider call: fuzz the parse/validate boundary with
   near-valid variants; replay existing recordings through the changed pipeline; scripted e2e smoke.
8. **E8 One variable per expensive attempt** — effective config into the run record.
9. **E9 Stage-heartbeats + objective progress rule** — CPU-active + advancing → wait; wall > 2×
   recorded historical → stop + profile. Never kill a progressing cold build.
10. **E10 Diagnose from already-paid evidence first** — build the failure table from data on disk
    before any fresh run.

**Never loosen a §3.5.6 correctness gate to satisfy an economics one** — a warm/cached run is
legitimate only because it is content-identical to the cold rebuild, and the cold closeout still
runs.

### 3.5.8 Domain/method-family genericity gates (the GY-N8 lesson — binding for every task downstream of the first vertical; NEW, Rev 15)

The first real vertical (Ukraine/governance world; panel/DID value over `avg_income`; 2/32 writable
levers) is the **scaffold, not the product**. The N8 saga proved that landing one real vertical
under adversarial pressure leaves hardcodes behind (governance transport covariates; panel-only
calibration credibility) — honest refusals today, silent universality loss tomorrow. Four gates,
front-loaded into every impl/audit prompt for N9–N12, N10a, O0–O3, and the V battery:

1. **U1 Typed-contract consumption.** A downstream consumer (promotion, confidence ledger, epochs,
   learning loop) consumes only the **typed contracts** (`ValueOuterSet`, `ValueGateReceipt`,
   transport/calibration receipts, the obligation taxonomy, `WorldModelRecord`) — never fields
   specific to the first vertical's method family or domain. The consumer must not need rework when
   N10 generalizes the producers.
2. **U2 Unseen-shape probe (P29 at domain scale).** Every consumer ships a contract mutation: a
   contract-valid artifact from an **unseen method family / domain** flows through with zero code
   change, or fail-closes typed. A consumer whose contract would not catch a hardcode to the first
   vertical is **not done**.
3. **U3 Vocabulary-from-data (Rule 12 at domain scale).** Domain vocabularies — transport
   covariates, schema regimes, epoch boundaries, lever spaces, eval-safety mode requirements —
   derive from substrate / domain-pack **data**, never enumerated in engine code. A new domain's
   vocabulary lifts via data alone (S0 free-grow + N7 acquisition), zero code.
4. **U4 Honest refusal over fake generality.** Where a capability is genuinely first-vertical-only,
   it must refuse **typed** (`scope_insufficient` / `unsupported` → routes to acquisition/N7) —
   never auto-pass, never fabricate. An honest typed refusal is a pass; fabricated generality is a
   fail. (The dual of the N8 lesson: no fabricated pass AND no fabricated block.)

### 3.5.9 Live-carrier conformance gates (the GY-N10 compiler lesson — binding for every task with a live LLM or external-data carrier; NEW, Rev 16)

The N10 plain-language compiler consumed multiple NO-GO rounds on one lesson: a free-form carrier
described in prose will drift from the strict gate; the fix is always **constrain the request,
never the gate**. Five gates for every surface that consumes a live model or an external data
source (the N13 connectors, the O-block bounded LLM agent, any new N4-class prompt lane):

1. **C1 Schema-constrained emission.** The full owner-derived machine schema travels WITH the
   request (LLM: the complete tool/response JSON schema **including Python-only conditional
   validators, which do not export automatically**; data connector: the schema-profile /
   binding-profile contract). Free-form generation validated only after the fact is not a carrier
   design.
2. **C2 Typed, derived budgets.** Output/token/row/rate budgets are typed and derived from
   measured need with journaled rationale — never an inherited silent default (the 3,072-token
   lesson); truncation/overrun at ANY budget is a **typed disposition**, never a parse crash or a
   partial artifact.
3. **C3 Characterize before proof.** A finite journaled characterization matrix (params × models
   × repetitions; sampled endpoints per connector family) precedes any proof capture; shadow rows
   never become proof rows; the winning config is selected from the table, and conformance must be
   a stable property (repetitions), never a seed lottery.
4. **C4 Request-side only; no response shims.** The carrier must emit conforming output natively
   via request parameters; stripping/unwrapping/repairing responses between the provider and the
   gate is forbidden (router-not-carrier). A carrier that only passes because we cleaned its
   output has not passed.
5. **C5 Earned NO-GO.** A carrier-exhausted terminal is earned only after the highest-value
   honest lever identified by root-cause analysis has been TESTED (structured outputs before
   "the model can't"; the budget before "the provider is broken"). Premature NO-GOs cost N10 two
   full rounds.

### 3.5.10 Frozen-expectation discipline — recompute-not-pin (the N10 expectation-transplant lesson; NEW, Rev 16)

One failure class fired three times inside N10: a frozen gate pinned a SPECIFIC downstream
terminal (the Stage-2 data-gap receipt transplanted onto a fresh capture; pre-CGF test assertions
demanding "all proposals become candidates"; the N10a checker demanding a superseded repair-only
terminal) — and every honest deepening of an owner then read as a failure. Binding for every gate
and frozen artifact from N11 on:

1. **Gates assert structurally recomputed properties.** A terminal/evidence class is recognized by
   recomputing its evidence from the owners (a real planner route report, a real advisor refusal
   receipt, real availability evidence) and comparing recomputed-vs-recorded — never by comparing
   a recorded label to a pinned string. The N10 capstone's `_domain_evidence_kind` pattern is the
   reference implementation.
2. **Distinctness/coverage bars replace per-role pinning.** Where a proof needs variety, demand
   "≥K structurally distinct classes over the set", never "role X must show terminal Y" — honest
   terminals legitimately move as owners deepen.
3. **A frozen expectation is valid only while it recomputes.** When the recomputation moves
   honestly, the artifact is rebaselined through its canonical writer (never hand-edited) and the
   diff must be provenance-only or an honestly remeasured disposition.
4. **Batch-fix → single ripple.** Audit to the END of the denominator first (the full findings
   list), land all owner fixes, then run ONE provenance-rebaseline pass in canonical order —
   never fix→ripple→fix→ripple (the N10 closure paid this cost repeatedly).

### 3.5.11 Projection-scoped provenance binding (ripple containment; NEW, Rev 16)

The frozen chain (census → N4 → N8 → N10a → composition → capstone) is now deep enough that a
one-line owner fix costs hours of serialized rebaselines. N10 also proved the containment
pattern: N8↔N10a converged as a fixed point because each consumed a **narrow projection** of the
other (the first-vertical transport projection stayed byte-fixed while the education lane moved).
Binding for every NEW frozen artifact (N13 acquisition receipts, the N11 ledger, N12 epochs, the
O-block):

1. A consumer binds to the **narrowest upstream projection hash** that carries its actual
   dependency — never the producer's whole-contract hash.
2. Projections must be **acyclic**, and each projection's scope is declared in the artifact.
3. Operational values (clocks, wall times) live outside every content hash (existing law) and are
   carried across rewrites only by the canonical writer's volatile-field branch under a matching
   contract hash — the volatile classification has ONE source of truth (the canonical GY hash
   owner's excluded-field list), never a writer-local list.

### 3.5.12 Data-pool growth + derived-data gates (the Rev-17 consultation — binding for N13+, the O-block, and every data-plane task; NEW, Rev 17)

The data plane grows two ways — new external sources, and new datasets **derived** from existing
ones. Both are authority events. Six gates:

1. **D1 Family-first, config-not-code growth.** A new external source is a **registry entry**
   (endpoint / auth / rate limits / license) over an existing connector family; a new connector
   CLASS is justified only by a genuinely new protocol family (one SDMX/CKAN-class family
   unlocks dozens–hundreds of sources). §3.5.6-gate-3 / U3 at the connector scale.
2. **D2 Demand-driven growth.** Sources are added when a typed N7 requirement resolves to
   `connector_gap` / `binding_gap` — the growth backlog is **VOI-ranked by the same machinery
   that ranks data acquisition**; the pool is pulled by the cycle, never grown for size.
3. **D3 Graded source promotion + recurring liveness.** A new source enters at a low L5 trust
   tier via ExploreLane (exploration-only authority) and **earns** curated-contract status
   through the scorecard + PromotionLane (liveness, schema stability, license clarity, data
   quality) — source authority is earned, exactly like a CGF bind. Liveness is a **recurring
   journaled census with tier decay** (a stale scorecard downgrades `execution_tier` and
   re-routes planning); schema drift at fetch time is a typed `schema_drift` → quarantine,
   never silent coercion.
4. **D4 Derived data = content-addressed artifacts, not a dataflow engine.** A derived
   dataset's identity is the hash of its **full recipe** — input dataset hashes ×
   method+version+parameters × **auxiliary inputs** (e.g. the deflator series version + base
   year). The transformation is a subordinated Operation with a recorded envelope in the
   EXISTING artifact graph; identical recipes are cache hits (E1); consumers bind the derived
   artifact's hash (§3.5.11). Auxiliary choices (CPI vs GDP deflator, base year) are **declared
   assumptions in the certificate**, visible to sensitivity analysis. The derivation graph is
   acyclic.
5. **D5 Provenance classes with an authority taxonomy.** The growing world store carries typed
   provenance classes — `observed` (acquired), `derived` (certified transform),
   `deployment_update` (posterior) — all epoch-stamped and passport-gated; derived data
   **never masquerades as observed**. Transforms are classed by authority impact:
   (i) normalizations (units / currency / inflation / per-capita — deterministic,
   assumption-carrying); (ii) aggregation / resampling (deterministic, lossy);
   (iii) statistical estimates (imputation / smoothing / seasonal models — model assumptions);
   (iv) model outputs (**never** admissible as observations). A consumer declares which classes
   it admits (**observed-only by default**); derived authority is monotone non-increasing over
   the weakest input, degraded per class (the `is_proxy` / `proxy_penalty` pattern).
6. **D6 Basis-aware matching — certified transform or typed refusal.** Variable **basis**
   (nominal / real + base-year + deflator-ref, currency, per-capita, seasonal adjustment) is a
   typed vocabulary over the existing units/dimensions/coercion + `condition_json` machinery; a
   method's `RequiredDataSpec` declares its required basis; a mismatch resolves through a
   **certified** transform (inserted or cache-hit) or refuses typed `basis_mismatch` → a
   derivation requirement routed to N7 — never a silent coercion (the CGF principle for
   transforms). Staleness inherits through N12 epochs: an input revision (agencies revise
   series) marks dependent derived artifacts `revalidation_required`; the certificate IS the
   recipe, so revalidation is an automatic recompute.

### 3.6 Anti-simplification audit — preserve capability, close findings substantively

Slice 0 is a shape proof, not a license to ship a small engine. The implementation must
use the existing system's real capabilities and close Task-0 findings by moving
producer/bridge/consumer/surface evidence, not by renaming stubs as governed artifacts.

Acceptance constraints:

- **Catalog:** use `DatasetCatalogGraph` and real catalog bindings; no private fixture
  table may stand in for search/resolve.
- **Connectors:** respect per-family fetch contracts (`WorldBank`, `CKAN`, `SDMX`, etc.)
  rather than a generic "connector exists" flag.
- **Foundry:** `ESTIMATE` consumes a real foundry method output and method metadata; a
  synthetic estimate is a helper-only smoke.
- **Lex/governance tail:** optional-bounds repair and judge-tail validity must land
  before any governance output can become authority-bearing.
- **Agent:** PI/drafter/critic/tool-loop records are event-backed Ring-1 proposals; no
  synthetic G6 credit.
- **LLM/public-surface authority:** LLM, drafter, critic, dashboard, and export text are
  projections or candidates until a verifier-stamped artifact grants a purpose-scoped
  boundary; no PUBLIC/REVIEWER/EXPERT/MACHINE view may infer authority from presentation.
- **Surfaces/CAS/time/secrets/406:** proof must pass through production routes, raw
  artifact access, public/dashboard exports, report indexes, CAS manifests, and the
  candidate-positive firewall inventory.
- **Scholar/OpenAlex, KnowledgeToolkit, and `data_requirement`:** if not in Slice 0,
  they stay named follow-ons with ownership, blocker, and expected proof packet; they
  cannot disappear as "out of scope" without a `surface_out_of_scope` rationale.
- **Substrate packages:** core/IR/evidence/BERL/DDM/calibration/requirement packages are
  consumed as existing constraints, ceilings, and authority inputs; do not copy their
  semantics into new PDC enums.

| Audit finding | Non-simplification closure |
| --- | --- |
| F4/F7 catalog/search | Real `DatasetCatalogGraph` + governed semantic benchmark + known-seed recall, consumed by `BIND`/`VERIFY`. |
| F5/F6 connectors/source contracts | Per-family connector gates + source-contract/freshness admissibility before fetch. |
| F10 foundry | At least one route-consumed real method output, with measurement-rooted authority and method classification. |
| F8/F9 lex/governance tail | Repair optional-bounds + phase-5 judge tail before governance-to-authority. |
| F11 agent/KnowledgeToolkit | Event-backed role records + Ring-2 rejection test; KnowledgeToolkit tools registered as discovered Operations. |
| F12/F13 surfaces/CAS/time/secrets/406 | Production proof packets from real routes: `CASIntegrityReport`, `TimeSourceEnvelopeAudit`, `SecretAndPIIScanReport`, `AuthorityCandidateInventory`. |
| F14 depth-2/generalization | GY-M2 non-pinned GX + GY-V3 labelled multi-case/depth-2 distribution; no one-case universal claim. |
| F15 substrate packages | Existing core/IR/evidence/BERL/DDM/calibration/requirements become consumed constraints or ceilings, not duplicated schema folklore. |
| P03/P15 LLM and public-surface laundering | Multi-audience projections consume `AuthorityBoundary`; LLM/drafter/export text remains candidate/projection unless backed by producer evidence and verifier authority. |
| P2 Scholar/OpenAlex | GY-K remains required for literature/prior/tool-backed search; web bundles stay non-authority until span-grounded. |

A task that only stubs/mocks/summarizes a finding and leaves the row green without a
complete chain (`producer -> persisted artifact/event -> bridge -> consumer -> surface
-> semantic/negative test`) is a P01/P10 failure, even if its local tests pass.

## 4. The two-ring waist — full type schemas (canonical-owner map in §3.5.2)

The canonical contracts the loop speaks. Some are reused from existing owners, some are
extended, and only the missing orchestration contracts are new (§3.5.2). **Ring 1 vs
Ring 2 is a per-field write permission, not a type set** — several Ring-2 fields live
inside Ring-1 types and stay
`null` until a verifier writes them (the agent may construct the surrounding Ring-1
object but not those fields). 17 contracts total. (Abbreviated where obvious.)

### 4.1 Ring 1 — execution waist (agent/engine-writable)

```yaml
ArtifactRef:               # identity + addressing, no payload
  artifact_id: str
  artifact_type: ArtifactType   # PolicyIntent|BaseDataset|ResearchClaim|MeasurementStrategy|
                                # DataNeed|AcquisitionRequest|Estimate|SimulationResult|LegalFinding|
                                # DesignCandidate|CounterexampleRecord|SubDesignContract|PolicyProgram|
                                # SearchExitContract|CompositionCertificate|...
  content_hash: str             # canonical, time-stripped (gy_evidence_canon) — F16
  schema_ref: str; uri: str; version: str

ArtifactEnvelope:          # provenance/authority carrier around every payload
  ref: ArtifactRef
  payload_ref: str; payload_schema_ref: str
  lifecycle_state: shadow | verified | promoted | rejected | superseded | archived
  created_by: {kind: operation|agent|human|imported, id: str}
  producer_operation: {invocation_id, operation_id, operation_version}
  input_artifacts: [ArtifactRef]
  producer_roots: [ArtifactRef]                              # measurement roots for authority
  certified_operation_envelope: CertifiedOperationEnvelope|null  # operation-DECLARED (Ring 1) + verifier-confirmed
  authority_boundary: AuthorityBoundary | null               # RING-2 FIELD — verifier-only
  obligations: [ObligationRef]
  verification: {latest_applicability_result: Ref|null, latest_promotion_result: Ref|null}  # promotion_result is Ring-2

PortSpec:
  port_id; direction: consumes|produces|requires|provides
  port_type: PolicyIntent|Dataset|Claim|Estimate|DesignCandidate|LegalFinding|CapacityModel|SequencePlan|RiskModel|SubDesign
  claim_shape: {kind: causal|legal|fiscal|operational|forecast|descriptive|design|system_program|none, subject_type, predicate_type, object_type?}
  multiplicity: {min, max}
  constraints: {jurisdiction?, time_horizon?, population?, scale?, data_shape?}   # data_shape e.g. {kind: panel, requires_groups_min: 2, requires_pre_period: true, requires_post_period: true}
  required_authority: AuthorityRequirement | null            # for requires/consumes
  provided_authority: AuthorityBoundary | null               # RING-2 FIELD — verifier-only

OperationContract:         # the coarse verb the loop plans over (not a foundry method)
  operation_id; operation_version
  operation_class: DISCOVER|ACQUIRE|BIND|TRANSFORM|ESTIMATE|SIMULATE|TRANSPORT|VERIFY|REFINE|LOWER|DECOMPOSE|COMPOSE|ELICIT|ESCALATE|ABSTAIN
  consumes: [PortSpec]; produces: [PortSpec]
  formal_preconditions: [{predicate_id, description, check_ref, severity: hard|soft}]
  allowed_internal_execution: [foundry_method|foundry_method_chain|llm_agent_plan|tool_call|human_request]
  implementation_refs: [{kind: python_function|foundry_method|agent_policy|tool_adapter|legacy_node_adapter, ref}]
  cost_model: {compute, acquisition?, expert_attention?}
  authority_transform: {kind: preserves|weakens|calibrates|simulates|transports|composes|unknown, rule_ref}
  failure_modes: [ApplicabilityErrorKind]; repair_options: [OperationClass]

OperationInvocationRecord:
  invocation_id; operation_id; operation_version; workspace_id; cycle_index
  selected_by: {kind: refinement_policy|llm_agent|human|playbook, id}; selection_rationale_ref?
  input_artifacts: [ArtifactRef]; parameters: {schema_ref, value_ref}
  internal_trace: {trace_kind: deterministic|agentic|mixed|human, trace_ref}
  tool_calls: [ToolCallRecordRef]; human_requests: [HumanRequestRecordRef]
  output_artifacts: [ArtifactRef]; applicability_result: ApplicabilityResultRef
  budget_delta: BudgetDelta; status: started|completed|failed|repair_required|cancelled

ApplicabilityResult:       # the deterministic formal gate result (type system for methods)
  result_id; invocation_id
  status: applicable|not_applicable|applicable_with_warnings|repair_required
  checked_preconditions: [{predicate_id, status: passed|failed|unknown, evidence_ref?}]
  failed_preconditions: [{predicate_id, reason}]
  type_errors: [{input_port, expected, observed, repair_options: [OperationProposalRef]}]
  repair_options: [{operation_class: TRANSFORM|ACQUIRE|BIND|SWITCH_METHOD|ESCALATE, description, expected_to_fix: [predicate_id]}]

WorkspaceContract:
  workspace_id; parent_workspace_id?
  intent_ref: ArtifactRef
  scope: {domain, jurisdiction, scale: local|regional|national|international|multi_level, time_horizon, posture: exploratory|advisory|pre_decision|implementation_ready}
  artifact_graph_ref; constraint_store_ref; agenda_ref; frontier_ref
  allowed_operations: [operation_id]; budget: BudgetVector
  recursion_policy: {max_depth, max_child_workspaces, decompose_allowed}
  exit_requirements: {require_search_exit_contract: true, require_incompleteness_record: true, require_authority_boundaries_for_promotion: true}

SearchLedgerEvent:         # audit/provenance spine (W3C PROV: entity/activity/agent)
  event_id; workspace_id; cycle_index
  event_type: workspace_started|constraint_store_updated|operation_proposed|operation_selected|operation_started|operation_finished|tool_called|human_input_requested|human_input_received|verifier_ran|artifact_promoted|artifact_rejected|budget_updated|terminal_state_selected
  actor: {kind: system|refinement_policy|llm_agent|human|verifier|tool, id}
  input_artifacts: [ArtifactRef]; output_artifacts: [ArtifactRef]
  operation_invocation_ref?; decision_record_ref?
  budget_delta?; authority_delta?  # authority_delta is verifier-written
  created_obligations: [ObligationRef]; timestamp

BudgetVector:              # budget is a vector, never one max_iterations
  compute: {max_tokens?, max_wall_seconds?, max_operation_invocations?, hard: bool}
  acquisition: {max_money?, max_data_requests?, max_pilot_duration_days?, hard: bool}
  expert_attention: {max_expert_hours?, max_review_rounds?, hard: bool}
  calendar: {decision_deadline?, hard: bool}
  novelty: {max_cycles_without_frontier_improvement?, min_improvement_delta?}
  recursion: {max_depth, max_child_workspaces}
  search_quality: {min_recall_at_known_seeds?, freshness_window_days?, required_source_classes: [official|academic|local_data|legal|administrative]}
```

### 4.2 Ring 2 — promotion / honesty waist (verifier/governance-written fields)

```yaml
AuthorityBoundary:         # [extend pdc/_impl/layer2_readiness.py]; authoritative_for AND may_not_use_for both mandatory for promoted
  boundary_id
  authoritative_for: [{claim_type: causal|legal|fiscal|operational|forecast|sequencing|system_program, jurisdiction, scale, time_horizon, posture, population?}]
  may_not_use_for: [{claim_type, reason}]
  # TWO ORTHOGONAL AXES (do not collapse into one total order — see §13):
  evidence_kind: measurement|derivation|proxy|transport|bounds|simulation|elicitation   # WHAT kind of evidence (the ladder)
  decision_grade: unsupported|descriptive_only|advisory_admissible|decision_admissible   # HOW decision-ready it is
  evidence_basis: {producer_roots: [ArtifactRef], method_refs: [str], calibration_refs: [ArtifactRef], counterexamples_closed: [ArtifactRef]}
  known_limits: [str]
  # SPEC OBLIGATION (GY-A2): define the lattice on EACH axis independently —
  #   authoritative_for: partial order by ⊇ ; envelope: intersection ;
  #   evidence_kind: partial order on the ladder (measurement strongest) ;
  #   decision_grade: total order (unsupported < descriptive_only < advisory_admissible < decision_admissible).
  # `meet` (§7) takes the meet on each axis separately. The two axes are orthogonal:
  # e.g. a `simulation` result may be `advisory_admissible`; a `measurement` result may be
  # only `descriptive_only` if it does not identify the effect. See §13 mixed examples.

CertifiedOperationEnvelope:    # operation-DECLARED (Ring 1) scope + verifier-CONFIRMED for authority
  envelope_id; domain; jurisdiction; scale; population?; time_horizon; posture
  data_conditions: {required_data_shapes: [str], observed_data_shapes: [str], missing_data: [str]}
  method_conditions: {assumptions: [str], diagnostics: [ArtifactRef]}
  out_of_envelope_triggers: [str]

FrontierSnapshot:          # anytime state of the search
  snapshot_id; workspace_id; cycle_index
  promoted_candidates: [ArtifactRef]; shadow_candidates: [ArtifactRef]
  rejected_candidates: [{artifact_ref, reason, counterexample_ref?}]
  dominated_candidates: [{artifact_ref, dominated_by, dimensions: [cost|risk|authority|feasibility|welfare]}]
  current_best: [ArtifactRef]
  frontier_metrics: {candidate_count, promoted_count, rejected_count, cycles_without_improvement}

SearchIncompletenessRecord:    # the honesty artifact — see §8.3
  record_id; workspace_id
  coverage: {operations_attempted, operations_not_attempted: [{operation_id, reason}], methods_attempted, source_classes_checked, source_classes_missing: [{source_class, reason}], jurisdictions_checked, time_horizons_checked}
  search_quality: {recall_at_known_seeds?, known_seeds_missed: [ArtifactRef], freshness_ok?, stale_source_classes: [str]}
  unresolved: {counterexamples, missing_data, unmet_required_ports, unresolved_couplings, human_questions}
  budget: {consumed: BudgetVector, remaining: BudgetVector, exhausted: [compute|acquisition|expert_attention|calendar|novelty|recursion]}
  next_best_actions: [{operation_proposal_ref, estimated_voi, estimated_cost, reason_not_taken}]
  ceiling_classification: domain_ceiling | search_ceiling | mixed | unknown

SearchExitContract:        # every Workspace exits with this, never success/failure — see §8
  exit_id; workspace_id; cycle_index
  terminal_state: {kind: grounded_admissible|grounded_partial_admissible|frontier_stable|acquisition_required|human_decision_required|grounded_abstention|search_ceiling_repair_required|budget_exhausted|composition_invalid|a_spec_gap|recursive_blocked|tool_failure, reason, blocking_obligations: [ObligationRef]}
  frontier_snapshot: FrontierSnapshotRef; incompleteness_record: SearchIncompletenessRecordRef
  budget_ledger: {consumed, remaining}; output_artifacts: [ArtifactRef]
  authority_boundary: AuthorityBoundary | null; next_best_actions: [OperationProposalRef]

ObligationRecord:
  obligation_id; obligation_type: counterexample|acquisition_required|human_decision_required|verifier_spec_gap|composition_gap|search_repair_required|legal_review_required|capacity_review_required
  raised_by: {workspace_id, operation_invocation_id?, verifier_id?}
  blocks: [{artifact_ref?|port_ref?|claim_ref?}]; description; severity: informational|blocks_promotion|blocks_composition|blocks_decision
  resolution_options: [{operation_class: ACQUIRE|REFINE|VERIFY|DECOMPOSE|COMPOSE|ESCALATE|HUMAN_DECISION, description, estimated_cost?, estimated_voi?}]
  status: open|resolved|escalated|accepted_as_limit

SubDesignContract:         # what a child Workspace exports to its parent — see §7
  subdesign_id; workspace_id; parent_workspace_id
  scope: {domain, jurisdiction, scale, time_horizon, posture}
  provides: [PortSpec]   # each provided port carries its own AuthorityBoundary (Ring-2) + envelope
  requires: [PortSpec]
  coupling_declarations: [{from_port, to_port, coupling_kind: independent|sequential|shared_resource|feedback|mutually_exclusive|unknown, rationale_ref}]
  producer_roots: [ArtifactRef]; search_exit: SearchExitContractRef
  unresolved_obligations: [ObligationRef]
  internal_trace_ref: AuditOnlyRef   # parent may audit, may NOT use as an authority shortcut

CompositionCertificate:    # required before any PolicyProgram promotion — see §7
  certificate_id; parent_workspace_id; input_subdesigns: [SubDesignContractRef]
  coupling_gate: {verdict: valid|requires_joint_workspace|requires_capacity_aggregation|requires_system_dynamics|invalid, blocking_edges: [CouplingEdgeRef]}
  authority_flow: [{from_port, to_port, resulting_authority: AuthorityBoundary, rationale_ref}]
  emergent_claims: [{claim_ref, grounding_status: grounded|simulation_only|missing|invalid, required_grounding: [capacity_aggregation|sequencing_consistency|system_dynamics|equilibrium_check|cross_chapter_counterexample_search], resulting_authority: AuthorityBoundary|null}]
  unresolved_obligations: [ObligationRef]; verdict: composable|composable_with_limits|not_composable
```

## 5. The control loop (spec)

```text
WorkspaceLoop(intent, budget):
  ws = initialize Workspace(intent, budget)
  publish initial ConstraintStore from A cluster producers
  while true:
    refresh ConstraintStore from current artifacts          # A BEFORE generation
    proposals  = Planner.propose_operations(ws.frontier, ws.agenda, ws.budget)          # Ring 1
    applicable = FormalGate.filter(proposals)               # ApplicabilityResult; deterministic
    ranked     = RefinementPolicy.rank_by_VOI(applicable, ws.budget, ws.scope.stakes)   # VOI owned by GY-H
    if should_terminate(ranked, ws.budget, ws.frontier, search_quality):
        return SearchExitContract(...)                      # §8 — typed terminal, anytime
    op  = ranked.best
    res = execute(op)                                       # MethodPlan; Ring-1 artifacts, shadow
    ws.graph.append(res.artifacts); SearchLedger.append(OperationInvocationRecord, events)
    verdict = A.verify(res)                                 # A AFTER generation; writes Ring-2 fields on pass
        promotable -> ws.frontier.update(res, AuthorityBoundary)   # only A writes Ring-2 fields
        failed     -> ws.agenda.add(CounterexampleRecord(typed_class -> allowed moves))
    if res is SubDesignContract:   register child
    if res is CompositionCandidate: cert = compose(...);  promote PolicyProgram or agenda.add(cert.obligations)
```

Replay: deterministic operations replay exactly (input/param hashes, seed, container
digest); agentic operations replay as decision/provenance trace; promoted artifacts
replay as a re-walkable audit trail (levels A/B/C, center doc §7).

**Slice-0 proposer.** Slice 0 has no agent proposer and no full playbook engine. It uses
a deterministic `SeedTrajectoryPlanner` with exactly one trajectory:
`BIND -> ESTIMATE -> VERIFY`. This is a temporary planner fixture, not GY-C1 playbooks.
Once GY-H lands, VOI can decide whether to stop after the fixed trajectory or emit the
matching typed terminal; it still cannot execute non-active operations in Slice 0.

**ConstraintStore producers.** Slice 0 starts with a minimal ConstraintStore built from
`PolicyIntent` scope, catalog/source-contract facts, method applicability requirements,
and existing authority ceilings attached to reused `pdc`/`ir` contracts. Later phases add
named A-side producers in this order: epistemic-regime/measurability constraints,
source/time/freshness constraints, legal/mandate constraints, capacity/participation
constraints, evidence-independence constraints, coupling constraints, and
human-decision/stakes constraints. An empty ConstraintStore is allowed only for a Slice-0
fixture whose proof states that no such producer is yet in scope; after the owning phase
lands, "empty because not wired" is a `producer_missing` blocker.

## 6. A's in-loop role — formal gate + authority derivation

A's first job each cycle is the **formal gate**: a type system over operations/methods
that checks mechanically-checkable preconditions and emits `ApplicabilityResult` with
actionable repairs (DiD needs ≥2 groups + pre/post + panel index; continuous method on
integer outcome → `repair: count_model|to_rate|poisson`). It is **derived from existing
metadata** (foundry method `input_slots`/dtypes/`requires`, IR contract assumptions),
not hand-written per method (Rule 12). It is **not** semantic judgment ("is DiD optimal
here") — that matures iteratively on output artifacts. The agent may propose freely and
assemble method chains; it may not bypass the formal gate, and it may not write a Ring-2
field.

A's second job is **authority derivation** after execution. `A.verify(res)` must emit an
`AuthorityDerivationTrace` (§3.5.4) and compute the stamped `AuthorityBoundary`
independently from the operation's self-description:

- `OperationContract.authority_transform` is a **Ring-1 hint**: the operation declares
  what it believes it preserves/weakens/calibrates/transports/simulates/composes. A
  verifier may use it as an input to check, but never as the stamped result.
- `evidence_kind` is derived from producer roots + method classification:
  `catalog/fetch CAS root -> measurement`; deterministic transform over measurement
  roots -> `derivation`; validated substitute -> `proxy`; cross-scope estimate ->
  `transport`; partial-identification method -> `bounds`; structural/ABM/simulation
  method -> `simulation`; LLM/expert-only output -> `elicitation` and shadow unless a
  separate producer validates it.
- `decision_grade` is derived from gate/envelope/diagnostics, not from the operation:
  no producer root, failed hard precondition, out-of-envelope output, open blocking
  obligation, or unresolved critical counterexample -> `unsupported`; measured or
  derived facts without identification for the requested claim -> `descriptive_only`;
  in-envelope identified/bounded/calibrated output with required data shape,
  applicability passed, calibration refs where required, and critical counterexamples
  closed -> `advisory_admissible`; `decision_admissible` is outside Slice 0 and requires
  the production-posture promotion gate, policy/legal/stakes floors, and no blocking
  obligations.
- A mismatch between declared `authority_transform` and computed boundary creates a
  `CounterexampleRecord` or downgrades/rejects the artifact; it never upgrades authority.

Agent boundary, stated operationally:

- **Agent may:** propose next Operations; assemble an internal `MethodPlan`; call tools;
  request data/human input; generate candidate artifacts; estimate expected usefulness
  or VOI inputs; explain a selection rationale as Ring-1 trace.
- **Agent may not:** bypass formal applicability checks; mutate `AuthorityBoundary` or
  any Ring-2 field; promote a shadow artifact; close unresolved obligations; classify
  abstention as grounded without the search-quality gate; compose subdesigns without a
  `CompositionCertificate`; mark search complete without a `SearchExitContract`.

Agent-provided VOI or usefulness estimates are also Ring-1 candidate inputs. GY-H's
deterministic VOI policy normalizes, clips, rejects, or accepts them and records the
decision in `VOISelectionAudit`; an agent cannot steer authority by framing the score.

## 7. Decision 3 — recursive SubDesign + port-authority composition (full)

A child Workspace exports only a `SubDesignContract` (assume-guarantee). **Authority
lives on ports**, never on the sub-design as a whole. The parent composes only through
ports. `AuthorityBoundary` is multi-dimensional (`authoritative_for` ∧ `may_not_use_for`
+ `evidence_kind` ∧ `decision_grade` + evidence basis), never a scalar.

Composition `compose(subdesigns, claims, graph) → CompositionCertificate |
CompositionInvalid` runs three stages in order:

1. **CouplingGate** — `independent`: compose by ports; `sequential`: downstream port
   capped by upstream port; `shared_resource`: requires a `CapacityAggregation`
   operation; **`feedback`: not independently composable** → joint sub-Workspace or an
   explicit `FIXPOINT/EQUILIBRIUM/SIMULATION` operation with capped authority; `unknown`:
   fail closed / discover coupling. Feedback is **not a warning** — it changes the
   mathematical object.
2. **PerPortAuthorityFlow** — lattice `meet` along dependencies: `authoritative_for =
   ∩ upstream`, `may_not_use_for = ∪ upstream`, `envelope = ∩`, `evidence_kind =
   evidence-ladder meet`, `decision_grade = min/upstream cap`, `obligations = ∪`.
   Empty `authoritative_for` ⇒ fail-closed for that use.
3. **EmergentClaimGrounding** — program-level claims are not inherited; they require own
   grounding (system-dynamics / sequencing-consistency / capacity-aggregation /
   cross-chapter counterexample search) and are capped by (weakest part) ∧ (system-model
   authority) ∧ (coupling certificate). It also consumes **evidence-independence (P14)**
   so support is not inflated by non-independent chapters (F15).

Promotion rule: **no `PolicyProgram` promotion without a `CompositionCertificate`**;
no composed claim exceeds child-port ∧ coupling ∧ emergent grounding authority.

## 8. Decision 5 — anytime exit + typed incompleteness + VOI (full)

Every Workspace exits with a `SearchExitContract`, never `success/failure`. **GY-H owns
this machinery** (terminals, `SearchIncompletenessRecord`, `BudgetVector`, the
ceiling-gate, and the VOI estimate + continuation); GY-B exposes only the
`rank_by_VOI` hook and a degenerate single-terminal exit until GY-H lands.

- **8.1 Multi-budget**: `BudgetVector`. Different exhaustions → different honest stops
  (compute → `budget_exhausted:compute`/`frontier_stable`; acquisition →
  `acquisition_required`; expert → `human_decision_required`; freshness/recall →
  `search_ceiling_repair_required`; novelty → `frontier_stable` iff search quality ok).
- **8.2 Typed terminal states** (§4.2 `SearchExitContract`).
- **8.3 `SearchIncompletenessRecord`** makes stopping an audit object; the frontier is
  always anytime-emittable as shadow with an honest boundary.
- **8.4 Domain-ceiling vs search-ceiling is a formal gate.** `grounded_abstention`
  allowed **only if** recall@known-seeds ≥ threshold AND freshness ok AND no required
  source class missing AND no high-VOI untried move AND no verifier gap AND no core
  tool failure. Otherwise `search_ceiling_repair_required` (formalizes F1/F8).
- **8.5 VOI is the single currency**: continue while `max(VOI(action)/cost(action)) ≥
  threshold` and hard budgets allow; else terminate with the matching state. "Buy data
  / run a pilot" → `acquisition_required` with a costed rung-7 plan, not failure.
- **8.6 Terminal precedence is deterministic.** When several terminal predicates fire,
  choose the first applicable class in this order: `a_spec_gap` / verifier-contract gap;
  `tool_failure` for a core producer with no repair path; `composition_invalid` /
  `recursive_blocked` for invalid decomposition/composition; `search_ceiling_repair_required`
  for recall/freshness/source-class/core-search deficits; `human_decision_required`;
  `acquisition_required`; `budget_exhausted:<kind>` when a hard budget blocks the next
  required/high-VOI action; `frontier_stable`; then `grounded_admissible` /
  `grounded_partial_admissible` / `grounded_abstention`. Positive terminals are emitted
  only after all higher-precedence blockers are absent.

**3 and 5 are linked**: a `SubDesignContract` embeds its `SearchExitContract`; a parent
cannot paper over a child's incompleteness (a child `acquisition_required` forces the
parent to fund, cap, or escalate).

## 9. The build tasks

Each task names its **posture** (`wire-existing` / `extend-existing` /
`consolidate-existing` / `build-new`), the **rows / findings** it acts on, and is sized
to roughly one focused PR. A `build-new` overlapping a `wire-existing` owner is a
design-review failure (Rule 1).

Every task's **Done when** also implicitly carries the §3.5.5 build-hygiene gate:
owner-first placement (P27), a `StrangleReceipt` with the default flipped for any path it
replaces or subordinates (P28, rule 9), and run-emitted/recomputed proof packets on a
representative substrate (P29). A task that leaves a parallel owner, an un-strangled legacy
default, or an authorial proof is **not done**, regardless of local test status.

### Phase 0 — the form (build-new; the binding hub)

- **GY-A1 — Ring-1 execution waist + field-permission framework.** build-new (`pdc`).
  The 9 Ring-1 contracts; the **field-level write-permission mechanism** that marks
  Ring-2 fields verifier-only (F2/rule 2); `gy_evidence_canon` canonical hashing into
  `ArtifactRef.content_hash` (F16). Done when: Ring-1 contracts + a test proving a
  non-verifier writer cannot set a Ring-2 field; no `pdc`→engine import.
- **GY-A2 — Ring-2 promotion waist + AuthorityBoundary lattice.** extend/build-new
  (`pdc`, per §3.5.2). The 8 Ring-2 contracts; the `AuthorityBoundary` lattice
  (`authoritative_for` ⊇-order, `may_not_use_for` ∪, envelope intersection,
  `evidence_kind` partial meet, `decision_grade` total meet) + `meet`; the
  deterministic Slice-0 authority derivation rule in §6; reuse `ir` analytics types as
  port vocabulary (F15). Done when: lattice `meet`/order unit-tested; mixed-axis
  examples in §13 pass, including measurement/descriptive, bounds/advisory,
  calibrated-simulation/advisory, and ungrounded-emergent caps; `AuthorityDerivationTrace`
  fixtures prove that `authority_transform` hints can only match/downgrade, never
  self-promote.
- **GY-B — Control loop skeleton + Operation registry + FormalGate + SearchLedger +
  Slice-0 fixtures.** build-new (`runtime/quality`). Minimal slice: one Workspace;
  active Operations are exactly `BIND/ESTIMATE/VERIFY`; `DISCOVER/ACQUIRE/REFINE/LOWER`
  may be registered only as fail-closed stubs until their owning tasks land; a
  deterministic `SeedTrajectoryPlanner` (`BIND -> ESTIMATE -> VERIFY`, not GY-C1
  playbooks); two fixtures: a committed **`Slice0FixtureManifest`**
  (`ua_msme_credit_worldbank_measurement`) as the catalog-supported groundable case and
  **tourism/local-development** as the ceiling/acquisition-heavy probe. Operation
  registry is **discovered** from engine registries (Rule 12). Quarry
  `policy_design/search.py`, `iteration_state_machine`, CAS+`artifacts_index`. Done
  when: both Slice-0 fixtures run to degenerate `SearchExitContract`s with
  `FrontierSnapshot` + `SearchLedger`; the groundable fixture expectations are read from
  `Slice0FixtureManifest`, not inline code; replay levels A/B/C implemented (F16); a
  Slice-0 invariant test fails if any non-active operation executes, if an agent/full
  playbook is used, or if the groundable fixture emits `grounded_admissible`/a
  `DesignCandidate`. (Honest typed exit = GY-H.)
- **GY-B2 — Production trigger + transition rule (one authority path).** build-new
  (`runtime/http` + control). Wire a control-plane request → `WorkspaceLoop`
  (intent-driven; **no `workflow_id`**). It is not enough to "augment/replace"
  `run_experiment`; the task must fix an explicit **transition rule** so two production
  paths cannot coexist and re-launder:
  - `/runs` (workflow path), `/runs/nl` (NL pipeline at `nl_pipeline.py:6596`), and the
    `workflow_run` job path (`run_lifecycle.py:1408`) either **route through the loop**
    or are marked **legacy-shadow**: their outputs are stamped `candidate_only` /
    non-authority (Ring-2 withheld) until migrated.
  - dashboard / public-export / lineage consumers read authority **only** from a
    loop-produced artifact with a verifier-stamped `AuthorityBoundary`; a legacy-path
    artifact cannot reach an authority surface.
  - **job-status honesty before F1:** until GY-F1 fully migrates all surfaces, any
    legacy-shadow or failed workflow path must also be marked non-authority at the job
    status/result layer (`candidate_only`, `repair_required`, or failed), not merely in
    artifact authority fields. A workflow failure cannot produce a clean completed job
    with an authority-looking result.
  - **durable-worker proof:** produce a `ProductionLoopRunProof` (§3.5.4) showing
    `enqueue_job -> ControlWorker lease -> _execute_workflow -> WorkspaceLoop ->
    SearchExitContract persisted to CAS/artifacts_index -> /runs readback`. A direct
    `WorkspaceLoop(...)` call or a direct `run_experiment(...)` call is only a helper
    smoke, never B2 completion evidence.
  - **invariant + test:** exactly one authority-bearing production path exists (the
    loop); a negative test asserts no second path can emit an authority-stamped artifact.
  Done when: a real queued control request launches a `WorkspaceLoop` through the
  durable worker path; every legacy entry is redirected or demoted to candidate-only at
  artifact **and job-result** level; `ProductionLoopRunProof` is persisted; the
  "single-authority-path" and "failed workflow cannot complete clean as authority"
  negative tests pass — closing both the Task-0 "built-but-untriggered" trap and the
  two-path/status laundering risk (F2, F12).

### Phase 1 — anytime-exit core + binding constraint (substrate + acquisition)

- **GY-H — Anytime exit + incompleteness + VOI (decision 5).** build-new. The full
  `SearchExitContract`/`SearchIncompletenessRecord`/`BudgetVector`, typed terminals, the
  domain-vs-search-ceiling gate (§8.4), deterministic terminal precedence (§8.6), and
  the **VOI estimate + continuation** (§8.5) with `VOISelectionAudit`.
  Placed before GY-E (which depends on VOI + `acquisition_required`). Findings: F1, F14.
  Done when: the groundable Slice-0 fixture exits as measurement-rooted
  `grounded_partial_admissible` at the **Estimate port only**; `grounded_admissible` is
  forbidden in Slice 0; the tourism ceiling fixture exits with
  `search_ceiling_repair_required` or `acquisition_required`; a poor-recall run yields
  `search_ceiling_repair_required`, not `grounded_abstention`; simultaneous-trigger
  tests prove terminal precedence; Slice-0 `BudgetVector` uses only the minimal subset
  named in §3.5.1.
- **GY-D1 — Catalog → measurement-root producer.** wire-existing (catalog) + build-new
  (root producer). Findings: F4. Wire `DatasetCatalogGraph` into Slice-0 `BIND` (and
  later `ACQUIRE` once GY-E activates it), not `RetrievalService(dataset_catalog=None)`;
  a real measurement-root producer so fetch writes a CAS artifact with producer-roots
  (fix the `persist_payload` no-op). Done when: a pinned construct resolves through the
  real catalog to a CAS-rooted artifact.
- **GY-D2 — Admission gates (connector + source-contract).** extend-existing. Findings:
  F5, F6. Per-connector **formal applicability gate** as `ApplicabilityResult`
  (rest.json/unpd/ukons → `repair_required`); the 16-facet source-contract/
  `DataRequirementSpec` admission as `VERIFY` preconditions before fetch. Done when:
  non-execution-ready connectors fail closed with repairs; a fetch with missing facets
  is blocked/downgraded.
- **GY-D3 — Semantic-adequacy gate + governed benchmark.** extend-existing. Finding: F7.
  A construct+scope adequacy gate + recall@known-seeds + freshness feeding
  `SearchIncompletenessRecord`; calibrated relevance (not `similarity=1.0`). The gate's
  **source of truth is a committed, versioned benchmark artifact** (not the gate's own
  output) so adequacy cannot become a structural pass again:
  - **labels:** a human-labelled construct→admissible-dataset gold set, with a named
    owner/expert author + a reviewer, provenance (who/when/rule_version) — a Ring-2
    governed artifact.
  - **thresholds:** explicit per-posture floors (e.g. construct+scope `precision@5`,
    `recall@known-seeds`) declared in the benchmark, not inline in code.
  - **negative controls:** known-irrelevant datasets that the gate MUST reject + known-
    groundable seeds it MUST find; the gate fails if a negative control passes or a seed
    is missed. (Extends the P2 five-case silver benchmark; reused by GY-V3's labelled set.)
  Done when: the benchmark artifact is committed + governed; the gate computes against it;
  precision/recall@seeds recorded; a negative-control pass or below-floor precision fails
  the gate; a no-hit with poor recall routes to `search_ceiling_repair_required` (GY-H),
  not abstention.
- **GY-E — Acquisition loop (RequiredDataSpec → DataNeedSpec → fetch / costed plan).**
  build-new producer + orchestrate. Reuse `DataNeedSpec` (do not invent a type). Build
  the `ACQUIRE` operation + the `acquisition_required` terminal carrying a costed rung-7
  plan via VOI (now available from GY-H). Done when: a pinned identification gap yields
  a `DataNeedSpec` resolving to a fetch (GY-D1) or an `acquisition_required` exit with a
  named missing distribution + cost.

### Phase 2 — subordinate engines + repair the spine rot

- **GY-C1 — Engines as Operations (adapters) + playbooks.** wire-existing. Findings:
  F2. `LegacyNodeAdapter` lands incrementally, only for nodes needed by the active
  playbook/operation under implementation (no 37-node mega-drop); each adapter declares
  ports/preconditions/authority-transform as a Ring-1 hint; the three workflows →
  `Playbook` trajectories the loop may deviate from; intent→operations (no
  `workflow_id`). Done when: at least one playbook trajectory runs as a default
  trajectory and the loop can deviate on a counterexample; adding another legacy node
  follows the same adapter conformance test.
- **GY-C2 — Spine-rot repair (separated, per stop-rule).** extend-existing/repair.
  Findings: F8, F9, F14. Repair: the lex optional-bounds `None→0.0` bug as a `REFINE`/
  search `ApplicabilityResult` precondition with frontier provenance (P25); the
  `run_normative_arbitration` outcome re-validation + the phase-5 judge stack; the
  blocked-input producer (`data_causal_graph`, producer_missing) + the missing input
  ports (`causal_variables`, `observational_data_ref`). **Lands before any
  governance-to-authority** (governance of a rotten asset is forbidden). Done when: the
  governance tail produces a valid verdict on real input; lex search yields a valid
  bounded frontier or a typed `search_blocker`.
- **GY-C3 — Foundry route-consumption + ceilings as constraints.** wire-existing.
  Findings: F10, F15. `ESTIMATE/SIMULATE` consume real foundry method outputs
  (`dag_consumed_method_outputs_count > 0`) with measurement-rooted authority;
  obligation/participation/method-requirement ceilings become ConstraintStore
  constraints A consumes (never inferred). Done when: the slice runs an `ESTIMATE`
  consuming a real method output stamped with a measurement-rooted `AuthorityBoundary`.
- **GY-I — Agent as Ring-1 proposer + event-backed G6.** extend-existing. Finding: F11.
  The agent proposes operations / assembles `MethodPlan`s (Ring 1); it cannot write
  Ring-2 fields. Emit role-event artifacts (`OperationInvocationRecord` +
  `AgentDecisionRecord`) for PI/drafter/critic/tool-loop; wire `run_tool_loop`; register
  KnowledgeToolkit tools (fix 3/20). Agent VOI/usefulness scores are candidate-only and
  pass through GY-H normalization. Done when: an agent run records its tool-loop as
  Ring-1 events; a no-client run blocks with no synthetic audit; Ring-2 writes by the
  agent are rejected by construction; a biased agent score is clipped/rejected in
  `VOISelectionAudit`.

### Phase 3 — authority surfaces behind one boundary

- **GY-F1 — Authority across surfaces + worker.** extend-existing. Finding: F12. Run/
  artifact/lineage/export/dashboard/public packet consume `AuthorityBoundary`; the
  worker job must not complete clean on workflow `fail`; a failed/candidate workflow is
  blocked or visibly downgraded. Done when: a failed-workflow fixture is blocked/
  downgraded across all probed surfaces.
- **GY-F2 — Secret/PII gate + CAS integrity/authority backing.** extend-existing.
  Finding: F12. Raw `/artifacts/{id}/content` + `/download`, DAG bundles, connector
  request/response payloads, CAS manifests, dashboard/public/export packets all pass a
  systematic `SecretAndPIIScanReport` (§3.5.4); DAG/loop CAS outputs carry
  `manifest.authority`. CAS authority is not only "manifest present": prove digest
  semantics over canonical bytes, dedup behavior, mutation/tamper rejection, GC
  survivability from report-index/lineage/workspace references, and dereferenceability
  through a `CASIntegrityReport` (§3.5.4). Done when: no scoped secret/PII fixture leaks
  through raw or public routes; loop CAS artifacts carry an authority manifest; duplicate
  payloads dedup to the same digest; a tampered blob is rejected or re-digested; GC dry
  run retains every authority-bearing artifact referenced by reports/lineage/workspaces.
- **GY-F3 — Time/source admission envelope + S12 + diagnostic-field boundary.**
  extend-existing/consolidate. Findings: F12, F13. A composed time/source admission
  envelope (catalog watermark, source observed/published/updated times, ingestion,
  effective/legal-valid time, transaction time, as-of/replay time, run/node execution
  times, retention/expiry); S12 G5 pass refs dereference to produced
  `ValueOfInformationAllocation`/`ResourceAllocationPolicy` objects or are downgraded;
  the 406 diagnostic pass fields are enumerated in an `AuthorityCandidateInventory`
  (§3.5.4), each with producer/source, field path, status text, candidate-positive rule,
  firewall, exclusion reason, resulting boundary, and false-exclusion review. Done when:
  S12 refs dereference or are candidate-only; every time mismatch blocks/downgrades or
  creates an obligation; all 406 candidate-positive rows reconcile to the validator
  aggregate; false exclusions are either zero or named repair tickets; diagnostic pass
  fields are not laundered.

### Phase 4 — scale (recursion + composition)

- **GY-G — Recursion + composition (decision 3) + promotion gate.** build-new (D2.6).
  Findings: F14, F15. `DECOMPOSE`/`COMPOSE`, `SubDesignContract`, the three-stage
  composition operator (incl. P14 evidence-independence), `CompositionCertificate`, the
  D3.8 promotion-gate extension. Done when: a two-chapter decomposition composes through
  ports with a certificate; a feedback decomposition is rejected
  (`composition_invalid:feedback_requires_joint_grounding`); an emergent program claim
  is capped to its own grounding.

### Cross-cutting — artifact/case lifecycle

- **GY-M1 — Artifact-family lifecycle registration (PHASE-0 HARD GATE).**
  build-new/extend-existing. Finding: F18. **Must land before any GY task emits a new
  committed artifact** — otherwise the build (and even the V-battery) produces unregistered
  surfaces, recreating the exact gap Task 0 found. Register the GY/loop generated/
  public-surface family in `architecture/generated_artifacts.toml` + `inventory.json`
  with owner / regeneration command / stale-output behavior / drift gate; decide the
  classification (`generated_committed` / `source_committed` / `surface_out_of_scope`).
  Done when: a new GY artifact cannot be committed without a registered lifecycle entry
  (a drift gate enforces it), and the generated-public-lifecycle validator is green for
  the GY family.
- **GY-M2 — GX reducer case-parameterization.** extend-existing. Finding: F14.
  Parameterize the GX reducer CLI / `data_home` for arbitrary case input so the tourism
  slice — not only the pinned ua-msme — validates. Runs before GY-L / GY-V (which
  validate non-pinned cases). Done when: the GX validator runs on the tourism case, not
  only the pinned ua-msme `data_home`.

### Parallel / near-term and follow-on

- **GY-J — Graded-outcome routing (fork-independent near-term).** wire. Finding: F17.
  Route partial evidence to `grounded_partial_admissible` + downgrade (research/governed;
  production strict per ADR-0174) using existing statuses. Independent of the mode
  decision — may start immediately. Done when: a publish-with-limitation case exits
  `grounded_partial_admissible`; `useful_design_rate` moves off 0 honestly.
- **GY-K — L2 growth (scholar/OpenAlex provider).** build-new provider (follow-on).
  Finding: P2. Provider in `scholar/search`; span-grounded design-tiered claims into L2;
  measured extractor accuracy; SKG query traces + no-hit frontier; web bundle ≠ L2
  authority. Done when: a credit-guarantee→firm-survival query ingests span-grounded
  claims with recorded accuracy.
- **GY-L — Outcome run (value check).** Run the pinned case through the loop end-to-end
  via the production trigger (GY-B2); persist the typed `SearchExitContract`,
  `evidence_kind`/`decision_grade`, ladder rung, and replay proof. Done when: the
  pinned case produces a terminal outcome
  (`grounded_partial_admissible` | `grounded_abstention` | `search_ceiling_repair_required`
  | typed blocker) with input/output hashes, producer roots,
  `evidence_kind`/`decision_grade`, and incompleteness recorded; GX validator passes on
  the new artifacts.

### Phase 5 — B-on-A Generation Cycle (subordinate the generative engine to A; close the loop)

GY built and hardened **backbone A** — the engines subordinated behind the two-ring
waist, the firewalls, and the honest *single-pass* terminals. The GY-N0 investigation
(`architecture/policy_design_case/layer3_gy_n0_investigation.md`) then proved that the
generative, causal, value, transport, VOI, monitoring-primitive, and world-substrate organs
**already exist and are real under Python 3.14** — but as **decoupled parallel worlds**: real
LLM drafter/formalizer/critic organs beside a scripted default generator; the foundry
causal/Bayesian/transport/joint-simulation engines beside a single-pass descriptive loop; the
layer-2 *shadow* design search with a hardcoded candidate; `fabric/world` (a bitemporal
epistemic fact store) and the foundry `GlobalState`/NCM/GCM mechanisms with **no
`WorldModelRecord` binding them**; and G4/Ring-2/P14/S6–S8 enforcement that nothing in-cycle
sequences. So this phase is **predominantly REWORK / WIRE over real organs**, with a small set
of **narrow BUILD-NEW bridges** (canonical `DesignProblem`, `InterventionAtomBinding`,
`WorldModelRecord`, `JointSimulationHorizonController`, the acquisition receipt, and the cycle
controller). No new heavy dependency is added; the value path stays on **Python 3.14**
(DoWhy/EconML/CVXPY are unavailable there and are not required — the reachable
statsmodels/JAX/SciPy/pymoo causal, Bayesian, and transport methods compute real value).

This phase **subordinates the generative engine B under the honest backbone A in one real
cycle** — plain-language request → typed `DesignProblem` → B proposes with high freedom → A
grounds / gates / **values against a named `WorldModelRecord`** → on ceiling or acquisition the
cycle **executes acquisition and revises** → re-enters → B is **promoted to real design
authority only when A has grounded it**, else honest shadow / abstention. **B-on-A,
shadow-first.** Tasks **N1–N3 build the three typed bridge artifacts the cycle operates over —
the world model is a foundation that precedes the cycle controller and the value gate**; N4–N10
are the cycle itself, predominantly rework/wire over the real organs. The deployed-policy
learning loop (where the world model *grows* from observation) is the genuinely greenfield
horizon and is **Phase 6**. Each task below is scoped to a roughly comparable amount of work.

> **Governing law of this phase — no new parallel worlds (P27/P28/P30).** Every relevant
> existing asset is **either USED (as-is, or reworked to fit the best approach) or
> DELETED.** Nothing is left as a live parallel owner beside a new one. The three known
> parallel worlds above are reconciled into **one** subordinated cycle; their generative
> organs are consumed or reworked, and the superseded paths are **strangled and deleted in
> the same change** (StrangleReceipt, §3.5.5). This phase opens with an exhaustive census
> (GY-N0) that assigns **every** touched asset a disposition before any wiring begins.

- **GY-N0 — Disposition ledger + consumption validator (PHASE HARD GATE).** build-new
  ledger + recomputing validator. The repo-wide census is **done** — the GY-N0 investigation
  notebook (`architecture/policy_design_case/layer3_gy_n0_investigation.md`, 5 passes) is the
  code-grounded substrate. Distil it into a **committed disposition ledger**: every
  cycle-relevant owner → `{USE_AS_IS | REWORK_TO_FIT | DELETE}` with file anchor,
  best-approach rationale, consuming GY-N task, and (for REWORK / DELETE) a StrangleReceipt
  obligation. Record the **runtime gate**: Python 3.14 keeps EconML/DoWhy/CVXPY unavailable
  and statsmodels/JAX/SciPy/pymoo + the foundry Bayesian/transport primitives reachable
  (stay on 3.14; do not move the baseline for EconML). Build a recomputing validator that
  fails if a GY-N task ships without consuming / strangling its named owner, or if any asset
  remains a **live parallel owner**. Done when: the ledger is committed, the validator is
  green over the current tree, the 3.14 method-availability gate is recorded, and every
  superseded path has a StrangleReceipt obligation pointing at its consuming task.
- **GY-N1 — Canonical `DesignProblem` (foundation bridge).** build-new bridge type +
  front-door rework. Build one canonical typed `DesignProblem` over the existing problem
  surfaces (`assurance_case.PolicyIntentEnvelope`, Scientist `ProblemFrame`, IR governance
  `ProblemFrame`, IR `ModelSpec`, verified `PolicyRequestFrame`): it spans NL provenance,
  authority profile, jurisdiction / time semantics, objectives / constraints / stakeholders,
  outcome-of-interest, candidate-lever space, evidence / acquisition needs, generator
  projection, and the IR formal-problem ref. Rework `nl_pipeline` to **emit** it and the
  cycle to **consume** it. **Strangle** the silent fork into `scientist_policy_verified` as
  the universal generation path and `run_intent`'s untyped-dict entry. Done when: a
  plain-language request produces a validated `DesignProblem` the cycle consumes; the
  verified-fork and untyped-dict entry are strangled with receipts; a hallucinated /
  unsupported constraint fails closed (no invented admissibility). `P10`/`P15`/`P30`.
- **GY-N2 — `InterventionAtomBinding` (foundation bridge).** build-new content-bound
  bridge artifact. Bind the two existing halves into one atom — Trinity
  `InterventionSpec` + linker (`ir/governance/policy_spec.py`, `ir/linker/_trinity_linker.py`:
  operator / target / schedule / params / read-write state slots) and proof-kernel `do()`
  expressions (`ir/analytics/interventions.py`: `NodeIntervention` / `QueryTarget` / estimand
  / identification plan). Fields per the GY-N0 seam contract: `operator_kind`,
  `target_selector` + `target_world_slots` / `read_slots`, `direct_effect_bundle`,
  `causal_do_expr`, `intended_downstream_estimand`, `causal_path_or_identification_plan_ref`,
  `world_model_record_ref`, `content_hash` / provenance / lifecycle `status`. Do **not** build
  a second lever hierarchy. Done when: a candidate's action binds to a typed `do()` + estimand
  + world-slot atom with a content hash; an atom whose direct-effect bundle and causal path do
  not content-bind fails closed; `measurement_expectations` is downgraded to metadata once the
  estimand exists. `P31`/`P32`.
- **GY-N3 — `WorldModelRecord` + build/bind/version lifecycle (FOUNDATION; UNIFY_EXISTING).**
  build-new bridge type + lifecycle over four real substrates — `fabric/world` (epistemic
  facts + provenance + bitemporal validity + snapshot / branch), foundry `GlobalState` / NCM /
  GCM mechanisms + the `DataSnapshot → GlobalState` input binding (`foundry/data_plane/bindings.py`),
  IR `ModelSpec`, and SKG / literature priors. Fields per the GY-N0 seam contract
  (identity / authority, scope / region / time / resolution / `branch_mode`, fabric-world ref,
  data-forge binding ref, model_spec / mechanism refs, foundry `input_bindings_ref`, SKG ref,
  policy-slot map, limitations). Construct + bind + **version** a simulatable world the cycle
  names; do **not** build a second world store (`P27`). The deployment / posterior write-back
  is **Phase 6**. Done when: a `WorldModelRecord` binds the four substrates into one versioned,
  regional, data-bound, simulatable world; the cycle's value step **names the exact world
  version** it runs against; a record missing any required binding fails closed. `P27`/`P30`.
  **Foundation — precedes GY-N6 and GY-N8.**

#### Foundation: production-data substrate lift + free-grow (GY-S)

The cycle grounds / simulates / values against a **real** world, not toy fixtures (the GY-N3 empty-world finding is
the canary). PolicyOS already holds ~32GB of richly preprocessed production data — L1 DCAT catalog (137k datasets,
3.7M observations), L2 Scholar KG (7.9k curated causal claims, transport scores, 62k parameter estimates), L3 Lex KG
(6M provisions, 374k thresholds, 156k amendments), L4 Ukraine corpus (8.8M agents + firm/distress/budget panels), L5
calibration internals (trust-tier / identification-mode / schema-regime registries + bias-corrected derivatives), L6
agent-sim bundle (intervention knobs, lex→knob map, observation→method manifest). Much of it is **not yet lifted to
runtime authority**. These foundation tasks **lift the existing substrate (wire-existing, do not rebuild)** and build a
**free-grow registry** so the world model GROWS as data arrives — future production data, GY-N7-acquired data, and
Phase-6 deployment-discovered data all register into the same substrate WITHOUT re-architecting. They land with the
foundation bridges (GY-N1–N3) and feed GY-N3 (real world binding), GY-N4 (grounding), GY-N8 (value / calibration /
transport), and GY-N2 (lever space).

> **The GY-S substrate IS the credal state of the target spec (Rev 11).** Per the formal target
> spec (`docs/system-design-decisions/policy-design-search-target-spec.md`), the L1–L6 substrate
> does not merely "carry data" — it **initializes the separated credal components** the value gate
> and promotion gate reason over. Each GY-S lift must therefore expose its data as the
> corresponding credal contract, not as raw fields: **L1 observations / L4 corpus state → `K_world`
> + `Obs`; L5 `identification_mode` (point/partial/proxy) → `K_id`; L5 `measurement_registry` /
> proxy_mappings → `K_cal` + `K_meas`; L5 trust_tiers → `DataTrust`; L2 `transport_scores` →
> transportability scope; L2 `contested_edges` → structural ambiguity; L3 thresholds / normative
> facts → `K_impl` + `K_norm`; L3 amendments + L5 `schema_regime` → epoch / temporal validity; L6
> knobs / lex_map / observation manifest → lever space + method routing**. The binding rule that
> follows: **a lifted state is set-valued, not point** — point identification → a narrow set,
> partial → an interval, proxy → a wide set; the L5 `identification_mode` selects the value-set
> type; a calibration scope-mismatch downgrades proxy → partial → blocked, fail-closed. Simulation
> output (`K_sim`, GY-N5) never shrinks `K_world` (L1/L4). The typed carrier for these set-valued
> states is **GY-N-V `ValueOuterSet`** (below).
>
> **Every GY-S task is bound by the four §3.5.6 completeness gates** (full-denominator coverage;
> fail-closed on a fake/novel input = owner-validation, not trust; data-only free-grow; the contract
> mutates the decisive validation property). They are the distilled lesson of this block — front-load
> them so a lift is real and load-bearing, not a happy-path shell.

- **GY-S0 — Production-data substrate registry + free-grow lifecycle (FOUNDATION GATE).** build-new registry over
  existing catalogs. A runtime-authority **substrate registry** that catalogs the production-data world by
  source / family with coverage / trust-tier / version / provenance / schema-regime, **content-addressed and
  versioned**, which the WorldModelRecord builder (GY-N3), the value gate (GY-N8), grounding (GY-N4), and the lever
  space (GY-N2) CONSUME. **Free-grow:** a new source / family / dataset registers (with its coverage / trust / version
  / provenance) and becomes available to the world model with **no code change** — the same registry absorbs future
  production data, GY-N7-acquired data, and Phase-6 deployment-discovered data. **Lift, do not rebuild:** reuse the L5
  `measurement_registry.json` (trust_tiers / coverage_rules / proxy_mappings), `identification_mode_registry.json`,
  `schema_regime_registry.json`, and the L1 DCAT `ds_datasets` quality / coverage metadata. Done when: the registry
  catalogs the L1–L6 substrate from the existing catalogs (no re-derivation); a new (test) source / family registers
  and is consumed by the WorldModelRecord builder with no code change; a substrate version is content-addressed and
  nameable (like the world version). `P27`/`P30`.
- **GY-S1 — Data-state substrate lift (L1 DCAT + L4 corpus + L5 calibration).** rework / wire over existing data.
  Materialize the real **L4 Ukraine corpus** (8.8M agent registry + firm_fundamentals / distress / budget panels;
  unified `period_id` / `record_hash` / `schema_version` / `source_snapshot_id`) into the world's `GlobalState` via the
  Data-Forge / Foundry binding, with the **L1 DCAT catalog** (`ds_datasets` / `ds_observations` / `ds_metric_bindings`)
  as the required-vs-available + coverage authority, gated by the **L5 calibration** (trust_tiers, identification_mode,
  schema_regime v1-prewar / v2-wartime changepoint + boundary buffer). The GY-N3 WorldModelRecord binds this REAL
  populated, queryable, content-addressed world (a real world is never empty). **Set-valued lift (Rev 11):** the bound
  state is **not point** — it carries a `GY-N-V ValueOuterSet` whose type is selected by the L5 `identification_mode`
  (point → narrow set; partially → interval; proxy → wide set), with the L5 trust_tier as its `DataTrust` and the
  measurement scope as its `K_cal`/`K_meas` obligation; a calibration scope-mismatch downgrades proxy → partial →
  blocked fail-closed. This is the substantive (not label-only) form of the proxy-honesty fix: toggling
  `identification_mode` must change the **bound set**, not just metadata. Done when: a WorldModelRecord builds a
  populated content-addressed world from the real L4 corpus bound through L1 / L5; the bound state is a typed
  `ValueOuterSet` whose width tracks the L5 `identification_mode` (proxy is bounded, never a point scalar); the value /
  identification respects the L5 trust_tier + identification_mode + schema-regime for the bound family; the same slice
  is **deterministically content-addressed** (same slice → same hash); the substrate registers in GY-S0.
  `P10`/`P14`/`P27`/`P29`.
- **GY-N-V — `ValueOuterSet` (set-valued value foundation contract; lands with GY-S1).** build-new bridge type +
  reuse/extend. The typed carrier of **credal value** the whole cycle reasons over — the typed home for the proxy-bounds
  GY-S1 would otherwise hand-roll into `HouseholdCellState`. A foundation contract **alongside N1–N3** (it must exist
  before S1 binds a bounded state, before N8 values against it, before N6 compares). Representations per the target spec
  (§7.3–7.4): `interval_box | polytope_support_functions | scenario_set | unknown`, each carrying
  `identification_status (point|partial|proxy|blocked)`, `assumptions` + `assumption_status`, `calibration_scope`,
  `world_model_record_ref`, `width`, `epoch`, and a `representation_status (certified|search_only|unknown)` — an
  **uncertified** sample-only set may train the surrogate but **cannot** define a promotion-grade `V_out`. Reuse the
  existing `pdc/_impl/layer2_readiness.py` value/uncertainty seeds; do **not** build a second value type. Honest
  comparison lives here too: a pairwise `compare` returns `dominates | incomparable | unknown` and **returns `unknown`
  on solver timeout — never silently "dominated"** (the marginal-interval fallback is the safe default; the joint
  coupled solve is opportunistic). Done when: GY-S1 binds its household state as a `ValueOuterSet` (proxy → bounded,
  point → narrow), GY-N8 values against it, and GY-N6 compares with the `unknown`/incomparable discipline; an
  uncertified set cannot mint promotion value; a missing identification status fails closed. `P10`/`P14`/`P27`/`P32`.
- **GY-S2 — Knowledge substrate lift (L2 Scholar KG + L3 Lex KG).** rework / wire over existing data. Bind the real
  **L2 Scholar KG** (7,868 curated causal claims with direction / strength / design-tier / trust; SKG edges +
  transport_scores; 62,248 parameter_estimates with CI; contested edges; the `ac_skg_versions` store) as the SKG causal
  priors + transport that grounding (GY-N4), value (GY-N8 — real `transported_limited`), and the atom estimand consume;
  bind the real **L3 Lex KG** (374,516 rule_thresholds metric+operator+value+unit; 156,196 amendments with
  `effective_from`; normative facts; entities) as the admissibility / obligation + temporal-competence authority the
  DesignProblem constraints (GY-N1) and the atom (GY-N2) consume. Lift (both are in data form, unused in runtime).
  **Credal binding (Rev 11) — the worked example the spec lacks:** an L2 `parameter_estimate` (estimate + CI +
  `design_quality_tier` + `trust_score`) is **world evidence with an identification status**, so it lowers to a
  constraint on `K_world` / `K_id` (a `ValueOuterSet` whose width is the CI and whose `identification_status` follows
  the design tier); the claim's **`transport_score` to the design scope sets the transportability bound**
  (`transported_limited`, GY-N8); an L2 **`contested_edge` lowers to structural ambiguity** (a disjoint / wide scenario
  set, never a point). L3 thresholds / normative facts lower to `K_impl` / `K_norm` admissibility, and L3 amendments'
  `effective_from` feeds the GY-N12 epoch / temporal-validity layer. Done
  when: candidate grounding resolves against the real L2 SKG (the `ac_skg_versions` store GY-N3 already resolves) and an
  L2 estimate produces a `ValueOuterSet` constraint with CI-width + transport-bounded scope; a `contested_edge` yields a
  wide (not point) set; a DesignProblem admissibility constraint resolves against a real L3 lex threshold / amendment
  with `effective_from` temporal competence; both register in GY-S0. `P10`/`P14`/`P15`/`P27`.
- **GY-S3 — Intervention substrate lift (L6 agent-sim bundle).** rework / wire over existing data. Bind the real
  **`intervention_knob_dictionary`** (budget_allocation_multiplier 0–2, procurement_shock −1..1, tax_relief_rate
  0–0.5) as the InterventionAtomBinding lever space (GY-N2); the **`lex_intervention_map`** (law→knob cross-modal:
  budget_law → budget_allocation_multiplier, …) as the L3-lex→lever binding; the **`observation_to_contract_manifest`**
  (family→foundry method: firm_fundamentals → foundry.ml.survival_data.v1, budget_flows →
  foundry.causal.panel_observational_data.v1, …) as the value-method routing (GY-N8). Done when: an
  InterventionAtomBinding operator / lever resolves against the real knob dictionary + lex_intervention_map (a
  law-bound lever traces to its statute); the GY-N8 value-method selection routes via observation_to_contract_manifest;
  registers in GY-S0. **Rev 11:** the knob dictionary is the spec atom's `(op, π)` lever space (GY-N2) and the
  `observation_to_contract_manifest` is the method-routing input to both the GY-N4 graph-causal **surrogate** and the
  GY-N8 value-method selection. `P27`/`P32`.

The GY-S0 free-grow registry is the **shared growth mechanism**: GY-N7 acquisition and the Phase-6 learning loop write
new data / discovered couplings into the **same** growing substrate, so the world model expands over time without
re-architecting.

- **GY-N4 — Generation under A (reuse the real LLM organs; shadow-only).** rework-existing +
  delete. Make the canonical generator the **real** LLM organs (`LLMDrafterAgent.draft_policy`,
  `LLMFormalizerAgent.formalize`, `LLMCriticAgent.critique`, `MultiPassLLMDrafter`) with a
  **model-profile preflight**: the live gateway supports Qwen / MiniMax / Kimi and **not** the
  documented `gpt-5-mini` — validate against `/models` before a run and fail closed on an
  unsupported profile. Generated candidates enter as `InterventionAtomBinding` **shadow
  (`candidate_unverified`)** through the candidate-firewall. **Strangle / delete** the scripted
  and mock generator sources as authority (verified-policy fixed tax-subsidy, `MockDrafter` /
  `MockFormalizer` / `MockCritic`, the S2 hardcoded `credit_guarantee` body) — keep them
  fixture-only. **Firewall + surrogate (Rev 11):** make the spec's role separation explicit —
  *Proposer proposes, Surrogate prioritizes, Validator certifies*; the **"Not certificates"** set
  (LLM explanation / NL rationale, high proxy score, unverified simulation, posterior CI without a
  coverage argument, self-reported causal claim, untyped JSON) **cannot** promote (this is our P32 +
  P15 + P29 made explicit at the generator boundary). Add a **graph-causal surrogate** for
  *prioritization only* — wire the foundry NCM / GCM + SKG priors (and the L6
  `observation_to_contract_manifest` routing from GY-S3) as a search-ranking model with trust level
  `proposal_only < search_guiding < calibrated_predictive < certified`; the surrogate ranks /
  estimates VOI but **never certifies**. Done when: ≥3 **diverse real** candidates from a
  `DesignProblem`, each shadow through the firewall; the scripted / mock / hardcoded generators are
  strangled with receipts; the preflight rejects an unsupported model; a candidate cannot reach
  authority without A; a surrogate score (any trust level below `certified`) cannot mint promotion.
  `P15`/`P27`/`P28`/`P29`.
- **GY-N5 — `JointSimulationHorizonController` (replace the ABM stub).** build-new thin
  controller over the **real** foundry joint engines — the shared-state program executor
  (`foundry/execute/_internal/graph`), NCM parallel worlds (`ncm_engine.py`), and the coupled
  DES / ABM queue horizon (`simulation/coupled.py`) — plus the coupling-composition gate. Per
  the GY-N0 seam contract it takes a `WorldModelRecord` + intervention atoms + horizon / engine
  plan / escalation, runs **individual → pairwise → joint** horizons, and returns per-atom and
  joint trajectories, interaction terms, shared-resource / feedback classification,
  general-equilibrium limitations, and a **content-bound simulation proof / calibration
  receipt that replaces `_abm_result_stub`** (`simulation/dynamics.py`). Done when: a generated
  atom set runs individual / pairwise / joint over the real engines with interactions reported;
  the ABM proof stub is replaced by a real content-bound receipt; an unsupported feedback /
  shared-resource coupling is **gated, not silently summed**. **Equilibrium-semantics taxonomy
  (Rev 11):** every design / objective declares
  `equilibrium_semantics ∈ {none, static_SCM, dynamic_SCM, time_unrolled_SCM, equilibrium_SCM,
  game_model, agent_based_model, unsupported}` bound to the actual engine that backs it; an
  objective whose feedback is `unsupported` **cannot be grounded** for that objective (a residual
  surrogate may flag it for investigation but never certifies equilibrium validity). The simulation
  output is `K_sim` and **never shrinks `K_world`** (L1/L4). `P10`/`P32`.
- **GY-N6 — The generation cycle controller (kill single-pass).** build-new thin controller
  on `engine_simple` + the existing S2 refinement discipline (`SearchIteration`,
  `no_retry_without_new_grammar`, `RefinementDecision`, `CounterexampleRecord`) + the
  Scientist **VOI scheduler** (`voi_scheduler.py` — reuse for stopping / escalation / budget).
  It closes the loop: `DesignProblem` → generate (N4) → ground (A) → joint-value (N5 + N8) →
  revise → re-enter, with the terminal feeding the next action. Remove the hardcoded
  `cycle_index` / single-pass from the production path; **LangGraph stays legacy** (owner-first
  on `engine_simple`). Done when: a `DesignProblem` runs ≥2 real cycles with a revision
  **driven by the prior terminal**; `no_retry_without_new_grammar` is enforced live; the VOI
  scheduler drives a real stop / advance / escalate; the single-pass `run_fixture` path is
  reworked or strangled (no parallel single-pass loop survives). **Four stratified fronts (Rev 11,
  high-value):** the cycle returns **not one "best" design** but the spec's stratified set —
  `DecisionFront` (certified / promoted, `current_valid` only), `ResearchFront` (promising shadow,
  exploration-only), `QuarantineFront` (high-proxy / high-gap candidates routed to the in-cycle
  `adversarial_validate` action — wire the existing S2 `CounterexampleRecord` discipline as the
  generator of this front), and `PortfolioFront` (deferred — empty until portfolio certification
  exists, §Phase-5 deferred). The **mixed proposer** keeps a **grammar-fallback channel** so
  finite-slice coverage holds (the spec's Thm 4) independent of LLM behavior. *(MCTS / progressive
  widening / nonstationary meta-controller are deferred — see the Phase-5 deferred list.)* Done
  also when: a cycle run emits the four fronts (Portfolio may be empty); a high-proxy / low-grounding
  candidate lands in `QuarantineFront` and is adversarially validated **before** it could promote,
  never silently into `DecisionFront`. `P02`/`P27`/`P29`.
- **GY-N7 — Closed acquisition (receipt + same-cycle re-entry).** rework-existing. Build the
  durable acquisition **receipt + re-entry** over the real execution owners: an
  `ACQUISITION_REQUIRED` decision compiles **all** gaps to claim-bound W7 `DataRequirementSpec`s
  (replacing the lossy first-gap / `unknown_missing_distribution` adapter), executes via Fabric
  retrieval / ingestion + Scholar / OpenAlex + Data Forge SKG on `control_worker`, persists a
  **content-bound cost / quality / rights / binding receipt**, and re-enters the **same cycle
  index**. Done when: an `ACQUISITION_REQUIRED` triggers a real acquisition run that ingests new
  grounding, persists a receipt, and re-enters; `useful_design_rate` moves off 0 **iff** real
  grounding results — honest, never forced (Rule 5); a no-result acquisition records an honest
  costed gap; the lossy / unknown fallback is deleted. **Acquisition-family taxonomy (Rev 11):**
  structure acquisition scoring as the spec's families — **start with `ID`** (identification /
  bound-shrinkage: a `width_{t,j}` worst-case potency over near-frontier `ValueOuterSet`s), **`CERT`**
  (proof-gap / certification closure), and **`COV`** (grammar coverage / search diversity); the
  remaining families (`HV`, `HKG`, `ADV`, `AUD`, `SAFE`) are named hooks adopted now, scored later.
  Add the **affected-region revalidation**: an acquisition `u` recomputes an **over-approximated**
  region `R_out(u) = { x : Dep_out(x) ∩ N_h(S(u)) }` and re-derives identification / calibration /
  value-set / grounding for **every** design in it (so a calibration buy that tightens one family
  re-grades all dependents, not just the requested design). Note bundle / complementarity honestly:
  single-step greedy is a **heuristic unless adaptive submodularity is verified** (two datasets each
  useless alone but jointly identifying). Done also when: an `ID` acquisition that shrinks many
  near-frontier widths is preferred over one that helps a single design; the affected region is
  recomputed and dependents re-graded after a real acquisition. `P28`/`P29`.
- **GY-N8 — Value as the live gate (reuse causal / Bayesian / transport under 3.14).**
  rework-existing / wire. Wire the reachable foundry value stack as the **live value criterion
  over a named `WorldModelRecord`**: causal methods (synthetic control, DID, diagnostics, SciPy
  QP, pymoo) + the **Bayesian / posterior** primitives (variational, BVAR, uncertainty
  envelopes) + the **transport** stack (selection diagrams, transport solver, density-ratio →
  real `transported_limited` receipts), gated by `outcome_prediction`'s calibration discipline
  (`forecast_tier`, uncertainty intervals, `false_clear` counters). Make method selection
  **candidate / problem-aware** (not the fixed `synthetic_control` default) and surface
  unavailable-method blockers truthfully. **Set-valued value + honest dominance + modes (Rev 11):**
  the value the gate produces is a **certified `ValueOuterSet` `V_out` (GY-N-V) over the named
  `WorldModelRecord`**, not a scalar + CI — point identification → a narrow set, partial → an
  interval / support-function bound, proxy → a wide set (the spec's set-valued value). Comparison
  uses **honest dominance**: strong-robust dominance where the coupled solve is available, else the
  **marginal-interval fallback**, and a solver timeout / approximation returns **`unknown`, never
  silently "dominated"**. Declare the **six evaluation modes** (`simulate_only`, `retrospective`,
  `measurement_audit`, `sandbox_pilot`, `field_pilot`, `deployment`) on every value call; only
  some yield world evidence — **`simulate_only` updates `K_sim` only and never shrinks `K_world`**;
  any non-simulation mode requires the appropriate gate before execution (`retrospective` /
  `measurement_audit` → DataTrust; `sandbox_pilot` / `field_pilot` / `deployment` → the **EvalSafety
  gate**, GY-O0, Phase 6 — *safe to simulate ≠ safe to pilot*). Done when: a
  candidate's value is a typed `ValueOuterSet` with an identification status **plus a transport
  receipt naming its world version**; a pairwise comparison returns `unknown` on timeout rather than
  a false dominance; a `simulate_only` evaluation provably does not narrow the world credal set; an
  uncalibrated / unsupported / regime-laundered / un-transportable forecast **cannot mint value
  authority**; the value feeds revision before promotion. `P10`/`P14`/`P32`.
- **GY-N9 — In-cycle B→A promotion sequence (one canonical path).** rework-existing. Build the
  **single** canonical in-cycle promotion sequence over the real enforcement owners (Ring-2
  waist + `AuthorityDerivationTrace`, P14 effective-independence, G4 governed-promotion, the
  S6 / S7 / S8 value / mandate / blind-spot gates): a shadow candidate promotes to
  `grounded_partial_admissible` **only** on resolve + content-bind + verifier-provenance for
  producer roots, entailment / grounding (GY-K), calibration + transport (N8), effective
  independence, admissibility, and the S6 / S7 / S8 gates; else honest shadow / abstention.
  **Collapse** the parallel Scientist-champion vs G4-PDC promotion into one persisted sequence.
  **Obligations compiler + δ-budget (Rev 11):** state the promotion gate as the spec's
  **obligations compiler** — the typed `O(x)` taxonomy (syntax / type / slot / param / coupling /
  effect / identification / calibration / measurement / data / implementation / equilibrium /
  normative / eval-safety / value), each with a satisfaction semantics and a fail-closed
  `single_obligation_fail | joint_obligation_inconsistency | proof_timeout | scope_insufficient |
  unknown` reason (`unknown`/timeout never implies grounded or blocked). Each probabilistic
  certificate spends from the **GY-N11 confidence ledger** (δ-budget) so that
  `P(false promotion) ≤ δ` by the union bound. **Honest caveat carried in the task:** this δ-claim
  is **conditional on obligation completeness + validator soundness** (the spec's A4) — our **P29**
  regress; the mitigation is the QuarantineFront + adversarial validation + GY-N12 epochs, not a
  proof that the obligation set is complete. Done when: a fully grounded + admissible candidate
  promotes with a derivation trace **and a recorded risk-spend within δ**; an
  ungrounded / uncalibrated / un-transportable candidate stays shadow; a `proof_timeout` /
  `unknown` obligation never promotes; a forced / optimistic promotion is rejected and the lower
  boundary wins; no LLM output, surrogate score, or evidence-count upgrades itself.
  **Universality rider (Rev 15, §3.5.8):** the obligations compiler is **total over the typed
  `O(x)` taxonomy** — every one of the 15 classes carries either a real satisfaction semantics or an
  honest typed `scope_insufficient` refusal; a class the current vertical cannot exercise
  (equilibrium / normative / measurement / implementation / eval-safety) must **never** become a
  vacuous auto-pass (that spends no δ while insuring nothing — the exact vacuity that makes
  δ-accounting theater). N9 lands **before** N10, so it will be built against today's panel-shaped
  N8 receipt: the sequence consumes **only the typed contracts** (U1 — `ValueOuterSet` +
  receipt interfaces, never `n_treated`/`pre_periods`-style fields) and ships the **unseen-shape
  probe** (U2 — a contract-valid non-panel value receipt flows through promotion unchanged or
  fail-closes typed), so N10's generalization does not rework N9. **Compute economics (§3.5.7):**
  promotion is replayed every cycle — Lane-0 the sequence logic on synthetic certificates; obligation
  solves reuse cached certificates (E1); the cold end-to-end promotion lane runs once at closeout;
  the P29 source-flip harness (the N8 pattern: patch source → probe RED → restore) is required for
  the decisive obligations, not probe-only mutations.
  `P05`/`P14`/`P15`/`P29`.
- **GY-N10a — Second-domain substrate pack (data-only free-grow proof; NEW, Rev 15).** data +
  acquisition task, **zero engine code** — lands before GY-N10 because the second domain's substrate
  does not exist yet: L6 (lever/intervention vocabulary) is Ukraine-only, CG3 owner-writability
  covers 2/32 targets on the Ukraine sim, and the N8 transport contexts assume the governance domain.
  Assemble the full substrate pack for N10's second domain via the free-grow path alone: (a) outcome
  variables present in L1 DCAT (or acquired via a real N7 run); (b) a **lever/intervention
  vocabulary for the domain** entering via the S0 free-grow registry / N7 acquisition — never a code
  table; (c) owner-writability / actuatability evidence for at least a minimal lever set; (d)
  transport covariates + source/target context profiles from the domain pack (what replaces the
  hardcoded governance tuple when N10 de-hardcodes N8); (e) grounding-reference coverage verified
  for the domain (L2 scholar KG is domain-broad — verify real coverage, don't assume). The chosen
  domain must satisfy N10's distinctness criterion. Done when: the pack exists as **data/registry
  entries with zero engine-code changes** (§3.5.6-gate-3 + U3 at domain scale); every missing piece
  routes through a real N7 acquisition receipt or an honest costed gap; a smoke `DesignProblem` for
  the domain parses and enters the cycle (terminals may be honest blocks — Rule 5); the pack's
  provenance is owner-derived, not hand-authored (the N7 capture discipline). **Compute economics
  (§3.5.7):** acquisition runs are journal-first (E6); the pack is content-addressed so N10 reuses it
  via E1. `P31`/Rule 12.
- **GY-N10 — Depth-N universality (arbitrary `DesignProblem`; ≥2 distinct domains).**
  rework + thin depth-N controller. Drive the whole cycle from **arbitrary** `DesignProblem`s
  (not committed fixtures; reuse GY-M2 case-parameterization) with a depth-N controller that
  reuses the existing ledgers / terminals / coupling-composition / recursion contract and
  generalizes the cycle over depth and candidate families. Run the full `DesignProblem` →
  generate → ground → joint-value → revise → promote cycle end-to-end on **≥2 distinct
  domains** from plain language. **Replace GY-G's hardcoded depth-2 independent fixture** with
  observed coupling + real joint simulation. **N8 value-gate universality debt (Rev 15):** the
  GY-N8 value gate landed honestly but is currently a **panel/DID + governance-domain vertical** —
  its second domain must remove two simplifications introduced while landing the first real value:
  (1) **de-hardcode the transport covariates** — `_build_candidate_selection_diagram` pins
  `("state_capacity", "institutional_quality")` + `post_conflict` governance defaults; the
  selection-diagram S-nodes / source-target contexts must be **derived from the candidate's real
  world relationship / the domain pack**, not a fixed governance tuple; (2) **generalize the value
  vertical across all foundry method families** in `src/polisyos/foundry/methods/catalog/`
  (bayesian, causal, dependence, distributional, econometrics, forecasting, mechanism, microsim,
  ml, network, optimization, policy, sensitivity, simulation, spatial, survey, validation) — the
  S10 calibration credibility (`_s10_calibration_evidence_from_report`) currently requires
  panel/DID report fields (`n_treated`/`n_control`/`pre_periods`/`post_periods`), so any non-panel
  method family refuses; credibility + the value-set width must derive **generically from whatever
  uncertainty / diagnostics the selected method's report provides**, so a Bayesian / synthetic-
  control / transport-only estimate can mint value too. These stay **honest refusals** until N10
  (they abstain, never fabricate), and the free-grow-over-data path (generic `canonical_var`
  loader + registry selection) is already intact; N10 restores free-grow **over domains and method
  families**. **Distinctness criterion (Rev 15):** the second domain must differ from the first in
  ALL of — outcome family / substrate slice (different L1 `canonical_var`s), method family
  (non-panel, per the debt above), transport covariate set (not the governance tuple), and lever
  space (a different S0/L6 intervention vocabulary, arriving via GY-N10a's data-only pack). Two
  Ukraine-economics variants (msme-credit vs tourism vs pl-household-energy) do **not** count as
  distinct domains. Add an **unseen-third-domain smoke** (U2 at cycle scale): a third domain's
  `DesignProblem` — for which no pack was prepared — must reach an **honest typed terminal** (costed
  abstention / acquisition / ceiling), never a crash or a first-vertical mismatch; universality
  means honest degradation on the unseen. Done when: the full cycle runs on ≥2 distinct domains, each reaching an **honest**
  terminal (promotion / costed abstention / ceiling), with no domain pinned / hardcoded; the GY-G
  fixture is strangled; **the two N8 value-gate hardcodes are removed (transport covariates
  domain-derived; value/calibration generic across the foundry method-family catalog, proven on a
  non-panel method family)**; the GY-N0 ledger shows no parallel world reopened. `P27`/`P31`.
- **GY-N11 — Honest confidence ledger (anytime-valid promotion risk; NEW, Rev 11).** build-new
  ledger + recomputing validator. The promotion gate (N9) is queried **adaptively** (candidates
  depend on prior outcomes, the validator is queried on demand, the user may stop anytime), so
  fixed-time intervals are unsound for promotion. Build the spec's confidence-accounting layer:
  promotion certificates use **anytime-valid** instruments (confidence sequences / e-values /
  e-processes / sequential tests; deterministic proofs where available), risk is **spent only on
  executed checks** from a predictable schedule (`Σ α_{t,q} ≤ δ`, e.g. the `6/(π²(t+1)²)` weights),
  and a **good-event** `Ω_δ` gives `P(false promotion | maintained assumptions) ≤ δ` by the union
  bound. Reuse any existing sequential-test / FDR primitives (the same family GY-O2 uses); do
  **not** build a second statistics stack. Surface the **δ-split** across obligation classes
  (value / ground / id / cal / data / eval / mc — a tunable budget). Done when: the promotion gate
  draws every probabilistic certificate from the ledger; a run records a total risk-spend `≤ δ`
  with a recomputing validator that fails on over-spend or on a non-anytime-valid certificate used
  for promotion; a Bayesian credible interval **without** a coverage argument cannot be used as a
  promotion certificate. **Universality rider (Rev 15, §3.5.8):** the ledger schema is generic over
  **obligation class × certificate instrument** (typed), free-grow over new instruments — a new
  method family's certificate type (post-N10) is accounted with **zero ledger code** (U3); an
  unknown instrument fail-closes `unknown_instrument` and never silently bypasses risk accounting
  (U4); the δ-split is keyed to the typed obligation taxonomy, never to the certificate types that
  happen to exist in the first vertical (U1, with the U2 unseen-instrument probe).
  **Acquisition/refusal instruments rider (Rev 16):** N10 measured the cycle's live output —
  typed refusals and acquisition routes, zero positives (Fork B). The instrument taxonomy
  therefore covers **refusal and acquisition certificates as first-class ledger rows from day
  one**: the three capstone evidence classes (`owner_acquisition_route` /
  `estimand_binding_refusal` / `owner_data_gap`) and the N13b admission passports are accounted
  instruments with their own risk-spend semantics (`P(confident-wrong refusal/admission)` is
  accounted exactly like `P(confident-wrong bind)`); positive promotion certificates remain the
  free-grow future — so the ledger is non-vacuous on the evidence that actually exists, and its
  frozen artifact is §3.5.11 projection-scoped. `P29`/`P14`.
- **GY-N12 — Model-revision epochs + stale certificates + OpenWorldRisk (NEW, Rev 11).**
  build-new epoch manager + bridge over existing temporal authority. A certificate is valid only
  within an **epoch** of fixed semantics (model class, obligation language, calibration scope,
  measurement / implementation / equilibrium semantics, validator version). Sit it on the substrate
  we already have: **L3 amendments `effective_from`** (legal validity windows) + **L5
  `schema_regime`** (ukraine v1-prewar / v2-wartime changepoint + boundary buffer) are the real
  epoch boundaries — do **not** invent a parallel time model (reuse `fabric/world` bitemporal
  validity + the GY-N3 `branch_mode`). On a **revision trigger** (`K` empty, calibration-
  transportability alarm, data-provenance alarm, simulator-discrepancy over bound, obligation-
  completeness alarm, a new normative constraint, a validator-soundness issue): **freeze promotion
  in the affected scope**, open a new epoch, mark affected certificates **stale /
  revalidation_required**, and re-validate the decision front so it returns **`current_valid` only**.
  Add the **OpenWorldRisk** indicator (true deployment scope outside the declared
  model / obligation / calibration scope) that freezes promotion for the affected scope. Done when:
  crossing an L3 amendment or an L5 schema-regime changepoint marks dependent certificates stale and
  forces revalidation before they can stay on the decision front; a high OpenWorldRisk scope freezes
  promotion; a stale certificate cannot appear in a public result. **Universality rider (Rev 15,
  §3.5.8):** epoch boundaries are **derived from the full substrate data** — every L5 `schema_regime`
  entry and every L3 amendment window in the registry (U3): a new domain's regime added via data
  alone creates epoch semantics with **zero engine code**; the ukraine v1-prewar/v2-wartime
  changepoint is the **first test case, never an enum in engine code**; the revision-trigger
  vocabulary stays the typed generic list (it already is — keep it that way); a scope with no
  regime/amendment data gets honest `epoch_scope_unresolved`, not an assumed epoch (U4).
  **Acquisition-epoch rider (Rev 16):** N13b acquisition events (a new dataset version / source
  watermark / overlay epoch) are **live epoch-boundary sources** alongside L3 amendments and L5
  schema regimes — the world growing IS a model-revision trigger: certificates whose evidence
  predates an admitted acquisition in their scope become `revalidation_required` exactly like an
  amendment crossing. The N13b overlay epoch stamps and the N12 epoch manager share ONE time
  semantics (no fragmentation — the time-semantics anti-pattern); and **derived artifacts
  inherit epoch validity from their inputs (Rev 17, §3.5.12-D6)** — an input revision (agencies
  revise series) marks dependent derivations `revalidation_required`, and because the
  derivation certificate IS the recipe, revalidation is an automatic recompute.
  `P07`/`P08`/`P29`.
- **GY-N13a — Acquisition-layer reality census (data + sampled-live probes; NEW, Rev 16).**
  census task, GY-0-class, zero engine-behavior change. The acquisition layer exists but is dark
  to the runtime: the DCAT catalog (`production_data/datasets_full_phase3full_20260327_183054/
  dataset_catalog.duckdb`) carries **56,846 metric bindings** (`ds_metric_bindings`: metric →
  dataset → distribution → `connector_id`/`profile_id`/`request_dataset_id`/default filters/
  confidence/`execution_tier`; 34,308 `transport_ready` + 7,668 `fetchable` = **41,976
  executable**, 14,870 catalog-only) over 124 metrics; **3.7M already-local L1 observations**
  (`ds_observations`) over 101 canonical vars; 605K distributions with direct URLs
  (`ds_distributions`); alignment machinery with confidence + `is_proxy`/`proxy_penalty`
  (`ds_variable_alignments`) and 176K schema profiles. Fabric has 20+ real connector classes
  (worldbank.wdi, eurostat, sdmx, who, unesco_uis, unpd, ukons, ckan, socrata, opendatasoft,
  wvs, sparql, rest…), binding profiles, `run_orchestrated_ingestion` (fetch-once → CAS →
  DataSnapshot), and `RetrievalService` (FastLane + ExploreLane + **PromotionLane**) with an
  **unwired** `_resolve_via_catalog` lane. Census: (1) the **catalog↔runtime seam** — which of
  the 124 bound metrics resolve to the cycle's canonical variables; classify the three N10
  capstone acquisition routes against the catalog (**local-lift** — first-vertical
  `employment_retention` vs the bound employment metrics + L4 firm panels; **live-fetchable** —
  the unseen water-quality gap vs WHO/Eurostat indicators; **not-a-data-gap** — education's
  estimand refusal needs method evidence, not rows); (2) construct `DatasetCatalogGraph` from
  the DuckDB catalog and feed `RetrievalService._resolve_via_catalog` — FetchPlans must
  **generate (not execute)** for a sampled metric set; (3) a **stratified live liveness
  census**: ~10–15 journaled probes per connector family (never the full 42k) under §3.5.9
  discipline — endpoint alive, schema-profile still matches, license/ToS metadata present —
  producing a typed connector scorecard + liveness map (the snapshot is ~4 months old; dead
  URLs are expected findings, not failures); (4) the **D2 demand signal (Rev 17)**: typed
  `connector_gap` / `binding_gap` residuals for every cycle-relevant metric with no executable
  binding, seeding the VOI-ranked source-growth backlog (§3.5.12). Done when: a frozen census
  artifact (recomputing validator, §3.5.10-compliant — classes recomputed, not pinned) records
  the metric-resolution map, the three routes classified with evidence, live FetchPlan
  generation from the real catalog, the per-family liveness table, and the typed growth-backlog
  residuals; the census lane is designed **re-runnable** (the D3 recurring liveness census with
  tier decay); every live probe journal-first; zero engine behavior changes.
  `P29`/§3.5.9/§3.5.12.
  **Measured N13a result (2026-07-16):** the frozen census covers 124 metrics (95 exact, 20 via
  alignment, 9 unresolved), 19 cycle-demand variables (4 executable, 15 `binding_gap`), all 12
  data-derived connector families (144 actual-connector REPLAY receipts; 128 intercepted, zero
  network escapes; 18 bounded live calls with journaled heartbeats), and all three capstone routes.
  The actual route projection classifies all three `not_a_data_gap`: education is
  blocked on `method_estimand_binding_mismatch`; first-vertical and unseen are blocked on their
  exact grounding/world-record links. Therefore N13b has **no honest capstone data-only execution
  lane yet** and must not force the stale water-quality hypothesis. Seven real catalog FetchPlans
  generate behind a zero-call execution fence (`implemented_but_not_orchestrated`). The 15-row
  growth backlog uses the declared interim binding-confidence × route-demand order with an explicit
  N13b VOI-owner integration note; it is not claimed as VOI. Frozen artifact:
  `architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json`, file
  `sha256:63212c8ccdcd80e96f8ae5903a74e4587090cfe096392e00069d30c17ba64791`.
- **GY-N13b — Acquisition executor — the world grows (close one capstone route end-to-end;
  NEW, Rev 16).** wire-existing + narrow build-new. Convert N7's routes from typed dead-ends
  into executed acquisitions: (1) wire the `DatasetCatalogGraph` into the N7 `_capture_fabric`
  path (kill the probe-only pattern that imports `run_orchestrated_ingestion` and immediately
  `del`etes it); (2) **two execution lanes** — **local-lift** (catalog/L4 observations →
  canonical L1 variables through the EXISTING alignment machinery, generic over
  `ds_variable_alignments`, never per-metric hand code — §3.5.6-gate-3) and **live-fetch**
  (`run_orchestrated_ingestion` → CAS → DataSnapshot under §3.5.9 discipline, journal-first raw
  evidence); (3) an **epoch-stamped overlay** on the canonical observation store — the baseline
  snapshot is epoch 0 and is **never mutated**; acquired observations land as new-epoch rows
  with full provenance (UNIFY_EXISTING, no parallel store — the GY-N0 law), and the runtime
  L1-availability read (`data_state_substrate` reads `dataset_catalog.duckdb#variable/…`) sees
  them without a new adapter; (4) a **fail-closed admission passport** — schema-profile match,
  unit coercion, alignment confidence (proxy → degraded authority), license admissibility, the
  PII stage, checksum/watermark, L5 trust tier; a fetched row without a full passport lands in
  **quarantine, never L1** (catalog confidence PRIORITIZES, owner validation ADMITS — the CGF
  principle applied to data); (5) close the two typed N10 residuals
  (`owner_registration_derivation_missing` → acquired snapshots registered in the
  generated-artifact lifecycle; `journal_raw_evidence_persistence_missing` → journal-first raw
  evidence persistence); (6) **close ONE measured, honestly data-shaped gap end-to-end (Rev 18
  — re-specified by the N13a census under §3.5.10):** the N13a census recomputed all three
  capstone routes as `not_a_data_gap` (structural grounding-relation / owner-lever / estimand
  gaps), so the demonstration target moves from the capstone routes to the census's **measured
  D2 backlog** (15 typed `binding_gap` cycle-demand residuals; 4 supported variables with
  executable bindings; worldbank.wdi live-proven) — the agent derives the exact target(s) from
  the census by evidence (one local-lift and/or one live-fetch case): typed requirement →
  resolved plan → executed acquisition → admitted observations → overlay epoch → the demanding
  cycle stage re-runs and its gap is **measurably closed** (or reaches an honest typed deeper
  state). The three capstone routes' structural gaps are typed residuals routed to the
  **knowledge/grounding acquisition plane** (CG5-class relation/lever acquisition + estimand
  evidence) — explicitly out of N13b scope, recorded as the next-frontier backlog item.
  **Two census-discovered enabling items are in scope:** (6a) the missing
  distribution-field→binding edge (`raw_variable_edge_missing` on all 115 resolved metrics) —
  the last-mile landing path for fetched rows into canonical variables; (6b) passport
  schema-check semantics under metadata-only profiles (all 176,249 schema profiles carry zero
  sampled rows, so `alive_conformant` is unearnable today) — measure-then-validate under
  quarantine: the first fetch measures the structure, the passport validates against declared
  metadata + the measured sample, and only then can conformance be earned; (7) the
  **`derived` provenance class + derivation certificates (Rev 17, §3.5.12-D4/D5/D6)**: the
  overlay store admits certified derivations (content-addressed recipe = input hashes ×
  method+version+params × auxiliary inputs), derived rows never masquerade as observed, and the
  acceptance case is the **real-terms/inflation normalization family** — an acquired nominal
  monetary series deflated against a connector-acquired deflator series (deflator choice + base
  year declared assumptions in the certificate), the derived series consumed by **two distinct
  method lanes from ONE cache-hit derivation**, a `basis_mismatch` with no certified transform
  refusing typed into a derivation requirement, and a class-(iv) model output presented as an
  observation failing the passport closed. Done when: the
  chosen measured gap's re-entry trace shows it closed by acquisition (or an honest typed
  deeper state); the three capstone routes remain honestly structural (never laundered into
  data support — the N13a fence stands); the
  overlay/baseline separation is proven by a source flip (mutating the baseline = RED); a
  fabricated fetch response fails the passport closed; the derived acceptance case records one
  derivation / two consumers / cache-hit reuse + the typed `basis_mismatch` refusal; the
  acquisition and derivation receipts are §3.5.11 projection-scoped frozen artifacts under
  §3.5.10 (recomputed, not pinned). This task builds
  the acquisition half of the Phase-6 world-growth spine — O1/O3's write-back reuses its
  overlay store + passport, not a second write path.
  `P27`/`P29`/§3.5.6/§3.5.9/§3.5.10/§3.5.11/§3.5.12.

  **Measured N13b result (2026-07-18; frozen at `6280e487f`):** the acquisition executor
  capability is `implemented` with an `audit_surface`, and its honest demonstration result is
  `typed_deeper_terminal`, not world growth. The resumption spent 3/6 authorized calls; no response
  was admitted, so `government.balance` remained 0 datasets / 0 bindings / 0 observations, with
  zero overlay epochs and terminal `deeper_terminal_primary_carrier_characterization_failed`. The
  separate real-terms acceptance case closed from owner-admissible epoch-0 catalog inputs: one
  certified exact-year CPI derivation, two distinct consumers, and a verified
  second-materialization cache hit. Both N10 lifecycle residuals are closed and all three capstone
  routes remain `not_a_data_gap`. Frozen contract:
  `architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json`, semantic
  `sha256:1e2b91fcf8ff2410524d86dd486ffdb7f07e417372f608f16b00135d5aa84235`.

**Phase-5 deferred (adopt the contract now, implement when a certified frontier exists).** With
`useful_design_rate ≈ 0` and depth-1 integration, the mature-frontier machinery is not yet
load-bearing. Carry the **contracts / labels** now (so artifacts already speak them) and implement
later — tracked here so they are not lost: **(1) Portfolio-as-design** (a randomized / mixed policy
as a new design object with its own obligations and **nonlinear** value — `V(x_μ) ≠ Σ μ(x)V(x)`
unless linearity / no-interference / assignment semantics are certified) → the `PortfolioFront`
stays empty until this lands (Phase 7 / follow-on; the spec itself forbids returning an uncertified
portfolio). **(2) CHHV solvers, scenario-tree VOI with rectangularity, EXP3 / sliding-window
meta-controller, and full MCTS** (progressive widening + `UCT_H` selection over the prefix tree) →
needed for a rich certified frontier and a non-stationary acquisition mix; not now. **(3) The
full transform-planner (Rev 17)** — automatic search/insertion of certified transform **chains**
over the §3.5.12-D6 basis vocabulary → N13b lands only single-transform matching + the typed
`basis_mismatch` refusal; chain search comes when the derived layer has enough certified
families to need it. The honest
**marginal-interval fallback** (GY-N-V) and the **phase-schedule** acquisition weights (N7) are the
interim stand-ins, and the `unknown`/incomparable discipline keeps them safe.

**Phase-5 acceptance (gates Phase 6 / 7):** the GY-N0 ledger is complete and **no asset
remains a live parallel owner** (every superseded path strangled / deleted with a receipt);
the three foundation bridges (`DesignProblem`, `InterventionAtomBinding`, `WorldModelRecord`)
exist and the cycle **names its exact world version**; the cycle runs on ≥2 domains from plain
language with honest terminals; the firewalls hold **under generative freedom** (the GY-V4
adversarial-against-A battery passes against the cycle); promotion is grounded-only; and
`useful_design_rate` is the honest consequence of real grounding — **never forced** (Rule 5).
**Rev-11 additions also gate Phase 6 / 7:** value is a set-valued `ValueOuterSet` (GY-N-V) with
the `unknown`/incomparable discipline; the cycle returns the four stratified fronts (QuarantineFront
populated, PortfolioFront deferred); promotion risk is ledgered with a recorded spend `≤ δ`
(GY-N11); and epoch / stale-certificate revalidation (GY-N12) is wired to the real L3-amendment /
L5-schema-regime boundaries. The deferred items (portfolio-as-design, CHHV / scenario-tree VOI /
EXP3 / MCTS) are **not** acceptance blockers — they are tracked contracts, not omissions.
**Rev-12 (the §3.5.6 completeness gates):** every cycle task that lifts / resolves / binds authority
(N2 atom binding, N4 grounding, N7 acquisition, N8 value-method routing, N9 promotion) must encode
all four gates for its decisive property — full-denominator coverage, fail-closed on a fake/novel
input (owner-validation, not trust), data-only free-grow, and a **contract mutation on the decisive
validation property** (the gate goes red if owner-validation is removed while the happy-path stays
valid). A cycle task whose runtime is correct but whose contract would not catch that regression is
**not done**.

### Phase 6 — Deployed-Policy Learning Loop (the world model grows; greenfield horizon)

The cycle (Phase 5) produces a grounded-or-honestly-limited design. The north-star's product
is the **growing causal world model** (`docs/system-design-decisions/policy-design-causal-operating-system-north-star.md`):
a deployed policy keeps living, its effect is updated from observation, and unpredicted
consequences are discovered and folded back into the world model. This is the **one genuinely
greenfield zone** — the posterior / calibration / drift / FDR / decision-feedback **primitives
are real and reusable** (GY-N0 sweep), but the deployed updater, the exploratory controller,
and the world write-back are new. *(Rev 16: GY-N13b builds the **acquisition half of the
world-growth spine** — O1/O3's world write-back reuses its epoch-overlay store and admission
passport, never a second write path; deployment updates and acquisitions are two provenance
classes landing in ONE growing world.)* It runs **two contours with different authority**, both on
the candidate→authority firewall. (Scope note: this phase may spin into its own follow-on
slice; it is planned here so the Phase-5 cycle designs its deployment hooks for it. Each task is
scoped to a roughly comparable amount of work.)

- **GY-O0 — Attempted-evaluation safety gate (EvalSafety; the Phase 5→6 bridge; NEW, Rev 11).**
  build-new gate. The Phase-5 value gate (GY-N8) declares the **six evaluation modes**; this task
  builds the **attempted-evaluation safety gate** the real-world modes must pass **before
  execution** — *promotion safety and attempted-evaluation safety are distinct: a design can be safe
  to simulate but unsafe to pilot.* Mode-specific requirements per the spec: `retrospective` → data
  trust + privacy / access + measurement validity; `sandbox_pilot` → containment + stop rules + harm
  bound; `field_pilot` → ethical / legal approval + monitoring + rollback + population protections;
  `deployment` → full deployment safety + governance + accountability. The gate is **fail-closed**
  and independent of the promotion gate (a promoted design still cannot be piloted without it). Done
  when: a non-simulation evaluation cannot execute without a passing `EvalSafety` certificate for
  its mode; an attempt to pilot a promotion-safe-but-pilot-unsafe design is **blocked** with a typed
  reason; the gate records `unsafe_attempt_blocked_count` / `near_miss_count` honestly.
  **Universality rider (Rev 15, §3.5.8):** the mode-requirement vocabulary (containment / harm-bound
  / stop-rules / approvals / population protections) is **typed and domain-pack-extensible** (U3),
  never enumerated per fixture; an unknown domain's pilot request fail-closes typed (U4) — a gate
  calibrated only for the governance fixture must refuse, not improvise. `P05`/`P09`.
- **GY-O1 — Confirmatory deployed-effect updater (Bayesian; high authority).** build-new
  updater over reusable primitives. For the variables a deployed design **pre-declared** it
  would change, compare realized vs predicted and produce a **Bayesian posterior effect
  update** — reuse the foundry variational / BVAR estimators + the uncertainty-adapter
  envelopes + `DecisionFeedbackService` confirm / refute / reissue + S13 attribution — and
  write the updated posterior + provenance into `fabric/world` as a `deployment_update` branch
  on the `WorldModelRecord`. Done when: a deployed design's pre-declared effect is Bayesian-
  updated from real realized metrics with an uncertainty envelope, persisted to `fabric/world`
  with attribution; an un-pre-registered or unpowered claim **cannot** mint a confirmatory
  effect update. **Universality rider (Rev 15, §3.5.8):** the realized-vs-predicted comparison is
  generic over the **typed effect/outcome carriers** the (N10-generalized) value gate produces (U1)
  — never panel-scalar-specific; an effect type the updater cannot yet compare gets an honest typed
  refusal (U4), not a coerced scalar. `P14`.
- **GY-O2 — Exploratory anomaly→hypothesis controller (low authority).** build-new controller
  over reusable detectors. Monitor the broader variable space for anomalies the model did
  **not** predict — reuse the DDM drift / performance / readiness detectors + the
  `multiple_testing` FDR controller — under false-discovery control. An anomaly is a
  **low-authority candidate hypothesis** (`candidate_unverified`) that must earn authority by
  passing into the confirmatory contour (O1); **never** a direct world edit. Done when: a real
  anomaly is detected under FDR control and emitted as a candidate hypothesis with an
  attribution trace; a chance / uncontrolled anomaly is rejected; an anomaly cannot become a
  world-model edge without confirmatory promotion. `P15`/`P33`.
- **GY-O3 — World-model write-back (the model grows).** build-new write-back + bridge. A
  confirmed effect (O1) or a confirmation-promoted hypothesis (O2 → O1) writes a new / updated
  coupling edge, mechanism update, or required-data spec into the `WorldModelRecord` as a new
  versioned branch — reusing `fabric/world`'s append-only + branch + provenance as the storage
  substrate — so future designs ground against a richer world. Done when: a confirmed deployed
  finding produces a **new versioned `WorldModelRecord` branch** with the added / updated
  coupling + provenance, and a subsequent Phase-5 cycle run grounds against the updated world;
  an unconfirmed finding **cannot** write back. `P29`.

**Phase-6 acceptance:** a deployed design's effect is Bayesian-updated from observation
(confirmatory) and written to `fabric/world`; an exploratory anomaly is discovered under FDR
control and promoted to a confirmed coupling **only via the firewall**; the world model gains a
versioned branch that a later cycle run grounds against — proving the world model **grows
honestly**, with no anomaly minting authority directly.

### Phase 7 — Deep Workability Verification (audit-grade; the close)

After implementation the system should begin producing **real policy design** — a
grounded or honestly-limited design, or an honest grounded abstention with a costed
acquisition path. That claim is **proven by execution, not asserted.** This phase
re-applies the Task-0 census discipline to the *built* system:

> **No label is evidence.** Not a green unit test, a README, a status enum, or this
> plan's prose. The only evidence is a **recorded run on real input** with a
> reproducible (`gy_evidence_canon`, time-invariant) hash and the **actual artifacts**
> inspected (Workspace graph, `SearchLedger`, `SearchExitContract`, `AuthorityBoundary`,
> `CompositionCertificate`), not their summaries.

Every GY-V task emits a **committed artifact + a recomputing validator** (the Task-0
pattern: the validator re-derives the claim from live code/artifacts and fails on
drift), and a repo-quality negative test. The success criterion honors Rule 5: the win
is **honest, measurement-rooted, replayable outcomes with firewalls intact** — *not* a
high `useful_design_rate`. Forcing useful-design credit is a failure of this phase.

- **GY-V1 — Coverage-matrix closure (the progress meter).** Re-derive the repo-wide
  capability coverage matrix post-implementation. Prove every row a GY task acted on
  moved off `bridge_missing`/`surface_missing`/`absent` to a **complete chain with a
  semantic test** (1/29 green → the target set green). Validator fails if any
  claimed-moved row is still broken. Done when: the moved-row delta is recorded and the
  validator is green.
- **GY-V2 — End-to-end loop execution proof (real input, reproducible).** Run the full
  loop **via the production trigger (GY-B2)** on real cases; capture the
  `WorkspaceContract`, artifact graph, `SearchLedger`, `FrontierSnapshot`, and typed
  `SearchExitContract` with `gy_evidence_canon` hashes. Prove a real terminal outcome
  whose promoted artifacts carry **measurement-rooted producer roots**. Done when: at
  least one case reaches `grounded_admissible`/`grounded_partial_admissible` with a
  measurement-rooted chain, **or** a `grounded_abstention`/`search_ceiling_repair_required`
  that the ceiling-gate (§8.4) certifies as honest — recorded and replayable.
- **GY-V3 — Multi-case generalization + scale battery.** Run a labelled set spanning
  depth-1 (tourism local; ua-msme) and depth-2/recursion (pl-household-energy; an
  accession-class recursive case). Record the **terminal-state distribution +
  evidence-kind distribution + decision-grade distribution + rung reached** (the honest
  claim is the distribution, never a useful-rate target). Prove scale-invariance: the
  same loop handles a 1-cycle local case and a recursive program; the recursive case
  actually composes via a
  `CompositionCertificate`. Done when: the distribution is recorded; the recursive case
  produces a certificate or an honest typed terminal; no case is forced to useful.
  **Universality rider (Rev 15, §3.5.8):** the labelled set MUST extend beyond the
  governance/Europe-economics cluster — include the GY-N10 second domain, at least one case
  exercising a **non-panel method family** through the value gate, and the **unseen-third-domain
  smoke** (honest typed terminal, no first-vertical mismatch); record the terminal / evidence-kind /
  decision-grade distributions **per domain**, so domain-invariance is measured, not asserted.
  **Rev 16:** consume the frozen N10 capstone directly — its three plain-language runs,
  per-domain terminal distributions, and three acquisition-route evidence classes ARE labelled
  cases (do not rebuild a parallel labelled set for those domains); add the post-N13b re-entry
  trace as a labelled case of a gap **closed by acquisition**.
- **GY-V4 — Adversarial-against-A battery (laundering firewalls live).** The
  constitution mandates this once real grounding happens. Executed **negative** probes,
  each with recorded evidence: (a) agent attempts to write a Ring-2 field → rejected;
  (b) a synthetic / no-measurement bundle attempts promotion → rejected (producer-root
  firewall); (c) a failed/candidate workflow attempts to reach a surface / export / sign
  → blocked or visibly downgraded; (d) poor-recall abstention → forced to
  `search_ceiling_repair_required`; (e) feedback decomposition → `composition_invalid`;
  (f) emergent program claim without system grounding → capped; (g) raw artifact route
  with a nested secret → redacted; (h) connector payload / DAG bundle with a nested
  secret → redacted or surface-blocked; (i) S12 authorial ref → non-dereferenceable →
  downgraded; (j) one candidate-positive diagnostic status attempts authority promotion
  without its firewall boundary → rejected and reconciled in `AuthorityCandidateInventory`;
  (k) CAS blob mutation/tamper probe → rejected or re-digested; (l) time-role mismatch
  (fresh source but stale catalog watermark, or valid legal time outside as-of replay
  time) → blocked/downgraded/obligation; (m) operation declares an optimistic
  `authority_transform` but A computes a lower boundary → lower boundary wins and an
  `AuthorityDerivationTrace` records the mismatch; (n) agent frames VOI/usefulness to
  select weak evidence over a higher-authority repair path → deterministic GY-H
  normalization rejects/clips the score in `VOISelectionAudit`; (o) workflow failure
  attempts clean completed job status before F1 surface migration → job is failed or
  non-authority. **Rev-11 firewall probes (the spec's "Not certificates" made behavioral —
  remove-the-property-keep-the-markers, P29):** (p) a high surrogate / high-proxy candidate (any
  trust level below `certified`) attempts promotion → rejected (QuarantineFront, not DecisionFront);
  (q) an **uncertified sample-only `ValueOuterSet`** attempts to mint promotion value → rejected
  (only a certified `V_out` promotes); (r) a `simulate_only` evaluation attempts to shrink `K_world`
  → rejected (stays in `K_sim`); (s) a **stale certificate** (post epoch-revision on an L3-amendment
  / L5-schema-regime boundary) attempts to appear on the decision front → removed /
  `revalidation_required`; (t) promotion whose cumulative risk-spend would exceed **δ** → blocked by
  the GY-N11 ledger; (u) a promotion-safe-but-pilot-unsafe design attempts a `field_pilot` without
  an EvalSafety certificate → blocked (GY-O0); (v) an `unsupported`-equilibrium feedback objective
  attempts grounding → capped (cannot be grounded). Done when: all listed probes fail closed with
  recorded evidence.
- **GY-V5 — Replay / determinism / reproducibility audit.** Prove the three replay
  levels: deterministic operations replay byte-identical (input/param hashes, seed,
  container digest); agentic operations replay as a decision/provenance trace; promoted
  artifacts re-walk the audit trail and re-validate. Prove `output_hash` evidence is
  time-invariant by re-running and comparing. Done when: a deterministic op replays
  identically; an agentic op's trace is reconstructable; a promoted artifact re-passes
  its audit trail; all recorded hashes are reproducible.
- **GY-V6 — GX validator + full audit suite green over all GY artifacts.** Every GY
  artifact passes the GX hardening validator (reducer provenance, producer-root chain,
  resolver dereference, runtime-literal lint); the Task-0 coverage matrix + the 16 audit
  validators + the GY-V validators are all green with **no uncatalogued drift**. Done
  when: the whole validator suite is green over the built system.
- **GY-V7 — Honest health-signal readout (T1/T6/T7).** Measure the constitution's five
  health signals on the built system: envelope-expansion-rate (T1), adapter-semantic-loss
  (T2), governance-throughput (T3), demand-pull-vs-abstention (T6),
  search-recall@known-seeds + index-staleness (T7). This answers, empirically and
  honestly, whether the system produces real grounded design or sits at a **domain
  ceiling** vs a repairable **search ceiling**. Done when: the five signals are recorded
  with the honest interpretation (domain vs search ceiling) per §8.4.

## 10. Execution order

1. **GY-M1 (hard gate) → GY-A1, GY-A2, GY-B, GY-B2** — the form. **GY-M1
   (artifact-family lifecycle registration) lands first** so no GY artifact is committed
   unregistered; then the waist (reuse/extend `pdc`, §3.5.2), the loop skeleton, and the
   production trigger on both Slice-0 fixtures (groundable
   `Slice0FixtureManifest:ua_msme_credit_worldbank_measurement` and tourism-ceiling).
   Honor the Slice-0 cut-lines (§3.5.1). Gate everything on these.
2. **GY-H, then GY-D1, GY-D2, GY-D3, GY-E** — anytime-exit core first (it owns VOI +
   `acquisition_required`), then the binding constraint (substrate + acquisition).
3. **GY-C1, then GY-C2 (repair), then GY-C3; GY-I** — subordination; **the spine-rot
   repair (GY-C2) lands before any governance-to-authority** (stop-rule).
4. **GY-F1, GY-F2, GY-F3** — authority surfaces behind one boundary.
5. **GY-G** — recursion + composition (scale; the accession-class capability).
6. **GY-M2** — GX reducer case-parameterization (needed before GY-L / GY-V validate a
   non-pinned case). (GY-M1 already landed as the Phase-0 hard gate in step 1.)
7. **GY-J** runs in parallel from the start (fork-independent). **GY-K, GY-L** are
   follow-on (GY-L after Phase 3 + GY-M; GY-K any time after GY-D1).
8. **GY-N0 (hard gate) → foundation bridges + GY-S substrate + GY-N4..N12 — B-on-A Generation
   Cycle (target spec: `policy-design-search-target-spec.md`).** After GY-L, the
   disposition ledger + consumption validator lands first (no parallel worlds — every asset
   used / reworked / deleted). Then the **three foundation bridges land before the cycle**:
   GY-N1 `DesignProblem`, GY-N2 `InterventionAtomBinding`, GY-N3 `WorldModelRecord` (the
   world model is a foundation the value gate names). **Alongside the bridges, the GY-S
   production-data substrate lift lands** — GY-S0 free-grow registry, then GY-S1 (data-state:
   L1/L4/L5), **GY-N-V `ValueOuterSet`** (the set-valued value carrier, landing with GY-S1),
   GY-S2 (knowledge: L2/L3), GY-S3 (intervention: L6) — so the world model binds the REAL
   substrate **as the spec's credal state** (set-valued, wire-existing, not toy fixtures) and
   grows as data arrives. Then the cycle is wired by **subordinating the existing generative /
   causal / value engines under A** (reuse, not from-scratch): GY-N4 generation-under-A (+
   firewall / surrogate), GY-N5 joint-simulation horizon (+ equilibrium-semantics taxonomy), GY-N6
   the real propose→ground→value→revise cycle (+ four stratified fronts), GY-N7 closed acquisition
   (+ ID/CERT/COV families + affected-region revalidation), GY-N8 value-as-gate (+ value-outer-set
   + honest dominance + six modes), GY-N9 in-cycle promotion (+ obligations compiler), **GY-N11
   honest confidence ledger (δ-budget)**, **GY-N12 epochs + stale certs + OpenWorldRisk**,
   **GY-N10a second-domain substrate pack (data-only, before N10)**, GY-N10
   depth-N universality. *(Rev 16 status note: the GY-CG grounding block CG0–CG6, GY-INFRA-1,
   GY-N4–N9, GY-N10a, and **GY-N10 (closed GO — capstone
   `layer3_gy_depth_n_universality_contract.json` at ce847b9f2; final architect audit in
   flight)**, **GY-N13a**, and **GY-N13b** are executed; N13b closed with an honest
   `typed_deeper_terminal` and no world-growth epoch. The remaining Phase-5 tasks run
   **N11 → N12**; all remain bound by
   §3.5.6–§3.5.12.)* The **Phase-5 deferred list** (portfolio-as-design, CHHV / scenario-tree
   VOI / EXP3 / MCTS) carries contracts now, implementation later. Runs before the learning loop
   and the V-battery so verification audits the **cycle**, not the single-pass harness.
9. **GY-O0..GY-O3 — Deployed-Policy Learning Loop (greenfield horizon).** After the cycle:
   GY-O0 the **EvalSafety gate** (the Phase 5→6 bridge — real-world modes pass attempted-evaluation
   safety before execution), then the confirmatory Bayesian deployed-effect updater, the exploratory
   anomaly→hypothesis controller, and the world-model write-back that makes the world model **grow**
   from observation. May spin into its own follow-on slice; the Phase-5 cycle designs its
   deployment hooks for it.
10. **GY-V1..GY-V7 — Deep Workability Verification (last).** Runs only after the build
    phases land; it is the audit-grade close that proves, by execution, that the system
    produces real (or honestly-limited/abstained) policy design with firewalls intact.
    GY-V1 (matrix closure) and GY-V6 (validator suite) gate slice completion.

Stop rules: a rotten asset is repaired before it is governed; a `build-new` overlapping
a `wire-existing` owner is rejected; any GY output that cannot pass the GX validator is
not done; the loop must have a production trigger (GY-B2) before GY-L; budget overrun
triggers a stop-and-review note; a parallel re-implementation beside a live canonical
owner is rejected (P27); a replacement that does not strangle its predecessor and flip the
default in the same change is rejected (P28); a proof/benchmark that is hand-authored or
validated for shape only — or a closure metric on a trivially-separable corpus — is not
evidence (P29); a module named after its plan/slice rather than its function (and with no
owner-breadcrumb docstring) is a naming defect fixed before merge (P30); a
generation-cycle asset (Phase 5) left as a **live parallel owner** instead of being
used-as-is, reworked-to-fit, or deleted via the GY-N0 disposition ledger is rejected
(P27/P28); and — Rev 11 — the formal target spec
(`policy-design-search-target-spec.md`) is **subordinated, not rebuilt**: its greenfield §27
build plan is superseded, every spec object maps to an existing organ (the decision record's
adoption table), and a task that implements a spec object as a parallel engine instead of
wiring the named owner is rejected (P27). The δ-safety theorem is carried **honestly as
conditional** on obligation completeness + validator soundness (the P29 regress), never asserted
as closed.

## 11. Acceptance bar

- The two-ring waist (17 waist contracts, roughly 13 new and the rest reused/extended
  per §3.5.2) is
  wired; **Ring-2 fields are not agent-writable (field-level, enforced + tested)**;
  `pdc` never imports engines; the `AuthorityBoundary` lattice tests cover
  `authoritative_for`, `may_not_use_for`, envelope intersection, `evidence_kind`
  partial meet, and `decision_grade` total meet; `AuthorityDerivationTrace` proves
  `A.verify` derives the stamped boundary independently from operation hints.
- The control loop runs both Slice-0 fixtures end-to-end **via the durable production
  trigger (GY-B2)** to typed `SearchExitContract`s with `FrontierSnapshot`,
  `SearchLedger`, replay levels A/B/C, and persisted `ProductionLoopRunProof`s showing
  `enqueue_job -> ControlWorker -> _execute_workflow -> WorkspaceLoop -> CAS/index ->
  /runs readback`; failed/legacy-shadow jobs cannot complete as authority-looking
  clean successes.
- Every coverage-matrix row a task acts on moves off `bridge_missing`/`surface_missing`/
  `absent` to a complete chain **with a semantic test** (the matrix is the progress meter).
- The binding constraint is real: a pinned construct resolves through the real catalog to
  a CAS-rooted measurement artifact with a `CertifiedOperationEnvelope`; recall@seeds +
  freshness recorded; non-execution-ready connectors fail closed; the groundable
  Slice-0 fixture is driven by `Slice0FixtureManifest`, reaches a measurement-rooted
  `grounded_partial_admissible` **Estimate-port** outcome, and is explicitly forbidden
  from emitting `grounded_admissible` or promoting a `DesignCandidate`; the tourism
  ceiling fixture stops honestly.
- `grounded_abstention` is emitted only past the domain-vs-search-ceiling gate; else
  `search_ceiling_repair_required` (F1/F8); simultaneous terminal triggers follow the
  §8.6 precedence.
- No authority surface renders/exports/signs a failed or candidate workflow as authority;
  no scoped secret/PII leak across raw routes, DAG bundles, connector payloads, CAS
  manifests, dashboard/public/export packets; CAS loop outputs carry `manifest.authority`
  and pass digest/dedup/tamper/GC survivability checks; S12 refs dereference or are
  candidate-only; the 406 candidate-positive statuses reconcile to a reviewed
  `AuthorityCandidateInventory`.
- A `PolicyProgram` is never promoted without a `CompositionCertificate`; feedback
  decomposition is rejected; emergent claims are capped to their own grounding.
- Graded outcomes route partial evidence to `grounded_partial_admissible` (GY-J), moving
  `useful_design_rate` off 0 honestly without weakening floors.
- The GY/loop artifact family has a registered lifecycle (F18); the GX validator runs on
  a non-pinned case (F14); every GY artifact passes the GX hardening validator; the Task
  0 coverage matrix and audit suite stay green.
- No parallel engine/pipeline/agent/DataNeed-type was built; engines entered only as
  Operations (adapters); the three workflows are playbooks, not modes.
- **Build hygiene (P27/P28/P29/P30):** no GY concept has two live owners (the §3.5.2 owner
  map is clean — `SearchLedger`, `AcquisitionPlanner`, the lex-bounds rule, and the fixture
  catalog each have exactly one home); modules are named by function with owner breadcrumbs,
  not by plan (`gy_loop.py`→`workspace_loop.py`, or a docstring naming the owners it extends
  — P30); every subordination/replacement task shipped a `StrangleReceipt` with the
  predecessor deleted or fenced and the default flipped (the `None→0.0` default is gone, no
  zero-deletion "migration"); every proof packet is run-emitted and recomputed by its
  validator, not authored; and F4/F7 closure is measured on a representative corpus or
  marked `surface_out_of_scope`, never a 2-record fixture.
- Slice 0 is not credited as policy-design synthesis: no `DesignCandidate` promotion is
  expected until the Phase-2 lowering/drafter/lex path is subordinated.
- **Deep Workability Verification (Phase 7) passes by execution:** the coverage matrix
  closes (GY-V1); a real loop run produces a measurement-rooted grounded/limited design
  or a ceiling-gate-certified honest abstention (GY-V2); the generalization distribution
  is recorded without forcing useful-design credit (GY-V3); all listed adversarial probes
  fail closed (GY-V4); replay levels A/B/C hold and hashes are reproducible (GY-V5); the
  full validator suite is green with no uncatalogued drift (GY-V6); the five health
  signals are recorded with the honest domain-vs-search-ceiling interpretation (GY-V7).

## 12. Required closeout evidence

- `pdc` two-ring waist + field-permission test + `AuthorityBoundary` two-axis lattice
  tests (GY-A1/A2).
- Control-loop Slice-0 fixture runs **launched via the durable production trigger**
  (GY-B/B2): committed `Slice0FixtureManifest`, two `ProductionLoopRunProof`s,
  `WorkspaceContract`, `SearchLedger`, `FrontierSnapshot`, typed `SearchExitContract`
  (GY-H), `AuthorityDerivationTrace`, `VOISelectionAudit`, replay A/B/C demonstration.
- GY-D supply report: real-catalog resolve → CAS measurement root + canonical snapshot
  hash + per-connector applicability + recall/precision@seeds.
- GY-E acquisition report (`RequiredDataSpec`→`DataNeedSpec`→fetch / costed plan).
- GY-C report: operations registry (discovered) + playbooks (C1); **spine-rot repair
  evidence — governance tail + lex (C2)**; a route-consumed foundry method output with
  measurement-rooted authority (C3).
- GY-I event-backed agent audit (Ring-1 role events; Ring-2 rejection test; VOI/input
  bias normalization evidence).
- GY-F report: failed-workflow blocked/downgraded across surfaces;
  `SecretAndPIIScanReport`; `CASIntegrityReport`; `TimeSourceEnvelopeAudit`; S12
  dereference; 406-row `AuthorityCandidateInventory`.
- GY-G composition report (`CompositionCertificate`; feedback rejection; emergent cap).
- GY-M1 artifact-family lifecycle registration (+ drift gate); GY-M2 GX validator run on a non-pinned case.
- GY-J graded-outcome report; GY-K scholar growth; GY-L pinned-route loop outcome.
- **Phase 5 generation-cycle artifacts (each with a recomputing validator + negative test):**
  GY-N0 disposition ledger + consumption-validator green; the three foundation bridges
  (`DesignProblem`, `InterventionAtomBinding`, `WorldModelRecord`) with content-bound provenance;
  the GY-S substrate registry + the L1/L4/L5, L2/L3, L6 lift receipts; **GY-N-V `ValueOuterSet`
  set-valued value evidence (proxy bounded, point narrow; `unknown`/incomparable on timeout)**; a
  cycle run emitting the **four stratified fronts** (DecisionFront / ResearchFront / QuarantineFront
  populated / PortfolioFront deferred); GY-N7 ID/CERT/COV acquisition + affected-region
  revalidation receipt; GY-N8 value-outer-set + transport receipt naming a world version; **GY-N11
  confidence-ledger risk-spend report (`Σ α ≤ δ`)**; **GY-N12 epoch / stale-certificate
  revalidation evidence on an L3-amendment or L5-schema-regime boundary**; GY-N10 ≥2-domain
  end-to-end honest terminals; StrangleReceipts for every superseded generator / single-pass path.
- **Phase 6 learning-loop artifacts:** GY-O0 EvalSafety gate (mode-specific blocked-attempt
  evidence); GY-O1 confirmatory Bayesian deployed-effect update persisted to `fabric/world`; GY-O2
  FDR-controlled anomaly→hypothesis candidate; GY-O3 versioned `WorldModelRecord` write-back a
  later cycle grounds against.
- **Phase 7 verification artifacts (each with a recomputing validator + negative test):**
  GY-V1 matrix-closure delta; GY-V2 e2e loop run (Workspace graph, `SearchLedger`,
  `SearchExitContract`, `ProductionLoopRunProof`, reproducible hashes); GY-V3 multi-case
  terminal/evidence-kind/decision-grade distribution; GY-V4 adversarial-against-A
  battery results; GY-V5 replay A/B/C proof; GY-V6 full validator-suite green report;
  GY-V7 health-signal readout.
- Updated coverage matrix showing the moved rows; GX validator pass over all GY artifacts.

## 13. Authority = two orthogonal axes (evidence_kind ⟂ decision_grade)

The earlier single grade order conflated two different things. They are **orthogonal**
and `meet`s independently (§7):

- **`evidence_kind`** — WHAT kind of evidence backs the claim. It is a **partial order**,
  not a total grade chain. `measurement` is strongest for directly observed facts;
  `derivation` is below `measurement` only when it is near-lossless and references
  measurement roots; `proxy` and `transport` are incomparable unless a rule proves one
  dominates for the claim type; `bounds` is an interval/identification class that may be
  decision-usable without being more "truthful" than `simulation`; `simulation` is
  model-based and may be calibrated or uncalibrated; `elicitation` is weakest unless a
  governed mandate/participation rule explicitly elevates its decision role. Rung-7
  "acquisition plan" is not an evidence_kind — it is the `acquisition_required`
  *terminal*, a plan not evidence.
- **`decision_grade`** — HOW decision-ready the claim is (total order):
  `unsupported` < `descriptive_only` < `advisory_admissible` < `decision_admissible`.
- **`calibrated`** is **not** a grade — it is a property of `evidence_basis`
  (`calibration_refs` present + non-zero denominator) that can *lift* `decision_grade`
  for a given `evidence_kind`. Calibration of a simulation can make it
  `advisory_admissible`; it does not turn it into `measurement`.

Worked mixed examples at the contested seams (these pin the semantics for GY-A2/GY-G):

- `(evidence_kind=bounds, decision_grade=advisory_admissible)` — Manski bounds on real
  panel data: weak evidence_kind, but the *interval* is decision-usable as a guardrail
  → advisory. **Beats** `(simulation, descriptive_only)` on decision_grade though it is
  weaker in evidence_kind — which is why one total order was wrong.
- `(evidence_kind=simulation, decision_grade=advisory_admissible)` only if the structural
  model is `calibrated` (calibration_refs present); otherwise `simulation` caps at
  `descriptive_only`. An *uncalibrated* simulation is never `advisory_admissible`.
- `(evidence_kind=measurement, decision_grade=descriptive_only)` — a directly measured
  correlation that does **not** identify the causal effect: strongest evidence_kind, but
  only descriptive readiness. Measurement ≠ decision-ready.
- `decision_admissible` requires BOTH a sufficient evidence_kind for the claim_type
  **and** calibration + closed counterexamples + an in-envelope `CertifiedOperationEnvelope`
  (it is the only `decision_grade` the promotion gate D3.8 admits to production posture).
- Composition (`meet`): `evidence_kind = ⊓ upstream kinds`, returning the strongest
  lower bound when comparable; if kinds are incomparable, the result is
  `incomparable_meet` until an explicit cap/downgrade/obligation rule resolves the
  combination. `decision_grade = min upstream`, independently. A program whose chapters are
  `(measurement, decision_admissible)` but coupled by an ungrounded `simulation` emergent
  claim composes to `(simulation, advisory_admissible)` at best — the emergent claim caps
  both axes (§7 stage 3).

Gap → ladder descent is the VOI-driven choice of the next Operation; the
`(evidence_kind, decision_grade)` pair reached is recorded on the frontier artifact and
in the `SearchExitContract`.

## 14. Relationship to GX and the roadmap

GX guarantees honesty (the waist cannot lie). GY grows capability **through** the honest
waist — now as a universal execution topology, not a fixed DAG. GX completes at an honest
blocker (`search_ceiling_repair_required` baseline). GY's first milestone is **not** full
policy-design synthesis: it proves, through the durable production trigger, that the loop
can (a) ground one catalog-supported estimate-level case with a verifier-derived
`AuthorityBoundary`, and (b) stop an acquisition-heavy tourism/local-development case as
an honest search/acquisition ceiling. The first full design milestone comes after Phase 2
subordinates lowering/drafter/lex/playbooks and GY-L records a real loop outcome with
input/output hashes, producer roots, `SearchExitContract`, and verifier-stamped
authority. Only then do T1 (groundable at acceptable cost?) and T6 (does demand overcome
abstention inertia?) become empirically answerable for generated policy designs.
