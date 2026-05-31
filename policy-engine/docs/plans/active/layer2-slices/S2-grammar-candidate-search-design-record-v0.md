---
title: PolicyOS Layer 2 S2 Grammar Candidate Search DesignRecord v0 Task Plan
status: active
owner: team-design-generation
created: 2026-05-30
last_verified: null
stability: draft
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
slice: S2
slice_label: grammar_candidate_search_design_record_v0
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on: S0
---

# Layer 2 S2 Grammar + Candidate + Search Loop / DesignRecord v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:test-driven-development` for Tasks 1, 3, 4, and 5. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start the B-side in shadow mode by proving one replayable design loop: grammar-derived candidate -> A-side verification -> typed counterexample -> refinement decision -> `SearchLedger` -> `DesignRecordV0`.

**Architecture:** S2 does not create production recommendations. It extends the S0 narrow waist with S2 typed design-search records in `polisyos.pdc`, emits a deterministic one-case shadow loop, persists replay-visible `SearchLedger` and `DesignRecordV0` artifacts, projects MACHINE/REVIEWER search traces, and marks only the two S2-owned non-acquisition design cells implemented. The acquisition branch remains explicitly `bridge_missing` until S3, and the broader Scientist orchestration cell remains split across S2/S7 rather than being closed wholesale.

**Tech Stack:** Python 3.14, Pydantic v2, existing `polisyos.pdc` S0 contracts, existing `PolicyCandidateSchema` concepts by reference, canonical CAS governed artifacts, pytest, repo-quality validators, architecture guardrails.

---

## Scope

This task plan implements only roadmap slice S2.

It does not implement S3 substrate acquisition, S4 epistemic-regime classification, S5 coupling/composition, S6 blind-spot producers, Pareto search, DAPP, real data acquisition, production recommendation authority, or public rollout authority.

Cells moved by S2:

- `INTERVENTION.design_grammar`: `implemented_but_not_orchestrated -> implemented`
- `INTERVENTION.design_candidate`: `implemented_but_not_orchestrated -> implemented`

Layer advanced but not closed by S2:

- `CROSS_CUTTING.scientist_orchestration`: S2 emits `ClusterHandoffRecord` for the generation handoff path, but the cell remains open/split until S7 closes the broader orchestration contract.

Open cell count delta:

- S0 baseline remains `17`.
- Current cluster-map open cell count becomes `15` after S2.
- `layer2_slice_cell_matrix.toml` remains the baseline slice assignment map; S2 records the closed cells in its own manifest and updates readiness validation to distinguish baseline assignments from current open cells.

Acquisition branch:

- S2 must report `acquisition_branch_state="bridge_missing"`.
- S2 must not mark S3 acquisition, source contracts, substrate coverage, or rerun closure implemented.

## Architecture Decision

S2 contracts live in `polisyos.pdc._impl.layer2_design_search`, not in `runtime.quality` and not inside `scientist.policy_design`.

Reason: S2 starts the Policy Design Case B-side narrow waist. The record family is a PDC contract and must consume the S0 `DesignRecordV0`, `AuthorityBoundary`, `AxisPositionDeclaration`, `AxisFirewallStatus`, and `CertifiedOperationEnvelope` contracts rather than inventing a parallel design record. The producer is deterministic and shadow-only; rich Scientist and LLM workflows may feed it later through `ClusterHandoffRecord`, but their summaries do not become authority.

Import boundary:

- Do not import `polisyos.policy_grammar` from `polisyos.pdc`; use grammar refs and deterministic fixture inputs instead.
- Do not import `polisyos.pdc` from `polisyos.scientist` for S2.
- Existing `PolicyCandidateSchema` concepts may be referenced by string refs or lightweight S2 records; S2 does not need to instantiate a full rich candidate for the first proving loop.

S2 public statuses:

- `shadow_ready`: full loop replayed in shadow and projected to MACHINE/REVIEWER.
- `blocked`: candidate is blocked by A-side verification or hard firewall.
- `governance_required`: `a_spec_gap` or governance-owned gap is routed out of the loop.
- `acquisition_required`: `substrate_gap` proves acquisition is the next valid move, while S2 still reports acquisition bridge `bridge_missing`.
- `abstained`: `budget_gap` or irreparable incompleteness produces honest shadow abstention rather than a best-candidate claim.

S2 authority boundary:

- `authoritative_for`: `shadow_design_search_replay`, `machine_replay_trace`, `reviewer_search_trace`
- `may_not_use_for`: `production_recommendation`, `publication_authority`, `rollout_authority`, `claim_authority`, `production_closeout_authority`, `acquisition_authority`, `source_contract_authority`

## Pattern Pass

Relevant failure patterns: `P01`, `P02`, `P03`, `P05`, `P10`, `P12`, `P13`, `P15`, `P16`, `P17`, `P20`, `P21`, `P25`.

Existing risks found:

- `DesignRecordV0` exists from S0, but no producer writes it from a real design loop; without S2 this remains `producer_missing`.
- Existing `policy_grammar` and `scientist.policy_design.search` contain useful pieces, but S2 must not wrap free-text or LLM output as authority. Grammar must precede candidate emission.
- The cluster map has closure contracts for `INTERVENTION.design_grammar` and `INTERVENTION.design_candidate`, but no persisted S2 artifacts or semantic tests close those cells. `CROSS_CUTTING.scientist_orchestration` has a generation-handoff slice contribution, but it must not be closed wholesale in S2.
- A search ledger can easily become P25 search-control laundering: a frontier or best-so-far candidate must not be projected as exhaustive or authoritative.

Correct pattern:

- Typed grammar expansion produces typed candidate.
- A-side verification produces typed counterexamples.
- Refinement policy consumes counterexamples and emits typed decisions.
- Search ledger persists the run and proves deterministic replay.
- DesignRecordV0 is the projection home, not a recommendation.
- Cluster handoff records prove the S2 generation handoff contribution without treating Scientist workflow summaries as authority or closing all Scientist orchestration.

Missing capability labels before implementation:

- `producer_missing` for S2 design-search loop producer.
- `artifact_missing` for `DesignGrammarExpansion`, `DesignCandidateV0`, `CounterexampleRecord`, `RefinementDecision`, `SearchLedger`, and S2-backed `DesignRecordV0`.
- `bridge_missing` for counterexample -> refinement and cluster handoff -> design record.
- `surface_missing` for MACHINE/REVIEWER S2 projections.
- `semantic_test_missing` for deterministic replay, architecture-aligned counterexample classes, `a_spec_gap` governance routing, `substrate_gap` acquisition routing, blocked candidate no-retry, grammar-before-candidate, grammar diversity adequacy, and LLM-only candidate rejection.

Acceptance signal:

- One pinned UA-MSME case runs the full shadow loop deterministically.
- The loop emits `DesignGrammarExpansion`, `DesignCandidateV0`, `ConstraintStoreSnapshot`, at least one typed `CounterexampleRecord`, a valid `RefinementDecision` with VOI and governance routing refs, `SearchLedger`, `ClusterHandoffRecord`, and `DesignRecordV0`.
- Counterexample conversion rate is `1.0`.
- Grammar diversity minimum is `3` as a shadow adequacy check.
- `a_spec_gap` routes to governance and is not self-classified as solved.
- `substrate_gap` routes to acquisition-required while acquisition remains `bridge_missing`.
- A blocked candidate cannot be retried into a pass without a new grammar-derived candidate.
- LLM-only candidate proposal without grammar derivation fails P15.
- MACHINE and REVIEWER projections expose search trace and authority boundary.
- S2 manifest is registered in inventory.
- Cluster map current open cell count decreases from `17` to `15`.

## Source Of Truth

| Concern | Source |
| --- | --- |
| Roadmap closure contract | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md#s2--grammar--candidate--search-loop--designrecord-v0--true-start-of-b` |
| Shared S0 contracts | `src/polisyos/pdc/_impl/layer2_readiness.py` |
| Slice cell assignments | `architecture/policy_design_case/layer2_slice_cell_matrix.toml` |
| S2 artifact traceability | `architecture/policy_design_case/layer2_artifact_traceability.toml` |
| S2 floor | `architecture/policy_design_case/layer2_floor_governance.toml#s2_counterexample_conversion` |
| Cluster closure contracts | `architecture/policy_design_case/cluster_ownership_map.toml` |
| Failure pattern register | `docs/reference/policy-design-case-failure-patterns.md` |
| First proving case | `architecture/policy_design_case/layer2_first_proving_case.json` |
| Canonical corpus route | `tools/quality/validation/run_universal_outcome_corpus.py` |

## Files

Create:

- `src/polisyos/pdc/_impl/layer2_design_search.py`
- `architecture/policy_design_case/layer2_s2_design_search_manifest.json`
- `tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py`
- `tests/unit/pdc/test_layer2_s2_design_search.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`

Modify:

- `src/polisyos/pdc/__init__.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- `architecture/policy_design_case/cluster_ownership_map.toml`
- `architecture/policy_design_case/inventory.json`

Do not modify:

- `architecture/policy_design_case/layer2_floor_governance.toml`
- `architecture/policy_design_case/layer2_artifact_traceability.toml`
- `architecture/policy_design_case/layer2_dependency_dag.json`
- S1 graded-outcome files, unless a test exposes a direct S2 interaction bug

---

## Task 1: Red-First S2 Semantic And Negative Tests

**Files:**

- Create: `tests/unit/pdc/test_layer2_s2_design_search.py`

- [ ] **Step 1: Write failing unit tests for the complete S2 shadow loop**

Create `tests/unit/pdc/test_layer2_s2_design_search.py`:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.pdc import (
    S2_DESIGN_SEARCH_SCHEMA_VERSION,
    ConstraintStoreSnapshot,
    CounterexampleRecord,
    DesignCandidateV0,
    DesignGrammarExpansion,
    DesignRecordV0,
    Layer2S2DesignSearchInput,
    Layer2S2DesignSearchInputError,
    RefinementDecision,
    SearchLedger,
    project_s2_design_search,
    run_s2_shadow_design_loop,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIRST_PROVING_CASE_PATH = (
    REPO_ROOT / "architecture/policy_design_case/layer2_first_proving_case.json"
)
NOW = datetime(2026, 5, 30, tzinfo=UTC)


def _input() -> Layer2S2DesignSearchInput:
    proving_case = json.loads(FIRST_PROVING_CASE_PATH.read_text(encoding="utf-8"))
    return Layer2S2DesignSearchInput(
        schema_version=S2_DESIGN_SEARCH_SCHEMA_VERSION,
        case_id=str(proving_case["case_id"]),
        intent_ref="repo://architecture/policy_design_case/layer2_first_proving_case.json",
        grammar_ref="repo://src/polisyos/policy_grammar",
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=tuple(f"objective://{item}" for item in proving_case["constructs"]),
        construct_refs=tuple(f"construct://{item}" for item in proving_case["constructs"]),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=NOW,
        rule_version_ref="policyos.layer2.s2.design_search.v1",
    )
```

Add:

```python
def test_s2_shadow_loop_emits_grammar_candidate_counterexample_refinement_and_record() -> None:
    run = run_s2_shadow_design_loop(_input())

    assert isinstance(run.grammar_expansion, DesignGrammarExpansion)
    assert isinstance(run.candidates[0], DesignCandidateV0)
    assert isinstance(run.constraint_store, ConstraintStoreSnapshot)
    assert isinstance(run.counterexamples[0], CounterexampleRecord)
    assert isinstance(run.refinement_decisions[0], RefinementDecision)
    assert isinstance(run.search_ledger, SearchLedger)
    assert isinstance(run.design_record, DesignRecordV0)
    assert run.status == "shadow_ready"
    assert run.search_ledger.counterexample_conversion_rate == 1.0
    assert run.search_ledger.acquisition_branch_state == "bridge_missing"
    assert run.design_record.projection_status == "shadow"
    assert run.design_record.candidate_ref == run.candidates[0].candidate_ref
    assert run.design_record.ledger_refs == [run.search_ledger.ledger_ref]
    assert run.design_record.axis_positions
    assert run.design_record.firewall_status
    assert run.search_ledger.counterexample_refs == [run.counterexamples[0].counterexample_ref]
    assert run.search_ledger.refinement_decision_refs == [
        run.refinement_decisions[0].decision_ref
    ]
    assert run.refinement_decisions[0].value_of_information.estimate_id == (
        "s2_shadow_refinement_voi"
    )
    assert "production_recommendation" in run.design_record.authority_boundary.may_not_use_for
```

Expected red result:

```text
ImportError: cannot import name 'S2_DESIGN_SEARCH_SCHEMA_VERSION' from 'polisyos.pdc'
```

- [ ] **Step 2: Add red tests for grammar-before-candidate and six counterexample classes**

Append:

```python
def test_s2_candidate_is_derived_from_grammar_before_candidate_emission() -> None:
    run = run_s2_shadow_design_loop(_input())

    candidate = run.candidates[0]
    assert candidate.grammar_expansion_ref == run.grammar_expansion.expansion_ref
    assert candidate.source_authority == "deterministic_producer"
    assert candidate.field_source_classification["instrument_family"] == "deterministic_grammar"
    assert candidate.field_source_classification["parameterization"] == "deterministic_grammar"
    assert run.grammar_expansion.instrument_families[:2] == [
        "credit_guarantee",
        "interest_rate_buydown",
    ]
    assert "cash_grant" in run.grammar_expansion.instrument_families


def test_s2_counterexample_classes_are_governed_and_typed() -> None:
    run = run_s2_shadow_design_loop(_input())

    assert set(run.search_ledger.counterexample_class_vocabulary) == {
        "real_design_blocker",
        "substrate_gap",
        "a_spec_gap",
        "abstraction_gap",
        "value_gap",
        "budget_gap",
    }
    assert {record.counterexample_class for record in run.counterexamples} == {
        "real_design_blocker"
    }
    assert run.counterexamples[0].diagnostic.severity == "block"
    assert run.counterexamples[0].diagnostic.authority_purpose == "shadow_design_search_replay"
```

Expected red result remains the missing public surface import.

- [ ] **Step 3: Add red negative controls**

Append:

```python
def test_s2_a_spec_gap_routes_to_governance_not_self_repair() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "a_spec_gap"})
    )

    assert run.status == "governance_required"
    assert run.refinement_decisions[0].decision == "human_decision"
    assert run.refinement_decisions[0].next_candidate_ref is None
    assert run.refinement_decisions[0].governance_decision_class_ref == "a_spec_gap"
    assert run.refinement_decisions[0].governance_decision_class is not None
    assert "governance://layer2/s2/a_spec_gap" in run.refinement_decisions[0].governance_refs


def test_s2_substrate_gap_requests_acquisition_without_claiming_acquisition() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "substrate_gap"})
    )

    assert run.status == "acquisition_required"
    assert run.refinement_decisions[0].decision == "acquire"
    assert run.refinement_decisions[0].next_candidate_ref is None
    assert run.search_ledger.acquisition_branch_state == "bridge_missing"
    assert "acquisition_authority" in run.design_record.authority_boundary.may_not_use_for


def test_s2_budget_gap_abstains_with_honest_search_incompleteness() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "budget_gap"})
    )

    assert run.status == "abstained"
    assert run.refinement_decisions[0].decision == "abstain"
    assert run.refinement_decisions[0].next_candidate_ref is None
    assert "best_known_shadow_frontier" in run.search_ledger.search_incompleteness_note
    assert "production_recommendation" in run.design_record.authority_boundary.may_not_use_for


def test_s2_blocked_candidate_cannot_be_retried_into_pass_without_new_grammar() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"force_retry_same_candidate": True})
    )

    assert run.status == "blocked"
    assert run.refinement_decisions[0].decision == "block_candidate"
    assert run.search_ledger.no_retry_without_new_grammar is True
    assert run.search_ledger.iterations[-1].status == "blocked_no_retry"


def test_s2_llm_only_candidate_without_grammar_derivation_fails_p15() -> None:
    with pytest.raises(
        Layer2S2DesignSearchInputError,
        match="llm_candidate requires grammar_expansion_ref and remains shadow-only",
    ):
        run_s2_shadow_design_loop(
            _input().model_copy(
                update={
                    "candidate_source_authority": "llm_candidate",
                    "omit_grammar_derivation": True,
                }
            )
        )
```

- [ ] **Step 4: Add red projection and replay tests**

Append:

```python
def test_s2_replay_key_is_deterministic_for_same_input() -> None:
    first = run_s2_shadow_design_loop(_input())
    second = run_s2_shadow_design_loop(_input())

    assert first.search_ledger.deterministic_replay_key == (
        second.search_ledger.deterministic_replay_key
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_s2_machine_and_reviewer_projection_expose_trace_without_authority() -> None:
    run = run_s2_shadow_design_loop(_input())

    projections = project_s2_design_search(run, audiences=("MACHINE", "REVIEWER"))

    assert set(projections) == {"MACHINE", "REVIEWER"}
    assert projections["MACHINE"]["search_ledger_ref"] == run.search_ledger.ledger_ref
    assert projections["MACHINE"]["grammar_diversity_minimum"] == 3
    assert projections["REVIEWER"]["counterexample_conversion_rate"] == 1.0
    assert "best_known_shadow_frontier" in projections["REVIEWER"][
        "search_incompleteness_note"
    ]
    assert "publication_authority" in projections["REVIEWER"]["authority_boundary"][
        "may_not_use_for"
    ]
```

- [ ] **Step 5: Run red test command**

```bash
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
```

Expected output:

```text
ERROR tests/unit/pdc/test_layer2_s2_design_search.py
ImportError: cannot import name 'S2_DESIGN_SEARCH_SCHEMA_VERSION' from 'polisyos.pdc'
```

- [ ] **Step 6: Commit Task 1**

```bash
git add tests/unit/pdc/test_layer2_s2_design_search.py
git commit -m "test: add layer2 s2 design search red tests"
```

---

## Task 2: Typed S2 Design Search Contracts And Producer

**Files:**

- Create: `src/polisyos/pdc/_impl/layer2_design_search.py`
- Modify: `src/polisyos/pdc/__init__.py`
- Test: `tests/unit/pdc/test_layer2_s2_design_search.py`

- [ ] **Step 1: Add the typed S2 module**

Create `src/polisyos/pdc/_impl/layer2_design_search.py` with strict Pydantic models:

```python
"""Layer 2 S2 shadow design-search contracts and deterministic producer."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from polisyos.core import artifacts, canon

from .layer2_readiness import (
    AuthorityBoundary,
    AxisFirewallStatus,
    AxisPositionDeclaration,
    CertifiedOperationEnvelope,
    DesignRecordV0,
    GovernanceDecisionClass,
    Layer2ReadinessModel,
    ValueOfInformationEstimate,
)

S2_DESIGN_SEARCH_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s2_design_search.v1"
S2_DESIGN_RECORD_RULE_VERSION = "policyos.layer2.s2.design_search.v1"

CounterexampleClass = Literal[
    "real_design_blocker",
    "substrate_gap",
    "a_spec_gap",
    "abstraction_gap",
    "value_gap",
    "budget_gap",
]
FieldSourceClass = Literal[
    "deterministic_grammar",
    "llm_candidate",
    "human_reviewer",
    "corpus_exemplar",
    "producer_derived_constraint",
]
S2RunStatus = Literal[
    "shadow_ready",
    "blocked",
    "governance_required",
    "acquisition_required",
    "abstained",
]
RefinementDecisionKind = Literal[
    "refine",
    "acquire",
    "reframe",
    "decompose",
    "human_decision",
    "abstain",
    "block_candidate",
]


class Layer2S2DesignSearchInputError(ValueError):
    """Raised when S2 shadow design-search input violates firewalls."""


class Layer2S2DesignSearchInput(Layer2ReadinessModel):
    """Input for the deterministic one-case S2 shadow design-search loop."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    case_id: str = Field(..., min_length=1)
    intent_ref: str = Field(..., min_length=1)
    grammar_ref: str = Field(..., min_length=1)
    actor_ref: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    objective_refs: tuple[str, ...] = Field(..., min_length=1)
    construct_refs: tuple[str, ...] = Field(..., min_length=1)
    authority_profile_ref: str = Field(..., min_length=1)
    requested_posture: Literal["shadow"] = "shadow"
    generated_at: datetime
    rule_version_ref: str = S2_DESIGN_RECORD_RULE_VERSION
    forced_counterexample_class: CounterexampleClass | None = None
    force_retry_same_candidate: bool = False
    candidate_source_authority: Literal["deterministic_producer", "llm_candidate"] = (
        "deterministic_producer"
    )
    omit_grammar_derivation: bool = False


class TypedDiagnosticRecord(Layer2ReadinessModel):
    """Design-time diagnostic carried by S2 counterexamples."""

    diagnostic_id: str
    code: str
    severity: Literal["warn", "block", "governance_required"]
    message: str
    authority_purpose: str
    owner: str
    rule_version_ref: str


class DesignGrammarExpansion(Layer2ReadinessModel):
    """Grammar-derived design-space expansion used before candidate emission."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    expansion_id: str
    expansion_ref: str
    case_id: str
    intent_ref: str
    source_grammar_ref: str
    instrument_families: list[str] = Field(..., min_length=2)
    parameter_space: dict[str, list[str]]
    constraints: list[str]
    construct_demand_refs: list[str]
    authority_boundary: AuthorityBoundary
    generated_at: datetime


class DesignCandidateV0(Layer2ReadinessModel):
    """S2 minimal typed design candidate produced from grammar expansion."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    candidate_id: str
    candidate_ref: str
    case_id: str
    grammar_expansion_ref: str
    instrument_family: str
    parameterization: dict[str, str]
    objective_refs: list[str]
    construct_refs: list[str]
    source_authority: Literal["deterministic_producer", "llm_candidate"]
    field_source_classification: dict[str, FieldSourceClass]
    authority_boundary: AuthorityBoundary
    status: Literal["candidate_unverified", "a_verified_shadow", "blocked"]

    @model_validator(mode="after")
    def _validate_grammar_first(self) -> DesignCandidateV0:
        if not self.grammar_expansion_ref:
            raise ValueError("DesignCandidateV0 requires grammar_expansion_ref")
        if self.source_authority == "llm_candidate" and self.status != "candidate_unverified":
            raise ValueError("llm_candidate cannot become A-verified authority")
        return self


class ConstraintStoreSnapshot(Layer2ReadinessModel):
    """Snapshot of S2 constraints consumed by A-side verification."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    snapshot_id: str
    snapshot_ref: str
    grammar_expansion_ref: str
    constraint_ids: list[str]
    hard_constraint_ids: list[str]
    governance_owned_gap_ids: list[str]


class CounterexampleRecord(Layer2ReadinessModel):
    """Typed counterexample emitted by S2 A-verification."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    counterexample_id: str
    counterexample_ref: str
    case_id: str
    candidate_ref: str
    counterexample_class: CounterexampleClass
    diagnostic: TypedDiagnosticRecord
    evidence_refs: list[str]
    routed_to: Literal[
        "refinement_policy",
        "acquisition",
        "governance",
        "abstention",
        "blocked",
    ]


class RefinementDecision(Layer2ReadinessModel):
    """Decision produced by consuming typed S2 counterexamples."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    decision_id: str
    decision_ref: str
    case_id: str
    candidate_ref: str
    consumed_counterexample_refs: list[str]
    decision: RefinementDecisionKind
    next_candidate_ref: str | None = None
    value_of_information: ValueOfInformationEstimate
    budget_refs: list[str] = Field(..., min_length=1)
    stakes_band: Literal["low", "moderate", "high", "high_stakes"]
    governance_decision_class_ref: str | None = None
    governance_decision_class: GovernanceDecisionClass | None = None
    governance_refs: list[str] = Field(default_factory=list)
    reason: str

    @model_validator(mode="after")
    def _validate_governance_handoff(self) -> RefinementDecision:
        if self.decision == "human_decision" and not self.governance_decision_class_ref:
            raise ValueError("human_decision requires governance_decision_class_ref")
        if self.governance_decision_class and (
            self.governance_decision_class.decision_class_id
            != self.governance_decision_class_ref
        ):
            raise ValueError("governance decision class ref mismatch")
        return self


class SearchIteration(Layer2ReadinessModel):
    """Single replay-visible S2 search iteration."""

    iteration_id: str
    candidate_ref: str
    counterexample_refs: list[str]
    refinement_decision_ref: str
    status: Literal[
        "blocked",
        "blocked_no_retry",
        "governance_required",
        "acquisition_required",
        "abstained",
        "refined_shadow",
    ]


class SearchLedger(Layer2ReadinessModel):
    """Replayable S2 search ledger."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    ledger_id: str
    ledger_ref: str
    case_id: str
    iterations: list[SearchIteration]
    candidate_refs: list[str]
    counterexample_refs: list[str]
    refinement_decision_refs: list[str]
    deterministic_replay_key: str
    counterexample_conversion_rate: float
    grammar_diversity_minimum: int
    instrument_family_coverage: list[str]
    counterexample_class_vocabulary: list[str]
    acquisition_branch_state: Literal["bridge_missing"] = "bridge_missing"
    no_retry_without_new_grammar: bool
    search_incompleteness_note: str


class ClusterInterfaceContract(Layer2ReadinessModel):
    """Typed cluster blackboard interface used by S2 handoffs."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    contract_id: str
    cell_ref: str
    publishes: list[str]
    consumes: list[str]
    authority_boundary: AuthorityBoundary


class ClusterHandoffRecord(Layer2ReadinessModel):
    """Typed handoff record proving Scientist/design workflow did not launder authority."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    handoff_id: str
    workflow_ref: str
    source_cell_ref: str
    target_cell_ref: str
    artifact_refs: list[str]
    disposition: Literal["emitted", "consumed", "rejected", "blocked"]
    authority_purpose: str
    may_not_use_for: list[str]


class Layer2S2DesignSearchRun(Layer2ReadinessModel):
    """Complete S2 shadow design-search run."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    run_id: str
    status: S2RunStatus
    grammar_expansion: DesignGrammarExpansion
    constraint_store: ConstraintStoreSnapshot
    candidates: list[DesignCandidateV0]
    counterexamples: list[CounterexampleRecord]
    refinement_decisions: list[RefinementDecision]
    search_ledger: SearchLedger
    cluster_interface_contracts: list[ClusterInterfaceContract]
    handoff_records: list[ClusterHandoffRecord]
    design_record: DesignRecordV0
```

- [ ] **Step 2: Implement the deterministic producer**

Add to the same file:

```python
def run_s2_shadow_design_loop(
    input: Layer2S2DesignSearchInput,
) -> Layer2S2DesignSearchRun:
    """Run the deterministic S2 one-case shadow design-search loop."""

    if input.candidate_source_authority == "llm_candidate" and input.omit_grammar_derivation:
        raise Layer2S2DesignSearchInputError(
            "llm_candidate requires grammar_expansion_ref and remains shadow-only"
        )
    boundary = _shadow_boundary(input)
    run_id = f"layer2.s2.{_slug(input.case_id)}"
    expansion = _grammar_expansion(input, boundary=boundary)
    candidate = _candidate(input, expansion=expansion, boundary=boundary)
    constraint_store = _constraint_store(input, expansion=expansion)
    counterexample = _counterexample(input, candidate=candidate)
    decision = _refinement_decision(
        input,
        candidate=candidate,
        counterexample=counterexample,
    )
    iteration_status = _iteration_status(input, decision)
    ledger = _search_ledger(
        input,
        candidate=candidate,
        counterexample=counterexample,
        decision=decision,
        iteration_status=iteration_status,
    )
    design_record = _design_record(
        input,
        candidate=candidate,
        ledger=ledger,
        boundary=boundary,
    )
    status: S2RunStatus = (
        "governance_required"
        if decision.decision == "human_decision"
        else "acquisition_required"
        if decision.decision == "acquire"
        else "abstained"
        if decision.decision == "abstain"
        else "blocked"
        if decision.decision == "block_candidate"
        else "shadow_ready"
    )
    return Layer2S2DesignSearchRun(
        run_id=run_id,
        status=status,
        grammar_expansion=expansion,
        constraint_store=constraint_store,
        candidates=[candidate],
        counterexamples=[counterexample],
        refinement_decisions=[decision],
        search_ledger=ledger,
        cluster_interface_contracts=_cluster_interfaces(boundary),
        handoff_records=_handoff_records(candidate, expansion, ledger),
        design_record=design_record,
    )
```

Implementation requirements:

- `_grammar_expansion` must emit `instrument_families=["credit_guarantee", "interest_rate_buydown", "cash_grant"]` and `SearchLedger.grammar_diversity_minimum=3`.
- `_candidate` must use `instrument_family="credit_guarantee"` and `grammar_expansion_ref=expansion.expansion_ref`.
- `_candidate` must set `field_source_classification` for at least `instrument_family`, `parameterization`, `objective_refs`, and `construct_refs`; the first two are `deterministic_grammar`.
- `_counterexample` defaults to `counterexample_class="real_design_blocker"`.
- `forced_counterexample_class="a_spec_gap"` must set `routed_to="governance"`, decision `human_decision`, and `governance_decision_class_ref="a_spec_gap"`.
- `forced_counterexample_class="substrate_gap"` must set `routed_to="acquisition"` and decision `acquire`, while preserving `acquisition_branch_state="bridge_missing"` because S3 owns the acquisition bridge.
- `forced_counterexample_class="budget_gap"` must set `routed_to="abstention"`, decision `abstain`, and a `search_incompleteness_note` containing `best_known_shadow_frontier`.
- Every `RefinementDecision` must carry `ValueOfInformationEstimate`, `budget_refs`, and `stakes_band`; these are scheduling/governance inputs only and cannot override authority floors.
- `force_retry_same_candidate=True` must set decision `block_candidate` and ledger iteration `blocked_no_retry`.
- `counterexample_conversion_rate` is computed as typed counterexamples divided by failed candidates, and must be `1.0` for this slice.
- The deterministic replay key is `sha256` over canonical JSON fields: `case_id`, `intent_ref`, `grammar_ref`, `objective_refs`, `construct_refs`, `candidate_ref`, `counterexample_class`, `decision`, `value_of_information.estimate_id`, and `budget_refs`.

- [ ] **Step 3: Add MACHINE/REVIEWER projection helper**

Add:

```python
def project_s2_design_search(
    run: Layer2S2DesignSearchRun,
    *,
    audiences: tuple[Literal["MACHINE", "REVIEWER"], ...],
) -> dict[str, dict[str, object]]:
    """Project S2 search trace without minting recommendation authority."""

    projections: dict[str, dict[str, object]] = {}
    boundary = run.design_record.authority_boundary.model_dump(mode="json")
    for audience in audiences:
        projections[audience] = {
            "schema_version": S2_DESIGN_SEARCH_SCHEMA_VERSION,
            "audience": audience,
            "status": run.status,
            "design_record_id": run.design_record.record_id,
            "search_ledger_ref": run.search_ledger.ledger_ref,
            "candidate_refs": list(run.search_ledger.candidate_refs),
            "counterexample_refs": list(run.search_ledger.counterexample_refs),
            "refinement_decision_refs": list(run.search_ledger.refinement_decision_refs),
            "counterexample_conversion_rate": run.search_ledger.counterexample_conversion_rate,
            "grammar_diversity_minimum": run.search_ledger.grammar_diversity_minimum,
            "instrument_family_coverage": list(run.search_ledger.instrument_family_coverage),
            "acquisition_branch_state": run.search_ledger.acquisition_branch_state,
            "search_incompleteness_note": run.search_ledger.search_incompleteness_note,
            "authority_boundary": boundary,
        }
    return projections
```

- [ ] **Step 4: Export S2 public surface**

Modify `src/polisyos/pdc/__init__.py` to export:

```python
from ._impl.layer2_design_search import (
    S2_DESIGN_SEARCH_SCHEMA_VERSION,
    ClusterHandoffRecord,
    ClusterInterfaceContract,
    ConstraintStoreSnapshot,
    CounterexampleRecord,
    DesignCandidateV0,
    DesignGrammarExpansion,
    Layer2S2DesignSearchInput,
    Layer2S2DesignSearchInputError,
    Layer2S2DesignSearchRun,
    RefinementDecision,
    SearchLedger,
    TypedDiagnosticRecord,
    project_s2_design_search,
    run_s2_shadow_design_loop,
)
```

Add the same names to `__all__`.

- [ ] **Step 5: Run green unit test command**

```bash
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
```

Expected output:

```text
10 passed
```

- [ ] **Step 6: Run focused style check**

```bash
uv run ruff check src/polisyos/pdc/_impl/layer2_design_search.py tests/unit/pdc/test_layer2_s2_design_search.py
```

Expected output:

```text
All checks passed!
```

- [ ] **Step 7: Commit Task 2**

```bash
git add src/polisyos/pdc/_impl/layer2_design_search.py src/polisyos/pdc/__init__.py tests/unit/pdc/test_layer2_s2_design_search.py
git commit -m "feat: add layer2 s2 shadow design search contracts"
```

---

## Task 3: Persisted Ledger And Replay Surface

**Files:**

- Modify: `src/polisyos/pdc/_impl/layer2_design_search.py`
- Modify: `tests/unit/pdc/test_layer2_s2_design_search.py`

- [ ] **Step 1: Add failing persistence and replay tests**

Append:

```python
def test_s2_persists_design_record_and_search_ledger(tmp_path: Path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.pdc import persist_s2_design_search_run

    run = run_s2_shadow_design_loop(_input())
    store = FileSystemCAS(tmp_path / "cas")
    refs = persist_s2_design_search_run(run, store=store)

    assert refs["design_record"].kind == "policyos.layer2_s2.design_record_v0"
    assert refs["search_ledger"].kind == "policyos.layer2_s2.search_ledger"
    assert refs["design_record"].media_type == "application/json"
    assert refs["search_ledger"].media_type == "application/json"
    design_record = json.loads(store.get_bytes(refs["design_record"].artifact_id))
    search_ledger = json.loads(store.get_bytes(refs["search_ledger"].artifact_id))
    assert design_record["record_id"] == run.design_record.record_id
    assert search_ledger["deterministic_replay_key"] == run.search_ledger.deterministic_replay_key


def test_s2_loaded_ledger_replays_same_key(tmp_path: Path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.pdc import load_s2_search_ledger, persist_s2_design_search_run

    run = run_s2_shadow_design_loop(_input())
    store = FileSystemCAS(tmp_path / "cas")
    refs = persist_s2_design_search_run(run, store=store)
    loaded = load_s2_search_ledger(store=store, artifact_ref=refs["search_ledger"])

    assert loaded == run.search_ledger
```

Expected red:

```text
ImportError: cannot import name 'persist_s2_design_search_run'
```

- [ ] **Step 2: Implement persistence helpers**

Add to `layer2_design_search.py`:

```python
def persist_s2_design_search_run(
    run: Layer2S2DesignSearchRun,
    *,
    store: artifacts.FileSystemCAS,
) -> dict[str, artifacts.ArtifactRef]:
    """Persist S2 DesignRecordV0 and SearchLedger as canonical CAS artifacts."""

    producer = artifacts.ProducerInfo(
        component="polisyos.pdc.layer2_design_search",
        version=S2_DESIGN_RECORD_RULE_VERSION,
    )
    design_record_ref = store.put_json(
        run.design_record.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="policyos.layer2_s2.design_record_v0",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="policyos.layer2_s2.design_record_v0",
                version=run.design_record.schema_version,
            ),
            producer=producer,
        ),
        canon_spec=canon.CanonSpec(),
    )
    search_ledger_ref = store.put_json(
        run.search_ledger.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="policyos.layer2_s2.search_ledger",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="policyos.layer2_s2.search_ledger",
                version=S2_DESIGN_SEARCH_SCHEMA_VERSION,
            ),
            producer=producer,
        ),
        canon_spec=canon.CanonSpec(),
    )
    return {
        "design_record": design_record_ref,
        "search_ledger": search_ledger_ref,
    }


def load_s2_search_ledger(
    *,
    store: artifacts.FileSystemCAS,
    artifact_ref: artifacts.ArtifactRef,
) -> SearchLedger:
    """Load a persisted S2 SearchLedger from CAS."""

    return SearchLedger.model_validate_json(store.get_bytes(artifact_ref.artifact_id))
```

Export both names from `polisyos.pdc`.

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
```

Expected output:

```text
12 passed
```

- [ ] **Step 4: Commit Task 3**

```bash
git add src/polisyos/pdc/_impl/layer2_design_search.py src/polisyos/pdc/__init__.py tests/unit/pdc/test_layer2_s2_design_search.py
git commit -m "feat: persist layer2 s2 search ledger and design record"
```

---

## Task 4: Canonical Corpus Route Wiring

**Files:**

- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`
- Modify: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`

- [ ] **Step 1: Add failing canonical route tests**

Add to `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`:

```python
def test_w12d_corpus_route_emits_s2_shadow_design_search_for_first_proving_case(
    tmp_path: Path,
) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
    )

    case = report["cases"][0]
    s2 = case["s2_design_search"]
    assert s2["status"] == "shadow_ready"
    assert s2["search_ledger"]["counterexample_conversion_rate"] == 1.0
    assert s2["search_ledger"]["grammar_diversity_minimum"] == 3
    assert set(s2["search_ledger"]["counterexample_class_vocabulary"]) == {
        "real_design_blocker",
        "substrate_gap",
        "a_spec_gap",
        "abstraction_gap",
        "value_gap",
        "budget_gap",
    }
    assert s2["search_ledger"]["acquisition_branch_state"] == "bridge_missing"
    assert s2["design_record"]["projection_status"] == "shadow"
    assert "production_recommendation" in s2["design_record"]["authority_boundary"][
        "may_not_use_for"
    ]


def test_w12d_s2_shadow_search_does_not_change_canonical_closeout_outcome(
    tmp_path: Path,
) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
    )

    case = report["cases"][0]
    assert case["s2_design_search"]["status"] == "shadow_ready"
    assert case["s2_design_search"]["canonical_outcome_effect"] == "none_shadow_only"
    assert case["outcome"] in {"accepted_deficit", "publish-with-limitation", "typed_blocker"}
```

Expected red:

```text
KeyError: 's2_design_search'
```

- [ ] **Step 2: Wire S2 into the canonical corpus route as shadow-only**

In `tools/quality/validation/run_universal_outcome_corpus.py`, import:

```python
from polisyos.pdc import (
    Layer2S2DesignSearchInput,
    run_s2_shadow_design_loop,
)
```

Add a helper:

```python
def _s2_design_search_summary(case: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    case_id = str(case.get("case_id") or case.get("id") or "")
    if case_id != "ua-msme-affordable-loans-2022":
        return {"status": "not_applicable", "canonical_outcome_effect": "none_shadow_only"}
    input_row = Layer2S2DesignSearchInput(
        case_id=case_id,
        intent_ref="repo://architecture/policy_design_case/layer2_first_proving_case.json",
        grammar_ref="repo://src/polisyos/policy_grammar",
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=(
            "objective://credit_program_enrollment",
            "objective://firm_survival",
            "objective://regional_displacement_pressure",
            "objective://credit_access",
            "objective://fiscal_burden_per_beneficiary",
        ),
        construct_refs=(
            "construct://credit_program_enrollment",
            "construct://firm_survival",
            "construct://regional_displacement_pressure",
            "construct://credit_access",
            "construct://fiscal_burden_per_beneficiary",
        ),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=datetime.fromisoformat(GENERATED_AT.replace("Z", "+00:00")),
        rule_version_ref="policyos.layer2.s2.design_search.v1",
    )
    run = run_s2_shadow_design_loop(input_row)
    return {
        "status": run.status,
        "canonical_outcome_effect": "none_shadow_only",
        "search_ledger": run.search_ledger.model_dump(mode="json"),
        "design_record": run.design_record.model_dump(mode="json"),
        "handoff_records": [row.model_dump(mode="json") for row in run.handoff_records],
    }
```

In `_run_case`, add `s2_design_search = _s2_design_search_summary(case, repo_root=repo_root)` and include `"s2_design_search": s2_design_search` in the returned case dictionary. Do not read expert labels as S2 runtime input.

- [ ] **Step 3: Run canonical route tests**

```bash
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q -k "s2 or s1 or canonical_outcome_consumes"
```

Expected output:

```text
4 passed
```

- [ ] **Step 4: Commit Task 4**

```bash
git add tools/quality/validation/run_universal_outcome_corpus.py tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py
git commit -m "feat: wire layer2 s2 shadow search into corpus route"
```

---

## Task 5: S2 Manifest And Readiness Validator

**Files:**

- Create: `architecture/policy_design_case/layer2_s2_design_search_manifest.json`
- Create: `tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`

- [ ] **Step 1: Add the S2 manifest**

Create `architecture/policy_design_case/layer2_s2_design_search_manifest.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s2_design_search_manifest.v1",
  "status": "active",
  "slice": "S2",
  "slice_label": "grammar_candidate_search_design_record_v0",
  "owner": "team-design-generation",
  "promotion": "shadow_only",
  "cells_closed": [
    "INTERVENTION.design_grammar",
    "INTERVENTION.design_candidate"
  ],
  "layer_contributions": [
    {
      "cell_ref": "CROSS_CUTTING.scientist_orchestration",
      "contribution": "generation_handoff",
      "artifact": "ClusterHandoffRecord",
      "ratchet_state_after_s2": "implemented_but_not_orchestrated",
      "closure_owner_slice": "S7"
    }
  ],
  "open_cell_count_baseline": 17,
  "expected_current_open_cell_count": 15,
  "first_proving_case_id": "ua-msme-affordable-loans-2022",
  "required_artifacts": [
    "DesignGrammarExpansion",
    "DesignCandidateV0",
    "ConstraintStoreSnapshot",
    "CounterexampleRecord",
    "RefinementDecision",
    "SearchLedger",
    "ClusterInterfaceContract",
    "ClusterHandoffRecord",
    "DesignRecordV0"
  ],
  "counterexample_class_vocabulary": [
    "real_design_blocker",
    "substrate_gap",
    "a_spec_gap",
    "abstraction_gap",
    "value_gap",
    "budget_gap"
  ],
  "floors": [
    {
      "floor_id": "s2_counterexample_conversion",
      "metric": "counterexample_conversion_rate",
      "required_value": 1.0,
      "owner": "team-runtime-quality"
    }
  ],
  "shadow_adequacy_checks": [
    {
      "check_id": "s2_shadow_grammar_diversity",
      "metric": "instrument_family_coverage_count",
      "required_value": 3,
      "owner": "team-design-generation",
      "rationale": "S2 shadow grammar must not collapse to variants of one instrument family."
    }
  ],
  "required_governance_decision_classes": ["a_spec_gap"],
  "required_voi_sites": ["s2_refinement_policy"],
  "acquisition_branch_state": "bridge_missing",
  "projection_audiences": ["MACHINE", "REVIEWER"],
  "authority_scope": "shadow_design_search_replay",
  "may_not_use_for": [
    "production_recommendation",
    "publication_authority",
    "rollout_authority",
    "claim_authority",
    "production_closeout_authority",
    "acquisition_authority",
    "source_contract_authority"
  ],
  "validator": "tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py",
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py",
  "rule_version_ref": "policyos.layer2.s2.design_search.v1",
  "firewalls": ["P05", "P10", "P12", "P15", "P25"]
}
```

- [ ] **Step 2: Add failing repo-quality tests**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`:

```python
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from polisyos.pdc import Layer2S2DesignSearchInputError
from tools.quality.validation import (
    check_policy_design_case_layer2_s2_design_search as s2_validator,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "architecture/policy_design_case/layer2_s2_design_search_manifest.json"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_s2_manifest_declares_closed_cells_and_shadow_scope() -> None:
    manifest = _manifest()

    assert manifest["slice"] == "S2"
    assert manifest["cells_closed"] == [
        "INTERVENTION.design_grammar",
        "INTERVENTION.design_candidate",
    ]
    assert manifest["layer_contributions"][0]["cell_ref"] == (
        "CROSS_CUTTING.scientist_orchestration"
    )
    assert manifest["layer_contributions"][0]["closure_owner_slice"] == "S7"
    assert manifest["open_cell_count_baseline"] == 17
    assert manifest["expected_current_open_cell_count"] == 15
    assert manifest["promotion"] == "shadow_only"
    assert {row["floor_id"] for row in manifest["floors"]} == {
        "s2_counterexample_conversion",
    }
    assert {row["check_id"] for row in manifest["shadow_adequacy_checks"]} == {
        "s2_shadow_grammar_diversity",
    }
    assert manifest["required_governance_decision_classes"] == ["a_spec_gap"]
    assert manifest["required_voi_sites"] == ["s2_refinement_policy"]
    assert "production_recommendation" in manifest["may_not_use_for"]


def test_s2_validator_blocks_until_cluster_map_closes_s2_cells() -> None:
    summary = s2_validator.validate_s2_design_search(repo_root=REPO_ROOT)

    assert summary["status"] == "fail"
    assert summary["slice"] == "S2"
    assert summary["first_proving_case_id"] == "ua-msme-affordable-loans-2022"
    assert summary["current_open_cell_count"] == 17
    assert summary["expected_current_open_cell_count"] == 15
    assert summary["cells_closed"] == [
        "INTERVENTION.design_grammar",
        "INTERVENTION.design_candidate",
    ]
    assert "s2_cluster_open_cell_count_unexpected" in {
        issue["code"] for issue in summary["issues"]
    }
    assert summary["counterexample_conversion_rate"] == 1.0
    assert summary["grammar_diversity_minimum"] == 3
    assert summary["governance_decision_classes_verified"] == ["a_spec_gap"]
    assert summary["voi_sites_verified"] == ["s2_refinement_policy"]
    assert summary["acquisition_branch_state"] == "bridge_missing"
    assert summary["projection_audiences_verified"] == ["MACHINE", "REVIEWER"]
    assert summary["canonical_route_status"] == "pass"


def test_s2_validator_rejects_llm_only_candidate_negative_control() -> None:
    with pytest.raises(Layer2S2DesignSearchInputError):
        s2_validator.validate_llm_only_candidate_negative_control()


def test_s2_validator_rejects_manifest_that_claims_acquisition() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["acquisition_branch_state"] = "implemented"

    validation = s2_validator.validate_s2_manifest_payload(manifest)

    assert validation["status"] == "fail"
    assert "s2_acquisition_branch_must_remain_bridge_missing" in {
        issue["code"] for issue in validation["issues"]
    }
```

Expected red:

```text
ImportError: cannot import name 'check_policy_design_case_layer2_s2_design_search'
```

- [ ] **Step 3: Implement S2 validator**

Create `tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py` with these public functions and implementations:

```python
def validate_s2_design_search(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Validate S2 design search from manifest through canonical corpus wiring."""

    root = Path(repo_root).resolve()
    manifest = _load_json(root / DEFAULT_MANIFEST_PATH)
    manifest_validation = validate_s2_manifest_payload(manifest)
    if manifest_validation["status"] != "pass":
        return manifest_validation
    input_row = _first_proving_case_input(root)
    run = run_s2_shadow_design_loop(input_row)
    a_spec_run = run_s2_shadow_design_loop(
        input_row.model_copy(update={"forced_counterexample_class": "a_spec_gap"})
    )
    substrate_gap_run = run_s2_shadow_design_loop(
        input_row.model_copy(update={"forced_counterexample_class": "substrate_gap"})
    )
    budget_gap_run = run_s2_shadow_design_loop(
        input_row.model_copy(update={"forced_counterexample_class": "budget_gap"})
    )
    projections = project_s2_design_search(run, audiences=("MACHINE", "REVIEWER"))
    cluster_summary = _cluster_summary(root)
    canonical_status = _canonical_route_status(root)
    governed_floor_ids = _floor_governance_ids(root)
    issues: list[dict[str, str]] = []
    _expect(
        run.search_ledger.counterexample_conversion_rate == 1.0,
        "s2_counterexample_conversion_floor_failed",
        issues,
    )
    _expect(
        "s2_counterexample_conversion" in governed_floor_ids,
        "s2_counterexample_conversion_floor_not_governed",
        issues,
    )
    _expect(
        run.search_ledger.grammar_diversity_minimum == 3
        and len(set(run.search_ledger.instrument_family_coverage)) >= 3,
        "s2_grammar_diversity_adequacy_failed",
        issues,
    )
    _expect(
        run.refinement_decisions[0].value_of_information.estimate_id
        == "s2_shadow_refinement_voi",
        "s2_refinement_voi_missing",
        issues,
    )
    _expect(
        a_spec_run.status == "governance_required"
        and a_spec_run.refinement_decisions[0].governance_decision_class_ref
        == "a_spec_gap",
        "s2_governance_decision_class_invalid",
        issues,
    )
    _expect(
        substrate_gap_run.status == "acquisition_required"
        and substrate_gap_run.search_ledger.acquisition_branch_state == "bridge_missing",
        "s2_substrate_gap_acquisition_bridge_invalid",
        issues,
    )
    _expect(
        budget_gap_run.status == "abstained"
        and "best_known_shadow_frontier"
        in budget_gap_run.search_ledger.search_incompleteness_note,
        "s2_budget_gap_abstention_invalid",
        issues,
    )
    _expect(
        run.search_ledger.acquisition_branch_state == "bridge_missing",
        "s2_acquisition_branch_not_bridge_missing",
        issues,
    )
    _expect(
        list(projections) == ["MACHINE", "REVIEWER"],
        "s2_projection_audiences_missing",
        issues,
    )
    _expect(
        cluster_summary["current_open_cell_count"]
        == int(manifest["expected_current_open_cell_count"]),
        "s2_cluster_open_cell_count_unexpected",
        issues,
    )
    _expect(canonical_status == "pass", "s2_canonical_route_missing", issues)
    return _result(
        issues,
        summary={
            "slice": "S2",
            "first_proving_case_id": input_row.case_id,
            "current_open_cell_count": cluster_summary["current_open_cell_count"],
            "expected_current_open_cell_count": int(
                manifest["expected_current_open_cell_count"]
            ),
            "cells_closed": list(manifest["cells_closed"]),
            "counterexample_conversion_rate": run.search_ledger.counterexample_conversion_rate,
            "grammar_diversity_minimum": run.search_ledger.grammar_diversity_minimum,
            "governance_decision_classes_verified": list(
                manifest["required_governance_decision_classes"]
            ),
            "voi_sites_verified": list(manifest["required_voi_sites"]),
            "acquisition_branch_state": run.search_ledger.acquisition_branch_state,
            "projection_audiences_verified": list(projections),
            "canonical_route_status": canonical_status,
        },
    )


def validate_s2_manifest_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the S2 manifest without touching runtime producers."""

    issues: list[dict[str, str]] = []
    _expect(
        payload.get("schema_version")
        == "policyos.policy_design_case.layer2_s2_design_search_manifest.v1",
        "s2_manifest_schema_version_invalid",
        issues,
    )
    _expect(payload.get("slice") == "S2", "s2_manifest_slice_invalid", issues)
    _expect(
        payload.get("acquisition_branch_state") == "bridge_missing",
        "s2_acquisition_branch_must_remain_bridge_missing",
        issues,
    )
    _expect(
        list(payload.get("cells_closed") or [])
        == [
            "INTERVENTION.design_grammar",
            "INTERVENTION.design_candidate",
        ],
        "s2_cells_closed_invalid",
        issues,
    )
    _expect(
        payload.get("expected_current_open_cell_count") == 15,
        "s2_expected_open_cell_count_invalid",
        issues,
    )
    _expect(
        list(payload.get("counterexample_class_vocabulary") or [])
        == [
            "real_design_blocker",
            "substrate_gap",
            "a_spec_gap",
            "abstraction_gap",
            "value_gap",
            "budget_gap",
        ],
        "s2_counterexample_class_vocabulary_invalid",
        issues,
    )
    floor_ids = {str(row.get("floor_id")) for row in payload.get("floors") or []}
    _expect(
        floor_ids == {"s2_counterexample_conversion"},
        "s2_floor_set_invalid",
        issues,
    )
    adequacy_ids = {
        str(row.get("check_id")) for row in payload.get("shadow_adequacy_checks") or []
    }
    _expect(
        adequacy_ids == {"s2_shadow_grammar_diversity"},
        "s2_shadow_adequacy_check_set_invalid",
        issues,
    )
    _expect(
        list(payload.get("required_governance_decision_classes") or []) == ["a_spec_gap"],
        "s2_required_governance_decision_classes_invalid",
        issues,
    )
    _expect(
        list(payload.get("required_voi_sites") or []) == ["s2_refinement_policy"],
        "s2_required_voi_sites_invalid",
        issues,
    )
    layer_contributions = list(payload.get("layer_contributions") or [])
    _expect(
        len(layer_contributions) == 1
        and layer_contributions[0].get("cell_ref")
        == "CROSS_CUTTING.scientist_orchestration"
        and layer_contributions[0].get("closure_owner_slice") == "S7",
        "s2_scientist_orchestration_must_remain_split",
        issues,
    )
    return _result(issues, summary={"slice": str(payload.get("slice", ""))})


def validate_llm_only_candidate_negative_control() -> None:
    """Raise when an LLM-only candidate has no grammar derivation."""

    run_s2_shadow_design_loop(
        _first_proving_case_input(REPO_ROOT).model_copy(
            update={
                "candidate_source_authority": "llm_candidate",
                "omit_grammar_derivation": True,
            }
        )
    )
```

Validator requirements:

- Load S2 manifest, first proving case, cluster map, floor governance, and inventory.
- Run `run_s2_shadow_design_loop` for `ua-msme-affordable-loans-2022`.
- Verify all required artifacts exist in the run.
- Verify `counterexample_conversion_rate == 1.0`.
- Verify governed floor `s2_counterexample_conversion` is present in `layer2_floor_governance.toml`.
- Verify `grammar_diversity_minimum == 3` and at least three distinct instrument families are covered as an S2 shadow adequacy check, not as a new governed floor.
- Verify `RefinementDecision` carries `ValueOfInformationEstimate`, budget refs, and stakes band.
- Verify `a_spec_gap` produces a typed `GovernanceDecisionClass` handoff and cannot become B-side success.
- Verify `substrate_gap` produces `acquisition_required` while the acquisition bridge remains `bridge_missing`.
- Verify `budget_gap` produces honest `abstained` status and search-incompleteness note.
- Verify `acquisition_branch_state == "bridge_missing"`.
- Verify `project_s2_design_search(run, audiences=("MACHINE", "REVIEWER"))` returns both audiences.
- Verify canonical corpus route includes `s2_design_search.status == "shadow_ready"` for the first proving case.
- Verify `cells_closed` exactly matches the two S2-owned cells.
- Verify `CROSS_CUTTING.scientist_orchestration` appears only under `layer_contributions` with `closure_owner_slice="S7"`.
- Verify manifest `expected_current_open_cell_count == 15`.
- Require current cluster-map open cell count to be `15`; before Task 6 this validator must fail with `s2_cluster_open_cell_count_unexpected`.
- Verify S2 inventory registration once Task 6 is complete.

CLI output shape:

```json
{
  "status": "fail",
  "slice": "S2",
  "first_proving_case_id": "ua-msme-affordable-loans-2022",
  "current_open_cell_count": 17,
  "expected_current_open_cell_count": 15,
  "cells_closed": [
    "INTERVENTION.design_grammar",
    "INTERVENTION.design_candidate"
  ],
  "counterexample_conversion_rate": 1.0,
  "grammar_diversity_minimum": 3,
  "governance_decision_classes_verified": ["a_spec_gap"],
  "voi_sites_verified": ["s2_refinement_policy"],
  "acquisition_branch_state": "bridge_missing",
  "projection_audiences_verified": ["MACHINE", "REVIEWER"],
  "canonical_route_status": "pass",
  "issues": [{"code": "s2_cluster_open_cell_count_unexpected"}]
}
```

- [ ] **Step 4: Run red, then green repo-quality tests**

Before implementation, run:

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py -q
```

Expected red:

```text
ImportError: cannot import name 'check_policy_design_case_layer2_s2_design_search'
```

After implementation, run the same command.

Expected green before Task 6 cluster-map/inventory wiring. This is green because the test now asserts that the final S2 validator remains blocked until Task 6 closes exactly the two S2-owned cells:

```text
4 passed
```

- [ ] **Step 5: Commit Task 5**

```bash
git add architecture/policy_design_case/layer2_s2_design_search_manifest.json tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py
git commit -m "chore: validate layer2 s2 design search"
```

---

## Task 6: Cluster Map, Readiness Progress, And Inventory Wiring

**Files:**

- Modify: `architecture/policy_design_case/cluster_ownership_map.toml`
- Modify: `architecture/policy_design_case/inventory.json`
- Modify: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`

- [ ] **Step 1: Add red readiness tests for post-S2 progress**

Modify `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`.

Change the first readiness test to assert both baseline and current counts:

```python
def test_layer2_s0_readiness_manifest_is_valid() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["open_cell_count_baseline"] == 17  # type: ignore[index]
    assert validation["summary"]["assigned_open_cell_count"] == 17  # type: ignore[index]
    assert validation["summary"]["current_open_cell_count"] == 15  # type: ignore[index]
    assert validation["summary"]["s0_cells_closed"] == []  # type: ignore[index]
    assert validation["summary"]["cells_closed_since_s0"] == [
        "INTERVENTION.design_candidate",
        "INTERVENTION.design_grammar",
    ]  # type: ignore[index]
```

Change `test_layer2_slice_cell_matrix_covers_every_open_cell`:

```python
def test_layer2_slice_cell_matrix_preserves_baseline_and_current_open_subset() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    cluster_map = payloads["cluster_map"]
    current_open_cells = readiness._open_cell_refs(cluster_map)  # type: ignore[attr-defined]
    assigned = {
        str(entry["cell_ref"]) for entry in payloads["slice_cell_matrix"].get("assignment", [])
    }

    assert len(assigned) == 17
    assert current_open_cells < assigned
    assert assigned - current_open_cells == {
        "INTERVENTION.design_candidate",
        "INTERVENTION.design_grammar",
    }
```

Expected red before validator update:

```text
KeyError: 'open_cell_count_baseline'
```

- [ ] **Step 2: Make readiness validator progress-aware**

Modify `tools/quality/validation/check_policy_design_case_layer2_readiness.py`:

- Preserve `open_cell_count_baseline = int(matrix["open_cell_count_baseline"])`.
- Treat slice-cell matrix assignments as baseline assignments.
- Compute `current_open_cells = _open_cell_refs(cluster_payload)`.
- Compute `closed_since_s0 = sorted(assigned_cells - current_open_cells)`.
- Validate `current_open_cells <= assigned_cells`.
- Keep `s0_cells_closed == []`.
- Return summary keys:
  - `open_cell_count_baseline`
  - `current_open_cell_count`
  - `assigned_open_cell_count`
  - `cells_closed_since_s0`
  - `s0_cells_closed`
- Keep compatibility key `open_cell_count` equal to `current_open_cell_count`.

Negative test update:

```python
def test_layer2_readiness_rejects_missing_open_cell_assignment() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["slice_cell_matrix"]["assignment"] = [
        entry
        for entry in payloads["slice_cell_matrix"]["assignment"]
        if entry["cell_ref"] != "KNOWLEDGE.calibration"
    ]

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_slice_cell_matrix_current_open_cell_not_assigned" in _issue_codes(validation)
```

- [ ] **Step 3: Close the two S2-owned cells in cluster map**

Modify these cells in `architecture/policy_design_case/cluster_ownership_map.toml`:

For `[cell.INTERVENTION.design_grammar]`:

```toml
ratchet_state = "implemented"
p01_chain = "implemented"
gap = "none_for_s2_shadow_design_search"
action = "S2 emits DesignGrammarExpansion artifacts consumed by DesignCandidateV0 and projected through MACHINE/REVIEWER search trace."
```

For `[cell.INTERVENTION.design_candidate]`:

```toml
ratchet_state = "implemented"
p01_chain = "implemented"
gap = "none_for_s2_shadow_design_search"
action = "S2 emits grammar-derived DesignCandidateV0 artifacts linked to DesignRecordV0, SearchLedger, and authority firewalls."
```

For `[cell.CROSS_CUTTING.scientist_orchestration]`, do not set `ratchet_state="implemented"` and do not remove its open-cell closure table. Keep it open/split for S7; S2's generation-handoff contribution is recorded in the S2 manifest and inventory, not as whole-cell closure.

Remove only the matching `[open_cell_closure.INTERVENTION.design_grammar]` and `[open_cell_closure.INTERVENTION.design_candidate]` tables. The cluster-map validator rejects closure contracts for non-open cells.

- [ ] **Step 4: Register S2 manifest in inventory**

Add an artifact entry to `architecture/policy_design_case/inventory.json`:

```json
{
  "id": "layer2_s2_design_search_manifest",
  "path": "architecture/policy_design_case/layer2_s2_design_search_manifest.json",
  "kind": "layer2_s2_design_search_manifest",
  "schema_version": "policyos.policy_design_case.layer2_s2_design_search_manifest.v1",
  "owner": "team-design-generation",
  "status": "active",
  "capability_reality_label": "implemented",
  "authority_scope": "shadow_design_search_replay",
  "may_not_use_for": [
    "production_recommendation",
    "publication_authority",
    "rollout_authority",
    "claim_authority",
    "production_closeout_authority",
    "acquisition_authority",
    "source_contract_authority"
  ],
  "validator": "tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py",
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py"
}
```

- [ ] **Step 5: Add inventory assertion to S2 repo-quality test**

First replace `test_s2_validator_blocks_until_cluster_map_closes_s2_cells` with `test_s2_validator_reports_full_loop_and_floor` in
`tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py` so
the final validator passes only after the two S2-owned cells are closed:

```python
def test_s2_validator_reports_full_loop_and_floor() -> None:
    summary = s2_validator.validate_s2_design_search(repo_root=REPO_ROOT)

    assert summary["status"] == "pass"
    assert summary["slice"] == "S2"
    assert summary["first_proving_case_id"] == "ua-msme-affordable-loans-2022"
    assert summary["current_open_cell_count"] == 15
    assert summary["expected_current_open_cell_count"] == 15
    assert summary["cells_closed"] == [
        "INTERVENTION.design_grammar",
        "INTERVENTION.design_candidate",
    ]
    assert summary["counterexample_conversion_rate"] == 1.0
    assert summary["grammar_diversity_minimum"] == 3
    assert summary["governance_decision_classes_verified"] == ["a_spec_gap"]
    assert summary["voi_sites_verified"] == ["s2_refinement_policy"]
    assert summary["acquisition_branch_state"] == "bridge_missing"
    assert summary["projection_audiences_verified"] == ["MACHINE", "REVIEWER"]
    assert summary["canonical_route_status"] == "pass"
```

Then append:

```python
def test_s2_manifest_is_registered_in_inventory() -> None:
    inventory = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/inventory.json").read_text(
            encoding="utf-8"
        )
    )
    artifacts = {str(row["id"]): row for row in inventory["artifacts"]}

    row = artifacts["layer2_s2_design_search_manifest"]
    assert row["path"] == "architecture/policy_design_case/layer2_s2_design_search_manifest.json"
    assert row["schema_version"] == (
        "policyos.policy_design_case.layer2_s2_design_search_manifest.v1"
    )
    assert row["owner"] == "team-design-generation"
    assert row["status"] == "active"
    assert row["capability_reality_label"] == "implemented"
    assert row["authority_scope"] == "shadow_design_search_replay"
    assert "acquisition_authority" in row["may_not_use_for"]
    assert "production_recommendation" in row["may_not_use_for"]
    assert row["validator"] == (
        "tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py"
    )
    assert row["canonical_route"] == (
        "tools/quality/validation/run_universal_outcome_corpus.py"
    )
```

- [ ] **Step 6: Run validators and repo-quality tests**

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py -q
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py
```

Expected:

```text
tests pass
cluster map status=pass with open_cell_count=15
readiness status=pass with open_cell_count_baseline=17 and current_open_cell_count=15
S2 validator status=pass
```

- [ ] **Step 7: Commit Task 6**

```bash
git add architecture/policy_design_case/cluster_ownership_map.toml architecture/policy_design_case/inventory.json tools/quality/validation/check_policy_design_case_layer2_readiness.py tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py
git commit -m "chore: register layer2 s2 design search progress"
```

---

## Task 7: Full S2 Verification

**Files:**

- No new files unless verification exposes a real gap.

- [ ] **Step 1: Run S2 unit tests**

```bash
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
```

Expected:

```text
12 passed
```

- [ ] **Step 2: Run S2 repo-quality tests**

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py -q
```

Expected:

```text
5 passed
```

- [ ] **Step 3: Run S0/S2 readiness and cluster-map validators**

```bash
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run python tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py
```

Expected:

```text
Layer 2 readiness: status=pass, open_cell_count_baseline=17, current_open_cell_count=15
Cluster map: status=pass, open_cell_count=15
S2 validator: status=pass, counterexample_conversion_rate=1.0, grammar_diversity_minimum=3, acquisition_branch_state=bridge_missing
```

- [ ] **Step 4: Run canonical corpus route regressions**

```bash
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
```

Expected:

- Existing S1 canonical downgrade tests still pass.
- S2 shadow search appears for `ua-msme-affordable-loans-2022`.
- S2 does not alter canonical closeout outcome because `canonical_outcome_effect="none_shadow_only"`.

- [ ] **Step 5: Run PDC/readiness regression suites**

```bash
uv run pytest tests/unit/pdc tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 6: Run architecture guardrails**

```bash
uv run polisyos-tools architecture guardrails check
```

Expected:

```text
Architecture guardrail check passed.
```

- [ ] **Step 7: Confirm verification left no uncommitted S2 changes**

```bash
git status --short
```

Expected: no output.

If this command shows S2 files, stop and repair the failing task that created the drift before making any additional commit.

---

## Done When

S2 is complete only when all of the following are true:

- `run_s2_shadow_design_loop` exists as a typed deterministic PDC producer.
- The UA-MSME first proving case runs grammar-derived candidate -> A-verify -> typed counterexample -> refinement decision -> `SearchLedger` -> `DesignRecordV0`.
- `DesignGrammarExpansion` is emitted before `DesignCandidateV0`; a candidate cannot exist without `grammar_expansion_ref`.
- `DesignCandidateV0` carries per-field source classification for grammar-derived fields.
- `SearchLedger` deterministic replay key is stable for identical inputs.
- `counterexample_conversion_rate == 1.0`.
- `grammar_diversity_minimum == 3` and instrument-family coverage is projected as S2 shadow adequacy.
- The six architecture-aligned counterexample classes are pinned in the S2 manifest: `real_design_blocker`, `substrate_gap`, `a_spec_gap`, `abstraction_gap`, `value_gap`, and `budget_gap`.
- Each `RefinementDecision` carries `ValueOfInformationEstimate`, budget refs, and stakes band.
- `a_spec_gap` routes to typed `GovernanceDecisionClass` handoff and cannot be self-classified by the loop.
- `substrate_gap` produces `acquisition_required` while acquisition branch remains `bridge_missing`.
- `budget_gap` produces honest `abstained` status and search-incompleteness note.
- A blocked candidate cannot be retried into a pass without a new grammar-derived candidate.
- LLM-only candidate proposal without grammar derivation fails P15.
- `ClusterHandoffRecord` proves the S2 generation handoff contribution and prevents Scientist workflow summary laundering without closing all `CROSS_CUTTING.scientist_orchestration`.
- `DesignRecordV0` is shadow-only, carries `may_not_use_for` firewalls, and points to a `SearchLedger` that contains candidate, counterexample, and refinement-decision refs.
- MACHINE and REVIEWER projections expose search trace and authority boundary without minting recommendation or publication authority.
- Canonical corpus route observes S2 shadow search for the first proving case.
- Acquisition branch remains `bridge_missing` and S3 is not claimed.
- S2 manifest is registered in inventory.
- Cluster map current open cell count is `15`; S0 baseline remains `17`.
- `CROSS_CUTTING.scientist_orchestration` remains open/split for S7 and is not counted as an S2-closed cell.
- S0 readiness validator, S2 validator, cluster-map validator, and architecture guardrails pass.

## Commit Guidance

Recommended commits:

1. `test: add layer2 s2 design search red tests`
2. `feat: add layer2 s2 shadow design search contracts`
3. `feat: persist layer2 s2 search ledger and design record`
4. `feat: wire layer2 s2 shadow search into corpus route`
5. `chore: validate layer2 s2 design search`
6. `chore: register layer2 s2 design search progress`

Keep the commits scoped. Do not include unrelated roadmap edits, S1 implementation changes, or S3 acquisition work unless explicitly requested.
