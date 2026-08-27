from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.foundry.methods.catalog.dependency_evidence import (
    DependencyEnvironmentMarkerStatement,
    DependencyProfileEnvironmentStatement,
    DigestDomain,
    canonical_json_bytes,
    domain_digest,
    record_ref,
)
from polisyos.foundry.methods.catalog.dependency_profile import (
    DependencyProfileEnvironmentReceipt,
)
from tools.quality.validation import check_layer3_gy_second_domain_pack as n10a
from tools.quality.validation import check_layer3_gy_value_gate_contract as n8
from tools.quality.validation import execute_gy_n12_artifact_transition as transition


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, stderr=subprocess.STDOUT
    ).strip()


def _init_repo(root: Path) -> tuple[str, str]:
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    (root / "uv.lock").write_text("fixture\n")
    registry = root / "architecture/generated_artifacts.toml"
    registry.parent.mkdir()
    registry.write_text("[generated_artifacts]\nversion = 1\nfamily = []\n")
    source = root / "src/polisyos/runtime/quality"
    source.mkdir(parents=True)
    (source / "owner.py").write_text("OWNER = True\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    base = _git(root, "rev-parse", "HEAD")
    (source / "owner.py").write_text("OWNER = False\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "source"], cwd=root, check=True)
    return base, _git(root, "rev-parse", "HEAD")


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _independent_receipt_sha256(payload: dict[str, object]) -> str:
    material = {key: value for key, value in payload.items() if key != "receipt_sha256"}
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _foundry_ref(domain: DigestDomain, label: str):
    return record_ref(
        domain,
        label.encode(),
        schema_version=f"polisyos.foundry.{domain.value}.v1",
    )


def _write_n8_environment_receipt(
    environment_root: Path,
    *,
    label: str = "fixture",
) -> DependencyProfileEnvironmentReceipt:
    stable_closure = domain_digest(DigestDomain.DEPENDENCY_CLOSURE, f"{label}:closure".encode())
    stable_content = domain_digest(
        DigestDomain.CONTENT_SET_STABLE,
        f"{label}:stable-content".encode(),
    )
    instance_content = domain_digest(
        DigestDomain.CONTENT_SET_INSTANCE,
        f"{label}:instance-content".encode(),
    )
    runtime_installation = _foundry_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION,
        f"{label}:runtime-installation",
    )
    runtime_verification = _foundry_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION,
        f"{label}:runtime-verification",
    )
    marker = DependencyEnvironmentMarkerStatement(
        schema_version="polisyos.foundry.dependency-environment-marker.v1",
        environment_creation_nonce=domain_digest(
            DigestDomain.ENVIRONMENT_INSTANCE,
            f"{label}:instance".encode(),
        ),
        stable_closure=stable_closure,
        source_authority_ref=_foundry_ref(
            DigestDomain.CANONICAL_SOURCE,
            f"{label}:source",
        ),
        python_runtime_ref=_foundry_ref(
            DigestDomain.TOOLCHAIN_RUNTIME,
            f"{label}:runtime",
        ),
        python_runtime_installation_ref=runtime_installation,
        observed_python_runtime_ref=_foundry_ref(
            DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED,
            f"{label}:runtime-observed",
        ),
        python_runtime_verification_ref=runtime_verification,
        uv_executable_ref=_foundry_ref(
            DigestDomain.TOOLCHAIN_EXECUTABLE,
            f"{label}:uv",
        ),
        derived_uv_argv=domain_digest(
            DigestDomain.DERIVED_UV_ARGV,
            f"{label}:uv-argv".encode(),
        ),
        instance_content_set=instance_content,
    )
    marker_raw = canonical_json_bytes(marker.model_dump(mode="json"))
    marker_ref = record_ref(
        DigestDomain.ENVIRONMENT_MARKER,
        marker_raw,
        schema_version=marker.schema_version,
    )
    marker_path = environment_root / ".polisyos-foundry-authority-v1" / "environment-marker.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_bytes(marker_raw)
    statement = DependencyProfileEnvironmentStatement(
        schema_version="polisyos.foundry.dependency-environment.v1",
        admission_ref=_foundry_ref(DigestDomain.PROFILE_ADMISSION, f"{label}:admission"),
        stable_closure=stable_closure,
        appointment_ref=_foundry_ref(
            DigestDomain.PRODUCTION_APPOINTMENT,
            f"{label}:appointment",
        ),
        sync_root_access_ref=_foundry_ref(
            DigestDomain.ROOT_ACCESS,
            f"{label}:root-access",
        ),
        sync_root_access_binding_ref=_foundry_ref(
            DigestDomain.SIGNED_RECORD_BINDING,
            f"{label}:root-access-binding",
        ),
        python_runtime_installation_ref=runtime_installation,
        python_runtime_verification_ref=runtime_verification,
        observed_distributions=(),
        stable_content_set=stable_content,
        instance_content_set=instance_content,
        marker_ref=marker_ref,
    )
    return DependencyProfileEnvironmentReceipt(
        receipt_ref=record_ref(
            DigestDomain.ENVIRONMENT_RECEIPT,
            canonical_json_bytes(statement.model_dump(mode="json")),
            schema_version=statement.schema_version,
        ),
        statement=statement,
        predicate_class="recomputed",
    )


def test_parser_exposes_exactly_the_five_declared_subcommands() -> None:
    parser = transition.build_parser()
    action = next(
        item for item in parser._actions if item.__class__.__name__ == "_SubParsersAction"
    )

    assert tuple(action.choices) == (
        "measure",
        "build-deployment-candidates",
        "declare",
        "apply",
        "readback",
    )


def test_measure_uses_complete_changed_set_and_exact_deployment_intersection(
    tmp_path: Path,
) -> None:
    base, freeze = _init_repo(tmp_path)
    report = transition.build_measurement(
        repo_root=tmp_path,
        implementation_base=base,
        source_freeze=freeze,
        deployment_paths=(Path("src/polisyos/runtime/quality/owner.py"),),
        tool_sources=(),
        potential_targets=(),
    )

    assert report["changed_paths"] == [
        {"path": "src/polisyos/runtime/quality/owner.py", "status": "M"}
    ]
    assert report["deployment_intersection"] == ["src/polisyos/runtime/quality/owner.py"]
    assert report["source_freeze"] == freeze
    assert report["source_tree"] == _git(tmp_path, "rev-parse", f"{freeze}^{{tree}}")
    assert transition.verify_receipt(report)


def test_measure_rejects_wrong_head_dirty_tree_and_non_ancestor(tmp_path: Path) -> None:
    base, freeze = _init_repo(tmp_path)
    (tmp_path / "dirty").write_text("dirty")
    with pytest.raises(ValueError, match="transition_worktree_not_clean"):
        transition.build_measurement(
            repo_root=tmp_path,
            implementation_base=base,
            source_freeze=freeze,
            deployment_paths=(),
            tool_sources=(),
            potential_targets=(),
        )
    (tmp_path / "dirty").unlink()
    with pytest.raises(ValueError, match="source_freeze_not_head"):
        transition.build_measurement(
            repo_root=tmp_path,
            implementation_base=base,
            source_freeze=base,
            deployment_paths=(),
            tool_sources=(),
            potential_targets=(),
        )


def test_measure_normalizes_git_root_paths_to_the_product_coordinate(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.invalid"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    product = tmp_path / "policy-engine"
    registry = product / "architecture/generated_artifacts.toml"
    registry.parent.mkdir(parents=True)
    registry.write_text("[generated_artifacts]\nversion = 1\nfamily = []\n")
    source = product / "src/polisyos/runtime/quality"
    source.mkdir(parents=True)
    (source / "owner.py").write_text("OWNER = True\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    base = _git(tmp_path, "rev-parse", "HEAD")
    (source / "owner.py").write_text("OWNER = False\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "source"], cwd=tmp_path, check=True)
    freeze = _git(tmp_path, "rev-parse", "HEAD")

    report = transition.build_measurement(
        repo_root=product,
        implementation_base=base,
        source_freeze=freeze,
        deployment_paths=(Path("src/polisyos/runtime/quality/owner.py"),),
        tool_sources=(),
        potential_targets=(),
    )

    assert report["changed_paths"] == [
        {"path": "src/polisyos/runtime/quality/owner.py", "status": "M"}
    ]
    assert report["deployment_intersection"] == ["src/polisyos/runtime/quality/owner.py"]


def test_declaration_refuses_unestablished_owner_predicate(tmp_path: Path) -> None:
    measurement = transition.with_receipt_hash(
        {
            "schema_version": transition.MEASUREMENT_SCHEMA,
            "source_freeze": "a" * 40,
            "source_tree": "b" * 40,
            "attached_branch": "codex/fixture",
            "protected_denominator_sha256": "sha256:" + "1" * 64,
            "owner_predicates": {
                "foundry_adjudication": "not_established",
                "writer_authority": "not_established",
            },
        }
    )
    candidate = transition.with_receipt_hash(
        {
            "schema_version": transition.CANDIDATE_SCHEMA,
            "measurement_sha256": measurement["receipt_sha256"],
            "rows": [],
        }
    )
    with pytest.raises(ValueError, match="foundry_adjudication_not_established"):
        transition.build_declaration(
            measurement=measurement,
            candidate_receipt=candidate,
            expected_branch="codex/fixture",
            expected_source_freeze="a" * 40,
            allowed_post_freeze_records=(Path("docs/journal.md"),),
        )


def test_apply_failure_after_first_replacement_restores_complete_denominator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    candidates = tmp_path / "candidates"
    state = tmp_path / "state"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=root, check=True)
    candidates.mkdir()
    (root / "one.txt").write_text("one-old")
    (root / "two.txt").write_text("two-old")
    (root / "protected.txt").write_text("protected")
    (candidates / "one.txt").write_text("one-new")
    (candidates / "two.txt").write_text("two-new")
    declaration = transition.with_receipt_hash(
        {
            "schema_version": transition.DECLARATION_SCHEMA,
            "targets": [
                {
                    "path": "one.txt",
                    "candidate_relative_path": "one.txt",
                    "candidate_sha256": _sha(candidates / "one.txt"),
                    "preimage": transition.path_state(root, Path("one.txt")),
                },
                {
                    "path": "two.txt",
                    "candidate_relative_path": "two.txt",
                    "candidate_sha256": _sha(candidates / "two.txt"),
                    "preimage": transition.path_state(root, Path("two.txt")),
                },
            ],
            "protected_paths": [transition.path_state(root, Path("protected.txt"))],
            "protected_denominator_sha256": transition.denominator_hash(
                [
                    transition.path_state(root, Path("one.txt")),
                    transition.path_state(root, Path("two.txt")),
                    transition.path_state(root, Path("protected.txt")),
                ]
            ),
            "owner_predicates": {
                "foundry_adjudication": "established",
                "owner_enforced_runtime_subtree_cutoff": "established",
                "writer_authority": "established",
            },
        }
    )
    replaced_paths: list[Path] = []
    real_replace = transition._atomic_replace

    def observed_replace(target: Path, payload: bytes) -> None:
        replaced_paths.append(target)
        real_replace(target, payload)

    monkeypatch.setattr(transition, "_atomic_replace", observed_replace)

    with pytest.raises(RuntimeError, match="injected_failure_after_replacement"):
        transition.apply_declaration(
            repo_root=root,
            declaration=declaration,
            candidate_dir=candidates,
            state_dir=state,
            writer_authority=transition._UNIT_TEST_WRITER_AUTHORITY,
            expected_branch="codex/fixture",
            expected_declaration_head="a" * 40,
            fault_after_replacements=1,
        )

    assert (root / "one.txt").read_text() == "one-old"
    assert (root / "two.txt").read_text() == "two-old"
    assert (root / "protected.txt").read_text() == "protected"
    assert replaced_paths == [
        root / "one.txt",
        root / "one.txt",
        root / "two.txt",
    ]
    assert (state / "armed.json").is_file()
    assert (state / "fallback.json").is_file()
    assert not (state / "final.json").exists()


def test_sigkill_after_first_replacement_is_recovered_by_a_new_process(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    candidates = tmp_path / "candidates"
    state = tmp_path / "state"
    root.mkdir()
    candidates.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
    (root / "one.txt").write_text("one-old")
    (root / "two.txt").write_text("two-old")
    (root / "protected.txt").write_text("protected")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    expected_head = _git(root, "rev-parse", "HEAD")
    (candidates / "one.txt").write_text("one-new")
    (candidates / "two.txt").write_text("two-new")
    declaration = transition.with_receipt_hash(
        {
            "schema_version": transition.DECLARATION_SCHEMA,
            "targets": [
                {
                    "path": "one.txt",
                    "candidate_relative_path": "one.txt",
                    "candidate_sha256": _sha(candidates / "one.txt"),
                    "preimage": transition.path_state(root, Path("one.txt")),
                },
                {
                    "path": "two.txt",
                    "candidate_relative_path": "two.txt",
                    "candidate_sha256": _sha(candidates / "two.txt"),
                    "preimage": transition.path_state(root, Path("two.txt")),
                },
            ],
            "protected_paths": [transition.path_state(root, Path("protected.txt"))],
            "protected_denominator_sha256": transition.denominator_hash(
                [
                    transition.path_state(root, Path("one.txt")),
                    transition.path_state(root, Path("two.txt")),
                    transition.path_state(root, Path("protected.txt")),
                ]
            ),
            "owner_predicates": {
                "foundry_adjudication": "established",
                "owner_enforced_runtime_subtree_cutoff": "established",
                "writer_authority": "established",
            },
        }
    )
    declaration_path = tmp_path / "declaration.json"
    declaration_path.write_bytes(transition._canonical_bytes(declaration))
    script = """
import json
import os
import signal
import sys
from pathlib import Path
from tools.quality.validation import execute_gy_n12_artifact_transition as transition

real_replace = transition._atomic_replace
replacement_count = 0

def kill_after_first_replacement(target: Path, payload: bytes) -> None:
    global replacement_count
    real_replace(target, payload)
    replacement_count += 1
    if replacement_count == 1:
        os.kill(os.getpid(), signal.SIGKILL)

transition._atomic_replace = kill_after_first_replacement
transition.apply_declaration(
    repo_root=Path(sys.argv[1]),
    declaration=json.loads(Path(sys.argv[2]).read_bytes()),
    candidate_dir=Path(sys.argv[3]),
    state_dir=Path(sys.argv[4]),
    writer_authority=transition._UNIT_TEST_WRITER_AUTHORITY,
    expected_branch="codex/fixture",
    expected_declaration_head=sys.argv[5],
)
"""

    killed = subprocess.run(
        (
            sys.executable,
            "-c",
            script,
            str(root),
            str(declaration_path),
            str(candidates),
            str(state),
            expected_head,
        ),
        cwd=root,
        check=False,
    )

    assert killed.returncode == -signal.SIGKILL
    assert (root / "one.txt").read_text() == "one-new"
    assert (root / "two.txt").read_text() == "two-old"
    assert (state / "armed.json").is_file()
    assert not (state / "final.json").exists()
    assert not (state / "fallback.json").exists()

    restart_script = """
import sys
from pathlib import Path
from tools.quality.validation import execute_gy_n12_artifact_transition as transition

repo_root = Path(sys.argv[1]).resolve()
transition._repo_root = lambda: repo_root
raise SystemExit(transition.main([
    "apply",
    "--declaration", sys.argv[2],
    "--candidate-dir", sys.argv[3],
    "--expected-branch", "codex/fixture",
    "--expected-source-freeze", sys.argv[4],
    "--expected-declaration-head", sys.argv[4],
    "--state-dir", sys.argv[5],
]))
"""
    restarted = subprocess.run(
        (
            sys.executable,
            "-c",
            restart_script,
            str(root),
            str(tmp_path / "missing-declaration.json"),
            str(tmp_path / "missing-candidates"),
            expected_head,
            str(state),
        ),
        cwd=transition._repo_root(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert restarted.returncode == 1, restarted.stderr
    restart_receipt = json.loads(restarted.stdout)
    assert restart_receipt["issues"] == [
        {"code": "recovered_armed_transition", "detail": "recovered_armed_transition"}
    ]
    assert (root / "one.txt").read_text() == "one-old"
    assert (root / "two.txt").read_text() == "two-old"
    assert (root / "protected.txt").read_text() == "protected"
    assert (state / "fallback.json").is_file()
    assert not (state / "final.json").exists()
    fallback = transition._read_receipt(state / "fallback.json", schema=transition.FALLBACK_SCHEMA)
    armed = transition._read_receipt(state / "armed.json", schema=transition.ARMED_SCHEMA)
    assert fallback["status"] == "fallback"
    assert fallback["error"] == "recovered_armed_transition"
    assert fallback["armed_sha256"] == armed["receipt_sha256"]
    assert fallback["restored_target_denominator_sha256"] == transition.denominator_hash(
        [
            transition.path_state(root, Path("one.txt")),
            transition.path_state(root, Path("two.txt")),
        ]
    )
    assert not _git(root, "status", "--porcelain")


def test_apply_success_is_atomic_and_final_receipt_is_exclusive(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    candidates = tmp_path / "candidates"
    state = tmp_path / "state"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=root, check=True)
    candidates.mkdir()
    (root / "target.txt").write_text("old")
    (root / "protected.txt").write_text("fixed")
    (candidates / "target.txt").write_text("new")
    declaration = transition.with_receipt_hash(
        {
            "schema_version": transition.DECLARATION_SCHEMA,
            "targets": [
                {
                    "path": "target.txt",
                    "candidate_relative_path": "target.txt",
                    "candidate_sha256": _sha(candidates / "target.txt"),
                    "preimage": transition.path_state(root, Path("target.txt")),
                }
            ],
            "protected_paths": [transition.path_state(root, Path("protected.txt"))],
            "protected_denominator_sha256": transition.denominator_hash(
                [
                    transition.path_state(root, Path("target.txt")),
                    transition.path_state(root, Path("protected.txt")),
                ]
            ),
            "owner_predicates": {
                "foundry_adjudication": "established",
                "owner_enforced_runtime_subtree_cutoff": "established",
                "writer_authority": "established",
            },
        }
    )

    final = transition.apply_declaration(
        repo_root=root,
        declaration=declaration,
        candidate_dir=candidates,
        state_dir=state,
        writer_authority=transition._UNIT_TEST_WRITER_AUTHORITY,
        expected_branch="codex/fixture",
        expected_declaration_head="a" * 40,
    )

    assert (root / "target.txt").read_text() == "new"
    assert (root / "protected.txt").read_text() == "fixed"
    assert final["status"] == "final"
    with pytest.raises(FileExistsError):
        transition.apply_declaration(
            repo_root=root,
            declaration=declaration,
            candidate_dir=candidates,
            state_dir=state,
            writer_authority=transition._UNIT_TEST_WRITER_AUTHORITY,
            expected_branch="codex/fixture",
            expected_declaration_head="a" * 40,
        )


def test_apply_refuses_to_arm_without_recoverable_execution_context(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    candidates = tmp_path / "candidates"
    state = tmp_path / "state"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=root, check=True)
    candidates.mkdir()
    (root / "target.txt").write_text("old")
    (candidates / "target.txt").write_text("new")
    declaration = transition.with_receipt_hash(
        {
            "schema_version": transition.DECLARATION_SCHEMA,
            "targets": [
                {
                    "path": "target.txt",
                    "candidate_relative_path": "target.txt",
                    "candidate_sha256": _sha(candidates / "target.txt"),
                    "preimage": transition.path_state(root, Path("target.txt")),
                }
            ],
            "protected_paths": [],
            "protected_denominator_sha256": transition.denominator_hash(
                [transition.path_state(root, Path("target.txt"))]
            ),
            "owner_predicates": {
                "foundry_adjudication": "established",
                "owner_enforced_runtime_subtree_cutoff": "established",
                "writer_authority": "established",
            },
        }
    )

    with pytest.raises(ValueError, match="apply_execution_context_not_established"):
        transition.apply_declaration(
            repo_root=root,
            declaration=declaration,
            candidate_dir=candidates,
            state_dir=state,
            writer_authority=transition._UNIT_TEST_WRITER_AUTHORITY,
        )

    assert (root / "target.txt").read_text() == "old"
    assert not state.exists()


def test_apply_runs_context_guard_after_last_replacement_before_final(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    candidates = tmp_path / "candidates"
    state = tmp_path / "state"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=root, check=True)
    candidates.mkdir()
    (root / "target.txt").write_text("old")
    (candidates / "target.txt").write_text("new")
    declaration = transition.with_receipt_hash(
        {
            "schema_version": transition.DECLARATION_SCHEMA,
            "targets": [
                {
                    "path": "target.txt",
                    "candidate_relative_path": "target.txt",
                    "candidate_sha256": _sha(candidates / "target.txt"),
                    "preimage": transition.path_state(root, Path("target.txt")),
                }
            ],
            "protected_paths": [],
            "protected_denominator_sha256": transition.denominator_hash(
                [transition.path_state(root, Path("target.txt"))]
            ),
            "owner_predicates": {
                "foundry_adjudication": "established",
                "owner_enforced_runtime_subtree_cutoff": "established",
                "writer_authority": "established",
            },
        }
    )
    guard_calls = 0

    def guard() -> None:
        nonlocal guard_calls
        guard_calls += 1
        if guard_calls == 3:
            raise RuntimeError("apply_head_changed_during_write")

    with pytest.raises(RuntimeError, match="apply_head_changed_during_write"):
        transition.apply_declaration(
            repo_root=root,
            declaration=declaration,
            candidate_dir=candidates,
            state_dir=state,
            writer_authority=transition._UNIT_TEST_WRITER_AUTHORITY,
            runtime_guard=guard,
            expected_branch="codex/fixture",
            expected_declaration_head="a" * 40,
        )

    assert guard_calls == 3
    assert (root / "target.txt").read_text() == "old"
    assert (state / "fallback.json").is_file()
    assert not (state / "final.json").exists()


def test_apply_cli_recovers_armed_state_before_reading_a_new_declaration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "repo"
    state = tmp_path / "state"
    root.mkdir()
    state.mkdir()
    (root / "target.txt").write_text("partial")
    preimage_root = state / "preimages"
    preimage_root.mkdir()
    backup = preimage_root / "000000.blob"
    backup.write_text("original")
    preimage = {
        "path": "target.txt",
        "kind": "present",
        "sha256": _sha(backup),
        "byte_size": len(backup.read_bytes()),
        "backup": "preimages/000000.blob",
    }
    armed = transition.with_receipt_hash(
        {
            "schema_version": transition.ARMED_SCHEMA,
            "status": "armed",
            "declaration_sha256": "sha256:" + "d" * 64,
            "expected_branch": "codex/fixture",
            "expected_declaration_head": "a" * 40,
            "target_preimages": [preimage],
            "protected_paths": [],
            "target_count": 1,
        }
    )
    transition._write_exclusive(state / "armed.json", armed)
    monkeypatch.setattr(transition, "_repo_root", lambda: root)
    monkeypatch.setattr(
        transition,
        "_git",
        lambda _root, *args, **_kwargs: (
            "codex/fixture" if args[:3] == ("symbolic-ref", "--short", "HEAD") else "a" * 40
        ),
    )

    exit_code = transition.main(
        [
            "apply",
            "--declaration",
            str(tmp_path / "missing-declaration.json"),
            "--candidate-dir",
            str(tmp_path / "candidates"),
            "--expected-branch",
            "codex/fixture",
            "--expected-source-freeze",
            "b" * 40,
            "--expected-declaration-head",
            "a" * 40,
            "--state-dir",
            str(state),
        ]
    )

    assert exit_code == 1
    assert (root / "target.txt").read_text() == "original"
    assert (state / "fallback.json").is_file()
    payload = json.loads(capsys.readouterr().out)
    assert payload["issues"][0]["code"] == "recovered_armed_transition"


def test_apply_cli_refuses_repository_state_before_recovery_can_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    git_root = tmp_path / "repo"
    product = git_root / "policy-engine"
    state = product / ".transition-state"
    product.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=git_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.invalid"], cwd=git_root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=git_root, check=True)
    (product / "target.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=git_root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=git_root, check=True)
    head = _git(git_root, "rev-parse", "HEAD")
    (product / "target.txt").write_text("partial")
    backup = state / "preimages/000000.blob"
    backup.parent.mkdir(parents=True)
    backup.write_text("original")
    armed = transition.with_receipt_hash(
        {
            "schema_version": transition.ARMED_SCHEMA,
            "status": "armed",
            "declaration_sha256": "sha256:" + "d" * 64,
            "expected_branch": "codex/fixture",
            "expected_declaration_head": head,
            "target_preimages": [
                {
                    "path": "target.txt",
                    "kind": "present",
                    "sha256": _sha(backup),
                    "byte_size": len(backup.read_bytes()),
                    "backup": "preimages/000000.blob",
                }
            ],
            "protected_paths": [],
            "target_count": 1,
        }
    )
    transition._write_exclusive(state / "armed.json", armed)
    monkeypatch.setattr(transition, "_repo_root", lambda: product)

    exit_code = transition.main(
        [
            "apply",
            "--declaration",
            str(tmp_path / "missing-declaration.json"),
            "--candidate-dir",
            str(tmp_path / "candidates"),
            "--expected-branch",
            "codex/fixture",
            "--expected-source-freeze",
            head,
            "--expected-declaration-head",
            head,
            "--state-dir",
            str(state),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["issues"][0]["code"] == "state_directory_inside_repository"
    assert (product / "target.txt").read_text() == "partial"
    assert not (state / "fallback.json").exists()


@pytest.mark.parametrize(
    ("expected_branch", "expected_head", "diagnostic"),
    [
        ("codex/other", "HEAD", "armed_recovery_branch_mismatch"),
        ("codex/fixture", "0" * 40, "armed_recovery_head_mismatch"),
    ],
)
def test_recovery_refuses_wrong_recorded_execution_context_without_writing(
    tmp_path: Path,
    expected_branch: str,
    expected_head: str,
    diagnostic: str,
) -> None:
    root = tmp_path / "repo"
    state = tmp_path / "state"
    root.mkdir()
    _init_repo(root)
    actual_head = _git(root, "rev-parse", "HEAD")
    (root / "target.txt").write_text("partial")
    backup = state / "preimages/000000.blob"
    backup.parent.mkdir(parents=True)
    backup.write_text("original")
    armed = transition.with_receipt_hash(
        {
            "schema_version": transition.ARMED_SCHEMA,
            "status": "armed",
            "declaration_sha256": "sha256:" + "d" * 64,
            "expected_branch": expected_branch,
            "expected_declaration_head": (
                actual_head if expected_head == "HEAD" else expected_head
            ),
            "target_preimages": [
                {
                    "path": "target.txt",
                    "kind": "present",
                    "sha256": _sha(backup),
                    "byte_size": len(backup.read_bytes()),
                    "backup": "preimages/000000.blob",
                }
            ],
            "protected_paths": [],
            "target_count": 1,
        }
    )
    transition._write_exclusive(state / "armed.json", armed)

    with pytest.raises(ValueError, match=diagnostic):
        transition.recover_armed_transition(repo_root=root, state_dir=state)

    assert (root / "target.txt").read_text() == "partial"
    assert not (state / "fallback.json").exists()


def test_apply_cli_normalizes_git_paths_to_the_product_coordinate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    git_root = tmp_path / "repo"
    git_root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=git_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.invalid"], cwd=git_root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=git_root, check=True)
    product = git_root / "policy-engine"
    record = product / "docs/journal.md"
    record.parent.mkdir(parents=True)
    record.write_text("base\n")
    subprocess.run(["git", "add", "."], cwd=git_root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=git_root, check=True)
    source_freeze = _git(git_root, "rev-parse", "HEAD")
    declaration = transition.with_receipt_hash(
        {
            "schema_version": transition.DECLARATION_SCHEMA,
            "expected_branch": "codex/fixture",
            "source_freeze": source_freeze,
            "source_tree": _git(git_root, "rev-parse", f"{source_freeze}^{{tree}}"),
            "allowed_post_freeze_records": ["docs/journal.md"],
            "targets": [],
            "protected_paths": [],
            "protected_denominator_sha256": transition.denominator_hash([]),
            "tool_sources": [],
            "owner_predicates": {
                "foundry_adjudication": "established",
                "owner_enforced_runtime_subtree_cutoff": "established",
                "writer_authority": "established",
            },
        }
    )
    declaration_bytes = transition._canonical_bytes(declaration) + b"\n"
    record.write_bytes(declaration_bytes)
    subprocess.run(["git", "add", "."], cwd=git_root, check=True)
    subprocess.run(["git", "commit", "-qm", "declaration"], cwd=git_root, check=True)
    declaration_head = _git(git_root, "rev-parse", "HEAD")
    declaration_path = tmp_path / "declaration.json"
    declaration_path.write_bytes(declaration_bytes)
    candidate_dir = tmp_path / "candidates"
    candidate_dir.mkdir()
    monkeypatch.setattr(transition, "_repo_root", lambda: product)
    monkeypatch.setattr(
        transition,
        "apply_declaration",
        lambda **_kwargs: transition.with_receipt_hash(
            {"schema_version": transition.FINAL_SCHEMA, "status": "final"}
        ),
    )

    exit_code = transition.main(
        [
            "apply",
            "--declaration",
            str(declaration_path),
            "--candidate-dir",
            str(candidate_dir),
            "--expected-branch",
            "codex/fixture",
            "--expected-source-freeze",
            source_freeze,
            "--expected-declaration-head",
            declaration_head,
            "--state-dir",
            str(tmp_path / "state"),
        ]
    )

    assert exit_code == 0, capsys.readouterr().out


def test_apply_cli_requires_the_declaration_commit_to_be_the_freeze_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    git_root = tmp_path / "repo"
    product = git_root / "policy-engine"
    record = product / "docs/journal.md"
    record.parent.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=git_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.invalid"], cwd=git_root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=git_root, check=True)
    record.write_text("base\n")
    subprocess.run(["git", "add", "."], cwd=git_root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=git_root, check=True)
    source_freeze = _git(git_root, "rev-parse", "HEAD")
    subprocess.run(
        ["git", "commit", "--allow-empty", "-qm", "intervening"],
        cwd=git_root,
        check=True,
    )
    declaration = transition.with_receipt_hash(
        {
            "schema_version": transition.DECLARATION_SCHEMA,
            "expected_branch": "codex/fixture",
            "source_freeze": source_freeze,
            "source_tree": _git(git_root, "rev-parse", f"{source_freeze}^{{tree}}"),
            "allowed_post_freeze_records": ["docs/journal.md"],
            "targets": [],
            "protected_paths": [],
            "protected_denominator_sha256": transition.denominator_hash([]),
            "tool_sources": [],
            "owner_predicates": {
                "foundry_adjudication": "established",
                "owner_enforced_runtime_subtree_cutoff": "established",
                "writer_authority": "established",
            },
        }
    )
    declaration_bytes = transition._canonical_bytes(declaration) + b"\n"
    record.write_bytes(declaration_bytes)
    subprocess.run(["git", "add", "."], cwd=git_root, check=True)
    subprocess.run(["git", "commit", "-qm", "declaration"], cwd=git_root, check=True)
    declaration_head = _git(git_root, "rev-parse", "HEAD")
    declaration_path = tmp_path / "declaration.json"
    declaration_path.write_bytes(declaration_bytes)
    candidate_dir = tmp_path / "candidates"
    candidate_dir.mkdir()
    monkeypatch.setattr(transition, "_repo_root", lambda: product)
    monkeypatch.setattr(
        transition,
        "apply_declaration",
        lambda **_kwargs: transition.with_receipt_hash(
            {"schema_version": transition.FINAL_SCHEMA, "status": "final"}
        ),
    )

    exit_code = transition.main(
        [
            "apply",
            "--declaration",
            str(declaration_path),
            "--candidate-dir",
            str(candidate_dir),
            "--expected-branch",
            "codex/fixture",
            "--expected-source-freeze",
            source_freeze,
            "--expected-declaration-head",
            declaration_head,
            "--state-dir",
            str(tmp_path / "state"),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["issues"][0]["code"] == "apply_declaration_not_direct_freeze_child"


def test_apply_cli_refuses_same_journal_path_with_noncanonical_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    git_root = tmp_path / "repo"
    product = git_root / "policy-engine"
    record = product / "docs/journal.md"
    record.parent.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=git_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.invalid"], cwd=git_root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=git_root, check=True)
    record.write_text("base\n")
    subprocess.run(["git", "add", "."], cwd=git_root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=git_root, check=True)
    source_freeze = _git(git_root, "rev-parse", "HEAD")
    declaration = transition.with_receipt_hash(
        {
            "schema_version": transition.DECLARATION_SCHEMA,
            "expected_branch": "codex/fixture",
            "source_freeze": source_freeze,
            "source_tree": _git(git_root, "rev-parse", f"{source_freeze}^{{tree}}"),
            "allowed_post_freeze_records": ["docs/journal.md"],
            "targets": [],
            "protected_paths": [],
            "protected_denominator_sha256": transition.denominator_hash([]),
            "tool_sources": [],
            "owner_predicates": {
                "foundry_adjudication": "established",
                "owner_enforced_runtime_subtree_cutoff": "established",
                "writer_authority": "established",
            },
        }
    )
    record.write_text("same path, wrong bytes\n")
    subprocess.run(["git", "add", "."], cwd=git_root, check=True)
    subprocess.run(["git", "commit", "-qm", "declaration"], cwd=git_root, check=True)
    declaration_path = tmp_path / "declaration.json"
    declaration_path.write_bytes(transition._canonical_bytes(declaration) + b"\n")
    candidate_dir = tmp_path / "candidates"
    candidate_dir.mkdir()
    monkeypatch.setattr(transition, "_repo_root", lambda: product)

    exit_code = transition.main(
        [
            "apply",
            "--declaration",
            str(declaration_path),
            "--candidate-dir",
            str(candidate_dir),
            "--expected-branch",
            "codex/fixture",
            "--expected-source-freeze",
            source_freeze,
            "--expected-declaration-head",
            _git(git_root, "rev-parse", "HEAD"),
            "--state-dir",
            str(tmp_path / "state"),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["issues"][0]["code"] == "apply_declaration_record_content_mismatch"


def test_readback_binds_final_to_declaration_parent_and_exact_target_map(
    tmp_path: Path,
) -> None:
    _base, declaration_head = _init_repo(tmp_path)
    target = tmp_path / "artifact.json"
    target.write_text("candidate\n")
    subprocess.run(["git", "add", "artifact.json"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "artifact"], cwd=tmp_path, check=True)
    artifact_head = _git(tmp_path, "rev-parse", "HEAD")
    declaration = transition.with_receipt_hash(
        {
            "schema_version": transition.DECLARATION_SCHEMA,
            "expected_branch": "codex/fixture",
            "targets": [{"path": "artifact.json", "candidate_sha256": _sha(target)}],
            "protected_denominator_sha256": "sha256:" + "a" * 64,
        }
    )
    final = transition.with_receipt_hash(
        {
            "schema_version": transition.FINAL_SCHEMA,
            "status": "final",
            "declaration_sha256": declaration["receipt_sha256"],
            "declaration_head": declaration_head,
            "target_sha256": {"artifact.json": _sha(target)},
            "protected_denominator_sha256": declaration["protected_denominator_sha256"],
        }
    )

    def accepted_consumer(**_kwargs: object) -> tuple[dict[str, str], ...]:
        return ({"target_path": "artifact.json", "consumer": "fixture", "status": "pass"},)

    report = transition.build_readback(
        repo_root=tmp_path,
        declaration=declaration,
        final=final,
        expected_branch="codex/fixture",
        expected_head=artifact_head,
        consumer_probe=accepted_consumer,
    )
    assert report["artifact_parent"] == declaration_head
    assert report["consumer_results"] == [
        {"target_path": "artifact.json", "consumer": "fixture", "status": "pass"}
    ]

    with pytest.raises(ValueError, match="readback_consumer_rejected"):
        transition.build_readback(
            repo_root=tmp_path,
            declaration=declaration,
            final=final,
            expected_branch="codex/fixture",
            expected_head=artifact_head,
            consumer_probe=lambda **_kwargs: (
                {
                    "target_path": "artifact.json",
                    "consumer": "fixture",
                    "status": "fail",
                    "diagnostic": "fixture_rejected",
                },
            ),
        )

    unrelated = transition.with_receipt_hash({**final, "declaration_sha256": "sha256:" + "f" * 64})
    with pytest.raises(ValueError, match="readback_declaration_binding_mismatch"):
        transition.build_readback(
            repo_root=tmp_path,
            declaration=declaration,
            final=unrelated,
            expected_branch="codex/fixture",
            expected_head=artifact_head,
            consumer_probe=accepted_consumer,
        )

    wrong_branch = transition.with_receipt_hash({**declaration, "expected_branch": "codex/other"})
    wrong_branch_final = transition.with_receipt_hash(
        {
            **final,
            "declaration_sha256": wrong_branch["receipt_sha256"],
        }
    )
    with pytest.raises(ValueError, match="readback_declaration_branch_binding_mismatch"):
        transition.build_readback(
            repo_root=tmp_path,
            declaration=wrong_branch,
            final=wrong_branch_final,
            expected_branch="codex/fixture",
            expected_head=artifact_head,
            consumer_probe=accepted_consumer,
        )

    wrong_denominator = transition.with_receipt_hash(
        {**final, "protected_denominator_sha256": "sha256:" + "b" * 64}
    )
    with pytest.raises(ValueError, match="readback_protected_denominator_mismatch"):
        transition.build_readback(
            repo_root=tmp_path,
            declaration=declaration,
            final=wrong_denominator,
            expected_branch="codex/fixture",
            expected_head=artifact_head,
            consumer_probe=accepted_consumer,
        )


def test_default_readback_recomputes_generated_reference_from_committed_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.devx.architecture import guardrails
    from tools.quality.validation import check_layer3_gy_epoch_chronology_contract as epoch

    _base, declaration_head = _init_repo(tmp_path)
    registry = tmp_path / transition.REGISTRY_TARGET
    reference = tmp_path / transition.REFERENCE_TARGET
    epoch_payload = tmp_path / transition.EPOCH_TARGET
    reference.parent.mkdir(parents=True)
    epoch_payload.parent.mkdir(parents=True)
    monkeypatch.setattr(epoch, "validate_payload", lambda *_args, **_kwargs: ())

    def family_block(
        *, family_id: str, owner: str, lifecycle: str, output: str, sequence: int
    ) -> str:
        return f"""
[[family]]
id = "{family_id}"
label = "{family_id} label"
owner = "{owner}"
approval_owner = "fixture-approval-owner"
lifecycle = "{lifecycle}"
generator = "fixture generator {sequence}"
verifier = "fixture verifier"
promotion_target = "fixture target"
stale_output_behavior = "fail"
source_of_truth = "fixture source"
outputs = ["{output}"]
regenerate_commands = ["python fixture.py"]
commit_policy = "committed_after_task"
freshness_rule = "regenerate on fixture change"
drift_gate = "automated"
"""

    def commit_family(
        *,
        owner_count: int,
        lifecycle: str = "generated_committed",
        forge_reference: bool = False,
        sequence: int,
    ) -> tuple[dict[str, object], dict[str, object], str]:
        parent = _git(tmp_path, "rev-parse", "HEAD")
        blocks = [
            family_block(
                family_id="fixture-family",
                owner="fixture-owner",
                lifecycle=lifecycle,
                output=(
                    transition.EPOCH_TARGET
                    if owner_count >= 1
                    else "architecture/not-the-epoch.json"
                ),
                sequence=sequence,
            )
        ]
        if owner_count == 2:
            blocks.append(
                family_block(
                    family_id="second-fixture-family",
                    owner="second-fixture-owner",
                    lifecycle="generated_committed",
                    output=transition.EPOCH_TARGET,
                    sequence=sequence,
                )
            )
        registry.write_text("[generated_artifacts]\nversion = 1\n" + "".join(blocks))
        rendered = guardrails.render_generated_artifacts_markdown(
            guardrails._parse_generated_artifacts(registry)
        )
        if forge_reference:
            rendered = rendered.replace("`fixture-owner`", "`forged-reference-owner`")
        reference.write_text(rendered)
        epoch_payload.write_text(json.dumps({"sequence": sequence}) + "\n")
        targets = (transition.EPOCH_TARGET, transition.REGISTRY_TARGET, transition.REFERENCE_TARGET)
        subprocess.run(["git", "add", *targets], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "commit", "-qm", f"generated family {sequence}"],
            cwd=tmp_path,
            check=True,
        )
        artifact_head = _git(tmp_path, "rev-parse", "HEAD")
        target_hashes = {
            transition.EPOCH_TARGET: _sha(epoch_payload),
            transition.REGISTRY_TARGET: _sha(registry),
            transition.REFERENCE_TARGET: _sha(reference),
        }
        declaration = transition.with_receipt_hash(
            {
                "schema_version": transition.DECLARATION_SCHEMA,
                "expected_branch": "codex/fixture",
                "source_freeze": parent,
                "targets": [
                    {"path": target, "candidate_sha256": target_hashes[target]}
                    for target in targets
                ],
                "protected_denominator_sha256": "sha256:" + "a" * 64,
            }
        )
        final = transition.with_receipt_hash(
            {
                "schema_version": transition.FINAL_SCHEMA,
                "status": "final",
                "declaration_sha256": declaration["receipt_sha256"],
                "declaration_head": parent,
                "target_sha256": target_hashes,
                "protected_denominator_sha256": declaration["protected_denominator_sha256"],
            }
        )
        return declaration, final, artifact_head

    declaration, final, artifact_head = commit_family(owner_count=1, sequence=0)
    assert declaration["source_freeze"] == declaration_head

    report = transition.build_readback(
        repo_root=tmp_path,
        declaration=declaration,
        final=final,
        expected_branch="codex/fixture",
        expected_head=artifact_head,
    )

    assert [(row["target_path"], row["status"]) for row in report["consumer_results"]] == [
        (transition.REGISTRY_TARGET, "pass"),
        (transition.EPOCH_TARGET, "pass"),
        (transition.REFERENCE_TARGET, "pass"),
    ]

    committed_registry = registry.read_bytes()
    subprocess.run(
        ["git", "update-index", "--assume-unchanged", transition.REGISTRY_TARGET],
        cwd=tmp_path,
        check=True,
    )
    registry.write_text('owner = "hidden-worktree-substitution"\n')
    assert not _git(tmp_path, "status", "--porcelain")
    hidden_report = transition.build_readback(
        repo_root=tmp_path,
        declaration=declaration,
        final=final,
        expected_branch="codex/fixture",
        expected_head=artifact_head,
    )
    assert all(row["status"] == "pass" for row in hidden_report["consumer_results"])
    registry.write_bytes(committed_registry)
    subprocess.run(
        ["git", "update-index", "--no-assume-unchanged", transition.REGISTRY_TARGET],
        cwd=tmp_path,
        check=True,
    )

    rejected_cases = (
        {"owner_count": 1, "forge_reference": True, "sequence": 1},
        {"owner_count": 1, "lifecycle": "invalid", "sequence": 2},
        {"owner_count": 0, "sequence": 3},
        {"owner_count": 2, "sequence": 4},
    )
    for case in rejected_cases:
        rejected_declaration, rejected_final, rejected_head = commit_family(**case)

        with pytest.raises(ValueError, match="readback_consumer_rejected"):
            transition.build_readback(
                repo_root=tmp_path,
                declaration=rejected_declaration,
                final=rejected_final,
                expected_branch="codex/fixture",
                expected_head=rejected_head,
            )


def test_external_scratch_guards_use_git_toplevel_not_product_subtree(
    tmp_path: Path,
) -> None:
    git_root = tmp_path / "repo"
    product = git_root / "policy-engine"
    product.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=git_root, check=True)
    sibling = git_root / "scratch"

    with pytest.raises(ValueError, match="candidate_directory_inside_repository"):
        transition._validate_candidate_root(product, sibling)
    with pytest.raises(ValueError, match="state_directory_inside_repository"):
        transition._require_external_path(
            product,
            sibling,
            code="state_directory_inside_repository",
        )


def test_measure_cli_refuses_governed_output_before_running_or_overwriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    git_root = tmp_path / "repo"
    product = git_root / "policy-engine"
    governed = product / "architecture/generated_artifacts.toml"
    governed.parent.mkdir(parents=True)
    governed.write_text("governed\n")
    subprocess.run(["git", "init", "-q", "-b", "codex/fixture"], cwd=git_root, check=True)
    monkeypatch.setattr(transition, "_repo_root", lambda: product)
    monkeypatch.setattr(
        "polisyos.runtime.quality.confidence_ledger._deployment_relative_paths",
        lambda _root: (),
    )
    monkeypatch.setattr(
        transition,
        "build_measurement",
        lambda **_kwargs: transition.with_receipt_hash(
            {"schema_version": transition.MEASUREMENT_SCHEMA, "status": "pass"}
        ),
    )

    exit_code = transition.main(
        [
            "measure",
            "--implementation-base",
            "a" * 40,
            "--source-freeze",
            "b" * 40,
            "--output",
            str(governed),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["issues"][0]["code"] == "output_path_inside_repository"
    assert governed.read_text() == "governed\n"


def test_safe_relative_path_rejects_escape_absolute_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ValueError, match="unsafe_relative_path"):
        transition.resolve_relative(root, Path("../escape"))
    with pytest.raises(ValueError, match="unsafe_relative_path"):
        transition.resolve_relative(root, Path("/absolute"))
    outside = tmp_path / "outside"
    outside.write_text("outside")
    os.symlink(outside, root / "link")
    with pytest.raises(ValueError, match="relative_path_symlink_escape"):
        transition.resolve_relative(root, Path("link"))


def test_zero_intersection_requires_zero_deployment_candidates() -> None:
    transition.require_candidate_family_exactness(
        affected_families=("epoch",),
        deployment_intersection=(),
        rows=tuple(
            {"family": "epoch", "target_path": target}
            for target in (
                transition.EPOCH_TARGET,
                transition.REGISTRY_TARGET,
                transition.REFERENCE_TARGET,
            )
        ),
    )
    with pytest.raises(ValueError, match="zero_intersection_requires_zero_deployment_reissue"):
        transition.require_candidate_family_exactness(
            affected_families=("epoch",),
            deployment_intersection=(),
            rows=(
                *(
                    {"family": "epoch", "target_path": target}
                    for target in (
                        transition.EPOCH_TARGET,
                        transition.REGISTRY_TARGET,
                        transition.REFERENCE_TARGET,
                    )
                ),
                {"family": "deployment", "target_path": "deployment.json"},
            ),
        )


def test_epoch_candidate_family_rejects_payload_without_registry_and_reference() -> None:
    with pytest.raises(ValueError, match="candidate_target_denominator_mismatch:epoch"):
        transition.require_candidate_family_exactness(
            affected_families=("epoch",),
            deployment_intersection=(),
            rows=({"family": "epoch", "target_path": transition.EPOCH_TARGET},),
        )


def test_candidate_command_refuses_leading_output_even_with_a_valid_last_envelope() -> None:
    envelope = transition.with_receipt_hash(
        {
            "validator": "validator.expected",
            "mode": "candidate-output",
            "status": "pass",
            "issues": [],
        }
    )
    script = "import json; print('junk'); print(json.dumps(" + repr(envelope) + "))"

    with pytest.raises(ValueError, match="candidate_command_payload_invalid"):
        transition._invoke_json(
            (sys.executable, "-c", script),
            expected_validator="validator.expected",
            expected_mode="candidate-output",
        )


def test_n8_environment_probe_binds_site_and_distribution_origins(tmp_path: Path) -> None:
    environment = tmp_path / "n8"
    interpreter = environment / "bin/python"
    interpreter.parent.mkdir(parents=True)
    os.symlink(sys.executable, interpreter)
    site = environment / "lib/python3.14/site-packages"
    metadata = site / "fixture_distribution-1.0.dist-info/METADATA"
    metadata.parent.mkdir(parents=True)
    metadata.write_text("Name: fixture-distribution\nVersion: 1.0\n")
    tooling_site = tmp_path / "tooling/lib/python3.14/site-packages"
    tooling_site.mkdir(parents=True)
    receipt = _write_n8_environment_receipt(environment)

    report = transition.validate_n8_environment(
        n8_python=interpreter,
        environment_receipt=receipt,
        tooling_site=tooling_site,
    )

    assert report["environment_site"] == str(site.resolve())
    assert report["tooling_site_present"] is False
    assert report["distribution_count"] == 1
    assert report["escaped_distribution_origins"] == []
    assert report["environment_receipt_ref"] == receipt.receipt_ref.model_dump(mode="json")
    assert report["environment_marker_ref"] == receipt.statement.marker_ref.model_dump(mode="json")


def test_n8_environment_refuses_a_caller_shaped_local_mapping(tmp_path: Path) -> None:
    environment = tmp_path / "n8"
    interpreter = environment / "bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"python")
    tooling_site = tmp_path / "tooling/lib/python3.14/site-packages"
    tooling_site.mkdir(parents=True)

    with pytest.raises(ValueError, match="n8_environment_receipt_not_established"):
        transition.validate_n8_environment(
            n8_python=interpreter,
            environment_receipt={
                "environment_root": str(environment),
                "source_freeze": "a" * 40,
            },
            tooling_site=tooling_site,
            origin_probe=lambda **_kwargs: {},
        )


def test_candidate_builder_requires_the_strict_foundry_environment_receipt(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _base, source_freeze = _init_repo(root)
    receipt_path = tmp_path / "caller-shaped-receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "environment_root": str(tmp_path / "n8"),
                "source_freeze": source_freeze,
            }
        )
    )
    measurement = transition.with_receipt_hash(
        {
            "schema_version": transition.MEASUREMENT_SCHEMA,
            "source_freeze": source_freeze,
            "source_tree": _git(root, "rev-parse", f"{source_freeze}^{{tree}}"),
            "affected_families": [],
        }
    )

    with pytest.raises(ValueError, match="n8_environment_receipt_not_established"):
        transition.build_candidates(
            repo_root=root,
            measurement=measurement,
            candidate_dir=tmp_path / "candidates",
            n8_python=tmp_path / "n8/bin/python",
            n8_environment_receipt_path=receipt_path,
        )


def test_jointly_content_bound_candidate_receipt_cannot_mint_owner_admission(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _base, source_freeze = _init_repo(root)
    environment = tmp_path / "n8"
    receipt = _write_n8_environment_receipt(environment)
    receipt_path = tmp_path / "candidate-environment-receipt.json"
    receipt_path.write_text(receipt.model_dump_json())
    candidate_dir = tmp_path / "candidates"
    measurement = transition.with_receipt_hash(
        {
            "schema_version": transition.MEASUREMENT_SCHEMA,
            "source_freeze": source_freeze,
            "source_tree": _git(root, "rev-parse", f"{source_freeze}^{{tree}}"),
            "affected_families": ["n8"],
        }
    )

    with pytest.raises(ValueError, match="dependency_environment_receipt_not_established"):
        transition.build_candidates(
            repo_root=root,
            measurement=measurement,
            candidate_dir=candidate_dir,
            n8_python=environment / "bin/python",
            n8_environment_receipt_path=receipt_path,
        )

    assert not candidate_dir.exists()


def test_n8_environment_refuses_marker_substitution(tmp_path: Path) -> None:
    environment = tmp_path / "n8"
    interpreter = environment / "bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"python")
    site = environment / "lib/python3.14/site-packages"
    site.mkdir(parents=True)
    tooling_site = tmp_path / "tooling/lib/python3.14/site-packages"
    tooling_site.mkdir(parents=True)
    receipt = _write_n8_environment_receipt(environment)
    marker_path = environment / ".polisyos-foundry-authority-v1" / "environment-marker.json"
    marker = DependencyEnvironmentMarkerStatement.model_validate_json(marker_path.read_bytes())
    forged = marker.model_copy(
        update={
            "environment_creation_nonce": domain_digest(
                DigestDomain.ENVIRONMENT_INSTANCE,
                b"forged-instance",
            )
        }
    )
    marker_path.write_bytes(canonical_json_bytes(forged.model_dump(mode="json")))

    with pytest.raises(ValueError, match="n8_environment_marker_mismatch"):
        transition.validate_n8_environment(
            n8_python=interpreter,
            environment_receipt=receipt,
            tooling_site=tooling_site,
            origin_probe=lambda **_kwargs: {},
        )


def test_n8_environment_refuses_a_rebound_receipt_with_a_different_marker_join(
    tmp_path: Path,
) -> None:
    environment = tmp_path / "n8"
    interpreter = environment / "bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"python")
    site = environment / "lib/python3.14/site-packages"
    site.mkdir(parents=True)
    tooling_site = tmp_path / "tooling/lib/python3.14/site-packages"
    tooling_site.mkdir(parents=True)
    receipt = _write_n8_environment_receipt(environment)
    substituted_statement = receipt.statement.model_copy(
        update={
            "stable_closure": domain_digest(
                DigestDomain.DEPENDENCY_CLOSURE,
                b"substituted-closure",
            )
        }
    )
    substituted_receipt = DependencyProfileEnvironmentReceipt(
        receipt_ref=record_ref(
            DigestDomain.ENVIRONMENT_RECEIPT,
            canonical_json_bytes(substituted_statement.model_dump(mode="json")),
            schema_version=substituted_statement.schema_version,
        ),
        statement=substituted_statement,
        predicate_class="recomputed",
    )

    with pytest.raises(ValueError, match="n8_environment_marker_statement_mismatch"):
        transition.validate_n8_environment(
            n8_python=interpreter,
            environment_receipt=substituted_receipt,
            tooling_site=tooling_site,
            origin_probe=lambda **_kwargs: {},
        )


@pytest.mark.parametrize(
    ("probe_update", "diagnostic"),
    [
        ({"tooling_site_present": True}, "n8_tooling_site_leaked"),
        (
            {"escaped_distribution_origins": ["/ambient/site-packages"]},
            "n8_distribution_origin_escape",
        ),
    ],
)
def test_n8_environment_rejects_probe_leakage_and_origin_escape(
    tmp_path: Path,
    probe_update: dict[str, object],
    diagnostic: str,
) -> None:
    environment = tmp_path / "n8"
    interpreter = environment / "bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"python")
    site = environment / "lib/python3.14/site-packages"
    site.mkdir(parents=True)
    tooling_site = tmp_path / "tooling/lib/python3.14/site-packages"
    tooling_site.mkdir(parents=True)
    probe = {
        "environment_site": str(site.resolve()),
        "tooling_site_present": False,
        "distribution_count": 0,
        "distribution_origins": [],
        "escaped_distribution_origins": [],
    }
    probe.update(probe_update)
    receipt = _write_n8_environment_receipt(environment)

    with pytest.raises(ValueError, match=diagnostic):
        transition.validate_n8_environment(
            n8_python=interpreter,
            environment_receipt=receipt,
            tooling_site=tooling_site,
            origin_probe=lambda **_kwargs: probe,
        )


def test_n8_candidate_reissue_writes_only_the_explicit_scratch_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = {"contract_content_hash": "old"}
    candidate_payload = {"contract_content_hash": "new", "candidate": True}
    monkeypatch.setattr(n8, "_load_json", lambda _path: recorded)
    monkeypatch.setattr(
        n8,
        "_candidate_catalog_denominator_evidence_cached",
        lambda: ({"catalog_provenance": {}}, {"entry_points": []}),
    )
    monkeypatch.setattr(
        n8,
        "_catalog_provenance_reissue_payload",
        lambda *args: candidate_payload,
    )
    monkeypatch.setattr(
        n8,
        "validate_payload_result",
        lambda *args, **kwargs: n8.ValueGateValidationResult((), ()),
    )
    candidate = tmp_path / "candidates/n8.json"
    governed = n8._repo_root() / n8.OUTPUT_PATH
    governed_preimage = governed.read_bytes()

    report = n8.write_candidate_catalog_provenance(
        n8._repo_root(),
        candidate_path=candidate,
        expected_source_freeze=_git(n8._repo_root(), "rev-parse", "HEAD"),
    )

    assert json.loads(candidate.read_text()) == candidate_payload
    assert report["status"] == "pass"
    assert report["candidate_sha256"] == _sha(candidate)
    assert report["receipt_sha256"] == transition.with_receipt_hash(report)["receipt_sha256"]
    assert not (n8._repo_root() / n8.OUTPUT_PATH).samefile(candidate)
    assert governed.read_bytes() == governed_preimage


def test_n8_candidate_reissue_refuses_a_governed_or_existing_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="candidate_path_inside_repository"):
        n8.write_candidate_catalog_provenance(
            n8._repo_root(),
            candidate_path=n8._repo_root() / n8.OUTPUT_PATH,
            expected_source_freeze=_git(n8._repo_root(), "rev-parse", "HEAD"),
        )
    with pytest.raises(ValueError, match="candidate_path_inside_repository"):
        n8.write_candidate_catalog_provenance(
            n8._repo_root(),
            candidate_path=n8._repo_root().parent / "n8-candidate.json",
            expected_source_freeze=_git(n8._repo_root(), "rev-parse", "HEAD"),
        )
    existing = tmp_path / "existing.json"
    existing.write_text("existing")
    with pytest.raises(ValueError, match="candidate_path_already_exists"):
        n8.write_candidate_catalog_provenance(
            n8._repo_root(),
            candidate_path=existing,
            expected_source_freeze=_git(n8._repo_root(), "rev-parse", "HEAD"),
        )


def test_n10a_candidate_dir_writes_exact_five_scratch_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = {
        "census": {"artifact": "census"},
        "pack": {"artifact": "pack"},
        "smoke_problem": {"artifact": "smoke"},
        "cycle_trace": {"artifact": "trace"},
        "gaps": {"artifact": "gaps"},
        "runtime_metrics": {"query_timings_seconds": {}},
    }
    monkeypatch.setattr(n10a, "_require_n10a_source_scope_clean", lambda _root: None)
    monkeypatch.setattr(n10a, "build_live_bundle", lambda *args, **kwargs: bundle)
    monkeypatch.setattr(n10a, "_cycle_trace_plan_from_manifest", lambda _trace: {})
    monkeypatch.setattr(
        n10a,
        "_reconcile_frozen_cycle_trace",
        lambda trace, _root, _plan: trace,
    )
    monkeypatch.setattr(n10a, "_preserve_frozen_operational_metrics", lambda *_args: None)
    monkeypatch.setattr(n10a, "validate_bundle_payloads", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        n10a,
        "_prepare_artifact_write_transitions",
        lambda *_args: [],
    )
    monkeypatch.setattr(
        n10a,
        "_artifact_write_transition_manifest",
        lambda *_args: {"content_hash": "candidate"},
    )
    candidate_root = tmp_path / "n10a"
    governed_preimages = {
        relative: (n10a.REPO_ROOT / relative).read_bytes() for relative in n10a.ARTIFACT_OUTPUTS
    }

    report = n10a.write(
        n10a.REPO_ROOT,
        expected_source_freeze="b" * 40,
        persist=False,
        candidate_dir=candidate_root,
    )

    assert report["status"] == "pass"
    assert report["write_performed"] is False
    assert report["candidate_write_performed"] is True
    assert report["outputs"] == list(n10a.ARTIFACT_OUTPUTS)
    assert sorted(
        path.relative_to(candidate_root).as_posix()
        for path in candidate_root.rglob("*")
        if path.is_file()
    ) == sorted(n10a.ARTIFACT_OUTPUTS)
    assert {
        relative: (n10a.REPO_ROOT / relative).read_bytes() for relative in n10a.ARTIFACT_OUTPUTS
    } == governed_preimages


def test_n10a_candidate_dir_refuses_persistence_and_repository_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="candidate_dir_conflicts_with_persist"):
        n10a.write(
            n10a.REPO_ROOT,
            expected_source_freeze="b" * 40,
            persist=True,
            candidate_dir=tmp_path / "candidate",
        )
    with pytest.raises(ValueError, match="candidate_dir_inside_repository"):
        n10a.write(
            n10a.REPO_ROOT,
            expected_source_freeze="b" * 40,
            persist=False,
            candidate_dir=n10a.REPO_ROOT / ".candidate",
        )
    with pytest.raises(ValueError, match="candidate_dir_inside_repository"):
        n10a.write(
            n10a.REPO_ROOT,
            expected_source_freeze="b" * 40,
            persist=False,
            candidate_dir=n10a.REPO_ROOT.parent / ".candidate",
        )


def test_n8_candidate_cli_emits_exactly_one_verified_json_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected = n8._semantic_envelope(
        mode="candidate-reissue-catalog-provenance",
        status="pass",
        issues=(),
        candidate_sha256="sha256:" + "a" * 64,
    )
    monkeypatch.setattr(n8, "write_candidate_catalog_provenance", lambda *args, **kwargs: expected)

    exit_code = n8.main(
        [
            "--candidate-reissue-catalog-provenance",
            str(tmp_path / "candidate.json"),
            "--expected-source-freeze",
            _git(n8._repo_root(), "rev-parse", "HEAD"),
            "--output-format",
            "json",
        ]
    )

    lines = capsys.readouterr().out.splitlines()
    payload = json.loads(lines[0])
    assert exit_code == 0
    assert len(lines) == 1
    assert payload["receipt_sha256"] == _independent_receipt_sha256(payload)
    assert transition.verify_receipt(payload)
    tampered = {**payload, "status": "fail"}
    assert tampered["receipt_sha256"] != _independent_receipt_sha256(tampered)
    assert not transition.verify_receipt(tampered)


def test_n10a_candidate_cli_emits_exactly_one_verified_json_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        n10a,
        "write",
        lambda *args, **kwargs: {
            "status": "pass",
            "issues": [],
            "outputs": list(n10a.ARTIFACT_OUTPUTS),
        },
    )

    exit_code = n10a.main(
        [
            "--repo-root",
            str(n10a.REPO_ROOT),
            "--candidate-dir",
            str(tmp_path / "candidate"),
            "--expected-source-freeze",
            "b" * 40,
            "--output-format",
            "json",
        ]
    )

    lines = capsys.readouterr().out.splitlines()
    payload = json.loads(lines[0])
    assert exit_code == 0
    assert len(lines) == 1
    assert payload["validator"] == n10a.VALIDATOR_ID
    assert payload["mode"] == "candidate-dir"
    assert payload["receipt_sha256"] == _independent_receipt_sha256(payload)
    assert transition.verify_receipt(payload)
    tampered = {**payload, "status": "fail"}
    assert tampered["receipt_sha256"] != _independent_receipt_sha256(tampered)
    assert not transition.verify_receipt(tampered)


def test_n10a_corrupt_envelope_retains_inverted_semantics() -> None:
    payload = n10a._semantic_report(
        {
            "status": "fail",
            "issues": [
                {"code": "corrupt_field_drift_detected", "detected": ["one"]},
                {"code": "ordinary_validation_detail"},
            ],
        },
        mode="corrupt-field-drift-check",
    )

    assert payload["status"] == "fail"
    assert payload["issues"] == [{"code": "corrupt_field_drift_detected", "detected": ["one"]}]
    assert "process_exit" not in payload
    assert transition.verify_receipt(payload)


def test_n8_corrupt_cli_emits_semantic_pass_with_documented_failure_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        n8,
        "corrupt_field_drift_results",
        lambda *_args, **_kwargs: (
            {"case_id": "field-one", "rejected": True},
            {"case_id": "field-two", "rejected": True},
        ),
    )

    exit_code = n8.main(
        [
            "--corrupt-field-drift-check",
            "--expected-source-freeze",
            "a" * 40,
            "--output-format",
            "json",
        ]
    )

    lines = capsys.readouterr().out.splitlines()
    payload = json.loads(lines[0])
    assert exit_code == 1
    assert len(lines) == 1
    assert payload["status"] == "pass"
    assert payload["issues"] == []
    assert transition.verify_receipt(payload)


def test_n10a_corrupt_cli_emits_detected_semantics_with_documented_failure_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        n10a,
        "corrupt_field_drift_check",
        lambda *_args, **_kwargs: {
            "status": "fail",
            "issues": [
                {"code": "corrupt_field_drift_detected", "detected": ["one"]},
                {"code": "ordinary_validation_detail"},
            ],
        },
    )

    exit_code = n10a.main(
        [
            "--repo-root",
            str(tmp_path),
            "--expected-source-freeze",
            "b" * 40,
            "--corrupt-field-drift-check",
            "--output-format",
            "json",
        ]
    )

    lines = capsys.readouterr().out.splitlines()
    payload = json.loads(lines[0])
    assert exit_code == 1
    assert len(lines) == 1
    assert payload["status"] == "fail"
    assert payload["issues"] == [{"code": "corrupt_field_drift_detected", "detected": ["one"]}]
    assert transition.verify_receipt(payload)


def test_n8_candidate_cli_converts_oserror_to_one_typed_failure_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise OSError("injected n8 write failure")

    monkeypatch.setattr(n8, "write_candidate_catalog_provenance", fail)

    exit_code = n8.main(
        [
            "--candidate-reissue-catalog-provenance",
            str(tmp_path / "candidate.json"),
            "--expected-source-freeze",
            "a" * 40,
            "--output-format",
            "json",
        ]
    )

    lines = capsys.readouterr().out.splitlines()
    payload = json.loads(lines[0])
    assert exit_code == 1
    assert len(lines) == 1
    assert payload["status"] == "fail"
    assert payload["issues"][0]["code"] == "value_gate_execution_failed"
    assert transition.verify_receipt(payload)


def test_n10a_candidate_cli_converts_oserror_to_one_typed_failure_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise OSError("injected n10a write failure")

    monkeypatch.setattr(n10a, "write", fail)

    exit_code = n10a.main(
        [
            "--repo-root",
            str(tmp_path),
            "--candidate-dir",
            str(tmp_path / "candidate"),
            "--expected-source-freeze",
            "b" * 40,
            "--output-format",
            "json",
        ]
    )

    lines = capsys.readouterr().out.splitlines()
    payload = json.loads(lines[0])
    assert exit_code == 1
    assert len(lines) == 1
    assert payload["status"] == "fail"
    assert payload["issues"][0]["code"] == "second_domain_pack_execution_failed"
    assert transition.verify_receipt(payload)
