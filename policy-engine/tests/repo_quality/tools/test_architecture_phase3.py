from __future__ import annotations

import argparse
import ast
import datetime as dt
import os
import subprocess
import sys
import textwrap
from dataclasses import replace
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
    assert "polisyos.runtime.quality.data_state_substrate->polisyos.fabric.world" not in edge_keys

    descendant_edges: dict[str, guardrails.DeepImportEdge] = {}
    guardrails._maybe_add_deep_import(
        edges=descendant_edges,
        allowed_entrypoints={"fabric": set(fabric.supported_entrypoints)},
        source_module="polisyos.runtime.consumer",
        source_root="runtime",
        source_file=guardrails.REPO_ROOT / "src/polisyos/runtime/consumer.py",
        target_module="polisyos.fabric.world.store",
    )
    assert set(descendant_edges) == {"polisyos.runtime.consumer->polisyos.fabric.world.store"}


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
    source = guardrails.REPO_ROOT / "src/polisyos/scientist/orchestration/engine/checkpoint.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    security_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.startswith("polisyos.core.security")
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("polisyos.core.security")
    }
    private_security_edges = {
        edge.target_module
        for edge in current_deep_import_edges
        if edge.source_module == "polisyos.scientist.orchestration.engine.checkpoint"
        and edge.target_module.startswith("polisyos.core.security.")
    }

    assert security_imports == {"polisyos.core.security"}
    assert private_security_edges == set()


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
    repo_root.mkdir(parents=True, exist_ok=True)
    directory_contract = repo_root / "architecture/policies/directory_contracts.toml"
    if not directory_contract.exists():
        directory_contract.parent.mkdir(parents=True, exist_ok=True)
        directory_contract.write_text(
            '[[contract]]\npath = ".git"\nstatus = "local_only"\n'
            '[[contract]]\npath = ".venv"\nstatus = "local_only"\n'
            '[[contract]]\npath = "production_data"\nstatus = "local_only"\n',
            encoding="utf-8",
        )
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
        probe_input_roots=(repo_root,),
        probe_required_paths=(directory_contract,),
    )


def _write_expected_output(expected_root: Path, relative: str, contents: str) -> None:
    destination = expected_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(contents, encoding="utf-8")


def test_generated_probe_preserves_caller_editable_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run a real uv generator without rebinding the caller's editable package."""
    caller = tmp_path / "caller"
    package = caller / "src/freshness_station_probe"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (caller / "pyproject.toml").write_text(
        '[project]\nname = "freshness-station-probe"\nversion = "0.0.0"\n'
        'requires-python = ">=3.11"\n'
        '[build-system]\nrequires = []\nbuild-backend = "backend"\nbackend-path = ["."]\n',
        encoding="utf-8",
    )
    # A stdlib-only editable backend keeps the regression independent of network/cache state.
    (caller / "backend.py").write_text(
        textwrap.dedent("""\
            from pathlib import Path
            from zipfile import ZipFile

            def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
                name = "freshness_station_probe-0.0.0-py3-none-any.whl"
                info = "freshness_station_probe-0.0.0.dist-info"
                files = {
                    "freshness_station_probe.pth": str(Path(__file__).parent / "src") + "\\n",
                    info + "/METADATA": "Metadata-Version: 2.1\\nName: freshness-station-probe\\nVersion: 0.0.0\\n",
                    info + "/WHEEL": "Wheel-Version: 1.0\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n",
                }
                files[info + "/RECORD"] = "".join(key + ",,\\n" for key in files) + info + "/RECORD,,\\n"
                with ZipFile(Path(wheel_directory) / name, "w") as wheel:
                    for path, content in files.items():
                        wheel.writestr(path, content)
                return name

            build_wheel = build_editable
            """),
        encoding="utf-8",
    )
    (caller / "uv.toml").write_text('cache-dir = "_cache/uv"\n', encoding="utf-8")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("UV_")}
    environment.pop("VIRTUAL_ENV", None)
    subprocess.run(
        ["uv", "sync", "--offline", "--python", sys.executable],
        cwd=caller,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    def bindings() -> dict[str, bytes]:
        return {
            path.relative_to(caller).as_posix(): path.read_bytes()
            for path in (caller / ".venv").rglob("*.pth")
        }

    before = bindings()
    assert before, "The probe must actually have an editable install to protect."
    expected = tmp_path / "expected"
    _write_expected_output(expected, "generated.txt", "generated\n")
    writer = (
        "from pathlib import Path; import sys, freshness_station_probe; "
        "p = Path(sys.argv[1]); p.mkdir(parents=True); "
        "(p / 'generated.txt').write_text('generated\\n')"
    )
    family = _generated_client_family(
        caller,
        family_id="editable-binding-probe",
        declared_outputs=("generated.txt",),
        emitted_outputs=(),
        output_probe_command=("uv", "run", "--offline", "python", "-c", writer, "{output_root}"),
    )
    directory_contract = caller / "architecture/policies/directory_contracts.toml"
    with directory_contract.open("a", encoding="utf-8") as contract:
        contract.write('[[contract]]\npath = "_cache/uv"\nstatus = "local_only"\n')
    monkeypatch.setattr(guardrails, "REPO_ROOT", caller)
    # Even a caller-selected environment must not redirect the generator's install.
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", str(caller / ".venv"))
    findings = guardrails._run_required_generated_artifact_checks([family], expected_root=expected)

    assert bindings() == before
    imported = subprocess.run(
        [
            str(caller / ".venv/bin/python"),
            "-c",
            "import freshness_station_probe; print(freshness_station_probe.__file__)",
        ],
        cwd=caller,
        capture_output=True,
        text=True,
        check=True,
    )
    assert Path(imported.stdout.strip()) == package / "__init__.py"
    assert findings == []


def test_generated_probe_prepares_private_python_and_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caller = tmp_path / "caller"
    caller.mkdir()
    (caller / "uv.toml").write_text('cache-dir = "_cache/uv"\n', encoding="utf-8")
    expected = tmp_path / "expected"
    _write_expected_output(expected, "generated.txt", "generated\n")
    writer = textwrap.dedent("""\
        import os
        import subprocess
        import sys
        from pathlib import Path

        source = Path.cwd().resolve()
        environment = Path(sys.prefix).resolve()
        assert environment != Path(sys.base_prefix).resolve()
        assert not environment.is_relative_to(source)
        assert (source / '.venv').resolve() == environment
        assert Path(os.environ['UV_PROJECT_ENVIRONMENT']).resolve() == environment
        cache = Path(subprocess.run(
            ['uv', 'cache', 'dir'], capture_output=True, text=True, check=True
        ).stdout.strip()).resolve()
        cache.mkdir(parents=True, exist_ok=True)
        (cache / 'probe-cache-write').write_text('cache')
        assert not cache.is_relative_to(source)
        output = Path(sys.argv[1])
        output.mkdir(parents=True)
        (output / 'generated.txt').write_text('generated\\n')
        """)
    family = _generated_client_family(
        caller,
        family_id="private-python-cache-probe",
        declared_outputs=("generated.txt",),
        emitted_outputs=(),
        output_probe_command=(".venv/bin/python", "-c", writer, "{output_root}"),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", caller)

    findings = guardrails._run_required_generated_artifact_checks([family], expected_root=expected)

    assert findings == []
    assert not (caller / ".venv").exists()
    assert not (caller / "_cache").exists()


@pytest.mark.parametrize("outcome", ["pass", "finding", "unrun", "interrupt"])
def test_retained_generated_probe_workspace_survives_every_measurement_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    """An explicit workspace remains available after a pass, finding, or interruption."""
    caller = tmp_path / "caller"
    caller.mkdir()
    package = caller / "src/polisyos"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("MARKER = 'copied'\n", encoding="utf-8")
    tools_package = caller / "tools"
    tools_package.mkdir()
    (tools_package / "__init__.py").write_text("MARKER = 'copied'\n", encoding="utf-8")
    source_data = tmp_path / "source-data"
    source_data.mkdir()
    (source_data / "private.csv").write_text("must not be copied\n", encoding="utf-8")
    (caller / "production_data").symlink_to(source_data, target_is_directory=True)
    cache = tmp_path / "shared-uv-cache"
    cache.mkdir()
    cache_marker = cache / "existing-wheel-cache-marker"
    cache_marker.write_text("reuse without copying\n", encoding="utf-8")
    retained = tmp_path / "retained-run"
    expected = tmp_path / "expected"
    _write_expected_output(expected, "generated.txt", "generated\n")
    emitted = "different\n" if outcome == "finding" else "generated\n"
    family = _generated_client_family(
        caller,
        family_id="retention-control",
        declared_outputs=("generated.txt",),
        emitted_outputs=(),
        output_probe_command=(
            sys.executable,
            "-c",
            textwrap.dedent(
                """\
                import os
                import sys
                from pathlib import Path

                cache = Path(os.environ["UV_CACHE_DIR"]).resolve()
                assert os.environ["UV_OFFLINE"] == "1"
                assert cache == Path(sys.argv[1]).resolve()
                output = Path(sys.argv[2])
                output.mkdir(parents=True, exist_ok=True)
                (output / "generated.txt").write_text(sys.argv[3], encoding="utf-8")
                """
            ),
            str(cache),
            "{output_root}",
            emitted,
        ),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", caller)
    monkeypatch.setattr(guardrails, "_snapshot_git_visible_worktree", lambda _root: {})

    def prepare_environment(_source_root: Path, environment: dict[str, str]) -> None:
        private_environment = Path(environment["UV_PROJECT_ENVIRONMENT"])
        python_bin = private_environment / "bin/python"
        python_bin.parent.mkdir(parents=True)
        python_bin.symlink_to(sys.executable)
        (_source_root / ".venv").symlink_to(private_environment, target_is_directory=True)
        if outcome == "unrun":
            raise OSError("offline dependency unavailable")

    monkeypatch.setattr(guardrails, "_prepare_isolated_probe_environment", prepare_environment)
    if outcome == "interrupt":
        real_run = guardrails.subprocess.run
        origin_preflight_completed = False
        generator_interrupted = False

        def interrupt_first_family_generator(*args, **kwargs):
            nonlocal origin_preflight_completed, generator_interrupted
            command = args[0] if args else kwargs.get("args")
            if isinstance(command, (list, tuple)) and "-c" in command:
                code = command[command.index("-c") + 1]
                if "canonical_source_origin" in str(code):
                    result = real_run(*args, **kwargs)
                    origin_preflight_completed = True
                    return result
            if origin_preflight_completed:
                generator_interrupted = True
                raise KeyboardInterrupt("fixture")
            return real_run(*args, **kwargs)

        monkeypatch.setattr(guardrails.subprocess, "run", interrupt_first_family_generator)

    if outcome in {"unrun", "interrupt"}:
        with pytest.raises(guardrails.GeneratedArtifactCheckUnrunError) as failure:
            guardrails._run_required_generated_artifact_checks(
                [family],
                expected_root=expected,
                retained_workspace_root=retained,
                uv_cache_dir=cache,
            )
        assert failure.value.unrun_checks[0].phase == (
            "environment" if outcome == "unrun" else "generator"
        )
        if outcome == "interrupt":
            assert origin_preflight_completed
            assert generator_interrupted
    else:
        findings = guardrails._run_required_generated_artifact_checks(
            [family],
            expected_root=expected,
            retained_workspace_root=retained,
            uv_cache_dir=cache,
        )
        assert bool(findings) is (outcome == "finding")

    assert (retained / "source").is_dir()
    assert (retained / "environment").is_dir()
    assert (retained / "outputs").is_dir()
    assert not (retained / "source/production_data").exists()
    if outcome in {"pass", "finding"}:
        assert (retained / "outputs/retention-control/generated.txt").read_text(
            encoding="utf-8"
        ) == emitted
    assert cache_marker.read_text(encoding="utf-8") == "reuse without copying\n"


def test_retained_generated_probe_rejects_existing_root_without_removing_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caller = tmp_path / "caller"
    caller.mkdir()
    retained = tmp_path / "already-retained"
    retained.mkdir()
    sentinel = retained / "keep-me.txt"
    sentinel.write_text("do not remove\n", encoding="utf-8")
    cache = tmp_path / "shared-uv-cache"
    cache.mkdir()
    expected = tmp_path / "expected"
    family = _generated_client_family(
        caller,
        family_id="existing-workspace",
        declared_outputs=(),
        emitted_outputs=(),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", caller)

    with pytest.raises(guardrails.GeneratedArtifactCheckUnrunError) as failure:
        guardrails._run_required_generated_artifact_checks(
            [family],
            expected_root=expected,
            retained_workspace_root=retained,
            uv_cache_dir=cache,
        )

    assert [(item.family_id, item.phase) for item in failure.value.unrun_checks] == [
        (family.family_id, "environment")
    ]
    assert sentinel.read_text(encoding="utf-8") == "do not remove\n"


def test_guardrail_check_parses_retained_workspace_and_offline_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "guardrails",
            "check",
            "--generated-freshness-workspace-root",
            "/tmp/run-123",
            "--generated-freshness-uv-cache-dir",
            "/tmp/uv-cache",
        ],
    )

    args = guardrails._parse_args()

    assert args.generated_freshness_workspace_root == Path("/tmp/run-123")
    assert args.generated_freshness_uv_cache_dir == Path("/tmp/uv-cache")


@pytest.mark.parametrize("provide_workspace", [False, True])
def test_retained_freshness_options_must_be_supplied_as_a_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provide_workspace: bool,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    cache = tmp_path / "existing-cache"
    cache.mkdir()
    expected = tmp_path / "expected"
    workspace = tmp_path / "new-workspace"
    family = _generated_client_family(
        source,
        family_id="option-pair",
        declared_outputs=(),
        emitted_outputs=(),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", source)

    with pytest.raises(guardrails.GeneratedArtifactCheckUnrunError) as failure:
        guardrails._run_required_generated_artifact_checks(
            [family],
            expected_root=expected,
            retained_workspace_root=workspace if provide_workspace else None,
            uv_cache_dir=None if provide_workspace else cache,
        )

    assert failure.value.unrun_checks[0].family_id == family.family_id
    assert failure.value.unrun_checks[0].phase == "environment"
    assert not workspace.exists()


def test_isolated_python_import_origin_rejects_canonical_source_with_matching_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "copied-source"
    canonical = tmp_path / "canonical-source"
    for root in (source, canonical):
        package = root / "src/polisyos"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("MARKER = 'same'\n", encoding="utf-8")
        tools_package = root / "tools"
        tools_package.mkdir()
        (tools_package / "__init__.py").write_text("MARKER = 'same'\n", encoding="utf-8")
    assert (source / "src/polisyos/__init__.py").read_bytes() == (
        canonical / "src/polisyos/__init__.py"
    ).read_bytes()
    expected = tmp_path / "expected"
    _write_expected_output(expected, "generated.txt", "byte-identical\n")
    family = _generated_client_family(
        source,
        family_id="canonical-origin-removal-probe",
        declared_outputs=("generated.txt",),
        emitted_outputs=(("generated.txt", "byte-identical\n"),),
    )
    cache = tmp_path / "uv-cache"
    cache.mkdir()
    retained = tmp_path / "retained"
    monkeypatch.setattr(guardrails, "REPO_ROOT", source)
    monkeypatch.setattr(guardrails, "_snapshot_git_visible_worktree", lambda _root: {})

    def prepare_private_python(source_root: Path, environment: dict[str, str]) -> None:
        private_environment = Path(environment["UV_PROJECT_ENVIRONMENT"])
        python_bin = private_environment / "bin/python"
        python_bin.parent.mkdir(parents=True)
        python_bin.symlink_to(sys.executable)
        (source_root / ".venv").symlink_to(private_environment, target_is_directory=True)

    monkeypatch.setattr(guardrails, "_prepare_isolated_probe_environment", prepare_private_python)
    environment_builder = guardrails._isolated_probe_environment

    def redirect_import_to_canonical(
        source_root: Path,
        *,
        uv_cache_dir: Path | None = None,
        offline: bool = False,
        repo_root: Path | None = None,
        families: tuple[guardrails.GeneratedArtifactFamily, ...] = (),
    ) -> dict[str, str]:
        environment = environment_builder(
            source_root,
            uv_cache_dir=uv_cache_dir,
            offline=offline,
            repo_root=repo_root,
            families=families,
        )
        environment["PYTHONPATH"] = os.pathsep.join((str(canonical / "src"), str(canonical)))
        return environment

    monkeypatch.setattr(
        guardrails,
        "_isolated_probe_environment",
        redirect_import_to_canonical,
    )

    with pytest.raises(guardrails.GeneratedArtifactCheckUnrunError) as failure:
        guardrails._run_required_generated_artifact_checks(
            [family],
            expected_root=expected,
            retained_workspace_root=retained,
            uv_cache_dir=cache,
        )

    assert failure.value.unrun_checks[0].phase == "environment"
    assert "canonical_source_origin" in failure.value.unrun_checks[0].diagnostic
    assert not (retained / "outputs/canonical-origin-removal-probe/generated.txt").exists()
    assert (retained / "source/src/polisyos/__init__.py").read_bytes() == (
        canonical / "src/polisyos/__init__.py"
    ).read_bytes()


def test_generated_probe_refuses_unprepared_project_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caller = tmp_path / "caller"
    caller.mkdir()
    (caller / "pyproject.toml").write_text(
        '[project]\nname = "missing-lock-probe"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    expected = tmp_path / "expected"
    _write_expected_output(expected, "generated.txt", "generated\n")
    family = _generated_client_family(
        caller,
        family_id="unprepared-environment-probe",
        declared_outputs=("generated.txt",),
        emitted_outputs=(("generated.txt", "generated\n"),),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", caller)

    with pytest.raises(RuntimeError, match="UNRUN") as failure:
        guardrails._run_required_generated_artifact_checks([family], expected_root=expected)

    assert failure.value.unrun_checks[0].phase == "environment"
    assert failure.value.unrun_checks[0].family_id == family.family_id
    assert not failure.value.violations


@pytest.mark.parametrize("missing_executable", [False, True])
def test_failed_generator_is_unrun_and_cannot_admit_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_executable: bool
) -> None:
    """A failed producer cannot establish freshness, even when it wrote matching bytes."""
    source = tmp_path / "source"
    source.mkdir()
    expected = tmp_path / "expected"
    _write_expected_output(expected, "partial.txt", "matching\n")
    _write_expected_output(expected, "sibling.txt", "stale\n")
    command = (
        (str(tmp_path / "missing-interpreter"),)
        if missing_executable
        else (
            sys.executable,
            "-c",
            "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.mkdir(parents=True); "
            "(p/'partial.txt').write_text('matching\\n'); "
            "print('producer-unavailable-witness',file=sys.stderr); sys.exit(17)",
            "{output_root}",
        )
    )
    families = [
        _generated_client_family(
            source,
            family_id="failed-producer",
            declared_outputs=("partial.txt",),
            emitted_outputs=(),
            output_probe_command=command,
        ),
        _generated_client_family(
            source,
            family_id="completed-sibling",
            declared_outputs=("sibling.txt",),
            emitted_outputs=(("sibling.txt", "fresh\n"),),
        ),
    ]
    monkeypatch.setattr(guardrails, "REPO_ROOT", source)

    with pytest.raises(RuntimeError, match="UNRUN") as failure:
        guardrails._run_required_generated_artifact_checks(families, expected_root=expected)

    assert [(check.family_id, check.phase) for check in failure.value.unrun_checks] == [
        ("failed-producer", "generator")
    ]
    assert [(finding.subject, finding.detail) for finding in failure.value.violations] == [
        ("completed-sibling", "sibling.txt")
    ]
    if not missing_executable:
        assert "producer-unavailable-witness" in str(failure.value)


def test_non_decodable_generator_output_is_an_unrun_measurement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even a zero exit cannot make an unreadable producer response a verdict."""
    source = tmp_path / "source"
    source.mkdir()
    expected = tmp_path / "expected"
    _write_expected_output(expected, "generated.txt", "expected\n")
    family = _generated_client_family(
        source,
        family_id="invalid-encoding",
        declared_outputs=("generated.txt",),
        emitted_outputs=(),
        output_probe_command=(sys.executable, "-c", "import os; os.write(1, b'\\xff')"),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", source)
    with pytest.raises(guardrails.GeneratedArtifactCheckUnrunError, match="UnicodeDecodeError"):
        guardrails._run_required_generated_artifact_checks([family], expected_root=expected)


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
        for family in guardrails._parse_generated_artifacts(guardrails.DEFAULT_GENERATED_MANIFEST)
    }

    family = families["runtime-openapi-snapshot"]

    assert family.default_freshness_check is True
    assert family.output_probe_command is not None
    assert "tools/ops_runners/runtime/export_runtime_openapi.py" in family.output_probe_command
    assert "{output_root}/schemas/runtime_api_v1.openapi.json" in family.output_probe_command
    assert "consulted dependency basis" in family.freshness_rule


def test_guardrails_check_discloses_the_standalone_status_gate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A passing aggregate cannot imply that it ran the Atlas status gate."""
    args = argparse.Namespace(
        public_manifest=guardrails.DEFAULT_PUBLIC_MANIFEST,
        public_json=guardrails.DEFAULT_PUBLIC_JSON,
        public_md=guardrails.DEFAULT_PUBLIC_MD,
        generated_manifest=guardrails.DEFAULT_GENERATED_MANIFEST,
        generated_md=guardrails.DEFAULT_GENERATED_MD,
        deep_import_baseline=guardrails.DEFAULT_DEEP_IMPORT_BASELINE,
        exceptions=guardrails.DEFAULT_EXCEPTION_FILE,
        exceptions_registry=guardrails.DEFAULT_EXCEPTION_REGISTRY,
        max_expiry_days=guardrails.DEFAULT_MAX_EXPIRY_DAYS,
        skip_generated_checks=True,
        all_generated_checks=False,
        generated_expected_root=guardrails.REPO_ROOT,
    )

    guardrails.run_check(args)

    assert guardrails.STATUS_RETIREMENT_STANDALONE_NOTICE in capsys.readouterr().out.splitlines()


def test_guardrail_cli_cannot_waive_an_unrun_required_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Artifact exceptions cannot turn an unavailable producer into a complete verdict."""
    exceptions = tmp_path / "exceptions.toml"
    registry = tmp_path / "registry.md"
    exceptions.write_text(
        '[[exception]]\nid = "unrun-waiver"\ncheck = "generated_artifact"\n'
        'owner = "test"\nreason = "must not waive missing measurement"\n'
        f'expires = "{(dt.date.today() + dt.timedelta(days=7)).isoformat()}"\n'
        'subject_glob = "*"\ndetail_glob = "*"\n'
    )
    registry.write_text("| unrun-waiver | fixture exception |\n")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "guardrails",
            "check",
            "--exceptions",
            str(exceptions),
            "--exceptions-registry",
            str(registry),
        ],
    )

    def unavailable(_source: Path, _environment: dict[str, str]) -> None:
        raise OSError("unavailable-station-witness")

    monkeypatch.setattr(guardrails, "_prepare_isolated_probe_environment", unavailable)
    assert guardrails.main() == 2
    output = capsys.readouterr().out
    assert "Architecture guardrail check UNRUN" in output
    assert "unavailable-station-witness" in output
    assert "Architecture guardrail check passed." not in output
    assert "Architecture guardrail check FAILED:" not in output


def test_guardrail_cli_reports_interrupted_setup_as_unrun(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A user interrupt during freshness setup produces the gate's typed UNRUN verdict."""
    monkeypatch.setattr(sys, "argv", ["guardrails", "check"])

    def prepare_empty_source(
        _repo_root: Path,
        destination: Path,
        *,
        families: tuple[guardrails.GeneratedArtifactFamily, ...] = (),
    ) -> tuple[tuple[Path, ...], str | None]:
        destination.mkdir(parents=True)
        return (), None

    def interrupted(_source: Path, _environment: dict[str, str]) -> None:
        raise KeyboardInterrupt("test cancellation")

    monkeypatch.setattr(guardrails, "_copy_isolated_probe_source", prepare_empty_source)
    monkeypatch.setattr(guardrails, "_prepare_isolated_probe_environment", interrupted)

    assert guardrails.main() == 2
    output = capsys.readouterr().out
    assert "Architecture guardrail check UNRUN" in output
    required = [
        family.family_id
        for family in guardrails._parse_generated_artifacts(guardrails.DEFAULT_GENERATED_MANIFEST)
        if guardrails._requires_default_generated_freshness(family)
    ]
    assert required
    for family_id in required:
        assert f"UNRUN {family_id} [environment]: KeyboardInterrupt" in output
    assert "Architecture guardrail check passed." not in output
    assert "Architecture guardrail check FAILED:" not in output


def test_interrupted_generator_is_unrun_and_keeps_completed_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The active and pending families are UNRUN while completed evidence is retained."""
    source = tmp_path / "source"
    source.mkdir()
    expected = tmp_path / "expected"
    _write_expected_output(expected, "completed.txt", "expected\n")
    _write_expected_output(expected, "active.txt", "expected\n")
    _write_expected_output(expected, "pending.txt", "expected\n")
    families = [
        _generated_client_family(
            source,
            family_id="completed-family",
            declared_outputs=("completed.txt",),
            emitted_outputs=(("completed.txt", "different\n"),),
        ),
        _generated_client_family(
            source,
            family_id="active-family",
            declared_outputs=("active.txt",),
            emitted_outputs=(("active.txt", "expected\n"),),
        ),
        _generated_client_family(
            source,
            family_id="pending-family",
            declared_outputs=("pending.txt",),
            emitted_outputs=(("pending.txt", "expected\n"),),
        ),
    ]
    monkeypatch.setattr(guardrails, "REPO_ROOT", source)
    monkeypatch.setattr(guardrails, "_prepare_isolated_probe_environment", lambda *_: None)
    monkeypatch.setattr(guardrails, "_snapshot_git_visible_worktree", lambda _root: {})
    original_run = subprocess.run

    def interrupt_active_family(*args, **kwargs):
        command = args[0] if args else kwargs.get("args", ())
        if (
            isinstance(command, (list, tuple))
            and "-c" in command
            and Path(str(command[-1])).name == "active-family"
        ):
            raise KeyboardInterrupt("test cancellation")
        return original_run(*args, **kwargs)

    monkeypatch.setattr(guardrails.subprocess, "run", interrupt_active_family)

    with pytest.raises(guardrails.GeneratedArtifactCheckUnrunError) as failure:
        guardrails._run_required_generated_artifact_checks(families, expected_root=expected)

    assert [(item.family_id, item.phase) for item in failure.value.unrun_checks] == [
        ("active-family", "generator"),
        ("pending-family", "not_started"),
    ]
    assert "KeyboardInterrupt" in failure.value.unrun_checks[0].diagnostic
    assert "Not started" in failure.value.unrun_checks[1].diagnostic
    assert [(item.subject, item.detail) for item in failure.value.violations] == [
        ("completed-family", "completed.txt")
    ]


def test_interrupted_output_comparison_names_pending_family_and_keeps_active_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interrupt during comparison keeps the active family's already observed mismatch."""
    source = tmp_path / "source"
    source.mkdir()
    expected = tmp_path / "expected"
    _write_expected_output(expected, "first.txt", "expected\n")
    _write_expected_output(expected, "second.txt", "expected\n")
    _write_expected_output(expected, "pending.txt", "expected\n")
    families = [
        _generated_client_family(
            source,
            family_id="active-family",
            declared_outputs=("first.txt", "second.txt"),
            emitted_outputs=(
                ("first.txt", "different\n"),
                ("second.txt", "expected\n"),
            ),
        ),
        _generated_client_family(
            source,
            family_id="pending-family",
            declared_outputs=("pending.txt",),
            emitted_outputs=(("pending.txt", "expected\n"),),
        ),
    ]
    monkeypatch.setattr(guardrails, "REPO_ROOT", source)
    monkeypatch.setattr(guardrails, "_prepare_isolated_probe_environment", lambda *_: None)
    monkeypatch.setattr(guardrails, "_snapshot_git_visible_worktree", lambda _root: {})
    original_read_bytes = Path.read_bytes

    def interrupt_on_second_output(path: Path) -> bytes:
        if "outputs" in path.parts and "active-family" in path.parts and path.name == "second.txt":
            raise KeyboardInterrupt("test cancellation during comparison")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", interrupt_on_second_output)

    with pytest.raises(guardrails.GeneratedArtifactCheckUnrunError) as failure:
        guardrails._run_required_generated_artifact_checks(families, expected_root=expected)

    assert [(item.subject, item.detail) for item in failure.value.violations] == [
        ("active-family", "first.txt")
    ]
    assert [(item.family_id, item.phase) for item in failure.value.unrun_checks] == [
        ("active-family", "output_comparison"),
        ("pending-family", "not_started"),
    ]
    assert "KeyboardInterrupt" in failure.value.unrun_checks[0].diagnostic


def test_interrupt_between_generated_families_preserves_prior_unrun_and_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The run cursor separates a completed attempt from the pending next family."""
    source = tmp_path / "source"
    source.mkdir()
    expected = tmp_path / "expected"
    _write_expected_output(expected, "pending.txt", "expected\n")
    first = _generated_client_family(
        source,
        family_id="completed-attempt",
        declared_outputs=(),
        emitted_outputs=(),
        output_probe_command=(
            sys.executable,
            "-c",
            "from pathlib import Path; Path('rogue.py').write_text('x'); raise SystemExit(17)",
            "{output_root}",
        ),
    )
    second = _generated_client_family(
        source,
        family_id="pending-family",
        declared_outputs=("pending.txt",),
        emitted_outputs=(("pending.txt", "expected\n"),),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", source)
    monkeypatch.setattr(guardrails, "_prepare_isolated_probe_environment", lambda *_: None)
    monkeypatch.setattr(guardrails, "_snapshot_git_visible_worktree", lambda _root: {})
    cursor_type = guardrails._GeneratedArtifactMeasurementCursor
    original_complete = cursor_type.complete_family

    def interrupt_after_first_completion(cursor, family_index: int) -> None:
        original_complete(cursor, family_index)
        if family_index == 0:
            raise KeyboardInterrupt("between-family cancellation")

    monkeypatch.setattr(cursor_type, "complete_family", interrupt_after_first_completion)

    with pytest.raises(guardrails.GeneratedArtifactCheckUnrunError) as failure:
        guardrails._run_required_generated_artifact_checks([first, second], expected_root=expected)

    assert [(item.family_id, item.phase) for item in failure.value.unrun_checks] == [
        ("completed-attempt", "generator"),
        ("pending-family", "not_started"),
    ]
    assert "exit=17" in failure.value.unrun_checks[0].diagnostic
    assert [(item.subject, item.detail) for item in failure.value.violations] == [
        ("completed-attempt", "output_probe_worktree_escape")
    ]


def test_interrupt_during_scratch_cleanup_does_not_relabel_completed_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After all family attempts, cleanup interruption has a run-level identity."""
    source = tmp_path / "source"
    source.mkdir()
    expected = tmp_path / "expected"
    _write_expected_output(expected, "changed.txt", "expected\n")
    _write_expected_output(expected, "clean.txt", "expected\n")
    families = [
        _generated_client_family(
            source,
            family_id="completed-with-finding",
            declared_outputs=("changed.txt",),
            emitted_outputs=(("changed.txt", "different\n"),),
        ),
        _generated_client_family(
            source,
            family_id="completed-cleanly",
            declared_outputs=("clean.txt",),
            emitted_outputs=(("clean.txt", "expected\n"),),
        ),
    ]
    monkeypatch.setattr(guardrails, "REPO_ROOT", source)
    monkeypatch.setattr(guardrails, "_prepare_isolated_probe_environment", lambda *_: None)
    monkeypatch.setattr(guardrails, "_snapshot_git_visible_worktree", lambda _root: {})
    real_temporary_directory = guardrails.tempfile.TemporaryDirectory

    class InterruptAfterCleanup:
        def __init__(self, *args, **kwargs) -> None:
            self._temporary_directory = real_temporary_directory(*args, **kwargs)

        def __enter__(self):
            return self._temporary_directory.__enter__()

        def __exit__(self, exc_type, exc, traceback):
            self._temporary_directory.__exit__(exc_type, exc, traceback)
            raise KeyboardInterrupt("cleanup cancellation")

    monkeypatch.setattr(guardrails.tempfile, "TemporaryDirectory", InterruptAfterCleanup)

    with pytest.raises(guardrails.GeneratedArtifactCheckUnrunError) as failure:
        guardrails._run_required_generated_artifact_checks(families, expected_root=expected)

    assert [(item.family_id, item.phase) for item in failure.value.unrun_checks] == [
        ("required_freshness_measurement", "scratch_cleanup")
    ]
    assert [(item.subject, item.detail) for item in failure.value.violations] == [
        ("completed-with-finding", "changed.txt")
    ]


def test_required_generator_normal_matching_output_remains_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The interruption boundary preserves the ordinary completed generator control."""
    source = tmp_path / "source"
    source.mkdir()
    expected = tmp_path / "expected"
    _write_expected_output(expected, "generated.txt", "expected\n")
    family = _generated_client_family(
        source,
        family_id="normal-control",
        declared_outputs=("generated.txt",),
        emitted_outputs=(("generated.txt", "expected\n"),),
    )
    monkeypatch.setattr(guardrails, "REPO_ROOT", source)
    monkeypatch.setattr(guardrails, "_prepare_isolated_probe_environment", lambda *_: None)
    monkeypatch.setattr(guardrails, "_snapshot_git_visible_worktree", lambda _root: {})

    assert (
        guardrails._run_required_generated_artifact_checks([family], expected_root=expected) == []
    )


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
        "      # run: uv run pytest tests/repo_quality/tools/test_trust_claim_posture.py -q\n"
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
            trust_step.replace("        run:", "        continue-on-error: true\n        run:", 1),
            1,
        )
    elif escape == "job_if_false":
        mutated = workflow_text.replace("  import-gate:\n", "  import-gate:\n    if: false\n", 1)
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
            guardrails.REPO_ROOT.parent / ".github/workflows/core-runtime-release-gate.yml"
        ),
    }

    for job, workflow_path in workflows.items():
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        actions = [
            step.get("uses") for step in workflow["jobs"][job]["steps"] if isinstance(step, dict)
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
    assert not any(violation.subject == "runtime-dashboard-api-types" for violation in violations)
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


def _family_with_probe_basis(
    repo_root: Path,
    *,
    family_id: str,
    roots: tuple[str, ...],
    required: tuple[str, ...],
) -> guardrails.GeneratedArtifactFamily:
    family = _generated_client_family(
        repo_root,
        family_id=family_id,
        declared_outputs=(),
        emitted_outputs=(),
    )
    directory_contract = repo_root / "architecture/policies/directory_contracts.toml"
    if not directory_contract.exists():
        directory_contract.parent.mkdir(parents=True, exist_ok=True)
        directory_contract.write_text("", encoding="utf-8")
    required_paths = tuple(repo_root / item for item in required)
    if directory_contract not in required_paths:
        required_paths += (directory_contract,)
    return replace(
        family,
        probe_input_roots=tuple(repo_root / item for item in roots),
        probe_required_paths=required_paths,
    )


def test_family_source_copy_includes_ignored_untracked_file_read_by_child(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    source_file = repo / "src/polisyos/raw/ignored-source.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("SOURCE_MARKER = 'from ignored source'\n", encoding="utf-8")
    (repo / ".gitignore").write_text("src/polisyos/raw/ignored-source.py\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='probe'\n", encoding="utf-8")
    subprocess.run(("git", "init", "--quiet", str(repo)), check=True)
    subprocess.run(("git", "-C", str(repo), "add", ".gitignore"), check=True)
    ignored = subprocess.run(
        (
            "git",
            "-C",
            str(repo),
            "check-ignore",
            "-q",
            "src/polisyos/raw/ignored-source.py",
        ),
        check=False,
    )
    assert ignored.returncode == 0
    family = _family_with_probe_basis(
        repo,
        family_id="ignored-source-child-read",
        roots=("src",),
        required=("pyproject.toml",),
    )
    destination = tmp_path / "retained/source"
    child = (
        sys.executable,
        "-c",
        "from pathlib import Path; print(Path('src/polisyos/raw/ignored-source.py').read_text())",
    )

    guardrails._copy_isolated_probe_source(repo, destination, families=(family,))
    first = subprocess.run(child, cwd=destination, capture_output=True, text=True, check=True)
    source_file.write_text("SOURCE_MARKER = 'updated ignored source'\n", encoding="utf-8")
    second_destination = tmp_path / "retained/source-after-change"
    guardrails._copy_isolated_probe_source(repo, second_destination, families=(family,))
    second = subprocess.run(
        child, cwd=second_destination, capture_output=True, text=True, check=True
    )

    assert first.stdout != second.stdout
    assert "from ignored source" in first.stdout
    assert "updated ignored source" in second.stdout


def test_family_source_copy_rejects_removed_required_input_while_contract_remains(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "pyproject.toml").write_text(
        "probe_required_paths = still declared\n", encoding="utf-8"
    )
    family = _family_with_probe_basis(
        repo,
        family_id="required-source-removal-control",
        roots=("src",),
        required=("schemas/runtime_api_v1.openapi.json",),
    )
    destination = tmp_path / "retained/source"

    with pytest.raises(OSError, match="required probe input is missing"):
        guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert "probe_required_paths" in (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert not destination.exists()


def test_family_source_copy_rejects_missing_tracked_source_before_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="missing-tracked-source",
        roots=("src",),
        required=("pyproject.toml",),
    )
    missing = repo / "src/missing.py"
    monkeypatch.setattr(guardrails, "iter_repository_files", lambda _root: iter((missing,)))
    destination = tmp_path / "retained/source"

    with pytest.raises(OSError, match="required probe input is missing"):
        guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert not destination.exists()


def test_family_source_copy_rejects_symlinked_source_ancestor(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    source = repo / "src"
    source.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "escape.py").write_text("SOURCE_MARKER = True\n", encoding="utf-8")
    (source / "escape").symlink_to(outside, target_is_directory=True)
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="symlink-ancestor-control",
        roots=("src",),
        required=("pyproject.toml",),
    )
    destination = tmp_path / "retained/source"

    with pytest.raises(OSError, match="symlink"):
        guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert not destination.exists()


def test_family_source_copy_fails_closed_on_directory_enumeration_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    source = repo / "src"
    source.mkdir(parents=True)
    (source / "visible.py").write_text("SOURCE_MARKER = True\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="denied-descendant-control",
        roots=("src",),
        required=("pyproject.toml",),
    )
    original_walk = guardrails.os.walk

    from collections.abc import Callable, Iterator

    def denied_walk(
        path: str | os.PathLike[str],
        topdown: bool = True,
        onerror: Callable[[OSError], None] | None = None,
        followlinks: bool = False,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        if Path(path) == source:
            assert onerror is not None
            onerror(PermissionError(13, "denied untracked descendant", str(source)))
        yield from original_walk(
            path,
            topdown=topdown,
            onerror=onerror,
            followlinks=followlinks,
        )

    monkeypatch.setattr(guardrails.os, "walk", denied_walk)
    destination = tmp_path / "retained/source"

    with pytest.raises(OSError, match="unable to enumerate selected probe source"):
        guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert (source / "visible.py").is_file()
    assert not destination.exists()


def test_family_source_copy_preflights_disk_before_creating_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    source = repo / "src/module.py"
    source.parent.mkdir(parents=True)
    source.write_text("x = 1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="disk-preflight",
        roots=("src",),
        required=("pyproject.toml",),
    )
    destination = tmp_path / "retained/nested/source"
    observed_filesystems: list[Path] = []

    def report_no_space(path: Path) -> object:
        observed_filesystems.append(path)
        return type("Usage", (), {"free": 0})()

    monkeypatch.setattr(guardrails.shutil, "disk_usage", report_no_space)

    with pytest.raises(OSError, match="insufficient disk space"):
        guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert observed_filesystems == [tmp_path]
    assert not (tmp_path / "retained").exists()
    assert not destination.exists()


def test_isolated_probe_ignores_stale_bytecode_in_the_copied_source_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import py_compile

    repo = tmp_path / "repo"
    source = repo / "src/stale_probe.py"
    source.parent.mkdir(parents=True)
    old_source = "VALUE = 'old'\n"
    current_source = "VALUE = 'new'\n"
    assert len(old_source) == len(current_source)
    source.write_text(old_source, encoding="utf-8")
    cache = Path(py_compile.compile(str(source), doraise=True))
    source_stat = source.stat()
    source.write_text(current_source, encoding="utf-8")
    os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
    assert cache.is_file()

    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="stale-bytecode-source-control",
        roots=("src",),
        required=("pyproject.toml",),
    )
    destination = tmp_path / "retained/source"
    guardrails._copy_isolated_probe_source(repo, destination, families=(family,))
    copied_cache = destination / cache.relative_to(repo)
    assert copied_cache.read_bytes() == cache.read_bytes()

    child = (sys.executable, "-B", "-c", "import stale_probe; print(stale_probe.VALUE)")
    plain_environment = os.environ.copy()
    plain_environment.pop("PYTHONPYCACHEPREFIX", None)
    plain_environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": str(repo / "src"),
        }
    )
    unisolated = subprocess.run(
        child,
        cwd=repo,
        env=plain_environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert unisolated.stdout.strip() == "old"

    monkeypatch.delenv("POLISYOS_GOVERNED_ARTIFACT_ROOT", raising=False)
    environment = guardrails._isolated_probe_environment(
        destination,
        repo_root=repo,
        families=(family,),
    )
    bytecode_cache = Path(environment["PYTHONPYCACHEPREFIX"])
    assert bytecode_cache == destination.parent / "python-bytecode-cache"
    assert bytecode_cache.is_absolute()
    assert not bytecode_cache.is_relative_to(destination)
    assert not bytecode_cache.is_relative_to(destination.parent / "environment")
    isolated = subprocess.run(
        child,
        cwd=destination,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert isolated.stdout.strip() == "new"

    marker_only_environment = environment.copy()
    marker_only_environment.pop("PYTHONPYCACHEPREFIX")
    marker_only = subprocess.run(
        child,
        cwd=destination,
        env=marker_only_environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert marker_only.stdout.strip() == "old"


def test_unadmitted_governed_artifact_root_is_refused_before_environment_preparation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="governed-root-control",
        roots=("src",),
        required=("pyproject.toml",),
    )
    source_root = tmp_path / "retained/source"
    source_root.mkdir(parents=True)
    external_root = tmp_path / "external-governed-artifacts"
    external_root.mkdir()
    monkeypatch.setenv("POLISYOS_GOVERNED_ARTIFACT_ROOT", str(external_root))

    with pytest.raises(OSError, match="outside the repository"):
        guardrails._isolated_probe_environment(
            source_root,
            repo_root=repo,
            families=(family,),
        )


def test_trust_probe_basis_includes_actual_compiler_read_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.lib.fs import admitted_read_bytes
    from tools.quality.validation import check_trust_claim_posture

    repo = tmp_path / "repo"
    source = repo / "src/ignored_source.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"source\n")
    register = repo / "docs/plans/active/DEBT-REGISTER.md"
    register.parent.mkdir(parents=True)
    register.write_bytes(b"debt\n")

    def compile_fixture(root: Path) -> tuple[None, bytes]:
        admitted_read_bytes(root / "src/ignored_source.py", root)
        debt = admitted_read_bytes(root / "docs/plans/active/DEBT-REGISTER.md", root)
        return None, debt

    monkeypatch.setattr(
        check_trust_claim_posture,
        "compile_claim_posture_register",
        compile_fixture,
    )

    observed = guardrails._trust_claim_posture_compiler_inputs(repo)

    assert set(observed) == {source, register}


def test_family_source_copy_preserves_python_files_inside_environment_layout(
    tmp_path: Path,
) -> None:
    from tools.quality.validation.trust_claim_posture_sources import walk_source_files

    repo = tmp_path / "repo"
    source = repo / "src"
    environment = source / "toolchain-cache"
    candidate = environment / "lib/python/site-packages/selected_source.py"
    (environment / "bin").mkdir(parents=True)
    candidate.parent.mkdir(parents=True)
    (environment / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    (environment / "bin/python").write_text("runtime-only\n", encoding="utf-8")
    candidate.write_text("SOURCE_MARKER = 'trust consumer input'\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="environment-layout-source",
        roots=("src",),
        required=("pyproject.toml",),
    )
    member_paths = {member.path for member in walk_source_files(repo)}
    relative = candidate.relative_to(repo).as_posix()
    assert relative in member_paths

    destination = tmp_path / "retained/source"
    guardrails._copy_isolated_probe_source(repo, destination, families=(family,))
    child = subprocess.run(
        (
            sys.executable,
            "-c",
            (
                "from pathlib import Path; print(Path("
                "'src/toolchain-cache/lib/python/site-packages/selected_source.py').read_text())"
            ),
        ),
        cwd=destination,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "trust consumer input" in child.stdout


def test_family_source_copy_refuses_fifo_in_source_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source = repo / "src"
    source.mkdir(parents=True)
    os.mkfifo(source / "producer.pipe")
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="special-file-control",
        roots=("src",),
        required=("pyproject.toml",),
    )
    destination = tmp_path / "retained/source"

    with pytest.raises(OSError, match="unsupported special file"):
        guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert not destination.exists()


def test_probe_runtime_links_are_typed_and_preserved_as_links(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    runtime_root = repo / "node_modules"
    (runtime_root / ".pnpm").mkdir(parents=True)
    (repo / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
    (runtime_root / ".pnpm/lock.yaml").write_bytes((repo / "pnpm-lock.yaml").read_bytes())
    (runtime_root / ".modules.yaml").write_text("packageManager: pnpm@10.33.2\n", encoding="utf-8")
    (runtime_root / "package.js").write_text("module.exports = true\n", encoding="utf-8")
    package_root = repo / "packages/runtime-api-client"
    package_root.mkdir(parents=True)
    (package_root / "package.json").write_text("{}\n", encoding="utf-8")
    package_link = package_root / "node_modules"
    package_link.symlink_to(runtime_root, target_is_directory=True)
    family = _family_with_probe_basis(
        repo,
        family_id="frontend-runtime-link",
        roots=("packages/runtime-api-client",),
        required=("packages/runtime-api-client/package.json", "package.json", "pnpm-lock.yaml"),
    )
    (repo / "package.json").write_text('{"packageManager":"pnpm@10.33.2"}\n', encoding="utf-8")
    family = replace(
        family,
        probe_runtime_paths=(
            repo / "node_modules",
            repo / "packages/runtime-api-client/node_modules",
        ),
    )
    destination = tmp_path / "retained/source"

    runtime_paths, initial_inventory = guardrails._copy_isolated_probe_source(
        repo, destination, families=(family,)
    )

    assert initial_inventory is not None
    assert len(initial_inventory) == 64
    assert runtime_paths == (
        Path("node_modules"),
        Path("packages/runtime-api-client/node_modules"),
    )
    assert (destination / "node_modules").is_symlink()
    assert (destination / "packages/runtime-api-client/node_modules").is_symlink()
    assert (destination / "node_modules/package.js").read_text(encoding="utf-8") == (
        "module.exports = true\n"
    )
    (runtime_root / "package.js").write_text("module.exports = false\n", encoding="utf-8")
    changed_inventory = guardrails._verify_pnpm_install_receipt(
        repo,
        frozenset(runtime_paths),
    )
    assert changed_inventory != initial_inventory


def test_probe_runtime_package_link_rejects_external_resolved_target(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    runtime_root = repo / "node_modules"
    (runtime_root / ".pnpm").mkdir(parents=True)
    (repo / "package.json").write_text('{"packageManager":"pnpm@10.33.2"}\n', encoding="utf-8")
    lock = b"lockfileVersion: '9.0'\n"
    (repo / "pnpm-lock.yaml").write_bytes(lock)
    (runtime_root / ".pnpm/lock.yaml").write_bytes(lock)
    (runtime_root / ".modules.yaml").write_text("packageManager: pnpm@10.33.2\n", encoding="utf-8")
    package_root = repo / "packages/runtime-api-client"
    package_root.mkdir(parents=True)
    external = tmp_path / "unbound-runtime"
    external.mkdir()
    (external / "package.js").write_text("EXTERNAL_MARKER = True\n", encoding="utf-8")
    (package_root / "node_modules").symlink_to(external, target_is_directory=True)
    family = _family_with_probe_basis(
        repo,
        family_id="redirected-package-runtime-link",
        roots=("packages/runtime-api-client",),
        required=("package.json", "pnpm-lock.yaml"),
    )
    family = replace(
        family,
        probe_runtime_paths=(
            repo / "node_modules",
            repo / "packages/runtime-api-client/node_modules",
        ),
    )
    destination = tmp_path / "retained/source"

    with pytest.raises(OSError, match="resolves outside the repository"):
        guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert (external / "package.js").read_text(encoding="utf-8") == ("EXTERNAL_MARKER = True\n")
    assert not destination.exists()


def test_probe_runtime_selector_rejects_unregistered_external_path(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="unknown-runtime-path",
        roots=("src",),
        required=("pyproject.toml",),
    )
    family = replace(family, probe_runtime_paths=(repo / "external-runtime",))
    destination = tmp_path / "retained/source"

    with pytest.raises(OSError, match="not an admitted package path"):
        guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert not destination.exists()


def test_local_only_roots_follow_owner_contract_not_nested_basenames(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "architecture/policies").mkdir(parents=True)
    (repo / "architecture/policies/directory_contracts.toml").write_text(
        '[[contract]]\npath = ".polisyos"\nstatus = "local_only"\n'
        '[[contract]]\npath = "production_data"\nstatus = "local_only"\n'
        '[[contract]]\npath = "_cache/uv"\nstatus = "local_only"\n',
        encoding="utf-8",
    )
    (repo / "src/.cache").mkdir(parents=True)
    (repo / "src/_cache/uv").mkdir(parents=True)
    (repo / ".polisyos").mkdir()
    (repo / "production_data").mkdir()
    (repo / "_cache/uv").mkdir(parents=True)
    (repo / "src/.cache/source.py").write_text("CACHE_NAMED_SOURCE = True\n", encoding="utf-8")
    (repo / "src/_cache/source.py").write_text("NESTED_SOURCE = True\n", encoding="utf-8")
    (repo / "src/_cache/uv/source.py").write_text(
        "NESTED_UV_CACHE_SOURCE = True\n", encoding="utf-8"
    )
    (repo / ".polisyos/state.bin").write_bytes(b"local state")
    (repo / "production_data/snapshot.bin").write_bytes(b"local snapshot")
    (repo / "_cache/uv/build.bin").write_bytes(b"local cache")
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="directory-contract-control",
        roots=(".",),
        required=("pyproject.toml",),
    )
    destination = tmp_path / "retained/source"

    guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert (destination / "src/.cache/source.py").is_file()
    assert (destination / "src/_cache/source.py").is_file()
    assert (destination / "src/_cache/uv/source.py").read_text(encoding="utf-8") == (
        "NESTED_UV_CACHE_SOURCE = True\n"
    )
    assert not (destination / ".polisyos").exists()
    assert not (destination / "production_data").exists()
    assert not (destination / "_cache/uv").exists()


def test_family_source_copy_preserves_python_files_inside_huggingface_layout(
    tmp_path: Path,
) -> None:
    from tools.quality.validation.trust_claim_posture_sources import walk_source_files

    repo = tmp_path / "repo"
    source = repo / "src"
    cache = source / "models--fixture--model"
    candidate = cache / "snapshots/revision/selected_source.py"
    for member in ("blobs", "refs", "snapshots/revision"):
        (cache / member).mkdir(parents=True)
    (cache / "blobs/weight.bin").write_bytes(b"cached model")
    candidate.write_text("SOURCE_MARKER = 'cache-layout input'\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="cache-layout-source",
        roots=("src",),
        required=("pyproject.toml",),
    )
    relative = candidate.relative_to(repo).as_posix()
    assert relative in {member.path for member in walk_source_files(repo)}

    destination = tmp_path / "retained/source"
    guardrails._copy_isolated_probe_source(repo, destination, families=(family,))
    child = subprocess.run(
        (
            sys.executable,
            "-c",
            (
                "from pathlib import Path; print(Path("
                "'src/models--fixture--model/snapshots/revision/selected_source.py').read_text())"
            ),
        ),
        cwd=destination,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "cache-layout input" in child.stdout


def test_pnpm_runtime_receipt_must_match_the_declared_lockfile(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "node_modules/.pnpm").mkdir(parents=True)
    (repo / "node_modules/.modules.yaml").write_text(
        "packageManager: pnpm@10.33.2\n", encoding="utf-8"
    )
    (repo / "package.json").write_text('{"packageManager":"pnpm@10.33.2"}\n', encoding="utf-8")
    (repo / "pnpm-lock.yaml").write_text("declared lock\n", encoding="utf-8")
    (repo / "node_modules/.pnpm/lock.yaml").write_text("different install lock\n", encoding="utf-8")
    (repo / "packages/runtime-api-client").mkdir(parents=True)
    family = _family_with_probe_basis(
        repo,
        family_id="pnpm-install-receipt-control",
        roots=("packages/runtime-api-client",),
        required=("package.json", "pnpm-lock.yaml"),
    )
    family = replace(family, probe_runtime_paths=(repo / "node_modules",))
    destination = tmp_path / "retained/source"

    with pytest.raises(OSError, match=r"does not match package\.json and the frozen pnpm lockfile"):
        guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert not destination.exists()


def test_governed_artifact_root_is_removed_when_parent_did_not_set_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="governed-root-unset-control",
        roots=("src",),
        required=("pyproject.toml",),
    )
    source_root = tmp_path / "retained/source"
    source_root.mkdir(parents=True)
    monkeypatch.delenv("POLISYOS_GOVERNED_ARTIFACT_ROOT", raising=False)

    environment = guardrails._isolated_probe_environment(
        source_root,
        repo_root=repo,
        families=(family,),
    )

    assert "POLISYOS_GOVERNED_ARTIFACT_ROOT" not in environment


def test_selected_governed_artifact_root_maps_into_the_isolated_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="governed-root-mapped-control",
        roots=("src",),
        required=("pyproject.toml",),
    )
    source_root = tmp_path / "retained/source"
    guardrails._copy_isolated_probe_source(repo, source_root, families=(family,))
    monkeypatch.setenv("POLISYOS_GOVERNED_ARTIFACT_ROOT", str(repo / "src"))

    environment = guardrails._isolated_probe_environment(
        source_root,
        repo_root=repo,
        families=(family,),
    )

    assert Path(environment["POLISYOS_GOVERNED_ARTIFACT_ROOT"]) == source_root / "src"


def test_internal_symlink_to_unselected_path_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    target = repo / "outside-selected-root.py"
    target.write_text("SOURCE_MARKER = True\n", encoding="utf-8")
    (repo / "src/linked.py").symlink_to(target)
    (repo / "pyproject.toml").write_text("config\n", encoding="utf-8")
    family = _family_with_probe_basis(
        repo,
        family_id="internal-unselected-symlink-control",
        roots=("src",),
        required=("pyproject.toml",),
    )
    destination = tmp_path / "retained/source"

    with pytest.raises(OSError, match="symlink"):
        guardrails._copy_isolated_probe_source(repo, destination, families=(family,))

    assert not destination.exists()
