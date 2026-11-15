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


def test_foundry_uses_public_shared_calibration_and_keeps_other_edges_closed() -> None:
    config = lint_imports.read_policy(POLICY_PATH)
    boundaries = _read_toml(BOUNDARIES_PATH)
    boundary_rows = boundaries.get("package")
    assert isinstance(boundary_rows, list)
    foundry_boundary = next(
        item
        for item in boundary_rows
        if isinstance(item, dict) and item.get("module") == "polisyos.foundry"
    )
    calibration_boundary = next(
        item
        for item in boundary_rows
        if isinstance(item, dict) and item.get("module") == "polisyos.calibration"
    )
    assert isinstance(foundry_boundary, dict)
    assert isinstance(calibration_boundary, dict)

    foundry_allowed = foundry_boundary.get("allowed_dependencies")
    foundry_forbidden = foundry_boundary.get("forbidden_dependencies")
    calibration_allowed = calibration_boundary.get("allowed_dependencies")
    assert isinstance(foundry_allowed, list)
    assert isinstance(foundry_forbidden, list)
    assert isinstance(calibration_allowed, list)
    assert "polisyos.calibration" in foundry_allowed
    assert "polisyos.calibration" not in foundry_forbidden
    assert {"polisyos.scientist", "polisyos.runtime", "polisyos.lex"} <= set(foundry_forbidden)
    assert set(calibration_allowed) == {
        "polisyos.core",
        "polisyos.ir",
        "polisyos.common",
    }
    assert config.internal_allow["calibration"] == {"calibration", "core", "ir", "common"}
    assert "calibration" in config.internal_allow["foundry"]
    assert not {"scientist", "runtime", "lex"}.intersection(config.internal_allow["foundry"])

    foundry_contract = _read_toml(REPO_ROOT / "architecture/packages/foundry.toml")
    foundry_contract_boundaries = foundry_contract.get("boundaries")
    assert isinstance(foundry_contract_boundaries, dict)
    assert foundry_contract_boundaries.get("allowed_dependencies") == foundry_allowed
    assert foundry_contract_boundaries.get("forbidden_dependencies") == foundry_forbidden

    calibration_contract = _read_toml(REPO_ROOT / "architecture/packages/calibration.toml")
    calibration_contract_boundaries = calibration_contract.get("boundaries")
    assert isinstance(calibration_contract_boundaries, dict)
    assert calibration_contract_boundaries.get("allowed_dependencies") == calibration_allowed
    calibration_public_surface = calibration_contract.get("public_surface")
    assert isinstance(calibration_public_surface, dict)
    public_entrypoints = calibration_public_surface.get("supported_entrypoints")
    assert public_entrypoints == ["polisyos.calibration"]

    advanced_path = SOURCE_ROOT / "foundry/methods/catalog/econometrics/advanced.py"
    advanced_tree = ast.parse(
        advanced_path.read_text(encoding="utf-8"), filename=str(advanced_path)
    )
    public_calibration_imports = [
        (node.module, tuple(alias.name for alias in node.names))
        for node in ast.walk(advanced_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "polisyos.calibration"
    ]
    assert public_calibration_imports == [
        (
            "polisyos.calibration",
            (
                "evaluate_continuous",
                "load_continuous_evaluation",
                "persist_continuous_evaluation",
            ),
        )
    ]

    import_contract_data = _read_toml(REPO_ROOT / "architecture/imports/contracts.toml")
    importlinter = import_contract_data.get("importlinter")
    assert isinstance(importlinter, dict)
    import_contracts = importlinter.get("contracts")
    assert isinstance(import_contracts, list)
    layer_contract = next(
        item
        for item in import_contracts
        if isinstance(item, dict) and item.get("name") == "Layered architecture"
    )
    foundry_contract_rule = next(
        item
        for item in import_contracts
        if isinstance(item, dict) and item.get("name") == "Foundry remains domain neutral"
    )
    assert isinstance(layer_contract, dict)
    assert isinstance(foundry_contract_rule, dict)
    layers = layer_contract.get("layers")
    assert isinstance(layers, list)
    layer_positions = {
        module.strip(): index for index, layer in enumerate(layers) for module in layer.split("|")
    }
    assert layer_positions["polisyos.foundry"] < layer_positions["polisyos.calibration"]
    assert layer_positions["polisyos.calibration"] < layer_positions["polisyos.core"]

    forbidden_modules = foundry_contract_rule.get("forbidden_modules")
    assert isinstance(forbidden_modules, list)
    assert "polisyos.calibration" not in forbidden_modules
    assert {"polisyos.scientist", "polisyos.runtime", "polisyos.lex"} <= set(forbidden_modules)
    assert foundry_contract_rule.get("allow_indirect_imports", False) is not True

    direct_facade_contract = next(
        item
        for item in import_contracts
        if isinstance(item, dict)
        and item.get("name") == "Foundry imports calibration through its public facade"
    )
    assert direct_facade_contract == {
        "name": "Foundry imports calibration through its public facade",
        "type": "forbidden",
        "source_modules": ["polisyos.foundry"],
        "forbidden_modules": ["polisyos.calibration.**"],
        "allow_indirect_imports": True,
    }


def test_calibration_facade_and_boundary_checks_use_real_import_edges(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from tools.quality.validation import architecture_report_only_contracts

    repo_root = tmp_path / "architecture-fixture"
    policy_path = repo_root / "architecture/imports/policy.toml"
    boundary_path = repo_root / "architecture/packages/boundaries.toml"
    public_path = repo_root / "architecture/public_surface/contract.toml"
    source_root = repo_root / "src/polisyos"

    fixture_files = {
        policy_path: """\
[policy]
version = "2"
contract_role = "enforced_direction_matrix"
package_boundaries = "../packages/boundaries.toml"
internal_prefix = "polisyos"
src_root = "../../src"

[roots]
known = ["foundry", "calibration", "scientist", "core"]

[internal.allow]
foundry = ["foundry", "calibration", "core"]
calibration = ["calibration", "core"]
scientist = ["scientist", "core"]
core = ["core"]
""",
        boundary_path: """\
[package_boundaries]
version = 2
contract_role = "ownership_and_narrowing_register"

[[package]]
module = "polisyos.foundry"
owner = "team-foundry"
allowed_dependencies = ["polisyos.foundry", "polisyos.calibration", "polisyos.core"]
forbidden_dependencies = ["polisyos.scientist"]

[[package]]
module = "polisyos.calibration"
owner = "team-scientist"
allowed_dependencies = ["polisyos.calibration", "polisyos.core"]
forbidden_dependencies = []

[[package]]
module = "polisyos.scientist"
owner = "team-scientist"
allowed_dependencies = ["polisyos.scientist", "polisyos.core"]
forbidden_dependencies = []

[[package]]
module = "polisyos.core"
owner = "team-core"
allowed_dependencies = ["polisyos.core"]
forbidden_dependencies = []
""",
        public_path: """\
[[package]]
module = "polisyos.foundry"
supported_entrypoints = ["polisyos.foundry"]

[[package]]
module = "polisyos.calibration"
supported_entrypoints = ["polisyos.calibration"]

[[package]]
module = "polisyos.scientist"
supported_entrypoints = ["polisyos.scientist"]

[[package]]
module = "polisyos.core"
supported_entrypoints = ["polisyos.core"]
""",
        source_root / "foundry/__init__.py": "",
        source_root / "foundry/consumer.py": (
            "from polisyos.calibration import evaluate_continuous\n"
        ),
        source_root / "calibration/__init__.py": (
            "from polisyos.calibration.diagnostics.continuous import evaluate_continuous\n"
        ),
        source_root / "calibration/diagnostics/__init__.py": "",
        source_root / "calibration/diagnostics/continuous.py": (
            "def evaluate_continuous():\n    return None\n"
        ),
        source_root / "scientist/__init__.py": "",
        source_root / "core/__init__.py": "",
    }
    for path, content in fixture_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_import_policy() -> int:
        return lint_imports.main(
            [
                "--policy",
                str(policy_path),
                "--exceptions",
                str(repo_root / "architecture/imports/exceptions.toml"),
                "--cache-dir",
                str(tmp_path / "import-cache"),
            ]
        )

    # A real Foundry consumer imports the supported facade; the facade itself
    # resolves its private implementation. Both architecture collectors accept
    # this path, and the direction-matrix linter accepts the package edge.
    hidden_edges = architecture_report_only_contracts._collect_hidden_import_edges(repo_root)
    forbidden_edges = architecture_report_only_contracts._collect_forbidden_package_edges(repo_root)
    assert not any(key.startswith("polisyos.foundry.consumer->") for key in hidden_edges)
    assert not any(key.startswith("polisyos.foundry.consumer->") for key in forbidden_edges)
    assert run_import_policy() == 0
    capsys.readouterr()

    # Directly reaching into the implementation is rejected by the real AST
    # edge collector, while the facade's own same-package import remains valid.
    (source_root / "foundry/consumer.py").write_text(
        "from polisyos.calibration.diagnostics.continuous import evaluate_continuous\n",
        encoding="utf-8",
    )
    hidden_edges = architecture_report_only_contracts._collect_hidden_import_edges(repo_root)
    assert "polisyos.foundry.consumer->polisyos.calibration.diagnostics.continuous" in (
        hidden_edges
    )
    (source_root / "foundry/consumer.py").write_text(
        "from polisyos.calibration import evaluate_continuous\n",
        encoding="utf-8",
    )

    # Upper-layer imports are rejected by the package-boundary collector and
    # the enforced direction matrix.
    (source_root / "foundry/upper.py").write_text("import polisyos.scientist\n", encoding="utf-8")
    forbidden_edges = architecture_report_only_contracts._collect_forbidden_package_edges(repo_root)
    assert "polisyos.foundry.upper->polisyos.scientist" in forbidden_edges
    assert run_import_policy() != 0
    capsys.readouterr()
    (source_root / "foundry/upper.py").unlink()

    # Calibration is a lower peer and cannot depend back on Foundry.
    (source_root / "calibration/consumer.py").write_text(
        "import polisyos.foundry\n", encoding="utf-8"
    )
    assert run_import_policy() != 0
    assert "calibration -> foundry" in capsys.readouterr().out


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
                    corpus_rows.append((path.relative_to(SOURCE_ROOT).as_posix(), target_module))
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
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
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
