---
title: PolicyOS Layer 2 S0 Readiness Narrow Waist Task Plan
status: active
owner: team-policyos-runtime
created: 2026-05-30
last_verified: 2026-05-30
stability: draft
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
slice: S0
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
---

# Layer 2 S0 Readiness / Narrow Waist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the S0 readiness gate for Layer 2 before any B-side designer slice starts: shared narrow-waist contracts, governed S0 artifacts, machine validation, and red-first semantic/negative tests.

**Architecture:** S0 creates no policy-design feature and closes no cluster cell. It freezes the shared contracts and governed architecture artifacts that S2+ will consume, then adds a validator proving all 17 open cells, floors, named artifacts, corpus partitions, first proving case, and maturity qualifiers are accounted for. The implementation is reuse-first: strict Pydantic contracts live in neutral `polisyos.pdc`, governed readiness artifacts live under `architecture/policy_design_case/`, and the validator plugs into the existing repo-quality tool pattern.

**Tech Stack:** Python 3.14, Pydantic v2 via `KernelModel`, JSON/TOML governed artifacts, pytest, existing `tools.quality.validation` validators.

---

## Scope

This task plan implements only roadmap slice S0. It does not implement S1 graded outcomes or any B-side generation/search behavior. It creates the readiness contracts and artifacts that S2+ must consume.

Cells moved: none. S0 preserves `open_cell_count = 17` and adds readiness validation only.

## Architecture Decision

`DesignRecordV0` and the S0 narrow-waist contracts live in `polisyos.pdc`, not
`polisyos.scientist.policy_design` and not `polisyos.core.contracts`.

Reason: `DesignRecord` starts as a shadow B-side record in S2, but S9 matures it
into a canonical authority-bearing record consumed by A-side grounding,
projection, replay, and closeout. Keeping it in `scientist.policy_design` would
couple the narrow waist to the generator. Moving it to `core/contracts` would
make a domain-specific policy-design record part of the low-level core contract
substrate. Existing `polisyos.pdc` is the neutral Policy Design Case graph
package, already runtime-owned and authority-boundary aware, so it is the
canonical home for the record while Scientist, Runtime, and later slices consume
it through the public `polisyos.pdc` surface.

## Pattern Pass

Relevant failure patterns: `P01`, `P03`, `P04`, `P05`, `P07`, `P10`, `P13`, `P15`, `P25`.

Existing risk found: the roadmap now names S0 artifacts, but the repo does not yet have a machine-checked S0 readiness bundle. Without this plan, S2 could start with `contract_only`, missing traceability, or a hidden maturity-state drift.

Correct pattern: define-once S0 contracts plus governed artifacts plus validator plus red-first semantic and negative tests. The validator prevents maturity qualifiers from becoming ratchet states and prevents open cells or named D2 artifacts from disappearing.

Missing capability labels before implementation: `contract_only` for shared Layer 2 contracts, `artifact_missing` for S0 governed artifacts, `verification_missing` for S0 readiness, `semantic_test_missing` for S0 authority/maturity/corpus negative controls.

Acceptance signal: `check_policy_design_case_layer2_readiness.py` returns `status=pass`; the unit and repo-quality tests pass; `cluster_ownership_map` still reports 17 open cells; no S0 artifact claims any B-side cell closure.

## Source Of Truth

| Concern | Source |
| --- | --- |
| Roadmap closure contract | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md` |
| Conceptual architecture | `docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md` |
| Open cells and acceptance signals | `architecture/policy_design_case/cluster_ownership_map.toml` |
| Ratchet vocabulary | `architecture/policy_design_case/capability_reality_report.json` |
| Failure patterns | `docs/reference/policy-design-case-failure-patterns.md` |
| Plan lifecycle | `docs/plans/README.md` |

## Files

Create:

- `src/polisyos/pdc/_impl/layer2_readiness.py`
- `architecture/policy_design_case/layer2_minimal_seed_manifest.json`
- `architecture/policy_design_case/layer2_dependency_dag.json`
- `architecture/policy_design_case/layer2_slice_cell_matrix.toml`
- `architecture/policy_design_case/layer2_floor_governance.toml`
- `architecture/policy_design_case/layer2_artifact_traceability.toml`
- `architecture/policy_design_case/layer2_corpus_partition.json`
- `architecture/policy_design_case/layer2_first_proving_case.json`
- `architecture/policy_design_case/layer2_readiness_manifest.json`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `tests/unit/pdc/test_layer2_readiness_contracts.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`

Modify:

- `src/polisyos/pdc/__init__.py`
- `src/polisyos/pdc/README.md`
- `architecture/policy_design_case/inventory.json`

## Task 1: Red-First Shared Contract Tests

**Files:**

- Create: `tests/unit/pdc/test_layer2_readiness_contracts.py`
- Create: `src/polisyos/pdc/_impl/layer2_readiness.py`
- Modify: `src/polisyos/pdc/__init__.py`
- Modify: `src/polisyos/pdc/README.md`

- [ ] **Step 1: Write failing unit tests for the S0 shared contracts**

Create `tests/unit/pdc/test_layer2_readiness_contracts.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.pdc import (
    AxisFirewallStatus,
    AuthorityBoundary,
    CertifiedOperationEnvelope,
    DesignRecordV0,
    MinimalSeedManifest,
)


def _authority_boundary(
    *,
    source_authority: str = "deterministic_producer",
    posture: str = "shadow",
) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["shadow_design_candidate"],
        may_not_use_for=["publication_authority", "rollout_authority"],
        source_authority=source_authority,
        posture=posture,
        rule_version_refs=["repo://architecture/policy_design_case/cluster_ownership_map.toml"],
    )


def test_minimal_seed_manifest_requires_launch_firewalls_and_budgets() -> None:
    manifest = MinimalSeedManifest(
        manifest_id="layer2.s0.seed",
        facet_primitives=["construct", "instrument", "actor", "time_role"],
        instrument_modality_primitives=["cash_transfer", "credit_guarantee"],
        projection_primitives=["status", "limitation", "authority_boundary"],
        launch_firewalls=["P15", "P25"],
        budgets={
            "compute": "bounded",
            "acquisition": "bounded",
            "expert_time": "bounded",
            "human_attention": "bounded",
            "legal_access": "bounded",
        },
        principal_set_explore_exploit="principal_set_explicit_governed_balance",
        owned_by="team-policyos-runtime",
        rule_version_refs=["repo://docs/reference/policy-design-case-failure-patterns.md"],
    )

    assert manifest.schema_version == "policyos.policy_design_case.layer2_readiness.v1"


def test_minimal_seed_manifest_rejects_missing_p15_or_p25() -> None:
    with pytest.raises(ValidationError, match="launch_firewalls must include P15 and P25"):
        MinimalSeedManifest(
            manifest_id="layer2.s0.seed",
            facet_primitives=["construct"],
            instrument_modality_primitives=["cash_transfer"],
            projection_primitives=["status"],
            launch_firewalls=["P15"],
            budgets={"compute": "bounded"},
            principal_set_explore_exploit="principal_set_explicit_governed_balance",
            owned_by="team-policyos-runtime",
            rule_version_refs=["repo://docs/reference/policy-design-case-failure-patterns.md"],
        )


def test_design_record_v0_blocks_llm_candidate_from_governed_authority() -> None:
    with pytest.raises(ValidationError, match="llm_candidate cannot carry governed"):
        DesignRecordV0(
            record_id="design.record.ua_msme.001",
            candidate_ref="candidate.ua_msme.credit_guarantee.001",
            candidate_source="llm_candidate",
            projection_status="governed",
            authority_boundary=_authority_boundary(
                source_authority="llm_candidate",
                posture="shadow",
            ),
            axis_positions=[],
            firewall_status=[],
            envelope=CertifiedOperationEnvelope(
                envelope_id="envelope.ua_msme.shadow",
                domains=["ukrainian_msme_credit"],
                posture_scopes=["shadow"],
                epistemic_regime_scopes=[],
                actor_scopes=["public_credit_program_operator"],
                method_scopes=["design_record_schema_only"],
                certified_for=["shadow_replay"],
                not_certified_for=["publication_authority", "rollout_authority"],
                rule_version_ref="repo://architecture/policy_design_case/layer2_readiness_manifest.json",
            ),
            ledger_refs=[],
            projection_audiences=["MACHINE", "REVIEWER"],
        )


def test_axis_firewall_maturity_is_qualifier_not_ratchet_state() -> None:
    status = AxisFirewallStatus(
        cell_ref="ACTOR.state_capacity_feasibility",
        status="block",
        pattern_ids=["P21"],
        reason="No capacity feasibility producer is available yet.",
        maturity="fail_closed",
        rule_version_ref="repo://architecture/policy_design_case/cluster_ownership_map.toml",
    )

    assert status.maturity == "fail_closed"


def test_certified_operation_envelope_separates_posture_from_epistemic_regime() -> None:
    envelope = CertifiedOperationEnvelope(
        envelope_id="envelope.ua_msme.shadow",
        domains=["ukrainian_msme_credit"],
        posture_scopes=["shadow"],
        epistemic_regime_scopes=["ignorance"],
        actor_scopes=["public_credit_program_operator"],
        method_scopes=["design_record_schema_only"],
        certified_for=["shadow_replay"],
        not_certified_for=["publication_authority", "rollout_authority"],
        rule_version_ref="repo://architecture/policy_design_case/layer2_readiness_manifest.json",
    )

    assert envelope.posture_scopes == ["shadow"]
    assert envelope.epistemic_regime_scopes == ["ignorance"]

    with pytest.raises(ValidationError):
        CertifiedOperationEnvelope(
            envelope_id="envelope.ua_msme.bad",
            domains=["ukrainian_msme_credit"],
            posture_scopes=["shadow"],
            epistemic_regime_scopes=["shadow"],
            actor_scopes=["public_credit_program_operator"],
            method_scopes=["design_record_schema_only"],
            certified_for=["shadow_replay"],
            not_certified_for=["publication_authority", "rollout_authority"],
            rule_version_ref="repo://architecture/policy_design_case/layer2_readiness_manifest.json",
        )


def test_design_record_v0_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AuthorityBoundary(
            authoritative_for=["shadow_design_candidate"],
            may_not_use_for=["publication_authority"],
            source_authority="deterministic_producer",
            posture="shadow",
            rule_version_refs=["repo://architecture/policy_design_case/cluster_ownership_map.toml"],
            unexpected="not allowed",
        )
```

- [ ] **Step 2: Run the contract tests and verify they fail red**

Run:

```bash
cd policy-engine
uv run pytest tests/unit/pdc/test_layer2_readiness_contracts.py -q
```

Expected:

```text
ImportError: cannot import name 'DesignRecordV0' from 'polisyos.pdc'
```

- [ ] **Step 3: Implement the strict S0 contract module**

Create `src/polisyos/pdc/_impl/layer2_readiness.py`:

```python
"""Layer 2 S0 readiness contracts for the universal policy designer."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from polisyos.ir.kernel.base import ID_PATTERN, KernelModel

LAYER2_READINESS_SCHEMA_VERSION = "policyos.policy_design_case.layer2_readiness.v1"

Audience = Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]
AuthorityPosture = Literal["shadow", "advisory", "governed", "production"]
EpistemicRegime = Literal["risk", "uncertainty", "ambiguity", "ignorance", "contested_model"]
SourceAuthority = Literal[
    "deterministic_producer",
    "governed_config",
    "human_governance",
    "llm_candidate",
    "llm_critic",
    "llm_drafter",
]
FirewallDisposition = Literal["not_applicable", "pass", "warn", "limit", "block"]
CellMaturity = Literal["fail_closed", "predictive"]


class AuthorityBoundary(KernelModel):
    """Purpose-scoped authority boundary carried by Layer 2 records."""

    authoritative_for: list[str] = Field(..., min_length=1, max_length=20)
    may_not_use_for: list[str] = Field(..., min_length=1, max_length=20)
    source_authority: SourceAuthority
    posture: AuthorityPosture
    rule_version_refs: list[str] = Field(..., min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_llm_firewall(self) -> AuthorityBoundary:
        if self.source_authority.startswith("llm_") and self.posture != "shadow":
            raise ValueError(f"{self.source_authority} cannot carry {self.posture} authority")
        return self


class ValueOfInformationEstimate(KernelModel):
    """Shared value-of-information currency consumed by downstream slices."""

    estimate_id: str = Field(..., pattern=ID_PATTERN)
    purpose: str = Field(..., min_length=1, max_length=200)
    budget_dimensions: list[str] = Field(..., min_length=1, max_length=10)
    used_by_sites: list[str] = Field(..., min_length=1, max_length=20)
    owner: str = Field(..., min_length=1, max_length=100)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class GovernanceDecisionClass(KernelModel):
    """Registry entry for a governance decision class."""

    decision_class_id: str = Field(..., pattern=ID_PATTERN)
    label: str = Field(..., min_length=1, max_length=120)
    required_role: str = Field(..., min_length=1, max_length=120)
    default_posture: AuthorityPosture
    high_stakes: bool
    authority_boundary: AuthorityBoundary


class AxisPositionDeclaration(KernelModel):
    """A declared position on a universal designer cluster axis."""

    cluster: str = Field(..., min_length=1, max_length=80)
    axis: str = Field(..., min_length=1, max_length=120)
    position: str = Field(..., min_length=1, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=40)
    authority_purpose: str = Field(..., min_length=1, max_length=200)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)

    @property
    def cell_ref(self) -> str:
        """Return the `CLUSTER.axis` reference."""

        return f"{self.cluster}.{self.axis}"


class AxisFirewallStatus(KernelModel):
    """Fail-closed or predictive firewall status for one axis."""

    cell_ref: str = Field(..., min_length=3, max_length=200)
    status: FirewallDisposition
    pattern_ids: list[str] = Field(default_factory=list, max_length=10)
    reason: str = Field(..., min_length=1, max_length=500)
    maturity: CellMaturity | None = None
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class CertifiedOperationEnvelope(KernelModel):
    """Certified operation envelope attached to a design record."""

    envelope_id: str = Field(..., pattern=ID_PATTERN)
    domains: list[str] = Field(..., min_length=1, max_length=20)
    posture_scopes: list[AuthorityPosture] = Field(..., min_length=1, max_length=4)
    epistemic_regime_scopes: list[EpistemicRegime] = Field(default_factory=list, max_length=20)
    actor_scopes: list[str] = Field(..., min_length=1, max_length=20)
    method_scopes: list[str] = Field(..., min_length=1, max_length=20)
    certified_for: list[str] = Field(..., min_length=1, max_length=20)
    not_certified_for: list[str] = Field(..., min_length=1, max_length=20)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class DesignRecordV0(KernelModel):
    """Minimal narrow-waist design record carried from S2 onward."""

    schema_version: str = LAYER2_READINESS_SCHEMA_VERSION
    record_id: str = Field(..., pattern=ID_PATTERN)
    candidate_ref: str = Field(..., min_length=1, max_length=300)
    candidate_source: SourceAuthority
    projection_status: AuthorityPosture
    authority_boundary: AuthorityBoundary
    axis_positions: list[AxisPositionDeclaration] = Field(default_factory=list, max_length=40)
    firewall_status: list[AxisFirewallStatus] = Field(default_factory=list, max_length=40)
    envelope: CertifiedOperationEnvelope
    ledger_refs: list[str] = Field(default_factory=list, max_length=40)
    projection_audiences: list[Audience] = Field(..., min_length=1, max_length=4)

    @model_validator(mode="after")
    def _validate_v0_authority(self) -> DesignRecordV0:
        if self.candidate_source.startswith("llm_") and self.projection_status != "shadow":
            raise ValueError(f"{self.candidate_source} cannot carry {self.projection_status} authority")
        if self.projection_status == "production":
            raise ValueError("DesignRecordV0 cannot carry production authority")
        return self


class MinimalSeedManifest(KernelModel):
    """S0 manifest of algebra generators and launch budgets."""

    schema_version: str = LAYER2_READINESS_SCHEMA_VERSION
    manifest_id: str = Field(..., pattern=ID_PATTERN)
    facet_primitives: list[str] = Field(..., min_length=1, max_length=40)
    instrument_modality_primitives: list[str] = Field(..., min_length=1, max_length=40)
    projection_primitives: list[str] = Field(..., min_length=1, max_length=40)
    launch_firewalls: list[str] = Field(..., min_length=1, max_length=20)
    budgets: dict[str, str] = Field(..., min_length=1, max_length=20)
    principal_set_explore_exploit: str = Field(..., min_length=1, max_length=200)
    owned_by: str = Field(..., min_length=1, max_length=100)
    rule_version_refs: list[str] = Field(..., min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_launch_firewalls(self) -> MinimalSeedManifest:
        required = {"P15", "P25"}
        if not required <= set(self.launch_firewalls):
            raise ValueError("launch_firewalls must include P15 and P25")
        return self
```

- [ ] **Step 4: Export the new contract types through the public PDC facade**

Modify `src/polisyos/pdc/__init__.py`.

Add these names to the import from `._impl.layer2_readiness`:

```python
from ._impl.layer2_readiness import (
    AuthorityBoundary,
    AxisFirewallStatus,
    AxisPositionDeclaration,
    CertifiedOperationEnvelope,
    DesignRecordV0,
    GovernanceDecisionClass,
    MinimalSeedManifest,
    ValueOfInformationEstimate,
)
```

Add the same names to `__all__`:

```python
    "AuthorityBoundary",
    "AxisFirewallStatus",
    "AxisPositionDeclaration",
    "CertifiedOperationEnvelope",
    "DesignRecordV0",
    "GovernanceDecisionClass",
    "MinimalSeedManifest",
    "ValueOfInformationEstimate",
```

Update `src/polisyos/pdc/README.md` by changing the purpose section to mention the
Layer 2 narrow waist:

```markdown
- Purpose: compile the runtime-owned `RuntimePolicyDesignCase` graph from claim registry, semantic binding, producer pipeline, closeout, contested, deficit, and projection-bound refs; own the neutral Layer 2 `DesignRecordV0` narrow-waist contracts consumed by Scientist, Runtime, and later A-side grounding.
```

- [ ] **Step 5: Run the unit tests and verify they pass**

Run:

```bash
cd policy-engine
uv run pytest tests/unit/pdc/test_layer2_readiness_contracts.py -q
```

Expected:

```text
6 passed
```

- [ ] **Step 6: Commit Task 1**

Run:

```bash
cd policy-engine
git add src/polisyos/pdc/_impl/layer2_readiness.py \
  src/polisyos/pdc/__init__.py \
  src/polisyos/pdc/README.md \
  tests/unit/pdc/test_layer2_readiness_contracts.py
git commit -m "feat: add layer2 s0 readiness contracts"
```

## Task 2: Governed S0 Architecture Artifacts

**Files:**

- Create: `architecture/policy_design_case/layer2_minimal_seed_manifest.json`
- Create: `architecture/policy_design_case/layer2_dependency_dag.json`
- Create: `architecture/policy_design_case/layer2_slice_cell_matrix.toml`
- Create: `architecture/policy_design_case/layer2_floor_governance.toml`
- Create: `architecture/policy_design_case/layer2_artifact_traceability.toml`
- Create: `architecture/policy_design_case/layer2_corpus_partition.json`
- Create: `architecture/policy_design_case/layer2_first_proving_case.json`
- Create: `architecture/policy_design_case/layer2_readiness_manifest.json`

- [ ] **Step 1: Write the S0 artifact files**

Create `architecture/policy_design_case/layer2_minimal_seed_manifest.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_readiness.v1",
  "manifest_id": "layer2.s0.seed",
  "status": "frozen_for_s2_start",
  "owner": "team-policyos-runtime",
  "facet_primitives": [
    "construct",
    "actor",
    "jurisdiction",
    "population_scope",
    "time_role",
    "evidence_status",
    "value_dimension",
    "capacity_dimension",
    "response_dimension"
  ],
  "instrument_modality_primitives": [
    "credit_guarantee",
    "grant",
    "cash_transfer",
    "tax_relief",
    "procurement_preference",
    "technical_assistance",
    "regulatory_forbearance",
    "information_disclosure"
  ],
  "projection_primitives": [
    "status",
    "limitation",
    "blocker",
    "authority_boundary",
    "uncertainty",
    "trace_ref",
    "audience",
    "redaction_depth"
  ],
  "launch_firewalls": [
    "P03",
    "P04",
    "P05",
    "P10",
    "P13",
    "P15",
    "P25"
  ],
  "budgets": {
    "compute": "bounded_per_search_run",
    "acquisition": "voi_ranked",
    "expert_time": "decision_class_gated",
    "human_attention": "voi_ranked_interruptions_only",
    "legal_access": "rights_checked_before_acquisition"
  },
  "principal_set_explore_exploit": "principal_set_explicit_governed_balance",
  "rule_version_refs": [
    "repo://architecture/policy_design_case/cluster_ownership_map.toml",
    "repo://docs/reference/policy-design-case-failure-patterns.md"
  ]
}
```

Create `architecture/policy_design_case/layer2_dependency_dag.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_dependency_dag.v1",
  "status": "active",
  "owner": "team-policyos-runtime",
  "critical_path": ["S0", "S2", "S3", "S4", "S5", "S6", "S7"],
  "nodes": {
    "S0": {"label": "readiness_narrow_waist", "prerequisites": []},
    "S1": {"label": "graded_outcomes_a_side", "prerequisites": []},
    "S2": {"label": "grammar_candidate_search_design_record_v0", "prerequisites": ["S0"]},
    "S3": {"label": "substrate_acquisition_ua_msme", "prerequisites": ["S0", "S2"]},
    "S4": {"label": "epistemic_regime", "prerequisites": ["S3"]},
    "S5": {"label": "coupling_composition", "prerequisites": ["S4"]},
    "S6": {"label": "fail_closed_blind_spots", "prerequisites": ["S5"]},
    "S7": {"label": "delegation", "prerequisites": ["S2", "S6"]},
    "S8": {"label": "normative_firewall_value_choice", "prerequisites": ["S7"]},
    "S9": {"label": "design_record_projection", "prerequisites": ["S2", "S5", "S8"]},
    "S10": {"label": "outcome_prediction", "prerequisites": ["S5", "S6", "S8"]},
    "S11": {"label": "rich_blind_spot_models", "prerequisites": ["S6", "S10"]},
    "S12": {"label": "cold_start_resource_economics", "prerequisites": ["S3", "S7"]},
    "S13": {"label": "post_deploy_accountability", "prerequisites": ["S7", "S9", "S12"]},
    "S14": {"label": "universality_battery", "prerequisites": ["S1", "S2", "S3", "S4", "S5", "S6"]}
  }
}
```

Create `architecture/policy_design_case/layer2_slice_cell_matrix.toml`:

```toml
schema_version = "policyos.policy_design_case.layer2_slice_cell_matrix.v1"
status = "active"
owner = "team-policyos-runtime"
cluster_ownership_map = "architecture/policy_design_case/cluster_ownership_map.toml"
open_cell_count_baseline = 17
s0_cells_closed = []

[[assignment]]
cell_ref = "INTERVENTION.design_grammar"
slice = "S2"
target_state = "implemented"
layer = "design_search_control_plane"

[[assignment]]
cell_ref = "INTERVENTION.design_candidate"
slice = "S2"
target_state = "implemented"
layer = "design_search_control_plane"

[[assignment]]
cell_ref = "KNOWLEDGE.epistemic_regime"
slice = "S4"
target_state = "implemented"
layer = "epistemic_regime"

[[assignment]]
cell_ref = "INTERVENTION.reversibility_lifecycle_stakes"
slice = "S4"
target_state = "implemented"
layer = "epistemic_regime"

[[assignment]]
cell_ref = "SYSTEM.connectivity_modularity"
slice = "S5"
target_state = "implemented"
layer = "coupling_composition"

[[assignment]]
cell_ref = "SYSTEM.dynamics_feedback"
slice = "S5"
target_state = "implemented"
layer = "coupling_composition"

[[assignment]]
cell_ref = "INTERVENTION.scale_composition"
slice = "S5"
target_state = "implemented"
layer = "coupling_composition"

[[assignment]]
cell_ref = "OTHER_AGENTS.strategic_response"
slice = "S6"
target_state = "implemented"
maturity = "fail_closed"
layer = "blind_spot_firewalls"

[[assignment]]
cell_ref = "ACTOR.state_capacity_feasibility"
slice = "S6"
target_state = "implemented"
maturity = "fail_closed"
layer = "blind_spot_firewalls"

[[assignment]]
cell_ref = "ACTOR.mandate_legitimacy"
slice = "S6"
target_state = "implemented"
maturity = "fail_closed"
layer = "blind_spot_firewalls"

[[assignment]]
cell_ref = "SYSTEM.measurability"
slice = "S6"
target_state = "implemented"
maturity = "fail_closed"
layer = "blind_spot_firewalls"

[[assignment]]
cell_ref = "SYSTEM.subject_granularity"
slice = "S6"
target_state = "implemented"
maturity = "fail_closed"
layer = "blind_spot_firewalls"

[[assignment]]
cell_ref = "ACTOR.value_choice_provenance"
slice = "S8"
target_state = "implemented"
layer = "normative_firewall"

[[assignment]]
cell_ref = "KNOWLEDGE.calibration"
slice = "S11"
target_state = "implemented"
layer = "rich_knowledge_producers"

[[assignment]]
cell_ref = "KNOWLEDGE.ir_proof_carrying_analytics"
slice = "S11"
target_state = "implemented"
layer = "rich_knowledge_producers"

[[assignment]]
cell_ref = "CROSS_CUTTING.scientist_orchestration"
slice = "S2"
target_state = "implemented"
layer = "generation_handoff"

[[assignment]]
cell_ref = "DESIGNER_ITSELF.envelope_growth"
slice = "S12"
target_state = "implemented"
layer = "resource_economics_and_envelope_growth"

[[maturity_transition]]
cell_ref = "OTHER_AGENTS.strategic_response"
from_maturity = "fail_closed"
to_maturity = "predictive"
slice = "S11"

[[maturity_transition]]
cell_ref = "ACTOR.state_capacity_feasibility"
from_maturity = "fail_closed"
to_maturity = "predictive"
slice = "S11"

[[maturity_transition]]
cell_ref = "SYSTEM.measurability"
from_maturity = "fail_closed"
to_maturity = "predictive"
slice = "S11"

[[maturity_transition]]
cell_ref = "SYSTEM.subject_granularity"
from_maturity = "fail_closed"
to_maturity = "predictive"
slice = "S11"
```

Create `architecture/policy_design_case/layer2_floor_governance.toml`:

```toml
schema_version = "policyos.policy_design_case.layer2_floor_governance.v1"
status = "active"
owner = "team-policyos-runtime"

[[floor]]
floor_id = "s2_counterexample_conversion"
slice = "S2"
metric = "counterexample_conversion_rate"
floor_owner = "team-runtime-quality"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "governance_pr_required_for_floor_or_denominator_change"

[[floor]]
floor_id = "s3_acquisition_closure"
slice = "S3"
metric = "acquisition_closure_rate"
floor_owner = "team-integration-spine"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "source_contract_and_rerun_closure_required"

[[floor]]
floor_id = "s4_regime_accuracy"
slice = "S4"
metric = "regime_accuracy_with_asymmetric_false_risk_penalty"
floor_owner = "team-policy-design-research"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "expert_label_change_requires_recorded_adjudication"

[[floor]]
floor_id = "s5_coupling_accuracy"
slice = "S5"
metric = "coupling_accuracy_with_false_modular_penalty"
floor_owner = "team-runtime-quality"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "negative_control_cannot_be_removed_without_replacement"

[[floor]]
floor_id = "s6_fail_closed_coverage"
slice = "S6"
metric = "per_axis_fail_closed_negative_control_pass_rate"
floor_owner = "team-runtime-quality"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "all_five_blind_spot_axes_required"

[[floor]]
floor_id = "s7_delegation_integrity"
slice = "S7"
metric = "delegation_precision_recall_and_responsibility_integrity"
floor_owner = "governance-board"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "decision_rights_matrix_change_requires_governance_owner"

[[floor]]
floor_id = "s8_value_provenance"
slice = "S8"
metric = "value_provenance_completeness"
floor_owner = "governance-board"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "ranked_recommendations_require_authorized_value_source"

[[floor]]
floor_id = "s9_projection_faithfulness"
slice = "S9"
metric = "projection_faithfulness_pass_rate"
floor_owner = "team-runtime-quality"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "faithfulness_negative_controls_required"

[[floor]]
floor_id = "s10_calibration"
slice = "S10"
metric = "observable_subset_calibration"
floor_owner = "team-research"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "forecast_support_tier_change_requires_calibration_record"

[[floor]]
floor_id = "s11_axis_calibration"
slice = "S11"
metric = "per_axis_predictive_calibration"
floor_owner = "team-research"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "model_relaxation_requires_calibration_before_relaxation"

[[floor]]
floor_id = "s12_growth_thermometers"
slice = "S12"
metric = "reuse_rate_and_override_rate_trend"
floor_owner = "principal-governance"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "growth_counting_requires_envelope_delta"

[[floor]]
floor_id = "s13_accountability"
slice = "S13"
metric = "a_before_b_ratio_and_attribution_resolution"
floor_owner = "governance-board"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "post_deploy_learning_requires_attribution_gate"

[[floor]]
floor_id = "s14_universality"
slice = "S14"
metric = "per_axis_posture_thresholds_and_breadth_floor"
floor_owner = "governance-board"
floor_artifact = "architecture/policy_design_case/layer2_floor_governance.toml"
revision_rule = "sealed_battery_change_requires_freeze_hash_rotation"
```

Create `architecture/policy_design_case/layer2_artifact_traceability.toml`:

```toml
schema_version = "policyos.policy_design_case.layer2_artifact_traceability.v1"
status = "active"
owner = "team-policyos-runtime"

[[artifact]]
name = "MinimalSeedManifest"
slice = "S0"
maturity = "frozen_for_s2_start"

[[artifact]]
name = "ValueOfInformationEstimate"
slice = "S0"
maturity = "skeleton_contract"

[[artifact]]
name = "GovernanceDecisionClass"
slice = "S0"
maturity = "skeleton_contract"

[[artifact]]
name = "AxisPositionDeclaration"
slice = "S0"
maturity = "skeleton_contract"

[[artifact]]
name = "AxisFirewallStatus"
slice = "S0"
maturity = "skeleton_contract"

[[artifact]]
name = "CertifiedOperationEnvelope"
slice = "S0"
maturity = "skeleton_contract"

[[artifact]]
name = "DesignRecord"
slice = "S0"
maturity = "v0_schema"

[[artifact]]
name = "DesignGrammarExpansion"
slice = "S2"
maturity = "planned"

[[artifact]]
name = "ConstraintStoreSnapshot"
slice = "S2"
maturity = "planned"

[[artifact]]
name = "CounterexampleRecord"
slice = "S2"
maturity = "planned"

[[artifact]]
name = "RefinementDecision"
slice = "S2"
maturity = "planned"

[[artifact]]
name = "SearchLedger"
slice = "S2"
maturity = "planned"

[[artifact]]
name = "ClusterInterfaceContract"
slice = "S2"
maturity = "planned"

[[artifact]]
name = "ClusterHandoffRecord"
slice = "S2"
maturity = "planned"

[[artifact]]
name = "FacetPrimitiveRegistry"
slice = "S3"
maturity = "planned"

[[artifact]]
name = "ConstructExpression"
slice = "S3"
maturity = "planned"

[[artifact]]
name = "ConstructDemandLedger"
slice = "S3"
maturity = "planned"

[[artifact]]
name = "ConstructOntologyDelta"
slice = "S3"
maturity = "planned"

[[artifact]]
name = "CapabilityBindingResult"
slice = "S3"
maturity = "planned"

[[artifact]]
name = "SubstrateCoverageSnapshot"
slice = "S3"
maturity = "planned"

[[artifact]]
name = "AcquisitionTaskRecord"
slice = "S3"
maturity = "planned"

[[artifact]]
name = "SourceContract"
slice = "S3"
maturity = "planned"

[[artifact]]
name = "RerunClosureReceipt"
slice = "S3"
maturity = "planned"

[[artifact]]
name = "HonestAbstentionReceipt"
slice = "S3"
maturity = "planned"

[[artifact]]
name = "EpistemicRegimeClaim"
slice = "S4"
maturity = "planned"

[[artifact]]
name = "CommitmentProfileRecord"
slice = "S4"
maturity = "planned"

[[artifact]]
name = "CouplingGraph"
slice = "S5"
maturity = "planned"

[[artifact]]
name = "CouplingRegimeClassification"
slice = "S5"
maturity = "planned"

[[artifact]]
name = "DecompositionResult"
slice = "S5"
maturity = "planned"

[[artifact]]
name = "RecursiveDesignGraph"
slice = "S5"
maturity = "planned"

[[artifact]]
name = "DesignInterfaceContract"
slice = "S5"
maturity = "planned"

[[artifact]]
name = "SystemDynamicsRequirement"
slice = "S5"
maturity = "planned"

[[artifact]]
name = "CompositionReceipt"
slice = "S5"
maturity = "planned"

[[artifact]]
name = "ComputationalTractabilityBudget"
slice = "S5"
maturity = "planned"

[[artifact]]
name = "CapacityFeasibilityRecord"
slice = "S6"
maturity = "planned_fail_closed"

[[artifact]]
name = "MandateLegitimacyRecord"
slice = "S6"
maturity = "planned_fail_closed"

[[artifact]]
name = "MeasurabilityAdequacyRecord"
slice = "S6"
maturity = "planned_fail_closed"

[[artifact]]
name = "AggregationValidityRecord"
slice = "S6"
maturity = "planned_fail_closed"

[[artifact]]
name = "StrategicResponseRecord"
slice = "S6"
maturity = "planned_fail_closed"

[[artifact]]
name = "ClusterAuthorityDimensionRecord"
slice = "S6"
maturity = "planned_fail_closed"

[[artifact]]
name = "DelegationContract"
slice = "S7"
maturity = "planned"

[[artifact]]
name = "DecisionRightsMatrix"
slice = "S7"
maturity = "planned"

[[artifact]]
name = "HumanDecisionRequest"
slice = "S7"
maturity = "planned"

[[artifact]]
name = "HumanDecisionRecord"
slice = "S7"
maturity = "planned"

[[artifact]]
name = "ParetoArchive"
slice = "S8"
maturity = "planned"

[[artifact]]
name = "ForecastSupport"
slice = "S10"
maturity = "planned"

[[artifact]]
name = "ForecastCalibrationRecord"
slice = "S10"
maturity = "planned"

[[artifact]]
name = "ProofCarryingAnalyticsRecord"
slice = "S11"
maturity = "planned"

[[artifact]]
name = "KnowledgeGovernanceThroughputLedger"
slice = "S12"
maturity = "planned"

[[artifact]]
name = "DeploymentDossier"
slice = "S13"
maturity = "planned"

[[artifact]]
name = "DivergenceRecord"
slice = "S13"
maturity = "planned"

[[artifact]]
name = "LearningUpdateProposal"
slice = "S13"
maturity = "planned"

[[artifact]]
name = "EnvelopeRevision"
slice = "S13"
maturity = "planned"

[[artifact]]
name = "CertifiedEnvelopeDelta"
slice = "S13"
maturity = "planned"

[[artifact]]
name = "AssuranceCaseDelta"
slice = "S13"
maturity = "planned"
```

Create `architecture/policy_design_case/layer2_corpus_partition.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_corpus_partition.v1",
  "status": "active",
  "owner": "team-policyos-runtime",
  "dev_regression_corpus": {
    "path": "tests/fixtures/universal-corpus/cases",
    "extensible": true,
    "access": "development_visible"
  },
  "sealed_universality_battery": {
    "path": "tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery",
    "extensible": false,
    "access": "ci_gate_only",
    "freeze_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "owner": "governance-board"
  },
  "integrity_rule": "development code and fixtures must not read the sealed battery path"
}
```

Create `architecture/policy_design_case/layer2_first_proving_case.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_first_proving_case.v1",
  "status": "active",
  "owner": "team-policyos-runtime",
  "case_id": "ukrainian_msme_credit_constructs",
  "jurisdiction": "ukraine",
  "policy_area": "msme_credit_support",
  "constructs": [
    "credit_program_enrollment",
    "firm_survival",
    "regional_displacement_pressure",
    "credit_access",
    "fiscal_burden_per_beneficiary"
  ],
  "first_slice_using_case": "S3",
  "purpose": "Repair the real W12 construct-observation failure mode rather than demonstrating a convenient case.",
  "authority_boundary": "proving_case_only_not_publication_authority"
}
```

Create `architecture/policy_design_case/layer2_readiness_manifest.json`:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_readiness_manifest.v1",
  "status": "active",
  "owner": "team-policyos-runtime",
  "slice": "S0",
  "cells_closed": [],
  "open_cell_count_baseline": 17,
  "artifacts": [
    "architecture/policy_design_case/layer2_minimal_seed_manifest.json",
    "architecture/policy_design_case/layer2_dependency_dag.json",
    "architecture/policy_design_case/layer2_slice_cell_matrix.toml",
    "architecture/policy_design_case/layer2_floor_governance.toml",
    "architecture/policy_design_case/layer2_artifact_traceability.toml",
    "architecture/policy_design_case/layer2_corpus_partition.json",
    "architecture/policy_design_case/layer2_first_proving_case.json"
  ],
  "validators": [
    "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
    "tools/quality/validation/check_policy_design_case_cluster_ownership_map.py"
  ],
  "readiness_items": [
    "MinimalSeedManifest",
    "DesignRecordV0 schema",
    "Dependency DAG",
    "Slice to open-cell matrix",
    "Floor governance table",
    "Artifact traceability table",
    "Corpus partition",
    "First proving case",
    "Shared cross-cutting contract skeletons",
    "Cell maturity qualifier",
    "Cell vs layer and full cell coverage"
  ]
}
```

- [ ] **Step 2: Commit Task 2**

Run:

```bash
cd policy-engine
git add architecture/policy_design_case/layer2_minimal_seed_manifest.json \
  architecture/policy_design_case/layer2_dependency_dag.json \
  architecture/policy_design_case/layer2_slice_cell_matrix.toml \
  architecture/policy_design_case/layer2_floor_governance.toml \
  architecture/policy_design_case/layer2_artifact_traceability.toml \
  architecture/policy_design_case/layer2_corpus_partition.json \
  architecture/policy_design_case/layer2_first_proving_case.json \
  architecture/policy_design_case/layer2_readiness_manifest.json
git commit -m "chore: add layer2 s0 readiness artifacts"
```

## Task 3: Red-First S0 Readiness Validator

**Files:**

- Create: `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- Create: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`

- [ ] **Step 1: Write failing repo-quality tests for S0 readiness**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`:

```python
from __future__ import annotations

import copy
from pathlib import Path

from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]


def _issue_codes(validation: dict[str, object]) -> set[str]:
    return {str(issue["code"]) for issue in validation["issues"]}  # type: ignore[index]


def test_layer2_s0_readiness_manifest_is_valid() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["open_cell_count"] == 17  # type: ignore[index]
    assert validation["summary"]["assigned_open_cell_count"] == 17  # type: ignore[index]
    assert validation["summary"]["s0_cells_closed"] == []  # type: ignore[index]


def test_layer2_slice_cell_matrix_covers_every_open_cell() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    cluster_map = payloads["cluster_map"]
    open_cells = readiness._open_cell_refs(cluster_map)  # type: ignore[attr-defined]
    assigned = {
        str(entry["cell_ref"])
        for entry in payloads["slice_cell_matrix"].get("assignment", [])
    }

    assert open_cells == assigned


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
    assert "layer2_slice_cell_matrix_open_cell_mismatch" in _issue_codes(validation)


def test_layer2_readiness_rejects_maturity_as_ratchet_state() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["slice_cell_matrix"]["assignment"][0]["target_state"] = "fail_closed"

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_slice_cell_matrix_unknown_ratchet_state" in _issue_codes(validation)


def test_layer2_readiness_rejects_unsealed_corpus_partition() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["corpus_partition"]["sealed_universality_battery"]["path"] = (
        payloads["corpus_partition"]["dev_regression_corpus"]["path"]
    )

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_corpus_partition_not_sealed" in _issue_codes(validation)


def test_layer2_readiness_rejects_missing_required_artifact_trace() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["artifact_traceability"]["artifact"] = [
        row
        for row in payloads["artifact_traceability"]["artifact"]
        if row["name"] != "CertifiedEnvelopeDelta"
    ]

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_artifact_traceability_missing_required_artifact" in _issue_codes(validation)


def test_layer2_readiness_rejects_incomplete_ua_msme_proving_case() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["first_proving_case"]["constructs"].remove("fiscal_burden_per_beneficiary")

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_first_proving_case_missing_construct" in _issue_codes(validation)
```

- [ ] **Step 2: Run the validator tests and verify they fail red**

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
```

Expected:

```text
ModuleNotFoundError: cannot import name 'check_policy_design_case_layer2_readiness'
```

- [ ] **Step 3: Implement the S0 readiness validator**

Create `tools/quality/validation/check_policy_design_case_layer2_readiness.py`:

```python
#!/usr/bin/env python3
"""Validate the Layer 2 S0 readiness bundle."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

DEFAULT_READINESS_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_readiness_manifest.json"
)
DEFAULT_MINIMAL_SEED_PATH = Path(
    "architecture/policy_design_case/layer2_minimal_seed_manifest.json"
)
DEFAULT_DEPENDENCY_DAG_PATH = Path("architecture/policy_design_case/layer2_dependency_dag.json")
DEFAULT_SLICE_CELL_MATRIX_PATH = Path(
    "architecture/policy_design_case/layer2_slice_cell_matrix.toml"
)
DEFAULT_FLOOR_GOVERNANCE_PATH = Path(
    "architecture/policy_design_case/layer2_floor_governance.toml"
)
DEFAULT_ARTIFACT_TRACEABILITY_PATH = Path(
    "architecture/policy_design_case/layer2_artifact_traceability.toml"
)
DEFAULT_CORPUS_PARTITION_PATH = Path(
    "architecture/policy_design_case/layer2_corpus_partition.json"
)
DEFAULT_FIRST_PROVING_CASE_PATH = Path(
    "architecture/policy_design_case/layer2_first_proving_case.json"
)

REQUIRED_SLICES = {f"S{number}" for number in range(15)}
REQUIRED_UA_MSME_CONSTRUCTS = {
    "credit_program_enrollment",
    "firm_survival",
    "regional_displacement_pressure",
    "credit_access",
    "fiscal_burden_per_beneficiary",
}
REQUIRED_ARTIFACT_NAMES = {
    "MinimalSeedManifest",
    "ValueOfInformationEstimate",
    "GovernanceDecisionClass",
    "AxisPositionDeclaration",
    "AxisFirewallStatus",
    "CertifiedOperationEnvelope",
    "DesignRecord",
    "ClusterInterfaceContract",
    "ClusterHandoffRecord",
    "ConstructOntologyDelta",
    "CapabilityBindingResult",
    "CommitmentProfileRecord",
    "ClusterAuthorityDimensionRecord",
    "ForecastCalibrationRecord",
    "ProofCarryingAnalyticsRecord",
    "CertifiedEnvelopeDelta",
}
MATURITY_QUALIFIERS = {"fail_closed", "predictive"}


def load_layer2_readiness_payloads(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Load all governed S0 readiness payloads."""

    root = Path(repo_root)
    return {
        "readiness_manifest": _load_json(root / DEFAULT_READINESS_MANIFEST_PATH),
        "minimal_seed": _load_json(root / DEFAULT_MINIMAL_SEED_PATH),
        "dependency_dag": _load_json(root / DEFAULT_DEPENDENCY_DAG_PATH),
        "slice_cell_matrix": _load_toml(root / DEFAULT_SLICE_CELL_MATRIX_PATH),
        "floor_governance": _load_toml(root / DEFAULT_FLOOR_GOVERNANCE_PATH),
        "artifact_traceability": _load_toml(root / DEFAULT_ARTIFACT_TRACEABILITY_PATH),
        "corpus_partition": _load_json(root / DEFAULT_CORPUS_PARTITION_PATH),
        "first_proving_case": _load_json(root / DEFAULT_FIRST_PROVING_CASE_PATH),
        "cluster_map": cluster_map.load_cluster_ownership_map(root),
    }


def validate_layer2_readiness(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Validate S0 readiness from files in the repository."""

    root = Path(repo_root)
    missing = [
        path.as_posix()
        for path in (
            DEFAULT_READINESS_MANIFEST_PATH,
            DEFAULT_MINIMAL_SEED_PATH,
            DEFAULT_DEPENDENCY_DAG_PATH,
            DEFAULT_SLICE_CELL_MATRIX_PATH,
            DEFAULT_FLOOR_GOVERNANCE_PATH,
            DEFAULT_ARTIFACT_TRACEABILITY_PATH,
            DEFAULT_CORPUS_PARTITION_PATH,
            DEFAULT_FIRST_PROVING_CASE_PATH,
        )
        if not (root / path).exists()
    ]
    if missing:
        return _result(
            [
                {
                    "code": "layer2_readiness_artifact_missing",
                    "message": "Missing S0 readiness artifacts: " + ", ".join(missing),
                }
            ],
            summary={},
        )
    return validate_layer2_readiness_payloads(load_layer2_readiness_payloads(root))


def validate_layer2_readiness_payloads(payloads: dict[str, Any]) -> dict[str, Any]:
    """Validate already-loaded S0 readiness payloads."""

    issues: list[dict[str, str]] = []
    cluster_payload = payloads["cluster_map"]
    open_cells = _open_cell_refs(cluster_payload)
    ratchet_states = set(cluster_payload.get("ratchet_state_vocabulary", []))

    matrix = payloads["slice_cell_matrix"]
    assignments = list(matrix.get("assignment", []))
    assigned_cells = {str(entry.get("cell_ref", "")) for entry in assignments}
    if assigned_cells != open_cells:
        issues.append(
            _issue(
                "layer2_slice_cell_matrix_open_cell_mismatch",
                "Slice-cell matrix must assign exactly the open cluster cells.",
            )
        )

    for entry in assignments:
        target_state = str(entry.get("target_state", ""))
        if target_state not in ratchet_states:
            issues.append(
                _issue(
                    "layer2_slice_cell_matrix_unknown_ratchet_state",
                    f"Unknown ratchet target_state={target_state}.",
                )
            )
        if target_state in MATURITY_QUALIFIERS:
            issues.append(
                _issue(
                    "layer2_slice_cell_matrix_maturity_used_as_state",
                    f"Maturity qualifier used as ratchet state: {target_state}.",
                )
            )
        maturity = entry.get("maturity")
        if maturity is not None and str(maturity) not in MATURITY_QUALIFIERS:
            issues.append(
                _issue(
                    "layer2_slice_cell_matrix_unknown_maturity",
                    f"Unknown maturity qualifier: {maturity}.",
                )
            )

    s0_cells_closed = list(matrix.get("s0_cells_closed", []))
    if s0_cells_closed:
        issues.append(
            _issue(
                "layer2_s0_must_not_close_cells",
                "S0 readiness cannot close cluster cells.",
            )
        )

    dag_nodes = set(payloads["dependency_dag"].get("nodes", {}))
    if dag_nodes != REQUIRED_SLICES:
        issues.append(
            _issue(
                "layer2_dependency_dag_slice_set_invalid",
                "Dependency DAG must declare S0 through S14 exactly.",
            )
        )
    if "S0" not in payloads["dependency_dag"]["nodes"]["S2"].get("prerequisites", []):
        issues.append(
            _issue(
                "layer2_dependency_dag_s2_missing_s0",
                "S2 must depend on S0.",
            )
        )

    _validate_minimal_seed(payloads["minimal_seed"], issues)
    _validate_floors(payloads["floor_governance"], issues)
    _validate_artifact_traceability(payloads["artifact_traceability"], issues)
    _validate_corpus_partition(payloads["corpus_partition"], issues)
    _validate_first_proving_case(payloads["first_proving_case"], issues)
    _validate_readiness_manifest(payloads["readiness_manifest"], issues)

    return _result(
        issues,
        summary={
            "open_cell_count": len(open_cells),
            "assigned_open_cell_count": len(assigned_cells),
            "s0_cells_closed": s0_cells_closed,
            "readiness_artifact_count": len(payloads["readiness_manifest"].get("artifacts", [])),
        },
    )


def _open_cell_refs(payload: dict[str, Any]) -> set[str]:
    return {
        f"{cluster}.{axis}"
        for cluster, axes in payload.get("open_cell_closure", {}).items()
        for axis in axes
    }


def _validate_minimal_seed(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if not {"P15", "P25"} <= set(payload.get("launch_firewalls", [])):
        issues.append(
            _issue(
                "layer2_minimal_seed_missing_launch_firewall",
                "Minimal seed manifest must include P15 and P25 launch firewalls.",
            )
        )
    required_budgets = {"compute", "acquisition", "expert_time", "human_attention", "legal_access"}
    if not required_budgets <= set(payload.get("budgets", {})):
        issues.append(
            _issue(
                "layer2_minimal_seed_missing_budget",
                "Minimal seed manifest must declare all launch budgets.",
            )
        )


def _validate_floors(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    floors = payload.get("floor", [])
    floor_slices = {str(floor.get("slice", "")) for floor in floors}
    required_floor_slices = {f"S{number}" for number in range(2, 15)}
    if not required_floor_slices <= floor_slices:
        issues.append(
            _issue(
                "layer2_floor_governance_missing_slice_floor",
                "Floor governance must cover S2 through S14.",
            )
        )
    for floor in floors:
        for field in ("metric", "floor_owner", "floor_artifact", "revision_rule"):
            if not floor.get(field):
                issues.append(
                    _issue(
                        "layer2_floor_governance_field_missing",
                        f"Floor {floor.get('floor_id')} omits {field}.",
                    )
                )


def _validate_artifact_traceability(
    payload: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    names = {str(row.get("name", "")) for row in payload.get("artifact", [])}
    missing = REQUIRED_ARTIFACT_NAMES - names
    if missing:
        issues.append(
            _issue(
                "layer2_artifact_traceability_missing_required_artifact",
                "Artifact traceability omits: " + ", ".join(sorted(missing)),
            )
        )


def _validate_corpus_partition(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    dev = payload.get("dev_regression_corpus", {})
    sealed = payload.get("sealed_universality_battery", {})
    if dev.get("path") == sealed.get("path") or sealed.get("extensible") is not False:
        issues.append(
            _issue(
                "layer2_corpus_partition_not_sealed",
                "Sealed universality battery must be distinct and non-extensible.",
            )
        )
    if not str(sealed.get("freeze_hash", "")).startswith("sha256:"):
        issues.append(
            _issue(
                "layer2_corpus_partition_freeze_hash_missing",
                "Sealed universality battery must carry a freeze hash.",
            )
        )


def _validate_first_proving_case(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    constructs = set(payload.get("constructs", []))
    missing = REQUIRED_UA_MSME_CONSTRUCTS - constructs
    if missing:
        issues.append(
            _issue(
                "layer2_first_proving_case_missing_construct",
                "First proving case omits constructs: " + ", ".join(sorted(missing)),
            )
        )


def _validate_readiness_manifest(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if payload.get("cells_closed") != []:
        issues.append(
            _issue(
                "layer2_readiness_manifest_closes_cells",
                "S0 readiness manifest must not claim closed cells.",
            )
        )
    if int(payload.get("open_cell_count_baseline", -1)) != 17:
        issues.append(
            _issue(
                "layer2_readiness_manifest_open_cell_count_invalid",
                "S0 readiness manifest must preserve open_cell_count_baseline=17.",
            )
        )
    if len(payload.get("readiness_items", [])) != 11:
        issues.append(
            _issue(
                "layer2_readiness_manifest_item_count_invalid",
                "S0 readiness manifest must carry the 11 roadmap readiness items.",
            )
        )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _result(issues: list[dict[str, str]], *, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the Layer 2 readiness validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--json-output", default="")
    args = parser.parse_args(argv)

    result = validate_layer2_readiness(args.repo_root)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.json_output:
        Path(args.json_output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the validator tests and verify they pass**

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
```

Expected:

```text
7 passed
```

- [ ] **Step 5: Run the validator CLI**

Run:

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
```

Expected:

```json
{
  "issues": [],
  "status": "pass",
  "summary": {
    "assigned_open_cell_count": 17,
    "open_cell_count": 17,
    "readiness_artifact_count": 7,
    "s0_cells_closed": []
  }
}
```

- [ ] **Step 6: Commit Task 3**

Run:

```bash
cd policy-engine
git add tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py
git commit -m "test: validate layer2 s0 readiness gate"
```

## Task 4: Inventory Wiring

**Files:**

- Modify: `architecture/policy_design_case/inventory.json`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- Modify: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`

- [ ] **Step 1: Add a failing inventory assertion**

Append this test to `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`:

```python
def test_layer2_readiness_artifacts_are_in_policy_design_case_inventory() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["inventory_artifact_count"] >= 8  # type: ignore[index]
```

- [ ] **Step 2: Run the inventory assertion and verify it fails**

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py::test_layer2_readiness_artifacts_are_in_policy_design_case_inventory -q
```

Expected:

```text
KeyError: 'inventory_artifact_count'
```

- [ ] **Step 3: Add the Layer 2 artifacts to inventory**

Modify `architecture/policy_design_case/inventory.json` by appending these objects to the `artifacts` array:

```json
{
  "id": "layer2_readiness_manifest",
  "path": "architecture/policy_design_case/layer2_readiness_manifest.json",
  "kind": "layer2_readiness_manifest",
  "owner": "team-policyos-runtime",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "authority_boundary": "readiness_gate_only_no_cell_closure",
  "status": "active"
},
{
  "id": "layer2_minimal_seed_manifest",
  "path": "architecture/policy_design_case/layer2_minimal_seed_manifest.json",
  "kind": "layer2_seed_manifest",
  "owner": "team-policyos-runtime",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "authority_boundary": "readiness_gate_only_no_cell_closure",
  "status": "active"
},
{
  "id": "layer2_dependency_dag",
  "path": "architecture/policy_design_case/layer2_dependency_dag.json",
  "kind": "layer2_dependency_dag",
  "owner": "team-policyos-runtime",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "authority_boundary": "execution_sequence_signal_only",
  "status": "active"
},
{
  "id": "layer2_slice_cell_matrix",
  "path": "architecture/policy_design_case/layer2_slice_cell_matrix.toml",
  "kind": "layer2_slice_cell_matrix",
  "owner": "team-policyos-runtime",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "authority_boundary": "cluster_cell_planning_signal_only",
  "status": "active"
},
{
  "id": "layer2_floor_governance",
  "path": "architecture/policy_design_case/layer2_floor_governance.toml",
  "kind": "layer2_floor_governance",
  "owner": "team-policyos-runtime",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "authority_boundary": "floor_governance_reference_only",
  "status": "active"
},
{
  "id": "layer2_artifact_traceability",
  "path": "architecture/policy_design_case/layer2_artifact_traceability.toml",
  "kind": "layer2_artifact_traceability",
  "owner": "team-policyos-runtime",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "authority_boundary": "architecture_traceability_only",
  "status": "active"
},
{
  "id": "layer2_corpus_partition",
  "path": "architecture/policy_design_case/layer2_corpus_partition.json",
  "kind": "layer2_corpus_partition",
  "owner": "team-policyos-runtime",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "authority_boundary": "evaluation_integrity_gate_only",
  "status": "active"
},
{
  "id": "layer2_first_proving_case",
  "path": "architecture/policy_design_case/layer2_first_proving_case.json",
  "kind": "layer2_first_proving_case",
  "owner": "team-policyos-runtime",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "authority_boundary": "proving_case_only_not_publication_authority",
  "status": "active"
}
```

- [ ] **Step 4: Extend the validator summary with inventory coverage**

Modify `tools/quality/validation/check_policy_design_case_layer2_readiness.py`:

1. Add this constant near the other path constants:

```python
DEFAULT_INVENTORY_PATH = Path("architecture/policy_design_case/inventory.json")
```

2. Load inventory in `load_layer2_readiness_payloads`:

```python
        "inventory": _load_json(root / DEFAULT_INVENTORY_PATH),
```

3. Add this helper:

```python
def _inventory_layer2_artifact_count(payload: dict[str, Any]) -> int:
    return sum(
        1
        for artifact in payload.get("artifacts", [])
        if str(artifact.get("id", "")).startswith("layer2_")
    )
```

4. Add this field to the `summary` object returned by `validate_layer2_readiness_payloads`:

```python
            "inventory_artifact_count": _inventory_layer2_artifact_count(payloads["inventory"]),
```

- [ ] **Step 5: Run the inventory test and verify it passes**

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py::test_layer2_readiness_artifacts_are_in_policy_design_case_inventory -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Commit Task 4**

Run:

```bash
cd policy-engine
git add architecture/policy_design_case/inventory.json \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py
git commit -m "chore: register layer2 s0 readiness artifacts"
```

## Task 5: Full S0 Verification

**Files:**

- No new files.

- [ ] **Step 1: Run the S0 contract tests**

Run:

```bash
cd policy-engine
uv run pytest tests/unit/pdc/test_layer2_readiness_contracts.py -q
```

Expected:

```text
6 passed
```

- [ ] **Step 2: Run the S0 readiness tests**

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
```

Expected:

```text
8 passed
```

- [ ] **Step 3: Run the existing cluster ownership tests**

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py -q
```

Expected:

```text
19 passed
```

- [ ] **Step 4: Run both validator CLIs**

Run:

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
```

Expected:

```text
Both commands exit 0. The Layer 2 readiness output has status "pass", open_cell_count 17, assigned_open_cell_count 17, and s0_cells_closed [].
```

- [ ] **Step 5: Run architecture guardrails**

Run:

```bash
cd policy-engine
uv run polisyos-tools architecture guardrails check
```

Expected:

```text
Architecture guardrails pass with no new import or public-surface violations.
```

- [ ] **Step 6: Commit verification fixes if any were needed**

Run only if Steps 1 through 5 required changes:

```bash
cd policy-engine
git add src/polisyos/pdc/_impl/layer2_readiness.py \
  src/polisyos/pdc/__init__.py \
  src/polisyos/pdc/README.md \
  architecture/policy_design_case \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py
git commit -m "fix: close layer2 s0 readiness verification gaps"
```

## Task 6: Closeout Notes For The Implementer

**Files:**

- No new files.

- [ ] **Step 1: Record the cell-state delta in the PR summary**

Use this exact delta:

```text
S0 cell delta: no cells closed.
Baseline preserved: open_cell_count=17.
New readiness gate: layer2_readiness status=pass.
Missing labels retired by S0: artifact_missing for S0 governed artifacts, verification_missing for S0 readiness validation, semantic_test_missing for S0 authority/maturity/corpus negative controls.
Remaining labels intentionally carried to downstream slices: open-cell labels in cluster_ownership_map.toml.
```

- [ ] **Step 2: Record the pattern pass in the PR summary**

Use this exact pattern pass:

```text
Pattern pass: P01/P03/P04/P05/P07/P10/P13/P15/P25 checked.
S0 prevents contract-only Layer 2 by pairing shared contracts with governed artifacts and validator coverage.
Maturity qualifiers fail_closed/predictive are validated as qualifiers, not ratchet states.
LLM-origin design records remain shadow-only in DesignRecordV0.
S0 does not close cells or claim B-side runtime authority.
```

- [ ] **Step 3: Confirm S2 is unblocked only after S0 validation passes**

Run:

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
```

Expected:

```text
Exit code 0 and status "pass".
```

## Final Acceptance Criteria

1. `src/polisyos/pdc/_impl/layer2_readiness.py` defines strict shared S0 contracts and blocks LLM candidate authority laundering.
2. `DesignRecordV0` is exported through `polisyos.pdc`.
3. All S0 governed artifacts exist under `architecture/policy_design_case/`.
4. `layer2_slice_cell_matrix.toml` assigns exactly all 17 open cells and closes none in S0.
5. Maturity qualifiers `fail_closed` and `predictive` are accepted only as qualifiers, never as ratchet states.
6. Artifact traceability includes the easily missed contracts: `ClusterInterfaceContract`, `ClusterAuthorityDimensionRecord`, `CapabilityBindingResult`, `ConstructOntologyDelta`, `CommitmentProfileRecord`, `CertifiedEnvelopeDelta`, `ForecastCalibrationRecord`, and `ProofCarryingAnalyticsRecord`.
7. Corpus partition has distinct dev and sealed paths plus a sealed freeze hash.
8. First proving case includes all five Ukrainian MSME constructs.
9. The S0 validator CLI returns `status=pass`.
10. Existing cluster ownership validation still reports 17 open cells.

## Verification Commands

Run:

```bash
cd policy-engine
uv run pytest tests/unit/pdc/test_layer2_readiness_contracts.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run polisyos-tools architecture guardrails check
```

Expected:

```text
Layer 2 readiness tests pass.
Cluster ownership tests pass.
Layer 2 readiness validator exits 0 with status "pass".
Cluster ownership validator exits 0 with status "pass".
Architecture guardrails pass.
```
