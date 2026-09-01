"""Non-HTTP closure tests for the pre-N9 epoch-validity strangle."""

from __future__ import annotations

import ast
import os
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final
from uuid import uuid4

import pytest

import polisyos.runtime.http.services.control.generation_cycle as generation_cycle_service
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.design_axes.coupling_composition import (
    derive_recursive_design_graph,
)
from polisyos.runtime.quality.generation_cycle import N4GenerationPort
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleController,
    RecursiveGenerationCycleError,
    build_default_recursive_generation_cycle_controller,
)

_CONSTRUCTOR_TARGETS: Final = frozenset(
    {
        "polisyos.runtime.quality.promotion_sequence.CanonicalN9PromotionPort",
        "polisyos.runtime.quality.generation_cycle.GenerationCycleController",
        "polisyos.runtime.quality.recursive_generation_cycle.RecursiveGenerationCycleController",
        "polisyos.runtime.quality.recursive_generation_cycle."
        "build_default_recursive_generation_cycle_controller",
        "polisyos.runtime.quality.recursive_generation_cycle."
        "RecursiveGenerationCycleController.for_contract_testing",
        "polisyos.runtime.quality.promotion_sequence.CanonicalN9PromotionPort._for_verification",
    }
)
_DYNAMIC_TARGET_MARKERS: Final = frozenset(
    {
        "CanonicalN9PromotionPort",
        "GenerationCycleController",
        "RecursiveGenerationCycleController",
        "build_default_recursive_generation_cycle_controller",
    }
)


@dataclass(frozen=True)
class _CallSite:
    module: str
    source_path: str
    enclosing: str
    target: str
    keyword_names: frozenset[str]
    has_keyword_expansion: bool
    authority_scope: str | None


def _module_name(repo_root: Path, source_path: Path) -> str:
    relative = source_path.relative_to(repo_root).with_suffix("")
    parts = list(relative.parts)
    if parts[0] == "src":
        parts.pop(0)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _attribute_name(
    node: ast.expr,
    bindings: dict[str, set[str]],
    shadowed: frozenset[str] = frozenset(),
) -> set[str]:
    if isinstance(node, ast.Name):
        if node.id in shadowed:
            return set()
        return set(bindings.get(node.id, ()))
    if isinstance(node, ast.Attribute):
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr == "_promotion_port"
        ):
            return {"self._promotion_port"}
        return {
            f"{prefix}.{node.attr}" for prefix in _attribute_name(node.value, bindings, shadowed)
        }
    return set()


def _scan_python_source(
    *,
    source: str,
    module: str,
    source_path: str,
) -> tuple[tuple[_CallSite, ...], tuple[_CallSite, ...], tuple[str, ...]]:
    tree = ast.parse(source, filename=source_path)
    bindings: dict[str, set[str]] = {}
    assignments: list[tuple[str, ast.expr]] = []
    binding_ambiguities: list[str] = []
    target_modules = {target.rsplit(".", 1)[0] for target in _CONSTRUCTOR_TARGETS}
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node in tree.body
        ):
            bindings.setdefault(node.name, set()).add(f"{module}.{node.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bindings.setdefault(alias.asname or alias.name.split(".")[0], set()).add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if any(alias.name == "*" for alias in node.names):
                if (node.module or "") in target_modules:
                    binding_ambiguities.append(
                        f"{source_path}:{node.lineno}:target_module_star_import"
                    )
                continue
            imported_module = node.module or ""
            for alias in node.names:
                bindings.setdefault(alias.asname or alias.name, set()).add(
                    f"{imported_module}.{alias.name}"
                )
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            assignments.append((node.targets[0].id, node.value))

    for _ in range(len(assignments) + 1):
        changed = False
        for local_name, expression in assignments:
            resolved = _attribute_name(expression, bindings)
            if resolved and not resolved.issubset(bindings.setdefault(local_name, set())):
                bindings[local_name].update(resolved)
                changed = True
        if not changed:
            break

    constructors: list[_CallSite] = []
    promotion_calls: list[_CallSite] = []
    ambiguous: list[str] = list(binding_ambiguities)

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []
            self.shadowed: list[frozenset[str]] = []

        def _visit_scope(
            self,
            node: ast.AST,
            name: str,
            shadowed: frozenset[str] = frozenset(),
        ) -> None:
            self.scope.append(name)
            self.shadowed.append(shadowed)
            self.generic_visit(node)
            self.shadowed.pop()
            self.scope.pop()

        @staticmethod
        def _arguments(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
            arguments = node.args
            return frozenset(
                item.arg
                for item in (
                    *arguments.posonlyargs,
                    *arguments.args,
                    *arguments.kwonlyargs,
                    *([arguments.vararg] if arguments.vararg is not None else []),
                    *([arguments.kwarg] if arguments.kwarg is not None else []),
                )
            )

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            self._visit_scope(node, node.name)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            self._visit_scope(node, node.name, self._arguments(node))

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            self._visit_scope(node, node.name, self._arguments(node))

        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            keywords = frozenset(item.arg for item in node.keywords if item.arg is not None)
            row = _CallSite(
                module=module,
                source_path=source_path,
                enclosing=".".join(self.scope),
                target="",
                keyword_names=keywords,
                has_keyword_expansion=any(item.arg is None for item in node.keywords),
                authority_scope=next(
                    (
                        item.value.value
                        for item in node.keywords
                        if item.arg == "authority_scope"
                        and isinstance(item.value, ast.Constant)
                        and isinstance(item.value.value, str)
                    ),
                    None,
                ),
            )
            active_shadows = frozenset().union(*self.shadowed)
            resolved = _attribute_name(node.func, bindings, active_shadows)
            matched = resolved & _CONSTRUCTOR_TARGETS
            if matched:
                if len(matched) != 1:
                    ambiguous.append(f"{source_path}:{node.lineno}:multiple_constructor_bindings")
                else:
                    constructors.append(
                        _CallSite(**{**row.__dict__, "target": next(iter(matched))})
                    )
            elif "self._promotion_port" in resolved:
                promotion_calls.append(
                    _CallSite(**{**row.__dict__, "target": "self._promotion_port"})
                )
            else:
                rendered = ast.unparse(node.func)
                inline_constructor = (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Call)
                    and bool(
                        _attribute_name(
                            node.func.value.func,
                            bindings,
                            active_shadows,
                        )
                        & _CONSTRUCTOR_TARGETS
                    )
                )
                if (
                    any(name in rendered for name in _DYNAMIC_TARGET_MARKERS)
                    and not inline_constructor
                ):
                    ambiguous.append(f"{source_path}:{node.lineno}:{rendered}")
                elif rendered in {"getattr", "globals", "__import__", "importlib.import_module"}:
                    rendered_call = ast.unparse(node)
                    if any(name in rendered_call for name in _DYNAMIC_TARGET_MARKERS):
                        ambiguous.append(f"{source_path}:{node.lineno}:dynamic_target_resolution")
            self.generic_visit(node)

    _Visitor().visit(tree)
    return tuple(constructors), tuple(promotion_calls), tuple(ambiguous)


def _source_role(relative_path: str) -> str:
    first = relative_path.split("/", 1)[0]
    if first == "tests":
        return "test_only"
    if first == "benchmarks":
        return "benchmark_only"
    if first == "examples":
        return "example_only"
    if relative_path.startswith("docs/research/"):
        return "research_only"
    if first in {"src", "tools", "apps", "ops", "architecture"}:
        return "production_capable"
    if relative_path in {"jax_bootstrap.py", "migrate.py"}:
        return "production_capable"
    raise AssertionError(f"unclassified Python/stub path: {relative_path}")


def _production_python_paths(repo_root: Path) -> tuple[set[str], set[str]]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.py",
            "*.pyi",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    git_candidates = {row for row in result.stdout.splitlines() if row.endswith((".py", ".pyi"))}

    ignored_directory_result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--directory",
            "-z",
        ],
        check=True,
        capture_output=True,
    )
    ignored_directories = {
        item.decode().rstrip("/")
        for item in ignored_directory_result.stdout.split(b"\0")
        if item
    }
    discovered: list[str] = []
    for directory, child_dirs, files in os.walk(repo_root, followlinks=False):
        root = Path(directory)
        child_dirs[:] = [
            name
            for name in child_dirs
            if name != ".git"
            and (root / name).relative_to(repo_root).as_posix()
            not in ignored_directories
        ]
        for name in files:
            if name.endswith((".py", ".pyi")):
                discovered.append((root / name).relative_to(repo_root).as_posix())
    payload = b"\0".join(item.encode() for item in discovered)
    if payload:
        payload += b"\0"
    ignored = subprocess.run(
        ["git", "check-ignore", "--stdin", "-z"],
        cwd=repo_root,
        input=payload,
        check=False,
        capture_output=True,
    )
    if ignored.returncode not in {0, 1}:
        raise AssertionError(ignored.stderr.decode(errors="replace"))
    ignored_paths = {item.decode() for item in ignored.stdout.split(b"\0") if item}
    filesystem_candidates = set(discovered) - ignored_paths

    return (
        {row for row in git_candidates if _source_role(row) == "production_capable"},
        {row for row in filesystem_candidates if _source_role(row) == "production_capable"},
    )


def _assert_constructor_contract(
    constructors: tuple[_CallSite, ...],
    promotion_calls: tuple[_CallSite, ...],
    ambiguous: tuple[str, ...],
) -> None:
    assert ambiguous == ()
    expected_production = {
        (
            "polisyos.runtime.http.services.control.generation_cycle",
            "src/polisyos/runtime/http/services/control/generation_cycle.py",
            "compile_and_run_recursive_generation_cycle",
            "polisyos.runtime.quality.recursive_generation_cycle."
            "build_default_recursive_generation_cycle_controller",
            frozenset(
                {"repo_root", "model_id", "promotion_runtime", "eval_safety_verifier"}
            ),
        ),
        (
            "polisyos.runtime.quality.recursive_generation_cycle",
            "src/polisyos/runtime/quality/recursive_generation_cycle.py",
            "build_default_recursive_generation_cycle_controller",
            "polisyos.runtime.quality.recursive_generation_cycle."
            "RecursiveGenerationCycleController",
            frozenset(
                {"repo_root", "model_id", "promotion_runtime", "eval_safety_verifier"}
            ),
        ),
        (
            "polisyos.runtime.quality.recursive_generation_cycle",
            "src/polisyos/runtime/quality/recursive_generation_cycle.py",
            "RecursiveGenerationCycleController.run.route",
            "polisyos.runtime.quality.generation_cycle.GenerationCycleController",
            frozenset(
                {
                    "generation_port",
                    "repo_root",
                    "model_id",
                    "cycle_substrate_context",
                    "promotion_runtime",
                    "value_port",
                }
            ),
        ),
        (
            "polisyos.runtime.quality.generation_cycle",
            "src/polisyos/runtime/quality/generation_cycle.py",
            "GenerationCycleController.__init__",
            "polisyos.runtime.quality.promotion_sequence.CanonicalN9PromotionPort",
            frozenset({"repo_root", "promotion_runtime", "epoch_n9_evidence_resolver"}),
        ),
    }
    observed_production = {
        (row.module, row.source_path, row.enclosing, row.target, row.keyword_names)
        for row in constructors
        if row.source_path.startswith("src/")
    }
    assert observed_production == expected_production
    assert all(
        row.authority_scope is None for row in constructors if row.source_path.startswith("src/")
    )

    expected_verification = {
        (
            "tools.quality.validation.check_layer3_gy_composition_artifacts",
            "tools/quality/validation/check_layer3_gy_composition_artifacts.py",
            "_build_lane0_depth_n_run._lane0_leaf_controller",
            "polisyos.runtime.quality.generation_cycle.GenerationCycleController",
            frozenset(
                {
                    "authority_scope",
                    "generation_port",
                    "grounding_port",
                    "promotion_port",
                    "repo_root",
                    "simulation_port",
                    "value_port",
                }
            ),
            "contract_testing",
        ),
        (
            "tools.quality.validation.check_layer3_gy_composition_artifacts",
            "tools/quality/validation/check_layer3_gy_composition_artifacts.py",
            "_build_lane0_depth_n_run",
            "polisyos.runtime.quality.recursive_generation_cycle."
            "RecursiveGenerationCycleController.for_contract_testing",
            frozenset({"cycle_controller_factory", "repo_root"}),
            None,
        ),
        (
            "tools.quality.validation.check_layer3_gy_depth_n_universality_contract",
            "tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py",
            "_governed_verification_recursive_controller.build_leaf_controller",
            "polisyos.runtime.quality.generation_cycle.GenerationCycleController",
            frozenset(
                {
                    "authority_scope",
                    "cycle_substrate_context",
                    "generation_port",
                    "model_id",
                    "promotion_port",
                    "repo_root",
                }
            ),
            "contract_testing",
        ),
        (
            "tools.quality.validation.check_layer3_gy_depth_n_universality_contract",
            "tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py",
            "_governed_verification_recursive_controller.build_leaf_controller",
            "polisyos.runtime.quality.promotion_sequence."
            "CanonicalN9PromotionPort._for_verification",
            frozenset({"confidence_ledger_session", "repo_root"}),
            None,
        ),
        (
            "tools.quality.validation.check_layer3_gy_depth_n_universality_contract",
            "tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py",
            "_governed_verification_recursive_controller",
            "polisyos.runtime.quality.recursive_generation_cycle."
            "RecursiveGenerationCycleController.for_contract_testing",
            frozenset({"cycle_controller_factory", "repo_root"}),
            None,
        ),
        (
            "tools.quality.validation.check_layer3_gy_epoch_chronology_contract",
            "tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py",
            "_run_generation_cycle",
            "polisyos.runtime.quality.generation_cycle.GenerationCycleController",
            frozenset({"generation_port", "promotion_runtime", "repo_root"}),
            None,
        ),
        (
            "tools.quality.validation.check_layer3_gy_epoch_chronology_contract",
            "tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py",
            "_n9_and_public_probe",
            "polisyos.runtime.quality.generation_cycle.GenerationCycleController",
            frozenset({"generation_port", "promotion_runtime", "repo_root"}),
            None,
        ),
        (
            "tools.quality.validation.check_layer3_gy_generation_cycle_contract",
            "tools/quality/validation/check_layer3_gy_generation_cycle_contract.py",
            "_build_live_payload_in_verification_namespace",
            "polisyos.runtime.quality.generation_cycle.GenerationCycleController",
            frozenset(
                {
                    "authority_scope",
                    "generated_at",
                    "generation_port",
                    "grounding_port",
                    "promotion_port",
                    "repo_root",
                    "value_port",
                }
            ),
            "contract_testing",
        ),
        (
            "tools.quality.validation.check_layer3_gy_generation_cycle_contract",
            "tools/quality/validation/check_layer3_gy_generation_cycle_contract.py",
            "_build_live_payload_in_verification_namespace",
            "polisyos.runtime.quality.promotion_sequence."
            "CanonicalN9PromotionPort._for_verification",
            frozenset({"confidence_ledger_session", "repo_root"}),
            None,
        ),
        (
            "tools.quality.validation.check_layer3_gy_generation_cycle_disposition_ledger",
            "tools/quality/validation/check_layer3_gy_generation_cycle_disposition_ledger.py",
            "_n8_value_gate_evidence",
            "polisyos.runtime.quality.generation_cycle.GenerationCycleController",
            frozenset({"authority_scope", "repo_root"}),
            "contract_testing",
        ),
        (
            "tools.quality.validation.check_layer3_gy_second_domain_pack",
            "tools/quality/validation/check_layer3_gy_second_domain_pack.py",
            "_build_cycle_trace.run",
            "polisyos.runtime.quality.generation_cycle.GenerationCycleController",
            frozenset(
                {
                    "authority_scope",
                    "cycle_substrate_context",
                    "generation_port",
                    "promotion_port",
                    "repo_root",
                }
            ),
            "contract_testing",
        ),
        (
            "tools.quality.validation.check_layer3_gy_second_domain_pack",
            "tools/quality/validation/check_layer3_gy_second_domain_pack.py",
            "_build_cycle_trace.run",
            "polisyos.runtime.quality.promotion_sequence."
            "CanonicalN9PromotionPort._for_verification",
            frozenset({"confidence_ledger_session", "repo_root"}),
            None,
        ),
        (
            "tools.quality.validation.check_layer3_gy_value_gate_contract",
            "tools/quality/validation/check_layer3_gy_value_gate_contract.py",
            "_run_real_first_vertical_cycle",
            "polisyos.runtime.quality.generation_cycle.GenerationCycleController",
            frozenset(
                {
                    "authority_scope",
                    "cycle_substrate_context",
                    "generation_port",
                    "promotion_port",
                    "repo_root",
                }
            ),
            "contract_testing",
        ),
    }
    observed_verification = {
        (
            row.module,
            row.source_path,
            row.enclosing,
            row.target,
            row.keyword_names,
            row.authority_scope,
        )
        for row in constructors
        if row.source_path.startswith("tools/")
    }
    assert observed_verification == expected_verification
    assert len(constructors) == len(expected_production) + len(expected_verification)
    assert not any(row.has_keyword_expansion for row in constructors)
    expected_promotion_calls = {
        (
            "polisyos.runtime.quality.generation_cycle",
            "src/polisyos/runtime/quality/generation_cycle.py",
            "GenerationCycleController._promote_completed_generation",
            frozenset({"summaries", "problem"}),
        ),
        (
            "polisyos.runtime.quality.generation_cycle",
            "src/polisyos/runtime/quality/generation_cycle.py",
            "GenerationCycleController._promote_completed_generation",
            frozenset({"admitted_batch", "problem"}),
        ),
    }
    assert len(promotion_calls) == len(expected_promotion_calls)
    assert {
        (row.module, row.source_path, row.enclosing, row.keyword_names) for row in promotion_calls
    } == expected_promotion_calls
    assert not any(row.has_keyword_expansion for row in promotion_calls)


def _assert_task_44_export_contract(
    *,
    expected_decision_names: tuple[str, ...],
    decision_owner_names: set[str],
    decision_facade_names: set[str],
    control_owner_names: set[str],
    control_facade_names: set[str],
    scientist_names: set[str],
    scientist_lazy_names: set[str],
    facade_lazy_imports: dict[str, str],
) -> None:
    expected_decision = set(expected_decision_names)
    assert decision_owner_names == expected_decision
    assert decision_facade_names == expected_decision

    control_epoch_names = {"EpochValidityBatchRequest", "EpochValidityBatchResponse"}
    assert control_epoch_names.issubset(control_owner_names)
    assert control_epoch_names.issubset(control_facade_names)
    assert scientist_lazy_names == scientist_names

    for name in expected_decision:
        assert facade_lazy_imports.get(name) == "polisyos.core.contracts.decision_validity"
    for name in control_epoch_names:
        assert facade_lazy_imports.get(name) == "polisyos.core.contracts.control"

    forbidden = {
        "_DecisionValidityStateStore",
        "DecisionValidityStateStore",
        "EpochValidityPredicateClass",
        "NoEpochTransitionVerifier",
        "ArtifactEpochValidityAuthorityGate",
        "ArtifactEpochValidityN9EvidenceResolver",
        "ArtifactEpochValidityPreN9SubjectAuthority",
        "seal_pre_n9_admitted_candidate_batch",
    }
    assert forbidden.isdisjoint(decision_owner_names)
    assert forbidden.isdisjoint(control_owner_names)
    assert forbidden.isdisjoint(scientist_names)
    assert forbidden.isdisjoint(facade_lazy_imports)


def test_default_recursive_generation_factory_binds_subject_authority_and_gate(
    tmp_path: Path,
) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    controller = build_default_recursive_generation_cycle_controller(
        repo_root=tmp_path,
        promotion_runtime=runtime,
    )

    assert controller._promotion_runtime is runtime
    assert controller._epoch_subject_authority is runtime.epoch_subject_authority
    assert controller._epoch_validity_gate is runtime.epoch_validity_gate
    assert controller._epoch_n9_evidence_resolver is runtime.epoch_n9_evidence_resolver


def test_direct_recursive_controller_rejects_foreign_epoch_dependencies(tmp_path: Path) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "owner-cas"))
    foreign = PromotionRuntime(store=FileSystemCAS(tmp_path / "foreign-cas"))

    with pytest.raises(ValueError, match="recursive_epoch_dependencies_must_be_runtime_derived"):
        RecursiveGenerationCycleController(
            promotion_runtime=runtime,
            epoch_validity_gate=foreign.epoch_validity_gate,
        )


@pytest.mark.asyncio
async def test_production_recursive_owner_requires_explicit_eval_safety_context_mapping(
    tmp_path: Path,
) -> None:
    from tests.unit.runtime.quality.test_generation_cycle import _budget, _problem

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem(f"recursive_missing_eval_safety_context_{uuid4().hex}")
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    root_ref = f"design-problem://{problem_ref.removeprefix('sha256:')}"
    graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
    )
    controller = build_default_recursive_generation_cycle_controller(
        promotion_runtime=runtime,
    )

    with pytest.raises(
        RecursiveGenerationCycleError,
        match="recursive_eval_safety_context_not_established",
    ):
        await controller.run(
            graph,
            problems_by_node={root_ref: problem},
            budget_state=_budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=0,
                max_nodes=1,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
        )


@pytest.mark.asyncio
async def test_non_simulation_leaf_requires_current_eval_safety_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.control import evaluation_safety as c02
    from polisyos.runtime.quality import evaluation_safety as es
    from polisyos.runtime.quality import generation_cycle as generation_cycle_owner
    from polisyos.runtime.quality.generation_cycle import (
        JointSimulationPort,
        RealValueOwnerGateway,
        ValueOwnerAccessError,
    )
    from tests.unit.runtime.http.services import test_evaluation_safety as c02_test
    from tests.unit.runtime.quality.test_generation_cycle import (
        REPO_ROOT,
        _Atom,
        _budget,
        _Candidate,
        _CgfGenerationPort,
        _problem,
    )
    from tests.unit.runtime.quality.test_value_gate import (
        _non_simulation_execution_context,
        _simulation,
        _world_record,
    )

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "promotion-cas"))
    problem = _problem(f"recursive_eval_safety_{uuid4().hex}")
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    root_ref = f"design-problem://{problem_ref.removeprefix('sha256:')}"
    graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
    )
    recursive_budget = RecursiveCycleBudget(
        max_depth=0,
        max_nodes=1,
        min_cycles_per_leaf=1,
        max_cycles_per_leaf=1,
    )
    candidate = _Candidate(
        candidate_id="candidate_cgf_shadow",
        atom=_Atom(
            "candidate_cgf_shadow",
            "sha256:" + "4" * 64,
            target_world_slots=("firm_survival",),
        ),
        diversity_key=("grant", "firms", "cgf_shadow", "baseline"),
    )
    world = _world_record("7")
    simulation = _simulation(world, candidate_id=candidate.candidate_id)
    bound_context = _non_simulation_execution_context(
        mode="field_pilot",
        candidate=candidate,
        world=world,
        problem=problem,
    )
    original_intake = c02_test.EvaluationAttemptIntake

    def bound_intake(**values: object) -> es.EvaluationAttemptIntake:
        values.update(
            {
                "candidate_ref": bound_context.candidate_ref,
                "world_model_record_ref": bound_context.world_model_record_ref,
            }
        )
        return original_intake(**values)

    monkeypatch.setattr(c02_test, "EvaluationAttemptIntake", bound_intake)
    fixture = c02_test._passing_fixture(  # noqa: SLF001
        tmp_path / "eval-safety",
        design_problem_ref=problem_ref,
    )

    def actual_n5_input_ref(
        observation: object,
    ) -> object:
        assert observation is simulation
        return fixture.execution_context.evaluation_input_refs[0]

    monkeypatch.setattr(
        generation_cycle_owner,
        "simulation_evaluation_input_ref",
        actual_n5_input_ref,
    )

    class CurrentStateResolver:
        def resolve(
            self,
            context: es.EvaluationExecutionContext,
        ) -> c02.EvaluationSafetyReplayMaterial:
            del context
            return fixture.replay_material

    concrete_verifier = c02.EvaluationSafetyAdmissionVerifier(
        persistence_service=fixture.service,
        current_state_resolver=CurrentStateResolver(),
        authority_resolver=fixture.authority_resolver,
        appointment_resolver=fixture.appointment_resolver,
        verifier_registry=fixture.verifier_registry,
    )

    class ReplayFirstPositive:
        def __init__(self) -> None:
            self.first: es.EvalSafetyConsumerAdmissionReceipt | None = None

        def require_admission(
            self,
            context: es.EvaluationExecutionContext,
            challenge: es.EvalSafetyAdmissionChallenge,
        ) -> es.EvalSafetyConsumerAdmissionReceipt:
            if self.first is None:
                self.first = concrete_verifier.require_admission(context, challenge)
            return self.first

    replaying_verifier = ReplayFirstPositive()
    owner_calls: list[str] = []

    def actual_n5(
        self: JointSimulationPort,
        *,
        candidate: object,
        problem: object,
        cycle_index: int,
    ) -> object:
        del self, problem, cycle_index
        assert candidate.candidate_id == simulation.candidate_id  # type: ignore[attr-defined]
        return simulation

    def value_owner_spy(
        self: RealValueOwnerGateway,
        **values: object,
    ) -> object:
        del self, values
        owner_calls.append("load_value_data_profile")
        raise ValueOwnerAccessError("value_owner_data_profile_invalid")

    monkeypatch.setattr(JointSimulationPort, "__call__", actual_n5)
    monkeypatch.setattr(RealValueOwnerGateway, "load_value_data_profile", value_owner_spy)

    class _CanonicalFixtureN4Port(N4GenerationPort):
        def __init__(self) -> None:
            super().__init__(model_id="fixture-model")
            self._delegate = _CgfGenerationPort()

        async def __call__(self, problem, *, cycle_index):
            return await self._delegate(problem, cycle_index=cycle_index)

    async def run_leaf(
        *,
        context: es.EvaluationExecutionContext,
        verifier: object,
        context_bindings: dict[str, es.EvaluationExecutionContext] | None = None,
    ):
        controller = build_default_recursive_generation_cycle_controller(
            repo_root=REPO_ROOT,
            promotion_runtime=runtime,
            eval_safety_verifier=verifier,
        )
        return await controller.run(
            graph,
            problems_by_node={root_ref: problem},
            budget_state=_budget(),
            recursive_budget=recursive_budget,
            n4_generation_ports_by_node={root_ref: _CanonicalFixtureN4Port()},
            evaluation_contexts_by_node=(
                {root_ref: context} if context_bindings is None else context_bindings
            ),
        )

    current = await run_leaf(
        context=fixture.execution_context,
        verifier=replaying_verifier,
    )
    replayed = await run_leaf(
        context=fixture.execution_context,
        verifier=replaying_verifier,
    )
    stale_context = fixture.execution_context.model_copy(
        update={
            "eval_safety_revision_head_ref": c02_test._ref(  # noqa: SLF001
                "sha256:" + "f" * 64,
                "test.certificate-revision",
            )
        }
    )
    stale = await run_leaf(context=stale_context, verifier=concrete_verifier)

    foreign_problem = _problem(f"recursive_eval_safety_foreign_{uuid4().hex}")
    foreign_context = fixture.execution_context.model_copy(
        update={
            "design_problem_ref": gy_content_hash(
                foreign_problem.model_dump(mode="json")
            )
        }
    )

    class VerifierMustNotRun:
        def require_admission(
            self,
            context: es.EvaluationExecutionContext,
            challenge: es.EvalSafetyAdmissionChallenge,
        ) -> es.EvalSafetyConsumerAdmissionReceipt:
            del context, challenge
            raise AssertionError("foreign problem context reached EvalSafety verifier")

    owner_calls_before_foreign = tuple(owner_calls)
    with pytest.raises(
        RecursiveGenerationCycleError,
        match="recursive_eval_safety_design_problem_mismatch",
    ):
        await run_leaf(
            context=foreign_context,
            verifier=VerifierMustNotRun(),
            context_bindings={root_ref: foreign_context},
        )
    assert tuple(owner_calls) == owner_calls_before_foreign

    def value_observation(run):
        leaf = run.leaf_nodes[0]
        assert leaf.cycle_run is not None
        return leaf.cycle_run.value_port

    current_value = value_observation(current)
    replayed_value = value_observation(replayed)
    stale_value = value_observation(stale)
    assert replaying_verifier.first is not None
    assert replaying_verifier.first.status == "verified"
    assert replaying_verifier.first.certificate_ref == (
        fixture.execution_context.eval_safety_certificate_ref
    )
    assert replaying_verifier.first.current_revision_head_ref == (
        fixture.execution_context.eval_safety_revision_head_ref
    )
    assert current_value.authority_blockers == ("value_owner_data_profile_invalid",)
    assert replayed_value.authority_blockers == (
        "eval_safety_consumer_admission_blocked",
    )
    assert stale_value.status == "value_blocked"
    assert any("eval_safety" in blocker for blocker in stale_value.authority_blockers)
    assert owner_calls == ["load_value_data_profile"]
    for invalid_bindings in (
        {},
        {root_ref: fixture.execution_context, "design-problem://extra": fixture.execution_context},
        {"design-problem://cross-leaf": fixture.execution_context},
    ):
        with pytest.raises(
            RecursiveGenerationCycleError,
            match="recursive_eval_safety_context_denominator_mismatch",
        ):
            await run_leaf(
                context=fixture.execution_context,
                verifier=concrete_verifier,
                context_bindings=invalid_bindings,
            )


@pytest.mark.asyncio
async def test_http_and_direct_recursive_paths_share_the_pre_n9_subject_strangle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import evaluation_safety as es
    from polisyos.runtime.quality import promotion_sequence as promotion_sequence_module
    from polisyos.runtime.quality.generation_cycle import (
        simulation_value_execution_context,
    )
    from tests.unit.runtime.quality.test_generation_cycle import (
        REPO_ROOT,
        _budget,
        _CgfGenerationPort,
        _problem,
    )
    from tests.unit.runtime.quality.test_value_gate import (
        _candidate,
        _simulation,
        _world_record,
    )

    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem(f"recursive_owner_strangle_{uuid4().hex}")
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    root_ref = f"design-problem://{problem_ref.removeprefix('sha256:')}"
    graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
    )
    recursive_budget = RecursiveCycleBudget(
        max_depth=0,
        max_nodes=1,
        min_cycles_per_leaf=1,
        max_cycles_per_leaf=1,
    )

    class _SimulationOnlyVerifier:
        def require_admission(
            self,
            context: es.EvaluationExecutionContext,
            challenge: es.EvalSafetyAdmissionChallenge,
        ) -> es.EvalSafetyConsumerAdmissionReceipt:
            del context, challenge
            raise AssertionError("simulation-only recursive fixture called verifier")

    verifier = _SimulationOnlyVerifier()
    simulation_candidate = _candidate()
    evaluation_context = simulation_value_execution_context(
        candidate=simulation_candidate,
        simulation=_simulation(_world_record()),
        problem=problem,
    )

    class _CanonicalFixtureN4Port(N4GenerationPort):
        def __init__(self) -> None:
            super().__init__(model_id="fixture-model")
            self._delegate = _CgfGenerationPort()

        async def __call__(self, problem, *, cycle_index):
            return await self._delegate(problem, cycle_index=cycle_index)

    direct_controller = build_default_recursive_generation_cycle_controller(
        repo_root=REPO_ROOT,
        promotion_runtime=runtime,
        eval_safety_verifier=verifier,
    )
    direct = await direct_controller.run(
        graph,
        problems_by_node={root_ref: problem},
        budget_state=_budget(),
        recursive_budget=recursive_budget,
        n4_generation_ports_by_node={root_ref: _CanonicalFixtureN4Port()},
        evaluation_contexts_by_node={root_ref: evaluation_context},
    )

    subject_kind = "runtime.promotion.pre_n9_epoch_validity_subject"
    direct_subject_ids = tuple(
        artifact_id
        for artifact_id in runtime.store.iter_artifact_ids()
        if runtime.store.get_manifest(artifact_id).kind == subject_kind
    )

    async def compile_problem(**kwargs):
        del kwargs
        return problem

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compile_problem,
    )
    compiled = await generation_cycle_service.compile_and_run_recursive_generation_cycle(
        raw_request=problem.nl_provenance.raw_request,
        context={},
        model_name="fixture-model",
        compiler_gateway=object(),  # type: ignore[arg-type]
        budget_state=_budget(),
        recursive_budget=recursive_budget,
        root_n4_generation_port=_CanonicalFixtureN4Port(),
        promotion_runtime=runtime,
        root_evaluation_context=evaluation_context,
        eval_safety_verifier=verifier,
        repo_root=REPO_ROOT,
    )

    direct_leaf = direct.leaf_nodes[0]
    http_leaf = compiled.recursive_run.leaf_nodes[0]
    for leaf in (direct_leaf, http_leaf):
        assert leaf.cycle_run is not None
        assert leaf.cycle_run.promotion_port.receipts == ()
        assert leaf.cycle_run.promotion_port.reason == (
            "epoch_validity_refused:policy_admission_missing"
        )
    http_subject_ids = tuple(
        artifact_id
        for artifact_id in runtime.store.iter_artifact_ids()
        if runtime.store.get_manifest(artifact_id).kind == subject_kind
    )
    assert len(direct_subject_ids) == 1
    assert http_subject_ids == direct_subject_ids


def test_recursive_constructor_denominator_has_no_unwrapped_n9_call() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    git_paths, filesystem_paths = _production_python_paths(repo_root)
    assert git_paths == filesystem_paths

    constructors: list[_CallSite] = []
    promotion_calls: list[_CallSite] = []
    ambiguous: list[str] = []
    for relative_path in sorted(git_paths):
        source_path = repo_root / relative_path
        found_constructors, found_ports, found_ambiguous = _scan_python_source(
            source=source_path.read_text(encoding="utf-8"),
            module=_module_name(repo_root, source_path),
            source_path=relative_path,
        )
        constructors.extend(found_constructors)
        promotion_calls.extend(found_ports)
        ambiguous.extend(found_ambiguous)
    _assert_constructor_contract(tuple(constructors), tuple(promotion_calls), tuple(ambiguous))

    # The denominator and alias resolver are themselves falsified, rather than trusted by form.
    sample = next(iter(git_paths))
    with pytest.raises(AssertionError):
        assert git_paths - {sample} == filesystem_paths
    aliased, _, alias_ambiguity = _scan_python_source(
        source="""
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveGenerationCycleController as ImportedController,
)
Alias = ImportedController
def build():
    return Alias(repo_root=None, model_id=None, promotion_runtime=runtime)
""",
        module="synthetic.alias_probe",
        source_path="synthetic/alias_probe.py",
    )
    assert alias_ambiguity == ()
    assert len(aliased) == 1
    assert aliased[0].target.endswith("RecursiveGenerationCycleController")

    _, _, star_ambiguity = _scan_python_source(
        source="""
from polisyos.runtime.quality.recursive_generation_cycle import *
RecursiveGenerationCycleController(
    repo_root=None, model_id=None, promotion_runtime=runtime,
)
""",
        module="synthetic.star_probe",
        source_path="synthetic/star_probe.py",
    )
    assert any("target_module_star_import" in row for row in star_ambiguity)
    _, _, shadow_ambiguity = _scan_python_source(
        source="""
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveGenerationCycleController,
)
def build(RecursiveGenerationCycleController):
    return RecursiveGenerationCycleController(
        repo_root=None, model_id=None, promotion_runtime=runtime,
    )
""",
        module="synthetic.shadow_probe",
        source_path="synthetic/shadow_probe.py",
    )
    assert any("RecursiveGenerationCycleController" in row for row in shadow_ambiguity)
    _, aliased_ports, port_alias_ambiguity = _scan_python_source(
        source="""
class Probe:
    def promote(self):
        port = self._promotion_port
        return port(admitted_batch=batch, problem=problem)
""",
        module="synthetic.port_alias_probe",
        source_path="synthetic/port_alias_probe.py",
    )
    assert port_alias_ambiguity == ()
    assert len(aliased_ports) == 1
    assert aliased_ports[0].keyword_names == frozenset({"admitted_batch", "problem"})

    missing_runtime = tuple(
        replace(
            row,
            keyword_names=row.keyword_names - {"promotion_runtime"},
        )
        if row.target.endswith("GenerationCycleController")
        else row
        for row in constructors
    )
    with pytest.raises(AssertionError):
        _assert_constructor_contract(missing_runtime, tuple(promotion_calls), tuple(ambiguous))
    with pytest.raises(AssertionError):
        _assert_constructor_contract(
            (*constructors, constructors[0]), tuple(promotion_calls), tuple(ambiguous)
        )
    unscoped_verification = tuple(
        replace(row, authority_scope=None) if row.authority_scope == "contract_testing" else row
        for row in constructors
    )
    with pytest.raises(AssertionError):
        _assert_constructor_contract(
            unscoped_verification,
            tuple(promotion_calls),
            tuple(ambiguous),
        )
    shaped_production_port = tuple(
        replace(row, keyword_names=frozenset({"summaries", "problem"}))
        if "admitted_batch" in row.keyword_names
        else row
        for row in promotion_calls
    )
    with pytest.raises(AssertionError):
        _assert_constructor_contract(tuple(constructors), shaped_production_port, tuple(ambiguous))


def test_task_44_public_export_denominator_is_exact() -> None:
    import polisyos.core.contracts as core_contracts
    import polisyos.scientist.validation as scientist_validation
    from polisyos.core.contracts import control, decision_validity
    from polisyos.scientist.validation import decision_validity as scientist_decision_validity

    base_decision_names = (
        "DecisionBasisSection",
        "DecisionDependencyEvent",
        "DecisionDependencyKind",
        "DecisionDependencyRef",
        "DecisionLifecycleJob",
        "DecisionLifecycleJobKind",
        "DecisionLifecycleJobState",
        "DecisionTriggerRecord",
        "DecisionTriggerSpec",
        "DecisionTriggerType",
        "DecisionValidityEnvelope",
        "DecisionValidityEvaluation",
        "DecisionValidityStatus",
        "DecisionValidityTransition",
    )
    epoch_decision_names = (
        "EpochTransitionVerificationReceipt",
        "EpochTransitionVerifier",
        "EpochValidityAuthorityGate",
        "EpochValidityBatchCompletionStatement",
        "EpochValidityBatchReceipt",
        "EpochValidityBatchTarget",
        "EpochValidityCompletedBatchEvidenceDenominator",
        "EpochValidityCompletedBatchEvidenceResolver",
        "EpochValidityGateNonReceipt",
        "EpochValidityGateReceipt",
        "EpochValidityN9EvidenceResolver",
        "EpochValidityN9Projection",
        "EpochValidityPendingBatch",
        "EpochValidityPreN9SubjectAuthority",
        "PersistedEpochValidityBatchEvidence",
        "PersistedEpochValidityGateEvidence",
        "PersistedPreN9AdmittedCandidateBatch",
        "PersistedPreN9EpochValiditySubject",
        "PreN9AdmittedCandidate",
        "PreN9EpochValiditySubjectStatement",
    )
    expected_decision_names = base_decision_names + epoch_decision_names
    control_epoch_names = ("EpochValidityBatchRequest", "EpochValidityBatchResponse")
    contract = {
        "expected_decision_names": expected_decision_names,
        "decision_owner_names": set(decision_validity.__all__),
        "decision_facade_names": set(core_contracts._MODULE_SYMBOLS[".decision_validity"]),
        "control_owner_names": set(control.__all__),
        "control_facade_names": set(core_contracts._MODULE_SYMBOLS[".control"]),
        "scientist_names": set(scientist_validation.__all__),
        "scientist_lazy_names": set(scientist_validation._LAZY_IMPORTS),
        "facade_lazy_imports": dict(core_contracts._LAZY_IMPORTS),
    }
    _assert_task_44_export_contract(**contract)

    assert tuple(decision_validity.__all__) == expected_decision_names
    assert (
        tuple(name for name in control.__all__ if name.startswith("EpochValidityBatch"))
        == control_epoch_names
    )
    assert (
        tuple(
            name
            for name in core_contracts._MODULE_SYMBOLS[".control"]
            if name.startswith("EpochValidityBatch")
        )
        == control_epoch_names
    )

    for owner, names in (
        (decision_validity, epoch_decision_names),
        (control, control_epoch_names),
    ):
        for name in names:
            assert name in core_contracts.__all__
            assert name in dir(core_contracts)
            assert getattr(core_contracts, name) is getattr(owner, name)

    assert tuple(scientist_decision_validity.__all__) == ("DecisionValidityService",)
    for forbidden in (
        "_DecisionValidityStateStore",
        "DecisionValidityStateStore",
        "NoEpochTransitionVerifier",
    ):
        assert forbidden not in scientist_validation.__dict__

    # Mutation probes feed the exact same generic oracle as the live surfaces.
    with pytest.raises(AssertionError):
        _assert_task_44_export_contract(
            **{
                **contract,
                "decision_owner_names": contract["decision_owner_names"]
                - {epoch_decision_names[0]},
            }
        )
    with pytest.raises(AssertionError):
        _assert_task_44_export_contract(
            **{
                **contract,
                "control_owner_names": contract["control_owner_names"]
                | {"NoEpochTransitionVerifier"},
            }
        )
    with pytest.raises(AssertionError):
        _assert_task_44_export_contract(
            **{
                **contract,
                "scientist_names": contract["scientist_names"] | {"DecisionValidityStateStore"},
            }
        )
    retargeted = dict(contract["facade_lazy_imports"])
    retargeted[epoch_decision_names[0]] = "polisyos.core.contracts.control"
    with pytest.raises(AssertionError):
        _assert_task_44_export_contract(**{**contract, "facade_lazy_imports": retargeted})

    assert set(control_epoch_names).issubset(core_contracts.__all__)
    assert set(epoch_decision_names).issubset(core_contracts.__all__)
