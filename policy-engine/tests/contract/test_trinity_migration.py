"""
Contract tests for Trinity migration.

Tests ensure:
1. Zero data loss during migration
2. Idempotent transformations
3. Round-trip correctness
4. Schema compliance
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.ir.kernel.time_semantics import TimeSemantics
from polisyos.ir.loaders import load_policy, load_trinity
from polisyos.ir.migrations.trinity_migration import (
    is_trinity_migrated,
    merge_to_surface_ir,
    split_surface_ir,
    split_to_bundle,
)
from polisyos.ir.surface import (
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


class TestSplitSurfaceIR:
    """Tests for split_surface_ir function."""

    def test_split_minimal_ir(self, minimal_legacy_ir: PolicySurfaceIR) -> None:
        """Minimal IR can be split without errors."""
        pf, ps, ms = split_surface_ir(minimal_legacy_ir)

        assert pf.schema_version == "1.0"
        assert ps.schema_version == "1.0"
        assert ms.schema_version == "1.0"
        assert ms.data_snapshot_ref == ZERO_REF
        assert ms.registry_bundle_ref == ONE_REF

    def test_split_preserves_objectives(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Objectives are moved to ProblemFrame.kpis."""
        pf, _, _ = split_surface_ir(full_legacy_ir)

        assert len(pf.kpis) == 2
        assert pf.kpis[0].objective_id == "reduce_poverty"
        assert pf.kpis[1].objective_id == "budget_balance"

    def test_split_preserves_interventions(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Interventions are moved to PolicySpec."""
        _, ps, _ = split_surface_ir(full_legacy_ir)

        assert len(ps.interventions) == 1
        assert ps.interventions[0].intervention_id == "ubi_program"

    def test_split_preserves_constraints(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Constraints are moved to ProblemFrame."""
        pf, _, _ = split_surface_ir(full_legacy_ir)

        assert len(pf.constraints) == 1
        assert pf.constraints[0].constraint_id == "budget_cap"

    def test_split_preserves_actors(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Advisory entities become actors in ProblemFrame."""
        pf, _, _ = split_surface_ir(full_legacy_ir)

        assert len(pf.actors) == 2
        assert pf.actors[0].entity_id == "government"

    def test_split_partitions_labels(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Labels are correctly partitioned by prefix."""
        pf, ps, ms = split_surface_ir(full_legacy_ir)

        assert "goal:poverty_reduction" in pf.success_criteria_tags
        assert "policy:transfer_program" in ps.policy_labels
        assert "model:abm_simulation" in ms.model_labels
        assert "unclassified_tag" in pf.general_labels

    def test_split_partitions_notes(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Notes are correctly partitioned by prefix."""
        _, ps, ms = split_surface_ir(full_legacy_ir)

        assert any("Phase 1" in note for note in ps.implementation_notes)
        assert any("2023 population" in note for note in ms.model_notes)

    def test_split_preserves_time_semantics(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """TimeSemantics is moved to ModelSpec."""
        _, _, ms = split_surface_ir(full_legacy_ir)

        assert ms.time_semantics is not None
        assert ms.time_semantics.frequency == TimeFrequency.MONTH
        assert ms.time_semantics.step_count == 120

    def test_split_sets_source_reference(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Source reference is set in metadata for traceability."""
        pf, ps, ms = split_surface_ir(full_legacy_ir)

        assert pf.metadata.source_ir_ref is not None
        assert pf.metadata.source_ir_ref.startswith("sha256:")
        assert pf.metadata.source_ir_ref == ps.metadata.source_ir_ref
        assert ps.metadata.source_ir_ref == ms.metadata.source_ir_ref


class TestMergeToSurfaceIR:
    """Tests for merge_to_surface_ir function."""

    def test_merge_produces_valid_ir(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Merged result is a valid PolicySurfaceIR."""
        pf, ps, ms = split_surface_ir(full_legacy_ir)
        merged = merge_to_surface_ir(pf, ps, ms)

        assert isinstance(merged, PolicySurfaceIR)
        assert merged.schema_version == "2.0"

    def test_merge_preserves_interventions(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Interventions survive round-trip."""
        pf, ps, ms = split_surface_ir(full_legacy_ir)
        merged = merge_to_surface_ir(pf, ps, ms)

        assert len(merged.semantic.interventions) == 1
        assert merged.semantic.interventions[0].intervention_id == "ubi_program"

    def test_merge_preserves_objectives(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Objectives survive round-trip."""
        pf, ps, ms = split_surface_ir(full_legacy_ir)
        merged = merge_to_surface_ir(pf, ps, ms)

        assert len(merged.semantic.objectives) == 2


class TestRoundTrip:
    """Tests for complete round-trip migrations."""

    def test_roundtrip_semantic_fingerprint(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Semantic fingerprint is preserved through round-trip."""
        original_fingerprint = full_legacy_ir.semantic_fingerprint_payload()

        pf, ps, ms = split_surface_ir(full_legacy_ir)
        merged = merge_to_surface_ir(pf, ps, ms)
        merged_fingerprint = merged.semantic_fingerprint_payload()

        assert original_fingerprint == merged_fingerprint

    def test_roundtrip_minimal(self, minimal_legacy_ir: PolicySurfaceIR) -> None:
        """Minimal IR survives round-trip."""
        pf, ps, ms = split_surface_ir(minimal_legacy_ir)
        merged = merge_to_surface_ir(pf, ps, ms)

        assert (
            merged.semantic.context_snapshot_ref
            == minimal_legacy_ir.semantic.context_snapshot_ref
        )
        assert (
            merged.semantic.registry_bundle_ref
            == minimal_legacy_ir.semantic.registry_bundle_ref
        )

    def test_roundtrip_preserves_all_fields(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """All semantic fields are preserved through round-trip."""
        pf, ps, ms = split_surface_ir(full_legacy_ir)
        merged = merge_to_surface_ir(pf, ps, ms)

        assert len(merged.semantic.objectives) == len(full_legacy_ir.semantic.objectives)
        assert len(merged.semantic.interventions) == len(full_legacy_ir.semantic.interventions)
        assert len(merged.semantic.constraints) == len(full_legacy_ir.semantic.constraints)

        assert merged.semantic.context_snapshot_ref == full_legacy_ir.semantic.context_snapshot_ref
        assert merged.semantic.registry_bundle_ref == full_legacy_ir.semantic.registry_bundle_ref


class TestIdempotency:
    """Tests for migration idempotency."""

    def test_split_twice_same_result(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Splitting the same IR twice produces identical results."""
        pf1, ps1, ms1 = split_surface_ir(full_legacy_ir)
        pf2, ps2, ms2 = split_surface_ir(full_legacy_ir)

        assert pf1.model_dump() == pf2.model_dump()
        assert ps1.model_dump() == ps2.model_dump()
        assert ms1.model_dump() == ms2.model_dump()

    def test_already_migrated_detection(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """is_trinity_migrated correctly identifies formats."""
        legacy_dict = full_legacy_ir.model_dump()
        assert not is_trinity_migrated(legacy_dict)

        bundle = split_to_bundle(full_legacy_ir)
        trinity_dict = bundle.model_dump()
        assert is_trinity_migrated(trinity_dict)

    def test_double_roundtrip(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Double round-trip produces same result."""
        pf1, ps1, ms1 = split_surface_ir(full_legacy_ir)
        merged1 = merge_to_surface_ir(pf1, ps1, ms1)

        pf2, ps2, ms2 = split_surface_ir(merged1)
        merged2 = merge_to_surface_ir(pf2, ps2, ms2)

        fp1 = merged1.semantic_fingerprint_payload()
        fp2 = merged2.semantic_fingerprint_payload()
        assert fp1 == fp2


class TestLoaderIntegration:
    """Tests for loader integration."""

    def test_load_legacy_as_trinity(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """load_policy with as_trinity=True returns TrinityBundle."""
        legacy_dict = full_legacy_ir.model_dump()
        result = load_policy(legacy_dict, as_trinity=True)

        assert isinstance(result, TrinityBundle)
        assert len(result.policy_spec.interventions) == 1

    def test_load_trinity_as_legacy(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """load_policy can load Trinity and return legacy format."""
        bundle = split_to_bundle(full_legacy_ir)
        trinity_dict = bundle.model_dump()

        result = load_policy(trinity_dict, as_trinity=False)

        assert isinstance(result, PolicySurfaceIR)
        assert result.schema_version == "2.0"

    def test_load_trinity_convenience(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """load_trinity always returns TrinityBundle."""
        legacy_dict = full_legacy_ir.model_dump()
        result = load_trinity(legacy_dict)

        assert isinstance(result, TrinityBundle)

    def test_load_preserves_type(self, full_legacy_ir: PolicySurfaceIR) -> None:
        """Loading typed objects returns them unchanged."""
        result_ir = load_policy(full_legacy_ir, as_trinity=False)
        assert result_ir is full_legacy_ir

        bundle = split_to_bundle(full_legacy_ir)
        result_bundle = load_policy(bundle, as_trinity=True)
        assert result_bundle is bundle


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_advisory(self, minimal_legacy_ir: PolicySurfaceIR) -> None:
        """IR with no advisory section migrates correctly."""
        assert minimal_legacy_ir.advisory is None
        pf, _, _ = split_surface_ir(minimal_legacy_ir)

        assert pf.actors == []
        assert pf.problem_statement is None

    def test_empty_lists_preserved(self, minimal_legacy_ir: PolicySurfaceIR) -> None:
        """Empty lists are preserved, not converted to None."""
        pf, ps, _ = split_surface_ir(minimal_legacy_ir)

        assert pf.kpis == []
        assert ps.interventions == []
        assert pf.constraints == []

    def test_invalid_payload_raises(self) -> None:
        """Invalid payload raises appropriate error."""
        with pytest.raises(ValueError):
            load_policy({"invalid": "data"})

        with pytest.raises(TypeError):
            load_policy("not a dict")
