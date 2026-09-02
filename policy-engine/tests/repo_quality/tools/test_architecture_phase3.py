from __future__ import annotations

import argparse
import datetime as dt
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from tools.devx.architecture import guardrails, scaffold


@pytest.fixture(scope="module")
def current_deep_import_edges() -> tuple[guardrails.DeepImportEdge, ...]:
    policies = guardrails._parse_public_surface(
        guardrails.REPO_ROOT / "architecture/public_surface/contract.toml"
    )
    return tuple(guardrails.collect_deep_import_edges(policies))


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
    assert (
        source.read_text(encoding="utf-8")
        == textwrap.dedent(
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
    )
    assert 'assert issues[0].code == "SAMPLE_POLICY_ARTIFACT_MISSING"' in tests.read_text(
        encoding="utf-8"
    )


def test_guardrails_detects_new_deep_import_creep(tmp_path: Path) -> None:
    baseline = tmp_path / "baselines" / "imports" / "deep_import.json"
    baseline.parent.mkdir(parents=True)
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


def test_fabric_world_exact_facade_is_shared_by_release_deep_import_classifier(
    current_deep_import_edges: tuple[guardrails.DeepImportEdge, ...],
) -> None:
    """The exact world facade is public while implementation descendants stay deep."""

    policies = guardrails._parse_public_surface(
        guardrails.REPO_ROOT / "architecture/public_surface/contract.toml"
    )
    fabric = next(policy for policy in policies if policy.module == "polisyos.fabric")
    assert "polisyos.fabric.world" in fabric.supported_entrypoints
    assert not any(
        entrypoint.startswith("polisyos.fabric.world.")
        for entrypoint in fabric.supported_entrypoints
    )

    edge_keys = {edge.key for edge in current_deep_import_edges}
    assert (
        "polisyos.runtime.quality.data_state_substrate->polisyos.fabric.world"
        not in edge_keys
    )

    descendant_edges: dict[str, guardrails.DeepImportEdge] = {}
    guardrails._maybe_add_deep_import(
        edges=descendant_edges,
        allowed_entrypoints={"fabric": set(fabric.supported_entrypoints)},
        source_module="polisyos.runtime.consumer",
        source_root="runtime",
        source_file=guardrails.REPO_ROOT / "src/polisyos/runtime/consumer.py",
        target_module="polisyos.fabric.world.store",
    )
    assert set(descendant_edges) == {
        "polisyos.runtime.consumer->polisyos.fabric.world.store"
    }


@pytest.mark.parametrize(
    ("source_module", "private_target"),
    [
        (
            "polisyos.runtime.http.services.channel_contracts",
            "polisyos.core.artifacts.manifest",
        ),
        (
            "polisyos.runtime.http.services.channel_contracts",
            "polisyos.core.contracts.decision_validity",
        ),
        (
            "polisyos.runtime.http.services.control.lex_pipeline",
            "polisyos.lex.knowledge.store",
        ),
        (
            "polisyos.runtime.http.services.control.lex_search_projection",
            "polisyos.core.contracts.runtime",
        ),
        (
            "polisyos.runtime.http.services.control.lex_search_projection",
            "polisyos.lex.knowledge.types",
        ),
        (
            "polisyos.scientist.orchestration.engine.checkpoint",
            "polisyos.core.security.tenant_context",
        ),
    ],
)
def test_adjudicated_consumer_does_not_bypass_selected_route(
    source_module: str,
    private_target: str,
    current_deep_import_edges: tuple[guardrails.DeepImportEdge, ...],
) -> None:
    edge_keys = {edge.key for edge in current_deep_import_edges}

    assert f"{source_module}->{private_target}" not in edge_keys


def test_runtime_lex_projection_has_no_unregistered_core_or_lex_edge(
    current_deep_import_edges: tuple[guardrails.DeepImportEdge, ...],
) -> None:
    targets = {
        edge.target_module
        for edge in current_deep_import_edges
        if edge.source_module == "polisyos.runtime.http.services.control.lex_search_projection"
        and edge.target_root in {"core", "lex"}
    }

    assert targets == set()


def test_checkpoint_scope_uses_candidate_security_route(
    current_deep_import_edges: tuple[guardrails.DeepImportEdge, ...],
) -> None:
    security_targets = {
        edge.target_module
        for edge in current_deep_import_edges
        if edge.source_module == "polisyos.scientist.orchestration.engine.checkpoint"
        and edge.target_module.startswith("polisyos.core.security")
    }

    assert security_targets == {"polisyos.core.security"}


def test_guardrails_exception_registry_requires_declared_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = tmp_path / "exceptions" / "guardrails.toml"
    registry = tmp_path / "guardrail_exceptions_registry.md"
    expires = dt.date.today() + dt.timedelta(days=14)
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)
    exceptions.parent.mkdir(parents=True)
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


def _generated_client_family(
    repo_root: Path,
    *,
    family_id: str,
    declared_outputs: tuple[str, ...],
    emitted_outputs: tuple[tuple[str, str], ...],
    default_freshness_check: bool = True,
    source_of_truth: str = "schemas/test.openapi.json",
    output_probe_command: tuple[str, ...] | None = None,
) -> guardrails.GeneratedArtifactFamily:
    writer = textwrap.dedent(
        f"""
        import sys
        from pathlib import Path

        output_root = Path(sys.argv[1])
        for relative, contents in {emitted_outputs!r}:
            destination = output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(contents, encoding="utf-8")
        """
    )
    return guardrails.GeneratedArtifactFamily(
        family_id=family_id,
        label=family_id,
        owner="test-owner",
        approval_owner="test-owner",
        lifecycle="generated_committed",
        generator="test generator",
        verifier="generator-observed freshness check",
        promotion_target="test outputs",
        stale_output_behavior="fail",
        source_of_truth=source_of_truth,
        outputs=tuple(repo_root / relative for relative in declared_outputs),
        regenerate_commands=("test generator",),
        commit_policy="committed",
        freshness_rule="generated bytes must match",
        drift_gate="automated",
        workflow=None,
        check_cwd=None,
        check_command=None,
        check_git_diff_paths=(),
        default_freshness_check=default_freshness_check,
        output_probe_command=output_probe_command
        or (sys.executable, "-c", writer, "{output_root}"),
        retention_days=None,
    )


def _write_expected_output(expected_root: Path, relative: str, contents: str) -> None:
    destination = expected_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(contents, encoding="utf-8")


def test_guardrails_rejects_emitted_but_unregistered_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_root = tmp_path / "expected"
    _write_expected_output(expected_root, "packages/client/owned.ts", "owned\n")
    family = _generated_client_family(
        tmp_path,
        family_id="runtime-api-client",
        declared_outputs=("packages/client/owned.ts",),
        emitted_outputs=(
            ("packages/client/owned.ts", "owned\n"),
            ("packages/client/new-output.ts", "new\n"),
        ),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)

    violations = guardrails._run_required_generated_artifact_checks(
        [family],
        expected_root=expected_root,
    )

    assert any(
        violation.subject == "runtime-api-client"
        and violation.detail == "packages/client/new-output.ts"
        and "not registered" in violation.message
        for violation in violations
    )


def test_runtime_openapi_client_cannot_escape_default_check_by_removing_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_root = tmp_path / "expected"
    relative = "packages/client/types.ts"
    _write_expected_output(expected_root, relative, "generated\n")
    family = _generated_client_family(
        tmp_path,
        family_id="runtime-api-client",
        declared_outputs=(relative,),
        emitted_outputs=((relative, "generated\n"),),
        default_freshness_check=False,
        source_of_truth=guardrails.RUNTIME_OPENAPI_CLIENT_SOURCE,
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)

    violations = guardrails._run_required_generated_artifact_checks(
        [family],
        expected_root=expected_root,
    )

    assert violations == []
    assert "runtime-api-client" in capsys.readouterr().out
    assert any(
        violation.detail == "missing_default_freshness_check"
        for violation in guardrails._check_generated_artifact_manifest([family])
    )


def test_runtime_openapi_snapshot_is_a_default_freshness_probe() -> None:
    families = {
        family.family_id: family
        for family in guardrails._parse_generated_artifacts(
            guardrails.DEFAULT_GENERATED_MANIFEST
        )
    }

    family = families["runtime-openapi-snapshot"]

    assert family.default_freshness_check is True
    assert family.output_probe_command is not None
    assert "tools/ops_runners/runtime/export_runtime_openapi.py" in family.output_probe_command
    assert (
        "{output_root}/schemas/runtime_api_v1.openapi.json"
        in family.output_probe_command
    )
    assert "consulted dependency basis" in family.freshness_rule


def test_guardrails_rejects_probe_that_rewrites_oracle_and_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_root = tmp_path / "expected"
    relative = "packages/client/types.ts"
    expected = expected_root / relative
    escaped = tmp_path / "escaped-output.ts"
    _write_expected_output(expected_root, relative, "original\n")
    writer = textwrap.dedent(
        """
        import sys
        from pathlib import Path

        output_root = Path(sys.argv[1])
        expected = Path(sys.argv[2])
        escaped = Path(sys.argv[3])
        candidate = output_root / "packages/client/types.ts"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("rewritten\\n", encoding="utf-8")
        expected.write_text("rewritten\\n", encoding="utf-8")
        escaped.write_text("outside scratch\\n", encoding="utf-8")
        """
    )
    family = _generated_client_family(
        tmp_path,
        family_id="runtime-api-client",
        declared_outputs=(relative,),
        emitted_outputs=(),
        output_probe_command=(
            sys.executable,
            "-c",
            writer,
            "{output_root}",
            "expected/packages/client/types.ts",
            "escaped-output.ts",
        ),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)

    violations = guardrails._run_required_generated_artifact_checks(
        [family],
        expected_root=expected_root,
    )

    assert any(
        violation.subject == "runtime-api-client"
        and violation.detail == "output_probe_worktree_escape"
        and "escaped-output.ts" in violation.message
        and "packages/client/types.ts" in violation.message
        for violation in violations
    )
    assert "Generated artifact freshness clean" not in capsys.readouterr().out
    assert expected.read_text(encoding="utf-8") == "original\n"
    assert not escaped.exists()


def test_standard_ci_always_reaches_plain_generated_freshness_gate() -> None:
    workflow_path = guardrails.REPO_ROOT.parent / ".github" / "workflows" / "ci.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True))

    assert triggers is not None
    pull_request = triggers["pull_request"]
    assert pull_request is None or "paths" not in pull_request
    commands = [
        step.get("run")
        for step in workflow["jobs"]["frontend-contracts"]["steps"]
        if isinstance(step, dict)
    ]
    assert "uv run polisyos-tools architecture guardrails check" in commands


@pytest.mark.parametrize(
    "escape",
    [
        "marker_only",
        "step_if_false",
        "step_continue_on_error",
        "job_if_false",
        "job_continue_on_error",
    ],
)
def test_architecture_guardrails_detect_non_gating_trust_posture_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    escape: str,
) -> None:
    """Keep the posture command executable and load-bearing in its named CI job."""

    workflow_rel = Path("ops/ci/templates/workflows/arch.yml")
    workflow_text = (guardrails.REPO_ROOT / workflow_rel).read_text(encoding="utf-8")
    trust_step = (
        "      - name: Verify trust claim posture\n"
        "        run: uv run pytest tests/repo_quality/tools/"
        "test_trust_claim_posture.py -q\n"
    )
    assert trust_step in workflow_text
    marker_only = (
        "      # run: uv run pytest tests/repo_quality/tools/"
        "test_trust_claim_posture.py -q\n"
    )
    if escape == "marker_only":
        mutated = workflow_text.replace(trust_step, marker_only, 1)
    elif escape == "step_if_false":
        mutated = workflow_text.replace(
            trust_step,
            trust_step.replace("        run:", "        if: false\n        run:", 1),
            1,
        )
    elif escape == "step_continue_on_error":
        mutated = workflow_text.replace(
            trust_step,
            trust_step.replace(
                "        run:", "        continue-on-error: true\n        run:", 1
            ),
            1,
        )
    elif escape == "job_if_false":
        mutated = workflow_text.replace(
            "  import-gate:\n", "  import-gate:\n    if: false\n", 1
        )
    else:
        mutated = workflow_text.replace(
            "  import-gate:\n", "  import-gate:\n    continue-on-error: true\n", 1
        )
    workflow_path = tmp_path / workflow_rel
    workflow_path.parent.mkdir(parents=True)
    workflow_path.write_text(mutated, encoding="utf-8")
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    import_gate = workflow["jobs"]["import-gate"]
    trust_steps = [
        step
        for step in import_gate["steps"]
        if isinstance(step, dict)
        and step.get("run")
        == "uv run pytest tests/repo_quality/tools/test_trust_claim_posture.py -q"
    ]
    assert escape == "marker_only" or len(trust_steps) == 1
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)

    violations = guardrails._check_workflow_toolchain_guardrails()

    assert "trust_claim_posture" in {violation.detail for violation in violations}


def test_jobs_collecting_generator_entrypoint_test_install_node_toolchain() -> None:
    workflows = {
        "runtime-http": guardrails.REPO_ROOT.parent / ".github/workflows/ci.yml",
        "runtime-contracts": (
            guardrails.REPO_ROOT.parent
            / ".github/workflows/core-runtime-release-gate.yml"
        ),
    }

    for job, workflow_path in workflows.items():
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        actions = [
            step.get("uses")
            for step in workflow["jobs"][job]["steps"]
            if isinstance(step, dict)
        ]
        assert "./.github/actions/setup-runtime-dashboard" in actions


def test_guardrails_corruption_names_failed_family_and_keeps_sibling_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_root = tmp_path / "expected"
    _write_expected_output(expected_root, "packages/client/types.ts", "corrupt\n")
    _write_expected_output(expected_root, "apps/dashboard/types.ts", "dashboard\n")
    families = [
        _generated_client_family(
            tmp_path,
            family_id="runtime-api-client",
            declared_outputs=("packages/client/types.ts",),
            emitted_outputs=(("packages/client/types.ts", "generated\n"),),
        ),
        _generated_client_family(
            tmp_path,
            family_id="runtime-dashboard-api-types",
            declared_outputs=("apps/dashboard/types.ts",),
            emitted_outputs=(("apps/dashboard/types.ts", "dashboard\n"),),
        ),
    ]
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)

    violations = guardrails._run_required_generated_artifact_checks(
        families,
        expected_root=expected_root,
    )

    assert any(
        violation.subject == "runtime-api-client"
        and violation.detail == "packages/client/types.ts"
        and "does not match" in violation.message
        for violation in violations
    )
    assert not any(
        violation.subject == "runtime-dashboard-api-types" for violation in violations
    )
    receipt = capsys.readouterr().out
    assert "runtime-dashboard-api-types" in receipt
    assert "clean" in receipt


def test_guardrails_rejects_generator_output_with_multiple_family_owners(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_root = tmp_path / "expected"
    shared_output = "packages/client/shared.ts"
    _write_expected_output(expected_root, shared_output, "shared\n")
    families = [
        _generated_client_family(
            tmp_path,
            family_id="client-a",
            declared_outputs=(shared_output,),
            emitted_outputs=((shared_output, "shared\n"),),
        ),
        _generated_client_family(
            tmp_path,
            family_id="client-b",
            declared_outputs=(shared_output,),
            emitted_outputs=((shared_output, "shared\n"),),
        ),
    ]
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)

    violations = guardrails._run_required_generated_artifact_checks(
        families,
        expected_root=expected_root,
    )

    assert any(
        violation.detail == shared_output
        and "registered by multiple families: client-a, client-b" in violation.message
        for violation in violations
    )


def test_guardrails_rejects_declared_output_that_generator_no_longer_emits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_root = tmp_path / "expected"
    emitted = "packages/client/emitted.ts"
    missing = "packages/client/not-emitted.ts"
    _write_expected_output(expected_root, emitted, "emitted\n")
    family = _generated_client_family(
        tmp_path,
        family_id="runtime-api-client",
        declared_outputs=(emitted, missing),
        emitted_outputs=((emitted, "emitted\n"),),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)

    violations = guardrails._run_required_generated_artifact_checks(
        [family],
        expected_root=expected_root,
    )

    assert any(
        violation.subject == "runtime-api-client"
        and violation.detail == missing
        and "did not emit" in violation.message
        for violation in violations
    )
