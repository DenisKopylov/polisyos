"""Owner for extracted DS11 trust-claim posture logic."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from polisyos.scientist.evidence.claims.posture import (
    ClaimPostureRegisterV1,
    ClaimPostureState,
    GeneratedFamilyBinding,
    SourceResolution,
    validate_posture_register,
)
from tools.quality.validation.trust_claim_posture_contracts import (
    _PostureInspectionError,
)


@dataclass(frozen=True, slots=True)
class LifecycleDependencies:
    """Bind this owner to the active facade collaborators."""

    admitted_is_file: Callable[..., Any]
    admitted_read_bytes: Callable[..., Any]
    admitted_read_text: Callable[..., Any]
    reject_owner_predicate: Callable[..., Any]
    require_contained_path: Callable[..., Any]
    compile_claim_posture_register: Callable[..., Any]
    derive_accessibility_document: Callable[..., Any]
    derive_identity_boundary: Callable[..., Any]
    validate_claim_copy: Callable[..., Any]
    a11y_path: Path
    corruption_reason_codes: Mapping[str, tuple[str, ...]]
    debt_register_path: Path
    generated_manifest_path: Path
    generated_reference_path: Path
    identity_path: Path
    output_path: Path


def validate_generated_family(
    repo_root: Path, *, dependencies: LifecycleDependencies
) -> GeneratedFamilyBinding:
    """Parse the existing manifest owner and admit only the strict posture family."""
    from tools.devx.architecture import guardrails

    root = repo_root.resolve()
    manifest = (root / dependencies.generated_manifest_path).resolve()
    dependencies.require_contained_path(
        manifest,
        root,
        code="DS11-GENERATED-FAMILY-CONTRACT",
        stage="generated_manifest_containment",
        label="generated-artifact manifest",
    )
    if not dependencies.admitted_is_file(
        manifest,
        root,
        code="DS11-GENERATED-FAMILY-CONTRACT",
        stage="generated_manifest_presence",
        label="generated-artifact manifest",
    ):
        raise ValueError("generated-artifact manifest is missing")
    raw_manifest = dependencies.admitted_read_bytes(
        manifest,
        root,
        code="DS11-GENERATED-FAMILY-CONTRACT",
        stage="generated_manifest_read",
        label="generated-artifact manifest",
    )
    try:
        families = guardrails._parse_generated_artifacts(raw_manifest)
    except tomllib.TOMLDecodeError, UnicodeError:
        raise
    except AttributeError, KeyError, TypeError, ValueError:
        dependencies.reject_owner_predicate(
            "DS11-GENERATED-FAMILY-CONTRACT",
            "generated_family_manifest_schema",
            "generated-artifact manifest violates its declared family schema",
        )
    matches = [item for item in families if item.family_id == "trust-claim-posture-register"]
    if len(matches) != 1:
        dependencies.reject_owner_predicate(
            "DS11-GENERATED-FAMILY-CONTRACT",
            "generated_family_cardinality",
            "trust posture generated family must appear exactly once",
        )
    family = matches[0]
    outputs = tuple(path.relative_to(guardrails.REPO_ROOT).as_posix() for path in family.outputs)

    def rebase_probe_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
        rebased: list[Path] = []
        for path in paths:
            candidate = path if path.is_absolute() else guardrails.REPO_ROOT / path
            try:
                relative = candidate.relative_to(guardrails.REPO_ROOT)
            except ValueError:
                dependencies.reject_owner_predicate(
                    "DS11-GENERATED-FAMILY-CONTRACT",
                    "generated_family_probe_path_containment",
                    f"trust posture probe input is outside the declared repository: {candidate}",
                )
                raise AssertionError("owner predicate rejection must raise") from None
            rebased.append(root / relative)
        return tuple(rebased)

    probe = family.output_probe_command
    if (
        family.lifecycle != "generated_committed"
        or family.stale_output_behavior != "fail"
        or outputs != (dependencies.output_path.as_posix(),)
        or family.default_freshness_check is not True
        or probe is None
        or sum("{output_root}" in item for item in probe) != 1
        or "--write" not in probe
        or "--output-root" not in probe
        or family.check_git_diff_paths
    ):
        dependencies.reject_owner_predicate(
            "DS11-GENERATED-FAMILY-CONTRACT",
            "generated_family_writer_contract",
            "trust posture generated family violates the strict writer contract",
        )
    return GeneratedFamilyBinding(
        family_id="trust-claim-posture-register",
        lifecycle="generated_committed",
        stale_output_behavior="fail",
        outputs=outputs,
        default_freshness_check=True,
        output_probe_command=probe,
        probe_input_roots=rebase_probe_paths(family.probe_input_roots),
        probe_required_paths=rebase_probe_paths(family.probe_required_paths),
        probe_runtime_paths=rebase_probe_paths(family.probe_runtime_paths),
    )


def run_generated_family_output_probe(
    repo_root: Path, *, source_root: Path, output_root: Path, dependencies: LifecycleDependencies
) -> tuple[str, ...]:
    """Execute the manifest probe in an isolated source and prove exact output bytes."""
    from tools.devx.architecture import guardrails

    family = validate_generated_family(repo_root, dependencies=dependencies)
    repo = repo_root.resolve()
    source = source_root.resolve()
    output = output_root.resolve()
    if source.parent != output.parent or source == output:
        raise ValueError("output probe source_root and output_root must be dedicated siblings")
    if source.exists() or output.exists():
        raise ValueError("output probe source_root and output_root must not already exist")
    if source.is_relative_to(repo) or output.is_relative_to(repo):
        raise ValueError("output probe scratch roots must be outside repo_root")

    guardrails._copy_isolated_probe_source(repo, source, families=(family,))
    if (source / ".git").exists():
        raise ValueError("output probe source_root must not contain .git")
    output.mkdir(parents=True)
    temporary_root = output / ".tmp"
    temporary_root.mkdir()

    rendered_command = tuple(
        item.replace("{output_root}", str(output)) for item in family.output_probe_command
    )
    executable_path = os.pathsep.join(
        (str(source / ".venv/bin"), str(Path(sys.executable).parent), "/usr/bin", "/bin")
    )
    if shutil.which(rendered_command[0], path=executable_path) is None:
        raise _PostureInspectionError(
            f"generated-family output probe executable is unavailable: {rendered_command[0]}",
            stage="generated_family_output_command",
            dependencies=dependencies,
        )
    environment = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": executable_path,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": os.pathsep.join((str(source / "src"), str(source))),
        "TMPDIR": str(temporary_root),
        "TZ": "UTC",
    }

    governed_root = guardrails._mapped_governed_artifact_root(
        repo,
        source,
        (family,),
        os.environ.get("POLISYOS_GOVERNED_ARTIFACT_ROOT"),
    )
    if governed_root is not None:
        environment["POLISYOS_GOVERNED_ARTIFACT_ROOT"] = governed_root

    scratch_root = source.parent
    output_prefix = output.relative_to(scratch_root).as_posix()

    def outside_output_snapshot() -> dict[str, str]:
        return {
            relative: state
            for relative, state in guardrails._snapshot_filesystem_tree(scratch_root).items()
            if relative != output_prefix and not relative.startswith(f"{output_prefix}/")
        }

    repo_before = guardrails._snapshot_filesystem_tree(repo)
    scratch_before = outside_output_snapshot()
    completed = subprocess.run(  # noqa: S603 - exact trusted manifest argv; no shell.
        rendered_command,
        cwd=source,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    repo_changes = guardrails._changed_snapshot_paths(
        repo_before,
        guardrails._snapshot_filesystem_tree(repo),
    )
    scratch_changes = guardrails._changed_snapshot_paths(
        scratch_before,
        outside_output_snapshot(),
    )
    escaped = tuple(sorted({*repo_changes, *(f"scratch/{item}" for item in scratch_changes)}))
    if escaped:
        dependencies.reject_owner_predicate(
            "DS11-GENERATED-FAMILY-PROBE",
            "generated_family_output_containment",
            "generated-family output probe wrote outside output_root",
        )
    if completed.returncode != 0:
        raise _PostureInspectionError(
            f"generated-family output probe command exited {completed.returncode}",
            stage="generated_family_output_command",
            dependencies=dependencies,
        )

    output_paths = tuple(output.rglob("*"))
    observed_paths: list[str] = []
    for path in output_paths:
        if dependencies.admitted_is_file(
            path,
            output,
            code="DS11-GENERATED-FAMILY-PROBE",
            stage="generated_family_candidate_containment",
            label="generated-family candidate output",
        ):
            observed_paths.append(path.relative_to(output).as_posix())
    observed = tuple(sorted(observed_paths))
    if observed != family.outputs:
        dependencies.reject_owner_predicate(
            "DS11-GENERATED-FAMILY-PROBE",
            "generated_family_output_set",
            "generated-family output probe differs from declared outputs",
        )
    for relative in observed:
        expected = repo / relative
        candidate = output / relative
        if not dependencies.admitted_is_file(
            expected,
            repo,
            code="DS11-GENERATED-FAMILY-PROBE",
            stage="generated_family_expected_containment",
            label="committed generated-family output",
        ):
            dependencies.reject_owner_predicate(
                "DS11-GENERATED-FAMILY-PROBE",
                "generated_family_committed_output_presence",
                f"generated-family committed artifact is missing: {relative}",
            )
        candidate_bytes = dependencies.admitted_read_bytes(
            candidate,
            output,
            code="DS11-GENERATED-FAMILY-PROBE",
            stage="generated_family_candidate_read",
            label="generated-family candidate output",
        )
        expected_bytes = dependencies.admitted_read_bytes(
            expected,
            repo,
            code="DS11-GENERATED-FAMILY-PROBE",
            stage="generated_family_expected_read",
            label="committed generated-family output",
        )
        if candidate_bytes != expected_bytes:
            dependencies.reject_owner_predicate(
                "DS11-GENERATED-FAMILY-PROBE",
                "generated_family_output_bytes",
                f"generated-family output differs from committed artifact: {relative}",
            )
    return observed


def write_generated_reference(
    repo_root: Path, *, output_root: Path | None = None, dependencies: LifecycleDependencies
) -> Path:
    """Render only the generated-artifact reference through its existing owner."""
    from tools.devx.architecture import guardrails

    root = repo_root.resolve()
    target_root = (output_root or root).resolve()
    manifest = (root / dependencies.generated_manifest_path).resolve()
    validate_generated_family(root, dependencies=dependencies)
    target = (target_root / dependencies.generated_reference_path).resolve()
    dependencies.require_contained_path(
        target,
        target_root,
        code="DS11-GENERATED-FAMILY-CONTRACT",
        stage="generated_reference_containment",
        label="generated reference target",
    )
    raw_manifest = dependencies.admitted_read_bytes(
        manifest,
        root,
        code="DS11-GENERATED-FAMILY-CONTRACT",
        stage="generated_manifest_read",
        label="generated-artifact manifest",
    )
    rendered = guardrails.render_generated_artifacts_markdown(
        guardrails._parse_generated_artifacts(raw_manifest)
    ).encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(rendered)
    return target


def validate_register_against_live_sources(
    payload: bytes, *, repo_root: Path, register_as_of: date, dependencies: LifecycleDependencies
) -> ClaimPostureRegisterV1:
    """Validate strict bytes and require equality with a live recompilation."""
    parsed = validate_posture_register(payload)
    live, live_bytes = dependencies.compile_claim_posture_register(
        repo_root, register_as_of=register_as_of
    )
    if payload != live_bytes:
        dependencies.reject_owner_predicate(
            "DS11-GENERATED-DRIFT",
            "generated_artifact_byte_equality",
            "DS11-GENERATED-DRIFT",
        )
    return live if parsed == live else parsed


def run_corruption_probe(
    kind: str, *, repo_root: Path, register_as_of: date, dependencies: LifecycleDependencies
) -> bool:
    """Require a corrupted live payload to fail strict validation."""
    register, _ = dependencies.compile_claim_posture_register(
        repo_root, register_as_of=register_as_of
    )
    payload = register.model_dump(mode="json")
    if kind == "extra_field":
        payload["unexpected"] = True
    elif kind == "payload_digest":
        payload["payload_digest"] = "sha256:" + "0" * 64
    else:
        raise ValueError(f"unsupported corruption probe: {kind}")
    try:
        validate_posture_register(payload)
    except ValueError:
        return True
    return False


def run_corruption_probes(
    *, repo_root: Path, register_as_of: date, dependencies: LifecycleDependencies
) -> dict[str, object]:
    """Run the closed C05 semantic mutation wave entirely in scratch roots."""
    root = repo_root.resolve()
    before = _bounded_filesystem_snapshot(root, dependencies=dependencies)
    register, canonical = dependencies.compile_claim_posture_register(
        root, register_as_of=register_as_of
    )
    outcomes: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="ds11-corruption-") as temporary:
        scratch = Path(temporary).resolve()
        outcomes["planned_to_supported"] = _status_projection_is_rejected(
            register, source_state="planned"
        )
        outcomes["candidate_to_supported"] = _candidate_projection_is_rejected(
            root,
            scratch / "candidate",
            register_as_of=register_as_of,
            dependencies=dependencies,
        )
        outcomes["forbidden_purpose_removal"] = _live_payload_mutation_is_rejected(
            register,
            root,
            _remove_forbidden_purpose,
            register_as_of=register_as_of,
            dependencies=dependencies,
        )
        outcomes["review_refresh_without_evidence"] = _live_payload_mutation_is_rejected(
            register,
            root,
            _refresh_review_without_evidence,
            register_as_of=register_as_of,
            dependencies=dependencies,
        )
        outcomes["source_digest_rebinding"] = _source_digest_rebinding_is_rejected(
            root,
            scratch / "source-rebinding",
            register_as_of=register_as_of,
            dependencies=dependencies,
        )
        outcomes["body_fact_removal"] = _body_fact_removal_is_rejected(
            root, scratch / "body-fact", dependencies=dependencies
        )
        outcomes["scope_assumption_change"] = _payload_mutation_is_rejected(
            register, _change_scope_assumption
        )
        outcomes["anti_role_removal"] = _anti_role_mutation_is_rejected(
            root,
            scratch / "anti-role",
            ", not an executor",
            dependencies=dependencies,
        )
        outcomes["crm_omission"] = _anti_role_mutation_is_rejected(
            root,
            scratch / "crm",
            "\nnot a CRM",
            dependencies=dependencies,
        )
        outcomes["manages_your_cases"] = dependencies.validate_claim_copy(
            "manages your cases", source_row=None
        ) == ("DS11-IDENTITY-COPY-UNBOUND",)
        outcomes["performance_relabel"] = _payload_mutation_is_rejected(
            register, _relabel_as_performance
        )
        outcomes["limitation_omission"] = _payload_mutation_is_rejected(register, _omit_limitation)
        outcomes["row_reorder"] = _payload_mutation_is_rejected(register, _reorder_rows)
        outcomes["machine_reserialization"] = _machine_reserialization_is_rejected(
            register, canonical
        )
        outcomes["dynamic_source_silently_dropped"] = _dynamic_source_drop_is_rejected(
            root,
            scratch / "dynamic",
            register_as_of=register_as_of,
            dependencies=dependencies,
        )
    after = _bounded_filesystem_snapshot(root, dependencies=dependencies)
    escaped = sorted(
        path for path in before.keys() | after.keys() if before.get(path) != after.get(path)
    )
    results = []
    for probe_id in sorted(dependencies.corruption_reason_codes):
        rejected = outcomes.get(probe_id, False)
        results.append(
            {
                "probe_id": probe_id,
                "outcome": "rejected" if rejected else "escaped",
                "reason_codes": list(dependencies.corruption_reason_codes[probe_id])
                if rejected
                else [],
                "declared_outputs": [],
                "write_set": [],
            }
        )
    return {
        "probe_count": len(results),
        "rejected_count": sum(item["outcome"] == "rejected" for item in results),
        "scratch_escape_count": len(escaped),
        "scratch_escape_paths": escaped,
        "results": results,
    }


def _bounded_filesystem_snapshot(
    root: Path, *, dependencies: LifecycleDependencies
) -> dict[str, str]:
    excluded = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "_build",
        "_cache",
        "node_modules",
        "production_data",
    }
    snapshot: dict[str, str] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts):
            continue
        if path.is_symlink():
            snapshot[relative.as_posix()] = "link:" + os.readlink(path)
        elif dependencies.admitted_is_file(
            path,
            root,
            code="DS11-CORRUPTION-PROBE-BOUNDARY",
            stage="corruption_snapshot_path_containment",
            label="corruption probe snapshot member",
        ):
            snapshot[relative.as_posix()] = (
                "sha256:"
                + hashlib.sha256(
                    dependencies.admitted_read_bytes(
                        path,
                        root,
                        code="DS11-CORRUPTION-PROBE-BOUNDARY",
                        stage="corruption_snapshot_read",
                        label="corruption probe snapshot member",
                    )
                ).hexdigest()
            )
    return snapshot


def _minimal_probe_repo(
    root: Path,
    source: str,
    *,
    basis_root: Path,
    source_name: str = "probe.py",
    dependencies: LifecycleDependencies,
) -> Path:
    source_path = root / "src/polisyos" / source_name
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(source, encoding="utf-8")
    identity = root / dependencies.identity_path
    identity.parent.mkdir(parents=True, exist_ok=True)
    identity.write_bytes(
        dependencies.admitted_read_bytes(
            basis_root / dependencies.identity_path,
            basis_root,
            code="DS11-CORRUPTION-PROBE-BOUNDARY",
            stage="corruption_probe_identity_input_read",
            label="corruption probe identity source",
        )
    )
    debt_register = root / dependencies.debt_register_path
    debt_register.parent.mkdir(parents=True, exist_ok=True)
    debt_register.write_bytes(
        dependencies.admitted_read_bytes(
            basis_root / dependencies.debt_register_path,
            basis_root,
            code="DS11-CORRUPTION-PROBE-BOUNDARY",
            stage="corruption_probe_custody_input_read",
            label="corruption probe custody source",
        )
    )
    return root


def _payload_with_digest(payload: Mapping[str, object]) -> dict[str, object]:
    rebound = json.loads(json.dumps(payload, ensure_ascii=False))
    unsigned = {key: value for key, value in rebound.items() if key != "payload_digest"}
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    rebound["payload_digest"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return rebound


def _payload_mutation_is_rejected(
    register: ClaimPostureRegisterV1, mutate: Callable[[dict[str, object]], None]
) -> bool:
    payload = register.model_dump(mode="json")
    mutate(payload)
    try:
        validate_posture_register(_payload_with_digest(payload))
    except ValueError:
        return True
    return False


def _live_payload_mutation_is_rejected(
    register: ClaimPostureRegisterV1,
    repo_root: Path,
    mutate: Callable[[dict[str, object]], None],
    *,
    register_as_of: date,
    dependencies: LifecycleDependencies,
) -> bool:
    payload = register.model_dump(mode="json")
    mutate(payload)
    rebound = _payload_with_digest(payload)
    encoded = (
        json.dumps(rebound, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    try:
        validate_register_against_live_sources(
            encoded,
            repo_root=repo_root,
            register_as_of=register_as_of,
            dependencies=dependencies,
        )
    except ValueError:
        return True
    return False


def _claim(payload: Mapping[str, object], subject: str) -> dict[str, object]:
    claims = payload.get("claims")
    if not isinstance(claims, list):
        raise ValueError("corruption payload has no claims")
    matches = [item for item in claims if isinstance(item, dict) and item.get("subject") == subject]
    if len(matches) != 1:
        raise ValueError(f"corruption payload requires one {subject} claim")
    return matches[0]


def _status_projection_is_rejected(register: ClaimPostureRegisterV1, *, source_state: str) -> bool:
    payload = register.model_dump(mode="json")
    claims = payload["claims"]
    if not isinstance(claims, list):
        return False
    row = next(
        (
            item
            for item in claims
            if isinstance(item, dict)
            and any(
                isinstance(binding, dict) and binding.get("source_state") == source_state
                for binding in item.get("source_bindings", [])
            )
        ),
        None,
    )
    if row is None:
        return False
    row["effective_state"] = "supported"
    try:
        validate_posture_register(_payload_with_digest(payload))
    except ValueError:
        return True
    return False


def _candidate_projection_is_rejected(
    basis_root: Path, root: Path, *, register_as_of: date, dependencies: LifecycleDependencies
) -> bool:
    repo = _minimal_probe_repo(
        root,
        '"""Candidate posture corruption probe."""\n\n'
        "class CandidateProbe:\n"
        '    authoritative_for = ("candidate_probe",)\n'
        '    may_not_use_for = ("publication_authority",)\n'
        '    trust_claim_posture = {"schema_version": '
        '"policyos.trust.producer_posture.v1", "subject": "candidate_probe", '
        '"source_state": "candidate", "owner": "team-scientist", '
        '"closure_signal": "pytest://candidate_probe"}\n',
        basis_root=basis_root,
        dependencies=dependencies,
    )
    register, _ = dependencies.compile_claim_posture_register(repo, register_as_of=register_as_of)
    return _status_projection_is_rejected(register, source_state="candidate")


def _remove_forbidden_purpose(payload: dict[str, object]) -> None:
    binding = _claim(payload, "system_identity")["source_bindings"][0]
    binding["may_not_use_for"] = [
        value for value in binding["may_not_use_for"] if value != "capability_claim"
    ]


def _refresh_review_without_evidence(payload: dict[str, object]) -> None:
    row = _claim(payload, "current_accessibility_conformance")
    row["review_on"] = "2026-08-26"
    row["review_due"] = "2027-08-26"
    binding = row["source_bindings"][0]
    binding["review_on"] = "2026-08-26"
    binding["review_due"] = "2027-08-26"


def _change_scope_assumption(payload: dict[str, object]) -> None:
    binding = _claim(payload, "system_identity")["source_bindings"][0]
    binding["declared_scope_assumption"] = "global"


def _relabel_as_performance(payload: dict[str, object]) -> None:
    _claim(payload, "system_identity")["family"] = "grounded_performance"


def _omit_limitation(payload: dict[str, object]) -> None:
    claims = payload["claims"]
    row = next(item for item in claims if item["limitations"])
    row["limitations"] = row["limitations"][1:]


def _reorder_rows(payload: dict[str, object]) -> None:
    payload["claims"] = list(reversed(payload["claims"]))


def _source_digest_rebinding_is_rejected(
    repo_root: Path, scratch: Path, *, register_as_of: date, dependencies: LifecycleDependencies
) -> bool:
    repo = _minimal_probe_repo(
        scratch,
        'class Probe:\n    authoritative_for = ("probe",)\n',
        basis_root=repo_root,
        dependencies=dependencies,
    )
    identity = repo / dependencies.identity_path
    text = dependencies.admitted_read_text(
        identity,
        repo,
        code="DS11-CORRUPTION-PROBE-BOUNDARY",
        stage="corruption_probe_identity_read",
        label="corruption probe identity input",
    )
    changed = text.replace("across the whole life of a", "throughout the whole life of a", 1)
    if changed == text:
        return False
    identity.write_text(changed, encoding="utf-8")
    try:
        register, _ = dependencies.compile_claim_posture_register(
            repo, register_as_of=register_as_of
        )
    except ValueError:
        return True
    row = next(item for item in register.claims if item.subject == "system_identity")
    return row.effective_state == ClaimPostureState.BLOCKED


def _body_fact_removal_is_rejected(
    repo_root: Path, scratch: Path, *, dependencies: LifecycleDependencies
) -> bool:
    repo = _minimal_probe_repo(
        scratch,
        'class Probe:\n    authoritative_for = ("probe",)\n',
        basis_root=repo_root,
        dependencies=dependencies,
    )
    source = repo_root.resolve() / dependencies.a11y_path
    target = repo / dependencies.a11y_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        dependencies.admitted_read_bytes(
            source,
            repo_root,
            code="DS11-CORRUPTION-PROBE-BOUNDARY",
            stage="corruption_probe_accessibility_input_read",
            label="corruption probe accessibility source",
        )
    )
    text = dependencies.admitted_read_text(
        target,
        repo,
        code="DS11-CORRUPTION-PROBE-BOUNDARY",
        stage="corruption_probe_accessibility_read",
        label="corruption probe accessibility input",
    )
    boundary = text.find("\n---\n", 4)
    if boundary < 0:
        return False
    frontmatter, body = text[: boundary + 5], text[boundary + 5 :]
    mutated = body.replace("- Audit status: Internal pre-audit complete", "", 1)
    if mutated == body:
        return False
    target.write_text(frontmatter + mutated, encoding="utf-8")
    try:
        dependencies.derive_accessibility_document(repo)
    except ValueError:
        return True
    return False


def _anti_role_mutation_is_rejected(
    repo_root: Path, scratch: Path, fragment: str, *, dependencies: LifecycleDependencies
) -> bool:
    baseline = dependencies.derive_identity_boundary(repo_root)
    repo = _minimal_probe_repo(
        scratch,
        'class Probe:\n    authoritative_for = ("probe",)\n',
        basis_root=repo_root,
        dependencies=dependencies,
    )
    identity = repo / dependencies.identity_path
    text = dependencies.admitted_read_text(
        identity,
        repo,
        code="DS11-CORRUPTION-PROBE-BOUNDARY",
        stage="corruption_probe_identity_read",
        label="corruption probe identity input",
    )
    changed = text.replace(fragment, "", 1)
    if changed == text:
        return False
    identity.write_text(changed, encoding="utf-8")
    try:
        mutated = dependencies.derive_identity_boundary(repo)
    except ValueError:
        return True
    return tuple(item.role for item in mutated.anti_roles) != tuple(
        item.role for item in baseline.anti_roles
    )


def _machine_reserialization_is_rejected(
    register: ClaimPostureRegisterV1, canonical: bytes
) -> bool:
    reserialized = (json.dumps(register.model_dump(mode="json"), indent=2) + "\n").encode("utf-8")
    return reserialized != canonical and validate_posture_register(reserialized) == register


def _dynamic_source_drop_is_rejected(
    basis_root: Path, root: Path, *, register_as_of: date, dependencies: LifecycleDependencies
) -> bool:
    repo = _minimal_probe_repo(
        root,
        'subjects = ("dynamic_probe",)\n\n'
        "class DynamicProbe:\n"
        "    authoritative_for = tuple(subjects)\n",
        basis_root=basis_root,
        source_name="dynamic_probe.py",
        dependencies=dependencies,
    )
    register, _ = dependencies.compile_claim_posture_register(repo, register_as_of=register_as_of)
    path = "src/polisyos/dynamic_probe.py"
    inventory = next((row for row in register.source_inventory if row.path == path), None)
    if inventory is None or inventory.resolution != SourceResolution.RUNTIME_BOUND:
        return False
    payload = register.model_dump(mode="json")
    removed_ids = {
        row["claim_id"]
        for row in payload["claims"]
        if any(binding["coordinate"]["path"] == path for binding in row["source_bindings"])
    }
    payload["source_inventory"] = [
        row for row in payload["source_inventory"] if row["path"] != path
    ]
    payload["claims"] = [row for row in payload["claims"] if row["claim_id"] not in removed_ids]
    for group in payload["projection_groups"]:
        group["claim_ids"] = [
            claim_id for claim_id in group["claim_ids"] if claim_id not in removed_ids
        ]
    rebound = _payload_with_digest(payload)
    encoded = (
        json.dumps(rebound, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    try:
        validate_register_against_live_sources(
            encoded,
            repo_root=repo,
            register_as_of=register_as_of,
            dependencies=dependencies,
        )
    except ValueError:
        return True
    return False
