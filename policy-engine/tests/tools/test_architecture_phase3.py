from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import textwrap

import pytest

from tools.devx.architecture import guardrails, scaffold


def test_scaffold_governance_pass_writes_expected_templates(tmp_path: Path) -> None:
    source = tmp_path / "sample_pass.py"
    tests = tmp_path / "test_sample_pass.py"

    exit_code = scaffold._run_governance_pass(
        argparse.Namespace(
            name="sample_policy",
            class_name=None,
            output=source,
            test_output=tests,
            dry_run=False,
        )
    )

    assert exit_code == 0
    assert source.read_text(encoding="utf-8") == textwrap.dedent(
        """
        from __future__ import annotations

        from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
        from polisyos.core.governance.passes.base import PassContext, ValidatorPass


        class SamplePolicyPass(ValidatorPass):
            \"\"\"Validate one focused governance invariant for Scientist workflows.

            Replace the TODO blocks with domain-specific reads from ``ctx.state`` and
            emit stable issue codes before wiring the pass into the builtin registry.
            \"\"\"

            @property
            def pass_id(self) -> str:
                return "sample_policy"

            @property
            def estimated_cost_ms(self) -> int:
                return 10

            def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
                \"\"\"Return compliance issues for the current workflow state.\"\"\"
                state = ctx.state

                # TODO: replace this placeholder lookup with the real boundary object.
                if state.get("sample_policy_artifact_ref") is None:
                    return [
                        ComplianceIssue(
                            pass_id=self.pass_id,
                            path=["sample_policy_artifact_ref"],
                            message="Required artifact is missing.",
                            severity=IssueSeverity.WARNING,
                            code="SAMPLE_POLICY_ARTIFACT_MISSING",
                            suggestion="Produce the required artifact before the governance pass runs.",
                        )
                    ]

                return []
        """
    ).lstrip()
    assert "assert issues[0].code == \"SAMPLE_POLICY_ARTIFACT_MISSING\"" in tests.read_text(
        encoding="utf-8"
    )


def test_guardrails_detects_new_deep_import_creep(tmp_path: Path) -> None:
    baseline = tmp_path / "deep_import_baseline.json"
    baseline.write_text('{"version":1,"edges":[]}\n', encoding="utf-8")

    violations = guardrails._check_deep_import_creep(
        baseline_path=baseline,
        current_edges=[
            guardrails.DeepImportEdge(
                source_module="polisyos.ir.module_a",
                source_root="ir",
                source_file="src/polisyos/ir/module_a.py",
                target_module="polisyos.fabric.world.store.internal",
                target_root="fabric",
            )
        ],
    )

    assert len(violations) == 1
    assert "New deep-import creep detected" in violations[0].message


def test_guardrails_exception_registry_requires_declared_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = tmp_path / "guardrail_exceptions.toml"
    registry = tmp_path / "guardrail_exceptions_registry.md"
    expires = dt.date.today() + dt.timedelta(days=14)
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)
    exceptions.write_text(
        textwrap.dedent(
            f"""
            [[exception]]
            id = "arch-temp-1"
            check = "deep_import"
            owner = "platform"
            reason = "temporary migration"
            expires = "{expires.isoformat()}"
            subject_glob = "*"
            detail_glob = "*"
            source_module_glob = "polisyos.ir.*"
            target_module_glob = "polisyos.fabric.*"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    registry.write_text("# Guardrail exceptions\n", encoding="utf-8")

    violations = guardrails._validate_guardrail_exceptions(
        exceptions,
        registry,
        max_expiry_days=90,
    )

    assert any("arch-temp-1" in violation for violation in violations)
    assert any("missing from" in violation for violation in violations)
