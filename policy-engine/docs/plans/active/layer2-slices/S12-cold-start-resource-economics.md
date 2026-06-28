---
title: PolicyOS Layer 2 S12 Cold-Start And Resource Economics Implementation Plan
status: active
owner: principal-governance
created: 2026-06-02
last_verified: null
stability: draft
revision_note: drafted 2026-06-02 after S11 verification; expands the roadmap S12 closure contract into red-first tasks and handles the burn-down endgame (last open cell -> 0)
slice: S12
slice_label: cold_start_resource_economics
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
floor_governance: ../../../../architecture/policy_design_case/layer2_floor_governance.toml
artifact_traceability: ../../../../architecture/policy_design_case/layer2_artifact_traceability.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on:
  - S3
  - S7
cells_closed:
  - DESIGNER_ITSELF.envelope_growth
expected_current_open_cell_count: 0
floor_id: s12_growth_thermometers
floor_metric: reuse_rate_and_override_rate_trend
---

# Layer 2 S12 - Cold-Start, Resource Economics, And Reflexive Self-Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

Read this whole file before editing. Execute tasks in order, keep commits
task-sized, and preserve the repo rule that the designer applies its own
discipline to its own growth: growth is counted only against a certified
envelope delta, bespoke one-off growth is never mechanism growth, and the
meta-regress of "who sets the mission/budgets/values" stops at the accountable
principal.

S12 closes the **last** open Layer 2 cell, `DESIGNER_ITSELF.envelope_growth`,
taking the cluster-map open cell count from `1` to `0`. This is the burn-down
endgame: after S12 the 17-cell open set is fully closed. S12 does **not** mark
S13 post-deploy accountability/envelope-shrink, S14 universality, production
authority, preference learning, or a falsely precise MDP/bandit optimizer as
implemented. Envelope **shrink** (bidirectional revision) belongs to S13; S12
implements the expand/growth direction plus the governed allocation policy.

## Goal

S12 makes the designer's own growth a governed, replayable resource-economics
decision instead of ad-hoc capability accretion. It consumes the S0
`ValueOfInformationEstimate` currency across at least three sites
(acquisition, refinement, attention, oracle, allocation), coordinates the
typed budgets the principal delegates through the S7 `DelegationContract`
(compute, acquisition money, expert time, human attention, legal access),
presents allocation tradeoffs as a Pareto frontier rather than a single
scalarized optimum, and records bootstrap thermometers (override-rate down,
reuse-rate up, held-out pending S14) plus an envelope-growth ledger keyed to
certified envelope deltas.

The closure contract is the roadmap S12 contract:

- producer: allocation policy plus bootstrap thermometers over S3/S7/VOI inputs.
- persisted artifact: an envelope-growth ledger whose every growth entry cites a
  `CertifiedEnvelopeDelta` (or pending-delta ref), plus a knowledge-governance
  throughput ledger.
- bridge/consumer: allocation drives slice/acquisition priorities and is read by
  the S2 shadow loop as injected posture, never as production authority.
- surface: explore/exploit posture and thermometers are visible in EXPERT and
  MACHINE projections; PUBLIC sees only a high-level growth/limitation note.
- semantic test: new cases reuse facet/design/projection primitives (reuse-rate
  trends up, override-rate trends down) without adding case-specific code.
- negative control: bespoke one-off growth is flagged and not counted as
  mechanism growth; allocation that games internal metrics is blocked; growth
  without an envelope delta is rejected.
- floor: `reuse_rate_and_override_rate_trend` is recorded from the governed floor
  table; growth counting requires an envelope delta; false-clear counts remain
  zero.

## Architecture

S12 is a runtime-quality reflexive self-design layer over existing acquisition,
delegation, ratchet, VOI, and Pareto substrates:

- `src/polisyos/pdc/_impl/layer2_readiness.py` already defines the S0
  `ValueOfInformationEstimate` currency, `CertifiedOperationEnvelope`, and the
  authority-boundary base. S12 reuses the VOI currency; it must not invent a
  second VOI vocabulary.
- `src/polisyos/runtime/quality/acquisition_planner.py` and
  `src/polisyos/runtime/quality/design_axes/substrate_acquisition.py` already rank
  acquisition by VOI (S3). S12 consumes the acquisition VOI site; it does not
  rebuild the acquisition loop.
- The S0 `MinimalSeedManifest`
  (`architecture/policy_design_case/layer2_minimal_seed_manifest.json`) is the
  authoritative source of the **five** typed budgets:
  `["compute", "acquisition", "expert_time", "human_attention",
  "legal_access"]`. S12 carries all five budget kinds from the seed manifest; it
  must not invent budget kinds or treat them as interchangeable.
- `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py` (S7) already owns the
  `DelegationContract` with `compute_budget_ref`, `acquisition_budget_ref`, and
  `human_attention_budget_ref` (the per-principal refs for three of the five
  seed-manifest budgets), plus `maximum_stakes_band`, `value_policy_ref`, and
  `override_policy_ref`. S12 reads those refs; `expert_time` and `legal_access`
  budgets come from the seed manifest (with `legal_access` also grounded in S3
  source-contract rights/legal-use scope).
  **The explore/exploit dial already has an S0 home - do not add a field to the
  frozen S7 `DelegationContract`.** `MinimalSeedManifest.principal_set_explore_exploit`
  is a typed, validated S0 field (`pdc/_impl/layer2_readiness.py`, current value
  `"principal_set_explicit_governed_balance"`). So the dial design is:
  (1) the governed **default/seed** is `MinimalSeedManifest.principal_set_explore_exploit`;
  (2) a **per-case principal setting** is a governance-act ref
  (`explore_exploit_dial_ref`) carried in the S12 inputs and validated as
  authorized by a valid S7 `DelegationContract` (the dial act cites the
  `contract_ref`/principal). This needs **zero changes to the frozen
  `DelegationContract`** and zero S0 change (both homes already exist). If a
  typed per-case decision class is later wanted, append an `explore_exploit_dial`
  entry to the S7 **registry** (`build_governance_decision_class_registry`'s
  `role_by_class` list, exactly like `value_authorization`) - a list append,
  never a new `DelegationContract` field. S12 never self-sets the dial
  (`meta_regress_past_principal` firewall). S12 does not create delegation
  authority or an attention ledger (that minimal ledger remains future work).
- `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py` (S8) already owns
  `ParetoArchive`. S12 presents allocation-policy tradeoffs as a Pareto frontier
  by reusing that archive shape; it must not collapse the frontier into a hidden
  scalar and must not select a policy without the principal's dial.
- `src/polisyos/runtime/quality/capability_ratchet.py` and
  `architecture/policy_design_case/capability_reality_report.json` are the
  envelope/burn-down tracker. S12 reads ratchet/cluster-map deltas as the
  ground truth for "did the certified envelope actually change."
- `src/polisyos/runtime/quality/performance_budget.py` is the multi-fidelity
  compute economy. S12 records its VOI/budget site; it does not rewrite it.
- `src/polisyos/pdc/_impl/layer2_design_search.py` already carries the
  S5/S6/S7/S8/S10/S11 injected-posture pattern. S12 adds
  `Layer2S12ResourceEconomicsPostureInput` and passes it as data. PDC search
  must not import `polisyos.runtime.quality.design_axes.resource_economics` or call
  S12 producer helpers directly.

Boundary rule: S12 can produce allocation/ledger/thermometer artifacts and PDC
posture. Downstream consumers may inherit S12 limitations and priorities, but
S12 grants no production, publication, approval, rollout, or closeout authority,
and the meta-allocation it designs is robust/governed, not a precise optimizer.

## Scope

In scope:

- strict Pydantic runtime-quality contracts exported from
  `polisyos.runtime.quality`.
- `KnowledgeGovernanceThroughputLedger` (the S12 traceability artifact already
  named by `layer2_artifact_traceability.toml`) plus the S12 growth artifacts:
  `EnvelopeGrowthLedger`, `ResourceAllocationPolicy`, `GrowthThermometerRecord`,
  and `ResourceEconomicsIntegrityReport`.
- a shared VOI allocation over at least three of the canonical sites
  (`acquisition`, `refinement`, `attention`, `oracle`, `allocation`), with a
  per-site VOI consumption record and a count.
- typed-budget portfolio rows for compute, acquisition money, expert time,
  human attention, and legal access, with no false interchangeability.
- an explore/exploit posture read from the S7 `DelegationContract` dial and a
  Pareto frontier of allocation policies (reusing S8 `ParetoArchive`).
- bootstrap thermometers: override-rate (regime/coupling/value/decomposition/
  final-selection decisions from S4/S5/S7/S8), reuse-rate (primitive reuse vs
  one-off growth), and a held-out-pending marker (S14 owns the real battery).
- an envelope-growth ledger whose entries each cite a certified envelope delta
  (cluster-map/ratchet delta) and the demand act that pulled the growth.
- demand-pulled bootstrap signals from S7 human acts (value_authorization,
  regime_override_with_provenance, decomposition_override, final_selection,
  a_spec_gap, acquisition approval/rejection) as growth seeds, consumed by ref.
- W12.D S12 blocks for all 13 universal corpus cases.
- negative controls for bespoke one-off growth, allocation gaming, floor
  lowering for `useful_design_rate`, B-faster-than-A growth, meta-regress past
  the principal, interchangeable budgets, and growth without an envelope delta.
- the burn-down endgame: close `DESIGNER_ITSELF.envelope_growth`, take open cell
  count to `0`, and keep both validators green with an empty open-cell set.
- manifest, inventory, traceability, readiness validator, floor metric, and
  repo-quality coverage, including the full open-count snapshot burn-down across
  every prior-slice repo test and the cluster-map negative-control endgame.

Out of scope:

- S13 post-deploy accountability, `DeploymentDossier`, `DivergenceRecord`,
  `LearningUpdateProposal`, `EnvelopeRevision` shrink, `AssuranceCaseDelta`, or
  MAPE-K. S12 implements the expand/growth direction only; bidirectional shrink
  is S13.
- a precise MDP/bandit/RL optimizer, a learned allocation controller, or
  automated preference learning.
- a new attention ledger or `OversightEffectivenessReport` (S13).
- S14 universality battery, held-out battery execution, or self-description
  authority.
- production recommendation, rollout, publication, approval, claim, scorecard,
  closeout, or preference-learning authority.

## Pattern Pass

Open the failure register before implementation and before closeout:
`docs/reference/policy-design-case-failure-patterns.md`.

| Pattern | S12 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | VOI/acquisition/ratchet/Pareto seeds exist, but no Layer 2 allocation producer, growth ledger, thermometer floor, or consumer path proves growth is governed. | Add typed contracts, producer, corpus route, PDC posture, manifest, readiness checks, and negative semantic tests. |
| P03 hidden internal richness | Explore/exploit posture, per-budget VOI, and thermometers can stay internal. | Surface explore/exploit posture, per-site VOI, and thermometers in EXPERT/MACHINE; PUBLIC gets a high-level growth/limitation note only. |
| P04 status lattice gap | `exploit`, `invest`, `growth_counted`, `growth_flagged`, and `allocation_blocked` can drift from existing authority/status semantics. | Map S12 dispositions to existing authority boundaries; add mixed-status tests. |
| P05 authority dilution | An allocation policy or growth entry can look like production/recommendation authority. | Every S12 artifact carries `authoritative_for`/`may_not_use_for`; consumers inherit the weakest boundary. |
| P07 replay gap | Growth or allocation can change without a replay-visible envelope delta. | Persist rule/schema versions, certified-envelope-delta refs, demand-act refs, and budget refs; growth counting requires an envelope delta. |
| P10 semantic adequacy gap | Field presence can pass while bespoke growth is counted as mechanism growth. | Red-first semantic tests + negative probes for bespoke growth, gaming, and growth-without-delta. |
| P11 failure-only memory | Growth can be recorded from successes only, hiding override/regret signals. | Thermometers track override-rate and reuse-rate together; growth ledger records demand and overrides, not just wins. |
| P12 producer fragmentation | VOI can be consumed inconsistently across acquisition/refinement/attention/oracle/allocation. | Require the shared `ValueOfInformationEstimate` currency and a per-site allocation record; count the sites. |
| P13 governance gravity well | The cell firewall: allocation/growth machinery can balloon into a governance taxonomy and a falsely precise optimizer. | Keep the allocation policy robust/governed and small; reuse S3/S7/S8 substrates; present a Pareto frontier, not an MDP optimum. |
| P15 candidate laundering | LLM-proposed growth or allocation can look authoritative. | Allocation/growth proposals are candidate-only unless the producer and the principal's dial authorize them. |
| P25 search-control laundering | Allocation can make the current frontier look exhaustive or production-ready. | Preserve search incompleteness; keep allocation separate from recommendation/closeout authority. |

Capability label transition:

- start: `DESIGNER_ITSELF.envelope_growth` is `implemented_but_not_orchestrated`
  with `bridge_missing` and firewall `P13_governance_gravity`;
  `s12_growth_thermometers` floor exists but is not wired.
- target: `DESIGNER_ITSELF.envelope_growth` is `implemented`; cluster-map open
  cell count is `0`; governed Layer 2 inventory count increases by one.
- missing chain to close: producer, persisted artifact, orchestration bridge,
  consumer, verification, surface, semantic test, and negative controls.

## Code-Grounded Reality Check

Current S12 anchors:

- `architecture/policy_design_case/layer2_slice_cell_matrix.toml` assigns
  `DESIGNER_ITSELF.envelope_growth` to S12 (`target_state = "implemented"`,
  `layer = "resource_economics_and_envelope_growth"`). It is the only remaining
  open cell. S13 has no matrix cell assignment; envelope shrink is an S13 layer
  advance over the cell S12 closes.
- `architecture/policy_design_case/cluster_ownership_map.toml` has
  `[cell.DESIGNER_ITSELF.envelope_growth]` as
  `ratchet_state = "implemented_but_not_orchestrated"`,
  `p01_chain = "bridge_missing"`, firewall `P13_governance_gravity`,
  `publishes = ["DESIGNER_ITSELF.certified_envelope_delta"]`, and
  `consumes = ["SYSTEM.nonstationarity", "KNOWLEDGE.substrate_coverage",
  "SYSTEM.measurability", "ACTOR.state_capacity_feasibility",
  "OTHER_AGENTS.strategic_response"]`. Seed files
  (`architecture/policy_design_case/capability_reality_report.json`,
  `src/polisyos/runtime/quality/capability_ratchet.py`) exist.
- `architecture/policy_design_case/layer2_floor_governance.toml` declares
  `floor_id = "s12_growth_thermometers"`,
  `metric = "reuse_rate_and_override_rate_trend"`,
  `floor_owner = "principal-governance"`, and revision rule
  `growth_counting_requires_envelope_delta`.
- `architecture/policy_design_case/layer2_artifact_traceability.toml` contains
  only `KnowledgeGovernanceThroughputLedger` for S12 as `planned`. This plan
  must add the remaining S12 growth artifacts instead of pretending the
  throughput ledger alone is the capability.
- `ValueOfInformationEstimate` is an S0 artifact and is already consumed in
  `src/polisyos/runtime/quality/design_axes/substrate_acquisition.py` (acquisition),
  `src/polisyos/pdc/_impl/layer2_design_search.py` (refinement), and
  `src/polisyos/runtime/quality/consultation.py`. S12 must coordinate these
  through a shared allocation, then add the missing sites (attention via S7,
  oracle via S4/S5/S8 override seeds, allocation via S12 itself).
- `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py` exposes
  `compute_budget_ref`, `acquisition_budget_ref`, `human_attention_budget_ref`
  on `DelegationContract`. The explore/exploit dial is a principal act; S12
  reads it as a ref, never sets it.
- `tools/quality/validation/run_universal_outcome_corpus.py` currently computes
  S4/S5/S6/S7/S8/S10/S11 and injects posture into S2. Insert S12 after S11 (it
  needs S3 acquisition refs, S7 delegation refs, and the S11 axis/forecast
  posture for reuse-rate signals), then pass S12 posture into the pinned S2 case.
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
  validates up through S11 and reports inventory artifact count `19`. S12
  registration should update this to `20` and the live open cell count to `0`.

## Code-Grounded Workload Boundaries

- Strong substrate: `Layer2ReadinessModel`, `AuthorityBoundary`,
  `ValueOfInformationEstimate`, and `CertifiedOperationEnvelope` are strict and
  reusable. No new DTO base or VOI vocabulary is needed.
- Strong substrate: S8 `ParetoArchive` already separates frontier facts from a
  selected scalar. S12 should reuse it for allocation-policy tradeoffs.
- Strong substrate: the capability ratchet + cluster map already define the
  certified envelope. S12 reads their delta as the growth-counting source of
  truth instead of inventing a private growth metric.
- Real wiring cost: S5/S6/S7/S8/S10/S11 posture DTOs live in
  `src/polisyos/pdc/_impl/layer2_design_search.py`.
  `Layer2S12ResourceEconomicsPostureInput` belongs beside them and is exported
  through `polisyos.pdc`. Threading it touches `Layer2S2DesignSearchRun`,
  `run_s2_shadow_design_loop(...)`, `_search_ledger`, `_design_record`,
  `_deterministic_replay_key`, cluster-interface/handoff helpers, and projection
  helpers, plus CAS round-trip/default tests.
- Real wiring cost: the W12.D full S2 loop runs only for the pinned
  `ua-msme-affordable-loans-2022` case. The other 12 cases get S12 corpus blocks
  plus a lightweight S2 posture ref; do not force full S2 search for all 13.
- **Burn-down endgame (the largest snapshot tax in the slice sequence):** S12
  takes the live open cell count from `1` to `0`. Every prior-slice repo-quality
  test that asserts the live open count `== 1` must become `== 0`, the readiness
  `cells_closed_since_s0` constant must grow to all 17 cells, and the cluster
  negative-controls that pick a remaining open cell now have **no** real open
  cell to pick. Treat this as semantic test work, not a find-and-replace.
- Weak spot: traceability has only `KnowledgeGovernanceThroughputLedger` for
  S12. Adding the other four growth artifacts is real contract work.
- Complexity guard (P13): do not build an RL/MDP/bandit optimizer, a learned
  controller, or a budget-conversion model. S12 records a robust governed
  allocation policy, a Pareto frontier, and thermometers - nothing more.

## Implementation Design And Code Interrelationships

This section pins the *best* implementation given what the code actually
provides, so the producer is a thin governed coordinator over existing
economies, not a new engine. Read it before Task 2.

### 1. VOI is a qualitative currency - allocate by coordination, not magnitudes

`ValueOfInformationEstimate` (S0, `pdc/_impl/layer2_readiness.py`) is a
**skeleton**: `estimate_id`, `purpose`, `budget_dimensions` (budget *names*),
`used_by_sites` (site *names*), `owner`, `rule_version_ref`. There is **no
numeric VOI magnitude**, by design (the arch doc forbids a falsely precise
optimizer). So "consume the VOI currency across >=3 sites" is implemented as
**site/budget coordination over `used_by_sites` / `budget_dimensions`**, plus a
robust governed priority *ordering* - never a scalar optimum.

The real per-site sources already exist:

| VOI site | Existing source (read by ref, never recomputed) | `used_by_sites` value today |
| --- | --- | --- |
| `acquisition` | `acquisition_planner.plan_requirement_gap_acquisition(..., voi_report=...)` -> `_voi_ranking_ref` / `_ranked_voi_by_gap`; S3 `layer2_substrate_acquisition.py` builds the estimate | `["layer2_s3_substrate_acquisition"]` |
| `refinement` | S2 `layer2_design_search.py` `_refinement_decision(...).value_of_information` | `["layer2.s2.shadow_design_loop"]` |
| `attention` | S7 `HumanDecisionRequest.voi_rank` + `attention_cost_rank` (`layer2_delegation.py`) | (S12 records `["layer2.s7.attention"]`) |
| `oracle` | S4 regime / S5 coupling / S8 value override seeds (decision acts that seed the oracles) | (S12 records `["layer2.oracle"]` when an override act is present) |
| `allocation` | S12 itself (the meta-allocation) | `["layer2.s12.resource_allocation"]` |

`allocate_value_of_information(...)` therefore **aggregates** the existing
estimates' `used_by_sites` into the canonical taxonomy and reports
`voi_site_count = len(distinct used_by_sites)`. Acquisition + refinement +
attention give three grounded sites with zero new estimation; oracle/allocation
extend coverage. It must keep each site's VOI inside its typed budget dimension
(no cross-budget conversion -> the `interchangeable_budget` firewall).

### 2. The certified-envelope delta comes from the ratchet + cluster map; the typed `CertifiedEnvelopeDelta` is S13's

`capability_ratchet.build_capability_reality_report(...)` plus the cluster-map
open-cell count are the **ground truth** for "did the certified envelope
actually change." There is no `CertifiedEnvelopeDelta` class in `src/` today, and
traceability assigns `CertifiedEnvelopeDelta` to **S13** (`planned`). So S12 must
**not** create that typed artifact; each `EnvelopeGrowthLedger` entry cites a
delta **ref** describing the real change (e.g. `open_cell_count: N->M`,
`capability_reality_state: X->Y`) derived from the ratchet/cluster-map. The
`growth_counting_requires_envelope_delta` revision rule is enforced by refusing
to count any growth entry whose delta ref does not resolve to a real
ratchet/cluster-map change. S12's own closure (open `1 -> 0`, burn-down complete)
is itself a real envelope delta and is the ledger's anchor entry; per-case
hypothetical growth uses explicit `pending_envelope_delta_ref`. The
`DESIGNER_ITSELF.certified_envelope_delta` the cell publishes is this ref, not
the S13 object.

### 3. The allocation Pareto frontier reuses S8 `ParetoArchive`; the S7 dial is the value schedule

Do not invent frontier logic. `build_resource_allocation_policy(...)` builds an
S8 `ParetoArchive` (`layer2_value_choice.py`) of candidate allocation policies:
`nondominated_alternative_ids` = the non-dominated policies, `objective_refs` =
budget dimensions / mission. The S8 `RankingMode` maps the dial exactly:

- explore/exploit dial present -> `ranking_mode = "ranked_with_authorized_values"`
  (the dial is the authorized value schedule that selects one policy);
- dial absent -> `ranking_mode = "unranked_frontier_only"` (present tradeoffs,
  select nothing);
- `shadow_scenario_ranking` for what-if dials that are not authorized.

This directly implements "the system presents a Pareto frontier and the
principal sets the dial," and inherits S8's normative firewall (no value/weight
selection without an authorized schedule) for free, so S12 cannot self-set the
dial (the `meta_regress_past_principal` firewall).

### 4. Typed budgets and the compute economy

The five typed budgets come from `MinimalSeedManifest.budgets`
(`[compute, acquisition, expert_time, human_attention, legal_access]`). S7's
`DelegationContract` supplies the per-principal refs for `compute`,
`acquisition`, `human_attention`; `compute` is further grounded in
`performance_budget.run_cost_budget_policy_from_performance_budget(...)`
(wall-clock economy); `legal_access` is grounded in S3 source-contract
rights/legal-use scope. `expert_time` is the seed-manifest budget with the S7
human-attention ref as its nearest per-principal proxy. (Thermometer signals are
in #6.)

### 6. Honest, ungameable thermometers (override-rate and reuse-rate)

The user-facing risk is a thermometer "improving" by gaming, not by mechanism
maturity. Both rates are therefore anchored to a **frozen/fixed reference**, and
S12 records the anchor so the trend is auditable.

**Override-rate** (should trend down "without reducing required questions"):

- **Source of truth is S7 `HumanDecisionRecord`s**, not the S4/S5/S8 blocks - I
  verified those blocks emit **no** human-override signal today. An override is a
  record with `decision_action_exercised in {"reject", "revise_scope"}` (the
  human changed/rejected the A-side proposal); `approve` is not an override.
- **Instrumented decision classes only.** The S7 registry
  (`build_governance_decision_class_registry`) has `final_choice`,
  `value_authorization`, `a_spec_gap`, `mandate_boundary` (override-eligible) but
  **no** `regime_override` or `decomposition_override` class. So
  `override_rate` is computed only over the instrumented classes, and
  `uninstrumented_override_dimensions = ["regime", "decomposition"]` is recorded
  honestly (these become instrumented later when S4/S5 emit override acts or the
  S7 registry gains those classes). **Do not fabricate a five-dimension rate.**
- **Fixed denominator = required questions.** `override_rate =
  overrides / required_decisions`, where `required_decisions` is the count of
  override-eligible decisions the `DecisionRightsMatrix` *required*, read from
  S7, never shrunk by S12. The thermometer records `required_question_count`, and
  the trend is `improving`/`flat` only if `required_question_count` is
  non-decreasing - this is the anti-gaming block against "lower the rate by
  asking fewer questions."

**Reuse-rate** (should trend up: new cases reuse primitives, not one-offs):

- **Anchor = the frozen `MinimalSeedManifest` primitive sets**:
  `facet_primitives` (9), `instrument_modality_primitives` (8),
  `projection_primitives` (8), plus the composition operators. A reused primitive
  counts toward `reuse_rate` **only if it is in those frozen sets**.
- A construct **not composed from frozen primitives is a one-off**: it counts
  against reuse and is flagged `bespoke_one_off_growth`. So reuse-rate **cannot
  be inflated by relabeling a bespoke construct as a "primitive,"** because the
  frozen seed set is the only thing that counts - expanding it is a governance
  act, not S12's to do. The thermometer records `frozen_primitive_set_ref`,
  `reused_primitive_refs` (all must be members of the frozen set), and
  `one_off_growth_refs`.

Held-out stays `pending_s14` (S12 must not run or claim the held-out battery).

### 5. Corpus wiring mirrors the S10/S11 helper shape exactly

The route already defines `_s11_predictive_knowledge_case_block(...)`,
`_s11_predictive_knowledge_summary(...)`, `_s11_predictive_posture_input(...)`,
and the post-S2 finalization helper `_s10_with_source_design_record(...)`. S12's
`_s12_resource_economics_case_block(...)` /`_summary(...)` /`_posture_input(...)`
mirror those signatures and call sites (the S11 posture is injected near route
line ~1277; S12 adds its posture input beside it). If the S12 block needs a
`source_design_record_ref` known only after `_s2_design_search_summary(...)`,
use the `_s10_with_source_design_record(...)` finalization pattern rather than a
circular producer dependency.

### Data-flow map (which existing block feeds which S12 field)

| S12 field | Fed by |
| --- | --- |
| `voi_allocations[*].used_by_sites` | S2 refinement VOI, S3 acquisition `voi_report`, S7 attention `voi_rank` |
| `typed_budget_rows` | `MinimalSeedManifest.budgets` + S7 `DelegationContract` budget refs + `performance_budget` (compute) + S3 source contracts (legal_access) |
| `pareto_archive_ref` / `selected_policy_ref` | S8 `ParetoArchive` + S7 explore/exploit dial (value schedule) |
| `envelope_growth_ledger.growth_entries[*].certified_envelope_delta_ref` | `capability_ratchet.build_capability_reality_report` + cluster-map open-count delta |
| `growth_entries[*].demand_act_ref` | S7 registry decision acts that exist today (`value_authorization`, `final_choice`, `a_spec_gap`, `acquisition`, `budget_use`, `mandate_boundary`, `data_access`); D3.10's `regime_override_with_provenance`/`decomposition_override` are conceptual seeds, not yet S7 classes |
| `growth_thermometer.override_rate` | S7 `HumanDecisionRecord`s with `decision_action_exercised in {reject, revise_scope}` on instrumented classes (`final_choice`, `value_authorization`, `a_spec_gap`, `mandate_boundary`); `regime`/`decomposition` recorded as `uninstrumented_override_dimensions` (see #6) |
| `growth_thermometer.required_question_count` | `DecisionRightsMatrix` required decisions (fixed denominator; anti-gaming) |
| `growth_thermometer.reuse_rate` | frozen `MinimalSeedManifest` primitive sets vs one-off-growth refs (anti-relabel; see #6) |
| `explore_exploit_posture` / dial | `MinimalSeedManifest.principal_set_explore_exploit` (seed) + S7-authorized `explore_exploit_dial_ref` act (per-case; never self-set) |

## S12 Closure Metrics

S12 closure is measured against these exact constraints:

- slice: `S12`.
- cells closed: `["DESIGNER_ITSELF.envelope_growth"]`.
- open-cell delta: `-1`; expected current open cell count becomes `0`.
- remaining open cells after S12: `[]` (the 17-cell open set is fully closed).
- floor: `s12_growth_thermometers`; metric `reuse_rate_and_override_rate_trend`.
- governed Layer 2 inventory artifact count after S12: `20`.
- required artifacts: `KnowledgeGovernanceThroughputLedger`, `EnvelopeGrowthLedger`,
  `ResourceAllocationPolicy`, `GrowthThermometerRecord`,
  `ResourceEconomicsIntegrityReport`.
- corpus case count: `13`.
- VOI consumption sites: at least `3` of
  `{acquisition, refinement, attention, oracle, allocation}`, recorded per site.
- typed budget kinds carried without interchangeability: `5`
  (compute, acquisition_money, expert_time, human_attention, legal_access).
- override-rate trend: non-increasing across the corpus seed (down or flat).
- reuse-rate trend: non-decreasing across the corpus seed (up or flat).
- envelope-growth ledger entries each cite a certified-envelope-delta ref (or an
  explicit pending-delta ref); growth-without-delta count is `0`.
- held-out battery status: `pending_s14` (S12 must not execute or claim the
  held-out battery).
- all S12 false-clear count fields: `0`.

## Contract Dictionary

Runtime constants:

- `LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION =
  "policyos.policy_design_case.layer2_s12_resource_economics.v1"`
- `LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION =
  "policyos.layer2.s12.resource_economics.v1"`
- `S12_GROWTH_THERMOMETERS_FLOOR_ID = "s12_growth_thermometers"`
- `S12_VOI_SITES = ("acquisition", "refinement", "attention", "oracle", "allocation")`
- `S12_TYPED_BUDGETS = ("compute", "acquisition_money", "expert_time",
  "human_attention", "legal_access")`
- `S12_FALSE_CLEAR_FIELDS = ("bespoke_one_off_growth",
  "allocation_gaming_internal_metrics", "floor_lowering_for_useful_design_rate",
  "b_faster_than_a_growth", "meta_regress_past_principal",
  "interchangeable_budget", "growth_without_envelope_delta")`

Runtime literals:

- `ExploreExploitPosture = Literal["exploit_in_envelope", "invest_in_growth",
  "balanced_governed", "blocked"]`
- `GrowthCountingDisposition = Literal["counted_mechanism_growth",
  "flagged_bespoke_one_off", "blocked_no_envelope_delta", "advisory_only"]`
- `BudgetKind = Literal["compute", "acquisition_money", "expert_time",
  "human_attention", "legal_access"]`
- `VoiSite = Literal["acquisition", "refinement", "attention", "oracle", "allocation"]`
- `ThermometerTrend = Literal["improving", "flat", "regressing"]`

Runtime models:

- `ResourceAllocationPolicy`
- `EnvelopeGrowthLedger`
- `GrowthThermometerRecord`
- `KnowledgeGovernanceThroughputLedger`
- `ResourceEconomicsIntegrityReport`

Runtime producer/verifier helpers:

- `build_resource_allocation_policy(...)`
- `allocate_value_of_information(...)`
- `build_envelope_growth_ledger(...)`
- `build_growth_thermometers(...)`
- `build_knowledge_governance_throughput_ledger(...)`
- `verify_resource_authority_envelope(...)`
- `summarize_resource_economics_integrity(...)`
- `build_s12_resource_economics_posture(...)`

PDC posture model:

- `Layer2S12ResourceEconomicsPostureInput`

Authority boundary:

- `authoritative_for` includes `value_of_information_allocation`,
  `explore_exploit_posture`, `envelope_growth_ledger`, `growth_thermometers`,
  `knowledge_governance_throughput`, `allocation_priority_input`, and
  `expert_machine_resource_projection`.
- `may_not_use_for` includes `production_authority`, `production_recommendation`,
  `rollout_authority`, `publication_authority`, `claim_authority`,
  `closeout_authority`, `approval_authority`, `scorecard_authority`,
  `preference_learning_authority`, `mdp_bandit_optimizer_authority`,
  `budget_interchangeability`, `mission_or_value_self_authorization`,
  `floor_relaxation`, `s13_envelope_shrink`, `s13_accountability_closure`, and
  `s14_universality`.

## File Map

Create:

- `src/polisyos/runtime/quality/design_axes/resource_economics.py`
- `tests/unit/runtime/quality/test_layer2_s12_resource_economics.py`
- `tests/fixtures/layer2/s12/s12_resource_economics_case_signals.json`
- `tests/fixtures/layer2/s12/s12_resource_economics_expert_labels.json`
- `tests/fixtures/layer2/s12/negative_controls/bespoke_one_off_growth_probe.json`
- `tests/fixtures/layer2/s12/negative_controls/allocation_gaming_internal_metrics_probe.json`
- `tests/fixtures/layer2/s12/negative_controls/floor_lowering_for_useful_design_rate_probe.json`
- `tests/fixtures/layer2/s12/negative_controls/b_faster_than_a_growth_probe.json`
- `tests/fixtures/layer2/s12/negative_controls/meta_regress_past_principal_probe.json`
- `tests/fixtures/layer2/s12/negative_controls/interchangeable_budget_probe.json`
- `tests/fixtures/layer2/s12/negative_controls/growth_without_envelope_delta_probe.json`
- `architecture/policy_design_case/layer2_s12_resource_economics_manifest.json`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py`

Modify:

- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/pdc/_impl/layer2_design_search.py`
- `src/polisyos/pdc/__init__.py`
- `src/polisyos/runtime/quality/projection_semantics.py`
- `src/polisyos/runtime/quality/public_export.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `architecture/policy_design_case/cluster_ownership_map.toml`
- `architecture/policy_design_case/layer2_artifact_traceability.toml`
- `architecture/policy_design_case/inventory.json`
- `tests/unit/pdc/test_layer2_readiness_contracts.py`
- `tests/unit/pdc/test_layer2_s2_design_search.py`
- `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- `tests/unit/runtime/quality/test_public_export.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`

Modify — **burn-down snapshot tax (open count `1 -> 0`).** These prior-slice
repo-quality tests assert the live open count `== 1`; every live assertion must
become `== 0`, and the cluster negative-controls must survive an empty open-cell
set (Task 6 Step 3). Static manifest fields (`sN_expected_current_open_cell_count`,
manifest `expected_current_open_cell_count`) are historical and must **not**
change.

- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py`

Do not modify `layer2_slice_cell_matrix.toml` (the S12 assignment already
exists) or `layer2_floor_governance.toml` (the `s12_growth_thermometers` floor
already exists).

## Task 1: Red-First S12 Semantic And Negative Tests

**Intent:** prove the repo fails the S12 contract before adding the producer,
manifest, and corpus wiring. Initial failures should be missing imports/fields
and absent S12 blocks. Do not weaken existing S3/S7/S8/S11 assertions.

**Files:**

- Create: `tests/unit/runtime/quality/test_layer2_s12_resource_economics.py`
- Create: the seven negative-control fixtures under
  `tests/fixtures/layer2/s12/negative_controls/`
- Modify: `tests/unit/pdc/test_layer2_readiness_contracts.py`
- Modify: `tests/unit/pdc/test_layer2_s2_design_search.py`
- Modify: `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- Modify: `tests/unit/runtime/quality/test_public_export.py`
- Modify: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py`

- [ ] **Step 1: Add runtime semantic tests**

Create `tests/unit/runtime/quality/test_layer2_s12_resource_economics.py` with:

- `test_s12_contracts_are_strict_replayable_and_exported`
- `test_voi_allocation_uses_shared_currency_across_at_least_three_sites`
- `test_typed_budgets_are_not_freely_interchangeable`
- `test_explore_exploit_posture_reads_s7_delegation_dial_not_self_set`
- `test_allocation_policy_presents_pareto_frontier_not_hidden_scalar`
- `test_growth_entry_requires_certified_envelope_delta`
- `test_bespoke_one_off_growth_is_flagged_not_counted_as_mechanism_growth`
- `test_allocation_gaming_internal_metrics_is_blocked`
- `test_floor_lowering_for_useful_design_rate_is_blocked`
- `test_b_capability_cannot_grow_faster_than_a_completeness_in_same_envelope`
- `test_meta_regress_stops_at_principal`
- `test_reuse_rate_up_and_override_rate_down_trend_passes_floor`
- `test_held_out_status_is_pending_s14_not_executed`
- `test_s12_integrity_report_requires_exact_false_clear_keys`

Each test imports from `polisyos.runtime.quality`; the first red run should fail
with `ImportError`/`AttributeError` for the missing S12 contracts.

- [ ] **Step 2: Add negative-control fixtures**

Each probe carries `probe_id`, `case_id`, `false_clear_field`,
`expected_false_clear_count = 0`, `expected_disposition`, and the exact fields
that trigger the block:

- `bespoke_one_off_growth_probe` (axis: a one-off construct/template counted as
  mechanism growth; expected `flagged_bespoke_one_off`).
- `allocation_gaming_internal_metrics_probe` (allocation maximizes an internal
  metric while user demand / hard-corner evidence is ignored; expected
  `blocked`).
- `floor_lowering_for_useful_design_rate_probe` (growth claimed by lowering a
  floor; expected `blocked`).
- `b_faster_than_a_growth_probe` (B capability growth outpaces A completeness in
  the same envelope; expected `blocked`).
- `meta_regress_past_principal_probe` (system sets its own mission/budgets/value
  tradeoffs; expected `blocked`).
- `interchangeable_budget_probe` (compute VOI substituted directly for human
  attention; expected `blocked`).
- `growth_without_envelope_delta_probe` (growth counted with no certified
  envelope delta; expected `blocked_no_envelope_delta`).

- [ ] **Step 3: Add PDC injected-posture tests**

Add to `tests/unit/pdc/test_layer2_readiness_contracts.py` and
`tests/unit/pdc/test_layer2_s2_design_search.py`:

- `test_layer2_s12_resource_economics_posture_input_is_strict_and_exported`
- `test_s2_consumes_injected_s12_posture_without_runtime_producer_import`
- `test_s2_s12_replay_digest_changes_only_when_resource_posture_changes`
- `test_s2_s12_search_ledger_defaults_preserve_legacy_cas_payloads`
- `test_s2_s12_persisted_search_ledger_round_trips_resource_refs`
- `test_s2_s12_handoff_records_consumed_posture_not_recommendation_authority`
- `test_s2_does_not_import_layer2_resource_economics`

The producer-import test must read
`src/polisyos/pdc/_impl/layer2_design_search.py` as text and assert it does not
contain `layer2_resource_economics`.

- [ ] **Step 4: Add projection/public-export tests**

Add to
`tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py` and
`tests/unit/runtime/quality/test_public_export.py`:

- `test_expert_machine_projection_surfaces_explore_exploit_and_thermometers`
- `test_public_projection_shows_growth_limitation_without_allocation_authority`
- `test_projection_semantics_blocks_allocation_as_recommendation_authority`

- [ ] **Step 5: Add W12.D corpus tests**

Add to `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`:

- `test_w12d_emits_s12_resource_economics_blocks_for_13_cases`
- `test_w12d_s12_voi_allocation_covers_at_least_three_sites`
- `test_w12d_s12_growth_entries_cite_envelope_delta`
- `test_w12d_s12_negative_controls_have_zero_false_clears`
- `test_w12d_s12_preserves_s2_shadow_only_outcome_effects`

Expected S12 summary assertions:

```python
summary = report["s12_resource_economics_summary"]
assert summary["case_count"] == 13
assert summary["voi_site_count"] >= 3
assert summary["typed_budget_count"] == 5
assert summary["override_rate_trend"] in {"improving", "flat"}
assert summary["reuse_rate_trend"] in {"improving", "flat"}
assert summary["growth_without_envelope_delta_count"] == 0
assert summary["held_out_status"] == "pending_s14"
assert all(v == 0 for v in summary["false_clear_counts"].values())
assert len(summary["per_case_resource_table"]) == 13
```

- [ ] **Step 6: Add manifest/readiness red tests**

Create
`tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py`
with:

- `test_layer2_s12_manifest_exists_and_open_count_drops_to_0`
- `test_layer2_s12_closes_envelope_growth_cell`
- `test_layer2_s12_required_artifacts_are_traceable_and_exported`
- `test_layer2_s12_floor_is_governed_and_growth_requires_envelope_delta`
- `test_layer2_s12_inventory_registration_exists`
- `test_layer2_s12_inventory_count_is_20_after_registration`
- `test_layer2_s12_b_side_does_not_import_resource_economics_producer`
- `test_layer2_s12_negative_controls_fail_closed`
- `test_layer2_s12_manifest_metrics_match_generated_corpus_summary`
- `test_layer2_s12_does_not_mark_s13_or_s14_or_production_authority`
- `test_layer2_s12_burn_down_complete_zero_open_cells`

- [ ] **Step 7: Run the red suite and commit**

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s12_resource_economics.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py \
  -q
```

Expected red: missing `layer2_resource_economics` contracts, missing
`Layer2S12ResourceEconomicsPostureInput`, absent `s12_resource_economics`
corpus block, and absent manifest. Commit only tests and fixtures:

```bash
git add tests/unit/runtime/quality/test_layer2_s12_resource_economics.py \
  tests/fixtures/layer2/s12 \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py
git commit -m "test: add layer2 s12 resource economics red tests" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 2: Contracts, Producer, Allocation Policy, And Anti-Gaming Firewalls

**Intent:** implement the strict runtime-quality S12 producer over existing VOI,
acquisition, delegation, Pareto, and ratchet substrates without building an
optimizer.

**Files:**

- Create: `src/polisyos/runtime/quality/design_axes/resource_economics.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`
- Test: `tests/unit/runtime/quality/test_layer2_s12_resource_economics.py`

- [ ] **Step 1: Add module constants and literals**

Add the constants and literals from the Contract Dictionary. `S12_FALSE_CLEAR_FIELDS`
is the false-clear source of truth, mirroring `S10_FALSE_CLEAR_FIELDS` /
`S11_FALSE_CLEAR_FIELDS`.

- [ ] **Step 2: Define strict models**

All public DTOs subclass `Layer2ReadinessModel` (`extra="forbid"`), carry
`schema_version`, stable `*_id`/`*_ref`, `rule_version_ref`, and an
`authority_boundary` where they cross workflow boundaries.

`ResourceAllocationPolicy` must carry:

- `policy_id`, `policy_ref`, `case_id`
- `explore_exploit_posture`, `explore_exploit_dial_ref` (S7 `DelegationContract`)
- `delegation_contract_ref`, `principal_ref`, `mission_ref`
- `voi_allocations` (list of per-site allocation rows; see Step 3)
- `voi_site_count`
- `typed_budget_rows` (one per `BudgetKind`, with budget ref and VOI estimate)
- `pareto_archive_ref` (allocation-policy tradeoffs; an S8 `ParetoArchive`),
  `ranking_mode` (reuse S8 `RankingMode`: `unranked_frontier_only` when no dial,
  `ranked_with_authorized_values` when the dial selects a policy),
  `selected_policy_ref`, `rejected_nondominated_policy_refs`
- `allocation_priority_rows` (slice/acquisition priorities driven by VOI)
- `disposition`, `limitation_refs`, `authority_boundary`, `may_not_use_for`,
  `rule_version_ref`

`EnvelopeGrowthLedger` must carry:

- `ledger_id`, `ledger_ref`, `case_id`
- `growth_entries` (each with: `entry_ref`, `demand_act_ref`,
  `certified_envelope_delta_ref` or `pending_envelope_delta_ref`,
  `growth_counting_disposition`, `reuse_evidence_refs`,
  `bespoke_flag_reason | None`, `a_completeness_delta_ref`,
  `b_capability_delta_ref`)
- `counted_mechanism_growth_count`, `flagged_bespoke_one_off_count`,
  `blocked_no_envelope_delta_count`
- `cluster_map_open_cell_count_before`, `cluster_map_open_cell_count_after`
- `authority_boundary`, `may_not_use_for`, `rule_version_ref`

`GrowthThermometerRecord` must carry (anti-gaming anchors per Implementation
Design #6):

- `thermometer_id`, `thermometer_ref`, `case_id`
- `override_rate`, `override_rate_trend`
- `override_decision_kinds` (the **instrumented** classes only:
  `final_choice`, `value_authorization`, `a_spec_gap`, `mandate_boundary`)
- `uninstrumented_override_dimensions` (e.g. `["regime", "decomposition"]` -
  recorded honestly, never faked into the rate)
- `required_question_count` (fixed denominator read from the
  `DecisionRightsMatrix`; the trend is `improving`/`flat` only if this is
  non-decreasing - blocks "lower the rate by asking fewer questions")
- `reuse_rate`, `reuse_rate_trend`
- `frozen_primitive_set_ref` (the `MinimalSeedManifest` primitive sets that anchor
  reuse), `reused_primitive_refs` (every entry must be a member of the frozen
  sets), `one_off_growth_refs` (constructs not composed from frozen primitives;
  count against reuse and are flagged bespoke)
- `held_out_status` (`pending_s14`), `held_out_battery_ref | None`
- `floor_id`, `floor_passed`, `threshold_ref`
- `authority_boundary`, `may_not_use_for`, `rule_version_ref`

`KnowledgeGovernanceThroughputLedger` must carry:

- `ledger_id`, `ledger_ref`, `case_id`
- `throughput_rows` (per knowledge-governance mode: automated proposal,
  human-reviewed, institution-owned, manual bespoke) with cost/latency refs
- `governance_mode_counts`, `manual_bespoke_ratio`
- `authority_boundary`, `may_not_use_for`, `rule_version_ref`

`ResourceEconomicsIntegrityReport` must carry:

- `report_id`, `case_count`
- `voi_site_count`, `typed_budget_count`
- `override_rate_trend`, `reuse_rate_trend`, `held_out_status`
- `counted_mechanism_growth_count`, `flagged_bespoke_one_off_count`,
  `growth_without_envelope_delta_count`
- `weakest_boundary_inheritance_count`
- `false_clear_counts` (keys must equal `set(S12_FALSE_CLEAR_FIELDS)`)
- `authority_boundary`, `may_not_use_for`, `rule_version_ref`

The integrity report must validate
`set(false_clear_counts) == set(S12_FALSE_CLEAR_FIELDS)`.

- [ ] **Step 3: Implement producer/verifier helpers**

- `allocate_value_of_information(...)` (see Implementation Design #1) **aggregates
  the `used_by_sites` / `budget_dimensions` of existing `ValueOfInformationEstimate`
  instances** - S2 refinement (`["layer2.s2.shadow_design_loop"]`), S3 acquisition
  (`["layer2_s3_substrate_acquisition"]`, via `acquisition_planner`'s `voi_report`),
  S7 attention (`voi_rank`/`attention_cost_rank`) - into the canonical site
  taxonomy. It returns per-site allocation rows over the shared (qualitative)
  currency and `voi_site_count = len(distinct used_by_sites)`. It must **not**
  synthesize a numeric VOI magnitude or an optimum, and must keep each site's VOI
  inside its own typed budget dimension (no cross-budget conversion ->
  `interchangeable_budget` firewall).
- `build_resource_allocation_policy(...)` (see Implementation Design #3) builds the
  allocation frontier as an **S8 `ParetoArchive`** (`nondominated_alternative_ids`
  = candidate policies, `objective_refs` = budget dimensions), and maps the S7
  explore/exploit dial onto S8 `RankingMode`: dial present ->
  `ranked_with_authorized_values` (dial is the value schedule), dial absent ->
  `unranked_frontier_only`. It reads the dial by ref (Architecture note), never
  self-sets it, and never collapses the frontier into a hidden scalar. It builds
  the typed-budget rows from `MinimalSeedManifest.budgets` + the S7 budget refs +
  `performance_budget` (compute).
- `build_envelope_growth_ledger(...)` (see Implementation Design #2) records growth
  entries only when a certified-envelope-delta **ref** resolves to a real
  `capability_ratchet.build_capability_reality_report(...)` + cluster-map open-count
  change; otherwise it records `blocked_no_envelope_delta`. It does **not** create
  the typed `CertifiedEnvelopeDelta` (that is S13's artifact) - it cites the delta
  ref the cell publishes. It flags bespoke one-off growth
  (`flagged_bespoke_one_off`) and excludes it from `counted_mechanism_growth_count`,
  and reads `cluster_map_open_cell_count_before/after` from the cluster map (S12's
  own `1 -> 0` closure is the anchor delta entry; per-case hypothetical growth uses
  `pending_envelope_delta_ref`).
- `build_growth_thermometers(...)` (see Implementation Design #6) computes
  override-rate from S7 `HumanDecisionRecord`s (`reject`/`revise_scope` on the
  instrumented classes) over a **fixed** `required_question_count` denominator
  read from the `DecisionRightsMatrix` (records `uninstrumented_override_dimensions`
  honestly), and reuse-rate against the **frozen** `MinimalSeedManifest` primitive
  sets (every `reused_primitive_ref` must be a member; non-frozen constructs are
  `one_off_growth_refs`). Trends are `improving`/`flat` only when the denominator
  is non-decreasing and the frozen set is unchanged. Sets
  `held_out_status = "pending_s14"`. It must not improve a rate by shrinking the
  denominator or relabeling a one-off as a primitive.
- `build_knowledge_governance_throughput_ledger(...)` records per-mode
  throughput rows.
- `verify_resource_authority_envelope(...)` enforces the anti-gaming/anti-learning
  firewalls (Step 4) and returns the disposition + issue codes.
- `summarize_resource_economics_integrity(...)` aggregates the corpus into a
  `ResourceEconomicsIntegrityReport`.
- `build_s12_resource_economics_posture(...)` returns the compact replayable
  mapping consumed by the corpus route and projected into S2, including
  `canonical_outcome_effect = "resource_allocation_only_not_production_authority"`.

- [ ] **Step 4: Implement anti-gaming/anti-learning firewalls**

Fail closed when:

- a growth entry has no certified-envelope-delta ref
  (`growth_without_envelope_delta`).
- a one-off construct/template is counted as mechanism growth
  (`bespoke_one_off_growth`).
- an allocation maximizes an internal metric while user demand or hard-corner
  evidence is unaddressed (`allocation_gaming_internal_metrics`).
- growth is claimed by lowering a floor (`floor_lowering_for_useful_design_rate`).
- B-capability growth outpaces A-completeness in the same envelope
  (`b_faster_than_a_growth`).
- the system sets its own mission, budgets, or value tradeoffs
  (`meta_regress_past_principal`).
- a budget kind is substituted directly for another (`interchangeable_budget`).

Each violation increments the matching `false_clear_counts` key only if a probe
were (incorrectly) cleared; correct behavior keeps the count at `0`.

- [ ] **Step 5: Export and run**

Add all S12 models, literals, constants, and helpers to
`src/polisyos/runtime/quality/__init__.py` `__all__`, ordered after the S11
block. Run:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s12_resource_economics.py -q
uv run ruff check src/polisyos/runtime/quality/design_axes/resource_economics.py \
  src/polisyos/runtime/quality/__init__.py \
  tests/unit/runtime/quality/test_layer2_s12_resource_economics.py
```

Expected: runtime S12 tests pass; ruff clean. Commit:

```bash
git add src/polisyos/runtime/quality/design_axes/resource_economics.py \
  src/polisyos/runtime/quality/__init__.py \
  tests/unit/runtime/quality/test_layer2_s12_resource_economics.py
git commit -m "feat: add layer2 s12 resource economics contracts" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 3: Wire S12 Posture Into PDC Context, Semantics, And Export

**Intent:** make PDC/projection consumers read injected S12 posture as
constraint/priority data without importing the runtime producer.

**Files:**

- Modify: `src/polisyos/pdc/_impl/layer2_design_search.py`
- Modify: `src/polisyos/pdc/__init__.py`
- Modify: `src/polisyos/runtime/quality/projection_semantics.py`
- Modify: `src/polisyos/runtime/quality/public_export.py`
- Test: `tests/unit/pdc/test_layer2_readiness_contracts.py`
- Test: `tests/unit/pdc/test_layer2_s2_design_search.py`
- Test: `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- Test: `tests/unit/runtime/quality/test_public_export.py`

- [ ] **Step 1: Add PDC posture contract**

Add `Layer2S12ResourceEconomicsPostureInput` next to the S10/S11 posture DTOs in
`src/polisyos/pdc/_impl/layer2_design_search.py`, with:

- `resource_allocation_policy_ref`
- `explore_exploit_posture`
- `explore_exploit_dial_ref`
- `delegation_contract_ref`
- `voi_allocation_refs`
- `voi_site_count`
- `typed_budget_refs`
- `pareto_archive_ref`
- `allocation_priority_rows`
- `envelope_growth_ledger_ref`
- `growth_thermometer_ref`
- `override_rate_trend`
- `reuse_rate_trend`
- `held_out_status`
- `knowledge_governance_throughput_ledger_ref`
- `residual_limitation_refs`
- `authority_boundary`
- `may_not_use_for`
- `rule_version_ref`

Export it from `src/polisyos/pdc/__init__.py`. Do not import the runtime
producer.

- [ ] **Step 2: Thread posture through S2 run state**

Add optional `resource_posture: Layer2S12ResourceEconomicsPostureInput | None`
to `Layer2S2DesignSearchRun` and `run_s2_shadow_design_loop(...)`, and thread it
through `_search_ledger`, `_design_record`, `_deterministic_replay_key`,
`_cluster_interfaces`, `_handoff_records`, and projection helpers. Add compact
`SearchLedger` fields with backward-compatible defaults:

- `resource_allocation_policy_refs`
- `envelope_growth_ledger_refs`
- `growth_thermometer_refs`
- `voi_allocation_refs`
- `explore_exploit_posture`
- `resource_authority_boundary`

Update `_constraint_store`, `persist_s2_design_record(...)` round-trip
expectations, and `SearchLedger.model_validate(...)` legacy-default tests. The
replay key must change only when resource posture changes and stay stable when
the same posture (or `None`) is replayed.

When S12 posture says allocation is `blocked` or a growth entry is flagged, S2
records a constraint-store row and keeps candidate ranking advisory/shadow; it
must not convert allocation priority into recommendation authority.

- [ ] **Step 3: Add projection fields**

EXPERT/MACHINE projections expose `explore_exploit_posture`, per-site VOI refs,
typed-budget refs, the Pareto-frontier ref, override/reuse trends, the
envelope-growth-ledger ref, and residual limitations. REVIEWER exposes
explore/exploit posture, trends, and allocation disposition. PUBLIC exposes a
high-level growth/limitation note only; it must not expose allocation as
recommendation or claim authority. Add
`assert_s2_public_projection_has_growth_limitation(...)` and call it for PUBLIC
when S12 posture is present.

- [ ] **Step 4: Bridge into projection semantics and public export**

In `projection_semantics.py`, add a narrow
`verify_s12_resource_projection_consumer_contract(...)` that reuses the existing
consumer-contract checks and adds S12 issue codes:

- `s12_allocation_as_recommendation_authority`
- `s12_growth_without_envelope_delta_surfaced_as_growth`
- `s12_explore_exploit_self_set`
- `s12_hidden_pareto_allocation_scalar`

In `public_export.py`, allow `explore_exploit_posture`, growth-limitation text,
and override/reuse trend status; deny production/recommendation language derived
from S12.

- [ ] **Step 5: Run and commit**

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py -q
uv run ruff check src/polisyos/pdc/__init__.py \
  src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py
```

Commit:

```bash
git add src/polisyos/pdc/__init__.py \
  src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py
git commit -m "feat: wire layer2 s12 resource posture into projections" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 4: Canonical Corpus Route Wiring - 13-Case S12 Coverage

**Intent:** every W12.D case carries an S12 resource-economics block while
preserving S3/S7/S8/S11 boundaries and S2 shadow-only outcomes.

**Files:**

- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`
- Create: `tests/fixtures/layer2/s12/s12_resource_economics_case_signals.json`
- Create: `tests/fixtures/layer2/s12/s12_resource_economics_expert_labels.json`
- Test: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`

- [ ] **Step 1: Add fixtures**

`s12_resource_economics_case_signals.json` covers all 13 case ids. Each case
includes per-site VOI input refs (acquisition/refinement/attention/oracle/
allocation), typed-budget refs for all five budget kinds, the S7
delegation-contract/dial ref, demand-act refs (S7 human acts), reuse-evidence
refs and one-off-growth refs, a certified-envelope-delta ref (or pending),
override-decision refs (S4/S5/S7/S8), and expected disposition/trend labels in
the separate expert-labels file. Producer-input fixtures must not contain the
gold trend/disposition labels.

Coverage must include: at least one counted mechanism-growth case, at least one
flagged bespoke-one-off case, at least one growth-without-delta block, at least
one exploit-in-envelope and one invest-in-growth posture, and the easy-corner
`ua-msme-affordable-loans-2022` real-demand bootstrap case.

- [ ] **Step 2: Add corpus route helpers**

Add `S12_CASE_SIGNALS_PATH`, `S12_EXPERT_LABELS_PATH`,
`S12_NEGATIVE_CONTROL_PROBE_PATHS`, `S12_MAY_NOT_USE_FOR`,
`_s12_resource_economics_case_block(...)`,
`_s12_resource_economics_summary(...)`, `_s12_negative_control_probe_results(...)`,
and `_s12_resource_posture_input(...)`. Route order:
`S4 -> S5 -> S6 -> S7 -> S8 -> S10 -> S11 -> S12 -> S2(+resource_posture) -> S9`.
Consume the already-built S3/S7/S8/S11 refs; do not rerun those producers.

Per-case `s12_resource_economics` block includes the schema version,
`explore_exploit_posture`, `voi_allocation_refs`, `voi_site_count`,
`typed_budget_refs`, `pareto_archive_ref`, `resource_allocation_policy_ref`,
`envelope_growth_ledger_ref`, `growth_thermometer_ref`, `override_rate_trend`,
`reuse_rate_trend`, `held_out_status`,
`knowledge_governance_throughput_ledger_ref`, growth counts,
`canonical_outcome_effect = "resource_allocation_only_not_production_authority"`,
`may_not_use_for`, and `matches_gold`.

Top-level `s12_resource_economics_summary` includes `case_count`,
`voi_site_count`, `typed_budget_count`, `override_rate_trend`,
`reuse_rate_trend`, `held_out_status`, growth counts,
`growth_without_envelope_delta_count`, flat + nested `false_clear_counts`, and
`per_case_resource_table`.

- [ ] **Step 3: Run and commit**

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
uv run ruff check tools/quality/validation/run_universal_outcome_corpus.py
for f in tests/fixtures/layer2/s12/*.json tests/fixtures/layer2/s12/negative_controls/*.json; do python3 -m json.tool "$f" >/dev/null || exit 1; done
git add tools/quality/validation/run_universal_outcome_corpus.py \
  tests/fixtures/layer2/s12 \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py
git commit -m "feat: classify layer2 s12 resource economics coverage" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 5: S12 Manifest, Readiness Validator, Cluster Closure (Burn-Down To 0), And Inventory

**Intent:** register S12, close the final open cell, take the open count to `0`,
and keep both validators green with an empty open-cell set.

**Files:**

- Create: `architecture/policy_design_case/layer2_s12_resource_economics_manifest.json`
- Modify: `architecture/policy_design_case/cluster_ownership_map.toml`
- Modify: `architecture/policy_design_case/layer2_artifact_traceability.toml`
- Modify: `architecture/policy_design_case/inventory.json`
- Modify: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- Test: `tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py`

- [ ] **Step 1: Create manifest**

`architecture/policy_design_case/layer2_s12_resource_economics_manifest.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s12_resource_economics_manifest.v1",
  "status": "active",
  "owner": "principal-governance",
  "slice": "S12",
  "depends_on": ["S3", "S7"],
  "cells_closed": ["DESIGNER_ITSELF.envelope_growth"],
  "expected_current_open_cell_count": 0,
  "remaining_open_cells": [],
  "burn_down_complete": true,
  "floor_id": "s12_growth_thermometers",
  "floor_metric": "reuse_rate_and_override_rate_trend",
  "required_artifacts": [
    "KnowledgeGovernanceThroughputLedger",
    "EnvelopeGrowthLedger",
    "ResourceAllocationPolicy",
    "GrowthThermometerRecord",
    "ResourceEconomicsIntegrityReport"
  ],
  "case_count": 13,
  "voi_site_count": 3,
  "typed_budget_count": 5,
  "override_rate_trend": "improving",
  "reuse_rate_trend": "improving",
  "held_out_status": "pending_s14",
  "growth_without_envelope_delta_count": 0,
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "authority_scope": [
    "value_of_information_allocation",
    "explore_exploit_posture",
    "envelope_growth_ledger",
    "growth_thermometers",
    "knowledge_governance_throughput",
    "allocation_priority_input"
  ],
  "may_not_use_for": [
    "production_claim_authority",
    "production_recommendation",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "preference_learning_authority",
    "mdp_bandit_optimizer_authority",
    "budget_interchangeability",
    "mission_or_value_self_authorization",
    "floor_relaxation",
    "s13_envelope_shrink",
    "s13_accountability_closure",
    "s14_universality"
  ]
}
```

Flat and nested S12 false-clear count fields must be present and all `0`. Copy
the live `voi_site_count`, trends, and growth counts from the Task 4 corpus
summary; the validator (Step 4 repo test) compares manifest metrics to the
generated `s12_resource_economics_summary`. Perfect trends are allowed as
fixture evidence but the semantic rule is "growth counted only against an
envelope delta," not "growth always succeeds."

- [ ] **Step 2: Close the cluster-map cell (open count 1 -> 0)**

In `architecture/policy_design_case/cluster_ownership_map.toml`:

- remove `[open_cell_closure.DESIGNER_ITSELF.envelope_growth]` (this empties the
  open-cell-closure set).
- update `[cell.DESIGNER_ITSELF.envelope_growth]`:
  - `owner_module = "src/polisyos/runtime/quality/design_axes/resource_economics.py"`
  - `ratchet_state = "implemented"`
  - `p01_chain = "implemented"`
  - `gap = "none_for_s12_resource_economics_scope"`
  - `action` text: S12 routes VOI allocation, growth thermometers, and the
    envelope-growth ledger; envelope shrink/bidirectional revision remains S13.
  - keep `firewall = "P13_governance_gravity"`, `publishes`, `consumes`, and
    `seed_files` unchanged.

After this edit the cluster validator must report
`open_or_incomplete_count == 0` and the readiness validator
`current_open_cell_count == 0`. Confirm both validators tolerate an empty
open-cell set (they compute counts by summation and validate the
`[open_cell_closure.*]` set equals the open-state cell set; both are empty, which
is valid). Do not add a placeholder open cell to keep the count non-zero.

- [ ] **Step 3: Traceability and inventory**

In `layer2_artifact_traceability.toml`: set `KnowledgeGovernanceThroughputLedger`
maturity to `implemented` and add S12 rows for `EnvelopeGrowthLedger`,
`ResourceAllocationPolicy`, `GrowthThermometerRecord`, and
`ResourceEconomicsIntegrityReport`, each with `slice = "S12"` and
`maturity = "implemented"`.

In `inventory.json`: add `layer2_s12_resource_economics_manifest` with `id`,
`path`, `kind`, `schema_version`, `owner = "principal-governance"`,
`status = "active"`, `capability_reality_label = "implemented"`,
`authority_scope`, `may_not_use_for`, `validator`, and `canonical_route`. The
governed Layer 2 inventory artifact count becomes `20` (use
`_inventory_layer2_artifact_count(...)`, not raw `len`).

- [ ] **Step 4: Extend readiness validator**

Add `DEFAULT_S12_RESOURCE_ECONOMICS_MANIFEST_PATH`, `S12_REQUIRED_ARTIFACTS`,
`S12_REQUIRED_AUTHORITY_SCOPE`, `S12_REQUIRED_DENY`, `S12_FALSE_CLEAR_FIELDS`,
`S12_INVENTORY_ID`; load `payloads["s12_resource_economics"]`; call
`_validate_s12_resource_economics(...)` after the S11 branch; add `s12_*` summary
fields. Validation must assert:

- `cells_closed == ["DESIGNER_ITSELF.envelope_growth"]`;
- `expected_current_open_cell_count == 0`;
- live `current_open_cells == set()` (burn-down complete) and the closed cell is
  not in `_open_cell_refs(...)`;
- governed Layer 2 inventory artifact count `20`;
- floor `s12_growth_thermometers` exists with revision rule
  `growth_counting_requires_envelope_delta`;
- `voi_site_count >= 3`; `typed_budget_count == 5`;
- override/reuse trends in `{improving, flat}`;
- `growth_without_envelope_delta_count == 0`; all S12 false-clears `0`;
- `held_out_status == "pending_s14"`;
- no S13/S14 or production cell is marked implemented; envelope shrink is not
  claimed.

Also update the S11 validator branch the way S11 updated S10: keep
`s11["expected_current_open_cell_count"] == 1` as the S11 manifest-local
contract while allowing live `current_open_cells == set()` and inventory `20`
once S12 is present.

- [ ] **Step 5: Add S12 repo-quality tests and run**

Fill in
`tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py`
(the names from Task 1 Step 6). Run:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py -q
```

Expected: both validators `status: pass`, `current_open_cell_count: 0`,
`open_or_incomplete_count: 0`, inventory `20`. Commit:

```bash
git add architecture/policy_design_case/layer2_s12_resource_economics_manifest.json \
  architecture/policy_design_case/cluster_ownership_map.toml \
  architecture/policy_design_case/layer2_artifact_traceability.toml \
  architecture/policy_design_case/inventory.json \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py
git commit -m "chore: close layer2 s12 envelope growth cell and complete burn-down" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 6: Repo-Quality Snapshots, Burn-Down Endgame, And Confirmation

**Intent:** propagate the open-count `1 -> 0` burn-down across every prior-slice
repo test, repair the cluster negative-controls for an empty open-cell set, and
confirm no future authority leaked. This is the largest snapshot task in the
sequence; enumerate every file rather than relying on reactive discovery.

- [ ] **Step 1: Update prior-slice live open-count assertions (`1 -> 0`)**

**Two different assertion forms exist in the tree today — grep before editing.**
S11 adopted the `>=` structural fix on the *prior-slice* tests, so s2-s9 assert
`current_open_cell_count >= 1` / `open_cell_count >= 1` (not `== 1`). That `>= 1`
form tolerates any non-zero burn-down state but **hard-fails at the `0`
endgame** (`0 >= 1` is False), which is exactly what S12 reaches. The readiness
test, the cluster test, and the S11 current-slice test still use exact `== 1`.
Change only the **live** assertions; never touch static manifest fields
(`sN_expected_current_open_cell_count`, manifest `expected_current_open_cell_count`),
which remain each slice's historical value.

- `test_policy_design_case_layer2_readiness.py` (exact form):
  - `summary["current_open_cell_count"] == 1 -> == 0`;
  - add `CELLS_CLOSED_THROUGH_S12 = sorted([*CELLS_CLOSED_THROUGH_S11,
    "DESIGNER_ITSELF.envelope_growth"])` and repoint the
    `cells_closed_since_s0 == CELLS_CLOSED_THROUGH_S11` and
    `assigned - current_open_cells == set(CELLS_CLOSED_THROUGH_S11)` assertions to
    the new constant (all 17 cells);
  - keep `open_cell_count_baseline == 17` and `assigned_open_cell_count == 17`.
- `test_policy_design_case_cluster_ownership_map.py` (exact form):
  - `open_or_incomplete_count == 1 -> == 0` and
    `open_cell_closure["open_cell_count"] == 1 -> == 0`.
- `test_policy_design_case_layer2_s11_predictive_knowledge.py` (exact form):
  - the live `summary["current_open_cell_count"] == 1 -> == 0`; keep the S11
    manifest static `expected_current_open_cell_count == 1` and
    `s11_expected_current_open_cell_count == 1` unchanged.
- `test_policy_design_case_layer2_s10_outcome_prediction.py` (named-set form):
  - `EXPECTED_LIVE_OPEN_CELLS` becomes the **empty set** `set()`, so
    `remaining_open_cells == EXPECTED_LIVE_OPEN_CELLS` and
    `current_open_cell_count == len(EXPECTED_LIVE_OPEN_CELLS)` both resolve to `0`;
    keep the S10 manifest static `expected_current_open_cell_count == 3`.
- `test_policy_design_case_layer2_s2_design_search.py`,
  `..._s3_substrate_acquisition.py`, `..._s4_epistemic_regime.py`,
  `..._s5_coupling_composition.py`, `..._s6_blind_spot_firewalls.py`,
  `..._s7_delegation.py`, `..._s8_value_choice.py`,
  `..._s9_projection_lowering.py` (`>= 1` form — these are the ones a `== 1`
  grep would miss): change each live `current_open_cell_count >= 1` /
  `open_cell_count >= 1` to `>= 0` (a per-slice test should not re-assert the
  global meter once burn-down completes; `>= 0` keeps it green and the readiness
  test remains the single exact-count source of truth). Keep each slice's static
  manifest expected-count field unchanged.

Discovery grep (run first so no live assertion is missed):

```bash
grep -rn "current_open_cell_count\|open_cell_count\|open_or_incomplete_count\|EXPECTED_LIVE_OPEN_CELLS" \
  tests/repo_quality/tools/test_policy_design_case_layer2_*.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  | grep -vE "expected_current_open_cell_count|open_cell_count_baseline|assigned_open_cell_count"
```

- [ ] **Step 2: Inventory `19 -> 20` (follow the established convention)**

Prior-slice repo tests already use `>= 18` inventory assertions (the
`>=`-for-prior convention S10/S11 adopted); those survive at `20`. Only two
exact `==` assertions exist today: `readiness:197 == 19` and
`s11:99 == 19`. Update only those: set the readiness inventory assertion to
`== 20`, change the S11 current-slice inventory `== 19` to `>= 19` (it is now a
prior slice), and let the new S12 test assert the exact `== 20`. Confirm with:

```bash
grep -rn "inventory_artifact_count" tests/repo_quality/tools/ | grep -E "==|>="
```

- [ ] **Step 3: Repair the cluster negative-controls for an empty open-cell set**

**Four** negative-controls (not three) select a remaining open cell via the
helper `_remaining_open_closure(payload)` (call sites at lines ~203, ~265, ~277,
~291; helper defined at ~364) and then mutate `open_cell_closure[cluster][axis]`.
After S12 there are **no** real open cells, so the helper has nothing to return
and all four strand. The cleanest fix is **one change at the helper**, not four
per-test rewrites:

- modify `_remaining_open_closure(payload)` so that when the payload has zero
  open cells it injects a **synthetic** open cell into the deep copy: add a fake
  `[cell.<CLUSTER>.<synthetic_axis>]` with an open ratchet state (e.g.
  `producer_missing`) and a matching `[open_cell_closure.<CLUSTER>.<synthetic_axis>]`
  entry whose closure-contract fields satisfy the validator's required-field
  shape, then return that `(cluster, axis, closure)`. All four callers
  (`test_cluster_ownership_validator_rejects_missing_open_cell_closure`,
  `..._rejects_closure_state_mismatch`, `..._rejects_closure_without_semantic_gap`,
  and the `gap`-mutation negative-control at line ~203) then keep working
  unchanged, because each operates on a deep copy.
- keep the positive test `test_cluster_ownership_map_is_governed_and_valid`
  asserting the **real** map has `open_or_incomplete_count == 0` and
  `open_cell_closure["open_cell_count"] == 0`.

This makes the negative-controls test the validator's cell-agnostic behavior
rather than the live burn-down state, and keeps them durable for S13/S14 (which
also run at `0` open cells). Verify the helper is the only edit:

```bash
grep -n "_remaining_open_closure" tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py
```

- [ ] **Step 4: Run the full burn-down gate**

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py \
  tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
git diff --check
```

Expected: all green; readiness/cluster `current_open_cell_count`/
`open_or_incomplete_count == 0`; inventory `20`; capability ratchet unchanged.
Commit:

```bash
git add tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py
git commit -m "chore: burn down layer2 open cells to zero after s12" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 7: Full S12 Verification Done When

- [ ] **Step 1: Run the full S12 + regression gate**

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s12_resource_economics.py -q
uv run pytest tests/unit/pdc/test_layer2_readiness_contracts.py tests/unit/pdc/test_layer2_s2_design_search.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py -q
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools architecture guardrails check
```

Expected:

```text
S12 unit + repo-quality tests pass.
S1..S11 regression tests pass.
W12.D route emits s4..s11 plus s12_resource_economics for all 13 cases.
Layer 2 readiness validator: status pass; open_cell_count/current_open_cell_count 0; envelope_growth closed; inventory 20.
Cluster ownership validator: status pass; open_or_incomplete 0.
Capability ratchet unchanged/green.
Runtime API contract pass.
Architecture guardrails pass.
```

Record the verified VOI site count, typed-budget count, override/reuse trends,
growth counts, held-out status, and any Done-When caveat under this task.

- [ ] **Step 2: Done When**

S12 is complete only when all statements below are true:

1. `KnowledgeGovernanceThroughputLedger`, `EnvelopeGrowthLedger`,
   `ResourceAllocationPolicy`, `GrowthThermometerRecord`, and
   `ResourceEconomicsIntegrityReport` are strict, replayable, and exported from
   `polisyos.runtime.quality`.
2. `Layer2S12ResourceEconomicsPostureInput` is strict and exported from
   `polisyos.pdc`; B-side PDC search consumes injected S12 posture only and does
   not import the S12 runtime producer.
3. S12 consumes the shared S0 `ValueOfInformationEstimate` currency across at
   least three of `{acquisition, refinement, attention, oracle, allocation}`,
   recorded per site, without inventing a second VOI vocabulary.
4. Typed budgets (compute, acquisition money, expert time, human attention,
   legal access) are compared but never treated as freely interchangeable.
5. The explore/exploit dial is read from the S7 `DelegationContract`; S12 does
   not self-set the mission, budgets, or value tradeoffs (meta-regress stops at
   the principal).
6. Allocation tradeoffs are presented as a Pareto frontier (reusing S8
   `ParetoArchive`), never collapsed into a hidden scalar optimum, and no
   MDP/bandit optimizer is implemented.
7. Every envelope-growth-ledger entry cites a certified-envelope-delta ref (or
   explicit pending-delta ref); growth-without-delta is blocked and counted `0`.
8. Bespoke one-off growth is flagged and excluded from mechanism-growth counts;
   allocation gaming of internal metrics is blocked; growth claimed by lowering a
   floor is blocked; B growth outpacing A completeness in the same envelope is
   blocked.
9. Bootstrap thermometers record override-rate (down/flat) and reuse-rate
   (up/flat) trends together, and `held_out_status == "pending_s14"` (the
   held-out battery is not executed or claimed).
10. EXPERT/MACHINE projections surface explore/exploit posture, per-site VOI,
    typed budgets, the Pareto frontier, trends, and the growth ledger; REVIEWER
    surfaces posture/trends/disposition; PUBLIC surfaces only a growth/limitation
    note with no allocation/recommendation authority.
11. All 13 corpus cases contain S12 blocks; negative-control false-clear counts
    are zero; the manifest metrics match the generated corpus summary.
12. Production-posture outcomes are unchanged by S12; S2 `canonical_outcome_effect`
    remains shadow-only; S12 affects governed allocation/priority only.
13. `reuse_rate_and_override_rate_trend` floor is recorded from the governed floor
    table; growth counting requires an envelope delta; no floor is changed.
14. `DESIGNER_ITSELF.envelope_growth` is `implemented`; the cluster-map open cell
    count is `0` (burn-down complete); both validators pass with an empty
    open-cell set; the cluster negative-controls pass via synthetic open cells.
15. Governed Layer 2 inventory artifact count is `20`; the S11 repo test
    distinguishes its manifest-local open count `1` from the post-S12 live open
    count `0`.
16. No S13 envelope shrink/post-deploy accountability, S14 universality,
    production authority, preference learning, or precise optimizer cell is
    marked implemented.

## Commit Guidance

Use one logical commit per task:

```text
test: add layer2 s12 resource economics red tests
feat: add layer2 s12 resource economics contracts
feat: wire layer2 s12 resource posture into projections
feat: classify layer2 s12 resource economics coverage
chore: close layer2 s12 envelope growth cell and complete burn-down
chore: burn down layer2 open cells to zero after s12
```

End commit messages with the repo's standard co-author trailer:

```text
Co-authored-by: Cursor <cursoragent@cursor.com>
```

Never use `git add .` for this plan. If `git status --short` shows unrelated
user changes, stage only the S12 paths listed in the relevant task or use
`git add -p`. Do not mark any S13 post-deploy accountability / envelope shrink,
S14 universality, production, preference-learning, or optimizer cell as
implemented. S12 advances reflexive resource economics and completes the open
cell burn-down only.
