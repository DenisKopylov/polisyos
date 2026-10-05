from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from tools.devx.architecture import guardrails


def _runtime_client_family() -> guardrails.GeneratedArtifactFamily:
    families = guardrails._parse_generated_artifacts(guardrails.DEFAULT_GENERATED_MANIFEST)
    return next(family for family in families if family.family_id == "runtime-api-client")


def _prepare_probe_source(source_root: Path) -> None:
    """Copy the real package generator inputs and bind installed workspace tools."""
    repo_root = guardrails.REPO_ROOT
    for relative in (
        Path("package.json"),
        Path("pnpm-lock.yaml"),
        Path("pnpm-workspace.yaml"),
        Path("schemas/runtime_api_v1.openapi.json"),
        Path("packages/runtime-api-client"),
        Path("tools/ops_runners/runtime/generate_runtime_client.py"),
    ):
        source = repo_root / relative
        destination = source_root / relative
        if source.is_dir():
            shutil.copytree(
                source,
                destination,
                ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".pytest_cache"),
            )
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    for relative in (Path("node_modules"), Path("packages/runtime-api-client/node_modules")):
        source = repo_root / relative
        assert source.exists(), f"Frozen pnpm install is required for {relative}."
        link = source_root / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(source, link, target_is_directory=True)

    python_link = source_root / ".venv/bin/python"
    python_link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(Path(sys.executable).resolve(), python_link)


def _measure_runtime_client_family(
    *,
    family: guardrails.GeneratedArtifactFamily,
    source_root: Path,
    expected_root: Path,
    output_root: Path,
) -> guardrails._GeneratedArtifactMeasurementCursor:
    outputs = {
        relative
        for output in family.outputs
        if (relative := guardrails._relative_generated_output(output)) is not None
    }
    expected_outputs = guardrails._expected_output_snapshot([family], expected_root=expected_root)
    cursor = guardrails._GeneratedArtifactMeasurementCursor(
        required_families=(family,),
        violations=[],
        unrun_checks=[],
    )
    environment = guardrails._isolated_probe_environment(source_root)
    guardrails._measure_required_generated_artifact_family(
        family,
        family_index=0,
        cursor=cursor,
        family_scratch_root=output_root,
        isolated_repo_root=source_root,
        environment=environment,
        expected_root=expected_root,
        expected_outputs=expected_outputs,
        declared_owners={relative: [family.family_id] for relative in outputs},
    )
    return cursor


def test_registered_runtime_client_probe_runs_real_generator_and_rejects_stale_member(
    tmp_path: Path,
) -> None:
    family = _runtime_client_family()
    assert family.output_probe_command is not None
    outputs = tuple(
        relative
        for output in family.outputs
        if (relative := guardrails._relative_generated_output(output)) is not None
    )
    assert len(outputs) == 3
    assert len(set(outputs)) == 3

    source_root = tmp_path / "source"
    source_root.mkdir()
    _prepare_probe_source(source_root)

    expected_root = tmp_path / "expected"
    for relative in outputs:
        destination = expected_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(guardrails.REPO_ROOT / relative, destination)

    stale_member = next(relative for relative in outputs if relative.endswith(".js"))
    expected_member = expected_root / stale_member
    clean_bytes = expected_member.read_bytes()
    expected_member.write_bytes(clean_bytes + b"\n// stale generated-byte witness\n")
    try:
        stale = _measure_runtime_client_family(
            family=family,
            source_root=source_root,
            expected_root=expected_root,
            output_root=tmp_path / "generated-output" / family.family_id,
        )
        assert stale.unrun_checks == []
        assert len(stale.violations) == 1
        matching = [
            violation
            for violation in stale.violations
            if violation.subject == family.family_id
            and violation.detail == stale_member
            and "does not match" in violation.message
        ]
        assert len(matching) == 1
        observed = {
            path.relative_to(tmp_path / "generated-output" / family.family_id).as_posix()
            for path in (tmp_path / "generated-output" / family.family_id).rglob("*")
            if path.is_file()
        }
        assert observed == set(outputs)
    finally:
        expected_member.write_bytes(clean_bytes)

    assert expected_member.read_bytes() == clean_bytes
