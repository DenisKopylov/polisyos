from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polisyos.scientist.methods.search.controller import SearchResult, SearchStatus
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
from polisyos.scientist.methods.search.transfer_context import TransferContext
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.policy_design.search import (
    HierarchicalSearchConfig,
    HierarchicalSearchCoordinator,
    StructureCandidate,
)

from .test_phase_b_output import _candidate, _evaluation_vector


def _persist_seed(
    registry: ParetoRegistry,
    candidate: PolicyCandidateSchema,
    *,
    candidate_id: str,
    transfer_context: TransferContext,
) -> PolicyCandidateSchema:
    stored_candidate = candidate.model_copy(update={"candidate_id": candidate_id})
    registry.update(
        f"source_{candidate_id}",
        candidate_hash=stored_candidate.candidate_hash(),
        evaluation=_evaluation_vector(stored_candidate),
        candidate_id=stored_candidate.candidate_id,
        policy_family=str(stored_candidate.metadata["policy_family"]),
        seed_payload=stored_candidate.model_dump(mode="json"),
        transfer_context=transfer_context,
    )
    return stored_candidate


def _observe_seed_reads(
    monkeypatch: pytest.MonkeyPatch,
    registry: ParetoRegistry,
) -> list[TransferContext]:
    observed: list[TransferContext] = []
    get_seed_bundle = registry.get_seed_bundle

    def observe(context: TransferContext, *, max_seeds: int = 5) -> Any:
        observed.append(context)
        return get_seed_bundle(context, max_seeds=max_seeds)

    monkeypatch.setattr(registry, "get_seed_bundle", observe)
    return observed


def _coordinator(registry: ParetoRegistry) -> HierarchicalSearchCoordinator:
    return HierarchicalSearchCoordinator(
        pareto_registry=registry,
        config=HierarchicalSearchConfig(enable_hybrid_seeds=False),
    )


def _empty_search_result(structure: StructureCandidate, loop_id: str) -> SearchResult:
    return SearchResult(
        search_id=f"{loop_id}:{structure.structure_id}",
        status=SearchStatus.CONVERGED,
        best_candidate=structure.candidate.as_search_payload(),
        best_objective=0.0,
        iterations_completed=0,
        history=[],
        stopping_reason="test_parameter_search_not_run",
        total_duration_seconds=0.0,
        stage_a_evaluations=0,
        stage_b_evaluations=0,
    )


def test_run_forwards_outer_context_to_persisted_structure_seed_without_changing_loop_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "registry"
    publisher = ParetoRegistry(root)
    candidate = _candidate()
    stored_seed = _persist_seed(
        publisher,
        candidate,
        candidate_id="persisted_seed",
        transfer_context=TransferContext(
            task_family="nested_family",
            domain="target_domain",
            run_id="registry_source_run",
            tenant_hash="tenant_a",
        ),
    )

    # A fresh owner instance proves the seed is read from the persisted registry.
    registry = ParetoRegistry(root)
    observed = _observe_seed_reads(monkeypatch, registry)
    coordinator = _coordinator(registry)
    parameter_calls: list[tuple[str, dict[str, Any] | None]] = []

    def skip_numeric_parameter_search(
        structure: StructureCandidate,
        *,
        loop_id: str,
        stage_b_evaluator: Any,
        stage_a_evaluator: Any = None,
        initial_context: dict[str, Any] | None = None,
    ) -> SearchResult:
        del stage_b_evaluator, stage_a_evaluator
        parameter_calls.append((loop_id, initial_context))
        return _empty_search_result(structure, loop_id)

    monkeypatch.setattr(coordinator, "run_parameter_search", skip_numeric_parameter_search)
    initial_context = {
        "run_id": "outer_run",
        "domain": "target_domain",
        "tenant_hash": "tenant_a",
        "policy_search_context": {"task_family": "nested_family"},
    }
    result = coordinator.run(
        candidate,
        loop_id="parameter_loop",
        stage_b_evaluator=lambda *_: {},
        initial_context=initial_context,
    )

    assert len(observed) == 1
    assert (
        observed[0].task_family,
        observed[0].domain,
        observed[0].run_id,
        observed[0].tenant_hash,
    ) == ("nested_family", "target_domain", "outer_run", "tenant_a")
    assert any(
        structure.source == "transfer_seed"
        and structure.candidate.candidate_id == stored_seed.candidate_id
        for structure in result.state.structure_candidates
    )
    assert parameter_calls
    assert all(loop_id == "parameter_loop" for loop_id, _ in parameter_calls)
    assert all(context is initial_context for _, context in parameter_calls)
    assert observed[0].run_id not in {candidate.candidate_id, "parameter_loop"}


@pytest.mark.parametrize(
    ("initial_context", "expected"),
    [
        pytest.param(
            {
                "source_run_id": "source_run",
                "run_id": "outer_run",
                "transfer_context": TransferContext(
                    task_family="base_family",
                    domain="base_domain",
                    run_id="base_run",
                    tenant_hash="base_tenant",
                ),
                "task_family": "top_family",
                "domain": "outer_domain",
                "tenant_hash": "outer_tenant",
                "policy_search_context": {"task_family": "nested_family"},
            },
            {
                "task_family": "top_family",
                "domain": "outer_domain",
                "run_id": "source_run",
                "tenant_hash": "outer_tenant",
            },
            id="source-run-and-top-level-values-win",
        ),
        pytest.param(
            {
                "run_id": "outer_run",
                "transfer_context": TransferContext(
                    task_family="base_family",
                    domain="base_domain",
                    run_id="base_run",
                    tenant_hash="base_tenant",
                ),
                "policy_search_context": {"task_family": "nested_family"},
            },
            {
                "task_family": "nested_family",
                "domain": "base_domain",
                "run_id": "outer_run",
                "tenant_hash": "base_tenant",
            },
            id="run-and-nested-family-win-over-base",
        ),
        pytest.param(
            {
                "transfer_context": TransferContext(
                    task_family="base_family",
                    domain="base_domain",
                    run_id="base_run",
                    tenant_hash="base_tenant",
                )
            },
            {
                "task_family": "base_family",
                "domain": "base_domain",
                "run_id": "base_run",
                "tenant_hash": "base_tenant",
            },
            id="typed-base-is-preserved",
        ),
        pytest.param(
            {},
            {"task_family": "policy", "domain": "fiscal", "run_id": "unknown"},
            id="present-empty-context-keeps-resolver-defaults",
        ),
        pytest.param(
            None,
            {"task_family": "policy", "domain": "fiscal", "run_id": "candidate_policy"},
            id="absent-context-keeps-candidate-id-fallback",
        ),
    ],
)
def test_structure_seed_context_uses_existing_resolver_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    initial_context: dict[str, Any] | None,
    expected: dict[str, str],
) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    observed = _observe_seed_reads(monkeypatch, registry)
    _coordinator(registry).generate_structure_candidates(
        _candidate(), initial_context=initial_context
    )

    assert len(observed) == 1
    for field, value in expected.items():
        assert getattr(observed[0], field) == value


def test_structure_seed_reader_rejects_wrong_task_family_and_tenant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "registry"
    publisher = ParetoRegistry(root)
    candidate = _candidate()
    _persist_seed(
        publisher,
        candidate,
        candidate_id="wrong_family_seed",
        transfer_context=TransferContext(
            task_family="wrong_family",
            domain="target_domain",
            run_id="wrong_family_run",
            tenant_hash="tenant_a",
        ),
    )
    _persist_seed(
        publisher,
        candidate,
        candidate_id="wrong_tenant_seed",
        transfer_context=TransferContext(
            task_family="expected_family",
            domain="target_domain",
            run_id="wrong_tenant_run",
            tenant_hash="tenant_b",
        ),
    )

    registry = ParetoRegistry(root)
    observed = _observe_seed_reads(monkeypatch, registry)
    structures = _coordinator(registry).generate_structure_candidates(
        candidate,
        initial_context={
            "run_id": "outer_run",
            "domain": "target_domain",
            "tenant_hash": "tenant_a",
            "policy_search_context": {"task_family": "expected_family"},
        },
    )

    assert len(observed) == 1
    assert observed[0].task_family == "expected_family"
    assert observed[0].tenant_hash == "tenant_a"
    assert not any(structure.source == "transfer_seed" for structure in structures)
