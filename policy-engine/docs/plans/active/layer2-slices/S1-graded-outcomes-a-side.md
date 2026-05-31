---
title: PolicyOS Layer 2 S1 Graded Outcomes A-Side Task Plan
status: active
owner: team-runtime-quality
created: 2026-05-30
last_verified: 2026-05-30
stability: draft
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
slice: S1
slice_label: graded_outcomes_a_side
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
adr_0166: ../../../adr/0166-evidence-acquisition-decision-boundaries.md
adr_0174: ../../../adr/0174-policy-evidence-capability-graph.md
---

# Layer 2 S1 Graded Outcomes / A-Side Prelude Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:test-driven-development` for Tasks 1, 4, and 5. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route partial/proxy evidence to `publish_with_limitation` instead of hard `typed_blocker` at research/governed authority, while preserving production strictness. This is an A-side closeout/projection improvement; it does not start B-side design generation.

**Architecture:** S1 wires an existing-but-incomplete status capability into the closeout path. It adds a typed `GradedOutcomeCompositionPolicy` in `polisyos.runtime.quality`, emits existing `DeficitRecord` rows with `disposition="publish_with_limitation"`, persists them through the existing `StatusEnvelope` / `deficit_crosswalk` artifact shape, consumes them through `build_can_i_closeout_verdict`, surfaces limitations through `PolicyDesignCaseProjection` for PUBLIC, REVIEWER, and EXPERT audiences, and wires the result into the canonical corpus/outcome routing path so S1 is not a sidecar validator. It must not mint claim authority, publication authority, production authority, or B-side design authority.

**Tech Stack:** Python 3.14, Pydantic v2, existing `runtime.quality.status_deficits`, existing `runtime.quality.closeout_reader`, existing `runtime.quality.projection_semantics`, JSON governed artifacts, pytest, existing repo-quality validation pattern.

---

## Scope

This task plan implements only roadmap slice S1.

It does not implement S2 grammar/candidates/search, S3 substrate/acquisition closure, S4 epistemic-regime classification, or any B-side generation behavior.

Cells moved:

- No open cluster cell moves in `layer2_slice_cell_matrix.toml`.
- `open_cell_count` remains 17.
- Layer capability `graded_outcomes_a_side` moves from `bridge_missing + semantic_test_missing` to `implemented`.

S1 is allowed to add a small architecture manifest for traceability, but it must not edit the S0 slice-cell matrix to claim an open-cell closure.

## Architecture Decision

`GradedOutcomeCompositionPolicy` lives in `polisyos.runtime.quality`, not in `polisyos.pdc` and not in `polisyos.scientist`.

Reason: S1 is an A-side closeout/status composition behavior. It changes how already-produced partial/proxy evidence is routed into closeout and projection surfaces. It is not a canonical design-record narrow waist like `DesignRecordV0`, and it is not a B-side generator. The correct reuse path is:

1. Produce a typed graded-outcome decision in `runtime.quality`.
2. Persist the decision as existing `DeficitRecord` / `StatusEnvelope` / `deficit_crosswalk` artifacts.
3. Let the existing closeout reader consume that persisted downgrade.
4. Let the existing projection semantics surface the limitation without creating authority.
5. Wire the decision into the canonical W12.D corpus/outcome path without using expert labels as runtime inputs.

S1 must not introduce a new global status enum. Local S1 outcomes compose into the existing shared status axes:

- `publish_with_limitation` -> `PublicationEffect.PUBLISH_WITH_LIMITATION` and `CloseoutEffect.LIMITED_CLOSEOUT`
- `typed_blocker` -> hard/closeout blocking
- production proxy/partial evidence -> hard block, not limitation
- governed/research `publish_with_limitation` -> requires a recorded decision owner and review/authority refs before it may change closeout or projection state
- non-overridable mandatory gate -> hard block, not limitation

## Pattern Pass

Relevant failure patterns: `P01`, `P03`, `P04`, `P05`, `P07`, `P09`, `P10`, `P13`, `P15`, `P18`, `P21`.

Existing risk found: `status_deficits`, `closeout_reader`, and `projection_semantics` already contain pieces of the graded-outcome path, but there is no single red-first semantic proof that the nine expert `limitation_required` cases route to `publish_with_limitation` at governed posture while production remains strict. Also, projection currently reads limitation-like closeout issues more reliably than top-level closeout `limitations`, so S1 must explicitly test the closeout-to-projection bridge. Finally, a standalone S1 validator could go green while `run_universal_outcome_corpus.py` still reports canonical typed blockers, so S1 must wire the downgrade into the canonical corpus/outcome route.

Correct pattern: a thin typed composition policy over existing status and closeout primitives. The policy may downgrade only when the evidence is real enough for a limitation and the authority posture permits it. A fabricated limitation with no proxy/partial evidence is rejected. Production does not receive proxy-as-production leakage.

Missing capability labels before implementation:

- `producer_missing` for the S1 composition policy.
- `bridge_missing` for partial/proxy evidence -> persisted deficit crosswalk -> closeout downgrade -> canonical corpus/outcome routing.
- `surface_missing` for top-level closeout limitations -> PUBLIC/REVIEWER/EXPERT projections.
- `semantic_test_missing` for the nine limitation cases, governed decision-owner negative control, mixed-status blocker dominance, and production-strict negative controls.

Acceptance signal:

- The nine `limitation_required` corpus cases route to `publish_with_limitation` under governed posture.
- The same corpus evidence under production posture routes to `typed_blocker` / `closeout_block`.
- The canonical corpus/outcome report observes the S1 governed downgrade instead of only the standalone S1 validator observing it.
- Governed/research limitation routing is rejected unless a decision owner and review/authority refs are recorded.
- A fabricated limitation with no proxy/partial evidence is rejected.
- A limitation cannot override an existing hard closeout blocker, reissue requirement, review-required state, or non-overridable gate.
- Closeout returns `closed_with_limitations` for governed limitation decisions.
- PUBLIC, REVIEWER, and EXPERT projections expose the limitation.
- S0 readiness and cluster-map validators still pass with 17 open cells.

## Source Of Truth

| Concern | Source |
| --- | --- |
| Roadmap closure contract | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md#s1-graded-outcomes-a-side-prelude-not-the-start-of-b` |
| Conceptual architecture | `docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md#d37-status-composition` |
| Authority and acquisition boundaries | `docs/adr/0166-evidence-acquisition-decision-boundaries.md` |
| Production strictness and no proxy-as-production leakage | `docs/adr/0174-policy-evidence-capability-graph.md` |
| Existing status lattice | `src/polisyos/runtime/quality/status_deficits.py` |
| Existing closeout reader | `src/polisyos/runtime/quality/closeout_reader.py` |
| Existing projection bridge | `src/polisyos/runtime/quality/projection_semantics.py` |
| Canonical corpus/outcome route | `tools/quality/validation/run_universal_outcome_corpus.py` |
| Layer 2 S0 contracts and matrix | `architecture/policy_design_case/layer2_readiness_manifest.json`, `architecture/policy_design_case/layer2_slice_cell_matrix.toml` |
| Corpus cases | `tests/fixtures/universal-corpus/cases/*.json` |

## Files

Create:

- `src/polisyos/runtime/quality/graded_outcomes.py`
- `tools/quality/validation/check_policy_design_case_layer2_s1_graded_outcomes.py`
- `tests/unit/runtime/quality/test_layer2_graded_outcomes.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s1_graded_outcomes.py`
- `architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json`

Modify:

- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/runtime/quality/projection_semantics.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- `architecture/policy_design_case/inventory.json`

Modify only if the red tests prove the bridge needs it:

- `src/polisyos/runtime/quality/closeout_reader.py`
- `src/polisyos/runtime/quality/status_deficits.py`

Do not modify:

- `architecture/policy_design_case/layer2_slice_cell_matrix.toml`
- `architecture/policy_design_case/cluster_ownership_map.toml`
- `src/polisyos/pdc/_impl/layer2_readiness.py`

---

## Task 1: Red-First S1 Semantic And Negative Tests

**Files:**

- Create: `tests/unit/runtime/quality/test_layer2_graded_outcomes.py`

- [ ] **Step 1: Write failing tests for governed limitation routing**

Create `tests/unit/runtime/quality/test_layer2_graded_outcomes.py` with tests that import the not-yet-existing S1 public surface:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.runtime.quality.graded_outcomes import (
    GradedOutcomeEvidenceInput,
    GradedOutcomeInputError,
    S1_GRADED_OUTCOME_SCHEMA_VERSION,
    compose_graded_outcome,
    graded_outcome_closeout_record,
)
from polisyos.runtime.quality.closeout_reader import (
    build_can_i_closeout_verdict,
)
from polisyos.runtime.quality.projection_semantics import (
    build_policy_design_case_projection_contract_fixture,
)
from tests._helpers.policy_design_case_projection import policy_design_case

REPO_ROOT = Path(__file__).resolve().parents[4]
CORPUS_CASES = REPO_ROOT / "tests" / "fixtures" / "universal-corpus" / "cases"
NOW = datetime(2026, 5, 30, tzinfo=UTC)


def _cases() -> list[dict[str, object]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(CORPUS_CASES.glob("*.json"))
    ]


def _case_id(case: dict[str, object]) -> str:
    return str(case.get("case_id") or case.get("id"))


def _label(case: dict[str, object]) -> str:
    adjudication = case.get("expert_adjudication")
    assert isinstance(adjudication, dict)
    return str(adjudication.get("case_label") or "")


def _input_for(case: dict[str, object], *, authority_level: str) -> GradedOutcomeEvidenceInput:
    case_id = _case_id(case)
    return GradedOutcomeEvidenceInput(
        schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
        case_id=case_id,
        claim_id=f"claim:{case_id}:main",
        authority_level=authority_level,
        requested_outcome="publish_with_limitation",
        evidence_profile="partial_or_proxy",
        proxy_evidence_refs=(f"corpus://{case_id}/proxy-evidence",),
        partial_evidence_refs=(f"corpus://{case_id}/partial-support",),
        limitation_reason_codes=("expert_limitation_required",),
        mandatory_gate_state="none",
        owner="team-evaluation",
        decision_owner_ref=f"review://layer2-s1/{case_id}/governed-owner",
        authority_profile_ref=f"authority_profile.{authority_level}",
        review_refs=(f"review://layer2-s1/{case_id}/limitation",),
        ttl_expires_at="2026-06-30T00:00:00Z",
        public_limitation_note=(
            "This governed output is publishable only with explicit limitation."
        ),
        rule_version_ref="policyos.layer2.s1.graded_outcomes.v1",
    )
```

Add this test:

```python
def test_governed_limitation_required_cases_route_to_publish_with_limitation() -> None:
    limitation_cases = [case for case in _cases() if _label(case) == "limitation_required"]

    assert len(limitation_cases) == 9

    decisions = [
        compose_graded_outcome(_input_for(case, authority_level="governed"))
        for case in limitation_cases
    ]

    assert {decision.outcome for decision in decisions} == {"publish_with_limitation"}
    assert all(decision.closeout_effect == "limited_closeout" for decision in decisions)
    assert all(decision.blockers == () for decision in decisions)
    assert all(len(decision.deficit_records) == 1 for decision in decisions)
    assert {
        row["disposition"]
        for decision in decisions
        for row in decision.deficit_records
    } == {"publish_with_limitation"}
    assert {
        row["authority_level"]
        for decision in decisions
        for row in decision.deficit_records
    } == {"governed"}
```

Expected red result:

```text
ModuleNotFoundError: No module named 'polisyos.runtime.quality.graded_outcomes'
```

- [ ] **Step 2: Write a failing test for research limitation routing without authority leakage**

Add:

```python
def test_research_limitation_routes_but_forbids_publication_authority() -> None:
    limitation_case = next(case for case in _cases() if _label(case) == "limitation_required")

    decision = compose_graded_outcome(_input_for(limitation_case, authority_level="research"))

    assert decision.outcome == "publish_with_limitation"
    assert decision.closeout_effect == "limited_closeout"
    assert "publication_authority_without_closeout" in decision.authority_boundary[
        "may_not_use_for"
    ]
    assert "production_closeout_authority" in decision.authority_boundary["may_not_use_for"]
    assert decision.deficit_records[0]["authority_level"] == "research"
```

- [ ] **Step 3: Write a failing test for governed limitation commit ownership**

Add:

```python
def test_governed_limitation_requires_decision_owner_before_closeout_change() -> None:
    limitation_case = next(case for case in _cases() if _label(case) == "limitation_required")

    with pytest.raises(
        GradedOutcomeInputError,
        match="publish_with_limitation requires decision_owner_ref and review_refs",
    ):
        compose_graded_outcome(
            _input_for(limitation_case, authority_level="governed").model_copy(
                update={"decision_owner_ref": None, "review_refs": ()}
            )
        )
```

- [ ] **Step 4: Write failing tests for production strictness**

Add:

```python
def test_production_strictness_blocks_all_corpus_cases_under_proxy_evidence() -> None:
    decisions = [
        compose_graded_outcome(_input_for(case, authority_level="production"))
        for case in _cases()
    ]

    assert len(decisions) == 13
    assert {decision.outcome for decision in decisions} == {"typed_blocker"}
    assert {decision.closeout_effect for decision in decisions} == {"closeout_blocked"}
    assert all(decision.limitations == () for decision in decisions)
    assert all(decision.blockers for decision in decisions)
    assert {
        blocker["code"]
        for decision in decisions
        for blocker in decision.blockers
    } == {"graded_outcome_production_proxy_block"}
```

This test means: given the same partial/proxy S1 evidence profile, production remains strict. It does not assert that every future production case is impossible to pass with exact production evidence.

- [ ] **Step 5: Write failing tests for fabricated limitation rejection**

Add:

```python
def test_fabricated_limitation_without_proxy_or_partial_evidence_is_rejected() -> None:
    with pytest.raises(
        GradedOutcomeInputError,
        match="publish_with_limitation requires proxy or partial evidence refs",
    ):
        compose_graded_outcome(
            GradedOutcomeEvidenceInput(
                schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
                case_id="fabricated-limitation",
                claim_id="claim:fabricated",
                authority_level="governed",
                requested_outcome="publish_with_limitation",
                evidence_profile="partial_or_proxy",
                proxy_evidence_refs=(),
                partial_evidence_refs=(),
                limitation_reason_codes=("unsupported_limitation",),
                mandatory_gate_state="none",
                owner="team-evaluation",
                decision_owner_ref="review://layer2-s1/fabricated/governed-owner",
                authority_profile_ref="authority_profile.governed",
                review_refs=("review://layer2-s1/fabricated/limitation",),
                ttl_expires_at="2026-06-30T00:00:00Z",
                public_limitation_note="Unsupported limitation.",
                rule_version_ref="policyos.layer2.s1.graded_outcomes.v1",
            )
        )
```

Add:

```python
def test_non_overridable_gate_dominates_limitation_request() -> None:
    decision = compose_graded_outcome(
        _input_for(_cases()[0], authority_level="governed").model_copy(
            update={"mandatory_gate_state": "non_overridable"}
        )
    )

    assert decision.outcome == "typed_blocker"
    assert decision.closeout_effect == "closeout_blocked"
    assert decision.limitations == ()
    assert decision.blockers[0]["code"] == "graded_outcome_non_overridable_gate"
```

- [ ] **Step 6: Write failing tests for persisted closeout downgrade**

Add a helper that builds the existing W4 closeout module records without reaching into another test module:

```python
def _w4_record(
    schema_version: str,
    *,
    status: str = "pass",
    issues: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "status": status,
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "producer": "test.layer2_s1",
        "runtime_event_ref": "event://layer2-s1/test",
        "cas_ref": "sha256:" + "a" * 64,
        "issues": list(issues or []),
    }


def _passing_w4_records() -> dict[str, dict[str, object]]:
    return {
        "i4_policy_design_case_graph": _w4_record(
            "policyos.runtime.policy_design_case.wave4_i4_graph.v1"
        ),
        "portfolio_effective_support": _w4_record(
            "policyos.runtime.policy_design_case.portfolio_effective_support.v1"
        ),
        "lifecycle_reissue": _w4_record(
            "policyos.runtime.policy_design_case.lifecycle_reissue_report.v1"
        ),
        "projection_consumer_contract": _w4_record(
            "policyos.runtime.policy_design_case.projection_contract_fixture.v1"
        ),
        "formal_invariants": _w4_record("policyos.runtime.formal_invariants.v1"),
        "source_truth": _w4_record("policyos.runtime.source_truth.v1"),
        "conflict_materialization": _w4_record(
            "policyos.runtime.policy_design_case.conflict_materialization_closeout.v1"
        ),
        "attestation": _w4_record("policyos.runtime.attestation.v1"),
        "closeout_compatibility": _w4_record(
            "policyos.runtime.can_i_closeout_compatibility.v1"
        ),
        "semantic_binding": _w4_record("policyos.runtime.semantic_binding.v1"),
        "claim_registry": _w4_record("policyos.runtime.claim_registry.v1"),
        "pdc_record_family_status": _w4_record(
            "policyos.policy_design_case.record_family_coverage.v1"
        ),
        "projection_publication_state": _w4_record(
            "policyos.runtime.policy_design_case.projection_publication_state.v1"
        ),
        "run_cost_gate": _w4_record("policyos.runtime.run_cost_gate.v1"),
        "complexity_self_fmea": _w4_record(
            "policyos.runtime.run_cost_proportionality.v1"
        ),
        "audit_verifier_ingestion": _w4_record("policyos.runtime.audit_verifier.v1"),
        "prompt_tool_repair_fmea": _w4_record(
            "policyos.runtime.prompt_tool_repair_fmea.v1"
        ),
    }
```

Add:

```python
def test_governed_limitation_persists_to_closeout_downgrade() -> None:
    decision = compose_graded_outcome(_input_for(_cases()[0], authority_level="governed"))
    closeout_record = graded_outcome_closeout_record(
        [decision],
        generated_at=NOW,
    )

    module_records = _passing_w4_records()
    module_records["deficit_crosswalk"] = closeout_record
    verdict = build_can_i_closeout_verdict(
        run_id="run-layer2-s1",
        module_records=module_records,
    )

    assert closeout_record["schema_version"] == "policyos.runtime.status_envelope.v1"
    assert closeout_record["status"] == "pass"
    assert closeout_record["authority_role"] == "runtime_reader"
    assert closeout_record["producer"] == "polisyos.runtime.quality.graded_outcomes"
    assert verdict["status"] == "closed_with_limitations"
    assert verdict["verdict"] == "can_closeout_with_limitations"
    assert verdict["summary"]["limitation_count"] == 1
    assert verdict["limitations"][0]["deficit_id"].startswith("limitation:")
```

- [ ] **Step 7: Write a failing mixed-status test where blockers dominate limitation**

Add:

```python
def test_limitation_does_not_override_existing_closeout_blocker() -> None:
    decision = compose_graded_outcome(_input_for(_cases()[0], authority_level="governed"))
    closeout_record = graded_outcome_closeout_record([decision], generated_at=NOW)
    module_records = _passing_w4_records()
    module_records["deficit_crosswalk"] = closeout_record
    module_records["semantic_binding"] = _w4_record(
        "policyos.runtime.semantic_binding.v1",
        status="fail",
        issues=[
            {
                "code": "semantic_binding_claim_missing",
                "severity": "fail",
                "message": "Major claim lacks semantic closure.",
                "producer": "test.semantic_binding",
                "claim_id": "claim:blocked",
            }
        ],
    )

    verdict = build_can_i_closeout_verdict(
        run_id="run-layer2-s1",
        module_records=module_records,
    )

    assert verdict["status"] == "blocked"
    assert verdict["can_closeout"] is False
    assert verdict["summary"]["limitation_count"] == 1
    assert "semantic_binding_claim_missing" in {
        blocker["upstream_issue_code"] for blocker in verdict["blockers"]
    }
```

- [ ] **Step 8: Write failing tests for PUBLIC/REVIEWER/EXPERT limitation surface**

Add:

```python
def test_public_reviewer_and_expert_projections_surface_closeout_limitation() -> None:
    decision = compose_graded_outcome(_input_for(_cases()[0], authority_level="governed"))
    closeout_record = graded_outcome_closeout_record([decision], generated_at=NOW)
    module_records = _passing_w4_records()
    module_records["deficit_crosswalk"] = closeout_record
    verdict = build_can_i_closeout_verdict(
        run_id="run-layer2-s1",
        module_records=module_records,
    )

    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict=verdict,
        audiences=("public", "reviewer", "expert"),
        generated_at=NOW,
    )

    assert fixture["status"] == "pass"
    for audience in ("public", "reviewer", "expert"):
        projection = fixture["projections"][audience]
        assert projection["closeout_truth"]["status"] == "closed_with_limitations"
        assert projection["closeout_truth"]["limitation_codes"]
        assert any(
            gap["publication_effect"] == "publish_with_limitation"
            for gap in projection["projection_gaps"]
        )
```

This red test is expected to expose whether `projection_semantics.py` currently ignores top-level `closeout_verdict["limitations"]`. If it does, fix the bridge in Task 3 instead of encoding limitations as fake blockers.

- [ ] **Step 9: Run the red tests**

Command:

```bash
uv run pytest tests/unit/runtime/quality/test_layer2_graded_outcomes.py -q
```

Expected output before implementation:

```text
ERROR tests/unit/runtime/quality/test_layer2_graded_outcomes.py
ModuleNotFoundError: No module named 'polisyos.runtime.quality.graded_outcomes'
```

Commit only after the implementation tasks turn these tests green.

---

## Task 2: Typed Graded Outcome Composition Policy

**Files:**

- Create: `src/polisyos/runtime/quality/graded_outcomes.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`

- [ ] **Step 1: Add the S1 typed contracts**

Create `src/polisyos/runtime/quality/graded_outcomes.py`.

Required public symbols:

```python
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

S1_GRADED_OUTCOME_SCHEMA_VERSION = "policyos.runtime.layer2.graded_outcome.v1"
S1_GRADED_OUTCOME_CLOSEOUT_RECORD_SCHEMA_VERSION = "policyos.runtime.status_envelope.v1"

class GradedOutcomeInputError(ValueError):
    pass

class GradedOutcomeEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class GradedOutcomeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

def compose_graded_outcome(input: GradedOutcomeEvidenceInput) -> GradedOutcomeDecision:
    raise GradedOutcomeInputError("composition rules are defined in Task 2 Step 2")

def graded_outcome_closeout_record(
    decisions: Sequence[GradedOutcomeDecision],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    raise GradedOutcomeInputError(
        "status envelope persistence is defined in Task 2 Step 3"
    )
```

Use Pydantic `ConfigDict(extra="forbid", frozen=True)`.

Import and use the existing typed deficit contract:

```python
from polisyos.runtime.quality.status_deficits import DeficitRecord
```

Every emitted deficit row in `GradedOutcomeDecision.deficit_records` must pass
`DeficitRecord.model_validate(row)` before the decision is returned. Do not use
raw `dict[str, Any]` as an unchecked contract boundary.

`GradedOutcomeEvidenceInput` required fields:

- `schema_version: Literal["policyos.runtime.layer2.graded_outcome.v1"]`
- `case_id: str`
- `claim_id: str`
- `authority_level: Literal["research", "governed", "governed_pilot", "governed-pilot", "production"]`
- `requested_outcome: Literal["pass", "publish_with_limitation", "accepted_deficit", "typed_blocker"]`
- `evidence_profile: Literal["exact", "partial_or_proxy", "unsupported"]`
- `proxy_evidence_refs: tuple[str, ...]`
- `partial_evidence_refs: tuple[str, ...]`
- `limitation_reason_codes: tuple[str, ...]`
- `mandatory_gate_state: Literal["none", "overridable_by_governed_commit", "non_overridable"]`
- `owner: str`
- `decision_owner_ref: str | None`
- `authority_profile_ref: str`
- `review_refs: tuple[str, ...]`
- `ttl_expires_at: datetime`
- `public_limitation_note: str | None`
- `rule_version_ref: str`
- `source_authority: Literal["deterministic_producer", "governed_config", "human_governance"] = "deterministic_producer"`

Do not allow `llm_candidate`, `llm_critic`, or `llm_drafter` as source authority in S1. LLM output can still be candidate material elsewhere, but not the A-side downgrade producer.

`GradedOutcomeDecision` required fields:

- `schema_version`
- `decision_id`
- `case_id`
- `claim_id`
- `authority_level`
- `outcome: Literal["pass", "publish_with_limitation", "accepted_deficit", "typed_blocker"]`
- `publication_effect`
- `closeout_effect`
- `authority_profile_ref`
- `decision_owner_ref`
- `review_refs`
- `deficit_records: tuple[dict[str, Any], ...]` where each row is validated by `DeficitRecord.model_validate`
- `limitations: tuple[dict[str, Any], ...]`
- `blockers: tuple[dict[str, Any], ...]`
- `authority_boundary`
- `rule_version_ref`

Authority boundary for S1 decisions:

```python
{
    "authoritative_for": ["graded_outcome_routing"],
    "may_not_use_for": [
        "claim_authority",
        "producer_domain_truth",
        "production_closeout_authority",
        "publication_authority_without_closeout",
        "b_side_design_generation",
    ],
    "source_authority": input.source_authority,
    "posture": normalized_authority_level,
}
```

- [ ] **Step 2: Implement the composition rules**

Rules in `compose_graded_outcome`:

1. Normalize `governed_pilot` and `governed-pilot` to `governed`.
2. If `mandatory_gate_state == "non_overridable"`, return `typed_blocker` with blocker code `graded_outcome_non_overridable_gate`.
3. If `authority_level == "production"` and evidence is not exact production evidence, return `typed_blocker` with blocker code `graded_outcome_production_proxy_block`.
4. If `requested_outcome == "publish_with_limitation"` and both `proxy_evidence_refs` and `partial_evidence_refs` are empty, raise `GradedOutcomeInputError`.
5. If `publish_with_limitation` is requested at research/governed authority, require all of:
   - `decision_owner_ref`
   - at least one `review_refs` value
   - `authority_profile_ref`
   - `public_limitation_note`
6. Research limitation routing is advisory/non-authority; governed limitation routing is the promoted posture that may change closeout/projection state after the owner/review refs above are present.
7. If limitation is requested and allowed at research/governed authority, return `publish_with_limitation` and one `DeficitRecord`-compatible dict with:
   - `deficit_id = "limitation:{case_id}:{claim_id_slug}"`
   - `deficit_family = "graded_outcome"`
   - `deficit_code = "graded_outcome_proxy_or_partial_evidence"`
   - `claim_ids = [claim_id]`
   - `authority_level = normalized_authority_level`
   - `audience_scope = "public"`
   - `disposition = "publish_with_limitation"`
   - `support_cap = "weak"`
   - `readiness_cap = "external_briefing"`
   - `max_audience = "public_with_limitation"`
   - `owner`
   - `ttl_expires_at`
   - `runtime_event_ref = "event://layer2/s1/graded-outcomes/{case_id}"`
   - `evidence_ref` from the first proxy/partial evidence ref
   - `public_limitation_note`
   - `review_refs = input.review_refs`

   Keep `authority_profile_ref` and `decision_owner_ref` on `GradedOutcomeDecision`
   and on closeout-visible issue summaries. `DeficitRecord` already carries
   `review_refs`; do not add unsupported extra fields to it.
8. If `requested_outcome == "pass"` and `evidence_profile == "exact"`, return `pass` with no deficit.
9. Unsupported or ambiguous inputs default to `typed_blocker`; never silently pass.

- [ ] **Step 3: Persist decisions through the existing status envelope**

Implement `graded_outcome_closeout_record` by calling:

```python
from polisyos.runtime.quality.status_deficits import (
    build_status_envelope,
    status_envelope_payload,
)
```

The returned payload must be a normal status envelope plus closeout-reader metadata:

```python
payload = status_envelope_payload(envelope)
payload.update(
    {
        "status": "pass" if not blocking_decisions else "blocked",
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "producer": "polisyos.runtime.quality.graded_outcomes",
        "runtime_event_ref": "event://layer2/s1/graded-outcomes",
        "issues": issue_rows,
    }
)
```

For limitation decisions, include an issue row with severity `limitation` so current closeout/projection readers can observe it:

```python
{
    "code": "graded_outcome_publish_with_limitation",
    "severity": "limitation",
    "message": public_limitation_note,
    "module_id": "graded_outcomes",
    "owner": owner,
    "decision_owner_ref": decision_owner_ref,
    "authority_profile_ref": authority_profile_ref,
    "review_refs": list(review_refs),
    "evidence_ref": evidence_ref,
    "claim_ids": [claim_id],
}
```

This is not fake evidence; it is a projection/closeout-visible summary of the persisted `deficit_crosswalk` row.

For blocker decisions, include fail issues with the blocker code.

- [ ] **Step 4: Export the public surface**

Modify `src/polisyos/runtime/quality/__init__.py` to export:

- `GradedOutcomeDecision`
- `GradedOutcomeEvidenceInput`
- `GradedOutcomeInputError`
- `S1_GRADED_OUTCOME_SCHEMA_VERSION`
- `compose_graded_outcome`
- `graded_outcome_closeout_record`

- [ ] **Step 5: Run the focused unit tests**

Command:

```bash
uv run pytest tests/unit/runtime/quality/test_layer2_graded_outcomes.py -q
```

Expected green output after Task 2 and before Task 3 may still have one projection-surface failure if `projection_semantics.py` ignores top-level limitations. The composition and closeout tests should pass.

---

## Task 3: Closeout Reader To Projection Surface Bridge

**Files:**

- Modify: `src/polisyos/runtime/quality/projection_semantics.py`
- Modify only if needed: `src/polisyos/runtime/quality/closeout_reader.py`

- [ ] **Step 1: Teach projection semantics to preserve top-level limitations**

If Task 1 Step 8 fails because `closeout_verdict["limitations"]` is not projected, update `projection_semantics.py`.

Required behavior:

- `_closeout_truth` must include limitation codes from top-level `closeout["limitations"]`.
- `_projection_gaps` must add limitation gaps from top-level `closeout["limitations"]`.
- Existing issue-based limitations must continue to work.
- The bridge must not treat limitations as blockers.

Implementation hint:

```python
def _closeout_limitations(closeout: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for limitation in _sequence(closeout.get("limitations")):
        if not isinstance(limitation, Mapping):
            continue
        code = _text(
            limitation.get("limitation_id")
            or limitation.get("deficit_id")
            or limitation.get("code")
        )
        if code:
            rows.append(
                {
                    "code": code,
                    "message": _text(limitation.get("message")) or code,
                    "owner": _text(limitation.get("owner")),
                    "evidence_ref": _text(limitation.get("evidence_ref")),
                    "claim_ids": list(_sequence(limitation.get("claim_ids"))),
                }
            )
    return rows
```

Then:

```python
limitation_codes = _unique_texts(
    [
        *_issue_codes(closeout, severities={"warning", "limited", "limitation"}),
        *(row["code"] for row in _closeout_limitations(closeout)),
    ]
)
```

For projection gaps, map each limitation to:

- `gap_family = "limitation"`
- `severity = "limitation"`
- `publication_effect = "publish_with_limitation"`
- `closeout_effect = "limited_closeout"`
- `audience_visibility = public/reviewer/expert/machine` from existing `_gap`

- [ ] **Step 2: Keep closeout reader semantics closeout-only**

Only modify `closeout_reader.py` if the S1 closeout record cannot be consumed through the existing `deficit_crosswalk` module.

Allowed modification:

- Include `limitation_codes` or limitation issue summaries in the returned verdict if derived from persisted `limitations`.

Forbidden modification:

- Do not let projection-only records satisfy closeout.
- Do not let readiness/dashboard/public export surfaces satisfy closeout.
- Do not change production strictness.

- [ ] **Step 3: Re-run bridge tests**

Command:

```bash
uv run pytest tests/unit/runtime/quality/test_layer2_graded_outcomes.py -q
```

Expected output:

```text
9 passed
```

If the final test count differs because helper-only tests were split differently, all S1 tests must still pass and include the nine named tests from Task 1.

---

## Task 4: Canonical Corpus Routing Wiring

**Files:**

- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`
- Modify: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`

- [ ] **Step 1: Write red tests proving S1 is not a sidecar**

In `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`, add focused tests:

```python
def test_w12d_canonical_outcome_consumes_s1_governed_closeout_downgrade(
    tmp_path: Path,
) -> None:
    stub_dir = tmp_path / "producer-stubs"
    stub_dir.mkdir()
    (stub_dir / "ua-msme-affordable-loans-2022.producer_stubs.json").write_text(
        json.dumps(
            {
                "case_id": "ua-msme-affordable-loans-2022",
                "mode": "corpus_stub",
                "max_authority_posture": "governed-pilot",
                "fabric": {"*": "selected"},
                "lex": {"*": "selected"},
                "foundry": {"*": "selected"},
                "scholar": {"*": "selected"},
                "participation": {"*": "limited"},
            }
        ),
        encoding="utf-8",
    )
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="corpus_stub",
        producer_stub_dir=stub_dir,
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    case = report["cases"][0]
    assert case["s1_graded_outcome"]["outcome"] == "publish_with_limitation"
    assert case["s1_graded_outcome"]["closeout_status"] == "closed_with_limitations"
    assert case["s1_graded_outcome"]["decision_owner_ref"]
    assert case["s1_graded_outcome"]["authority_profile_ref"]
    assert case["s1_graded_outcome"]["review_refs"]
    assert case["outcome"] == "publish-with-limitation"
    assert case["expert_adjudication_delta"]["canonical_runtime_outcome"] == (
        "publish-with-limitation"
    )


def test_w12d_s1_route_does_not_override_production_or_hard_blockers(
    tmp_path: Path,
) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    governed_report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "governed-graphs",
        hypothesis_ledger_output_dir=tmp_path / "governed-ledgers",
        mode="corpus_stub",
        producer_stub_dir=REPO_ROOT / "tests/fixtures/universal-corpus/producer_stubs",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )
    governed_case = governed_report["cases"][0]
    assert governed_case["authority_outcomes"]["governed"]["outcome"] == (
        "publish-with-limitation"
    )
    assert governed_case["authority_outcomes"]["production"]["outcome"] == "typed_blocker"

    blocked_report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=SINGLE_CASE_PATH,
        graph_output_dir=tmp_path / "blocked-graphs",
        hypothesis_ledger_output_dir=tmp_path / "blocked-ledgers",
        mode="real_producer",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )
    blocked_case = blocked_report["cases"][0]
    assert blocked_case["outcome"] == "typed_blocker"
    assert blocked_case["s1_graded_outcome"]["blocked_by"] in {
        "hard_closeout_blocker",
        "non_overridable_gate",
        "review_required",
        "reissue_required",
    }
```

The first test must run the canonical W12.D/corpus path, not the standalone S1
validator, and assert the governed limitation-required case produces a report
section like:

```python
assert result["s1_graded_outcome"]["outcome"] == "publish_with_limitation"
assert result["s1_graded_outcome"]["closeout_status"] == "closed_with_limitations"
assert result["outcome"] == "publish-with-limitation"
assert result["s1_graded_outcome"]["decision_owner_ref"]
assert result["s1_graded_outcome"]["authority_profile_ref"]
assert result["s1_graded_outcome"]["review_refs"]
```

The second test must assert S1 cannot downgrade these conditions:

```python
assert production_result["authority_outcomes"]["production"]["outcome"] == "typed_blocker"
assert hard_blocker_result["outcome"] == "typed_blocker"
assert hard_blocker_result["s1_graded_outcome"]["blocked_by"] in {
    "hard_closeout_blocker",
    "non_overridable_gate",
    "review_required",
    "reissue_required",
}
```

Expected red result before wiring:

```text
AssertionError: missing s1_graded_outcome
```

or:

```text
AssertionError: outcome is still typed_blocker for governed limitation route
```

- [ ] **Step 2: Wire S1 into the canonical W12.D outcome route**

Modify `tools/quality/validation/run_universal_outcome_corpus.py`.

Required behavior:

1. Build `GradedOutcomeEvidenceInput` from deterministic corpus/runtime signals only.
2. Do not use expert labels as runtime inputs. Expert labels may remain evaluation ground truth for measuring disagreement, but they must not be the producer input that decides a case.
3. Derive S1 input from signals such as partial/proxy evidence refs, selected proxy evidence, limited support, capability-binding gaps, closeout downgrade record, and requested authority posture.
4. Persist the S1 decision through `graded_outcome_closeout_record`.
5. Feed the persisted record into `build_can_i_closeout_verdict`.
6. Add a case-result section `s1_graded_outcome` with:
   - `outcome`
   - `closeout_effect`
   - `closeout_status`
   - `decision_owner_ref`
   - `authority_profile_ref`
   - `review_refs`
   - `projection_surface_status`
   - `blocked_by` when S1 cannot downgrade
7. Let `_canonical_outcome` and authority-specific outcome rows accept W12.D `publish-with-limitation` only when all are true:
   - authority posture is `research` or `governed`, not `production`
   - S1 decision outcome is `publish_with_limitation`
   - persisted closeout verdict is `closed_with_limitations`
   - no hard closeout blocker exists
   - no non-overridable gate exists
   - no reissue-required or review-required status exists
   - `decision_owner_ref`, `authority_profile_ref`, and `review_refs` are present
8. Production keeps returning `typed_blocker` for the same proxy/partial profile.

- [ ] **Step 3: Re-run W12.D focused tests**

Command:

```bash
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
```

Expected result:

```text
all selected W12.D canonical corpus tests passed
```

If the file is too slow to run as a whole, run the two S1-focused tests plus the existing W12.D authority-outcome regression tests in the same command.

---

## Task 5: Red-First S1 Readiness Validator And Corpus Manifest

**Files:**

- Create: `architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json`
- Create: `tools/quality/validation/check_policy_design_case_layer2_s1_graded_outcomes.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer2_s1_graded_outcomes.py`

- [ ] **Step 1: Write failing repo-quality tests for the S1 manifest and validator**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_s1_graded_outcomes.py`.

Start the file with:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.runtime.quality.graded_outcomes import GradedOutcomeInputError
from tools.quality.validation import (
    check_policy_design_case_layer2_s1_graded_outcomes as s1_validator,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    REPO_ROOT / "architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json"
)
LIMITATION_REQUIRED_CASE_IDS = [
    "ua-msme-affordable-loans-2022",
    "w11a_boston_operation_ceasefire_1996",
    "w11a_ghana_free_shs_2017",
    "w11a_mexico_ssb_tax_2014",
    "w11a_netherlands_room_for_river_2007",
    "w11a_uk_levelling_up_fund_2021",
    "w11a_uk_mtd_vat_2019",
    "w11a_uk_work_programme_2011",
    "w11a_us_ppp_2020",
]
PRODUCTION_CONTROL_CASE_IDS = [
    "ua-msme-affordable-loans-2022",
    "w11a_berlin_rent_cap_2020",
    "w11a_boston_operation_ceasefire_1996",
    "w11a_eu_temporary_protection_ukraine_2022",
    "w11a_ghana_free_shs_2017",
    "w11a_india_aadhaar_dbt_2016",
    "w11a_mexico_ssb_tax_2014",
    "w11a_netherlands_room_for_river_2007",
    "w11a_pakistan_ehsaas_cash_2020",
    "w11a_uk_levelling_up_fund_2021",
    "w11a_uk_mtd_vat_2019",
    "w11a_uk_work_programme_2011",
    "w11a_us_ppp_2020",
]


def _load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
```

Required tests:

```python
def test_s1_manifest_declares_no_open_cell_closure() -> None:
    manifest = _load_manifest()

    assert manifest["slice"] == "S1"
    assert manifest["cells_closed"] == []
    assert manifest["open_cell_count_baseline"] == 17


def test_s1_manifest_names_nine_limitation_cases_and_thirteen_production_controls() -> None:
    manifest = _load_manifest()

    assert manifest["limitation_required_case_ids"] == LIMITATION_REQUIRED_CASE_IDS
    assert manifest["production_strict_control_case_ids"] == PRODUCTION_CONTROL_CASE_IDS
    assert manifest["limitation_required_case_count"] == len(LIMITATION_REQUIRED_CASE_IDS)
    assert manifest["production_strict_control_case_count"] == len(PRODUCTION_CONTROL_CASE_IDS)


def test_s1_manifest_requires_governed_decision_owner_and_canonical_route() -> None:
    manifest = _load_manifest()

    assert manifest["decision_owner_required"] is True
    assert manifest["review_refs_required"] is True
    assert manifest["canonical_route_ref"] == (
        "tools/quality/validation/run_universal_outcome_corpus.py"
    )


def test_s1_validator_reports_governed_limitations_and_production_strictness() -> None:
    summary = s1_validator.validate_s1_graded_outcomes(repo_root=REPO_ROOT)

    assert summary["status"] == "pass"
    assert summary["governed_publish_with_limitation_count"] == 9
    assert summary["production_typed_blocker_count"] == 13
    assert summary["canonical_route_status"] == "pass"


def test_s1_validator_rejects_fabricated_limitation_without_proxy_evidence() -> None:
    with pytest.raises(GradedOutcomeInputError):
        s1_validator.validate_fabricated_limitation_negative_control()


def test_s1_validator_keeps_s0_open_cell_count_unchanged() -> None:
    summary = s1_validator.validate_s1_graded_outcomes(repo_root=REPO_ROOT)

    assert summary["open_cell_count"] == 17
    assert summary["cells_closed"] == []
```

The first red result should be:

```text
FileNotFoundError: architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json
```

or:

```text
ModuleNotFoundError: No module named 'tools.quality.validation.check_policy_design_case_layer2_s1_graded_outcomes'
```

- [ ] **Step 2: Add the S1 manifest**

Create `architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s1_graded_outcomes_manifest.v1",
  "status": "active",
  "owner": "team-runtime-quality",
  "slice": "S1",
  "layer_capability": "graded_outcomes_a_side",
  "cells_closed": [],
  "open_cell_count_baseline": 17,
  "corpus_ref": "tests/fixtures/universal-corpus/cases",
  "limitation_required_case_count": 9,
  "limitation_required_case_ids": [
    "ua-msme-affordable-loans-2022",
    "w11a_boston_operation_ceasefire_1996",
    "w11a_ghana_free_shs_2017",
    "w11a_mexico_ssb_tax_2014",
    "w11a_netherlands_room_for_river_2007",
    "w11a_uk_levelling_up_fund_2021",
    "w11a_uk_mtd_vat_2019",
    "w11a_uk_work_programme_2011",
    "w11a_us_ppp_2020"
  ],
  "production_strict_control_case_count": 13,
  "production_strict_control_case_ids": [
    "ua-msme-affordable-loans-2022",
    "w11a_berlin_rent_cap_2020",
    "w11a_boston_operation_ceasefire_1996",
    "w11a_eu_temporary_protection_ukraine_2022",
    "w11a_ghana_free_shs_2017",
    "w11a_india_aadhaar_dbt_2016",
    "w11a_mexico_ssb_tax_2014",
    "w11a_netherlands_room_for_river_2007",
    "w11a_pakistan_ehsaas_cash_2020",
    "w11a_uk_levelling_up_fund_2021",
    "w11a_uk_mtd_vat_2019",
    "w11a_uk_work_programme_2011",
    "w11a_us_ppp_2020"
  ],
  "governed_expected_outcome": "publish_with_limitation",
  "production_expected_outcome": "typed_blocker",
  "decision_owner_required": true,
  "review_refs_required": true,
  "producer_ref": "src/polisyos/runtime/quality/graded_outcomes.py#compose_graded_outcome",
  "persisted_artifact_ref": "src/polisyos/runtime/quality/graded_outcomes.py#graded_outcome_closeout_record",
  "bridge_ref": "src/polisyos/runtime/quality/closeout_reader.py#build_can_i_closeout_verdict",
  "consumer_ref": "src/polisyos/runtime/quality/projection_semantics.py#build_policy_design_case_projection_contract_fixture",
  "canonical_route_ref": "tools/quality/validation/run_universal_outcome_corpus.py",
  "semantic_test_ref": "tests/unit/runtime/quality/test_layer2_graded_outcomes.py#test_governed_limitation_required_cases_route_to_publish_with_limitation",
  "negative_test_refs": [
    "tests/unit/runtime/quality/test_layer2_graded_outcomes.py#test_fabricated_limitation_without_proxy_or_partial_evidence_is_rejected",
    "tests/unit/runtime/quality/test_layer2_graded_outcomes.py#test_production_strictness_blocks_all_corpus_cases_under_proxy_evidence",
    "tests/unit/runtime/quality/test_layer2_graded_outcomes.py#test_governed_limitation_requires_decision_owner_before_closeout_change",
    "tests/unit/runtime/quality/test_layer2_graded_outcomes.py#test_limitation_does_not_override_existing_closeout_blocker"
  ],
  "firewalls": [
    "ADR-0174 production strictness",
    "no proxy-as-production leakage",
    "no fabricated limitation without proxy or partial evidence",
    "non-overridable gates dominate limitation routing",
    "governed limitation requires decision owner and review refs",
    "canonical W12.D route consumes S1 downgrade"
  ]
}
```

- [ ] **Step 3: Add the S1 validator**

Create `tools/quality/validation/check_policy_design_case_layer2_s1_graded_outcomes.py`.

Validator requirements:

1. Load `layer2_s1_graded_outcomes_manifest.json`.
2. Load `layer2_slice_cell_matrix.toml` and assert S1 has no open-cell assignment.
3. Load all corpus cases under `tests/fixtures/universal-corpus/cases`.
4. Count cases whose `expert_adjudication.case_label == "limitation_required"`; assert the exact nine case IDs from the manifest, not only the count.
5. For each limitation case, build a governed `GradedOutcomeEvidenceInput`, call `decision = compose_graded_outcome(input_row)`, and assert `decision.outcome == "publish_with_limitation"`.
6. For all 13 manifest-listed production controls, build a production `GradedOutcomeEvidenceInput` with the same proxy/partial profile and assert `outcome == "typed_blocker"`.
7. Build one closeout record from governed decisions, feed it to `build_can_i_closeout_verdict` with minimal passing W4 module records, and assert `closed_with_limitations`.
8. Build PUBLIC/REVIEWER/EXPERT projections and assert the limitation is visible.
9. Run or import the canonical W12.D/corpus route and assert at least one governed limitation-required case reports `s1_graded_outcome.outcome == "publish_with_limitation"` and W12.D `outcome == "publish-with-limitation"` in the canonical report.
10. Assert missing `decision_owner_ref` / `review_refs` is rejected.
11. Emit JSON summary:

```json
{
  "status": "pass",
  "slice": "S1",
  "open_cell_count": 17,
  "cells_closed": [],
  "limitation_required_case_count": 9,
  "governed_publish_with_limitation_count": 9,
  "production_control_case_count": 13,
  "production_typed_blocker_count": 13,
  "closeout_status": "closed_with_limitations",
  "canonical_route_status": "pass",
  "projection_audiences_verified": ["public", "reviewer", "expert"],
  "closeout_honesty_rate": 1.0
}
```

Add CLI behavior:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer2_s1_graded_outcomes.py
```

Expected output:

```json
{
  "status": "pass",
  "slice": "S1",
  "open_cell_count": 17,
  "cells_closed": [],
  "limitation_required_case_count": 9,
  "governed_publish_with_limitation_count": 9,
  "production_control_case_count": 13,
  "production_typed_blocker_count": 13,
  "closeout_status": "closed_with_limitations",
  "canonical_route_status": "pass",
  "projection_audiences_verified": ["public", "reviewer", "expert"],
  "closeout_honesty_rate": 1.0
}
```

- [ ] **Step 4: Run the repo-quality tests**

Command:

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s1_graded_outcomes.py -q
```

Expected output:

```text
6 passed
```

---

## Task 6: Inventory Wiring

**Files:**

- Modify: `architecture/policy_design_case/inventory.json`

- [ ] **Step 1: Register the S1 manifest**

Add an inventory entry for:

- `layer2_s1_graded_outcomes_manifest`

Required metadata:

- `path`: `architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json`
- `schema_version`: `policyos.policy_design_case.layer2_s1_graded_outcomes_manifest.v1`
- `owner`: `team-runtime-quality`
- `status`: `active`
- `capability_reality_label`: `implemented`
- `authority_scope`: `graded_outcome_routing`
- `may_not_use_for`: includes `production_closeout_authority`, `claim_authority`, `b_side_design_generation`
- `validator`: `tools/quality/validation/check_policy_design_case_layer2_s1_graded_outcomes.py`
- `canonical_route`: `tools/quality/validation/run_universal_outcome_corpus.py`

- [ ] **Step 2: Extend the S1 repo-quality test to require inventory registration**

In `tests/repo_quality/tools/test_policy_design_case_layer2_s1_graded_outcomes.py`, add or extend:

```python
def test_s1_manifest_is_registered_in_inventory() -> None:
    inventory_path = REPO_ROOT / "architecture/policy_design_case/inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    artifacts = {
        str(artifact["id"]): artifact
        for artifact in inventory["artifacts"]
    }

    row = artifacts["layer2_s1_graded_outcomes_manifest"]
    assert row["path"] == (
        "architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json"
    )
    assert row["schema_version"] == (
        "policyos.policy_design_case.layer2_s1_graded_outcomes_manifest.v1"
    )
    assert row["owner"] == "team-runtime-quality"
    assert row["status"] == "active"
    assert row["capability_reality_label"] == "implemented"
    assert row["authority_scope"] == "graded_outcome_routing"
    assert "production_closeout_authority" in row["may_not_use_for"]
    assert "claim_authority" in row["may_not_use_for"]
    assert "b_side_design_generation" in row["may_not_use_for"]
    assert row["validator"] == (
        "tools/quality/validation/check_policy_design_case_layer2_s1_graded_outcomes.py"
    )
    assert row["canonical_route"] == (
        "tools/quality/validation/run_universal_outcome_corpus.py"
    )
```

Expected output after rerun:

```text
7 passed
```

---

## Task 7: Full S1 Verification

**Files:**

- No new files unless verification exposes a real gap.

- [ ] **Step 1: Run focused S1 unit tests**

Command:

```bash
uv run pytest tests/unit/runtime/quality/test_layer2_graded_outcomes.py -q
```

Expected output:

```text
9 passed
```

- [ ] **Step 2: Run focused S1 repo-quality tests**

Command:

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s1_graded_outcomes.py -q
```

Expected output:

```text
7 passed
```

- [ ] **Step 3: Run canonical W12.D corpus routing regressions**

Command:

```bash
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
```

Expected:

- The S1 governed downgrade is visible in the canonical W12.D/corpus report.
- Production and hard blockers still produce `typed_blocker`.
- Expert labels are used only as evaluation ground truth, not as runtime downgrade inputs.

- [ ] **Step 4: Run existing bridge regression tests**

Command:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_status_deficits.py \
  tests/unit/runtime/quality/test_closeout_reader.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  -q
```

Expected output before S1 additions is 28 collected tests. After this plan, the command must report all tests passed and no regression in:

- projection-only records rejected as closeout evidence
- readiness/dashboard/public export not accepted as closeout substrate
- `accepted_deficit`, `publish_with_limitation`, review, reissue, and hard block distinct
- projection consumer contract preserves closeout truth

- [ ] **Step 5: Run S0 and cluster-map guardrails**

Commands:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run polisyos-tools architecture guardrails check
```

Expected:

- S0 readiness remains `status=pass`.
- `open_cell_count=17`.
- `s0_cells_closed=[]`.
- S1 validator reports `cells_closed=[]`.
- Architecture guardrails pass.

- [ ] **Step 6: Run the S1 validator**

Command:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer2_s1_graded_outcomes.py
```

Expected summary:

```text
status=pass
slice=S1
limitation_required_case_count=9
governed_publish_with_limitation_count=9
production_typed_blocker_count=13
closeout_status=closed_with_limitations
canonical_route_status=pass
projection_audiences_verified=public,reviewer,expert
closeout_honesty_rate=1.0
```

---

## Done When

S1 is complete only when all of the following are true:

- `compose_graded_outcome` exists as a typed runtime-quality producer.
- The nine expert `limitation_required` corpus cases route to `publish_with_limitation` at governed posture.
- The exact nine limitation case IDs and exact thirteen production-control case IDs are pinned in the S1 manifest.
- The same proxy/partial evidence profile routes to `typed_blocker` under production posture for all 13 corpus cases.
- Governed/research `publish_with_limitation` requires `decision_owner_ref`, `authority_profile_ref`, and `review_refs`.
- A fabricated limitation with no proxy or partial evidence is rejected.
- A non-overridable mandatory gate blocks even if limitation is requested.
- A limitation cannot override a hard closeout blocker, reissue-required state, review-required state, or non-overridable gate.
- The persisted artifact is a normal `StatusEnvelope` / `deficit_crosswalk` closeout record.
- `build_can_i_closeout_verdict` returns `closed_with_limitations` for governed limitation decisions.
- The canonical W12.D/corpus outcome route consumes the S1 closeout downgrade; the standalone S1 validator is not the only place that observes it.
- PUBLIC, REVIEWER, and EXPERT projections expose the limitation without minting authority.
- `architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json` is registered in inventory.
- `layer2_slice_cell_matrix.toml` remains unchanged for S1 and still covers 17 open cells.
- S0 readiness validator, S1 validator, cluster-map validator, and architecture guardrails pass.

## Commit Guidance

Recommended commits:

1. `test: add layer2 s1 graded outcome red tests`
2. `feat: add layer2 s1 graded outcome policy`
3. `fix: surface graded outcome limitations in projections`
4. `feat: wire layer2 s1 graded outcomes into corpus route`
5. `chore: validate layer2 s1 graded outcomes`
6. `chore: register layer2 s1 graded outcome artifact`

Keep the commits scoped. Do not include unrelated roadmap or S0 planning edits unless explicitly requested.
