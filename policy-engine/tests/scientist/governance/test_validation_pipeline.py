import pytest

from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator
from polisyos.scientist.governance.pipeline import ValidationPipeline
from polisyos.scientist.governance.profiles import ValidationProfile, ProfileLevel
from polisyos.scientist.governance.passes.base import (
    ValidatorPass,
    PassContext,
    ComplianceIssue,
    IssueSeverity,
)


def _create_minimal_ir() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_1", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_1",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_subsidy_1",
                    kind="tax_subsidy",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 1},
                    params={"rate": "0.1"},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_1",
            data_snapshot_ref="sha256:" + "0" * 64,
        ),
    )


class AlwaysBlockerPass(ValidatorPass):
    """Test pass that always returns a blocker."""

    @property
    def pass_id(self) -> str:
        return "always_blocker"

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        return [
            ComplianceIssue(
                pass_id=self.pass_id,
                path=["test"],
                message="Always blocks",
                severity=IssueSeverity.BLOCKER,
                code="TEST_BLOCKER",
            )
        ]


class NeverRunPass(ValidatorPass):
    """Test pass that should never run if short-circuit works."""

    @property
    def pass_id(self) -> str:
        return "never_run"

    @property
    def estimated_cost_ms(self) -> int:
        return 1000

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        raise AssertionError("This pass should not run due to short-circuit!")


class ExpensiveSafetyPass(ValidatorPass):
    """Mock safety pass with high cost."""

    @property
    def pass_id(self) -> str:
        return "safety"

    @property
    def estimated_cost_ms(self) -> int:
        return 100

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        return [
            ComplianceIssue(
                pass_id=self.pass_id,
                path=["safety"],
                message="Safety check ran",
                severity=IssueSeverity.INFO,
                code="SAFETY_RAN",
            )
        ]


def test_blocker_short_circuits_pipeline() -> None:
    """Blocker should stop pipeline when short_circuit_on_blocker=True."""
    pipeline = ValidationPipeline([AlwaysBlockerPass(), NeverRunPass()])

    profile = ValidationProfile(
        level=ProfileLevel.MVP,
        pass_ids=frozenset({"always_blocker", "never_run"}),
        thresholds={},
        short_circuit_on_blocker=True,
    )

    ctx = PassContext(
        ir=None,
        state={},
        registry_bundle=None,
        profile=profile,
        run_id="test_001",
    )

    issues, trace = pipeline.validate(ctx, profile)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.BLOCKER
    assert trace.short_circuited is True
    assert len(trace.spans) == 1
    assert trace.spans[0].pass_id == "always_blocker"


def test_fast_profile_skips_safety() -> None:
    """FAST profile should not run safety pass."""
    from polisyos.scientist.governance.passes.schema_pass import SchemaPass
    from polisyos.scientist.governance.passes.budget_pass import BudgetPass

    pipeline = ValidationPipeline([BudgetPass(), SchemaPass(), ExpensiveSafetyPass()])

    fast_profile = ValidationProfile.fast()

    ctx = PassContext(
        ir=_create_minimal_ir(),
        state={"budget": {"max_sim_runs": 5}},
        registry_bundle=None,
        profile=fast_profile,
        run_id="test_002",
    )

    _, trace = pipeline.validate(ctx, fast_profile)

    pass_ids_run = [span.pass_id for span in trace.spans]
    assert "safety" not in pass_ids_run
    assert "schema" in pass_ids_run
    assert "budget" in pass_ids_run


def test_mvp_profile_runs_safety() -> None:
    """MVP profile should run safety pass."""
    from polisyos.scientist.governance.passes.schema_pass import SchemaPass
    from polisyos.scientist.governance.passes.budget_pass import BudgetPass

    pipeline = ValidationPipeline([BudgetPass(), SchemaPass(), ExpensiveSafetyPass()])

    mvp_profile = ValidationProfile.mvp()

    ctx = PassContext(
        ir=_create_minimal_ir(),
        state={"budget": {"max_sim_runs": 5}},
        registry_bundle={"mechanism_registry": {"mechanisms": {}}},
        profile=mvp_profile,
        run_id="test_003",
    )

    _, trace = pipeline.validate(ctx, mvp_profile)

    pass_ids_run = [span.pass_id for span in trace.spans]
    assert "safety" in pass_ids_run


def test_telemetry_attached_on_failure() -> None:
    """Trace should be in state even when validation fails."""
    from polisyos.scientist.governance import preflight_checks
    from polisyos.scientist.governance.profiles import ValidationProfile

    state = {"run_id": "test_004", "ir": None, "budget": {"max_sim_runs": 5}}

    updated_state, gate_request = preflight_checks(state, ValidationProfile.mvp())

    assert gate_request is not None
    assert "validation_trace" in updated_state

    trace = updated_state["validation_trace"]
    assert trace["run_id"] == "test_004"
    assert trace["profile"] == "mvp"
    assert trace["total_blockers"] >= 1
    assert len(trace["spans"]) >= 1

    from polisyos.scientist.governance.telemetry import ValidationTrace

    trace_obj = ValidationTrace(
        run_id=trace["run_id"],
        profile=trace["profile"],
        spans=[],
        total_issues=trace["total_issues"],
        total_blockers=trace["total_blockers"],
        short_circuited=trace["short_circuited"],
    )

    record = trace_obj.to_trace_record()
    assert record.run_id == "test_004"
    assert record.phase == "governance_validation"


def test_telemetry_has_timing_data() -> None:
    """Each pass span should have duration_ms after completion."""
    from polisyos.scientist.governance.passes.schema_pass import SchemaPass
    from polisyos.scientist.governance.passes.budget_pass import BudgetPass

    pipeline = ValidationPipeline([BudgetPass(), SchemaPass()])

    ctx = PassContext(
        ir=_create_minimal_ir(),
        state={"budget": {"max_sim_runs": 5}},
        registry_bundle=None,
        profile=ValidationProfile.fast(),
        run_id="test_005",
    )

    _, trace = pipeline.validate(ctx, ValidationProfile.fast())

    for span in trace.spans:
        assert span.duration_ms is not None
        assert span.duration_ms >= 0
        assert span.start_time is not None
        assert span.end_time is not None
