"""Byte-exact, source-free replay for persisted N6 history."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import time
import zipfile
from collections.abc import Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any, Literal

import pytest
from pydantic import BaseModel

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.foundry.methods.selection import MethodSelectionReceipt
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import generation_cycle as generation
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionActionRecord,
    AcquisitionStrategy,
)
from polisyos.runtime.quality.design_problem import (
    CandidateLever,
    DesignProblem,
)
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleRun,
    StrangleReceipt,
    validate_generation_cycle_run,
    validate_generation_cycle_run_history,
)
from tests.unit.runtime.quality.historical_artifacts import (
    GENERATION_CYCLE_V1_BLOB,
    historical_generation_cycle_v1,
    historical_owner_bytes,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
N6_SCHEMA_PREFIX = "policyos.runtime.generation_cycle_controller."


def _n6_runs(
    value: object, *, path: str, pointer: str = "$"
) -> list[tuple[str, str, dict[str, Any]]]:
    """Enumerate every N6 run object in one decoded committed document."""

    rows: list[tuple[str, str, dict[str, Any]]] = []
    if isinstance(value, dict):
        version = value.get("schema_version")
        if isinstance(version, str) and version.startswith(N6_SCHEMA_PREFIX):
            rows.append((path, pointer, value))
        for key, child in value.items():
            rows.extend(_n6_runs(child, path=path, pointer=f"{pointer}/{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_n6_runs(child, path=path, pointer=f"{pointer}/{index}"))
    return rows


def test_source_free_package_replays_n6_v1_v2_v3_with_semantic_mutation(
    tmp_path: Path,
    record_property: Any,
) -> None:
    """Replay pinned histories from an actual wheel without checkout imports."""

    v1 = historical_generation_cycle_v1()["generation_cycle_run"]
    v2_path = (
        REPO_ROOT
        / "architecture/policy_design_case/layer3_gy_generation_cycle_contract.json"
    )
    v2_document = json.loads(v2_path.read_text(encoding="utf-8"))
    v2 = v2_document["generation_cycle_run"]
    v3 = [payload for _name, payload in _v3_history_fixtures()]
    fixtures = {"v1": [v1], "v2": [v2], "v3": v3}

    uv_executable = shutil.which("uv")
    assert uv_executable is not None, "uv is required to build the local wheel offline"
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    build_environment = os.environ.copy()
    build_environment["UV_OFFLINE"] = "1"
    build_environment["UV_PYTHON_DOWNLOADS"] = "never"
    started = time.monotonic()
    build_result = subprocess.run(
        [
            uv_executable,
            "--offline",
            "build",
            "--wheel",
            "--out-dir",
            str(wheelhouse),
        ],
        cwd=REPO_ROOT,
        env=build_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    record_property("wheel_build_wall_seconds", round(time.monotonic() - started, 3))
    record_property(
        "wheel_build_command",
        "uv --offline build --wheel --out-dir <pytest-tmp>/wheelhouse",
    )
    assert build_result.returncode == 0, (
        build_result.stdout + "\n" + build_result.stderr
    )
    wheels = tuple(sorted(wheelhouse.glob("*.whl")))
    assert len(wheels) == 1, f"expected one wheel, found {len(wheels)}"
    wheel_path = wheels[0]
    registry_member = (
        "polisyos/foundry/methods/catalog/_resources/"
        "method_catalog_dependency_digest_domains.toml"
    )
    snapshot_member = "polisyos/foundry/methods/catalog/snapshot.py"
    canonical_registry = (
        REPO_ROOT
        / "architecture/production_quality"
        / "method_catalog_dependency_digest_domains.toml"
    ).read_bytes()
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    with zipfile.ZipFile(wheel_path) as archive:
        members = tuple(archive.namelist())
        assert members.count(registry_member) == 1
        assert not any("layer3_gx_pinned_request.json" in member for member in members)
        assert snapshot_member in members
        wheel_registry = archive.read(registry_member)
        assert wheel_registry == canonical_registry
        python_module_count = sum(
            member.startswith("polisyos/") and member.endswith(".py")
            for member in members
        )
        assert python_module_count >= 1
        archive.extractall(site_packages)
    with wheel_path.open("rb") as wheel_file:
        wheel_sha256 = hashlib.file_digest(wheel_file, "sha256").hexdigest()
    record_property("built_wheel_sha256", wheel_sha256)
    record_property("wheel_python_module_count", python_module_count)
    record_property(
        "wheel_registry_sha256", hashlib.sha256(wheel_registry).hexdigest()
    )

    unrelated_source = site_packages / "polisyos/lex/simulator/report.py"
    assert unrelated_source.is_file()
    unrelated_source.write_bytes(
        unrelated_source.read_bytes()
        + b"\n# unrelated edit must not stale old history\n"
    )
    decoy_registry = (
        tmp_path
        / "architecture/production_quality"
        / "method_catalog_dependency_digest_domains.toml"
    )
    decoy_registry.parent.mkdir(parents=True, exist_ok=True)
    decoy_registry.write_text("not the packaged runtime registry\n", encoding="utf-8")

    outside = tmp_path / "outside"
    outside.mkdir()
    fixture_path = outside / "n6-history.json"
    fixture_path.write_text(json.dumps(fixtures), encoding="utf-8")
    configured_paths = sysconfig.get_paths()
    dependency_paths = tuple(
        dict.fromkeys(
            configured_paths[key]
            for key in ("purelib", "platlib")
            if Path(configured_paths[key]).is_dir()
        )
    )
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": os.pathsep.join((str(site_packages), *dependency_paths)),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "R2_PRODUCT_ROOT": str(REPO_ROOT.resolve()),
        "R2_SITE_PACKAGES": str(site_packages.resolve()),
        "R2_HISTORY_FIXTURES": str(fixture_path),
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "JAX_PLATFORMS": "cpu",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            """
import copy
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import polisyos
from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.foundry.methods.catalog import dependency_authority
from polisyos.runtime.quality.design_axes import value_choice_provenance
from polisyos.runtime.quality import generation_cycle
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleRun,
    validate_generation_cycle_run,
    validate_generation_cycle_run_history,
)

product_root = Path(os.environ["R2_PRODUCT_ROOT"]).resolve()
site_packages = Path(os.environ["R2_SITE_PACKAGES"]).resolve()
package_root = (site_packages / "polisyos").resolve()
assert Path(polisyos.__file__).resolve().parent == package_root
assert GenerationCycleRun.__module__ == "polisyos.runtime.quality.generation_cycle"
registry_path = Path(dependency_authority._DIGEST_REGISTRY_PATH).resolve()
expected_registry_path = (
    package_root
    / "foundry/methods/catalog/_resources"
    / "method_catalog_dependency_digest_domains.toml"
)
assert registry_path == expected_registry_path
assert registry_path.is_file()
for module_name, module in tuple(sys.modules.items()):
    if module_name == "polisyos" or module_name.startswith("polisyos."):
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        if origin and origin.endswith(".py"):
            assert Path(origin).resolve().is_relative_to(package_root), (
                module_name,
                origin,
            )
for entry in sys.path:
    if not entry:
        continue
    resolved = Path(entry).resolve()
    assert not resolved.is_relative_to(product_root / "src"), entry
    assert not resolved.is_relative_to(product_root / "tests"), entry
    assert not resolved.is_relative_to(product_root / "architecture"), entry

fixture_path = Path(os.environ["R2_HISTORY_FIXTURES"])
fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
expected = {"v1": ".v1", "v2": ".v2", "v3": ".v3"}
spec = CanonSpec(forbid_floats=False)
replayed_count = 0
for label, records in fixtures.items():
    assert records and label in expected
    for payload in records:
        assert payload["schema_version"].endswith(expected[label])
        run = GenerationCycleRun.model_validate(payload)
        projection = generation_cycle._historical_generation_cycle_run_projection(run)
        assert (
            to_canonical_bytes(projection, spec)
            == to_canonical_bytes(payload, spec)
        ), label
        assert validate_generation_cycle_run_history(payload) == (), label
        replayed_count += 1

source = fixtures["v1"][0]
schema_version = source["schema_version"]
store = artifacts.FileSystemCAS(Path.cwd() / "s8-cas")
owner = value_choice_provenance.NormativeValueScheduleOwner(
    store=store,
    trust=value_choice_provenance.NormativeAuthorityTrust(),
    repo_root=None,
)
source_options = artifacts.PutOptions(
    kind=value_choice_provenance.NORMATIVE_GENERATION_SOURCE_KIND,
    media_type="application/json",
    schema=artifacts.SchemaInfo(
        name=value_choice_provenance.NORMATIVE_GENERATION_SOURCE_KIND,
        version=schema_version,
    ),
)
valid_source_ref = str(
    store.put_json(source, source_options, canon_spec=spec).artifact_id
)
assert owner._read(
    valid_source_ref,
    kind=value_choice_provenance.NORMATIVE_GENERATION_SOURCE_KIND,
    schema=generation_cycle.GENERATION_CYCLE_SCHEMA_VERSION,
) == source
canonical_source_bytes = store.get_bytes(valid_source_ref)
noncanonical_source_ref = str(
    store.put_bytes(canonical_source_bytes + b" \\n", source_options).artifact_id
)
assert from_canonical_bytes(store.get_bytes(noncanonical_source_ref)) == source
try:
    owner._read(
        noncanonical_source_ref,
        kind=value_choice_provenance.NORMATIVE_GENERATION_SOURCE_KIND,
        schema=generation_cycle.GENERATION_CYCLE_SCHEMA_VERSION,
    )
except value_choice_provenance.P20NormativeChoiceError as exc:
    assert exc.code == "p20_normative_generation_history_invalid"
else:
    raise AssertionError("S8 accepted noncanonical raw N6 source bytes")
source_run = GenerationCycleRun.model_validate(source)
strict_issues = validate_generation_cycle_run(source_run)
assert len(strict_issues) == 1
assert strict_issues[0]["code"] == "strangle_receipt_currentness_not_established"
assert strict_issues[0]["reason"] == "historical_deployment_identity_not_recorded"
assert strict_issues[0]["census_verdict"] == "UNRUN"
binding = value_choice_provenance.NormativeGenerationBinding(
    compiled_run_ref="sha256:" + "a" * 64,
    source_run_ref=valid_source_ref,
    node_ref="fixture:n6-leaf",
)
disposition = owner._generation_disposition(
    binding=binding,
    evidence=None,
    evaluated_at=datetime.now(UTC),
)
expected_reasons = (
    "strangle_receipt_currentness_not_established",
    "historical_deployment_identity_not_recorded",
    "generation_cycle_source_preservation_not_established",
    "historical_v1_source_custody_not_represented",
)
assert disposition.authorization_status == "blocked"
assert disposition.ranked_recommendations == ()
assert disposition.ranking_bundle_ref is None
assert disposition.decision_request is not None
assert disposition.decision_request.reason_codes == expected_reasons
assert disposition.candidate_fronts == source_run.fronts.candidate_ids_by_front()
assert any(disposition.candidate_fronts.values())
assert disposition.compiled_membership_status == "not_established"

mutated_v1 = copy.deepcopy(source)
mutated_v1["source_handoff_refs"] = []
assert GenerationCycleRun.model_validate(mutated_v1).model_dump(mode="json") == source
invalid_source_ref = str(
    store.put_json(mutated_v1, source_options, canon_spec=spec).artifact_id
)
invalid_binding = binding.model_copy(update={"source_run_ref": invalid_source_ref})
try:
    owner._generation_disposition(
        binding=invalid_binding,
        evidence=None,
        evaluated_at=datetime.now(UTC),
    )
except value_choice_provenance.P20NormativeChoiceError as exc:
    assert exc.code == "p20_normative_generation_history_invalid"
else:
    raise AssertionError("S8 accepted post-v1 persisted content after markers stayed intact")

original = fixtures["v3"][0]
mutated = copy.deepcopy(original)
retained_run_id = mutated["run_id"]
retained_receipt = copy.deepcopy(mutated["strangle_receipt"])
mutated["cycles"][-1]["refinement_decision"]["decision"] = "stop"
assert mutated["run_id"] == retained_run_id
assert mutated["strangle_receipt"] == retained_receipt
issues = validate_generation_cycle_run_history(mutated)
assert "generation_cycle_blocked_terminal_projection_mismatch" in {
    issue.get("code") for issue in issues
}
print(
    f"source_free_n6_history=v1,v2,v3 replayed={replayed_count} "
    "s8_raw_v1=red_currentness=limited unrelated_comment=valid"
)
""",
        ],
        cwd=outside,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "source_free_n6_history=v1,v2,v3 replayed=4 "
        "s8_raw_v1=red_currentness=limited unrelated_comment=valid"
    )

    # Remove the import-boundary property while retaining every exported symbol.
    # Both former module-scope GX reads must make an otherwise valid wheel import
    # fail when the repository's pinned-case fixture is absent.
    eager_reads = (
        (
            "runtime/quality/construct_registry.py",
            "REPO_ROOT = Path(__file__).resolve().parents[4]\n",
            "PINNED_CASE_ID = read_layer3_gx_pinned_case_id(REPO_ROOT)\n",
        ),
        (
            "runtime/quality/design_axes/substrate_acquisition.py",
            "REPO_ROOT = Path(__file__).resolve().parents[5]\n",
            "S3_PINNED_CASE_ID = read_layer3_gx_pinned_case_id(REPO_ROOT)\n",
        ),
    )
    for relative_path, anchor, eager_read in eager_reads:
        module_path = site_packages / "polisyos" / relative_path
        original = module_path.read_text(encoding="utf-8")
        assert original.count(anchor) == 1
        assert eager_read not in original
        try:
            module_path.write_text(
                original.replace(anchor, anchor + eager_read, 1),
                encoding="utf-8",
            )
            negative = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    "-c",
                    "from polisyos.runtime.quality import generation_cycle",
                ],
                cwd=outside,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
            assert negative.returncode != 0, relative_path
            expected_request = (
                tmp_path
                / "architecture/policy_design_case/layer3_gx_pinned_request.json"
            )
            assert "FileNotFoundError" in negative.stderr
            assert str(expected_request) in negative.stderr
            assert module_path.name in negative.stderr
        finally:
            module_path.write_text(original, encoding="utf-8")


def _v3_history_fixtures() -> tuple[tuple[str, dict[str, Any]], ...]:
    """Read two SHA-pinned v3 records captured before the schema bump."""

    fixtures = (
        (
            "generation_cycle_controller_v3.json.fixture",
            "dba1d1ff6598ac7c7705e2d46fc085e42e6d1f4651e14ab5c16af57f848ea02c",
        ),
        (
            "generation_cycle_controller_v3_identity.json.fixture",
            "0c8027f56795dc40ccf263b82ef261f645397bb69c2c2a49b23bd8197f570d20",
        ),
    )
    rows: list[tuple[str, dict[str, Any]]] = []
    for fixture_name, expected_sha256 in fixtures:
        fixture_path = Path(__file__).parent / "fixtures" / fixture_name
        raw_fixture = fixture_path.read_bytes()
        assert hashlib.sha256(raw_fixture).hexdigest() == expected_sha256
        rows.append((fixture_name, canon.from_canonical_bytes(raw_fixture)))
    return tuple(rows)


@cache
def _tracked_n6_runs() -> tuple[int, list[tuple[str, str, dict[str, Any]]]]:
    """Walk all tracked JSON/JSONL files and add the pinned Git-history fixture."""

    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.json", "*.jsonl"],
        cwd=REPO_ROOT.parent,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    paths = tuple(path for path in listed.split("\0") if path)
    assert "policy-engine/.vscode/settings.json" in paths
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for relative in paths:
        path = REPO_ROOT.parent / relative
        source = path.read_text(encoding="utf-8")
        documents = (
            [json.loads(line) for line in source.splitlines() if line.strip()]
            if path.suffix == ".jsonl"
            else [json.loads(source)]
        )
        for index, document in enumerate(documents):
            pointer = f"$line{index + 1}" if path.suffix == ".jsonl" else "$"
            rows.extend(_n6_runs(document, path=relative, pointer=pointer))

    pinned_raw = historical_owner_bytes(GENERATION_CYCLE_V1_BLOB)
    pinned_document = historical_generation_cycle_v1()
    assert json.loads(pinned_raw) == pinned_document
    pinned_run = pinned_document["generation_cycle_run"]
    rows.append((
        f"git-blob:{GENERATION_CYCLE_V1_BLOB}",
        "$/generation_cycle_run",
        pinned_run,
    ))
    for fixture_name, fixture in _v3_history_fixtures():
        fixture_path = Path(__file__).parent / "fixtures" / fixture_name
        rows.append((
            f"historical-fixture:{fixture_path.relative_to(REPO_ROOT.parent)}",
            "$",
            fixture,
        ))
    return len(paths), rows


def _nested_models(value: object, model_type: type[BaseModel]) -> list[BaseModel]:
    """Find instances of one typed owner under a persisted model graph."""

    found: list[BaseModel] = []
    seen: set[int] = set()

    def visit(node: object) -> None:
        identity = id(node)
        if identity in seen:
            return
        if isinstance(node, (BaseModel, Mapping, tuple, list)):
            seen.add(identity)
        if isinstance(node, model_type):
            found.append(node)
        if isinstance(node, BaseModel):
            for field_name in type(node).model_fields:
                visit(getattr(node, field_name))
        elif isinstance(node, Mapping):
            for child in node.values():
                visit(child)
        elif isinstance(node, (tuple, list)):
            for child in node:
                visit(child)

    visit(value)
    return found


def test_all_current_and_pinned_historical_n6_runs_replay_byte_exactly(
    record_property: Any,
) -> None:
    """Replay each enumerated persisted run through its own historical serializer."""

    tracked_file_count, occurrences = _tracked_n6_runs()
    versions: dict[str, int] = {}
    for _path, _pointer, payload in occurrences:
        version = str(payload["schema_version"])
        versions[version] = versions.get(version, 0) + 1

    # Record the complete tracked JSON/JSONL denominator; the set may grow.
    record_property("tracked_json_jsonl_file_count", tracked_file_count)
    assert tracked_file_count > 0
    assert versions.get("policyos.runtime.generation_cycle_controller.v1", 0) >= 10
    assert versions.get("policyos.runtime.generation_cycle_controller.v2", 0) >= 1
    assert versions.get("policyos.runtime.generation_cycle_controller.v3", 0) >= 2
    v3_identity_statuses = {
        payload["deployment_identity_status"]
        for _path, _pointer, payload in occurrences
        if payload["schema_version"] == "policyos.runtime.generation_cycle_controller.v3"
    }
    assert v3_identity_statuses == {"established", "not_established"}
    assert sum(
        path == f"git-blob:{GENERATION_CYCLE_V1_BLOB}"
        for path, _pointer, _payload in occurrences
    ) == 1

    spec = canon.CanonSpec(forbid_floats=False)
    for path, pointer, payload in occurrences:
        run = GenerationCycleRun.model_validate(payload)
        live_projection = run.model_dump(mode="json")
        if run.schema_version.endswith(".v3"):
            # This patch must not change ordinary producer serialization.
            assert canon.to_canonical_bytes(live_projection, spec) == (
                canon.to_canonical_bytes(payload, spec)
            )
        replayed = generation._historical_generation_cycle_run_projection(run)
        persisted_bytes = canon.to_canonical_bytes(payload, spec)
        replayed_bytes = canon.to_canonical_bytes(replayed, spec)
        assert replayed_bytes == persisted_bytes, f"serializer drift at {path}{pointer}"
        assert gy_content_hash(replayed) == gy_content_hash(payload), (
            f"semantic identity drift at {path}{pointer}"
        )
        assert validate_generation_cycle_run_history(payload) == (), (
            f"historical semantic replay failed at {path}{pointer}"
        )


def test_v3_history_freeze_rejects_dotted_target_slot_while_markers_remain() -> None:
    """The v3 receipt keeps its original target grammar despite model_copy tampering."""

    fixture_name, payload = _v3_history_fixtures()[0]
    assert all(
        cycle["revision_request"]["revised_problem"]["schema_version"]
        == "policyos.runtime.design_problem.v1"
        for cycle in payload["cycles"]
    )
    run = GenerationCycleRun.model_validate(payload)

    def replace_target_slot(value: object) -> tuple[object, bool]:
        if isinstance(value, CandidateLever):
            return value.model_copy(update={"target_slot": "government.balance"}), True
        if isinstance(value, BaseModel):
            updates: dict[str, object] = {}
            for field_name in type(value).model_fields:
                replacement, changed = replace_target_slot(getattr(value, field_name))
                if changed:
                    updates[field_name] = replacement
                    break
            return (value.model_copy(update=updates), True) if updates else (value, False)
        if isinstance(value, (tuple, list)):
            items = list(value)
            for index, item in enumerate(items):
                replacement, changed = replace_target_slot(item)
                if changed:
                    items[index] = replacement
                    return (tuple(items) if isinstance(value, tuple) else items), True
        return value, False

    forged, changed = replace_target_slot(run)
    assert changed, f"v3 fixture has no CandidateLever: {fixture_name}"
    assert isinstance(forged, GenerationCycleRun)
    assert forged.schema_version == run.schema_version
    assert forged.strangle_receipt.status == run.strangle_receipt.status
    with pytest.raises(
        ValueError, match="generation_cycle_history_field_pattern_out_of_epoch"
    ):
        generation._historical_generation_cycle_run_projection(forged)


def test_v3_history_accepts_nested_design_problem_v2_dotted_target_slot() -> None:
    """Outer N6 v3 may contain an R1 v2 problem using the canonical dotted slot."""

    _fixture_name, payload = _v3_history_fixtures()[0]
    for cycle in payload["cycles"]:
        problem = cycle["revision_request"]["revised_problem"]
        problem["schema_version"] = "policyos.runtime.design_problem.v2"
        problem["candidate_lever_space"]["candidate_levers"][0]["target_slot"] = (
            "government.balance"
        )

    run = GenerationCycleRun.model_validate(payload)
    assert run.schema_version == "policyos.runtime.generation_cycle_controller.v3"
    projection = generation._historical_generation_cycle_run_projection(run)
    for cycle in projection["cycles"]:
        problem = cycle["revision_request"]["revised_problem"]
        assert problem["schema_version"] == "policyos.runtime.design_problem.v2"
        assert (
            problem["candidate_lever_space"]["candidate_levers"][0]["target_slot"]
            == "government.balance"
        )


def test_v3_history_accepts_nested_design_problem_v3_qualified_outcome() -> None:
    """A new nested v3 problem replays with its exact qualified outcome owner."""

    _fixture_name, payload = _v3_history_fixtures()[0]
    for cycle in payload["cycles"]:
        problem = cycle["revision_request"]["revised_problem"]
        problem["schema_version"] = "policyos.runtime.design_problem.v3"
        problem["outcome_of_interest"]["target_variable"] = "government.balance"

    run = GenerationCycleRun.model_validate(payload)
    projection = generation._historical_generation_cycle_run_projection(run)
    spec = canon.CanonSpec(forbid_floats=False)
    assert canon.to_canonical_bytes(projection, spec) == canon.to_canonical_bytes(
        payload, spec
    )
    assert all(
        cycle["revision_request"]["revised_problem"]["outcome_of_interest"][
            "target_variable"
        ]
        == "government.balance"
        for cycle in projection["cycles"]
    )


@pytest.mark.parametrize(
    "schema_version",
    [
        "policyos.runtime.design_problem.v1",
        "policyos.runtime.design_problem.v2",
        "policyos.runtime.design_problem.v3",
    ],
)
def test_history_rejects_qualified_outcome_without_v3_nested_owner(
    schema_version: str,
) -> None:
    """A version marker alone cannot give the strict outcome owner v3 syntax."""

    _fixture_name, payload = _v3_history_fixtures()[0]
    run = GenerationCycleRun.model_validate(payload)

    def replace_old_outcome(value: object) -> tuple[object, bool]:
        if isinstance(value, DesignProblem):
            outcome = value.outcome_of_interest.model_copy(
                update={"target_variable": "government.balance"}
            )
            return (
                value.model_copy(
                    update={
                        "schema_version": schema_version,
                        "outcome_of_interest": outcome,
                    }
                ),
                True,
            )
        if isinstance(value, BaseModel):
            for field_name in type(value).model_fields:
                replacement, changed = replace_old_outcome(getattr(value, field_name))
                if changed:
                    return value.model_copy(update={field_name: replacement}), True
        if isinstance(value, (tuple, list)):
            items = list(value)
            for index, item in enumerate(items):
                replacement, changed = replace_old_outcome(item)
                if changed:
                    items[index] = replacement
                    return (tuple(items) if isinstance(value, tuple) else items), True
        return value, False

    forged, changed = replace_old_outcome(run)
    assert changed
    assert isinstance(forged, GenerationCycleRun)
    assert forged.schema_version == run.schema_version
    assert forged.strangle_receipt.status == run.strangle_receipt.status
    with pytest.raises(
        ValueError, match="generation_cycle_history_field_pattern_out_of_epoch"
    ):
        generation._historical_generation_cycle_run_projection(forged)


def test_v3_history_projects_n5_artifact_root_model_as_scalar_wire() -> None:
    """A valid N5 result ref replays through the frozen typed v3 graph."""

    artifact_id = ArtifactID.from_sha256_hex("a" * 64)
    observation = generation.SimulationPortObservation(
        candidate_id="candidate_a",
        status="joint_simulated",
        simulation_result_ref=ArtifactRef(
            artifact_id=artifact_id,
            kind="runtime_quality.simulation_result",
            media_type="application/json",
        ),
    )
    wire = observation.model_dump(mode="json", exclude_unset=True)
    assert wire["simulation_result_ref"]["artifact_id"] == str(artifact_id)

    projected = generation._historical_generation_cycle_field_tree(
        observation, wire, version="v3"
    )
    spec = canon.CanonSpec(forbid_floats=False)
    assert canon.to_canonical_bytes(projected, spec) == canon.to_canonical_bytes(
        wire, spec
    )

    malformed = copy.deepcopy(wire)
    malformed["simulation_result_ref"]["artifact_id"] = "sha256:broken"
    with pytest.raises(ValueError):
        generation.SimulationPortObservation.model_validate(malformed)

    noncanonical = copy.deepcopy(wire)
    noncanonical["simulation_result_ref"]["artifact_id"] = "sha256:" + "A" * 64
    normalized = generation.SimulationPortObservation.model_validate(noncanonical)
    with pytest.raises(ValueError, match="generation_cycle_history_root_wire_mismatch"):
        generation._historical_generation_cycle_field_tree(
            normalized, noncanonical, version="v3"
        )


def test_v3_blocked_terminal_semantics_remain_enforced_in_history() -> None:
    """Changing the persisted blocked terminal marker makes v3 history red."""

    for _fixture_name, original in _v3_history_fixtures():
        assert validate_generation_cycle_run_history(original) == ()
        forged = copy.deepcopy(original)
        forged["cycles"][-1]["refinement_decision"]["decision"] = "stop"
        issues = validate_generation_cycle_run_history(forged)
        assert "generation_cycle_blocked_terminal_projection_mismatch" in {
            issue.get("code") for issue in issues
        }


def test_v3_history_preserves_arbitrary_design_problem_schema_strings() -> None:
    """Historical replay preserves the v3 plain-string schema version contract."""

    _fixture_name, payload = _v3_history_fixtures()[0]
    forged = copy.deepcopy(payload)
    changed = False

    def change_nested_problem_version(value: object) -> None:
        nonlocal changed
        if isinstance(value, dict):
            if "problem_statement" in value and "candidate_lever_space" in value:
                value["schema_version"] = "historical_custom_schema_label"
                changed = True
                return
            for child in value.values():
                change_nested_problem_version(child)
        elif isinstance(value, list):
            for child in value:
                change_nested_problem_version(child)

    change_nested_problem_version(forged)
    assert changed
    assert validate_generation_cycle_run_history(forged) == ()


def test_frozen_vocabulary_and_wire_schema_cover_the_complete_model_graph() -> None:
    """Freeze aliases/Enums across every map class and exclude computed wire keys."""

    frozen = generation.FROZEN_N6_HISTORY_SCHEMA
    expected_field_counts = {"v1": 76, "v2": 82, "v3": 86}
    expected_model_counts = {"v1": 59, "v2": 60, "v3": 62}
    assert {version: len(models) for version, models in frozen.items()} == expected_model_counts
    for version, models in frozen.items():
        assert sum(
            len(shape["field_vocabulary"]) for shape in models.values()
        ) == expected_field_counts[version]
        assert all(
            not (set(shape["computed_fields"]) & set(shape["wire_fields"]))
            for shape in models.values()
        )
        for shape in models.values():
            for field_name, legacy_values in shape.get("literal_values", {}).items():
                literal_descriptors = [
                    descriptor
                    for descriptor in shape["field_vocabulary"].get(field_name, ())
                    if descriptor["kind"] == "literal"
                ]
                assert len(literal_descriptors) == 1
                frozen_values = {
                    value
                    for descriptor in literal_descriptors
                    for value in descriptor["values"]
                }
                assert frozen_values == set(legacy_values)
                if field_name in shape.get("nullable_literal_fields", ()):
                    assert any(
                        any(part.startswith("union:") for part in descriptor["path"])
                        for descriptor in literal_descriptors
                    )

    promotion_status = frozen["v2"][
        "polisyos.runtime.quality.generation_cycle.PromotionPortObservation"
    ]["field_vocabulary"]["status"]
    assert promotion_status == [{
        "kind": "literal",
        "path": [],
        "type": None,
        "values": [
            "certified_current_valid",
            "not_promoted",
            "promotion_pending_n9",
        ],
    }]
    strategies = frozen["v2"][
        "polisyos.runtime.quality.acquisition_planner.AcquisitionActionRecord"
    ]["field_vocabulary"]["eligible_strategies"]
    assert strategies[0]["kind"] == "enum"
    assert strategies[0]["type"] == (
        "polisyos.runtime.quality.acquisition_planner.AcquisitionStrategy"
    )


def test_v1_projection_removal_probe_rejects_post_v1_field_with_markers_retained() -> None:
    """Deleting serializer equality must make an empty post-v1 field pass incorrectly."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, payload = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v1"
    )
    mutated = copy.deepcopy(payload)
    # Empty semantic content does not excuse a field absent from the v1 projection.
    mutated["source_handoff_refs"] = []
    assert GenerationCycleRun.model_validate(mutated).model_dump(mode="json") == payload
    assert validate_generation_cycle_run_history(mutated) == (
        {"code": "generation_cycle_historical_projection_mismatch"},
    )


@pytest.mark.parametrize(
    ("path", "field", "value"),
    [
        (("candidate_summaries", 0), "grounding_issue_codes", []),
        (("cycles", 0), "design_problem_basis_ref", "sha256:" + "0" * 64),
        (
            ("cycles", 0, "simulation"),
            "simulation_result_ref",
            {
                "artifact_id": "sha256:" + "0" * 64,
                "kind": "runtime_quality.simulation_result",
                "media_type": "application/json",
            },
        ),
        (("strangle_receipt",), "source_file_count", 0),
    ],
)
def test_v2_history_rejects_post_version_nested_fields_with_markers_retained(
    path: tuple[str | int, ...], field: str, value: object
) -> None:
    """An old outer version cannot acquire a later nested field by supplying it."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, original = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v2"
    )
    assert validate_generation_cycle_run_history(original) == ()
    mutated = copy.deepcopy(original)
    target = mutated
    for component in path:
        target = target[component]
    target[field] = value
    assert mutated["schema_version"] == original["schema_version"]
    assert mutated["strangle_receipt"]["status"] == original["strangle_receipt"]["status"]
    assert validate_generation_cycle_run_history(mutated) == (
        {"code": "generation_cycle_historical_projection_mismatch"},
    )


def test_history_replay_is_read_only_and_does_not_consult_current_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Historical replay has no writer capability and no live-source dependency."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, payload = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v1"
    )

    def source_probe_must_not_run(
        self: StrangleReceipt, repo_root: Path | None = None
    ) -> None:
        del self, repo_root
        raise AssertionError("historical_replay_consulted_live_source")

    monkeypatch.setattr(
        generation.FileSystemCAS,
        "put_json",
        lambda *_args, **_kwargs: pytest.fail("history replay wrote an artifact"),
    )
    monkeypatch.setattr(
        generation.FileSystemCAS,
        "put_bytes",
        lambda *_args, **_kwargs: pytest.fail("history replay wrote artifact bytes"),
    )
    before = canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
    current_validator = generation._validate_generation_cycle_run

    def require_history_mode(
        run: object, **kwargs: object
    ) -> tuple[dict[str, Any], ...]:
        assert kwargs.get("repo_root") is None
        assert kwargs.get("current_strangle_receipt") is None
        assert kwargs.get("require_currentness") is False
        return current_validator(run, **kwargs)

    with monkeypatch.context() as history_only:
        history_only.setattr(
            StrangleReceipt, "verify_current", source_probe_must_not_run
        )
        history_only.setattr(
            generation, "_validate_generation_cycle_run", require_history_mode
        )
        assert validate_generation_cycle_run_history(payload) == ()
    after = canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
    assert before == after
    assert "strangle_receipt_currentness_not_established" in {
        str(issue.get("code")) for issue in validate_generation_cycle_run(payload)
    }


@pytest.mark.parametrize(
    ("path", "field", "value"),
    [
        (("strangle_receipt",), "status", "not_established"),
        (("cycles", 0, "search_iteration"), "status", "stopped"),
        (("candidate_summaries", 0), "value_status", "value_conditional"),
        (("cycles", 0, "refinement_decision"), "decision", "stop"),
    ],
)
def test_v1_v2_history_rejects_current_only_literal_or_alias_values(
    path: tuple[str | int, ...], field: str, value: object
) -> None:
    """Current direct and aliased Literal additions do not enter old history."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, original = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v2"
    )
    candidate = copy.deepcopy(original)
    target = candidate
    for component in path:
        target = target[component]
    target[field] = value
    # Current DTO validation accepts both newer vocabulary members; historical
    # replay must still reject them under the v1/v2 field map.
    GenerationCycleRun.model_validate(candidate)
    issues = validate_generation_cycle_run_history(candidate)
    assert issues
    assert issues[0]["code"] in {
        "generation_cycle_historical_projection_invalid",
        "generation_cycle_historical_projection_mismatch",
    }



def test_v2_nested_future_enum_strategy_is_rejected_by_historical_projection() -> None:
    """A typed acquisition enum cannot gain a value while old markers remain."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, original = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v2"
    )
    run = GenerationCycleRun.model_validate(original)
    actions = _nested_models(run, AcquisitionActionRecord)
    assert actions, "the persisted v2 run must exercise the acquisition action owner"
    action = actions[0]
    assert "eligible_strategies" in action.model_fields_set
    raw_action = action.model_dump(mode="json")
    assert raw_action["schema_version"] == action.schema_version
    assert raw_action["status"] == action.status

    future_strategy = str.__new__(AcquisitionStrategy, "r2_future_strategy")
    future_strategy._name_ = "R2_FUTURE_STRATEGY"
    future_strategy._value_ = "r2_future_strategy"
    mutated_action = action.model_copy(
        update={
            "eligible_strategies": (
                *action.eligible_strategies,
                future_strategy,
            )
        }
    )
    mutated_payload = copy.deepcopy(raw_action)
    mutated_payload["eligible_strategies"].append("r2_future_strategy")

    with pytest.raises(
        ValueError, match="generation_cycle_history_vocabulary_out_of_epoch"
    ):
        generation._historical_generation_cycle_field_tree(
            mutated_action, mutated_payload, version="v2"
        )


def test_historical_vocabulary_guard_uses_reflected_mapping_and_sequence_paths() -> None:
    """Finite vocabularies remain correct below Mapping and Sequence containers."""

    enum_owner = (
        f"{AcquisitionStrategy.__module__}.{AcquisitionStrategy.__qualname__}"
    )
    future_strategy = str.__new__(AcquisitionStrategy, "r2_future_strategy")
    future_strategy._name_ = "R2_FUTURE_STRATEGY"
    future_strategy._value_ = "r2_future_strategy"
    cases = (
        (
            Mapping[str, Literal["old", "current"]],
            {"Mapping:1"},
            {"scope": "old"},
            {"scope": "future"},
        ),
        (
            Sequence[Literal["old", "current"]],
            {"Sequence:0"},
            ("old",),
            ("future",),
        ),
        (
            Mapping[str, AcquisitionStrategy],
            {"Mapping:1"},
            {"strategy": AcquisitionStrategy.PUBLIC_REGISTRY},
            {"strategy": future_strategy},
        ),
    )
    for annotation, expected_paths, accepted, rejected in cases:
        reflected = generation._historical_annotation_vocabularies(annotation)
        assert {"/".join(path) for path, _kind, _owner, _values in reflected} == (
            expected_paths
        )
        frozen = {
            (path, kind, owner): set(values)
            for path, kind, owner, values in reflected
        }
        assert frozen
        assert generation._historical_value_matches_vocabulary(
            annotation, accepted, frozen
        )
        assert not generation._historical_value_matches_vocabulary(
            annotation, rejected, frozen
        )
    assert enum_owner in {owner for _path, _kind, owner, _values in reflected}

def test_currentness_unknown_preserves_the_saved_historical_status() -> None:
    """Currentness is a separate observation and never rewrites saved history."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, original = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v2"
    )
    before = canon.to_canonical_bytes(original, canon.CanonSpec(forbid_floats=False))
    assert original["strangle_receipt"]["status"] == "strangled"
    assert validate_generation_cycle_run_history(original) == ()
    assert "strangle_receipt_currentness_not_established" in {
        str(issue.get("code")) for issue in validate_generation_cycle_run(original)
    }
    after = canon.to_canonical_bytes(original, canon.CanonSpec(forbid_floats=False))
    assert before == after
    assert original["strangle_receipt"]["status"] == "strangled"


def test_all_method_selection_receipts_in_n6_history_replay() -> None:
    """Every embedded method-selection receipt passes its current owner validator."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    raw_receipts: list[dict[str, Any]] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            if value.get("schema_version") == "policyos.foundry.method_selection_receipt.v2":
                raw_receipts.append(value)
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    for _path, _pointer, payload in occurrences:
        collect(payload)
    assert len(raw_receipts) == 6
    spec = canon.CanonSpec(forbid_floats=False)
    for raw in raw_receipts:
        receipt = MethodSelectionReceipt.model_validate(raw)
        assert canon.to_canonical_bytes(receipt.model_dump(mode="json"), spec) == (
            canon.to_canonical_bytes(raw, spec)
        )


@pytest.mark.parametrize("schema_suffix", [".v1", ".v2"])
def test_source_comment_preserves_actual_v1_v2_history(
    tmp_path: Path, schema_suffix: str
) -> None:
    """Comment edits alter neither census semantics nor source-free history."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, original = next(
        row for row in occurrences
        if row[2]["schema_version"].endswith(schema_suffix)
    )
    source = tmp_path / "src/polisyos/lex/simulator/report.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"def unrelated_report():\n    return 'unchanged'\n")

    before = canon.to_canonical_bytes(
        original, canon.CanonSpec(forbid_floats=False)
    )
    census_before = generation.inspect_n6_source_census(tmp_path)
    assert census_before.source_verdict == "UNRUN"
    assert "n6_production_entrypoint_and_binding_denominator_not_established" in (
        census_before.unresolved_by_construction
    )
    assert validate_generation_cycle_run_history(original) == ()
    current_before = generation.currentness_for_generation_cycle_run(original)
    assert current_before.status == "not_established"
    assert current_before.reason_code == "historical_deployment_identity_not_recorded"

    source.write_bytes(
        b"def unrelated_report():\n    return 'unchanged'\n# unrelated source comment\n"
    )
    census_after = generation.inspect_n6_source_census(tmp_path)
    assert census_after.source_verdict == "UNRUN"
    assert "n6_production_entrypoint_and_binding_denominator_not_established" in (
        census_after.unresolved_by_construction
    )
    assert census_after.semantic_census_sha256 == census_before.semantic_census_sha256
    assert census_after.inputs["source_bytes_sha256"] != census_before.inputs["source_bytes_sha256"]
    assert census_after.source_path_set_sha256 == census_before.source_path_set_sha256
    current_after = generation.currentness_for_generation_cycle_run(original)
    assert current_after.status == "not_established"
    assert current_after.reason_code == "historical_deployment_identity_not_recorded"
    assert validate_generation_cycle_run_history(original) == ()
    after = canon.to_canonical_bytes(
        original, canon.CanonSpec(forbid_floats=False)
    )
    assert after == before


def test_currentness_uses_ledger_observation_without_source_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Currentness is a typed owner question; the historical bytes stay replayable."""

    fixtures = dict(_v3_history_fixtures())
    payload = fixtures["generation_cycle_controller_v3_identity.json.fixture"]
    run = GenerationCycleRun.model_validate(payload)
    from polisyos.runtime.quality.confidence_ledger import (
        capture_loaded_deployment_identity,
    )

    loaded_identity = capture_loaded_deployment_identity()
    assert loaded_identity.status == "established"
    run = run.model_copy(
        update={
            "deployment_identity_status": "established",
            "deployment_identity": loaded_identity.deployment_identity,
            "deployment_identity_reason": None,
        }
    )

    def source_scan_must_not_run(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("runtime_currentness_rehashed_source_tree")

    monkeypatch.setattr(StrangleReceipt, "recompute", source_scan_must_not_run)
    monkeypatch.setattr(StrangleReceipt, "verify_current", source_scan_must_not_run)

    currentness = generation.currentness_for_generation_cycle_run(run)
    assert currentness.status == "not_established"
    assert currentness.census_verdict == "UNRUN"
    assert currentness.reason_code == "n6_census_issuer_not_appointed"
    assert validate_generation_cycle_run_history(payload) == ()
    assert "strangle_receipt_currentness_not_established" in {
        str(issue.get("code"))
        for issue in validate_generation_cycle_run(run)
    }

    stale = run.model_copy(
        update={"deployment_identity": "policy-engine-deployment:sha256:" + "0" * 64}
    )
    stale_observation = generation.currentness_for_generation_cycle_run(stale)
    assert stale_observation.status == "stale"
    assert stale_observation.reason_code == "generation_cycle_deployment_identity_mismatch"


def test_source_census_records_observations_but_holds_production_verdict_unrun(tmp_path: Path) -> None:
    """Direct references are observed while source-root completeness stays unclaimed."""

    source = tmp_path / "src/polisyos/runtime/quality/cycle.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def cycle():\n    return None\n# direct_ast_symbol_census_v1\n",
        encoding="utf-8",
    )
    clean = generation.inspect_n6_source_census(tmp_path)
    assert clean.source_verdict == "UNRUN"
    assert clean.schema_version == "policyos.runtime.generation_cycle.n6_source_census.v4"
    assert clean.census_rule == "n6_direct_reference_observation_v4"
    assert clean.source_path_count == 1
    assert clean.source_path_enumeration_complete is True
    assert clean.source_path_pattern == "src/polisyos/**/*.py"
    assert clean.production_path_verdict == "UNRUN"
    assert clean.production_root_and_binding_denominator == "not_established"
    assert {
        "n6_production_entrypoint_and_binding_denominator_not_established",
        "n6_module_and_class_attribute_rebinding_not_reconciled",
        "n6_direct_call_observations_not_reachability_proof",
    }.issubset(clean.unresolved_by_construction)
    assert clean.authority_currentness == "UNRUN"
    assert clean.canonical_identity_binding == "not_established"
    assert clean.inputs["read_inputs"] == (
        "UTF-8 byte reads and AST parse attempts for every enumerated Python source path"
    )
    assert clean.inputs["source_bytes_sha256"] != "UNRUN"

    fixture_owner = tmp_path / "src/polisyos/runtime/quality/workspace/loop.py"
    fixture_owner.parent.mkdir(parents=True)
    fixture_owner.write_text(
        "class WorkspaceLoop:\n"
        "    def run_fixture(self):\n        return None\n"
        "    def decompose_fixture(self):\n"
        "        return self.run_fixture()\n"
        "    def run_control_plane_fixture(self):\n"
        "        return self.run_fixture()\n",
        encoding="utf-8",
    )
    owner_control = generation.inspect_n6_source_census(tmp_path)
    assert owner_control.source_verdict == "UNRUN"
    assert owner_control.source_path_count == 2
    assert "allowed_fixture_reachability_not_established" in (
        owner_control.unresolved_by_construction
    )
    assert "dynamic_attribute_dispatch" not in owner_control.unresolved_by_construction

    fixture_owner.write_text(
        "class WorkspaceLoop:\n"
        "    def run_fixture(self):\n        return None\n"
        "    def unclassified_fixture_dispatch(self):\n"
        "        return self.run_fixture()\n",
        encoding="utf-8",
    )
    unclassified_owner_call = generation.inspect_n6_source_census(tmp_path)
    assert unclassified_owner_call.source_verdict == "UNRUN"
    assert "dynamic_attribute_dispatch" in (
        unclassified_owner_call.unresolved_by_construction
    )

    source.write_text(
        "from polisyos.runtime.quality.workspace.loop import WorkspaceLoop as CycleOwner\n"
        "def cycle():\n"
        "    runner = CycleOwner.run_fixture\n"
        "    return runner(None)\n",
        encoding="utf-8",
    )
    aliased_method = generation.inspect_n6_source_census(tmp_path)
    assert aliased_method.source_verdict == "UNRUN"
    assert "non_call_fixture_reference" in aliased_method.unresolved_by_construction

    source.write_text(
        "from polisyos.runtime.quality.workspace.loop import WorkspaceLoop as CycleOwner\n"
        "def cycle(owner):\n    return CycleOwner.run_fixture(owner)\n"
        "# direct_ast_symbol_census_v1\n",
        encoding="utf-8",
    )
    alias = generation.inspect_n6_source_census(tmp_path)
    assert alias.source_verdict == "UNRUN"
    assert alias.observed_direct_calls == ("src/polisyos/runtime/quality/cycle.py:3",)

    source.write_text(
        "from polisyos.runtime.quality.workspace.loop import WorkspaceLoop\n"
        "def cycle(owner):\n    return WorkspaceLoop.run_fixture(owner)\n",
        encoding="utf-8",
    )
    direct = generation.inspect_n6_source_census(tmp_path)
    assert direct.source_verdict == "UNRUN"
    assert direct.observed_direct_calls == ("src/polisyos/runtime/quality/cycle.py:3",)

    source.write_text(
        "class Unrelated:\n    def run_fixture(self):\n        return None\n"
        "def cycle(obj, name):\n    return getattr(obj, name)()\n",
        encoding="utf-8",
    )
    unresolved = generation.inspect_n6_source_census(tmp_path)
    assert unresolved.source_verdict == "UNRUN"
    assert "dynamic_attribute_dispatch" in unresolved.unresolved_by_construction
    assert unresolved.observed_direct_calls == ()

    source.write_text("def malformed(:\n    pass\n", encoding="utf-8")
    parse_error = generation.inspect_n6_source_census(tmp_path)
    assert parse_error.source_verdict == "UNRUN"
    assert parse_error.source_path_count == 2
    assert parse_error.source_path_enumeration_complete is True
    assert parse_error.unresolved_by_construction


def test_source_census_rebinding_falsifier_and_controls_keep_root_unrun(
    tmp_path: Path,
) -> None:
    """A marker-bearing method rebind cannot produce a production-root verdict."""

    source = tmp_path / "src/polisyos/runtime/quality/cycle.py"
    source.parent.mkdir(parents=True)
    markers = "\n# direct_ast_symbol_census_v1\n# generation_cycle_strangle_gate\n"
    rebound = (
        "from polisyos.runtime.quality.workspace.loop import WorkspaceLoop as CycleOwner\n"
        "\n"
        "def unsafe_helper(owner):\n"
        "    return CycleOwner.run_fixture(owner)\n"
        "\n"
        "class GenerationCycleController:\n"
        "    def run(self, owner):\n"
        "        return None\n"
        "\n"
        "GenerationCycleController.run = unsafe_helper\n"
        + markers
    )
    source.write_text(rebound, encoding="utf-8")

    falsifier = generation.inspect_n6_source_census(tmp_path)
    assert falsifier.source_verdict == "UNRUN"
    assert falsifier.source_path_enumeration_complete is True
    assert falsifier.production_path_verdict == "UNRUN"
    assert falsifier.production_root_and_binding_denominator == "not_established"
    assert falsifier.observed_direct_calls == (
        "src/polisyos/runtime/quality/cycle.py:4",
    )
    assert "n6_module_and_class_attribute_rebinding_not_reconciled" in (
        falsifier.unresolved_by_construction
    )
    assert markers.strip() in source.read_text(encoding="utf-8")

    rebind_removed_control = rebound.replace(
        "GenerationCycleController.run = unsafe_helper\n",
        "",
    )
    source.write_text(rebind_removed_control, encoding="utf-8")
    rebind_removed = generation.inspect_n6_source_census(tmp_path)
    assert rebind_removed.source_verdict == "UNRUN"
    assert rebind_removed.production_path_verdict == "UNRUN"
    assert rebind_removed.observed_direct_calls == falsifier.observed_direct_calls
    assert markers.strip() in source.read_text(encoding="utf-8")

    safe_control = (
        "class GenerationCycleController:\n"
        "    def run(self, owner):\n"
        "        return None\n"
        + markers
    )
    source.write_text(safe_control, encoding="utf-8")
    control = generation.inspect_n6_source_census(tmp_path)
    assert control.source_verdict == "UNRUN"
    assert control.source_path_enumeration_complete is True
    assert control.production_path_verdict == "UNRUN"
    assert control.production_root_and_binding_denominator == "not_established"
    assert control.observed_direct_calls == ()
    assert "n6_production_entrypoint_and_binding_denominator_not_established" in (
        control.unresolved_by_construction
    )
    assert markers.strip() in source.read_text(encoding="utf-8")


def test_source_census_scan_time_directory_error_marks_denominator_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A suppressed directory enumeration error cannot leave a partial green set."""

    source_root = tmp_path / "src/polisyos"
    blocked = source_root / "nested"
    blocked.mkdir(parents=True)
    (blocked / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    complete = generation.inspect_n6_source_census(tmp_path)
    assert complete.source_path_enumeration_complete is True
    assert complete.source_path_count == 1

    real_scandir = os.scandir

    def fail_nested_listing(path):
        if Path(path) == blocked:
            raise PermissionError("synthetic scan-time denial")
        return real_scandir(path)

    with monkeypatch.context() as scoped:
        scoped.setattr(generation.os, "scandir", fail_nested_listing)
        incomplete = generation.inspect_n6_source_census(tmp_path)
    assert incomplete.source_verdict == "UNRUN"
    assert incomplete.source_path_enumeration_complete is False
    assert incomplete.source_path_count == 0
    assert "source_denominator_enumeration_failed" in (
        incomplete.unresolved_by_construction
    )


def test_candidate_census_removal_stays_unrun_and_unrelated_control(tmp_path: Path) -> None:
    """Removing a helper edge with markers intact cannot produce a green result."""

    source = tmp_path / "src/polisyos/runtime/quality/workspace/loop.py"
    source.parent.mkdir(parents=True)
    markers = "\n# direct_ast_symbol_census_v1\n# generation_cycle_strangle_gate\n"
    helper_call = "        return self.run_fixture()\n"
    helper_source = (
        "class WorkspaceLoop:\n"
        "    def run_fixture(self):\n        return None\n"
        "    def decompose_fixture(self):\n"
        + helper_call
        + "    def run(self):\n        return self.decompose_fixture()\n"
        + markers
    )
    source.write_text(helper_source, encoding="utf-8")

    recognized_helper_route = generation.inspect_n6_source_census(tmp_path)
    assert recognized_helper_route.source_verdict == "UNRUN"
    assert recognized_helper_route.observed_direct_calls == ()
    assert "allowed_fixture_reachability_not_established" in (
        recognized_helper_route.unresolved_by_construction
    )
    assert "n6_production_entrypoint_and_binding_denominator_not_established" in (
        recognized_helper_route.unresolved_by_construction
    )

    removed_helper_call = helper_source.replace(helper_call, "        return None\n", 1)
    source.write_text(removed_helper_call, encoding="utf-8")
    after_removal = generation.inspect_n6_source_census(tmp_path)
    assert after_removal.source_verdict == "UNRUN"
    assert after_removal.observed_direct_calls == ()
    assert "n6_production_entrypoint_and_binding_denominator_not_established" in (
        after_removal.unresolved_by_construction
    )
    assert "allowed_fixture_reachability_not_established" not in (
        after_removal.unresolved_by_construction
    )
    retained_source = source.read_text(encoding="utf-8")
    assert "def run_fixture(self)" in retained_source
    assert markers.strip() in retained_source
    assert "return self.run_fixture()" not in retained_source
    assert after_removal.source_path_enumeration_complete is True
    assert after_removal.authority_currentness == "UNRUN"

    unrelated = tmp_path / "src/polisyos/runtime/quality/fixture_control.py"
    unrelated.write_text(
        "class UnrelatedFixture:\n"
        "    def run_fixture(self):\n        return None\n"
        "def call_fixture(owner):\n    return owner.safe_fixture()\n"
        + markers,
        encoding="utf-8",
    )
    unrelated_control = generation.inspect_n6_source_census(tmp_path)
    assert unrelated_control.source_verdict == "UNRUN"
    assert unrelated_control.observed_direct_calls == ()
    assert "n6_production_entrypoint_and_binding_denominator_not_established" in (
        unrelated_control.unresolved_by_construction
    )
    assert unrelated_control.observed_direct_calls == ()
    assert unrelated_control.authority_currentness == "UNRUN"
