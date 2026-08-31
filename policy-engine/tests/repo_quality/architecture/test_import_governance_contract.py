from __future__ import annotations

import ast
import json
import shutil
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tools.quality.lint import lint_imports

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = REPO_ROOT / "architecture" / "imports" / "policy.toml"
BOUNDARIES_PATH = REPO_ROOT / "architecture" / "packages" / "boundaries.toml"
SOURCE_ROOT = REPO_ROOT / "src" / "polisyos"


def _read_toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _root(module: str) -> str:
    prefix = "polisyos."
    assert module.startswith(prefix)
    return module.removeprefix(prefix).split(".", 1)[0]


def test_import_authority_contracts_declare_distinct_canonical_roles() -> None:
    policy = _read_toml(POLICY_PATH)
    boundaries = _read_toml(BOUNDARIES_PATH)

    policy_contract = policy["policy"]
    boundary_contract = boundaries["package_boundaries"]
    assert isinstance(policy_contract, dict)
    assert isinstance(boundary_contract, dict)
    assert policy_contract["contract_role"] == "enforced_direction_matrix"
    assert boundary_contract["version"] == 2
    assert boundary_contract["contract_role"] == "ownership_and_narrowing_register"

    boundary_ref = policy_contract["package_boundaries"]
    assert isinstance(boundary_ref, str)
    assert (POLICY_PATH.parent / boundary_ref).resolve() == BOUNDARIES_PATH.resolve()


def test_every_direction_root_exists_and_has_package_governance_disposition() -> None:
    policy = _read_toml(POLICY_PATH)
    boundaries = _read_toml(BOUNDARIES_PATH)

    internal = policy["internal"]
    assert isinstance(internal, dict)
    allow = internal["allow"]
    assert isinstance(allow, dict)
    matrix_roots = set(allow)
    source_roots: set[str] = set()
    for path in SOURCE_ROOT.rglob("*.py"):
        relative = path.relative_to(SOURCE_ROOT)
        if len(relative.parts) == 1:
            if path.stem != "__init__":
                source_roots.add(path.stem)
        else:
            source_roots.add(relative.parts[0])
    assert matrix_roots == source_roots
    nonexistent = sorted(root for root in matrix_roots if not (SOURCE_ROOT / root).is_dir())
    assert nonexistent == []

    packages = boundaries["package"]
    assert isinstance(packages, list)
    governed = {
        _root(entry["module"])
        for entry in packages
        if isinstance(entry, dict)
        and isinstance(entry.get("module"), str)
        and entry["module"].count(".") == 1
        and isinstance(entry.get("owner"), str)
        and entry["owner"].startswith("team-")
    }
    ungoverned_rows = boundaries["deliberately_ungoverned_root"]
    assert isinstance(ungoverned_rows, list)
    ungoverned = {
        entry["root"]
        for entry in ungoverned_rows
        if isinstance(entry, dict)
        and isinstance(entry.get("root"), str)
        and isinstance(entry.get("reason"), str)
        and entry["reason"].strip()
    }
    assert sorted(matrix_roots - governed - ungoverned) == []
    assert governed.isdisjoint(ungoverned)


def test_five_remaining_narrowings_have_one_canonical_form() -> None:
    config = lint_imports.read_policy(POLICY_PATH)

    assert config.internal_narrowings == {
        ("fabric", "data_forge"): ("polisyos.data_forge.read_api",),
        ("foundry", "data_forge"): ("polisyos.data_forge.read_api",),
        ("ir", "data_forge"): ("polisyos.data_forge.read_api",),
        ("lex", "data_forge"): ("polisyos.data_forge.read_api",),
        ("scientist", "data_forge"): ("polisyos.data_forge.read_api",),
    }


def test_runtime_corpus_edge_is_replaced_by_live_projection_denominator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real projector rejects a short corpus before owner-worker validation."""

    from polisyos.runtime.http.services import governed_projections

    source = REPO_ROOT / "tests" / "fixtures" / "universal-corpus"
    target = tmp_path / "tests" / "fixtures" / "universal-corpus"
    target.parent.mkdir(parents=True)
    shutil.copytree(source, target)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fixtures"] = manifest["fixtures"][:-1]
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    owner_validation_calls: list[object] = []

    def fail_if_called(**kwargs: object) -> object:
        owner_validation_calls.append(kwargs)
        raise AssertionError("short source must fail before owner-worker validation")

    monkeypatch.setattr(governed_projections, "_run_owner_validation", fail_if_called)
    packet = governed_projections.GovernedProjectionService(tmp_path).get(
        governed_projections.ProjectionId.LEGACY_PROVING_GROUND
    )

    assert packet.availability is governed_projections.ProjectionAvailability.INVALID_SOURCE
    assert packet.source is not None
    assert packet.source.validation.status == "not_run"
    assert packet.source.validation.issue_codes == ("projection_contract_invalid",)
    assert owner_validation_calls == []

    corpus_rows: list[tuple[str, str]] = []
    runtime_root = SOURCE_ROOT / "runtime"
    for path in sorted(runtime_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            targets: tuple[str, ...]
            if isinstance(node, ast.Import):
                targets = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                targets = (node.module,)
            else:
                continue
            for target_module in targets:
                if target_module == "polisyos.corpus" or target_module.startswith(
                    "polisyos.corpus."
                ):
                    corpus_rows.append(
                        (path.relative_to(SOURCE_ROOT).as_posix(), target_module)
                    )
    assert corpus_rows == []

    worker = (
        runtime_root / "http" / "services" / "governed_projection_validation_worker.py"
    ).read_text(encoding="utf-8")
    assert "tests/fixtures/universal-corpus" not in worker


def test_scientist_runtime_declared_cycle_is_removed_after_eval_safety_split() -> None:
    """Scientist consumes neutral EvalSafety vocabulary only through PDC."""

    policy = _read_toml(POLICY_PATH)
    internal = policy["internal"]
    assert isinstance(internal, dict)
    allow = internal["allow"]
    assert isinstance(allow, dict)
    scientist_allow = allow["scientist"]
    assert isinstance(scientist_allow, list)

    pdc_allow = allow["pdc"]
    assert isinstance(pdc_allow, list)
    assert "runtime" not in scientist_allow
    assert "pdc" in scientist_allow
    assert "runtime" not in pdc_allow
    assert "scientist" not in pdc_allow

    runtime_rows: list[tuple[str, str, tuple[str, ...], str]] = []
    scientist_root = SOURCE_ROOT / "scientist"
    for path in sorted(scientist_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            targets: tuple[tuple[str, tuple[str, ...]], ...]
            if isinstance(node, ast.Import):
                targets = tuple((alias.name, (alias.name,)) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                targets = ((node.module, tuple(alias.name for alias in node.names)),)
            else:
                continue
            parent = parents.get(node)
            scope = "module"
            while parent is not None:
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    scope = "deferred"
                    break
                parent = parents.get(parent)
            for target, aliases in targets:
                if target == "polisyos.runtime" or target.startswith("polisyos.runtime."):
                    runtime_rows.append(
                        (
                            path.relative_to(SOURCE_ROOT).as_posix(),
                            target,
                            aliases,
                            scope,
                        )
                    )

    assert runtime_rows == []


def test_pdc_eval_safety_verifier_rejects_hand_constructed_receipt() -> None:
    """Neither public shape nor direct marker construction can impersonate Runtime."""

    from polisyos.core import components as core_components
    from polisyos.pdc import (
        ArtifactRef,
        EvalSafetyAdmissionChallenge,
        EvalSafetyConsumerAdmissionReceipt,
        EvaluationExecutionContext,
        evaluation_execution_context_hash,
        evaluation_safety_consumer_admission_is_verified,
    )
    from polisyos.runtime.quality.evaluation_safety import (
        _ProducedEvalSafetyConsumerAdmissionReceipt,
    )

    def ref(index: int, kind: str) -> ArtifactRef:
        digest = f"sha256:{index:064x}"
        return ArtifactRef(
            artifact_id=digest,
            artifact_type=f"test.{kind}",
            content_hash=digest,
            schema_ref=f"test.{kind}.v1",
            uri=f"cas://sha256/{digest.removeprefix('sha256:')}",
            version="1.0",
        )

    owner = core_components.ComponentId("polisyos.scientist.eval_safety@1.0.0")
    context = EvaluationExecutionContext(
        intake_ref=ref(1, "intake"),
        evaluator_owner_id=owner,
        design_problem_ref=f"sha256:{2:064x}",
        evaluation_mode="field_pilot",
        candidate_ref=ref(3, "candidate"),
        world_model_record_ref=ref(4, "world-model"),
        target_population_scope_ref=ref(5, "population"),
        rule_version="policyos.runtime.eval-safety.v1",
        intended_start_at=datetime(2026, 8, 31, tzinfo=UTC),
        evaluation_input_refs=(),
        evaluation_input_provenance=(),
        eval_safety_certificate_ref=ref(6, "certificate"),
        eval_safety_revision_head_ref=ref(7, "revision"),
    )
    challenge = EvalSafetyAdmissionChallenge.fresh(consumer_component_id=owner)
    receipt_fields = {
        "status": "verified",
        "intake_ref": context.intake_ref,
        "certificate_ref": context.eval_safety_certificate_ref,
        "current_revision_head_ref": context.eval_safety_revision_head_ref,
        "execution_context_hash": evaluation_execution_context_hash(context),
        "challenge": challenge,
        "blocker_codes": (),
        "verified_at": datetime(2026, 8, 31, tzinfo=UTC),
    }
    forged_receipts = (
        EvalSafetyConsumerAdmissionReceipt(**receipt_fields),
        _ProducedEvalSafetyConsumerAdmissionReceipt(**receipt_fields),
    )

    assert all(
        not evaluation_safety_consumer_admission_is_verified(
            forged,
            context,
            challenge,
        )
        for forged in forged_receipts
    )


def test_observability_truthfulness_consumers_use_the_exact_ir_facade() -> None:
    """The IR-owned family has no cross-package Core deep-import route."""

    rows: list[tuple[str, str, tuple[str, ...]]] = []
    deep_prefix = "polisyos.core.observability."
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(SOURCE_ROOT)
        if relative.parts[0] == "core":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 0 or not node.module:
                continue
            if node.module.startswith(deep_prefix):
                rows.append(
                    (
                        relative.as_posix(),
                        node.module,
                        tuple(sorted(alias.name for alias in node.names)),
                    )
                )

    assert rows == []

    from polisyos.ir import analytics
    from polisyos.ir.api import ANALYTICS_FACADE_EXPORTS

    truthfulness_names = {
        "TruthfulnessReceipt",
        "TruthfulnessScope",
        "TruthfulnessStatus",
        "TruthfulnessTier",
        "extract_truthfulness_receipt",
        "parse_truthfulness_scope",
        "parse_truthfulness_tier",
        "reconcile_truthfulness_tiers",
        "truthfulness_depth",
        "validate_truthfulness_receipt",
    }
    assert truthfulness_names <= set(ANALYTICS_FACADE_EXPORTS)
    assert {name for name in truthfulness_names if getattr(analytics, name) is None} == set()

    stub = SOURCE_ROOT / "foundry" / "methods" / "base.pyi"
    stub_tree = ast.parse(stub.read_text(encoding="utf-8"), filename=str(stub))
    stub_modules = {
        node.module
        for node in ast.walk(stub_tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
    }
    assert "polisyos.core.observability" in stub_modules
    assert not any(module.startswith(deep_prefix) for module in stub_modules)
