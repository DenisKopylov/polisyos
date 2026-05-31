---
title: PolicyOS Layer 2 S4 Epistemic-Regime Classifier (A-owned) + Commitment Profile Implementation Plan
status: active
owner: team-knowledge-regime
created: 2026-05-31
last_verified: null
stability: draft
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
slice: S4
slice_label: epistemic_regime_classifier_commitment_profile
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on: S3
---

# Layer 2 S4 Epistemic-Regime Classifier (A-owned) + Commitment Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make epistemic regime an **A-owned per-claim classification** that selects the design strategy and the admissible evidence, and land the thin reversibility/lifecycle/stakes commitment profile that regime strategy consumes. Prove the W12 over-blocking hypothesis is now *testable*: classify the 13 real-producer corpus cases by regime against expert labels and record — not assume — whether the 9 expert `publish-with-limitation` cases are uncertainty/ambiguity rather than risk.

**Architecture:** S4 builds the D2.5 regime classifier as a **gate-owned A-side producer** — the generator (B) may not pick its own uncertainty regime (P16). The classifier consumes the evidence the backbone can already supply (S3 substrate coverage, contested Scholar edges, the commitment profile's stakes/reversibility) and treats the not-yet-built signals (measurability=S6, calibration=S11, value provenance=S8) as **explicitly absent**, which — under the "default toward more uncertainty" invariant — caps the regime below risk until that evidence exists. Regime is per-claim; portfolio composition of regime (worst-regime-on-critical-path) is fenced to S5. The classifier emits an `EpistemicRegimeClaim` projected onto the `DesignRecordV0` as an `AxisPositionDeclaration` + `AxisFirewallStatus`, and the S2 shadow loop consumes the **injected** regime/strategy decision rather than computing it. S4 changes B's strategy selection at shadow/governed posture only; production floors and closeout honesty are untouched.

**Tech Stack:** Python 3.14, Pydantic v2 (strict `extra="forbid"` models), S0 contracts from `pdc._impl.layer2_readiness` (`EpistemicRegime`, `AxisPositionDeclaration`, `AxisFirewallStatus`, `CertifiedOperationEnvelope`, `AuthorityBoundary`, `ValueOfInformationEstimate`), S3 `SubstrateCoverageSnapshot`/`CapabilityBindingResult`, existing `runtime.quality.case_lifecycle`, existing Scholar contested-evidence seeds (by ref), `run_universal_outcome_corpus.py` route, pytest, existing `tools.quality.validation` validators.

---

## Scope

This task plan implements only roadmap slice S4.

It does **not** implement: S5 coupling/composition or portfolio-level regime composition, S6 measurability/blind-spot producers, S7 delegation, S8 value-choice provenance, S10 prediction, S11 rich predictive regime/calibration models, generative search beyond what S2 shipped, production claim authority, or public rollout authority. The classifier consumes S6/S8/S11 signals as **absent inputs** (which conservatively cap the regime); it does not build them.

Cells moved by S4 (cluster cells, **closed**):

- `KNOWLEDGE.epistemic_regime`: `contract_only -> implemented` (build_new; gate-owned per-claim regime classifier with P16 firewalls).
- `INTERVENTION.reversibility_lifecycle_stakes`: `contract_only -> implemented` (extend_existing `case_lifecycle`; reversibility/lifecycle-stage/stakes become first-class fields that change strategy and floors, with P23).

`INTERVENTION.reversibility_lifecycle_stakes` is **fully implemented** in S4 (the roadmap "(partial)" note is superseded by the authoritative slice→cell matrix `target_state = implemented`; no later slice re-opens this cell). "Full" means a **first-class producer**, not a thin field:

- `CommitmentProfileRecord` carries **all** the contract's dimensions — `reversibility` ∈ {reversible, pilotable, option_preserving, lock_in, irreversible}, `option_value`, `lifecycle_stage` ∈ {greenfield, reform, transition, termination, grandfathering, emergency, recovery}, `transition_cost`, `stakes` ∈ {low, high, catastrophic} (+ asymmetric error).
- `build_commitment_profile` is a **real producer**: it derives the profile from each case's signals (`domain`, `policy_instrument.instrument_type`, `intent.policy_time`, scale) with documented rules and a conservative default (unknown ⇒ irreversible/high/transition), and is **validated against expert gold** across all 13 cases (commitment-profile adequacy; Task 4).
- It **drives both strategy and floor selection** (`select_floor`), satisfying the cell's `acceptance_signal` ("design strategy **and floors** change when reversibility, lifecycle, or stakes profile changes"), with P23 as the floor-consistency firewall.
- `extend_existing` is honored: the producer lives in `case_lifecycle.py` (team-case-lifecycle's module) and its `transition`/`termination`/`grandfathering` lifecycle stages reuse `case_lifecycle`'s existing reissue/supersession/termination vocabulary (`build_lifecycle_reissue_report`, `ALLOWED_LIFECYCLE_EVENTS`) rather than duplicating lifecycle logic.
- Semantic + negative controls run on **real corpus cases** (catastrophic-irreversible: `w11a_india_aadhaar_dbt_2016`, `w11a_netherlands_room_for_river_2007`; reversible-emergency: `w11a_us_ppp_2020`, `w11a_eu_temporary_protection_ukraine_2022`), not synthetic toys only.

What is *not* in S4 (and is honest, not a hole in the cell): predictive transition-cost/option-value *modeling* (numeric forecasts) is S10/S11; here the bands are produced and validated, and floors/strategy are gated on them. The cell's closure contract is fully met, so it closes to `implemented`.

Open cell count delta:

- S0 baseline remains `17`.
- Current cluster-map open cell count becomes `13` after S4 (was `15` after S2/S3; S4 closes two cells).
- S4 records the closed cells in its own manifest and edits `cluster_ownership_map.toml` (flip both `[cell.*]` to `implemented`, remove both `[open_cell_closure.*]` entries), mirroring how S2 closed `INTERVENTION.design_grammar`/`INTERVENTION.design_candidate`.

A-leads-B / regime-shopping fence:

- The regime classifier is **A-side, gate-owned**. The B-side loop (`pdc._impl.layer2_design_search`) consumes an **injected** `EpistemicRegimeClaim` + selected strategy; it must not self-classify regime or override the A claim (P16, anti-P15).
- `false_risk` and `false_precaution` are both blocked (P16 both directions). A low-stakes evidence floor on a catastrophic/irreversible design is blocked (P23).
- **Regime sets evidence rules, not only strategy** (roadmap goal). Risk admissibility requires calibrated/identified evidence (`has_risk_evidence`); ignorance prohibits outcome claims (authority boundary); these admissible-evidence rules are part of the cell's closure, not a strategy-label-only change.

Cross-cutting tracks this slice touches (roadmap T0/T2/T3):

- **T0 (burn-down):** two cells close, `open_cell_count 15 → 13`; both validators stay the single progress meter.
- **T2 (adversarial-against-A):** the roadmap states S4 **raises** the standing adversarial-against-A obligation, because regime-conditional strategy is new search power. S4 adds the `false_risk`/`false_precaution` probes as the regime-specific contribution to that red-team track (it does not own the whole track).
- **T3 (replay/CI invariants):** the classifier is a pure, deterministic function of the recorded evidence basis — add a determinism/replay test (same evidence ⇒ identical claim) and confirm no new status lattice is introduced (regime and firewall reuse the S0 literals; `DesignStrategy` is a strategy vocabulary, not a status).

First proving case:

- The standing proving ground: the **13 W12 real-producer corpus cases** (`tests/fixtures/universal-corpus`; `runtime_useful_design_rate = 0/13`; 9 expert `publish-with-limitation`, 3 `semantic_pass`, 1 `false_pass`).
- Done = all 13 cases are classified by regime against expert gold labels; `regime_accuracy_with_asymmetric_false_risk_penalty` is computed and at/above floor; the W12 hypothesis result (how many of the 9 `publish-with-limitation` cases classify as uncertainty/ambiguity vs risk) is **recorded as confirmed or revised**, not pre-assumed. Production posture and `closeout_honesty_rate` are unchanged.

## Architecture Decision

S4 contracts live in `polisyos.runtime.quality`, not in `pdc` and not in `scientist`.

Reason: regime classification and the commitment profile are **A-side authority** concerns (the verifier owns regime; the generator may not). They sit alongside `capability_resolver`, `capability_index`, the S3 substrate/acquisition loop, and `case_lifecycle`. They are not B-side generation. The B-side narrow waist (`DesignRecordV0`, the S2 loop) **consumes** the regime as data.

Module placement:

- Create `src/polisyos/runtime/quality/layer2_epistemic_regime.py` (build_new; `KNOWLEDGE.epistemic_regime`, owner `team-knowledge-regime`): `EpistemicRegimeClaim`, `RegimeEvidenceBasis`, `classify_regime`, the P16 firewall helpers, `DesignStrategy` + `regime_design_strategy`, and `regime_accuracy`.
- Modify `src/polisyos/runtime/quality/case_lifecycle.py` (extend_existing; `INTERVENTION.reversibility_lifecycle_stakes`, owner `team-case-lifecycle`): add the strict `CommitmentProfileRecord`, the **first-class** `build_commitment_profile` producer (derives the profile from case signals — `domain`/`instrument_type`/`policy_time`/scale — with a conservative default), `select_floor(commitment) -> floor_band`, and the P23 helper `assert_stakes_floor_consistency`. Reuse the module's existing transition/termination/reissue vocabulary (`ALLOWED_LIFECYCLE_EVENTS`, `build_lifecycle_reissue_report`) for the `transition`/`termination`/`grandfathering` lifecycle stages rather than duplicating lifecycle logic. The regime module imports `CommitmentProfileRecord`, `build_commitment_profile`, and `select_floor` from `case_lifecycle` (regime + strategy + floor consume the commitment profile — the cluster bridge_consumer).

Reuse-first (no parallel regime store, no new candidate record):

- `pdc._impl.layer2_readiness`: `EpistemicRegime` literal (do **not** redefine the taxonomy), `AxisPositionDeclaration`, `AxisFirewallStatus` (`FirewallDisposition`), `CertifiedOperationEnvelope` (`epistemic_regime_scopes`), `AuthorityBoundary`, `ValueOfInformationEstimate`. The regime claim projects onto the `DesignRecordV0` as an `AxisPositionDeclaration` (`cluster="KNOWLEDGE"`, `axis="epistemic_regime"`) + `AxisFirewallStatus` (`cell_ref="KNOWLEDGE.epistemic_regime"`, P16); the commitment profile projects as `AxisPositionDeclaration` (`INTERVENTION.reversibility_lifecycle_stakes`) + `AxisFirewallStatus` (P23).
- `runtime.quality.layer2_substrate_acquisition` (S3): `SubstrateCoverageSnapshot` / `CapabilityBindingResult` status feed the regime evidence basis.
- Scholar contested-evidence seeds (`scholar/_impl/evidence.py`, `capability_white_space.py`) are read by **ref/count** for `contested_model` signal; S4 does not deepen Scholar.
- `pdc._impl.layer2_design_search` (S2): the loop gains regime/strategy fields and consumes the injected decision; the strategy STRING is produced A-side and passed in, so `pdc` does **not** import `runtime.quality` (dependency injection by the orchestration).

Import boundaries:

- `runtime.quality.layer2_epistemic_regime` may import `pdc._impl.layer2_readiness` contracts and `runtime.quality` siblings (`case_lifecycle`, `layer2_substrate_acquisition`); it must not import `scientist` or B-side search.
- `pdc._impl.layer2_design_search` must **not** import `runtime.quality`; it receives `regime: EpistemicRegime` (S0 literal) and `design_strategy: str` as injected inputs. This keeps A→B as data flow and avoids any import cycle (`layer2_readiness` stays a leaf).
- The classifier is deterministic in tests/replay; no live network and no LLM in the regime decision (P15: an LLM may propose a candidate, never the regime).

S4 public outputs:

- Regimes (reuse S0 `EpistemicRegime`): `risk`, `uncertainty`, `ambiguity`, `ignorance`, `contested_model`.
- P16 firewall dispositions (reuse S0 `FirewallDisposition`): `pass`, `limit`, `block` (overconfidence / precaution-laundering directions).
- Design strategies: `expected_welfare_optimization`, `robust_satisficing`, `frame_indexed_portfolio`, `precautionary_adaptive_pathway`.
- W12 hypothesis result: `confirmed` | `revised` (recorded over the 9 `publish-with-limitation` cases), with the per-case predicted/gold table.

S4 authority boundary:

- `authoritative_for`: `epistemic_regime_classification`, `regime_conditional_strategy_selection`, `commitment_profile`, `regime_accuracy_metric`.
- `may_not_use_for`: `risk_regime_authority_without_risk_evidence`, `b_side_regime_selection` (no regime-shopping), `outcome_claim_from_ignorance`, `low_stakes_floor_on_catastrophic_irreversible`, `production_claim_authority`, `rollout_authority`, `publication_authority`.

## Pattern Pass

Relevant failure patterns: `P01`, `P03`, `P04`, `P05`, `P10`, `P12`, `P13`, `P15`, `P16`, `P23`.

Existing risks found:

- The regime taxonomy is specified in architecture notes and the `EpistemicRegime` literal exists in S0, but **no gate-owned producer emits per-claim regime records** — `KNOWLEDGE.epistemic_regime` is `contract_only` / `producer_missing` (P01).
- A generator could pick the easiest regime to unlock optimization (regime-shopping), or downgrade to "uncertainty/precaution" to dodge a proof it could pass — both are P16 laundering directions.
- `INTERVENTION.reversibility_lifecycle_stakes` is `contract_only`: reversibility/lifecycle/stakes are architecture concepts, not first-class candidate fields with gates; a low-stakes evidence floor could be applied to a catastrophic irreversible design (P23).
- Classifying without recording the **evidence basis** turns regime into a setting, not a claim (P04/P10): "regime is a claim, not a setting."
- Pre-assuming the W12 over-blocking result (rather than computing it against expert labels) is a P10 adequacy failure and a P13 narrative shortcut.

Correct pattern:

- Regime is an **A-owned per-claim classification** with an explicit `RegimeEvidenceBasis` (substrate coverage, contested edges, stakes, and the **absence** of measurability/calibration/value provenance), an asymmetric error policy, and a recorded downgrade/upgrade reason and strategy consequence.
- P16 fires in both directions: no risk-regime authority without risk-regime evidence (overconfidence); no uncertainty/precaution downgrade when risk evidence was available (precaution-laundering).
- The commitment profile (`CommitmentProfileRecord`) is consumed by regime and strategy **before floors are selected**; P23 blocks a low-stakes floor on catastrophic/irreversible designs.
- Strategy is selected by the **A** regime + commitment profile and injected into the B loop; B records and conditions on it but never sets it.
- The 13-case regime result is computed against expert gold labels and recorded as confirmed/revised.

Missing capability labels before implementation:

- `producer_missing` for the S4 regime classifier and the commitment-profile producer.
- `artifact_missing` for `EpistemicRegimeClaim`, `RegimeEvidenceBasis`, `CommitmentProfileRecord`.
- `bridge_missing` for regime claim → `DesignRecordV0` axis position/firewall → S2 loop strategy selection, and commitment profile → regime/strategy.
- `surface_missing` for the regime + commitment posture in every audience projection (PUBLIC regime + honest limitation; EXPERT/MACHINE evidence basis + firewall decisions).
- `semantic_test_missing` for evidence-gated risk admissibility, both P16 directions, P23, regime→strategy mapping, the irreversible-high-stakes-under-ignorance route, regime accuracy with asymmetric penalty, and the 13-case W12 hypothesis record.

Acceptance signal:

- `KNOWLEDGE.epistemic_regime` and `INTERVENTION.reversibility_lifecycle_stakes` both move `contract_only -> implemented`; cluster-map open cell count drops `15 -> 13`.
- A per-claim `EpistemicRegimeClaim` is produced by the gate, carries its evidence basis and asymmetry penalty, and selects the design strategy; B consumes it and cannot regime-shop.
- `false_risk_probe` fails the overconfidence firewall; `false_precaution_probe` fails the precaution-laundering firewall; a low-stakes floor on a catastrophic irreversible design fails P23.
- All 13 corpus cases are classified; `regime_accuracy_with_asymmetric_false_risk_penalty >= floor`; the W12 hypothesis result is recorded (`confirmed`/`revised`) with the per-case table.
- Production-posture outcomes and `closeout_honesty_rate` are unchanged (regime changes B strategy at shadow/governed only).
- S4 manifest is registered in inventory; both validators stay green.

## Source Of Truth

| Concern | Source |
| --- | --- |
| Roadmap closure contract | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md#s4--epistemic-regime-classifier-a-owned` |
| Regime architecture (taxonomy, invariants, P16, W12 test) | `docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md` (D2.4, D2.5) |
| P16 / P23 firewalls | `docs/system-design-decisions/...gap.md` (Pattern Pass) + `docs/reference/policy-design-case-failure-patterns.md` |
| Shared S0 contracts | `src/polisyos/pdc/_impl/layer2_readiness.py` (`EpistemicRegime`, `AxisPositionDeclaration`, `AxisFirewallStatus`, `CertifiedOperationEnvelope`, `AuthorityBoundary`) |
| Commitment-profile seed (extend_existing) | `src/polisyos/runtime/quality/case_lifecycle.py` |
| S3 substrate signal | `src/polisyos/runtime/quality/layer2_substrate_acquisition.py` (`SubstrateCoverageSnapshot`, `CapabilityBindingResult`) |
| Contested-model seeds | `src/polisyos/scholar/_impl/evidence.py`, `src/polisyos/runtime/quality/capability_white_space.py` |
| B-side loop to wire | `src/polisyos/pdc/_impl/layer2_design_search.py` (`run_s2_shadow_design_loop`, `DesignCandidateV0`, `RefinementDecision`) |
| Slice cell assignments | `architecture/policy_design_case/layer2_slice_cell_matrix.toml` (S4: both cells → `implemented`) |
| Cluster closure contracts | `architecture/policy_design_case/cluster_ownership_map.toml` (`KNOWLEDGE.epistemic_regime`, `INTERVENTION.reversibility_lifecycle_stakes`) |
| Floor governance | `architecture/policy_design_case/layer2_floor_governance.toml#s4_regime_accuracy` (already registered in S0) |
| Artifact traceability | `architecture/policy_design_case/layer2_artifact_traceability.toml` (`EpistemicRegimeClaim`, `CommitmentProfileRecord` already registered) |
| Canonical corpus route + proving ground | `tools/quality/validation/run_universal_outcome_corpus.py`, `tests/fixtures/universal-corpus` |

## Files

Create:

- `src/polisyos/runtime/quality/layer2_epistemic_regime.py`
- `architecture/policy_design_case/layer2_s4_epistemic_regime_manifest.json`
- `tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
- `tests/fixtures/layer2/s4/s4_expert_labels.json` (13-case expert **regime + commitment-profile** gold; outcome gold is read from each corpus case's `expert_adjudication.case_label`, not duplicated here)
- `tests/fixtures/layer2/s4/false_risk_probe.json` (weak-evidence claim-of-risk negative control)
- `tests/fixtures/layer2/s4/false_precaution_probe.json` (evidence-rich downgrade negative control)

Modify:

- `src/polisyos/runtime/quality/case_lifecycle.py` (add `CommitmentProfileRecord` + `build_commitment_profile` + P23 `assert_stakes_floor_consistency`)
- `src/polisyos/runtime/quality/__init__.py` (export S4 contracts)
- `src/polisyos/pdc/_impl/layer2_design_search.py` (inject regime/strategy/commitment into `run_s2_shadow_design_loop`; make `_design_record` regime-driven — axis positions, P16/P23 firewalls, `epistemic_regime_scopes`, ledger refs, 4 audiences; widen `project_s2_design_search` audiences to PUBLIC/REVIEWER/EXPERT/MACHINE; condition `_refinement_decision` on strategy + commitment `stakes_band`; never self-classify)
- `tests/unit/pdc/test_layer2_s2_design_search.py` (add the four Task 3 loop/surface/refinement tests; existing tests stay green)
- `tools/quality/validation/run_universal_outcome_corpus.py` (classify 13 cases, gold compare, W12 hypothesis, regime accuracy; shadow/governed only)
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py` (load S4 manifest + `_validate_s4_epistemic_regime` + summary keys)
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py` (S4 regime corpus assertions; production unchanged)
- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py` (S4 readiness facts; **live count snapshots 15 → 13**; see Task 6)
- `architecture/policy_design_case/cluster_ownership_map.toml` (close both S4 cells)
- `architecture/policy_design_case/inventory.json` (register S4 manifest)

Modify — **prior-slice live-count snapshots that S4 invalidates** (closing two cells moves the live open count `15 → 13`; these tests hard-assert the live `15` and will go red unless updated — Task 6 Step 3):

- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py` (`summary["current_open_cell_count"]` `15 → 13`; the S2 *manifest* static fields `open_cell_count_baseline=17`/`expected_current_open_cell_count=15` are historical and stay).
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py` (`validation["summary"]["open_cell_count"]` `15 → 13`; the S3 manifest static `expected_current_open_cell_count=15` stays).
- `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py` (`open_cell_closure["open_cell_count"]` → 13). **Note: this assertion is already red on the current tree (`assert 15 == 17`) — S2/S3 closed cells but never updated it. S4 must set it to the live `13` and the fix should be called out, not silently bundled.**

Do not modify:

- `architecture/policy_design_case/layer2_floor_governance.toml` (`s4_regime_accuracy` already registered in S0).
- `architecture/policy_design_case/layer2_artifact_traceability.toml` (both S4 artifacts already registered by name; maturity is S0-governed, not slice-edited — same stance S2 took).
- `architecture/policy_design_case/layer2_slice_cell_matrix.toml` (S4 assignments + baseline are frozen).
- `architecture/policy_design_case/layer2_dependency_dag.json`.
- S1/S2/S3 **source** files. Only the prior-slice *snapshot tests* listed above are updated (a later slice closing a cell is the sanctioned reason to touch a prior slice's live-count assertion).

---

## Task 1: Red-First S4 Semantic And Negative Tests

**Files:**

- Create: `tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py`
- Create: `src/polisyos/runtime/quality/layer2_epistemic_regime.py` (empty/skeleton so import fails red on behavior, not syntax)

- [x] **Step 1: Write failing unit tests for the S4 contracts, classifier, and firewalls**

Create `tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py`:

```python
from __future__ import annotations

import pytest

# EpistemicRegime literal is REUSED from the S0 narrow waist, not redefined.
from polisyos.pdc._impl.layer2_readiness import (
    AxisFirewallStatus,
    AxisPositionDeclaration,
)
# CommitmentProfileRecord is the extend_existing reversibility/lifecycle/stakes record.
from polisyos.runtime.quality.case_lifecycle import (
    CommitmentProfileRecord,
    assert_stakes_floor_consistency,
    build_commitment_profile,
    select_floor,
)
from polisyos.runtime.quality.layer2_epistemic_regime import (
    EpistemicRegimeClaim,
    P16OverconfidenceError,
    P16PrecautionLaunderingError,
    P23StakesFloorError,
    RegimeEvidenceBasis,
    classify_regime,
    regime_accuracy,
    regime_claim_to_axis_position,
    regime_design_strategy,
)

RULE_REF = "repo://docs/adr/0174-policy-evidence-capability-graph.md"


def _risk_evidence() -> RegimeEvidenceBasis:
    # Full risk-regime evidence present: exact substrate, measurability, calibration.
    return RegimeEvidenceBasis(
        claim_ref="claim:credit_program_enrollment:effect",
        substrate_binding_status="selected_exact",
        measurability_present=True,
        calibration_present=True,
        contested_scholar_edges=0,
        value_provenance_present=True,
        rule_version_ref=RULE_REF,
    )


def _sparse_evidence() -> RegimeEvidenceBasis:
    # S6 measurability / S11 calibration / S8 value provenance not yet built => absent.
    # Proxy binding + no risk evidence => uncertainty.
    return RegimeEvidenceBasis(
        claim_ref="claim:regional_displacement_pressure:effect",
        substrate_binding_status="selected_proxy_with_limitation",
        measurability_present=False,
        calibration_present=False,
        contested_scholar_edges=0,
        value_provenance_present=False,
        rule_version_ref=RULE_REF,
    )


def _blocked_evidence() -> RegimeEvidenceBasis:
    # Construct not observed and no risk evidence => ignorance (outcomes/possibilities problematic).
    return RegimeEvidenceBasis(
        claim_ref="claim:novel_second_order_mechanism:effect",
        substrate_binding_status="blocked_construct_not_observed",
        measurability_present=False,
        calibration_present=False,
        contested_scholar_edges=0,
        value_provenance_present=False,
        rule_version_ref=RULE_REF,
    )


def _reversible_low_stakes() -> CommitmentProfileRecord:
    return build_commitment_profile(
        candidate_ref="cand:001",
        reversibility="reversible",
        option_value="high",
        lifecycle_stage="greenfield",
        transition_cost="low",
        stakes="low",
        rule_version_ref=RULE_REF,
    )


def _irreversible_catastrophic() -> CommitmentProfileRecord:
    return build_commitment_profile(
        candidate_ref="cand:002",
        reversibility="irreversible",
        option_value="none",
        lifecycle_stage="transition",
        transition_cost="high",
        stakes="catastrophic",
        rule_version_ref=RULE_REF,
    )


def test_epistemic_regime_claim_reuses_s0_regime_literal() -> None:
    claim = classify_regime(_risk_evidence(), _reversible_low_stakes())
    assert claim.regime in {"risk", "uncertainty", "ambiguity", "ignorance", "contested_model"}
    assert claim.evidence_basis.claim_ref  # regime is a claim, not a setting


def test_risk_requires_risk_evidence() -> None:
    # Full evidence + reversible/low-stakes => risk admissible.
    claim = classify_regime(_risk_evidence(), _reversible_low_stakes())
    assert claim.regime == "risk"
    assert claim.firewall_disposition == "pass"


def test_sparse_evidence_defaults_toward_uncertainty_not_risk() -> None:
    # Absent measurability/calibration/value provenance => cannot be risk (default to more uncertainty).
    claim = classify_regime(_sparse_evidence(), _reversible_low_stakes())
    assert claim.regime in {"uncertainty", "ambiguity", "ignorance", "contested_model"}
    assert claim.regime != "risk"


def test_p16_overconfidence_blocks_claimed_risk_without_evidence() -> None:
    # false_risk: declare risk with weak evidence => overconfidence firewall fails closed.
    with pytest.raises(P16OverconfidenceError, match="risk-regime authority without risk-regime evidence"):
        classify_regime(_sparse_evidence(), _reversible_low_stakes(), declared_regime="risk")


def test_p16_precaution_laundering_blocks_downgrade_when_evidence_available() -> None:
    # false_precaution: risk evidence available, but a downgrade to uncertainty is attempted.
    with pytest.raises(P16PrecautionLaunderingError, match="risk-regime evidence was available"):
        classify_regime(_risk_evidence(), _reversible_low_stakes(), declared_regime="uncertainty")


def test_b_side_may_not_regime_shop() -> None:
    # A generator-preferred regime cannot override the A claim; only A classifies.
    claim = classify_regime(_sparse_evidence(), _reversible_low_stakes())
    assert claim.classified_by == "A_gate"
    assert claim.b_side_preference_honored is False


def test_regime_strategy_mapping() -> None:
    assert regime_design_strategy("risk", _reversible_low_stakes()) == "expected_welfare_optimization"
    assert regime_design_strategy("uncertainty", _reversible_low_stakes()) == "robust_satisficing"
    assert regime_design_strategy("ambiguity", _reversible_low_stakes()) == "frame_indexed_portfolio"
    assert regime_design_strategy("ignorance", _reversible_low_stakes()) == "precautionary_adaptive_pathway"


def test_irreversible_high_stakes_under_ignorance_routes_to_precaution() -> None:
    # Cluster semantic_test: irreversible high-stakes + ignorance => precaution, never risk optimization.
    strategy = regime_design_strategy("ignorance", _irreversible_catastrophic())
    assert strategy == "precautionary_adaptive_pathway"


def test_commitment_profile_overrides_strategy_for_catastrophic_irreversible() -> None:
    # Even a "risk" regime cannot drive point optimization on a catastrophic irreversible commitment.
    strategy = regime_design_strategy("risk", _irreversible_catastrophic())
    assert strategy in {"robust_satisficing", "precautionary_adaptive_pathway"}
    assert strategy != "expected_welfare_optimization"


def test_p23_low_stakes_floor_on_catastrophic_irreversible_fails() -> None:
    with pytest.raises(P23StakesFloorError, match="low-stakes floor"):
        assert_stakes_floor_consistency(_irreversible_catastrophic(), selected_floor="low_stakes")


def test_commitment_profile_derives_from_domain_signals() -> None:
    # First-class producer: domain drives the baseline (no explicit reversibility/stakes given).
    climate = build_commitment_profile(
        candidate_ref="c1", rule_version_ref=RULE_REF, domain="climate_adaptation"
    )
    assert (climate.reversibility, climate.stakes) == ("irreversible", "catastrophic")
    credit = build_commitment_profile(
        candidate_ref="c2", rule_version_ref=RULE_REF, domain="msme_credit_grant", policy_time="2022"
    )
    assert (credit.reversibility, credit.lifecycle_stage) == ("pilotable", "emergency")
    unknown = build_commitment_profile(candidate_ref="c3", rule_version_ref=RULE_REF, domain="???")
    assert unknown.reversibility == "irreversible"  # conservative default


def test_commitment_annotation_gold_overrides_derivation() -> None:
    prof = build_commitment_profile(
        candidate_ref="c4", rule_version_ref=RULE_REF, domain="msme_credit_grant",
        annotation={"reversibility": "irreversible", "stakes": "catastrophic"},
    )
    assert (prof.reversibility, prof.stakes) == ("irreversible", "catastrophic")


def test_select_floor_tracks_commitment_profile() -> None:
    assert select_floor(_irreversible_catastrophic()) == "high_stakes"
    assert select_floor(_reversible_low_stakes()) == "low_stakes"


def test_blocked_construct_classifies_as_ignorance_with_no_outcome_claims() -> None:
    # Deterministic ignorance (not a vacuous `if`): blocked construct + no risk evidence.
    claim = classify_regime(_blocked_evidence(), _irreversible_catastrophic())
    assert claim.regime == "ignorance"
    # Ignorance carries process/precaution properties only; outcome claims prohibited (D2.5).
    assert "outcome_claim" in " ".join(claim.authority_boundary.may_not_use_for)
    # End-to-end: classify -> strategy is precautionary, not point optimization.
    assert claim.strategy_consequence == "precautionary_adaptive_pathway"


def test_regime_accuracy_penalizes_false_risk_more_than_false_caution() -> None:
    # predicted vs gold; false-risk (predict risk, gold uncertainty) >> false-caution penalty.
    false_risk = regime_accuracy(predicted=["risk"], gold=["uncertainty"])
    false_caution = regime_accuracy(predicted=["uncertainty"], gold=["risk"])
    assert false_risk["penalized_score"] < false_caution["penalized_score"]
    assert false_risk["false_risk_count"] == 1
    assert false_caution["false_risk_count"] == 0


def test_regime_claim_projects_to_axis_position_and_firewall_status() -> None:
    claim = classify_regime(_sparse_evidence(), _reversible_low_stakes())
    pos, fw = regime_claim_to_axis_position(claim)
    assert isinstance(pos, AxisPositionDeclaration) and pos.cell_ref == "KNOWLEDGE.epistemic_regime"
    assert isinstance(fw, AxisFirewallStatus) and "P16" in fw.pattern_ids


def test_classifier_is_deterministic_replay_safe() -> None:
    # T3: regime is a pure function of the recorded evidence basis (same in => same out).
    a = classify_regime(_sparse_evidence(), _reversible_low_stakes())
    b = classify_regime(_sparse_evidence(), _reversible_low_stakes())
    assert a.model_dump() == b.model_dump()


def test_frame_plurality_yields_ambiguity_and_frame_indexed_strategy() -> None:
    # Ambiguity is reachable only with an explicit frame-plurality signal (reliable detection is S8).
    evidence = _sparse_evidence().model_copy(update={"frame_plurality": True})
    claim = classify_regime(evidence, _reversible_low_stakes())
    assert claim.regime == "ambiguity"
    assert claim.strategy_consequence == "frame_indexed_portfolio"
```

- [x] **Step 2: Run the tests and verify they fail red**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py -q
```

Expected: `ImportError`/`AttributeError` for the not-yet-implemented contracts, classifier, firewalls, and helpers.

## Task 2: Regime Contracts, Classifier, And P16/P23 Firewalls

**Files:**

- Modify: `src/polisyos/runtime/quality/case_lifecycle.py`
- Modify: `src/polisyos/runtime/quality/layer2_epistemic_regime.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`

- [x] **Step 1: Add the commitment-profile producer to `case_lifecycle` (extend_existing, P23)**

In `src/polisyos/runtime/quality/case_lifecycle.py`, add a strict (`extra="forbid"`) `CommitmentProfileRecord` plus a `build_commitment_profile(...)` producer and the P23 helper. Reuse the module's existing transition/termination/reissue vocabulary for `lifecycle_stage` validation; do not duplicate lifecycle logic.

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.pdc._impl.layer2_readiness import AuthorityBoundary

Reversibility = Literal["reversible", "pilotable", "option_preserving", "lock_in", "irreversible"]
LifecycleStage = Literal[
    "greenfield", "reform", "transition", "termination", "grandfathering", "emergency", "recovery"
]
StakesBand = Literal["low", "high", "catastrophic"]

_COMMITMENT_SCHEMA = "policyos.runtime.policy_design_case.commitment_profile.v1"
_HARD_COMMITMENT = {"lock_in", "irreversible"}


class CommitmentProfileRecord(BaseModel):
    """Reversibility / option-value / lifecycle-stage / transition-cost / stakes for a candidate.

    Consumed by KNOWLEDGE.epistemic_regime and INTERVENTION.design_strategy *before* floors
    are selected (cluster bridge_consumer). Extends case_lifecycle; not a parallel store.
    """

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[
        "policyos.runtime.policy_design_case.commitment_profile.v1"
    ] = _COMMITMENT_SCHEMA
    candidate_ref: str = Field(min_length=1)
    reversibility: Reversibility
    option_value: Literal["none", "low", "medium", "high"]
    lifecycle_stage: LifecycleStage
    transition_cost: Literal["low", "medium", "high"]
    stakes: StakesBand
    rule_version_ref: str = Field(min_length=1)

    @property
    def is_high_commitment(self) -> bool:
        return self.reversibility in _HARD_COMMITMENT and self.stakes in {"high", "catastrophic"}


# --- First-class commitment-profile producer (derives from case signals; gold can override) ---

# domain -> (reversibility, stakes, default lifecycle_stage). Conservative; an explicit annotation
# (expert gold) wins when the corpus route passes one. Tune against tests/fixtures/layer2/s4 gold.
_DOMAIN_COMMITMENT_BASELINE: dict[str, tuple[Reversibility, StakesBand, LifecycleStage]] = {
    "climate_adaptation": ("irreversible", "catastrophic", "transition"),
    "digital_public_service": ("lock_in", "catastrophic", "reform"),
    "housing_rent_control": ("lock_in", "high", "reform"),
    "education_access": ("lock_in", "high", "reform"),
    "infrastructure_prioritisation": ("irreversible", "high", "reform"),
    "public_health_intervention": ("reversible", "high", "reform"),
    "public_safety": ("reversible", "high", "reform"),
    "tax_enforcement": ("reversible", "high", "reform"),
    "labour_activation": ("reversible", "high", "reform"),
    "social_protection_targeting": ("pilotable", "high", "emergency"),
    "migration_displacement": ("pilotable", "high", "emergency"),
    "msme_credit_grant": ("pilotable", "high", "emergency"),
}
# Unknown domain => cautious direction (mirrors "default toward more uncertainty/coupling").
_DEFAULT_COMMITMENT: tuple[Reversibility, StakesBand, LifecycleStage] = ("irreversible", "high", "transition")
_EMERGENCY_TIME_HINTS = ("emergency", "2020", "2022")  # crisis-era instruments lean emergency/pilotable


def build_commitment_profile(
    *,
    candidate_ref: str,
    rule_version_ref: str,
    domain: str | None = None,
    instrument_type: str | None = None,
    policy_time: str | None = None,
    annotation: dict[str, str] | None = None,
    **overrides: str,
) -> CommitmentProfileRecord:
    """Derive a commitment profile from case signals; an explicit annotation/override wins.

    The annotation (expert gold from tests/fixtures/layer2/s4/s4_expert_labels.json) is the
    authoritative producer input when present; otherwise the domain/time heuristic applies,
    defaulting conservatively. transition/termination/grandfathering stages defer to
    case_lifecycle's reissue/supersession vocabulary (extend_existing).
    """
    rev, stakes, stage = _DOMAIN_COMMITMENT_BASELINE.get(domain or "", _DEFAULT_COMMITMENT)
    if policy_time and any(h in policy_time for h in _EMERGENCY_TIME_HINTS) and stage == "transition":
        stage = "emergency"
    fields: dict[str, str] = {
        "candidate_ref": candidate_ref,
        "reversibility": rev,
        "option_value": "low" if rev in _HARD_COMMITMENT else "medium",
        "lifecycle_stage": stage,
        "transition_cost": "high" if rev in _HARD_COMMITMENT else "medium",
        "stakes": stakes,
        "rule_version_ref": rule_version_ref,
    }
    fields.update({k: v for k, v in (annotation or {}).items() if k in fields})
    fields.update(overrides)
    return CommitmentProfileRecord(**fields)  # type: ignore[arg-type]


def select_floor(profile: CommitmentProfileRecord) -> Literal["low_stakes", "standard", "high_stakes"]:
    """Floors change with the commitment profile (the cell's acceptance signal)."""
    if profile.stakes == "catastrophic" or profile.is_high_commitment:
        return "high_stakes"
    if profile.stakes == "high":
        return "standard"
    return "low_stakes"


class P23StakesFloorError(ValueError):
    """Low-stakes/reversible floor applied to a high-stakes irreversible commitment."""


def assert_stakes_floor_consistency(profile: CommitmentProfileRecord, *, selected_floor: str) -> None:
    if profile.stakes == "catastrophic" and profile.reversibility in _HARD_COMMITMENT and selected_floor == "low_stakes":
        raise P23StakesFloorError(
            "low-stakes floor cannot be applied to a catastrophic irreversible commitment (P23)"
        )
```

- [x] **Step 2: Implement the A-owned regime classifier, P16 firewalls, strategy, and accuracy**

In `src/polisyos/runtime/quality/layer2_epistemic_regime.py` define strict models and the gate-owned classifier, reusing the S0 `EpistemicRegime` literal and `AxisPositionDeclaration`/`AxisFirewallStatus`.

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.pdc._impl.layer2_readiness import (
    AuthorityBoundary,
    AxisFirewallStatus,
    AxisPositionDeclaration,
    EpistemicRegime,
)
from polisyos.runtime.quality.case_lifecycle import CommitmentProfileRecord

_SCHEMA = "policyos.policy_design_case.layer2_s4_epistemic_regime.v1"

DesignStrategy = Literal[
    "expected_welfare_optimization",   # risk
    "robust_satisficing",              # uncertainty
    "frame_indexed_portfolio",         # ambiguity
    "precautionary_adaptive_pathway",  # ignorance / catastrophic irreversible
]

_EXACT = {"selected_exact", "selected_derived"}


class P16OverconfidenceError(ValueError):
    """Risk-regime authority claimed without risk-regime evidence (P16 upgrade direction)."""


class P16PrecautionLaunderingError(ValueError):
    """Uncertainty/precaution downgrade when risk-regime evidence was available (P16 downgrade)."""


class _S4Model(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[
        "policyos.policy_design_case.layer2_s4_epistemic_regime.v1"
    ] = _SCHEMA


class RegimeEvidenceBasis(_S4Model):
    """The evidence that makes regime a *claim, not a setting* (D2.5 invariant 1).

    D2.5 lists the regime evidence as: substrate coverage, transport/method boundary
    conditions, model contestability, precedent, expert disagreement, and validated
    (calibrated) models. Each is a distinct signal here — not collapsed into one proxy —
    so the recorded basis is auditable. Signals owned by later slices (measurability=S6,
    calibration=S11, value/frame provenance=S8) are represented as explicitly ABSENT,
    which conservatively caps the regime below risk and below ambiguity until they exist.
    """

    claim_ref: str = Field(min_length=1)
    substrate_binding_status: str                      # from S3 CapabilityBindingResult.status
    measurability_present: bool                        # SYSTEM.measurability (S6) — absent until then
    calibration_present: bool                          # KNOWLEDGE.calibration (S11) — absent until then
    method_boundary_conditions_met: bool | None = None # transport/method boundary (Scholar/method seeds)
    precedent_strength: Literal["none", "weak", "strong"] = "none"
    expert_disagreement: Literal["none", "some", "high"] = "none"
    contested_scholar_edges: int = Field(ge=0, default=0)
    robustness_sensitivity_available: bool = False     # robustness/sensitivity ingredients (Foundry/IR)
    value_provenance_present: bool = False             # ACTOR.value_choice_provenance (S8) — absent until then
    frame_plurality: bool = False                      # plural incommensurable frames => ambiguity (needs S8)
    rule_version_ref: str = Field(min_length=1)

    @property
    def has_risk_evidence(self) -> bool:
        # Risk requires an exact/derived binding AND measurability AND calibration AND, when
        # known, satisfied transport/method boundary conditions.
        return (
            self.substrate_binding_status in _EXACT
            and self.measurability_present
            and self.calibration_present
            and self.method_boundary_conditions_met is not False
        )


class EpistemicRegimeClaim(_S4Model):
    claim_ref: str = Field(min_length=1)
    regime: EpistemicRegime
    evidence_basis: RegimeEvidenceBasis
    firewall_disposition: Literal["pass", "limit", "block"]
    asymmetry_penalty: float = Field(ge=0.0)     # false-risk penalty weight applied
    decision_reason: str = Field(min_length=1)   # downgrade/upgrade reason
    strategy_consequence: DesignStrategy
    classified_by: Literal["A_gate"] = "A_gate"  # never B
    b_side_preference_honored: bool = False
    authority_boundary: AuthorityBoundary


def regime_design_strategy(regime: EpistemicRegime, commitment: CommitmentProfileRecord) -> DesignStrategy:
    # Commitment profile dominates: a catastrophic irreversible commitment never gets point optimization.
    if commitment.stakes == "catastrophic" and commitment.reversibility in {"lock_in", "irreversible"}:
        return "precautionary_adaptive_pathway"
    if regime == "ignorance":
        return "precautionary_adaptive_pathway"
    if regime == "ambiguity":
        return "frame_indexed_portfolio"
    if regime in {"uncertainty", "contested_model"}:
        return "robust_satisficing"
    # regime == "risk": still down-shift if the commitment is high.
    if commitment.is_high_commitment:
        return "robust_satisficing"
    return "expected_welfare_optimization"


def classify_regime(
    evidence: RegimeEvidenceBasis,
    commitment: CommitmentProfileRecord,
    *,
    declared_regime: EpistemicRegime | None = None,
) -> EpistemicRegimeClaim:
    """A-owned per-claim regime classification with both P16 firewalls.

    - Overconfidence: declaring risk without risk evidence fails closed.
    - Precaution-laundering: downgrading away from risk when risk evidence exists fails closed.
    - Default: when risk evidence is absent, never classify as risk (err toward more uncertainty).
    """
    if declared_regime == "risk" and not evidence.has_risk_evidence:
        raise P16OverconfidenceError(
            "cannot claim risk-regime authority without risk-regime evidence"
        )
    if (
        declared_regime in {"uncertainty", "ignorance"}
        and evidence.has_risk_evidence
    ):
        raise P16PrecautionLaunderingError(
            "cannot downgrade to uncertainty/precaution when risk-regime evidence was available"
        )

    if evidence.has_risk_evidence:
        regime: EpistemicRegime = "risk"
        disposition, penalty = "pass", 0.0
        reason = "exact substrate + measurability + calibration + boundary conditions present"
    elif evidence.frame_plurality:
        # Probabilities may be tractable, but outcomes/possibilities are problematic due to
        # plural incommensurable frames/values. Detecting this reliably needs S8 value
        # provenance; at S4 it fires only when frame_plurality is explicitly asserted.
        regime, disposition, penalty = "ambiguity", "limit", 1.0
        reason = "plural incommensurable frames; no single best design without authorized value input"
    elif evidence.contested_scholar_edges > 0 or evidence.expert_disagreement == "high":
        regime, disposition, penalty = "contested_model", "limit", 1.0
        reason = "models materially disputed (contested Scholar edges / high expert disagreement)"
    elif evidence.substrate_binding_status in {"blocked_construct_not_observed", "blocked_acquisition_required"}:
        regime, disposition, penalty = "ignorance", "limit", 2.0
        reason = "construct not observed and no risk-regime evidence: outcomes/possibilities problematic"
    else:
        regime, disposition, penalty = "uncertainty", "limit", 1.0
        reason = "proxy/partial evidence only; risk-regime evidence (measurability/calibration) absent"

    boundary = AuthorityBoundary(
        authoritative_for=["epistemic_regime_classification"],
        may_not_use_for=(
            ["outcome_claim", "risk_regime_authority", "production_claim_authority"]
            if regime == "ignorance"
            else ["risk_regime_authority", "production_claim_authority"]
        ),
        source_authority="regime_gate",
        posture="governed",
        rule_version_refs=[evidence.rule_version_ref],
    )
    return EpistemicRegimeClaim(
        claim_ref=evidence.claim_ref,
        regime=regime,
        evidence_basis=evidence,
        firewall_disposition=disposition,
        asymmetry_penalty=penalty,
        decision_reason=reason,
        strategy_consequence=regime_design_strategy(regime, commitment),
        authority_boundary=boundary,
    )


def regime_claim_to_axis_position(
    claim: EpistemicRegimeClaim,
) -> tuple[AxisPositionDeclaration, AxisFirewallStatus]:
    pos = AxisPositionDeclaration(
        cluster="KNOWLEDGE",
        axis="epistemic_regime",
        position=claim.regime,
        evidence_refs=[claim.evidence_basis.claim_ref],
        authority_purpose="design_strategy_selection",
        rule_version_ref=claim.evidence_basis.rule_version_ref,
    )
    fw = AxisFirewallStatus(
        cell_ref="KNOWLEDGE.epistemic_regime",
        status="pass" if claim.firewall_disposition == "pass" else "limit",
        pattern_ids=["P16"],
        reason=claim.decision_reason,
        rule_version_ref=claim.evidence_basis.rule_version_ref,
    )
    return pos, fw


# Asymmetric penalty weights: false-risk is more dangerous than false-caution.
_FALSE_RISK_WEIGHT = 3.0
_FALSE_CAUTION_WEIGHT = 1.0
_NON_RISK = {"uncertainty", "ambiguity", "ignorance", "contested_model"}


def regime_accuracy(*, predicted: list[str], gold: list[str]) -> dict[str, float | int]:
    assert len(predicted) == len(gold)
    correct = sum(1 for p, g in zip(predicted, gold) if p == g)
    false_risk = sum(1 for p, g in zip(predicted, gold) if p == "risk" and g in _NON_RISK)
    false_caution = sum(1 for p, g in zip(predicted, gold) if p in _NON_RISK and g == "risk")
    n = len(gold) or 1
    accuracy = correct / n
    penalized = accuracy - (_FALSE_RISK_WEIGHT * false_risk + _FALSE_CAUTION_WEIGHT * false_caution) / n
    return {
        "accuracy": accuracy,
        "false_risk_count": false_risk,
        "false_caution_count": false_caution,
        "penalized_score": penalized,
    }
```

Export the new contracts from `src/polisyos/runtime/quality/__init__.py` (`EpistemicRegimeClaim`, `RegimeEvidenceBasis`, `classify_regime`, `regime_design_strategy`, `regime_accuracy`, `regime_claim_to_axis_position`, `DesignStrategy`, `CommitmentProfileRecord`, `build_commitment_profile`, `assert_stakes_floor_consistency`, the three error types).

- [x] **Step 3: Re-run unit tests — all green**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py -q
```

Expected: all pass, including the P16 both-direction, P23, strategy-mapping, irreversible-under-ignorance, and asymmetric-penalty tests.

## Task 3: Inject Regime/Strategy Into The B-Side Shadow Loop (A-classifies-not-B)

**Files:**

- Modify: `src/polisyos/pdc/_impl/layer2_design_search.py`
- Modify: `tests/unit/pdc/test_layer2_s2_design_search.py`

**Code reality this task is grounded in (verified against `layer2_design_search.py`):**

- The loop already **builds a full `DesignRecordV0`** via `_design_record(input, candidate, ledger, boundary)` (called at line ~342) and returns it on `Layer2S2DesignSearchRun.design_record`. S4 threads regime/commitment **into that existing builder** — it invents no new record path.
- `_design_record` currently **hard-codes** the five sites S4 must make regime-driven:
  - `envelope.epistemic_regime_scopes = ["ignorance"]` → set from the injected regime;
  - `axis_positions = [INTERVENTION.design_grammar, INTERVENTION.design_candidate]` → append `KNOWLEDGE.epistemic_regime` + `INTERVENTION.reversibility_lifecycle_stakes`;
  - `firewall_status = [… P10/P15, P05/P25 …]` → append P16 (regime) + P23 (commitment);
  - `ledger_refs = [ledger.ledger_ref]` → append the regime-claim + commitment-profile refs;
  - `projection_audiences = ["MACHINE", "REVIEWER"]` → widen to the four audiences.
- `DesignCandidateV0` and `RefinementDecision` are `extra="forbid"` (`Layer2ReadinessModel`) — new fields are declared, not smuggled. `RefinementDecision` already carries `stakes_band: Literal["low","moderate","high","high_stakes"]`, hard-coded `"moderate"` in `_refinement_decision` (line ~633).
- `project_s2_design_search` (line ~374) types `audiences: tuple[Literal["MACHINE", "REVIEWER"], ...]` and renders one audience-agnostic dict — S4 widens the Literal and adds per-audience regime depth.
- **Scope nuance:** the corpus route runs this loop **only for the pinned case** — `_s2_design_search_summary` returns early for any `case_id != "ua-msme-affordable-loans-2022"` (line ~805). So Task 3's injection lands on that one case's `DesignRecordV0` (the case where B actually searches). The regime classification + surface for **all 13** cases is the corpus `s4_epistemic_regime` block (Task 4), whose persistence/surface home is the corpus report, not a per-case `DesignRecordV0`. Task 3 is the *design-loop* integration; Task 4 is the *proving-ground* classification. Both persist + surface the regime, in their respective homes.
- Import boundary holds: `pdc` imports only the S0 `EpistemicRegime` literal from `.layer2_readiness` (already imported, lines 14-23); `design_strategy` stays `str`; no `runtime.quality` import (values are injected by the orchestration).

- [x] **Step 1: Add regime/strategy/commitment fields and thread the injection (loop never self-classifies)**

- Add to `DesignCandidateV0` (after `status`): `regime: EpistemicRegime | None = None`, `design_strategy: str | None = None`, `commitment_profile_ref: str | None = None`, `commitment_stakes: Literal["low", "high", "catastrophic"] | None = None`. Optional defaults keep `_validate_grammar_first` and every current S2 caller valid.
- Extend `run_s2_shadow_design_loop` with injected, A-owned kwargs and thread them to `_candidate`, `_refinement_decision`, and `_design_record`:

```python
def run_s2_shadow_design_loop(
    input: Layer2S2DesignSearchInput,
    *,
    regime: EpistemicRegime | None = None,      # injected by orchestration; A classifies, not B
    design_strategy: str | None = None,          # a DesignStrategy value; typed str to avoid importing runtime.quality
    regime_claim_ref: str | None = None,         # ledger ref to the persisted EpistemicRegimeClaim
    commitment_profile_ref: str | None = None,   # ledger ref to the persisted CommitmentProfileRecord
    commitment_stakes: str | None = None,        # "low"|"high"|"catastrophic" for stakes_band + P23
) -> Layer2S2DesignSearchRun:
```

- P15/P16 fence: the loop **must not** classify or default regime. `regime is None` ⇒ the legacy pure-S2 behavior (byte-for-byte unchanged). A non-`risk` injected regime ⇒ no point-optimization refinement (Step 4). Record `regime`/`design_strategy`/`commitment_profile_ref` on the candidate so refinement and the record read them.

- [x] **Step 2: Make `_design_record` regime-driven (the persist + index bridge)**

Pass `regime`, `regime_claim_ref`, `commitment_profile_ref`, `design_strategy` into `_design_record` and change exactly the hard-coded sites:

- `epistemic_regime_scopes = [regime] if regime else ["ignorance"]` (backward-compatible default).
- Append two `AxisPositionDeclaration`s — `KNOWLEDGE.epistemic_regime` (`position=regime`, `evidence_refs=[regime_claim_ref]`) and `INTERVENTION.reversibility_lifecycle_stakes` (`position=<commitment posture>`, `evidence_refs=[commitment_profile_ref]`) — reusing the `regime_claim_to_axis_position` shape from Task 2.
- Append two `AxisFirewallStatus`es — `KNOWLEDGE.epistemic_regime` (`pattern_ids=["P16"]`) and `INTERVENTION.reversibility_lifecycle_stakes` (`pattern_ids=["P23"]`).
- `ledger_refs = [ledger.ledger_ref] + [r for r in (regime_claim_ref, commitment_profile_ref) if r]` — this is the **persistence** the cluster contract requires (the full `EpistemicRegimeClaim`/`CommitmentProfileRecord` live as ledger artifacts; the axis positions only *index* them).
- `projection_audiences = ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]` when a regime is injected.

When `regime is None`, `_design_record` returns the current S2 output unchanged (no regression for the standalone S2 unit tests).

- [x] **Step 3: Widen and enrich `project_s2_design_search` for all four audiences (the surface)**

- Widen the signature to `audiences: tuple[Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"], ...]`. Existing `("MACHINE", "REVIEWER")` callers stay valid: the `audiences` arg still controls which keys appear, so the current assertion `set(projections) == {"MACHINE", "REVIEWER"}` (`test_layer2_s2_design_search.py:188`) holds. The regime fields are added **only when the record carries a regime** (regime injected); a pure-S2 projection (regime `None`) keeps its exact current key set — no regression.
- Add regime depth per audience, read from `run.design_record` (axis positions / firewall status / envelope) — do not re-read loop internals:
  - **PUBLIC**: `regime`, `design_strategy`, the regime/commitment honest **limitation** text, and the reversible/adaptive/precautionary posture — no evidence internals.
  - **REVIEWER**: PUBLIC + the firewall disposition.
  - **EXPERT/MACHINE**: + evidence-basis ref, asymmetry penalty, P16/P23 firewall decisions, stakes band, lifecycle stage, and the selected floor.
- The PUBLIC projection must carry the load-bearing limitation; omitting it is a faithfulness failure (presence check here; the full faithfulness verifier is S9).

- [x] **Step 4: Condition refinement on strategy + commitment, then verify**

- In `_refinement_decision`, set `stakes_band` from the injected commitment instead of the hard-coded `"moderate"`: `catastrophic -> "high_stakes"`, `high -> "high"`, `low -> "low"` (the visible "floors change with stakes" signal in the decision stream).
- Under a non-`risk` strategy, a non-`real_design_blocker` counterexample routes to `reframe` (toward adaptive/precautionary/robust), never a point-optimization `refine`; `frame_indexed_portfolio` records frame-indexing as a limitation (full multi-frame portfolio is S8). Put the strategy in the decision `reason`.

```bash
cd policy-engine
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
```

Expected: existing S2 tests stay green (regime not injected ⇒ identical output). Add S2-loop tests:
- `test_injected_regime_recorded_on_record_without_self_classification` — injected `regime`/`design_strategy` appear on the candidate; the `KNOWLEDGE.epistemic_regime` axis position + P16 firewall + `epistemic_regime_scopes == [regime]` appear on the record; the claim/commitment refs are in `ledger_refs`; the loop computes no regime itself.
- `test_four_audience_surface_renders_regime` — `project_s2_design_search(run, audiences=("PUBLIC","REVIEWER","EXPERT","MACHINE"))` renders regime in all four, PUBLIC carrying the limitation and EXPERT/MACHINE the evidence basis + firewall + stakes/lifecycle/floor.
- `test_public_projection_dropping_limitation_fails` — a PUBLIC projection without the load-bearing limitation fails the presence check (anticipates S9 faithfulness).
- `test_precautionary_strategy_blocks_point_optimization_refinement` — injected `ignorance`/`precautionary_adaptive_pathway` ⇒ refinement is `reframe`, not point-optimization `refine`, and `stakes_band` tracks the commitment.

## Task 4: Canonical Corpus Route Wiring — 13-Case Regime Classification + W12 Hypothesis

**Files:**

- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`
- Create: `tests/fixtures/layer2/s4/s4_expert_labels.json` (regime + commitment-profile gold for the 13 cases)
- Create: `tests/fixtures/layer2/s4/false_risk_probe.json`, `tests/fixtures/layer2/s4/false_precaution_probe.json`
- Modify: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`

**Code reality this task is grounded in (verified against `run_universal_outcome_corpus.py` and the corpus):**

- Cases load via `_load_cases` (line ~2915) from `tests/fixtures/universal-corpus/cases/*.json` — **13** files (`ua-msme-affordable-loans-2022.json` + twelve `w11a_*`). `_run_case` builds per-case summaries (`s1_graded_outcome`, `s2_design_search`, `capability_graph_trace`) and the case dict is returned with those keys (e.g. `"s2_design_search": s2_design_search` at line ~795).
- **Outcome gold already exists in the corpus** — each case carries `expert_adjudication.case_label` ∈ {`limitation_required` (9), `semantic_pass` (3), `false_pass` (1)}. The route already maps `limitation_required -> publish-with-limitation` (line ~145). So the S4 fixture supplies only the **regime + commitment** gold, never re-states the outcome split.
- **Substrate-binding status must come from static case annotations; the capability graph is an optional enrichment.** `capability_graph_trace` resolves real bindings only when a capability index is available — and that index is a **build artifact**: the CLI `--capability-index` defaults to `_build/.tmp/production-quality/capability-index/capability_index_v1.duckdb` (present in a *built* tree, **absent** in a fresh checkout/CI), while the programmatic `run_w12d_universal_outcome_corpus(...)` defaults `capability_index_path=None` (→ `_capability_graph_trace` returns `not_run`/`blocked`). So S4 must **not** depend on it. Derive the substrate signal from the **always-present static annotations**: `expected_claim_families.families[].expected_support_status` and `claim_evidence_annotations.claims[].admissibility_label`, both ∈ {`limited` (9), `publishable_with_limitation` (3), `blocked` (1)}; `expected_adapter_bindings.bindings[].status` ∈ {selected, rejected, blocked}. **None are risk-grade**, so all 13 classify non-risk by static evidence — the over-blocking signal, computed not assumed. When the trace *did* resolve (`status == "pass"`), prefer the live `capability_bindings[].status` (incl. the S3-grounded `selected_exact`) as enrichment.
- `claim_evidence_annotations.claims[].contestability_status` ∈ {`contested` (9), `limited`, `resolved_by_court`, `review_required`} drives the contested/expert-disagreement signal.
- Commitment signals per case: `policy_instrument.instrument_type`, `domain` (e.g. `climate_adaptation`, `digital_public_service`, `msme_credit_grant`), `intent.policy_time`, `targeting.affected_populations` (scale).

- [x] **Step 1: Add the S4 expert-labels fixture (regime + commitment gold, 13 cases)**

Create `tests/fixtures/layer2/s4/s4_expert_labels.json` keyed by `case_id`, each entry:

```json
{
  "w11a_india_aadhaar_dbt_2016": {
    "expert_regime": "contested_model",
    "reversibility": "irreversible", "option_value": "low",
    "lifecycle_stage": "reform", "transition_cost": "high", "stakes": "catastrophic"
  }
}
```

- `expert_regime` is the gold for `s4_regime_accuracy` (floor revision rule: `expert_label_change_requires_recorded_adjudication` — the fixture header records reviewer + date). Seed the first adjudication from the available signals (`contestability_status`, `admissibility_label`, `domain`, `known_failure_limitation_labels`) and mark it for `team-policy-design-research` confirmation; do **not** back-fit it to make accuracy look good.
- The commitment fields are the gold for the commitment-profile producer (Task 2). Ensure the set spans the closure-test corners: at least one **catastrophic + irreversible** case (`w11a_india_aadhaar_dbt_2016`, `w11a_netherlands_room_for_river_2007`) and at least one **reversible/pilotable emergency** case (`w11a_us_ppp_2020`, `w11a_eu_temporary_protection_ukraine_2022`).

- [x] **Step 2: Add `_s4_epistemic_regime_summary(case, repo_root)` (mirror `_s2_design_search_summary` / `_s3_*`)**

For each case, deterministically (no capability index required):

- **Substrate status** — map the static annotation to `RegimeEvidenceBasis.substrate_binding_status`: `blocked -> "blocked_construct_not_observed"`; `limited`/`publishable_with_limitation -> "selected_proxy_with_limitation"`; (`selected`/exact -> `"selected_exact"` if ever present). When `capability_graph_trace.status == "pass"`, prefer the live `capability_bindings[].status` (and the S3-grounded `selected_exact` for the pinned UA-MSME construct) as an enrichment.
- **Contestation** — `contestability_status == "contested" -> contested_scholar_edges = 1`; `review_required -> expert_disagreement = "some"`; else `none`.
- **Absent S6/S11/S8 signals** — `measurability_present = calibration_present = value_provenance_present = False`, `method_boundary_conditions_met = None`. (These cap the regime below risk and are the dependency edges S6/S8/S11 will later strengthen.)
- **Commitment** — `build_commitment_profile(...)` from the case signals (Task 2 producer); attach the gold from the fixture for the adequacy comparison.
- Run the A-side gate: `classify_regime(evidence, commitment)` -> `regime_design_strategy` -> `select_floor`; persist the full `EpistemicRegimeClaim` + `CommitmentProfileRecord` (ledger refs) and the `regime_claim_to_axis_position` projection; record per-case `predicted_regime` vs `expert_regime`, `derived_commitment` vs gold, the selected strategy, and the selected floor.
- Attach an `s4_epistemic_regime` block to the case result (alongside `s2_design_search`); when `--capability-index` is present, thread it through the same `capability_graph_trace` block where S3 attaches `s3_acquisition`.

- [x] **Step 3: Add the corpus-level `s4_regime_summary` and W12 hypothesis record**

In `build_w12d_universal_outcome_corpus_report` (or a sibling that reads `case_results`), add `s4_regime_summary`:

- `regime_accuracy(predicted=[...], gold=[...])` over all 13 (the asymmetric false-risk-penalized score from Task 2).
- `commitment_profile_adequacy`: fraction of cases whose derived commitment matches gold on `reversibility`/`stakes` (the manifest `shadow_adequacy_check`, not a governed floor).
- **W12 hypothesis** — restrict to the 9 cases whose `expert_adjudication.case_label == "limitation_required"`; count how many classified **non-risk** (uncertainty/ambiguity/ignorance/contested_model — i.e. would route to robust/limited design rather than a hard block), with a per-regime breakdown; set `w12_overblocking_hypothesis ∈ {"confirmed","revised"}` from those counts. **Computed, never hard-coded.** D2.5 frames the hypothesis as "uncertainty/ambiguity"; record contested_model and ignorance in the breakdown too, since they are equally non-risk and equally support the over-blocking finding.
- Shadow/governed only: the S4 block is additive metadata; it must not alter `outcomes`, `typed_blockers`, `rollout_blockers`, or `closeout_honesty_rate`.

- [x] **Step 4: Verify the honest metric and the unchanged production floors**

```bash
cd policy-engine
uv run python tools/quality/validation/run_universal_outcome_corpus.py --mode real_producer 2>&1 | tail -60
```

Expected: every case carries an `s4_epistemic_regime` block; `s4_regime_summary` reports `regime_accuracy`, `penalized_score`, `commitment_profile_adequacy`, and `w12_overblocking_hypothesis` with the per-regime breakdown; the existing assertions stay green — `len(cases) == 13`, the S2/S3 blocks unchanged, production-posture outcomes and `closeout_honesty_rate` not moved by S4. Add corpus-test cases in `test_w12d_universal_outcome_corpus_run.py`: `test_w12d_emits_s4_regime_for_13_cases`, `test_w12d_s4_records_w12_hypothesis`, and `test_w12d_s4_does_not_change_canonical_closeout_outcome` (mirror the existing `test_w12d_s2_shadow_search_does_not_change_canonical_closeout_outcome`). Record the computed accuracy, adequacy, penalized score, and hypothesis result in the S4 manifest.

**Task 4 verification note (2026-05-31):** `s4_regime_summary` over the 13-case corpus recorded `regime_accuracy = 1.0`, `penalized_score = 1.0`, `false_risk_count = 0`, `false_caution_count = 0`, `commitment_profile_adequacy = 0.9231`, and `w12_overblocking_hypothesis = "confirmed"` with `limitation_required_non_risk_breakdown = {"contested_model": 8, "uncertainty": 1}`. The adequacy miss is intentional and visible: the expert fixture keeps India Aadhaar as `irreversible` while the current producer derives `lock_in`. The S4 block is additive (`canonical_outcome_effect = "none_shadow_only"`); the real-producer corpus still reports `runtime_useful_design_rate = 0.0` and `closeout_honesty_rate = 0.0769`, i.e. the W12.D production floors were not relaxed by S4.

## Task 5: S4 Manifest, Readiness Validator, And Cluster-Map Cell Closure

**Files:**

- Create: `architecture/policy_design_case/layer2_s4_epistemic_regime_manifest.json`
- Modify: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- Modify: `architecture/policy_design_case/cluster_ownership_map.toml`

**Code reality this task is grounded in (verified against both validators):**

- **Cluster validator (`check_policy_design_case_cluster_ownership_map.py`).** Every `[cell.*]` must carry all `REQUIRED_FIELDS` = {`owner_module`, `seed_files`, `ratchet_state`, `p01_chain`, `authority_dim`, `firewall`, `publishes`, `consumes`, `gap`, `action`} — *including implemented cells*. The traps when closing a cell:
  - `ratchet_state == "implemented"` ⇒ `owner_module` must be non-empty (line ~410); `owner_module` is **not** existence-checked, but **every `seed_files` entry is** (line ~436).
  - `gap` and `action` must stay non-empty for **all** cells (line ~454). Only *open* cells additionally may not have `gap` starting with `"none"` and may not have `p01_chain == "implemented"` (lines ~464-477). So a closed cell uses `gap = "none_for_..."` (S2's pattern) + a closure `action`.
  - `publishes`/`consumes` must remain non-empty string lists (line ~444). Keep the existing edges — other cells `consume` `KNOWLEDGE.epistemic_regime`, and closing does not delete the cell, so those references still resolve.
  - `_validate_open_cell_closures` builds `open_cells_by_id` = cells with `ratchet_state ∈ OPEN_OR_INCOMPLETE_STATES` and requires the `[open_cell_closure.*]` set to **equal** it: a closure for a non-open cell ⇒ `extra_closure`; an open cell without a closure ⇒ `missing_closure`. **The flip and the removal are therefore one atomic edit per cell.**
  - `ratchet_state`/`p01_chain` must be in the capability-ratchet **state vocabulary** loaded from `capability_reality_report.json`; `"implemented"` is valid. The validator uses the ratchet report only for the vocabulary — **closing a cluster cell does not touch `capability_reality_report.json`** (the separate A-side W12 meter; "W12 green ≠ Layer-2 readiness").
- **Readiness validator (`check_policy_design_case_layer2_readiness.py`).** `current_open_cells = _open_cell_refs(cluster_map)` = the `[open_cell_closure.*]` set (→ 13 after removal); it must stay `⊆ assigned_cells` (the frozen 17 in the slice→cell matrix). `_validate_s3_substrate_acquisition` already **enforces inventory registration** (`{artifact.get("path") …}` must contain the manifest path) and is loaded via `_load_optional_json` (not-yet-landed ⇒ readiness still valid at the S0/S2/S3 baseline). `_validate_s4_epistemic_regime` mirrors both behaviors.

- [x] **Step 1: Write the S4 manifest (two cells closed, open count 13)**

Create `architecture/policy_design_case/layer2_s4_epistemic_regime_manifest.json` mirroring the S2/S3 manifest shape:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s4_epistemic_regime_manifest.v1",
  "status": "active",
  "owner": "team-knowledge-regime",
  "slice": "S4",
  "slice_label": "epistemic_regime_classifier_commitment_profile",
  "promotion": "governed",
  "promotion_note": "Regime classification is governed A-side authority; the B-side strategy it drives stays shadow (regime does not grant the design production/rollout authority). Ignorance outputs carry no outcome claims.",
  "cells_closed": [
    "KNOWLEDGE.epistemic_regime",
    "INTERVENTION.reversibility_lifecycle_stakes"
  ],
  "cell_owners": {
    "KNOWLEDGE.epistemic_regime": "team-knowledge-regime",
    "INTERVENTION.reversibility_lifecycle_stakes": "team-case-lifecycle"
  },
  "open_cell_count_baseline": 17,
  "expected_current_open_cell_count": 13,
  "regimes": ["risk", "uncertainty", "ambiguity", "ignorance", "contested_model"],
  "design_strategies": [
    "expected_welfare_optimization", "robust_satisficing",
    "frame_indexed_portfolio", "precautionary_adaptive_pathway"
  ],
  "required_artifacts": ["EpistemicRegimeClaim", "RegimeEvidenceBasis", "CommitmentProfileRecord"],
  "proving_ground_case_count": 13,
  "s4_expert_labels_ref": "tests/fixtures/layer2/s4/s4_expert_labels.json",
  "w12_overblocking_hypothesis": "<confirmed|revised — set from the computed corpus run, not hard-coded>",
  "regime_accuracy": null,
  "penalized_score": null,
  "commitment_profile_adequacy": null,
  "floors": ["s4_regime_accuracy"],
  "shadow_adequacy_checks": [
    {
      "check_id": "s4_commitment_profile_adequacy",
      "metric": "commitment_profile_match_rate_vs_gold",
      "owner": "team-case-lifecycle",
      "rationale": "Reversibility cell is fully implemented: the producer's derived reversibility/stakes must match expert gold across the 13 cases. Non-governed adequacy check (floor governance is S0-frozen and carries only s4_regime_accuracy)."
    }
  ],
  "authority_scope": [
    "epistemic_regime_classification", "regime_conditional_strategy_selection",
    "commitment_profile", "regime_accuracy_metric"
  ],
  "may_not_use_for": [
    "risk_regime_authority_without_risk_evidence", "b_side_regime_selection",
    "outcome_claim_from_ignorance", "low_stakes_floor_on_catastrophic_irreversible",
    "production_claim_authority", "rollout_authority", "publication_authority"
  ],
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py",
  "rule_version_ref": "repo://docs/adr/0174-policy-evidence-capability-graph.md",
  "firewalls": ["P01", "P03", "P04", "P05", "P10", "P12", "P13", "P15", "P16", "P23"]
}
```

Fill `regime_accuracy`, `penalized_score`, and `w12_overblocking_hypothesis` from the Task 4 corpus run (recorded, not assumed). `s4_regime_accuracy` is already in `layer2_floor_governance.toml` (do not re-add it).

- [x] **Step 2: Close both cells in the cluster ownership map (mirror S2)**

In `architecture/policy_design_case/cluster_ownership_map.toml`:

For **each** of the two `[cell.*]` tables, apply all of the following as **one atomic edit** (see Code reality — a half-edit fails the validator):

- `ratchet_state`: `contract_only -> implemented`; `p01_chain`: `producer_missing -> implemented`.
- `owner_module`: `"" -> "src/polisyos/runtime/quality"`.
- `gap`: replace the real-gap text with `"none_for_s4_epistemic_regime"` (must stay non-empty; a closed cell *may* start with `"none"`, an open one may not).
- `action`: rewrite to a closure description, e.g.
  - `KNOWLEDGE.epistemic_regime`: "S4 gate-owned classifier emits per-claim EpistemicRegimeClaim with P16; consumed by INTERVENTION.design_strategy and DESIGNER_ITSELF.envelope_membership."
  - `INTERVENTION.reversibility_lifecycle_stakes`: "S4 CommitmentProfileRecord producer derives reversibility/lifecycle/stakes; drives design strategy and select_floor, with P23."
- Keep `authority_dim` (`regime_appropriateness` / `reversibility_stakes_fit`), `publishes`, `consumes`, and `seed_files` **unchanged**.
- **Remove** the matching `[open_cell_closure.KNOWLEDGE.epistemic_regime]` and `[open_cell_closure.INTERVENTION.reversibility_lifecycle_stakes]` tables.

`_validate_open_cell_closures` requires the `[open_cell_closure.*]` set to equal the open-state cell set, so flip-without-removal is `extra_closure` and removal-without-flip is `missing_closure`. The live open count drops `15 -> 13`. Do **not** edit `capability_reality_report.json`.

`seed_files` stay as-is — the validator checks every entry **exists** (`scholar/_impl/evidence.py`, `capability_white_space.py`, `case_lifecycle.py` all do); `owner_module` is not existence-checked. Optionally add `src/polisyos/runtime/quality/layer2_epistemic_regime.py` to `seed_files` here in Task 5 (it exists only after Task 2 — never reference it before).

- [x] **Step 3: Add `_validate_s4_epistemic_regime` to the readiness validator**

Add a `DEFAULT_S4_EPISTEMIC_REGIME_MANIFEST_PATH` constant (mirroring `DEFAULT_S3_SUBSTRATE_ACQUISITION_MANIFEST_PATH`), register the manifest in `load_layer2_readiness_payloads` as `"s4_epistemic_regime": _load_optional_json(root / DEFAULT_S4_EPISTEMIC_REGIME_MANIFEST_PATH)`, and call `_validate_s4_epistemic_regime(...)` from `validate_layer2_readiness_payloads` immediately after the S3 call — passing the already-computed local `current_open_cells` and `assigned_cells`, plus `inventory=payloads["inventory"]` (the inventory check mirrors S3 and stays red until Task 6 Step 1 registers the manifest — expected under red-first):

```python
def _validate_s4_epistemic_regime(
    *, s4, floor_governance, current_open_cells, assigned_cells, inventory, issues,
):
    if not s4:
        return  # S4 not yet landed; readiness still valid at the S0/S2/S3 baseline
    expected_closed = {"KNOWLEDGE.epistemic_regime", "INTERVENTION.reversibility_lifecycle_stakes"}
    if set(s4.get("cells_closed", [])) != expected_closed:
        issues.append({"code": "layer2_s4_cells_closed_invalid",
                       "message": "S4 must close exactly the epistemic_regime and reversibility cells."})
    if s4.get("expected_current_open_cell_count") != 13:
        issues.append({"code": "layer2_s4_open_cell_count_drift",
                       "message": "S4 manifest must record expected_current_open_cell_count=13 (its snapshot)."})
    # Robust, slice-future-proof: assert the two S4 cells are CLOSED, never the live total
    # (later slices reduce the total; only this per-cell invariant holds forever — same reason
    # S3 checks its static manifest field, not the live count).
    if expected_closed & current_open_cells:
        issues.append({"code": "layer2_s4_cluster_map_not_closed",
                       "message": "S4 cells must be removed from open_cell_closure (still open)."})
    if not (expected_closed <= assigned_cells):
        issues.append({"code": "layer2_s4_cells_not_assigned",
                       "message": "S4 closed cells must be in the frozen slice-cell baseline."})
    deny = set(s4.get("may_not_use_for", []))
    required_deny = {"risk_regime_authority_without_risk_evidence", "b_side_regime_selection",
                     "outcome_claim_from_ignorance", "low_stakes_floor_on_catastrophic_irreversible"}
    if not required_deny <= deny:
        issues.append({"code": "layer2_s4_authority_boundary_incomplete",
                       "message": "S4 may_not_use_for must block false-risk, regime-shopping, ignorance-outcome, and P23."})
    if not _floor_by_id(floor_governance, "s4_regime_accuracy"):
        issues.append({"code": "layer2_s4_regime_floor_missing",
                       "message": "s4_regime_accuracy floor must be registered."})
    if s4.get("w12_overblocking_hypothesis") not in {"confirmed", "revised"}:
        issues.append({"code": "layer2_s4_w12_hypothesis_not_recorded",
                       "message": "S4 must record the W12 hypothesis as confirmed or revised (not assumed/blank)."})
    # Inventory registration — mirror _validate_s3_substrate_acquisition.
    inventory_paths = {
        str(a.get("path", "")) for a in inventory.get("artifacts", []) if isinstance(a, dict)
    }
    if DEFAULT_S4_EPISTEMIC_REGIME_MANIFEST_PATH.as_posix() not in inventory_paths:
        issues.append({"code": "layer2_s4_manifest_missing_from_inventory",
                       "message": "S4 manifest must be registered in the Policy Design Case inventory."})
```

Add the `s4_*` keys to the summary (`s4_w12_overblocking_hypothesis`, `s4_regime_accuracy`, `s4_expected_current_open_cell_count`). The cluster-map edit (Step 2) and inventory registration (Task 6 Step 1) are what make `current_open_cells` resolve to 13 and the inventory check pass; until both land, `_validate_s4_epistemic_regime` is honestly red.

**Task 5 verification note (2026-05-31):** S4 manifest landed with recorded Task 4 metrics (`regime_accuracy = 1.0`, `penalized_score = 1.0`, `commitment_profile_adequacy = 0.9231`, `w12_overblocking_hypothesis = "confirmed"`). `cluster_ownership_map` now marks `KNOWLEDGE.epistemic_regime` and `INTERVENTION.reversibility_lifecycle_stakes` as `implemented` and removes both `open_cell_closure` entries; the cluster validator reports `open_or_incomplete_count = 13`. Readiness loads S4 and reports the `s4_*` summary fields, while full readiness intentionally fails only on `layer2_s4_manifest_missing_from_inventory` until Task 6 registers the manifest.

## Task 6: Repo-Quality Tests, Inventory, Snapshot Updates, And Burn-Down Confirmation

**Files:**

- Create: `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`
- Modify: `architecture/policy_design_case/inventory.json`

- [x] **Step 1: Register the S4 manifest in inventory**

Add an `artifacts[]` entry to `inventory.json` mirroring the S3 entry shape (`id`, `path`, `kind`, `schema_version`, `owner`, `status`, `authority_scope`, `may_not_use_for`, `validator`, `canonical_route`). The **`path` must be exactly** `architecture/policy_design_case/layer2_s4_epistemic_regime_manifest.json` — that is the field `_validate_s4_epistemic_regime` matches on (and `_inventory_layer2_artifact_count` counts ids starting `layer2_`):

```json
{
  "id": "layer2_s4_epistemic_regime_manifest",
  "path": "architecture/policy_design_case/layer2_s4_epistemic_regime_manifest.json",
  "kind": "layer2_s4_epistemic_regime_manifest",
  "schema_version": "policyos.policy_design_case.layer2_s4_epistemic_regime_manifest.v1",
  "owner": "team-knowledge-regime",
  "status": "active",
  "capability_reality_label": "implemented",
  "authority_scope": ["epistemic_regime_classification", "regime_conditional_strategy_selection", "commitment_profile", "regime_accuracy_metric"],
  "may_not_use_for": ["risk_regime_authority_without_risk_evidence", "b_side_regime_selection", "outcome_claim_from_ignorance", "low_stakes_floor_on_catastrophic_irreversible", "production_claim_authority", "rollout_authority", "publication_authority"],
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py"
}
```

- [x] **Step 2: Add repo-quality tests for the S4 readiness/cell facts**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness
from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map

REPO_ROOT = Path(__file__).resolve().parents[3]
S4_MANIFEST = REPO_ROOT / "architecture/policy_design_case/layer2_s4_epistemic_regime_manifest.json"
S4_LABELS = REPO_ROOT / "tests/fixtures/layer2/s4/s4_expert_labels.json"
CORPUS_CASES = REPO_ROOT / "tests/fixtures/universal-corpus/cases"


def _s4() -> dict:
    return json.loads(S4_MANIFEST.read_text())


def test_layer2_s4_manifest_is_valid_and_open_count_is_13() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["open_cell_count"] == 13


def test_layer2_s4_closes_two_cluster_cells() -> None:
    assert set(_s4()["cells_closed"]) == {
        "KNOWLEDGE.epistemic_regime", "INTERVENTION.reversibility_lifecycle_stakes"
    }
    assert _s4()["expected_current_open_cell_count"] == 13


def test_layer2_s4_cluster_map_marks_cells_implemented_and_unlisted_as_open() -> None:
    # load_cluster_ownership_map returns the raw nested TOML: cell -> CLUSTER -> axis -> {fields}.
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    cells = payload["cell"]
    assert cells["KNOWLEDGE"]["epistemic_regime"]["ratchet_state"] == "implemented"
    assert cells["INTERVENTION"]["reversibility_lifecycle_stakes"]["ratchet_state"] == "implemented"
    open_closures = payload.get("open_cell_closure", {})
    assert "epistemic_regime" not in open_closures.get("KNOWLEDGE", {})
    assert "reversibility_lifecycle_stakes" not in open_closures.get("INTERVENTION", {})


def test_layer2_s4_may_not_use_for_blocks_false_risk_and_regime_shopping() -> None:
    deny = set(_s4()["may_not_use_for"])
    assert {"risk_regime_authority_without_risk_evidence", "b_side_regime_selection",
            "outcome_claim_from_ignorance", "low_stakes_floor_on_catastrophic_irreversible"} <= deny


def test_layer2_s4_w12_hypothesis_recorded_not_blank() -> None:
    assert _s4()["w12_overblocking_hypothesis"] in {"confirmed", "revised"}


def test_layer2_s4_expert_labels_cover_13_cases_with_regime_and_commitment_gold() -> None:
    labels = json.loads(S4_LABELS.read_text())
    cases = {p.stem for p in CORPUS_CASES.glob("*.json")}
    assert len(cases) == 13
    # The S4 fixture supplies regime + commitment gold for every corpus case (no outcome gold here).
    assert set(labels) == cases
    regimes = {"risk", "uncertainty", "ambiguity", "ignorance", "contested_model"}
    commitment_fields = {"reversibility", "option_value", "lifecycle_stage", "transition_cost", "stakes"}
    for entry in labels.values():
        assert entry["expert_regime"] in regimes
        assert commitment_fields <= set(entry)


def test_layer2_s4_outcome_split_comes_from_corpus_not_the_fixture() -> None:
    # Outcome gold is the corpus's expert_adjudication.case_label, not duplicated in the S4 fixture.
    import collections
    counts = collections.Counter(
        json.loads(p.read_text())["expert_adjudication"]["case_label"]
        for p in CORPUS_CASES.glob("*.json")
    )
    assert counts["limitation_required"] == 9   # == publish-with-limitation
    assert counts["semantic_pass"] == 3
    assert counts["false_pass"] == 1
```

- [x] **Step 3: Update prior-slice live-count snapshots (the cell-closing tax) and fix the already-red cluster test**

Closing two cells moves the live open count `15 → 13`, which invalidates every test that hard-asserts the live `15`. These are **live** summary assertions, distinct from the prior slices' **static manifest** fields (which record the count *at that slice's time* and must not change). Update exactly:

- `test_policy_design_case_layer2_readiness.py`:
  - `summary["current_open_cell_count"]` `15 → 13`;
  - `cells_closed_since_s0` `["INTERVENTION.design_candidate", "INTERVENTION.design_grammar"]` → the **sorted four**: `["INTERVENTION.design_candidate", "INTERVENTION.design_grammar", "INTERVENTION.reversibility_lifecycle_stakes", "KNOWLEDGE.epistemic_regime"]`;
  - in `test_layer2_slice_cell_matrix_preserves_baseline_and_current_open_subset`, `assigned - current_open_cells` → the same sorted four set. Leave `open_cell_count_baseline == 17` and `assigned_open_cell_count == 17` (frozen baseline).
- `test_policy_design_case_layer2_s2_design_search.py`: `summary["current_open_cell_count"]` `15 → 13`. Do **not** touch the S2 manifest's static `open_cell_count_baseline=17` / `expected_current_open_cell_count=15`.
- `test_policy_design_case_layer2_s3_substrate_acquisition.py`: `validation["summary"]["open_cell_count"]` `15 → 13`. Do **not** touch the S3 manifest's static `expected_current_open_cell_count=15`.
- `test_policy_design_case_cluster_ownership_map.py`: `open_cell_closure["open_cell_count"]` → `13`. This assertion is **already red on the current tree** (`assert 15 == 17`, an S2/S3 oversight); S4 corrects it to the live value and the commit message must say so explicitly (it is a real pre-existing failure, not S4-introduced churn).

These updates are mandatory for a green Task 7. A later slice closing a cell is the sanctioned reason to touch a prior slice's live-count snapshot; the prior slices' *static manifest* fields and *source* are untouched.

- [x] **Step 4: Confirm the burn-down moved by exactly two**

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py | python3 -c "import sys,json;print(json.load(sys.stdin)['summary']['open_or_incomplete_count'])"
```

Expected: `13`.

**Task 6 verification note (2026-05-31):** S4 manifest is now registered in `inventory.json`, full Layer-2 readiness returns `pass`, live open-cell snapshots are updated from `15` to `13` while S2/S3 static manifest snapshots remain unchanged, and the cluster burn-down command reports `13`. The pre-existing cluster snapshot drift (`17`/`15`) is corrected to the live S4 value.

## Task 7: Full S4 Verification

- [x] **Step 1: Run the full S4 + regression gate**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py -q
uv run pytest tests/unit/pdc tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py tests/unit/runtime/quality/test_layer2_graded_outcomes.py -q
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run pytest tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools architecture guardrails check
```

Expected:

```text
S4 unit + repo-quality tests pass.
S1/S2/S3 regression tests pass.
Layer 2 readiness validator: status pass; open_cell_count 13; S4 cells closed; W12 hypothesis recorded.
Cluster ownership validator: status pass; open_or_incomplete 13.
Capability ratchet (A-side W12) unchanged/green.
Runtime API contract pass.
Architecture guardrails pass.
```

Record the verified accuracy/penalized-score/hypothesis result and any Done-When caveat (e.g., the broader `closeout_honesty_rate` is a separate W12.D backlog and is unchanged by S4) directly under this task, mirroring the S3 audit note.

**Task 7 verification note (2026-05-31):** Full S4 + regression gate passed. The guardrail pass required routing the S4 runtime import through the public `polisyos.pdc` facade for the reused S0 `EpistemicRegime` literal instead of the private readiness implementation; no architecture baseline was weakened. Verified S4 corpus metrics: `case_count=13`, `regime_accuracy=1.0`, `penalized_score=1.0`, `false_risk_count=0`, `false_caution_count=0`, `commitment_profile_adequacy=0.9231`, and `w12_overblocking_hypothesis=confirmed` with the per-case table. Layer-2 readiness and cluster ownership both return `pass`, with open cell count `13`, S4 cells closed, and the S4 manifest registered in inventory. Runtime API contract and architecture guardrails pass. `closeout_honesty_rate` remains unchanged at `0.0769`, so S4 affects shadow/governed strategy routing without weakening production posture floors.

## Done When

1. `EpistemicRegimeClaim`, `RegimeEvidenceBasis`, and `CommitmentProfileRecord` are strict, reuse the S0 `EpistemicRegime` literal and `AxisPositionDeclaration`/`AxisFirewallStatus`, and the regime classifier is **A-gate-owned** — the B loop consumes an injected regime/strategy and cannot self-classify or regime-shop.
2. Risk is admissible only with risk-regime evidence; absent measurability/calibration/value provenance, the classifier never returns risk (defaults toward more uncertainty). P16 fails closed in **both** directions (`false_risk_probe`, `false_precaution_probe`).
3. `INTERVENTION.reversibility_lifecycle_stakes` is **fully implemented**: `build_commitment_profile` is a first-class producer that derives reversibility/lifecycle-stage/stakes from case signals across all 13 cases and matches expert gold at/above the `s4_commitment_profile_adequacy` shadow check; it drives **both** strategy and `select_floor`; a low-stakes floor on a catastrophic irreversible design fails P23; irreversible-high-stakes-under-ignorance routes to `precautionary_adaptive_pathway`, not risk optimization. The producer reuses `case_lifecycle` for transition/termination/grandfathering stages.
4. All 13 corpus cases are classified against expert gold labels; `regime_accuracy_with_asymmetric_false_risk_penalty >= floor`; the W12 over-blocking hypothesis is **recorded** (`confirmed`/`revised`) with the per-case table — not pre-assumed.
5. Production-posture outcomes and `closeout_honesty_rate` are unchanged by S4 (regime affects B strategy at shadow/governed posture only).
6. `KNOWLEDGE.epistemic_regime` and `INTERVENTION.reversibility_lifecycle_stakes` are `implemented`; cluster-map open cell count is `13`; both validators pass; the S4 manifest is registered in inventory.
7. The full `EpistemicRegimeClaim` / `CommitmentProfileRecord` are persisted as replayable ledger entries referenced from `DesignRecordV0.ledger_refs` (not only a thin axis label), and the regime + commitment posture renders in **all four** audience projections via `project_s2_design_search` (PUBLIC regime + limitation; REVIEWER regime + strategy; EXPERT/MACHINE evidence basis + asymmetry penalty + firewall + stakes/lifecycle), proven by a surface test — an internal effect is not a surface.

## Verification Commands

See Task 7. Plan-level done = all Task 7 commands pass with the expected output, the open cell count is `13`, the W12 hypothesis is recorded, and no production floor is weakened.

## Commit Guidance

Mirror the S2/S3 red-first sequence, one logical commit per task:

```text
test: add layer2 s4 epistemic-regime red tests
feat: add layer2 s4 regime classifier, commitment profile, P16/P23 firewalls
feat: inject layer2 s4 regime/strategy into shadow design loop
feat: classify layer2 s4 corpus regimes and record w12 hypothesis
chore: close layer2 s4 epistemic-regime and reversibility cells
chore: register layer2 s4 epistemic-regime progress
```

End commit messages with the repo's standard co-author trailer. Do not mark any S5+ cell, production authority, portfolio-level regime composition, or rich predictive regime/calibration models as implemented.
