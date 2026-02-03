"""
Contract tests for Trinity migration (Phase 2 canonical contract).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.ir.kernel.time_semantics import TimeSemantics
from polisyos.ir.legacy.migrations.surface_to_trinity import (
    migrate_surface_ir_to_trinity,
    migrate_trinity_bundle_v0_to_trinity,
    migrate_trinity_to_surface_ir,
)
from polisyos.ir.legacy.surface import (
    AdvisoryEntity,
    ConstraintSpec,
    InterventionSpec,
    ObjectiveSpec,
    PolicyAdvisory,
    PolicySemantic,
    PolicySurfaceIR,
    ScheduleSpec,
    SelectorPredicate,
)
from polisyos.ir.legacy.trinity_v0 import (
    ModelSpec as LegacyModelSpec,
    PolicySpec as LegacyPolicySpec,
    ProblemFrame as LegacyProblemFrame,
    TrinityBundle as LegacyTrinityBundle,
)
from polisyos.ir.loaders import PolicyLoadError, load_policy, load_trinity
from polisyos.ir.problem_frame import ConstraintType, ProblemDomain
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import EntityType, OptimizationDirection, SelectorOperator, TimeFrequency

ZERO_REF = "sha256:" + "0" * 64
ONE_REF = "sha256:" + "1" * 64


@pytest.fixture
def minimal_legacy_ir() -> PolicySurfaceIR:
    """Minimal valid PolicySurfaceIR for testing."""
    return PolicySurfaceIR(
        schema_version="2.0",
        semantic=PolicySemantic(
            context_snapshot_ref=ZERO_REF,
            registry_bundle_ref=ONE_REF,
        ),
    )


@pytest.fixture
def full_legacy_ir() -> PolicySurfaceIR:
    """Fully populated PolicySurfaceIR for testing."""
    return PolicySurfaceIR(
        schema_version="2.0",
        semantic=PolicySemantic(
            context_snapshot_ref=ZERO_REF,
            registry_bundle_ref=ONE_REF,
            time_semantics=TimeSemantics(
                frequency=TimeFrequency.MONTH,
                start_date="2024-01-01",
                step_count=120,
            ),
            objectives=[
                ObjectiveSpec(
                    objective_id="reduce_poverty",
                    metric_id="poverty_rate",
                    direction=OptimizationDirection.MINIMIZE,
                    weight=Decimal("1.0"),
                ),
                ObjectiveSpec(
                    objective_id="budget_balance",
                    metric_id="deficit_gdp_ratio",
                    direction=OptimizationDirection.MINIMIZE,
                    weight=Decimal("0.5"),
                ),
            ],
            interventions=[
                InterventionSpec(
                    intervention_id="ubi_program",
                    kind="transfer",
                    target=SelectorPredicate(
                        field="income_quintile",
                        operator=SelectorOperator.LESS_EQUAL,
                        value=2,
                    ),
                    schedule=ScheduleSpec(start_step=0, end_step=120),
                    params={"amount": 1000, "frequency": "monthly"},
                ),
            ],
            constraints=[
                ConstraintSpec(
                    constraint_id="budget_cap",
                    value="deficit_gdp_ratio <= 0.03",
                ),
            ],
            notes=[
                "[policy] Phase 1 implementation note",
                "[model] Assumes 2023 population data",
                "General note without prefix",
            ],
        ),
        advisory=PolicyAdvisory(
            entities=[
                AdvisoryEntity(
                    entity_id="government",
                    entity_type=EntityType.AGENT,
                    attributes={"budget_authority": True},
                ),
                AdvisoryEntity(
                    entity_id="households",
                    entity_type=EntityType.AGENT,
                ),
            ],
            narrative="Universal Basic Income pilot to reduce poverty",
            labels=[
                "goal:poverty_reduction",
                "policy:transfer_program",
                "model:abm_simulation",
                "unclassified_tag",
            ],
            notes=["Advisory note for context"],
        ),
    )


class TestSurfaceToTrinity:
    def test_migrate_minimal_ir(self, minimal_legacy_ir: PolicySurfaceIR) -> None:
        bundle, report = migrate_surface_ir_to_trinity(minimal_legacy_ir)

        assert isinstance(bundle, TrinityBundle)
        assert bundle.schema_version == "1.0"
        assert bundle.problem_frame.problem_id.startswith("pf_")
        assert bundle.policy_spec.policy_id.startswith("ps_")
        assert bundle.model_spec.model_id.startswith("ms_")
        assert bundle.problem_frame.domain == ProblemDomain.CUSTOM
        assert report.source_ref.startswith("sha256:")

    def test_migrate_preserves_fields(self, full_legacy_ir: PolicySurfaceIR) -> None:
        bundle, _ = migrate_surface_ir_to_trinity(full_legacy_ir)

        assert len(bundle.policy_spec.interventions) == 1
        assert bundle.policy_spec.interventions[0].intervention_id == "ubi_program"

        assert len(bundle.problem_frame.hard_constraints) == 1
        assert bundle.problem_frame.hard_constraints[0].constraint_id == "budget_cap"
        assert bundle.problem_frame.hard_constraints[0].constraint_type == ConstraintType.HARD

        assert len(bundle.problem_frame.stakeholders) == 2
        assert bundle.problem_frame.stakeholders[0].stakeholder_id == "government"

        assert bundle.model_spec.time_semantics is not None
        assert bundle.model_spec.time_semantics.frequency == TimeFrequency.MONTH

    def test_partitions_labels_and_notes(self, full_legacy_ir: PolicySurfaceIR) -> None:
        bundle, _ = migrate_surface_ir_to_trinity(full_legacy_ir)

        assert "goal:poverty_reduction" in bundle.problem_frame.labels
        assert "unclassified_tag" in bundle.problem_frame.labels
        assert "policy:transfer_program" in bundle.policy_spec.labels
        assert "model:abm_simulation" in bundle.model_spec.labels

        assert any("Phase 1" in note for note in bundle.policy_spec.notes)
        assert any("General note" in note for note in bundle.policy_spec.notes)
        assert any("2023 population" in note for note in bundle.model_spec.notes)
        assert any("Advisory" in note for note in bundle.problem_frame.notes)


class TestTrinityToSurface:
    def test_merge_to_surface_roundtrip(self, full_legacy_ir: PolicySurfaceIR) -> None:
        bundle, _ = migrate_surface_ir_to_trinity(full_legacy_ir)
        merged, _ = migrate_trinity_to_surface_ir(bundle)

        assert isinstance(merged, PolicySurfaceIR)
        assert merged.schema_version == "2.0"
        assert merged.semantic.context_snapshot_ref == full_legacy_ir.semantic.context_snapshot_ref
        assert merged.semantic.registry_bundle_ref == full_legacy_ir.semantic.registry_bundle_ref

    def test_roundtrip_semantic_fingerprint(self, full_legacy_ir: PolicySurfaceIR) -> None:
        bundle, _ = migrate_surface_ir_to_trinity(full_legacy_ir)
        merged, _ = migrate_trinity_to_surface_ir(bundle)

        assert merged.semantic_fingerprint_payload() == full_legacy_ir.semantic_fingerprint_payload()


class TestLegacyTrinityBundle:
    def test_migrate_legacy_bundle(self) -> None:
        legacy_bundle = LegacyTrinityBundle(
            problem_frame=LegacyProblemFrame(),
            policy_spec=LegacyPolicySpec(),
            model_spec=LegacyModelSpec(data_snapshot_ref=ZERO_REF),
        )

        bundle, report = migrate_trinity_bundle_v0_to_trinity(legacy_bundle)
        assert bundle.schema_version == "1.0"
        assert report.source_format == "legacy_trinity_bundle_v0"


class TestLoaderIntegration:
    def test_load_legacy_as_trinity(self, full_legacy_ir: PolicySurfaceIR) -> None:
        legacy_dict = full_legacy_ir.model_dump()
        result = load_policy(legacy_dict, as_trinity=True)

        assert isinstance(result, TrinityBundle)
        assert len(result.policy_spec.interventions) == 1

    def test_load_trinity_as_legacy(self, full_legacy_ir: PolicySurfaceIR) -> None:
        bundle, _ = migrate_surface_ir_to_trinity(full_legacy_ir)
        trinity_dict = bundle.model_dump()

        result = load_policy(trinity_dict, as_trinity=False)
        assert isinstance(result, PolicySurfaceIR)
        assert result.schema_version == "2.0"

    def test_load_trinity_convenience(self, full_legacy_ir: PolicySurfaceIR) -> None:
        legacy_dict = full_legacy_ir.model_dump()
        result = load_trinity(legacy_dict)

        assert isinstance(result, TrinityBundle)

    def test_load_policy_auto_migrate_toggle(self, full_legacy_ir: PolicySurfaceIR) -> None:
        legacy_dict = full_legacy_ir.model_dump()
        with pytest.raises(PolicyLoadError):
            load_policy(legacy_dict, as_trinity=True, auto_migrate=False)

        bundle, _ = migrate_surface_ir_to_trinity(full_legacy_ir)
        trinity_dict = bundle.model_dump()
        with pytest.raises(PolicyLoadError):
            load_policy(trinity_dict, as_trinity=False, auto_migrate=False)

    def test_invalid_payload_raises(self) -> None:
        with pytest.raises(PolicyLoadError):
            load_policy({"invalid": "data"})

        with pytest.raises(PolicyLoadError):
            load_policy("not a dict")
