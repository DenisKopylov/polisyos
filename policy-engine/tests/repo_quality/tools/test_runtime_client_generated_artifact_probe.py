"""The runtime-client freshness gate detects a removed operation with its markers intact."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.devx.architecture import guardrails

ROOT = Path(__file__).resolve().parents[3]
COPY_PATHS = (
    "package.json",
    "pnpm-workspace.yaml",
    "pnpm-lock.yaml",
    "architecture/generated_artifacts.toml",
    "schemas/runtime_api_v1.openapi.json",
    "packages/runtime-api-client/package.json",
    "packages/runtime-api-client/types.ts",
    "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
    "packages/runtime-api-client/canonicalRuntimeApiClient.js",
    "packages/runtime-api-client/scripts/generate-runtime-api-client.sh",
    "packages/runtime-api-client/scripts/normalize-recursive-openapi-types.mjs",
    "packages/runtime-api-client/scripts/canonicalize-runtime-client.mjs",
    "tools/ops_runners/runtime/generate_runtime_client.py",
)


def _copy_generator_workspace(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    for relative in COPY_PATHS:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)

    for relative in ("node_modules", "packages/runtime-api-client/node_modules"):
        dependency = ROOT / relative
        assert dependency.is_dir(), f"UNRUN: fresh frozen pnpm install required: {dependency}"
        (source / relative).symlink_to(dependency, target_is_directory=True)

    python = source / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    return source


def _measure(
    source: Path,
    output_root: Path,
    family: guardrails.GeneratedArtifactFamily,
    families: list[guardrails.GeneratedArtifactFamily],
    expected_root: Path,
) -> guardrails._GeneratedArtifactMeasurementCursor:
    owners: dict[str, list[str]] = {}
    for candidate_family in families:
        for output in candidate_family.outputs:
            relative = guardrails._relative_generated_output(output)
            if relative is not None:
                owners.setdefault(relative, []).append(candidate_family.family_id)
    cursor = guardrails._GeneratedArtifactMeasurementCursor(
        required_families=(family,),
        violations=[],
        unrun_checks=[],
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(source / "src"), str(source)))
    guardrails._measure_required_generated_artifact_family(
        family,
        family_index=0,
        cursor=cursor,
        family_scratch_root=output_root,
        isolated_repo_root=source,
        environment=environment,
        expected_root=expected_root,
        expected_outputs=guardrails._expected_output_snapshot(
            [family], expected_root=expected_root
        ),
        declared_owners=owners,
    )
    return cursor


def test_freshness_rejects_a_missing_runtime_operation_with_package_markers_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _copy_generator_workspace(tmp_path)
    monkeypatch.setattr(guardrails, "REPO_ROOT", source)
    families = guardrails._parse_generated_artifacts(
        source / "architecture/generated_artifacts.toml"
    )
    family = next(item for item in families if item.family_id == "runtime-api-client")
    expected = {
        guardrails._relative_generated_output(output)
        for output in family.outputs
        if guardrails._relative_generated_output(output) is not None
    }

    positive_root = tmp_path / "positive-output" / family.family_id
    positive = _measure(source, positive_root, family, families, source)
    observed = {
        item.relative_to(positive_root).as_posix()
        for item in positive_root.rglob("*")
        if item.is_file()
    }
    assert positive.violations == []
    assert positive.unrun_checks == []
    assert observed == expected

    selected_relative = sorted(expected)[0]
    corrupted_candidate: dict[str, Path | bytes] = {}
    real_run = guardrails.subprocess.run

    def generate_then_corrupt(
        command: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        result = real_run(command, **kwargs)  # type: ignore[arg-type]
        if (
            isinstance(command, (list, tuple))
            and command
            and command[0] == "corepack"
            and "--output-root" in command
        ):
            generated_root = Path(command[command.index("--output-root") + 1])
            candidate = generated_root / selected_relative
            original_bytes = candidate.read_bytes()
            candidate.write_bytes(original_bytes + b"\n// test-only byte corruption\n")
            corrupted_candidate.update(path=candidate, original=original_bytes)
        return result

    monkeypatch.setattr(guardrails.subprocess, "run", generate_then_corrupt)
    corruption = _measure(
        source,
        tmp_path / "corrupted-output" / family.family_id,
        family,
        families,
        source,
    )
    assert corruption.unrun_checks == []
    assert {violation.detail for violation in corruption.violations} == {selected_relative}
    candidate = corrupted_candidate["path"]
    original_bytes = corrupted_candidate["original"]
    assert isinstance(candidate, Path)
    assert isinstance(original_bytes, bytes)
    candidate.write_bytes(original_bytes)
    assert candidate.read_bytes() == original_bytes
    monkeypatch.setattr(guardrails.subprocess, "run", real_run)

    generator = source / "tools/ops_runners/runtime/generate_runtime_client.py"
    generator_source = generator.read_text(encoding="utf-8")
    operation_append = "            operations.append(\n                OperationSpec(\n                    name=name,"
    assert generator_source.count(operation_append) == 1
    generator.write_text(
        generator_source.replace(
            operation_append,
            '            if name == "getRunHumanDecisionEvidenceContent":\n'
            "                continue\n" + operation_append,
        ),
        encoding="utf-8",
    )

    output_root = tmp_path / "mutated-output" / family.family_id
    negative = _measure(source, output_root, family, families, source)
    assert negative.unrun_checks == []
    generated_client = (
        output_root / "packages/runtime-api-client/canonicalRuntimeApiClient.ts"
    ).read_text(encoding="utf-8")
    assert "export class RuntimeApiClient" in generated_client
    assert "getRunHumanDecisionEvidenceContent" not in generated_client
    package = json.loads(
        (source / "packages/runtime-api-client/package.json").read_text(encoding="utf-8")
    )
    assert package["exports"]["."]["import"] == "./canonicalRuntimeApiClient.js"
    assert package["exports"]["."]["types"] == "./canonicalRuntimeApiClient.ts"

    assert {violation.detail for violation in negative.violations} == {
        "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
        "packages/runtime-api-client/canonicalRuntimeApiClient.js",
    }
