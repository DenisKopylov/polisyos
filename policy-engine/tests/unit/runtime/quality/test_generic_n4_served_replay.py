"""Canonical child-subject routing for source-conditioned N4 fixture responses."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData
from polisyos.ir.analytics.ncm import (
    ExogenousSpec,
    NCMSpec,
    StructuralEquation,
    candidate_ncm_spec_from_declaration,
)
from polisyos.runtime.quality.cycle_substrate import (
    cycle_job_design_problem_ref,
    generic_n4_child_profile_selection_ref,
)
from polisyos.runtime.quality.design_generation import N4CandidateChildProblem
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_V3_SCHEMA_VERSION,
    DesignProblem,
)
from polisyos.runtime.quality.generic_simulation_admission import GenericCycleN5RequestProfileV1
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    _effective_evidence_state,
)
from tests._helpers.controlled_candidate_profile import _problem
from tests._helpers.generic_n4_served_replay import (
    _ORIGINAL_SECOND_CAPTURE_RECORDING_ID,
    _bind_child_formalizer_frame,
    _child_conditioned_provider_profile_bindings,
    _complete_child_conditioned_provider_request,
    _ncm_declared_variables,
    _require_child_ncm_scope,
    _selected_child_n5_baseline,
)


def _ref(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def test_selected_child_ncm_baseline_and_model_scope_are_exact() -> None:
    """Typed child N5 evidence includes its modeled variables and refuses foreign fields."""
    declaration = SimpleNamespace(
        target_world_slot="global.tax_rate",
        outcome_variable="employment_retention",
        target_baseline=0.0,
        outcome_baseline=1.0,
        outcome_per_target_unit=0.5,
        outcome_noise_stddev=0.01,
    )
    ncm = candidate_ncm_spec_from_declaration(declaration)
    expected_variables = {"global.tax_rate", "employment_retention"}
    assert _ncm_declared_variables(ncm) == expected_variables
    _require_child_ncm_scope(
        ncm,
        target_world_slot="global.tax_rate",
        outcome_variable="employment_retention",
    )
    broad_baseline = {
        "global.tax_rate": 0.0,
        "employment_retention": 1.0,
        "cells.distress_score": 0.0,
    }

    with pytest.raises(ValidationError, match="evidence variables not in NCM"):
        NCMQueryData(ncm_spec=ncm, evidence=broad_baseline, n_samples=1)

    selected_baseline = _selected_child_n5_baseline(
        broad_baseline,
        target_world_slot="global.tax_rate",
        outcome_variable="employment_retention",
        overrides={},
    )
    assert selected_baseline == {
        "global.tax_rate": 0.0,
        "employment_retention": 1.0,
    }
    assert _selected_child_n5_baseline(
        broad_baseline,
        target_world_slot="global.tax_rate",
        outcome_variable="employment_retention",
        overrides={"target_baseline": 0.25, "outcome_baseline": 1.5},
    ) == {"global.tax_rate": 0.25, "employment_retention": 1.5}
    profile = GenericCycleN5RequestProfileV1(
        budget_ref="budget://test/selected-ncm",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state=selected_baseline,
    )
    query = NCMQueryData(
        ncm_spec=ncm,
        evidence=profile.baseline_state,
        n_samples=1,
    )
    assert query.evidence == profile.baseline_state == selected_baseline

    # A future selected model with another endogenous input is not silently
    # reduced to the current two-variable fixture declaration.
    expanded_fields = ncm.model_dump(mode="python")
    expanded_fields["scm_spec"] = None
    expanded_fields["endogenous_vars"].append("modeled_context")
    expanded_fields["exogenous_specs"].append(
        ExogenousSpec(
            variable="U_modeled_context",
            associated_endogenous="modeled_context",
            distribution_params={"mean": 0.0, "std": 0.0},
        )
    )
    expanded_fields["structural_equations"].append(
        StructuralEquation(
            variable="modeled_context",
            exogenous="U_modeled_context",
            equation_type="linear",
            equation_params={"intercept": 0.0, "coefficients": {}},
        )
    )
    expanded_ncm = NCMSpec.model_validate(expanded_fields)
    assert "modeled_context" in _ncm_declared_variables(expanded_ncm)
    with pytest.raises(ValueError, match="controlled_n4_selected_ncm_model_scope_unexpected"):
        _require_child_ncm_scope(
            expanded_ncm,
            target_world_slot="global.tax_rate",
            outcome_variable="employment_retention",
        )


def test_legacy_baseline_evidence_none_remains_distinct_from_explicit_empty() -> None:
    """Child scoping does not change the established None versus empty meaning."""
    baseline = {"modelled": 1.0}
    legacy = _effective_evidence_state(
        SimpleNamespace(baseline_state=baseline, evidence_state=None)
    )
    explicit_empty = _effective_evidence_state(
        SimpleNamespace(baseline_state=baseline, evidence_state={})
    )

    assert legacy == (baseline, "legacy_baseline_state_compat")
    assert explicit_empty == ({}, "explicit_evidence_state")


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


def test_child_formalizer_keeps_typed_source_domain_for_open_problem_domain() -> None:
    """An open DesignProblem domain label must not replace Trinity's typed domain."""
    import json
    from pathlib import Path

    from polisyos.scientist.agent.formalizer import (
        TrinityBundle,
        _normalize_formalizer_payload_for_validation,
        build_production_metric_taxonomy,
    )

    repo_root = Path(__file__).resolve().parents[4]
    recording_payload = json.loads(
        (
            repo_root
            / "architecture/policy_design_case/layer3_gy_design_generation_replay_recordings.json"
        ).read_text(encoding="utf-8")
    )
    (recording,) = tuple(
        row
        for row in recording_payload["recordings"]
        if row["recording_id"] == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
    )
    formalizer_payload = json.loads(recording["responses"][8]["raw_response"])
    child_problem = _problem("open_domain_child").model_copy(
        update={"domain": "ua_msme_cgf_decisive_capture"}
    )

    _bind_child_formalizer_frame(formalizer_payload, child_problem=child_problem)

    assert child_problem.domain == "ua_msme_cgf_decisive_capture"
    assert formalizer_payload["problem_frame"]["domain"] == "fiscal"
    assert formalizer_payload["problem_frame"]["problem_id"] == child_problem.design_problem_id
    normalized, _healing_events = _normalize_formalizer_payload_for_validation(
        formalizer_payload,
        taxonomy=build_production_metric_taxonomy(),
        fail_unknown_metrics=False,
        schema_healing_mode="audit",
    )
    bundle = TrinityBundle.model_validate(normalized)
    assert bundle.problem_frame.domain == "fiscal"
    assert bundle.problem_frame.problem_id == child_problem.design_problem_id
