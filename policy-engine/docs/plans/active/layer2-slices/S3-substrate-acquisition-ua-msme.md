---
title: PolicyOS Layer 2 S3 Substrate + Closed Acquisition Loop (Ukrainian MSME) Implementation Plan
status: active
owner: team-runtime-quality
created: 2026-05-30
last_verified: 2026-05-30
stability: draft
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
slice: S3
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
---

# Layer 2 S3 Substrate + Closed Acquisition Loop / Ukrainian MSME Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the real W12 failure mode. Make the design loop's `acquisition_required` branch real by grounding the **Ukrainian MSME credit constructs** through a closed, deterministic, replay-safe acquisition loop, and measure substrate coverage by facet-space demand rather than raw capability counts.

**Architecture:** S3 is the binding constraint. It does **not** invent a new data lake (ADR-0174 forbids). It expresses construct demand as compositional facet-space `ConstructExpression`s over the S0-frozen facet primitives, resolves them through the existing capability resolver/index, and closes the D2.8 acquisition state machine (`gap_detected -> ... -> closed_as_binding | closed_as_limitation | closed_as_still_blocked`) by orchestrating the existing typed acquisition planner and Fabric connector registry. The closure rule is strict: a task marked done by a fetcher or human is **not** closure; only a rerun that consumes the updated capability index and changes binding/limitation/blocker state is closure. S3 is A-side substrate authority and lives in `runtime.quality`.

**Tech Stack:** Python 3.14, Pydantic v2 (strict `extra="forbid"` models), existing `runtime.quality` capability resolver/index/acquisition planner, Fabric connector registry (deterministic fixture mode for replay), `run_universal_outcome_corpus.py` route, pytest, existing `tools.quality.validation` validators.

---

## Scope

This task plan implements only roadmap slice S3.

It does **not** implement: S4 epistemic-regime classification, S5 coupling/composition, S6 blind-spot producers, generative search beyond what S2 shipped, rich predictive models, production claim authority, public rollout authority, or a new dataset catalog. It also does **not** require grounding the entire UA-MSME proving set — only proving the loop closes (see "First proving case" below).

Cells moved by S3:

- **None.** `KNOWLEDGE.substrate_coverage` is already `implemented` (resolver/index exist); S3 advances its real coverage, not its cell state. S3 closes no open cluster cell.

Layers advanced (not cluster cells):

- `facet_substrate`: `seed -> implemented` (compositional facet-space construct demand + denominator-aware coverage).
- `acquisition_loop`: `implemented_but_not_orchestrated + bridge_missing -> implemented` (closed loop with rerun-proven closure).

Open cell count delta:

- Baseline remains `17`; current cluster-map open cell count remains `15` after S3 (no cluster cell closed).
- S3 progress is therefore measured by the **acquisition-loop closure** and the **corpus metric**, recorded in the S3 manifest, not by a cell delta. Do not "find" a cell to close to make burn-down move.

Acquisition branch:

- S2 reported `acquisition_branch_state="bridge_missing"`. S3 **closes** it: after S3, `acquisition_branch_state="implemented"`.
- S3 must not claim production authority for any acquired source, and must not let proxy/simulation bindings satisfy production claim slots.

First proving case:

- Pinned to `ua-msme-affordable-loans-2022` and the five D2.10 constructs: `credit_program_enrollment`, `firm_survival`, `regional_displacement_pressure`, `credit_access`, `fiscal_burden_per_beneficiary`.
- Done = **at least one** pinned construct grounds through the full state machine (the loop closes / mechanism proven). The remaining pinned constructs are a **staged follow-up** recorded in the manifest, not required for S3 done.

## Architecture Decision

S3 contracts live in `polisyos.runtime.quality.design_axes.substrate_acquisition`, not in `pdc` and not in `scientist`.

Reason: substrate coverage, capability binding, and acquisition closure are A-side authority concerns on the ADR-0174 capability-graph spine, alongside `capability_resolver`, `capability_index`, and `acquisition_planner`. They are not B-side generation and not the PDC narrow-waist record (that is `pdc._impl`).

Reuse-first (no new data lake, no parallel catalog):

- `runtime.quality.capability_resolver` — resolve a `ConstructExpression` to a binding or typed gap.
- `runtime.quality.capability_index` — capability-index delta and frozen-ref replay.
- `runtime.quality.acquisition_planner` — `requirement_gaps_from_compiled_specs` + `plan_requirement_gap_acquisition` (eligibility-before-ranking, VOI).
- `runtime.quality.production_data_contract_index` — binding report (construct path, not scenario-family authority).
- `runtime.quality.capability_white_space` — coverage denominator base.
- `fabric.connectors` registry — `SourceDiscoveryCandidate` in deterministic fixture mode (no live network in tests/replay).
- S0 contracts from `pdc._impl.layer2_readiness`: `AuthorityBoundary`, `AxisFirewallStatus`, `CertifiedOperationEnvelope`, `ValueOfInformationEstimate`, and the frozen `facet_primitives` from `layer2_minimal_seed_manifest.json`.

Import boundaries:

- `runtime.quality` may import `pdc._impl.layer2_readiness` contracts and `fabric.connectors`, but must not import `scientist` or B-side search.
- The acquisition loop must run deterministically from a frozen fixture source in tests and replay; live connector fetches are gated behind an explicit non-test flag and are never required for closure proof.

S3 public statuses (intermediate D2.8 states plus terminal):

- States: `gap_detected`, `eligibility_checked`, `ranked_by_voi`, `task_opened`, `source_acquired`, `source_contract_validated`, `capability_index_updated`, `rerun_started`, `rerun_consumed_delta`.
- Terminal: `closed_as_binding`, `closed_as_limitation`, `closed_as_still_blocked`.

S3 authority boundary:

- `authoritative_for`: `substrate_coverage_snapshot`, `acquisition_loop_closure`, `construct_binding_status`, and (for grounded constructs at governed posture) `governed_construct_binding`.
- `may_not_use_for`: `production_claim_authority`, `scenario_family_authority`, `publication_authority`, `rollout_authority`, `claim_authority_from_proxy_or_simulation`.

## Pattern Pass

Relevant failure patterns: `P01`, `P02`, `P05`, `P06`, `P07`, `P10`, `P12`, `P13`, `P14`.

Existing risks found:

- `acquisition_planner` emits plans but no orchestrated loop **closes** them; without S3 the acquisition branch stays `bridge_missing` (P01/P02).
- `production_data_contract_index` still has a legacy scenario-family path; S3 must bind by `ConstructExpression`, never let scenario-family strings act as authority selectors (P06; ADR-0174 C1).
- A capability-index delta can silently mutate closed-case replay if not frozen-ref guarded (P07; ADR-0174 C2).
- A proxy/simulation/context-only binding can launder into production claim authority (P05/P14).
- "Task done" can be mistaken for closure without a rerun that changes binding state (P01).

Correct pattern:

- Construct demand is a compositional facet-space `ConstructExpression`, bound via the resolver to a typed `CapabilityBindingResult` with authority, lineage, time, rights, and independence semantics.
- A typed gap opens an owned `AcquisitionTaskRecord`; automated `SourceDiscoveryCandidate` (Fabric) runs before human fallback; a validated `SourceContract` produces a capability-index delta; a rerun consumes the delta and proves closure with a `RerunClosureReceipt`.
- Coverage is denominator-aware (`SubstrateCoverageSnapshot`) with bounded honest abstention.
- Replay is frozen-ref safe: a closed case replays unchanged after an index delta.

Missing capability labels before implementation:

- `producer_missing` for the S3 substrate/acquisition orchestration loop.
- `artifact_missing` for `ConstructExpression`, `ConstructDemandLedger`, `CapabilityBindingResult`, `AcquisitionTaskRecord`, `SourceDiscoveryCandidate`, `SourceContract` delta, `RerunClosureReceipt`, `SubstrateCoverageSnapshot`.
- `bridge_missing` for gap -> acquisition task -> source contract -> index delta -> rerun.
- `surface_missing` for the EXPERT/MACHINE coverage + abstention surface.
- `semantic_test_missing` for full-state-machine closure, no-rerun-no-closure, frozen-ref replay, scenario-family non-authority, proxy-not-production, bounded abstention, and the pinned UA-MSME grounding.

Acceptance signal:

- One pinned UA-MSME construct grounds through the full D2.8 state machine deterministically, producing a `RerunClosureReceipt` whose terminal state is `closed_as_binding`.
- `acquisition_branch_state` transitions `bridge_missing -> implemented`.
- A `SubstrateCoverageSnapshot` reports facet-space coverage and a bounded abstention rate.
- Closed-case replay is unchanged by the index delta (frozen-ref safe).
- The corpus real-producer result for the grounded construct moves from `blocked_construct_not_observed` to a governed binding (the honest metric moves), without weakening production floors.
- Negative controls fail closed: scenario-family string cannot select authority; task-done-without-rerun is not closure; proxy binding is limitation not production.
- Cluster-map open cell count stays `15`; S3 closes no cell.

## Source Of Truth

| Concern | Source |
| --- | --- |
| Roadmap closure contract | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md#s3--concrete-substrate--closed-acquisition-loop-ukrainian-msme` |
| Substrate/acquisition architecture | `docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md` (D2.3, D2.7, D2.8, D2.10) |
| Authority ordering / replay / scenario-family sunset | `docs/adr/0174-policy-evidence-capability-graph.md` (C1, C2) |
| Shared S0 contracts + frozen facet primitives | `src/polisyos/pdc/_impl/layer2_readiness.py`, `architecture/policy_design_case/layer2_minimal_seed_manifest.json` |
| First proving case | `architecture/policy_design_case/layer2_first_proving_case.json` |
| Existing resolver/index/planner | `src/polisyos/runtime/quality/capability_resolver.py`, `capability_index.py`, `acquisition_planner.py`, `production_data_contract_index.py`, `capability_white_space.py` |
| Connectors | `src/polisyos/fabric/connectors/` |
| Canonical corpus route | `tools/quality/validation/run_universal_outcome_corpus.py` |
| Floor governance | `architecture/policy_design_case/layer2_floor_governance.toml#s3_acquisition_closure` |
| Cluster closure contracts | `architecture/policy_design_case/cluster_ownership_map.toml` |

## Files

Create:

- `src/polisyos/runtime/quality/design_axes/substrate_acquisition.py`
- `architecture/policy_design_case/layer2_s3_substrate_acquisition_manifest.json`
- `tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
- `tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json` (deterministic acquired-source fixture)

Modify:

- `src/polisyos/runtime/quality/__init__.py` (export S3 contracts)
- `tools/quality/validation/run_universal_outcome_corpus.py` (consume grounded binding on the corpus route; behind the existing real-producer path, no scenario-family authority)
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py` (recognize S3 manifest + `acquisition_branch_state` transition; keep `open_cell_count == 15`)
- `architecture/policy_design_case/layer2_floor_governance.toml` (add `s3_acquisition_closure` floor)
- `architecture/policy_design_case/inventory.json` (register S3 manifest)

---

## Task 1: Red-First S3 Semantic And Negative Tests

**Files:**

- Create: `tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py`
- Create: `src/polisyos/runtime/quality/design_axes/substrate_acquisition.py` (empty/skeleton so import fails red on behavior, not syntax)

- [x] **Step 1: Write failing unit tests for the S3 contracts and loop**

Create `tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

# CapabilityBindingResult is REUSED from the existing capability spine, not redefined.
from polisyos.runtime.quality.capability_authority import CapabilityBindingResult
from polisyos.runtime.quality.design_axes.substrate_acquisition import (
    AcquisitionState,
    ConstructDemandLedger,
    ConstructExpression,
    SubstrateAcquisitionLoop,
    SubstrateCoverageSnapshot,
    is_production_claim_admissible,
    max_admissible_posture,
    resolve_expression,
)

PINNED = "credit_program_enrollment"
SEED_FACETS = ["construct", "actor", "jurisdiction", "population_scope", "time_role", "evidence_status"]


def _expression(construct: str = PINNED) -> ConstructExpression:
    return ConstructExpression(
        construct=construct,
        facets={
            "actor": "public_credit_program_operator",
            "jurisdiction": "ua",
            "population_scope": "wartime_msme",
            "time_role": "observation",
            "evidence_status": "demanded",
        },
        authority_posture="governed",
        rule_version_refs=["repo://architecture/policy_design_case/layer2_minimal_seed_manifest.json"],
    )


def test_construct_expression_composes_only_from_seed_facet_primitives() -> None:
    expr = _expression()
    assert expr.is_composed_from(SEED_FACETS)


def test_construct_expression_rejects_unknown_facet_primitive() -> None:
    with pytest.raises(ValidationError, match="facet primitive 'made_up' is not in the frozen seed"):
        ConstructExpression(
            construct=PINNED,
            facets={"made_up": "x"},
            authority_posture="governed",
            rule_version_refs=["repo://architecture/policy_design_case/layer2_minimal_seed_manifest.json"],
            allowed_facet_primitives=SEED_FACETS,
        )


def test_construct_demand_ledger_is_denominator_never_evidence() -> None:
    ledger = ConstructDemandLedger(
        case_id="ua-msme-affordable-loans-2022",
        expressions=[_expression()],
        authority_posture="governed",
    )
    assert ledger.authority_boundary.may_not_use_for and "claim_authority" in ledger.authority_boundary.may_not_use_for


def test_resolve_expression_binds_by_construct_not_scenario_family() -> None:
    # ADR-0174 C1 / P06: S3 resolves on the construct path and returns the reused
    # CapabilityBindingResult. A scenario-family string is never an authority selector.
    binding = resolve_expression(
        _expression(),
        source="tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json",
    )
    assert isinstance(binding, CapabilityBindingResult)
    assert binding.construct_ref == PINNED
    assert "production_msme_panel" not in (binding.selected_capability_ref or "")


def test_proxy_status_is_limitation_not_production() -> None:
    # Helpers interpret the reused binding's status/posture; no scenario-family selector.
    assert max_admissible_posture("selected_proxy_with_limitation", "production") == "governed"
    assert is_production_claim_admissible("selected_proxy_with_limitation", "governed") is False
    assert is_production_claim_admissible("selected_exact", "production") is True


def test_substrate_coverage_snapshot_reports_bounded_abstention() -> None:
    snap = SubstrateCoverageSnapshot(
        demanded=5,
        observed=1,
        proxy_limited=1,
        construct_not_observed=3,
        authority_posture="governed",
    )
    assert 0.0 <= snap.bounded_abstention_rate() <= 1.0
    assert snap.construct_demand_coverage() == pytest.approx(2 / 5)


def test_acquisition_loop_full_state_machine_closes_as_binding() -> None:
    loop = SubstrateAcquisitionLoop.from_fixture(
        expression=_expression(),
        source_fixture="tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json",
    )
    receipt = loop.run_to_closure()
    assert [s.state for s in receipt.transitions] == [
        AcquisitionState.GAP_DETECTED,
        AcquisitionState.ELIGIBILITY_CHECKED,
        AcquisitionState.RANKED_BY_VOI,
        AcquisitionState.TASK_OPENED,
        AcquisitionState.SOURCE_ACQUIRED,
        AcquisitionState.SOURCE_CONTRACT_VALIDATED,
        AcquisitionState.CAPABILITY_INDEX_UPDATED,
        AcquisitionState.RERUN_STARTED,
        AcquisitionState.RERUN_CONSUMED_DELTA,
        AcquisitionState.CLOSED_AS_BINDING,
    ]
    assert receipt.terminal == AcquisitionState.CLOSED_AS_BINDING
    assert receipt.voi_ref is not None  # eligibility-before-ranking used VOI


def test_task_done_without_rerun_is_not_closure() -> None:
    loop = SubstrateAcquisitionLoop.from_fixture(
        expression=_expression(),
        source_fixture="tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json",
    )
    loop.advance_to(AcquisitionState.CAPABILITY_INDEX_UPDATED)  # stop before rerun
    with pytest.raises(RuntimeError, match="closure requires a rerun that consumes the index delta"):
        loop.assert_closed()


def test_index_delta_does_not_mutate_closed_case_replay() -> None:
    # ADR-0174 C2: a closed case replays unchanged after a new index delta.
    loop = SubstrateAcquisitionLoop.from_fixture(
        expression=_expression(),
        source_fixture="tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json",
    )
    frozen = loop.freeze_closed_case_refs()
    loop.run_to_closure()
    assert loop.replay_closed_case(frozen) == frozen.outcome  # unchanged
```

- [x] **Step 2: Run the tests and verify they fail red**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py -q
```

Expected: `ImportError`/`AttributeError` for the not-yet-implemented contracts and loop.

## Task 2: Facet Substrate Contracts And Resolver-Over-Expressions

**Files:**

- Modify: `src/polisyos/runtime/quality/design_axes/substrate_acquisition.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`

- [x] **Step 1: Implement the strict S3 substrate contracts**

In `src/polisyos/runtime/quality/design_axes/substrate_acquisition.py` define strict (`extra="forbid"`) models, reusing S0 contracts:

- `ConstructExpression`: `construct`, `facets: dict[str,str]`, `authority_posture`, `rule_version_refs`, optional `allowed_facet_primitives`. Validator: every facet key must be in the frozen seed primitives (load from `layer2_minimal_seed_manifest.json` if `allowed_facet_primitives` not passed). Method `is_composed_from(primitives)`.
- `ConstructDemandLedger`: `case_id`, `expressions: list[ConstructExpression]`, `authority_posture`, derived `authority_boundary: AuthorityBoundary` (from `pdc._impl.layer2_readiness`) with `may_not_use_for` including `claim_authority`. The denominator, never evidence.
- `CapabilityBindingResult`: **reused** from `runtime.quality.capability_authority` — do **not** redefine. It is the frozen capability-spine contract (`binding_id`, `status: CapabilityBindingStatus`, `authority_level: AuthorityPosture`, `construct_ref`, `selected_capability_ref`, `factors` (>=9), `limitations`, `blocked_reasons`, ...). S3 adds only module-level interpreters `max_admissible_posture(status, posture)` (proxy/context/simulation cap at governed) and `is_production_claim_admissible(status, posture)`, plus `resolve_expression(expr)` which calls the existing `RequirementToCapabilityResolver` on the **construct path** (ADR-0174 C1; scenario-family strings never select authority).
- `SubstrateCoverageSnapshot`: `demanded`, `observed`, `proxy_limited`, `construct_not_observed`, `authority_posture`; methods `construct_demand_coverage()`, `bounded_abstention_rate()`.

Bind via the existing resolver:

- `resolve_expression(expr) -> CapabilityBindingResult` delegates to `capability_resolver` and `production_data_contract_index` on the **construct** path; it must not consult scenario-family selectors for authority.

Reference implementation:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc._impl.layer2_readiness import AuthorityBoundary
# Reuse the existing capability spine; do not redefine these.
from polisyos.runtime.quality.capability_authority import CapabilityBindingResult
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver

_SCHEMA = "policyos.policy_design_case.layer2_s3_substrate_acquisition.v1"
_SEED = "architecture/policy_design_case/layer2_minimal_seed_manifest.json"


def _frozen_facet_primitives(repo_root: Path) -> list[str]:
    return list(json.loads((repo_root / _SEED).read_text())["facet_primitives"])


class _S3Model(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[
        "policyos.policy_design_case.layer2_s3_substrate_acquisition.v1"
    ] = _SCHEMA


class ConstructExpression(_S3Model):
    construct: str = Field(min_length=1)
    facets: dict[str, str] = Field(default_factory=dict)
    authority_posture: Literal["research", "governed", "production"]
    rule_version_refs: list[str] = Field(default_factory=list)
    allowed_facet_primitives: list[str] | None = None

    @model_validator(mode="after")
    def _facets_in_seed(self) -> "ConstructExpression":
        allowed = set(self.allowed_facet_primitives or [])
        for key in self.facets:
            if allowed and key not in allowed:
                raise ValueError(
                    f"facet primitive '{key}' is not in the frozen seed primitives"
                )
        return self

    def is_composed_from(self, primitives: list[str]) -> bool:
        return set(self.facets).issubset(set(primitives))


# CapabilityBindingResult is REUSED from capability_authority (frozen, factors>=9).
# S3 adds only thin status/posture interpreters and a construct-path resolver wrapper.

_PROXY_STATUSES = {
    "selected_proxy_with_limitation", "selected_context_only", "selected_simulation_only",
}
_EXACT_STATUSES = {"selected_exact", "selected_derived"}


def max_admissible_posture(status: str, posture: str) -> str:
    """Proxy/context/simulation bindings cap at governed; otherwise posture is unchanged."""
    return "governed" if status in _PROXY_STATUSES else posture


def is_production_claim_admissible(status: str, posture: str) -> bool:
    return status in _EXACT_STATUSES and posture == "production"


def resolve_expression(
    expr: ConstructExpression,
    *,
    source: str | None = None,
    resolver: RequirementToCapabilityResolver | None = None,
) -> CapabilityBindingResult:
    """Resolve a ConstructExpression on the CONSTRUCT path and return the reused binding.

    Builds a query whose authority selector is the construct (plus optional facet refs),
    then delegates to the existing resolver. ADR-0174 C1 keeps scenario-family strings as
    compatibility projections, never authority selectors.

    NOTE: confirm the exact `RequirementToCapabilityQuery` field names and the resolver
    constructor against `capability_resolver.py` when implementing; the keys below are the
    construct-path shape, not a scenario-family selector.
    """
    resolver = resolver or RequirementToCapabilityResolver()
    query = {
        "requirement_id": f"s3:{expr.construct}",
        "construct_ref": expr.construct,
        "facets": expr.facets,
        "authority_posture": expr.authority_posture,
        "source_ref": source,
    }
    return resolver.resolve(query)


class ConstructDemandLedger(_S3Model):
    case_id: str
    expressions: list[ConstructExpression]
    authority_posture: Literal["research", "governed", "production"]

    @property
    def authority_boundary(self) -> AuthorityBoundary:
        return AuthorityBoundary(
            authoritative_for=["construct_demand"],
            may_not_use_for=["claim_authority", "evidence_authority"],
            source_authority="demand_ledger",
            posture=self.authority_posture,
            rule_version_refs=["repo://" + _SEED],
        )


class SubstrateCoverageSnapshot(_S3Model):
    demanded: int = Field(ge=0)
    observed: int = Field(ge=0)
    proxy_limited: int = Field(ge=0)
    construct_not_observed: int = Field(ge=0)
    authority_posture: Literal["research", "governed", "production"]

    def construct_demand_coverage(self) -> float:
        return 0.0 if self.demanded == 0 else (self.observed + self.proxy_limited) / self.demanded

    def bounded_abstention_rate(self) -> float:
        return 0.0 if self.demanded == 0 else self.construct_not_observed / self.demanded
```

Note: resolve `_SEED` against the repo root (not cwd) in the real module, mirroring `ensure_repo_import_roots` usage elsewhere. The unit test passes `allowed_facet_primitives` explicitly so it does not depend on filesystem state.

- [x] **Step 2: Re-run unit tests — contract/coverage tests should pass; loop tests still red**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py -q
```

## Task 3: Closed Acquisition Loop (D2.8 State Machine)

**Files:**

- Modify: `src/polisyos/runtime/quality/design_axes/substrate_acquisition.py`
- Create: `tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json`

- [x] **Step 1: Add the deterministic acquired-source fixture**

Create `tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json` with a minimal but real-shaped source: dataset identity, lineage, rights/legal-use scope, coverage period, update cadence, linkage-key quality, construct-validity note, and the rows needed to bind `credit_program_enrollment` at governed posture (no PII; fixture-only).

- [x] **Step 2: Implement `SubstrateAcquisitionLoop` and `AcquisitionState`**

- `AcquisitionState`: `StrEnum` with the 10 states from the Architecture Decision.
- `SubstrateAcquisitionLoop.from_fixture(expression, source_fixture)`: deterministic; no live network.
- Loop transitions, reusing existing pieces:
  - `gap_detected`: resolver returns `blocked_construct_not_observed`/`blocked_acquisition_required`.
  - `eligibility_checked` -> `ranked_by_voi`: `acquisition_planner.requirement_gaps_from_compiled_specs` + `plan_requirement_gap_acquisition`; eligibility precedes ranking; `ValueOfInformationEstimate` (S0) ranks. Record `voi_ref`.
  - `task_opened`: `AcquisitionTaskRecord` (owner, TTL, legal-use review, expected authority envelope, automated/human route).
  - `source_acquired`: `SourceDiscoveryCandidate` from the Fabric connector registry in **fixture mode** (the JSON fixture); live fetch gated behind an explicit non-test flag.
  - `source_contract_validated`: `SourceContract` with lineage/quality/rights/freshness/construct-validity/authority-derivation; rejects on missing rights or unusable dictionary.
  - `capability_index_updated`: `capability_index` delta from the source contract.
  - `rerun_started` -> `rerun_consumed_delta`: re-resolve the expression against the updated index.
  - terminal: `closed_as_binding` if the rerun yields a governed binding; `closed_as_limitation` if only proxy/sim/context; `closed_as_still_blocked` otherwise.
- `RerunClosureReceipt`: `transitions`, `terminal`, `voi_ref`, `binding`, `coverage_snapshot`, frozen-ref refs.
- Closure rule: `assert_closed()` raises unless the receipt reached `rerun_consumed_delta` and changed binding state. `freeze_closed_case_refs()` / `replay_closed_case(frozen)` prove C2 frozen-ref safety (replay unchanged after later deltas).

Reference skeleton:

```python
from enum import StrEnum


class AcquisitionState(StrEnum):
    GAP_DETECTED = "gap_detected"
    ELIGIBILITY_CHECKED = "eligibility_checked"
    RANKED_BY_VOI = "ranked_by_voi"
    TASK_OPENED = "task_opened"
    SOURCE_ACQUIRED = "source_acquired"
    SOURCE_CONTRACT_VALIDATED = "source_contract_validated"
    CAPABILITY_INDEX_UPDATED = "capability_index_updated"
    RERUN_STARTED = "rerun_started"
    RERUN_CONSUMED_DELTA = "rerun_consumed_delta"
    CLOSED_AS_BINDING = "closed_as_binding"
    CLOSED_AS_LIMITATION = "closed_as_limitation"
    CLOSED_AS_STILL_BLOCKED = "closed_as_still_blocked"


_NON_TERMINAL_END = AcquisitionState.RERUN_CONSUMED_DELTA
_TERMINALS = {
    AcquisitionState.CLOSED_AS_BINDING,
    AcquisitionState.CLOSED_AS_LIMITATION,
    AcquisitionState.CLOSED_AS_STILL_BLOCKED,
}


class SubstrateAcquisitionLoop:
    """Deterministic, replay-safe acquisition loop. No live network in tests/replay."""

    @classmethod
    def from_fixture(cls, *, expression: "ConstructExpression", source_fixture: str) -> "SubstrateAcquisitionLoop":
        ...

    def run_to_closure(self) -> "RerunClosureReceipt":
        # gap_detected:            capability_resolver -> blocked_construct_not_observed
        # eligibility_checked,
        # ranked_by_voi:           acquisition_planner.requirement_gaps_from_compiled_specs
        #                          + plan_requirement_gap_acquisition; eligibility precedes
        #                          ranking; ValueOfInformationEstimate (S0) -> voi_ref
        # task_opened:             AcquisitionTaskRecord(owner, ttl, legal_use, route)
        # source_acquired:         SourceDiscoveryCandidate via fabric.connectors (fixture mode)
        # source_contract_validated: SourceContract(lineage/quality/rights/freshness/validity)
        # capability_index_updated:  capability_index delta
        # rerun_started,
        # rerun_consumed_delta:    re-resolve expression against the updated index
        # terminal:                closed_as_binding | closed_as_limitation | closed_as_still_blocked
        ...

    def advance_to(self, state: AcquisitionState) -> None:
        ...

    def assert_closed(self) -> None:
        if self._state != _NON_TERMINAL_END and self._state not in _TERMINALS:
            raise RuntimeError("closure requires a rerun that consumes the index delta")

    def freeze_closed_case_refs(self) -> "FrozenClosedCase":
        # ADR-0174 C2: snapshot rules + source refs + constraint refs that closed the case
        ...

    def replay_closed_case(self, frozen: "FrozenClosedCase") -> object:
        # replay uses frozen refs; later index deltas must not change the outcome
        ...
```

Supporting record contracts (new S3 artifacts; strict, reuse `_S3Model`):

```python
class AcquisitionTaskRecord(_S3Model):
    construct_ref: str
    owner: str
    route: Literal["automated", "human_fallback"]
    ttl_days: int = Field(ge=1)
    legal_use_reviewed: bool
    expected_authority_posture: Literal["research", "governed", "production"]
    voi_ref: str


class SourceDiscoveryCandidate(_S3Model):
    construct_ref: str
    connector: str          # fabric connector id from the registry
    source_fixture: str     # deterministic fixture path in tests/replay
    rights_scope: str


class SourceContract(_S3Model):
    construct_ref: str
    source_id: str
    lineage_ref: str
    rights_scope: str
    coverage_period: str
    update_cadence: str
    linkage_key_quality: str
    construct_validity_note: str
    capability_index_delta_ref: str


class _Transition(_S3Model):
    state: AcquisitionState
    detail: str | None = None


class FrozenClosedCase(_S3Model):
    rule_version_ref: str
    capability_index_ref: str
    constraint_refs: tuple[str, ...]
    outcome: str


class RerunClosureReceipt(_S3Model):
    construct_ref: str
    transitions: tuple[_Transition, ...]
    terminal: AcquisitionState
    voi_ref: str | None
    binding_status: str
    coverage_snapshot: SubstrateCoverageSnapshot
    frozen: FrozenClosedCase
```

Concrete `run_to_closure` body (reuses the real resolver and acquisition planner):

```python
from polisyos.runtime.quality.acquisition_planner import (
    plan_requirement_gap_acquisition,
    requirement_gaps_from_compiled_specs,
)

    def run_to_closure(self) -> RerunClosureReceipt:
        t: list[_Transition] = []
        binding = resolve_expression(self._expression)               # gap_detected
        t.append(_Transition(state=AcquisitionState.GAP_DETECTED, detail=binding.status))
        if binding.status not in {"blocked_construct_not_observed", "blocked_acquisition_required"}:
            return self._close(t, binding)                           # already observed
        gaps = requirement_gaps_from_compiled_specs(                 # eligibility_checked
            data_requirement_specs=self._data_requirement_specs(),
        )
        plan = plan_requirement_gap_acquisition(                     # ranked_by_voi
            run_id=self._run_id, requirement_gaps=gaps, voi_report=self._voi_report(),
        )
        t.append(_Transition(state=AcquisitionState.ELIGIBILITY_CHECKED))
        t.append(_Transition(state=AcquisitionState.RANKED_BY_VOI, detail=self._voi_ref))
        task = self._open_task(plan)                                 # task_opened
        t.append(_Transition(state=AcquisitionState.TASK_OPENED, detail=task.route))
        candidate = self._discover_source(task)                      # source_acquired (fabric, fixture)
        t.append(_Transition(state=AcquisitionState.SOURCE_ACQUIRED, detail=candidate.connector))
        contract = self._validate_source_contract(candidate)        # source_contract_validated
        t.append(_Transition(state=AcquisitionState.SOURCE_CONTRACT_VALIDATED))
        self._apply_index_delta(contract)                           # capability_index_updated
        t.append(_Transition(state=AcquisitionState.CAPABILITY_INDEX_UPDATED,
                             detail=contract.capability_index_delta_ref))
        t.append(_Transition(state=AcquisitionState.RERUN_STARTED))
        rebinding = resolve_expression(self._expression)            # rerun_consumed_delta
        t.append(_Transition(state=AcquisitionState.RERUN_CONSUMED_DELTA, detail=rebinding.status))
        self._state = AcquisitionState.RERUN_CONSUMED_DELTA
        return self._close(t, rebinding)

    def _close(self, t: list[_Transition], binding: "CapabilityBindingResult") -> RerunClosureReceipt:
        if binding.status in _EXACT_STATUSES:
            terminal = AcquisitionState.CLOSED_AS_BINDING
        elif binding.status in _PROXY_STATUSES:
            terminal = AcquisitionState.CLOSED_AS_LIMITATION
        else:
            terminal = AcquisitionState.CLOSED_AS_STILL_BLOCKED
        t.append(_Transition(state=terminal))
        self._terminal = terminal
        return self._build_receipt(t, terminal, binding)
```

Private helper bodies (reuse the real spec, connector, and incremental-index APIs):

```python
import json
from pathlib import Path

from polisyos.data_requirement._impl.models import DataRequirementSpec
from polisyos.fabric.connectors import get_registry
from polisyos.runtime.quality.capability_index_compiler import (
    CapabilityIndexCompilerConfig,
    compile_capability_index,
)

    def _data_requirement_specs(self) -> tuple[DataRequirementSpec, ...]:
        # Construct path: facets -> mandatory_facets; families are a derived compatibility
        # projection, never an authority selector (ADR-0174 C1). DataRequirementSpec is the
        # existing frozen contract in polisyos.data_requirement._impl.models.
        e = self._expression
        return (
            DataRequirementSpec(
                requirement_id=f"s3:{e.construct}",
                claim_id=f"s3:{self._case_id}:{e.construct}",
                required_data_families=(e.construct,),
                scope=self._scope_from_facets(e.facets),
                recency_horizon="P3Y",
                quality_minima=self._default_quality_minima(),
                missingness_tolerance=0.2,
                transformation_tolerance=self._default_transformation_tolerance(),
                admissibility_predicates=("construct_validity", "rights_access"),
                mandatory_facets=tuple(e.facets),
            ),
        )

    def _discover_source(self, task: AcquisitionTaskRecord) -> SourceDiscoveryCandidate:
        if self._fixture_mode:                                 # tests + replay: no network
            data = json.loads(Path(self._source_fixture).read_text())
            return SourceDiscoveryCandidate(
                construct_ref=task.construct_ref,
                connector=data["connector"],
                source_fixture=self._source_fixture,
                rights_scope=data["rights_scope"],
            )
        connector = get_registry().get(task.preferred_connector)  # live mode (non-test flag only)
        ...  # await connector.connect(cfg); await connector.fetch(...); persist; then as above

    def _validate_source_contract(self, candidate: SourceDiscoveryCandidate) -> SourceContract:
        data = json.loads(Path(candidate.source_fixture).read_text())
        if not data.get("rights_scope"):
            raise RuntimeError("source has no usable rights / legal-use scope")
        return SourceContract(
            construct_ref=candidate.construct_ref,
            source_id=data["source_id"],
            lineage_ref=data["lineage_ref"],
            rights_scope=data["rights_scope"],
            coverage_period=data["coverage_period"],
            update_cadence=data["update_cadence"],
            linkage_key_quality=data["linkage_key_quality"],
            construct_validity_note=data["construct_validity_note"],
            capability_index_delta_ref="",                     # set below
        )

    def _apply_index_delta(self, contract: SourceContract) -> None:
        # Materialize the validated source, then INCREMENTAL rebuild. The new manifest path
        # is the frozen capability_index_ref (ADR-0174 C2); white_space feeds coverage.
        self._materialize_source(contract)
        result = compile_capability_index(
            CapabilityIndexCompilerConfig(
                production_data_root=self._production_data_root,
                output_dir=self._index_output_dir,
                mode="incremental",
                previous_manifest_path=self._capability_index_ref,
            )
        )
        contract.capability_index_delta_ref = str(result.manifest_path)
        self._capability_index_ref = result.manifest_path
        self._white_space_report = result.white_space_report_path

    def freeze_closed_case_refs(self) -> FrozenClosedCase:
        return FrozenClosedCase(
            rule_version_ref=self._rule_version_ref,
            capability_index_ref=str(self._capability_index_ref),
            constraint_refs=self._constraint_refs,
            outcome=self._current_outcome(),
        )

    def replay_closed_case(self, frozen: FrozenClosedCase) -> object:
        # C2: re-resolve against the FROZEN index ref; later deltas must not change the outcome.
        return resolve_expression(
            self._expression,
            resolver=self._resolver_for(frozen.capability_index_ref),
        ).status
```

Small builders left to the implementer (all against existing nested types): `_scope_from_facets` (`DataRequirementScope`), `_default_quality_minima` (`DataQualityMinimums`), `_default_transformation_tolerance` (`TransformationTolerance`), `_materialize_source` (drop the fixture rows into the delta region of `production_data_root`), and `_resolver_for(ref)` (a `RequirementToCapabilityResolver` bound to a specific frozen manifest). The compiler's `mode="incremental"` path (`discover_input_fingerprints` + `_merge_incremental_capabilities`) is what makes the delta cheap and replay-safe.

- [x] **Step 3: Re-run unit tests — all green**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py -q
```

Expected: all pass, including `test_acquisition_loop_full_state_machine_closes_as_binding`, `test_task_done_without_rerun_is_not_closure`, `test_index_delta_does_not_mutate_closed_case_replay`.

## Task 4: Canonical Corpus Route Wiring

**Files:**

- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`

- [x] **Step 1: Wire the grounded binding into the real-producer route**

On the real-producer path, when the pinned UA-MSME construct has a governed binding from a closed S3 acquisition loop, the resolver returns the binding instead of `blocked_construct_not_observed`. Constraints:

- governed posture only; production posture stays strict (proxy/sim never production).
- no scenario-family authority selector is introduced.
- the change is additive and guarded by frozen capability-index refs (closed cases unaffected).

- [x] **Step 2: Verify the honest metric moves for the grounded construct (no floor weakening)**

```bash
cd policy-engine
uv run python tools/quality/validation/run_universal_outcome_corpus.py --mode real_producer 2>&1 | tail -40
```

Expected: the grounded construct for `ua-msme-affordable-loans-2022` moves from `blocked_construct_not_observed` to a governed binding; `closeout_honesty_rate` stays `1.0`; production-posture outcomes unchanged. Record the before/after construct status in the S3 manifest.

Verified Task 4 route status: current corpus baseline for the grounded construct is
`blocked_acquisition_required`; the S3 route records
`blocked_acquisition_required -> selected_exact` in the W12.D trace, with
`rollout_blocker_count=0` and production-posture outcome still `typed_blocker`.
The full current corpus reports `closeout_honesty_rate=0.0769`; Task 4 did not
weaken or mask that broader corpus honesty signal.

## Task 5: S3 Manifest And Readiness Validator Update

**Files:**

- Create: `architecture/policy_design_case/layer2_s3_substrate_acquisition_manifest.json`
- Modify: `architecture/policy_design_case/layer2_floor_governance.toml`
- Modify: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`

- [x] **Step 1: Write the S3 manifest (layer-advancement, no cell closed)**

Create `architecture/policy_design_case/layer2_s3_substrate_acquisition_manifest.json` mirroring the S1 manifest shape:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s3_substrate_acquisition_manifest.v1",
  "status": "active",
  "owner": "team-runtime-quality",
  "slice": "S3",
  "layer_capabilities": ["facet_substrate", "acquisition_loop"],
  "cells_closed": [],
  "open_cell_count_baseline": 17,
  "expected_current_open_cell_count": 15,
  "acquisition_branch_state": "implemented",
  "acquisition_state_machine": [
    "gap_detected", "eligibility_checked", "ranked_by_voi", "task_opened",
    "source_acquired", "source_contract_validated", "capability_index_updated",
    "rerun_started", "rerun_consumed_delta",
    "closed_as_binding", "closed_as_limitation", "closed_as_still_blocked"
  ],
  "first_proving_case_id": "ua-msme-affordable-loans-2022",
  "pinned_constructs": [
    "credit_program_enrollment", "firm_survival", "regional_displacement_pressure",
    "credit_access", "fiscal_burden_per_beneficiary"
  ],
  "constructs_grounded_in_s3": ["credit_program_enrollment"],
  "constructs_staged_followup": ["firm_survival", "regional_displacement_pressure", "credit_access", "fiscal_burden_per_beneficiary"],
  "required_artifacts": [
    "ConstructExpression", "ConstructDemandLedger", "CapabilityBindingResult",
    "AcquisitionTaskRecord", "SourceDiscoveryCandidate", "SourceContract",
    "RerunClosureReceipt", "SubstrateCoverageSnapshot"
  ],
  "floors": ["s3_acquisition_closure"],
  "authority_scope": ["substrate_coverage_snapshot", "acquisition_loop_closure", "governed_construct_binding"],
  "may_not_use_for": ["production_claim_authority", "scenario_family_authority", "publication_authority", "rollout_authority", "claim_authority_from_proxy_or_simulation"],
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py",
  "rule_version_ref": "repo://docs/adr/0174-policy-evidence-capability-graph.md",
  "firewalls": ["P01", "P02", "P05", "P06", "P07", "P10", "P12", "P14"]
}
```

Add the `s3_acquisition_closure` floor to `layer2_floor_governance.toml`: metric `acquisition_loop_closure_rate`, owner `team-integration-spine`, floor artifact = governed config, revision rule documented.

- [x] **Step 2: Update the readiness validator to recognize S3**

The validator must additionally assert: `acquisition_branch_state == "implemented"` after S3; `cells_closed == []` and `expected_current_open_cell_count == 15`; the S3 manifest is registered in inventory; `may_not_use_for` includes the production/scenario-family/proxy clauses. Keep `open_cell_count == 15`.

Add an `_validate_s3` step in the existing validator (same `issues.append({"code": ...})` convention used by the S0/S2 checks):

```python
def _validate_s3_substrate_acquisition(root: Path, issues: list[dict]) -> None:
    path = root / "architecture/policy_design_case/layer2_s3_substrate_acquisition_manifest.json"
    if not path.exists():
        return  # S3 not yet landed; readiness still valid at the S0/S2 baseline
    s3 = json.loads(path.read_text())
    if s3.get("acquisition_branch_state") != "implemented":
        issues.append({"code": "layer2_s3_acquisition_branch_not_implemented",
                       "message": "S3 must close the acquisition branch (bridge_missing -> implemented)."})
    if s3.get("cells_closed"):
        issues.append({"code": "layer2_s3_must_not_close_cluster_cell",
                       "message": "S3 advances layers only; it closes no cluster cell."})
    if s3.get("expected_current_open_cell_count") != 15:
        issues.append({"code": "layer2_s3_open_cell_count_drift",
                       "message": "S3 must keep current open_cell_count at 15."})
    deny = set(s3.get("may_not_use_for", []))
    required_deny = {"production_claim_authority", "scenario_family_authority",
                     "claim_authority_from_proxy_or_simulation"}
    if not required_deny <= deny:
        issues.append({"code": "layer2_s3_authority_boundary_incomplete",
                       "message": "S3 may_not_use_for must block production/scenario-family/proxy authority."})
```

Call it from `validate_layer2_readiness_payloads` (or the file-path validate entry) alongside the existing S0/S2 checks.

- [x] **Step 3: Add repo-quality tests for the S3 readiness/loop facts**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]
S3_MANIFEST = REPO_ROOT / "architecture/policy_design_case/layer2_s3_substrate_acquisition_manifest.json"
FIRST_PROVING = REPO_ROOT / "architecture/policy_design_case/layer2_first_proving_case.json"


def _s3() -> dict:
    return json.loads(S3_MANIFEST.read_text())


def test_layer2_s3_manifest_is_valid() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["open_cell_count"] == 15  # type: ignore[index]


def test_layer2_s3_closes_no_cluster_cell() -> None:
    assert _s3()["cells_closed"] == []
    assert _s3()["expected_current_open_cell_count"] == 15


def test_layer2_s3_acquisition_branch_state_is_implemented() -> None:
    assert _s3()["acquisition_branch_state"] == "implemented"


def test_layer2_s3_pinned_constructs_match_first_proving_case() -> None:
    pinned = set(_s3()["pinned_constructs"])
    proving = set(json.loads(FIRST_PROVING.read_text())["constructs"])
    assert pinned == proving
    assert len(pinned) == 5


def test_layer2_s3_may_not_use_for_blocks_production_and_scenario_family() -> None:
    deny = set(_s3()["may_not_use_for"])
    assert {"production_claim_authority", "scenario_family_authority",
            "claim_authority_from_proxy_or_simulation"} <= deny


def test_layer2_s3_grounded_and_staged_constructs_are_disjoint_and_complete() -> None:
    m = _s3()
    grounded = set(m["constructs_grounded_in_s3"])
    staged = set(m["constructs_staged_followup"])
    assert grounded                              # at least one construct grounded (loop proven)
    assert grounded.isdisjoint(staged)           # no double-claim
    assert grounded | staged == set(m["pinned_constructs"])  # nothing silently dropped
```

## Task 6: Cluster Map, Readiness Progress, And Inventory Wiring

**Files:**

- Modify: `architecture/policy_design_case/inventory.json`

- [x] **Step 1: Register the S3 manifest in inventory**

Add `layer2_s3_substrate_acquisition_manifest.json` to `inventory.json` following the S1/S2 entries.

- [x] **Step 2: Confirm no cluster-map cell is changed by S3**

S3 does not edit `cluster_ownership_map.toml` cell states. The cluster-ownership validator must still report `open_or_incomplete == 15`. If any cell appears closed by S3, that is a defect (over-claim) — revert it.

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['summary']['open_or_incomplete_count'])"
```

Expected: `15`.

## Task 7: Full S3 Verification

- [x] **Step 1: Run the full S3 + regression gate**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py -q
uv run pytest tests/unit/runtime/quality/test_layer2_graded_outcomes.py tests/unit/pdc -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools architecture guardrails check
```

Expected:

```text
S3 unit + repo-quality tests pass.
S1/S2 regression tests pass.
Layer 2 readiness validator: status pass; acquisition_branch_state implemented; open_cell_count 15.
Cluster ownership validator: status pass; open_or_incomplete 15.
Runtime API contract pass.
Architecture guardrails pass.
```

Verified Task 7 command pass: S3 unit and repo-quality tests, S1/S2
regression tests, Layer 2 readiness, cluster ownership, runtime API contract,
and architecture guardrails all pass. Done When audit caveat: full W12.D
real-producer corpus still reports `closeout_honesty_rate=0.0769`, because the
metric measures expert-closeout alignment across all 13 corpus cases; S3 moved
the pinned governed construct to `selected_exact` with `rollout_blocker_count=0`
and production outcome still `typed_blocker`, but it does not close the broader
W12.D expert-delta backlog.

## Done When

1. `ConstructExpression`, `ConstructDemandLedger`, `CapabilityBindingResult`, `SubstrateCoverageSnapshot`, and `SubstrateAcquisitionLoop` are strict, reuse the existing resolver/index/planner/Fabric, and never let a scenario-family string select authority.
2. The full D2.8 state machine closes one pinned UA-MSME construct as `closed_as_binding` deterministically, with a `RerunClosureReceipt` and a VOI-ranked acquisition.
3. A task marked done without a rerun is not closure; a capability-index delta does not mutate closed-case replay (C2).
4. `acquisition_branch_state` is `implemented`; the corpus real-producer status for the grounded construct moved off `blocked_construct_not_observed` at governed posture, with production floors intact and `closeout_honesty_rate == 1.0`.
5. A `SubstrateCoverageSnapshot` reports denominator-aware coverage and a bounded abstention rate.
6. S3 closes no cluster cell; `open_cell_count` stays `15`; both validators pass; the S3 manifest is registered.
7. Staged follow-up constructs are recorded in the manifest, not silently dropped or falsely claimed.

## Verification Commands

See Task 7. Plan-level done = all Task 7 commands pass with the expected output and no production floor is weakened.

## Commit Guidance

Mirror the S1/S2 red-first sequence, one logical commit per task:

```text
test: add layer2 s3 substrate acquisition red tests
feat: add layer2 s3 facet substrate contracts and resolver
feat: close layer2 s3 acquisition loop state machine
feat: wire layer2 s3 grounded binding into corpus route
chore: validate layer2 s3 substrate acquisition
chore: register layer2 s3 substrate acquisition progress
```

End commit messages with the repo's standard co-author trailer. Do not mark any S4+ cell, production authority, or the full UA-MSME set as implemented.
