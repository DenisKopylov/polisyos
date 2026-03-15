"""
Contract tests for the Trinity artifacts: ProblemFrame, PolicySpec, ModelSpec.

Tests roundtrip serialization, validation, and cross-reference consistency.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
import yaml
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.trinity import (
    ModelSpecRef,
    PolicySpecRef,
    ProblemFrameRef,
    TrinityBundle,
)
from polisyos.ir.model_spec import (
    AgentConfig,
    AgentTypeConfig,
    AssumptionSpec,
    AssumptionType,
    FidelityLevel,
    ModelSpec,
)
from polisyos.ir.governance.policy_spec import (
    InterventionSpec,
    MechanismBinding,
    PolicySpec,
)
from polisyos.ir.trinity import TrinityBundle as IRTrinityBundle
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    ConstraintType,
    KPISpec,
    NormativeArbitrationPolicy,
    NormativeFrame,
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
    StakeholderOutcomeBinding,
    StakeholderRightSpec,
    StakeholderSpec,
    StakeholderUtilityTerm,
    SuccessCriterion,
)
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorNot, SelectorPredicate
from polisyos.ir.types import EntityType, OptimizationDirection


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_problem_frame() -> ProblemFrame:
    """Minimal valid ProblemFrame."""
    return ProblemFrame(
        problem_id="test_problem",
        domain=ProblemDomain.FISCAL,
        objectives=[
            ObjectiveSpec(
                objective_id="obj_1",
                metric_id="gdp_growth",
                direction=OptimizationDirection.MAXIMIZE,
            )
        ],
    )


@pytest.fixture
def minimal_policy_spec() -> PolicySpec:
    """Minimal valid PolicySpec."""
    return PolicySpec(
        policy_id="test_policy",
        interventions=[
            InterventionSpec(
                intervention_id="int_1",
                kind="income_tax",
                target=SelectorPredicate(
                    kind="predicate",
                    field="income",
                    operator=">",
                    value=Decimal("10000"),
                ),
                schedule=ScheduleSpec(start_step=0, duration_steps=12),
                params={"rate": Decimal("0.15")},
            )
        ],
    )


@pytest.fixture
def minimal_model_spec() -> ModelSpec:
    """Minimal valid ModelSpec."""
    return ModelSpec(
        model_id="test_model",
        data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        fidelity_level=FidelityLevel.HYBRID,
    )


# =============================================================================
# ProblemFrame Tests
# =============================================================================


class TestProblemFrame:
    """Tests for ProblemFrame schema."""

    def test_minimal_valid(self, minimal_problem_frame: ProblemFrame) -> None:
        """Test minimal valid ProblemFrame."""
        assert minimal_problem_frame.problem_id == "test_problem"
        assert minimal_problem_frame.domain == ProblemDomain.FISCAL
        assert minimal_problem_frame.schema_version == "1.0"

    def test_roundtrip_yaml(self, minimal_problem_frame: ProblemFrame) -> None:
        """Test YAML roundtrip serialization."""
        yaml_str = yaml.dump(minimal_problem_frame.model_dump(mode="json"))
        loaded = yaml.safe_load(yaml_str)
        restored = ProblemFrame.model_validate(loaded)
        assert restored == minimal_problem_frame

    def test_roundtrip_json(self, minimal_problem_frame: ProblemFrame) -> None:
        """Test JSON roundtrip serialization."""
        json_str = minimal_problem_frame.model_dump_json()
        restored = ProblemFrame.model_validate_json(json_str)
        assert restored == minimal_problem_frame

    def test_rejects_duplicate_objective_ids(self) -> None:
        """Test rejection of duplicate objective IDs."""
        with pytest.raises(ValidationError) as exc_info:
            ProblemFrame(
                problem_id="test",
                domain=ProblemDomain.FISCAL,
                objectives=[
                    ObjectiveSpec(
                        objective_id="dup",
                        metric_id="m1",
                        direction=OptimizationDirection.MAXIMIZE,
                    ),
                    ObjectiveSpec(
                        objective_id="dup",  # Duplicate!
                        metric_id="m2",
                        direction=OptimizationDirection.MINIMIZE,
                    ),
                ],
            )
        assert "duplicate objective_id" in str(exc_info.value)

    def test_rejects_invalid_kpi_reference(self) -> None:
        """Test rejection of invalid KPI reference in success criteria."""
        with pytest.raises(ValidationError) as exc_info:
            ProblemFrame(
                problem_id="test",
                domain=ProblemDomain.FISCAL,
                kpis=[
                    KPISpec(
                        kpi_id="kpi_1",
                        metric_id="metric_1",
                        direction=OptimizationDirection.MAXIMIZE,
                    )
                ],
                success_criteria=[
                    SuccessCriterion(
                        criterion_id="crit_1",
                        kpi_id="nonexistent_kpi",  # Invalid reference!
                        operator=">=",
                        threshold=Decimal("100"),
                    )
                ],
            )
        assert "unknown KPI" in str(exc_info.value)

    def test_rejects_invalid_problem_id_pattern(self) -> None:
        """Test rejection of invalid problem_id pattern."""
        with pytest.raises(ValidationError):
            ProblemFrame(
                problem_id="Invalid-ID",  # Hyphens not allowed
                domain=ProblemDomain.FISCAL,
            )

    def test_hard_constraints_must_be_hard(self) -> None:
        """Test that hard_constraints list only accepts HARD type."""
        with pytest.raises(ValidationError) as exc_info:
            ProblemFrame(
                problem_id="test",
                domain=ProblemDomain.FISCAL,
                hard_constraints=[
                    ConstraintSpec(
                        constraint_id="c1",
                        constraint_type=ConstraintType.SOFT,  # Wrong type!
                        value=100,
                    )
                ],
            )
        assert "must have constraint_type=HARD" in str(exc_info.value)

    def test_normative_frame_validates_existing_refs(self) -> None:
        frame = ProblemFrame(
            problem_id="test",
            domain=ProblemDomain.FISCAL,
            stakeholders=[
                StakeholderSpec(
                    stakeholder_id="workers",
                    entity_type=EntityType.AGENT,
                )
            ],
            hard_constraints=[
                ConstraintSpec(
                    constraint_id="budget_cap",
                    constraint_type=ConstraintType.HARD,
                    slot_id="fiscal_cost",
                    operator="<=",
                    value=100,
                )
            ],
            normative_frame=NormativeFrame(
                default_policy=NormativeArbitrationPolicy.WEIGHTED_WELFARE,
                enabled_policies=[
                    NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
                    NormativeArbitrationPolicy.WEIGHTED_WELFARE,
                ],
                stakeholder_bindings=[
                    StakeholderOutcomeBinding(
                        binding_id="workers_income",
                        stakeholder_id="workers",
                        channel="distributional_net_impact",
                        outcome_key="workers",
                    )
                ],
                utility_terms=[
                    StakeholderUtilityTerm(
                        term_id="workers_welfare",
                        stakeholder_id="workers",
                        binding_refs=["workers_income"],
                    )
                ],
                rights_catalog=[
                    StakeholderRightSpec(
                        right_id="workers_non_loss",
                        stakeholder_id="workers",
                        binding_ref="workers_income",
                        operator=">=",
                        threshold=0,
                    )
                ],
                hard_constraint_refs=["budget_cap"],
            ),
        )

        assert frame.normative_frame is not None
        assert frame.normative_frame.default_policy == NormativeArbitrationPolicy.WEIGHTED_WELFARE

    def test_normative_frame_rejects_unknown_stakeholder_ref(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ProblemFrame(
                problem_id="test",
                domain=ProblemDomain.FISCAL,
                normative_frame=NormativeFrame(
                    stakeholder_bindings=[
                        StakeholderOutcomeBinding(
                            binding_id="missing_binding",
                            stakeholder_id="missing",
                            channel="distributional_net_impact",
                            outcome_key="missing",
                        )
                    ]
                ),
            )
        assert "unknown stakeholder" in str(exc_info.value)

    def test_normative_frame_rejects_duplicate_binding_ids(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ProblemFrame(
                problem_id="test",
                domain=ProblemDomain.FISCAL,
                stakeholders=[
                    StakeholderSpec(
                        stakeholder_id="workers",
                        entity_type=EntityType.AGENT,
                    )
                ],
                normative_frame=NormativeFrame(
                    stakeholder_bindings=[
                        StakeholderOutcomeBinding(
                            binding_id="dup_binding",
                            stakeholder_id="workers",
                            channel="distributional_net_impact",
                            outcome_key="workers",
                        ),
                        StakeholderOutcomeBinding(
                            binding_id="dup_binding",
                            stakeholder_id="workers",
                            channel="distributional_net_impact",
                            outcome_key="workers_alt",
                        ),
                    ]
                ),
            )
        assert "duplicate binding_id" in str(exc_info.value)


# =============================================================================
# PolicySpec Tests
# =============================================================================


class TestPolicySpec:
    """Tests for PolicySpec schema."""

    def test_minimal_valid(self, minimal_policy_spec: PolicySpec) -> None:
        """Test minimal valid PolicySpec."""
        assert minimal_policy_spec.policy_id == "test_policy"
        assert len(minimal_policy_spec.interventions) == 1

    def test_roundtrip_yaml(self, minimal_policy_spec: PolicySpec) -> None:
        """Test YAML roundtrip serialization."""
        yaml_str = yaml.dump(minimal_policy_spec.model_dump(mode="json"))
        loaded = yaml.safe_load(yaml_str)
        restored = PolicySpec.model_validate(loaded)
        assert restored.model_dump(mode="json") == minimal_policy_spec.model_dump(mode="json")

    def test_rejects_duplicate_intervention_ids(self) -> None:
        """Test rejection of duplicate intervention IDs."""
        with pytest.raises(ValidationError) as exc_info:
            PolicySpec(
                policy_id="test",
                interventions=[
                    InterventionSpec(
                        intervention_id="dup",
                        kind="income_tax",
                        target=SelectorPredicate(
                            kind="predicate", field="id", operator="==", value="all"
                        ),
                        schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    ),
                    InterventionSpec(
                        intervention_id="dup",  # Duplicate!
                        kind="subsidy",
                        target=SelectorPredicate(
                            kind="predicate", field="id", operator="==", value="all"
                        ),
                        schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    ),
                ],
            )
        assert "duplicate intervention_id" in str(exc_info.value)

    def test_rejects_invalid_mechanism_binding_reference(self) -> None:
        """Test rejection of invalid intervention reference in mechanism binding."""
        with pytest.raises(ValidationError) as exc_info:
            PolicySpec(
                policy_id="test",
                interventions=[
                    InterventionSpec(
                        intervention_id="int_1",
                        kind="income_tax",
                        target=SelectorPredicate(
                            kind="predicate", field="id", operator="==", value="all"
                        ),
                        schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    )
                ],
                mechanism_bindings=[
                    MechanismBinding(
                        binding_id="bind_1",
                        mechanism_id="income_tax",
                        intervention_ids=["nonexistent"],  # Invalid reference!
                    )
                ],
            )
        assert "unknown intervention" in str(exc_info.value)

    def test_selector_depth_limit(self) -> None:
        """Test enforcement of selector depth limit."""
        nested = SelectorPredicate(kind="predicate", field="id", operator="==", value="all")
        for _ in range(15):  # Exceeds MAX_SELECTOR_DEPTH=10
            nested = SelectorNot(kind="not", clause=nested)

        with pytest.raises(ValidationError) as exc_info:
            PolicySpec(
                policy_id="test",
                interventions=[
                    InterventionSpec(
                        intervention_id="int_1",
                        kind="income_tax",
                        target=nested,
                        schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    )
                ],
            )
        assert "exceeds limit" in str(exc_info.value)


# =============================================================================
# ModelSpec Tests
# =============================================================================


class TestModelSpec:
    """Tests for ModelSpec schema."""

    def test_minimal_valid(self, minimal_model_spec: ModelSpec) -> None:
        """Test minimal valid ModelSpec."""
        assert minimal_model_spec.model_id == "test_model"
        assert minimal_model_spec.fidelity_level == FidelityLevel.HYBRID

    def test_roundtrip_yaml(self, minimal_model_spec: ModelSpec) -> None:
        """Test YAML roundtrip serialization."""
        yaml_str = yaml.dump(minimal_model_spec.model_dump(mode="json"))
        loaded = yaml.safe_load(yaml_str)
        restored = ModelSpec.model_validate(loaded)
        assert restored == minimal_model_spec

    def test_rejects_invalid_data_snapshot_ref(self) -> None:
        """Test rejection of invalid data_snapshot_ref pattern."""
        with pytest.raises(ValidationError):
            ModelSpec(
                model_id="test",
                data_snapshot_ref="invalid_ref",  # Not sha256:... pattern
            )

    def test_rejects_duplicate_assumption_ids(self) -> None:
        """Test rejection of duplicate assumption IDs."""
        with pytest.raises(ValidationError) as exc_info:
            ModelSpec(
                model_id="test",
                data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
                assumptions=[
                    AssumptionSpec(
                        assumption_id="dup",
                        assumption_type=AssumptionType.BEHAVIORAL,
                        description="Test 1",
                    ),
                    AssumptionSpec(
                        assumption_id="dup",  # Duplicate!
                        assumption_type=AssumptionType.STRUCTURAL,
                        description="Test 2",
                    ),
                ],
            )
        assert "duplicate assumption_id" in str(exc_info.value)

    def test_rejects_population_share_exceeding_one(self) -> None:
        """Test rejection of agent type population shares exceeding 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            ModelSpec(
                model_id="test",
                data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
                agent_config=AgentConfig(
                    agent_types=[
                        AgentTypeConfig(
                            agent_type_id="type_1",
                            entity_type=EntityType.AGENT,
                            population_share=Decimal("0.7"),
                        ),
                        AgentTypeConfig(
                            agent_type_id="type_2",
                            entity_type=EntityType.AGENT,
                            population_share=Decimal("0.5"),  # Total = 1.2 > 1.0
                        ),
                    ]
                ),
            )
        assert "exceeds 1.0" in str(exc_info.value)


# =============================================================================
# Typed Reference Tests
# =============================================================================


class TestTypedReferences:
    """Tests for typed references (ProblemFrameRef, PolicySpecRef, ModelSpecRef)."""

    def test_problem_frame_ref_kind(self) -> None:
        """Test ProblemFrameRef has correct kind literal."""
        ref = ProblemFrameRef(
            artifact_id=ArtifactID.from_sha256_hex(
                "0000000000000000000000000000000000000000000000000000000000000000"
            )
        )
        assert ref.kind == "ir.problem_frame"
        assert ref.media_type == "application/json"

    def test_policy_spec_ref_kind(self) -> None:
        """Test PolicySpecRef has correct kind literal."""
        ref = PolicySpecRef(
            artifact_id=ArtifactID.from_sha256_hex(
                "0000000000000000000000000000000000000000000000000000000000000000"
            )
        )
        assert ref.kind == "ir.policy_spec"
        assert ref.media_type == "application/json"

    def test_model_spec_ref_kind(self) -> None:
        """Test ModelSpecRef has correct kind literal."""
        ref = ModelSpecRef(
            artifact_id=ArtifactID.from_sha256_hex(
                "0000000000000000000000000000000000000000000000000000000000000000"
            )
        )
        assert ref.kind == "ir.model_spec"
        assert ref.media_type == "application/json"

    def test_trinity_bundle(self) -> None:
        """Test TrinityBundle correctly bundles all three refs."""
        artifact_id = ArtifactID.from_sha256_hex(
            "0000000000000000000000000000000000000000000000000000000000000000"
        )
        bundle = TrinityBundle(
            problem_frame_ref=ProblemFrameRef(artifact_id=artifact_id),
            policy_spec_ref=PolicySpecRef(artifact_id=artifact_id),
            model_spec_ref=ModelSpecRef(artifact_id=artifact_id),
        )
        assert bundle.compatible is True
        assert bundle.problem_frame_ref.kind == "ir.problem_frame"
        assert bundle.policy_spec_ref.kind == "ir.policy_spec"
        assert bundle.model_spec_ref.kind == "ir.model_spec"


class TestIRTrinityBundle:
    """Tests for canonical IR TrinityBundle payload."""

    def test_ir_bundle_schema(self) -> None:
        bundle = IRTrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="pf_test",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(
                policy_id="ps_test",
            ),
            model_spec=ModelSpec(
                model_id="ms_test",
                data_snapshot_ref="sha256:" + "0" * 64,
            ),
        )
        assert bundle.schema_version == "1.0"


# =============================================================================
# Canonical Output Tests
# =============================================================================


class TestCanonicalOutput:
    """Tests for canonical serialization output."""

    def test_yaml_roundtrip_produces_canonical_output(
        self, minimal_problem_frame: ProblemFrame
    ) -> None:
        """Test that yaml -> model -> yaml produces identical output."""
        yaml1 = yaml.dump(
            minimal_problem_frame.model_dump(mode="json"),
            sort_keys=True,
            default_flow_style=False,
        )
        model1 = ProblemFrame.model_validate(yaml.safe_load(yaml1))

        yaml2 = yaml.dump(
            model1.model_dump(mode="json"),
            sort_keys=True,
            default_flow_style=False,
        )

        assert yaml1 == yaml2, "YAML roundtrip not canonical"

    def test_json_serialization_deterministic(self, minimal_policy_spec: PolicySpec) -> None:
        """Test that JSON serialization is deterministic."""
        json1 = minimal_policy_spec.model_dump_json(indent=2)
        json2 = minimal_policy_spec.model_dump_json(indent=2)
        assert json1 == json2, "JSON serialization not deterministic"


# =============================================================================
# Float Rejection Tests (inherited from surface.py behavior)
# =============================================================================


class TestFloatRejection:
    """Tests ensuring float values are rejected (Decimal required)."""

    def test_policy_spec_rejects_float_params(self) -> None:
        """Test that float params are rejected in PolicySpec."""
        with pytest.raises(ValidationError):
            PolicySpec(
                policy_id="test",
                interventions=[
                    InterventionSpec(
                        intervention_id="int_1",
                        kind="income_tax",
                        target=SelectorPredicate(
                            kind="predicate", field="id", operator="==", value="all"
                        ),
                        schedule=ScheduleSpec(start_step=0, duration_steps=1),
                        params={"rate": 0.15},  # float, should be Decimal
                    )
                ],
            )
