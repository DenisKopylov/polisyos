#!/usr/bin/env python3
"""Validate committed Layer 3 GY recursion/composition artifacts."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

from tools.lib.timing import run_timed_entrypoint

FAMILY_ID = "policy-design-case-layer3-gy-composition-artifacts"
CERTIFICATES_PATH = "architecture/policy_design_case/layer3_gy_composition_certificates.json"


def _run_source_flip(
    repo_root: Path,
    *,
    mutation_id: str,
    source_relative: str,
    old_source: str,
    new_source: str,
    command: tuple[str, ...],
    expected_red_signal: str,
) -> dict[str, Any]:
    """Apply one guarded mutation, run its behavioral probe, and restore bytes."""

    source_path = repo_root / source_relative
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    guard_count = text.count(old_source)
    if guard_count != 1:
        return {
            "mutation_id": mutation_id,
            "result": "HARNESS_ERROR",
            "proof": {"source_guard_count": guard_count},
        }
    completed: subprocess.CompletedProcess[str] | None = None
    harness_error: str | None = None
    started = time.monotonic()
    try:
        source_path.write_text(text.replace(old_source, new_source, 1), encoding="utf-8")
        completed = subprocess.run(
            command,
            cwd=repo_root,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
                "JAX_PLATFORMS": "cpu",
            },
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - emitted as harness evidence.
        harness_error = str(exc)
    finally:
        source_path.write_bytes(original)
    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": mutation_id,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "source_restore_hash_mismatch",
                "before": original_hash,
                "after": restored_hash,
            },
        }
    if harness_error is not None or completed is None:
        return {
            "mutation_id": mutation_id,
            "result": "HARNESS_ERROR",
            "proof": harness_error or "source_flip_probe_not_run",
        }
    output = f"{completed.stdout}\n{completed.stderr}"
    mutation_red = completed.returncode != 0 and expected_red_signal in output
    return {
        "mutation_id": mutation_id,
        "result": "RED" if mutation_red else "GREEN_MUTATION_SURVIVED",
        "proof": {
            "command": list(command),
            "exit_code": completed.returncode,
            "expected_red_signal": expected_red_signal,
            "signal_observed": expected_red_signal in output,
            "source_restored_sha256": restored_hash,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
        },
    }


def run_source_flip_mutations(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Run the Stage-3 decisive source mutations serially with exact restore."""

    python = sys.executable
    strangle = _run_source_flip(
        repo_root,
        mutation_id="gy_g_fixture_caller_reintroduced",
        source_relative="src/polisyos/runtime/quality/workspace/loop.py",
        old_source="\n\n__all__ = [",
        new_source=(
            "\n\ndef _reintroduced_fixture_caller() -> None:\n"
            "    run_recursive_case()\n"
            "\n\n__all__ = ["
        ),
        command=(
            python,
            "tools/quality/validation/check_layer3_gy_composition_artifacts.py",
            "--repo-root",
            ".",
            "--check",
            "--output-format",
            "json",
        ),
        expected_red_signal="layer3_gy_depth_n_strangle_receipt_red",
    )
    coupling = _run_source_flip(
        repo_root,
        mutation_id="empty_coupling_assumed_independent",
        source_relative=(
            "src/polisyos/runtime/quality/design_axes/coupling_composition.py"
        ),
        old_source=(
            "    elif (\n"
            "        graph.evidence_state == \"absent\"\n"
            "        or graph.module_discovery_ref is None\n"
            "        or not graph.interaction_edges\n"
            "    ):\n"
        ),
        new_source=(
            "    elif (\n"
            "        graph.evidence_state == \"absent\"\n"
            "        or graph.module_discovery_ref is None\n"
            "    ):\n"
        ),
        command=(
            python,
            "-m",
            "pytest",
            (
                "tests/unit/runtime/quality/test_depth_n_universality.py::"
                "test_missing_coupling_evidence_defaults_toward_entanglement"
            ),
            "-q",
        ),
        expected_red_signal=(
            "empty_coupling_without_observed_boundary_must_default_entangled"
        ),
    )
    n5_owner = _run_source_flip(
        repo_root,
        mutation_id="n5_joint_simulation_owner_bypassed",
        source_relative="src/polisyos/runtime/quality/recursive_generation_cycle.py",
        old_source=(
            "                joint_simulation = "
            "self._joint_simulation_controller.run(request)\n"
        ),
        new_source=(
            "                raise RecursiveGenerationCycleError(\n"
            "                    \"joint_simulation_owner_bypassed\"\n"
            "                )\n"
        ),
        command=(
            python,
            "-m",
            "pytest",
            (
                "tests/unit/runtime/quality/test_depth_n_universality.py::"
                "test_coupled_parent_runs_real_n5_and_records_interactions"
            ),
            "-q",
        ),
        expected_red_signal="joint_simulation_owner_bypassed",
    )
    unsupported_label = _run_source_flip(
        repo_root,
        mutation_id="unsupported_n5_relabelled_joint_simulated",
        source_relative="src/polisyos/runtime/quality/generation_cycle.py",
        old_source=(
            "        return \"simulation_blocked\", "
            "tuple(dict.fromkeys(str(item) for item in blockers))\n"
        ),
        new_source=(
            "        return \"joint_simulated\", "
            "tuple(dict.fromkeys(str(item) for item in blockers))\n"
        ),
        command=(
            python,
            "-m",
            "pytest",
            (
                "tests/unit/runtime/quality/test_generation_cycle.py::"
                "test_real_unsupported_n5_result_is_serialized_as_simulation_blocked"
            ),
            "-q",
        ),
        expected_red_signal="unsupported_n5_result_must_block",
    )
    default_route = _run_source_flip(
        repo_root,
        mutation_id="gy_g_production_default_route_removed",
        source_relative="src/polisyos/runtime/http/services/control/generation_cycle.py",
        old_source=(
            "    resolved_controller = controller or "
            "build_default_recursive_generation_cycle_controller(\n"
        ),
        new_source=(
            "    resolved_controller = controller or "
            "RecursiveGenerationCycleController(\n"
        ),
        command=(
            python,
            "tools/quality/validation/check_layer3_gy_composition_artifacts.py",
            "--repo-root",
            ".",
            "--check",
            "--output-format",
            "json",
        ),
        expected_red_signal="layer3_gy_depth_n_strangle_receipt_red",
    )
    return (strangle, coupling, n5_owner, unsupported_label, default_route)


def declared_outputs() -> list[str]:
    """Return the generated artifacts this validator writes in --write mode."""

    return [CERTIFICATES_PATH]


def validate(
    repo_root: Path,
    *,
    write: bool = False,
    corrupt_field_drift_check: bool = False,
) -> dict[str, Any]:
    """Validate or regenerate the committed GY-G composition proof artifact."""

    issues: list[dict[str, str]] = []
    _ensure_src_path(repo_root)
    generated = tomllib.loads(
        (repo_root / "architecture/generated_artifacts.toml").read_text(encoding="utf-8")
    )
    family = {item.get("id"): item for item in generated.get("family", [])}.get(FAMILY_ID)
    if not family:
        issues.append({"code": "layer3_gy_composition_family_missing"})
    else:
        outputs = set(family.get("outputs") or [])
        if CERTIFICATES_PATH not in outputs:
            issues.append(
                {
                    "code": "layer3_gy_composition_output_not_registered",
                    "path": CERTIFICATES_PATH,
                }
            )
        if family.get("stale_output_behavior") != "fail":
            issues.append({"code": "layer3_gy_composition_stale_output_not_fail_closed"})
        if "--check" not in list(family.get("check_command") or []):
            issues.append({"code": "layer3_gy_composition_check_command_missing_check_mode"})

    live_payload = _normalise_payload_for_artifact(
        build_live_composition_artifacts(repo_root)[CERTIFICATES_PATH]
    )
    _validate_certificate_payload(live_payload, issues, path="$live")
    if write:
        output_path = repo_root / CERTIFICATES_PATH
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(live_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        committed = _read_json(repo_root / CERTIFICATES_PATH, issues)
        if committed:
            _validate_certificate_payload(committed, issues, path="$committed")
            if committed != live_payload:
                issues.append(
                    {
                        "code": "layer3_gy_composition_certificate_drift",
                        "path": CERTIFICATES_PATH,
                    }
                )
            if corrupt_field_drift_check:
                corrupt = json.loads(json.dumps(committed))
                corrupt["certificates"][0]["certificate_id"] = "composition-certificate-corrupt"
                if corrupt != live_payload:
                    issues.append(
                        {"code": "layer3_gy_composition_corrupt_field_drift_detected"}
                    )
                else:
                    issues.append({"code": "layer3_gy_composition_corrupt_field_not_detected"})

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "checked_artifacts": [CERTIFICATES_PATH],
        "family_id": FAMILY_ID,
        "write": write,
        "corrupt_field_drift_check": corrupt_field_drift_check,
    }


def build_live_composition_artifacts(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Recompute GY-G through canonical composition and the depth-N router."""

    _ensure_src_path(repo_root)
    from polisyos.pdc import ArtifactRef, gy_content_hash
    from polisyos.runtime.quality.design_axes.coupling_composition import (
        CouplingEdge,
        build_composition_receipt,
        build_coupling_graph,
        classify_coupling,
        compose_subdesigns,
        decompose_design,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        recompute_depth_n_strangle_receipt,
    )

    independent_children = _synthetic_composition_subdesigns(
        artifact_ref_factory=ArtifactRef.from_payload
    )
    independent_edge = CouplingEdge(
        boundary_ref="boundary://gyg/observed-independent",
        source_module_ref=independent_children[0].workspace_id,
        target_module_ref=independent_children[1].workspace_id,
        relation="observed_independent_measurement",
        interaction_strength="none",
        evidence_ref="evidence://gyg/observed-independent",
    )
    independent_graph = build_coupling_graph(
        design_ref="pdc://gyg/independent/design",
        module_refs=[child.workspace_id for child in independent_children],
        module_discovery_ref="pdc://gyg/independent/module-discovery",
        interaction_edges=(independent_edge,),
        evidence_state="observed",
        rule_version_ref="policyos.gy.composition.v1",
    )
    independent_classification = classify_coupling(independent_graph)
    independent_decomposition = decompose_design(
        independent_graph,
        independent_classification,
        critical_path_module_refs=independent_graph.module_refs,
    )
    independent_receipt = build_composition_receipt(independent_decomposition)
    independent_certificate = compose_subdesigns(
        parent_workspace_id="ws-gyg-independent",
        subdesigns=independent_children,
        graph=independent_graph,
        claims=(),
    )
    feedback_edge = CouplingEdge(
        boundary_ref="boundary://gyg/feedback",
        source_module_ref=independent_children[0].workspace_id,
        target_module_ref=independent_children[1].workspace_id,
        relation="tariff_take_up_feedback",
        interaction_strength="strong",
        feedback_intensity="high",
        feedback=True,
        evidence_ref="evidence://gyg/feedback",
    )
    feedback_back_edge = CouplingEdge(
        boundary_ref="boundary://gyg/feedback",
        source_module_ref=independent_children[1].workspace_id,
        target_module_ref=independent_children[0].workspace_id,
        relation="take_up_response",
        interaction_strength="strong",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="evidence://gyg/feedback-back-edge",
    )
    feedback_graph = independent_graph.model_copy(
        update={
            "graph_id": "graph-gyg-feedback",
            "graph_ref": "pdc://gyg/feedback/coupling-graph",
            "design_ref": "pdc://gyg/feedback/design",
            "interaction_edges": [feedback_edge, feedback_back_edge],
        }
    )
    feedback_certificate = compose_subdesigns(
        parent_workspace_id="ws-gyg-feedback",
        subdesigns=independent_children,
        graph=feedback_graph,
        claims=(),
    )
    recursive_result = _build_lane0_depth_n_run(
        repo_root,
        subdesigns=independent_children,
    )
    strangle_receipt = recompute_depth_n_strangle_receipt(repo_root)
    subdesign_verifications = _unique_records_by_id(
        [
            *_subdesign_verification_records(
                independent_children,
                gy_content_hash=gy_content_hash,
            ),
            *_subdesign_verification_records(
                _synthetic_composition_subdesigns(
                    artifact_ref_factory=ArtifactRef.from_payload
                ),
                gy_content_hash=gy_content_hash,
            ),
            *_subdesign_verification_records(
                _synthetic_empty_meet_subdesigns(
                    artifact_ref_factory=ArtifactRef.from_payload
                ),
                gy_content_hash=gy_content_hash,
            ),
        ]
    )
    p14_independent = _p14_verification_record(
        verification_id="p14-independent-test",
        evidence_lines=_gyg_p14_evidence_lines(independent=True),
        raw_count=2,
        effective_count=2,
        gy_content_hash=gy_content_hash,
        artifact_ref_factory=ArtifactRef.from_payload,
    )
    p14_dependent = _p14_verification_record(
        verification_id="p14-dependent-test",
        evidence_lines=_gyg_p14_evidence_lines(independent=False),
        raw_count=2,
        effective_count=1,
        gy_content_hash=gy_content_hash,
        artifact_ref_factory=ArtifactRef.from_payload,
    )
    payload = {
        "schema_version": "policyos.policy_design_case.layer3_gy.composition_certificates.v1",
        "owner": "team-runtime-quality",
        "writer_role": "system_verifier",
        "proof_source": "recursive_generation_cycle_recomputed",
        "produced_by": "tools/quality/validation/check_layer3_gy_composition_artifacts.py",
        "composition_engine_owner": (
            "polisyos.runtime.quality.design_axes.coupling_composition"
        ),
        "certificates": [
            independent_certificate.model_dump(mode="json"),
            feedback_certificate.model_dump(mode="json"),
        ],
        "composition_receipts": [independent_receipt.model_dump(mode="json")],
        "subdesign_contract_verifications": subdesign_verifications,
        "independence_consistency_verifications": [
            {
                "verification_id": "independence-consistency-other-edge",
                "writer_role": "system_verifier",
                "produced_by": (
                    "tools/quality/validation/check_layer3_gy_composition_artifacts.py"
                ),
                "binding": {
                    "graph_hash": "sha256:other-graph",
                    "boundary_ref": "boundary://other-edge",
                    "source_module_ref": "ws-other-a",
                    "target_module_ref": "ws-other-b",
                    "relation": "observed_independent_measurement",
                },
            }
        ],
        "p14_independence_verifications": [p14_independent, p14_dependent],
        "emergent_grounding_verifications": [
            _emergent_grounding_verification_record(
                verification_id="emergent-grounding-decision-test",
                grounding_ref=(
                    "repo://architecture/policy_design_case/"
                    "layer3_gy_composition_certificates.json"
                    "#emergent-grounding-decision-test"
                ),
                evidence_kind="measurement",
                decision_grade="decision_admissible",
            ),
            _emergent_grounding_verification_record(
                verification_id="emergent-grounding-simulation-test",
                grounding_ref=(
                    "repo://architecture/policy_design_case/"
                    "layer3_gy_composition_certificates.json"
                    "#emergent-grounding-simulation-test"
                ),
                evidence_kind="simulation",
                decision_grade="advisory_admissible",
            ),
        ],
        "recursive_runs": [
            recursive_result.model_dump(mode="json"),
        ],
        "depth_n_strangle_receipt": strangle_receipt.model_dump(mode="json"),
    }
    return {CERTIFICATES_PATH: _normalise_payload_for_artifact(payload)}


def _build_lane0_depth_n_run(
    repo_root: Path,
    *,
    subdesigns: list[Any],
) -> Any:
    """Run a depth-three mini-world through real N6, N5, and composition owners."""

    import asyncio
    from decimal import Decimal
    from importlib import import_module
    from types import SimpleNamespace

    from polisyos.pdc import SearchTerminalKind, SearchTerminalState, gy_content_hash
    from polisyos.runtime.quality.design_axes.coupling_composition import (
        derive_recursive_design_graph,
    )
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generation_cycle import (
        CandidateGroundingObservation,
        GenerationCycleController,
        PendingN8ValuePort,
        PromotionPortObservation,
        SimulationPortObservation,
    )
    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleBudget,
        RecursiveGenerationCycleController,
    )
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState

    problem_payload = json.loads(
        (
            repo_root
            / "architecture/policy_design_case/layer3_gy_second_domain_smoke_design_problem.json"
        ).read_text(encoding="utf-8")
    )["design_problem"]
    class _Lane0GenerationPort:
        async def __call__(
            self,
            problem: DesignProblem,
            *,
            cycle_index: int,
        ) -> SimpleNamespace:
            del problem, cycle_index
            atom = SimpleNamespace(
                intervention_id="lane0_depth_n_intervention",
                content_hash="sha256:" + "4" * 64,
                status="candidate_unverified",
                world_model_record_ref="world_model_record_lane0_depth_n",
                target_world_slots=("final_queue_length",),
            )
            candidate = SimpleNamespace(
                candidate_id="candidate_lane0_depth_n",
                atom=atom,
                diversity_key=("queue", "claims", "lane0", "depth-n"),
                status="candidate_unverified",
            )
            ranking = SimpleNamespace(
                candidate_id=candidate.candidate_id,
                score=0.2,
                voi_estimate=0.1,
                trust_level="search_guiding",
                promotion_allowed=False,
            )
            return SimpleNamespace(
                status="generated",
                candidates=(candidate,),
                surrogate_rankings=(ranking,),
                grounding_dispositions=(),
            )

    class _Lane0GroundingPort:
        def __call__(
            self,
            *,
            candidate: Any,
            **kwargs: Any,
        ) -> CandidateGroundingObservation:
            del kwargs
            return CandidateGroundingObservation(
                candidate_id=str(candidate.candidate_id),
                status="grounding_gap",
                grounding_score=0.2,
                issue_codes=("lane0_grounding_gap",),
                current_valid=False,
            )

    class _Lane0SimulationPort:
        def __call__(
            self,
            *,
            candidate: Any,
            **kwargs: Any,
        ) -> SimulationPortObservation:
            del kwargs
            return SimulationPortObservation(
                candidate_id=str(candidate.candidate_id),
                status="simulation_pending_n5",
                authority_blockers=("lane0_joint_request_not_leaf_owned",),
            )

    class _Lane0PromotionPort:
        def __call__(self, **kwargs: Any) -> PromotionPortObservation:
            del kwargs
            return PromotionPortObservation()

    def _lane0_leaf_controller(
        node_ref: str,
        problem: DesignProblem,
    ) -> GenerationCycleController:
        del node_ref, problem
        return GenerationCycleController(
            generation_port=_Lane0GenerationPort(),
            grounding_port=_Lane0GroundingPort(),
            simulation_port=_Lane0SimulationPort(),
            value_port=PendingN8ValuePort(),
            promotion_port=_Lane0PromotionPort(),
            repo_root=repo_root,
        )

    leaf_terminal = SearchTerminalState(
        kind=SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED,
        reason="Terminal emitted by the canonical generation-cycle owner.",
        blocking_obligations=["lane0_grounding_gap", "value_gate_pending_n8"],
    )

    root = "design://gy-n10/depth/root"
    unary = "design://gy-n10/depth/one"
    branch = "design://gy-n10/depth/two"
    leaves = ("design://gy-n10/depth/three-a", "design://gy-n10/depth/three-b")
    node_refs = (root, unary, branch, *leaves)
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=node_refs[1:],
        parent_child_edges=((root, unary), (unary, branch), (branch, leaves[0]), (branch, leaves[1])),
        rule_version_ref="policyos.gy.depth_n.lane0.v1",
    )
    base_problem = DesignProblem.model_validate(problem_payload)
    problems = {
        node_ref: base_problem.model_copy(
            update={
                "design_problem_id": f"depth_n_{index}",
                "objectives": [
                    base_problem.objectives[0].model_copy(
                        update={"metric_id": "final_queue_length"}
                    )
                ],
                "outcome_of_interest": base_problem.outcome_of_interest.model_copy(
                    update={
                        "target_variable": "final_queue_length",
                        "metric_id": "final_queue_length",
                        "estimand": "effect on the final claims queue length",
                        "direction": "minimize",
                    }
                ),
            }
        )
        for index, node_ref in enumerate(node_refs)
    }
    n5_module = import_module(
        "tools.quality.validation.check_layer3_gy_joint_simulation_horizon_contract"
    )
    request = n5_module._coupled_request()
    request_graph = request.coupling_graph
    if request_graph is None:
        raise AssertionError("lane0_coupled_request_missing_graph")
    request_edges = tuple(
        edge.model_copy(
            update={
                "source_module_ref": leaves[0],
                "target_module_ref": leaves[1],
            }
        )
        for edge in request_graph.interaction_edges
    )
    branch_problem_ref = gy_content_hash(problems[branch].model_dump(mode="json"))
    request_atoms: list[InterventionAtomBinding] = []
    for atom in request.intervention_atoms:
        draft = atom.model_copy(update={"problem_frame_ref": branch_problem_ref})
        content_hash = intervention_atom_content_hash(draft)
        bound = draft.model_copy(
            update={
                "atom_id": f"atom_{content_hash.removeprefix('sha256:')[:16]}",
                "content_hash": content_hash,
            }
        )
        request_atoms.append(
            InterventionAtomBinding.model_validate(bound.model_dump(mode="python"))
        )
    request = request.model_copy(
        update={
            "intervention_atoms": tuple(request_atoms),
            "coupling_graph": request_graph.model_copy(
                update={
                    "design_ref": branch,
                    "module_refs": leaves,
                    "interaction_edges": request_edges,
                    "evidence_state": "observed",
                }
            )
        }
    )
    bound_subdesigns = tuple(
        child.model_copy(
            update={
                "workspace_id": leaf_ref,
                "parent_workspace_id": branch,
                "search_exit": child.search_exit.model_copy(
                    update={
                        "workspace_id": leaf_ref,
                        "terminal_state": leaf_terminal,
                    }
                ),
            }
        )
        for child, leaf_ref in zip(subdesigns, leaves, strict=True)
    )
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=_lane0_leaf_controller,
        repo_root=repo_root,
    )
    return asyncio.run(
        controller.run(
            graph,
            problems_by_node=problems,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            recursive_budget=RecursiveCycleBudget(
                max_depth=3,
                max_nodes=5,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=2,
            ),
            joint_simulation_requests_by_node={branch: request},
            subdesign_contracts_by_node={branch: bound_subdesigns},
        )
    )


def _unique_records_by_id(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        verification_id = str(record.get("verification_id") or "")
        if verification_id:
            unique[verification_id] = record
    return list(unique.values())


def _subdesign_verification_records(
    subdesigns: list[Any],
    *,
    gy_content_hash: Any,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for child in subdesigns:
        for port in getattr(child, "provides", []):
            authority = getattr(port, "provided_authority", None)
            if authority is None:
                continue
            records.append(
                _subdesign_verification_record(
                    child=child,
                    port=port,
                    gy_content_hash=gy_content_hash,
                )
            )
    return records


def _subdesign_verification_record(
    *,
    child: Any,
    port: Any,
    gy_content_hash: Any,
) -> dict[str, Any]:
    ref = str(getattr(child, "internal_trace_ref", "") or "")
    verification_id = (
        ref.rsplit("#", 1)[-1]
        if "#" in ref
        else f"subdesign-{_artifact_slug(str(child.parent_workspace_id or 'root'))}-{child.subdesign_id}"
    )
    authority = port.provided_authority
    producer_roots = list(getattr(child, "producer_roots", []) or [])
    return {
        "verification_id": verification_id,
        "subdesign_contract_ref": ref,
        "writer_role": "system_verifier",
        "produced_by": "tools/quality/validation/check_layer3_gy_composition_artifacts.py",
        "binding": {
            "subdesign_id": child.subdesign_id,
            "workspace_id": child.workspace_id,
            "parent_workspace_id": child.parent_workspace_id,
            "port_id": port.port_id,
            "search_exit_ref": child.search_exit.exit_id,
            "search_exit_content_hash": _search_exit_binding_hash(
                child.search_exit.model_dump(mode="json"),
                gy_content_hash=gy_content_hash,
            ),
            "producer_root_refs": [
                value
                for root in producer_roots
                for value in (root.artifact_id, root.uri)
                if value
            ],
            "producer_root_content_hashes": [
                root.content_hash for root in producer_roots if root.content_hash
            ],
            "provided_authority_content_hash": _stable_content_hash(
                authority.model_dump(mode="json"),
                gy_content_hash=gy_content_hash,
            ),
        },
        "subdesign_contract": child.model_dump(mode="json"),
        "authority_boundary": authority.model_dump(mode="json"),
    }


def _synthetic_composition_subdesigns(*, artifact_ref_factory: Any) -> list[Any]:
    return [
        _synthetic_subdesign(
            "chapter-a",
            artifact_ref_factory=artifact_ref_factory,
        ),
        _synthetic_subdesign(
            "chapter-b",
            artifact_ref_factory=artifact_ref_factory,
        ),
    ]


def _synthetic_empty_meet_subdesigns(*, artifact_ref_factory: Any) -> list[Any]:
    return [
        _synthetic_subdesign(
            "chapter-a",
            authority=_synthetic_authority(
                "boundary-a",
                artifact_ref_factory=artifact_ref_factory,
                authoritative_for=["chapter_a_only"],
            ),
            verification_suffix="empty-meet",
            artifact_ref_factory=artifact_ref_factory,
        ),
        _synthetic_subdesign(
            "chapter-b",
            authority=_synthetic_authority(
                "boundary-b",
                artifact_ref_factory=artifact_ref_factory,
                authoritative_for=["chapter_b_only"],
            ),
            verification_suffix="empty-meet",
            artifact_ref_factory=artifact_ref_factory,
        ),
    ]


def _synthetic_subdesign(
    subdesign_id: str,
    *,
    artifact_ref_factory: Any,
    authority: Any | None = None,
    verification_suffix: str | None = None,
) -> Any:
    from polisyos.pdc import (
        FrontierSnapshot,
        PortSpec,
        SearchBudgetRecord,
        SearchCoverageRecord,
        SearchExitContract,
        SearchIncompletenessRecord,
        SearchQualityRecord,
        SearchTerminalKind,
        SearchTerminalState,
        SearchUnresolvedRecord,
        SubDesignContract,
    )

    authority = authority or _synthetic_authority(
        f"boundary-{subdesign_id}",
        artifact_ref_factory=artifact_ref_factory,
    )
    workspace_id = f"ws-{subdesign_id}"
    artifact = _synthetic_artifact_ref(
        f"estimate-{workspace_id}",
        artifact_ref_factory,
    )
    search_exit = SearchExitContract(
        exit_id=f"exit-{workspace_id}",
        workspace_id=workspace_id,
        cycle_index=1,
        terminal_state=SearchTerminalState(
            kind=SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE,
            reason="test child workspace grounded a port",
            blocking_obligations=[],
        ),
        frontier_snapshot=FrontierSnapshot(
            snapshot_id=f"frontier-{workspace_id}",
            workspace_id=workspace_id,
            cycle_index=1,
            promoted_candidates=[artifact],
            shadow_candidates=[],
            rejected_candidates=[],
            dominated_candidates=[],
            current_best=[artifact],
            frontier_metrics={"candidate_count": 1},
        ),
        incompleteness_record=SearchIncompletenessRecord(
            record_id=f"incomplete-{workspace_id}",
            workspace_id=workspace_id,
            coverage=SearchCoverageRecord(
                operations_attempted=["VERIFY"],
                source_classes_checked=["official"],
            ),
            search_quality=SearchQualityRecord(
                recall_at_known_seeds=1.0,
                freshness_ok=True,
            ),
            unresolved=SearchUnresolvedRecord(),
            budget=SearchBudgetRecord(consumed={}, remaining={}, exhausted=[]),
            next_best_actions=[],
            ceiling_classification="domain_ceiling",
        ),
        budget_ledger={"consumed": {}, "remaining": {}},
        output_artifacts=[artifact],
        authority_boundary=authority,
        next_best_actions=[],
    )
    port = PortSpec.model_validate(
        {
            "port_id": f"port-{subdesign_id}",
            "direction": "provides",
            "port_type": "Estimate",
            "claim_shape": {"claim_type": "policy_program_claim"},
            "multiplicity": {"min": 1, "max": 1},
            "provided_authority": authority.model_dump(mode="json"),
        },
        context={"writer_role": "system_verifier"},
    )
    suffix = f"-{verification_suffix}" if verification_suffix else ""
    return SubDesignContract(
        subdesign_id=subdesign_id,
        workspace_id=workspace_id,
        parent_workspace_id="ws-parent",
        scope={
            "domain": "energy",
            "jurisdiction": "PL",
            "scale": "chapter",
            "time_horizon": "2026",
            "posture": "advisory",
        },
        provides=[port],
        requires=[],
        coupling_declarations=[],
        producer_roots=[_synthetic_artifact_ref(f"root-{subdesign_id}", artifact_ref_factory)],
        search_exit=search_exit,
        unresolved_obligations=[],
        internal_trace_ref=(
            "repo://architecture/policy_design_case/"
            "layer3_gy_composition_certificates.json"
            f"#subdesign-ws-parent-{subdesign_id}{suffix}"
        ),
    )


def _synthetic_authority(
    boundary_id: str,
    *,
    artifact_ref_factory: Any,
    authoritative_for: list[str] | None = None,
) -> Any:
    from polisyos.pdc import AuthorityBoundary, EvidenceBasis

    return AuthorityBoundary(
        boundary_id=boundary_id,
        authoritative_for=authoritative_for or ["policy_program_claim"],
        may_not_use_for=["production_claim_authority_without_composition"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=["policyos.gy.composition.test.v1"],
        evidence_kind="measurement",
        decision_grade="decision_admissible",
        evidence_basis=EvidenceBasis(
            producer_roots=[
                _synthetic_artifact_ref(f"root-{boundary_id}", artifact_ref_factory)
            ],
            method_refs=["measurement.root"],
            calibration_refs=["calibration://test"],
            counterexamples_closed=["counterexample://closed"],
        ),
    )


def _synthetic_artifact_ref(artifact_id: str, artifact_ref_factory: Any) -> Any:
    return artifact_ref_factory(
        artifact_id=artifact_id,
        artifact_type="MeasurementRoot",
        payload={"artifact_id": artifact_id},
        schema_ref="policyos.gy.test.v1",
        uri=f"cas://{artifact_id}",
        version="v1",
    )


def _artifact_slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


def _stable_content_hash(value: object, *, gy_content_hash: Any) -> str:
    payload = json.loads(json.dumps(value, sort_keys=True))
    _normalise_generated_at(payload, in_planner_report=True)
    return gy_content_hash(payload)


def _search_exit_binding_hash(value: object, *, gy_content_hash: Any) -> str:
    payload = value if isinstance(value, dict) else {}
    authority_payload = payload.get("authority_boundary")
    binding_payload = {
        "exit_id": str(payload.get("exit_id") or ""),
        "workspace_id": str(payload.get("workspace_id") or ""),
        "terminal_state": payload.get("terminal_state") if isinstance(
            payload.get("terminal_state"),
            dict,
        ) else {},
        "authority_boundary_content_hash": _stable_content_hash(
            authority_payload,
            gy_content_hash=gy_content_hash,
        )
        if isinstance(authority_payload, dict)
        else "",
    }
    return _stable_content_hash(binding_payload, gy_content_hash=gy_content_hash)


def _emergent_grounding_verification_record(
    *,
    verification_id: str,
    grounding_ref: str,
    evidence_kind: str,
    decision_grade: str,
) -> dict[str, Any]:
    from polisyos.pdc import ArtifactRef

    root_a = ArtifactRef.from_payload(
        artifact_id="root-chapter-a",
        artifact_type="MeasurementRoot",
        payload={"artifact_id": "root-chapter-a"},
        schema_ref="policyos.gy.test.v1",
        uri="cas://root-chapter-a",
        version="v1",
    )
    root_b = ArtifactRef.from_payload(
        artifact_id="root-chapter-b",
        artifact_type="MeasurementRoot",
        payload={"artifact_id": "root-chapter-b"},
        schema_ref="policyos.gy.test.v1",
        uri="cas://root-chapter-b",
        version="v1",
    )
    return {
        "verification_id": verification_id,
        "grounding_ref": grounding_ref,
        "writer_role": "system_verifier",
        "produced_by": "tools/quality/validation/check_layer3_gy_composition_artifacts.py",
        "binding": {
            "grounding_ref": grounding_ref,
            "claim_refs": ["claim://program/system-effect"],
            "subdesign_refs": ["chapter-a", "chapter-b"],
            "producer_root_refs": [
                "root-chapter-a",
                "cas://root-chapter-a",
                "root-chapter-b",
                "cas://root-chapter-b",
            ],
            "producer_root_content_hashes": [
                root_a.content_hash,
                root_b.content_hash,
            ],
            "required_grounding": ["system_dynamics"],
        },
        "authority_boundary": {
            "boundary_id": f"boundary-{verification_id}",
            "authoritative_for": ["policy_program_claim"],
            "may_not_use_for": ["production_claim_authority_without_composition"],
            "source_authority": "deterministic_producer",
            "posture": "governed",
            "rule_version_refs": ["policyos.gy.composition.test.v1"],
            "evidence_kind": evidence_kind,
            "decision_grade": decision_grade,
            "evidence_basis": {
                "producer_roots": [root_a.model_dump(mode="json"), root_b.model_dump(mode="json")],
                "method_refs": ["polisyos.runtime.quality.design_axes.coupling_composition"],
                "calibration_refs": ["calibration://gyg-emergent-grounding"],
                "counterexamples_closed": ["p17:false-modularity", "p14:inflation"],
            },
        },
    }


def _p14_verification_record(
    *,
    verification_id: str,
    evidence_lines: list[dict[str, Any]],
    raw_count: int,
    effective_count: int,
    gy_content_hash: Any,
    artifact_ref_factory: Any,
) -> dict[str, Any]:
    lineage_records = [line["source_lineage"] for line in evidence_lines]
    return {
        "verification_id": verification_id,
        "writer_role": "system_verifier",
        "produced_by": "tools/quality/validation/check_layer3_gy_composition_artifacts.py",
        "binding": {
            "claim_refs": ["claim://program/system-effect"],
            "subdesign_refs": ["chapter-a", "chapter-b"],
            "producer_root_refs": ["root-chapter-a", "root-chapter-b"],
            "producer_root_content_hashes": [
                artifact_ref_factory(
                    artifact_id="root-chapter-a",
                    artifact_type="MeasurementRoot",
                    payload={"artifact_id": "root-chapter-a"},
                    schema_ref="policyos.gy.test.v1",
                    uri="cas://root-chapter-a",
                    version="v1",
                ).content_hash,
                artifact_ref_factory(
                    artifact_id="root-chapter-b",
                    artifact_type="MeasurementRoot",
                    payload={"artifact_id": "root-chapter-b"},
                    schema_ref="policyos.gy.test.v1",
                    uri="cas://root-chapter-b",
                    version="v1",
                ).content_hash,
            ],
            "evidence_line_content_hashes": [
                gy_content_hash(line) for line in evidence_lines
            ],
            "lineage_content_hashes": [
                gy_content_hash(lineage) for lineage in lineage_records
            ],
            "raw_evidence_line_count": raw_count,
            "effective_independent_evidence_count": effective_count,
        },
    }


def _gyg_p14_evidence_lines(*, independent: bool) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for index in range(2):
        line = _gyg_p14_evidence_line(index=index)
        if independent:
            line["source_lineage"] = {
                "source_id": f"source-{index}",
                "source_ref": _test_sha(f"source-{index}"),
                "lineage_refs": [_test_sha(f"lineage-{index}")],
                "corpus_id": f"corpus-{index}",
                "corpus_ancestry": [f"corpus-{index}"],
            }
            line["corpus_ancestry"] = [f"corpus-{index}"]
            line["author_pool"] = [f"author-{index}"]
            line["institution_pool"] = [f"institution-{index}"]
            line["preprocessing_pipeline_id"] = f"preprocessing-{index}"
            line["method_id"] = f"foundry.method.{index}"
            line["method_assumptions"] = [f"assumption-{index}"]
            line["identification_strategy_id"] = f"identification-{index}"
            line["shared_failure_modes"] = [f"failure-mode-{index}"]
        lines.append(line)
    return lines


def _gyg_p14_evidence_line(*, index: int) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": f"composition-line-{index}",
        "portfolio_id": "portfolio-composition",
        "portfolio_strand_id": "composition-grounding",
        "claim_id": "claim://program/system-effect",
        "evidence_strand": "data",
        "source_lineage": {
            "source_id": "shared-admin-source",
            "source_ref": _test_sha("shared-admin-source"),
            "lineage_refs": [_test_sha("shared-lineage")],
            "corpus_id": "shared-corpus",
            "corpus_ancestry": ["shared-corpus"],
        },
        "corpus_ancestry": ["shared-corpus"],
        "author_pool": ["same-analysis-cell"],
        "institution_pool": ["same-policy-lab"],
        "preprocessing_pipeline_id": "same-preprocessing",
        "method_id": "foundry.shared.method",
        "method_assumptions": ["same assumptions"],
        "identification_strategy_id": "same-identification",
        "shared_failure_modes": ["same-bias"],
        "specification_id": f"shared-spec-{index}",
        "producer_identity": {
            "component": "polisyos.foundry.methods.causal",
            "version": "test",
            "owner": "team-runtime-quality",
        },
        "execution_context": {
            "run_id": "run-composition",
            "job_id": f"job-composition-{index}",
            "tenant_id": "tenant-test",
            "trace_id": f"trace-composition-{index}",
        },
        "evidence_ref": _test_sha(f"composition-evidence-{index}"),
        "runtime_event_ref": _test_sha(f"composition-event-{index}"),
    }


def _test_sha(value: str) -> str:
    return "sha256:" + value * 64


def _normalise_payload_for_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove run-clock drift from otherwise replayable GY-G proof artifacts."""

    normalised = json.loads(json.dumps(payload))
    _normalise_generated_at(normalised, in_planner_report=False)
    return normalised


def _normalise_generated_at(value: Any, *, in_planner_report: bool) -> None:
    if isinstance(value, dict):
        current_is_planner_report = in_planner_report or value.get("report_type") == (
            "canonical_acquisition_planner_report"
        )
        if current_is_planner_report and "generated_at" in value:
            value["generated_at"] = "recomputed-run-clock-normalized"
        for key, child in value.items():
            _normalise_generated_at(
                child,
                in_planner_report=current_is_planner_report
                or key == "canonical_planner_report",
            )
    elif isinstance(value, list):
        for child in value:
            _normalise_generated_at(child, in_planner_report=in_planner_report)


def _validate_certificate_payload(
    payload: dict[str, Any],
    issues: list[dict[str, str]],
    *,
    path: str,
) -> None:
    if payload.get("schema_version") != (
        "policyos.policy_design_case.layer3_gy.composition_certificates.v1"
    ):
        issues.append({"code": "layer3_gy_composition_schema_invalid", "path": path})
    if payload.get("writer_role") != "system_verifier":
        issues.append({"code": "layer3_gy_composition_writer_role_invalid", "path": path})
    if payload.get("produced_by") != (
        "tools/quality/validation/check_layer3_gy_composition_artifacts.py"
    ):
        issues.append({"code": "layer3_gy_composition_producer_invalid", "path": path})
    certificates = payload.get("certificates")
    if not isinstance(certificates, list) or len(certificates) < 2:
        issues.append({"code": "layer3_gy_composition_certificates_missing", "path": path})
        return
    verdicts = {str(item.get("verdict")) for item in certificates if isinstance(item, dict)}
    if "composable" not in verdicts:
        issues.append({"code": "layer3_gy_composition_independent_certificate_missing"})
    receipts = payload.get("composition_receipts")
    if not isinstance(receipts, list) or not receipts:
        issues.append({"code": "layer3_gy_composition_receipts_missing", "path": path})
    else:
        receipt_refs = {
            str(item.get("receipt_ref") or "")
            for item in receipts
            if isinstance(item, dict)
        }
        for item in certificates:
            if not isinstance(item, dict) or item.get("verdict") != "composable":
                continue
            if str(item.get("composition_receipt_ref") or "") not in receipt_refs:
                issues.append({"code": "layer3_gy_composition_receipt_ref_unresolved"})
    if not isinstance(payload.get("p14_independence_verifications"), list):
        issues.append({"code": "layer3_gy_composition_p14_verifications_missing"})
    if not isinstance(payload.get("subdesign_contract_verifications"), list):
        issues.append({"code": "layer3_gy_composition_subdesign_verifications_missing"})
    if not isinstance(payload.get("independence_consistency_verifications"), list):
        issues.append({"code": "layer3_gy_composition_consistency_verifications_missing"})
    if not isinstance(payload.get("emergent_grounding_verifications"), list):
        issues.append({"code": "layer3_gy_composition_grounding_verifications_missing"})
    feedback = [
        item
        for item in certificates
        if isinstance(item, dict)
        and item.get("coupling_gate", {}).get("invalid_reason")
        == "feedback_requires_joint_grounding"
    ]
    if not feedback:
        issues.append({"code": "layer3_gy_composition_feedback_rejection_missing"})
    elif any(item.get("authority_flow") for item in feedback):
        issues.append({"code": "layer3_gy_composition_feedback_authority_flow_leaked"})
    recursive_runs = payload.get("recursive_runs")
    if not isinstance(recursive_runs, list):
        issues.append({"code": "layer3_gy_composition_recursive_runs_missing", "path": path})
    else:
        from polisyos.runtime.quality.recursive_generation_cycle import (
            RecursiveGenerationCycleRun,
        )

        for index, item in enumerate(recursive_runs):
            try:
                RecursiveGenerationCycleRun.model_validate(item)
            except ValueError as exc:
                issues.append(
                    {
                        "code": "layer3_gy_recursive_run_semantically_invalid",
                        "path": f"{path}.recursive_runs[{index}]",
                        "error": str(exc),
                    }
                )
        depth_n_runs = [
            item
            for item in recursive_runs
            if isinstance(item, dict)
            and int(item.get("observed_max_depth") or -1) >= 3
            and any(
                isinstance(node, dict)
                and isinstance(node.get("joint_simulation"), dict)
                and bool(node["joint_simulation"].get("interaction_terms"))
                and isinstance(node.get("composition_certificate"), dict)
                for node in item.get("nodes") or []
            )
        ]
        if not depth_n_runs:
            issues.append({"code": "layer3_gy_composition_depth_n_run_missing"})
    strangle = payload.get("depth_n_strangle_receipt")
    if not isinstance(strangle, dict):
        issues.append({"code": "layer3_gy_depth_n_strangle_receipt_missing"})
    elif (
        strangle.get("status") != "strangled"
        or strangle.get("production_fixture_callers") != []
        or not strangle.get("production_default_routes")
        or not str(strangle.get("default_controller") or "").endswith(
            "RecursiveGenerationCycleController"
        )
    ):
        issues.append({"code": "layer3_gy_depth_n_strangle_receipt_red"})
    for index, certificate in enumerate(certificates):
        if not isinstance(certificate, dict):
            issues.append(
                {
                    "code": "layer3_gy_composition_certificate_not_object",
                    "path": f"{path}.certificates[{index}]",
                }
            )
            continue
        if not certificate.get("certificate_id"):
            issues.append(
                {
                    "code": "layer3_gy_composition_certificate_id_missing",
                    "path": f"{path}.certificates[{index}]",
                }
            )
        gate = certificate.get("coupling_gate")
        if not isinstance(gate, dict) or not gate.get("verdict"):
            issues.append(
                {
                    "code": "layer3_gy_composition_coupling_gate_missing",
                    "path": f"{path}.certificates[{index}].coupling_gate",
                }
            )


def _read_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append({"code": "layer3_gy_composition_artifact_missing", "path": str(path)})
        return {}
    except json.JSONDecodeError as exc:
        issues.append(
            {
                "code": "layer3_gy_composition_artifact_invalid_json",
                "path": str(path),
                "error": str(exc),
            }
        )
        return {}
    if not isinstance(payload, dict):
        issues.append({"code": "layer3_gy_composition_artifact_not_object", "path": str(path)})
        return {}
    return payload


def _ensure_src_path(repo_root: Path) -> None:
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-format", choices=("json", "text"), default="text")
    parser.add_argument("--check", action="store_true", help="Validate committed artifacts.")
    parser.add_argument("--write", action="store_true", help="Regenerate committed proof artifacts.")
    parser.add_argument(
        "--corrupt-field-drift-check",
        action="store_true",
        help="Mutate a committed field in memory and assert drift is detectable.",
    )
    parser.add_argument(
        "--source-flip-mutations",
        action="store_true",
        help="Run restoring Stage-3 source mutations serially.",
    )
    args = parser.parse_args(argv)
    if args.check and args.write:
        parser.error("--check and --write are mutually exclusive")

    if args.source_flip_mutations:
        results = run_source_flip_mutations(Path(args.repo_root).resolve())
        report = {
            "results": list(results),
            "validator_wall_time_seconds": round(time.perf_counter() - started, 6),
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if all(row.get("result") == "RED" for row in results) else 1

    with contextlib.redirect_stdout(sys.stderr):
        report = validate(
            Path(args.repo_root).resolve(),
            write=args.write,
            corrupt_field_drift_check=args.corrupt_field_drift_check,
        )
    report["validator_wall_time_seconds"] = round(time.perf_counter() - started, 6)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Layer 3 GY composition artifacts: {report['status']}")
        for issue in report["issues"]:
            print(json.dumps(issue, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
