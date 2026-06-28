---
title: PolicyOS Layer 2 S14 Evaluation Redesign And Universality Assurance Battery Implementation Plan
status: active
owner: governance-board
created: 2026-06-03
last_verified: null
stability: draft
revision_note: Drafted after S13 verification, tightened against the roadmap S14 closure contract plus D4 target architecture, and calibrated against existing S12/S13 code seams.
slice: S14
slice_label: evaluation_redesign_universality_assurance_battery
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
floor_governance: ../../../../architecture/policy_design_case/layer2_floor_governance.toml
artifact_traceability: ../../../../architecture/policy_design_case/layer2_artifact_traceability.toml
corpus_partition: ../../../../architecture/policy_design_case/layer2_corpus_partition.json
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on:
  - S0
  - S1
  - S2
  - S3
  - S4
  - S5
  - S6
  - S7
  - S8
  - S9
  - S10
  - S11
  - S12
  - S13
cells_closed: []
layer_cells_advanced:
  - DESIGNER_ITSELF.evaluation_corpus
expected_current_open_cell_count: 0
floor_id: s14_universality
floor_metric: per_axis_posture_thresholds_and_breadth_floor
sealed_battery_path: tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery
---

# PolicyOS Layer 2 S14 Evaluation Redesign And Universality Assurance Battery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the only gate that lets PolicyOS externally claim any form of
"universal" designer capability, with a sealed held-out battery, per-axis
scorecard, skeptic defeaters, and projection/export enforcement.

**Architecture:** S14 is an evaluation and claim-authority gate, not another
design-power slice. It advances the already implemented
`DESIGNER_ITSELF.evaluation_corpus` layer by adding a sealed-battery producer,
strict assurance artifacts, projection/public consumers, and readiness
validation. Regular development routes may emit S14 dev-shadow posture, but only
the explicit S14 sealed-battery runner may read the hidden battery path.

**Tech Stack:** Python 3.14, Pydantic strict models, existing `polisyos.corpus`
loader split controls, runtime-quality projection/public export helpers,
`tools/quality/validation` repo-quality runners, pytest, ruff, TOML/JSON
governance artifacts.

Read this whole file before editing code. S14 is not a marketing badge. It is a
falsifiable, replayable definition of what "universal" means for this Layer 2
designer, and it blocks every universal self-description unless a sealed
battery, per-axis scorecard, declared envelope, and skeptic-defeater assurance
case survive.

S14 does not close a new open cell. It advances the existing
`DESIGNER_ITSELF.evaluation_corpus` layer and leaves `current_open_cell_count`
at `0`. It does not grant production, rollout, recommendation, approval,
publication, claim, scorecard, preference-learning, or automated value-learning
authority.

This plan is intentionally a task plan, not a roadmap rewrite. The roadmap owns
strategy, sequencing, doctrine, and slice closure contracts. This file unfolds
the S14 closure contract into exact contracts, files, wiring, tests, commands,
expected failures, and repository-state deltas.

## S14 Closure Contract

- Slice: `S14 | Evaluation redesign + universality assurance battery`.
- Cell advanced: `DESIGNER_ITSELF.evaluation_corpus`.
- Layer: `universality battery`.
- Producer: D4 corpus/breadth/oracle coverage builder, sealed-battery runner,
  per-axis scorecard builder, mechanism generality evaluator, skeptic-defeater
  evaluator, grounded-authority coverage evaluator, evaluation-status composer,
  baseline comparison evaluator, and universality-claim gate.
- Persisted artifacts: `SealedUniversalityBatteryRun`,
  `UniversalityAxisScorecard`, `MechanismGeneralityReport`,
  `SkepticDefeaterRecord`, `UniversalityClaimAssuranceCase`,
  `UniversalityClaimGateRecord`.
- Bridge and consumer: D4 supporting records, scorecard, grounded-authority
  coverage, baseline comparison, status composition, and assurance case gate
  every universal self-description through S9 faithfulness, projection
  semantics, public export, readiness validation, and inventory.
- Surface: per-axis scorecard, declared operation envelope, D4 breadth/oracle
  limitations, grounded-authority refs, held-out integrity status, baseline
  comparison, and skeptic-defeater state in PUBLIC, EXPERT, and MACHINE
  surfaces.
- Semantic test: held-out cases demonstrate mechanism generality with sublinear
  marginal bespoke cost, calibrated boundary, grounded authority inside the
  declared envelope, D4 breadth/oracle discipline, status composition, and all
  six architecture-defined skeptic attacks passing.
- Negative controls: a bare universal claim without envelope plus battery is
  rejected; development code touching the sealed battery fails; an aggregate
  "universal score" is blocked; untested axis combinations default
  out-of-envelope; sealed gold labels cannot leak into dev signals or public
  export.
- Firewalls: universality-claim firewall, held-out integrity firewall, freeze
  hash replay, D4 breadth-floor firewall, expert-oracle bootstrap firewall, S9
  faithfulness reuse, grounded-authority coverage, no aggregate universal
  number, no-production-authority boundary, no sealed-battery
  training/development access, and no gold-label leakage.
- Floor: `s14_universality` with metric
  `per_axis_posture_thresholds_and_breadth_floor`.

## Scope Boundaries

S14 may say whether a scoped universal claim is currently allowed, limited, or
blocked. It may declare the envelope in which the universal claim is supported,
which axes remain out-of-envelope, which D4 breadth dimensions are covered,
which oracle layers are only seed authority, which hard corners passed, which
skeptic defeaters passed, and which grounded-authority/scorecard refs support
the claim.

S14 must not claim an aggregate universal number. It must not turn held-out
battery results into production authority, policy recommendation authority,
claim evidence, approval, publication, rollout, or scorecard authority. It must
not expose hidden cases, sealed answer keys, reviewer-private notes, or gold
labels through dev fixtures, projections, or public export.

An untested axis combination is out-of-envelope by default. A scoped statement
such as "universal over the declared envelope" may pass only with S14 assurance
refs, visible limitations, D4 breadth-floor evidence, grounded-authority refs,
and a projection-only authority role.

## Pattern Pass

| Pattern | S14 risk | Closure move |
| --- | --- | --- |
| `P01` contract-only capability | A manifest or scorecard could exist without a runner, consumer, or surface. | Add strict contracts, sealed-battery producer, persisted manifest, projection/export consumers, repo-quality tests, and readiness validation. |
| `P02` thin orchestration | Battery results could coexist with projections while never gating claims. | Wire S14 into S9 faithfulness positive refs, projection semantics, public export, W12D dev-shadow route, sealed runner, and readiness validator. |
| `P03` hidden internal richness | The battery could pass internally while PUBLIC/EXPERT/MACHINE cannot inspect the envelope. | Surface per-axis posture, hard corners, skeptic defeaters, sealed integrity, and limitation refs without leaking hidden content. |
| `P04` status lattice gap | `universal`, `limited_universal`, `out_of_envelope`, `weak_gold`, `shadow_candidate_pool`, `held_out_universality_case`, `bespoke_growth_detected`, `envelope_expanded`, and `envelope_shrunk` could become a parallel authority lattice. | Compose S14-local dispositions through the existing S1/closeout status lattice (`case_lifecycle.py`, `approval.py`, and scorecard closeout semantics) and add mixed-status composition records proving seed/status labels block, limit, or project claims without minting a new authority tier. |
| `P05` authority boundary leak | "Universal" could be confused with production or recommendation authority. | Add `authoritative_for` only for universality-claim gating and explicit `may_not_use_for` denial of production, recommendation, claim, approval, publication, rollout, and scorecard authority. |
| `P07` rule replay gap | Held-out results could be unreplayable after fixture or threshold changes. | Carry battery id, partition ref, freeze hash, runner rule version, fixture manifest digest, and threshold config refs. |
| `P08` time-role conflation | Battery freeze time, run time, threshold revision time, and claim publication time could blur. | Model freeze, access, run, scoring, assurance, and projection timestamps separately. |
| `P10` semantic adequacy gap | Tests could prove only field presence. | Start red with held-out mechanism-generality, exact six skeptic-attack, D4 breadth/oracle, grounded-authority, mixed-status, baseline-comparison, and negative-control semantic tests. |
| `P12` producer handshake gap | The dev corpus route could emit S14 summary fields without a typed producer. | Add a dedicated S14 sealed-battery runner and make W12D dev blocks explicitly `sealed_battery_not_accessed_in_dev`. |
| `P13` governance gravity | S14 could become a giant benchmark platform or a parallel CAE/scorecard/growth engine. | Reuse S0 corpus partition, `polisyos.corpus` split controls, W12D route, S9 faithfulness, `assurance_case.py`, `capability_ratchet.py`, S12 growth thermometers/ledgers, S13 envelope revisions, projection/public export, readiness validator, and manifest-nested D4 coverage records; do not build a new corpus or assurance framework. |
| `P15` LLM speculation laundering | LLM self-description could become universal authority. | Require deterministic S14 assurance refs; LLM/candidate language remains blocked or projection-only until the S14 gate passes. |
| `P16` through `P26` universal-axis laundering | A "universal" claim could hide regime, coupling, measurability, aggregation, value, capacity, mandate, stakes, strategic-response, search-control, responsibility, or grounded-authority gaps. | Score every required cluster axis, hard-corner cases, exact six architecture-defined skeptic attacks, and grounded-authority refs; default untested combinations out-of-envelope. |

Capability label transition:

- Starting label: `surface_missing`, `verification_missing`,
  `semantic_test_missing` for the S14 universality battery layer.
- Target label: complete S14 capability chain with `cells_closed=[]`,
  `layer_cells_advanced=["DESIGNER_ITSELF.evaluation_corpus"]`, inventory count
  `22`, and open-cell count still `0`.

## Code-Grounded Reality Check

Existing substrates to reuse:

- `architecture/policy_design_case/layer2_corpus_partition.json` already defines
  the sealed battery path, `access="ci_gate_only"`, owner
  `governance-board`, and a freeze hash. S14 must rotate the freeze hash after
  creating the sealed pack; it must not move the path or remove the integrity
  rule.
- `src/polisyos/corpus/_impl/loaders.py` already enforces
  `UniversalCorpusSplit.HIDDEN` opt-in through `HiddenFixtureAccessError`. S14
  must reuse this split/access pattern instead of inventing another hidden
  loader.
- The same loader also allows `load_universal_corpus_fixtures(split=None)` to
  load all fixtures with `include_hidden=True` for internal validators. That is
  acceptable for the older universal corpus, but it is a footgun for S14 sealed
  battery work. W12D and dev-shadow S14 code must not use the generic all-loader
  to reach sealed fixtures; the sealed battery runner must read only the
  partition-configured sealed path after an explicit allow flag.
- `tests/unit/corpus/test_loaders.py` already proves hidden fixture access
  requires explicit opt-in for universal-corpus fixtures. S14 should add
  sealed-battery tests beside the S14 runner, not weaken the existing loader
  tests.
- `tools/quality/validation/run_universal_outcome_corpus.py` already emits
  S1-S13 blocks over the 13 canonical cases. S14 should add a dev-shadow block
  that does not read the sealed battery and a separate sealed runner that does.
- `tools/quality/validation/run_universal_outcome_corpus.py` is already a large
  route file. Add S14 as a sibling helper cluster near S12/S13, keep W12D S14
  payloads compact, and avoid broad route refactors while S14 is being added.
- `src/polisyos/runtime/quality/projection_semantics.py` already carries S9-S13
  consumer verifiers and blocks `s14_universality` as a future authority. S14
  should add a sibling verifier that allows scoped universal claims only when
  S14 assurance refs exist. Preserve the existing `s14_universality` deny
  tokens in the four pre-S14 consumer deny lists
  (`_S11_REQUIRED_MAY_NOT_USE_FOR`, `_S12_REQUIRED_MAY_NOT_USE_FOR`,
  `_S13_REQUIRED_MAY_NOT_USE_FOR`, and `_S13_FORBIDDEN_AUTHORITY_USES`);
  the relaxation belongs only in the new S14 verifier, not by deleting those
  four guards.
- `src/polisyos/runtime/quality/projection_semantics.py` and
  `src/polisyos/runtime/quality/public_export.py` are also large shared
  surfaces. S14 should project refs, statuses, limitation text, and redacted
  scorecard summaries; it must not duplicate full supporting-record bodies or
  hidden case rows into these files.
- `src/polisyos/runtime/quality/public_export.py` already enriches public export
  with S9-S13 projection hooks and redacts hidden benchmark material. S14 must
  add a sibling hook and strengthen redaction for sealed battery material.
- `src/polisyos/pdc/_impl/layer2_readiness.py` already provides
  `Layer2ReadinessModel` and `AuthorityBoundary`, and S12/S13 contracts use
  that readiness-model pattern. S14 public DTOs should inherit the same strict,
  frozen base and reuse the same authority-boundary shape instead of creating a
  parallel Pydantic base or authority DTO.
- `docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md`
  names `assurance_case.py`, the D4 corpus, capability ratchet, and cluster map
  as the existing substrate for the universality assurance/test battery. S14
  must treat these as mandatory reuse targets, not optional inspiration.
- `src/polisyos/runtime/quality/assurance_case.py` already exports
  `build_assurance_case_for_scorecard`, which produces a claim/subclaims/
  argument/evidence/defeaters view, separates blockers from warnings, computes
  `claim_status`, `non_overridable_blockers`, and `confidence_limits`, and
  supports the "pass only without blocking defeaters" gate. S14 should extend
  this module by adding a sibling `build_universality_assurance_case` builder
  that reuses its `_blockers`, `_warnings`, `_subclaims`, `_evidence`,
  `_claim_status`, and `_confidence_limits` path while leaving
  `build_assurance_case_for_scorecard` untouched. Only use a
  backwards-compatible `claim_spec` generalization if the sibling builder cannot
  satisfy the tests, and keep `tests/unit/runtime/quality/test_assurance_case.py`
  green as the closeout-regression anchor. Do not implement a parallel SACM/CAE
  engine in `layer2_universality_assurance.py`.
- `src/polisyos/runtime/quality/capability_ratchet.py` already exports
  `build_capability_reality_report`, whose returned `capability_claims` rows
  are the existing report surface for cluster-map capability reality. S14
  `UniversalityAxisScorecard` must derive its 27 axis rows from this report
  plus cluster-map cell refs, adding only S14 posture, hard-corner refs, and
  battery status.
- `src/polisyos/runtime/quality/design_axes/resource_economics.py` already exports
  `GrowthThermometerRecord`, `EnvelopeGrowthLedger`,
  `build_growth_thermometers`, and `build_envelope_growth_ledger`.
  `GrowthThermometerRecord` carries `reuse_rate`, `reuse_rate_trend`,
  `frozen_primitive_set_ref`, `reused_primitive_refs`, `one_off_growth_refs`,
  and `held_out_status == "pending_s14"` while rejecting a S12
  `held_out_battery_ref`. S14 must materialize that pending S12 hook through
  S14 refs, not mutate S12 thermometers into battery authority.
- `src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py` already
  exports `EnvelopeRevision`, `CertifiedEnvelopeDelta`,
  `build_envelope_revision`, and `build_certified_envelope_delta`.
  `EnvelopeRevisionDynamicsRecord` must aggregate S12 expansion evidence
  (`EnvelopeGrowthLedger`) and S13 shrink/split evidence (`EnvelopeRevision`
  and `CertifiedEnvelopeDelta`) to defeat "frozen once", instead of tracking
  only S13 shrink records.
- Existing closeout/status composition lives in `case_lifecycle.py`,
  `approval.py`, scorecard closeout semantics, and the source-truth lattice
  loader. S14 D4.5 labels are new local evaluation labels, but
  `EvaluationStatusCompositionRecord` must map them into the existing
  block/limit/review/projection semantics rather than creating another status
  lattice.
- `polisyos.corpus` already uses `redacted_source_hash` with the `sha256:<hex>`
  convention in `loaders.py` and `annotations.py`. The S14 sealed battery
  freeze hash is genuinely new, but it must follow that existing digest string
  convention.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`
  already has a negative test for
  `s9_universal_self_claim_without_s14_refs`. S14 must keep that negative test
  and add a positive path only when the S14 gate record passes.
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py` already
  uses a module-scoped W12D report fixture. S14 W12D tests should add compact
  assertions against that report rather than launching a second full W12D run.
- `architecture/policy_design_case/layer2_floor_governance.toml` already
  contains `s14_universality`.
- `architecture/policy_design_case/cluster_ownership_map.toml` already assigns
  `src/polisyos/corpus` to `DESIGNER_ITSELF.evaluation_corpus` with
  `ratchet_state="implemented"`. S14 advances the layer; it does not reopen or
  reassign the cell.
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
  currently loads through S13, keeps `S14` in future-slice guards, and expects
  inventory count `21`. Task 5 must add S14 constants, loader, summary,
  validator, traceability checks, and inventory count `22`.
- `src/polisyos/runtime/quality/design_axes/resource_economics.py` and the S12
  manifest currently use `held_out_status == "pending_s14"`. S14 must convert
  this into an S14 assurance reference in S14 outputs without mutating S12
  growth entries into battery authority.

Weak or expensive seams:

- Do not import the S14 runtime producer into `src/polisyos/pdc/_impl/layer2_design_search.py`.
  S14 is a claim gate, not a search constraint. If S14 refs need to be
  projected, pass them through projection payloads and W12D report blocks.
- Do not make the default W12D run read
  `tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery`.
  A dev run that accesses this path is a test failure.
- Do not replace S9 faithfulness verification. S14 should provide refs that let
  S9 allow a scoped universal claim; S9 still blocks self-description claims
  when refs are absent.
- Do not encode the battery as public fixture JSON in
  `tests/fixtures/universal-corpus`. The sealed pack has its own hidden path
  governed by S0 corpus partition.

Overbuild guard:

- S14 should extend the existing runtime-quality, corpus, projection, export,
  W12D, and readiness seams. Do not introduce a separate benchmark platform,
  database, dashboard, corpus DSL, search engine, or production promotion
  system.
- S14 must not build a parallel assurance-case, defeater, per-axis reality, or
  envelope-growth/revision engine. New S14 code wraps and gates existing
  substrate outputs, then adds sealed-battery evidence and universality-specific
  authority boundaries.

Complexity budget:

- S14 is materially larger than S13 because it adds seven D4/supporting records
  plus the sealed runner. Treat Task 2, Task 4, and Task 5 as the heavy work;
  do not hide that cost behind "similar to S13".
- Keep the new runtime capability in one S14 module for the S14 DTOs and gates,
  but put only the minimal sibling universality assurance builder in
  `assurance_case.py` if needed. Avoid changing
  `build_assurance_case_for_scorecard`; if a fallback generalization is chosen,
  prove default closeout behavior is unchanged. Use small private adapters and
  the existing `Layer2ReadinessModel` base rather than creating a new package or
  framework.
- Do not duplicate CAE/GSN/SACM structures, capability-ratchet scoring,
  S12 reuse-rate logic, S12 expansion ledgers, S13 shrink/split records, or
  closeout status lattice logic. The S14 surface should point to those refs and
  add only S14 posture, held-out measurements, sealed integrity, and claim-gate
  semantics.
- Keep the W12D dev route as `dev_shadow_no_hidden_access`: it may emit
  pending/ref/status summaries and negative-control results, but it must not
  mark the sealed universal claim gate as passed.
- Keep public export compact: public bundles carry declared-envelope text,
  limitation refs, S14 gate refs, status summaries, and redacted scorecard refs,
  not hidden fixtures, gold labels, private oracle notes, or full battery case
  payloads.

## Reuse Map

| Existing substrate | S14 typed wrapper / gate |
| --- | --- |
| CAE helper path in `src/polisyos/runtime/quality/assurance_case.py`, exposed for S14 through sibling `build_universality_assurance_case` | `UniversalityClaimAssuranceCase`; `SkepticDefeaterRecord` is a typed projection of CAE defeaters for the exact six skeptic attacks. |
| Existing `build_assurance_case_for_scorecard` closeout behavior in `assurance_case.py` | Regression anchor that must stay unchanged while S14 adds the sibling universality builder. |
| CAE blocker/warning/no-blocker gate in `assurance_case.py` | Universality claim passes only when all six skeptic defeaters are non-blocking and the S14 gate has no authority false clears. |
| `capability_ratchet.build_capability_reality_report` in `src/polisyos/runtime/quality/capability_ratchet.py` | `UniversalityAxisScorecard` with 27 rows derived from existing capability reality plus S14 posture, hard-corner refs, and battery status. |
| S12 `GrowthThermometerRecord` (`reuse_rate`, `reuse_rate_trend`, `reused_primitive_refs`, `one_off_growth_refs`, `frozen_primitive_set_ref`, `held_out_status="pending_s14"`) | `MechanismGeneralityReport`, adding only S14 held-out marginal-bespoke-cost measurement and materializing the pending S12 held-out hook. |
| S12 `EnvelopeGrowthLedger` plus S13 `EnvelopeRevision` and `CertifiedEnvelopeDelta` | `EnvelopeRevisionDynamicsRecord`, proving both reusable expansion and shrink/split on disconfirmation for the `frozen_once_defeater`. |
| Existing S1/closeout status lattice (`case_lifecycle.py`, `approval.py`, scorecard/source-truth lattice semantics) | `EvaluationStatusCompositionRecord`, mapping D4.5 labels to block/limit/seed-only/projection-only effects without a parallel authority tier. |
| `layer2_corpus_partition.json` | Source of truth for sealed path, owner, access mode, and freeze hash. |
| `polisyos.corpus` hidden split access controls | Access-control precedent for hidden fixtures and opt-in loading. |
| Corpus `redacted_source_hash` `sha256:<hex>` convention | New `compute_sealed_battery_freeze_hash`, using the existing digest string convention. |
| W12D universal outcome corpus runner | Dev-shadow route over the 13 canonical cases without hidden access. |
| S9 projection faithfulness verifier | Consumer-side firewall for universal self-description claims. |
| Projection semantics S10-S13 verifier pattern | S14 consumer contract for scoped universal claims and per-axis envelope surfaces. |
| Public export redaction and authority-boundary helpers | Public S14 envelope projection without hidden battery or gold-label leakage. |
| Cluster ownership map `DESIGNER_ITSELF.evaluation_corpus` | Layer advanced by S14 without reopening a cell. |
| Floor governance `s14_universality` | Governed floor for per-axis posture thresholds and breadth. |

## Implementation Design

### D4 Corpus, Oracle, And Breadth Floor

S14 must unfold the D4 evaluation redesign, not only add a hidden fixture pack.
It does this through manifest-nested supporting records that are produced by the
S14 runner and projected by S14 surfaces:

- `D4CorpusTrackCoverage`
- `ExpertOracleBootstrapRecord`
- `UniversalityBreadthFloorConfig`
- `UniversalityBaselineComparison`
- `GroundedAuthorityCoverageRecord`
- `EvaluationStatusCompositionRecord`
- `EnvelopeRevisionDynamicsRecord`

`D4CorpusTrackCoverage` must cover the 19 D4.1 tracks from the architecture
document:

1. `grounding`
2. `construct_demand`
3. `acquisition_loop`
4. `epistemic_regime`
5. `coupling_modularity`
6. `axis_declaration`
7. `cluster_ownership`
8. `scale_composition`
9. `design_quality`
10. `search_control`
11. `delegation`
12. `projection_lowering`
13. `bootstrap_resource`
14. `system_dynamics_backtest`
15. `post_deploy_accountability`
16. `prediction_backtest`
17. `adversarial`
18. `odd_abstention`
19. `universality_battery`

Each track row carries `track_id`, `minimum_label_refs`, `covered_case_refs`,
`coverage_status`, `limitation_refs`, and `authority_boundary`. Missing D4
tracks limit or block the universal claim; they cannot be hidden behind a
passing sealed battery.

`ExpertOracleBootstrapRecord` must declare exactly four oracle layers:

- `weak_gold`
- `expert_gold_seed`
- `causal_support_seed`
- `shadow_candidate_pool`

`weak_gold` may seed candidate designs, baselines, constraints, and observed
outcomes, but it cannot define promotion floors alone. `expert_gold_seed` must
carry conflict declarations plus inter-rater reliability or a disagreement
taxonomy. `causal_support_seed` may support backtestable outcome estimates only
inside its transport limits. `shadow_candidate_pool` may stress-test recall,
diversity, and pruning, but it cannot become the oracle.

`UniversalityBreadthFloorConfig` must name the first governed breadth target for
the declared S14 posture. At minimum it carries:

- domain target and covered/excluded domains;
- jurisdiction or governance-context target, including non-OECD or crisis/low
  data coverage;
- scale-class target from leaf intervention through transnational or
  integration program;
- epistemic-regime, coupling-regime, lifecycle, state-capacity, authority
  posture, and instrument-family targets;
- system-dynamics or feedback-sensitive case coverage;
- owner, revision rule, threshold refs, and floor-setting method.

If the governed fixture set does not satisfy the breadth target for a broad
external universal claim, the S14 gate must emit `universal_claim_limited` or
`universal_claim_blocked`; it may not silently lower the target.

`GroundedAuthorityCoverageRecord` proves that in-envelope cases pass the A-side
requirements named by the architecture: A-firewalls, claim/evidence binding,
value-choice provenance, mandate and legitimacy refs, capacity checks,
regime/coupling refs, and projection faithfulness. S14 can cite these refs; it
cannot manufacture them.

`UniversalityBaselineComparison` supports the "Why call it first?" skeptic
attack. It compares the S14 mechanism/boundary/grounded-authority triad against
bespoke tools, raw LLM baselines, and expert panels through fixture references
or governed benchmark records. Missing baseline comparison limits or blocks the
external universal claim.

`EvaluationStatusCompositionRecord` composes D4 labels such as `weak_gold`,
`expert_gold_seed`, `shadow_candidate_pool`, `outside_certified_envelope`,
`a_spec_gaming_probe`, `substrate_gap`, `search_incomplete`,
`projection_only`, `held_out_universality_case`, `bespoke_growth_detected`,
`envelope_expanded`, `envelope_shrunk`, and `historical_prior_only` with the
S14 gate. The record must prove, for example, that `weak_gold` and
`shadow_candidate_pool` remain seed authority, `bespoke_growth_detected` blocks
mechanism-generality claims, and `envelope_shrunk` is an honest result rather
than a readiness failure. The composition target is the existing S1/closeout
status lattice: D4.5 labels map to `blocks_claim`, `limits_claim`,
`seed_only`, `projection_only`, or `advisory_only` effects and then to existing
block/limit/review/public-revalidation semantics. S14 must not define a new
promotion or authority tier.

### Sealed Battery Integrity

Create a dedicated runner:

`tools/quality/validation/run_layer2_s14_universality_battery.py`

It is the only code path allowed to read the sealed battery path. It requires an
explicit `--allow-sealed-battery` flag or `allow_sealed_battery=True` argument.
Without explicit access it returns a typed failure and never traverses the
hidden path.

The runner computes a deterministic freeze hash over the sealed battery
manifest and all sealed case files:

- sorted relative paths.
- raw bytes for each JSON fixture.
- normalized JSON metadata for battery id, owner, fixture schema version, and
  hard-corner ids.
- `sha256:<hex>` output, matching the existing corpus `redacted_source_hash`
  digest convention.

The computed hash must match
`architecture/policy_design_case/layer2_corpus_partition.json` under
`sealed_universality_battery.freeze_hash`. A mismatch fails closed with
`freeze_hash_mismatch`.

Regular W12D dev runs must emit:

- `sealed_battery_access_attempted == false`.
- `sealed_battery_status == "not_accessed_in_dev"`.
- `sealed_battery_ref` only as a redacted partition ref, never as loaded case
  contents.

### Per-Axis Scorecard

S14 scores every cell in the cluster ownership map, not only cases that happen
to be convenient. The initial scorecard uses 27 axis rows, one per
`CLUSTER.axis` cell. It must be derived from
`capability_ratchet.build_capability_reality_report(...)` plus cluster-map
cell refs; S14 adds posture, hard-corner, and battery fields rather than
reimplementing capability reality scoring.

Each `UniversalityAxisScoreRow` carries:

- `axis_ref`
- `declared_posture`: `in_envelope`, `limited`, `out_of_envelope`, or
  `not_tested`
- `battery_status`: `pass`, `limited`, `blocked`, or `not_tested`
- `threshold_ref`
- `floor_passed`
- `hard_corner_case_refs`
- `mechanism_refs`
- `limitation_refs`
- `failure_refs`
- `evidence_refs`

Untested axis combinations default to `out_of_envelope` or `not_tested`; they
cannot be silently counted inside the universal envelope.

S14 must not publish a scalar "universal score". It may publish counts and
rates needed for audit, but the public/expert/machine surface is the per-axis
scorecard plus declared envelope.

### Mechanism Generality

`MechanismGeneralityReport` proves that held-out cases are handled through
reused mechanisms rather than bespoke one-off patches.

The report reuses S12 `GrowthThermometerRecord` rather than computing a
parallel reuse metric. S12 owns `reuse_rate`, `reuse_rate_trend`,
`reused_primitive_refs`, `one_off_growth_refs`, and
`frozen_primitive_set_ref`; S14 adds the held-out marginal-bespoke-cost result
and points back to the S12 thermometer ref that was waiting on
`held_out_status == "pending_s14"`.

Required fields:

- `mechanism_reuse_rate`
- `growth_thermometer_ref`
- `s12_held_out_status`
- `marginal_bespoke_cost_status`: `pass`, `limited`, or `fail`
- `sublinear_marginal_bespoke_cost`
- `reused_mechanism_refs`
- `bespoke_patch_refs`
- `bespoke_patch_limitations`
- `held_out_case_refs`
- `dev_case_refs`
- `rule_version_ref`

The semantic pass condition is:

- held-out cases reuse the declared mechanism set;
- marginal bespoke cost is sublinear or explicitly limited;
- bespoke patches are not counted as mechanism generality;
- failed or untested mechanism regions stay out-of-envelope.

### Envelope Revision Dynamics

`EnvelopeRevisionDynamicsRecord` proves that S14 is not a frozen first-run
showcase. It is an aggregate over existing S12 and S13 records:

- S12 `EnvelopeGrowthLedger` rows provide reusable expansion evidence,
  counted mechanism-growth refs, flagged bespoke one-off refs, and open-cell
  count movement.
- S13 `EnvelopeRevision` and `CertifiedEnvelopeDelta` rows provide shrink,
  split, hold, and certified expansion refs with disconfirmation latency.
- S14 adds only the universality-battery interpretation: whether the held-out
  battery caused honest envelope expansion, limitation, shrink, or split.

The `frozen_once_defeater` may pass only when both sides are present: reusable
expansion evidence from S12 and shrink/split-on-disconfirmation evidence from
S13. A record that cites only expansion, or only shrink, is `limited` or
`fail`.

### Six Skeptic Defeaters

S14 evaluates exactly the six skeptic attacks from the target architecture. The
held-out integrity check remains a firewall, not one of the six attacks.

| Defeater id | Architecture attack | Required falsification input |
| --- | --- | --- |
| `bespoke_disguise_defeater` | "This is bespoke in disguise." | Frozen-system held-out cases, no case-specific code/manual construct/template authoring, sublinear marginal bespoke cost, rising primitive reuse. |
| `confident_theater_defeater` | "It is confident theater." | Negative controls and adversarial-against-A cases where false in-envelope, false pass, or hidden limitation would be caught. |
| `failure_boundary_defeater` | "It does not know where it fails." | Axis-stratified envelope calibration with false-in-envelope errors penalized heavily. |
| `single_axis_universality_defeater` | "It is universal only on one axis." | Per-axis and hard-corner scorecard that cannot aggregate away regime, scale, coupling, capacity, or authority failures. |
| `frozen_once_defeater` | "It works once, then freezes." | Envelope revision over rounds, reusable expansion evidence, and shrink on disconfirmation through S13/accountability refs. |
| `first_call_defeater` | "Why call it first?" | Baseline comparison against bespoke tools, raw LLMs, and expert panels for mechanism-generality, honest boundary, and grounded authority together. |

Every `SkepticDefeaterRecord` is a typed projection of a CAE defeater from
`assurance_case.py`, not an independent defeater taxonomy. S14 may add S14
fields for axis refs, hard corners, and baseline refs, but blocker/warning
semantics and the no-blocking-defeater pass gate come from the existing
assurance-case engine.

Every `SkepticDefeaterRecord` carries:

- `defeater_id`
- `attack_id`
- `attack_family`
- `status`: `pass`, `limited`, or `fail`
- `evidence_refs`
- `axis_refs`
- `hard_corner_case_refs`
- `baseline_refs`
- `envelope_revision_refs`
- `grounded_authority_refs`
- `residual_limitation_refs`
- `replay_digest`
- `rule_version_ref`

The S14 gate passes only when all six architecture-defined defeaters have
`status == "pass"`.

### Universality Claim Assurance Case

`UniversalityClaimAssuranceCase` is a S14 wrapper around the existing
`assurance_case.py` CAE/GSN substrate. The primary implementation path is to
add a sibling `build_universality_assurance_case` builder in
`assurance_case.py` that reuses the same blocker, warning, subclaim, evidence,
claim-status, and confidence-limit helpers while leaving
`build_assurance_case_for_scorecard` unchanged. A backwards-compatible
`claim_spec` generalization is only an allowed fallback if the sibling builder
cannot satisfy the S14 red tests; choosing that fallback requires explicit
regression assertions in `tests/unit/runtime/quality/test_assurance_case.py`.

The S14 module must convert S14 scorecard rows, D4 records, mechanism
generality, envelope revision dynamics, baseline comparison, and the six
skeptic attacks into the existing assurance-case scorecard shape:
`quality_gates`, `blocking_quality_failures`, `warnings`, `evidence_refs`, and
`quality_status`. `UniversalityClaimAssuranceCase` then stores refs to the CAE
claim, subclaims, evidence, defeaters, non-overridable blockers, and confidence
limits. It must not define an independent SACM/CAE object graph.

### Universality Claim Gate

`UniversalityClaimGateRecord` is the consumer-facing gate. It evaluates a claim
request such as "PolicyOS is a universal policy designer" against the scorecard
and assurance case.

Allowed dispositions:

- `universal_claim_allowed`
- `universal_claim_limited`
- `universal_claim_blocked`

Rules:

- A bare claim with no `s14_universality_assurance_refs` is blocked.
- A claim that implies all axes while the scorecard has any `not_tested` or
  `out_of_envelope` axis is blocked.
- A scoped claim is allowed only when the requested scope is a subset of the
  declared envelope, all six skeptic defeaters pass, the D4 breadth floor is
  satisfied for that posture, the grounded-authority coverage passes for every
  in-envelope axis, and the baseline comparison does not dominate PolicyOS on
  mechanism-generality plus honest boundary plus grounded authority.
- A limited claim is allowed only when limitations and out-of-envelope axes are
  visible in PUBLIC, EXPERT, and MACHINE surfaces, including D4 breadth
  shortfalls, oracle limitations, status-composition limits, and missing or
  limited grounded-authority refs.
- A claim is blocked when `weak_gold` is treated as a promotion floor,
  `shadow_candidate_pool` is treated as an oracle, `bespoke_growth_detected` is
  hidden, `envelope_shrunk` is treated as failure instead of honest boundary
  revision, or missing A-firewall refs are ignored.
- The gate can authorize only the use of the scoped universal claim wording. It
  cannot authorize policy recommendation, rollout, production, claim evidence,
  approval, publication, closeout, scorecard, preference learning, or automated
  value learning.

## Closure Metrics

Required S14 closeout metrics:

- `slice == "S14"`.
- `cells_closed == []`.
- `layer_cells_advanced == ["DESIGNER_ITSELF.evaluation_corpus"]`.
- `current_open_cell_count == 0`.
- `inventory_artifact_count == 22`.
- `required_traceability_artifact_count == 6`.
- `supporting_record_count >= 7`.
- `d4_corpus_track_count == 19`.
- `d4_corpus_track_coverage_status == "pass"`.
- `expert_oracle_layer_count == 4`.
- `expert_oracle_bootstrap_status == "pass"`.
- `breadth_floor_config_status == "ratified"`.
- `breadth_floor_status == "pass"`.
- `grounded_authority_coverage_status == "pass"`.
- `baseline_comparison_status == "pass"`.
- `evaluation_status_composition_status == "pass"`.
- `envelope_revision_dynamics_status == "pass"`.
- `canonical_corpus_case_count == 13`.
- `sealed_battery_case_count >= 6`.
- `axis_scorecard_row_count == 27`.
- `hard_corner_case_count >= 6`.
- `skeptic_defeater_count == 6`.
- `skeptic_defeater_pass_rate == 1.0`.
- `mechanism_generality_status == "pass"`.
- `sublinear_marginal_bespoke_cost_status == "pass"`.
- `sealed_battery_integrity_status == "pass"`.
- `sealed_battery_freeze_hash_match == true`.
- `dev_sealed_battery_access_count == 0`.
- `universal_claim_gate_status == "pass"`.
- `bare_universal_claim_block_count >= 1`.
- `untested_axis_out_of_envelope_count >= 1`.
- `aggregate_universal_number_block_count >= 1`.
- All S14 false-clear counts are `0`.

## Contract Dictionary

Add runtime constants in
`src/polisyos/runtime/quality/design_axes/universality_assurance.py`:

```python
LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s14_universality_assurance.v1"
)
LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION = (
    "policyos.layer2.s14.universality_assurance.v1"
)
S14_UNIVERSALITY_FLOOR_ID = "s14_universality"
S14_FALSE_CLEAR_FIELDS = (
    "bare_universal_claim_without_battery",
    "sealed_battery_dev_access",
    "aggregate_universal_number_laundering",
    "untested_axis_combination_in_envelope",
    "bespoke_cost_hidden_as_generality",
    "skeptic_defeater_ignored",
    "faithfulness_claim_without_s9",
    "battery_result_as_production_authority",
    "gold_label_leak_into_dev_signal",
    "freeze_hash_mismatch_accepted",
    "d4_breadth_floor_missing",
    "expert_oracle_bootstrap_missing",
    "weak_gold_floor_laundering",
    "shadow_candidate_oracle_laundering",
    "grounded_authority_refs_missing",
    "status_composition_laundering",
    "envelope_revision_freeze_laundering",
    "baseline_comparison_missing",
)
S14_SKEPTIC_DEFEATER_IDS = (
    "bespoke_disguise_defeater",
    "confident_theater_defeater",
    "failure_boundary_defeater",
    "single_axis_universality_defeater",
    "frozen_once_defeater",
    "first_call_defeater",
)
```

Add strict Pydantic contracts:

- `D4CorpusTrackCoverage`
- `ExpertOracleBootstrapRecord`
- `UniversalityBreadthFloorConfig`
- `UniversalityBaselineComparison`
- `GroundedAuthorityCoverageRecord`
- `EvaluationStatusCompositionRecord`
- `EnvelopeRevisionDynamicsRecord`
- `SealedUniversalityBatteryRun`
- `UniversalityAxisScoreRow`
- `UniversalityAxisScorecard`
- `MechanismGeneralityReport`
- `SkepticDefeaterRecord`
- `UniversalityClaimAssuranceCase`
- `UniversalityClaimGateRecord`
- `UniversalityAssuranceSummary`

Add literal types:

- `UniversalityAxisPosture = Literal["in_envelope", "limited", "out_of_envelope", "not_tested"]`
- `UniversalityBatteryStatus = Literal["pass", "limited", "blocked", "not_tested"]`
- `SkepticDefeaterStatus = Literal["pass", "limited", "fail"]`
- `MechanismGeneralityStatus = Literal["pass", "limited", "fail"]`
- `UniversalityClaimDisposition = Literal["universal_claim_allowed", "universal_claim_limited", "universal_claim_blocked"]`
- `D4CoverageStatus = Literal["pass", "limited", "blocked"]`
- `OracleLayerAuthority = Literal["seed_only", "supporting_evidence", "not_authoritative"]`
- `EvaluationStatusEffect = Literal["blocks_claim", "limits_claim", "seed_only", "projection_only", "advisory_only"]`
- `GroundedAuthorityStatus = Literal["pass", "limited", "blocked"]`
- `SealedBatteryAccessMode = Literal["ci_gate_only", "development_forbidden"]`
- `SealedBatteryRunMode = Literal["sealed_ci", "dev_shadow_no_hidden_access"]`

Import and reuse existing public substrate APIs:

- From `polisyos.runtime.quality.assurance_case`:
  `build_assurance_case_for_scorecard` and the new sibling
  `build_universality_assurance_case`. Prefer the sibling builder so the
  closeout-critical `build_assurance_case_for_scorecard` default behavior stays
  untouched. A backwards-compatible optional `claim_spec` generalization is a
  fallback only if the sibling builder cannot satisfy the S14 tests.
- From `polisyos.runtime.quality.capability_ratchet`:
  `build_capability_reality_report`.
- From `polisyos.runtime.quality.design_axes.resource_economics`:
  `EnvelopeGrowthLedger`, `GrowthThermometerRecord`,
  `build_envelope_growth_ledger`, and `build_growth_thermometers`.
- From `polisyos.runtime.quality.design_axes.post_deploy_accountability`:
  `CertifiedEnvelopeDelta`, `EnvelopeRevision`,
  `build_certified_envelope_delta`, and `build_envelope_revision`.

Add producer/helper functions:

- `build_s14_universality_authority_boundary`
- `build_d4_corpus_track_coverage`
- `build_expert_oracle_bootstrap_record`
- `build_universality_breadth_floor_config`
- `build_universality_baseline_comparison`
- `build_grounded_authority_coverage_record`
- `compose_s14_evaluation_statuses`
- `build_envelope_revision_dynamics_record`
- `compute_sealed_battery_freeze_hash`
- `verify_sealed_battery_integrity`
- `build_s14_capability_reality_axis_rows`
- `build_universality_axis_scorecard`
- `build_s14_mechanism_generality_from_growth_thermometer`
- `build_mechanism_generality_report`
- `build_s14_cae_scorecard`
- `build_universality_assurance_case` in `assurance_case.py`
- `project_cae_defeaters_to_s14_skeptic_records`
- `build_skeptic_defeater_records`
- `build_universality_claim_assurance_case`
- `gate_universality_claim`
- `verify_universality_claim_authority`
- `summarize_universality_assurance`
- `build_s14_universality_assurance_projection`

Authority posture:

- `authoritative_for`: `s14_universality_claim_gate`,
  `sealed_battery_integrity`, `per_axis_universality_scorecard`,
  `mechanism_generality_assessment`, `skeptic_defeater_evaluation`,
  `d4_corpus_track_coverage`, `expert_oracle_bootstrap`,
  `universality_breadth_floor`, `baseline_comparison`,
  `grounded_authority_coverage`, `evaluation_status_composition`,
  `envelope_revision_dynamics`, `declared_operation_envelope`.
- `may_not_use_for`: `production_rollout_authority`,
  `production_recommendation`, `recommendation_authority`,
  `publication_authority`, `approval_authority`, `claim_authority`,
  `runtime_closeout_authority`, `scorecard_authority`, `current_evidence_slot`,
  `pre_policy_evidence`, `preference_learning`, `automated_value_learning`,
  `sealed_battery_training`, `development_fixture_access`,
  `aggregate_universal_score`, `untested_axis_envelope_expansion`,
  `gold_label_authority`, `floor_relaxation`,
  `weak_gold_promotion_floor`, `shadow_candidate_oracle`,
  `baseline_free_universal_claim`, `grounded_authority_without_a_firewalls`,
  `status_composition_override`.

## File Map

Create:

- `src/polisyos/runtime/quality/design_axes/universality_assurance.py`
- `tools/quality/validation/run_layer2_s14_universality_battery.py`
- `tests/unit/runtime/quality/test_layer2_s14_universality_assurance.py`
- `tests/repo_quality/tools/test_layer2_s14_universality_battery.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s14_universality_assurance.py`
- `tests/fixtures/layer2/s14/s14_universality_dev_signals.json`
- `tests/fixtures/layer2/s14/s14_universality_expert_labels.json`
- `tests/fixtures/layer2/s14/s14_d4_corpus_track_coverage.json`
- `tests/fixtures/layer2/s14/s14_expert_oracle_bootstrap.json`
- `tests/fixtures/layer2/s14/s14_universality_breadth_floor_config.json`
- `tests/fixtures/layer2/s14/s14_universality_baseline_comparison.json`
- `tests/fixtures/layer2/s14/s14_grounded_authority_refs.json`
- `tests/fixtures/layer2/s14/s14_evaluation_status_composition_cases.json`
- `tests/fixtures/layer2/s14/s14_envelope_revision_dynamics.json`
- `tests/fixtures/layer2/s14/negative_controls/bare_universal_claim_without_battery_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/sealed_battery_dev_access_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/aggregate_universal_number_laundering_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/untested_axis_combination_in_envelope_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/bespoke_cost_hidden_as_generality_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/skeptic_defeater_ignored_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/faithfulness_claim_without_s9_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/battery_result_as_production_authority_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/gold_label_leak_into_dev_signal_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/freeze_hash_mismatch_accepted_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/d4_breadth_floor_missing_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/expert_oracle_bootstrap_missing_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/weak_gold_floor_laundering_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/shadow_candidate_oracle_laundering_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/grounded_authority_refs_missing_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/status_composition_laundering_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/envelope_revision_freeze_laundering_probe.json`
- `tests/fixtures/layer2/s14/negative_controls/baseline_comparison_missing_probe.json`
- `tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery/manifest.json`
- `tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery/cases/s14_capacity_constrained_refugee_services.json`
- `tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery/cases/s14_entangled_river_basin_adaptation.json`
- `tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery/cases/s14_low_observability_health_equity.json`
- `tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery/cases/s14_multi_principal_social_protection.json`
- `tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery/cases/s14_strategic_tax_enforcement_response.json`
- `tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery/cases/s14_high_stakes_irreversible_climate.json`
- `architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json`

Modify:

- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/runtime/quality/assurance_case.py` to add the sibling
  `build_universality_assurance_case` builder; use `claim_spec` generalization
  only as fallback.
- `src/polisyos/runtime/quality/projection_semantics.py`
- `src/polisyos/runtime/quality/public_export.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `architecture/policy_design_case/layer2_corpus_partition.json`
- `architecture/policy_design_case/layer2_artifact_traceability.toml`
- `architecture/policy_design_case/cluster_ownership_map.toml`
- `architecture/policy_design_case/inventory.json`
- `architecture/public_surface/inventory.json` if the public-surface snapshot
  detects drift after adding S14 runtime-quality exports.
- `docs/reference/public-surface.md` if the public-surface snapshot detects
  drift after adding S14 runtime-quality exports.
- `tests/unit/runtime/quality/test_assurance_case.py` for the sibling builder
  and for closeout-regression coverage if fallback generalization is used.
- `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- `tests/unit/runtime/quality/test_public_export.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- Prior Layer 2 repo-quality snapshot tests that assert exact inventory counts
  or that S14 is still a future implemented-artifact denial.

Read/reuse first; do not modify unless a failing test proves a contract gap:

- `src/polisyos/corpus/_impl/loaders.py`
- `tests/unit/corpus/test_loaders.py`
- `src/polisyos/runtime/quality/capability_ratchet.py`
- `tests/unit/runtime/quality/test_capability_ratchet.py`
- `src/polisyos/runtime/quality/design_axes/projection_lowering.py`
- `src/polisyos/runtime/quality/design_axes/resource_economics.py`
- `src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py`
- `src/polisyos/pdc/_impl/layer2_design_search.py`

Do not modify unless a validator proves it is necessary:

- `architecture/policy_design_case/layer2_slice_cell_matrix.toml`
- `architecture/policy_design_case/layer2_floor_governance.toml`

## Task 1: Red-First S14 Semantic And Negative Tests

Write failing tests before adding implementation.

Runtime tests in
`tests/unit/runtime/quality/test_layer2_s14_universality_assurance.py`:

- `test_s14_contracts_are_strict_replayable_and_exported`
- `test_sealed_battery_integrity_requires_partition_path_freeze_hash_and_owner`
- `test_sealed_battery_access_requires_explicit_ci_gate`
- `test_dev_shadow_mode_cannot_read_hidden_sealed_battery`
- `test_axis_scorecard_defaults_untested_axis_combinations_out_of_envelope`
- `test_per_axis_scorecard_covers_all_cluster_cells_without_aggregate_universal_number`
- `test_per_axis_scorecard_derives_rows_from_capability_reality_report`
- `test_mechanism_generality_requires_sublinear_marginal_bespoke_cost`
- `test_mechanism_generality_reuses_s12_growth_thermometer_pending_s14_ref`
- `test_d4_corpus_track_coverage_requires_all_19_architecture_tracks`
- `test_expert_oracle_bootstrap_keeps_weak_gold_and_shadow_candidates_seed_only`
- `test_breadth_floor_config_names_domain_jurisdiction_scale_regime_coupling_targets`
- `test_grounded_authority_requires_a_firewall_claim_value_mandate_capacity_refs`
- `test_evaluation_status_composition_blocks_seed_and_gap_laundering`
- `test_evaluation_status_composition_maps_d4_labels_to_existing_closeout_lattice`
- `test_skeptic_defeaters_match_architecture_six_attacks_exactly`
- `test_skeptic_defeaters_require_all_six_attacks_to_pass`
- `test_skeptic_defeaters_are_projected_from_assurance_case_defeaters`
- `test_frozen_once_defeater_requires_expand_and_shrink_revision_evidence`
- `test_envelope_revision_dynamics_reuses_s12_growth_ledger_and_s13_revisions`
- `test_first_call_defeater_requires_baseline_comparison`
- `test_universality_claim_requires_scorecard_battery_and_assurance_refs`
- `test_universality_claim_assurance_case_reuses_runtime_assurance_case_builder`
- `test_bare_universal_claim_without_s14_refs_is_blocked`
- `test_universality_gate_allows_limited_claim_with_declared_envelope_only`
- `test_universality_assurance_cannot_mint_production_or_recommendation_authority`
- `test_gold_labels_cannot_appear_in_dev_signals_or_public_export`
- `test_freeze_hash_mismatch_fails_closed`
- `test_s14_summary_requires_exact_false_clear_keys`

Projection and export tests in
`tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py` and
`tests/unit/runtime/quality/test_public_export.py`:

- `test_s14_projection_surfaces_per_axis_scorecard_and_declared_envelope`
- `test_s14_projection_surfaces_d4_breadth_oracle_and_grounded_authority_refs`
- `test_s14_projection_blocks_aggregate_universal_number`
- `test_s14_projection_blocks_universal_claim_without_gate_record`
- `test_s14_projection_allows_universal_claim_only_with_assurance_refs`
- `test_public_export_surfaces_limited_universality_claim_as_projection_only`
- `test_public_export_blocks_hidden_battery_material_and_gold_labels`
- `test_public_export_blocks_s14_as_production_or_recommendation_authority`

Sealed runner tests in
`tests/repo_quality/tools/test_layer2_s14_universality_battery.py`:

- `test_s14_battery_runner_refuses_sealed_pack_without_allow_flag`
- `test_s14_battery_runner_verifies_freeze_hash`
- `test_s14_battery_runner_emits_d4_oracle_breadth_scorecard_skeptic_defeaters_and_summary`
- `test_s14_battery_runner_emits_baseline_grounded_authority_and_status_composition`
- `test_s14_battery_runner_emits_required_substrate_reuse_refs`
- `test_s14_battery_runner_rejects_dev_corpus_as_sealed_result`
- `test_s14_battery_runner_redacts_hidden_case_content_from_public_summary`

W12D dev-route tests in
`tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`:

- `test_w12d_emits_s14_dev_assurance_blocks_for_13_cases_without_sealed_access`
- `test_w12d_s14_dev_route_preserves_s2_s9_s13_authority_boundaries`
- `test_w12d_s14_bare_universal_claim_negative_control_has_zero_false_clears`
- `test_w12d_s14_scorecard_refs_are_pending_sealed_not_passed_in_dev`
- `test_w12d_s14_gold_labels_cover_13_cases_without_leaking_into_signals`
- `test_w12d_s14_dev_route_emits_d4_status_composition_without_claim_authority`

Manifest tests in
`tests/repo_quality/tools/test_policy_design_case_layer2_s14_universality_assurance.py`:

- `test_s14_manifest_exists_and_declares_closure_contract`
- `test_s14_manifest_registers_six_artifacts_and_firewalls`
- `test_s14_manifest_registers_d4_corpus_oracle_breadth_supporting_records`
- `test_s14_manifest_registers_required_substrate_reuse_refs`
- `test_s14_manifest_maps_skeptic_defeaters_to_architecture_attacks`
- `test_s14_manifest_requires_grounded_authority_and_baseline_comparison`
- `test_s14_manifest_advances_evaluation_corpus_without_new_closed_cell`
- `test_s14_manifest_keeps_current_open_cell_count_zero`
- `test_s14_artifact_traceability_is_implemented_once`
- `test_s14_cluster_map_advances_evaluation_corpus_without_reopening_cell`
- `test_s14_inventory_adds_one_manifest_and_authorizes_only_universal_claim_gate`
- `test_s14_readiness_validator_accepts_universality_assurance`
- `test_s14_corpus_partition_rotates_freeze_hash_and_keeps_hidden_access_rule`

Fixture requirements:

- 13 S14 dev-signal rows, one per W12D canonical case.
- 13 S14 expert-label rows, one per W12D canonical case.
- 19 D4 corpus-track coverage rows with minimum-label refs.
- 4 expert-oracle bootstrap rows:
  `weak_gold`, `expert_gold_seed`, `causal_support_seed`, and
  `shadow_candidate_pool`.
- 1 breadth-floor config naming domain, jurisdiction, scale, regime, coupling,
  lifecycle, capacity, authority-posture, instrument-family,
  system-dynamics, inter-rater, and excluded-domain fields.
- 1 baseline-comparison fixture covering bespoke tools, raw LLMs, and expert
  panels.
- 1 grounded-authority fixture with A-firewall, claim/evidence,
  value-choice, mandate, capacity, regime, coupling, and projection refs.
- 1 status-composition fixture covering `weak_gold`, `shadow_candidate_pool`,
  `outside_certified_envelope`, `a_spec_gap`, `search_incomplete`,
  `projection_only`, `bespoke_growth_detected`, `envelope_expanded`,
  `envelope_shrunk`, and `historical_prior_only`.
- Mechanism-generality fixtures must cite S12 `GrowthThermometerRecord`
  `thermometer_ref`, `reuse_rate`, `reused_primitive_refs`,
  `one_off_growth_refs`, `frozen_primitive_set_ref`, and
  `held_out_status == "pending_s14"`.
- Envelope-revision-dynamics fixtures must cite S12 `EnvelopeGrowthLedger`
  expansion refs and S13 `EnvelopeRevision`/`CertifiedEnvelopeDelta`
  shrink/split or certified expansion refs.
- Assurance fixtures must cite the CAE assurance-case ref, CAE defeater refs,
  and capability-reality report ref used to derive the S14 scorecard.
- 6 sealed hard-corner cases in the hidden battery path.
- The sealed battery manifest must declare the exact six architecture skeptic
  defeaters and the same hard-corner case ids as the hidden case files.
- Negative probes for every `S14_FALSE_CLEAR_FIELDS` value.
- Dev signals must not contain `expected_*`, `gold_*`, `answer_key`,
  `hidden_case_payload`, or `sealed_fixture_contents` fields.
- Public projection/export tests must prove hidden content is absent from
  rendered bundles.

Execution steps:

- [ ] **Step 1: Add runtime red tests and S14 fixtures** in
  `tests/unit/runtime/quality/test_layer2_s14_universality_assurance.py` and
  `tests/fixtures/layer2/s14`.
- [ ] **Step 2: Add projection, public-export, sealed-runner, W12D, and manifest
  red tests** in the files named above.
- [ ] **Step 3: Run the red command** and verify the expected missing-module,
  missing-runner, missing-verifier, and missing-manifest failures.
- [ ] **Step 4: Commit only tests and fixtures** with
  `test: add layer2 s14 universality assurance red tests`.

Expected red command:

```bash
cd policy-engine
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s14_universality_assurance.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_layer2_s14_universality_battery.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s14_universality_assurance.py \
  -q
```

Expected red output:

- Import failure for `polisyos.runtime.quality.design_axes.universality_assurance`.
- Missing `assurance_case.build_universality_assurance_case`; if the fallback
  `claim_spec` route is chosen instead, closeout regression tests must fail red
  until default behavior is proven unchanged.
- Missing `tools/quality/validation/run_layer2_s14_universality_battery.py`.
- Missing S14 projection verifier and public-export hook.
- Missing W12D `s14_universality_assurance` blocks and summary.
- Missing S14 manifest.

Commit:

```bash
git add tests/unit/runtime/quality/test_layer2_s14_universality_assurance.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_layer2_s14_universality_battery.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s14_universality_assurance.py \
  tests/fixtures/layer2/s14 \
  tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery
git commit -m "test: add layer2 s14 universality assurance red tests"
```

## Task 2: Contracts, Producer Helpers, And Universality Firewalls

Implement
`src/polisyos/runtime/quality/design_axes/universality_assurance.py`.

Implementation requirements:

- Strict Pydantic models must inherit `Layer2ReadinessModel` imported from the
  public `polisyos.pdc` package, matching S12/S13; do not use raw `BaseModel`
  for public S14 DTOs.
- Authority boundaries must use the existing `AuthorityBoundary` shape and a
  `build_s14_universality_authority_boundary` helper, mirroring S12/S13
  patterns.
- Google-style docstrings for public models/functions.
- Deterministic replay digests built from stable semantic fields.
- Distinct freeze, access, run, scoring, assurance, and projection timestamps.
- Add the sibling `build_universality_assurance_case` in `assurance_case.py`
  and preserve `build_assurance_case_for_scorecard(scorecard)` unchanged.
  Generalize the existing closeout builder with `claim_spec` only as a fallback
  if the sibling path cannot satisfy the S14 red tests; that fallback must keep
  `test_assurance_case.py` green.
- `SealedUniversalityBatteryRun` requires partition path, owner,
  `access_mode == "ci_gate_only"`, freeze hash, computed hash, and explicit
  access grant when `run_mode == "sealed_ci"`.
- `SealedUniversalityBatteryRun` in dev-shadow mode must set
  `sealed_battery_access_attempted == False` and cannot carry hidden case
  payloads.
- `D4CorpusTrackCoverage` must carry all 19 architecture D4 tracks and their
  minimum-label refs.
- `ExpertOracleBootstrapRecord` must carry exactly four oracle layers and
  preserve `weak_gold` and `shadow_candidate_pool` as non-authoritative seeds.
- `UniversalityBreadthFloorConfig` must name the governed breadth target,
  owner, revision rule, threshold refs, excluded domains, and floor-setting
  method.
- `UniversalityBaselineComparison` must include bespoke-tool, raw-LLM, and
  expert-panel comparison refs.
- `GroundedAuthorityCoverageRecord` must require A-firewall, claim/evidence,
  value-choice, mandate/legitimacy, capacity, regime, coupling, and projection
  refs for in-envelope claims.
- `EvaluationStatusCompositionRecord` must define whether each D4 status blocks,
  limits, seeds, projects, or remains advisory for a universal claim, and must
  map those effects into existing closeout/review/public-revalidation semantics
  rather than creating a new D4 authority lattice.
- `EnvelopeRevisionDynamicsRecord` must require reusable expansion evidence and
  shrink-on-disconfirmation refs from S12 `EnvelopeGrowthLedger` plus S13
  `EnvelopeRevision`/`CertifiedEnvelopeDelta`.
- `UniversalityAxisScorecard` must carry exactly 27 axis rows when built from
  the current cluster map cells and must use
  `build_capability_reality_report(...)` as the existing capability-reality
  substrate.
- Untested axis combinations must be `out_of_envelope` or `not_tested`, never
  implicitly `in_envelope`.
- `MechanismGeneralityReport` must block mechanism generality when bespoke
  patches are counted as reusable mechanisms, and must reuse S12
  `GrowthThermometerRecord` refs for reuse rate, one-off growth, reused
  primitives, and frozen primitive set.
- `SkepticDefeaterRecord` must require the exact six architecture-defined
  defeater ids and must be projected from assurance-case defeaters; held-out
  integrity is a firewall, not a skeptic defeater.
- `UniversalityClaimAssuranceCase` must include D4 coverage, oracle, breadth,
  battery, scorecard, mechanism, grounded authority, baseline comparison,
  envelope revision dynamics, S9 faithfulness, projection, status composition,
  and skeptic-defeater refs. It must call the existing assurance-case builder
  path and persist refs to its CAE claim, evidence, defeaters,
  non-overridable blockers, and confidence limits.
- `UniversalityClaimGateRecord` must block bare universal claims, aggregate
  universal numbers, unscoped claims over untested axes, and authority
  laundering.
- `verify_universality_claim_authority` returns exact false-clear keys.
- `summarize_universality_assurance` reports closure metrics and false-clear
  counts.
- `UniversalityAssuranceSummary` must validate exact nested
  `false_clear_counts` keys and matching flat `*_false_clear_count` fields,
  following the S12/S13 summary pattern.
- Runtime package exports S14 public contracts from
  `src/polisyos/runtime/quality/__init__.py`.

Anti-universality-laundering firewalls:

- No bare universal claim without S14 battery, scorecard, declared envelope,
  assurance case, and gate record refs.
- No hidden sealed battery access during development routes.
- No aggregate universal score or single number as the authority surface.
- No untested axis combination inside the declared envelope.
- No bespoke one-off patch counted as mechanism generality.
- No ignored skeptic defeater.
- No parallel CAE/GSN/SACM object graph for S14.
- No parallel per-axis capability reality report.
- No faithfulness claim without S9 projection faithfulness refs.
- No D4 breadth floor missing or silently relaxed.
- No expert-oracle bootstrap missing.
- No `weak_gold` treated as a promotion floor.
- No `shadow_candidate_pool` treated as the oracle.
- No missing A-firewall or grounded-authority refs for in-envelope claims.
- No status-composition laundering across seed, gap, projection-only, or
  envelope-revision labels.
- No envelope revision that only expands and cannot shrink on disconfirmation.
- No frozen-once pass without both S12 expansion and S13 shrink/split refs.
- No universal claim without baseline comparison against bespoke tools, raw LLMs,
  and expert panels.
- No battery result as production, rollout, recommendation, approval,
  publication, claim, closeout, or scorecard authority.
- No gold labels or hidden sealed case contents in dev signals, projection
  payloads, or public export.
- No freeze hash mismatch accepted.

Execution steps:

- [ ] **Step 1: Add the sibling universality assurance builder** in
  `src/polisyos/runtime/quality/assurance_case.py` as
  `build_universality_assurance_case`, reusing the existing CAE helper path and
  leaving `build_assurance_case_for_scorecard` unchanged. Use a
  backwards-compatible `claim_spec` generalization only as a fallback, with
  tests proving the existing closeout assurance case output remains unchanged
  by default.
- [ ] **Step 2: Add module constants, literals, and strict models** in
  `src/polisyos/runtime/quality/design_axes/universality_assurance.py`.
- [ ] **Step 3: Implement the S14 authority boundary and D4 coverage, oracle,
  breadth, baseline, grounded authority, status composition, envelope revision,
  freeze-hash, scorecard, mechanism, skeptic, assurance, gate, authority, and
  summary helpers** as adapters over `assurance_case.py`,
  `capability_ratchet.py`, S12 `GrowthThermometerRecord`/
  `EnvelopeGrowthLedger`, S13 `EnvelopeRevision`/`CertifiedEnvelopeDelta`, and
  existing closeout status semantics.
- [ ] **Step 4: Implement S14 false-clear detection** so every
  `S14_FALSE_CLEAR_FIELDS` key is produced and summarized.
- [ ] **Step 5: Export runtime contracts** from
  `src/polisyos/runtime/quality/__init__.py`.
- [ ] **Step 6: Run runtime tests and ruff**, then commit
  `feat: add layer2 s14 universality assurance contracts`.

Verification:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s14_universality_assurance.py -q
uv run pytest tests/unit/runtime/quality/test_assurance_case.py -q
uv run ruff check \
  src/polisyos/runtime/quality/assurance_case.py \
  src/polisyos/runtime/quality/design_axes/universality_assurance.py \
  tests/unit/runtime/quality/test_assurance_case.py \
  tests/unit/runtime/quality/test_layer2_s14_universality_assurance.py
```

Expected output:

- Runtime S14 tests pass.
- Assurance-case tests pass, the sibling universality builder is covered, and
  the existing closeout assurance case behavior remains unchanged. If the
  fallback `claim_spec` path was used, tests also prove default closeout output
  is unchanged when no `claim_spec` is supplied.
- S14 reuse tests prove scorecard rows come from capability reality, mechanism
  generality cites S12 thermometers, envelope dynamics cite S12/S13 records,
  and skeptic records are projected from CAE defeaters.
- Ruff reports no issues for the new module and tests.

Commit:

```bash
git add src/polisyos/runtime/quality/design_axes/universality_assurance.py \
  src/polisyos/runtime/quality/assurance_case.py \
  src/polisyos/runtime/quality/__init__.py \
  tests/unit/runtime/quality/test_assurance_case.py \
  tests/unit/runtime/quality/test_layer2_s14_universality_assurance.py
git commit -m "feat: add layer2 s14 universality assurance contracts"
```

## Task 3: Gate Universal Claims Through Projection Semantics And Public Export

Wire S14 into projection semantics and public export.

Implementation requirements:

- Add `_S14_CONSUMER_CONTRACT_REF` to
  `src/polisyos/runtime/quality/projection_semantics.py`.
- Add `verify_s14_universality_projection_consumer_contract` as a sibling
  of the S13 verifier.
- Add `_s14_universality_projection_record`, `_s14_projection_issues`,
  `_s14_authority_laundered`, and `_s14_public_projection` helper functions.
- PUBLIC view includes scoped universal claim wording, declared envelope,
  limitations, out-of-envelope axes, D4 breadth limitation summary, oracle
  seed-only caveats, grounded-authority status, and projection-only authority.
- EXPERT view includes per-axis rows, hard-corner coverage, D4 track coverage,
  oracle bootstrap layers, breadth floor, baseline comparison, grounded
  authority refs, status composition, skeptic defeaters, mechanism-generality
  report, threshold refs, and residual limitations.
- MACHINE view includes battery run ref, freeze hash, scorecard ref, assurance
  case ref, D4/oracle/breadth/baseline/grounded-authority refs, gate record
  ref, replay digest, rule version, and issue codes.
- Projection checks block aggregate universal numbers, missing S14 gate refs,
  missing D4/breadth/oracle/grounded-authority/baseline/status-composition refs,
  hidden sealed content, gold labels, and production/recommendation authority.
- Add `_apply_s14_universality_projection` to
  `src/polisyos/runtime/quality/public_export.py`.
- Call the S14 public-export hook after S13 enrichment, as a sibling hook in
  the existing `build_public_export_bundle` projection flow.
- Public export may include S14 surface fields only after the S14 projection
  consumer contract passes.
- Public export must redact hidden battery material and gold labels even when
  S14 projection is present.
- Expand public-export forbidden key/value tokens with exact S14 terms:
  `sealed_battery`, `sealed_fixture`, `sealed_fixture_contents`,
  `sealed_case_payload`, `hidden_case_payload`, `gold_label`,
  `gold_labels`, `weak_gold_answer`, `expert_oracle_private_notes`,
  `oracle_private_notes`, and `answer_key`.
- Public export should include S14 refs, status summaries, and limitation text;
  it must not embed sealed case contents, gold labels, full expert-oracle
  private notes, or full hidden battery fixture bodies.
- Keep S9's existing
  `s9_universal_self_claim_without_s14_refs` negative path; add a positive
  projection test with passing S14 assurance refs.

Concrete projection payload fields:

- `s14_universality_assurance_ref`
- `universality_claim_gate_ref`
- `universality_claim_disposition`
- `declared_operation_envelope_ref`
- `d4_corpus_track_coverage_ref`
- `d4_corpus_track_coverage_status`
- `expert_oracle_bootstrap_ref`
- `expert_oracle_seed_only_layer_refs`
- `breadth_floor_config_ref`
- `breadth_floor_status`
- `excluded_domain_refs`
- `universality_baseline_comparison_ref`
- `baseline_comparison_status`
- `grounded_authority_coverage_ref`
- `grounded_authority_status`
- `a_firewall_refs`
- `claim_evidence_binding_refs`
- `value_choice_provenance_refs`
- `mandate_legitimacy_refs`
- `capacity_check_refs`
- `evaluation_status_composition_ref`
- `status_composition_limit_refs`
- `envelope_revision_dynamics_ref`
- `envelope_revision_dynamics_status`
- `axis_scorecard_ref`
- `axis_scorecard_rows`
- `out_of_envelope_axis_refs`
- `not_tested_axis_refs`
- `hard_corner_case_refs`
- `sealed_battery_run_ref`
- `sealed_battery_freeze_hash`
- `sealed_battery_integrity_status`
- `mechanism_generality_report_ref`
- `mechanism_generality_status`
- `sublinear_marginal_bespoke_cost_status`
- `skeptic_defeater_refs`
- `skeptic_defeater_statuses`
- `s9_projection_faithfulness_refs`
- `public_universality_limitation`
- `replay_digest`
- `authority_boundary`
- `may_not_be_used_for`
- `rule_version_ref`

For PUBLIC export, `axis_scorecard_rows` and supporting-record details must be
redacted or summarized to non-hidden refs/statuses. EXPERT and MACHINE payloads
may carry redacted derived rows, but none of the three surfaces may expose
sealed case payloads, gold labels, or private oracle notes.

Execution steps:

- [ ] **Step 1: Add S14 projection verifier and helper functions** in
  `projection_semantics.py`.
- [ ] **Step 2: Add S14 public-export hook and redaction checks** in
  `public_export.py`.
- [ ] **Step 3: Add positive and negative S14 projection/export tests** while
  keeping S9's no-ref negative test.
- [ ] **Step 4: Run projection/export tests and ruff**, then commit
  `feat: gate universal claims through s14 projections`.

Verification:

```bash
cd policy-engine
uv run pytest \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  -q
uv run ruff check \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py
```

Expected output:

- Projection and public export tests pass.
- Ruff reports no issues for touched modules.

Commit:

```bash
git add src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py
git commit -m "feat: gate universal claims through s14 projections"
```

## Task 4: Sealed Battery Runner And 13-Case Dev Route Bridge

Implement the explicit S14 sealed runner and the W12D dev-shadow bridge.

### Sealed Runner

Create `tools/quality/validation/run_layer2_s14_universality_battery.py`.

Required public functions:

- `build_s14_universality_battery_manifest`
- `compute_sealed_battery_freeze_hash`
- `run_layer2_s14_universality_battery`
- `main`

Required CLI:

```bash
uv run python tools/quality/validation/run_layer2_s14_universality_battery.py \
  --repo-root . \
  --battery-root tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery \
  --allow-sealed-battery \
  --output _build/.tmp/production-quality/layer2_s14_universality_battery.json
```

Required bootstrap CLI for hash rotation:

```bash
uv run python tools/quality/validation/run_layer2_s14_universality_battery.py \
  --repo-root . \
  --battery-root tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery \
  --allow-sealed-battery \
  --print-freeze-hash
```

Runner requirements:

- Without `--allow-sealed-battery`, return non-zero and issue
  `sealed_battery_access_requires_explicit_allow`.
- With `--allow-sealed-battery`, read only the configured sealed battery path.
- Do not call `load_universal_corpus_fixtures(split=None)` for the S14 sealed
  battery. The runner should read the partition-configured sealed pack directly
  after validating the path, owner, access mode, and explicit allow flag.
- Compute and verify freeze hash against `layer2_corpus_partition.json`.
- Support `--print-freeze-hash` as the only bootstrap path that computes the
  same deterministic hash and prints only `sha256:<hex>` before the partition
  value has been rotated. This mode still requires `--allow-sealed-battery`,
  validates the configured path, owner, and access mode, and does not produce a
  passing battery result.
- Rotate `architecture/policy_design_case/layer2_corpus_partition.json`
  `sealed_universality_battery.freeze_hash` in Task 4 after the runner and
  Task 1 sealed fixtures exist. Task 5 validates this value; it does not perform
  the rotation.
- Produce a top-level `s14_universality_assurance_summary`.
- Produce `D4CorpusTrackCoverage`, `ExpertOracleBootstrapRecord`,
  `UniversalityBreadthFloorConfig`, `UniversalityBaselineComparison`,
  `GroundedAuthorityCoverageRecord`, `EvaluationStatusCompositionRecord`,
  `EnvelopeRevisionDynamicsRecord`, `SealedUniversalityBatteryRun`,
  `UniversalityAxisScorecard`, `MechanismGeneralityReport`, six
  `SkepticDefeaterRecord` rows, `UniversalityClaimAssuranceCase`, and
  `UniversalityClaimGateRecord` payloads.
- Build those payloads through the reuse adapters named in Task 2:
  `UniversalityAxisScorecard` from `build_capability_reality_report`,
  `MechanismGeneralityReport` from S12 `GrowthThermometerRecord`,
  `EnvelopeRevisionDynamicsRecord` from S12 `EnvelopeGrowthLedger` plus S13
  `EnvelopeRevision`/`CertifiedEnvelopeDelta`, and
  `UniversalityClaimAssuranceCase`/`SkepticDefeaterRecord` from the
  `assurance_case.py` CAE path.
- Redact hidden case contents from the public summary.
- Set all S14 false-clear counts to zero for the governed fixture set.

### W12D Dev Route

Wire `tools/quality/validation/run_universal_outcome_corpus.py` so regular
W12D runs emit S14 dev-shadow blocks over the 13 canonical cases without sealed
access.

Concrete W12D touch points:

- Import S14 runtime constants/builders from
  `polisyos.runtime.quality.design_axes.universality_assurance`.
- Add `S14_DEV_SIGNALS_PATH`, `S14_EXPERT_LABELS_PATH`, and
  `S14_NEGATIVE_CONTROL_PROBE_PATHS`.
- Add `S14_D4_TRACK_COVERAGE_PATH`, `S14_ORACLE_BOOTSTRAP_PATH`,
  `S14_BREADTH_FLOOR_PATH`, `S14_BASELINE_COMPARISON_PATH`,
  `S14_GROUNDED_AUTHORITY_REFS_PATH`, `S14_STATUS_COMPOSITION_PATH`, and
  `S14_ENVELOPE_REVISION_DYNAMICS_PATH`.
- Add `_s14_universality_dev_case_block`, `_s14_universality_dev_summary`,
  `_s14_negative_control_probe_results`, and `_s14_matches_gold` as siblings of
  the S13 helpers.
- Add `s14_universality_assurance` to each case output.
- Add `s14_universality_assurance_summary` to the top-level report.
- Set `sealed_battery_status == "not_accessed_in_dev"` and
  `sealed_battery_access_attempted == False` for W12D.
- Do not import or traverse the sealed battery path from W12D. W12D may read
  only `tests/fixtures/layer2/s14/*.json`, negative-control probes, the cluster
  map, and redacted corpus-partition metadata.
- W12D S14 dev-shadow status may be `pending_sealed`, `not_tested`,
  `limited`, or `blocked` depending on fixture evidence. It must not emit
  `universal_claim_gate_status == "pass"` without the sealed runner output.
- Preserve S2/S9/S13 authority boundaries. S14 dev-shadow blocks do not change
  canonical outcome, closeout, or production authority.

Required W12D summary assertions:

```python
assert summary["case_count"] == 13
assert summary["sealed_battery_status"] == "not_accessed_in_dev"
assert summary["sealed_battery_access_attempted"] is False
assert summary["dev_sealed_battery_access_count"] == 0
assert summary["universal_claim_gate_status"] != "pass"
assert summary["d4_corpus_track_count"] == 19
assert summary["expert_oracle_layer_count"] == 4
assert summary["breadth_floor_status"] in {"pass", "limited", "blocked"}
assert summary["grounded_authority_coverage_status"] in {"pass", "limited", "blocked"}
assert summary["baseline_comparison_status"] in {"pass", "limited", "blocked"}
assert summary["evaluation_status_composition_status"] == "pass"
assert summary["envelope_revision_dynamics_status"] in {"pass", "limited", "blocked"}
assert summary["bare_universal_claim_block_count"] >= 1
assert summary["aggregate_universal_number_block_count"] >= 1
assert summary["untested_axis_out_of_envelope_count"] >= 1
assert all(count == 0 for count in summary["false_clear_counts"].values())
```

Execution steps:

- [ ] **Step 1: Verify the Task 1 hidden battery manifest and six hard-corner
  fixtures** are the only sealed case ids used by the runner; new case ids require
  a red-test fixture update first.
- [ ] **Step 2: Implement the S14 sealed-battery runner** with explicit access
  gating, freeze-hash verification, D4/oracle/breadth/baseline/grounded-authority
  records, scorecard, exact skeptic defeaters, assurance case, and gate record
  output, reusing the Task 2 substrate adapters rather than constructing
  parallel scorecard, growth, envelope, or assurance-case engines.
- [ ] **Step 3: Rotate the sealed battery freeze hash** by running
  `--print-freeze-hash`, replacing the empty-content placeholder in
  `architecture/policy_design_case/layer2_corpus_partition.json`, and rerunning
  the normal sealed runner until `sealed_battery_integrity_status=pass`.
- [ ] **Step 4: Add W12D S14 dev-shadow imports, paths, helper functions, and
  summary output** without reading the sealed battery or using a generic
  all-fixture loader for hidden/sealed content.
- [ ] **Step 5: Run sealed-runner and W12D tests**, then commit
  `feat: run layer2 s14 universality battery`.

Verification:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_layer2_s14_universality_battery.py -q
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
uv run python tools/quality/validation/run_layer2_s14_universality_battery.py \
  --repo-root . \
  --battery-root tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery \
  --allow-sealed-battery \
  --print-freeze-hash
uv run python tools/quality/validation/run_layer2_s14_universality_battery.py \
  --repo-root . \
  --battery-root tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery \
  --allow-sealed-battery \
  --output _build/.tmp/production-quality/layer2_s14_universality_battery.json
uv run python -m json.tool architecture/policy_design_case/layer2_corpus_partition.json > /tmp/layer2_corpus_partition.json
```

Expected output:

- S14 sealed-runner repo-quality tests pass.
- W12D repo-quality tests pass.
- `--print-freeze-hash` prints a non-placeholder `sha256:<hex>` value that is
  not `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- The explicit runner exits `0`, reports `status=pass`, reports
  `sealed_battery_integrity_status=pass`, reports D4/oracle/breadth/baseline/
  grounded-authority/status-composition fields, and writes the output JSON.
- The runner output includes `substrate_reuse_refs` for
  `assurance_case.py`, `capability_ratchet.py`, S12 growth thermometer/ledger,
  S13 envelope revision/delta, and existing closeout status semantics.

Commit:

```bash
git add tools/quality/validation/run_layer2_s14_universality_battery.py \
  tools/quality/validation/run_universal_outcome_corpus.py \
  architecture/policy_design_case/layer2_corpus_partition.json \
  tests/repo_quality/tools/test_layer2_s14_universality_battery.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/fixtures/layer2/s14 \
  tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery
git commit -m "feat: run layer2 s14 universality battery"
```

## Task 5: S14 Manifest, Readiness Validator, Traceability, And Inventory

Create
`architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json`.

Manifest requirements:

- `slice == "S14"`.
- `schema_version == "policyos.policy_design_case.layer2_s14_universality_assurance_manifest.v1"`.
- `status == "active"`.
- `owner == "governance-board"`.
- `depends_on == ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "S11", "S12", "S13"]`.
- `slice_label == "evaluation_redesign_universality_assurance_battery"`.
- `cells_closed == []`.
- `layer_cells_advanced == ["DESIGNER_ITSELF.evaluation_corpus"]`.
- `expected_current_open_cell_count == 0`.
- `remaining_open_cells == []`.
- `burn_down_complete == true`.
- `floor_id == "s14_universality"`.
- `floor_metric == "per_axis_posture_thresholds_and_breadth_floor"`.
- Six implemented artifacts:
  - `SealedUniversalityBatteryRun`
  - `UniversalityAxisScorecard`
  - `MechanismGeneralityReport`
  - `SkepticDefeaterRecord`
  - `UniversalityClaimAssuranceCase`
  - `UniversalityClaimGateRecord`
- Supporting records, nested in the manifest and runner output:
  - `D4CorpusTrackCoverage`
  - `ExpertOracleBootstrapRecord`
  - `UniversalityBreadthFloorConfig`
  - `UniversalityBaselineComparison`
  - `GroundedAuthorityCoverageRecord`
  - `EvaluationStatusCompositionRecord`
  - `EnvelopeRevisionDynamicsRecord`
- The manifest should persist supporting-record refs, counts, statuses,
  required dimensions, and replay digests. It must not embed hidden sealed case
  payloads, gold labels, or private oracle notes.
- `substrate_reuse_refs` must include:
  - `src/polisyos/runtime/quality/assurance_case.py#build_universality_assurance_case`
  - `src/polisyos/runtime/quality/assurance_case.py#build_assurance_case_for_scorecard`
  - `src/polisyos/runtime/quality/capability_ratchet.py#build_capability_reality_report`
  - `src/polisyos/runtime/quality/design_axes/resource_economics.py#GrowthThermometerRecord`
  - `src/polisyos/runtime/quality/design_axes/resource_economics.py#EnvelopeGrowthLedger`
  - `src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py#EnvelopeRevision`
  - `src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py#CertifiedEnvelopeDelta`
  - existing closeout/status composition surfaces in `case_lifecycle.py`,
    `approval.py`, and scorecard/source-truth lattice semantics
- `skeptic_defeater_mapping` must map exactly:
  - `bespoke_disguise_defeater` -> `"This is bespoke in disguise."`
  - `confident_theater_defeater` -> `"It is confident theater."`
  - `failure_boundary_defeater` -> `"It does not know where it fails."`
  - `single_axis_universality_defeater` -> `"It is universal only on one axis."`
  - `frozen_once_defeater` -> `"It works once, then freezes."`
  - `first_call_defeater` -> `"Why call it first?"`
- Firewalls:
  - `universality_claim_firewall`
  - `held_out_integrity_firewall`
  - `sealed_battery_freeze_hash_replay`
  - `d4_breadth_floor_firewall`
  - `expert_oracle_bootstrap_firewall`
  - `grounded_authority_coverage_firewall`
  - `evaluation_status_composition_firewall`
  - `baseline_comparison_firewall`
  - `envelope_revision_dynamics_firewall`
  - `s9_faithfulness_required`
  - `no_aggregate_universal_number`
  - `no_production_authority_from_battery`
  - `no_gold_label_or_hidden_fixture_leakage`
- Surfaces:
  - public declared envelope and limitation note
  - expert D4 track/oracle/breadth/grounded-authority and per-axis scorecard
  - machine D4/supporting-record, replay, and freeze-hash refs
  - reviewer/governance skeptic-defeater view
- Closure metrics from this plan.

Readiness validator:

- Add `DEFAULT_S14_UNIVERSALITY_ASSURANCE_MANIFEST_PATH`.
- Add `S14_REQUIRED_ARTIFACTS`, `S14_REQUIRED_AUTHORITY_SCOPE`,
  `S14_REQUIRED_DENY`, `S14_FALSE_CLEAR_FIELDS`, `S14_SKEPTIC_DEFEATER_IDS`,
  and `S14_INVENTORY_ID`.
- Add `S14_REQUIRED_CORPUS_TRACKS`, `S14_REQUIRED_ORACLE_LAYERS`,
  `S14_REQUIRED_BREADTH_DIMENSIONS`, `S14_REQUIRED_GROUNDED_AUTHORITY_REF_TYPES`,
  `S14_REQUIRED_STATUS_COMPOSITION_CASES`, and `S14_REQUIRED_SUPPORTING_RECORDS`.
- Load `"s14_universality_assurance"` in `load_layer2_readiness_payloads`.
- Add `_validate_s14_universality_assurance` and call it from
  `validate_layer2_readiness_payloads` after S13 validation.
- Add S14 summary fields to the readiness summary.
- Migrate the exact prior future-S14 traceability guards deliberately:
  - `S9_LATER_SLICES = {"S14"}` in
    `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
    near current line `328` becomes `set()`. This unblocks both
    `layer2_s9_later_slice_maturity_invalid` and
    `layer2_s10_future_slice_maturity_invalid`.
  - The inline `{"S14"}` guard in `_validate_s11_predictive_knowledge` near
    current line `3544` becomes `set()`, unblocking
    `layer2_s11_future_slice_maturity_invalid`.
  - The inline `{"S14"}` guard in `_validate_s12_envelope_growth` near current
    line `3934` becomes `set()`, unblocking
    `layer2_s12_future_slice_maturity_invalid`.
  - Do not add range-style rejection logic for hypothetical later slices. S14 is
    the terminal Layer 2 slice in this roadmap. Keep authority rejection through
    deny lists, authority-boundary checks, and unscoped universal-claim checks.
- Migrate the exact prior inventory checks deliberately:
  - `_validate_s11_predictive_knowledge` near current line `3477`: change
    `not in {19, 20, 21}` to accept `22` after S14 registration, while S14 owns
    the exact `22` assertion.
  - `_validate_s12_envelope_growth` near current line `3877`: change
    `not in {20, 21}` to accept `22` after S14 registration, while S14 owns the
    exact `22` assertion.
  - `_validate_s13_post_deploy_accountability` near current line `4314`:
    change `!= 21` to accept `{21, 22}` or an equivalent conditional that
    accepts `22` only when the S14 manifest and S14 validator are present.
  - Leave the three `< 18` floor checks near current lines `2441`, `2724`, and
    `3067` unchanged.
- Validate no new closed cell and open-cell count `0`.
- Validate `DESIGNER_ITSELF.evaluation_corpus` remains implemented in the
  cluster map and its action mentions S14 sealed battery and universal-claim
  gate.
- Validate the six S14 artifacts are implemented exactly once in
  `layer2_artifact_traceability.toml`.
- Validate supporting records are present in the S14 manifest and runner output.
- Validate the manifest and runner output carry all required
  `substrate_reuse_refs`, and fail readiness if S14 omits the assurance-case,
  capability-ratchet, S12 thermometer/ledger, S13 envelope-revision, or
  existing status-lattice reuse refs.
- Validate all 19 D4 corpus tracks are present with minimum-label refs.
- Validate exactly four oracle layers are present and `weak_gold` plus
  `shadow_candidate_pool` are seed-only/non-authoritative.
- Validate breadth-floor dimensions include domain, jurisdiction, scale,
  epistemic regime, coupling regime, lifecycle, capacity, authority posture,
  instrument family, system dynamics, inter-rater/disagreement, and excluded
  domain fields.
- Validate grounded-authority refs include A-firewall, claim/evidence,
  value-choice, mandate/legitimacy, capacity, regime, coupling, and projection
  refs.
- Validate status-composition cases block or limit `weak_gold`,
  `shadow_candidate_pool`, `a_spec_gap`, `search_incomplete`,
  `bespoke_growth_detected`, and preserve `envelope_shrunk` as honest boundary
  revision through existing closeout/review/public-revalidation semantics.
- Validate the exact six skeptic-defeater ids map to the six architecture
  attacks, are projected from assurance-case defeaters, and that
  `held_out_integrity_firewall` is not counted as one of them.
- Validate `MechanismGeneralityReport` cites S12 `GrowthThermometerRecord`
  refs and materializes `held_out_status == "pending_s14"` without changing S12
  authority.
- Validate `EnvelopeRevisionDynamicsRecord` cites both S12 expansion ledger refs
  and S13 shrink/split or certified-delta refs for the `frozen_once_defeater`.
- Validate `UniversalityAxisScorecard` cites a capability-reality report ref and
  carries exactly 27 rows derived from current cluster-map cells.
- Validate baseline comparison includes bespoke-tool, raw-LLM, and expert-panel
  refs.
- Validate exact false-clear fields in nested and flat forms.
- Validate corpus partition freeze hash equals the S14 sealed-runner hash stored
  in the manifest and is no longer the empty-content hash.
- Validate inventory count `22`.
- Validate that implemented S14 artifacts are allowed only through the S14
  manifest and validator. Keep rejection for production authority,
  recommendation authority, preference learning, automated value learning, and
  unscoped universal claims.

Traceability:

- Add S14 entries to
  `architecture/policy_design_case/layer2_artifact_traceability.toml` with
  `maturity = "implemented"`.
- Keep traceability in the current minimal schema: `name`, `slice`, and
  `maturity`.
- Put exact artifact path bindings in the S14 manifest and in
  `tests/repo_quality/tools/test_policy_design_case_layer2_s14_universality_assurance.py`.

Cluster map:

- Update `DESIGNER_ITSELF.evaluation_corpus` action text to mention S14 D4
  corpus coverage, expert oracle bootstrap, breadth floor, sealed battery,
  grounded-authority coverage, per-axis scorecard, baseline comparison, and
  universal-claim gate.
- Do not reopen the cell.
- Preserve existing owner module and implemented status:
  - `owner_module = "src/polisyos/corpus"`
  - `ratchet_state = "implemented"`
  - `p01_chain = "implemented"`

Corpus partition validation:

- Validate that `sealed_universality_battery.freeze_hash` was already rotated
  in Task 4 to the actual hash computed by the S14 sealed-runner over the
  committed hidden battery fixtures.
- Preserve:
  - `path`
  - `extensible == false`
  - `access == "ci_gate_only"`
  - `owner == "governance-board"`
  - `integrity_rule == "development code and fixtures must not read the sealed battery path"`

Inventory:

- Add one S14 manifest entry.
- Layer 2 inventory count becomes `22`.
- `capability_reality_label == "implemented"`.
- Authority scope authorizes only S14 universality-claim gating, D4/breadth/
  oracle/grounded-authority/baseline/status-composition assurance surfaces, and
  battery assurance surfaces, not production or recommendation authority.

Execution steps:

- [ ] **Step 1: Create the S14 manifest** at
  `architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json`.
- [ ] **Step 2: Extend the readiness validator** with S14 constants, loader,
  validator call, manifest checks, supporting-record checks, exact skeptic
  mapping checks, corpus-partition hash checks, staged S14 guard updates, and
  inventory count migration from `21` to `22`.
- [ ] **Step 3: Update traceability, cluster map action text, and inventory**
  without reopening `DESIGNER_ITSELF.evaluation_corpus`; do not rotate the
  corpus-partition freeze hash here because Task 4 already did it.
- [ ] **Step 4: Add and run S14 repo-quality tests plus JSON/cluster/readiness
  validators**.
- [ ] **Step 5: Commit** `chore: register layer2 s14 universality assurance`.

Verification:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s14_universality_assurance.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run python -m json.tool architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json > /tmp/layer2_s14_manifest.json
uv run python -m json.tool architecture/policy_design_case/layer2_corpus_partition.json > /tmp/layer2_corpus_partition.json
uv run python -m json.tool architecture/policy_design_case/inventory.json > /tmp/pdc_inventory.json
```

Expected output:

- S14 repo-quality tests pass.
- Readiness validator passes and reports `current_open_cell_count=0`.
- Readiness validator reports `inventory_artifact_count=22`.
- Cluster map validator passes.
- JSON files parse cleanly.

Commit:

```bash
git add architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json \
  architecture/policy_design_case/layer2_artifact_traceability.toml \
  architecture/policy_design_case/cluster_ownership_map.toml \
  architecture/policy_design_case/inventory.json \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s14_universality_assurance.py
git commit -m "chore: register layer2 s14 universality assurance"
```

## Task 6: Repo-Quality Snapshots, S9 Positive Gate, And Inventory Confirmation

Update repo-quality snapshots after S14 is registered.

Required snapshot changes:

- Exact Layer 2 inventory count becomes `22`.
- S12 and S13 current-slice snapshot tests should accept post-S14 registration
  where they are scoped to prior manifests.
- S11 inventory-count guards that currently accept only pre-S14 counts should
  accept the post-S14 count only when the S14 manifest is present and valid.
- S14 owns the exact `22` count.
- Open-cell count remains `0`.
- `DESIGNER_ITSELF.evaluation_corpus` remains implemented and now documents
  S14 D4 corpus coverage, expert oracle bootstrap, breadth floor, sealed
  battery, grounded-authority coverage, baseline comparison, and
  universal-claim gate.
- S9 negative test for no S14 refs remains unchanged.
- Add a S9 positive test proving a scoped universal self-description is allowed
  only when passing S14 assurance refs are present, D4/breadth/oracle/
  grounded-authority/baseline/status-composition refs are visible, and the
  projection remains projection-only.
- No snapshot may claim production, recommendation, preference-learning,
  automated value-learning, or unscoped universal authority.

Regression checks:

- Capability ratchet still passes.
- Cluster ownership map still has no open Layer 2 cells.
- S14 sealed runner passes with explicit sealed access.
- W12D dev route emits S14 blocks without sealed access.
- D4 corpus/oracle/breadth, grounded-authority, baseline comparison, status
  composition, and exact six skeptic mappings remain visible in S14 readiness.
- Required substrate reuse refs for assurance case, capability reality, S12
  thermometers/ledgers, S13 envelope revisions, and existing status lattice
  remain visible in readiness and sealed-runner output.
- Public export redacts hidden sealed material.
- Public export redacts the exact S14 sealed/gold/oracle tokens named in Task 3.
- W12D S14 tests use the existing module-scoped W12D report fixture and do not
  add a second full W12D execution path.
- Architecture guardrails and runtime API contract remain green.
- Public-surface snapshot is regenerated or explicitly reviewed if
  `src/polisyos/runtime/quality/__init__.py` export changes cause drift.

Execution steps:

- [ ] **Step 1: Update prior exact-count snapshot tests** so S10/S11/S12/S13
  remain scoped and S14 owns exact `22`.
- [ ] **Step 2: Add S9 positive S14-ref gate regression** without removing the
  no-ref negative control.
- [ ] **Step 3: Run the repo-quality regression gate** listed below.
- [ ] **Step 4: Commit** `chore: confirm layer2 s14 universality regression`.

Verification:

```bash
cd policy-engine
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s14_universality_assurance.py \
  tests/repo_quality/tools/test_layer2_s14_universality_battery.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run polisyos-tools quality public-surface snapshot --all
uv run python tools/quality/validation/architecture_report_only_contracts.py --report generated-artifacts --fail-on-contract-errors
```

Expected output:

- All listed repo-quality tests pass.
- Open-cell count remains `0`.
- Inventory count is `22`.
- S14 sealed-runner tests prove explicit sealed access and dev no-access.
- Public-surface/generated-artifact checks either report no drift or the
  regenerated `architecture/public_surface/inventory.json` and
  `docs/reference/public-surface.md` are included in the commit.

Commit:

```bash
git add tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s14_universality_assurance.py \
  tests/repo_quality/tools/test_layer2_s14_universality_battery.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  architecture/policy_design_case/inventory.json \
  architecture/policy_design_case/cluster_ownership_map.toml \
  architecture/public_surface/inventory.json \
  docs/reference/public-surface.md
git commit -m "chore: confirm layer2 s14 universality regression"
```

## Task 7: Full S14 Verification Done When

Run the full S14 gate after Tasks 1-6 are committed.

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s14_universality_assurance.py -q
uv run pytest \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  -q
uv run pytest \
  tests/repo_quality/tools/test_layer2_s14_universality_battery.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s14_universality_assurance.py \
  tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  -q
uv run python tools/quality/validation/run_layer2_s14_universality_battery.py \
  --repo-root . \
  --battery-root tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery \
  --allow-sealed-battery \
  --output _build/.tmp/production-quality/layer2_s14_universality_battery.json
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run polisyos-tools architecture guardrails check
uv run polisyos-tools quality public-surface snapshot --all
uv run python tools/quality/validation/architecture_report_only_contracts.py --report generated-artifacts --fail-on-contract-errors
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
```

- [ ] **Step 1: Run the full S14 verification gate** exactly as listed above.
- [ ] **Step 2: Reopen the failure-pattern register and complete the closeout
  pattern check.**
- [ ] **Step 3: Only mark S14 complete when every Done When condition below is
  true.**

Done when all of the following are true:

- Red-first tests were committed before implementation.
- S14 runtime contracts are strict, typed, exported, and replayable.
- S14 public DTOs inherit `Layer2ReadinessModel`, and S14 authority boundaries
  reuse the existing `AuthorityBoundary` shape.
- Only the explicit S14 sealed-runner can read the sealed battery path.
- W12D dev route emits S14 dev-shadow blocks without reading hidden sealed
  fixtures.
- W12D S14 dev route does not call a generic all-fixture loader or traverse the
  sealed battery path, and it does not mark the sealed universal claim gate as
  `pass`.
- Corpus partition freeze hash matches the committed sealed battery fixtures.
- Freeze hash mismatch fails closed.
- D4 corpus-track coverage includes all 19 architecture tracks with
  minimum-label refs.
- Expert oracle bootstrap includes `weak_gold`, `expert_gold_seed`,
  `causal_support_seed`, and `shadow_candidate_pool`, with seed-only boundaries
  enforced.
- Breadth floor config names domain, jurisdiction/governance context, scale,
  epistemic-regime, coupling-regime, lifecycle, capacity, authority-posture,
  instrument-family, system-dynamics, inter-rater/disagreement, and excluded
  domain fields.
- Grounded-authority coverage requires A-firewall, claim/evidence,
  value-choice, mandate/legitimacy, capacity, regime, coupling, and projection
  refs for in-envelope claims.
- Baseline comparison covers bespoke tools, raw LLMs, and expert panels.
- Evaluation status composition blocks seed/gap/search/projection/bespoke labels
  from becoming universal authority and treats `envelope_shrunk` as honest
  boundary revision.
- Envelope revision dynamics requires reusable expansion and shrink on
  disconfirmation.
- Per-axis scorecard covers all 27 cluster cells.
- Untested axis combinations default out-of-envelope.
- No aggregate universal number is emitted or accepted as authority.
- Mechanism generality requires sublinear marginal bespoke cost.
- Bespoke one-off patches are visible and not counted as mechanism generality.
- All six skeptic defeaters match the architecture attacks exactly and pass.
- Held-out integrity is enforced as a firewall, not counted as one of the six
  skeptic defeaters.
- Bare universal self-description without S14 refs is blocked.
- Scoped universal claim with S14 assurance refs can pass only as
  projection-only claim wording over the declared envelope, with D4/breadth/
  oracle/grounded-authority/baseline/status-composition refs visible.
- S9 no-ref negative control remains in place.
- S14 positive S9/ref projection path is covered.
- Public, expert, and machine surfaces expose D4/breadth/oracle, grounded
  authority, baseline comparison, status composition, scorecard, envelope,
  limitation, freeze-hash, replay, and skeptic-defeater refs without leaking
  hidden content.
- Public export redacts hidden battery contents and gold labels.
- Public export redacts the exact S14 sealed/gold/oracle key and value tokens
  listed in Task 3.
- S14 cannot mint production, rollout, recommendation, approval, publication,
  closeout, claim, scorecard, preference-learning, or automated value-learning
  authority.
- W12D S14 false-clear counts are exact and zero.
- Sealed-runner S14 false-clear counts are exact and zero.
- Manifest declares six implemented S14 artifacts.
- Manifest declares the seven S14 supporting records and exact skeptic mapping.
- Inventory count is `22`.
- `current_open_cell_count == 0`.
- `DESIGNER_ITSELF.evaluation_corpus` remains implemented and advanced, not
  reopened.
- Architecture guardrails and runtime API contract checks pass.
- Public-surface/generated-artifact checks pass after S14 runtime-quality
  exports are added.

No additional commit is required for Task 7 unless verification forces a fix. If
a fix is needed, commit it with a precise message describing the verified
correction.

## Commit Sequence

Use this sequence unless a red/green split requires a smaller corrective commit:

1. `test: add layer2 s14 universality assurance red tests`
2. `feat: add layer2 s14 universality assurance contracts`
3. `feat: gate universal claims through s14 projections`
4. `feat: run layer2 s14 universality battery`
5. `chore: register layer2 s14 universality assurance`
6. `chore: confirm layer2 s14 universality regression`

Do not combine Task 1 with implementation. Do not claim S14 complete until Task
7 passes.

## Closeout Pattern Check

Before final response, reopen
`docs/reference/policy-design-case-failure-patterns.md` and verify:

- No contract-only capability remains for S14.
- No producer or bridge is missing.
- No S14 artifact is hidden from projection/public/expert/machine surfaces.
- Hidden sealed battery contents and gold labels remain hidden from dev and
  public export.
- S14 uses the existing corpus partition and S9 faithfulness surfaces rather
  than a parallel benchmark or projection framework.
- Universal claim status is gate-scoped and does not become a new production or
  closeout lattice.
- D4 corpus-track, expert-oracle, breadth-floor, baseline-comparison,
  grounded-authority, status-composition, and envelope-revision records are
  produced, persisted in S14 outputs, validated, and projected.
- Public projection carries S14 refs, statuses, limitation text, and redacted
  scorecard summaries, not full hidden battery cases or private oracle payloads.
- W12D dev-shadow code never uses generic hidden/all-fixture loading to read the
  sealed battery; sealed access stays inside the explicit S14 runner.
- `weak_gold` and `shadow_candidate_pool` remain seed authority and cannot define
  promotion floors or oracle truth.
- Grounded-authority refs are cited from A-side producers and are not minted by
  S14.
- Baseline comparison covers bespoke tools, raw LLMs, and expert panels.
- `envelope_expanded` and `envelope_shrunk` are replay-visible boundary changes,
  not silent universal-claim upgrades or failures.
- Rule version, freeze hash, threshold refs, and replay digest make the sealed
  run reproducible.
- Per-axis scorecard and hard-corner coverage prevent aggregate-number
  laundering.
- Untested axis combinations default out-of-envelope.
- Skeptic defeaters map exactly to the six target-architecture attacks, are
  visible, and all pass; held-out integrity remains a firewall, not a seventh or
  replacement defeater.
- False-clear counts are exact and zero.
- S14 does not claim production, recommendation, preference-learning,
  automated value-learning, claim, closeout, publication, approval, or rollout
  authority.

Final response should include:

- Plan path.
- Any files changed.
- Verification performed for the plan file itself.
- Reminder that implementation starts with Task 1 red tests.
