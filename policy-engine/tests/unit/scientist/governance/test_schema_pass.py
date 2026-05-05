from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.core.governance.passes.base import IssueSeverity
from polisyos.scientist.governance.passes.schema_pass import SchemaPass
from pydantic import ValidationError


def _make_valid_ir(*, num_interventions: int = 2):
    """Create a mock IR that passes schema validation."""
    ir = MagicMock()
    ir.policy_spec.interventions = [MagicMock() for _ in range(num_interventions)]
    ir.model_dump.return_value = {"valid": "payload"}
    return ir


class TestSchemaPass:
    def test_ir_none_blocker(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(ir=None, profile=strict_profile)
        issues = SchemaPass().validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "IR_MISSING"
        assert issues[0].severity is IssueSeverity.BLOCKER

    def test_valid_ir_no_issues(self, pass_context_factory, strict_profile):
        ir = _make_valid_ir(num_interventions=2)
        with patch("polisyos.scientist.governance.passes.schema_pass.TrinityBundle.model_validate"):
            ctx = pass_context_factory(ir=ir, profile=strict_profile)
            issues = SchemaPass().validate(ctx)
            assert issues == []

    def test_ir_validation_errors_blocker(self, pass_context_factory, strict_profile):
        ir = _make_valid_ir(num_interventions=2)

        # Simulate a ValidationError from TrinityBundle.model_validate
        validation_issue = MagicMock()
        validation_issue.loc = ("policy_spec", "name")
        validation_issue.message = "Field required"
        validation_issue.input_value = "None"

        report_mock = MagicMock()
        report_mock.issues = [validation_issue]

        with (
            patch(
                "polisyos.scientist.governance.passes.schema_pass.TrinityBundle.model_validate",
                side_effect=ValidationError.from_exception_data(
                    title="TrinityBundle",
                    line_errors=[
                        {
                            "type": "missing",
                            "loc": ("policy_spec", "name"),
                            "msg": "Field required",
                            "input": {},
                        }
                    ],
                ),
            ),
            patch(
                "polisyos.scientist.governance.passes.schema_pass.build_validation_report",
                return_value=report_mock,
            ),
        ):
            ctx = pass_context_factory(ir=ir, profile=strict_profile)
            issues = SchemaPass().validate(ctx)
            schema_errors = [i for i in issues if i.code == "SCHEMA_VALIDATION_ERROR"]
            assert len(schema_errors) >= 1
            assert schema_errors[0].severity is IssueSeverity.BLOCKER

    def test_empty_interventions_blocker(self, pass_context_factory, strict_profile):
        ir = _make_valid_ir(num_interventions=0)
        ir.policy_spec.interventions = []

        with patch("polisyos.scientist.governance.passes.schema_pass.TrinityBundle.model_validate"):
            ctx = pass_context_factory(ir=ir, profile=strict_profile)
            issues = SchemaPass().validate(ctx)
            assert any(i.code == "NO_INTERVENTIONS" for i in issues)
            no_int = next(i for i in issues if i.code == "NO_INTERVENTIONS")
            assert no_int.severity is IssueSeverity.BLOCKER

    def test_single_intervention_passes(self, pass_context_factory, strict_profile):
        ir = _make_valid_ir(num_interventions=1)

        with patch("polisyos.scientist.governance.passes.schema_pass.TrinityBundle.model_validate"):
            ctx = pass_context_factory(ir=ir, profile=strict_profile)
            issues = SchemaPass().validate(ctx)
            assert issues == []

    def test_pass_id_is_schema(self):
        assert SchemaPass().pass_id == "schema"

    def test_ir_missing_returns_early(self, pass_context_factory, strict_profile):
        """When IR is None, should return immediately with IR_MISSING and no other issues."""
        ctx = pass_context_factory(ir=None, profile=strict_profile)
        issues = SchemaPass().validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "IR_MISSING"
