"""Canonical child-subject routing for source-conditioned N4 fixture responses."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from polisyos.runtime.quality.cycle_substrate import (
    cycle_job_design_problem_ref,
    generic_n4_child_profile_selection_ref,
)
from polisyos.runtime.quality.design_generation import N4CandidateChildProblem
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_V3_SCHEMA_VERSION,
    DesignProblem,
)
from tests._helpers.controlled_candidate_profile import _problem
from tests._helpers.generic_n4_served_replay import (
    _child_conditioned_provider_profile_bindings,
    _complete_child_conditioned_provider_request,
)


def _ref(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class _ChildProviderProfile:
    """Small response owner for one test-only source intervention."""

    profile_selection_ref: str
    intervention_id: str

    def completion(
        self,
        request: dict[str, Any],
        *,
        raw_request: bytes,
        compiled_problem_ref: str | None,
    ) -> dict[str, Any]:
        assert compiled_problem_ref is not None
        assert request["subject_ref"] == compiled_problem_ref
        assert raw_request == b"source-owned child request"
        return {"interventions": [self.intervention_id]}


def _child_problem(
    *,
    parent_problem: DesignProblem,
    problem_id: str,
    source_result_ref: str,
    source_atom_ref: str,
    semantic_ref: str,
    job_id: str,
) -> N4CandidateChildProblem:
    """Build one typed child with source lineage and execution-scoped context."""
    source_context = {
        "tenant_id": "tenant-test",
        "cell_id": "cell-test",
        "job_id": job_id,
        "run_id": f"run-{job_id}",
    }
    child_payload = _problem(problem_id).model_dump(mode="python")
    child_payload["schema_version"] = DESIGN_PROBLEM_V3_SCHEMA_VERSION
    child_payload["nl_provenance"]["source_context"] = source_context
    child_payload["runtime_hints"] = {
        "n4_candidate_child_source": {
            "purpose": "candidate_lever_exploration_only",
            "parent_design_problem_ref": cycle_job_design_problem_ref(parent_problem),
            "source_result_ref": source_result_ref,
            "source_atom_refs": [source_atom_ref],
            "semantic_ref": semantic_ref,
        }
    }
    child = DesignProblem.model_validate(child_payload)
    return N4CandidateChildProblem(
        problem=child,
        source_result_ref=source_result_ref,
        source_atom_refs=(source_atom_ref,),
        semantic_ref=semantic_ref,
    )


def test_actual_canonical_child_subjects_select_only_their_source_intervention() -> None:
    """Bind runtime child refs to prepared profiles while preserving the parent reply."""
    parent = _problem("parent")
    rows = (
        (
            "tax_child",
            "source-result-a",
            "source-atom-a",
            "semantic-a",
            "prepared-job-a",
            "actual-job-a",
            "tax-credit",
        ),
        (
            "procurement_child",
            "source-result-b",
            "source-atom-b",
            "semantic-b",
            "prepared-job-b",
            "actual-job-b",
            "procurement-backstop",
        ),
    )
    prepared_children = tuple(
        _child_problem(
            parent_problem=parent,
            problem_id=problem_id,
            source_result_ref=_ref(source_result),
            source_atom_ref=_ref(source_atom),
            semantic_ref=_ref(semantic),
            job_id=prepared_job,
        )
        for (
            problem_id,
            source_result,
            source_atom,
            semantic,
            prepared_job,
            _actual_job,
            _intervention_id,
        ) in rows
    )
    actual_children = tuple(
        _child_problem(
            parent_problem=parent,
            problem_id=problem_id,
            source_result_ref=_ref(source_result),
            source_atom_ref=_ref(source_atom),
            semantic_ref=_ref(semantic),
            job_id=actual_job,
        )
        for (
            problem_id,
            source_result,
            source_atom,
            semantic,
            _prepared_job,
            actual_job,
            _intervention_id,
        ) in rows
    )
    prepared_refs = tuple(
        cycle_job_design_problem_ref(child.problem) for child in prepared_children
    )
    actual_refs = tuple(cycle_job_design_problem_ref(child.problem) for child in actual_children)
    assert set(prepared_refs).isdisjoint(actual_refs)

    profiles_by_selection: dict[str, _ChildProviderProfile] = {}
    for row, child in zip(rows, prepared_children, strict=True):
        selection_ref = generic_n4_child_profile_selection_ref(
            child.problem,
            parent_problem_ref=cycle_job_design_problem_ref(parent),
            source_result_ref=child.source_result_ref,
            source_atom_refs=child.source_atom_refs,
            semantic_ref=child.semantic_ref,
        )
        profiles_by_selection[selection_ref] = _ChildProviderProfile(
            profile_selection_ref=selection_ref,
            intervention_id=row[-1],
        )

    bindings = _child_conditioned_provider_profile_bindings(
        parent_problem=parent,
        children=actual_children,
        child_profiles_by_selection_ref=profiles_by_selection,
    )
    assert set(bindings) == set(actual_refs)
    assert not set(bindings).intersection(prepared_refs)

    parent_response = {"interventions": ["parent-tax-credit", "parent-procurement-backstop"]}
    parent_calls: list[dict[str, Any]] = []

    def complete_parent(
        request: dict[str, Any], *, raw_request: bytes, compiled_problem_ref: str | None
    ) -> dict[str, Any]:
        parent_calls.append(request)
        assert compiled_problem_ref == cycle_job_design_problem_ref(parent)
        assert raw_request == b"source-owned parent request"
        return parent_response

    for row, subject_ref in zip(rows, actual_refs, strict=True):
        response = _complete_child_conditioned_provider_request(
            subject_ref=subject_ref,
            request={"subject_ref": subject_ref},
            raw_request=b"source-owned child request",
            compiled_problem_ref=subject_ref,
            parent_completion=complete_parent,
            child_profiles_by_problem_ref=bindings,
            child_keys=tuple(profiles_by_selection),
        )
        assert response == {"interventions": [row[-1]]}

    original_parent_response = {"interventions": list(parent_response["interventions"])}
    assert (
        _complete_child_conditioned_provider_request(
            subject_ref=cycle_job_design_problem_ref(parent),
            request={"subject_ref": cycle_job_design_problem_ref(parent)},
            raw_request=b"source-owned parent request",
            compiled_problem_ref=cycle_job_design_problem_ref(parent),
            parent_completion=complete_parent,
            child_profiles_by_problem_ref=bindings,
            child_keys=tuple(profiles_by_selection),
        )
        is parent_response
    )
    assert parent_response == original_parent_response
    assert len(parent_calls) == 1
